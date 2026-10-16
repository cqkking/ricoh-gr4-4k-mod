#!/usr/bin/env python3
"""Ricoh GR IV (v1.11) T-Kernel RTOS Decompilation & Static Symbol Analyzer.

Performs automated ARMv7 (Cortex-A7) static analysis on 05_RTOS.bin (vaddr 0x53000000)
and 10_SHELLCMD.bin:
  1. Exports all 650 SHELLCMD RTOS function symbols to CSV and JSON.
  2. Scans MOVW/MOVT 32-bit immediate pairs (mask 0x0FFF0FFF) to verify active vs.
     linker --gc-sections stripped code paths.
  3. Disassembles and annotates key subsystems:
     - Image Control (Look) visibility check (0x533cc6e0 / payload 0x3e43f0) & Look table (0x53dbf360 / payload 0xdd7070)
     - 4K Movie Recipe & LiveView sequence planners (CreateRecipeSequenceMov4kExt @ 0x536498c4, Debug 4K Movie @ 0x5362e514)
     - 3840x2160p/30Hz video mode descriptor (@ 0x53055d44)
     - Active Chips&Media WAVE H.265 VDI Memory Manager (mm.c @ 0x5394da44 / 0x5394de10)
     - GC-stripped boundary around Socionext FJ_VideoEncoder_Setup (h265/h264) (.rodata @ 0x5435f00c, .text gap @ 0x53a93458..0x53a93500)
"""
import csv
import json
import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

RTOS_BASE = 0x53000000
RTOS_PAYLOAD_OFFSET = 0x00017D10


def parse_shellcmd(shellcmd_bytes: bytes):
    symbols = []
    for line in shellcmd_bytes.decode("ascii", errors="replace").splitlines():
        if "," not in line:
            continue
        name, addr_str = [x.strip() for x in line.split(",", 1)]
        if not name or addr_str == "0x00000000":
            continue
        vaddr = int(addr_str, 16)
        rtos_off = vaddr - RTOS_BASE
        pay_off = RTOS_PAYLOAD_OFFSET + rtos_off
        symbols.append({
            "name": name,
            "vaddr": f"{vaddr:#010x}",
            "rtos_offset": f"{rtos_off:#010x}",
            "payload_offset": f"{pay_off:#010x}",
        })
    return symbols


def find_movw_movt_xrefs(rtos: bytes, target_vaddr: int):
    lo = target_vaddr & 0xFFFF
    hi = (target_vaddr >> 16) & 0xFFFF
    movw_pat = 0x03000000 | ((lo & 0xF000) << 4) | (lo & 0x0FFF)
    movt_pat = 0x03400000 | ((hi & 0xF000) << 4) | (hi & 0x0FFF)
    mask = 0x0FFF0FFF
    words = struct.unpack(f"<{len(rtos)//4}I", rtos)
    hits = []
    for i, w in enumerate(words):
        if (w & mask) == movw_pat:
            rd = (w >> 12) & 0xF
            for j in range(max(0, i - 6), min(len(words), i + 8)):
                if (words[j] & mask) == movt_pat and ((words[j] >> 12) & 0xF) == rd:
                    vaddr = RTOS_BASE + i * 4
                    pay_off = RTOS_PAYLOAD_OFFSET + i * 4
                    hits.append({"vaddr": f"{vaddr:#010x}", "payload_offset": f"{pay_off:#010x}"})
                    break
    return hits


def read_cstring(rtos: bytes, vaddr: int, max_len: int = 96) -> str:
    off = vaddr - RTOS_BASE
    if off < 0 or off >= len(rtos):
        return ""
    chunk = rtos[off : off + max_len].split(b"\0", 1)[0]
    if not chunk or not all(32 <= b < 127 for b in chunk):
        return ""
    return chunk.decode("ascii", errors="replace")


def disasm_window(rtos: bytes, start_vaddr: int, end_vaddr: int, sym_map: dict):
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    start_off = start_vaddr - RTOS_BASE
    end_off = end_vaddr - RTOS_BASE
    lines = []
    reg_movw = {}
    for insn in md.disasm(rtos[start_off:end_off], start_vaddr):
        pay_off = RTOS_PAYLOAD_OFFSET + (insn.address - RTOS_BASE)
        comment = ""
        if insn.mnemonic == "movw":
            parts = [p.strip() for p in insn.op_str.split(",")]
            if len(parts) == 2 and parts[1].startswith("#"):
                reg_movw[parts[0]] = int(parts[1][1:], 0)
        elif insn.mnemonic == "movt":
            parts = [p.strip() for p in insn.op_str.split(",")]
            if len(parts) == 2 and parts[1].startswith("#") and parts[0] in reg_movw:
                hi = int(parts[1][1:], 0)
                full_addr = (hi << 16) | reg_movw[parts[0]]
                s = read_cstring(rtos, full_addr)
                if s:
                    comment = f'  ; {full_addr:#010x} -> "{s}"'
                else:
                    comment = f"  ; {full_addr:#010x}"
        elif insn.mnemonic in ("bl", "b", "beq", "bne", "ble", "bgt", "bls", "bhi"):
            if insn.op_str.startswith("#"):
                target = int(insn.op_str[1:], 0)
                if target in sym_map:
                    comment = f"  ; <{sym_map[target]}>"
        lines.append(
            f"{insn.address:#010x} (pay {pay_off:#010x}): {insn.bytes.hex():8s}  {insn.mnemonic:8s} {insn.op_str}{comment}"
        )
    return lines


def main():
    repo_root = Path(__file__).resolve().parent.parent
    unpacked_dir = repo_root / "firmware" / "unpacked" / "v1.11"
    rtos_path = unpacked_dir / "sections" / "05_RTOS.bin"
    shellcmd_path = unpacked_dir / "sections" / "10_SHELLCMD.bin"
    analysis_dir = repo_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    if not rtos_path.exists():
        print("ERROR: 05_RTOS.bin not found. Run 'python tools/fw_container.py unpack' first.", file=sys.stderr)
        return 1

    rtos = rtos_path.read_bytes()
    shellcmd_bytes = shellcmd_path.read_bytes()

    # 1. Export SHELLCMD symbol table
    symbols = parse_shellcmd(shellcmd_bytes)
    sym_map = {int(s["vaddr"], 16): s["name"] for s in symbols}

    csv_path = analysis_dir / "shellcmd_symbols.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "vaddr", "rtos_offset", "payload_offset"])
        writer.writeheader()
        writer.writerows(symbols)

    (analysis_dir / "shellcmd_symbols.json").write_text(
        json.dumps(symbols, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Exported {len(symbols)} SHELLCMD symbols to {csv_path}")

    # 2. Empirical Xref Survival Audit (Active vs GC-Stripped)
    probe_strings = [
        ("CreateRecipeSequenceMov4kExt", 0x53EB18D0),
        ("CreateRecipeSequenceMov4kRemote", 0x53EB18F0),
        ("[LVC] for Debug 4K Movie!", 0x53EAE744),
        ("7:3840x2160p/30Hz", 0x540404CC),
        ("GetLv4k", 0x53FD8124),
        ("ConvertToH264CodecDefsImageSize", 0x53EC91C0),
        ("src/H264Processor.cpp", 0x53EC71DC),
        ("RiberyM9M_Codec/.../H265/WAVE/Project/vdi/src/mm.c", 0x53CE8D58),
        ("H265_Wave_Initialize (high-level wrapper string)", 0x5436AC74),
        ("FJ_VideoEncoder_Setup(h265) (high-level wrapper string)", 0x5435F00C),
        ("FJ_VideoEncoder_Setup(h264) (high-level wrapper string)", 0x5435F178),
    ]
    xref_audit = []
    for label, s_vaddr in probe_strings:
        hits = find_movw_movt_xrefs(rtos, s_vaddr)
        xref_audit.append({
            "label": label,
            "string_vaddr": hex(s_vaddr),
            "status": "ACTIVE_REFERENCED" if hits else "RODATA_ONLY_GC_STRIPPED",
            "code_xrefs": hits,
        })

    # 3. Disassemble key RTOS routines
    windows = [
        {
            "id": "image_control_look_visibility",
            "title": "Image Control (Look) Visibility Check & Branch (Payload 0x003e43c0..0x003e4468)",
            "start_vaddr": 0x533CC6B0,
            "end_vaddr": 0x533CC758,
        },
        {
            "id": "movie_4k_recipe_sequence",
            "title": "Active 4K Movie Recipe Planner (CreateRecipeSequenceMov4kExt / Mov4kRemote @ 0x53649880..0x53649950)",
            "start_vaddr": 0x53649880,
            "end_vaddr": 0x53649950,
        },
        {
            "id": "lvc_debug_4k_movie",
            "title": "Active LiveView Controller Debug 4K Movie Handler (@ 0x5362e4d0..0x5362e570)",
            "start_vaddr": 0x5362E4D0,
            "end_vaddr": 0x5362E570,
        },
        {
            "id": "video_mode_3840x2160p_30hz",
            "title": "Active 3840x2160p/30Hz Video Timing Descriptor Setup (@ 0x53055d00..0x53055da0)",
            "start_vaddr": 0x53055D00,
            "end_vaddr": 0x53055DA0,
        },
        {
            "id": "h265_wave_vdi_mm",
            "title": "Active Chips&Media WAVE H.265 VDI Memory Manager (mm.c @ 0x5394da10..0x5394daa0)",
            "start_vaddr": 0x5394DA10,
            "end_vaddr": 0x5394DAA0,
        },
        {
            "id": "fj_video_encoder_gc_boundary",
            "title": "Linker --gc-sections Boundary Skipping FJ_VideoEncoder_Setup (.text @ 0x53a93440..0x53a93520)",
            "start_vaddr": 0x53A93440,
            "end_vaddr": 0x53A93520,
        },
    ]

    md_sections = [
        "# Ricoh GR IV (v1.11) T-Kernel RTOS Decompilation Audit\n",
        "- **Firmware**: `fwdc248b.bin` (v1.11, Official SHA-256 `a2f664dfca034059eb0fd6e18ab08684c326b4a034d85c164dad7e1ec9b5655f`)",
        "- **RTOS Load Base (`vaddr`)**: `0x53000000` (Payload offset `0x00017d10`, size `20,785,856` bytes)",
        "- **Conversion Formula**: `payload_offset = (vaddr - 0x53000000) + 0x00017d10`\n",
        "## 1. Make-or-Break Xref Audit: Active vs. Linker GC-Stripped Subsystems\n",
        "| Subsystem / Symbol String | `.rodata` VAddr | Status in `05_RTOS.bin` | Active `.text` Xref VAddr (Payload Offset) |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for item in xref_audit:
        xref_str = ", ".join(f"`{h['vaddr']}` (`{h['payload_offset']}`)" for h in item["code_xrefs"][:3]) or "*(None — stripped by `--gc-sections`)*"
        if len(item["code_xrefs"]) > 3:
            xref_str += f" (+{len(item['code_xrefs']) - 3} more)"
        md_sections.append(f"| `{item['label']}` | `{item['string_vaddr']}` | **{item['status']}** | {xref_str} |")
    md_sections.append("")

    audit_data = {
        "rtos_vaddr_base": hex(RTOS_BASE),
        "rtos_payload_offset": hex(RTOS_PAYLOAD_OFFSET),
        "xref_survival_audit": xref_audit,
        "windows": [],
    }

    for w in windows:
        dis_lines = disasm_window(rtos, w["start_vaddr"], w["end_vaddr"], sym_map)
        w_out = dict(w)
        w_out["start_vaddr"] = hex(w["start_vaddr"])
        w_out["end_vaddr"] = hex(w["end_vaddr"])
        w_out["disassembly"] = dis_lines
        audit_data["windows"].append(w_out)

        md_sections.append(f"## {w['title']}\n")
        md_sections.append("```armasm")
        md_sections.extend(dis_lines)
        md_sections.append("```\n")

    (analysis_dir / "rtos_decompilation_audit.json").write_text(
        json.dumps(audit_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (analysis_dir / "rtos_decompilation_audit.md").write_text("\n".join(md_sections), encoding="utf-8")
    print(f"Wrote RTOS decompilation audit to {analysis_dir / 'rtos_decompilation_audit.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

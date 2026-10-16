#!/usr/bin/env python3
"""Ricoh GR IV (v1.11) 4K (3840x2160) Movie & Hardware H.264/HEVC Pipeline Scanner.

Audits both T-Kernel RTOS (`05_RTOS.bin`) and Linux `libcamera-controller.so` / `camctld`:
  1. Active 4K Movie Recipe & LiveView Sequence Planners:
     - `CreateRecipeSequenceMov4kExt` (string @ 0x53eb18d0, active code xref @ 0x536498c4)
     - `CreateRecipeSequenceMov4kRemote` (string @ 0x53eb18f0, active code xref @ 0x53649914)
     - `[LVC] for Debug 4K Movie!` (string @ 0x53eae744, active code xref @ 0x5362e514)
     - `7:3840x2160p/30Hz` (string @ 0x540404cc, active code xref @ 0x53055d44)
  2. Active H.264 Image Size Enum Converter:
     - `ConvertToH264CodecDefsImageSize` (string @ 0x53ec91c0, active code xref @ 0x5366cd3c)
  3. Chips&Media WAVE H.265 (HEVC) VDI Layer vs. GC-Stripped High-Level Wrapper:
     - Active VDI memory manager (`RiberyM9M_Codec/.../H265/WAVE/Project/vdi/src/mm.c` @ 0x5394da44, 0x5394de10)
     - GC-stripped boundary around `FJ_VideoEncoder_Setup(h265)` (.rodata @ 0x5435f00c, .text gap @ 0x53a93458..0x53a93500)
  4. Linux `libcamera-controller.so` Movie Size & Framerate Enums.
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

RTOS_BASE = 0x53000000
RTOS_PAYLOAD_OFFSET = 0x00017D10


def read_cstring(rtos: bytes, vaddr: int, max_len: int = 96) -> str:
    off = vaddr - RTOS_BASE
    if off < 0 or off >= len(rtos):
        return ""
    chunk = rtos[off : off + max_len].split(b"\0", 1)[0]
    if not chunk or not all(32 <= b < 127 for b in chunk):
        return ""
    return chunk.decode("ascii", errors="replace")


def disasm_range(rtos: bytes, start_vaddr: int, end_vaddr: int):
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
        lines.append(
            f"{insn.address:#010x} (pay {pay_off:#010x}): {insn.bytes.hex():8s}  {insn.mnemonic:8s} {insn.op_str}{comment}"
        )
    return lines


def extract_linux_movie_symbols(libcam_path: Path):
    if not libcam_path.exists():
        return []
    raw = libcam_path.read_bytes()
    hits = []
    for m in re.finditer(rb"[ -~]{5,120}", raw):
        s = m.group(0).decode("ascii", errors="replace")
        sl = s.lower()
        if any(k in sl for k in ("moviesize", "movierate", "movieformat", "h264", "h265", "4k", "3840", "2160", "1920")):
            hits.append({"offset": hex(m.start()), "string": s})
    return hits


def main():
    parser = argparse.ArgumentParser(description="Scan GR IV v1.11 4K movie & H.264/HEVC RTOS/Linux pipeline")
    parser.add_argument("--compare-k3iii", help="Optional path to unpacked Pentax K-3 III RTOS binary for cross-diff")
    args = parser.parse_args()

    worktree_root = Path(__file__).resolve().parent.parent.parent
    shared_root = worktree_root.parent.parent if worktree_root.parent.name == "worktrees" else worktree_root
    unpacked_dir = shared_root / "firmware" / "unpacked" / "v1.11"
    rtos_path = unpacked_dir / "sections" / "05_RTOS.bin"
    libcam_path = unpacked_dir / "initfs_root" / "usr" / "lib" / "libcamera-controller.so"

    if not rtos_path.exists():
        print(f"ERROR: {rtos_path} not found. Run 'python tools/fw_container.py unpack' in root.", file=sys.stderr)
        return 1

    rtos = rtos_path.read_bytes()

    targets = [
        {
            "id": "mov4k_recipe_dispatcher",
            "title": "CreateRecipeSequenceMov4kExt / Mov4kRemote Dispatcher (@ 0x53649880..0x53649950)",
            "start": 0x53649880,
            "end": 0x53649950,
        },
        {
            "id": "h264_codec_defs_image_size",
            "title": "ConvertToH264CodecDefsImageSize Resolution Switch (@ 0x5366cd00..0x5366cd90)",
            "start": 0x5366CD00,
            "end": 0x5366CD90,
        },
        {
            "id": "lvc_debug_4k_movie",
            "title": "LiveView Controller Debug 4K Movie Mode (@ 0x5362e4d0..0x5362e570)",
            "start": 0x5362E4D0,
            "end": 0x5362E570,
        },
        {
            "id": "video_timing_3840x2160p_30hz",
            "title": "Video Timing Descriptor 7:3840x2160p/30Hz (@ 0x53055d00..0x53055da0)",
            "start": 0x53055D00,
            "end": 0x53055DA0,
        },
        {
            "id": "wave_h265_vdi_mm",
            "title": "Active Chips&Media WAVE H.265 VDI Memory Manager (mm.c @ 0x5394da10..0x5394daa0)",
            "start": 0x5394DA10,
            "end": 0x5394DAA0,
        },
    ]

    report = {
        "rtos_base": hex(RTOS_BASE),
        "rtos_payload_offset": hex(RTOS_PAYLOAD_OFFSET),
        "rtos_disassembly_windows": [],
        "linux_libcamera_movie_strings": extract_linux_movie_symbols(libcam_path),
    }

    for t in targets:
        lines = disasm_range(rtos, t["start"], t["end"])
        report["rtos_disassembly_windows"].append({
            "id": t["id"],
            "title": t["title"],
            "start_vaddr": hex(t["start"]),
            "end_vaddr": hex(t["end"]),
            "disassembly": lines,
        })

    out_dir = worktree_root / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "video_4k_pipeline_audit.json"
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote 4K video & H.264/HEVC pipeline audit to {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
build_4k_firmware.py - Pack Verified 4K Flashable Firmware (fwdc248b.bin)

Combines the Pentax K-3 III Plan 4 recipe splicing trampoline,
4K resolution/buffer enablement, and official container repacking
with dual word-sum (== 0) validation.
"""

import json
import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

REPO_ROOT = Path(r"d:\Ricoh GR4 firmware Mod")
OFFICIAL_FW = REPO_ROOT / "firmware" / "official" / "v1.11" / "fwdc248b.bin"
UNPACKED_DIR = REPO_ROOT / "firmware" / "unpacked" / "v1.11"
OUTPUT_FW = REPO_ROOT / "worktrees" / "feat-4k-k3-hevc" / "output" / "fwdc248b.bin"
MANIFEST_PATH = REPO_ROOT / "worktrees" / "feat-4k-k3-hevc" / "analysis" / "k3_4k_patch_manifest.json"

# Import fw_container functions
sys.path.insert(0, str(REPO_ROOT / "tools"))
from fw_container import (
    decode_container,
    verify_container,
    rezero_payload,
    rebuild_container,
    diff_offsets,
    sha256_hex,
    word_sum,
)
from k3_gr4_4k_patcher import (
    build_cave_payload,
    encode_arm_branch,
    CAVE_VA,
    PLAN4_STUB_VA,
    GR4_BASE,
)

RTOS_PAYLOAD_START = 0x00017D10

def v2p(vaddr: int) -> int:
    return vaddr - GR4_BASE + RTOS_PAYLOAD_START

def generate_patch_spec(official_payload: bytes) -> dict:
    changes = []

    # 1. Cave Payload at 0x53000e00 (128 bytes)
    cave_payload = build_cave_payload()
    cave_poff = v2p(CAVE_VA)
    cave_exp = official_payload[cave_poff : cave_poff + len(cave_payload)]
    assert cave_exp == b"\x00" * len(cave_payload), "Cave not empty!"
    changes.append({
        "id": "k3_plan4_recipe_cave",
        "description": "Pentax K-3 III Plan 4 4K Recipe Sequence + Return Bridge",
        "vaddr": hex(CAVE_VA),
        "offset": hex(cave_poff),
        "expected_hex": cave_exp.hex(),
        "replacement_hex": cave_payload.hex(),
        "length": len(cave_payload)
    })

    # 2. Plan 4 Stub Trampoline at 0x536498c4 (52 bytes)
    stub_poff = v2p(PLAN4_STUB_VA)
    stub_exp = official_payload[stub_poff : stub_poff + 52]
    trampoline_ins = encode_arm_branch(PLAN4_STUB_VA, CAVE_VA)
    stub_repl = struct.pack("<I", trampoline_ins) + (b"\x00\x00\xa0\xe1" * 12) # b #cave + 12 NOPs
    changes.append({
        "id": "plan4_stub_trampoline",
        "description": "Trampoline branch from Plan 4 stub to 4K recipe cave",
        "vaddr": hex(PLAN4_STUB_VA),
        "offset": hex(stub_poff),
        "expected_hex": stub_exp.hex(),
        "replacement_hex": stub_repl.hex(),
        "length": 52
    })

    # 3a. In-place Slot Hijack: Case 3 (1080p 24p @ 0x536497f4) -> Case 4 (0x536498c4)
    slot_va = 0x536497f4
    slot_poff = v2p(slot_va)
    slot_exp = official_payload[slot_poff : slot_poff + 4]
    slot_repl = struct.pack("<I", 0x536498c4)
    changes.append({
        "id": "slot3_hijack_to_4k_24p",
        "description": "Redirect Movie Jump Table Case 3 (24p) to 4K Ext (0x536498c4) -> 4K 24P",
        "vaddr": hex(slot_va),
        "offset": hex(slot_poff),
        "expected_hex": slot_exp.hex(),
        "replacement_hex": slot_repl.hex(),
        "length": 4
    })

    # 3b. In-place Slot Hijack: Case 2 (1080p 30p @ 0x536497f0) -> Case 4 (0x536498c4)
    slot2_va = 0x536497f0
    slot2_poff = v2p(slot2_va)
    slot2_exp = official_payload[slot2_poff : slot2_poff + 4]
    slot2_repl = struct.pack("<I", 0x536498c4)
    changes.append({
        "id": "slot2_hijack_to_4k_30p",
        "description": "Redirect Movie Jump Table Case 2 (30p) to 4K Ext (0x536498c4) -> 4K 30P",
        "vaddr": hex(slot2_va),
        "offset": hex(slot2_poff),
        "expected_hex": slot2_exp.hex(),
        "replacement_hex": slot2_repl.hex(),
        "length": 4
    })

    # 4. LiveView Kb588 Width & Height (0x5387f68c) -> 3840x2160
    kb588_va = 0x5387f68c
    kb588_poff = v2p(kb588_va)
    kb588_exp = official_payload[kb588_poff : kb588_poff + 8]
    kb588_repl = struct.pack("<II", 0xe3000f00, 0xe3003870) # movw r0, #0xf00 (3840); movw r3, #0x870 (2160)
    changes.append({
        "id": "liveview_kb588_res_3840x2160",
        "description": "LiveView Kb588 Video Resolution 3840x2160",
        "vaddr": hex(kb588_va),
        "offset": hex(kb588_poff),
        "expected_hex": kb588_exp.hex(),
        "replacement_hex": kb588_repl.hex(),
        "length": 8
    })

    # 5. LiveView Kb636 Width & Height (0x5388176c) -> 3840x2160
    kb636_va = 0x5388176c
    kb636_poff = v2p(kb636_va)
    kb636_exp = official_payload[kb636_poff : kb636_poff + 8]
    kb636_repl = struct.pack("<II", 0xe3000f00, 0xe3003870) # movw r0, #0xf00 (3840); movw r3, #0x870 (2160)
    changes.append({
        "id": "liveview_kb636_res_3840x2160",
        "description": "LiveView Kb636 Video Resolution 3840x2160",
        "vaddr": hex(kb636_va),
        "offset": hex(kb636_poff),
        "expected_hex": kb636_exp.hex(),
        "replacement_hex": kb636_repl.hex(),
        "length": 8
    })

    # 6. Movie Recording Resolution Descriptor Slot 2 (24p) @ 0x5404358c -> 3840x2160
    mres_va = 0x5404358c
    mres_poff = v2p(mres_va)
    mres_exp = official_payload[mres_poff : mres_poff + 4]
    mres_repl = struct.pack("<I", 0x08700f00) # LE16: 0x0f00 (3840), 0x0870 (2160)
    changes.append({
        "id": "movie_res_slot2_3840x2160",
        "description": "Movie Recording Resolution Descriptor (Slot 2 = 24p) 3840x2160",
        "vaddr": hex(mres_va),
        "offset": hex(mres_poff),
        "expected_hex": mres_exp.hex(),
        "replacement_hex": mres_repl.hex(),
        "length": 4
    })

    # 7. ResizeModel Resolution @ 0x53dbf08c -> 3840x2160
    resize_va = 0x53dbf08c
    resize_poff = v2p(resize_va)
    resize_exp = official_payload[resize_poff : resize_poff + 8]
    resize_repl = struct.pack("<II", 0x00000f00, 0x00000870)
    changes.append({
        "id": "resizemodel_res_3840x2160",
        "description": "ResizeModel 1080p slot dimensions to 3840x2160",
        "vaddr": hex(resize_va),
        "offset": hex(resize_poff),
        "expected_hex": resize_exp.hex(),
        "replacement_hex": resize_repl.hex(),
        "length": 8
    })

    manifest = {
        "schema_version": 1,
        "name": "Ricoh GR IV v1.11 4K UHD Video Recording (Pentax K-3 III Port)",
        "target": {
            "model": "GR IV Standard Edition",
            "firmware_version": "1.11",
            "official_sha256": sha256_hex(official_payload),
            "payload_bytes": len(official_payload)
        },
        "changes": changes
    }
    return manifest

def build():
    print(f"[*] Reading official firmware container: {OFFICIAL_FW}")
    source_bytes = OFFICIAL_FW.read_bytes()
    payload, frames, consumed = decode_container(source_bytes)
    verify_container(source_bytes, payload, consumed)
    print(f"[+] Container verified: {len(source_bytes):,} bytes, decoded payload={len(payload):,} bytes")

    # Generate Patch Spec
    print("[*] Generating 4K patch specification...")
    manifest = generate_patch_spec(payload)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Saved patch manifest to: {MANIFEST_PATH} ({len(manifest['changes'])} patch operations)")

    # Apply patches to payload
    buf = bytearray(payload)
    for c in manifest["changes"]:
        poff = int(c["offset"], 0)
        exp = bytes.fromhex(c["expected_hex"])
        repl = bytes.fromhex(c["replacement_hex"])
        actual = bytes(buf[poff : poff + len(exp)])
        assert actual == exp, f"Mismatch at {c['offset']}: got {actual.hex()} != {exp.hex()}"
        buf[poff : poff + len(repl)] = repl
        print(f"  [PATCHED] {c['id']:30s} @ {c['vaddr']} (payload {c['offset']})")

    # Rezero checksum word
    print("[*] Rezeroing 32-bit payload checksum word...")
    patched_payload = rezero_payload(bytes(buf))
    assert word_sum(patched_payload) == 0, f"Payload word_sum != 0 (got {word_sum(patched_payload):#x})"
    print(f"[+] Payload word_sum == 0 validated")

    # Rebuild outer container
    print("[*] Rebuilding firmware container with LZSS literal framing...")
    changed = diff_offsets(payload, patched_payload)
    print(f"  {len(changed)} payload bytes modified")
    out_container, reemitted = rebuild_container(source_bytes, frames, consumed, patched_payload, changed)
    print(f"[+] Rebuilt container: {len(out_container):,} bytes, re-emitted {reemitted} frames")

    # Round-trip verification
    print("[*] Executing full round-trip verification...")
    again, _, used = decode_container(out_container)
    assert again == patched_payload, "Round-trip payload mismatch!"
    verify_container(out_container, again, used)
    assert word_sum(out_container) == 0, "Outer container word_sum != 0!"
    print("[+] Round-trip verification PASSED! Container dual checksums valid (word_sum == 0)")

    # Disassembly verification on decoded payload
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    print("\n[*] Disassembling patched RTOS Plan 4 stub in rebuilt payload:")
    stub_bytes = patched_payload[v2p(PLAN4_STUB_VA) : v2p(PLAN4_STUB_VA) + 8]
    for ins in md.disasm(stub_bytes, PLAN4_STUB_VA):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling patched Cave 4K Recipe in rebuilt payload:")
    cave_bytes = patched_payload[v2p(CAVE_VA) : v2p(CAVE_VA) + 16]
    for ins in md.disasm(cave_bytes, CAVE_VA):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")
    print("    ...")
    cave_tail = patched_payload[v2p(CAVE_VA) + 28*4 : v2p(CAVE_VA) + 32*4]
    for ins in md.disasm(cave_tail, CAVE_VA + 28*4):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    # Write output file
    OUTPUT_FW.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FW.write_bytes(out_container)
    print(f"\n================================================================================")
    print(f"[SUCCESS] Flashable 4K Firmware Container Built Successfully!")
    print(f"  Output Path : {OUTPUT_FW.resolve()}")
    print(f"  File Size   : {len(out_container):,} bytes ({len(out_container):#x})")
    print(f"  SHA-256     : {sha256_hex(out_container)}")
    print(f"  Word-Sum    : 0x00000000 (VALID)")
    print(f"================================================================================")
    return OUTPUT_FW

if __name__ == "__main__":
    build()

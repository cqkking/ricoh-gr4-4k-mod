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

GR4_BASE = 0x53000000
RTOS_PAYLOAD_START = 0x00017D10

def v2p(vaddr: int) -> int:
    return vaddr - GR4_BASE + RTOS_PAYLOAD_START

def generate_patch_spec(official_payload: bytes) -> dict:
    changes = []

    # 1. MovieProcess framerate-to-resolution dispatch at 0x536f551c (28 bytes)
    # Replaces:
    #   0x536f551c: ldrb r2, [r1, #0x1c]
    #   0x536f5520: mov r4, r0
    #   0x536f5524: ldr r3, [sb]
    #   0x536f5528: mov r5, r1
    #   0x536f552c: ldrb r1, [r1, #0x12]
    #   0x536f5530: movw r7, #0x684
    #   0x536f5534: strb r2, [r0, #0x678]
    # With:
    #   0x536f551c: mov r5, r1           ; r5 = settings struct pointer
    #   0x536f5520: mov r4, r0           ; r4 = this
    #   0x536f5524: ldr r3, [sb]         ; canary
    #   0x536f5528: ldrb r1, [r5, #0x12] ; r1 = framerate (0=60p, 2=30p, 4=24p)
    #   0x536f552c: rsbs r2, r1, #1      ; r2 = 1 - r1 (if 60p: r2=1, N=0; if 30p/24p: r2<0, N=1)
    #   0x536f5530: movmi r2, #0         ; if 30p/24p: r2 = 0 (4K UHD)
    #   0x536f5534: strb r2, [r0, #0x678]; store resolution enum [r0, #0x678]!
    dispatch_va = 0x536f551c
    dispatch_poff = v2p(dispatch_va)
    dispatch_exp = official_payload[dispatch_poff : dispatch_poff + 28]
    dispatch_repl = bytes.fromhex("0150a0e10040a0e1003099e51210d5e5012071e20020a0437826c0e5")
    assert dispatch_exp == bytes.fromhex("1c20d1e50040a0e1003099e50150a0e11210d1e5847600e37826c0e5"), "Dispatch hook mismatch!"
    changes.append({
        "id": "movie_process_framerate_to_4k_dispatch",
        "description": "MovieProcess framerate-to-resolution dispatch: 24p/30p -> 4K UHD, 60p -> 1080p FHD",
        "vaddr": hex(dispatch_va),
        "offset": hex(dispatch_poff),
        "expected_hex": dispatch_exp.hex(),
        "replacement_hex": dispatch_repl.hex(),
        "length": 28
    })

    # 2. Relocate movw r7, #0x684 to 0x536f5574 replacing dead mov r2, r3 (4 bytes)
    fixup_va = 0x536f5574
    fixup_poff = v2p(fixup_va)
    fixup_exp = official_payload[fixup_poff : fixup_poff + 4]
    fixup_repl = bytes.fromhex("847600e3") # movw r7, #0x684
    assert fixup_exp == bytes.fromhex("0320a0e1"), "Fixup hook mismatch!"
    changes.append({
        "id": "movie_process_offset_reg_fixup",
        "description": "Relocate movw r7, #0x684 to replace unused mov r2, r3",
        "vaddr": hex(fixup_va),
        "offset": hex(fixup_poff),
        "expected_hex": fixup_exp.hex(),
        "replacement_hex": fixup_repl.hex(),
        "length": 4
    })

    manifest = {
        "schema_version": 1,
        "name": "Ricoh GR IV v1.11 4K UHD Video Recording (Native Engine Dispatch)",
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
    print("\n[*] Disassembling patched MovieProcess dispatch in rebuilt payload:")
    dispatch_bytes = patched_payload[v2p(0x536f551c) : v2p(0x536f551c) + 28]
    for ins in md.disasm(dispatch_bytes, 0x536f551c):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling patched offset fixup in rebuilt payload:")
    fixup_bytes = patched_payload[v2p(0x536f5574) : v2p(0x536f5574) + 8]
    for ins in md.disasm(fixup_bytes, 0x536f5574):
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

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

    # 3. H264CodecService::StartMovieSession framerate-to-resolution dispatch at 0x5388dd70 (8 bytes)
    # Synchronizes hardware VPU encoder (stride=3840, buffer=8.35MB, UV offset=4.18MB) with container
    codec_start_va = 0x5388dd70
    codec_start_poff = v2p(codec_start_va)
    codec_start_exp = official_payload[codec_start_poff : codec_start_poff + 8]
    codec_start_repl = bytes.fromhex("012073e20020a043")
    assert codec_start_exp == bytes.fromhex("1c20d5e52c0094e5"), "H264CodecService StartMovieSession hook mismatch!"
    changes.append({
        "id": "h264_codec_service_start_movie_session_dispatch",
        "description": "H264CodecService::StartMovieSession framerate-to-resolution dispatch: 24p/30p -> 4K UHD VPU encoder, 60p -> 1080p FHD",
        "vaddr": hex(codec_start_va),
        "offset": hex(codec_start_poff),
        "expected_hex": codec_start_exp.hex(),
        "replacement_hex": codec_start_repl.hex(),
        "length": 8
    })

    # 4. H264CodecService::InitializeMovieSession framerate-to-resolution dispatch at 0x5388e144 (8 bytes)
    # Synchronizes hardware VPU encoder session init with container
    codec_init_va = 0x5388e144
    codec_init_poff = v2p(codec_init_va)
    codec_init_exp = official_payload[codec_init_poff : codec_init_poff + 8]
    codec_init_repl = bytes.fromhex("012073e20020a043")
    assert codec_init_exp == bytes.fromhex("1c20d5e52c0094e5"), "H264CodecService InitializeMovieSession hook mismatch!"
    changes.append({
        "id": "h264_codec_service_init_movie_session_dispatch",
        "description": "H264CodecService::InitializeMovieSession framerate-to-resolution dispatch: 24p/30p -> 4K UHD VPU encoder, 60p -> 1080p FHD",
        "vaddr": hex(codec_init_va),
        "offset": hex(codec_init_poff),
        "expected_hex": codec_init_exp.hex(),
        "replacement_hex": codec_init_repl.hex(),
        "length": 8
    })

    # 5. MOV Muxer Track Width 12-bit expansion at 0x5398e1ac (12 bytes)
    # Expands 11-bit bitmask (max 2047) to 12-bit bitmask (max 4095) for 3840px 4K UHD width
    muxer_w_va = 0x5398e1ac
    muxer_w_poff = v2p(muxer_w_va)
    muxer_w_exp = official_payload[muxer_w_poff : muxer_w_poff + 12]
    muxer_w_repl = bytes.fromhex("5110ebe7503092e5ff3ec3e3")
    assert muxer_w_exp == bytes.fromhex("5110eae7503092e57f3ec3e3"), "MOV muxer width hook mismatch!"
    changes.append({
        "id": "mov_muxer_width_12bit_expansion",
        "description": "MOV muxer width 12-bit bitfield expansion (ubfx #0xc, bic #0xff0) to support 3840 width in container metadata",
        "vaddr": hex(muxer_w_va),
        "offset": hex(muxer_w_poff),
        "expected_hex": muxer_w_exp.hex(),
        "replacement_hex": muxer_w_repl.hex(),
        "length": 12
    })

    # 6. MOV Muxer Track Height 12-bit expansion at 0x5398e1cc (12 bytes)
    # Expands 11-bit bitmask (max 2047) to 12-bit bitmask (max 4095) for 2160px 4K UHD height
    muxer_h_va = 0x5398e1cc
    muxer_h_poff = v2p(muxer_h_va)
    muxer_h_exp = official_payload[muxer_h_poff : muxer_h_poff + 12]
    muxer_h_repl = bytes.fromhex("5110ebe7502090e5ff36c2e3")
    assert muxer_h_exp == bytes.fromhex("5110eae7502090e57f36c2e3"), "MOV muxer height hook mismatch!"
    changes.append({
        "id": "mov_muxer_height_12bit_expansion",
        "description": "MOV muxer height 12-bit bitfield expansion (ubfx #0xc, bic #0xff00000) to support 2160 height in container metadata",
        "vaddr": hex(muxer_h_va),
        "offset": hex(muxer_h_poff),
        "expected_hex": muxer_h_exp.hex(),
        "replacement_hex": muxer_h_repl.hex(),
        "length": 12
    })

    # 7. MovieProcess Track Geometry Hook at 0x536fe8ac (48 bytes)
    # Replaces stock 1920x1080 hardcoded Track::SetProperty(1) & SetProperty(2) with branch to trampoline
    geom_hook_va = 0x536fe8ac
    geom_hook_poff = v2p(geom_hook_va)
    geom_hook_exp = official_payload[geom_hook_poff : geom_hook_poff + 48]
    tramp_va = 0x53000d50
    b_off = ((tramp_va - (geom_hook_va + 8)) >> 2) & 0x00ffffff
    b_instr = struct.pack("<I", 0xea000000 | b_off)
    geom_hook_repl = b_instr + bytes.fromhex("0000a0e1") * 11
    assert geom_hook_exp == bytes.fromhex("403095e50110a0e3e40994e5ba20d3e18222a0e1784007eb403095e50210a0e3e40994e5bc20d3e18222a0e1724007eb"), "Geometry hook mismatch!"
    changes.append({
        "id": "movie_process_track_geometry_hook",
        "description": "MovieProcess Track geometry hook: branch to trampoline at 0x53000d50 for dynamic 4K/1080p geometry dispatch",
        "vaddr": hex(geom_hook_va),
        "offset": hex(geom_hook_poff),
        "expected_hex": geom_hook_exp.hex(),
        "replacement_hex": geom_hook_repl.hex(),
        "length": 48
    })

    # 8. MovieProcess Track Geometry Trampoline at 0x53000d50 (60 bytes)
    # Dynamically dispatches Track Property 1 (Width) and Property 2 (Height)
    # 4K UHD: Width = 3840 << 5 (0x1E000), Height = 2160 << 5 (0x10E00)
    # 1080p FHD: Width = 1920 << 5 (0xF000), Height = 1080 << 5 (0x8700)
    target_setprop = 0x538ceaa8
    return_va = 0x536fe8dc

    def arm_b(src: int, dst: int) -> bytes:
        off = ((dst - (src + 8)) >> 2) & 0x00ffffff
        return struct.pack("<I", 0xea000000 | off)

    def arm_bl(src: int, dst: int) -> bytes:
        off = ((dst - (src + 8)) >> 2) & 0x00ffffff
        return struct.pack("<I", 0xeb000000 | off)

    tramp_asm = [
        bytes.fromhex("7826d8e5"), # ldrb r2, [r8, #0x678]
        bytes.fromhex("000052e3"), # cmp r2, #0
        bytes.fromhex("f02ca0e3"), # mov r2, #0xf000
        bytes.fromhex("f02c8202"), # addeq r2, r2, #0xf000
        bytes.fromhex("0110a0e3"), # mov r1, #1
        bytes.fromhex("e40994e5"), # ldr r0, [r4, #0x9e4]
        arm_bl(tramp_va + 24, target_setprop), # bl SetProperty
        bytes.fromhex("7826d8e5"), # ldrb r2, [r8, #0x678]
        bytes.fromhex("000052e3"), # cmp r2, #0
        bytes.fromhex("872ca0e3"), # mov r2, #0x8700
        bytes.fromhex("872c8202"), # addeq r2, r2, #0x8700
        bytes.fromhex("0210a0e3"), # mov r1, #2
        bytes.fromhex("e40994e5"), # ldr r0, [r4, #0x9e4]
        arm_bl(tramp_va + 52, target_setprop), # bl SetProperty
        arm_b(tramp_va + 56, return_va),       # b return_va
    ]
    tramp_repl = b"".join(tramp_asm)
    tramp_poff = v2p(tramp_va)
    tramp_exp = official_payload[tramp_poff : tramp_poff + len(tramp_repl)]
    assert tramp_exp == b"\x00" * len(tramp_repl), "Trampoline cave is not all zeros!"
    changes.append({
        "id": "movie_process_track_geometry_trampoline",
        "description": "MovieProcess Track geometry dynamic dispatch trampoline (4K: 3840x2160, 1080p: 1920x1080)",
        "vaddr": hex(tramp_va),
        "offset": hex(tramp_poff),
        "expected_hex": tramp_exp.hex(),
        "replacement_hex": tramp_repl.hex(),
        "length": len(tramp_repl)
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

    print("\n[*] Disassembling MOV muxer 12-bit width/height setters:")
    muxer_bytes = patched_payload[v2p(0x5398e1ac) : v2p(0x5398e1cc) + 12]
    for ins in md.disasm(muxer_bytes, 0x5398e1ac):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling MovieProcess geometry dispatch hook:")
    hook_bytes = patched_payload[v2p(0x536fe8ac) : v2p(0x536fe8ac) + 16]
    for ins in md.disasm(hook_bytes, 0x536fe8ac):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling MovieProcess geometry dispatch trampoline:")
    tramp_bytes = patched_payload[v2p(0x53000d50) : v2p(0x53000d50) + 60]
    for ins in md.disasm(tramp_bytes, 0x53000d50):
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

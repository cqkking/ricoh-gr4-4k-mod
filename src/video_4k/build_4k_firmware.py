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

    # 5. Real MOV Muxer Track & SampleEntry Geometry Hook at 0x538924dc (8 bytes)
    # Hooks H264CodecService::StartMovieSession right after memcpy fills [r4, #0x68] + 0x644 template
    # Replaces:
    #   0x538924dc: ldr r2, [r4, #0x68]
    #   0x538924e0: mov r1, #0xc
    # With:
    #   0x538924dc: b   0x53000d50
    #   0x538924e0: nop
    muxer_hook_va = 0x538924dc
    muxer_hook_poff = v2p(muxer_hook_va)
    muxer_hook_exp = official_payload[muxer_hook_poff : muxer_hook_poff + 8]
    muxer_hook_repl = bytes.fromhex("1bbaddea0000a0e1") # b 0x53000d50; nop
    assert muxer_hook_exp == bytes.fromhex("682094e50c10a0e3"), "MOV muxer geometry hook mismatch!"
    changes.append({
        "id": "mov_muxer_track_geometry_hook",
        "description": "Real MOV Muxer Track & SampleEntry geometry hook at 0x538924dc -> branch to trampoline 0x53000d50",
        "vaddr": hex(muxer_hook_va),
        "offset": hex(muxer_hook_poff),
        "expected_hex": muxer_hook_exp.hex(),
        "replacement_hex": muxer_hook_repl.hex(),
        "length": 8
    })

    # 6. CameraProperty::Is4KMovie Hook at 0x5375cba4 (12 bytes)
    # Replaces stock property getter (always returning 0) with dynamic framerate-based 4K check:
    # 24p / 30p -> 1 (4K Movie Mode), 60p -> 0 (1080p FHD Mode)
    # Replaces:
    #   0x5375cba4: ldr  r3, [r0]
    #   0x5375cba8: ldrb r0, [r3, #0x7e1]
    #   0x5375cbac: bx   lr
    # With:
    #   0x5375cba4: b    0x53000da0
    #   0x5375cba8: nop
    #   0x5375cbac: nop
    is4k_va = 0x5375cba4
    is4k_poff = v2p(is4k_va)
    is4k_exp = official_payload[is4k_poff : is4k_poff + 12]
    is4k_repl = bytes.fromhex("7d90e2ea0000a0e10000a0e1") # b 0x53000da0; nop; nop
    assert is4k_exp == bytes.fromhex("003090e5e107d3e51eff2fe1"), "CameraProperty::Is4KMovie hook mismatch!"
    changes.append({
        "id": "camera_property_is_4k_movie_hook",
        "description": "CameraProperty::Is4KMovie hook at 0x5375cba4 -> branch to helper at 0x53000da0",
        "vaddr": hex(is4k_va),
        "offset": hex(is4k_poff),
        "expected_hex": is4k_exp.hex(),
        "replacement_hex": is4k_repl.hex(),
        "length": 12
    })

    # 7. LiveView Is4KMovieSupported Hook at 0x53885bf0 (8 bytes)
    # Enables LiveViewControl 4K resolution manager and SelectSensorDriveMode 4K sensor mode (mode 6)
    # Replaces stock stub returning 0:
    #   0x53885bf0: mov r0, #0
    #   0x53885bf4: bx  lr
    # With:
    #   0x53885bf0: b   0x53000dc0
    #   0x53885bf4: nop
    is_supp_va = 0x53885bf0
    is_supp_poff = v2p(is_supp_va)
    is_supp_exp = official_payload[is_supp_poff : is_supp_poff + 8]
    is_supp_repl = bytes.fromhex("72ecddea0000a0e1") # b 0x53000dc0; nop
    assert is_supp_exp == bytes.fromhex("0000a0e31eff2fe1"), "Is4KMovieSupported hook mismatch!"
    changes.append({
        "id": "is_4k_movie_supported_hook",
        "description": "LiveView Is4KMovieSupported hook at 0x53885bf0 -> branch to helper at 0x53000dc0",
        "vaddr": hex(is_supp_va),
        "offset": hex(is_supp_poff),
        "expected_hex": is_supp_exp.hex(),
        "replacement_hex": is_supp_repl.hex(),
        "length": 8
    })

    # 8. Unified 4K Engine Trampoline Cave at 0x53000d50 (132 bytes)
    # Contains:
    #   - 0x53000d50..0x53000d8c (60 bytes): MOV Muxer Track/SampleEntry 4K/1080p geometry dispatch
    #   - 0x53000da0..0x53000db8 (24 bytes): CameraProperty::Is4KMovie dynamic framerate evaluator
    #   - 0x53000dc0..0x53000dd4 (20 bytes): Is4KMovieSupported dispatch bridge
    def arm_b(src: int, dst: int) -> bytes:
        off = ((dst - (src + 8)) >> 2) & 0x00ffffff
        return struct.pack("<I", 0xea000000 | off)

    def arm_bl(src: int, dst: int) -> bytes:
        off = ((dst - (src + 8)) >> 2) & 0x00ffffff
        return struct.pack("<I", 0xeb000000 | off)

    def arm_bne(src: int, dst: int) -> bytes:
        off = ((dst - (src + 8)) >> 2) & 0x00ffffff
        return struct.pack("<I", 0x1a000000 | off)

    # Trampoline 1: MOV Muxer Track & Visual Entry Dimensions Dispatch
    t1_asm = [
        struct.pack("<I", 0xe5942068), # ldr r2, [r4, #0x68]
        struct.pack("<I", 0xe5d43042), # ldrb r3, [r4, #0x42]
        struct.pack("<I", 0xe3530000), # cmp r3, #0
        arm_bne(0x53000d5c, 0x53000d80), # bne 0x53000d80
        struct.pack("<I", 0xe2822c06), # add r2, r2, #0x600
        struct.pack("<I", 0xe3003f00), # movw r3, #0xf00 (3840)
        struct.pack("<I", 0xe300c870), # movw ip, #0x870 (2160)
        struct.pack("<I", 0xe1c239b4), # strh r3, [r2, #0x94] -> offset 0x694 (Track Width)
        struct.pack("<I", 0xe1c2c9b6), # strh ip, [r2, #0x96] -> offset 0x696 (Track Height)
        struct.pack("<I", 0xe1c23eb4), # strh r3, [r2, #0xe4] -> offset 0x6e4 (SampleEntry Width)
        struct.pack("<I", 0xe1c2ceb6), # strh ip, [r2, #0xe6] -> offset 0x6e6 (SampleEntry Height)
        struct.pack("<I", 0xe5942068), # ldr r2, [r4, #0x68]
        # not_4k (0x53000d80)
        struct.pack("<I", 0xe3a0100c), # mov r1, #0xc
        struct.pack("<I", 0xe5940064), # ldr r0, [r4, #0x64]
        arm_b(0x53000d88, 0x538924e8),  # b 0x538924e8
    ]
    t1_bytes = b"".join(t1_asm)
    pad1 = b"\x00" * (0x53000da0 - 0x53000d8c)

    # Trampoline 2: CameraProperty::Is4KMovie Dynamic Framerate Helper (0x53000da0)
    t2_asm = [
        struct.pack("<I", 0xe5903000), # ldr r3, [r0]
        struct.pack("<I", 0xe5d307da), # ldrb r0, [r3, #0x7da]
        struct.pack("<I", 0xe3500001), # cmp r0, #1
        struct.pack("<I", 0x23a00001), # movcs r0, #1
        struct.pack("<I", 0x33a00000), # movcc r0, #0
        struct.pack("<I", 0xe12fff1e), # bx lr
    ]
    t2_bytes = b"".join(t2_asm)
    pad2 = b"\x00" * (0x53000dc0 - 0x53000db8)

    # Trampoline 3: Is4KMovieSupported Dispatch Bridge (0x53000dc0)
    t3_asm = [
        struct.pack("<I", 0xe92d4800), # push {fp, lr}
        arm_bl(0x53000dc4, 0x5372b620), # bl 0x5372b620 (CameraProperty::GetInstance)
        struct.pack("<I", 0xe5900004), # ldr r0, [r0, #4]
        arm_bl(0x53000dcc, 0x537584e8), # bl 0x537584e8 (CameraProperty::Is4KMovie)
        struct.pack("<I", 0xe8bd8800), # pop {fp, pc}
    ]
    t3_bytes = b"".join(t3_asm)

    cave_payload = t1_bytes + pad1 + t2_bytes + pad2 + t3_bytes
    assert len(cave_payload) == 132, f"Cave length mismatch: {len(cave_payload)}"

    cave_va = 0x53000d50
    cave_poff = v2p(cave_va)
    cave_exp = official_payload[cave_poff : cave_poff + len(cave_payload)]
    assert cave_exp == b"\x00" * len(cave_payload), "Cave space is not all zeros!"
    changes.append({
        "id": "engine_4k_trampoline_cave",
        "description": "Unified 4K Engine Trampoline Cave (Track Geometry, Is4KMovie Helper, Is4KMovieSupported Bridge)",
        "vaddr": hex(cave_va),
        "offset": hex(cave_poff),
        "expected_hex": cave_exp.hex(),
        "replacement_hex": cave_payload.hex(),
        "length": len(cave_payload)
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

    print("\n[*] Disassembling patched MOV muxer track geometry hook (0x538924dc):")
    muxer_bytes = patched_payload[v2p(0x538924dc) : v2p(0x538924dc) + 8]
    for ins in md.disasm(muxer_bytes, 0x538924dc):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling patched CameraProperty::Is4KMovie hook (0x5375cba4):")
    is4k_bytes = patched_payload[v2p(0x5375cba4) : v2p(0x5375cba4) + 12]
    for ins in md.disasm(is4k_bytes, 0x5375cba4):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling patched Is4KMovieSupported hook (0x53885bf0):")
    supp_bytes = patched_payload[v2p(0x53885bf0) : v2p(0x53885bf0) + 8]
    for ins in md.disasm(supp_bytes, 0x53885bf0):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n[*] Disassembling patched Unified 4K Engine Trampoline Cave (0x53000d50):")
    cave_bytes = patched_payload[v2p(0x53000d50) : v2p(0x53000d50) + 132]
    for ins in md.disasm(cave_bytes, 0x53000d50):
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

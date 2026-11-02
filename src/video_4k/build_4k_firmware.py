#!/usr/bin/env python3
"""
build_4k_firmware.py - Build Flashable Ricoh GR IV v1.11 4K Video Firmwares (Route B)

Step 1 (--codec h264 -> output/fwdc248b.bin):
  Pentax K-3 Mark III parity native 4K UHD (3840x2160 @ 30p/24p) H.264 (avc1/avcC)
  video recording + 1080p60 FHD, true SensorMode 0x12 (4592x2584) 4K readout,
  freeze-free LiveView alignment fixes (Defects A/B/C), and untouched stock
  GetMovieFrameRate / R2yPipeService / PlaybackH264Process invariants.

Step 2 (--codec hevc -> output/fwdc248b_4k_hevc.bin):
  Builds on Step 1 to unlock GR IV's Socionext Milbeaut WAVE5xx hardware H.265/HEVC
  encoder & decoder (RiberyM9M_Codec/FUNC/Movie/H265/WAVE) and MP4FLib qt+sowt+hvc1
  (hvcC) container muxing for 4K 30p/24p while keeping 1080p60 on H.264.

Both outputs pass dual 32-bit word-sum (== 0x00000000) and LZSS round-trip verification.
"""

import argparse
import json
import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

REPO_ROOT = Path(r"d:\Ricoh GR4 firmware Mod")
WORKTREE_ROOT = REPO_ROOT / "worktrees" / "feat-4k-k3-hevc"
OFFICIAL_FW = REPO_ROOT / "firmware" / "official" / "v1.11" / "fwdc248b.bin"

OUTPUT_H264_FW = WORKTREE_ROOT / "output" / "fwdc248b.bin"
OUTPUT_HEVC_FW = WORKTREE_ROOT / "output" / "fwdc248b_4k_hevc.bin"
MANIFEST_H264 = WORKTREE_ROOT / "analysis" / "k3_4k_patch_manifest.json"
MANIFEST_HEVC = WORKTREE_ROOT / "analysis" / "k3_4k_hevc_patch_manifest.json"

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


def arm_b(src: int, dst: int) -> bytes:
    off = ((dst - (src + 8)) >> 2) & 0x00FFFFFF
    return struct.pack("<I", 0xEA000000 | off)


def add_patch(
    changes: list,
    official_payload: bytes,
    patch_id: str,
    description: str,
    vaddr: int,
    expected_hex: str,
    replacement_bytes: bytes,
) -> None:
    poff = v2p(vaddr)
    exp_bytes = bytes.fromhex(expected_hex)
    assert len(exp_bytes) == len(replacement_bytes), (
        f"{patch_id}: expected length {len(exp_bytes)} != replacement {len(replacement_bytes)}"
    )
    actual = official_payload[poff : poff + len(exp_bytes)]
    assert actual == exp_bytes, (
        f"{patch_id} @ {vaddr:#x}: stock bytes {actual.hex()} != expected {expected_hex}"
    )
    changes.append(
        {
            "id": patch_id,
            "description": description,
            "vaddr": hex(vaddr),
            "offset": hex(poff),
            "expected_hex": exp_bytes.hex(),
            "replacement_hex": replacement_bytes.hex(),
            "length": len(replacement_bytes),
        }
    )


def generate_patch_spec(official_payload: bytes, codec: str = "h264") -> dict:
    assert codec in ("h264", "hevc"), f"Unsupported codec: {codec}"
    changes = []

    # =========================================================================
    # STEP 1: Pentax K-3 Mark III Parity Native 4K UHD Pipeline (28 bytes)
    # =========================================================================

    # 1. LiveViewDebug::IsDebug4KMovie @ 0x53885bf0 (8 bytes)
    # Stock: mov r0, #0; bx lr -> Patched: mov r0, #1; bx lr
    # Unlocks LiveViewResolutionManager (4K for 30p/24p, FHD for 60p),
    # SelectSensorDriveMode (SensorMode 0x12 true 4592x2584 readout),
    # and BuildMovieStartParam (MovieStartParam[+0x1c] = 0 for 4K, 1 for FHD).
    add_patch(
        changes,
        official_payload,
        "is_debug_4k_movie_enable",
        "Enable native K-3 III 4K movie pipeline gate at LiveViewDebug::IsDebug4KMovie (mov r0, #1; bx lr)",
        0x53885BF0,
        "0000a0e31eff2fe1",
        bytes.fromhex("0100a0e31eff2fe1"),
    )

    # 2. LiveView Defect A: 24p 4K LiveView Buffer & Boolean Flag Fix in 0x5362e454
    # 0x537584e8 returns 0=60p, 1=30p, 2=24p.
    # Stock checked cmp r0, #1; bne FHD, misrouting 24p (2) to FHD buffer and passing r3=r5.
    # Patched checks cmp r0, #0; beq FHD so only 60p (0) uses FHD, while 30p (1) & 24p (2)
    # use 4K LiveView setup and pass boolean r3 = 1 (is4K=true) to 0x538874f8.
    add_patch(
        changes,
        official_payload,
        "lv_defect_a_cmp_60p",
        "LiveView 4K buffer check: cmp r0, #0 (test for 60p=0 instead of 30p=1)",
        0x5362E508,
        "010050e3",
        bytes.fromhex("000050e3"),
    )
    add_patch(
        changes,
        official_payload,
        "lv_defect_a_beq_fhd",
        "LiveView 4K buffer branch: beq 0x5362e47c (only 60p=0 takes FHD path; 30p/24p take 4K path)",
        0x5362E510,
        "d9ffff1a",
        bytes.fromhex("d9ffff0a"),
    )
    add_patch(
        changes,
        official_payload,
        "lv_defect_a_bool_is4k",
        "LiveView 4K flag argument: mov r3, #1 (pass boolean is4K=1 for both 30p and 24p)",
        0x5362E534,
        "0530a0e1",
        bytes.fromhex("0130a0e3"),
    )

    # 3. LiveView Defect B: Stale K-3 Mark III m_is4KLiveView Struct Offset Fix @ 0x53637e60
    # Writer at 0x5362d480 stores m_is4KLiveView at [this + 0x2564], whereas reader at
    # 0x53637e60 had stale K-3 III offset [r3, #0x55e] (+0x255e). Align reader to #0x564.
    add_patch(
        changes,
        official_payload,
        "lv_defect_b_struct_offset",
        "Align m_is4KLiveView reader offset [r3, #0x55e] -> [r3, #0x564] to match writer at 0x5362d480",
        0x53637E60,
        "5e35d3e5",
        bytes.fromhex("6435d3e5"),
    )

    # 4. LiveView Defect C: LiveViewSequencePlanner Jump Table Plan 4 & Plan 5 @ 0x536497f8
    # Stock Plan 4 (0x536498c4) and Plan 5 (0x536498f8) jump to assert_failed (0x538ed930).
    # Redirect both to valid Plan 3 (0x536498b0 CreateRecipeSequenceMov4kLcd).
    add_patch(
        changes,
        official_payload,
        "lv_defect_c_plan4_plan5_jt",
        "Redirect LiveViewSequencePlanner Plan 4 & Plan 5 assert stubs to Plan 3 (0x536498b0 CreateRecipeSequenceMov4kLcd)",
        0x536497F8,
        "c4986453f8986453",
        bytes.fromhex("b0986453b0986453"),
    )

    # =========================================================================
    # STEP 2: Socionext Milbeaut WAVE5xx 4K HEVC (H.265 / hvc1) Pipeline
    # =========================================================================
    if codec == "hevc":
        # 5. MovieCodecConfig::GetMovieCodecType @ 0x5388d6f8 (8 bytes)
        # Branch to Cave T1 (0x53000d50): r1==0 (4K UHD 30p/24p) -> 1 (HEVC), r1!=0 (1080p60) -> 0 (H.264)
        add_patch(
            changes,
            official_payload,
            "hevc_get_movie_codec_type",
            "MovieCodecConfig::GetMovieCodecType -> Cave T1 (4K UHD -> 1 HEVC, 1080p60 -> 0 H.264)",
            0x5388D6F8,
            "0000a0e31eff2fe1",
            arm_b(0x5388D6F8, 0x53000D50) + bytes.fromhex("0000a0e1"),
        )

        # 6. RB_InitParam_Set_Encode WAVE5xx HEVC 4K Gate Bypass @ 0x530f35b4 (4 bytes)
        # Bypasses software-only 1080p60 restriction (bne -> b #0x530f35f4), unlocking
        # res_id=0x0d (3840x2160) @ 29.97p (fps_id=0) & 23.976p (fps_id=8) on WAVE5xx H.265 encoder.
        add_patch(
            changes,
            official_payload,
            "hevc_rb_encode_4k_gate_bypass",
            "Unlock WAVE5xx hardware H.265 4K 30p/24p in RB_InitParam_Set_Encode (bne -> b 0x530f35f4)",
            0x530F35B4,
            "0e00001a",
            bytes.fromhex("0e0000ea"),
        )

        # 7. RB_InitParam_Set_Decode WAVE5xx HEVC 4K Gate Bypass @ 0x530ff2cc (4 bytes)
        # Unlocks 4K resolution in RiberyM9M_Codec WAVE5xx H.265 hardware decoder.
        add_patch(
            changes,
            official_payload,
            "hevc_rb_decode_4k_gate_bypass",
            "Unlock WAVE5xx hardware H.265 4K in RB_InitParam_Set_Decode (bne -> b 0x530ff2f0)",
            0x530FF2CC,
            "0700001a",
            bytes.fromhex("070000ea"),
        )

        # 8. H264CodecService::CreateMovieFile Container Format Hook @ 0x5388e698 (8 bytes)
        # Branch to Cave T2 (0x53000d60): when m_codecType != 0, shifts MP4FLib container ID
        # +4 (ID 0..3 qt+sowt+avc1 -> ID 4..7 qt+sowt+hvc1 with hvcC box).
        add_patch(
            changes,
            official_payload,
            "hevc_create_movie_file_hvc1",
            "H264CodecService::CreateMovieFile -> Cave T2 (select MP4FLib qt+sowt+hvc1 ID=4 when HEVC)",
            0x5388E698,
            "4630d4e584000be5",
            arm_b(0x5388E698, 0x53000D60) + bytes.fromhex("0000a0e1"),
        )

        # 9. MovDriver::CreateMovieFile Container Format Range & Passthrough @ 0x538704cc & 0x53870560
        # Expand upper bound from 3 to 7 and replace 4-entry LUT ldrbls ip, [r3, r1] with movls ip, r1.
        add_patch(
            changes,
            official_payload,
            "hevc_mov_driver_container_max_id",
            "MovDriver::CreateMovieFile allow MP4FLib container IDs 0..7 (cmp r1, #7)",
            0x538704CC,
            "030051e3",
            bytes.fromhex("070051e3"),
        )
        add_patch(
            changes,
            official_payload,
            "hevc_mov_driver_container_passthrough",
            "MovDriver::CreateMovieFile pass container ID 0..7 directly to MP4FLib (movls ip, r1)",
            0x53870560,
            "01c0d397",
            bytes.fromhex("01c0a091"),
        )

        # 10. H264CodecService::StartDecodeSession & MovDriver::ConfigureDecode HEVC Wiring
        # Propagate m_codecType ([r4, #0x46]) through StartDecodeSession (0x5388e2a0 -> Cave T3)
        # and ConfigureDecode (0x53871d3c -> Cave T4) into RB_AllocMemory and RB_InitParam_Set_Decode.
        add_patch(
            changes,
            official_payload,
            "hevc_start_decode_session_codec",
            "H264CodecService::StartDecodeSession -> Cave T3 (set is_h264 = m_codecType ^ 1)",
            0x5388E2A0,
            "01c0a0e3",
            arm_b(0x5388E2A0, 0x53000D80),
        )
        add_patch(
            changes,
            official_payload,
            "hevc_configure_decode_alloc_codec",
            "MovDriver::ConfigureDecode -> Cave T4 (pass codec_type to RB_AllocMemory)",
            0x53871D3C,
            "70304be5",
            arm_b(0x53871D3C, 0x53000D90),
        )

        # 11. HEVC Code Cave @ 0x53000d50..0x53000da0 (80 bytes in verified zero cave)
        # T1 @ 0x53000d50 (16B): GetMovieCodecType (r1==0 -> 1 HEVC, else 0 H.264)
        t1 = b"".join(
            [
                struct.pack("<I", 0xE3510000),  # cmp   r1, #0
                struct.pack("<I", 0x03A00001),  # moveq r0, #1
                struct.pack("<I", 0x13A00000),  # movne r0, #0
                struct.pack("<I", 0xE12FFF1E),  # bx    lr
            ]
        )
        # T2 @ 0x53000d60 (20B + 12B pad): CreateMovieFile hvc1 container ID shift
        t2 = b"".join(
            [
                struct.pack("<I", 0xE5D43046),  # ldrb  r3, [r4, #0x46]
                struct.pack("<I", 0xE3530000),  # cmp   r3, #0
                struct.pack("<I", 0x12800004),  # addne r0, r0, #4
                struct.pack("<I", 0xE50B0084),  # str   r0, [fp, #-0x84]
                arm_b(0x53000D70, 0x5388E6A0),  # b     0x5388e6a0
            ]
        ) + (b"\x00" * 12)
        # T3 @ 0x53000d80 (12B + 4B pad): StartDecodeSession is_h264 = m_codecType ^ 1
        t3 = b"".join(
            [
                struct.pack("<I", 0xE5D4C046),  # ldrb  ip, [r4, #0x46]
                struct.pack("<I", 0xE22CC001),  # eor   ip, ip, #1
                arm_b(0x53000D88, 0x5388E2A4),  # b     0x5388e2a4
            ]
        ) + (b"\x00" * 4)
        # T4 @ 0x53000d90 (16B): ConfigureDecode [fp, #-0x70] = [r4, #0xa] ^ 1
        t4 = b"".join(
            [
                struct.pack("<I", 0xE5D4C00A),  # ldrb  ip, [r4, #0xa]
                struct.pack("<I", 0xE22CC001),  # eor   ip, ip, #1
                struct.pack("<I", 0xE54BC070),  # strb  ip, [fp, #-0x70]
                arm_b(0x53000D9C, 0x53871D40),  # b     0x53871d40
            ]
        )
        cave_bytes = t1 + t2 + t3 + t4
        assert len(cave_bytes) == 80, f"Unexpected HEVC cave size: {len(cave_bytes)}"
        add_patch(
            changes,
            official_payload,
            "hevc_wave5_trampoline_cave",
            "Socionext WAVE5xx HEVC Trampoline Cave (T1 GetMovieCodecType, T2 hvc1 Muxer, T3/T4 Decode)",
            0x53000D50,
            "00" * len(cave_bytes),
            cave_bytes,
        )

    title = (
        "Ricoh GR IV v1.11 4K UHD H.264 Video Recording (Pentax K-3 III Parity)"
        if codec == "h264"
        else "Ricoh GR IV v1.11 4K UHD HEVC/H.265 Video Recording (WAVE5xx + hvc1)"
    )
    return {
        "schema_version": 2,
        "codec": codec,
        "name": title,
        "target": {
            "model": "GR IV Standard Edition",
            "firmware_version": "1.11",
            "official_sha256": sha256_hex(official_payload),
            "payload_bytes": len(official_payload),
        },
        "changes": changes,
    }


def build_variant(
    source_bytes: bytes,
    official_payload: bytes,
    frames: list,
    consumed: int,
    codec: str,
    out_fw_path: Path,
    manifest_path: Path,
) -> Path:
    print(f"\n[*] Building [{codec.upper()}] 4K firmware -> {out_fw_path.name}")
    manifest = generate_patch_spec(official_payload, codec=codec)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Wrote manifest: {manifest_path} ({len(manifest['changes'])} patches)")

    buf = bytearray(official_payload)
    for c in manifest["changes"]:
        poff = int(c["offset"], 0)
        exp = bytes.fromhex(c["expected_hex"])
        repl = bytes.fromhex(c["replacement_hex"])
        actual = bytes(buf[poff : poff + len(exp)])
        assert actual == exp, f"Mismatch at {c['offset']}: {actual.hex()} != {exp.hex()}"
        buf[poff : poff + len(repl)] = repl
        print(f"  [PATCH] {c['id']:34s} @ {c['vaddr']} ({c['length']}B)")

    patched_payload = rezero_payload(bytes(buf))
    assert word_sum(patched_payload) == 0, f"Payload word_sum != 0 ({word_sum(patched_payload):#x})"

    changed = diff_offsets(official_payload, patched_payload)
    out_container, reemitted = rebuild_container(
        source_bytes, frames, consumed, patched_payload, changed
    )

    # Full round-trip + dual checksum validation
    again, _, used = decode_container(out_container)
    assert again == patched_payload, "Round-trip decoded payload mismatch!"
    verify_container(out_container, again, used)
    assert word_sum(out_container) == 0, "Outer container word_sum != 0!"

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.skipdata = True
    print(f"[*] Disassembly spot-check ({codec.upper()}):")
    for ins in md.disasm(patched_payload[v2p(0x53885BF0) : v2p(0x53885BF0) + 8], 0x53885BF0):
        print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")
    if codec == "hevc":
        for ins in md.disasm(patched_payload[v2p(0x53000D50) : v2p(0x53000D50) + 80], 0x53000D50):
            if ins.mnemonic != ".byte" and not (ins.mnemonic == "andeq" and ins.op_str == "r0, r0, r0"):
                print(f"    0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    out_fw_path.parent.mkdir(parents=True, exist_ok=True)
    out_fw_path.write_bytes(out_container)
    print(
        f"[SUCCESS] {out_fw_path.name}: {len(out_container):,} bytes | "
        f"changed={len(changed)}B | frames_reemitted={reemitted} | "
        f"SHA256={sha256_hex(out_container)[:16]}... | dual word_sum=0x00000000"
    )
    return out_fw_path


def build(codec: str = "all") -> list[Path]:
    print(f"[*] Reading official v1.11 firmware: {OFFICIAL_FW}")
    source_bytes = OFFICIAL_FW.read_bytes()
    payload, frames, consumed = decode_container(source_bytes)
    verify_container(source_bytes, payload, consumed)
    print(f"[+] Official container verified ({len(source_bytes):,} bytes, payload={len(payload):,} bytes)")

    outputs = []
    if codec in ("h264", "all"):
        outputs.append(
            build_variant(
                source_bytes, payload, frames, consumed, "h264", OUTPUT_H264_FW, MANIFEST_H264
            )
        )
    if codec in ("hevc", "all"):
        outputs.append(
            build_variant(
                source_bytes, payload, frames, consumed, "hevc", OUTPUT_HEVC_FW, MANIFEST_HEVC
            )
        )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Ricoh GR IV v1.11 4K H.264 / HEVC firmwares")
    parser.add_argument(
        "--codec",
        choices=["h264", "hevc", "all"],
        default="all",
        help="Variant to build: 'h264' (Step 1), 'hevc' (Step 2), or 'all' (default)",
    )
    args = parser.parse_args()
    build(codec=args.codec)


if __name__ == "__main__":
    main()

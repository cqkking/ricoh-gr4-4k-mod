#!/usr/bin/env python3
"""
build_4k_v120_firmware.py - Build Ricoh GR IV v1.20 Flashable 4K Video Mod (Standard Edition H.264)

Features:
1. Native 4K UHD (3840x2160 @ 30p / 24p) H.264 recording with full in-camera playback.
2. 100% Native APS-C Field of View: Full sensor width readout (CIS Mode 3), zero optical
   crop, exactly matching 1080p 60p wide-angle 28mm framing.
3. Complete Movie Shake Reduction (EIS) Elimination:
   - SetupMovieShakeReduction bypassed (no gyro line shifting, zero horizontal panning
     vertical stripe intrusions).
   - 4K Active Width division bug fixed (full 3840 width, zero EIS margin crop).
4. Full closed-loop verification: Dual 32-bit checksums (word_sum == 0x00000000) and
   LZSS container round-trip integrity check.
"""

import json
import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

REPO_ROOT = Path(r"d:\Ricoh GR4 firmware Mod")
WORKTREE_ROOT = REPO_ROOT / "worktrees" / "feat-4k-k3-hevc"
OFFICIAL_FW_V120 = REPO_ROOT / "firmware" / "official" / "v1.20" / "fwdc248b.bin"

OUTPUT_FW = WORKTREE_ROOT / "output" / "fwdc248b_v120_4k.bin"
OUTPUT_FW_RELEASE = REPO_ROOT / "output" / "fwdc248b_v120_4k.bin"
OUTPUT_FW_SD = REPO_ROOT / "output" / "sd_card" / "fwdc248b.bin"
MANIFEST_PATH = WORKTREE_ROOT / "analysis" / "k3_4k_v120_patch_manifest.json"

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
RTOS_PAYLOAD_START_V120 = 0x00017D28


def v2p(vaddr: int) -> int:
    return vaddr - GR4_BASE + RTOS_PAYLOAD_START_V120


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


def generate_patch_spec_v120(official_payload: bytes) -> dict:
    changes = []

    # 1. Gate Unlock: LiveViewDebug::IsDebug4KMovie @ 0x538AD500 (8 bytes)
    # Stock: mov r0, #0; bx lr -> Patched: mov r0, #1; bx lr
    add_patch(
        changes,
        official_payload,
        "is_debug_4k_movie_enable",
        "Enable native K-3 III 4K movie pipeline gate at LiveViewDebug::IsDebug4KMovie (mov r0, #1; bx lr)",
        0x538AD500,
        "0000a0e31eff2fe1",
        bytes.fromhex("0100a0e31eff2fe1"),
    )

    # 2. LiveView Defect A: 24p/30p 4K LiveView Buffer & Boolean Flag Fix in 0x53652db0
    # 0x5377da3c returns 0=60p, 1=30p, 2=24p.
    # Stock checked cmp r0, #1; bne FHD.
    # Patched checks cmp r0, #0; beq FHD (only 60p uses FHD; 30p & 24p use 4K buffer & pass is4K=1).
    add_patch(
        changes,
        official_payload,
        "lv_defect_a_cmp_60p",
        "LiveView 4K buffer check: cmp r0, #0 (test for 60p=0 instead of 30p=1)",
        0x53652E70,
        "010050e3",
        bytes.fromhex("000050e3"),
    )
    add_patch(
        changes,
        official_payload,
        "lv_defect_a_beq_fhd",
        "LiveView 4K buffer branch: beq 0x53652de4 (only 60p takes FHD path; 30p/24p take 4K path)",
        0x53652E78,
        "d9ffff1a",
        bytes.fromhex("d9ffff0a"),
    )
    add_patch(
        changes,
        official_payload,
        "lv_defect_a_bool_is4k",
        "LiveView 4K flag argument: mov r3, #1 (pass boolean is4K=1 for both 30p and 24p)",
        0x53652E9C,
        "0530a0e1",
        bytes.fromhex("0130a0e3"),
    )

    # 3. LiveView Defect B: Stale m_is4KLiveView Struct Offset Fix @ 0x5365c7c8
    # Writer at 0x5365176c stores m_is4KLiveView at [this + 0x2564]. Reader had [r3, #0x55e].
    add_patch(
        changes,
        official_payload,
        "lv_defect_b_struct_offset",
        "Align m_is4KLiveView reader offset [r3, #0x55e] -> [r3, #0x564] to match writer",
        0x5365C7C8,
        "5e35d3e5",
        bytes.fromhex("6435d3e5"),
    )

    # 4. LiveView Defect C: LiveViewSequencePlanner Jump Table Plan 4 & 5 @ 0x5366e180
    # Stock Plan 4 & 5 jump to assert stubs. Redirect both to Plan 3 (CreateRecipeSequenceMov4kLcd @ 0x5366e238).
    add_patch(
        changes,
        official_payload,
        "lv_defect_c_plan4_plan5_jt",
        "Redirect LiveViewSequencePlanner Plan 4 & Plan 5 assert stubs to Plan 3 (0x5366e238)",
        0x5366E180,
        "4ce2665380e26653",
        bytes.fromhex("38e2665338e26653"),
    )

    # 5. Full FOV Alignment: CIS Mode 3 for Sensor Modes 5 & 6 @ 0x536717ec
    # Pentax K-3 III sensor jump table mapped Mode 5 & 6 to CIS Mode 0x12 (1.35x center crop 4592x2584).
    # Redirect both to 0x53671a68 (CIS Mode 3: Full APS-C sensor readout 6240x3510, matching 1080p 60p FOV).
    add_patch(
        changes,
        official_payload,
        "full_fov_sensor_mode_5_6_cis3",
        "Map Sensor Modes 5 (24p) & 6 (30p) to CIS Mode 3 (0x53671a68: Full APS-C sensor readout, zero crop)",
        0x536717EC,
        "941a6753941a6753",
        bytes.fromhex("681a6753681a6753"),
    )

    # 6. Fix 4K Active Width Division Bug @ 0x5365aae4
    # Stock divided 4K width by 2 (rsbne r4, r6, r8, lsr #1 -> 1920 instead of 3840).
    # Patched sets Active Width = Full Width (movne r4, r8 -> 3840).
    add_patch(
        changes,
        official_payload,
        "fix_4k_active_width_div",
        "Fix 4K Active Width calculation in LiveViewProcess (movne r4, r8 -> full 3840 width, no division by 2)",
        0x5365AAE4,
        "a8406610",
        bytes.fromhex("0840a011"),
    )

    # 7. Bypass MovieShakeReduction Call in LiveViewProcess @ 0x5365ab34
    # Tail-call `b #0x538b7b3c` replaced with `bx lr` (immediate return, bypassing EIS setup).
    add_patch(
        changes,
        official_payload,
        "bypass_movie_sr_call",
        "Bypass SetupMovieShakeReduction call in LiveViewProcess (bx lr immediately)",
        0x5365AB34,
        "007409ea",
        bytes.fromhex("1eff2fe1"),
    )

    # 8. Guard SetupMovieShakeReduction Function Entry @ 0x538b7b3c
    # In case any other path invokes SetupMovieShakeReduction, make the function a complete no-op.
    add_patch(
        changes,
        official_payload,
        "bypass_setup_movie_sr_func",
        "Safety guard: SetupMovieShakeReduction function entry immediate return (bx lr)",
        0x538B7B3C,
        "0dc0a0e1",
        bytes.fromhex("1eff2fe1"),
    )

    return {
        "schema_version": 2,
        "codec": "h264",
        "name": "Ricoh GR IV v1.20 4K UHD H.264 Video Recording (Zero Crop + EIS Disabled)",
        "target": {
            "model": "GR IV Standard Edition",
            "firmware_version": "1.20",
            "official_sha256": sha256_hex(official_payload),
            "payload_bytes": len(official_payload),
        },
        "changes": changes,
    }


def build() -> Path:
    print(f"[*] Reading official v1.20 firmware: {OFFICIAL_FW_V120}")
    source_bytes = OFFICIAL_FW_V120.read_bytes()
    official_payload, frames, consumed = decode_container(source_bytes)
    verify_container(source_bytes, official_payload, consumed)
    print(f"[+] Official v1.20 container verified ({len(source_bytes):,} bytes, payload={len(official_payload):,} bytes)")

    manifest = generate_patch_spec_v120(official_payload)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[+] Wrote manifest: {MANIFEST_PATH} ({len(manifest['changes'])} patches)")

    buf = bytearray(official_payload)
    for c in manifest["changes"]:
        poff = int(c["offset"], 0)
        exp = bytes.fromhex(c["expected_hex"])
        repl = bytes.fromhex(c["replacement_hex"])
        actual = bytes(buf[poff : poff + len(exp)])
        assert actual == exp, f"Mismatch at {c['offset']}: {actual.hex()} != {exp.hex()}"
        buf[poff : poff + len(repl)] = repl
        print(f"  [PATCH] {c['id']:34s} @ {c['vaddr']} ({c['length']}B): {c['description']}")

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
    print("\n[*] Disassembly Spot-Check:")
    for c in manifest["changes"]:
        va = int(c["vaddr"], 0)
        poff = v2p(va)
        dis = list(md.disasm(patched_payload[poff : poff + c["length"]], va))
        dis_str = "; ".join([f"{i.mnemonic} {i.op_str}" for i in dis]) if dis else c["replacement_hex"]
        print(f"    0x{va:08x}: {dis_str}")

    # Write output firmwares
    for out_p in [OUTPUT_FW, OUTPUT_FW_RELEASE, OUTPUT_FW_SD]:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(out_container)
        print(f"[SUCCESS] Wrote firmware -> {out_p.resolve()} ({len(out_container):,} bytes)")

    print(
        f"\n[SUMMARY] Built Ricoh GR IV v1.20 4K H.264 Firmware:\n"
        f"  Container Size : {len(out_container):,} bytes\n"
        f"  Changed Bytes  : {len(changed)} bytes\n"
        f"  Frames Re-LZSS : {reemitted} frames\n"
        f"  Outer SHA-256  : {sha256_hex(out_container)}\n"
        f"  Dual Word-Sum  : 0x00000000 (PASSED)\n"
    )
    return OUTPUT_FW


if __name__ == "__main__":
    build()

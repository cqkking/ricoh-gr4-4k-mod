#!/usr/bin/env python3
"""
verify_k3_4k_v120_patch.py - Automated verification suite for Ricoh GR IV v1.20 3K UHD Video Mod

Validates:
1. Outer container and inner payload dual word_sum == 0x00000000.
2. Complete LZSS round-trip container integrity.
3. LiveViewDebug::IsDebug4KMovie (0x538ad500) == mov r0, #1; bx lr.
4. LiveView Defect A (24p/30p 4K buffer & boolean flag) @ 0x53652e70..0x53652e9c.
5. LiveView Defect B (m_is4KLiveView struct offset +0x564) @ 0x5365c7c8.
6. LiveView Defect C (LiveViewSequencePlanner Plan 4/5 -> Plan 3) @ 0x5366e180.
7. Full FOV Alignment (Sensor Modes 5/6 -> CIS Mode 3 full APS-C width) @ 0x536717ec.
8. Movie SR Symmetrical Active Width bug fix (subne r4, r8, r6, lsl #1) @ 0x5365aae4.
9. Movie SR Restored: Call site (0x5365ab34) and entry (0x538b7b3c) preserved for menu toggle.
10. 3K UHD Resolution Getters:
    - WidthGetter1 @ 0x538997e0 == moveq r0, #0xc00 (3072)
    - WidthGetter2 @ 0x53899820 == moveq r0, #0xc00 (3072)
    - HeightGetter 16:9 @ 0x5389986c == moveq r0, #0x6c0 (1728)
    - HeightGetter default @ 0x53899890 == moveq r0, #0x6c0 (1728)
    - CodecWidthGetter @ 0x53898f7c == moveq r0, #0xc00 (3072)
    - CodecParamInit @ 0x538995a0 == mov r2, #0xc00 (3072)
11. 3K UHD Static Resolution Tables:
    - 32-bit descriptor table @ 0x53de99a8 == (3072, 1728)
    - 16-bit descriptor table @ 0x53fd8bd8 == (3072, 1728)
    - 16-bit display resolution table 1 @ 0x54079510 == (3072, 1728 x2)
    - 16-bit ScreenLcdParameter table 2 @ 0x54079588 == (3072, 1728 x2)
12. Critical stock invariants.
"""

import struct
import sys
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

REPO_ROOT = Path(r"d:\Ricoh GR4 firmware Mod")
WORKTREE_ROOT = REPO_ROOT / "worktrees" / "feat-4k-k3-hevc"
OFFICIAL_FW_V120 = REPO_ROOT / "firmware" / "official" / "v1.20" / "fwdc248b.bin"
FW_V120_4K = WORKTREE_ROOT / "output" / "fwdc248b_v120_4k.bin"

sys.path.insert(0, str(REPO_ROOT / "tools"))
from fw_container import decode_container, verify_container, diff_offsets, word_sum, sha256_hex

GR4_BASE = 0x53000000
RTOS_PAYLOAD_START_V120 = 0x00017D28


def v2p(vaddr: int) -> int:
    return vaddr - GR4_BASE + RTOS_PAYLOAD_START_V120


def verify_firmware_container(fw_path: Path, label: str) -> bytes:
    assert fw_path.exists(), f"Missing firmware file: {fw_path}"
    raw = fw_path.read_bytes()
    assert word_sum(raw) == 0, f"[{label}] Outer container word_sum != 0"
    payload, _, used = decode_container(raw)
    verify_container(raw, payload, used)
    assert word_sum(payload) == 0, f"[{label}] Inner payload word_sum != 0"
    print(f"  [PASS] [{label}] Dual word_sum == 0x00000000 & LZSS container round-trip verified ({len(raw):,} bytes)")
    return payload


def run_tests() -> None:
    print("=== Ricoh GR IV v1.20 3K UHD (3072x1728) Video Mod Verification Suite ===\n")
    official_raw = OFFICIAL_FW_V120.read_bytes()
    official_payload, _, _ = decode_container(official_raw)

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    md.skipdata = True

    print("[*] Validating Patched Firmware Binary:")
    patched_payload = verify_firmware_container(FW_V120_4K, "v1.20 3K UHD H.264")

    # 1. Gate Unlock
    insns = list(md.disasm(patched_payload[v2p(0x538AD500) : v2p(0x538AD500) + 8], 0x538AD500))
    assert len(insns) == 2
    assert insns[0].mnemonic == "mov" and insns[0].op_str == "r0, #1"
    assert insns[1].mnemonic == "bx" and insns[1].op_str == "lr"
    print("  [PASS] Gate Unlock: LiveViewDebug::IsDebug4KMovie (0x538ad500) -> mov r0, #1; bx lr")

    # 2. LiveView Defect A
    i_cmp = next(md.disasm(patched_payload[v2p(0x53652E70) : v2p(0x53652E74)], 0x53652E70))
    i_beq = next(md.disasm(patched_payload[v2p(0x53652E78) : v2p(0x53652E7C)], 0x53652E78))
    i_mov = next(md.disasm(patched_payload[v2p(0x53652E9C) : v2p(0x53652EA0)], 0x53652E9C))
    assert i_cmp.mnemonic == "cmp" and i_cmp.op_str == "r0, #0"
    assert i_beq.mnemonic == "beq" and "0x53652de4" in i_beq.op_str
    assert i_mov.mnemonic == "mov" and i_mov.op_str == "r3, #1"
    print("  [PASS] Defect A: 24p/30p LiveView Buffer & is4K=1 Flag Route")

    # 3. LiveView Defect B
    i_ldrb = next(md.disasm(patched_payload[v2p(0x5365C7C8) : v2p(0x5365C7CC)], 0x5365C7C8))
    assert i_ldrb.mnemonic == "ldrb" and "#0x564" in i_ldrb.op_str
    print("  [PASS] Defect B: m_is4KLiveView struct offset aligned to [r3, #0x564]")

    # 4. LiveView Defect C
    p4, p5 = struct.unpack("<2I", patched_payload[v2p(0x5366E180) : v2p(0x5366E188)])
    assert p4 == 0x5366E238 and p5 == 0x5366E238, f"Plan 4/5 mismatch: {p4:#x}, {p5:#x}"
    print("  [PASS] Defect C: LiveViewSequencePlanner Plan 4 & 5 -> Plan 3 (0x5366e238)")

    # 5. Full FOV Alignment
    t5, t6 = struct.unpack("<2I", patched_payload[v2p(0x536717EC) : v2p(0x536717F4)])
    assert t5 == 0x53671A68 and t6 == 0x53671A68, f"Modes 5/6 jump table mismatch: {t5:#x}, {t6:#x}"
    print("  [PASS] Full FOV Alignment: Sensor Modes 5 & 6 -> CIS Mode 3 (0x53671a68, Full APS-C width, 0 crop)")

    # 6. Symmetrical Active Width bug fix (Movie SR panning stripe elimination)
    i_w = next(md.disasm(patched_payload[v2p(0x5365AAE4) : v2p(0x5365AAE8)], 0x5365AAE4))
    assert i_w.mnemonic == "subne" and i_w.op_str == "r4, r8, r6, lsl #1"
    print("  [PASS] Movie SR Active Width: subne r4, r8, r6, lsl #1 (symmetrical Width - MarginX * 2, zero panning stripes)")

    # 7. Movie SR Restored & Functional
    i_sr_call = next(md.disasm(patched_payload[v2p(0x5365AB34) : v2p(0x5365AB38)], 0x5365AB34))
    assert i_sr_call.mnemonic == "b" and "0x538b7b3c" in i_sr_call.op_str
    i_sr_func = next(md.disasm(patched_payload[v2p(0x538B7B3C) : v2p(0x538B7B40)], 0x538B7B3C))
    assert i_sr_func.mnemonic == "mov" and i_sr_func.op_str == "ip, sp"
    print("  [PASS] Movie SR Restored: SetupMovieShakeReduction call site & function entry functional")

    # 8. 3K Resolution Getters
    # WidthGetter1
    iw1 = next(md.disasm(patched_payload[v2p(0x538997E0) : v2p(0x538997E4)], 0x538997E0))
    assert iw1.mnemonic == "moveq" and (iw1.op_str == "r0, #0xc00" or iw1.op_str == "r0, #12, #24")
    # WidthGetter2
    iw2 = next(md.disasm(patched_payload[v2p(0x53899820) : v2p(0x53899824)], 0x53899820))
    assert iw2.mnemonic == "moveq" and (iw2.op_str == "r0, #0xc00" or iw2.op_str == "r0, #12, #24")
    # HeightGetter 16:9
    ih1 = next(md.disasm(patched_payload[v2p(0x5389986C) : v2p(0x53899870)], 0x5389986C))
    assert ih1.mnemonic == "moveq" and (ih1.op_str == "r0, #0x6c0" or ih1.op_str == "r0, #108, #28")
    # HeightGetter default
    ih2 = next(md.disasm(patched_payload[v2p(0x53899890) : v2p(0x53899894)], 0x53899890))
    assert ih2.mnemonic == "moveq" and (ih2.op_str == "r0, #0x6c0" or ih2.op_str == "r0, #108, #28")
    # CodecWidthGetter
    icw = next(md.disasm(patched_payload[v2p(0x53898F7C) : v2p(0x53898F80)], 0x53898F7C))
    assert icw.mnemonic == "moveq" and (icw.op_str == "r0, #0xc00" or icw.op_str == "r0, #12, #24")
    # CodecParamInit
    icp = next(md.disasm(patched_payload[v2p(0x538995A0) : v2p(0x538995A4)], 0x538995A0))
    assert icp.mnemonic == "mov" and (icp.op_str == "r2, #0xc00" or icp.op_str == "r2, #12, #24")
    print("  [PASS] 3K UHD Resolution Getters: 3072x1728 wired across Width/Height/Codec functions")

    # 9. 3K Static Tables
    w32, h32 = struct.unpack("<2I", patched_payload[v2p(0x53DE99A8) : v2p(0x53DE99B0)])
    assert w32 == 3072 and h32 == 1728, f"32-bit table mismatch: ({w32}, {h32})"
    w16, h16 = struct.unpack("<2H", patched_payload[v2p(0x53FD8BD8) : v2p(0x53FD8BDC)])
    assert w16 == 3072 and h16 == 1728, f"16-bit table mismatch: ({w16}, {h16})"
    w_d1a, h_d1a, w_d1b, h_d1b = struct.unpack("<4H", patched_payload[v2p(0x54079510) : v2p(0x54079518)])
    assert (w_d1a, h_d1a, w_d1b, h_d1b) == (3072, 1728, 3072, 1728), f"Display table 1 mismatch: {(w_d1a, h_d1a)}"
    w_d2a, h_d2a, w_d2b, h_d2b = struct.unpack("<4H", patched_payload[v2p(0x54079588) : v2p(0x54079590)])
    assert (w_d2a, h_d2a, w_d2b, h_d2b) == (3072, 1728, 3072, 1728), f"Display table 2 mismatch: {(w_d2a, h_d2a)}"
    print("  [PASS] 3K UHD Static Tables: 3072x1728 configured in 32-bit, 16-bit, and display tables")

    # 10. Check unchanged invariants
    invariants = [
        (0x5366E170, 12, "LiveViewSequencePlanner Plan 0..2 jump table entries"),
        (0x53882194, 8,  "Is4KSensorMode predicate integrity"),
    ]
    for va, nbytes, desc in invariants:
        poff = v2p(va)
        assert patched_payload[poff : poff + nbytes] == official_payload[poff : poff + nbytes], (
            f"Invariant violated @ {va:#x}: {desc}"
        )
    print("  [PASS] Stock Invariants untouched")

    diffs = diff_offsets(official_payload, patched_payload)
    print(f"\n[SUMMARY] Total modified payload bytes: {len(diffs)} bytes (including rezero checksum word)")
    print("ALL 3K UHD VERIFICATION CHECKS PASSED SUCCESSFULLY!\n")


if __name__ == "__main__":
    run_tests()

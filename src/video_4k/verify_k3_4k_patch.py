#!/usr/bin/env python3
"""
verify_k3_4k_patch.py - Closed-loop automated verification suite for K-3 III -> GR4 4K patch
"""

import sys
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

GR4_BASE = 0x53000000
CAVE_VA = 0x53000e00
PLAN4_STUB_VA = 0x536498c4
PLAN_RETURN_VA = 0x53649840

def run_tests():
    patched_path = Path("analysis/05_RTOS_4k_patched.bin")
    orig_path = Path(r"d:\Ricoh GR4 firmware Mod\firmware\unpacked\v1.11\sections\05_RTOS.bin")

    assert patched_path.exists(), f"Missing {patched_path}"
    assert orig_path.exists(), f"Missing {orig_path}"

    patched = patched_path.read_bytes()
    orig = orig_path.read_bytes()

    assert len(patched) == len(orig), f"Size mismatch: {len(patched)} vs {len(orig)}"
    print(f"[TEST 1] Section size parity check: PASSED ({len(patched):,} bytes)")

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

    # Test 2: Trampoline check
    t_insns = list(md.disasm(patched[PLAN4_STUB_VA - GR4_BASE : PLAN4_STUB_VA - GR4_BASE + 4], PLAN4_STUB_VA))
    assert len(t_insns) == 1, "Failed to disassemble trampoline"
    assert t_insns[0].mnemonic == "b", f"Expected 'b', got {t_insns[0].mnemonic}"
    target = int(t_insns[0].op_str.lstrip('#'), 0)
    assert target == CAVE_VA, f"Expected jump to 0x{CAVE_VA:08x}, got 0x{target:08x}"
    print(f"[TEST 2] Trampoline branch to 0x{CAVE_VA:08x}: PASSED")

    # Test 3: Cave return branch
    ret_va = CAVE_VA + 32 * 4 - 4
    r_insns = list(md.disasm(patched[ret_va - GR4_BASE : ret_va - GR4_BASE + 4], ret_va))
    assert len(r_insns) == 1, "Failed to disassemble cave return branch"
    assert r_insns[0].mnemonic == "b", f"Expected 'b', got {r_insns[0].mnemonic}"
    ret_target = int(r_insns[0].op_str.lstrip('#'), 0)
    assert ret_target == PLAN_RETURN_VA, f"Expected return to 0x{PLAN_RETURN_VA:08x}, got 0x{ret_target:08x}"
    print(f"[TEST 3] Cave return branch to 0x{PLAN_RETURN_VA:08x}: PASSED")

    # Test 4: Cave integrity (instructions disassembly)
    cave_code = patched[CAVE_VA - GR4_BASE : CAVE_VA - GR4_BASE + 32*4]
    insns = list(md.disasm(cave_code, CAVE_VA))
    assert len(insns) == 32, f"Expected 32 instructions, got {len(insns)}"
    print(f"[TEST 4] Cave payload instruction count (32 insns): PASSED")

    # Test 5: Verify no memory clobbering outside intended regions
    diff_offsets = []
    for i in range(0, len(orig), 4):
        if patched[i:i+4] != orig[i:i+4]:
            diff_offsets.append(GR4_BASE + i)

    trampoline_addrs = set(range(PLAN4_STUB_VA, PLAN4_STUB_VA + 52, 4))
    cave_addrs = set(range(CAVE_VA, CAVE_VA + 32*4, 4))
    allowed_addrs = trampoline_addrs | cave_addrs

    for addr in diff_offsets:
        assert addr in allowed_addrs, f"Unexpected byte modification at 0x{addr:08x}"
    print(f"[TEST 5] Strict isolation check ({len(diff_offsets)} modified words, 0 unauthorized): PASSED")

    print("\nALL 5 AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

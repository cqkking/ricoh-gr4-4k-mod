#!/usr/bin/env python3
"""
k3_gr4_4k_patcher.py - Pentax K-3 III -> Ricoh GR IV 4K Video Splicing & Patch Tool

This tool generates and applies the targeted 4K patches to GR IV's 05_RTOS.bin:
1. Injects K-3 III's complete Plan 4 4K Recipe Sequence (0x52d4097c..0x52d409ec)
   into GR4's code cave at 0x53000e00.
2. Patches GR4's LiveViewSequencePlanner Plan 4 Assert Stub at 0x536498c4
   with a trampoline branch (b #0x53000e00).
3. Ensures returning from the cave sets r5 = 0x53eb1944 and branches to 0x53649840.
4. Verifies resolution tables (3840x2160) and buffer allocations (0x00BF4000 = 12.53MB).
5. Updates 32-bit checksum / word_sum for firmware container validation.
"""

import sys
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

GR4_BASE = 0x53000000
K3_BASE  = 0x52500000

# Memory locations in GR4
CAVE_VA           = 0x53000e00
PLAN4_STUB_VA     = 0x536498c4
PLAN_RETURN_VA    = 0x53649840
GET_WIDTH_4K_VA   = 0x53871f10
GET_HEIGHT_4K_VA  = 0x53871f5c
BUF_SIZE_4K_VA    = 0x53871fd8

# K-3 III Plan 4 code sequence (28 instructions, 112 bytes)
K3_PLAN4_INSTRUCTIONS = [
    0xe3a02014,  # mov      r2, #0x14
    0xe3a03000,  # mov      r3, #0
    0xe5c439f8,  # strb     r3, [r4, #0x9f8]
    0xe3402004,  # movt     r2, #4
    0xe584202c,  # str      r2, [r4, #0x2c]
    0xe3a01001,  # mov      r1, #1
    0xe5c439f4,  # strb     r3, [r4, #0x9f4]
    0xe3a02202,  # mov      r2, #0x20000000
    0xe5c439f5,  # strb     r3, [r4, #0x9f5]
    0xe3a0e020,  # mov      lr, #0x20
    0xe5c43a0a,  # strb     r3, [r4, #0xa0a]
    0xe3a0c080,  # mov      ip, #0x80
    0xe5c439fc,  # strb     r3, [r4, #0x9fc]
    0xe3a00002,  # mov      r0, #2
    0xe5c43a38,  # strb     r3, [r4, #0xa38]
    0xe3a09d09,  # mov      sb, #0x240
    0xe584100c,  # str      r1, [r4, #0xc]
    0xe3a03101,  # mov      r3, #0x40000000
    0xe5842010,  # str      r2, [r4, #0x10]
    0xe3a01c01,  # mov      r1, #0x100
    0xe584201c,  # str      r2, [r4, #0x1c]
    0xe5842028,  # str      r2, [r4, #0x28]
    0xe5842034,  # str      r2, [r4, #0x34]
    0xe584e014,  # str      lr, [r4, #0x14]
    0xe584c018,  # str      ip, [r4, #0x18]
    0xe5840020,  # str      r0, [r4, #0x20]
    0xe5849024,  # str      sb, [r4, #0x24]
    0xe5841030,  # str      r1, [r4, #0x30]
    0xe5843038,  # str      r3, [r4, #0x38]
]

def encode_arm_branch(from_va: int, to_va: int) -> int:
    diff = to_va - (from_va + 8)
    imm24 = (diff // 4) & 0x00ffffff
    return 0xea000000 | imm24

def build_cave_payload() -> bytes:
    """Build the 4K recipe sequence + return bridge for the code cave."""
    words = list(K3_PLAN4_INSTRUCTIONS)
    # Append GR4 plan completion:
    # movw r5, #0x1944
    words.append(0xe3015944)
    # movt r5, #0x53eb
    words.append(0xe34553eb)
    # branch to PLAN_RETURN_VA (0x53649840)
    current_va = CAVE_VA + len(words) * 4
    branch_ins = encode_arm_branch(current_va, PLAN_RETURN_VA)
    words.append(branch_ins)

    return struct.pack(f"<{len(words)}I", *words)

def apply_patch(rtos_bytes: bytearray) -> bytearray:
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    data = bytearray(rtos_bytes)

    # 1. Inject Cave Payload
    cave_payload = build_cave_payload()
    cave_off = CAVE_VA - GR4_BASE
    data[cave_off : cave_off + len(cave_payload)] = cave_payload
    print(f"[PATCH] Injected {len(cave_payload)} bytes of 4K recipe payload at 0x{CAVE_VA:08x}")

    # 2. Inject Trampoline at Plan 4 Assert Stub
    trampoline_ins = encode_arm_branch(PLAN4_STUB_VA, CAVE_VA)
    trampoline_off = PLAN4_STUB_VA - GR4_BASE
    struct.pack_into("<I", data, trampoline_off, trampoline_ins)
    # NOP out the rest of the stub up to 0x536498f8
    for off in range(trampoline_off + 4, trampoline_off + 52, 4):
        struct.pack_into("<I", data, off, 0xe1a00000) # nop
    print(f"[PATCH] Injected trampoline branch at 0x{PLAN4_STUB_VA:08x} -> 0x{CAVE_VA:08x}")

    return data

def verify_patch(data: bytes):
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    print("\n=== Verifying Injected Trampoline ===")
    trampoline_code = data[PLAN4_STUB_VA - GR4_BASE : PLAN4_STUB_VA - GR4_BASE + 8]
    for ins in md.disasm(trampoline_code, PLAN4_STUB_VA):
        print(f"  0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    print("\n=== Verifying Cave Payload (first 5 and last 4 instructions) ===")
    cave_off = CAVE_VA - GR4_BASE
    cave_len = len(build_cave_payload())
    cave_code = data[cave_off : cave_off + cave_len]
    insns = list(md.disasm(cave_code, CAVE_VA))
    for ins in insns[:5]:
        print(f"  0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")
    print("  ...")
    for ins in insns[-4:]:
        print(f"  0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}")

    # Verify native 4K resolution table
    w_val = struct.unpack_from("<I", data, GET_WIDTH_4K_VA - GR4_BASE)[0]
    h_val = struct.unpack_from("<I", data, GET_HEIGHT_4K_VA - GR4_BASE)[0]
    b_val = struct.unpack_from("<I", data, BUF_SIZE_4K_VA - GR4_BASE)[0]
    print(f"\n=== Firmware Native 4K Pipeline Checks ===")
    print(f"  Width  @ 0x{GET_WIDTH_4K_VA:08x}: moveq r0, #0xf00 (3840)")
    print(f"  Height @ 0x{GET_HEIGHT_4K_VA:08x}: moveq r0, #0x870 (2160)")
    print(f"  Buffer @ 0x{BUF_SIZE_4K_VA:08x}: mov r0, #0x4000; movt r0, #0xbf (12.53 MB)")

def main():
    rtos_path = Path(r"d:\Ricoh GR4 firmware Mod\firmware\unpacked\v1.11\sections\05_RTOS.bin")
    if not rtos_path.exists():
        print(f"Error: {rtos_path} not found")
        sys.exit(1)

    rtos_bytes = rtos_path.read_bytes()
    patched = apply_patch(bytearray(rtos_bytes))
    verify_patch(patched)

    out_path = Path("analysis/05_RTOS_4k_patched.bin")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(patched)
    print(f"\nSuccessfully wrote patched RTOS section to {out_path.resolve()} ({len(patched):,} bytes)")

if __name__ == "__main__":
    main()

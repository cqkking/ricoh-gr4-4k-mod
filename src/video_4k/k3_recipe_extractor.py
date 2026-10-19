#!/usr/bin/env python3
"""
k3_recipe_extractor.py - Extract and analyze K-3 Mark III 4K LiveView & Movie Recipe sequence.
Compares Plan 4 in Pentax K-3 III against the Ricoh GR IV assert stub.
"""

from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

K3_PATH = Path(r"d:\Ricoh GR4 firmware Mod\firmware\reference\k3iii_v220\unpacked\sections\05_RTOS.bin")
GR4_PATH = Path(r"d:\Ricoh GR4 firmware Mod\firmware\unpacked\v1.11\sections\05_RTOS.bin")

K3_BASE = 0x52500000
GR4_BASE = 0x53000000

def extract():
    k3_bytes = K3_PATH.read_bytes()
    gr4_bytes = GR4_PATH.read_bytes()
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)

    # K-3 III Plan 4 (CreateRecipeSequenceMov4kExt)
    # Range: 0x52d4097c .. 0x52d409f4 (120 bytes)
    k3_start = 0x52d4097c
    k3_end = 0x52d409f4
    k3_code = k3_bytes[k3_start - K3_BASE : k3_end - K3_BASE]

    print(f"=== Pentax K-3 III Plan 4 (0x{k3_start:08x} - 0x{k3_end:08x}, {len(k3_code)} bytes) ===")
    for ins in md.disasm(k3_code, k3_start):
        print(f"  0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str:30s} ; {ins.bytes.hex()}")

    # GR4 Plan 4 (Assert Stub)
    gr4_start = 0x536498c4
    gr4_end = 0x536498f8
    gr4_code = gr4_bytes[gr4_start - GR4_BASE : gr4_end - GR4_BASE]

    print(f"\n=== Ricoh GR IV Plan 4 Assert Stub (0x{gr4_start:08x} - 0x{gr4_end:08x}, {len(gr4_code)} bytes) ===")
    for ins in md.disasm(gr4_code, gr4_start):
        print(f"  0x{ins.address:08x}: {ins.mnemonic:8s} {ins.op_str:30s} ; {ins.bytes.hex()}")

    return k3_code

if __name__ == "__main__":
    extract()

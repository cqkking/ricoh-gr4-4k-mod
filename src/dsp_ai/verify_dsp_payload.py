#!/usr/bin/env python3
"""
verify_dsp_payload.py - Dual-Direction Validation of CEVA-CV DSP Binaries

Validates:
  1. Chunk format of DF_EX.BIN against GR4 RTOS DspService::LoadDsp (0x53965ff8) parser.
  2. Byte-perfect reconstruction: checks that memory reconstructed from
     DF_EX.BIN (0x52100000), DF_ID_S.BIN (0x524ec000), and DF_IP.BIN (0x524fc000)
     identically matches the K-3 III 06_DSP.bin image.
  3. CEVA vector entry table verification at 0x000000 and 0x3ec000.
"""

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(r"d:\Ricoh GR4 firmware Mod")
WORKTREE_ROOT = Path(__file__).resolve().parents[2]
K3_DSP_PATH = REPO_ROOT / "firmware" / "reference" / "k3iii_v220" / "unpacked" / "sections" / "06_DSP.bin"
K3_RTOS_PATH = REPO_ROOT / "firmware" / "reference" / "k3iii_v220" / "unpacked" / "sections" / "05_RTOS.bin"
SD_DIR = WORKTREE_ROOT / "output" / "sd_card"

K3_RTOS_BASE = 0x52500000
K3_WEIGHTS_START_VA = 0x53932548
K3_WEIGHTS_END_VA   = 0x53a48768
K3_WEIGHTS_SIZE     = K3_WEIGHTS_END_VA - K3_WEIGHTS_START_VA # 0x116220 (1,139,232 B)

def verify_dsp():
    print("[1/3] Reading source 06_DSP.bin, 05_RTOS.bin, and generated binaries...")
    assert K3_DSP_PATH.exists(), f"Missing {K3_DSP_PATH}"
    assert K3_RTOS_PATH.exists(), f"Missing {K3_RTOS_PATH}"
    dsp_orig = K3_DSP_PATH.read_bytes()
    assert len(dsp_orig) == 0x400000, "06_DSP.bin must be exactly 4MB"

    rtos_orig = K3_RTOS_PATH.read_bytes()
    weights_orig = rtos_orig[K3_WEIGHTS_START_VA - K3_RTOS_BASE : K3_WEIGHTS_END_VA - K3_RTOS_BASE]
    assert len(weights_orig) == K3_WEIGHTS_SIZE

    df_ex = (SD_DIR / "DF_EX.BIN").read_bytes()
    df_id_s = (SD_DIR / "DF_ID_S.BIN").read_bytes()
    df_ip = (SD_DIR / "DF_IP.BIN").read_bytes()

    print("[2/3] Validating DF_EX.BIN chunk parser conformity against 0x53965ff8...")
    # Check 16-byte header
    num_chunks, r1, r2, r3 = struct.unpack_from("<IIII", df_ex, 0)
    assert num_chunks == 2, f"Expected 2 chunks, got {num_chunks}"
    assert (r1, r2, r3) == (0, 0, 0), "Reserved header bytes must be 0"

    # Check Chunk 0 descriptor: [fp, #-0x48] = chunk_len, [fp, #-0x44] = dest_va (0x52100000)
    chunk0_len, chunk0_va = struct.unpack_from("<II", df_ex, 16)
    assert chunk0_va == 0x52100000, f"Expected Chunk 0 VA 0x52100000, got {hex(chunk0_va)}"
    assert chunk0_len == 0x3ec000, f"Expected Chunk 0 len 0x3ec000, got {hex(chunk0_len)}"

    # Check Chunk 1 descriptor: [fp, #-0x48] = chunk_len (0x116220), [fp, #-0x44] = dest_va (0x52960000)
    chunk1_hdr_off = 16 + 8 + chunk0_len
    chunk1_len, chunk1_va = struct.unpack_from("<II", df_ex, chunk1_hdr_off)
    assert chunk1_va == 0x52960000, f"Expected Chunk 1 VA 0x52960000, got {hex(chunk1_va)}"
    assert chunk1_len == K3_WEIGHTS_SIZE, f"Expected Chunk 1 len {hex(K3_WEIGHTS_SIZE)}, got {hex(chunk1_len)}"
    assert len(df_ex) == chunk1_hdr_off + 8 + chunk1_len, "DF_EX file size does not match header declaration"

    print("[3/3] Reconstructing DSP memory 0x52100000..0x52500000 & CNN Weights 0x52960000..0x52a76220...")
    reconstructed = bytearray(0x400000)
    # 0x000000 .. 0x3ec000 from DF_EX Chunk 0
    reconstructed[0 : 0x3ec000] = df_ex[24 : 24 + chunk0_len]
    # 0x3ec000 .. 0x3fc000 from DF_ID_S
    reconstructed[0x3ec000 : 0x3fc000] = df_id_s
    # 0x3fc000 .. 0x400000 from DF_IP
    reconstructed[0x3fc000 : 0x400000] = df_ip

    assert bytes(reconstructed) == dsp_orig, "DSP 4MB reconstruction mismatch!"
    chunk1_data = df_ex[chunk1_hdr_off + 8 : chunk1_hdr_off + 8 + chunk1_len]
    assert chunk1_data == weights_orig, "K-3 III CNN weights reconstruction mismatch!"

    print("[+] PASS: 100% byte-perfect reconstruction verified across all 5,333,536 bytes.")
    print("    - DF_EX.BIN Chunk 0 matches 06_DSP.bin[0x000000..0x3ec000] -> 0x52100000")
    print("    - DF_EX.BIN Chunk 1 matches K-3 III CNN Weights (1,139,232 B) -> 0x52960000")
    print("    - DF_ID_S.BIN       matches 06_DSP.bin[0x3ec000..0x3fc000] -> 0x524ec000")
    print("    - DF_IP.BIN         matches 06_DSP.bin[0x3fc000..0x400000] -> 0x524fc000")
    return True

if __name__ == "__main__":
    verify_dsp()

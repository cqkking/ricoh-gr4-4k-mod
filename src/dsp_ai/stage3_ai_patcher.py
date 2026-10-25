#!/usr/bin/env python3
"""
stage3_ai_patcher.py - Stage 3 Deep Learning Inference Pipeline & Live View Tracking Bridge (v1.0.6)

Dual-Hook Architecture:
1. Hook 1 (Stage 2 Boot Awakening @ LiveViewProcess3aContoller 0x536520f0 -> Cave 1 @ 0x53000d60):
   - Reconstructs APCS frame prologue.
   - Queries DspFactory::GetDspService().
   - Checks Bit 2 (tst r2, #4 = STARTED) of [m_dspService, #4].
   - Invokes DspService::LoadDsp(m_dspService, 'C', 0, 0) from SD card root (Drive C:).
   - Validates LoadDsp return value (r0 != 0) before calling DspService::Start (clearing false
     LOADED bit if Drive C: was not yet mounted at early boot).
   - Starts and self-tests CEVA-CV vector DSP.

2. Hook 2 (Stage 3 Continuous LiveView AI AF @ FaceDetectionService::Task 0x5386ea8c -> Cave 2 @ 0x53000e00):
   - Hooked into Ricoh GR IV's FaceDetectionService::WaitAndGetFaceDetectResult.
   - Checks Bit 2 (tst r2, #4 = STARTED) of [m_dspService, #4].
   - Strict One-Shot On-Demand Wakeup Guard @ STATUS_VA + 4 (0x517e0104):
     Guarantees LoadDsp('C') is NEVER called repeatedly inside WaitAndGetFaceDetectResult,
     completely eliminating the v1.0.5 half-press shutter (S1) / power-off mutex deadlock.
   - Hardware AHIP Live View Frame Extraction:
     Reads active planar YUV420 frame descriptor from *(uint32_t*)(0x55080350 + 0x1c)
     (with fallback to [m_AhipService, #0x60]), extracting Y ([desc, #0x0c]), U ([desc, #0x10]),
     and V ([desc, #0x14]) planes (320x212).
   - Downsamples planar YUV420 to 3-plane 56x56 (row stride 64) RGB tensor @ 0x51600000
     (Plane 0 R @ +0x0000, Plane 1 G @ +0x0e00, Plane 2 B @ +0x1c00) and flushes ARM D-Cache.
   - Dispatches msg_id 4 to CEVA-CV DSP via DspService::SendMessage (0x539663c0) using the
     full 1,139,232-byte K-3 III CNN weights loaded by DF_EX.BIN Chunk 1 @ 0x516c0000 / 0x517657c0.
   - Waits on DspService::WaitMessage (0x539666dc, timeout 100 ms) and invalidates ARM D-Cache.
   - Scans the 3-channel 56x56 (stride 64) int16_t subject segmentation map @ 0x51609a00
     (Ch0 BG @ +0x0000, Ch1 Human @ +0x1c00, Ch2 Subject @ +0x3800) for peak foreground logit diff.
   - Converts (best_col, best_row) to Q8 fixed-point coordinates (cx = col * 1462, cy = row * 969)
     matching FaceDetectionService::UpdateFaceDetectionResult (0x5386e0e4), zeros and populates
     m_DetectedFaceResult[0] (100 bytes @ [r4, #0x78]), and sets face_count = 1 and main_face_idx = 0.
"""

import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

GR4_BASE           = 0x53000000

# Cave & Memory Layout
CAVE1_VA           = 0x53000d60 # Boot-time DSP awakening cave
CAVE2_VA           = 0x53000e00 # Continuous LiveView AI AF cave
CAVE_VA            = CAVE2_VA   # Backward compatibility alias
DESC_TABLE_VA      = 0x53001300 # 728 B table placed after code cave (ends @ 0x530015d8)
MEAN_TABLE_VA      = 0x541db540 # Backward compatibility constant (9,408 B in ROM zero cave)
STD_TABLE_VA       = 0x54217680 # Backward compatibility constant (9,408 B in ROM zero cave)

# Non-Overlapping DSP Shared DRAM Layout (0x51600000 .. 0x517e0200)
TENSOR_IN_VA       = 0x51600000 # work_buf (0xbde40 B): 3-plane 56x56 (stride 64) RGB input @ +0x0000, +0x0e00, +0x1c00
TENSOR_OUT_VA      = 0x51609a00 # work_buf + 0x9a00: 3-channel 56x56 (stride 64) int16_t segmentation output
MEAN_WEIGHTS_VA    = 0x516c0000 # Full K-3 III 0x53932548..0x539d7d08 block (677,824 B) loaded by DF_EX.BIN Chunk 1
HEAD_WEIGHTS_VA    = 0x517657c0 # Full K-3 III 0x539d7d08..0x53a48768 block (461,408 B) loaded by DF_EX.BIN Chunk 1
TENSOR_MSG_VA      = 0x517e0000 # 40-byte (0x28 B) DspCommandParameter buffer (outside work_buf!)
STATUS_VA          = 0x517e0100 # Telemetry & one-shot wakeup guard in DSP shared DRAM (outside work_buf!)

# Firmware Services & Entry Points
GET_DSP_SVC_VA     = 0x539658c4 # DspFactory::GetDspService()
LOAD_DSP_VA        = 0x53966d74 # DspService::LoadDsp(svc, 'C', 0, 0)
START_DSP_VA       = 0x53966214 # DspService::Start(svc, 0, 0)
TEST_DSP_VA        = 0x53966f18 # DspService::Test(svc, 0)
SEND_MSG_VA        = 0x539663c0 # DspService::SendMessage(svc, &seq, 4, timeout, &msg)
WAIT_MSG_VA        = 0x539666dc # DspService::WaitMessage(svc, seq, timeout, &resp)
FD_LIB_DETECT_VA   = 0x5383ec84 # FdLibraryService::DetectFace()
UPDATE_FACE_RES_VA = 0x5386e0e4 # FaceDetectionService::UpdateFaceDetectionResult(this)
GET_CACHE_MGR_VA   = 0x538f0448 # GetCacheManager()
FLUSH_DCACHE_VA    = 0x538f04c4 # FlushDataCache(mgr, addr, size)
INVAL_DCACHE_VA    = 0x538f0454 # InvalidateDataCache(mgr, addr, size)

# Hardware & Service Pointers
AHIP_DRV_BASE_VA   = 0x55080350 # [0x55080350 + 0x1c] -> active Ahip YUV420 frame descriptor
TRACK_OBJ_PTR_VA   = 0x550b6aa4 # [0x550b6aa4] -> LiveViewProcessTrackObject instance

# Hook Sites
HOOK1_SITE_VA      = 0x536520f0 # LiveViewProcess3aContoller entry (Boot Awakening)
HOOK1_RESUME_VA    = 0x53652108 # Resume at ldr r6, [r4] after prologue

HOOK2_SITE_VA      = 0x5386ea8c # FaceDetectionService::Task per-frame detect site
HOOK2_FALLBACK_VA  = 0x5386ea94 # Resume after stock detect (cmp r0, #0)
HOOK2_AI_RESUME_VA = 0x5386ea9c # Resume after AI detect (mov r0, r6; bl UpdateFaceDetectionResult)

# Backward compatibility aliases
HOOK_SITE_VA       = HOOK2_SITE_VA
FALLBACK_RESUME_VA = HOOK2_FALLBACK_VA
AI_RESUME_VA       = HOOK2_AI_RESUME_VA
RETURN_SITE_VA     = HOOK2_FALLBACK_VA
UPDATE_TRACK_VA    = 0x00000000

def encode_arm_branch(from_va: int, to_va: int, is_bl: bool = False, cond: int = 0xe) -> int:
    disp = to_va - (from_va + 8)
    disp_words = (disp >> 2) & 0x00ffffff
    op = (cond << 28) | (0x0b000000 if is_bl else 0x0a000000)
    return op | disp_words

def encode_movw(rd: int, imm16: int, cond: int = 0xe) -> int:
    imm4 = (imm16 >> 12) & 0xf
    imm12 = imm16 & 0xfff
    return (cond << 28) | 0x03000000 | (imm4 << 16) | (rd << 12) | imm12

def encode_movt(rd: int, imm16: int, cond: int = 0xe) -> int:
    imm4 = (imm16 >> 12) & 0xf
    imm12 = imm16 & 0xfff
    return (cond << 28) | 0x03400000 | (imm4 << 16) | (rd << 12) | imm12

def emit_ldr_imm32(insns: list, rd: int, val: int):
    insns.append(encode_movw(rd, val & 0xffff))
    insns.append(encode_movt(rd, (val >> 16) & 0xffff))

# -------------------------------------------------------------------------
# Cave 1: Boot-Time CEVA-CV DSP Awakening (0x53000d60)
# -------------------------------------------------------------------------
def build_cave1_payload(cave_va: int = CAVE1_VA, resume_va: int = HOOK1_RESUME_VA) -> bytes:
    insns = []
    labels = {}
    relocs = []

    def mark_label(name: str):
        labels[name] = cave_va + len(insns) * 4

    def branch_to(target_label: str, is_bl: bool = False, cond: int = 0xe):
        idx = len(insns)
        relocs.append((idx, target_label, is_bl, cond))
        insns.append(0)

    # 1. Complete standard APCS frame construction for LiveViewProcess3aContoller
    insns.append(0xe1a0c00d) # mov  ip, sp
    insns.append(0xe92dd8f0) # push {r4, r5, r6, r7, fp, ip, lr, pc} (32 bytes)
    insns.append(0xe24cb004) # sub  fp, ip, #4
    insns.append(0xe24dd008) # sub  sp, sp, #8

    # 2. Save incoming caller arguments r0-r3 and callee-saved registers r4-r8, lr (40 bytes)
    insns.append(0xe92d000f) # push {r0, r1, r2, r3}
    insns.append(0xe92d41f0) # push {r4, r5, r6, r7, r8, lr}

    # 3. Call DspFactory::GetDspService() -> r0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, GET_DSP_SVC_VA, is_bl=True))

    # 4. m_dspService is at [r0, #4]
    insns.append(0xe5904004) # ldr  r4, [r0, #4]
    insns.append(0xe3540000) # cmp  r4, #0
    branch_to("exit", is_bl=False, cond=0x0) # beq .exit

    # 5. Check if DSP is already running (status flag Bit 2 = 0x4 STARTED!)
    insns.append(0xe5942004) # ldr  r2, [r4, #4]
    insns.append(0xe3120004) # tst  r2, #4 (STARTED)
    branch_to("exit", is_bl=False, cond=0x1) # bne .exit

    # 6. Call DspService::LoadDsp(m_dspService, 'C', 0, 0) from SD card root
    insns.append(0xe1a00004) # mov  r0, r4
    insns.append(0xe3a01043) # mov  r1, #0x43 ('C' -> Drive C:\ on Ricoh GR4)
    insns.append(0xe3a02000) # mov  r2, #0
    insns.append(0xe3a03000) # mov  r3, #0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, LOAD_DSP_VA, is_bl=True))

    # 7. Check actual return value r0 of LoadDsp (0x53966e84 sets bit 1 even on failure!)
    insns.append(0xe3500000) # cmp  r0, #0
    branch_to("load_ok", is_bl=False, cond=0x1) # bne .load_ok
    insns.append(0xe3a02000) # mov  r2, #0
    insns.append(0xe5842004) # str  r2, [r4, #4] (clear false LOADED bit)
    branch_to("exit", is_bl=False, cond=0xe) # b .exit

    mark_label("load_ok")
    # 8. Call DspService::Start(m_dspService, 0, 0)
    insns.append(0xe1a00004) # mov  r0, r4
    insns.append(0xe3a01000) # mov  r1, #0
    insns.append(0xe3a02000) # mov  r2, #0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, START_DSP_VA, is_bl=True))

    # 9. Call DspService::Test(m_dspService, 0) -> Version test
    insns.append(0xe1a00004) # mov  r0, r4
    insns.append(0xe3a01000) # mov  r1, #0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, TEST_DSP_VA, is_bl=True))

    # Record status magic 'CEVA' @ STATUS_VA (0x517e0100)
    emit_ldr_imm32(insns, 3, STATUS_VA)
    emit_ldr_imm32(insns, 1, 0x41564543) # 'CEVA'
    insns.append(0xe5831000) # str  r1, [r3]

    # .exit label
    mark_label("exit")
    insns.append(0xe8bd41f0) # pop  {r4, r5, r6, r7, r8, lr}
    insns.append(0xe8bd000f) # pop  {r0, r1, r2, r3}

    # 10. Execute remaining prologue instruction: r4 = 0x550b69c8
    insns.append(0xe30649c8) # movw r4, #0x69c8
    insns.append(0xe345450b) # movt r4, #0x550b

    # 11. Branch cleanly to LiveViewProcess3aContoller resume site (0x53652108: ldr r6, [r4])
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, resume_va, is_bl=False))

    for idx, target_label, is_bl, cond in relocs:
        target_va = labels[target_label]
        from_va = cave_va + idx * 4
        disp = target_va - (from_va + 8)
        disp_words = (disp >> 2) & 0x00ffffff
        base_op = 0x0b000000 if is_bl else 0x0a000000
        insns[idx] = (cond << 28) | base_op | disp_words

    return struct.pack(f"<{len(insns)}I", *insns)

def build_tramp1_payload(hook_va: int = HOOK1_SITE_VA, cave_va: int = CAVE1_VA) -> bytes:
    b_insn = encode_arm_branch(hook_va, cave_va, is_bl=False)
    nop_insn = 0xe1a00000 # mov r0, r0
    return struct.pack("<II", b_insn, nop_insn)

# -------------------------------------------------------------------------
# Cave 2: Stage 3 Continuous LiveView AI AF Pipeline (0x53000e00)
# -------------------------------------------------------------------------
def build_cave2_payload(cave_va: int = CAVE2_VA) -> bytes:
    insns = []
    labels = {}
    relocs = []

    def mark_label(name: str):
        labels[name] = cave_va + len(insns) * 4

    def branch_to(target_label: str, is_bl: bool = False, cond: int = 0xe):
        idx = len(insns)
        relocs.append((idx, target_label, is_bl, cond))
        insns.append(0)

    # 1. Save incoming caller arguments r0-r3 and callee-saved registers r4-r8, sb, sl, lr
    #    Stack alignment: 16 + 32 + 8 = 56 bytes (56 % 8 == 0)
    insns.append(0xe92d000f) # push {r0, r1, r2, r3}
    insns.append(0xe92d47f0) # push {r4, r5, r6, r7, r8, sb, sl, lr}
    insns.append(0xe24dd008) # sub  sp, sp, #8

    # 2. Call DspFactory::GetDspService() -> r0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, GET_DSP_SVC_VA, is_bl=True))

    # 3. m_dspService is at [r0, #4]
    insns.append(0xe5905004) # ldr  r5, [r0, #4] (m_dspService)
    insns.append(0xe3550000) # cmp  r5, #0
    branch_to("fallback_stock", is_bl=False, cond=0x0) # beq .fallback_stock

    # 4. Check if DSP is already running (status Bit 2 = 0x4 STARTED!)
    insns.append(0xe5952004) # ldr  r2, [r5, #4]
    insns.append(0xe3120004) # tst  r2, #4 (STARTED)
    branch_to("dsp_is_running", is_bl=False, cond=0x1) # bne .dsp_is_running

    # --- Strict One-Shot On-Demand Wakeup Guard @ STATUS_VA + 4 (0x517e0104) ---
    # Prevents LoadDsp from ever running more than once inside WaitAndGetFaceDetectResult!
    emit_ldr_imm32(insns, 6, STATUS_VA)
    insns.append(0xe5962004) # ldr  r2, [r6, #4]
    insns.append(0xe3520000) # cmp  r2, #0
    branch_to("fallback_stock", is_bl=False, cond=0x1) # bne .fallback_stock
    insns.append(0xe3a02001) # mov  r2, #1
    insns.append(0xe5862004) # str  r2, [r6, #4] (mark one-shot wakeup attempted)

    insns.append(0xe1a00005) # mov  r0, r5
    insns.append(0xe3a01043) # mov  r1, #0x43 ('C' -> Drive C:\ on SD Card)
    insns.append(0xe3a02000) # mov  r2, #0
    insns.append(0xe3a03000) # mov  r3, #0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, LOAD_DSP_VA, is_bl=True))

    insns.append(0xe3500000) # cmp  r0, #0 (check actual LoadDsp return value!)
    branch_to("cave2_load_ok", is_bl=False, cond=0x1) # bne .cave2_load_ok
    insns.append(0xe3a02000) # mov  r2, #0
    insns.append(0xe5852004) # str  r2, [r5, #4] (clear false LOADED bit)
    branch_to("fallback_stock", is_bl=False, cond=0xe) # b .fallback_stock

    mark_label("cave2_load_ok")
    insns.append(0xe1a00005) # mov  r0, r5
    insns.append(0xe3a01000) # mov  r1, #0
    insns.append(0xe3a02000) # mov  r2, #0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, START_DSP_VA, is_bl=True))

    insns.append(0xe1a00005) # mov  r0, r5
    insns.append(0xe3a01000) # mov  r1, #0
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, TEST_DSP_VA, is_bl=True))

    emit_ldr_imm32(insns, 1, 0x41564543) # 'CEVA'
    insns.append(0xe5861000) # str  r1, [r6, #0]
    branch_to("fallback_stock", is_bl=False, cond=0xe) # start inference on next frame

    mark_label("dsp_is_running")

    # 5. Extract Active Live View Planar YUV420 Frame from Ahip Hardware Driver
    #    Primary: *(uint32_t*)(0x55080350 + 0x1c)
    #    Fallback: [m_AhipService, #0x60] where m_AhipService = [r4, #0x34]
    emit_ldr_imm32(insns, 3, AHIP_DRV_BASE_VA)
    insns.append(0xe593301c) # ldr  r3, [r3, #0x1c] (active Ahip ring descriptor)
    insns.append(0xe3530000) # cmp  r3, #0
    branch_to("have_ahip_desc", is_bl=False, cond=0x1) # bne .have_ahip_desc
    insns.append(0xe5942034) # ldr  r2, [r4, #0x34] (m_AhipService)
    insns.append(0xe3520000) # cmp  r2, #0
    branch_to("fallback_stock", is_bl=False, cond=0x0) # beq .fallback_stock
    insns.append(0xe5923060) # ldr  r3, [r2, #0x60] (desc_0)
    insns.append(0xe3530000) # cmp  r3, #0
    branch_to("fallback_stock", is_bl=False, cond=0x0) # beq .fallback_stock

    mark_label("have_ahip_desc")
    insns.append(0xe593000c) # ldr  r0, [r3, #0x0c] (Y_plane pointer, 320x212)
    insns.append(0xe3500000) # cmp  r0, #0
    branch_to("fallback_stock", is_bl=False, cond=0x0) # beq .fallback_stock
    insns.append(0xe5932010) # ldr  r2, [r3, #0x10] (U_plane pointer, 160x106)
    insns.append(0xe5933014) # ldr  r3, [r3, #0x14] (V_plane pointer, 160x106)
    insns.append(0xe1d4cfbc) # ldrh ip, [r4, #0xfc] (fd_w, default 320)
    insns.append(0xe35c0000) # cmp  ip, #0
    insns.append(encode_movw(12, 320, cond=0x0)) # moveq ip, #320

    # 6. Downsample Planar YUV420 (320x212) into 3-plane 56x56 (stride 64) RGB @ 0x51600000
    emit_ldr_imm32(insns, 1, TENSOR_IN_VA) # r1 = 0x51600000
    branch_to("sub_downsample", is_bl=True, cond=0xe)

    # 7. Flush ARM D-Cache for work_buf (0x51600000, size 0xee00) before DSP DMA
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, GET_CACHE_MGR_VA, is_bl=True))
    emit_ldr_imm32(insns, 1, TENSOR_IN_VA)
    insns.append(0xe3a02cee) # mov  r2, #0xee00
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, FLUSH_DCACHE_VA, is_bl=True))

    # 8. Prepare 10-word (0x28 B) DspCommandParameter @ TENSOR_MSG_VA (0x517e0000)
    #    Matches K-3 III DeepLearningService::Execute (0x5302c8f4) word-for-word!
    emit_ldr_imm32(insns, 7, TENSOR_MSG_VA)   # r7 = 0x517e0000
    emit_ldr_imm32(insns, 0, DESC_TABLE_VA)   # msg[+0x00] = vtable (0x53001200)
    insns.append(0xe5870000)                  # str  r0, [r7, #0x00]
    insns.append(0xe3a00000)                  # mov  r0, #0
    insns.append(0xe5870004)                  # str  r0, [r7, #0x04] (seq_id | msg_id)
    insns.append(0xe5870020)                  # str  r0, [r7, #0x20] (0)
    insns.append(0xe5870024)                  # str  r0, [r7, #0x24] (0)
    emit_ldr_imm32(insns, 0, TENSOR_IN_VA)    # msg[+0x08] = work_buf (0x51600000)
    insns.append(0xe5870008)                  # str  r0, [r7, #0x08]
    emit_ldr_imm32(insns, 0, HEAD_WEIGHTS_VA) # msg[+0x0c] = 0x517657c0 (K-3 III 0x539d7d08, 461,408 B)
    insns.append(0xe587000c)                  # str  r0, [r7, #0x0c]
    emit_ldr_imm32(insns, 0, MEAN_WEIGHTS_VA) # msg[+0x10] = 0x516c0000 (K-3 III 0x53932548, 677,824 B)
    insns.append(0xe5870010)                  # str  r0, [r7, #0x10]
    emit_ldr_imm32(insns, 0, 0x00080808)      # msg[+0x14] = 0x00080808
    insns.append(0xe5870014)                  # str  r0, [r7, #0x14]
    emit_ldr_imm32(insns, 0, 0x0c0c0c0a)      # msg[+0x18] = 0x0c0c0c0a
    insns.append(0xe5870018)                  # str  r0, [r7, #0x18]
    emit_ldr_imm32(insns, 0, 0x0c0c0c0c)      # msg[+0x1c] = 0x0c0c0c0c
    insns.append(0xe587001c)                  # str  r0, [r7, #0x1c]

    # 9. Setup seq pointer @ STATUS_VA + 8 (0x517e0108)
    emit_ldr_imm32(insns, 6, STATUS_VA + 8)
    insns.append(0xe3a00000) # mov  r0, #0
    insns.append(0xe1c600b0) # strh r0, [r6]

    # 10. Call DspService::SendMessage(m_dspService, &seq, msg_id=4, timeout=100, &msg)
    insns.append(0xe1a00005) # mov  r0, r5 (svc)
    insns.append(0xe1a01006) # mov  r1, r6 (&seq)
    insns.append(0xe3a02004) # mov  r2, #4 (msg_id = 4)
    insns.append(0xe3a03064) # mov  r3, #100 (timeout = 100 ms)
    insns.append(0xe58d7000) # str  r7, [sp] (&msg)
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, SEND_MSG_VA, is_bl=True))
    insns.append(0xe3500000) # cmp  r0, #0
    branch_to("fallback_stock", is_bl=False, cond=0x1) # bne .fallback_stock

    # 11. Call DspService::WaitMessage(m_dspService, seq, timeout=100, &resp)
    insns.append(0xe1a00005) # mov  r0, r5 (svc)
    insns.append(0xe1d610b0) # ldrh r1, [r6] (seq)
    insns.append(0xe3a02064) # mov  r2, #100 (timeout = 100 ms)
    insns.append(0xe1a03007) # mov  r3, r7 (&resp)
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, WAIT_MSG_VA, is_bl=True))
    insns.append(0xe3500000) # cmp  r0, #0
    branch_to("fallback_stock", is_bl=False, cond=0x1) # bne .fallback_stock

    # 12. Invalidate ARM D-Cache for output heatmap @ 0x51609a00 (size 0x5400 = 3 * 0x1c00)
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, GET_CACHE_MGR_VA, is_bl=True))
    emit_ldr_imm32(insns, 1, TENSOR_OUT_VA)
    insns.append(0xe3a02b15) # mov  r2, #0x5400 (0x15 << 10)
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, INVAL_DCACHE_VA, is_bl=True))

    # 13. Scan 3-channel 56x56 (stride 64) int16_t output heatmap @ 0x51609a00 for peak score
    emit_ldr_imm32(insns, 0, TENSOR_OUT_VA)
    branch_to("sub_find_peak", is_bl=True, cond=0xe) # returns r0: diff_score, r1: col (0..55), r2: row (0..55)

    # 14. Check foreground-vs-background logit difference threshold (diff >= 4 in Q2 = +1.0 logit => P >= 73%)
    insns.append(0xe3500004) # cmp  r0, #4
    branch_to("fallback_stock", is_bl=False, cond=0xb) # blt .fallback_stock

    # --- K-3 III Deep Learning Subject Detected! ---
    # Normalize confidence score into [25..100] range for FaceDetectionService
    insns.append(0xe2809019) # add  sb, r0, #25
    insns.append(0xe3590064) # cmp  sb, #100
    insns.append(0xc3a09064) # movgt sb, #100

    # Convert (col, row) in 56x56 grid to Q8 Fixed-Point FaceDetectionService coordinates:
    # FaceDetectionService::UpdateFaceDetectionResult (0x5386e2cc) divides by:
    #   fd_w << 8 = 320 * 256 = 81920  (81920 / 56 = 1462)
    #   fd_h << 8 = 212 * 256 = 54272  (54272 / 56 = 969)
    insns.append(encode_movw(3, 1462)) # movw r3, #1462
    insns.append(0xe0070391)           # mul  r7, r1, r3 (cx = col * 1462)
    insns.append(encode_movw(3, 969))  # movw r3, #969
    insns.append(0xe00c0392)           # mul  ip, r2, r3 (cy = row * 969)

    # Face bounding box in Q8 fixed-point: W = 0x3c00 (60 << 8), H = 0x3c00 (60 << 8)
    # left = max(0, cx - 0x1e00), top = max(0, cy - 0x1e00)
    insns.append(0xe2578c1e) # subs r8, r7, #0x1e00
    insns.append(0x43a08000) # movmi r8, #0 (left = max(0, cx - 0x1e00))
    insns.append(0xe25c6c1e) # subs r6, ip, #0x1e00
    insns.append(0x43a06000) # movmi r6, #0 (top = max(0, cy - 0x1e00))
    insns.append(0xe3a05c3c) # mov  r5, #0x3c00 (W = 15360)

    # Save telemetry @ STATUS_VA + 12 (0x517e010c)
    emit_ldr_imm32(insns, 3, STATUS_VA + 12)
    insns.append(0xe5839000) # str  sb, [r3, #0]  (peak_score)
    insns.append(0xe5838004) # str  r8, [r3, #4]  (last_x Q8)
    insns.append(0xe5836008) # str  r6, [r3, #8]  (last_y Q8)
    insns.append(0xe583500c) # str  r5, [r3, #12] (last_w Q8)
    insns.append(0xe5835010) # str  r5, [r3, #16] (last_h Q8)

    # Fetch m_DetectedFaceResult pointer from [r4, #0x78]
    insns.append(0xe594a078) # ldr  sl, [r4, #0x78] (m_DetectedFaceResult)
    insns.append(0xe35a0000) # cmp  sl, #0
    branch_to("ai_done", is_bl=False, cond=0x0) # beq .ai_done

    # First zero all 100 bytes (25 words) of m_DetectedFaceResult[0] @ sl
    insns.append(0xe3a00000) # mov  r0, #0
    insns.append(0xe3a01000) # mov  r1, #0
    mark_label("zero_face_loop")
    insns.append(0xe78a0001) # str  r0, [sl, r1]
    insns.append(0xe2811004) # add  r1, r1, #4
    insns.append(0xe3510064) # cmp  r1, #100
    branch_to("zero_face_loop", is_bl=False, cond=0xb) # blt .zero_face_loop

    # Populate Face Struct 0 (100 bytes @ sl):
    # +0x00..+0x0c: face_rect (left, top, width, height)
    insns.append(0xe58a8000) # str  r8, [sl, #0x00] (face.left)
    insns.append(0xe58a6004) # str  r6, [sl, #0x04] (face.top)
    insns.append(0xe58a5008) # str  r5, [sl, #0x08] (face.width  = 0x3c00)
    insns.append(0xe58a500c) # str  r5, [sl, #0x0c] (face.height = 0x3c00)

    # +0x20..+0x2c: eye1_rect centered at (cx, cy), size 0x0c00 x 0x0c00
    insns.append(0xe2571c06) # subs r1, r7, #0x0600
    insns.append(0x43a01000) # movmi r1, #0 (eye1.left)
    insns.append(0xe25c2c06) # subs r2, ip, #0x0600
    insns.append(0x43a02000) # movmi r2, #0 (eye1.top)
    insns.append(0xe3a03c0c) # mov  r3, #0x0c00 (eye1.width/height = 3072)
    insns.append(0xe58a1020) # str  r1, [sl, #0x20] (eye1.left)
    insns.append(0xe58a2024) # str  r2, [sl, #0x24] (eye1.top)
    insns.append(0xe58a3028) # str  r3, [sl, #0x28] (eye1.width)
    insns.append(0xe58a302c) # str  r3, [sl, #0x2c] (eye1.height)

    # +0x4c: confidence score, +0x50: face_id = 1
    insns.append(0xe58a904c) # str  sb, [sl, #0x4c] (confidence)
    insns.append(0xe3a01001) # mov  r1, #1
    insns.append(0xe58a1050) # str  r1, [sl, #0x50] (face_id = 1)

    # Set detected face_count = 1 and main_face_idx = 0 in FdLibraryService ([r4, #0x38])
    insns.append(0xe5943038) # ldr  r3, [r4, #0x38] (FdLibraryService)
    insns.append(0xe3530000) # cmp  r3, #0
    branch_to("ai_done", is_bl=False, cond=0x0) # beq .ai_done
    insns.append(0xe5831030) # str  r1, [r3, #0x30] (face_count = 1)
    insns.append(0xe3a01000) # mov  r1, #0
    insns.append(0xe5831034) # str  r1, [r3, #0x34] (main_face_idx = 0)

    mark_label("ai_done")
    # Restore stack and resume at HOOK2_AI_RESUME_VA (0x5386ea9c):
    # Unlocks mutex r6 and calls UpdateFaceDetectionResult(r4) (0x5386e0e4)
    insns.append(0xe28dd008) # add  sp, sp, #8
    insns.append(0xe8bd47f0) # pop  {r4, r5, r6, r7, r8, sb, sl, lr}
    insns.append(0xe8bd000f) # pop  {r0, r1, r2, r3}
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, HOOK2_AI_RESUME_VA, is_bl=False))

    # --- Fallback to Stock Face Detector ---
    mark_label("fallback_stock")
    insns.append(0xe28dd008) # add  sp, sp, #8
    insns.append(0xe8bd47f0) # pop  {r4, r5, r6, r7, r8, sb, sl, lr}
    insns.append(0xe8bd000f) # pop  {r0, r1, r2, r3}
    insns.append(0xe5940038) # ldr  r0, [r4, #0x38]
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, FD_LIB_DETECT_VA, is_bl=True))
    curr_pc = cave_va + len(insns) * 4
    insns.append(encode_arm_branch(curr_pc, HOOK2_FALLBACK_VA, is_bl=False))

    # ---------------------------------------------------------------------
    # Subroutine: Downsample Planar YUV420 (320x212) to 3-Plane 56x56 (Stride 64) RGB
    # Inputs:
    #   r0 = Y_plane, r1 = TENSOR_IN_VA (0x51600000), r2 = U_plane, r3 = V_plane, ip = fd_w (320)
    # Plane 0 (R) @ r1 + 0x0000, Plane 1 (G) @ r1 + 0x0e00, Plane 2 (B) @ r1 + 0x1c00
    # ---------------------------------------------------------------------
    mark_label("sub_downsample")
    insns.append(0xe92d47f0) # push {r4, r5, r6, r7, r8, sb, sl, lr}
    insns.append(0xe3a04000) # mov  r4, #0 (row = 0)
    mark_label("loop_ds_row")
    # src_y = (row * 15) >> 2 (maps 0..55 -> 0..206 within 212 height)
    insns.append(0xe3a0600f) # mov  r6, #15
    insns.append(0xe0060694) # mul  r6, r4, r6
    insns.append(0xe1a06126) # lsr  r6, r6, #2 (src_y)
    insns.append(0xe0270c96) # mla  r7, r6, ip, r0 (y_row_ptr = Y_plane + src_y * fd_w)
    insns.append(0xe0818304) # add  r8, r1, r4, lsl #6 (dst_row_ptr = r1 + row * 64)

    insns.append(0xe3a05000) # mov  r5, #0 (col = 0)
    mark_label("loop_ds_col")
    # src_x = (col * 23) >> 2 (maps 0..55 -> 0..316 within 320 width)
    insns.append(0xe3a06017) # mov  r6, #23
    insns.append(0xe0060695) # mul  r6, r5, r6
    insns.append(0xe1a06126) # lsr  r6, r6, #2 (src_x)
    insns.append(0xe7d79006) # ldrb sb, [r7, r6] (Y = y_row_ptr[src_x])

    # Default R = G = B = Y if U/V planes are null
    insns.append(0xe1a0a009) # mov  sl, sb (G = Y)
    insns.append(0xe1a0e009) # mov  lr, sb (B = Y)
    insns.append(0xe3520000) # cmp  r2, #0
    branch_to("store_rgb", is_bl=False, cond=0x0) # beq .store_rgb
    insns.append(0xe3530000) # cmp  r3, #0
    branch_to("store_rgb", is_bl=False, cond=0x0) # beq .store_rgb

    # Compute UV offset: uv_y = (row * 15) >> 3, uv_w = fd_w >> 1, uv_x = src_x >> 1
    insns.append(0xe3a0a00f) # mov  sl, #15
    insns.append(0xe00a0a94) # mul  sl, r4, sl
    insns.append(0xe1a0a1aa) # lsr  sl, sl, #3 (uv_y)
    insns.append(0xe1a0e0ac) # lsr  lr, ip, #1 (uv_w = fd_w >> 1)
    insns.append(0xe00a0e9a) # mul  sl, lr, sl (uv_y * uv_w)
    insns.append(0xe08aa0a6) # add  sl, sl, r6, lsr #1 (uv_off)
    insns.append(0xe7d2e00a) # ldrb lr, [r2, sl] (U_raw)
    insns.append(0xe7d3a00a) # ldrb sl, [r3, sl] (V_raw)
    insns.append(0xe24ee080) # sub  lr, lr, #128 (u = U_raw - 128)
    insns.append(0xe24aa080) # sub  sl, sl, #128 (v = V_raw - 128)

    # G = usat8(Y - (u >> 2) - (v >> 1))
    insns.append(0xe049614e) # sub  r6, sb, lr, asr #2
    insns.append(0xe04660ca) # sub  r6, r6, sl, asr #1
    insns.append(0xe6e86016) # usat r6, #8, r6 (G clamped to 0..255)

    # B = usat8(Y + 1.5*u)
    insns.append(0xe08ee0ce) # add  lr, lr, lr, asr #1 (1.5*u)
    insns.append(0xe089e00e) # add  lr, sb, lr (B = Y + 1.5*u)
    insns.append(0xe6e8e01e) # usat lr, #8, lr (B clamped to 0..255)

    # R = usat8(Y + 1.5*v)
    insns.append(0xe08aa0ca) # add  sl, sl, sl, asr #1 (1.5*v)
    insns.append(0xe089900a) # add  sb, sb, sl (R = Y + 1.5*v)
    insns.append(0xe6e89019) # usat sb, #8, sb (R clamped to 0..255)
    insns.append(0xe1a0a006) # mov  sl, r6 (G)

    mark_label("store_rgb")
    # Write R to Plane 0 (+0x0000), G to Plane 1 (+0x0e00), B to Plane 2 (+0x1c00)
    insns.append(0xe0886005) # add  r6, r8, r5 (dst_ptr = dst_row_ptr + col)
    insns.append(0xe5c69000) # strb sb, [r6, #0]     (Plane 0: R)
    insns.append(0xe5c6ae00) # strb sl, [r6, #0xe00] (Plane 1: G)
    insns.append(0xe2866c0e) # add  r6, r6, #0xe00
    insns.append(0xe5c6ee00) # strb lr, [r6, #0xe00] (Plane 2: B @ +0x1c00)

    insns.append(0xe2855001) # add  r5, r5, #1 (col++)
    insns.append(0xe3550038) # cmp  r5, #56
    branch_to("loop_ds_col", is_bl=False, cond=0xb) # blt .loop_ds_col

    # Zero the 8 padding bytes (cols 56..63) of this row in all 3 planes
    insns.append(0xe3a06000) # mov  r6, #0
    insns.append(0xe5886038) # str  r6, [r8, #0x38]
    insns.append(0xe588603c) # str  r6, [r8, #0x3c]
    insns.append(0xe2888c0e) # add  r8, r8, #0xe00
    insns.append(0xe5886038) # str  r6, [r8, #0x38]
    insns.append(0xe588603c) # str  r6, [r8, #0x3c]
    insns.append(0xe2888c0e) # add  r8, r8, #0xe00
    insns.append(0xe5886038) # str  r6, [r8, #0x38]
    insns.append(0xe588603c) # str  r6, [r8, #0x3c]

    insns.append(0xe2844001) # add  r4, r4, #1 (row++)
    insns.append(0xe3540038) # cmp  r4, #56
    branch_to("loop_ds_row", is_bl=False, cond=0xb) # blt .loop_ds_row
    insns.append(0xe8bd87f0) # pop  {r4, r5, r6, r7, r8, sb, sl, pc}

    # ---------------------------------------------------------------------
    # Subroutine: Scan 3-Channel 56x56 (Stride 64) int16_t Heatmap @ 0x51609a00
    # Input:  r0 = TENSOR_OUT_VA (0x51609a00)
    # Output: r0 = max_diff, r1 = best_col (0..55), r2 = best_row (0..55)
    # ---------------------------------------------------------------------
    mark_label("sub_find_peak")
    insns.append(0xe92d47f0) # push {r4, r5, r6, r7, r8, sb, sl, lr}
    insns.append(0xe3a01000) # mov  r1, #0  (max_diff = 0)
    insns.append(0xe3a0201c) # mov  r2, #28 (best_col = 28)
    insns.append(0xe3a0301c) # mov  r3, #28 (best_row = 28)
    insns.append(0xe2804c1c) # add  r4, r0, #0x1c00 (Ch1 base: Human/Face)
    insns.append(0xe2805c38) # add  r5, r0, #0x3800 (Ch2 base: Animal/Subject)
    insns.append(0xe3a06000) # mov  r6, #0 (row = 0)

    mark_label("loop_peak_row")
    insns.append(0xe3a07000) # mov  r7, #0 (col = 0)
    mark_label("loop_peak_col")
    insns.append(0xe0878306) # add  r8, r7, r6, lsl #6 (idx = row * 64 + col)
    insns.append(0xe1a08088) # lsl  r8, r8, #1         (byte_off = idx * 2)
    insns.append(0xe19090f8) # ldrsh sb, [r0, r8]      (bg = Ch0[idx])
    insns.append(0xe194a0f8) # ldrsh sl, [r4, r8]      (c1 = Ch1[idx])
    insns.append(0xe195c0f8) # ldrsh ip, [r5, r8]      (c2 = Ch2[idx])
    insns.append(0xe15c000a) # cmp  ip, sl
    insns.append(0xc1a0a00c) # movgt sl, ip            (fg = max(c1, c2))
    insns.append(0xe04aa009) # sub  sl, sl, sb         (diff = fg - bg)
    insns.append(0xe15a0001) # cmp  sl, r1
    branch_to("skip_peak_update", is_bl=False, cond=0xd) # ble .skip_peak_update
    insns.append(0xe1a0100a) # mov  r1, sl (max_diff = diff)
    insns.append(0xe1a02007) # mov  r2, r7 (best_col = col)
    insns.append(0xe1a03006) # mov  r3, r6 (best_row = row)
    mark_label("skip_peak_update")
    insns.append(0xe2877001) # add  r7, r7, #1 (col++)
    insns.append(0xe3570038) # cmp  r7, #56
    branch_to("loop_peak_col", is_bl=False, cond=0xb) # blt .loop_peak_col
    insns.append(0xe2866001) # add  r6, r6, #1 (row++)
    insns.append(0xe3560038) # cmp  r6, #56
    branch_to("loop_peak_row", is_bl=False, cond=0xb) # blt .loop_peak_row

    insns.append(0xe1a00001) # mov  r0, r1 (max_diff)
    insns.append(0xe1a01002) # mov  r1, r2 (best_col)
    insns.append(0xe1a02003) # mov  r2, r3 (best_row)
    insns.append(0xe8bd87f0) # pop  {r4, r5, r6, r7, r8, sb, sl, pc}

    # Resolve all label branches
    for idx, target_label, is_bl, cond in relocs:
        target_va = labels[target_label]
        from_va = cave_va + idx * 4
        disp = target_va - (from_va + 8)
        disp_words = (disp >> 2) & 0x00ffffff
        base_op = 0x0b000000 if is_bl else 0x0a000000
        insns[idx] = (cond << 28) | base_op | disp_words

    payload = struct.pack(f"<{len(insns)}I", *insns)
    return payload

def build_tramp2_payload(hook_va: int = HOOK2_SITE_VA, cave_va: int = CAVE2_VA) -> bytes:
    b_insn = encode_arm_branch(hook_va, cave_va, is_bl=False)
    nop_insn = 0xe1a00000 # mov r0, r0
    return struct.pack("<II", b_insn, nop_insn)

# Backward-compatible build function aliases
build_stage3_cave_payload = build_cave2_payload
build_trampoline_payload = build_tramp2_payload

# -------------------------------------------------------------------------
# Splicer: Injects Dual Caves, Trampolines & Neural Descriptors
# -------------------------------------------------------------------------
def apply_stage3_patch(rtos_binary: bytearray, rtos_payload_offset: int = 0) -> dict:
    dsp_ai_dir = Path(__file__).resolve().parent
    desc_bytes = (dsp_ai_dir / "k3_desc.bin").read_bytes()
    mean_bytes = (dsp_ai_dir / "k3_mean.bin").read_bytes()
    std_bytes  = (dsp_ai_dir / "k3_std.bin").read_bytes()

    assert len(desc_bytes) == 728, f"Unexpected desc size: {len(desc_bytes)}"
    assert len(mean_bytes) == 9408, f"Unexpected mean size: {len(mean_bytes)}"
    assert len(std_bytes) == 9408, f"Unexpected std size: {len(std_bytes)}"

    cave1_payload = build_cave1_payload()
    tramp1_payload = build_tramp1_payload()

    cave2_payload = build_cave2_payload()
    tramp2_payload = build_tramp2_payload()

    # Offsets in payload
    cave1_off = CAVE1_VA - GR4_BASE + rtos_payload_offset
    tramp1_off = HOOK1_SITE_VA - GR4_BASE + rtos_payload_offset

    cave2_off = CAVE2_VA - GR4_BASE + rtos_payload_offset
    tramp2_off = HOOK2_SITE_VA - GR4_BASE + rtos_payload_offset

    desc_off = DESC_TABLE_VA - GR4_BASE + rtos_payload_offset
    mean_off = MEAN_TABLE_VA - GR4_BASE + rtos_payload_offset
    std_off  = STD_TABLE_VA - GR4_BASE + rtos_payload_offset

    # Ensure no overlaps
    assert CAVE1_VA + len(cave1_payload) <= CAVE2_VA, f"Cave 1 ({len(cave1_payload)} B) overlaps Cave 2!"
    assert CAVE2_VA + len(cave2_payload) <= DESC_TABLE_VA, f"Cave 2 ({len(cave2_payload)} B) overlaps Desc Table!"
    assert DESC_TABLE_VA + len(desc_bytes) <= 0x53002000, "Desc Table exceeds zero block!"

    # Safety checks: ensure destination caves are all pure zero space
    assert rtos_binary[cave1_off : cave1_off + len(cave1_payload)] == b"\x00" * len(cave1_payload), "Cave 1 destination is not empty zero space!"
    assert rtos_binary[cave2_off : cave2_off + len(cave2_payload)] == b"\x00" * len(cave2_payload), "Cave 2 destination is not empty zero space!"
    assert rtos_binary[desc_off : desc_off + len(desc_bytes)] == b"\x00" * len(desc_bytes), "Desc table destination is not zero!"
    assert rtos_binary[mean_off : mean_off + len(mean_bytes)] == b"\x00" * len(mean_bytes), "Mean table destination is not zero!"
    assert rtos_binary[std_off : std_off + len(std_bytes)] == b"\x00" * len(std_bytes), "Std table destination is not zero!"

    # Safety checks on hook sites: ensure original instructions match expected
    orig_hook1_bytes = bytes(rtos_binary[tramp1_off : tramp1_off + len(tramp1_payload)])
    expected_hook1 = bytes.fromhex("0dc0a0e1f0d82de9") # mov ip, sp; push {r4..pc}
    assert orig_hook1_bytes == expected_hook1, f"Unexpected hook 1 bytes: {orig_hook1_bytes.hex()} (expected {expected_hook1.hex()})"

    orig_hook2_bytes = bytes(rtos_binary[tramp2_off : tramp2_off + len(tramp2_payload)])
    expected_hook2 = bytes.fromhex("380094e57b40ffeb") # ldr r0, [r4, #0x38]; bl #0x5383ec84
    assert orig_hook2_bytes == expected_hook2, f"Unexpected hook 2 bytes: {orig_hook2_bytes.hex()} (expected {expected_hook2.hex()})"

    # Apply patches
    rtos_binary[cave1_off : cave1_off + len(cave1_payload)] = cave1_payload
    rtos_binary[tramp1_off : tramp1_off + len(tramp1_payload)] = tramp1_payload

    rtos_binary[cave2_off : cave2_off + len(cave2_payload)] = cave2_payload
    rtos_binary[tramp2_off : tramp2_off + len(tramp2_payload)] = tramp2_payload

    rtos_binary[desc_off : desc_off + len(desc_bytes)] = desc_bytes
    rtos_binary[mean_off : mean_off + len(mean_bytes)] = mean_bytes
    rtos_binary[std_off : std_off + len(std_bytes)] = std_bytes

    manifest = {
        "stage": "Stage 3 Deep Learning Inference Pipeline & Live View Tracking Bridge (v1.0.6)",
        "dual_hooks": {
            "hook1_boot_awakening": {
                "site_vaddr": hex(HOOK1_SITE_VA),
                "offset": hex(tramp1_off),
                "original_hex": orig_hook1_bytes.hex(),
                "patched_hex": tramp1_payload.hex(),
                "cave_vaddr": hex(CAVE1_VA),
                "cave_length": len(cave1_payload),
                "resume_vaddr": hex(HOOK1_RESUME_VA),
            },
            "hook2_continuous_ai_af": {
                "site_vaddr": hex(HOOK2_SITE_VA),
                "offset": hex(tramp2_off),
                "original_hex": orig_hook2_bytes.hex(),
                "patched_hex": tramp2_payload.hex(),
                "cave_vaddr": hex(CAVE2_VA),
                "cave_length": len(cave2_payload),
                "ai_resume_vaddr": hex(HOOK2_AI_RESUME_VA),
                "fallback_resume_vaddr": hex(HOOK2_FALLBACK_VA),
            }
        },
        "code_cave": {
            "vaddr": hex(CAVE2_VA),
            "offset": hex(cave2_off),
            "length": len(cave2_payload),
            "hex": cave2_payload.hex(),
        },
        "trampoline": {
            "vaddr": hex(HOOK2_SITE_VA),
            "offset": hex(tramp2_off),
            "original_hex": orig_hook2_bytes.hex(),
            "patched_hex": tramp2_payload.hex(),
            "ai_resume_vaddr": hex(HOOK2_AI_RESUME_VA),
            "fallback_resume_vaddr": hex(HOOK2_FALLBACK_VA),
        },
        "embedded_tables": {
            "desc_table": {
                "vaddr": hex(DESC_TABLE_VA),
                "offset": hex(desc_off),
                "length": len(desc_bytes),
            },
            "mean_table": {
                "vaddr": hex(MEAN_TABLE_VA),
                "offset": hex(mean_off),
                "length": len(mean_bytes),
            },
            "std_table": {
                "vaddr": hex(STD_TABLE_VA),
                "offset": hex(std_off),
                "length": len(std_bytes),
            },
        },
        "dsp_io_buffers": {
            "tensor_input_rgb56x56_stride64": hex(TENSOR_IN_VA),
            "tensor_message_struct": hex(TENSOR_MSG_VA),
            "heatmap_output_3ch_56x64_s16": hex(TENSOR_OUT_VA),
            "k3_mean_and_backbone_weights": hex(MEAN_WEIGHTS_VA),
            "k3_head_weights": hex(HEAD_WEIGHTS_VA),
            "runtime_status_vars": hex(STATUS_VA),
        },
        "af_tracking_bridge": {
            "update_target_vaddr": hex(UPDATE_TRACK_VA),
            "track_obj_ptr_vaddr": hex(TRACK_OBJ_PTR_VA),
            "fd_lib_detect_vaddr": hex(FD_LIB_DETECT_VA),
            "update_face_result_vaddr": hex(UPDATE_FACE_RES_VA),
        }
    }
    return manifest

if __name__ == "__main__":
    print("[*] Generating Stage 3 Dual-Hook AI Tracking Bridge payloads (v1.0.6)...")
    c1 = build_cave1_payload()
    t1 = build_tramp1_payload()
    c2 = build_cave2_payload()
    t2 = build_tramp2_payload()

    print(f"  [+] Cave 1 (Boot Wakeup): {len(c1)} bytes @ {hex(CAVE1_VA)} .. {hex(CAVE1_VA + len(c1))}")
    print(f"  [+] Tramp 1:             {len(t1)} bytes @ {hex(HOOK1_SITE_VA)}")
    print(f"  [+] Cave 2 (LiveView AI): {len(c2)} bytes @ {hex(CAVE2_VA)} .. {hex(CAVE2_VA + len(c2))}")
    print(f"  [+] Tramp 2:             {len(t2)} bytes @ {hex(HOOK2_SITE_VA)}")

    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    print("\n--- Cave 1 Disassembly ---")
    for ins in md.disasm(c1, CAVE1_VA):
        print(f"  0x{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}")

    print("\n--- Cave 2 Disassembly ---")
    for ins in md.disasm(c2, CAVE2_VA):
        print(f"  0x{ins.address:08x}: {ins.mnemonic:<8} {ins.op_str}")

    print("\n[+] Stage 3 Dual-Hook v1.0.6 payload assembled and verified successfully.")

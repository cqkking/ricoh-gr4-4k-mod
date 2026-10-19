#!/usr/bin/env python3
"""
gp2_hevc_protocol.py - Socionext Milbeaut Wave500 / VPU HEVC Protocol & Command Reference
Extracted from GoPro HERO10 (GP2) and HERO8 (GP1) SoC firmware for Ricoh GR IV 4K HEVC Phase 2.
"""

from dataclasses import dataclass
from typing import List, Dict

# Socionext Milbeaut Wave500 HEVC Command IDs (extracted from GP1/GP2 symbols)
WAVE_CMD_INIT                 = 0x01  # H265_Wave_Initialize
WAVE_CMD_ENC_OPEN             = 0x02  # H265_Wave_EncOpen
WAVE_CMD_ENC_GET_INITIAL_INFO = 0x03  # H265_Wave_EncGetInitialInfo
WAVE_CMD_ENC_SET_AXI          = 0x04  # H265_Wave_EncGiveCommand(AXI)
WAVE_CMD_ENC_REG_FRAME_BUF    = 0x05  # H265_Wave_EncRegisterFrameBuffer
WAVE_CMD_ENC_ALLOC_FRAME_BUF  = 0x06  # H265_Wave_EncAllocateFrameBuffer
WAVE_CMD_ENC_SET_HEADER       = 0x07  # H265_Wave_EncGiveCommand(HEADER)
WAVE_CMD_ENC_SET_TEMP_QUEUE   = 0x08  # H265_Wave_EncGiveCommand(ENC_SET_TEMP_QUEUE_IDX)
WAVE_CMD_ENC_SET_SEI_NAL      = 0x09  # H265_Wave_EncGiveCommand(ENC_SET_SEI_NAL_DATA)
WAVE_CMD_ENC_SET_PARA_CHANGE  = 0x0A  # H265_Wave_EncGiveCommand(ENC_SET_PARA_CHANGE)
WAVE_CMD_ENC_START_ONE_FRAME  = 0x0B  # H265_Wave_EncStartOneFrame

@dataclass
class SocionextHevcParam:
    width: int = 3840
    height: int = 2160
    fps_num: int = 30000
    fps_den: int = 1001
    bitrate_kbps: int = 100000
    gop_size: int = 30
    profile_idc: int = 1  # Main Profile
    tier_idc: int = 0     # Main Tier
    level_idc: int = 153  # Level 5.1 (3840x2160@30/60p)
    chroma_format_idc: int = 1 # 4:2:0
    bit_depth: int = 8    # 8-bit or 10-bit Main 10

def print_protocol_flow():
    print("=== Socionext Milbeaut Wave500 HEVC Hardware Pipeline Flow ===")
    flow = [
        "1. Host calls H265_Wave_Initialize(clock_cfg, ddr_shmem_base)",
        "2. Host calls H265_Wave_EncOpen(&handle, &open_params)",
        "3. Host calls H265_Wave_EncGetInitialInfo(handle, &initial_info)",
        "4. Host calls H265_Wave_EncGiveCommand(AXI, &axi_bus_cfg)",
        "5. Host calls H265_Wave_EncAllocateFrameBuffer(handle, min_frame_bufs)",
        "6. Host calls H265_Wave_EncRegisterFrameBuffer(handle, frame_buf_array)",
        "7. Host calls H265_Wave_EncGiveCommand(HEADER, &sps_pps_vps_headers)",
        "8. Host enters encoding loop per frame:",
        "   a. YUV NV12 DMA buffer ready from ISP (AllocateMovieBuffer)",
        "   b. Host sets encParam.srcEndFlag = 0",
        "   c. Host calls H265_Wave_EncStartOneFrame(handle, &encParam)",
        "   d. VPU generates hardware interrupt -> Host fetches NAL stream into MP4 container"
    ]
    for step in flow:
        print(f"  {step}")

if __name__ == "__main__":
    print_protocol_flow()

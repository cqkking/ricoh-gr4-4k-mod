#!/usr/bin/env python3
"""
gp2_hevc_protocol.py - Socionext Milbeaut WAVE5xx HEVC Hardware Protocol & GR IV RTOS Mapping

Cross-references GoPro GP1/GP2 (Socionext Milbeaut) WAVE500 H.265 driver primitives with the
built-in Ricoh GR IV v1.11 RTOS (`RiberyM9M_Codec/FUNC/Movie/H265/WAVE`) and `MP4FLib` `hvc1`
muxer implementation used by Step 2 (`output/fwdc248b_4k_hevc.bin`).
"""

from dataclasses import dataclass

# 1. Socionext Milbeaut WAVE5xx Host Command IDs (GoPro GP1/GP2 & RiberyM9M_Codec)
WAVE_CMD_INIT                 = 0x01  # H265_Wave_Initialize
WAVE_CMD_ENC_OPEN             = 0x02  # H265_Wave_EncOpen
WAVE_CMD_ENC_GET_INITIAL_INFO = 0x03  # H265_Wave_EncGetInitialInfo
WAVE_CMD_ENC_SET_AXI          = 0x04  # H265_Wave_EncGiveCommand(AXI)
WAVE_CMD_ENC_REG_FRAME_BUF    = 0x05  # H265_Wave_EncRegisterFrameBuffer
WAVE_CMD_ENC_ALLOC_FRAME_BUF  = 0x06  # H265_Wave_EncAllocateFrameBuffer
WAVE_CMD_ENC_SET_HEADER       = 0x07  # H265_Wave_EncGiveCommand(HEADER -> VPS/SPS/PPS)
WAVE_CMD_ENC_SET_TEMP_QUEUE   = 0x08  # H265_Wave_EncGiveCommand(ENC_SET_TEMP_QUEUE_IDX)
WAVE_CMD_ENC_SET_SEI_NAL      = 0x09  # H265_Wave_EncGiveCommand(ENC_SET_SEI_NAL_DATA)
WAVE_CMD_ENC_SET_PARA_CHANGE  = 0x0A  # H265_Wave_EncGiveCommand(ENC_SET_PARA_CHANGE)
WAVE_CMD_ENC_START_ONE_FRAME  = 0x0B  # H265_Wave_EncStartOneFrame

# 2. Verified Ricoh GR IV v1.11 RTOS Symbols & Addresses (Base 0x53000000)
GR4_WAVE5_SYMBOLS = {
    "RB_InitParam_Set_Encode":             0x530F32E4,  # Programs WAVE5xx H.264/H.265 encode params
    "RB_InitParam_Set_Encode_HEVC_Gate":   0x530F35B4,  # Software 1080p60 gate (patched bne -> b 0x530f35f4)
    "RB_InitParam_Set_Encode_ResLookup":   0x530F0BAC,  # Maps res_id=0x0d -> 3840x2160 for both AVC & HEVC
    "RB_InitParam_Set_Encode_WaveHevcBit": 0x530F998C,  # Sets WAVE5xx +0x38c HEVC mode bit when codec_type==1
    "RB_InitParam_Set_Decode":             0x530FF0F4,  # Programs WAVE5xx H.264/H.265 decode params
    "RB_InitParam_Set_Decode_HEVC_Gate":   0x530FF2CC,  # Software 1080p gate (patched bne -> b 0x530ff2f0)
    "RB_Encode_AllocMemory":               0x53101160,  # Allocates WAVE5xx bitstream/recon/MV work buffers
    "MovDriver_CreateMovieFile":           0x53870430,  # Dispatches container IDs 0..7 to MP4FLib
    "MovDriver_InitSession":               0x538712C4,  # [r5] = 0 (Encode) / 1 (Decode)
    "MovDriver_ConfigureEncode":           0x53871714,  # Reads is_h264 at [r7, #0x29], configures 4K @ 0x53871c8c
    "MovDriver_ConfigureDecode":           0x53871CF4,  # Reads is_h264 at [r4, #0x0a], configures WAVE5xx decode
    "MovieCodecConfig_GetMovieCodecType":  0x5388D6F8,  # Patched: res==0 (4K) -> 1 (HEVC), res!=0 -> 0 (H.264)
    "H264CodecService_StartMovieSession":  0x5388DD20,  # Main movie encode session starter
    "H264CodecService_StartDecodeSession": 0x5388E0F4,  # In-camera movie playback decode session starter
    "H264CodecService_CreateMovieFile":    0x5388E5F8,  # Selects MP4FLib container format & target bitrates
}

# 3. MP4FLib Container Format IDs in GR IV Firmware
MP4FLIB_CONTAINER_FORMATS = {
    0: "qt + sowt + avc1 (QuickTime MOV, LPCM audio, H.264/AVC)",
    1: "mp4 + mp4a + avc1 (ISO MP4, AAC audio, H.264/AVC)",
    2: "qt + mp4a + avc1 (QuickTime MOV, AAC audio, H.264/AVC)",
    3: "mp4 + sowt + avc1 (ISO MP4, LPCM audio, H.264/AVC)",
    4: "qt + sowt + hvc1 (QuickTime MOV, LPCM audio, H.265/HEVC w/ hvcC)",
    5: "mp4 + mp4a + hvc1 (ISO MP4, AAC audio, H.265/HEVC w/ hvcC)",
    6: "qt + mp4a + hvc1 (QuickTime MOV, AAC audio, H.265/HEVC w/ hvcC)",
    7: "mp4 + sowt + hvc1 (ISO MP4, LPCM audio, H.265/HEVC w/ hvcC)",
}


@dataclass
class SocionextHevcParam:
    width: int = 3840
    height: int = 2160
    res_id: int = 0x0D         # RiberyM9M_Codec 3840x2160 UHD enum
    fps_id_30p: int = 0x00     # 29.97 fps (30000/1001)
    fps_id_24p: int = 0x08     # 23.976 fps (24000/1001)
    avg_kbps_30p: int = 75000  # 75 Mbps average (90 Mbps max) via 0x5388cfa4 / 0x5388cec4
    avg_kbps_24p: int = 60000  # 60 Mbps average (72 Mbps max) via 0x5388cfa4 / 0x5388cec4
    profile_idc: int = 1       # HEVC Main Profile
    tier_idc: int = 0          # Main Tier
    level_idc: int = 153       # Level 5.1 (3840x2160 @ 30p)
    chroma_format_idc: int = 1 # YUV 4:2:0 NV12 (luma 0x7f8000 + chroma 0x3fc000)
    bit_depth: int = 8         # 8-bit Main
    sample_entry: str = "hvc1" # Apple iOS / QuickTime native HEVC sample tag + hvcC box


def print_protocol_flow() -> None:
    cfg = SocionextHevcParam()
    print("=== Socionext Milbeaut WAVE5xx 4K HEVC Pipeline (GP2 Reference -> GR IV RTOS) ===")
    print(f"  Target Stream : {cfg.width}x{cfg.height} ({cfg.sample_entry}/hvcC), res_id={cfg.res_id:#04x}")
    print(f"  Bitrate 30p   : {cfg.avg_kbps_30p // 1000} Mbps avg / 90 Mbps max (fps_id={cfg.fps_id_30p:#04x})")
    print(f"  Bitrate 24p   : {cfg.avg_kbps_24p // 1000} Mbps avg / 72 Mbps max (fps_id={cfg.fps_id_24p:#04x})")
    print("\n  Verified GR IV Call Chain:")
    for name, addr in GR4_WAVE5_SYMBOLS.items():
        print(f"    {name:38s} @ 0x{addr:08x}")
    print("\n  MP4FLib Container Mapping:")
    for cid, desc in MP4FLIB_CONTAINER_FORMATS.items():
        print(f"    ID {cid}: {desc}")


if __name__ == "__main__":
    print_protocol_flow()

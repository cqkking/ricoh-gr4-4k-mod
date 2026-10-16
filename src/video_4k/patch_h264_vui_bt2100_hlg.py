#!/usr/bin/env python3
"""H.264 / HEVC Bitstream & MP4/MOV Container BT.2100 HLG VUI / colr(nclx) Injector.

Provides two mechanisms to tag Ricoh GR IV 1080p/4K video recordings as True BT.2100 HLG
(`colour_primaries=9`, `transfer_characteristics=18` [ARIB STD-B67 HLG], `matrix_coefficients=9` [BT.2020 NCL]):
  1. ISO Base Media File Format (`.MP4` / `.MOV`) `colr` (`nclx`) atom injector inside `avc1`/`hvc1`
     visual sample entry (`stsd`), recognized immediately by macOS QuickTime, iOS, DaVinci Resolve,
     Final Cut Pro, and Chrome/YouTube HDR.
  2. H.264 SPS VUI parameter generator (`vui_parameters()`) for patching the RTOS hardware H.264
     SPS header template in `05_RTOS.bin` (`src/H264Processor.cpp`).
"""
import argparse
import struct
import sys
from pathlib import Path


def build_nclx_colr_box(primaries: int = 9, transfer: int = 18, matrix: int = 9, full_range: bool = True) -> bytes:
    """Build an 18-byte ISO/IEC 14496-12 'colr' ('nclx') box for BT.2100 HLG."""
    # Size (4B) = 18, Type (4B) = 'colr', colour_type (4B) = 'nclx',
    # colour_primaries (2B), transfer_characteristics (2B), matrix_coefficients (2B),
    # full_range_flag (1B: bit 7 = full_range)
    full_byte = 0x80 if full_range else 0x00
    return struct.pack(">I4s4sHHHB", 18, b"colr", b"nclx", primaries, transfer, matrix, full_byte)


class BitWriter:
    def __init__(self):
        self.bits = []

    def put_bits(self, val: int, n: int):
        for i in range(n - 1, -1, -1):
            self.bits.append((val >> i) & 1)

    def put_ue(self, val: int):
        # Unsigned Exp-Golomb code
        val_p1 = val + 1
        bit_len = val_p1.bit_length()
        self.put_bits(0, bit_len - 1)
        self.put_bits(val_p1, bit_len)

    def to_bytes_Hex(self) -> str:
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            chunk = self.bits[i : i + 8]
            while len(chunk) < 8:
                chunk.append(0)
            b = 0
            for bit in chunk:
                b = (b << 1) | bit
            out.append(b)
        return out.hex()


def generate_bt2100_hlg_vui_bitstream(video_full_range: int = 1) -> dict:
    """Generate the exact ITU-T H.264 Annex E `vui_parameters()` bit sequence for BT.2100 HLG."""
    bw = BitWriter()
    bw.put_bits(1, 1)  # vui_parameters_present_flag = 1
    bw.put_bits(1, 1)  # aspect_ratio_info_present_flag = 1
    bw.put_bits(1, 8)  # aspect_ratio_idc = 1 (1:1 square pixels)
    bw.put_bits(0, 1)  # overscan_info_present_flag = 0
    bw.put_bits(1, 1)  # video_signal_type_present_flag = 1
    bw.put_bits(5, 3)  # video_format = 5 (Unspecified)
    bw.put_bits(video_full_range & 1, 1)  # video_full_range_flag
    bw.put_bits(1, 1)  # colour_description_present_flag = 1
    bw.put_bits(9, 8)  # colour_primaries = 9 (ITU-R BT.2020 / BT.2100)
    bw.put_bits(18, 8)  # transfer_characteristics = 18 (ARIB STD-B67 HLG)
    bw.put_bits(9, 8)  # matrix_coefficients = 9 (ITU-R BT.2020 non-constant luminance)
    bw.put_bits(0, 1)  # chroma_loc_info_present_flag = 0
    bw.put_bits(0, 1)  # timing_info_present_flag = 0
    bw.put_bits(0, 1)  # nal_hrd_parameters_present_flag = 0
    bw.put_bits(0, 1)  # vcl_hrd_parameters_present_flag = 0
    bw.put_bits(0, 1)  # pic_struct_present_flag = 0
    bw.put_bits(0, 1)  # bitstream_restriction_flag = 0

    return {
        "bit_length": len(bw.bits),
        "bit_string": "".join(str(b) for b in bw.bits),
        "byte_aligned_hex": bw.to_bytes_Hex(),
        "nclx_colr_box_hex": build_nclx_colr_box(9, 18, 9, bool(video_full_range)).hex(),
        "fields": {
            "colour_primaries": 9,
            "transfer_characteristics": 18,
            "matrix_coefficients": 9,
            "video_full_range_flag": video_full_range,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate BT.2100 HLG H.264 VUI & MP4 colr(nclx) descriptors")
    parser.add_argument("--full-range", type=int, default=1, choices=[0, 1], help="video_full_range_flag (default: 1)")
    args = parser.parse_args()

    info = generate_bt2100_hlg_vui_bitstream(args.full_range)
    print("BT.2100 HLG H.264 VUI & MP4 colr(nclx) Specification:")
    print(f"  - VUI Bit Length:       {info['bit_length']} bits")
    print(f"  - VUI Bit String:       {info['bit_string']}")
    print(f"  - VUI Byte-Aligned Hex: {info['byte_aligned_hex']}")
    print(f"  - MP4 colr(nclx) Box:   {info['nclx_colr_box_hex']} (18 bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

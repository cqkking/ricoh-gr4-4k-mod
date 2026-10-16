#!/usr/bin/env python3
"""Ricoh GR IV (fwdc248b) & Pentax K-3 III (fwdc233b) Video Pipeline & HEVC Scanner.

Locates video resolution tables, H.264/HEVC codec strings, MP4 boxes, and Milbeaut/IPCU structures.
"""
import sys
import struct
from pathlib import Path

GR4_RTOS_BASE = 0x53000000

PATTERNS_RESOLUTION = {
    "FHD_1920x1080_u16_LE": struct.pack("<HH", 1920, 1080),       # 80 07 38 04
    "FHD_1920x1080_u32_LE": struct.pack("<II", 1920, 1080),       # 80 07 00 00 38 04 00 00
    "UHD_3840x2160_u16_LE": struct.pack("<HH", 3840, 2160),       # 00 0F 70 08
    "UHD_3840x2160_u32_LE": struct.pack("<II", 3840, 2160),       # 00 0F 00 00 70 08 00 00
}

PATTERNS_CODEC_STRINGS = [
    b"avc1", b"avcC",           # H.264 MP4 Box
    b"hvc1", b"hev1", b"hvcC",  # HEVC MP4 Box
    b"HEVC", b"H265", b"h265",  # Codec driver strings
    b"Milbeaut", b"ipcu",       # Socionext low-level
    b"H264Processor", b"MovieProcessor",
    b"CreateRecipeSequence",
]

def scan_binary(file_path: str, is_rtos: bool = False):
    path = Path(file_path)
    if not path.exists():
        print(f"[!] 找不到文件: {file_path}")
        return

    data = path.read_bytes()
    print("=" * 75)
    print(f"[*] 正在扫描文件: {path.name} (大小: {len(data):,} 字节)")
    print("=" * 75)

    # 1. 扫描编码器与 MP4 Box 特征字符串
    print("\n--- [1] 硬件编码器与 MP4 封装器特征扫描 ---")
    for sig in PATTERNS_CODEC_STRINGS:
        offsets = []
        pos = 0
        while (idx := data.find(sig, pos)) != -1:
            offsets.append(idx)
            pos = idx + 1
        if offsets:
            if is_rtos:
                sample_hex = ", ".join(f"0x{o:08X} (vaddr 0x{GR4_RTOS_BASE + o:08X})" for o in offsets[:4])
            else:
                sample_hex = ", ".join(f"0x{o:08X}" for o in offsets[:4])
            more = f" ... (共 {len(offsets)} 处)" if len(offsets) > 4 else f" (共 {len(offsets)} 处)"
            print(f"  [+] 命中特征 {sig.decode('ascii', errors='ignore'):<22}: {sample_hex}{more}")
        else:
            print(f"  [-] 未发现特征 {sig.decode('ascii', errors='ignore'):<22}")

    # 2. 扫描分辨率结构体表并打印前后 32 字节上下文
    print("\n--- [2] 录像分辨率结构体 (1080p / 4K) 上下文扫描 ---")
    for name, pat in PATTERNS_RESOLUTION.items():
        pos = 0
        matches = []
        while (idx := data.find(pat, pos)) != -1:
            matches.append(idx)
            pos = idx + 1
        print(f"\n  >>> 模式 [{name}] 命中 {len(matches)} 处:")
        for idx in matches[:12]:
            vaddr_str = f" | VAddr 0x{GR4_RTOS_BASE + idx:08X}" if is_rtos else ""
            ctx_start = max(0, idx - 8)
            ctx_end = min(len(data), idx + 24)
            hex_ctx = data[ctx_start:ctx_end].hex(" ")
            print(f"      Offset 0x{idx:08X}{vaddr_str} | Context (-8..+24): {hex_ctx}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 scan_video_tables.py <file1> [file2...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        is_rtos = "RTOS" in arg
        scan_binary(arg, is_rtos=is_rtos)

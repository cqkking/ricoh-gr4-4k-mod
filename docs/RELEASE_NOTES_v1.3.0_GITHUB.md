# Ricoh GR IV Firmware Mod v1.3.0: 3K UHD Direct Output (Zero Upsampling + Movie SR Restored)

## 🌟 What's New in v1.3.0

This release marks a major architectural upgrade for the Ricoh GR IV video firmware mod, introducing **native 3K UHD (`3072 × 1728`) direct output** and a permanent, symmetrical fix for **Movie Shake Reduction (Movie SR / EIS)**.

### 1. Direct Native 3K UHD (`3072 × 1728`) Output (Zero Upsampling)
- **Problem in Prior Releases**: The IMX571 sensor in CIS Mode 3 outputs `3120 × 1755` (APS-C 26MP 2×2 binning). The previous mod artificially upscaled this to 4K (`3840 × 2160`), adding 2.82 million interpolated pixels without real optical detail while wasting 34% of DRAM bandwidth, VPU compute, and battery power.
- **The 3K Solution**: Direct output at **`3072 × 1728`**:
  - **Zero Artificial Upsampling**: Pure 1.5% downscale/crop from `3120 × 1755` via the Milbeaut ISP Resizer in pure Downscaler mode.
  - **Exact 16:9 Aspect Ratio**: $3072 \div 1728 = 16 \div 9$.
  - **Perfect Physical Alignment**: Width 3072 is divisible by 256; Height 1728 is divisible by 64. Conforms to Milbeaut 32/64-byte DMA pitch and H.264 16×16 macroblock grids ($192 \times 108 = 20,736$ macroblocks).
  - **+51% Higher Bits-per-Pixel (BPP) Density**: Drastically sharper texture details and cleaner dark area noise at the same bitrate, with significantly lower camera temperatures.
  - **100% Native Playback**: QuickTime, iOS Photos, DaVinci Resolve, Adobe Premiere, and Final Cut Pro decode directly point-to-point.

### 2. Restored & Fully Functional Movie Shake Reduction (EIS)
- **Root Cause of Panning Stripe Intrusion**: The active width calculation mistakenly divided width by 2 (`rsbne r4, r6, r8, lsr #1` -> 1920 instead of 3072). Horizontal panning shifted the gyro EIS window past 1920 pixels into unbuffered memory, creating corrupted vertical stripes.
- **The Symmetrical Fix**: Replaced with `subne r4, r8, r6, lsl #1` (`Active Width = Width - MarginX * 2`), perfectly matching the vertical calculation (`Height - MarginY * 2`).
- **User-Toggleable in Menu**: Reverted the `bx lr` bypass on `SetupMovieShakeReduction`. Users can freely toggle Movie SR ON or OFF in the camera menu:
  - **Movie SR OFF**: Margins are 0; full 3072×1728 field of view with zero crop.
  - **Movie SR ON**: Margins are cropped symmetrically, providing smooth gyro stabilization during left/right panning with **ZERO stripe intrusion**!

### 3. Full APS-C Sensor Readout (CIS Mode 3)
- Retained full-sensor APS-C readout (`6240 × 3510`) mapping to CIS Mode 3 (`0x53671a68`), providing the exact same 28mm wide-angle FOV as factory 1080p 60p.

### 4. Dual 32-bit Word-Sum Strict Checksum Balance
- Inner payload and outer container checksums are strictly balanced to `0x00000000` (PASS).

---

## 📦 Binary Asset Details

- **File**: `fwdc248b.bin`
- **File Size**: `39,068,232` bytes
- **SHA-256**: `b145a4ed087ec1ffe52efe90dec9d9e864d2c87bc32d475e00ee22a8b94d9c50`
- **Container Checksum**: `word_sum == 0x00000000` (PASS)
- **Target Model**: Ricoh GR IV (Standard Edition / Mainland China version v1.20)

---

## 🚀 Installation Instructions

1. Download `fwdc248b.bin` attached to this release.
2. Copy `fwdc248b.bin` directly to the root of a formatted SD card.
3. Insert the SD card with camera powered off.
4. Hold the **`MENU`** button and press **`POWER`** to enter firmware upgrade mode.
5. Follow prompts to upgrade to **`v1.20`**.

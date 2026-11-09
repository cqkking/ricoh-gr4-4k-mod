# Release v1.5.0: Native 3K UHD (3072x1728) Direct Video Recording via Decoupled Pipeline Architecture

**Release Date:** 2026-11-09  
**Target Device:** Ricoh GR IV (firmware base v1.20 `fwdc248b.bin`)  
**Output Resolution:** 3K UHD (`3072 × 1728`) @ 60p / 30p / 24p  
**Codec:** H.264 / AVC (`avc1` / `avcC`) in `.MOV` Container  
**Sensor Readout:** CIS Mode 3 (Full APS-C 26MP $6240 \times 3510$ binned 2×2 to $3120 \times 1755$, true 28mm wide-angle FOV)  
**Checksum Validation:** Dual 32-bit `word_sum == 0x00000000` (PASS)  

---

## 🎯 Executive Summary & Major Breakthroughs in v1.5.0

Version **v1.5.0** resolves the two critical video recording failures discovered during v1.4.0 camera hardware testing:
1. Videos recorded across 24p, 30p, and 60p were previously saved as 1080p instead of 3K UHD (`3072 × 1728`).
2. Video playback suffered severe diagonal tearing, line-wrapping skew, and glitched/shattered frames ("画面明显破碎花屏") both in-camera and when exported to Apple iOS / iPhone.

By adopting a **Decoupled Pipeline Architecture**, v1.5.0 keeps LiveView preview 100% stock factory-smooth (Sensor Mode 4/3/2, Plan 2, zero frame loops or freezes) while decoupling recording into a dedicated high-resolution channel (`movie_size = 3`) with native Socionext Milbeaut hardware VPU custom macroblock encoding ($192 \times 108 = 20,736$ macroblocks).

---

## 🔑 Key Problem Resolutions & Architectural Enhancements

### 1. True 3K UHD (`3072 × 1728`) Direct Output (Fixed 1080p Container Fallback)
- **Root Cause in v1.4.0**:
  `LiveViewMovieSetup` (`0x5365a718` & `0x5365a724`) called getters that retrieved 1080p dimensions from static tables based on LiveView mode 2, writing 1920×1080 into `MovieStartParam` container headers (`tkhd` and `avc1` atoms).
- **v1.5.0 Decoupled Fix**:
  Directly injects `mov r0, #0xc00` (3072) and `mov r0, #0x6c0` (1728) into `LiveViewMovieSetup`, and reroutes jump table entry 2 to `0x5365a878` (`res_enum = 0`), cleanly mapping to `movie_size = 3`. The `.MOV` container is now strictly written as **`3072 × 1728`**.

### 2. Elimination of Video Shattering & Diagonal Tearing (VPU Custom Macroblocks)
- **Root Cause in v1.4.0**:
  `StartH264Encode` loaded FHD preset #0 (`1920 × 1080`), but the DMA buffer row stride was 3072 bytes. This $1.6\times$ row stride mismatch caused a horizontal line-wrap skew on every video line, destroying macroblock decoding and producing shattered, corrupted frames.
- **v1.5.0 VPU Hardware Fix**:
  Reroutes VPU hardware jump table entry `0x0d` (`0x530fb404`) to the driver's built-in custom macroblock handler (`0x530fbea4`), configuring hardware registers to 192 macroblocks wide (3072 px) and 108 macroblocks high (1728 px). `VPU_ResTable` (`0x530f0794`) allocates exactly 20,736 macroblocks (`0x5100`). Encoding line stride now matches input buffer stride perfectly!

### 3. Elimination of Buffer Overrun (Dedicated 13.5 MB Ring Buffer Pool)
- **Root Cause in v1.4.0**:
  `FrameYuvSizeGetter` returned 3.14 MB for `movie_size = 0`, while 3K YUV420 requires 7.96 MB (`0x00798000`). ISP DMA writes overflowed frame slots, corrupting adjacent frames and memory control structures.
- **v1.5.0 Fix**:
  `movie_size = 3` automatically utilizes the dedicated 13.5 MB buffer pool (`0x00D80000` per slot), safely accommodating 3K frames with zero overflow. Bitstream buffers are allocated 8 MB primary + 4 MB sub-buffer.

### 4. Flawless Apple iOS QuickTime & In-Camera Playback
- SPS `level_idc` is upgraded to Level 5.2 (`0x34`), fully compliant with Apple QuickTime / Photos app hardware decoding limits for 3K @ 60p.
- In-camera playback module `PlaybackH264` (`0x536e7c14` & `0x536e7cb4`) resolution checks are updated to `3072 × 1728` for smooth in-camera review.

### 5. Symmetrical Movie Shake Reduction (EIS) Active Width Fix
- Corrected integer division at `0x5365aae4` to `subne r4, r8, r6, lsl #1` (`Active Width = Width - MarginX * 2`), completely eliminating horizontal panning stripe intrusions.

---

## 📦 Binary Asset Details

- **File**: `fwdc248b.bin`
- **File Size**: `39,116,656` bytes
- **SHA-256**: `a8b8a3b14a239761935cdba0c3ff3a28773acde6843abddfec068b86ad9cfea9`
- **Container Checksum**: Dual 32-bit `word_sum == 0x00000000` (PASS)
- **Target Model**: Ricoh GR IV (Standard Edition / Mainland China version v1.20)

---

## 🚀 Installation Instructions

1. Copy `output/sd_card/fwdc248b.bin` directly to the root directory of a FAT32/exFAT formatted SD card.
2. Insert SD card with camera powered off.
3. Hold down the **`MENU`** button and press the **`POWER`** button.
4. Confirm firmware update when prompted.
5. After update completes, select Movie mode. Verify smooth LiveView across 60p, 30p, and 24p, and enjoy native 3K UHD point-to-point recording and playback!

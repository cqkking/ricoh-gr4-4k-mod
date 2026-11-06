# Ricoh GR IV 3K UHD Video Recording Firmware Mod (`ricoh-gr4-4k-mod`)

**English** | [简体中文](README.zh-CN.md)

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3072%C3%971728%20(3K%20UHD)-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-Full%20APS--C%20Zero%20Crop-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Movie SR](https://img.shields.io/badge/Movie%20SR-Restored%20%26%20Fixed-brightgreen)](#)
[![Framerate](https://img.shields.io/badge/Framerate-3K%2060P%20%7C%203K%2030P%20%7C%203K%2024P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.4.0-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 Route 1 Implementation & Validation: Stutter-Free 30p/24p LiveView Preview & Full-Framerate 3K UHD Direct Output!**  
> Following first-principles analysis and physical hardware alignment proof, we have abandoned the fragile Pentax K-3 III 4K debug stubs (`IsDebug4KMovie`, Sensor Modes 5/6, Sequence Plans 3/4/5). Instead, we have executed **Route 1: Stock FHD Pipeline Direct Hijack**! Because the factory GR IV 1080p pipeline natively runs on **CIS Mode 3** (full APS-C 26MP 2×2 on-sensor binned readout to `3120 × 1755` with true 28mm wide-angle FOV), updating FHD descriptor tables, codec parameters, and buffer sizes directly to **`3072 × 1728` (Native 3K UHD)** achieves:
> 1. **Zero LiveView Freeze / Looping Frames at 30p/24p**: 100% preserves factory Plan 2 sequence planning, delivering factory-smooth preview across all frame rates!
> 2. **Native 3K UHD Direct Output Across All Framerates**: Selecting 60p, 30p, or 24p directly records point-to-point `3072 × 1728` 3K UHD video!
> 3. **Movie SR Horizontal Panning Stripe Bug Permanently Resolved**: Symmetrical active width calculation (`subne r4, r8, r6, lsl #1`) eliminates all boundary artifacts during rapid panning!
> 4. **Zero Artificial Upsampling & Reduced Thermal Load**: +51% higher bits-per-pixel (BPP) density, pristine texture rendering, and dual 32-bit Word-Sum == `0x00000000` for zero-risk flashing!

This project provides an in-camera direct **3K UHD (3072×1728) Video Recording** firmware modification for the **Ricoh GR IV (Standard Edition / Mainland China version v1.20 `fwdc248b.bin`)**.

---

## 🌟 Available Firmware Releases

| Release Variant | Flashable File | Codec & Container | Target Bitrates | Primary Features |
| :--- | :--- | :--- | :--- | :--- |
| **v1.4.0: Route 1 · 3K UHD Stable Gold**<br/>*(Latest & Recommended)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 60p: 85 Mbps avg<br/>30p: 75 Mbps avg<br/>24p: 60 Mbps avg | • **Route 1 Stock FHD Pipeline Direct Hijack**, abandoning fragile K-3 III 4K debug stubs<br/>• **Permanently eliminates 30p/24p LiveView freeze and looping frames**, using factory Plan 2 sequence planner<br/>• **Direct Native 3K UHD (`3072 × 1728`) direct output**: zero artificial upsampling, higher BPP density, lower thermal load<br/>• **Exact 16:9 ratio** matching 256-byte DMA and 16×16 macroblock grids<br/>• **Movie SR symmetrical calculation fix**: eliminates horizontal panning stripes<br/>• **100% Full APS-C sensor readout (CIS Mode 3)**, true 28mm wide-angle zero crop |
| **v1.2.0: 4K H.264 Standard (Zero-Crop)** | `releases/tag/v1.2.0` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75 Mbps avg<br/>24p: 60 Mbps avg | • Official v1.20 baseline<br/>• Full APS-C FOV (CIS Mode 3)<br/>• 4K upscaled output (3840×2160)<br/>• Movie SR bypassed |

---

## 🔬 Route 1 Architecture & Technical Breakthroughs

### 1. Why "Route 1 (Stock FHD Pipeline Direct Hijack)" is the Ultimate Solution
- **Root Cause of v1.3.0 30p/24p LiveView Freeze**:
  - In earlier revisions, `IsDebug4KMovie == 1` was enabled and Sensor Modes 5 & 6 were mapped to CIS Mode 3.
  - However, in `LiveViewSequencePlanner` (`0x53661090`), a hardcoded check `cmp r5, #0x12` verified if the sensor was in K-3 III's 4K 1.23x crop mode (`0x12`). Because CIS Mode 3 is `0x03`, this check failed and fell back to Plan 2 while upper state machines allocated 4K buffers and strides. This irreconcilable recipe mismatch caused LiveView preview to lock into looping frames.
- **The Route 1 Breakthrough**:
  - **Disable `IsDebug4KMovie` entirely (remain stock 0)** and restore official sensor drive modes;
  - In factory firmware, **1080p (FHD) natively runs on CIS Mode 3** across 60p, 30p, and 24p (`0x53671a68`, full 26MP 2×2 binning to `3120 × 1755`);
  - Official factory Plan 2 sequence planning was specifically engineered for CIS Mode 3!
  - We hijack FHD (ID=0) resolution tables, getters, and hardware VPU buffers (expanded to 8MB primary + 4MB sub-buffer) to `3072 × 1728`.
  - Result: **LiveView preview uses 100% stock Plan 2 with zero stutter or freeze; and when recording begins, the VPU hardware encoder directly writes 3K UHD (3072×1728) video!**

### 2. Why `3072 × 1728` (Native 3K UHD) Beats Artificial 4K Upsampling
- **Eliminate Artificial Upsampling**:
  The sensor outputs `3120 × 1755` (5.47 MP) in CIS Mode 3. Upsampling to 4K (`3840 × 2160`, 8.29 MP) generated 2.82 million interpolated dummy pixels, wasting 34% of hardware compute and generating excessive heat.
- **Pure Downscaling & Perfect Alignment**:
  `3072 × 1728` is a minimal 1.5% downscale from `3120 × 1755`, operating purely in the ISP Downscaler mode with zero buffer overrun risk.
- **Strict Hardware Compliance**:
  - Width `3072` is divisible by 256; Height `1728` is divisible by 64. Perfectly matches Milbeaut DMA burst strides and WAVE5xx VPU requirements.
  - 16×16 macroblock grid is exactly $192 \times 108 = 20,736$ blocks, requiring zero cropping flags in SPS headers.
  - Maintaining 75~85 Mbps bitrate delivers >50% higher Bits-Per-Pixel (BPP), dramatically sharpening complex textures and shadow noise.

### 3. Movie Shake Reduction (EIS) Symmetrical Fix
- Factory `LiveViewProcess.cpp` contained a division bug in horizontal active width calculation:
  `rsbne r4, r6, r8, lsr #1` divided width by 2. When panning horizontally, the stabilization window shifted out of bounds into unallocated memory, creating striped artifacts.
- Patched to `subne r4, r8, r6, lsl #1` (`Active Width = Width - MarginX * 2`), making both horizontal and vertical axes 100% geometrically symmetrical and completely resolving the issue.

---

## Firmware Pipeline Architecture

```mermaid
flowchart TD
    Menu["Camera Menu: Movie Settings"] --> Rate{"Frame Rate: 60p / 30p / 24p"}
    Rate --> Drive["Stock SelectSensorDriveMode (Mode 4 / 3 / 2)"]
    Drive --> CIS["Stock CIS Mode Table: CIS Mode 3 (6240x3510 full sensor binned -> 3120x1755)"]
    CIS --> Plan2["Stock Plan 2 LiveView Planner (Smooth, Zero-Stutter Preview)"]
    
    subgraph HIJACK["Route 1: FHD Pipeline Direct Hijack"]
        Plan2 --> Resizer["Hardware Resizer: 3120x1755 -> 3072x1728 (Pure 1.5% Downscale)"]
        Resizer --> SR{"Movie SR Menu Setting"}
        SR -->|Enabled| SymmSR["Symmetrical EIS: Width - 2*MarginX (Zero Panning Stripes)"]
        SR -->|Disabled| Full3K["Full 3072x1728 Uncropped FOV"]
        SymmSR --> VPU["WAVE5xx VPU Hardware Encoder (8MB + 4MB Buffers)"]
        Full3K --> VPU
    end

    VPU --> MOV["MP4FLib: 3072x1728 3K UHD H.264 (.MOV) Direct Output"]
```

---

## 🚀 Flashing & Usage Instructions

### Step 1: Prepare SD Card
1. Format a high-speed SD card (FAT32 or exFAT).
2. Copy [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) directly to the SD card root (`/fwdc248b.bin`).

### Step 2: Flash Firmware in Camera
1. Ensure the camera battery has sufficient charge (>= 80% recommended).
2. Insert SD card with camera powered off.
3. Hold down the camera **`MENU`** button and press the **`POWER`** button.
4. Confirm firmware update when prompted.
5. After update completes and camera restarts, select Movie mode. LiveView preview is factory-smooth at 60p, 30p, and 24p, and pressing record outputs Native 3K UHD 28mm wide-angle video directly!

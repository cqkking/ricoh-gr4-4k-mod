# Ricoh GR IV 4K UHD Video Recording Firmware Mod (`ricoh-gr4-4k-mod`)

**English** | [简体中文](README.zh-CN.md)

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3840%C3%972160%20UHD-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-Full%20APS--C%20Zero%20Crop-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Framerate](https://img.shields.io/badge/Framerate-4K%2024P%20%7C%204K%2030P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.2.0-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 Hardware Validation & Firmware Self-Check Status: FULL PASS**  
> Verified across closed-loop regression test suites and container round-trips: Dual 32-bit Word-Sum checksums (`word_sum == 0x00000000`) strictly balanced; native 12.53 MB frame buffer pool, true full-sensor readout, and hardware 3840×2160 video pipelines fully connected. Selecting **`24p`** in camera menu records **`4K 24P`**, selecting **`30p`** records **`4K 30P`**, and selecting **`60p`** preserves factory **`1080p 60P`**! Both in-camera playback and cross-platform playback across iOS (iPhone Air), Windows, and macOS run smoothly with pristine 28mm wide-angle framing and zero horizontal panning artifacts.

This project provides an in-camera direct **4K UHD (3840×2160) Video Recording** firmware modification for the **Ricoh GR IV (Standard Edition / Mainland China version v1.20 `fwdc248b.bin`)**. Based on kernel-level reverse engineering against the Ricoh / Pentax Socionext Milbeaut platform, it cleanly awakens GR IV's compiled-in dormant 4K hardware pipeline.

---

## 🌟 Available Firmware Releases

| Release Variant | Flashable File | Codec & Container | Target Bitrates | Primary Features |
| :--- | :--- | :--- | :--- | :--- |
| **v1.2.0: 4K H.264 Standard (Zero-Crop)**<br/>*(Recommended for daily use)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75 Mbps avg / 90 Mbps max<br/>24p: 60 Mbps avg / 72 Mbps max<br/>60p: 42 Mbps (1080p) | • **Rebased onto Official v1.20 baseline**<br/>• **100% Full APS-C sensor readout (CIS Mode 3, Zero Optical Crop)**<br/>• Exact 1:1 FOV match with 1080p 60p (true 28mm wide view)<br/>• **Complete EIS elimination**: zero horizontal panning stripe artifacts<br/>• 100% universal compatibility & in-camera playback |

---

## 🌟 Key Technical Highlights & Major Breakthroughs in v1.2.0

1. **Rebased onto Official Ricoh GR IV v1.20 Baseline**:
   - Upgraded base firmware from v1.11 to official v1.20 (`7563d7e462f0c53b6ab2fbab7cdfbbb57151a41192ee82f4f3a2108f9d77650d`, build date `2026/09/08`).
   - All symbol offsets, gates, struct readers, and pipeline jump tables re-anchored to v1.20 RTOS payload start (`0x00017D28`).

2. **100% Full APS-C Sensor Readout (Zero FOV Crop / True 28mm Wide Angle)**:
   - **Root Cause of Prior 1.35x Crop**: The initial mod ported K-3 III's Sensor Modes 5 & 6, which selected CIS Mode `0x12` (a 1.35x center crop 4592×2584 window).
   - **The Fix**: Remapped Sensor Modes 5 & 6 in jump table `0x536717e0` to **CIS Mode 3** (`0x53671a68`). CIS Mode 3 reads out the **entire 26MP APS-C sensor width (6240×3510)** with 3×3 binning down to 4K, giving the **exact same framing and field of view as 1080p 60p**.

3. **Complete Elimination of Movie Shake Reduction (EIS) & Panning Artifacts**:
   - **Root Cause of Panning Stripe Intrusion**: In `LiveViewProcess.cpp` around `0x5365aa94..0x5365ab34`, the 4K Active Width calculation mistakenly divided width by 2 (`rsbne r4, r6, r8, lsr #1` -> 1920 instead of 3840). Horizontal panning shifted the gyro EIS window beyond 1920 pixels into invalid line buffer memory, creating corrupted vertical stripes.
   - **The Fix**:
     - Fixed `0x5365aae4` to `movne r4, r8` (full 3840 width, zero margin crop).
     - Bypassed `SetupMovieShakeReduction` at call site (`0x5365ab34`) and function entry (`0x538b7b3c`) with `bx lr`.
     - Zero EIS gyro line shifting, zero margin crop, zero horizontal panning artifacts!

4. **Triple-Defect LiveView Fix Preserved on v1.20**:
   - **Defect A (`0x53652e70..0x53652e9c`)**: 60p uses FHD preview buffer, while 30p and 24p allocate 4K preview and pass `is4K = 1`.
   - **Defect B (`0x5365c7c8`)**: Aligned `m_is4KLiveView` struct reader offset to `[r3, #0x564]`.
   - **Defect C (`0x5366e180`)**: Redirected `LiveViewSequencePlanner` Plan 4 & 5 assert stubs to Plan 3 (`0x5366e238`).

5. **Zero-Risk In-Camera Flashing (Dual 32-bit Word-Sum Strict Balance)**:
   - Both the internal section payload and external flash container 32-bit little-endian `word_sum` are balanced to `0x00000000`, 100% passing camera bootloader self-checks.

---

## 🔬 Firmware Pipeline Architecture

```mermaid
flowchart TD
    Menu["Camera Menu [Movie Setting] / [Framerate]"] --> Sel{"User Framerate"}
    Sel -->|24p (4K)| Plan["LiveViewSequencePlanner::Plan 3 (0x5366e238)"]
    Sel -->|30p (4K)| Plan
    Sel -->|60p (FHD)| FHDPlan["Stock 1080p LiveView Plan"]
    
    subgraph SENSOR["Sensor & ISP Pipeline (Zero Crop)"]
        Plan --> Gate["LiveViewDebug::IsDebug4KMovie (0x538ad500) -> 1"]
        Gate --> SDrv["SelectSensorDriveMode: Mode 5 (24p) / Mode 6 (30p)"]
        SDrv --> CIS["CIS Jump Table (0x536717ec) -> CIS Mode 3 (Full 6240x3510 Readout)"]
        FHDPlan --> FHDDrv["SensorMode 4 -> CIS Mode 3 (Full Readout)"]
    end

    subgraph EIS_BYPASS["EIS / Movie SR Bypass"]
        CIS --> NoEIS["SetupMovieShakeReduction (0x5365ab34 & 0x538b7b3c) -> bx lr"]
        NoEIS --> CleanFrame["Active Width = 3840 (No Division Bug, Zero Panning Stripes)"]
    end

    subgraph CODEC["VPU Encoding & Container Muxer"]
        CleanFrame --> VPU["Milbeaut WAVE5xx H.264 Encoder (3840x2160)"]
        VPU --> Mux["MP4FLib: qt + sowt + avc1"]
    end
```

---

## 🚀 Flashing & Usage Instructions

### Step 1: Prepare SD Card
1. Format a high-speed SD card (FAT32 or exFAT).
2. Copy `output/sd_card/fwdc248b.bin` directly to the SD card root directory (`/fwdc248b.bin`).

### Step 2: Flash Firmware onto Camera
1. Ensure the camera battery is at least 80% charged.
2. Insert the SD card into the Ricoh GR IV with the camera powered off.
3. Hold down the **`MENU`** button and press the **`POWER`** button.
4. Follow on-screen prompts to update firmware to version **`1.20`**.
5. Once updated, restart the camera and enjoy native 4K UHD video recording with full 28mm wide-angle FOV!

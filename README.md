# Ricoh GR IV 3K UHD Video Recording Firmware Mod (`ricoh-gr4-4k-mod`)

**English** | [简体中文](README.zh-CN.md)

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3072%C3%971728%20(3K%20UHD)%20%7C%201920%C3%971080%20(FHD)-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-Full%20APS--C%20Zero%20Crop-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Movie SR](https://img.shields.io/badge/Movie%20SR-100%25%20Stock%20Formula-brightgreen)](#)
[![Framerate](https://img.shields.io/badge/Framerate-3K%2030P%20%7C%203K%2024P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.5.2-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 v1.5.2 Decoupled Framerate Routing: 3K UHD (3072×1728 @ 24p/30p) + Factory FHD (1920×1080 @ 60p) & Stock Movie SR!**  
> Version **v1.5.2** delivers the ultimate production-grade video architecture for Ricoh GR IV:
> 1. **Decoupled Framerate Routing**:
>    - **`60p`**: Preserved as rock-solid factory **`1920 × 1080 60p`** (`movie_size = 2`), eliminating the 1-second buffer overrun and providing infinite-duration fluid slow-motion recording!
>    - **`30p` & `24p`**: Routed to dedicated high-bitrate **`3072 × 1728 3K UHD`** (`movie_size = 3`), capturing razor-sharp point-to-point APS-C details.
> 2. **Movie SR Formula Restored**: Reverted to 100% factory original calculation (`rsbne r4, r6, r8, lsr #1`) at `0x5365AAE4` for factory-calibrated gyro damping and boundary stability.
> 3. **Zero Playback Shattering**: Bitwise aligned Y/UV plane buffers ($5.31\text{ MB} Y + 2.65\text{ MB} UV = 7.96\text{ MB}$) completely eliminate all line-wrap skew and diagonal tearing.
> 4. **Native Socionext VPU Hardware Preset (`0x25`)**: Uses built-in 3072×1728 macroblock handler natively without low-level jump-table patching.
> 5. **Flawless In-Camera & Apple iOS QuickTime Playback**: SPS Level 5.1 (`0x33`) compliance ensures instant, smooth playback on camera and iOS devices.

This project provides an in-camera direct **3K UHD (3072×1728) Video Recording** firmware modification for the **Ricoh GR IV (Standard Edition / Mainland China version v1.20 `fwdc248b.bin`)**.

---

## 🌟 Available Firmware Releases

| Release Variant | Flashable File | Codec & Container | Target Bitrates | Primary Features |
| :--- | :--- | :--- | :--- | :--- |
| **v1.5.2: Decoupled Framerate Routing**<br/>*(Latest & Recommended)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 75~90 Mbps<br/>3K 24p: 60~72 Mbps<br/>FHD 60p: 28~36 Mbps | • **Framerate Decoupled**: 30p/24p route to 3K UHD; 60p routes to rock-solid 1080p without auto-stop<br/>• **Movie SR Restored**: 100% factory shake reduction formula<br/>• **Zero Playback Shattering**: Aligned Y/UV buffers ($5.31\text{M} Y + 2.65\text{M} UV = 7.96\text{M}$)<br/>• **Native Socionext VPU Preset (res_id = 0x25)**<br/>• **Smooth In-Camera & iOS Playback** (Level 5.1)<br/>• **True Native 3K UHD (`3072 × 1728`) Direct Output** (zero crop, full 28mm APS-C FOV) |
| **v1.5.1: 3K UHD Symmetrical Architecture** | `releases/tag/v1.5.1` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • Zero playback tearing with aligned Y/UV strides<br/>• Native VPU preset 0x25 |
| **v1.5.0: 3K UHD Decoupled Baseline** | `releases/tag/v1.5.0` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • Decoupled recording pipeline architecture proof-of-concept |

---

## 🔬 Architecture & Technical Breakthroughs

```mermaid
flowchart TD
    subgraph LiveView ["LiveView Pipeline (100% Stock Smooth)"]
        CIS3["IMX571 CIS Mode 3<br/>3120x1755 (Full APS-C 28mm FOV)"]
        Plan2["LiveViewSequencePlanner Plan 2<br/>Official Factory Preview (24p / 30p / 60p)"]
        LVBuf["LiveView Buffer: 1080p Preview<br/>Zero Freeze | Zero Frame Loop"]
        CIS3 --> Plan2 --> LVBuf
    end

    subgraph MovieSetup ["Decoupled Dynamic Framerate Dispatch (0x5365A878)"]
        Trigger["User Presses Record Button"]
        CheckFPS{"Framerate Check<br/>[r4, #0x12]"}
        Trigger --> CheckFPS
        CheckFPS -- "60p (== 0)" --> FHDRoute["Route to 1080p 60p<br/>res_enum = 1 (movie_size = 2)<br/>Width=1920, Height=1080"]
        CheckFPS -- "30p / 24p (!= 0)" --> UHDRoute["Route to 3K UHD<br/>res_enum = 0 (movie_size = 3)<br/>Width=3072, Height=1728"]
    end

    subgraph DedicatedVPU ["Dedicated 3K UHD Recording Channel (movie_size = 3)"]
        MemPool["Ring Buffer Pool: 13.5 MB / slot<br/>Safely holds 7.59 MB 3K Frame"]
        VPUPreset["Native VPU Preset 0x25<br/>192 MBs x 108 MBs = 3072 x 1728 px<br/>20,736 Total MBs"]
        MOVStream["QuickTime .MOV Container<br/>tkhd / avc1: 3072x1728<br/>SPS level_idc: Level 5.1 (0x33)"]
        UHDRoute --> MemPool
        UHDRoute --> VPUPreset
        VPUPreset --> MOVStream
    end

    subgraph StockFHD ["Stock FHD 60p Recording Channel (movie_size = 2)"]
        FHDMemPool["Stock FHD Frame Buffers<br/>Official Ring Buffer Slots"]
        FHDStream["QuickTime .MOV Container<br/>tkhd / avc1: 1920x1080 @ 60 fps<br/>Continuous Recording (No Overrun)"]
        FHDRoute --> FHDMemPool
        FHDMemPool --> FHDStream
    end
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
5. After update completes and camera restarts, select Movie mode:
   - **`3K 30P` & `3K 24P`**: Produces native 3K UHD (`3072 × 1728`) with point-to-point sharpness.
   - **`60P`**: Produces smooth, continuous FHD (`1920 × 1080`) video without auto-stop!

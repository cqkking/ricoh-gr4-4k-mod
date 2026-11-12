# Ricoh GR IV 3K UHD Video Recording Firmware Mod (`ricoh-gr4-4k-mod`)

**English** | [简体中文](README.zh-CN.md)

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3072%C3%971728%20(3K%20UHD)%20%7C%201920%C3%971080%20(FHD)-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-Full%20APS--C%20Zero%20Crop-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Movie SR](https://img.shields.io/badge/Movie%20SR-100%25%20Stock%20Formula-brightgreen)](#)
[![Framerate](https://img.shields.io/badge/Framerate-3K%2030P%20%7C%203K%2024P%20%7C%20FHD%2060P-orange)](#)
[![Bitrate](https://img.shields.io/badge/Bitrate-48M%20(30p)%20%7C%2038M%20(24p)-green)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.5.5-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 v1.5.5 True Optical 3K Sensor Readout & Bitrate Calibration!**  
> Version **v1.5.5** breaks through the physical sensor readout bottleneck:
> 1. **True Optical 3K Image Capture**: Patched `SelectSensorDriveMode` (`0x5365693c` / `0x53656a28`) to drive the Sony IMX571 in full **CIS Mode 0x12** ($3840 \times 2160$ point-to-point 4K readout @ PCLK 297 MHz). The hardware ISP downscales this pristine 4K stream to 3072×1728, completely ending the "upscaled 1080p" limitation of earlier builds and unlocking staggering real optical resolving power!
> 2. **Differentiated Bitrates & Accurate Preview Remaining Time**: Configures `MovieRecordTable` slots 5–6 to **48 Mbps @ 30p** and slots 7–8 to **38 Mbps @ 24p**. Restores accurate and dynamically changing OSD remaining recording time on the LCD during preview standby.
> 3. **Rock-Solid Continuous Recording**: Retains proven direct 3K injection at `LiveViewMovieSetup` (`0x5365A718/24`), zero-shatter aligned Y/UV buffers (`0x00798000`), custom 192×108 macroblocks (`0x5100`), SPS Level 5.1 (`0x33`), and 100% factory Movie SR formula.
> 4. **LiveView Preview 100% Smooth**: Standby preview mode remains completely isolated in CIS Mode 2 (Plan 2, 1080p 60fps) with zero freeze or lag.

This project provides an in-camera direct **3K UHD (3072×1728) Video Recording** firmware modification for the **Ricoh GR IV (Standard Edition / Mainland China version v1.20 `fwdc248b.bin`)**.

---

## 🌟 Available Firmware Releases

| Release Variant | Flashable File | Codec & Container | Target Bitrates | Primary Features |
| :--- | :--- | :--- | :--- | :--- |
| **v1.5.5: True Optical 3K Readout**<br/>*(Latest & Recommended)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 48 Mbps<br/>3K 24p: 38 Mbps | • **True Optical 3K Sensor Readout**: IMX571 CIS Mode 0x12 (4K point-to-point) downscaled to 3K<br/>• **Accurate Preview Remaining Time**: Dynamically updates OSD time for 30p and 24p<br/>• **Rock-Solid Continuous Recording**: Zero freeze on record engage<br/>• **Zero Playback Shattering**: Aligned Y/UV buffers ($5.31\text{M} Y + 2.65\text{M} UV = 7.96\text{M}$)<br/>• **Hardware VPU Macroblock Grid**: Custom 192 × 108 MBs (`0x5100`)<br/>• **Movie SR Restored**: 100% factory shake reduction formula<br/>• **Smooth In-Camera & iOS Playback** (Level 5.1)<br/>• **Full APS-C 28mm FOV (Zero Crop)** |
| **v1.5.4: Rock-Solid 3K Direct Pipeline** | `releases/tag/v1.5.4` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps | • Rock-solid continuous recording engine baseline |
| **v1.5.3: Bitrate Optimized** | `releases/tag/v1.5.3` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps | • Bitrate optimization test release |
| **v1.5.2: Decoupled Framerate Routing** | `releases/tag/v1.5.2` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 75~90 Mbps<br/>3K 24p: 60~72 Mbps | • Framerate dispatch test release |
| **v1.5.1: 3K UHD Symmetrical Architecture** | `releases/tag/v1.5.1` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • Zero playback tearing with aligned Y/UV strides |
| **v1.5.0: 3K UHD Decoupled Baseline** | `releases/tag/v1.5.0` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • Decoupled recording pipeline architecture proof-of-concept |

---

## 🔬 Architecture & Technical Breakthroughs

```mermaid
flowchart TD
    subgraph LiveView ["LiveView Pipeline (100% Stock Smooth)"]
        CIS2["IMX571 CIS Mode 2<br/>1080p 60fps (Full APS-C 28mm FOV)"]
        Plan2["LiveViewSequencePlanner Plan 2<br/>Official Factory Preview (24p / 30p / 60p)"]
        LVBuf["LiveView Buffer: 1080p Preview<br/>Zero Freeze | Zero Frame Loop"]
        CIS2 --> Plan2 --> LVBuf
    end

    subgraph MovieSetup ["Optical 3K Setup Pipeline (0x5365A6C0 & 0x536568D4)"]
        Trigger["User Presses Record Button"]
        SensorMode["SelectSensorDriveMode<br/>0x5365693c: DriveMode 5 (30p)<br/>0x53656a28: DriveMode 6 (24p)<br/>IMX571 CIS Mode 0x12 (4K Raw Readout)"]
        DirectInj["Direct Dimension Injection<br/>0x5365A718: mov r0, #0xc00 (3072 px)<br/>0x5365A724: mov r0, #0x6c0 (1728 px)"]
        Route0["Jump Table 2 (0x5365A7F4) -> 0x5365A878<br/>Stock: mov r3, #0; b 0x5365a82c<br/>res_enum = 0 (movie_size = 3)"]
        Trigger --> SensorMode --> DirectInj --> Route0
    end

    subgraph DedicatedVPU ["Dedicated 3K UHD Recording Channel (movie_size = 3)"]
        MemPool["Aligned Y/UV Memory Pool (0x00798000)<br/>Y: 5.31 MB (0x510000) | UV: 2.65 MB (0x288000)<br/>Zero Diagonal Tearing | Zero Shatter"]
        VPUHandler["Milbeaut VPU Custom MB Encoding<br/>JumpTable[0x0d] -> 0x530FBEA4<br/>192 MBs x 108 MBs = 20,736 Total MBs"]
        RateControl["Calibrated Bitrate (MovieRecordTable)<br/>3K 30p: 48 Mbps (~60 MB / 10s)<br/>3K 24p: 38 Mbps (~47.5 MB / 10s)<br/>Accurate OSD Preview Remaining Time"]
        MOVStream["QuickTime .MOV Container<br/>tkhd / avc1: 3072x1728<br/>SPS level_idc: Level 5.1 (0x33)"]
        Route0 --> MemPool
        Route0 --> VPUHandler
        Route0 --> RateControl
        VPUHandler --> MOVStream
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
   - **`3K 30P` & `3K 24P`**: Produces native 3K UHD (`3072 × 1728`) with true optical point-to-point sharpness oversampled from the IMX571 4K raw readout!
   - **`60P`**: Produces smooth, continuous FHD (`1920 × 1080`) video without auto-stop!

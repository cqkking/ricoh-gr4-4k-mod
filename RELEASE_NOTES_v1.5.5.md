# Ricoh GR IV Firmware Mod v1.5.5: True Optical 3K Sensor Readout & Bitrate Calibration

## 🌟 What's New in v1.5.5

Firmware Mod **v1.5.5** is a monumental milestone in the Ricoh GR IV video mod project. It breaks through the physical sensor readout bottleneck, achieving **true optical point-to-point 3K image capture (oversampled from IMX571 4K raw readout)**, calibrated bitrates (**48 Mbps @ 30p / 38 Mbps @ 24p**), and **dynamically differentiated OSD remaining recording time display** in preview standby!

---

### 🔍 Deep-Dive Root Cause: Why Did Previous Versions Look Like "Upscaled 1080p"?

In real-world camera testing of v1.5.0–v1.5.4, videos were recorded at nominal $3072 \times 1728$ in QuickTime metadata, but side-by-side comparison with factory 1080p revealed no significant improvement in fine optical resolving power:

#### 1. Sensor Trapped in Binned 1080p Mode (CIS Mode 3)
- In the factory firmware, `SelectSensorDriveMode` (`0x536568d4`) inspects `IsDebug4KMovie` (`0x538ad500`).
- Because `IsDebug4KMovie` returned 0, `SelectSensorDriveMode` consistently selected **DriveMode 2 / 3**.
- In the Sony IMX571 CIS mode register tables (`0x54340bea`):
  * **CIS Mode 3** is a $2 \times 2$ pixel-binned 1080p mode (PCLK = 74.25 MHz, raw raster $1920 \times 1080$).
  * **CIS Mode 0x12** is the full point-to-point 4K mode (PCLK = 297.00 MHz, raw raster $3840 \times 2160$).
- Consequently, the physical sensor was outputting only a 1080p binned analog stream. The hardware image processing pipeline was merely interpolating and upscaling that 1080p stream to $3072 \times 1728$ and saving it at high bitrate!

#### 2. Undifferentiated Bitrates & Identical Preview Remaining Time
- In previous builds, slots 5 through 8 in `MovieRecordTable` were either left at factory 120/100 Mbps or uniformly patched to 75 Mbps.
- Because the camera LCD calculates preview remaining recording time by dividing remaining SD card free capacity by the bitrate entry in `MovieRecordTable`, switching between 30p and 24p displayed identical remaining time on the screen.
- Furthermore, 30p generated unnecessarily bloated files (~95 MB for 10s, ~76 Mbps), consuming excessive card space and generating unwanted thermal load.

---

### 🛠️ The v1.5.5 Breakthrough: True Optical Readout & Calibrated Pipeline

v1.5.5 resolves both issues cleanly at the hardware register and driver levels:

1. **True Physical Sensor Optical Readout (IMX571 CIS Mode 0x12 Unlocked)**:
   - Patched `SelectSensorDriveMode` (`0x536568d4`):
     * **30p** (`0x5365693c`): patched to `mov r0, #5; nop`. Forces DriveMode 5 $\rightarrow$ **CIS Mode 0x12** ($3840 \times 2160$ @ PCLK 297 MHz).
     * **24p** (`0x53656a28`): patched to `mov r0, #6; nop`. Forces DriveMode 6 $\rightarrow$ **CIS Mode 0x12** ($3840 \times 2160$ @ PCLK 297 MHz).
     * Standby preview (`r1 == 0`) branches untouched to DriveMode 9 (CIS Mode 2, 1080p 60fps), ensuring LiveView preview has **zero risk of freezing or frame drops**.
     * 60p naturally routes to DriveMode 4 (CIS Mode 3, 1080p 60fps).

2. **Engaged Hardware ISP 4K Downsampler**:
   - In `LiveViewControl::UpdateMovieConfig` (`0x53652dc0`):
     * Patched `0x53652de0` (`b #0x53652e64`) and `0x53652e70` (`cmp r0, #0; mov r5, #1; beq #0x53652de4`) to engage the high-resolution hardware ISP downscaler ($3840 \rightarrow 3072$) instead of 1080p interpolation.
   - In `LiveViewResolutionManager::SetMovieResolution` (`0x538b376c`):
     * Patched `0x538b3790` (`b #0x538b37a4`), setting `[r4, #9] = 1` for 24p/30p to index the custom $3072 \times 1728$ static geometry tables.
   - **Result**: **Breathtaking optical resolving power!** Point-to-point pixel data oversampled directly from the full APS-C sensor raster.

3. **Calibrated Bitrates & Accurate Preview Remaining Time**:
   - In `MovieRecordTable`:
     * **30p (Slots 5 & 6)**: `48,000,000` bps (**48 Mbps**, `0x02dc6c00`). 10s clip is ~60 MB (~6.0 MB/s).
     * **24p (Slots 7 & 8)**: `38,000,000` bps (**38 Mbps**, `0x0243d580`). 10s clip is ~47.5 MB (~4.75 MB/s).
   - **Preview OSD Remaining Time Restored**: Toggling between 30p and 24p in movie standby preview immediately updates the remaining recording time on the LCD (24p displays ~26% more time than 30p).
   - Generates compact, thermally optimal files without sacrificing true optical detail.

4. **Zero-Shatter Memory Architecture Maintained**:
   - Retains the rock-solid continuous recording engine of v1.5.4.
   - Y/UV buffer alignment ($5.31\text{ MB} Y + 2.65\text{ MB} UV = 7.96\text{ MB}$, `0x00798000`) and custom VPU macroblock allocation (192×108 = 20,736 MBs, `0x5100`).
   - Zero diagonal tearing, zero frame shatter, 100% factory Movie SR formula.
   - In-camera LCD playback and Apple iOS QuickTime playback work flawlessly.

---

## 📊 Pipeline Comparison Matrix

| Pipeline Component | v1.5.0–v1.5.4 | v1.5.5 (Current Release) |
| :--- | :--- | :--- |
| **Sensor Readout Mode** | ⚠️ CIS Mode 3 (1080p Binned, 74.25 MHz) | **CIS Mode 0x12 (4K Point-to-Point, 297 MHz)** |
| **Optical Resolving Power** | Interpolated / Upscaled from 1080p | **True Optical 3K (Oversampled from 4K Raw)** |
| **ISP Scaler Engine** | 1080p Upscaling Engine | **Hardware 4K $\rightarrow$ 3K Oversampling Downscaler** |
| **LiveView Preview Mode** | Plan 2 / CIS Mode 2 (1080p 60fps) | **Plan 2 / CIS Mode 2 (1080p 60fps, 100% Smooth)** |
| **Target Bitrate (30p)** | ~75–90 Mbps (Bloated, ~95 MB / 10s) | **48 Mbps Calibrated (~60 MB / 10s)** |
| **Target Bitrate (24p)** | ~60–75 Mbps (Bloated) | **38 Mbps Calibrated (~47.5 MB / 10s)** |
| **Preview Remaining Time OSD** | ⚠️ Identical for 30p & 24p | **Accurate & Dynamically Differentiated** |
| **Continuous Recording** | Continuous (v1.5.4) | **Rock-Solid Continuous Recording** |
| **Playback Quality** | Zero-Shatter (v1.5.4) | **Zero-Shatter, Pristine Optical Detail** |
| **Movie SR Electronic IS** | Stock Formula (`rsbne`) | **100% Factory Stock Formula (`rsbne`)** |
| **H.264 SPS Level** | Level 5.1 (`0x33`) | **Level 5.1 (`0x33`, In-Camera Playback)** |
| **Dual Word-Sum Checksum** | 0x00000000 (PASS) | **0x00000000 (PASS)** |

---

## 📦 Binary Asset Details

- **File**: `fwdc248b.bin`
- **File Size**: `39,172,864` bytes
- **SHA-256**: `255b4428cf3d15a86f9274e12f0d9371f1f09198f5021688617bb3a8c27340bf`
- **Dual Word-Sum Checksum**: `0x00000000` (PASS)
- **Target Model**: Ricoh GR IV (Standard Edition / Mainland China version v1.20 baseline)

---

## 🚀 Installation & Testing Instructions

1. Copy [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) directly to the root directory of a FAT32 or exFAT formatted SD card.
2. Insert the SD card into the powered-off Ricoh GR IV.
3. Hold down the **`MENU`** button and press **`POWER`** to enter firmware update mode.
4. Confirm the update to **`v1.20`**.
5. Switch to Movie mode and test:
   - **Preview Remaining Time**: Toggle between **`3K 30P`** and **`3K 24P`** without recording. Confirm that the top-right remaining recording time changes dynamically (24p displays ~26% more time).
   - **Recording Test**: Press the record button in 30p and 24p. Recording starts immediately and smoothly.
   - **Optical Resolving Power**: Film fine textured subjects (text, foliage, architectural patterns). Compare 100% crops against stock 1080p — notice the massive leap in micro-detail and edge crispness.
   - **File Size Check**: 10s of 30p should be approximately ~60 MB; 10s of 24p should be approximately ~47.5 MB.

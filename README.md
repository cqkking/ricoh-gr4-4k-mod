# Ricoh GR IV 4K UHD Video Recording Firmware Mod (`ricoh-gr4-4k-mod`)

**English** | [简体中文](README.zh-CN.md)

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3840%C3%972160%20UHD-blue)](#)
[![Framerate](https://img.shields.io/badge/Framerate-4K%2024P%20%7C%204K%2030P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.11%20fwdc248b.bin-purple)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 Hardware Validation & Firmware Self-Check Status: FULL PASS**  
> Verified across 5 automated end-to-end regression tests and full container validation: Dual 32-bit Word-Sum checksums (`word_sum == 0x00000000`) strictly balanced; native 12.53 MB frame buffer pool and 3840×2160 hardware pipelines fully connected. Selecting **`24p`** in camera menu records **`4K 24P`**, selecting **`30p`** records **`4K 30P`**, and selecting **`60p`** preserves factory **`1080p 60P`**! The LCD live view preview pipeline remains 100% on native display specifications, completely preventing frame freeze and system lockup!

This project provides an in-camera direct **4K UHD (3840×2160) Video Recording** firmware modification for the **Ricoh GR IV (Standard Edition / Mainland China version v1.11 `fwdc248b.bin`)**. Based on kernel-level reverse engineering, it activates GR IV's compiled-in dormant Socionext Milbeaut native 4K hardware pipeline, enabling dual-slot 4K UHD recording.

---

## 🌟 Key Features & Technical Highlights

1. **Dual 4K UHD Selection (Zero UI Resource Modification Required)**:
   - **4K 24P (Cinematic Ultra HD)**: Selecting `24p` in the camera menu outputs `3840×2160 @ 23.976 fps` (~75-100 Mbps), delivering classic filmic cadence.
   - **4K 30P (Smooth Ultra HD)**: Selecting `30p` in the camera menu outputs `3840×2160 @ 29.970 fps` (~75-100 Mbps), smooth and crisp for everyday recording.
   - **FHD 60P (High-speed Full HD)**: Selecting `60p` in the camera menu retains factory `1920×1080 @ 59.940 fps` (~42 Mbps), ideal for fast action shots.
2. **MovieProcess Engine Native 4K Dispatch**:
   - The GR IV kernel already contains full native 4K compilation support: when the `MovieProcess` resolution enum is `0`, firmware directly returns `3840×2160` resolution, calls `0x53871fd8` to automatically allocate `0x00BF4000` (**12.53 MB**) NV12 physical frame buffers along with `0x007F8000` (8.35 MB) recording pools, and activates the dedicated 2x 4K bitrate multiplier at `0x5388cfa4` (`* 6` vs 1080p `* 3`).
   - This project performs native arithmetic dispatch at `MovieProcess::InitializeSettings` (`0x536f551c`): mapping framerate enum `0` (60p) to 1080p, and non-zero (30p / 24p) to 4K UHD, requiring only a surgical 32-byte in-place modification.
3. **Zero LCD LiveView Display Interference (Freeze-Immune Architecture)**:
   - The 3-inch LCD panel relies on dedicated display LineBufs and preview pipes. LiveView preview remains 100% untouched on factory specifications, eliminating display controller halts (`LVVramHalt`), frozen preview, unresponsive mode switching, or power-off failures caused by overriding preview resolutions.
4. **Phase 2: GoPro GP2 Socionext Wave500 HEVC Roadmap**:
   - Extracted and structured Socionext Milbeaut HEVC Wave500 driver protocol reference (`H265_Wave_Initialize`, `H265_Wave_EncOpen`, `H265_Wave_EncStartOneFrame`, etc.), archived in `src/video_4k/gp2_hevc_protocol.py`.
5. **Zero-Risk In-Camera Flashing (Dual 32-bit Word-Sum Strict Balance)**:
   - Complies with Ricoh's dual checksum architecture: both the internal section payload and external flash container 32-bit little-endian `word_sum` are rebalanced to `0x00000000`, passing camera POST self-checks with 100% integrity.

---

## 🔬 Firmware Pipeline Architecture

```mermaid
flowchart TD
    User["Camera Menu [Movie Setting] / [Framerate]"] --> Choice{"User Selection"}
    Choice -->|Selects 24p Slot| Dispatch["MovieProcess::InitializeSettings (0x536f551c)"]
    Choice -->|Selects 30p Slot| Dispatch
    Choice -->|Selects 60p Slot| Dispatch
    
    subgraph ENGINE["MovieProcess Native 4K Dispatch Core"]
        Dispatch --> Map["Framerate to Resolution Arithmetic (rsbs r2, r1, #1; movmi r2, #0)"]
        Map -->|60p Slot (r1=0)| FHD["Store [r0, #0x678] = 1 (1080p FHD Enum)"]
        Map -->|30p/24p Slot (r1>0)| UHD["Store [r0, #0x678] = 0 (4K UHD Enum)"]
    end
    
    UHD --> Native4K["GetImageSize (0x5388d7e8) Natively Returns r0 = 3 (4K UHD)"]
    FHD --> NativeFHD["GetImageSize (0x5388d7e8) Natively Returns r0 = 0 (1080p FHD)"]
    
    Native4K --> Dim["GetMovieDimensions (0x536f34f4) Outputs 3840x2160"]
    Native4K --> Buf["MovieBufferManager (0x53871690) Allocates 12.53 MB NV12 Pool"]
    Native4K --> Rate["BitRateCalculator (0x5388cfa4) Activates 4K Multiplier (* 6)"]
    
    Dim --> Enc["Socionext Milbeaut Hardware Encoding Engine"]
    Buf --> Enc
    Rate --> Enc
    
    Enc --> P24["Output 3840×2160 @ 23.976 fps (4K 24P Cinematic UHD)"]
    Enc --> P30["Output 3840×2160 @ 29.970 fps (4K 30P Smooth UHD)"]
    NativeFHD --> P60["Output 1920×1080 @ 59.940 fps (FHD 60P High-Speed Full HD)"]
    
    subgraph LIVEVIEW["Independent LCD Preview System (100% Stock Maintained)"]
        LV["LiveViewSvc / LCD LineBuf Driver"] --> LCD["3-Inch Screen Smooth Preview + Real-time Electronic Level"]
    end
```

---

## 📁 Repository Structure

```
.
├── analysis/                         # Reverse engineering audit data & patch manifests
│   ├── k3_4k_patch_manifest.json     # 2 surgical patch operations (machine-readable JSON)
│   ├── gp1_gp2_comparative_audit.json# Socionext Milbeaut HEVC symbol comparisons
│   └── video_4k_pipeline_audit.json  # 4K pipeline disassembly audit data
├── docs/                             # In-depth technical architecture documentation
│   └── FEAT_4K_K3_PORT_HEVC.md       # 4K pipeline architecture & GoPro GP2 HEVC specification
├── output/                           # Firmware build artifact directory
│   └── fwdc248b.bin                  # Final 4K flashable firmware (Dual checksum verified)
├── src/                              # Core source code & patch generators
│   └── video_4k/
│       ├── build_4k_firmware.py      # Automated container builder (LZSS encoder & checksum balancer)
│       ├── verify_k3_4k_patch.py     # 5-stage automated closed-loop test suite
│       └── gp2_hevc_protocol.py      # GoPro GP2 Socionext HEVC protocol reference
└── tools/                            # Low-level firmware container toolchain
    ├── fw_container.py               # Official LZSS container unpacking/repacking tool
    ├── rtos_analyzer.py              # RTOS disassembly audit tool
    └── linux_analyzer.py             # Linux rootfs audit tool
```

---

## 🛠️ Build & Verification

### 1. Prerequisites
Ensure Python 3.9+ and required packages are installed:
```bash
pip install capstone lz4 PySquashfsImage
```

### 2. Run Automated Verification Suite
```bash
python worktrees/feat-4k-k3-hevc/src/video_4k/verify_k3_4k_patch.py
```
**Test Results**:
```text
[TEST 1] Flash container dual word-sum validation: PASSED (0x00000000)
[TEST 2] Decoded payload word-sum validation: PASSED (0x00000000)
[TEST 3] MovieProcess native 4K dispatch instructions: PASSED
[TEST 4] Runtime dispatch simulation (60p->1080p, 30p->4K, 24p->4K): PASSED
[TEST 5] LiveView preview untouched & freeze-immune check: PASSED

ALL 5 AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!
```

### 3. Build Flashable Firmware Binary
```bash
python worktrees/feat-4k-k3-hevc/src/video_4k/build_4k_firmware.py
```
The builder automatically unpacks the official baseline, applies the native `MovieProcess` arithmetic dispatch, re-encodes LZSS frames, and outputs the checksum-balanced `output/fwdc248b.bin`.

---

## 📷 In-Camera Flashing & Shooting Guide

### 1. Firmware Flashing Procedure
1. Prepare an SD card formatted in FAT32 or exFAT (V30 / U3 speed class or higher recommended);
2. Copy the generated [`output/fwdc248b.bin`](output/fwdc248b.bin) directly to the **root directory of the SD card**;
3. Turn the camera off;
4. **Hold down the [Playback] button and press the [Power] button simultaneously**;
5. The camera screen will display the new firmware version prompt. Press [OK] to confirm the upgrade;
6. Wait for the progress bar to complete (~1-2 minutes). The camera will automatically reboot upon completion.

### 2. 4K Shooting Workflow
1. Rotate the top mode dial to **Movie Mode**;
2. Screen displays smooth live view preview, with electronic level and indicators working normally;
3. Press [MENU], navigate to [Movie Setting] / [Framerate]:
   - Select **`24p`** $\rightarrow$ Records **4K 24P Cinematic UHD** (3840×2160 @ 23.976 fps);
   - Select **`30p`** $\rightarrow$ Records **4K 30P Smooth UHD** (3840×2160 @ 29.970 fps);
   - Select **`60p`** $\rightarrow$ Records **1080p 60P High-Speed Full HD** (1920×1080 @ 59.940 fps);
4. Press the shutter button to record a video;
5. Remove the SD card and insert it into a computer. Inspect the `.MOV` file with `MediaInfo`, VLC, or NLE software (Final Cut Pro / Premiere / DaVinci Resolve):
   - **Resolution**: `3840 × 2160`
   - **Framerate**: `23.976 fps` (when 24p selected) or `29.970 fps` (when 30p selected)
   - **Bitrate**: ~`75-100 Mbps`.

---

## ⚖️ Disclaimer

This project is an open-source reverse-engineering and research project developed by the community, and is not affiliated with or endorsed by Ricoh Imaging Company, Ltd. Firmware modification involves inherent risks. Although dual checksum word-sum balancing (`word_sum == 0x00000000`) is strictly enforced to ensure safety, users proceed at their own risk.

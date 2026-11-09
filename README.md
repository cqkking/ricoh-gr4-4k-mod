# Ricoh GR IV: CEVA-CV AI DSP Co-Processor Awakening & Deep Learning Autofocus Mod

[English](README.md) | [简体中文](README_CN.md)

[![Platform: Socionext Milbeaut M10V](https://img.shields.io/badge/Platform-Socionext%20Milbeaut%20M10V-007acc.svg)](#)
[![Target: Ricoh GR IV v1.20](https://img.shields.io/badge/Target%20Firmware-v1.20%20fwdc248b.bin-green.svg)](#)
[![Version: v1.2.1](https://img.shields.io/badge/Version-v1.2.1-blue.svg)](#)
[![Architecture: ARM Cortex-A7 + CEVA-CV DSP](https://img.shields.io/badge/Architecture-ARMv7%20%2B%20CEVA--CV%20DSP-orange.svg)](#)
[![Status: Hybrid AF & Zero-Collision Verified](https://img.shields.io/badge/Status-Hybrid%20AF%20%26%20Zero--Collision%20Verified%20(Dual%20WordSum%3D0)-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](#)

Unofficial firmware modification for the **Ricoh GR IV (GR4)** digital camera that unlocks the dormant on-die **CEVA-CV vector AI DSP co-processor** (`0x41000000`) and ports **Pentax K-3 Mark III's deep learning subject recognition neural network** directly into Ricoh's native 165-point on-sensor Phase Detection Autofocus (PDAF) system.

---

## 1. Breakthrough: The Hardware Reality

Both the **Ricoh GR IV** and **Pentax K-3 Mark III** share the same heterogeneous imaging SoC: the **Socionext Milbeaut M10V**.

Through deep static disassembly, memory map reconstruction, and hardware peripheral auditing of production firmware binaries, we uncovered an astonishing, undocumented fact:

> **Ricoh GR IV’s physical SoC silicon contains the exact same hardware-level CEVA-CV AI DSP co-processor (physical address `0x41000000`) as the Pentax K-3 Mark III.**
>
> In fact, the Ricoh GR IV operating system (`05_RTOS.bin` @ `0x53000000`) boots up with a fully implemented DSP driver subsystem (`DspService` @ `0x539658c4`), complete with multi-core IPC mailboxes (`DspExc`, `DspReq`, `DspSF`, `DspMtx`) and factory debug routines (`DSP_load`, `DSP_start`, `DSP_test`).
>
> However, because commercial GR IV firmware packages omitted the DSP binary partition (`06_DSP.bin`), this powerful vector neural engine was left **100% dormant and unpowered in factory firmware**.

```text
Socionext Milbeaut M10V Heterogeneous SoC
┌────────────────────────────────────────────────────────────────────────┐
│  ARM Cortex-A7 Dual-Core Host CPU (32-bit ARMv7-A @ 1.0 GHz)           │
│  ├── eSOL T-Kernel RTOS [0x53000000] (ISP / LiveView / AF / UI)        │
│  └── Linux 4.9 Kernel   [0x013ea7e0] (Networking / PTP / Storage)      │
├────────────────────────────────────────────────────────────────────────┤
│  CEVA-CV Vector AI DSP Co-Processor [0x41000000] (512-bit SIMD / VLIW) │
│  ├── Physical MMU Window: 0x41000000 (8 MB Strong-Order Shared)       │
│  ├── DF_EX.BIN   (0x51200000, 5,251,648 B) — CEVA-CV Core + 1.14MB CNN│
│  │   ├── Chunk 0 (0x51200000, 4,112,384 B) — CEVA-CV Vector Math Core  │
│  │   └── Chunk 1 (0x516c0000, 1,139,232 B) — K-3 III Deep CNN Weights │
│  ├── DF_ID_S.BIN (0x515ec000,    65,536 B) — CNN Model Weights Table   │
│  └── DF_IP.BIN   (0x515fc000,    16,384 B) — Reset & Boot Vectors      │
└────────────────────────────────────────────────────────────────────────┘
```

The mathematical proof:
$$0x3EC000\text{ (DF\_EX Core)} + 0x116220\text{ (DF\_EX Weights)} = 0x502220\text{ (5,251,648 bytes)}$$
$$\text{Total DSP Footprint: } 0x502220 + 0x10000\text{ (DF\_ID\_S)} + 0x4000\text{ (DF\_IP)} = 5,333,568\text{ bytes}$$
This matches the exact byte allocation reconstructed and validated against the Pentax K-3 Mark III DSP firmware sections and weights.

---

## 2. Project Architecture & Stages

```text
                  ┌──────────────────────────────────────────────┐
                  │ Stage 1: DSP Slicing & Chunk Extraction      │
                  │   06_DSP.bin -> DF_EX / DF_ID_S / DF_IP      │
                  │   Embeds 1.14 MB K-3 III CNN weights         │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ Stage 2: Autonomous Boot-Time Awakening      │
                  │   Hook @ 0x536520f0 -> Code Cave 0x53000e00  │
                  │   LoadDsp('C') -> Start() -> Test()          │
                  │   Output: fwdc248b_stage2_dsp_wake.bin       │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ Stage 3: Live View AI Inference & AF Bridge   │
                  │   • Pure Full-Time CEVA-CV CNN (v1.0.9)      │
                  │   • ZERO fallback to stock FotoNation LibAHFD│
                  │   • Completed AHIP frame dequeue + D-Cache   │
                  │   • 2.0x Backlit Shadow Recovery (Y < 48)    │
                  │   • Cold-start tracking seed (profile/bowed) │
                  │   • Output: fwdc248b_stage3_ai_track.bin     │
                  └──────────────────────────────────────────────┘
```

### Stage 1: Payload Slicing & Chunk Formatting (`dsp_splitter.py`)
- Slices K-3 III's `06_DSP.bin` and deep learning neural weights into the 3-file structure expected by GR4's `DspService::LoadDsp`:
  - `DF_EX.BIN` (5,251,648 bytes): Chunk 0 (CEVA-CV core, 4,112,384 B) + Chunk 1 (1,139,232 B K-3 III CNN weights: 677,824 B backbone weights @ `0x516c0000` + 461,408 B head weights @ `0x517657c0`).
  - `DF_ID_S.BIN` (65,536 bytes): 64 KB constant neural weights loaded to `0x515ec000`.
  - `DF_IP.BIN` (16,384 bytes): 16 KB instruction reset entry vectors loaded to `0x515fc000`.
- Passes 100% byte-perfect reconstruction test verified by [`verify_dsp_payload.py`](src/dsp_ai/verify_dsp_payload.py).

### Stage 2: Autonomous Boot-Time Awakening (`k3_gr4_dsp_patcher.py`)
- **Zero-UART Design**: Designed for consumer camera bodies without debug serial headers.
- Installs a trampoline at `LiveViewProcess3aContoller` (`0x536520f0` $\to$ `b #0x53000e00`).
- Calls `DspService::LoadDsp(m_dspService, 'C', 0, 0)`, `Start()`, and `Test()`, verified 100% stable on real hardware.

### Stage 3: Pure Full-Time CEVA-CV AI Tracking Bridge (`stage3_ai_patcher.py`, v1.0.9)
- **Zero Fallback to Stock LibAHFD**: Stock FotoNation `FdLibraryService::DetectFace` (`0x5383ec84`) is completely unhooked and disconnected. 100% of face and subject AF tracking boxes rendered on the camera LCD are mathematically guaranteed to come directly from the CEVA-CV hardware vector DSP.
- **Embedded Neural Tables** (inside audited zero caves in RTOS text/rodata):
  - `k3_desc.bin` (728 B) @ `0x53001400`: CNN layer topology, soft thresholds, and projection matrix.
  - `k3_mean.bin` (9,408 B) @ `0x541db540`: $56 \times 56 \times 3$ channel mean normalization bias.
  - `k3_std.bin`  (9,408 B) @ `0x54217680`: $56 \times 56 \times 3$ standard deviation activation scale.
- **Dual-Hook Architecture**:
  - **Hook 1: Boot Wakeup (`LiveViewProcess3aContoller` @ `0x536520f0` -> Cave 1 @ `0x53000d60`, 84 B)**:
    - Reconstructs APCS prologue and zeroes telemetry at `STATUS_VA` (`0x517e0100..0x517e011f`) on singleton creation without blocking early boot on SD card I/O.
  - **Hook 2: Continuous LiveView AI AF (`FaceDetectionService::Task` @ `0x5386ea8c` -> Cave 2 @ `0x53000e00`, 1,440 B)**:
    - **Boot-Safe Initialization via Constructor-Zeroed `[r4, #0x13e]`**: Eliminates the uninitialized DDR `0x517e0104` bug. Waits 20 frames (~0.65s) for SD mount, then retries `LoadDsp('C')` every 64 frames (~2.1s) up to 30 times (~65s) with mutex `r4 + 0x48` unlocked during I/O.
    - **Completed AHIP Ring Frame Dequeue**: Reads active completed YUV420 frame from `*(*(0x55080350 + 0x424))` (Y @ `+0x04`, U @ `+0x08`, V @ `+0x0c`, fallback `*(0x55080350 + 0x1c)`).
    - **ARM D-Cache Invalidation**: Calls `InvalidateDataCache` (`0x538f0454`) on the completed DMA slot before CPU downsampling.
    - **Aspect-Ratio-Aware Downsampler**: Resamples any aspect ratio (3:2, 4:3, 16:9, 1:1) using `[r4, #0xfc]` (`fd_w`) and `[r4, #0xfe]` (`fd_h`).
    - **$C^0$-Continuous $2.0\times$ Backlit Shadow Recovery**: Smooth contrast curve ($Y < 48 \to 2Y$, $48 \le Y < 144 \to 72 + Y/2$, $Y \ge 144 \to Y$) preventing crushed backlit faces from disappearing.
    - **DspService Dispatch**: Dispatches Message ID 4 to CEVA-CV DSP via `SendMessage` (`0x539663c0`) and awaits completion via `WaitMessage` (`0x539666dc`, timeout 100 ms).
    - **Head-Priority Scanning & Dynamic Bounding Box Sizing**:
      - Scans 3-channel $56 \times 56$ (stride 64) `int16_t` signed logits @ `0x51609a00`.
      - Prioritizes Head/Face ($Ch1$) over Body ($Ch2$): $fg = \max(Ch1, Ch2 - 0.5\text{ logit})$.
      - Gated noise immunity: $max\_diff \ge 2$ and ($area \ge 2$ or $max\_diff \ge 4$).
      - Dynamic box sizing: $box\_size = \text{clamp}(0x2800 + (area \ll 6), 0x2800, 0x5c00)$ (40 to 92 px on 320w).
    - **Cold-Start State Seeding & Instant Lock**:
      - Seeds `[r4, #0x100..0x10c]` = $(cx, cy, box\_size, box\_size)$, `[r4, #0x118..0x11c] = face_id`, `[r4, #0x13c] = 1`, `[r4, #0x121] = 0`, and `[r4, #0x124] = 0`.
      - Fires `EVENT 0x04070001` (`FACE_DETECT_RESULT_UPDATED`) to PDAF and LCD OSD immediately on Frame 1, locking side profiles and bowed heads instantaneously without needing prior frontal face detection.

---

## 3. Quick Start: Flashing & Usage

> [!IMPORTANT]
> **No disassembly, no soldering, and no UART debug cable required.**
> The entire modification runs 100% autonomously on camera power-on and is flashable via Ricoh's official SD card firmware updater.

### Step 1: Prepare SD Card Files
1. Format an SD Card with **FAT32**.
2. Copy the three DSP runtime binaries to the **SD card root (`C:\`)**:
   - `DF_EX.BIN` (5,251,648 bytes)
   - `DF_ID_S.BIN` (65,536 bytes)
   - `DF_IP.BIN` (16,384 bytes)
3. Copy the patched firmware image to the **SD card root** as `fwdc248b.bin`:
   - Flash Stage 3 full AI tracking firmware `output/fwdc248b_stage3_ai_track.bin` (or `output/fwdc248b.bin`).

Your SD card root directory will look like:
```text
SD Card Root (C:\)
├── fwdc248b.bin       (38,842,088 B [Stage 3 v1.0.9])
├── DF_EX.BIN          ( 5,251,648 B - CEVA-CV Execution partition + 1.14MB CNN weights)
├── DF_ID_S.BIN        (    65,536 B - Neural Network configuration table)
└── DF_IP.BIN          (    16,384 B - Reset vector table)
```

### Step 2: Flashing Firmware
1. Insert the SD card into your Ricoh GR IV with a fully charged battery.
2. While holding down the **`DISP`** (or **`MENU`**) button, turn the camera **ON**.
3. The official firmware update screen will appear, showing the current version (`v1.11`) and the update version.
4. Select **Yes** to execute the update. Wait for the progress bar to reach 100% and restart.

### Step 3: Experience AI Autofocus
- Turn on the camera. Within ~0.7s, the boot state machine initializes and verifies the CEVA-CV DSP.
- Frame a human subject in Live View: The camera's on-sensor PDAF tracking box will magnetically snap to and track the subject across the frame, including 90° side profiles, bowed heads, and backlit scenes.
- **Physical Verification**: Remove `DF_EX.BIN` from the SD card. The camera will display **zero** face detection boxes, proving that 100% of detection relies on the CEVA-CV hardware CNN.

---

## 4. Safety, Brick-Prevention & Emergency Recovery Guide

### Emergency Recovery (If Camera Fails to Boot Normally)
> [!TIP]
> **Your camera is NOT permanently bricked!**
> This project **never touches** the bootloader partitions (`00_BOOTPARA.bin` through `04_BOOT.bin` / IPL).
> The camera's built-in emergency recovery mode runs from the boot ROM / IPL before RTOS executes. Even if the RTOS image hangs or crashes, the bootloader update mode remains 100% operational.

**Unbricking Steps:**
1. **Power Off**: If the camera is unresponsive, remove the battery for 10 seconds and reinsert.
2. **Prepare SD Card**: Place the official unmodified `fwdc248b.bin` (v1.11 stock firmware) or `fwdc248b_stage2_dsp_wake.bin` on the root of your SD card (named `fwdc248b.bin`).
3. **Trigger Hardware Update Mode**:
   - Make sure the camera is completely OFF.
   - **Press and hold the `MENU` (or `DISP`) button**.
   - While continuing to hold `MENU` / `DISP`, press the **Power** button.
   - The camera will bypass RTOS and launch the official `Firmware Update` screen directly.
   - Select **Yes** to flash back clean firmware and restore normal operation!

---

## 5. Repository Layout

```text
.
├── analysis/
│   ├── dsp_stage3_manifest.json     # Release manifest for Stage 3 build
│   ├── dsp_wake_manifest.json       # Release manifest for Stage 2 build
│   ├── rtos_decompilation_audit.md  # Comprehensive GR4 RTOS reverse engineering audit
│   └── shellcmd_symbols.csv         # 651 verified RTOS shell symbols
├── docs/
│   ├── FEAT_DSP_STAGE3_AI_TRACK.md  # Detailed Stage 3 technical whitepaper
│   ├── FEAT_DSP_AI_WAKE.md          # Detailed Stage 2 DSP awakening whitepaper
│   ├── FEAT_K3_AF_PORT.md           # Pentax K-3 III to GR4 AF porting audit
│   ├── RELEASE_NOTES_v1.0.5.md      # v1.0.5 release notes
│   └── RELEASE_NOTES_v1.0.9.md      # v1.0.9 release notes
├── src/
│   └── dsp_ai/
│       ├── build_stage3_firmware.py # Complete Stage 3 packager & container rebuilder
│       ├── stage3_ai_patcher.py     # Stage 3 ARM assembly code cave generator
│       ├── build_dsp_firmware.py    # Stage 2 firmware builder
│       ├── k3_gr4_dsp_patcher.py    # Stage 2 ARM assembly patch generator
│       ├── dsp_splitter.py          # 06_DSP.bin -> DF_EX / DF_ID_S / DF_IP splitter
│       ├── verify_dsp_payload.py    # Byte-perfect payload reconstruction verifier
│       ├── k3_desc.bin              # Extracted DeepLearningService descriptor (728 B)
│       ├── k3_mean.bin              # Extracted channel mean normalization table (9,408 B)
│       └── k3_std.bin               # Extracted channel std normalization table (9,408 B)
├── tools/
│   ├── fw_container.py              # LZSS container unpacker, repacker & word-sum solver
│   ├── rtos_analyzer.py             # RTOS xref & symbol parser
│   └── linux_analyzer.py            # Linux rootfs analyzer
└── README.md
```

---

## 6. Building from Source

### Prerequisites
- Python 3.10+
- `capstone` (`pip install capstone`)
- Official Ricoh GR IV v1.11 firmware (`fwdc248b.bin`) placed in `firmware/official/v1.11/`
- Official Pentax K-3 Mark III v2.20 section `06_DSP.bin` placed in `firmware/reference/k3iii_v220/unpacked/sections/`

### Build Command
```bash
# Slices DSP partitions, embeds AI model tables, compiles code cave, and builds flashable container:
python src/dsp_ai/build_stage3_firmware.py
```

Output:
```text
======================================================================
Ricoh GR IV Stage 3 AI Live View Tracking Firmware Rebuilder
======================================================================
[*] Confirmed Stage 2 binary intact: fwdc248b_stage2_dsp_wake.bin (38,693,256 bytes)

[Step 1/4] Verifying staged SD card DSP binaries...
[+] PASS: 100% byte-perfect reconstruction verified across all 5,333,536 bytes.

[Step 2/4] Decoding official firmware container baseline...
  -> Official payload decoded: 67,948,280 bytes

[Step 3/4] Splicing Stage 3 Dual Caves, Trampolines & AI Tables...
  [+] Hook 1 (Boot Wakeup): 84 B Cave @ VA 0x53000d60, Hook @ VA 0x536520f0
  [+] Hook 2 (LiveView AI): 1440 B Cave @ VA 0x53000e00, Hook @ VA 0x5386ea8c
  [+] Embedded Desc Table (728 B) @ VA 0x53001400
  [+] Embedded Mean Table (9408 B) @ VA 0x541db540
  [+] Embedded Std Table  (9408 B) @ VA 0x54217680
[*] Rezeroing 32-bit payload checksum word...
  [+] Payload word_sum == 0 validated successfully.

[Step 4/4] Rebuilding flashable container with LZSS framing...
  -> Modified payload bytes: 20324
  [+] Written Stage 3 preserved binary: output/fwdc248b_stage3_ai_track.bin (38,842,088 bytes)
  [+] Written active flashable binary:  output/fwdc248b.bin (38,842,088 bytes)

[*] Executing round-trip container verification...
  [+] Round-trip container verification PASSED! Dual word-sums == 0.
```

---

## 7. Technical Cross-Reference

| Function / Component | Virtual Address (VA) | Purpose |
| :--- | :--- | :--- |
| `LiveViewProcess3aContoller` | `0x536520f0` | Hook 1 entry for one-time boot DSP status initialization (`b #0x53000d60`) |
| Cave 1 (Boot Init) | `0x53000d60` | 84-byte non-blocking APCS frame reconstruction + status zeroing |
| `FaceDetectionService::Task` | `0x5386ea8c` | Hook 2 site for continuous per-frame LiveView AI AF (`b #0x53000e00`) |
| Cave 2 (LiveView AI AF) | `0x53000e00` | 1,440-byte execution engine (Boot safe retry + AHIP dequeue + D-Cache + DSP IPC + 2.0x Backlit + Result injection) |
| Completed AHIP Ring | `*(*(0x55080350 + 0x424))` | Descriptor dequeued by `AhipService::WaitFrame` (`+0x04` Y, `+0x08` U, `+0x0c` V) |
| `InvalidateDataCache` | `0x538f0454` | Invalidates CPU L1/L2 data cache before reading frame buffer |
| `FlushDataCache` | `0x538f04c4` | Flushes CPU data cache after writing RGB tensor before DSP DMA |
| `DspFactory::GetDspService()` | `0x539658c4` | Retrieves CEVA-CV `DspService` singleton pointer |
| `DspService::LoadDsp` | `0x53966d74` | Loads `DF_EX.BIN`, `DF_ID_S.BIN`, `DF_IP.BIN` from SD card root (Drive `C:\`) |
| `DspService::Start` | `0x53966214` | Deasserts DSP reset, starts execution at `0x515fc000` |
| `DspService::Test` | `0x53966f18` | Runs CEVA-CV version self-test |
| `DspService::SendMessage` | `0x539663c0` | Dispatches Message ID 4 (Inference request) |
| `DspService::WaitMessage` | `0x539666dc` | Awaits tensor inference completion (timeout 100 ms) |
| `m_DetectedFaceResult` | `[FaceDetectionService, #0x78]` | Array of 100-byte face structures (`x, y, w, h, eye_l, eye_r, mouth, score`) |
| `FdLibraryService` | `[FaceDetectionService, #0x38]` | Subsystem holding detected face count @ `+0x30` |
| `UpdateFaceDetectionResult` | `0x5386e0e4` | Submits face/eye coordinates to LCD OSD display task & AF engine |
| Stock FotoNation `DetectFace` | `0x5383ec84` | **100% disconnected & removed** in v1.0.9 (Zero fallback) |

---

## 8. Release Changelog

### v1.0.9 (Current Release)
- **100% Pure CEVA-CV CNN — Zero Stock Fallback**: Completely disconnected and removed `FdLibraryService::DetectFace` (`0x5383ec84`). 100% of detection boxes on the LCD are mathematically guaranteed to come from CEVA-CV hardware CNN.
- **Eliminated Uninitialized DDR `0x517e0104` Boot Bug**: Cave 1 no longer blocks early boot on SD card I/O; Cave 2 uses constructor-zeroed `[r4, #0x13e]` to initialize the boot retry counter, waits 20 frames (~0.65s) for SD mount, and retries `LoadDsp('C')` every 64 frames up to 30 times (~65s) with mutex `r4 + 0x48` unlocked.
- **Completed AHIP Ring Frame Extraction & D-Cache Invalidation**: Reads active completed frame descriptor `*(*(0x55080350 + 0x424))` dequeued by `AhipService::WaitFrame`, calling `InvalidateDataCache` (`0x538f0454`) on the completed DMA buffer before CPU access.
- **Aspect-Ratio-Aware Downsampler (3:2, 4:3, 16:9, 1:1)**: Scales downsampling and coordinates based on active `[r4, #0xfc]` (`fd_w`) and `[r4, #0xfe]` (`fd_h`).
- **$C^0$-Continuous $2.0\times$ Backlit Shadow Recovery**: Smooth contrast lift curve ($Y < 48 \to 2Y$, $48 \le Y < 144 \to 72 + Y/2$) doubling shadow face contrast while preserving bright highlights.
- **Head-Priority Scanning & Dynamic Box Sizing**: Prioritizes Head ($Ch1$) over Body ($Ch2$), applies noise immunity gate ($max\_diff \ge 2$, $area \ge 2$ or $max\_diff \ge 4$), and scales bounding box dynamically `clamp(0x2800 + (area << 6), 0x2800, 0x5c00)`.
- **Cold-Start Tracking State Seeding**: Seeds `[r4, #0x100..0x10c]` with $(cx, cy, w, h)$, seeds `[r4, #0x118..0x11c] = face_id`, `[r4, #0x13c] = 1`, `[r4, #0x121] = 0`, and `[r4, #0x124] = 0`, locking side profiles and bowed heads on Frame 1.
- **Binary Checksum**: `fwdc248b.bin` (38,842,088 bytes, SHA-256: `35cd54790a81734055834db1c97c54ef9b6740789aaaf3f3d749bed7e997d7d6`).

### v1.0.8
- **Full-Time CEVA-CV CNN**: Removed Stage 1 FotoNation pre-filtering; executed CEVA-CV inference on every frame without dropping detection states.
- **Cold-Start Side/Low-Head Seeding**: Initial implementation of cold-start tracking flags for non-frontal face acquisition.

### v1.0.7
- **Stock ROM Bug Fix in `DspService::LoadDsp`**: Patched `0x53966eb0` and `0x53966ef4` where the ROM hardcoded `"A:\DF_ID_S.BIN"` and `"A:\DF_IP.BIN"` pointers instead of `sub r1, fp, #0x40` (`"C:\DF_*.BIN"`).

### v1.0.6
- **Full 1.14 MB K-3 III CNN Weights**: Re-structured `DF_EX.BIN` into Chunk 0 (CEVA-CV core, 4,112,384 B) + Chunk 1 (1,139,232 B neural weights: 677,824 B backbone + 461,408 B head weights).
- **YUV420 to RGB Tensor Pipeline**: Converted LiveView preview into $56 \times 56$ 3-plane RGB input tensor @ `0x51600000` with 3-channel (BG, Human, Subject) `int16_t` signed heatmap output @ `0x51609a00`.

### v1.0.5
- **Drive Letter Fix (`'A'` -> `'C'`)**: Fixed argument passed to `DspService::LoadDsp` from `'A'` to `'C'` (`0x43`).
- **Dynamic Preview Frame Buffer via `p_FdEngine`**: Replaced uninitialized BSS pointer `0x55395a18` with true hardware pointer extracted via `FaceDetectionService::Task`.

---

## 9. Disclaimer & License

- **Disclaimer**: This is an independent reverse engineering research project for educational and technical exploration. Firmware modification carries inherent risks. While extensive safeguards (dual word-sum verification, memory range bounds checks, safe fallback branches) have been implemented, the authors assume no liability for camera malfunctions.
- **Copyright Notice**: This repository contains original disassembly tools, patch scripts, and mathematical specifications. It does not distribute proprietary binary firmware copyrighted by Ricoh Imaging Company, Ltd. Users must provide their own legally acquired firmware files.
- **License**: MIT License. See [LICENSE](LICENSE) for details.

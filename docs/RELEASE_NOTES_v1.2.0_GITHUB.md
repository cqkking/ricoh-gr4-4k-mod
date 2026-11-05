# Ricoh GR IV 4K UHD Video Recording Mod v1.2.0 Release

We are excited to announce the release of **v1.2.0** for `ricoh-gr4-4k-mod`, bringing major optical and stabilization breakthroughs to the Ricoh GR IV in-camera 4K UHD video recording pipeline, completely rebased on the latest official **Ricoh GR IV v1.20** firmware baseline (`fwdc248b.bin`, build date `2026/09/08 15:30:31`).

This release directly addresses all real-world user feedback from the v1.1.0 release: eliminating the 1.35x optical magnification/crop (restoring full 28mm wide-angle FOV) and completely resolving the horizontal panning vertical stripe corruption caused by an underlying line buffer division bug in the electronic stabilization subsystem.

---

## 🌟 Major Highlights & Breakthroughs in v1.2.0

### 1. 100% Native APS-C Readout (Zero Crop / True 28mm Equivalent Wide Angle)
- **Problem**: In previous builds, 4K selected K-3 III's Sensor Modes 5 & 6, which engaged CIS Mode `0x12` (a 1.35x center crop `4592×2584` window), resulting in significant magnification and losing the GR's iconic 28mm street framing.
- **Solution**: Remapped Sensor Modes 5 (24p) & 6 (30p) in jump table `0x536717e0` to **CIS Mode 3** (`0x53671a68`). CIS Mode 3 reads out the **full 26MP APS-C sensor width (6240×3510)** with 3×3 binning.
- **Result**: 4K 24p and 30p now share the **exact 1:1 identical field of view as 1080p 60p** (full 28mm wide angle, zero optical crop).

### 2. Elimination of Movie Shake Reduction (EIS) & Panning Stripe Corruption
- **Root Cause**: In `LiveViewProcess.cpp` (`0x5365aa94..0x5365ab34`), the 4K Active Width calculation contained an architectural bug (`0x5365aae4: rsbne r4, r6, r8, lsr #1`) that mistakenly divided 3840 by 2, storing halved width (`1920`) into the line buffer register. Horizontal panning shifted the gyro EIS window past 1920 pixels into invalid DMA line memory, causing corrupted vertical stripes to intrude from the edges (faster pan = worse intrusion). Vertical motion was unaffected because height was never halved.
- **Solution**:
  - Replaced `0x5365aae4` with `movne r4, r8` (full 3840 active width, zero margin subtraction).
  - Bypassed `SetupMovieShakeReduction` at both its caller (`0x5365ab34`) and its function entry (`0x538b7b3c`) with `bx lr` immediate returns.
- **Result**: Electronic stabilization gyro shifting and margin cropping are completely disabled. Panning horizontally or tilting vertically is 100% smooth, clean, and artifact-free!

### 3. Rebased onto Official Ricoh GR IV v1.20 Baseline
- Base firmware upgraded from v1.11 to official v1.20 (`7563d7e462f0c53b6ab2fbab7cdfbbb57151a41192ee82f4f3a2108f9d77650d`).
- Accommodated expanded RTOS section (+232 KB) and re-anchored all patch offsets:
  - Gate: `LiveViewDebug::IsDebug4KMovie` @ `0x538AD500`
  - Defect A (24p/30p 4K buffer & `is4K=1` flag): `0x53652E70..0x53652E9C`
  - Defect B (`m_is4KLiveView` offset `[r3, #0x564]`): `0x5365C7C8`
  - Defect C (Plan 4 & 5 -> Plan 3 `0x5366E238`): `0x5366E180`
  - FOV Alignment (Modes 5/6 -> CIS Mode 3): `0x536717EC`
  - Width fix & EIS bypass: `0x5365AAE4`, `0x5365AB34`, `0x538B7B3C`

### 4. Strict Dual 32-bit Word-Sum Checksums & Safety Guarantees
- Both the decoded inner payload (69,632,740 bytes) and outer flash container (39,002,112 bytes) strictly balance to little-endian 32-bit `word_sum == 0x00000000`, 100% passing camera bootloader self-checks.

---

## 📦 Firmware Binary & Checksums

| File | Size (Bytes) | SHA-256 Checksum | Dual Word-Sum | Description |
| :--- | :--- | :--- | :---: | :--- |
| **`fwdc248b.bin`** | 39,002,112 | `ef67b24de574bbd28a6808223b4a02ad3f040ffda597d11d3a1e551b6668eab0` | `0x00000000` | v1.20 4K UHD H.264 Standard Edition Flashable Firmware |

---

## 📷 Flashing & Quick Start Instructions

1. Format an SD card (FAT32 or exFAT, V30 / U3 speed class recommended);
2. Download `fwdc248b.bin` from this release and copy it directly to the SD card root directory (`/fwdc248b.bin`);
3. Ensure camera battery is charged (80%+ recommended) and power off camera;
4. **Hold down the [MENU] button and press [POWER] to boot into firmware update mode**;
5. Follow the on-screen prompt to update firmware to **1.20**;
6. Switch the top mode dial to Movie mode, select `24p` or `30p` in the menu, and press shutter to record pristine 4K UHD video with true 28mm wide-angle framing!

---

*Disclaimer: This is an open-source community reverse-engineering project and is not affiliated with or endorsed by Ricoh Imaging Company, Ltd. Flash and use at your own risk.*

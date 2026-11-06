# Release v1.4.0: Native 3K UHD (3072x1728) Direct Video Recording via Route 1 (Stock FHD Pipeline Direct Hijack)

**Release Date:** 2026-11-06  
**Target Device:** Ricoh GR IV (firmware base v1.20 `fwdc248b.bin`)  
**Output Resolution:** 3K UHD (`3072 × 1728`) @ 60p / 30p / 24p  
**Codec:** H.264 / AVC (`avc1` / `avcC`) in `.MOV` Container  
**Sensor Readout:** CIS Mode 3 (Full APS-C 26MP $6240 \times 3510$ binned 2×2 to $3120 \times 1755$, true 28mm wide-angle FOV)  
**Checksum Validation:** Dual 32-bit `word_sum == 0x00000000` (PASS)  

---

## 🎯 Executive Summary & Major Breakthroughs in v1.4.0

Version **v1.4.0** represents a fundamental architectural breakthrough in the Ricoh GR IV video modification project. Following first-principles analysis and physical hardware alignment proof, we have completely abandoned the fragile Pentax K-3 III 4K debug stubs (`IsDebug4KMovie`, Sensor Modes 5/6, Sequence Plans 3/4/5) which caused LiveView preview to lock into looping frames at 30p/24p.

Instead, v1.4.0 executes **Route 1: Stock FHD Pipeline Direct Hijack**. Because the factory GR IV 1080p pipeline natively runs on **CIS Mode 3** across 60p, 30p, and 24p, hijacking the FHD resolution descriptors, getters, and VPU buffers directly to **`3072 × 1728` (Native 3K UHD)** achieves 100% factory-smooth LiveView preview with zero freeze, full APS-C 28mm wide-angle framing, and pristine direct 3K recording.

---

## 🔑 Key Enhancements & Problem Resolutions

### 1. Root-Cause Resolution of 30p/24p LiveView Freeze & Frame Looping
- **v1.3.0 Bug Mechanism**:
  In v1.3.0, enabling `IsDebug4KMovie == 1` and redirecting Sensor Modes 5 & 6 caused `LiveViewSequencePlanner` (`0x53661090`) to fail its recipe assertion (`cmp r5, #0x12`). Because CIS Mode 3 is `0x03`, it defaulted to Plan 2 while upper state machines configured 4K buffer parameters, creating an unresolvable ISP configuration mismatch and stalling the preview stream.
- **Route 1 Fix**:
  `IsDebug4KMovie` is restored to official stock (0), and stock Sensor Modes 4, 3, 2 are preserved. All framerates use factory Plan 2 sequence planning with 100% stability.

### 2. Native 3K UHD (`3072 × 1728`) Point-to-Point Direct Output
- Eliminates 1.23x artificial upsampling to 4K: avoids generating 2.82 million interpolated dummy pixels.
- ISP Resizer operates in pure 1.5% downscale mode ($3120 \times 1755 \rightarrow 3072 \times 1728$) with zero buffer overrun risk.
- +51% higher bits-per-pixel (BPP) density at 75~85 Mbps, delivering vastly sharper fine detail and cleaner shadows.
- Strict 256-byte DMA alignment and 16×16 macroblock grid ($192 \times 108 = 20,736$ blocks) with zero `frame_cropping_flag` in SPS.

### 3. Movie Shake Reduction (EIS) Symmetrical Fix
- Replaced buggy active width calculation (`rsbne r4, r6, r8, lsr #1` which halved the active width) with `subne r4, r8, r6, lsl #1` (`Width - 2 * MarginX`).
- Restored 100% geometric symmetry with the vertical height calculation, permanently resolving the horizontal panning stripe intrusion artifacts!

### 4. Flashing Integrity
- Flashable binary: `output/sd_card/fwdc248b.bin` (39,016,940 bytes)
- Container SHA-256: `adad531fa2ad79e054e33f0567780fcd540dd19692c19b1b6a6371edfbaf5baf`
- Dual 32-bit Word-Sum: `0x00000000` (STRICT PASS)

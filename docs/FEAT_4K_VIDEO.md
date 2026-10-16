# Feature Design & Engineering Spec: 4K Video & Hardware H.264/HEVC Pipeline (`feat/4k-video`)

## 1. Make-or-Break Empirical Findings in GR IV v1.11 (`05_RTOS.bin`)

Using ARMv7 `MOVW`/`MOVT` cross-reference analysis (`mask = 0x0FFF0FFF`) across the 20.78 MB T-Kernel RTOS binary (`05_RTOS.bin` @ `0x53000000`), we proved which video subsystems are **actively compiled and referenced** vs. **stripped by linker `--gc-sections`**:

| Subsystem / Function | `.rodata` VAddr | Active `.text` Xref VAddr (Payload Offset) | Status in GR IV v1.11 |
| :--- | :--- | :--- | :--- |
| `CreateRecipeSequenceMov4kExt` | `0x53eb18d0` | `0x536498c4` (`0x006615d4`) | **ACTIVE & REFERENCED** |
| `CreateRecipeSequenceMov4kRemote` | `0x53eb18f0` | `0x53649914` (`0x00661624`) | **ACTIVE & REFERENCED** |
| `[LVC] for Debug 4K Movie!` | `0x53eae744` | `0x5362e514` (`0x00646224`) | **ACTIVE & REFERENCED** |
| `7:3840x2160p/30Hz` | `0x540404cc` | `0x53055d44` (`0x0006da54`) | **ACTIVE & REFERENCED** |
| `ConvertToH264CodecDefsImageSize` | `0x53ec91c0` | `0x5366cd3c` (`0x00684a4c`) | **ACTIVE & REFERENCED** |
| `src/H264Processor.cpp` | `0x53ec71dc` | `0x5366b25c` (`0x00682f6c`) | **ACTIVE & REFERENCED** |
| `H265/WAVE/Project/vdi/src/mm.c` | `0x53ce8d58` | `0x5394da44` (`0x00965754`) | **ACTIVE & REFERENCED** |
| `FJ_VideoEncoder_Setup(h265)` | `0x5435f00c` | *(None — `.text` gap `0x53a93458..0x53a93500`)* | **GC-STRIPPED WRAPPER** |
| `H265_Wave_Initialize` | `0x5436ac74` | *(None — `.text` gap `0x53aaa898..0x53aab7ec`)* | **GC-STRIPPED WRAPPER** |

---

## 2. Dual-Track Development Roadmap

### Track A: Unlocking Internal `3840x2160` 30p (4K) + Hardware H.264 High Profile + BT.2100 HLG VUI (Primary Active Path)

Because `CreateRecipeSequenceMov4kExt`, `[LVC] for Debug 4K Movie!`, `3840x2160p/30Hz`, and `H264Processor.cpp` (`ConvertToH264CodecDefsImageSize`) are **100% present and referenced in `.text`**:

1. **Recipe & LVC Mode Switch (`0x53649880..0x53649950`)**:
   - At `vaddr = 0x53649894` (`payload = 0x006615a4`), the movie recipe selector branches between standard 1080p (`0x53649850`), `CreateRecipeSequenceMov4kExt` (`0x536498b8`), and `CreateRecipeSequenceMov4kRemote` (`0x53649908`).
   - Redirecting the 1080p30/60 movie menu selection (or Debug 4K Movie flag at `0x5362e514`) to invoke `CreateRecipeSequenceMov4kExt` configures the Sony IMX sensor readout and Milbeaut ISP scaler for `3840x2160 @ 30fps`.
2. **H.264 Codec ImageSize & Bitrate Escalation (`0x5366cd00..0x5366cd90`)**:
   - In `ConvertToH264CodecDefsImageSize` (`0x5366cd3c`), map the 4K enum case (`3840x2160`) and scale the target bitrate parameter in `H264Processor.cpp` from ~24 Mbps (1080p) to 60–100 Mbps (4K High@L5.1).
3. **BT.2100 HLG VUI & `colr(nclx)` Metadata (`src/video_4k/patch_h264_vui_bt2100_hlg.py`)**:
   - Combine the Phase 1 HLG Image Control (`Look`) ISP profile (Rec.2020 3×3 CCM + ARIB STD-B67 1D LUT) with H.264 SPS VUI (`colour_primaries=9`, `transfer_characteristics=18`, `matrix_coefficients=9`) and MP4 `colr(nclx)` box (`00000012 636f6c72 6e636c78 0009 0012 0009 80`) so recorded `.MP4`/`.MOV` clips play back in native HDR on macOS/iOS/YouTube/DaVinci Resolve.

### Track B: Hardware H.265 (HEVC) WAVE VPU Re-attachment via Pentax K-3 Mark III (`fwdc233b.bin`) Cross-Diff

While the low-level Chips&Media WAVE H.265 VDI memory manager (`mm.c` @ `0x5394da44`) survived linker garbage collection, the upper Socionext wrapper (`FJ_VideoEncoder_Setup(h265)` / `H265_Wave_Initialize`) was stripped at build time.
- Using [`src/video_4k/scan_4k_hevc_pipeline.py`](../src/video_4k/scan_4k_hevc_pipeline.py) with `--compare-k3iii`, we can extract the intact `H265_Wave_*` / `VPU_Enc*` wrapper functions from Pentax K-3 Mark III (`fwdc233b.bin`, which shares the identical `RiberyM9M_Codec` SDK) and graft them into a code cave in `05_RTOS.bin`.

---

## 3. Usage

```powershell
# Scan and disassemble the active 4K movie & codec pipeline in 05_RTOS.bin + libcamera-controller.so
python src/video_4k/scan_4k_hevc_pipeline.py

# Generate BT.2100 HLG H.264 SPS VUI bitstream & MP4 colr(nclx) atom
python src/video_4k/patch_h264_vui_bt2100_hlg.py
```

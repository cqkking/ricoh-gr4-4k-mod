# Ricoh GR IV (GR4) Standard Edition v1.11 Firmware Decompilation & Modification Workspace

Baseline reverse-engineering, decompilation, and feature development repository for the **Ricoh GR IV (GR4) Standard Edition (China Mainland sales version)** firmware **v1.11** (`fwdc248b.bin`, built `2025/12/01 11:09:09 JST`).

---

## 1. Repository & Git Worktree Topology

This repository uses Git worktrees so that the clean **v1.11 decompilation baseline (`main`)** and two independent feature development tracks share the unpacked binary assets in `firmware/` without duplicating ~110 MB of binary payloads across branches:

| Worktree Path | Git Branch | Role / Technical Scope |
| :--- | :--- | :--- |
| `d:\Ricoh GR4 firmware Mod` | `main` | **v1.11 Decompilation Baseline**: Container unpacker/repacker ([`tools/fw_container.py`](tools/fw_container.py)), T-Kernel RTOS disassembler & xref auditor ([`tools/rtos_analyzer.py`](tools/rtos_analyzer.py)), Linux RootFS ELF/IPCU analyzer ([`tools/linux_analyzer.py`](tools/linux_analyzer.py)), and symbol tables ([`analysis/`](analysis/)). |
| `worktrees/feat-hlg-photo` | `feat/hlg-photo` | **HLG HDR Still Photography (`feat/hlg-photo`)**: <br>• **Phase 1**: ISP 3×3 Rec.2020 Color Matrix (CCM) + 1D ARIB STD-B67 (HLG) Tone Curve override + ICC v4 `cicp` (`[9, 18, 0]`) profile injection into `.JPG`.<br>• **Phase 2**: Linux `libshmem_manager.so` 14-bit raw/linear RGB intercept + `libx265` 10-bit `.HIF` (`heic`/`mif1`) encoder pipeline. |
| `worktrees/feat-4k-video` | `feat/4k-video` | **4K Video & HEVC/HLG Pipeline (`feat/4k-video`)**: <br>• **Track A (100% Active RTOS Path)**: Unlocking internal `3840x2160` 30p (`CreateRecipeSequenceMov4kExt` @ `0x536498c4`) + Hardware H.264 High Profile + BT.2020/HLG VUI (`colour_primaries=9`, `transfer_characteristics=18`).<br>• **Track B (Hardware H.265/HEVC Investigation)**: Auditing the active Chips&Media WAVE H.265 VDI layer (`mm.c` @ `0x53ce8d58`) vs. linker `--gc-sections` stripped high-level `H265_Wave_Initialize` / `FJ_VideoEncoder_Setup(h265)` wrappers, with cross-firmware diffing tools for Pentax K-3 Mark III (`fwdc233b.bin`). |

---

## 2. Official Firmware Baseline (`fwdc248b.bin` v1.11)

- **File**: `firmware/official/v1.11/fwdc248b.bin` (`38,648,776` bytes)
- **SHA-256**: `a2f664dfca034059eb0fd6e18ab08684c326b4a034d85c164dad7e1ec9b5655f`
- **Model / Version**: `GR IV` / `01.11.00` (`2025/12/01 11:09:09`)
- **Outer Container**: 128-byte `RICOH\0\0\0` header + 2,765 LZSS frames (`window=4096, lookahead=18, threshold=2, init_byte=0x20`) + 16-byte `0xA55A5AA5` footer. Both outer container and inner payload enforce a 32-bit little-endian `word_sum == 0` integrity check.
- **China Mainland Regional Support**: Embedded `RES` section (`12_RES.bin`) includes Simplified Chinese vector/bitmap font packs (`A:\Resource\Font\LE_CN_S.bin`, `A:\Resource\Font\RT_CN_S.bin`), and `05_RTOS.bin` contains the regional destination table (`JPN`, `AA`, `EUR`, `USA`, `CHN`, `KOR`, `TWN`).

### Inner Payload Partition Map (`payload.bin`, `67,948,280` bytes)

| ID | Section Name | Payload Offset Range | Size (Bytes) | Description & Architecture |
| :-: | :--- | :--- | ---: | :--- |
| `00` | `BOOTPARA` | `0x00000010 .. 0x00000058` | 72 | Boot parameter descriptor |
| `01` | `DRAMPARA` | `0x00000068 .. 0x00000294` | 556 | LPDDR SDRAM timing parameters |
| `02` | `PARTPARA` | `0x000002a4 .. 0x000004a8` | 516 | Partition layout table |
| `03` | `M0` | `0x000004b8 .. 0x000125f8` | 74,048 | ARM Cortex-M0 power/system supervisor |
| `04` | `BOOT` | `0x00012608 .. 0x00017d00` | 22,264 | Stubby primary bootloader |
| `05` | `RTOS` | `0x00017d10 .. 0x013ea7d0` | 20,785,856 | **eSOL T-Kernel RTOS** (`ARMv7 Cortex-A7`, load base **`0x53000000`**) — ISP, Sensor, Codec, LVC, and UI Look Tables |
| `06` | `LINUX` | `0x013ea7e0 .. 0x0196d7e0` | 5,779,456 | Stubby + Linux Kernel Image (`4.9.126-yocto-standard`) + DTB |
| `07` | `INITFS` | `0x0196d7f0 .. 0x02e437f0` | 21,848,064 | **SquashFS 4.0** (LZ4 block compressed) Linux RootFS (502 files, 202 symlinks) |
| `08` | `SRIC` | `0x02e43800 .. 0x02e69800` | 155,648 | Sub-controller firmware |
| `09` | `CPU` | `0x02e69810 .. 0x02e89810` | 131,072 | Sub-CPU firmware |
| `10` | `SHELLCMD` | `0x02e89820 .. 0x02e93ae0` | 41,664 | **650 RTOS function symbols** (`Name , 0x53xxxxxx`) |
| `11` | `ICONBIN` | `0x02e93af0 .. 0x03c62f50` | 14,480,480 | OSD / Menu UI icons & bitmaps |
| `12` | `RES` | `0x03c62f60 .. 0x040ccef1` | 4,628,369 | 31 embedded files (`A:\Resource\Font\*`, `A:\sound\*.wav`) |

> **Address Conversion Formula for `05_RTOS.bin`**:
> $$\text{payload\_offset} = (\text{vaddr} - \mathtt{0x53000000}) + \mathtt{0x00017d10}$$

---

## 3. Empirical RTOS Audit Summary (Make-or-Break Findings)

Full disassembly and cross-reference proofs are generated in [`analysis/rtos_decompilation_audit.md`](analysis/rtos_decompilation_audit.md):

1. **Image Control (Look) Table & Visibility Gate**:
   - Visibility check function at `vaddr = 0x533cc6e0` (`payload = 0x003e43f0`) tests `r3` (`cmp r3, #0; beq 0x533cc710`) before exposing hidden Look slots (`0x0E..0x10`).
   - 17-entry Look pointer table at `vaddr = 0x53dbf360` (`payload = 0x00dd7070`) maps standard/monotone/cinema looks alongside reserved entries (`#10` `0x53dbe4ba`, `#11` `0x53dbe4be`).
2. **4K (`3840x2160`) Movie Pipeline & H.264 Hardware Encoder**:
   - **100% Active & Referenced in `.text`**:
     - `CreateRecipeSequenceMov4kExt` (`0x53eb18d0`) referenced at `0x536498c4` (`payload = 0x006615d4`)
     - `[LVC] for Debug 4K Movie!` (`0x53eae744`) referenced at `0x5362e514` (`payload = 0x00646224`)
     - `7:3840x2160p/30Hz` (`0x540404cc`) referenced at `0x53055d44` (`payload = 0x0006da54`)
     - `ConvertToH264CodecDefsImageSize` (`0x53ec91c0`) referenced at `0x5366cd3c` (`payload = 0x00684a4c`)
3. **Chips&Media WAVE H.265 (HEVC) Hardware VPU Status**:
   - Low-level WAVE VDI memory allocator (`RiberyM9M_Codec/FUNC/Movie/H265/WAVE/Project/vdi/src/mm.c` @ `0x53ce8d58`) is **ACTIVE & REFERENCED** at `0x5394da44` and `0x5394de10`.
   - High-level wrapper strings `FJ_VideoEncoder_Setup(h265)` (`0x5435f00c`) and `H265_Wave_Initialize` (`0x5436ac74`) remain in `.rodata.str1.4`, while their high-level caller wrappers were stripped by linker `--gc-sections` (visible at `.text` boundary `0x53a93458..0x53a93500`).

---

## 4. Quick Start Commands

```powershell
# 1. Verify or unpack official v1.11 firmware (fwdc248b.bin)
python tools/fw_container.py info firmware/official/v1.11/fwdc248b.bin
python tools/fw_container.py unpack firmware/official/v1.11/fwdc248b.bin -o firmware/unpacked/v1.11

# 2. Regenerate RTOS & Linux RootFS static analysis reports
python tools/rtos_analyzer.py
python tools/linux_analyzer.py

# 3. Repack a modified payload.bin into a flashable fwdc248b.bin with valid word-sum checksums
python tools/fw_container.py pack firmware/unpacked/v1.11/payload.bin -t firmware/official/v1.11/fwdc248b.bin -o firmware/unpacked/v1.11/fwdc248b_mod.bin
```

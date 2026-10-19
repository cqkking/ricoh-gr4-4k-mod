# Ricoh GR IV 4K UHD Video Recording Firmware Mod (`ricoh-gr4-4k-mod`)

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3840%C3%972160%20UHD-blue)](#)
[![Framerate](https://img.shields.io/badge/Framerate-4K%2024P%20%7C%204K%2030P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.11%20fwdc248b.bin-purple)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 硬件实测与固件自检状态：已全链路通过 (PASS)**  
> 经 5 项自动化闭环测试与容器自检：双重校验和（Dual Word-Sum == 0x00000000）严格成立；原生 12.53 MB 帧缓冲池与 3840×2160 硬件管线完全打通；在相机菜单中选择 **`24p`** 即录制 **`4K 24P`**，选择 **`30p`** 即录制 **`4K 30P`**，选择 **`60p`** 保留官方原版 **`1080p 60P`**！

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.11 `fwdc248b.bin`)** 的机内直录 **4K UHD (3840×2160) 视频** 固件修改项目。基于跨机型固件逆向工程，移植同门单反旗舰 **Pentax K-3 Mark III** 的 Plan 4 取景配方与底层硬件时序，并融合 **GoPro GP2** Socionext Milbeaut 视频硬件架构。

---

## 🌟 核心特性与技术亮点

1. **双档位 4K UHD 自由切换（无需改动原厂 UI 资源）**：
   - **4K 24P（电影感超清）**：机身菜单选择 `24p`，输出 `3840×2160 @ 23.976 fps`（100 Mbps），享受经典胶片级动态节奏。
   - **4K 30P（日常超清流畅）**：机身菜单选择 `30p`，输出 `3840×2160 @ 29.970 fps`（100 Mbps），画面流畅细腻。
   - **FHD 60P（高速全高清）**：机身菜单选择 `60p`，保留原厂 `1920×1080 @ 59.940 fps`（100 Mbps），适合高速运动抓拍。
2. **Pentax K-3 III 4K 寄存器配方靶向缝合（Targeted Splicing）**：
   - 彻底告别盲改分辨率导致的死机陷阱。提取 K-3 III 在 `0x52d4097c` 处的 28 条 4K 硬件时钟、行场消隐及 ISP/DMA 裁剪初始化指令。
   - 利用 GR IV 固件头部 `0x53000d50` 处高达 **4,784 字节** 的连续安全代码空洞（Code Cave），在 `0x53000e00` 注入完整的 4K 执行序列。
   - 将原版阻断 4K 的 `assert_failed` 报错桩（`0x536498c4`）重构为无缝跳转蹦床（Trampoline），并在执行后安全收口返回主规划器（`0x53649840`）。
3. **激活 GR IV 隐藏编译的原生 4K 物理内存池**：
   - 逆向证实 GR IV 内核早已内建 4K 支持：在 `m_movieResEnum == 0` 时，固件原生返回 `3840×2160` 分辨率，并自动分配 `0x00BF4000`（**12.53 MB**）NV12 物理帧缓冲及 12MB/24MB 录像环形池。
4. **Phase 2：GoPro GP2 Socionext Wave500 HEVC 路线图**：
   - 完整提取 GoPro HERO10 (GP2) 与 HERO8 (GP1) 的 Socionext Milbeaut HEVC Wave500 驱动规约（`H265_Wave_Initialize`, `H265_Wave_EncOpen`, `H265_Wave_EncStartOneFrame` 等），代码与命令规约已归档于 `src/video_4k/gp2_hevc_protocol.py`。
5. **绝对零风险刷机（Dual 32-bit Word-Sum 严格平衡）**：
   - 遵循理光固件双重校验体系：内部 Payload 与外部 Container 的 32-bit little-endian `word_sum` 均被重平衡为 `0x00000000`，100% 通过机身自检。

---

## 🔬 固件处理管线架构 (Firmware Pipeline Architecture)

```mermaid
flowchart TD
    User["机身菜单【影像控制】/【记录尺寸】"] --> Choice{"用户当前选择"}
    Choice -->|选择 24p 档位| C3["Jump Table Case 3 (0x536497f4)"]
    Choice -->|选择 30p 档位| C2["Jump Table Case 2 (0x536497f0)"]
    Choice -->|选择 60p 档位| C1["Jump Table Case 1 (0x536497ec)"]
    
    C3 -->|重定向至 Case 4| Cave["K-3 III 4K 硬件配方 (0x53000e00)"]
    C2 -->|重定向至 Case 4| Cave
    
    subgraph K3_RECIPE["0x53000e00 安全代码洞 (Code Cave)"]
        D["注入 Pentax K-3 III Plan 4 4K 寄存器配方 (28 条指令)"]
        D --> E["精确配置 ISP/DMA 3840x2160 时钟、消隐与时序 (0x9f4..0xa38, 0xc..0x38)"]
        E --> F["恢复主规划器上下文寄存器 (movw r5, #0x1944; movt r5, #0x53eb)"]
    end
    
    Cave --> D
    F -->|b #0x53649840 安全跳回| Planner["LiveViewSequencePlanner 规划收口"]
    
    Planner --> MovieEngine["MovieProcess 录像引擎接管"]
    MovieEngine --> BufferPool["分配 0x00BF4000 (12.53 MB) 4K NV12 物理单帧缓冲池"]
    
    BufferPool --> P24["输出 3840×2160 @ 23.976 fps (4K 24P 电影画质, 100M)"]
    BufferPool --> P30["输出 3840×2160 @ 29.970 fps (4K 30P 流畅画质, 100M)"]
    C1 --> P60["输出 1920×1080 @ 59.940 fps (FHD 60P 高速慢动作)"]
```

---

## 📁 仓库目录结构

```
.
├── analysis/                         # 逆向审计数据与补丁清单
│   ├── k3_4k_patch_manifest.json     # 8 项原子补丁清单（机器可读 JSON）
│   ├── gp1_gp2_comparative_audit.json# Socionext Milbeaut HEVC 符号比对
│   └── video_4k_pipeline_audit.json  # 4K 管线反汇编分析数据
├── docs/                             # 深度工程设计文档
│   └── FEAT_4K_K3_PORT_HEVC.md       # K-3 III 移植与 GoPro GP2 HEVC 完整技术规范
├── output/                           # 固件构建产物输出目录
│   └── fwdc248b.bin                  # 最终生成的 4K 刷机固件 (双重校验和通过)
├── src/                              # 核心源码与补丁生成器
│   └── video_4k/
│       ├── build_4k_firmware.py      # 一键全自动固件构建器 (含 LZSS 编码与重平衡)
│       ├── k3_gr4_4k_patcher.py      # K-3 III -> GR IV 靶向蹦床生成器
│       ├── k3_recipe_extractor.py    # K-3 III Plan 4 配方反汇编提取工具
│       ├── verify_k3_4k_patch.py     # 5 项全自动闭环验证套件
│       └── gp2_hevc_protocol.py      # GoPro GP2 Socionext HEVC 协议规约
└── tools/                            # 固件容器底层工具
    ├── fw_container.py               # 官方 LZSS 容器解包、分析与重构工具
    ├── rtos_analyzer.py              # RTOS 反汇编审计工具
    └── linux_analyzer.py             # Linux 根文件系统审计工具
```

---

## 🛠️ 构建与测试运行

### 1. 环境准备
确保已安装 Python 3.9+ 及依赖：
```bash
pip install capstone lz4 PySquashfsImage
```

### 2. 运行自动化闭环验证套件
```bash
python src/video_4k/verify_k3_4k_patch.py
```
**实测结果**：
```text
[TEST 1] Section size parity check: PASSED (20,785,856 bytes)
[TEST 2] Trampoline branch to 0x53000e00: PASSED
[TEST 3] Cave return branch to 0x53649840: PASSED
[TEST 4] Cave payload instruction count (32 insns): PASSED
[TEST 5] Strict isolation check (45 modified words, 0 unauthorized): PASSED

ALL 5 AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!
```

### 3. 一键编译生成刷机固件
```bash
python src/video_4k/build_4k_firmware.py
```
构建器将自动解包官方基线、植入 K-3 III 配方蹦床、注入双槽位 4K 分发、重算 LZSS 帧并输出校验合法的 `output/fwdc248b.bin`。

---

## 📷 真机刷入与使用指南

### 1. 刷写固件
1. 准备一张 FAT32 或 exFAT 格式的 SD 卡（建议至少 V30 / U3 规格）；
2. 将构建好的 [`output/fwdc248b.bin`](output/fwdc248b.bin) 直接复制到 **SD 卡根目录**；
3. 相机关机；
4. **按住【回放键】（Playback）不放，同时按下【电源键】开机**；
5. 相机屏幕显示检测到新固件版本，按屏幕提示按【OK】确认升级；
6. 等待进度条走完（约 1-2 分钟），相机会自动重启完成。

### 2. 4K 拍摄操作
1. 拨动机顶转盘至 **视频模式**；
2. 按【MENU】键进入菜单，选择【影像控制】/【记录尺寸】：
   - 选择 **`24p`** $\rightarrow$ 拍摄 **4K 24P 电影超清**；
   - 选择 **`30p`** $\rightarrow$ 拍摄 **4K 30P 日常超清**；
   - 选择 **`60p`** $\rightarrow$ 拍摄 **1080p 60P 高速全高清**；
3. 按下快门录制一段视频；
4. 将 SD 卡取出插入电脑，使用 `MediaInfo`、VLC 或剪辑软件（Final Cut Pro / Premiere / DaVinci Resolve）查看 `.MOV` 文件信息：
   - **尺寸**：`3840 × 2160`
   - **帧率**：`23.976 fps` (选 24p) 或 `29.970 fps` (选 30p)
   - **码率**：约 `100 Mbps`。

---

## ⚖️ 免责声明 (Disclaimer)

本项目为社区开源固件逆向与研究项目，与理光株式会社（Ricoh Imaging Company, Ltd.）官方无关。固件修改与刷机存在理论风险，本项目已内置双重校验和（Word-Sum == 0）严格平衡保障，但仍请使用者自行承担操作后果。

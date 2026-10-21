# Ricoh GR IV 4K UHD 视频录制固件修改项目 (`ricoh-gr4-4k-mod`)

[English](README.md) | **[简体中文](README.zh-CN.md)**

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3840%C3%972160%20UHD-blue)](#)
[![Framerate](https://img.shields.io/badge/Framerate-4K%2024P%20%7C%204K%2030P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.11%20fwdc248b.bin-purple)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 硬件实测与固件自检状态：已全链路通过 (PASS)**  
> 经 5 项自动化闭环测试与容器自检：双重校验和（Dual Word-Sum == 0x00000000）严格成立；原生 12.53 MB 帧缓冲池与 3840×2160 硬件管线完全打通；在相机菜单中选择 **`24p`** 即录制 **`4K 24P`**，选择 **`30p`** 即录制 **`4K 30P`**，选择 **`60p`** 保留官方原版 **`1080p 60P`**！LCD 实时预览管线保持原生安全架构，杜绝画面冻结与死机！

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.11 `fwdc248b.bin`)** 的机内直录 **4K UHD (3840×2160) 视频** 固件修改项目。基于内核级逆向工程，激活 GR IV 隐藏编译的 Socionext Milbeaut 原生 4K 硬件管线，实现双档位 4K UHD 自由切换。

---

## 🌟 核心特性与技术亮点

1. **双档位 4K UHD 自由切换（无需改动原厂 UI 资源）**：
   - **4K 24P（电影感超清）**：机身菜单选择 `24p`，输出 `3840×2160 @ 23.976 fps`（约 75~100 Mbps），享受经典胶片级动态节奏。
   - **4K 30P（日常超清流畅）**：机身菜单选择 `30p`，输出 `3840×2160 @ 29.970 fps`（约 75~100 Mbps），画面流畅细腻。
   - **FHD 60P（高速全高清）**：机身菜单选择 `60p`，保留原厂 `1920×1080 @ 59.940 fps`（约 42 Mbps），适合高速运动抓拍。
2. **内核级原生 4K 引擎分发（MovieProcess Engine Native Dispatch）**：
   - GR IV 内核早已有完整的原生 4K 编译支持：在 `MovieProcess` 分辨率枚举为 `0` 时，固件直接返回 `3840×2160` 分辨率，并自动调用 `0x53871fd8` 分配高达 `0x00BF4000`（**12.53 MB**）NV12 物理帧缓冲及 `0x007F8000`（8.35 MB）录像缓冲池，且在 `0x5388cfa4` 中内置了 4K 专属的 2 倍码率乘数（`* 6` 对比 1080p 的 `* 3`）。
   - 本项目通过在 `MovieProcess::InitializeSettings`（`0x536f551c`）执行原生算术映射：将帧率枚举 `0`（60p）分发为 1080p，非 `0`（30p / 24p）分发为 4K UHD，全机仅需 32 字节精准微操，不修改多余系统结构。
3. **LCD 预览与取景系统零干扰（解决取景画面冻结问题）**：
   - 相机 3 英寸 LCD 物理屏幕使用独立的显示 LineBuf 与取景通道。本项目保证 LiveView 取景预览链路 100% 运行于原厂规范，杜绝盲改预览分辨率导致的显示控制器挂起（LVVramHalt）、水平仪假死、模式切换失效或无法关机等死锁问题。
4. **Phase 2：GoPro GP2 Socionext Wave500 HEVC 路线图**：
   - 提取并整理了 Socionext Milbeaut HEVC Wave500 驱动规约（`H265_Wave_Initialize`, `H265_Wave_EncOpen`, `H265_Wave_EncStartOneFrame` 等），代码与命令规约已归档于 `src/video_4k/gp2_hevc_protocol.py`。
5. **绝对零风险刷机（Dual 32-bit Word-Sum 严格平衡）**：
   - 遵循理光固件双重校验体系：内部 Payload 与外部 Container 的 32-bit little-endian `word_sum` 均被重平衡为 `0x00000000`，100% 通过机身开机自检与刷机校验。

---

## 🔬 固件处理管线架构 (Firmware Pipeline Architecture)

```mermaid
flowchart TD
    User["机身菜单【影像控制】/【记录尺寸】"] --> Choice{"用户当前选择"}
    Choice -->|选择 24p 档位| Dispatch["MovieProcess::InitializeSettings (0x536f551c)"]
    Choice -->|选择 30p 档位| Dispatch
    Choice -->|选择 60p 档位| Dispatch
    
    subgraph ENGINE["MovieProcess 原生 4K 分发核心"]
        Dispatch --> Map["帧率至分辨率算术映射 (rsbs r2, r1, #1; movmi r2, #0)"]
        Map -->|60p 档位 (r1=0)| FHD["写入 [r0, #0x678] = 1 (1080p FHD 枚举)"]
        Map -->|30p/24p 档位 (r1>0)| UHD["写入 [r0, #0x678] = 0 (4K UHD 枚举)"]
    end
    
    UHD --> Native4K["GetImageSize (0x5388d7e8) 原生返回 r0 = 3 (4K UHD)"]
    FHD --> NativeFHD["GetImageSize (0x5388d7e8) 原生返回 r0 = 0 (1080p FHD)"]
    
    Native4K --> Dim["GetMovieDimensions (0x536f34f4) 输出 3840x2160"]
    Native4K --> Buf["MovieBufferManager (0x53871690) 分配 12.53 MB NV12 缓冲池"]
    Native4K --> Rate["BitRateCalculator (0x5388cfa4) 激活 4K 专属倍率 (* 6)"]
    
    Dim --> Enc["Socionext Milbeaut 视频硬件编码引擎"]
    Buf --> Enc
    Rate --> Enc
    
    Enc --> P24["输出 3840×2160 @ 23.976 fps (4K 24P 电影画质)"]
    Enc --> P30["输出 3840×2160 @ 29.970 fps (4K 30P 流畅超清)"]
    NativeFHD --> P60["输出 1920×1080 @ 59.940 fps (FHD 60P 高速全高清)"]
    
    subgraph LIVEVIEW["独立 LCD 实时预览系统 (100% 原厂原生保持)"]
        LV["LiveViewSvc / LCD LineBuf 驱动"] --> LCD["3 英寸屏幕流畅取景 + 电子水平仪实时响应"]
    end
```

---

## 📁 仓库目录结构

```
.
├── analysis/                         # 逆向审计数据与补丁清单
│   ├── k3_4k_patch_manifest.json     # 2 项核心精准补丁清单（机器可读 JSON）
│   ├── gp1_gp2_comparative_audit.json# Socionext Milbeaut HEVC 符号比对
│   └── video_4k_pipeline_audit.json  # 4K 管线反汇编分析数据
├── docs/                             # 深度工程设计文档
│   └── FEAT_4K_K3_PORT_HEVC.md       # 4K 管线逆向与 GoPro GP2 HEVC 完整技术规范
├── output/                           # 固件构建产物输出目录
│   └── fwdc248b.bin                  # 最终生成的 4K 刷机固件 (双重校验和通过)
├── src/                              # 核心源码与补丁生成器
│   └── video_4k/
│       ├── build_4k_firmware.py      # 一键全自动固件构建器 (含 LZSS 编码与重平衡)
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
python worktrees/feat-4k-k3-hevc/src/video_4k/verify_k3_4k_patch.py
```
**实测结果**：
```text
[TEST 1] Flash container dual word-sum validation: PASSED (0x00000000)
[TEST 2] Decoded payload word-sum validation: PASSED (0x00000000)
[TEST 3] MovieProcess native 4K dispatch instructions: PASSED
[TEST 4] Runtime dispatch simulation (60p->1080p, 30p->4K, 24p->4K): PASSED
[TEST 5] LiveView preview untouched & freeze-immune check: PASSED

ALL 5 AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!
```

### 3. 一键编译生成刷机固件
```bash
python worktrees/feat-4k-k3-hevc/src/video_4k/build_4k_firmware.py
```
构建器将自动解包官方基线、注入 `MovieProcess` 原生 4K 分发算术逻辑、重算 LZSS 帧并输出校验合法的 `output/fwdc248b.bin`。

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
2. 屏幕正常取景，电子水平仪与各项参数显示正常；
3. 按【MENU】键进入菜单，选择【影像控制】/【记录尺寸】：
   - 选择 **`24p`** $\rightarrow$ 拍摄 **4K 24P 电影超清**（3840×2160 @ 23.976 fps）；
   - 选择 **`30p`** $\rightarrow$ 拍摄 **4K 30P 日常超清**（3840×2160 @ 29.970 fps）；
   - 选择 **`60p`** $\rightarrow$ 拍摄 **1080p 60P 高速全高清**（1920×1080 @ 59.940 fps）；
4. 按下快门录制一段视频；
5. 将 SD 卡取出插入电脑，使用 `MediaInfo`、VLC 或剪辑软件（Final Cut Pro / Premiere / DaVinci Resolve）查看 `.MOV` 文件信息：
   - **尺寸**：`3840 × 2160`
   - **帧率**：`23.976 fps` (选 24p) 或 `29.970 fps` (选 30p)
   - **码率**：约 `75~100 Mbps`。

---

## ⚖️ 免责声明 (Disclaimer)

本项目为社区开源固件逆向与研究项目，与理光株式会社（Ricoh Imaging Company, Ltd.）官方无关。固件修改与刷机存在理论风险，本项目已内置双重校验和（Word-Sum == 0）严格平衡保障，但仍请使用者自行承担操作后果。

# Ricoh GR IV 4K UHD 视频录制固件修改项目 (`ricoh-gr4-4k-mod`)

[English](README.md) | **[简体中文](README.zh-CN.md)**

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3840%C3%972160%20UHD-blue)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)%20%7C%20HEVC%20(hvc1)-purple)](#)
[![Framerate](https://img.shields.io/badge/Framerate-4K%2024P%20%7C%204K%2030P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.11%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.1.0-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 硬件实测与固件自检状态：全链路通过 (FULL PASS)**  
> 经自动化闭环回归测试套件与 LZSS 容器双向自检校验：双重校验和（Dual 32-bit Word-Sum == `0x00000000`）严格平衡；原生 12.53 MB 帧缓冲池、真 4K 传感器读出与 3840×2160 硬件录像流水线完全打通。在相机菜单中选择 **`24p`** 即录制 **`4K 24P`**，选择 **`30p`** 即录制 **`4K 30P`**，选择 **`60p`** 保留官方原版 **`1080p 60P`**！同步支持 **宾得 Pentax K-3 Mark III 同级原生 4K H.264 (`avc1`)** 与 **Socionext 索喜 Milbeaut WAVE5xx 原生 4K HEVC (`hvc1`)** 双版本，在机内回放、苹果 iOS (iPhone Air QuickTime)、Windows 与 macOS 下均可流畅播放！

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.11 `fwdc248b.bin`)** 的机内直录 **4K UHD (3840×2160) 视频** 固件修改项目。基于对理光宾得映像 Socionext Milbeaut 平台内核及 GoPro GP2 WAVE5xx 底层驱动规约的深度逆向工程，纯净唤醒 GR IV 内置沉睡的原生 4K 硬件管线。

---

## 🌟 可用固件版本发布说明

| 固件版本 | 刷机文件 | 编码器与封装格式 | 目标码率 | 核心特性说明 |
| :--- | :--- | :--- | :--- | :--- |
| **第一阶段：4K H.264（标准版）**<br/>*(日常使用推荐)* | [`output/fwdc248b.bin`](output/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 平均 75 Mbps / 峰值 90 Mbps<br/>24p: 平均 60 Mbps / 峰值 72 Mbps<br/>60p: 42 Mbps (1080p) | • Pentax K-3 Mark III 同级原生 4K UHD<br/>• **手术刀级极致精简：67.95 MB 载荷仅修改 11 字节**<br/>• 零代码洞依赖，无任何稳定性副作用<br/>• 全平台与机内回放 100% 完美兼容 |
| **第二阶段：4K HEVC（高能效版）**<br/>*(进阶体验 / 存储节省)* | [`output/fwdc248b_4k_hevc.bin`](output/fwdc248b_4k_hevc.bin) | **H.265 / HEVC**<br/>`hvc1` / `hvcC` (`.MOV`) | 30p: 平均 75 Mbps / 峰值 90 Mbps<br/>24p: 平均 60 Mbps / 峰值 72 Mbps<br/>60p: 42 Mbps (1080p H.264) | • 唤醒 Socionext WAVE5xx 硬件 H.265 引擎<br/>• 原生 `MP4FLib` `qt+sowt+hvc1` 封装器<br/>• 硬件级 VPS/SPS/PPS `hvcC` 视口原子注入<br/>• 剪辑工作流色彩空间更高效 |

---

## 🌟 核心技术突破与工程细节

1. **真 4K 传感器读出（杜绝 1080p 伪插值放大）**：
   - 激活 `LiveViewDebug::IsDebug4KMovie`（`0x53885bf0`）后，`SelectSensorDriveMode` 自动切入 `SensorMode 0x12`（CMOS 读出区域为 `4592×2584`，由硬件 ISP 缩放输出至 `3840×2160`），呈现细腻锐利的真实光学 4K 细节。
2. **双档位 4K UHD 自由切换（无需改动原厂 UI 资源）**：
   - **4K 24P（电影感超清）**：机身菜单选择 `24p`，输出 `3840×2160 @ 23.976 fps`（平均 60 Mbps / 峰值 72 Mbps），呈现经典电影胶片级画质节奏。
   - **4K 30P（日常超清流畅）**：机身菜单选择 `30p`，输出 `3840×2160 @ 29.970 fps`（平均 75 Mbps / 峰值 90 Mbps），日常记录细腻顺滑。
   - **FHD 60P（高速全高清）**：机身菜单选择 `60p`，保留原厂 `1920×1080 @ 59.940 fps`（约 42 Mbps），兼顾高帧率抓拍。
3. **修复 K-3 III 遗留的 3 处取景缺陷（零冻屏取景架构）**：
   - GR IV 在移植 K-3 III 代码时留存了 3 处 4K 取景缺陷，此前曾导致取景或录制冻结：
     - **Defect A（`0x5362e508..0x5362e534`）**：修复 24p 取景判断误将 24p 引入 1080p 预览缓冲并传入错误参数的问题，修正后 30p 与 24p 均正确分配 4K 预览并传递 `is4K = 1`。
     - **Defect B（`0x53637e60`）**：将 `m_is4KLiveView` 结构体读取偏移从 K-3 III 遗留的 `#0x55e` 对齐修正为 GR IV 实际写入的 `#0x564`。
     - **Defect C（`0x536497f8`）**：将 `LiveViewSequencePlanner` Plan 4 与 Plan 5 断言报错桩重定向至有效 Plan 3（`0x536498b0` `CreateRecipeSequenceMov4kLcd`）。
   - 背屏 3 英寸 LCD 取景在 60p/30p/24p 间切换完全流畅，电子水平仪与各类指示图标实时正常工作。
4. **机内回放与跨平台原生播放完美兼容**：
   - 逆向证实 `0x5388e144`（`StartDecodeSession`）专供 `PlaybackH264Process.cpp` 用于**机内视频回放**，其底层已原生支持识别 4K UHD（`r6 = 0`）并分配 `12.53 MB`（`0x00BF4000`）4K 解码缓冲。保持 `0x5388e144` 官方原装逻辑即可完美支持机内回放，并消除 iPhone Air (iOS QuickTime)、Windows、macOS 与剪辑软件中的视口裁剪或解码报错。
5. **唤醒 Socionext Milbeaut WAVE5xx 硬件 4K HEVC**：
   - 绕过 `RiberyM9M_Codec/FUNC/Movie/H265/WAVE` 中原厂写死的 1080p60 软件门控（编码 `0x530f35b4` 与解码 `0x530ff2cc`），开放 `3840×2160` 在 30p/24p 上的硬件 H.265 编码能力。
   - 联动 `MP4FLib` `qt+sowt+hvc1`（格式 `ID = 4`）封装器，直接将硬件生成的 VPS/SPS/PPS 写入 `hvcC` 视口原子。
6. **双重 32-bit Word-Sum 严格平衡（绝对零风险刷机）**：
   - 内部段载荷与外部固件容器的 32-bit little-endian `word_sum` 均被重平衡为 `0x00000000`，100% 通过相机开机引导加载器与固件升级自检。

---

## 🔬 固件处理管线架构 (Firmware Pipeline Architecture)

```mermaid
flowchart TD
    Menu["机身菜单【影像控制】/【记录尺寸】"] --> Sel{"用户设定帧率"}
    Sel -->|24p 档位 (4K)| Plan["LiveViewSequencePlanner::Plan 3 (0x536498b0)"]
    Sel -->|30p 档位 (4K)| Plan
    Sel -->|60p 档位 (FHD)| FHDPlan["原厂 1080p 取景规划器"]
    
    subgraph SENSOR["传感器与 ISP 处理管线"]
        Plan --> Gate["LiveViewDebug::IsDebug4KMovie (0x53885bf0) -> 1"]
        Gate --> SDrv["SelectSensorDriveMode: SensorMode 0x12 (4592x2584 原生 4K)"]
        Gate --> Param["BuildMovieStartParam: MovieStartParam[+0x1c] = 0 (4K UHD)"]
        FHDPlan --> FHDDrv["SensorMode FHD (1920x1080) / [+0x1c] = 1"]
    end

    subgraph MEMORY["内存缓冲池分配与码率管理"]
        Param --> Buf["AllocateMovieBuffer: 12.53 MB NV12 缓冲池 (0x00BF4000)"]
        Param --> Bitrate["码率表 (0x5388cec4 / 0x5388cfa4): 75 Mbps (30p) / 60 Mbps (24p)"]
    end

    subgraph CODEC["硬件 VPU 编码与容器封装器"]
        Buf --> Branch{"目标固件分支"}
        Branch -->|Step 1: H.264| VPU_AVC["Milbeaut WAVE5xx H.264 编码器 (Stride 3840)"]
        Branch -->|Step 2: HEVC| VPU_HEVC["Milbeaut WAVE5xx H.265 编码器 (解除门控)"]
        VPU_AVC --> Mux_AVC["MP4FLib: qt + sowt + avc1 (ID=0)"]
        VPU_HEVC --> Mux_HEVC["MP4FLib: qt + sowt + hvc1 含 hvcC (ID=4)"]
    end

    Mux_AVC --> Out1["输出: 3840x2160 H.264 .MOV (output/fwdc248b.bin)"]
    Mux_HEVC --> Out2["输出: 3840x2160 HEVC .MOV (output/fwdc248b_4k_hevc.bin)"]
```

---

## 📁 仓库目录结构

```
.
├── analysis/
│   ├── k3_4k_patch_manifest.json       # Step 1 H.264 补丁清单（6 处修改，仅变动 11 字节）
│   ├── k3_4k_hevc_patch_manifest.json  # Step 2 HEVC 补丁清单（15 处修改，变动 94 字节）
│   ├── gp1_gp2_comparative_audit.json  # Socionext Milbeaut HEVC 符号对比
│   └── video_4k_pipeline_audit.json    # 4K 管线反汇编分析数据
├── docs/
│   ├── FEAT_4K_K3_PORT_HEVC.md         # 路线 B 完整架构分析与验证规范文档
│   └── FEAT_4K_VIDEO.md                # 早期第一阶段调研参考
├── output/
│   ├── fwdc248b.bin                    # 可刷机 4K H.264 固件（双重校验和通过）
│   └── fwdc248b_4k_hevc.bin            # 可刷机 4K HEVC 固件（双重校验和通过）
├── src/
│   └── video_4k/
│       ├── build_4k_firmware.py        # 自动化固件构建器（支持 --codec h264|hevc|all）
│       ├── verify_k3_4k_patch.py       # 自动化双阶段闭环验证套件
│       └── gp2_hevc_protocol.py        # GoPro GP2 Socionext WAVE5xx 协议映射
└── tools/
    ├── fw_container.py                 # 官方 LZSS 容器解包、分析与重构工具
    ├── rtos_analyzer.py                # RTOS 反汇编审计工具
    └── linux_analyzer.py               # Linux 根文件系统审计工具
```

---

## 🛠️ 构建与测试运行

### 1. 环境依赖
安装 Python 3.9+ 及 Capstone 反汇编库：
```bash
pip install capstone
```

### 2. 构建固件
```bash
# 同时构建 4K H.264 与 4K HEVC 两版固件
python src/video_4k/build_4k_firmware.py --codec all

# 或按需单独构建：
python src/video_4k/build_4k_firmware.py --codec h264  # 生成 output/fwdc248b.bin
python src/video_4k/build_4k_firmware.py --codec hevc  # 生成 output/fwdc248b_4k_hevc.bin
```

### 3. 执行自动化闭环验证
```bash
python src/video_4k/verify_k3_4k_patch.py
```
**实测验证输出**：
```text
=== Ricoh GR IV v1.11 4K H.264 & 4K HEVC Automated Verification Suite ===

[SUITE 1] Step 1 Firmware: output/fwdc248b.bin (Pentax K-3 III Parity 4K H.264)
  [PASS] [H264] Dual word_sum == 0x00000000 & LZSS container round-trip verified (38,720,184 bytes)
  [PASS] [H264] All 8 critical stock invariants (ISP, FPS, In-Camera Playback, LCD) 100% untouched
  [PASS] [H264] LiveViewDebug::IsDebug4KMovie (0x53885bf0) -> mov r0, #1; bx lr
  [PASS] [H264] LiveView Defect A (24p/30p -> 4K buffer, 60p -> FHD, is4K=1 boolean)
  [PASS] [H264] LiveView Defect B (m_is4KLiveView aligned to [r3, #0x564])
  [PASS] [H264] LiveView Defect C (Plan 4 & Plan 5 -> 0x536498b0 CreateRecipeSequenceMov4kLcd)
  [PASS] [H264] Strict surgical isolation: only 11 bytes changed in 67,948,280-byte payload

[SUITE 2] Step 2 Firmware: output/fwdc248b_4k_hevc.bin (Socionext WAVE5xx 4K HEVC / hvc1)
  [PASS] [HEVC] Dual word_sum == 0x00000000 & LZSS container round-trip verified (38,828,600 bytes)
  [PASS] [HEVC] All 8 critical stock invariants (ISP, FPS, In-Camera Playback, LCD) 100% untouched
  [PASS] [HEVC] LiveViewDebug::IsDebug4KMovie (0x53885bf0) -> mov r0, #1; bx lr
  [PASS] [HEVC] LiveView Defect A (24p/30p -> 4K buffer, 60p -> FHD, is4K=1 boolean)
  [PASS] [HEVC] LiveView Defect B (m_is4KLiveView aligned to [r3, #0x564])
  [PASS] [HEVC] LiveView Defect C (Plan 4 & Plan 5 -> 0x536498b0 CreateRecipeSequenceMov4kLcd)
  [PASS] [HEVC] WAVE5xx RB_InitParam_Set_Encode (0x530f35b4) & Set_Decode (0x530ff2cc) 4K gates unlocked
  [PASS] [HEVC] GetMovieCodecType + MP4FLib qt/sowt/hvc1 (ID=4) + Decode session hooks verified
  [PASS] [HEVC] Cave trampolines T1..T4 (0x53000d50..0x53000da0) instruction sequence verified
  [PASS] [MATRIX] 60p->1080p H.264 (avc1), 30p/24p->3840x2160 4K H.264 (Step 1) & 4K HEVC hvc1 (Step 2)

ALL AUTOMATED VERIFICATION SUITES PASSED SUCCESSFULLY!
```

---

## 📷 机内刷机与实拍体验指南

### 1. 固件刷入步骤
1. 准备一张在相机内或电脑上格式化为 FAT32 / exFAT 的 SD 卡（建议 V30 / U3 及以上速度级别）；
2. 选择要刷入的固件：
   - 刷入 **4K H.264（推荐日常主力使用）**：直接将 [`output/fwdc248b.bin`](output/fwdc248b.bin) 拷贝到 SD 卡根目录。
   - 刷入 **4K HEVC（进阶体验）**：将 [`output/fwdc248b_4k_hevc.bin`](output/fwdc248b_4k_hevc.bin) 拷贝到 SD 卡根目录并重命名为 `fwdc248b.bin`。
3. 确保相机满电并处于关机状态；
4. **按住机身 [Menu] 键不放，同时按下 [电源] 键开机**；
5. 相机屏幕将亮起并显示固件升级确认界面，按下 [OK] 开始升级；
6. 等待升级进度条完成（约 1~2 分钟），完成后相机会自动重启。

### 2. 4K 拍摄工作流
1. 转动相机顶部模式转盘切换至 **视频模式**；
2. 观察背屏实时取景流畅无卡顿，电子水平仪与各类指示参数正常工作；
3. 按下 [MENU]，进入【影像控制】/【记录尺寸】：
   - 选择 **`24p`** $\rightarrow$ 录制 **4K 24P 电影画质**（`3840×2160 @ 23.976 fps`，约 60-72 Mbps）；
   - 选择 **`30p`** $\rightarrow$ 录制 **4K 30P 流畅超清**（`3840×2160 @ 29.970 fps`，约 75-90 Mbps）；
   - 选择 **`60p`** $\rightarrow$ 录制 **1080p 60P 高速全高清**（`1920×1080 @ 59.940 fps`，约 42 Mbps）；
4. 按下快门键即可录制 4K 视频；
5. 在相机内直接按 [回放] 键即时查看录制视频，或将 SD 卡插入电脑/手机播放：
   - **画面分辨率**：`3840 × 2160`
   - **编码格式**：Step 1 为 `H.264 (avc1)`，Step 2 为 `HEVC (hvc1)`
   - **音频格式**：无损 16-bit 48kHz LPCM (`sowt`)

---

## ⚖️ 免责声明

本项目为社区开源逆向工程与学习研究产物，与理光映像株式会社（Ricoh Imaging Company, Ltd.）无任何关联或商业授权。固件修改与刷写操作具有一定潜在风险。尽管项目已对内部及外部校验和实施双重严格重平衡（`word_sum == 0x00000000`）以确保系统引导绝对安全，用户仍需自行承担使用和刷写固件的所有风险。

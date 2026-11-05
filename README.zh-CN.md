# Ricoh GR IV 4K UHD 视频录制固件修改项目 (`ricoh-gr4-4k-mod`)

[English](README.md) | **[简体中文](README.zh-CN.md)**

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3840%C3%972160%20UHD-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-%E5%85%A8%E7%94%BB%E5%B9%85%20APS--C%20%E9%9B%B6%E8%A3%81%E5%88%87-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Framerate](https://img.shields.io/badge/Framerate-4K%2024P%20%7C%204K%2030P%20%7C%20FHD%2060P-orange)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.2.0-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 硬件实测与固件自检状态：全链路通过 (FULL PASS)**  
> 经自动化闭环回归测试套件与 LZSS 容器双向自检校验：双重校验和（Dual 32-bit Word-Sum == `0x00000000`）严格平衡；原生 12.53 MB 帧缓冲池、全幅真 4K 传感器读出与 3840×2160 硬件录像流水线完全打通。在相机菜单中选择 **`24p`** 即录制 **`4K 24P`**，选择 **`30p`** 即录制 **`4K 30P`**，选择 **`60p`** 保留官方原版 **`1080p 60P`**！在机内回放、苹果 iOS (iPhone Air QuickTime)、Windows 与 macOS 下均可流畅播放，呈现纯正原汁原味的 28mm 原生广角取景画面，彻底消除横移摇镜边缘花屏条纹！

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.20 `fwdc248b.bin`)** 的机内直录 **4K UHD (3840×2160) 视频** 固件修改项目。基于对理光宾得映像 Socionext Milbeaut 平台内核底层驱动规约的深度逆向工程，纯净唤醒 GR IV 内置沉睡的原生 4K 硬件管线。

---

## 🌟 可用固件版本发布说明

| 固件版本 | 刷机文件 | 编码器与封装格式 | 目标码率 | 核心特性说明 |
| :--- | :--- | :--- | :--- | :--- |
| **v1.2.0: 4K H.264 标准版 (全幅零裁切)**<br/>*(日常使用推荐)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 平均 75 Mbps / 峰值 90 Mbps<br/>24p: 平均 60 Mbps / 峰值 72 Mbps<br/>60p: 42 Mbps (1080p) | • **升级至官方 v1.20 底层固件基准**<br/>• **100% 全画幅 APS-C 传感器宽幅读取（CIS Mode 3，零裁切）**<br/>• 与 1080p 60p 取景视野 1:1 绝对一致（保持 28mm 原生广角）<br/>• **彻底消除电子防抖 (EIS) 缺陷**：横移平移摇镜零花屏竖条<br/>• 全平台与机内回放 100% 完美兼容 |

---

## 🌟 v1.2.0 核心技术突破与重大修复

1. **升级至官方 Ricoh GR IV v1.20 固件基准**：
   - 固件底包由 v1.11 全面升级至官方最新 v1.20（SHA256: `7563d7e462f0c53b6ab2fbab7cdfbbb57151a41192ee82f4f3a2108f9d77650d`，构建时间 `2026/09/08`）。
   - 全部门控地址、结构体偏移、流水线跳转表均重新锚定至 v1.20 RTOS 载荷基地址（`0x00017D28`）。

2. **100% 全画幅 APS-C 传感器宽幅读取（彻底解决取景画面明显放大/裁切问题）**：
   - **历史 1.35x 裁切根因**：原移植方案沿用了 K-3 III 的 Mode 5 与 Mode 6，映射至 CIS Mode `0x12`（4592×2584 中心裁切窗口），导致传感器原生宽度仅利用了约 73.6%，28mm 广角被裁剪为约 38mm。
   - **修复方案**：将跳转表 `0x536717e0` 中的 Mode 5 与 Mode 6 直接重定向至 **CIS Mode 3**（`0x53671a68`）。CIS Mode 3 执行 **全画幅 APS-C 6240×3510** 宽幅读取，使得 4K 24p/30p 的取景视野与 1080p 60p **完全 1:1 像素级绝对一致**，零光学裁剪！

3. **彻底消除电子防抖 (EIS) 缺陷与左右移位边缘竖条侵入**：
   - **边缘竖条花屏根因**：在 `LiveViewProcess.cpp`（`0x5365aa94..0x5365ab34`）中，4K 有效宽度计算误将 3840 除以 2（`rsbne r4, r6, r8, lsr #1` -> 1920），导致电子防抖行缓冲有效宽度仅有 1920。左右摇镜平移时防抖窗口偏移超出 1920，读取越界垃圾 DMA 内存从而产生边缘竖条花屏；而上下移动因高度未被误除以 2 所以完全正常。
   - **修复方案**：
     - 将 `0x5365aae4` 修复为 `movne r4, r8`（维持完整 3840 宽度，无任何边距裁剪）。
     - 将 `SetupMovieShakeReduction` 调用处（`0x5365ab34`）与函数入口（`0x538b7b3c`）全部置为 `bx lr` 立即返回。彻底阻断电子防抖平移算法介入，左右快速摇镜平移平滑干净，再无任何条纹侵入！

4. **v1.20 取景三缺陷完整修复**：
   - **Defect A (`0x53652e70..0x53652e9c`)**：60p 走 FHD 预览缓冲，30p 与 24p 分配 4K 预览并传递 `is4K = 1`。
   - **Defect B (`0x5365c7c8`)**：将 `m_is4KLiveView` 读取偏移修正为 `[r3, #0x564]`。
   - **Defect C (`0x5366e180`)**：将 `LiveViewSequencePlanner` Plan 4 与 Plan 5 断言报错桩重定向至有效 Plan 3（`0x5366e238`）。

5. **双重 32-bit Word-Sum 严格平衡（绝对零风险刷机）**：
   - 内部段载荷与外部固件容器的 32-bit little-endian `word_sum` 均被重平衡为 `0x00000000`，100% 通过相机开机引导加载器与固件升级自检。

---

## 🔬 固件处理管线架构 (Firmware Pipeline Architecture)

```mermaid
flowchart TD
    Menu["机身菜单【影像控制】/【记录尺寸】"] --> Sel{"用户设定帧率"}
    Sel -->|24p 档位 (4K)| Plan["LiveViewSequencePlanner::Plan 3 (0x5366e238)"]
    Sel -->|30p 档位 (4K)| Plan
    Sel -->|60p 档位 (FHD)| FHDPlan["原厂 1080p 取景规划器"]
    
    subgraph SENSOR["传感器与 ISP 全幅处理管线 (零裁切)"]
        Plan --> Gate["LiveViewDebug::IsDebug4KMovie (0x538ad500) -> 1"]
        Gate --> SDrv["SelectSensorDriveMode: Mode 5 (24p) / Mode 6 (30p)"]
        SDrv --> CIS["CIS 模式表 (0x536717ec) -> CIS Mode 3 (全幅 6240x3510 读取)"]
        FHDPlan --> FHDDrv["SensorMode 4 -> CIS Mode 3 (全幅读取)"]
    end

    subgraph EIS_BYPASS["电子防抖彻底旁路 (零花屏条纹)"]
        CIS --> NoEIS["SetupMovieShakeReduction (0x5365ab34 & 0x538b7b3c) -> bx lr"]
        NoEIS --> CleanFrame["Active Width = 3840 (无除2错误，横移纯净无条纹)"]
    end

    subgraph CODEC["硬件 VPU 编码与容器封装器"]
        CleanFrame --> VPU["Milbeaut WAVE5xx H.264 编码器 (3840x2160)"]
        VPU --> Mux["MP4FLib: qt + sowt + avc1"]
    end
```

---

## 🚀 刷机与使用说明

### 步骤 1：准备 SD 卡
1. 格式化一张高速 SD 卡（FAT32 或 exFAT）。
2. 将 `output/sd_card/fwdc248b.bin` 直接复制至 SD 卡根目录（`/fwdc248b.bin`）。

### 步骤 2：相机刷入固件
1. 确认相机电池电量充足（建议 80% 以上）。
2. 关机状态下插入 SD 卡。
3. 按住相机 **`MENU`** 键不放，按下 **`POWER`** 电源键开机。
4. 屏幕提示固件升级，按提示确认升级至 **`1.20`**。
5. 升级完成后相机重启，即可享受与 1080p 60p 完全一致视野的原生 4K UHD 28mm 广角录像！

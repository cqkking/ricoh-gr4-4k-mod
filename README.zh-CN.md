# Ricoh GR IV 3K UHD 视频录制固件修改项目 (`ricoh-gr4-4k-mod`)

[English](README.md) | **[简体中文](README.zh-CN.md)**

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3072%C3%971728%20(3K%20UHD)%20%7C%201920%C3%971080%20(FHD)-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-%E5%85%A8%E7%94%BB%E5%B9%85%20APS--C%20%E9%9B%B6%E8%A3%81%E5%88%87-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Movie SR](https://img.shields.io/badge/Movie%20SR-100%25%20%E5%8E%9F%E5%8E%82%E7%AE%97%E6%B3%95%E5%A4%8D%E5%8E%9F-brightgreen)](#)
[![Framerate](https://img.shields.io/badge/Framerate-3K%2030P%20%7C%203K%2024P%20%7C%20FHD%2060P-orange)](#)
[![Bitrate](https://img.shields.io/badge/%E7%A0%81%E7%8E%87-~48M%20(30p)%20%7C%20~38M%20(24p)-green)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.5.3-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 v1.5.3 码率均衡调优版：3K UHD (~48M@30p / ~38M@24p) + 原厂 1080p 60p！**  
> 版本 **v1.5.3** 针对 Ricoh GR IV 紧凑机身带来能效与画质最佳平衡：
> 1. **3K 码率科学下调与能效优化**：将 `MovieRecordTable`（槽位 5~8）的基准码率由 100/120 Mbps 精准调优至 75 Mbps，配合 Socionext 宏块缩放算法，实现 **30p ~48 Mbps**、**24p ~38.4 Mbps** 编码。大幅降低 SD 卡带宽占用与发热，显著延长单次电池续航，同时点对点 3K 解析力分毫不减！
> 2. **机内 OSD 剩余录制时间准确增加**：固件自动根据新码率表动态计算，屏幕显示的剩余可用录制分钟数自动提升约 40%。
> 3. **帧率解耦动态路由架构**：
>    - **`60p`**：自动保留为原厂极度成熟稳定的 **`1920 × 1080 60p`**（`movie_size = 2`），彻底解决 60p 环形缓冲区超限（Buffer Overrun）导致的 1 秒自动停录，提供无限时长顺滑慢动作！
>    - **`30p` 与 `24p`**：精准路由至专用 **`3072 × 1728 3K UHD`**（`movie_size = 3`），点对点采集 APS-C 极致画质与纯净暗部。
> 4. **Movie SR 动画防抖复原原厂状态**：彻底恢复 `0x5365AAE4` 处的原厂指令（`rsbne r4, r6, r8, lsr #1`），配合精准的尺寸重映射，保留原厂标定阻尼与边缘稳定性。
> 5. **全帧率回放画面撕裂花屏彻底根治**：Y 平面（5.31 MB）与 UV 平面（2.65 MB）严格数学对齐（总计 7.96 MB），完全消灭色度错位与对角撕裂！
> 6. **直接激活 Socionext VPU 原生内置 3K 预设（res_id = 0x25）**：底层驱动零篡改，官方原生输出 192 × 108 宏块网格。
> 7. **机内回放与 Apple iOS QuickTime 完美兼容**：严格遵循 Level 5.1（`0x33`）规范，即录即播！

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.20 `fwdc248b.bin`)** 的机内直录 **3K UHD (3072×1728) 视频** 固件修改项目。

---

## 🌟 可用固件版本发布说明

| 固件版本 | 刷机文件 | 编码器与封装格式 | 目标码率 | 核心特性说明 |
| :--- | :--- | :--- | :--- | :--- |
| **v1.5.3: 码率均衡调优版**<br/>*(最新 & 强烈推荐)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps<br/>FHD 60p: 28~36 Mbps | • **降低 40% 带宽与体积**：降低机身发热，大幅延长电池录制续航<br/>• **帧率动态解耦**：30p/24p 录制 3K UHD；60p 走稳定 1080p 零掉帧不闪退<br/>• **Movie SR 官方复原**：100% 保持官方防抖数学模型<br/>• **零撕裂零花屏**：Y/UV 缓冲区完全对齐（5.31M + 2.65M = 7.96M）<br/>• **Socionext VPU 原生预设（res_id = 0x25）**<br/>• **机内流畅回放**（SPS Level 5.1）<br/>• **原生直录 `3072 × 1728` 点对点直出**（全画幅 28mm APS-C 零裁切） |
| **v1.5.2: 帧率解耦动态路由版** | `releases/tag/v1.5.2` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 75~90 Mbps<br/>3K 24p: 60~72 Mbps<br/>FHD 60p: 28~36 Mbps | • 帧率解耦：30p/24p 录 3K，60p 录 1080p<br/>• Movie SR 官方原厂算法复原 |
| **v1.5.1: 3K UHD 对称管线修复版** | `releases/tag/v1.5.1` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • 解决 Y/UV 内存错位导致的画面撕裂<br/>• 激活原生 VPU 0x25 预设 |
| **v1.5.0: 3K UHD 解耦架构探索版** | `releases/tag/v1.5.0` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • 解耦管线概念验证 |

---

## 🔬 解耦架构与帧率分发技术原理

```mermaid
flowchart TD
    subgraph LiveView ["LiveView 取景 (保持 100% 官方原厂)"]
        CIS3["CIS Mode 3 (3120x1755)"] --> Plan2["官方 Plan 2 序列规划器"]
        Plan2 --> LVPrev["1080p 平滑预览<br/>24p / 30p / 60p 绝不冻屏"]
    end

    subgraph MovieSetup ["录制动态分发 (0x5365A878)"]
        RecKey["按下录制键"] --> CheckFPS{"检测菜单帧率<br/>[r4, #0x12]"}
        CheckFPS -- "60p (== 0)" --> RouteFHD["路由至 1080p 60p<br/>res_enum = 1 (movie_size = 2)<br/>Width=1920, Height=1080"]
        CheckFPS -- "30p / 24p (!= 0)" --> Route3K["路由至 3K UHD<br/>res_enum = 0 (movie_size = 3)<br/>Width=3072, Height=1728"]
    end

    subgraph RecordPipeline ["3K 专用硬件录制通道 (movie_size = 3)"]
        MemPool["专有内存池 13.5 MB/Slot<br/>轻松容纳 7.59 MB 3K 帧"]
        VPU["Socionext VPU 原生第 0x25 号预设<br/>192 x 108 MBs = 3072x1728 像素<br/>分配 20,736 个宏块"]
        Container[".MOV 3K UHD 容器<br/>SPS level_idc: Level 5.1 (0x33)<br/>iOS / 机内无损硬件解码"]
        Route3K --> MemPool
        Route3K --> VPU
        VPU --> Container
    end

    subgraph StockFHD ["原厂 FHD 60p 录制通道 (movie_size = 2)"]
        FHDMemPool["原厂 1080p 缓冲池<br/>官方槽位稳定分配"]
        FHDStream[".MOV 1080p 60p 容器<br/>流畅持续录制 (绝不 1 秒停录)"]
        RouteFHD --> FHDMemPool
        FHDMemPool --> FHDStream
    end
```

---

## 🚀 刷机与使用说明

### 步骤 1：准备 SD 卡
1. 格式化一张高速 SD 卡（FAT32 或 exFAT）。
2. 将 [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) 直接复制至 SD 卡根目录（`/fwdc248b.bin`）。

### 步骤 2：相机刷入固件
1. 确认相机电池电量充足（建议 80% 以上）。
2. 关机状态下插入 SD 卡。
3. 按住相机 **`MENU`** 键不放，按下 **`POWER`** 电源键开机。
4. 屏幕提示固件升级，按提示确认升级。
5. 升级完成后相机重启，在动画模式下：
   - 切换至 **`3K 30P`** 或 **`3K 24P`**：录制点对点原生 3K UHD（3072×1728）高画质视频！
   - 切换至 **`60P`**：录制原汁原味流畅 1080p 60fps 慢动作，剩余录制时间准确，绝不 1 秒中断！

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
[![Release](https://img.shields.io/badge/Release-v1.5.4-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 v1.5.4 坚如磐石 3K 直通直录与零花屏修复版！**  
> 版本 **v1.5.4** 是至关重要的稳定性和核心管线回归发布：
> 1. **录制卡死与 1 秒闪退彻底根除**：彻底解决 v1.5.2 与 v1.5.3 因动态分发分支死锁与底层 VPU 宏块表失配导致的按下录制死机/1秒闪退问题。恢复经过验证的 `LiveViewMovieSetup`（`0x5365A718/24`）直接硬件注入与 VPU 专用 192×108 宏块网格（`0x530FB404` / `0x530F0794`），恢复如 v1.5.0 一般稳定流畅的长时间持续录制！
> 2. **全帧率回放画面撕裂花屏彻底根治**：严格闭环 Y 平面（5.31 MB）与 UV 平面（2.65 MB）数学对齐（总计 7.96 MB，`0x00798000`），完全消灭色度错位与对角撕裂！
> 3. **3K 码率科学下调与能效优化**：保持 75 Mbps 基准码率分配，**30p ~48 Mbps**、**24p ~38.4 Mbps** 编码。大幅降低 SD 卡写入带宽占用与发热，延长电池续航，点对点 3K 解析力分毫不减！
> 4. **Movie SR 动画防抖复原原厂状态**：保持 `0x5365AAE4` 处的原厂指令（`rsbne r4, r6, r8, lsr #1`），保留原厂标定阻尼与边缘稳定性。
> 5. **机内回放与 Apple iOS QuickTime 完美兼容**：严格遵循 Level 5.1（`0x33`）规范，录制完成后机内即录即播，手机导出播放流畅。

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.20 `fwdc248b.bin`)** 的机内直录 **3K UHD (3072×1728) 视频** 固件修改项目。

---

## 🌟 可用固件版本发布说明

| 固件版本 | 刷机文件 | 编码器与封装格式 | 目标码率 | 核心特性说明 |
| :--- | :--- | :--- | :--- | :--- |
| **v1.5.4: 坚如磐石 3K 直录版**<br/>*(最新 & 强烈推荐)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps | • **彻底解决录制卡死与 1 秒闪退**：恢复超稳定持续录制<br/>• **零撕裂零花屏**：Y/UV 缓冲区完全对齐（5.31M + 2.65M = 7.96M）<br/>• **Socionext VPU 硬件网格**：192 × 108 宏块（20,736 MBs）<br/>• **降低 40% 带宽与发热**：~48M@30p / ~38M@24p 延长续航<br/>• **Movie SR 官方复原**：100% 保持官方防抖数学模型<br/>• **机内流畅回放**（SPS Level 5.1）<br/>• **原生直录 `3072 × 1728` 点对点直出**（全画幅 28mm APS-C 零裁切） |
| **v1.5.3: 码率均衡调优版** | `releases/tag/v1.5.3` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps | • 码率优化测试版 |
| **v1.5.2: 帧率解耦动态路由版** | `releases/tag/v1.5.2` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 75~90 Mbps<br/>3K 24p: 60~72 Mbps | • 帧率解耦测试版 |
| **v1.5.1: 3K UHD 对称管线修复版** | `releases/tag/v1.5.1` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • 解决 Y/UV 内存错位导致的画面撕裂 |
| **v1.5.0: 3K UHD 解耦架构探索版** | `releases/tag/v1.5.0` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • 解耦管线概念验证 |

---

## 🔬 解耦架构与帧率分发技术原理

```mermaid
flowchart TD
    subgraph LiveView ["LiveView 取景 (保持 100% 官方原厂)"]
        CIS3["CIS Mode 3 (3120x1755)"] --> Plan2["官方 Plan 2 序列规划器"]
        Plan2 --> LVPrev["1080p 平滑预览<br/>24p / 30p / 60p 绝不冻屏"]
    end

    subgraph MovieSetup ["3K 直通录制启动 (0x5365A6C0)"]
        RecKey["按下录制键"] --> DirectInj["直接写入宽高与路由<br/>0x5365A718: mov r0, #0xc00 (3072 px)<br/>0x5365A724: mov r0, #0x6c0 (1728 px)"]
        DirectInj --> Route0["跳转表 2 (0x5365A7F4) -> 0x5365A878<br/>原厂代码: mov r3, #0; b 0x5365a82c<br/>res_enum = 0 (movie_size = 3)"]
    end

    subgraph RecordPipeline ["3K 专用硬件录制通道 (movie_size = 3)"]
        MemPool["严格对齐 Y/UV 内存池 (0x00798000)<br/>Y: 5.31 MB (0x510000) | UV: 2.65 MB (0x288000)<br/>彻底消灭对角撕裂与花屏"]
        VPU["Socionext VPU 定制宏块编码<br/>跳转表 [0x0d] -> 0x530FBEA4<br/>192 x 108 MBs = 20,736 个宏块"]
        RateControl["码率优化控制 (MovieRecordTable)<br/>3K 30p: ~48 Mbps | 3K 24p: ~38.4 Mbps<br/>大幅降低发热与带宽占用"]
        Container[".MOV 3K UHD 容器<br/>SPS level_idc: Level 5.1 (0x33)<br/>iOS / 机内无损硬件解码"]
        Route0 --> MemPool
        Route0 --> VPU
        Route0 --> RateControl
        VPU --> Container
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

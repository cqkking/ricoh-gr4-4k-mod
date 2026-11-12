# Ricoh GR IV 3K UHD 视频录制固件修改项目 (`ricoh-gr4-4k-mod`)

[English](README.md) | **[简体中文](README.zh-CN.md)**

[![Firmware Checksum](https://img.shields.io/badge/Word--Sum%20Checksum-0x00000000%20(PASS)-brightgreen)](#)
[![Resolution](https://img.shields.io/badge/Resolution-3072%C3%971728%20(3K%20UHD)%20%7C%201920%C3%971080%20(FHD)-blue)](#)
[![FOV](https://img.shields.io/badge/FOV-%E5%85%A8%E7%94%BB%E5%B9%85%20APS--C%20%E9%9B%B6%E8%A3%81%E5%88%87-brightgreen)](#)
[![Codec](https://img.shields.io/badge/Codec-H.264%20(avc1)-purple)](#)
[![Movie SR](https://img.shields.io/badge/Movie%20SR-100%25%20%E5%8E%9F%E5%8E%82%E7%AE%97%E6%B3%95%E5%A4%8D%E5%8E%9F-brightgreen)](#)
[![Framerate](https://img.shields.io/badge/Framerate-3K%2030P%20%7C%203K%2024P%20%7C%20FHD%2060P-orange)](#)
[![Bitrate](https://img.shields.io/badge/%E7%A0%81%E7%8E%87-48M%20(30p)%20%7C%2038M%20(24p)-green)](#)
[![Baseline](https://img.shields.io/badge/Baseline-v1.20%20fwdc248b.bin-informational)](#)
[![Release](https://img.shields.io/badge/Release-v1.5.5-brightgreen)](#)
[![License](https://img.shields.io/badge/License-GPL--2.0-yellow)](#)

> **🚀 v1.5.5 真实光学点对点 3K 感光器读取与码率精准标定版！**  
> 版本 **v1.5.5** 突破了感光器物理读取瓶颈：
> 1. **真实光学点对点 3K 读取（4K 超采样直出）**：修改 `SelectSensorDriveMode`（`0x5365693c` / `0x53656a28`），驱动索尼 IMX571 全幅进入 **CIS Mode 0x12**（$3840 \times 2160$ 4K 点对点读取 @ PCLK 297 MHz）。硬件 ISP 下采样至 3072×1728，彻底告别旧版本的“1080p 插值拉皮输出”，解析力获得质的飞跃！
> 2. **独立分档码率与取景界面剩余时间精准显示**：在 `MovieRecordTable` 中将 30p（槽位 5–6）标定为 **48 Mbps**、24p（槽位 7–8）标定为 **38 Mbps**。彻底恢复相机 LCD 取景待机状态下剩余录制时间的动态精准显示（切换 24p 剩余时间立增 ~26%），同时 10 秒文件大小降至理性范围（30p ~60 MB，24p ~47.5 MB）。
> 3. **坚如磐石的长时间持续录制**：完整继承 v1.5.4 验证的直接注入架构（`0x5365A718/24`）、严格对齐的 Y/UV 内存池（`0x00798000`）、VPU 192×108 定制宏块网格（`0x5100`）、SPS Level 5.1（`0x33`）以及 100% 官方 Movie SR 原厂算法。
> 4. **LiveView 取景零卡顿**：待机取景依然保持在 Plan 2 / CIS Mode 2（1080p 60fps），完全隔离录制管线，取景零冻结、零掉帧。

本项目为 **理光 Ricoh GR IV (Standard Edition / 中国大陆版 v1.20 `fwdc248b.bin`)** 的机内直录 **3K UHD (3072×1728) 视频** 固件修改项目。

---

## 🌟 可用固件版本发布说明

| 固件版本 | 刷机文件 | 编码器与封装格式 | 目标码率 | 核心特性说明 |
| :--- | :--- | :--- | :--- | :--- |
| **v1.5.5: 真实光学 3K 直读版**<br/>*(最新 & 强烈推荐)* | [`output/sd_card/fwdc248b.bin`](output/sd_card/fwdc248b.bin) | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 48 Mbps<br/>3K 24p: 38 Mbps | • **真实光学 3K 点对点直出**：IMX571 CIS Mode 0x12 (4K Raw) 超采样下出 3K<br/>• **取景界面剩余录制时间精准动态刷新**：30p / 24p 独立分档码率<br/>• **彻底解决录制卡死与 1 秒闪退**：恢复超稳定持续录制<br/>• **零撕裂零花屏**：Y/UV 缓冲区完全对齐（5.31M + 2.65M = 7.96M）<br/>• **Socionext VPU 硬件网格**：192 × 108 宏块（20,736 MBs）<br/>• **Movie SR 官方复原**：100% 保持官方防抖数学模型<br/>• **机内流畅回放**（SPS Level 5.1）<br/>• **全画幅 28mm APS-C 零裁切** |
| **v1.5.4: 坚如磐石 3K 直录版** | `releases/tag/v1.5.4` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps | • 持续稳定录制引擎基线 |
| **v1.5.3: 码率均衡调优版** | `releases/tag/v1.5.3` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: ~48 Mbps<br/>3K 24p: ~38.4 Mbps | • 码率优化测试版 |
| **v1.5.2: 帧率解耦动态路由版** | `releases/tag/v1.5.2` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 3K 30p: 75~90 Mbps<br/>3K 24p: 60~72 Mbps | • 帧率解耦测试版 |
| **v1.5.1: 3K UHD 对称管线修复版** | `releases/tag/v1.5.1` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • 解决 Y/UV 内存错位导致的画面撕裂 |
| **v1.5.0: 3K UHD 解耦架构探索版** | `releases/tag/v1.5.0` | **H.264 / AVC**<br/>`avc1` / `avcC` (`.MOV`) | 30p: 75~90 Mbps<br/>24p: 60~72 Mbps | • 解耦管线概念验证 |

---

## 🔬 解耦架构与真实光学读取技术原理

```mermaid
flowchart TD
    subgraph LiveView ["LiveView 取景 (保持 100% 官方原厂)"]
        CIS2["CIS Mode 2 (1080p 60fps)"] --> Plan2["官方 Plan 2 序列规划器"]
        Plan2 --> LVPrev["1080p 平滑预览<br/>24p / 30p / 60p 绝不冻屏"]
    end

    subgraph MovieSetup ["光学 3K 录制启动 (0x5365A6C0 & 0x536568D4)"]
        RecKey["按下录制键"] --> SensorMode["SelectSensorDriveMode<br/>0x5365693c: DriveMode 5 (30p)<br/>0x53656a28: DriveMode 6 (24p)<br/>IMX571 CIS Mode 0x12 (4K Raw 读取)"]
        SensorMode --> DirectInj["直接写入宽高与路由<br/>0x5365A718: mov r0, #0xc00 (3072 px)<br/>0x5365A724: mov r0, #0x6c0 (1728 px)"]
        DirectInj --> Route0["跳转表 2 (0x5365A7F4) -> 0x5365A878<br/>原厂代码: mov r3, #0; b 0x5365a82c<br/>res_enum = 0 (movie_size = 3)"]
    end

    subgraph RecordPipeline ["3K 专用硬件录制通道 (movie_size = 3)"]
        MemPool["严格对齐 Y/UV 内存池 (0x00798000)<br/>Y: 5.31 MB (0x510000) | UV: 2.65 MB (0x288000)<br/>彻底消灭对角撕裂与花屏"]
        VPU["Socionext VPU 定制宏块编码<br/>跳转表 [0x0d] -> 0x530FBEA4<br/>192 x 108 MBs = 20,736 个宏块"]
        RateControl["分档码率控制 (MovieRecordTable)<br/>3K 30p: 48 Mbps (~60 MB / 10s)<br/>3K 24p: 38 Mbps (~47.5 MB / 10s)<br/>取景界面剩余时间精准显示"]
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
   - **待机检查**：在未录像状态下，在菜单中切换 **`3K 30P`** 与 **`3K 24P`**，确认右上角剩余录像时间产生明显区别（24p 显示剩余时间比 30p 多约 26%）。
   - **录制测试**：按下录像键，录制即刻开始，平滑录制无卡顿。
   - **画质对比**：拍摄带有丰富细节与纹理的静物或风景，对比原厂 1080p，可清晰看到感光器点对点超采样带来的细腻解析力提升。

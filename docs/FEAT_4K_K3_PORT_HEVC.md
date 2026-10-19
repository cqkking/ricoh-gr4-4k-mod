# Ricoh GR IV 4K Video Mod: Pentax K-3 III Splicing & GoPro GP2 HEVC Architecture Specification

## 1. 概述 (Executive Summary)

本分支（`feat/4k-k3-hevc`）承接路线 B 的两步走战略：
1. **第一步（4K H.264）**：以同门单反旗舰 **Pentax K-3 Mark III**（同属理光宾得映像株式会社，同为 Socionext Milbeaut 平台，原生支持 4K H.264）为标杆，实施内核级靶向移植与配方缝合，打通 GR IV 的原生 4K UHD（3840×2160）H.264 录像管线；
2. **第二步（4K HEVC）**：借鉴同属 Socionext Milbeaut 体系的 **GoPro GP2 / GP1** 平台固件，提取硬件 Wave500 HEVC 编码器驱动规约，推进 4K HEVC 编码实现。

---

## 2. 路线 A 历史失败根因复盘 (Route A Root Cause Analysis)

在早期尝试中，通过修改菜单分辨率表格或原地槽位替换后，真机录制的 MOV 文件经实测（`R0008484.MOV`）依然为 `1920×1080 24p @ 19.84 Mbps`。深入反汇编揭示了四个致命阻断点：

1. **取景与录制链路混淆**：此前修改的跳转表 `0x536497E8` 仅属于背屏取景器（`LiveViewSequencePlanner.cpp`），根本不是视频录制与 Milbeaut 硬件编码链路；
2. **4K 取景配方断言截断**：理光官方固件中，4K 配方入口 `CreateRecipeSequenceMov4kExt`（Plan 4 @ `0x536498c4`）被物理剔除，留下的是直接报错退出进程的断言桩（`assert_failed` @ `0x538ed930`）；
3. **菜单槽位误绑**：官方菜单仅注册了 1080p 24p/60p/30p，底层对应的 `m_movieResEnum` 被写死在 1080p 索引（`r2 == 0`），导致录制引擎从未进入 4K 分支。

---

## 3. 重大逆向突破：GR IV 原生内置的 4K 沉睡引擎

在反汇编对齐 Pentax K-3 III（加载基址 `0x52500000`）与 Ricoh GR IV（加载基址 `0x53000000`）的过程中，我们发现了一个决定性的事实：

> **理光 GR IV 的 `MovieProcess` 内核早已完整编译了 4K 录像分辨率与单帧 12.53MB 缓冲区！**

### 3.1 分辨率查找表（`0x53871ef4` 与 `0x53871f34`）
```arm
0x53871f0c: cmp      r2, #3
0x53871f10: moveq    r0, #0xf00      ; 3840 像素 (4K Width)
0x53871f14: movne    r0, #0x780      ; 1920 像素 (1080p Width)
...
0x53871f54: cmp      r2, #3
0x53871f58: movw     r0, #0x438      ; 1080 像素 (1080p Height)
0x53871f5c: moveq    r0, #0x870      ; 2160 像素 (4K Height)
```

### 3.2 帧缓冲区分配表（`0x53871fbc`）
```arm
0x53871fd4: cmp      r2, #3
0x53871fd8: mov      r0, #0x4000
0x53871fdc: movt     r0, #0xbf       ; 0x00BF4000 = 12,533,760 字节 = 12.53 MB (4K NV12)!
0x53871fe0: movne    r0, #0x300000   ; 0x00300000 = 3,145,728 字节 = 3.14 MB (1080p NV12)!
```

### 3.3 环形缓冲池扩展（`0x538715dc`）
```arm
0x538715dc: cmp      r1, #0
0x538715e0: movne    r0, #0xc00000   ; 12 MB 录像环形池 (4K)
0x538715e4: moveq    r0, #0x100000   ; 1 MB (普通录像)
```

**结论**：只要 `m_movieResEnum == 0`（即解析映射为 `r2 == 3`），GR IV 录像引擎会**自动输出 3840×2160 分辨率并自动分配 12.53MB 缓冲区**！
**唯一的崩溃阻断点**，是按下录像键时由 `LiveViewSequencePlanner` 执行 Plan 4 时触发了 `0x536498ec` 处的 `assert_failed` 报错！

---

## 4. 靶向缝合方案与蹦床代码注入 (Targeted Splicing & Trampoline)

为了避免整体模块移植引发外设不兼容死机，我们采用了**靶向缝合（Targeted Splicing）**技术：

```mermaid
flowchart TD
    A["LiveViewSequencePlanner::Plan"] -->|Plan 4 选中| B["0x536498c4 (原 assert_failed)"]
    B -->|b #0x53000e00 (蹦床跳转)| C["0x53000e00 (代码洞 CAVE)"]
    subgraph CAVE["0x53000e00 注入区 (4.7KB 自由空闲区)"]
        D["注入 Pentax K-3 III Plan 4 4K 配方 (28 条指令)"]
        D --> E["配置 ISP/DMA 帧宽、行高、消隐与时钟 (0x9f4..0xa38, 0xc..0x38)"]
        E --> F["movw r5, #0x1944 / movt r5, #0x53eb (恢复规划器上下文)"]
    end
    F -->|b #0x53649840 (安全跳回)| G["0x53649840 (GR4 规划器后续统一收口流程)"]
    G --> H["硬件建立 3840x2160 流水线并正常录制"]
```

### 4.1 注入代码清单
- **蹦床入口** (`0x536498c4`)：`b #0x53000e00` + NOP 填充。
- **CAVE 执行体** (`0x53000e00`)：
  - 执行 Pentax K-3 III 在 `0x52d4097c` 处的 28 条 4K 寄存器初始化指令；
  - 设置 `r5 = 0x53eb1944`；
  - `b #0x53649840` 跳回 GR IV 的通用收口流程。

---

## 5. GoPro GP2 Socionext HEVC 协议资产 (Phase 2)

从 GoPro HERO10 (GP2) 和 HERO8 (GP1) 提取的符号与驱动规约证实其与 GR IV 的 Socionext 芯片完全共享 Wave500 硬件核心：
- `H265_Wave_Initialize`
- `H265_Wave_EncOpen`
- `H265_Wave_EncGetInitialInfo`
- `H265_Wave_EncGiveCommand` (AXI / HEADER / ENC_SET_TEMP_QUEUE_IDX / ENC_SET_SEI_NAL_DATA / ENC_SET_PARA_CHANGE)
- `H265_Wave_EncRegisterFrameBuffer` / `H265_Wave_EncAllocateFrameBuffer`
- `H265_Wave_EncStartOneFrame`

相关命令集已封装于 `src/video_4k/gp2_hevc_protocol.py`，待 4K H.264 跑通后无缝切入。

---

## 6. 工具链与自动化验证 (Toolchain & Verification)

### 6.1 工具脚本
- `src/video_4k/k3_recipe_extractor.py`: 从 K-3 III 固件提取并反汇编 Plan 4 4K 配方序列。
- `src/video_4k/k3_gr4_4k_patcher.py`: 自动生成注入补丁并输出 `analysis/05_RTOS_4k_patched.bin`。
- `src/video_4k/verify_k3_4k_patch.py`: 5 项自动化闭环验证测试套件。
- `src/video_4k/gp2_hevc_protocol.py`: GoPro GP2 Socionext HEVC 协议规约参考。

### 6.2 闭环测试验证结果
运行 `python src/video_4k/verify_k3_4k_patch.py` 结果全部通过：
1. **Section size parity check**: PASSED (`20,785,856` 字节无形变)
2. **Trampoline branch to 0x53000e00**: PASSED
3. **Cave return branch to 0x53649840**: PASSED
4. **Cave payload instruction count (32 insns)**: PASSED
5. **Strict isolation check (45 modified words, 0 unauthorized)**: PASSED

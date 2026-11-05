# 理光 GR IV：片上 CEVA-CV AI DSP 协处理器唤醒与深度学习追焦固件补丁

[English](README.md) | [简体中文](README_CN.md)

[![平台: Socionext Milbeaut M10V](https://img.shields.io/badge/平台-Socionext%20Milbeaut%20M10V-007acc.svg)](#)
[![适配固件: Ricoh GR IV v1.20](https://img.shields.io/badge/目标固件-v1.20%20fwdc248b.bin-green.svg)](#)
[![版本: v1.2.0](https://img.shields.io/badge/版本-v1.2.0-blue.svg)](#)
[![架构: ARM Cortex-A7 + CEVA-CV DSP](https://img.shields.io/badge/芯片架构-ARMv7%20%2B%20CEVA--CV%20DSP-orange.svg)](#)
[![状态: 纯 CEVA-CV CNN 校验通过](https://img.shields.io/badge/验证状态-纯%20CEVA--CV%20CNN%20(双重累加和%3D0)-brightgreen.svg)](#)
[![开源协议: MIT](https://img.shields.io/badge/协议-MIT-blue.svg)](#)

本项目是针对 **理光 GR IV (GR4)** 数码相机的非官方底层固件扩展补丁。它通过破译芯片内存映射与二进制驱动协议，成功激活了片上完全闲置的 **CEVA-CV 矢量 AI DSP 硬件协处理器**（物理基地址 `0x41000000`），并将**宾得旗舰单反 Pentax K-3 Mark III 的深度学习人体/主体识别卷积神经网络**无缝移植挂接进理光 GR4 原生的 165 点片上相位差检测自动对焦（PDAF）系统。

---

## 1. 突破性发现：芯片底层硬件真相

**理光 GR IV** 与 **宾得 K-3 Mark III** 均搭载 Socionext 为理光/宾得定制的 **Milbeaut M10V** 异构多核图像处理芯片。

通过对量产版固件的底层反汇编、内存映射审计与寄存器遍历，我们揭示了一个此前从未被公开的技术真相：

> **理光 GR IV 的物理芯片完全集成了与宾得 K-3 Mark III 规格分毫不差的 CEVA-CV 矢量 AI DSP 协处理器（物理地址 `0x41000000`）。**
>
> 事实上，理光 GR4 的操作系统固件（`05_RTOS.bin` @ `0x53000000`）在开机时便内置了完整的 DSP 驱动层（`DspService` @ `0x539658c4`）、跨核心通信信箱（`DspExc`, `DspReq`, `DspSF`, `DspMtx`）以及原厂调试指令（`DSP_load`, `DSP_start`, `DSP_test`）。
>
> 然而，理光在量产发布固件中**移除了 DSP 固件分区（`06_DSP.bin`）**，导致这颗具备 512 位矢量运算能力的硬件 AI 核心在 GR4 上处于 **100% 闲置断电状态**。

```text
Socionext Milbeaut M10V 异构多核处理器芯片
┌────────────────────────────────────────────────────────────────────────┐
│  ARM Cortex-A7 双核主控 CPU (32-bit ARMv7-A @ 1.0 GHz)                 │
│  ├── eSOL T-Kernel RTOS [0x53000000] (ISP / 实时取景 / 3A / AF / UI)    │
│  └── Linux 4.9 内核     [0x013ea7e0] (网络 / PTP 通信 / 存储服务)       │
├────────────────────────────────────────────────────────────────────────┤
│  CEVA-CV 矢量 AI DSP 协处理器 [0x41000000] (512-bit SIMD / VLIW)        │
│  ├── 物理 MMU 映射窗口: 0x41000000 (8 MB 强顺序普通共享内存)            │
│  ├── DF_EX.BIN   (0x51200000, 5,251,648 字节) — CEVA-CV 算子库 + 1.14M │
│  │   ├── 分块 0 (0x51200000, 4,112,384 字节) — CEVA-CV 矢量数学核心    │
│  │   └── 分块 1 (0x516c0000, 1,139,232 字节) — K-3 III 深度神经网络权重 │
│  ├── DF_ID_S.BIN (0x515ec000,    65,536 字节) — 神经网络模型配置表     │
│  └── DF_IP.BIN   (0x515fc000,    16,384 字节) — 复位引导与中断向量入口 │
└────────────────────────────────────────────────────────────────────────┘
```

数学与内存映射的绝对吻合证明：
$$0x3EC000\text{ (DF\_EX 核心)} + 0x116220\text{ (DF\_EX 权重)} = 0x502220\text{ (5,251,648 字节)}$$
$$\text{DSP 总内存开销: } 0x502220 + 0x10000\text{ (DF\_ID\_S)} + 0x4000\text{ (DF\_IP)} = 5,333,568\text{ 字节}$$
与宾得 K-3 Mark III 解包所得的 `06_DSP.bin` 及完整深度学习卷积权重视图 **100% 完美一致**。

---

## 2. 项目架构与阶段演进

```text
                  ┌──────────────────────────────────────────────┐
                  │ 阶段 1：DSP 固件分块提取与协议适配            │
                  │   06_DSP.bin -> DF_EX / DF_ID_S / DF_IP      │
                  │   集成 1.14 MB 完整 K-3 III 神经网络权重     │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ 阶段 2：免串口开机全自动唤醒                  │
                  │   挂接 0x536520f0 -> 代码洞 0x53000e00       │
                  │   LoadDsp('C') -> Start() -> Test()          │
                  │   输出归档: fwdc248b_stage2_dsp_wake.bin      │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │ 阶段 3：实时取景全时 CEVA-CV AI 追焦 (v1.0.9)│
                  │   • 100% 纯 CEVA-CV CNN，彻底移除原厂回退    │
                  │   • AHIP 出队帧提取 + CPU D-Cache 刷新        │
                  │   • 2.0x 逆光暗部平滑增益曲线 (Y < 48)       │
                  │   • 侧脸 / 低头首帧状态播种，开机瞬时锁定    │
                  │   输出成品: fwdc248b_stage3_ai_track.bin     │
                  └──────────────────────────────────────────────┘
```

### 阶段 1：固件分块与协议重构 (`dsp_splitter.py`)
- 将 K-3 III 的 `06_DSP.bin` 按照理光底层 `DspService::LoadDsp` 解析器要求的格式打包：
  - `DF_EX.BIN` (5,251,648 字节)：分块 0（CEVA-CV 核心，4,112,384 字节）+ 分块 1（1,139,232 字节 K-3 III 卷积神经网络权重：主干骨干网 677,824 字节 @ `0x516c0000` + 分类头 461,408 字节 @ `0x517657c0`）。
  - `DF_ID_S.BIN` (65,536 字节)：64 KB 神经网络常量权值配置表，加载到 `0x515ec000`。
  - `DF_IP.BIN` (16,384 字节)：16 KB 指令复位入口向量，加载到 `0x515fc000`。
- 通过 [`verify_dsp_payload.py`](src/dsp_ai/verify_dsp_payload.py) 验证，实现对原始载荷的 100% 字节级无损复原。

### 阶段 2：免串口开机全自动唤醒 (`k3_gr4_dsp_patcher.py`)
- **专为无串口量产机身设计**：零售版相机无法引出调试串口，所有唤醒与自检流程必须在机内自主运行。
- 在实时取景初始化函数 `LiveViewProcess3aContoller`（`0x536520f0`）注入单向跳转蹦床（`b #0x53000e00`）。
- 成功调用 `LoadDsp('C')`、`Start()` 与 `Test()`，实机测试完全稳定通过。

### 阶段 3：全时纯 CEVA-CV AI 追焦管线 (`stage3_ai_patcher.py`, v1.0.9)
- **100% 纯硬件加速，彻底移除原厂 `LibAHFD` 回退**：
  - 完全移除了对 `FdLibraryService::DetectFace`（`0x5383ec84`，原厂 FotoNation）的一切调用。屏幕上出现的每一个对焦绿框，数学上 100% 保证由 CEVA-CV 硬件矢量 DSP 加速运行 K-3 III CNN 计算生成。
- **固化神经网络参数表**：
  - `k3_desc.bin` (728 字节) @ `0x53001400`：网络层拓扑结构与输入输出尺度。
  - `k3_mean.bin` (9,408 字节) @ `0x541db540`：$56 \times 56 \times 3$ 通道均值偏置。
  - `k3_std.bin`  (9,408 字节) @ `0x54217680`：$56 \times 56 \times 3$ 通道标准差激活权重。
- **双挂接点安全架构**：
  - **挂接点 1：开机状态初始化（`LiveViewProcess3aContoller` @ `0x536520f0` -> 代码洞 1 @ `0x53000d60`，84 字节）**：
    - 重构 APCS 栈帧并在单例创建时仅清零遥测区 `0x517e0100..0x517e011f`，绝不因等待 SD 卡 I/O 而阻塞相机早期 3A 初始化。
  - **挂接点 2：实时取景连续 AI 追焦（`FaceDetectionService::Task` @ `0x5386ea8c` -> 代码洞 2 @ `0x53000e00`，1,440 字节）**：
    - **构造函数清零字节 `[r4, #0x13e]` 彻底杜绝 DDR 未初始化回退 Bug**：利用构造函数（`0x5386d974`）开机必清零的 `[r4, #0x13e]` 维护开机重试状态；前 20 帧（约 `0.65s`）静默等待 SD 卡挂载，随后在解锁互斥锁 `r4 + 0x48` 的状态下每 64 帧重试 `LoadDsp('C')`（最多 30 次 / 约 `65s`），从根本上解决了 v1.0.8 冷启动 DDR 随机值导致跳过 DSP 加载的问题。
    - **AHIP 硬件完成队列出队与 D-Cache 刷新**：直接从 `AhipService::WaitFrame` 出队的完成帧描述符 `*(*(0x55080350 + 0x424))` 提取 Y/U/V 平面，并在 CPU 读取前调用 `InvalidateDataCache`（`0x538f0454`），彻底杜绝缓存陈旧像素。
    - **全画幅比例自适应下采样（3:2, 4:3, 16:9, 1:1）**：根据 `[r4, #0xfc]` 与 `[r4, #0xfe]` 动态计算源行指针与 UV 色度偏移。
    - **$C^0$ 连续 $2.0\times$ 逆光暗部平滑增益曲线**：
      $$Y' = \begin{cases} 2 \cdot Y & Y < 48 \\ 72 + \lfloor Y / 2 \rfloor & 48 \le Y < 144 \\ Y & Y \ge 144 \end{cases}$$
      大幅提升逆光面部阴影对比度，同时保持天空高光不溢出。
    - **DSP 矢量硬件推断**：通过 `SendMessage`（`0x539663c0`）与 `WaitMessage`（`0x539666dc`，超时 100 ms）派发 Message ID 4。
    - **头部通道优先解析与动态框尺寸**：优先识别人头/面部（$fg = \max(Ch1, Ch2 - 0.5\text{ logit})$），抗噪门限过滤，并根据分割面积自适应调整对焦框大小（`clamp(0x2800 + (area << 6), 0x2800, 0x5c00)`）。
    - **侧脸/低头首帧状态播种**：完整播种 `[r4, #0x100..0x10c]` = $(cx, cy, w, h)$、`[r4, #0x118..0x11c] = face_id`、`[r4, #0x13c] = 1`、`[r4, #0x121] = 0`，使侧脸与低头角度无需事先经历正脸即可在第 1 帧瞬时触发 `EVENT 0x04070001` 锁定！

---

## 3. 极速上手：刷机与使用指南

> [!IMPORTANT]
> **无需拆机、无需焊接、无需任何 USB/TTL 调试转接线。**
> 补丁完全利用相机官方固件升级通道，开机后 100% 机内自主点火与运行。

### 第 1 步：准备 SD 卡文件
1. 将 SD 卡格式化为 **FAT32** 文件系统。
2. 将以下 3 个 DSP 固件文件复制至 **SD 卡根目录 (`C:\`)**：
   - `DF_EX.BIN` (5,251,648 字节)
   - `DF_ID_S.BIN` (65,536 字节)
   - `DF_IP.BIN` (16,384 字节)
3. 将阶段 3 编译生成的固件 `output/fwdc248b.bin`（或 `output/fwdc248b_stage3_ai_track.bin`）重命名为 `fwdc248b.bin` 复制至 **SD 卡根目录**。

SD 卡根目录文件树预览：
```text
SD 卡根目录 (C:\)
├── fwdc248b.bin       (38,842,088 字节 [阶段 3 v1.0.9 纯 CEVA-CV 固件])
├── DF_EX.BIN          ( 5,251,648 字节 — CEVA-CV 执行库 + 1.14MB 深度模型权重)
├── DF_ID_S.BIN        (    65,536 字节 — 神经网络模型结构配置表)
└── DF_IP.BIN          (    16,384 字节 — 复位向量表)
```

### 第 2 步：固件卡刷升级
1. 确保相机电池电量充足，将 SD 卡插入理光 GR IV。
2. **按住相机的 `DISP` 键（或 `MENU` 键）不放**，同时按下**电源键**开机。
3. 屏幕将显示官方固件升级菜单，当前版本为 `v1.11`，更新版本显示就绪。
4. 方向键选择 **“是”** 确认升级，静候进度条跑满并自动关机重启。

### 第 3 步：体验 AI 追焦与物理验证
- 开机约 `0.7` 秒内，机内状态机即完成 CEVA-CV DSP 与 1.14 MB 权重的全自动点火与校验。
- 无论正脸、90° 极限侧脸、低头还是强逆光人脸，画面中的相位对焦框均会立刻吸附锁定。
- **100% 纯硬件 CNN 物理验证方法**：若将 SD 卡上的 `DF_EX.BIN` 临时移除或改名，开机后屏幕将**完全不出现任何人脸对焦框**（证明原厂算法已被彻底断开）；放回文件后立刻恢复识别。

---

## 4. 安全防护机制与防变砖救砖指南

### 应急恢复救砖指南（若相机异常无法开机）
> [!TIP]
> **您的相机绝不会永久变砖！**
> 本项目**绝对未修改**相机的引导加载程序分区（`00_BOOTPARA.bin` 至 `04_BOOT.bin` / IPL）。
> 理光相机的底层应急升级模式固化在片上 BootROM / IPL 中，其执行优先级远高于主系统 RTOS。即使 RTOS 代码洞有任何语法异常，底层卡刷模式依然 100% 正常运行。

**救砖步骤：**
1. **彻底断电**：扣出电池等待 10 秒后重新装入。
2. **准备官方固件**：将官方未经修改的原厂 `v1.11` 固件 `fwdc248b.bin`（或阶段 2 验证固件 `fwdc248b_stage2_dsp_wake.bin`）拷贝至 FAT32 SD 卡根目录。
3. **强制触发硬件卡刷模式**：
   - 确保相机彻底处于关机状态。
   - **长按住 `MENU` 键（或 `DISP` 键）**。
   - 保持按住不放的同时，轻按一次**电源键**。
   - 相机会无视损坏的 RTOS，直接点亮屏幕进入官方 `Firmware Update` 强制刷机界面。
   - 选择 **“是”** 刷回官方固件，相机瞬间恢复如初！

---

## 5. 源码仓库结构

```text
.
├── analysis/
│   ├── dsp_stage3_manifest.json     # 阶段 3 发布清单与反汇编转储
│   ├── dsp_wake_manifest.json       # 阶段 2 发布清单
│   ├── rtos_decompilation_audit.md  # GR4 RTOS 深度逆向反汇编报告
│   └── shellcmd_symbols.csv         # 651 个经验证的 RTOS 导出符号表
├── docs/
│   ├── FEAT_DSP_STAGE3_AI_TRACK.md  # 阶段 3 完整白皮书
│   ├── FEAT_DSP_AI_WAKE.md          # 阶段 2 完整白皮书
│   ├── FEAT_K3_AF_PORT.md           # 宾得 K-3 III 自动对焦移植报告
│   ├── RELEASE_NOTES_v1.0.5.md      # v1.0.5 版本发布说明
│   └── RELEASE_NOTES_v1.0.9.md      # v1.0.9 版本发布说明
├── src/
│   └── dsp_ai/
│       ├── build_stage3_firmware.py # 阶段 3 固件构建与容器封装器
│       ├── stage3_ai_patcher.py     # 阶段 3 纯 CEVA-CV 代码洞注入器
│       ├── build_dsp_firmware.py    # 阶段 2 固件构建器
│       ├── k3_gr4_dsp_patcher.py    # 阶段 2 汇编注入器
│       ├── dsp_splitter.py          # 06_DSP.bin 分块提取工具
│       ├── verify_dsp_payload.py    # 分块字节无损复原校验器
│       ├── k3_desc.bin              # 提取自 K-3 III 的神经网络描述符 (728 B)
│       ├── k3_mean.bin              # 提取自 K-3 III 的通道均值矩阵 (9,408 B)
│       └── k3_std.bin               # 提取自 K-3 III 的通道标准差矩阵 (9,408 B)
├── tools/
│   ├── fw_container.py              # LZSS 容器解包、打包与双重累加和校验器
│   ├── rtos_analyzer.py             # RTOS 交叉引用与符号解析器
│   └── linux_analyzer.py            # Linux rootfs 解析器
└── README_CN.md
```

---

## 6. 从源码构建

```bash
# 自动切分 DSP 分块、固化神经网络参数、编译注入代码洞并生成最终卡刷固件：
python src/dsp_ai/build_stage3_firmware.py
```

---

## 7. 底层技术地址速查表

| 函数 / 组件符号 | 虚拟地址 (VA) | 功能说明 |
| :--- | :--- | :--- |
| `LiveViewProcess3aContoller` | `0x536520f0` | 挂接点 1 入口：开机非阻塞状态区清零 (`b #0x53000d60`) |
| 代码洞 1 (Cave 1) | `0x53000d60` | 84 字节：重构 APCS 栈帧并清零 `0x517e0100..0x517e011f` 遥测状态 |
| `FaceDetectionService::Task` | `0x5386ea8c` | 挂接点 2 入口：逐帧全时纯 CEVA-CV AI 对焦循环 (`b #0x53000e00`) |
| 代码洞 2 (Cave 2) | `0x53000e00` | 1,440 字节：安全开机重试 + AHIP 出队 + D-Cache 失效 + DSP 调度 + 逆光增益 + 结果注入 |
| 完成态 AHIP 描述符 | `*(*(0x55080350 + 0x424))` | `AhipService::WaitFrame` 正常出队的完成帧（`+0x04` Y, `+0x08` U, `+0x0c` V） |
| `InvalidateDataCache` | `0x538f0454` | CPU 读取取景帧前使 L1/L2 数据缓存失效 |
| `FlushDataCache` | `0x538f04c4` | CPU 写入输入 RGB 张量后写回数据缓存以供 DSP DMA 读取 |
| `DspFactory::GetDspService()` | `0x539658c4` | 获取片上 CEVA-CV `DspService` 驱动单例指针 |
| `DspService::LoadDsp` | `0x53966d74` | 从 SD 卡根目录 (`C:\`) 载入 `DF_EX.BIN`, `DF_ID_S.BIN`, `DF_IP.BIN` |
| `DspService::Start` | `0x53966214` | 解除 DSP 复位，从 `0x515fc000` 启动矢量计算核心 |
| `DspService::Test` | `0x53966f18` | 执行硬件握手自检 |
| `DspService::SendMessage` | `0x539663c0` | 派发 Message ID 4（神经网络卷积推断请求） |
| `DspService::WaitMessage` | `0x539666dc` | 阻塞等待 DSP 完成推断信号量（超时 100 ms） |
| `m_DetectedFaceResult` | `[FaceDetectionService, #0x78]` | 100 字节人脸/主体结构体数组（Q8 坐标、眼部、置信度等） |
| `FdLibraryService` | `[FaceDetectionService, #0x38]` | 原厂服务句柄，`+0x30` 保存识别目标数 `face_count` |
| `UpdateFaceDetectionResult` | `0x5386e0e4` | 向 LCD 取景渲染线程与 165 点 PDAF 驱动派发对焦坐标 |
| 原厂 FotoNation `DetectFace` | `0x5383ec84` | **在 v1.0.9 中已 100% 断开移除**（零回退） |

---

## 8. 版本更新履历

### v1.0.9 (当前最新版本)
- **100% 纯 CEVA-CV CNN，彻底移除原厂回退**：完全断开并移除对 `FdLibraryService::DetectFace` (`0x5383ec84`) 的调用，确保屏幕上所有对焦框 100% 由 CEVA-CV 硬件加速 CNN 计算生成。
- **根治未初始化 DDR `0x517e0104` 导致的开机回退原厂 Bug**：Cave 1 移除非必要的开机阻塞加载；Cave 2 利用构造函数每次开机必定清零的 `[r4, #0x13e]` 跟踪开机重试状态，前 20 帧（约 `0.65s`）等待 SD 卡挂载，随后每 64 帧重试 `LoadDsp('C')` 最多 30 次（约 `65s`），并在 I/O 期间释放互斥锁 `r4 + 0x48`。
- **AHIP 硬件完成出队帧提取与 D-Cache 失效刷新**：读取 `*(*(0x55080350 + 0x424))` 出队指针，并在 CPU 读取前执行 `InvalidateDataCache` (`0x538f0454`)，杜绝陈旧缓存像素。
- **全画幅比例自适应下采样（3:2, 4:3, 16:9, 1:1）**：动态适配 `[r4, #0xfc]` 与 `[r4, #0xfe]`，保证各种构图比例下的张量准确无畸变。
- **$C^0$ 连续 $2.0\times$ 逆光暗部平滑增益曲线**：$Y < 48 \to 2Y$，$48 \le Y < 144 \to 72 + Y/2$，大幅增强强逆光场景下的面部阴影对比度。
- **头部通道优先解析与动态框尺寸**：优先识别人头/面部（$fg = \max(Ch1, Ch2 - 0.5\text{ logit})$），根据目标分割面积自适应调整对焦框大小（`clamp(0x2800 + (area << 6), 0x2800, 0x5c00)`）。
- **侧脸/低头首帧状态播种**：完整播种 `[r4, #0x100..0x10c]` 等字段，绕过 `SelectMainFace` 冷启动拒绝，实现侧脸与低头开机第 1 帧瞬时锁定。
- **固件校验码**：`fwdc248b.bin`（38,842,088 字节，SHA-256：`35cd54790a81734055834db1c97c54ef9b6740789aaaf3f3d749bed7e997d7d6`）。

### v1.0.8
- **移除阶段 1 预检**：取消 FotoNation 正脸过滤，开启 CEVA-CV CNN 逐帧推断。
- **初步实现非正脸首帧跟踪标志播种**。

### v1.0.7
- **修复原厂 ROM 中 `DspService::LoadDsp` 路径硬编码 Bug**：修正 `0x53966eb0` 与 `0x53966ef4` 错误传递 `"A:\DF_ID_S.BIN"` 与 `"A:\DF_IP.BIN"` 的问题。

### v1.0.6
- **加载完整 1.14 MB K-3 III CNN 权重**：`DF_EX.BIN` 扩展包含分块 0（核心）与分块 1（权重）。
- **重构 YUV420 到 3 平面 RGB 输入张量与 3 通道 int16_t 热力图解析管线**。

### v1.0.5
- **修正 SD 卡盘符参数（`'A'` -> `'C'`）**。
- **通过 `p_FdEngine` 动态解析预览帧物理显存地址**。

---

## 9. 权利声明与开源协议

- **免责声明**：本项目为技术爱好者出于学习、逆向工程与学术研究目的开展的独立开源研究。刷机具有潜在风险，尽管我们设计了极尽严苛的硬件防变砖保护策略与双重校验累加和机制，作者对使用本工具所导致的任何直接或间接设备故障概不承担责任。
- **版权声明**：本仓库仅分发原创的反汇编解析工具、汇编注入脚本与数学逻辑规范，不分发任何受理光（Ricoh Imaging Company, Ltd.）版权保护的私有固件二进制。用户须使用自身合法持有的相机固件进行构建。
- **开源协议**：本项目基于 MIT License 开源，详见 [LICENSE](LICENSE)。

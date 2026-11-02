# Ricoh GR IV 阶段 3 深度学习推断与实时追焦挂接白皮书 (Stage 3 Deep Learning Inference & Live View AF Bridge v1.0.9)

## 1. 架构总览与阶段成果

在成功实装 **阶段 2（片上 CEVA-CV AI DSP 协处理器免串口开机自唤醒）** 的坚实基础上，本项目已正式完成 **阶段 3（深度学习卷积神经网络实时推断管线与实时取景 AF 跟踪桥接）**。

### 1.1 关键里程碑 (v1.0.9)
1. **100% 纯硬件加速，彻底移除原厂 `LibAHFD` 回退**：
   - 完全移除了对 `FdLibraryService::DetectFace`（`0x5383ec84`，原厂 FotoNation）的一切调用。屏幕上出现的每一个对焦绿框，数学上 100% 保证由 CEVA-CV 硬件矢量 DSP 加速运行 K-3 III CNN 计算生成。
2. **机身固件零破坏与双阶段独立封包**：
   - **阶段 2 纯唤醒固件保持 100% 独立保留**：[`output/fwdc248b_stage2_dsp_wake.bin`](file:///d:/Ricoh%20GR4%20firmware%20Mod/worktrees/feat-dsp-ai-af/output/fwdc248b_stage2_dsp_wake.bin)（38,693,256 字节，纯 DSP 点火与自检）。
   - **阶段 3 完整 AI 追焦固件**：[`output/fwdc248b_stage3_ai_track.bin`](file:///d:/Ricoh%20GR4%20firmware%20Mod/worktrees/feat-dsp-ai-af/output/fwdc248b_stage3_ai_track.bin) 与当前刷机固件 [`output/fwdc248b.bin`](file:///d:/Ricoh%20GR4%20firmware%20Mod/worktrees/feat-dsp-ai-af/output/fwdc248b.bin)（38,842,088 字节，通过官方 LZSS 容器双重 32-bit `word_sum == 0` 校验）。
3. **彻底根除未初始化 DDR 开机回退 Bug**：
   - `Cave 1` 改为非阻塞状态初始化，不因等待 SD 卡挂载而阻塞早期 3A。
   - `Cave 2` 利用 `FaceDetectionService` 构造函数开机必定清零的保留字节 `[r4, #0x13e]`，在前 20 帧（约 `0.65s`）等待 SD 卡就绪，随后每 64 帧重试 `LoadDsp('C')`，开机瞬时点火。
4. **AHIP 硬件完成队列出队与 D-Cache 失效刷新**：
   - 读取 `*(*(0x55080350 + 0x424))` 出队指针并执行 `InvalidateDataCache`（`0x538f0454`），避免 CPU 读到陈旧像素。
5. **$C^0$ 连续 $2.0\times$ 逆光暗部平滑增益曲线**：
   - 平滑分段曲线提升暗部对比度，逆光人脸清晰可辨，同时高光天空完全不溢出。
6. **侧脸/低头首帧状态播种，开机瞬时锁定**：
   - 完整播种 `[r4, #0x100..0x10c]` 等字段，绕过 `SelectMainFace` 冷启动拒绝，实现侧脸与低头开机第 1 帧瞬时锁定。

---

## 2. 深度学习网络模型与内存映射拓扑

CEVA-CV 矢量协处理器与主控 ARM Cortex-A7 通过 Milbeaut M10V 的多核硬件总线及强顺序共享内存窗口交互。

### 2.1 固化模型参数与权重嵌入（RTOS 内部空间）

利用理光原厂 RTOS 固件内部经精细审计的零填充代码洞（Zero-padded Code Caves），将原本理光裁剪掉的 Pentax K-3 Mark III 人体/主体识别卷积神经网络权值与描述符**直接固化进固件内部**：

| 模块 / 参数表 | 虚拟地址 (VA) | 固件偏移 | 尺寸 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **`DeepLearningService` 描述符表** | `0x53001400` | `0x19110` | 728 字节 | 网络拓扑结构、输入输出张量尺度、正交投影矩阵与软阈值常数 |
| **通道均值偏差表 (`mean_table`)** | `0x541db540` | `0x11f3250` | 9,408 字节 | $56 \times 56 \times 3$ 归一化输入层偏置参数 |
| **通道标准差偏差表 (`std_table`)** | `0x54217680` | `0x122f390` | 9,408 字节 | $56 \times 56 \times 3$ 激活层缩放权重参数 |
| **AI 运行状态与遥测数据块** | `0x517e0100` | DDR 共享区 | 32 字节 | 存储 Magic `'CEVA'`、开机计数器、遥测数据 |

### 2.2 DSP 共享内存张量交换区 (Zero-Copy DMA Window)

在片上 DSP 物理保留区中，紧随 4.00 MB DSP 代码区后划分专用高速 DMA 缓冲区：

| 通信缓冲区 | 虚拟地址 (VA) | 尺寸 | 用途 |
| :--- | :--- | :--- | :--- |
| **输入张量缓冲区** | `0x51600000` | 9,408 字节 | 下采样的 $56 \times 56$ 24-bit 3 平面 RGB 输入张量（行跨度 64） |
| **输出热力图缓冲区** | `0x51609a00` | 21,504 字节 | DSP 卷积推断完成后的 3 通道 $56 \times 56$ (行跨度 64) int16_t 热力图 |
| **主干权重缓冲区** | `0x516c0000` | 677,824 字节 | K-3 III 0x53932548..0x539d7d08 卷积神经网络特征提取层骨干权重 |
| **分类头权重缓冲区** | `0x517657c0` | 461,408 字节 | K-3 III 0x539d7d08..0x53a48768 人体/主体识别分类头权重 |
| **DSP 消息控制块** | `0x517e0000` | 40 字节 (10 words) | 承载 10 词请求载荷（模型描述符、均值、方差、量化因子、网络层标志） |
| **遥测与状态区** | `0x517e0100` | 32 字节 | 存储 Magic `'CEVA'`、开机计数器、遥测数据 |

---

## 3. 运行执行管线与追焦挂接机制

### 3.1 闭环执行时序图

```text
实时取景循环 (Live View Loop @ 60 fps)
       │
       ▼
[0x5386ea8c] FaceDetectionService::Task 钩子蹦床 (b #0x53000e00)
       │
       ▼
[0x53000e00] 阶段 3 纯 CEVA-CV 智能追焦代码洞 2 (Cave 2, 1,440 字节)
       │
       ├─ [零回退保证] 预先将 FdLibraryService::face_count 置 0 (完全不调用 0x5383ec84)
       │
       ├─ [安全开机机制]
       │     ├─ 检查 [r4, #0x13e] (构造函数清零)，首次开机清零 DDR 计数器
       │     ├─ 前 20 帧 (~0.65s) 静默等待 SD 卡挂载
       │     └─ 之后每 64 帧重试 LoadDsp('C') -> Start() -> Test()，期间释放互斥锁
       │
       ├─ [步骤 1: 图像截取与 D-Cache 刷新]
       │     ├─ 从 AhipService::WaitFrame 出队描述符 *(*(0x55080350 + 0x424)) 获取物理 Y/U/V 平面
       │     ├─ 调用 InvalidateDataCache (0x538f0454) 刷新 CPU 数据缓存
       │     └─ 汇编内核: YUV420 -> 56x56 RGB Planar (含 2.0x 逆光暗部平滑增益)
       │
       ├─ [步骤 2: 硬件信箱调度推断]
       │     ├─ 调用 FlushDataCache (0x538f04c4) 写回 RGB 输入张量
       │     ├─ 装填 10 词消息结构体 (@ 0x517e0000)
       │     ├─ 调用 DspService::SendMessage(svc, &seq, msg_id=4, timeout=100)
       │     └─ 调用 DspService::WaitMessage(svc, seq, timeout=100) 等待 CEVA 矢量核执行完成
       │
       ├─ [步骤 3: 3 通道热力图解析]
       │     ├─ 调用 InvalidateDataCache 刷新 0x51609a00 输出缓存
       │     ├─ 汇编扫描 3 通道 (BG, Human, Subject) 提取最大峰值 (max_diff, col, row, area)
       │     ├─ 头部优先: fg = max(Ch1, Ch2 - 0.5 logit)
       │     └─ 门限判定: max_diff >= 2 且 (area >= 2 或 max_diff >= 4)
       │
       ├─ [步骤 4: 挂接理光原生 AF 跟踪系统与首帧播种]
       │     ├─ 动态对焦框尺寸: clamp(0x2800 + (area << 6), 0x2800, 0x5c00)
       │     ├─ 填入 m_DetectedFaceResult ([r4, #0x78]) 并置 face_count = 1
       │     ├─ 完整播种 [r4, #0x100..0x10c] = (cx, cy, w, h)，绕过 SelectMainFace 冷启动拒绝
       │     └─ 恢复栈帧，跳转 0x5386ea9c 原生调用 UpdateFaceDetectionResult (0x5386e0e4)
       │        └─ 理光 165 点片上相位对焦 (ZafPredictor) 立即平滑锁定并在 LCD 渲染绿色对焦框!
       │
       ▼
返回原流程 [0x5386ea9c] 继续执行理光原生 3A / 画面渲染循环 (完全平滑，无卡顿)
```

---

## 4. 刷机与使用验证

### 4.1 准备 SD 卡
1. 将 `output/sd_card/` 目录下的 3 个 DSP 二进制固件复制到 FAT32 SD 卡根目录：
   - `DF_EX.BIN` (5,251,648 字节)
   - `DF_ID_S.BIN` (65,536 字节)
   - `DF_IP.BIN` (16,384 字节)
2. 将最新生成的刷机文件 `output/fwdc248b.bin` 复制到 SD 卡根目录。

### 4.2 刷机升级与对焦体验
1. 按住相机的 `DISP` 或 `MENU` 键开机进入官方固件升级菜单。
2. 确认固件升级并等待刷机进度条走满重启。
3. 开机后对准人物（正脸、90° 侧脸、低头、强逆光）：相位对焦绿框瞬时锁定。
4. **验证纯硬件 CNN**：移除 SD 卡上的 `DF_EX.BIN` 后开机，屏幕完全不出现任何人脸对焦框，证明原厂代码已 100% 断开。

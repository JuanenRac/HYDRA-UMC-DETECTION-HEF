<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-DETECTION-HEF banner" width="100%">
</p>

# 🎯 HYDRA-UMC-DETECTION-HEF

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | 🇨🇳 <b>简体中文</b> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 📦 硬件加速工业模型库（Hailo-8 / Hailo-10）

<p align="left">
  <img src="https://img.shields.io/badge/Licencia-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Format-HEF-FF6F00.svg" alt="HEF">
  <img src="https://img.shields.io/badge/Models-YOLOv8%20%2F%20YOLOv10-00A4EF.svg" alt="YOLO">
  <img src="https://img.shields.io/badge/Stage-Skeleton-lightgrey.svg" alt="Skeleton stage">
</p>

---

## 1. 🛠️ 技术概述

**HYDRA-UMC-DETECTION-HEF** 旨在成为一个精心策划的高性能神经网络模型库和
工具链，这些模型被编译为 **Hailo 可执行格式（HEF）**，并针对工业微工厂
环境（电子装配、SMD 贴片和刀头验证）进行调优。

这是集成父项目 **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** 4 个子项目之一：本项目仅负责模型编译和版本管理——`.hef` 模型的实际服务、运行副本由持有 Hailo-8 设备句柄的父项目加载和执行，而非本项目自身。

### 关键要点

* 🛠️ **工业检测（计划中）：** 针对 PCB 组件、焊点和机械缺陷的模型。
* 📐 **基准点对位（计划中）：** 用于抓取放置同步的高精度锚点。
* ⚡ **量化性能（计划中）：** 针对 Hailo-8/Hailo-10 NPU 的 INT8/INT4 变体，实现亚 10ms 推理。
* 🤖 **姿态估计（计划中）：** 用于机械臂关节跟踪的关键点检测。
* 🧩 **为何作为独立项目存在：** 编译和管理模型版本是一项数据/机器学习工作流，与提供服务的运行时进程完全不同——将工具链保持在此处，意味着一次糟糕的编译永远不会危及正在运行的感知节点，模型可以在到达 [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) 之前离线迭代和验证。

**诚实说明——今天实际运行的内容：** 本仓库目前处于骨架阶段。真正的入口点
（`src/hydra_umc_detection_hef/main.py`）会打印项目名称、已安装的版本号，
以及一行角色说明，然后以退出码 0 结束。上文描述的 ONNX 导出、Hailo
Dataflow Compiler 量化、HAR/HEF 打包或模型注册/版本管理逻辑均尚未在代码
中实现。具体已交付内容请参见 [`CHANGELOG.md`](CHANGELOG.md)，尚待完成的
内容请参见下方"当前状态与后续步骤"章节。

---

## 2. 🔄 目标模型编译流程

下图是本骨架项目正朝其构建的目标工具链，而非当前已运行的流水线。

```mermaid
flowchart LR
    TRAIN["Training (PyTorch/YOLO)"] --> ONNX["Export to ONNX"]
    ONNX --> DFC["Hailo Dataflow Compiler"]
    DFC --> HAR["Quantization (HAR)"]
    HAR --> HEF["HEF Binary"]
    HEF --> NODE["HYDRA-UMC-VISION-NODE"]
```

---

## 3. 🧠 高级技术信息

### 为何这里没有 `hardware/`/`firmware/`，以及为何 `os/`/`models/` 仍位于父项目中

本项目交付模型文件及编译它们的工具，而非物理设备——因此，与 Vision AI
Node 系列的其他项目一样，它不携带 `hardware/`/`firmware/` 文件夹。它也
不携带 `os/` 或 `models/`，即使 `.hef` 文件确实是在这里*生成*的：运行时
加载到 Hailo-8 NPU 上的*实际提供服务、正在运行*的副本，仅存在于集成父
项目 [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) 中，因为那是持有 Hailo-8 设备句柄的进程。本项目自身的 `build/` 是编译后的工具链输出在发布到那里之前应落地的地方。

### 编译流程是先于代码的设计决策

上图已经确定了预期的流水线形态：PyTorch/YOLO 训练在其他地方进行（超出
本仓库范围），模型导出为 ONNX，通过 Hailo Dataflow Compiler 进行
INT8/INT4 量化（生成 `.har`），最后打包为 [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) 所消费的 `.hef` 二进制文件。在编写工具链代码之前，现在就决定并记录这一形态，可以避免最终实现日后不得不临时拼凑模型注册/版本管理方案。

### 本骨架中已做出的设计决策

* **版本从已安装的包元数据读取，而非硬编码** —— `main.py` 调用 `importlib.metadata.version("hydra-umc-detection-hef")`，而非第二个 `__version__` 字符串，因此 `bump_version.py` 永远只有一处需要修改。
* **里程表式递增只自动触及 `PATCH`/`MINOR`** —— `bump_version.py` 在 `PATCH` 超过 9 时进位到 `MINOR`，`MINOR` 超过 9 时进位到 `MAJOR`，但从不自行递增 `MAJOR`；与 `HYDRA-UMC-EDITOR-URDF/bump_version.py` 和 `HYDRA-UMC-SUITE/bump_version.py` 的惯例相同。

---

## 📂 目录结构

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # 源代码（hydra_umc_detection_hef 包）
├── docs/                # 文档与验证报告
├── build/               # 构建输出（本地 .venv + 未来的 HEF 工具链输出）
├── images/              # 媒体与图表
├── scripts/             # 实用脚本
├── pyproject.toml       # 包元数据、依赖项、里程表版本号
├── bump_version.py      # 里程表式版本递增（由 build.sh/.bat 运行）
├── build.sh / build.bat # venv + 可编辑安装 + 编译检查
├── run.sh / run.bat     # 从本地 venv 运行入口点
└── CHANGELOG.md         # 逐版本历史（里程表方案，无日期）
```

没有 `hardware/`、`firmware/`、`os/` 或 `models/` 文件夹——原因见上方
"高级技术信息"。`os/` 和 `models/` 仅存在于集成父项目
[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) 中；本项目自身的 `build/` 是其 HEF 工具链输出在发布到那里之前应落地的地方。

---

## 🏗️ 构建与运行

### 前提条件

* `PATH` 中存在 **Python 3.10 或更新版本**（脚本先尝试 `python3`，再回退到 `python`）。
* 目前不需要任何 ONNX/Hailo Dataflow Compiler 工具——此阶段**没有任何第三方运行时依赖**（`pyproject.toml` 中 `dependencies = []`）。
* 本地虚拟环境（`.venv/` 下）需要数十 MB 磁盘空间。

### 逐步说明

```bash
# Linux / macOS
./build.sh
```

1. **里程表式版本递增** —— 运行 `bump_version.py`，每次构建时在 `pyproject.toml` 中递增 `PATCH`（按上述规则进位到 `MINOR`/`MAJOR`）。
2. **虚拟环境** —— 若 `.venv/` 不存在则创建；否则复用。
3. **可编辑安装** —— `pip install -e .`，使 `src/` 下的修改立即生效，并注册 `hydra-umc-detection-hef` 控制台入口点。
4. **编译检查** —— `python -m compileall -q src` 对 `src/` 下每个文件进行字节码编译，在整个生态系统范围内捕获语法错误。

`set -euo pipefail` 会在第一个失败步骤处停止脚本；只有全部 4 个步骤均
成功时才打印 `== Build OK ==`。

```bash
./run.sh
```

在 `.venv` 内定位解释器（同时处理 POSIX 和 Windows 的 `.venv` 目录结构），
运行 `python -m hydra_umc_detection_hef.main`，打印名称 + 版本 + 角色。

```bat
:: Windows - 步骤相同，批处理语法
build.bat
run.bat
```

### 故障排查

* **找不到 `python`/`python3`** —— 安装 Python 3.10+ 并确保其在 `PATH` 中。
* **`compileall` 失败** —— 意味着 `src/` 下确实引入了语法错误；构建会故意在不触及安装的情况下停止。
* **`run.sh`/`run.bat` 提示"未找到 `.venv`"** —— 先至少运行一次 `build.sh`/`build.bat`。
* **可编辑安装过期** —— 删除 `.venv/` 并重新构建；很少需要这样做。

---

## 🚀 当前状态与后续步骤

**今天已实现的内容：** 一个真实的、可安装的 Python 包，带有已验证的入口点
（具体已捕获的构建/运行输出见 [`CHANGELOG.md`](CHANGELOG.md)），以及一个
已接入构建流程的里程表式版本递增机制。

**仍待完成的内容（顺序不分先后，无既定时间表）：**

* 从已训练的 PyTorch/YOLO 模型进行真实的 ONNX 导出步骤。
* 集成 Hailo Dataflow Compiler 以进行 INT8/INT4 量化。
* HAR/HEF 打包以及版本化的模型注册表。
* 将编译好的 `.hef` 输出发布到 [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) 的 `models/` 文件夹中。

---

## 🔗 相关项目

本项目是同一作者（JuanenRac / Electro Hobby 3D）打造的更大规模机器人生态
系统的一部分，涵盖固件、控制软件、AI 节点和车队工具。值得了解，因为某个
需求实际上可能是关于这些项目之一，而非本仓库。

### 项目族

**父项目：** **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** —— 将这些 HEF 模型加载到其 Hailo-8 NPU 上的集成父项目。

**同族项目：**
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** —— 捕获并预处理父项目所消费的摄像头画面。
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** —— 使用本项目编译的模型，将父项目的感知结果转化为入侵检测和 E-STOP 触发。
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** —— 将父项目的感知结果转化为运动学位姿修正。

### 直接相关（项目族之外）

- **[URTC](https://github.com/JuanenRac/URTC)** —— URTC 自身刀头的视觉识别依赖于本项目编译的模型。

### 生态系统的其余部分

**HYDRA-UMC 平台** —— 多机器人微工厂单元
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** —— 协调最多 8 条机械臂的 CM5 + STM32H745 主板。
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** —— 每个控制客户端所对接的 Express/WebSocket 后端。
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** —— 基于 Web 的控制仪表盘，多机器人 3D 可视化。
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** —— 通过 Wi-Fi/蓝牙的 Android 控制应用。
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** —— 基于 Flutter 构建的 iOS/iPadOS 控制应用。
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** —— 桌面端集群指挥中心（Python/PySide6）。
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** —— 用于机器人目录的桌面端 URDF 模型编辑器。
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** —— 机载 DSI 触摸屏的原生触控 UI。

**URTC 平台** —— 每台 HYDRA-UMC 机械臂搭载的工具头控制器
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** —— 桌面端 CAN-OTA + SWD/JTAG 刷写工具。
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** —— 桌面端实时 CAN 总线诊断工具。
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** —— 通过 Web Serial API 的浏览器端替代方案。

**🧠 认知 AI 节点（Hailo-10）**
- [HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)
- [HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)
- [HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)
- [HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)
- [HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)

**🐝 编排与集群**
- [HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)
- [HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)
- [HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)
- [HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)
- [HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)

**🎮 数字孪生与仿真**
- [HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)
- [HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)
- [HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)
- [HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)

**📊 数据与分析**
- [HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)
- [HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)
- [HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)
- [HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)

**🏭 工业网关**
- [HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)
- [HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)
- [HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)
- [HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)

**🛠️ 配套工具**
- [URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)
- [URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)
- [HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)
- [HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)
- [HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)

---

## 👤 作者
**JuanenRac**（Electro Hobby 3D）
📧 electrohobby3d@gmail.com

## 📜 许可证
GPL-3.0 —— 详见 LICENSE。

## 关联项目

> Canonical public ecosystem relationship map.

**Direct integrations:**
[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS) · [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) · [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) · [URTC](https://github.com/JuanenRac/URTC) · [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) · [HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER) · [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)

**Platform and contracts:**
[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS) · [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)

**Rest of the ecosystem:**
All remaining public repositories are grouped by the seven ecosystem layers in the [JuanenRac ecosystem dashboard](https://juanenrac.github.io/JuanenRac/).

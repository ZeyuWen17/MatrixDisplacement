# MatrixDisplacement — 矩阵位移法结构分析与可视化教学系统

**当前版本：V1.1.0（源码开发版，Windows 正式验收尚未完成）**  
**开发语言：** Python 3 / NumPy / Matplotlib / PySide6  
**计算单位：** m、N、Pa、m²、m⁴、N·m、rad  
**主要用途：** 结构力学课程学习、二维杆系线弹性静力分析、教学矩阵过程展示。

> **验收声明（2026-11-06）**：本版本基于 V1.0 源码推进。当前环境中**259 项测试通过，5 个 Qt 测试模块因缺少 PySide6 被跳过**；可执行的旧数值测试、恢复文件完整性/故障注入测试和无界面示例通过。**没有在当前环境启动真实 PySide6 窗口，没有在 Windows 上构建或运行 EXE，也没有执行 GitHub Actions 工作流**。不能将“源码已实现”“离屏测试脚本已编写”误认为“Windows 已验收”。详细限制见第 9 节。

## 1. 用户原始需求及长期目标

1. **结构类型**：连续梁、平面桁架、平面刚架；将来扩展空间桁架、空间刚架。
2. **技术方案**：Python；先建立可靠的矩阵位移法数值计算内核，再开发图形化建模和结果显示。
3. **数值计算**：单元刚度矩阵、坐标转换、整体刚度自动组装、自由度管理、节点位移、支座反力、杆端内力。
4. **后处理**：轴力/剪力/弯矩图、变形图、查询与 CSV/PNG 数据输出。
5. **教学 + 快速模式**：教学模式保留组装与中间矩阵、计算报告；快速模式不保留大量中间记录，二者共用求解算法。
6. **持续交付规则**：每阶段更新中文 README、CHANGELOG、验证测试和源代码 ZIP；无法完成或无法验证的事项必须明确记录。

## 2. 历次版本完成记录

| 版本 | 已完成的主要能力 |
|---|---|
| V0.1 | `Frame2D` 二维刚架、自由度编号、单元/整体刚度、位移与杆端内力 |
| V0.1.1 | 非有限数值检查、部分机构/病态刚度矩阵数值筛查 |
| V0.2 | 均布荷载、杆内集中力、一致等效节点荷载、固端力恢复 |
| V0.3 | 任意截面 N/V/M、跨内位移与变形、结果 PNG |
| V0.4 | 杆端转角释放、独立桁架 `Truss2D`、刚架—桁架混合模型 |
| V0.5 | 水平连续梁 `Beam2D`、JSON 保存读取、教学报告 |
| V0.6 | 线性分布荷载、整体刚度分步组装记录、CSV 数据导出 |
| V0.7 | PySide6 图形界面源码原型、节点/杆件/支座/荷载编辑与绘图 |
| V0.8 | 拖拽、逐项荷载编辑、撤销/重做、杆件属性表、截面查询 |
| V0.9 | 画布平移/缩放、尺寸标注、内力图点选、Windows 构建脚本 |
| V1.0 | 框选/多选、批量移动/删除/属性编辑、基础标签避让 |
| **V1.1** | **自动保存、崩溃草稿恢复、原子手动保存、错误日志、Windows 离屏构建验收准备** |

以上功能的**源码实现范围**不等于所有功能都已在 Windows 窗口中通过鼠标实测；V0.7 起的 Qt 操作仍需实机验收。

## 3. V1.1 完成的工作

### 3.1 自动保存与崩溃恢复（新）

- `matrix_displacement/recovery.py` 新增 Qt 独立的 `RecoveryStore`。
- 只在**模型有未保存的修改**时建立快照。GUI 编辑停止后约 **2.5 秒**写一次（防抖），另设 **60 秒**定时兜底。
- Windows 默认恢复目录：`%LOCALAPPDATA%\MatrixDisplacement\recovery\`；其他平台使用用户本地状态目录。测试时可使用绝对路径环境变量 `MATRIX_DISPLACEMENT_RECOVERY_DIR` 隔离目录。
- 每个打开的程序会话使用独立 `session-<UUID>.json`，避免不同会话在同一个恢复文件中相互覆盖。**多个程序同时编辑同一个源文件时，仍不具备真正的冲突合并能力。**
- 快照保存 UTC 时间、原始 JSON 路径、模型数据、独立恢复格式版本与 SHA-256 内容校验；格式不使用 pickle、eval 或可执行对象反序列化。
- 写入使用**同目录临时文件 + fsync + `os.replace()` 原子替换**；在中断/写入异常时尽可能保留旧的完整快照。
- 程序启动时扫描历史草稿；可选择 **恢复 / 删除 / 暂不处理**。也可用“**文件 → 恢复自动保存草稿...**”再打开选择器。
- **恢复只在内存中加载模型，不会自动覆盖原 JSON 文件**。恢复后标记为“未保存”，用户必须手动保存。
- 手动保存成功、正常关闭（保存或明确放弃）、成功新建/切换模型时清理**当前会话**快照；其余会话快照不被自动删除。
- 损坏、超限、格式错误或校验失败的草稿被跳过并保留，不会默默删除；界面状态栏会提示被跳过的数量。
- **恢复文件只保存结构数据**：不包含撤销/重做历史、结果图、计算结果或窗口排列。

### 3.2 更可靠的手动 JSON 保存（新）

`io.save_model_json()` 现在也采用原子替换，降低中断时覆盖并截断原文件的风险。若写入失败，原文件仍应保持旧内容；这不是完全防电源故障文件系统保证，仍建议维护外部备份。

### 3.3 GUI 异常日志与离屏自检（新）

- `gui/startup.py` 将未处理的 Python GUI 异常写入最多 3 份轮转日志；Windows 默认路径：`%LOCALAPPDATA%\MatrixDisplacement\logs\gui_errors.log`。日志包含 Python 堆栈，**不会主动序列化模型内容**，但仍可能含本地路径。
- 增加 `python -m matrix_displacement.gui --self-test`：在装有 PySide6 的环境中创建窗口、求解默认悬臂梁、生成四幅结果图、模拟修改并写入自动恢复快照。此入口旨在验证 Qt + 求解器 + 恢复功能可同时工作。
- `scripts/windows_acceptance.ps1` 加入 V1.1 GUI 专项与端到端离屏自检；`scripts/build_exe_windows.ps1` 在生成 EXE 后强制运行 **打包后 `--self-test`** 并生成 `BUILD_VALIDATION.txt`（如果运行通过）。
- 新增可选 `.github/workflows/windows-smoke.yml`，供**用户将项目根目录作为 GitHub 仓库根目录**并推送后，在 Windows CI 环境尝试构建；**此工作流当前未运行**。

## 4. 安装、使用与测试

### 4.1 Windows 图形界面（需要 Python）

在 ZIP 解压后的**项目根目录**打开 PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
.\.venv\Scripts\python.exe -m matrix_displacement.gui
```

如 `py` 不存在，可使用 `python -m venv .venv`。启动后可通过界面绘制结构、设定荷载与支座、运行教学/快速计算、查看内力图与变形图。

### 4.2 不需要 Qt 的回归测试及恢复演示

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m examples.recovery_workflow_v11
```

恢复演示生成 `artifacts_v11/original_model.json`、`artifacts_v11/recovery/session-....json`、`artifacts_v11/restored_model.json` 及 `recovery_demo.txt`。可以检查原模型不会因为恢复草稿而被覆盖。

当前实际环境结果：**`259 passed, 5 skipped`**。5 个跳过模块为 V0.7、V0.8、V0.9、V1.0 和 V1.1 的 GUI smoke tests，原因是本环境没有 PySide6。对于 Qt 的正确性，这些跳过**不是通过**。

### 4.3 Windows GUI 离屏自检

在已安装 GUI 依赖的 Windows PowerShell 中：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m matrix_displacement.gui --self-test
Remove-Item Env:QT_QPA_PLATFORM
```

亦可运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_acceptance.ps1
```

完成自动测试后，仍必须按 `docs/V1.1_WINDOWS_ACCEPTANCE.md` 执行真实鼠标、不同 DPI、恢复提示、异常与多机器兼容性检查。

### 4.4 在 Windows 尝试生成 `.exe`

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe_windows.ps1
```

若脚本成功，预计文件路径：

`dist\MatrixDisplacement\MatrixDisplacement.exe`

**当前提供的是构建脚本，不是已实际生成并验证的 Windows EXE。** PyInstaller 使用 `--onedir`，分发时需携带**完整目录**。脚本会验证打包后 EXE 的离屏 `--self-test` 退出码并记录 SHA-256，但不代替真实 UI 人工验收。`-SkipTests` 仅跳过源码阶段测试，**不会绕过打包后的 EXE 自检**。

## 5. 数值模型与软件功能

- `Frame2D`：平面刚架单元（节点 `ux,uy,rz`），支持杆端释放；`Truss2D`：二维只承受轴力；`Beam2D`：只用于从左至右的水平梁，节点 `uy,rz`。
- 支持节点荷载、杆件均布/集中/线性荷载；杆件荷载的单元适用性不同，桁架不直接施加杆件分布荷载。
- 使用 `DOFManager` 自动编号、局部/全局刚度转换、整体刚度组装、约束分块求解、反力及杆端力恢复。
- 截面 N/V/M、内部挠曲线和变形图；图形为按杆件采样绘制，不保证采样极值即精确解析极值。
- 教学模式记录单元、坐标变换和整体组装过程；快速模式省略大部分中间记录。
- JSON 模型与 CSV、PNG、Markdown 教学报告。
- GUI 支持节点和杆件绘制、框选、多选、移动、荷载编辑、批量参数更改、撤销重做与截面结果查询。

## 6. 核心目录

```text
matrix_displacement_v11/
├── matrix_displacement/
│   ├── core.py                 # 二维单元、自由度、矩阵组装和静力求解
│   ├── postprocessing.py       # N/V/M 与变形恢复
│   ├── visualization.py        # Matplotlib 绘图
│   ├── editor.py               # 建模和模型修改 API
│   ├── history.py              # 撤销/重做，新增恢复草稿“未保存”基准
│   ├── recovery.py             # V1.1 自动恢复，原子快照和校验
│   ├── io.py                   # JSON 读写，V1.1 原子手动保存
│   ├── selection.py            # 框选和多选算法
│   ├── label_layout.py         # 有限文字标签避让
│   ├── reporting.py            # 教学报告
│   ├── exporting.py            # CSV 导出
│   ├── gui/main.py             # PySide6 UI、恢复菜单/计时器
│   └── gui/startup.py          # V1.1 错误日志与入口
├── examples/recovery_workflow_v11.py
├── tests/test_recovery_v11.py
├── tests/test_gui_startup_v11.py
├── tests/test_gui_smoke_v11.py  # 当前环境缺 Qt 而跳过
├── scripts/build_exe_windows.ps1
├── scripts/windows_acceptance.ps1
├── docs/V1.1_WINDOWS_ACCEPTANCE.md
├── docs/V1.1_QUALITY_REPORT.md
├── .github/workflows/windows-smoke.yml
├── requirements*.txt
├── README.md
└── CHANGELOG.md
```

## 7. 本阶段实际测试证据

| 检查项 | 当前环境情况 |
|---|---|
| 既有 V1.0 243 项回归测试 | 通过 |
| 自动恢复文件的校验、读写、原子中断保护、多会话 | 通过 |
| 模型恢复后仍显示“未保存”的历史基准逻辑 | 通过 |
| 原模型 JSON 原子手动保存、读回一致性 | 通过 |
| 启动异常日志记录（无 Qt） | 通过 |
| 无 Qt 恢复端到端演示 | 通过 |
| V1.1 Qt 实际窗口与恢复弹窗 | **未执行（环境缺 PySide6）** |
| Windows onedir EXE 构建及启动 | **未执行（环境不是 Windows）** |
| GitHub Actions Windows 工作流 | **未执行（需要用户连接/推送仓库）** |

## 8. 自动恢复的安全使用建议

- **自动保存 ≠ 永久备份**。重要结构模型仍应手动保存到用户管理的目录，并定期独立备份。
- 恢复快照可能包含敏感工程数据，默认仅在本机用户目录保存。共享电脑上应注意本地目录权限、磁盘清理和备份策略。
- 恢复草稿文件有 SHA-256 校验，能够识别常见数据损坏，**不能证明文件不曾被有权限的人恶意修改**。
- 恢复操作不会主动覆盖原文件。确认恢复后应“另存为”保留一个独立版本，再决定是否替换原文件。
- 如程序被强制终止而最后一次修改发生在快照写入之前，最后几秒的修改可能未恢复。
- 恢复数据只针对当前线弹性模型 JSON 格式；软件升级后如有格式不兼容，需要另行迁移。

## 9. 无法完成、尚未验证及技术限制（必须保留）

| 项目 | 状态 | 影响 / 后续处理 |
|---|---|---|
| Windows PySide6 真窗口启动与鼠标交互 | **未验证** | 本环境无 PySide6 且非 Windows，需完成 `docs/V1.1_WINDOWS_ACCEPTANCE.md` |
| Qt 离屏 V1.1 自动恢复弹窗/Widget 测试 | **未执行** | 测试代码已编写，本环境跳过；需在安装 PySide6 后执行 |
| Windows PyInstaller EXE 和打包后自检 | **未构建、未执行** | 已准备增强版脚本，必须在 Windows 环境执行、保存日志并修复实际报错 |
| Windows GitHub Actions 工作流 | **未执行** | 用户需创建/推送项目到 GitHub 仓库或自行运行脚本 |
| Windows 高 DPI / 多显示器 / 其他无 Python 电脑 | **未验证** | 必须人工测试，不可凭 Qt 离屏 smoke 代替 |
| 系统断电后保证零数据丢失 | **未实现** | 异步保存有 2.5 秒窗口；原子替换保护已有数据，但不承诺所有文件系统的强一致性 |
| 同一源 JSON 的并发编辑与冲突合并 | **未实现** | 每个会话保留快照，不会合并磁盘上其他会话的改动；需人工检查 |
| 高密度标签全局无重叠布局 | **未实现** | 当前有限贪心布局，复杂模型仍可能遮挡 |
| 更精细的 CAD 对齐、图层及荷载子项框选 | **未实现** | 后续 GUI 路线规划 |
| 空间刚架/桁架、非线性、动力学和规范设计 | **未实现** | 远期独立数值模块；目前仅二维线弹性静力 |
| 全面机构识别、极端病态结构和工程认证 | **未实现** | 数值筛查和基础解析例题不能替代工程核验 |

**工程用途限制：本软件用于结构力学课程学习与数值验证，不能直接视为经过认证的工程安全设计软件。**

## 10. 后续优先级

1. 在 Windows 安装 PySide6，执行 V1.1 Qt 离屏自检与真实交互验收，修复平台兼容性问题。
2. 在 Windows 构建 `onedir` EXE，并用另一台没有 Python 的 Windows 机器验证分发、文件权限与 Qt 平台插件。
3. 完善自动恢复多实例冲突提示、大型模型的绘图性能和标签布局，再考虑 V1.2 GUI 稳定版。
4. 稳定的二维架构通过更多教材算例后，再讨论空间结构扩展。

---

*状态说明：V1.1 是本次完成的源码开发版本，尚不是已通过 Windows 发布验收的可执行软件。未验证事项在以上章节保留，不应因为源代码测试通过就被删除。*

# 矩阵位移法结构分析与可视化教学系统

**版本：V0.7.0（2026-11-06）**  
**定位：** Python 矩阵位移法二维杆系结构力学教学软件，提供教学模式 / 快速计算模式、独立计算内核、可交互桌面建模和计算结果可视化。  
**单位体系：** SI（长度 m、力 N、力矩 N·m、弹性模量 Pa、截面面积 m²、惯性矩 m⁴、转角 rad）。

> **重要说明：** 本项目是线弹性、小变形、静力分析的教学原型，不是工程设计认证软件。所有计算结果和结构稳定性判断均需结合教材解析解或独立软件复核。V0.7 新增的 PySide6 图形界面已完成源代码和测试入口，但当前构建环境缺少 PySide6 且无法联网安装，**尚未在本构建环境实际启动 Qt 窗口**。请在 Windows 安装依赖后运行和验证 GUI。

## 1. 最初的用户需求

1. **结构类型：** 连续梁、平面桁架、平面刚架；软件架构预留扩展空间桁架 / 空间刚架的可能。
2. **编程语言：** Python；以模块化和可复核的矩阵位移法求解器为核心。
3. **开发路线：** 先计算内核、后图形界面；现已从 V0.1 迭代到 V0.7 的首次 GUI 原型。
4. **计算功能：** 单元刚度、整体刚度组装、节点位移、支座反力、杆端力、轴力 / 剪力 / 弯矩图、变形图。
5. **用途：** 结构力学课程学习；保留过程矩阵、教学报告、典型验证算例。
6. **模式选择：** 同时支持教学模式（保存过程矩阵）和快速模式（不记录大量中间矩阵），两者使用**同一数值计算内核**。

## 2. 从 V0.1 到 V0.7 的完成情况

| 版本 | 本轮完成内容 | 当前状态 |
|---|---|---|
| V0.1 | 二维刚架单元刚度、整体矩阵组装、自由度、位移与反力 | 完成 |
| V0.1.1 | 机构/近奇异数值检查、NaN/Inf 输入校验 | 完成基础数值筛查 |
| V0.2 | 均布、杆内集中力、等效节点荷载与杆端力恢复 | 完成 |
| V0.3 | 截面 N/V/M 及内力图、杆件受荷挠曲线与变形图 | 完成 |
| V0.4 | 刚架单元杆端转角释放、独立 `Truss2D`、部分混合模型 | 完成 |
| V0.5 | 连续梁 `Beam2D`、模型 JSON、教学 Markdown 报告 | 完成 |
| V0.6 | 线性变化分布荷载、逐单元组装记录、CSV 导出 | 完成 |
| **V0.7** | **PySide6 鼠标建模 GUI、建模控制层、图形结果标签页与文件菜单** | **代码完成；Qt 窗口待 Windows 实机验证** |

后续将继续迭代；**没有实现**空间结构、材料非线性、几何非线性、动力分析和商业工程软件级别的全面验算。

## 3. Windows 安装与启动（重要）

推荐安装 64 位 Python，并在解压后的 `matrix_displacement_v07` **项目根目录**执行下列命令。

### 3.1 安装图形界面依赖

在 PowerShell 或 Windows Terminal 中：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
```

`requirements-gui.txt` 会安装 NumPy、Matplotlib、pytest 和 **PySide6**；安装时通常需要联网。也可在安装 Python 后双击 `install_gui_windows.bat`（使用 PATH 中的默认 Python）。

### 3.2 运行图形界面

```powershell
.\.venv\Scripts\python.exe -m matrix_displacement.gui
```

或在已安装相关依赖的默认 Python 环境下双击 `run_gui_windows.bat`。

如果只想运行数值内核（不需要 GUI），可以只执行：

```powershell
python -m pip install -r requirements.txt
python -m examples.editor_workflow_v07
```

### 3.3 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Qt 已安装时会额外执行 `tests/test_gui_smoke_v07.py` 中的**窗口创建、求解页签和程序化画布点击**冒烟测试。Windows 手动交互仍建议按照 `docs/V0.7_GUI_TEST_CHECKLIST.md` 检查。

## 4. V0.7 图形界面怎么操作

软件初次启动时加载一个**悬臂梁示例**，可以直接选择教学模式、点击“计算并显示结果”，无需先编写 Python 代码。

### 4.1 新建模型

1. 菜单“文件 → 新建空白模型”打开空白画布。
2. 选“**绘制节点**”工具，在网格上单击即可创建节点；网格默认按 **0.5 m** 吸附。或者使用“精确输入节点坐标”。
3. 在左侧“**新建杆件类型**”选择 `Frame2D`（平面刚架）、`Truss2D`（平面桁架）、`Beam2D`（水平连续梁）。选择“**连接杆件**”，再依次单击两个已有节点。
4. 点击“设置默认 E、A、I”配置**新建杆件**的默认参数，或用选择工具单击已有杆件，再双击/点击“编辑选中的节点/杆件”修改该杆件的 E/A/I。编辑已有杆件采用独立材料与截面的 **copy-on-write** 策略，不会同步修改其他杆件。
5. 选择“**设置支座 / 给定位移**”，点击节点，在弹窗中勾选 `ux` / `uy` / `rz` 约束。约束值为 0 表示普通支座；非零可输入给定位移 / 转角。可用自由度随单元类型自动限制。
6. 选择“**设置节点荷载**”，点击节点，输入 `Fx`、`Fy`、`Mz`。再次设置会**替换**该节点原有同类荷载值而不是累加。
7. 选择“**添加杆件荷载**”，点击梁 / 刚架杆件，可选均布荷载、杆内集中力、线性变化分布荷载；支持局部 / 整体坐标系。向下的 `Fy/qy` 用负值。桁架仅支持节点荷载。
8. 点击“计算并显示结果”，查看“**数值结果、轴力 N、剪力 V、弯矩 M、变形图**”页签。

**模型修改会清除旧计算结果**，避免将过时的位移或内力图误当成当前模型答案。可通过菜单载入三个典型算例：悬臂梁、两跨连续梁、三角形桁架。

### 4.2 删除、坐标和选中状态

- 鼠标滚轮缩放，点击“适应窗口”重新定位模型。
- “选择”工具下单击节点 / 杆件，左侧显示对象属性和当前荷载摘要；双击可以编辑节点坐标或杆件截面 / 释放条件。
- 点击“删除节点或杆件”，删除节点时会同时删除连接的杆件及其杆件荷载；此操作会弹出确认提示。
- 点击“清空选中杆件的所有荷载”可移除指定杆件的荷载，之后可以重新添加。
- 目前**没有**鼠标拖拽移动节点、逐项编辑已有杆件荷载、撤销/重做、多选、独立 exe 安装包等功能。

### 4.3 教学模式 / 快速模式

| 选项 | 计算 | 教学记录 | CSV / PNG |
|---|---|---|---|
| 教学模式 | ✅ | ✅ 单元刚度、组装过程、约束/求解方程 | ✅ |
| 快速模式 | ✅ | ❌ 不保存逐步组装矩阵 | ✅ |

两个模式调用相同的线性静力求解器。快速模式主要是**节省教学 trace 的内存**，目前没有使用专用稀疏求解器或特殊快速算法。要导出教学报告，必须选择教学模式并重新计算。

### 4.4 文件与导出

- **保存/打开 JSON：** 结构节点、材料、截面、杆件、支座和荷载。结果需重新计算。沿用 V0.6 的 `schema_version=2`，支持读取旧 schema 1。
- **导出教学报告 `.md`：** 包含自由度编号、局部/整体单元刚度、逐单元组装矩阵、最终位移/反力/杆端力。
- **导出 CSV：** `nodal_results.csv`、`element_end_forces.csv`、`section_forces.csv`、`deformations.csv`。
- **保存当前 PNG：** 先切换到结果页中的 N/V/M/变形图，再点保存当前图形。

## 5. 文件结构

```text
matrix_displacement_v07/
├── matrix_displacement/
│   ├── core.py                # V0.6 数值计算内核（不改算法）
│   ├── editor.py              # V0.7 新增：纯 Python 模型操作控制层
│   ├── gui/
│   │   ├── __main__.py        # python -m matrix_displacement.gui
│   │   └── main.py            # PySide6 Qt Widgets / QGraphicsView
│   ├── io.py                  # JSON 模型
│   ├── reporting.py           # 教学报告
│   ├── exporting.py           # CSV
│   ├── postprocessing.py      # 截面内力、杆件变形
│   └── visualization.py       # Matplotlib
├── examples/
│   └── editor_workflow_v07.py # 无 Qt 的完整建模→求解→成果导出示例
├── outputs/examples/artifacts_v07/            # 已生成的示例 JSON、报告、CSV、5 张 PNG
├── tests/                    # 数值测试 + 编辑器测试 + 可选 GUI 冒烟测试
├── docs/
│   ├── README_V0.6.md         # 上一版详细数学与 API 说明
│   └── V0.7_GUI_TEST_CHECKLIST.md
├── requirements.txt          # 仅数值内核
├── requirements-gui.txt      # 数值内核 + PySide6
├── install_gui_windows.bat
├── run_gui_windows.bat
└── CHANGELOG.md
```

之前 V0.6 的计算公式、单元符号约定、CSV 格式和结果说明，见 [`docs/README_V0.6.md`](docs/README_V0.6.md)。本版本不重写 V0.6 数学内核。

## 6. V0.7 自动验证与重要限制

**本次构建环境执行：**

```text
171 passed, 1 skipped
```

- **已验证：** 继承 V0.6 的 146 项测试；新增 25 项 `ModelEditor` 计算/编辑/JSON/荷载/约束测试；`python -m compileall` 语法检查；`examples.editor_workflow_v07` 生成模型、计算结果、教学报告、CSV 和 PNG；教学/快速模式计算结果一致；最终 ZIP 需再次解压回归验证。
- **未验证：** 本构建环境未安装 PySide6，Qt GUI 模块的离屏测试 **被跳过**，实际窗口启动、鼠标事件、系统对话框、图形尺寸与 Windows 高 DPI 表现需要在 Windows 上验证。QT 模块中提供两项可选离屏冒烟测试，但它们不是完整的交互质量保证。
- **数值限制：** 二维线弹性小变形静力分析；桁架不接受杆件分布荷载；`Beam2D` 仅水平、i→j 向右，单元仅弯曲自由度；`Frame2D` 可用于斜梁 / 轴向变形并支持端部转角释放；机构检测属于数值筛查而非严格稳定性证明。
- **GUI 限制：** 首版只覆盖必要的鼠标建模、编辑、约束、荷载、运行和结果输出，不包含 3D、拖动编辑、撤销、打印排版、多荷载工况组合、半刚性连接、荷载逐项修改和 exe 安装包。

## 7. V0.8 建议开发内容

优先在 Windows 上完成 V0.7 的界面冒烟和手工验证，并解决实际显示 / 交互问题；然后增加：

1. 鼠标拖拽节点、网格吸附开关、标尺和荷载数值标注。
2. 模型/荷载属性表，支持**逐项**编辑与删除、撤销/重做。
3. 各杆件最大/最小内力数值提示，图形缩放与单独杆件查询。
4. 项目测试通过后，考虑 Windows 独立可执行文件的打包与安装。

---

## 8. 不依赖 GUI 的 V0.7 示例

使用 `ModelEditor` 能以与 GUI 相同的接口创建结构、求解并保存：

```python
from matrix_displacement.editor import ModelEditor
from matrix_displacement import Mode

editor = ModelEditor()
editor.load_example('continuous_beam')
editor.save('beam.json')
result = editor.solve(Mode.TEACHING)
print('中间支座反力 (N):', result.reaction(2, 'uy'))  # 5000
```

运行 `python -m examples.editor_workflow_v07` 将生成 `outputs/examples/artifacts_v07`：结构 JSON、教学报告、四个 CSV 文件和五张 PNG。这个例子**无需 PySide6**，适合确认数值求解内核和文件导出正常。

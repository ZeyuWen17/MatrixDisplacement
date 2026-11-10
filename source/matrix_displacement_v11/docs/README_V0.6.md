# 矩阵位移法结构分析与可视化教学系统

**当前版本：V0.6.0（2026-11-06）**  
**项目定位：** Python 矩阵位移法二维杆系结构计算内核，主要服务结构力学课程学习，未来拓展空间结构及桌面图形界面。

> 注意：当前是**线弹性、小变形、静力分析教学原型**，不是经过全面工程验证的软件。请使用 SI 单位（m、N、Pa、m²、m⁴、rad），对工程用途的计算结果进行独立复核。

## 1. 原始需求与开发原则

用户希望支持：**连续梁、平面桁架、平面刚架**，以后扩展空间结构；采用 **Python**；先完善**计算内核**，再开发**图形界面**；可求单元刚度、整体刚度、节点位移、支座反力、杆端内力，能绘制轴力/剪力/弯矩/变形图。最初主要用于结构力学课程学习。

用户确定采用两种模式：

- **教学模式** `Mode.TEACHING`：保留自由度映射、单元刚度、变换矩阵、整体刚度逐单元组装过程、荷载和约束处理，可以生成 Markdown 计算报告。
- **快速模式** `Mode.FAST`：只保留求解所需数据，不额外保存教学中间过程。两种模式共享同一数值求解内核；目前**尚未使用稀疏矩阵或专门加速算法**。

工程架构将模型数据、单元力学、求解器、后处理、绘图与数据导出分开；未来图形界面只调用这些模块，不重写计算公式。

## 2. 需求完成状态

| 功能需求 | V0.6 进度 | 适用范围 |
|---|---|---|
| 平面刚架 | ✅ | `Frame2D`：6 自由度，任意平面方向，杆端释放 |
| 平面桁架 | ✅ | `Truss2D`：4 自由度，轴向拉压，只支持节点荷载 |
| 连续梁 | ✅ | `Beam2D`：水平且 i→j 向右；4 自由度，不含轴向变形 |
| 部分梁-桁架-刚架混合模型 | ✅ | 自动合并节点实际用到的自由度；应满足真实连接假设 |
| 单元刚度、整体刚度、边界处理 | ✅ | 自动组装、零/非零位移约束、反力恢复 |
| 杆件均布荷载、杆内集中力 | ✅ | V0.2 起，桁架单元例外 |
| **杆件线性变化分布荷载** | ✅ **V0.6 新增** | 三角形/梯形、轴向/横向分量；Beam2D 仅横向 |
| 截面轴力/剪力/弯矩计算和绘图 | ✅ | 按局部坐标；考虑集中力跳跃和内力极值 |
| 弹性变形曲线 | ✅ | 考虑杆件荷载；释放端实际转角恢复 |
| JSON 保存与读取 | ✅ | V0.6 写 schema 2，同时读取 schema 1 |
| **逐单元刚度组装教学报告** | ✅ **V0.6 增强** | 教学模式生成 Markdown，记录每步组装矩阵 |
| **结果 CSV 导出** | ✅ **V0.6 新增** | 位移、反力、杆端力、截面内力、变形数据 |
| 桌面图形交互界面 | ⬜ | 计划 V0.7 使用 PySide6 |
| 空间桁架与空间刚架 | ⬜ | 未来版本 |

## 3. V0.6 新增：线性变化分布荷载

### 3.1 荷载输入

`LinearLoad2D` 规定沿杆件局部 x 方向从 i 端到 j 端的全长度线性变化力：

\[
q_x(x)=q_{xi}+\frac{q_{xj}-q_{xi}}{L}x,\qquad
q_y(x)=q_{yi}+\frac{q_{yj}-q_{yi}}{L}x
\]

例如水平梁上，向下的三角形荷载从 `0` 增至 `1.5 kN/m`：

```python
model.add_linear_load(element_id=1, qy_i=0, qy_j=-1500)
```

梯形荷载从向下的 `0.5 kN/m` 增至 `1.5 kN/m`：

```python
model.add_linear_load(element_id=1, qy_i=-500, qy_j=-1500)
```

通过 `system='local'` 或 `system='global'` 指定分量坐标系；`Frame2D` 同时支持 `qx_i/qx_j` 与 `qy_i/qy_j`；`Beam2D` 只支持横向分量（`qx_i=qx_j=0`）；`Truss2D` 仍不接受直接杆件荷载。

同一杆件可以叠加多个 `UniformLoad2D`、`LinearLoad2D` 和 `PointLoad2D`。可以直接构造 `LinearLoad2D` 再调用 `add_member_load()`，也可以调用上述便捷方法。

### 3.2 一致等效节点荷载

对水平梁单元，自由度顺序为 `[v_i, θ_i, v_j, θ_j]`。**按实际分布荷载本身的代数符号**，横向等效节点力为：

\[
\mathbf f_{eq,y}=\begin{bmatrix}
\frac{L}{20}(7q_{yi}+3q_{yj})\\
\frac{L^2}{60}(3q_{yi}+2q_{yj})\\
\frac{L}{20}(3q_{yi}+7q_{yj})\\
-\frac{L^2}{60}(2q_{yi}+3q_{yj})
\end{bmatrix}
\]

`Frame2D` 另有对应轴向分量：

\[
F_{xi}=\frac{L}{6}(2q_{xi}+q_{xj}),\quad
F_{xj}=\frac{L}{6}(q_{xi}+2q_{xj})
\]

固端**抗力**为 `-f_eq`。若杆端弯矩释放，程序先构造完整一致荷载，然后进行与刚度一致的静力凝聚。

### 3.3 截面内力与变形

在没有杆内集中力的位置，采用以下关系：

\[
V(x)=F_{yi}+q_{yi}x+\frac{q_{yj}-q_{yi}}{2L}x^2
\]
\[
M(x)=-M_i+F_{yi}x+\frac{q_{yi}x^2}{2}+\frac{(q_{yj}-q_{yi})x^3}{6L}
\]

杆内集中力的影响另外叠加，轴力也按局部平衡恢复。轴向变形由 `EA u'(x)=N(x)`、弯曲变形由 `EI v''(x)=M(x)` 积分计算；弯矩极值搜索支持求解二次剪力函数的零点。

**符号约定：** 全局 X 右、Y 上；局部 x 从 i 指向 j，局部 y 为 x 的逆时针法线；`+rz` 为逆时针；截面轴力受拉为正。`section(x,side='left'/'right')` 可得到杆内集中力两侧剪力或轴力。

### 3.4 解析算例

一根长 **6 m** 的水平简支梁，承受向下的三角形荷载，从 i 端的 0 增大到 j 端的 **1.5 kN/m**，程序得到：

| 物理量 | 解析解 | 实测计算 |
|---|---|---|
| i 端支座反力 | `q_j L/6`（取荷载绝对值） | `1.500000 kN` |
| j 端支座反力 | `q_j L/3`（取荷载绝对值） | `3.000000 kN` |
| 最大弯矩位置 | `L/√3` | `3.46410 m` |
| 最大弯矩 | `q_j L²/(9√3)`（取荷载绝对值） | `3.464102 kN·m` |

运行示例会生成结构与箭头示意、剪力图、弯矩图、变形图等成果。

## 4. V0.6 新增：逐单元整体刚度组装

教学模式下，每个单元的教学记录包含：

- 局部刚度 `k_local`、坐标转换矩阵 `T`、整体坐标单元刚度 `k_global = T.T @ k_local @ T`。
- 单元局部自由度对应的**全局自由度索引**，并说明每个 `K[I_a,I_b] += k_global[a,b]` 的叠加原则。
- 当前单元的矩阵贡献、**本次叠加后的整体刚度矩阵 `K`**、对应的等效节点荷载。
- 最终 `K`、总外荷载、自由/约束自由度划分、缩减方程 `K_ff d_f = F_f - K_fc d_c` 以及位移和反力。

```python
from matrix_displacement import LinearStaticSolver, Mode, save_teaching_report
result = LinearStaticSolver(Mode.TEACHING).solve(model)
save_teaching_report(model, result, 'teaching_report.md')
```

由于中间每一步都保存一份整体矩阵，教学模式会比快速模式占用更多内存。报告默认限制 `max_dofs=80`，建议用于课程规模算例。快速模式不保存教学 `trace`，不能生成教学报告。

## 5. V0.6 新增：CSV 结果导出

```python
from matrix_displacement import export_results_csv
# 教学模式或快速模式的 result 都可以导出 CSV
paths = export_results_csv(model, result, 'csv_output', points=101)
```

输出四个 UTF-8 BOM 编码文件（Windows Excel 可直接打开）：

| 文件名 | 内容 | 主要列 |
|---|---|---|
| `nodal_results.csv` | 节点自由度、位移、反力和约束状态 | node_id, dof, displacement, reaction |
| `element_end_forces.csv` | 每个杆件的局部杆端抗力 | element_id, component, unit, value |
| `section_forces.csv` | 各杆件截面轴力、剪力、弯矩 | x_m, side, N_N, V_N, M_Nm |
| `deformations.csv` | 轴向/横向位移、截面转角 | ux_local_m, uy_local_m, rz_rad, ux_global_m, uy_global_m |

集中力作用位置的截面内力会记录左右两个极限值；带有 `side` 列以区分。内部弯矩极值的准确位置也加入采样数据。使用 `include_sections=False` 可仅导出前两个文件，适合小型结果表格。

## 6. JSON 模型版本

- **V0.6 写入 `schema_version=2`**，支持 `LinearLoad2D` 的 `qx_i/qy_i/qx_j/qy_j` 等属性。
- **V0.6 可读取 V0.5 的 `schema_version=1` 文件**（其中只有 `UniformLoad2D` / `PointLoad2D`）。
- V0.5 旧版软件不能保证读取包含新荷载类型的 V0.6 模型；需要使用 V0.6 的读取器。
- JSON 仅存储结构输入，不保存数值求解结果。读取时执行字段白名单、材料/单元/荷载及有限数值校验，不会执行外部 Python 代码。

```python
from matrix_displacement import save_model_json, load_model_json
save_model_json(model, 'structure.json')
restored_model = load_model_json('structure.json')
```

## 7. 工程目录

```text
matrix_displacement_v06/
├── matrix_displacement/
│   ├── __init__.py
│   ├── core.py                  # 模型、荷载、单元、自由度编号、组装、求解
│   ├── postprocessing.py        # 截面 N/V/M 和实际挠曲线
│   ├── visualization.py         # 结构示意、加载箭头、内力图、变形图
│   ├── io.py                    # JSON 模型版本与校验
│   ├── reporting.py             # 教学计算 Markdown 报告
│   └── exporting.py             # CSV 结果导出（V0.6）
├── examples/
│   ├── cantilever.py
│   ├── member_loads.py
│   ├── diagrams.py
│   ├── release_and_truss.py
│   ├── continuous_beam.py
│   └── linear_load_v06.py      # V0.6 三角形荷载/JSON/CSV/教学报告
├── tests/
│   ├── test_core.py
│   ├── test_validation.py
│   ├── test_member_loads.py
│   ├── test_postprocessing.py
│   ├── test_release_and_truss.py
│   ├── test_beam2d_v05.py
│   ├── test_io_reports_v05.py
│   └── test_v06.py
├── outputs/examples/artifacts_v06/               # 三角形荷载完整演示成果
├── requirements.txt
├── README.md
└── CHANGELOG.md
```

## 8. Windows 安装与运行

要求 Python **3.10+**。解压项目，在包含 `requirements.txt` 的目录打开 PowerShell：

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m examples.linear_load_v06
```

如果 `python` 命令不可用，可尝试 Windows Python Launcher：`py -m pip ...`。运行第三条命令会生成 `outputs/examples/artifacts_v06/`：

```text
triangular_beam.json   # 可再次加载的模型
teaching_report.md     # 带逐单元组装的完整教学报告
structure.png          # 三角形荷载箭头示意
shear.png              # 剪力图
moment.png             # 弯矩图
deformation.png        # 挠曲变形图
csv/
  nodal_results.csv
  element_end_forces.csv
  section_forces.csv
  deformations.csv
```

可以指定输出文件夹：

```powershell
python -m examples.linear_load_v06 --output my_results
```

旧版示例继续可运行：

```powershell
python -m examples.cantilever
python -m examples.member_loads
python -m examples.diagrams
python -m examples.release_and_truss
python -m examples.continuous_beam
```

## 9. 测试记录与已知限制

**V0.6：146 项测试全部通过（V0.5 的 127 项 + V0.6 新增 19 项）。**

新增测试覆盖：三角形等效荷载、均布荷载退化关系、简支梁解析反力及弯矩极值、精确挠曲、倾斜刚架坐标转换、轴向梯形荷载、刚架端释放后弯矩零值、不同荷载叠加、非法荷载拒绝、旧 JSON 向后兼容、逐单元矩阵累加、CSV 数据表与集中力跳跃、加载箭头图像生成。

**限制和风险：**

1. 仅二维杆系的线性静力分析；无空间结构、剪切变形、材料/几何非线性、温度、动力、屈曲和二阶效应。
2. `Beam2D` 限于**水平、从左到右、只有横向弯曲自由度**；倾斜杆件和轴向变形用 `Frame2D`。
3. `Truss2D` 只接受节点荷载，不支持杆内分布力或杆内集中力；需细分杆件后施加节点荷载。
4. 机构及近奇异判断是基于矩阵数值诊断，极端刚度比、单位不一致及高度病态结构需要独立复核。
5. 内力图是按局部正负号绘制的比例图，放大/缩小仅为展示；**不代表真实结构变形或内力值的绝对比例**。查询精确数据应使用 `section()` 或 CSV。
6. 图形建模、模型交互编辑与三维可视化尚未开发。`plot_structure(show_loads=True)` 中荷载箭头长度按各荷载归一化，并非公共绝对力标尺。
7. 教学模式保存每步完整整体刚度矩阵，适合教学小模型，不适用于大规模结构高效求解。

## 10. 下一阶段计划

- **V0.7：图形界面基础版。** 使用 PySide6 实现二维画布、节点/杆件绘制、支座和荷载参数编辑、调用现有求解器并查看内力/变形图。
- 以后：进一步实现材料和截面属性面板、模型文件管理、计算过程交互展示、单元荷载更多形式，以及空间桁架和空间刚架。

本 README 既是项目需求基线，也是已完成任务的版本记录，新增功能应继续遵守 **数学公式 → 编程实现 → 解析例题 → 自动测试 → README 更新 → 完整源码打包** 的开发流程。

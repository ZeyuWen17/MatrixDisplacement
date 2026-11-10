# 更新记录（CHANGELOG）

## V1.1.1 — 2026-11-06 — Windows 兼容修复与实际验收

- 修复 Windows PowerShell 5.1 中文脚本编码与 Python 导入命令引号错误。
- 包版本、GUI 标题及版本回归测试共用版本来源，修复遗留 V1.0 断言。
- 自动测试隔离恢复草稿目录，避免接触用户草稿。
- 构建按需收集 Qt 模块，支持跳过依赖安装；打包自检增加隐藏启动和 120 秒超时。
- 本机 Windows 测试 270 passed、1 skipped（仅非 Windows XDG 测试）；源码验收脚本通过。
- 本次完整证据及剩余验收范围见 docs/V1.1.1_WINDOWS_VALIDATION.md。


## V1.1.0 — 2026-11-06 — 自动保存、崩溃恢复与 Windows 发布自检准备

- 新增独立 `recovery.py`：每个 GUI 会话单独快照，2.5 秒编辑防抖 + 60 秒周期保底；原子写入、UTC 时间、SHA-256 数据校验、无可执行反序列化。
- GUI 新增“恢复自动保存草稿...”菜单与启动提示；由用户选择恢复/删除/暂不处理，恢复模型仍标记未保存，且不自动覆盖原模型 JSON。
- `io.save_model_json` 改为同目录临时写入、fsync 和 os.replace，降低保存中断导致原模型截断的风险。
- 新增 `gui/startup.py` 轮转错误日志、`--self-test` 源码/打包通用 Qt 求解绘图和自动保存离屏自检。
- 更新 Windows `build_exe_windows.ps1`：PyInstaller onedir 构建后强制运行打包 EXE 自检并写出 SHA256 和 `BUILD_VALIDATION.txt`；新增 Windows CI 工作流模板（未运行）。
- 新增无 Qt `examples.recovery_workflow_v11`、恢复故障注入测试、可选 Qt GUI smoke 和 V1.1 Windows 验收清单。
- **当前环境测试为 259 passed, 5 skipped**。五个 Qt 模块因缺少 PySide6 被跳过；**未生成/运行 Windows EXE，Qt 窗口和 CI 仍需实际验收**。

---


## V1.0.0 — 2026-11-06 — 多选与批量模型编辑（源码功能版）

- `selection.py`：独立于 Qt 的左到右窗口选择、右到左交叉选择以及 Ctrl/Shift 多选集合操作。
- PySide6 画布添加 QRubberBand 选框、全选与清除选择、组选中高亮、单击恢复单选与整组节点拖动。
- `ModelEditor`：多节点同步移动/平移、多杆件共同 E/A/I、批量删除和关联数据清理，复用 `EditHistory` 单次事务和回滚。
- `label_layout.py`：标签在有限候选位置内减少遮挡，覆盖节点、尺寸、杆件荷载与节点荷载说明；密集模型仍可能重叠。
- 新增不依赖 Qt 的 `examples.batch_workflow_v10`，测试批量编辑、撤销重做、JSON 往返及教学/快速结果一致性。
- 新增 V1.0 专项自动化测试。**实际环境结果：243 passed, 4 skipped**；4 个跳过模块均依赖 PySide6，Windows GUI 和 EXE 均未通过实机验证。
- Windows 构建和验收脚本增加 Qt import、GUI smoke 专项检查；新增 `docs/V1.0_WINDOWS_ACCEPTANCE.md`，全部 Windows 实机项为待验证。
- **交付边界：** Windows `.exe` 尚未生成或认证，V1.0 为源码功能版，不是最终经 Windows 验收的桌面程序。

---

## V0.9.0 — 2026-11-06

- 在 V0.8 的 Qt 画布基础上增加鼠标中键平移、独立平移工具、菜单缩放与 `Ctrl+0` 适应窗口。
- 新增杆件长度/角度尺寸标注及视图开关，支持水平、竖直与斜杆。
- Matplotlib N/V/M 曲线可选交互模式，图形点选映射到真实杆件位置和截面查询；正确区分集中力位置左右极限。
- `interaction.py` 提供不依赖 Qt 的几何标注、杆内投影、图形采样位置恢复；`diagnostics.py` 为常见异常提供用户可执行的排查建议。
- 新增 Windows 构建 PowerShell/BAT、PyInstaller 依赖声明、Windows 验收脚本和清单。**脚本已生成，不代表 Windows EXE 已构建或通过实际运行验证**。
- 数值/非 Qt 测试：`212 passed, 3 skipped`；3 个跳过模块均需要 PySide6，当前 Linux 环境不具备 Qt。
- 当前版本保留全部已有功能，README 列明 Windows GUI、EXE、多选、文字避让与空间结构等未完成/待验证任务。

---

## V0.8.0 — 2026-11-06

- 新增 `EditHistory` 模型快照事务、失败回滚、撤销与重做（100 条上限）。
- 选择工具下拖拽节点，几何校验与单步撤销；网格吸附复选框。
- 新增 `ModelEditor.replace_member_load/delete_member_load`，支持单项杆件荷载修改与删除。
- 画布荷载标注含实际输入数值；侧栏增加杆件属性表和杆件荷载表。
- 新增 `inspection.py`，查询节点位移、反力、任意位置杆件 N/V/M、变形、采样范围。
- 结果页面增加“杆件截面查询”，可选集中力位置的左 / 右极限。
- 新增 V0.8 自动测试与可选 Qt 离屏冒烟测试；旧测试保留。
- 已验证数值与非 Qt 逻辑；构建环境缺 PySide6，Windows GUI 仍待实测。

---

## V0.7.0 — 2026-11-06 — 首版桌面图形建模界面

- 新增 **PySide6 + QGraphicsView** 图形界面（`python -m matrix_displacement.gui`），提供网格点击建节点、两节点连杆、三类单元类型选择、支座/给定位移、节点荷载、均布/集中/线性分布杆件荷载设置、节点/杆件属性编辑和删除。
- 新增独立于 Qt 的 **`ModelEditor`** 控制层；复用 V0.6 原有 `StructuralModel`、`LinearStaticSolver`、JSON 和绘图算法，避免界面重复实现数学运算。
- 界面可切换教学/快速模式，显示各节点位移、反力和杆端抗力，并嵌入轴力/剪力/弯矩/变形 Matplotlib 图；支持导出 Markdown 教学报告、CSV 与 PNG。
- 新增 Windows 启动/安装脚本、三组可加载教学算例、`examples.editor_workflow_v07` 无 GUI 端到端示例和可选的 Qt offscreen 冒烟测试。
- 增加节点位置和杆件荷载合法性检查、支座/节点荷载的原子替换行为、原始单元属性的 copy-on-write 修改及模型版本 JSON 往返测试。
- **本环境验证：171 passed, 1 skipped**（跳过的是未安装 PySide6 的 Qt 冒烟测试模块）；核心数值、静态语法和 JSON/报告/CSV/PNG 流程已验证。由于本环境无法安装 PySide6，尚未完成 Qt 桌面窗口的实际启动和交互验证，Windows 需补跑 `python -m pytest -q` 并手动检查界面。
- 仍属于二维线弹性静力教学原型；本阶段未提供三维结构、节点鼠标拖拽、撤销/重做、荷载逐项编辑或打包为独立 exe。

---

# 更新日志

## V0.6.0 — 2026-11-06

- 增加 `LinearLoad2D(qx_i,qy_i,qx_j,qy_j)` 与 `StructuralModel.add_linear_load()`，实现三角形/梯形全杆长度荷载（局部或整体坐标）。
- 为 `Frame2D` 和 `Beam2D` 增加一致等效节点荷载；释放端仍按一致静力凝聚处理；桁架直接杆内荷载仍拒绝。
- 增加线性变化荷载下精确截面 `N(x)/V(x)/M(x)` 和积分变形恢复；弯矩极值位置可由二次剪力方程求得。
- 教学模式新增逐单元组装后的整体刚度矩阵记录，Markdown 报告列出每一步自由度映射与矩阵叠加。
- 新增 `export_results_csv()`，以 UTF-8 BOM 输出节点、杆端、截面和变形四份 CSV 表；支持教学/快速两模式。
- JSON 写入 schema_version=2，支持读取 V0.5 旧 schema_version=1 文件；新增 V0.6 荷载类型支持。
- `plot_structure(show_loads=True)` 绘制杆件均布/线性/点力的归一化箭头。
- 新增三角形荷载示例 `examples.linear_load_v06`，自动输出 JSON、Markdown 报告、CSV 与 PNG。
- 保留全部 V0.5 旧测试 127 项，V0.6 新增 19 项测试，共 146 项通过。

# 更新日志（Changelog）

## V0.5.0 — 连续梁专用单元、JSON 模型与教学报告

- 新增水平左到右的 `Beam2D` 四自由度 Euler–Bernoulli 单元（每节点 `uy`、`rz`），支持横向均布载荷和任意位置横向集中力、支座沉降、后处理和绘图。
- `DOFManager` 改为自动按不同单元类型取节点自由度并集，保持 V0.4 刚架 / 桁架及端部释放行为兼容。
- 新增 `BeamResponse2D`，复用内力、弹性挠曲线积分与绘图能力。
- 新增 `io.py`：显式 `schema_version=1` 的 JSON 存取、类型与字段白名单、加载校验，无可执行反序列化。
- 新增 `reporting.py`：教学模式结果导出 Markdown，包含输入、自由度、局部/整体矩阵、荷载、求解及结果。
- 新增 `examples/continuous_beam.py`：两跨梁解析验证、读写 JSON、生成教学报告和 PNG 图。
- 新增 `test_beam2d_v05.py`、`test_io_reports_v05.py`：32 项；旧 95 项回归通过，**总计 127 项测试通过**。
- 使用边界：`Beam2D` 不支持轴向力、斜杆或端部释放；这些情况仍使用 `Frame2D`。

## V0.4.0 — 二维桁架与刚架端部转动释放

- `Frame2D` 新增 `release_i` / `release_j`：通过静力凝聚同时修正单元刚度矩阵和一致等效节点荷载，释放端弯矩保持零。
- `Frame2D.physical_local_displacements()` 重建释放端真实转角，保证跨内变形曲线与受荷释放条件相符。
- 新增 `Truss2D` 4 自由度二维桁架单元与 `TrussResponse2D` 拉/压轴力及变形接口。
- 自由度管理支持桁架-only 节点两平动自由度、刚架节点三自由度、无刚度的旋转自由度自动不参与静力求解；兼容刚架—桁架组合结构。
- 可视化兼容混合结构的 N/V/M 与变形图；新增 `examples/release_and_truss.py` 与图形样例。
- 新增 `tests/test_release_and_truss.py` 23 项，原 72 项全部保留，**共 95 项测试通过**。
- README 记录功能约束、数学推导、使用示例与后续开发计划。

## V0.3.0 — 截面内力与可视化

- 新增 `matrix_displacement/postprocessing.py`：单元任意截面的 `N(x)、V(x)、M(x)` 与 `u(x)、v(x)、rz(x)`。
- 新增 `MemberResponse2D`、`SectionForces2D`、`Deformation2D`、采样数据对象。
- 内力计算根据杆端抗力、均布线荷载、杆内点荷载及平衡关系进行；点力截面支持左右极限。
- 变形恢复以 `EA*u'=N`、`EI*v''=M` 积分，能重现固定端荷载作用的杆内挠曲。
- 添加 Matplotlib 的轴力、剪力、弯矩图、整体变形图与原始数值曲线绘制。
- 新增 `examples/diagrams.py`，生成 5 张 PNG；提供生成后的 `figures/` 示例。
- 新增 `tests/test_postprocessing.py`；原有 43 项测试保留，总计 72 项通过。
- README 补充原始需求、已实现状态、公式、计算约定、运行示例与后续开发路线。

## V0.2.0 — 杆件荷载

- 常值分布力、杆内点力、局部/整体坐标输入、等效节点荷载与固端抗力。
- 计算求解器支持节点荷载与杆件荷载叠加，恢复杆端内力。
- 共 43 项测试通过。

## V0.1.1 — 数值验证与输入检查

- 对 NaN/Inf 输入进行有限性验证；对机构和近奇异刚度矩阵加强筛查。
- 共 20 项测试通过。

## V0.1.0 — 二维刚架基本求解内核

- 完成节点/材料/截面、二维刚架刚度矩阵、自由度映射、刚度组装与边界求解。
- 提供教学模式和快速模式。

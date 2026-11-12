# MatrixDisplacement · 矩阵位移法教学系统

用于结构力学课程学习的二维结构建模与线弹性静力分析程序。基于 Python、NumPy、Matplotlib 和 PySide6，支持连续梁、平面桁架、平面刚架及刚架—桁架混合模型。

当前源码版本：**V1.2.0**。提供图形建模、矩阵组装过程、内力与变形结果，方便将教材计算步骤与数值结果对照。

V1.1.9 完成大模型分阶段绘图与导出、自动精简标注、可排序复制的结果表格、带单位输入、荷载工况与组合，并包含模型检查和支座预设。[验收记录](source/matrix_displacement_v11/docs/V1.1.9_VALIDATION.md)。

V1.2.0 阶段性成果新增：建模画布增加杆件集中力作用点箭头、均布/线性分布荷载箭头与轮廓，标注杆件编号、荷载序号、坐标系及数值。集中荷载采用红色粗长单箭头，均布荷载采用青绿色等长细箭头及直线，线性荷载采用紫色渐变箭头及斜线；画布底部提供图例。箭头长度为示意，各组荷载单独归一化，不表示跨荷载数值比例。

## 主要功能

- **交互建模**：节点与杆件编辑、支座与给定位移、材料及截面属性、杆端转角释放、多选与批量修改、撤销与重做。
- **工况与组合**：保存多组荷载，按自定系数组合并重新求解；共享结构和支座，JSON 保存工况库，支持撤销。
- **荷载输入**：节点力与力矩、杆件均布荷载、集中荷载和线性分布荷载，支持局部与整体坐标系。
- **分析与教学**：教学模式保留组装矩阵，快速模式减少中间记录；输出节点位移、支座反力及杆端力。
- **响应与诊断**：后台求解提供忙碌提示和取消结果入口；结果图按需生成并缓存；不稳定结构显示相关自由度，并选中对应节点便于排查。
- **结果表格**：位移/反力及杆端力表按数值排序，`Ctrl+A` 全选、`Ctrl+C` 带表头复制至 Excel。
- **结果查看**：轴力、剪力、弯矩、变形图和杆件截面查询；超过 100 根杆件自动隐藏密集标注；可手动选择隐藏、采样极值或完整标注，点击曲线查看杆件详情。
- **保存与导出**：JSON 模型、自动恢复草稿、保存冲突提示、Markdown 教学报告、CSV 数据和 PNG 图片；支持一次导出全部四张结果图。

![两跨两层刚架弯矩图](source/matrix_displacement_v11/docs/assets/acceptance-2026-11-09/dense_frame_labels.png)

## 安装与启动

### Windows 免安装包（推荐）

**[下载 V1.2.0 Windows x64 免安装版](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.2.0/MatrixDisplacement_V1.2.0_Windows.zip)** · [发布说明与校验文件](https://github.com/ZeyuWen17/MatrixDisplacement/releases/tag/v1.2.0)

无需单独安装 Python。下载后**解压整个 ZIP**，打开 `MatrixDisplacement` 文件夹，双击 `MatrixDisplacement.exe`。必须保留 `_internal` 文件夹，不能只复制 EXE，也不要直接从压缩包预览窗口运行。

| 版本 | Windows 免安装包 | 说明 |
| --- | --- | --- |
| **V1.2.0（推荐）** | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.2.0/MatrixDisplacement_V1.2.0_Windows.zip) | 阶段性成果：完整功能回归、荷载标注与图例 |
| V1.1.9 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.9/MatrixDisplacement_V1.1.9_Windows.zip) | 大模型体验、结果表格、单位输入、工况组合 |
| V1.1.8 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.8/MatrixDisplacement_V1.1.8_Windows.zip) | 支座约束符号与给定位移显示 |
| V1.1.7 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.7/MatrixDisplacement_V1.1.7_Windows.zip) | 后台求解、按需绘图、错误定位 |
| V1.1.6 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.6/MatrixDisplacement_V1.1.6_Windows.zip) | 导出体验与四图批量导出 |
| V1.1.5 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.5/MatrixDisplacement_V1.1.5_Windows.zip) | 内力标注与布局优化 |
| V1.1.4 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.4/MatrixDisplacement_V1.1.4_Windows.zip) | 历史版本 |
| V1.1.3 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.3/MatrixDisplacement_V1.1.3_Windows.zip) | 历史版本 |
| V1.1.2 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.2/MatrixDisplacement_V1.1.2_Windows.zip) | 历史版本 |
| V1.1.1 | [下载 ZIP](https://github.com/ZeyuWen17/MatrixDisplacement/releases/download/v1.1.1/MatrixDisplacement_V1.1.1_Windows.zip) | 历史版本 |

V1.1 仅保留源码归档。完整版本说明及附件见 [Releases](https://github.com/ZeyuWen17/MatrixDisplacement/releases)。页面中的 **Source code (zip/tar.gz)** 是源码，不是免安装程序。

V1.1.5～V1.2.0 包含运行说明，发布页附 SHA256 校验文件及解压自检记录。可在 PowerShell 使用 `Get-FileHash .\MatrixDisplacement_V1.2.0_Windows.zip -Algorithm SHA256` 核对下载文件。

### 运行最新源码（Windows）

安装 Python 3.12，下载或克隆仓库，然后在 PowerShell 执行：

```powershell
git clone https://github.com/ZeyuWen17/MatrixDisplacement.git
cd MatrixDisplacement/source/matrix_displacement_v11
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
.\.venv\Scripts\python.exe -m matrix_displacement.gui
```

也可从仓库首页选择 **Code → Download ZIP**，解压后进入 `source/matrix_displacement_v11`，从创建虚拟环境开始执行。安装依赖需要联网；后续启动只需执行最后一行。

## 快速上手

1. 启动后使用默认悬臂梁，或从“教学算例”菜单选择连续梁、平面桁架等示例。
2. 选择“教学模式（保留组装矩阵）”，按 **Ctrl+R** 计算。
3. 在“计算结果”中查看数值、杆件截面、内力图和变形图。
4. 按 **Ctrl+S** 保存模型；从“分析与导出”菜单导出报告、CSV 或图片。

输入框支持 `10 kN`、`200 mm`、`210 GPa`、`100 cm²` 等单位后缀，并校验量纲；不带单位时使用 **m、N、Pa、m²、m⁴、N·m、rad**，保存和结果保持 SI。整体 X 向右、Y 向上，向下的整体竖向力取负值。修改模型后须重新计算。

完整建模练习、单位换算、单元选择、荷载编辑、恢复方法和快捷键见[程序使用指南](source/matrix_displacement_v11/docs/USER_GUIDE.md)。

## 工况与组合快速使用

1. 建模并输入第一组荷载，从“分析与导出 → 荷载工况与组合”命名 `G`，点击“保存当前荷载为工况”。
2. 点击“清空当前荷载并返回建模”，输入另一组荷载，再打开管理窗口保存为 `Q`。
3. 在组合系数表填写 `G=1.2`、`Q=1.4`，命名并保存组合；点击“应用表中系数并返回”，按 `Ctrl+R` 计算。
4. 应用工况或组合会替换当前荷载；先保存需要保留的荷载。窗口中点击“取消”放弃该窗口全部修改。`Ctrl+S` 将当前荷载、工况和组合一起保存。

组合只叠加荷载，给定位移属于共享支座并施加一次；不自动提供规范组合或包络。修改几何后，失效工况会在应用时提示错误，需重新保存。

## 适用范围

- 面向二维线弹性静力分析与教学，暂不支持空间结构、非线性、动力学或规范设计。
- 内力图极值来自截面采样，不等同于严格解析极值；密集模型建议隐藏数值标注并使用截面查询。
- 自动恢复存在防抖间隔，不保证每次编辑即时备份；重要修改请主动保存。
- 取消计算会丢弃结果并等待数值求解安全结束；绘图可在分阶段边界取消。完整标注布局及单张 PNG 写入不可中途打断，取消在步骤结束后生效。已完成图片保留，失败写入不破坏原图。
- 重要结果应结合教材解析解或独立计算核对。多显示器及独立无 Python 电脑的运行验收仍待完成。

## 开发与文档

源码位于 `source/matrix_displacement_v11`；其中 `matrix_displacement/` 为程序，`tests/` 为测试，`examples/` 为示例，`scripts/` 为构建工具，`docs/` 为文档。目录名不代表当前版本号。

在源码目录执行 Windows 自动验收与构建：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_acceptance.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_exe_windows.ps1
```

- [程序使用指南](source/matrix_displacement_v11/docs/USER_GUIDE.md)
- [更新记录](source/matrix_displacement_v11/CHANGELOG.md)
- [V1.1.6 验收记录](source/matrix_displacement_v11/docs/V1.1.6_VALIDATION.md)
- [V1.1.7 优化与验收记录](source/matrix_displacement_v11/docs/V1.1.7_VALIDATION.md)
- [需求与开发进度](source/matrix_displacement_v11/任务单.md)

支座符号及约束含义见[使用指南](source/matrix_displacement_v11/docs/USER_GUIDE.md#如何识别支座符号)，新版验证见[V1.2.0 验收记录](source/matrix_displacement_v11/docs/V1.2.0_VALIDATION.md)。

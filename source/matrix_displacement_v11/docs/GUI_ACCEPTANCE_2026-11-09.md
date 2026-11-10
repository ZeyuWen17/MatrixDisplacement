# 基础 GUI 工作流程验收（2026-11-09）

环境：Windows，项目 `.venv`，PySide6 最新源码。现有 V1.1.4 EXE 未重建。

## 已完成

- 前序手工悬臂梁：新建节点、杆件、固定约束和端部集中力，求解、保存 JSON、撤销/重做、重新打开。
- 本次重新启动最新源码，确认固定端斜线符号、约束文字及数值结果等宽排版。
- 使用默认悬臂梁（4 m，E=2.1e11 Pa，I=8e-6 m⁴，均布荷载 -1200 N/m，x=1.7 m 处集中力 -700 N）求解。
- 通过“分析与导出”菜单完成 Markdown 报告、CSV 目录及当前弯矩图 PNG 导出，未通过脚本替代菜单操作。
- 读回导出文件：竖向反力 5500 N，反力矩 10790 N·m，端部位移 -0.024924295634920636 m；弯矩固定端 -10790 N·m，自由端接近零。图片打开正常，标题、曲线和坐标未截断。

## 验收产物

- [教学报告](../outputs/acceptance/2026-11-09/teaching_report.md)
- [节点结果](../outputs/acceptance/2026-11-09/csv_results/nodal_results.csv)
- [杆端力](../outputs/acceptance/2026-11-09/csv_results/element_end_forces.csv)
- [截面内力](../outputs/acceptance/2026-11-09/csv_results/section_forces.csv)
- [变形数据](../outputs/acceptance/2026-11-09/csv_results/deformations.csv)
- [弯矩图](../outputs/acceptance/2026-11-09/moment.png)

弯矩图叠加在结构几何坐标上并自动缩放；不能将纵轴的 m 当作弯矩读数，精确弯矩读取截面查询或 CSV 的 M_Nm 列。

## 范围与后续

本轮基础流程通过；未覆盖全部结构类型、多显示器和 DPI 组合。上轮源码完整自动回归为 288 passed、1 skipped，本轮未修改计算源码。下一步可完善内力图的关键值标注和中文说明，提高初学者读图体验。

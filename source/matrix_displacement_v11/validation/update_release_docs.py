from pathlib import Path
root = Path(__file__).resolve().parents[1]
readme = root / 'README.md'
old = readme.read_text(encoding='utf-8')
(root / 'docs' / 'README_V1.1.0_HISTORY.md').write_text(old, encoding='utf-8')
current = '''# MatrixDisplacement 矩阵位移法教学系统

**当前版本：V1.1.1，Windows 自动验收通过，完整真实交互验收尚未完成。**

## 用户需求与已有能力

用于结构力学课程学习，支持连续梁、平面桁架、平面刚架和刚架—桁架混合模型。采用 Python / NumPy / Matplotlib / PySide6，先保证矩阵位移法内核，再完善图形交互。

已实现单元刚度、坐标转换、整体组装、自由度管理、节点位移、反力、杆端内力；支持节点及杆件荷载、杆端释放、N/V/M 与变形图、截面查询、教学/快速模式、JSON/CSV/PNG/教学报告。GUI 源码具备建模、框选、多选、批量编辑、撤销重做、自动保存和崩溃草稿恢复。

## 本次完成

- 修复 Windows PowerShell 5.1 的中文编码和命令引号问题。
- GUI 标题、程序版本及测试统一为 1.1.1，修复遗留 V1.0 断言。
- 自动测试隔离恢复目录，避免接触用户真实草稿。
- 修复打包时误收集其他工具 ICU DLL 导致 QtCore 加载失败的问题。
- 构建增加受控 PATH、按需模块收集、可跳过依赖安装、EXE 自检超时与退出码检查。
- **本机 270 项测试通过，1 项仅适用于非 Windows 的测试跳过；Qt 测试全部执行。**
- **Windows 源码验收脚本通过，EXE 已构建，打包后 Qt/求解/四幅结果图/恢复快照自检通过。**

## 使用与交付

已构建程序位于 `dist/MatrixDisplacement/MatrixDisplacement.exe`。必须保留整个 `MatrixDisplacement` 目录和 `_internal`，不能只复制 EXE。完整源码 ZIP 由 `python scripts/package_source.py` 生成。

从源码启动（在项目根目录）：

```powershell
py -3 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-gui.txt
.\\.venv\\Scripts\\python.exe -m matrix_displacement.gui
```

自动验收：`powershell -ExecutionPolicy Bypass -File scripts/windows_acceptance.ps1`。

构建：`powershell -ExecutionPolicy Bypass -File scripts/build_exe_windows.ps1`。依赖已安装时可加 `-SkipDependencyInstall`；`-SkipTests` 不跳过打包后自检。

## 证据与剩余工作

- 实际日志：`validation/pytest-final.txt`、`validation/pytest.xml`、`validation/windows-acceptance.txt`、`validation/build-fixed.txt`。
- 构建校验和与自检结果：`dist/MatrixDisplacement/BUILD_VALIDATION.txt`；副本 `validation/BUILD_VALIDATION.txt`。
- 完整说明：[V1.1.1 验收记录](docs/V1.1.1_WINDOWS_VALIDATION.md)。依赖版本见 `validation/requirements-tested.txt`。
- 本轮尝试打开真实窗口，但自动化未取得可操作的目标窗口，因此**真实窗口启动和鼠标交互不计为通过**，原因未确定；离屏通过不替代真实交互。
- 下一步优先：真实窗口与恢复弹窗验收、125%/150% DPI、多显示器、另一台无 Python 电脑运行；GitHub Actions 尚未执行。
- 后续功能：多实例冲突提示、大模型性能和标签布局；在二维架构经过更多教材算例验证后再扩展空间结构。
- 尚未实现：并发冲突合并、完整 CAD 对齐/图层、全局无重叠标签、空间结构、非线性、动力学、规范设计及全面机构识别。

每阶段继续交付中文 README、CHANGELOG、测试证据和源代码 ZIP。V1.1.0 的详细功能及历史验证结果保留于 [历史 README](docs/README_V1.1.0_HISTORY.md)，其中“缺 Qt、非 Windows、未构建 EXE”只代表当时状态。

自动恢复有约 2.5 秒防抖窗口，不保证零数据丢失；只恢复模型，不含撤销历史和结果。软件用于教学和数值验证，尚不属于经认证的工程安全设计软件。
'''
readme.write_text(current, encoding='utf-8')
(root.parents[1] / 'README_matrix_displacement_V1.1.md').write_text(current.replace('](docs/', '](source/matrix_displacement_v11/docs/'), encoding='utf-8')

# V1.1 Windows source GUI+recovery automatic acceptance; manual checks still mandatory.
$ErrorActionPreference = 'Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if ($env:OS -ne 'Windows_NT') { throw '该脚本仅用于 Windows 实机验收。' }
    $python=Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { throw '未发现 .venv，请先安装 requirements-gui.txt。' }
    & $python -c 'import PySide6; from PySide6.QtWidgets import QApplication'
    if ($LASTEXITCODE -ne 0) { throw 'PySide6 导入失败。' }
    & $python -m compileall -q matrix_displacement examples tests
    if ($LASTEXITCODE -ne 0) { throw 'Python 语法检查失败。' }
    $previousQt=$env:QT_QPA_PLATFORM
    try {
        $env:QT_QPA_PLATFORM='offscreen'
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw '回归测试失败。' }
        & $python -m pytest -q tests/test_gui_smoke_v11.py
        if ($LASTEXITCODE -ne 0) { throw 'V1.1 Qt 自动保存/恢复测试失败。' }
        & $python -m matrix_displacement.gui --self-test
        if ($LASTEXITCODE -ne 0) { throw 'GUI 启动 + 求解 + 图形 + 恢复的端到端自检失败。' }
    }
    finally { $env:QT_QPA_PLATFORM=$previousQt }
    & $python -m examples.batch_workflow_v10
    if ($LASTEXITCODE -ne 0) { throw '批量编辑算例失败。' }
    & $python -m examples.continuous_beam
    if ($LASTEXITCODE -ne 0) { throw '连续梁数值示例失败。' }
    Write-Host '自动测试完成；真实鼠标、DPI、崩溃恢复、分发仍须人工检查。'
    Write-Host '请参照 docs/V1.1_WINDOWS_ACCEPTANCE.md。'
}
finally { Pop-Location }

# V1.1 Windows-only reproducible onedir build with packaged GUI+solver self-test.
# powershell -ExecutionPolicy Bypass -File .\scripts\build_exe_windows.ps1
param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if ($env:OS -ne 'Windows_NT') { throw '此脚本必须在 Windows 上执行。' }
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败。' }
    }
    & $python -m pip install -r requirements-build-windows.txt
    if ($LASTEXITCODE -ne 0) { throw '安装构建依赖失败。' }
    & $python -c 'import PySide6; from PySide6.QtWidgets import QApplication'
    if ($LASTEXITCODE -ne 0) { throw 'PySide6 无法导入。' }
    $previousQt = $env:QT_QPA_PLATFORM
    try {
        $env:QT_QPA_PLATFORM = 'offscreen'
        if (-not $SkipTests) {
            & $python -m pytest -q
            if ($LASTEXITCODE -ne 0) { throw '回归测试未通过。' }
            & $python -m pytest -q tests/test_gui_smoke_v11.py
            if ($LASTEXITCODE -ne 0) { throw 'V1.1 GUI 冒烟测试失败。' }
            & $python -m matrix_displacement.gui --self-test
            if ($LASTEXITCODE -ne 0) { throw '源码 Qt/求解器/自动保存自检失败。' }
        }
        & $python -m PyInstaller --noconfirm --clean --windowed --onedir `
            --name MatrixDisplacement `
            --paths $root `
            --collect-all PySide6 `
            --collect-all matplotlib `
            --hidden-import matplotlib.backends.backend_qtagg `
            scripts/gui_launcher.py
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败。' }
        $exe = Join-Path $root 'dist\MatrixDisplacement\MatrixDisplacement.exe'
        if (-not (Test-Path $exe)) { throw "未找到生成的 EXE：$exe" }
        # Even -SkipTests must not bypass packaged EXE execution verification.
        # Start-Process -Wait is needed because --windowed exe is a GUI subsystem binary.
        $process = Start-Process -FilePath $exe -ArgumentList '--self-test' -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "打包后的 EXE 离屏自检失败，退出代码 $($process.ExitCode)。请检查用户本地 GUI 错误日志。"
        }
        $sha = (Get-FileHash -Path $exe -Algorithm SHA256).Hash
        $report = Join-Path $root 'dist\MatrixDisplacement\BUILD_VALIDATION.txt'
        @(
            'MatrixDisplacement V1.1 - Windows build validation',
            "Validated at: $(Get-Date -Format o)",
            'Packaged --self-test: PASS (Qt offscreen + solver + plots + recovery)',
            "EXE SHA256: $sha",
            "Full regression run: $(if ($SkipTests) {'SKIPPED by operator'} else {'PASS'})",
            'Manual GUI mouse/DPI/other-PC tests: NOT YET VERIFIED'
        ) | Set-Content -Path $report -Encoding UTF8
        Write-Host "成功构建并完成离屏自检：$exe"
        Write-Host "构建验证记录：$report"
        Write-Host '仍须按 docs/V1.1_WINDOWS_ACCEPTANCE.md 验证真实窗口、多显示器、恢复流程和分发。'
    }
    finally { $env:QT_QPA_PLATFORM = $previousQt }
}
finally { Pop-Location }

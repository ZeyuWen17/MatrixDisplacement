# V1.1 Windows-only reproducible onedir build with packaged GUI+solver self-test.
# powershell -ExecutionPolicy Bypass -File .\scripts\build_exe_windows.ps1
param([switch]$SkipTests, [switch]$SkipDependencyInstall)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$previousPath = $env:PATH
Push-Location $root
try {
    if ($env:OS -ne 'Windows_NT') { throw '此脚本必须在 Windows 上执行。' }
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败。' }
    }
    if (-not $SkipDependencyInstall) {
        & $python -m pip install -r requirements-build-windows.txt
        if ($LASTEXITCODE -ne 0) { throw '安装构建依赖失败。' }
    }
    & $python -c 'import PySide6; from PySide6.QtWidgets import QApplication'
    if ($LASTEXITCODE -ne 0) { throw 'PySide6 无法导入。' }
    $version = & $python -c 'from matrix_displacement import __version__; print(__version__)'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read package version.' }
    $distRoot = Join-Path $root "dist\V$version"
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
        # Prevent unrelated tools on PATH from supplying incompatible Qt dependencies (e.g. ICU).
        $env:PATH = "$(Join-Path $root '.venv\Scripts');$env:SystemRoot\System32;$env:SystemRoot"
        & $python -m PyInstaller --noconfirm --clean --windowed --onedir `
            --distpath $distRoot `
            --name MatrixDisplacement `
            --paths $root `
            --hidden-import matplotlib.backends.backend_qtagg `
            scripts/gui_launcher.py
        if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 构建失败。' }
        $exe = Join-Path $distRoot 'MatrixDisplacement\MatrixDisplacement.exe'
        if (-not (Test-Path $exe)) { throw "未找到生成的 EXE：$exe" }
        # Even -SkipTests must not bypass packaged EXE execution verification.
        # Start-Process -Wait is needed because --windowed exe is a GUI subsystem binary.
        $process = Start-Process -FilePath $exe -ArgumentList '--self-test' -WindowStyle Hidden -PassThru
        if (-not $process.WaitForExit(120000)) {
            $process.Kill()
            throw '打包后的 EXE 自检超过 120 秒，已终止本次自检进程。'
        }
        $process.Refresh()
        if ($process.ExitCode -ne 0) {
            throw "打包后的 EXE 离屏自检失败，退出代码 $($process.ExitCode)。请检查用户本地 GUI 错误日志。"
        }
        $sha = (Get-FileHash -Path $exe -Algorithm SHA256).Hash
        $report = Join-Path $distRoot 'MatrixDisplacement\BUILD_VALIDATION.txt'
        @(
            'MatrixDisplacement V1.1.2 - Windows build validation',
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
finally { $env:PATH = $previousPath; Pop-Location }

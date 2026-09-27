# ============================================================
# loam - Windows PowerShell One-Click Setup & Launcher
# ============================================================
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
# ============================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "       Loam Windows Setup & Launcher     " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. 检查 Python 环境
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
} else {
    Write-Host "未找到 Python 3，请先安装 Python 3.9+ 并加入系统 PATH。" -ForegroundColor Red
    exit 1
}

$pyVer = & $pythonCmd --version 2>&1
Write-Host "-> 检测到 Python: $pyVer" -ForegroundColor Green

# 2. 检查配置目录
$loamHome = Join-Path $env:USERPROFILE ".loam"
if (-not (Test-Path $loamHome)) {
    New-Item -ItemType Directory -Path $loamHome -Force | Out-Null
}

$secretsFile = Join-Path $loamHome "secrets.json"
$upstreamsFile = Join-Path $loamHome "upstreams.json"

if (-not (Test-Path $secretsFile)) {
    $defaultSecrets = @{
        api_key = ""
        base_url = "https://api.deepseek.com"
        model = "deepseek-chat"
    } | ConvertTo-Json
    [System.IO.File]::WriteAllText($secretsFile, $defaultSecrets, [System.Text.Encoding]::UTF8)
    Write-Host "-> 已初始化配置模板: $secretsFile" -ForegroundColor Yellow
}

if (-not (Test-Path $upstreamsFile)) {
    $defaultUpstreams = @{
        default = "deepseek"
        providers = @{
            deepseek = @{
                base_url = "https://api.deepseek.com"
                api_key = ""
                default_model = "deepseek-chat"
            }
        }
    } | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($upstreamsFile, $defaultUpstreams, [System.Text.Encoding]::UTF8)
    Write-Host "-> 已初始化上游网关配置: $upstreamsFile" -ForegroundColor Yellow
}

# 3. 运行冒烟测试
Write-Host "`n-> 运行本地轻量端到端冒烟测试..." -ForegroundColor Cyan
& $pythonCmd e2e_smoke.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "冒烟测试未通过，请检查代码或依赖。" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n=========================================" -ForegroundColor Green
Write-Host "  环境配置完备，组件就绪！" -ForegroundColor Green
Write-Host "  后端端口: http://127.0.0.1:8765" -ForegroundColor Gray
Write-Host "  代理端口: http://127.0.0.1:8781" -ForegroundColor Gray
Write-Host "  管理后台: http://127.0.0.1:8900" -ForegroundColor Gray
Write-Host "=========================================" -ForegroundColor Green
Write-Host "输入 1 启动核心服务 (Loam + Proxy + Admin)" -ForegroundColor Yellow
Write-Host "输入 2 启动终端演化沙盒 (Demo Walkthrough)" -ForegroundColor Yellow
Write-Host "输入 3 运行全套单元测试" -ForegroundColor Yellow
Write-Host "输入 0 退出" -ForegroundColor Gray

$choice = Read-Host "`n请选择操作 [1/2/3/0] (默认 1)"
if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

switch ($choice) {
    "1" {
        Write-Host "启动 Loam 后端..." -ForegroundColor Cyan
        Start-Process $pythonCmd -ArgumentList "-m loam run"
        Write-Host "启动强制代理..." -ForegroundColor Cyan
        Start-Process $pythonCmd -ArgumentList "bridge/forced_flow_proxy.py"
        Write-Host "启动 Admin 后台..." -ForegroundColor Cyan
        Start-Process $pythonCmd -ArgumentList "scripts/admin.py"
        Start-Sleep -Seconds 1
        Start-Process "http://127.0.0.1:8900"
    }
    "2" {
        & $pythonCmd scripts/demo_walkthrough.py
    }
    "3" {
        Get-ChildItem tests\test_*.py | ForEach-Object {
            Write-Host "=== $($_.Name) ===" -ForegroundColor Cyan
            & $pythonCmd $_.FullName
        }
    }
    Default {
        Write-Host "已退出。"
    }
}

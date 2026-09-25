<#
.SYNOPSIS
  把 damo 当**本机应用**打开: 一个进程(API + 界面) + 一个窗口。

.DESCRIPTION
  与 dev-up.ps1 的分工: dev-up 面向改代码(前端 dev server、热更新、灌种子); 这个面向用 ——
  直接吃 frontend/dist 的产物, 单进程, 关窗即停。

  四条约定:

    - 不动仓库: 只写 .dev(日志与 pid), 不生成也不改 .env
    - 认得出自己: 端口上跑的已经是本实例就直接复用, 不再起第二个, 也不重复开窗
    - 关窗即停: 窗口一关就把服务收掉; 找不到能开应用窗口的浏览器时退回默认浏览器, 那时
      服务留在后台, 用 -Down 收
    - 失败说人话: 起不来时弹一个对话框指出日志在哪, 而不是留一个空窗口让人猜;
      数据库没起也一样 —— **不启动**一个每个接口都会 500 的空壳

.PARAMETER Port
  应用端口, 默认 8100(与 dev-up 的 8000/8010 错开, 两边可以同时开着)。
.PARAMETER DatabaseUrl
  直接指定 DATABASE_URL; 不给就按 dev-up 那套探测: DATABASE_URL 环境变量 -> 5432 -> 55432。
.PARAMETER Rebuild
  先重新 build 前端产物。改了前端代码, 或拿不准 dist 是不是最新的, 加这个。
.PARAMETER NoWindow
  只起服务不开窗口(给脚本/CI 用)。
.PARAMETER KeepServer
  关窗之后不停服务, 留着给浏览器直接用。
.PARAMETER Down
  收掉本脚本起的实例, 不碰别的进程。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/damo-app.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/damo-app.ps1 -Rebuild

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/damo-app.ps1 -Down
#>
[CmdletBinding()]
param(
    [int]$Port = 8100,
    [string]$DatabaseUrl = "",
    [string]$PgHost = "127.0.0.1",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$Database = "attraction_atlas",
    [switch]$Rebuild,
    [switch]$NoWindow,
    [switch]$KeepServer,
    [switch]$Down
)

$ErrorActionPreference = "Stop"

$Root        = Split-Path -Parent $PSScriptRoot
$DevDir      = Join-Path $Root ".dev"
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$DistDir     = Join-Path $FrontendDir "dist"
$SelfPath    = Join-Path $PSScriptRoot "damo-app.ps1"
$AppUrl      = "http://127.0.0.1:$Port/"
$HealthUrl   = "http://127.0.0.1:$Port/api/v1/healthz"
$PidFile     = Join-Path $DevDir "app.pid"
$OutLog      = Join-Path $DevDir "app.out.log"
$ErrLog      = Join-Path $DevDir "app.err.log"
$ProfileDir  = Join-Path $DevDir "app-profile"

if (-not (Test-Path $DevDir)) { $null = New-Item -ItemType Directory -Path $DevDir }

function Write-Info { param([string]$Msg) Write-Host "[damo] $Msg" }
function Write-Note { param([string]$Msg) Write-Host "[damo] $Msg" -ForegroundColor DarkGray }
function Write-Warn { param([string]$Msg) Write-Host "[damo][warn] $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "[damo][error] $Msg" -ForegroundColor Red }
function Test-Port {
    param([string]$TargetHost, [int]$Port2)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($TargetHost, $Port2, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-Health {
    # 这个端口上是不是我们的应用: 是就返回 healthz 的内容, 否则 $null。
    # 只认 /api/v1/healthz 的形状 —— 端口被别的程序占着时, 那个程序多半不会回这个。
    try {
        $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
        if ($null -ne $r.status) { return $r }
        return $null
    } catch {
        return $null
    }
}

function Test-Healthy {
    param($Health)
    # **不能只看有没有 status 字段**: 数据库连不上时 healthz 照样回 200, 只是把 status
    # 报成 degraded —— 只看字段在不在, 等于把一个「每个接口都 500」的应用当好的开出去。
    # (2026-09-26 真出过这事: 便携实例非正常停止, 启动器探不到端口就退回默认的 5432 起了
    # 服务, 界面上推荐 / 分类 / 最新收录整片 500, 而没有任何一处说「数据库没起」。)
    return ($null -ne $Health) -and ($Health.status -eq "ok")
}

function Get-DbHint {
    # 只说「连不上」没用, 要给出能直接粘的起库命令 —— 「便携实例还躺在磁盘上却不在跑」
    # 是这台机器上最常见的那种「数据库没起」。
    if ((Test-Path "C:\pgtemp\pginstall\bin\pg_ctl.exe") -and (Test-Path "C:\pgtemp\pgdata")) {
        return "便携实例看起来是停的, 起来它(这台机器的库在 55432):`n`n  & C:\pgtemp\pginstall\bin\pg_ctl.exe -D C:\pgtemp\pgdata -l C:\pgtemp\pgdata\server.log -o ""-p 55432 -c listen_addresses=127.0.0.1"" start`n"
    }
    return "起库命令见 scripts/dev-up.ps1 顶部注释, 或用 -PgPort / -PgBin 指到已有实例。"
}

function Show-Alert {
    param([string]$Title, [string]$Text)
    # 界面起见窗口失败时, 这是唯一能把话说给用户听的地方(脚本自己没有窗口)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show($Text, $Title, "OK", "Warning")
    } catch {
        Write-Fail $Text
    }
}

function Stop-App {
    if (-not (Test-Path $PidFile)) { return $false }
    $recorded = 0
    [void][int]::TryParse((Get-Content $PidFile -Raw).Trim(), [ref]$recorded)
    if ($recorded -le 0 -or -not (Get-Process -Id $recorded -ErrorAction SilentlyContinue)) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return $false
    }
    # /T 连子孙一起收: uvicorn 的 --reload 外层是父进程, 真正 listen 的是子进程
    $null = taskkill /PID $recorded /T /F 2>&1
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    return $true
}
# ------------------------------------------------------------------ 收尾模式
if ($Down) {
    if (Stop-App) { Write-Info "已收掉 damo(pid 见 .dev\app.pid)" } else { Write-Note "没有本脚本起的 damo 在跑。" }
    exit 0
}

# ------------------------------------------------------------------ 产物
$needBuild = $Rebuild -or -not (Test-Path (Join-Path $DistDir "index.html"))
if ($needBuild) {
    if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
        Show-Alert "damo 起不来" "前端依赖还没装。先执行:`n`n    cd frontend`n    npm install`n`n然后再打开 damo。"
        Write-Fail "frontend\node_modules 不存在, 先 npm install"
        exit 1
    }
    Write-Info "构建前端产物(npm run build)..."
    Push-Location $FrontendDir
    try {
        $buildLog = Join-Path $DevDir "app.build.log"
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $build | Set-Content -Path $buildLog -Encoding utf8
    if ($code -ne 0 -or -not (Test-Path (Join-Path $DistDir "index.html"))) {
        Show-Alert "damo 起不来" "前端构建失败(退出码 $code)。日志: $buildLog"
        Write-Fail "npm run build 失败, 看 .dev\app.build.log"
        exit 1
    }
    Write-Info "产物就绪: $DistDir"
}

# ------------------------------------------------------------------ 起服务
$reused = $false
$health = Get-Health
if (Test-Healthy $health) {
    $reused = $true
    Write-Info "已经在跑(端口 $Port), 直接复用, 不再起第二个。"
} elseif ($health) {
    # 服务在, 但它自己说数据库连不上 —— 页面会整片 500。它的 DATABASE_URL 是启动那一刻
    # 定下的, 改不了, 所以只能收掉重开; 这里是「说清楚」, 不是「复用过去」。
    Show-Alert "damo 在跑, 但数据库连不上" "端口 $Port 上的实例回报 status=$($health.status) / database=$($health.database), 界面上每个接口都会 500。`n`n它的 DATABASE_URL 是启动时定下的, 改不了 —— 先把数据库起好, 再收掉重开:`n`n  damo.cmd -Down`n  damo.cmd`n`n$(Get-DbHint)"
    Write-Fail "端口 $Port 上的实例数据库连不上($($health.status)), 先 -Down 收掉再重开"
    exit 1
} elseif (Test-Port "127.0.0.1" $Port) {
    Show-Alert "端口 $Port 被占用" "那个程序不是 damo(没回 /api/v1/healthz)。`n`n换个端口:  damo.cmd -Port 8101`n或先停掉它。"
    Write-Fail "端口 $Port 被占用, 而且不是我们的应用"
    exit 1
} else {
    if (-not $DatabaseUrl) {
        if ($env:DATABASE_URL) {
            $DatabaseUrl = $env:DATABASE_URL
        } else {
            if (-not (Test-Port $PgHost $PgPort) -and (Test-Port $PgHost 55432)) {
                Write-Note "连不上 $PgHost`:$PgPort, 但 55432 有实例, 改用 55432。"
                $PgPort = 55432
            }
            if (-not (Test-Port $PgHost $PgPort)) {
                # 数据库没起就别启动: 起了也是一个每个接口都 500 的空壳, 而且窗口里看不出
                # 是数据库的问题(真出过事, 见 Test-Healthy 的注释)。
                Show-Alert "数据库没起" "连不上 $PgHost`:$PgPort —— 这样启动出来的应用每个接口都会 500。`n`n$(Get-DbHint)"
                Write-Fail "连不上 $PgHost`:$PgPort, 数据库没起, 不启动。"
                exit 1
            }
            $DatabaseUrl = "postgresql+psycopg://$PgUser@$($PgHost):$PgPort/$Database"
        }
    }
    $env:DATABASE_URL = $DatabaseUrl
    $env:SERVE_FRONTEND = "true"
    $env:FRONTEND_DIST = $DistDir
    $py = Join-Path $BackendDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        Show-Alert "damo 起不来" "没找到 backend\.venv\Scripts\python.exe。`n`n先建虚拟环境并装依赖:`n`n    cd backend`n    python -m venv .venv`n    .venv\Scripts\pip install -r requirements.txt"
        Write-Fail "backend.venv 不存在"
        exit 1
    }
    # 不开 --reload: 这是"用"的场景, 改代码请走 dev-up.ps1
    $proc = Start-Process -FilePath $py -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") -WorkingDirectory $BackendDir -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
    $proc.Id | Set-Content -Path $PidFile -Encoding ascii
    Write-Info "服务已起(pid $($proc.Id)), 日志 .dev\app.out.log"

    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Healthy (Get-Health)) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
    $health = Get-Health
    if (-not $health) {
        Show-Alert "damo 起不来" "服务 60 秒内没就绪。日志:`n$ErrLog"
        Write-Fail "服务没起来, 看 .dev\app.err.log"
        Stop-App | Out-Null
        exit 1
    }
    if (-not (Test-Healthy $health)) {
        # 进程活着但数据库连不上: 收掉它, 别留一个「看着像好的」的窗口
        Show-Alert "damo 起来了, 但数据库连不上" "status=$($health.status) / database=$($health.database)`n`nDATABASE_URL 用的是:`n$DatabaseUrl`n`n$(Get-DbHint)`n日志: $ErrLog"
        Write-Fail "数据库连不上, 已收掉这个实例(它只会一直 500)"
        Stop-App | Out-Null
        exit 1
    }
    Write-Info "就绪: $AppUrl"
}
function Find-AppBrowser {
    # --app= 能开出一个没有地址栏、有独立任务栏图标的窗口, 这就是「应用」的样子。
    # Edge 在 Win10/11 上是自带的, 排前面; LOCALAPPDATA 那份是 Chromium 的按用户安装。
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)
    foreach ($rel in @("Microsoft\Edge\Application\msedge.exe", "Google\Chrome\Application\chrome.exe")) {
        foreach ($root in $roots) {
            if (-not $root) { continue }
            $candidate = Join-Path $root $rel
            if (Test-Path $candidate) { return $candidate }
        }
    }
    return $null
}

function Get-AppWindow {
    # 挑出「命令行里带我们这个 profile 目录」的浏览器进程。不靠 Start-Process 返回的句柄:
    # 浏览器常常先起一个转交进程就退出, 句柄拿到手时已经死了, 等它会立刻误判成「窗口关了」。
    $filter = "Name = 'msedge.exe' OR Name = 'chrome.exe'"
    Get-CimInstance Win32_Process -Filter $filter -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($ProfileDir) }
}

# ------------------------------------------------------------------ 开窗口
if ($NoWindow) {
    Write-Info "服务在跑: $AppUrl"
    Write-Note "-NoWindow: 不开窗口。收它: damo.cmd -Down"
    exit 0
}

$browser = Find-AppBrowser
if (-not $browser) {
    Write-Warn "没找到 Edge/Chrome, 退回默认浏览器开页面。"
    Write-Note "这种情况服务会留在后台: 页面关掉后用 damo.cmd -Down 收。"
    Start-Process $AppUrl
    exit 0
}

Write-Info "打开应用窗口($(Split-Path -Leaf $browser))"
Start-Process -FilePath $browser -ArgumentList @(
    "--app=$AppUrl",
    "--user-data-dir=$ProfileDir",
    "--window-size=1360,900",
    "--no-first-run",
    "--no-default-browser-check",
    # 独立 profile 让窗口生命周期 = 进程生命周期, 顺手也不打扰用户自己的浏览器;
    # 关掉 Edge 的启动增强, 否则关窗后进程还在, 我们等不到「窗口关了」这一刻。
    "--disable-features=msEdgeStartupBoost"
) | Out-Null

$deadline = (Get-Date).AddSeconds(30)
while (-not (Get-AppWindow) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500 }
if (-not (Get-AppWindow)) {
    Show-Alert "damo 的窗口没开起来" "服务是好的, 直接访问 $AppUrl 也行。`n`n日志: $OutLog"
    Write-Fail "30 秒内没看到应用窗口"
    exit 1
}

Write-Note "应用已打开。关掉这个窗口就会把服务一起收掉(想留着: -KeepServer)。"
while (Get-AppWindow) { Start-Sleep -Seconds 2 }

if ($KeepServer) {
    Write-Info "窗口已关。-KeepServer: 服务留着, 用 damo.cmd -Down 收。"
    exit 0
}
if ($reused) {
    Write-Info "窗口已关。服务是复用已有实例, 不动它。"
    exit 0
}
Stop-App | Out-Null
Write-Info "窗口已关, 服务已停。"

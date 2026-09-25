<#
.SYNOPSIS
  Have-A-Trip 一键起本地开发环境: 连 PostgreSQL -> 灌 schema 与种子 -> 起后端 -> 起前端。

.DESCRIPTION
  只做本地开发。三条硬约束:

    - 幂等: 库连得上就接着用; schema.sql / seed.sql / attractions_cn.sql / images.sql 本身都可重复执行
    - 不装东西: 不下载不安装 PostgreSQL / Node / Python; 找不到 psql 只打印起库指引后退出
    - 不动仓库: 只写 .dev\(日志与 pid), 不生成也不修改 .env
    - 认得出自己: 端口被占时先看 .dev\<name>.pid 是不是本脚本起的那份, 是就直接复用并打印
      访问地址(重复跑不再报错); 不是才退出 —— 别人的进程不替它杀, 也不假装起好了

.PARAMETER BackendPort
  后端监听端口, 默认 8000。
.PARAMETER FrontendPort
  前端 dev server 端口, 默认 5173。
.PARAMETER PgPort
  PostgreSQL 端口, 默认 5432; 5432 不通时自动试探 55432(便携实例常用端口)。
.PARAMETER PgBin
  PostgreSQL bin 目录(含 psql.exe)。不给就依次找 PATH、Program Files、C:\pgtemp。
.PARAMETER DatabaseUrl
  直接指定后端的 DATABASE_URL; 不给就按 PgHost / PgPort / PgUser / Database 拼。
.PARAMETER Down
  只收尾: 按 .dev\*.pid 关掉本脚本起的后端与前端, 不碰别的进程。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-up.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-up.ps1 -PgBin C:\pgtemp\pginstall\bin -PgPort 55432

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-up.ps1 -Down
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$PgHost = "127.0.0.1",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$Database = "attraction_atlas",
    [string]$DatabaseUrl = "",
    [string]$PgBin = "",
    [string]$DbPassword = "",
    [switch]$NoSeed,
    [switch]$NoBackend,
    [switch]$NoFrontend,
    [switch]$Down,
    [string]$LlmProvider = "",
    [string]$LlmBaseUrl = "",
    [string]$LlmModel = "",
    [string]$LlmApiKey = ""
)

$ErrorActionPreference = "Stop"

$Root        = Split-Path -Parent $PSScriptRoot
$DevDir      = Join-Path $Root ".dev"
$BackendDir  = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$SelfPath    = Join-Path $PSScriptRoot "dev-up.ps1"
$BackendUrl  = "http://127.0.0.1:" + $BackendPort
$FrontendUrl = "http://127.0.0.1:" + $FrontendPort

if (-not (Test-Path $DevDir)) { $null = New-Item -ItemType Directory -Path $DevDir }

function Write-Info { param([string]$Msg) Write-Host "[dev-up] $Msg" }
function Write-Note { param([string]$Msg) Write-Host "[dev-up] $Msg" -ForegroundColor DarkGray }
function Write-Warn { param([string]$Msg) Write-Host "[dev-up][warn] $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "[dev-up][error] $Msg" -ForegroundColor Red }

function Test-Tcp {
    param([string]$TargetHost, [int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($TargetHost, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Resolve-Psql {
    if ($PgBin) {
        $explicit = Join-Path $PgBin "psql.exe"
        if (Test-Path $explicit) { return $explicit }
        Write-Fail "PgBin 下没有 psql.exe: $PgBin"
        exit 1
    }
    $onPath = Get-Command psql -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    foreach ($pattern in @("C:\Program Files\PostgreSQL\*\bin\psql.exe", "C:\pgtemp\pginstall\bin\psql.exe")) {
        $hit = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

function Get-OursRunning {
    # 端口被占不等于"我们已经在跑"。两个条件都要满足, 缺一不可:
    #   1. .dev 里那份 <name>.pid 记的进程还活着(那是本脚本自己写下的凭据);
    #   2. 真正在监听这个端口的进程就是它, 或者是它的子孙 —— uvicorn 的 --reload 外层是
    #      父进程, 真正 listen 的是子进程, 只比 pid 会漏掉这种情况。
    # 只看第 1 条会在"换 -BackendPort 起, 而新端口恰好被别的项目占着"时误判成自己的。
    param([string]$Name, [int]$Port)
    if (-not (Test-Tcp "127.0.0.1" $Port)) { return 0 }
    $pidFile = Join-Path $DevDir "$Name.pid"
    if (-not (Test-Path $pidFile)) { return 0 }
    $recorded = 0
    [void][int]::TryParse((Get-Content $pidFile -Raw).Trim(), [ref]$recorded)
    if ($recorded -le 0) { return 0 }
    if (-not (Get-Process -Id $recorded -ErrorAction SilentlyContinue)) { return 0 }

    $owner = 0
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) { $owner = [int]$conn.OwningProcess }
    if ($owner -le 0) { return 0 }
    if ($owner -eq $recorded) { return $recorded }

    # 父子关系一次查全, 再在内存里往上走, 别每一层都打一次 WMI
    $parents = @{}
    foreach ($proc in Get-CimInstance Win32_Process -ErrorAction SilentlyContinue) {
        $parents[[int]$proc.ProcessId] = [int]$proc.ParentProcessId
    }
    $current = $owner
    for ($hop = 0; $hop -lt 8 -and $current -gt 0; $hop++) {
        if ($current -eq $recorded) { return $recorded }
        if (-not $parents.ContainsKey($current)) { break }
        $next = $parents[$current]
        if ($next -eq $current) { break }
        $current = $next
    }
    return 0
}

function Wait-Http {
    param([string]$Url, [int]$TimeoutSec, [string]$Name, [string]$LogTail)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) { return $true }
        } catch { }
        Start-Sleep -Milliseconds 800
    }
    Write-Fail "$Name 在 $TimeoutSec 秒内没起来: $Url"
    if ($LogTail -and (Test-Path $LogTail)) {
        Write-Host "----- 日志尾部: $LogTail -----"
        Get-Content $LogTail -Tail 25
        Write-Host "-------------------------------"
    }
    return $false
}

# ------------------------------------------------------------------ 收尾
if ($Down) {
    $stopped = 0
    foreach ($name in @("backend", "frontend")) {
        $pidFile = Join-Path $DevDir "$name.pid"
        if (-not (Test-Path $pidFile)) { Write-Note "$name 没有 pid 记录, 跳过"; continue }
        $targetId = 0
        [void][int]::TryParse((Get-Content $pidFile -Raw).Trim(), [ref]$targetId)
        Remove-Item $pidFile -Force
        if ($targetId -le 0) { continue }
        if (-not (Get-Process -Id $targetId -ErrorAction SilentlyContinue)) {
            Write-Note "$name(pid $targetId)已经不在了"
            continue
        }
        & taskkill /PID $targetId /T /F | Out-Null
        Write-Info "$name 已停(pid $targetId, 含子进程)"
        $stopped++
    }
    Write-Info "收尾完成, 共停 $stopped 个进程。"
    exit 0
}

# ------------------------------------------------------------------ 数据库
if ($Database -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    Write-Fail "库名只允许字母数字下划线: $Database"
    exit 1
}

$psql = Resolve-Psql
if (-not $psql) {
    Write-Fail "找不到 psql; 本脚本不代装数据库。"
    Write-Host @"
先起一个 PostgreSQL 16, 再回来跑本脚本。便携实例的起法:

  # 一次性初始化(二进制作解压到 C:\pgtemp\pginstall)
  & C:\pgtemp\pginstall\bin\initdb.exe -D C:\pgtemp\pgdata -U postgres -E UTF8 --locale=C

  # 起库(端口 55432, trust 认证, 只听本机)
  & C:\pgtemp\pginstall\bin\pg_ctl.exe -D C:\pgtemp\pgdata -l C:\pgtemp\pgdata\server.log -o "-p 55432 -c listen_addresses=127.0.0.1" start

  # 再跑本脚本
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-up.ps1 -PgBin C:\pgtemp\pginstall\bin -PgPort 55432
"@
    exit 1
}

$binDir = Split-Path -Parent $psql
if ($DbPassword) { $env:PGPASSWORD = $DbPassword }
# 种子文件是 UTF-8, 而 Windows 控制台默认代码页(936)会把中文读花; 除非外面已经指定过, 一律强制 UTF8
if (-not $env:PGCLIENTENCODING) { $env:PGCLIENTENCODING = "UTF8" }
Write-Info "psql: $psql"

if (-not (Test-Tcp $PgHost $PgPort)) {
    if ($PgPort -eq 5432 -and (Test-Tcp $PgHost 55432)) {
        Write-Warn "连不上 $($PgHost):5432, 但 55432 有实例, 自动改用 55432。"
        $PgPort = 55432
    } else {
        Write-Fail "连不上 $($PgHost):$($PgPort), 数据库没起。"
        Write-Host "  起库命令见 scripts/dev-up.ps1 顶部注释, 或用 -PgPort / -PgBin 指到已有实例。"
        exit 1
    }
}

$exists = & $psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc "select 1 from pg_database where datname = '$Database'"
if ($LASTEXITCODE -ne 0) {
    Write-Fail "连库失败, 检查用户名 / 口令 / pg_hba 认证方式。"
    exit 1
}

if (-not $exists) {
    $createdb = Join-Path $binDir "createdb.exe"
    if (-not (Test-Path $createdb)) {
        Write-Fail "库 $Database 不存在, 且同目录下没有 createdb.exe。"
        exit 1
    }
    Write-Info "库 $Database 不存在, 新建。"
    & $createdb -h $PgHost -p $PgPort -U $PgUser -E UTF8 $Database
    if ($LASTEXITCODE -ne 0) { Write-Fail "createdb 失败。"; exit 1 }
} else {
    Write-Info "库 $Database 已存在, 直接复用。"
}

$sqlFiles = @("db\schema.sql")
if ($NoSeed) {
    Write-Note "-NoSeed: 跳过种子数据, 只应用 schema。"
} else {
    # 三个种子文件都要灌: seed.sql 是自采档案, attractions_cn.sql 是官方名录(1229 条),
    # images.sql 是配图。images.sql 必须排在两个景点文件之后 —— 它按 slug 关联景点。
    $sqlFiles += @("db\seed\seed.sql", "db\seed\attractions_cn.sql", "db\seed\images.sql")
}

foreach ($rel in $sqlFiles) {
    $file = Join-Path $Root $rel
    if (-not (Test-Path $file)) { Write-Fail "缺少 $rel"; exit 1 }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $psql -h $PgHost -p $PgPort -U $PgUser -d $Database -v ON_ERROR_STOP=1 -q -c "set client_min_messages=warning" -f $file
    if ($LASTEXITCODE -ne 0) { Write-Fail "$rel 执行失败(psql 退出码 $LASTEXITCODE)"; exit 1 }
    $sw.Stop()
    Write-Info "$rel 已应用($([int]$sw.Elapsed.TotalSeconds) 秒)"
}

$count = & $psql -h $PgHost -p $PgPort -U $PgUser -d $Database -tAc "select count(*) from attraction"
Write-Info "库内景点数: $count"

# ------------------------------------------------------------------ 子进程环境
if ($DatabaseUrl) {
    $env:DATABASE_URL = $DatabaseUrl
} else {
    $cred = $PgUser
    if ($DbPassword) { $cred = "$($PgUser):$($DbPassword)" }
    $env:DATABASE_URL = "postgresql+psycopg://$($cred)@$($PgHost):$($PgPort)/$Database"
}
$env:CORS_ORIGINS  = "http://localhost:$($FrontendPort),http://127.0.0.1:$($FrontendPort)"
$env:DEV_API_PROXY = $BackendUrl
if ($LlmProvider) { $env:LLM_PROVIDER = $LlmProvider }
if ($LlmBaseUrl)  { $env:LLM_BASE_URL  = $LlmBaseUrl }
if ($LlmModel)    { $env:LLM_MODEL    = $LlmModel }
if ($LlmApiKey)   { $env:LLM_API_KEY  = $LlmApiKey }
Write-Note "DATABASE_URL=$($env:DATABASE_URL)"

# ------------------------------------------------------------------ 后端
$backendStarted = $false
$backendReused = $false
if ($NoBackend) {
    Write-Note "-NoBackend: 不起后端。"
} elseif (Test-Tcp "127.0.0.1" $BackendPort) {
    $ours = Get-OursRunning -Name "backend" -Port $BackendPort
    if ($ours -gt 0) {
        $backendReused = $true
        Write-Info "后端已经在跑(pid $ours), 直接复用, 不再起第二个。"
    } else {
        Write-Fail "端口 $BackendPort 已被占用, 而且不是本脚本起的(没有 .dev\backend.pid, 或那个进程已经不在)。"
        Write-Host "  先停掉那个进程, 或换端口: -BackendPort 8011"
        exit 1
    }
} else {
    $py = Join-Path $BackendDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        $py = "python"
        Write-Warn "没找到 backend\.venv\Scripts\python.exe, 回落到全局 python; 依赖没装会起不来。"
    }
    $spArgs = @{
        FilePath               = $py
        ArgumentList           = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort", "--reload")
        WorkingDirectory       = $BackendDir
        WindowStyle            = "Hidden"
        RedirectStandardOutput = (Join-Path $DevDir "backend.out.log")
        RedirectStandardError  = (Join-Path $DevDir "backend.err.log")
        PassThru               = $true
    }
    $backendProc = Start-Process @spArgs
    $backendProc.Id | Set-Content -Path (Join-Path $DevDir "backend.pid") -Encoding ascii
    Write-Info "后端已起(pid $($backendProc.Id)), 日志 .dev\backend.out.log"
    $backendStarted = $true
}

if ($backendStarted) {
    Write-Info "等后端就绪: $($BackendUrl)/api/v1/healthz"
    $ok = Wait-Http -Url "$($BackendUrl)/api/v1/healthz" -TimeoutSec 40 -Name "后端" -LogTail (Join-Path $DevDir "backend.err.log")
    if (-not $ok) { Write-Warn "后端没起来, 先按上面日志排错; 前端仍会启动, 但 /api 会 502。" }
}

# ------------------------------------------------------------------ 前端
$frontendStarted = $false
$frontendReused = $false
if ($NoFrontend) {
    Write-Note "-NoFrontend: 不起前端。"
} elseif (Test-Tcp "127.0.0.1" $FrontendPort) {
    $ours = Get-OursRunning -Name "frontend" -Port $FrontendPort
    if ($ours -gt 0) {
        $frontendReused = $true
        Write-Info "前端已经在跑(pid $ours), 直接复用, 不再起第二个。"
    } else {
        Write-Fail "端口 $FrontendPort 已被占用, 而且不是本脚本起的(没有 .dev\frontend.pid, 或那个进程已经不在)。"
        Write-Host "  先停掉那个进程, 或换端口: -FrontendPort 5175"
        exit 1
    }
} elseif (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Fail "frontend\node_modules 不存在, 先 cd frontend; npm install"
    exit 1
} else {
    $viteJs = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"
    if (Test-Path $viteJs) {
        $file = "node"
        $argList = @($viteJs, "--port", "$FrontendPort", "--strictPort", "--host", "127.0.0.1")
    } else {
        $file = "npm.cmd"
        $argList = @("run", "start", "--", "--port", "$FrontendPort", "--strictPort", "--host", "127.0.0.1")
        Write-Warn "没找到 vite.js, 退回 npm.cmd; 这种起法关停可能留孤儿进程。"
    }
    $spArgs = @{
        FilePath               = $file
        ArgumentList           = $argList
        WorkingDirectory       = $FrontendDir
        WindowStyle            = "Hidden"
        RedirectStandardOutput = (Join-Path $DevDir "frontend.out.log")
        RedirectStandardError  = (Join-Path $DevDir "frontend.err.log")
        PassThru               = $true
    }
    $frontendProc = Start-Process @spArgs
    $frontendProc.Id | Set-Content -Path (Join-Path $DevDir "frontend.pid") -Encoding ascii
    Write-Info "前端已起(pid $($frontendProc.Id)), 日志 .dev\frontend.out.log"
    $frontendStarted = $true
}

if ($frontendStarted) {
    Write-Info "等前端就绪: $FrontendUrl"
    $ok = Wait-Http -Url $FrontendUrl -TimeoutSec 40 -Name "前端" -LogTail (Join-Path $DevDir "frontend.err.log")
    if (-not $ok) { Write-Warn "前端没起来, 看上面日志; vite 首次启动要预构建依赖, 慢一点正常。" }
}

# ------------------------------------------------------------------ 收尾提示
Write-Host ""
Write-Info "== 起来了 =="
if ($frontendStarted -or $frontendReused) { Write-Host "  前端      $FrontendUrl" }
if ($backendStarted -or $backendReused) {
    Write-Host "  接口文档  $($BackendUrl)/docs"
    Write-Host "  健康检查  $($BackendUrl)/api/v1/healthz"
}
Write-Host "  日志目录  $DevDir"
Write-Host "  关掉它们  powershell -NoProfile -ExecutionPolicy Bypass -File $SelfPath -Down"
if ($backendReused -or $frontendReused) {
    Write-Note "复用的那份是已经在跑的实例: 这一次给的 -LlmProvider / -LlmModel 等参数只对新起的"
    Write-Note "进程生效, 复用的还是它自己的配置; 要换配置就先 -Down 再起。"
}

if ($backendStarted -and -not $LlmProvider -and -not $env:LLM_PROVIDER) {
    Write-Note "AI 检索默认关闭(LLM_PROVIDER=none), 应用照常跑。想开本地模型: 装 ollama 并 pull 过模型后, 加 -LlmProvider ollama 再跑一次。"
}

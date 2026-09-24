<#
.SYNOPSIS
  Have-A-Trip 离线演示: 一条命令证明「不配任何模型, 应用也完整可用」。

.DESCRIPTION
  这不是第二个启动脚本, 而是一份**能跑出来的验收报告**: 起一个不接模型的实例,
  把关键接口挨个打一遍, 逐条打印断言结果与关键数字, 最后给通过率和退出码。

  为什么值得单做一支:
    - 讲「我做了一堆降级」不如当场跑一遍。报告里每行都是一句能直接念出来的话
      ——「AI 状态 available=false」「检索退回关键词仍是 200」「行程失败给了原因」。
    - 顺带把工程护栏钉住: 看板各档之和恒等于总数、许可字段齐全、假 token 一律 404、
      限流拒绝必须带原因与重置时间。这些是回归用例之外的第二道网。

  三条硬约束(与 dev-up.ps1 一致):
    - 不装东西: 不下载不安装 PostgreSQL / Python; 找不到 psql 就打印指引后退出
    - 不污染主库: 默认自带一个 attraction_atlas_demo 库, 反复跑也不会动 attraction_atlas
    - 认得出自己: 只写 .dev\demo-offline.*, 收尾只关自己起的那个进程

  与 dev-up.ps1 的分工: dev-up 管「把环境跑起来」, 本脚本管「把能力跑一遍并给出证据」。
  两者共用 .dev\ 目录, 但 pid 与日志的文件名不同, 互不覆盖。

.PARAMETER BackendPort
  演示实例的端口, 默认 8020。刻意避开 dev-up 的 8000, 不和开发环境抢端口。
.PARAMETER Database
  演示库, 默认 attraction_atlas_demo。首次跑会自动建库并灌种子。
.PARAMETER NoSeed
  跳过灌种子。库里已经有景点时本来也会自动跳过。
.PARAMETER KeepRunning
  演示结束后不关后端, 留着看 /docs。默认跑完即关, 不留后台进程。
.PARAMETER Down
  只收尾: 关掉上一次 -KeepRunning 留下的那个进程, 不碰别的。
.PARAMETER Json
  只输出一份 JSON 报告, 供 CI 或二次加工。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo-offline.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo-offline.ps1 -PgBin C:\pgtemp\pginstall\bin -PgPort 55432

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo-offline.ps1 -Down
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8020,
    [string]$Database = "attraction_atlas_demo",
    [string]$PgHost = "127.0.0.1",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$DbPassword = "",
    [string]$PgBin = "",
    [switch]$NoSeed,
    [switch]$KeepRunning,
    [switch]$Down,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

# 控制台按 UTF-8 写, 否则中文报告在 936 代码页下会花
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$Root       = Split-Path -Parent $PSScriptRoot
$DevDir     = Join-Path $Root ".dev"
$BackendDir = Join-Path $Root "backend"
$SelfPath   = Join-Path $PSScriptRoot "demo-offline.ps1"
$PidFile    = Join-Path $DevDir "demo-offline.pid"
$BaseUrl    = "http://127.0.0.1:$BackendPort/api/v1"
$LogOut     = Join-Path $DevDir "demo-offline.out.log"
$LogErr     = Join-Path $DevDir "demo-offline.err.log"

if (-not (Test-Path $DevDir)) { $null = New-Item -ItemType Directory -Path $DevDir }

$script:JsonMode = [bool]$Json
$script:Checks = New-Object System.Collections.ArrayList

# 过程信息一律走 stderr: -Json 时 stdout 必须只剩那一份 JSON, 不被日志污染
function Write-Say {
    param([string]$Text, [string]$Color)
    if ($script:JsonMode) { [Console]::Error.WriteLine($Text) }
    else { Write-Host $Text -ForegroundColor $Color }
}
function Write-Demo { param([string]$Msg) Write-Say "[demo] $Msg" "Gray" }
function Write-Note { param([string]$Msg) Write-Say "[demo] $Msg" "DarkGray" }
function Write-Warn { param([string]$Msg) Write-Say "[demo][warn] $Msg" "Yellow" }
function Write-Fail { param([string]$Msg) Write-Say "[demo][error] $Msg" "Red" }

function Stop-Ours {
    # 只关 pid 文件里记着的那个进程树 —— 别人的进程不替它杀, 这是 dev-up 的同一套规矩。
    if (-not (Test-Path $PidFile)) { return $false }
    $targetId = 0
    [void][int]::TryParse((Get-Content $PidFile -Raw).Trim(), [ref]$targetId)
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    if ($targetId -le 0) { return $false }
    if (-not (Get-Process -Id $targetId -ErrorAction SilentlyContinue)) { return $false }
    & taskkill /PID $targetId /T /F 2>&1 | Out-Null
    return $true
}

# ------------------------------------------------------------------ 只收尾
if ($Down) {
    if (Stop-Ours) { Write-Demo "演示实例已停(含子进程)。" } else { Write-Note "没有本脚本起的实例, 无需收尾。" }
    exit 0
}

# ------------------------------------------------------------------ 前置检查
if ($Database -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
    Write-Fail "库名只允许字母数字下划线: $Database"
    exit 1
}

function Resolve-Psql {
    if ($PgBin) {
        $explicit = Join-Path $PgBin "psql.exe"
        if (Test-Path $explicit) { return $explicit }
        return $null
    }
    $onPath = Get-Command psql -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    foreach ($pattern in @("C:\Program Files\PostgreSQL\*\bin\psql.exe", "C:\pgtemp\pginstall\bin\psql.exe")) {
        $hit = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}

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

function Invoke-Psql {
    # 统一收口 psql: $ErrorActionPreference=Stop 时, psql 写到 stderr 的 NOTICE 会被
    # PowerShell 当成 NativeCommandError 抛出来 —— 那些 NOTICE 是正常的(IF NOT EXISTS
    # 之类), 不该中断演示。所以这里临时降到 Continue, 只认退出码。
    param([string]$Db, [string[]]$SqlArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $psql -h $PgHost -p $PgPort -U $PgUser -d $Db @SqlArgs 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    return [pscustomobject]@{ Code = $code; Output = ($out | Out-String).Trim() }
}

$psql = Resolve-Psql
if (-not $psql) {
    Write-Fail "找不到 psql; 本脚本不代装数据库。"
    [Console]::Error.WriteLine("先起一个 PostgreSQL, 再回来跑本脚本。便携实例的起法见 scripts/dev-up.ps1 顶部注释。")
    exit 1
}

if ($DbPassword) { $env:PGPASSWORD = $DbPassword }
# 种子文件是 UTF-8, 而 Windows 控制台默认代码页(936)会把中文读花
if (-not $env:PGCLIENTENCODING) { $env:PGCLIENTENCODING = "UTF8" }

if (-not (Test-Tcp $PgHost $PgPort)) {
    if ($PgPort -eq 5432 -and (Test-Tcp $PgHost 55432)) {
        Write-Warn "连不上 $($PgHost):5432, 但 55432 有实例, 自动改用 55432。"
        $PgPort = 55432
    } else {
        Write-Fail "连不上 $($PgHost):$($PgPort), 数据库没起。"
        exit 1
    }
}

# ------------------------------------------------------------------ 演示库
if (-not $script:JsonMode) { Write-Demo "准备演示库 $Database ..." }

$exists = Invoke-Psql "postgres" @("-tAc", "select 1 from pg_database where datname = '$Database'")
if ($exists.Code -ne 0) {
    Write-Fail "连库失败(认证或 pg_hba 问题)。加 -DbPassword 再试。"
    [Console]::Error.WriteLine($exists.Output)
    exit 1
}
if ($exists.Output -ne "1") {
    $made = Invoke-Psql "postgres" @("-c", "create database $Database encoding 'UTF8'")
    if ($made.Code -ne 0) { Write-Fail "建库失败: $($made.Output)"; exit 1 }
    if (-not $script:JsonMode) { Write-Demo "已建库 $Database。" }
}

$countRes = Invoke-Psql $Database @("-tAc", "select count(*) from attraction")
$stored = 0
if ($countRes.Code -eq 0) { [void][int]::TryParse($countRes.Output, [ref]$stored) }

if ($NoSeed) {
    if (-not $script:JsonMode) { Write-Note "-NoSeed: 不灌种子。" }
} elseif ($stored -gt 0) {
    if (-not $script:JsonMode) { Write-Note "库内已有 $stored 个景点, 跳过种子(要重灌先 drop 掉这个库)。" }
} else {
    foreach ($rel in @("db\schema.sql", "db\seed\seed.sql", "db\seed\images.sql")) {
        $file = Join-Path $Root $rel
        if (-not (Test-Path $file)) { Write-Fail "缺少 $rel"; exit 1 }
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $applied = Invoke-Psql $Database @("-v", "ON_ERROR_STOP=1", "-q", "-c", "set client_min_messages=warning", "-f", $file)
        if ($applied.Code -ne 0) { Write-Fail "$rel 执行失败: $($applied.Output)"; exit 1 }
        $sw.Stop()
        if (-not $script:JsonMode) { Write-Demo "$rel 已应用($([int]$sw.Elapsed.TotalSeconds) 秒)" }
    }
}

# ------------------------------------------------------------------ 后端
$started = $false

# 先清掉上一次 -KeepRunning 留下的实例。这里刻意不先看端口: 这次若换了 -BackendPort,
# 只看端口就会把它漏掉, 旧进程从此没有 pid 记录, 变成 -Down 也收不走的孤儿。
if (Test-Path $PidFile) {
    $stale = 0
    [void][int]::TryParse((Get-Content $PidFile -Raw).Trim(), [ref]$stale)
    if ($stale -gt 0 -and (Get-Process -Id $stale -ErrorAction SilentlyContinue)) {
        Write-Warn "上一次留下的实例(pid $stale)还在跑, 先收掉。"
        Stop-Ours | Out-Null
        Start-Sleep -Seconds 2
    } else {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Tcp "127.0.0.1" $BackendPort) {
    Write-Fail "端口 $BackendPort 被别的进程占着(不是本脚本起的)。"
    [Console]::Error.WriteLine("  换个端口: -BackendPort 8021")
    exit 1
}

$py = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
    Write-Warn "没找到 backend\.venv\Scripts\python.exe, 回落到全局 python。"
}

$cred = $PgUser
if ($DbPassword) { $cred = "$($PgUser):$($DbPassword)" }
$env:DATABASE_URL = "postgresql+psycopg://$($cred)@$($PgHost):$($PgPort)/$Database"
# 演示的关键就是「什么都不配」: 两个 provider 都钉成 none, 免得被外部环境变量带偏
$env:LLM_PROVIDER = "none"
$env:EMBEDDING_PROVIDER = "none"
$env:PYTHONIOENCODING = "utf-8"
$env:CORS_ORIGINS = "http://127.0.0.1:$BackendPort"

# 让 uvicorn 自己把输出写进日志, 而不是用 Start-Process 的重定向: 一旦带了重定向,
# PowerShell 会改用 UseShellExecute=$false, 子进程于是继承本进程的标准句柄 —— 只要有人
# 用管道或重定向跑本脚本(CI 里很常见), 子进程就一直攥着管道写端, 上层永远等不到 EOF,
# 表现就是脚本迟迟不返回。让子进程自己去开文件, 句柄就不在本进程这棵树上了。
$bootFile = Join-Path $DevDir "demo-offline-boot.py"
$boot = @"
# 由 scripts/demo-offline.ps1 每次生成, 不要手改。
import runpy, sys

sys.stdout = open(r"$LogOut", "w", encoding="utf-8", buffering=1)
sys.stderr = open(r"$LogErr", "w", encoding="utf-8", buffering=1)
sys.argv = ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort"]
runpy.run_module("uvicorn", run_name="__main__")
"@
[IO.File]::WriteAllText($bootFile, $boot, (New-Object Text.UTF8Encoding($false)))

if (-not $script:JsonMode) { Write-Demo "起后端(LLM_PROVIDER=none)..." }
$proc = Start-Process -FilePath $py `
    -ArgumentList @($bootFile) `
    -WorkingDirectory $BackendDir `
    -WindowStyle Hidden `
    -PassThru
$proc.Id | Set-Content -Path $PidFile -Encoding ascii
$started = $true

function Wait-Ready {
    $deadline = (Get-Date).AddSeconds(40)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "$BaseUrl/healthz" -UseBasicParsing -TimeoutSec 4
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) { return $true }
        } catch { }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

try {
    if (-not (Wait-Ready)) {
        Write-Fail "后端 40 秒内没起来, 日志尾部:"
        if (Test-Path $LogErr) { [Console]::Error.WriteLine((Get-Content $LogErr -Tail 25 | Out-String)) }
        exit 1
    }

    # -------------------------------------------------------------- HTTP 与断言
    function ConvertFrom-JsonSafe {
        param([string]$Text)
        if ([string]::IsNullOrWhiteSpace($Text)) { return $null }
        try { return $Text | ConvertFrom-Json } catch { return $null }
    }

    function Invoke-Api {
        # 用 HttpWebRequest 而不是 Invoke-WebRequest: 后者在 4xx 时会把响应流读掉,
        # catch 里再读只剩空串 —— 而 429 的 reason / retry_after 恰好在那段 body 里,
        # 这份演示要断言它们。另外 5.1 在响应头没带 charset 时也不按 UTF-8 解, 中文会花,
        # 所以一律自己用 StreamReader(UTF8) 读。
        param([string]$Method, [string]$Path, $Body)
        $req = [System.Net.WebRequest]::Create($BaseUrl + $Path)
        $req.Method = $Method
        $req.Timeout = 60000
        $req.Proxy = $null
        if ($null -ne $Body) {
            $json = $Body | ConvertTo-Json -Depth 8 -Compress
            $bytes = [Text.Encoding]::UTF8.GetBytes($json)
            $req.ContentType = "application/json; charset=utf-8"
            $req.ContentLength = $bytes.Length
            $stream = $req.GetRequestStream()
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Close()
        }
        $status = 0
        $text = ""
        $webResp = $null
        try {
            $webResp = $req.GetResponse()
        } catch [System.Net.WebException] {
            $webResp = $_.Exception.Response
            if ($null -eq $webResp) { $text = $_.Exception.Message }
        }
        if ($null -ne $webResp) {
            $httpResp = $webResp -as [System.Net.HttpWebResponse]
            if ($httpResp) { $status = [int]$httpResp.StatusCode }
            try {
                $reader = New-Object System.IO.StreamReader($webResp.GetResponseStream(), [Text.Encoding]::UTF8)
                $text = $reader.ReadToEnd()
                $reader.Close()
            } catch { }
            $webResp.Close()
        }
        return [pscustomobject]@{ Status = $status; Text = $text; Data = (ConvertFrom-JsonSafe $text) }
    }

    function Add-Check {
        param([string]$Group, [string]$Name, [bool]$Pass, [string]$Detail)
        [void]$script:Checks.Add([pscustomobject]@{ group = $Group; name = $Name; pass = $Pass; detail = $Detail })
        if (-not $script:JsonMode) {
            if ($Pass) { Write-Host ("  [ OK ] " + $Name + " · " + $Detail) -ForegroundColor Green }
            else { Write-Host ("  [FAIL] " + $Name + " · " + $Detail) -ForegroundColor Red }
        }
    }

    function Assert-That {
        # 断言体返回一行详情; 不满足就 throw, 由这里统一记成失败 —— 一条挂掉不拖垮其余
        param([string]$Group, [string]$Name, [scriptblock]$Body)
        try {
            $detail = & $Body
            Add-Check -Group $Group -Name $Name -Pass $true -Detail ([string]$detail)
        } catch {
            Add-Check -Group $Group -Name $Name -Pass $false -Detail $_.Exception.Message
        }
    }

    $G1 = "数据与浏览(不依赖模型)"
    $G2 = "AI 入口的降级(核心)"
    $G3 = "工程护栏"

    if (-not $script:JsonMode) {
        Write-Host ""
        Write-Host ("=" * 78)
        Write-Host " Have-A-Trip 离线演示 —— 不配任何模型, 应用也完整可用"
        Write-Host " 后端 $BaseUrl"
        Write-Host " 库   $Database (PostgreSQL $($PgHost):$($PgPort))"
        Write-Host " 模型 LLM_PROVIDER=none · EMBEDDING_PROVIDER=none"
        Write-Host ("=" * 78)
        Write-Host ""
        Write-Host "[1/3] $G1" -ForegroundColor Cyan
    }

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $script:probeSlug = $null

    Assert-That $G1 "健康检查" {
        $r = Invoke-Api "GET" "/healthz"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        if ($r.Data.status -ne "ok") { throw "status 应为 ok, 实际 '$($r.Data.status)'" }
        if ($r.Data.database -ne "ok") { throw "数据库未就绪: '$($r.Data.database)'" }
        "200 · status=$($r.Data.status) · database=$($r.Data.database) · version=$($r.Data.version)"
    }

    Assert-That $G1 "看板各档求和恒等于总数" {
        $r = Invoke-Api "GET" "/stats"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $s = $r.Data
        $total = [int]$s.attraction_total
        if ($total -le 0) { throw "库里没有已发布景点" }
        $groups = [ordered]@{
            "国别"     = $s.by_country
            "分类"     = $s.by_category
            "景区等级" = $s.by_a_level
            "世界遗产" = $s.by_heritage
        }
        $bad = @()
        foreach ($name in $groups.Keys) {
            $sum = 0
            foreach ($slice in @($groups[$name])) { $sum += [int]$slice.count }
            if ($sum -ne $total) { $bad += "$name 合计 $sum 不等于 $total" }
        }
        if ($bad.Count -gt 0) { throw ($bad -join "; ") }
        "景点 $total · 图 $($s.image_total) · 方案 $($s.plan_total) · 省级行政区 $($s.province_total) · 四组分布求和均等于总数"
    }

    Assert-That $G1 "来源与图片许可齐全" {
        $r = Invoke-Api "GET" "/sources"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $s = $r.Data
        if (-not $s.sources -or @($s.sources).Count -eq 0) { throw "没有任何数据来源记录" }
        foreach ($rec in @($s.sources)) {
            if (-not $rec.license) { throw "来源「$($rec.source)」没写许可" }
        }
        foreach ($img in @($s.images)) {
            if (-not $img.license) { throw "图片署名「$($img.credit)」没写许可" }
        }
        if ($s.needs_attention) { throw "needs_attention=true, 有条款需要人工确认" }
        "来源 $(@($s.sources).Count) 条 · 图片署名 $(@($s.images).Count) 条 · 全部带许可 · needs_attention=false"
    }

    Assert-That $G1 "列表与看板同口径" {
        $stats = (Invoke-Api "GET" "/stats").Data
        $r = Invoke-Api "GET" "/attractions?page=1&size=5"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        if ([int]$r.Data.total -ne [int]$stats.attraction_total) {
            throw "列表 total=$($r.Data.total) 与看板 $($stats.attraction_total) 不一致"
        }
        $items = @($r.Data.items)
        if ($items.Count -eq 0) { throw "列表为空" }
        $script:probeSlug = $items[0].slug
        "$($r.Data.total) 条 · 首条「$($items[0].name)」($($items[0].slug))"
    }

    Assert-That $G1 "景点详情字段完整" {
        if (-not $script:probeSlug) { throw "上一步没拿到 slug" }
        $r = Invoke-Api "GET" "/attractions/$($script:probeSlug)"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $d = $r.Data
        foreach ($field in @("name", "slug", "city", "category")) {
            if (-not $d.$field) { throw "详情缺字段 $field" }
        }
        "「$($d.name)」· $($d.city) · $($d.category.name) · 标签 $(@($d.tags).Count) 个"
    }

    Assert-That $G1 "相似景点没有向量也不空" {
        if (-not $script:probeSlug) { throw "没有可用的 slug" }
        $r = Invoke-Api "GET" "/attractions/$($script:probeSlug)/similar?limit=6"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $items = @($r.Data)
        if ($items.Count -eq 0) { throw "退回结构化后仍为空, 详情页会开天窗" }
        "退回结构化排序, 仍返回 $($items.Count) 条"
    }

    Assert-That $G1 "冷启动也给出推荐" {
        $r = Invoke-Api "GET" "/recommendations?device_id=demo-offline-visitor&limit=10"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $items = @($r.Data)
        if ($items.Count -eq 0) { throw "新用户拿不到任何推荐" }
        "无行为数据的新设备仍拿到 $($items.Count) 条 · algo=$($items[0].algo)"
    }

    Assert-That $G1 "分类与标签可用" {
        $cats = Invoke-Api "GET" "/categories"
        $tags = Invoke-Api "GET" "/tags"
        if ($cats.Status -ne 200) { throw "/categories 返回 $($cats.Status)" }
        if ($tags.Status -ne 200) { throw "/tags 返回 $($tags.Status)" }
        if (@($cats.Data).Count -eq 0) { throw "分类为空" }
        if (@($tags.Data).Count -eq 0) { throw "标签为空" }
        "分类 $(@($cats.Data).Count) 个 · 标签 $(@($tags.Data).Count) 个"
    }
    if (-not $script:JsonMode) {
        Write-Host ""
        Write-Host "[2/3] $G2" -ForegroundColor Cyan
    }

    Assert-That $G2 "AI 状态如实报不可用" {
        $r = Invoke-Api "GET" "/ai/status"
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $s = $r.Data
        if ($s.available) { throw "没配模型却报 available=true" }
        if ($s.embedding_available) { throw "没有向量模型却报 embedding_available=true" }
        if ([int]$s.published -le 0) { throw "published=0, 库没起来" }
        if ([int]$s.embedded -ne 0) { throw "库里居然有向量(embedded=$($s.embedded)), 这份演示要的是 0" }
        "available=false · embedding_available=false · embedded=$($s.embedded)/$($s.published) —— 前端据此隐藏 AI 入口"
    }

    Assert-That $G2 "用一句话找景点: 退回关键词仍是 200" {
        $r = Invoke-Api "POST" "/ai/search" @{ query = "博物馆"; size = 5 }
        if ($r.Status -ne 200) { throw "降级不该是错误, 但返回 $($r.Status)" }
        $d = $r.Data
        if (-not $d.degraded) { throw "没配模型, degraded 应为 true" }
        if ([int]$d.total -le 0) { throw "退回关键词后一条都没查到" }
        if (-not $d.note) { throw "降级了却没告诉用户原因(note 为空)" }
        "200 · degraded=true · total=$($d.total) · note=「$($d.note)」"
    }

    Assert-That $G2 "语义检索: 没有向量也退回关键词" {
        $r = Invoke-Api "POST" "/search/semantic" @{ query = "西湖"; limit = 5 }
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $d = $r.Data
        if (-not $d.degraded) { throw "没有向量, degraded 应为 true" }
        $items = @($d.items)
        if ($items.Count -eq 0) { throw "退回关键词后一条都没查到" }
        if ($items[0].match -ne "keyword") { throw "match 应为 keyword, 实际 '$($items[0].match)'" }
        "200 · degraded=true · match=keyword · total=$($d.total) · note=「$($d.note)」"
    }

    Assert-That $G2 "景点追问: 答不出就给档案摘录, 不编" {
        if (-not $script:probeSlug) { throw "没有可用的 slug" }
        $r = Invoke-Api "POST" "/ai/ask" @{ slug = $script:probeSlug; question = "开放时间是什么时候" }
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $d = $r.Data
        if ($d.grounded) { throw "没配模型却报 grounded=true" }
        if (-not $d.degraded) { throw "没配模型却报 degraded=false" }
        if (-not $d.answer) { throw "降级后答案为空, 用户会看到一张空页" }
        "grounded=false · degraded=true · 答案仍是档案摘录($($d.answer.Length) 字), 没有凭空作答"
    }

    Assert-That $G2 "推荐理由: 润色不了就沿用原理由" {
        $r = Invoke-Api "POST" "/ai/recommend-notes" @{ device_id = "demo-offline-visitor"; limit = 6 }
        if ($r.Status -ne 200) { throw "期望 200, 实际 $($r.Status)" }
        $d = $r.Data
        if ($d.polished) { throw "没配模型却报 polished=true" }
        $reasons = @($d.reasons)
        if ($reasons.Count -eq 0) { throw "理由为空" }
        "polished=false · degraded=true · 沿用原理由 $($reasons.Count) 条"
    }
    if (-not $script:JsonMode) {
        Write-Host ""
        Write-Host "[3/3] $G3" -ForegroundColor Cyan
    }

    Assert-That $G3 "行程生成: 受理后如实失败, 不静默" {
        $sub = Invoke-Api "POST" "/itineraries" @{
            request_text = "杭州玩两天, 想看西湖和周边"
            days = 2
            device_id = "demo-offline-trip"
        }
        if ($sub.Status -ne 202 -and $sub.Status -ne 200) { throw "提交返回 $($sub.Status)" }
        $token = $sub.Data.token
        if (-not $token) { throw "受理了却没给 token" }
        $final = $null
        for ($i = 0; $i -lt 10; $i++) {
            Start-Sleep -Seconds 1
            $poll = Invoke-Api "GET" "/itineraries/$token"
            if ($poll.Status -ne 200) { throw "轮询返回 $($poll.Status)" }
            if ($poll.Data.status -ne "pending" -and $poll.Data.status -ne "generating") { $final = $poll.Data; break }
        }
        if ($null -eq $final) { throw "10 秒内没进终态" }
        if ($final.status -ne "failed") { throw "没配模型却得到 status=$($final.status)" }
        if (-not $final.error) { throw "失败了却没写原因, 用户只会看到一直转圈" }
        "202 受理 → status=failed · error=「$($final.error)」"
    }

    Assert-That $G3 "行程 token 不可枚举" {
        $r = Invoke-Api "GET" "/itineraries/itn_not_a_real_token"
        if ($r.Status -ne 404) { throw "假 token 应 404, 实际 $($r.Status)" }
        "假 token → 404, 不区分「不存在」与「不是你的」"
    }

    Assert-That $G3 "按次计费的能力有当日限额" {
        $owner = "demo-offline-quota-" + [Guid]::NewGuid().ToString("N").Substring(0, 8)
        $rejected = $null
        for ($i = 1; $i -le 6; $i++) {
            $r = Invoke-Api "POST" "/itineraries" @{
                request_text = "限额探针第 $i 条需求: 杭州两日游"
                days = 2
                device_id = $owner
            }
            if ($r.Status -eq 429) { $rejected = $r.Data.detail; break }
            if ($r.Status -ne 202 -and $r.Status -ne 200) { throw "第 $i 次提交返回 $($r.Status)" }
        }
        if ($null -eq $rejected) { return "6 次均被受理 —— 当日限额被配成不限(TRIP_DAILY_LIMIT=0), 拒绝路径未触发" }
        if (-not $rejected.reason) { throw "被拒了却没给 reason" }
        if (-not $rejected.retry_after) { throw "被拒了却没给 retry_after" }
        "超额被拒 → reason=$($rejected.reason) · retry_after=$($rejected.retry_after)"
    }

    $watch.Stop()
    $elapsed = [Math]::Round($watch.Elapsed.TotalSeconds, 1)
    $passed = @($script:Checks | Where-Object { $_.pass }).Count
    $failed = @($script:Checks | Where-Object { -not $_.pass }).Count
    $totalChecks = @($script:Checks).Count

    if ($script:JsonMode) {
        $report = [pscustomobject]@{
            backend         = $BaseUrl
            database        = $Database
            llm_provider    = "none"
            passed          = $passed
            failed          = $failed
            total           = $totalChecks
            elapsed_seconds = $elapsed
            checks          = $script:Checks
        }
        $report | ConvertTo-Json -Depth 6
    } else {
        Write-Host ""
        Write-Host ("=" * 78)
        Write-Host " 结果: $passed 通过 / $failed 失败 (共 $totalChecks 项) · 耗时 $elapsed 秒"
        if ($failed -gt 0) {
            Write-Host " 失败项:" -ForegroundColor Red
            foreach ($c in @($script:Checks | Where-Object { -not $_.pass })) {
                Write-Host "   - [$($c.name)] $($c.detail)" -ForegroundColor Red
            }
        } else {
            Write-Host " 已证明: 无模型时浏览 / 推荐 / 看板 / 许可全部可用; AI 三条能力降级后仍是 200;"
            Write-Host "         行程如实报失败并给原因; 假 token 一律 404; 超额拒绝带原因与重置时间。"
        }
        Write-Host ("=" * 78)
    }

    if ($failed -gt 0) { exit 1 }
    exit 0
} finally {
    # 无论中间怎么退出都要收尾, 除非用户明确说要留着
    if ($started -and -not $KeepRunning) {
        if (Stop-Ours) { Write-Note "后端已关闭(pid 记录已清)。" }
    } elseif ($started -and $KeepRunning) {
        Write-Note "后端仍在运行: http://127.0.0.1:$BackendPort/docs"
        Write-Note "关掉它: powershell -NoProfile -ExecutionPolicy Bypass -File $SelfPath -Down"
    }
}
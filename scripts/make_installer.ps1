<#
.SYNOPSIS
  打一个「简易安装包」: 拿到的人解压后双击 install.cmd 就能装上。

.DESCRIPTION
  与 scripts\ 里那几个脚本的分工: dev-up 面向改代码, damo-app 面向用, install-damo-app 只装
  快捷方式; 这个负责把上面这些**打成一个可以直接发给别人的 zip**。

  包里比仓库多一样: 预构建的 frontend\dist。所以拿包的人不需要 Node —— 只要有 Python 3.13
  与 PostgreSQL 16, 双击 install.cmd 就能装上桌面图标。

  装的是 git 跟踪的文件(外加 frontend\dist) —— 本地没进仓库的散件不会被带进去。
  包里比仓库少几样(都是本地状态、密钥或原始数据, 不该外发):
    .git / node_modules / .venv / .dev / __pycache__ / .pytest_cache / .cache /
    dist-installer / 景区名录 / backend\.env

.PARAMETER OutDir
  zip 写到哪。默认 dist-installer。给相对路径就相对仓库根。
.PARAMETER Version
  版本号, 默认读 frontend/package.json 的 version。
.PARAMETER Build
  打包前先 npm run build 重建前端产物。默认要求 frontend\dist 已存在 —— 宁可让你显式说一句
  「重建」, 也不要在打包时悄悄用一份过期的 dist, 那种包装上之后前端是旧的, 最难回头发现。
.PARAMETER KeepStage
  留着组装用的临时目录(排查「包里到底装了什么」时用)。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_installer.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/make_installer.ps1 -Build -Version 0.2.0
#>
[CmdletBinding()]
param(
    [string]$OutDir = "",
    [string]$Version = "",
    [switch]$Build,
    [switch]$KeepStage
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) {
    $OutDir = Join-Path $Root "dist-installer"
} elseif (-not [IO.Path]::IsPathRooted($OutDir)) {
    $OutDir = Join-Path $Root $OutDir
}

function Write-Info { param([string]$Msg) Write-Host "[make-installer] $Msg" }
function Write-Note { param([string]$Msg) Write-Host "[make-installer] $Msg" -ForegroundColor DarkGray }
function Write-Warn { param([string]$Msg) Write-Host "[make-installer] $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "[make-installer][error] $Msg" -ForegroundColor Red }

# ------------------------------------------------------------------ 1. 前置检查
$required = @(
    "backend\requirements.txt",
    "backend\.env.example",
    "db\schema.sql",
    "db\seed\seed.sql",
    "db\seed\attractions_cn.sql",
    "db\seed\images.sql",
    "scripts\damo-app.ps1",
    "scripts\install-damo-app.ps1",
    "installer\install.ps1",
    "install.cmd"
)
$missing = @($required | Where-Object { -not (Test-Path (Join-Path $Root $_)) })
if ($missing) {
    Write-Fail "缺文件, 这不是一个完整的仓库:"
    $missing | ForEach-Object { Write-Note "  - $_" }
    exit 1
}

$distIndex = Join-Path $Root "frontend\dist\index.html"
if ($Build) {
    # 显式找 npm.cmd: PATH 上有 npm.ps1, PowerShell 会优先命中它, 反而多绕一层。
    $npmExe = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npmExe) { $npmExe = (Get-Command npm -ErrorAction SilentlyContinue).Source }
    if (-not $npmExe) {
        Write-Fail "找不到 npm。装好 Node 后重开一个命令行窗口(PATH 才会刷新)。"
        exit 1
    }
    if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
        Write-Fail "frontend\node_modules 不在, 没法构建。先 cd frontend 跑一次 npm install。"
        exit 1
    }
    Write-Info "重建前端产物: npm run build"
    Push-Location (Join-Path $Root "frontend")
    try {
        & $npmExe run build
        if ($LASTEXITCODE -ne 0) { Write-Fail "npm run build 失败(exit $LASTEXITCODE)"; exit 1 }
    } finally { Pop-Location }
} elseif (-not (Test-Path $distIndex)) {
    Write-Fail "没有 frontend\dist\index.html。"
    Write-Note "先构建: cd frontend; npm install; npm run build —— 或加 -Build 让本脚本代跑。"
    exit 1
} else {
    # 产物比源头旧就停下来。vite 把源在构建期写死进产物, 一份过期的 dist 打包出去,
    # 表现是「界面是旧的」, 最难回头发现 —— 本轮就真踩了一次: 本机那份 dist 是 v4.2
    # 加景区封面之前建的, 少 1229 张图, 界面上是整片破图。
    $distTime = (Get-Item $distIndex).LastWriteTimeUtc
    $watch = @()
    foreach ($rel in @("frontend\src", "frontend\public")) { $watch += (Join-Path $Root $rel) }
    $watch += @(Get-ChildItem -LiteralPath (Join-Path $Root "frontend") -File | ForEach-Object { $_.FullName })
    $newestSrc = Get-ChildItem -LiteralPath $watch -Recurse -File -ErrorAction SilentlyContinue |
                 Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($newestSrc -and $newestSrc.LastWriteTimeUtc -gt $distTime) {
        $where = $newestSrc.FullName.Replace($Root + "\", "")
        Write-Fail "frontend\dist 比前端源码旧(比 $where 还旧)。"
        Write-Note "构建期写死的东西, 旧产物打出去就是旧界面; 加 -Build 重建, 或先 cd frontend && npm run build。"
        exit 1
    }
    Write-Note "用现有的 frontend\dist(它比 frontend\src 与 frontend\public 新)。"
}

# ------------------------------------------------------------------ 2. 版本
if (-not $Version) {
    # 显式 -Encoding UTF8: package.json 里 description 是中文且文件无 BOM,
    # PS 5.1 的 Get-Content 默认按 ANSI 读, 中文一乱码 JSON 就解析不了。
    $pkg = Get-Content (Join-Path $Root "frontend\package.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $Version = $pkg.version
}
if (-not $Version) { $Version = "0.0.0" }
Write-Info "版本: $Version"
# ------------------------------------------------------------------ 3. 组装暂存目录
# 拷什么不靠扫工作区, 而是问 git: 包里 = 仓库跟踪的文件 + frontend\dist(构建产物, 单独带上)。
# 扫工作区会把「本来就不该进仓库」的散件一起带上 —— 上次会话遗留的 .dev-q1.out 与探针 sql
# 就是这么混进包的。工作区里改过但没提交的内容照样会被取到(拷的是当前内容), 只是**新文件**
# 要先 git add 才会进包 —— 缺了会有下面的 mustHave 检查兜住。
Write-Info "组装暂存目录(git 跟踪清单 + frontend\dist)"
$tracked = @(& git -C $Root -c core.quotepath=false ls-files)
if ($LASTEXITCODE -ne 0 -or -not $tracked) {
    Write-Fail "git ls-files 拿不到文件清单。打包要在仓库里跑(这是维护者的事)。"
    exit 1
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stage = Join-Path $OutDir "stage"
if (Test-Path $stage) { [IO.Directory]::Delete($stage, $true) }
$zip = Join-Path $OutDir "have-a-trip-$Version.zip"
if (Test-Path $zip) { [IO.File]::Delete($zip) }

$copied = 0
$vanished = @()
foreach ($rel in $tracked) {
    $srcFile = Join-Path $Root ($rel -replace "/", "\")
    if (-not [IO.File]::Exists($srcFile)) { $vanished += $rel; continue }
    $dstFile = Join-Path $stage ($rel -replace "/", "\")
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($dstFile))
    [IO.File]::Copy($srcFile, $dstFile, $true)
    $copied++
}
# 索引里有、工作区没有的: 说一句就好。这正是「删了但没提交」的样子, 不是打包的错。
if ($vanished) {
    Write-Warn "有 $($vanished.Count) 个文件在 git 里但工作区没有(删过又没提交?):"
    $vanished | Select-Object -First 5 | ForEach-Object { Write-Note "  - $_" }
}

# frontend\dist 是构建产物, 被 .gitignore 挡在 git 之外 —— 这一份是包里唯一比仓库多的东西,
# 也是装的人不需要 Node 的原因。
$distSrc = Join-Path $Root "frontend\dist"
& robocopy $distSrc (Join-Path $stage "frontend\dist") /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Fail "复制 frontend\dist 失败(exit $LASTEXITCODE)"; exit 1 }
Write-Note "仓库文件 $copied 个, 外加 frontend\dist"
# 拷完先验一遍: 包里缺了这几样, 拿包的人双击下去只会得到一个说不清原因的失败。
$mustHave = @(
    "install.cmd",
    "installer\install.ps1",
    "backend\requirements.txt",
    "backend\.env.example",
    "frontend\dist\index.html",
    "db\schema.sql",
    "db\seed\seed.sql",
    "db\seed\attractions_cn.sql",
    "db\seed\images.sql",
    "scripts\damo-app.ps1",
    "scripts\install-damo-app.ps1"
)
$lost = @($mustHave | Where-Object { -not (Test-Path (Join-Path $stage $_)) })
if ($lost) {
    Write-Fail "暂存目录里缺文件:"
    $lost | ForEach-Object { Write-Note "  - $_" }
    Write-Note "清单是从 git 拿的 —— 新文件得先 git add 才进得来。"
    exit 1
}
# 包根放一张中文说明 —— 拿到 zip 的人第一眼要能看见「要装什么、双击什么、怎么卸载」。
# 带 BOM 写: 记事本靠 BOM 认 UTF-8, 否则中文是乱码。
$readmeLines = @(
    "Have-A-Trip 景点图谱  $Version",
    "",
    "安装",
    "  1. 先装好 Python 3.13 与 PostgreSQL 16(用官方安装包的默认选项就行)。",
    "  2. 双击本目录下的 install.cmd, 按提示走完。",
    "  3. 装完桌面上会出现 damo 图标, 双击即用。",
    "",
    "装着什么",
    "  %LOCALAPPDATA%\Programs\Have-A-Trip —— 用户级目录, 不需要管理员权限。",
    "  前端产物已随包带好, 所以**不需要装 Node**。",
    "",
    "卸载",
    "  开始菜单里的「卸载 damo」, 或在本目录跑: install.cmd -Uninstall",
    "",
    "出问题看这里",
    "  - 说找不到 Python / PostgreSQL: 刚装完要重开一个命令行窗口, 让 PATH 生效。",
    "  - 数据库连不上: 确认 PostgreSQL 服务在跑, 或用 -PgBin / -PgPort 指定实例。",
    "  - 只想先放文件、不碰数据库: install.cmd -SkipDatabase",
    "  - 看全部参数: powershell -NoProfile -ExecutionPolicy Bypass -File installer\install.ps1 -?",
    ""
)
[IO.File]::WriteAllText((Join-Path $stage "安装说明.txt"), (($readmeLines -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($true)))
# ------------------------------------------------------------------ 4. 打 zip
# 逐条自己写 zip, 不用 Compress-Archive: 它两处不合用 —— 通配符 -Path 看不见隐藏项
# (.gitignore / .env.example 会漏), 而条目名在 .NET Framework 下会写成反斜杠,
# 拿到非 Windows 上解压就是一堆带怪名字的文件。
Write-Info "压缩"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$stagePrefixLen = $stage.TrimEnd("\").Length + 1
$packed = 0
$zipStream = [IO.Compression.ZipFile]::Open($zip, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($f in Get-ChildItem -LiteralPath $stage -Recurse -File -Force) {
        $rel = $f.FullName.Substring($stagePrefixLen).Replace("\", "/")
        [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zipStream, $f.FullName, $rel, [IO.Compression.CompressionLevel]::Optimal)
        $packed++
    }
} finally {
    $zipStream.Dispose()
}
Write-Note "入了 $packed 个文件"

# ------------------------------------------------------------------ 5. 自己验包
# 别只信「拷的时候排除了」—— 直接从 zip 的目录表上读, 看该在的在不在、不该在的有没有。
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zip)
try {
    $entries = @($archive.Entries | ForEach-Object { $_.FullName })
} finally {
    $archive.Dispose()
}

$needEntries = @(
    "install.cmd",
    "installer/install.ps1",
    "frontend/dist/index.html",
    "db/seed/attractions_cn.sql"
)
$absent = @($needEntries | Where-Object { $entries -notcontains $_ })
# 一样都不许进包: 仓库本身、dev 运行时产物、密钥、本地状态、带第三方许可的原始下载件。
$forbidden = "^(\.git/|\.dev|景区名录/|dist-installer/)" +
             "|(^|/)(node_modules|\.venv|__pycache__|\.pytest_cache|\.cache)/" +
             "|(^|/)\.env$"
$leaked = @($entries | Where-Object { $_ -match $forbidden })

if ($absent -or $leaked) {
    if ($absent) {
        Write-Fail "包里缺文件:"
        $absent | ForEach-Object { Write-Note "  - $_" }
    }
    if ($leaked) {
        Write-Fail "包里有不该带的东西:"
        $leaked | Select-Object -First 10 | ForEach-Object { Write-Note "  - $_" }
    }
    [IO.File]::Delete($zip)
    Write-Note "已删掉这个包 —— 发出去才是麻烦。"
    exit 1
}

# ------------------------------------------------------------------ 6. 报告
$zipItem = Get-Item $zip
$sha = (Get-FileHash $zip -Algorithm SHA256).Hash
Write-Info "打包完成"
Write-Host "  文件  : $($zipItem.FullName)"
Write-Host ("  大小  : {0:N1} MB, {1} 个文件" -f ($zipItem.Length / 1MB), $entries.Count)
Write-Host "  SHA256: $sha"
Write-Host ""
Write-Note "包内已含 frontend\dist, 装的人不需要 Node; 要有 Python 3.13 与 PostgreSQL 16。"
Write-Note "把 zip 发出去, 对方解压后双击 install.cmd。"

if ($KeepStage) {
    Write-Note "-KeepStage: 暂存目录留着了 —— $stage"
} else {
    [IO.Directory]::Delete($stage, $true)
}
exit 0
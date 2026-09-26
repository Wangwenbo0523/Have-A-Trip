<#
.SYNOPSIS
  把 Have-A-Trip 装到本机(当前用户), 装完双击桌面上的 damo 就能用。

.DESCRIPTION
  装的是「用」的形态(scripts\damo-app.ps1 那条路: 单进程 + 独立窗口), 不是改代码用的
  dev server。四件事:

    1. 把文件复制到 %LOCALAPPDATA%\Programs\Have-A-Trip
    2. 建 backend\.venv 并装后端依赖(backend\requirements.txt)
    3. 连 PostgreSQL: 建库 + 灌 schema 与三个种子文件(幂等, 可重复跑)
    4. 建桌面与开始菜单快捷方式, 外加一个卸载入口

  前端产物 frontend\dist 是**随包带好的**, 所以装的时候不需要 Node —— 安装方只要有
  Python 3.13 与 PostgreSQL 16 就行。这两样本脚本不代装: 缺哪个就停下来告诉你去哪装。

  可重复执行: 重装、补装、换参数重跑都可以。已经存在的 backend\.env 一律不动。

.PARAMETER TargetDir
  装到哪。默认 %LOCALAPPDATA%\Programs\Have-A-Trip —— 用户级目录, 不需要管理员。

.PARAMETER PythonExe
  指定用哪个 Python。不给就依次找 PATH 上的 python / python3 / py -3.13。
  要求 3.13(本项目验证过的版本); 显式指定别的版本会继续, 但会明确警告。

.PARAMETER PgBin
  PostgreSQL 的 bin 目录(含 psql.exe / createdb.exe)。不给就依次找 PATH、
  Program Files\PostgreSQL\*\bin、C:\pgtemp\pginstall\bin。

.PARAMETER PgHost
  数据库主机, 默认 127.0.0.1。
.PARAMETER PgPort
  数据库端口, 默认 5432。
.PARAMETER PgUser
  数据库用户, 默认 postgres。
.PARAMETER PgPassword
  数据库口令, 默认 postgres。只写进 backend\.env(已在 .gitignore 里), 不入库。
.PARAMETER Database
  库名, 默认 attraction_atlas。

.PARAMETER SkipDeps
  不建 venv、不装后端依赖(只复制文件与建快捷方式)。
.PARAMETER SkipDatabase
  不碰数据库(只复制文件与装依赖)。数据库还没就绪时可以用它先装一半。
.PARAMETER SkipShortcuts
  不建快捷方式。
.PARAMETER Uninstall
  卸载: 删快捷方式与安装目录。
.PARAMETER NoPause
  跑完不等人按回车(给脚本 / CI 用; 双击 install.cmd 时不要加)。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File installer\install.ps1

.EXAMPLE
  # 便携 PostgreSQL 实例
  powershell -NoProfile -ExecutionPolicy Bypass -File installer\install.ps1 -PgBin C:\pgtemp\pginstall\bin -PgPort 55432

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File installer\install.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$TargetDir = "",
    [string]$PythonExe = "",
    [string]$PgBin = "",
    [string]$PgHost = "127.0.0.1",
    [int]$PgPort = 5432,
    [string]$PgUser = "postgres",
    [string]$PgPassword = "postgres",
    [string]$Database = "attraction_atlas",
    [switch]$SkipDeps,
    [switch]$SkipDatabase,
    [switch]$SkipShortcuts,
    [switch]$Uninstall,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

# 中文控制台(代码页 936)下 pip 按 GBK 解码 UTF-8 的 requirements 会报 UnicodeDecodeError。
# 这一条与 README 的装依赖说明是同一件事, 所以这里也设上。
$env:PYTHONUTF8 = "1"

$SourceDir = Split-Path -Parent $PSScriptRoot
if (-not $TargetDir) { $TargetDir = Join-Path $env:LOCALAPPDATA "Programs\Have-A-Trip" }

function Write-Info { param([string]$Msg) Write-Host "[damo-install] $Msg" }
function Write-Note { param([string]$Msg) Write-Host "[damo-install] $Msg" -ForegroundColor DarkGray }
function Write-Warn { param([string]$Msg) Write-Host "[damo-install][warn] $Msg" -ForegroundColor Yellow }
function Write-Fail { param([string]$Msg) Write-Host "[damo-install][error] $Msg" -ForegroundColor Red }

function Exit-With {
    param([int]$Code)
    # 双击 install.cmd 时窗口是脚本自己开的, 跑完立刻关掉的话用户看不到结果。
    # 只在真有控制台时等人按回车, 免得拖住脚本调用方。
    if (-not $NoPause -and $Host.Name -eq "ConsoleHost") {
        Write-Host ""
        Write-Host "按回车关闭这个窗口。" -ForegroundColor DarkGray
        [void](Read-Host)
    }
    exit $Code
}

function Invoke-Exe {
    # 跑一个外部程序: 输出照旧显示在控制台上, 但**不进管道** —— 只把退出码返回给调用方。
    # 外部程序的非零退出码不会抛异常, 所以必须显式看。
    #
    # 别写回裸的 `& $Exe @Arguments`: 那样子进程写到 stdout 的每一行都会变成这个函数的返回值,
    # 于是 `$rc = Invoke-Exe ...` 拿到的是「一整屏输出 + 退出码」的数组, 而 `$rc -ne 0` 恒真。
    # 2026-09-26 用真打出来的安装包实测到: pip 明明装成功了(输出末尾就是 0), 脚本却报
    # 「pip 装依赖失败」并中止, 后面建库、写 .env、装快捷方式全没跑。robocopy / psql /
    # python -m venv 之所以一直没露馅, 只是因为它们被叫起来时几乎不往 stdout 写东西 ——
    # 也就是说这条路一直是坏的, 只是没人在一台没有 backend\.venv 的机器上走到过。
    param([string]$Exe, [string[]]$Arguments)
    # 两个流一起转发到控制台: pip 的告警走 stderr, 分开转会在窗口里和正常输出乱序。
    # 调用期间把 $ErrorActionPreference 降到 Continue, 是因为外部程序往 stderr 写一行、又用
    # `2>&1` 合流进来时, 会被本脚本顶上那句 Stop 升级成终止错误(同一天在 psql 探测那条路上
    # 实测到一次: 连不上库时本该打出来的提示被一句 PowerShell 异常整段盖掉)。真正的失败
    # 判定只认退出码, 外部程序的一句告警不该把安装中断在半路。
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe @Arguments 2>&1 | Out-Host
    } finally {
        $ErrorActionPreference = $previous
    }
    return $LASTEXITCODE
}
# ------------------------------------------------------------------ 卸载
if ($Uninstall) {
    Write-Info "卸载: $TargetDir"
    $uninstaller = Join-Path $TargetDir "scripts\install-damo-app.ps1"
    if (Test-Path $uninstaller) {
        & $uninstaller -Uninstall
    } elseif (Test-Path $TargetDir) {
        Write-Warn "没找到 $uninstaller, 桌面与开始菜单的 damo 快捷方式要手动删。"
    }
    $link = Join-Path (Join-Path ([Environment]::GetFolderPath("Programs")) "damo") "卸载 damo.lnk"
    if (Test-Path $link) { [IO.File]::Delete($link) }
    if (-not (Test-Path $TargetDir)) {
        Write-Info "安装目录本来就不在, 完事。"
        Exit-With 0
    }
    # 删自己所在的目录: 直接删会被正在跑的脚本文件挡住, 所以把一个影子脚本丢到 %TEMP%,
    # 由它等我们退出之后再动手。影子脚本用**带 BOM 的 UTF-8**存 —— 用户名可能是中文
    # (如 C:\Users\雷神), 无 BOM 的 UTF-8 会被 PowerShell 按 ANSI 读, 路径就烂了。
    $shadow = Join-Path $env:TEMP ("damo-uninstall-" + [guid]::NewGuid().ToString("N") + ".ps1")
    $code = @"
Start-Sleep -Seconds 2
[IO.Directory]::Delete('$TargetDir', `$true)
[IO.File]::Delete(`$PSCommandPath)
"@
    [IO.File]::WriteAllText($shadow, $code, (New-Object Text.UTF8Encoding($true)))
    Start-Process -FilePath "powershell" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $shadow
    ) -WindowStyle Hidden
    Write-Info "安装目录正在后台删除(这个窗口关闭后几秒内完成)。"
    Write-Info "库 $Database 与 backend\.env 都留着 —— 要一并清掉请手动 drop 掉那个库。"
    Exit-With 0
}

# ------------------------------------------------------------------ 前置检查
if (-not (Test-Path (Join-Path $SourceDir "backend\requirements.txt"))) {
    Write-Fail "这个目录不像安装包: 缺 backend\requirements.txt"
    Write-Note "安装包解压后应是一个 have-a-trip 文件夹, installer\ 与 backend\ 都在它下面。"
    Exit-With 1
}
if (-not (Test-Path (Join-Path $SourceDir "frontend\dist\index.html"))) {
    Write-Fail "缺 frontend\dist\index.html —— 安装包应该带着它(装的时候不需要 Node)。"
    Write-Note "若是从源码目录直接装: 先 cd frontend 跑 npm install && npm run build。"
    Exit-With 1
}

function Resolve-Python {
    param([string]$Explicit)
    if ($Explicit) {
        if (-not (Test-Path $Explicit)) { Write-Fail "指定的 Python 不存在: $Explicit"; return $null }
        return $Explicit
    }
    foreach ($name in @("python", "python3")) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    # py 启动器: 问它 3.13 装在哪
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $out = & py -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -First 1).Trim() }
    }
    return $null
}

function Resolve-Psql {
    param([string]$Bin)
    if ($Bin) {
        $explicit = Join-Path $Bin "psql.exe"
        if (Test-Path $explicit) { return $explicit }
        Write-Fail "PgBin 下没有 psql.exe: $Bin"
        return $null
    }
    $onPath = Get-Command psql -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    foreach ($pattern in @("C:\Program Files\PostgreSQL\*\bin\psql.exe", "C:\pgtemp\pginstall\bin\psql.exe")) {
        $hit = Get-ChildItem $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { return $hit.FullName }
    }
    return $null
}
$python = $null
if (-not $SkipDeps) {
    $python = Resolve-Python -Explicit $PythonExe
    if (-not $python) {
        Write-Fail "找不到 Python。这个安装包不代装 Python, 请先装 Python 3.13。"
        Write-Note "下载: https://www.python.org/downloads/  (装的时候勾上 Add python.exe to PATH)"
        Write-Note "装好后再双击一次 install.cmd 即可; 也可以先只放文件: install.cmd -SkipDeps"
        Exit-With 1
    }
    $version = ((& $python -c "import sys; print('%d.%d' % sys.version_info[:2])") -join "").Trim()
    Write-Info "Python: $python ($version)"
    if ($version -ne "3.13") {
        if ($PythonExe) {
            Write-Warn "Python $version 不是本项目验证过的 3.13, 继续装, 但出问题先怀疑这里。"
        } else {
            Write-Fail "需要 Python 3.13, 当前是 $version。"
            Write-Note "装一个 3.13 再重跑; 或指定解释器: install.cmd -PythonExe C:\Python313\python.exe"
            Exit-With 1
        }
    }
}

$psql = $null
if (-not $SkipDatabase) {
    $psql = Resolve-Psql -Bin $PgBin
    if (-not $psql) {
        Write-Fail "找不到 psql。这个安装包不代装 PostgreSQL, 请先装 PostgreSQL 16。"
        Write-Note "下载: https://www.postgresql.org/download/windows/"
        Write-Note "便携实例可以用 -PgBin 指过去, 例如:"
        Write-Note "  install.cmd -PgBin C:\pgtemp\pginstall\bin -PgPort 55432"
        Write-Note "库还没就绪、想先把程序放上去的话: install.cmd -SkipDatabase"
        Exit-With 1
    }
    Write-Info "psql: $psql"
}

# ------------------------------------------------------------------ 1. 复制文件
Write-Info "复制文件到 $TargetDir"
if (-not (Test-Path $TargetDir)) { $null = New-Item -ItemType Directory -Path $TargetDir -Force }
# 排除表里那几样都是本地状态或密钥, 不该进安装目录; /E 连空目录一起拷。
# frontend\dist 不排除 —— 它就是让安装方不用装 Node 的那份东西。
$excludeDirs = @(".git", "node_modules", ".venv", ".dev", "__pycache__", ".pytest_cache", "dist-installer", "景区名录")
$excludeFiles = @(".env", "*.pyc")
$rc = Invoke-Exe "robocopy" (@(
    $SourceDir, $TargetDir, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD"
) + $excludeDirs + @("/XF") + $excludeFiles + @("/R:1", "/W:1"))
if ($rc -ge 8) { Write-Fail "复制文件失败(robocopy 退出码 $rc)"; Exit-With 1 }
Write-Info "文件已就位。"

# ------------------------------------------------------------------ 2. 后端依赖
$backendDir = Join-Path $TargetDir "backend"
$venvPy = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not $SkipDeps) {
    if (Test-Path $venvPy) {
        Write-Info "已有 backend\.venv, 直接复用。"
    } else {
        Write-Info "建虚拟环境 backend\.venv"
        $rc = Invoke-Exe $python @("-m", "venv", (Join-Path $backendDir ".venv"))
        if ($rc -ne 0 -or -not (Test-Path $venvPy)) { Write-Fail "建 venv 失败"; Exit-With 1 }
    }
    Write-Info "装后端依赖(要联网, 第一次大概一两分钟)"
    $rc = Invoke-Exe $venvPy @(
        "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
        "-r", (Join-Path $backendDir "requirements.txt")
    )
    if ($rc -ne 0) {
        Write-Fail "pip 装依赖失败(退出码 $rc)。"
        Write-Note "网络不通或代理拦了 pypi 都会这样; 修好后重跑 install.cmd 会接着装。"
        Exit-With 1
    }
    Write-Info "后端依赖装好了。"
} else {
    Write-Note "-SkipDeps: 跳过 venv 与后端依赖。"
}
# ------------------------------------------------------------------ 3. 数据库
$databaseUrl = "postgresql+psycopg://$PgUser@$($PgHost):$PgPort/$Database"
if ($PgPassword) { $databaseUrl = "postgresql+psycopg://$($PgUser):$PgPassword@$($PgHost):$PgPort/$Database" }

if (-not $SkipDatabase) {
    $env:PGPASSWORD = $PgPassword
    $binDir = Split-Path -Parent $psql

    Write-Info "连库 $($PgHost):$PgPort (用户 $PgUser)"
    # 探测连库走 Invoke-Exe, 不写回 `& $psql ... 2>&1`。原因是实测出来的: psql 连不上时
    # 往 stderr 写一行, 那句 `2>&1` 把 stderr 合进成功流之后, 就被脚本顶上那句
    # $ErrorActionPreference='Stop' 升级成终止错误 —— 于是下面专门写给人看的两行提示
    # (「服务在跑吗 / 端口对不对 / 口令对不对」)一个字都打不出来, 用户只看到一段红色
    # 堆栈, 而「数据库没起」恰恰是这条路上最常发生的一种失败。
    # Invoke-Exe 里已经把两个流都转发到控制台并把失败还原成退出码, 所以这里能好好报错。
    $probeRc = Invoke-Exe $psql @("-h", $PgHost, "-p", "$PgPort", "-U", $PgUser, "-d", "postgres", "-tAc", "select 1")
    if ($probeRc -ne 0) {
        Write-Fail "连不上数据库(psql 退出码 $probeRc; 具体原因见上面那行 psql 输出)。"
        Write-Note "确认 PostgreSQL 服务在跑、端口对、口令对; 便携实例要指 -PgBin / -PgPort。"
        Exit-With 1
    }

    $exists = & $psql -h $PgHost -p $PgPort -U $PgUser -d postgres -tAc "select 1 from pg_database where datname = '$Database'"
    if ($exists -ne "1") {
        $createdb = Join-Path $binDir "createdb.exe"
        if (-not (Test-Path $createdb)) { Write-Fail "库 $Database 不存在, 且同目录下没有 createdb.exe。"; Exit-With 1 }
        Write-Info "建库 $Database"
        $rc = Invoke-Exe $createdb @("-h", $PgHost, "-p", "$PgPort", "-U", $PgUser, "-E", "UTF8", $Database)
        if ($rc -ne 0) { Write-Fail "createdb 失败"; Exit-With 1 }
    } else {
        Write-Info "库 $Database 已存在, 直接复用。"
    }

    # 执行顺序不能换: images.sql 按 slug 关联景点, 两个景点文件必须先跑完。
    foreach ($rel in @("db\schema.sql", "db\seed\seed.sql", "db\seed\attractions_cn.sql", "db\seed\images.sql")) {
        $file = Join-Path $TargetDir $rel
        if (-not (Test-Path $file)) { Write-Fail "缺少 $rel"; Exit-With 1 }
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $rc = Invoke-Exe $psql @(
            "-h", $PgHost, "-p", "$PgPort", "-U", $PgUser, "-d", $Database,
            "-v", "ON_ERROR_STOP=1", "-q", "-c", "set client_min_messages=warning", "-f", $file
        )
        if ($rc -ne 0) { Write-Fail "$rel 执行失败(psql 退出码 $rc)"; Exit-With 1 }
        $sw.Stop()
        Write-Info "$rel 已应用($([int]$sw.Elapsed.TotalSeconds) 秒)"
    }

    $count = & $psql -h $PgHost -p $PgPort -U $PgUser -d $Database -tAc "select count(*) from attraction"
    Write-Info "库内景点数: $count"
    [Environment]::SetEnvironmentVariable("PGPASSWORD", $null)
} else {
    Write-Note "-SkipDatabase: 没碰数据库。"
}

# ------------------------------------------------------------------ 4. .env
$envFile = Join-Path $backendDir ".env"
if (Test-Path $envFile) {
    Write-Info "backend\.env 已存在, 不动它。"
    Write-Note "要改库地址请自己编辑: $envFile"
} else {
    $example = Join-Path $backendDir ".env.example"
    if (Test-Path $example) {
        $text = [IO.File]::ReadAllText($example)
        $text = [regex]::Replace($text, "(?m)^DATABASE_URL=.*$", "DATABASE_URL=$databaseUrl")
        # 无 BOM 的 UTF-8: 带着 BOM 会让第一个键名多出不可见字符, 配置读取会认不出它
        [IO.File]::WriteAllText($envFile, $text, (New-Object Text.UTF8Encoding($false)))
        Write-Info "已生成 backend\.env(DATABASE_URL 指向 $Database)"
    } else {
        Write-Warn "没有 .env.example, 跳过生成 .env。"
    }
}

# ------------------------------------------------------------------ 5. 快捷方式
if (-not $SkipShortcuts) {
    $shortcutter = Join-Path $TargetDir "scripts\install-damo-app.ps1"
    if (Test-Path $shortcutter) {
        & $shortcutter
    } else {
        Write-Warn "没找到 scripts\install-damo-app.ps1, 跳过建快捷方式。"
    }
    # 再给一个卸载入口。与 damo 放同一层开始菜单目录, 找起来顺手。
    try {
        $menuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "damo"
        if (-not (Test-Path $menuDir)) { $null = New-Item -ItemType Directory -Path $menuDir -Force }
        $link = Join-Path $menuDir "卸载 damo.lnk"
        $icon = Join-Path $TargetDir "frontend\public\favicon.ico"
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($link)
        $shortcut.TargetPath = $env:ComSpec
        $shortcut.Arguments = '/c "' + (Join-Path $TargetDir "install.cmd") + '" -Uninstall'
        $shortcut.WorkingDirectory = $TargetDir
        $shortcut.Description = "卸载 Have-A-Trip(删程序文件与快捷方式; 数据库不动)"
        if (Test-Path $icon) { $shortcut.IconLocation = $icon }
        $shortcut.Save()
        Write-Info "已创建卸载入口: $link"
    } catch {
        Write-Warn "建卸载快捷方式失败: $_"
    }
} else {
    Write-Note "-SkipShortcuts: 没建快捷方式。"
}

# ------------------------------------------------------------------ 收尾
Write-Host ""
Write-Info "装好了。双击桌面上的 damo 就能用(等价物: $TargetDir\damo.cmd)。"
if (-not $SkipDatabase) {
    Write-Note "AI 是可选的: 想开就把 backend\.env 里的 LLM_PROVIDER 按注释配好(本地 ollama 零成本)。"
    Write-Note "不配也能用, 一句话检索会退回关键词 —— 是降级不是报错。"
}
Write-Note "卸载: 开始菜单「卸载 damo」, 或在安装目录里跑 install.cmd -Uninstall。"
Exit-With 0
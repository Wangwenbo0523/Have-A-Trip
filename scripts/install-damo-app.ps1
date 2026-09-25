<#
.SYNOPSIS
  把 damo 装到桌面与开始菜单(快捷方式), 图标用仓库里那个 favicon。

.DESCRIPTION
  只写两个 .lnk 到**当前用户**的桌面与开始菜单: 不需要管理员, 不碰系统目录, 不改注册表。
  快捷方式指向仓库里的 damo.cmd —— 仓库挪了位置就重跑一次(或先 -Uninstall)。

.PARAMETER Uninstall
  删掉这两个快捷方式。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-damo-app.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-damo-app.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$Root    = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $Root "damo.cmd"
$Icon    = Join-Path $Root "frontend\public\favicon.ico"
$Name    = "damo"

function Write-Info { param([string]$Msg) Write-Host "[damo-install] $Msg" }

if (-not (Test-Path $Launcher)) {
    Write-Host "[damo-install][error] 没找到 $Launcher" -ForegroundColor Red
    exit 1
}

$desktop = [Environment]::GetFolderPath("Desktop")
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) $Name
$targets = @(
    (Join-Path $desktop "$Name.lnk"),
    (Join-Path $startMenu "$Name.lnk")
)

if ($Uninstall) {
    foreach ($link in $targets) {
        if (Test-Path $link) { Remove-Item $link -Force; Write-Info "已删除 $link" }
    }
    if (Test-Path $startMenu) { Remove-Item $startMenu -Force -Recurse }
    Write-Info "卸载完成。"
    exit 0
}

$shell = New-Object -ComObject WScript.Shell
foreach ($link in $targets) {
    $dir = Split-Path -Parent $link
    if (-not (Test-Path $dir)) { $null = New-Item -ItemType Directory -Path $dir }
    $shortcut = $shell.CreateShortcut($link)
    # 直接用 cmd.exe 跑 damo.cmd: 双击的等价物, 不依赖 .cmd 的文件关联
    $shortcut.TargetPath = $env:ComSpec
    $shortcut.Arguments = '/c "' + $Launcher + '"'
    $shortcut.WorkingDirectory = $Root
    $shortcut.Description = "damo - 出去走走"
    if (Test-Path $Icon) { $shortcut.IconLocation = $Icon }
    $shortcut.Save()
    Write-Info "已创建 $link"
}

Write-Info "装好了: 桌面与开始菜单里各有一个 damo。双击即可。"
Write-Info "卸载: 加 -Uninstall 再跑一次。"

<#
.SYNOPSIS
    按 scripts/bases.lock.json 的钉版信息, 把上游基底拉到 .cache/upstream/ 下用于对比。

.DESCRIPTION
    frontend/ 已经被我们改过, 所以不要整目录覆盖上游。
    正确用法: 跑本脚本把上游拉到 .cache/upstream/travel-guide-upstream,
    然后用 git diff 或对比工具挑需要的改动合进 frontend/。

    .cache/ 已在 .gitignore 中, 上游副本不会进仓库。
#>
$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'

$root = Split-Path -Parent $PSScriptRoot          # 项目根目录
$lockPath = Join-Path $PSScriptRoot 'bases.lock.json'
if (-not (Test-Path $lockPath)) { throw "找不到 $lockPath" }

$lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
$fe = $lock.bases.frontend

# 上游缓存放在项目内, 保证项目整体可搬移
$outBase = Join-Path $root '.cache\upstream'
New-Item -ItemType Directory -Force -Path $outBase | Out-Null

Write-Output "上游    : $($fe.upstream)"
Write-Output "钉定    : $($fe.commit)  ($($fe.commitDate))"
Write-Output "许可证  : $($fe.license)"
Write-Output "落地点  : $outBase\travel-guide-upstream"
Write-Output ""

$dest = Join-Path $outBase 'travel-guide-upstream'
if (Test-Path (Join-Path $dest '.git')) {
    Write-Output "已存在, 直接 fetch 钉定 commit ..."
    git -C $dest fetch --depth 1 origin $fe.commit 2>&1 | Select-Object -Last 2
    git -C $dest checkout --detach $fe.commit 2>&1 | Select-Object -Last 1
} else {
    Write-Output "克隆(仅文件树, 省流量) ..."
    git clone --filter=blob:none --no-checkout $fe.upstream $dest 2>&1 | Select-Object -Last 1
    git -C $dest fetch --depth 1 origin $fe.commit 2>&1 | Select-Object -Last 1
    git -C $dest checkout --detach $fe.commit 2>&1 | Select-Object -Last 1
}

$actual = (git -C $dest rev-parse HEAD 2>$null)
if ($actual) { $actual = $actual.Trim() }
Write-Output ""
Write-Output "实际 HEAD: $actual"
if ($actual -ne $fe.commit) {
    Write-Output "!! 与 bases.lock.json 不一致, 请确认上游 commit 是否仍可达"
} else {
    Write-Output "OK: 与钉定 commit 一致"
}
Write-Output ""
Write-Output "下一步: 对比上游改动, 只把需要的部分合进 frontend/"
Write-Output "  git -C `"$dest`" log -1 --stat"

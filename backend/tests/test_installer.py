"""安装包的守线: 把「用真打出来的包装一遍才发现」的两个坑变成可执行的断言。

2026-09-26 用 `scripts\\make_installer.ps1` 真打了一份 zip, 解压后按收包人的流程跑
`install.cmd`, 装到一半就停了 —— pip 明明装成功(输出末尾就是 0), 脚本却报「pip 装依赖失败」。
查下来是两个各自独立的错:

- `installer\\install.ps1` 的 `Invoke-Exe` 里写的是裸的 `& $Exe @Arguments`。PowerShell 会把
  子进程写到 stdout 的每一行都当成这个函数的**返回值**, 于是 `$rc = Invoke-Exe ...` 拿到的是
  「一整屏输出 + 退出码」的数组, `$rc -ne 0` 恒为真。robocopy / psql / `python -m venv` 一直
  没露馅, 只是因为它们被叫起来时几乎不往 stdout 写东西 —— 这条路一直是坏的, 只是没人在一台
  没有 `backend\\.venv` 的机器上走到过。
- `install.cmd` 的失败分支把 `(exit code %RC%)` 连同括号一起 echo, 而它本身就在 `if (...)` 的
  括号块里 —— 那个 `)` 提前闭合了块, cmd 报 ". was unexpected at this time."。于是用户看到的
  不是「装失败了」, 而是一句莫名其妙的语法错, 真正的原因被盖掉。

与 `test_launcher.py` 的分工: 那个管「本机应用」那条路(scripts\\damo-app.ps1 + damo.cmd),
这个管「发给别人的包」那条路(installer\\ + install.cmd)。
"""
from __future__ import annotations

import pathlib
import re
import shutil
import socket
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "installer"
INSTALL_PS1 = INSTALLER / "install.ps1"
INSTALL_CMD = ROOT / "install.cmd"
BOM = b"\xef\xbb\xbf"

# PowerShell 里那段「只把 Invoke-Exe 抽出来跑」的脚本。__PS1__ 由下面替换成实际路径,
# 不用 str.format —— 里面既有正则的 {} 又有 PowerShell 的 {0}, 两层花括号很容易写错。
PS_HARNESS = r"""
$ErrorActionPreference = 'Stop'
$text = [IO.File]::ReadAllText('__PS1__', [Text.UTF8Encoding]::new($true))
$m = [regex]::Match($text, '(?ms)^function Invoke-Exe \{.*?\r?\n\}')
if (-not $m.Success) { Write-Output 'NO_MATCH'; exit 2 }
Invoke-Expression $m.Value
# 1) 话多的子进程(模拟 pip): 输出必须不进返回值
$chatty = Invoke-Exe 'cmd' @('/c', 'echo line one & echo line two & exit /b 0')
# 2) 往 stderr 写一行告警、自身成功(模拟 pip 的 warning): 不能把安装打断
$noisy = Invoke-Exe 'cmd' @('/c', 'echo a warning 1>&2 & exit /b 0')
# 3) 真的失败: 退出码要原样传出来
$failing = Invoke-Exe 'cmd' @('/c', 'exit /b 7')
$ok = ($chatty -is [int]) -and ($chatty -eq 0) -and
      ($noisy -is [int]) -and ($noisy -eq 0) -and
      ($failing -is [int]) -and ($failing -eq 7)
Write-Output ('RESULT chatty={0}/{1} noisy={2}/{3} failing={4}/{5} ok={6}' -f @(
    $chatty.GetType().Name, $chatty, $noisy.GetType().Name, $noisy,
    $failing.GetType().Name, $failing, $ok
))
"""


def _windows_powershell_or_skip() -> str:
    """拿到本机的 PowerShell; 不在 Windows 上就直接跳过。

    这里按**平台**跳, 不按「有没有 PowerShell」跳。第一次写成「CI 的 ubuntu 上没有 PowerShell,
    自然会跳过」—— 那是错的: 那份运行器自带 PowerShell 7(2026-09-26 查到镜像里写着 7.6.6),
    于是下面两条真跑了起来, 而它们要的 cmd.exe 与 Windows 路径都不在, 一句
    "is not recognized" 直接把用例打成红的。判据要按能力挑: 能不能装这个包, 等价于是不是
    Windows, 而不是是否存在一个叫 powershell 的命令。
    """
    if sys.platform != "win32":
        import pytest

        pytest.skip("安装包只面向 Windows: 这两条要 cmd.exe 与 Windows 路径, 在 CI 的 ubuntu 上跳过")
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        import pytest

        pytest.skip("这台机器上没有 PowerShell, 跑不了这段")
    return powershell


def test_installer_powershell_scripts_start_with_a_bom():
    """没 BOM 的 .ps1 在中文 Windows 上会被按 GBK 读, 中文注释直接变乱码甚至语法错。

    `test_launcher.py` 里那条只扫 `scripts\\*.ps1`, 安装目录下的这份漏在外面 —— 补上。
    """
    scripts = sorted(INSTALLER.glob("*.ps1"))
    assert scripts, "installer 目录下一个 .ps1 都没有, 这个用例就没意义了"
    missing = [p.name for p in scripts if not p.read_bytes().startswith(BOM)]
    assert missing == [], f"这些 .ps1 缺 UTF-8 BOM: {missing}"


def test_the_double_click_entry_point_is_ascii_only():
    """cmd.exe 按 OEM 码页读文件, 中文写进 .cmd 只会变成乱码。"""
    assert INSTALL_CMD.is_file(), "缺 install.cmd(安装包的双击入口)"
    bad = [i for i, byte in enumerate(INSTALL_CMD.read_bytes()) if byte > 127]
    assert bad == [], f"install.cmd 里有非 ASCII 字节: {bad[:5]}"


def test_no_echo_line_in_the_cmd_entry_point_contains_a_closing_paren():
    """cmd 的 `if ... ( ... )` 块里出现裸的 `)` 会提前闭合块, 报 ". was unexpected at this time."

    这条就是上面那个坑的形状: 报错发生在**失败分支**里, 把真正的失败原因盖掉了。
    括号要显示就转义成 `^)` 或干脆别写。
    """
    offenders = [
        line for line in INSTALL_CMD.read_text(encoding="ascii").splitlines()
        if line.strip().lower().startswith("echo") and ")" in line
    ]
    assert offenders == [], f"install.cmd 的 echo 行里有未转义的右括号: {offenders}"


def test_invoke_exe_does_not_leak_the_child_output_into_its_return_value():
    """`& $Exe @Arguments` 的每一行输出都会成为返回值 —— 必须显式转发掉, 只 return 退出码。"""
    text = INSTALL_PS1.read_text(encoding="utf-8-sig")
    match = re.search(r"(?ms)^function Invoke-Exe \{.*?\r?\n\}", text)
    assert match, "找不到 Invoke-Exe, 用例该跟着脚本改"
    body = match.group(0)
    bare = [line.strip() for line in body.splitlines() if line.strip() in ("& $Exe @Arguments",)]
    assert bare == [], "子进程的输出会漏进返回值: 要 2>&1 | Out-Host 转发, 别让它进管道"
    assert "| Out-Host" in body, "子进程输出必须转发到控制台(看得见但不进管道)"
    assert "return $LASTEXITCODE" in body


def test_invoke_exe_returns_a_scalar_exit_code_even_for_a_chatty_child():
    """真的跑一遍: 话多的子进程、往 stderr 写告警的子进程、真失败的子进程, 三种都要拿到 int。

    只在 Windows 上跑: CI 那份 ubuntu 运行器其实自带 PowerShell, 但它没有 cmd.exe —— 第一次
    推送时这句 harness 一开口就抛终止错误(NativeCommandError), CI 直接红了。文本级那条(上一条)
    在所有平台把关, 这条在能真装这个包的 Windows 上把关。
    """
    powershell = _windows_powershell_or_skip()
    harness = PS_HARNESS.replace("__PS1__", str(INSTALL_PS1))
    proc = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", harness],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "ok=True" in out, f"Invoke-Exe 的返回值不对(要全是 int): {out.strip()}"

def test_the_database_probe_does_not_send_a_bare_redirected_psql_call():
    """探测连库不能写回 `$probe = & $psql ... 2>&1`: stderr 一合流就被 Stop 升级成终止错误。"""
    text = INSTALL_PS1.read_text(encoding="utf-8-sig")
    offenders = [
        line.strip() for line in text.splitlines()
        if line.strip().startswith("$probe") and "& $psql" in line
    ]
    assert offenders == [], f"连库探测要经 Invoke-Exe(失败只以退出码回来): {offenders}"
    assert "$probeRc = Invoke-Exe $psql" in text, "找不到走 Invoke-Exe 的探测, 用例该跟着脚本改"


def test_a_missing_database_prints_the_hint_instead_of_only_a_powershell_exception(tmp_path):
    """库连不上时, 用户要看到「确认 PostgreSQL 服务在跑 / 端口对 / 口令对」, 而不是一段异常。

    2026-09-26 真踩到: 便携库停了(留下一个死 postmaster.pid), 安装脚本探测连库失败, 本该
    打出来的那两行提示被一句 NativeCommandError 整段盖掉 —— 报错把「下一步该干什么」也
    一起遮住了。这条用一个连不上任何东西的端口真跑一遍脚本(跳过依赖与快捷方式), 只看它说了什么。
    同样只在 Windows 上跑: 脚本里到处是 Windows 的路径与命令。
    """
    powershell = _windows_powershell_or_skip()
    candidates = [
        shutil.which("psql"),
        r"C:\pgtemp\pginstall\bin\psql.exe",
        *[str(p) for p in sorted(pathlib.Path(r"C:\Program Files\PostgreSQL").glob(r"*\bin\psql.exe"))],
    ]
    psql = next((c for c in candidates if c and pathlib.Path(c).exists()), None)
    if not psql:
        import pytest

        pytest.skip("这台机器上没有 psql, 走不到安装脚本的连库那一步")

    # 借一个刚关闭的空端口: 几乎不可能有人在听, 也就不可能误判成「库在跑」
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]

    proc = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(INSTALL_PS1),
         "-TargetDir", str(tmp_path / "app"), "-SkipDeps", "-SkipShortcuts", "-NoPause",
         "-PgBin", str(pathlib.Path(psql).parent), "-PgPort", str(dead_port)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = out.strip()[-500:]
    assert proc.returncode == 1, f"连不上库时应当以 1 退出: {tail}"
    assert "连不上数据库" in out, f"缺「连不上数据库」这句: {tail}"
    assert "确认 PostgreSQL 服务在跑" in out, f"给人看的提示被异常盖掉了: {tail}"
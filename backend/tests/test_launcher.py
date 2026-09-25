"""本地应用启动器的守线: 把今天踩过的坑变成可执行的断言。

启动器是**本机用**的那条路径(scripts/damo-app.ps1 + damo.cmd), 它不在 CI 的测试矩阵里,
所以这里用文本级断言替它把关 —— 三条都是真出过事或真会出事的:

- .ps1 不带 BOM: PowerShell 5.1 会按系统码页(中文机器上是 GBK)读文件, 中文注释被解成
  乱码, 严重时直接语法错(实测: 一个中文注释的脚本报 UnexpectedToken)
- .ps1 里出现 0.0.0.0: 这是给人在这台机器上用的应用, 不该顺手对局域网开口
- --reload: 那是 dev-up.ps1 的场景; 应用路径开了它, 进程会多一层, 关窗收不干净
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
APP_PS1 = SCRIPTS / "damo-app.ps1"
CMD = ROOT / "damo.cmd"
BOM = b"\xef\xbb\xbf"


def powershell_scripts() -> list[pathlib.Path]:
    return sorted(SCRIPTS.glob("*.ps1"))


def test_every_powershell_script_starts_with_a_bom():
    """没 BOM 的 .ps1 在中文 Windows 上会被按 GBK 读 —— 中文注释直接变乱码。"""
    scripts = powershell_scripts()
    assert scripts, "scripts 目录下一个 .ps1 都没有, 这个用例就没意义了"
    missing = [p.name for p in scripts if not p.read_bytes().startswith(BOM)]
    assert missing == [], f"这些 .ps1 缺 UTF-8 BOM: {missing}"


def test_the_app_binds_to_loopback_only():
    text = APP_PS1.read_text(encoding="utf-8-sig")
    assert "0.0.0.0" not in text, "本机应用不该绑 0.0.0.0(等于对局域网开口)"
    assert "127.0.0.1" in text


def test_the_app_does_not_run_uvicorn_with_reload():
    """只看真正拉起 uvicorn 的那一行, 不做裸词匹配。

    这条是照 v3.8 的教训写的: 当时「不做定位」的界面文案被守线的裸词 grep 拦下来,
    于是每个提交都红。这里同理 —— 脚本的注释里**必须**能写「--reload 是 dev-up 的事」,
    被查的只有那条命令。
    """
    invocations = [
        line for line in APP_PS1.read_text(encoding="utf-8-sig").splitlines()
        if '"uvicorn"' in line
    ]
    assert invocations, "没找到拉起 uvicorn 的那一行, 用例该跟着脚本改"
    for line in invocations:
        assert "--reload" not in line, f"应用路径不要 --reload: {line.strip()}"


def test_no_secrets_are_baked_into_the_launcher():
    """启动脚本会被复制、会被贴给别人看, 不许把密钥写进去。"""
    for path in [APP_PS1, CMD]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for needle in ("GEO_IP_API_KEY=", "LLM_API_KEY=", "API_KEY=", "PASSWORD="):
            assert needle not in text, f"{path.name} 里出现了疑似密钥: {needle}"


def test_the_double_click_entry_point_is_ascii_only():
    """cmd.exe 按 OEM 码页读文件, 中文写进 .cmd 只会变成乱码。"""
    assert CMD.is_file(), "缺 damo.cmd(双击入口)"
    bad = [i for i, byte in enumerate(CMD.read_bytes()) if byte > 127]
    assert bad == [], f"damo.cmd 里有非 ASCII 字节: {bad[:5]}"

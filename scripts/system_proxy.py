#!/usr/bin/env python3
"""读本机的 Windows 代理设置, 并实测「命令行到底会不会走代理」。

为什么需要这个文件
------------------
浏览器能打开某个站点, 不等于命令行也能 —— 这是本机排查「抓不到图」时最容易卡住的地方:

  * Windows 有**两套互不相通**的代理设置: WinINET(浏览器与多数 GUI 程序用)与
    WinHTTP(系统服务与部分命令行工具用)。在工具里打开的「系统代理」写的是 WinINET。
  * WinINET 里还分「固定代理」与「PAC 脚本(AutoConfigURL)」。PAC 是一段 JavaScript,
    由浏览器取回并执行后才算出该走哪个代理 —— **Python 与 curl 都不执行 PAC**, 所以在
    PAC 模式下命令行会继续走直连, 表现就是「浏览器能上, 脚本上不了」。
  * Python 只看两处: 环境变量, 与 WinINET 的固定代理(见 urllib.request.getproxies)。
    而且**环境变量优先**: 只要设了其中任何一个, 就完全不再看注册表。

用法
----
    python scripts/system_proxy.py                        # 现在是什么状况
    python scripts/system_proxy.py --test                 # 再实测一次能不能连出去
    python scripts/system_proxy.py --proxy http://127.0.0.1:7890 --test
                                                          # 直接验一个地址(不改系统设置)
    python scripts/system_proxy.py --url https://example.com/ --test
    python scripts/system_proxy.py --export powershell    # 打印可直接粘的临时设置命令
    python scripts/system_proxy.py --json                 # 给别的脚本吃

它**只读**注册表与环境变量, 不改任何设置; 打印出来的命令要不要跑, 由你决定。
退出码: 0 读到了可用代理或至少设置正常; 1 没找到可用代理; 2 平台不对; 3 有代理但连不通。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, getproxies, urlopen

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
ENV_KEYS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
)
# 默认拿维基媒体的 API 试: 它在国内是典型的「必须走代理」的站点, 一次请求就能分清
# 「代理真的生效了」还是「命令行在直连」。
DEFAULT_TEST_URL = "https://commons.wikimedia.org/w/api.php?format=json"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: 免得每次跑都闪一个黑框

def read_wininet() -> dict:
    """读 WinINET(「系统代理」开关写的地方)的四项, 缺的给 None。"""
    import winreg

    keys = ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL")
    out: dict = {k: None for k in keys}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as handle:
            for name in keys:
                try:
                    out[name] = winreg.QueryValueEx(handle, name)[0]
                except FileNotFoundError:
                    out[name] = None
    except FileNotFoundError:
        pass
    return out


def read_env_proxies() -> dict:
    """读环境变量里的代理。设成空串等于没设 —— 这是常见的「看着像配了」。"""
    out: dict = {}
    for key in ENV_KEYS:
        value = (os.environ.get(key) or "").strip()
        if not value:
            continue
        # Windows 的环境变量大小写不敏感: HTTPS_PROXY 会被大小写两个键各读到一遍,
        # 只留一份, 免得输出看着像设了两个。
        if key.islower() and out.get(key.upper()) == value:
            continue
        out[key] = value
    return out


def as_url(value: str, scheme: str = "http") -> str:
    """补上协议: 注册表里常写成 `127.0.0.1:7890` 这种不带协议的。

    socks 条目要补成 socks5:// —— 补成 http:// 会让它看着像一个根本不存在的端口。
    """
    value = (value or "").strip()
    if not value:
        return ""
    if "://" in value:
        return value
    if scheme.lower().startswith("socks"):
        return "socks5://" + value
    return "http://" + value


def parse_proxy_server(raw) -> dict:
    """把 ProxyServer 拆成 {协议: 地址}。

    它有两种写法, 都得认:
        127.0.0.1:7890                             # 一个地址给所有协议用
        http=127.0.0.1:7890;https=1.2.3.4:8080     # 按协议分开
    """
    if not raw:
        return {}
    text = str(raw)
    if "=" not in text:
        url = as_url(text)
        return {"http": url, "https": url}
    out: dict = {}
    for part in text.split(";"):
        scheme, _, value = part.partition("=")
        scheme, value = scheme.strip().lower(), value.strip()
        if scheme and value:
            out[scheme] = as_url(value, scheme)
    return out


def parse_override(raw) -> list:
    """ProxyOverride -> 旁路清单; `<local>` 是「不含点的主机名」的意思。"""
    if not raw:
        return []
    return [item.strip() for item in str(raw).split(";") if item.strip()]


def _decode(raw: bytes) -> str:
    """netsh 的输出既不是 UTF-8 也不是 GBK(实测是 OEM 代码页), 逐个试, 不一上来就崩。"""
    for encoding in ("utf-8", "oem", "mbcs"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def read_winhttp() -> str:
    """WinHTTP 那套设置(netsh 看得到)。原样给出来 —— 输出随系统语言变, 不解析更诚实。"""
    try:
        done = subprocess.run(
            ["netsh", "winhttp", "show", "proxy"],
            capture_output=True, timeout=15, creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # netsh 不在或超时
        return f"(读不到: {exc})"
    text = _decode(done.stdout).strip() or _decode(done.stderr).strip()
    return text or "(空)"

def build_report(override: str = "") -> dict:
    """把三处设置读一遍, 算出「命令行实际会用哪个代理」以及为什么。"""
    env = read_env_proxies()
    wininet = read_wininet()
    winhttp = read_winhttp()
    parsed = parse_proxy_server(wininet["ProxyServer"])
    enabled = int(wininet["ProxyEnable"] or 0) == 1
    pac = (wininet["AutoConfigURL"] or "").strip()
    bypass = parse_override(wininet["ProxyOverride"])

    notes: list = []
    effective: dict = {}
    source = ""

    def from_env(key: str) -> str:
        return env.get(key) or env.get(key.upper()) or ""

    if override:
        url = as_url(override)
        effective = {"http": url, "https": url}
        source = "命令行 --proxy"
    elif env:
        http = from_env("http_proxy") or from_env("all_proxy")
        https = from_env("https_proxy") or from_env("all_proxy")
        effective = {k: as_url(v) for k, v in (("http", http), ("https", https)) if v}
        source = "环境变量"
        if from_env("all_proxy") and not from_env("https_proxy"):
            notes.append("只设了 ALL_PROXY: requests 认它, urllib 与 curl 不认 —— 要显式设 HTTPS_PROXY。")
        if any(str(v).startswith("socks") for v in effective.values()):
            notes.append("这是 SOCKS 入口: Python urllib 不直接支持(要装 PySocks), "
                         "curl 要用 --socks5-hostname —— 建议换成工具里的 HTTP 入口。")
        if enabled and parsed:
            notes.append("环境变量会盖过系统代理: 命令行用上面这个, 不是 WinINET 里那个。")
    elif enabled and parsed:
        effective = dict(parsed)
        # 多数工具只开一个入口, 注册表里往往只有 http; https 也跟着它走。
        if "http" in effective and "https" not in effective:
            effective["https"] = effective["http"]
        source = "WinINET 系统代理"
    else:
        source = ""
        if pac:
            notes.append(
                "只有 PAC 脚本(AutoConfigURL): Python 与 curl 都不执行 PAC, 命令行会走直连。"
                "要么在工具里换成「固定端口 + 系统代理」, 要么显式设 HTTPS_PROXY。"
            )
        if not enabled and wininet["ProxyServer"]:
            notes.append("注册表里有 ProxyServer 但 ProxyEnable=0 —— 「系统代理」那个开关没打开。")
    if ("direct" in winhttp.lower() or "直接访问" in winhttp) and effective:
        notes.append("WinHTTP 是直连(部分命令行工具只认它): 如果某个工具仍连不上, 试试 netsh winhttp import proxy source=ie。")

    return {
        "platform": f"{sys.platform} {sys.getwindowsversion().major}.{sys.getwindowsversion().build}" if sys.platform == "win32" else sys.platform,
        "env": env,
        "wininet": {
            "enabled": enabled,
            "server": wininet["ProxyServer"],
            "parsed": parsed,
            "pac": pac,
            "bypass": bypass,
        },
        "winhttp": winhttp,
        "python_view": {k: as_url(v) for k, v in getproxies().items()},
        "effective": effective,
        "source": source,
        "notes": notes,
    }


def probe(url: str, proxies: dict, timeout: float) -> dict:
    """拿一次真实请求试。proxies 为空 = 显式直连(免得又被环境变量接走)。"""
    from urllib.request import ProxyHandler, build_opener

    opener = build_opener(ProxyHandler(dict(proxies)))
    req = Request(url, headers={"User-Agent": "have-a-trip-proxy-check/0.1"})
    started = time.time()
    try:
        with opener.open(req, timeout=timeout) as resp:
            head = resp.read(240)
            return {
                "ok": True,
                "status": resp.status,
                "seconds": round(time.time() - started, 2),
                "head": head.decode("utf-8", "replace").strip()[:150],
            }
    except HTTPError as exc:  # 有响应, 只是状态码不 200 —— 代理其实是通的
        return {"ok": False, "status": exc.code, "seconds": round(time.time() - started, 2),
                "error": f"HTTP {exc.code}"}
    except URLError as exc:
        return {"ok": False, "seconds": round(time.time() - started, 2), "error": str(exc.reason)}
    except Exception as exc:  # noqa: BLE001 —— 读代理这事, 什么异常都可能冒出来
        return {"ok": False, "seconds": round(time.time() - started, 2),
                "error": f"{type(exc).__name__}: {exc}"}

def _joined(mapping: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in mapping.items()) if mapping else "(无)"


def format_human(rep: dict, test: dict = None, url: str = "") -> str:
    env = rep["env"]
    wi = rep["wininet"]
    out = ["Windows 代理体检", ""]
    out.append(f"  环境变量   : {_joined(env) if env else '无 HTTP_PROXY / HTTPS_PROXY / ALL_PROXY'}")
    out.append(f"  WinINET    : {'已启用' if wi['enabled'] else '未启用(ProxyEnable=0)'}")
    out.append(f"     代理服务器: {wi['server'] if wi['server'] else '(无)'}")
    if wi["parsed"]:
        out.append(f"     解析结果  : {_joined(wi['parsed'])}")
    out.append(f"     PAC 脚本  : {wi['pac'] if wi['pac'] else '(无)'}")
    out.append(f"     旁路      : {'; '.join(wi['bypass']) if wi['bypass'] else '(无)'}")
    rows = (rep["winhttp"] or "").splitlines()
    out.append(f"  WinHTTP    : {rows[0] if rows else '(空)'}")
    for extra in rows[1:]:
        out.append(f"               {extra}")
    out.append(f"  Python 看到: {_joined(rep['python_view'])}")
    if rep["effective"]:
        where = rep["effective"].get("https") or rep["effective"].get("http")
        out.append(f"  结论       : 命令行会走 {where}(来源: {rep['source']})")
    else:
        out.append("  结论       : 命令行会走直连 —— 没找到可用代理。")
    for note in rep["notes"]:
        out.append(f"  注意       : {note}")
    if test is not None:
        if test.get("ok"):
            out.append(f"  实测       : {url} -> HTTP {test['status']}, {test['seconds']}s, {test['head']!r}")
            out.append(f"               走的是 {'直连' if not rep['effective'] else rep['effective'].get('https') or rep['effective'].get('http')}")
        else:
            out.append(f"  实测       : 失败({test['seconds']}s): {test['error']}")
            if rep["effective"]:
                out.append("               代理没把请求带出去 —— 换个节点, 或确认它不是只认 SOCKS。")
            else:
                out.append("               直连被挡住了。要连这个地址就得先有代理。")
    return "\n".join(out)


def export_lines(proxies: dict, style: str) -> list:
    """把有效代理变成可直接粘的临时环境变量命令。"""
    https = proxies.get("https") or proxies.get("http") or ""
    http = proxies.get("http") or https
    https = proxies.get("https") or http
    if not http:
        return []
    if style == "powershell":
        return [
            f'$env:HTTP_PROXY  = "{http}"',
            f'$env:HTTPS_PROXY = "{https}"',
            '$env:NO_PROXY     = "localhost,127.0.0.1,::1"',
        ]
    if style == "cmd":
        return [
            f"set HTTP_PROXY={http}",
            f"set HTTPS_PROXY={https}",
            "set NO_PROXY=localhost,127.0.0.1,::1",
        ]
    return [
        f'export HTTP_PROXY="{http}"',
        f'export HTTPS_PROXY="{https}"',
        'export NO_PROXY="localhost,127.0.0.1,::1"',
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="读 Windows 的代理设置, 并实测「命令行会不会走代理」。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--proxy", default="", metavar="URL",
                        help="直接用这个代理验, 例如 http://127.0.0.1:7890(不改系统设置)")
    parser.add_argument("--test", action="store_true", help="发一次真实请求试到底通不通")
    parser.add_argument("--url", default=DEFAULT_TEST_URL, help="--test 要连的地址")
    parser.add_argument("--timeout", type=float, default=10.0, help="--test 的超时秒数(默认 10)")
    parser.add_argument("--export", choices=("powershell", "cmd", "sh"),
                        help="打印可直接粘的临时设置命令")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    if sys.platform != "win32":
        print("这个脚本读的是 Windows 的代理设置, 当前平台不是 Windows。", file=sys.stderr)
        return 2

    rep = build_report(args.proxy)
    result = probe(args.url, rep["effective"], args.timeout) if args.test else None
    exported = export_lines(rep["effective"], args.export) if args.export else []

    if args.json:
        print(json.dumps(dict(rep, test=result, export=exported), ensure_ascii=False, indent=2))
    else:
        print(format_human(rep, result, args.url))
        if args.export:
            print("")
            if exported:
                print(f"# 临时设置({args.export}, 只影响当前窗口):")
                for line in exported:
                    print(line)
            else:
                print("# 没发现可用代理, 导不出。先把工具的「系统代理」打开, 或用 --proxy 直接给地址。")
        elif rep["effective"]:
            print("")
            print("  想把它设成临时环境变量: 加 --export powershell")

    if result is not None:
        if result.get("ok"):
            return 0
        return 3 if rep["effective"] else 1
    return 0 if rep["effective"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
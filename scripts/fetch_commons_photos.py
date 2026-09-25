# -*- coding: utf-8 -*-
"""从 Wikimedia Commons 抓景点实景照片, 产出 db/seed/photos.json 与封面文件。

为什么要有这个脚本: 仓库里的配图分两种, 自绘的 SVG 由 make_attraction_covers.py
生成, 抓来的实景照片由本脚本产出 —— 都留脚本, 出处才查得到。台账逐张记
pid / seq / slug / photo / license / artist / source, 落库到 attraction_image。

许可口径(与 docs/LICENSE-AUDIT.md 第五节一致):
  只收 Public domain / CC0 / CC BY / CC BY-SA; 排除 NC / ND / 非自由;
  脚本只能保证"没收录错许可", 署名义务靠人看 —— CC BY-SA 有相同方式共享义务,
  CC BY 有署名义务, 用到就得在声明页逐图署名。前端目前只把封面的 credit
  聚合成一行, 逐图署名仍是缺口, 见 docs/LICENSE-AUDIT.md 第五节。

网络: Wikimedia 在中国大陆直连不通(TLS 握手上被重置), 需要能出去的代理, 形如
      --proxy http://127.0.0.1:7890; 代理会轮换重试, 坏掉的自动跳过。

用法:
  python scripts/fetch_commons_photos.py --proxy-file proxies.txt --levels 5A --width 800
  python scripts/fetch_commons_photos.py --redo --slugs-file retry.txt
  python scripts/fetch_commons_photos.py --check     # 只校验台账与磁盘上的封面

抓完接着跑 python scripts/make_attraction_covers.py 把台账编进 db/seed/images.sql。
--check 退出码: 0 一致, 1 有对不上的条目。
"""
import argparse, concurrent.futures as cf, csv, io, json, re, sys, time
import http.client, socket, ssl
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PHOTOS_JSON = ROOT / "db" / "seed" / "photos.json"
COVER_DIR = ROOT / "frontend" / "public" / "images" / "covers"
SEED_PATHS = (ROOT / "db" / "seed" / "seed.sql", ROOT / "db" / "seed" / "attractions_cn.sql")
CN_CSV = ROOT / "db" / "seed" / "data" / "cn_a_level.csv"


def read_text(path):
    """按 UTF-8 读文本。utf-8-sig 让带 BOM 的文件也能读(种子里混着 BOM 过)。"""
    return io.open(path, encoding="utf-8-sig").read()
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

UA = "Have-A-Trip-PhotoFetcher/0.1 (Wikimedia Commons; one-off public-data fetch)"

ALLOW = ("cc0", "public domain", "cc by", "cc-by", "pd-")
BAD = re.compile(
    r"landsat|satellite|sentinel|modis|map\b|locator|logo|diagram|schematic|floor ?plan|"
    r"\bchart\b|coat of arms|\bflag\b|\bseal\b|stamp|banknote|screenshot|\bicon\b|"
    r"drawing|painting|sketch|\bposter\b|panorama ?360|qr ?code|infographic|"
    r"hospital|airport|railway|metro station|bus station|parking|toll|"
    r"机场|醫院|医院|火车站|地铁站|車站|车站|停车场|收费站|"
    r"圖卷|图卷|画卷|清趣|絹本|纸本|紙本|\.svg$|\.pdf$|\.gif$", re.I)
CITY = re.compile(r"^.{1,8}?(市|自治州|地区|省|县|区|盟|旗)")
SUFFIX = re.compile(
    r"(风景名胜区|风景区|旅游景区|旅游区|景区|国家森林公园|森林公园|自然保护区|"
    r"度假区|旅游度假区|博物馆|纪念馆|古城|古镇|遗址|石窟|陵园|陵|公园|湿地|"
    r"大峡谷|峡谷|瀑布|溶洞|温泉|滑雪场|文化区|文化园|广场)$")
PUNCT = re.compile(r"[•·、，,\-—()（）\s]+")


def strip_html(s):
    return re.sub(r"<[^>]+>", " ", s or "").replace("&amp;", "&").strip()


def norm(s):
    return PUNCT.sub("", s or "").strip()


def levels_of():
    """slug -> "5A" / "4A" / "3A"。

    两处来源, 少一处就会漏掉一批景点: 名录条目的等级写在 db/seed/data/cn_a_level.csv,
    自采档案(黄山、故宫那一批)的等级写在 db/seed/seed.sql 的等级映射表里。
    在库外把等级算出来, 是为了让 --levels 不依赖数据库也能跑。
    """
    out = {}
    if CN_CSV.exists():
        with io.open(CN_CSV, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                slug = (row.get("slug") or "").strip()
                grade = (row.get("grade") or "").strip().upper()
                if slug and grade:
                    out[slug] = grade
    text = read_text(SEED_PATHS[0])
    for m in re.finditer(r"^\s*\('([a-z0-9-]+)',\s*'(5A|4A|3A|2A|1A)',", text, re.M):
        out.setdefault(m.group(1), m.group(2))
    return out


def variants(name):
    """名录里是全称(丽江市玉龙雪山景区), Commons 文件名常用核心名(玉龙雪山)。"""
    base = norm(name)
    out = [base]
    for c in (CITY.sub("", base), SUFFIX.sub("", base),
              SUFFIX.sub("", CITY.sub("", base)), CITY.sub("", SUFFIX.sub("", base))):
        c = norm(c)
        if len(c) >= 2 and c not in out:
            out.append(c)
    return out


def licence_ok(short, terms):
    s, t = (short or "").lower(), (terms or "").lower()
    if re.search(r"[\s-](nc|nd)\b", s) or "noncommercial" in t or "noderiv" in t:
        return False
    if "fair use" in s or "non-free" in s or "copyright" in s:
        return False
    return any(a in s for a in ALLOW) or "public domain" in t or "cc0" in t

class Pool:
    """轮换用代理池; 全部标记坏掉之后清空重来。"""

    def __init__(self, entries):
        self.entries = list(entries)
        self.bad = set()
        self.lock = __import__("threading").Lock()

    def pick(self):
        with self.lock:
            live = [e for e in self.entries if e not in self.bad]
            if not live:
                self.bad.clear()
                live = list(self.entries)
        import random
        return random.choice(live)

    def note(self, entry, ok):
        with self.lock:
            if ok:
                self.bad.discard(entry)
            else:
                self.bad.add(entry)

    def get(self, host, path, timeout=12, tries=None):
        tries = tries or max(6, len(self.entries) * 2)
        last = "?"
        for _ in range(tries):
            entry = self.pick()
            try:
                status, body = self._one(entry, host, path, timeout)
                if status == 200:
                    self.note(entry, True)
                    return body
                last = "HTTP %d" % status
            except Exception as e:
                last = "%s: %s" % (type(e).__name__, e)
            self.note(entry, False)
        raise RuntimeError("代理都不通, 最后错误 %s" % last)

    def _one(self, entry, host, path, timeout):
        kind, ph, pp = entry
        if kind == "http":
            c = http.client.HTTPSConnection(ph, pp, timeout=timeout)
            c.set_tunnel(host, 443)
            c.request("GET", path, headers={"User-Agent": UA, "Accept": "*/*"})
            r = c.getresponse()
            status, body = r.status, r.read()
            c.close()
            return status, body
        s = socket.create_connection((ph, pp), timeout)
        s.settimeout(timeout)
        s.sendall(b"\x05\x01\x00")
        if s.recv(2)[:1] != b"\x05":
            s.close()
            raise OSError("not socks5")
        h = host.encode()
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(h)]) + h + (443).to_bytes(2, "big"))
        rep = s.recv(10)
        if len(rep) < 2 or rep[1] != 0:
            s.close()
            raise OSError("socks5 reject")
        tls = ssl.create_default_context().wrap_socket(s, server_hostname=host)
        tls.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
                     "Accept: */*\r\nConnection: close\r\n\r\n" % (path, host, UA)).encode())
        chunks = []
        while True:
            b = tls.recv(65536)
            if not b:
                break
            chunks.append(b)
        tls.close()
        head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
        parts = head.split(b" ")
        if len(parts) < 2:
            raise OSError("bad status line")
        return int(parts[1]), body


def api(pool, host, params):
    params = dict(params)
    params.setdefault("format", "json")
    params.setdefault("formatversion", 2)
    return json.loads(pool.get(host, "/w/api.php?" + urlencode(params)))


def search(pool, query, limit, width):
    j = api(pool, "commons.wikimedia.org", {
        "action": "query", "generator": "search",
        "gsrsearch": "%s filetype:bitmap" % query, "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": width})
    out = []
    for p in (j.get("query") or {}).get("pages") or []:
        ii = p.get("imageinfo") or []
        if not ii:
            continue
        ii = ii[0]
        em = ii.get("extmetadata") or {}
        g = lambda k: strip_html((em.get(k) or {}).get("value", ""))
        out.append({
            "file": p.get("title"), "descriptionurl": ii.get("descriptionurl"),
            "thumb": ii.get("thumburl"), "width": ii.get("width") or 0,
            "height": ii.get("height") or 0, "mime": ii.get("mime") or "",
            "license": g("LicenseShortName"), "terms": g("UsageTerms"),
            "artist": g("Artist")[:120], "desc": g("ImageDescription")[:300],
        })
    return out


def score(c, name, name_en):
    f = c.get("file") or ""
    if BAD.search(f) or not licence_ok(c["license"], c["terms"]):
        return -99
    if c["mime"] not in ("image/jpeg", "image/png") or c["width"] < 1000:
        return -99
    blob = (f + " " + c.get("desc", "")).lower()
    s = 4 if name and name in (f + " " + c.get("desc", "")) else 0
    toks = [t for t in re.split(r"[^A-Za-z]+", (name_en or "").lower()) if len(t) >= 4]
    hit = [t for t in toks if t in blob]
    s += 3 if len(hit) > 1 else (2 if hit else 0)
    if c["width"] > c["height"]:
        s += 1
    if c["width"] >= 1600:
        s += 1
    return s

def load_attractions(slugs_file=None, levels=None):
    """景点清单取自两个种子文件(与自绘封面同一个来源), 可按 slug 白名单与等级过滤。

    返回 (slug, name, name_en, seq)。seq 是该景点在"先按等级、再按种子文件顺序"里的
    序号 —— 与库里 `order by a_level, id` 的顺序一致(id 就是种子的插入顺序), 台账里的
    seq 就是这么来的: 先定 seq 再抓图, 抓不到的仍然占着号, 所以 seq 有跳号是正常的。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_attraction_covers as covers
    rows = []
    for p in SEED_PATHS:
        parsed, _skipped = covers.parse_attractions(read_text(p))
        rows.extend(parsed)
    lv = levels_of()
    if levels:
        want_lv = {x.strip().upper() for x in levels if x.strip()}
        rows = [r for r in rows if lv.get(r[0]) in want_lv]
    if slugs_file:
        want = {l.strip() for l in io.open(slugs_file, encoding="utf-8") if l.strip()}
        rows = [r for r in rows if r[0] in want]
    rank = {"5A": 0, "4A": 1, "3A": 2}
    rows.sort(key=lambda r: rank.get(lv.get(r[0]), 3))   # 稳定排序, 同级内保持种子顺序
    return [(slug, name, name_en or "", i)
            for i, (slug, name, name_en, _category) in enumerate(rows, 1)]


def fetch_one(pool, slug, name, name_en, seq, width, min_score):
    """搜 + 打分 + 下载。搜不到合适照片返回 None(不是异常 —— 冷门景点本来就常没有)。"""
    best, best_s, used = None, 0, None
    for q in variants(name)[:3]:
        try:
            cands = search(pool, q, 8, width)
        except Exception:
            continue
        for c in cands:
            for v in variants(name):
                s = score(c, v, name_en)
                if s > best_s:
                    best, best_s, used = c, s, q
        if best_s >= 6:
            break
    if not best or best_s < min_score:
        return None
    url = best["thumb"]
    parts = urlsplit(url)
    if not parts.netloc:
        raise RuntimeError("缩略图地址不完整: %r" % url)
    body = pool.get(parts.netloc, parts.path + ("?" + parts.query if parts.query else ""),
                    timeout=25)
    # 缩略图地址的后缀就是真实格式(可能是 .png / .jpeg), 拿不到才退回 mime 推断。
    suffix = Path(parts.path).suffix.lower()
    ext = suffix if suffix in (".jpg", ".jpeg", ".png") else (
        ".jpg" if "jpeg" in best["mime"] else ".png")
    target = COVER_DIR / (slug + ext)
    target.write_bytes(body)
    # 重抓时格式可能变(上次 .png 这次 .jpg), 不清掉旧文件会留下两张同 slug 的封面。
    for other in (".jpg", ".jpeg", ".png"):
        stale = COVER_DIR / (slug + other)
        if stale != target and stale.exists():
            stale.unlink()
    return {"seq": seq, "slug": slug, "photo": slug + ext, "file": best["file"],
            "license": best["license"], "artist": best["artist"],
            "source": best["descriptionurl"], "width": best["width"],
            "height": best["height"], "from": used}


def check() -> int:
    """只校验台账: 每条都要有许可、作者, 且文件在磁盘上。不联网。"""
    if not PHOTOS_JSON.exists():
        print("没有 %s, 先抓一次" % PHOTOS_JSON.relative_to(ROOT))
        return 1
    items = json.loads(PHOTOS_JSON.read_text(encoding="utf-8"))
    problems = []
    for it in items:
        slug, photo = it.get("slug"), it.get("photo")
        if not slug or not photo:
            problems.append("第 %s 条缺 slug / photo" % it.get("pid"))
            continue
        if not (it.get("license") or "").strip():
            problems.append("%s 缺 license" % slug)
        if not (it.get("artist") or "").strip():
            problems.append("%s 缺 artist" % slug)
        path = COVER_DIR / photo
        if not path.exists() or path.stat().st_size == 0:
            problems.append("%s 台账里写的是 %s, 磁盘上没有" % (slug, photo))
    if problems:
        print("照片台账与磁盘对不上:")
        for p in problems[:40]:
            print("  -", p)
        print("共 %d 条问题" % len(problems))
        return 1
    print("照片台账 %d 条, 与磁盘一致" % len(items))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", action="append", default=[],
                    help="http://host:port 或 socks5://host:port, 可多次")
    ap.add_argument("--proxy-file", help="每行一个 host:port 的文件")
    ap.add_argument("--slugs-file", help="只抓这些 slug(每行一个)")
    ap.add_argument("--levels", default="", help="只抓这些等级, 逗号分隔(如 5A 或 5A,4A); 留空=全部")
    ap.add_argument("--width", type=int, default=800, help="缩略图宽度(px)")
    ap.add_argument("--min-score", type=int, default=4, help="打分低于它就不要这张图")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--redo", action="store_true", help="连已有照片的景点也重抓")
    ap.add_argument("--check", action="store_true", help="只校验台账与磁盘, 不联网")
    a = ap.parse_args()
    if a.check:
        return check()

    if not a.proxy and not a.proxy_file:
        print("需要代理: Wikimedia 在中国大陆直连不通。--proxy 或 --proxy-file 给一个。")
        return 2
    entries = []
    for spec in a.proxy:
        kind, _, hp = spec.partition("://")
        if hp:
            host, _, port = hp.rpartition(":")
            entries.append(("socks5" if "socks" in kind else "http", host, int(port)))
        else:
            host, _, port = spec.rpartition(":")
            entries.append(("http", host, int(port)))
    if a.proxy_file:
        for line in io.open(a.proxy_file, encoding="utf-8"):
            line = line.strip()
            if line and ":" in line and not line.startswith("#"):
                host, _, port = line.rpartition(":")
                entries.append(("http", host, int(port)))
    pool = Pool(entries)

    existing = json.loads(PHOTOS_JSON.read_text(encoding="utf-8")) if PHOTOS_JSON.exists() else []
    have = {e["slug"] for e in existing}
    rows = load_attractions(a.slugs_file, [x for x in a.levels.split(",") if x.strip()])
    todo = [r for r in rows if a.redo or r[0] not in have]
    print("景点 %d 个, 已有照片 %d 个, 本次待抓 %d 个" % (len(rows), len(have), len(todo)), flush=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)

    got, t0 = [], time.time()
    with cf.ThreadPoolExecutor(max_workers=a.threads) as ex:
        futs = {ex.submit(fetch_one, pool, s, n, en, seq, a.width, a.min_score): s
                for s, n, en, seq in todo}
        for f in cf.as_completed(futs):
            slug = futs[f]
            try:
                r = f.result()
            except Exception as e:
                r = None
                print("  %-30s 失败 %s" % (slug, type(e).__name__), flush=True)
            if r:
                got.append(r)
                print("  %-30s ok  %-16s %s" % (slug, r["license"][:15], r["file"][:44]), flush=True)

    merged = {e["slug"]: e for e in existing}
    for r in got:
        merged[r["slug"]] = r
    ordered = sorted(merged.values(), key=lambda e: (e.get("seq") is None, e.get("seq") or 0))
    fixed = []
    for i, e in enumerate(ordered, 1):
        e.pop("bytes", None)
        e.pop("pid", None)
        fixed.append({"pid": i, **e})
    # newline="\n" 是必须的: .gitattributes 要求 *.json 用 LF, 而 Path.write_text 在
    # Windows 上会把 \n 翻成 CRLF —— 那样每跑完一次都在工作区留下一份换行不同的文件。
    io.open(PHOTOS_JSON, "w", encoding="utf-8", newline="\n").write(
        json.dumps(fixed, ensure_ascii=False, indent=2) + "\n")
    print("---")
    print("本次抓到 %d 张, 台账共 %d 张, 耗时 %.0fs" % (len(got), len(fixed), time.time() - t0))
    print("台账已写入 %s" % PHOTOS_JSON.relative_to(ROOT))
    print("接着跑: python scripts/make_attraction_covers.py   # 重新生成 images.sql")
    return 0


if __name__ == "__main__":
    sys.exit(main())
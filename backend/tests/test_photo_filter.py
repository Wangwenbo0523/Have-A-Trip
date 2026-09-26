"""配图抓取的守线: 「抓回来的是照片吗」这件事要能自动判, 不能只靠人过目。

2026-09-26 用户的反馈是「还有一些是 AI 生成的图片, 更改为实拍」—— 查下来仓库里的配图只有两种:
130 张 Commons 实拍照片 + 1255 张自绘 SVG(就是被当成「AI 生成」的那批), 台账里没有任何一张
是 AI 画的。但顺手重跑抓图脚本时, 西湖抓到的是《漂海录》西湖图象.jpg —— **一张古籍木刻插图**:
文件名里既没有 painting 也没有 drawing, 老的 BAD 正则拦不住, 于是它作为「实拍」进了台账。

所以过滤器要按**类别**判: Commons 的 AI 生成图、版画、木刻、舆图、手稿都有各自的类别,
文件名能骗人、类别骗不了人。这个文件守着这条 —— 顺带守住「照片还能正常打分通过」,
免得把过滤器收得太紧, 把好图也一起挡了。
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "fetch_commons_photos.py"

_spec = importlib.util.spec_from_file_location("fetch_commons_photos", SCRIPT)
fetch = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fetch)


def candidate(file, categories=(), desc="", width=3000, height=2000,
              license="CC BY-SA 4.0", terms="", mime="image/jpeg"):
    """造一个候选, 字段与 search() 返回的那一份一致。"""
    return {
        "file": file, "desc": desc, "categories": list(categories),
        "width": width, "height": height, "license": license, "terms": terms,
        "mime": mime, "artist": "某摄影师", "source": "https://example.invalid",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:X.jpg",
    }


def test_a_woodblock_book_illustration_is_refused():
    """《漂海录》西湖图象.jpg: 名字里不带 painting / drawing, 靠文件名就得多挡一层。"""
    assert fetch.score(candidate("File:《漂海录》西湖图象.jpg"), "西湖", "West Lake") == -99


def test_a_scan_in_a_woodcut_category_is_refused():
    """名字看不出来时, 类别要说话 —— 这条是老过滤器真正漏掉的那类。"""
    c = candidate("File:West Lake scenery.jpg", categories=["Category:Woodcuts of China"])
    assert fetch.score(c, "西湖", "West Lake") == -99


def test_an_ai_generated_picture_is_refused():
    """用户口径里的「AI 生成的图片」: Commons 上确实有, 而且常常是一张很好看的假实拍。"""
    for cat in ("Category:AI-generated images", "Category:Images generated with Midjourney"):
        c = candidate("File:Mount Tai sea of clouds.jpg", categories=[cat])
        assert fetch.score(c, "泰山", "Mount Tai") == -99, cat


def test_a_plain_photo_of_the_place_still_passes():
    """过滤器收紧了, 好图不能被误伤 —— 不然这条守线会逼着人把它放宽回去。"""
    c = candidate("File:Mount Tai 泰山 2007 075.jpg", desc="View from the summit",
                  categories=["Category:Mount Tai"])
    s = fetch.score(c, "泰山", "Mount Tai")
    assert s >= 4, f"这张图应当留下来, 实际打分 {s}"


def test_free_licences_are_still_required():
    assert fetch.score(candidate("File:Mount Tai.jpg", license="CC BY-NC 4.0"), "泰山", "Mount Tai") == -99
    assert fetch.score(candidate("File:Mount Tai.jpg", license="All rights reserved"), "泰山", "Mount Tai") == -99


def test_search_asks_commons_for_the_categories():
    """score() 只能判它拿到的东西: 不问类别, 上面那几条就都是空转。"""
    text = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r'"prop":\s*"imageinfo\|categories"', text), "search() 没向 Commons 要类别"
    assert '"cllimit"' in text
    assert '"categories":' in text, "候选里没有把类别带出来"


def test_the_artist_fallback_is_the_same_sentence_in_both_scripts():
    """抓图脚本与生成封面脚本各写一次兜底, 两处必须一模一样。

    不一样的话: 台账里是 A、落库的 credit 是 B, 声明页对着台账就核不上。
    Commons 上确实有文件没写作者(4a-beijing-041), 所以这句话一定会用上。
    """
    covers = (ROOT / "scripts" / "make_attraction_covers.py").read_text(encoding="utf-8")
    m = re.search(r'PHOTO_CREDIT_FALLBACK = "([^"]+)"', covers)
    assert m, "生成封面脚本里的 PHOTO_CREDIT_FALLBACK 换了写法, 用例该跟着改"
    assert fetch.ARTIST_FALLBACK == m.group(1)
    assert fetch.ARTIST_FALLBACK.strip()


def test_a_photo_of_somewhere_else_is_refused():
    """配错城市: 东莞市的展览馆抓到了天津规划展览馆 —— 名字能对上「展览馆」三个字。"""
    c = candidate("File:天津规划展览馆.jpg", desc="Tianjin Planning Exhibition Hall")
    assert fetch.score(c, "东莞市展览馆", "Dongguan Exhibition Hall", ("东莞", "广东")) == -99


def test_a_same_named_station_or_ship_is_refused():
    """同名车站与军舰: 陈家祠配成「陈家祠站台」, 长白山配成军舰 PLANS Changbai Mountain。"""
    for name in ("File:Chen Clan Academy Station Platforms.JPG",
                 "File:PLANS Changbai Mountain (LPD-989) 20150911.jpg",
                 "File:Wild Animal Park Station 20140221 142848.jpg"):
        assert fetch.score(candidate(name), "长白山", "Changbai Mountain") == -99, name


def test_a_place_name_inside_the_attraction_name_is_not_a_mismatch():
    """北京市中山公园景区 —— 文件名里的「中山」是景点自己名字的一部分, 不是中山市。"""
    c = candidate("File:中山公园 - panoramio (2).jpg", desc="Zhongshan Park, Beijing")
    assert fetch.score(c, "北京市中山公园景区", "Zhongshan Park Beijing", ("北京", "北京")) >= 4


def test_the_city_vocabulary_comes_from_the_official_list():
    """地名词表取自名录 CSV 的省市两列 —— 拿不到它, 「别的城市」这条就等于没写。"""
    toks = fetch.city_tokens()
    assert "东莞" in toks and "天津" in toks
    assert all(len(x) >= 2 for x in toks)

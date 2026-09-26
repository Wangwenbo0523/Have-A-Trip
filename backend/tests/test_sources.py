"""数据来源与许可声明页的接口。

这一页的价值全在「从数据库聚合」上 —— 一旦有人改成前端写死, 引入新来源时页面就会撒谎。
所以既查接口形状, 也查判定口径本身。
"""
from __future__ import annotations

import json
import pathlib
import re

from app.api import sources
from app.models import Attraction

API = "/api/v1"

ROOT = pathlib.Path(__file__).resolve().parents[2]
# 实拍照片的台账, 与由它生成的种子 SQL。两个都读, 是为了守住「台账里有的, 种子里也得有」
LEDGER = ROOT / "db" / "seed" / "photos.json"
IMAGES_SQL = ROOT / "db" / "seed" / "images.sql"


def get_json(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- 纯函数: 判定口径

def test_share_alike_detection_covers_real_world_spellings():
    """许可字符串是人写的, 同一份许可有好几种写法, 都得认出来。"""
    for text in ("ODbL 1.0", "ODbL-1.0", "CC BY-SA 4.0", "CC-BY-SA-4.0", "cc by-sa"):
        assert sources.is_share_alike(text) is True, text
    for text in ("MIT", "CC0 1.0", "CC BY 4.0", "Apache-2.0", ""):
        assert sources.is_share_alike(text) is False, text


def test_unregistered_share_alike_is_flagged_rather_than_assumed():
    """库里有 share-alike 来源却没登记改没改过时, 必须是 unregistered —— 宁可见红。"""
    assert sources.modification_of("OpenStreetMap", "ODbL 1.0") == "unregistered"
    assert sources.modification_of("Wikipedia", "CC BY-SA 4.0") == "unregistered"
    assert sources.modification_of("随便什么", "MIT") == "not-applicable"


# ---------------------------------------------------------------- 接口

def test_source_list_comes_from_the_database(client, seeded):
    body = get_json(client, f"{API}/sources")
    # 5 条已发布 + 1 条 draft。数字是 5 就说明 draft 没被算进去
    assert body["attraction_total"] == 5
    assert len(body["sources"]) == 1
    record = body["sources"][0]
    assert record["source"] == "测试夹具"
    assert record["license"] == "MIT"
    assert record["attraction_count"] == 5
    # 杭州(浙江)、北京、西安(陕西)、上海 —— draft 没有省份, 且不该被统计
    assert record["province_count"] == 4
    assert record["share_alike"] is False
    assert record["modification"] == "not-applicable"
    assert body["needs_attention"] is False


def test_no_images_yields_empty_list_not_a_placeholder_row(client, seeded):
    """一张图都没有时返回空数组。页面负责解释「为什么没有」, 接口不编造行。"""
    body = get_json(client, f"{API}/sources")
    assert body["images"] == []
    assert body["image_total"] == 0


def test_share_alike_source_flips_the_attention_flag(client, db_session, seeded):
    """真往库里放一条 ODbL 数据, 告警必须亮起来 —— 这是这一页存在的意义。"""
    db_session.add(
        Attraction(
            slug="osm-spot", name="OSM 来的景点", category_id=seeded["nature"].id,
            province="浙江省", city="杭州市", status="published",
            source="OpenStreetMap", license="ODbL 1.0",
        )
    )
    db_session.commit()

    body = get_json(client, f"{API}/sources")
    assert body["needs_attention"] is True
    assert body["attraction_total"] == 6
    osm = next(row for row in body["sources"] if row["source"] == "OpenStreetMap")
    assert osm["share_alike"] is True
    assert osm["modification"] == "unregistered"


def test_image_credits_are_aggregated(client, db_session, seeded):
    from app.models import AttractionImage

    db_session.add_all([
        AttractionImage(
            attraction_id=seeded["west_lake"].id, url="/img/a.jpg",
            credit="张三", license="CC0 1.0",
        ),
        AttractionImage(
            attraction_id=seeded["west_lake"].id, url="/img/b.jpg",
            credit="张三", license="CC0 1.0",
        ),
        AttractionImage(
            attraction_id=seeded["palace"].id, url="/img/c.jpg",
            credit="李四", license="CC BY 4.0",
        ),
    ])
    db_session.commit()

    body = get_json(client, f"{API}/sources")
    assert body["image_total"] == 3
    assert {(row["credit"], row["license"], row["image_count"]) for row in body["images"]} == {
        ("张三", "CC0 1.0", 2),
        ("李四", "CC BY 4.0", 1),
    }


def test_draft_attraction_images_stay_out_of_the_declaration(client, db_session, seeded):
    from app.models import AttractionImage

    db_session.add(
        AttractionImage(
            attraction_id=seeded["draft"].id, url="/img/draft.jpg",
            credit="不该出现", license="CC0 1.0",
        )
    )
    db_session.commit()

    body = get_json(client, f"{API}/sources")
    assert body["images"] == []


# ---------------------------------------------------------------- 逐图署名

def test_license_url_points_at_the_deed_not_at_a_guess():
    """许可 -> 许可全文地址。认不出来的返回 None —— 猜一个比不给链接更糟。"""
    assert sources.license_url("CC BY-SA 4.0") == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert sources.license_url("CC BY 3.0") == "https://creativecommons.org/licenses/by/3.0/"
    assert sources.license_url("CC0") == "https://creativecommons.org/publicdomain/zero/1.0/"
    assert (
        sources.license_url("CC BY-SA 3.0 igo")
        == "https://creativecommons.org/licenses/by-sa/3.0/igo/"
    )
    assert sources.license_url("MIT") == "https://opensource.org/license/mit"
    assert (
        sources.license_url("Public domain")
        == "https://commons.wikimedia.org/wiki/Commons:Public_domain"
    )
    # 编出来的 / 空的不给链接: 那一格宁可是纯文本, 也不要指向别的许可
    assert sources.license_url("随便写的许可") is None
    assert sources.license_url("") is None
    assert sources.license_url(None) is None


def test_every_license_in_use_has_a_deed_link():
    """库里出现过的许可写法都要能给出全文地址 —— 新写法忘了登记, 这条会红。"""
    licenses = {item["license"] for item in json.loads(LEDGER.read_text(encoding="utf-8"))}
    licenses.add("MIT")  # 自绘的那一批, 不经过台账
    assert sorted(text for text in licenses if sources.license_url(text) is None) == []


def test_image_modification_is_about_the_pipeline_not_the_license():
    """外部来源的图一律 modified: 抓的是 Commons 重渲染的缩略图, 页面上还裁过。

    CC BY 3.0 起就要求标注修改, 所以不能只在 share-alike 上标; 自绘图没有这个义务。
    """
    for text in ("CC BY-SA 4.0", "CC BY 3.0", "CC0", "Public domain"):
        assert sources.image_modification(text) == "modified", text
    assert sources.image_modification("MIT") == "not-applicable"


def test_every_photo_in_the_ledger_has_a_source_page():
    """署名要能追到出处: 台账里每条都得有 Commons 的文件页地址。"""
    items = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert items, "台账是空的, 这条守线就白写了"
    missing = [
        item["slug"]
        for item in items
        if not (item.get("source") or "").startswith("https://commons.wikimedia.org/")
    ]
    assert missing == []


def test_generated_images_sql_puts_the_source_page_on_photos_only():
    """生成的种子里: 照片行带来源页, 自绘行写 NULL(它没有外部来源, 不需要向谁署名)。"""
    rows = [
        line
        for line in IMAGES_SQL.read_text(encoding="utf-8").splitlines()
        if line.startswith("    ((SELECT id FROM attraction")
    ]
    photos = [line for line in rows if ".svg'" not in line]
    svgs = [line for line in rows if ".svg'" in line]
    assert len(photos) == len(json.loads(LEDGER.read_text(encoding="utf-8")))
    assert svgs, "自绘图那一批不见了?"
    for line in photos:
        assert re.search(r", 'https://commons\.wikimedia\.org/[^']+', 0\),?$", line), line
    for line in svgs:
        assert re.search(r", NULL, 0\),?$", line), line


# VALUES 行长这样: 一行一条 attraction_image, 第二个字段是站内路径。
# 用纯字符串切而不用正则: 行首那两个左括号在正则里要转义, 写错过一次。
ROW_PREFIX = "    ((SELECT id FROM attraction WHERE slug = '"


def _images_sql_urls() -> dict:
    """把 db/seed/images.sql 的 VALUES 行读成 {slug: url}。"""
    urls = {}
    for line in IMAGES_SQL.read_text(encoding="utf-8").splitlines():
        if not line.startswith(ROW_PREFIX):
            continue
        # slug 那一位外面还套着子查询的右括号: `... = 'west-lake'), '/images/...'`
        slug, rest = line[len(ROW_PREFIX):].split("'), '", 1)
        urls[slug] = rest.split("', '", 1)[0]
    return urls


def test_generated_images_sql_points_at_files_that_exist_on_disk():
    """种子里的每个配图 URL, 在磁盘上都得是同一个文件。

    这条盯的是**两处名字是否一致**。曾经这里是坏的: 照片的 URL 是拿 slug 拼死 .jpg 的,
    而抓取脚本与台账保留的是原图的真实后缀 —— 199 张里唯一那张 .jpeg(珠海市圆明新园)
    因此指着一个不存在的文件。更难发现的是它不报错: `backend/app/web.py` 对找不到的静态
    路径会回落 SPA 外壳, HTTP 照样 200, 浏览器里只是那张图空着。
    """
    rows = [
        line
        for line in IMAGES_SQL.read_text(encoding="utf-8").splitlines()
        if line.startswith("    ((SELECT id FROM attraction")
    ]
    urls = _images_sql_urls()
    assert len(urls) == len(rows), "有行没解析出 URL, 这条守线就等于没查"
    assert urls, "一条配图都没有?"
    missing = [
        url for url in urls.values()
        if not (ROOT / "frontend" / "public" / url.lstrip("/")).exists()
    ]
    assert missing == []


def test_photo_urls_use_the_filename_recorded_in_the_ledger():
    """照片行的 URL 必须用台账里记的那个文件名(带真实后缀), 不能拿 slug 另拼一个。

    允许的后缀就是抓取脚本肯写出来的那几个: Commons 缩略图地址的后缀 .jpg / .jpeg / .png。
    """
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    urls = _images_sql_urls()
    wrong = [
        item["slug"] for item in ledger
        if urls.get(item["slug"]) != "/images/covers/" + item["photo"]
    ]
    assert wrong == []
    suffix = {pathlib.PurePosixPath(urls[item["slug"]]).suffix for item in ledger}
    assert suffix <= {".jpg", ".jpeg", ".png"}, suffix


def test_attributions_come_out_one_row_per_image_that_has_a_source(client, db_session, seeded):
    """有来源页的图逐张列出来: 聚合行说不清是哪一张, 也说不出出处。"""
    from app.models import AttractionImage

    db_session.add_all([
        AttractionImage(
            attraction_id=seeded["west_lake"].id, url="/images/covers/west-lake.jpg",
            caption="#001 · West Lake.jpg", credit="张三", license="CC BY-SA 4.0",
            source_url="https://commons.wikimedia.org/wiki/File:West_Lake.jpg",
        ),
        # 自绘图没有外部来源, 不该出现在逐图署名里
        AttractionImage(
            attraction_id=seeded["palace"].id, url="/images/covers/palace.svg",
            caption="自绘示意图", credit="Have-A-Trip 自绘", license="MIT",
        ),
    ])
    db_session.commit()

    body = get_json(client, f"{API}/sources")
    assert len(body["attributions"]) == 1
    row = body["attributions"][0]
    assert row["attraction_slug"] == "west-lake"
    assert row["caption"] == "#001 · West Lake.jpg"
    assert row["credit"] == "张三"
    assert row["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert row["source_url"] == "https://commons.wikimedia.org/wiki/File:West_Lake.jpg"
    assert row["modification"] == "modified"
    # 聚合口径没变: 两张图都还在 image_total 里, 只是聚合那一栏不逐张列
    assert body["image_total"] == 2
    assert {item["license_url"] for item in body["images"]} == {
        "https://creativecommons.org/licenses/by-sa/4.0/",
        "https://opensource.org/license/mit",
    }


def test_draft_attraction_photos_are_not_attributed(client, db_session, seeded):
    """下架景点的照片一样不许署到声明页上 —— 这一页只说「我们用了什么」。"""
    from app.models import AttractionImage

    db_session.add(
        AttractionImage(
            attraction_id=seeded["draft"].id, url="/images/covers/draft.jpg",
            credit="不该出现", license="CC BY 4.0",
            source_url="https://commons.wikimedia.org/wiki/File:Draft.jpg",
        )
    )
    db_session.commit()

    body = get_json(client, f"{API}/sources")
    assert body["attributions"] == []

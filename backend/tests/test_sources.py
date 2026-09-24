"""数据来源与许可声明页的接口。

这一页的价值全在「从数据库聚合」上 —— 一旦有人改成前端写死, 引入新来源时页面就会撒谎。
所以既查接口形状, 也查判定口径本身。
"""
from __future__ import annotations

from app.api import sources
from app.models import Attraction

API = "/api/v1"


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

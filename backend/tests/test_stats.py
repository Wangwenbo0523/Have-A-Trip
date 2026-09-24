"""景点库总览看板的接口。

看板最容易出的错是**口径漂移**: 把草稿算进来、把下架景点的配图算进来、或者把
「未核实」的景点从分布里丢掉。这几种错都不会抛异常, 只会让页面上的数字悄悄变假,
所以这里逐个数字对, 不只查形状。
"""
from __future__ import annotations

from app.models import Attraction, AttractionImage, AttractionPlan

API = "/api/v1"


def get_json(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def keys_of(body: dict, field: str) -> list[str]:
    return [item["key"] for item in body[field]]


def count_of(body: dict, field: str, key: str) -> int:
    return next(item["count"] for item in body[field] if item["key"] == key)


# ---------------------------------------------------------------- 总数

def test_totals_only_count_published_attractions(client, seeded):
    body = get_json(client, f"{API}/stats")
    # 5 条已发布 + 1 条 draft。数字是 5 就说明 draft 没被算进去
    assert body["attraction_total"] == 5
    # 杭州(浙江)、北京、西安(陕西)、上海 —— draft 没有省份, 也不该被统计
    assert body["province_total"] == 4
    assert body["image_total"] == 0
    assert body["plan_total"] == 0


# ---------------------------------------------------------------- 分布

def test_country_split_follows_country_code(client, seeded):
    body = get_json(client, f"{API}/stats")
    assert body["by_country"] == [{"key": "CN", "label": "CN", "count": 5}]


def test_missing_grade_lands_in_unknown_instead_of_being_dropped(client, seeded):
    """夹具里没有一条填了等级。这些景点必须落在 unknown 档, 不能被丢掉 ——
    丢掉的后果是各档之和小于总数, 看板上会凭空少掉几十个景点。"""
    body = get_json(client, f"{API}/stats")
    assert keys_of(body, "by_a_level") == ["unknown"]
    assert keys_of(body, "by_heritage") == ["unknown"]
    for field in ("by_a_level", "by_heritage", "by_country", "by_category"):
        assert sum(item["count"] for item in body[field]) == body["attraction_total"], field


def test_category_distribution_counts_published_per_category(client, seeded):
    body = get_json(client, f"{API}/stats")
    # 历史古迹有两条(兵马俑、灵隐寺), 其余分类各一条。数量降序, 同数量按 slug 升序
    assert keys_of(body, "by_category") == ["history", "museum", "nature", "theme-park"]
    assert count_of(body, "by_category", "history") == 2
    # label 是库里的分类名, 不是 slug —— 它是内容, 前端直接显示
    history = next(item for item in body["by_category"] if item["key"] == "history")
    assert history["label"] == "历史古迹"


def test_a_level_heritage_and_country_are_aggregated(client, db_session, seeded):
    db_session.add_all([
        Attraction(
            slug="great-wall", name="八达岭长城", category_id=seeded["history"].id,
            province="北京市", city="北京市", status="published",
            source="测试夹具", license="MIT", a_level="5A",
        ),
        Attraction(
            slug="kyoto-temple", name="清水寺", category_id=seeded["history"].id,
            country_code="JP", city="京都", status="published",
            source="测试夹具", license="MIT", heritage="cultural",
        ),
    ])
    db_session.commit()

    body = get_json(client, f"{API}/stats")
    assert body["attraction_total"] == 7
    assert count_of(body, "by_a_level", "5A") == 1
    # 没填等级的 6 条仍在, 一档都没少
    assert count_of(body, "by_a_level", "unknown") == 6
    assert count_of(body, "by_heritage", "cultural") == 1
    assert {item["key"]: item["count"] for item in body["by_country"]} == {"CN": 6, "JP": 1}


# ---------------------------------------------------------------- 与声明页同口径

def test_source_section_reuses_the_declaration_page_aggregation(client, seeded):
    """看板上的来源分布与 /sources 必须是同一份 —— 两处各算一套, 就没人知道该信哪个。"""
    body = get_json(client, f"{API}/stats")
    declaration = get_json(client, f"{API}/sources")
    assert body["sources"] == declaration["sources"]
    assert body["needs_attention"] == declaration["needs_attention"]
    assert declaration["needs_attention"] is False


def test_share_alike_source_flips_the_flag_on_the_dashboard(client, db_session, seeded):
    """真往库里放一条 ODbL 数据, 看板与声明页要同时亮 —— 两边看的是同一份聚合。"""
    db_session.add(
        Attraction(
            slug="osm-spot", name="OSM 来的景点", category_id=seeded["nature"].id,
            province="浙江省", city="杭州市", status="published",
            source="OpenStreetMap", license="ODbL 1.0",
        )
    )
    db_session.commit()

    body = get_json(client, f"{API}/stats")
    assert body["needs_attention"] is True
    assert body["attraction_total"] == 6
    osm = next(item for item in body["sources"] if item["source"] == "OpenStreetMap")
    assert osm["modification"] == "unregistered"


def test_published_images_and_plans_are_counted(client, db_session, seeded):
    db_session.add_all([
        AttractionImage(
            attraction_id=seeded["west_lake"].id, url="/img/1.jpg",
            credit="张三", license="CC0 1.0",
        ),
        AttractionImage(
            attraction_id=seeded["palace"].id, url="/img/2.jpg",
            credit="张三", license="CC0 1.0",
        ),
        AttractionPlan(
            attraction_id=seeded["west_lake"].id, slug="west-lake-day", title="西湖一日",
            summary="沿湖走一圈", source="测试夹具", license="MIT",
        ),
    ])
    db_session.commit()

    body = get_json(client, f"{API}/stats")
    assert body["image_total"] == 2
    assert body["plan_total"] == 1


def test_drafts_and_archived_stay_out_of_every_number(client, db_session, seeded):
    """下架景点连同它的配图与方案都不进统计。看板说的是「对外提供了什么」。"""
    archived = Attraction(
        slug="closed-spot", name="已下架景点", category_id=seeded["nature"].id,
        province="浙江省", city="杭州市", status="archived",
        source="测试夹具", license="MIT", a_level="5A",
    )
    db_session.add(archived)
    db_session.flush()
    db_session.add_all([
        AttractionImage(
            attraction_id=archived.id, url="/img/gone.jpg",
            credit="不该出现", license="CC0 1.0",
        ),
        AttractionImage(
            attraction_id=seeded["draft"].id, url="/img/draft.jpg",
            credit="不该出现", license="CC0 1.0",
        ),
        AttractionPlan(
            attraction_id=archived.id, slug="closed-day", title="下架方案",
            summary="不该出现", source="测试夹具", license="MIT",
        ),
    ])
    db_session.commit()

    body = get_json(client, f"{API}/stats")
    assert body["attraction_total"] == 5
    assert body["image_total"] == 0
    assert body["plan_total"] == 0
    assert keys_of(body, "by_a_level") == ["unknown"]

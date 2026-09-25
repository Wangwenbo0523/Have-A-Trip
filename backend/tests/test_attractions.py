"""景点列表 / 详情 / 相似推荐 / 就近推荐。"""
from __future__ import annotations

import pytest

from app.config import Settings, get_settings
from app.geo import ip_locate
from app.main import app
from app.models import Attraction

API = "/api/v1"


def get_json(client, path, **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_only_published_is_listed(client, seeded):
    body = get_json(client, f"{API}/attractions")
    assert body["total"] == 5
    slugs = {item["slug"] for item in body["items"]}
    assert "draft-spot" not in slugs


def test_item_shape(client, seeded):
    body = get_json(client, f"{API}/attractions")
    item = next(i for i in body["items"] if i["slug"] == "west-lake")
    assert item["category"] == {"slug": "nature", "name": "自然风光"}
    assert {t["slug"] for t in item["tags"]} == {"free", "world-heritage"}
    assert "description" not in item  # 列表刻意不带长文本
    assert item["rating_avg"] == 4.7
    assert item["ticket_price"] == 0.0


def test_pagination_is_stable_and_disjoint(client, seeded):
    first = get_json(client, f"{API}/attractions", page=1, size=2)
    second = get_json(client, f"{API}/attractions", page=2, size=2)
    assert len(first["items"]) == 2 and len(second["items"]) == 2
    assert {i["id"] for i in first["items"]}.isdisjoint({i["id"] for i in second["items"]})
    assert get_json(client, f"{API}/attractions", page=1, size=2)["items"] == first["items"]


def test_page_beyond_end_is_empty_not_error(client, seeded):
    body = get_json(client, f"{API}/attractions", page=99, size=20)
    assert body["items"] == []
    assert body["total"] == 5


def test_size_is_capped(client, seeded):
    assert get_json(client, f"{API}/attractions", size=9999)["size"] == 100


def test_filter_by_category(client, seeded):
    body = get_json(client, f"{API}/attractions", category="history")
    assert {i["slug"] for i in body["items"]} == {"terracotta-army", "lingyin-temple"}


def test_filter_by_city(client, seeded):
    body = get_json(client, f"{API}/attractions", city="杭州市")
    assert {i["slug"] for i in body["items"]} == {"west-lake", "lingyin-temple"}


def test_filter_by_tag(client, seeded):
    body = get_json(client, f"{API}/attractions", tag="free")
    assert {i["slug"] for i in body["items"]} == {"west-lake", "lingyin-temple"}


def test_filters_combine(client, seeded):
    body = get_json(client, f"{API}/attractions", city="杭州市", tag="world-heritage")
    assert {i["slug"] for i in body["items"]} == {"west-lake"}


def test_search_matches_name(client, seeded):
    body = get_json(client, f"{API}/attractions", q="西")
    assert {i["slug"] for i in body["items"]} == {"west-lake"}


def test_search_matches_summary(client, seeded):
    body = get_json(client, f"{API}/attractions", q="杭州")
    assert {i["slug"] for i in body["items"]} == {"lingyin-temple"}


def test_search_is_case_insensitive_on_latin(client, seeded):
    assert get_json(client, f"{API}/attractions", q="WEST LAKE")["total"] == 1


def test_search_no_hit(client, seeded):
    body = get_json(client, f"{API}/attractions", q="不存在的关键字")
    assert body["total"] == 0 and body["items"] == []


def test_sort_by_rating(client, seeded):
    names = [i["slug"] for i in get_json(client, f"{API}/attractions", sort="rating")["items"]]
    assert names == [
        "palace-museum", "west-lake", "terracotta-army", "lingyin-temple", "ocean-world",
    ]


def test_detail_by_slug_and_by_id(client, seeded):
    by_slug = get_json(client, f"{API}/attractions/west-lake")
    by_id = get_json(client, f"{API}/attractions/{seeded['west_lake'].id}")
    assert by_slug["id"] == by_id["id"] == seeded["west_lake"].id
    assert by_slug["description"] == "位于杭州城西。"
    assert by_slug["source"] and by_slug["license"]


def test_detail_404_for_unknown(client, seeded):
    assert client.get(f"{API}/attractions/nope").status_code == 404


def test_detail_404_for_draft(client, seeded):
    assert client.get(f"{API}/attractions/draft-spot").status_code == 404


def test_detail_404_for_draft_by_id(client, seeded):
    assert client.get(f"{API}/attractions/{seeded['draft'].id}").status_code == 404


# ------------------------------------------------------------ 随机抽取(首页弹窗)

def test_random_is_not_swallowed_by_the_detail_route(client, seeded):
    """路由顺序的回归护栏: /random 必须排在 /{id_or_slug} 前面。

    排到后面的话会被详情路由先接走 —— 它把 "random" 当 slug 查一次, 然后 404。
    """
    response = client.get(f"{API}/attractions/random")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 3


def test_random_returns_published_only_and_without_duplicates(client, seeded):
    """随机不该把 draft 抽出来, 也不该同一条重复出现。"""
    for _ in range(10):
        body = get_json(client, f"{API}/attractions/random", limit=3)
        ids = [item["id"] for item in body]
        assert len(ids) == 3
        assert len(set(ids)) == 3, "同一个景点在一批里出现两次就不叫三个地方了"
        assert seeded["draft"].id not in ids


def test_random_is_actually_random(client, seeded):
    """同一组参数连着调, 抽到的组合必须会变 —— 否则「随机」只是个幌子。

    已发布 5 条里抽 3 条有 10 种组合, 30 次全抽到同一组的概率是 (1/10)^29, 可以忽略。
    """
    seen = {
        tuple(sorted(item["id"] for item in get_json(client, f"{API}/attractions/random", limit=3)))
        for _ in range(30)
    }
    assert len(seen) > 1


def test_random_declares_itself_uncacheable(client, seeded):
    """被任何一层缓存按住, 随机就成了固定 —— 响应上必须说明。"""
    response = client.get(f"{API}/attractions/random")
    assert "no-store" in response.headers["cache-control"]


def test_random_limit_is_bounded(client, seeded):
    assert client.get(f"{API}/attractions/random", params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/attractions/random", params={"limit": 13}).status_code == 422


def test_random_returns_the_whole_catalogue_when_limit_exceeds_it(client, seeded):
    body = get_json(client, f"{API}/attractions/random", limit=12)
    assert len(body) == 5, "只有 5 条已发布, 要 12 条就给 5 条, 不报错也不重复"
    assert len({item["id"] for item in body}) == 5

def test_similar_is_deterministic_and_relevant(client, seeded):
    body = get_json(client, f"{API}/attractions/west-lake/similar")
    slugs = [i["slug"] for i in body]
    # lingyin 同城 + 共享 free 标签排第一, 然后是共享 world-heritage 的故宫与兵马俑
    assert slugs == ["lingyin-temple", "palace-museum", "terracotta-army"]
    assert "west-lake" not in slugs
    assert get_json(client, f"{API}/attractions/west-lake/similar") == body


def test_similar_respects_limit(client, seeded):
    assert len(get_json(client, f"{API}/attractions/west-lake/similar", limit=2)) == 2


def test_similar_404(client, seeded):
    assert client.get(f"{API}/attractions/nope/similar").status_code == 404


def test_categories_carry_published_counts(client, seeded):
    body = get_json(client, f"{API}/categories")
    counts = {c["slug"]: c["attraction_count"] for c in body}
    assert counts == {"nature": 1, "museum": 1, "history": 2, "theme-park": 1}  # draft 不计入
    assert [c["slug"] for c in body] == ["nature", "museum", "history", "theme-park"]  # 按 sort


def test_tags_only_include_ones_with_attractions(client, seeded):
    body = get_json(client, f"{API}/tags")
    counts = {t["slug"]: t["attraction_count"] for t in body}
    assert counts == {"world-heritage": 3, "free": 2, "family": 2}


# ------------------------------------------------------- 就近推荐(首页「出去走走」)

@pytest.fixture()
def from_hangzhou(monkeypatch):
    """把归属地那一层换成「访问者在杭州」, 并断掉网络。

    正常这条路径读的是真 Request 的对端地址, 而 TestClient 的对端是 "testclient"
    (不是 IP); 而且默认配置是 GEO_IP_PROVIDER=none, 压根不问。所以不把这两处都换掉,
    就近那几条路永远跑不到。
    """
    def install(payload, *, peer="223.5.5.5"):
        app.dependency_overrides[get_settings] = lambda: Settings(geo_ip_provider="ipapi")
        monkeypatch.setattr(ip_locate, "client_ip", lambda request, settings: peer)
        monkeypatch.setattr(ip_locate, "fetch_json", lambda url, *, headers, timeout: payload)
        return payload
    yield install
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture()
def no_lookup(monkeypatch):
    """装上「谁敢发网络请求就炸」的打桩。"""
    def fake(url, *, headers, timeout):
        raise AssertionError(f"这条路径不该发外部请求, 却去问了 {url}")
    monkeypatch.setattr(ip_locate, "fetch_json", fake)


def attr(payload):
    """ip-api 认出来时的回答。"""
    return {"status": "success", "countryCode": "CN", **payload}


def test_nearby_is_not_swallowed_by_the_detail_route(client, seeded):
    """路由顺序的回归护栏: /nearby 必须排在 /{id_or_slug} 前面。"""
    response = client.get(f"{API}/attractions/nearby")
    assert response.status_code == 200, response.text
    assert "items" in response.json()


def test_nearby_without_a_location_still_returns_three(client, seeded, no_lookup):
    """认不出你在哪儿也照常给三个国内随机, 但必须如实说清楚 —— 不假装就近。"""
    body = get_json(client, f"{API}/attractions/nearby")
    assert len(body["items"]) == 3
    assert body["located"] is False
    assert body["scope"] == "nation"
    assert body["city"] is None and body["region"] is None


def test_nearby_declares_itself_uncacheable(client, seeded):
    response = client.get(f"{API}/attractions/nearby")
    assert "no-store" in response.headers["cache-control"]


def test_nearby_prefers_the_same_city(client, seeded, from_hangzhou):
    """杭州有 2 条, 要 2 条时就该是这两个 —— 而且报出来的位置是库内写法。"""
    from_hangzhou(attr({"city": "杭州", "regionName": "浙江"}))
    body = get_json(client, f"{API}/attractions/nearby", limit=2)
    assert body["located"] is True
    assert (body["city"], body["region"]) == ("杭州市", "浙江省")
    assert body["scope"] == "city"
    assert {item["slug"] for item in body["items"]} == {"west-lake", "lingyin-temple"}


def test_nearby_puts_the_near_ones_first(client, seeded, from_hangzhou):
    """要 3 条而杭州只有 2 条: 前两条必须是杭州的, 第三条才是全国补的。"""
    from_hangzhou(attr({"city": "杭州", "regionName": "浙江"}))
    slugs = [item["slug"] for item in get_json(client, f"{API}/attractions/nearby")["items"]]
    assert set(slugs[:2]) == {"west-lake", "lingyin-temple"}, "同城的必须排在前面"
    assert len(slugs) == 3 and len(set(slugs)) == 3
    assert get_json(client, f"{API}/attractions/nearby")["scope"] == "nation", (
        "掺进了全国随机就不是纯就近, 不能报 city"
    )


def test_nearby_fills_from_the_same_province(client, seeded, db_session, from_hangzhou):
    """同城不够时先用同省补, 而不是直接跳到全国。"""
    db_session.add(
        Attraction(
            slug="tianyi-pavilion", name="天一阁", category_id=seeded["history"].id,
            province="浙江省", city="宁波市",
            status="published", source="测试夹具", license="MIT",
        )
    )
    db_session.commit()
    from_hangzhou(attr({"city": "杭州", "regionName": "浙江"}))

    body = get_json(client, f"{API}/attractions/nearby")
    assert body["scope"] == "region"
    slugs = [item["slug"] for item in body["items"]]
    assert set(slugs[:2]) == {"west-lake", "lingyin-temple"}
    assert slugs[2] == "tianyi-pavilion"


def test_nearby_survives_a_city_the_catalogue_does_not_have(client, seeded, from_hangzhou):
    """认出了位置、库里却没有这个城市: 照样三个, 但 located 只能是 false。"""
    from_hangzhou(attr({"city": "洛阳市", "regionName": "河南省"}))
    body = get_json(client, f"{API}/attractions/nearby")
    assert body["located"] is False
    assert body["scope"] == "nation"
    assert len(body["items"]) == 3


def test_nearby_never_returns_a_draft_or_a_duplicate(client, seeded, from_hangzhou):
    from_hangzhou(attr({"city": "杭州", "regionName": "浙江"}))
    for _ in range(10):
        body = get_json(client, f"{API}/attractions/nearby", limit=12)
        ids = [item["id"] for item in body["items"]]
        assert len(ids) == len(set(ids)), "同一个景点在一批里出现两次就不叫三个地方了"
        assert len(ids) == 5, "只有 5 条已发布, 要 12 条就给 5 条"
        assert seeded["draft"].id not in ids


def test_nearby_the_national_fill_is_still_random(client, seeded, from_hangzhou):
    """同城那两条是固定的(库里就两条), 补的第 3 条得会变 —— 否则「换一批」没意义。"""
    from_hangzhou(attr({"city": "杭州", "regionName": "浙江"}))
    seen = {
        tuple(
            sorted(
                item["slug"]
                for item in get_json(client, f"{API}/attractions/nearby")["items"]
            )
        )
        for _ in range(30)
    }
    assert len(seen) > 1


def add_overseas(db_session, seeded, *, slug="banff", country="CA"):
    """加一条境外景点。默认夹具那 5 条全是 CN, 不补一条就测不到「境外会不会掺进来」。"""
    spot = Attraction(
        slug=slug, name="班夫国家公园", category_id=seeded["nature"].id,
        city="班夫", province="阿尔伯塔省", country_code=country,
        status="published", source="测试夹具", license="MIT",
    )
    db_session.add(spot)
    db_session.commit()
    return spot


def test_nearby_fills_within_the_home_country_not_the_whole_world(
    client, seeded, db_session, no_lookup
):
    """第三级是「国内」不是「全世界」。

    库里 1385 条已发布有 40 条在境外, 不按国别收口的话一次要三个会掺进境外景点 ——
    首页第一屏推一张去加拿大的机票说不通(真实库里这个概率只有百分之几, 夹具把它放大到
    5/6)。这里国内 5 条、境外 1 条, 每轮要 5 条,
    跑 20 轮: 国内正好够用, 境外那条一次都不该进来(不加国别过滤时每轮都有 5/6 的概率
    抽到它, 20 轮全躲开的可能小于亿分之一 —— 这条用例不是摆设)。
    """
    add_overseas(db_session, seeded)
    for _ in range(20):
        body = get_json(client, f"{API}/attractions/nearby", limit=5)
        slugs = {item["slug"] for item in body["items"]}
        assert body["scope"] == "nation"
        assert "banff" not in slugs, "国内还有得抽的时候不该掺境外景点"
        assert len(slugs) == 5


def test_nearby_falls_back_to_the_whole_catalogue_when_home_is_not_enough(
    client, seeded, db_session, no_lookup
):
    """国内凑不满才轮到第四级, 而且要如实把 scope 改成 world。"""
    add_overseas(db_session, seeded)
    body = get_json(client, f"{API}/attractions/nearby", limit=6)
    slugs = [item["slug"] for item in body["items"]]
    assert body["scope"] == "world"
    assert len(slugs) == 6
    assert slugs[-1] == "banff", "境外的只能补在最后, 不能挤到前面的就近位"


def test_nearby_does_not_claim_home_for_a_visitor_abroad(client, seeded, db_session, from_hangzhou):
    """访客已知在境外时**跳过**「国内」这一级。

    那边每个国家库内只有一两条(见 /stats 的 by_country), 按国别抽等于把「就近」变成
    「就那一条」; 直接走全部随机更诚实, 页面上也会说「从全部景点里抽的」而不是「国内」。
    """
    add_overseas(db_session, seeded)
    from_hangzhou(attr({"city": "巴黎", "regionName": "法兰西岛", "countryCode": "FR"}))
    body = get_json(client, f"{API}/attractions/nearby", limit=2)
    assert body["located"] is False
    assert body["scope"] == "world", "要是还先抽国内, 这两条就会全是 CN 并报成 nation"


def test_nearby_limit_is_bounded(client, seeded):
    assert client.get(f"{API}/attractions/nearby", params={"limit": 0}).status_code == 422
    assert client.get(f"{API}/attractions/nearby", params={"limit": 13}).status_code == 422

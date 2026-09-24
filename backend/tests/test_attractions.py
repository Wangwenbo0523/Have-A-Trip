"""景点列表 / 详情 / 相似推荐。"""
from __future__ import annotations

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

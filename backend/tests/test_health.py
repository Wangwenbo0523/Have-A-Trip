"""健康检查与 OpenAPI 契约。"""
from __future__ import annotations

API = "/api/v1"


def test_healthz(client):
    response = client.get(f"{API}/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]


def test_openapi_has_expected_paths(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        f"{API}/healthz",
        f"{API}/attractions",
        f"{API}/attractions/{{id_or_slug}}",
        f"{API}/attractions/{{id_or_slug}}/similar",
        f"{API}/categories",
        f"{API}/tags",
        f"{API}/sources",
        f"{API}/events",
    } <= paths


def test_no_map_or_geolocation_fields(client):
    """硬约束: API 不暴露任何轨迹/定位相关的入参。"""
    spec = client.get("/openapi.json").json()
    text = str(spec).lower()
    for word in ("geolocation", "latitude_only", "track", "route", "gps"):
        assert word not in text, f"OpenAPI 里出现了 {word}"

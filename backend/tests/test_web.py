"""单进程静态层(app/web.py): 默认不改变任何行为, 开了之后才接管 / 与静态文件。"""
from __future__ import annotations

import pytest

from app.config import Settings, get_settings
from app.main import app

API = "/api/v1"


@pytest.fixture()
def dist(tmp_path):
    """一个像 frontend/dist 的产物目录, 上一级摆一份「不该被读到的」package.json。"""
    build = tmp_path / "frontend" / "dist"
    (build / "assets").mkdir(parents=True)
    (build / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (build / "images" / "covers").mkdir(parents=True)
    (build / "images" / "covers" / "west-lake.svg").write_text("<svg/>", encoding="utf-8")
    (build / "index.html").write_text("<!doctype html><title>damo</title>", encoding="utf-8")
    (tmp_path / "frontend" / "package.json").write_text(
        '{"devDependencies": {"vite": "1.0.0"}}', encoding="utf-8"
    )
    return build


@pytest.fixture()
def serving(dist):
    """打开静态层, 指向临时产物目录。"""
    app.dependency_overrides[get_settings] = lambda: Settings(
        serve_frontend=True, frontend_dist=str(dist)
    )
    yield dist
    app.dependency_overrides.pop(get_settings, None)

# ------------------------------------------------------------------ 默认关闭时

def test_root_still_describes_the_api_when_the_static_layer_is_off(client):
    """默认配置下 "/" 还是那份 API 自述 —— 不给别人的部署换首页。"""
    body = client.get("/").json()
    assert body["api"] == API
    assert "version" in body


def test_unknown_paths_are_still_404_json_when_off(client):
    response = client.get("/attraction/west-lake")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


def test_index_is_not_served_when_off_even_if_dist_exists(client, dist):
    """产物在那儿也不算数: 开不开只看 SERVE_FRONTEND。"""
    assert (dist / "index.html").is_file()
    assert client.get("/").headers["content-type"].startswith("application/json")

# ------------------------------------------------------------------ 开了之后

def test_root_serves_the_app_shell(client, serving):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "damo" in response.text
    # 首页是壳, 必须每次回源: 缓存住就换不掉前端了
    assert response.headers["cache-control"] == "no-store"


def test_assets_are_cached_hard(client, serving):
    """vite 产物名里有内容哈希, 可以长缓存。"""
    response = client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]


def test_public_files_are_served(client, serving):
    """public/ 下的图标与封面在产物根目录, 不是只在 /assets 里。"""
    response = client.get("/images/covers/west-lake.svg")
    assert response.status_code == 200
    assert "<svg/>" in response.text


def test_unknown_path_falls_back_to_index(client, serving):
    """SPA 回落: 刷新 /attraction/<slug> 不能 404。"""
    response = client.get("/attraction/west-lake")
    assert response.status_code == 200
    assert "damo" in response.text
    assert response.headers["cache-control"] == "no-store"

def test_api_paths_are_never_swallowed_by_the_shell(client, seeded, serving):
    """动态路由优先。真把 HTML 回给一个 fetch, 前端只会报 JSON.parse 错。"""
    assert client.get(f"{API}/attractions").status_code == 200
    unknown = client.get(f"{API}/nope")
    assert unknown.status_code == 404
    assert unknown.headers["content-type"].startswith("application/json")
    assert "damo" not in unknown.text


def test_docs_and_openapi_survive(client, serving):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200

def test_path_traversal_is_refused(client, serving):
    """拼出来的路径必须仍在 dist 里。

    靶子是 dist 上一级那份 package.json: 少了那道检查就会把它原样吐出来(实测过),
    而真实的 frontend/dist 上一级正好就是 package.json。用 %2e%2e 这种写法是因为
    字面的 ../ 会被 HTTP 客户端先规范化掉, 到不了服务端。
    """
    for target in ("/%2e%2e/package.json", "/..%2fpackage.json", "/assets/..%2f..%2fpackage.json"):
        response = client.get(target)
        assert "devDependencies" not in response.text, target + " 读到 dist 之外的文件了"
        assert "damo" in response.text, target + " 该回落到 SPA 壳"


def test_a_missing_build_does_not_turn_into_a_blank_404(client, tmp_path):
    """开了开关但没 build: "/" 老老实实给 API 自述, 而不是空白页。"""
    missing = str(tmp_path / "not-built-yet")
    app.dependency_overrides[get_settings] = lambda: Settings(
        serve_frontend=True, frontend_dist=missing
    )
    try:
        assert client.get("/").headers["content-type"].startswith("application/json")
        assert client.get("/attraction/west-lake").status_code == 404
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_frontend_dist_defaults_to_the_repo_not_the_cwd(monkeypatch, tmp_path):
    """默认产物路径按文件位置算: 从别处启动后端也要找得到。"""
    monkeypatch.chdir(tmp_path)
    path = Settings().frontend_dist_path
    assert path.name == "dist"
    assert path.parent.name == "frontend"
    assert path.parent.parent.joinpath("backend", "app", "main.py").is_file()

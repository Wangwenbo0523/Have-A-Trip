"""按 IP 猜归属地这一层。

全程离线: 唯一发网络请求的 fetch_json 在每个用例里都被打桩, 所以跑测试不会去问
ip-api, 也不会因为「今天网断了」而时红时绿。
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_db
from app.geo import ip_locate
from app.main import app
from app.models import Attraction

API = "/api/v1"


def settings(**overrides) -> Settings:
    """显式给 geo_* 每一项, 免得本机环境变量或 .env 漏进来。"""
    base = {
        "geo_ip_provider": "none",
        "geo_ip_base_url": "",
        "geo_ip_api_key": "",
        "geo_ip_timeout_seconds": 1.5,
        "geo_trust_forwarded_for": False,
    }
    return Settings(**{**base, **overrides})


def request_from(peer, forwarded=None):
    """client_ip 只碰 headers 与 client.host 两处, 为这两行起一个真 Request 不值当。"""
    return SimpleNamespace(
        client=SimpleNamespace(host=peer) if peer else None,
        headers={"x-forwarded-for": forwarded} if forwarded else {},
    )


def stub_lookup(monkeypatch, payload, calls=None):
    """把网络那一层换成固定回答, 并记下问了哪些 url / 带了什么头。"""
    seen: list[tuple[str, dict[str, str], float]] = [] if calls is None else calls

    def fake_fetch(url, *, headers, timeout):
        seen.append((url, headers, timeout))
        if isinstance(payload, Exception):
            raise payload
        return payload

    monkeypatch.setattr(ip_locate, "fetch_json", fake_fetch)
    return seen


def refuse_to_ask(monkeypatch):
    """装上「谁敢发网络请求就炸」的打桩, 用来证明某条路径一个包都没发。"""

    def fake_fetch(url, *, headers, timeout):
        raise AssertionError(f"这条路径不该发外部请求, 却去问了 {url}")

    monkeypatch.setattr(ip_locate, "fetch_json", fake_fetch)


# --------------------------------------------------------------- 写法归一化

def test_normalize_matches_catalogue_spellings():
    """服务给的「杭州」和库里的「杭州市」得能对上 —— 这是这一层存在的理由。"""
    assert ip_locate.normalize_place("杭州市") == "杭州"
    assert ip_locate.normalize_place("杭州") == "杭州"
    assert ip_locate.normalize_place("浙江省") == "浙江"
    assert ip_locate.normalize_place("山东") == "山东"
    assert ip_locate.normalize_place("内蒙古自治区") == "内蒙古"
    assert ip_locate.normalize_place("香港特别行政区") == "香港"
    assert ip_locate.normalize_place("阿勒泰地区") == "阿勒泰"
    assert ip_locate.normalize_place("花莲县") == "花莲"


def test_normalize_leaves_places_whose_name_ends_in_zhou_alone():
    """回归护栏: 「州」不能当后缀剥。

    库里的「苏州市」剥掉「市」就已经是全名, 而 ip-api 给的正是没后缀的「苏州」;
    两边如果都再剥一次「州」, 得到的是「苏」, 反而对不上。
    """
    assert ip_locate.normalize_place("苏州") == "苏州"
    assert ip_locate.normalize_place("苏州市") == "苏州"
    assert ip_locate.normalize_place("广州市") == "广州"
    # 直辖市的区不改写: 对不上就退回省级, 不拿「去掉区字」去硬凑
    assert ip_locate.normalize_place("西城区") == "西城区"


def test_normalize_handles_blank_and_latin():
    assert ip_locate.normalize_place(None) is None
    assert ip_locate.normalize_place("   ") is None
    assert ip_locate.normalize_place(" 杭州 ") == "杭州"
    assert ip_locate.normalize_place("Ashburn") == "ashburn"


# ------------------------------------------------------------------- 取地址

@pytest.mark.parametrize(
    "address",
    [
        "223.5.5.5",
        "114.114.114.114",
        "2001:4860:4860::8888",
    ],
)
def test_public_addresses_are_worth_asking_about(address):
    assert ip_locate.is_public_ip(address) is True


@pytest.mark.parametrize(
    "address",
    [
        None,
        "",
        "testclient",  # TestClient 的默认对端, 不是 IP
        "1.2.3.4.5",
        "127.0.0.1",
        "::1",
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.10",
        "169.254.10.1",
        "100.64.0.1",  # 运营商级 NAT: 不是 private, 但同样不该送出去
        "0.0.0.0",
        "224.0.0.1",
    ],
)
def test_everything_else_is_left_alone(address):
    """私网 / 回环 / 链路本地 / 保留 / CGNAT / 非 IP: 一律不问。

    外发的不只是「查一下」, 还等于把内网地址结构告诉第三方。本机开发时对端就是
    127.0.0.1, 这个分支天天都会走到。
    """
    assert ip_locate.is_public_ip(address) is False


def test_client_ip_defaults_to_the_tcp_peer():
    """X-Forwarded-For 默认不信 —— 谁都能写这个头。"""
    request = request_from("203.0.113.9", forwarded="1.2.3.4")
    assert ip_locate.client_ip(request, settings()) == "203.0.113.9"


def test_client_ip_reads_forwarded_for_only_when_asked():
    request = request_from("10.0.0.1", forwarded="1.2.3.4, 5.6.7.8")
    trusted = settings(geo_trust_forwarded_for=True)
    # 取最左边那个: 那是客户端地址, 后面的都是中间层
    assert ip_locate.client_ip(request, trusted) == "1.2.3.4"
    assert ip_locate.client_ip(request_from("10.0.0.1"), trusted) == "10.0.0.1"


def test_client_ip_without_a_peer_is_none():
    assert ip_locate.client_ip(request_from(None), settings()) is None


# ------------------------------------------------------------------- 问一次

def test_no_provider_means_not_a_single_request(monkeypatch):
    """默认配置(provider=none)下, 这一层一个包都不该发。"""
    refuse_to_ask(monkeypatch)
    assert ip_locate.locate("223.5.5.5", settings()) is None


def test_private_address_is_not_asked_about_even_with_a_provider(monkeypatch):
    refuse_to_ask(monkeypatch)
    configured = settings(geo_ip_provider="ipapi")
    for address in ("127.0.0.1", "192.168.1.10", "100.64.0.1", None, "testclient"):
        assert ip_locate.locate(address, configured) is None


def test_preset_url_carries_the_address_and_the_answer_is_parsed(monkeypatch):
    seen = stub_lookup(
        monkeypatch,
        {"status": "success", "countryCode": "CN", "city": "杭州", "regionName": "浙江"},
    )
    found = ip_locate.locate("223.5.5.5", settings(geo_ip_provider="ipapi"))
    assert found == ip_locate.Location(city="杭州", region="浙江", country_code="CN")
    url, headers, timeout = seen[0]
    assert "223.5.5.5" in url
    assert "lang=zh-CN" in url, "要中文写法才能跟库里的城市名对上"
    assert headers == {}, "没配 key 就不该带 Authorization"
    assert timeout == 1.5, "超时取自配置 —— 认不出来是小事, 拖慢首页是大事"


def test_custom_url_placeholder_and_bare_url_both_work(monkeypatch):
    seen = stub_lookup(monkeypatch, {"city": "杭州市"})
    ip_locate.locate(
        "223.5.5.5",
        settings(geo_ip_provider="custom", geo_ip_base_url="https://geo.example.com/{ip}?f=1"),
    )
    ip_locate.locate(
        "223.5.5.5",
        settings(geo_ip_provider="custom", geo_ip_base_url="https://geo.example.com/lookup/"),
    )
    assert seen[0][0] == "https://geo.example.com/223.5.5.5?f=1"
    assert seen[1][0] == "https://geo.example.com/lookup/223.5.5.5"


def test_custom_provider_without_a_url_is_not_an_error(monkeypatch):
    refuse_to_ask(monkeypatch)
    assert ip_locate.locate("223.5.5.5", settings(geo_ip_provider="custom")) is None


def test_api_key_is_sent_as_a_bearer_token(monkeypatch):
    seen = stub_lookup(monkeypatch, {"city": "杭州"})
    ip_locate.locate(
        "223.5.5.5",
        settings(
            geo_ip_provider="custom",
            geo_ip_base_url="https://geo.example.com",
            geo_ip_api_key="sk-x",
        ),
    )
    assert seen[0][1] == {"Authorization": "Bearer sk-x"}


def test_region_and_country_field_aliases(monkeypatch):
    """有的服务把省份叫 region。两种都收, 免得为了换一家再改一次代码。"""
    stub_lookup(monkeypatch, {"city": "", "region": "广东省", "countryCode": "CN"})
    found = ip_locate.locate("223.5.5.5", settings(geo_ip_provider="ipapi"))
    assert found == ip_locate.Location(city=None, region="广东省", country_code="CN")


def test_every_failure_is_just_not_recognised(monkeypatch):
    """连不上 / 超时 / 不是 JSON / 服务自己说认不出来 / 两个字段都空 —— 全是 None。

    这一层绝不能往上抛异常: 首页最先看到的那一块不该因为归属地服务抖了一下就变成
    一个 500。
    """
    configured = settings(geo_ip_provider="ipapi")
    cases = [
        httpx.ConnectError("连不上"),
        httpx.ReadTimeout("超时"),
        ValueError("不是 JSON"),
        {"status": "fail", "message": "reserved range"},
        {"status": "success", "city": "", "regionName": ""},
        ["不是对象"],
        {"status": "success"},
    ]
    for payload in cases:
        stub_lookup(monkeypatch, payload)
        assert ip_locate.locate("223.5.5.5", configured) is None, payload


# ------------------------------------------------- 对到库内取值(这一层才碰库)

def test_match_place_maps_the_spellings_to_catalogue_values(seeded, db_session):
    city, region = ip_locate.match_place(db_session, city="杭州", region="浙江")
    assert (city, region) == ("杭州市", "浙江省")
    city, region = ip_locate.match_place(db_session, city="西城区", region="北京市")
    assert (city, region) == (None, "北京市"), "认不出城市就只认省份, 不硬凑"


def test_match_place_gives_up_instead_of_guessing(seeded, db_session):
    """库外的写法一律 None: 猜错城市(把人指到隔壁市)比不猜更糟。"""
    assert ip_locate.match_place(db_session, city="杭州湾", region="江南省") == (None, None)
    assert ip_locate.match_place(db_session, city=None, region=None) == (None, None)


def test_match_place_ignores_drafts(seeded, db_session):
    """候选只从已发布景点里取 —— 拿 draft 的城市去匹配会得到一个查不出东西的「命中」。"""
    db_session.add(
        Attraction(
            slug="draft-luoyang", name="未发布的洛阳景点",
            category_id=seeded["nature"].id, city="洛阳市", province="河南省",
            status="draft", source="测试夹具", license="MIT",
        )
    )
    db_session.commit()
    assert ip_locate.match_place(db_session, city="洛阳", region="河南") == (None, None)


# ------------------------------------------------------------- 接线(真 Request)

def test_the_endpoint_reads_the_real_peer_address(seeded, db_session, monkeypatch):
    """不打桩 client_ip: 起一个对端是公网地址的 TestClient。

    打桩只能证明我们自己的逻辑对, 证明不了 FastAPI 的 Request 真把对端地址交到了这一层
    手里 —— 而「读错字段」这种错只会安静地让所有访客都退化成全国随机。
    """
    seen = stub_lookup(
        monkeypatch,
        {"status": "success", "countryCode": "CN", "city": "杭州", "regionName": "浙江"},
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings(geo_ip_provider="ipapi")
    try:
        with TestClient(app, client=("223.5.5.5", 43210)) as fresh:
            body = fresh.get(f"{API}/attractions/nearby").json()
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_db, None)

    assert seen, "对端地址没被送到 client_ip 这一层 —— 接线断了"
    assert "223.5.5.5" in seen[0][0]
    assert body["located"] is True and body["city"] == "杭州市"


def test_a_local_peer_never_leaves_the_process(client, seeded, monkeypatch):
    """本机开发时对端是 TestClient 自己 —— 配了 provider 也不该发请求。"""
    refuse_to_ask(monkeypatch)
    app.dependency_overrides[get_settings] = lambda: settings(geo_ip_provider="ipapi")
    try:
        body = client.get(f"{API}/attractions/nearby").json()
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert body["located"] is False
    assert body["scope"] == "nation"
    assert len(body["items"]) == 3


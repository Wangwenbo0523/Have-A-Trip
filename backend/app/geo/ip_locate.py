"""按 IP 猜归属地 —— 只到城市级, 不做定位。

产品定位是「不做地图与定位」, 所以这一层给的不是坐标, 而是三个字符串: 归属地的城市、
省份与国别。用它把同城 / 同省的景点排在前面, 仅此而已。

三条硬规矩:

1. **默认关闭**。`GEO_IP_PROVIDER=none`(默认)时这里一个外部请求都不发, 接口直接
   退回全国随机并如实标明 —— 与 LLM_PROVIDER 同一思路: 不配就不连外网。
2. **不落库、不写 cookie、不返回坐标**。归属地只在这一次请求里用一下, 出了函数就没了;
   埋点(/events)那条路径也不带任何位置字段。
3. **失败一律当作「没认出来」**。超时、限流、字段缺失、返回不是 JSON 都返回 None,
   绝不往上抛 —— 这是首页的锦上添花, 不该因为它没认出来就给人一个 500。

一个只有实测才会知道的坑: ip-api 的 lang=zh-CN 对**中国** IP 返回的是中文, 但写法与
库内取值并不一致 —— 实测 223.5.5.5 -> city 杭州, 114.114.114.114 -> city 济南市 /
region 山东, 北京某 IP 干脆只到区(西城区)。所以匹配是「归一化后相等」, 对不上就逐级
下降(城市 -> 省份 -> 全国), 绝不拿 LIKE 硬凑: 把人指到隔壁城市比不猜更糟。
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Attraction

PUBLISHED = "published"

# 预设服务。ip-api 免费档 45 次/分钟、只给 http(要 https 得付费), 这一层一天也没几次
# 调用, 够用。要换别家就用 GEO_IP_BASE_URL + GEO_IP_PROVIDER=custom。
PRESETS: dict[str, str] = {
    "ipapi": "http://ip-api.com/json/{ip}?fields=status,countryCode,city,regionName&lang=zh-CN",
}

# 行政区后缀。「杭州市」与「杭州」是同一个地方, 「浙江省」与「山东」同理。
# 只从末尾剥**一次**, 而且**不把「州」和「区」本身算后缀**: 库里的「苏州市」剥掉「市」
# 就是全名, 而服务给的是没后缀的「苏州」—— 若两边都再剥一次「州」, 得到的是「苏」,
# 库里的「苏州」与服务给的「苏州」反而对不上。顺序也有讲究: 长的在前, 先匹配先返回。
_ADMIN_SUFFIXES = (
    "特别行政区", "自治区", "自治州", "自治县", "地区", "盟", "市", "省", "县",
)

# RFC 6598 的运营商级 NAT 段。Python 3.13 认为它既不 private 也不 global, 只靠
# is_private 会把 100.64.0.0/10 当成公网地址去问一次 —— 那是运营商内网的地址, 问了
# 也没意义, 还等于把内网结构送出去。
_CARRIER_GRADE_NAT = ipaddress.ip_network("100.64.0.0/10")


@dataclass(frozen=True)
class Location:
    """一次的归属地猜测。**只有名字, 没有坐标** —— 这一层不做定位。"""

    city: str | None = None
    region: str | None = None
    country_code: str | None = None


def normalize_place(value: str | None) -> str | None:
    """归一化行政区写法, 只用来比对, 不展示。"""
    if value is None:
        return None
    text = value.strip().lower().replace(" ", "")
    for suffix in _ADMIN_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
            break
    return text or None


def is_public_ip(value: str | None) -> bool:
    """这个地址值不值得拿去问归属地。

    非 IP(TestClient 的 "testclient")、私网、回环、链路本地、保留段、多播、CGNAT
    一律 False —— 要么问了没意义, 要么等于把内网结构暴露给第三方。
    """
    if not value:
        return False
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return False
    if address.version == 4 and address in _CARRIER_GRADE_NAT:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def client_ip(request: Request, settings: Settings) -> str | None:
    """访客地址。

    默认只信 TCP 对端(request.client)。X-Forwarded-For 谁都能写, 默认信了就等于让
    伪造的头把所有人指到同一个城市。确实在反向代理后面部署时把 GEO_TRUST_FORWARDED_FOR
    打开, 并确认代理是**覆盖**而不是追加这个头。
    """
    if settings.geo_trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else None


def endpoint_for(settings: Settings, ip: str) -> str | None:
    """拼出查询地址。GEO_IP_BASE_URL 里有 {ip} 就替换, 没有就拼在路径末尾。"""
    template = settings.geo_ip_base_url.strip() or PRESETS.get(settings.geo_ip_provider, "")
    if not template:
        return None
    quoted = quote(ip, safe="")
    if "{ip}" in template:
        return template.replace("{ip}", quoted)
    return template.rstrip("/") + "/" + quoted


def fetch_json(url: str, *, headers: dict[str, str], timeout: float) -> Any:
    """**唯一**发出网络请求的地方。

    单独一个函数是为了可测: 测试只打桩这一个函数, 就能在不联网的前提下断言
    「配了 provider 时确实去问了」与「没配 / 是私网地址时一次都没问」。
    """
    with httpx.Client(timeout=timeout) as http:
        response = http.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def locate(ip: str | None, settings: Settings) -> Location | None:
    """问一次归属地。任何失败都返回 None(见模块开头第 3 条), 不抛异常。"""
    if settings.geo_ip_provider == "none" or not is_public_ip(ip):
        return None
    url = endpoint_for(settings, ip or "")
    if url is None:
        return None

    headers: dict[str, str] = {}
    if settings.geo_ip_api_key:
        headers["Authorization"] = f"Bearer {settings.geo_ip_api_key}"
    try:
        payload = fetch_json(url, headers=headers, timeout=settings.geo_ip_timeout_seconds)
    except (httpx.HTTPError, ValueError, TypeError):
        # 连不上 / 超时 / 回的不是 JSON —— 都只是「没认出来」
        return None
    if not isinstance(payload, dict):
        return None
    # ip-api 认不出来时给 status=fail; 别的服务没有这个字段就当它是 success
    if str(payload.get("status", "")).lower() not in ("", "success"):
        return None

    city = _text(payload.get("city"))
    region = _text(payload.get("regionName")) or _text(payload.get("region"))
    country = _text(payload.get("countryCode"))
    if city is None and region is None:
        return None
    return Location(city=city, region=region, country_code=country)


def match_place(
    db: Session,
    *,
    city: str | None,
    region: str | None,
) -> tuple[str | None, str | None]:
    """把归属地写法对到库内取值。返回 (库内城市, 库内省份), 对不上给 None。

    相等而不是 LIKE: 「杭州」能对上库里的「杭州市」, 但对不上「杭州湾」。猜错城市比
    不猜更糟, 所以宁可返回 None 走降级。

    候选只从**已发布**景点里取 —— 拿 draft 的城市名去匹配, 会得到一个查不出东西的
    「命中」。
    """
    if city is None and region is None:
        return (None, None)
    cities = _distinct_values(db, Attraction.city)
    provinces = _distinct_values(db, Attraction.province)
    return (_match_one(cities, city), _match_one(provinces, region))


def _distinct_values(db: Session, column) -> dict[str, str]:
    """归一化写法 -> 库内原样取值。"""
    rows = db.scalars(
        select(column).where(Attraction.status == PUBLISHED, column.is_not(None)).distinct()
    ).all()
    index: dict[str, str] = {}
    for value in rows:
        key = normalize_place(value)
        if key:
            index[key] = value
    return index


def _match_one(index: dict[str, str], value: str | None) -> str | None:
    key = normalize_place(value)
    return index.get(key) if key else None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None

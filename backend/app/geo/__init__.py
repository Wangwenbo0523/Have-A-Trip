"""按 IP 猜归属地(只到城市级)。对外只暴露取地址、查一次、对库内取值三个函数。"""
from .ip_locate import Location, client_ip, is_public_ip, locate, match_place, normalize_place

__all__ = [
    "Location",
    "client_ip",
    "is_public_ip",
    "locate",
    "match_place",
    "normalize_place",
]

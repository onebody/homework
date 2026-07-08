import math

from ..config import GEO_THRESHOLD_METERS


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """返回两点间距离（米）。任一坐标为 None 时返回 None。"""
    if None in (lat1, lng1, lat2, lng2):
        return None
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_far_from_home(home_lat, home_lng, cur_lat, cur_lng) -> bool:
    d = haversine(home_lat, home_lng, cur_lat, cur_lng)
    if d is None:
        return False
    return d > GEO_THRESHOLD_METERS

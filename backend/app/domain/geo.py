import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def interpolate(
    lat1: float, lon1: float, lat2: float, lon2: float, f: float
) -> tuple[float, float]:
    """Point a fraction ``f`` of the way along the straight line (fine at city scale)."""
    return lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f

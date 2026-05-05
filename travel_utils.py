"""
travel_utils.py — 이동 시간 추정 함수

운영 기준 확정 (HAPPY_TRAVEL_SYSTEM_DESIGN_ADDENDUM.md § 2):
  최대 raw speed : 16.0 km/h (≤ 18km/h 운영 상한 충족)
  최소 이동거리  : 50m (0.05km) 보정
  최소 이동시간  : 5분 강제

  구간별 속도 및 정체 계수:
    d < 1.0km  : 4.0  km/h × 1.50  → 체감 2.7 km/h  (보행 + 심리 버퍼)
    d < 3.0km  : 7.0  km/h × 1.35  → 체감 5.2 km/h  (근거리 도심)
    d < 6.0km  : 11.0 km/h × 1.25  → 체감 8.8 km/h  (중거리)
    d >= 6.0km : 16.0 km/h × 1.20  → 체감 13.3 km/h (장거리)

  폐기된 공식: speed = clip(4 + (d/1.5) * 21, 4, 25)
    → 최대 25km/h 허용으로 과밀 일정 유발 — 운영 기준에서 제외
"""

from math import ceil


def estimate_travel_minutes(distance_km: float) -> int:
    """
    두 장소 간 직선거리(km) → 이동 예상 시간(분) 변환.

    Parameters
    ----------
    distance_km : 직선거리 (km). 음수/0도 허용 — 50m 하한으로 자동 보정.

    Returns
    -------
    이동 예상 시간 (분, 최소 5분 보장)

    Examples
    --------
    >>> estimate_travel_minutes(0.3)   # 300m — 보행 근거리
    7
    >>> estimate_travel_minutes(2.0)   # 2km — 근거리 도심
    17
    >>> estimate_travel_minutes(5.0)   # 5km — 중거리
    28
    >>> estimate_travel_minutes(10.0)  # 10km — 장거리
    45
    """
    d = max(distance_km, 0.05)  # 최소 이동거리 50m 보정

    if d < 1.0:
        speed_kmh      = 4.0
        traffic_factor = 1.50
    elif d < 3.0:
        speed_kmh      = 7.0
        traffic_factor = 1.35
    elif d < 6.0:
        speed_kmh      = 9.0
        traffic_factor = 1.35
    else:
        speed_kmh      = 11.5
        traffic_factor = 1.35

    raw_minutes = (d / speed_kmh) * 60
    adjusted    = raw_minutes * traffic_factor
    return max(5, ceil(adjusted))

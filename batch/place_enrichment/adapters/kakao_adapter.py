from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
import urllib.parse
import urllib.request
import json


KAKAO_LOCAL_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


@dataclass
class NormalizedExternalPlace:
    source_type: str
    source_place_id: str
    name: str
    category: str | None
    address: str | None
    road_address: str | None
    phone: str | None
    latitude: float | None
    longitude: float | None
    place_url: str | None
    source_payload: dict[str, Any]
    image_url: str | None = None
    thumbnail_url: str | None = None


class KakaoAdapter:
    """Kakao Local Search adapter for offline enrichment batches only."""

    source_type = "KAKAO"

    def __init__(self, api_key: str | None = None, timeout: int = 8):
        self.api_key = api_key or os.getenv("KAKAO_REST_API_KEY")
        self.timeout = timeout

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def fetch_candidates(self, place: dict, *, radius_m: int = 500, limit: int = 5) -> list[NormalizedExternalPlace]:
        if not self.has_api_key:
            return self.mock_candidates(place, limit=limit)

        lat = place.get("latitude")
        lon = place.get("longitude")
        if lat is None or lon is None:
            return []

        params = {
            "query": place.get("name") or "",
            "x": lon,
            "y": lat,
            "radius": radius_m,
            "size": min(max(limit, 1), 15),
            "sort": "distance",
        }
        headers = {"Authorization": f"KakaoAK {self.api_key}"}
        url = KAKAO_LOCAL_SEARCH_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [self.normalize(item) for item in payload.get("documents", [])]

    def normalize(self, raw: dict) -> NormalizedExternalPlace:
        return NormalizedExternalPlace(
            source_type=self.source_type,
            source_place_id=str(raw.get("id") or ""),
            name=(raw.get("place_name") or "").strip(),
            category=raw.get("category_name") or None,
            address=raw.get("address_name") or None,
            road_address=raw.get("road_address_name") or None,
            phone=raw.get("phone") or None,
            latitude=_to_float(raw.get("y")),
            longitude=_to_float(raw.get("x")),
            place_url=raw.get("place_url") or None,
            source_payload=raw,
        )

    def mock_candidates(self, place: dict, *, limit: int = 5) -> list[NormalizedExternalPlace]:
        lat = place.get("latitude")
        lon = place.get("longitude")
        if lat is None or lon is None:
            return []
        name = place.get("name") or "mock cafe"
        raw = {
            "id": f"mock-kakao-{place.get('place_id')}",
            "place_name": name,
            "category_name": "음식점 > 카페",
            "address_name": place.get("address") or "",
            "road_address_name": place.get("road_address") or "",
            "phone": place.get("tel") or "",
            "x": str(lon),
            "y": str(lat),
            "place_url": "https://place.map.kakao.com/mock",
            "mock": True,
        }
        candidate = self.normalize(raw)
        candidate.image_url = f"https://example.com/mock/place-{place.get('place_id')}.jpg"
        candidate.thumbnail_url = candidate.image_url
        return [candidate][:limit]


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

from __future__ import annotations

import html
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


NAVER_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"


@dataclass
class NormalizedNaverPlace:
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


class NaverAdapter:
    """Naver Local Search adapter for offline enrichment batches only."""

    source_type = "NAVER"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None, timeout: int = 8):
        self.client_id = client_id or os.getenv("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET")
        self.timeout = timeout

    @property
    def has_api_key(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def fetch_candidates(self, place: dict, *, limit: int = 5) -> list[NormalizedNaverPlace]:
        if not self.has_api_key:
            return []

        query = " ".join(part for part in [place.get("region_1"), place.get("name")] if part)
        params = {
            "query": query,
            "display": min(max(limit, 1), 5),
            "start": 1,
            "sort": "random",
        }
        url = NAVER_LOCAL_SEARCH_URL + "?" + urllib.parse.urlencode(params)
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [self.normalize(item) for item in payload.get("items", [])]

    def normalize(self, raw: dict) -> NormalizedNaverPlace:
        name = _strip_html(raw.get("title") or "").strip()
        external_key = raw.get("link") or f"{name}:{raw.get('mapx')}:{raw.get('mapy')}"
        external_id = hashlib.sha1(str(external_key).encode("utf-8")).hexdigest()
        return NormalizedNaverPlace(
            source_type=self.source_type,
            source_place_id=external_id,
            name=name,
            category=raw.get("category") or None,
            address=raw.get("address") or None,
            road_address=raw.get("roadAddress") or None,
            phone=raw.get("telephone") or None,
            latitude=_naver_coord(raw.get("mapy")),
            longitude=_naver_coord(raw.get("mapx")),
            place_url=raw.get("link") or None,
            source_payload=raw,
        )


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value or "")
    stripped = re.sub(r"<[^>]+>", "", unescaped)
    return html.unescape(stripped).strip()


def _naver_coord(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return int(value) / 10_000_000
    except (TypeError, ValueError):
        return None

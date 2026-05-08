from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse


QUALITY_LEVELS = ("BLOCKED", "LOW", "REVIEW_REQUIRED", "GOOD", "REPRESENTATIVE_GRADE")
PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "127.0.0.1",
    "dummyimage.com",
    "placehold.co",
    "placeholder.com",
    "via.placeholder.com",
}
BLOCKING_RISK_FLAGS = {
    "PLACEHOLDER_IMAGE_URL",
    "INVALID_IMAGE_URL",
    "WRONG_PLACE_RISK",
    "NEARBY_BUSINESS_RISK",
    "WATERMARK_DETECTED",
    "ADVERTISEMENT_DETECTED",
    "LICENSE_INVALID",
    "SOURCE_INVALID",
}


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_domain(url: str | None) -> str | None:
    if not has_text(url):
        return None
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return parsed.netloc.lower().split(":")[0]


def is_placeholder_url(url: str | None) -> bool:
    domain = normalize_domain(url)
    if not domain:
        return False
    return domain in PLACEHOLDER_DOMAINS or any(domain.endswith("." + d) for d in PLACEHOLDER_DOMAINS)


def url_fingerprint(url: str | None) -> str | None:
    if not has_text(url):
        return None
    return hashlib.sha256(str(url).strip().encode("utf-8")).hexdigest()


def extract_nested(payload: dict[str, Any] | None, *keys: str) -> Any:
    current: Any = payload or {}
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def image_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    source_payload = candidate.get("source_payload") or {}
    nested = source_payload.get("enrichment_payload") or {}
    image = nested.get("representative_image") or {}
    return image if isinstance(image, dict) else {}


def qa_payload(candidate: dict[str, Any], duplicate_count: int = 0) -> dict[str, Any]:
    image = image_payload(candidate)
    image_url = candidate.get("image_url") or image.get("image_url")
    source_credit = (
        image.get("source_credit")
        or extract_nested(candidate.get("review_payload"), "source_credit")
        or extract_nested(candidate.get("source_payload"), "source_credit")
    )
    license_note = image.get("license_note") or extract_nested(candidate.get("source_payload"), "license_note")
    image_source_url = image.get("image_source_url") or extract_nested(candidate.get("source_payload"), "image_source_url")
    width = image.get("width")
    height = image.get("height")
    mime_type = image.get("mime_type")
    checksum = image.get("checksum")

    risk_flags: list[str] = list((candidate.get("validation_payload") or {}).get("risk_flags") or [])
    if not image_url or not normalize_domain(image_url):
        risk_flags.append("INVALID_IMAGE_URL")
    if is_placeholder_url(image_url):
        risk_flags.append("PLACEHOLDER_IMAGE_URL")
    if not source_credit:
        risk_flags.append("SOURCE_CREDIT_MISSING")
    if not license_note:
        risk_flags.append("LICENSE_NOTE_MISSING")
    if duplicate_count > 1:
        risk_flags.append("DUPLICATE_IMAGE_URL")

    source_validity = "VALID" if source_credit and image_source_url else "REVIEW_REQUIRED"
    license_validity = "VALID" if license_note else "REVIEW_REQUIRED"
    resolution = {
        "width": width,
        "height": height,
        "mime_type": mime_type,
        "checksum": checksum,
        "metadata_extraction": "NOT_PERFORMED_NO_DOWNLOAD",
    }

    quality_level = grade_image_quality(
        {
            "risk_flags": risk_flags,
            "source_validity": source_validity,
            "license_validity": license_validity,
            "width": width,
            "height": height,
            "landmark_identifiable": image.get("landmark_identifiable"),
        }
    )

    return {
        "landmark_identifiable": image.get("landmark_identifiable"),
        "wrong_place_risk": bool(image.get("wrong_place_risk", False)),
        "nearby_business_risk": bool(image.get("nearby_business_risk", False)),
        "watermark_detected": bool(image.get("watermark_detected", False)),
        "advertisement_detected": bool(image.get("advertisement_detected", False)),
        "resolution": resolution,
        "source_validity": source_validity,
        "license_validity": license_validity,
        "source_credit": source_credit,
        "license_note": license_note,
        "image_source_url": image_source_url,
        "placeholder_domain": is_placeholder_url(image_url),
        "duplicate_url_count": duplicate_count,
        "url_fingerprint": url_fingerprint(image_url),
        "risk_flags": sorted(set(risk_flags)),
        "quality_level": quality_level,
    }


def grade_image_quality(summary: dict[str, Any]) -> str:
    risk_flags = set(summary.get("risk_flags") or [])
    width = summary.get("width")
    height = summary.get("height")

    if risk_flags & BLOCKING_RISK_FLAGS:
        return "BLOCKED"
    if "INVALID_IMAGE_URL" in risk_flags or "PLACEHOLDER_IMAGE_URL" in risk_flags:
        return "BLOCKED"
    if summary.get("source_validity") != "VALID" or summary.get("license_validity") != "VALID":
        return "REVIEW_REQUIRED"
    if width is None or height is None:
        return "REVIEW_REQUIRED"
    try:
        if int(width) < 800 or int(height) < 500:
            return "LOW"
    except (TypeError, ValueError):
        return "REVIEW_REQUIRED"
    if summary.get("landmark_identifiable") is True:
        return "REPRESENTATIVE_GRADE"
    return "GOOD"


def qa_checklist() -> list[dict[str, str]]:
    return [
        {"item": "landmark_identifiable", "pass": "대표 POI 본체 또는 대표 전경이 명확히 식별된다."},
        {"item": "wrong_place_risk", "pass": "동명 장소나 다른 지역 명소가 아니다."},
        {"item": "nearby_business_risk", "pass": "호텔, 식당, 카페, 주차장 등 주변 비즈니스 사진이 아니다."},
        {"item": "watermark_detected", "pass": "워터마크가 없거나 매우 작아 서비스 품질을 해치지 않는다."},
        {"item": "advertisement_detected", "pass": "광고 배너나 홍보 이미지가 아니다."},
        {"item": "resolution", "pass": "대표 이미지는 최소 800px 이상을 권장한다."},
        {"item": "source_validity", "pass": "source_credit과 image_source_url이 확인된다."},
        {"item": "license_validity", "pass": "license_note 또는 운영 소유권이 확인된다."},
        {"item": "placeholder_domain", "pass": "example.com, placeholder 계열 테스트 URL이 아니다."},
        {"item": "duplicate_checksum", "pass": "동일 checksum 또는 동일 URL 중복 후보가 아니다."},
    ]

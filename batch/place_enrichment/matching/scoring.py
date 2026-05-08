from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal


ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "REJECT"]
MatchDecision = Literal["AUTO_APPROVE", "MANUAL_REVIEW", "LOW_CONFIDENCE", "REJECT"]
StandardCategory = Literal["cafe", "meal", "culture", "spot", "unknown"]

CAFE_TERMS = (
    "\uce74\ud398",  # cafe
    "\ucee4\ud53c",  # coffee
    "\ub514\uc800\ud2b8",  # dessert
    "\ubca0\uc774\ucee4\ub9ac",  # bakery
    "\ucee4\ud53c\uc804\ubb38\uc810",  # coffee shop
    "cafe",
    "coffee",
    "bakery",
    "dessert",
)
MEAL_TERMS = (
    "\uc74c\uc2dd\uc810",
    "\uc2dd\ub2f9",
    "\ud55c\uc2dd",
    "\uc911\uc2dd",
    "\uc77c\uc2dd",
    "\uc591\uc2dd",
    "\ubd84\uc2dd",
    "\ub9db\uc9d1",
    "\uace0\uae30",
    "\uc694\ub9ac",
    "\ub808\uc2a4\ud1a0\ub791",
    "restaurant",
)
CULTURE_TERMS = (
    "\ubb38\ud654",
    "\uc804\uc2dc",
    "\ubc15\ubb3c\uad00",
    "\ubbf8\uc220\uad00",
    "\uacf5\uc5f0",
    "\uac24\ub7ec\ub9ac",
    "\uccb4\ud5d8",
    "\ub3c4\uc11c\uad00",
    "\uae30\ub150\uad00",
)
SPOT_TERMS = (
    "\uad00\uad11",
    "\uba85\uc18c",
    "\uacf5\uc6d0",
    "\ud574\uc218\uc695\uc7a5",
    "\uc0b0",
    "\ud638\uc218",
    "\uc804\ub9dd\ub300",
)

CHAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "\uc2a4\ud0c0\ubc85\uc2a4": ("\uc2a4\ud0c0\ubc85\uc2a4", "starbucks", "star bucks"),
    "\ud22c\uc378\ud50c\ub808\uc774\uc2a4": ("\ud22c\uc378", "\ud22c\uc378\ud50c\ub808\uc774\uc2a4", "twosome"),
    "\uba54\uac00\ucee4\ud53c": ("\uba54\uac00\ucee4\ud53c", "mega coffee", "megacoffee"),
    "\ucef4\ud3ec\uc988\ucee4\ud53c": ("\ucef4\ud3ec\uc988", "\ucef4\ud3ec\uc988\ucee4\ud53c", "compose coffee"),
    "\uc774\ub514\uc57c": ("\uc774\ub514\uc57c", "ediya"),
    "\ube7d\ub2e4\ubc29": ("\ube7d\ub2e4\ubc29", "paik", "paiks coffee", "paik's coffee"),
    "\ud560\ub9ac\uc2a4": ("\ud560\ub9ac\uc2a4", "hollys"),
    "\uc5d4\uc81c\ub9ac\ub108\uc2a4": ("\uc5d4\uc81c\ub9ac\ub108\uc2a4", "angel in us", "angelinus"),
    "\ud3f4\ubc14\uc14b": ("\ud3f4\ubc14\uc14b", "paul bassett"),
    "\ucee4\ud53c\ube48": ("\ucee4\ud53c\ube48", "coffee bean"),
    "\ud30c\uc2a4\ucfe0\ucc0c": ("\ud30c\uc2a4\ucfe0\ucc0c", "pascucci"),
    "\uacf5\ucc28": ("\uacf5\ucc28", "gong cha", "gongcha"),
    "\ubc30\uc2a4\ud0a8\ub77c\ube48\uc2a4": ("\ubc30\uc2a4\ud0a8\ub77c\ube48\uc2a4", "baskin robbins"),
    "\ub9e5\ub3c4\ub0a0\ub4dc": ("\ub9e5\ub3c4\ub0a0\ub4dc", "mcdonald", "mcdonalds"),
    "\ubc84\uac70\ud0b9": ("\ubc84\uac70\ud0b9", "burger king"),
    "\ub86f\ub370\ub9ac\uc544": ("\ub86f\ub370\ub9ac\uc544", "lotteria"),
    "\ub9d8\uc2a4\ud130\uce58": ("\ub9d8\uc2a4\ud130\uce58", "momstouch", "mom's touch"),
    "\uc11c\ube0c\uc6e8\uc774": ("\uc11c\ube0c\uc6e8\uc774", "subway"),
}

REGION_NOISE_TOKENS = (
    "\uc11c\uc6b8",
    "\ub300\ud55c\ubbfc\uad6d",
    "\ud55c\uad6d",
)
GENERIC_NAME_TOKENS = (
    "\uce74\ud398",
    "\ucee4\ud53c",
    "cafe",
    "coffee",
)


@dataclass
class NormalizedName:
    raw_name: str
    normalized_name: str
    compact_name: str
    match_name: str
    base_name: str
    chain_brand: str | None = None
    chain_alias_matched: str | None = None
    is_chain_brand: bool = False
    branch_name: str | None = None
    branch_type: str | None = None
    branch_tokens: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    score: int
    confidence_level: ConfidenceLevel
    decision: MatchDecision
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    normalized_name: str = ""
    external_normalized_name: str = ""
    name_similarity: float = 0.0
    distance_meters: float | None = None
    score_breakdown: dict[str, int] = field(default_factory=dict)
    normalized_payload: dict = field(default_factory=dict)


def calculate_place_match_score(base_place: dict, external_place: dict) -> MatchResult:
    base_normalized = normalize_place_name_parts(base_place.get("name"))
    ext_normalized = normalize_place_name_parts(external_place.get("name"))
    name_similarity = (
        SequenceMatcher(None, base_normalized.match_name, ext_normalized.match_name).ratio()
        if base_normalized.match_name and ext_normalized.match_name
        else 0.0
    )
    distance_meters = calculate_distance_meters(
        base_place.get("latitude"),
        base_place.get("longitude"),
        external_place.get("latitude"),
        external_place.get("longitude"),
    )
    risk_flags = detect_risk_flags(base_place, external_place, name_similarity, distance_meters)
    breakdown = {
        "name_similarity": score_name_similarity(name_similarity),
        "distance_score": score_distance(distance_meters),
        "category_score": score_category(base_place, external_place),
        "region_score": score_region(base_place, external_place),
        "address_score": score_address(base_place, external_place),
        "phone_score": score_phone(base_place, external_place),
        "business_status_score": score_business_status(external_place),
        "risk_penalty": score_risk_penalty(risk_flags),
    }
    score = max(0, min(100, int(round(sum(breakdown.values())))))
    confidence, decision = score_based_decision(score)
    return MatchResult(
        score=score,
        confidence_level=confidence,
        decision=decision,
        reasons=build_reasons(breakdown, risk_flags),
        risk_flags=risk_flags,
        normalized_name=base_normalized.match_name,
        external_normalized_name=ext_normalized.match_name,
        name_similarity=name_similarity,
        distance_meters=distance_meters,
        score_breakdown=breakdown,
        normalized_payload=build_normalized_payload(base_place, external_place, base_normalized, ext_normalized),
    )


def normalize_korean_text(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_special_chars(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[&\u00b7\u318d\u30fb/\\,._\-:;'\"|]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_place_name(name: str | None) -> str:
    return normalize_place_name_parts(name).match_name


def normalize_place_name_parts(name: str | None) -> NormalizedName:
    raw = normalize_korean_text(name)
    lowered = raw.lower()
    normalized = normalize_special_chars(lowered)
    parenthetical_tokens = extract_parenthetical_tokens(lowered)
    chain_brand, chain_alias = detect_chain_brand(normalized)

    working = normalized
    if chain_alias:
        working = remove_chain_alias(working, chain_alias)
    working = strip_parenthetical_text(working)
    branch_name, branch_type, branch_tokens = extract_branch_tokens(working, parenthetical_tokens)
    if chain_brand and not branch_name:
        fallback_branch = remove_generic_tokens(working)
        if fallback_branch:
            branch_name = fallback_branch
            branch_type = "BRANCH"
            branch_tokens = [fallback_branch]

    base_name = chain_brand or remove_generic_tokens(working)
    match_name = chain_brand or base_name
    if not chain_brand:
        match_name = remove_generic_tokens(match_name)

    compact_name = compact(normalized)
    return NormalizedName(
        raw_name=raw,
        normalized_name=normalized,
        compact_name=compact_name,
        match_name=compact(match_name),
        base_name=compact(base_name),
        chain_brand=chain_brand,
        chain_alias_matched=chain_alias,
        is_chain_brand=bool(chain_brand),
        branch_name=compact(branch_name) if branch_name else None,
        branch_type=branch_type,
        branch_tokens=[compact(token) for token in branch_tokens if compact(token)],
    )


def extract_parenthetical_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"\(([^)]*)\)|\[([^]]*)\]|\{([^}]*)\}", value):
        token = next(group for group in match.groups() if group)
        tokens.append(normalize_special_chars(token))
    return tokens


def strip_parenthetical_text(value: str) -> str:
    return re.sub(r"\([^)]*\)|\[[^]]*\]|{[^}]*}", " ", value).strip()


def detect_chain_brand(value: str | None) -> tuple[str | None, str | None]:
    normalized = normalize_special_chars(normalize_korean_text(value).lower())
    compacted = compact(normalized)
    for brand, aliases in CHAIN_ALIASES.items():
        for alias in aliases:
            alias_normalized = normalize_special_chars(alias.lower())
            if compact(alias_normalized) in compacted:
                return brand, alias_normalized
    return None, None


def remove_chain_alias(value: str, alias: str) -> str:
    alias_pattern = re.escape(alias)
    without_alias = re.sub(alias_pattern, " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", without_alias).strip()


def extract_branch_tokens(value: str, parenthetical_tokens: list[str] | None = None) -> tuple[str | None, str | None, list[str]]:
    candidates = [value, *(parenthetical_tokens or [])]
    for candidate in candidates:
        branch_name, branch_type = parse_branch_candidate(candidate)
        if branch_name:
            tokens = [branch_name]
            if branch_type:
                tokens.append(branch_type)
            return branch_name, branch_type, tokens
    return None, None, []


def parse_branch_candidate(value: str) -> tuple[str | None, str | None]:
    value = normalize_special_chars(normalize_korean_text(value).lower())
    patterns = (
        (r"([\uac00-\ud7a3a-z0-9 ]+?)\s*(?:\ubcf8\uc810|\uc9c1\uc601\uc810|\uc9c0\uc810)$", "STORE"),
        (r"([\uac00-\ud7a3a-z0-9 ]+?)\s*(?:\uc5ed\uc810|\uc810\ud3ec|\uc810|store)$", "STORE"),
        (r"([\uac00-\ud7a3a-z0-9 ]+?)\s*(?:r|reserve|\ub9ac\uc800\ube0c)$", "RESERVE"),
        (r"([\uac00-\ud7a3a-z0-9 ]+?)\s*(?:dt|drive thru|drive through|\ub4dc\ub77c\uc774\ube0c\uc2a4\ub8e8)$", "DRIVE_THROUGH"),
    )
    for pattern, branch_type in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            branch = remove_generic_tokens(match.group(1))
            return branch, branch_type
    return None, None


def remove_generic_tokens(value: str) -> str:
    normalized = normalize_special_chars(normalize_korean_text(value).lower())
    for token in (*REGION_NOISE_TOKENS, *GENERIC_NAME_TOKENS):
        normalized = re.sub(re.escape(token), " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def compact(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "")


def normalize_category(category: str | None) -> str:
    value = normalize_special_chars(normalize_korean_text(category).lower())
    value = value.replace(">", " ").replace("/", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_category_to_standard(category: str | None) -> StandardCategory:
    normalized = normalize_category(category)
    if has_any(normalized, CAFE_TERMS):
        return "cafe"
    if has_any(normalized, MEAL_TERMS):
        return "meal"
    if has_any(normalized, CULTURE_TERMS):
        return "culture"
    if has_any(normalized, SPOT_TERMS):
        return "spot"
    return "unknown"


def calculate_distance_meters(lat1, lon1, lat2, lon2) -> float | None:
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (TypeError, ValueError):
        return None
    radius_m = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_name_similarity(value: float) -> int:
    if value >= 0.95:
        return 25
    if value >= 0.90:
        return 22
    if value >= 0.80:
        return 18
    if value >= 0.65:
        return 12
    if value >= 0.50:
        return 6
    return 0


def score_distance(distance_meters: float | None) -> int:
    if distance_meters is None:
        return 0
    if distance_meters <= 50:
        return 25
    if distance_meters <= 100:
        return 20
    if distance_meters <= 200:
        return 12
    if distance_meters <= 300:
        return 5
    return 0


def score_category(base_place: dict, external_place: dict) -> int:
    role = (base_place.get("visit_role") or "").lower()
    category = normalize_category_to_standard(external_place.get("category"))
    if role == category:
        return 15
    if not external_place.get("category"):
        return 5
    if role == "cafe" and category == "meal":
        return 8
    return 3


def score_region(base_place: dict, external_place: dict) -> int:
    region = normalize_korean_text(str(base_place.get("region_1") or ""))
    address = normalize_korean_text(f"{external_place.get('address') or ''} {external_place.get('road_address') or ''}")
    return 10 if region and region in address else 5


def score_address(base_place: dict, external_place: dict) -> int:
    base_address = normalize_address(base_place.get("road_address") or base_place.get("address"))
    ext_address = normalize_address(external_place.get("road_address") or external_place.get("address"))
    if not base_address or not ext_address:
        return 0
    return 10 if base_address == ext_address else 5 if base_address[:6] == ext_address[:6] else -5


def score_phone(base_place: dict, external_place: dict) -> int:
    base_phone = normalize_phone(base_place.get("tel") or base_place.get("phone"))
    ext_phone = normalize_phone(external_place.get("phone"))
    if not base_phone or not ext_phone:
        return 0
    return 10 if base_phone == ext_phone else -10


def score_business_status(external_place: dict) -> int:
    status = (external_place.get("business_status") or "UNKNOWN").upper()
    if status == "OPEN":
        return 5
    if status == "CLOSED":
        return -20
    if status == "TEMP_CLOSED":
        return -5
    return 0


def detect_risk_flags(base_place: dict, external_place: dict, name_similarity: float, distance_meters: float | None) -> list[str]:
    flags: list[str] = []
    base_name = normalize_place_name_parts(base_place.get("name"))
    ext_name = normalize_place_name_parts(external_place.get("name"))
    same_chain = bool(base_name.chain_brand and base_name.chain_brand == ext_name.chain_brand)

    if distance_meters is not None and distance_meters > 300:
        flags.append("DISTANCE_TOO_FAR")
    if distance_meters is not None and distance_meters > 100:
        flags.append("DISTANCE_OVER_100M")
    if distance_meters is not None and distance_meters <= 30 and name_similarity < 0.80:
        flags.append("SAME_BUILDING_AMBIGUITY")
    if score_phone(base_place, external_place) < 0:
        flags.append("PHONE_CONFLICT")
    if score_address(base_place, external_place) < 0:
        flags.append("ADDRESS_CONFLICT")
    if score_category(base_place, external_place) <= 3:
        flags.append("CATEGORY_CONFLICT")
    if (external_place.get("business_status") or "").upper() == "CLOSED":
        flags.append("CLOSED_BUSINESS")
    if name_similarity < 0.65:
        flags.append("LOW_NAME_SIMILARITY")
    if not (external_place.get("address") or external_place.get("road_address")):
        flags.append("NO_ADDRESS")
    if not external_place.get("phone"):
        flags.append("NO_PHONE")
    if {"NO_ADDRESS", "NO_PHONE"} <= set(flags):
        flags.append("LOW_EVIDENCE")
    if base_name.is_chain_brand or ext_name.is_chain_brand:
        flags.append("CHAIN_BRAND_RISK")
    if same_chain and base_name.branch_name and ext_name.branch_name and base_name.branch_name != ext_name.branch_name:
        flags.append("BRANCH_MISMATCH")
    if same_chain and not (base_name.branch_name and ext_name.branch_name):
        flags.append("CHAIN_BRANCH_LOW_EVIDENCE")
    return flags


def score_risk_penalty(flags: list[str]) -> int:
    penalty = 0
    if "CHAIN_BRAND_RISK" in flags:
        penalty -= 8
    if "LOW_EVIDENCE" in flags:
        penalty -= 8
    if "CATEGORY_CONFLICT" in flags:
        penalty -= 20
    if "DISTANCE_TOO_FAR" in flags:
        penalty -= 20
    if "BRANCH_MISMATCH" in flags:
        penalty -= 20
    if "SAME_BUILDING_AMBIGUITY" in flags:
        penalty -= 12
    if "CHAIN_BRANCH_LOW_EVIDENCE" in flags:
        penalty -= 6
    return max(-35, penalty)


def score_based_decision(score: int) -> tuple[ConfidenceLevel, MatchDecision]:
    if score >= 85:
        return "HIGH", "AUTO_APPROVE"
    if score >= 70:
        return "MEDIUM", "MANUAL_REVIEW"
    if score >= 50:
        return "LOW", "LOW_CONFIDENCE"
    return "REJECT", "REJECT"


def build_reasons(breakdown: dict[str, int], risk_flags: list[str]) -> list[str]:
    reasons = [f"{key}={value}" for key, value in breakdown.items()]
    reasons.extend(f"risk:{flag}" for flag in risk_flags)
    return reasons


def build_normalized_payload(
    base_place: dict,
    external_place: dict,
    base_name: NormalizedName,
    external_name: NormalizedName,
) -> dict:
    return {
        "normalization": {
            "unicode_policy": "NFKC",
            "base": {
                "raw_name": base_name.raw_name,
                "normalized_name": base_name.normalized_name,
                "compact_name": base_name.compact_name,
                "match_name": base_name.match_name,
                "base_name": base_name.base_name,
                "chain_brand": base_name.chain_brand,
                "chain_alias_matched": base_name.chain_alias_matched,
                "is_chain_brand": base_name.is_chain_brand,
                "branch_name": base_name.branch_name,
                "branch_type": base_name.branch_type,
                "branch_tokens": base_name.branch_tokens,
                "visit_role": base_place.get("visit_role"),
            },
            "external": {
                "raw_name": external_name.raw_name,
                "normalized_name": external_name.normalized_name,
                "compact_name": external_name.compact_name,
                "match_name": external_name.match_name,
                "base_name": external_name.base_name,
                "chain_brand": external_name.chain_brand,
                "chain_alias_matched": external_name.chain_alias_matched,
                "is_chain_brand": external_name.is_chain_brand,
                "branch_name": external_name.branch_name,
                "branch_type": external_name.branch_type,
                "branch_tokens": external_name.branch_tokens,
                "source_category": external_place.get("category"),
                "normalized_category": normalize_category_to_standard(external_place.get("category")),
            },
        }
    }


def normalize_phone(phone: str | None) -> str:
    return re.sub(r"\D+", "", phone or "")


def normalize_address(address: str | None) -> str:
    value = normalize_korean_text(address).lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", "", value)
    return value


def is_chain_brand(name: str | None) -> bool:
    return normalize_place_name_parts(name).is_chain_brand


def has_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in value for term in terms)

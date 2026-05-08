from __future__ import annotations

from batch.place_enrichment.matching.decision_engine import MatchDecisionEngine
from batch.place_enrichment.matching.scoring import (
    calculate_place_match_score,
    is_chain_brand,
    normalize_category_to_standard,
    normalize_place_name_parts,
)


SEOUL = "\uc11c\uc6b8"
STARBUCKS = "\uc2a4\ud0c0\ubc85\uc2a4"
GANGNAM = "\uac15\ub0a8"
YEOKSAM = "\uc5ed\uc0bc"


def test_korean_space_and_parentheses_branch_normalization():
    left = normalize_place_name_parts(f"{STARBUCKS} {GANGNAM}\uc810")
    right = normalize_place_name_parts(f"{STARBUCKS}({GANGNAM}\uc810)")

    assert left.chain_brand == STARBUCKS
    assert right.chain_brand == STARBUCKS
    assert left.branch_name == GANGNAM
    assert right.branch_name == GANGNAM
    assert left.match_name == right.match_name == STARBUCKS


def test_mixed_english_korean_chain_normalization():
    left = normalize_place_name_parts(f"{STARBUCKS} {GANGNAM}\uc810")
    right = normalize_place_name_parts(f"STARBUCKS {GANGNAM}")

    assert right.chain_brand == STARBUCKS
    assert left.branch_name == right.branch_name == GANGNAM
    assert left.is_chain_brand is True
    assert right.is_chain_brand is True


def test_branch_suffix_r_and_dt_are_detected():
    reserve = normalize_place_name_parts(f"{STARBUCKS} {GANGNAM}R")
    drive_through = normalize_place_name_parts(f"{STARBUCKS} {GANGNAM}DT")

    assert reserve.branch_name == GANGNAM
    assert reserve.branch_type == "RESERVE"
    assert drive_through.branch_name == GANGNAM
    assert drive_through.branch_type == "DRIVE_THROUGH"


def test_chain_cafe_detection_aliases():
    assert is_chain_brand(f"{STARBUCKS} {GANGNAM}\uc810")
    assert is_chain_brand(f"STARBUCKS {GANGNAM}")
    assert is_chain_brand("\uba54\uac00\ucee4\ud53c \ud64d\ub300\uc810")
    assert is_chain_brand("\ucef4\ud3ec\uc988\ucee4\ud53c \ud569\uc815\uc810")
    assert is_chain_brand("\ube7d\ub2e4\ubc29 \uc2e0\ucd0c\uc810")


def test_category_variations_map_to_cafe():
    categories = [
        "\uce74\ud398,\ub514\uc800\ud2b8>\uce74\ud398",
        "\uce74\ud398 > \ub514\uc800\ud2b8",
        "CAFE",
        "\ucee4\ud53c\uc804\ubb38\uc810",
    ]

    assert {normalize_category_to_standard(category) for category in categories} == {"cafe"}


def test_branch_mismatch_blocks_chain_auto_approval():
    base = {
        "name": f"{STARBUCKS} {GANGNAM}\uc810",
        "visit_role": "cafe",
        "region_1": SEOUL,
        "latitude": 37.5000,
        "longitude": 127.0250,
        "road_address": f"{SEOUL} \uac15\ub0a8\uad6c \ud14c\ud5e4\ub780\ub85c 1",
    }
    external = {
        "name": f"{STARBUCKS} {YEOKSAM}\uc810",
        "category": "\uce74\ud398,\ub514\uc800\ud2b8>\uce74\ud398",
        "latitude": 37.5001,
        "longitude": 127.0251,
        "road_address": f"{SEOUL} \uac15\ub0a8\uad6c \ud14c\ud5e4\ub780\ub85c 1",
        "phone": "02-123-4567",
        "business_status": "OPEN",
    }

    result = calculate_place_match_score(base, external)
    final = MatchDecisionEngine().evaluate_match_decision(result)

    assert "BRANCH_MISMATCH" in result.risk_flags
    assert final.blocked is True
    assert final.final_decision == "REJECT"


def test_same_building_ambiguity_for_nearby_different_name():
    base = {
        "name": "\uace0\ub77c\ub2c8\ucee4\ud53c\ud074\ub7fd",
        "visit_role": "cafe",
        "region_1": SEOUL,
        "latitude": 37.5665,
        "longitude": 126.9780,
        "road_address": f"{SEOUL} \uc911\uad6c \uc138\uc885\ub300\ub85c 110",
    }
    external = {
        "name": "\uace0\ub77c\ub2c8 \ubca0\uc774\ud06c\ub4dc",
        "category": "\uce74\ud398,\ub514\uc800\ud2b8>\uce74\ud398",
        "latitude": 37.56651,
        "longitude": 126.97801,
        "road_address": f"{SEOUL} \uc911\uad6c \uc138\uc885\ub300\ub85c 110",
        "phone": "",
        "business_status": "OPEN",
    }

    result = calculate_place_match_score(base, external)
    final = MatchDecisionEngine().evaluate_match_decision(result)

    assert "SAME_BUILDING_AMBIGUITY" in result.risk_flags
    assert final.review_required is True or final.blocked is True

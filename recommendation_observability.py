"""Recommendation trace helpers.

Keep observability logic separate from ranking logic. Helpers in this module
only summarize already-computed candidates/results; they must not mutate score
inputs or alter selection behavior.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any


_CITY_ALIASES: dict[str, set[str]] = {
    "전주": {"전주", "전주시", "전주역", "한옥마을", "전주한옥마을", "객사", "경기전", "청연루", "남부시장"},
    "군산": {"군산", "군산시", "군산근대거리", "군산근대문화거리", "군산근대역사박물관", "군산역", "근대거리"},
    "익산": {"익산", "익산시", "익산역", "중앙동", "미륵사지"},
    "남원": {"남원", "남원시", "광한루", "광한루원"},
    "고창": {"고창", "고창군", "고창읍성"},
    "부안": {"부안", "부안군", "채석강", "변산", "변산반도"},
    "정읍": {"정읍", "정읍시", "정읍역", "내장산"},
    "제주": {"제주", "제주시", "서귀포", "서귀포시"},
    "강릉": {"강릉", "강릉시"},
    "부산": {"부산", "부산시"},
}


def _normalize(value: Any) -> str:
    return re.sub(r"[\s\-\(\)\[\],·/]", "", str(value or "").strip().lower())




def _classify_support_role(place: dict[str, Any] | None) -> str:
    """Classify selected place role for observability only.

    This helper is intentionally coarse and must not be used for filtering or
    scoring. It exists to expose route role-sequence shape in traces before any
    future bounded diversity logic is considered.
    """
    if not isinstance(place, dict):
        return "other"

    text = " ".join(
        str(place.get(key) or "")
        for key in (
            "visit_role",
            "role",
            "category",
            "category_name",
            "place_name",
            "name",
            "description",
        )
    ).lower()

    # Streets such as "cafe street" should behave as walk/support texture,
    # not as another cafe stop in role-repetition traces.
    if any(term in text for term in ("\uce74\ud398\uac70\ub9ac", "\ub85c\ub370\uc624\uac70\ub9ac", "\uc74c\uc2dd\ubb38\ud654\uac70\ub9ac")):
        return "walk"

    role_terms = {
        "cafe": ("\uce74\ud398", "coffee", "\ub85c\uc2a4\ud130", "\ubca0\uc774\ucee4\ub9ac", "\ucc3b\uc9d1"),
        "meal": ("\ub9db\uc9d1", "\uc2dd\ub2f9", "\uc74c\uc2dd", "\uad6d\ubc25", "\uac08\ube44", "\ud574\uc7a5", "\ubd84\uc2dd", "restaurant", "meal"),
        "walk": ("\uacf5\uc6d0", "\uc0b0\ucc45", "\uc232", "\uae38", "\uac70\ub9ac", "\uace8\ubaa9", "\uc218\ubcc0", "\ud574\ubcc0", "\ud574\uc218\uc695\uc7a5", "\ud638\uc218", "\uac15", "\ucc9c", "\ud574\uc548"),
        "viewpoint": ("\uc804\ub9dd", "\uc57c\uacbd", "\ud0c0\uc6cc", "\ubdf0", "\ub300\uad50", "\ub8e8\ud504\ud0d1", "\uc804\ub9dd\ub300"),
        "market": ("\uc2dc\uc7a5", "\ub9c8\ucf13", "\uc57c\uc2dc\uc7a5"),
        "gallery": ("\uac24\ub7ec\ub9ac", "\uc804\uc2dc", "\ubbf8\uc220", "\ubc15\ubb3c\uad00", "\ubb38\ud654", "\uacf5\uc608", "\uccb4\ud5d8", "gallery"),
        "landmark_support": ("\uad81", "\uc131", "\uc0ac\ucc30", "\ud55c\uc625", "\uc5ed\uc0ac", "\uc720\uc801", "\uc804\ud1b5", "landmark"),
        "indoor": ("\uc2e4\ub0b4", "\uc13c\ud130", "\ud68c\uad00", "\ub3c4\uc11c\uad00", "\uc544\ud2b8\ud640", "\ub77c\uc6b4\uc9c0"),
    }
    for role_name, terms in role_terms.items():
        if any(term in text for term in terms):
            return role_name
    return "other"


def summarize_support_slot_roles(selected_places: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Return role-sequence observability for selected route support slots.

    The first selected place is treated as the anchor/main slot. All following
    places are support slots for this trace. No score, route order, or selected
    candidate is changed here.
    """
    places = [p for p in (selected_places or []) if isinstance(p, dict)]
    support_places = places[1:] if len(places) > 1 else []
    sequence = [_classify_support_role(place) for place in support_places]

    repetitions: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(sequence, sequence[1:]), start=1):
        if left == right and left != "other":
            repetitions.append({
                "role": left,
                "from_support_index": index,
                "to_support_index": index + 1,
            })

    counts: Counter[str] = Counter(sequence)
    indoor_count = sum(1 for role in sequence if role in {"indoor", "gallery"})
    preferred_roles = {"walk", "viewpoint", "market", "gallery", "landmark_support"}
    missing_preferred = sorted(role for role in preferred_roles if role not in counts)
    balance_score = 1.0
    if sequence:
        repeated_penalty = min(0.45, 0.18 * len(repetitions))
        indoor_penalty = 0.15 if indoor_count >= max(2, len(sequence) - 1) else 0.0
        narrow_penalty = 0.15 if len(counts) <= 2 and len(sequence) >= 4 else 0.0
        balance_score = max(0.0, round(1.0 - repeated_penalty - indoor_penalty - narrow_penalty, 4))

    return {
        "support_slot_role_sequence": sequence,
        "support_slot_role_repetition": repetitions,
        "support_slot_indoor_count": indoor_count,
        "support_slot_role_counts": dict(counts),
        "support_slot_missing_preferred_roles": missing_preferred,
        "support_slot_role_balance_score": balance_score,
    }


def _gangnam_support_tag(place: dict[str, Any] | None) -> str:
    """Classify Gangnam support-slot editorial fit for trace only."""
    if not isinstance(place, dict):
        return "other"
    text = " ".join(
        str(place.get(key) or "")
        for key in (
            "visit_role",
            "role",
            "category",
            "category_name",
            "place_name",
            "name",
            "description",
        )
    ).lower()
    normalized = _normalize(text)
    checks = (
        ("coex_family", ("\ucf54\uc5d1\uc2a4", "coex", "\ubcc4\ub9c8\ub2f9", "starfield", "\uc2a4\ud0c0\ud544\ub4dc")),
        ("garosugil_walk", ("\uac00\ub85c\uc218\uae38", "\uc2e0\uc0ac\ub3d9", "\ub85c\ub370\uc624\uac70\ub9ac")),
        ("apgujeong_cheongdam_lifestyle", ("\uc555\uad6c\uc815", "\uccad\ub2f4", "\ud328\uc158", "\uac24\ub7ec\ub9ac", "\ud3b8\uc9d1\uc20d")),
        ("bongeunsa_heritage", ("\ubd09\uc740\uc0ac", "\uc120\uc815\ub989", "\uc120\ub989", "\uc815\ub989", "\uc720\ub124\uc2a4\ucf54")),
        ("weak_public_training", ("\uad6d\uae30\uc6d0", "\uad6d\uac00\ubb34\ud615\uc720\uc0b0\uc804\uc218\uad50\uc721\uad00", "\uc804\uc218\uad50\uc721\uad00", "\ud0dc\uad8c\ub3c4")),
        ("weak_indoor_education", ("\ud55c\uc0dd\uc5f0", "\uc2e4\ud5d8\ub204\ub9ac", "\uacfc\ud559\uad00", "\uad50\uc721", "\ub3c4\uc11c\uad00")),
        ("weak_culture_hall", ("\uc288\ud53c\uac90\ud640", "\ud640", "\ubb38\ud654\ub9c8\ub8e8", "\ud68c\uad00")),
        ("weak_lifestyle", ("\ubc18\ub824\ubb38\ud654",)),
        ("weak_generic_meal", ("\uc9c4\uc218\uc0ac", "\ucf74\uc548\ub2e4\uc624", "\uc54c\ub77c\ud504\ub9ac\ub9c8", "\ud1a0\ub9d0", "\uacf1\ucc3d")),
    )
    for tag, terms in checks:
        if any(term in text or _normalize(term) in normalized for term in terms):
            return tag
    role = str(place.get("visit_role") or "").strip().lower()
    if role == "meal":
        return "weak_generic_meal"
    if role == "cafe":
        return "curated_cafe_walk_support"
    if _classify_support_role(place) == "walk":
        return "curated_cafe_walk_support"
    return "other"


def summarize_gangnam_editorial_support(
    selected_places: list[dict[str, Any]] | None,
    selected_anchor_raw: Any,
) -> dict[str, Any]:
    """Expose Gangnam support-slot editorial quality signals without scoring."""
    anchor_text = _normalize(selected_anchor_raw)
    if not any(term in anchor_text for term in (_normalize("\uac15\ub0a8"), _normalize("\ucf54\uc5d1\uc2a4"), _normalize("\uac00\ub85c\uc218\uae38"), _normalize("\uc555\uad6c\uc815"), _normalize("\uccad\ub2f4"))):
        return {
            "gangnam_editorial_support_fit": None,
            "gangnam_weak_public_support_risk": None,
            "gangnam_repeated_generic_meal_support": None,
            "gangnam_support_candidate_tags": [],
        }

    places = [p for p in (selected_places or []) if isinstance(p, dict)]
    support_places = places[1:] if len(places) > 1 else []
    positive_tags = {
        "coex_family",
        "garosugil_walk",
        "apgujeong_cheongdam_lifestyle",
        "bongeunsa_heritage",
        "curated_cafe_walk_support",
    }
    weak_public_tags = {"weak_public_training", "weak_indoor_education", "weak_culture_hall", "weak_lifestyle"}
    tag_rows: list[dict[str, Any]] = []
    for index, place in enumerate(support_places, start=1):
        tag = _gangnam_support_tag(place)
        tag_rows.append({
            "support_index": index,
            "place_name": place.get("place_name") or place.get("name"),
            "visit_role": place.get("visit_role"),
            "tag": tag,
            "positive_fit": tag in positive_tags,
            "weak_public_risk": tag in weak_public_tags,
            "generic_meal_risk": tag == "weak_generic_meal",
        })

    support_count = len(tag_rows)
    positive_count = sum(1 for row in tag_rows if row["positive_fit"])
    weak_public_rows = [row for row in tag_rows if row["weak_public_risk"]]
    generic_meal_rows = [row for row in tag_rows if row["generic_meal_risk"]]
    repeated_meal_names = [
        name for name, count in Counter(row["place_name"] for row in generic_meal_rows).items()
        if name and count >= 1
    ]

    return {
        "gangnam_editorial_support_fit": {
            "support_count": support_count,
            "positive_fit_count": positive_count,
            "fit_ratio": round(positive_count / support_count, 4) if support_count else None,
        },
        "gangnam_weak_public_support_risk": {
            "count": len(weak_public_rows),
            "candidates": weak_public_rows,
        },
        "gangnam_repeated_generic_meal_support": {
            "count": len(generic_meal_rows),
            "candidates": generic_meal_rows,
            "candidate_names": repeated_meal_names,
        },
        "gangnam_support_candidate_tags": tag_rows,
    }


def infer_city_token(place: dict[str, Any] | None) -> str:
    """Infer a coarse city token from place metadata for QA/trace only."""
    if not isinstance(place, dict):
        return "unknown"

    terms: list[str] = []
    for key in ("city", "region_2", "region", "region_1", "name", "address", "addr", "address_name", "overview"):
        value = place.get(key)
        if value:
            terms.append(str(value))

    joined = "|".join(_normalize(term) for term in terms)
    for city, aliases in _CITY_ALIASES.items():
        if any(_normalize(alias) and _normalize(alias) in joined for alias in aliases):
            return city
    return "unknown"


def summarize_city_distribution(scored_candidates: list[Any], limit: int = 5) -> dict[str, int]:
    """Summarize city distribution for top scored candidate tuples."""
    counter: Counter[str] = Counter()
    for item in (scored_candidates or [])[:limit]:
        place = item[4] if isinstance(item, tuple) and len(item) >= 5 else item
        counter[infer_city_token(place)] += 1
    return dict(counter)


def summarize_scored_candidates(scored_candidates: list[Any], limit: int = 8) -> list[dict[str, Any]]:
    """Return compact candidate score breakdown for trace logs."""
    rows: list[dict[str, Any]] = []
    for item in (scored_candidates or [])[:limit]:
        if not isinstance(item, tuple) or len(item) < 5:
            continue
        score, travel_min, dist_km, components, place = item
        components = components or {}
        place = place or {}
        rows.append({
            "place_name": place.get("name"),
            "place_id": place.get("place_id"),
            "city_token": infer_city_token(place),
            "base_score": round(float(score or 0), 4),
            "locality_bonus": components.get("locality_bonus", 0.0),
            "wrong_city_demote": components.get("wrong_city_demote", 0.0),
            "distance_score": components.get("travel_fit", 0.0),
            "city_intent_score": components.get("city_intent_score", 0.0),
            "inferred_belt": components.get("inferred_belt"),
            "belt_confidence": components.get("belt_confidence", 0.0),
            "belt_match_bonus": components.get("belt_match_bonus", 0.0),
            "belt_match_reasons": components.get("belt_match_reasons") or [],
            "candidate_belt_match": bool(components.get("candidate_belt_match")),
            "candidate_belt_affinity": components.get("candidate_belt_affinity", 0.0),
            "wrong_belt_match": components.get("wrong_belt_match"),
            "dominant_belt": components.get("dominant_belt"),
            "dominant_belt_bonus": components.get("dominant_belt_bonus", 0.0),
            "dominant_belt_reasons": components.get("dominant_belt_reasons") or [],
            "inferred_flow_profile": components.get("inferred_flow_profile"),
            "slot_flow_alignment": components.get("slot_flow_alignment", 0.0),
            "continuity_bonus": components.get("continuity_bonus", 0.0),
            "flow_break_candidate": bool(components.get("flow_break_candidate")),
            "flow_match_reasons": components.get("flow_match_reasons") or [],
            "suitability_profile": components.get("suitability_profile"),
            "vibe_suitability_score": components.get("vibe_suitability_score", 0.0),
            "tourism_suitability_score": components.get("tourism_suitability_score", 0.0),
            "suitability_bonus": components.get("suitability_bonus", 0.0),
            "suitability_soft_demote": components.get("suitability_soft_demote", 0.0),
            "public_facility_demote": components.get("public_facility_demote", 0.0),
            "representative_tourism_fit": components.get("representative_tourism_fit", 0.0),
            "weak_public_facility_reason": components.get("weak_public_facility_reason"),
            "vibe_match_reasons": components.get("vibe_match_reasons") or [],
            "soft_demote_reason": components.get("soft_demote_reason"),
            "meal_cafe_profile": components.get("meal_cafe_profile"),
            "meal_vibe_score": components.get("meal_vibe_score", 0.0),
            "meal_experience_score": components.get("meal_experience_score", 0.0),
            "meal_soft_demote_reason": components.get("meal_soft_demote_reason"),
            "local_food_bonus": components.get("local_food_bonus", 0.0),
            "view_bonus": components.get("view_bonus", 0.0),
            "meal_cafe_bonus": components.get("meal_cafe_bonus", 0.0),
            "meal_cafe_soft_demote": components.get("meal_cafe_soft_demote", 0.0),
            "meal_cafe_match_reasons": components.get("meal_cafe_match_reasons") or [],
            "same_role_soft_demote_applied": bool(components.get("same_role_soft_demote_applied")),
            "same_role_soft_demote_role": components.get("same_role_soft_demote_role"),
            "same_role_soft_demote_delta": components.get("same_role_soft_demote_delta", 0.0),
            "route_contamination_demote": components.get("route_contamination_demote", 0.0),
            "route_contamination_flags": components.get("route_contamination_flags") or [],
            "route_contamination_reasons": components.get("route_contamination_reasons") or [],
            "route_positive_matches": components.get("route_positive_matches") or [],
            "religious_facility_demote": components.get("religious_facility_demote", 0.0),
            "religious_tourism_exception": components.get("religious_tourism_exception") or [],
            "coastal_vibe_score": components.get("coastal_vibe_score", 0.0),
            "night_view_score": components.get("night_view_score", 0.0),
            "harbor_alignment": components.get("harbor_alignment", 0.0),
            "sea_route_continuity": components.get("sea_route_continuity", 0.0),
            "inland_contamination_flags": components.get("inland_contamination_flags") or [],
            "editorial_bonus": components.get("editorial_bonus", 0.0),
            "editorial_demote": components.get("editorial_demote", 0.0),
            "editorial_demote_reason": components.get("editorial_demote_reason"),
            "weak_first_place_reason": components.get("weak_first_place_reason"),
            "central_drift_reason": components.get("central_drift_reason"),
            "landmark_priority_score": components.get("landmark_priority_score", 0.0),
            "representative_vibe_score": components.get("representative_vibe_score", 0.0),
            "weak_indoor_demote": components.get("weak_indoor_demote", 0.0),
            "landmark_alignment_reason": components.get("landmark_alignment_reason"),
            "seongsu_vibe_score": components.get("seongsu_vibe_score", 0.0),
            "cafe_street_alignment": components.get("cafe_street_alignment", 0.0),
            "weak_meal_demote": components.get("weak_meal_demote", 0.0),
            "editorial_first_place_bonus": components.get("editorial_first_place_bonus", 0.0),
            "euljiro_night_score": components.get("euljiro_night_score", 0.0),
            "hipjiro_alignment": components.get("hipjiro_alignment", 0.0),
            "central_drift_demote": components.get("central_drift_demote", 0.0),
            "night_vibe_bonus": components.get("night_vibe_bonus", 0.0),
            "seoul_date_score": components.get("seoul_date_score", 0.0),
            "date_vibe_alignment": components.get("date_vibe_alignment", 0.0),
            "broad_seoul_drift_demote": components.get("broad_seoul_drift_demote", 0.0),
            "romantic_walk_bonus": components.get("romantic_walk_bonus", 0.0),
            "busan_night_meal_score": components.get("busan_night_meal_score", 0.0),
            "waterfront_alignment": components.get("waterfront_alignment", 0.0),
            "weak_daytime_meal_demote": components.get("weak_daytime_meal_demote", 0.0),
            "night_meal_bonus": components.get("night_meal_bonus", 0.0),
            "curated_night_family_applied": bool(components.get("curated_night_family_applied")),
            "night_representative_preference": components.get("night_representative_preference", 0.0),
            "nightlife_curated_alignment": components.get("nightlife_curated_alignment", 0.0),
            "night_vibe_coherence": components.get("night_vibe_coherence", 0.0),
            "curated_night_support_slot": components.get("curated_night_support_slot", 0.0),
            "curated_night_match_terms": components.get("curated_night_match_terms") or [],
            "curated_night_weak_demote": components.get("curated_night_weak_demote", 0.0),
            "busan_landmark_priority_score": components.get("busan_landmark_priority_score", 0.0),
            "busan_representative_bonus": components.get("busan_representative_bonus", 0.0),
            "busan_landmark_alignment_reason": components.get("busan_landmark_alignment_reason"),
            "representative_tourism_family_score": components.get("representative_tourism_family_score", 0.0),
            "indoor_culture_fallback_demote": components.get("indoor_culture_fallback_demote", 0.0),
            "regional_landmark_density": components.get("regional_landmark_density", 0.0),
            "first_place_representative_bonus": components.get("first_place_representative_bonus", 0.0),
            "jinju_history_first_place_bonus": components.get("jinju_history_first_place_bonus", 0.0),
            "tongyeong_same_city_bonus": components.get("tongyeong_same_city_bonus", 0.0),
            "tongyeong_geoje_drift_demote": components.get("tongyeong_geoje_drift_demote", 0.0),
            "gimhae_gaya_family_score": components.get("gimhae_gaya_family_score", 0.0),
            "gimhae_support_slot_family_score": components.get("gimhae_support_slot_family_score", 0.0),
            "gimhae_support_slot_drift_demote": components.get("gimhae_support_slot_drift_demote", 0.0),
            "support_slot_coherence_score": components.get("support_slot_coherence_score", 0.0),
            "seoul_default_representative_score": components.get("seoul_default_representative_score", 0.0),
            "seoul_default_weak_first_place_demote": components.get("seoul_default_weak_first_place_demote", 0.0),
            "seoul_broad_default_family_balance": components.get("seoul_broad_default_family_balance", 0.0),
            "seoul_curated_district_priority": components.get("seoul_curated_district_priority", 0.0),
            "broad_seoul_demoted": components.get("broad_seoul_demoted", 0.0),
            "district_identity_alignment": components.get("district_identity_alignment", 0.0),
            "support_slot_role_diversity": components.get("support_slot_role_diversity", 0.0),
            "bukchon_editorial_depth_score": components.get("bukchon_editorial_depth_score", 0.0),
            "seongsu_editorial_depth_score": components.get("seongsu_editorial_depth_score", 0.0),
            "lifestyle_support_slot_visibility": components.get("lifestyle_support_slot_visibility", 0.0),
            "representative_family_rotation_balance": components.get("representative_family_rotation_balance", 0.0),
            "seoul_broad_family_key": components.get("seoul_broad_family_key"),
            "seoul_broad_family_matches": components.get("seoul_broad_family_matches") or [],
            "bukchon_editorial_depth_matches": components.get("bukchon_editorial_depth_matches") or [],
            "seongsu_editorial_depth_matches": components.get("seongsu_editorial_depth_matches") or [],
            "bukchon_lifestyle_drift_matches": components.get("bukchon_lifestyle_drift_matches") or [],
            "seongsu_support_slot_drift_matches": components.get("seongsu_support_slot_drift_matches") or [],
            "seoul_editorial_depth_pool_included": bool(components.get("seoul_editorial_depth_pool_included")),
            "bukchon_editorial_candidate_exists": bool(components.get("bukchon_editorial_candidate_exists")),
            "bukchon_lifestyle_support_slot_score": components.get("bukchon_lifestyle_support_slot_score", 0.0),
            "seongsu_editorial_candidate_exists": bool(components.get("seongsu_editorial_candidate_exists")),
            "seongsu_support_slot_coherence": components.get("seongsu_support_slot_coherence", 0.0),
            "editorial_lifestyle_visibility_bonus": components.get("editorial_lifestyle_visibility_bonus", 0.0),
            "weak_museum_first_place_demote": components.get("weak_museum_first_place_demote", 0.0),
            "landmark_authority_score": components.get("landmark_authority_score", 0.0),
            "popularity_signal": components.get("popularity_signal", 0.0),
            "popularity_authority_score": components.get("popularity_authority_score", 0.0),
            "landmark_confidence": components.get("landmark_confidence", 0.0),
            "representative_tourism_bonus": components.get("representative_tourism_bonus", 0.0),
            "tourism_representative_score": components.get("tourism_representative_score", 0.0),
            "normalized_popularity_hint": components.get("normalized_popularity_hint", 0.0),
            "external_verified_score": components.get("external_verified_score", 0.0),
            "external_popularity_score": components.get("external_popularity_score", 0.0),
            "public_data_weakness_penalty": components.get("public_data_weakness_penalty", 0.0),
            "public_data_weakness_reason": components.get("public_data_weakness_reason"),
            "representative_confidence_score": components.get("representative_confidence_score", 0.0),
            "image_density_score": components.get("image_density_score", 0.0),
            "review_density_hint": components.get("review_density_hint", 0.0),
            "curated_representative_priority": components.get("curated_representative_priority", 0.0),
            "verified_api_candidate": bool(components.get("verified_api_candidate")),
            "public_fallback_used": bool(components.get("public_fallback_used")),
            "weak_public_contamination_demote": components.get("weak_public_contamination_demote", 0.0),
            "curated_support_slot_alignment": components.get("curated_support_slot_alignment", 0.0),
            "curated_representative_matches": components.get("curated_representative_matches") or [],
            "landmark_authority_matches": components.get("landmark_authority_matches") or [],
            "landmark_authority_reason": components.get("landmark_authority_reason"),
            "landmark_authority_source_policy": components.get("landmark_authority_source_policy"),
            "alias_normalization_match": components.get("alias_normalization_match") or [],
            "region_aware_alias_guard": components.get("region_aware_alias_guard"),
            "wrong_region_alias_demote": components.get("wrong_region_alias_demote", 0.0),
            "family_candidate_lookup_bonus": components.get("family_candidate_lookup_bonus", 0.0),
            "representative_alias_pool_included": bool(components.get("representative_alias_pool_included")),
            "weak_generic_authority_demote": components.get("weak_generic_authority_demote", 0.0),
            "weak_generic_authority_reason": components.get("weak_generic_authority_reason"),
            "image_available": bool(components.get("image_available")),
            "image_quality_bonus": components.get("image_quality_bonus", 0.0),
            "no_image_first_place_demote": components.get("no_image_first_place_demote", 0.0),
            "placeholder_used": bool(components.get("placeholder_used")),
            "indoor_leisure_demote": components.get("indoor_leisure_demote", 0.0),
            "indoor_leisure_reason": components.get("indoor_leisure_reason"),
            "default_preset_mode": bool(components.get("default_preset_mode")),
            "representative_landmark_selected": bool(components.get("representative_landmark_selected")),
            "default_preset_landmark_bonus": components.get("default_preset_landmark_bonus", 0.0),
            "weird_candidate_demote": components.get("weird_candidate_demote", 0.0),
            "weird_candidate_demote_reason": components.get("weird_candidate_demote_reason"),
            "first_place_repeat_count": components.get("first_place_repeat_count", 0),
            "first_place_saturation_penalty": components.get("first_place_saturation_penalty", 0.0),
            "diversity_rotation_bonus": components.get("diversity_rotation_bonus", 0.0),
            "representative_pool_size": components.get("representative_pool_size", 1),
            "regenerate_diversity_applied": bool(components.get("regenerate_diversity_applied")),
            "representative_family_pool_size": components.get("representative_family_pool_size", 0),
            "representative_family_rotation_bonus": components.get("representative_family_rotation_bonus", 0.0),
            "representative_family_saturation_penalty": components.get("representative_family_saturation_penalty", 0.0),
            "representative_family_first_place_repeat": components.get("representative_family_first_place_repeat", 0),
            "representative_family_diversity_applied": bool(components.get("representative_family_diversity_applied")),
            "regenerate_repeat_penalty": components.get("regenerate_repeat_penalty", components.get("representative_family_saturation_penalty", 0.0)),
            "representative_family_rotation_applied": bool(components.get("representative_family_rotation_applied", components.get("representative_family_diversity_applied"))),
            "description_quality_variant": components.get("description_quality_variant"),
            "generic_copy_demote": components.get("generic_copy_demote", 0.0),
            "representative_candidate_pool_included": bool(components.get("representative_candidate_pool_included")),
            "representative_candidate_pool_reason": components.get("representative_candidate_pool_reason"),
            "representative_pool_cutoff_score": components.get("representative_pool_cutoff_score"),
            "representative_pool_competitor_count": components.get("representative_pool_competitor_count", 0),
            "weak_museum_pool_demote": components.get("weak_museum_pool_demote", 0.0),
            "selected_anchor_family_id": components.get("selected_anchor_family_id"),
            "selected_anchor_family_match_score": components.get("selected_anchor_family_match_score", 0.0),
            "selected_anchor_family_preserved": bool(components.get("selected_anchor_family_preserved")),
            "selected_anchor_family_matched_terms": components.get("selected_anchor_family_matched_terms") or [],
            "selected_anchor_family_drift_demote": components.get("selected_anchor_family_drift_demote", 0.0),
            "selected_anchor_drift_reason": components.get("selected_anchor_drift_reason"),
            "fallback_level_used": components.get("fallback_level_used"),
            "busan_oldtown_family_score": components.get("busan_oldtown_family_score", 0.0),
            "busan_oldtown_pool_included": bool(components.get("busan_oldtown_pool_included")),
            "busan_oldtown_drift_demote": components.get("busan_oldtown_drift_demote", 0.0),
            "busan_oldtown_support_slot_score": components.get("busan_oldtown_support_slot_score", 0.0),
            "busan_oldtown_expected_landmark_visible": bool(components.get("busan_oldtown_expected_landmark_visible")),
            "busan_oldtown_match_terms": components.get("busan_oldtown_match_terms") or [],
            "exact_landmark_visibility_score": components.get("exact_landmark_visibility_score", 0.0),
            "exact_landmark_pool_included": bool(components.get("exact_landmark_pool_included")),
            "exact_landmark_support_slot_bonus": components.get("exact_landmark_support_slot_bonus", 0.0),
            "exact_support_slot_visibility_bonus": components.get("exact_support_slot_visibility_bonus", 0.0),
            "exact_support_slot_replacement_applied": bool(components.get("exact_support_slot_replacement_applied")),
            "exact_landmark_final_route_visible": bool(components.get("exact_landmark_final_route_visible")),
            "exact_slot_alignment_bonus": components.get("exact_slot_alignment_bonus", 0.0),
            "exact_anchor_final_visibility": bool(components.get("exact_anchor_final_visibility")),
            "oldtown_substitute_demote": components.get("oldtown_substitute_demote", 0.0),
            "oldtown_candidate_replaced": components.get("oldtown_candidate_replaced"),
            "support_slot_visibility_reason": components.get("support_slot_visibility_reason"),
            "exact_landmark_missing_reason": components.get("exact_landmark_missing_reason"),
            "weak_substitute_demote": components.get("weak_substitute_demote", 0.0),
            "exact_landmark_match_terms": components.get("exact_landmark_match_terms") or [],
            "exact_landmark_focus_match_terms": components.get("exact_landmark_focus_match_terms") or [],
            "seomyeon_family_score": components.get("seomyeon_family_score", 0.0),
            "seomyeon_family_pool_included": bool(components.get("seomyeon_family_pool_included")),
            "seomyeon_nightlife_pool_included": bool(components.get("seomyeon_nightlife_pool_included")),
            "seomyeon_drift_demote": components.get("seomyeon_drift_demote", 0.0),
            "seomyeon_weak_candidate_demote": components.get("seomyeon_weak_candidate_demote", 0.0),
            "seomyeon_family_match_terms": components.get("seomyeon_family_match_terms") or [],
            "busan_east_coast_family_score": components.get("busan_east_coast_family_score", 0.0),
            "east_coast_family_preserved": bool(components.get("east_coast_family_preserved")),
            "haeundae_gwangan_drift_demote": components.get("haeundae_gwangan_drift_demote", 0.0),
            "east_coast_support_slot_score": components.get("east_coast_support_slot_score", 0.0),
            "east_coast_expected_landmark_visible": bool(components.get("east_coast_expected_landmark_visible")),
            "east_coast_match_terms": components.get("east_coast_match_terms") or [],
            "seoul_external_authority_boost": components.get("seoul_external_authority_boost", 0.0),
            "gangnam_family_score": components.get("gangnam_family_score", 0.0),
            "yeouido_family_score": components.get("yeouido_family_score", 0.0),
            "seoul_weak_lifestyle_demote": components.get("seoul_weak_lifestyle_demote", 0.0),
            "seoul_family_pool_included": bool(components.get("seoul_family_pool_included")),
            "seoul_family_match_terms": components.get("seoul_family_match_terms") or [],
            "gangnam_candidate_depth_score": components.get("gangnam_candidate_depth_score", 0.0),
            "gangnam_representative_pool_included": bool(components.get("gangnam_representative_pool_included")),
            "gangnam_first_place_dominance_penalty": components.get("gangnam_first_place_dominance_penalty", 0.0),
            "yeouido_public_facility_final_demote": components.get("yeouido_public_facility_final_demote", 0.0),
            "family_candidate_depth_before_after": components.get("family_candidate_depth_before_after"),
            "euljiro_night_family_score": components.get("euljiro_night_family_score", 0.0),
            "euljiro_nightlife_pool_included": bool(components.get("euljiro_nightlife_pool_included")),
            "gangnam_editorial_representative_score": components.get("gangnam_editorial_representative_score", 0.0),
            "weak_editorial_first_place_demote": components.get("weak_editorial_first_place_demote", 0.0),
            "nightlife_coherence_score": components.get("nightlife_coherence_score", 0.0),
            "targeted_route_coherence_score": components.get("targeted_route_coherence_score", 0.0),
            "support_slot_family_alignment": components.get("support_slot_family_alignment", 0.0),
            "coherence_demote_reason": components.get("coherence_demote_reason"),
            "broad_default_balance_score": components.get("broad_default_balance_score", 0.0),
            "editorial_route_alignment": components.get("editorial_route_alignment", 0.0),
            "targeted_coherence_positive_terms": components.get("targeted_coherence_positive_terms") or [],
            "targeted_coherence_weak_terms": components.get("targeted_coherence_weak_terms") or [],
            "targeted_coherence_demote": components.get("targeted_coherence_demote", 0.0),
            "support_slot_family_assembly_score": components.get("support_slot_family_assembly_score", 0.0),
            "representative_support_slot_alignment": components.get("representative_support_slot_alignment", 0.0),
            "weak_support_slot_demote": components.get("weak_support_slot_demote", 0.0),
            "support_slot_coherence_balance": components.get("support_slot_coherence_balance", 0.0),
            "editorial_support_slot_match": bool(components.get("editorial_support_slot_match")),
            "support_slot_family_match_terms": components.get("support_slot_family_match_terms") or [],
            "weak_support_slot_terms": components.get("weak_support_slot_terms") or [],
            "support_slot_family_replacement_applied": bool(components.get("support_slot_family_replacement_applied")),
            "nightlife_support_slot_alignment": components.get("nightlife_support_slot_alignment", 0.0),
            "nightlife_family_depth": components.get("nightlife_family_depth", 0.0),
            "nightlife_replacement_applied": bool(components.get("nightlife_replacement_applied")),
            "nightlife_core_alignment": components.get("nightlife_core_alignment", 0.0),
            "nightlife_core_match_terms": components.get("nightlife_core_match_terms") or [],
            "central_seoul_broad_demote": components.get("central_seoul_broad_demote", 0.0),
            "support_slot_purity_score": components.get("support_slot_purity_score", 0.0),
            "support_slot_editorial_contamination": bool(components.get("support_slot_editorial_contamination")),
            "representative_support_purity_score": components.get("representative_support_purity_score", 0.0),
            "residual_support_slot_contamination": bool(components.get("residual_support_slot_contamination")),
            "support_slot_cleanup_applied": bool(components.get("support_slot_cleanup_applied")),
            "representative_support_slot_purity": components.get("representative_support_slot_purity", 0.0),
            "bounded_support_slot_cleanup": bool(components.get("bounded_support_slot_cleanup")),
            "support_slot_family_coherence": components.get("support_slot_family_coherence", 0.0),
            "representative_family_purity_score": components.get("representative_family_purity_score", 0.0),
            "support_slot_purity_cleanup": bool(components.get("support_slot_purity_cleanup")),
            "weak_contamination_demote": components.get("weak_contamination_demote", 0.0),
            "representative_family_alignment": components.get("representative_family_alignment", 0.0),
            "bounded_purity_replacement": bool(components.get("bounded_purity_replacement")),
            "residual_cleanup_applied": bool(components.get("residual_cleanup_applied")),
            "weak_contamination_repeat": bool(components.get("weak_contamination_repeat")),
            "support_slot_minimal_cleanup": bool(components.get("support_slot_minimal_cleanup")),
            "runtime_stability_guard": bool(components.get("runtime_stability_guard")),
            "heritage_family_exception": components.get("heritage_family_exception") or [],
            "nightlife_core_exception": components.get("nightlife_core_exception") or [],
            "coherence_false_positive_removed": bool(components.get("coherence_false_positive_removed")),
            "nightlife_false_positive_removed": bool(components.get("nightlife_false_positive_removed")),
            "heritage_false_positive_removed": bool(components.get("heritage_false_positive_removed")),
            "final_score": components.get("final_score", round(float(score or 0), 4)),
            "travel_min": travel_min,
            "distance_km": round(float(dist_km or 0), 3),
            "selected": False,
        })
    return rows


def summarize_wrong_city_ratio(candidate_summaries: list[dict[str, Any]], target_city: str | None) -> dict[str, Any]:
    """Summarize wrong-city ratio from candidate summaries."""
    if not candidate_summaries or not target_city:
        return {"target_city": target_city, "wrong_city_count": 0, "total": len(candidate_summaries or []), "ratio": 0.0}
    total = len(candidate_summaries)
    wrong = sum(1 for row in candidate_summaries if row.get("city_token") not in {target_city, "unknown"})
    return {"target_city": target_city, "wrong_city_count": wrong, "total": total, "ratio": round(wrong / max(total, 1), 4)}


def build_recommendation_trace(
    *,
    request_id: str | None,
    region: str,
    selected_anchor_raw: Any,
    selected_anchor_normalized: dict[str, Any] | None,
    top_candidate_city_distribution: dict[str, int] | None,
    selected_places: list[dict[str, Any]],
    rejected_candidates_count: int,
    wrong_city_demote_applied_count: int,
    locality_bonus_applied_count: int,
    belt_match_applied_count: int = 0,
    wrong_belt_match_count: int = 0,
    continuity_bonus_applied_count: int = 0,
    flow_break_candidate_count: int = 0,
    suitability_bonus_applied_count: int = 0,
    suitability_soft_demote_count: int = 0,
    meal_cafe_bonus_applied_count: int = 0,
    meal_cafe_soft_demote_count: int = 0,
    same_role_soft_demote_applied_count: int = 0,
    same_role_soft_demote_role: str | None = None,
    same_role_soft_demote_delta: float = 0.0,
    gangnam_editorial_soft_demote_applied_count: int = 0,
    gangnam_editorial_soft_demote_delta: float = 0.0,
    route_contamination_applied_count: int = 0,
    night_late_safe_relaxed_mode: bool = False,
    relaxed_operating_hour_filter: bool = False,
    night_safe_candidate_preserved: bool = False,
    nightlife_support_slot_fallback: bool = False,
    strict_closed_filter_skipped: bool = False,
    late_user_selected_mode: bool = False,
    intentional_late_schedule: bool = False,
    late_cutoff_relaxed: bool = False,
    night_support_slot_preserved: bool = False,
    short_course_prevented: bool = False,
    night_operating_confidence: int = 0,
    indoor_night_confidence_demote: int = 0,
    night_safe_outdoor_priority: int = 0,
    nightlife_suitability_alignment: int = 0,
    indoor_heavy_route_detected: int = 0,
    operating_hours_known_closed: int = 0,
    night_indoor_strong_demote: int = 0,
    relaxed_unknown_hours_allowed: int = 0,
    known_closed_removed: int = 0,
    night_safe_indoor_exception: int = 0,
    indoor_semantic_detected: int = 0,
    known_closed_indoor_removed: int = 0,
    night_indoor_semantic_demote: int = 0,
    indoor_closing_time_applied: int = 0,
    curated_night_family_applied: int = 0,
    night_representative_preference: int = 0,
    nightlife_curated_alignment: int = 0,
    night_vibe_coherence: int = 0,
    curated_night_support_slot: int = 0,
    curated_representative_priority: int = 0,
    verified_api_candidate: int = 0,
    public_fallback_used: int = 0,
    weak_public_contamination_demote: int = 0,
    curated_support_slot_alignment: int = 0,
    seoul_curated_district_priority: int = 0,
    broad_seoul_demoted: int = 0,
    district_identity_alignment: int = 0,
    support_slot_role_diversity: int = 0,
    euljiro_mood_label_applied: bool = False,
    euljiro_night_mode_removed: bool = False,
    default_preset_mode: bool = False,
    representative_landmark_selected: bool = False,
    representative_pool_size: int = 1,
    weird_candidate_demote: float = 0.0,
    regenerate_diversity_applied: bool = False,
    representative_family_pool_size: int = 0,
    representative_family_rotation_bonus: float = 0.0,
    representative_family_saturation_penalty: float = 0.0,
    representative_family_first_place_repeat: int = 0,
    representative_family_diversity_applied: bool = False,
    regenerate_repeat_penalty: float = 0.0,
    representative_family_rotation_applied: bool = False,
    description_quality_variant: str | None = None,
    generic_copy_demote: float = 0.0,
    selected_anchor_family_id: str | None = None,
    selected_anchor_family_match_score: float = 0.0,
    selected_anchor_family_preserved: bool = False,
    selected_anchor_family_drift_demote: float = 0.0,
    selected_anchor_drift_reason: str | None = None,
    fallback_level_used: str | None = None,
    cross_flow_candidate_count: int = 0,
    lifestyle_mismatch_count: int = 0,
    first_anchor_reason: dict[str, Any] | None = None,
    first_anchor_vibe_match: dict[str, Any] | None = None,
    first_anchor_candidate_scores: list[dict[str, Any]] | None = None,
    first_anchor_belt_match: dict[str, Any] | None = None,
    first_anchor_contamination: dict[str, Any] | None = None,
    first_anchor_replacement_attempted: bool = False,
    first_place_replacement: dict[str, Any] | None = None,
    broad_region_belt_candidates: list[dict[str, Any]] | None = None,
    inferred_belt_confidence: float | None = None,
    dominant_belt_reason: dict[str, Any] | None = None,
    belt_candidate_scores: list[dict[str, Any]] | None = None,
    cross_belt_transition_count: int = 0,
    dominant_district: str | None = None,
    district_candidate_scores: list[dict[str, Any]] | None = None,
    cross_district_transition_count: int = 0,
    district_vibe_reason: dict[str, Any] | None = None,
    route_level_warnings: list[dict[str, Any]] | None = None,
    replacement_events: list[dict[str, Any]] | None = None,
    unsuitable_block_counts: dict[str, int] | None = None,
    candidate_samples: list[dict[str, Any]] | None = None,
    region_identity: dict[str, Any] | None = None,
    course_belt_coherence: dict[str, Any] | None = None,
    flow_profile: dict[str, Any] | None = None,
    route_coherence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    support_role_trace = summarize_support_slot_roles(selected_places)
    gangnam_support_trace = summarize_gangnam_editorial_support(selected_places, selected_anchor_raw)
    return {
        "request_id": request_id,
        "region": region,
        "selected_anchor_raw": selected_anchor_raw,
        "normalized_city": (selected_anchor_normalized or {}).get("normalized_city_token"),
        "normalized_anchor": (selected_anchor_normalized or {}).get("normalized_anchor_token"),
        "normalized_anchor_aliases": (selected_anchor_normalized or {}).get("normalized_anchor_aliases") or [],
        "top_candidate_city_distribution": top_candidate_city_distribution or {},
        "selected_places": selected_places,
        **support_role_trace,
        **gangnam_support_trace,
        "rejected_candidates_count": int(rejected_candidates_count or 0),
        "wrong_city_demote_applied_count": int(wrong_city_demote_applied_count or 0),
        "locality_bonus_applied_count": int(locality_bonus_applied_count or 0),
        "belt_match_applied_count": int(belt_match_applied_count or 0),
        "wrong_belt_match_count": int(wrong_belt_match_count or 0),
        "continuity_bonus_applied_count": int(continuity_bonus_applied_count or 0),
        "flow_break_candidate_count": int(flow_break_candidate_count or 0),
        "suitability_bonus_applied_count": int(suitability_bonus_applied_count or 0),
        "suitability_soft_demote_count": int(suitability_soft_demote_count or 0),
        "meal_cafe_bonus_applied_count": int(meal_cafe_bonus_applied_count or 0),
        "meal_cafe_soft_demote_count": int(meal_cafe_soft_demote_count or 0),
        "same_role_soft_demote_applied": bool(same_role_soft_demote_applied_count),
        "same_role_soft_demote_role": same_role_soft_demote_role,
        "same_role_soft_demote_delta": round(float(same_role_soft_demote_delta or 0.0), 4),
        "same_role_soft_demote_applied_count": int(same_role_soft_demote_applied_count or 0),
        "gangnam_editorial_soft_demote_applied": bool(gangnam_editorial_soft_demote_applied_count),
        "gangnam_editorial_soft_demote_count": int(gangnam_editorial_soft_demote_applied_count or 0),
        "gangnam_editorial_soft_demote_delta": round(float(gangnam_editorial_soft_demote_delta or 0.0), 4),
        "route_contamination_applied_count": int(route_contamination_applied_count or 0),
        "night_late_safe_relaxed_mode": bool(night_late_safe_relaxed_mode),
        "relaxed_operating_hour_filter": bool(relaxed_operating_hour_filter),
        "night_safe_candidate_preserved": bool(night_safe_candidate_preserved),
        "nightlife_support_slot_fallback": bool(nightlife_support_slot_fallback),
        "strict_closed_filter_skipped": bool(strict_closed_filter_skipped),
        "late_user_selected_mode": bool(late_user_selected_mode),
        "intentional_late_schedule": bool(intentional_late_schedule),
        "late_cutoff_relaxed": bool(late_cutoff_relaxed),
        "night_support_slot_preserved": bool(night_support_slot_preserved),
        "short_course_prevented": bool(short_course_prevented),
        "night_operating_confidence": int(night_operating_confidence or 0),
        "indoor_night_confidence_demote": int(indoor_night_confidence_demote or 0),
        "night_safe_outdoor_priority": int(night_safe_outdoor_priority or 0),
        "nightlife_suitability_alignment": int(nightlife_suitability_alignment or 0),
        "indoor_heavy_route_detected": int(indoor_heavy_route_detected or 0),
        "operating_hours_known_closed": int(operating_hours_known_closed or 0),
        "night_indoor_strong_demote": int(night_indoor_strong_demote or 0),
        "relaxed_unknown_hours_allowed": int(relaxed_unknown_hours_allowed or 0),
        "known_closed_removed": int(known_closed_removed or 0),
        "night_safe_indoor_exception": int(night_safe_indoor_exception or 0),
        "indoor_semantic_detected": int(indoor_semantic_detected or 0),
        "known_closed_indoor_removed": int(known_closed_indoor_removed or 0),
        "night_indoor_semantic_demote": int(night_indoor_semantic_demote or 0),
        "indoor_closing_time_applied": int(indoor_closing_time_applied or 0),
        "curated_night_family_applied": int(curated_night_family_applied or 0),
        "night_representative_preference": int(night_representative_preference or 0),
        "nightlife_curated_alignment": int(nightlife_curated_alignment or 0),
        "night_vibe_coherence": int(night_vibe_coherence or 0),
        "curated_night_support_slot": int(curated_night_support_slot or 0),
        "curated_representative_priority": int(curated_representative_priority or 0),
        "verified_api_candidate": int(verified_api_candidate or 0),
        "public_fallback_used": int(public_fallback_used or 0),
        "weak_public_contamination_demote": int(weak_public_contamination_demote or 0),
        "curated_support_slot_alignment": int(curated_support_slot_alignment or 0),
        "seoul_curated_district_priority": int(seoul_curated_district_priority or 0),
        "broad_seoul_demoted": int(broad_seoul_demoted or 0),
        "district_identity_alignment": int(district_identity_alignment or 0),
        "support_slot_role_diversity": int(support_slot_role_diversity or 0),
        "euljiro_mood_label_applied": bool(euljiro_mood_label_applied),
        "euljiro_night_mode_removed": bool(euljiro_night_mode_removed),
        "default_preset_mode": bool(default_preset_mode),
        "representative_landmark_selected": bool(representative_landmark_selected),
        "representative_pool_size": int(representative_pool_size or 1),
        "weird_candidate_demote": float(weird_candidate_demote or 0.0),
        "regenerate_diversity_applied": bool(regenerate_diversity_applied),
        "representative_family_pool_size": int(representative_family_pool_size or 0),
        "representative_family_rotation_bonus": round(float(representative_family_rotation_bonus or 0.0), 4),
        "representative_family_saturation_penalty": round(float(representative_family_saturation_penalty or 0.0), 4),
        "representative_family_first_place_repeat": int(representative_family_first_place_repeat or 0),
        "representative_family_diversity_applied": bool(representative_family_diversity_applied),
        "regenerate_repeat_penalty": round(float(regenerate_repeat_penalty or 0.0), 4),
        "representative_family_rotation_applied": bool(representative_family_rotation_applied),
        "description_quality_variant": description_quality_variant,
        "generic_copy_demote": round(float(generic_copy_demote or 0.0), 4),
        "selected_anchor_family_id": selected_anchor_family_id,
        "selected_anchor_family_match_score": round(float(selected_anchor_family_match_score or 0.0), 4),
        "selected_anchor_family_preserved": bool(selected_anchor_family_preserved),
        "selected_anchor_family_drift_demote": round(float(selected_anchor_family_drift_demote or 0.0), 4),
        "selected_anchor_drift_reason": selected_anchor_drift_reason,
        "fallback_level_used": fallback_level_used,
        "route_coherence_score": (route_coherence or {}).get("route_coherence_score"),
        "route_purity_score": (route_coherence or {}).get("route_purity_score"),
        "same_region_ratio": (route_coherence or {}).get("same_region_ratio"),
        "same_belt_ratio": (route_coherence or {}).get("same_belt_ratio"),
        "contamination_region_pairs": (route_coherence or {}).get("contamination_region_pairs") or [],
        "contamination_flags": (route_coherence or {}).get("contamination_flags") or [],
        "cross_flow_candidate_count": int(cross_flow_candidate_count or 0),
        "lifestyle_mismatch_count": int(lifestyle_mismatch_count or 0),
        "first_anchor_reason": first_anchor_reason or {},
        "first_anchor_vibe_match": first_anchor_vibe_match or {},
        "first_anchor_candidate_scores": first_anchor_candidate_scores or [],
        "first_anchor_belt_match": first_anchor_belt_match or {},
        "first_anchor_contamination": first_anchor_contamination or {},
        "first_anchor_replacement_attempted": bool(first_anchor_replacement_attempted),
        "first_place_replacement_attempted": bool((first_place_replacement or {}).get("first_place_replacement_attempted")),
        "first_place_replacement_success": bool((first_place_replacement or {}).get("first_place_replacement_success")),
        "first_place_replacement": first_place_replacement or {},
        "broad_region_belt_candidates": broad_region_belt_candidates or [],
        "inferred_belt_confidence": inferred_belt_confidence,
        "dominant_belt_reason": dominant_belt_reason or {},
        "belt_candidate_scores": belt_candidate_scores or [],
        "cross_belt_transition_count": int(cross_belt_transition_count or 0),
        "dominant_district": dominant_district,
        "district_candidate_scores": district_candidate_scores or [],
        "cross_district_transition_count": int(cross_district_transition_count or 0),
        "district_vibe_reason": district_vibe_reason or {},
        "broad_default_fallback_guard": bool((region_identity or {}).get("broad_default_fallback_guard")),
        "fallback_exhaustion_detected": bool((region_identity or {}).get("fallback_exhaustion_detected")),
        "broad_family_recovery_applied": bool((region_identity or {}).get("broad_family_recovery_applied")),
        "nocourse_guard_applied": bool((region_identity or {}).get("nocourse_guard_applied")),
        "route_level_warnings": route_level_warnings or [],
        "replacement_attempted": any((event or {}).get("replacement_attempted") for event in (replacement_events or [])),
        "replacement_success": any((event or {}).get("replacement_success") for event in (replacement_events or [])),
        "replacement_events": replacement_events or [],
        "unsuitable_block_counts": unsuitable_block_counts or {},
        "candidate_samples": candidate_samples or [],
        "region_identity": region_identity or None,
        "course_belt_coherence": course_belt_coherence or None,
        "flow_profile": flow_profile or None,
        "route_coherence": route_coherence or None,
    }

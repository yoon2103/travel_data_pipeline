from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402
import db_client  # noqa: E402


BLACKLIST_TERMS = (
    "pinterest",
    "pinimg",
    "핀터레스트",
    "wallpaper",
    "배경화면",
    "banner",
    "배너",
    "coupon",
    "쿠폰",
    "menu",
    "메뉴판",
    "logo",
    "로고",
)

CAFE_TERMS = ("카페", "커피", "디저트", "베이커리", "브런치", "cafe", "coffee", "dessert", "bakery")


@dataclass
class ImageCandidate:
    place_name: str
    region: str | None
    category: str | None
    source: str | None
    query: str
    rank: int
    image_title: str
    image_link: str
    image_thumbnail: str
    source_page: str
    confidence: str
    score: float
    title_similarity: float
    region_similarity: float
    category_similarity: float
    mismatch_risk: str
    recommended_action: str


def normalize_text(value: str | None) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", html.unescape(value or "")).lower()


def token_overlap_score(needle: str, haystack: str) -> float:
    needle_norm = normalize_text(needle)
    haystack_norm = normalize_text(haystack)
    if not needle_norm or not haystack_norm:
        return 0.0
    if needle_norm in haystack_norm:
        return 1.0
    tokens = [normalize_text(token) for token in re.split(r"\s+", needle or "") if normalize_text(token)]
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token and token in haystack_norm)
    return round(hits / len(tokens), 3)


def category_score(category: str | None, title: str, query: str) -> float:
    text = f"{category or ''} {title or ''} {query or ''}".lower()
    return 1.0 if any(term in text for term in CAFE_TERMS) else 0.0


def mismatch_reason(title: str, link: str, thumbnail: str) -> str:
    text = f"{title} {link} {thumbnail}".lower()
    hits = [term for term in BLACKLIST_TERMS if term in text]
    if hits:
        return "blacklist:" + ",".join(hits)
    if not link or not thumbnail:
        return "missing_image_url"
    return ""


def confidence_label(score: float, mismatch: str) -> str:
    if mismatch:
        return "LOW"
    if score >= 0.75:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"


def recommended_action(confidence: str, mismatch: str) -> str:
    if mismatch:
        return "REJECT_OR_MANUAL_REVIEW"
    if confidence == "HIGH":
        return "REVIEW_IMAGE_CANDIDATE"
    if confidence == "MEDIUM":
        return "MANUAL_REVIEW_REQUIRED"
    return "REJECT_OR_MANUAL_REVIEW"


def search_naver_images(query: str, display: int) -> list[dict[str, Any]]:
    if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET are not configured")
    url = "https://openapi.naver.com/v1/search/image.json?" + urllib.parse.urlencode(
        {"query": query, "display": display, "sort": "sim"}
    )
    request = urllib.request.Request(
        url,
        headers={
            "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8")).get("items") or []


def load_clean_candidates(run_id: str, region: str | None, visit_role: str | None, limit: int) -> list[dict[str, Any]]:
    conn = db_client.get_connection()
    try:
        sql = """
            SELECT source, external_id, name, region, category, visit_role
            FROM clean_external_places
            WHERE run_id = %s
        """
        params: list[Any] = [run_id]
        if region:
            sql += " AND region = %s"
            params.append(region)
        if visit_role:
            sql += " AND visit_role = %s"
            params.append(visit_role)
        sql += " ORDER BY id LIMIT %s"
        params.append(limit)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def build_query(row: dict[str, Any], extra_keywords: str | None) -> str:
    parts = [row.get("name"), row.get("region")]
    if extra_keywords:
        parts.append(extra_keywords)
    elif row.get("visit_role") == "cafe":
        parts.append("카페")
    return " ".join(str(part).strip() for part in parts if part)


def score_item(row: dict[str, Any], query: str, rank: int, item: dict[str, Any]) -> ImageCandidate:
    title = html.unescape(re.sub(r"<[^>]+>", "", item.get("title") or ""))
    link = item.get("link") or ""
    thumbnail = item.get("thumbnail") or ""
    source_page = item.get("originallink") or ""
    title_similarity = token_overlap_score(str(row.get("name") or ""), title)
    region_similarity = token_overlap_score(str(row.get("region") or ""), f"{title} {source_page}")
    category_similarity = category_score(row.get("category"), title, query)
    mismatch = mismatch_reason(title, link, thumbnail)
    score = round((title_similarity * 0.65) + (region_similarity * 0.15) + (category_similarity * 0.2), 3)
    confidence = confidence_label(score, mismatch)
    return ImageCandidate(
        place_name=str(row.get("name") or ""),
        region=row.get("region"),
        category=row.get("category"),
        source=row.get("source"),
        query=query,
        rank=rank,
        image_title=title,
        image_link=link,
        image_thumbnail=thumbnail,
        source_page=source_page,
        confidence=confidence,
        score=score,
        title_similarity=title_similarity,
        region_similarity=region_similarity,
        category_similarity=category_similarity,
        mismatch_risk=mismatch or "none",
        recommended_action=recommended_action(confidence, mismatch),
    )


def run_poc(run_id: str, region: str | None, visit_role: str | None, limit: int, display: int, extra_keywords: str | None) -> dict[str, Any]:
    rows = load_clean_candidates(run_id, region, visit_role, limit)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in rows:
        query = build_query(row, extra_keywords)
        try:
            items = search_naver_images(query, display)
        except Exception as exc:
            errors.append({"place_name": row.get("name"), "query": query, "error": str(exc)})
            items = []
        candidates = [asdict(score_item(row, query, index + 1, item)) for index, item in enumerate(items)]
        best = candidates[0] if candidates else None
        results.append(
            {
                "place_name": row.get("name"),
                "region": row.get("region"),
                "category": row.get("category"),
                "source": row.get("source"),
                "query": query,
                "candidate_count": len(candidates),
                "best_confidence": best.get("confidence") if best else "NONE",
                "best_score": best.get("score") if best else 0,
                "best_thumbnail": best.get("image_thumbnail") if best else "",
                "best_mismatch_risk": best.get("mismatch_risk") if best else "no_image_candidate",
                "recommended_action": best.get("recommended_action") if best else "NO_IMAGE_CANDIDATE",
                "candidates": candidates,
            }
        )
    summary = {
        "run_id": run_id,
        "region": region,
        "visit_role": visit_role,
        "write": False,
        "candidate_count": len(rows),
        "places_with_image_candidates": sum(1 for item in results if item["candidate_count"] > 0),
        "high_confidence_count": sum(1 for item in results if item["best_confidence"] == "HIGH"),
        "medium_confidence_count": sum(1 for item in results if item["best_confidence"] == "MEDIUM"),
        "low_confidence_count": sum(1 for item in results if item["best_confidence"] == "LOW"),
        "none_count": sum(1 for item in results if item["best_confidence"] == "NONE"),
        "errors_count": len(errors),
        "scraping_used": False,
        "production_places_write": False,
        "migration_executed": False,
    }
    return {"summary": summary, "results": results, "errors": errors}


def safe_filename(value: str | None) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣_-]+", "_", str(value or "all")).strip("_") or "all"


def write_reports(result: dict[str, Any], output_dir: str) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = "image_enrichment_poc_{run_id}_{region}_{role}_{timestamp}".format(
        run_id=safe_filename(summary.get("run_id")),
        region=safe_filename(summary.get("region")),
        role=safe_filename(summary.get("visit_role")),
        timestamp=timestamp,
    )
    json_path = out / f"{stem}.json"
    csv_path = out / f"{stem}.csv"
    md_path = out / f"{stem}.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "place_name",
        "query",
        "candidate_count",
        "best_confidence",
        "best_score",
        "best_thumbnail",
        "best_mismatch_risk",
        "recommended_action",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fields)
        writer.writeheader()
        for row in result["results"]:
            writer.writerow({field: row.get(field) for field in fields})

    lines = [
        "# Image Enrichment PoC Report",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Candidate Images",
            "",
            "| place | query | count | confidence | score | thumbnail | mismatch | action |",
            "|---|---|---:|---|---:|---|---|---|",
        ]
    )
    for row in result["results"]:
        thumbnail = row.get("best_thumbnail") or ""
        thumb_md = f"[preview]({thumbnail})" if thumbnail else ""
        lines.append(
            "| {place} | {query} | {count} | {confidence} | {score} | {thumb} | {mismatch} | {action} |".format(
                place=str(row.get("place_name") or "").replace("|", "/"),
                query=str(row.get("query") or "").replace("|", "/"),
                count=row.get("candidate_count"),
                confidence=row.get("best_confidence"),
                score=row.get("best_score"),
                thumb=thumb_md,
                mismatch=str(row.get("best_mismatch_risk") or "").replace("|", "/"),
                action=row.get("recommended_action"),
            )
        )
    lines.extend(
        [
            "",
            "## Policy Notes",
            "",
            "- This is dry-run only. No DB write, no migration, no scraping.",
            "- Image candidates are not automatically approved.",
            "- HIGH confidence still requires reviewer preview before promotion.",
            "- LOW confidence or mismatch candidates should be rejected or manually reviewed.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run Naver Image Search enrichment PoC for external candidates.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--region")
    parser.add_argument("--visit-role", choices=["cafe", "meal", "culture", "spot"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--display", type=int, default=3)
    parser.add_argument("--keywords", help="Optional extra keywords appended to each image query.")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--output-dir", default="qa_reports/image_enrichment_poc")
    args = parser.parse_args()

    result = run_poc(args.run_id, args.region, args.visit_role, args.limit, args.display, args.keywords)
    if args.report:
        result["report_paths"] = write_reports(result, args.output_dir)
    print(json.dumps(result["summary"] | {"report_paths": result.get("report_paths", {}), "errors": result.get("errors", [])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

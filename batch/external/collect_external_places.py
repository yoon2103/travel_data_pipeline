from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config  # noqa: E402
import db_client  # noqa: E402
from batch.external.common import ensure_run, haversine_km, log_step, valid_korea_coord  # noqa: E402


def _get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_kakao(keyword: str, lat: float, lon: float, radius_km: float, limit: int) -> list[dict]:
    if not config.KAKAO_REST_API_KEY:
        return []
    collected: list[dict] = []
    radius_m = min(int(radius_km * 1000), 20000)
    page = 1
    while len(collected) < limit and page <= 3:
        params = {
            "query": keyword,
            "x": lon,
            "y": lat,
            "radius": radius_m,
            "size": min(15, limit - len(collected)),
            "page": page,
        }
        url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urllib.parse.urlencode(params)
        data = _get_json(url, {"Authorization": f"KakaoAK {config.KAKAO_REST_API_KEY}"})
        docs = data.get("documents") or []
        for item in docs:
            collected.append({
                "source": "kakao",
                "external_id": str(item.get("id") or ""),
                "name": item.get("place_name") or "",
                "latitude": float(item["y"]) if item.get("y") else None,
                "longitude": float(item["x"]) if item.get("x") else None,
                "category": item.get("category_name"),
                "address": item.get("road_address_name") or item.get("address_name"),
                "phone": item.get("phone"),
                "place_url": item.get("place_url"),
                "raw_payload": item,
            })
        if data.get("meta", {}).get("is_end", True):
            break
        page += 1
    return collected


def fetch_naver(keyword: str, region: str, lat: float, lon: float, radius_km: float, limit: int) -> list[dict]:
    if not config.NAVER_CLIENT_ID or not config.NAVER_CLIENT_SECRET:
        return []
    query = urllib.parse.quote(f"{region} {keyword}")
    url = f"https://openapi.naver.com/v1/search/local.json?query={query}&display={min(limit, 5)}"
    data = _get_json(url, {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    })
    rows: list[dict] = []
    for item in data.get("items", []):
        try:
            item_lon = int(item["mapx"]) / 1e7
            item_lat = int(item["mapy"]) / 1e7
        except (KeyError, TypeError, ValueError):
            continue
        if haversine_km(lat, lon, item_lat, item_lon) > radius_km:
            continue
        external_key = item.get("link") or f"{item.get('title')}:{item.get('mapx')}:{item.get('mapy')}"
        external_id = hashlib.sha1(str(external_key).encode("utf-8")).hexdigest()
        rows.append({
            "source": "naver",
            "external_id": str(external_id),
            "name": (item.get("title") or "").replace("<b>", "").replace("</b>", ""),
            "latitude": item_lat,
            "longitude": item_lon,
            "category": item.get("category"),
            "address": item.get("roadAddress") or item.get("address"),
            "phone": item.get("telephone"),
            "place_url": item.get("link"),
            "raw_payload": item,
        })
    return rows


def insert_raw(conn, run_id: str, region: str, anchor_lat: float, anchor_lon: float, radius_km: float, keyword: str, rows: list[dict]) -> int:
    count = 0
    with conn.cursor() as cur:
        for row in rows:
            if not row.get("external_id") or not row.get("name"):
                continue
            if not valid_korea_coord(row.get("latitude"), row.get("longitude")):
                continue
            cur.execute(
                """
                INSERT INTO raw_external_places (
                    run_id, region, anchor_lat, anchor_lon, radius_km, keyword,
                    source, external_id, name, latitude, longitude, category,
                    address, phone, place_url, raw_payload
                )
                VALUES (
                    %(run_id)s, %(region)s, %(anchor_lat)s, %(anchor_lon)s, %(radius_km)s, %(keyword)s,
                    %(source)s, %(external_id)s, %(name)s, %(latitude)s, %(longitude)s, %(category)s,
                    %(address)s, %(phone)s, %(place_url)s, %(raw_payload)s
                )
                ON CONFLICT (run_id, source, external_id) DO NOTHING
                """,
                {
                    **row,
                    "run_id": run_id,
                    "region": region,
                    "anchor_lat": anchor_lat,
                    "anchor_lon": anchor_lon,
                    "radius_km": radius_km,
                    "keyword": keyword,
                    "raw_payload": psycopg2.extras.Json(row.get("raw_payload") or {}),
                },
            )
            count += cur.rowcount
    conn.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Kakao/Naver external places around an anchor.")
    parser.add_argument("--region", required=True)
    parser.add_argument("--anchor-lat", type=float, required=True)
    parser.add_argument("--anchor-lon", type=float, required=True)
    parser.add_argument("--keywords", required=True, help="Comma-separated keywords")
    parser.add_argument("--radius-km", type=float, default=15.0)
    parser.add_argument("--sources", default="kakao,naver")
    parser.add_argument("--limit-per-keyword", type=int, default=10)
    parser.add_argument("--max-total", type=int, default=80)
    parser.add_argument("--run-id")
    parser.add_argument("--write", action="store_true", help="Write rows to raw_external_places.")
    args = parser.parse_args()

    keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
    sources = {src.strip() for src in args.sources.split(",") if src.strip()}
    rows: list[dict] = []
    errors: list[dict] = []
    for keyword in keywords:
        if len(rows) >= args.max_total:
            break
        if "kakao" in sources:
            try:
                kakao_rows = fetch_kakao(keyword, args.anchor_lat, args.anchor_lon, args.radius_km, args.limit_per_keyword)
            except Exception as exc:
                kakao_rows = []
                errors.append({"source": "kakao", "keyword": keyword, "error": str(exc)})
            for row in kakao_rows:
                row["_keyword"] = keyword
            rows.extend(kakao_rows)
        if "naver" in sources:
            try:
                naver_rows = fetch_naver(keyword, args.region, args.anchor_lat, args.anchor_lon, args.radius_km, args.limit_per_keyword)
            except Exception as exc:
                naver_rows = []
                errors.append({"source": "naver", "keyword": keyword, "error": str(exc)})
            for row in naver_rows:
                row["_keyword"] = keyword
            rows.extend(naver_rows)
        rows = rows[:args.max_total]

    inserted = 0
    run_id = args.run_id
    if args.write:
        conn = db_client.get_connection()
        try:
            run_id = ensure_run(conn, run_id, dry_run=False)
            for keyword in keywords:
                keyword_rows = [r for r in rows if r.get("_keyword") == keyword]
                inserted += insert_raw(conn, run_id, args.region, args.anchor_lat, args.anchor_lon, args.radius_km, keyword, keyword_rows)
            log_step(conn, run_id, "collect_external_places", "SUCCESS", output_count=inserted, metadata={"keywords": keywords})
        finally:
            conn.close()

    print(json.dumps({
        "run_id": run_id,
        "write": args.write,
        "fetched_count": len(rows),
        "inserted_count": inserted,
        "errors": errors,
        "sample": rows[:5],
    }, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

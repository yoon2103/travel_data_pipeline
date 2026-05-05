#!/usr/bin/env python3
"""
repair_cat12_cat14_duration.py
cat12(관광지) dur > 120, cat14(문화시설) dur > 100 인 행을
최신 classify_place() 규칙(DURATION_CLAMP 포함)으로 재계산하여 보정한다.

안전장치:
  - stored_role == new_role 인 행만 업데이트
  - role 불일치 행은 mismatch 리포트로 분리, 업데이트 없음

실행:
  python repair_cat12_cat14_duration.py --dry-run
  python repair_cat12_cat14_duration.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

# (category_id, SOT_upper_clamp)
TARGETS = [
    (12, 120),
    (14, 100),
]


def repair_category(conn, cat_id: int, upper: int, dry: bool) -> None:
    label = "[DRY-RUN]" if dry else "[APPLY]"

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, overview, visit_role, estimated_duration
            FROM   places
            WHERE  is_active           = TRUE
              AND  category_id         = %s
              AND  estimated_duration  > %s
            ORDER BY place_id
        """, (cat_id, upper))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{label} cat{cat_id}  estimated_duration > {upper}  대상: {total}건")

    to_update  = []
    mismatches = []

    for r in rows:
        result      = classify_place(r["name"], r["overview"], cat_id)
        new_role    = result["visit_role"]
        new_dur     = result["estimated_duration"]
        stored_role = r["visit_role"]
        old_dur     = r["estimated_duration"]

        entry = {
            "place_id":    r["place_id"],
            "name":        r["name"],
            "stored_role": stored_role,
            "new_role":    new_role,
            "old_dur":     old_dur,
            "new_dur":     new_dur,
        }
        if stored_role == new_role:
            to_update.append(entry)
        else:
            mismatches.append(entry)

    dist: dict[tuple, int] = {}
    for e in to_update:
        key = (e["old_dur"], e["new_dur"])
        dist[key] = dist.get(key, 0) + 1

    print(f"  {'=' * 54}")
    print(f"  total 대상          : {total:>5}건")
    print(f"  실제 업데이트 대상  : {len(to_update):>5}건  (role 일치)")
    print(f"  role mismatch       : {len(mismatches):>5}건  (업데이트 보류)")
    print(f"  old -> new 분포 (업데이트 대상):")
    for (old, new), cnt in sorted(dist.items()):
        print(f"    {old:>4} -> {new:>4}  :  {cnt}건")

    if mismatches:
        print(f"  [role mismatch 리포트]")
        for e in mismatches[:20]:
            print(f"    place_id={e['place_id']:>6}  "
                  f"stored={e['stored_role']:<10}  new={e['new_role']:<10}  "
                  f"dur={e['old_dur']}->{e['new_dur']}  {e['name'][:24]}")
        if len(mismatches) > 20:
            print(f"    ... ({len(mismatches) - 20}건 생략)")

    if dry:
        return

    ok = fail = 0
    for e in to_update:
        if e["old_dur"] == e["new_dur"]:
            ok += 1
            continue
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE places
                       SET estimated_duration = %(new_dur)s,
                           updated_at         = NOW()
                     WHERE place_id           = %(pid)s
                       AND estimated_duration = %(old_dur)s
                """, {"new_dur": e["new_dur"], "pid": e["place_id"],
                      "old_dur": e["old_dur"]})
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            print(f"  FAIL place_id={e['place_id']} — {exc}", file=sys.stderr)
            fail += 1

    print(f"  완료 — 성공: {ok}건 / 실패: {fail}건")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cat12/cat14 duration SOT 초과분 보정 배치")
    parser.add_argument("--dry-run", action="store_true",
                        help="변경 없이 결과만 출력")
    args = parser.parse_args()
    dry = args.dry_run

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    print(f"\n{'=' * 60}")
    print(f"  cat12/cat14 duration repair  "
          f"{'[DRY-RUN]' if dry else '[APPLY]'}")
    print(f"{'=' * 60}")

    for cat_id, upper in TARGETS:
        repair_category(conn, cat_id, upper, dry)

    conn.close()
    if dry:
        print(f"\n[DRY-RUN] 완료 — 실제 변경 없음")


if __name__ == "__main__":
    main()

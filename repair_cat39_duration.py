#!/usr/bin/env python3
"""
repair_cat39_duration.py
cat39(음식) 중 estimated_duration < 40 인 행을
최신 classify_place() 규칙(DURATION_CLAMP 포함)으로 재계산하여 보정한다.

안전장치:
  - classify_place()로 new_role, new_duration 동시 계산
  - stored_role == new_role 인 행만 estimated_duration 업데이트
  - stored_role != new_role 인 행은 mismatch 리포트로 분리, 업데이트 없음

실행:
  python repair_cat39_duration.py --dry-run   # 변경 없이 결과 미리보기
  python repair_cat39_duration.py             # 실제 UPDATE 실행
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

TARGET_CATEGORY  = 39
DURATION_CEILING = 40   # estimated_duration < 40 인 행만 대상


def main() -> None:
    parser = argparse.ArgumentParser(description="cat39 duration < 40 보정 배치")
    parser.add_argument("--dry-run", action="store_true",
                        help="변경 없이 결과만 출력")
    args = parser.parse_args()
    dry = args.dry_run
    label = "[DRY-RUN]" if dry else "[APPLY]"

    conn = psycopg2.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        dbname=config.DB_NAME, user=config.DB_USER, password=config.DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, overview, visit_role, estimated_duration
            FROM   places
            WHERE  is_active        = TRUE
              AND  category_id      = %s
              AND  estimated_duration < %s
            ORDER BY place_id
        """, (TARGET_CATEGORY, DURATION_CEILING))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{label} 대상 건수: {total}건  (cat39, estimated_duration < {DURATION_CEILING})\n")

    to_update  = []   # stored_role == new_role
    mismatches = []   # stored_role != new_role

    for r in rows:
        result     = classify_place(r["name"], r["overview"], TARGET_CATEGORY)
        new_role   = result["visit_role"]
        new_dur    = result["estimated_duration"]
        stored_role = r["visit_role"]
        old_dur    = r["estimated_duration"]

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

    # ── old -> new 분포 집계 (업데이트 대상만) ────────────────────────
    dist: dict[tuple, int] = {}
    for e in to_update:
        key = (e["old_dur"], e["new_dur"])
        dist[key] = dist.get(key, 0) + 1

    # ── 결과 요약 출력 ─────────────────────────────────────────────────
    print(f"{'=' * 60}")
    print(f"  {label} 요약")
    print(f"{'=' * 60}")
    print(f"  total 대상          : {total:>5}건")
    print(f"  실제 업데이트 대상  : {len(to_update):>5}건  (role 일치)")
    print(f"  role mismatch       : {len(mismatches):>5}건  (업데이트 보류)")

    print(f"\n  old_duration -> new_duration 분포 (업데이트 대상):")
    for (old, new), cnt in sorted(dist.items()):
        print(f"    {old:>3} -> {new:>3}  :  {cnt}건")

    if mismatches:
        print(f"\n  [role mismatch 리포트] {len(mismatches)}건 — 업데이트 없음")
        for e in mismatches[:20]:
            print(f"    place_id={e['place_id']:>6}  "
                  f"stored={e['stored_role']:<8}  new={e['new_role']:<8}  "
                  f"dur={e['old_dur']}->{e['new_dur']}  {e['name'][:24]}")
        if len(mismatches) > 20:
            print(f"    ... ({len(mismatches) - 20}건 생략)")

    if dry:
        print(f"\n{label} dry-run 완료 — 실제 변경 없음")
        conn.close()
        return

    # ── 실제 UPDATE ────────────────────────────────────────────────────
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
                """, {"new_dur": e["new_dur"], "pid": e["place_id"], "old_dur": e["old_dur"]})
            conn.commit()
            ok += 1
        except Exception as exc:
            conn.rollback()
            print(f"  FAIL place_id={e['place_id']} — {exc}", file=sys.stderr)
            fail += 1

    conn.close()
    print(f"\n{label} 완료 — 성공: {ok}건 / 실패: {fail}건")


if __name__ == "__main__":
    main()

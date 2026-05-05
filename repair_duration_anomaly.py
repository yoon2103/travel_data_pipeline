#!/usr/bin/env python3
"""
repair_duration_anomaly.py
cat39 duration anomaly 두 그룹을 분리된 로직으로 보정한다.

그룹 B: cat39 estimated_duration > 90
  - classify_place() 재계산
  - stored_role == new_role AND old_dur != new_dur 인 행만 UPDATE
  - mismatch는 skip + 리포트

그룹 A: place_id=19177 단건 예외
  - 일반 규칙 확장 없음 — 이 레코드에만 적용되는 scripted repair
  - visit_role 유지 (meal), estimated_duration = 90 고정 보정
  - classify_place() 재계산 결과 사용 안 함:
      cafe spillover 오류로 role=cafe를 반환하므로 신뢰 불가
  - FIXED_DURATION=90 근거:
      음식점(meal) 맥락상 타당하고 cat39 SOT 상한(40~90) 경계값임

실행:
  python repair_duration_anomaly.py --dry-run
  python repair_duration_anomaly.py
"""

import argparse
import sys

import psycopg2
import psycopg2.extras

import config
from batch_rules import classify_place

TARGET_CATEGORY = 39
DURATION_UPPER  = 90   # estimated_duration > 90 인 행만 그룹 B 대상


def repair_group_b(conn, dry: bool) -> None:
    label = "[DRY-RUN]" if dry else "[APPLY]"

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, overview, visit_role, estimated_duration
            FROM   places
            WHERE  is_active           = TRUE
              AND  category_id         = %s
              AND  estimated_duration  > %s
            ORDER BY place_id
        """, (TARGET_CATEGORY, DURATION_UPPER))
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    print(f"\n{label} [그룹 B] cat39 estimated_duration > {DURATION_UPPER}  대상: {total}건")

    to_update  = []   # role 일치 AND 값 변경 있음 → UPDATE
    no_change  = []   # role 일치 AND 값 동일 → skip (이미 정상)
    mismatches = []   # role 불일치 → skip + 리포트

    for r in rows:
        result      = classify_place(r["name"], r["overview"], TARGET_CATEGORY)
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

        if stored_role != new_role:
            mismatches.append(entry)
        elif old_dur == new_dur:
            no_change.append(entry)
        else:
            to_update.append(entry)

    dist: dict[tuple, int] = {}
    for e in to_update:
        key = (e["old_dur"], e["new_dur"])
        dist[key] = dist.get(key, 0) + 1

    print(f"  {'=' * 54}")
    print(f"  total 대상          : {total:>5}건")
    print(f"  실제 업데이트 대상  : {len(to_update):>5}건  (role 일치 + 값 변경)")
    print(f"  값 동일 skip        : {len(no_change):>5}건  (role 일치, 이미 정상)")
    print(f"  role mismatch skip  : {len(mismatches):>5}건  (업데이트 보류)")
    print(f"  old -> new 분포 (업데이트 대상):")
    for (old, new), cnt in sorted(dist.items()):
        print(f"    {old:>4} -> {new:>4}  :  {cnt}건")

    if mismatches:
        print(f"\n  [role mismatch 리포트]")
        for e in mismatches:
            print(f"    place_id={e['place_id']:>6}  "
                  f"stored={e['stored_role']:<10}  new={e['new_role']:<10}  "
                  f"dur={e['old_dur']}->{e['new_dur']}  {e['name'][:24]}")

    if dry:
        return

    ok = fail = 0
    for e in to_update:
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


def repair_group_a(conn, dry: bool) -> None:
    """
    place_id=19177 단건 예외 scripted repair.

    classify_place()가 cafe spillover 오류로 role=cafe를 반환하므로
    재계산 결과를 신뢰할 수 없다. visit_role은 stored 값(meal)을 유지하고
    estimated_duration만 SOT 상한인 90으로 고정 보정한다.
    FIXED_DURATION=90은 음식점 맥락 및 cat39 clamp(40~90) 경계값으로 타당하다.
    """
    label = "[DRY-RUN]" if dry else "[APPLY]"
    TARGET_PLACE_ID = 19177
    FIXED_DURATION  = 90

    with conn.cursor() as cur:
        cur.execute("""
            SELECT place_id, name, visit_role, estimated_duration
            FROM   places
            WHERE  place_id = %s
        """, (TARGET_PLACE_ID,))
        row = cur.fetchone()

    if not row:
        print(f"\n  [그룹 A] place_id={TARGET_PLACE_ID} — 조회 결과 없음")
        return

    row = dict(row)
    print(f"\n{label} [그룹 A] place_id={TARGET_PLACE_ID} 단건 예외 scripted repair")
    print(f"  {'=' * 54}")
    print(f"  장소명         : {row['name']}")
    print(f"  stored_role    : {row['visit_role']}  (유지 — cafe spillover 오류, role 재계산 불신뢰)")
    print(f"  estimated_dur  : {row['estimated_duration']} -> {FIXED_DURATION}"
          f"  (SOT 상한 고정 보정, cat39 clamp 40~90 경계값)")

    if row["estimated_duration"] == FIXED_DURATION:
        print(f"  -> 이미 {FIXED_DURATION}. skip.")
        return

    if dry:
        print(f"  -> dry-run: 실제 변경 없음")
        return

    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE places
                   SET estimated_duration = %(new_dur)s,
                       updated_at         = NOW()
                 WHERE place_id           = %(pid)s
                   AND visit_role         = 'meal'
                   AND estimated_duration = %(old_dur)s
            """, {"new_dur": FIXED_DURATION,
                  "pid":     TARGET_PLACE_ID,
                  "old_dur": row["estimated_duration"]})
        conn.commit()
        print(f"  완료 — estimated_duration {row['estimated_duration']} -> {FIXED_DURATION}")
    except Exception as exc:
        conn.rollback()
        print(f"  FAIL — {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="cat39 duration anomaly 보정 배치")
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
    print(f"  duration anomaly repair  {'[DRY-RUN]' if dry else '[APPLY]'}")
    print(f"{'=' * 60}")

    repair_group_b(conn, dry)
    repair_group_a(conn, dry)

    conn.close()
    if dry:
        print(f"\n[DRY-RUN] 완료 — 실제 변경 없음")


if __name__ == "__main__":
    main()

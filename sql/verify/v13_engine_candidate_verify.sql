-- v13_engine_candidate_verify.sql
-- 목적: 당일 엔진 후보군(category_id IN 12/14/39) 기준 가공 필드 검증
-- 판정 기준: 검증 판정 기준 섹션 참조
--   - 28/32 NULL은 실패 아님
--   - 12/14/39 NULL은 실패
-- READ-ONLY

-- [1] 전체 active 기준 — 분포 확인용 (판정 기준 아님)
SELECT
    category_id,
    COUNT(*)                                                            AS total,
    COUNT(*) FILTER (WHERE visit_role IS NULL OR visit_role = '')       AS null_role,
    COUNT(*) FILTER (WHERE visit_time_slot IS NULL)                     AS null_slot,
    COUNT(*) FILTER (WHERE estimated_duration IS NULL)                  AS null_duration,
    COUNT(*) FILTER (WHERE indoor_outdoor IS NULL OR indoor_outdoor='') AS null_io
FROM places
WHERE is_active = TRUE
GROUP BY category_id
ORDER BY category_id;

-- [2] 엔진 후보군(12/14/39) 기준 — 판정 기준
-- 이 쿼리의 null_* 컬럼이 0이어야 정상
SELECT
    category_id,
    COUNT(*)                                                            AS total,
    COUNT(*) FILTER (WHERE visit_role IS NULL OR visit_role = '')       AS null_role,
    COUNT(*) FILTER (WHERE visit_time_slot IS NULL)                     AS null_slot,
    COUNT(*) FILTER (WHERE estimated_duration IS NULL)                  AS null_duration,
    COUNT(*) FILTER (WHERE indoor_outdoor IS NULL OR indoor_outdoor='') AS null_io
FROM places
WHERE is_active    = TRUE
  AND category_id  IN (12, 14, 39)
GROUP BY category_id
ORDER BY category_id;

-- [3] 엔진 후보군 visit_role 이상값 (허용값: spot/culture/meal/cafe)
SELECT
    category_id,
    visit_role,
    COUNT(*) AS cnt,
    'UNEXPECTED' AS status
FROM places
WHERE is_active   = TRUE
  AND category_id IN (12, 14, 39)
  AND (visit_role IS NULL
       OR BTRIM(visit_role) NOT IN ('spot', 'culture', 'meal', 'cafe'))
GROUP BY category_id, visit_role
ORDER BY category_id, cnt DESC;

-- [4] 엔진 후보군 duration 범위 이탈 (cat12: 60~120 / cat14: 45~100 / cat39: 40~90)
SELECT
    category_id,
    place_id,
    name,
    estimated_duration,
    CASE category_id
        WHEN 12 THEN '60~120'
        WHEN 14 THEN '45~100'
        WHEN 39 THEN '40~90'
    END AS expected_range
FROM places
WHERE is_active    = TRUE
  AND category_id  IN (12, 14, 39)
  AND estimated_duration IS NOT NULL
  AND CASE category_id
          WHEN 12 THEN estimated_duration < 60  OR estimated_duration > 120
          WHEN 14 THEN estimated_duration < 45  OR estimated_duration > 100
          WHEN 39 THEN estimated_duration < 40  OR estimated_duration > 90
          ELSE FALSE
      END
ORDER BY category_id, place_id;

-- [5] 엔진 후보군 indoor_outdoor 허용값 외 (허용값: indoor/outdoor/mixed)
SELECT
    category_id,
    indoor_outdoor,
    COUNT(*) AS cnt
FROM places
WHERE is_active    = TRUE
  AND category_id  IN (12, 14, 39)
  AND (indoor_outdoor IS NULL
       OR BTRIM(indoor_outdoor) NOT IN ('indoor', 'outdoor', 'mixed'))
GROUP BY category_id, indoor_outdoor
ORDER BY category_id;

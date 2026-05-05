-- v07_time_slot_dist.sql
-- 목적: visit_time_slot 분포 점검
-- 컬럼 타입: VARCHAR(20)[] (배열) — 빈문자 비교 제외
-- OK 슬롯값: morning / lunch / afternoon / dinner
-- READ-ONLY

-- [1] NULL / 빈배열 / 정상 비율 (category별)
SELECT
    category_id,
    COUNT(*)                                                                          AS total,
    COUNT(*) FILTER (WHERE visit_time_slot IS NULL)                                   AS null_count,
    COUNT(*) FILTER (WHERE visit_time_slot IS NOT NULL AND cardinality(visit_time_slot) = 0) AS empty_array_count,
    COUNT(*) FILTER (WHERE visit_time_slot IS NOT NULL AND cardinality(visit_time_slot) > 0) AS filled_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE visit_time_slot IS NULL)
        / NULLIF(COUNT(*), 0), 1
    )                                                                                 AS null_pct
FROM places
WHERE is_active IS TRUE
GROUP BY category_id
ORDER BY category_id;

-- [2] 슬롯값 분포 (배열 원소 단위 unnest)
SELECT
    p.category_id,
    slot,
    COUNT(*)                                                                          AS cnt,
    ROUND(
        100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY p.category_id), 0), 1
    )                                                                                 AS pct,
    CASE
        WHEN slot IN ('morning', 'lunch', 'afternoon', 'dinner') THEN 'OK'
        ELSE                                                          'UNEXPECTED'
    END                                                                               AS status
FROM places p,
     UNNEST(p.visit_time_slot) AS slot
WHERE p.is_active IS TRUE
GROUP BY p.category_id, slot
ORDER BY p.category_id, cnt DESC;

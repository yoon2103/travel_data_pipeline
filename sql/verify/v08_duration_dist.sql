-- v08_duration_dist.sql
-- 목적: estimated_duration 분포 점검 (NULL 비율 + 범위 이탈 + 값 분포)
-- 컬럼명: estimated_duration (INT, 단위: 분)
-- DB constraint: 10~240 또는 NULL (migration_001)
-- category별 기대 범위: cat12 60~120 / cat14 45~100 / cat39 40~90
-- READ-ONLY

-- [1] NULL 비율, 통계, 기대 범위 이탈 건수 (category별)
SELECT
    category_id,
    COUNT(*)                                                                  AS total,
    COUNT(*) FILTER (WHERE estimated_duration IS NULL)                        AS null_count,
    COUNT(*) FILTER (WHERE estimated_duration IS NOT NULL)                    AS filled_count,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE estimated_duration IS NULL)
        / NULLIF(COUNT(*), 0), 1
    )                                                                         AS null_pct,
    ROUND(AVG(estimated_duration), 0)                                         AS avg_duration,
    MIN(estimated_duration)                                                   AS min_duration,
    MAX(estimated_duration)                                                   AS max_duration,
    COUNT(*) FILTER (WHERE estimated_duration IS NOT NULL AND CASE category_id
        WHEN 12 THEN estimated_duration < 60  OR estimated_duration > 120
        WHEN 14 THEN estimated_duration < 45  OR estimated_duration > 100
        WHEN 39 THEN estimated_duration < 40  OR estimated_duration > 90
        ELSE FALSE
    END)                                                                      AS out_of_range_count
FROM places
WHERE is_active IS TRUE
GROUP BY category_id
ORDER BY category_id;

-- [2] 값별 분포 (category별)
SELECT
    category_id,
    estimated_duration,
    COUNT(*)                                                                  AS cnt,
    ROUND(
        100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY category_id), 0), 1
    )                                                                         AS pct
FROM places
WHERE is_active IS TRUE
GROUP BY category_id, estimated_duration
ORDER BY category_id, estimated_duration NULLS FIRST;

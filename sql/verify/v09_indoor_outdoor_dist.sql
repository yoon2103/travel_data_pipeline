-- v09_indoor_outdoor_dist.sql
-- 목적: indoor_outdoor 분포 점검
-- OK 값: indoor / outdoor / mixed
-- MISSING: NULL 또는 빈문자
-- UNEXPECTED: 허용값 외 문자열
-- READ-ONLY

SELECT
    category_id,
    indoor_outdoor,
    COUNT(*)                                                                      AS cnt,
    ROUND(
        100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY category_id), 0), 1
    )                                                                             AS pct,
    CASE
        WHEN indoor_outdoor IS NULL OR BTRIM(indoor_outdoor) = '' THEN 'MISSING'
        WHEN indoor_outdoor IN ('indoor', 'outdoor', 'mixed')     THEN 'OK'
        ELSE                                                           'UNEXPECTED'
    END                                                                           AS status
FROM places
WHERE is_active IS TRUE
GROUP BY category_id, indoor_outdoor
ORDER BY category_id, cnt DESC;

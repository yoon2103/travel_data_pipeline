-- v11_ai_status_dist.sql
-- 목적: ai_validation_status 분포 — AI 처리 잔량(pending) 파악
-- 허용값: pending / success / fail
-- READ-ONLY

SELECT
    category_id,
    ai_validation_status,
    COUNT(*)                                                                          AS cnt,
    ROUND(
        100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY category_id), 0), 1
    )                                                                                 AS pct,
    CASE
        WHEN ai_validation_status IS NULL OR BTRIM(ai_validation_status) = '' THEN 'MISSING'
        WHEN BTRIM(ai_validation_status) IN ('pending', 'success', 'fail') THEN 'OK'
        ELSE                                                                     'UNEXPECTED'
    END                                                                               AS status
FROM places
WHERE is_active IS TRUE
GROUP BY category_id, ai_validation_status
ORDER BY category_id, cnt DESC;

-- v06_visit_role_dist.sql
-- 목적: visit_role 분포 점검
-- 실사용 기준 OK 값: spot / culture / meal / cafe
--   'rest'는 DB constraint(migration_003)에 정의돼 있으나
--   batch_rules.py DEFAULT_ROLE에 없어 실제 배정되지 않음 → UNEXPECTED 처리
-- READ-ONLY

SELECT
    category_id,
    visit_role,
    COUNT(*)                                                                            AS cnt,
    ROUND(
        100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (PARTITION BY category_id), 0), 1
    )                                                                                   AS pct,
    CASE
        WHEN visit_role IS NULL OR BTRIM(visit_role) = ''              THEN 'MISSING'
        WHEN BTRIM(visit_role) IN ('spot', 'culture', 'meal', 'cafe')  THEN 'OK'
        ELSE                                                                'UNEXPECTED'
    END                                                                                 AS status
FROM places
WHERE is_active IS TRUE
GROUP BY category_id, visit_role
ORDER BY category_id, cnt DESC;

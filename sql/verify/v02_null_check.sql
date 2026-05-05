-- v02_null_check.sql
-- 목적: 주요 필드 NULL / 빈문자 현황 (is_active = TRUE 기준)
-- 텍스트 계열 컬럼(overview, first_image_url, ai_summary, visit_role, indoor_outdoor)은
--   NULL과 빈문자('')를 동일하게 결측으로 집계한다.
-- visit_time_slot: VARCHAR(20)[] 배열 타입 → 빈문자 비교 제외, NULL만 체크
-- latitude/longitude 이상치: v04_coordinate_outlier.sql 에서 별도 검증
-- READ-ONLY

SELECT
    category_id,
    COUNT(*)                                                                         AS total,
    COUNT(*) FILTER (WHERE overview         IS NULL OR overview         = '')        AS null_overview,
    COUNT(*) FILTER (WHERE first_image_url  IS NULL OR first_image_url  = '')        AS null_image,
    COUNT(*) FILTER (WHERE ai_summary       IS NULL OR ai_summary       = '')        AS null_ai_summary,
    COUNT(*) FILTER (WHERE ai_tags          IS NULL)                                 AS null_ai_tags,
    COUNT(*) FILTER (WHERE embedding        IS NULL)                                 AS null_embedding,
    COUNT(*) FILTER (WHERE visit_role       IS NULL OR visit_role       = '')        AS null_visit_role,
    COUNT(*) FILTER (WHERE visit_time_slot  IS NULL)                                 AS null_time_slot,
    COUNT(*) FILTER (WHERE estimated_duration IS NULL)                               AS null_duration,
    COUNT(*) FILTER (WHERE indoor_outdoor   IS NULL OR indoor_outdoor   = '')        AS null_indoor_outdoor,
    COUNT(*) FILTER (WHERE latitude         IS NULL)                                 AS null_lat,
    COUNT(*) FILTER (WHERE longitude        IS NULL)                                 AS null_lng
FROM places
WHERE is_active = TRUE
GROUP BY category_id
ORDER BY category_id;

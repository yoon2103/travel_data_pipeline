-- v10a_misclassify_count.sql
-- 목적: 오분류 건수 집계
--   cat12(관광지)  기본값 outdoor → indoor 배정된 건수 확인
--   cat14(문화시설) 기본값 indoor → outdoor 배정된 건수 확인
--   cat39(음식점)  기본값 indoor → outdoor 배정된 건수 확인
-- 샘플 상세 조회: v10b_misclassify_sample.sql 참조
-- READ-ONLY

SELECT
    'cat12_indoor'  AS check_type,
    12              AS category_id,
    'indoor'        AS flagged_value,
    COUNT(*)        AS suspicious_count
FROM places
WHERE is_active IS TRUE AND category_id = 12 AND indoor_outdoor = 'indoor'

UNION ALL

SELECT
    'cat14_outdoor',
    14,
    'outdoor',
    COUNT(*)
FROM places
WHERE is_active IS TRUE AND category_id = 14 AND indoor_outdoor = 'outdoor'

UNION ALL

SELECT
    'cat39_outdoor',
    39,
    'outdoor',
    COUNT(*)
FROM places
WHERE is_active IS TRUE AND category_id = 39 AND indoor_outdoor = 'outdoor'

ORDER BY suspicious_count DESC;

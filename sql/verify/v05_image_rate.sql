-- v05_image_rate.sql
-- 목적: category별 first_image_url 보유율(%)
-- 추후 필요 시 first_image_thumb_url 기준 has_thumb 컬럼 추가 검토
-- READ-ONLY

SELECT
    category_id,
    COUNT(*)                                                                         AS total,
    COUNT(*) FILTER (WHERE first_image_url IS NOT NULL AND first_image_url != '')    AS has_image,
    COUNT(*) FILTER (WHERE first_image_url IS NULL     OR  first_image_url  = '')    AS no_image,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE first_image_url IS NOT NULL AND first_image_url != '')
        / NULLIF(COUNT(*), 0), 1
    )                                                                                AS image_rate_pct
FROM places
WHERE is_active IS TRUE
GROUP BY category_id
ORDER BY category_id;

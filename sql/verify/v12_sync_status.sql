-- v12_sync_status.sql
-- 목적: synced_at 최신/최구 시각 — category별 적재 진행 상태 확인
-- READ-ONLY

SELECT
    category_id,
    COUNT(*)                                          AS total,
    COUNT(*) FILTER (WHERE synced_at IS NULL)         AS never_synced,
    MIN(synced_at)                                    AS earliest_sync,
    MAX(synced_at)                                    AS latest_sync
FROM places
GROUP BY category_id
ORDER BY category_id;

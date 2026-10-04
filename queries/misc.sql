-- name: get-dashboard-charts
SELECT data FROM mat_dashboard_charts;

-- name: get-dashboard-counts
SELECT data FROM mat_dashboard_counts;

-- name: get-scoped-dashboard-counts
WITH scoped_lists AS (
    SELECT id, type, optin FROM lists WHERE id = ANY($1::INT[])
), scoped_subscribers AS (
    SELECT s.id, s.status FROM subscribers s
    WHERE EXISTS (SELECT 1 FROM subscriber_lists sl
                  WHERE sl.subscriber_id = s.id AND sl.list_id = ANY($1::INT[]))
), scoped_campaigns AS (
    SELECT c.id, c.status, c.sent FROM campaigns c
    WHERE EXISTS (SELECT 1 FROM campaign_lists cl
                  WHERE cl.campaign_id = c.id AND cl.list_id = ANY($1::INT[]))
)
SELECT JSON_BUILD_OBJECT(
    'subscribers', JSON_BUILD_OBJECT(
        'total', (SELECT COUNT(*) FROM scoped_subscribers),
        'blocklisted', (SELECT COUNT(*) FROM scoped_subscribers WHERE status = 'blocklisted'),
        -- Orphans have no list membership and are not visible to scoped users.
        'orphans', 0
    ),
    'lists', JSON_BUILD_OBJECT(
        'total', (SELECT COUNT(*) FROM scoped_lists),
        'private', (SELECT COUNT(*) FROM scoped_lists WHERE type = 'private'),
        'public', (SELECT COUNT(*) FROM scoped_lists WHERE type = 'public'),
        'optin_single', (SELECT COUNT(*) FROM scoped_lists WHERE optin = 'single'),
        'optin_double', (SELECT COUNT(*) FROM scoped_lists WHERE optin = 'double')
    ),
    'campaigns', JSON_BUILD_OBJECT(
        'total', (SELECT COUNT(*) FROM scoped_campaigns),
        'by_status', COALESCE((SELECT JSON_OBJECT_AGG(status, num) FROM
            (SELECT status, COUNT(*) AS num FROM scoped_campaigns GROUP BY status) r), '{}')
    ),
    'messages', COALESCE((SELECT SUM(sent) FROM scoped_campaigns), 0)
);

-- name: get-scoped-dashboard-charts
WITH scoped_campaigns AS (
    SELECT c.id FROM campaigns c
    WHERE EXISTS (SELECT 1 FROM campaign_lists cl
                  WHERE cl.campaign_id = c.id AND cl.list_id = ANY($1::INT[]))
), clicks_window AS (
    SELECT created_at::DATE AS to_date, created_at::DATE - INTERVAL '30 DAY' AS from_date
    FROM link_clicks WHERE campaign_id IN (SELECT id FROM scoped_campaigns)
    ORDER BY id DESC LIMIT 1
), views_window AS (
    SELECT created_at::DATE AS to_date, created_at::DATE - INTERVAL '30 DAY' AS from_date
    FROM campaign_views WHERE campaign_id IN (SELECT id FROM scoped_campaigns)
    ORDER BY id DESC LIMIT 1
)
SELECT JSON_BUILD_OBJECT(
    'link_clicks', COALESCE((SELECT JSON_AGG(ROW_TO_JSON(r)) FROM (
        SELECT COUNT(*) AS count, created_at::DATE AS date FROM link_clicks
        WHERE campaign_id IN (SELECT id FROM scoped_campaigns)
          AND created_at >= (SELECT from_date FROM clicks_window)
          AND created_at < (SELECT to_date FROM clicks_window) + INTERVAL '1 day'
        GROUP BY date ORDER BY date
    ) r), '[]'),
    'campaign_views', COALESCE((SELECT JSON_AGG(ROW_TO_JSON(r)) FROM (
        SELECT COUNT(*) AS count, created_at::DATE AS date FROM campaign_views
        WHERE campaign_id IN (SELECT id FROM scoped_campaigns)
          AND created_at >= (SELECT from_date FROM views_window)
          AND created_at < (SELECT to_date FROM views_window) + INTERVAL '1 day'
        GROUP BY date ORDER BY date
    ) r), '[]')
);

-- name: get-settings
SELECT JSON_OBJECT_AGG(key, value) AS settings FROM (SELECT * FROM settings ORDER BY key) t;

-- name: update-settings
UPDATE settings AS s SET value = c.value
    -- For each key in the incoming JSON map, update the row with the key and its value.
    FROM(SELECT * FROM JSONB_EACH($1)) AS c(key, value) WHERE s.key = c.key;

-- name: update-settings-by-key
UPDATE settings SET value = $2, updated_at = NOW() WHERE key = $1;

-- name: get-db-info
SELECT JSON_BUILD_OBJECT('version', (SELECT VERSION()),
                        'size_mb', (SELECT ROUND(pg_database_size((SELECT CURRENT_DATABASE()))/(1024^2)))) AS info;

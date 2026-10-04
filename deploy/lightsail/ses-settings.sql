-- Initial small-list settings. SMTP credentials are applied separately.
UPDATE settings SET value = '"https://lists.creativeattribution.com"'::jsonb WHERE key = 'app.root_url';
UPDATE settings SET value = '"Creative Attribution <newsletter@creativeattribution.com>"'::jsonb WHERE key = 'app.from_email';
UPDATE settings SET value = '1'::jsonb WHERE key IN ('app.concurrency', 'app.message_rate');
UPDATE settings SET value = '100'::jsonb WHERE key = 'app.batch_size';
UPDATE settings SET value = 'true'::jsonb WHERE key IN ('bounce.enabled', 'bounce.webhooks_enabled', 'bounce.ses_enabled');
UPDATE settings SET value = '{"soft":{"count":2,"action":"none"},"hard":{"count":1,"action":"blocklist"},"complaint":{"count":1,"action":"blocklist"}}'::jsonb WHERE key = 'bounce.actions';
UPDATE settings SET value = '"/listmonk/uploads"'::jsonb WHERE key = 'upload.filesystem.upload_path';

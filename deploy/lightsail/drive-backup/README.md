# Encrypted Google Drive backups

The existing server backup service creates a PostgreSQL custom-format dump and
an uploaded-media archive. The database includes subscribers, their associated
lists, and subscription/unsubscribe status, as well as campaigns and templates.
`upload.py` copies the newest complete pair to the private personal Google Drive
folder `Mailing List Backups/encrypted` through rclone crypt.

The physical Drive location is **Backups → Mailing List Server → Mailing List
Backups → encrypted**. The administrator's chosen parent folder is
[Mailing List Server](https://drive.google.com/drive/folders/1kIw7aGYwKAJFpviMJUcrQOSTCbKZyywx).
The existing [Mailing List Backups folder](https://drive.google.com/drive/folders/1dvS3WSt9xx9-8H1OmVLYix7vpcdZC7J_)
was moved there on 13 October 2026 Sydney time, preserving its file IDs,
encryption, and private ownership.

An app-created shortcut named **Mailing List Backups** remains in **My Drive**.
Keep that shortcut and its name: the scheduled remote follows it into the moved
folder. It is a link to the same files, not another backup copy. This preserves
the existing server configuration and narrow `drive.file` permission without
reopening SSH. `verify-location.py` confirmed the existing file IDs, sizes, and
encrypted hashes stayed unchanged and checked an encrypted write/read through
the exact scheduled path. Its uniquely named harmless probe was moved to Trash;
no database restore test was performed.

The existing `listmonk-backup.timer` runs at **03:00 Australia/Sydney** daily.
`drive-upload.conf` adds the upload after a successful local backup. The uploader
downloads and decrypts the remote data in memory to compare it with the local
files before recording success. This is a file-integrity check, not a database
restore test. A restore test was explicitly excluded by the administrator.

Approximately 30 days are retained in the active Drive folder. Only recognized
older backup files are moved to Trash, and only after a newer backup verifies.
Drive's Trash still uses storage. There is no permanent-delete operation here.
Local retention remains the existing seven-day policy.

## Private configuration and recovery

The Google project is `mailing-list-backup`. Its OAuth application is in
Production mode, uses the dedicated Desktop client, and requests only
`https://www.googleapis.com/auth/drive.file` with offline authorization.
The app can access files it creates or that the user explicitly opens with it;
it has no permission to read all existing Drive files or Gmail.

The server configuration is:

```
/opt/listmonk/deploy/lightsail/secrets/rclone-backups.conf
```

It is root-owned and mode 0600. The separate recovery copy on the administrator's
PC is:

```
C:\Users\MQ10007341\Documents\Github\attribution-listmonk\deploy\lightsail\secrets\rclone-backups.conf
```

The PC file is ignored by Git and its ACL allows only the current user and
SYSTEM. **Keep a further secure copy of this configuration, such as in a password
manager or offline encrypted storage.** It contains the encryption password and
salt as well as the Google token. Rclone's password obscuring is reversible;
the configuration itself must be kept private. Never place it in the backup
Drive folder or commit it to Git. Losing both configuration copies means losing
the ability to decrypt the Drive files. Recreating the OAuth client or obtaining
a new token cannot recreate the encryption keys.

The PC recovery copy may contain an older access token; rclone can use its
refresh token. If Google authorization is revoked or expires, reauthorize the
existing remote while preserving the crypt password and salt. Do not rerun
initial setup in a way that generates replacement encryption keys.

## Operations

On the existing server:

```sh
sudo systemctl list-timers listmonk-backup.timer
sudo systemctl status listmonk-backup.service
sudo journalctl -u listmonk-backup.service --since yesterday
sudo cat /opt/listmonk/deploy/lightsail/secrets/drive-backup-status.json
```

The status file records the latest successful file verification, backup names,
bytes, and number of old files moved to Trash. If a job fails, it leaves the
previous successful status in place and systemd records a failure. No email
alerts or paid monitoring resources were configured.

To create a fresh backup and upload it through the same scheduled service:

```sh
sudo systemctl start listmonk-backup.service
```

The uploader rejects stale, incomplete, empty, or oversized backup pairs and
requires available Drive storage. The current size guard is 128 MiB per daily
pair. An inherited `RCLONE_*` environment cannot override its remote settings.

## Retrieve files after a server failure

Use the private recovery configuration with rclone on a trusted computer.
Listing through the crypt remote shows the original filenames; opening the
Drive website shows encrypted names.

```powershell
$backupConfig = 'C:\Users\MQ10007341\Documents\Github\attribution-listmonk\deploy\lightsail\secrets\rclone-backups.conf'
$backupTool = 'C:\Users\MQ10007341\Documents\Github\attribution-listmonk\deploy\lightsail\secrets\tools\rclone.exe'
& $backupTool --config $backupConfig lsf listmonk-backups:
```

Choose a matching timestamp for the database dump and media archive. Copy each
selected file from `listmonk-backups:FILENAME` to a private local recovery
directory using `rclone copyto --immutable`; this downloads and decrypts it.
Protect those decrypted files because they contain subscriber details. Database
restoration is a separate administrator action; never restore over a running
production database without a specific recovery plan.

## Initial setup and website notice

`install-rclone.py` obtains the pinned official Windows/Linux amd64 release and
verifies the archive's SHA-256 against the official release checksums.
`authorize-local.py` performs the initial Desktop OAuth flow on Windows without
printing credentials or tokens. It refuses to overwrite an existing crypt
configuration. This is an initial-setup helper, not the daily backup job.

The public pages are served at `/backup-info` and `/backup-privacy` by Caddy from
`/data/listmonk-backup-info` inside the existing proxy's persistent volume.
The original server Caddyfile is saved privately as
`secrets/Caddyfile.pre-drive-backup`. No new host or cloud resource is needed.
When rebuilding the proxy on a new server, copy the HTML files into this path
before enabling the two Caddy routes.

This uses the existing VM, existing network allowance, and available personal
Drive storage. No paid resource, storage upgrade, billing account, or paid
monitoring feature is enabled by this setup. Storage limits or future provider
pricing changes may require review rather than an automatic purchase.

#!/usr/bin/env python3
"""Check the moved Drive destination with a harmless encrypted write/read probe."""
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess

DEPLOY = Path(__file__).resolve().parent.parent
CONFIG = DEPLOY / "secrets/rclone-backups.conf"
RCLONE = DEPLOY / "secrets/tools/rclone.exe"
ROOT = "0ANygLUUs-asJUk9PVA"
BACKUP_FOLDER = "1dvS3WSt9xx9-8H1OmVLYix7vpcdZC7J_"
ENCRYPTED_FOLDER = "1O14HkKdGdPXefO-7Ivzoj2xmDmkRL7ur"


def run(*args, data=None):
    result = subprocess.run([str(RCLONE), "--config", str(CONFIG), "--log-level", "ERROR",
                             "--retries", "2", *args], input=data, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"rclone {args[0]} failed; credential output suppressed")
    return result.stdout


def query(value):
    return json.loads(run("backend", "query", "listmonk-drive:", value))


shortcut = query(f"name = 'Mailing List Backups' and '{ROOT}' in parents and trashed = false")
assert len(shortcut) == 1, "The configured root path must resolve uniquely"
assert shortcut[0]["mimeType"] == "application/vnd.google-apps.shortcut"
assert shortcut[0]["shortcutDetails"]["targetId"] == BACKUP_FOLDER
before = query(f"'{ENCRYPTED_FOLDER}' in parents and trashed = false")
before_files = {value["id"]: (value.get("md5Checksum"), value.get("size")) for value in before}
visible = json.loads(run("lsjson", "listmonk-backups:", "--files-only", "--max-depth", "1"))
assert len(visible) == len(before_files) and len(visible) >= 4, "Existing backups must remain accessible"
probe = "listmonk-backups:.destination-check-" + secrets.token_hex(12) + ".txt"
contents = b"Harmless encrypted backup-destination check: " + secrets.token_bytes(32)
created = False
try:
    run("rcat", probe, data=contents)
    created = True
    assert run("cat", probe) == contents, "Encrypted readback must match the written probe"
    after = query(f"'{ENCRYPTED_FOLDER}' in parents and trashed = false")
    after_files = {value["id"]: (value.get("md5Checksum"), value.get("size")) for value in after}
    assert len(after_files.keys() - before_files.keys()) == 1, "Probe must be saved in the moved folder"
    assert all(after_files.get(key) == value for key, value in before_files.items()), "Backup files must stay unchanged"
finally:
    if created:
        # Retire only the uniquely named harmless probe; normal Drive Trash is recoverable.
        run("deletefile", probe, "--drive-use-trash=true")
remaining = query(f"'{ENCRYPTED_FOLDER}' in parents and trashed = false")
assert {value["id"]: (value.get("md5Checksum"), value.get("size")) for value in remaining} == before_files
report = {"verified_at_utc": datetime.now(timezone.utc).isoformat(),
          "destination_parent_folder_id": "1kIw7aGYwKAJFpviMJUcrQOSTCbKZyywx",
          "backup_folder_id": BACKUP_FOLDER, "encrypted_folder_id": ENCRYPTED_FOLDER,
          "existing_backup_files": len(before_files), "existing_file_ids_sizes_and_hashes_unchanged": True,
          "encrypted_write_read_probe_passed": True, "probe_moved_to_trash": True,
          "scheduled_remote_path": "listmonk-drive:Mailing List Backups/encrypted",
          "automation_shortcut_id": shortcut[0]["id"], "database_restore_test_performed": False}
(Path(__file__).parent / "location-verification-20261013.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))

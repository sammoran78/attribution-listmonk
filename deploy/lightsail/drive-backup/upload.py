#!/usr/bin/env python3
"""Copy the newest complete local backup to the dedicated encrypted Drive remote."""
import configparser
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess

DEPLOY = Path(__file__).resolve().parent.parent
REMOTE = "listmonk-backups:"
CRYPT_PATH = "listmonk-drive:Mailing List Backups/encrypted"
NAME = re.compile(r"^(db|uploads)-(\d{8}T\d{6}Z)\.(dump|tar\.gz)$")
MAX_BYTES = 128 * 1024 * 1024


def timestamp(value):
    return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def backup_name(value):
    match = NAME.fullmatch(value)
    if not match or (match[1], match[3]) not in (("db", "dump"), ("uploads", "tar.gz")):
        return None
    try:
        return match[1], timestamp(match[2])
    except ValueError:
        return None


def newest_pair(directory, now):
    if directory.is_symlink():
        raise RuntimeError("Backup directory must not be a symlink")
    grouped = {}
    for path in directory.iterdir():
        parsed = backup_name(path.name)
        if parsed:
            if path.is_symlink() or not path.is_file():
                raise RuntimeError("Backup files must be regular files")
            grouped.setdefault(parsed[1], {})[parsed[0]] = path
    if not grouped:
        raise RuntimeError("No local backup files were found")
    created = max(grouped)
    pair = grouped[created]
    if set(pair) != {"db", "uploads"}:
        raise RuntimeError("Newest backup is incomplete; refusing to upload an older pair")
    if now - created > timedelta(hours=36) or created - now > timedelta(minutes=10):
        raise RuntimeError("Newest backup timestamp is stale or in the future")
    files = [pair["db"], pair["uploads"]]
    sizes = [path.stat().st_size for path in files]
    if min(sizes) <= 0 or sum(sizes) > MAX_BYTES:
        raise RuntimeError("Backup is empty or exceeds the 128 MiB upload guard")
    return files


def validate_config(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Private rclone config is missing or is a symlink")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise RuntimeError("rclone config must have mode 0600")
    config = configparser.ConfigParser(interpolation=None)
    config.read(path, encoding="utf-8")
    crypt = config["listmonk-backups"]
    drive = config["listmonk-drive"]
    if (crypt.get("type") != "crypt" or crypt.get("remote") != CRYPT_PATH
            or crypt.get("filename_encryption") != "standard"
            or crypt.get("directory_name_encryption") != "true"
            or not crypt.get("password") or not crypt.get("password2")):
        raise RuntimeError("Destination must be the configured encrypted backup folder")
    if (drive.get("type") != "drive" or drive.get("scope") != "drive.file"
            or not drive.get("client_id") or not drive.get("client_secret")
            or not json.loads(drive.get("token", "{}")).get("refresh_token")):
        raise RuntimeError("Drive must use the dedicated file scope and offline authorization")


def rclone(config, *args):
    # Prevent inherited rclone environment settings from overriding encryption or scope.
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("RCLONE_")}
    result = subprocess.run(["rclone", "--config", str(config), "--log-level", "ERROR",
                             "--tpslimit", "2", "--transfers", "1", "--checkers", "1",
                             "--retries", "3", "--low-level-retries", "5", *args],
                            env=environment, text=True, capture_output=True, timeout=1800)
    if result.returncode:
        # Never include raw authorization errors or tokens in the journal.
        raise RuntimeError(f"rclone {args[0]} failed (exit {result.returncode})")
    return result.stdout


def upload(deploy=DEPLOY, now=None, run=rclone):
    now = now or datetime.now(timezone.utc)
    config = deploy / "secrets/rclone-backups.conf"
    validate_config(config)
    files = newest_pair(deploy / "backups", now)
    size = sum(path.stat().st_size for path in files)
    capacity = json.loads(run(config, "about", "listmonk-drive:", "--json"))
    if "free" not in capacity or capacity["free"] < size * 2 + 1024 * 1024:
        raise RuntimeError("Drive has insufficient free storage for a verified backup")
    selection = ["--max-depth", "1"]
    for path in files:
        selection += ["--include", "/" + path.name]
    run(config, "copy", str(deploy / "backups"), REMOTE, "--immutable", *selection)
    run(config, "check", str(deploy / "backups"), REMOTE, "--download", "--one-way", *selection)
    # Prune only recognized backup filenames and only after a successful download check.
    entries = json.loads(run(config, "lsjson", REMOTE, "--files-only", "--max-depth", "1"))
    retired = 0
    for entry in entries:
        name = entry.get("Path", "")
        parsed = backup_name(name)
        if parsed and parsed[1] < now - timedelta(days=30):
            run(config, "deletefile", REMOTE + name, "--drive-use-trash=true")
            retired += 1
    state = {"verified_at": now.isoformat(), "files": [path.name for path in files],
             "bytes": size, "old_files_moved_to_trash": retired}
    state_file = deploy / "secrets/drive-backup-status.json"
    temporary = state_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(state_file)
    print(json.dumps(state))
    return state


if __name__ == "__main__":
    os.umask(0o077)
    upload()

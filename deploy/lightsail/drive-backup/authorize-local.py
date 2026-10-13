#!/usr/bin/env python3
"""Authorize the dedicated Drive client without printing secrets or tokens."""
import configparser
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

deploy = Path(__file__).resolve().parent.parent
private = deploy / "secrets"
rclone = private / "tools/rclone.exe"
destination = private / "rclone-backups.conf"
if destination.exists():
    raise SystemExit("Private config already exists; preserve its encryption keys")
credentials = json.loads((private / "google-drive-oauth.json").read_text())["installed"]
environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("RCLONE_")}
environment.update(RCLONE_DRIVE_CLIENT_ID=credentials["client_id"],
                   RCLONE_DRIVE_CLIENT_SECRET=credentials["client_secret"],
                   RCLONE_DRIVE_SCOPE="drive.file")


def restrict(path):
    user = subprocess.run(["whoami"], capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)",
                    "SYSTEM:(F)"], capture_output=True, check=True)


process = subprocess.Popen([str(rclone), "authorize", "drive", "--auth-no-open-browser"],
                           env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True)
output = []
ready = False
for line in process.stdout:
    output.append(line)
    match = re.search(r"http://127\.0\.0\.1:53682/auth\?[^\s]+", line)
    if match and not ready:
        url_file = private / "drive-authorize-url.txt"
        url_file.write_text(match.group(0), encoding="utf-8")
        restrict(url_file)
        ready = True
        print("Google authorization is ready in the private local URL file", flush=True)
if process.wait():
    raise SystemExit("Authorization failed; no credential output was printed")
token = None
for candidate in re.findall(r"\{[^\n]+\}", "".join(output)):
    try:
        value = json.loads(candidate)
        if value.get("refresh_token") and value.get("access_token"):
            token = value
    except (ValueError, AttributeError):
        pass
if token is None:
    raise SystemExit("No offline authorization returned; private config was not created")


def obscure():
    return subprocess.run([str(rclone), "obscure", "-"], input=secrets.token_urlsafe(48) + "\n",
                          text=True, capture_output=True, check=True).stdout.strip()


config = configparser.ConfigParser(interpolation=None)
config["listmonk-drive"] = {"type": "drive", "scope": "drive.file",
    "client_id": credentials["client_id"], "client_secret": credentials["client_secret"],
    "token": json.dumps(token)}
config["listmonk-backups"] = {"type": "crypt", "remote": "listmonk-drive:Mailing List Backups/encrypted",
    "filename_encryption": "standard", "directory_name_encryption": "true",
    "password": obscure(), "password2": obscure()}
with destination.open("x", encoding="utf-8") as handle:
    config.write(handle)
restrict(destination)
print("Offline Drive authorization and encryption recovery config saved privately", flush=True)

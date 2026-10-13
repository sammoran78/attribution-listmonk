#!/usr/bin/env python3
"""Install the pinned official rclone binary after verifying its SHA-256."""
import hashlib
import io
import os
from pathlib import Path
import platform
import subprocess
import zipfile

VERSION = "v1.75.2"
system = platform.system().lower()
if system not in ("windows", "linux") or platform.machine().lower() not in ("amd64", "x86_64"):
    raise SystemExit("Only Windows/Linux amd64 are configured")
name = f"rclone-{VERSION}-{system}-amd64.zip"
base = f"https://downloads.rclone.org/{VERSION}/"
def download(url):
    # The official CDN rejects Python's default user agent on some networks.
    return subprocess.run(["curl.exe" if system == "windows" else "curl", "--fail",
                           "--silent", "--show-error", "--location", "--max-time", "120", url],
                          capture_output=True, check=True).stdout

checksums = download(base + "SHA256SUMS").decode()
expected = next(parts[0] for line in checksums.splitlines()
                if len(parts := line.split()) == 2 and parts[1].lstrip("*") == name)
data = download(base + name)
if hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit("Download checksum mismatch; nothing installed")
binary = "rclone.exe" if system == "windows" else "rclone"
target = (Path(__file__).resolve().parent.parent / "secrets/tools/rclone.exe"
          if system == "windows" else Path("/usr/local/bin/rclone"))
target.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    payload = archive.read(f"rclone-{VERSION}-{system}-amd64/{binary}")
temporary = target.with_suffix(".download")
temporary.write_bytes(payload)
if system == "linux":
    temporary.chmod(0o755)
os.replace(temporary, target)
print(f"Installed official rclone {VERSION}; SHA-256 verified")

"""Update only the installed CAIRN template, with backup and unsent render checks.

Default audits without writing to listmonk. --apply requires the hash from the
audit, guarding against concurrent template edits. Never sends an email.
"""
import argparse
import base64
import datetime
import hashlib
import html.parser
import http.cookiejar
import json
import pathlib
import urllib.parse
import urllib.request
import uuid


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.extend(v for k, v in attrs if k == "href")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-hash")
    parser.add_argument("--deploy-dir", type=pathlib.Path, default=pathlib.Path("/opt/listmonk/deploy/lightsail"))
    args = parser.parse_args()
    base = pathlib.Path(__file__).resolve().parent
    ids = json.loads((base / "installation.json").read_text())
    url = "https://lists.creativeattribution.com"
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    client.open(url + "/admin/login", timeout=30).read()
    nonce = next(c.value for c in jar if c.name == "nonce")
    client.open(url + "/admin/login", data=urllib.parse.urlencode({
        "username": "admin", "password": (args.deploy_dir / "secrets/admin_password").read_text().strip(),
        "nonce": nonce,
    }).encode(), timeout=30).read()

    def request(path, data=None, method=None, content_type="application/json", raw=False):
        if data is not None and not isinstance(data, bytes):
            data = json.dumps(data).encode()
        req = urllib.request.Request(url + path, data=data, method=method, headers={"Content-Type": content_type})
        with client.open(req, timeout=40) as response:
            body = response.read()
        return body.decode() if raw else json.loads(body)["data"]

    tpl_path = f'/api/templates/{ids["template_id"]}'
    original = request(tpl_path)
    assert original["type"] == "campaign" and original["is_default"] is False
    digest = hashlib.sha256(original["body"].encode()).hexdigest()
    if not args.apply:
        (base / "live-template-before-dark.html").write_text(original["body"])
        print(json.dumps({"template_id": original["id"], "body_sha256": digest, "name": original["name"]}))
        return
    assert args.expected_hash == digest, "Live template changed since audit; review it before applying."
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.deploy_dir / "secrets" / f"cairn-template-before-dark-{stamp}.json"
    backup.write_text(json.dumps(original, indent=2) + "\n")
    backup.chmod(0o600)
    current_campaign = request(f'/api/campaigns/{ids["campaign_id"]}')

    file = base / "assets/cairn-logo-band.png"
    receipt_path = base / "dark-mode-installation.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    for prefix, image_file in (("logo", file), ("dark_logo", base / "assets/cairn-logo-band-dark.png")):
        sha_key = prefix + "_asset_sha256"
        asset_sha = hashlib.sha256(image_file.read_bytes()).hexdigest()
        if not receipt.get(prefix + "_url") or receipt.get(sha_key) != asset_sha:
            boundary = "cairn-" + uuid.uuid4().hex
            data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{image_file.name}"\r\n'
                    'Content-Type: image/png\r\n\r\n').encode() + image_file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            media = request("/api/media", data, "POST", "multipart/form-data; boundary=" + boundary)
            receipt.update({prefix + "_media_id": media["id"], prefix + "_url": urllib.parse.urljoin(url, media["url"]), sha_key: asset_sha})
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        with urllib.request.urlopen(receipt[prefix + "_url"], timeout=30) as response:
            assert response.read() == image_file.read_bytes(), "Uploaded logo must match the prepared pixels."
    logo_url = receipt["logo_url"]
    dark_logo_url = receipt["dark_logo_url"]
    body = (base / "campaign-template.html").read_text().replace(
        "https://lists.creativeattribution.com/uploads/cairn-logo-band.png", logo_url).replace(
        "https://lists.creativeattribution.com/uploads/cairn-logo-band-dark.png", dark_logo_url)
    assert body.count('{{ template "content" . }}') == 1 and body.count("{{ TrackView }}") == 1
    replacement = {k: original[k] for k in ("name", "type", "subject", "body_source")}
    replacement["body"] = body
    fixture_id = None
    try:
        request(tpl_path, replacement, "PUT")
        generic = request(tpl_path + "/preview", raw=True)
        assert "Date and time to be confirmed" in generic
        fixture = {
            "name": "[TEMPORARY PREVIEW] CAIRN dark-mode verification",
            "subject": "CAIRN dark-mode layout example", "from_email": current_campaign["from_email"],
            "lists": [ids["list_id"]], "type": "regular", "content_type": "richtext", "messenger": "email",
            "template_id": ids["template_id"], "body": '<p>SAMPLE LAYOUT ONLY — NOT A SCHEDULED EVENT</p>' + (base / "campaign-body.html").read_text(),
            "attribs": json.loads((base / "example-event.json").read_text()), "archive": False,
        }
        fixture["attribs"]["cairn"]["calendar_ics_url"] = ids["sample_calendar_url"]
        saved = request("/api/campaigns", fixture)
        fixture_id = saved["id"]
        assert saved["status"] == "draft" and saved["sent"] == 0 and not saved.get("send_at")
        sample = request(f"/api/campaigns/{fixture_id}/preview", raw=True)
        assert "Tuesday, 20 October 2026" in sample and "12:00 pm–1:00 pm AEDT" in sample
        assert "<!--[if mso]>" in sample and "ZgotmplZ" not in sample and "{{" not in sample
        assert "Unsubscribe" in sample and "View in your browser" in sample and "Join Zoom meeting" in sample
        links = Links()
        links.feed(sample)
        google = next(x for x in links.urls if x.startswith("https://calendar.google.com/"))
        outlook = next(x for x in links.urls if x.startswith("https://outlook.office.com/"))
        g = urllib.parse.parse_qs(urllib.parse.urlsplit(google).query)
        o = urllib.parse.parse_qs(urllib.parse.urlsplit(outlook).query)
        assert g["dates"] == ["20261020T010000Z/20261020T020000Z"]
        assert o["startdt"] == ["2026-10-20T01:00:00Z"] and o["enddt"] == ["2026-10-20T02:00:00Z"]
        assert ids["sample_calendar_url"] in links.urls
        assert fixture["attribs"]["cairn"]["zoom_url"] in links.urls
        embedded = "data:image/png;base64," + base64.b64encode(file.read_bytes()).decode()
        sample = sample.replace(logo_url, embedded).replace(dark_logo_url,
            "data:image/png;base64," + base64.b64encode((base / "assets/cairn-logo-band-dark.png").read_bytes()).decode())
        # Separate standalone proofs; the dark proof activates the Outlook selectors.
        (base / "preview-light.html").write_text(sample.replace('<html ', '<html style="color-scheme:light" ', 1).replace('<style>', '<style>\n:root { color-scheme:light; }', 1))
        (base / "preview-dark.html").write_text(sample.replace('<html ', '<html data-ogsc ', 1))
        current_preview = request(f'/api/campaigns/{ids["campaign_id"]}/preview', raw=True)
        assert logo_url in current_preview and "cairn-surface" in current_preview
        assert request(f'/api/campaigns/{ids["campaign_id"]}') == current_campaign, "Existing campaign changed during verification."
        persisted = request(tpl_path)
        assert persisted["is_default"] is False and persisted["body"] == body
        receipt.update({"template_id": original["id"], "backup": str(backup), "checks": "passed", "email_sent": False})
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt))
    except Exception:
        restore = {k: original[k] for k in ("name", "type", "subject", "body", "body_source")}
        request(tpl_path, restore, "PUT")
        raise
    finally:
        if fixture_id is not None:
            request(f"/api/campaigns/{fixture_id}", method="DELETE")


if __name__ == "__main__":
    main()

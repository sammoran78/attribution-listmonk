"""Install the CAIRN template and an unsent starter draft on the existing VM.

Runs on the VM; uses its private admin file without logging credentials.
Only template/media/draft and preview endpoints are called, never send/status.
"""
import argparse
import copy
import html.parser
import http.cookiejar
import json
import pathlib
import urllib.error
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
    parser.add_argument("--deploy-dir", type=pathlib.Path, default=pathlib.Path("/opt/listmonk/deploy/lightsail"))
    args = parser.parse_args()
    base = pathlib.Path(__file__).resolve().parent
    result_path = base / "installation.json"
    if result_path.exists():
        raise RuntimeError("Already installed. Use the existing IDs; do not overwrite an edited draft.")
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
        try:
            with client.open(req, timeout=40) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{path}: HTTP {exc.code}: {exc.read().decode()}") from exc
        return body.decode() if raw else json.loads(body)["data"]

    def upload(file, mime):
        boundary = "cairn-" + uuid.uuid4().hex
        data = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\n'
                f'Content-Type: {mime}\r\n\r\n').encode() + file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        media = request("/api/media", data, "POST", "multipart/form-data; boundary=" + boundary)
        return media, urllib.parse.urljoin(url, media["url"])

    lists = request("/api/lists?per_page=all")["results"]
    cairn_lists = [x for x in lists if x["name"].startswith("CAIRN")]
    assert len(cairn_lists) == 1, "Expected exactly one CAIRN list"
    existing = request("/api/templates")
    name = "CAIRN — Reading group invitation"
    assert not any(x["name"] == name for x in existing), "Template name already exists; preserve it"
    logo, logo_url = upload(base / "assets/cairn-main-logo.png", "image/png")
    sample_calendar, calendar_url = upload(base / "example-output/cairn-reading-group.ics", "text/calendar; charset=utf-8")
    body = (base / "campaign-template.html").read_text()
    original_logo = "https://www.cairn.org.au/wp-content/uploads/2026/01/CAIRN_Main-logo-1.png"
    body = body.replace(original_logo, logo_url).replace("https://lists.creativeattribution.com/uploads/cairn-main-logo.png", logo_url)
    template = request("/api/templates", {"name": name, "type": "campaign", "body": body})
    generic_preview = request(f'/api/templates/{template["id"]}/preview', raw=True)
    assert "Date and time to be confirmed" in generic_preview
    assert "ZgotmplZ" not in generic_preview and "{{" not in generic_preview
    starter = json.loads((base / "starter-attributes.json").read_text())
    campaign = {
        "name": "[DRAFT] CAIRN reading group — starter", "subject": "[Reading group title] | CAIRN",
        "from_email": "CAIRN <newsletter@creativeattribution.com>", "lists": [cairn_lists[0]["id"]],
        "type": "regular", "content_type": "richtext", "messenger": "email", "template_id": template["id"],
        "body": (base / "campaign-body.html").read_text(),
        "altbody": (base / "campaign-alt-body.txt").read_text(),
        "attribs": starter, "tags": ["cairn", "reading-group", "starter"], "archive": False,
    }
    saved = request("/api/campaigns", campaign)
    ids = {"template_id": template["id"], "campaign_id": saved["id"], "list_id": cairn_lists[0]["id"],
           "logo_media_id": logo["id"], "sample_calendar_media_id": sample_calendar["id"],
           "logo_url": logo_url, "sample_calendar_url": calendar_url}
    result_path.write_text(json.dumps(ids, indent=2) + "\n")
    sample = copy.deepcopy(campaign)
    sample["attribs"] = json.loads((base / "example-event.json").read_text())
    sample["attribs"]["cairn"]["calendar_ics_url"] = calendar_url
    sample["body"] = '<p style="font-size:12px;color:#784322;font-weight:700;">SAMPLE LAYOUT ONLY — NOT A SCHEDULED EVENT</p>' + sample["body"]
    try:
        request(f'/api/campaigns/{saved["id"]}', sample, "PUT")
        preview = request(f'/api/campaigns/{saved["id"]}/preview', raw=True)
        assert "Tuesday, 20 October 2026" in preview and "12:00 pm–1:00 pm AEDT" in preview
        assert "<!--[if mso]>" in preview, "Outlook markup must survive Go HTML rendering"
        assert "ZgotmplZ" not in preview and "{{" not in preview
        links = Links()
        links.feed(preview)
        google = next(x for x in links.urls if x.startswith("https://calendar.google.com/"))
        outlook = next(x for x in links.urls if x.startswith("https://outlook.office.com/"))
        g = urllib.parse.parse_qs(urllib.parse.urlsplit(google).query)
        o = urllib.parse.parse_qs(urllib.parse.urlsplit(outlook).query)
        assert g["dates"] == ["20261020T010000Z/20261020T020000Z"]
        assert g["ctz"] == ["Australia/Sydney"]
        assert o["startdt"] == ["2026-10-20T01:00:00Z"] and o["enddt"] == ["2026-10-20T02:00:00Z"]
        assert sample["attribs"]["cairn"]["zoom_url"] in g["details"][0]
        assert calendar_url in links.urls
        (base / "preview.html").write_text(preview)
        print("Sample render passed: calendar UTC times, Sydney daylight saving, Zoom, Outlook markup, and .ics link.")
    finally:
        request(f'/api/campaigns/{saved["id"]}', campaign, "PUT")
    starter_preview = request(f'/api/campaigns/{saved["id"]}/preview', raw=True)
    assert "Date and time to be confirmed" in starter_preview and "Joining link to be confirmed" in starter_preview
    assert "calendar.google.com" not in starter_preview and "Join Zoom meeting" not in starter_preview
    assert "Unsubscribe" in starter_preview and "View in your browser" in starter_preview
    (base / "starter-preview.html").write_text(starter_preview)
    persisted = request(f'/api/campaigns/{saved["id"]}')
    assert persisted["status"] == "draft" and not persisted.get("send_at")
    assert persisted["attribs"]["cairn"]["start"] == "" and persisted["sent"] == 0
    assert request(f'/api/templates/{template["id"]}')["is_default"] is False
    ids["checks"] = "passed"
    result_path.write_text(json.dumps(ids, indent=2) + "\n")
    print(json.dumps(ids))


if __name__ == "__main__":
    main()

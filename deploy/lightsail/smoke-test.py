"""Verify admin login and send previews only to SES mailbox simulator addresses."""
import http.cookiejar
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request


def main():
    base = pathlib.Path(__file__).resolve().parent
    if (base / "secrets/smoke-result.json").exists():
        print("Simulator setup test already ran; no additional emails sent.")
        return
    url = "https://lists.creativeattribution.com"
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    client.open(url + "/admin/login", timeout=30).read()
    nonce = next(c.value for c in jar if c.name == "nonce")
    form = urllib.parse.urlencode({"username": "admin", "password": (base / "secrets/admin_password").read_text().strip(), "nonce": nonce}).encode()
    client.open(url + "/admin/login", data=form, timeout=30).read()

    def api(path, data=None, method=None):
        payload = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(url + path, data=payload, method=method, headers={"Content-Type": "application/json"})
        try:
            with client.open(req, timeout=60) as resp:
                return json.load(resp)["data"]
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{path}: HTTP {exc.code}: {exc.read().decode()}") from exc

    lists = api("/api/lists?per_page=all")["results"]
    test_list = next((x for x in lists if x["name"] == "Setup verification"), None)
    if test_list is None:
        test_list = api("/api/lists", {"name": "Setup verification", "type": "private", "optin": "single", "tags": ["setup-test"], "description": "SES simulator recipients only."})
    recipients = ["success@simulator.amazonses.com", "bounce@simulator.amazonses.com", "complaint@simulator.amazonses.com"]
    for address in recipients:
        api("/api/subscribers", {"email": address, "name": "SES setup verification", "status": "enabled", "lists": [test_list["id"]], "preconfirm_subscriptions": True}, "POST")
    campaign = {
        "name": "SES setup verification", "subject": "SES setup verification",
        "from_email": "Creative Attribution <newsletter@creativeattribution.com>",
        "lists": [test_list["id"]], "type": "regular", "content_type": "html",
        "body": '<p>Setup verification using the SES mailbox simulator.</p><p><a href="{{ UnsubscribeURL }}">Unsubscribe</a></p>',
        "messenger": "email", "tags": ["setup-test"], "template_id": 1,
    }
    saved = api("/api/campaigns", campaign)
    api(f'/api/campaigns/{saved["id"]}/test', {**campaign, "subscribers": recipients})
    (base / "secrets/smoke-result.json").write_text(json.dumps({"campaign_id": saved["id"], "list_id": test_list["id"], "recipients": recipients}))
    print(json.dumps({"login": "passed", "campaign_id": saved["id"], "simulator_previews": len(recipients)}))


if __name__ == "__main__":
    main()

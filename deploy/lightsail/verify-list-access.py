"""Integration check: assigned, unassigned, and global list access.

Creates only temporary API users/roles, removes them in finally, sends no mail,
and does not modify existing user permissions or lists.
"""
import base64
import http.cookiejar
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    base = pathlib.Path(__file__).resolve().parent
    url = "https://lists.creativeattribution.com"
    jar = http.cookiejar.CookieJar()
    admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    admin.open(url + "/admin/login", timeout=30).read()
    nonce = next(c.value for c in jar if c.name == "nonce")
    admin.open(url + "/admin/login", data=urllib.parse.urlencode({
        "username": "admin", "password": (base / "secrets/admin_password").read_text().strip(),
        "nonce": nonce,
    }).encode(), timeout=30).read()

    def request(path, data=None, method=None, credentials=None):
        headers = {"Content-Type": "application/json"}
        if credentials:
            headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
        req = urllib.request.Request(url + path, data=None if data is None else json.dumps(data).encode(),
                                     method=method, headers=headers)
        client = urllib.request.build_opener() if credentials else admin
        with client.open(req, timeout=30) as response:
            return json.load(response)["data"]

    lists = request("/api/lists?minimal=true&per_page=all")["results"]
    assert len(lists) >= 2, "Need two existing lists for isolation check"
    allowed, forbidden = lists[0]["id"], lists[-1]["id"]
    stamp = str(time.time_ns())
    users, roles, subscribers = [], [], []
    try:
        scoped = request("/api/roles/users", {"name": "verify-scoped-" + stamp,
                         "permissions": ["subscribers:get", "subscribers:manage"]})
        roles.append(scoped["id"])
        global_role = request("/api/roles/users", {"name": "verify-global-" + stamp,
                              "permissions": ["lists:get_all", "subscribers:manage"]})
        roles.append(global_role["id"])
        assigned = request("/api/roles/lists", {"name": "verify-assigned-" + stamp,
                           "lists": [{"id": allowed, "permissions": ["list:get", "list:manage"]}]})
        roles.append(assigned["id"])
        for label, role_id, list_role_id, expected in [
            ("assigned", scoped["id"], assigned["id"], {allowed}),
            ("none", scoped["id"], None, set()),
            ("global", global_role["id"], assigned["id"], {l["id"] for l in lists}),
        ]:
            user = request("/api/users", {"username": "verify-" + label + "-" + stamp,
                           "name": "Temporary access verification", "type": "api", "status": "enabled",
                           "user_role_id": role_id, "list_role_id": list_role_id})
            users.append(user["id"])
            credentials = user["username"] + ":" + user["password"]
            response = request("/api/lists?minimal=true&per_page=all", credentials=credentials)
            actual = {l["id"] for l in response.get("results", [])} if isinstance(response, dict) else set()
            assert actual == expected, (label, actual, expected)
            # Read visibility does not authorize changing subscriptions. Preconfirm
            # avoids opt-in mail, and all recipients are synthetic reserved addresses.
            for list_id, should_allow in [(allowed, label in ("assigned", "global")),
                                          (forbidden, False)]:
                try:
                    sub = request("/api/subscribers", {
                        "email": f"verify-{label}-{list_id}-{stamp}@example.invalid",
                        "name": "Temporary subscriber permission verification", "status": "enabled",
                        "attribs": {}, "lists": [list_id], "preconfirm_subscriptions": True,
                    }, credentials=credentials)
                    subscribers.append(sub["id"])
                except urllib.error.HTTPError as exc:
                    assert not should_allow and exc.code == 403, (label, list_id, exc.code)
                else:
                    assert should_allow, (label, "Unauthorized subscriber creation succeeded", list_id)
            if label == "assigned":
                for method in ("GET", "PUT"):
                    try:
                        request(f"/api/lists/{forbidden}", data={"name": "Denied verification"} if method == "PUT" else None,
                                method=method, credentials=credentials)
                    except urllib.error.HTTPError as exc:
                        assert exc.code == 403, (method, exc.code)
                    else:
                        raise AssertionError("Unassigned list access was permitted")
            print(json.dumps({"access": label, "visible_lists": len(actual), "check": "passed"}))
    finally:
        for subscriber_id in reversed(subscribers):
            request(f"/api/subscribers/{subscriber_id}", method="DELETE")
        for user_id in reversed(users):
            request(f"/api/users/{user_id}", method="DELETE")
        for role_id in reversed(roles):
            request(f"/api/roles/{role_id}", method="DELETE")
        print("Temporary verification users and roles removed.")


if __name__ == "__main__":
    main()

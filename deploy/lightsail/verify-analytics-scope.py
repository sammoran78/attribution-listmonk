"""Check analytics isolation using rolled-back SQL fixtures and temporary API users.

Run on the existing VM. Never sends mail or changes production campaign,
subscriber, list or analytics records. SQL fixtures use temporary tables only.
"""
import argparse
import base64
import datetime
import http.cookiejar
import json
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent
ROOT = BASE.parent.parent


def queries(file):
    body = file.read_text()
    markers = list(re.finditer(r"^-- name: (\S+)\s*$", body, re.M))
    return {m[1]: body[m.end():markers[i + 1].start() if i + 1 < len(markers) else len(body)].strip()
            for i, m in enumerate(markers)}


def psql(script):
    return subprocess.run(['docker', 'compose', 'exec', '-T', 'db', 'psql', '-U', 'listmonk',
                           '-d', 'listmonk', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'],
                          cwd=BASE, input=script, text=True, capture_output=True, check=True).stdout


def verify_sql():
    misc = queries(ROOT / 'queries/misc.sql')
    camp = queries(ROOT / 'queries/campaigns.sql')
    seed = """
BEGIN;
CREATE TEMP TABLE lists (id INT, type TEXT, optin TEXT);
CREATE TEMP TABLE subscribers (id INT, status TEXT);
CREATE TEMP TABLE subscriber_lists (subscriber_id INT, list_id INT);
CREATE TEMP TABLE campaigns (id INT, status TEXT, sent INT);
CREATE TEMP TABLE campaign_lists (campaign_id INT, list_id INT);
CREATE TEMP TABLE campaign_views (id INT, campaign_id INT, subscriber_id INT, created_at TIMESTAMP);
CREATE TEMP TABLE link_clicks (id INT, campaign_id INT, subscriber_id INT, link_id INT, created_at TIMESTAMP);
CREATE TEMP TABLE links (id INT, url TEXT);
CREATE TEMP TABLE bounces (id INT, campaign_id INT, subscriber_id INT, created_at TIMESTAMP);
INSERT INTO lists VALUES (1,'public','single'),(2,'private','double'),(3,'public','double');
INSERT INTO subscribers VALUES (1,'enabled'),(2,'blocklisted'),(3,'blocklisted'),(4,'enabled'),(5,'enabled');
INSERT INTO subscriber_lists VALUES (1,1),(2,2),(3,1),(3,2),(5,1),(5,3);
INSERT INTO campaigns VALUES (10,'finished',11),(20,'finished',90),(30,'draft',5),(40,'finished',2),(50,'finished',4);
INSERT INTO campaign_lists VALUES (10,1),(20,2),(30,1),(30,2),(50,NULL);
INSERT INTO campaign_views VALUES
 (1,10,1,'2026-08-15'),(2,10,1,'2026-08-15'),(3,30,3,'2026-08-16'),
 (4,20,2,'2026-10-02'),(5,20,2,'2026-10-02'),(6,40,4,'2026-10-03');
INSERT INTO links VALUES (1,'https://allowed.invalid/reading'),(2,'https://forbidden.invalid/reading');
INSERT INTO link_clicks VALUES
 (1,10,1,1,'2026-08-15'),(2,10,1,1,'2026-08-15'),(3,30,3,1,'2026-08-16'),
 (4,20,2,2,'2026-10-02'),(5,20,2,2,'2026-10-02'),(6,40,4,2,'2026-10-03');
INSERT INTO bounces VALUES (1,10,1,'2026-08-15'),(2,30,3,'2026-08-16'),(3,20,2,'2026-10-02'),(4,40,4,'2026-10-03');
"""
    statements = [seed]
    cases = [('{1}', 1, 3, 2, 16, 3), ('{1,3}', 2, 3, 2, 16, 3),
             ('{1,2}', 2, 4, 3, 106, 2), ('{}', 0, 0, 0, 0, 0)]
    for i, (ids, *_expected) in enumerate(cases):
        for kind in ('counts', 'charts'):
            statements.append(f"PREPARE {kind}{i}(int[]) AS {misc['get-scoped-dashboard-' + kind]}")
            statements.append(f"EXECUTE {kind}{i}('{ids}');")
    analytics = [
        ('raw_views', camp['get-campaign-analytics-counts'].replace('%s', 'campaign_views'), 3),
        ('unique_views', camp['get-campaign-analytics-unique-counts'].replace('%s', 'campaign_views'), 2),
        ('raw_clicks', camp['get-campaign-analytics-counts'].replace('%s', 'link_clicks'), 3),
        ('unique_clicks', camp['get-campaign-analytics-unique-counts'].replace('%s', 'link_clicks'), 2),
        ('bounces', camp['get-campaign-bounce-counts'], 2),
        ('raw_links', camp['get-campaign-link-counts'].replace('%s', '*'), 3),
        ('unique_links', camp['get-campaign-link-counts'].replace('%s', 'DISTINCT subscriber_id'), 2),
    ]
    for name, query, _ in analytics:
        # JSON wrap makes result comparisons independent of psql formatting.
        query = query.strip().rstrip(';')
        statements.append(f"PREPARE {name}(int[],timestamp,timestamp,boolean,int[]) AS SELECT COALESCE(JSON_AGG(r),'[]') FROM ({query}) r;")
        for all_lists, ids in ((False, '{1}'), (False, '{}'), (True, '{}')):
            statements.append(f"EXECUTE {name}('{{10,20,30,40,50}}','2026-01-01','2026-12-31',{str(all_lists).lower()},'{ids}');")
    statements.append('ROLLBACK;')
    # PostgreSQL's JSON_BUILD_OBJECT can put formatting newlines inside an
    # otherwise single JSON value. Decode consecutive values, not output lines.
    output = psql('\n'.join(statements))
    decoder = json.JSONDecoder()
    rows = []
    while output.strip():
        value, end = decoder.raw_decode(output.lstrip())
        rows.append(value)
        output = output.lstrip()[end:]
    for i, (ids, lists, subs, campaigns, messages, points) in enumerate(cases):
        counts, charts = rows[i * 2:i * 2 + 2]
        assert counts['lists']['total'] == lists, (ids, counts)
        assert counts['subscribers']['total'] == subs and counts['subscribers']['orphans'] == 0
        assert counts['campaigns']['total'] == campaigns and counts['messages'] == messages
        assert sum(p['count'] for p in charts['campaign_views']) == points, (ids, charts)
        assert sum(p['count'] for p in charts['link_clicks']) == points, (ids, charts)
        if ids == '{1}':
            assert counts['subscribers']['blocklisted'] == 1
            assert counts['lists']['private'] == 0
            assert counts['campaigns']['by_status'] == {'finished': 1, 'draft': 1}
            assert charts['campaign_views'][-1]['date'] == '2026-08-16', 'Forbidden dates affected scoped window'
        if ids == '{}':
            assert counts['campaigns']['by_status'] == {} and charts == {'link_clicks': [], 'campaign_views': []}
    start = len(cases) * 2
    for i, (name, _, total) in enumerate(analytics):
        allowed, empty, all_rows = rows[start + i * 3:start + i * 3 + 3]
        assert sum(x['count'] for x in allowed) == total, (name, allowed)
        assert empty == [], (name, 'Empty permissions leaked data')
        assert sum(x['count'] for x in all_rows) > total, (name, 'Global access broken')
        if 'links' in name:
            assert {x['url'] for x in allowed} == {'https://allowed.invalid/reading'}
        else:
            assert {x['campaign_id'] for x in allowed} == {10, 30}
    print('SQL checks passed: overlapping memberships, shared campaigns, empty scope, scoped dates, raw/unique views, clicks, bounces and link URLs. Fixtures rolled back.')


def verify_api():
    url = 'https://lists.creativeattribution.com'
    jar = http.cookiejar.CookieJar()
    admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    admin.open(url + '/admin/login', timeout=30).read()
    nonce = next(c.value for c in jar if c.name == 'nonce')
    admin.open(url + '/admin/login', data=urllib.parse.urlencode({
        'username': 'admin', 'password': (BASE / 'secrets/admin_password').read_text().strip(), 'nonce': nonce,
    }).encode(), timeout=30).read()

    def request(path, data=None, method=None, credentials=None):
        headers = {'Content-Type': 'application/json'}
        if credentials:
            headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
        req = urllib.request.Request(url + path, data=None if data is None else json.dumps(data).encode(),
                                     method=method, headers=headers)
        with (urllib.request.build_opener() if credentials else admin).open(req, timeout=30) as response:
            return json.load(response)['data']

    campaigns = request('/api/campaigns?per_page=all')['results']
    subscribers = request('/api/subscribers?per_page=all')['results']
    lists = request('/api/lists?minimal=true&per_page=all')['results']
    user_roles = request('/api/roles/users')
    list_roles = request('/api/roles/lists')
    base_role = next(r for r in user_roles if r['id'] == 3)
    profiles = [(r['name'], r['id'], {l['id'] for l in r['lists'] if {'list:get', 'list:manage'} & set(l['permissions'])}, 3, False)
                for r in list_roles]
    profiles.append(('No assigned lists', None, set(), 3, False))
    users, roles = [], []
    psql('REFRESH MATERIALIZED VIEW mat_dashboard_counts; REFRESH MATERIALIZED VIEW mat_dashboard_charts;')
    try:
        for label, extras, all_lists in (
            ('Global campaign/subscriber permissions with assigned lists', ['campaigns:get_all', 'subscribers:get_all'], False),
            ('All-list access', ['lists:get_all'], True),
        ):
            role = request('/api/roles/users', {'name': 'Temporary analytics scope ' + str(time.time_ns()),
                                               'permissions': sorted(set(base_role['permissions']) | set(extras))})
            roles.append(role['id'])
            lr = next(r for r in list_roles if r['id'] == 12)
            ids = {l['id'] for l in lr['lists'] if {'list:get', 'list:manage'} & set(l['permissions'])}
            profiles.append((label, lr['id'], ids, role['id'], all_lists))
        # Leave dates broad enough to include setup and subsequent real campaigns.
        to = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        dates = '&from=2026-01-01&to=' + to
        for label, lr_id, permitted, ur_id, all_lists in profiles:
            user = request('/api/users', {'username': 'verify-analytics-' + str(time.time_ns()),
                           'name': 'Temporary analytics isolation verification', 'type': 'api',
                           'status': 'enabled', 'user_role_id': ur_id, 'list_role_id': lr_id})
            users.append(user['id'])
            credentials = user['username'] + ':' + user['password']
            allowed = {l['id'] for l in lists} if all_lists else permitted
            allowed_camps = {c['id'] for c in campaigns if all_lists or any(l['id'] in allowed for l in c['lists'])}
            allowed_subs = {s['id'] for s in subscribers if all_lists or any(l['id'] in allowed for l in s['lists'])}
            counts = request('/api/dashboard/counts', credentials=credentials)
            assert counts['lists']['total'] == len(allowed), (label, 'Lists count leaked')
            assert counts['subscribers']['total'] == len(allowed_subs), (label, 'Subscriber count leaked')
            assert counts['campaigns']['total'] == len(allowed_camps), (label, 'Campaign count leaked')
            assert (counts['messages'] or 0) == sum(c['sent'] for c in campaigns if c['id'] in allowed_camps)
            if not all_lists:
                assert counts['subscribers']['orphans'] == 0
            charts = request('/api/dashboard/charts', credentials=credentials)
            for name, table in [('campaign_views', 'campaign_views'), ('link_clicks', 'link_clicks')]:
                ids = ','.join(map(str, allowed_camps)) or 'NULL'
                expected = int(psql(f"SELECT count(*) FROM {table} WHERE campaign_id IN ({ids}) AND created_at >= (SELECT created_at::DATE - INTERVAL '30 DAY' FROM {table} WHERE campaign_id IN ({ids}) ORDER BY id DESC LIMIT 1) AND created_at < (SELECT created_at::DATE + INTERVAL '1 DAY' FROM {table} WHERE campaign_id IN ({ids}) ORDER BY id DESC LIMIT 1);"))
                assert sum(x['count'] for x in charts[name]) == expected, (label, name, 'Chart leaked')
            for typ in ('views', 'clicks', 'bounces', 'links'):
                for c in campaigns:
                    path = f'/api/campaigns/analytics/{typ}?id={c["id"]}' + dates
                    if c['id'] in allowed_camps:
                        actual = request(path, credentials=credentials)
                        assert actual == request(path), (label, typ, c['id'], 'Accessible campaign analytics changed')
                    else:
                        try:
                            request(path, credentials=credentials)
                        except urllib.error.HTTPError as exc:
                            assert exc.code == 403, (label, typ, c['id'], exc.code)
                        else:
                            raise AssertionError((label, typ, c['id'], 'Forbidden campaign analytics leaked'))
                if allowed_camps and allowed_camps != {c['id'] for c in campaigns}:
                    mixed = urllib.parse.urlencode([('id', c['id']) for c in campaigns])
                    try:
                        request(f'/api/campaigns/analytics/{typ}?' + mixed + dates, credentials=credentials)
                    except urllib.error.HTTPError as exc:
                        assert exc.code == 403, (label, 'Mixed request must be denied')
                    else:
                        raise AssertionError((label, typ, 'Mixed campaign request leaked'))
            print(json.dumps({'profile': label, 'lists': sorted(allowed), 'dashboard': counts, 'analytics_checks': 'passed'}))
    finally:
        for user_id in reversed(users):
            request(f'/api/users/{user_id}', method='DELETE')
        for role_id in reversed(roles):
            request(f'/api/roles/{role_id}', method='DELETE')
        print('Temporary API users and roles removed; no emails sent or real records changed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('--api', action='store_true')
    args = parser.parse_args()
    if args.sql or not args.api:
        verify_sql()
    if args.api or not args.sql:
        verify_api()


if __name__ == '__main__':
    main()

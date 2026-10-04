"""Scope the existing List Administrator role and verify live result isolation.

No campaign sends or subscriber changes. Only temporary API test users are
created, and removed in finally. Back up the original role before narrowing it.
"""
import argparse
import base64
import http.cookiejar
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    base = pathlib.Path(__file__).resolve().parent
    url = 'https://lists.creativeattribution.com'
    jar = http.cookiejar.CookieJar()
    admin = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    admin.open(url + '/admin/login', timeout=30).read()
    nonce = next(c.value for c in jar if c.name == 'nonce')
    admin.open(url + '/admin/login', data=urllib.parse.urlencode({
        'username': 'admin', 'password': (base / 'secrets/admin_password').read_text().strip(),
        'nonce': nonce,
    }).encode(), timeout=30).read()

    def request(path, data=None, method=None, credentials=None):
        headers = {'Content-Type': 'application/json'}
        if credentials:
            headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
        req = urllib.request.Request(url + path, data=None if data is None else json.dumps(data).encode(),
                                     method=method, headers=headers)
        client = urllib.request.build_opener() if credentials else admin
        with client.open(req, timeout=30) as response:
            return json.load(response)['data']

    roles = request('/api/roles/users')
    role = next(r for r in roles if r['id'] == 3)
    assert role['name'] == 'List Administrator', 'Role identity changed; inspect before applying'
    assert not {'lists:get_all', 'lists:manage_all'} & set(role['permissions']), 'Role has global list scope'
    bypass = {'subscribers:get_all', 'campaigns:get_all', 'campaigns:manage_all'}
    removed = sorted(bypass & set(role['permissions']))
    print(json.dumps({'role': role['name'], 'remove_global_overrides': removed, 'apply': args.apply}))
    if not args.apply:
        return
    if removed:
        backup = base / 'secrets/role-3-before-result-scope-20261003.json'
        if not backup.exists():
            backup.write_text(json.dumps(role, indent=2) + '\n')
            backup.chmod(0o600)
        request('/api/roles/users/3', {'name': role['name'],
                'permissions': [p for p in role['permissions'] if p not in bypass]}, 'PUT')

    updated = next(r for r in request('/api/roles/users') if r['id'] == 3)
    assert set(updated['permissions']) == set(role['permissions']) - bypass
    campaigns = request('/api/campaigns?per_page=all')['results']
    subscribers = request('/api/subscribers?per_page=all')['results']
    all_lists = request('/api/lists?minimal=true&per_page=all')['results']
    list_roles = request('/api/roles/lists')
    profiles = [(r['name'], r['id'], {l['id'] for l in r['lists']
                 if {'list:get', 'list:manage'} & set(l['permissions'])}) for r in list_roles]
    profiles.append(('No assigned lists', None, set()))
    fixtures = []
    try:
        for label, list_role_id, allowed in profiles:
            user = request('/api/users', {'username': 'verify-result-scope-' + str(time.time_ns()),
                           'name': 'Temporary result isolation verification', 'type': 'api',
                           'status': 'enabled', 'user_role_id': 3, 'list_role_id': list_role_id})
            fixtures.append(user['id'])
            credentials = user['username'] + ':' + user['password']
            counts = {}
            for kind, reference in [('campaigns', campaigns), ('subscribers', subscribers)]:
                expected = {r['id'] for r in reference if any(l['id'] in allowed for l in r['lists'])}
                # The existing subscriber SQL join returns one row per matching
                # membership; verify its count is scoped as well as its records.
                expected_rows = (sum(sum(l['id'] in allowed for l in r['lists']) for r in reference)
                                 if kind == 'subscribers' else len(expected))
                found = request(f'/api/{kind}?per_page=all', credentials=credentials)
                actual = {r['id'] for r in found['results'] or []}
                assert actual == expected, (label, kind, actual, expected)
                assert found.get('total', 0) == expected_rows, (label, kind, 'pagination count')
                # Searching and direct URLs must respect the same boundary.
                searched = request(f'/api/{kind}?per_page=all&' + ('search' if kind == 'subscribers' else 'query')
                                   + '=Sam', credentials=credentials)
                assert {r['id'] for r in searched['results'] or []} <= expected, (label, kind, 'search leaked')
                for item in reference:
                    if item['id'] in expected:
                        request(f'/api/{kind}/{item["id"]}', credentials=credentials)
                    else:
                        try:
                            request(f'/api/{kind}/{item["id"]}', credentials=credentials)
                        except urllib.error.HTTPError as exc:
                            assert exc.code == 403, (label, kind, item['id'], exc.code)
                        else:
                            raise AssertionError((label, kind, 'unassigned direct URL permitted', item['id']))
                if kind == 'subscribers':
                    # An explicit unassigned-list query must never expose its subscribers.
                    for forbidden in {l['id'] for l in all_lists} - allowed:
                        filtered = request(f'/api/subscribers?per_page=all&list_id={forbidden}', credentials=credentials)
                        assert {r['id'] for r in filtered['results'] or []} <= expected, (label, 'list filter leaked')
                counts[kind] = len(actual)
            print(json.dumps({'profile': label, 'allowed_lists': sorted(allowed), 'visible': counts,
                              'search_and_direct_url_checks': 'passed'}))
    finally:
        for user_id in reversed(fixtures):
            request(f'/api/users/{user_id}', method='DELETE')
        print('Temporary API test users removed; no mail sent or subscribers changed.')


if __name__ == '__main__':
    main()

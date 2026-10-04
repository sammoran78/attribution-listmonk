"""Check subscriber creation without sending mail; remove only own fixtures."""
import http.cookiejar
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    base = pathlib.Path(__file__).resolve().parent
    url = 'https://lists.creativeattribution.com'
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    client.open(url + '/admin/login', timeout=30).read()
    nonce = next(c.value for c in jar if c.name == 'nonce')
    client.open(url + '/admin/login', data=urllib.parse.urlencode({
        'username': 'admin', 'password': (base / 'secrets/admin_password').read_text().strip(),
        'nonce': nonce,
    }).encode(), timeout=30).read()

    def request(path, data=None, method=None):
        req = urllib.request.Request(url + path, data=None if data is None else json.dumps(data).encode(),
                                     method=method, headers={'Content-Type': 'application/json'})
        with client.open(req, timeout=30) as response:
            return json.load(response)['data']

    profile = request('/api/profile')
    print(json.dumps({'user': profile['username'], 'role': profile['user_role']['name'],
                      'list_permissions': [p for p in profile['user_role']['permissions'] if p.startswith('lists:')]}))
    lists = request('/api/lists?minimal=true&per_page=all')['results']
    selected = [l['id'] for l in lists if l['id'] in (4, 5, 6)]
    assert len(selected) == 3, 'Expected the three lists from the reported form'
    created = None
    try:
        created = request('/api/subscribers', {'email': 'verify-subscriber-' + str(time.time_ns()) + '@example.invalid',
                          'name': 'Temporary subscriber save verification', 'status': 'enabled', 'attribs': {},
                          'lists': selected, 'preconfirm_subscriptions': True})
        saved = request('/api/subscribers/' + str(created['id']))
        assert {l['id'] for l in saved['lists']} == set(selected), 'Lists were lost while saving'
        print(json.dumps({'create': 'passed', 'selected_lists': len(saved['lists']), 'mail_sent': False}))
    except urllib.error.HTTPError as exc:
        print(json.dumps({'create_http_status': exc.code, 'error': exc.read().decode()}))
        raise
    finally:
        if created:
            request('/api/subscribers/' + str(created['id']), method='DELETE')
            print('Temporary subscriber removed.')


if __name__ == '__main__':
    main()

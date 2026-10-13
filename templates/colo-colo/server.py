"""Small authenticated client for template and draft setup; never sends mail."""
import http.cookiejar
import json
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = pathlib.Path(__file__).resolve().parent
URL = 'https://lists.creativeattribution.com'

class Server:
    def __init__(self):
        jar = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self.client.open(URL + '/admin/login', timeout=30).read()
        nonce = next(x.value for x in jar if x.name == 'nonce')
        self.client.open(URL + '/admin/login', data=urllib.parse.urlencode({
            'username': 'admin', 'nonce': nonce,
            'password': (ROOT / 'deploy/lightsail/secrets/admin_password').read_text().strip(),
        }).encode(), timeout=30).read()

    def request(self, path, data=None, method=None, raw=False):
        assert path.startswith(('/api/templates', '/api/campaigns', '/api/lists', '/api/media'))
        assert not any(x in path for x in ['/status', '/test', '/running'])
        req = urllib.request.Request(URL + path, data=None if data is None else json.dumps(data).encode(),
                                     method=method, headers={'Content-Type': 'application/json'})
        with self.client.open(req, timeout=40) as r:
            result = r.read().decode()
        return result if raw else json.loads(result)['data']

if __name__ == '__main__':
    server = Server()
    for endpoint in ['/api/lists?per_page=all', '/api/templates', '/api/media?per_page=all']:
        data = server.request(endpoint)
        rows = data.get('results', []) if isinstance(data, dict) else data
        print(endpoint, json.dumps([{k:x[k] for k in ['id','name','type','url','filename','is_default'] if k in x} for x in rows]))
    for name, url in [('home', 'https://www.colocolosydney.com'),
                      ('pages', 'https://colocolosydney.com/wp-json/wp/v2/pages?per_page=100'),
                      ('media', 'https://colocolosydney.com/wp-json/wp/v2/media?per_page=100')]:
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = r.read().decode()
            (BASE / ('source-' + name + ('.html' if name == 'home' else '.json'))).write_text(data, encoding='utf-8')
            print(name, 'saved', len(data), 'characters')
        except Exception as e:
            print(name, type(e).__name__, str(e))

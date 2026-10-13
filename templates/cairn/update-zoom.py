"""Audit/update CAIRN references to the replaced Zoom meeting without email."""
import argparse
import copy
import datetime
import hashlib
import http.cookiejar
import json
import re
import runpy
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path('/opt/listmonk/templates/cairn')
DEPLOY = Path('/opt/listmonk/deploy/lightsail')
UPLOADS = Path('/var/lib/docker/volumes/attribution-listmonk_uploads/_data')
URL = 'https://lists.creativeattribution.com'
OLD_URL = 'https://macquarie.zoom.us/j/88625432585'
NEW_URL = 'https://macquarie.zoom.us/j/83101513504'
OLD_ID = '886 2543 2585'
NEW_ID = '831 0151 3504'
AUDIT = Path('/tmp/cairn-zoom-audit.json')


def replace(value):
    if isinstance(value, str):
        return value.replace(OLD_URL, NEW_URL).replace(OLD_ID, NEW_ID)
    if isinstance(value, list):
        return [replace(x) for x in value]
    if isinstance(value, dict):
        return {k: v if k == 'uid' else replace(v) for k, v in value.items()}
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    client.open(URL + '/admin/login', timeout=30).read()
    nonce = next(c.value for c in jar if c.name == 'nonce')
    client.open(URL + '/admin/login', data=urllib.parse.urlencode({
        'username': 'admin', 'password': (DEPLOY / 'secrets/admin_password').read_text().strip(),
        'nonce': nonce,
    }).encode(), timeout=30).read()

    def api(path, data=None, method=None, raw=False, content_type='application/json'):
        if data is not None and not isinstance(data, bytes):
            data = json.dumps(data).encode()
        req = urllib.request.Request(URL + path, method=method, data=data,
                                     headers={'Content-Type': content_type})
        with client.open(req, timeout=40) as response:
            body = response.read()
        return body.decode() if raw else json.loads(body)['data']

    campaigns = [api('/api/campaigns/' + str(c['id']))
                 for c in api('/api/campaigns?per_page=all')['results']]
    targets = [c for c in campaigns if 'cairn' in c['attribs'] and any(
        replace(c.get(k)) != c.get(k) for k in ('attribs', 'body', 'body_source', 'altbody'))]
    templates = [t for t in api('/api/templates') if replace(t['body']) != t['body']]
    files = {}
    for file in UPLOADS.glob('*.ics'):
        raw = file.read_bytes()
        text = raw.decode('utf-8-sig').replace('\r\n ', '').replace('\r\n\t', '')
        if replace(text) != text:
            files[file.name] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                'uid': re.search(r'^UID:(.+)$', text, re.MULTILINE).group(1).strip()}
    report = {'campaigns': [{'id': c['id'], 'name': c['name'], 'status': c['status'],
                'hash': digest(c), 'event': c['attribs']['cairn']} for c in targets],
              'templates': [{'id': t['id'], 'name': t['name'], 'hash': digest(t)} for t in templates],
              'calendar_files': files}
    if not args.apply:
        AUDIT.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return
    assert json.loads(AUDIT.read_text()) == report, 'Live records changed since audit'
    assert any(c['id'] == 3 for c in targets), 'Expected the named draft to require updating'
    assert all(c['status'] == 'draft' and c['sent'] == 0 for c in targets), 'Review non-draft campaigns before updating'
    assert all('CAIRN' in t['name'] for t in templates), 'Review unrelated templates first'
    originals = {name: (UPLOADS / name).read_bytes() for name in files}
    backup = DEPLOY / 'secrets/cairn-zoom-before-20261009.json'
    assert not backup.exists(), 'Already applied; inspect receipt before retrying'
    backup.write_text(json.dumps({'campaigns': targets, 'templates': templates,
                                 'calendar_files': {k: v.decode() for k, v in originals.items()}}, indent=2))
    backup.chmod(0o600)

    for t in templates:
        request = {k: t[k] for k in ('name', 'type', 'subject', 'body_source')}
        request['body'] = replace(t['body'])
        request['body_source'] = replace(t['body_source'])
        api('/api/templates/' + str(t['id']), request, 'PUT')
    for c in targets:
        request = {k: replace(c[k]) for k in ('attribs', 'body', 'body_source', 'altbody')}
        request.update(lists=[x['id'] for x in c['lists']], media=[x['id'] for x in c['media']])
        api('/api/campaigns/' + str(c['id']), request, 'PUT')
        after = api('/api/campaigns/' + str(c['id']))
        for k in ('name', 'subject', 'from_email', 'lists', 'media', 'archive', 'archive_meta',
                  'tags', 'headers', 'send_at', 'status', 'sent'):
            assert after[k] == c[k], 'Unexpected change: ' + k
        for k in ('attribs', 'body', 'body_source', 'altbody'):
            assert after[k] == replace(c[k]), 'Unexpected edit: ' + k
    fold = runpy.run_path(str(BASE / 'prepare-event.py'))['fold']
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for name, raw in originals.items():
        text = raw.decode().replace('\r\n ', '').replace('\r\n\t', '')
        lines = replace(text).split('\r\n')
        lines = ['DTSTAMP:' + now if line.startswith('DTSTAMP:') else
                 'SEQUENCE:' + str(int(line.split(':', 1)[1]) + 1) if line.startswith('SEQUENCE:') else line
                 for line in lines]
        if not any(line.startswith('SEQUENCE:') for line in lines):
            lines.insert(lines.index('END:VEVENT'), 'SEQUENCE:1')
        updated = '\r\n'.join(fold(line) for line in lines).encode()
        assert max(len(line) for line in updated.split(b'\r\n')) <= 75
        assert ('UID:' + files[name]['uid'] + '\r\n').encode() in updated
        for key in ('DTSTART', 'DTEND', 'SUMMARY'):
            old_line = next(line for line in text.split('\r\n') if line.startswith(key + ':'))
            assert old_line in updated.decode().replace('\r\n ', '')
        (UPLOADS / name).write_bytes(updated)
        with urllib.request.urlopen(URL + '/uploads/' + urllib.parse.quote(name), timeout=30) as response:
            assert response.status == 200 and response.read() == updated
            assert response.headers.get_content_type() == 'text/calendar'
        if (BASE / 'events/2026-10-16' / name).exists():
            (BASE / 'events/2026-10-16' / name).write_bytes(updated)

    previews = {}
    for c in targets:
        preview = api('/api/campaigns/' + str(c['id']) + '/preview', raw=True)
        assert OLD_URL not in preview and OLD_ID not in preview
        assert NEW_URL in preview and NEW_ID in preview
        links = runpy.run_path(str(BASE / 'fix-event-links.py'))['Links']()
        links.feed(preview)
        for prefix, title_key, details_key in [('https://calendar.google.com/', 'text', 'details'),
                                               ('https://outlook.office.com/', 'subject', 'body')]:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(next(u for u in links.urls if u.startswith(prefix))).query)
            assert query['location'] == [NEW_URL] and NEW_URL in query[details_key][0]
            assert query[title_key] == ['CAIRN: Lunchtime Reading Group']
        # Compile/render the alternate text through the preview endpoint, without sending.
        plain = api('/api/campaigns/' + str(c['id']) + '/preview',
                    urllib.parse.urlencode({'content_type': 'plain', 'body': replace(c['altbody'])}).encode(),
                    'POST', raw=True, content_type='application/x-www-form-urlencoded')
        assert OLD_URL not in plain and OLD_ID not in plain and NEW_URL in plain and NEW_ID in plain
        previews[c['id']] = 'passed'
        if c['id'] == 3:
            (BASE / 'draft-links-preview-20261009.html').write_text(preview)
            (BASE / 'draft-plain-preview-20261009.txt').write_text(plain)
    remaining = [c['id'] for c in api('/api/campaigns?per_page=all')['results']
                 if 'cairn' in c['attribs'] and replace(c['attribs']) != c['attribs']]
    assert not remaining
    receipt = {'checks': 'passed', 'campaign_ids': list(previews), 'template_ids': [t['id'] for t in templates],
               'calendar_files': list(files), 'zoom_url': NEW_URL, 'zoom_meeting_id': NEW_ID,
               'dates_titles_uids_preserved': True, 'plain_text_preview': 'passed',
               'emails_sent': False, 'new_aws_resources': False}
    (BASE / 'zoom-update-verified-20261009.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

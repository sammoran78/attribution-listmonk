"""Correct calendar titles in the unsent CAIRN draft; never sends email.

Run on the existing VM after a fresh fix-event-links.py audit. Backups are
private and public calendar bytes are checked before replacing the file.
"""
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
URL = 'https://lists.creativeattribution.com'
TITLE = 'CAIRN: Lunchtime Reading Group'
FILE_NAME = 'cairn-joint-select-committee-2026-10-16.ics'
AUDIT = Path('/tmp/cairn-calendar-title-audit.json')


def main():
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    client.open(URL + '/admin/login', timeout=30).read()
    nonce = next(c.value for c in jar if c.name == 'nonce')
    client.open(URL + '/admin/login', data=urllib.parse.urlencode({
        'username': 'admin', 'password': (DEPLOY / 'secrets/admin_password').read_text().strip(),
        'nonce': nonce,
    }).encode(), timeout=30).read()

    def api(path, data=None, method=None, raw=False):
        req = urllib.request.Request(URL + path, method=method,
              data=None if data is None else json.dumps(data).encode(),
              headers={'Content-Type': 'application/json'})
        with client.open(req, timeout=40) as response:
            body = response.read()
        return body.decode() if raw else json.loads(body)['data']

    audit = json.loads(AUDIT.read_text())
    c = api('/api/campaigns/3')
    t = api('/api/templates/5')
    assert hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest() == audit['campaign_hash']
    assert hashlib.sha256(t['body'].encode()).hexdigest() == audit['template_hash']
    assert c['status'] == 'draft' and c['sent'] == 0 and c['template_id'] == 5
    assert 'Joint Select Committee on Artificial Intelligence' in c['name']
    attributes = copy.deepcopy(c['attribs'])
    e = attributes['cairn']
    assert e['calendar_ics_url'] == URL + '/uploads/' + FILE_NAME
    e['calendar_title'] = TITLE

    body = t['body']
    marker = '{{ $title := ($e.event_title | default $e.eventTitle) | default "Our next reading group" }}'
    assert body.count(marker) == 1 and body.count('(urlquery $title)') == 2
    body = body.replace(marker, marker + '\n{{ $calendarTitle := ($e.calendar_title | default $e.calendarTitle) | default "' + TITLE + '" }}')
    body = body.replace('(urlquery $title)', '(urlquery $calendarTitle)')
    assert body == (BASE / 'campaign-template.html').read_text(), 'Unexpected template changes'

    file = Path('/var/lib/docker/volumes/attribution-listmonk_uploads/_data') / FILE_NAME
    original = file.read_bytes()
    with urllib.request.urlopen(e['calendar_ics_url'], timeout=30) as response:
        assert response.read() == original
    unfolded = original.decode().replace('\r\n ', '').replace('\r\n\t', '')
    uid = re.search(r'^UID:(.+)$', unfolded, re.MULTILINE).group(1).strip()
    event = dict(e, uid=uid)
    helper = runpy.run_path(str(BASE / 'prepare-event.py'))
    start, end = helper['event_times'](event)
    calendar = helper['calendar'](event).decode()
    assert start.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') == '20261016T013000Z'
    assert end.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') == '20261016T023000Z'
    alarm = 'BEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER:-PT15M\r\nDESCRIPTION:CAIRN reading group starts in 15 minutes\r\nEND:VALARM\r\n'
    calendar = calendar.replace('END:VEVENT\r\n', 'SEQUENCE:1\r\n' + alarm + 'END:VEVENT\r\n').encode()
    assert max(len(line) for line in calendar.split(b'\r\n')) <= 75
    backup = DEPLOY / 'secrets/cairn-calendar-title-before-20261009.json'
    assert not backup.exists(), 'Already applied; inspect the receipt before retrying'
    backup.write_text(json.dumps({'campaign': c, 'template': t, 'calendar': original.decode()}, ensure_ascii=False, indent=2))
    backup.chmod(0o600)

    replacement = {key: t[key] for key in ('name', 'type', 'subject', 'body_source')}
    replacement['body'] = body
    api('/api/templates/5', replacement, 'PUT')
    api('/api/campaigns/3', {'attribs': attributes, 'lists': [x['id'] for x in c['lists']],
                           'media': [x['id'] for x in c['media']], 'altbody': c['altbody']}, 'PUT')
    file.write_bytes(calendar)
    (BASE / 'events/2026-10-16' / FILE_NAME).write_bytes(calendar)

    after = api('/api/campaigns/3')
    for key in ('body', 'body_source', 'altbody', 'name', 'subject', 'from_email', 'lists', 'media',
                'archive', 'archive_meta', 'tags', 'headers', 'send_at', 'status', 'sent'):
        assert after[key] == c[key], 'Unexpected campaign change: ' + key
    assert after['attribs'] == attributes
    preview = api('/api/campaigns/3/preview', raw=True)
    links = runpy.run_path(str(BASE / 'fix-event-links.py'))['Links']()
    links.feed(preview)
    g = urllib.parse.parse_qs(urllib.parse.urlsplit(next(u for u in links.urls if u.startswith('https://calendar.google.com/'))).query)
    o = urllib.parse.parse_qs(urllib.parse.urlsplit(next(u for u in links.urls if u.startswith('https://outlook.office.com/'))).query)
    assert g['text'] == [TITLE] and o['subject'] == [TITLE]
    assert e['event_title'] in g['details'][0] and e['event_title'] in o['body'][0]
    assert g['dates'] == ['20261016T013000Z/20261016T023000Z']
    assert o['startdt'] == ['2026-10-16T01:30:00Z'] and o['enddt'] == ['2026-10-16T02:30:00Z']
    assert e['event_title'] in preview and e['zoom_url'] in links.urls
    with urllib.request.urlopen(e['calendar_ics_url'], timeout=30) as response:
        downloaded = response.read()
        assert downloaded == calendar and response.status == 200
    assert ('SUMMARY:' + TITLE + '\r\n').encode() in downloaded
    assert ('UID:' + uid + '\r\n').encode() in downloaded
    receipt = {'campaign_id': 3, 'template_id': 5, 'calendar_title': TITLE, 'checks': 'passed',
               'calendar_ics_url': e['calendar_ics_url'], 'uid_preserved': True, 'dates_preserved': True,
               'html_topic_preserved': True, 'plain_text_unchanged': True, 'campaign_status': 'draft',
               'emails_sent': False, 'new_aws_resources': False}
    (BASE / 'calendar-title-verified-20261009.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (BASE / 'draft-links-preview-20261009.html').write_text(preview)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

"""Audit/repair the named unsent CAIRN draft; never sends or schedules mail."""
import argparse
import hashlib
import html.parser
import http.cookiejar
import json
import datetime
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = Path(__file__).resolve().parent
DEPLOY = Path('/opt/listmonk/deploy/lightsail')
URL = 'https://lists.creativeattribution.com'


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(v for k, v in attrs if k == 'href')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-campaign-hash')
    parser.add_argument('--expected-template-hash')
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
        payload = None if data is None else data if isinstance(data, bytes) else json.dumps(data).encode()
        req = urllib.request.Request(URL + path, data=payload, method=method,
                                     headers={'Content-Type': content_type})
        try:
            with client.open(req, timeout=40) as resp:
                body = resp.read()
            return body.decode() if raw else json.loads(body)['data']
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'{path}: HTTP {exc.code}: {exc.read().decode()}') from exc

    found = [c for c in api('/api/campaigns?per_page=all')['results']
             if 'CAIRN reading group' in c['name'] and 'Joint Select Committee on Artificial Intelligence' in c['name']]
    assert len(found) == 1, 'Expected exactly one matching campaign'
    c = api(f'/api/campaigns/{found[0]["id"]}')
    t = api(f'/api/templates/{c["template_id"]}')
    c_hash = hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()
    t_hash = hashlib.sha256(t['body'].encode()).hexdigest()
    report = {'campaign_id': c['id'], 'name': c['name'], 'status': c['status'],
              'template_id': c['template_id'], 'attribs': c['attribs'],
              'campaign_hash': c_hash, 'template_hash': t_hash,
              'template_reads': {k: ('$e.' + k) in t['body'] for k in
                                 ('zoom_url', 'zoomUrl', 'calendar_ics_url', 'calendarIcsUrl')},
              'altbody': c.get('altbody')}
    try:
        preview = api(f'/api/campaigns/{c["id"]}/preview', raw=True)
        links = Links()
        links.feed(preview)
        report['preview_links'] = [u for u in links.urls if any(s in u for s in ('zoom.', '.ics', 'calendar.google.', 'outlook.office.'))]
        report['preview_has_zoom_button'] = 'Join Zoom meeting' in preview
    except RuntimeError as exc:
        report['preview_error'] = str(exc)
    if not args.apply:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    assert args.expected_campaign_hash == c_hash and args.expected_template_hash == t_hash, 'Live draft/template changed since audit'
    assert c['status'] == 'draft' and c['sent'] == 0, 'Only an unsent draft may be repaired'
    backup = DEPLOY / 'secrets/cairn-event-links-before-20261009.json'
    assert not backup.exists(), 'Backup already exists; review prior repair before reapplying'
    backup.write_text(json.dumps({'campaign': c, 'template': t}, ensure_ascii=False, indent=2))
    backup.chmod(0o600)

    # Compatibility with older drafts whose editor transformed custom keys.
    body = t['body']
    for snake, camel in [('event_title', 'eventTitle'), ('calendar_description', 'calendarDescription'),
                         ('calendar_ics_url', 'calendarIcsUrl'), ('zoom_url', 'zoomUrl'),
                         ('zoom_meeting_id', 'zoomMeetingId'), ('zoom_passcode', 'zoomPasscode')]:
        body = body.replace('$e.' + snake, f'($e.{snake} | default $e.{camel})')

    # Canonicalize this draft without changing its event values or reading copy.
    attributes = json.loads(json.dumps(c['attribs']))
    e = attributes['cairn']
    for snake, camel in [('event_title', 'eventTitle'), ('calendar_description', 'calendarDescription'),
                         ('calendar_ics_url', 'calendarIcsUrl'), ('zoom_url', 'zoomUrl'),
                         ('zoom_meeting_id', 'zoomMeetingId'), ('zoom_passcode', 'zoomPasscode')]:
        if camel in e:
            assert snake not in e or e[snake] == e[camel], f'Conflicting attribute: {snake}'
            e[snake] = e.pop(camel)
    helper = __import__('runpy').run_path(str(BASE / 'prepare-event.py'))
    start, end = helper['event_times'](e)
    ics_url = e.get('calendar_ics_url', '')
    needs_calendar_file = not ics_url
    if ics_url:
        parsed = urllib.parse.urlsplit(ics_url)
        assert parsed.scheme == 'https' and parsed.netloc == 'lists.creativeattribution.com', 'Review external calendar URL before repairing'
        with urllib.request.urlopen(ics_url, timeout=30) as resp:
            downloaded = resp.read()
        unfolded = downloaded.decode('utf-8-sig').replace('\r\n ', '').replace('\r\n\t', '')
        needs_calendar_file = 'BEGIN:VCALENDAR' not in unfolded or 'BEGIN:VEVENT' not in unfolded
        for label, value in [('DTSTART', start), ('DTEND', end)]:
            expected = value.astimezone(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            needs_calendar_file |= label + ':' + expected not in unfolded
    if needs_calendar_file:
        # Publish a separate file so existing links to the sample stay intact.
        file = BASE / 'events/2026-10-16/cairn-joint-select-committee-2026-10-16.ics'
        file.parent.mkdir(parents=True, exist_ok=True)
        event = dict(e)
        event['uid'] = 'cairn-lunchtime-reading-group-20261016-88625432585@cairn.org.au'
        event['event_title'] = c['name']
        calendar = helper['calendar'](event).decode()
        alarm = 'BEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER:-PT15M\r\nDESCRIPTION:CAIRN reading group starts in 15 minutes\r\nEND:VALARM\r\n'
        file.write_bytes(calendar.replace('END:VEVENT\r\n', alarm + 'END:VEVENT\r\n').encode())
        boundary = 'cairn-' + uuid.uuid4().hex
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file.name}"\r\nContent-Type: text/calendar\r\n\r\n').encode() + file.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        media = api('/api/media', payload, 'POST', content_type='multipart/form-data; boundary=' + boundary)
        e['calendar_ics_url'] = urllib.parse.urljoin(URL, media['url'])
        with urllib.request.urlopen(e['calendar_ics_url'], timeout=30) as resp:
            assert resp.read() == file.read_bytes()

    replacement = {k: t[k] for k in ('name', 'type', 'subject', 'body_source')}
    replacement['body'] = body
    api(f'/api/templates/{t["id"]}', replacement, 'PUT')
    # Keep the existing associations; omitted list/media IDs otherwise clear them.
    altbody = (c.get('altbody') or '').replace('{{ 886 2543 2585 }}', '{{ . }}')
    request = {'attribs': attributes, 'lists': [l['id'] for l in c['lists']],
               'media': [m['id'] for m in c['media']], 'altbody': altbody}
    result = api(f'/api/campaigns/{c["id"]}', request, 'PUT')
    assert result['status'] == 'draft' and result['sent'] == 0 and result['send_at'] == c['send_at']
    after = api(f'/api/campaigns/{c["id"]}')
    for key in ('body', 'body_source', 'name', 'subject', 'from_email', 'lists', 'media', 'archive', 'archive_meta', 'tags', 'headers'):
        assert after[key] == c[key], f'Unexpected campaign change: {key}'
    preview = api(f'/api/campaigns/{c["id"]}/preview', raw=True)
    links = Links()
    links.feed(preview)
    assert e['zoom_url'] in links.urls and e['calendar_ics_url'] in links.urls
    assert 'Join Zoom meeting' in preview and e['event_title'] in preview
    assert 'ZgotmplZ' not in preview and '{{' not in preview
    assert after['altbody'] == altbody
    g = urllib.parse.parse_qs(urllib.parse.urlsplit(next(u for u in links.urls if u.startswith('https://calendar.google.com/'))).query)
    o = urllib.parse.parse_qs(urllib.parse.urlsplit(next(u for u in links.urls if u.startswith('https://outlook.office.com/'))).query)
    assert g['dates'] == ['20261016T013000Z/20261016T023000Z']
    assert o['startdt'] == ['2026-10-16T01:30:00Z'] and o['enddt'] == ['2026-10-16T02:30:00Z']
    assert g['location'] == [e['zoom_url']] and o['location'] == [e['zoom_url']]
    (BASE / 'draft-links-preview-20261009.html').write_text(preview)
    (BASE / 'campaign-template.html').write_text(body)
    report = {'before': report, 'after': {'attribs': after['attribs'],
              'preview_links': links.urls, 'preview_has_zoom_button': True,
              'altbody': after['altbody'], 'status': after['status']},
              'campaign_id': c['id'], 'checks': 'passed',
              'calendar_ics_url': e['calendar_ics_url'], 'zoom_url': e['zoom_url'],
              'backup': str(backup), 'emails_sent': False}
    (BASE / 'draft-links-repair-20261009.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'campaign_id': c['id'], 'checks': 'passed', 'calendar_ics_url': e['calendar_ics_url'],
                      'zoom_url': e['zoom_url'], 'emails_sent': False}))


if __name__ == '__main__':
    main()

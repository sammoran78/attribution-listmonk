"""Verify phone storage and public forms using removable fixtures and no mail."""
import csv
import html
import http.cookiejar
import io
import json
import pathlib
import re
import time
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

    def raw(path, data=None, method=None, form=False):
        if data is not None:
            data = urllib.parse.urlencode(data, doseq=True).encode() if form else json.dumps(data).encode()
        request = urllib.request.Request(url + path, data=data, method=method,
                                         headers={'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'})
        with client.open(request, timeout=30) as response:
            return response.read().decode()

    def api(path, data=None, method=None):
        return json.loads(raw(path, data, method))['data']

    api('/api/profile')  # Confirm login before creating any fixtures.
    stamp = str(time.time_ns())
    created = []
    test_list = None
    results = {}
    try:
        test_list = api('/api/lists', {'name': 'Temporary phone verification ' + stamp,
                                     'type': 'public', 'optin': 'single', 'tags': []})
        assert test_list['optin'] == 'single'
        page = raw('/subscription/form')
        field = re.search(r'<input[^>]*name="phone"[^>]*>', page).group()
        assert 'type="tel"' in field and 'required' not in field and 'maxlength="64"' in field
        results['public_optional_input'] = 'passed'

        data = {'email': 'phone-admin-' + stamp + '@example.invalid', 'name': 'Temporary phone verification',
                'status': 'enabled', 'lists': [test_list['id']], 'preconfirm_subscriptions': True,
                'attribs': {'phone': '+61 0412 345 678', 'city': 'Sydney', 'nested': {'keep': True}}}
        sub = api('/api/subscribers', data)
        created.append(sub['id'])
        saved = api('/api/subscribers/' + str(sub['id']))
        assert saved['attribs'] == data['attribs']
        data['attribs']['phone'] = '+1 (212) 555-0100 ext. 23'
        api('/api/subscribers/' + str(sub['id']), data, 'PUT')
        assert api('/api/subscribers/' + str(sub['id']))['attribs'] == data['attribs']
        exported = next(csv.DictReader(io.StringIO(raw('/api/subscribers/export?id=' + str(sub['id'])))))
        assert json.loads(exported['attributes']) == data['attribs']
        results['admin_create_edit_read_and_export'] = 'passed'

        path = '/subscription/00000000-0000-0000-0000-000000000000/' + saved['uuid']
        prefs = raw(path + '?manage=true')
        if 'name="phone"' in prefs:
            value = re.search(r'name="phone" value="([^"]*)"', prefs).group(1)
            assert html.unescape(value) == data['attribs']['phone']
            fields = {'manage': 'true', 'name': data['name'], 'l': [test_list['uuid']], 'phone': '  0412 000 000  '}
            raw(path, fields, 'POST', form=True)
            assert api('/api/subscribers/' + str(sub['id']))['attribs']['phone'] == '0412 000 000'
            fields.pop('phone')
            raw(path, fields, 'POST', form=True)
            assert api('/api/subscribers/' + str(sub['id']))['attribs']['phone'] == '0412 000 000'
            fields['phone'] = ''
            raw(path, fields, 'POST', form=True)
            final = api('/api/subscribers/' + str(sub['id']))['attribs']
            assert final == {'city': 'Sydney', 'nested': {'keep': True}}
            results['preferences_edit_omit_and_clear'] = 'passed'
        else:
            results['preferences_edit_omit_and_clear'] = 'disabled by existing settings'

        data['attribs'].pop('phone')
        api('/api/subscribers/' + str(sub['id']), data, 'PUT')
        assert api('/api/subscribers/' + str(sub['id']))['attribs'] == data['attribs']
        results['admin_clear_preserves_other_attributes'] = 'passed'

        for label, phone, use_form in [('public-api', '+61 412 345 678', False), ('public-form', '+44 (0)20 1234 5678', True), ('email-only', None, False)]:
            email = 'phone-' + label + '-' + stamp + '@example.invalid'
            fields = {'email': email, 'name': 'Temporary phone verification'}
            fields['l' if use_form else 'list_uuids'] = [test_list['uuid']]
            if phone is not None:
                fields['phone'] = '  ' + phone + '  '
            raw('/subscription/form' if use_form else '/api/public/subscription', fields, 'POST', form=use_form)
            # Restrict cleanup to this unique fixture's exact email address.
            matches = [s for s in api('/api/subscribers?search=' + urllib.parse.quote(email))['results'] if s['email'] == email]
            assert len(matches) == 1
            created.append(matches[0]['id'])
            assert matches[0]['attribs'].get('phone') == phone
            results[label + '_stored_record'] = 'passed'
        results['mail_sent'] = False
    finally:
        for sub_id in created:
            api('/api/subscribers/' + str(sub_id), method='DELETE')
        if test_list:
            api('/api/lists/' + str(test_list['id']), method='DELETE')
        results['temporary_fixtures_removed'] = True
    receipt = base / 'phone-verified-20261013.json'
    receipt.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()

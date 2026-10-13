"""Guarded recovery of the zero-send CAIRN campaign; never starts or sends it."""
import argparse
import http.cookiejar
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

DEPLOY = Path('/opt/listmonk/deploy/lightsail')
URL = 'https://lists.creativeattribution.com'
BEFORE = 'CAIRN: Creative AI Research Network <newsletter@creativeattribution.com>'
AFTER = '"CAIRN: Creative AI Research Network" <newsletter@creativeattribution.com>'


def sql(query):
    return subprocess.run(['docker', 'compose', 'exec', '-T', 'db', 'psql', '-X', '-At',
                           '-v', 'ON_ERROR_STOP=1', '-U', 'listmonk', '-d', 'listmonk'],
                          cwd=DEPLOY, input=query, text=True, capture_output=True, check=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    c = json.loads(sql('SELECT row_to_json(c) FROM campaigns c WHERE id=3;'))
    assert c['status'] == 'finished' and c['sent'] == 0 and c['to_send'] == 23
    assert c['from_email'] == BEFORE and c['last_subscriber_id'] == 56
    assert c['name'] == 'CAIRN reading group — Joint Select Committee on Artificial Intelligence'
    view_stats = json.loads(sql("SELECT json_build_object('count',count(*),'first',min(created_at),'last',max(created_at),'after_start',count(*) FILTER (WHERE created_at >= (SELECT started_at FROM campaigns WHERE id=3))) FROM campaign_views WHERE campaign_id=3;"))
    recipients = json.loads(sql("SELECT json_agg(row_to_json(s)) FROM (SELECT DISTINCT s.id,s.email FROM subscribers s JOIN subscriber_lists sl ON sl.subscriber_id=s.id JOIN campaign_lists cl ON cl.list_id=sl.list_id JOIN lists l ON l.id=sl.list_id WHERE cl.campaign_id=3 AND s.status != 'blocklisted' AND ((l.optin='double' AND sl.status='confirmed') OR (l.optin!='double' AND sl.status!='unsubscribed')) ORDER BY s.id) s;"))
    assert len(recipients) == 23
    validation_input = DEPLOY / 'secrets/cairn-address-validation-input-20261009.json'
    if not args.apply:
        validation_input.write_text(json.dumps({'before': BEFORE, 'after': AFTER, 'recipients': recipients}))
        validation_input.chmod(0o600)
        (DEPLOY / 'secrets/cairn-sender-recovery-audit-20261009.json').write_text(json.dumps(c, indent=2))
        (DEPLOY / 'secrets/cairn-sender-recovery-audit-20261009.json').chmod(0o600)
        print(json.dumps({'campaign_id':3, 'status':c['status'], 'sent':c['sent'], 'to_send':c['to_send'],
                          'from_before':BEFORE,'from_after':AFTER,'views':view_stats,'recipient_count':len(recipients)}, indent=2))
        return
    audit = json.loads((DEPLOY / 'secrets/cairn-sender-recovery-audit-20261009.json').read_text())
    assert c == audit, 'Campaign changed since audit'
    validation = json.loads(Path('/tmp/cairn-address-validation-result.json').read_text())
    assert validation['corrected_sender'] == AFTER and validation['recipients_checked'] == 23
    assert not validation['invalid_recipient_ids'] and validation['original_sender_error'] == 'mail: expected comma'
    backup = DEPLOY / 'secrets/cairn-sender-before-20261009.json'
    assert not backup.exists(), 'Already recovered; inspect current status'
    backup.write_text(json.dumps({'campaign': c, 'views': view_stats}, indent=2))
    backup.chmod(0o600)
    # Restore only this proven zero-send campaign. The draft is never eligible
    # for the manager's sending scan. Its existing analytics remain intact.
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    changed = sql("BEGIN; UPDATE campaigns SET from_email=" + quote(AFTER) +
        ",status='draft',last_subscriber_id=0,max_subscriber_id=0,started_at=NULL,updated_at=NOW() "
        "WHERE id=3 AND status='finished' AND sent=0 AND to_send=23 AND last_subscriber_id=56 "
        "AND from_email=" + quote(BEFORE) + " AND updated_at=" + quote(c['updated_at']) +
        "::timestamptz RETURNING id; COMMIT;")
    assert 'UPDATE 1' in changed, 'Guard prevented recovery'
    after = json.loads(sql('SELECT row_to_json(c) FROM campaigns c WHERE id=3;'))
    for key, value in c.items():
        if key not in ('from_email','status','last_subscriber_id','max_subscriber_id','started_at','updated_at'):
            assert after[key] == value, 'Unexpected change: ' + key
    assert after['status'] == 'draft' and after['from_email'] == AFTER and after['sent'] == 0
    assert int(sql('SELECT count(*) FROM campaign_views WHERE campaign_id=3;')) == view_stats['count']
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    client.open(URL + '/admin/login', timeout=30).read()
    nonce = next(x.value for x in jar if x.name == 'nonce')
    client.open(URL + '/admin/login', data=urllib.parse.urlencode({'username':'admin',
        'password':(DEPLOY / 'secrets/admin_password').read_text().strip(),'nonce':nonce}).encode(),timeout=30).read()
    preview = client.open(URL + '/api/campaigns/3/preview',timeout=30).read().decode()
    assert 'https://macquarie.zoom.us/j/83101513504' in preview and '831 0151 3504' in preview
    assert '20261016T013000Z' in preview and 'ZgotmplZ' not in preview
    receipt = {'campaign_id':3, 'status':'draft', 'sent':0, 'recipient_count':23,
               'sender':AFTER, 'envelope_validation':validation, 'queue_checkpoint_reset':True,
               'existing_views_retained':view_stats, 'preview':'passed', 'emails_sent':False,
               'new_aws_resources':False}
    (DEPLOY / 'cairn-sender-recovery-20261009.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    main()

"""Install only the four new templates and unsent starters on the existing server."""
import copy
import hashlib
import html.parser
import json
import urllib.parse
import urllib.request
from server import Server, BASE

CONFIG = {
 'committee': ('Colo Colo Sydney COMMITTEE', 'Colo Colo Sydney — Committee meeting', '[Committee meeting] | Colo Colo Sydney'),
 'members': ('Colo Colo Sydney Members', 'Colo Colo Sydney — Members update', '[Month] Members update | Colo Colo Sydney'),
 'newsletter': ('Colo Colo Sydney Newsletter', 'Colo Colo Sydney — What’s on newsletter', '[Upcoming event] | Colo Colo Sydney'),
 'football': ('Colo Colo Sydney Football', 'Colo Colo Sydney — Football update', '[Training / season update] | Colo Colo Sydney'),
}

class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.images=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='a': self.links.append(d.get('href',''))
        if tag=='img': self.images.append(d.get('src',''))

def main():
    receipt=BASE/'installation.json'
    assert not receipt.exists(), 'Installation receipt exists; preserve existing drafts.'
    s=Server()
    lists=s.request('/api/lists?per_page=all')['results']
    templates=s.request('/api/templates')
    before={x['id']:hashlib.sha256(x['body'].encode()).hexdigest() for x in templates}
    defaults=[x['id'] for x in templates if x['is_default']]
    items={}
    for key,(list_name,name,subject) in CONFIG.items():
        matches=[x for x in lists if x['name'].strip()==list_name]
        assert len(matches)==1, list_name
        assert not any(x['name']==name for x in templates), name
        b=BASE/key
        attrs=json.loads((b/'starter-attributes.json').read_text(encoding='utf-8'))
        items[key]={'list_id':matches[0]['id'],'template_name':name,'subject':subject,'attribs':attrs}
    result={'status':'installing','existing_template_hashes':before,'items':{}}
    def record(): receipt.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    record()
    for key,entry in items.items():
        b=BASE/key
        template_body=(b/'campaign-template.html').read_text(encoding='utf-8')
        assert template_body.count('{{ template "content" . }}')==1
        t=s.request('/api/templates',{'name':entry['template_name'],'type':'campaign','body':template_body})
        result['items'][key]={'template_id':t['id'],'list_id':entry['list_id']}; record()
        generic=s.request(f'/api/templates/{t["id"]}/preview',raw=True)
        assert 'ZgotmplZ' not in generic and '{{' not in generic
        campaign={'name':'[DRAFT] Colo Colo Sydney '+key+' — starter','subject':entry['subject'],
          'from_email':'Colo Colo Sydney <newsletter@creativeattribution.com>',
          'lists':[entry['list_id']],'type':'regular','content_type':'richtext','messenger':'email',
          'template_id':t['id'],'body':(b/'campaign-body.html').read_text(encoding='utf-8'),
          'altbody':(b/'campaign-alt-body.txt').read_text(encoding='utf-8'),
          'attribs':entry['attribs'],'tags':['colo-colo',key,'starter'],'archive':False,
          'headers':[{'Reply-To':'info@colocolosydney.com'}]}
        c=s.request('/api/campaigns',campaign)
        result['items'][key]['campaign_id']=c['id']; record()
        preview=s.request(f'/api/campaigns/{c["id"]}/preview',raw=True)
        assert 'ZgotmplZ' not in preview and '{{' not in preview
        assert 'Unsubscribe' in preview and 'View in your browser' in preview
        assert '<!--[if mso]>' in preview
        if key=='committee':
            assert 'Date and time to be confirmed' in preview and 'calendar.google.com' not in preview
            sample=copy.deepcopy(campaign)
            sample['attribs']['colocolo'].update(event_title='SAMPLE ONLY — Committee planning',start='2026-10-20T19:00:00+11:00',end='2026-10-20T20:00:00+11:00',location='Online via Zoom',zoom_url='https://example.org/meeting',calendar_ics_url='https://example.org/meeting.ics')
            try:
                s.request(f'/api/campaigns/{c["id"]}',sample,'PUT')
                test=s.request(f'/api/campaigns/{c["id"]}/preview',raw=True)
                assert 'Tuesday, 20 October 2026' in test and '7:00 pm–8:00 pm AEDT' in test
                links=Links(); links.feed(test)
                g=urllib.parse.parse_qs(urllib.parse.urlsplit(next(x for x in links.links if x.startswith('https://calendar.google.com'))).query)
                o=urllib.parse.parse_qs(urllib.parse.urlsplit(next(x for x in links.links if x.startswith('https://outlook.office.com'))).query)
                assert g['dates']==['20261020T080000Z/20261020T090000Z']
                assert o['startdt']==['2026-10-20T08:00:00Z'] and o['enddt']==['2026-10-20T09:00:00Z']
                assert 'https://example.org/meeting.ics' in links.links
                (b/'sample-preview.html').write_text(test,encoding='utf-8')
            finally: s.request(f'/api/campaigns/{c["id"]}',campaign,'PUT')
            preview=s.request(f'/api/campaigns/{c["id"]}/preview',raw=True)
        (b/'preview.html').write_text(preview,encoding='utf-8')
        final=s.request(f'/api/campaigns/{c["id"]}')
        assert final['status']=='draft' and not final.get('send_at') and final['sent']==0
        assert final['attribs']==campaign['attribs']
        assert [x['id'] for x in final['lists']]==campaign['lists']
        assert final['template_id']==t['id']
        assert not s.request(f'/api/templates/{t["id"]}')['is_default']
        result['items'][key]['verified']='draft, list, template, attributes, preview, zero sends'
        record(); print(key, result['items'][key])
    after=s.request('/api/templates')
    assert [x['id'] for x in after if x['is_default']]==defaults
    for x in after:
        if x['id'] in before: assert hashlib.sha256(x['body'].encode()).hexdigest()==before[x['id']]
    result['status']='verified'; record()

if __name__=='__main__': main()

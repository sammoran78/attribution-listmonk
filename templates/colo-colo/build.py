"""Build four editable Colo Colo listmonk template kits. No network calls."""
import json
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parent
LOGO = 'https://lists.creativeattribution.com/uploads/chile_colo-colo.football-logos.png'
WEB = 'https://colocolosydney.com'
PHOTO = WEB + '/wp-content/uploads/2026/09/'
GREETING = '<p>Hello{{ with .Subscriber.FirstName }} {{ . }}{{ end }},</p>'

def save(folder, name, text):
    p = BASE / folder
    p.mkdir(exist_ok=True)
    (p / name).write_text(text, encoding='utf-8')

def image(url, alt):
    return f'<p><img src="{url}" alt="{alt}" width="560" style="display:block;width:100%;max-width:560px;height:auto;border:0;"></p>'

def button(url, label):
    return f'<p><a href="{url}" style="display:inline-block;background-color:#C8203A;color:#ffffff;padding:14px 22px;font-size:15px;font-weight:bold;text-decoration:none;border-radius:4px;">{label} &rarr;</a></p>'

def section(label, title, body):
    return f'<p style="margin:30px 0 8px;color:#C8203A;font-size:11px;font-weight:bold;letter-spacing:1.5px;text-transform:uppercase;">{label}</p><h2>{title}</h2>{body}'

def photo_template(label, title, intro, hero, alt, reason):
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="x-apple-disable-message-reformatting"><meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>{{ .Campaign.Subject }}</title>
<style>
:root{color-scheme:light dark;supported-color-schemes:light dark}body,table,td,a{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}body{margin:0!important;padding:0!important}table{border-collapse:collapse}table,td{mso-table-lspace:0pt;mso-table-rspace:0pt}img{border:0;outline:none;-ms-interpolation-mode:bicubic}a{color:#1B3A66}.copy p{margin:0 0 18px;line-height:1.65}.copy h2{font-size:26px;line-height:1.25;margin:0 0 16px;color:#1B3A66}.copy h3{font-size:20px;line-height:1.4;margin:22px 0 12px}.copy li{margin-bottom:10px}.copy img{max-width:100%!important;height:auto!important}
@media only screen and (max-width:660px){.outer{padding:14px 8px!important}.pad{padding-left:24px!important;padding-right:24px!important}.headline{font-size:32px!important}.brand-name{font-size:22px!important}.crest{width:72px!important;height:auto!important}.brand-pad{padding:22px 24px!important}}
@media(prefers-color-scheme:dark){.page,.footer{background-color:#111a27!important;color:#e4e8ef!important}.surface{background-color:#1d293a!important;color:#f7f4ee!important}.surface h1,.surface h2,.surface h3,.surface p,.surface li{color:#f7f4ee!important}.surface a{color:#a9cfff!important}.surface a[style*="background-color"]{background-color:#C8203A!important;color:#fff!important}.footer a{color:#dce3ee!important}.muted{color:#dce3ee!important}}
[data-ogsc] .surface,[data-ogsb] .surface{background-color:#1d293a!important;color:#f7f4ee!important}[data-ogsc] .surface p,[data-ogsc] .surface h1,[data-ogsc] .surface h2,[data-ogsc] .surface h3,[data-ogsc] .surface li{color:#f7f4ee!important}[data-ogsc] .surface a{color:#a9cfff!important}[data-ogsc] .surface a[style*="background-color"]{color:#fff!important;background-color:#C8203A!important}[data-ogsc] .footer,[data-ogsb] .footer{background-color:#111a27!important;color:#e4e8ef!important}[data-ogsc] .footer a{color:#dce3ee!important}
</style></head>
{{ $c := .Campaign.Attribs.colocolo | default dict }}
<body class="page" bgcolor="#F7F4EE" style="background-color:#F7F4EE;font-family:Arial,Helvetica,sans-serif;color:#1A1F2B;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">{{ $c.preheader | default "__INTRO__" }}</div>
<table role="presentation" width="100%"><tr><td align="center" class="outer" style="padding:28px 16px;">
{{ Safe "<!--[if mso]><table role='presentation' width='640'><tr><td><![endif]-->" }}
<table role="presentation" width="640" style="width:100%;max-width:640px;">
<tr><td align="right" style="padding:0 0 14px;font-size:12px;"><a href="{{ MessageURL }}" style="color:#5A5F6B;">View in your browser</a></td></tr>
<tr><td class="brand-pad" bgcolor="#F7F4EE" style="padding:24px 40px;border-top:5px solid #C8203A;background-color:#F7F4EE;color:#1A1F2B;"><table role="presentation" width="100%"><tr><td width="100"><a href="__WEB__/"><img class="crest" src="__LOGO__" width="80" height="80" alt="Colo Colo crest" style="display:block;background-color:#ffffff;"></a></td><td><p class="brand-name" style="margin:0;font-size:27px;font-weight:800;letter-spacing:-.8px;color:#1A1F2B;">Colo Colo Sydney</p><p style="margin:7px 0 0;font-size:11px;line-height:17px;letter-spacing:1px;color:#1B3A66;">CULTURE. COMMUNITY. FOOTBALL.</p></td></tr></table></td></tr>
<tr><td bgcolor="#1B3A66" style="padding:12px 40px;color:#ffffff;font-size:11px;font-weight:bold;letter-spacing:2px;">__LABEL__</td></tr>
<tr><td><img src="{{ $c.hero_url | default "__HERO__" }}" alt="{{ $c.hero_alt | default "__ALT__" }}" width="640" style="display:block;width:100%;max-width:640px;height:auto;"></td></tr>
<tr><td class="surface pad" bgcolor="#ffffff" style="padding:32px 40px 18px;background-color:#ffffff;"><h1 class="headline" style="margin:0 0 16px;font-size:40px;line-height:1.08;letter-spacing:-1.2px;color:#1B3A66;">{{ $c.title | default "__TITLE__" }}</h1><p class="muted" style="margin:0;font-size:17px;line-height:27px;color:#5A5F6B;">{{ $c.intro | default "__INTRO__" }}</p></td></tr>
<tr><td class="surface pad copy" bgcolor="#ffffff" style="padding:12px 40px 32px;background-color:#ffffff;font-size:16px;line-height:26px;">{{ template "content" . }}</td></tr>
<tr><td class="footer pad" style="padding:26px 40px;border-top:3px solid #C8203A;font-size:12px;line-height:20px;color:#5A5F6B;"><p style="margin:0 0 10px;font-weight:bold;">Colo Colo Sports Social Club Incorporated</p><p style="margin:0 0 12px;">P.O. Box 642, Fairfield, NSW 2165<br>__REASON__</p><p style="margin:0 0 12px;"><a href="__WEB__/contact/" style="color:#1B3A66;">Contact the club</a> &nbsp;&middot;&nbsp; <a href="__WEB__/" style="color:#1B3A66;">Website</a></p><p style="margin:0;"><a href="{{ UnsubscribeURL }}?manage=true" style="color:#5A5F6B;">Manage preferences</a> &nbsp;&middot;&nbsp; <a href="{{ UnsubscribeURL }}" style="color:#5A5F6B;">Unsubscribe</a></p><p style="margin:12px 0 0;">&copy; {{ Date "2006" }} Colo Colo Sydney</p>{{ TrackView }}</td></tr>
</table>{{ Safe "<!--[if mso]></td></tr></table><![endif]-->" }}</td></tr></table></body></html>'''.replace('__LABEL__', label).replace('__TITLE__', title).replace('__INTRO__', intro).replace('__HERO__', hero).replace('__ALT__', alt).replace('__REASON__', reason).replace('__LOGO__', LOGO).replace('__WEB__', WEB)

def main():
    committee = (BASE.parent / 'cairn/campaign-template.html').read_text(encoding='utf-8')
    replacements = {'cairn':'colocolo', 'CAIRN':'Colo Colo Sydney', 'https://www.colocolo.org.au/':WEB+'/',
        'Creative AI Research Network':'Colo Colo Sports Social Club Incorporated',
        'Reading group invitation':'Committee meeting', 'Our next reading group':'Committee meeting',
        'Lunchtime Reading Group':'Committee Meeting', 'reading group':'committee meeting',
        'Reading group':'Committee', 'Shared reading. New perspectives.':'Working together for our club.',
        'An interdisciplinary forum exploring AI and the creative sector.':'Committee notices, meeting papers and club business.',
        'Bring your questions and a perspective from your own discipline.':'Please review the agenda and papers before the meeting.',
        '#ffebcc':'#F7F4EE','#3a312e':'#1B3A66','#fffaf3':'#ffffff','#784322':'#C8203A',
        '#685851':'#5A5F6B','#f4e3cc':'#edf1f6','#dfc9ae':'#d3dbe6',
        '#191715':'#111a27','#24201d':'#1d293a','#352c25':'#23344b','#30251f':'#14243b',
        '#fff4e6':'#f7f4ee','#ffd49b':'#a9cfff','#dccfc3':'#dce3ee','#d4ae7d':'#a9cfff',
        '#806a54':'#4d6482','#f0cf9d':'#dce3ee'}
    for old, new in replacements.items():
        committee = committee.replace(old,new)
    start = committee.index('        <tr><td class="colocolo-brand"')
    end = committee.index('        <tr><td class="section-pad colocolo-surface"',start)
    committee = committee[:start]+f'''        <tr><td bgcolor="#F7F4EE" align="center" style="padding:26px;background-color:#F7F4EE;">
<a href="{WEB}/"><img src="{LOGO}" width="96" height="96" alt="Colo Colo crest" style="display:block;background-color:#ffffff;"></a>
<p style="margin:16px 0 0;font-size:26px;font-weight:bold;color:#1B3A66;">Colo Colo Sydney</p></td></tr>
'''+committee[end:]
    committee = committee.replace('Online via Zoom','{{ $e.location | default "Location to be confirmed" }}')
    # Replacement inside Go string expressions must use expressions, not nested template braces.
    committee = committee.replace('| default "{{ $e.location | default "Location to be confirmed" }}"', '| default $e.location | default "Location to be confirmed"')
    committee = committee.replace('JOIN THE CONVERSATION','MEETING ACCESS').replace('Meet us on Zoom','Join the committee meeting')
    committee = committee.replace('You’re receiving this email as a subscriber to the Colo Colo Sydney mailing list.', 'You’re receiving this email on the Colo Colo Sydney Committee list.')
    save('committee','campaign-template.html',committee)
    attrs={'colocolo':{'event_title':'[Committee meeting title]','calendar_title':'Colo Colo Sydney: Committee Meeting','preheader':'Committee meeting notice, agenda and papers.','start':'','end':'','timezone':'Australia/Sydney','location':'','calendar_description':'','calendar_ics_url':'','zoom_url':'','zoom_meeting_id':'','zoom_passcode':''}}
    save('committee','starter-attributes.json',json.dumps(attrs,indent=2)+'\n')
    body=GREETING+'<p>Please join our next committee meeting. The agenda and papers are below.</p>'+section('Meeting business','Agenda','<ol><li>[Welcome, attendance and apologies]</li><li>[Previous minutes and outstanding actions]</li><li>[Treasurer’s report and fundraising]</li><li>[Events, projects and football updates]</li><li>[Decisions, action owners and next meeting]</li></ol>')+section('Before we meet','Papers &amp; apologies','<p>[Add links to the agenda, previous minutes and supporting papers.]</p><p>[Add the RSVP or apologies contact and deadline.]</p>')+'<p>Thank you,<br>The Colo Colo Sydney Committee</p>'
    save('committee','campaign-body.html',body)
    alt=(BASE.parent/'cairn/campaign-alt-body.txt').read_text(encoding='utf-8').replace('cairn','colocolo').replace('CAIRN READING GROUP','COLO COLO SYDNEY COMMITTEE').replace('Our next reading group','Committee meeting').replace('The CAIRN team','The Colo Colo Sydney Committee').replace('https://www.colocolo.org.au/',WEB+'/')
    a=alt.index("WHAT WE'RE READING"); z=alt.index('JOIN ON ZOOM')
    alt=alt[:a]+'LOCATION\n{{ $e.location | default "Location to be confirmed" }}\n\nAGENDA\n[Add agenda items, decisions required and action owners.]\n\nPAPERS & APOLOGIES\n[Add document URLs, RSVP contact and deadline.]\n\n'+alt[z:]
    save('committee','campaign-alt-body.txt',alt)

    variants={
      'members': ('MEMBERS / CLUB UPDATE','Look what we’re building together.','Your member update: recent events, shared progress and what comes next.',PHOTO+'Colo-Colo-Damas.jpg','Members of the Colo Colo community','You’re receiving this update as a member on the Colo Colo Sydney Members list.'),
      'newsletter': ('WHAT’S ON / COLO COLO SYDNEY','Your next reason to come together.','Events, culture and football. Find your place in the Colo Colo community.',PHOTO+'365176993_598292292497049_5939250674213667038_n-Firefly-Upscaler-2x-scale.jpg','Chilean Festival stage and audience','You signed up for the Colo Colo Sydney Newsletter.'),
      'football': ('FOOTBALL / ESCUELA · TEAMS · SOCIAL','See you on the pitch.','Training news, season dates and the next chance to play.',PHOTO+'colocolo_escuela_drills.jpg','Football training drills on the club website','You signed up for Colo Colo Sydney Football updates.')}
    bodies={
      'members':GREETING+'<p>Thank you for supporting Colo Colo Sydney. Here’s a look at the people, events and projects your membership helps bring together.</p>'+section('01 / Looking back','[Recent event highlight]','<p>[Add the event date, a short recap and a thank-you to the members and volunteers who made it happen.]</p>')+image(PHOTO+'cueca-2.jpg','Chilean dance from the club’s community photo collection')+section('02 / Your support at work','[Project or fundraising goal]','<p>[Explain the project, who it will benefit and what member support is making possible.]</p><ul><li><strong>Raised so far:</strong> [confirmed amount and reporting date]</li><li><strong>Our goal:</strong> [approved target]</li><li><strong>Next milestone:</strong> [what happens next and when]</li></ul><p>[Add a specific way members can help and a verified project link.]</p>')+section('03 / Club notes','[Member notices &amp; next steps]','<p>[Add member updates, volunteering opportunities and the next progress report.]</p>')+button(WEB+'/get-involved/','Help with the next chapter')+'<p>With thanks,<br>The Colo Colo Sydney team</p>',
      'newsletter':GREETING+section('01 / Coming up','[Featured upcoming event]','<p>[Add a lively event introduction: what’s happening, who it’s for and why to come along.]</p><p><strong>When:</strong> [confirmed date and time]<br><strong>Where:</strong> [venue and suburb]<br><strong>Entry:</strong> [confirmed price or free entry]</p><p>[Add the verified booking link and booking deadline.]</p>')+button(WEB+'/chilean-festival/','Explore the Chilean Festival')+image(PHOTO+'futbol_kids-1.jpg','Young players taking part in football activities')+section('02 / Get on the pitch','Football for the next generation','<p>Discover Escuela Colo-Colo Sydney and register your interest in the youth football program.</p><p>[Add confirmed upcoming football events, open days or registration news.]</p>')+button(WEB+'/escuela/','Explore Escuela football')+section('03 / Make it your club','Become a member','<p>Help keep Chilean culture, club events and community projects growing in Sydney. Membership is one way to support the club’s future and bring your ideas to it.</p>')+button(WEB+'/membership/','Become a member')+section('Also coming up','[More dates for your diary]','<ul><li>[Event · date · booking link]</li><li>[Community activity · date · details link]</li></ul>'),
      'football':GREETING+'<p>[Add a short update for players, parents, carers and coaches.]</p>'+section('01 / This week','Training &amp; ground updates','<p><strong>Group / team:</strong> [age group or team]<br><strong>Training:</strong> [day, date and time]<br><strong>Ground:</strong> [venue and meeting point]<br><strong>Bring:</strong> [kit and equipment]<br><strong>Wet weather:</strong> [where and when changes will be announced]</p>')+section('02 / Plan ahead','Season dates','<ul><li><strong>Registration:</strong> [opening and closing dates]</li><li><strong>First session / round:</strong> [confirmed date]</li><li><strong>Breaks &amp; final round:</strong> [confirmed dates]</li></ul>')+image(PHOTO+'futbol_kids-1.jpg','Football activities for young players')+section('03 / Escuela &amp; camps','[Training camp or school update]','<p>[Add age groups, dates, venue, places, confirmed costs and a verified registration link.]</p>')+button(WEB+'/escuela/','Escuela information &amp; interest')+section('04 / Teams &amp; social soccer','[Fixtures, social games &amp; team functions]','<p>[Add team fixtures, social soccer arrangements, team functions and RSVP deadlines.]</p><p><strong>Football contact:</strong> [name and preferred contact details]</p>')+button(WEB+'/contact/','Contact the football organisers')}
    for key,values in variants.items():
        save(key,'campaign-template.html',photo_template(*values))
        save(key,'campaign-body.html',bodies[key])
        save(key,'starter-attributes.json',json.dumps({'colocolo':dict(zip(['title','intro','hero_url','hero_alt'],[values[1],values[2],values[3],values[4]]),preheader=values[2])},ensure_ascii=False,indent=2)+'\n')
        # Keep link destinations in the separately editable plain-text alternative.
        plain = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',r'\2: \1',bodies[key])
        plain = re.sub(r'<img[^>]*>','',plain)
        plain = re.sub(r'</(?:p|h2|li)>|<br\s*/?>','\n\n',plain)
        plain = re.sub('<[^>]+>','',plain)
        import html
        plain=html.unescape(plain)
        save(key,'campaign-alt-body.txt','COLO COLO SYDNEY / '+key.upper()+'\n{{ $c := .Campaign.Attribs.colocolo | default dict }}\n{{ $c.title }}\n{{ $c.intro }}\n\n'+plain+'\nColo Colo Sports Social Club Incorporated\nP.O. Box 642, Fairfield, NSW 2165\n'+WEB+'/\nManage preferences: {{ UnsubscribeURL }}?manage=true\nUnsubscribe: {{ UnsubscribeURL }}\nView in browser: {{ MessageURL }}\n')
    helper=(BASE.parent/'cairn/prepare-event.py').read_text(encoding='utf-8').replace('CAIRN','Colo Colo Sydney').replace('cairn','colocolo').replace('Lunchtime Reading Group','Committee Meeting').replace('Reading Group','Committee Meeting').replace('Reading topic: ','Meeting: ').replace('@colocolo.org.au','@colocolosydney.com').replace('colocolo-reading-group.ics','colocolo-committee.ics').replace('event.get("zoom_url") or "Online via Zoom"','event.get("zoom_url") or event.get("location") or "Location to be confirmed"')
    save('committee','prepare-event.py',helper)
    print('Built four template kits.')

if __name__=='__main__': main()

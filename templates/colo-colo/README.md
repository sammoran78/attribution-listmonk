# Colo Colo Sydney email templates

Installed on the existing listmonk server on 12 October 2026. Nothing was sent
or scheduled. The existing default and CAIRN templates were preserved.

| Audience | Template ID | Starter campaign ID | List ID |
| --- | --- | --- | --- |
| Committee | 6 | 6 | 8 |
| Members | 7 | 7 | 9 |
| Newsletter | 8 | 8 | 10 |
| Football | 9 | 9 | 11 |

## Use a starter

In Campaigns → All campaigns, clone the matching **[DRAFT] Colo Colo Sydney … —
starter**. Cloning retains the right list, template, attributes, sender and
editable content. Templates alone do not automatically select a mailing list.

1. Edit the subject and replace the square-bracket placeholders in Content.
   Remove sections you do not need. The editor is Rich text; switching to the
   Visual editor bypasses these campaign templates.
2. Under Attributes, edit the `colocolo` object. In the photo templates,
   `title`, `intro`, `preheader`, `hero_url` and `hero_alt` control the opening.
   Replace the main photo URL with a new HTTPS Media URL when appropriate.
   Other photos and buttons can be edited directly in Content.
3. Update the separately editable plain-text alternative to match your copy.
4. Review the audience, links, dates, images and preview before sending.
   These are reusable starters, not finished announcements.

Members has event recaps, project/fundraising progress and member notices.
Newsletter has upcoming events, football promotion and a membership invitation.
Football has training/ground updates, season dates, camps and team/social news.

## Committee meetings

The committee layout adapts CAIRN’s meeting notice, agenda, papers, Zoom and
calendar links. Fill in `event_title`, `calendar_title`, `start`, `end`,
`timezone` and `location`. For online meetings, add `zoom_url` and optionally
`zoom_meeting_id` and `zoom_passcode`. The default zone is `Australia/Sydney`.

Use explicit ISO timestamps with seconds and the correct seasonal UTC offset,
for example `2026-10-20T19:00:00+11:00`. The starter contains no event date.
Google and Outlook links use the same timestamps and convert to UTC. With no
times, the date shows as unconfirmed and calendar links stay hidden.

For Apple/other calendar apps, save the attributes as JSON and run:

```sh
python committee/prepare-event.py meeting-attributes.json --output meeting-output
```

Upload the generated `colocolo-committee.ics` through Media and put its HTTPS URL
in `calendar_ics_url`. Keep the generated UID if revising an event. Windows
Python needs the `tzdata` package; the bundled Codex Python already includes it.
The helper validates time ordering and Sydney offsets. For hybrid meetings,
include the physical address in the calendar description as well as location.

## Branding and delivery

The crest reuses existing Media item 8. Photos remain hosted on the official
website. They are editable examples and do not document a newly announced event
or a specific funded project. The members hero is an archive community photo.

The designs use the website’s cream, navy and red palette, inline email styles,
presentation tables, mobile spacing, alternative text, preference/unsubscribe
links, and dark-mode styles. Fonts fall back to Arial/Helvetica.

From is `Colo Colo Sydney <newsletter@creativeattribution.com>`, using the
existing verified sender domain. Each draft has `Reply-To: info@colocolosydney.com`,
the club’s published contact address. No domain/SMTP configuration was changed.
No new service, paid resource, or email send was introduced.

## Sources and verification

- [Official website](https://colocolosydney.com/)
- [Membership](https://colocolosydney.com/membership/)
- [Escuela](https://colocolosydney.com/escuela/)
- [Festival](https://colocolosydney.com/chilean-festival/)
- [Get involved](https://colocolosydney.com/get-involved/)
- [Contact](https://colocolosydney.com/contact/)

Website dates and details were inconsistent or unconfirmed in places; the
starters therefore keep dates, prices, schedules and fundraising figures blank.

`installation.json` records IDs and saved-state verification. Live previews
passed Go template rendering, audience/template association, draft status and
zero-send checks. Committee calendar links passed UTC/Sydney daylight-saving
checks. Browser checks confirmed loaded photos and no horizontal overflow at
390px. Screenshots and preview HTML are saved beside each kit. Dark previews
exercise Outlook CSS selectors, not a real Outlook client. No inbox test was sent.

`build.py` regenerates local kits; it does not update the server. `install.py`
refuses to rerun when its receipt exists to protect edited drafts. Keep source
snapshots and preview evidence local; they are ignored by Git.

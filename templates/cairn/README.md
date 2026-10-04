# CAIRN reading group campaign

The template follows [CAIRN's website](https://www.cairn.org.au/): cream #ffebcc,
dark brown #3a312e, the supplied black CAIRN logo, and Inter with Arial/Helvetica
fallbacks. Email clients often ignore web fonts, so there are no external font
downloads. Presentation tables, inline essential styles, explicit image sizes,
mobile spacing, and Outlook conditional markup keep the design portable.

## Dark mode

The saved template now supplies a dark palette through `prefers-color-scheme`
and Outlook's `data-ogsc` / `data-ogsb` selectors. Body text, inline rich-text
headings, calendar links, the Zoom panel and button, and footer have explicit
dark styles. Light mode keeps the original CAIRN colours.

`assets/cairn-main-logo-email.png` is an opaque cream composite of the original
transparent PNG. It preserves the original dimensions and artwork; the uploaded
copy gives the black lettering its own light background when email clients
darken surrounding HTML. Keep the original PNG for other uses.

The active email header uses `assets/cairn-logo-band.png`: the same unchanged
original artwork centered on a 1280 × 528 opaque cream canvas. It displays
across the full 640px email column and scales on mobile. The background is part
of the pixels, so forced dark mode cannot leave a floating cream rectangle
around the logo. Supported dark-mode clients swap this for
`assets/cairn-logo-band-dark.png`, with white lettering on a dark canvas and
exactly the same letter shapes. Clients that do not honour image swapping keep
the readable full-width cream band. The alternate image is hidden inline and
excluded from legacy Outlook through conditional comments.

`preview-light.html` and `preview-dark.html` are standalone example renders from
listmonk. The dark proof activates the Outlook selectors in a browser; it does
not reproduce Outlook's proprietary colour transformations. Browser text contrast
checks passed (minimum 5.38:1 light, 9.84:1 dark). Email clients differ, so send a
fresh test and check the actual iPhone Outlook display before a campaign send.
Previously delivered messages do not pick up changes to the saved template.

`update-dark-mode.py` audits by default. Its explicit `--apply --expected-hash`
mode backs up template 5 privately on the VM, uploads the separate email logo,
updates only that template, and validates an unsent disposable example draft.
It does not change existing campaign content or send email. Installation details
are recorded in `dark-mode-installation.json`.

Client behaviour reference: [Litmus dark-mode guide](https://www.litmus.com/blog/the-ultimate-guide-to-dark-mode-for-email-marketers).

## Use in listmonk

1. Open **Campaigns → All campaigns** and clone **[DRAFT] CAIRN reading group —
   starter**. It is assigned to the existing CAIRN list and uses the campaign
   template **CAIRN — Reading group invitation**. The starter uses Rich text so
   the reading text can be edited directly. Raw HTML also works; the Visual
   editor uses its own layout and bypasses this template.
2. Change the subject and edit the reading, introduction, and discussion questions
   in **Content**. Replace all square-bracket placeholders. The greeting falls
   back to “Hello,” when a subscriber has no name. Reading links can use the
   editor's link control; `{{ TrackLink "https://your-reading-url" }}` is optional.
3. In **Attributes**, edit the `cairn` object from `starter-attributes.json`.
   Enter `event_title`, `start`, `end`, and `zoom_url`. Dates must be ISO timestamps
   with seconds and an explicit offset: `2026-10-20T12:00:00+11:00` is an example,
   not a scheduled event. Use `Australia/Sydney` for Sydney time, with +11:00 in
   daylight saving time and +10:00 in standard time. Other IANA zones work too.
   `preheader`, `calendar_description`, `zoom_meeting_id`, and `zoom_passcode`
   are optional. Leave absent fields as empty strings.
4. Google and Microsoft 365 calendar links are generated from those same event
   times. They include the Zoom link and use UTC to avoid ambiguous calendar
   offsets. Without both times, the template shows “Date and time to be confirmed”
   and omits calendar actions. Without a Zoom URL, it omits the join button.
5. For Apple Calendar or another calendar app, generate the `.ics` using
   `python prepare-event.py your-event.json --output event-output`, upload
   `cairn-reading-group.ics` under **Media**, and paste its HTTPS URL into
   `calendar_ics_url`. The Apple / .ics link then appears. Optionally attach the
   same file in **Content → Attachments**. Keep the generated UID when updating
   an event. The helper checks dates, timezone offsets, and ordering, and writes
   escaped UTF-8 content with CRLF and RFC-compliant line folding.
6. Update the plain-text alternative alongside the HTML reading text. Date,
   Zoom, and calendar details in that alternative use the same attributes.
7. Preview, send a test to your own verified address, and check the calendar
   time, reading URL, and Zoom details before starting the campaign. This setup
   creates a draft and does not send or schedule email.

## Files and listmonk expressions

- `campaign-template.html`: complete reusable email layout, with exactly one
  `{{ template "content" . }}` insertion. During installation the logo URL is
  changed to the copy in your existing listmonk Media store.
- `campaign-body.html`: editable reading/discussion starter content.
- `campaign-alt-body.txt`: multipart plain-text alternative.
- `starter-attributes.json`: empty event configuration for the unsent draft.
- `example-event.json`: fictional event used only for rendering checks.
- `prepare-event.py`: optional local event validation and `.ics` generation.
- `preview.html`: standalone rendered example; sample dates and links are not
  live event details. It can be opened without listmonk.
- `preview-desktop.jpg` and `preview-mobile.jpg`: checked layout snapshots.
- `installation.json`: saved template, draft, list, and media IDs.

The template uses `MessageURL`, `UnsubscribeURL`, the documented manage-preferences
query, and one `TrackView`. Go/Sprig expressions render event data from
`.Campaign.Attribs.cairn`, available in this fork, and `mustToDate` fails on
malformed dates rather than silently putting the wrong date on an invitation.
Calendar and Zoom links are direct links; they are not wrapped in click tracking.
The unsubscribe and browser links are generated by listmonk at send time.
The CAIRN template is not made the global default for other mailing lists.

Sources: [listmonk templating](https://listmonk.app/docs/templating/),
[RFC 5545 iCalendar](https://www.rfc-editor.org/rfc/rfc5545.html),
[Google Calendar link format](https://github.com/InteractionDesignFoundation/add-event-to-calendar-docs/blob/main/services/google.md).

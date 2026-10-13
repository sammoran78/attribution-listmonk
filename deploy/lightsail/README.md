# Deployed listmonk on Lightsail

Current signup integration and deployment: [Negro Matapacos signup verification](signup-verified-20261005.md). Compile builds off the production VM; see the memory incident and rollback notes there.


Deployed 2 October 2026 with approval for the VM, metered sending, SNS delivery,
simulator tests, and deletion of the old feedback pipeline.

## Access and service

- Site: https://lists.creativeattribution.com/admin/login
- Username: `admin`; initial password: local ignored `secrets/admin_password`.
- AWS account: `366101997840`; region: Sydney (`ap-southeast-2`).
- Instance: `attribution-listmonk`; attached static IP: `13.54.46.240`.
- Azure DNS: `lists.creativeattribution.com` A record points to that IP.
- SSH user: `ubuntu`; VM directory: `/opt/listmonk/deploy/lightsail`.
- Local key and host fingerprints: ignored `secrets` directory.
  The private `secrets/access-notes.md` records the key passphrase.
- SSH is restricted to `163.53.146.38/32`; update the narrow firewall entry if
  your public IP changes.

Change the admin password in the dashboard after first login. The initial
password file does not change when the dashboard password changes.

Ubuntu 24.04, Lightsail `micro_3_2`: 1 GB RAM, two burstable vCPUs, 40 GB disk,
1,024 GB/month Sydney transfer allowance, attached static IPv4: **US$7/month**
before tax and currency conversion. Stopping the instance does not stop billing;
an unattached static IP can incur charges.

Docker runs this fork at commit `3f9177a51d192f0c6ec9d75cb028306adbc16cba`,
PostgreSQL 17, and Caddy with automatic HTTPS. Only TCP 80/443 are public;
database port 5432 and app port 9000 stay private to Docker. Persistent volumes
hold PostgreSQL, uploads, and TLS state. Container logs are capped at 10 MB each.
The host has 2 GB swap on its included disk.

SES's live pricing is now `CurrentPlan=NONE` rather than Essentials. Sending is
metered at US$0.10 per 1,000 recipients plus applicable data charges. SNS
publishing, HTTPS notifications, and applicable transfer are metered too.
No RDS, load balancer, NAT gateway, paid registry, cloud backup, or new DNS zone
was created. Seek approval before resizing or adding paid services.

Sources: [Lightsail pricing](https://aws.amazon.com/lightsail/pricing/),
[SES pricing](https://aws.amazon.com/ses/pricing/),
[SNS pricing](https://aws.amazon.com/sns/pricing/).

## Email and feedback

Default From: `Creative Attribution <newsletter@creativeattribution.com>`.
Reply-To: `sam.moran@mq.edu.au`, verified in both SES notification headers.
Other send-as addresses at the verified domain can be entered in campaign
From fields; they do not need mailboxes. Dedicated SMTP IAM user
`listmonk-ses-smtp` permits only `ses:SendRawEmail` for identities in this Sydney account,
with From addresses restricted to the domain. Recipient identities are included
in the resource scope so sandbox test recipients are not denied by IAM.

Reply-To sends replies to the personal inbox. Direct mail to a domain alias
would need a forwarding service. No inbound mail server, MX change, mailbox
hosting, or alias-forwarding service was provisioned.

SMTP uses Sydney SES on port 587 with STARTTLS and certificate verification.
The pool allows two connections so smtppool v2.1.2's idle sweeper runs, with
a five-second idle timeout. Campaign concurrency and sending rate remain one.
**SES remains in the sandbox**: 200 recipients/day, one/second, and only
verified recipients or simulator addresses. Expected subscriber count,
sending volume, and actual opt-in process are needed before requesting
[production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html).
No production-access request has been submitted.

SES identity Bounce and Complaint notifications go to the existing
`ses-bounce-complaints` SNS topic, then directly to
`https://lists.creativeattribution.com/webhooks/service/ses`. The confirmed
HTTPS subscription has raw delivery disabled, signature version 1, original
headers enabled, and a 50-retry policy. Topic publishing is restricted to this
account and domain identity.

Identity notifications are used because this fork does not process
configuration-set complaint events correctly. The old configuration-set event
destination was removed; the configuration set remains for existing callers.
SES email feedback forwarding is disabled because the domain has no monitored
mailbox. SES account suppression for BOUNCE and COMPLAINT stays enabled.

Listmonk records feedback in PostgreSQL and blocklists after one hard bounce or
complaint. Soft-bounce action is none after two records. Listmonk supplies its
own campaign opens/clicks reporting; SES still supplies account reputation
statistics. Long VM downtime can lose feedback after SNS's finite retries;
no paid queue or off-server archive was added.
[SNS retry behavior](https://docs.aws.amazon.com/sns/latest/dg/sns-message-delivery-retries.html).

## Verified outcome and cleanup

- Both frontends and the fork server built on the VM; frontend lint passed.
- HTTPS certificate issued; admin login and authenticated API passed.
- Three previews sent only to SES success, bounce, and complaint simulators.
- Hard bounce and complaint recorded with source `ses` and campaign ID 2;
  both recipients blocklisted. Reply-To headers matched.
- Unsubscribe page and submission passed; success simulator unsubscribed.
- App/database restart preserved records and HTTPS.
- PostgreSQL backup restored into a temporary database and counts checked;
  the temporary database was removed. Upload archive extraction passed
  (there were no real uploads yet).
- The installation's two sample subscribers were removed. The private Setup
  verification list and draft retain simulator evidence.
- Deleted CloudFormation `ses-feedback-suppression`, its Lambda, old SNS
  subscription, execution role, and logs. Explicitly deleted retained DynamoDB
  `ses-suppressed-addresses` and SQS failure queue.
- Re-audit confirmed no Lambda functions, DynamoDB tables, or SQS queues in
  Sydney, no old role/log group, and only the new HTTPS topic subscription.
  Other regions were restricted by organization policy in the initial audit;
  this is not an account-wide billing report.

## Backups and operation

`listmonk-backup.timer` runs `backup.sh` daily at 03:00 Australia/Sydney. Dumps
and uploads archives stay on the VM, retaining about a week. A recovery archive
was copied into the local ignored `backups` directory. It contains credentials;
keep it private. Copy newer backups to an existing computer periodically:
VM-local backups do not survive disk loss. No paid cloud snapshots are enabled.

On the VM:

```sh
cd /opt/listmonk/deploy/lightsail
sudo docker compose ps
sudo docker compose logs --tail 50 app
sudo systemctl start listmonk-backup.service
sudo systemctl list-timers listmonk-backup.timer
```

Use this directory's Compose file, rather than the upstream root Compose file.
Base images and PostgreSQL/Caddy are pinned to deployed digests.
`Dockerfile.fork` builds both frontends and embeds assets/schema. The main
frontend's `.gitignore` must be included for lint; the root `.dockerignore`
contains the exception. VM builds need swap and the 1,536 MB Node heap.

`start.sh` creates initial secrets only if absent. Do not rerun
`ses-settings.sql` or `configure-smtp.py` after customizing settings unless
you intend to replace them. The simulator test script avoids resending if
its result file exists.

Before upgrading, back up, check disk space, build the tested new commit with a
distinct tag, and update `.env`. Then:

```sh
docker compose stop app
docker compose run --rm app ./listmonk --upgrade --yes --config ''
docker compose up -d
```

Never run `docker compose down -v` on production data. Keep the secrets directory
mode 700. Database/admin files are mode 444 inside that private parent so the
non-root containers can read their bind-mounted files.

## Branding and assigned-list update (2 October 2026)

The deployed update builds from base commit 3f9177a5 plus the local branding and
role-interface changes, under image tag 3f9177a5-ca-20261002. The supplied Creative
Attribution JPEG is reused unchanged for the admin, login/public, email, and
favicon branding. app.logo_url and app.favicon_url point to its public asset.

User Roles now offer List visibility: Assigned lists only or All lists. For
assigned access, create a List Role containing allowed lists and select that role
on the user. None gives no access when the User Role has no global list rights.
Existing user and role assignments are preserved. Global subscriber/campaign
permissions remain separate: disable *_all permissions for full isolation.
New User Roles no longer grant those global permissions by default.

The test-email toast says queued because SMTP delivery happens asynchronously;
it does not imply delivery. The IAM policy includes regional recipient identities
and restricts the From address to *@creativeattribution.com. SES sandbox still
requires recipient verification or production access.

## SMTP idle timeout correction (2 October 2026)

An authenticated SMTP connection reproduced SES's 451 timeout after 20 seconds
idle. smtppool v2.1.2 does not start its idle sweeper for a single-connection
pool. The live SMTP entry now permits two connections and closes idle ones after
five seconds; campaign concurrency and message rate stay at one. Other SMTP
settings were preserved. SES accepted a simulator SMTP test, and campaign
previews before and after 25 seconds idle produced no delivery errors.

Listmonk's email validator does not verify SES recipient identities. Following
the user's approval, AWS sent a verification link to samoran@gmail.com; its
Sydney identity subsequently reported Success. Production access is still
required to send to arbitrary unverified mailing-list recipients.

## Subscriber form permissions (2 October 2026)

Image tag: 3f9177a5-subscribers-20261002. The previous image and a private copy
of the previous .env are retained for rollback.

The subscriber list selector now offers only lists the user can manage. Global
list visibility no longer makes the frontend treat a list as manageable. The
API continues to enforce its existing permissions; no user or role assignments
were broadened. Save errors keep the form open and use the existing API error
toast without an unhandled promise rejection.

Preconfirmation is available only for double opt-in lists. When selected lists
use single opt-in, the form explains that no confirmation email is required.
Single opt-in campaigns do not require a confirmed subscription status.

The reported save error did not reproduce in the current sammoran Super Admin
session: a synthetic subscriber saved to lists 4, 5, and 6 in the browser before
the update. The admin API creation check also passed. verify-list-access.py
checks creation for assigned, unassigned, and globally visible lists, and
verify-subscriber-save.py checks saving all three reported lists. Both remove
their own temporary records and send no mail. Existing samoran@gmail.com should
be edited to change its memberships rather than created again.
The frontend permission checks in verify-subscriber-form.cjs also cover Super
Admin, view-all, manage-all, assigned management, read-only, and unassigned
profiles, plus single/double opt-in preconfirmation availability.

## Campaign and subscriber result scope (3 October 2026)

The live List Administrator User Role (ID 3) no longer has subscribers:get_all,
campaigns:get_all, or campaigns:manage_all. Those inherited global permissions
overrode the assigned List Role despite list visibility already being scoped.
The existing API now filters campaign and subscriber pages and searches to
records associated with at least one accessible list, and rejects direct URLs
for unrelated records. Super Admin access and each user's assigned List Role
are preserved. This is a role configuration change; no image rebuild is needed.

scope-list-role-results.py --apply applies the narrowing through the role API
(which refreshes API-token permission caches), backs up the original role in
the private secrets directory, and tests every existing List Role plus no
assigned lists using temporary API users. It checks list results, pagination,
searches, explicit subscriber list filters, and direct record URLs. It sends
no mail and removes its own test users. The current subscriber query can
return multiple rows for a subscriber belonging to multiple accessible lists;
the scope check accounts for membership rows when validating pagination.

## Dashboard and analytics scope (4 October 2026)

Image tag: 3f9177a5-analytics-20261004. Dashboard counts and charts use the
signed-in user's accessible list IDs. Restricted users bypass the shared global
materialized views; users with all-list access retain the existing global view.
Subscribers and campaigns associated with multiple accessible lists count once.
Records with no associated list are excluded from restricted users' totals.

Campaign analytics enforce the same list association in both the API handler
and database queries, including views, clicks, bounces, and link URLs. A global
campaign permission alone cannot bypass the list boundary. A campaign associated
with an accessible list exposes its whole campaign's analytics, matching its
visibility on the campaigns page. Chart date windows use only accessible events.

verify-analytics-scope.py --sql checks isolated, rolled-back fixtures for shared
memberships, forbidden events, empty scope, and raw/unique analytics. Its --api
checks existing List Roles, no-list access, global campaign/subscriber permission
overrides, and all-list access using temporary API users and roles; it removes
those records and sends no email. The update uses the existing VM, PostgreSQL
volume, and Docker services. It adds no AWS services or schema migration.

## Campaign custom attributes and event links (9 October 2026)

Image tag: 3f9177a5-event-links-20261009. Campaign responses preserve custom
attribute and header keys on list/detail/create/update/archive/status operations.
Previously the editor camel-cased nested custom keys, so saving/reopening a
campaign could break a template that expected `zoom_url` or `calendar_ics_url`.
verify-campaign-attributes.cjs checks the actual response interceptor and key
transformer, including three JSON save/reopen cycles, without network calls.

CAIRN template 5 accepts legacy camelCase keys as well as canonical snake_case.
Draft 3's keys were normalized; the incorrect sample calendar was replaced with
a separate Media file for 16 October 2026, 12:30–13:30 Sydney, and an invalid
plain-text meeting-ID expression was corrected. HTML reading copy, list/media
associations and draft status were preserved. The repair backup is private;
templates/cairn/fix-event-links.py audits and checks guarded changes without mail.

The full rebuild exceeded practical memory limits in the unchanged email builder.
Dockerfile.campaign-attributes reuses the cached frontend stage before this API
change and overlays only the new admin API module, with a 1 GiB Node heap limit.
For that build the original API file was briefly restored with its original 664
mode, the patched API was staged as campaign-api-update.js, and the working
source was restored afterward. No VM resize, new AWS resource, or schema change
was introduced. The prior image and environment remain available for rollback.

Live verification after deployment: the signed-in editor saved draft 3, reloaded
it and preserved its custom JSON keys verbatim. Its refreshed preview displayed
the correct Sydney date/time, Google/Outlook/.ics links, Zoom button and meeting
ID. The public calendar returned HTTP 200 with text/calendar. The campaign
remained a draft and no email was sent. See the live verification receipt and
screenshots under templates/cairn.

## CAIRN sender recovery (9 October 2026)

Campaign 3's sender name contained an unquoted colon. Go's mail parser returned
`mail: expected comma` before SMTP transmission for all 23 recipients. Its
default error threshold of 1000 was never reached, so exhausting the queue
marked the zero-send campaign finished. All 25 stored views predated this send
attempt; they are retained as historical pixel events, not delivery evidence.

`validate-campaign-addresses.go` reproduced the exact original parser error and
validated the quoted sender plus all 23 recipient addresses offline, without
SMTP connections. `recover-campaign-sender.py` privately backed up the original
row, guarded against concurrent changes and restored this specific finished,
zero-send campaign to draft. It reset the subscriber checkpoints and start
timestamp while retaining audience, content, calendar/Zoom attributes, views,
and counters. The sender is now `"CAIRN: Creative AI Research Network"
<newsletter@creativeattribution.com>`. The draft and preview were verified.
No campaign was started, no email sent, and no AWS resource changed.

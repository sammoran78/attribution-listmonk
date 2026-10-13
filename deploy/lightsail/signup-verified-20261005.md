# Negro Matapacos signup — 5 October 2026

Deployed image: `attribution-listmonk:signup-20261005`, based on the existing
`3f9177a5-analytics-20261004` runtime, with a locally compiled Linux binary.
No database migration, hosting upgrade, new cloud resource or email campaign.

`POST /api/public/negromatapacos/subscription` accepts email, optional name,
`preferred_languages` (exactly one of `Spanish` or `English`), explicit consent,
and an empty honeypot `nonce`. It writes only the public, active list with UUID
`f7a562f4-4162-4632-ad29-2cd6062c4f3a`. Unknown request fields are rejected.

Subscriber JSON contains `preferred_languages: ["English"]` or `["Spanish"]`,
plus `negromatapacos_consent` with timestamp, source, purpose and wording version.
Existing names, other attributes, global status and other memberships are
preserved. Disabled/blocklisted subscribers are not reactivated. An explicit
repeat signup can resubscribe to this list using listmonk's existing behavior.
The preference belongs to the shared subscriber record, not a single list.

The endpoint respects the list's opt-in setting. The live list uses **single
opt-in**, so this form saves records without sending confirmation email. If
changed to double opt-in, enable listmonk's confirmation sending and review its
template/language; the website already handles `has_optin: true`. Campaign sending
still incurs the existing SES usage charges and is a separate operation.

Allowed browser origins are `https://negromatapacos.cl` and the existing Azure
Static Web Apps hostname. Requests are limited to 4 KB and 5/minute per client
IP (burst 5). This assumes the existing Caddy-only public ingress; the app port
must remain private. Origin checking is not authentication or comprehensive bot
protection. The existing upstream subscription endpoints remain unchanged.

## Verification

Local Go 1.26.1:

```sh
go test cmd/negromatapacos.go cmd/negromatapacos_test.go -count=1 -v
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o listmonk-signup ./cmd
```

The explicit file test command avoids the main package's startup `init`, which
otherwise requires a configured database even for unit tests.

Passed validation, allowed-language, insert/update, suppression, unavailable-list,
CORS, body-size and IP-rate-limit tests. Live HTTPS verification created two
reserved `example.invalid` subscribers, checked exact language arrays, consent,
list scope, preservation on repeat signup and blocklist protection, then removed
both fixtures. No confirmation email was requested or sent. The production site
allows this service in its CSP; both desktop/mobile bilingual modal checks passed.

## Build and rollback

The first full Docker build exhausted the 1 GB VM's memory and temporarily
interrupted service. A VM restart restored the existing deployment. **Do not run
the full frontend build on this production VM.** Compile elsewhere and upload
the finished binary/image. No resize was performed.

For this backend-only update, the 137 static assets embedded in the deployed
binary were preserved byte-for-byte using stuffbin v1.3.0's documented format.
Asset archive SHA256:
`aa30fe00423fa784217e85b6a443c9bd3217a1eb2c007d3c001be3b377551529`.
The new Linux binary was smoke-tested with `--version` before the app switch.
Existing admin UI, SQL queries, templates, settings and volumes are unchanged.

The existing local backup service ran before deployment. Previous image remains
available. To roll back, set `LISTMONK_IMAGE_TAG=3f9177a5-analytics-20261004` in
the VM's protected `.env`, then `sudo docker compose up -d --no-deps app`.
The protected `.env.before-signup-20261005` also preserves that configuration.
Rolling back disables the new endpoint; coordinate the website CTA accordingly.

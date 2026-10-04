# AWS configuration and pricing confirmation — 3 October 2026

Read-only inventory of the Sydney deployment (`ap-southeast-2`), AWS account
366101997840. This confirms configuration and public list prices, not the
account's billed total across all regions or existing Azure DNS costs.

- One running Lightsail `attribution-listmonk` instance, bundle `micro_3_2`:
  US$7/month, 1 GB RAM, two vCPUs, 40 GB included disk and 1,024 GB monthly
  Sydney transfer allowance. One static IP, attached to the instance.
- PostgreSQL 17, the forked listmonk app and Caddy all run on that VM. The
  PostgreSQL data directory is the persistent local Docker volume
  `attribution-listmonk_postgres_data`; there is no managed database bill.
- SES `PricingAttributes.CurrentPlan=NONE`: à-la-carte sending. Production
  access is granted, with live quotas of 50,000 recipients per 24 hours and
  14 recipients per second. Sending is enabled and enforcement is healthy.
- Domain bounce and complaint notifications both target `ses-bounce-complaints`.
  Its only discovered subscription is the confirmed HTTPS endpoint at
  `https://lists.creativeattribution.com/webhooks/service/ses`.
- Listmonk bounce handling and its SES webhook are enabled. The local database
  contains two feedback records from setup testing. Hard bounces and complaints
  cause blocklisting after one event. SES also retains its own account-level
  suppression and reputation state.
- No Sydney Lambda functions, DynamoDB tables, SQS queues, RDS instances,
  load balancers, NAT gateways, CloudWatch log groups, dedicated SES IPs,
  Mail Manager ingress points or archives were found. Lightsail has no extra
  disks, managed databases, manual instance snapshots or automatic snapshots.
- Daily backups use the VM's own disk; no off-server backup service was added.

All prices below are USD before tax, credits and currency conversion.

| Item | Price |
| --- | --- |
| Existing Lightsail VM | $7/month |
| SES à-la-carte outbound email | $0.10/1,000 recipient emails |
| SES Essentials, for comparison | $0.16/1,000 recipient emails in the first 10M/month; no fixed monthly fee |
| SES applicable outgoing-data charges | $0.12/GB |
| PostgreSQL, listmonk and local feedback storage | No separate service charge |

Essentials includes SES Virtual Deliverability Manager. The current deployment
uses listmonk's reports instead. A newsletter sent to 1,000 subscribers counts
as 1,000 recipient emails. Computed VM-plus-SES examples: 1,000/month = $7.10;
10,000/month = $8.00; 100,000/month = $17.00, excluding data and SNS charges.

SNS remains the small feedback transport service. Its published free allowance
is one million requests and 100,000 HTTP notifications per month. Beyond that,
AWS quotes $0.50/million requests and $0.06/100,000 HTTP notifications, with
applicable data transfer charges. Allowances can be shared with other account
usage, and retries/payload size can affect billable requests.

Sources: [Lightsail](https://aws.amazon.com/lightsail/pricing/),
[SES](https://aws.amazon.com/ses/pricing/),
[SNS billing FAQ](https://aws.amazon.com/sns/faqs/).

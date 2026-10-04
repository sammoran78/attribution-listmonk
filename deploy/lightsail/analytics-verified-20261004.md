# Analytics isolation verification — 4 October 2026

Deployed image: `attribution-listmonk:3f9177a5-analytics-20261004`.
Docker build completed on the existing Lightsail VM. Database backup and
previous image/environment retained before replacing only the app container.

`verify-analytics-scope.py --sql` passed isolated PostgreSQL fixtures covering
overlapping subscriber memberships, shared campaigns, empty permissions,
forbidden events affecting date windows, raw/unique views and clicks, bounces,
and link URLs. All fixture data was rolled back.

`verify-analytics-scope.py --api` passed on the deployed app:

| Profile | Accessible lists | Subscribers | Campaigns |
| --- | --- | ---: | ---: |
| Creative Agency List Admin | 4, 6 | 2 | 1 |
| CAIRN Administrator | 6 | 1 | 1 |
| CAIRN Manager | 6 | 1 | 1 |
| No assigned lists | None | 0 | 0 |
| Global campaign/subscriber permissions with assigned lists | 6 | 1 | 1 |
| All-list access | 1, 3, 4, 5, 6 | 6 | 3 |

Dashboard totals and charts matched each scope. Accessible campaign analytics
matched the super-admin response; forbidden and mixed allowed/forbidden IDs
returned 403 for views, clicks, bounces, and links. All temporary API users and
roles were removed. No emails were sent or real content records modified.

Existing PostgreSQL and upload volumes were preserved. No schema migration,
new AWS service, or paid feature was introduced.

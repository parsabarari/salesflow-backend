# 06 — Architecture Document

**Relation to 01–05:** This document covers two kinds of decisions
deliberately deferred until now: (a) foundational choices that shape
the whole system (multi-tenancy model, storage), most of which were
already implicitly fixed by decisions made in 02–05 and are simply
made explicit here; and (b) infrastructure/deployment concerns
(background jobs, caching, deployment topology) that don't belong in
the PRD, Domain Model, ERD, or API Spec.

---

## 1. Multi-Tenancy Model — confirming an already-made decision

**Shared database, shared schema, row-level isolation via
`organization_id`** — not schema-per-tenant, not database-per-tenant.
This isn't a new decision; it's already baked into every table in
04-erd.md (every tenant-scoped table carries `organization_id` as a
plain foreign key, not a schema name). It's stated explicitly here so
it's not left as an implicit assumption: schema-per-tenant would mean
running Django migrations against N schemas per deploy and would
complicate the cross-tenant-safe generic ContentType relations
(Section 15 of the Domain Model) considerably, for a benefit (stronger
tenant isolation) that isn't needed at the PRD's target scale (Section
3: 5–50 users per org, not thousands of large enterprise tenants each
needing dedicated infrastructure).

Enforcement: every queryset in every view is filtered by the
requester's `organization_id` at the base manager/queryset level (not
left to each individual view to remember), so a missing filter in one
view can't leak cross-tenant data — this is the concrete implementation
of Business Rules 1.1–1.2.

---

## 2. File Storage (resolves the open item from 04-erd.md / 05-api-spec.md)

**Decision: S3-compatible object storage** (AWS S3 in production;
MinIO as the S3-compatible local/dev equivalent, since Docker is
already the stated dev environment — PRD Section 7 NFR), accessed via
`django-storages`. `Attachment.file_reference` (ERD Section 15) stores
the object key; `GET /attachments/{id}` (API Spec Section 10) returns
a short-lived signed URL rather than proxying file bytes through the
Django app.

Reasoning: the PRD commits to Docker-based deployment (Section 7 NFR).
Storing uploaded files on local disk inside a container is fragile
under that deployment model specifically — containers are expected to
be disposable/replaceable, and local files don't survive a container
being recreated or don't work at all once there's more than one web
container behind a load balancer. Object storage is the standard fix
for this exact situation and needs no bespoke reasoning beyond "the
stated deployment model requires it."

---

## 3. Background Jobs (Celery)

Per PRD Section 7 NFR (Celery is already in the stack), the following
async/scheduled jobs are needed — this is the concrete list that
justifies Celery being in the stack at all, since nothing above
required it as a hard technical necessity by itself:

| Job | Trigger | Notes |
|---|---|---|
| Send transactional email | async task, fired on: invitation sent, password reset requested, mention notification (Phase 3) | keeps request/response cycle fast; email delivery shouldn't block the API call that triggered it |
| Activity due-soon / overdue sweep | Celery Beat, every 15 minutes | scans `activities` where `due_date` is within the next 24h or already past and not yet notified (Business Rules 8.3); writes `Notification` rows |
| Invitation expiry sweep | Celery Beat, daily | flips `status` to `expired` on invitations past `expires_at` |

No other async work is currently justified by the PRD's feature set —
this list should be treated as a starting point, not a ceiling; adding
a job later (e.g., a scheduled digest email) is cheap once Celery is
already wired in.

---

## 4. Caching (resolves the open item from 05-api-spec.md)

**Decision: cache `GET /dashboard/summary` per organization, TTL 60
seconds, in Redis** (already in the stack). This endpoint aggregates
across Leads, Tickets, and Activities (PRD 5.10) — at 5–50 users per
org this isn't a heavy query, but it's read far more often than the
underlying data changes meaningfully within a minute, so a short TTL
cache removes repeated aggregation work essentially for free. Cache
key includes `organization_id`; invalidation is time-based only (no
explicit invalidation on writes) — deliberately simple, since a
60-second-stale dashboard number is an acceptable tradeoff for a
sales-team dashboard, not a financial ledger.

**`GET /search` is not cached** — search queries are too varied
(different `q` per request) for a cache to have a meaningful hit rate,
and freshness matters more for search (a rep searching for a lead they
just created shouldn't get a stale miss).

---

## 5. Rate Limiting (resolves the open item from 05-api-spec.md)

Applied only to the unauthenticated endpoints named in API Spec
Section "Open Items," since these are the ones reachable without a
valid session and therefore the only realistic abuse surface:

| Endpoint | Limit |
|---|---|
| `POST /auth/login` | 10 attempts / 15 min per IP + per email combined |
| `POST /auth/password-reset/request` | 5 / hour per email |
| `POST /invitations/{token}/accept` | 10 / hour per token |

Implemented via DRF's throttle classes backed by Redis. No rate
limiting is applied to authenticated endpoints in MVP — the PRD's
target scale (5–50 users per org) doesn't present a realistic internal
abuse scenario, and adding blanket authenticated-endpoint throttling
without a concrete threat to size it against would be arbitrary.

---

## 6. Deployment Topology

Per PRD Section 7 NFR (Docker):

```
docker-compose services:
  web        — Django + DRF (gunicorn), horizontally scalable
  worker     — Celery worker (Section 3 jobs)
  beat       — Celery Beat scheduler (single instance only — running
               more than one Beat process double-fires scheduled jobs)
  redis      — JWT refresh-token blocklist (Business Rules 2.2),
               Celery broker/result backend, dashboard cache (Section 4)
  postgres   — primary datastore
```

`web` is the only service that needs to scale horizontally under load
at this product's target size; `worker`/`beat`/`redis`/`postgres` run
as single instances in MVP, which matches the "production deployment
ready" success criterion (PRD Section 11) without over-provisioning
for a scale the target customer (Section 3) won't reach.

---

## 7. Observability (minimum viable, not tooling-prescriptive)

The PRD's Quality Goals (Section 9) and success criteria (Section 11)
imply the system needs to be operable in production, but don't specify
tools — consistent with the earlier decision (PRD Section 7 note) to
keep specific tool choices out of product-level documents. What *is*
an architectural concern, not a tooling one, is what must be
observable:
- Every AuditLog write (Domain Model Section 17) doubles as a
  security-relevant event trail — no separate logging pipeline is
  required to satisfy that need.
- Celery job failures (Section 3) must surface somewhere an operator
  will see them (specific APM/error-tracking product is an
  implementation choice, left open).
- Standard request logging (status code, latency, org_id) on the `web`
  service for basic operational visibility.

---

## 8. Summary: Decisions Made in This Document

| # | Decision |
|---|---|
| 1 | Shared schema, row-level tenancy via `organization_id` (confirms existing ERD design) |
| 2 | S3-compatible object storage for Attachments, signed URLs |
| 3 | Three Celery jobs: transactional email, due/overdue sweep, invitation expiry sweep |
| 4 | Dashboard summary cached 60s in Redis; Search not cached |
| 5 | Rate limits on the three unauthenticated endpoints only |
| 6 | Docker Compose topology: web (scalable), worker, beat (singleton), redis, postgres |

## Open Items for Implementation Roadmap (07)

None outstanding — every deferred item from 01 through 05 is now
resolved. 07 can proceed as a pure task-breakdown of everything
defined in 01–06.

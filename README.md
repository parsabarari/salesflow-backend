# SalesFlow Backend

A production-grade, multi-tenant CRM SaaS backend built with Django + DRF. Solo-developer project targeting small businesses, agencies, and sales teams (5–50 users per organization). The frontend will be developed separately — this repo is API-only.

Full spec lives in [`docs/`](docs/): product requirements, business rules, domain model, ERD, API spec, and architecture.

## Tech Stack

- **Django 6 + Django REST Framework**
- **PostgreSQL** (with `citext` for case-insensitive emails)
- **Redis** — JWT refresh-token blocklist, Celery broker/backend, dashboard cache
- **Celery + Celery Beat** — background jobs and scheduled sweeps
- **MinIO** (S3-compatible) locally / **AWS S3** in production — file attachments
- **JWT auth** (`djangorestframework-simplejwt`) — access + refresh, refresh blocklisted on logout
- **drf-spectacular** — OpenAPI schema, served via Swagger UI and Scalar
- Docker Compose for local dev (`web`, `worker`, `beat`, `redis`, `postgres`, `minio`)

## Architecture Highlights

- **Multi-tenancy:** shared schema, row-level isolation via `organization_id`, enforced at the manager level (fail-closed — querying without org context raises, doesn't silently return everything).
- **RBAC:** six roles (Owner, Admin, Sales Manager, Sales Agent, Support Agent, Viewer) enforced via queryset-scoping + action-level permission classes, matching the matrix in `docs/01-product-requirements.md` §5.3.
- **Soft delete everywhere** via a single nullable `deleted_at` — no parallel `is_active`/`is_deleted` flags.
- **Polymorphic parents** (Activity, Comment, Attachment, Notification, AuditLog) use Django's `ContentType` framework.
- **Business logic lives in `services.py`**, not views or signals — views stay thin.
- **404, not 403**, for objects outside a requester's visible scope, to avoid leaking existence.

## Project Structure

```
config/              Django project (settings, urls, celery.py)
apps/core/            Abstract base models, org-scoped managers, base permissions
apps/accounts/         User (global identity), JWT auth
apps/organizations/    Organization, Membership, Invitation, RBAC/team logic
apps/leads/            Lead, Tag, LeadStageHistory, pipeline state machine
apps/customers/        Customer, Contact, CustomerLeadLink, Won→Customer matching
apps/tickets/          Ticket
apps/activities/       Activity (Call/Meeting/Task/etc.)
apps/collaboration/    Comment, CommentMention, Attachment
apps/notifications/    Notification
apps/audit/            AuditLog
apps/dashboard/        Aggregated summary endpoint
apps/search/           Global RBAC-scoped search
```

Dependency direction is one-way: `core → audit/notifications → accounts/organizations → customers → leads → tickets → activities/collaboration → dashboard/search`.

## Getting Started

```bash
cp .env.example .env   # fill in real secrets
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml exec web python manage.py migrate
```

API docs: `/api/schema/swagger/` (dark-themed Swagger UI) or `/api/docs/` (Scalar).

### Running tests

```bash
docker compose -f docker/docker-compose.yml exec web python manage.py test --settings=config.settings.test
```

## Project Status

Built in phases per `docs/07-implementation-roadmap.md`:

- ✅ **Phase 1** — Auth, Organizations, RBAC, Leads & Pipeline
- ✅ **Phase 2** — Customers, Activities, Ticketing, Collaboration (Comments + mentions)
- ✅ **Phase 3** — Dashboard, Search, Notifications, Audit Log
- ⬜ **Phase 4** — Rate limiting, deployment hardening, performance pass, observability, soft-delete restore endpoints

Known open items: `?include_archived=true` list filter is deferred; a handful of judgment calls made during implementation (documented inline in code comments) are pending write-up into `docs/02-business-rules.md` by the project owner.

## License

MIT — see [`LICENSE`](LICENSE).

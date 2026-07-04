# AGENTS.md — Project Instructions for AI Coding Agents

## What This Project Is

A multi-tenant CRM SaaS backend (Django + DRF), built by a single
developer with an AI coding agent, targeting small businesses/agencies
(5–50 users per organization). The frontend is developed separately —
this repo is API-only.

**Every product, business-rule, data-model, API, and architecture
decision has already been made and written down in `docs/`.** Your job
in this repo is disciplined implementation of an already-finished
spec, not design. Treat `docs/` as the single source of truth, above
your own training knowledge or defaults.

## Required Reading Before Any Task

```
docs/01-product-requirements.md   — what the product does, scope, roles
docs/02-business-rules.md         — exact rules per entity, all resolved
docs/03-domain-model.md           — entities, fields, relationships
docs/04-erd.md                    — physical schema: types, constraints, indexes
docs/05-api-spec.md               — endpoints, conventions, permissions
docs/06-architecture.md           — infra: storage, caching, Celery, deployment
docs/07-implementation-roadmap.md — the task checklist you are executing
```

**Before writing any code for a task, open and read the specific
section of the specific doc that covers it.** Do not rely on memory of
an earlier conversation turn or on general Django conventions when a
doc gives a concrete answer — the doc wins every time it conflicts with
a general convention.

## Tech Stack (fixed, do not substitute)

Django + DRF, PostgreSQL, Redis, Celery, Docker. JWT auth (access +
refresh, refresh blocklisted in Redis on logout). No GraphQL, no
alternate web framework, no alternate database, regardless of what
seems easier for a given task.

## Folder / App Structure (already decided — do not restructure)

```
config/            — Django project (settings, urls, celery.py)
apps/core/          — abstract base models, shared managers, base permissions
apps/accounts/       — User (global identity)
apps/organizations/  — Organization, Membership, Invitation
apps/leads/          — Lead, Tag, LeadTag, LeadStageHistory
apps/customers/      — Customer, Contact, CustomerLeadLink
apps/tickets/        — Ticket
apps/activities/     — Activity
apps/collaboration/  — Comment, CommentMention, Attachment
apps/notifications/  — Notification
apps/audit/          — AuditLog
apps/dashboard/       — aggregation endpoint only, no models
apps/search/          — search endpoint only, no models
```

Dependency direction is one-way: `core` → `accounts`/`organizations` →
`customers` → `leads` → `tickets` → `activities`/`collaboration` →
`notifications`/`audit` → `dashboard`/`search`. A lower app must never
import from a higher one. `activities` and `collaboration` reach Lead/
Customer/Ticket only through Django's ContentType framework
(`GenericForeignKey`), never a direct import or FK.

Inside every app: `models.py` (data only) / `services.py` (business
logic — this is where rule enforcement lives) / `serializers.py` /
`permissions.py` / `views.py` (thin — validates input, calls a
service, returns) / `tests/`.

## Workflow Rules

1. **One task at a time**, taken directly from
   `docs/07-implementation-roadmap.md`'s checklist. Do not combine
   multiple checklist items into one change, and do not start a task
   from a later phase before the current phase's tasks are done.
2. Every task ends with: migrations applied cleanly, tests written and
   passing, and a single commit whose message references the roadmap
   item (e.g. `feat(leads): stage transition state machine [07 §1.3]`).
3. If a requirement is ambiguous or the docs don't cover a case you've
   hit: **stop and ask**, in prose, quoting the specific gap. Do not
   guess and do not silently pick "a reasonable default" — every
   default in this system was already deliberated on and written down;
   an undocumented one you invent will likely conflict with something
   already decided elsewhere.

## Things You MUST Do

- Enforce `organization_id` scoping via the shared base manager/
  queryset in `apps/core`, on every tenant-scoped query — never write
  a one-off queryset that skips it.
- Use `deleted_at` (nullable timestamp) as the **only** soft-delete
  mechanism, everywhere. No parallel `is_active`/`is_deleted` boolean
  fields alongside it.
- Implement enums as `TextChoices` + a DB `CHECK` constraint, never a
  native Postgres `ENUM` type.
- Return **404**, not 403, when a request targets an object outside
  the requester's RBAC-visible scope (own-only / team-scoped
  resources) — per `docs/05-api-spec.md` §1.5.
- Put every business rule enforcement (stage transitions, Won→Customer
  matching, duplicate checks, RBAC team resolution, etc.) in
  `services.py`, called explicitly from views/tasks — not in Django
  signals, and not inline in a view or serializer.
- Write a test for every rule in `docs/02-business-rules.md` that your
  current task touches, including the edge cases spelled out there
  (e.g. zero/one/many Customer matches on Won; Lost reopenable, Won
  not).
- Use Django's `ContentType` framework for every polymorphic parent
  relation (Activity, Comment, Attachment, Notification, AuditLog
  targets), per `docs/03-domain-model.md` §15.
- Keep `organization_id` in the URL path
  (`/api/v1/organizations/{organization_id}/...`), not a custom header,
  for every tenant-scoped endpoint.

## Things You MUST NOT Do

- Do not invent a business rule, validation, or default value that
  isn't in `docs/02-business-rules.md` or `docs/04-erd.md`. If you
  need one that isn't there, ask instead of assuming.
- Do not add a `POST /customers` (direct Customer-creation) endpoint —
  Customers are only created through the Won-lead flow, by explicit
  design (`docs/02-business-rules.md` §6.4).
- Do not add features, endpoints, or fields from the PRD's "Explicitly
  Out of Scope" list (Section 6): AI, marketing automation, billing,
  public API, mobile app, real-time/WebSockets, complex analytics, bulk
  email campaigns.
- Do not add a testing framework, linter, or formatter choice on your
  own initiative — if one isn't already configured in the repo,
  ask which to use rather than picking one.
- Do not introduce a new third-party package without checking whether
  the existing stack (Section "Tech Stack" above) already covers the
  need.
- Do not touch `docs/*.md` to make the documentation match code you've
  written — if implementation reveals a real gap or contradiction in
  the docs, stop and flag it in prose; don't silently edit the spec.
- Do not restructure the app/folder layout above, even if you think a
  different grouping is cleaner — it was chosen deliberately to keep
  dependency direction one-way (see above).
- Do not implement real-time delivery (WebSockets, polling shortcuts
  that simulate push) for Notifications — the frontend polls a plain
  REST endpoint, by design.
- Do not skip writing tests "to move faster" — a task is not complete
  without them, regardless of how simple the change looks.

## When You're Done With a Task

State plainly: which roadmap item you completed, which doc sections
you implemented against, what you deliberately left out (and why, with
a doc reference), and any open question you hit that needs a human
decision before the next task can safely proceed.

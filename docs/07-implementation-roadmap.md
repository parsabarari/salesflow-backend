# 07 — Implementation Roadmap

**Relation to 01–06 and to PRD Section 10:** The PRD's own Roadmap
(Section 10) states phases at feature level ("Phase 1: Auth,
Organizations, RBAC, Leads, Pipeline"). This document breaks each
phase down into concrete build tasks — models → permissions →
endpoints → background jobs — directly against the entities (03),
tables (04), endpoints (05), and infrastructure (06) already defined.
Nothing here introduces new decisions; it's purely sequencing what's
already been decided.

**Sequencing principle used within each phase:** models/migrations
first, then permissions (since nothing else can be safely tested
without them), then endpoints, then background jobs, then the
cross-entity flows that depend on multiple pieces existing together.

---

## Phase 1 — Auth, Organizations, RBAC, Leads, Pipeline

### 1.1 Foundation
- [ ] `users`, `organizations`, `memberships`, `invitations` models +
      migrations (04-erd.md §1–4)
- [ ] JWT auth wired up: access/refresh pair, Redis-backed refresh
      blocklist (06-architecture.md §1, Business Rules 2.1–2.2)
- [ ] Base queryset manager enforcing `organization_id` filtering at
      the manager level, not per-view (06-architecture.md §1)
- [ ] Auth endpoints: signup, login, logout, refresh, password reset,
      email verification (05-api-spec.md §2)
- [ ] Invitation flow: create, resend, accept (05-api-spec.md §3);
      Celery Beat expiry sweep (06-architecture.md §3)

### 1.2 RBAC
- [ ] Permission classes implementing the full matrix (PRD 5.3):
      queryset-level filtering + action-level checks
      (Business Rules 3.1)
- [ ] `reports_to` "team" resolution logic (Business Rules 3.2)
- [ ] Role-change / member-removal endpoints + AuditLog writes
      (05-api-spec.md §3, Business Rules 3.3)
- [ ] 404-not-403 behavior verified for out-of-scope object access
      (API Spec §1.5)

### 1.3 Leads & Pipeline
- [ ] `leads`, `lead_tags`, `lead_stage_history`, `tags` models +
      migrations (04-erd.md §5–8)
- [ ] Lead CRUD + duplicate-warning logic on create/edit
      (Business Rules 4.3, API Spec §4)
- [ ] Stage-transition endpoint with the full state machine (free
      movement between non-terminal stages, Lost reversible, Won
      terminal, `lost_reason` required) — Business Rules 5.2,
      API Spec §4
- [ ] Lead Timeline read endpoint (aggregates stage history + notes/
      comments/activities once those exist — can return a partial
      view until Phase 2 lands, or be built last in this phase)

### 1.4 Tests for Phase 1
- [ ] Org isolation: cross-org access attempts return 404
- [ ] Each RBAC matrix cell: at least one test per role × resource
      combination in PRD 5.3
- [ ] Every stage-transition rule from Business Rules 5.2 (valid and
      invalid transitions, Lost reopening, Won irreversibility)

---

## Phase 2 — Customers, Activities, Ticketing, Collaboration

### 2.1 Customers
- [ ] `customers`, `contacts`, `customer_lead_links` models +
      migrations (04-erd.md §9–11)
- [ ] Won→Customer linking logic: zero/one/many-match branches
      (Business Rules 5.3), including
      `requires_manual_customer_selection` + `/resolve-customer`
      endpoint (API Spec §4)
- [ ] Company-type "requires ≥1 Contact" service-layer check
      (ERD §9 note)
- [ ] Customer/Contact CRUD (no direct Customer creation endpoint —
      API Spec §6 explicitly excludes it)

### 2.2 Activities
- [ ] `activities` model + migration (04-erd.md §12), ContentType
      parent restricted to Lead/Customer (Business Rules 8.2)
- [ ] Activity CRUD (API Spec §7)
- [ ] Overdue/due-soon Celery Beat sweep writing to Notification
      (06-architecture.md §3) — Notification model itself can be
      built now (Phase 2) even though it's only fully consumed in
      Phase 3, so this sweep has somewhere to write to

### 2.3 Ticketing
- [ ] `tickets` model + migration (04-erd.md §16), `customer_id`
      required
- [ ] Ticket CRUD + status transitions (Business Rules 7.3)
- [ ] Cross-check: Ticket blocked on Leads with
      `requires_manual_customer_selection = true` until resolved
      (Business Rules 7.1)

### 2.4 Collaboration
- [ ] `comments`, `comment_mentions` models + migrations
      (04-erd.md §13–14) — covers Notes/Internal-notes per the
      Domain Model §1 unification decision
- [ ] Comment CRUD restricted to Lead/Customer/Ticket parents
      (Business Rules 9.1)
- [ ] `@mention` parsing on comment creation, writing
      `CommentMention` rows scoped to org members only
      (Business Rules 9.2) — **notification delivery for mentions is
      explicitly Phase 3, not built here** (PRD 5.9 / Roadmap
      cross-reference)
- [ ] `attachments` model + migration (04-erd.md §15), S3-compatible
      storage wiring (06-architecture.md §2)

### 2.5 Tests for Phase 2
- [ ] Won-linking: zero-match, one-match, multi-match branches, each
      with a dedicated test
- [ ] Ticket creation rejected when Customer unresolved
- [ ] Comment/mention parsing: valid member mention, non-member
      mention ignored

---

## Phase 3 — Dashboard, Search, Notifications

- [ ] `notifications` model + migration (04-erd.md §17) if not
      already created in Phase 2 for the Activity sweep
- [ ] Notification triggers wired into every event listed in
      Business Rules 10.3 (Lead assignment/stage change, mention,
      Ticket assignment/status change, Activity due/overdue)
- [ ] Notification endpoints: list, mark-read, mark-all-read
      (API Spec §12)
- [ ] Mention transactional email (Business Rules 9.3 — reads the
      `CommentMention` rows already created back in Phase 2)
- [ ] `GET /dashboard/summary` aggregation endpoint + 60s Redis cache
      (API Spec §11, 06-architecture.md §4)
- [ ] `GET /search` across Leads/Customers/Tickets, RBAC-scoped
      (API Spec §11)
- [ ] `audit-logs` read endpoint, Owner/Admin only (API Spec §13)

### Tests for Phase 3
- [ ] Every notification trigger fires exactly once per event
- [ ] Dashboard numbers match a hand-computed fixture
- [ ] Search results respect RBAC visibility (a Sales Agent's search
      doesn't surface another agent's Leads)

---

## Phase 4 — UX Improvements, Performance, Deployment Hardening

This phase is inherently less specifiable in advance than 1–3 (PRD
Section 10 groups it as post-MVP polish), but the concrete,
already-known items are:

- [ ] Rate limiting on the three unauthenticated endpoints
      (06-architecture.md §5)
- [ ] Production Docker Compose / deployment config finalized
      (06-architecture.md §6)
- [ ] Index/query performance pass against the indexes already
      defined in 04-erd.md — confirm they're actually being used
      (`EXPLAIN ANALYZE` on the heaviest list endpoints)
- [ ] Basic observability wiring (06-architecture.md §7): request
      logging, Celery failure visibility
- [ ] Soft-delete restore endpoints exercised end-to-end for every
      entity that needs them (Business Rules 12.3)

---

## Traceability Check

Every entity in 03-domain-model.md and every table in 04-erd.md
appears in exactly one phase above except `AuditLog`, which is written
to starting in Phase 1 (role changes, member removal) but only
*readable* via its own endpoint in Phase 3 — this is intentional, not
an oversight: the audit trail should start accumulating from the first
privileged action in the system, even before there's a UI to view it.

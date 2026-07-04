# 05 — API Specification

**Relation to 04:** Every endpoint below maps directly onto a table
in 04-erd.md. This document defines URL shape, methods, and the
cross-cutting API conventions (pagination, filtering, errors,
versioning, idempotency) that the PRD's NFRs (Section 7: Pagination,
Filtering, Ordering; Section 9: idempotent endpoints where applicable)
require but didn't specify at implementation level.

**Scope note:** this is an *internal* API — consumed by the
separately-developed frontend (PRD Section 1 Vision), not a
third-party-facing product. "Public API" being Out of Scope (PRD
Section 6) means no external developer access/API-key distribution;
it does not mean the API shouldn't follow normal REST conventions
internally.

---

## 1. Cross-Cutting Conventions

### 1.1 Base path & versioning
`/api/v1/...` — versioned from day one. Versioning cost is close to
zero to add now and expensive to retrofit later once the frontend is
built against unversioned routes.

### 1.2 Authentication
`Authorization: Bearer <access_token>` (JWT, Business Rules Section 2).
`POST /api/v1/auth/refresh` exchanges a valid refresh token for a new
access token. `POST /api/v1/auth/logout` blocklists the refresh token
(Business Rules 2.2).

### 1.3 Pagination
**Decision: `PageNumberPagination`** (`?page=2&page_size=25`, default
page size 25, max 100) rather than cursor-based pagination. Cursor
pagination solves problems (stable pagination under high write
concurrency, very large datasets) that don't apply at the PRD's stated
target scale (Section 3: 5–50 users per organization) — page-number is
simpler to implement and simpler for the frontend to build "page 1 of
N" UI against, which this kind of CRM list view typically wants
anyway.

Response envelope:
```json
{
  "count": 132,
  "next": "/api/v1/leads/?page=3",
  "previous": "/api/v1/leads/?page=1",
  "results": [ ... ]
}
```

### 1.4 Filtering & Ordering
Query params, `django-filter`-style:
- `?field=value` for exact-match filters (e.g. `?stage=won&owner=42`)
- `?ordering=-created_at` (prefix `-` for descending)
- `?search=` for the free-text fields on a given resource, separate
  from Global Search (Section 11 below)

Each resource section lists its specific filterable/orderable fields.

### 1.5 Error format
```json
{
  "error": {
    "code": "validation_error",
    "message": "Human-readable summary",
    "details": { "field_name": ["Specific issue"] }
  }
}
```
Standard HTTP status codes apply (400 validation, 401 unauthenticated,
403 forbidden, 404 not found/not visible, 409 conflict, 422 semantic
validation e.g. invalid stage transition).

**Note on 403 vs. 404** (Business Rules 3.1): for "own only"/"team"
scoped resources, a request for an object outside the requester's
visibility returns **404**, not 403 — a Sales Agent requesting another
agent's Lead by ID must not be able to distinguish "doesn't exist"
from "exists but isn't yours," which 403 would leak.

### 1.6 Idempotency
For POST endpoints with side effects beyond simple row creation
(Lead stage transition to Won, which triggers Customer creation/
linking; Invitation acceptance, which creates a Membership), clients
may send an `Idempotency-Key` header. A repeated request with the same
key returns the original response without re-executing the side
effect. This directly implements the PRD's "idempotent endpoints where
applicable" Quality Goal (Section 9) for exactly the endpoints where
it matters — plain CRUD endpoints don't need it, since a duplicate
`POST /leads` just creates a second Lead (an acceptable, visible
outcome the user controls), whereas a duplicate Won-transition could
silently create a second Customer.

### 1.7 Soft delete at the API layer
`DELETE` on any resource performs a soft delete (sets `deleted_at`).
List endpoints exclude soft-deleted rows by default;
`?include_deleted=true` is available only to Owner/Admin (Business
Rules 12.3). `POST /{resource}/{id}/restore` (Owner/Admin only)
reverses it.

---

## 2. Auth & Users

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/signup` | Creates User + Organization + Owner Membership in one transaction |
| POST | `/auth/login` | Returns access + refresh token |
| POST | `/auth/logout` | Blocklists refresh token |
| POST | `/auth/refresh` | Returns new access token |
| POST | `/auth/password-reset/request` | Sends reset email |
| POST | `/auth/password-reset/confirm` | Sets new password; invalidates all refresh tokens (Business Rules 2.3) |
| POST | `/auth/email/verify` | Confirms `is_email_verified` |
| GET | `/auth/me` | Current User + active Membership/role for the current org context |

---

## 3. Organizations & Members

| Method | Path | Notes |
|---|---|---|
| GET | `/organizations/{id}` | Owner/Admin/Manager full; others read-only per matrix |
| PATCH | `/organizations/{id}` | Owner/Admin only (settings) |
| GET | `/memberships` | filterable by `role`, `is_active` (derived from `deleted_at`) |
| PATCH | `/memberships/{id}` | role change or `reports_to` change — Owner/Admin only; writes an AuditLog row (Business Rules 3.3) |
| DELETE | `/memberships/{id}` | remove member (soft delete); AuditLog row |
| GET | `/invitations` | Owner/Admin |
| POST | `/invitations` | Owner/Admin; enforces the `(organization_id, email) WHERE status='pending'` uniqueness from the ERD |
| POST | `/invitations/{id}/resend` | resets `expires_at` |
| POST | `/invitations/{token}/accept` | public (unauthenticated) endpoint reached via emailed link; idempotent (Section 1.6) |

---

## 4. Leads

| Method | Path | Notes |
|---|---|---|
| GET | `/leads` | filter: `stage`, `owner`, `tags`, `source`, `is_archived`, `created_at__gte/lte`; ordering: `created_at`, `stage` |
| POST | `/leads` | validates email-or-phone (ERD `CHECK`); returns `possible_duplicates` in the response body if any match found (Business Rules 4.3) |
| GET | `/leads/{id}` | 404 if outside requester's visibility (Section 1.5) |
| PATCH | `/leads/{id}` | field edits **excluding** `stage` — stage changes go through the dedicated endpoint below, since they carry side effects and validation a generic PATCH shouldn't silently trigger |
| DELETE | `/leads/{id}` | archive/soft-delete |
| POST | `/leads/{id}/stage` | body: `{ "to_stage": "...", "reason": "..." }`; enforces the transition rules in Business Rules 5.2; idempotency-key supported (Section 1.6) since this is the Won-triggering endpoint |
| GET | `/leads/{id}/timeline` | aggregated read of stage history + notes/comments + activities (Business Rules 8.1/11.2, PRD 8.1) |
| POST | `/leads/{id}/resolve-customer` | body: `{ "customer_id": ... }` — resolves `requires_manual_customer_selection` (Business Rules 5.3.4) by picking one of the previously-returned candidate Customer IDs |
| POST | `/leads/{id}/tags` | attach a Tag |
| DELETE | `/leads/{id}/tags/{tag_id}` | detach |

---

## 5. Tags

| Method | Path | Notes |
|---|---|---|
| GET | `/tags` | org-scoped list |
| POST | `/tags` | Sales Manager+ |

---

## 6. Customers & Contacts

**No `POST /customers`** — per Business Rules 6.4, Customers are only
created through `POST /leads/{id}/stage` (Won). Exposing a direct
creation endpoint would contradict that rule at the API surface, so it
is deliberately absent, not merely undocumented.

| Method | Path | Notes |
|---|---|---|
| GET | `/customers` | filter: `type`; search: `name`, `email` |
| GET | `/customers/{id}` | includes linked Leads via `customer_lead_links` (Business Rules 6.2) |
| PATCH | `/customers/{id}` | edit name/contact info; Company-type Customers still require ≥1 Contact to remain (service-layer check on Contact deletion, ERD Section 9 note) |
| DELETE | `/customers/{id}` | soft delete |
| GET | `/customers/{id}/contacts` | |
| POST | `/customers/{id}/contacts` | |
| PATCH / DELETE | `/contacts/{id}` | |

---

## 7. Activities

| Method | Path | Notes |
|---|---|---|
| GET | `/activities` | filter: `type`, `status`, `assignee`, `due_date__gte/lte`, `parent_type`, `parent_id` (required together — Business Rules 8.2, an Activity always has exactly one parent) |
| POST | `/activities` | body includes `parent_type` (`lead`\|`customer`) + `parent_id`; server resolves the ContentType |
| GET / PATCH / DELETE | `/activities/{id}` | |

---

## 8. Tickets

| Method | Path | Notes |
|---|---|---|
| GET | `/tickets` | filter: `status`, `priority`, `assignee`, `customer` |
| POST | `/tickets` | `customer_id` required (ERD `NOT NULL`); `contact_id` optional and must belong to that customer |
| GET / PATCH / DELETE | `/tickets/{id}` | status transitions validated against the enum in Business Rules 7.3 |

---

## 9. Comments (covers Notes / Internal Notes — see Domain Model Section 1)

| Method | Path | Notes |
|---|---|---|
| GET | `/comments?parent_type=lead&parent_id=123` | `parent_type` restricted to `lead`\|`customer`\|`ticket` (Business Rules 9.1) |
| POST | `/comments` | body includes `parent_type`, `parent_id`, `body`; server parses `@mentions` and writes `CommentMention` rows (Business Rules 9.2) |
| PATCH / DELETE | `/comments/{id}` | author or Owner/Admin only |

---

## 10. Attachments

| Method | Path | Notes |
|---|---|---|
| POST | `/attachments` | multipart upload; `parent_type` restricted to `lead`\|`customer` |
| GET | `/attachments/{id}` | returns a signed URL (storage backend detail deferred to 06-architecture.md) |
| DELETE | `/attachments/{id}` | soft delete |

---

## 11. Search & Dashboard

| Method | Path | Notes |
|---|---|---|
| GET | `/search?q=...` | global search across Leads, Customers, Tickets (PRD 5.12); results scoped to requester's RBAC visibility, not just organization |
| GET | `/dashboard/summary` | lead counts, pipeline overview, conversion rate, open tickets, upcoming activities (PRD 5.10) — a single aggregated read-only endpoint rather than one call per widget, to keep the dashboard fast |

---

## 12. Notifications

| Method | Path | Notes |
|---|---|---|
| GET | `/notifications` | filter: `is_read`; ordering: `-created_at` |
| POST | `/notifications/{id}/read` | |
| POST | `/notifications/read-all` | |

No push/WebSocket delivery (Real-time explicitly Out of Scope, PRD
Section 6) — the frontend polls this endpoint. Polling interval is a
frontend concern, not part of this API spec.

---

## 13. Audit Log

| Method | Path | Notes |
|---|---|---|
| GET | `/audit-logs` | Owner/Admin only (Business Rules 11.1); filter: `action_type`, `actor`, `created_at__gte/lte` |

---

## Open Items for Architecture Document (06)

- Attachment storage backend (local vs. S3-compatible) — referenced
  but deliberately deferred in both the Domain Model (Section 13) and
  ERD (`file_reference` column note).
- Whether `/dashboard/summary` and `/search` need caching given they
  aggregate across multiple tables — a performance concern belonging
  in Architecture, not API shape.
- Rate limiting policy on public/unauthenticated endpoints
  (`/auth/login`, `/invitations/{token}/accept`, `/auth/password-reset/request`).

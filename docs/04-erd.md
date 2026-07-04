# 04 — Database Schema (ERD)

**Relation to 03:** This document turns every entity in
03-domain-model.md into a concrete PostgreSQL table: column types,
keys, constraints, and indexes. Three cross-cutting decisions apply
everywhere below and are made once here rather than repeated per
table:

1. **Enums as `varchar` + `CHECK` constraint, not native Postgres
   `ENUM` types.** Native Postgres enums require `ALTER TYPE ... ADD
   VALUE` (which can't run inside a transaction in older Postgres
   versions and is generally awkward to migrate) every time a new
   status/role value is added. A `varchar` column with a `CHECK`
   constraint (or, at the Django layer, `TextChoices`) is trivial to
   extend via a normal migration. This is a well-established Django/
   Postgres convention, not a stylistic preference.
2. **Soft delete is the single mechanism for "is this record gone,"
   everywhere.** Per Business Rules 12.1, this is always a nullable
   `deleted_at timestamptz`. One correction made while building this
   ERD: the Domain Model listed `Membership.is_active` as a separate
   flag alongside the general soft-delete convention. Having two
   different fields both answering "is this membership gone" invites
   drift (one gets set, the other forgotten) and is exactly the kind
   of inconsistency this whole review process has been catching at
   every stage. **`Membership.is_active` is removed; a removed member
   is simply `deleted_at IS NOT NULL`,** consistent with every other
   entity.
3. **Polymorphic parents (Activity, Comment, Attachment, Notification,
   AuditLog) use Django's `ContentType` framework**
   (`content_type_id` + `object_id`), per Domain Model Section 15.
   The `django_content_type` table itself is framework-managed and
   not listed below.

---

## 1. `users` *(global — no `organization_id`)*

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| email | citext | UNIQUE NOT NULL |
| password_hash | varchar | NOT NULL |
| is_email_verified | boolean | NOT NULL DEFAULT false |
| created_at | timestamptz | NOT NULL DEFAULT now() |

---

## 2. `organizations` *(global)*

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| name | varchar(255) | NOT NULL |
| settings | jsonb | NOT NULL DEFAULT '{}' |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

---

## 3. `memberships`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| user_id | bigint | FK → users, NOT NULL |
| organization_id | bigint | FK → organizations, NOT NULL |
| role | varchar(20) | NOT NULL, CHECK IN ('owner','admin','sales_manager','sales_agent','support_agent','viewer') |
| reports_to_id | bigint | FK → memberships, NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

**Indexes:**
- `UNIQUE (user_id, organization_id) WHERE deleted_at IS NULL`
  (partial — Business Rules 12.2; a removed member can be re-invited
  and get a fresh row without conflicting with the soft-deleted one)
- `INDEX (organization_id, role)`
- `INDEX (reports_to_id)`

**Check:** `reports_to_id` must reference a Membership in the same
`organization_id` — enforced at the service layer (cross-column,
cross-row checks aren't expressible as a simple `CHECK` constraint in
Postgres without a trigger, and a trigger is more complexity than this
single rule warrants at this scale).

---

## 4. `invitations`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| email | citext | NOT NULL |
| role | varchar(20) | NOT NULL, same CHECK list as memberships.role |
| invited_by_id | bigint | FK → memberships, NOT NULL |
| token | varchar(64) | UNIQUE NOT NULL |
| status | varchar(20) | NOT NULL DEFAULT 'pending', CHECK IN ('pending','accepted','expired','revoked') |
| expires_at | timestamptz | NOT NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |

**Indexes:**
- `UNIQUE (organization_id, email) WHERE status = 'pending'` — prevents
  duplicate outstanding invites to the same email within one org.

---

## 5. `tags`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| name | varchar(50) | NOT NULL |
| deleted_at | timestamptz | NULL |

**Indexes:** `UNIQUE (organization_id, name) WHERE deleted_at IS NULL`

---

## 6. `leads`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| owner_id | bigint | FK → memberships, NOT NULL |
| source | varchar(100) | NOT NULL |
| email | citext | NULL |
| phone | varchar(30) | NULL |
| stage | varchar(20) | NOT NULL DEFAULT 'new', CHECK IN ('new','contacted','qualified','proposal','negotiation','won','lost') |
| lost_reason | text | NULL |
| is_archived | boolean | NOT NULL DEFAULT false |
| requires_manual_customer_selection | boolean | NOT NULL DEFAULT false |
| customer_id | bigint | FK → customers, NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

**Constraints:**
- `CHECK (email IS NOT NULL OR phone IS NOT NULL)` — Business Rules
  4.2.
- `CHECK (stage <> 'lost' OR lost_reason IS NOT NULL)` — Lost requires
  a reason, enforced at the DB level, not just the service layer,
  since this is cheap to guarantee and protects data integrity even
  against a future bug in application code.

**Indexes:**
- `INDEX (organization_id, owner_id)` — Sales Agent "own only" queries
- `INDEX (organization_id, stage)` — pipeline/dashboard views
- `INDEX (organization_id, email)`, `INDEX (organization_id, phone)`
  — duplicate-warning and Won-matching lookups (Business Rules 4.3,
  5.3); **not** unique indexes, since duplicates are explicitly
  allowed (non-blocking warning, not a hard constraint).

---

## 7. `lead_tags`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| lead_id | bigint | FK → leads, NOT NULL |
| tag_id | bigint | FK → tags, NOT NULL |

**Indexes:** `UNIQUE (lead_id, tag_id)`

---

## 8. `lead_stage_history` *(append-only — no `deleted_at`, no update/delete exposed at the application layer)*

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| lead_id | bigint | FK → leads, NOT NULL |
| from_stage | varchar(20) | NULL (first row has none) |
| to_stage | varchar(20) | NOT NULL |
| changed_by_id | bigint | FK → memberships, NOT NULL |
| changed_at | timestamptz | NOT NULL DEFAULT now() |
| reason | text | NULL |

**Indexes:** `INDEX (lead_id, changed_at)`

---

## 9. `customers`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| type | varchar(20) | NOT NULL, CHECK IN ('company','individual') |
| name | varchar(255) | NOT NULL |
| email | citext | NULL |
| phone | varchar(30) | NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

**Note:** "company must have ≥1 Contact" (Business Rules 6.1) is not
a column-level constraint — it's a service-layer check at Customer-
creation time (which, per Business Rules 6.4, only happens through
the Won-lead flow, a single controlled code path, making a DB-level
constraint unnecessary overhead here).

**Indexes:** `INDEX (organization_id, email)`,
`INDEX (organization_id, phone)` — used by Won-matching (Business
Rules 5.3, 6.3), not unique (a Customer's own contact info isn't
required to be globally unique across the org, only used as one of
several signals for matching).

---

## 10. `contacts`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| customer_id | bigint | FK → customers, NOT NULL |
| name | varchar(255) | NOT NULL |
| email | citext | NULL |
| phone | varchar(30) | NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

**Indexes:** `INDEX (customer_id)`, `INDEX (email)`, `INDEX (phone)`
(same non-unique matching-lookup rationale as `customers`)

---

## 11. `customer_lead_links`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| customer_id | bigint | FK → customers, NOT NULL |
| lead_id | bigint | FK → leads, NOT NULL |
| linked_at | timestamptz | NOT NULL DEFAULT now() |

**Indexes:** `UNIQUE (lead_id)` — a Lead links to exactly one Customer
(Domain Model Section 9.1); `INDEX (customer_id)` for the reverse
lookup ("all leads that won this customer").

---

## 12. `activities`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| type | varchar(20) | NOT NULL, CHECK IN ('call','meeting','follow_up','task','reminder') |
| parent_content_type_id | integer | FK → django_content_type, NOT NULL |
| parent_object_id | bigint | NOT NULL |
| assignee_id | bigint | FK → memberships, NOT NULL |
| due_date | timestamptz | NOT NULL |
| status | varchar(20) | NOT NULL DEFAULT 'pending', CHECK IN ('pending','completed','cancelled') |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

**Constraint:** `parent_content_type_id` restricted at the service
layer to `Lead` or `Customer` only (Business Rules 8.2) — Django's
ContentType framework doesn't support a DB-level CHECK against a set
of allowed content types, so this is validated in the serializer/
service layer, matching the "business logic in services" Quality Goal
(PRD Section 9).

**Indexes:** `INDEX (parent_content_type_id, parent_object_id)`,
`INDEX (assignee_id, due_date)` — for the overdue-notification sweep
(Business Rules 8.3).

---

## 13. `comments`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| parent_content_type_id | integer | FK → django_content_type, NOT NULL |
| parent_object_id | bigint | NOT NULL |
| author_id | bigint | FK → memberships, NOT NULL |
| body | text | NOT NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

Allowed parent types restricted to Lead / Customer / Ticket at the
service layer (Business Rules 9.1), same rationale as `activities`
above.

**Indexes:** `INDEX (parent_content_type_id, parent_object_id,
created_at)` — feeds both the Lead Timeline and direct comment-thread
views.

---

## 14. `comment_mentions`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| comment_id | bigint | FK → comments, NOT NULL |
| mentioned_membership_id | bigint | FK → memberships, NOT NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |

**Indexes:** `INDEX (mentioned_membership_id, created_at)` — Phase 3
notification consumption reads this.

---

## 15. `attachments`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| parent_content_type_id | integer | FK → django_content_type, NOT NULL |
| parent_object_id | bigint | NOT NULL |
| uploaded_by_id | bigint | FK → memberships, NOT NULL |
| file_reference | varchar(500) | NOT NULL — storage key/path; backend TBD in 06-architecture.md |
| original_filename | varchar(255) | NOT NULL |
| file_size_bytes | bigint | NOT NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

Allowed parent types restricted to Lead / Customer at the service
layer (Domain Model Section 13 — Tickets don't have Attachments per
PRD 5.8).

---

## 16. `tickets`

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| customer_id | bigint | FK → customers, NOT NULL |
| contact_id | bigint | FK → contacts, NULL |
| subject | varchar(255) | NOT NULL |
| priority | varchar(20) | NOT NULL DEFAULT 'medium', CHECK IN ('low','medium','high','urgent') |
| status | varchar(20) | NOT NULL DEFAULT 'open', CHECK IN ('open','in_progress','resolved','closed','reopened') |
| assignee_id | bigint | FK → memberships, NULL |
| created_by_id | bigint | FK → memberships, NOT NULL |
| created_at | timestamptz | NOT NULL DEFAULT now() |
| deleted_at | timestamptz | NULL |

**Constraint:** if `contact_id` is set, its `customer_id` must match
this row's `customer_id` — service-layer check (cross-table
consistency, not a plain column constraint).

**Indexes:** `INDEX (organization_id, assignee_id)`,
`INDEX (organization_id, status)`, `INDEX (customer_id)`

---

## 17. `notifications` *(no `deleted_at` — see Domain Model Section 16)*

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| recipient_membership_id | bigint | FK → memberships, NOT NULL |
| type | varchar(40) | NOT NULL, CHECK IN ('lead_assigned','lead_stage_changed','comment_mention','ticket_assigned','ticket_status_changed','activity_due_soon','activity_overdue') |
| related_content_type_id | integer | FK → django_content_type, NOT NULL |
| related_object_id | bigint | NOT NULL |
| is_read | boolean | NOT NULL DEFAULT false |
| created_at | timestamptz | NOT NULL DEFAULT now() |

**Indexes:** `INDEX (recipient_membership_id, is_read, created_at)` —
the primary "unread notifications for me" query.

---

## 18. `audit_logs` *(append-only — no `deleted_at`, no update/delete exposed)*

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PK |
| organization_id | bigint | FK → organizations, NOT NULL |
| actor_membership_id | bigint | FK → memberships, NOT NULL |
| action_type | varchar(40) | NOT NULL, CHECK IN ('member_invited','member_removed','role_changed','org_settings_changed','ownership_transferred','hard_deleted','restored') |
| target_content_type_id | integer | FK → django_content_type, NOT NULL |
| target_object_id | bigint | NOT NULL |
| metadata | jsonb | NOT NULL DEFAULT '{}' |
| created_at | timestamptz | NOT NULL DEFAULT now() |

**Indexes:** `INDEX (organization_id, created_at)`

---

## 19. Cross-Cutting Notes

- **Every tenant-scoped table's `organization_id` should, in the ERD's
  physical implementation, also be validated as matching the parent
  object's `organization_id`** wherever a row references another
  tenant-scoped row (e.g., a Ticket's `customer_id` must point to a
  Customer in the *same* `organization_id` as the Ticket). This is
  the concrete, table-level expression of Business Rules 1.1–1.2 and
  is enforced at the service layer (Django `clean()`/service methods)
  rather than as a SQL-level constraint, since Postgres doesn't
  support cross-table composite foreign keys of this shape without
  denormalizing `organization_id` onto every join, which isn't worth
  the complexity at this scale.
- **All partial unique indexes filter on `deleted_at IS NULL`**
  consistently (Business Rules 12.2) — `memberships`, `tags`.
  (`leads`, `customers`, `contacts` intentionally have **no** unique
  constraint on email/phone at all — see their sections above — so
  there's nothing to make partial there.)
- No table above uses a native Postgres `ENUM` type, per the
  cross-cutting decision at the top of this document.

---

## Open Items for API Specification (05)

None outstanding from 02/03 — this schema fully implements every
resolved business rule. The only things still open are pure API-layer
concerns (URL shape, pagination style, error format) which belong in
05, not here.

# 02 — Business Rules

**Status:** Resolved. All open items from the previous draft have been
decided below, each with the reasoning behind it (established
convention, or a rule directly implied by an existing decision in
01-product-requirements.md). None of these decisions change or
contradict anything already agreed in the PRD — they fill in the
detail the PRD didn't specify.

**Relation to 01-product-requirements.md:** The PRD's Section 8 states
the business rules at product level (what must be true). This document
goes one level deeper — for every entity, it defines the exact states,
transitions, validations, and enforcement logic needed to build the
Domain Model (03) and ERD (04).

---

## 1. Organization & Multi-Tenancy

1.1. Every tenant-scoped resource (Lead, Customer, Contact, Ticket,
     Activity, Comment, Attachment) carries an `organization_id` and
     is invisible to any request not authenticated within that
     organization.

1.2. There is no cross-organization reference of any kind — not even
     read-only. A Lead in Org A can never reference a Customer in Org
     B, at the database constraint level (foreign keys scoped within
     the same `organization_id`), not just at the query-filter level.

1.3. **Decision: a single user account can belong to multiple
     organizations.** This is the standard multi-tenant SaaS pattern
     (Slack, Notion, Asana all work this way): one email/account, a
     separate `Membership(user, organization, role)` row per
     organization the user belongs to. The alternative (one account
     tied to exactly one org) would force people who work across
     multiple client organizations — plausible for the "agencies,
     consultants" target customer in PRD Section 3 — to create
     duplicate accounts per email, which is worse UX and not how any
     comparable product behaves.

1.4. Deleting (soft-deleting) an Organization cascades a soft-delete
     to all its resources; it does not hard-delete any child records.

---

## 2. Authentication & Session

2.1. JWT pair: access token (short-lived) + refresh token
     (longer-lived), per PRD Section 5.1.

2.2. Logout blocklists the refresh token in Redis with a TTL equal to
     its remaining validity. A blocklisted refresh token cannot mint
     new access tokens.

2.3. **Decision: password reset invalidates all existing refresh
     tokens for that user**, forcing re-login on every device. This
     is the standard OWASP-recommended behavior for any credential
     reset flow — if a password reset happens because credentials
     were compromised, leaving old sessions alive would defeat the
     purpose of the reset.

2.4. **Decision: unverified users can log in, but all write actions
     (creating/editing Leads, Customers, Tickets, etc.) are blocked
     until email is verified.** Read access is not blocked. This
     "soft block" is the common convention (GitHub, most B2B SaaS)
     — it avoids locking a brand-new signup out entirely while still
     making sure the verified-email guarantee (used for password
     reset delivery, notifications, etc.) actually holds before
     anyone can create real data.
     - **Exception:** invited members (PRD 5.1 "Invitation-based
       member onboarding") are considered verified automatically upon
       accepting the invite, since clicking a link sent to their
       email already proves mailbox ownership. Explicit email
       verification only applies to the self-signup flow (the user
       who creates a new Organization as Owner).

2.5. **Decision: invitations expire after 7 days.** Common default
     across SaaS products; re-sendable by an Admin/Owner if expired.

---

## 3. RBAC & Permission Enforcement

3.1. The Permission Matrix in PRD Section 5.3 is the source of truth.
     Enforcement happens at two layers, both required:
     - **Queryset-level filtering**: "Own only" and "Read (team)"
       rows filter the queryset itself (e.g., a Sales Agent's Lead
       list endpoint only ever queries `WHERE owner = request.user`),
       not just at the serializer/permission-check level. This
       prevents ID-guessing attacks (a Sales Agent requesting
       `/leads/123/` for a lead they don't own must get 404, not 403,
       to avoid confirming the lead exists).
     - **Action-level permission classes**: Create/Update/Delete
       checks per role, as defined in the matrix.

3.2. **Decision: "team" is a flat, one-level manager relationship,
     not a full Team entity.** A `Membership.reports_to` field
     (self-referencing FK to another Membership in the same
     organization) is added. "Team" for a Sales Manager = every
     Membership whose `reports_to` points to them, one level deep
     (no recursive multi-level hierarchies). This is the right-sized
     choice for the stated target customer (PRD Section 3: 5–50
     users) — a full multi-level Team/hierarchy object is the kind of
     complexity the PRD's Section 6 (Out of Scope) already steers
     away from ("Complex analytics", general over-engineering), and a
     flat one-level structure is sufficient for a 5–50 person sales
     org.

3.3. Changing a user's role is an Org-Settings-level action (Owner/
     Admin only per the matrix) and generates an audit event
     (Section 11, below).

3.4. A user can never elevate their own role. Only Owner/Admin can
     change roles, and an Admin cannot promote themselves or anyone
     to Owner (ownership transfer is explicitly excluded from Admin's
     permissions per PRD 5.3).

---

## 4. Lead Lifecycle

### 4.1 Lead States
`Active` → `Archived` (soft-deleted / manually archived by user, per
PRD 5.4 "Archive lead") — independent of Pipeline Stage (Section 5
below). An Archived lead is excluded from default list views and from
duplicate/matching logic (per PRD Section 7 soft-delete rule) but its
history remains intact.

### 4.2 Required Fields at Creation
- Owner (mandatory per PRD Business Rule 3).
- Source.
- **Decision: at least one of email or phone is required.** Without
  contact info, neither the Duplicate Warning (4.3) nor the
  Won→Customer matching (Section 5.3, which implements PRD Business
  Rule 5) has anything to match against — making these two rules,
  which the PRD explicitly requires, unenforceable for that Lead.
  Requiring a contact method at creation is also standard practice
  for any CRM lead-capture flow.

### 4.3 Duplicate Warning Logic (deepens PRD 5.4)
- Trigger: on Lead creation, or on email/phone edit of an existing
  Lead.
- Match scope: other **Active** (non-archived, non-soft-deleted)
  Leads in the same organization.
- **Decision: matching is normalized, not raw-string exact match.**
  Email is lowercased and trimmed; phone numbers are stripped of
  spaces, dashes, and parentheses before comparison. Raw exact-match
  would miss trivially-different formatting of the same contact
  (`+1 (555) 123-4567` vs `5551234567`), which would make the
  duplicate warning unreliable in practice — normalization is the
  correct and conventional approach for this kind of check.
- Non-blocking: response includes `possible_duplicates: [lead_id,...]`.
  No database-level unique constraint on email/phone for Leads.

### 4.4 Ownership Reassignment
- Any user with "Full" or "Full (team)" Lead permission (Owner,
  Admin, Sales Manager for their team) can reassign a Lead's owner.
- Reassignment triggers a Notification to the new owner (PRD 5.11)
  and an entry in the Lead Timeline (PRD 8.1) — not the Audit Log,
  since this is routine sales activity, not an administrative action.

---

## 5. Sales Pipeline (Stage State Machine)

### 5.1 Stages
`New → Contacted → Qualified → Proposal → Negotiation → Won`
`Lost` (terminal, reachable from any non-terminal stage)

### 5.2 Transition Rules

**Decision: movement between non-terminal stages (New, Contacted,
Qualified, Proposal, Negotiation) is free in either direction,
including skipping stages.** A Lead can move directly from New to
Proposal, or from Negotiation back to Qualified. This matches how
virtually every mainstream pipeline CRM actually works (Pipedrive,
HubSpot, Salesforce kanban boards all allow free drag-and-drop between
any non-terminal stage) — real sales activity doesn't move in a
strictly rigid line, and deals genuinely do cool off and regress. A
hard forward-only restriction would fight normal sales usage patterns
rather than support them, so the more permissive, more common
convention is used here.

- **Lost** is reachable from any non-terminal stage and requires a
  `lost_reason` (explicit PRD rule).
- **Won** is terminal and irreversible: once a Lead is Won, no further
  stage changes are permitted, because Won triggers Customer creation/
  linking (Section 5.3), a side effect that must not be silently
  undone by moving the Lead back later. If a Won deal genuinely needs
  to be corrected, that is a data-correction operation for an
  Owner/Admin outside the normal stage-transition flow, not a regular
  stage change.
- **Lost is reversible**: a Lost Lead can be moved back to any
  non-terminal stage ("reactivating" a lost deal). This is standard
  CRM behavior and safe to allow, because Lost has no side effect to
  undo (unlike Won) — reopening it is just a normal stage change like
  any other.
- Every transition (including into/out of Lost) writes an immutable
  row to Stage History: `(lead_id, from_stage, to_stage, changed_by,
  changed_at, reason [nullable except required when to_stage=Lost])`.

### 5.3 Won → Customer Linking (deepens PRD Business Rule 5)
Executed as a single transaction when a Lead transitions to Won:

1. Search for matching Customer/Contact within the same organization
   by normalized (Section 4.3 rule) email or phone, excluding
   soft-deleted records (PRD Section 7).
2. **Zero matches** → create a new Customer from the Lead's data,
   link the Lead to it.
3. **Exactly one match** → link the Lead to that existing Customer.
4. **More than one match** → do not link automatically; set
   `requires_manual_customer_selection = true` on the Lead, return
   candidate Customer IDs in the API response. The stage transition
   to Won still succeeds (matches PRD's non-blocking pattern) — the
   Lead is Won, just not yet definitively linked.
5. Until step 4 is resolved by a human, the Lead behaves as Won for
   pipeline/reporting purposes but cannot yet be used to open a
   Ticket (Section 7 below), since Ticketing requires a resolved
   Customer link.

---

## 6. Customer & Contact

6.1. A Customer is either `type = company` or `type = individual`
     (PRD 5.6 "Company or individual").
     **Decision: for `type = individual`, contact info (email/phone)
     lives directly on the Customer record; a separate Contact is
     optional, not required.** For `type = company`, at least one
     Contact is required (a company itself doesn't have a personal
     email/phone to act as the primary point of contact). This
     mirrors the well-established Person-Account vs. Business-Account
     distinction used by mainstream CRMs (e.g. Salesforce), and avoids
     forcing a pointless extra Contact row for the common case of an
     individual freelancer/consultant Customer.

6.2. A Customer can accumulate links from multiple Won Leads over
     time (PRD 5.6). Each link is recorded, not overwritten — i.e., a
     Customer has a *history* of which Leads won it business, not
     just a single `originating_lead_id`.

6.3. Matching (used in Section 5.3 above) checks:
     - The Customer's own primary email/phone (individual type, or
       optionally set on a company type too), AND
     - Any Contact's email/phone currently linked to that Customer.
     Soft-deleted Customers and Contacts are excluded (PRD Section 7).

6.4. **Reconfirmed: Customers are never created directly outside the
     Won-lead pathway in MVP scope.** This was a deliberate scope
     decision already made in v3 of the PRD (see PRD Changelog v2→v3)
     specifically to keep MVP scope tight; nothing in this
     business-rules pass changes that decision — it's restated here
     only so the Domain Model doesn't need to build a
     direct-Customer-creation endpoint.

---

## 7. Ticketing

7.1. A Ticket's `customer_id` (or `contact_id`) is required at
     creation — no Ticket can exist without a resolved Customer link
     (PRD 5.8). This also means a Lead with
     `requires_manual_customer_selection = true` (Section 5.3.4
     above) cannot have a Ticket opened against it until resolved.

7.2. Ticket assignment follows the same "Own only" vs. "Full
     (assigned/team)" split as Leads (PRD 5.3 matrix) — a Support
     Agent sees only tickets assigned to them or their team, per the
     matrix.

7.3. **Decision: Ticket status enum is `Open → In Progress → Resolved
     → Closed`, with `Reopened` allowed from `Resolved` or `Closed`
     back to `Open`.** This four-status-plus-reopen model is the
     standard lightweight ticketing pattern (Zendesk, Freshdesk, and
     effectively every helpdesk tool use some variant of this) and
     matches the "Lightweight" framing already used in PRD Section
     5.8's heading.

---

## 8. Activities

8.1. **Decision: Activity status enum is `Pending → Completed`, plus
     `Cancelled` (reachable only from `Pending`).** This is the
     minimal standard set needed to support the Dashboard's "Upcoming
     activities" and the overdue-notification trigger (PRD 5.11)
     without over-modeling; more granular statuses aren't needed by
     any stated MVP feature.

8.2. **Decision: an Activity must link to exactly one parent — either
     a Lead or a Customer, never both, never neither.** This is
     required, not optional, because the Lead Timeline (PRD 5.4,
     8.1) is explicitly defined as including "Activities logged"
     against that Lead — an unlinked/standalone personal-task Activity
     would have nowhere to appear and would effectively be a generic
     task-manager feature, which is outside what Section 5.7 defines
     ("Activities" are scoped as CRM activities tied to sales
     entities, not a general to-do app).

8.3. **Decision: the "approaching due date" notification (PRD 5.11)
     fires once, 24 hours before the due date, plus once when the
     Activity becomes overdue** (not repeatedly). A single 24-hour
     heads-up plus a single overdue alert is the common default for
     this kind of reminder and avoids notification spam, which the
     PRD's overall "in-app only, lightweight" framing for
     Notifications (5.11) implies should stay minimal.

---

## 9. Collaboration (Comments & Mentions)

9.1. **Decision: Comments can attach to a Lead, a Customer, or a
     Ticket** — the three entities the Permission Matrix (PRD 5.3)
     already lists a "Comments" column for. Activities are not
     commentable in MVP (no stated need, and the matrix doesn't
     define Comment permissions in an Activities context).

9.2. Mention parsing (Phase 2) stores a `CommentMention(comment_id,
     mentioned_user_id)` row per `@user` found in the comment body,
     scoped to organization members only (a mention of a
     non-member/non-existent username is not stored as a valid
     mention).

9.3. The notification side (Phase 3, per PRD 5.9) reads these stored
     `CommentMention` rows retroactively when Notifications ships —
     meaning Phase 2 must still create the rows even though nothing
     consumes them yet, so Phase 3 doesn't need a data-backfill step.

---

## 10. Notifications (deepens PRD 5.11)

10.1. Every notification row: `(recipient_id, type, related_object_type,
      related_object_id, is_read, created_at)`.

10.2. A user is only notified for events on resources they can
      already see per RBAC (Section 3) — e.g., a Sales Agent is never
      notified about another agent's Lead reassignment, even if some
      other trigger condition is technically met.

10.3. Notification triggers list, restated from PRD 5.11 with owning
      logic clarified:
      - Lead assigned/reassigned → notify new owner only.
      - Lead stage changed → notify current owner only (not previous
        owner if reassigned in the same transaction).
      - Comment @mention → notify each mentioned user (in-app now;
        email added in Phase 3).
      - Ticket assigned → notify new assignee only.
      - Ticket status changed → notify assignee AND the ticket
        creator's owning Sales rep if different (per PRD wording
        "assignee and ticket creator's owner").
      - Activity due/overdue → notify the Activity's assignee only.

---

## 11. Audit Log vs. Lead Timeline (restates PRD 8.1)

11.1. **Decision: the Audit Log records exactly the following action
      types** (a definitive, closed list rather than an open-ended
      one, since an unbounded "log everything important" definition
      is not implementable):
      - Member invited / removed / role changed.
      - Organization settings changed.
      - Ownership transferred.
      - Any hard/permanent delete (as opposed to soft-delete).
      - Any restore from soft-delete (Section 12.3).
      This set covers every action already called "important"
      elsewhere in the PRD (Section 7 NFR, Section 8 Rule 6) without
      overlapping the Lead Timeline's day-to-day sales content.

11.2. **Lead Timeline** — per-lead, aggregates: Notes, Stage changes,
      Activities logged against that Lead, Comments on that Lead.
      Read from the same underlying event tables via a query, not
      written twice.

---

## 12. Soft Delete (deepens PRD Section 7)

12.1. Soft-deleted records get `deleted_at` (nullable timestamp,
      null = active). No `is_deleted` boolean — timestamp also
      answers "when."

12.2. All uniqueness constraints (member email per org, etc.) and all
      matching logic (Section 5.3, Section 6.3 above) are implemented
      as **partial indexes / filtered queries with `deleted_at IS
      NULL`**, so a soft-deleted record never blocks new valid data
      or gets incorrectly matched.

12.3. Default querysets exclude soft-deleted rows everywhere; an
      explicit `include_deleted=true` flag (Owner/Admin only, for
      audit or recovery purposes) is required to see them.
      **Decision: a restore capability is included in MVP** — Owner/
      Admin can restore a soft-deleted record (sets `deleted_at` back
      to null). The entire stated purpose of soft-delete over hard
      delete (PRD Section 7) is recoverability plus audit trail; a
      soft-delete without any restore path only delivers the audit
      half of that purpose, and restoring is a trivial operation
      (single field update) once `deleted_at` already exists — there
      is no meaningful cost reason to leave it out.

---

## Summary: Decisions Made in This Pass

| # | Item | Decision | Section |
|---|---|---|---|
| 1 | Multi-organization membership | Allowed — standard multi-tenant pattern | 1.3 |
| 2 | Password reset session invalidation | All refresh tokens revoked | 2.3 |
| 3 | Unverified email + write actions | Writes blocked until verified; invited members auto-verified | 2.4 |
| 4 | Invitation expiry | 7 days | 2.5 |
| 5 | Team/reports-to structure | Flat one-level `reports_to` field, no Team entity | 3.2 |
| 6 | Lead requires email or phone | Required at creation | 4.2 |
| 7 | Exact vs. normalized duplicate match | Normalized (case/whitespace/format-insensitive) | 4.3 |
| 8 | Pipeline stage skipping/backward movement | Free movement between non-terminal stages | 5.2 |
| 9 | Reopening Won/Lost leads | Won is irreversible; Lost is reversible | 5.2 |
| 10 | Individual Customer contact structure | Contact info on Customer directly; Contact optional | 6.1 |
| 11 | Direct Customer creation | Still excluded from MVP (reconfirmed, no change) | 6.4 |
| 12 | Ticket status enum | Open → In Progress → Resolved → Closed (+ Reopened) | 7.3 |
| 13 | Activity status enum | Pending → Completed / Cancelled | 8.1 |
| 14 | Activity parent requirement | Exactly one: Lead XOR Customer, required | 8.2 |
| 15 | "Approaching due" notification window | 24h before, once overdue | 8.3 |
| 16 | Commentable entity types | Lead, Customer, Ticket | 9.1 |
| 17 | Audit Log action-type list | Closed list of 5 action types (Section 11.1) | 11.1 |
| 18 | Restore from soft-delete | Included in MVP, Owner/Admin only | 12.3 |

All 18 items from the previous draft are now resolved and ready to
carry into the Domain Model (03).

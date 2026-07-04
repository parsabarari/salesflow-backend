# Product Requirements Document (PRD)

# Project: CRM SaaS (Solo Backend Edition) — v5

## 1. Vision

A production-grade multi-tenant CRM designed to be built by a single
backend developer using Django and DRF, with the frontend developed
separately. The scope prioritizes clean architecture and realistic
business value over feature count.

## 2. Goals

-   Demonstrate production backend engineering.
-   Build a product that could realistically be sold to small and medium
    businesses.
-   Keep **Phase 1 + Phase 2 (MVP scope, see Roadmap)** achievable in
    3–4 months of part-time work. Phases 3–4 are post-MVP iterations
    and are not part of the 3–4 month estimate.

## 3. Target Customers

Small businesses, agencies, consultants and sales teams (5–50 users).

## 4. User Roles

-   Owner
-   Admin
-   Sales Manager
-   Sales Agent
-   Support Agent
-   Viewer

**Note:** All six roles are retained for MVP. The permission matrix
below (Section 5.3) must be finalized *before* implementation starts.
If, once the matrix is written out, two roles turn out to have
identical permissions across all resources, they should be merged —
but that is a decision to make *after* the matrix exists, not before.

## 5. Product Scope (MVP)

### 5.1 Authentication

-   Login / Logout
-   JWT authentication — access token (short-lived) + refresh token
    (longer-lived). Logout is implemented as a real server-side
    invalidation: the refresh token is blocklisted in Redis (with a
    TTL matching its remaining lifetime), not just discarded
    client-side. Access tokens are short-lived enough that they are
    not individually blocklisted — they simply expire.
-   Password reset
-   Email verification
-   Invitation-based member onboarding

### 5.2 Organization

-   Multi-tenant organizations
-   Members
-   Workspace settings

### 5.3 RBAC

-   Built-in roles (see Section 4)
-   Object ownership
-   Organization isolation
-   **Permission Matrix (required before implementation):** a table
    must be produced mapping each role × each resource (Lead,
    Customer, Ticket, Activity, Comment, Organization Settings,
    Member Management) to allowed actions (Create / Read own / Read
    team / Update / Delete / Archive). Suggested starting shape:

| Role | Leads | Customers | Tickets | Activities | Comments | Pipeline stage change | Org settings / Members |
|---|---|---|---|---|---|---|---|
| Owner | Full | Full | Full | Full | Full | Full | Full |
| Admin | Full | Full | Full | Full | Full | Full | Full (except ownership transfer) |
| Sales Manager | Full (team) | Full (team) | Read | Full (team) | Full (team) | Full (team) | Read |
| Sales Agent | Own only | Read (own leads' customers) | — | Own only | Own leads/customers | Own leads only | — |
| Support Agent | — | Read | Full (assigned/team) | Own only (ticket-related) | Ticket-related | — | — |
| Viewer | Read-only (team) | Read-only (team) | Read-only (team) | Read-only (team) | Read-only (team) | — | — |

  This matrix is a starting draft, not final — it must be reviewed and
  confirmed before coding begins.

### 5.4 Lead Management

-   Create/Edit/Archive lead
-   Tags
-   Source
-   Owner
-   Notes
-   Attachments
-   Timeline (Lead-specific event feed — see Section 8.1 for scope)
-   Duplicate warning (email/phone):
    -   Non-blocking: shown as a warning at creation time, does not
        prevent the user from saving the lead.
    -   The API response on creation includes a `possible_duplicates`
        field listing matching lead IDs so the frontend can render
        the warning; it is the client's decision to proceed or not.

### 5.5 Sales Pipeline

Stages: New → Contacted → Qualified → Proposal → Negotiation → Won /
Lost

Rules:
- Every stage change is logged (immutable stage history).
- Lost reason required.
- Won creates or links to a Customer (see Business Rule 5 in Section 9).

### 5.6 Customer

-   Company or individual
-   Contacts
-   Notes
-   Files
-   Activity history
-   A Customer can have multiple Leads associated with it over time
    (e.g., upsell/repeat business), but every Lead→Customer link is
    still established only through a Lead reaching the Won stage —
    see Section 9, Rule 5.

### 5.7 Activities

-   Call
-   Meeting
-   Follow-up
-   Task
-   Reminder
-   Due date
-   Status

### 5.8 Ticketing (Lightweight)

-   Customer support tickets
-   Priority
-   Status
-   Assignment
-   Internal notes
-   **Tickets attach only to a Customer (or a Contact belonging to a
    Customer) — never directly to a Lead.** A Lead must first convert
    to a Customer (via Won stage) before a support ticket can be
    opened against it. This keeps the support workflow scoped to
    confirmed customers, consistent with Section 3 target customers.

### 5.9 Collaboration

-   Comments — ship in Phase 2 (MVP core) alongside Customers/
    Activities/Ticketing (Section 10). Plain comments (no mention
    parsing, no notification) work standalone and do not depend on
    the notification system.
-   @Mentions — the mention *parsing* (detecting `@user` in a comment
    and storing the reference) ships in Phase 2 with Comments. The
    *notification* side of a mention (in-app alert + transactional
    email, Section 5.11) ships in Phase 3 together with the rest of
    the Notifications system, since it depends on that
    infrastructure. In Phase 2, a mentioned user can still see who
    was tagged by opening the comment thread; they just aren't
    proactively alerted until Phase 3. This keeps Phase 2 free of a
    dependency on unbuilt infrastructure while still delivering
    Collaboration incrementally.
-   Once live (Phase 3), the mention notification is a single
    transactional email to the mentioned user — a one-to-one email,
    not a marketing/campaign email, so it does not fall under the
    "Email campaign system" exclusion in Section 6. This avoids the
    dependency on real-time infrastructure (WebSockets), which
    remains explicitly out of scope, while still making mentions
    functionally useful without requiring the user to poll or
    refresh.

### 5.10 Dashboard

-   Lead counts
-   Pipeline overview
-   Conversion rate
-   Open tickets
-   Upcoming activities

### 5.11 Notifications (in-app only, except the mention email above)

Triggering events:
-   Lead assigned/reassigned to a user
-   Lead stage changed (notify lead owner)
-   Comment @mention (in-app + email, see 5.9)
-   Ticket assigned to a user
-   Ticket status changed (notify assignee and ticket creator's owner)
-   Activity due date approaching / overdue (notify assignee)

### 5.12 Search & Filters

-   Global search
-   Filter by owner, status, tags, dates

## 6. Explicitly Out of Scope

-   AI
-   Marketing automation
-   Accounting
-   ERP
-   Billing & subscriptions
-   Public API
-   Mobile app
-   Real-time collaboration (WebSockets, live cursors, etc.)
-   Complex analytics
-   Email campaign system (bulk/marketing email — does not include the
    single transactional mention email defined in 5.9)

## 7. Non-functional Requirements

-   Django + DRF
-   PostgreSQL
-   Redis
-   Celery
-   Docker
-   OpenAPI docs
-   Pagination
-   Filtering
-   Ordering
-   Audit log (see Section 8.1 for scope vs. Lead Timeline)
-   Soft delete — soft-deleted records must not block valid new data
    or duplicate-matching logic. Concretely: uniqueness checks and
    database indexes (e.g. PostgreSQL partial unique indexes) must
    filter out soft-deleted rows, so a soft-deleted member's email,
    for example, doesn't prevent inviting a new member with that same
    email. This also applies to the Lead→Customer/Contact matching
    logic in Business Rule 5 (Section 8): soft-deleted Customers/
    Contacts are excluded from the match, so a Won lead never links
    to a record the organization has already removed.
-   Timezone-aware timestamps
-   Unit tests for core business logic

  (Specific testing frameworks, linters, and formatters are an
  implementation/tooling decision and are intentionally left out of
  this PRD; they belong in the project's engineering setup, e.g.
  `pyproject.toml` / CI config, not in the product requirements.)

## 8. Business Rules

1.  Every resource belongs to one organization.
2.  Cross-organization access is forbidden.
3.  Lead ownership is mandatory.
4.  Stage history is immutable.
5.  **A Customer is created or linked only when a Lead reaches the Won
    stage.** On Won:
    -   If the Lead's email/phone matches either the Customer
        record's own primary contact info **or** any Contact
        currently linked to a Customer within the same organization,
        the Lead is linked to that existing Customer (no duplicate
        Customer is created). This matters for company Customers,
        where the matching email is often a person at the company
        (a Contact) rather than the company's own listed
        email/phone.
    -   **If no Customer/Contact matches**, a new Customer record is
        created from the Lead.
    -   **If more than one distinct Customer matches** (e.g. a shared
        generic email like `info@company.com` was mistakenly entered
        against multiple Customer records), the system does **not**
        auto-link to any of them. Instead, following the same
        non-blocking pattern as the Lead duplicate warning (Section
        5.4), the Won lead is saved and flagged as
        `requires_manual_customer_selection`, with the list of
        matching Customer IDs returned in the API response, so a
        human picks the correct one. This avoids silently attaching a
        Won lead to the wrong Customer.
    -   A single Customer may accumulate links from multiple Won
        Leads over time (repeat business/upsell), but Customer
        records are never created directly outside of this Won-lead
        pathway in MVP scope.
6.  Important actions generate audit events.
7.  Soft delete is used unless permanent deletion is explicitly
    requested.

### 8.1 Timeline vs. Audit Log (scope clarification)

To avoid building two overlapping logging systems:

-   **Lead Timeline** (Section 5.4): a business-facing, chronological
    feed scoped to a single Lead, showing Notes added, Stage changes,
    Activities logged, and Comments — intended for the sales user to
    understand "what happened with this lead."
-   **Audit Log** (Section 7, Business Rule 6): a system-facing,
    organization-wide record of sensitive/administrative actions
    (permission changes, member invites/removals, deletions,
    ownership transfers, settings changes) — intended for
    compliance/security review, not for day-to-day sales use.
-   Stage changes and Notes appear in both, sourced from the same
    underlying event, not duplicated as separate writes.

## 9. Quality Goals

-   Thin Views
-   Business logic in services
-   Reusable permissions
-   Consistent API naming
-   Idempotent endpoints where applicable

## 10. Roadmap

-   **Phase 1 (MVP core):** Auth, Organizations, RBAC (incl.
    permission matrix), Leads, Pipeline
-   **Phase 2 (MVP core):** Customers, Activities, Ticketing,
    Collaboration (Comments + mention parsing, without mention
    notifications — see Section 5.9)
-   **Phase 3 (post-MVP):** Dashboard, Search, Notifications
    (including mention notifications from Phase 2's Collaboration
    feature — see Section 5.9)
-   **Phase 4 (post-MVP):** UX improvements, performance, deployment
    hardening

  MVP = Phase 1 + Phase 2. The 3–4 month part-time estimate (Section
  2) applies to this scope only.

## 11. Success Criteria

-   Multiple organizations operate independently.
-   Full lead lifecycle works.
-   Customer lifecycle works.
-   Ticket workflow works.
-   Fully documented REST API.
-   Production deployment ready.

---

## Appendix: Changelog from v4 → v5

-   **Soft Delete vs. Uniqueness/Matching (Section 7):** Generalized
    beyond the originally-suggested Lead duplicate-check case (which
    was already non-blocking and had no real constraint conflict).
    Added an explicit rule that soft-deleted records must be excluded
    from database uniqueness constraints (via partial indexes) and
    from the Lead→Customer/Contact matching logic in Business Rule 5,
    so a removed record never blocks new valid data or gets
    incorrectly matched against.
-   **Multiple-Customer-Match Edge Case (Business Rule 5, Section
    8):** Added handling for the case where a Lead's contact info
    (e.g. a shared inbox like `info@company.com`) matches more than
    one existing Customer. Rather than auto-linking to the first or
    most-recently-updated match (which risks silently attaching a Won
    lead to the wrong Customer), the system flags the lead as
    `requires_manual_customer_selection` and returns the candidate
    Customer IDs — consistent with the existing non-blocking
    duplicate-warning pattern already used for Leads (Section 5.4).
-   **JWT Logout Architecture (Section 5.1):** Removed ambiguity
    between purely client-side token discard and real server-side
    invalidation. Specified access + refresh token pair, with logout
    implemented as refresh-token blocklisting in Redis (already in
    the stack) rather than relying on stateless client-side discard.

## Appendix: Changelog from v3 → v4

-   **Permission Matrix (5.3):** Added the missing **Activities** and
    **Comments** columns so the table matches the resource list
    stated in the prose above it. Removed the dangling "billing"
    exception on Admin's Org Settings permission, since Billing &
    Subscriptions is entirely out of scope (Section 6) — kept only
    "except ownership transfer."
-   **Collaboration vs. Roadmap (5.9, 10):** Resolved the dependency
    gap where @Mentions (MVP, Section 5.9) implicitly relied on
    Notifications (post-MVP, Phase 3). Split the feature: Comments +
    mention *parsing* now explicitly ship in Phase 2 (MVP) and work
    standalone; mention *notifications* (in-app + email) ship in
    Phase 3 with the rest of Notifications. Roadmap (Section 10)
    updated to name Collaboration in Phase 2 and cross-reference the
    deferred notification piece in Phase 3.
-   **Customer matching logic (Business Rule 5, Section 8):**
    Clarified that Lead email/phone matching checks both the
    Customer's own contact info and any linked Contact's info — not
    just the Customer record itself — since company Customers are
    often matched via a Contact's email rather than a company-level
    one.

## Appendix: Changelog from v2 → v3

-   **Timeline/Roadmap:** Clarified that the 3–4 month MVP estimate
    refers to Phases 1–2 only; Phases 3–4 are post-MVP (Sections 2,
    10).
-   **RBAC:** Kept all 6 roles for MVP but added a required permission
    matrix (Section 5.3) as a prerequisite for implementation; merging
    roles is deferred until the matrix reveals genuine overlap.
-   **Lead → Customer relationship:** Clarified that Won leads link to
    an *existing* Customer when a match is found, rather than always
    creating a new one; a Customer can accumulate multiple Won leads
    over time. Direct/independent Customer creation was **not**
    added, as it would expand scope beyond what v2 defined (Section
    8, Rule 5; Section 5.6).
-   **Ticketing:** Explicitly scoped to attach only to Customers/
    Contacts, not Leads (Section 5.8).
-   **Duplicate warning:** Defined as non-blocking, surfaced via a
    `possible_duplicates` field in the API response (Section 5.4).
-   **Timeline vs. Audit Log:** Added explicit scope distinction to
    prevent building two redundant logging systems (Section 8.1).
-   **Notifications:** Added a concrete list of triggering events
    (Section 5.11).
-   **@Mentions:** Kept in scope, but paired with a single
    transactional email (not bulk/campaign email, so still consistent
    with the Section 6 exclusion) instead of requiring real-time
    infrastructure (Section 5.9).
-   **Testing/linting tools (Pytest, FactoryBoy, Ruff, etc.):** Not
    added. These are implementation/tooling choices, not product
    requirements, and were left out of this PRD by design (Section
    7).

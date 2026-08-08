# 08 — Performance Notes

**Relation to 04/07:** Companion to 04-erd.md's index design and the
roadmap Phase 4 "index/query performance pass" item. Records the
methodology and findings from that pass — not a new set of decisions,
just verification of what 04 already specified.

---

## Methodology

`apps/core/management/commands/perf_check.py` (kept in the repo as a
reusable diagnostic tool) seeds two throwaway organizations — one
matching the target org size, one ~4x larger as "noise" — so that
`organization_id` is genuinely selective (with only one org in the
table, every row matches it, and the planner has no reason to prefer
any index on it). It then runs `EXPLAIN ANALYZE` (via
`QuerySet.explain()`, the real ORM code path) against the exact
queryset shapes used by the heaviest list endpoints.

```bash
python manage.py perf_check --seed 5000      # target-scale org
python manage.py perf_check --noise 20000    # second org, for selectivity
python manage.py perf_check --explain
python manage.py perf_check --cleanup        # removes both orgs and all their data
```

## Findings (verified against ~25,000 leads across 2 orgs)

**Every index defined in 04-erd.md exists and is chosen correctly**
where table size/selectivity justifies it:
- `idx_leads_org_stage`, `idx_tickets_org_status`, `idx_activities_parent`,
  `idx_ntf_recipient_read_created` all confirmed via `Bitmap Index Scan`
  / `Index Scan` in `EXPLAIN ANALYZE` output.
- A handful of filters (Activities due/overdue sweep, Notifications
  unread-list at small volume) planned as `Seq Scan` instead — this is
  the query planner making the *correct* cost-based choice when the
  filter matches a large fraction of a small table; it will
  automatically switch to the index as these tables grow in real
  usage. Not a gap, no action needed.

**One redundant-index observation, deliberately left as-is:** Django
auto-creates a single-column index on every `ForeignKey` field
(`OrgScopedModel.organization`) unless `db_index=False` is passed. On
models where an ERD composite index already leads with
`organization_id` (Lead, Ticket, Customer, Membership, AuditLog), this
auto-index is redundant — a composite `(organization_id, X)` index
already serves `organization_id`-only lookups via the B-tree
leading-column rule. Postgres sometimes picks the plain single-column
index over the composite one for equality lookups since both are
equally cheap; this is not a correctness issue and does not slow any
query — all measured queries executed in well under 2ms at 25k rows.
The only cost is a small amount of extra write overhead and disk
space per affected table.

**Decision: not removing the redundant indexes.** At the PRD's target
scale (5–50 users per organization, 01-product-requirements.md §3),
the write-amplification cost of a handful of redundant single-column
indexes is immaterial, and a migration to drop them (scoped per-model,
since some org-scoped models like Comment/Attachment do *not* have a
composite index covering `organization_id` and would regress if
`db_index=False` were applied blanket via the abstract base class)
is not worth the risk this represents relative to the benefit. Revisit
if/when this product's scale assumptions change materially.

## Open items

None — this closes out the Phase 4 "index/query performance pass"
roadmap item. No schema changes were needed; the ERD's index design
(04-erd.md) is already correct and effective.

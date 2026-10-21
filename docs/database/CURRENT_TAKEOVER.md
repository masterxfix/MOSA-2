# One-time exact Current takeover

Preparation is read-only and grants no authority. The manual, existing
`observation-view-check.yml` workflow has NONE, PREPARE and APPLY modes. Only
PREPARE is used for the preparation order. No installed release or remote file
is changed. There are no provider, Collector, scheduler or deployment calls.

## Pending private plan

The existing reader resolves and qualifies the five-member Observation scope.
`takeover.prepare` reuses the existing Current fact planner and exact projection.
It requires exactly two UPDATE and three INSERT candidates. The private plan
binds the complete physical route row and SHA-256, revision, asset/source identity,
qualified scope rows, current row/origin, both candidate facts and their dedupe,
and selected observation ID/decision. Nothing is hard coded except the existing
qualified five-member scope and the requested 2/3 result contract.

The run identifier is `current-once-<preparation Actions run id>`. The plan is
pending, authorization is NULL, and it expires 24 hours after the snapshot.
A plan hash binds every field. Route activation never changes. Disabled-route
projection is requested, never granted by preparation.

Private evidence is AES-256-GCM encrypted before becoming an Actions artifact.
The content key is independently wrapped for a local RSA-3072 review recipient
and via HKDF/AES-GCM with the existing SSH secret (separate context and salt).
No access account, GitHub secret, password or DB configuration is created. The
local encryption key is for evidence recovery, not authentication. Plaintext
plans and the review key live only in the ignored, access-controlled local
`.current-takeover-private` directory; they must never be committed or logged.
Public outputs contain status labels, the run identifier and plan digest only.
Artifact retention is seven days; authorization expires sooner, after 24 hours.

## Existing execution access, checked without business writes

The existing pinned SSH transport and its existing loopback tunnel are reused.
The existing test writer secret is delivered only over stdin to the existing
Phase2 connection helper. A session READ ONLY transaction checks the exact
account/target, existing grants, InnoDB tables, absence of triggers, and the
existing schema/seed/state snapshot contract. All results are fixed codes.
No INSERT/UPDATE/DELETE or capability write probe is issued. This confirms
configured rights and prerequisites, not a real committed write.

Native preparation of the later FOR UPDATE query remains inside READ ONLY.
MySQL may reject even preparation with error 1792 / SQLSTATE 25006. Only this
exact documented READ ONLY rejection is accepted as a positive barrier proof;
the active transaction and session READ ONLY flag must still match afterwards.
Syntax, privilege or other errors remain failures. The query is never executed
and the transaction never changes to READ WRITE during preparation. See the
[MySQL READ ONLY contract](https://dev.mysql.com/doc/refman/8.0/en/innodb-performance-ro-txn.html).

## Later explicit authorization

After a separate human execution order, APPLY requires the same reviewed main
commit, the successful preparation run and this exact authorization contract:

    EXECUTE_CURRENT_ONCE:<run_id>:<plan_sha256>:ALLOW_DISABLED_ROUTE_PROJECTION

This explicitly grants projection through the exact disabled routes in that
plan; it does not enable a route. The authorization is checked before connecting
to the database and again by the Current planner under lock. No default mode or
missing authorization can reach the writer.

The workflow permits only first attempts and serializes Current work without
cancelling in-progress work. Before APPLY it publishes a public attempt-claim
artifact containing no private data. Exactly one claim, belonging to the current
run, must exist. A failed or uncertain execution consumes that attempt: do not
retry; inspect protected evidence and obtain a new order/plan. Expiration prevents
old claim-artifact retention from enabling a later retry.

The existing Current writer is the only writer. Its original transaction body
is extracted into `MarketCurrent.transaction`, used by both refresh paths and
by synthetic PDO tests. APPLY takes the existing exclusive `m2-current-refresh`
lock and uses REPEATABLE READ. Fresh scope, routes, sources, units, observations,
current and origin are read with FOR UPDATE. The pending baseline must match
exactly; the existing planner rechecks provenance, dedupe, conflicts and approval.
Any drift or changed 2 UPDATE / 3 INSERT result stops before the first write.
All five writes share one transaction. Pre-commit exact readback and unchanged
other-table comparison retain the existing rollback behavior.

After commit an independent READ ONLY connection compares the complete existing
snapshot and replays the same approved Current planner; all five must be
UNCHANGED. A post-commit readback failure is a post-commit failure, not a rollback
claim. The public result remains failed/possibly committed and no retry occurs.
No claim is made that advisory locks exclude unrelated noncooperating writers;
row/range locks protect the selected records, and independent full-state
comparison detects other concurrent changes.

## Evidence limits

Offline PDO tests demonstrate atomic orchestration, rollback, failed readback,
replay and other-table checks without a live database. PREPARE confirms real
routes, candidates and read-only runtime/rights checks. A real commit, actual
write rollback, post-commit readback and replay remain unexecuted until the
separate explicit authorization. Those future criteria must not be reported
as already live-tested.

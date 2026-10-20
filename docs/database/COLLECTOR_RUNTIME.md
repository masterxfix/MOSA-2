# Explicit collector batches and bounded observation persistence

## Entry points and scope

`MarketBatch\run(privateRoot, password, config, entries)` takes an explicit ordered
list of 1–10 approved asset directories. Each contains the existing private
`live-manifest.json`; every manifest must use `USE_EXISTING_ROUTE`. The complete
list is validated before any provider/database call. Empty lists, more than ten
entries, duplicate identities/folders, noncanonical paths, symlinks and paths
outside the private scope or inside the public webroot are rejected. There is
no database discovery and no asset-specific branch. Names do not reorder inputs.

Execution is sequential, with one provider acquisition per started asset, no
retry and no overlap. Every asset has its own transaction and independent
readback. Stop at the first failure; previous committed observations remain.
`COMPLETE` means all items succeeded; `PARTIAL_FAILED` means a failed batch has
at least one confirmed commit, including a commit followed by a readback failure;
`FAILED_BEFORE_FIRST_COMMIT` means no confirmed commit. Unstarted items remain
visible. Item results identify the asset, provider-request status/count, writer
decision, Observation ID, exact replay status, commit state and failure stage.
Unknown runner counters remain unknown. Private evidence never belongs in public
logs; raw provider responses and credentials are not copied into item results.

## Runtime and explicit proof

`MarketLive\run` defaults to `config.verification_mode = runtime`. Runtime
requires an existing approved identity/source/route, defaults to schema 4 and
accepts `state_contract.schema_version = 3` only as an explicit older contract.
Current may already contain facts: observation-only execution does not select,
insert or update Current/Bars. There is no scheduler, cron, background loop,
parallelism, retry system, new provider, Bars build or production approval.

Runtime is a separate verified persistence algorithm, not a switch suppressing
the old checks:

1. Acquire the existing identifier advisory lock. Validate the table set,
   bounded migration ledger and exact checksums, the four approved unit
   definitions and required identity/route/dedupe unique indexes.
2. Resolve only the explicit identity's candidates, identifier bindings,
   configured source and two route-unique groups. Anti-conflict probes include
   old route revisions; latest revisions are selected by revision with LIMIT 1.
   The existing pure identity and route planners still decide `EXISTING_MATCH`.
3. Acquire once through the existing bridge, adapter and transport. Verify the
   acquired adapter, instrument and provider against the manifest/route evidence.
4. In a new transaction recheck the entire scoped baseline, normalize through
   the existing pipeline/writer and obtain its canonical dedupe key. Load only
   that unique key and the semantic fact identity
   `(asset_id, source_id, market_at, observed_at)`. The latter intentionally
   includes other physical routes and v1/v2 domains, preserving the writer's
   protection against reimporting a fact under another route/domain. A second
   semantic match fails closed. No history is transferred to the writer.
5. Invoke the same writer with those stored facts. INSERT uses its existing SQL
   executor; `DUPLICATE_UNCHANGED` preserves the stored ID/row and inserts nothing.
   A primary-key readback checks every physical observation field. Replay must
   reproduce `DUPLICATE_UNCHANGED`, canonical bytes and dedupe key exactly.
6. Recheck scoped bindings, commit atomically, and independently verify bindings
   and the exact observation on a new read-only connection while retaining the
   identifier lock. A transaction failure rolls back and independently verifies
   scoped bindings plus unchanged relevant facts. No automatic second attempt.

Catalog lookups have LIMIT 33 and fail above 32 matching rows; this is an explicit
safety bound, never silent truncation. Route history itself has no such cap.
Ledger/unit reads have LIMIT 5 and reject extra versions/definitions. Observation
reads always use WHERE plus LIMIT 2 (one expected match plus ambiguity detection).
The runtime's only business mutation is the existing Observation INSERT. It
does not globally prove the absence of unrelated concurrent writes; that claim
belongs to the exhaustive proof. Relevant drift or conflicting facts stop it.

`config.verification_mode = proof` explicitly calls the preserved `proofRun`.
Its `snapshot`/`compareDelta` checks still enumerate and compare all expected
tables, exact insert deltas, old facts, rollback and independent readback.
Onboarding/new-route proof remains there; runtime cannot create catalog rows.
Proof's historical schema/Current/Bars preconditions and duplicate opt-in remain
available. With schema 4/existing Current, pass the existing explicit
`state_contract` and `allow_duplicate` approvals as appropriate. No migration
or historical evidence was replaced.

`MarketCurrent\run` remains the separately approved opt-in projection path.
Only a COMPLETE batch proceeds to its Current transaction; its explicit global
approval/projection proof checks are unchanged. Normal Observation runtime
neither imports nor invokes the Current projector.

## Query/index review

Reviewed the existing migrations 0001–0004; no new migration/index/DDL:

| Bounded query | Existing index / limit |
| --- | --- |
| Global identifier | `uq_identifiers_identity` (all three key columns) |
| Entity name | `ix_entities_name` (`canonical_name` prefix), type residual |
| Asset/entity ID; per-asset identifiers | PRIMARY; `ix_identifiers_asset` prefix |
| Source key | `uq_sources_key` |
| External route group/latest revision | `uq_routes_external_revision` equality prefix, reverse revision traversal |
| Asset/source route group/latest revision | `uq_routes_asset_source_revision` equality prefix, reverse revision traversal |
| Cross-group route conflicts | same unique-group prefixes; opposite identity is a residual predicate |
| Observation dedupe / independent ID readback | `uq_market_observations_dedupe` / PRIMARY |
| Semantic fact | `ix_market_observations_asset_source` prefix `(asset_id,source_id,market_at)`; `observed_at` residual |
| Ledger / units | PRIMARY; fixed maximum four rows |

The preserved `m2_assets.display_name` ambiguity probe has no matching index in
0001–0004. LIMIT bounds returned rows but cannot bound scanned catalog rows.
This catalog index gap is documented for separate measured qualification; no
speculative index is added. Likewise the fact query can examine several facts
sharing the same market timestamp before its observed-time residual matches;
route anti-conflict probes can inspect that one route group's revisions. These
are not global Observation-history reads. MySQL EXPLAIN/timing was not performed
because this code task uses no database connection. No actual optimizer choice,
constant database latency or production capacity is claimed.

## Offline evidence

`test_market_live_batch.py` exercises list validation, configured order,
1/2/5/10 assets, sequential execution, exact statuses, middle failure and commit
followed by failed readback. `test_market_runtime.py` executes the PHP runtime
against transactional PDO doubles and the actual Python bridge, adapter,
normalizer and v2 writer. It checks 1/2/5 real runtime items, stop-on-failure with
prior durable commits, exact duplicate/readback/replay, rollback, drift,
cross-route conflicts, corrupt stored payload, and observation-only mutations.
Proof tests execute exhaustive snapshots and detect an unrelated table change.

History-growth evidence compares zero with 20,000 unrelated stored observations:
the SQL call count and returned-row count must be identical, with at most 100 SQL
calls per successful asset. This proves bounded query shape/work transferred to
the application, not MySQL execution time. Batch query work grows with assets;
there is no N-times-full-history read. The adapter/normalizer/writer runs twice
on the single acquired payload to bind exact relevant facts, without another
provider request. This is a small offline scale check, not a live benchmark.

Run relevant tests with PHP on PATH and a writable TEMP/TMP directory. The pinned
SQL/seed artifacts must have their committed LF bytes; automatic CRLF checkout
changes their hashes and is correctly rejected. Test execution results are
recorded below. No web file changes or
testsite deployment are required.

### Execution results

- New/updated batch tests: **13/13 PASS**. Runtime integration tests: **14/14
  PASS**, including separate existing-Current/Bars preservation and old-revision
  route conflicts. Final ledger reads retain all four rows' metadata, including
  applied timestamps, so scoped drift comparison does not discard ledger facts.
- Measured insertion path: **75 SQL calls / 70 returned data rows per asset**,
  unchanged with **0 versus 20,000** unrelated historical Observations.
- Market regression: **130 tests**, with one pre-existing failing test containing
  four initial hash subfailures. Three were checkout CRLF artifacts; after
  restoring the committed bytes, the schema subblock is **15/16 PASS**, with only
  its existing homepage hash expectation still failing.
- Related transport, v2 writer/persistence, batch and additional Runtime test:
  **74/75 PASS**, with the other pre-existing homepage hash assertion failing.
  Both failing test sources and `index.html` match `origin/main` (`d092bcb`)
  exactly after checkout newline normalization. The unchanged homepage's SHA-256
  is `33749a09b437c464e16b59327e8e8a0e33c4e08175601f349be155b3e8928181`;
  both old tests expect
  `f271e50a25fe7dadac9f4e76f0dfb1ce0264d21476e6cb09125ad5deb6c2f4d6`.
  These unrelated tests/HTML are preserved; no protection was weakened.
- PHP lint and `git diff --check`: PASS. Local PHP 8.5.8 / Python 3.13;
  production connection's existing PHP 8.4 guard is unchanged. No live MySQL,
  provider, browser, deployment, scheduler or schema mutation was executed.
- Native order recording was attempted once and failed with
  `PROMPT_RECEIPT_MISSING`. No receipt, time or control-center event was invented.

The code task is implemented. A fully green inherited regression remains blocked
by the two baseline homepage hash tests. MySQL optimizer/latency and the catalog
index gap remain separate qualification work, not a production release.

## Five-asset live acceptance attempt — 20 October 2026

**Incomplete: read-only inventory and EXPLAIN obtained; no onboarding and no final
batch executed.** The one approved local masked credential entry was cancelled
before credentials were handed to the SSH/DB runner. It was not repeated. This
is not evidence that the existing passwords or database permissions are invalid.

Existing hosting SSO, after the user renewed two-factor authentication, opened
phpMyAdmin for precisely `h29077_mosa2_test`. A read-only identity query verified
MySQL `8.0.26-16`, `h29077_mosa2_test@localhost` and port `3307`; the UI's historical
“MySQL 5.7” label was not used as engine evidence. No Plesk task was run.

### Read-only inventory and deterministic provisional selection

Nine active equity assets had nine global, primary ISIN identifiers, matching
identifier/normalized values and NULL source/validity fields. All nine ISINs
passed the existing `Phase3D\isinValid` check. The ledger contained versions
1–4; four frozen units were visible. This does not replace the exact five-manifest
Runtime preflight or provider qualification.

Exclude the two mandated historical assets, sort remaining valid global ISINs
lexicographically, and qualify the first three with the existing adapter. This
yields the following **provisional** scope/order, without name-based preference:

| Order | Asset | ISIN | Existing asset ID | Observed route situation |
| --- | --- | --- | --- | --- |
| 1 | DroneShield | AU000000DRO2 | 516 | Legacy route 517 / Source 205; no unit-bound Frankfurt route shown |
| 2 | BYD | CNE100000296 | 514 | Legacy Frankfurt route 514 / Source 204; unit binding NULL |
| 3 | Ubtech Robotics | CNE100006CQ4 | 517 | Legacy route 518 / Source 205; no unit-bound Frankfurt route shown |
| 4 | Carl Zeiss Meditec | DE0005313704 | 529 | Frankfurt route 530 / revision 1 / Source 204 / EUR@1 |
| 5 | PNE AG | DE000A0JBPG2 | 528 | Frankfurt route 529 / revision 1 / Source 204 / EUR@1 |

DroneShield, BYD and Ubtech are not yet provider-qualified or onboarded by this
assignment. Identity validity alone does not establish eligibility. No synthetic
assets, new Sources or manual SQL INSERTs were used. Initial inventory: 13
Observations (maximum ID 4902), two Current rows and zero Bars. Observation
history was not enumerated.

### Concrete runtime binding correction

The documented adapter key `boerse_frankfurt_api_v1` differs from the existing
canonical Source reference `boerse_frankfurt_api` (Source 204). The previous
Runtime check required these distinct keys to be identical and would reject
this historically qualified binding.

An approved private manifest can now explicitly supply `provider_key` for the
adapter contract; `route_evidence.row.provider_key` still qualifies the existing
canonical Source/route. Acquired adapter module, class, instrument and provider
key continue to match exactly. Without a separate explicit key, the original
exact comparison remains. No suffix stripping, automatic alias discovery,
Source rename or new Source is introduced. A generic test proves rejection
without explicit binding and persistence with it, preserving the Source row.

### Exactly one read-only EXPLAIN

Executed once through the existing Test-DB administration session:

```sql
EXPLAIN SELECT * FROM m2_assets WHERE display_name <=> 'DroneShield' LIMIT 33;
```

Result: `select_type=SIMPLE`, `type=ALL`, `possible_keys=NULL`, `key=NULL`,
estimated `rows=9`, `filtered=11.11`, `Extra=Using where`. This confirms the
documented catalog scan on the small current asset catalog. It is not a measured
Runtime bottleneck or Observation-history scan. No index or migration was added.
No second EXPLAIN was executed.

### Execution and evidence boundaries

- Preparation provider requests: **0**. Final-batch provider requests: **0**.
  The private qualifier was checked only with a frozen synthetic offline fixture.
- Catalog/Source/route/unit/Observation writes by this assignment: **0**.
  No onboarding plan was applied and no final batch budget was consumed.
- Batch: **NOT STARTED**. No fabricated `overall_status`, writer decisions,
  Observation IDs, commits, readbacks or replays. Stored IDs above are inventory
  facts, not new per-asset execution results.
- Current/Bars were read with **no mutation issued**. The independent post-batch
  unchanged-state proof remains **incomplete**, because there was no batch.
  No Current projection ran.
- Real per-asset Runtime/query/provider timings: **not measured**. Historical
  offline 75-SQL/70-row values are not presented as live measurements.
- SSH without a password was currently tested and denied. Both matching local
  WinSCP profiles had neither a stored password nor a key configuration. Direct
  MySQL port 3307 was reachable and advertised TLS, but certificate verification
  failed before authentication; verification was not disabled or bypassed.
- The user approved one masked local dialog for the existing SSH and Test-DB
  passwords and one private temporary CLI directory. The dialog's final state
  was `CANCELLED`: no password handover, authenticated SSH run or remote temporary
  CLI directory. No password was logged, placed in command arguments, stored in
  the repository or sent to GitHub.
- Collector **28/28**, batch **13/13**, final Runtime **15/15** tests passed. The
  final Runtime block/new binding test used local PHP 8.4.13; the initial unchanged
  Collector/batch block used existing PHP 8.5.8. The two unrelated homepage hash
  tests were neither repaired nor rerun. PHP lint and diff checks passed.
- No scheduler, retry, parallel run, webdeployment, Plesk task, password/account
  change, new database, Bars import or production action occurred. Native order
  registration was attempted once and returned `PROMPT_RECEIPT_MISSING` again.

Remaining prerequisite: available existing SSH/Test-DB authentication. Another
credential-entry attempt requires renewed user instruction because this order
limited that interaction to once. Then obtain all three actual provider
qualifications and conflict-free generic onboarding plans, followed by the
complete five-asset preflight, before consuming the single final batch budget.


## Noninteractive Actions acceptance runner

The manual-only `.github/workflows/collector-live-test.yml` runs the existing
Collector/Adapter/Normalizer/Writer on Ubuntu with PHP 8.4 and Python. It uses
only the existing three Actions secrets `MOSA_TEST_SFTP_PASSWORD`,
`MOSA_TEST_SFTP_HOST_KEY_SHA256`, `MOSA_TEST_DB_PASSWORD`, and the fixed four
`MOSA_TEST_SFTP_*` repository variables. No password dialog, fallback, new
account, SFTP session, remote command/file, Plesk task, webdeployment or production
operation is used. The earlier interactive attempt above is historical and is
superseded by this noninteractive path.

`collector_actions.py` reuses `deploy_test_sftp.configuration` and
`deploy_sftp.verify_fingerprint`. It accepts only the pinned Ed25519 host key,
disables agent/key discovery, authenticates once, probes `direct-tcpip` to
Dogado 127.0.0.1:3307 and binds an ephemeral listener to runner 127.0.0.1 only.
Missing secrets produce exact secret names, never values. Authentication,
forwarding or configuration failure prevents all provider calls and DB writes.
SSH and tunnel resources close on every exit. SSH exception text, PHP stderr,
raw provider payloads and database exceptions are never published.

The PDO helper accepts explicit loopback host/port transport parameters; the
existing default remains 127.0.0.1:3307. Database/user/version and the remote
server's own port remain strictly checked, including through a tunnel.
The DB password reaches PHP only over stdin. Its child environment omits SSH,
DB and GitHub secrets; the bridge receives none. Temporary manifests are mode
0600 in runner-only mode-0700 directories and are removed in a finally/context
cleanup. No private artifacts are uploaded. Public output is screened against
all supplied secret values before logging or writing the step summary.

### Frozen acceptance scope and gates

`live_test_scope.json` is the explicit run configuration, in the user-requested
order: DroneShield, BYD, Ubtech Robotics, Carl Zeiss Meditec, PNE AG. Asset IDs
are resolved from the authenticated global ISIN catalog, not copied from old
readbacks. All five complete identity/source/unit/route plans are validated
before a provider request. The final two must already match their existing
unit-bound routes. No asset substitutions or identity discovery are performed.

A shared generic manifest generator retains the historical Phase-3D external
identity `{isin, venue: boerse_frankfurt}`, with null quote variant, snapshot
series and market_quote kind. This exact historical contract was recovered from
existing Phase-3DB and Collector-40 evidence; it is not inferred by hash search.
The unchanged generic planner must confirm the old route group, including BYD's
legacy revision. It still rejects mismatched old revisions/external identities.
The explicit versioned adapter/canonical Source binding remains unchanged.
`frankfurt_request.php` is one shared descriptor, copied from the existing pure
Frankfurt helpers at fixlab commit baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c
(blob ead84889894fd3c1336e2259abb14b607446f366), with a stdin CLI wrapper.
No five asset-specific request scripts or live source/secret files are needed.

Authenticated target and ledger 1-4/unit/index checks precede acquisition.
Each of the first three assets is fetched at most once into a clearly labelled
NON_PERSISTENT_TEST_ROUTE qualification sidecar using the existing adapter,
normalizer, normative unit catalog and writer planner. Qualification persists
nothing. Any failure stops immediately, without onboarding or final acquisition.
Only after all three pass, the existing identity/route apply helpers execute
all planned onboarding atomically, preserving every old revision. The independent
readback must equal the exact initial snapshot plus the planned route rows.

All five final manifests must then use USE_EXISTING_ROUTE. An exclusive batch
marker permits exactly one sequential batch invocation. The existing runtime
retains per-asset commit, exact independent row readback and identical
DUPLICATE_UNCHANGED replay. Failure stops later items and retains earlier commits.
Exhaustive acceptance-only snapshots on separate connections independently prove
Current/Bars and all unrelated tables unchanged; only exact planned routes and
confirmed inserted Observations may differ. These snapshots are outside the
bounded per-asset runtime, not a replacement for it.

### Metrics, validation and execution record

Per-asset elapsed runtime and HTTP fetch duration are measured once. SQL-call and
returned-row metrics are explicitly null/unavailable: the PDO path does not yet
provide reliable complete counters. Offline 75-SQL/70-row values are not imposed
or presented as live measurements. No benchmark loop or new EXPLAIN is run.
The existing display_name ALL / estimated 9 rows finding from c95e9cc remains
applicable; its query/schema are unchanged and no index/migration is added.

Targeted offline checks cover missing secrets, fixed configuration, strict key
rejection, forwarding denial, loopback forwarding cleanup, password stdin and
child environment isolation, output suppression, explicit PDO parameters,
shared descriptor, actual adapter/unit qualification, all-five acceptance,
qualification/authentication/ledger failures, and partial-batch commit retention.
Local PHP 8.4 validation: 19 Actions/acceptance, 28 Collector, 13 batch and 15
runtime tests passed (75 distinct relevant tests); affected transport checks
passed again after the final reporting change. PHP lint and diff checks passed.
The complete five-asset success and failure paths use transactional PDO doubles
and frozen synthetic responses; they are not live acceptance evidence.
An initial integration test exposed an incorrect use of zero-delta entries for
tables without an id column in the global proof. The corrected proof declares
only changed route/observation tables and still compares all other tables exactly.
No check or assertion was weakened. Unrelated homepage hash tests are untouched.

The completion commit is pushed once with [skip ci], then this workflow is
manually dispatched exactly once with expected_commit equal to that SHA. Checkout
is bound to github.sha; a mismatch fails before access. A rerun attempt is skipped.
No repository file is changed after that live run. Actual access statuses,
qualification outcomes, deltas, per-asset writer/IDs/readback/replay, metrics and
failures are recorded in the Actions log/step summary and the final task report,
not retroactively written into this pre-run document. This document does not
claim that SSH/tunnel/authentication or live acceptance have already passed.

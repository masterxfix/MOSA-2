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


## Read-only Collector performance diagnosis — 21 October 2026

This diagnosis investigates the successful five-asset run
[39498807003](https://github.com/masterxfix/MOSA-2/actions/runs/39498807003)
at cb9b723a60867e8dcfe12310db7e1baebb7677a6. It does not optimize the collector.

The original asset timer encloses runtimeRun only. SSH authentication and tunnel
creation happen before that timer. Complete acceptance snapshots likewise sit
outside it: the successful acceptance path calls snapshot eleven times, each
performing a table-set query and three queries per table (52 calls for 17 tables;
572 calls derived from code, not an old live query counter). These snapshots
contribute to the overall acceptance duration, not directly to the reported
37.4–37.7 seconds per asset.

The separate manual workflow is
`.github/workflows/collector-performance.yml`. It reuses the existing fixed
Actions secret configuration, fingerprint verification, SSH context manager and
direct-tcpip forwarding. No remote file, command, deployment or provider
request is used. The diagnostic uses only existing global ISIN identities,
existing unit-bound routes and existing Observations from the five fixed assets.

Measurement definitions:

- A: SSH TCP/handshake/authentication wall time, including strict key verification.
- B: forwarding probe plus local loopback listener/thread creation; excludes teardown.
- C: one bare native PDO constructor/authentication measurement, plus separately
  measured calls to the unchanged configured connection helper. The latter also
  include authenticated identity/version verification and its five session SETs.
- D: exactly ten simple SELECT executions total: five direct query calls and
  five fresh native prepare/execute pairs. There is no warmup or retry.
- E: the same four bounded runtimeState checks per asset as the successful
  runtime, with three on the first connection and the independent check on the
  second. prepare, execute, query and fetch operations are timed separately.
  Existing-fact lookup equivalents are measured separately. A bounded query
  selects an existing Observation for the offline replay; its setup cost is not
  falsely counted as part of the original runtime.
- F: completePlan wall time without DB I/O, parent PHP process CPU time, and
  runtimeState wall time minus measured PDO API wall time. This residual includes
  wrapper/timer overhead and local file/validation work; it is not a pure CPU
  measurement. Local Python bridge startup and offline stored-fact replay wall
  times are reported separately. These make no HTTP request.

Configured connections enter a server-side SESSION TRANSACTION READ ONLY
transaction. A diagnostic-only PDO adapter additionally rejects SQL other than
SELECT/SHOW, side-effecting lock/file/sleep statements, exec, commit and caller
transaction changes. The original runtime/preflight queries and connection
helper are unchanged. Measurement progress is flushed after phases/assets.
Passwords remain on process stdin/in memory, the child environment omits Actions
secrets, process stderr is never published, and the existing output secret guard
is reused. No private artifact is uploaded.

Reported PDO API calls are not synonymous with SQL executions: a prepared
statement has separate prepare and execute calls; fetches are counted too.
Rows count fetched result rows, not optimizer estimates or scanned rows.
The diagnostic cannot separate SQL-server execution time from network/SSH/
protocol waits inside a measured PDO call. No new EXPLAIN, index, migration,
query rewrite, caching, emulated prepares or tunnel/socket optimization is made.

### Successful measurement and evidence

Diagnostic run: [39553694338](https://github.com/masterxfix/MOSA-2/actions/runs/39553694338),
job 119068413406, attempt 1, diagnostic revision
0d4ababc63bc13619f5e6f0d94be1e80e8942516. All steps succeeded:
both PHP lint checks and all nine diagnostic tests passed (1.534 s).
PHP 8.4.26; GitHub-hosted Ubuntu 24.04; runner region centralus.
The historical collector run used westcentralus. Results below are new
measurements, not retroactive per-phase instrumentation of the old run.

The unavailable browser/dispatch route required the explicitly authorized
one-time push trigger on codex/collector-performance-a15aee. On that isolated
branch only, the existing registered acceptance-workflow path temporarily
contained the read-only diagnostic. It did not execute the collector.
The delivered new workflow is workflow_dispatch only; the original acceptance
workflow on main is unchanged. The temporary branch is reset to the original
revision after publication to remove its one-time trigger.

| Component | Measured result |
| --- | --- |
| A SSH connection/auth/key verification | 1.649 s; SSH and host-key PASS |
| B DB forwarding probe/listener creation | 0.301 s; tunnel PASS |
| C Bare native PDO constructor/authentication | 0.515 s; DB authentication successful |
| C Configured helper, 11 separate calls | 1.305–1.657 s; mean 1.569 s |
| D SELECT 1, 5 direct executions | 430.849–432.368 ms; mean 431.280 ms |
| D SELECT 1, 5 fresh native prepare/execute executions | 431.304–436.217 ms; mean 432.853 ms |
| E Four bounded runtime-state checks per asset | 25.125–29.096 s total per asset |
| F Pure PHP completePlan, five assets | 0.161–0.211 ms per asset |
| F Local bridge runtime initialization | 90.851–94.191 ms per asset |
| F Offline existing-fact writer replay, including local child process | 317.205–322.127 ms per asset; all DUPLICATE_UNCHANGED |

A and B occur once before the historical asset timer, so they cannot explain
37.6 seconds repeated for each asset. Configured helper time includes the bare
PDO constructor; these two C figures must not be added together. The diagnostic
opened one bare probe plus eleven configured connections: one setup connection
and two per asset. Extra diagnostic read-only transaction control and rollback
are outside the configured-helper timer.

All ten simple SELECT wall times, milliseconds, in execution order:

| Mode | 1 | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Direct query | 430.849 | 430.986 | 430.993 | 431.202 | 432.368 |
| Native prepare/execute | 436.217 | 431.304 | 433.853 | 431.512 | 431.381 |

For the native probes prepare took 300.599–305.425 ms and execute took
130.434–130.702 ms; fetchColumn took 0.003–0.006 ms. A direct query's PDO call
also took about 431 ms. Native prepare/execute therefore did **not** demonstrate
twice the latency of direct query in this experiment. These client API timings
cannot establish whether the delay originates in network propagation, SSH
forwarding, driver/protocol behavior, or DB-server work.

### Repeated bounded preflight cost

Each measured runtimeState call executed 17 SQL statements (13 prepared
executions and four direct queries), using 47 measured PDO calls including
prepare and fetchAll. It returned 89 rows, including schema/index metadata.
Each asset repeated this check four times: 68 SQL executions, 188 PDO API calls
and 356 returned rows. These counters exclude configured-connection setup,
fact lookups and diagnostic scope setup.

| Asset | Initial preflight s | Transaction recheck s | Before-commit recheck s | Independent state readback s | Sum s | PDO share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DroneShield | 6.327 | 6.323 | 6.670 | 6.661 | 25.981 | 99.9711% |
| BYD | 7.175 | 7.341 | 7.405 | 7.176 | 29.096 | 99.9688% |
| Ubtech Robotics | 5.987 | 6.320 | 6.167 | 6.661 | 25.136 | 99.9682% |
| Carl Zeiss Meditec | 7.179 | 7.349 | 7.346 | 7.175 | 29.049 | 99.9687% |
| PNE AG | 6.157 | 5.981 | 6.664 | 6.322 | 25.125 | 99.9680% |

The phase labels reproduce the original runtime's read sequence; this diagnostic
does not perform the original INSERT or commit. The three checks on the first
connection and the independent check on the second returned identical state.

| Asset | PDO prepare s, four checks | PDO execute s | PDO query s | PDO fetchAll ms | PHP wall residual ms, four checks |
| --- | ---: | ---: | ---: | ---: | ---: |
| DroneShield | 13.607 | 6.799 | 5.567 | 1.110 | 7.502 |
| BYD | 15.660 | 6.803 | 6.623 | 1.183 | 9.084 |
| Ubtech Robotics | 12.589 | 6.795 | 5.742 | 1.130 | 7.997 |
| Carl Zeiss Meditec | 15.641 | 6.809 | 6.589 | 1.144 | 9.093 |
| PNE AG | 12.239 | 6.798 | 6.079 | 1.105 | 8.051 |

Each individual state check used only 4.913–6.386 ms of parent PHP process CPU;
its wall residual outside PDO was 1.814–2.354 ms. CPU time includes client-side
work inside PDO, so CPU and residual must not be added as disjoint components.
These measurements rule out substantial local PHP computation as the cause
of the multi-second state-check duration.

Configured connection times, milliseconds, in execution order (global setup,
then first/independent connection per asset):

1647.244, 1643.531, 1644.497, 1475.111, 1649.393, 1474.901, 1644.611, 1474.241, 1644.460, 1305.257, 1656.614.

Bounded scope/manifest setup took 26.412 s (26.404 s inside PDO), with 61 SQL
executions and 136 fetched rows. It is setup for this five-asset diagnostic,
not a per-asset runtime component. The extra existing-Observation selection
for offline replay took 430.979–432.033 ms per asset and is also excluded
from the historical-runtime comparison.

### Comparison with the historical asset timer

The following sum uses measured equivalents only: four runtimeState checks,
two configured connections, the original three targeted fact-read equivalents,
one independent fact readback and pure completePlan. It excludes this
diagnostic's setup and extra existing-fact selection, and excludes local
bridge initialization/replay so that their different diagnostic use is not
silently equated with all original child-process actions.

| Asset | Historical runtime s | Four checks s | Two connections s | Four targeted reads s | Measured equivalent subtotal s | Historical minus subtotal s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DroneShield | 37.737 | 25.981 | 3.288 | 1.386 | 30.656 | 7.081 |
| BYD | 37.581 | 29.096 | 3.125 | 1.728 | 33.949 | 3.632 |
| Ubtech Robotics | 37.643 | 25.136 | 3.120 | 1.387 | 29.643 | 8.000 |
| Carl Zeiss Meditec | 37.623 | 29.049 | 3.119 | 1.727 | 33.894 | 3.729 |
| PNE AG | 37.438 | 25.125 | 2.962 | 1.555 | 29.642 | 7.796 |

The equivalent subtotal is a **comparison calculation**, not a measured full
collector runtime or exact attribution of the historical run. It represents
78.7–90.3% of the old duration numerically under the new probe conditions.
The remaining 3.632–8.000 s is an arithmetic difference across different runs,
not a measured unexplained phase. The old provider times were 472–748 ms,
already measured in the old run; this diagnosis made no new provider request.

**Proven cause at the processing-step level:** repeated bounded DB preflights
dominate the measured work, consuming 25–29 s per asset, almost entirely inside
PDO calls. Two configured connections and targeted fact reads add approximately
4.5–4.9 s per asset. A cheap SELECT itself takes about 431 ms, so repeated
serial DB/protocol interactions are a substantial source of wall time even
for bounded small result sets. PHP computation, provider HTTP time and one-time
SSH/tunnel setup do not account for the large repeated preflight cost.

**Not proven:** the exact historical 37.6-second decomposition; which fraction
of PDO wall time belongs to network, SSH, driver or DB-server execution; the
timing of the prohibited INSERT/commit; and unmeasured original transaction
control/child-process actions. Server profiling and a new mutating collector
run were intentionally outside this diagnosis. No index defect, table-scan
cause, artificial sleep, or particular network mechanism is asserted.

### Boundaries and validation

The successful report has provider_requests = 0 and business_writes = 0.
Existing observations were read and replayed offline; no collector batch,
writer apply, schema operation, Current/Bars write, scheduler or deployment ran.
The server read-only transaction and SQL adapter enforce the measured DB path;
there was no independent full-database before/after checksum in this diagnostic,
so its evidence must not be presented as a new global unchanged-data snapshot.
SSH and host-key verification passed, all five read-only state/readback checks
passed, and all five offline replays were DUPLICATE_UNCHANGED.
The existing secret-output guard reported NEIN/PASS; no secret value or private
artifact was published.

Nine relevant tests cover read-only rejection before delegation, forbidden
transaction/write APIs, required transaction ownership, actual bounded query
shapes, separate operation/row/residual accounting, missing-secret rejection,
secret-output rejection, manual-only final workflow and the ten-SELECT budget.
No production collector logic or existing acceptance workflow is changed.


## Runtime metadata round-trip consolidation — 21 October 2026

This change addresses the repeated metadata I/O identified by diagnostic
[39553694338](https://github.com/masterxfix/MOSA-2/actions/runs/39553694338).
It changes the shared runtime path, with no asset-specific cases or cache.

### Implementation and safety

Previously each runtimeContract call retrieved the database table set in one
query and the three required tables' indexes in three SHOW INDEX queries.
runtimeMetadata now retrieves those same relevant metadata fields in one
UNION ALL SELECT over information_schema.tables and information_schema.statistics.
The table branch retains the original DATABASE() scope without a table-name
prefix filter. The index branch is restricted to the same three tables.
All unique-key column groups are still reconstructed by index name and sequence
and validated by the unchanged fail-closed checks. Nonunique indexes do not
satisfy uniqueness requirements. An unavailable metadata query or absent unique
group fails the runtime; there is no silent SHOW/cached fallback.

No metadata is retained between calls, assets, transactions or connections.
All four runtimeState checkpoints remain: initial preflight, transaction recheck,
before-commit recheck and independent state readback. The rollback path also
performs a fresh independent state read. Ledger rows/checksums and all unit
definitions are reread in full at every checkpoint; identity, source, route
bindings, both historical route-conflict probes, bounded fact reads, exact dedupe,
writer replay, observation readbacks, identifier lock, commit/rollback and
sequential stop-on-failure behavior are unchanged. The public runtime entry point
fixes the optimized reader; injectable readers are explicit offline test seams.
The old metadata reader exists only in performance_reference.php for comparisons,
with the same contract/state validation code, and is never selected as a fallback.

Proof mode, exhaustive snapshots, migrations, indexes, Current and Bars paths are
unchanged. A cache of schema/ledger/units was rejected here because no guaranteed
invalidation contract protects those values from later changes. This conservative
change removes round trips while continuing to observe metadata at every original
checkpoint. It does not introduce stronger guarantees about concurrent changes
between SQL statements than the previous implementation had.

### Evidence definitions

The offline suite runs the existing runtime integrity tests against both readers,
then compares actual state results and full runtime decisions for 1, 2 and 5
synthetic assets with transactional PDO doubles and the real local writer bridge.
Provider acquisitions in these tests are fixed offline fixtures, never HTTP.
Additional faults cover ledger/unit/route/schema/index changes after preflight
and immediately before commit; missing/denied metadata; independent route and
observation corruption; INSERT/duplicate/corrupt facts; rollback and middle-item
failure. Writes and Current/Bars contents are compared between paths.

The live comparison reuses collector_performance.py, the fixed existing Actions
configuration, pinned host-key validation and SSH forwarding. The --compare-runtime
mode calls only the read-only diagnostic, never runtimeRun, a provider fetch or
writer apply. Each of the five already qualified assets is checked at the same
four checkpoints, with alternating reference/optimized order and an independent
second connection for the fourth checkpoint. State and completePlan results must
be identical; an existing Observation is read independently and replayed offline.
The server READ ONLY transaction, diagnostic SQL allowlist and secret-output guard
remain in force. Setup, connection and existing-fact/replay costs are outside the
state-check comparison timers. There is exactly one live comparison, with no
warmup/repeated full collector batch.

The GitHub connector exposes no workflow_dispatch operation. Execution therefore
uses a temporary, exact-branch push trigger on the isolated verification branch,
with contents:read permissions, run_attempt == 1 and a strict repository/ref/event
job guard. All offline tests must pass before the secret-bearing read-only step.
The committed performance workflow on main remains workflow_dispatch-only; the
temporary workflow is excluded from the completion commit and its branch reset
removes the trigger after the run.

### Successful offline and live results

Run [39555265402](https://github.com/masterxfix/MOSA-2/actions/runs/39555265402),
job 119073457499, attempt 1, revision
3b6aa5bd27c75e7480d54c173c312eb61c14a0d2 completed successfully.
All 46 relevant tests passed: 15 existing optimized-runtime tests (38.442 s),
22 comparison/reference tests (107.593 s, including the same 15 integrity tests
against the reference reader), and nine diagnostic safety tests (1.369 s).
All five PHP lint checks passed. Runner: Ubuntu 24.04, PHP 8.4.26, region westus3.

Offline measured operation counts, for the four state checks only:

| Synthetic assets | SQL before | SQL after | PDO before | PDO after | Returned rows before/after |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 68 | 56 | 188 | 164 | 188 / 188 |
| 2 | 136 | 112 | 376 | 328 | 376 / 376 |
| 5 | 340 | 280 | 940 | 820 | 940 / 940 |

The offline row count depends on the deliberately small synthetic index fixture;
it is not the live row count. Both paths returned identical states per asset.
Full offline runtime results also matched for 1/2/5 assets: decisions, identifiers,
deltas, transaction events and business-write SQL. Only generated created_at
timestamps are excluded when comparing newly created rows across separate runs.
INSERT followed by DUPLICATE_UNCHANGED, conflicts, corrupt observations, early
and late drift, independent corruption, rollback and partial-batch stop cases
passed. Existing Current/Bars sentinel rows remained unchanged, and successful
offline INSERT paths had exactly one Observation INSERT per asset, matching the
old path; duplicate paths added none.

Live timings below sum all four state checks per asset. They do not include
connection/setup, provider, writer, transaction control or replay time.

| Asset | Reference checks s | Optimized checks s | Saved s | Improvement |
| --- | ---: | ---: | ---: | ---: |
| DroneShield | 30.769 | 25.443 | 5.326 | 17.31% |
| BYD | 31.021 | 25.440 | 5.581 | 17.99% |
| Ubtech Robotics | 30.959 | 25.442 | 5.517 | 17.82% |
| Carl Zeiss Meditec | 31.026 | 25.089 | 5.937 | 19.14% |
| PNE AG | 30.419 | 25.451 | 4.969 | 16.33% |
| Mean per asset | 30.839 | 25.373 | 5.466 | 17.72% |

The aggregate improvement is computed as
100 × (1 − 126.864014327 / 154.193654934) = 17.72423%.
All five assets improved, with individual reductions of 16.33–19.14%.

| Four checks, per live asset | Reference | Optimized | Reduction |
| --- | ---: | ---: | ---: |
| SQL executions | 68 | 56 | 12 / 17.65% |
| PDO API calls, including fetches | 188 | 164 | 24 / 12.77% |
| Fetched rows, including schema/index metadata | 356 | 356 | 0 |

At a single checkpoint these counts are 17 → 14 SQL executions,
47 → 41 PDO API calls and 89 → 89 returned rows. The three eliminated
query/fetchAll pairs per checkpoint account for the 24-call reduction per asset.
Prepared identity/ledger/unit/source/route reads are not removed.

Checkpoint wall times, seconds (reference / optimized):

| Asset | Initial preflight | Transaction recheck | Before-commit recheck | Independent state readback |
| --- | ---: | ---: | ---: | ---: |
| DroneShield | 7.599 / 6.403 | 7.782 / 6.407 | 7.606 / 6.405 | 7.782 / 6.229 |
| BYD | 7.779 / 6.226 | 7.796 / 6.404 | 7.833 / 6.402 | 7.612 / 6.408 |
| Ubtech Robotics | 7.601 / 6.401 | 7.779 / 6.403 | 7.791 / 6.405 | 7.787 / 6.233 |
| Carl Zeiss Meditec | 7.801 / 6.227 | 7.780 / 6.229 | 7.821 / 6.227 | 7.624 / 6.405 |
| PNE AG | 7.598 / 6.410 | 7.780 / 6.406 | 7.262 / 6.406 | 7.779 / 6.229 |

All 20 checkpoint comparisons returned identical states; completePlan equality
passed for each of the five assets. Each asset's existing Observation was
read exactly on the independent connection, and its stored-fact offline replay
returned DUPLICATE_UNCHANGED. These are read-only acceptance checks, not new
Observation commits.

SSH, fingerprint verification and DB tunnel reported PASS. The result reports
provider_requests = 0, business_writes = 0, ok = true and secrets_in_log =
NEIN/PASS. No new secret, password input, remote file/deployment, production action
or additional live run was used. The database path was server-enforced read-only;
Current/Bars were not written. No new full-database before/after checksum was
taken, so global absence of unrelated concurrent writes is not claimed.

### Limits and remaining opportunities

The measured 17.72% improvement applies to the four runtime-state checks.
The historical full collector average of about 37.6 seconds was not remeasured:
a full collector run, provider request, INSERT and commit were forbidden here.
It would be incorrect to present 25.37 seconds as the new full asset runtime
or 17.72% as a measured full-collector improvement.

The earlier diagnosis ran in centralus (25.1–29.1 s for its four checks), the
historical collector in westcentralus, and this comparison in westus3.
Only the paired same-run comparison supports the percentage above. A/B order
alternates to reduce simple ordering bias, but this remains one bounded run
with no statistical confidence interval or claim for other network conditions.
The reference uses the previous four metadata statements with unchanged
contract/state validation; it materializes the metadata at the beginning of
the contract call, rather than reproducing the historical interleaving with
ledger/unit reads. No historical per-phase timing is reconstructed.

The change retains every checkpoint and all data checks. It does not solve
pre-existing concurrency limitations between separate statements, or provide
new protection against a valid metadata change that the previous contract
would also accept. Missing required metadata and invalid unique groups still
fail closed. DB execution, network, SSH and driver time remain combined within
PDO wall time.

The remaining serial prepared catalog/fact reads and the two configured
connections per asset are possible future investigation points. Any further
bundling must retain excess-row/conflict detection, full drift visibility and
independent readback; a schema/unit cache needs a proven invalidation mechanism.
No such further change, connection reuse, parallelism, index change or scheduler
is included in this commit.

## DB locality measurement — 21 October 2026

### Scope and execution

[Run 39557709233](https://github.com/masterxfix/MOSA-2/actions/runs/39557709233),
job 119081282922, attempt 1, revision
d7073943492b38dc4dfb13cf526f7953474b4475 completed successfully.
Both PHP lint checks and all twelve relevant offline safety tests passed
(0.461 s). This is a measurement only: collector placement, runtime/persistence
logic, hosting configuration and deployment remain unchanged.

A uses PHP on a GitHub-hosted Ubuntu 24.04 runner (eastus) with the existing
pinned SSH direct-tcpip tunnel. B uses PHP directly through the same authenticated
web213 chrooted SSH transport and TCP 127.0.0.1:3307. The first explicitly approved
PHP candidate, /opt/plesk/php/8.4/bin/php, succeeded; no other candidate was needed.
PHP CLI and PDO MySQL were confirmed before any DB password was sent to a remote
command. The fixed candidate fallback list contains only that PHP 8.4 command,
/usr/bin/php and php; an SSH exec rejection stops immediately, with no alternate
access protocol or hosting change.

Both variants execute the exact same PHP source (SHA-256
8e68a98f2d564b6f713a60689fdf8ab367a52d822e0649a8a78d23888a70253b), database h29077_mosa2_test and account
h29077_mosa2_test@localhost. The authenticated DB identity, version 8.0.26-16
and server port 3307 must match the existing fixed profile.
The source and DB password travel only in process stdin; for B this is the
encrypted, fingerprint-verified SSH channel. The command arguments contain only
a fixed bootstrap and PHP options, never the secret or a secret-bearing source
string. No remote file, directory, SFTP operation, PTY, environment-secret request,
password prompt, Plesk action or provider request is used. PHP CLI file caching,
automatic prepend/append and error logging are explicitly disabled. Raw remote
stderr and exception messages/traces are never published.

The probe sets SESSION TRANSACTION READ ONLY, applies the same five session
settings as the existing connection helper, begins a transaction and verifies
the read-only flag before its target-identity SELECT or any timed SELECT.
The PDO constructor is timed separately from session/identity setup.
Each variant executes exactly ten SELECT 1 AS probe statements: five direct
queries followed by five fresh native prepare/execute pairs, with no warmup
or retry. There are additionally two fixed one-row read-only verification SELECTs
per variant. No other bounded business query was necessary to establish the
locality difference, so none was added. Both transactions end with rollback.

The new manual workflow is .github/workflows/collector-db-locality.yml. It reuses
collector_actions.configuration, ssh_client, tunnel and public_text, the existing
three secrets/four variables, pinned dependencies/actions and the shared live
diagnostic concurrency group. The connector has no workflow_dispatch operation;
the explicitly permitted temporary exact-branch trigger ran on
codex/db-locality-a15aee, guarded by repository, event, ref and run_attempt == 1.
Tests gated the secret-bearing live step. The final main tree contains only the
manual workflow; resetting the temporary branch to the initial revision removes
its one-time trigger.

### Measured A/B comparison

PHP/mysqlnd differ at the patch level: A = PHP/mysqlnd 8.4.26,
B = PHP/mysqlnd 8.4.12. Both use native prepares, native result types,
FETCH_ASSOC, a 5-second PDO timeout, utf8mb4 / utf8mb4_0900_ai_ci, UTC and the
existing strict SQL mode. Configured options were identical and native-prepare/
native-type settings were checked. This is an observed environment comparison,
not an isolated experiment attributing every difference exclusively to SSH.

All timings below are milliseconds unless explicitly marked:

| Measurement | A: GitHub PHP / tunnel | B: Dogado PHP / local DB |
| --- | ---: | ---: |
| Bare PDO constructor/authentication, n=1 | 259.659 | 0.994 |
| Session setup plus read-only/target verification | 1241.508 | 1.494 |
| Direct SELECT mean, n=5 | 256.600 | 0.261233 |
| Direct SELECT min–max | 200.178–341.309 | 0.200223–0.403082 |
| Native prepare/execute SELECT mean, n=5 | 284.263 | 0.216166 |
| Native SELECT min–max | 200.153–480.563 | 0.206893–0.224898 |
| All ten SELECTs mean | 270.432 | 0.238700 |
| All ten SELECTs min–max | 200.153–480.563 | 0.200223–0.403082 |
| Ten-SELECT sequence | 2704.331 | 2.398 |
| Total internal PHP measurement sequence, including connect/setup/rollback | 4305.755 | 5.038 |
| Parent-observed process/SSH-command duration | 4354.070 | 433.454 |

PDO and whole-sequence timing each have only one sample per variant; no
repeatability range or confidence interval can be inferred for those values.
The ten-SELECT mean combines the explicitly reported five direct and five native
measurements; the separate mode statistics are the primary like-for-like result.
SQL wall timers include prepare/query, execute where applicable and fetch.

| Comparison | A / B factor | B reduction relative to A |
| --- | ---: | ---: |
| Direct SELECT mean | 982.26× | 99.8982% |
| Native SELECT mean | 1315.02× | 99.9240% |
| Combined SELECT mean | 1132.94× | 99.9117% |
| PDO constructor/authentication | 261.15× | 99.6171% |
| Internal PHP sequence | 854.68× | 99.8830% |

Raw SELECT wall times, in execution order, milliseconds:

| Mode / sample | A | B |
| --- | ---: | ---: |
| direct 1 | 341.309240 | 0.209388 |
| direct 2 | 200.386413 | 0.288659 |
| direct 3 | 200.208570 | 0.204815 |
| direct 4 | 340.919341 | 0.200223 |
| direct 5 | 200.177600 | 0.403082 |
| native 1 | 480.563481 | 0.222991 |
| native 2 | 200.152506 | 0.211163 |
| native 3 | 340.024780 | 0.206893 |
| native 4 | 200.166060 | 0.224898 |
| native 5 | 200.408982 | 0.214886 |

The local PHP sequence took only 5.038 ms, while the runner-observed B command
took 433.454 ms. The latter also includes SSH command/channel/control transport,
interpreter startup, stdin transfer and result delivery. It must not be called
local SQL time. Similarly the internal A sequence excludes initial SSH login,
the forwarding setup and the earlier capability command.

### What is measured, estimated and still unverified

**Measured:** this run's combined cheap-SELECT latency fell from 270.432 ms to
0.238700 ms, approximately 1,133× / 99.9117% lower. Direct and native modes
individually show the same large order-of-magnitude advantage. PDO connection
latency also fell from 259.659 ms to 0.994 ms. The previous roughly 431 ms
tunnel value is historical; this run's eastus latency differs substantially.
No uniform network latency or statistical guarantee is claimed from ten probes.

**Illustrative estimate, not a collector prediction:** the optimized collector's
four state checks contain 52 prepared executions and four direct queries per
asset. Substituting only this run's SELECT 1 means gives a cheap-query component
of 52 × 284.263162 + 4 × 256.600233 = 15808.085 ms for A and
52 × 0.216166 + 4 × 0.261233 = 12.286 ms for B, a difference of
about 15.80 seconds. Two PDO constructors at the observed difference
would add about 0.517 seconds of possible savings.
This scaling assumes every real query behaves like SELECT 1, which is unproven.
It excludes real schema/catalog/fact query execution, row transfer, validations,
provider work, writer/commit, process startup and independent readback overhead.
It is a transport/cheap-query sensitivity calculation, neither a lower bound nor
a reliable total-runtime estimate. Do not subtract it from the historical
37.6-second collector runtime or present a new measured collector duration.

**Architecture assessment:** prioritize a future, separately authorized
feasibility/integration design for running the collector close to the DB over
further small round-trip reductions. Local DB access removes the large per-query
remote-path penalty for every retained integrity checkpoint, whereas another
small SQL consolidation affects only a few calls. The measurements strongly
support this direction, while leaving all current checks and placement intact.
They do not authorize a collector move or deployment.

Still untested are the actual bounded runtime queries on Dogado, Python/provider
adapter dependencies and network access, the complete PHP/Python collector
runtime, private workspace and secret provisioning without files, failure and
resource limits, concurrent/manual-run exclusion and recovery/operational
ownership. No scheduling mechanism was added or tested. A full collector run
with real acquisition/writer/commit would require a separate explicit scope;
the present result does not establish its end-to-end speed or production readiness.

### Safety outcome and relevant tests

SSH, host-key verification, tunnel, both fixed DB-identity checks, read-only
enforcement and rollback: PASS. Dogado PHP 8.4 CLI, PDO MySQL and local test DB:
available. Both variants report provider_requests = 0, business_writes = 0 and
select1_executions = 10; the existing secret-output guard reports NEIN/PASS.
No new Observation, Current/Bars write, schema change, production change or
remote file operation was performed. This is enforced by the fixed read-only
probe path; no global before/after checksum of unrelated concurrent activity
was taken.

Twelve offline tests cover the exact SELECT budget/modes and read-only ownership,
identity/value failure and rollback, invalid endpoint/missing secret before PDO,
exception-text suppression, stdin-only secret/source transport and sanitized
child environment, no PTY and channel cleanup, exec rejection before password/DB,
the three-command capability bound, stop before tunnel on failed capability,
output bounds and secret guard, ratio arithmetic, and the manual-only/fileless/
no-provider/no-business-write workflow contract. Both PHP files passed lint.
No collector/runtime logic or previous workflow was modified.

## Dogado collector runtime readiness — 21 October 2026

### Result: assessment complete; unchanged collector not ready

[Run 39560561990](https://github.com/masterxfix/MOSA-2/actions/runs/39560561990),
job 119090524991, attempt 1, revision
3a75962c32a5fd7eaef572d5c543e478369b45ae completed successfully.
Both PHP lint checks and all ten relevant safety tests passed (0.698 s).
The diagnostic reports ok=true / assessment_complete=true but
collector_runtime_ready=false. A completed assessment is not a collector PASS.

The currently checked SSH/chroot commands expose Python 3.6.8, while the
unchanged collector requires Python >=3.10. dataclasses is absent,
typing.Protocol is absent, and the representative collector annotation/dataclass
syntax check fails. No compatible interpreter was found in the three fixed
commands below; this is not an inventory of every interpreter on the host.

| Harmless live check | Result |
| --- | --- |
| SSH authentication / pinned host key | PASS / PASS |
| PHP CLI / PDO MySQL | PHP 8.4.12 / PASS |
| PHP proc_open / process status / terminate / nonblocking pipes | Available; harmless child start and collection PASS |
| /usr/bin/python3 | Python 3.6.8; not collector-compatible |
| python3 | Resolves to /usr/bin/python3, Python 3.6.8; not collector-compatible |
| /usr/local/bin/python3 | Exit 127; not executable through this checked command |
| Python modules | 23/24 imported; dataclasses FAIL |
| typing.Protocol / minimum version / collector annotation test | FAIL / FAIL / FAIL |
| Python -> literal php using existing PATH | PHP 8.3.35, so the PHP-8.4 check FAILS |
| Python -> literal php using a child-only pinned PHP-bin PATH prefix | PHP 8.4.12 with PDO MySQL; PASS |
| Start and terminate a harmless child in its own process group | PASS |
| PHP MD5/JSON primitives and Europe/Berlin timezone | Available |
| Python TLS context | SNI available; 153 CA certificates; OpenSSL 1.0.2k-fips |
| Provider requests / DB connections / business writes / remote file operations | 0 / 0 / 0 / 0 |

PHP/Python process interoperability is demonstrated even with the old Python.
That does not make the actual normalizer/writer/bridge importable on Python 3.6.
Installing a dataclasses backport alone would not solve the typing/built-in
generic/union-annotation requirements. No installation, compatibility port,
fallback collector path, PATH configuration change or hosting change was made.
The pinned PATH existed only in the harmless test child's environment.

The live module imports were: argparse, ast, base64, copy, dataclasses, datetime,
decimal, fractions, hashlib, importlib.util, json, math, pathlib, re, subprocess,
types, typing, urllib.request, urllib.parse, urllib.error, ssl, resource, signal
and time. All except dataclasses imported successfully. Import success for typing
does not imply Protocol exists; that attribute was tested separately.
MOSA project modules were not deployed or imported on Dogado.

### Targeted code dependency review

| Existing component | Required runtime/files and behavior |
| --- | --- |
| market_collector/live_batch.php, live_persistence.php, runtime_persistence.php | PHP 8.4, PDO MySQL, existing transaction/identifier locks, bounded state checks, exact Observation readbacks and stop-on-failure; transitive PHP includes under phase2/3b/3c/3d/3k/3m/3o |
| market_collector/live_bridge.py and contracts/collector/normalizer | Python >=3.10, standard-library modules, actual repository layout and credential-free JSON stdin/stdout bridge |
| phase3n/writer_plan.py, observation_v2.py, unit_catalog_adapter.py; phase3l/unit_seed.py; phase3o/live_plan.py | Same existing normalization, canonical bytes, unit binding and Dedupe/WriterPlanner; dynamic imports resolve real relative files |
| phase3n/value_adapter.php and phase3c/market_flow.php | Python repeatedly invokes literal php for unchanged v1 identity/decimal/time primitives; an absolute top-level PHP command alone does not pin these nested calls |
| docs/database/seeds/0001_market_units_v1.json and the 0004 migration SQL | Normative catalog bytes/fingerprint and schema checksum anchors; read-only validation inputs, not permission to apply migrations |
| market_collector/boerse_frankfurt.py and frankfurt_request.php | Existing qualified descriptor, PHP subprocess, UTC/Berlin date handling and MD5 public protocol headers; one anonymous HTTPS acquisition through the existing single-use transport |
| Per-run private_root | Existing live-manifest.json reads and exclusive provider-consumed.lock creation; a real acquisition cannot use the present fileless probe strategy unchanged |

The inspected Python collector/normalizer/writer dependency closure uses the
standard library; requests, pandas, numpy and a Python MySQL client are not
required by this path. Paramiko/cryptography and the pinned deployment
requirements belong to the GitHub control runner, not the Dogado collector.
No asset-specific module, route shortcut or alternative Dedupe implementation
is proposed.

The generic bridge fetch action calls the chosen adapter's live_request.
Frankfurt has the existing qualified acquisition descriptor; the Yahoo adapter
currently supplies normalization only. Availability of a normalizer does not
authorize a new live provider/acquisition path. Qualified manifests must continue
to select supported adapters explicitly.

The existing PHP bridge supplies config.python/project/runtime_path and launches
the Python bridge with PATH plus PYTHONDONTWRITEBYTECODE=1. The reverse value
adapter invokes php by name. The future runtime must therefore pin both the
explicit interpreter fields and the minimal child PATH consistently; it must
derive the PATH from the approved remote binaries, not copy GitHub runner paths.
State-contract checks, normalizers, writer decisions, independent readbacks and
the existing proof-mode dispatch remain unchanged.

### Observed limits and provider prerequisites

| Limit/primitive | Observed value |
| --- | --- |
| PHP memory_limit | 256M |
| PHP max_execution_time | 0 |
| PHP hard_timeout | 2 |
| PHP default_socket_timeout | 60 s |
| PHP open_basedir restriction | Not configured for this CLI |
| Python/POSIX CPU, address space, data, RSS and file-size rlimits | Unlimited at this interface |
| Open files | soft 1024 / hard 4096 |
| Processes | soft 4096 / hard 175577 |
| Stack | soft 8 MiB / hard unlimited |

These are reported PHP settings and process rlimits, not measured capacity or a
hosting-service guarantee. PHP max_execution_time=0 supplies no useful CLI wall
deadline; hard_timeout=2 must not be interpreted as a two-second job limit.
Account/cgroup/shared-host quotas, long-running-session termination and realistic
peak memory were not probed or stress-tested. No workload was used to exhaust
a limit.

TLS context/SNI/CA loading, JSON, MD5 availability, decimal/date primitives and
subprocess access are necessary building blocks, not proof of provider access.
No DNS lookup, outbound connection, HTTPS request, provider authentication,
IP/rate-limit behavior or clock-synchronization check was made. The existing
HTTP transport uses one anonymous GET, no ambient authenticated proxy/cookies,
no redirect retry and a 25-second acquisition timeout. Its response.read() has
no explicit byte cap in the inspected path; realistic memory use still requires
a separately scoped test. No HTTP or process policy was weakened here.

### Uniform future execution concept — design only

GitHub Actions remains the manual control plane: fixed reviewed commit, explicit
qualified scope, existing secrets, pinned SSH host key and a shared concurrency
group. SSH starts one foreground, release-bound remote supervisor. That process
runs the existing generic PHP batch/runtime against the local test DB and its
existing credential-free Python normalizer/writer bridge. No scheduler, remote
daemon or per-asset implementation is needed or added.

1. **Runtime/release binding.** First obtain a separately approved Python >=3.10
   runtime through an authorized hosting route. Pin absolute PHP/Python binaries
   and a minimal PATH covering both reverse subprocess calls. Use a secret-free,
   immutable release tree that preserves the repository's relative paths,
   normative files and reviewed commit/hash manifest. Fail closed if any bound
   file, version, route, ledger or unit contract differs; no package is installed
   by the collector.
2. **Secrets.** Keep SSH credentials on the Actions side. Transfer the DB password
   once over the verified SSH channel into the owning PHP process's stdin,
   using the existing run(password, config, manifest) interface. Do not create
   access.php, .env, command-line secrets, secret-bearing environment variables,
   archives, diagnostic artifacts or password files. Python receives the same
   credential-free plan/acquisition messages as now. Parent/child pipes and
   output buffers are private and bounded; reports reuse the existing full-output
   secret guard and fixed error codes.
3. **Private state.** A future explicitly approved root outside every webroot
   must hold owner-only release/run directories (umask 077, directories 0700,
   files 0600). Per-run directories contain only the existing nonsecret
   manifest, consumption marker and redacted evidence. Validate canonical parent
   paths, reject symlinks/traversal and exclusive-create run files. The current
   webroot-only authorization does not already permit creating that root.
4. **Concurrency.** Keep the Actions concurrency group and existing per-identifier
   MySQL GET_LOCK through independent readback. Add a remote whole-job exclusive
   lock for the approved private root before any acquisition; Actions alone
   cannot exclude a second SSH/manual process. A future flock-based lock needs
   an authorized file path and a separate collision test. Do not replace the
   existing DB/Dedupe/transaction locks or their fail-closed outcomes.
5. **Termination/cleanup.** A foreground supervisor must own and validate its
   child process group, enforce per-operation and total wall/output budgets,
   monitor control-channel loss and use TERM, bounded grace, then KILL only for
   that owned group. The harmless own-group termination mechanism worked here;
   full collector disconnect/timeout handling is not implemented or proved.
   Preserve the consumed-acquisition marker and an explicit OUTCOME_UNKNOWN
   status if interruption makes commit outcome uncertain; never refetch blindly.
   Cleanup may remove only files in the verified run-owned private directory
   after proven success/rollback, with independent DB readback still required.
   Passwords remain memory-only and die with their owning processes.
6. **Status semantics.** Use explicit stages (preflight, acquire, transaction,
   commit, independent readback, cleanup), bounded run IDs/commit identities,
   counters and failure codes. A completed diagnostic with runtime_ready=false
   must not be reported as a collector success. Committed-but-readback-failed,
   rolled-back and unknown outcomes remain distinct; stop the batch on failure.

This concept is not an implemented wrapper or a release/deployment authorization.

### Files and the approved deployment boundary

A later unchanged full run **requires files on Dogado**. __file__/__DIR__-relative
imports/includes, hash_file/normative catalog checks, the PHP request descriptor
(frankfurt_request.php, or the private/request.php fallback) and the private
manifest/consumption marker cannot all be satisfied by the fileless
interpreter probes. A release must contain an audited tracked-file dependency
closure of the PHP/Python modules and required seed/migration files, with the
same layout and hashes. Historical apply/test entry points must not be invoked.

The current approved .github/workflows/deploy-testsite.yml uses
deploy_test_sftp.selected_files -> deploy_sftp.web_files. That package explicitly
excludes scripts/, docs/ and tests/, and the SFTP profile is hard-bound to
/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de.
Consequently the existing workflow **cannot safely provision the required
private collector tree as-is**. Putting an archive, source tree or runtime state
in the public webroot is not an acceptable workaround.

A future separately scoped private-package operation could reuse this deployment
route's existing secrets, fingerprint check, exact target/canonical-parent and
symlink guards, explicit tracked-file selection, SHA-256 readback and atomic
rename. It would need a newly explicit, fixed private-root authorization/profile,
a minimal reviewed manifest, private modes and tests proving isolation from the
webroot and other domains. It must not loosen the current web deployment profile.
No such path was inspected, created, uploaded, modified or approved by this task.

### Recommended gates before the first full Dogado test

Current answer for the unchanged collector in the inspected environment: **NO**.
A compatible Python runtime, consistent pinned PHP/Python PATH and an approved
private release/run deployment mechanism are still missing. Project-module
imports, real normative file access, lock collisions, realistic limits,
provider reachability and full lifecycle/recovery remain unverified.

After those prerequisites are separately resolved, first run the actual
release-bound offline normalizer/writer fixtures on Dogado without provider
or DB writes, plus bounded read-only preflight/independent checks and timeout/
disconnect/lock-collision cases. Only then recommend a separately authorized
manual full test of exactly one existing qualified asset, at most one acquisition
and its bounded expected Observation write, exact independent readback,
DUPLICATE_UNCHANGED replay and Current/Bars invariance. Do not begin with a five-
asset or production run. No part of that proposed full test was executed here.

### Diagnostic safeguards and test receipt

The new manual workflow is .github/workflows/collector-runtime-readiness.yml;
it reuses collector_actions.configuration/ssh_client/public_text and
collector_db_locality.capability/command/remote_call without changing them.
No DB password is included in the remote readiness payload, and no DB connection
is made. Source is streamed in memory over the verified SSH channel. Python
runs isolated with -I -B; PHP CLI auto-prepend/append, file cache and error logging
are disabled. No project file or Python bytecode cache is created remotely.
Only fixed Python commands are attempted; process permission rejection is
reported without an alternate access protocol.

The connector exposes no dispatch method, so the bounded exact-branch temporary
trigger ran on codex/runtime-readiness-a15aee with contents:read,
repository/event/ref/run_attempt guards and tests before SSH. The final main
workflow is manual-only; resetting the temporary branch removes its trigger.
The initial [test-only run 39560443617](https://github.com/masterxfix/MOSA-2/actions/runs/39560443617)
caught a new child-output-drain defect and skipped SSH entirely. The helper
was corrected to drain through EOF while enforcing the output bound, then the
same safety suite passed before the single live assessment.

The ten tests cover fixed/limited candidate commands and early stop; harmless
PHP child completion; private stderr suppression and excessive-output rejection;
local module/syntax/PHP reverse calls and own-process-group cleanup; absence
of secrets/DB input in remote payload; correct negative-readiness semantics;
missing-secret stop before SSH; no alternate route after exec rejection;
manual-only workflow/no DB, provider or filesystem-mutating probe; and the
existing secret-output guard. Only new diagnostic/workflow/tests and this
documentation are changed. Existing collector core, proof mode, deployment and
production workflows, database, scheduler and masterxfix/fixlab are untouched.

## Compatible Python found and private provisioning contract — 21 October 2026

### Present and tested: Python >=3.10 YES

[Run 39562130881](https://github.com/masterxfix/MOSA-2/actions/runs/39562130881),
job 119095645983, attempt 1, revision
088d0bc1533f15c6480b97b6d4ca948b8c38e7ee completed successfully.
The ten reused process/security tests passed in 0.560 s and six new bounded-path/
ABI tests passed in 0.125 s. Existing PHP sources and the generated PHP program
passed lint. The live command completed in about 0.963 s.

The extended fixed-path check found:

| Property | Observed result |
| --- | --- |
| Interpreter | /opt/alt/python311/bin/python3.11 |
| Exact version | Python 3.11.17 |
| Required standard modules | 24/24 PASS |
| dataclasses / typing.Protocol / collector annotation compatibility | PASS / PASS / PASS |
| PHP -> selected Python | PASS, existing proc_open helper |
| Selected Python -> existing PATH php | PHP 8.3.35; PHP-8.4 requirement FAILS |
| Selected Python -> child-only pinned PHP-bin PATH | PHP 8.4.12 / PDO MySQL PASS |
| Own harmless process-group termination | PASS |
| Python TLS prerequisites | SNI true, 153 CA certificates, OpenSSL 1.1.1w |
| SSH / host key / secret-output guard | PASS / PASS / NEIN-PASS |

This supersedes only the earlier negative *interpreter availability* result:
the earlier check inspected three baseline commands and did not include the
Alt-Python 3.11 path. No Python installation or hosting change was required.
MOSA project files were not transferred/imported/executed; standard-library,
syntax and process checks do not constitute a full collector qualification.

The allowed candidate list had 18 explicit versioned files: versions
3.12/3.13/3.14/3.15/3.11/3.10 under /usr/bin/python<V>,
/usr/local/bin/python<V> and /opt/alt/python<digits>/bin/python<V>.
The probe checked 15 entries and stopped at the first compatible one.
Fourteen preceding entries were unavailable/not executable in the jail; the
remaining three 3.10 entries were not checked. No directory listing, glob,
recursive scan, whole-system search or other-domain inspection occurred.

The baseline /usr/bin/python3 remains Python 3.6.8. It was used only to read
ABI metadata through native APIs and explicitly named system library loads:

| Platform prerequisite | Observed result |
| --- | --- |
| Machine / pointer width / byte order | x86_64 / 64 bit / little endian |
| GNU libc | glibc 2.17 |
| libc.so.6, libpthread.so.0, libdl.so.2, libutil.so.1, librt.so.1, libm.so.6 | All loadable inside the jail |
| libcrypt.so.1 | Loadable |
| /lib64/ld-linux-x86-64.so.2 | Accessible |
| /usr/bin/cloudlinux-selector | Not executable/visible at this fixed path |
| /usr/bin/selectorctl | Executable at this fixed path; never invoked |

Presence of selectorctl is not proof of an enabled/supported application selector
or permission to change its settings. It was not run, so no account/application/
domain list or selector configuration was read or changed.

### Public documentation versus this account's evidence

[Dogado's SSH interpreter guide](https://help.dogado.de/hc/de/articles/28536696027537-PHP-und-Python-per-SSH-im-Webhosting-und-WordPress-Hosting)
documents Python per SSH but makes the available version/path environment-specific.
Its [paths-and-ports guide](https://help.dogado.de/hc/de/articles/23633586903569-Wichtige-Pfade-und-Ports-im-Web-und-WordPress-Hosting)
directs users to their package's oneHome information; it does not publish a
universal modern Python version.

[Plesk's Python support guidance](https://support.plesk.com/hc/en-us/articles/15902915279767-Which-Python-versions-are-supported-by-Plesk)
says additional instances are a server-owner responsibility and may be called
through their binaries. The [CloudLinux Python Selector requirements](https://docs.cloudlinux.com/cloudlinuxos/cloudlinux_os_components/#python-selector)
list cPanel/DirectAdmin and exclude Plesk for that selector. This does not negate
the successful direct Alt-Python CLI test on the actual account.

Conclusion: a suitable interpreter is **actually present and executable**.
An enabled modern Plesk/CloudLinux application-selector UI, contractual support
guarantee, update policy and long-running CLI quota for this package are
**not proven** by public documentation or binary presence. No Plesk setting,
application registration, support ticket or browser form was submitted.
No selector operation is necessary for the preferred direct-CLI approach.

### Preferred concrete route: use the existing Alt-Python, install nothing

Use /opt/alt/python311/bin/python3.11 as the explicitly configured interpreter.
Keep /usr/bin/python3 and every existing domain configuration unchanged.
No venv is necessary for the inspected standard-library-only collector; creating
a venv from Python 3.6 would not supply a newer interpreter anyway.

For the eventual release, provide a small secret-free private launcher named
python3 that execs the absolute 3.11 interpreter with -I -B and the original
arguments. Bind config.python to that launcher and config.php to
/opt/plesk/php/8.4/bin/php. Build a **process-local** minimal PATH from the private
launcher directory, /opt/plesk/php/8.4/bin and required system binary directories,
so both explicit calls and nested literal php/python3 calls stay pinned.
Do not modify account shell startup files, global PATH, alternatives, symlinks
in system directories or selectors.

The actual live_bridge.py already inserts its release's project root explicitly;
an isolated Python start therefore need not depend on user site-packages,
PYTHONPATH or another website. This wrapper/actual-project combination still
requires a file-based offline fixture test after a private deployment is
authorized. It is a design contract here, not an installed launcher.

Record the exact interpreter/version, PHP version and source/seed hashes in each
run's evidence. A vendor patch/path change requires rerunning the runtime and
canonical writer fixtures before use; do not silently switch to the old default.
The [Python lifecycle table](https://devguide.python.org/versions/) lists 3.11
security support through October 2027; >=3.10 is a code-compatibility floor, not
a reason to select the now-EOL 3.10 branch for a new installation.

### Private directory and package contract — not created

Proposed host-side root for a later explicit approval:
 /var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector

This is an uncreated, unverified proposal outside the test webroot. Its exact
chroot-visible spelling, canonical parent, isolation and execute permission must
be confirmed under that later path-specific scope. The existing AGENTS.md and
SFTP webroot authorization do not already permit using it.

A future root has these fixed roles:

- releases/<commit-sha>/ contains the audited PHP/Python dependency closure,
  normative seed/migration validation inputs, launcher and SHA-256 manifest;
  owner-only traversal and no HTTP mapping. Preserve repository-relative paths.
- runs/<safe-run-id>/ contains only the existing nonsecret per-run manifest,
  consumed-acquisition marker and bounded redacted evidence.
- locks/ contains a remote whole-job exclusive lock. Retain the existing Actions
  concurrency group, per-identifier DB locks, Dedupe and independent readbacks.
- Pin the selected release path in the run request; no global runtime replacement
  or mutable system symlink is needed. Keep one previous release for rollback.

Directory modes are 0700, nonexecutable files 0600 and required launchers 0700,
with umask 077 and exclusive creation. Reject traversal, source/destination
symlinks and unexpected ownership. All paths remain under the exact approved
private root, never another domain or a public staging directory.

The deployment extension must reuse the existing testsite SFTP secrets, pinned
host key, exact canonical-root/parent checks, explicit tracked-file manifest,
SHA-256 readback and atomic publication. Add a separately fixed private-package
profile/operation; do not relax the existing web profile. Current web_files
excludes scripts/ and docs/ and its destination is the test webroot, so the
unchanged deployment workflow cannot provision this private package.
No existing workflow or deployment helper was changed in this task.

Only the existing PHP DB owner receives the DB password over protected stdin.
No credential belongs in the launcher, code archive, environment, manifest, file,
command arguments, Python bridge or logs. Keep foreground ownership, total
deadline, bounded outputs, owned-process-group cleanup and explicit unknown-
commit status from the preceding runtime design. No collector-core change,
asset special case, new normalizer/writer or package installation is proposed.

### Storage and dependencies

The preferred route adds **zero runtime-installation bytes**: Python 3.11.17,
its standard library and the tested native dependencies are already present.
It still needs a private application package and run space.

At commit 760689452cb3cb366d1cc899bd5bcdffa74c9aa1, the broad source families
market_collector, phase2/3b/3c/3d/3k/3l/3m/3n/3o plus the normative unit seed
and 0004 migration comprise 54 tracked files / 415855 raw bytes
(about 0.397 MiB), measured through Git tree metadata.
This is a source-size reference, **not a deployment allowlist or a fully
audited release size**: it includes unused diagnostics/historical entry points
which must be excluded, and the final dependency closure must be verified.
Do not publish all those files blindly.

A concrete initial planning reserve is 64 MiB: up to 4 MiB each for active,
rollback and staging application releases (12 MiB), bounded evidence for up to
16 one-MiB run records (16 MiB), up to 8 MiB logs/manifests and 28 MiB slack.
These are proposed caps/headroom, not measured usage or available quota.
Fail/review a package or run that exceeds its agreed budget. Account free space,
inode quota and the as-yet-unapproved private root were not inspected.

PHP's previously measured 256M memory_limit is not an account RAM guarantee.
Real Python/combined-process peak memory and shared-host/cgroup quotas remain
untested; no memory exhaustion test was run. Required packages on Dogado:
none for the inspected path. Required existing facilities: selected Alt-Python,
PHP 8.4/PDO MySQL/proc_open, standard TLS/CA trust, POSIX child control and local
test DB. API/DNS/HTTPS reachability and a complete collector remain untested.

### Contingency only: isolated private CPython package

Because a suitable interpreter was found, this fallback is **not the preferred
implementation** and no runtime archive was downloaded, transferred or executed.
For completeness, public release metadata identified this pinned alternative:

| Item | Metadata-only candidate |
| --- | --- |
| Source | [astral-sh/python-build-standalone release 20261020](https://github.com/astral-sh/python-build-standalone/releases/tag/20261020) |
| Artifact | cpython-3.12.15+20261020-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz |
| Compressed size | 34479233 bytes (32.88 MiB) |
| SHA-256 from release asset metadata | 7d6ef1164fb94c4b60d913340610fc7e0ef8e3d1b705aa5628b299b08cbdd4b5 |
| Target | baseline x86_64-unknown-linux-gnu; regular GIL build |
| Extraction/RAM/actual execution on Dogado | Not tested |

The upstream [runtime requirements](https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.rst)
describe baseline GNU/Linux builds with minimal system-library dependencies and
a glibc 2.17 floor for this target. The observed ABI/libraries make this a
plausible fallback, **not proof that this exact binary works in the jail**.
The [archive documentation](https://docs.astral.sh/python-build-standalone/distributions/)
defines install-only stripped packages as excluding build/debug material.

If that fallback is ever needed, first bind URL/version/hash and licenses in a
reviewed manifest, inspect the archive/dependency metadata on the control runner,
and qualify extraction, safe link materialization, TLS trust and modules before
private publication. Do not use remote builds, curl|sh, automatic uv/pyenv
downloads, system upgrades, musl assumptions or global LD_LIBRARY_PATH changes.
A provisional cap of 256 MiB per extracted runtime and 1 GiB total staging/
rollback reserve would need actual archive-member measurement before approval;
these are planning limits, not a measured footprint. No such space is needed
for the currently preferred existing interpreter.

### Certainty and next implementation step

| Evidence class | Conclusion |
| --- | --- |
| Present and checked | Python 3.11.17 at the exact Alt-Python path; 24 modules, syntax, typing, child-only PHP 8.4 pin, process cleanup and ABI/library checks PASS |
| Technically feasible, untested | Private launcher/release with the unchanged actual MOSA modules; complete normative file access, lock collision/timeout/disconnect handling |
| Hoster-dependent | Private-root approval/chroot mapping/noexec policy, account quotas, support/update policy and long-running CLI/provider-network allowance |
| Not allowed/not done | Runtime/package installation or upload, private directory creation, selector/hosting/global Python changes, other-domain investigation, DB/provider/collector execution |

The next useful implementation is an explicitly private-root-scoped, secret-free
collector package and pinned-launcher deployment using the already available
Python 3.11.17, followed by the actual offline fixtures and bounded read-only
preflight on Dogado. A new Python installation is unnecessary. Resolve the
private deployment/ownership/quota contract before any transfer; do not start a
full collector or change the eight domains/testsite as part of this assessment.

### Safety/test receipt

Run 39562130881 used the new manual
.github/workflows/collector-python-options.yml and the established isolated,
exact-branch test trigger on codex/python-options-a15aee. Tests gate the live
step, contents permission is read-only, and the same concurrency/SSH/fingerprint/
output guard is reused. The final main workflow has workflow_dispatch only;
resetting the verification branch removes its temporary trigger.

The new helper reuses the corrected readinessChild pipe/timeout implementation.
Its own candidate loop has a 45-second admission budget, each child is bounded,
and the outer SSH command is limited to 90 seconds. Only executable-file checks
on named candidates and native ABI/library APIs run. Selector commands are
checked for presence only and never invoked. There is no DB password in the
remote payload, no package-download path, no remote project/cache/credential
file creation, no DNS/provider request and no DB connection.

All 16 relevant tests passed: the ten existing process/output/secret-safety
tests plus six tests for the finite candidate set/early stop, found-interpreter
version/module protocol, generated PHP syntax and secret-free payload, explicit
ABI/library-only inspection, negative-result semantics and manual/no-install/
no-transfer workflow contract. Only a new diagnosis helper/workflow/tests and
this document change; collector, normalizer/writer, production/deployment
workflows, database, system Python and the existing domains are untouched.


## Offline private collector release preparation (2026-10-21)

This phase changes the repository only. It does not connect to Dogado, inspect
or create the proposed private root, read Actions secrets, upload a file,
contact a provider, connect to MySQL or start a collector batch.

### Audited payload and dependency boundary

The versioned allowlist is
[collector_release_contract.json](collector_release_contract.json).
It contains exactly 33 files, with an explicit dependency graph and Git-blob
pins for every qualified source. No directory glob becomes a release allowlist.
Repository-relative paths are preserved.

The payload consists of the existing generic MarketBatch/MarketLive path,
its onboarding/schema/ledger/unit/transaction/readback libraries, the existing
Python bridge, contracts, transport, Collector, normalizer, writer and unit
catalog, both registered normalizer adapters, the Frankfurt request descriptor,
the shared PHP value adapter, the normative unit seed and the 0004 migration
**as a checksum input only**. The Yahoo adapter remains a supported offline
normalizer; packaging it does not qualify a Yahoo live acquisition path.
A disabled, secret-free configuration template and a library-only interpreter
binding complete the payload.

The include chain was followed through Phase 2, 3B, 3C, 3D, 3K, 3M and 3O.
Some historically named files are unavoidable current library dependencies.
They are copied byte-for-byte, with mode 0600, and are **not** allowed CLI
entrypoints. Their dormant historical apply/migration/report routines are not
called; private historical access.php/secret.php, migration inputs, reports,
diagnostics, fixtures and old Actions acceptance programs are not packaged.
No SQL migration is executed by packaging or its validator.

Static Python imports must resolve to the standard library or a listed local
module. Static PHP includes must have recorded edges. Dynamic imports,
subprocess scripts and active file reads are explicitly audited graph edges:
live_bridge → selected registered adapter; writer_plan → observation_v2 →
unit_catalog_adapter → unit_seed → normative JSON; observation_v2 →
value_adapter → market_flow; Frankfurt → frankfurt_request; runtime/proof
state checks → normative JSON and migration checksum. Inactive historical
function resources are outside the supported collector entrypoint boundary.
Changing a pinned source requires an explicit dependency re-audit, rather
than silently trusting a previously generated graph.

The extracted package is tested independently of the repository import path:
PHP includes load without executing historical mains; Python loads its actual
relative files, normative catalog and nested PHP adapter, and produces the
same INSERT and DUPLICATE_UNCHANGED plans for synthetic 1/2/5-asset cases.
These are offline plans, not DB inserts or live collector runs.

### Reproducible artifacts and verification

scripts/collector_release.py builds only from a full, existing 40-character Git
commit. Each allowlisted working file must match that commit's regular tracked
blob and its qualified-source pin. Every source ancestor is checked for links.
The graph must be closed and every payload file reachable from the approved
roots. Missing files, unknown imports/includes, unreachable additions and
source changes abort.

The result is <commit>.tar plus <commit>.manifest.json. The USTAR archive has
sorted regular-file members, mode 0600, uid/gid 0, empty owner/group names and
mtime 0. It contains no links, directory entries, credentials or generated
bytecode. All required directories have a separate intended mode 0700.
The canonical sidecar lists each payload path, SHA-256, size and target mode,
the complete source commit, interpreter contract, allowed entrypoints and
the dependency-contract SHA-256. Build output also records archive and sidecar
SHA-256. The sidecar is control metadata outside the payload archive, avoiding
a self-referential manifest hash.

Verification reconstructs the expected bytes from the caller's trusted exact
commit and reviewed contract; an archive-supplied manifest is never its own
trust anchor. It rejects unknown/duplicate/missing members, absolute/traversal/
backslash/hidden paths, symbolic/hard links, metadata changes, hash mismatch,
noncanonical JSON and extra archive bytes. The local materialized-tree check
also rejects extra directories/files, changed owners, permissive modes,
symlinked ancestors and missing/changed dependencies. It is an offline
validator, not an enabled remote extractor.

A payload cap of 4 MiB is enforced. The 64 MiB initial reserve remains a
planning ceiling, not a measured hosting quota. No Python runtime, pip cache,
third-party package, dependency installer, database password, SFTP credential,
run manifest or provider payload is shipped. Ambient secret/environment values
are never inputs to the builder; synthetic canaries verify their absence.
The existing qualified source pins prevent unnoticed source/template injection.

For a later trusted completion revision, on a clean checkout:
    python3 -B scripts/collector_release.py build --commit FULL_REVIEWED_SHA --output NEW_LOCAL_DIRECTORY
    python3 -B scripts/collector_release.py verify --commit FULL_REVIEWED_SHA --output SAME_LOCAL_DIRECTORY

The output directory must not exist before build. Do not place output in a
webroot. Artifacts should later be retained privately with the expected commit,
archive hash and sidecar hash in the reviewed control-plane receipt.

### Interpreter and execution contract

The library scripts/collector_release/runtime.php pins:
- /opt/alt/python311/bin/python3.11, exactly 3.11.17;
- /opt/plesk/php/8.4/bin/php, exactly 8.4.12;
- child PATH /opt/plesk/php/8.4/bin:/usr/bin:/bin.

It checks the actual CLI/PHP binary/version and a bounded, isolated, bytecode-free
Python version subprocess, then returns existing bridge configuration including
the packaged Frankfurt descriptor. It starts no collector, reads no password
and changes no global PATH. The existing bridge receives this fixed runtime_path;
therefore observation_v2's unchanged literal php child resolves to PHP 8.4.
The bridge already prevents Python bytecode writes. Interpreter updates require
explicit requalification and a new release contract.

Existing generic collector, normalizer, writer, dedupe, runtime/proof modes,
transaction and independent readback code remain byte-identical. No alternative
collector implementation or per-asset package exists. Asset identity/route/run
manifests belong to separately reviewed run data, never release source.

This phase does not provide an executable batch supervisor. Its later contract
must accept only the release-bound generic batch API and the three listed
child entrypoints (bridge, value adapter, request descriptor); historical
apply programs are never accepted as entrypoints. It must enforce the disabled
execution flag, immutable verified release, qualified USE_EXISTING_ROUTE run
inputs, single-job lock, bounded output, timeout/disconnect termination and
cleanup before any real run can be authorized.

### Private root proposal and explicit approval contract

Proposed host-side root, **not authorized or remotely inspected**:
    /var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector

Proposed structure:
    releases/<full-commit>/     immutable verified application payload
    staging/<release-id>/      exclusive partial transfer, never executed
    runs/<run-id>/             bounded run manifests/evidence; no saved passwords
    locks/                     exclusive MOSA-2 supervisor lock

Every directory is intended 0700; payload/config/evidence files 0600; umask 0077.
No symlinks, shared website workspaces, public URL, public handler or site
deployment mapping is allowed. The path string alone proves none of these
properties. The host-side to chroot-visible mapping is still unknown.

A later **explicit path-scoped authorization** must name the canonical root,
host/account, its chroot mapping, permitted directory/file operations, release
commit and limits. Only after that authorization may a bounded verification
check every ancestor with lstat, canonical equality, numeric owner/group and
restrictive permissions; establish that it is outside every account webroot
and has no public alias/URL; and verify available byte/inode quota and permitted
CLI use. Obtain hoster/operator confirmation for the eight-domain boundary
rather than enumerating other domains without authorization. A visible SSH
path is not approval. Owner web213 by name is not proof of the numeric UID.

No root is created, opened, written, treated as preapproved or inferred from
the earlier testsite authorization in this phase. The disabled template uses
approved_root=null, execution_enabled=false and upload_enabled=false.

### Separate, permanently closed preparation profile

scripts/deploy_private_collector.py imports the existing deploy_sftp module
and reuses its fixed public-root constants and host-key fingerprint algorithm.
It offers only an offline lexical proposal review. Known webroots, their
ancestors, malformed paths and any supplied public-root overlap are rejected.
This is not a substitute for complete future remote verification.

The upload entrypoint unconditionally raises
PRIVATE_COLLECTOR_UPLOAD_NOT_IMPLEMENTED_OR_AUTHORIZED before reading
configuration, environment/secrets, loading a client or touching a remote
object. A forged approval object or changing a JSON flag cannot unlock it.
There is no implemented connect, mkdir, upload, rename, extraction or cleanup
path. This deliberate code gate remains until a later separately authorized
implementation. No workflow invokes private deployment.

After explicit approval, a future implementation may reuse the existing
pinned-host-key/SFTP transport while keeping a separate immutable private-root
policy. It must transfer only the verified allowlist to exclusive staging,
verify permissions/owner/hash by independent readback, and atomically publish
a commit-named release without symlink switching. No blind recursive copy,
remote tar extraction or overwrite of a running release. Cleanup must be
bounded to manifest-owned files under that exact root and must never traverse
links or delete unrelated files.

Secret transport is a separate future launch concern: existing Actions secrets
only, strict host-key verification, protected in-memory stdin framing, no
passwords in argv/environment/files/artifacts/logs, no echo or tracing.
The supervisor must retain secrets only for the required process lifetime,
close pipes, redact status output and terminate/wait for the entire child
process group on failure, timeout or disconnect. Lock collision must fail
closed. These operational guarantees are design requirements, not tested
remote behavior in this phase.

The existing deploy_sftp.py, deploy_test_sftp.py and deploy-testsite.yml are
unchanged and tested. The testsite profile cannot select the private proposal.
No production workflow, scheduler, database, hosting configuration or fixlab
file changes.

### Remaining gates before a first upload

1. Explicitly authorize the exact private root and its allowed verification/
   creation/transfer operations; resolve host-side/chroot mapping and all-webroot
   isolation, owner/group, no-symlink/no-public-alias evidence.
2. Confirm account byte/inode quotas, private storage/CLI policy, release/run
   retention and the initial maximum 64 MiB plan reserve. The earlier proposed
   allocation (three 4-MiB releases, 16 MiB run evidence, 8 MiB logs/manifests,
   28 MiB slack) remains a planning limit, not available-space evidence.
3. In a separate scoped implementation, replace the hard-disabled upload gate
   with verified staging/readback/atomic publication and bounded rollback.
4. Qualify the future supervisor's lock/timeout/disconnect/secret cleanup and
   asset-neutral run manifest contract. Only then consider an explicitly
   authorized private file-fixture test; a provider/DB-writing collector test
   still needs its own scope.

No upload or collector move is authorized by this documentation.

### Validated payload manifest

All rows have intended mode **0600**; directory mode is **0700**. These exact
payload bytes are unchanged between the successful verification revision and
the completion revision; only control-plane documentation/workflow metadata
and commit identity differ. Rebuild the sidecar for the exact completion SHA.

| Repository-relative path | Bytes | SHA-256 | Mode |
| --- | ---: | --- | --- |
| config/collector-private.example.json | 820 | 6392e084d2aad6008ef4d00faf7a561bdfa6be156666d0ca3f266a43570b1e3c | 0600 |
| docs/database/migrations/0004_current_observation_provenance.sql | 901 | 46238979889d2fe1bdaac4c5ba4c1ddda7f5810cd87cdf1a8b806db71f63df70 | 0600 |
| docs/database/seeds/0001_market_units_v1.json | 2475 | 0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf | 0600 |
| scripts/collector_release/runtime.php | 2024 | 8eee1230907dbe3d60f308e4bc0c3d1c1f01557302a8b7dc4e341bf1cd2fb4d3 | 0600 |
| scripts/market_collector/boerse_frankfurt.py | 4299 | 1f15fe806b71cd78925de8b0301c97849f4bb3730a09917f33b371b86c3e9f99 | 0600 |
| scripts/market_collector/collector.py | 2960 | 200c4ea06c7a25602b4056a3b648f33191c3980c282c66906ed8f1f46bdd4efb | 0600 |
| scripts/market_collector/contracts.py | 4137 | 66ea63e24f9ba11cc4fb8777b3a50e3dd91f3e148fd1cae025fe79075e76a996 | 0600 |
| scripts/market_collector/frankfurt_request.php | 3102 | 36aff6eb1e00145cfa54de72c97e504f2cc12b1a80d3a81d698ee01f81cae356 | 0600 |
| scripts/market_collector/http_transport.py | 4151 | 89536225178a405aae3e87ae433c6864bdfb81b8ae45416cf45a5c36911ea5a7 | 0600 |
| scripts/market_collector/live_batch.php | 6347 | fb779dd9daf7b5facc0d0b441d04f8fec76f0b8b707c0a98af22c9bbd0a1362a | 0600 |
| scripts/market_collector/live_bridge.py | 4987 | 052235ff01dbff0dda4a65ada1b730a124fabba71c70d7af99b8518d300ae535 | 0600 |
| scripts/market_collector/live_persistence.php | 14165 | 15ce37c95a1318eff4bce094770f9378799fe4d25c55a57a92e3eda157574a35 | 0600 |
| scripts/market_collector/normalizer.py | 4385 | 51972b80d463d319760adffabd82dae4e0404ee17bc573cc8e881f375f49259d | 0600 |
| scripts/market_collector/onboarding.php | 12246 | 8d965adfb1a9fbe04c69b3e1a9f9eec6d571074fb0deedcd89d46e9d38b05b4f | 0600 |
| scripts/market_collector/runtime_persistence.php | 14394 | e87ca09f49b07db7c242ff3151c85f6bd78817c8b18ebaca55d1b57039f49c4f | 0600 |
| scripts/market_collector/yahoo_chart.py | 3372 | e8a94b32d6fc82ba3784e60c35708c0b7267efaa1830e12f8f9905b441568eff | 0600 |
| scripts/phase2/check_expression.php | 7701 | f0ee3266231931d334b2e5dca4a40c17228a90552d6c0f7ac50046ced0bfcac9 | 0600 |
| scripts/phase2/postcheck.php | 24874 | 141a6f50e2682b318af44ad7c39e9aca2f86f4d0856becdbb07d241770c7e5d0 | 0600 |
| scripts/phase3b/postcheck.php | 14850 | 14b69fd726a24175d7370c4a551b0bc0a0e70425d2f109e8132b50521b22b102 | 0600 |
| scripts/phase3c/market_flow.php | 7355 | ab2b9510da0a76b549b587e10db5d768f079b57cd1d4e0d6542b46f805cd33af | 0600 |
| scripts/phase3d/dry_run.php | 13961 | 28e3d689178c6aece3bc77c2c721fc81399defb4854cfbe1420fe583990c7bdc | 0600 |
| scripts/phase3k/live_apply.php | 21429 | 1797852129ed6e898af0fcd6c72af606a62ea46f38c69274f819024825a78101 | 0600 |
| scripts/phase3k/unit_schema.php | 12749 | f681eb92324bb5ec1726c3d92300fe9238c58eebd7b4aab029d2d9b11bfe0f4f | 0600 |
| scripts/phase3l/unit_seed.py | 7842 | f067537f4a9f610469369fd0376830e0551ea12b966931c444924a63914a894c | 0600 |
| scripts/phase3m/live_seed.php | 10514 | 8ab75743cca0acf3953add99cf58cd456467f36a4fda810cd401639bf0e8ce60 | 0600 |
| scripts/phase3m/state_integrity.php | 8437 | 9ae5d26bcf1bcecdf73ffcda732fe967a84a3e9fe72cd459cab44876ade534b2 | 0600 |
| scripts/phase3n/observation_v2.py | 4063 | 2c072d60aade3a4d74963835dad99cb4dcc3ed04b48ade32e1b14e303dc89c61 | 0600 |
| scripts/phase3n/unit_catalog_adapter.py | 2025 | de132450146ec23ccb02b2cec67af3cb38eb604ce5c7861b920389e6d72a897b | 0600 |
| scripts/phase3n/value_adapter.php | 2078 | 6d66f9d1328b4de678081f3e212de89e9ed4a0c71dd390ca157fbfd1f39111e8 | 0600 |
| scripts/phase3n/writer_plan.py | 6955 | 514f826b63d70dc229ebf75caf4f0b039e16ee1f7d71c2ef3128d537976b831d | 0600 |
| scripts/phase3o/live_plan.py | 2298 | cc94d3d1cdb6515d7851c62ec9e436802f01b3aa3423b9af318f796c91ad0782 | 0600 |
| scripts/phase3o/live_writer.php | 14553 | 5276bf33b5e283866cdd4816ed47561fd287a7034a29f58571a39f8136a5bb02 | 0600 |
| scripts/phase3o/state_integrity.php | 1656 | 5f2d758dfcc9f566f17917b98fd93663884d9b770571c1d6dfaa41bafb7f7866 | 0600 |

### Offline test and artifact receipt

- Successful run: [39568896048](https://github.com/masterxfix/MOSA-2/actions/runs/39568896048).
- Verified source snapshot: 498fcf70803c5d91f365829a78555fe71a664f2b.
- Payload: **33 files / 248105 bytes**, about 242.29 KiB.
- Deterministic USTAR length from member/header/block sizes: 276480 bytes.
- Archive SHA-256: 73e34c8d8e13ce37265ef5dded1ceae162140eee5b17341b23ee7dae3e3a68f7.
- Verification-snapshot sidecar SHA-256: 1b9c6456c79e1258166ef8c05a1e672fa3c99e969fab3e8bd60fc044578985f2.
- Audited dependency-contract SHA-256: 26f636d66b880dfd62891230fbcf97a91091c20cc567f255bef806ad7710dcd2.
- Build followed by separate full verify: PASS, identical receipt.

The first offline run
[39568209508](https://github.com/masterxfix/MOSA-2/actions/runs/39568209508)
ran 110 tests: the 98 existing collector/batch/runtime/deployment regressions
and 11 of 12 new release/profile tests passed. One new unchanged-testsite
comparison attempted to read the historical base commit from a shallow
checkout and errored. It was corrected to compare the three immutable,
independently recorded base Git-blob IDs with the current commit, without
fetching history or weakening the equality check.

The successful second run repeated all 12 new tests and the 20 existing
deployment tests: **32/32 PASS**. It also strengthened the extracted-package
fixture to use distinct synthetic ISINs and bound source/output ancestor
checks. The 98 existing tests had already passed; the collector and deployment
implementation bytes did not change between runs. Thus all 110 distinct
relevant tests have passing evidence across the two runs; this is not a claim
that the first run itself was green. Existing deployment test messages saying
“Deployed” concern in-memory FakeSFTP objects only.

Covered: exact dependency closure/loadability; deterministic bytes and hashes;
full commit binding; malformed/absolute/traversal/backslash paths; symlink/
hardlink/unknown/duplicate/missing files; archive owner/mode/timestamp changes;
materialized owner/mode/hash integrity; source tampering; synthetic credential
canaries; default-disabled/forged approval; public-root exclusion; unchanged
testsite blobs and behavior; same extracted package with 1/2/5 distinct assets;
actual normalizer INSERT/replay parity. Existing unchanged tests additionally
cover conflict/corruption/drift, rollback, stop-on-failure, independent readback
and no Current/Bars or extra observation writes using PDO doubles.

The control runner used Python 3.12 and PHP 8.4.26. The new PHP binding was
linted and its fixed runtime/PATH contract checked offline; the absolute
Dogado interpreter paths were not executed in this phase. Their prior
3.11.17/8.4.12 evidence remains separate from these package fixtures.
No remote readiness, quotas, provider connectivity, real DB behavior, process
disconnect cleanup or operational lock collision is newly claimed.

The final .github/workflows/collector-release-offline.yml is manual only,
requires the exact expected_commit, has contents:read and has no MOSA secrets,
SSH/SFTP client installation, DB/provider call or remote deployment step.
Its only execution commands are offline tests and package build/verify on the
runner. The isolated branch trigger used for verification is omitted from
main and removed by resetting the temporary branch to the original base.
Exactly one completion commit is added to main; verification commits are not
merged. No generated archive or credential is committed.


## Read-only private-root assessment (2026-10-21)

### Authorization and bounded execution

The user explicitly authorized **read-only metadata inspection** of:
    /var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector

Necessary ancestor metadata is included; directory inventories, other-domain
inspection, creation, transfer, chmod/chown, deletion and collector execution
remain excluded. This read authorization does not approve a deployment root
or lift the hard upload gate from the previous release-preparation phase.

The new manual workflow .github/workflows/collector-private-path.yml uses the
existing pinned SSH client/host-key verification from collector_actions.py,
the existing two-secret deploy_test_sftp configuration and the bounded,
stderr-suppressing SSH command runner from collector_db_locality.py.
No DB secret is requested or needed. The existing pinned Paramiko dependency
set is installed on the Actions runner only.

scripts/collector_private_path.py performs a finite lstat chain, SFTP
canonicalization of the checked account anchor/current-directory string,
and one fileless Python command using the already qualified absolute
/opt/alt/python311/bin/python3.11 with -I -B. That command calls only current
directory/process-ID APIs, lstat and statvfs on named, checked locations.
No directory is listed and no remote file/source/cache is created.
Unknown current-directory strings are never used as probe targets.

The finite chroot alias is conditional on a missing absolute namespace,
SSH cwd=/ and a verified SFTP account anchor. Permission errors, symlinks
and non-directory ancestors stop inspection; they never trigger alternate
protocol/path attempts. This fallback was offline-tested but **not used**
in the observed live run, since full absolute host paths were visible.
SFTP metadata calls have an eight-second per-call/45-second admission budget;
the SSH command has a 30-second bound, and the live step a two-minute limit.

### Observed path and ownership results

The existing SSH and SFTP connections and pinned host key passed. Both protocols
observed the account anchor and its documented test-webroot sibling using the
same full absolute names. SSH cwd and SFTP normalize(".") were both:
    /var/www/vhosts/web213.server10.configcenter.info

SFTP normalize(account anchor) returned that same exact absolute name.
SSH selected HOST_ABSOLUTE; no additional chroot alias was needed.
The permitted scope does not establish the entire jail boundary or physical
host mount configuration. This is an observed path-view mapping, not proof
that the account is restricted to MOSA 2.

- Target mosa2-collector: **NICHT VORHANDEN**, because its direct parent is absent.
- Direct parent .../private: **NICHT VORHANDEN**, independently reported by both
  protocols. No child lstat was attempted through the missing parent.
- No target owner, group or permissions exist to verify.
- SSH real/effective UID: 10317; real/effective primary GID: 1003.
- Existing account directory owner/group: **10317:1002**, mode **0710**.
- Known test-webroot owner/group: **10317:1002**, mode **0750**.
- All inspected existing ancestors are directories; no symlinks were observed.
  There is no claim about uninspected paths or a subsequently created target.

The numeric primary GID differs from the account-directory GID. Any future
private-directory contract must explicitly choose/verify the intended group;
this diagnosis neither changes it nor infers new group permissions.

| Exact SSH path | Result/type | UID:GID | Mode | Device:inode |
| --- | --- | --- | --- | --- |
| / | directory | 0:0 | 0755 | 64768:1313004 |
| /var | directory | 0:0 | 0755 | 64768:2101312 |
| /var/www | directory | 0:0 | 0755 | 64768:2238886 |
| /var/www/vhosts | directory | 0:0 | 0755 | 64768:13108822 |
| /var/www/vhosts/web213.server10.configcenter.info | directory | 10317:1002 | 0710 | 64768:5248112 |
| /var/www/vhosts/web213.server10.configcenter.info/private | NICHT VORHANDEN | —:— | — | —:— |
| /var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector | NICHT VORHANDEN (parent missing; not traversed) | — | — | — |
| /var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de | directory, known MOSA-2 test webroot | 10317:1002 | 0750 | 64768:35128320 |

SFTP matched existence, directory type, UID/GID, mode, byte size and integer
mtime for the account anchor and known test webroot; the missing parent
matched too. SFTP v3 does not expose device/inode identity, so these are
cross-protocol path/metadata matches rather than inode-identity proof.
SSH supplies device/inode values in the table.

### Isolation and suitability

The proposed path is a separate future sibling branch of the documented
mosa2-test.scharwerk.de webroot, with no symlink in its existing prefix.
The routine's **PASS** is restricted to this known-test-webroot comparison
and the checked path prefix. The private target and its parent do not exist;
their future ownership, modes and isolation cannot already have passed.

**Overall private/public webroot isolation: UNBESTÄTIGT.**
Existing approved documentation (AGENTS.md, docs/DEPLOYMENT.md and
docs/dogado/README.md) identifies the MOSA-2 test document root but does not
provide sufficient evidence that no domain alias, public URL mapping or other
webroot could expose the proposed private location. No other domain, public
URL, Plesk configuration, directory listing or mount inventory was inspected.

The location appears **technically plausible as a proposal**, given the
consistent account anchor, matching current UID and separate path branch.
It is **not ready for private deployment**: both directories are absent and
no creation/write authorization, complete public-isolation evidence or hosting
quota confirmation has been obtained. No unsafe alternative path was selected.

### Filesystem capacity, not hosting quota

statvfs was called only on the nearest existing authorized ancestor:
    /var/www/vhosts/web213.server10.configcenter.info

| Filesystem metric | Observed value |
| --- | ---: |
| Fragment size | 4096 bytes |
| Total filesystem bytes | 3059424206848 |
| Free bytes (including privileged reserve) | 1482807173120 |
| Bytes available to an unprivileged process | 1482790395904 |
| Total filesystem inodes | 189726720 |
| Free inodes | 178663444 |
| Available inodes | 178663444 |
| Confirmed account/hosting byte quota | **UNBESTÄTIGT** |
| Confirmed account/hosting inode quota | **UNBESTÄTIGT** |

These are a snapshot of a potentially shared filesystem, not an account
allocation or a guarantee of usable MOSA-2 space. The numbers exceed the planned
64 MiB reserve arithmetically, but do not prove that the hosting account has
64 MiB quota headroom. No quota command, capacity allocation or stress test ran.

### Tests and live receipt

- Successful [Actions run 39571023928](https://github.com/masterxfix/MOSA-2/actions/runs/39571023928).
- Tested revision: 0fcfa4e728565157b6e8588c94748e90f594716e.
- **11/11 offline safety tests PASS** before the live step.
- SSH PASS; pinned host key PASS; finite SSH/SFTP metadata assessment completed.
- Remote Python command elapsed: about 555 ms; no retry/alternative live route.
- Provider requests 0; DB connections 0; remote writes 0; directory listings 0.
- No target creation, upload, test file, chmod/chown, removal, hosting change
  or collector run. Existing private deployment remains disabled.
- Only the two existing SSH/SFTP secrets are consumed in memory by the common
  pinned client. No secret value was published; public_text suppresses an
  entire report if a known credential appears. Raw stderr/exception messages
  are not emitted.

Tests cover finite allowed paths, metadata fields/capacity semantics, missing
parent/target without creation or child traversal, tightly gated chroot aliases,
denial/symlink/non-directory stops without bypass, cross-protocol mismatches,
known-webroot inode alias detection, SFTP time budgets, absence of write/list/
DB/provider/subprocess capability in the remote payload, pinned-client reuse,
credential-free remote stdin, configuration failure before connection,
secret-output suppression and the restricted workflow contract. Fake OS/SFTP
objects provide these safety cases without remote fixtures.

The isolated codex/private-path-a15aee branch supplied the permitted one-shot
push trigger for this diagnostic. The final workflow on main is manual only,
requires the exact expected_commit and run_attempt=1, with contents:read and
the existing diagnostic concurrency lock. The temporary trigger is removed by
resetting that branch to the pre-task base; verification commits are not merged.
No existing collector, release payload/contract, deployment profile or testsite
workflow is changed.

### Remaining authorization and evidence

Before any first upload, obtain explicit authorization to create/use the exact
private root and its scoped subdirectories, plus hoster/operator evidence of
no public mapping and account byte/inode quota headroom. Then separately
implement/review restrictive owner/group/mode verification and the staging/
readback/publication path. The upload gate stays unimplemented and closed.
A later authorization to create directories would still not authorize a
collector batch, DB writes, providers or production changes.

This task ends with read-only findings and repository documentation. No action
is taken to resolve the missing directories.


## Hosting-Voraussetzungen vor privater Verzeichnisanlage (21.10.2026)

### Nachweisstand und Browsergrenze

Gezielt ausgewertet wurden
[DOGADO_PLATFORM_QUALIFICATION.md](DOGADO_PLATFORM_QUALIFICATION.md),
der vorstehende private Pfadnachweis und
[docs/dogado/README.md](../dogado/README.md).
Historische Kontoanzeigen, der lesende SSH-/SFTP-Nachweis und heutige
öffentliche Produktdokumentation sind unterschiedliche Nachweisarten.

Eine aktuelle angemeldete Kontoansicht konnte in diesem Auftrag nicht über
einen nachgewiesen zulässigen, laufwerksgrenzenkonformen Browserzugang geprüft
werden. Die bekannte lokale Initialisierungsroute ist durch die
Werkzeug-/Laufwerksregeln ausgeschlossen und wurde nicht gestartet.
**Chrome-/Anmeldestatus: UNGEPRÜFT**, nicht „nachweislich abgemeldet“.
Es wurde keine neue Browsersitzung gestartet, kein Login/Passwort angefordert
und keine erneute Authentifizierung ausgelöst. Eine öffentliche Hilfeseite ist
kein Ersatz für aktuelle persönliche Kontoanzeigen.

Es gab in dieser Phase auch keinen weiteren SSH-/SFTP-Lauf. Die folgenden
numerischen Eigentümer- und Pfadangaben stammen ausdrücklich aus dem
vorherigen [Nachweis 39571023928](https://github.com/masterxfix/MOSA-2/actions/runs/39571023928)
und Abschluss-Commit 26c4516, nicht aus einer neuen Servermessung.

### Tarif, Belegung und tatsächlich belegbare Reserve

| Frage | Belegbarer Stand | Aussagegrenze |
| --- | --- | --- |
| Hostingtarif / Speicherlimit | WEB M 3.0, 150 GB, in der Kontoaufnahme vom **17.10.2026** bestätigt | Heute nicht erneut im Konto verifiziert; keine aktuelle Vertrags-/Quota-Zusage |
| oneHome-Belegung | Historisch 6,32 GB am 17.10.2026 | Keine aktuelle Belegung |
| Plesk-Belegung | Historisch 7725,7 MB am 17.10.2026 | Andere Anzeige/Bezugsgröße; nicht mit oneHome verrechnen oder stillschweigend gleichsetzen |
| Aktuelle verbrauchte Account-Quota | **UNBESTÄTIGT** | Keine aktuelle Kontoansicht oder Hosterbestätigung |
| Aktuelle freie Tarif-/Quota-Reserve | **UNBESTÄTIGT** | Keine aktuelle Differenz aus 150 GB und alten Verbrauchswerten berechnen |
| Inode-Quota / aktueller Account-Inodeverbrauch | **UNBESTÄTIGT** | In der damaligen Ressourcenansicht nicht ausgewiesen; das bedeutet nicht unbegrenzt |
| Geplante zusätzliche MOSA-2-Obergrenze | 64 MiB = **67108864 Byte**, einschließlich Releases, Staging, Laufdaten, Locks und temporärer Daten | Planlimit, keine reservierte oder zugesicherte Hostingkapazität |
| Vorheriger statvfs-Befund | 1482790395904 verfügbare Dateisystem-Byte; 178663444 verfügbare Inodes | Shared-Dateisystemkapazität, **keine Account-Quota** |

Die frühere Plesk-Anzeige erlaubte Überbeanspruchung von Speicher/Traffic.
Das erweitert weder das bestätigte historische 150-GB-Limit noch begründet es
eine heute verfügbare Reserve. Zu klären bleiben außerdem Abrechnung von
Datenbanken, Mail, Backups, Logs und temporären Dateien sowie Einheiten und
Aktualisierungsverzug der beiden Belegungsanzeigen.

Die öffentliche
[Dogado-Anleitung zur Paketverwaltung](https://help.dogado.de/hc/de/articles/27647035445649-Ansicht-der-Hosting-Paketverwaltung-im-Kundencenter)
beschreibt eine Speicherübersicht in oneHome. Sie liefert keine aktuellen
Werte dieses Kontos und keinen Nachweis einer Inodegrenze.

### Private Verzeichnisse und öffentliche Zuordnungen

**Öffentliche Isolation des vorgeschlagenen Roots: UNBESTÄTIGT.**

Die letzte Prüfung zeigte den übereinstimmenden SSH-/SFTP-Accountpfad:
    /var/www/vhosts/web213.server10.configcenter.info

Dessen Unterordner private war nicht vorhanden; folglich existierte auch
private/mosa2-collector nicht. Der geplante Pfad liegt als Zeichenpfad außerhalb
des bekannten Test-Webroots mosa2-test.scharwerk.de; in seinem geprüften
bestehenden Vorlauf wurden keine Symlinks gefunden. Das schmale PASS des
vorherigen bekannten-Test-Webroot-Vergleichs ist **kein** vollständiger
Nachweis gegen alle öffentlichen Einbindungen.

Die aktuelle öffentliche
[Dogado-Dokumentation zur Domain-/Ordnerzuordnung](https://help.dogado.de/hc/de/articles/25447619916561-Domain-und-Ordnerzugeh%C3%B6rigkeit-im-Webhosting-und-WordPress-Hosting)
erläutert, dass Domains aus einem zugewiesenen Verzeichnis ausgeliefert werden
und mehrere Domains dasselbe Verzeichnis verwenden können. Die Anleitung zum
[Dokumentenstamm](https://help.dogado.de/hc/de/articles/22595937740305-Dokumentenstamm-bzw-Verzeichnis-einer-Domain-%C3%A4ndern)
beschreibt veränderbare Zuordnungen. Diese öffentlichen Anleitungen wurden
nur gelesen; ihre Änderungsschritte wurden nicht ausgeführt.

Die allgemeine
[Plesk-Obsidian-Dokumentation zur Linux-Verzeichnisstruktur](https://docs.plesk.com/en-US/obsidian/advanced-administration-guide-linux/virtual-hosts-configuration/website-directory-structure/virtual-host-structure-linux.68806/)
führt private unter den seit Plesk 11.5 nicht mehr standardmäßig enthaltenen
Virtual-Host-Verzeichnissen. Daraus folgt weder ein Verbot eines selbst
angelegten Ordners noch eine besondere Schutzgarantie für dessen Namen.
Eine kontospezifische Dogado-Freigabe für den vorgeschlagenen Ordner ist
damit nicht belegt.

Aus den vorhandenen freigegebenen Unterlagen ergibt sich keine vollständige
aktuelle Liste aller Document Roots, Domain-/Subdomain-Aliase, Webserver-Aliase,
Weiterleitungen oder sonstigen öffentlichen Pfadabbildungen dieses Accounts.
Keine fremden Domaininhalte, Dateiverzeichnisse oder Konfigurationen wurden
geöffnet oder durchsucht. Deshalb ist weder PASS noch FAIL für die vollständige
öffentliche Isolation gerechtfertigt.

0700 ist eine notwendige Dateisystemgrenze zu anderen Betriebssystem-UIDs,
aber kein Schutz vor Prozessen mit derselben UID 10317. Auch ein außerhalb
des Document Roots liegender Pfad könnte von einer unter demselben Account
laufenden Webanwendung gelesen und ausgegeben werden. Der Plan schafft
keine neue Betriebssystemidentität und behauptet keine gegenseitige Isolation
der acht Websites. Eine fehlende direkte URL-Zuordnung und die gemeinsame
Account-Laufzeitgrenze müssen getrennt bewertet werden.

### Konkreter Vertrag für eine spätere, ausdrücklich freizugebende Anlage

Dies ist ein **Plan**, keine Anlage- oder Schreibfreigabe.

| Gegenstand | Vorgabe |
| --- | --- |
| Vorhandener, unveränderter Account-Vorfahre | /var/www/vhosts/web213.server10.configcenter.info; zuletzt UID 10317, GID 1002, Modus 0710 |
| Neu anzulegender Zwischenordner, falls weiterhin fehlend | Exakt .../private; muss in einer späteren Freigabe separat mitgenannt sein |
| Neuer privater MOSA-2-Root | Exakt .../private/mosa2-collector |
| Ausschließlich initial erlaubte Unterordner | releases, staging, runs, locks direkt unter dem Root |
| Soll-UID aller neuen privaten Verzeichnisse | **10317** (bestehender Account, kein neuer Benutzer) |
| Vorgeschlagene Soll-GID aller neuen privaten Verzeichnisse | **1003**, aus der zuletzt gemessenen realen/effektiven primären SSH-GID; vor Anlage durch Hoster bzw. aktuellen Identitätsnachweis bestätigen |
| Rolle der beobachteten GID 1002 | Bereits bestehende Account-/Webroot-Gruppe; keine automatische Sollgruppe für neue private Ordner |
| Andere Eigentümer/Gruppen | Nicht stillschweigend zulässig; bei Abweichung stoppen, keine automatische chown-/Gruppenreparatur |
| Modus neuer privater Verzeichnisse | **0700**, ohne SGID/SUID/Sticky-Sonderbits; restriktive Erzeugungsmaske 0077 |
| Spätere Dateien | 0600 gemäß Releasevertrag, aber in einer reinen Verzeichnisanlagephase noch keine Dateien |
| Gesamtes anfängliches Planbudget | Höchstens **64 MiB / 67108864 Byte**; nicht pro Unterverzeichnis und nicht als Vorausallokation |

Die numerische Gruppenrolle ist bislang nicht unabhängig im Hostingpanel
bestätigt; Gruppennamen werden nicht aus einer üblichen Plesk-Installation
erraten. GID 1003 ist der konkrete vorgeschlagene Sollwert. Sollte der Hoster
für private Ordner GID 1002 oder eine andere Gruppe vorschreiben, muss der
Vertrag vor einer Ausführung ausdrücklich angepasst werden. Bestehende
Account- und Systemverzeichnisse bleiben unverändert.

Erforderliche Kontrollen vor und nach einer später erlaubten Anlage:

1. Exakte Host-/Accountidentität, gepinnter Host-Key und dieselbe bestätigte
   SSH-/SFTP-Abbildung; keine automatische Ausweichroute oder Pfadverkürzung.
2. Gesamten notwendigen Vorlauf einzeln mit lstat prüfen; keine Symlinks,
   Nicht-Verzeichnisse, verweigerten Zugriffe oder unerwarteten Eigentümer
   übergehen. Systemvorfahren dürfen ihre nachgewiesenen Systemeigentümer
   behalten; der Account-Vorfahre muss unverändert zum bestätigten Account
   gehören. Keine fremden Ordner inventarisieren.
3. Canonical-Pfadgleichheit und strikte Eingrenzung auf die ausdrücklich
   genannten sechs neuen Verzeichnisse (private, mosa2-collector und vier
   Unterordner) prüfen. Bereits vorhandene unerwartete Objekte nicht übernehmen,
   überschreiben oder „reparieren“. Eine wiederholte Ausführung ist kein Anlass
   für neue Berechtigungsänderungen.
4. Vorab einen aktuellen, kontospezifischen Quota-Nachweis mit wenigstens
   64 MiB zusätzlichem Headroom sowie geklärter Inodegrenze verlangen.
   Bereits belegte gemeinsame Ressourcen und die vereinbarte Reserve
   berücksichtigen; statvfs allein genügt nicht.
5. Den Nachweis aller öffentlichen Pfadabbildungen bzw. eine konkrete
   Hosterbestätigung für diesen Root einholen. Keine bloße Ordnerbezeichnung
   oder .htaccess-Datei als Ersatz verwenden.
6. Eine spätere Implementierung muss Symlink-/Austauschrennen beim
   pfadgebundenen Anlegen verhindern und anschließend numerischen Eigentümer,
   Gruppe, Typ, exakten Modus 0700 und Pfadzuordnung unabhängig zurückprüfen.
   Bei Abweichung stoppen; kein rekursives chmod/chown und kein Aufweichen
   bestehender Vorfahren.

Eine spätere Freigabe muss sowohl den fehlenden Zwischenordner private als
auch den MOSA-2-Root und die vier Unterordner, Soll-UID/GID, Rechte und
Budget ausdrücklich benennen. Sie darf nicht als Upload-, Collector-,
Provider- oder DB-Schreibfreigabe ausgelegt werden.

### Vorbereitete Fragen an Dogado – NICHT VERSANDT

Die folgenden Fragen sind ein Entwurf für eine spätere, vom Nutzer veranlasste
Hosteranfrage. Codex hat keine Anfrage oder Nachricht abgesendet.

1. Gilt für das bestehende WEB-M-3.0-Abonnement aktuell weiterhin ein Limit
   von 150 GB? Wie hoch sind derzeit abrechnungsrelevante Belegung und freie
   Account-Quota, jeweils mit Einheit, Messzeitpunkt und Hard-/Soft-Limit?
   Welche Anteile aus Webspace, Datenbanken, Mail, Backups, Logs und temporären
   Dateien werden gezählt? Warum unterscheiden sich oneHome- und Plesk-Werte?
2. Gibt es eine Datei-/Inodegrenze für dieses Abonnement, wie hoch ist sie und
   wie viel ist belegt? Sind mindestens zusätzliche 64 MiB und die für ein
   kleines versioniertes Collector-Paket samt begrenzten Laufdaten benötigten
   Inodes innerhalb der bestehenden Quota nutzbar?
3. Darf web213 unter
   /var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector
   einen ausschließlich privaten CLI-Anwendungsbereich anlegen? Ist der
   Zwischenordner private frei nutzbar oder plattformseitig reserviert/
   verwaltet? Welchen bestehenden Benutzer-/Gruppenkennungen und Rechten
   müssen diese neuen Ordner entsprechen? Ist 10317:1003 mit 0700 zulässig?
4. Können Sie für genau diesen Pfad bestätigen, dass er außerhalb **aller**
   öffentlich eingebundenen Document Roots dieses Abonnements liegt und weder
   durch Domains/Subdomains/Aliase noch durch Apache-/nginx-Aliase,
   Weiterleitungen, Bind-/Pfadabbildungen oder öffentliche Dateidienste direkt
   ausgeliefert wird? Bitte die Account-Zuordnung administrativ bestätigen,
   ohne Websiteinhalte anderer Domains bereitzustellen oder zu verändern.
5. Gibt es für diesen privaten Bereich zusätzliche Hostingbedingungen,
   automatische Lösch-/Berechtigungsprozesse oder Einschränkungen für die
   bereits verfügbaren CLI-Interpreter
   /opt/alt/python311/bin/python3.11 und /opt/plesk/php/8.4/bin/php?
   Bitte auch die gemeinsame UID-Grenze zu vorhandenen PHP-Webanwendungen
   erläutern; eine neue Benutzeranlage ist nicht gewünscht.

### Empfehlung und Prüfabschluss

**Die Verzeichnisanlage jetzt noch nicht freigeben.** Der vorgeschlagene
Speicherort bleibt technisch plausibel, aber aktuelle Account-Quota,
Inodebedingungen, zulässige neue GID und vollständige öffentliche Isolation
sind noch offen. Erst nach deren Bestätigung kann ein eng begrenzter
Anlageauftrag für die oben genannten Pfade formuliert werden. Im vorliegenden
Auftrag wird niemand zur Anmeldung, Passwortübergabe oder Klickaktion
aufgefordert.

Geändert wird ausschließlich diese Dokumentation. Geprüft wurden
Quellen-/Datumszuordnung, Trennung historischer und aktueller Werte,
64-MiB-Umrechnung, Soll-/Ist-Eigentümervertrag, unveränderte bisherige
Dokumentation und der auf genau eine Datei begrenzte Git-Diff.
Mangels Codeänderung sind keine zusätzlichen Laufzeit-/Actions-Tests nötig.
Der frühere 11/11-Sicherheitstest ist ein historischer Nachweis, kein neuer
Testlauf dieses Auftrags.

Keine Verzeichnisanlage, kein Upload, keine gespeicherte Plesk-Änderung,
kein SSH-/SFTP-/DB-/Provider-/Collector-Lauf und keine Hosteranfrage.
Privates Deployment und Ausführung bleiben technisch gesperrt.


## Praktische Plesk-Prüfung: Verzeichnisanlage empfohlen (21.10.2026)

Die bestehende Chrome-Erweiterungsverbindung und die vorhandene oneHome-/
Plesk-Anmeldung wurden jetzt erfolgreich genutzt, ohne neue Browserinstanz,
Passwort oder Nutzeraktion. Die zuvor offene Browserprüfung ist damit erledigt.
Gelesen wurden nur Account-/Hosting-Metadaten; keine Dateimanager, Websiteinhalte
oder Datenbanken geöffnet, keine Einstellungen gespeichert.

**Öffentliche Pfadzuordnung: PASS im Umfang aller in der Plesk-Übersicht
ausgewiesenen Zuordnungen.** „Websites & Domains“ zeigte vollständig 8 Elemente,
passend zu den Ressourcenangaben 6 Domains und 2 Subdomains. Die angezeigten
Verzeichnisse („Dateimanager unter“, ohne diesen zu öffnen), relativ zum bereits
bestätigten Accountpfad, waren:

| Plesk-Eintrag | Öffentlich zugeordnetes Verzeichnis |
| --- | --- |
| handel.scharwerk.de | httpdocs/handel.scharwerk.de |
| privat.scharwerk.de | httpdocs/privat.scharwerk.de |
| scharwerk.de | httpdocs/scharwerk.de |
| mosa.scharwerk.de | mosa.scharwerk.de |
| mosa2-test.scharwerk.de | mosa2-test.scharwerk.de |
| schmitfranz.de | httpdocs/schmitfranz.de |
| web213.server10.configcenter.info | httpdocs |
| zen.scharwerk.de | httpdocs/zen.scharwerk.de |

Für die Account-Hauptdomain wurde zusätzlich das Dokumentstammfeld httpdocs
in den Hosting-Einstellungen gelesen. Damit liegt der geplante Root
/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector
außerhalb sämtlicher oben ausgewiesener öffentlicher Verzeichnisbäume.
Keine angezeigte Zuordnung bindet private oder mosa2-collector öffentlich ein.
Versteckte serverweite Alias-/Bind-/Proxyregeln sind damit nicht vollständig
auditiert; eine solche tatsächliche Einbindung wurde aber auch nicht festgestellt.
Dies ist keine Behauptung absoluter Isolation gegenüber jeder denkbaren URL.

**Speicherplatz: 64 MiB plausibel nutzbar.** Plesk zeigte aktuell WEB M 3.0,
8262,2 MB genutzt von 150 GB; in den Webspace-Einstellungen ist das
Datenträgerkontingent aktiviert und mit 153600 MB angegeben. Innerhalb dieser
Plesk-Anzeigen verbleiben rechnerisch 145337,8 MB. Die vom Nutzer bereits
bestätigte aktuelle oneHome-Anzeige beträgt 7,58 GB von 150 GB, also dort
rechnerisch 142,42 GB Reserve. Die unterschiedlichen Anzeigen werden nicht
gleichgesetzt. Beide sprechen deutlich für ausreichenden Spielraum für das
gesamte anfängliche MOSA-2-Budget von 64 MiB = 67108864 Byte. Das ist eine
praktische Kapazitätsbewertung, keine Vorausreservierung. Ein Inode-Limit wurde
in der gelesenen Ressourcenansicht nicht ausgewiesen; es bleibt unbekannt,
ohne dass ein konkreter Inode-/Quota-Fehler beobachtet wurde.

**Benutzerrechte: kein konkreter Anlageblocker.** Plesk bestätigt web213 als
Systembenutzer, gemeinsame Webspace-Einstellungen für 8 Domains und
/bin/bash (chrooted). Hosting-Verwaltung und SSH-Verwaltung sind erlaubt.
Numerische Gruppen zeigt diese Oberfläche nicht. Der vorhandene Nachweis
10317 als UID, primäre GID 1003 und Account-Vorfahre 10317:1002 / 0710 wird
übernommen und nicht erneut per SSH getestet. Der Eigentümer besitzt damit
am vorhandenen Account-Vorfahren die erforderlichen POSIX-Verzeichnisrechte.

Für einen später ausdrücklich genehmigten Anlageauftrag gilt weiterhin:
neue private Verzeichnisse 10317:1003 / 0700, einschließlich des fehlenden
Zwischenordners private, des Roots mosa2-collector und ausschließlich seiner
vier initialen Unterordner releases, staging, runs und locks. Vor Anlage
Identität/Pfad/Vorfahren prüfen, danach tatsächliche Eigentümer, Gruppe und
Modi zurückprüfen. Bei anderer Gruppe, Symlink, unerwartetem Objekt,
Zugriffs-/Quota-Fehler stoppen; keine automatische chown-/Rechtekorrektur.

Verbleibende tatsächliche Betriebsgrenze ist die gemeinsame UID: vorhandene
Webanwendungen mit derselben UID können durch 0700 nicht voneinander isoliert
werden. In der gelesenen Apache-/nginx-Ansicht der Account-Hauptdomain war
„Fähigkeit, symbolischen Verknüpfungen zu folgen, einschränken“ nicht aktiviert;
das allein belegt keine bestehende Verknüpfung zum privaten Ziel. Künftige
öffentliche Symlinks/Zuordnungen zum privaten Bereich müssen vermieden werden.
Keine Webserver- oder sonstige Sicherheitseinstellung wurde geändert.
Nicht sichtbare Serverregeln und Inodegrenzen bleiben unbestätigt, sind für
die reine kleine Verzeichnisanlage aber keine nachgewiesenen Blocker.

**Empfehlung: VERZEICHNISANLAGE FREIGEBEN**, eng auf die genannten sechs Ordner,
0700, den Eigentümervertrag und insgesamt maximal 64 MiB begrenzt. Die vorherige
pauschale Zurückstellung bis zu einer Hosterantwort wird für diese Testphase
durch die aktuelle praktische Bewertung ersetzt. Kein Kontakt zu Dogado nötig,
solange die spätere Anlage ihre normalen Pfad-/Eigentümer-/Fehlerkontrollen
besteht. Diese Empfehlung führt selbst noch keine Anlage aus und erteilt
weder Upload- noch Collector-Freigabe; das Deploymentprofil bleibt gesperrt.

Keine zusätzlichen SSH-/Actions-Läufe, Laufzeit- oder Paketwiederholungstests.
Nur dieser neue Dokumentationsabschnitt; Konsistenz der acht Zuordnungen,
Pfadüberschneidungen, Budgetrechnung und auf eine Datei begrenzter Diff geprüft.
Die beiden Einstellungsansichten wurden ohne Speichern über Abbrechen verlassen.


## Freigegebene private Verzeichnisanlage: PASS (21.10.2026)

Die ausdrückliche Nutzerfreigabe wurde ausschließlich für die sechs unten
aufgeführten Verzeichnisse umgesetzt. Basis:
    /var/www/vhosts/web213.server10.configcenter.info

| Relativer Pfad | UID:GID | Rechte | Device:Inode | Anlage / unmittelbare Prüfung / unabhängiger Readback |
| --- | --- | --- | --- | --- |
| private | 10317:1003 | 0700 | 64768:97002064 | PASS |
| private/mosa2-collector | 10317:1003 | 0700 | 64768:97002065 | PASS |
| private/mosa2-collector/releases | 10317:1003 | 0700 | 64768:97002066 | PASS |
| private/mosa2-collector/staging | 10317:1003 | 0700 | 64768:97002067 | PASS |
| private/mosa2-collector/runs | 10317:1003 | 0700 | 64768:97002068 | PASS |
| private/mosa2-collector/locks | 10317:1003 | 0700 | 64768:97002069 | PASS |

**6/6 PASS:** reguläre Verzeichnisse, keine Symlinks, exakte kanonische Pfade,
UID 10317, GID 1003, Modus 0700. Der Prozess setzte umask 0077. Das spätere
Gesamtbudget bleibt 64 MiB / 67108864 Byte; keine Quotaänderung oder
Speichervorausallokation wurde vorgenommen.

[Actions-Nachweis 39577244026](https://github.com/masterxfix/MOSA-2/actions/runs/39577244026),
geprüfter Stand cc815d059e6041575caff6687a3fc04aefb5c4df.
**11/11 Offline-Sicherheitstests PASS**, danach genau ein Remote-Anlageaufruf.
Der vorgelagerte Lauf 39577132312 scheiterte an einem SFTP-Kontextmanager-
Testdouble und übersprang den gesamten Remote-Schritt. Nach dessen Korrektur
wurde der Sicherheitsblock vollständig wiederholt; keine Anlage wurde wiederholt.

Die Routine collector_private_directories.py verwendet den bestehenden
festen SSH-Account-/Serververtrag und gepinnten Host-Key. Vor der Anlage wurden
reale/effektive UID/GID, cwd, der unveränderte Account-Vorfahre
10317:1002 / 0710 sowie Device/Inode 64768:5248112 überprüft. Die festen Ziele
überschneiden sich nicht mit den drei öffentlichen Hauptbäumen httpdocs,
mosa.scharwerk.de und mosa2-test.scharwerk.de, die sämtliche acht zuvor in Plesk
gelesenen Zuordnungen umfassen. Keine erneute Domain-/Websiteinventur.

Nur sechs exklusive, nichtrekursive mkdir-Aufrufe. No-follow-Verzeichnisdeskriptoren
und erneutes Öffnen des geprüften Elternpfads vor jedem mkdir begrenzen die
Operation; vorhandene Ziele, Symlinks, fremde Eigentümer, Pfaddrift und
OS-Fehler führen zum Stopp. Jedes neue Verzeichnis wurde sofort geprüft.
Keine chmod-/chown-Reparatur, Löschung, Wiederholungs- oder Weiterlaufautomatik.

Anschließend wurden die sechs Verzeichnisse durch einen neuen Python-Prozess
über eine zweite, erneut Host-Key-geprüfte SSH-Verbindung unabhängig gelesen.
UID/GID, Modus, Typ, Device/Inode und Pfade stimmten exakt mit der unmittelbaren
Prüfung überein. Ein zusätzlicher SFTP-Metadatenreadback bestätigte alle sechs
Eigentümer-/Gruppen-/Rechtewerte, Verzeichnistyp und kanonischen Pfade.
SSH und Host-Key: für beide Verbindungen PASS. Keine Abweichung am Server.

Die 11 Tests decken exakte Anzahl/Reihenfolge, unmittelbare Kontrolle,
fehlende Freigabe, falsche Identität, Basispfaddrift, vorhandene Objekte,
Symlinks, kanonische Abweichung, Objektwechsel, falsche neue Rechte/UID/GID,
Teilfehler und Kollision ohne Reparatur/Retry, schreibfreien Readback,
strikten SFTP-Scope, zwei unabhängige Verbindungen, unterdrückte private
Fehlermeldungen und weiterhin gesperrten privaten Upload ab.

Der neue Workflow collector-private-directories.yml bleibt auf main manuell,
mit erwartetem Commit, ausdrücklichem Verzeichnis-Freigabetoken,
run_attempt=1 und eigener Nebenläufigkeitssperre. Der temporäre, exakt
branchgebundene Prüftrigger auf codex/private-directories-a15aee wird entfernt,
indem der Prüfbranch auf den Vorauftragsstand zurückgesetzt wird.
Die Prüfcommits werden nicht nach main übernommen. Ein erneuter Anlageversuch
würde bereits am vorhandenen Zwischenordner ohne Änderung abbrechen.

Keine Programm- oder Testdatei übertragen/angelegt; die begrenzten Python-
Befehle liefen dateilos mit -I -B. Keine DB-Verbindung, Provideranfrage,
Collector-Ausführung, Website-/Plesk-Änderung oder Supportnachricht.
Das vorhandene private Deploymentprofil bleibt unverändert gesperrt.

**Nächster Schritt:** separat freizugebendes privates Collector-Deployment
des bereits geprüften Releasepakets mit Staging, Manifestprüfung und
unabhängigem Dateireadback. Die jetzige Verzeichnisfreigabe umfasst weder
diesen Upload noch einen Collector-Lauf.


## Installiertes Release: synthetischer Remote-Offline-Test (21.10.2026)

**Status: teilweise; kein erfolgreicher Remote-Abschlussnachweis.**
Geprüft wurde ausschließlich das bereits installierte Release
`92274a79550b8acd719434459022da6de5261d2e` unter
`/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector/releases/92274a79550b8acd719434459022da6de5261d2e`.
Kein neues Paket, Upload oder Collector-Start.

[Manueller Diagnose-Run 39582990913](https://github.com/masterxfix/MOSA-2/actions/runs/39582990913),
Diagnosequellstand `2b4c8c8dd0a133bcf7aa927f06d217506e5599ff`, run_attempt=1.
Vor dem einzigen Remote-Test führte der bestehende SFTP-Readback eine vollständige
Dateisatz-, Eigentümer-, Rechte- und SHA-256-Prüfung der 33 Dateien / 248.105 Byte
erfolgreich durch. Dies ist durch den anschließend erreichten Remote-Testpfad
belegt; der damalige Fehlerpfad gab den bereits erfolgreichen Readback leider
nicht im Abschluss-JSON aus. Paket-SHA-256:
`73e34c8d8e13ce37265ef5dded1ceae162140eee5b17341b23ee7dae3e3a68f7`.

Die dateilos über SSH ausgeführte Prüfroutine brach mit PermissionError ab.
Der damalige Treiber reduzierte den Remote-Fehler auf
`REMOTE_TEST_REJECTED:PermissionError`; der genaue Remote-Abbruchpunkt wurde
nicht erhalten. Daher sind PHP-/Python-Modulprüfung, Zusammenarbeit, Normalizer,
INSERT-Plan, Replay und Referenzvergleich auf Dogado **nicht abschließend
nachgewiesen**. Auch ein abschließender Hash-Readback aus dem Testprozess liegt
nicht vor. Daraus folgt kein belegter Fehler im installierten Collector.

Ein Fehler der Prüfroutine wurde offline nachgewiesen und korrigiert:
Der Python-Audithook behandelte das Öffnen bereits vorhandener anonymer
STDIN-Pipe-Dateideskriptoren wie eine Dateischreiboperation. Die Ausnahme gilt
nun ausschließlich für als FIFO geprüfte numerische Deskriptoren. Schreibende
Dateipfade und reguläre Dateideskriptoren bleiben gesperrt. Der Treiber erhält
künftig strukturierte Remote-Fehler samt schon bestandenem SFTP-Readback.
Diese Korrektur wurde **nicht erneut auf Dogado ausgeführt**.

[Rein lokale Sicherheitsprüfung 39583400808](https://github.com/masterxfix/MOSA-2/actions/runs/39583400808):
12/12 Tests PASS. Enthalten sind tatsächliche PHP-STDIO-Aufrufe unter aktivem
Audithook, bestehende synthetische Frankfurt-/Yahoo-GBX-Referenzen, normative
Unit-Definitionen, INSERT und DUPLICATE_UNCHANGED, exakte kanonische Bytes und
Dedupe-Schlüssel sowie Hash-/Dateisatz-/Symlink-/Modus-, Netzwerk- und
Prozessgrenzen. Die erste Testvorbereitung hatte lokale Zwischenverzeichnisse
mit falschem Modus erzeugt; Run 39582628861 stoppte deshalb vor dem Remote-Schritt.
Insgesamt wurde genau **ein** Remote-Offline-Test ausgeführt.

Der Diagnoseweg verwendet die vorhandenen SSH-/Host-Key-Komponenten, keinen
DB-Tunnel und kein DB-Secret. Remote-Python: festes Python 3.11.17 mit -I -B;
PHP und verschachtelte Wertadapter: festes PHP 8.4 mit -n, deaktivierten Logs,
Dateicaches, URL-Zugriffen sowie schreibenden/Netzwerkfunktionen. PHP-Includes
werden als Bibliotheken geladen; das unbedingte Main des Frankfurt-
Requestdeskriptors wird nur syntaktisch geprüft. Keine Provider-/HTTP-Anfrage,
DB-Verbindung oder DB-Schreiboperation im ausgeführten Testpfad; keine
Observation-, Current-/Bars-, Hosting- oder Releaseänderung. Prozessanzahl,
CPU, Speicher, Dateischreibgröße, Ausgabe und Gesamtlaufzeit sind begrenzt.

Der separate Diagnoseworkflow bleibt ausschließlich manuell und
commitgebunden. Der temporäre Kontrollbranch wird auf den Vorauftragsstand
zurückgesetzt. Kein zweiter Remote-Versuch innerhalb dieses Auftrags.
**Offen:** ein separat beauftragter Remote-Offline-Test mit dem korrigierten
Prüfharness; noch keine Freigabe eines echten Collector-Laufs.


## Remote-Funktionsnachweis des installierten Releases abgeschlossen (21.10.2026)

**PASS:** [Actions-Run 39584169023](https://github.com/masterxfix/MOSA-2/actions/runs/39584169023).
Neuer workflow_dispatch auf main, Diagnose-Commit
`8adcef6f643ff70cdab8053c082b066c4d927da5`, run_attempt=1.
Der bestehende Workflow collector-remote-offline.yml wurde unverändert genutzt:
zuerst 12/12 relevante Sicherheits-/Referenztests PASS, danach genau ein
Remote-Offline-Test. Keine Wiederholung oder isolierter Ersatztrigger.

Ausschließlich installiertes Release
`92274a79550b8acd719434459022da6de5261d2e`:
unabhängiger SFTP-Readback aller 33 Dateien / 248.105 Byte einschließlich
vollständigem Dateisatz, SHA-256, UID/GID 10317:1003 und Modi 0700/0600 PASS.
Die vollständigen Integritätsprüfungen im Testprozess vor **und nach** dem
Funktionstest sind ebenfalls PASS. Das Release blieb unverändert.

| Prüfung auf Dogado | Ergebnis |
| --- | --- |
| Python 3.11.17, 12 Paketmodule und Herkunft der Imports | PASS |
| PHP 8.4.12, Syntax aller 18 PHP-Dateien | PASS |
| 17 PHP-Bibliotheken mit vollständiger Include-Menge | PASS |
| PHP → Python und Python → fest gepinntes PHP | PASS |
| Normative Unit-Definitionen und bestehender Normalizer | PASS |
| WriterPlanner: zwei synthetische INSERT-Pläne im Speicher | PASS |
| Replay beider Fälle: DUPLICATE_UNCHANGED | PASS |
| Kanonische Bytes, Dedupe-Schlüssel und Offline-Referenzen identisch | PASS |

Die vorhandenen synthetischen Frankfurt-/EUR- und Yahoo-/GBX-Fälle verwenden
dieselbe generische Normalizer-/WriterPlanner-Logik. Keine Asset-Sonderlogik.
Die Dedupe-Schlüssel sind `9ca94b0d411dc5c7909a298cc96a9a993387b3cf5ea0dcb63303ba1859d0bde0`
und `735d68d152e0842a6b94b7f88e9bb24c63c240fe6064d2727bd80192d5eeb267`.
40 verschachtelte PHP-Wertadapteraufrufe liefen mit den vorgeschriebenen Pins
und deaktivierten Logs/Caches erfolgreich. Die zuvor korrigierte
STDIN-Pipe-Ausnahme ist damit erstmals auf Dogado bestätigt.

SSH und gepinnter Host-Key PASS. Abschlussbericht:
database_connections=0, provider_requests=0, remote_files_written=0;
auch der Python-Audithook registrierte keine blockierten Netzwerk- oder
Dateischreibversuche. Kein DB-Secret übergeben, kein Tunnel, HTTP-/Provider-
Aufruf, Upload, Paketinstallation, echter Collector-Start, Scheduler oder
Produktionszugriff. Der Testcode lief nur im Speicher; keine Observation-,
Current-/Bars- oder Releaseänderung.

Der frühere offene Remote-Offline-Nachweis ist damit abgeschlossen.
**Nicht geprüft:** echte Providerakquisition, DB-Persistenz und vollständiger
Collector-Livebetrieb auf Dogado. **Nächster Schritt:** einen begrenzten
Dogado-Livetest separat freigeben und vorbereiten; dieser Auftrag führt ihn
nicht aus. Nur Dokumentation geändert, keine Laufzeit- oder Workflowänderung.


## PNE-Startfehler eingegrenzt und korrigiert (21.10.2026)

Ausgang: [Run 39586524795](https://github.com/masterxfix/MOSA-2/actions/runs/39586524795),
Launcher-Commit 307c718fdd326c51188f3e1f05f0eb7d75ab72a2. Der Supervisor
meldete nach 550,82 ms nur Stop / OUTCOME_UNKNOWN. PHP-Exitcode und stderr
wurden damals nicht erhalten; der historische Exitcode bleibt UNBESTÄTIGT.

**Reproduzierte Ursache:** RLIMIT_AS=256 MiB reicht für den PHP-8.4-Start
mit der vorhandenen normalen Erweiterungskonfiguration nicht aus.
[Einmalige lesende Diagnose 39588668836](https://github.com/masterxfix/MOSA-2/actions/runs/39588668836)
verwendete den bisherigen erzeugten PHP-Bibliothekscode ohne main/perform-
Aufruf auf dem unveränderten installierten Release. Ein einziger harmloser
Remote-Vergleich mit zwei begrenzten Fällen, ohne DB-Passwort im Testprozess:

| Virtueller Adressraum | PHP 8.4.12 | Ergebnis |
| --- | --- | --- |
| bisher 256 MiB | Exit 254 | PHP_ADDRESS_SPACE_EXHAUSTED |
| korrigiert 1024 MiB | Exit 0, kein stderr | Start und PDO-MySQL-Verfügbarkeit PASS |

Der Supervisor setzt künftig 1 GiB als weiterhin endliche **virtuelle**
Adressraumgrenze. Das reserviert weder 1 GiB physischen Speicher noch
Hosting-Speicherplatz. PHP memory_limit=128M, CPU=45 s, Prozessdeadline=120 s,
Dateischreiblimit=1 MiB, Ausgabegrenze=64 KiB, Prozessgruppenbeendigung und
alle Einmal-/Integritätsprüfungen bleiben unverändert. Keine Änderung der
installierten Collector-, Normalizer-, Writer- oder Dedupe-Implementierung.

Fehlerberichte verwenden eine geschlossene Liste fester Codes und enthalten
Prüfbedingung, Fehlerphase, PHP-Prozessstart, Exitcode (sonst null),
Providerstart gemäß geprüftem Verbrauchsmarker sowie Commit-Zustand
bestätigt / nicht bestätigt / unbekannt. Unbekannte Fehlermeldungen werden
generisch unterdrückt; weder stderr, Stacktraces, SQL noch beliebige
Exceptiontexte werden veröffentlicht. OUTCOME_UNKNOWN bleibt bei unklarem
Prozess-/Commit-Ausgang erhalten. Der PHP-Startweg filtert auch interne
Prüfmeldungen, statt ungeprüfte Exceptiontexte weiterzureichen.

**Unabhängige Test-DB-Prüfung:** separater PHP-Prozess und SSH-Kanal mit
bestehendem DB-Secret ausschließlich über stdin. Feste Server-/Account-
Identität PASS; ausschließlich READ-ONLY-Transaktion, SELECT/Metadaten und
Rollback, keine Business-Writes. Asset-ID 528, 18 Observations insgesamt;
PNE hat genau vier bestehende IDs: 4898, 4899, 4902, 4907. Alle created_at
liegen am 20.10.2026; letzte PNE-Observation 4907 um 21:23:40.699693 UTC,
bereits im erfolgreichen 5-Asset-Run 39498807003 dokumentiert.
Keine gegenwärtige Observation weist auf einen Commit des Versuchs vom
21.10. hin. Current: insgesamt zwei Zeilen, davon eine für PNE mit
observed_at 20.10.2026 13:51:39.324776 UTC. Bars: null Zeilen.
SHA-256 des lesend erfassten Gesamtbestands:
Observations 6cfecab68a2836d9855eecee0bf753f523c320396d86e7333c1bcc1f62e47095,
Current 93d449cac9dc8a863777f9b210ce73574d5c0b681001b6bdc3778283cb69af2d,
Bars 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945.
Ein vollständiger Vorher-Hash des gescheiterten Versuchs fehlt:
historische Gleichheit aller Werte und dessen endgültiger Commit-Zustand
bleiben ausdrücklich UNBESTÄTIGT; der alte OUTCOME_UNKNOWN-Beleg wird
nicht rückwirkend zu FAILED geändert.

Das vorhandene deterministische PNE-Laufverzeichnis wurde nur gelesen.
Enthalten: job.lock, started.json und result.json; kein live-manifest.json,
kein provider-consumed.lock. started/result bestätigen den alten Commit
und Stop / OUTCOME_UNKNOWN / provider_requests=0. Dateisatz, Größen,
SHA-256 und Änderungszeiten vor/nach der Diagnose identisch. Keine
Laufdatei angelegt, gelöscht oder überschrieben. Unabhängiger SFTP-
Readback aller 33 Release-Dateien vor/nach der Diagnose: PASS,
248.105 Byte, Hashes, UID:GID 10317:1003, Modi 0700/0600 unverändert.

**Tests:** [abschließender Offline-Run 39588998116](https://github.com/masterxfix/MOSA-2/actions/runs/39588998116),
35/35 PASS. Erzeugter PHP-Code: Syntax und harmloser Bibliotheksstart PASS;
feste Fehlercodes, Exitcodes/Startphasen, Secret-Canaries, unbekannte
Ergebnisse, kein Retry, unveränderte bestehende Laufdaten und
Adressraum-/Heap-/CPU-/Datei-/Ausgabegrenzen geprüft. Bestehende Runtime-
Regressionen für INSERT/Dedupe, Readback, Drift, Konflikte, Rollback und
Current/Bars ebenfalls PASS. Offline-PHP 8.4.26; der getrennte
Dogado-Startnachweis verwendete das gepinnte PHP 8.4.12/Python 3.11.17.

In diesem Auftrag: genau ein harmloser Remote-Startvergleich und eine
separate lesende DB-Prüfung; null Collector-Aufrufe, Providerrequests,
Business-Writes oder Remote-Dateischreibvorgänge. Bestehende Secrets und
Host-Key-Pinning wiederverwendet. Der temporäre manuelle Diagnoseworkflow
wird zurückgenommen; keine dauerhafte Workflowänderung. Der korrigierte
Code wurde anschließend ausschließlich offline geprüft.

**Grenze:** PHP-Startfähigkeit ist nachgewiesen, ein vollständiger
korrigierter Live-Durchlauf nicht. Der bestehende Einmallauf bleibt
absichtlich durch sein unverändertes Laufverzeichnis gesperrt
(RUN_ALREADY_EXISTS); keine automatische Wiederfreigabe und kein neuer
PNE-Livetest in diesem Auftrag. Ein künftiger separat freigegebener
Versuch muss diese Sperre und die erhaltene Historie berücksichtigen.


## Zweiter begrenzter PNE-Livetest: eigener commitgebundener Startweg (21.10.2026)

Separate ausdrückliche Freigabe für PNE AG / DE000A0JBPG2: genau ein
Providerrequest, höchstens eine Observation, kein Retry. Unverändertes
installiertes Release 92274a79550b8acd719434459022da6de5261d2e; vorhandener
generischer Runtime-, Normalizer-, Writer-, Dedupe- und Readback-Pfad.
PHP 8.4.12, Python 3.11.17, RLIMIT_AS 1 GiB und PHP-Heaplimit 128 MiB bleiben
gepinnt. Kein Upload und keine Veränderung des ersten Versuchs.

Der neue manuelle Start verlangt MOSA2-PNE-SECOND-LIVE-20261021:<source-commit>,
exaktes main/Checkout, run_attempt=1. Laufbereich ausschließlich
runs/second-live-PNE-DE000A0JBPG2-<vollständiger-source-commit>, exklusives
mkdir, job.lock und bestehender identifier_lock vor Providerkontakt.
Kollisionen stoppen; keine automatische Wiederholung oder Bereinigung.

Vor der Akquisition: bestehende DB-Identitäts-, Schema-/Ledger-/Unit- und
USE_EXISTING_ROUTE-Prüfungen. Neuer ausschließlich privater preflight.json-
Beleg (0600, exklusiv, fsync) enthält Observation-IDs, Zeilenzahlen sowie
Prüfsummen des unmittelbar gelesenen Ausgangszustands, keine Passwörter
oder Rohkurse. Bestehende vier Prüfstellen vergleichen Current/Bars,
Katalog, Units und alle alten Observations vollständig; höchstens eine
neue Observation der qualifizierten PNE-Route. Unabhängiger Readback und
Replay bleiben erhalten. Release und historische Laufdateien erhalten
zusätzlichen unabhängigen SFTP-Vorher-/Nachhervergleich.

Das Actions-Ergebnis dokumentiert Ausgangs- und End-IDs, Commit/Dedupe,
Readback/Replay, Integrität und gemessene Zeiten getrennt: Vorbereitung,
SSH, SFTP, Remote-Supervisor, lokaler Collector einschließlich Provider,
Providerzeit, DB-Prüfstellen und gesamter Treiber. Supervisor-Aufwand
ist die Differenz zwischen gemessener Remote-Dauer und PHP-Gesamtdauer,
keine separate CPU-Messung. Der historische Wert 37,6 s ist ein
Referenzvergleich bei anderem Abrufzeitpunkt und damals fünf Assets;
der lokale Lauf enthält zusätzliche vollständige Zustandsprüfungen.
Actions-/SSH-/SFTP-Zeiten gehören nicht zum Collector-Geschwindigkeitsvergleich.

Der Abschluss-Commit wird vor genau einem neuen manuellen Liveversuch
geprüft und auf main veröffentlicht. Der vollständige Livebeleg verbleibt
im [manuellen PNE-Workflow](https://github.com/masterxfix/MOSA-2/actions/workflows/collector-dogado-pne.yml);
diese Vorbereitung behauptet noch keinen erfolgreichen Liveausgang.
Nach dem Versuch keine weiteren Codeänderungen oder erneute Akquisition.


## Gemeinsamer Dogado-Aktienstart für 1–10 Assets, nur offline vorbereitet (21.10.2026)

Der erfolgreiche historische PNE-Nachweis bleibt unverändert:
[Run 39590396752](https://github.com/masterxfix/MOSA-2/actions/runs/39590396752),
Commit 73643c2e397549c1799624c2653c8959654a5b3d, INSERT 4908,
Readback PASS, Replay DUPLICATE_UNCHANGED, lokale Collector-Dauer 4,31 s.
Er beweist nicht die Livefunktion des hier neu vorbereiteten Mehrfachstarts.
Installiertes Release weiterhin ausschließlich
92274a79550b8acd719434459022da6de5261d2e, 33 Dateien / 248.105 Byte.

**Gemeinsame Komponenten:** dogado_runtime.php enthält die aus dem PNE-
Startweg herausgezogenen Prüf-, Prozess-, Audit- und Startfunktionen.
Der PNE-Einstieg delegiert mit denselben Pins und Verträgen an diese
Bibliothek; seine bisherige Schnittstelle bleibt verfügbar. Batch und
Einzelstart verwenden dieselben Funktionen. Keine zweite Normalizer-,
Writer-, Dedupe-, SQL- oder Transaktionsimplementierung:
MarketBatch::prepare/execute aus dem installierten live_batch.php
koordiniert weiterhin sequentiell; MarketLive::runtimeRun aus
runtime_persistence.php übernimmt Transaktion, Writer, unabhängigen
Readback und Replay. Der bestehende Proof Mode bleibt unverändert.

Konfiguration ist eine geordnete JSON-Liste von 1 bis 10 ISINs, keine
fest eingebaute Aktienliste. Die vollständige Auswahl wird vor dem
ersten Providerrequest gegen den authentifizierten DB-Snapshot geprüft:
globale Identität, asset_class=equity, bestehender qualifizierter Source,
USE_EXISTING_ROUTE, vorhandene Route, Ledger, Schema und Unit-Bindung.
ETFs, Duplikate, unbekannte Assets, neue Routen oder Konflikte stoppen den
gesamten Start vor Akquisition. Der übernommene Manifest-/Providervertrag
ist der bereits qualifizierte Frankfurt-Snapshot-Pfad; andere vorhandene
Routen werden nicht stillschweigend auf diesen Vertrag umgestellt.

Jedes Asset erhält ein eigenes privates asset-NN-Verzeichnis und sein
unveränderliches Manifest. Vor jeder Akquisition erfolgt erneut der
vollständige Abgleich mit dem erwarteten Zustand: am Anfang dem globalen
Preflight, danach dem exakt bestätigten Endzustand der vorherigen Aktie.
Es gibt keinen Cache veränderlicher Schema-, Ledger-, Unit- oder Route-
Prüfungen. Vier Auditpunkte einschließlich unabhängigem Readback erhalten
Current/Bars, Katalog und sämtliche Bestandszeilen; pro Aktie höchstens
eine neue Observation. Ein Providerbudget und Verbrauchsmarker gelten
je Asset. Beim ersten Fehler stoppt der bestehende Coordinator, spätere
Assets bleiben NOT_STARTED; frühere Commits bleiben erhalten.
OUTCOME_UNKNOWN wird einschließlich bestätigter Teilcommits ausdrücklich
erhalten, auch wenn die Coordinator-Ergebnisverarbeitung ausfällt.

**Supervisor:** vorhandene Guard-, Metadaten-, exklusive Datei-, Prozess-
gruppen-, Deadline-, Ausgabe- und sichere Fehlercodefunktionen werden
direkt aus der gemeinsamen bestehenden Supervisorquelle wiederverwendet.
Laufkennung bindet vollständigen Quellcommit, validiertes Laufetikett und
SHA-256 der geordneten Auswahl:
runs/batch-<commit>-<run_id>-<selection-hash-prefix>.
Exklusives mkdir, globaler nichtblockierender collector-batch.lock unter
locks/ und bestehender DB-Identifier-Lock verhindern Wiederverwendung und
Überschneidungen. Keine alte Laufdatei oder kein Verbrauchsmarker wird
gelöscht oder überschrieben. UID:GID 10317:1003, Verzeichnisse 0700,
Dateien 0600, no-follow-Pfadprüfung und umask 0077 bleiben verbindlich.
Python 3.11.17/PHP 8.4.12, 1 GiB virtueller Adressraum, PHP-Heap 128 MiB,
höchstens 120 s Deadline und 45 s CPU je angeforderter Aktie, maximal
1200 s/450 s pro Batch, 64 KiB Ausgabe, 1 MiB je geschriebener Datei.
DB-Passwort ausschließlich über geschütztes stdin, keine dauerhafte
Credentialdatei und keine Secretwerte in Bericht oder Paket.

**Release-Integrität und Startaufwand:** Der Actions-Treiber verifiziert
zunächst das reproduzierbare Paket/Manifest des unveränderten installierten
Release-Commits gegen den vorhandenen Deploymentbeleg. Auf Dogado prüfen
dieselben bestehenden Integritätsfunktionen vor und nach dem gesamten
Batch alle 33 Dateien einschließlich Dateisatz, SHA-256, Größe, Owner,
Modus, Pfad und Symlinks gegen dieses vertrauenswürdige Manifest.
Hashfehler stoppen, nach bereits gestartetem Batch konservativ mit
OUTCOME_UNKNOWN. Der normale Batch-Treiber öffnet keinen SFTP-Kanal.
Vollständige unabhängige SFTP-Audits bleiben über den bestehenden
deploy_private_collector.readback und die vorhandenen separaten
Offline-/Diagnosewege möglich; sie werden nicht je Aktie ausgeführt.

Beim historischen PNE-Lauf benötigten die beiden SFTP-Auditphasen zusammen
80,36 s. Deren Transfer-Roundtrips entfallen im normalen Batchstart;
serverlokale Hashprüfungen bleiben bestehen. Erwartung: dieser bisherige
Startaufwand wird weitgehend vermieden und SSH nur einmal pro Batch
aufgebaut. **Keine neue Live-Messung oder gemessene Beschleunigung**
des Mehrfachstarts in diesem Auftrag; Provider-, Prozess- und Actions-
Zeiten sowie die zusätzliche vollständige Scope-Prüfung bleiben offen.

Berichte enthalten requested/started/completed/not_started/committed,
Providerrequests und erhaltene Marker, INSERT-/DUPLICATE_UNCHANGED-
Entscheidungen, Observation-IDs, Readback, Replay, Fehlercode/-phase,
Collector- und Providerdauer pro Aktie, DB-Prüfzeit pro Aktie und globalem
Scope-Preflight, lokale Batch-Gesamtzeit sowie getrennte Actions-/SSH-/
Supervisorzeiten. INSERT-/Duplicate-Zähler zählen Writerentscheidungen;
committed_count weist davon unabhängig bestätigte Commits aus.
Rohe Zustandsdaten bleiben im Prozessspeicher; öffentliche Ausgaben
enthalten keine Provider-Rohantworten oder ungeprüften Exceptiontexte.

**Offline-Nachweis:** Die bestehenden Tests wurden erweitert und
Fixture-/PDO-/Provider-Doubles wiederverwendet, keine realen DB- oder
HTTP-Verbindungen. Abgedeckt sind 1/2/5/10 Assets (auch mit echtem
bestehendem Normalizer/Writer gegen In-Memory-PDO), Duplikate, ETFs,
unqualifizierte/fehlende Route, Unit-Drift, Provider-/Writer-/Readbackfehler,
INSERT und Dedupe, Teilcommit mit Folgefehler, unbekannte Ergebnisse,
Einmalkollision, Erhalt alter Laufdaten, Current/Bars und Bestandszeilen,
sowie tatsächliche 33-Dateien-Hash-, Fremddatei- und Symlink-Prüfungen.

[Abschließende betroffene Suite 39593243437](https://github.com/masterxfix/MOSA-2/actions/runs/39593243437):
36/36 PASS. Die 19 unveränderten Diagnose-/Runtime-Tests bestanden im
[initialen Gesamtblock 39592819507](https://github.com/masterxfix/MOSA-2/actions/runs/39592819507)
einschließlich tatsächlichem Runtime-Batch mit 10 synthetischen Assets;
dieser erste Block hatte zwei inzwischen korrigierte Testverdrahtungsfehler.
Damit 55/55 relevante Tests abgedeckt. Keine Schutzprüfung abgeschwächt.

**Live bleibt gesperrt:** neuer manueller Workflow collector-dogado-batch.yml
ist commitgebunden. Sein Livejob ist mit konstant false gesperrt; zusätzlich
stehen LIVE_ENABLED im Actions-Treiber und im Remote-Supervisor auf false.
Kein Workflow-Input kann diese Sperren aufheben. Vor späterer Ausführung
sind eine separate ausdrückliche Nutzerfreigabe und eine geprüfte Aktivierung
erforderlich. Die vorbereitete Autorisierung bindet Commit, Laufetikett und
vollständigen Auswahlhash; main, Checkout, Repository und run_attempt=1
werden zusätzlich geprüft. Vorhandene Secrets und Host-Key-Pinning
werden erst im künftig separat freigegebenen Livepfad verwendet.

In diesem Auftrag ausschließlich Repositoryänderungen und Offline-Actions:
null Hostingzugriffe, Providerrequests, reale DB-Verbindungen/-Writes,
Uploads, neue Observations, Scheduler- oder Produktionsänderungen.
Noch nicht live geprüft: neuer Batch-Supervisor, globaler Job-Lock,
refaktorisierte PHP-Integration, serverlokale Vorher-/Nachherprüfung und
tatsächliche Multi-Asset-Laufzeiten. Der PNE-Livebeleg bleibt historischer
Einzelnachweis. Nach Tests und genau einem main-Abschluss-Commit stoppen.


## Einmalige Freigabe des geordneten Drei-Aktien-Tests (21.10.2026)

Ausschließlich PNE AG (DE000A0JBPG2), Carl Zeiss Meditec (DE0005313704),
DroneShield (AU000000DRO2), exakt in dieser Reihenfolge. Höchstens drei
Providerrequests und drei neue Observations; keine automatische Wiederholung.
Gemeinsame generische Verarbeitung und installiertes Release unverändert.

Die zuvor geschlossenen drei Aktivierungsstellen erlauben jetzt allein
diese konkrete Auswahl und den festen Laufnamen
three-equities-20261021-01. Auswahlhash:
1fbae8bd949490a5866efad170ca7b8bd16e26f7cd35823c810b6a8b8e510c84.
Freigabetoken bindet MOSA2-DOGADO-THREE-20261021-01, vollständigen
geprüften Quellcommit, Laufnamen und vollständigen Auswahlhash.
Workflow, Actions-Treiber und Remote-Supervisor prüfen die Bindungen;
zusätzlich GitHub Actions, Repository, workflow_dispatch, main,
run_attempt=1 sowie Checkout-/main-Commit vor SSH. Der Remote-Prozess
prüft den über stdin übergebenen Actions-Kontext ebenfalls.

Das neue Verzeichnis ist exakt runs/three-equities-20261021-01.
Es wird exklusiv angelegt und bindet seinen tatsächlichen Quellcommit
über started.json und den PHP-Quellhash. Anders als eine variable
Commit-Unterordnerkennung verhindert dieser feste Reservierungsname
auch einen zweiten Versuch mit verändertem Quellcommit. Bereits
vorhandenes Verzeichnis bedeutet Stopp; keine Bereinigung oder
Wiederverwendung. Globaler Job-Lock und per-Asset-Verbrauchsmarker
bleiben erhalten. Allgemeiner Livebetrieb, beliebige Auswahl,
andere Laufnamen und automatischer Regelbetrieb bleiben gesperrt.

Zusätzlicher Nachweis alter Laufverzeichnisse: begrenzter serverlokaler
Vorher-/Nachher-Readback ausschließlich unter dem eigenen privaten
runs-Bereich, über no-follow-Directory-Deskriptoren. Die beiden
vorhandenen PNE-Laufverzeichnisse müssen vorhanden sein. Metadaten,
Dateisatz und SHA-256 werden verglichen; keine Datei wird verändert.
Symlinks, Hardlinks, unbekannte Objekttypen, falsche Rechte/Eigentümer,
übermäßiger Umfang oder Änderungen stoppen sicher. Grenzen:
128 Einträge je Verzeichnis, höchstens 128 Unterverzeichnisse,
256 Dateien, 16 MiB gelesene Dateidaten; atime wird
als lesebedingtes Metadatum nicht verglichen. Das neue Verzeichnis ist
vom historischen Vergleich ausgenommen. Keine vollständige SFTP-Runde.

Vor Providerkontakt bleibt die gemeinsame vollständige Identitäts-,
equity-, Route-/Source-/Unit-, Ledger-/Schema- und Zustandsprüfung
aller drei Aktien verpflichtend. Bestehende Transaktionen,
Dedupe/Replay, unabhängige Readbacks und vollständige Bestandsprüfungen
bleiben unverändert. Release-Hashprüfung vor/nach dem Batch.
Bei Fehler stoppen spätere Aktien, bestätigte Commits bleiben erhalten;
unbekannte Ausgänge werden nicht als sicher fehlgeschlagen ausgegeben.

Der Abschluss-Commit wird vor genau einem neuen manuellen Actions-
Versuch geprüft und auf main veröffentlicht. Messwerte und vollständiger
Livebeleg verbleiben im Actions-Run; diese Vorbereitung behauptet
noch keinen Liveerfolg. Danach keine weitere Codeänderung oder
Akquisition. Der historische PNE-Einzellauf und alle alten Marker
werden erhalten. Kein Upload oder Eingriff ins installierte Release.

Offline-Freigabenachweis vor Live: [Run 39594598884](https://github.com/masterxfix/MOSA-2/actions/runs/39594598884), 50/50 PASS. Exakte Aktien/Reihenfolge, Token, Laufname, Commit-/Actions-Kontext, Einmalkollision, alte Laufdaten, Hash-/Symlink-Schutz sowie bestehende Transaktions-/Readback-/Replay-Fehlerfälle geprüft. Keine Hosting-Secrets im Offline-Test.


## Regelbetrieb: deaktivierte Planung und Monitoring (21.10.2026)

Zentrale Datei: config/collector-operation.json, Vertrag
mosa2-collector-operation-plan-v1. Standard execution_enabled=false;
Aktienauswahl, Handelsplatz, freigegebener Kalender, Handelstage/-fenster,
Intervall, Laufdauer und Frischegrenzen sind absichtlich leer/null,
Providerbudgets ohne Freigabe (0). Keine erfundene Handelsfreigabe.
Höchstens zehn zuvor qualifizierte Aktien, equity/USE_EXISTING_ROUTE,
gemeinsamer Handelsplatz und Europe/Berlin. Keine Asset-Sonderregeln.
Der nachgewiesene Drei-Aktien-Test bleibt der historische Livebeleg
[39594892471](https://github.com/masterxfix/MOSA-2/actions/runs/39594892471).

scripts/collector_operation_plan.py ist ausschließlich eine reine
In-Memory-Bibliothek, kein Starter, kein Scheduler und kein Collector.
decide() liefert nur RUN_ELIGIBLE, SKIP oder BLOCKED.
RUN_ELIGIBLE ist ein Simulationsergebnis, niemals Ausführungsberechtigung.
Auch execution_enabled=true ermöglicht keinen Prozessstart.
Workflow-/Treiber-/Supervisor-Sperren, verbrauchte Einmalfreigaben und
das installierte Release bleiben unverändert.

Freigegebene Kalender benötigen Quelle, Version, Gültigkeitsbereich und
explizite offene/geschlossene lokale Datumswerte. Unvollständige,
widersprüchliche oder außerhalb der Gültigkeit liegende Angaben blockieren.
Wochenenden und explizit geschlossene Tage überspringen den Start;
ein Werktag allein reicht nicht. Zeitfenster sind am selben lokalen Tag
start-inklusive/end-exklusive; über Mitternacht reichende und überlappende
Fenster werden nicht unterstützt. ZoneInfo berücksichtigt Berliner
Sommer-/Winterzeit; Fälligkeit und Nachweisalter verwenden absolute UTC-Zeit.

Vor jeder simulierten Freigabe: frische vollständige Scope-Qualifikation,
kein aktiver Lock/ungeklärter Auftrag, neue Laufkennung und bekannter
tagesbezogener Providerbudgetstand. Maximal eine Anfrage je Aktie wird
gegen Lauf-/Tagesbudget geprüft. FAILED/PARTIAL_FAILED/OUTCOME_UNKNOWN
stoppen bis zur ausdrücklichen Prüfung; kein automatischer Retry oder
stilles Zurücksetzen. Veraltete/zukünftige Nachweise blockieren.
Marktfrische ist getrennte Monitoringinformation, keine Handelsfreigabe.

Die Eingaben sind injizierte Simulationsevidenz, keine DB-Prüfung und keine
sichere Lockreservierung. Ein späterer Adapter muss die bestehende
vollständige qualify()/Runtime-Prüfung samt Source-/Route-/Unit-/Schema-
Verträgen wiederverwenden und Lauf-/Budgetreservierung atomar unter dem
bestehenden gemeinsamen Lock prüfen. Zwischen Planung und Akquisition
muss die vollständige Prüfung erneut gelten. Der Planer ersetzt weder
Lock noch Provider-Verbrauchsmarker. Keine Liveanbindung in diesem Auftrag.

monitoring()/project_receipt() projizieren vorhandene batch/item_results-
Belege über eine feste Feldliste: letzter Start/Erfolg, Aktien, Writer-
Entscheidungen, Observation-IDs, bestätigte Providerfehler, Einzel-/Batchzeiten
und feste Fehlercodes. FAILED_BEFORE_FIRST_COMMIT erscheint als FAILED;
unbekannte Teilresultate erhalten OUTCOME_UNKNOWN, auch bei späterem Erfolg.
Nicht zuordenbare Providerfehler bleiben unbekannt. Rohfehler, SQL, Pfade
und zusätzliche Eingabefelder werden nicht ausgegeben. Ausgabe enthält
execution_authorized=false. Start-/Endzeiten kommen aus vertrauenswürdigen
Laufmetadaten; fehlende Marktzeit ergibt UNKNOWN, keine abgeleitete
Datenfrische aus dem Abschlusszeitpunkt. Keine neue DB-Tabelle.
Historische ungeklärte Läufe nur nach gesonderter dokumentierter Prüfung
auflösen; der Planer tut dies nicht.

**Späterer Startweg:** vorhandene Actions-Steuerung → gepinntes SSH →
gepinntes Python/PHP auf Dogado → generischer Batch/Runtime/Normalizer/
Writer/Dedupe/Replay. Ein separat freizugebender Regelbetriebsadapter muss
eindeutige Laufkennungen, privaten runs-Bereich, globalen Supervisor-Lock,
geschütztes stdin, Deadline/Prozessgruppenbeendigung und serverlokale
Releaseintegrität erhalten. Keine Wiederverwendung verbrauchter
Einmal-Token oder alter Laufordner. Genehmigte Laufdauer darf bestehende
Supervisor-Höchstgrenzen nicht überschreiten. Ein späterer periodischer
Actions-Impuls wäre nur ein Wecksignal; Entscheidung vor jedem Start neu
prüfen. Kein Cron/Plesk/Scheduler jetzt angelegt oder aktiviert.
Direkter Hosting-Cron würde zusätzlich eine eigens freizugebende sichere
Secretversorgung benötigen.

**Noch erforderlich:** ausdrückliche Regelbetriebs-Ausführungsfreigabe,
Aktien/Handelsplatz, verifizierter Handelskalender, Tage/Fenster, Intervall,
Providerbudgets, Laufdauer, Evidenz-/Frischegrenzen und geprüfter Startadapter
mit atomarer Job-/Budgetreservierung und belastbarer Statusaufnahme.
Kein Providerkontakt, DB-Zugriff, Upload, Deployment oder Hostingzugriff.

Offline-Suite tests/test_collector_operation_plan.py: deaktivierte Defaults,
1/2/5/10 Aktien, Kalenderlücken/Feiertag/Wochenende, Zeitgrenzen, Sommer-/
Winterzeit/DST, Fälligkeit, Duplikate, Lock/ungeklärte Läufe, Providerfehler,
veraltete Daten/Evidenz, ungültige Auswahl/Budgets, unveränderte Eingaben
und sichere Feldprojektion. Zeitfenster/Freigaben sind rein synthetisch.

**Testergebnis:** 21/21 PASS einschließlich Syntaxprüfung, ausschließlich offline:
[Actions 39598760835](https://github.com/masterxfix/MOSA-2/actions/runs/39598760835).
Kein Liveversuch und keine Hosting-Secrets im Prüflauf.

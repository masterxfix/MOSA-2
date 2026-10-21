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

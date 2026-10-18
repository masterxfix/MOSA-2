# Phase 3B: offline bars_asset analysis (2026-10-18)

Status: incomplete; no new live apply authorized by this analysis. No database
connection was made. Historical optimizer choices cannot be recreated from
source code or mocked EXPLAIN rows.

## Established facts

The failed query in the original postcheck was:

```sql
SELECT id,starts_at FROM m2_market_bars
WHERE asset_id=1 AND interval_key='1m'
  AND starts_at>='2026-01-01' AND starts_at<'2026-01-02'
ORDER BY starts_at,id LIMIT 5
```

The expected index was `ix_market_bars_asset_time`
`(asset_id, interval_key, starts_at, id)`. This implements the bounded
asset/interval/time read described in MARKET_DATA_PHASE3.md, which specifies
the business path rather than a literal SQL query. No FORCE INDEX was used.

The old code checked index equality before saving the plan. On an exception,
the entire practical() return value was lost. Consequently the actual index,
access type, estimated rows and Extra of the failed live plan are unavailable.
This is a confirmed diagnostic defect, not proof of a schema defect.

## Reproducible fixture definition, not recovered live telemetry

512 assets, one route per asset, 32 sources; source_id=(asset_id % 32)+1.
Every bar uses interval 1m. Initially each asset has eight consecutive minute
bars starting 2026-01-01 00:00 UTC (4096 total). If any earlier/current EXPLAIN
returned ALL, the code expanded every asset to 32 minutes (16384 total).
The old failure report did not retain whether that expansion happened.
Thus the exact failed-run row count cannot be asserted beyond these two
possible counts. All rows for asset 1 fall inside the queried day; neither
interval nor time excludes any rows within that asset. Source and route are
fully correlated with asset. This fixture is weak evidence for time/interval
selectivity, but does not prove why MySQL chose a competing index.

## Competing hypotheses

| Hypothesis | Evidence / limit |
| --- | --- |
| A: wrong business query | Not supported: asset, interval, bounded time and LIMIT are present. |
| B: small / unselective fixture | Possible: only 8 or 32 rows per asset, all matching interval/time. Actual optimizer costs absent. |
| C: correlated fixture | Correlation proven by generator; causal optimizer effect unproven. |
| D: rigid name equality | Proven implementation property; equivalence of the rejected plan unknown. Do not relax it without that evidence. |
| E: unsuitable intended index | Not established; declared prefix matches equality filters followed by time range and ordering. |
| F: competing identity/source index | Possible, not established: actual chosen index and plan absent. |

Neither a full scan nor a legitimate equivalent alternative can be claimed.
No migration, query, fixture or acceptance condition was changed speculatively.
Both migrations remain unchanged; no additional index was added.

## Narrow diagnostic correction

Practical evidence now belongs to the caller by reference. Before the existing
guards run, the postcheck retains the exact query, expected/actual key, type, estimated rows,
Extra and generated row count for each EXPLAIN attempt, including both attempts
if expansion occurs. A callback writes the existing private report before each
guard, and the final report retains it after rollback. Only named diagnostic fields are copied; arbitrary
driver fields are not. Reports remain private and must not be committed.

The new offline regression test verifies retention across the original guard
failure, attempt history and field allowlisting. Its artificial plan is a unit
test input, explicitly NOT the missing MySQL plan and NOT optimizer evidence.

Release gate remains closed: the historical cause is not uniquely recoverable.
A future separately authorized diagnostic execution or an existing retained
plan is needed before changing fixture/acceptance or approving another apply.
No live action, password request or automatic retry is part of this work.

## Offline verification of the diagnostic correction

Previous offline suite: 92 tests, 91 passed. The only failure was the existing Windows
POSIX-permissions guard `budget_not_private`; no safety test was weakened.
All 19 Phase-3A tests and all 9 Phase-3B tests passed. All four changed/new PHP
files passed lint; deploy-file validation and `git diff --check` passed.
The fake-SFTP unit test's "Deployed" output is not a deployment.
Migration 0001 SHA-256 remains
`9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`;
migration 0002 remains
`205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee`.
Formal closure adds a disk-readback regression test for evidence saved before
the failing guard. No database or optimizer execution is involved. Final local
and Linux results, exact commit and run link are recorded in Issue #11 to avoid
changing the tested commit after its Linux verification. The sanitized interim
report is already present in Issue #11.

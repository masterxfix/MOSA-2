# Phase 3B: bars_asset fixture and retry correction (2026-10-19)

## Retained live evidence

The second live run on 2026-10-19 retained this natural MySQL plan for
`bars_asset`: expected `ix_market_bars_asset_time`, actual
`uq_market_bars_identity`, access type `ref`, estimated rows **8**, Extra
`Using where; Using index; Using filesort`. The fixture contained 4096 bars,
eight per asset. Structure checks and 30/30 practical constraint checks passed;
five of eight EXPLAIN paths passed before this guard stopped execution.

```sql
SELECT id,starts_at FROM m2_market_bars
WHERE asset_id=1 AND interval_key='1m'
  AND starts_at>='2026-01-01' AND starts_at<'2026-01-02'
ORDER BY starts_at,id LIMIT 5
```

All eight bars per asset previously used interval `1m` and fell within the
queried day. Interval and time therefore excluded no rows within the asset.
The identity index could locate those eight rows, with a small filesort.
This explains the fixture weakness and is consistent with the retained plan;
there is no optimizer cost trace proving the precise cost comparison.
It is not evidence of a schema defect. The intended index still matches the
asset/interval/time chart read described in MARKET_DATA_PHASE3.md.
The first, older run's unsaved plan remains unavailable; it is not reconstructed.

The last evidenced cleanup restored 13 tables, Ledger v1 and twelve empty
fact tables, without Ledger v2. This offline task makes no database connection
and does not refresh that server state.

## Deterministic fixture correction

All 512 assets use the same generator, one valid route each and 32 sources
(`source_id=(asset_id % 32)+1`). No special case targets asset 1.
Every asset receives `1m`, `5m`, `1h` and `1d` bars. Each bar is aligned to its
canonical interval and its end is exactly one interval after its start.

For each interval, slot j starts at midnight 2026-01-01 UTC plus
`(floor(j/perDay)-2)` days plus `(j % perDay)` intervals, where `perDay` is
2 for minute/hour bars and 1 for daily bars. Slots 0..7 are inserted initially;
expansion adds disjoint slots 8..15. Intraday bars thus start on 2025-12-30
and span four days initially, eight days after expansion; daily bars span
eight and sixteen days respectively.

| Fixture | Initially | After the one allowed expansion |
| --- | ---: | ---: |
| Current rows | 512 | 512 |
| Observation rows | 4096 | 16384 |
| Bar rows | 16384 | 32768 |
| Bars per asset | 32 | 64 |
| Bars per asset and interval | 8 | 16 |
| Bars per asset matching interval 1m and queried day | 2 | 2 |

Interval filtering selects one quarter of an asset's bars. The bounded day
then selects two of eight (or sixteen) bars in that interval. This supplies
meaningful interval/time selectivity with moderate row counts. Observation
fixture logic and all eight query strings are unchanged.

## Controlled retry and retained evidence

Before any acceptance guard, the first EXPLAIN is saved. A wrong expected key
**or** access type `ALL` consumes the single global expansion budget. The
fixture is expanded once, the same query is explained again and the second
attempt is saved before acceptance. Later queries cannot expand again.

The strict expected-key equality and allowed types `const`, `eq_ref`, `ref`,
`range` remain unchanged. Neither another arbitrary index nor a full scan is
accepted after expansion. No FORCE INDEX or acceptance shortcut is introduced;
existing checks are not removed or skipped.

Each attempt retains SQL, expected/actual key, type, estimated rows, Extra and
row counts. `fixture_rows` snapshots all three table sizes; the legacy
`history_rows_per_table` field now records the queried table's fixture size.
Only allowlisted diagnostic fields are saved, through the existing private
report callback, before a guard can throw. Both attempts survive a later
failure and rollback.

## Offline proof and live release boundary

Regression tests execute the real generator and retry helper using fake PDO
rows, without a database connection. They cover canonical intervals, alignment,
disjoint expansion, bounded selectivity, wrong-key/ref and ALL retries, the
single global budget, strict rejection after expansion, and retained attempts.
These tests do not prove a MySQL optimizer choice. A separately authorized new
Phase-3B live apply must still demonstrate all eight natural expected plans.
No live apply, password prompt, DDL, Ledger v2, real data, deployment or Phase 3C
is part of this correction. Issue #11 remains open.

Both migrations, indexes and constraints are byte-identical:

- Migration 0001 SHA-256:
  `9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`
- Migration 0002 SHA-256:
  `205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee`

Final local results, exact commit and Linux workflow run are recorded in
Issue #11 after verifying that commit, without editing the tested commit.
The verification branch must run the existing workflow with deployment skipped.

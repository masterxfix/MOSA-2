# Shared quote selection (offline logic)

`scripts/market_current/selection.php` is the generic selection contract.
The existing `scripts/market_current/planner.py` retains its route approval,
v2 writer validation and exact Current projection checks, and delegates selection
to this contract through local JSON stdio. `refresh.php` continues to invoke that
existing planner. `api/observations_read.php` calls the same contract directly;
`api/read_model.php` uses its clock and market-age calculation.

The contract has no database or provider capability. It reuses the existing
Phase-3N value primitives and the writer's pinned frozen unit catalog. Python
can pass an explicitly qualified catalog for offline synthetic quantity tests.
No instrument name, ISIN, equity class, venue or provider affects selection.
The Observations view retains its existing fixed subscription scope and route
identity checks; those are access/binding checks, not price selection rules.

- Only canonical native Observation-v2 facts are eligible. Physical identities,
  source and route binding, units, currency, quantity/volume pairs, decimal
  precision, positive price, bid/ask ordering and the v2 dedupe hash are checked.
  The Observations adapter excludes legacy NULL-format rows; malformed v2 facts
  and unsupported non-NULL formats block the result.
- Compare `market_at`, then `observed_at`, both in UTC with microseconds.
  Different facts at the same pair of timestamps block the complete supplied
  set, including conflicts with the existing Current origin or at older times.
  A physical ID only orders identical facts deterministically.
- With no previous Current: select `INSERT`, or `MISSING` when there is no fact.
  With a verified previous Current: newer means `UPDATE`, equal means
  `UNCHANGED`, older means `UNCHANGED_OLDER`. No candidates means `UNCHANGED`.
  Unchanged decisions preserve the exact Current values and update timestamp.
- Market time cannot follow observation time or the supplied clock. Observation
  time allows the existing five-minute clock tolerance. Age and stale status
  use market time, never acquisition time.
- Existing input bounds remain: two Current candidates; 100 Observations
  candidates plus a completeness sentinel. An unexamined possible winning tie
  fails closed. This is selection within a bounded input, not a full-history audit.

`tests/test_quote_selection.py` exercises synthetic PNE and Carl Zeiss cases
through the existing Python planner and the PHP Observations adapter. It also
covers generic native EUR/GBP/GBX/POINT and explicitly qualified synthetic
quantity/volume units. Prices are artificial and are not live-market evidence.

This change is logic and offline tests only. No Current, Bars, Observations,
Collector or schema data is changed. No runtime or web files were deployed.
Any later deployment must separately include and qualify the shared module and
its existing Phase-3N/Phase-3C primitives and pinned catalog dependencies.

## Offline validation, 2026-10-21

- Current: 19/19 passed; Observations: 9/9 passed; shared contract: 10/10
  passed. PHP syntax and Git whitespace checks passed.
- The broad existing regression is not green on this Windows environment
  (PHP 8.5.8 without PDO-MySQL, missing Python `resource`/timezone support,
  existing homepage expectations and byte assertions). The unrelated failing
  cases were compared with an unchanged archive of base commit `7f0c75d`, using
  the same local Git-byte normalization for the pinned catalog/migrations.
  Both versions produced exactly the same comparison result: 23 executed test
  methods, 28 failed subchecks, 9 errors and 2 import exceptions. No new failure
  or error appeared in this comparison.
- The existing Readiness stderr/overflow test hangs in Windows PHP pipes.
  The unchanged baseline's overflow fixture also exceeded an isolated
  eight-second timeout. This test remains incomplete; Collector code was not
  changed to work around it. The 84 regression tests after that test were run
  separately (5 existing failed byte subchecks, included in the comparison).
- These are synthetic offline results, not database, provider or deployment
  evidence. The existing unrelated failures and incomplete Readiness test are
  retained explicitly; no test or guard was weakened.

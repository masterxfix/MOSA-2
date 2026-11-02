# General market collection

`MarketBatch::collect` connects the existing authenticated snapshot, MarketSelection,
MarketBatchScope, sequential MarketBatch, MarketLive proof/Observation-v2 writer and
MarketCurrent transaction/readback. The web readers continue to read stored data only.

The catalog supplies every asset, ISIN, source and physical route. The common adapter
registry uses the existing Tradegate Mid and Frankfurt manifest factories. Explicit
source priorities select one qualified source per asset. Qualification fails rather
than truncating an excessive scope. An enabled route can only be reused; creating an
enabled route remains forbidden. Disabled routes require manual mode. The normal
Schema-5/6 acquisition gate and scheduler locks remain in place.

Before each GET, the physical route/hash is rechecked against the reviewed batch.
Each item uses its own atomic Observation transaction and independent readback.
Failure stops subsequent requests; committed earlier items remain reported. Current
runs only after the entire batch is COMPLETE, including correctly deduplicated items.
The existing Current planner protects newer prices and checks source transitions.
Final read-only reconciliation reports counts and changed business rows, including
after a Current/readback failure. Unknown process results are never reported as zero.

## Manual Actions execution

`.github/workflows/market-collector.yml` is manual only and has no schedule or deploy.
It reuses the pinned SSH tunnel and existing testsite/DB secrets through
`scripts/collector_actions.py --collection`. Passwords reach PHP on stdin only.
PHP 8.4 with pdo_mysql is required. A rerun (attempt > 1) is rejected.

Inputs: `expected_commit`, exact `scope` JSON, `authorization`.

Scope keys: `mode` (manual), `request_budget` (integer 1–5), `source_priority`
(ordered registered source keys), `expected_isins` (unique explicitly approved ISINs).
The complete dynamically qualified selection must match expected_isins exactly.
No new route, source, asset, migration or scheduler state is written.

Authorization: `MOSA2-MARKET-BATCH:<full SHA>:<SHA256 of exact UTF-8 scope input>`.
The Python runner verifies the dispatch context, attempt, SHA, budget and scope
authorization before SSH. The token string binds scope; it is not a GitHub credential.
User approval for a historical PNE or five-asset run does not authorize this workflow.
Exactly one separately approved batch is to be dispatched; no retry or replacement run.

Suggested first live scope: the previously qualified BYD, DroneShield, UBTECH, PNE and
Carl Zeiss Meditec Tradegate routes, with at most five sequential GETs and existing
Observation/Current writes in the test database. This live execution is not yet approved
or evidenced by this change. Web/Chrome readback and the two-second browser limit
remain part of the live acceptance, not an offline performance claim.

## Offline evidence

`tests/test_market_general.py` composes five dynamically selected synthetic catalog
assets, two registered adapter types, the actual bridge, Observation writer, batch,
Current transaction and web presenter using the existing transactional PDO doubles.
It covers deduplication, older market times, partial failure, independent readback
failure, scope authorization and manual/automatic route status. No live provider or
database access is part of these tests. `tests/test_market_batch_scope.php` verifies
source priorities and physical binding; the existing relevant regression families
cover runtime, route identity, Current transitions and Schema-6 locks/release integrity.

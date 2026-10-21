# Read-only Current preview

The preview prepares possible projections; it cannot execute them. It uses
`planner.plan_facts`, `planner.check_approval`, `planner.projection` and the shared
`selection.php` contract. The existing write planner still checks its approval
before calling the same fact planner. No second quote-selection algorithm exists.

`preview_read.php::gather` resolves the existing five qualified ISINs through
`ObservationRead::scopeSql` and collects the existing `MarketCurrent::inputs`.
No physical asset or route IDs are configured. One route is resolved from the
existing qualified scope; missing or ambiguous routes block that item. Source,
asset, physical-route and frozen-unit metadata is qualified again through the
existing Observations binding before facts reach the Current planner.

The snapshot contains at most two native-v2 candidates per physical route, its
single existing Current row and its single origin observation. The origin lookup
is additionally bounded to the already selected asset, including for corrupted
provenance. There are at most 30 asset-scoped data SELECTs for all five assets;
single-row lookups use existing primary/unique keys. The scope lookup has LIMIT 2
and the Observation lookup has LIMIT 2. Existing v2 validation, canonical dedupe,
route/unit checks, time ordering and exact Current-projection checks remain active.

The full private result is returned by `preview.snapshot_preview(snapshot)`:

- Previous Current with native price, units, market/observation times, origin ID,
  market age and a verification flag. Invalid existing provenance is explicitly
  unverified rather than advertised as valid.
- Latest eligible native Observation with the same fields. No currency or price
  conversion occurs. The existing `MarketRead::present` validates presentation;
  market age comes from the shared selection contract.
- `candidate_decision`: INSERT, UPDATE, UNCHANGED, UNCHANGED_OLDER or MISSING.
- `decision`: the candidate decision, or BLOCKED for invalid data/provenance,
  conflicts, or missing route approval for a proposed change.
- A fixed reason code, missing approvals and the existing exact projection for
  a valid candidate. A projection is data, never an executed statement.

Gathering never creates an approval: it clears the query-scope placeholder to
NULL. Approvals supplied by an authorized private caller must pass the original
complete physical-route SHA-256 and approval timestamp checks. A disabled route
also needs the original explicit disabled-projection permission; its enabled flag
is never modified. Any actual takeover still requires a separate explicit human
Current-apply order. Approvals cannot override data conflicts or provenance errors.

The CLI `python -B scripts/market_current/preview.py` accepts a **private** JSON
snapshot on stdin and returns the full private report. Do not send that output to
public CI logs. `public_summary` is an explicit allowlist of public instrument
names and operational decision/reason/approval labels; it excludes all private
quote values, physical IDs, timestamps, hashes, SQL and credentials.

## Optional one-time real inventory

The existing registered `observation-view-check.yml` workflow runs all targeted
offline tests first, checks the exact reviewed commit, and optionally performs one
inspection when `read_inventory` is true. Only the first run attempt is admitted.
There is no provider, Collector, Scheduler, deployment or installed-release change.

The runner reuses the existing pinned SSH profile, host-key verification and
fileless PHP transport. `read_bundle.php` extracts the **actual existing read
functions** using PHP reflection; they are evaluated in memory, with no remote
upload or file creation. The fixed existing private read configuration is checked
at `/var/www/vhosts/web213.server10.configcenter.info/mosa2-market-read-private/access.php`.
This expected path is tested, not assumed to be available inside the SSH namespace.
No other credential path, writer password, credential setup or connection retry
is allowed. If that configuration is inaccessible, the concrete missing proof is
reported and the offline preview remains usable.

If available, only `h29077_mosa2_read@localhost` on the existing isolated test DB
is accepted. The existing grant validator rejects every privilege beyond SELECT
and SHOW VIEW (including roles or grant delegation). Exactly one PDO connection
starts a verified READ ONLY, REPEATABLE READ transaction and always rolls it back.
Only the five qualified assets are inspected. The remote reply stays in memory
on the runner; complete validation and projection happen in the checked-out
candidate modules. Public output contains operational labels only. Nothing is
stored as a public artifact, and raw PHP/SSH errors are never published.

An unavailable reader is reported as `real_data_checked=false`, with a fixed
failure code; it is not a successful DB preview. The allowed fallback neither
creates access nor uses a write-capable account. Successful offline CI alone is
not proof of real-data decisions or authorization to apply a projection.

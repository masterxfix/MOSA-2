# Manual fundamentals report collector

The shared manual workflow `fundamentals-reports.yml` runs the reviewed report list in order. Registry: `scripts/fundamentals/reports.py`. Existing PNE annual and Zeiss adapters remain supported. The sole current execution authorization is `pne-q1-2026`; one anonymous GET, no redirect/retry. Additional registry entries require explicit review and authorization, but no company-specific workflow or SQL writer.

The workflow requires exact main SHA, attempt 1, and `MOSA2-REPORTS-pne-q1-2026:<SHA>`. The private exclusive execution marker is `fundamentals-pne-q1-2026-20261101-01`. Repeating a consumed report stops before GET. No scheduler or collector job is enabled.

Each report uses the existing shared pilot pipeline: identity/schema/locks and bounded baseline checks; exclusive reservation; existing single-use HTTP transport; complete private original body plus URL/status/times/size/SHA metadata; separate owner/mode/hash/metadata readback; versioned adapter; one generic SQL transaction; a fresh independent read-only connection; final archive verification. Failure stops the sequence, and unknown commit outcomes never retry. Prior successful reports remain committed.

The PNE Q1 adapter binds the dated official release to calendar Q1 2026 and explicit previous-year comparisons to Q1 2025. Only actual monetary amounts with explicit million-EUR units qualify. Forecast sentences are excluded. Missing/ambiguous individual metrics remain in raw storage; conflicts in qualified facts or units stop. No result amounts are embedded in the adapter. Existing total_output, revenue, ebitda_normalised and ebit definitions are reused exactly; revenue is distinct from total output, and normalized EBITDA is distinct from EBITDA.

PNE FY (7 observations/4 Current), Zeiss (20/10), existing market data (28/5), master data and ledger are checked independently before/after. Generic preservation can filter FY or FQ. Current uses separate FY/FQ keys. Performance now measures the imported period type: Current PRIMARY, bounded History ix_fund_obs_period LIMIT 20, EXPLAIN ANALYZE iterator time separate from client/tunnel time. A zero const iterator time is not whole-query DB latency.

Focused offline proof covers actual/prior quarter periods, exact evidence offsets, existing catalog reuse, missing metrics, forecast exclusion, duplicate/conflicting facts, FY/FQ with two issuers, all new-quarter write failure points, independent readback tampering, sequential stop and existing transport/archive boundaries. Synthetic data are never a substitute for a successful live readback.

Limits: only reviewed prose structures and catalog fields are normalized; all additional content remains in the original archive. No website changes, provider requests on page loads, migrations, production deployment or automatic operation. Existing bounded baseline capacities are retained.

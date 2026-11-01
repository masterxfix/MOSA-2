# DroneShield PDF extension (2026-11-01)

Current execution authority: `droneshield-fy-2025`, exact reviewed main SHA and `MOSA2-REPORTS-droneshield-fy-2025:<SHA>`. Existing workflow `fundamentals-reports.yml`; new private marker `fundamentals-droneshield-fy2025-20261101-01`. Only the fixed official ASX URL is permitted. One GET, no redirects, retry or alternate endpoint. Earlier report keys remain supported but are not authorized for a new fetch by this order.

`pdf_document.py` extracts bounded PDF word coordinates; `droneshield.py` qualifies only the titled Financial Highlights table with explicit FY2025/FY2024 columns. It does not read chart amounts as facts. Page, table, row, column, vertical position and original AUD scale are recorded in field provenance. The existing SQL core remains issuer-independent. The PDF stays byte-identical in the private original archive; no raw PDF appears in stdout or GitHub artifacts. Archive transfer uses existing SSH stdin; only the bounded receipt returns through the 64-KiB stdout channel. The existing 8-MiB raw-file limit remains unchanged.

Source and document identity, MIME/signature, fiscal years, AUD currency and table units are required. Decimal conversion maps explicit AUD thousands to AUD_MILLION. Parenthesized negatives are supported. Revenue/EBITDA reuse exact existing definitions. Underlying EBITDA, underlying PBT, consolidated PAT, customer cash receipts and operating cashflow have distinct definitions. Cash and term deposits remain raw because the current writer supports FY/FQ flows, not a qualified point-in-time period. Missing cells/rows remain raw with a fixed reason; conflicting qualified facts or currency/unit/year identity stop.

The live preflight checks existing PNE 11/6, Zeiss 20/10, market 28/5, schema/ledger 1-6, identity and disabled jobs. Transaction and independent new-connection readback are unchanged. History measurements now explicitly bind the imported year range as well as asset, metric, FY/FQ and LIMIT 20. Server EXPLAIN iterator timing and client/tunnel time stay separate.

Dependencies are pinned in requirements-fundamentals-pdf.txt together with existing requirements-deploy.txt. PDF extraction API reference: https://github.com/jsvine/pdfplumber . Synthetic byte-generated PDF tests cover coordinate/year mapping, scale, negative values, missing cells, chart exclusion, identity/currency/year conflicts, exact catalog reuse, the complete PHP validator, replay, all write failure points and independent readback tampering. The synthetic page is rendered and visually checked locally. Existing PNE/Zeiss regressions are retained. No original provider document is fetched for tests.

Limits: reviewed text PDFs only, up to 200 pages / 2 million extracted characters within 8 MiB; no OCR or inferred chart values. Unsupported layouts fail closed after retaining raw data. No website change, migration, deployment or scheduler activation.

---

# Manual fundamentals report collector

The shared manual workflow `fundamentals-reports.yml` runs the reviewed report list in order. Registry: `scripts/fundamentals/reports.py`. Existing PNE annual and Zeiss adapters remain supported. The sole current execution authorization is `pne-q1-2026`; one anonymous GET, no redirect/retry. Additional registry entries require explicit review and authorization, but no company-specific workflow or SQL writer.

The workflow requires exact main SHA, attempt 1, and `MOSA2-REPORTS-pne-q1-2026:<SHA>`. The private exclusive execution marker is `fundamentals-pne-q1-2026-20261101-01`. Repeating a consumed report stops before GET. No scheduler or collector job is enabled.

Each report uses the existing shared pilot pipeline: identity/schema/locks and bounded baseline checks; exclusive reservation; existing single-use HTTP transport; complete private original body plus URL/status/times/size/SHA metadata; separate owner/mode/hash/metadata readback; versioned adapter; one generic SQL transaction; a fresh independent read-only connection; final archive verification. Failure stops the sequence, and unknown commit outcomes never retry. Prior successful reports remain committed.

The PNE Q1 adapter binds the dated official release to calendar Q1 2026 and explicit previous-year comparisons to Q1 2025. Only actual monetary amounts with explicit million-EUR units qualify. Forecast sentences are excluded. Missing/ambiguous individual metrics remain in raw storage; conflicts in qualified facts or units stop. No result amounts are embedded in the adapter. Existing total_output, revenue, ebitda_normalised and ebit definitions are reused exactly; revenue is distinct from total output, and normalized EBITDA is distinct from EBITDA.

PNE FY (7 observations/4 Current), Zeiss (20/10), existing market data (28/5), master data and ledger are checked independently before/after. Generic preservation can filter FY or FQ. Current uses separate FY/FQ keys. Performance now measures the imported period type: Current PRIMARY, bounded History ix_fund_obs_period LIMIT 20, EXPLAIN ANALYZE iterator time separate from client/tunnel time. A zero const iterator time is not whole-query DB latency.

Focused offline proof covers actual/prior quarter periods, exact evidence offsets, existing catalog reuse, missing metrics, forecast exclusion, duplicate/conflicting facts, FY/FQ with two issuers, all new-quarter write failure points, independent readback tampering, sequential stop and existing transport/archive boundaries. Synthetic data are never a substitute for a successful live readback.

Limits: only reviewed prose structures and catalog fields are normalized; all additional content remains in the original archive. No website changes, provider requests on page loads, migrations, production deployment or automatic operation. Existing bounded baseline capacities are retained.

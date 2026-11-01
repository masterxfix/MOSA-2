# Zeiss: nested-table correction and archive-only import

## Qualified partial import after c9ea06b

Run 41302603556 passed archive, table and EPS qualification, then stopped at
EBITDA_QUALIFICATION before connecting to the DB or creating the application
marker. Parser version 3 now separates the ten mandatory table metrics from
optional narrative EBITDA. All table, EPS, year, number and unit checks remain
mandatory. Exactly one match of the already qualified EBITDA pattern adds its
two yearly facts; zero or multiple matches add no EBITDA facts/catalog entry.
No new wording, estimates or EBIT/EBITA derivations are accepted.

The bounded plan and public result explicitly list unqualified EBITDA with
EBITDA_PATTERN_NOT_MATCHED or EBITDA_MULTIPLE_MATCHES. Only observed metric keys
enter the catalog plan. parse_status remains partial; the unchanged complete
original archive retains all unstructured information.

New manual workflow: fundamentals-zeiss-qualified-import.yml. Separate exact-SHA
authorization: MOSA2-ZEISS-QUALIFIED-IMPORT-20261101:<commit>. Separate exclusive
application marker: fundamentals-zeiss-qualified-import-20261101-01.consumed.
No rerun of the preceding workflow, no provider acquisition and no original
archive changes. The existing archive verification, bounded transfer, PHP core
validation, DB preflight, immediately-before-apply reservation, atomic write,
independent readback and targeted EXPLAIN ANALYZE path are reused unchanged.

Focused tests additionally validate ten metrics without EBITDA through the full
PHP core, unique optional EBITDA, missing/ambiguous/invalid EBITDA, mandatory
EPS/table rejection and explicit October-to-September fiscal periods.

## Previous nested-table preparation

Starting commit: fbd11218078eccfe7ac4e7cc1211ef5c9a286692.
Confirmed first failure: NESTED_TABLE, diagnosed in run 41302067314 against
the immutable original archive. No new provider acquisition is authorized.

The existing HTMLParser now keeps a stack of table-local row and cell states.
Tables retain document opening order for evidence paths. Child table text never
enters parent cells. A parent cell containing a child table is explicitly marked
non-scalar; number validation cannot silently concatenate text around it.
The actual-results table must still uniquely contain all expected metric labels,
and all existing years, units, EPS and EBITDA checks remain mandatory.
Parser version is 2. PNE parser and generic DB core are unchanged.

Workflow: fundamentals-zeiss-archive-import.yml, manual main only, run number
and attempt 1, exact reviewed commit with authorization
MOSA2-ZEISS-ARCHIVE-IMPORT-20261101:<commit>.

The successful in-place archive-reading code is reused. It verifies the original
commit, SHA-256, owner/mode/no-follow protections, bytes and metadata on Dogado,
then runs the corrected adapter in the same isolated remote process. Only the
qualified fact plan travels over pinned SSH: plan <=45000 bytes, total reply
<=49152 bytes, existing transport cap 65536 unchanged. Neither raw HTML nor
financial values are printed in public logs. No downloaded provider content,
new private archive files, deployed module files or database migrations.

Before DB application, the existing PHP core validates the plan offline. The
existing read-only preflight then verifies Schema 6, locked Collector, original
master/market data and protected PNE 7 observations / 4 Current. The remote
process rereads the archive, reparses and compares the exact plan hash before
exclusively creating a separate 0600 application marker in the existing locks
directory. The original archive and its consumed marker are never modified.
Marker creation uses the existing no-follow/exclusive/fsync/readback functions.

The unchanged generic transaction writes facts and Current, reuses catalog
entries and rejects conflicts. A fresh DB connection independently reads back
the committed rows and checks protected stocks, market baseline, ledger and
Collector locks. Existing targeted Current/History EXPLAIN ANALYZE measurements
run once. Finally the original archive is independently reread again.

On any further adapter failure, only its fixed safe error code is reported;
there is no DB connection/application and no marker creation. On an unknown
application result there is no retry. One commit and at most one live Action.

Focused tests cover nested results and unrelated layout tables, isolated cells,
ambiguous/missing values, exact fiscal periods/units, a large synthetic archive,
bounded plan transfer, exclusive marker consumption and unchanged originals.
Existing PNE/generic writer/archive regressions run without provider requests.
Synthetic results are preparation only; success requires the actual live
archive import and independent Dogado readback. Chrome checks only the existing
unchanged market-data page; no new Fundamentals UI is claimed.

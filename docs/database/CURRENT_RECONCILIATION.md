# Read-only reconciliation after an uncertain Current APPLY

RECONCILE is independent of APPLY. It retrieves the successful original PREPARE
artifact through existing GitHub access, checks the source commit/run and exact
plan digest, and decrypts it with the existing SSH secret. No local attachment,
local private key, writer DB secret, new approval, claim or plan is needed.
The plan remains historical evidence even after execution authorization expires.

The existing reader opens one SELECT-only account connection, verifies the
READ ONLY transaction and gathers only the existing five qualified assets. The
original Current planner and validators check units, source/route binding,
canonical dedupe, clocks and exact origin/projection provenance. The comparison
uses the existing projection for the original selected observation. All target
fields must match exactly; only updated_at uses the actual stored projection
time, which must be a valid timestamp between preparation and the read snapshot.
Private price, origin ID, market/acquisition times, source, route and revision
are processed in memory. Public output contains status codes only.

A means all five exact targets, B all five exact original rows/absences. A/B also
require unchanged scoped routes, binding metadata and candidate observations.
C means mixed results, different valid rows, or known scoped baseline drift.
D means a missing, invalid or otherwise unverifiable comparison. None of these
states alone proves which historical SQL statement or commit/rollback occurred;
they establish the currently observed database state.

The historical plan covers five routes/bindings, at most two candidates per
asset, and the original Current origins. It contains no complete other-table
snapshot. Therefore observations/metadata equality is scoped, and a full-table
or full-database integrity guarantee is explicitly unavailable. Once a Current
origin changes, its prior origin is not separately reread by the bounded reader;
no claim is made for that unreturned historic row.

Failed APPLY 39637283761 ran its execution step from 16:45:19.3660522 to
16:47:53.6377415 UTC (154.2716893 seconds). The immutable source sets timeout=150
for its PHP subprocess. TimeoutExpired and other exceptions reach the same broad
handler and public TAKEOVER_STOPPED_NO_RETRY code; the private stderr/reply is
not retained. This timing is compatible with a subprocess timeout plus access
and cleanup time, but cannot confirm the actual exception, failure stage, or
commit outcome. No APPLY rerun or write probe is used to investigate it.

# Current takeover: bounded execution and uncertain outcomes

Scope: source improvements and synthetic offline qualification only. No new
takeover, provider call, database inspection/write, deployment, collector, or
installed release change belongs to this change.

## Historical evidence

Base revision: `d54114e`. The implementation used by APPLY run
[39637283761](https://github.com/masterxfix/MOSA-2/actions/runs/39637283761)
wrapped the entire PHP process in `subprocess.run(timeout=150)`. Its public
exception handler discarded the exception type and the PHP failure stage.
The APPLY step started at 16:45:19.370 UTC and emitted the generic stop at
16:47:53.638 UTC on 2026-10-21: approximately 154.268 seconds including artifact
retrieval and SSH setup. The job itself ran approximately 278 seconds against
a ten-minute limit. This was not a GitHub job-limit cancellation.

The duration is consistent with the PHP timeout; it does **not prove** that
exception was raised. A PHP rejection, invalid output, tunnel failure, or other
exception was indistinguishable. No per-phase timing survives from that run.
The supplied READ ONLY reconciliation
[39654910812](https://github.com/masterxfix/MOSA-2/actions/runs/39654910812)
reported case A (five target rows). It establishes the later observed target
state, not the historical process exception, commit acknowledgment, or successful
completion of its original replay. No new live comparison was performed.

The call chain is Python runner -> PHP takeover preflight -> Python exact
takeover validation -> bounded PHP qualification/selection calls. The validation
runs again against locked fresh state in the transaction. Existing full-state
captures and exact delta checks precede commit. A new connection then performs a
READ ONLY capture and an ordinary planner replay that must return five UNCHANGED
decisions. The old PHP planner bridge used blocking pipe reads and had no total
planner deadline. Individual nested 10/15-second limits did not bound their sum.

## Outcome contract

JSON-lines progress records are flushed at phase boundaries. A terminal record is
mandatory for success. Public output is rebuilt from enumerated codes, booleans,
and monotonic millisecond durations; raw PHP output, stderr, SQL, exception text,
prices, credentials, authorization phrases, and paths are never copied into it.

| Status | Evidence |
| --- | --- |
| PREFLIGHT_FAILED_NO_WRITE | Preflight/begin failure, no write attempt |
| TRANSACTION_FAILED_BEFORE_COMMIT | Transaction began; no commit attempt; rollback not confirmed |
| ROLLBACK_CONFIRMED | rollback returned true and transaction ended, with no commit attempt |
| COMMIT_CONFIRMED_READBACK_PENDING | Progress only: commit returned true; verification incomplete |
| CURRENT_COMMITTED_READBACK_AND_REPLAY_PASS | Terminal success: commit acknowledged, independent readback equal, five replay decisions UNCHANGED, READ ONLY cleanup successful |
| ERROR_AFTER_COMMIT | Commit acknowledged; subsequent error, timeout, invalid/missing terminal record, or cleanup failure |
| OUTCOME_UNKNOWN | Commit attempt unacknowledged, rollback unconfirmed, or missing trustworthy completion evidence before commit confirmation |

`commit=UNKNOWN` is set **before** calling commit. A failed/throwing commit stays
unknown even if a subsequent rollback returns true: rollback cannot prove that an
earlier commit was not accepted by the server. A hard timeout cannot infer rollback
from connection loss. The parent preserves an already observed commit confirmation;
otherwise incomplete output is conservatively unknown. No timeout authorizes a retry.

## Time and resource budgets

| Boundary | Budget / behavior |
| --- | --- |
| Separate read-only readiness process | 60 seconds |
| Each preflight/locked planner | 60 seconds; concurrent output collection via private anonymous files; 1 MiB output cap |
| Write/commit admission | Refuse further writes or commit after 120 seconds from PHP preflight start |
| Replay planner | 45 seconds |
| Cooperative PHP completion | 210 seconds; reserves 90 seconds at latest commit admission for commit and verification |
| Entire apply PHP process tree | 240 seconds; additional cleanup/reaping waits bounded to five seconds each |
| MySQL lock wait / SELECT | Session limits 10 seconds each; existing connect timeout five seconds |
| Artifact API calls | Existing 30-second request timeouts, no retry |
| Actions test / preparation-execution steps | 5 / 7 minutes |
| Actions job | 15 minutes: test + execution + setup/cleanup reserve |

Checks are cooperative around synchronous database calls; the outer process-tree
deadline is the final containment boundary, not proof of server-side completion.
An unresponsive commit can consume the verification reserve; its outcome then
remains unknown rather than claiming either commit failure or rollback.
On Linux the runner starts a new session and kills its process group on timeout
and after process exit. Windows uses taskkill /T /F plus direct termination fallback.
The planner owns no DB connection; nested qualification processes retain their
10/15-second limits. Private anonymous planner files close in finally. Transaction
rollback and advisory-lock release use nested finally blocks so a rollback error
does not skip lock release. Writer references are dropped before independent
readback. Readback cleanup failure cannot produce takeover success.

## No retries and historical authority

There is exactly one writer invocation. Neither parent, PHP, nor workflow retries
it. Existing first-attempt, revision, exact authorization, fresh-state binding,
expiry and consumed-artifact guards remain. Historical source run `39634298612`
is additionally a permanent consumed tombstone in both authorization and claim
validation, independent of artifact expiry/deletion. Reconcile may still use its
immutable historical plan as evidence; this never grants writing authority.

For OUTCOME_UNKNOWN / ERROR_AFTER_COMMIT, preserve the original plan reference and
use the existing `current_reconcile_remote.py` / `market_current/reconcile.py` in a
**separate explicitly requested READ ONLY** run. Cases A/B/C/D retain their existing
meaning and limits. Reconciliation is neither started automatically nor converted
into a new authorization. No new database table is required.

## Verification and limits

`test_current_outcome` exercises synthetic PDO failures at begin, write, rollback,
commit acknowledgment, readback and replay, post-commit timeout, malformed/missing
final records, output redaction, consumed authority, bounded real local processes,
and Linux descendant termination. Existing Current, preview, Reconcile, quote
selection, observations and web regressions remain in the same manual workflow.
Run only with `takeover_mode=NONE` and `read_inventory=false` for this assignment.

Offline tests establish control-flow behavior, not MySQL/network failure behavior
or production timing. Full-state captures can still consume significant time;
budget exhaustion deliberately fails closed. Abrupt runner/host termination may
lose even flushed acknowledgments; this remains OUTCOME_UNKNOWN and requires the
separate reconciliation. The installed release is untouched.

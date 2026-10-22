# Schema4 backup/restore protocol — synthetic CI only

This is preparation and an isolated MySQL8 recovery test, not a Dogado backup,
restore, migration authorization or operational readiness statement. Migration SQL
0001–0005, both execution switches, provider rights, the historical33 contract,
the separate53 candidate and installed Collector remain unchanged.

## Reused architecture

`scripts/database_backup.py` has no command-line executor, hosting configuration or
production connection factory. The existing guarded MySQL fixture supplies its
connection; the adapter further requires GitHub Actions, two explicit isolation
flags, loopback127.0.0.1:3307, container-side port3306, MySQL8.0, the fixed service
database, exact container hostname/UUID obtained directly from the CI service,
and event_scheduler=OFF/partial_revokes=OFF. Every source/target connection is rechecked. No hosting
secrets are provided to the `backup-restore` workflow mode; it cannot select the
separate migration5-readonly job. There is no dump/artifact/release upload.

Schema tables/digests come from the existing migration5 envelope. The unchanged
exact PHP metadata parser and bounded runtime ledger/unit checks validate both
schemas. The existing Current/Observation readers validate the reused five-asset
fixture and native-v2 provenance. This adds a generic complete-data comparison,
not a second MOSA schema parser or price selector. Schema-local FK metadata is
normalized to the original fixture name only after proving it references the
actual inspected database; foreign-schema references fail. Data is never rewritten. CHECK metadata rows from the unchanged unordered query
are sorted by constraint name for comparison; every name and complete clause
remains checked. The PDO field order in encrypted metadata is preserved for
the existing numeric SHOW CREATE replay.

## Consistency and completeness

Source is the synthetic schema4 fixture `h29077_mosa2_test`, 17 exact InnoDB tables.
It additionally contains synthetic rows in every table, Bars with maximum-scale
DECIMAL, binary NUL/high bytes, JSON/Unicode, microsecond dates, disabled jobs and
history, checkpoints and module state. It has a harmless trigger, procedure,
function and disabled future event. No provider or event is executed.

An exclusively held `FLUSH TABLES WITH READ LOCK` spans the complete pre-capture,
`mysqldump --single-transaction`, and identical post-capture. The control connection
remains open until `UNLOCK TABLES`; a lost lock connection aborts the backup.
This deliberately requires write/DDL quiescence for the WHOLE operation, including
AUTO_INCREMENT and object metadata. It is not a zero-downtime claim.
Single-transaction by itself does not isolate concurrent ALTER/CREATE/DROP/RENAME/
TRUNCATE; see [MySQL mysqldump](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)
and [global read locks](https://dev.mysql.com/doc/refman/8.0/en/flush.html).
Real competing UPDATE and ALTER tests must time out behind the held lock; unchanged
pre/post snapshots and successful restores prove no mixed-time export.

Root visibility and global privileges are explicitly verified in the ephemeral
service; an empty information_schema object list alone is insufficient. Dump flags
include routines/events/triggers, hex binary, UTC, explicit utf8mb4, no tablespace
or GTID server-state commands, primary ordering, and no generated DATABASE/USE
or DROP TABLE statements. All table DDL, indexes, FK/CHECK clauses, charset,
collation, row format/options and next AUTO_INCREMENT are preserved. All columns
and rows are canonicalized with explicit byte/Decimal/datetime6/date types and
hashed per table; no float conversion, currency conversion or time shift occurs.
Complete SHOW CREATE definitions, SQL modes and character/collation contexts are
compared for stored objects. MySQL-generated object creation timestamps/table
statistics are not restorable business data and are excluded from equality;
stored DATETIME(6) values are all compared. Explicit schema-qualified object-body
references fail closed rather than being silently rewritten across schemas.

## Encrypted, authenticated package

Backup ID, schema4/source identity, exact MySQL version, container UUID, full repository commit,
exact ledger including checksums, per-table content SHA-256, full comparison-state
SHA-256 and raw dump SHA-256 are bound by a separate canonical Ed25519-signed
manifest. The verifying public key must come from the trusted caller, never the
package. The signature also binds the entire encrypted envelope SHA-256.

The existing `deploy_test_sftp.persist_backup` AES-GCM/HKDF-SHA256 envelope is reused
without changing its pinned source or protocol: info/AAD
`mosa2-testsite-web-backup-v1`, random16-byte salt and12-byte nonce. Encrypted files
contain `dump.sql` and the complete `state.json`; the historical context name does
not make this a web deployment. A bounded terminal marker detects incomplete dump
output in addition to authenticated hashes and the full independent restore check.
Only temporary synthetic key material is generated, held in process, then discarded.

Limits are explicit: dump8MiB, comparison state16MiB, encrypted envelope36MiB,
manifest64KiB, cell1MiB, 100000 rows/table, 32 objects/type; overages abort, not
truncate or raise old transport limits. Anonymous mode0600 temporary process files
avoid pipes/deadlocks; command timeout90s, bounded stderr64KiB, finite DB/socket/
metadata subprocess timeouts, backup test step8min. Directories0700/files0600 and
no symlinks are required on Linux. Plaintext is never logged or uploaded; package,
temporary files and keys are removed by fixture teardown even after failures.
Deletion means unlinking ephemeral runner storage, not a claimed forensic SSD wipe.
Larger real databases require a separately reviewed chunked/streaming encryption,
snapshot and full comparison contract, with authenticated sequence/count/final
marker and finite aggregate limits. They are unsupported by this bounded version.

## Isolated restore and explicit outcomes

Only fresh `mosa2_restore_isolated_a`, `_b`, or `_fault` databases on that exact
verified container are allowed; source, system and production database names are
rejected before a claim, DDL or data command. Authenticated identities, schema,
hashes, complete table set and trusted signature precede target creation.
An exclusive mode0600 attempt claim and fresh-database requirement prevent retry;
no existing database is dropped by the restore implementation.

The actual SQL client uses a passwordless socket-only **synthetic fixture** account,
not the administrative source connection. Its DML/DDL grants cover only the three
literal escaped target names. SET_USER_ID/SYSTEM_USER allow preserving original
DEFINERs; they do not grant source-table DML. The ephemeral service explicitly enables log_bin_trust_function_creators for restoring
stored functions with binary logging, avoiding SUPER on the restore account. This
is CI-only configuration, not a hosting prerequisite assumed to be satisfied.
No hosting account, password or Secret
is created. A validly signed test dump trying to DELETE original-source rows must
fail with access denied while the original data remains identical. Restored events
cannot run because the ephemeral server event scheduler is OFF.

`RESTORE_READBACK_PASS` requires a new independently connected complete canonical
snapshot, existing schema/ledger/unit validation and five-asset provenance/read
results identical to the authenticated baseline. Row counts alone never pass.
Known client failure is `RESTORE_PARTIAL_FAILED`; DDL is auto-committing, so this
does not claim rollback. Timeout/connection-loss/unknown acknowledgment is
`RESTORE_OUTCOME_UNKNOWN`. Failed independent comparison is
`RESTORE_VERIFICATION_FAILED`. All prohibit automatic retry. Partial test targets
remain until separately guarded fixture teardown; no automatic repair is attempted.

The migration scenario restores A, proves exact schema4 equality, applies unchanged
0005 DDL on A only, commits locked bootstrap+ledger5 atomically, checks schema5/21
tables and unchanged old facts/objects/Current/Observations, then restores the
original untouched encrypted package into fresh B and proves schema4 equality
again. It implements no production rollback or automatic database switching.

## Later Dogado prerequisites — NOT verified live here

Repository inspection confirms the existing non-interactive Actions SSH/SFTP path
and fixed SELECT-only read account. `read_access.php` deliberately accepts only
SELECT/SHOW VIEW on the isolated database. These do **not** prove RELOAD/FLUSH lock
rights, full SHOW CREATE routine/trigger/event visibility or suitable backup rights.
No existing credential value was read and no Dogado connection was opened.

A separate authorized assignment must first establish actual DB bytes/row counts,
all objects and full visibility, existing approved backup-capable identity and tools,
whether write/DDL quiescence/global-lock privileges are permitted, scope of impact
on other databases, actual free space plus scratch/encryption overhead, retention,
trusted off-host key custody and private storage outside every webroot. If existing
access is insufficient, stop and report exact missing evidence; do not request new
passwords or pretend SELECT-only is sufficient. This test-only executor is not a
fallback for Dogado. A future live adapter requires separate review and authorization.

Before migration0005: verified encrypted live backup, complete isolated restore
comparison, full object visibility, fresh unchanged source fingerprint immediately
before migration, installed release qualification and separate migration approval
remain mandatory. This synthetic success supplies none of those live permissions.

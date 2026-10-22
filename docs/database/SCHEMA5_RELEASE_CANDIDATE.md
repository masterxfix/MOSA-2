# Explicit schema4/schema5 candidate — offline only

The installed Collector is unchanged. No Dogado connection, upload, deployment,
migration, provider acquisition or operating permission is part of this change.
Both operation/budget configurations remain disabled; provider rights remain false.

## Separate immutable contracts

The historical `collector_release_contract.json` remains byte-identical to commit
`6fa0655088f5ae2b37b7043b10a568d4aa2f14fb`: 33 files with exact Git blob pins.
It cannot package today's changed sources. Its original tests/build run at that
qualified commit, without rewriting its pins or relaxing its checks.

`collector_release_contract_schema5_v1.json` separately pins the complete candidate:
53 files, including `schema_contract.php`, migration0004/0005 hash resources,
normative unit seed, shared API value/selection primitives and catalog, existing
Current planner/refresh/outcome/bounded subprocess and takeover dependency chain.
All Python/PHP modules remain the existing implementation; no second writer or
selection algorithm is introduced. Dynamic subprocess/resource edges are recorded
in addition to checked static Python imports and PHP includes (including lazy ones).
There is no new service, scheduler, web endpoint or launch command. Original public
entrypoints remain identical; Current libraries retain their existing internal
planner subprocesses. Merely loading the libraries performs no DB/provider I/O.

Build with `scripts/collector_release.py build --profile schema5 --commit <full SHA>
--output <new private local directory>`; verify with the same arguments and `verify`.
The default profile remains historical. Separate output directories are mandatory;
build refuses an existing directory. Each manifest binds commit, contract SHA-256,
every file SHA-256/size/mode, runtime pins and exact entrypoints. USTAR ordering,
timestamps, owners and modes are deterministic. Verification rebuilds from the
exact Git commit and rejects missing/foreign/changed files, links, forged manifests
and wrong commits. A candidate cannot pass historical-profile verification.
Only pinned allowlisted tracked blobs are packaged, never environment credentials.

Verified local deterministic USTAR SHA-256 (Git/LF source bytes):

| Payload | Archive SHA-256 |
| --- | --- |
| Historical33 at `6fa0655088f5ae2b37b7043b10a568d4aa2f14fb` | `73e34c8d8e13ce37265ef5dded1ceae162140eee5b17341b23ee7dae3e3a68f7` |
| Separate schema5 candidate53 | `dbbf91b6f174bb2d5190c22c131c654159e6db282dc638ea1040b2a4a6b0b40b` |

Historical contract SHA-256 is
`26f636d66b880dfd62891230fbcf97a91091c20cc567f255bef806ad7710dcd2`;
candidate contract SHA-256 is
`2a9e9d2ad57508f3bda2d131acef2997cbb258af73378f80eb58a4e35afc1e0c`.
These are repository artifacts, not a new measurement of the installed package.

The `schema5` mode in `collector-release-offline.yml` prints historical and candidate
archive/manifest SHA-256 plus the full candidate per-file manifest. The disabled
candidate remains exclusively in the temporary runner directory; no artifact or
release upload is performed. Those run outputs are the authoritative
artifact hashes. The manifest SHA-256 additionally binds the final commit; the
USTAR SHA-256 covers payload bytes independently of that manifest.
No offline test job receives hosting secrets. `schema5` cannot reach the separate
`migration5-readonly` job, even if `read_preflight` is supplied.

## Explicit contracts and transition matrix

Schema4 is the Current/runtime default. Schema5 requires integer
`state_contract.schema_version=5`; there is no discovery, fallback or automatic switch.
The runtime configuration helper accepts this explicit version. Legacy historical
proof callers retain their original schema3 default; schema4/5 callers set their
contract. Current uses the same selected contract for preflight, transaction capture
and independent readback; collector dispatch receives that identical contract.

| State | Compatibility and execution boundary |
| --- | --- |
| A: original Collector4 + DB4 | Historical package retains its qualified behavior; configuration remains disabled. |
| B: candidate explicit4 + DB4 | Exact 17-table/ledger1–4/unit/route contracts; existing behavior preserved. |
| C: DB5, Collector disabled | Old/explicit4 fails `table_set` before acquisition. No transparent compatibility. |
| D: candidate explicit5 + DB5 | Exact21-table/ledger1–5/hash/unit/route contract accepted only with locked anchors. Acquisition stops `schema5_collector_locked`. |
| E: Current explicit5 + DB5 | Same existing atomic writer/planner/readback; independent route and execution authorizations still required. |

Version conflicts fail before requests. Ledger errors use `ledger_versions`,
`ledger_checksum`, `schema5_ledger_keys`; bootstrap errors use `schema5_job`,
`schema5_module`, `schema5_state`, `schema5_activity`. Schema5 requires the exact
UNWIRED disabled job, module5 LOCKED, initial IDLE/latched state and empty reservation
activity tables. Compatibility does **not** authorize opening that latch or running
the Collector. Such operation still needs a separately reviewed implementation and
approval. No automatic retry, schema repair or job/route activation is implemented.

Current approval scope, native v2/dedupe/provenance, market/observed ordering,
disabled-route permission, locking, atomicity, rollback, independent readback,
replay and timeout/OUTCOME_UNKNOWN rules remain intact. The consumed
`current-once-39634298612` authorization tombstone is unchanged. This candidate
creates no replacement execution authorization.

## Later authorized installation/migration order

1. Verify an encrypted schema4 backup and isolated restore. Prove full visibility
   of triggers/routines/events; take a fresh bounded Dogado baseline.
2. Review candidate hashes, exact dependency closure, installed PHP8.4.12/Python3.11.17
   pins and separate private release location. Installation requires separate approval;
   retain the old package and keep all execution switches disabled.
3. Qualify the new package explicitly against DB4 before changing the DB. Stop any old
   schema4 consumer before migration; do not let it silently continue on DB5.
4. Obtain separate migration authorization. Follow migration0005 PREPARE's exact
   backup/baseline/DDL-interruption/locked-bootstrap/ledger requirements. No migration
   executor or migration permission is supplied here.
5. Verify schema5 and unchanged business facts independently; explicitly configure
   the candidate and Current for5. Do not enable the Collector job or routes. Keep the
   original4 package only for historical proof, not as a runtime fallback on DB5.
6. A separately scoped future review must resolve remaining provider rights, budgets,
   reservations execution and operating approval. Any future Current write needs its
   own valid authorization; the old consumed five-asset plan remains blocked.

Repository compatibility, synthetic MySQL8 results and reproducible archives do not
prove that the installed release has changed. Migration0005 remains blocked pending
the independent backup/restore, object visibility, fresh inventory and authorization
requirements above.

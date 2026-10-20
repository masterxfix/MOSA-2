# Prepared Current and read-only market display

The display is an explicit extension of the manual collector, not an implicit
change to its observation-only default. `MarketCurrent\run` uses the existing
sequential `MarketBatch\run`, adapter, normalizer and v2 writer. It first checks
the whole configured scope and its Current approvals without a provider call.
An unchanged acquired fact is accepted only by this opt-in caller. The default
live persistence still requires an INSERT and an empty Current under schema 3.

## Current selection

An approval pins the complete physical route row by SHA-256, its revision and
unit contract. Disabled routes require `allow_disabled_projection: true` in
that separate, explicit approval. This grants only this Current projection;
it neither activates the route nor permits a scheduler or automatic collection.
Changing any route field invalidates the approval. No route is selected from
database order or activated implicitly.

For each approved asset/source/route the bounded query loads the latest two
native v2 facts by market time, then observed time. The existing v2 writer
validates their stored dedupe keys, payloads, identities and unit bindings.
The larger `(market_at, observed_at)` pair wins. Older pairs leave Current
unchanged. Equal pairs with equal canonical facts leave it unchanged, including
`updated_at`. Equal pairs with different canonical facts stop the entire
Current transaction. Database IDs never resolve a semantic conflict. The
existing unique dedupe constraint makes two candidates sufficient to expose a
conflict in the winning pair. The current origin is independently loaded and
validated; an altered or untraceable Current row is rejected.

Current copies the native exact price, bid, ask and quote/quantity basis. It
stores the selected Observation ID, format 2, dedupe key and route revision.
No FX conversion or floating point arithmetic occurs. A point observation's
volume is not a day's volume. All day prices, previous close and day volume
stay NULL. No price change is invented.

The collector retains its per-item atomic commits and independent readbacks.
Only a COMPLETE batch can proceed to one atomic Current transaction for its
whole scope. A partial batch never projects Current. A Current failure after a
successful batch reports CURRENT_FAILED: already stored observations remain
valid, Current rolls back, and there is no automatic retry or provider call.
An independent connection verifies the committed Current and unchanged other
tables. This is a manual, bounded path, not a parallel or scheduled service.

Existing stored observations can also be projected without running the collector:
the shared `planner.plan` / `MarketCurrent\refresh` path has no provider dependency.
An explicitly authorized administration session may transport the same planned
values to the database when a PHP writer login is unavailable. It must check the
reviewed stored state, preserve atomicity, and independently verify the exact
Current rows, unchanged other tables and an `UNCHANGED` replay. It must not
reimplement selection, normalize prices again, or rerun an applied migration.

## Version 4 migration

`0004_current_observation_provenance.sql` adds four nullable provenance columns,
one index, one restrictive foreign key and one enforced CHECK to Current.
It does not alter observations, routes, units, Bars or other business data.
The existing exact schema checker is reused with a version 4 extension.

Live application requires a read-only preview of exact schema 3 metadata and
all existing facts, an approved preview hash and SQL checksum, and a private
recoverable backup. The apply function rechecks the preview before its single
atomic MySQL ALTER. MySQL DDL auto-commits: a post-DDL failure stops without a
retry or ledger insertion. Diagnose the preserved state before any separately
approved repair. Ledger 4 is inserted only after the exact metadata and
unchanged facts pass; an independent readback follows. Schema 3 callers keep
their original contract unless they explicitly opt into schema 4.

## Read-only web path

`api/market.php` loads only the fixed subscription-private
`mosa2-market-read-private/access.php`, outside the document root, mode 0600 in
a mode 0700 directory. It contains the separately approved permanent read-only
account and a bounded asset/route configuration. It is unrelated to temporary
operator gateways. No credentials belong in this repository or HTTP responses.
Installation verifies the account, isolated database and grants, rejecting
privileges beyond SELECT / SHOW VIEW on the isolated test database.
When provisioned before migration 4, it checks empty Current and bounded
asset/route references under schema 3 without querying future provenance
columns. Under schema 4 it verifies the actual Current reader instead.
Database-name underscores must be escaped in grants, unless the actual server
has `partial_revokes` enabled and therefore treats them literally. This prevents
an apparently exact database grant from widening into a wildcard scope
([MySQL GRANT contract](https://dev.mysql.com/doc/refman/8.0/en/grant.html)).

Password-free access is a separate hosting capability, not a consequence of
using localhost. Plesk-managed database users require a nonempty password
([Plesk account contract](https://docs.plesk.com/en-US/obsidian/administrator-guide/website-management/website-databases/managing-database-user-accounts.69539/)).
If the available hosting interface has no password-free authentication mode and
the server has no socket-authentication plugin, retain the explicitly approved
working reader configuration and report that boundary. Do not remove the
configuration, alter server administration accounts or imply that a password
was removed. Password-free local access would still permit other processes
running as the same webspace user; it does not isolate those processes.

The endpoint accepts GET only, uses native prepared statements, a read-only
transaction, and at most one LIMIT 1 Current query per configured asset
(maximum ten; milestone acceptance scope two). There are no observation-history
scans, providers, collector imports, mutations, query-controlled assets or
retries. It returns exact decimal strings and unit versions, source/venue,
market time, observed time and status. Binding errors fail closed. Responses
are private/no-store; errors contain no database diagnostics.

Status is `missing` without Current, `stale` when market time exceeds the
configured age, otherwise `stored`. Recent acquisition never freshens an old
market time. The initial policy is 1,800 seconds and the page makes no real-time
claim. GBX remains GBX even when its currency dimension is GBP.

## Browser acceptance

HTML and reserved space appear before the async same-origin data GET. Local
failure does not remove the shell. Shared CSS covers desktop and mobile states.
Prices are formatted as strings with all significant decimal places preserved.
DOM data attributes retain exact native price/unit and full UTC timestamps.
The existing Navigation Timing load indicator stays intact. A separate timing
records `performance.now()` after two animation frames following data rendering;
failure timing is explicitly marked unsuccessful. Browser evidence must show
the actual viewport, shell/paint timing, navigation duration, successful data
completion below 2,000 ms, and displayed values matched to independent DB reads.
Offline DOM tests are not live/browser/performance proof. Two assets are not
a scale, production, scheduler or broad route approval.

A fixed same-origin browser frame can test the actual homepage's responsive
document viewport when the browser's viewport override is ineffective. Record
the frame document's measured `innerWidth`/`innerHeight`, scroll width, successful
data timing and values. Identify this as a responsive browser-frame test,
not a physical-phone or device-emulation test.

Before any testsite change back up the exact existing files; verify uploaded
hashes and retain a private rollback map. Keep inherited authentication in place.
Remove temporary gateways and helpers after proof; keep only the approved
permanent read-only configuration and necessary rollback backup protected.
Production deployment is excluded. The completion commit uses `[skip ci]` on
main; the exact commit gets one workflow_dispatch on a temporary branch with
the production deploy skipped. Delete that branch after the Linux run.

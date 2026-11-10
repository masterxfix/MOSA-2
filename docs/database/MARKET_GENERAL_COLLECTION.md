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
Only the ISINs explicitly listed in expected_isins are selected before planning. Exactly those requested assets must qualify; other qualified assets must not be included.
No new route, source, asset, migration or scheduler state is written.

Authorization: `MOSA2-MARKET-BATCH:<full SHA>:<SHA256 of exact UTF-8 scope input>`.
The Python runner verifies the dispatch context, attempt, SHA, budget and scope
authorization before SSH. The token string binds scope; it is not a GitHub credential.
User approval for a historical PNE or five-asset run does not authorize this workflow.
Exactly one separately approved batch is to be dispatched; no retry or replacement run.

The first live collector acceptance can use a single qualified ISIN and an exact
request_budget of 1, without changing the general collector. Provider GETs and test-DB
writes still require explicit authorization. The separate testsite ISIN input is a
read-only on-demand provider preview; it never silently dispatches a GitHub Action
or writes observations. This live execution is not yet approved
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

## Rund-um-die-Uhr-Kurse

Die Browserautomatik nutzt den eingestellten Takt unabhängig vom deutschen
Handelskalender. Quellabrufe bleiben sequenziell. Ein HTTP 429 pausiert weitere
Abrufe für denselben Host in der Sitzung. Andere Hosts können weiter liefern.
Die Ansicht nutzt zusätzlich den schreibgeschützten Endpunkt
api/market.php?view=best für den freigegebenen Veröffentlichungsumfang.
Eine identische Marktzeit behält beim erneuten Abruf die erste Erfassungszeit.

Der vorhandene Scheduler akzeptiert für einen geprüften privaten Betrieb
die Policy UTC_900_V1 mit calendar=null. Die passende Budget-Proposal enthält
schedule_policy=UTC_900_V1, timezone=UTC, assets und interval_seconds=900.
Die UTC-Takte werden alle 15 Minuten fällig. Der Kalendertag für das bestehende
Budget richtet sich weiterhin nach Europe/Berlin. Die geschützte Scheduler-Sidecar
kann mit --private-operation operation_config und budget_config gemeinsam aufnehmen. Für jede
Betriebsfreigabe bleiben Provider-Rechte, dokumentierte Limits, frische
MOSA-Vergleichsdaten, DB-Job und geprüfte Route erforderlich. Die veröffentlichten
Standardkonfigurationen sind deaktiviert. Die Schema-5/6-Sperren bleiben wirksam.

Gettex MUND nutzt die veröffentlichten verzögerten Posttrade-Dateien mit
expliziter ISIN und UTC-Zeitstempel. Der manuelle Archivimport ist an den
geprüften Commit, genau eine ISIN, das UTC-Dateifenster und den SHA-256 der
Originaldatei gebunden. Er prüft die geschützte Testdatenbank, registriert bei
Bedarf Quelle und deaktivierte Route zur bestehenden ISIN und nutzt den
vorhandenen Observation-v2-Writer und Current-Readback. Die Variable
MOSA_MARKET_GETTEX_PRIVATE_USE=1 bezieht sich auf die private, zugriffsgeschützte
Testsite. Die Verarbeitung und die Originaldatei bleiben auf Dogado. Der
öffentliche Actions-Bericht enthält nur Prüfergebnisse und Zähler.

Der Erstlauf erlaubt einen GET und reserviert die ISIN und Datei gemeinsam.
Wenn Dogado den Datei-Endpunkt nicht erreicht, kann die Originaldatei über den
vorhandenen privaten Dateizugang im reservierten Ordner bereitgestellt werden.
Der separate Wiederanlauf prüft Eigentümer, Dateityp, Größe, Modus und
Prüfsumme. Er verwendet den erfassten UTC-Dateizeitpunkt und sendet keinen
weiteren GET. Jede Wiederanlaufreservierung lässt genau eine Ausführung zu.
Eine bestätigte Route ist keine Freigabe für den Scheduler.

Auf Dogado konnte der Diagnose-Lauf die TCP-Verbindung zum gettex-Archiv auf
Port 8000 nicht aufbauen. Der Wiederanlauf mit der geprüften Originaldatei
bestand die unabhängigen Observation- und Current-Readbacks ohne Provider-GET.
Nachweise: [Verbindungsprüfung](https://github.com/masterxfix/MOSA-2/actions/runs/42772931393)
und [privater Archivimport](https://github.com/masterxfix/MOSA-2/actions/runs/42773391152).

Vor dem Dauerbetrieb sind die Verbindung vom Scheduler zum veröffentlichten
Datei-Endpunkt, der bestehende Freigabestand von Schema und Job, die
nicht-interaktive Secret-Übergabe und dokumentierte Providerlimits zu prüfen.
Der veröffentlichte Viertelstundentakt der Dateien begrenzt den sinnvollen
Bedarf auf höchstens einen Abruf je veröffentlichter Datei mit Wiederverwendung
für die zugeordneten ISINs. Der Takt ist keine zugesicherte Provider-Obergrenze.
Die Yahoo-HTTPS-Quelle bleibt bis zur bestätigten Zustimmung
für automatisierte Abrufe gesperrt. Die zusätzlichen Währungseinheiten sind ein
eigenes versioniertes Paket. Bestehende Seed-Definitionen bleiben bytegleich.
Ein physischer Writer-Route-Binding für eine neue Währung setzt den passenden
eingefrorenen Datenbankeintrag voraus.

- [Gettex Delayed Data](https://www.gettex.de/handel/delayed-data/)
- [Yahoo-Nutzungsbedingungen](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)

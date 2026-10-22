# MOSA 2: technischer Betriebsstand

Stand: 22.10.2026. Schema 4 bleibt verbindlich. Diese Übersicht unterscheidet
nutzbare Komponenten von einer tatsächlich freigegebenen Live-Ausführung.

## Aktive Komponenten und Datenweg

| Aufgabe | Gemeinsame Implementierung | Betriebsgrenze |
| --- | --- | --- |
| Registry-Qualifikation | `scripts/market_collector/live_batch.php::qualify` → `live_persistence.php::qualifyBatch`, `onboarding.php`, `live_persistence.php::completePlan` | Vorhandene eindeutige Identifier, Assets, Sources und physische Routen; vollständige private Qualifikationsnachweise erforderlich. Aktien und ETFs verwenden denselben Weg. Keine automatische Freigabe. |
| Erfassung | `market_collector/collector.py`, `boerse_frankfurt.py`, `yahoo_chart.py`, `http_transport.py` | Adapter normalisieren native Snapshots. Frankfurt verwendet den vorhandenen Request-Descriptor. Yahoo verarbeitet ausschließlich einen bereits qualifizierten privaten, symbolgebundenen Descriptor; kein Symbolsuchlauf. Für Yahoo liegt noch kein freigegebener privater Live-Descriptor vor. |
| Observation | `normalizer.py` → `phase3n/writer_plan.py` → `phase3o/live_writer.php`, koordiniert durch `runtime_persistence.php` | Ein Writer, ein Dedupe-Vertrag, Transaktion, Readback und Replay; sequenzieller Batch stoppt bei Fehlern oder unbekanntem Ausgang. |
| Current | `market_current/refresh.php` → `planner.py` → `selection.php` → `api/market_core/selection.php` | Bestehender Current-Writer. Frische physische Routenfreigaben, Herkunft und unveränderter Bestand erforderlich. Historische Einmalpläne sind keine allgemeine Betriebsfreigabe. |
| Webanzeige | `api/market.php`, `current_read.php`, `observations_read.php`, `qualified_scope.php`, bestehendes JavaScript | Current liest ausschließlich gespeicherte Projektionen. Observation dient der Herkunftsprüfung und der getrennten Observation-Ansicht. Kein Provideraufruf beim Seitenaufbau. Dynamische Auswahl ausschließlich aus vollständig validiertem Current, keine Registry-Veröffentlichung. |
| Zeit- und Budgetentscheidung | `collector_operation_plan.py`, `collector_cycle.py`, `provider_budget_plan.py` | Reine Simulation. 60/900 Sekunden, Europe/Berlin einschließlich DST, dokumentierte Kalender-/Providerlimits, Stopps und keine Wiederholungen. Umfang 1–10, keine feste Fünferliste; Provider im Zyklus explizit auswählbar. |
| Testsite-Deployment | `.github/workflows/deploy-testsite.yml`, `scripts/deploy_test_sftp.py` | Ausschließlich manuell, exakter Commit und Dateiumfang, Sicherung und SHA-256-Readback. |
| Produktionsdeployment | `.github/workflows/deploy.yml` | Kein Push-Trigger. Manueller Aufruf benötigt exakten Commit und `DEPLOY_PRODUCTION:<vollständiger Commit>`. |

Pfade ohne Präfix in der Collector-Zeile liegen unter `scripts/market_collector/`.
Die vorhandene Gestaltung, Schriftarten und Farben bleiben unverändert.

## Erhaltene Datenbank

Die 17 Schema-4-Tabellen bleiben unverändert:
`m2_entities`, `m2_sources`, `m2_relationships`, `m2_files`, `m2_events`,
`m2_jobs`, `m2_job_runs`, `m2_assets`, `m2_asset_identifiers`,
`m2_asset_source_routes`, `m2_schema_migrations`, `m2_sync_checkpoints`,
`m2_module_state`, `m2_market_current`, `m2_market_observations`,
`m2_market_bars`, `m2_units`.

Migrationen 0001–0004, Unit-Katalog, vorhandene Current-Provenance und Daten
werden durch diese Codearbeit nicht verändert. Es erfolgt weder eine
Migration noch eine Bestandsmutation. Dies ersetzt keine neue Live-Inventur.

## Noch offene Funktionen und Aktivierungsbedingungen

- Providerrechte, tatsächliche Abrufgrenzen und belegter Handelskalender sind
  nicht freigegeben. Die Repository-Ausführungsschalter bleiben unverändert.
- Der persistente Reservierungsprototyp `collector_persistence.py` benötigt
  Schema-5-Tabellen. Er wird nicht in die Schema-4-Laufzeit eingebunden.
  Damit ist eine dauerhafte, gegen Neustarts gesicherte 60/900-Automatik noch
  **nicht** ausführbar. Eine reine Zyklusentscheidung ist kein Schedulerbeweis.
- Die öffentliche Auswahl startet dynamisch bei `m2_market_current`. Eine
  ausdrücklich autorisierte und vollständig validierte Current-Projektion ist
  gemäß Nutzerentscheidung die Anzeigefreigabe. Beide Ansichten prüfen zuvor
  dieselbe Current-Provenance. Reine Registry- und Observation-Einträge bleiben
  privat. Höchstens zehn Assets, eine elfte Zeile blockiert statt abzuschneiden.
  Der bestehende qualifizierte Frankfurt-Routenvertrag wird weiter geprüft.
  Andere registrierte Sources benötigen gültige physische Route-/Unit-Verträge
  und die validierte Current-Provenance; unbekannte Handelsplätze werden nicht erfunden.
  Historische Fünferlisten liegen ausschließlich im CLI-Nachweisbereich.
- Der vollständige synthetische Datenweg verwendet vorhandene Writer-/Current-
  Planer und die Webdarstellung. Er beweist weder einen echten Providerabruf
  noch reale DB-Persistenz oder eine neu sichtbare Live-Notierung.
- Seitenziele <1 s, p95 <1,5 s, harte Grenze 2 s bleiben bestehen. In dieser
  Offline-Codearbeit wurden sie nicht live gemessen.

## Archivierte Einstiegspunkte

Nach `.github/archived-workflows/` verschoben und damit für Actions deaktiviert:
`collector-live-test.yml`, `collector-dogado-pne.yml`,
`collector-dogado-batch.yml`, `collector-performance.yml`,
`collector-db-locality.yml`.

Ihre von Tests und anderen Modulen tatsächlich verwendeten PHP-/Python-
Bibliotheken bleiben erhalten. Der historische Dogado-Qualifizierer delegiert
an `MarketBatch\qualify`; es gibt keine zweite Aktien-/ETF-Qualifikation.
Die vorhandenen Quellen-/Negativtests lesen die archivierten Workflowdateien
weiterhin. Historische Nachweisdokumente werden nicht neu geschrieben.

Schema-5-Verträge, Migration 0005 und isolierte Tests bleiben als gesperrte
Vorbereitung erhalten. Sie werden weder installiert noch als aktive
Schema-4-Betriebsfähigkeit dargestellt. Alte APPLY-Freigaben bleiben verbraucht.

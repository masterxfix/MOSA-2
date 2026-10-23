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
| Scheduler (vorbereitet, deaktiviert) | `scripts/collector_scheduler.php`, `collector_scheduler_decision.py`, bestehende `m2_jobs`/`m2_job_runs` | Ein CLI-Tick, MySQL-Sperre, vor Abruf bestätigte Reservierung, sticky Stopp bei ungeklärtem Vorgänger; kein installierter Cronjob. |
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
  Der separate Schema-4-CLI-Scheduler verwendet stattdessen die bestehenden
  Jobtabellen. Der Prototyp wird dafür weder aktiviert noch umgebaut.
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

## Manueller Scheduler-Start; Plesk-Zugang noch nicht bereit

Einziger Einstieg: `/opt/plesk/php/8.4/bin/php <privates-release>/scripts/collector_scheduler.php <freigegebene-private-konfiguration.json>`.
Nur ein ausdrücklich autorisierter manueller Aufruf mit geschützter STDIN-Pipe
ist vorbereitet. Der gemeinsame Python-Zyklusvertrag entscheidet über 60/900 Sekunden in Europe/Berlin. Python bleibt
`/opt/alt/python311/bin/python3.11`. Der CLI-Start benötigt keine neue Installation.
Cron-Jitter innerhalb derselben Minute wird dem aktuellen UTC-Slot zugeordnet;
verpasste Slots werden nicht nachgeholt. Kalenderlücken blockieren.

Beide Repository-`execution_enabled`-Schalter bleiben false. Ohne diese beiden
ausdrücklichen Betriebsfreigaben beendet sich der Einstieg vor STDIN-Lesen,
privater Konfiguration, DB-Verbindung und Provideraufruf mit DISABLED. Die bestehenden Providerrechte,
dokumentierten Limits, MOSA-Priorität, frischen Baseline-/Monitoringnachweise,
Kalenderfreigaben und exakten Current-Routenfreigaben werden zusätzlich geprüft.
Die Modellansicht von `collector_cycle.py` erteilt selbst keine Ausführungsfreigabe.

Für eine spätere Aktivierung sind extern erforderlich, hier **nicht** eingerichtet:
- Freigegebener privater Release-/Arbeits-/Konfigurationspfad außerhalb des Webroots;
  vorhandene Dateien mit 0600, Arbeitsverzeichnis 0700, keine Symlinks.
- Für einen ausdrücklich autorisierten manuellen Start: geschützte, nicht-interaktive
  STDIN-Pipe aus dem bereits freigegebenen Zugang. Ein JSON-Objekt mit genau dem
  Feld `password`, maximal 4096 Bytes insgesamt, Passwort 1–1024 UTF-8-Bytes ohne
  Steuerzeichen und nicht ausschließlich Leerraum; EOF innerhalb von zwei Sekunden.
  Terminal und reguläre Datei als STDIN werden abgewiesen. Keine Übergabe über
  Argumente, Umgebung oder Dateien; keine Dialoge, Protokollierung oder Ausgabe
  des Secrets. Der gemeinsame DB-Connector bleibt unverändert.
- Ein ausdrücklich provisionierter Job in den bestehenden Schema-4-Tabellen:
  `job_key=market_collector_scheduler_v1`, `module_key=market_collector`,
  `handler_key=collector_scheduler_v1`, enabled=1. Kein automatisches Anlegen,
  Aktivieren oder Zurücksetzen eines Jobs durch den Scheduler.
- Private JSON-Konfiguration mit `private_root`, `provider`,
  `manifests`, `current_approvals`, `evidence_file`. Manifeste und Freigaben sind
  bestehende qualifizierte Verträge, keine erzeugten Provider- oder Routenrechte.
  Die Auswahl stammt aus der Operation-Konfiguration und wird vollständig über
  `MarketBatch::qualify`/`completePlan` validiert; keine feste Assetliste.
  Der bestehende Budgetvertrag begrenzt den tatsächlich zulässigen Umfang.
  Der vorhandene Qualifikationsvertrag verlangt eine Assetklasse pro Zyklus.
- Frische private Evidence für `budget_state`, `mosa_baseline`,
  `monitoring_previous`, `monitoring_event` aus dem vorhandenen Betriebsnachweis.
  Unbekannte externe Aktivität wird nicht durch einen erfundenen Nullverbrauch
  ersetzt. Eigener Verbrauch, Vorgänger und Receipts kommen aus den DB-Jobruns.

Die benannte MySQL-Sperre bleibt vom Bestandslesen über Reservierung, bestehenden
Collector/Current-Aufruf bis zur Abschlussquittung gehalten. `m2_job_runs`
reserviert vor dem ersten möglichen Provideraufruf konservativ den gesamten
Zyklusumfang mit attempt_no=1. Ein bestätigter Abschluss enthält den geschützten
Receipt; Ausfälle hinterlassen running/failed als dauerhafte Sperre, auch nach
Neustart oder Tageswechsel. Keine Lease-Verfallszeit und kein automatischer Retry.
Ein neuer Zyklusordner wird erst nach Reservierungs-Commit unter dem später
ausdrücklich freigegebenen Arbeitsroot angelegt; verbrauchte Provider-Markierungen
werden nie gelöscht oder wiederverwendet. Observation/Current bleiben ausschließlich
im vorhandenen `MarketCurrent::run`-Datenweg mit dessen Readbacks und Dedupe.
Andere Geschäftstabellen, Routen und Freigaben werden nicht vom Scheduler geändert.

Die neue isolierte Schedulerprüfung ersetzt keinen Live-Nachweis von Plesk,
MySQL-Sperren oder Providerbetrieb. Schema, Migrationen, Webdateien und Design
bleiben unverändert; kein Cronjob, Deployment oder Live-DB-Schritt gehört dazu.

### Offene Zugangsvoraussetzung für unbeaufsichtigtes Plesk-Cron

**Automatischer Plesk-Betrieb ist nicht bereit.** Ein Plesk-Cronjob erhält keine
GitHub-Actions-Secrets. Die bestehende manuelle geschützte STDIN-Übergabe ist
allein kein Bereitstellungsweg für einen unbeaufsichtigten Minutentakt.
Es fehlt ein bereits vorhandener, ausdrücklich autorisierter und nachweislich
sicherer Weg, der dem Plesk-Prozess das DB-Secret nicht-interaktiv und ausschließlich
im Arbeitsspeicher/über eine geschützte Pipe bereitstellt. Ein solcher Weg ist
hier nicht nachgewiesen. Es wird weder eine Ersatzdatei noch eine Umgebungsvariable
oder neue Credential-Infrastruktur angelegt. Bis zu diesem Nachweis bleibt die
automatische Aktivierung gesperrt; alle übrigen Betriebsfreigaben bleiben erforderlich.

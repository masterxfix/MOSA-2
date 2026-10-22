# Collector-Persistenz und atomare Reservierung

Vorbereiteter Adapter, **keine Betriebsfreigabe**. `collector_persistence.py`
hat weder Verbindungsdaten noch CLI, Scheduler, Transport oder Migrationstarter.
Nur der isolierte Test verdrahtet seine DB-API-Factory. Beide Konfigurationen
bleiben unverändert deaktiviert, `rights_confirmed=false` bleibt bestehen.
Jeder Bericht enthält `execution_authorized=false`, `actual_provider_requests=0`,
keinen Retry und kein automatisches Resume. RUN_ELIGIBLE bleibt Planung;
der vorhandene Dry-Run bleibt datenbankfrei.

## Schema und Wiederverwendung

0001–0004 bleiben unverändert. Die vorbereitete Migration 0005 verwendet
`m2_jobs` als deaktivierte Identität mit Handler `UNWIRED` und `m2_module_state`
als Versionsanker 5, Status `LOCKED`. Abweichungen blockieren. Das sind keine
Ausführungsrechte. `m2_job_runs` erlaubt nur running/completed/failed/cancelled;
Request-Identitäten, Teilfehler-/Unbekanntstatus und Quoten fehlen.
`m2_sync_checkpoints` bildet Source-Cursor ab, keine Verbrauchsbuchführung.
Deshalb werden vier InnoDB-Tabellen ergänzt:

| Tabelle | Vertrag |
| --- | --- |
| `m2_collector_state` | Provider-Lock, IDLE/RUNNING/COMPLETE/FAILED/PARTIAL_FAILED/OUTCOME_UNKNOWN, Stoppsperre, aktiver/letzter bestätigter Zyklus, offener Request, Vorgangsmarker, monotone UTC-Zeit, fester Fehlercode |
| `m2_collector_cycles` | Unique UTC-Zyklus/Slot, Provider-FK, geordnete ISIN-/Asset-Auswahl, Besitzerkennung, Konfigurationshash, Start/Ende, reservierte und bestätigte Versuche |
| `m2_collector_days` | Dauerhafter Verbrauch je Provider/Berliner Tag; keine Rücksetzung oder Erstattung |
| `m2_collector_requests` | Unique Zyklus/Asset und Zyklus/Position, Asset-/Tages-FKs, UTC-Reservierung, Berliner Tag, RESERVED/CONFIRMED/FAILED/OUTCOME_UNKNOWN, bestätigter Versuch |

Bootstrap: IDLE, Stoppsperre 1, `INITIAL_LOCK`, Job deaktiviert. Es gibt **keine
Entsperr-, Reset-, Enable-, Übernahme- oder Resume-Funktion**. Nur die synthetische
Fixture setzt ihren eigenen temporären Zustand frei. Eine produktive Migration
samt Bestandsübernahme und gesondertem Freigabevertrag fehlt ausdrücklich.

## Transaktionsvertrag

1. Dedizierte Verbindung, UTC, READ COMMITTED, Lockwartezeit 3 Sekunden und
   SELECT-Grenze 2 Sekunden. Die Factory muss zusätzlich endliche Connect-/Read-/
   Write-Limits setzen (Test: 3/5/5 Sekunden).
2. `SELECT ... FOR UPDATE` sperrt die Provider-Zeile. Versionsanker, Job,
   Zustand und Vorgänger werden geprüft. Ein eindeutiger Vorgangsmarker wird
   **vor** der Reservierung separat dauerhaft bestätigt. Vorhandene Marker
   blockieren; es gibt weder TTL noch Übernahme.
3. Die Haupttransaktion sperrt dieselbe Zeile und prüft Marker/Besitzer, Zyklus,
   sequenzielle Aktienidentität gegen aktive Equity-/ISIN-Stammdaten,
   unveränderte Konfiguration, Dauer, Qualifikation, Monitoring, frische
   MOSA-Baseline und tatsächlichen Verbrauch. Budgetprüfung, Tageszähler und
   Reservierungszeile liegen in **derselben geschützten Transaktion**.
   Unique-Constraints sichern zusätzlich die Identität.
4. Nur nach bestätigtem Hauptcommit wird der Marker separat entfernt.
   Eine neue Reservierung ist RESERVED/unresolved, bleibt verbraucht und wird
   niemals erneut erteilt, auch nicht an denselben Besitzer. Ein zweiter Prozess
   kann weder Marker noch offene Reservierung übernehmen.
5. Nur eingespeiste synthetische Abschlussnachweise über `record` schließen
   Versuche ab. SUCCESS setzt CONFIRMED; erst dann darf der nächste Wert
   reserviert werden. Fünf bestätigte Abschlüsse setzen COMPLETE und den letzten
   bestätigten Lauf. Fehler setzen FAILED/PARTIAL_FAILED und die Stoppsperre;
   TIMEOUT/MISSING_FINAL setzen OUTCOME_UNKNOWN.

Besitzerkennungen werden nicht zur automatischen Fortsetzung ausgelesen.
COMPLETE bestätigt hier synthetische Request-Abschlüsse, keine Observation-/
Current-Schreiboperation oder Marktwertprüfung. Ein realer Abschlussadapter
ist noch nicht angeschlossen.

## Abbruch, Neustart und Read-only-Abgleich

| Abbruchpunkt | Dauerhafter Schutz |
| --- | --- |
| Vor Marker | Keine Reservierung, kein Verbrauch |
| Unbestätigter Marker-Commit | Keine Haupttransaktion; gespeicherter Marker blockiert |
| Reservierung mit bestätigtem Rollback | Keine neuen Reservierungen/Zähler; Marker bleibt zur Prüfung |
| Unbestätigter Reservierungs-/Abschluss-Commit | OUTCOME_UNKNOWN; Marker bleibt unabhängig vom tatsächlichen Server-Commit |
| Nach Reservierung, vor möglichem Request | Reservierung verbraucht und unresolved, keine Wiederholung |
| Timeout/fehlender Abschluss | OUTCOME_UNKNOWN, Verbrauch und Stoppsperre |
| Neustart mit aktivem Vorgänger ohne Request | RUNNING blockiert neuen Zyklus, kein Resume |
| Hauptcommit bestätigt, Markerfreigabe ausstehend | Hauptzustand bleibt dauerhaft, Marker blockiert |

Eine verlorene Bestätigung der separaten Markerfreigabe ändert den bereits
bestätigten Hauptcommit nicht. Der betroffene Adapter bleibt vergiftet und
meldet konservativ OUTCOME_UNKNOWN. Ein separater Read-only-Abgleich kann
zeigen, ob nur die Freigabe aussteht oder der dauerhaft bestätigte Endzustand
vorliegt. Es wird weder Quote freigegeben noch ein Request wiederholt.

`inspect()` verwendet eine neue Verbindung und READ ONLY. Es prüft Verträge
und begrenzte Ledgerdaten, zeigt offene Marker als OUTCOME_UNKNOWN und verändert
weder Sperren noch Zähler. Ausgabe nur als feste Codes, UTC-Zykluskennungen und
Summen; keine SQL-/Exceptiontexte, Kurse, Zugangsdaten, Besitzerkennungen oder
Pfade. Fehlender/korrupter Zustand blockiert. Manuelle Auflösung gehört in einen
gesonderten Auftrag. Datenbankausfall führt nicht zum automatischen Retry.

## Budget und Zeit

`begin` verwendet die vollständige reine `collector_cycle.cycle`-Entscheidung
mit aus der Datenbank projiziertem Vorgänger und Verbrauch. Mitgelieferte
MOSA-2-Zähler überschreiben diese nicht. Jedes `reserve` verwendet erneut
`provider_budget_plan.admission` für genau einen Request, aktuelle Ledgerwerte
und frische MOSA-Evidenz. Strenges vorhandenes Monitoring wird wiederverwendet.
Konfigurationswechsel im Zyklus sind ausgeschlossen; keine zweite Limitlogik.

Minutenfenster: `(UTC jetzt − 60 Sekunden, UTC jetzt]`. Tageszähler: Europe/Berlin
mit 23-/25-Stunden-Tagen. Mitternacht löscht weder alte Tageszeilen noch offene
Vorgänge; Reservierungen des Vortags zählen weiter im Minutenfenster. Eine
rückwärts laufende Uhr blockiert. Die spätere Live-Uhr wäre Datenbank-UTC nach
dem Lock; ausschließlich Tests injizieren synthetische Zeit.

Indizierte Abfragen lesen höchstens 100001 Reservierungen je Fenster/Tag, sechs
je Zyklus und zwei offene Vorgänge. Über 100000 blockiert der Adapter: Das ist
eine Implementierungsgrenze, **kein Providerlimit**. Tageszähler und Ledger
werden gegengeprüft; der Adapter bietet keine Bereinigung/Erstattung.

MOSA bleibt unverändert und reserviert nicht unter diesem Lock. Deshalb gibt es
**keine vollständige gemeinsame atomare Providergarantie für MOSA/MOSA 2**.
Die kombinierte Entscheidung gilt für die belegte frische MOSA-Baseline; deren
parallele Änderung ist nicht atomar ausgeschlossen. Unbekannte Rechte/Limits/
Baseline blockieren. Positive Testwerte sind keine Providerfreigabe.

## Nachweise und Live-Blocker

Offline-Fehlerinjektion: `test_collector_persistence`. Reale InnoDB-Transaktionen,
Rollback, Unique-Constraints, Neustart und unabhängige parallele Verbindungen:
`test_collector_persistence_mysql`. Nur der vorhandene manuelle Offline-Workflow
mit `verification_scope=persistence` startet einen wegwerfbaren MySQL-8.0-Dienst.
Außerhalb GitHub mit explizitem Isolationsschalter werden DB-Tests übersprungen.
Der Client verbindet ausschließlich 127.0.0.1:3307 mit der festen Datenbank
`mosa2_collector_isolated`, ohne Projekt-DB-Helfer oder Secrets. Der Dienst hat
kein Passwort, ist nur an Runner-Loopback veröffentlicht und wird anschließend
entfernt. Keine neuen Passwörter oder Secrets werden angelegt.

Geprüft werden sequenzielle Reservierungen, sechster/doppelter Versuch,
Parallelität, Minuten-/Tageslimit, Tageswechsel und beide Zeitumstellungen,
Baseline/Limits, Stoppsperre, Vorgänger, Rollback und verlorene Bestätigungen vor
und nach tatsächlichem COMMIT. Collector-/Budget-/Current-/Quote-Regressionen
laufen im selben Workflow. Bestehende Release-Prüfschritte bleiben unverändert.
Ein lokal übersprungener MySQL-Test ist kein Locking-Nachweis; maßgeblich ist
der erfolgreiche Actions-Lauf für den exakten Abschluss-Commit.

Offen: produktive Migration/Bestandsübernahme, geprüfte Live-Factory und
Abschlussanbindung, Providerrechte, belegte kombinierte Limits, MOSA-Baseline
und Betriebsfreigabe. Kein Dogado-Zugriff, kein Providerrequest, kein Deployment
und keine Änderung des installierten Releases. Keine Produktionsbereitschaft.

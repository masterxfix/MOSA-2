# NEL ASA – Q2 2026 Importergebnis

Stand: 2026-11-08  
Repository: `masterxfix/MOSA-2`  
Datenbankziel: `h29077_mosa2_test`  
Asset: NEL ASA, ISIN `NO0010081235`

## Ergebnis

Der einmalige Importversuch wurde **nicht erfolgreich abgeschlossen**. Der autorisierte Lauf `42512074642` erreichte nach genau einem erfolgreichen PDF-Abruf den Adapter, stoppte dort mit `STOP_NO_RETRY` und erreichte den Writer nicht. Es wurden daher keine der fünf Q2-Fakten gespeichert.

Der aktuelle `main`-Commit für den Lauf war `de0e56d00c301d2f95ed195215c1ec9a312052c1`. Der öffentliche Teil der Quelle wurde im Lauf einmal abgerufen: [offizieller NEL-Q2-2026-Bericht (PDF)](https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf), HTTP 200, 510279 Bytes, SHA-256 `60336ebdbcba904234ea9c40a759eb22baf9892fab571651b78e3c319f89a116`.

## Bestätigter DB-Precheck

Der unabhängige authentifizierte Read-only-Lauf `42512499151` bestätigte nach dem fehlgeschlagenen Importversuch:

- Datenbankidentität: `h29077_mosa2_test`
- genau ein NEL-Asset für `NO0010081235`
- 6 bestehende Fundamental-Observations
- 3 bestehende Fundamental-Current-Zuordnungen
- keine Q2-2026-Fakten
- FY-Bestand unverändert mit Observations für 2024 und 2025; Current-Zuordnungen für `ifrs_operating_profit`, `operating_cashflow` und `profit_before_tax`
- `read_only_confirmed=true`, `db_writes=0`, `db_unchanged=true`, `provider_requests=0`, `market_data_read=false`, Quellen- und Faktenreferenzen bestanden

Die sechs FY-Observations und drei FY-Current-Zuordnungen waren damit die unveränderte Import-Baseline.

## Fachlich geprüfte Q2-2026-Werte

Berichtsperiode: `2026-04-01` bis `2026-06-30` (`fq`, Geschäftsjahr 2026, Quartal 2). Originaleinheit für alle fünf Werte: `NOK_THOUSAND`, Währung NOK.

| Metric-Key | Originalwert | Fundstelle im Bericht |
|---|---:|---|
| `revenue` | 153407 | PDF S. 12, „Consolidated statement of comprehensive income“, „Revenue from contracts with customers“, Spalte Q2 2026 |
| `ebitda` | -155337 | PDF S. 17, Note 3 „Segment information“, „Total EBITDA“, Spalte Q2 2026 |
| `ifrs_operating_profit` | -205220 | PDF S. 12, „Operating loss“, Spalte Q2 2026 |
| `profit_after_tax` | -188571 | PDF S. 12, „Net income (loss) for period“, Spalte Q2 2026 |
| `operating_cashflow` | 1673 | PDF S. 13, „Net cash flow from operating activities“, Spalte Q2 2026 |

Der Iwatani-Effekt wurde ausschließlich als Herkunftshinweis vorgesehen. Es wurde kein bereinigtes EBITDA gebildet.

## Actions-Nachweis

1. Lauf `42512074642`, Commit `de0e56d00c301d2f95ed195215c1ec9a312052c1`, mit `reports=nel-q2-2026` und konsistenter Execution-/Authorization-Kennung: Commit- und Offline-Prüfungen bestanden; genau ein PDF-GET mit HTTP 200 wurde ausgeführt.
2. Der Lauf stoppte in `stage=ADAPTER` mit `STOP_NO_RETRY`, `provider_requests=1`, `observations=0`, `current=0`, `full_responses_archived=0`. Die fünf Fakten wurden nicht erzeugt; der Writer und die Importtransaktion wurden nicht erreicht. Es gab keinen automatischen Wiederholungsversuch.
3. Der anschließende unabhängige Read-only-Run `42512499151` bestätigte den unveränderten Bestand mit 6 Observations / 3 Current, `db_writes=0` und `db_unchanged=true`.

Der Nachweis belegt damit: ein einzelner PDF-GET, keine Evidence-Archivierung, keine Importtransaktion, kein Commit der fünf Fakten und keine Änderung an Markt- oder Fremdassetdaten. Der unabhängige Postcheck ist als Read-only-Bestandstest bestanden, nicht als erfolgreicher Import-Postcheck: Die erwarteten fünf Q2-Fakten existieren weiterhin nicht.

## Codekorrekturen

- `9cf3a90ff4461d8b85bd8b0b0ceb9408d0fcb174`: kontrollierter NEL-Q2-Adapter, Evidence-Validator, generischer Writer-Anschluss und gezielte Tests.
- `b9ce07e26eca5035a8d3b0d78a3f9ca050247e4d`: NEL-Execution in der bestehenden privaten Reservierungs-Allowlist.
- `d0bcf375a027302ef2214a285f063916b3d9c1d8`: NEL-Execution zusätzlich als `derived_evidence` registriert.

Alle drei Commits sind nach `main` gepusht. Es wurden keine Webseiten, keine Tabellen und keine Datenbankwerte geändert; es gab kein Testsite-Deployment.

## Offener Blocker

Der PDF-Abruf war erfolgreich, aber der bestehende NEL-Adapter stoppte anschließend in der gekürzten öffentlichen Phase `ADAPTER`. Der Actions-Nachweis enthält keine feinere interne Parser-/Validierungsursache; deshalb wird keine nicht belegte Unterursache behauptet. Der einmalige autorisierte Versuch ist verbraucht. Ein weiterer Importlauf oder eine Änderung am Reservierungsmarker ist nicht erfolgt und nicht Bestandteil dieses Abschlusses.

## Zwischenziel 7A – korrigierte Execution-Kennung

Die konkrete Blockade lag in einer abweichenden Reservierungskennung: `scripts/fundamentals/reports.py` registriert `fundamentals-nel-q2-2026-20261108-01`, während `scripts/fundamentals/archive_remote.py` zuvor den verkürzten Wert `fundamentals-nel-q2-20261108-01` in `EXECUTIONS` und `EVIDENCE_EXECUTIONS` enthielt. Beide Allowlist-Einträge verwenden jetzt exakt die registrierte Kennung.

Der gezielte Regressionstest `test_registered_nel_execution_matches_both_reservation_lists` vergleicht die tatsächliche Registry-Kennung mit beiden Reservierungslisten und bestätigt zusätzlich, dass die Kennungsprüfung vor `create_file(...consumed)` erfolgt. Der NEL-Test läuft ohne fest codierten Windows-PHP-Pfad; der Linux-Workflow `fundamentals-reports.yml` führt ihn gezielt mit dem dort eingerichteten `php` aus. Die NEL-Tests und die fokussierten Offline-Reservierungstests bestanden lokal.

Der exakte Remote-Reservierungsmarker `fundamentals-nel-q2-2026-20261108-01.consumed` wurde am 08.11.2026 im bestehenden privaten Collectorpfad `/private/mosa2-collector/locks` über den autorisierten Dogado/Plesk-Readback nicht gefunden. Es wurden ausschließlich die vorhandenen Einträge dieses Locks-Verzeichnisses gelesen; der Marker ist damit aktuell nicht vorhanden. Es wurde kein Marker verändert, kein Import gestartet und keine Datenbank- oder Provideroperation ausgeführt.


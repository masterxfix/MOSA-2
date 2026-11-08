# NEL ASA – Q2 2026 Importergebnis

Stand: 2026-11-08  
Repository: `masterxfix/MOSA-2`  
Datenbankziel: `h29077_mosa2_test`  
Asset: NEL ASA, ISIN `NO0010081235`

## Ergebnis

Der einmalige Import wurde **nicht ausgeführt**. Beide autorisierten Läufe stoppten vor dem PDF-Abruf und vor jeder Datenbank-Schreiboperation in der bestehenden privaten Evidence-Reservierung. Es gibt deshalb keinen bestätigten Import und keinen unabhängigen Post-Import-Readback.

Der öffentliche Teil der Quelle wurde zuvor einmal fachlich geprüft: [offizieller NEL-Q2-2026-Bericht (PDF)](https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf). Ein Source-SHA-256 aus dem autorisierten Importlauf existiert nicht, weil dieser Lauf die Quelle nicht abgerufen hat.

## Bestätigter DB-Precheck

Der authentifizierte Read-only-Lauf `42487931725` bestätigte vor dem Import:

- Datenbankidentität: `h29077_mosa2_test`
- genau ein NEL-Asset für `NO0010081235`
- 6 bestehende Fundamental-Observations
- 3 bestehende Fundamental-Current-Zuordnungen
- keine Q2-2026-Fakten
- READ ONLY bestätigt, 0 DB-Schreiboperationen, 0 Provider-/KI-Aufrufe

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

1. Lauf `42491260261`, Commit `9cf3a90ff4461d8b85bd8b0b0ceb9408d0fcb174`: Offline- und Commit-Prüfungen bestanden; Abbruch bei `PRIVATE_RESERVATION`, `STOP_NO_RETRY`, `provider_requests=0`, `observations=0`, `current=0`.
2. Nach Korrektur der fehlenden Execution-Allowlist wurde Lauf `42491547644`, Commit `b9ce07e26eca5035a8d3b0d78a3f9ca050247e4d`, gestartet. Auch dieser Lauf stoppte in `PRIVATE_RESERVATION` mit `STOP_NO_RETRY`, `provider_requests=0`, `observations=0`, `current=0`.

Der öffentliche Nachweis belegt damit: kein PDF-GET, keine Evidence-Archivierung, keine Transaktion, kein Commit der fünf Fakten und keine Änderung an Markt- oder Fremdassetdaten durch diese Läufe. Ein Postcheck nach erfolgreichem DB-Commit war mangels Commit nicht möglich und wird nicht als bestanden ausgegeben.

## Codekorrekturen

- `9cf3a90ff4461d8b85bd8b0b0ceb9408d0fcb174`: kontrollierter NEL-Q2-Adapter, Evidence-Validator, generischer Writer-Anschluss und gezielte Tests.
- `b9ce07e26eca5035a8d3b0d78a3f9ca050247e4d`: NEL-Execution in der bestehenden privaten Reservierungs-Allowlist.
- `d0bcf375a027302ef2214a285f063916b3d9c1d8`: NEL-Execution zusätzlich als `derived_evidence` registriert.

Alle drei Commits sind nach `main` gepusht. Es wurden keine Webseiten, keine Tabellen und keine Datenbankwerte geändert; es gab kein Testsite-Deployment.

## Offener Blocker

Die bestehende Remote-Reservierung liefert nach dem Allowlist-Fix weiterhin nur den absichtlich gekürzten Fehlerzustand `PRIVATE_RESERVATION`. Die interne Ursache wird durch den bestehenden sicheren Remote-Reader nicht in die Actions-Logs ausgegeben. Ein Umgehen oder Löschen eines möglichen One-shot-Locks sowie ein weiterer Importlauf wären ohne erneute gezielte Freigabe nicht vertretbar.

## Zwischenziel 7A – korrigierte Execution-Kennung

Die konkrete Blockade lag in einer abweichenden Reservierungskennung: `scripts/fundamentals/reports.py` registriert `fundamentals-nel-q2-2026-20261108-01`, während `scripts/fundamentals/archive_remote.py` zuvor den verkürzten Wert `fundamentals-nel-q2-20261108-01` in `EXECUTIONS` und `EVIDENCE_EXECUTIONS` enthielt. Beide Allowlist-Einträge verwenden jetzt exakt die registrierte Kennung.

Der gezielte Regressionstest `test_registered_nel_execution_matches_both_reservation_lists` vergleicht die tatsächliche Registry-Kennung mit beiden Reservierungslisten und bestätigt zusätzlich, dass die Kennungsprüfung vor `create_file(...consumed)` erfolgt. Der NEL-Test läuft ohne fest codierten Windows-PHP-Pfad; der Linux-Workflow `fundamentals-reports.yml` führt ihn gezielt mit dem dort eingerichteten `php` aus. Die NEL-Tests und die fokussierten Offline-Reservierungstests bestanden lokal.

Der exakte Remote-Reservierungsmarker `fundamentals-nel-q2-2026-20261108-01.consumed` wurde am 08.11.2026 im bestehenden privaten Collectorpfad `/private/mosa2-collector/locks` über den autorisierten Dogado/Plesk-Readback nicht gefunden. Es wurden ausschließlich die vorhandenen Einträge dieses Locks-Verzeichnisses gelesen; der Marker ist damit aktuell nicht vorhanden. Es wurde kein Marker verändert, kein Import gestartet und keine Datenbank- oder Provideroperation ausgeführt.


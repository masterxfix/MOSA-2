# NEL ASA – Ergebnis des dauerhaften Read-only-Zugangs

Stand: 2026-11-08  
Repository: `masterxfix/MOSA-2`  
Ziel-Datenbank: `h29077_mosa2_test`  
Asset: NEL ASA, ISIN `NO0010081235`

## Ergebnis

Der authentifizierte Read-only-Zugang über den bestehenden GitHub-Actions-/SSH-
Dogado-Leseweg funktioniert. Der Reader hat genau ein aktives Equity-Asset für
die übergebene ISIN gefunden. Die Datenbankidentität wurde als
`h29077_mosa2_test` mit dem Account `h29077_mosa2_test@localhost` bestätigt.

Nachweis im erweiterten Lauf `42487931725` auf Commit
`c3ac85fd5788c04e32b1253010e0548fb0540b3e`:

- explizite READ-ONLY-Transaktion bestätigt;
- 1 NEL-Asset, 6 Fundamental-Observations und 3 Fundamental-Current-Zuordnungen;
- 0 Datenbank-Schreiboperationen, `db_unchanged=true`;
- 0 Providerabfragen und 0 Modell-/KI-Aufrufe;
- `market_data_read=false`;
- keine Secrets oder privaten DB-Konfigurationswerte im Log.

Der vorherige aggregierte Nachweis-Lauf `42487746978` auf Commit `47fab8a`
bestätigte dieselben Schutz- und Bestandsbedingungen.

## Tatsächlicher NEL-Bestand in MOSA 2

Alle sechs Observations stammen aus `source_id=214`, `fetch_id=9`, dem Katalog-
Eintrag `nel_official_esef` (`NEL official ESEF reports`, Typ
`issuer_annual_report`). Die Quelle ist im Katalog derzeit `enabled=0`, die
gespeicherten Herkunftsbindungen sind jedoch vollständig vorhanden. Alle Zeilen
haben `unit_key=NOK`, `unit_version=1`, `monetary_currency_code=NOK`,
`parse_status=parsed`, `http_status=200`, Parser `esef_ifrs_inline_v1` Version 1
und den Evidence-Backend-Typ `dogado_private_evidence_json_v1`.

| Observation | Metric-Key | Berichtszeitraum | Originalwert | Current |
|---:|---|---|---:|---|
| 67 | `ifrs_operating_profit` | FY 2024, 2024-01-01–2024-12-31 | -389.428.000 NOK | nein |
| 64 | `ifrs_operating_profit` | FY 2025, 2025-01-01–2025-12-31 | -1.364.667.000 NOK | ja |
| 69 | `operating_cashflow` | FY 2024, 2024-01-01–2024-12-31 | -241.581.000 NOK | nein |
| 66 | `operating_cashflow` | FY 2025, 2025-01-01–2025-12-31 | -252.795.000 NOK | ja |
| 68 | `profit_before_tax` | FY 2024, 2024-01-01–2024-12-31 | -264.185.000 NOK | nein |
| 65 | `profit_before_tax` | FY 2025, 2025-01-01–2025-12-31 | -1.296.152.000 NOK | ja |

Die drei Current-Zeilen lauten konkret:

- `ifrs_operating_profit:fy` → Observation 64;
- `operating_cashflow:fy` → Observation 66;
- `profit_before_tax:fy` → Observation 65.

Alle sechs Zeilen hatten dieselbe Evidence-Prüfsumme
`A2F6FC42D628835883F2657634AAE6FB621AC61A993D79CAC8A95EAFC573F562`.
Die Field-Paths und die Prüfsumme wurden im Actions-Log vollständig ausgegeben
und sind damit für jede Zeile nachvollziehbar. Der Reader hat innerhalb des
gezielt ausgelesenen NEL-Bestands keine Dublette mit gleichem Metric-Key und
gleichem FY-Jahr sowie keinen widersprüchlichen Wert gefunden.

## Abgleich mit dem vorbereiteten NEL-Q2-2026-Paket

Der Readback enthält ausschließlich FY-2024/FY-2025-ESEF-Fakten. Er enthält
keine Q2-2026-Observation und keine Snapshot-, Auftrags- oder Aktienzahl.
Damit dürfen Jahreswerte nicht stillschweigend als Q2-Werte verwendet werden.

| Vorbereiteter Kandidat | MOSA-2-Readback | Bewertung |
|---|---|---|
| `revenue`, Q2 2026, 153.407 NOK tausend | fehlt | Q2-Kandidat bleibt offen/importfähig nach Herkunftsprüfung |
| `ebitda`, Q2 2026, -155.337 NOK tausend | fehlt | importfähig nach Source-Bindung; Iwatani-Effekt separat qualifizieren |
| `ifrs_operating_profit`, Q2 2026, -205.220 NOK tausend | nur FY 2024/2025 vorhanden | nicht identisch; Q2 separat speichern, nicht als FY ersetzen |
| `profit_after_tax`, Q2 2026, -188.571 NOK tausend | fehlt | fachlich eindeutig, aber noch nicht gespeichert |
| `operating_cashflow`, Q2 2026, 1.673 NOK tausend | nur FY 2024/2025 vorhanden | nicht identisch; Q2 separat speichern |
| Cashbestand, 30.06.2026 | fehlt | Stichtags-/Snapshot-Vertrag und Katalog noch offen |
| Auftragseingang, Auftragsbestand, Risikobetrag | fehlt | Periodenart/Stichtag und Metric-Keys getrennt prüfen |
| Eigenkapital, 30.06.2026 | fehlt | Folgepaket wegen Snapshot-Vertrag |
| Aktienzahl | fehlt | separater datierter Kapitalmaßnahmen-Snapshot |

Der vorhandene Jahresbestand ist für historische FY-Vergleiche nutzbar. Er ist
kein Beleg dafür, dass die Q2-Kandidaten bereits importiert wurden. Die
Definition `ifrs_operating_profit` wird nicht in `ebit` umbenannt; ebenso wird
aus `operating_cashflow` kein Free Cashflow abgeleitet.

## Wiederverwendbare Bedienung

Der bestehende Workflow `.github/workflows/fundamentals-analysis.yml` wird auf
`main` manuell mit folgenden Eingaben gestartet:

1. `scope=standard`;
2. `expected_commit=<vollständiger main-Commit>`;
3. `authorization=MOSA2-ANALYSIS:<derselbe vollständige Commit>`;
4. `isin=<uppercase ISIN>`, zum Beispiel `NO0010081235`.

Der neue ISIN-Modus validiert das Format, sucht genau ein aktives Equity-Asset,
liest nur dessen Fundamental-Observations, Current-Zuordnungen und die dafür
benötigten Sources und liest im Target-Modus keine Markt-Current-Tabelle. Der
Reader setzt vor jeder Transaktion `SET SESSION TRANSACTION READ ONLY`, prüft
die Session-Eigenschaft, verwendet gebundene und begrenzte SELECTs, vergleicht
die Fundamental-Fingerprints vor/nach dem Readback und schließt Verbindung und
SSH-Tunnel nach dem Lauf. Provider-, KI- und Schreibpfade sind nicht Teil dieses
Lesewegs.

## Migrationseinschätzung

Aus dem aktuellen NEL-Readback ist kein Import der sechs Jahreszeilen nötig; sie
sind bereits vorhanden und dürfen nicht dupliziert werden. Für das erste kleine
Importpaket bleiben die fünf eindeutig belegten Q2-2026-Finanzkennzahlen aus
`NEL_MIGRATION_PREPARE_2026-11-08.md` priorisiert: Umsatz, EBITDA, IFRS-
Operating-Profit, Net Income und operativer Cashflow. Vor einem Schreiblauf
müssen je Zeile die Q2-Periode, der passende NOK-/NOK-tausend-Unit-Key, der
offizielle Source-/Fetch-/File-/Field-Path und die Duplikatprüfung im selben
Fundamentalmodell bestätigt werden. Cash, Auftragsbestand, Risikobetrag,
Eigenkapital und Aktienzahl bleiben Folgepakete, bis ihr Snapshot- bzw.
Stichtagsvertrag geklärt ist.

Es wurden keine Datenbankänderungen, Migrationen, Collector-/Scheduler-Starts
oder Testsite-Deployments durchgeführt.

## Offene Punkte

- Der Read-only-Weg ist nachgewiesen; ein Schreiblauf oder eine Migration ist
  ausdrücklich noch nicht freigegeben.
- Die sechs vorhandenen Jahreszeilen haben eine deaktivierte Katalogquelle
  (`enabled=0`); die Herkunft ist vorhanden, die fachliche Freigabe einer
  späteren Wiederverwendung bleibt eine separate Entscheidung.
- Für die Q2-2026-Kandidaten fehlen weiterhin MOSA-2-Observations; ihre
  Originalquellen und die vorbereitete fachliche Bewertung liegen im
  vorhandenen NEL-Vorbereitungsbericht.

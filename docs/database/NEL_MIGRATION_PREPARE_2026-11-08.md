# NEL ASA – Datenbankabgleich und Importvorbereitung

Stand der Prüfung: 2026-11-08  
Unternehmen: NEL ASA  
ISIN: `NO0010081235`  
Ziel-DB: `h29077_mosa2_test`  
MOSA-2-Ausgangsrevision: `a84c67b6ca4946d5a064361da0f021e9efdc371b`

## 1. Ergebnisstatus

Ein authentifizierter aktueller Datenbank-Readback war in diesem Auftrag
nicht möglich. Der bestehende Nachweis aus dem Read-only-Inventar ist ein
HTTP-`401` des Fundamental-Endpunkts; dieser wurde nicht wiederholt und nicht
als leerer Datenbestand interpretiert.

Die übrigen Prüfungen sind abgeschlossen: Die Q2-/Halbjahreswerte wurden
gegen den offiziellen NEL-Bericht und die Aktienzahl gegen die offizielle
Euronext-Mitteilung geprüft. Es wurden keine Datenbank-Schreibzugriffe,
Providerabrufe, Collector- oder Scheduler-Läufe ausgeführt.

## 2. Zugangsprüfung und konkreter Blocker

### Bereits vorhandene Wege

Geprüft wurden nur die dokumentierten bzw. im Repository sichtbaren Wege:

- lokale MOSA-Konfiguration `C:\GitHub\dashboard_neu_config\database.php`;
- lokale MOSA-2-Konfiguration
  `mosa2-market-read-private/access.php`;
- `FIXLAB_DB_*`- und `MOSA_TEST_*`-Umgebungsvariablen, nur auf Präsenz;
- lokaler Loopback-Listener auf `127.0.0.1:3307` und laufende SSH-Prozesse;
- der vorhandene MOSA-2-Reader `api/fundamentals_read.php`;
- der vorhandene Dogado-Leser `scripts/fundamentals/analysis_read.php`.

Ergebnis: lokale Konfigurationen, erforderliche Secret-Umgebungsvariablen,
Loopback-Listener und SSH-Prozess waren nicht vorhanden. `analysis_read.php`
ist zwar als read-only Reader mit `SET SESSION TRANSACTION READ ONLY`
implementiert, wird aber nur über einen bestehenden einmaligen Dogado-Workflow
aufgerufen, der zusätzlich einen externen Responses-Aufruf ausführt und eine
separate Einmal-Autorisierung verlangt. Dieser Workflow wurde wegen des
Auftragsverbots für zusätzliche externe Aufrufe nicht gestartet.

Der separate `fundamentals-pilot-once`-Workflow ist ebenfalls nicht zulässig:
er führt einen Provider-GET aus und schreibt qualifizierte Fakten/Current.
Der reine Ziel-Readback konnte daher nicht sicher hergestellt werden.

### Nicht nachgewiesene Ziel-Daten

Für `h29077_mosa2_test` bleiben daher offen:

- NEL-Asset-/ISIN-Zeile,
- Anzahl und Inhalt der `m2_fundamental_observations`,
- Anzahl und Inhalt der `m2_fundamental_current`,
- Sources, Fetches, Files, Units und Metric-Katalogzeilen,
- Dubletten und fachliche Widersprüche.

HTTP 401 ist kein Nachweis für null Datensätze. Erwartete Inserts und Current-
Änderungen werden deshalb im Dry-Run nur als konditionale Fälle angegeben.

## 3. Gegenprüfung der Originalquellen

### Quellen

- Offizielle NEL-Meldung: [Second quarter 2026 financial results](https://nelhydrogen.com/press-release/nel-asa-second-quarter-2026-financial-results/)
- Verknüpfter Originalbericht: [Nel ASA Q2 and half-year 2026 report (PDF)](https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf), veröffentlicht am 15.07.2026.
- Aktienzahl: [Euronext-Mitteilung zur registrierten Kapitalerhöhung vom 25.03.2025](https://live.euronext.com/en/products/equities/company-news/2025-03-25-nel-asa-share-capital-increase-registered).

Der Bericht unterscheidet Q2-Flüsse, Halbjahreswerte und 30.06.-Snapshots.
Die folgenden Originalwerte sind deshalb nicht miteinander vermischt:

| Kennzahl | Originalwert | Einheit / Periodenvertrag | Geeigneter Key | Status |
|---|---:|---|---|---|
| Umsatz aus Kundenverträgen | 153.407 | NOK tausend, Q2 2026 (`2026-04-01`–`2026-06-30`) | `revenue` | importfähig nach Ziel-Readback |
| EBITDA | -155.337 | NOK tausend, Q2 2026 | `ebitda` | importfähig; Iwatani-Effekt als Evidence-Qualifier |
| Iwatani-Effekt | -70 Mio. | NOK million, Q2 2026 | kein separater Import im ersten Paket | nicht als bereinigtes EBITDA abziehen |
| Operating loss | -205.220 | NOK tausend, Q2 2026 | `ifrs_operating_profit` | kein stillschweigendes `ebit` |
| Net income (loss) | -188.571 | NOK tausend, Q2 2026 | `profit_after_tax` | importfähig |
| Net cash flow from operating activities | 1.673 | NOK tausend, Q2 2026 | `operating_cashflow` | importfähig; nicht Cashbestand |
| Cash and cash equivalents | 1.328.048 | NOK tausend, Stichtag 30.06.2026 | `cash_balance`* | Snapshot-Import im ersten Paket blockiert |
| Auftragseingang | 230 | NOK million, Q2 2026 | `order_intake`* | Key-/Katalogprüfung erforderlich |
| Auftragsbestand | 1.213 | NOK million, Stichtag 30.06.2026 | `order_backlog`* | Snapshot-Import blockiert |
| Davon erhebliches Verzögerungs-/Stornorisiko | 296 | NOK million, Stichtag 30.06.2026, PEM | `order_backlog_risk_amount`* | getrennt vom Gesamtbestand |
| Eigenkapital | 3.601.586 | NOK tausend, Stichtag 30.06.2026 | `total_equity`* | Folgepaket wegen Snapshot-Vertrag |
| Aktienzahl | 1.838.457.834 | Stück, registriert/wirksam 25.03.2025 | `shares_outstanding`* | Folgepaket; nicht als aktuell ausgeben |

`*` kennzeichnet einen Key, der im vorhandenen generischen Modell als
fachlicher Katalogeintrag qualifiziert werden muss; dadurch entsteht keine
neue Tabelle oder NEL-Sonderarchitektur.

### Zusätzliche verifizierte Angaben

- Der Bericht definiert EBITDA als Ergebnis vor Zinsen, Steuern,
  Abschreibungen und Wertminderungen; das Q2-EBITDA enthält die NOK-70-Mio.-
  Belastung aus dem Iwatani-Vergleich. Daher wird `ebitda` verwendet, nicht
  `ebitda_normalised`.
- Das ausgewiesene Operating loss ist kein ausdrücklich als EBIT bezeichneter
  Wert. Die IFRS-Betriebsverlustdefinition bleibt daher getrennt von einem
  allgemeinen `ebit`-Key.
- Die beiden Segmente sind Nel Alkaline Electrolyser und Nel PEM Electrolyser.
  Q2-Umsatz: 55.998 bzw. 97.409 NOK tausend; Q2-EBITDA: -27.989 bzw.
  -34.810 NOK tausend. Der Corporate-Anteil des EBITDA beträgt -92.538 NOK
  tausend. Diese Segmentwerte sind verifiziert, aber nicht Bestandteil des
  kleinen Erstpakets.
- Die Q2-Ausgabe nennt eine initiierte 1-GW-Produktionslinie in Herøya. Das
  ist eine qualitative Kapazitätsangabe und wird nicht als Finanzkennzahl
  importiert.
- Der Q2-Bericht nennt gewichtete durchschnittliche ausstehende Aktien von
  rund 1.838 Mio. im Q2. Das ersetzt nicht die exakte, datierte
  Kapitalregisterzahl von 1.838.457.834 und wird nicht als neuer Aktien-
  Snapshot ausgegeben.

## 4. Fachlicher Vergleich mit MOSA und MOSA 2

Das vorherige MOSA-Inventar weist zwei strukturierte Referenzwerte aus:

- Aktienzahl `1.838.457.834`, wirksam 25.03.2025;
- Eigenkapital `NOK 3.601.586.000`, zum 30.06.2026.

Der Q2-Kandidat enthielt sieben gerundete Faktpunkte. Die offizielle Quelle
bestätigt diese Kandidatenwerte; für Umsatz, EBITDA, Cash und Eigenkapital
liegen im Bericht zusätzlich exakte NOK-tausend-Werte vor. Die Kandidatendatei
ist dennoch keine MOSA-2-Observation, weil ihr Fetch-/File-/Field-Path-
Nachweis und die normierte Zielbindung fehlen.

| Kennzahl | MOSA-Quelle | MOSA 2 | Einstufung |
|---|---|---|---|
| `revenue` Q2 2026 | vorhanden, 153.407 NOK tausend | nicht ausgelesen | Zielstatus offen; kein Dublettenentscheid |
| `ebitda` Q2 2026 | vorhanden, -155.337 NOK tausend | nicht ausgelesen | fachlich eindeutig, Iwatani qualifier erhalten |
| `ifrs_operating_profit` Q2 2026 | vorhanden, -205.220 NOK tausend | nicht ausgelesen | nicht als EBIT umbenennen |
| `profit_after_tax` Q2 2026 | vorhanden, -188.571 NOK tausend | nicht ausgelesen | fachlich eindeutig |
| `operating_cashflow` Q2 2026 | vorhanden, 1.673 NOK tausend | nicht ausgelesen | fachlich eindeutig; kein FCF ableiten |
| `cash_balance` 30.06.2026 | vorhanden, 1.328.048 NOK tausend | nicht ausgelesen | Snapshot-Vertrag/Katalog offen |
| `order_intake` Q2 2026 | vorhanden, 230 NOK million | nicht ausgelesen | Katalog-/Einheitenprüfung offen |
| `order_backlog` 30.06.2026 | vorhanden, 1.213 NOK million | nicht ausgelesen | Snapshot, nicht Auftragseingang |
| `order_backlog_risk_amount` 30.06.2026 | vorhanden, 296 NOK million | nicht ausgelesen | separat, PEM-bezogen |
| `total_equity` 30.06.2026 | vorhanden, 3.601.586 NOK tausend | nicht ausgelesen | Folgepaket; Snapshot-Vertrag offen |
| `shares_outstanding` 25.03.2025 | vorhanden, 1.838.457.834 Stück | nicht ausgelesen | datierter historischer Snapshot, nicht aktuell |

Keine MOSA-2-Klassifikation „bereits vorhanden“, „Duplikat“ oder
„widersprüchlich“ wird ohne den tatsächlichen DB-Readback vergeben.

## 5. Erstes kleines Importpaket

### Empfohlener Inhalt

Das erste Paket umfasst fünf Q2-Finanz-Observations, die mit den vorhandenen
Metric-Key-Verträgen und dem bestehenden FY/FQ-Writer fachlich kompatibel
sind:

1. `revenue = 153407`, `NOK_THOUSAND`, Q2 2026;
2. `ebitda = -155337`, `NOK_THOUSAND`, Q2 2026;
3. `ifrs_operating_profit = -205220`, `NOK_THOUSAND`, Q2 2026;
4. `profit_after_tax = -188571`, `NOK_THOUSAND`, Q2 2026;
5. `operating_cashflow = 1673`, `NOK_THOUSAND`, Q2 2026.

Die Werte sind die exakten Tabellenwerte; die gerundeten Millionenwerte aus
Highlights werden nicht zusätzlich als zweite Observation gespeichert.
Der Iwatani-Effekt bleibt als Evidence-/Feldhinweis am EBITDA erhalten und
wird nicht zur Erfindung eines bereinigten Wertes verwendet.

### Bewusst verschobene Werte

Cashbestand, Eigenkapital, Auftragseingang, Auftragsbestand, Risikobetrag und
Aktienzahl werden in ein Folgepaket verschoben, bis der Ziel-Readback und die
Katalog-/Periodenverträge bestätigt sind. Besonders Cash, Eigenkapital und
Auftragsbestand sind Stichtagswerte; der vorhandene Offline-Writer akzeptiert
im aktuellen Vertragsstand nur `fy` und `fq`-Observations, obwohl das SQL-
Modell `snapshot` kennt.

Free Cashflow wird nicht importiert: Der Bericht weist ihn nicht als
Originalkennzahl aus und ein eigener Wert wäre eine Ableitung.

## 6. Deterministischer Dry-Run ohne DB-Schreibzugriff

Plan-ID: `nel-q2-2026-fundamentals-v1`  
Asset: ISIN `NO0010081235`, `asset_class=equity`  
Quelle: offizieller NEL-Q2-/Halbjahresbericht, Veröffentlichung 2026-07-15  
Berichtszeitraum: `2026-04-01` bis `2026-06-30`  
Währung/Einheit: `NOK` / `NOK_THOUSAND`  
Beabsichtigter Modus: read-only validation and plan output, no apply.

Deterministische Schritte:

1. Asset über aktive globale ISIN auflösen; bei null oder mehr als einer
   aktiven NEL-Zeile abbrechen.
2. Source, Report-Datei, SHA-256, Beobachtungszeitpunkt, Reportdatum und
   Feldpfade aus dem offiziellen PDF-Nachweis bilden; keine vollständige
   Webseite oder PDF-Kopie als Hot-/Current-Daten speichern.
3. Metric- und Unit-Kataloge für die fünf Keys und `NOK_THOUSAND` prüfen;
   Definition-/Unit-Hash muss exakt zum vorhandenen Katalog passen.
4. Für jede der fünf Fakten nach `(asset, metric_key, period_type=fq,
   period_start, period_end, source, value, unit)` suchen.
5. Plan ausschließlich als Vorschau ausgeben:
   - identische Observation vorhanden: `0` Observation-Inserts;
   - keine identische Observation: `5` Observation-Inserts vorgesehen;
   - konkurrierender Wert/Definition/Einheit: `CONFLICT_STOP`, keine Inserts;
   - Current-Slot identisch gebunden: `0` Current-Änderungen;
   - Current-Slot fehlt: bis zu `5` Current-Inserts vorgesehen;
   - anderer Current-Wert oder andere Provenienz: `CURRENT_CONFLICT_STOP`.
6. Vor dem Apply erneut Asset, Source, File-/Fetch-Bindung, Perioden,
   Einheiten, Dedupe-Key und Current-Observation-Bindung prüfen.

Erwartete Änderungen sind damit nur Vorschauwerte. Es wurden keine Inserts,
Updates, Current-Projektionen oder Transaktionen ausgeführt.

## 7. Vor dem Import noch erforderlich

1. Authentifizierten reinen MOSA-2-Read-only-Zugang zur Ziel-DB herstellen
   oder einen bestehenden DB-Reader ohne Provider-/Modellaufruf bereitstellen.
2. Tatsächliche NEL-Asset-, Observation-, Current-, Source-, Unit-, Fetch- und
   File-Zeilen lesen und Dubletten-/Konfliktentscheidungen treffen.
3. Prüfen, ob `revenue`, `ebitda`, `ifrs_operating_profit`,
   `profit_after_tax`, `operating_cashflow` und `NOK_THOUSAND` bereits exakt
   katalogisiert sind.
4. Für die verschobenen Snapshot-/Auftrags-/Aktienkennzahlen die vorhandenen
   Katalog- und Writerverträge prüfen; keine stille Umwandlung von NOK-Millionen
   in NOK-Tausend und keine Aktualisierung der Aktienzahl ohne Stichtag.
5. Erst danach einen separat freigegebenen, kleinen Apply mit unabhängiger
   Readback-Prüfung ausführen.

## 8. Bestätigt / offen

**Bestätigt:** Originalwerte und Definitionen des Q2-/Halbjahresberichts, die
exakte Eigenkapitalzahl, die datierte Aktienzahl, fünf geeignete bestehende
Fundamental-Key-Kandidaten sowie der Dry-Run ohne DB-Schreibzugriff.

**Offen:** Tatsächlicher MOSA-2-Bestand, ob eine der fünf Kennzahlen bereits
identisch vorhanden ist, konkrete Duplikat-/Current-Konflikte, Source-/Fetch-
/File-IDs und die Zulässigkeit der Snapshot-/Auftrags-/Aktien-Keys im
Zielkatalog.


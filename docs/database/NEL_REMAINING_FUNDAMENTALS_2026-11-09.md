# NEL ASA: verbleibende Fundamentaldaten (Issue #47)

Ziel: `h29077_mosa2_test`, NEL ASA, aktive ISIN `NO0010081235`.
[Read-only-Ausgangsbestand](https://github.com/masterxfix/MOSA-2/actions/runs/42640096305)
auf `64ace11e82aa1b3f923627a158c8fc27d865cc2d`: **11 Observations
(6 FY, 5 FQ) und 8 Current (3 FY, 5 FQ)**. Bestehende Q2-Observations:
100 (Umsatz), 101 (EBITDA), 102 (IFRS-Betriebsergebnis), 103
(Nachsteuerergebnis), 104 (operativer Cashflow). Executions 01–03 bleiben
verbraucht; keine Wiederholung des [ursprünglichen Imports](NEL_Q2_2026_IMPORT_RESULT.md).

## Quellen und Datenvertrag

Der [NEL-Originalbericht](https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf)
weist Bilanzwerte auf Berichtsseite 12, den Quartals-Auftragseingang auf
Seite 4 und den Auftragsbestand samt Risikoanteil auf Seite 20 aus.
Die [Originalmeldung des Emittenten](https://nelhydrogen.com/press-release/nel-asa-share-capital-increase-registered-23/)
und die [Euronext-Mitteilung](https://live.euronext.com/en/products/equities/company-news/2025-03-25-nel-asa-share-capital-increase-registered)
belegen die registrierte Aktienzahl am 25.03.2025.

| Kennzahl | Originalwert | Zeitraum/Stichtag |
|---|---:|---|
| `cash_balance` | 1.328.048 NOK Tausend | 30.06.2026 |
| `total_equity` | 3.601.586 NOK Tausend | 30.06.2026 |
| `order_intake` | 230 NOK Millionen | 01.04.–30.06.2026 |
| `order_backlog` | 1.213 NOK Millionen | 30.06.2026 |
| `order_backlog_risk_amount` | 296 NOK Millionen | 30.06.2026; Teilwert, vollständig PEM |
| `shares_issued` | 1.838.457.834 Stück | 25.03.2025; ausschließlich Historie |

Der Aktienwert bezeichnet das registrierte Kapital in Stück. Die Quelle
belegt keine um eigene Aktien bereinigte Zahl (`shares_outstanding`);
dieser Key bleibt deshalb unbesetzt. Keine Aktualitätsaussage und keine
Current-Zuordnung für diese historische Meldung.

Snapshots verwenden den vorhandenen Schema-6-Typ `snapshot` und
`as_of_at` (Datum ohne bekannte Uhrzeit als UTC-Mitternacht kodiert).
Geschäftsjahr, Quartal und Periodengrenzen bleiben bei Snapshots NULL.
Der Q2-Auftragseingang bleibt ein Fluss in der ausgewiesenen Originaleinheit.
Die beiden geprüften Manifeste binden Wert, Einheit, Zeitraum/Stichtag,
Dokument, Fundstelle und gegebenenfalls Qualifier. Das private JSON-Evidence-
Archiv wird gehasht; der Fetch-Datensatz belegt den Manifestimport und trägt
keinen erfundenen HTTP-Status. Die Importläufe selbst benötigen keine
Provideranfragen und aktivieren keine Quellen.

## Generische Nachprüfung

Der alte Lauf endete nach dem DB-COMMIT in `INDEPENDENT_READBACK`.
Der genaue fehlgeschlagene Untercheck war nicht protokolliert. Entgegen
der Vermutung im Altbericht enthält `original()` das Schema-5-Tabellenset,
also keine Fundamental-Tabellen. Diese Prüfung bleibt für Altbestände und
Marktdaten erhalten. Neu hinzu kommt ein vollständiger, begrenzter
Fundamental-Fingerprint (einschließlich Quellen/Dateien und Fetches):
Nur exakt geprüfte Inserts und die genau belegte Ersetzung eines Current-Slots
werden im Vergleich berücksichtigt. Alle übrigen Zeilen müssen unverändert
bleiben. Der zweite DB-Anschluss muss eine andere Verbindungs-ID und
bestätigten Read-only-Modus besitzen. Fehler nach Commit bleiben ohne Retry.

Der isolierte Regressionstest reproduziert einen Fehler in der
Performanceprüfung nach dem Commit. Mit `publish_current=false` bleibt der
Current-Slot absichtlich leer. Der alte Code prüft ihn trotzdem und scheitert
im Test an `required_index`, weil der leere Current-Lookup keinen
`PRIMARY`-Index meldet. Der Lauf [42644523776](https://github.com/masterxfix/MOSA-2/actions/runs/42644523776)
protokollierte nur `INDEPENDENT_READBACK / UNKNOWN_NO_RETRY`. Welcher
Untercheck dort zuerst fehlschlug, lässt sich daraus nicht ableiten.

Die Korrektur überspringt die Current-Abfrage und ihre Performanceprüfung
gezielt für `publish_current=false`. History-Index und History-Timing
bleiben Pflicht. Reguläre Importe verlangen weiterhin genau eine
Current-Zeile und den `PRIMARY`-Index. Receipt, Herkunft, unabhängige
Verbindung, Dedupe und Bestands-Fingerprints werden unverändert geprüft.
Der isolierte Test deckt auch falsche oder leere Ausführungspläne, fehlendes
History-Timing und einen Abfragefehler nach Commit ab.

## Prüfstand vor dem Merge

- Implementierung: `08ff5b164d4ef0f46c53a5987d5da4d920ab207c`,
  [PR #53](https://github.com/masterxfix/MOSA-2/pull/53).
- 61 fokussierte Tests bestanden auf bytegetreu ausgechecktem Indexstand,
  einschließlich unveränderter SQL-Migrationshashes. PHP- und JS-Syntax
  geprüft. Die Tests sind kein Produktions- oder DB-Schreibnachweis.
- Verbundener Chrome, realer Startweg Testsite → Fundamentaldaten → NEL ASA:
  **11 Observations / 8 Current** sichtbar; Footer meldete 157 ms für
  den Seitenaufbau. Das ist kein End-to-End-Messwert inklusive Daten-API
  und keine Sichtabnahme des neuen Stands.

## Migrationsnachweis und Endabnahme

Der erste [Schreiblauf](https://github.com/masterxfix/MOSA-2/actions/runs/42643426332)
und der getrennte [Readback](https://github.com/masterxfix/MOSA-2/actions/runs/42644352056)
bestätigten 16 Observations und 13 Current-Zuordnungen. Der abschließende
[Read-only-Readback](https://github.com/masterxfix/MOSA-2/actions/runs/42645258426)
bestätigte **17 Observations und 13 Current-Zuordnungen**. Er enthält die
historische `shares_issued`-Observation 110 zum 25.03.2025 ohne Current,
die unveränderten Q2-Observations 100–104 und dieselben Fingerprints für
Fremdassets und Marktdaten. Der historische Schreiblauf wurde einmal
ausgeführt und blieb ohne Retry.

Das [Testsite-Deployment](https://github.com/masterxfix/MOSA-2/actions/runs/42645406183)
lieferte die datierte Darstellung aus. Im verbundenen Chrome wurde die
Fundamentaldatenansicht über die reguläre Navigation einschließlich API
in 386 ms geladen. Der History-only-Fix betrifft den Import und seine
isolierten Tests. Die abschließenden PR-, Merge-, Datenbank- und
Chrome-Nachweise sind in [Issue #47](https://github.com/masterxfix/MOSA-2/issues/47)
festgehalten.

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

Die Testsite zeigt Stichtage ausdrücklich als Datum an und trennt sie von
FY/FQ. Eine Abnahme erfolgt erst nach den unabhängigen Ziel-Readbacks und
der Prüfung im verbundenen Chrome.

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
- Die neuen Schreibläufe, unabhängigen Vor-/Nachvergleiche mit
  Fremdasset-/Marktdaten-Fingerprints und das SFTP-Testsite-Deployment
  stehen aus. Die relevanten Workflows akzeptieren Live-Importe nur auf
  `main`. [Issue #47](https://github.com/masterxfix/MOSA-2/issues/47) bleibt
  bis zu den Abschlussnachweisen offen.

# Wiederverwendbarer Fundamentals-Import / Zeiss-Pilot

Ausgangsstand: `23da4a1670845b0cd9e6bae98ab6609c6d468c93`, Schema 6.
Vorbereitung ist kein Live-Erfolgsnachweis. Der einmalige Actions-Lauf liefert
den tatsächlichen Abschluss samt unabhängigem DB-Readback und Messwerten.

## Gemeinsamer Vertrag

- Qualifizierte Adapter liefern Definitionen, exakte Dezimalstrings, explizite
  Perioden und Feldbelege. Der gemeinsame DB-Core enthält keine Emittentenregeln.
- Katalogdefinitionen werden anhand Schlüssel, Inhalt und Definitionshash
  wiederverwendet. Abweichende Definitionen brechen ab; neue Definitionen werden
  ausschließlich aus dem geprüften Adapterplan innerhalb der Transaktion ergänzt.
- FY/FQ: Geschäftsjahr bezeichnet das Endjahr. Expliziter Startmonat und Quartal
  bestimmen Start/Ende; abweichende Periodengrenzen werden abgewiesen. Kalenderjahr
  ist keine Vorgabe. Unterstützt werden volle Monatsjahre und Dreimonatsquartale;
  Rumpf-/52-/53-Wochenjahre bleiben bis zur Qualifikation unstrukturiert.
- Identische Fakten verwenden bestehende Observations. Eine identische
  Fetch-Wiederverarbeitung verwendet auch vorhandene Fetch-/Dateizeilen. Ein neuer
  tatsächlicher Abruf kann eigene Evidenz behalten, ohne Fakten zu duplizieren.
- Current je Aktie/Kennzahl/FY oder FQ: späteres Periodenende gewinnt. Ältere
  Nachlieferung verdrängt keine neuere Periode. Gleiche Perioden mit anderen
  Fakten (auch historische), Einheiten- oder Quellenwechsel brechen atomar ab.
  Keine automatische Restatement-/Anbieterpriorität oder Konfliktauflösung.
- Verarbeitung mehrerer Aktien erfolgt nacheinander, Transaktion und Readback
  jeweils pro Aktie. Kein automatischer Collector-/Schedulerbetrieb.
- Readback prüft alle betroffenen Zeilen plus exakte Tabellenänderungen.
  Bestehende Stammdaten/Marktdaten werden begrenzt gehasht; explizit geschützte
  Aktien zusätzlich vor und nach dem Import. Kein unbegrenzter History-Download.

## Einziger freigegebener Live-Lauf

Workflow: `.github/workflows/fundamentals-zeiss-once.yml`, manuell auf dem exakt
geprüften Main-Commit. Run-Nummer und Versuch müssen 1 sein. Autorisierung:
`MOSA2-ZEISS-FUNDAMENTALS-ONCE-20261101:<commit>`.

Profil `zeiss`: ISIN DE0005313704, bestehender Stammdatenname
`Carl Zeiss Meditec` (rechtlich Carl Zeiss Meditec AG).
Genau ein GET, keine Weiterleitung und kein Retry:
<https://reports.zeiss.com/meditec-ag/2425/de/konzernlagebericht/wirtschaftsbericht/ertragslage.html>.
Der Suchindex diente ausschließlich zur Vorbereitung der Parserstruktur;
Finanzwerte werden ausschließlich aus der tatsächlich archivierten Antwort gelesen.

Der Adapter qualifiziert 11 Kennzahlen für FY 2024/25 und 2023/24:
Umsatz, EBIT, EBITA, EBITDA, Ergebnis vor Steuern, den Anteilseignern zurechenbares
Ergebnis, unverwässertes EPS, Brutto-/EBIT-/EBITA-Marge und Steuerquote. EBIT und
EBITDA sowie EUR_MILLION behalten die bestehenden PNE-Definitionen. EPS wird
zusätzlich mit der explizit unverwässerten Textstelle abgeglichen. Finanzzahlen
sind keine Codekonstanten; die Tests verwenden ausschließlich erfundene Werte.
Geschäftsjahre: 2024-10-01 bis 2025-09-30 und 2023-10-01 bis 2024-09-30.
Kein erfundener Veröffentlichungszeitpunkt: reported_at/as_of_at bleiben NULL.
Weitere Tabellen, Segmente, Erläuterungen und nicht qualifizierte Angaben bleiben
vollständig im Original erhalten (`parse_status=partial`).

Privates Archiv: bestehender Bereich `private/mosa2-collector/runs/`, einmaliger
Unterordner `fundamentals-zeiss2025-20261101-01`, Verzeichnis 0700, Dateien 0600,
exklusive Erstellung, fsync, SHA-256 und unabhängiges erneutes Einlesen vor DB
und nach Readback. Originalantwort und Metadaten bleiben außerhalb der Webroots.
Bestehender Verbrauchsmarker verhindert erneute Ausführung. Keine Secrets oder
Rohdaten in Logs, Git oder Actions-Artefakten.

PNE muss unverändert 7 Observations / 4 Current behalten; Marktbestand 28 / 5.
Migrationen 0001–0006, Collector-Sperren und Webseiten bleiben unverändert.
Die vorhandene Chrome-Sitzung prüft nur die unveränderte sichtbare Marktdaten-
Seite; es wird keine neue Fundamentals-Oberfläche behauptet oder deployed.

## Nachweis und Grenzen

Fokussierte synthetische Tests: zwei Aktien, Katalog-/Fetch-/Faktenwiederverwendung,
FY und FQ mit verschiedenen Kalendern, neue/alte Perioden, historische Konflikte,
Rollback und unbekanntes Commit-Ergebnis. Anschließend relevante PNE-Regressionen.

Auf Dogado: unabhängige Read-only-Verbindung nach bestätigtem Commit;
Current über vollständigen Primary Key, History über `ix_fund_obs_period`,
LIMIT 20 und EXPLAIN ANALYZE. Clientzeit enthält SSH-Tunnel/Netz; die separate
Serverzeit ist die EXPLAIN-Iteratorzeit. Bei `const` kann der PK-Zugriff vor dem
gemessenen Iterator liegen: dessen 0 ms sind keine vollständige DB-Laufzeit.
Keine erzwungenen Indizes oder Schemaänderungen. Synthetische Tests sind kein
MySQL- oder Produktionslastnachweis.

Unbekanntes Ergebnis oder Fehler: stoppen, keine erneute Action, kein zweiter
Providerabruf und kein automatischer Schreibversuch.

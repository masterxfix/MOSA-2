# MOSA 2 – Kursanbieter: Aufgaben und tatsächliche Auswahlregeln

**Dokumentationsstand:** 12.11.2026. **Aktiver M2-Collector:** `a82439c0`; ein gemeinsamer ISIN-Kursauswahlweg für Aktien und ETFs, live nachgewiesen. Die internationale Originalwährungsabdeckung ist weiterhin keine freigegebene Gesamtfunktion.

> **Wichtig:** „Anbieter erreichbar“ ist nicht dasselbe wie „Kurs gespeichert“. Die internationale Heimatmarktversorgung ist noch nicht vollständig live abgenommen.

## 1. Wer liefert was?

| Kursanbieter | Aufgabe in MOSA 2 | Automatische ISIN-Abfrage | Unter welchen Bedingungen wird er bevorzugt? |
| --- | --- | --- | --- |
| **Lang & Schwarz (TradeCenter)** | ISIN-Suche, Instrumentendetails/Namensinformation, Geld-/Brief-Offerte und Handelswerte | **Aktiv** | Für Aktien und ETFs identisch: qualifizierter Geld-/Briefkurs kann im gemeinsamen Quotenvergleich gewinnen |
| **Tradegate BSX** | ISIN-bezogene Geld-/Brief-Offerte und letzte Umsätze | **Aktiv** | Für Aktien und ETFs identisch: kein typabhängiger Vorrang; Bewertung derselben Kursqualität |
| **Börse Frankfurt** | Letzter Kurs vom gezielt abgefragten Handelsplatz **XFRA** | **Aktiv** | Für Aktien und ETFs identisch: **Last-Trade-Fallback**, wenn keine geeignete vollständige Geld-/Brief-Offerte ausgewählt wird |
| **Yahoo Finance** | Früher für internationale Kurse (z. B. NEL in NOK) genutzt; heute nur historischer Entwicklungsnachweis | **AUSGESCHLOSSEN** (12.11.2026) | **Keine Nutzung in M2:** weder automatische noch manuelle Kursabfrage; keine Auswahl oder Speicherung |
| **Twelve Data** | Früher vorbereiteter internationaler ISIN-Adapter; kostenfreier Umfang und Konditionen ungeeignet/undurchsichtig für M2 | **AUSGESCHLOSSEN** (12.11.2026) | Keine automatische/manuelle M2-Kursabfrage, Registrierung oder Auswahl |
| **EODHD** | Früher vorbereiteter internationaler ISIN-Adapter; kostenloses API-Kontingent unzureichend für M2 | **AUSGESCHLOSSEN** (12.11.2026) | Keine automatische/manuelle M2-Kursabfrage, Registrierung oder Auswahl |

**Klarstellung zur Tabelle:** **Drei Quellen sind tatsächlich aktiv; Yahoo Finance, Twelve Data und EODHD sind ausdrücklich ausgeschlossen.** Historische Adapter/Tests bleiben als Entwicklungsreferenz, keine Betriebsfreigabe. Wiederaufnahme ausschließlich nach neuer ausdrücklicher Nutzerentscheidung, separatem überprüftem Nutzungsrecht und erfolgreicher Live-Abnahme.

**Aktueller Abnahmenachweis (12.11.2026, 20:21 UTC):** Die aktive private Collector-Version `a82439c0` verarbeitet im selben Minutenjob **Aktien und ETFs** mit **derselben Kursauswahl** und dem gemeinsamen M2-Writer. Nach der Umschaltung wurden sowohl **DroneShield (Aktie, Tradegate BSX, EUR)** als auch **iShares Automation & Robotics (ETF, Lang & Schwarz, EUR)** erneut als Current gespeichert. Der ETF erhielt damit nach dem Entfernen des pauschalen Tradegate-Vorrangs einen tatsächlich anders gewählten Anbieter. Unabhängiger Read-only-DB-Readback: **3 ISINs, 19 Währungseinheiten, 0 Yahoo-Quellen, 0 freigeschaltete internationale Quellen**. Der geöffnete M2-Marktdaten-Tab zeigte beide aktualisierten Werte und **233 ms** angezeigte Seitenladezeit; das war eine **DOM-/Textprüfung, kein visueller Screenshot**. **Internationale native Live-Kurse bleiben ungetestet, weil die Anbieterrechte noch fehlen.**

Belege: [Aktiver Collector/Unveränderter übriger Cron](https://github.com/masterxfix/MOSA-2/actions/runs/43298963840) · [Unabhängiger Live-Readback: Aktie + ETF](https://github.com/masterxfix/MOSA-2/actions/runs/43299387626) · [Gemeinsame Kursauswahl: 83/83 Tests](https://github.com/masterxfix/MOSA-2/actions/runs/43297929873).

## 2. Welche Quelle wird WANN tatsächlich ausgewählt?

### Vorbedingung: Eine Quelle muss verfügbar und berechtigt sein

- Ein **einziger** M2-Minutenjob verarbeitet die registrierten ISINs zurzeit in Chargen von bis zu **2 Einträgen**. Die angezeigte M2-Tabelle liest gespeicherte Kurse **alle 30 Sekunden**, ohne einen neuen Börsenabruf auszulösen.
- Maßgeblich sind der **gemeinsame Quellenkatalog**, die M2-Datenbank-Registrierung, die Scheduler-Sperre, der Quellencooldown und bei internationalen Anbietern zusätzlich private Rechte und Tages-/Minutenkontingente.
- Geprüft werden insbesondere passende ISIN, zugelassene Datenquelle, Preis, echter Marktzeitpunkt und eine in M2 **eingefrorene Originalwährungseinheit**. Es erfolgt **keine erfundene Umrechnung in EUR**.

### Internationale Kandidaten: ausdrücklich ausgeschlossen

**Twelve Data und EODHD dürfen nicht im M2-Collector aktiviert werden.**
Der gemeinsame Quellkatalog `api/market_sources.php` enthält weiterhin die historischen
Providerkennungen, liefert sie aber **nie** als aktive Quelle zurück, auch nicht
mit alten Berechtigungs-Flags. Der Quellen-/URL-Guard weist ihre Requests ab.
Die aktivierte private Release-Version war bereits vor dieser Entscheidung ohne
diese Anbieter konfiguriert. Die GitHub-Regel ist für künftige Releases maßgeblich.

**Neue internationale Originalwährungsquellen** werden nach ISIN, bestätigtem
Börsen-MIC, Originalwährung, Marktzeit und erlaubter Nutzung bewertet,
nicht aus den ausgeschlossenen APIs übernommen.

### Die drei aktiven deutschen Quellen – gemeinsame Kursauswahl

**Eine gemeinsame Auswahl für Aktien, ETFs, Fonds und andere registrierte Wertpapiere:**

1. Vollständige **Geld-/Brief-Offerten** werden **pro Währungsgruppe** verglichen: zuerst Frischeklasse (fresh vor aging), dann **niedrigerer relativer Spread**, danach **geringeres Datenalter**, bei Gleichstand stabiler Quellenschlüssel.
2. Gibt es Sieger aus verschiedenen Währungsgruppen, wird derzeit derjenige mit dem **jüngsten Marktzeitpunkt** genommen; nominale Preise verschiedener Währungen werden **nicht** direkt verglichen.
3. Gibt es keine geeignete vollständige Offerte, werden gültige **Last-Trades/Snapshots** aus den erlaubten Quellen geprüft. **Jüngerer Marktzeitpunkt** entscheidet. Die Kandidatenliste ist **keine feste Priorität Tradegate vor Frankfurt oder umgekehrt**.
4. Für den Tradegate-Last-Trade muss zusätzlich die zugehörige Tradegate-Quote dieselbe ISIN nachweisen.

**Wichtig:** Die frühere ETF-Sonderauswahl (Tradegate-Vorrang, feste 0,25-%-Gegenprüfung, Berliner Uhrzeitgrenze 08:00–22:00 Uhr) ist **nicht mehr an den M2-Kurswriter angebunden**. Der ETF-/Aktien-Typ ist nur Klassifikation/Metadatum; der Quote- und Last-Trade-Weg wählt unabhängig davon denselben Anbieter für dieselbe Quelleingabe. Reale Quellenzeiten, Marktzeitstempel und Währungsqualifikation werden weiterhin geprüft. Historische ETF-Shadow-Hilfsfunktionen können noch im übernommenen MOSA-Kern stehen, sind aber nicht Teil der M2-Auswahl.

## 3. Was bedeutet die Anzeige?

| Darstellung in M2 | Tatsächliche Bedeutung |
| --- | --- |
| **Mid (Geld/Brief)** | Rechenwert aus Geld- und Briefkurs. **Kein** tatsächlich gehandelter Kurs |
| **Last Trade** | Letzter vom Anbieter gemeldeter Handelspreis. **Keine** Zusage, jetzt zu diesem Preis handeln zu können |
| **EUR, AUD, JPY usw.** | Gespeicherte Original-Währung/Kurseinheit der qualifizierten Route, **keine automatische FX-Konvertierung** |
| **Marktzeitpunkt** | Zeitstempel des Preises an der Quelle |
| **Erfasst** | Zeitpunkt des M2-Datenabrufs bzw. der Erfassung |
| **Datenalter** | Alter des tatsächlichen Marktzeitpunkts; **kein** Countdown zum nächsten Handel |

Beim normalen EUR-Vergleich akzeptiert die Auswahl in der Regel höchstens **300 Sekunden** alte Kandidaten. Twelve Data verwendet ebenfalls **300 Sekunden**; für EODHD sind **1.800 Sekunden** zulässig. Der Anbieter beschreibt EODHD-Kurse als **verzögert**. Das Alter wird nicht durch erneutes Abrufen künstlich zurückgesetzt. Ein vorhandener älterer gespeicherter Wert muss in der M2-Ansicht als veraltet erkennbar bleiben.

## 4. Aktivierung und Kostenkontrolle

- Die drei tatsächlich **automatisch aktivierten** traditionellen Quellen sind **Lang & Schwarz**, **Tradegate BSX** und **Börse Frankfurt**. Der **einzige** Collector und derselbe Observation-/Current-Writer übernehmen die Speicherung.
- **Twelve Data: AUSGESCHLOSSEN** aufgrund Nutzerentscheidung. Keine M2-Nutzung; eine private Lizenzkonfiguration darf den Ausschluss nicht aufheben.
- **EODHD: AUSGESCHLOSSEN** aufgrund Nutzerentscheidung. Keine M2-Nutzung; eine private Lizenzkonfiguration darf den Ausschluss nicht aufheben.
- **Yahoo Finance: AUSGESCHLOSSEN** (siehe Tabelle). Historische MOSA-Parser/Tests bleiben ausschließlich technische Altnachweise, keine M2-Freigabe.
- Nach Quellenfehlern **401/403/429** gibt es Abkühlphasen; ohne gültigen neuen Marktpreis gibt es **keinen fingierten neuen Current**. Die vorhandenen deutschen Quellen bleiben als Rückfall erhalten.

## 5. Bewusst dokumentierte Schwachstellen / noch keine Gesamtfreigabe

1. **Kein verifizierter internationaler Livefeed:** Die internationalen Adapter sind programmiert und getestet, derzeit jedoch nicht mit berechtigter realer Originalwährungsquelle abgenommen.
2. **Internationale Lücke:** Nach dem Ausschluss der beiden optionalen APIs ist noch keine internationale Originalwährungsquelle produktiv. Die historische internationale Auswahl im Code ist ohne freigegebene Quellen nicht erreichbar.
3. **MIC ist nicht automatisch Heimatbörse:** Eine durch den Anbieter belegte Handelsplatzkennung muss zur tatsächlichen Heimatmarktbehauptung zusätzlich fachlich eingeordnet werden.
4. **Globale Handelszeiten:** Der ETF-spezifische Berliner Ausschluss ist aus der M2-Auswahl entfernt. Handelsunterbrechungen, Feiertage und internationale Sitzungskalender sind trotzdem noch nicht vollständig live abgenommen.
5. **Abnahme offen:** Erforderlich sind echte internationale Quellenantworten aus mehreren Zeitzonen, M2-eigene Observations/Current, korrektes Kursalter, ISIN/MIC/Originalwährung und **visuelle Browserkontrolle** am tatsächlich genutzten M2-Startweg.

Es gibt **keinen separaten Collector pro Land oder einzelner ISIN**. Die historischen internationalen Adapter bleiben nur für Offline-Regressionen erhalten und sind aus der laufzeitfähigen Quellenregistrierung ausgeschlossen. Neue Anbieteradapter brauchen dieselbe zentrale ISIN-neutrale Registrierungs- und Auswahlarchitektur.

## 6. Maßgebliche Implementierungen und Tests

- [Gemeinsamer Quellenkatalog, Freigaben und Auswahl](../api/market_sources.php): **catalog()**, **scheduled()**, **allowed()**, **fact()**, **choose()**.
- [Zentraler privater M2-Collector](../scripts/market_collector/mosa_tick.php): **sourceRegistry()**, **acquire()**, **syncFact()**, **main()**.
- [Gemeinsamer Quotenvergleich](../api/market_source_engine.php): **fixlabMosaMarketQuoteRouter()** und **fixlabMosaMarketSourceLabQuoteCandidate()** für alle Wertpapierklassen; der alte **EtfShadowSelection**-Helper gehört nicht mehr zur M2-Kursauswahl.
- [Twelve-Data-Adapter](../api/market_core/twelve_data.php), [EODHD-Adapter](../api/market_core/eodhd.php).
- [Vertiefung: internationale Quellen und Lizenzvoraussetzungen](database/M2_INTERNATIONAL_MARKET_PROVIDER.md).
- [Tests der gemeinsamen Quellenauswahl](../tests/test_market_tick_sources.php), [Twelve-Data-Tests](../tests/test_twelve_data_provider.php), [EODHD-Tests](../tests/test_eodhd_provider.php), [EODHD-MySQL-Tests](../tests/test_eodhd_mysql.php).

**Pflegeregel:** Bei Änderungen der Quellenaktivierung, Kursqualitäts-/Frischeregeln oder Lizenzfreigaben diese Seite mitaktualisieren. **Diese Markdown-Seite ist nur Dokumentation; die ausführbare zentrale Quellenregistrierung bleibt allein im Code.**

## 7. Weitere offizielle kostenlose Datenquellen – Kandidaten, noch nicht integriert

Die drei derzeitigen aktiven deutschen Abfrageanbieter sind **nicht** die einzigen kostenfreien Quellen.
Offizielle Datenbörsen stellen verzögerte, maschinenlesbare regulatorische Vor-/Nachhandelsdaten bereit. Dies sind **Dateidienste** (typisch bis zu 15 Minuten verzögert), keine zugesagten kostenlosen weltweiten Live-APIs.

| Kandidat | Märkte | Format / Daten | Zulässigkeit und Status |
| --- | --- | --- | --- |
| [Euronext MiFID delayed](https://www.euronext.com/en/data/pricing-specs-agreements/mifid-ii-compliant-data) | **Oslo**, Paris, Amsterdam, Mailand u. a. | CSV; ISIN, Preis, Stück, Währung, Handel-/Veröffentlichungszeit | Kostenlos veröffentlichte Verzögerungsdaten; Bedingungen für private Verwendung/Weitergabe beachten. **Prüfkandidat für NEL-NOK**, nicht live in M2 getestet. |
| [Nasdaq Nordic/Baltic](https://tradereports.nasdaq.com/) | Skandinavien und Baltikum | Minütliche 15-min.-verzögerte CSV-Vor-/Nachhandelsdaten | Offiziell kostenfreier Zugriff; keine Behauptung einer universellen ISIN-Live-API. Nicht integriert. |
| [LSEG Delayed Market Data](https://dmd.lseg.com/) | XLON, Turquoise | Minütliche CSV-Vor-/Nachhandelsdaten mit UTC-Zeiten | 15-min.-verzögert, eigene Nutzung nach Bedingungen, nicht integriert. |
| [gettex / Börse München](https://www.gettex.de/handel/delayed-data/) | MUND/MUNC | 15-min.-verzögerte CSV-Dateien, Vor-/Nachhandel | Laut BBAG für private nichtkommerzielle Verwendung frei, nicht integriert. |
| [Deutsche Börse MiFIR](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/Delayed-data) | Xetra, Frankfurt, Tradegate BSX u. a. | GZ-JSON-Pre-/Posttrade minütlich | Offiziell kostenfrei für nichtkommerzielle Verwendung nach jeweiligen Bedingungen, **separates Datenprodukt vom HTML-Scraping**. Nicht integriert. |
| [OpenFIGI](https://www.openfigi.com/api/documentation) | International | ISIN → FIGI, Börsen-/Ticker-Referenzen | Kostenlose offene Identifikatoren, **keine Kurse**. Nicht integriert. |

**Kritisch:** Die Lizenz einer offiziellen verzögerten Datei ist nicht automatisch die Lizenz einer anderen Website oder Echtzeit-API desselben Anbieters. Vor Integration Datenfelder, Aktualität, MIC, ISIN, Nutzungsrechte, Rate-Limits, Host-Erreichbarkeit, unveränderte Originalwährung und korrekten Source-Current/History-Readback prüfen. Keine Anbieter-Sonderkollektoren, keine unbegrenzten Downloads.

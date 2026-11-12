# MOSA 2 – Kursanbieter: Aufgaben und tatsächliche Auswahlregeln

**Dokumentationsstand:** 12.11.2026; aktualisiert nach Nutzerentscheidung „Yahoo Finance aus M2 entfernen“.  **Geprüfter technischer Ausgangsstand:** main, Commit 2315cff54f3eee6e85a4679e6dbe30cca0375a87. Diese Seite dokumentiert den implementierten **IST-Stand** von MOSA 2, nicht ein noch nicht getestetes Zielbild.

> **Wichtig:** „Anbieter erreichbar“ ist nicht dasselbe wie „Kurs gespeichert“. Die internationale Heimatmarktversorgung ist noch nicht vollständig live abgenommen.

## 1. Wer liefert was?

| Kursanbieter | Aufgabe in MOSA 2 | Automatische ISIN-Abfrage | Unter welchen Bedingungen wird er bevorzugt? |
| --- | --- | --- | --- |
| **Lang & Schwarz (TradeCenter)** | ISIN-Suche, Instrumentendetails/Namensinformation, Geld-/Brief-Offerte und Handelswerte | **Aktiv** | Bei normalen Aktien, wenn seine vollständige Offerte im gemeinsamen EUR-Quotenvergleich gewinnt; bei ETFs vor allem **Ausweichquelle**, falls Tradegate nicht geeignet ist |
| **Tradegate BSX** | ISIN-bezogene Geld-/Brief-Offerte und letzte Umsätze | **Aktiv** | Bei normalen Aktien **kein pauschaler Vorrang**, sondern Bewertung der Quotenqualität; bei ETFs **erste Wahl** innerhalb der speziellen deutschen EUR-ETF-Regel |
| **Börse Frankfurt** | Letzter Kurs vom gezielt abgefragten Handelsplatz **XFRA** | **Aktiv** | Bei Nicht-ETFs als gültiger **Last-Trade-Fallback**, wenn keine geeignete vollständige Geld-/Brief-Offerte ausgewählt wird |
| **Yahoo Finance** | Früher für internationale Kurse (z. B. NEL in NOK) genutzt; heute nur historischer Entwicklungsnachweis | **AUSGESCHLOSSEN** (12.11.2026) | **Keine Nutzung in M2:** weder automatische noch manuelle Kursabfrage; keine Auswahl oder Speicherung |
| **Twelve Data** | Optionaler internationaler Last-Trade anhand der ISIN, mit Originalwährung und Handelsplatz-MIC | **Deaktiviert**, bis private Rechte und Quoten eingerichtet sind | Nach Aktivierung **vor EODHD und deutschen Quellen**, wenn MIC, Währung und Zeitstempel qualifiziert sind; Marktalter höchstens **5 Minuten** |
| **EODHD** | Optionale exakte ISIN-Suche, Zuordnung zu Börsenticker und Handelsplatz-MIC, verzögerter letzter Kurs in Originalwährung | **Deaktiviert**, bis private Rechte und Quoten eingerichtet sind | Nach Aktivierung **nach Twelve Data, aber vor deutschen Quellen**, wenn Zuordnung eindeutig und Marktalter höchstens **30 Minuten** ist |

**Klarstellung zur Tabelle:** Fünf Anbieter sind als aktive oder bedingt freigebbare Kursquellen vorgesehen; **Yahoo Finance steht bewusst weiterhin in der Übersicht, ist aber ausgeschlossen**. Wiederaufnahme nur nach neuer ausdrücklicher Nutzerentscheidung und nachgewiesenen Nutzungsrechten.

**Zuletzt nachgewiesener M2-Testbetrieb (12.11.2026):** Lang & Schwarz, Tradegate BSX und Börse Frankfurt lieferten bei den echten ISIN-Abfragen HTTP 200. Auf der M2-Marktdatenseite wurden für **NEL ASA** und **DroneShield** die gespeicherten **EUR-Geld-/Brief-Mittelkurse von Tradegate BSX** angezeigt. **0** registrierte Twelve-Data-/EODHD-Quellen in der unabhängigen Datenbankprüfung; **keine** nachgewiesenen AUD- oder JPY-Heimatmarktkurse. Dieser Befund ist datiert und **keine Live-Statusabfrage**.

Belege: [Collector mit internationalen Adaptern aktiviert](https://github.com/masterxfix/MOSA-2/actions/runs/43272934165) · [Unabhängiger Cron-/DB-Livenachweis](https://github.com/masterxfix/MOSA-2/actions/runs/43273617957).

## 2. Welche Quelle wird WANN tatsächlich ausgewählt?

### Vorbedingung: Eine Quelle muss verfügbar und berechtigt sein

- Ein **einziger** M2-Minutenjob verarbeitet die registrierten ISINs zurzeit in Chargen von bis zu **2 Einträgen**. Die angezeigte M2-Tabelle liest gespeicherte Kurse **alle 30 Sekunden**, ohne einen neuen Börsenabruf auszulösen.
- Maßgeblich sind der **gemeinsame Quellenkatalog**, die M2-Datenbank-Registrierung, die Scheduler-Sperre, der Quellencooldown und bei internationalen Anbietern zusätzlich private Rechte und Tages-/Minutenkontingente.
- Geprüft werden insbesondere passende ISIN, zugelassene Datenquelle, Preis, echter Marktzeitpunkt und eine in M2 **eingefrorene Originalwährungseinheit**. Es erfolgt **keine erfundene Umrechnung in EUR**.

### Priorität 1: Internationaler Kandidat – falls tatsächlich aktiviert

Der aktuelle Code prüft die beiden internationalen Quellen **in fester Anbieterreihenfolge**:

1. **Twelve Data** gewinnt zuerst, wenn der internationale Kurs eine gültige **vierstellige Börsen-MIC** hat, die ISIN korrekt ist, die Währung qualifiziert ist und der Börsenzeitpunkt höchstens **300 Sekunden** zurückliegt.
2. **EODHD** wird gewählt, wenn der erste Kandidat nicht qualifiziert ist. Benötigt werden eine eindeutig aufgelöste ISIN-/Ticker-/MIC-Kette, qualifizierte Währung und ein Börsenzeitpunkt von höchstens **1.800 Sekunden**.

**Der erste gültige internationale Kandidat gewinnt auch gegenüber einer frischeren deutschen EUR-Offerte.** Twelve Data und EODHD werden untereinander derzeit **nicht nach derselben Qualitätsmetrik verglichen**. Diese Priorität ist eine **anbieterbezogene Regel**, noch keine vollständig neutrale Auswahl. Ein realer MIC beweist den angegebenen Handelsplatz, **aber für sich allein noch nicht die Heimatbörse** des Instruments.

### Priorität 2: Deutsche Quellen, wenn kein internationaler Kandidat qualifiziert ist

**Aktien, Fonds und andere Nicht-ETF-Werte:**

1. Vollständige **Geld-/Brief-Offerten** werden **pro Währungsgruppe** verglichen: zuerst Frischeklasse (fresh vor aging), dann **niedrigerer relativer Spread**, danach **geringeres Datenalter**, bei Gleichstand stabiler Quellenschlüssel.
2. Gibt es Sieger aus verschiedenen Währungsgruppen, wird derzeit derjenige mit dem **jüngsten Marktzeitpunkt** genommen; nominale Preise verschiedener Währungen werden **nicht** direkt verglichen.
3. Gibt es keine geeignete vollständige Offerte, werden gültige **Last-Trades/Snapshots** aus den erlaubten Quellen geprüft. **Jüngerer Marktzeitpunkt** entscheidet. Die Kandidatenliste ist **keine feste Priorität Tradegate vor Frankfurt oder umgekehrt**.
4. Für den Tradegate-Last-Trade muss zusätzlich die zugehörige Tradegate-Quote dieselbe ISIN nachweisen.

**ETFs (eigene generische Assetklassenregel, keine Einzel-ISIN-Ausnahme):**

1. Nach der internationalen Vorprüfung wird die deutsche EUR-ETF-Auswahl geprüft. **Tradegate** ist die erste Wahl; **Lang & Schwarz** ist Ersatz.
2. Sind beide EUR-Quotes geeignet, wird die Kursabweichung geprüft. Bei **mehr als 0,25 %** wird die automatische Freigabe wegen eines Konflikts unterbunden.
3. Freigabe nur im im Code hinterlegten **Berliner Zeitfenster 08:00–22:00 Uhr**; die Funktion bildet dabei **keinen vollständigen Feiertags-/Heimatbörsenkalender** ab.
4. Ohne geeigneten internationalen Kurs und ohne freigegebene EUR-ETF-Quote entsteht **kein erfundener neuer Kurs**.

**Merke:** Dass Tradegate häufig gespeichert wird, heißt **nicht**, dass es bei jeder Aktie als erster Anbieter vorgeschrieben ist. Bei ETFs gibt es dagegen ausdrücklich einen Tradegate-Vorrang innerhalb der EUR-Regel.

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
- **Twelve Data** bleibt ohne privaten API-Zugang, bestätigte Markt- und **ISIN-Datenrechte** sowie echte Limits aus. Die im Code vorhandene Integration ist keine Marktdatenlizenz.
- **EODHD** bleibt ohne bestätigte private Nutzungsrechte und Kontingente aus. Bei Freischaltung wird die ISIN generisch einem eindeutigen Börsenticker/MIC zugeordnet. Positive Zuordnungen werden **14 Tage**, negative/mehrdeutige Zuordnungen **6 Stunden** in bestehenden M2-Checkpoints zwischengespeichert. Anbieteraufrufe belasten die genehmigten Tages-/Minutenbudgets.
- **Yahoo Finance: AUSGESCHLOSSEN** (siehe Tabelle). Historische MOSA-Parser/Tests bleiben ausschließlich technische Altnachweise, keine M2-Freigabe.
- Nach Quellenfehlern **401/403/429** gibt es Abkühlphasen; ohne gültigen neuen Marktpreis gibt es **keinen fingierten neuen Current**. Die vorhandenen deutschen Quellen bleiben als Rückfall erhalten.

## 5. Bewusst dokumentierte Schwachstellen / noch keine Gesamtfreigabe

1. **Kein verifizierter internationaler Livefeed:** Die internationalen Adapter sind programmiert und getestet, derzeit jedoch nicht mit berechtigter realer Originalwährungsquelle abgenommen.
2. **Feste Anbieterpriorität:** Twelve Data wird vor EODHD geprüft, selbst wenn eine neutrale Qualitätsbewertung anders ausfallen könnte.
3. **MIC ist nicht automatisch Heimatbörse:** Eine durch den Anbieter belegte Handelsplatzkennung muss zur tatsächlichen Heimatmarktbehauptung zusätzlich fachlich eingeordnet werden.
4. **Globale Handelszeiten:** Die deutsche ETF-Regel nutzt ein Berliner Zeitfenster; internationale Sitzungen, Handelsunterbrechungen und Feiertage sind noch nicht vollständig live abgenommen.
5. **Abnahme offen:** Erforderlich sind echte internationale Quellenantworten aus mehreren Zeitzonen, M2-eigene Observations/Current, korrektes Kursalter, ISIN/MIC/Originalwährung und **visuelle Browserkontrolle** am tatsächlich genutzten M2-Startweg.

Es gibt **keinen separaten Collector pro Land oder einzelner ISIN**. Die unterschiedlichen Provideradapter sind notwendige Schnittstellen; die darauf aufbauende Auswahl enthält aber **noch anbieterspezifische Prioritäts- und Zeitregeln**.

## 6. Maßgebliche Implementierungen und Tests

- [Gemeinsamer Quellenkatalog, Freigaben und Auswahl](../api/market_sources.php): **catalog()**, **scheduled()**, **allowed()**, **fact()**, **choose()**.
- [Zentraler privater M2-Collector](../scripts/market_collector/mosa_tick.php): **sourceRegistry()**, **acquire()**, **syncFact()**, **main()**.
- [MOSA-Router in M2 übernommen](../api/market_source_engine.php): **fixlabMosaMarketQuoteRouter()**, **fixlabMosaMarketEtfShadowSelection()**.
- [Twelve-Data-Adapter](../api/market_core/twelve_data.php), [EODHD-Adapter](../api/market_core/eodhd.php).
- [Vertiefung: internationale Quellen und Lizenzvoraussetzungen](database/M2_INTERNATIONAL_MARKET_PROVIDER.md).
- [Tests der gemeinsamen Quellenauswahl](../tests/test_market_tick_sources.php), [Twelve-Data-Tests](../tests/test_twelve_data_provider.php), [EODHD-Tests](../tests/test_eodhd_provider.php), [EODHD-MySQL-Tests](../tests/test_eodhd_mysql.php).

**Pflegeregel:** Bei Änderungen der Quellenaktivierung, Prioritäten, Frische-/ETF-Regeln oder Lizenzfreigaben diese Seite mitaktualisieren. **Diese Markdown-Seite ist nur Dokumentation; die ausführbare zentrale Quellenregistrierung bleibt allein im Code.**

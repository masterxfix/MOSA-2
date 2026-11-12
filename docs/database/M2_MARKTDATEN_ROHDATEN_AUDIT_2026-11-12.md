# M2: Rohdaten-Audit und Datenbank-Erweiterungsplan

**Datum:** 12.11.2026. **Status:** fachlich analysiert, **keine Migration ausgeführt**, kein Collector geändert.  
**Ziel:** Alle tatsächlich verfügbaren und für die Nutzung erlaubten Daten aus ISIN-gebundenen Quellen systematisch verarbeiten; mehr als MOSA, keine ISIN-Sonderlösungen, kein zweiter Collector, kein Reset.  
**Referenzmaterial:** authentifizierte, bereits im Browser geladene M2-Seite `anbieter-labor.html` mit `NO0010081235` (Abruf `2026-11-12T21:27:33Z`); M2 GitHub-Lauf [43308368967](https://github.com/masterxfix/MOSA-2/actions/runs/43308368967) (3× HTTP 200 bzw. 5 erfolgreiche Requests beim Live-Lab-Test mit anderem Wertpapier); unabhängige echte MySQL-Inventur [43312629482](https://github.com/masterxfix/MOSA-2/actions/runs/43312629482) (UTC `2026-11-12T21:41:01Z`); MOSA-Vorarbeiten `fixlab/docs/M8_32B_MARKTDATEN_QUELLENMATRIX.md` und `fixlab/docs/M8_32D_MARKTDATEN_COLLECTION_BUNDLE.md`.  

**Wahrheitsmaßstab:**
- `LIVE`: Im bereits angezeigten tatsächlichen NEL-Anbieter-Labor direkt mit Wert gefunden.
- `PARSER`: Gegenwärtiger M2-Parser liest das Feld (kann bei anderen ISINs fehlen).
- `HIST`: Frühere MOSA-Datei/Fixture belegt nur das Datenmodell oder ein historisches Beispiel; **nicht** im aktuellen NEL-Rohdatensatz bestätigt.
- `ABGELEITET`: Nur aus geprüften Zahlen berechenbar; kein zusätzliches unabhängiges Anbieterfeld.
- `FEHLT`: Bei diesem Abruf nicht geliefert oder `null`.
- `BEGRENZT`: Das Anbieter-Labor begrenzt die angezeigte Anzahl der Rohfelder. Es ist **kein** vollständiges Roharchiv.

## 1. Was wirklich ankommt

### 1.1 Lang & Schwarz (LIVE, NEL)

Echte, ISIN-identifizierte `lang_schwarz_search`-Felder: `isin=NO0010081235`, `wkn=A0B733`, `displayname=NEL ASA NK-,20`, `instrumentId=560527`, `categorySymbol=STK` und `categoryName=Aktie`. Weitere Felder (`id`, `categoryid`, `productcount`, `alias`, `categorysort`, `url`, `link`) sind überwiegend technische/Produktseiten-Metadaten. In diesem Suchergebnis wurde **kein belegtes `marketId`-Feld** angezeigt; ein vom Parser eingesetzter Default ist kein Nachweis.

Konkret der **richtigen Instrument-ID `560527@1`** zugeordnete Felder: `mid=0,1876 EUR`, `bid=0,1866 EUR`, `ask=0,1886 EUR`, `bidSize=27.263 Stück`, `askSize=27.263 Stück`, `midTime=22:22:27`, `midPerf1d=+0,0009`, `midPerf1dRel=+0,48 %`. Der normalisierte Quellzeitpunkt wurde `2026-11-12T21:22:27Z` angezeigt; 306 Sekunden Alter, `stale`: nicht als frischer handelbarer Kurs bezeichnen.

**Weitere tatsächlich auf der NEL-Seite angebotene Daten, die das bisherige Collector-Fact ignoriert:**

- Mehrere vollständige Einzelgeschäfte mit `tradeTime` (teilweise Millisekunden), `trade` und `tradeSize`; sichtbares Beispiel `20:09:11.271 / 0,1884 EUR / 350 Stück` und `15:26:39.911 / 0,1898 EUR / 17.244 Stück`. Das einzelne `lang_schwarz_trade`-Parserergebnis war zum Abrufzeitpunkt trotzdem `available=false`/`trade_not_delivered`: **Rohdaten vorhanden ≠ heutiger Adapter erkennt sie bereits zuverlässig**.
- Mehrere ältere Geld-/Briefstellungen mit `bidTime`, `bidSize`, `bid`, `ask` und `askSize`; beispielhaft `18:59:51.746 / 500 / 0,1873 EUR / 0,1926 EUR / 500`. Bei der Tabelle wird ein Uhrzeitwert ohne Tagesdatum geliefert; **Datum nicht ohne verifizierten Kontext erraten**.
- Angezeigte Referenzpreise und Perf.-Prozente für 1 Woche, 1 Monat, 6 Monate, laufendes Jahr, 1 Jahr, 3 Jahre und 5 Jahre. Diese sind **quellenseitige Periodenstatistiken**, keine echten OHLCV-Bars.
- `Tagesumsatz=4,13 Tsd.` ohne hinreichend eindeutige Einheit im isolierten Tabellenfeld – **nicht** als Stückzahl oder EUR übernehmen, solange das nicht verifiziert ist.
- `Abstand Allzeithoch=99,67 %` und `Abstand 52W Hoch=49,10 %`: Prozentabstände, **nicht** absolute Hochwerte.

**Explizit aussortieren:** Die gleiche HTML-Seite enthält Live-Indikatoren anderer Instrument-IDs, Derivate, Produktempfehlungen, Navigation, Handelskalender, Kauf-/Verkauf-Umfrageindikatoren und doppelte Darstellungen derselben Daten. Sie gehören **nicht automatisch zu NEL**. Nur exakt ISIN-/Instrument-/Market-ID-gebundene Werte können zu `NO0010081235` gespeichert werden. Das ursprüngliche Labor zeigte 370 Rohfeldzeilen, darunter zahlreiche Wiederholungen und fremde Inhalte. Es sind **keine 370 unabhängigen NEL-Marktdatenfelder**.

### 1.2 Tradegate BSX (LIVE, NEL)

Aus der separaten Kursseite: `WKN=A0B733`, `Kürzel=D7G`, `ISIN=NO0010081235`, `Handelswährung=EUR`, `Bid=0,1872`, `Ask=0,1890`, `Bid Size=28.000`, `Ask Size=127.000`, `High=0,1904`, `Low=0,1870`, `Last=0,1872`, `Change=-0,74 %`, `Umsatz=196 TEUR`, `Stück=1.038.691`, `Ø-Preis=0,1889`.

Die getrennte `orderbuch_umsaetze.php`-Antwort zeigt eine Tabelle mit `Datum`, `Uhrzeit` (Millisekunden), `Stückzahl`, `Auftragsstückzahl` und `Kurs`. Im abgeschnittenen Rohfeldinventar waren **mindestens 181 datierte Umsatzzeilen** zu erkennen; beispielhaft `12.11.2026 21:53:58,621 / 1.000 Stück / 0,1872 EUR`. Zusätzliche Folgezeilen enthalten teils Teilausführungs-/Auftragsgrößen. **Nicht jede HTML-Tabellenzeile ist eine unabhängige abgeschlossene Transaktion.** Der Parser muss Header, Parent-/Child-Zeilen, eindeutige Ausführungsidentität und Geschäftsstückzahl von Auftragsstückzahl trennen. Quelleninterne Stück-/Umsatzstatistik ist nicht automatisch das Handelsvolumen einer anderen Börse.

Die Seite zeigte **1.133 Rohfeldzeilen**, davon das Tradegate-Handelsfenster bei 1.100 Anzeigezeilen begrenzt. Inkludiert sind mehrfach dargestellte Werte, Kopfzeilen und Website-Navigation. Nicht als Anzahl Kennzahlen oder vollständige Historie interpretieren.

### 1.3 Börse Frankfurt / MIC XFRA (LIVE, NEL)

Das einzelne JSON-Objekt umfasste **22 sichtbare Rohfelder** einschließlich Null-/Anzeige-Metadaten:

| Feld | Tatsächlicher Wert | Behandlung |
|---|---|---|
| `isin` / `mic` / `currency.originalValue` | `NO0010081235` / `XFRA` / `EUR` | ISIN-, Handelsplatz- und Währungsbeweis |
| `lastPrice` / `timestampLastPrice` | `0.1872` / `2026-11-12T18:29:04+01:00` | marktbezogener Referenz-/letzter Preis, Quelle/Zeit bewahren |
| `closingPricePrevTradingDay` | `0.187` | Tagesreferenz, **nicht** mit letztem Kurs verwechseln |
| `dayHigh` / `dayLow` | `0.1932` / `0.1872` | Tageswerte nur für XFRA |
| `weeks52High` / `weeks52Low` | `0.3675` / `0.172` | 52-Wochen-Referenz, nicht Tageswerte |
| `turnoverInEur` / `turnoverInPieces` | `29608.0016` / `157453` | Umsatzbetrag vs. gehandeltes Stückvolumen getrennt |
| `priceFixings` | `12` | Zahl der Preisfeststellungen; **nicht** zu ausgeführten Einzeltrades umdeuten |
| `tradingTimeStart` / `tradingTimeEnd` | `08:00:00` / `22:00:00` | Plan-/Handelszeiten, **keine** einzelnen Zeitstempel |
| `minimumTradableUnit` | `1` | Handels-/Stammdatenregel |
| `changeToPrevDayAbsolute` / `changeToPrevDayInPercent` | `0.0002` / `0.11` | verifizierbare Veränderungsangaben |
| `lastPriceIndicator` / `turnoverNominal` | `null` / `null` | **nicht geliefert**, nicht erfinden |
| `tradedInPercent` | `false` | Preisnotierungs-/Instrumenteigenschaft |
| `currency.translations.others` | `Euro` | UI-Übersetzung, kein eigener Kursfakt |

`marketCapitalization`, `numberOfShares`, `bidLimit`, `askLimit` waren **nur im älteren MOSA-Feldvertrag** dokumentiert, nicht im aktuellen NEL-Frankfurt-Payload. Sie gehören als **optionale Modellfähigkeit**, **nicht** als aktuell kostenlos belegte Lieferung in den Plan.

**Quellentrennung:** Tradegate-High/Low/Volumen (z. B. 0,1904/0,1870/1.038.691 Stück) und Frankfurt-High/Low/Volumen (0,1932/0,1872/157.453 Stück) sind **kein gemeinsamer Marktstand**. Direkte Vergleiche nur mit identischem Börsen-/Währungs-/Zeitraumkontext.

## 2. Was `kostenlos` wirklich heißt und rechtliche Aktivierungssperre

Technischer HTTP-200-Abruf ist ohne ausgewiesene Einzelgebühr möglich, **nicht identisch mit der Erlaubnis zu automatisiertem Dauerbetrieb oder historischer DB-Speicherung**.

| Anbieter | Öffentliche Daten gesehen | Automatisierte Speicherung für M2 nachgewiesen erlaubt? | Entscheidung |
|---|---|---|---|
| L&S TradeCenter | Ja (NL/Quote/History, HTTP 200) | **Nicht nachgewiesen.** Website erlaubt persönliche private Kopien/Downloads; keine explizite M2-Minutencollector-Lizenz gefunden | Quelle nur mit geklärten Rechten für neuen Speicherausbau zulassen |
| Tradegate BSX | Ja (Kurs-/Einzelumsatzseiten, HTTP 200) | **Nein.** Offizielle Bedingungen untersagen maschinelle Zugriffe und Kopieren/Speichern ohne schriftliche Zustimmung | **Zwingender Rechte-Blocker** für Automatik und Persistenz; alternative lizenzierte Quelle prüfen |
| Frankfurt/Deutsche Börse | Ja (XFRA, HTTP 200) | **Nicht nachgewiesen.** Deutsche Börse verweist auf Market-Data-Vertrags-/Nutzungsregeln | Einsatzrechte für konkret verwendeten öffentlichen Datenpfad schriftlich klären |
| Yahoo Finance | Aus älterem MOSA bekannt | M2-Nutzerentscheidung: **ausgeschlossen** | unverändert aus |

Quellen (12.11.2026 geprüft): https://www.tradegatebsx.com/nutzungsbedingung.php · https://www.ls-tc.de/de/disclaimer · https://mds.deutsche-boerse.com/mds-en/real-time-data/agreements · https://mds.deutsche-boerse.com/mds-en/real-time-data/how-to-order-data

**Akute Konsequenz:** Das bereits laufende M2-Minutenprogramm ist technisch unabhängig von dieser Dokumentation. Seine bestehende Anbieterabfrage ist **keine** urheber-/lizenzrechtliche Freigabe. Insbesondere der Tradegate-Abruf sollte nach Prüfung der konkreten Nutzungsbedingungen **vor weiterem automatisierten Betrieb** ausgesetzt bzw. auf berechtigte Bezugswege umgestellt werden. Diese Analyse verändert den Cron/Providerzustand nicht.

## 3. Echtes Schema-6-Inventar: Stand UTC 21:41:01

**Read-only** gegen `h29077_mosa2_test`, dedizierter Reader, `transaction_read_only=1`, Ledger `0001`–`0006` bestätigt. Die Anlage der Schema-6-Tabellen ist real; die Dateikopfzeilen älterer SQL-Migrationen sind historische Vorbereitungsvermerke, keine Aussage über den heutigen Laufzustand.

| Bereits vorhanden | Was die Tabelle leisten kann | Strukturelle oder fachliche Grenze |
|---|---|---|
| `m2_assets`, `m2_asset_identifiers` | ISIN/WKN/Ticker als allgemeine Identitäten | Quellengebundene Nachpflege muss validiert sein; kein hartcodiertes Instrument |
| `m2_sources`, `m2_asset_source_routes` | Provider/Asset/Route, externe Quellidentitäten, Einheit, Version | physischer Handelsplatz, Quote vs. Trade und Berechtigung sauber abgrenzen |
| `m2_market_observations` | Preis, Bid/Ask, Volumen und Originalwährung, Markt-/Erfassungszeit, Herkunft, Historie | **kein Bid-/Ask-Volumen**; Writer übernimmt aktuell nur einen gewählten Kurs je Zyklus; temporäre Quote ohne Preis/Market-Time nicht abbildbar |
| `m2_market_current` | ein schneller ausgewählter Stand pro Asset, Tageshoch/-tief, Vortagesschluss, Tagesvolumen als Felder vorhanden | **PRIMARY KEY(asset_id)**, also **kein Current je Quelle/Markt**; Tagesfelder werden vom aktuellen Writer nicht gefüllt |
| `m2_market_bars` | OHLCV für 1m/5m/1h/1d | einzelne Prints und Bid/Ask-Historien sind **keine** vollständigen OHLCV-Bars |
| `m2_units` | 18 monetäre Einheiten + 1 Indexpunkteinheit, versioniert | **keine geprüfte handelsfähige Wertpapier-Stückeinheit** für Mengen-/Volumen-FKs |
| `m2_provider_fetches`, `m2_files` | Parser-/Payload-Metadaten, Hash, potenzielle Dateireferenzen | `m2_provider_fetches.file_id` ist Pflicht: kein Ersatz für reine fehlgeschlagene HTTP-Requests, rohe Payloads nur mit Archivierungsrecht |
| `m2_collector_requests` | Budget und Reservierung | keine vollständige normalisierte Datensatzfamilie je Provider/Rohfakt |

Im Read-only-Prüflauf lagen 76 Markt-Observations, 3 Current und 0 Bars vor, außerdem 0 Fetch-/File-Einträge; diese Zahlen sind **Momentaufnahmen**, keine Aussage über einen späteren Bestand.

## 4. Konkreter Erweiterungsplan für Schema 7 (additiv, ohne Reset)

**Entscheidung:** Schema-6-Verträge und bestehende Daten unverändert erhalten. Versionierte, neue Tabellen und nur notwendige nullable Zusatzfelder, kein pauschaler JSON-Blob als Massendatenspeicher. Für alle Markt- und Handelsdaten gilt `asset_id + source_id + route_id/physischer Handelsplatz + Marktzeit/Zeitzone + observed_at + Einheit + Quellrolle + Parserrevision`. Kein NEL-/ETF-/Xiaomi-Spezialpfad.

| Baustein | Neue Felder / Tabelle (Entwurf) | Zweck |
|---|---|---|
| **A – Identitäten** | vorhandene `m2_asset_identifiers` für `wkn`, `ticker`, `isin`; vorhandene `m2_asset_source_routes` für externe IDs; Versionierung/Quellbindung prüfen | keine unnötige zusätzliche `isin`- oder `wkn`-Tabelle |
| **B – Mengen** | neue versionierte Einheit für `security_piece`/handelbare Stückzahl, saubere Semantik (Aktien/ETF-Anteile), QUANTITY dimension und FK | notwendige Grundlage für `bid_size`, `ask_size`, `trade_size`, Stückvolumen; **keine** Umdeutung von EUR |
| **C – Historische Quotes** | `m2_market_observations` für **jede** gültige Quelle/Route (nicht nur Sieger); nullable `bid_size`, `ask_size`, optionale bewiesene Zeitfelder/Qualität; ggf. 1:1 `m2_market_quote_details`, wenn Schema-6-Writer nicht geändert werden darf | Parallelkurse, Offertengrößen, Spread/Zeitentwicklung pro Handelsplatz; ausgewählte Current-Projektion bleibt getrennt |
| **D – Source-Current** | neue `m2_market_source_current` (PK: Asset + Route + Quoteart), FK auf Original-Observation, Markt- und Abrufzeit | schnelle Mehrquellenansicht ohne teure `MAX`-Joins beim 30-Sekunden-Frontendabruf |
| **E – Einzelumsätze** | neue `m2_market_trade_prints`: Asset, Source, Venue/Route, Preis, Währung/Einheit, Trade-UTC (µs), gehandeltes Volumen, optionale `order_quantity`, Abruf-/Originalreferenz, parser_version, Dedupe/Status | Tradegate- und L&S-Einzelgeschäfte **ohne** Verwechslung mit Preisfeststellungen oder Auftragseingängen |
| **F – Tages-Snapshots** | neue `m2_market_session_snapshots`: Session-Date/Zone, High, Low, Open, Vortagesschluss, kumulierte Stückzahl, Umsatzbetrag + -währung, Ø-Preis, Fixings, Marktzeit, Abrufzeit; Version/Quelle | je Börsenplatz zeitlich fortgeschriebene Tageswerte; andere Handelsplätze nicht vermischen |
| **G – Referenzdaten** | neue `m2_market_reference_snapshots`: 52W-/Allzeithoch/-tief, evtl. `market_capitalization` und `shares_outstanding` (nur bei tatsächlicher Lieferung), `minimum_tradable_unit`, Gültigkeits-/Quellzeit | separate Stammdatenfamilie, keine vermischte Preisobservation |
| **H – Periodenperformance** | bei bestätigter Semantik `m2_market_provider_period_stats`: Referenzperiode/Horizont, Quellenreferenzkurs, gemeldete Veränderung absolut/% und beobachteter Zeitpunkt | L&S-1W/1M/6M/... aufbewahren, **ohne** dadurch eine OHLCV-Historie zu erfinden |
| **I – Abrufprotokoll** | neue `m2_market_source_attempts` (pro Request) mit Asset, Source, Requestrolle, HTTP-Code, Latenz, Bytes, Parserstatus, Fehlercode, Zeit, optional Hash/Fetch-FK | Erfolg/Teilfehler/lückenhafte Daten sichtbar; `m2_provider_fetches` nur bei rechtmäßiger Originalablage |
| **J – Quellenrechte** | neue `m2_market_source_rights` (Quelle, erlaubte Zwecke: manuell, automatisch, normalisierte DB, Roh-Archiv; Rechtsbeleg, Gültigkeit, bestätigte Limits, Zustand) | fehlende Berechtigung = keine automatischen Requests und keine DB-Schreibfreigabe |

**Technische Konsequenzen im Detail:**

1. `m2_market_observations` aktuell `price NOT NULL` und `market_at NOT NULL`: Ältere L&S-HTML-Quotes mit **nur Uhrzeit** sind kein sicher datiertes Market-Observation-Objekt. Entweder überprüfbaren Handelstag aus derselben Quelle nachweisen oder als `undated/unresolved` in einer getrennten, vom Kurswriter ausgeschlossenen Diagnosefamilie behandeln. Keine synthetische Datumszuweisung.
2. `m2_market_current` (PK Asset) bleibt **eine** bewusst ausgewählte Anzeigeprojektion; **alle** anderweitigen Quellenwerte gehören vor der Auswahl in append-only Beobachtungen. Gleiches gilt für `ETF` und `stock`.
3. **Deduplizierung:** Nicht pro Collector-Run dieselben Trades und Tages-Snapshots vervielfachen. Benötigt werden Identitäts-/Quellzeit-/Payloadregeln für tatsächliche neue Beobachtungen. Reale identische Mehrfachausführungen dürfen nicht irrtümlich zusammenfallen; Tradegate-Parent-/Child-Zeilen vor der Dedup-Definition fachlich auflösen. Der bestehende v2-Dedupe-Writer darf nicht ungeprüft neu interpretiert werden.
4. **Rohdatenhaltung:** Der Feldkatalog dient der Entdeckung. Roh-HTML inklusive fremder Instrumente, Navigation, Scripts oder nicht lizenzierter Marktdaten wird **nicht** automatisch aufbewahrt. Nur erlaubte Originalbelege, sonst normalisierte beweisbare Werte mit minimaler technischer Provenienz.
5. **Performance:** Indizes mindestens `asset_id, route_id, market_at` für Observations, `asset_id, source_id, trade_at` für Prints, `asset_id, source_id, session_date, observed_at` für Sessionwerte und `asset_id, route_id` für Source-Current. Neue Tabellen append-only außer expliziten Current-Projektionen. Keine ungebremste JSON-EAV- oder minutengenaue unveränderte Snapshot-Kopie.
6. **Internationale Einheiten:** EUR von L&S/Tradegate/XFRA ist nicht Heimatwährung. Handelsplatz, Handelswährung und ISIN-Ausgabeland nicht gleichsetzen. Ausländische native Preisquellen bleiben gesondert lizenz-/quota-/MIC-gesperrt.
7. **Historik:** Alte Anbieter-Seiten sind **keine** zuverlässige vollständige Historie seit 2025. Bis 2025 rückwirkend nur mit echter Historienquelle, belegtem Zeitfenster und Nutzungsrechten auffüllen.

## 5. Prioritäten nach fachlichem Wert

| Stufe | Daten | Grund |
|---|---|---|
| P1 | Bid/Ask und **beide Stückzahlen**, tatsächliche Quotezeiten und History | Liquidität, Spread, verfügbare Größe, zeitliche Mikrostruktur |
| P1 | Pro Quelle/Markt jede qualifizierte neue Quote und eigener schneller Current | Fehlende Anbieterbeobachtungen nicht verlieren, Marktabweichungen später nachvollziehbar |
| P1 | Einzelgeschäfte (Preis, Stück, echte Millisekundenzeit, ggf. Auftragsgröße) | Handelstätigkeit, große Blöcke, Zeit-/Preis-/Volumen-Zusammenhang |
| P1 | Tageshoch/-tief, Vortagesschluss, Stückvolumen, Umsatz in Originalwährung, Ø-Preis | Tagesstatistik, volumenbegleitete Bewegung |
| P2 | 52-Wochen-Marke, Fixings, Handelszeiten, kleinste handelbare Einheit | Kontext, Plausibilität, Handelsplatzspezifik |
| P2 | Periodenrenditen/Referenzkurse, WKN/Ticker/Provider-IDs | Vergleich und Identität; nur bestätigte Semantik |
| P3 | Kapitalisierung/Aktienanzahl, Allzeithoch, zusätzliche Statistikfelder | erst bei tatsächlich verfügbarer verifizierter Quelle; NEL-XFRA **nicht geliefert** |
| Nicht importieren | Web-Navigation, Fremdinstrumente, Derivate-Promos, irrelevante Website-Metadaten, unklare Stimmungs-/Kaufprozente | Keine echten ISIN-gebundenen Marktbeobachtungen |

**Abgeleitet, nicht doppelt persistieren:** `mid=(bid+ask)/2`, absoluter/relativer Spread, Tages-/Quellenabweichung, Tagesrange, Alter, einfache Wertänderungen. Für eine Vergleichsanalyse die zugrunde liegenden Rohfakten mit exakter Herkunft erhalten.

## 6. Prüf- und Freigabeweg (ohne Datenverlust)

1. **Feldvertrag gegen weitere reale Proben:** Dieselbe Matrix für wenigstens eine Aktie, ein ETF und einen Spezialfall mit fehlenden/zeitlosen Daten belegen. NEL-LIVE-Werte sind **nicht automatisch universelle Verfügbarkeit**. Kein hartcodierter ISIN-Pfad in Produktionsmodulen.
2. **Rechte-Gate:** Anbieter-/Produktgenehmigung für regelmäßigen Abruf, lokale normalisierte Speicherung und gegebenenfalls Roharchiv getrennt dokumentieren. Tradegate-Pfad ohne Zustimmung ausdrücklich blockieren bzw. berechtigte Alternative nutzen.
3. **Schema-7-Draft/Preflight:** nullable und neue Tabellen, FK-/Index-/Einheitenvertrag, geprüft gegen das wirkliche Schema 6 und echte bestehende Daten, Platzbedarf/Query-Pläne. Kein Reset.
4. **Getrennter Test:** Migrator gegen isolierten MySQL-Schema-6-Klon und synthetische Fixtures; vor Live-Apply irreversible DDL-Grenzen/Backups prüfen. Der bestehende Kernwriter bleibt nutzbar.
5. **Ein zentraler Collector:** Nur freigegebene Quellen, pro Instrument alle neuen Beobachtungen erfassen; Trade/Quote/Session/Reference getrennt. Nachrangige Current-Auswahl ändert die Rohdatenhistorie nicht.
6. **Echte Abnahme:** Originalantwort → identische ISIN/physischer Handelsplatz → Normalisierung → Quellbeobachtung → unabhängig lesbarer DB-Readback → Marktdatenseite; bei jedem Feld (insbesondere Stückzahl, Marktzeit, Währung, Ausfälle und Mehrfachumsätze). Bestehende Dogado-Jobs und MOSA unverändert.
7. **Last/Pflege:** Indizes, verlässliche Upserts ohne Datenvernichtung, source-spezifische Retention, P95 der Web-Seite < 2 s, bounded 30-Sekunden-Reader; keinerlei gleichzeitige Doppel-Providerrequests.

## 7. Noch nicht belegte oder freigabepflichtige Details

- Die komplette Tradegate-Umsatzliste ist auf der Testseite gekappt; im gegenwärtig geöffneten Labor sind nur **mindestens** 181 datierte Zeilen sichtbar. Parent-/Child-Zeilen müssen fachlich aufgelöst werden.
- L&S-Historienzeilen enthalten teils nur Uhrzeit. Kein sicheres Datum = keine künstlich präzise DB-Zeile.
- `Tagesumsatz 4,13 Tsd.` (L&S) ist ohne gesicherte Stück-/Währungssemantik offen.
- Quelle für zusätzliche `marketCapitalization`/`numberOfShares` ist in der tatsächlichen NEL-XFRA-Antwort **nicht** belegt.
- Datenrechte für die schon eingesetzten täglichen/minütlichen Website-Abfragen sind **nicht** durch einen HTTP-200-Test belegt; Tradegate weist automatisierte Nutzung sogar ausdrücklich zurück.
- Für echtes globales 24/7-M2 sind weiterhin **lizenzierte lokale MIC-Quellen in Originalwährung** erforderlich; drei deutsche EUR-Seiten reichen nicht.

**Abnahme dieses Auftrags:** Analyse der bereits geladenen **drei** echten Quellen, Feld-/Herkunftsprüfung, Live-Schema-6-Abgleich und konkrete additive DB-Vorbereitung dokumentiert. **Nicht Bestandteil:** Schemaänderung, Anlage neuer Tabellen, Codeänderung am Collector, Provider-Cron-Umschaltung, Lizenzbeschaffung. Kein Scheinerfolg behaupten.

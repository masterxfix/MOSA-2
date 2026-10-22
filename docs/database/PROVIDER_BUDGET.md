
# MOSA-Providerstrategie und MOSA-2-Zusatzlast

Stand: 21.10.2026. Ausschließlich Repository-/Dokumentrecherche und synthetische
Tests; keine neuen Providerabrufe, DB-Zugriffe, Hostingzugriffe oder Deployments.
fixlab wurde ausschließlich gelesen, nicht verändert.
Quellstände: fixlab baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c; MOSA 2 a21b3b7795eea5ab8a9f38c8e0a403351300cb32.

## Nachweisstufen und Bestand

| Aussage | Nachweis / Grenze |
| --- | --- |
| 10 Assets, 20 Requests, 20 erfolgreich, ca. 1 s | Historischer M8.134-Benchmark, im Architekturpapier 77 wiedergegeben. Kein neuer Dauer-, Grenzlast- oder Frankfurt-Nachweis. |
| Leichter Current-Pfad statt täglicher Historienpayloads pro Minute | In MOSA implementierte Requestprofile; für MOSA 2 bereits Frankfurt-Snapshot-Adapter vorhanden. |
| Minuten-/15-Minuten-Takte | Papier 76: 24/7 jede Minute. Papier 77: Current minütlich, reiches Yahoo-Intraday 15-minütlich; tägliche/backfill-Pfade getrennt. CLI-Scheduler hat selbst keinen Timer/Fälligkeitscheck. Aktuell installierte Cronintervalle und tatsächliche Tageslast ohne Laufbelege UNBESTÄTIGT. |
| Aktueller Code | Current-Scheduler filtert kanonische Aktien auf Frankfurt, hat zusätzlich L&S-/Tradegate-Quote-Router und Marktindikatoren. Daher keine Gleichsetzung des heutigen Requestmixes mit dem historischen 20-Request-Test. |
| Beobachtete Fehlergrenze | Historischer Benchmark: 0/20 Fehler. Keine aktuelle Fehlerquote, kein Dauerlastnachweis, kein experimentell bestimmter 429-/Sperrschwellwert vorhanden. |
| MOSA 2 | Erfolgreiche freigegebene Einzel-/Drei-/Fünf-Asset-Läufe sind funktionale Einmalbelege. Kein Nachweis für 5.520 Requests/Tag oder gleichzeitigen Dauerbetrieb mit MOSA. |

Gelesene Primärquellen (unveränderlich an fixlab-Commit gebunden):
[Architektur 76](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/docs/76_M8_124_GENERIC_MARKET_DATA_ARCHITEKTUR_2026-08-23.md),
[Takte 77](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/docs/77_M8_135_MARKET_DATA_CADENCE_ARCHITEKTUR_2026-08-24.md),
[Scheduler](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_scheduler.php),
[Batchtransport](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_batch_transport.php),
[Frankfurt-Descriptor](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_boerse_frankfurt.php),
[Quote-Runner](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_live_quote_runner.php),
[Indikatoren](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_indicator_collector.php),
[Verifier](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_source_readonly_verifier.php),
[Intraday](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_intraday_runner.php),
[inkrementeller Filter](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_incremental_state.php).
Taskdateien wurden nur als historische Planung, nicht als ausgeführter Nachweis gewertet.

## Endpunkte, Requests und technische Schutzgrenzen

Alle Zahlen unten sind Codepfad-/Planwerte, keine aktuellen Registryzählungen.
F = eindeutige qualifizierte Frankfurt-ISINs im Current-Pfad,
A = eindeutige ISINs der Aktien/ETFs im zusätzlichen Quote-Router,
P = tatsächlich gefundene L&S-Seiten (0 ≤ P ≤ A),
I = Yahoo-Intraday-Symbole, C = notwendige eindeutige FX-Paare.

| Provider / Pfad | MOSA pro Aufruf | Zusätzliche MOSA-2-Requests pro Fünferlauf |
| --- | --- | --- |
| Frankfurt api.live.deutsche-boerse.com/v1/data/price_information/single?isin=…&mic=XFRA | F, URL-/Header-Fingerprint dedupliziert | 5, dieselbe Endpunktfamilie |
| Frankfurt /v1/tradingview/lightweight/history/single | Separate Intraday-/Daily-/Backfill-Descriptoren vorhanden; Current nutzt sie nicht. Tatsächliche Aufruffrequenz offen. | 0 |
| Yahoo query1.finance.yahoo.com/v8/finance/chart/… | Current-Descriptor range=1d, interval=1d; heutiger kanonischer Aktien-Current-Pfad jedoch Frankfurt. Indikatoren: 5 Yahoo-Requests pro Indikatorphase. Separater Intraday-Pfad I + C, Primärdaten interval=1m, range=1d, FX kompakt/current. | 0 |
| L&S www.ls-tc.de/_rpc/json/.lstc/instrument/search/main und gefundene Instrumentenseite | Quote-Router: A Suchrequests + P Seitenrequests, abhängig von Scope/Discovery. Historischer Chartpfad /_rpc/json/instrument/chart/dataForInstrument vorhanden. | 0 |
| Tradegate www.tradegatebsx.com/orderbuch.php?isin=… | A Offerten; zusätzlich 1 DAX-Request /indizes.php?index=…&lang=de in der Indikatorphase | 0 |

Im Current-Scheduler können somit F + A + P + A + 6 logische Requests
anfallen, zusätzlich variabler Onboarding-/Discovery-Traffic. Registry und
Quote-Router enthalten ggf. verschiedene Scopes; keine erfundene Assetanzahl.
L&S-Seiten dürfen höchstens zwei HTTPS-Weiterleitungen folgen: Wire-Requests
können deshalb höher als logische Requestzähler sein. Andere beschriebene
Verifierpfade folgen Redirects nicht. Requests verschiedener Jobs/Phasen
werden nicht gemeinsam providerübergreifend dedupliziert.

Batchtransport: maximal 12 gleichzeitig aktive Handles, zwei Prefetchphasen
(Primärdaten, nötiges FX), sortierte Verarbeitung, Fingerprintcache,
Cache-Miss-Erkennung, kein spontaner Netzwerknachschlag aus dem Cache.
Das ist eine lokale technische Parallelitätsgrenze, KEIN Providerlimit.
Verifier/Quote-Transport: 5 s Verbindungs-, 12 s Gesamttimeout, TLS-Prüfung.
Current-Lock nichtblockierend; Intraday teilt denselben MOSA-Lock, wartet
höchstens 45 s in 100-ms-Schritten. Das sind Lockversuche, keine HTTP-Retries.
Die untersuchten Transportpfade wiederholen fehlgeschlagene HTTP-Anfragen
nicht automatisch. Nicht-2xx wird als Fehler behandelt; kein spezifischer
429-/Retry-After-Circuit nachgewiesen. Antwortheader werden dafür nicht
erhalten. Konstanten MAX_REQUESTS im Read-only-Verifier (Yahoo 1, L&S 4,
Frankfurt 3) begrenzen einzelne Diagnoseoperationen, nicht den Provider
und nicht den gesamten Scheduler.

MOSA 2: bestehender HttpGet-Transport ist einmalig, ohne Redirects, Cookies
oder Auth-Handler, standardmäßig 20 s Timeout (Parameter höchstens 60 s);
auch Fehlschlag verbraucht den Versuch. Aktuell wird Retry-After nicht
weitergereicht. Der neue Vertrag wird noch nicht in diesen Livepfad eingehängt.
Fünf serielle 20-s-Timeouts könnten bereits 100 s beanspruchen; aus 4,43 s
je Aktie im erfolgreichen Dreiertest folgt keine gesicherte 60-s-Deadline
für fünf Aktien. Keine Aufholschleifen oder überlappenden MOSA-2-Läufe vorsehen.

## Berechnete Zusatzlast des gewünschten Rhythmus

Europe/Berlin, halb offene Fenster: werktags [06:00, Folgetag 00:00) alle
60 s; [00:00, 06:00) alle 900 s. Wochenende und bekannte Feiertage 900 s.
Fünf bestehende qualifizierte Aktien, je eine Frankfurt-Anfrage, keine
FX-/Discovery-/Historienrequests, kein Retry. Kalender unbekannt: keine
automatische Freigabe. cadence_seconds/day_load sind nur Lastsimulation.

| Zeitraum | Läufe | Frankfurt zusätzlich |
| --- | ---: | ---: |
| schnelle Werktagsstunde | 60 | 300 (5/min, im Mittel 0,0833/s; Batchburst möglich) |
| langsame Stunde | 4 | 20 |
| normaler Werktag | 1.080 + 24 = 1.104 | 5.520 |
| normaler Wochenende-/Feiertag | 96 | 480 |
| Woche ohne Feiertag/DST | 5.712 | 28.560 |
| Woche mit einem Werktagsfeiertag | 4.704 | 23.520 |
| Sonntag Sommerzeitbeginn / Winterzeitbeginn | 92 / 100 | 460 / 500 |

Je zusätzlichem Werktagsfeiertag gegenüber normaler Woche: minus 5.040.
Kalenderwochen mit DST haben entsprechend minus/plus 20 Requests.
Bei Ausfällen oder ausgelassenen Läufen liegt die tatsächliche Last darunter.

Vergleich: +5 sind 25 % der historischen 20 gemischten Benchmarkrequests,
aber NICHT 25 % einer bekannten Frankfurt-Last. Gegen heutigen Code:
Frankfurt relativ +5/F je gemeinsamem Current-Tick; Yahoo/L&S/Tradegate +0.
Beispiel, ausdrücklich hypothetisch: F=10, MOSA jede Minute 24/7 →
10/min Frankfurt, mit MOSA 2 tagsüber 15/min (+50 %), nachts 10,333/min
im Mittel. 14.400 MOSA-Frankfurt/Tag + 5.520 = 19.920 an normalem Werktag
(+38,33 %); pro normaler Woche 100.800 + 28.560 = 129.360 (+28,33 %).
Diese Baseline ist eine Rechenannahme, kein aktueller Betriebsnachweis.
Onboarding, Indikatoren, andere Nutzer/Jobs, Redirects und geteilte
Ausgangs-IP müssen zusätzlich in einer echten Baseline erfasst werden.

## Nutzungsrechte und Providergrenzen

Recherche ausschließlich auf offiziellen Informations-/Vertragsseiten,
keine Anfrage an den Kursendpunkt, keine Registrierung oder Kontaktaufnahme.

- [Offizieller Disclaimer](https://live.deutsche-boerse.com/disclaimer):
  enthält besondere Bedingungen für **Download Price History**:
  nicht ausschließliche, nicht übertragbare und nicht unterlizenzierbare
  Nutzung heruntergeladener FWB-Daten; kostenlose Lizenz an Bedingungen
  fehlender Kommerzialisierung gebunden. Für die dort beschriebene
  Kommerzialisierung wird eine gesonderte kostenpflichtige Lizenz verlangt.
  Dies belegt KEINE Freigabe automatischer Snapshot-API-Abfragen,
  regelmäßiger Speicherung oder einer öffentlichen Weitergabe durch MOSA 2.
- [Offizielle Agreements & Guidelines](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/agreements)
  unterscheiden Marktverbreitung und Non-Display-Nutzung.
  [Offizielle Non-Display-Richtlinien](https://www.mds.deutsche-boerse.com/mds-en/real-time-data/Guidelines-and-Policies-2716338)
  beschreiben eigene Nutzungskategorien. Deren konkrete Anwendbarkeit,
  Produkt, Echtzeit-/verzögerter Status und vorhandene Berechtigung des
  Nutzers sind hier nicht nachgewiesen. Kein pauschaler Lizenzschluss
  allein aus einem allgemeinen Vertragsverzeichnis.
- Für genau /v1/data/price_information/single wurde keine offizielle
  öffentliche Rate-Limit-/Quota-/Burst-/SLA-Dokumentation gefunden.
  Unbekannt bedeutet weder unbegrenzt noch verboten. Technischer Erfolg
  und vorhandene Requestheader sind keine Lizenz oder Mengenfreigabe.
- Praktisch beobachtete Belastungsgrenze: nicht bestimmt. Historisch 20/20
  erfolgreiche gemischte Requests und MOSA-2-Einmalläufe sind nur untere
  Erfolgsbelege ihrer jeweiligen Testbedingungen, keine Dauerlastgrenze.
  Nachgewiesene Nutzungsberechtigung für den geplanten automatischen
  MOSA-2-Dauerabruf: **UNGEKLÄRT**. Vor einem späteren Test Rechte und
  konkrete erlaubte Verwendung anhand belastbarer Bedingungen klären;
  in diesem Auftrag keinen Anbieter kontaktieren.

## Gemeinsamer MOSA-2-Budget- und Monitoringvertrag

config/collector-provider-budget.json und scripts/provider_budget_plan.py.
Standard deaktiviert; rights_confirmed=false, Providerlimit/Baseline unbekannt,
eigene freigegebene Minuten-/Tagesbudgets 0, kombinierte Limits und
Schwellwerte null. Vorschlag für später höchstens 1 MOSA-2-Providerzugriff
gleichzeitig und höchstens 5 Anfragen pro Lauf: interne konservative
Testgrenzen, keine gemessenen oder zulässigen Providerkapazitäten.

admission() ist rein simuliert, execution_authorized=false. Anforderungen:
frische bekannte MOSA-Baseline und MOSA-2-Zähler für denselben Provider,
rollierende 60-s-Nutzung, lokaler Tagesstand, laufende/ungeklärte Jobs,
eigene sowie kombinierte genehmigte Budgets und Gesamtparallelität.
Alle Requests derselben Provider-/Hostfamilie zählen, auch andere Endpunkte
und Fehler; reservierte/gestartete Versuche bleiben verbraucht.
MOSA erhält Vorrang: wenn Reserve fehlt, nur MOSA 2 überspringen/blockieren.
Keine Änderung an MOSA-Locks, Konfiguration, Prozessen oder Freigaben.
Eine reale atomare Reservierung/Telemetry-Anbindung ist noch nicht implementiert.

observe() projiziert ausschließlich sichere technische Felder, begrenztes
Fehlerfenster, Latenz, Datenalter und bestehende Writerentscheidung.
429 samt Retry-After (Sekunden oder HTTP-Datum) → MOSA-2-Stopp mit
frühestem Wiederaufnahmehinweis, auch bei ungültigem/fehlendem Header
Stopp. 401/403 oder Sperrindikator → sofortiger MOSA-2-Stopp.
Keine automatische Wiederaufnahme nach Ablauf von Retry-After oder bei 200.
Genehmigte Latenz-/Timeout-/Fehlertrend-Schwellen und gemeldete MOSA-
Beeinträchtigung stoppen ebenfalls nur MOSA 2. Bestehendes Stop-on-Failure
des Collectors bleibt zusätzlich erhalten. Fehlende Schwellen/Evidenz
erlauben keinen Betrieb. Keine Proxy-/IP-/Headerrotation, Captcha-,
Authentifizierungs- oder Limitumgehung.

Marktzeit, Erfassungszeit, Datenalter und INSERT/DUPLICATE_UNCHANGED getrennt
beobachten. Alte Daten nicht künstlich frisch machen; Stale ist ein
Monitoringzustand, kein Anlass zu Zusatzrequests oder Preis-/Zeitänderungen.
MOSA-2-Observation-v2 kanonisiert auch observed_at; der Frankfurt-Normalizer
bindet es an collected_at. Exaktes Replay desselben Payload-Snapshots:
DUPLICATE_UNCHANGED. Neuer Abruf mit neuer Erfassungszeit: anderer Schlüssel,
selbst bei gleichem Preis und market_at potenziell INSERT. Neue Marktzeit
bei gleichem Preis ebenfalls nicht verwerfen. Bis zu 5.520 neue Observations
pro normalem Werktag sind daher rechnerisch möglich. Dedupe spart keine
Netzwerkanfragen. MOSAs inkrementellen Quellzeit-/Content-Filter nicht ohne
eigene fachliche Freigabe in den MOSA-2-Writer kopieren; Kern bleibt unverändert.

Der historische Betriebsplan-v1 überspringt weiterhin geschlossene Handelstage.
Der gemeinsame Offline-Zyklus verwendet ausdrücklich Betriebsplan-v2 mit
BERLIN_60_900_V1 und denselben zentralen Taktfunktionen wie das Lastmodell.
Feiertage bedeuten darin 900 Sekunden statt Ausfall. Alte Verträge und Tests
werden nicht stillschweigend geändert; die deaktivierten Konfigurationen bleiben
unverändert. Vertrag, lokale Simulation, strenge Monitoringintegration und noch
fehlende Live-Voraussetzungen: [COLLECTOR_CYCLE.md](COLLECTOR_CYCLE.md).

## Später separat freizugebende Teststufen

1. **Passiv:** bestehende MOSA-Telemetrie für normale/spitze sowie langsame
   Zeitabschnitte auswerten: Provider-/Wire-Requests, Ausgangs-IP, Latenzen,
   Status/429/403/Timeouts, Erfolgs-/Fehlerraten und Ressourcennutzung.
   Keine zusätzlichen MOSA-Requests. Ohne belastbare Baseline nicht starten.
2. **Klein:** nach Rechteklärung einmal eine qualifizierte MOSA-2-Aktie,
   maximal ein Request; MOSA-Metriken vor/während/nachher vergleichen.
3. **Ausweiten:** gesondert einmal zwei, danach separat maximal fünf
   qualifizierte Aktien, je höchstens ein Request. Kein automatischer
   Aufstieg bei Erfolg. HTTP-Sperrindikatoren stoppen MOSA 2 sofort.
4. **Takt prüfen:** erst danach eine separat genehmigte endliche Anzahl
   langsamer Zyklen, später ggf. separat begrenzte 60-s-Zyklen. Anzahl,
   Gesamtbudget, Dauer, kombinierte Parallelität und Abbruchschwellen
   vorher festlegen; keine Dauerfreigabe aus Einzeltests ableiten.

Shared-IP-Sperren können MOSA trotz getrenntem Prozess betreffen; dazu kommen
CPU-/DB-/Speicher- und zeitgleiche Netzwerkspitzen. Stopp von MOSA 2 reduziert
Zusatzlast, beweist aber keine unbeeinträchtigte MOSA-Ausführung.
Keine aktuelle Baseline/Anbieterschwelle oder störungsfreie Koexistenz
nachgewiesen. Heute bleibt jeder Regel-/Teststart gesperrt.

Offline-Tests: exakte Tages-/Wochenrechnung, DST, fehlender Kalender,
kombinierte Budgets/Baselinealter, MOSA-Vorrang, Parallelität, 429/Retry-After,
403/Sperre, Timeout-/Fehlertrend, Latenz, Datenalter, sichere Ausgabe,
unveränderte Eingaben und tatsächlicher bestehender WriterPlanner mit
synthetischem exaktem Replay und neuer Erfassungs-/Marktzeit.

**Testergebnis:** 36/36 PASS (15 Provider-/Last-/Dedupe-Tests und 21
unveränderte Betriebsplan-Regressionen), Syntax PASS:
[Offline-Actions 39602934272](https://github.com/masterxfix/MOSA-2/actions/runs/39602934272).
Die zunächst gewählte normale Wochenfixture enthielt eine DST-Umstellung;
der korrigierte Test prüft normale, Feiertags- und DST-Woche getrennt.
Keine Schutzprüfung abgeschwächt, kein Live-Netzwerk oder Secret im Test.

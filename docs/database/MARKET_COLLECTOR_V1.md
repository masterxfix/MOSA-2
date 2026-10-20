# Marktdaten-Collector v1 – nativer Offline-Hauptpfad

Issue [#34](https://github.com/masterxfix/MOSA-2/issues/34), Ausgangspunkt
`82d256b495ce35e89ed45f388d2519c0b48c72ad`.

**Technisch realistisch: JA.** Observation-v2-Writer, Unitkatalog und qualifizierte
Route-/Unitbindung existieren. Der Collector liegt als eigenständige Schicht
davor; sämtliche benötigten Observationfelder sind vorhanden. Keine
Schemaänderung, Migration 0004 oder neue Abhängigkeit erforderlich.

Der allgemeine Collector ist der neue Einstieg für zukünftige native Marktdaten.
Die historische Restmigration wird dadurch nicht freigegeben. B8 bleibt gemäß
[Phase 3Q](PHASE3Q_B8_EVIDENCE.md) geparkt; B6/B7 bleiben ebenfalls geparkt.
Migrationen und bestehende Phase-3N-/Unitmodule unverändert. Die Homepage wurde
in Issue #36 ausschließlich inhaltlich auf den Stand vom 20. Oktober aktualisiert.

## Architektur und Verantwortungen

`FixtureTransport → Collector → Provideradapter → gemeinsamer Normalizer → Phase-3N WriterPlanner`

| Modul | Aufgabe |
| --- | --- |
| `scripts/market_collector/contracts.py` | Unveränderliche Requests, Responses, Payloads, qualifizierte Routensidecars und native Candidates; Transport-/Adapterprotokolle |
| `collector.py` | Request validieren, registrierten Adapter auswählen, Responsebytes und Transportmetadaten übernehmen, exakten Payloadhash bilden |
| `yahoo_chart.py` | Nur Yahoo-Chart-Snapshot v1: JSON, Symbol, native Providerunit und Unix-Marktzeit interpretieren |
| `boerse_frankfurt.py` | Börse-Frankfurt-price_information-Snapshot v1: ISIN/XFRA/EUR, lastPrice und explizite ISO-Marktzeit prüfen |
| `normalizer.py` | Providerneutral IDs/Route/Units/Provenienz prüfen, Raw-Observation erzeugen und an den vorhandenen Writer übergeben |
| `http_transport.py` | Explizit gebundener, einmal verwendbarer anonymer HTTPS-GET; keine Providerlogik, Cookies, Credentials, Redirects oder Retries |

Der Collector kennt keine Preise, Währungen, Units oder Yahoo-Feldnamen.
Provideradapter werden über ihren versionierten Schlüssel registriert; keine
Providerverzweigung im Core. Doppelte/fehlende Adapter und fehlende Fixture-
Requests werden abgewiesen. Keine automatische Discovery oder Ersatzquelle.

Die Schnittstellen `Transport.fetch(Request) -> TransportResponse` und
`ProviderAdapter.normalize(CollectedPayload, RouteContract) -> ObservationCandidate`
haben zunächst ausschließlich `FixtureTransport` verwendet. Issue #36 ergänzt
einen ausdrücklich übergebenen `ReadOnlyHttpTransport` für genau einen freigegebenen
GET; der Core importiert oder aktiviert ihn nicht selbst. Provider-URL und
technische Header kommen getrennt aus dem qualifizierten Requestvertrag.
Kein Retry, Scheduler, Credentialszugriff oder Live-Fallback. Weitere Transport-/
Adapterimplementierungen bleiben eigener zu qualifizierender Code.

## CollectedPayload und unveränderte Bytes

`contract_version = mosa2-collected-payload-v1`; weitere Felder:

`provider_key`, `source_id`, `route_id`, `request_key`, `requested_at`,
`collected_at`, `http_status`, `content_type`, `payload_sha256`, `payload_bytes`,
`transport_status`, `transport_error`.

Payload und Response sind eingefrorene Dataclasses mit echten unveränderlichen
`bytes`. Der Fixturetransport kopiert seine Zuordnung und gibt exakt die
eingefrorene Response zurück. Der Collector dekodiert, parst und serialisiert
die Payload nicht. SHA-256 umfasst jedes originale Byte einschließlich Whitespace
und abschließendem LF; keine JSON-Kanonisierung. Vor Providerinterpretation und
gemeinsamer Normalisierung wird diese Bindung geprüft. Geänderte Bytes oder
geänderter Hash führen zu REJECT.

Die Requestbeschreibung enthält den generischen qualifizierten Instrumentbezug,
keinen Endpunkt oder freie Providerfelder. Der eingefrorene Request selbst ist
der Fixtureschlüssel; Provider, Source, Route, Instrument, Requestkey und
Anforderungszeit müssen passen. Zeit und alle IDs kommen vom Aufrufer. Die
vorhandenen Phase-3N-Wertprimitiven prüfen kanonische IDs und UTC-DATETIME(6).
Erfassung darf nicht vor der Anforderung liegen. Keine lokale aktuelle Uhr.

HTTP-/Transportfehler bleiben im Rohbeleg sichtbar, dürfen aber keinen Candidate
erzeugen. Erwartet werden erfolgreicher Transport, 2xx und JSON-Content-Type.
Transportfehler sind technische Codes, keine beliebigen Secret-/Diagnosetexte.

## Yahoo-Snapshot-v1 und Candidate

Erster Adapterkey: `yahoo_finance_chart_v1`. Architektur-/Semantikreferenz nur
die zwei erlaubten historischen fixlab-Dateien auf
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`:
`php/mosa_market_collection_runner.php` (registrierter Instrument-/Sourcekontext)
und `php/market_collection_bundle.php` (GBp/GBX und Snapshot-Metafelder).
Keine anderen historischen Dateien oder heutige Providerantworten benötigt.

Genau ein `chart.result[0].meta` wird erwartet; Providerfehler, fehlende Meta,
mehrdeutige JSON-Member und abweichendes Symbol werden abgewiesen. Der Provider
definiert weder Asset noch Source, Route oder deren Unitbindung.

| Providerfeld | Native Bedeutung |
| --- | --- |
| `meta.regularMarketPrice` | `native_price`; JSON-Zahlen dezimal und ohne binäre Floatkonvertierung gelesen |
| `meta.regularMarketTime` | `market_at`; ganzzahlige Unixsekunden explizit in UTC-DATETIME(6) übersetzt |
| `meta.symbol` | muss zum qualifizierten Request-/Routeinstrument passen |
| `meta.currency` | EUR → EUR, GBP → GBP, GBp/GBX → Providerunit GBX |
| `CollectedPayload.collected_at` | `observed_at`, getrennt vom Marktzeitpunkt |
| `meta.regularMarketVolume` | bewusst ignoriert; kein qualifiziertes Historyvolume |

Keine Liste aller Währungen; nur die benötigten normativen Providerunits.
Ungültige Zeiten, fehlende Preise, nichtendliche/zu präzise Zahlen und
unbekannte Providerunits werden abgewiesen. Keine Rundung oder Floatreparatur.
Der bestehende Writer prüft abschließend seine Preis-/Zeit-/Wertebereiche.

`ObservationCandidate` enthält `asset_id`, `source_id`, `route_id`, `market_at`,
`observed_at`, `native_price`, `native_bid`, `native_ask`, `native_volume`,
`provider_unit`, `payload_sha256`, `provenance`. Dieser erste Adapter liefert
Bid/Ask/Volume NULL. Die immutable Provenienz enthält Providerkey, Requestkey,
Payloadhash und die konkreten Preis-, Zeit-, Symbol- und Unitfeldpfade sowie
die Erfassungszeitquelle. Originalbytes verbleiben im CollectedPayload; keine
zweite Rawpayloadkopie im Candidate und keine Secrets.

## Börse-Frankfurt-Snapshot-v1

Issue [#35](https://github.com/masterxfix/MOSA-2/issues/35), Ausgangspunkt
`d8106f8a0ea188b9ab1c4f29bf77fe1d994ad19e`. Zwei reale Provideradapter sind jetzt
offline unterstützt: Yahoo Snapshot v1 und Börse Frankfurt Snapshot v1.
Collector-Core, Contracts, gemeinsamer Normalizer und Yahoo-Modul bleiben
byteidentisch. Die vorhandene Adapterregistrierung reicht unverändert aus;
beide Adapter können gleichzeitig übergeben werden. Kein Yahoo-Fallback.

Neuer Adapterkey `boerse_frankfurt_api_v1`, historischer Providerbezug
`boerse_frankfurt_api`. Ausschließlich Semantikreferenz auf fixlab-Commit
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`:

- `php/mosa_boerse_frankfurt.php`, Git-Blob
  `ead84889894fd3c1336e2259abb14b607446f366`: current/rich verwenden fachlich
  price_information, MIC XFRA, Currency EUR.
- `php/market_collection_bundle.php`, Git-Blob
  `8c4cc8afe3b9eef28ecb50cb0251e87fbc7781ba`, price_information-Zweig:
  Payload-ISIN/MIC/Currency werden gegen den Kontext gebunden, lastPrice und
  timestampLastPrice bilden den Snapshot. Keine andere historische Datei nötig.

Keine historischen Header-/Security-/Transportfunktionen übernommen und keine
aktuelle Providerkompatibilität behauptet. Request.instrument und
RouteContract.instrument sind dieselbe qualifizierte ISIN, formal zwölf große
alphanumerische Zeichen. Keine Tickerheuristik, Identitätssuche oder Stammdatenanlage.

| Frankfurt-Payloadfeld | Prüfung / nativer Candidate |
| --- | --- |
| `$.isin` | exakt gleich qualifiziertem Request-/Routeinstrument |
| `$.mic` | exakt XFRA |
| `$.currency.originalValue` | exakt EUR; Providerunit EUR |
| `$.lastPrice` | einziger Preis; echte JSON-Zahl, dezimal ohne Float-Zwischenrechnung gelesen |
| `$.timestampLastPrice` | ISO mit explizitem Z oder ±HH:MM; UTC-DATETIME(6) |
| `CollectedPayload.collected_at` | observed_at; unabhängig vom Marktzeitpunkt |

Der Adapter verlangt ein JSON-Top-Level-Objekt, eindeutige Member und unveränderten
Payloadhash. Fehlender/widersprüchlicher Kontext und ungültige Preis-/Zeitfelder
führen zu REJECT. Zeitwerte ohne Offset, ungültige Kalenderdaten/Offsets und mehr
als sechs Nachkommastellen werden abgewiesen; keine lokale Zeitzone und keine
stille Mikrosekundentrunkierung. Präzisions-/Bereichsprüfung der nativen Preise
bleibt im vorhandenen Writer, keine Rundung, Skalierung oder FX-Rechnung.

Provenienz bindet provider_key, request_key, payload_sha256 und exakt die
JSON-Pfade für Preis, Zeit, Instrument, MIC und Unit sowie die Erfassungszeitquelle.
Keine Rawkopie im Candidate. Der gemeinsame Normalizer prüft Providerunit EUR
gegen die qualifizierte Route EUR@1 und leitet Currency EUR aus dem Katalog ab;
der Adapter baut keinen MOSA-Unitvertrag nach.

Bid/Ask/Volume bleiben NULL. turnoverInPieces, turnoverNominal, turnoverInEur,
closingPricePrevTradingDay, Tages-/Jahresgrenzen und minimumTradableUnit werden
bewusst nicht zu Historyvolume oder weiteren Observations. Nur lastPrice.
Keine History, Intraday-History, Daily/Backfill, Bars, Current-Auswahl oder Scheduler.

Eine zusätzliche eingefrorene synthetische Frankfurt-Fixture mit fiktiver
12-Zeichen-Kennung enthält absichtlich diese Zusatzfelder. Neun neue Frankfurt-
Tests ergänzen den bestehenden Collectorblock: echtes End-to-End-INSERT samt
Writerbytes/Key und Provenienz, ISIN, MIC, Currency/Routeunit, Preis, ISO-Zeit,
JSON-/Hashintegrität, ignorierte Zusatzfelder und parallele Registrierung ohne
Fallback. Bestehende Yahoo-Tests unverändert, kein neuer Yahoo-Testkatalog.
Lokale Gesamtregression und Linux-Vollrun für diesen Auftrag jeweils genau
einmal; endgültige Ergebnisse/Run-ID in Issue #35. Kein PHP geändert.
Erster und einziger gezielter Collectorblock: **28/28 bestanden**, darin
**9/9 neue Frankfurtfälle**. Keine Testfehler oder zusätzlichen Fehler-Retests.
Einmalige lokale Gesamtsuite: **427/428**, ausschließlich bekanntes Windows-
`budget_not_private`; Validate (drei Webdateien) und Diff-Check bestanden.
Keine Codekorrektur nach Abschlussregression und kein Wiederholungslauf.

## Routeautorität, gemeinsame Normalisierung und Writer

`RouteContract` ist ein unveränderlicher qualifizierter Aufrufer-Sidecar:
Providerkey/Instrument plus unverändertes Phase-3N-Routenenvelope mit
`format_version` und `route`. Keine neuen SQL-Spalten. Die Route enthält exakt
`id`, `asset_id`, `source_id`, `route_revision` und die acht bestehenden Unitfelder.
Der Normalizer verlangt Format 2, positive Revision, vollständige Unitbindung
und passende IDs. Legacy-v1 wird nicht still umgedeutet.

Providerunit muss exakt zur Quote-Unit passen. `currency` stammt ausschließlich
aus `monetary_currency_code` der qualifizierten Unitdefinition: EUR@1 → EUR,
GBP@1 → GBP, GBX@1 → GBP, POINT@1 → NULL. Der gemeinsame Code kennt keine
GBX-/Yahoo-Sonderregel. Ein synthetischer Testadapter mit POINT belegt diese
Providerneutralität; er ist kein zusätzlicher realer Provideradapter.

GBX bleibt eine native Pence-Zahl mit GBX@1 und Currency GBP. Keine Division
durch 100, FX-Rechnung oder zweite Basispreis-Observation. Mengenbasis,
Historyvolume und Volumeunit müssen für diesen Snapshotpfad NULL sein. Spätere
Volumequalifikation ist ein eigener Vertrag. Kein OHLCV-/Bars-Normalizer,
FX-/Derived-Layer, Current-Arbitration oder automatische Routenauswahl.

Der Normalizer erzeugt ausschließlich die vorhandenen 18 Raw-Observation-v2-
Felder. Danach genau der bestehende `WriterPlanner.plan(...)` mit
`format_version=2`, `intent=NEW_NATIVE_V2`, `representation=native` und explizitem
`created_at`. Keine neue Kanonisierung und kein zweiter Observation-Dedupehash;
der Transport-Payloadhash ist ein anderer, ausdrücklich separater Nachweis.

Der Pipelinebericht enthält Gesamtentscheidung, Collector-/Adapter-/Normalizer-
Status, CollectedPayload/Hash, Candidate, tatsächliche Writerentscheidung,
Writerplan, kanonische Bytes, rohen 32-Byte-Dedupekey und Routebindungsnachweis.
Bei einem Vorstufen-REJECT bleibt `writer_decision=NOT_RUN`; nur die
Gesamtentscheidung ist dann REJECT. Writerablehnungen bleiben sichtbar, keine
Umgehung und kein Retry. Prozess-/Runtimefehler sind kein Importnachweis.
Provenienz ist ein separater Begleitbeleg, keine zusätzliche Observation-Spalte
und kein Bestandteil eines veränderten v2-Dedupevertrags.

Vom Repository aus verwendbar:

```python
from scripts.market_collector.collector import FixtureTransport
from scripts.market_collector.normalizer import pipeline, writer
from scripts.market_collector.yahoo_chart import YahooChartSnapshotV1

# request, qualified_route und frozen_response explizit aus freigegebenen
# synthetischen Inputs bilden; vollständige Beispiele in test_market_collector_v1.py.
result = pipeline(request, qualified_route,
    FixtureTransport({request: frozen_response}), [YahooChartSnapshotV1()],
    catalog=writer.observation.catalog_module.normative_catalog(),
    created_at=frozen_insert_timestamp, existing=existing_snapshot)
```

Die vorhandene lokale PHP-Runtime bleibt Voraussetzung der wiederverwendeten
Phase-3N-Wertprüfung. Der neue Collector liefert keinen SQL-Executor.

## Offline-Nachweis und Kostenbegrenzung

Zwei eingefrorene, ausschließlich synthetische JSON-Fixtures: EUR und GBX.
Die EUR-Fixture enthält bewusst zusätzlich OHLCV-/Volume-Information, die im
Snapshotpfad ignoriert wird. Die GBX-Fixture verwendet GBp; derselbe gezielte
Test prüft zusätzlich GBX. Keine B8-Originalwerte oder privaten Identifier.

Gezielter Testblock: `python -m unittest discover -s tests -p test_market_collector_v1.py -v`.
Erster Lauf: **19/19 erfolgreich**, keine Testfehler und keine zusätzlichen
Retests oder Testausweitungen wegen eines Fehlers.
Geprüft werden Bytegenauigkeit/Immutabilität, Payloadintegrität, EUR/GBX bis zum
echten Writer, getrennte Zeiten/Provenienz, native Dezimal-/große Ganzzahlpreise,
NULL-Volume, erforderliche Ablehnungen, generische Adapter-/Katalogbindung und
der fehlende eingebaute Netzwerk-/DB-Zugriff. Keine erneuten separaten
Schema-/Unit-/Writer-Grundlagen-/Rollback-/Homepage-/Performanceläufe.

Vor Abschluss genau eine volle lokale Regression, danach Validate und Diff-Check.
Ergebnis dieses einen lokalen Vollruns: **418/419**, ausschließlich die bekannte
Windows-Abweichung `budget_not_private`. Validator (drei Webdateien) und
Diff-Check bestanden. Keine nachträgliche Codekorrektur, zusätzliche gezielte
Fehlerprüfung oder zweite Vollregression erforderlich. Die Deploymentmeldung
der bestehenden Testsuite stammt aus einem Mocktest, keinem echten Upload.
Genau ein Linux-Workflow auf dem exakten Abschlusscommit, auf temporärem
Nicht-main-Branch mit Produktionsdeploy skipped. Ergebnisse, Laufzahlen, Commit
und Run-ID in Issue #34; anschließend Prüfbranch löschen. Kein PHP geändert.

## Ein echter PNE-Snapshot read-only – Issue #36

Ausgangspunkt `04d74b7a095723903b044bb47d8881f1849a6067`.
**Genau ein** externer Börse-Frankfurt-price_information-GET für **PNE AG**,
keine Yahoo-Abfrage und kein Retry. Vorher vorhandene MOSA-Evidenz geprüft:
die freigegebene, gesicherte historische Metadatenassoziation bindet die vom
Nutzer angegebene öffentliche ISIN exakt an PNE AG. Keine Discovery/Heuristik.
Request/MIC XFRA/EUR und deterministische Headerbildung stammen ausschließlich
aus dem bereits gebundenen historischen Frankfurtvertrag. Header und interne
Hilfswerte werden weder hier noch im Repository veröffentlicht.

Der minimale allgemeine HTTPS-Transport bindet einen unveränderlichen GET-
Descriptor an genau einen Collector-Request. Er ignoriert authentifizierte
Umgebungsproxies, verwendet keine Cookies, Auth-Handler oder Sessionpersistenz
und folgt keiner Weiterleitung, auch nicht zur selben Domain. Jeder Fetch
verbraucht die Instanz vor dem Öffnen des Requests; Netzwerk-/HTTPfehler lösen
keinen zweiten Versuch aus. Technische Fehlercodes enthalten keine rohen
Diagnosen. Der tatsächliche Einmalabruf wurde zusätzlich durch eine exklusive
private Budgetdatei gegen erneutes Ausführen gesperrt.

| Tatsächlicher Nachweis | Ergebnis |
| --- | --- |
| PNE-Identität / qualifizierter Request vor Abruf | PASS |
| Externe Providerrequests | 1 |
| HTTP / Content-Type | 200 / application/json |
| Originalantwort | 561 unveränderte Bytes; ausschließlich privat gesichert |
| ISIN / XFRA / EUR / Preis / explizite Marktzeit / eindeutiges JSON | PASS |
| Collector | COLLECTED |
| Frankfurtadapter / gemeinsamer Normalizer | jeweils NORMALIZED |
| Echter Phase-3N WriterPlanner | INSERT, Format 2, native EUR-Zahl unverändert, EUR@1 |
| Volume / Mengenbasis / Volumeunit | NULL |
| Persistente Route behauptet | nein |
| DB-Verbindungen / DB-Writes | 0 / 0 |

Requeststart **20.10.2026 10:15:25.317491 UTC**, Responseende/observed_at
**10:15:25.581287 UTC**. Provider-market_at **07:33:17.000000 UTC** desselben
Tages; Markt- und Erfassungszeit bleiben getrennt. Der gelesene Preis ist
fachlich verarbeitbar; daraus folgt keine Zusage über Tickaktualität.
SHA-256 der privat erhaltenen Antwortbytes:
`73df054a69cf1d78ff086f1bcdb7c1c929cbd6c7ff9c08afee4bea91ba7fb029`.
Kein Rawpayload oder echter Preiswert im Repository. Native Zahl, Payloadhash
und tatsächliche Erfassungszeit zusätzlich anhand derselben gespeicherten
Antwort mit Candidate/Writerplan abgeglichen, ohne weiteren Netzwerkabruf.

Der Sidecar ist ausdrücklich **NON_PERSISTENT_TEST_ROUTE**: an die verifizierte
PNE-Identity, Frankfurt/XFRA/EUR und EUR@1 gebunden, ohne Mengenbasis/Volumeunit.
Seine ausschließlich lokalen Test-IDs und Revision sind **keine** behaupteten
DB-Identitäten oder existierende Route. Der Plan beweist nur: dieser reale
Providerpayload ist mit dem vorhandenen MOSA-2-v2-Vertrag verarbeitbar. Er
beweist weder eine persistente v2-PNE-Route noch einen DB-Insert.

Neue gezielte Offline-Transporttests: **7/7**, erster Lauf erfolgreich. GET-only,
Bytegenauigkeit/Metadaten, sichere Descriptorbindung, keine Redirects/Cookies/
Credentials/Proxies, einmaliger Erfolg/Fehler/Timeout und keine DB-/Providerlogik.
Kein erneuter separater Yahoo-/Frankfurt-/Writer-/Schema-/Unit-/Rollbacktest.
Die bestehende Offline-Importschutzprüfung grenzt den expliziten neuen HTTP-
Transport aus und verbietet weiterhin seine implizite Nutzung im Core/Adapter.

Homepage: statische Inhalte auf **20. Oktober 2026**, Schwerpunkt Collector &
kontrollierte Live-Daten, zwei offline geprüfte Provideradapter und genau diesen
read-only PNE-Erfolg aktualisiert. Vier Hauptphasen erhalten, Phase 4 Collector &
Datenübernahme; Current/Bars laut letztem qualifiziertem Stand leer, B8 geparkt,
keine Produktivfreigabe. Keine neuen Requests, Assets, CSS-/JS-/Ladestrukturen.
Inhaltsprüfungen und feste Homepagefingerprints entsprechend der ausdrücklich
beauftragten Änderung aktualisiert; v1-/Schema-/CSS-/JS-Schutzwerte unverändert.
Validator und bestehende Regression reichen; kein Performance-/Browserblock.
Der Quellenstand wird mit Deploy skipped abgeschlossen, kein Homepage-Livedeploy.

Genau eine vollständige lokale Regression und genau ein Linux-Vollrun auf dem
Abschlusscommit; endgültige Ergebnisse/Commit/Run-ID in Issue #36. Keine weiteren
Providerrequests. Native Start-/Describe-/Plan-Erfassung jeweils einmal regulär
versucht, weiterhin Promptbeleg-/Laboridentitätsfehler; keine erfundenen Ereignisse.
Lokaler Vollrun: **434/435**, ausschließlich bekanntes Windows-
`budget_not_private`. Validate und Diff-Check erfolgreich; alle aktualisierten
Homepage- und Transportschutzprüfungen bestanden. Keine Fehler-Retests,
Codekorrekturen nach Abschlussregression oder zusätzlichen Vollruns.

## Nächste Grenze

Keine Freigabe für DB-Persistenz, Last-/Parallelbetrieb, breitere Instrumentlisten,
Scheduler, Current/Bars, FX, B8 oder Produktion. Kein Browser, Dogado/Plesk,
Gateway oder Passwort verwendet. Ein kontrollierter Test-DB-Insert wäre ein
eigener neuer Auftrag mit ausdrücklicher Freigabe. Hier nicht ausgeführt.

Native Registrierung scheitert an `PROMPT_RECEIPT_MISSING`; Describe und Plan
jeweils einmal regulär versucht, ungültige Laboridentität. Keine IDs/Zeiten oder
Ereignisse erfunden und keine wiederholten Bindungsversuche. Fachlichen
Offline-Nachweis und diese separate Erfassungslücke nicht gleichsetzen.

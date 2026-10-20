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
Homepage, Migrationen und bestehende Phase-3N-/Unitmodule unverändert.

## Architektur und Verantwortungen

`FixtureTransport → Collector → Provideradapter → gemeinsamer Normalizer → Phase-3N WriterPlanner`

| Modul | Aufgabe |
| --- | --- |
| `scripts/market_collector/contracts.py` | Unveränderliche Requests, Responses, Payloads, qualifizierte Routensidecars und native Candidates; Transport-/Adapterprotokolle |
| `collector.py` | Request validieren, registrierten Adapter auswählen, Responsebytes und Transportmetadaten übernehmen, exakten Payloadhash bilden |
| `yahoo_chart.py` | Nur Yahoo-Chart-Snapshot v1: JSON, Symbol, native Providerunit und Unix-Marktzeit interpretieren |
| `normalizer.py` | Providerneutral IDs/Route/Units/Provenienz prüfen, Raw-Observation erzeugen und an den vorhandenen Writer übergeben |

Der Collector kennt keine Preise, Währungen, Units oder Yahoo-Feldnamen.
Provideradapter werden über ihren versionierten Schlüssel registriert; keine
Providerverzweigung im Core. Doppelte/fehlende Adapter und fehlende Fixture-
Requests werden abgewiesen. Keine automatische Discovery oder Ersatzquelle.

Die Schnittstellen `Transport.fetch(Request) -> TransportResponse` und
`ProviderAdapter.normalize(CollectedPayload, RouteContract) -> ObservationCandidate`
erlauben später einen getrennt freizugebenden Transport. Aktuell wird ausschließlich
`FixtureTransport` geliefert und verwendet. Kein HTTPTransport, URL-Builder,
Retry, Scheduler, Credentialszugriff oder Live-Fallback implementiert. Zusätzliche
eingespeiste Transport-/Adapterimplementierungen wären eigener vertrauenswürdiger
Code und sind durch diesen Auftrag nicht qualifiziert.

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
GBX-/Yahoo-Sonderregel. Ein synthetischer zweiter Adapter mit POINT belegt diese
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

## Nächste Live-Grenze

Bewiesen wird ausschließlich die Offlinekette mit synthetischen Inputs und
Planentscheidungen. Keine aktuelle Providerkompatibilität, kein Live-Collector,
DB-Insert, Last-/Parallelbetrieb oder freigegebener produktiver Transport.
Netzwerk-/DB-Zugriffe 0; kein Browser, Dogado/Plesk, Gateway, Passwort,
Scheduler, Schema-/Ledger-/Current-/Bars-Write, B8-Import oder Produktion.

Nächster eigener kompakter Auftrag: genau ein qualifiziertes Testasset, ein
Provider, kontrollierter read-only Providerabruf ohne DB-Write; originale Payload
über Adapter/Normalizer bis zum Writerplan vergleichen. Nicht hier ausgeführt.

Native Registrierung scheitert an `PROMPT_RECEIPT_MISSING`; Describe und Plan
jeweils einmal regulär versucht, ungültige Laboridentität. Keine IDs/Zeiten oder
Ereignisse erfunden und keine wiederholten Bindungsversuche. Fachlichen
Offline-Nachweis und diese separate Erfassungslücke nicht gleichsetzen.

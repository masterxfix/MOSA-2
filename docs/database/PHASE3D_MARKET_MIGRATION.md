# MOSA 2 – Phase 3D: kontrollierte Übernahme vorhandener MOSA-Marktdaten

**Status:** Phase 3D-G: 8/8 ursprünglich transformierbare Observations importiert. Phase 3H: acht Restfälle weiterhin gesperrt. Phase 3I: allgemeiner versionierter Unit-/Quantity-Vertrag entschieden; nur logischer Zielentwurf, keine Schemaänderung oder weitere Übernahme. Gesamtmigration weiterhin offen. [Unit-Vertrag](PHASE3I_UNIT_CONTRACT.md).
**Grundlage:** Phase 3C-B am 19.10.2026 erfolgreich abgeschlossen; 16 Tabellen, Ledger v1+v2, alle 15 Nicht-Ledger-Tabellen leer  
**Ziel:** Vorhandene wertvolle MOSA-Marktdaten kontrolliert, nachvollziehbar und wiederholbar auf das MOSA-2-Modell abbilden, ohne 1:1-Altdatenkopie, Dual Write oder Provider-Sonderlogik.

## Grundprinzip

MOSA bleibt Quelle und wird ausschließlich **read-only** gelesen. MOSA 2 bleibt die saubere Zielarchitektur.

Die Übernahme erfolgt in klar getrennten Stufen:

1. Quelle inventarisieren.
2. Feld- und Identitätsmapping definieren.
3. Transformation/Dedupe offline bzw. in Dry-Run prüfen.
4. Kleine kontrollierte Stichprobe auf der isolierten Testdatenbank importieren.
5. Ergebnis fachlich gegen die Quelle vergleichen.
6. Erst danach größere Pakete mit Checkpoints planen.

## Nicht Teil von Phase 3D-A

- keine Schreibzugriffe auf MOSA;
- keine Änderung an `masterxfix/fixlab`;
- keine echten Daten in MOSA 2 schreiben;
- kein produktiver Collector;
- kein Scheduler;
- kein Dual Write;
- kein Produktionsdeployment;
- keine Depot-, News-, KI- oder Prognosedaten.

## Phase 3D-A – Source-Inventar und Mapping

Phase 3D-A ist rein analysierend.

Ergebnisstand 19.10.2026:

- [Quelleninventar](PHASE3D_SOURCE_INVENTORY.md), fixlab-Quellcode auf
  `baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c` schreibgeschützt untersucht;
- [Feldmapping und Dry-Run-Vertrag](PHASE3D_FIELD_MAPPING.md), alle Attribute
  der sieben vorhandenen Zieltabellen einschließlich Quellfeldklassifikation;
- belegt: L&S-/Tradegate-Live-Offerten, Yahoo-Chart-/Heimatmarkt-/FX-Daten,
  L&S-Chartpunkte, Frankfurt-Referenz-/Historywerte, Marktindikatoren und
  NEL-JSON-Stände; angrenzende Kraftstoffpreis-History ausdrücklich abgegrenzt;
- Persistenzverträge: sechs gemeinsame SQL-Tabellen sowie Quellen-/Identitäts-
  und NEL-Intraday-JSON; tatsächliche aktuelle Datenbestände hier nicht gelesen;
- offene Sperren: reale Identifier-/Route-Zuordnung, lokale Altzeiten/DST,
  fehlende Barintervalle/-Endzeiten, Adjustierung/Revisionsregeln, GBX/XXX und
  Einheiten, FX-Provenienz und ausdrückliche Current-Routenauswahl;
- keine Quelländerung, keine DB-Aktion, kein Provider-Fetch, keine Übernahme.

3D-A beschreibt das reproduzierbare Format und seine Ablehnungsregeln; es
implementiert keinen Reader, Dry-Run-Executor oder Importer. 3D-B bleibt separat
freizugeben und darf diese offenen Fälle nicht stillschweigend übergehen.

Zu erfassen sind mindestens:

- welche aktuellen MOSA-Marktdatenquellen fachlich tatsächlich genutzt werden;
- welche Tabellen/Dateien/API-normalisierten Strukturen die persistierten Marktwerte und Historien liefern;
- welche Felder fachlich relevant sind;
- Zeitsemantik (Marktzeit, Erfassungszeit, Zeitzone);
- Währung;
- Preis/Bid/Ask/Volumen;
- Asset-Identität (ISIN, Ticker, Börsenplatz, providerbezogene Kennung);
- Source-/Route-Zuordnung;
- vorhandene Dubletten-/Unique-Regeln;
- bekannte Lücken oder Sonderfälle im Altbestand.

Ergebnis ist ein explizites Mapping nach:

- `m2_assets`
- `m2_asset_identifiers`
- `m2_sources`
- `m2_asset_source_routes`
- `m2_market_observations`
- `m2_market_bars`
- `m2_market_current`

## Kein 1:1-Mapping

Technische Altspalten werden nicht automatisch übernommen.

Jedes Quellfeld erhält genau eine Einordnung:

- **übernehmen** – fachlich notwendig;
- **ableiten** – deterministisch aus anderen Feldern erzeugbar;
- **verwerfen** – technischer Altballast;
- **offen** – fachliche Entscheidung erforderlich.

Providerbezogene IDs bleiben in der vorhandenen MOSA-2-Source/Route-Struktur und führen nicht zu providerbezogenen Markttabellen.

## Identitäten

Vor jeder späteren Datenübernahme muss ein Quellobjekt deterministisch auf genau ein MOSA-2-Asset abbildbar sein.

Bevorzugte Reihenfolge:

1. stabile externe Kennung wie ISIN, sofern vorhanden und fachlich passend;
2. bereits definierte MOSA-2-Identifier;
3. explizite Source-/Route-Zuordnung.

Ticker allein ist keine universelle Identität.

Uneindeutige Fälle werden nicht automatisch importiert.

## Zeitmodell

Alle Zielzeiten bleiben UTC.

Für jedes Quellfeld ist explizit festzulegen, ob es:

- `market_at`
- `observed_at`
- `starts_at`
- `ends_at`

entspricht.

Lokale Zeiten ohne eindeutig bekannte Zeitzone dürfen nicht stillschweigend als UTC übernommen werden.

## Dedupe

Für punktuelle History muss exakt der in Phase 3C validierte zentrale kanonische Observation-Vertrag verwendet werden.

Keine zweite Migrations-Dedupe-Logik.

Für Bars bleibt die eindeutige Zielidentität:

`asset_id + route_id + interval_key + starts_at`

## Current

Current wird nicht blind aus einem Quell-"current"-Datensatz kopiert.

Der spätere Import muss Current deterministisch aus den fachlich gültigen, ausgewählten Daten erzeugen bzw. nach demselben Phase-3C-Zeitvertrag aktualisieren.

Keine Cross-Source-Arbitration erfinden, bevor eine explizite Regel dafür beschlossen ist.

## Dry-Run-Ausgabe

Phase 3D-A soll bereits ein Format für einen späteren Dry Run definieren.

Mindestens je Quellobjekt/-zeile:

- Quellreferenz ohne Secret;
- erkannte Asset-Identität;
- erkannte Source/Route;
- Zieltyp Observation/Bar/Current-relevant;
- normalisierte Werte;
- Dedupe-/Bar-Identität;
- Aktion: insert / duplicate / reject / unresolved;
- Grund bei reject/unresolved.

Keine Secrets oder privaten Zugangsdaten in Reports.

## Qualitätsregeln

Vor einem echten Import müssen mindestens prüfbar sein:

- Quellanzahl;
- erfolgreich gemappte Anzahl;
- ungelöste Identitäten;
- verworfene Datensätze nach Grund;
- erwartete neue Observations;
- erwartete Dubletten;
- erwartete Bars;
- Zeitbereich min/max;
- Währungen;
- Assets/Sources/Routes betroffen.

Summen müssen reproduzierbar sein.

## Phase 3D-B – kleine echte Read-only-Stichprobe

Separat freigegebene Stichprobe vom 19.10.2026: 16 Objekte, SELECT-only;
erneute feste Auswahl bytegleich. Keine MOSA-2-DB-Verbindung. Private Manifest-
und Reportdateien bleiben außerhalb des Repositories. Zwei Offline-Läufe
bytegleich; reale GBX-/XXX-/FX-/Bar-Sperren und Current-Auswahl bleiben explizit.
Details, Zähler und Beweisgrenzen: [PHASE3D_SAMPLE_RESULTS.md](PHASE3D_SAMPLE_RESULTS.md).

Der generische Evaluator liegt in `scripts/phase3d/dry_run.php`; seine
Eingabe sind bereits extrahierte Zeilen mit geprüften Evidence-Annotationen.
Er besitzt keinen Quellreader oder DB-Adapter und behauptet ohne Zielvergleich
keinen insert/duplicate. Vorgeschlagene Schlüssel ersetzen keine realen IDs;
der echte Phase-3C-Dedupe-Key bleibt bis zu bestätigten IDs null.

- MOSA ausschließlich read-only lesen;
- kleine explizit begrenzte Stichprobe;
- noch keine Ziel-DB-Schreibvorgänge;
- Transformation und Dry-Run erzeugen;
- fachliche Vergleichstabelle Quelle ↔ Zielabbildung;
- offene Identitäts-/Zeit-/Währungsfragen klären.

## Phase 3D-C – kleiner Testimport

Erst nach erfolgreichem 3D-B und separater Freigabe.

- isolierte MOSA-2-Testdatenbank;
- kleine kontrollierte echte Datenmenge;
- wiederholbar/idempotent;
- Checkpoint;
- Postcheck;
- Vergleich Quelle ↔ Ziel;
- kein Produktionsimport.

## Erfolgskriterium 3D-A

Phase 3D-A ist abgeschlossen, wenn die vorhandenen MOSA-Marktdatenquellen und relevanten Felder vollständig genug inventarisiert sind, ein eindeutiges Zielmapping existiert, offene Fälle explizit markiert sind und ein reproduzierbarer Dry-Run-Vertrag für 3D-B feststeht – ohne irgendeine echte Datenübernahme.

## Phase 3D-C – ausgeführter Testimport am 19.10.2026

Die separat freigegebene feste Auswahl A1/A2/A3 ist nach read-only belegter
Stammdatenauflösung erfolgreich übernommen: 3 native Observations, 2 Assets,
2 Sources, 3 Routes, 2 Identifier und 2 Checkpoints; genau 1 NOK- und 2 EUR-Fälle.
Identischer Replay: 0 neue Zeilen in allen sieben erlaubten Tabellen.
Zwei unabhängige Readbacks bestätigen identische Werte und Zeitstempel;
Current/Bars bleiben 0, Ledger v1+v2 unverändert. Keine Defaults, keine Produktion.
Private Snapshot-/Manifest-/Reportdateien und reale Identitäten bleiben privat.
Details: [PHASE3D_TEST_IMPORT_RESULTS.md](PHASE3D_TEST_IMPORT_RESULTS.md).
Weitere Migrationen benötigen eigene kleine geprüfte Pakete und Freigaben.

## Phase 3D-D – Paket 2 vorbereitet

Fünf feste Restkandidaten geprüft: fünf eindeutige aktive Portfolio-Namen,
fünf passende gültige Frankfurt-Registrierungen. Der bestehende produktive
Live-Quote-Assetvertrag klassifiziert diese als `stock`; die explizite
Zielabbildung ist `equity`. Keine passende ETF-Referenz, keine Konflikte.
Die frühere negative Prüfung von `fixlab_assets` wurde nicht wiederholt.

Deterministisch ausgewählt: drei Observations, drei neue Assets, eine bestehende
und eine neue Source, drei neue Routes. Die zwei weiteren geeigneten Kandidaten
bleiben wegen der Paketgrenze zurückgestellt. Planung ausschließlich gegen den
privaten, verifizierten Phase-3D-C-Zielreport; keine aktuelle Ziel-DB-Abfrage.
Alle neuen IDs und endgültigen Dedupe-Keys bleiben null. Kein Import, kein
Checkpoint, kein Current/Bars, keine Produktion. Ein späterer Import benötigt
eine eigene Freigabe und echte Katalogauflösung. Details: [Paketplan](PHASE3D_NEXT_BATCH.md).

## Phase 3D-E – Paket 2 persistent übernommen

Drei unveränderte vorbereitete Observations erfolgreich importiert: drei neue
Assets/Identifier, eine neue und eine bestehende Source, drei neue Routes und
zwei neue Checkpoints im allgemeinen Stream `phase3d_market_migration_v1`.
Gesamt: fünf Assets/Identifier, drei Sources, sechs Routes, sechs Observations,
vier Checkpoints. Die zwei Paket-1-Checkpoints und alle bisherigen Fachwerte und
Zeitstempel sind unverändert. Finale Dedupe-Keys erst mit echten erzeugten IDs.
Zwei unabhängige Readbacks und identischer Replay mit überall null neuen Zeilen.
Current/Bars weiterhin leer, Ledger v1+v2 und Struktur unverändert. Keine Produktion.
Details und Aussagegrenzen: [Paket-2-Ergebnisse](PHASE3D_BATCH2_IMPORT_RESULTS.md).

## Phase 3D-F – Paket 3 vorbereitet

Exakt die zwei in Phase 3D-D nur wegen der Paketgrenze zurückgestellten Kandidaten
mit unveränderter privater Evidence reproduziert und gegen den bestätigten
Phase-3D-E-Abschlussreport geplant. Beide geeignet: zwei neue Equity-Assets und
Identifier, eine neue Source, zwei neue Routes; keine bestehenden Katalogobjekte
wiederzuverwenden. Finale IDs und Dedupe-Keys bleiben bis zur echten Auflösung null.
Geplant wäre ein neuer Checkpoint für die neue Source im allgemeinen Stream
`phase3d_market_migration_v1`; bestehende Checkpoints sind nicht betroffen.

Kein DB-Zugriff, keine Live-Quelle, kein Browser/Dogado, kein Import oder
Checkpoint-Write. Homepage und Ladezeitanzeige unverändert, kein Deployment.
Die sechs importierten Fälle bleiben ausgeschlossen; die acht ursprünglich
gesperrten Fälle bleiben gesperrt. Paket 3 ist nur vorbereitet: Die ursprüngliche
transformierbare Stichprobe ist noch nicht vollständig migriert. Ein späterer
Import benötigt ein eigenes Issue und eine separate ausdrückliche Freigabe.
Details: [Paket-3-Plan](PHASE3D_BATCH3_PLAN.md).

## Phase 3D-G – Paket 3 persistent übernommen

Exakt die beiden eingefrorenen Observations erfolgreich importiert: zwei neue
Assets/Identifier, eine neue Source, zwei neue Routes und ein neuer Checkpoint im
bestehenden allgemeinen Migrationsstream. Gesamt sieben Assets/Identifier, vier
Sources, acht Routes, acht Observations und fünf Checkpoints. Paket 1/2 und alle
vier bisherigen Checkpoints unverändert; Current/Bars null, Ledger v1+v2 und
Struktur unverändert. Finale Dedupe-Keys mit echten IDs privat vollständig belegt.
Zwei unabhängige Readbacks, identischer Replay überall null neu, keine UPDATEs.

8/8 ursprünglich transformierbare Observations der kontrollierten Stichprobe sind
übernommen. Die ursprünglichen acht gesperrten Fälle bleiben ausgeschlossen;
keine Aussage einer vollständigen MOSA-Historien- oder Gesamtmarktdatenmigration.
Keine Produktion. [Paket-3-Ergebnisse](PHASE3D_BATCH3_IMPORT_RESULTS.md).

## Phase 3H – ausschließlich die acht gesperrten Fälle untersucht

Die exakt acht verbleibenden Kandidaten der ursprünglichen 16er-Stichprobe
anhand unveränderter Snapshot-/Dry-Run-Fingerprints reproduziert. Die bereits
importierten 8/8 Fälle aus den drei Paketen sind ausgeschlossen und werden
nicht erneut analysiert. Familien überlappen: drei GBX-Fälle enthalten zugleich
die beiden OHLCV-Barfälle; Reason-Summen sind keine Kandidatensummen.

Eine Hauptklassifikation je Fall: sechs TARGET_CONTRACT_REQUIRED, zwei bewusst
OUT_OF_SCOPE; jeweils null EXISTING_EVIDENCE_RESOLVABLE,
READONLY_EVIDENCE_REQUIRED und CONFLICT. Die sechs Vertragsfälle benötigen
zusätzlich gezielte spätere Evidenz, werden deshalb aber nicht doppelt gezählt.
Allgemeiner Unit-/Quantity-Vertrag zuerst, danach getrennte Bar-/FX-Provenienz-
und Indikatorverträge; zwei Future-Referenzen außerhalb der aktuellen
Investment-Quote-Migration geparkt. Native/FX/Derived, Preiseinheit und Current-
Routenauswahl bleiben getrennt. Schemaerweiterung teilweise voraussichtlich nötig,
aber keine Migration 0003 und keine Implementierung.

Keine weitere Übernahme, keine DB-/Browser-/Provideraktion oder Deployment.
Homepage/Ladezeit unverändert, keine Produktion. Alle acht bleiben gesperrt;
die Gesamtmigration ist weiterhin offen. [Einzelmatrix und universelle
Auflösungsstrategie](PHASE3H_BLOCKED_CASES.md).

## Phase 3I – allgemeiner Unit-/Quantity-Vertrag entschieden

Variante C: native Zahl + explizite unveränderliche Unitversion mit Basisdimension,
Geldwährung soweit vorhanden und exaktem rationalem Skalierungsvertrag. B8 behält
seine native GBX-Zahl; currency beschreibt GBP, Quote-Unit GBX und Faktor 1/100
sind ausdrücklich getrennt. GBP ist nur eine deterministische Projektion derselben
Tatsache, keine zweite native History-Zeile oder künstliche Route.

Ein minimaler allgemeiner Unitkatalog, Route-/Datensatzbindung und explizite
Routenrevisionen sind vorgesehen. Physische Route-ID bindet unveränderliche Unit-
Semantik; Unitwechsel braucht neue ID und später kontrolliert erweiterte Routen-
UNIQUEs. Unitinformationen gehören nicht in external_key oder Provider-Sonderfelder.
Current übernimmt die native Unitbindung seiner Observation. Bars teilen einen
Quote-Vertrag über OHLC, Volumen bleibt separat. B6/B7 können denselben Unitvertrag
nutzen; ihre Intervall-/End-/Adjustment-Sperren bleiben bestehen. B5 kann POINT
ohne Geldwährung ausdrücken; Indexidentität bleibt offen. Mengenbasis ist optional
konzeptionell vorgesehen, ohne Futures in Scope zu nehmen.

mosa2-observation-v1 und alle bisherigen Zeilen/Keys bleiben unverändert.
Vorgeschlagenes v2 bindet Unitkey/-version, Unitvertrag sowie explizite optionale
Mengenbasis und Volumeneinheit. Versionierter Legacy-Lesemantel mit 1/1 nur für
bereits qualifizierte einfache monetäre v1-Zeilen, kein Backfill/Reimport.

Additive fachliche Schemaerweiterung nötig; ausschließlich logischer Entwurf,
keine Migration 0003 oder Implementierung. B8 ist fachlich modellierbar, aber noch
nicht importierbar: Schema-/Writer-/Evidenzschritte benötigen eigene Freigaben.
Keine DB-/Browser-/Provideraktion, kein Import/Deployment, Homepage/Ladezeit
unverändert, keine Produktion. [Entscheidung und Migrationsgrenzen](PHASE3I_UNIT_CONTRACT.md).

# MOSA 2 – Phase 3D: kontrollierte Übernahme vorhandener MOSA-Marktdaten

**Status:** Phase 3D-G: 8/8 ursprünglich transformierbare Observations importiert. Phase 3H: acht Restfälle weiterhin gesperrt. Phase 3I: allgemeiner versionierter Unit-/Quantity-Vertrag entschieden; nur logischer Zielentwurf, keine Schemaänderung oder weitere Übernahme. Gesamtmigration weiterhin offen. [Unit-Vertrag](PHASE3I_UNIT_CONTRACT.md).
**Grundlage:** Phase 3C-B am 19.10.2026 erfolgreich abgeschlossen; 16 Tabellen, Ledger v1+v2, alle 15 Nicht-Ledger-Tabellen leer  
**Ziel:** Vorhandene wertvolle MOSA-Marktdaten kontrolliert, nachvollziehbar und wiederholbar auf das MOSA-2-Modell abbilden, ohne 1:1-Altdatenkopie, Dual Write oder Provider-Sonderlogik.

**Aktueller Schemahinweis Phase 3K (19.10.2026):** Migration 0003 vollständig
live validiert, Ledger v3 und zwei unabhängige Final-Readbacks bestätigt.
17 Tabellen, 186 Spalten, 17 PK, 10 zusätzliche UNIQUEs, 39 weitere Indizes,
36 FKs, 37 CHECKs. Die acht bestehenden Observations einschließlich Dedupe-Keys
und übrigen Fachdaten sind gegenüber dem Original-Pre-State unverändert.
Units 0, Routes 8/revision 1, Checkpoints 5, Current/Bars 0.
Keine weiteren Imports, Unit-Seeds oder Writer-v2; die übrigen fachlichen
Sperren bleiben bestehen. [Phase-3K-Nachweis](PHASE3K_UNIT_SCHEMA_LIVE.md).

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

## Phase 3J – Unit-Schema 0003 ausschließlich offline implementiert

[Migration 0003](migrations/0003_market_units.sql) ergänzt repositoryseitig genau
`m2_units`, positive Routenrevisionen mit revision-aware UNIQUEs sowie explizite
Quote-/Quantity-/Volume-FKs auf Routes, Observations, Current und Bars.
Currency ist für unit-aware Fakten nullable; lokale CHECKs erhalten Legacy mit
Pflichtwährung und vollständig NULL bleibenden neuen Feldern. Vorhandenes
Legacyvolumen bleibt zulässig. Observation-v1 und Dedupe unverändert.

Kein Apply, Ledgerwrite, Seed, Writer-v2, Import oder DB-Zugriff. Späteres Ziel
17 Tabellen / Ledger v3; historisch dokumentierter Teststand weiterhin
16 Tabellen / Ledger v1+v2 / acht Observations, hier nicht live geprüft.
B8 benötigt weiterhin freigegebenen Apply, qualifizierte Seeds, Writer-v2 und
spezifische Identitäts-/Evidenzprüfung. B5/B6/B7 behalten ihre weiteren Sperren;
alle acht bleiben gesperrt. Homepage/Ladezeit unverändert, kein Deployment,
keine Produktion. Späterer Apply braucht eigenes Issue und ausdrückliche Freigabe.
[Physischer Vertrag, Offline-Beweisgrenzen und Preflight](PHASE3J_UNIT_SCHEMA.md).

## Phase 3L – normative Unit-Definitionen repositoryseitig vorbereitet

EUR@1, GBP@1, POINT@1 und GBX@1 liegen als deterministisches providerneutrales
[Seed-Manifest](seeds/0001_market_units_v1.json) mit generischer Offline-Validierung,
Definition-SHA-256 und separatem Paketfingerprint vor. Direkte Basen: EUR→EUR,
GBP→GBP, POINT→POINT, GBX→GBP; Faktoren 1/1 beziehungsweise exakt 1/100.
Geldwährung EUR/GBP beziehungsweise NULL bei POINT; keine Floatrechnung.

Dokumentarische Grundlage ist der bestätigte Phase-3K-Stand: Schema 3 / 17 Tabellen /
Ledger v3 / Units leer / acht unveränderte Observations / Current und Bars 0.
In Phase 3L keine DB-Verbindung oder erneute Live-Prüfung, keine Seeds live,
kein Writer-v2 und kein B8-Import. B8 bleibt gesperrt. Migration 0003,
Observation-v1 und Homepage unverändert; kein Deployment, keine Produktion.
Der kontrollierte Seed-Insert einschließlich praktischem Self-FK-Precheck
benötigt eine eigene ausdrückliche Freigabe.
[Kanonische Definitionen, Fingerprint und Beweisgrenzen](PHASE3L_UNIT_SEEDS.md).

## Phase 3M – Live-Preflight gestoppt, keine Unit-Seeds geschrieben

Das freigegebene Phase-3L-Paket wurde erneut offline validiert. Der geschützte
einmalige Testlauf stoppte vor Self-FK-Probe und normativem Insert mit
`auto_increments_changed`: AUTO_INCREMENT-Metadaten weichen vom eingefrorenen
privaten Phase-3K-Abschlussbeleg ab. Keine weitere DB-Diagnose, Reparatur oder
Wiederholung. Keine Seeds, Updates oder Ledgerwrites. Readbacks und Replay
wurden nicht live erreicht; vollständiger Endzustandsnachweis bleibt offen.

Gateway/temporäre Quellen/Zugangskonfiguration/Lock entfernt, Gateway 404 und
Homepage ohne Auth 401 bestätigt. Homepage unverändert. Issue #29 bleibt offen;
kein Erfolgscommit, kein Writer-v2, kein B8-Import, keine Produktion.
[Tatsächlicher Stopp und Nachweisgrenzen](PHASE3M_UNIT_SEEDS_LIVE.md).

Die ausdrücklich autorisierte Fortsetzung erfasste anschließend einmalig einen
Read-only-Snapshot. Rows/PKs/Hashes, Ledger v1/v2/v3 und Struktur sind identisch,
Units weiterhin 0. Bei 10 von 12 Tabellen weichen Zählermetadaten ab; die
technische Bedingung AUTO_INCREMENT > MAX(PK) ist jedoch nicht durchgehend
belegt (`counter_not_above_max`). Klassifikation: **EVIDENCE_INSUFFICIENT**.
Deshalb erneuter Stopp vor Guardfix, Self-FK und Seeds; kein Counter-Reset,
keine Wiederholung oder DB-Reparatur. 33/33 gezielte Diagnosetests bestanden.
Alle 17 temporären Quellen und Zugang entfernt; Gateway 404 / Schutz 401.
Kein Abschlusscommit oder Linux-Lauf; Issue #29 bleibt offen.

## Phase 3M – abschließend erfolgreich

Die zusätzliche AUTO_INCREMENT-vs-MAX(PK)-Bedingung ist gemäß dem bestehenden
Phase-3C-Vertrag entfernt. Korrigierte Klassifikation: CHECKER_BASELINE_BUG mit
METADATA_ONLY_DRIFT (10/12 historische Zähler), kein Counter-Reset oder Repair.
Die gemeinsame Logik schützt weiterhin vollständige Rows/PKs/Hashes, Schema,
Grants, Ledger und Units; Readbacks normalisieren nur Zählermetadaten.

Praktischer Self-FK-Test mit vollständigem Rollback und unabhängigem
Empty-Readback bestanden. EUR@1, GBP@1, POINT@1 und GBX@1 exakt in einer
Transaktion nach 4/4-Readback committed: Units 0 → 4. Zwei neue Verbindungen
bestätigten identischen Fachzustand und Definitionhashes; Replay 4/0/0/0 ohne
zweite Insert-Transaktion. Legacydaten einschließlich Dedupe-Keys und Ledger
v1/v2/v3 unverändert; Current/Bars 0. Keine Legacy-Unit-FKs nachgetragen.

34/34 gezielte Tests; Windows-Gesamtsuite 320/321 ausschließlich mit bekanntem
`budget_not_private`, Validator/PHP-Lints/Diff-Prüfung erfolgreich.
15/15 temporäre Quellen und Zugang entfernt; Gateway 404, Schutz 401,
Homepage byteidentisch. Exakter Abschlusscommit und Linux-Run werden in
Issue #29 dokumentiert. Nächster Schritt Phase 3N ist ausschließlich offline
vorbereitet; kein Writer-v2 live, B8-Import oder Produktionsdeploy.

## Phase 3N – Observation-v2 / unit-aware Writer offline implementiert

Allgemeine v2-Normalisierung mit exakt 18 kanonischen Feldern und Domain
`mosa2-observation-v2`, rohe SHA-256-Keys und deterministische Offline-Write-Pläne
implementiert. Gemeinsame Phase-3C-Wertprimitiven und Phase-3L-Katalogvalidierung
wiederverwendet; v1-Code, Homepage und Migrationen byteidentisch. Keine Migration 0004.
Strenge Unit-/Routebindung, expliziter v1-Replay-/v2-Neudaten-Dispatcher,
Duplicate/Conflict und Schutz vor Reimport/Projektion als neue History.

EUR/GBP/GBX/POINT sowie zusätzliche ausschließlich synthetische Quantity- und
Volume-Definitionen offline getestet. 27/27 gezielte Tests einschließlich acht
eingefrorener synthetischer v1-Byte-/Dedupe-Vektoren erfolgreich. Tatsächliche
Live-Zeilen wurden nicht erneut gelesen; v1-Schutz beruht auf byteidentischem
Code und unveränderten Regressionen. Kein Live-Writer-Test, B8-Import,
Current-/Bars-Write, Browser, Provider, DB-Verbindung oder Produktionsdeploy.
[Vertrag, API und Nachweisgrenzen](PHASE3N_OBSERVATION_V2_WRITER.md).
Der spätere Phase-3O-Test in der isolierten DB benötigt neue ausdrückliche Freigabe.

Lokale Gesamtsuite für Phase 3N: 347/348, ausschließlich bekanntes
Windows-`budget_not_private`; alle bisherigen v1-Tests grün. Validator,
PHP-Lint und Diff-Prüfung bestanden. Exakter Abschlusscommit und Linux-Run
werden in Issue #30 dokumentiert; Produktionsdeploy skipped.

## Phase 3O – Observation-v2-Writer kontrolliert live validiert

Der echte Phase-3N-Writer wurde über den späteren FPM-Gatewaypfad vor jeder
synthetischen Testtransaktion erfolgreich mit vier vollständigen Goldenplänen
qualifiziert. Portable Prozesskommunikation, struktureller Countertabellensatz,
Capabilitybindung, zentrale Normalisierung verschachtelter SHOW-CREATE-
Counteroptionen und getrenntes Rollbackreporting sind korrigiert und getestet.

EUR/GBP/GBX/POINT praktisch in genau einer synthetischen Testtransaktion geprüft:
vier INSERTs aus validierten echten Writerplänen, DB-Werte/canonical bytes/rohe
32-Byte-Dedupe-Keys identisch, jeweils Duplicate und Conflict sowie sieben
Rejectfälle ohne zusätzliche Writes. Anschließend vollständiger ROLLBACK.
Zwei neue unabhängige Verbindungen bestätigen unveränderte Legacy-PKs/-Werte/
Dedupe, v1-Marker/Unitfelder NULL, Units 4, Ledger v1/v2/v3, Routes 8,
Observations 8, Checkpoints 5 und Current/Bars 0. Keine synthetischen Rows übrig.

Gateway, Konfiguration, Locks und 27 temporäre Quellen entfernt; Gateway 404,
anonyme Homepage 401 und Homepagebytes unverändert. Lokale Tests 374/375,
ausschließlich bekanntes Windows-budget_not_private; gezielt Phase 3O und 3N
jeweils 27/27, Validate/PHP-Lints/Diff-Check erfolgreich. Abschlusscommit und
exakter Linux-Workflow mit Deploy skipped werden in Issue #31 dokumentiert.
[Chronologischer Nachweis und Grenzen](PHASE3O_OBSERVATION_V2_WRITER_LIVE.md).

Kein B8-Import, Produktionsdeploy oder neue Migration. Als nächster Schritt
ist ausschließlich Phase 3P read-only vorbereitet: Identität, Source, Route,
native GBX-Semantik, Zeit-/Payload-Evidenz und notwendige unit-aware
Routenrevision qualifizieren. Diese B8-Prüfung wurde noch nicht ausgeführt.

## Phase 3P – B8 read-only qualifiziert

Untersuchung abgeschlossen: **READONLY_EVIDENCE_REQUIRED**. Genau B8 anhand der
privaten Phase-3H-Matrix und Originalfingerprints wiedergefunden; historischer
Yahoo-Snapshotvertrag ausschließlich auf fixlab baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c
bestätigt. Native GBX-Zahl, monetäre Basis GBP, getrennte gespeicherte UTC-Markt-/
Erfassungszeiten, NULL-Historyvolume statt unqualifiziertem Tagesvolumen und
passende vorhandene Source qualifiziert. Keine andere Restmenge neu analysiert.

Im hashgebundenen Phase-3O-Finalreadback fehlt ein passender Zielidentifier;
damit sind bestehendes Zielasset, Name/Klasse, konkrete B8-Legacyroute und
tatsächliche nächste Routenrevision nicht qualifiziert. Kein Widerspruch erfunden,
keine neue Identität/Source angelegt. Rawpayload und unabhängiger historischer
Deploymenthash waren im ursprünglichen Snapshot nicht gesichert. Der vollständige
v1-Factvergleich und tatsächliche B8-v2-Plan bleiben offen; nur synthetische
Helpertests verwenden den echten Phase-3N-Writer. Kein INSERT-Plan für B8 behauptet.

Allgemeiner bedingter Vertrag: neue unveränderliche unit-aware Route mit GBX@1,
mosa2-market-unit-v1, NULL-Mengenbasis und NULL-Volumeunit; echte Providerkeys/
Rollenart erhalten, beide revisionsbewussten UNIQUEs prüfen. Keine Legacyroute
mutieren. Zuerst exakt fehlende historische Stammdaten-/Zuordnungsevidenz und
Provenienz beschaffen; kein Import vorbereiten. Currentauswahl bleibt separat.

[Ergebnismatrix, Fingerprintbindung und Grenzen](PHASE3P_B8_QUALIFICATION.md).
DB-Verbindungen/Writes 0, kein Passwort/Gateway, Providerabruf, B8-Import,
fixlab-Write, Schema-/Ledger-/Current-/Bars-Write oder Produktionsdeploy.
Tests, einziger Abschlusscommit und exakter Linux-Run werden in Issue #32
festgehalten; dessen Abschluss bestätigt die Untersuchung, keine Importfreigabe.

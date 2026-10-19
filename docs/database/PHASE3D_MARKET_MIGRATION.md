# MOSA 2 – Phase 3D: kontrollierte Übernahme vorhandener MOSA-Marktdaten

**Status:** Phase 3D-A abgeschlossen; Phase 3D-B mit 16 echten, privat eingefrorenen Read-only-Quellobjekten offline geprüft. Acht fachlich transformierbar, 16 finale Zielaktionen unresolved, keine echten MOSA-Daten übernommen. [Stichprobenbefunde](PHASE3D_SAMPLE_RESULTS.md).
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

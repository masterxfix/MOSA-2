# MOSA 2 – Phase 3D-C: kleiner echter Testimport

**Status:** Separat freigegeben und am 19.10.2026 in der isolierten Testdatenbank erfolgreich ausgeführt; [Ergebnisse](PHASE3D_TEST_IMPORT_RESULTS.md)
**Grundlage:** Phase 3D-B am 19.10.2026 erfolgreich abgeschlossen; reale Read-only-Stichprobe validiert, keine MOSA-2-Schreibaktion  
**Ziel:** Eine sehr kleine, fachlich eindeutig transformierbare Teilmenge echter MOSA-Marktdaten kontrolliert und idempotent in die isolierte MOSA-2-Testdatenbank übernehmen.

## Grundsatz

Phase 3D-C ist der erste echte fachliche Datenimport nach MOSA 2.

Daher gilt:

- ausschließlich isolierte MOSA-2-Testdatenbank;
- Quelle MOSA/fixlab bleibt read-only;
- keine Produktion;
- keine Bars, Derived-/FX-, GBX-, XXX- oder Indikatordaten;
- keine Current-Projektion, solange keine Current-Route ausdrücklich freigegeben ist;
- kein Dual Write;
- kein Collector/Scheduler;
- jeder Import muss wiederholbar und idempotent sein;
- private reale Identitäten bleiben aus dem öffentlichen Repository heraus.

## Importumfang

Der erste Testimport verwendet **genau drei** bereits in Phase 3D-B als fachlich transformierbar bestätigte Observation-Kandidaten.

Deterministische Auswahl aus dem privaten 3D-B-Snapshot:

- ausschließlich Kandidaten mit gültiger, konfliktfreier ISIN;
- ausschließlich native Marktquotes, keine derived_quote;
- mindestens zwei verschiedene Assets;
- mindestens zwei verschiedene Sources;
- wenn im transformierbaren Set vorhanden: genau ein Kandidat mit nativer Nicht-EUR-Währung (bevorzugt der bereits belegte NOK-Fall);
- keine Bar-Kandidaten;
- keine GBX-/XXX-/Indikator-/Future-Fälle;
- keine Kandidaten mit offenen Zeit-, Einheiten- oder FX-Provenienzfragen.

Die konkrete reale Auswahl bleibt privat. Öffentliche Nachweise verwenden nur A1/A2/A3.

## Zielobjekte

Für die drei ausgewählten Kandidaten dürfen nur die fachlich erforderlichen Zielobjekte angelegt werden:

- `m2_entities`
- `m2_assets`
- `m2_asset_identifiers`
- `m2_sources`
- `m2_asset_source_routes`
- `m2_market_observations`
- `m2_sync_checkpoints`

Explizit **nicht** schreiben:

- `m2_market_current`
- `m2_market_bars`
- Relationships, Events, Files, Jobs oder andere Module.

Current bleibt leer, weil Phase 3D-B keine Current-Route freigegeben hat.

## Katalogregeln

### Assets

- neue IDs ausschließlich durch vorhandenes AUTO_INCREMENT;
- Quell-IDs niemals als Ziel-ID kopieren;
- Identität über validierte ISIN;
- ein ISIN-Widerspruch ist fail-closed;
- vorhandenes Asset mit gleicher ISIN wird wiederverwendet, nicht dupliziert.

### Identifiers

Für diesen ersten Import mindestens:

- `identifier_type='isin'`
- `normalized_value` = validierte normalisierte ISIN
- globaler Scope `''`
- genau eine fachlich passende Asset-Zuordnung.

Keine Ticker-Identität ohne Scope erzwingen.

### Sources

Source-Key muss aus dem in Phase 3D-A/B definierten provider-/venuebezogenen Vertrag deterministisch stammen.

Kein Provider-Sonderfeld in Markttabellen.

Existiert derselbe `source_key` bereits, wird er nur bei identischem fachlichem Vertrag wiederverwendet.

### Routes

Route wird deterministisch aus Asset + Source + route_type + external_key aufgelöst.

Beide bestehenden UNIQUE-Verträge müssen respektiert werden.

Konflikt zwischen external_key und Asset/Source/route_type ist reject und stoppt den Import.

Keine NEL-Sonderroute.

## Observation

Die drei Observations verwenden exakt den in Phase 3C validierten Vertrag:

- gleiche Normalisierung;
- gleiche kanonische Darstellung;
- gleicher SHA-256-Dedupe-Key;
- native Währung bleibt erhalten;
- market_at / observed_at aus dem bereits validierten 3D-B-Snapshot;
- keine Float-Roundtrips;
- keine Alt-Hashes übernehmen.

## Current

`m2_market_current` bleibt in Phase 3D-C absichtlich leer.

Reason:

`current_route_unselected`

Dies ist kein Importfehler, sondern die korrekte fail-closed Grenze.

Keine Legacy-`is_selected`-/Fallback-/ETF-/Router-Priorität automatisch übernehmen.

## Checkpoint

Nach erfolgreichem ersten Commit genau ein deterministischer Checkpoint je tatsächlich verwendeter Source in `m2_sync_checkpoints`.

`stream_key` muss stabil und versionsgebunden sein, z. B. `phase3d_market_sample_v1`.

`cursor_value` enthält nur eine nicht geheime deterministische Referenz/Fingerprint auf den eingefrorenen privaten Sample-Stand, keine reale Quellzeile oder Credentials.

Bei identischer Wiederholung:

- vorhandenen identischen Checkpoint nur verifizieren;
- kein unnötiges UPDATE;
- `updated_at` nicht verändern.

## Ablauf

### 1. Private Import-Manifestdatei

Aus dem bereits privat eingefrorenen 3D-B-Snapshot genau die drei freigegebenen Kandidaten ableiten.

Manifest enthält intern:

- private source_reference;
- validierte Identitäts-/Source-/Route-Evidenz;
- normalized observation;
- vorgeschlagene stabile source/route keys;
- Snapshot-/Mapping-Fingerprint.

Manifest bleibt außerhalb Git bzw. git-ignored.

### 2. Preflight

Vor erstem Write:

- exakte isolierte Testdatenbank;
- 16 Tabellen;
- Ledger v1+v2 unverändert;
- vollständiger Schema-/Constraint-Vertrag;
- keine Routinen/Trigger/Events;
- erwartete Grants;
- alle 15 Nicht-Ledger-Tabellen leer.

Bei Abweichung kein Import.

### 3. Erster Import

Eine DB-Transaktion:

1. Sources auflösen/anlegen.
2. Assets anhand ISIN auflösen/anlegen.
3. ISIN-Identifier auflösen/anlegen.
4. Routes auflösen/anlegen.
5. Drei Observations mit Phase-3C-Dedupe schreiben.
6. Checkpoints je verwendeter Source anlegen.
7. exakte Postchecks innerhalb der Transaktion.
8. Commit nur bei vollständigem Erfolg.

### 4. Unabhängiger Readback

Neue Verbindung.

Bestätigen:

- exakt die erwarteten neuen Katalog-/Observation-/Checkpoint-Zeilen;
- `m2_market_current=0`;
- `m2_market_bars=0`;
- alle sonst nicht verwendeten Fachtabellen leer;
- Ledger unverändert;
- keine unbekannten Daten.

### 5. Zweiter identischer Import

Exakt dasselbe private Manifest erneut ausführen.

Erwartung:

- 0 neue Entities;
- 0 neue Assets;
- 0 neue Identifiers;
- 0 neue Sources;
- 0 neue Routes;
- 0 neue Observations;
- 0 neue Checkpoints;
- drei Observation-Replays werden als Dedupe/duplicate erkannt;
- keine bestehenden fachlichen Werte oder `updated_at`-Werte unnötig verändern.

Damit wird echte Idempotenz nachgewiesen.

### 6. Zweiter unabhängiger Readback

Zustand muss fachlich byte-/wertgleich zum Zustand nach dem ersten Import sein, abgesehen von nichtfachlichen DB-Metadaten, die nicht Teil des Vertrags sind.

## Quelle ↔ Ziel-Vergleich

Für A1/A2/A3 privat vollständig und öffentlich anonymisiert prüfen:

- ISIN/Asset-Auflösung;
- Source;
- Route;
- currency;
- market_at;
- observed_at;
- price;
- bid;
- ask;
- volume;
- Dedupe-Key;
- Zielzeile.

Keine privaten Realidentitäten in öffentliche Dokumente.

## Erfolgskriterien

Phase 3D-C ist erfolgreich, wenn:

- exakt drei freigegebene echte Observations importiert wurden;
- nur notwendige Katalogobjekte angelegt wurden;
- Current und Bars leer bleiben;
- Quelle unverändert blieb;
- erster Import vollständig transaktional erfolgreich war;
- zweiter identischer Import 0 neue fachliche Zeilen erzeugt;
- Dedupe/idempotente Katalogauflösung live nachgewiesen ist;
- Checkpoints stabil bleiben;
- unabhängige Postchecks erfolgreich sind;
- Quelle↔Ziel-Vergleich für A1/A2/A3 stimmt;
- keine Produktion berührt wurde.

## Öffentliche Dokumentation

Nach Erfolg:

- `docs/database/PHASE3D_TEST_IMPORT_RESULTS.md`
- `PHASE3D_MARKET_MIGRATION.md` Status aktualisieren.

Nur anonymisierte/aggregierte Werte veröffentlichen.

## Aussagegrenze

Dieser kleine Testimport ist keine Freigabe für:

- Vollmigration;
- große Datenmengen;
- Current-Routenauswahl;
- Bars;
- FX/Derived Quotes;
- GBX/XXX/Indikatoren;
- Parallelbetrieb;
- Produktion.

## Belegte Stammdaten und ausführbarer Vertrag

Die feste Auswahl A1/A2/A3 wurde unverändert aus dem eingefrorenen 3D-B-Snapshot
übernommen. Ergänzt wurden nur belegte fachliche Namen und explizite Assetklassen.
Der Basisreport bleibt als Parent-Fingerprint erhalten; das private Importmanifest
bindet Snapshot, Mapping, Stammdatenquellen und Werte mit SHA-256.

Namensbelege stammen aus exakt passenden Instrument-/Identity-Datensätzen.
Der Typbeleg stammt aus gespeicherten Source-Registry-Werten EQUITY/STOCK;
exakte gültige ETF-Referenzen werden gesondert geprüft. Fehlende, widersprüchliche
oder unbekannte Belege sperren den Import. Keine Defaults oder Providerabfragen.
Die native Quote-Währung setzt keine Asset-Basiswährung: diese bleibt hier NULL.

`scripts/phase3d/import_sample.php` implementiert den begrenzten Importvertrag.
Er prüft beide Route-Identitäten, den vollständigen Katalogvertrag und vorhandene
Dedupe-Payloads. Es gibt keine UPDATEs, Löschungen oder unterdrückten SQL-Fehler.
Reale erzeugte IDs werden innerhalb der ersten Transaktion gebunden; das aufgelöste
Manifest einschließlich kanonischer erwarteter Dedupe-Keys wird vor COMMIT privat
gesichert. Vorher werden keine numerischen Ziel-IDs oder echten Dedupe-Keys erfunden.
Eine exklusive Startmarke verhindert einen erneuten Erstimport. Nach unklarem
Commit-Ausgang gibt es keinen Wiederholungsversuch. Beide Readbacks nutzen neue
Verbindungen; der identische Replay prüft Werte und Zeitstempel unverändert.

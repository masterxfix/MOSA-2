# MOSA 2 – Phase 3: Marktdaten Current + History

**Status:** Phase 3A implementiert und Phase 3B am 19.10.2026 auf der isolierten Testdatenbank erfolgreich live validiert; Phase 3C nicht begonnen
**Grundlage:** Phase 1 Plattform qualifiziert, Phase 2 Core-/Asset-Identität live technisch freigegeben  
**Ziel:** Die erste echte Fachschicht von MOSA 2 aufbauen: aktuelle Marktdaten schnell lesbar halten und historische Marktdaten nachvollziehbar, append-only und skalierbar speichern.

## Scope

Phase 3 umfasst ausschließlich die Marktdaten-Grundschicht:

- aktueller, für normale Seiten vorbereiteter Marktzustand je Asset;
- append-only punktuelle Marktbeobachtungen;
- historische OHLCV-Bars für Charts und zeitbasierte Auswertungen;
- Provenienz über bestehende Sources und Asset-Source-Routes;
- deterministische, indexierte Lesewege;
- idempotent planbare spätere Datenübernahme.

Nicht Teil dieser Phase:

- produktive MOSA-Datenmigration;
- Live-Collector oder Scheduler;
- Depot-/Positionsdaten;
- News;
- KI-Analyse;
- Kursprognosen;
- produktives Deployment.

## Verbindliches Grundprinzip

```text
Quelle / Collector
       ↓
History / nachvollziehbare Fakten
       ↓
Current / vorbereiteter aktueller Zustand
       ↓
Webseite / spätere KI-Kontexte
```

Normale Seiten lesen nicht millionenfach History neu aus. Current und History bleiben strikt getrennt.

## Tabellen

### 1. `m2_market_current`

Genau ein vorbereiteter aktueller Marktzustand je Asset.

| Feld | Typ | Regel |
| --- | --- | --- |
| `asset_id` | BIGINT UNSIGNED | PK, FK → `m2_assets.entity_id` |
| `source_id` | BIGINT UNSIGNED | FK → `m2_sources.id` |
| `route_id` | BIGINT UNSIGNED | FK → `m2_asset_source_routes.id` |
| `currency` | CHAR(3) | ISO-4217, binäre Vergleichssemantik |
| `price` | DECIMAL(28,10) | letzter fachlich gültiger Preis |
| `bid` | DECIMAL(28,10) NULL | optional |
| `ask` | DECIMAL(28,10) NULL | optional |
| `day_open` | DECIMAL(28,10) NULL | optional |
| `day_high` | DECIMAL(28,10) NULL | optional |
| `day_low` | DECIMAL(28,10) NULL | optional |
| `previous_close` | DECIMAL(28,10) NULL | optional |
| `day_volume` | DECIMAL(32,8) NULL | optional, keine Float-Semantik |
| `market_at` | DATETIME(6) | fachlicher Zeitpunkt des Marktwerts |
| `observed_at` | DATETIME(6) | Zeitpunkt der MOSA-2-Erfassung |
| `updated_at` | DATETIME(6) | technische Aktualisierung |

Regeln:

- genau eine Current-Zeile je Asset;
- Current ist austauschbarer, vorbereiteter Zustand, keine Historie;
- `source_id` und `route_id` dokumentieren die aktuell gewählte Provenienz;
- `route_id` muss fachlich zum selben Asset und Source gehören; diese Cross-Table-Regel wird in der Anwendung/Validierung geprüft, nicht durch providerbezogene Sonder-FKs;
- `price > 0`;
- falls Bid und Ask beide gesetzt sind: `bid <= ask`;
- falls Day High/Low beide gesetzt sind: `day_low <= day_high`;
- Current darf nur aktualisiert werden, wenn der eingehende fachliche Marktzeitpunkt nicht älter ist als der gespeicherte Zustand; Gleichstand muss deterministisch behandelt werden.

Geplante Lesewege:

1. Current per `asset_id` über PRIMARY.
2. Optional technische Kontrolle nach `source_id, observed_at`.

Sekundärindex:

- `(source_id, observed_at, asset_id)`

### 2. `m2_market_observations`

Append-only normalisierte Punktbeobachtungen.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `asset_id` | BIGINT UNSIGNED | FK → `m2_assets.entity_id` |
| `source_id` | BIGINT UNSIGNED | FK → `m2_sources.id` |
| `route_id` | BIGINT UNSIGNED | FK → `m2_asset_source_routes.id` |
| `currency` | CHAR(3) | ISO-4217 |
| `price` | DECIMAL(28,10) | > 0 |
| `bid` | DECIMAL(28,10) NULL | |
| `ask` | DECIMAL(28,10) NULL | |
| `volume` | DECIMAL(32,8) NULL | provider-/beobachtungsbezogener Volumenwert |
| `market_at` | DATETIME(6) | fachlicher Marktzeitpunkt |
| `observed_at` | DATETIME(6) | MOSA-2-Erfassungszeitpunkt |
| `dedupe_key` | BINARY(32) | deterministischer SHA-256-Schlüssel der kanonischen Beobachtungsidentität |
| `created_at` | DATETIME(6) | UTC |

Regeln:

- append-only;
- keine nachträgliche Umdeutung alter Beobachtungen;
- `dedupe_key` verhindert Dubletten bei wiederholbarer Migration/Collector-Wiederholung;
- der Dedupe-Schlüssel wird zentral aus stabilen Identitätsfeldern gebildet, nicht pro Asset als Sonderlogik;
- keine großen Provider-Rohpayloads in dieser Tabelle;
- `price > 0`;
- Bid/Ask-Regel wie Current.

Eindeutig:

- `UNIQUE (dedupe_key)`

Geplante Indizes:

- `(asset_id, market_at, id)` für begrenzte Zeitfenster eines Assets;
- `(asset_id, source_id, market_at, id)` für quellenbezogene History;
- `(source_id, observed_at, id)` für Collector-/Migrationskontrolle.

### 3. `m2_market_bars`

Append-only bzw. deterministisch reproduzierbare OHLCV-Zeitintervalle für Charts und Analysen.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `asset_id` | BIGINT UNSIGNED | FK → `m2_assets.entity_id` |
| `source_id` | BIGINT UNSIGNED | FK → `m2_sources.id` |
| `route_id` | BIGINT UNSIGNED | FK → `m2_asset_source_routes.id` |
| `interval_key` | VARCHAR(16) | kanonisch, z. B. `1m`, `5m`, `1h`, `1d` |
| `currency` | CHAR(3) | ISO-4217 |
| `starts_at` | DATETIME(6) | inklusive Intervallstart, UTC |
| `ends_at` | DATETIME(6) | exklusives Intervallende, UTC |
| `open_price` | DECIMAL(28,10) | > 0 |
| `high_price` | DECIMAL(28,10) | > 0 |
| `low_price` | DECIMAL(28,10) | > 0 |
| `close_price` | DECIMAL(28,10) | > 0 |
| `volume` | DECIMAL(32,8) NULL | |
| `trade_count` | BIGINT UNSIGNED NULL | optional |
| `observed_at` | DATETIME(6) | Erfassungs-/Berechnungszeitpunkt |
| `created_at` | DATETIME(6) | UTC |

Regeln:

- `starts_at < ends_at`;
- `low_price <= open_price/close_price/high_price`;
- `high_price >= open_price/close_price/low_price`;
- nur definierte kanonische Intervalle;
- keine ungebundenen Chart-Abfragen ohne Asset, Zeitraum und Limit;
- dieselbe fachliche Bar darf für dieselbe Route und dasselbe Intervall nicht doppelt existieren.

Eindeutig:

- `UNIQUE (asset_id, route_id, interval_key, starts_at)`

Geplante Indizes:

- `(asset_id, interval_key, starts_at, id)` für Charts;
- `(asset_id, source_id, interval_key, starts_at, id)` für quellenbezogene Vergleiche;
- `(source_id, observed_at, id)` für Import-/Collector-Kontrolle.

## Zeit- und Datenregeln

- Alle Zeitpunkte werden in UTC gespeichert.
- `market_at` bzw. `starts_at/ends_at` sind fachliche Marktzeiten.
- `observed_at` ist der Zeitpunkt, zu dem MOSA 2 den Wert gesehen oder erzeugt hat.
- Keine FLOAT/DOUBLE-Typen für Preise oder Finanzmengen.
- Währung wird pro Datensatz explizit gespeichert; keine stillschweigende Annahme aus dem Asset.
- Währungsumrechnung ist nicht Teil dieser ersten Marktdaten-Grundschicht.
- Provider-spezifische IDs bleiben in `m2_asset_source_routes`; die Markttabellen erhalten keine Yahoo-, L&S-, Oslo- oder sonstigen providerbezogenen Spalten.

## Current-Aktualisierung

Der spätere Schreibpfad muss transaktional und deterministisch sein:

1. eingehende Beobachtung validieren;
2. append-only History schreiben bzw. über Dedupe erkennen;
3. Current nur aktualisieren, wenn der neue fachliche Zeitpunkt zulässig ist;
4. Current und History dürfen niemals durch zwei unabhängige Sonderlogiken auseinanderlaufen;
5. Rollback bei Fehlern.

Die konkrete Collector-Implementierung gehört nicht in Phase 3A; Tests müssen diese Semantik jedoch modellieren.

## Geplante Normalabfragen

Mindestens folgende Wege müssen ohne ungebundenen Full Scan funktionieren:

1. aktueller Marktzustand eines Assets;
2. letzte N Beobachtungen eines Assets;
3. Beobachtungen eines Assets in begrenztem Zeitraum;
4. dasselbe quellenbezogen;
5. letzte N Bars eines Assets und Intervalls;
6. Bars eines Assets/Intervalls in begrenztem Zeitraum;
7. technische Kontrolle neuer Beobachtungen einer Source seit einem Zeitpunkt.

## Performance-Ziele

Die bereits in Phase 1 bestätigten Budgets bleiben verbindlich:

- Current-Abfrage ideal < 20 ms;
- History-/Bar-Abfrage < 100 ms;
- normale Seiten sollen insgesamt < 200 ms DB-Zeit benötigen;
- keine Normalabfrage darf auf einen ungebundenen Vollscan angewiesen sein.

Die frühere Skalierungsprüfung bis 1.000.000 History-Zeilen belegt die Plattformfähigkeit, ersetzt aber nicht die Prüfung der echten Phase-3-Indizes und DDL.

## Phase-3-Ablauf

### 3A – Repository-Implementierung

- versionierte Migration `0002_market_current_history.sql`;
- deterministische Offline-Tests für Tabellen, Keys, FKs, CHECKs und Indexdefinitionen;
- bestehende Migration 0001 byte-identisch lassen;
- keine Live-DB-Änderung.

### 3B – isolierter Live-Apply und Postcheck

**Erfolgreich abgeschlossen am 19.10.2026 nach separater Freigabe.**
Migration 0002 wurde einmalig angewendet: 16 Tabellen, 140 Spalten, 16 PKs,
9 zusätzliche Unique Keys, 26 sekundäre Indizes, 23 FKs und 19 CHECKs.
30/30 praktische Tests und 8/8 natürliche EXPLAIN-Pfade bestanden.
`bars_asset`: `ix_market_bars_asset_time`, `range`, estimated rows 2,
`Using where; Using index`, kein Filesort. Kein Fixture-Ausbau erforderlich.
Alle synthetischen Daten wurden zurückgerollt; eine neue Verbindung bestätigte
Ledger v1 unverändert, v2 korrekt und alle 15 Nicht-Ledger-Tabellen leer.
[Finaler Live-Nachweis](PHASE3B_FINAL_LIVE.md), ohne Produktivfreigabe oder echte Daten.

Der durchgeführte freigegebene Ablauf:

- Preflight der isolierten Testdatenbank;
- sicherstellen, dass Version 1 vorhanden ist und exakt 13 Phase-2-Tabellen bestehen;
- Migration 0002 einmalig anwenden;
- Struktur, Constraints und Indexpfade prüfen;
- ausschließlich synthetische Testdaten verwenden;
- Ledger Version 2 erst nach vollständigem Erfolg schreiben;
- keine echten MOSA-Daten.

### 3C – kleine kontrollierte Beispieldaten

Erst nach erfolgreicher 3B und einer eigenen ausdrücklichen Freigabe; hier nicht gestartet:

- wenige synthetische bzw. ausdrücklich freigegebene Testassets;
- Current/History-Konsistenz prüfen;
- Dedupe und zeitliche Update-Regel nachweisen;
- Chart-/History-Lesewege messen.

### 3D – kontrollierte MOSA-Datenübernahme planen

Erst danach wird festgelegt, welche vorhandenen echten MOSA-Marktdaten read-only übernommen werden. Keine 1:1-Altdatenkopie und kein Dual Write.

## Akzeptanzkriterien für Phase 3A

- genau drei neue Marktdatentabellen;
- Current und History strikt getrennt;
- keine Provider-Sondertabellen oder Provider-Spalten;
- Provenienz über bestehende Source/Route-Struktur;
- append-only Beobachtungen mit zentralem Dedupe;
- OHLCV-Bars mit eindeutiger Intervallidentität;
- DECIMAL statt FLOAT/DOUBLE;
- UTC-Zeitmodell;
- passende Indizes für alle dokumentierten Normalabfragen;
- FK-Standard weiterhin ON DELETE RESTRICT;
- bestehende Migration 0001 unverändert;
- keine Live-Datenbankänderung;
- keine echten MOSA-Daten;
- keine produktive Änderung.

## Ergebnisziel

Nach Phase 3 besitzt MOSA 2 erstmals eine fachlich nutzbare Finanzdatenbasis:

- ein Asset kann einen aktuellen, schnell lesbaren Marktwert besitzen;
- seine Marktbeobachtungen bleiben historisch nachvollziehbar;
- Charts können auf vorbereitete Bars zugreifen;
- Quelle, Route, Zeit und Währung bleiben transparent;
- die Struktur ist für spätere Collector und kontrollierte MOSA-Migration vorbereitet, ohne diese bereits vorwegzunehmen.

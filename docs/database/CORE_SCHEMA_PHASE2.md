# MOSA 2 – Phase 2: Core- und Asset-Identitätsmodell

**Status:** fachlich und technisch spezifiziert · noch nicht als Datenbankschema angewendet  
**Grundlage:** Phase 1 erfolgreich abgeschlossen; Issue #5 geschlossen  
**Ziel:** Den stabilen gemeinsamen Core und das Finanz-Identitätsmodell festlegen, bevor Markt-, Depot-, News- oder Migrationsdaten in MOSA 2 übernommen werden.

## Scope

Phase 2 umfasst ausschließlich:

- gemeinsame Entities;
- gerichtete Beziehungen zwischen Entities;
- Datenquellen und Provenienz;
- Dateimetadaten;
- allgemeine Ereignisse;
- Jobdefinitionen und Jobläufe;
- Schema-Migrationen, Modulzustände und Sync-Checkpoints;
- Finanz-Assets und deren externe Kennungen;
- providerbezogene Asset-Routen.

Nicht Teil dieser Phase:

- Markt-Current und Markt-History;
- Depottransaktionen und Positionsberechnung;
- News, Story, Handlungsbedarf oder KI-Kontext;
- echte MOSA-Daten;
- produktive Migration;
- produktives Deployment.

## Verbindliche technische Basis

- MySQL 8.0.26-16, InnoDB.
- PHP 8.4 über PDO-MySQL/mysqlnd.
- Session-Zeitzone UTC mit `+00:00`.
- Der in Phase 1 praktisch geprüfte strikte Session-SQL-Modus.
- Tabellenstandard `utf8mb4`.
- Standardkollation für menschenlesbare Texte: `utf8mb4_0900_ai_ci`.
- Maschinenkennungen werden zusätzlich kanonisch normalisiert und mit binärer/eindeutiger Vergleichssemantik gespeichert, damit Groß-/Kleinschreibung oder Akzente keine stillen Identitätskollisionen erzeugen.
- Primärschlüssel sind `BIGINT UNSIGNED AUTO_INCREMENT`. Fachliche und externe Identitäten werden niemals aus dem numerischen Primärschlüssel abgeleitet.
- Zeitpunkte werden als UTC gespeichert. Fachzeitpunkt und technischer Erfassungszeitpunkt bleiben getrennt, wenn beide fachlich relevant sind.

Die in Phase 1 verwendete Kollation `utf8mb4_0900_as_cs` bleibt ein Testdetail und wird nicht global auf das Core-Schema übertragen.

## Grundregeln

1. Keine Universal-Tabelle für alle Fachattribute.
2. `m2_entities` liefert nur die gemeinsame, stabile Identität eines Objekts.
3. Fachliche Details bleiben in Modultabellen.
4. Externe Kennungen werden normalisiert und getrennt von Anzeigenamen gespeichert.
5. Provenienz wird über `source_id` nachvollziehbar gemacht, wo eine Quelle fachlich relevant ist.
6. Historische Fakten werden später append-only modelliert; Current-Tabellen bleiben getrennt.
7. JSON ist nur für begrenzte Zusatzmetadaten erlaubt und niemals Ersatz für häufig gefilterte, sortierte oder referenzierte Felder.
8. Physisches Löschen von produktiven Fachdaten ist später nur über ausdrücklich definierte Prozesse zulässig. Core-Objekte erhalten stattdessen Status bzw. Gültigkeitsgrenzen.
9. Fremdschlüssel und Indizes werden passend zu den vorgesehenen Lesewegen definiert.
10. Keine provider- oder asset-spezifische Sonderlogik im Core.

## Tabellenmodell

### 1. `m2_entities`

Gemeinsame Identität aller späteren MOSA-2-Objekte.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK, AUTO_INCREMENT |
| `entity_type` | VARCHAR(64) | fachlicher Typ, z. B. `asset`, `device`, `document` |
| `canonical_name` | VARCHAR(255) | menschenlesbarer kanonischer Name |
| `status` | VARCHAR(32) | `active`, `inactive`, `archived` |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

Indizes:

- PK `(id)`
- `(entity_type, status, id)`
- `(canonical_name, id)` für begrenzte Namenssuche; keine Volltextsuche in Phase 2

Es gibt bewusst keinen generischen JSON-Fachdatenspeicher in dieser Tabelle.

### 2. `m2_relationships`

Gerichtete Beziehungen zwischen zwei Entities.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `from_entity_id` | BIGINT UNSIGNED | FK → `m2_entities.id` |
| `relationship_type` | VARCHAR(64) | kanonischer Beziehungstyp |
| `to_entity_id` | BIGINT UNSIGNED | FK → `m2_entities.id` |
| `source_id` | BIGINT UNSIGNED NULL | optionale Provenienz |
| `valid_from` | DATETIME(6) NULL | fachliche Gültigkeit |
| `valid_to` | DATETIME(6) NULL | NULL = aktuell |
| `created_at` | DATETIME(6) | UTC |

Regeln:

- Self-Relations sind nur erlaubt, wenn der Beziehungstyp dies fachlich zulässt.
- Aktive und historische Beziehungen werden über Gültigkeitsgrenzen unterschieden.
- Keine frei interpretierbaren Richtungen; der Beziehungstyp definiert Semantik von `from` und `to`.

Indizes:

- `(from_entity_id, relationship_type, valid_to, to_entity_id)`
- `(to_entity_id, relationship_type, valid_to, from_entity_id)`
- `(source_id, created_at, id)`

### 3. `m2_sources`

Kanonische Datenquellen.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `source_key` | VARCHAR(128) | eindeutig, kanonisch, maschinenlesbar |
| `source_type` | VARCHAR(64) | z. B. `official`, `market_data`, `user`, `derived` |
| `display_name` | VARCHAR(255) | Anzeigename |
| `base_url` | VARCHAR(512) NULL | nur wenn sinnvoll |
| `enabled` | TINYINT(1) | 0/1 |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

Eindeutig:

- `source_key` mit binärer/eindeutiger Vergleichssemantik

Keine Secrets, Tokens oder Zugangsdaten in dieser Tabelle.

### 4. `m2_files`

Nur Dateimetadaten; Binärdateien bleiben außerhalb der Datenbank.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `entity_id` | BIGINT UNSIGNED NULL | optionaler Objektbezug |
| `source_id` | BIGINT UNSIGNED NULL | optionale Quelle |
| `storage_backend` | VARCHAR(64) | z. B. lokaler Speicher/Objektspeicher |
| `storage_key` | VARCHAR(1024) | interner Speicherverweis, kein öffentlicher URL-Zwang |
| `mime_type` | VARCHAR(255) NULL | |
| `byte_size` | BIGINT UNSIGNED | |
| `sha256` | BINARY(32) | Inhaltsdigest |
| `observed_at` | DATETIME(6) NULL | fachlicher Zeitpunkt |
| `created_at` | DATETIME(6) | UTC |

Indizes:

- `(entity_id, created_at, id)`
- `(source_id, created_at, id)`
- `(sha256)`

### 5. `m2_events`

Schmale, append-only Ereignis-Hülle für modulübergreifende Ereignisse.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `event_type` | VARCHAR(96) | kanonischer Typ |
| `entity_id` | BIGINT UNSIGNED NULL | Hauptbezug |
| `source_id` | BIGINT UNSIGNED NULL | Provenienz |
| `occurred_at` | DATETIME(6) | fachlicher Zeitpunkt |
| `observed_at` | DATETIME(6) | Erfassungszeitpunkt |
| `metadata_json` | JSON NULL | nur seltene Zusatzmetadaten |
| `created_at` | DATETIME(6) | UTC |

Regel: Häufig abgefragte Fachattribute gehören in Modultabellen, nicht in `metadata_json`.

Indizes:

- `(entity_id, occurred_at, id)`
- `(event_type, occurred_at, id)`
- `(source_id, observed_at, id)`

### 6. `m2_jobs`

Logische Hintergrundaufgaben.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `job_key` | VARCHAR(128) | eindeutig |
| `module_key` | VARCHAR(64) | Modulzuordnung |
| `handler_key` | VARCHAR(128) | stabiler Handlername |
| `enabled` | TINYINT(1) | |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

Keine Provider-Cronkonfiguration und keine Secrets speichern.

### 7. `m2_job_runs`

Append-only Ausführungshistorie.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `job_id` | BIGINT UNSIGNED | FK |
| `status` | VARCHAR(32) | `running`, `completed`, `failed`, `cancelled` |
| `started_at` | DATETIME(6) | UTC |
| `finished_at` | DATETIME(6) NULL | |
| `attempt_no` | INT UNSIGNED | >= 1 |
| `summary_json` | JSON NULL | kleine technische Zusammenfassung |
| `created_at` | DATETIME(6) | UTC |

Indizes:

- `(job_id, started_at, id)`
- `(status, started_at, id)`

### 8. `m2_assets`

Finanzfachliche Erweiterung einer Core-Entity.

| Feld | Typ | Regel |
| --- | --- | --- |
| `entity_id` | BIGINT UNSIGNED | PK und FK → `m2_entities.id` |
| `asset_class` | VARCHAR(64) | z. B. `equity`, `etf`, `fund`, `bond`, `cash`, `crypto` |
| `display_name` | VARCHAR(255) | fachlicher Anzeigename |
| `base_currency` | CHAR(3) NULL | ISO-4217, wenn sinnvoll |
| `status` | VARCHAR(32) | fachlicher Assetstatus |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

Regel: Marktpreise, Positionen und Depotwerte gehören nicht in `m2_assets`.

### 9. `m2_asset_identifiers`

Alle externen Asset-Kennungen ohne providerbezogene Kursroute.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `asset_id` | BIGINT UNSIGNED | FK → `m2_assets.entity_id` |
| `identifier_type` | VARCHAR(32) | z. B. `isin`, `wkn`, `ticker`, `figi` |
| `identifier_value` | VARCHAR(128) | Originaldarstellung |
| `normalized_value` | VARCHAR(128) | kanonische maschinenlesbare Form |
| `scope_key` | VARCHAR(64) | nicht NULL; leer für globale Kennungen, sonst z. B. MIC |
| `is_primary` | TINYINT(1) | 0/1 |
| `source_id` | BIGINT UNSIGNED NULL | Provenienz |
| `valid_from` | DATETIME(6) NULL | |
| `valid_to` | DATETIME(6) NULL | |
| `created_at` | DATETIME(6) | UTC |

Eindeutig:

- `(identifier_type, normalized_value, scope_key)` mit exakter/binärer Vergleichssemantik

Zusätzliche Indizes:

- `(asset_id, identifier_type, valid_to, id)`
- `(source_id, created_at, id)`

Normalisierung ist typabhängig und wird zentral implementiert, nicht pro Collector.

### 10. `m2_asset_source_routes`

Providerbezogene Identität und Routing für spätere Collector.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `asset_id` | BIGINT UNSIGNED | FK |
| `source_id` | BIGINT UNSIGNED | FK |
| `route_type` | VARCHAR(64) | z. B. `quote`, `history`, `news` |
| `external_key` | VARCHAR(255) | Providerkennung |
| `priority` | SMALLINT UNSIGNED | kleinere Zahl = bevorzugt |
| `enabled` | TINYINT(1) | |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

Eindeutig:

- `(source_id, route_type, external_key)`
- `(asset_id, source_id, route_type)`

Damit entsteht keine Sondertabelle pro Provider.

### 11. `m2_schema_migrations`

| Feld | Typ | Regel |
| --- | --- | --- |
| `version` | BIGINT UNSIGNED | PK, monoton |
| `migration_key` | VARCHAR(160) | eindeutig |
| `checksum` | BINARY(32) | SHA-256 der Migration |
| `applied_at` | DATETIME(6) | UTC |

### 12. `m2_sync_checkpoints`

Wiederholbare, idempotente spätere Datenübernahme.

| Feld | Typ | Regel |
| --- | --- | --- |
| `id` | BIGINT UNSIGNED | PK |
| `source_id` | BIGINT UNSIGNED | FK |
| `stream_key` | VARCHAR(128) | kanonischer Datenstrom |
| `cursor_value` | VARCHAR(512) NULL | undurchsichtiger Cursor |
| `watermark_at` | DATETIME(6) NULL | fachlicher Zeit-Wasserstand |
| `updated_at` | DATETIME(6) | UTC |

Eindeutig:

- `(source_id, stream_key)`

### 13. `m2_module_state`

Kleiner aktueller Zustand je MOSA-2-Modul.

| Feld | Typ | Regel |
| --- | --- | --- |
| `module_key` | VARCHAR(64) | PK |
| `schema_version` | BIGINT UNSIGNED | |
| `status` | VARCHAR(32) | |
| `updated_at` | DATETIME(6) | UTC |

## Fremdschlüssel- und Löschstrategie

- Core-FKs werden tatsächlich in MySQL definiert.
- Standard ist `ON DELETE RESTRICT`.
- Keine Kaskade von Entity-Löschungen durch Fach- oder Historytabellen.
- Technische Kindtabellen wie Job-Runs können später nur dann `CASCADE` erhalten, wenn der Löschfall ausdrücklich fachlich freigegeben wurde.
- Produktionsobjekte werden grundsätzlich über Status/Gültigkeit stillgelegt statt physisch entfernt.

## Namens- und Identitätsregeln

- Tabellennamen beginnen mit `m2_`.
- Spalten und Keys verwenden `snake_case`.
- Kanonische Schlüssel sind klein, stabil und maschinenlesbar.
- Anzeigenamen dürfen sich ändern; Identität darf davon nicht abhängen.
- ISIN/WKN/FIGI/Ticker werden nicht als Primärschlüssel verwendet.
- Ticker ohne Venue/Scope ist keine global eindeutige Identität.
- Providerkennungen gehören in `m2_asset_source_routes`, nicht in `m2_assets`.

## Geplante Lesewege

Phase 2 muss mindestens diese Wege indexiert abdecken:

1. Entity per ID.
2. Aktive Entities eines Typs.
3. Vorwärts- und Rückwärtsbeziehungen einer Entity nach Typ.
4. Quelle per `source_key`.
5. Asset über ISIN/WKN/FIGI bzw. Ticker+Scope.
6. Alle gültigen Identifikatoren eines Assets.
7. Bevorzugte aktive Providerroute eines Assets.
8. Letzte Jobläufe eines Jobs.
9. Sync-Checkpoint eines Source/Streams.

Keine dieser Abfragen darf einen ungebundenen Full Scan als vorgesehenen Normalweg benötigen.

## Phase-2-Migrationsartefakte

Die spätere technische Umsetzung soll zunächst ausschließlich Repository-Artefakte erzeugen:

- versionierte SQL-Migration für das leere Phase-2-Schema;
- deterministische Offline-Schema-/Index-Tests;
- DDL-Validierung gegen MySQL 8;
- dokumentierte Down-/Cleanup-Strategie ausschließlich für die isolierte Testdatenbank.

Noch keine Anwendung auf eine Datenbank ohne separaten ausdrücklich freigegebenen Testauftrag.

## Akzeptanzkriterien für die Schema-Spezifikation

- Keine Sonderlocken oder providerbezogenen Core-Tabellen.
- Menschliche Anzeige und maschinenlesbare Identität sauber getrennt.
- Asset-Identität unterstützt globale und venuebezogene Kennungen.
- Beziehungen sind in beide Richtungen effizient lesbar.
- Provenienz ist zentral anschließbar.
- Files speichern keine großen Binärdaten in MySQL.
- Jobs und Job-Runs sind getrennt.
- Sync ist checkpoint-fähig und idempotent planbar.
- Alle vorgesehenen Normalabfragen besitzen einen nachvollziehbaren Indexpfad.
- Keine echten MOSA-Daten, kein Deployment und keine produktive Migration in Phase 2.

## Nächster Schritt

Die Spezifikation wird als versionierte SQL-Migration und automatisierte Offline-Tests umgesetzt. Danach folgt ein separater, kontrollierter Apply-/Postcheck-Test ausschließlich auf der leeren isolierten MOSA-2-Testdatenbank.

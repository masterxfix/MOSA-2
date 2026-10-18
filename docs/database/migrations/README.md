# Phase-2-Migrationen

Status: **Repository-Artefakt, auf keine Datenbank angewendet.**

`0001_core_asset_identity.sql` ist Version 1 mit dem Migrationsschlüssel
`0001_core_asset_identity`. Grundlage ist [CORE_SCHEMA_PHASE2.md](../CORE_SCHEMA_PHASE2.md).
Vorher existierte keine Migrationsablage und kein Runner; diese Ablage enthält
nur versionierte DDL, keine zweite Laufzeitarchitektur. Die 13 Tabellen werden
in FK-sicherer Reihenfolge angelegt. Keine Daten, Ledger-Einträge, Datenbanken,
Benutzer, Servervariablen oder vorhandenen Tabellen werden verändert.

## Technische Entscheidungen

- InnoDB, utf8mb4, menschenlesbare Namen mit `utf8mb4_0900_ai_ci`.
- Maschinenfelder verwenden explizit `utf8mb4_0900_bin` (MySQL-8-NO-PAD-
  Kollation). Case, Akzente und abschließende Leerzeichen werden nicht zu
  gleicher Identität zusammengezogen. Kanonische Normalisierung bleibt Aufgabe
  der späteren zentralen Anwendung; der DDL-Code normalisiert keine Kennungen.
- Zehn `id`-PKs sind BIGINT UNSIGNED AUTO_INCREMENT. Die ausdrücklich im
  Tabellenmodell festgelegten Ausnahmen sind `m2_assets.entity_id` (PK/FK),
  `m2_schema_migrations.version` (explizite monotone Version) und
  `m2_module_state.module_key` (exakter fachlicher Modulschlüssel).
- 14 explizite FKs mit ON DELETE RESTRICT; keine Kaskaden und kein Abschalten
  der FK-Prüfung. Alle FK-Spalten besitzen einen führenden Indexpfad.
- Unique Keys entsprechen der Spezifikation. Identifier-Eindeutigkeit gilt
  auch für historische Zeilen; `valid_to` ist absichtlich nicht Teil des Keys.
- `scope_key` ist NOT NULL DEFAULT ''. CHECKs verlangen für kanonisches
  `ticker` einen nichtleeren Scope und für `isin`, `wkn`, `figi` den leeren
  globalen Scope. MIC-Prüfung und typabhängige Normalisierung folgen später.
- CHECKs sichern die spezifizierten Statuswerte bei Entities/Job-Runs,
  0/1-Schalter und `attempt_no >= 1`. Asset- und Modulstatus bleiben offen.
- Zusätzlich zu den ausdrücklich aufgelisteten Indizes deckt
  `ix_routes_preferred (asset_id, enabled, priority, id)` Leseweg 7 ab:
  aktive Routen eines Assets, priorisiert mit stabiler ID-Reihenfolge.
  Ein optionaler `route_type`-Filter wird innerhalb des begrenzten Asset-Pfads
  ausgewertet; keine Provider-Sonderlogik.
- Append-only-Verhalten, zulässige Self-Relations je Beziehungstyp, UTC-
  Eingaben, monotone Migrationsversionen und begrenzte JSON-Inhalte erfordern
  spätere Schreiblogik bzw. Rechte. Das Schema behauptet diese nicht allein
  durch DDL zu erzwingen. JSON existiert nur in Events und Job-Runs.

## Reproduzierbare Offline-Prüfung

Vom Repository-Root mit Python 3 und dem bestehenden PHP-Testlaufzeitbedarf:

```text
python -m unittest discover -s tests -v
python scripts/deploy_sftp.py validate
git diff --check
```

Nur die neuen Schema-Tests benötigen kein PHP:

```text
python -m unittest discover -s tests -p test_core_schema_phase2.py -v
```

Der kleine Standardbibliothek-Parser konsumiert die gesamte erlaubte DDL-
Teilmenge. Spalten/Typen/NULL-Regeln werden unabhängig aus der verbindlichen
Spezifikation gelesen, Keys/FKs/Indizes/CHECKs separat verglichen. Mutationstests
prüfen, dass relevante Sicherheitsabweichungen tatsächlich erkannt werden.
Das ist **keine MySQL-Server-Syntax- oder Ausführungsbestätigung**. Ein späterer
separat freigegebener Apply-/Postcheck muss auf MySQL 8.0.26-16 insbesondere
SHOW CREATE TABLE, INFORMATION_SCHEMA, CHECK-Verhalten, binäre Identität,
Nullability und EXPLAIN der vorgesehenen Lesewege prüfen.

## Späterer Apply: ausdrücklich noch nicht freigegeben

Kein automatischer Runner und kein Deployment-Hook. Vor einem separat
beauftragten Apply die leere isolierte Ziel-DB, Rechte und Serverversion
bestätigen, Session auf UTC `+00:00` und den qualifizierten strikten SQL-Modus
setzen. SQL unverändert ausführen, Postchecks durchführen und erst dann
Version/Schlüssel/SHA-256 der unveränderten Datei/UTC-Zeit in der Migrationstabelle
erfassen. Diese Migration fügt diesen Eintrag bewusst nicht selbst ein.
MySQL-DDL besitzt implizite Commits: ein Gesamtlauf ist nicht atomar. Bei einem
Teilfehler stoppen, den tatsächlichen Tabellenstand prüfen; nicht blind erneut
ausführen. Kein `IF NOT EXISTS`, das unbekannte Altstrukturen verdecken könnte.

## Cleanup ausschließlich nach gesonderter Testfreigabe

Keine ausführbare Down-Migration und keine Bereinigung in diesem Auftrag.
Vor einem späteren Cleanup die isolierte Test-DB und ihre ausschließlich
synthetischen Inhalte eindeutig prüfen. Bei Fremdtabellen oder unbekannten
Abhängigkeiten stoppen. Nur tatsächlich vorhandene Phase-2-Tabellen in dieser
Reihenfolge entfernen, FK-Prüfung eingeschaltet lassen:

<!-- cleanup-order -->
1. `m2_module_state`
2. `m2_sync_checkpoints`
3. `m2_schema_migrations`
4. `m2_asset_source_routes`
5. `m2_asset_identifiers`
6. `m2_assets`
7. `m2_job_runs`
8. `m2_jobs`
9. `m2_events`
10. `m2_files`
11. `m2_relationships`
12. `m2_sources`
13. `m2_entities`
<!-- /cleanup-order -->

Nie Datenbanken, Benutzer oder andere Tabellen löschen. Für produktive Daten
gilt diese Test-Cleanup-Anleitung nicht; dort Status/Gültigkeit verwenden.

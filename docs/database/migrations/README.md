# Versionierte Migrationen

## Version 0005 – Collector-Reservierungen, nur vorbereitet

`0005_collector_reservations.sql` ergänzt isolierte Zustands-/Reservierungstabellen
und gesperrte Job-/Modulanker. 0001–0004 bleiben unverändert. Ausschließlich der
temporäre MySQL-8-Dienst des Offline-Workflows darf diese Migration für synthetische
Tests anwenden; keine Anwendung auf Dogado oder Produktion. Vertrag und offene
Live-Blocker: [COLLECTOR_PERSISTENCE.md](../COLLECTOR_PERSISTENCE.md).

## Version 0004 – Current-Provenienz (Issue 41)

`0004_current_observation_provenance.sql` ist der versionierte Anzeigepfad:
ein ALTER an Current mit Observation-ID, Format, Dedupe-Key und Routenrevision.
Preview, exakter Schema-/Fact-Check, Rückfallsicherung und ausdrückliche
Freigabe der isolierten Testanwendung sind erforderlich. Die bestehende
Migrationshistorie bleibt byte-identisch. Ablauf und Nachweisgrenzen:
[CURRENT_DISPLAY.md](../CURRENT_DISPLAY.md). Eine Repository-Datei belegt
keine Live-Anwendung.

## Version 0003 – Unit-Schema live validiert (Phase 3K)

Am 19.10.2026 wurde die unveränderte Migration auf der isolierten Testdatenbank
vollständig validiert. Zwei vorherige fail-closed Stopps waren generische
Checkerfehler (FK-Komma-Leerzeichen und associative OR-Darstellung); beide wurden
ohne Datenbankreparatur korrigiert. Exakt bestätigte Resume-States verhinderten
jede Wiederholung bereits ausgeführter DDLs. DDL 4/5 und vollständiger Postcheck,
rollbackbare Constraintproben und zwei unabhängige Final-Readbacks bestanden.

Ledger v3: `0003_market_units`, SHA-256
`199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee`,
`applied_at` UTC **2026-10-19 18:17:09.921125**; v1/v2 unverändert.
Endschema: **17 Tabellen, 186 Spalten, 17 PK, 10 zusätzliche UNIQUEs,
39 weitere Indizes, 36 FKs, 37 CHECKs**. Units 0, Routes 8/revision 1,
Observations 8 einschließlich Dedupe-Keys unverändert, Current/Bars 0.
Keine Seeds, Writer-v2, B8 oder Produktion.
[Vollständiger Nachweis und Sicherheitsbereinigung](../PHASE3K_UNIT_SCHEMA_LIVE.md).

## Version 0002 – Marktdaten (Phase 3A)

`0002_market_current_history.sql` wurde am **19.10.2026 einmalig auf der isolierten
Testdatenbank live validiert**. Reihenfolge: **0001 → 0002**. Ledger Version 2:
`0002_market_current_history`, SHA-256
`205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee`,
`applied_at` UTC **2026-10-19 08:02:39.939576**. Version 1 unverändert.
16 Tabellen, 30/30 praktische Tests, 8/8 natürliche EXPLAIN-Pfade und alle
15 Nicht-Ledger-Tabellen nach Rollback leer; unabhängiger Readback erfolgreich.
[Finaler Phase-3B-Live-Nachweis](../PHASE3B_FINAL_LIVE.md).
Migrationen 0001/0002 byte-identisch; keine Produktivfreigabe und keine Phase 3C.
Grundlage: [MARKET_DATA_PHASE3.md](../MARKET_DATA_PHASE3.md).

Genau drei Tabellen: `m2_market_current` (ein Zustand je Asset),
`m2_market_observations` (append-only Beobachtungen, eindeutiger BINARY(32)-Dedupe)
und `m2_market_bars` (OHLCV, eindeutige Asset/Route/Intervall/Start-Identität).
Neun FKs referenzieren Assets, Sources und Routes mit ON DELETE RESTRICT.
Finanzwerte sind DECIMAL, Zeiten explizite UTC-Eingaben in DATETIME(6).
CHECKs prüfen positive Preise, Bid/Ask, Tagesrange, Intervallgrenzen und
OHLC-Grenzen; kanonische Intervalle sind ausschließlich 1m, 5m, 1h und 1d.
Nullable Vergleichswerte dürfen fehlen (SQL-CHECK akzeptiert UNKNOWN).

Die spezifizierten Asset-/Zeit-/Source-Indizes sind vollständig enthalten.
Zusätzlich existiert je Tabelle ein expliziter `route_id`-Index für den FK,
damit MySQL keinen impliziten Index erzeugen muss. Keine redundanten Composite-FKs.
Route/Asset/Source-Konsistenz, ISO-Währungskanonisierung, Append-only-Rechte,
Dedupe-Bildung und monotone Current-Aktualisierung bleiben spätere zentrale
Anwendungs-/Validierungsregeln; keine Trigger oder Schreiblogik in dieser Phase.
Offline-Modelltests beschreiben Dedupe, ältere Beobachtungen, deterministischen
Gleichstand und Rollback, ohne einen produktiven Schreibpfad zu implementieren.

Offline-Test: `python -m unittest discover -s tests -p test_market_schema_phase3.py -v`.
Der Offline-Test allein ist kein MySQL-Ausführungs-, EXPLAIN- oder Performance-
Nachweis. Der separat freigegebene Phase-3B-Lauf bestätigte nun Struktur,
Constraints und acht natürliche Indexpfade auf begrenzten synthetischen Daten.
Eine weitergehende Performance-/Parallelitätsfreigabe folgt daraus nicht.
Migration 0001 bleibt byte-identisch.
Die unten stehende Cleanup-Reihenfolge betrifft ausschließlich Phase 2 vor
einem Apply von 0002; nach dessen Apply sind die abhängigen Markttabellen in
einem separat freizugebenden Cleanup zu berücksichtigen.

## Version 0001 – Core (Phase 2)

Status: **Live technisch validiert auf der isolierten Testdatenbank am 18.10.2026.**

Der autorisierte einmalige Apply und sämtliche Postchecks sind erfolgreich.
Migration SHA-256: `9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`.
Ledger: Version `1`, Schlüssel `0001_core_asset_identity`, identischer Digest als
`BINARY(32)`, tatsächliches `applied_at` UTC `2026-10-18 14:10:22.604406`.
13 Tabellen bleiben bestehen; Ledger 1 Zeile, alle übrigen 12 Tabellen leer.
Details einschließlich aller 11 EXPLAIN-Wege: [finaler Live-Nachweis](../PHASE2_FINAL_LIVE.md).

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
Offline-Tests allein sind **keine MySQL-Server-Syntax- oder Ausführungsbestätigung**.
Der zusätzlich ausgeführte freigegebene Live-Apply-/Postcheck bestätigte auf MySQL 8.0.26-16
SHOW CREATE TABLE, INFORMATION_SCHEMA, CHECK-Verhalten, binäre Identität,
Nullability und EXPLAIN der vorgesehenen Lesewege.

## Weitere Applies benötigen eine eigene Freigabe

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

Keine ausführbare Down-Migration. Das erfolgreich validierte Schema bleibt erhalten.
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

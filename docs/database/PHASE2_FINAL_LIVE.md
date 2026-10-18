# Phase 2: finaler Live-Apply/Postcheck

## Ergebnis und Grenzen

Fachlich erfolgreich: das Core-/Asset-Identitätsschema ist technisch für weitere
MOSA-2-Testentwicklung freigegeben. Keine Last-, Parallelbetriebs- oder
Produktionsfreigabe; keine nächste Fachphase begonnen. Keine echten MOSA-Daten,
kein Restore-Zugriff, keine Rechteerweiterung und keine globale MySQL-Änderung.

Ausgangscommit: `381be6a22a2fc5fb5b3b6a8d011e87ba9ba8ca60`.
Genau ein Apply aus leerem Zustand am 2026-10-18 um 14:10:22 UTC; kein zweiter
Apply, kein Resume und kein DROP. Die Migration blieb bytegleich:
`9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`.

## Preflight und Struktur

Der gemeinsame Prüfcode bestätigte vor DDL die bekannte isolierte Testidentität,
MySQL 8.0.26-16, 0 Tabellen, keine Routinen/Trigger/Events, unveränderte Rechte,
FK-Prüfung 1, UTC +00:00, utf8mb4 / utf8mb4_0900_ai_ci und den qualifizierten
strikten Session-SQL-Modus. Änderungen waren auf diese Session begrenzt.

Vollständiger Strukturvergleich: 13 Tabellen, 96 Spalten, 13 PKs, 7 Unique Keys,
16 sekundäre Indizes, 14 FKs mit RESTRICT und 9 CHECKs. Typen, Reihenfolge,
Nullability, Defaults, AUTO_INCREMENT, InnoDB, Zeichensätze, Kollationen,
FK-Ziele und Indexeigenschaften entsprachen der unveränderten Migration.
Alle neun CHECKs stimmten dreifach überein: Migration, INFORMATION_SCHEMA und
SHOW CREATE TABLE. Die konservative AST-Normalisierung bleibt fail-closed.

## Praktische Tests

Alle 19 dokumentierten Ergebnisse bestanden:

- gültige Entity vorhanden;
- Entity-Status, Source-/Job-/Route-Boolean, is_primary, Job-Run-Status und
  attempt_no >= 1: ungültige Werte jeweils mit Fehler 3819 abgewiesen;
- korrigierter neuer Relationship-Kinddatensatz ohne Parent: exakt Fehler 1452;
- Löschen eines referenzierten Parents: exakt Fehler 1451;
- Ticker ohne Scope und ISIN/WKN/FIGI mit falschem Scope: jeweils 3819;
- scope_key NULL: 1048; Identifier-Duplikat: 1062;
- Identifier und Source-Key case-sensitiv; menschenlesbarer Name ai_ci.

Kein Fehler wurde pauschal akzeptiert. Alle synthetischen Prüfdaten wurden
zurückgerollt; danach wurden alle Tabellen tatsächlich auf Leerstand geprüft.

## EXPLAIN: 11 von 11 erwarteten Indexpfaden

| Leseweg | key | access type | rows (Schätzung) | Extra |
| --- | --- | --- | ---: | --- |
| Entity-ID | PRIMARY | const | 1 | NULL |
| Aktiver Entity-Typ | ix_entities_type_status | ref | 1 | Using index |
| Relationship vorwärts | ix_relationships_from | ref | 1 | Using where; Using index |
| Relationship rückwärts | ix_relationships_to | ref | 1 | Using where; Using index |
| Source-Key | uq_sources_key | const | 1 | Using index |
| Globale Asset-Kennung | uq_identifiers_identity | const | 1 | NULL |
| Ticker und Scope | uq_identifiers_identity | const | 1 | NULL |
| Gültige Asset-Identifier | ix_identifiers_asset | ref | 4 | Using where; Using index |
| Bevorzugte Route | ix_routes_preferred | range | 1 | Using where; Using index |
| Letzte Job-Runs | ix_job_runs_job | ref | 8 | Backward index scan; Using index |
| Source-/Stream-Checkpoint | uq_checkpoints_stream | const | 1 | Using index |

Kein ungebundener Full Scan. Dieser kleine synthetische Bestand belegt
Indexpfade, nicht Last- oder Performancekapazität.

## Ledger und dauerhafter Endzustand

Ledger erst nach sämtlichen erfolgreichen Tests geschrieben und zurückgelesen:
Version 1, Schlüssel `0001_core_asset_identity`, obiger SHA-256 als BINARY(32),
`applied_at = 2026-10-18 14:10:22.604406` UTC. Exakt eine Ledger-Zeile.
Unabhängiger Readback um 14:12:31 UTC: exakt 13 erwartete Tabellen; Ledger 1,
alle anderen 12 Tabellen 0 Zeilen. Das Schema bleibt ausdrücklich erhalten.

Privater Laufbericht SHA-256:
`3cbbf8e0fe1e82728d04de0e100a3ba73b5093ebe7908a84801d0bcd8c2d64e8`.
Dies ist ein Integritätsverweis, kein öffentlich abrufbarer vollständiger Bericht.

## Temporäre Bereinigung

Um 14:16:57 UTC wurden ausschließlich die zwölf eigenen privaten Testdateien
(einschließlich Passwort, Konfiguration, Locks und Bericht) sowie die beiden
Dateien des temporären HTTPS-Einstiegs und deren zwei Verzeichnisse entfernt.
Die Plesk-Sitzung war zuvor abgelaufen; sie wurde über den bestehenden
Dogado-SSO erneuert und die noch vorhandene exakte Dateiliste vor Löschung
erneut geprüft. Keine Datenbanktabellen wurden dabei gelöscht.
Anschließend bestätigt: Einstieg HTTP 404, neutrale Teststartseite HTTP 200
und bytegleich; unverändert neun bestehende Plesk-Aufgaben, keine neue
dauerhafte Aufgabe gespeichert. Die entfernten temporären Zugangsdaten sind
nicht aus dem Repository wiederherstellbar; das bestehende DB-Passwort wurde
nicht geändert.

## Prüfcode und Kontrollzentrum

Ein zusätzlicher eng begrenzter Prüfhalt bewahrt ein vollständig strukturgeprüftes,
leeres Schema ausschließlich bei Fehlern im praktischen Testabschnitt zur Analyse.
DDL-/Struktur-/Ledger-Fehler oder nichtleere/fremde Tabellen erfüllen diesen
Prüfhalt nicht. Regressionen prüfen diese Grenzen. Im erfolgreichen Live-Lauf
wurde dieser Prüfhalt nicht benötigt.

Der native Recorder nahm die Registrierung an. Describe und Plan wurden jeweils
einmal versucht; beide meldeten die bekannte Lücke: kein offener Laborauftrag
für den tatsächlichen nativen Turn. Keine künstlichen IDs, Starts oder Stops;
Kontrollzentrum-Sichtbarkeit ist damit nicht vollständig bestätigt. Der fachliche
Live-Nachweis ist davon getrennt.

## Lokale Tests

Gesamtlauf: 58 Tests, davon 57 erfolgreich unter Windows. Der unveränderte
Phase-1B-Test `test_target_runtime_identifier_and_row_budget_guards` scheitert
wie im Ausgangsstand an der POSIX-Dateirechteprüfung `budget_not_private`.
Alle Phase-2-Tests und drei PHP-Lints sind erfolgreich, ebenso die bestehende
Repository-Validierung. Der vollständige Linux-Workflow ist vor Übernahme
desselben Abschluss-SHA nach main zwingend; Deployment muss skipped bleiben.

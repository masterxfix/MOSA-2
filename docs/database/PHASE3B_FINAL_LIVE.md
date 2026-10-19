# Phase 3B – finaler Live-Nachweis

Status: **erfolgreich auf der isolierten Testdatenbank am 19.10.2026**.
Keine Produktivfreigabe, keine echten MOSA-Daten, keine Phase 3C.

## Grundlage und einmaliger Apply

Ausgangscommit: `c1f98d536f2abf6c69d80306d70908cf87169033`.
Die unveränderten Prüfquellen mit der korrigierten deterministischen Bar-Fixture
wurden vor dem Apply serverseitig hashgleich zurückgelesen. Beide Migrationen
blieben byte-identisch:

- 0001: `9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`
- 0002: `205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee`

Laufbeginn UTC: **2026-10-19 08:02:34**; erfolgreicher Abschluss UTC:
**2026-10-19 08:02:40**. Migration 0002 wurde genau einmal angewendet.
Kein Resume, kein zweiter Apply, keine spontane DDL-Korrektur.

## Preflight

Der gemeinsame fail-closed Preflight bestätigte die exakte isolierte
Ziel- und Loginidentität, MySQL/Percona `8.0.26-16`, Port `3307`, UTC `+00:00`,
`utf8mb4` / `utf8mb4_0900_ai_ci`, den vorgegebenen strikten SQL-Modus,
`FOREIGN_KEY_CHECKS=1` und die erwarteten unveränderten Grants.
Keine Routinen, Trigger oder Events. Exakt 13 bekannte Core-Tabellen,
Ledger ausschließlich Version 1 und zwölf Fachtabellen mit jeweils null Zeilen.
Der vollständige Core-Strukturvergleich war erfolgreich.

## Struktur und praktische Tests

INFORMATION_SCHEMA und SHOW CREATE TABLE wurden gegen den unveränderten
Migrationsvertrag verglichen: Spaltenreihenfolge, Typen einschließlich DECIMAL-
Präzision, Nullability, AUTO_INCREMENT, Kollationen, InnoDB, Keys, Indizes,
FK-Ziele/RESTRICT und CHECK-Ausdrücke vollständig erfolgreich.

| Merkmal | Erwartet | Bestätigt |
| --- | ---: | ---: |
| Tabellen | 16 | 16 |
| Spalten | 140 | 140 |
| Primary Keys | 16 | 16 |
| Zusätzliche Unique Keys | 9 | 9 |
| Sekundäre Indizes | 26 | 26 |
| Foreign Keys | 23 | 23 |
| CHECK-Constraints | 19 | 19 |

**30/30 praktische Tests erfolgreich**, ausschließlich mit synthetischen Daten
in einer rollbackfähigen Transaktion: gültige Inserts, Preis-/Bid-Ask-/Range-
und Bar-Zeit-/Intervallprüfungen, FKs, PK-/Dedupe-/Bar-Duplikate und Delete-RESTRICT.
Negativtests bestanden nur mit den exakt erwarteten MySQL-Fehlernummern.

## Natürliche EXPLAIN-Pläne

**8/8 erfolgreich**, jeweils bereits im ersten Versuch. Kein Fixture-Ausbau,
kein FORCE INDEX und keine Lockerung des erwarteten Keys oder der erlaubten
gebundenen Zugriffstypen. Jeder Versuch wurde vor dem Guard privat gesichert.

| Query | Tatsächlicher und erwarteter Key | Type | Estimated rows | Extra |
| --- | --- | --- | ---: | --- |
| `current_asset` | `PRIMARY` | `const` | 1 | — |
| `current_source` | `ix_market_current_source` | `range` | 16 | Using where; Using index |
| `observations_asset` | `ix_market_observations_asset_time` | `ref` | 8 | Backward index scan; Using index |
| `observations_asset_source` | `ix_market_observations_asset_source` | `range` | 8 | Using where; Using index |
| `observations_source` | `ix_market_observations_source` | `range` | 128 | Using where; Using index |
| `bars_asset` | `ix_market_bars_asset_time` | `range` | 2 | Using where; Using index |
| `bars_asset_source` | `ix_market_bars_asset_source` | `range` | 2 | Using where; Using index |
| `bars_source` | `ix_market_bars_source` | `range` | 288 | Using where; Using index |

Insbesondere nutzt `bars_asset` natürlich `ix_market_bars_asset_time` mit
`range`, geschätzt zwei Zeilen und `Using where; Using index`; kein Filesort.
Die initiale Fixture umfasste 512 Current-Zeilen, 4096 Beobachtungen und
16384 Bars. Alle 512 Assets erhielten dieselbe Verteilung über vier kanonische
Intervalle und mehrere Tage. Das Prüfzeitfenster traf zwei Bars je Asset.

Dieser Nachweis gilt für die begrenzte synthetische Fixture und diese acht
Abfragen. Er ersetzt keine Messung größerer Datenmengen oder des Parallelbetriebs
und keine spätere fachliche Current-/History-/Dedupe-Prüfung in Phase 3C.

## Rollback, Ledger und unabhängiger Readback

Nach den praktischen und EXPLAIN-Prüfungen wurde die synthetische Transaktion
vollständig zurückgerollt. Vor dem Ledger-Schreiben waren alle 15 Nicht-Ledger-
Tabellen leer und ausschließlich Version 1 vorhanden.

Version 2 wurde transaktional geschrieben, vor Commit zurückgelesen und geprüft:

- Version: `2`
- Migration-Key: `0002_market_current_history`
- Checksum: `205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee`
- Tatsächliches `applied_at` UTC: **2026-10-19 08:02:39.939576**

Eine neue unabhängige DB-Verbindung bestätigte anschließend erneut den
Preflight und die vollständige Struktur: **16 Tabellen, exakt zwei Ledgerzeilen,
Version 1 unverändert, Version 2 korrekt und alle 15 Nicht-Ledger-Tabellen leer**.
Keine Routinen, Trigger oder Events; Grants unverändert.

## Kurzlebiger Zugang und Bereinigung

Der vorhandene HTTPS-Gateway blieb hinter dem unveränderten äußeren Stufe-1-
Passwortschutz. Ein secretfreier POST-Probelauf bestätigte den Origin-/Cookie-/
CSRF-Weg vor der Passworteingabe. Secure, HttpOnly, SameSite Strict, no-store
und private Verzeichnis-/Dateirechte `0700`/`0600` wurden beibehalten.

Der erste Formularversuch wurde nach Ablauf des zehnminütigen CSRF-Tokens
vor jeder DB-Verbindung abgewiesen; dabei wurde kein Passwort gespeichert.
Ein frisches Formular ermöglichte anschließend die erfolgreiche Übergabe.
Kein weiterer Passwortreset. Das Passwort wurde nicht ausgelesen, ausgegeben
oder in Nachweise übernommen. Der Runner entfernte die kurzlebige Secret-Datei.

Danach wurden alle 13 temporären Zugangs-, Quellen-, Konfigurations- und
Lock-Dateien sowie der Web-Einstieg entfernt. Ein unabhängiger Dateireadback
bestätigte ausschließlich einen secretfreien Originalbericht mit `0700`/`0600`-
Schutz. Dessen unveränderter SHA-256 lautet:
`391e5f4e1c09e3838bd5a2e01064e863e425739c5292f6ab76adb53553c60143`.

Die temporäre URL lieferte authentifiziert **404**. Die permanente Testhauptseite
blieb erreichbar und bytegleich, ihr Schutz unverändert; ohne Anmeldung weiterhin
**HTTP 401**. Keine temporäre Credential-Datei bleibt zurück.

## Repository-Abschluss

Geändert werden ausschließlich dieser Nachweis, `MARKET_DATA_PHASE3.md` und
`migrations/README.md`. Die vier serverseitigen Prüfquellen bestanden PHP-Lint.
Lokale Repository-Suite: 98/99 erfolgreich, ausschließlich der bekannte Windows-
POSIX-Fall `budget_not_private` abweichend. Dateivalidierung und Diff-Prüfung
bestanden. Der manuelle Linux-Abschlusslauf prüft exakt den Abschluss-Commit;
Ergebnisse, Commit und Run-ID werden in Issue #11 festgehalten, ohne den
geprüften Commit danach zu verändern.
Der Deploy-Job muss übersprungen bleiben. Keine Produktion, keine Collector,
keine echten Daten, keine Phase 3C und keine Sicherheitsstufen 2–4.

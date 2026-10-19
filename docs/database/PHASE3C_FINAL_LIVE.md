# Phase 3C-B – finaler Live-Nachweis

**Status:** fachlich vollständig erfolgreich, 23/23 Prüfungen.
**Ausgangscommit:** `b61f18945011a804baa03ed2c2012300120105b6`.
**Laufzeit UTC:** 19.10.2026, 09:42:32–09:42:33.

Der separat freigegebene zweite fachliche Lauf verwendete den auf diesem Commit
vorhandenen Runner unverändert, genau einmal. Kein weiterer Testlauf,
keine Migration, keine DDL und keine Änderung der Indizes oder Guards.

## Vorbereitung und Preflight

Die acht temporären Quelldateien wurden direkt aus dem Startcommit übertragen,
mit SHA-256 zurückgeprüft und alle sechs PHP-Dateien serverseitig gelintet.
Der getrennte HTTPS-Gateway blieb hinter dem bestehenden Stufe-1-Schutz
(ohne Anmeldung 401). Der secretfreie Origin-/Cookie-/CSRF-POST-Probeweg und
0700/0600-Dateirechte ohne Symlinks bestanden vor jeder DB-Verbindung.
Das Passwort wurde ausschließlich vom Nutzer im Formular eingegeben,
kurzlebig privat übernommen und nach dem Test entfernt.

Der Gateway-Preflight und der erneute Runner-Preflight bestanden fail-closed:

- isolierte DB `h29077_mosa2_test`, Account `h29077_mosa2_test@localhost`,
  `127.0.0.1:3307`, Percona `8.0.26-16`;
- UTC, utf8mb4/utf8mb4_0900_ai_ci, vorgeschriebener strikter SQL-Modus,
  FOREIGN_KEY_CHECKS=1;
- erwartete Grants, keine Routinen, Trigger oder Events;
- vollständiger Schema-/Constraint-Vertrag: 16 Tabellen, 140 Spalten,
  16 Primärschlüssel, neun Unique-, 26 Sekundärindizes, 23 Fremdschlüssel,
  19 CHECKs; keine fremden Tabellen;
- Ledger exakt v1+v2 mit unveränderten Keys, Checksums und applied_at;
- alle 15 Nicht-Ledger-Tabellen vor dem Test leer.

Migrationen byte-identisch:

| Migration | SHA-256 | Ledger applied_at UTC |
| --- | --- | --- |
| 0001_core_asset_identity | `9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd` | 2026-10-18 14:10:22.604406 |
| 0002_market_current_history | `205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee` | 2026-10-19 08:02:39.939576 |

## Fachlicher Nachweis und Fixtures

| Prüfgruppe | Bestanden/gesamt |
| --- | ---: |
| Preflight-Gruppen | 5/5 |
| History/Dedupe | 2/2 |
| Current-Zeitregeln | 5/5 |
| Provenienz-Negativfälle | 6/6 |
| Mehr-Asset-Isolation | 1/1 |
| Atomarer Savepoint-Rollback | 1/1 |
| Lese-/Performancepfade | 3/3 |
| **Gesamt** | **23/23** |

Alle Prüfungen wurden in diesem zusammenhängenden Lauf erneut ausgeführt.
Die History-Inserts nutzen die gemeinsame Normalisierung und den identischen
rohen 32-Byte-SHA-256-Key. Ein identischer Replay erzeugte die tatsächliche
MySQL-Unique-Verletzung **errno 1062**, ohne zweite History-Zeile oder
Current-Änderung. Andere Fehler werden nicht als Replay unterdrückt.

Current bestand: erste Observation, neueres market_at, älteres market_at trotz
späterem observed_at, gleiches market_at mit neuerem observed_at sowie identische
Zeitpunkte bei anderem Payload. Unbekannte Asset-/Source-/Route-IDs,
falsche Asset-/Source-Zuordnung und unerlaubter Route-/Source-Wechsel wurden
vor jeder Mutation abgelehnt. Asset-A-Änderungen ließen B/C unverändert.
Ein absichtlicher Fehler nach dem History-INSERT bewies den echten
SAVEPOINT-Rollback ohne teilweise History-/Current-Änderung.

Alle Fixtures blieben in einer äußeren MySQL-Transaktion:
drei Assets, zwei Sources, vier funktionale Routes, acht funktionale
Observations und drei Current-Zeilen. Erst danach folgten zwei zusätzliche
gültige Routes, 768 Performance-Observations und 96 synthetische Bars.
Jedes Asset hatte zwei Sources/Routes mit derselben Verteilung über acht Tage,
16 Zeitpunkten je Tag/Source. Kein Current-Arbitrationspfad wurde ergänzt.

| Asset | Observations gesamt | Sources/Routes | Zeilen im History-Tagesfenster |
| --- | ---: | ---: | ---: |
| 101 | 262 | 2/2 | 35 |
| 102 | 257 | 2/2 | 32 |
| 103 | 257 | 2/2 | 32 |
| Gesamt | 776 | | |

## Natürliche Lesepläne und Latenzen

Jeder Leseweg bestand bereits im **ersten Versuch**. Fixture-Ausbau: **nein (0)**;
kein zweiter History-Plan erforderlich. Alle Pläne wurden vor dem Guard im
privaten Report gespeichert. Keine FORCE/USE/IGNORE-INDEX-Hints.

Die History-Query blieb unverändert:

```sql
SELECT id,market_at FROM m2_market_observations
WHERE asset_id=? AND market_at>=? AND market_at<?
ORDER BY market_at,id LIMIT 5
```

Parameter: `101`, `2026-01-02`, `2026-01-03`.

| Leseweg | Tatsächlicher Key | Zugriff | Geschätzte Zeilen | Extra |
| --- | --- | --- | ---: | --- |
| Current per asset_id | PRIMARY | const | 1 | NULL |
| History, Tagesfenster + LIMIT 5 | ix_market_observations_asset_time | range | 35 | Using where; Using index |
| Bars, Asset/1m/Zeitraum + LIMIT 5 | ix_market_bars_asset_time | range | 2 | Using where; Using index |

Kein Filesort und kein ungebundener Full Scan. Pro Pfad erfolgten ein Warmup
und 20 Messungen von execute+fetchAll mit monotonem `hrtime` in derselben
serverseitigen CLI-Laufzeit. p95 entspricht dem nächsthöheren Rang.

| Leseweg | Messungen | Ergebniszeilen | Median ms | p95 ms | Max ms | Budget ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current | 20 | 1 | 0.0962445 | 0.117369 | 0.137539 | <20 |
| History | 20 | 5 | 0.1667255 | 0.271995 | 0.306098 | <100 |
| Bars | 20 | 2 | 0.195615 | 0.222815 | 0.238689 | <100 |

Alle Budgets wurden eingehalten. Die maximale gemessene Zeit lag unter 0,31 ms.
Dies ist ein kleiner Funktions-/Latenznachweis, keine Lasttest-,
Parallelitäts-, Collector- oder Produktivfreigabe.

## Rollback, unabhängiger Endcheck und Bereinigung

Nach den Fachprüfungen erfolgte der vollständige äußere **ROLLBACK**, kein COMMIT
synthetischer Fachdaten. Dieselbe Verbindung und danach eine neue unabhängige
Verbindung bestätigten jeweils 16 Tabellen, unverändertes Ledger v1+v2,
unveränderte Grants und 15 exakt leere Nicht-Ledger-Tabellen.
Der vollständige Struktur-/Constraint-Vertrag blieb unverändert; keine
Routinen/Trigger/Events. Nur AUTO_INCREMENT-Tabellenoptionen unterschieden sich
als nichtfachlicher Insert-/Rollback-Nebeneffekt. Ausschließlich diese Option
wurde im Strukturvergleich normalisiert. Kein Zähler-Reset oder Reparatur-DDL.

Das Secret wurde automatisch entfernt. Anschließend wurden alle 15 übrigen
temporären privaten Dateien einschließlich access.php, Formularnachweis,
Preflight, Locks, Quellkopien und Payload sowie der Web-Einstieg entfernt.
Ein einzelner secretfreier privater Originalreport bleibt mit 0700/0600 erhalten;
sein SHA-256 blieb beim Bereinigen unverändert:
`74b78381f4778b2c4ad8cd56c1c2d0f41e09905a1de47c3b469592cd23c077f5`.
Keine privaten Serverpfade oder Credentials werden veröffentlicht.

Der temporäre Einstieg liefert 404. Die permanente Testhauptseite ist erreichbar,
ihre Datei unverändert und der Stufe-1-Schutz weiterhin aktiv (ohne Anmeldung 401).

Keine echten MOSA-Daten, keine Produktion, keine Phase 3D.
Die lokale Gesamtsuite bestand 142/143 Tests; ausschließlich der bekannte
Windows-POSIX-Dateirechtefall `budget_not_private` weicht ab. Dateivalidierung,
Diff-Prüfung und PHP-Lints aller drei Phase-3C-PHP-Dateien bestanden.
Repository-/Linux-Nachweis, Abschlusscommit und Run-ID werden nach dem
Abschlusscommit in Issue #14 dokumentiert. Deploy muss skipped bleiben.

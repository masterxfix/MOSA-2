# Phase 3D-C – erster kontrollierter echter Testimport

Am 19.10.2026 erfolgreich in der isolierten MOSA-2-Testdatenbank ausgeführt.
Keine Produktion, keine breitere Migration und keine neue Providerabfrage.

## Beleg und unveränderte Auswahl

Die eingefrorene Auswahl A1/A2/A3, Snapshot- und Dry-Run-Fingerprints wurden
unverändert wiederverwendet. Die Stammdatenlücke wurde ausschließlich read-only
geschlossen: exakte private Instrument-/Identity-Datensätze belegen Namen;
gespeicherte Source-Registry-Typen belegen die Klasse. ETF-Referenzen wurden auf
Konflikte geprüft. Asset X und Asset Y: Name bestätigt, Klasse equity bestätigt.
Defaults: keine. Asset-Basiswährung: NULL, unabhängig von der Quote-Währung.
Das neue private Manifest referenziert den Basisreport und bindet die Belege.

## Live-Ergebnis

| Zielobjekt | Erster Import neu | Identischer Replay neu | Readback 1 und 2 |
|---|---:|---:|---:|
| Entities | 2 | 0 | 2 |
| Assets | 2 | 0 | 2 |
| ISIN-Identifier | 2 | 0 | 2 |
| Sources | 2 | 0 | 2 |
| Routes | 3 | 0 | 3 |
| Observations | 3 | 0 | 3 |
| Checkpoints | 2 | 0 | 2 |
| Current | 0 | 0 | 0 |
| Bars | 0 | 0 | 0 |

Alle übrigen ungenutzten Fachtabellen bleiben leer. Die drei nativen Observations
umfassen genau einen NOK- und zwei EUR-Fälle, keine Derived-/FX-/GBX-/XXX-/Bars-Fälle.
A1/A2/A3 wurden privat vollständig gegen die Zielzeilen geprüft: Asset-Identifier,
Source, Route, Preis, bid/ask/volume, Währung, beide Zeiten und kanonischer Dedupe-Key.
Reale Namen, ISINs, Quellreferenzen und Einzelwerte bleiben außerhalb des Repositories.

Preflight: erwartete isolierte Identität, Loopback-Port, Serverversion,
UTC, utf8mb4/utf8mb4_0900_ai_ci, strikter SQL-Modus, Fremdschlüsselprüfung und
Grants bestätigt; keine Routinen, Trigger oder Events. 16 Tabellen, 140 Spalten;
alle 15 Fachtabellen vor dem ersten Write leer. Vollständiger Strukturvertrag
und unveränderte Migrationen 0001/0002 geprüft. Ledger exakt v1+v2 einschließlich
Checksums und applied_at unverändert; keine DDL- oder Ledger-Schreibvorgänge.

Erster Import: genau eine erfolgreiche Transaktion und COMMIT nach vollständigem
Postcheck und privatem Report. Danach unabhängiger Readback über neue Verbindung.
Zweiter Import: exakt dasselbe Manifest in eigener Transaktion, drei Dedupe-Replays,
null neue Zeilen in allen sieben freigegebenen Tabellen. Keine UPDATEs.
Zweiter unabhängiger Readback: Fachwerte und sämtliche Zeitstempel exakt identisch.
AUTO_INCREMENT-Metadaten wurden separat verglichen und blieben ebenfalls gleich.
Das kurzlebige DB-Secret wurde im finally-Pfad entfernt.

## Aussagegrenze und Validierung

Dies belegt nur die feste kleine Stichprobe. Current-Routenauswahl, Bars,
breitere Migration, Depot, News, KI und Produktion bleiben gesondert freizugeben.
Die öffentliche Testhomepage bildet ausschließlich diesen belegten Stand ab.

Importer-/Stammdaten-Regressionen verwenden ausschließlich synthetische Fixtures.
Lokaler vollständiger Testlauf und Linux-Nachweis des Abschlusscommits werden
mit Run-ID im zugehörigen Issue #17 dokumentiert. Der bekannte Windows-Unterschied
budget_not_private ersetzt keinen Linux-Nachweis. Homepage-Transferhash,
sichtbare Darstellung, Zugriffsschutz und Gateway-Aufräumprüfung werden dort
separat als Live-Belege festgehalten.

Die native Kontrollzentrum-Zuordnung fehlte. Es wurden keine IDs oder Ereignisse
rekonstruiert. Der Nutzer hat die Fortsetzung trotz dieser Erfassungslücke
ausdrücklich freigegeben; fachlicher Import und Telemetrie sind getrennte Belege.

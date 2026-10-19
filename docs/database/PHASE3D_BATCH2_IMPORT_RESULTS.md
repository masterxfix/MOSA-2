# Phase 3D-E – Paket 2 erfolgreich testimportiert

**Status:** Am 19.10.2026 separat freigegebenes Paket mit exakt P2-A1/P2-A2/P2-A3
erfolgreich in die isolierte Testdatenbank übernommen. Kein Produktionsimport.

## Vorprüfung und gemeinsamer Vertrag

Die drei vorhandenen lokalen Importer-/Fixture-/Teständerungen wurden erhalten
und geprüft. Paketmanifest, Eligibility, alle Parent-Fingerprints, ursprünglicher
Snapshot/Dry Run und Phase-3D-C-Zielreport stimmen. Zwei erneute Offline-Auswertungen
sind bytegleich zum eingefrorenen Plan; keine Neuauswahl oder Ersatzkandidaten.

Der vorherige Versuch hatte vor jedem Write gestoppt. Sein unabhängiger Fehler-
Readback bestätigt Paket 1 unverändert. Der korrigierte Vergleich kanonisiert
verschachtelte Maps rekursiv; Listenreihenfolge und skalare Typen bleiben strikt.
Zusätzliche/fehlende Keys und geänderte Werte sperren weiterhin. Regressionen
prüfen auch Integer/Float/String/Boolean-Unterschiede. Der reale Fehler-Readback
besteht diesen Vergleich offline. Vollständige lokale Suite vor neuem Live-Zugriff:
214/215, ausschließlich zugelassene vorhandene Windows-Abweichung `budget_not_private`.
PHP-Lints, Webdatei-Validierung und diff-check erfolgreich.

Ein gemeinsamer kleiner Importpfad erhält den Paket-1-Vertrag und unterstützt
eine fingerprintgebundene nichtleere Baseline. Der neue allgemeine Stream heißt
`phase3d_market_migration_v1`; der Paket-1-Stream bleibt vollständig unverändert.
Bestehende Katalogzeitstempel werden nur aus der gebundenen Baseline übernommen,
niemals aus einer unbekannten aktuellen Zeile. Fachliche Konflikte bleiben gesperrt.

## Persistenter Nachweis

| Fachobjekt | Paket-1-Baseline | Paket-2-Zuwachs | Gesamt nach Import / Replay |
| --- | ---: | ---: | ---: |
| Entities | 2 | 3 | 5 |
| Assets (neue Klassen explizit equity) | 2 | 3 | 5 |
| ISIN-Identifier | 2 | 3 | 5 |
| Sources | 2 | 1 | 3 |
| Routes | 3 | 3 | 6 |
| Observations | 3 | 3 | 6 |
| Checkpoints | 2 | 2 | 4 |
| Current | 0 | 0 | 0 |
| Bars | 0 | 0 | 0 |
| Ledger-Einträge | 2 | 0 | 2 |

Eine bestehende Source wurde vollständig geprüft und ohne UPDATE wiederverwendet;
eine neue Source wurde angelegt. Die drei neuen Assets erhalten reale erzeugte IDs,
belegte Namen, aktive Equity-Verträge und `base_currency = NULL`. Drei globale
primäre ISIN-Identifier ohne erfundene Sourcebindung. Bei Routes wurden beide
Unique-Verträge geprüft; keine Current-Prioritätsregel abgeleitet.

Baseline-Preflight bestätigt die isolierte Identität, Server-/Session-/Grants-
Verträge, keine Routinen/Trigger/Events, exakt 16 Tabellen und 140 Spalten,
vollständige Constraints und unveränderte Migrationen 0001/0002. Ledger exakt
v1+v2 einschließlich Checksums/applied_at. Sämtliche Paket-1-Fachwerte, IDs,
Dedupe-Keys, Checkpoints und Zeitstempel entsprechen dem privaten Abschlussreport.
Keine unbekannte zusätzliche Zeile wurde akzeptiert.

Der neue Auftrag führte genau einen neuen ersten Import aus: eine Transaktion,
vollständiger Postcheck und privates resolved Manifest vor COMMIT. Finale IDs,
kanonische Payloads und drei finale 32-Byte-Dedupe-Keys stammen ausschließlich
aus der zentralen Phase-3C-Normalisierung und Dedupe-Funktion mit echten Ziel-IDs.
Zwei neue Checkpoints, je verwendeter Paket-2-Source einer: deterministischer
Manifest-Cursor, maximale belegte observed_at-Watermark und festes import_at.

Readback 1 über neue Verbindung bestätigt den Transaktionsstand vollständig.
Identischer Manifest-Replay in eigener Transaktion erkennt drei Duplikate und
erzeugt **in allen sieben erlaubten Tabellen null neue Zeilen**, ohne UPDATE.
Readback 2 über eine weitere neue Verbindung ist fachlich und zeitlich identisch.
AUTO_INCREMENT-Metadaten blieben beim Replay ebenfalls gleich. Paket-1-Werte
und Paket-1-Checkpoints blieben vollständig unverändert. Privater Quelle↔Ziel-
Vergleich bestätigt alle drei Kandidaten einschließlich Katalog, Preisen,
Währung, Zeiten, optionalen Werten, kanonischem Payload und Dedupe-Hexwert.

Relationships, Files, Events, Jobs, Job Runs und Module State bleiben leer.
Keine DDL, keine Ledger-Schreibaktion, keine Current-/Bars-Projektion.

## Schutz und Aussagegrenze

HTTPS-/POST-/Origin-/CSRF-geschützter Gateway mit Secure/HttpOnly/SameSite Strict,
no-store/noindex und privaten temporären Dateien. Referrer-Richtlinie verhindert
keinen gültigen Origin-Nachweis. Secretfreier Formular-Probelauf erfolgreich mit
0 DB-Verbindungen/0 Writes; Passwort ausschließlich durch den Nutzer im Formular,
kurzlebig genutzt und entfernt. Gateway, Zugriffskonfiguration, Formular-Proof,
Locks, Sessions und temporäre ausführbare Dateien bereinigt; frischer Aufruf 404.
Nur geschützte secretfreie private Nachweise bleiben erhalten.

Reale Namen, ISINs, Benutzerkontexte, externe IDs und Einzelwerte bleiben privat.
Die öffentliche Testhomepage bildet den belegten Gesamtstand mit unveränderter
Latenzanzeige ab; ihre Veröffentlichung folgt erst auf Abschlusscommit und grünen
Linux-Nachweis. Transferhash, sichtbare Darstellung und HTTP-401-Schutz werden
separat im zugehörigen Issue #20 belegt. Keine Produktion, keine breitere Migration,
kein Collector/Scheduler und kein Provider-Fetch. Weitere Pakete benötigen eine
eigene Freigabe; Current-Routenauswahl und Bars bleiben offen.

Abschlusscommit, vollständiger abschließender Windows-/Linux-Teststand und Run-ID
werden in Issue #20 dokumentiert. Die native Kontrollzentrum-Zuordnung fehlt;
keine IDs, Ereignisse oder Zeitpunkte wurden rekonstruiert.

# Qualifizierte HTML-Berichte mit kompakter Evidenz

Vorbereitet auf Basis `afe4254daa201193f8eb4373a8057c85b7c9e77f`.
Ein Offline-Erfolg ist kein Dogado-Importnachweis. Live-Ergebnis ausschließlich
aus dem einmaligen manuellen Lauf und dessen unabhängigem Readback ableiten.

## Schema 6 und getrennte Provenienz

Keine Migration und keine Umdeutung des Originalhashes:

| Datensatz | Bedeutung |
| --- | --- |
| `m2_provider_fetches.payload_sha256/payload_bytes/content_type` | Hash, Größe und MIME der tatsächlich erhaltenen vollständigen HTTP-Antwort; diese Bytes werden nicht gespeichert |
| `m2_provider_fetches.file_id` | FK auf den dauerhaft gespeicherten Nachweis; seine Rolle ist über den versionierten Files-Backendvertrag eindeutig |
| `m2_files.storage_backend=dogado_private_evidence_json_v1` | Abgeleitetes Evidence-JSON, ausdrücklich keine Originalantwort |
| `m2_files.sha256/byte_size/mime_type` | SHA-256 und Größe der exakten gespeicherten JSON-Bytes, `application/json` |
| Observation `field_path` | Index des Evidence-Fakts und ursprüngliche HTML-Tabellen-/Zeilen-/Spaltenposition |

Das JSON (`mosa2-fundamental-evidence-v1`, `kind=derived_evidence`) enthält
HTTP-Quelle, reale Abruf-/Erfassungszeit, Antwortmetadaten und `retained=false`,
Emittentenidentität, Drittanbieterklassifikation, Parserversion sowie pro Fakt
Originalbezeichnung/-wert/-einheit, Periode, Position, normalisierten Wert und
Prüfstatus. Keine Volltexte und keine ungenutzten HTML-Inhalte.
Der gemeinsame PHP-Core prüft JSON-Hash/-Größe, Antwortmetadaten, Parser und
jede Faktenbindung vor dem Schreiben. Beim unabhängigen Readback werden auch
Files und Fetches gegen ihre getrennten Sollwerte geprüft. Nur danach werden
die bestätigten öffentlichen Finanzzahlen für die angeforderte KI-Einordnung
ausgegeben. Dafür entsteht keine KI-Tabelle und kein externer KI-Aufruf.

Das bestehende Files-Schema besitzt freie versionierbare Backendbezeichnungen
und eigene Hash-/Größenfelder. Das Fetch-Schema hat eigene Antwortfelder und
erzwingt keine Gleichheit beider Hashes. Deshalb ist keine Tabellenänderung
erforderlich. Legacy-Backend `dogado_private_file` behält seinen Originalvertrag.
Migrationen und Ledger bleiben unverändert.

## Ausführung und Quelle

Gemeinsamer Workflow `fundamentals-reports.yml`, einzig freigegebener Schlüssel
`droneshield-html-fy-2025`, exakter Main-Commit, Versuch 1 und passende
`MOSA2-REPORTS-droneshield-html-fy-2025:<commit>`-Autorisierung.
Eine neue exklusive Verbrauchskennung verhindert Wiederholung. Bestehende
Archiv-Schutzfunktionen (Host-Pinning, feste Pfade, Owner/Mode, no-follow,
exclusive create, fsync, unabhängiger Hash-Readback) werden wiederverwendet.
Neue Dateien heißen `evidence.json` und `evidence-metadata.json`, nicht
`response.body`. Evidence maximal 128 KiB, maximal 256 Fakten.

Genau ein anonymer HTML-GET ohne Weiterleitung, Anmeldung oder Retry:
https://financialfilings.com/filings/droneshield-limited/annual-report/2026/42833624/

Financial Filings ist ein unabhängiger Drittanbieter. Die Wiedergabe wird nicht
als direkt bei DroneShield/ASX abgefragt oder unabhängig mit dem Original
verglichen ausgegeben. Keine PDF-Anfrage oder -Extraktion. Nichtöffentliche,
fehlerhafte oder nicht qualifizierbare Antworten führen zum Stopp; kein Umgehen
von Zugangsbeschränkungen. Nur erforderliche Faktendaten werden behalten.

Qualifikation: DroneShield Limited, Jahresbericht 2025 mit Jahresende
31.12.2025, ausdrückliche AUD-Angabe, getrennte FY2025-/FY2024-Spalten.
Explizite Tabellenpositionen statt Zusammenziehen von Zahlentexten.
Konsolidierte Ergebnis-/Cashflow-Rechnungen haben für semantisch identische
Kennzahlen Vorrang vor gerundeten Financial Highlights. Widersprüche innerhalb
derselben Priorität stoppen. EBITDA/Underlying EBITDA bleiben getrennt;
Cash and Term Deposits wird nicht als Cashflow übernommen. Fehlende oder
mehrdeutige Werte werden ausgelassen; es gibt keine Ergebniszahlen im Adapter.
FY2025 und FY2024 haben jeweils 01.01.–31.12.; AUD wird nicht umgerechnet.

Bestehende PNE 11/6, Zeiss 20/10, Markt 28/5 und Stammdaten werden über die
gemeinsamen Schutzprüfungen erhalten. Nach bestätigtem Commit: neue unabhängige
Read-only-DB-Verbindung, begrenzter Readback, Current-PK und History-Index mit
LIMIT 20 und Jahresgrenzen, EXPLAIN ANALYZE; Client-/Iteratorzeit getrennt.
Unbekanntes Ergebnis ist kein Anlass für Wiederholung.

## Prüfgrenzen

Fokussierte synthetische HTML-/Evidence-Tests prüfen präzise vs. gerundete Werte,
FY/AUD, Verwechslungen, unvollständige Paare, Konflikte, getrennte Hashes,
Manipulation, atomaren Abbruch, Replays, unabhängige Readback-Logik und den
gemeinsamen Ein-GET-Pfad ohne HTML-Speicherung. Danach einmalig die relevanten
Collector- und generischen PNE-/Zeiss-Regressionen. Keine PDF-Gesamtsuite.
Die tatsächliche Drittanbieter-HTML-Struktur und Erreichbarkeit sind erst mit
dem einzigen Live-GET nachgewiesen; bei Abweichung stoppen statt erneut abrufen.
Keine Website-/Designänderung, kein Deployment und kein Dauerbetrieb.

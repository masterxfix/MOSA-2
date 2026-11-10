# Issue #61 – Kontrollierter Reset der MOSA-2-Testdaten

Ziel: `h29077_mosa2_test` auf dem fest gebundenen Dogado-Testhost,
MySQL `8.0.26-16`, Port 3307, Schema 6. Der Reset darf ausschließlich
Fachdaten leeren; DDL, andere Datenbanken und Browser-Nutzerdaten bleiben
außerhalb des Auftrags.

Einzige vorgesehene technische Ausnahme: `m2_schema_migrations` mit sechs
Zeilen, Versionen 0001–0006. Das Ledger bindet die unveränderte physische
Struktur an die geprüften Migrationsdateien. Der deaktivierte Job in
`m2_jobs` und die Collector-Sperrzeile in `m2_collector_state` sind
Fach-/Betriebsdaten und keine Ausnahmen.

## Ausgangsinventar

[Leselauf 42778002914](https://github.com/masterxfix/MOSA-2/actions/runs/42778002914):
26 InnoDB-Tabellen, 310 Spalten, 26 Primärschlüssel, 19 Unique- und 64 weitere
Indizes, 60 Fremdschlüssel und 62 Checks. Die SHA-256-Signaturen pro Tabelle
und für das Ledger sind im Leselauf dokumentiert. Null DB-Events, Trigger
oder Routinen, null aktivierte DB-Jobs und null laufende Jobzeilen. Die
Sitzungsliste ist auf das geprüfte Datenbankkonto beschränkt.

| Tabelle | Ausgangszeilen |
| --- | ---: |
| `m2_asset_identifiers` | 9 |
| `m2_asset_source_routes` | 19 |
| `m2_assets` | 9 |
| `m2_collector_cycles` | 0 |
| `m2_collector_days` | 0 |
| `m2_collector_requests` | 0 |
| `m2_collector_state` | 1 |
| `m2_entities` | 9 |
| `m2_events` | 0 |
| `m2_files` | 16 |
| `m2_fundamental_current` | 60 |
| `m2_fundamental_metrics` | 27 |
| `m2_fundamental_observations` | 113 |
| `m2_fundamental_units` | 11 |
| `m2_job_runs` | 0 |
| `m2_jobs` | 1 |
| `m2_market_bars` | 0 |
| `m2_market_current` | 6 |
| `m2_market_observations` | 29 |
| `m2_module_state` | 1 |
| `m2_provider_fetches` | 16 |
| `m2_relationships` | 0 |
| `m2_schema_migrations` | 6 |
| `m2_sources` | 16 |
| `m2_sync_checkpoints` | 5 |
| `m2_units` | 4 |
| **Summe** | **358** |

## Verriegelte Auslöser

- 25 GitHub-Workflows für M2-Schreiber, Importe, geplante Historie und alte
  Wartungsläufe wurden bei GitHub auf `disabled_manually` gesetzt. Es gab
  keine laufenden, wartenden oder angeforderten Schreibjobs.
- Die M2-Testsite wurde über die [freigegebenen Dateien](https://github.com/masterxfix/MOSA-2/actions/runs/42777436321)
  aktualisiert. Das [letzte Deployment](https://github.com/masterxfix/MOSA-2/actions/runs/42777865652)
  enthält den korrigierten Marktdaten-Hinweis. Der Testsite-Workflow ist
  danach gesperrt, damit eine frühere Revision die Sperren nicht zurückrollt.
- Das manuelle ISIN-Formular und der Browser-Cache bleiben nutzbar. Die
  Browser-Timer, Startsteuerung und History-Formulare sind entfernt.
  Altes Browser-JavaScript kann den Kurs-Endpunkt nicht mehr aufrufen.
  History-POST und Codex-Status-Ingest sind auf der M2-Testsite gesperrt;
  die Importmodule und das Codex-Modell bleiben erhalten.
- Plesk: neun sichtbare geplante Aufgaben, kein M2-Treffer.
  Dogado: kein M2-Eintrag im sichtbaren Benutzer-Crontab oder in den
  lesbaren systemd-Unit-Dateien. Die Sicht auf laufende systemd-Timer
  und auf MySQL-Sitzungen anderer Konten bleibt unvollständig.

Chrome über die echte Testsite: Startseite 97 ms, Marktdaten 109 ms,
Fundamentaldaten 176 ms. Der manuelle Test lieferte einen Kurs. Nur die
temporäre Test-ISIN wurde aus dem Browser entfernt.

Bei fehlender vollständiger Inventur der M2-Schreiber oder fehlender
verifizierter Sicherung darf kein Reset gestartet werden. `main` und
PR #60 bleiben von diesem Arbeitsbranch getrennt.

## Geprüfte Sicherung

[Backup- und Restore-Nachweis 42778639026](https://github.com/masterxfix/MOSA-2/actions/runs/42778639026),
Commit `debaa8ef508b80b63c28a781a4de0fae160ccf0d`. Vollständiger Schema-6-Export
unter Lesesperre für genau die 26 Zieltabelle(n); verschlüsseltes Readback aus
dem privaten Dogado-Verzeichnis und vollständiger DDL- und Datenvergleich nach
Wiederherstellung in einer netzisolierten MySQL-8-Instanz. Die isolierte Instanz
wurde nach dem Vergleich entfernt. Null Schreibzugriffe auf die Live-Datenbank.

- SQL-Dump SHA-256: `7304bd0ca6d70bb0fe9be48aecdedf8f9cdd744f5eaecc6d5096938629094e08`
- Verschlüsselte Datei SHA-256: `e34d43c5b29136b21757a8a15b5d7f6dcb7c821bdd5cab8035b4955f1c43890f`
- Manifest SHA-256: `6e40b6e9c59ec98691b2815239fcdedff9c400f2e89372e7dd4389d85efa68de`

Aufbewahrung: höchstens sieben Tage bis 17.11.2026, 07:56 UTC. Die Sicherung
liegt außerhalb des Webroots im privaten Dogado-Verzeichnis. Der
Wiederherstellungsschlüssel ist getrennt im geschützten Windows-Benutzerkontext
hinterlegt. Die Löschfrist ist im Manifest vermerkt; es gibt dafür keinen
neuen automatischen Auslöser.

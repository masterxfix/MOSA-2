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

TABLE_CONTENT

## Verriegelte Auslöser

- 25 GitHub-Workflows für M2-Schreiber, Importe, geplante Historie und alte
  Wartungsläufe wurden bei GitHub auf `disabled_manually` gesetzt. Es gab
  keine laufenden, wartenden oder angeforderten Schreibjobs.
- Die M2-Testsite wurde über die [freigegebenen Dateien](https://github.com/masterxfix/MOSA-2/actions/runs/42777436321)
  aktualisiert. Der [Marktdaten-Hinweis](https://github.com/masterxfix/MOSA-2/actions/runs/42777865652)
  und der [abschließende Kompatibilitätsstand](https://github.com/masterxfix/MOSA-2/actions/runs/42779346579)
  wurden separat ausgerollt. Der Testsite-Workflow wurde wieder gesperrt,
  damit eine frühere Revision die Sperren nicht zurückrollt.
- Das manuelle ISIN-Formular und der Browser-Cache bleiben nutzbar. Die
  Browser-Timer, Startsteuerung und History-Formulare sind entfernt.
  Altes Browser-JavaScript kann den Kurs-Endpunkt nicht mehr aufrufen.
  History-POST und Codex-Status-Ingest sind auf der M2-Testsite gesperrt;
  die Importmodule und das Codex-Modell bleiben erhalten.
- Plesk: neun sichtbare geplante Aufgaben, kein M2-Treffer.
  Dogado: kein M2-Eintrag im sichtbaren Benutzer-Crontab oder in den
  lesbaren systemd-Unit-Dateien. Die Sicht auf laufende systemd-Timer
  und auf MySQL-Sitzungen anderer Konten bleibt unvollständig.

Chrome über die echte Testsite: Startseite 97 ms, Marktdaten zuletzt 72 ms,
Fundamentaldaten zuletzt 178 ms, jeweils mit vollständiger Anzeige.
Der manuelle Test lieferte einen Kurs. Nur die temporäre Test-ISIN wurde
aus dem Browser entfernt. Die offizielle Berichtsverlinkung mit Kennzeichen
„Manuell“ ist auf der Testsite erhalten.

GitHub-Readback am Ende: 53 Workflows im M2-Testumfang gesperrt, einschließlich
des einmaligen Sicherungs-/Lesewegs und der CI-Auslöser. Null laufende und
keine wartenden Läufe. Der separate Produktionsworkflow blieb unverändert.

Diese Sperren galten auch für die spätere einmalige Reset-Ausführung.
`main` und PR #60 blieben unverändert.

## Geprüfte Sicherung

[Backup- und Restore-Nachweis 42778639026](https://github.com/masterxfix/MOSA-2/actions/runs/42778639026),
Commit `debaa8ef508b80b63c28a781a4de0fae160ccf0d`. Vollständiger Schema-6-Export
unter Lesesperre für genau die 26 Zieltabellen; verschlüsseltes Readback aus
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

## Unabhängiger Readback vor dem Reset

[Leselauf 42778982325](https://github.com/masterxfix/MOSA-2/actions/runs/42778982325)
nach den Seitenaufrufen und der manuellen Abfrage: alle 26 Zeilenzahlen,
26 Schemasignaturen und die Signatur des Migrationsledgers stimmen mit dem
Ausgangsinventar überein. Es sind weiter 358 Zeilen vorhanden. Das Webkonto
hat nur Leserechte auf die Testdatenbank. Die im Dogado-Konto sichtbare
Prozessliste zeigte keinen M2-Schreiber.

## Ausführung und unabhängiger Readback nach dem Reset

Der aktualisierte Auftrag vom 10.11.2026 ersetzte die frühere Sperre. Die
vorhandene Sicherung wurde verwendet. Ein einziger [Resetlauf 42781660635](https://github.com/masterxfix/MOSA-2/actions/runs/42781660635)
unter Commit `e1e9e0c62f802a66c532becc3558047a805ac790` hat 352 Zeilen gelöscht. Die Prüfungen in der
isolierten Instanz bestanden vor der Live-Ausführung. Die Live-Transaktion
wurde bestätigt; eine neu aufgebaute Read-only-Verbindung hat die
Tabellenwerte oben und unveränderte Struktur bestätigt.

- Schema SHA-256: `9070f22389cccb33c1fcde65c2105e17da0371e2b28af61534ebc44efaff1edc`
- Ledger SHA-256: `8527723c195d78daec825e83397b2b7e5ebe35c4f7294fc42b62882d8597c018`
- 25 Tabellen mit null Zeilen, Ledger mit genau sechs Zeilen; alle 11
  Waisenprüfungen ergaben null. Der einmalige Reset-Auslöser ist wieder
  bei GitHub deaktiviert und im Workflow hart gesperrt.

Chrome nach dem Reset: Startseite 113 ms, Marktdaten 67 ms und beim
abschließenden Aufruf 31 ms, inklusive Datenabruf. Ein manueller
ISIN-Test lieferte einen Kurs. Nur die Test-ISIN wurde wieder entfernt.
Der vorhandene Browser-Cache blieb erhalten. Der leere Fundamentalbestand
führt im bestehenden Reader zu „Fundamentaldaten nicht verfügbar“; für
diese Seite liegt keine erfolgreiche Ladezeitmessung vor. Es gab für den
Reset keine Änderung der Webanwendung und kein Testsite-Deployment.

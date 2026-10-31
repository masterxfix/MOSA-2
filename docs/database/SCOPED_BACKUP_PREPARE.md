# Schema-begrenztes MOSA-2-Backup mit unabhängigem Recovery-Schlüssel

## Erreichter Stand

| Aussage | Stand |
| --- | --- |
| Eng begrenzter Backup-Weg technisch vorbereitet | JA |
| Isolierter vollständiger Export/Verschlüsselung/Restore | PASS, MySQL 8.0.46 |
| Echter Dogado-Export durchgeführt | NEIN |
| Echtes Dogado-Backup vorhanden | NEIN |
| Unabhängiger Restore echter Dogado-Daten | NEIN |
| Recovery-Secret eingerichtet / angefordert | NEIN / NEIN |
| Installation, Migration oder Betriebsaktivierung | NEIN |

Einziger Actions-Lauf dieses Auftrags:
[41211740525](https://github.com/masterxfix/MOSA-2/actions/runs/41211740525),
Job [124567992252](https://github.com/masterxfix/MOSA-2/actions/runs/41211740525/job/124567992252).
Geprüfter Kandidat: `d7c4fafc26e5dd91ad29344325b005f34e6b42db`.
Scope `backup-restore`, Stage `scoped`, read_preflight=false.
Die Dogado-/Berechtigungs-/Migrationsjobs wurden übersprungen.
Die früheren erfolgreichen Inventar- und Fundamentals-/Performance-Läufe wurden
nicht erneut ausgeführt. Das vorbereitete Live-Workflow wurde NICHT gestartet.

## Wiederverwendete Komponenten und feste Grenzen

Der historische `database_backup.IsolatedBackup`-Executor behält seine
GHA-/Isolationsflags, Container-UUID/-Hostname, Loopback/Port-, Root- und
Datenbank-/Target-Prüfungen. Sein bisheriger Backup-Aufruf hält unverändert
seinen globalen Lock ausschließlich auf dem synthetischen Dienst.
Er hat keinen Dogado-Exportmodus.

Nur vollständige begrenzte Aufnahme, exakte Typkodierung und Metadatenfunktionen
wurden zur gemeinsamen Wiederverwendung herausgezogen. Der neue schmale
`database_backup_scoped`-Ablauf benutzt dieselben:
- kanonischen Binär-/DECIMAL-/DATETIME(6)-/DATE-Repräsentationen und Zeilenhashes;
- ursprünglichen vollständigen Schema-/Ledger-/Unit-/Current-/Observation-Prüfer;
- AES-GCM/HKDF-Envelope aus `deploy_test_sftp.persist_backup`;
- Ed25519-signierten Manifest-, Hash- und Entschlüsselungsnachweis;
- unabhängigen Restore und Vollvergleich auf dem bewachten isolierten Dienst.

Kein zweiter allgemeiner Parser, SQL-Writer oder Backup-Dateiformat.
`database_backup_read.php` enthält den bisherigen gemeinsamen Evidence-Lesepfad.
Der bestehende isolierte PHP-Wrapper behält seine vollständigen Server-/Modusguards
und ruft jetzt diesen gemeinsamen Pfad auf. PDO-Evidenztypen werden auf beiden
Seiten explizit identisch gesetzt; keine Fakten werden verändert.
Der alte Standard-Restore verlangt weiterhin identische Quell-/Zielserverversionen.

Für den separaten externen Restore bleibt der Zielserver vollständig CI-isoliert.
Quell-UUID und Commit stammen aus dem authentifizierten Manifest und Recovery-Key.
Ein MySQL-8.0-Patchwechsel und der belegte Serverport dürfen ausschließlich in
den zwei bekannten Identitätsnachweisen explizit auf den Quellwert abgebildet
werden; die tatsächliche Zielidentität wird vorher unabhängig streng geprüft.
Kein Feld wird entfernt. Alle Inhalte, Ledger, SHOW CREATE/Constraints,
AUTO_INCREMENT, Objekte und Provenance bleiben vollständig zu vergleichen.
Diese Identitätsabbildung ist offline geprüft; ein tatsächlicher 8.0.26→8.0.46-
Restore privater Daten ist hier ausdrücklich NICHT nachgewiesen.

## Vorbereiteter späterer Live-Ablauf

Manuell, nicht zeitgesteuert:
`.github/workflows/database-backup-once.yml`.
Kein Export durch Import, Webseite, Scheduler oder CI-Push.
Nur main, run_attempt=1, exakter expected_commit und ausdrückliches
`MOSA2-DB-BACKUP-ONCE:<vollcommit>`.
Der Ablauf benötigt außerdem einen gültigen extern signierten Ruhe-Nachweis
und die bestätigte private Aufbewahrung. Keine neue Quelle oder Zugangseinrichtung.

1. Vor Quellenzugriff: unabhängigen Recovery-Key, signierten Ruhe-Nachweis,
   restriktiven Runner-Pfad, Frist und freie Ressourcen prüfen.
2. Vorbereiteten isolierten Restore-Dienst und frisches Ziel prüfen.
3. Bestehenden `backup_permissions_remote`-Prüfer mit derselben gepinnten
   SSH-/Tunnelkonfiguration und vorhandenen MOSA_TEST-SFTP-/DB-Secrets verwenden.
   Kein Upload und keine Dateien/Verzeichnisse auf Dogado.
4. Ausschließlich `h29077_mosa2_test`, bekanntes Konto und geprüfte tatsächliche
   Identität MySQL 8.0.26-16/Serverport3307 zulassen. Frische Schema-/Ledger-
   Prüfung, 17 InnoDB-Tabellen, vollständige Objektsichtbarkeit, keine Routinen
   und keine erkennbaren Jobs/Schreiber/Sperrsignale verlangen.
5. Vollständige private Voraufnahme und dann genau einen schema-begrenzten Dump
   über denselben bestehenden Tunnel erzeugen. Keine Schleife oder Ersatzroute.
6. Vollständige Nachaufnahme exakt mit vorher vergleichen und Ruhe-Nachweis erneut
   prüfen. Bei Drift/Timeout/unklarem Ergebnis STOP ohne Veröffentlichung.
7. Unmittelbar verschlüsseln, signieren, entschlüsseln und Hashes/Manifest prüfen.
8. Auf frischem bewachtem CI-MySQL-Ziel mit vorhandenem eingeschränktem
   synthetischem Restore-Konto wiederherstellen und unabhängig vollständig vergleichen.
   Kein neuer Hosting-Benutzer; der bestehende temporäre Fixture-Kontoweg wird
   unverändert nur im wegwerfbaren Dienst wiederverwendet.
9. Nur vollständiger Erfolg ergibt `BACKUP_RESTORE_PASS`; erst danach exakt
   `backup.sealed.json` und `manifest.json` als Artefakt mit sieben Tagen Retention
   außerhalb Dogado hochladen. Kein SQL-/State-Klartext, Secret oder Schlüssel hochladen.

Der isolierte Test dieses Auftrags prüft den gemeinsamen Ablauf mit bewachtem
synthetischem Quelladapter. Die spezifische Dogado-Tunnel-/Kontoanbindung wird
hier nicht ausgeführt; ihre bisherige Inventarqualifikation wird wiederverwendet.
Der neue Live-Workflow ist technische Vorbereitung, kein durchgeführtes Backup
und keine Ausführungsfreigabe.

## Exportvertrag und Ressourcen

Ausschließlich fest vorgegebene Optionen für eine einzige Datenbank:

`--single-transaction --quick --skip-lock-tables --no-tablespaces
--set-gtid-purged=OFF --hex-blob --tz-utc --skip-routines --events --triggers
--default-character-set=utf8mb4 --column-statistics=0 --skip-comments
--skip-dump-date --skip-add-locks --skip-add-drop-table --complete-insert
--order-by-primary h29077_mosa2_test`

Kein globaler FLUSH-/LOCK-Aufruf am Quellserver, keine All-Databases-Option.
Das Weglassen von Routinen ist nur nach vollständigem Rechte-/Objektnachweis
ihrer Abwesenheit zulässig. Trigger und Events werden vollständig exportiert,
mit ihren Definitionen verglichen; der isolierte Event-Scheduler bleibt aus.

Dump-Client muss MySQL 8.0 sein. Das vorhandene DB-Passwort wird nur über
anonymes privates STDIN mit `--defaults-file=/dev/stdin` übergeben, weder
Kommandozeilenwert, persistente Konfigurationsdatei noch Passwort-Umgebungsvariable.
Andere Login-Dateien werden für diesen Client ausgeschlossen. Die Funktion zum
Prozessaufruf behält begrenzte anonyme private Dateien, Zeit-/Größenlimits und
unterdrückte Clientdiagnosen. Der isolierte Dump hat diesen STDIN-Mechanismus
tatsächlich mit dem vorhandenen synthetischen Socketkonto verwendet.

Bestehende Grenzen bleiben: SQL 8 MiB, vollständiger State 16 MiB, Envelope 36 MiB,
100000 Zeilen/Tabelle, 1 MiB/Zelle, 32 Objekte/Typ und endliche Prozesslimits.
Vor Beginn verlangt der neue Weg mindestens achtmal die Summe der maximalen
Dump-/State-/Envelopegrößen als freie Scratch-Reserve. Überschreitungen brechen ab,
statt Fakten abzuschneiden oder Limits still anzuheben.
Temporärer Runner-Pfad 0700, Dateien 0600, keine Symlinks. Quellpasswort nicht
im Kindprozess-Environment des Dumps; Recovery-Key nie im Paket.
Anonyme Scratchdateien werden geschlossen und Runner-Speicher wird entsorgt;
keine Behauptung forensischer SSD-Löschung.

## Recovery-Key: später separat einzurichten, NICHT in diesem Auftrag

Einrichtung erst in einem gesondert beauftragten Schritt:
1. Einen eigenständigen kryptografisch zufälligen 32-Byte-Schlüssel erzeugen,
   Darstellung genau 64 kleine Hexzeichen. Kein menschliches Passwort,
   kein SFTP-/DB-Passwort und keine Ableitung daraus.
2. Einmalig im Repository als Actions Secret
   **MOSA_TEST_DB_BACKUP_RECOVERY_KEY** hinterlegen.
3. Dieselbe Recovery-Schlüsselversion zusätzlich in einem sicheren externen
   Passwortmanager/Offline-Tresor außerhalb GitHub verwahren.
   Backup-ID, Quellcommit und Fingerprint des daraus abgeleiteten öffentlichen
   Ed25519-Prüfschlüssels dort zuordnen. Schlüsselrotation darf alte Kopien
   vor Ablauf/Prüfung der zugehörigen Sicherungen nicht vernichten.
4. Den externen Zugriff auf diese Kopie vor einer realen Sicherung prüfen.
   Ein nur in GitHub gespeichertes Secret ist kein unabhängiger Recovery-Nachweis.

Aus diesem eigenständigen Root-Key werden ausschließlich die vorhandenen
AES-GCM/HKDF- und getrennt kontextgebundenen Ed25519-Signaturmaterialien abgeleitet.
Die signierte Manifestprüfung vertraut dem extern verwahrten Recovery-Key,
niemals einem vom Paket selbst mitgelieferten Schlüssel.
Keine Schlüsselwerte, Eingabedialoge oder Secretänderungen wurden hier benötigt.

## Kontrollierte Schreib-/DDL-Ruhe: noch extern herzustellen

Eine leere Prozessliste bzw. PROCESS=NEIN beweist keine durchgehende Ruhe.
Vor realem Export müssen alle MOSA-2-Test-Writer und DDL-Zugänge tatsächlich
kontrolliert ruhig sein: Collector/Scheduler/manuelle Runs und direkte Clients.
Keine Untersuchung oder Stilllegung anderer Dogado-Datenbanken/MOSA-Dienste.

Der vorbereitete Weg verlangt eine von der verantwortlichen Stelle außerhalb
des Workflows signierte, maximal 900 Sekunden gültige Erklärung:
`purpose=MOSA2_SCHEMA4_BACKUP`, exakte Datenbank, geprüfter Vollcommit,
`all_test_writers_stopped=true`, `ddl_prohibited=true`,
issued_at/expires_at als UTC-Unixsekunden sowie eindeutige Laufkennung.
Die Ed25519-Signatur bindet die kanonische vollständige Erklärung.
Der Workflow stellt diese Erklärung NICHT selbst her und hält keine bloße
Unterschrift für einen technischen Stopp fremder Writer.
Kann die verantwortliche Stelle diese Bedingungen nicht tatsächlich sicherstellen,
darf kein gültiger Nachweis erteilt werden und der Export bleibt gesperrt.
Gültigkeit wird vor, während und nach dem Export erneut geprüft.

Ein lokaler Run-Claim verhindert Wiederholung im selben Arbeitsverzeichnis;
run_attempt=1 verhindert Actions-Re-runs, eine feste Concurrencygruppe parallele
Runs. Nach unbekanntem/fehlgeschlagenem Ergebnis kein automatischer Neuversuch.
Eine neue manuelle Ausführung benötigt erneut ausdrückliche Beauftragung und
einen frischen kontrollierten Ruhe-Nachweis. Keine konsumierten Collector-Marker ändern.

## Tatsächlicher isolierter Nachweis

Zehn fokussierte Offline-Tests PASS, zwei PHP-Syntaxprüfungen und Python-Syntax
der fünf betroffenen Module PASS. Bestehende CI-Modus-/Typ-/Prozessschutztests
wurden wiederverwendet. Genau ein gezielter MySQL-Integrationstest PASS.

Die vorhandene Fixture befüllt **alle 17 Tabellen**, enthält fünf gültige
Current-/Observation-v2-Ketten, Ledger1–4 mit Original-SQL-Hashes, große exakte
DECIMAL-Werte, Binärbytes inklusive NUL/High Bytes, Unicode/JSON und Mikrosekunden.
Für den routinenfreien Export werden nur im isolierten Fixture die beiden
synthetischen Routinen entfernt. Harmloser Trigger und deaktiviertes Event bleiben
erhalten und werden tatsächlich mitgesichert/restauriert.
Keine neue Benutzerart, Providerdaten, echte Konten oder Produktions-Secrets.

Nachgewiesen:
- Genau ein vollständiger synthetischer Dump, ohne globalen Exportlock.
  Frühere schemaweite Exportrechte-Qualifikation 39768976953 wird wiederverwendet;
  der aktuelle Dump verwendet das vorhandene isolierte Konto, kein neuer
  Dogado-Rechtebeweis.
- AES-GCM/HKDF-Verschlüsselung, Ed25519-Signatur und alle Hashes PASS.
- Gültiger synthetischer Recovery-Key entschlüsselt; falscher Key wird abgewiesen.
- Manipulierte/abgeschnittene Envelope- und Manifestdateien werden abgewiesen.
- Restore A frisch, unabhängig neu verbunden und vollständige Gleichheit von
  allen Zeilen, Werten, Schema/Constraints/AUTO_INCREMENT, Ledger, Objekten und
  Current-/Observation-Provenance PASS. Quelle vor/nach identisch.
- Ein mit gültigem Key neu signierter/verschlüsselter SQL-Dump ohne m2_files-
  INSERTs scheitert im frischen Target B ausdrücklich mit
  `RESTORE_VERIFICATION_FAILED / RESTORE_MISMATCH_ROWS`.
  Gleiche Tabellen-/Metadatenzahl genügt nicht; keine automatische Wiederholung.
- Aktueller Ergebniscode `BACKUP_RESTORE_PASS`, live_dogado_exports=0,
  source_export_calls=1, global_export_locks=0.

Die synthetischen verschlüsselten Testdateien und Testschlüssel werden durch die
vorhandene Fixture entsorgt; kein Artefakt mit privaten Daten oder Testschlüssel
hochgeladen. Eine reale langfristige Sicherung ist dadurch nicht entstanden.

## Nächster konkreter Schritt

Recovery-Key samt sicherer externer Kopie in einem separat freigegebenen
Einrichtungsschritt herstellen; anschließend tatsächliche kontrollierte
MOSA-2-Schreib-/DDL-Ruhe und Aufbewahrung verbindlich bestätigen.
Erst ein weiterer ausdrücklich autorisierter, exakt gebundener manueller
Live-Auftrag darf den vorbereiteten Workflow einmal starten.
Bis dahin bleibt echter Dogado-Export **NEIN** und Migration 0005/0006 gesperrt.

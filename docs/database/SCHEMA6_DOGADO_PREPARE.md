# Dogado Schema 4 -> 6: PREPARE, kein APPLY

## Beleggrenzen und einmaliger Bestandslauf

Quellstand: `2a5b22f547c16521cf7235b4ba82651dea815e3a`.
Migrationen 0001-0006 bleiben unverändert. Der isolierte MySQL-8.0.46-Nachweis
[41205801735](https://github.com/masterxfix/MOSA-2/actions/runs/41205801735)
wird wiederverwendet, nicht erneut ausgeführt. Das ist keine Dogado-Apply-Freigabe.

Der nur im Kandidatenbranch `codex/schema6-dogado-prepare` vorbereitete Scope
`schema6-prepare` im vorhandenen manuellen Workflow benutzt dieselbe
`backup_permissions_remote.py`-, SSH-Tunnel- und `Phase2\\connection`-Identitätsprüfung.
Genau ein Versuch, READ ONLY vor Bestandsabfragen, keine Installation oder Serverdateien.
Der historische Scope `backup-permissions` bleibt verfügbar.
Der Kandidat soll den exakten Schema-4-Vertrag mit dem gemeinsamen Metadatenprüfer prüfen,
Ledger 1-4 samt SQL-Hashes, alle 17 InnoDB-Tabellen und exakte Zeilenzähler.
Er benutzt dieselben Current-/Observation-/Route-/Unit-/Dedupe-/Provenanceprüfungen
wie die Website. Ausgegeben werden Identitäten, Status und einseitige Baseline-Hashes,
keine Preise, DB-IDs, Objektdefinitionen, SQL-Fehler oder Secrets.
Diese Fingerprints sind keine vollständigen Zeilenhashes aller Geschäftstabellen.

Erkennbare Jobs und zwei bestehende Collector-/Current-Sperrsignale werden gelesen.
Die Prozessabfrage ist ausdrücklich auf `DB=DATABASE()` beschränkt und gibt keine
SQL-Texte aus. Ohne globales PROCESS sieht sie nur das eigene Konto. Auch mit
PROCESS beweist eine Momentaufnahme keine durchgehende Schreib-/DDL-Ruhe.
Keine anderen Dogado-Datenbanken werden untersucht.

## Backup: qualifizierte Methode, noch kein operativer Live-Nachweis

Vorhandene Belege:
[MIGRATION_0005_PREPARE.md](MIGRATION_0005_PREPARE.md),
[BACKUP_RESTORE_PREPARE.md](BACKUP_RESTORE_PREPARE.md),
synthetischer Schema-Export/Restore
[39768976953](https://github.com/masterxfix/MOSA-2/actions/runs/39768976953).

Die dort dokumentierte `mysqldump --single-transaction --quick --skip-lock-tables
--no-tablespaces --set-gtid-purged=OFF --hex-blob --tz-utc --skip-routines`-Methode
bleibt nur bei vollständiger Metadatensichtbarkeit, routinenfreiem InnoDB-Bestand
und kontrollierter Schreib-/DDL-Ruhe geeignet. Weitere dort qualifizierte
Zeichensatz-/Event-/Trigger-Optionen unverändert übernehmen.
Schemaweites LOCK TABLES ersetzt weder globale RELOAD-/FLUSH_TABLES-Rechte noch
eine nachweislich ruhige Quelle; keine globale Sperre wird ausprobiert.

Der vorhandene `database_backup.py`-Executor ist absichtlich auf den synthetischen
CI-Dienst begrenzt. Diese Sicherungssperre wird nicht entfernt oder durch eine
zweite Live-Backup-Implementierung umgangen. Das vorhandene AES-GCM/HKDF- und
Ed25519/Hash-Verfahren ist wiederzuverwenden; temporäre synthetische Schlüssel
beweisen keine dauerhafte unabhängige Schlüsselverwahrung.
Vor einem Live-Export fehlen damit insbesondere der durchgehende Ruhe-Nachweis,
ein geprüfter operativer Adapter und nachvollziehbare Off-Host-Schlüsselverwahrung.
Ein kompatibler Client und freie Runner-Bytes werden gelesen; daraus folgt ohne
vollständige Export-/Verschlüsselungsgrößen kein ausreichender Ressourcenbeweis.
Bei fehlender Voraussetzung: STOP vor Export. Kein Dump, Artefakt oder Restoreversuch.

## Runtime-Kompatibilität: konkret vorzubereitende Erweiterung

| Komponente | Aktueller Vertrag | Konsequenz nach 0005/0006 |
| --- | --- | --- |
| Web-Reader Current/Observations | Gemeinsame validierte Publikation über Current; kein globaler Tabellensatz | Datenlesepfad verwendet unveränderte alte Tabellen; tatsächlicher Web-/Provenance-Readback nach Apply bleibt nötig |
| Installierter Schema-4-Einmalpfad | Exakt 17 Tabellen und Ledger 1-4; zuletzt erfolgreich 41198494118 | Kein erneuter Start gegen 21/26 Tabellen; historische Einmalmarker bleiben verbraucht |
| Schema-5-Release-Kandidat | Explizit Version 5, exakt 21 Tabellen, Ledger 1-5 | Unverändert gegen 26 Tabellen inkompatibel; kein Deployment in diesem Auftrag |
| Schema-6-Ziel | 26 Tabellen, Ledger 1-6 und exakt fünf neue Tabellen | Noch kein qualifizierter Runtime-/Release-Vertrag |

Konkrete minimale Erweiterung für einen späteren Implementierungsauftrag:
den bestehenden expliziten Vertrag in `market_collector/schema_contract.php`
um Version 6 mit exakt 26 Namen, sechs unveränderten SQL-SHA-256 und sechs
Ledger-Schlüsseln ergänzen. Versionen 3/4/5 unverändert exakt lassen.
Die bestehende strukturelle Schema-Prüfung und den bereits qualifizierten
0006-Metadatenvertrag wiederverwenden; keine unbekannten Tabellen/Ledger ignorieren.
Die gesperrten Bootstrap-Anker aus 0005 auch bei Version 6 vollständig prüfen.
`acquisitionAllowed`, Runtime-/Current-Opt-in und das geschlossene Release-Manifest
müssen Version 6 ausdrücklich behandeln; keine implizite Betriebsfreigabe aus
`version != 5`. Ein separater gepinnter Schema-6-Releasevertrag samt Abhängigkeiten
und fokussiertem Kompatibilitätsnachweis ist vor Apply erforderlich.
Bis dahin ist Runtime-Kompatibilität NICHT nachgewiesen; vorhandene Guards bleiben
unverändert. Kein neues Release wird installiert und kein Scheduler aktiviert.

## Späterer Applyplan: erst nach gesonderter ausdrücklicher Freigabe

1. Frische Identität, vollständige exakte Metadaten, Ledger 1-4 und unveränderte
   Migrationen prüfen; alle 17 Tabellen vollständig hashen, fünf Tradegate-
   Current-/Observation-Provenance samt Route-/Source-/Unit-Verträgen festhalten.
2. Kontrollierte Schreib-/DDL-Ruhe über alle MOSA-2-Zugänge für die gesamte
   Sicherung und Migration belegen. Bestehende MySQL-Migrations-/Current-Sperren
   koordinieren; nur kooperierende Named-Locks ersetzen keine Ruhegarantie.
3. Vollständiges verschlüsseltes Live-Backup mit vertrauenswürdiger Schlüssel-
   verwahrung, privater Aufbewahrung/Frist und authentifiziertem Manifest sichern.
   In frischer isolierter MySQL-8-Instanz alle Inhalte, Struktur, AUTO_INCREMENT,
   Ledger, Binär-/DECIMAL-/Zeitwerte und fünf Provenance-Ketten unabhängig vergleichen.
4. Explizit qualifizierten Schema-6-Runtime-/Releasevertrag bereitstellen und
   unveränderten Quellfingerprint unmittelbar vor DDL erneut bestätigen.
5. Unveränderte 0005: fünf DDL-Schritte einzeln protokollieren, danach die drei
   vorhandenen gesperrten Bootstrap-Schritte plus Ledger 5 atomar bestätigen.
   Exakt Schema 5/21 Tabellen und LOCKED/disabled/stop_latched prüfen.
6. Unveränderte 0006: fünf CREATE TABLE einzeln protokollieren und exakt gegen
   den qualifizierten Vertrag prüfen. Ledger 6 mit
   `0006_fundamentals_and_payload_provenance` und
   `55457063c72d20498a097d273b5465d34cfd8aba5b2c7c229a9673bfc0c4a60c`
   erst nach vollständigem Strukturbeweis atomar bestätigen. Keine Seeds.
7. Neue unabhängige READ-ONLY-Verbindung: exakt 26 Tabellen, Ledger 1-6,
   alle Constraints; alte Daten unverändert bis auf die geplanten 0005-Anker und
   Ledger-Ergänzungen, fünf Tradegate-Current-/Observation-Ketten unverändert.
   Tatsächliche bestehende Chrome-Anzeige kontrollieren, keine Providerabfragen.
8. Alle Collector-/Provider-/Scheduler-Sperren erhalten. Kein Betrieb durch
   Migration oder Runtime-Installation freigeben.

Mehrere MySQL-DDLs sind nicht atomar. Bei Teilfehler oder unbekannter Bestätigung:
STOP, bekannte letzte Schritte und unklaren Zustand dokumentieren; kein Retry,
kein automatisches DROP/Restore/Umschalten, kein behaupteter Rollback.
Ein späterer Read-only-Abgleich und ggf. Recovery benötigen einen eigenen Auftrag.

## Ergebnis des aktuellen Auftrags

**Status: BLOCKIERT.** Genau ein manueller Actions-Lauf, kein Rerun:
[41207129005](https://github.com/masterxfix/MOSA-2/actions/runs/41207129005),
Job [124554397679](https://github.com/masterxfix/MOSA-2/actions/runs/41207129005/job/124554397679),
Kandidat `0a24d5c466b05cf799a5058a819e6cb718b7bcb1`, Ergebnis failure.

Der einzige ausgeführte Job war `backup-permissions`; Offline-, Persistenz- und
Migrationsjobs wurden übersprungen. Er lief mit `schema6-prepare`, nicht mit
APPLY. Das bestätigte erste Fehlersignal am 31.10.2026, 13:47:29 UTC lautet
`SCHEMA6_PREPARE_INVENTORY_REJECTED`; Exitcode 1. Es liegt nach Verbindung,
Identitätsprüfung, READ-ONLY-Nachweis und Grant-/Objektabfragen, innerhalb
der neuen Bestandsprüfung. Diese Position beweist die vorhandene sichere
Verbindung zur erlaubten Testdatenbank und deren fest geprüfte MySQL-Version
`8.0.26-16`. Sie beweist NICHT das erfolgreiche Inventar.

Der Catch-Pfad gibt absichtlich keine SQL-Fehler oder privaten Daten aus, bewahrt
aber auch keinen genaueren Unterabschnitt dieser Bestandsprüfung. Die konkrete
innere Ursache lässt sich daher aus diesem Lauf nicht bestimmen. Weder
Schemaabweichung, Rechteproblem noch Timeout werden ohne Beleg behauptet.
Keine weitere Diagnose-Action, kein anderer DB-Zugriff und kein Export wurden gestartet.

| Nachweis | Tatsächlich erreicht |
| --- | --- |
| Sichere Dogado-Identität / MySQL | Verbindung und fest geprüfte Version 8.0.26-16; READ ONLY vor Inventar erreicht |
| Aktuelle Dogado-Schemaversion / Ledger / Zeilenzähler | NICHT erneut bestätigt; letzter erfolgreicher Betriebsnachweis Schema 4 bleibt historisch |
| Aktuelle vollständige Objektsichtbarkeit / Rechte | Kein vollständiger neuer Ergebnisbericht; früherer Berechtigungsnachweis 39767648960 bleibt historisch |
| Fünf aktuelle Current-/Observation-Ketten | In diesem Lauf NICHT bestätigt; historischer Fünfernachweis 41198494118 wird nicht ersetzt |
| Durchgehende Schreib-/DDL-Ruhe | NICHT nachgewiesen |
| Exportclient / ausreichende Ressourcen / Schlüsselverwahrung | In diesem Lauf NICHT bestätigt |
| Live-Backup technisch freigegeben | NEIN; Voraussetzungen unvollständig |
| Tatsächlicher Export / verschlüsseltes Backup / Artefakt | NEIN; jeweils 0 |
| Unabhängiger Restore des echten Bestands | NEIN; 0 Versuche |
| Schema-6-Runtime | NICHT kompatibel qualifiziert; genaue notwendige Erweiterung oben bestimmt |
| Dogado-Apply 0005 + 0006 | BLOCKIERT; im nächsten Auftrag noch nicht sicher ausführbar |

Neue Offline-Guards: **6/6 PASS**, PHP-Syntax beider betroffener Dateien PASS.
Der erste lokale Testversuch hatte nur im eigenen isolierten Testcheckout
fehlende aktuelle Tradegate-Abhängigkeiten; nach Übernahme der unveränderten
main-Dateien bestand derselbe fokussierte Block. Keine Schema-/Performance-
Regression aus 41205801735 wiederholt.

Der nicht live bestätigte Prüfcode verbleibt ausschließlich im Kandidatenbranch.
Nach main gelangt für diesen Auftrag nur diese Dokumentation mit einem
Abschluss-Commit. Die bisherigen Runtime-/Release-/Backup-Sperren bleiben
unverändert. Keine Dogado-DDL/DML, keine Provideranfrage, kein Deployment,
kein Collector-/Schedulerstart, keine Seeds und keine Migration ausgeführt.

Vor einem neuen freigegebenen Versuch: den konkreten Inventar-Unterabschnitt
durch sichere feste Diagnosecodes und belastbaren Offline-Nachweis eingrenzen.
Danach weiter erforderlich: frischer vollständiger Bestand, kontrollierte Ruhe,
geprüfter Live-Backup-Weg mit Schlüsselverwahrung und unabhängigem Restore sowie
explizit qualifizierte Schema-6-Runtime. Eine spätere Apply-Freigabe allein ersetzt
diese fehlenden technischen Nachweise nicht.

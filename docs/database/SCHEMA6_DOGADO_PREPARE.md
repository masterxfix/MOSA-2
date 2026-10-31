# Dogado Schema 4 -> 6: PREPARE, kein APPLY

## Software-Nachtrag: Schema 6 isoliert kompatibel

[SCHEMA6_RUNTIME_COMPAT.md](SCHEMA6_RUNTIME_COMPAT.md) dokumentiert den erfolgreichen
zusätzlichen Kompatibilitätsnachweis [Actions 41210299524](https://github.com/masterxfix/MOSA-2/actions/runs/41210299524):
expliziter 26-Tabellen-/Ledger-1–6-Vertrag, gesperrter Collector, unveränderte
fünf synthetische Current-/Observation-Ketten und separater reproduzierbarer
61-Dateien-Releasevertrag. Die nachstehenden Aussagen zur noch fehlenden
Softwarekompatibilität sind damit historisch überholt. Dogado-Installation und
Dogado-Apply weiterhin NEIN; Backup-/Restore-/Ruhe-Nachweise bleiben offen.
Die historischen Bestands-/Fehlernachweise und der Applyplan werden erhalten.

## Aktueller bestätigter Inventarnachweis: 31.10.2026

**READ-ONLY-Inventar PASS; Backup und Migration weiterhin BLOCKIERT.**
Genau ein neuer manueller Lauf, kein Rerun:
[Actions 41208789503](https://github.com/masterxfix/MOSA-2/actions/runs/41208789503),
Job [124559244122](https://github.com/masterxfix/MOSA-2/actions/runs/41208789503/job/124559244122),
geprüfter Kandidat `24fc35885eedb2cfc9ca93da64096cc688619d13`.
Alle anderen Workflow-Jobs wurden übersprungen. Keine Wiederholung der isolierten
Fundamentals-Qualifikation 41205801735.

### Fehlerkorrektur und Aussage zur früheren Ursache

Der statisch bewiesene Parser-Pfadfehler aus dem Kandidaten wurde bereits in
`90ae70f` korrigiert: Originalmigrationen 0001/2/3 werden byteidentisch unter den
vom unveränderten Parser erwarteten Dateinamen in einem temporären privaten
Runner-Verzeichnis bereitgestellt, mit Original-SHA-256 geprüft und danach
entfernt. 0004 wird weiter über den bestehenden Originalparser eingebunden.
Kein SQL-Artefakt wurde verändert, kein zweiter Parser gebaut.

Die bislang pauschale Python-Ausnahmebehandlung verlor nachweislich Fehlerklasse
und PHP-Abschnitt. Jetzt separate feste Codes für Timeout, SSH, Tunnel,
Subprozess, unerwartetes Stderr und ungültiges Ergebnis; keine Roh-Exceptions.
PHP-Stderr ist ausschließlich für die exakten `MOSA2_PHASE:`-Marker der gemeinsamen
Whitelist erlaubt. Andere Inhalte werden vollständig verworfen und abgewiesen.
Beim Timeout wird nur die letzte erlaubte Phase samt überschrittenem Prozesslimit
ausgegeben; private stdout-/stderr-Werte werden nicht übernommen.

Der umfangreiche Modus ist endlich auf **150 Sekunden** begrenzt; permissions-only
behält **60 Sekunden** und keine Fortschrittsmarker. SQL-Einzellimits unverändert.
Die umfangreiche Prüfung umfasst 17-mal SHOW CREATE und sechs Metadatenkategorien,
zusätzlich Tabelleninventar, Ledger, Zeilenzähler und Provenance über den Tunnel.
Das vorgelagerte Tabelleninventar und der unveränderte Parser-Tabellenabgleich sind
die einzige erkennbare Tabellenlistenüberschneidung; die pro Tabelle notwendigen
Metadaten werden nicht erneut vollständig abgefragt. Keine Vollständigkeitsprüfung entfernt.

Im erfolgreichen Lauf: Python-Schritt 14:09:16.865 UTC bis Ergebnis 14:10:13.361 UTC,
rund **56,5 Sekunden einschließlich Zugang und Zusatzproben**. Kein Timeout.
Letzter begonnener Abschnitt `REPORT_REJECTED` bezeichnet hier die erreichte
Berichtsphase; tatsächlicher Status `SCHEMA6_PREPARE_INVENTORY_PASS`, kein Fehler.
Die alte 60-Sekunden-Timeout-Hypothese für 41208064706 bleibt **unbewiesen**:
der frühere Catch hat die nötige Ursache verworfen; dieser neue Lauf rekonstruiert sie nicht.

### Tatsächlicher Dogado-Bestand

- Ausschließlich `h29077_mosa2_test`; bestehende Konto-/Portidentität PASS,
  MySQL **8.0.26-16**, verifizierte READ-ONLY-Transaktion.
- **Schema 4, exakt 17 InnoDB-Tabellen**, vollständiger gemeinsamer Strukturcheck PASS.
  Ledger **1–4**, alle Migrationsschlüssel und Original-SQL-Prüfsummen PASS.
  Keine 0005-/0006-Tabellen; Migrationen 0001–0006 im Repository unverändert.
- Metadaten-Baseline SHA-256:
  `167fef374c3d4b5aa2b15799cf8f407808924242bbf7f72bbf094eba9ffba614`.
  Dies ist ein Metadaten-/Ledger-Fingerprint, kein Vollbackup aller Geschäftsdaten.
- Allocated DATA_LENGTH + INDEX_LENGTH ca. **1097728 Bytes**,
  keine garantierte Dump-/Verschlüsselungsgröße.

| Tabelle | Exakte Zeilen |
| --- | --- |
| m2_asset_identifiers | 9 |
| m2_asset_source_routes | 18 |
| m2_assets | 9 |
| m2_entities | 9 |
| m2_events | 0 |
| m2_files | 0 |
| m2_job_runs | 0 |
| m2_jobs | 0 |
| m2_market_bars | 0 |
| m2_market_current | 5 |
| m2_market_observations | 28 |
| m2_module_state | 0 |
| m2_relationships | 0 |
| m2_schema_migrations | 4 |
| m2_sources | 5 |
| m2_sync_checkpoints | 5 |
| m2_units | 4 |

### Fünf bestehende Tradegate-Ketten

Gemeinsame Current-/Observation-/Route-/Source-/Unit-/Dedupe-/Provenance-Logik
unverändert verwendet. Aktuell gespeicherter Current und ausgewählte Observation
stimmen bei Preis, Währung sowie Markt-/Erfassungszeit überein; jeder Current
ist gegen seinen gespeicherten Observation-Ursprung validiert. Keine Kurse,
DB-IDs oder Zeitwerte werden in dieser öffentlichen Dokumentation ausgegeben.

| Aktie | ISIN | Current / Observation / Provenance | Datenstatus | Route aktiviert |
| --- | --- | --- | --- | --- |
| BYD | CNE100000296 | VALID / VALID / PASS | stale | NEIN |
| DroneShield | AU000000DRO2 | VALID / VALID / PASS | stale | NEIN |
| Ubtech Robotics | CNE100006CQ4 | VALID / VALID / PASS | stale | NEIN |
| PNE AG | DE000A0JBPG2 | VALID / VALID / PASS | stale | NEIN |
| Carl Zeiss Meditec | DE0005313704 | VALID / VALID / PASS | stale | NEIN |

Alle fünf Quellen: **Tradegate · XGAT · Mid**. Veraltetes Marktalter wird nicht
durch die neue Bestandsprüfung oder Erfassungszeit aufgefrischt. Keine neue
Web-/Preisaktualisierung und kein Providerabruf behauptet.

### Jobs, Rechte und Backup-Voraussetzungen

Keine Jobs oder Jobläufe gespeichert, enabled_jobs=0, running_jobs=0.
`m2-current-refresh` und der tatsächlich vorhandene `m2-collector-scheduler`
nicht belegt. Der frühere nicht vorhandene Named-Lock `m2-collector-live-batch`
wurde schon in `90ae70f` berichtigt. Keine andere eigene Testschema-Sitzung sichtbar.
PROCESS fehlt: dies ist nur Kontosicht, kein Nachweis der Abwesenheit fremder
Schreiber, kein OS-Prozess-/Croninventar und keine durchgehende DDL-/Schreibruhe.

Schemaweite SELECT, SHOW VIEW, TRIGGER, EVENT, CREATE ROUTINE, ALTER ROUTINE,
EXECUTE und LOCK TABLES bestätigt. Globale RELOAD, FLUSH_TABLES, SHOW_ROUTINE,
PROCESS und SELECT fehlen. Trigger/Routinen/Events: jeweils **0**, vollständige
Enumeration durch vorhandene Rechte und erfolgreiche Metadatenabfragen bestätigt.
Mangels Objekten kein SHOW CREATE eines gespeicherten Objekts notwendig.

MySQL-8.0-Dumpclient im Runner erkannt, ca. 91623366656 freie Scratch-Bytes.
Das beweist noch keine ausreichenden Export-/Verschlüsselungsressourcen.
Global sperrender bestehender Backup-Executor bleibt mit diesen Rechten gesperrt.
Die synthetisch qualifizierte schema-begrenzte Alternative bleibt bedingt geeignet,
nicht als betriebsfertiger Live-Backup-Weg bestätigt.

Weiter konkret offen:
1. Kontrollierte durchgehende MOSA-2-Schreib-/DDL-Ruhe einschließlich anderer Zugänge.
2. Geprüfter operativer, schema-begrenzter Exportweg unter Erhalt der vorhandenen
   CI-Isolationssperren, ausreichender Ressourcen und sicherer Schlüsselverwahrung.
3. Tatsächliches verschlüsseltes vollständiges Backup und unabhängiger isolierter Restore.
4. Explizit qualifizierter Schema-6-Runtime-/Releasevertrag; bestehende exakte
   Schema-4/5-Verträge nicht gegen 26 Tabellen verwenden.

**Keine Backup-/Restore-Ausführung, DDL/DML, Migration, Provideranfrage, Deployment
oder Collector-/Scheduler-Aktivierung.** Späterer Apply weiterhin nicht bereit;
der nachstehende gesondert freizugebende Applyplan bleibt verbindlich.

### Offline- und Veröffentlichungsnachweis

**13/13 fokussierte Offline-Tests PASS**, beide PHP-Syntaxprüfungen PASS:
TimeoutExpired, letzte Phase, Geheimnisschutz, Stderr-Allowlist, normaler Abschluss,
unverändertes permissions-only-Limit, exakter 17-Tabellen-Parser und bestehende Guards.
Keine zusätzlichen Regressionen oder neuen Actions gestartet.
Geprüfter Kandidat wird mit der unveränderten aktuellen main-Dokumentation in
genau einem Abschlusscommit auf main zusammengeführt; historische Fehlläufe bleiben erhalten.

## Historische Vorbereitungsnotizen und fehlgeschlagener Erstlauf

Die folgenden ursprünglichen Angaben bleiben als historische Befunde erhalten.
Für den aktuellen Inventarstand gilt ausschließlich der bestätigte Abschnitt oben.

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

## Historisches Ergebnis des ersten Auftrags

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

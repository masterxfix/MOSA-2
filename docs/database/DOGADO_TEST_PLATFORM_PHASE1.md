# MOSA 2 – Phase 1: isolierte Datenbank-Testplattform

**Status:** Phase 1A abgeschlossen · begrenzte Phase 1B (PDO/Rechte/Transaktionen) abgeschlossen · weitere Testblöcke und Issue #5 offen
**Grundlage:** abgeschlossene Dogado-Plattformqualifikation  
**Ziel:** MySQL 8.0 und PHP 8.4 unter realen Dogado-Bedingungen prüfen, bevor das endgültige MOSA-2-Schema freigegeben wird.

## Festgelegter Ausgangspunkt

- eigene, von MOSA getrennte Testdatenbank;
- MySQL 8.0;
- PHP 8.4 FPM und PHP 8.4 CLI;
- lokaler Datenbankzugriff;
- eigener Datenbankbenutzer;
- keine echten MOSA-Daten in dieser Phase;
- keine produktive MOSA- oder MOSA-2-Änderung.

PHP 8.5 wird später als zusätzlicher Kompatibilitätskandidat verglichen. Es wird nicht automatisch zum Standard.

## Sicherheits- und Freigabegrenze

Die Anlage einer Datenbank, eines Benutzers oder einer Testdomain ist eine Dogado-Änderung und erfolgt erst nach ausdrücklicher Freigabe. Die begrenzte Plattformanlage wurde am 17.10.2026 ausdrücklich freigegeben; Umfang und Grenzen sind in [Issue #5](https://github.com/masterxfix/MOSA-2/issues/5#issuecomment-6233907983) dokumentiert.

Zugangsdaten bleiben außerhalb von GitHub. Externer Datenbankzugriff bleibt zunächst deaktiviert. Alle Testtabellen erhalten einen eindeutig als temporär erkennbaren Präfix.

## Phase 1A – tatsächlich angelegte Plattform

**Nachweisstand:** 17.10.2026, ca. 14:44 Europe/Berlin. Prüfung ausschließlich über die vorhandene angemeldete Chrome-Sitzung, oneHome, Plesk und phpMyAdmin. Keine lokalen Laufwerke, Shells oder Launcher verwendet.

### Anlage und Zugriff

- Eigene neue Testdatenbank mit Suffix `mosa2_test` auf dem MySQL-8-Server; accountbezogene Präfixe bleiben hier ausgespart.
- Eigener neuer Benutzer mit demselben Test-Suffix. Die Benutzerübersicht ordnet ihn ausschließlich dieser Testdatenbank zu; im gespeicherten Formular ist die Rolle **Lesen und Schreiben** ausgewählt.
- Gespeicherte Zugriffskontrolle: **Nur lokalen Zugriff zulassen**. Externer Zugriff und benutzerdefinierte externe Verbindungen sind nicht ausgewählt.
- Lokaler TCP-Endpunkt: `127.0.0.1:3307`. Der vorhandene MySQL-5.7-Bestand bleibt auf Port 3306.
- Vorher drei, nachher vier Datenbanken; keine bestehende Datenbank oder bestehender Benutzer verändert.
- Das neue Passwort wurde vom Nutzer direkt im Dogado-Formular gesetzt und die Anlage von ihm abgesendet. Es wurde weder ausgelesen noch in GitHub übernommen.
- Neuer separater Webbereich `mosa2-test.<Testdomain>` mit eigenem Dokumentstamm `mosa2-test.<Testdomain>` außerhalb der bestehenden MOSA-Verzeichnisse.
- Nur für diesen neuen Webbereich wurde PHP 8.4 mit **FPM-Anwendung (Apache)** gespeichert. Keine bestehende Domain oder Anwendung umgestellt.
- Die Trennung erfolgt durch eine eigene Datenbank, einen darauf begrenzten Benutzer und einen eigenen Dokumentstamm im bestehenden Hosting-Abonnement. Ein eigener Server oder eigener Betriebssystembenutzer wurde nicht eingerichtet.
- Keine MOSA-Daten übernommen, keine Testtabellen oder Anwendung hochgeladen, kein produktives Deployment.

### Praktischer Datenbanknachweis

Die folgende reine Leseabfrage wurde im WebAdmin-Kontext der neuen Testdatenbank erfolgreich ausgeführt:

```sql
SELECT
    VERSION() AS mysql_version,
    @@port AS port,
    DATABASE() AS selected_database,
    @@session.sql_mode AS sql_mode,
    @@character_set_database AS db_charset,
    @@collation_database AS db_collation,
    @@session.time_zone AS session_time_zone,
    @@global.time_zone AS global_time_zone,
    @@default_storage_engine AS default_engine,
    @@max_allowed_packet AS max_allowed_packet,
    (
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
    ) AS table_count;
```

| Messpunkt | Im neuen Testkontext bestätigt |
| --- | --- |
| MySQL-Version | `8.0.26-16` |
| Port | `3307` |
| Ausgewählte Datenbank | ausschließlich die neu angelegte Testdatenbank |
| Tabellenzahl | `0` |
| SQL-Modus | `NO_ENGINE_SUBSTITUTION` |
| Datenbank-Zeichensatz | `utf8mb3` |
| Datenbank-Kollation | `utf8_general_ci` |
| Session-/globale Zeitzone | jeweils `SYSTEM` |
| Standard-Storage-Engine | `InnoDB` |
| `max_allowed_packet` | `67108864` Bytes = 64 MiB |

phpMyAdmin zeigt im durch Plesk geöffneten WebAdmin-Kontext irreführend das Serverlabel „MySQL 5.7“, obwohl Port 3307 verwendet wird. Maßgeblich ist das erfolgreiche Ergebnis von `VERSION()`: **8.0.26-16**. Es wurde keine andere Datenbank ausgewählt.

Die Provider-Voreinstellungen wurden unverändert erfasst. Vor dem Testschema sind **utf8mb4 mit ausdrücklich gewählter Kollation**, ein geeigneter strikter Session-SQL-Modus und eine ausdrückliche UTC-Strategie festzulegen und im isolierten Testkontext zu prüfen. `SYSTEM` belegt keine konkrete UTC-Zeitzone; `NO_ENGINE_SUBSTITUTION` ist kein Nachweis eines strikten SQL-Modus. Diese Einstellungen sind noch keine Schemafreigabe.

### Praktischer PHP-FPM-Nachweis

Nach dem Speichern der neuen Domain-Konfiguration wurde die von Plesk angebotene phpinfo-Ansicht ausschließlich auf die folgenden Laufzeitdaten und Modulnamen ausgewertet. Es wurde keine öffentliche phpinfo-Datei angelegt und keine vollständige Ausgabe übernommen.

| Messpunkt | Im neuen Webbereich bestätigt |
| --- | --- |
| Tatsächliche PHP-Version | `8.4.26` |
| Server API | `FPM/FastCGI` |
| PDO | aktiviert; Treiber `mysql` vorhanden |
| MySQL-Client | `mysqlnd 8.4.26` |
| `memory_limit` | `256M` |
| `max_execution_time` / `max_input_time` | jeweils `900` Sekunden |
| `post_max_size` / `upload_max_filesize` | jeweils `64M` |
| OPcache | aktiviert |

Bestätigte relevante Module: `curl`, `date`, `dom`, `fileinfo`, `filter`, `hash`, `intl`, `json`, `mbstring`, `mysqli`, `mysqlnd`, `openssl`, `PDO`, `pdo_mysql`, `session`, `sodium`, `zip` und `Zend OPcache`.

### Prüfung, offene Nachweise und nächste Phase

**Phase 1A geprüft:** Anlage vorhanden und nicht mehr als ausstehend markiert; Benutzerzuordnung ausschließlich zur neuen Datenbank; lokale Zugriffsbeschränkung gespeichert; erfolgreiche SQL-Leseabfrage mit null Tabellen; PHP 8.4.26 tatsächlich als FPM im neuen Dokumentstamm bestätigt.

**Noch offen:** PDO-Verbindung vom Test-Webbereich zur Datenbank mit dem neuen Benutzer, CLI-Laufzeit und PDO-CLI-Verbindung, genauer SQL-Rechteumfang einschließlich DDL sowie Transaktions-, Schreib- und Isolationstests. Die WebAdmin-Leseabfrage ersetzt diese Anwendungsnachweise nicht.

Die nächste praktische Testphase umfasst die kontrollierte Verbindungskonfiguration außerhalb von GitHub, Testschema mit festgelegtem Zeichensatz/SQL-Modus/Zeitzone, synthetische Datenstufen, Query-Pläne, begrenzte Lastmessungen und Backup/Restore in einem eigenen Ziel. Diese Schritte wurden in Phase 1A nicht vorgezogen. Eine Million Zeilen bleibt an eine positive Zwischenbewertung und die erforderliche Freigabe gebunden.

**Issue #5 bleibt offen.** Die Plattformanlage ist umgesetzt; die nachfolgend beschriebenen praktischen Testblöcke und die endgültige Schemafreigabe sind damit nicht abgeschlossen.

## Phase 1A – HTTPS und sichtbare Testseite

**Live geprüft am 17.10.2026, ca. 15:11–15:12 Europe/Berlin.**

- Vorher: nicht passendes HTTPS-Zertifikat. Belastbarer Kontobefund: Für die Testsubdomain war kein Zertifikat ausgewählt.
- Ein vorhandenes gültiges kostenloses Let's-Encrypt-Zertifikat wurde ausschließlich der Testsubdomain zugeordnet. Seine Domainabdeckung umfasst `mosa2-test.scharwerk.de`. Keine Neuausstellung, keine DNS-Änderung, kein selbstsigniertes Zertifikat und keine Veränderung anderer Domains oder Zertifikate.
- **Gültiges Zertifikat eingerichtet: ja. HTTPS ohne Warnung bestätigt: ja.** Hostname und Zertifikatskette wurden beim Browseraufruf ohne Ausnahme akzeptiert.
- Nach dieser Prüfung wurde ausschließlich die neutrale `index.html` im bestehenden Test-Document-Root bereitgestellt. Der exakt zurückgelesene Inhalt entspricht [fixtures/mosa2-test-index.html](fixtures/mosa2-test-index.html).
- URL: `https://mosa2-test.scharwerk.de/`. Titel: **MOSA 2 Testplattform**. Sichtbarer Inhalt: **MOSA 2 Testplattform** und **Technische Testumgebung aktiv**.
- Bestätigt: HTML5, `lang="de"`, UTF-8, responsiver Viewport, `robots=noindex,nofollow`, keine Skripte, Links oder externen Ressourcen. Keine Verzeichnisliste, Hosting-Standardseite oder Diagnose-/Fehlermeldung im Seiteninhalt.
- Der abschließende Aufruf von `/` ist im HTTPS-Zugriffsprotokoll mit **HTTP 200** bestätigt.
- Keine Diagnose-, phpinfo-, Smoke-, Backup- oder temporären Dateien angelegt; im geprüften Document Root keine entsprechende Datei gefunden. Unveränderte Provider-Bestandteile werden von der neuen Seite nicht eingebunden.
- Bestehende MOSA-Ressourcen und Datenbanktabellen/-daten wurden nicht verändert.

### Reine Erreichbarkeitsprüfung bestehender Adressen

| Adresse | Beobachtung ohne weitere Aktion |
| --- | --- |
| `https://mosa.scharwerk.de/` | HTTPS ohne Warnung; Hosting-Standardseite sichtbar. |
| `https://scharwerk.de/dashboard_neu/` | HTTPS antwortet mit **403 Zugriff verweigert**. Keine Funktionsbestätigung der Anwendung und keine Änderung vorgenommen. |

Die technischen Live-Kriterien dieser Phase 1A sind erfüllt. **Phase 1B und Issue #5 bleiben offen.** Die spätere Phase umfasst weiterhin insbesondere PDO-/CLI-Nachweise, Testschema, synthetische Daten, Lastmessungen und Backup/Restore.

Der Abschluss-Commit enthält `[skip ci]`, damit der Main-Push kein ausgeschlossenes Deployment auf eine bestehende Domain auslöst. `git diff --check HEAD^ HEAD` wird separat im unveränderten vorhandenen Validierungsjob auf einem Prüfbranch ausgeführt; der Deploy-Job ist dort durch seine bestehende Main-Bedingung ausgeschlossen. Ergebnis und Lauf werden in Issue #5 zum Abschluss-Commit dokumentiert.

## Phase 1B – PDO, Rechte und Transaktionen

**Nachweisstand: 17.10.2026, 16:21 Europe/Berlin (MESZ).** Der ausdrücklich freigegebene Umfang dieser Phase ist abgeschlossen. Die weiteren Testblöcke und **Issue #5 bleiben offen**.

### Gemeinsamer Testkern und sichere Ausführung

- Wiederverwendbarer, geheimnisfreier Code: [probe.php](../../scripts/phase1b/probe.php) für Verbindung, Zielprüfung und Tests; [entry.php](../../scripts/phase1b/entry.php) als gemeinsamer FPM-/CLI-Adapter. Es gab zuvor keinen passenden PDO-Testkern im Repository.
- Vor jedem Schreibzugriff wurden ausgewählte Testdatenbank, zugeordneter authentifizierter Testbenutzer, MySQL-8.0-Server und der fest im Code begrenzte lokale TCP-Endpunkt geprüft. Unerwartete Ziele brechen vor Test-DDL ab; accountbezogene Namen bleiben außerhalb GitHubs.
- Das bestehende Testpasswort wurde vom Nutzer im maskierten HTTPS-Formular eingegeben. Laufzeitkonfiguration, Passwort, Zeilenbudget und Sitzungen lagen ausschließlich in einem eigenen privaten Verzeichnis außerhalb aller öffentlichen Dokumentstämme. Verzeichnisrechte `0700`, Passwortdatei `0600`; keine fremden Anwendungskonfigurationen gelesen und kein Passwort zurückgesetzt.
- Der temporäre FPM-Einstieg wurde vor Nutzung durch IP-Beschränkung auf Webserver- und PHP-Ebene geschützt. Ein Aufruf außerhalb der erlaubten Herkunft wurde tatsächlich mit **HTTP 403** abgewiesen. Zusätzlich: bestehendes DB-Passwort, HTTPS-/Host-/Origin-Prüfung, kurzlebige Secure/HttpOnly/SameSite-Sitzung und einmaliges CSRF-Token für den Test-POST. GET zeigte ausschließlich das maskierte Anmeldeformular und führte keine Datenbanktests aus. Keine öffentliche Diagnoseausgabe.
- CLI lief ausschließlich über Plesks **„Jetzt ausführen“** im ungespeicherten, inaktiven Aufgabenformular mit ausgeschalteten Benachrichtigungen. Kein Cronjob gespeichert; vorher und nachher **neun** bestehende Aufgaben.
- Browserzugriff und Repository-Zugriff erfolgten über die verbundenen Browser beziehungsweise GitHub. Lokal wurde ausschließlich der ausdrücklich erlaubte Statussender mit seinen JSON-Meldungen verwendet; keine lokalen fachlichen Prüfungen oder Launcher und kein Zugriff auf E:.

### Tatsächliche Ergebnisse beider Laufzeiten

| Prüfung | FPM | CLI |
| --- | --- | --- |
| PHP-Version / SAPI | `8.4.26` / `fpm-fcgi` | `8.4.12` / `cli` |
| PDO-MySQL, Zielprüfung und zwei unabhängige Verbindungen | bestanden | bestanden |
| CREATE, ALTER, Indexanlage und DROP | bestanden | bestanden |
| INSERT, SELECT mit Umlauten/Emoji, UPDATE und DELETE | bestanden | bestanden |
| Ungültiger Integer im strikten Modus abgewiesen, keine Restzeile | bestanden | bestanden |
| Unbestätigte Änderung für zweite Verbindung unsichtbar | bestanden | bestanden |
| Rollback: beide Verbindungen sehen anschließend null Zeilen | bestanden | bestanden |
| Commit: bestehender REPEATABLE-READ-Snapshot bleibt stabil | bestanden | bestanden |
| Neue Lesetransaktion sieht den Commit | bestanden | bestanden |
| Eigene Tabelle entfernt und Abwesenheit geprüft | bestanden | bestanden |

Der benötigte Rechteumfang **CREATE, ALTER, INDEX, INSERT, SELECT, UPDATE, DELETE und DROP** wurde ermittelt und praktisch bestätigt. Keine Rechte erweitert. Die erste konservative Vorprüfung stoppte ohne DDL, weil MySQL Datenbankrechte als Muster mit maskierten Unterstrichen ausweist. Der Kern berücksichtigt jetzt serverseitige Grant-Muster statt eines reinen Namensvergleichs; die korrigierten Tests liefen danach erfolgreich unter beiden SAPIs.

Beide Verbindungen lasen identisch zurück:

- Zeichensatz `utf8mb4`, Kollation `utf8mb4_0900_as_cs`, Isolation `REPEATABLE-READ`, Session-Zeitzone `+00:00` (UTC).
- SQL-Modus: `STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY` (Reihenfolge beim Rücklesen normalisiert).
- Eigene Tabelle: `InnoDB`, explizit `utf8mb4_0900_as_cs`. Diese Unicode-9-Kollation unterscheidet Akzente und Groß-/Kleinschreibung und macht die Testvergleiche eindeutig; sie ist noch keine Kollationsentscheidung für das endgültige Core-Schema.

Alle Einstellungen waren verbindungsbezogen. Globale Servereinstellungen und bestehende Datenbankstandards blieben unverändert. DDL lief außerhalb der Transaktionstests.

### Umfang und Bereinigung

Pro Laufzeit wurde eine kollisionsfrei benannte eigene Tabelle mit Präfix `mosa2_tmp_` und Zufallssuffix verwendet. Insgesamt **sechs erfolgreiche synthetische INSERT-Anweisungen**, davon zwei zurückgerollt; höchstens **eine Zeile gleichzeitig je Tabelle**. Das über beide SAPIs gemeinsame private Budget zählte **acht Reservierungen** einschließlich zweier absichtlich abgewiesener Integer-Inserts; die harte Grenze von 100 wurde eingehalten.

Abschließend tatsächlich bestätigt:

- **Null Tabellen** in der isolierten Testdatenbank; beide eigenen Tabellen zuvor jeweils durch den Testkern entfernt.
- Privater Code, Zielkonfiguration, Passwortdatei, Budget, Sitzungen, öffentlicher Wrapper und dessen Zugriffsschutz vollständig entfernt; ausschließlich eigene Testobjekte bereinigt.
- Temporärer HTTP-Einstieg antwortet danach mit **404**. Neutrale Startseite weiterhin **HTTP 200**, sichtbar unverändert und bytegenau identisch mit dem vorhandenen Repository-Fixture.
- Bestehende MOSA-/fixlab-Ressourcen, Zertifikate und die neutrale Startseite nicht verändert. Kein Produktionsdeployment.

### Prüfungen und nächste Freigabe

PHP-Lint aller drei wiederverwendbaren PHP-Dateien lief auf Dogado PHP 8.4 erfolgreich; nach der Rechtekorrektur wurde der betroffene Kern erneut gelintet und der Offline-Test erneut ausgeführt. **17 Offline-Grenzprüfungen** bestanden ohne Datenbankverbindung, einschließlich falscher Ziele/Laufzeiten, unsicherer Tabellennamen sowie erschöpftem und beschädigtem Zeilenbudget.

[tests/test_phase1b.py](../../tests/test_phase1b.py) bindet PHP-Lint und diese Grenzprüfungen in den bestehenden Validierungsworkflow ein. Der einzelne Abschluss-Commit enthält `[skip ci]`; derselbe Commit wird auf einem Prüfbranch mit dem unveränderten Workflow validiert, einschließlich `git diff --check HEAD^ HEAD`. Der Deploy-Job muss dort übersprungen sein, bevor genau dieser Commit nach Main übernommen wird. Konkreter Workflow-Lauf und Abschlussergebnis stehen in Issue #5.

**Keine fehlenden Live-Nachweise innerhalb dieses begrenzten Phase-1B-Auftrags.** Nicht geprüft und weiterhin ausdrücklich freizugeben: endgültiges Core-Schema, repräsentative Current-/History-Muster, größere Datenstufen, Query-Pläne, Performance/Last, Backup/Restore und Migration echter Daten. Die nachfolgenden Testblöcke sind Planungsumfang und keine Freigabe zur Ausführung. Das Schema bleibt unfreigegeben.

## Testblöcke

### 1. Plattform-Fingerprint

Zu erfassen sind unter anderem:

- genaue MySQL-8-Version;
- SQL-Modus, Zeichensatz, Kollation und Zeitzone;
- InnoDB- und Transaktionsverhalten;
- wichtige DB-Limits, soweit lesbar;
- PDO-MySQL-Verbindung über PHP 8.4 FPM und CLI;
- verfügbare PHP-Module für MOSA 2.

### 2. Minimales Testschema

Es werden noch keine endgültigen MOSA-2-Fachtabellen angelegt. Das Testschema bildet nur die geplanten Muster ab:

- kleine Current-Tabelle;
- große append-only History-Tabelle;
- Entity-/Identity-Zuordnung;
- Schema-Migrationsprotokoll;
- passende zusammengesetzte Indizes.

### 3. Datenmengen

Stufenweise testen:

1. 10.000 synthetische History-Zeilen;
2. 100.000 Zeilen;
3. 1.000.000 Zeilen erst nach positiver Zwischenbewertung und ausreichender Größen-/Lastfreigabe.

Jede Stufe muss wiederholbar und vollständig löschbar sein.

### 4. Kernabfragen

Mindestens messen:

- Current-Zustand eines Objekts;
- Current-Zustände mehrerer Objekte in einem Batch;
- neuesten History-Eintrag eines Objekts;
- begrenzten Zeitraum eines Objekts;
- Chart-/Zeitreihenbereich mit LIMIT;
- Insert-Batches;
- Update/Upsert eines Current-Zustands;
- Verhalten paralleler Lese- und Schreibzugriffe.

Für kritische Abfragen werden `EXPLAIN`, verwendeter Index, Sortierung und geschätzte gelesene Zeilen dokumentiert.

## Zielwerte

| Messpunkt | Ziel |
| --- | ---: |
| einfacher Current-Read | ideal < 20 ms |
| begrenzte History-Abfrage | < 100 ms |
| gesamte DB-Zeit einer normalen Seite | < 200 ms |
| normaler Seitenaufruf | < 1,0 s |
| p95 Seitenaufruf | < 1,5 s |
| harte Obergrenze | 2,0 s |

Ein Test gilt nicht als bestanden, wenn ein schneller Messwert nur durch Cache-Effekte entsteht, aber der Query-Plan ungeeignet ist.

## Backup- und Restore-Nachweis

Vor einer Schemafreigabe muss praktisch bewiesen werden:

- Export der Testdatenbank;
- Restore in eine zweite, getrennte Testdatenbank oder einen dafür vorgesehenen Restore-Zielbereich;
- Vergleich von Tabellen, Zeilenzahlen und Prüfsummen;
- dokumentierte Dauer und benötigter Speicher;
- kein Überschreiben einer bestehenden MOSA-Datenbank.

## Ergebnisse

Die Resultate werden nachvollziehbar in GitHub dokumentiert:

- getestete Versionen und Einstellungen;
- Testdatenmengen;
- Query-Pläne und Laufzeiten;
- Speicherentwicklung;
- Backup-/Restore-Ergebnis;
- Abweichungen von den Zielwerten;
- Entscheidung zu MySQL-Version, PHP-Version und Betriebsgrenzen.

## Freigabekriterium für das endgültige Schema

Das echte MOSA-2-Core-Schema wird erst freigegeben, wenn:

1. Current- und History-Muster die Zielwerte erreichen;
2. kritische Queries passende Indizes nutzen;
3. die Tests reproduzierbar sind;
4. Backup und Restore erfolgreich nachgewiesen wurden;
5. keine produktiven MOSA-Daten verändert wurden;
6. die technischen Dogado-Grenzen ausreichend verstanden sind.

Erst danach beginnen Core-Schema und kontrollierte MOSA→MOSA-2-Datenmigration.

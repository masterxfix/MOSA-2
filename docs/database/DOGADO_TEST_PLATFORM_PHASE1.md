# MOSA 2 – Phase 1: isolierte Datenbank-Testplattform

**Status:** Million-Zeilen-Skalierungstest und Backup/Restore durchgeführt und bereinigt · begrenzte Testziele erfüllt · Issue #5 und Schema-/Produktivfreigaben offen
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

## Phase 1C – Current/History mit 10.000 synthetischen History-Zeilen

**Dokumentiert am 17.10.2026, 17:10:42 Europe/Berlin (MESZ, UTC+02:00), nach erfolgreicher Live-Bereinigung.** Dieser freigegebene Testblock ist abgeschlossen. Issue #5 und die endgültige Schemafreigabe bleiben offen.

### Wiederverwendung und begrenztes Profil

Verbindung, exakte Zielprüfung, Session-Konfiguration, getestete Kollation und Identifier-Prüfung aus [phase1b/probe.php](../../scripts/phase1b/probe.php) bleiben unverändert. Der vorhandene [FPM-/CLI-Adapter](../../scripts/phase1b/entry.php) wählt das Zusatzprofil nur über eine serverseitige Konstante; HTTP-Parameter können es nicht umschalten. Das **100-Zeilen-Budget des Phase-1B-Basistests bleibt unverändert**.

[Gemeinsamer Testkern](../../scripts/phase1c/profile.php), [Einstieg](../../scripts/phase1c/entry.php) und [Offline-Prüfungen](../../scripts/phase1c/self_test.php) sind geheimnisfrei. Kein endgültiges Fachtabellenschema und keine sichtbare Anwendung.

Fünf kollisionsfreie eigene Tabellen mit mosa2_tmp_-Zufallsnamen wurden vor DDL in einem privaten Manifest reserviert. Vor CREATE wurde die Abwesenheit geprüft, danach ein zufälliges Eigentumsmerkmal im Tabellenkommentar bestätigt. DROP prüft dieses Merkmal und verwendet ausschließlich die gespeicherten exakten Namen.

| Logische Tabelle | Schlüssel und minimale Struktur | Tatsächliche Zeilen / harte Grenze |
| --- | --- | ---: |
| Entity | numerische ID, eindeutiger künstlicher Code | 100 / 100 |
| Identity | ID, eindeutige Entity-Zuordnung, eindeutiges Paar Namespace/externer Schlüssel | 100 / 100 |
| History | ID, Entity, Sequenz, UTC-Zeit, künstlicher Integer; UNIQUE(Entity,Sequenz); Index history_time(entity_id,observed_at DESC,id DESC) | 10.000 / 10.000 |
| Current | Entity als Primärschlüssel, History-Verweis, UTC-Zeit, künstlicher Integer | 100 / 100 |
| Migrationsprotokoll | ID, eindeutige synthetische Versionskennung, fester Testzeitpunkt | 1 / 10 |

InnoDB, utf8mb4 und utf8mb4_0900_as_cs ausdrücklich gesetzt; CHECK-/Schlüsselgrenzen und Fremdschlüssel sichern Bestand und Zuordnungen zusätzlich. Beide SAPIs lasen dieselben bereits getesteten strikten Session-SQL-Modi, UTC +00:00 und REPEATABLE-READ zurück. Keine globalen Einstellungen oder bestehenden Datenbankstandards verändert.

Fester Seed **mosa2-synthetic-v1**, fester Zeitbezug **2020-01-01T00:00:00Z**. 100 künstliche Objekte mit je 100 History-Einträgen; absichtlich gleiche Zeitstempel für benachbarte Sequenzen. Eindeutige Reihenfolge über (observed_at,id). Keine echten Namen, Kurse oder MOSA-Daten.

**Genau einmal per CLI aufgebaut**, 24 INSERT-Batches in einer Datentransaktion, davon 20 History-Batches mit jeweils 500 Zeilen. DDL getrennt außerhalb der Transaktion. Ein bestehendes Manifest verhindert erneuten Aufbau/Anhängen; beide SAPIs nutzen denselben Bestand.

Feste Grenzen: Aufbau 90 Sekunden, Mess-/Inspektions-/Bereinigungsschritt je 30 Sekunden, PHP zusätzlich 120 Sekunden; SELECT-Grenze 3 Sekunden und Lock-Wartegrenzen je 3 Sekunden pro DB-Session. Privates exklusives Profilschloss verhindert parallele Ausführung. Ein ganzer Messlauf wird vor Beginn je SAPI im Manifest reserviert. Fehlerpfade versuchen nur nachgewiesen eigene Tabellen zu bereinigen und melden verbleibende eigene Reste.

### Tatsächlich bestandene Korrektheit

PHP **8.4.12 CLI** und **8.4.26 FPM**, jeweils PDO-MySQL, bestanden dieselbe gemeinsame Logik:

- exakte Zeilenzahlen, eindeutige Zuordnungen, keine verwaisten Datensätze;
- alle 100 Current-Zustände entsprechen dem eindeutig neuesten History-Eintrag;
- Einzel-/Batch-Abfragen, letzter History-Eintrag, Zeitfenster, begrenztes Chart und Identity-Lookup liefern exakt erwartete synthetische Ergebnisse;
- gleiche Zeitstempel eindeutig nach ID sortiert; leere Entity-Ergebnisse, leeres Intervall, exklusives Zeitfensterende und Zeitraum außerhalb des Bestands geprüft;
- Current-Upsert aktualisiert neuere Werte, erzeugt keine Duplikate und lässt ältere Zeitpunkte beziehungsweise ältere IDs bei gleichem Zeitpunkt nicht überschreiben; Teständerungen zurückgerollt;
- History blieb nach dem Laden unverändert: erwartete SHA-256-Prüfsumme vor/nach Schreibprüfungen unter beiden SAPIs und bei der Größenprüfung bestätigt. Der Audit liest begrenzte 500er-Blöcke; er ist kein normaler Leseweg.

### Messungen und EXPLAIN

Je Abfragetyp und SAPI **elf gemessene Ausführungen**: erste separat, danach zehn für Median/p95. Nearest-Rank-p95 entspricht bei zehn Werten dem Maximum. Zusätzliche Korrektheitsprüfungen bleiben innerhalb von 30; der mehrfach geprüfte Zeitfenstertyp erreicht höchstens 15 SELECT-Ausführungen je SAPI.

PHP-Wandzeit von PDO execute plus vollständigem Abruf begrenzter Ergebnisse; Verbindung und Statement-Vorbereitung ausgeschlossen. Keine Cache-Leerung oder parallele Last. „Erste“ ist kein nachgewiesener Kaltstart. Kleine Stichprobe, keine Seitenladezeit- oder allgemeine Lastfreigabe.

| Abfrage | CLI: erste / Median / p95 (ms) | FPM: erste / Median / p95 (ms) | EXPLAIN (beide SAPIs) |
| --- | ---: | ---: | --- |
| current_single | 0.6051 / 0.2226 / 0.3154 | 0.4609 / 0.1362 / 0.2663 | const, PRIMARY, ≈1 Zeile, kein Filesort |
| current_batch | 0.2929 / 0.2472 / 0.2965 | 0.2012 / 0.1253 / 0.1884 | range, PRIMARY, ≈6 Zeilen, kein Filesort |
| history_latest | 0.6827 / 0.4615 / 1.7417 | 0.3467 / 0.3126 / 0.4536 | ref, history_time, ≈100 Zeilen, kein Filesort |
| history_window | 0.4617 / 0.3940 / 0.4286 | 0.3369 / 0.2414 / 0.3439 | range, history_time, ≈10 Zeilen, Filesort |
| chart | 0.6134 / 0.5006 / 0.6614 | 0.3914 / 0.3825 / 0.4319 | ref, history_time, ≈100 Zeilen, kein Filesort |
| identity_lookup | 0.2498 / 0.1372 / 0.1761 | 0.2277 / 0.1680 / 0.3288 | const, identity_lookup, ≈1 Zeile; const, PRIMARY, ≈1 Zeile; kein Filesort |

SQL/Parameter/Erwartungen stehen gemeinsam in querySet()/expectedQueries(). Current: Einzel-ID, LIMIT 1, beziehungsweise sechs feste IDs, aufsteigend, LIMIT 6. History für ein Objekt: neuester Eintrag absteigend nach Zeit/ID, LIMIT 1; Zeitfenster 00:10 inklusive bis 00:15 exklusive, aufsteigend nach Zeit/ID, LIMIT 20; Chart 00:00 bis 00:49 inklusive, absteigend nach Zeit/ID, LIMIT 25. Zeitangaben gehören zum festen UTC-Testtag.

Alle kritischen History-Lesewege verwenden einen Index, keinen ungebundenen Full Scan. **Abweichung:** Das Zeitfenster nutzt zusätzlich Filesort über geschätzt zehn Treffer; bei größeren Datenstufen beobachten. EXPLAIN-Zeilen sind Optimizer-Schätzwerte, keine gemessenen gelesenen Zeilen.

Current liegt hier unter 20 ms, begrenzte History unter 100 ms. Daraus folgt keine Aussage zu Parallelbetrieb, Seitenaufbau oder größeren Beständen.

### Schreiben und Größen

CLI-INSERT-Batchzeiten ohne DDL, Vorbereitung und Commit:

| Tabelle | Batches × maximale Zeilen | Summe (ms) | Median je Batch (ms) | p95 je Batch (ms) |
| --- | ---: | ---: | ---: | ---: |
| Entity | 1 × 100 | 0.9517 | 0.9517 | 0.9517 |
| Identity | 1 × 100 | 1.6947 | 1.6947 | 1.6947 |
| History | 20 × 500 | 255.3558 | 12.1051 | 20.6671 |
| Current | 1 × 100 | 1.7822 | 1.7822 | 1.7822 |
| Migrationsprotokoll | 1 × 1 | 0.2651 | 0.2651 | 0.2651 |

Die erste Metadatenabfrage nach dem Laden zeigte veraltete Größen. Ein begrenzter CLI-Inspektionsschritt las anschließend mit **SET SESSION information_schema_stats_expiry=0** frisch: nur Statistik-Cache dieser Session umgangen, kein Daten-Cache geleert, kein ANALYZE und keine globale Änderung. Zeilenzahlen und unveränderte History-Prüfsumme erneut bestätigt.

| Tabelle | Daten (KiB, näherungsweise) | Sekundärindizes (KiB, näherungsweise) | Geschätzte Zeilen |
| --- | ---: | ---: | ---: |
| Entity | 16 | 16 | 100 |
| Identity | 16 | 32 | 100 |
| History | 432 | 384 | 9.986 |
| Current | 16 | 16 | 100 |
| Migrationsprotokoll | 16 | 16 | 1 |

InnoDB meldet belegte Daten-/Indexseiten, keine exakte Nutzdaten-/Backupgröße: zusammen ungefähr **960 KiB**. Die Schätzung 9.986 ersetzt nicht den bestätigten COUNT **10.000**.

### Schutz, Bereinigung und Prüfungen

- Passwort nur vom Nutzer im maskierten HTTPS-Formular eingegeben, geschützt außerhalb öffentlicher Dokumentstämme gespeichert. Verzeichnisse 0700, Passwortdatei 0600; keine Geheimnisse/vollständigen Verbindungsdaten in GitHub.
- Vor Nutzung tatsächlicher HTTP-403-Nachweis für nicht erlaubte Herkunft. Bestehende IP-/Host-/HTTPS-/Origin-Prüfung, Passwort und einmaliger CSRF-Test-POST wiederverwendet. GET führt keine Schreibtests aus und liefert keine Diagnosen.
- CLI nur über Plesks ungespeichertes, inaktives „Jetzt ausführen“-Formular. Vorher/nachher **neun** geplante Aufgaben, keine gespeichert.
- Alle fünf eigenen Tabellen anhand Eigentumsnachweis entfernt; Ausgangsstand **null Tabellen** wiederhergestellt.
- Quellen vor Entfernung gegen GitHub-Blob-Hashes geprüft. Eigener privater Code, Konfiguration, Passwort, Manifest, Ergebnisse, Schloss, Sitzungen sowie öffentlicher Einstieg und Zugriffsschutz vollständig entfernt.
- Einstieg danach **HTTP 404**; neutrale HTTPS-Startseite **HTTP 200**, sichtbar und gesamter ausgelieferter Inhalt bytegenau wie bestehendes Fixture. Keine Zertifikats-/Startseitenänderung.
- PHP-Lint aller sechs beteiligten PHP-Dateien erfolgreich; nach Größenanpassung betroffenen Code erneut gelintet. Unveränderte **17 Phase-1B-Grenzprüfungen** und **80 neue Profilprüfungen** bestanden ohne Datenbankverbindung.
- [Neue CI-Einbindung](../../tests/test_history_profile.py) im vorhandenen Validierungsworkflow; keine Workflow-/Deployment-Secret-Änderung. Ein Abschluss-Commit mit [skip ci], identisch auf Prüfbranch einschließlich git diff --check HEAD^ HEAD prüfen, Deploy überspringen, erst danach denselben Commit nach Main übernehmen. Endgültiger Lauf und Ergebnis stehen in Issue #5.
- Keine AGENTS.md-, fixlab-, bestehenden MOSA-/Produktivänderungen; keine größeren Datenstufen, Restore-Tests oder Produktionsdeployments.

**Erfassungslücke:** Der vorhandene freigegebene Statussender meldete für die native Nachricht mit Auftragsanhang keinen offenen Auftrag. Kein Ersatzweg und keine erfundenen Ereignisse/Zeitpunkte; fachliche Nachweise stammen aus tatsächlichen Browser-/Provider-/GitHub-Prüfungen.

### Empfehlung

Der 10.000er-Block ist positiv. Als **gesondert freizugebender** nächster Schritt ist ein begrenztes 100.000er-Profil mit erneuten Korrektheits-, EXPLAIN-, Größen- und Laufzeitprüfungen sinnvoll; insbesondere Filesort und Schätzabweichungen beobachten. Das 10.000er-Profil und der 100-Zeilen-Basistest werden nicht stillschweigend erweitert.

Keine Ausführungs-/Lastfreigabe aus diesem Ergebnis. 100.000/1.000.000 Zeilen, parallele Last, Restore, endgültiges Schema und Migration bleiben unausgeführt. **Issue #5 bleibt offen.**

## Phase 1D – 100.000 synthetische History-Zeilen

**Nachweisstand: 17.10.2026, 18:07:24 Europe/Berlin (MESZ, UTC+02:00), nach Live-Bereinigung. Fachliches Ergebnis: teilweise erfolgreich.** Korrektheit und Bereinigung bestanden; das neue breite Zeitfenster verfehlt das 100-ms-Ziel. Testauftrag ausgeführt, keine allgemeine Skalierungs-/Produktivfreigabe. Issue #5 bleibt offen.

### Auftragsnachweis und Profiltrennung

Der neue native Auftrag wurde vor Facharbeit nachgewiesen. Describe und Plan über den vorgegebenen E:-freien Statusadapter quittiert; im bestehenden KI-Kontrollzentrum waren der genaue Betreff **„Datenbank-Testplattform: 100.000 synthetische History-Zeilen“**, nativer Eingang, Auftrag/Verständnis und alle sechs Arbeitsschritte sichtbar. Konkrete Step-Wechsel einschließlich Wartephase, Live-Befund und Bereinigung wurden quittiert und sichtbar kontrolliert. Keine Starts/Stopps rekonstruiert und keine Kennung eines Altauftrags wiederverwendet.

Ausgangsstand: fde17e6dd4ceec714b58fa8ea6bac9daab3164f0. [Gemeinsamer Testkern](../../scripts/phase1c/profile.php) gezielt erweitert; keine kopierte Sonderlösung. [Neuer Einstieg](../../scripts/phase1d/entry.php) wählt ausschließlich serverseitig history100000_v1. Der 100-Zeilen-Basistest und history10000_v1 behalten ihre Grenzen, deterministischen Daten und dokumentierten Ergebnisse. HTTP kann weder Profil noch Zeilenzahl frei bestimmen.

Whitelist der Profile, Generator/IDs/Zeitbezug, SQL-CHECKs, Sollwerte, Manifest und Prüfsummen sind konsistent profilabhängig. Das 100.000er-Manifest verlangt passende Mengen-, Sequenz- und Sollwertfelder; manipulierte oder profilfremde Zustände werden abgewiesen. Erzeugung, Laden und Prüfsummen arbeiten in begrenzten Blöcken, kein vollständiger 100.000er-History-Array im Live-Ladeweg.

Abfrage-Statistik bleibt auf **30 Werte** begrenzt. Eine getrennte Batchstatistik erlaubt für dieses Profil höchstens **200 Batchzeiten**, für das 10.000er-Profil weiterhin höchstens 20. Die neue Prüfung bestätigt 200 Werte und weist 201 sowie 31 Abfragemesswerte ab.

### Tatsächlicher Bestand und Korrektheit

**Einmal per PHP 8.4.12 CLI** aufgebaut; derselbe Bestand anschließend unter **PHP 8.4.26 FPM**, jeweils PDO-MySQL, verwendet:

| Tabelle | Tatsächlicher Bestand | Unveränderte/ausdrückliche Grenze |
| --- | ---: | ---: |
| Entity | 100 | 100 |
| Identity | 100 | 100 |
| History | 100.000 = 100 Objekte × 1.000 | 100.000 |
| Current | 100 | 100 |
| Migrationsprotokoll | 1 | 10 |

Fester Seed mosa2-synthetic-v1 und fester UTC-Zeitbezug 2020-01-01T00:00:00Z; keine echten Daten. Je zwei Sequenzen haben gleiche Zeitstempel. Neuester Eintrag wird über Zeit und ID eindeutig bestimmt; letzte Sequenz 1.000 liegt um 08:19 UTC. Exakte Testdatenbank, zugeordneter authentifizierter Benutzer und lokaler Endpunkt vor Schreibzugriffen geprüft. InnoDB, utf8mb4_0900_as_cs, strikte Session-SQL-Modi, UTC und REPEATABLE-READ beibehalten; keine globalen Änderungen.

200 History-INSERT-Batches mit je 500 Zeilen plus vier Nebenbatches, zusammen 204; eine Datentransaktion, DDL getrennt. Privates Manifest, festes Profil und exklusives Schloss verhindern Anhängen und parallele Ausführung. Bestehende Abbruchgrenzen unverändert: Aufbau 90 s, Messung/Inspektion/Bereinigung je 30 s, PHP zusätzlich 120 s, SELECT- und Lock-Wartegrenzen je 3 s.

Beide SAPIs bestätigten exakte Zeilenzahlen, eindeutige Zuordnungen, keine verwaisten Daten und Current = eindeutig neueste History. Einzel-/Batch-/History-/Chart-/Identity- und beide Zeitfenster-Abfragen lieferten exakt erwartete Ergebnisse. Leere Ergebnisse, Zeitgrenzen und Gleichstände bestanden. Current-Upsert erzeugte keine Duplikate und ließ ältere Werte nicht überschreiben; Änderungen zurückgerollt. History blieb nach dem Laden unverändert: Soll-Prüfsumme vor/nach Schreibprüfungen bestätigt. Der 100.000er-Sollhash wird zusätzlich gegen eine unabhängig erzeugte feste Offline-Referenz geprüft.

### Messumfang und tatsächliche EXPLAIN-Pläne

Je **sieben Abfragetypen und SAPI elf Messungen**: erste separat, Median/p95 aus zehn Folgewerten (Nearest-Rank, p95 hier Maximum). Mit zusätzlichen Korrektheitsabfragen höchstens 15 Ausführungen beim schmalen Fenster, sonst höchstens 12; unter der Grenze von 30. Kein wiederholter Aufbau oder zweiter Messlauf.

Zeitmessung: PHP-Wandzeit für PDO execute und Abruf der begrenzten Ergebnismenge, ohne Verbindung/Statement-Vorbereitung. Kein Cache-Leeren oder Parallelbetrieb; erster Wert kein nachgewiesener Kaltstart. Gleiche Methode wie beim 10.000er-Test.

| Abfrage | CLI erste / Median / p95 (ms) | FPM erste / Median / p95 (ms) | EXPLAIN: Zugriff / Index / geschätzte Zeilen / Sortierung |
| --- | ---: | ---: | --- |
| current_single | 0.3383 / 0.1729 / 0.2729 | 0.2403 / 0.1457 / 0.1715 | const / PRIMARY / 1 / kein Filesort |
| current_batch | 0.2707 / 0.2419 / 0.3022 | 0.3008 / 0.1389 / 0.2800 | range / PRIMARY / 6 / kein Filesort |
| history_latest | 0.7302 / 0.4485 / 3.6958 | 0.4462 / 0.2991 / 0.3949 | ref / history_time / 1.000 / kein Filesort |
| history_window | 0.4901 / 0.2512 / 1.5959 | 0.3285 / 0.2579 / 0.3344 | range / history_time / 10 / Filesort |
| chart | 0.4236 / 0.3767 / 0.4497 | 0.3993 / 0.4447 / 0.6744 | ref / history_time / 1.000 / kein Filesort |
| identity_lookup | 0.2384 / 0.1191 / 0.1640 | 0.2500 / 0.1191 / 0.1539 | const / identity_lookup und PRIMARY / je 1 / kein Filesort |
| history_wide_window | 133.1552 / 123.2527 / 152.6096 | 124.4720 / 134.3951 / 168.0070 | index / history_time / CLI 5.000, FPM 5.003 / kein Filesort; Backward index scan |

Gemeinsame SQL-Definitionen/Parameter/Erwartungen stehen in querySet()/expectedQueries(). Bestehendes schmales Fenster: 00:10 inklusive bis 00:15 exklusive, aufsteigend nach Zeit/ID, LIMIT 20. **Neues breites Fenster:** Entity 7, 00:00 inklusive bis 07:30 exklusive, aufsteigend nach Zeit/ID, festes LIMIT 50; 900 passende Verlaufseinträge, davon die ersten 50 erwartet. Chart bleibt auf 25 Ergebnisse absteigend bis zum jeweils neuesten Zeitpunkt begrenzt. Alle Zeiten am festen UTC-Testtag.

**Wichtiger Befund:** LIMIT begrenzt die Ausgabe, garantiert aber keinen kleinen Suchaufwand. Beim breiten Fenster wählt der Optimizer einen rückwärts gerichteten Indexscan statt range/ref. Das 100-ms-Ziel wird schon vom ersten Wert und von beiden Medianen verfehlt. Kein Filesort bedeutet hier keine ausreichende Effizienz. EXPLAIN-Zeilen sind Schätzungen, tatsächliche untersuchte Zeilen wurden nicht gemessen. Kein zusätzlicher EXPLAIN-ANALYZE-, Optimierungs- oder Lasttest ausgeführt.

Die Laufzeitberichte mit ok=true bestätigen Korrektheit/Schutzprüfungen, **nicht** die Einhaltung sämtlicher Laufzeitziele. Für das breite Fenster ist die Freigabe eines hinreichend selektiven Leseplans offen.

### Vergleich mit 10.000 Zeilen und Zielwerten

Median jeweils CLI / FPM in ms:

| Muster | 10.000 History-Zeilen | 100.000 History-Zeilen | Einordnung |
| --- | ---: | ---: | --- |
| Current einzeln | 0.2226 / 0.1362 | 0.1729 / 0.1457 | klar unter Idealziel 20 ms |
| Neueste History | 0.4615 / 0.3126 | 0.4485 / 0.2991 | unter Ziel 100 ms |
| Schmales Fenster | 0.3940 / 0.2414 | 0.2512 / 0.2579 | unter Ziel 100 ms; Filesort weiter vorhanden |
| Chart, LIMIT 25 | 0.5006 / 0.3825 | 0.3767 / 0.4447 | unter Ziel 100 ms |
| Breites Fenster, LIMIT 50 | nicht Bestandteil der 10.000er-Messung | 123.2527 / 134.3951 | Ziel 100 ms verfehlt |

Größter p95 der vergleichbaren begrenzten History-Muster: CLI 3.6958 ms statt zuvor 1.7417 ms; weiterhin unter 100 ms. Schwankungen dieser kleinen, zeitlich getrennten Hosting-Stichproben belegen weder allgemeine Beschleunigung noch Skalierbarkeit. Das breite Fenster besitzt keinen direkten 10.000er-Vergleichswert. Keine Seitenladezeitbehauptung oder Freigabe für Parallel-/Produktivbetrieb.

### Batch-Schreiben und Größen

INSERT-Ausführung ohne DDL, Vorbereitung und Commit:

| Tabelle | Batches × maximale Zeilen | Summe ms | Batch-Median ms | Batch-p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Entity | 1 × 100 | 1.2492 | 1.2492 | 1.2492 |
| Identity | 1 × 100 | 1.7132 | 1.7132 | 1.7132 |
| History | 200 × 500 | 1762.3435 | 7.3126 | 12.5630 |
| Current | 1 × 100 | 1.7790 | 1.7790 | 1.7790 |
| Migrationsprotokoll | 1 × 1 | 0.2000 | 0.2000 | 0.2000 |

Zuvor History: 20 × 500, Summe 255.3558 ms, Median 12.1051 ms, p95 20.6671 ms. Zehnfache Datenmenge bei ungefähr 6,9-facher INSERT-Ausführungssumme in diesen einzelnen Läufen; keine Durchsatz-/Lastprognose.

Spätere, mit Session-Statistikablauf 0 gelesene **FPM-Metadaten**, ausdrücklich näherungsweise:

| Tabelle | Daten KiB | Sekundärindizes KiB | Geschätzte Zeilen |
| --- | ---: | ---: | ---: |
| Entity | 16 | 16 | 100 |
| Identity | 16 | 32 | 100 |
| History | 4.624 | 6.176 | 100.076 |
| Current | 16 | 16 | 100 |
| Migrationsprotokoll | 16 | 16 | 1 |

Zusammen ungefähr **10.944 KiB = 10,69 MiB**, vorher ungefähr 960 KiB. History allein ungefähr 10.800 KiB, vorher 816 KiB. InnoDB-Seitenbelegung ist keine exakte Nutzdaten-/Backupgröße; erste CLI-Größen direkt nach dem Laden waren noch nicht aussagekräftig. Die Schätzung 100.076 ersetzt nicht den bestätigten COUNT **100.000**. Keine Daten-Cache-Leerung, kein ANALYZE und keine globale Statistikänderung.

### Bereinigung, Prüfungen und Entscheidung

- FPM-Schutz vor Nutzung mit tatsächlichem HTTP 403 für nicht erlaubte Herkunft geprüft; bestehenden Passwort-/HTTPS-/IP-/Origin-/CSRF-/POST-Schutz wiederverwendet. Passwort nur vom Nutzer im maskierten Formular eingegeben; private Konfiguration außerhalb öffentlicher Verzeichnisse/GitHubs, Verzeichnisse 0700 und Passwortdatei 0600.
- Ausschließlich fünf eigene, im Manifest gespeicherte Tabellen nach Eigentumsprüfung entfernt. Ausgangsstand **null Tabellen** wiederhergestellt; keine Präfix-Pauschallöschung.
- Eigene Quellen vor Entfernung gegen GitHub-Hashes geprüft. Danach sämtliche privaten Testdateien, Passwort/Konfiguration, Manifest, Berichte, Schloss/Sitzungen sowie öffentlicher Einstieg und Zugriffsschutz entfernt.
- Einstieg danach **HTTP 404**, HTTPS-Startseite **HTTP 200** und vollständig bytegenau wie vorhandenes Fixture. Weiterhin **neun** geplante Aufgaben; keine gespeichert.
- Alle acht beteiligten PHP-Dateien unter Dogado PHP 8.4.12 gelintet. **17** Basisschutzprüfungen, unveränderte **80** 10.000er-Prüfungen und **264** neue Prüfungen bestanden; Offline-Tests ohne DB-Verbindung. Neue Tests decken Profiltrennung, Streaming, Grenzen, 200 Batchzeiten, feste Prüfsummen und fehlerhafte Manifeste ab.
- [Neue CI-Einbindung](../../tests/test_history_100000.py) ergänzt die vorhandenen Tests. Ein Abschluss-Commit mit [skip ci], identisch auf Prüfbranch einschließlich git diff --check HEAD^ HEAD validieren, Deploy überspringen, anschließend genau diesen Commit nach Main übernehmen. Endgültiger Lauf und Ergebnis stehen in Issue #5.
- Keine Änderungen an AGENTS.md, Workflows, Deployment-Secrets, fixlab oder bestehenden MOSA-Ressourcen; kein Produktionsdeployment, keine Million Zeilen, Parallel- oder Restore-Tests.

**Nächster sinnvoller Schritt:** das breite Zeitfenster und die Planwahl gezielt in einem gesondert freizugebenden Optimierungsauftrag untersuchen. In diesem Auftrag keine Abfrage-/Indexvarianten nachgetestet und keine weitere Datenstufe begonnen. Korrekte 100.000er-Datenverarbeitung ist belegt; der breite Leseweg ist vor weiterer Skalierung zu klären. **Issue #5 bleibt offen**, endgültiges Schema unfreigegeben.

## Phase 1E – breiten History-Leseweg gezielt optimieren

**Nachweisstand: 17.10.2026, 18:41:17 Europe/Berlin (MESZ, UTC+02:00), nach Live-Bereinigung. Fachliches Ergebnis: erfolgreich innerhalb dieses begrenzten Optimierungsauftrags.** Das breite Fenster erreicht unter CLI und FPM sowohl Median als auch p95 unter 100 ms. Ergebnissemantik und schnelle Vergleichsabfragen bleiben erhalten. Keine allgemeine Skalierungs-/Produktivfreigabe; Issue #5 bleibt offen.

### Neuer Auftrag und kontrollierter Vergleich

Ausgangsstand: 8b14363dabf0a596949c9172f343f10fc52193e5. Vor Facharbeit wurde **genau die neue native Nachricht** bestätigt: Eingang 18:24:18, Serverempfang 18:24:20 Europe/Berlin; quittiertes Describe/Plan und neuer Betreff **„Datenbank-Testplattform: breiten History-Leseweg optimieren“** mit sieben eigenen Schritten im bestehenden Kontrollzentrum sichtbar. Keine alten Turn-Kennungen oder künstlichen Start-/Stop-Ereignisse. Eine eigene unzulässige Step-Reihenfolge wurde abgewiesen und im selben Lauf über gültige Zustandsübergänge korrigiert; dies war kein Datenbankfehler. Nachfolgende Live-Befunde und Bereinigung wurden quittiert und sichtbar geprüft.

[Gemeinsamer Phase-1B-Kern](../../scripts/phase1b/probe.php), [Phase-1B-Adapter](../../scripts/phase1b/entry.php) und [Phase-1C/1D-Profil](../../scripts/phase1c/profile.php) wiederverwendet. Der [begrenzte Vergleichsablauf](../../scripts/phase1e/optimization.php) verwendet dieselbe gemeinsame Abfrage-, Mess-, Korrektheits-, Aufbau- und Bereinigungslogik. Keine parallele Testarchitektur.

**Einmaliger erneuter CLI-Aufbau:** genau 100.000 synthetische History-Zeilen, 100 künstliche Objekte × 1.000; Entity/Identity/Current jeweils 100, Migrationsprotokoll 1. Genau 200 gestreamte History-Batches à 500 und vier Nebenbatches. Keine weiteren Datenstufen, kein Anhängen, keine Wiederholungs- oder Parallelmessung. Alle drei Zustände nutzten denselben Bestand.

Ausgangsindex ausdrücklich wie im vorherigen Lauf aufgebaut: history_time(entity_id, observed_at DESC, id DESC). Unveränderte Baseline zuerst unter beiden SAPIs gemessen, danach **zwei** Kandidaten in fester Reihenfolge:
1. Nur in der Testverbindung prefer_ordering_index=off setzen; Index und SQL unverändert.
2. Den vorhandenen Index durch history_time(entity_id, observed_at ASC, id ASC) ersetzen; normale Optimizer-Präferenz wieder on. Kein zusätzlicher Index und keine SQL-Änderung.

Serverseitige Whitelist und privates Manifest begrenzen Reihenfolge und genau einen Lauf je Zustand/SAPI. FPM kann nur den zuvor per CLI vorbereiteten Zustand messen; HTTP kann weder Variante, Datenmenge noch Profil frei bestimmen. Neue Stage-Statistiken umgehen weder die bestehenden Profilgrenzen noch die unveränderte Grenze von 30 Werten je Statistik.

### Ursache mit geschätzter und tatsächlicher Sucharbeit

Tatsächlich **MySQL 8.0.26-16**, CLI **PHP 8.4.12**, FPM **PHP 8.4.26**, jeweils PDO-MySQL. EXPLAIN ANALYZE wurde sicher unterstützt und genau einmal je Zustand/SAPI zusätzlich zur regulären Messung ausgeführt, mit SELECT-Zeitgrenze 3 s. Es führt die begrenzte SELECT tatsächlich aus; seine instrumentierten Zeiten gehören nicht zu den elf normalen Laufzeitwerten.

| Zustand | EXPLAIN breite Abfrage | EXPLAIN ANALYZE, beide SAPIs |
| --- | --- | --- |
| Baseline | index / history_time; geschätzt CLI 5.000, FPM 5.003; Using where; Backward index scan; kein Filesort | Rückwärts-Indexscan liefert tatsächlich **93.050 Zeilen** an den Filter; Filter/LIMIT geben 50 aus. Instrumentierter Gesamtabschluss CLI 136,267 ms / FPM 128,605 ms. |
| Kandidat 1 | ref / history_sequence; geschätzt 1.000; Using where; Using filesort | Entity-Lookup liefert 1.000 Zeilen, Zeitfilter 900, Top-50-Sortierung/LIMIT 50. |
| Kandidat 2 | ref / history_time; geschätzt 1.000; Using index condition; kein Filesort | Selektiver Entity-Lookup mit Zeitbedingung liefert dem LIMIT **50 Zeilen**, ein Durchlauf. Instrumentierter Gesamtabschluss CLI 0,140 ms / FPM 0,152 ms. |

Die Ursache ist im gemessenen Lauf die **unselektive Planwahl zugunsten der vorhandenen Sortierreihenfolge**: Der rückwärts gerichtete Gesamtindexscan filtert die Entity erst nach vielen anderen Objekten. LIMIT 50 begrenzt die Ausgabe und verhindert diese Sucharbeit nicht. Das reine Abschalten der Sortierindex-Präferenz beseitigt den schlechten Plan bereits, benötigt aber mehr Entity-Zeilen und eine Sortierung. Die strukturelle ASC-Variante ermöglicht bei normaler Optimizer-Konfiguration einen selektiven Zugriff ohne Filesort.

Die tatsächlichen Zeilen oben sind die vom jeweiligen ANALYZE-Operator ausgegebenen Zeilen, getrennt von Optimizer-Schätzungen. Interne InnoDB-Prüfschritte, physische Seitenzugriffe und Cache-Treffer wurden nicht separat gemessen. Es wird kein allgemeiner MySQL-Fehler oder Vorteil aller Vorwärts- gegenüber Rückwärtsscans behauptet.

### Laufzeiten auf identischem Bestand

Je fünf Abfragetypen, drei Zustände und SAPI elf reguläre Ausführungen: **erste separat; Median/p95 aus zehn Folgewerten**, Nearest-Rank (p95 hier Maximum). Insgesamt 330 reguläre, begrenzte SELECT-Messungen. Zusätzlich gemeinsame Korrektheitsprüfungen und die sechs genannten ANALYZE-Ausführungen; keine weiteren Kandidaten oder Messwiederholungen.

PHP-Wandzeit für PDO execute plus begrenzten Abruf; Vorbereitung/Verbindung/DDL nicht enthalten. Keine Cache-Leerung; erster Wert kein nachgewiesener Kaltstart. Sequenzielle Hosting-Stichprobe, kein Last-/Paralleltest.

#### Baseline: DESC, Optimizer normal

| Abfrage | CLI erste / Median / p95 (ms) | FPM erste / Median / p95 (ms) |
| --- | ---: | ---: |
| Current einzeln | 0.3859 / 0.1435 / 0.1895 | 0.2121 / 0.0957 / 0.1637 |
| Neueste History | 0.4506 / 0.3039 / 1.0191 | 0.3858 / 0.3024 / 0.3789 |
| Schmales Zeitfenster | 0.3028 / 0.3643 / 0.5574 | 0.2553 / 0.2083 / 0.2486 |
| Chart, LIMIT 25 | 0.3818 / 0.4721 / 0.6281 | 0.3464 / 0.3579 / 1.0415 |
| Breites Zeitfenster, LIMIT 50 | 130.4747 / 118.4536 / 124.1564 | 124.9075 / 121.8794 / 125.0455 |

#### Kandidat 1: DESC, prefer_ordering_index=off

| Abfrage | CLI erste / Median / p95 (ms) | FPM erste / Median / p95 (ms) |
| --- | ---: | ---: |
| Current einzeln | 0.2394 / 0.0990 / 0.1388 | 0.2952 / 0.1229 / 0.2347 |
| Neueste History | 0.3517 / 0.2733 / 0.3864 | 0.4014 / 0.2852 / 0.3600 |
| Schmales Zeitfenster | 0.2400 / 0.1924 / 0.2260 | 0.2379 / 0.1853 / 0.2286 |
| Chart, LIMIT 25 | 0.3779 / 0.3328 / 0.3667 | 0.3377 / 0.3215 / 0.3679 |
| Breites Zeitfenster, LIMIT 50 | 1.8552 / 1.7399 / 40.8880 | 1.7223 / 1.6035 / 1.7269 |

#### Kandidat 2: ASC, Optimizer normal

| Abfrage | CLI erste / Median / p95 (ms) | FPM erste / Median / p95 (ms) |
| --- | ---: | ---: |
| Current einzeln | 0.2608 / 0.0986 / 0.1710 | 0.2024 / 0.0965 / 0.1247 |
| Neueste History | 0.8378 / 0.2796 / 0.3311 | 0.3727 / 0.2656 / 0.3433 |
| Schmales Zeitfenster | 0.2441 / 0.1865 / 0.2223 | 0.2622 / 0.1890 / 0.2411 |
| Chart, LIMIT 25 | 0.3684 / 0.3333 / 0.4016 | 0.3573 / 0.3221 / 0.8414 |
| Breites Zeitfenster, LIMIT 50 | 0.4120 / 0.3575 / 0.4157 | 0.4530 / 0.3814 / 0.4315 |

**Zielvergleich:** breite Abfrage vorher in diesem Lauf Median CLI/FPM **118,4536 / 121,8794 ms**, p95 **124,1564 / 125,0455 ms**; nach ASC-Umstellung Median **0,3575 / 0,3814 ms**, p95 **0,4157 / 0,4315 ms**. Beide Kennwerte beider SAPIs klar unter **100 ms**, auch die ersten Werte. Zum älteren Phase-1D-Lauf (123,2527 / 134,3951 ms Median und 152,6096 / 168,0070 ms p95) passt die erneut langsame Baseline; maßgeblich für den Optimierungsvergleich ist die Baseline desselben Laufs.

Die vier bisherigen kritischen Vergleichsmuster zeigen keine wesentliche Regression: Current-Median CLI 0,1435 → 0,0986 ms, FPM 0,0957 → 0,0965 ms; neueste History 0,3039 → 0,2796 bzw. 0,3024 → 0,2656 ms; schmales Fenster 0,3643 → 0,1865 bzw. 0,2083 → 0,1890 ms; Chart 0,4721 → 0,3333 bzw. 0,3579 → 0,3221 ms. Alle Vergleichs-p95 nach ASC unter 1 ms. Diese kleinen Schwankungen belegen keine allgemeine Beschleunigung aller Seiten.

Gewählter Index: Current weiter const/PRIMARY; neueste History ref/history_time mit Backward index scan; schmales Fenster range/history_time, geschätzt zehn Zeilen und kein Filesort; Chart ref/history_time mit Backward index scan. Kein ungebundener Full Scan in diesen normalen Lesewegen.

### Semantik, allgemeine Integration und Indexaufwand

Alle sechs Stage-/SAPI-Berichte bestätigten vollständige Korrektheit: exakte Mengen, eindeutige Zuordnungen, keine verwaisten Daten, Current = neueste History, erwartete Ergebnisse aller gemeinsamen Abfragen, leere/Zeitgrenzenfälle und Zeitstempelgleichstände, kein Current-Duplikat oder Rückschritt, erfolgreiches Rollback und unveränderte History-Prüfsumme.

Die breite Abfrage ist **bytegleich unverändert**: eine gebundene Entity, untere Zeitgrenze inklusive, obere exklusiv, ORDER BY observed_at,id aufsteigend, LIMIT 50. Dieselben Parameter und exakt dieselben vollständigen 50 erwarteten Zeilen in Baseline und beiden Kandidaten. Im Testzeitraum liegen 900 passende History-Zeilen; Gleichstände werden unverändert nach ID aufgelöst.

Die erfolgreiche Lösung ist **ASC als allgemeine Voreinstellung des gemeinsamen Index-Builders** für beide vorhandenen Profile. Die explizite DESC-Option dient dem reproduzierbaren alten Ausgangszustand dieses Vergleichs. Keine Bedingung für Entity 7, Datum oder Zeilenzahl, keine FORCE-INDEX-Dauerlösung, kein dauerhaft geänderter Optimizer-Schalter, keine neue Summary-/Cache-Tabelle und kein endgültiges Core-Schema. Absteigende Latest-/Chart-Abfragen verwenden denselben ASC-Index rückwärts und bleiben schnell.

- History behält PRIMARY und **dieselben zwei Sekundärindizes** (eindeutiger Sequenzindex und Zeitindex), mit denselben Spalten/Breiten. **Kein zusätzlicher dauerhafter Indexspeicher durch einen weiteren Index.**
- Einmaliger DROP/ADD-Umbau ausschließlich der eigenen History-Tabelle: **335,4381 ms**. Temporärer DDL-Arbeitsraum/Spitzenspeicher und künftige Schreiblast wurden nicht gemessen; dies ist keine kostenfreie Produktionsmigration.
- Näherungsweise Metadaten vor/nach Umbau: History **4.734.976 Bytes Daten + 6.324.224 Bytes Sekundärindizes**; fünf Tabellen zusammen **10.944 KiB**. Kein erkennbarer Mehrverbrauch in diesen Metadaten. Direkt nach Laden gelesene CLI-Größen waren noch veraltet; spätere FPM-Werte verwenden.
- InnoDB-Seitenbelegung ist keine exakte Nutzdaten-/Backupgröße; Metadaten können zeitlich nachlaufen. Keine Cache-Leerung, kein globales ANALYZE/Flush und keine globale Einstellung verändert. Der Umbau ersetzt die Indexrichtung; seine gemeldeten Größen beweisen keine allgemein identische physische Belegung.

### Schutz, Bereinigung und Prüfungen

- Exakte isolierte Testdatenbank, bestehender Testbenutzer und 127.0.0.1:3307 vor Schreibblöcken geprüft. Keine Rechte erweitert; utf8mb4_0900_as_cs, strikte Session-Modi, UTC und REPEATABLE-READ beibehalten.
- Derselbe bestehende Passwort-/HTTPS-/IP-/Host-/Origin-/POST-/CSRF-Schutz; **vor Nutzung tatsächlich HTTP 403** für nicht erlaubte Herkunft. Nutzer gab das bestehende Passwort ausschließlich im maskierten Formular ein. Keine Secrets in GitHub, Statusmeldungen oder Ausgaben.
- Derselbe kurzlebige geschützte Browser-Login für die drei serverseitig vorbereiteten Zustände; jedes Mal ein frisches einmaliges CSRF-Token, keine öffentliche Variantenwahl, keine Tests durch GET. Nach der letzten Variante Sitzung zerstört.
- Privater Code und Konfiguration außerhalb öffentlicher Dokumentstämme/GitHubs, Verzeichnisse 0700 und Passwortdatei 0600. CLI ausschließlich über das ungespeicherte inaktive Plesk-„Jetzt ausführen“-Formular ohne Benachrichtigungen; anschließend abgebrochen. **Neun geplante Aufgaben vor/nachher**, keine gespeichert.
- Ausschließlich fünf eigene Tabellen nach Manifest-/Eigentumsprüfung entfernt; **null Tabellen** wiederhergestellt. Elf Quellen gegen GitHub-Hashes und sechs erfolgreiche Berichte vor Entfernung geprüft. Danach eigener Code, Passwort/Konfiguration, Manifest, Berichte, Schloss/Sitzungen und öffentlicher Einstieg vollständig entfernt.
- Einstieg anschließend **HTTP 404**, neutrale HTTPS-Startseite **HTTP 200**, sichtbar und vollständig bytegenau wie vorhandenes Fixture. Keine Zertifikats-/Startseitenänderung.
- **Elf PHP-Dateien gelintet**, **17** bestehende Basis-, **80** unveränderte 10.000er-, **264** unveränderte 100.000er- sowie **54** neue Offline-Prüfungen erfolgreich, ohne Datenbankverbindung. Angepasster Sitzungsadapter anschließend erneut erfolgreich gelintet.
- [Neue CI-Prüfung](../../tests/test_history_optimization.py) prüft PHP-Lint und Offline-Schutz für Indexrichtung, Zustand/SAPI-Reihenfolge, Wiederholungs-/Kandidatenbudget, unveränderte Query-Semantik und Trennung geschätzter/tatsächlicher ANALYZE-Zeilen.
- Veröffentlichungsschranke: genau ein Abschluss-Commit mit [skip ci], derselbe SHA auf Prüfbranch im unveränderten Validierungsworkflow einschließlich git diff --check HEAD^ HEAD; Deploy muss übersprungen sein, erst danach derselbe Commit auf main. Konkreter Lauf und Resultat werden in Issue #5 festgehalten.

**Entscheidung:** ASC-Index allgemein im gemeinsamen Testkern übernehmen. Die gestellte begrenzte Optimierung ist fachlich erfolgreich; die vorherige offene Planwahl ist für diesen 100.000er-Leseweg geklärt. Keine Freigabe für Million Zeilen, Parallelbetrieb, Last, Backup/Restore, endgültiges Core-Schema oder Produktion. Nächste Testphase wurde nicht begonnen. **Issue #5 bleibt offen.**

## Phase 1F – überlappende Lese-/Schreibtransaktionen und kontrollierter Konflikt

**Nachweisstand: 17.10.2026, 19:26:06 Europe/Berlin (MESZ, UTC+02:00), nach Live-Bereinigung. Fachliches Ergebnis: erfolgreich im ausdrücklich begrenzten Szenarioumfang.** Parallele logische Transaktionen lesen und schreiben im Test sicher: stabile REPEATABLE-READ-Snapshots, keine Dirty Reads, keine Rollback-Reste und keine unerwarteten Sperren oder Datenfehler. Je SAPI ein erwarteter Lock-Wait wurde vollständig beendet und genau einmal erfolgreich wiederholt. Kein allgemeiner Last-/Produktivnachweis; Issue #5 bleibt offen.

### Auftragsnachweis und gemeinsame Grundlage

Ausgangsstand: d62573a43a6f8b358cd6fb740907f23e060ee7dc. Vor Facharbeit neuer nativer Eingang **19:05:32**, Serverempfang **19:05:34 Europe/Berlin** bestätigt. Describe und Plan quittiert und genau der neue Betreff **„Datenbank-Testplattform: parallele Zugriffe und Transaktionskonflikte“** mit sechs eigenen Schritten im vorhandenen KI-Kontrollzentrum sichtbar. Wartephase, tatsächliche Live-Ergebnisse und Bereinigung ebenfalls quittiert und sichtbar kontrolliert. Keine alten Turn-Kennungen oder künstlichen Start-/Stop-Ereignisse.

Die vollständige native Nachricht ist die Auftragsgrundlage. **Kein Anhang gelesen**, kein lokaler fachlicher Datei-/Shell-/Launcherzugriff; lokal ausschließlich der freigegebene Statusadapter und seine JSON-Meldungen. Kein Zugriff auf E:.

[Phase-1B-Verbindungs-/Zielprüfung](../../scripts/phase1b/probe.php), [geschützter gemeinsamer Adapter](../../scripts/phase1b/entry.php), [Phase-1C/D/E-Aufbau, ASC-Index, Abfragen, Upsert, Korrektheit und Bereinigung](../../scripts/phase1c/profile.php) wiederverwendet. [Phase-1F-Szenarien](../../scripts/phase1f/concurrency.php) werden über einen optionalen serverseitigen Mess-Callback innerhalb desselben Manifest-/Schloss-/Fehlerbereinigungsablaufs ausgeführt. Keine zweite Testarchitektur.

Der gemeinsame Messhelfer akzeptiert nun eine begrenzte Stichprobengröße. **Bestehende Voreinstellung elf und bestehende 100-/10.000-/100.000-Grenzen unverändert**; dieser Auftrag wählt ausdrücklich zehn Ausführungen. HTTP kann weder Callback, Profil, Verbindungszahl noch Wiederholungen frei bestimmen.

### Tatsächlicher Umfang und Ablauf

Einmaliger CLI-Aufbau mit bestehendem history100000_v1 und allgemeinem ASC-Zeitindex: **100.000 synthetische History-Zeilen**, 100 Objekte × 1.000; Entity/Identity/Current jeweils 100, Migrationsprotokoll 1. 200 History-Batches à 500 plus vier Nebenbatches. Derselbe Bestand unter **PHP 8.4.12 CLI** und **PHP 8.4.26 FPM**, jeweils PDO-MySQL, geprüft. Kein weiterer Aufbau und kein History-DML nach dem Laden.

Je SAPI **genau vier unabhängig bestätigte PDO-Verbindungen**, keine fünfte Verbindung. Alle vier mit identischer strikter utf8mb4-/UTC-/REPEATABLE-READ-Konfiguration; genaue isolierte Datenbank, bestehender Testbenutzer und 127.0.0.1:3307 vor Schreibblöcken geprüft. Keine Rechte oder globalen Einstellungen geändert.

Die Verbindungen werden in einem PHP-Lauf gezielt ineinander verschachtelt: Transaktionen überlappen wirklich im Datenbankserver und halten ihre Sperren, während eine andere Verbindung arbeitet. Dies sind **kontrolliert orchestrierte Transaktionsüberschneidungen**, keine gleichzeitig gestarteten HTTP-Worker, keine CPU-/Durchsatz- oder Anfragelastmessung.

| Szenario | Durchläufe CLI / FPM | Tatsächlicher Nachweis |
| --- | ---: | --- |
| Snapshot, Dirty Read und Commit-Sichtbarkeit | 3 / 3 | Alter Leser sieht vor und nach Writer-Commit weiter den alten Stand. Zweite unabhängige Verbindung sieht keine uncommittete Änderung. Neue Lesertransaktionen sehen den bestätigten neuen Stand. |
| Rollback | 3 / 3 | Eigene Current-Zeile innerhalb der Writer-Transaktion gelöscht; zweite Verbindung sieht sie weiterhin. Nach Rollback sehen alle vier Verbindungen exakt den ursprünglichen Zustand. Kein Restzustand. |
| Writer auf verschiedenen Entities | 3 / 3 | Writer A hält Entity 3, Writer C schreibt Entity 4 bei weiter offener A-Transaktion. Beide bleiben gleichzeitig offen; andere Leser sehen keinen Dirty Read. Beide Commits erfolgreich, Current danach eindeutig und vollständig auf dem neuesten Sollstand. **Null unerwartete Lock-Konflikte.** |
| Derselbe Current-Datensatz | 1 / 1 | A hält Entity 5; C wartet auf dieselbe Zeile und erhält erwarteten MySQL-Fehler 1205/HY000. Ganze wartende Transaktion explizit zurückgerollt. A committed; C startet genau einen neuen Versuch und committed erfolgreich den eindeutig neueren Stand. |

Damit sechs Wiederholungen je normalem Szenario über beide SAPIs (unter zehn) und insgesamt **zwei** absichtliche Konflikte (unter drei). Keine automatische Wiederholung normaler Szenarien oder beliebiger SQL-Fehler; Deadlocks/andere Fehler gelten nicht als erwarteter Lock-Wait.

Für beobachtbare Zustandsübergänge werden ausschließlich eigene Current-Testzeilen als Fixture auf den vorhandenen synthetischen History-Stand Sequenz 998 gesetzt. Der eigentliche Upsert führt wieder zu Sequenz 1.000; beim Konflikt A zu 999 und der einzige Retry zu 1.000. Die beiden letzten Sequenzen besitzen denselben Zeitstempel und werden über die History-ID geordnet. Diese ausdrücklich künstliche Fixture-Vorbereitung ist keine fachliche Rückwärtsmigration; sie verändert keine History-Zeile. Nach abgeschlossenen normalen Szenarien und nach dem Konflikt-Retry stimmen alle 100 Current-Zeilen wieder exakt mit der jeweils neuesten History überein.

### Erwarteter Konflikt und begrenzter Retry

| Messpunkt | CLI | FPM |
| --- | ---: | ---: |
| Zurückgelesenes Session-innodb_lock_wait_timeout des wartenden Writers | 1 s | 1 s |
| Tatsächliche Dauer des erwarteten Fehlversuchs | **2001,0694 ms** | **2001,0494 ms** |
| Erwarteter Fehler | 1205 / HY000 | 1205 / HY000 |
| Ganze wartende Transaktion explizit zurückgerollt | ja | ja |
| Retry-Anzahl | **genau 1** | **genau 1** |
| Erfolgreicher Retry einschließlich Upsert und Commit | **0,7533 ms** | **0,6474 ms** |
| Neuester Current-Stand nach Retry | bestätigt | bestätigt |

Die tatsächlich gemessene Wartezeit lag trotz zurückgelesenem Sessionwert von einer Sekunde bei etwa **zwei Sekunden**. Keine Behauptung einer exakt einsekündigen Wandzeitgrenze; die Ursache dieser Zeitabweichung wurde im begrenzten Auftrag nicht weiter untersucht. Der Konflikt selbst ist ausdrücklich erwartet und endet mit Fehler 1205. Transaktions-/Anwendungsabbruchgrenzen bleiben begrenzt; keine globalen Timeout-Änderungen.

Ein Lock-Wait kann nur das Statement zurückrollen. Deshalb endet der Test unabhängig von der Server-Timeout-Rollback-Politik die vollständige fehlgeschlagene Transaktion, bevor genau eine neue Transaktion beginnt. Im tatsächlichen Lauf war jeweils ein expliziter Rollback erforderlich. Keine blind fortgesetzte Transaktion, kein zweiter Retry, kein abgefangener beliebiger SQL-Fehler als scheinbarer Erfolg.

Upsert-Ausführung auf verschiedenen Entities bei gleichzeitig offenen Transaktionen, jeweils A/C in ms:

| Durchlauf | CLI | FPM |
| --- | ---: | ---: |
| 1 | 0,3830 / 0,4168 | 0,4411 / 0,4663 |
| 2 | 0,3182 / 0,3540 | 0,5064 / 0,7060 |
| 3 | 0,3122 / 0,3269 | 0,4116 / 0,3696 |

Diese Upsert-Zeiten enthalten Statement-Vorbereitung und Ausführung, aber keinen Commit oder Verbindungsaufbau. Keine Durchsatzprognose.

### Normale Reads bei zwei offenen Schreibtransaktionen

Während Writer A und C die verschiedenen Current-Zeilen von Entity 3/4 uncommittet halten, liest eine dritte Verbindung die unveränderten gemeinsamen Abfragen für **Entity 7**. Beide Writer bleiben während der gesamten Messung offen; eine vierte Verbindung bestätigt die Unsichtbarkeit ihrer uncommitteten Zustände.

Je fünf Muster und SAPI **zehn** reguläre Messungen, erste separat; Median/p95 aus neun Folgewerten (Nearest-Rank, p95 hier Maximum). Insgesamt 100 begrenzte Leseausführungen über beide SAPIs, kein zusätzlicher Last-/Wiederholungslauf. Gleiche PDO-execute-plus-fetch-Methode wie zuvor; ohne Verbindung/Vorbereitung, ohne Cache-Leerung und ohne nachgewiesenen Kaltstart.

| Abfrage auf Entity 7 | CLI erste / Median / p95 (ms) | FPM erste / Median / p95 (ms) | Ziel |
| --- | ---: | ---: | ---: |
| Current einzeln | 0.1655 / 0.0954 / 0.1230 | 0.1797 / 0.1652 / 0.2319 | <20 ms |
| Neueste History | 0.3501 / 0.2596 / 0.3088 | 0.4228 / 0.3023 / 0.3655 | <100 ms |
| Schmales History-Fenster | 0.2309 / 0.1909 / 0.2214 | 0.2965 / 0.2391 / 0.2471 | <100 ms |
| Chart, LIMIT 25 | 0.3299 / 0.3031 / 0.3752 | 0.4030 / 0.4430 / 0.6994 | <100 ms |
| Breites History-Fenster, LIMIT 50 | 0.3669 / 0.3244 / 0.3392 | 0.4577 / 0.4067 / 0.6330 | <100 ms |

Alle Median- und p95-Werte liegen unter den vereinbarten Zielen. **Current-Median CLI/FPM 0,0954 / 0,1652 ms gegenüber ideal <20 ms**; höchster History-p95 **0,6994 ms gegenüber <100 ms**. Das breite Fenster bleibt mit Median **0,3244 / 0,4067 ms** und p95 **0,3392 / 0,6330 ms** schnell.

EXPLAIN bestätigt unverändert: Current const/PRIMARY; neueste History ref/history_time, rückwärts; schmales Fenster range/history_time mit geschätzt zehn Zeilen; Chart ref/history_time rückwärts; breites Fenster ref/history_time mit Indexbedingung. Bei diesen Mustern kein Filesort und kein ungebundener Full Scan. EXPLAIN-Zeilen sind Schätzungen; keine zusätzliche EXPLAIN-ANALYZE-Serie in diesem Auftrag.

### History, Current und Bereinigung

Beide Laufzeiten bestätigten **vor/nach jeweils 100.000 History-Zeilen** und exakt dieselbe SHA-256-Prüfsumme:

9d1be385cdc925c8a5968ffd1ea899fa9aa3b2e82369ef14d47e233dfbf98d68

Die History wurde nach dem Aufbau ausschließlich gelesen; die Szenarien schreiben nur eigene Current-Zeilen. Nachweis ist die Unverändertheit dieses Bestands, keine behauptete allgemeine technische Erzwingung von Append-only-Rechten. Keine Update-/Delete-Rechte geändert. Alle gemeinsamen Integritäts-, eindeutigen Zuordnungs-, Current-Recency-, Zeitgrenzen-/Gleichstands-, Upsert-/Rollback- und Prüfsummenprüfungen vor/nach bestanden. Nach Szenarien keine offenen Transaktionen.

- FPM vor Nutzung tatsächlich durch **HTTP 403** für nicht erlaubte Herkunft geschützt. Bestehende HTTPS-/Host-/IP-/Origin-/POST-/CSRF-Prüfungen und kurzlebige Sitzung verwendet. Keine öffentlichen Schreib-GETs oder Diagnosen.
- Nutzer gab das bestehende Testpasswort ausschließlich im maskierten Formular ein. Konfiguration/Passwort und Code nur im eigenen privaten Bereich außerhalb öffentlicher Dokumentstämme/GitHubs; Verzeichnisse 0700, Passwortdatei 0600. Kein Passwort zurückgesetzt, keine fremden Anwendungskonfigurationen gelesen.
- Abgelaufene Plesk-Sitzung über vorhandenen oneHome-Zugang regulär erneuert. CLI ausschließlich über ungespeichertes, inaktives „Jetzt ausführen“-Formular ohne Benachrichtigungen; abschließend abgebrochen. **Neun geplante Aufgaben vor/nachher**, keine gespeichert.
- Ausschließlich fünf eigene Tabellen nach Manifest/Eigentumsmerkmal entfernt; **null Tabellen** wiederhergestellt. Vierzehn Quellen gegen GitHub-Hashes und beide erfolgreiche Berichte vor Entfernung geprüft.
- Privater Code, Zielkonfiguration/Passwort, Manifest, Ergebnisse, Schloss/Sitzungen und öffentlicher Einstieg vollständig entfernt. Einstieg anschließend **HTTP 404**; neutrale HTTPS-Startseite **HTTP 200**, sichtbar und vollständig bytegenau unverändert.
- Keine Änderungen an fixlab, Workflows, Deployment-Secrets, Zertifikaten, Startseite oder Produktivressourcen. Keine Million Zeilen, Last-/Dauertests oder Restore-Tests; keine nächste Phase begonnen.

### Offline-Prüfung und Veröffentlichungsschranke

**Vierzehn PHP-Dateien gelintet**, **17** Basis-, **80** 10.000er-, **264** 100.000er-, **54** Optimierungs- sowie **48** neue Transaktionsprüfungen erfolgreich, jeweils ohne Datenbankverbindung. Angepasste Timeout-Rollback-Behandlung vor den Live-Tests erneut gelintet und durch die betroffenen 48 Offline-Prüfungen bestätigt.

[Neue Offline-Prüfung](../../tests/test_concurrency.py) deckt Verbindungs-/Szenario-/Konflikt-/Lesebudgets, exakte Fehlerklassifikation statt beliebigem Retry, unveränderte gemeinsame Mess-Voreinstellung, sichere Abfrageauswahl und vorhandenen ASC-Index ab. Tatsächliche Transaktions-/Lock-Nachweise stammen ausschließlich aus den oben beschriebenen Live-Läufen.

Genau ein Abschluss-Commit mit [skip ci]; derselbe SHA ist vor Übernahme auf main im unveränderten vorhandenen Prüfbranch-Workflow einschließlich git diff --check HEAD^ HEAD zu validieren, Deploy muss übersprungen sein. Konkreter Lauf und Resultat stehen im abschließenden Issue-#5-Kommentar.

**Einordnung:** Die geprüften überlappenden Transaktionen funktionieren sicher und schnell; der erwartete Konflikt wird kontrolliert mit genau einem Retry aufgelöst. Die Messung ist **kein allgemeiner Last-, Worker-Parallelitäts-, Dauer-, Skalierungs- oder Produktivnachweis**. Weitere Tests bleiben gesondert freizugeben; in diesem Auftrag keine nächste Phase. **Issue #5 bleibt offen.**

## Phase 1G – Backup-/Restore-Fortsetzung: Zugang fehlt

**Prüfzeitpunkt: 17.10.2026, 20:09:01 Uhr Europe/Berlin (MESZ, UTC+02:00). Fachliches Ergebnis: nicht durchgeführt; Backup/Restore weiterhin offen.**

### Bestätigt

- Der neue native Fortsetzungsauftrag ist im KI-Kontrollzentrum sichtbar: Eingang 20:04:58 Uhr, Serverempfang 20:05:00 Uhr; Describe und Plan wurden zugestellt.
- Dogado bestätigt die bereits erfolgte Anlage der einen getrennten MySQL-8-Restore-Testdatenbank samt eigenem Benutzer am lokalen Testendpunkt. Insgesamt werden fünf von 50 Datenbanken angezeigt. Die vorhandene Restore-Datenbank und das vom Nutzer gesetzte Passwort wurden unverändert belassen.
- Eine einmalige providerseitige Prüfung bestätigt PHP **8.4.12 CLI** und den PDO-MySQL-Treiber. Ausschließlich das Vorhandensein eigener Test-Konfiguration wurde geprüft, ohne Passwortinhalte zu öffnen oder auszugeben.
- Die vorgesehenen privaten Passwortdateien für Quelle und Restore fehlen. Auch die eigene Passwortdatei der vorigen Transaktionsphase ist nicht mehr vorhanden; deren Entfernung war Bestandteil der dort nachgewiesenen Bereinigung. Ein bei Dogado gesetztes DB-Passwort wird dadurch nicht automatisch zu einer geschützten PHP-Testkonfiguration.
- Der Nutzer schließt eine erneute Passwortabfrage ausdrücklich aus. Daher keine Passwortabfrage, kein Zurücksetzen, keine neue Datenbank, kein Durchsuchen fremder Anwendungskonfigurationen und kein Versuch mit anderen Zugangsdaten.

### Fehlender Nachweis und Aussagegrenze

Ohne verfügbare geschützte Zugangskonfiguration kann der gemeinsame Phase-1B–1F-Testkern weder Quelle noch Restore-Ziel authentifizieren. Deshalb **kein Aufbau des synthetischen Bestands, kein Backup und kein Restore** in dieser Fortsetzung.

| Erforderlicher Nachweis | Ergebnis |
| --- | --- |
| 100 Entity, 100 Identity, 100.000 History, 100 Current, 1 Migration | Nicht aufgebaut |
| Quellstruktur, Indizes, exakte Zeilenzahlen und Prüfsummen | Nicht erhoben |
| Backup-Verfahren, Dateigröße und Backup-Dauer | Nicht praktisch geprüft / nicht erhoben |
| Restore in getrenntes leeres Ziel und Restore-Dauer | Nicht durchgeführt / nicht erhoben |
| Gleichheit aller fünf Tabellen, Strukturen, Zeilenzahlen und Prüfsummen | Offen |
| Current = neueste History, keine verwaisten oder doppelten Datensätze | Für diesen Testbestand offen |
| Einmalige funktionale Reads im Restore-Ziel | Nicht durchgeführt |
| Beide Datenbanken aktuell mit null Tabellen | Ohne authentifizierte Verbindung nicht neu nachgewiesen |

### Unveränderter Zustand und Veröffentlichung

- Dieser Lauf hat keine Testtabellen, Backups, privaten Testdateien oder öffentlichen Testeinstiege erzeugt. Der vorgesehene eigene Backup-Testbereich und Einstieg sind providerseitig nachweislich nicht vorhanden.
- Neutrale HTTPS-Startseite: **HTTP 200**, sichtbar „Technische Testumgebung aktiv“, vollständiger Antworttext gegen den bestehenden Git-Blob bytegenau unverändert.
- Providerprüfung ausschließlich über „Jetzt ausführen“ im ungespeicherten, deaktivierten Plesk-Dialog; anschließend abgebrochen. Kein dauerhafter Cronjob angelegt. Die Aufgabenliste zeigt weiterhin neun Einträge.
- Keine Änderungen an Produktivressourcen, fixlab, Workflows, Deployment-Secrets, Zertifikaten oder Startseite. Keine lokalen fachlichen Shell-/Laufwerkszugriffe.
- Ausschließlich diese Phasendokumentation wird geändert. Die vorbereiteten Codeentwürfe werden nicht als geprüfte Backup-/Restore-Implementierung veröffentlicht.
- Ein Abschluss-Commit mit [skip ci] dokumentiert den **unvollständigen** Stand. Vor Übernahme desselben SHA auf main muss der unveränderte Validierungsworkflow auf dem Prüfbranch erfolgreich sein und Deploy überspringen. Die konkreten Prüfergebnisse und der Lauf stehen im Kommentar zu Issue #5.

**Blocker:** Ein vorhandener sicherer Authentifizierungsweg für beide Testdatenbanken fehlt. Das gesetzte Passwort allein ersetzt diesen Weg nicht. Der vollständige Wiederherstellungsnachweis bleibt erforderlich; keine Schema- oder Produktivfreigabe. **Issue #5 bleibt offen.** Keine nächste Testphase gestartet.


## Phase 1G – Backup/Restore praktisch nachgewiesen

**Verifiziert: 18.10.2026, 10:10:30 Uhr Europe/Berlin (MESZ, UTC+02:00). Bereinigung: 10:11:56 Uhr. Fachlich erfolgreich für den isolierten synthetischen Testbestand.**

Die bereits vorhandenen Quell- und Restore-Testdatenbanken wurden mit ihren eigenen bestehenden Benutzern am festen lokalen MySQL-8-Endpunkt 127.0.0.1:3307 authentifiziert und vor Schreibzugriffen als leer bestätigt. Keine Datenbank angelegt, kein Passwort zurückgesetzt. Beide Datenbanken bleiben nach Abschluss leer bestehen.

### Verfahren und Messung

Gemeinsamer Phase-1B-Verbindungskern sowie Phase-1C/D-Profil, Generator, Tabellen-Eigentumsnachweis und Bereinigung wiederverwendet. Einmalig 100 Entity, 100 Identity, **100.000 History**, 100 Current und 1 Migration in 204 Batches (maximal 500 Zeilen) erzeugt. Der allgemeine ASC-History-Index aus Phase 1E bleibt unverändert.

Die neue wiederverwendbare Phase-1G-Logik schreibt providerseitig eine private JSONL-Sicherung: exaktes SHOW CREATE TABLE und typisierte Zeilen in höchstens 500er-Batches, Primärschlüsselreihenfolge, festes Format und Abschlussmarker. Keine Zugangsdaten, CREATE DATABASE, DROP DATABASE oder Datenbankauswahl im Backup. Der Import akzeptiert ausschließlich die im verifizierten Manifest benannten fünf Tabellen, die exakte vertrauenswürdige Quell-DDL und ein unverändertes Backup mit passendem SHA-256; ausschließlich die getrennte leere Restore-Datenbank wird beschrieben. Fremdschlüssel bleiben eingeschaltet. Rechte und globale MySQL-Einstellungen werden nicht geändert.

| Messwert | Tatsächliches Ergebnis |
| --- | --- |
| PHP CLI | 8.4.12, PDO-MySQL |
| Backup-Größe | 4.983.041 Bytes |
| Backup-Dauer | 211,8804 ms |
| Restore-Dauer, erfolgreicher korrigierter Lauf | 2.015,2001 ms |
| Backup-SHA-256 | 5ff3324a0e13075250aeab2510de1e08c4943c79296966796212ca12f8c662ab |

Backup-Dauer umfasst das Schreiben und Flushen der JSONL-Datei, ohne Bestandsaufbau, Vorprüfung oder anschließende Dateihashberechnung. Restore-Dauer umfasst DDL und Import einschließlich Tabellen-Commits, ohne vorgeschaltete Dateihashprüfung und nachgelagerte Gesamtvergleiche. Keine neue Performance-/Lastmessreihe.

### Exakter Vergleich

Vorherige Quelle, wiederhergestelltes Ziel und erneut geprüfte Quelle stimmen in allen fünf Tabellen, Spalten, relevanten Indizes, Constraints, Engine InnoDB, utf8mb4 und Kollation utf8mb4_0900_as_cs überein. Zeilenzahlen exakt 100 / 100 / 100.000 / 100 / 1. Sämtliche Zeilen werden zusätzlich gegen den gemeinsamen deterministischen synthetischen Generator geprüft. Current entspricht der neuesten History; keine verwaisten oder doppelten Zuordnungen.

MySQL stellt nach SHOW-CREATE-Replay bei Textspalten das zuvor implizite CHARACTER SET utf8mb4 zusätzlich explizit dar. Nur diese redundante Angabe wird für den DDL-Vergleich normalisiert; vollständige Spaltenkollationen, Tabellenkollation, Engine, Constraints und Indizes werden separat verglichen. SHOW-INDEX-Kardinalitäten sind Optimizer-Schätzungen und keine Strukturmerkmale; sie werden nicht als Strukturabweichung gewertet. Die ursprünglichen DDL-Texte sind deshalb nicht bytegleich, ihre relevanten Strukturen jedoch gleich.

SHA-256 je Tabelle über alle Zeilen in Primärschlüsselreihenfolge, kanonische JSON-Zeilen mit erhaltenen Typen und Zeilenabschluss. Diese Kodierung unterscheidet sich bewusst vom früheren History-only-Pipe-Format; dessen Digest ist kein Vergleichswert für dieses Format.

| Tabelle | Zeilen | SHA-256 in Quelle und Restore |
| --- | ---: | --- |
| Entity | 100 | e0ce2448872620e86c6b202f515b66f4e8d9aa700e4d647130da80339fa92fda |
| Identity | 100 | 98d560df05ae20d29c1d09b85dc107099c894255f77e66bba4934e444f5c6b25 |
| History | 100.000 | a52f9793a1a442892364344cf0510ce33d6d902052b965438c74b245ab58a672 |
| Current | 100 | 7e43a74be62c535c7d5a9e62da03b192fe5470e6da1c37e495e4d8bb2e4b34b9 |
| Migration | 1 | 284aa24d5f791b818591e86ea3ba36f274b83857310062986a85244f3cc1ba82 |

Im Restore genau einmal je gefordertem Funktionsmuster ausgeführt: Current einzeln (1 Zeile), neueste History (1), schmales Zeitfenster (10), breites Zeitfenster (50), Identity-Lookup (1). Alle Ergebnisse exakt gegen gemeinsame Sollwerte geprüft. Keine Last-/Dauertests und keine Million Zeilen.

### Korrekturen und Nachweisgrenzen im Verlauf

- Das zuerst im In-App-Browser geöffnete Passwortformular war für den Nutzer nicht wie behauptet in Chrome sichtbar. Anschließend im vorhandenen Chrome-Tab geöffnet und das Fenster fokussiert.
- Eigener Fehler im temporären Formularschutz: Referrer-Policy no-referrer führte beim POST zu Origin null und zur korrekten Ablehnung durch die strikte Origin-Prüfung. Auf same-origin korrigiert; Origin-Prüfung nicht gelockert. Nutzer musste beide Passwörter erneut eingeben. Danach beide Testdatenbanken erfolgreich authentifiziert und leer bestätigt. Passwörter ausschließlich maskiert an den eigenen HTTPS-Testzugang übergeben; privat mit 0600 außerhalb öffentlicher Dokumentstämme gespeichert. HTTPS, Host/IP, POST, signierter kurzlebiger CSRF-Cookie und Einmalübernahme; keine Datenbankschreibaktion per GET. Fremdzugriff HTTP 403 tatsächlich geprüft.
- Erster Restore importierte fünf Tabellen, der nachfolgende Vergleich scheiterte an der beschriebenen redundanten Charset-Darstellung. Lesende Diagnose, gezielte Normalisierung und drei zusätzliche Regressionstests; anschließend ausschließlich eigene Restore-Tabellen entfernt, Ziel erneut leer nachgewiesen und dasselbe Backup erneut importiert. Quelle und Backup nicht neu aufgebaut. Erfolgreiche Restore-Dauer wird unmittelbar nach Import vor weiteren Vergleichen gespeichert.
- Native Auftragsanzeige mit Eingang 18.10.2026 09:40:39 Uhr sowie Describe/Plan vor Facharbeit im KI-Kontrollzentrum sichtbar bestätigt. Nach den notwendigen Nutzer-Eingabepausen lehnt der Sender weitere Schritte für die alte native Kennung mit „No open laboratory order for this exact native turn“ ab. Keine neue Kennung erfunden, kein Start/Stop nachgebildet. Deshalb keine lückenlose Statusübertragung oder Abschlussbewertung behauptet.

### Tests, Bereinigung und Veröffentlichung

- Providerseitig 17 PHP-Lints und bestehende 17 Basis-, 80 10.000er-, 264 100.000er-, 54 Optimierungs- und 48 Transaktionsprüfungen ohne DB-Verbindung bestanden. Neue Backup-Prüfungen zunächst 27, nach gezielter Korrektur **30**; drei geänderte PHP-Dateien erneut gelintet. Neue Python-Testintegration übernimmt Lint und Offline-Prüfungen in den unveränderten Validierungsworkflow.
- Nach Erfolg alle fünf eigenen Quell- und alle fünf eigenen Restore-Tabellen anhand des reservierten Manifests und ihrer Eigentumsmarker entfernt. Beide Datenbanken vor Entfernung der Zugangskonfiguration erneut mit **null Tabellen** geprüft.
- 17 Testquellen gegen GitHub-Blob-Hashes geprüft; Backup, private Berichte/Manifeste, Sperrdateien, beide Passwortdateien, Zugangskonfiguration, privater Testcode, temporärer Fehlercodebericht und öffentlicher FPM-Einstieg vollständig entfernt. Keine anderen Dateien oder fremden Datenbanken bereinigt. Kurzlebiger Zugangscookie nach erfolgreicher Übernahme abgelaufen; keine serverseitigen Sitzungdateien verwendet.
- Temporärer HTTPS-Einstieg danach **HTTP 404**. Neutrale HTTPS-Startseite **HTTP 200**, sichtbarer unveränderter Text und vollständiger Antwortinhalt gegen Git-Blob 333a115eb2d83a45d7ff0a6a27709826a1a4e94c bytegenau bestätigt.
- Ausführung ausschließlich providerseitig über den bestehenden verbundenen Browser und den ungespeicherten deaktivierten Plesk-Aufgabendialog; danach Abbrechen. Keine lokalen Backupdateien, kein Zugriff auf E:, keine Produktions-, fixlab-, Workflow- oder Deployment-Secret-Änderungen.
- Ein Abschluss-Commit mit [skip ci]. Derselbe Commit wird auf einem Prüfbranch mit dem bestehenden Workflow validiert, Deploy muss übersprungen sein; erst danach Übernahme nach main. Konkreter SHA und Prüflauf stehen im Abschlusskommentar zu Issue #5.

**Aussagegrenze:** Vollständige Sicherung und Wiederherstellung dieses isolierten synthetischen Fünf-Tabellen-Bestands ist nachgewiesen. Kein Backup einer vollständigen produktiven MOSA-Anwendung, kein Online-Backup unter konkurrierenden Schreibern, keine langfristige Aufbewahrungs-/Desaster-Recovery-, Schema- oder Produktivfreigabe. **Issue #5 bleibt offen.** Keine nächste Testphase gestartet.


## Phase 1H – abschließender Million-Zeilen-Skalierungstest

**18.10.2026, Europe/Berlin (MESZ, UTC+02:00). Fachlich erfolgreich für den begrenzten synthetischen Test.** Aufbauabschluss 10:43:20; CLI-Messbeginn 10:43:37; FPM-Messbeginn 10:44:46; abschließender Leerstands-/Dateibereinigungsnachweis 10:46:26.

### Vorprüfung, Profil und Grenzen

Ausschließlich die bestehende Quell-Testdatenbank und ihr zugeordneter Benutzer am festen lokalen Endpunkt 127.0.0.1:3307. Authentifizierung und **null Tabellen** vor Aufbau bestätigt. Restore-Testdatenbank nicht verbunden oder verändert, kein erneuter Backup/Restore, keine neue Datenbank und kein Passwortreset.

Providerkonto: oneHome 7,05 GB von 150 GB belegt; Plesk 7.856,6 MB von 150 GB (abweichende Anzeigezeitpunkte/Einheiten). Aus 10,69 MiB bei 100.000 Zeilen zunächst ungefähr 107 MiB abgeleitet; deutlicher Spielraum gegenüber der sichtbaren Abonnementgrenze. Providerseitig im privaten Verzeichnis gemeldeter freier Dateisystemraum 1.486.569.500.672 Bytes ist **keine persönliche DB-Quota**. MySQL 8.0.26-16, Port 3307, max_allowed_packet 67.108.864 Bytes, max_user_connections 30, InnoDB-Seite 16.384 Bytes bestätigt. Keine separate per-DB-Bytequota aus diesen Nachweisen ableitbar; keine erkennbare Provider-/Speichergrenze. Nur eine Testverbindung pro sequenziellem Lauf, keine Rechte-/globalen Einstellungen geändert.

Gemeinsamer Phase-1B-Verbindungskern und Phase-1C-Profilgenerator, Batch-Lader, Messungen, Korrektheit, Manifest und Bereinigung wiederverwendet. Phase-1E-Indexinspektion und EXPLAIN-ANALYZE-Parser ebenfalls wiederverwendet, **keine Optimierungsstufen ausgeführt**. Neues festes history1000000_v1 nur mit ausdrücklich serverseitig aktiviertem MOSA2_HISTORY_MILLION; alte Einstiege weisen es weiterhin ab. Alte Profiltests unverändert. Keine freie HTTP-Mengen-/Profilwahl, kein Anhängen oder Wiederaufbau.

Genau 100 Entity, 100 Identity, **1.000.000 History (10.000 je Entity)**, 100 Current und 1 Migration. Fester Seed mosa2-synthetic-v1, UTC-Basis 2020-01-01T00:00:00Z; gleiche Zeitstempel deterministisch nach ID. Einmaliger CLI-Aufbau, 2.000 History-Batches zu höchstens 500 plus vier Nebenbatches, eine Datentransaktion. Allgemeiner ASC-Index history_time(entity_id,observed_at ASC,id ASC), kein Zusatzindex. Query-Statistik weiterhin höchstens 30 Werte; eigene Batchstatistik maximal 2.000. Bestehende Laufgrenzen bleiben 90 s Aufbau, 30 s Messung/Bereinigung, PHP 120 s und SELECT-/Lock-Grenzen 3 s.

### Korrektheit

CLI PHP 8.4.12 und FPM PHP 8.4.26, beide PDO-MySQL, jeweils alle 16 gemeinsamen Prüfmerkmale erfolgreich: exakte Mengen, keine verwaisten Daten, eindeutige History-/Identity-Zuordnung, alle 100 Current-Zeilen exakt neueste History, sämtliche sieben Abfrageergebnisse, leere/Zeitgrenzenfälle und ID-Gleichstandsauflösung. Current-Upserts erzeugen keine Duplikate oder Rückschritte; Prüfschreibungen zurückgerollt. History nach Aufbau ausschließlich gelesen.

Vollständiger SHA-256 vor/nach Schreibprüfungen unter **beiden SAPIs identisch** und passend zur deterministischen Erwartung:

`3a80ac0ad6741320a1477cf250c3268a5a1f41d12298b27f033c1cd4030057b9`

Kanonische Pipe-Zeilen in ID-Reihenfolge, wie Phase 1D. Zusätzlich unabhängig in JavaScript aus festen Formeln/UTC-Zeiten berechnet und als feste Offline-Regression übernommen. Keine Passwort-/Produktivdaten in Prüfsummen oder Berichten.

### Laufzeiten und Pläne

Je sieben Abfragetypen und SAPI **erste Ausführung separat plus zehn Folgemessungen**, Median/p95 (Nearest-Rank, bei zehn Werten Maximum). Alle Ergebnisse jeder Ausführung vollständig gegen Sollwerte geprüft. Zeit umfasst PDO execute plus begrenzten Abruf, nicht Verbindung/Prepare. Keine Cache-Leerung; erster Wert ist kein nachgewiesener Kaltstart. Insgesamt 154 reguläre Query-Messungen, zusätzlich begrenzte Korrektheits-/Integritätsabfragen, vollständige Prüfsummenscans und je ein EXPLAIN ANALYZE.

| Muster | CLI erste / Median / p95 ms | FPM erste / Median / p95 ms | EXPLAIN beider SAPIs: Zugriff / Index / geschätzte Zeilen |
| --- | ---: | ---: | --- |
| Current einzeln | 0,3219 / 0,1075 / 0,1683 | 0,2128 / 0,1150 / 0,1444 | const / PRIMARY / 1 |
| Current Batch | 0,1718 / 0,1271 / 0,1441 | 0,1549 / 0,1216 / 0,1358 | range / PRIMARY / 6 |
| Neueste History | 0,5203 / 0,2908 / 1,6627 | 0,4217 / 0,2855 / 0,3605 | ref / history_time / 10.000; rückwärts |
| Schmales Fenster | 0,3043 / 0,2166 / 1,2897 | 0,2587 / 0,2039 / 0,2335 | range / history_time / 10; Indexbedingung |
| Chart LIMIT 25 | 0,3621 / 0,3331 / 0,3780 | 0,3681 / 0,3233 / 0,3391 | ref / history_time / 10.000; rückwärts |
| Identity | 0,1790 / 0,1238 / 0,2640 | 0,2117 / 0,1282 / 0,1521 | const / identity_lookup + PRIMARY / je 1 |
| Breites Fenster LIMIT 50 | 0,4491 / 0,3845 / 0,4361 | 0,4491 / 0,3558 / 0,3926 | ref / history_time / 10.000; Indexbedingung |

Alle ersten Werte, Median und p95 unter den Zielen **Current <20 ms**, **begrenzte History <100 ms**. Kein Filesort oder ungeeigneter ungebundener Full Scan im normalen Leseweg. Vollständige Integritäts-/Prüfsummenscans sind gesonderte Prüfungen, keine normalen Seitenabfragen.

Breites Fenster: Entity gebunden wie bisher, UTC 2020-01-01 00:00 inklusive bis 2020-01-04 10:30 exklusive; **9.900 passende History-Zeilen**, gegenüber 900 in Phase 1D/E. ORDER BY observed_at,id, LIMIT 50, keine entityspezifische Sonderlösung, kein FORCE INDEX und keine Optimizer-Umschaltung.

EXPLAIN ANALYZE unterstützt. Beide SAPIs: selektiver Index-Lookup auf history_time mit Zeitbedingung, tatsächlich **50 vom Indexoperator an LIMIT ausgegebene Zeilen, ein Durchlauf**; Schätzung 10.000 am Lookup und 50 am LIMIT. Instrumentierter LIMIT-Abschluss CLI 0,145 ms, FPM 0,128 ms; Lookup-Ende 0,141 / 0,123 ms. Das sind Operator-Ausgabezeilen, **kein separater Nachweis interner InnoDB-Zeilenprüfungen oder physischer Seitenzugriffe**.

Vergleich zur erfolgreichen allgemeinen ASC-Stufe 1E bei 100.000 Zeilen: Current-Median CLI/FPM 0,0986/0,0965 → 0,1075/0,1150 ms; breite History 0,3575/0,3814 → 0,3845/0,3558 ms, p95 0,4157/0,4315 → 0,4361/0,3926 ms. Kein unerwarteter Planwechsel: ref/history_time bleibt, Entity-Kardinalität geschätzt 1.000 → 10.000; schmales range-Fenster weiter zehn. Höchster History-p95 jetzt 1,6627 ms (CLI Latest), weiterhin weit unter 100 ms. Kleine zeitlich getrennte Hosting-Stichproben belegen keine allgemeine Beschleunigung oder Verschlechterung. Die ursprüngliche langsame DESC-Stufe 1D ist nicht der maßgebliche ASC-Vergleich.

### Aufbau und Speicher

Gesamter Aufruf für Verbindung, Vorprüfung, DDL, Generator, Inserts, Commit und Manifest: **20.668,1901 ms**. Für Phase 1D ist keine methodisch identische Gesamtaufbauzeit dokumentiert; daher kein erfundener Gesamtzeitfaktor.

| Schreiben | Batches | INSERT-Summe ms | Median ms | p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Entity | 1 | 0,9734 | 0,9734 | 0,9734 |
| Identity | 1 | 1,6060 | 1,6060 | 1,6060 |
| History | 2.000 | 11.312,4964 | 5,1527 | 8,6196 |
| Current | 1 | 1,9508 | 1,9508 | 1,9508 |
| Migration | 1 | 0,1786 | 0,1786 | 0,1786 |

History-INSERT-Summe gegenüber Phase 1D 1.762,3435 ms etwa **6,42-fach bei zehnfacher Menge**. Keine allgemeine Durchsatzprognose; getrennte Läufe, keine Parallel-/Dauerlast.

CLI- und spätere FPM-Metadaten stimmen überein; ausdrücklich InnoDB-Seitenbelegung, keine exakte Nutzdaten-/Backupgröße:

| Tabelle | Daten Bytes | Sekundärindizes Bytes | Geschätzte Zeilen |
| --- | ---: | ---: | ---: |
| Entity | 16.384 | 16.384 | 100 |
| Identity | 16.384 | 32.768 | 100 |
| History | 41.484.288 | 33.636.352 | 997.926 |
| Current | 16.384 | 16.384 | 100 |
| Migration | 16.384 | 16.384 | 1 |
| Gesamt | 41.549.824 | 33.718.272 | — |

Gesamt **75.268.096 Bytes = 71,78125 MiB** (Daten 39,625 MiB, Sekundärindizes 32,15625 MiB), etwa **6,72-fach** gegenüber 10,6875 MiB bei 100.000. Keine unerwartete Index-/Speicherexplosion; Seitenfüllung und Metadaten sind nicht linear garantiert. History-COUNT ist exakt 1.000.000; 997.926 bleibt ausdrücklich eine Optimizer-Schätzung. Nur bereits vorhandene sessionlokale information_schema_stats_expiry=0-Abfrage, keine Cache-Manipulation, ANALYZE TABLE oder globale Serveränderung.

### Tests, Bereinigung und Veröffentlichung

- 20 PHP-Testquellen unter PHP 8.4.12 gelintet; bestehende 17 Basis-, 80 10.000er-, 264 100.000er-, 54 Optimierungs-, 48 Transaktions- und 30 Backup-Offlineprüfungen erfolgreich, ohne Datenbankzugriff. Backup-Livetest nicht wiederholt.
- Million-Test zunächst 2.041 Prüfungen; nach zusätzlicher unabhängiger fester Digest-Referenz erneut gelintet und **2.042** Prüfungen erfolgreich. Grenzen 1.000.000/2.000, Generator/UTC/IDs, Streaming, Query-Semantik, Manifest-/Eigentumsschutz und separate Messbudgets abgedeckt. Neue Python-CI-Integration, vorhandene Tests unverändert.
- Geschütztes Ein-Feld-HTTPS-Formular in bestehendem Chrome sichtbar bestätigt, bestehendes Quellpasswort nur durch Nutzer eingegeben. HTTPS/Host/IP/Origin/POST, signierter kurzlebiger CSRF-Cookie, 0700-Verzeichnisse und 0600-Privatdateien. Fremdzugriff praktisch HTTP 403. Keine Zugangsdaten ausgegeben oder in GitHub übertragen.
- Beim Übergang von der erfolgreichen Passwort-POST-Seite zur Messung wurde ein Reload mit abgelaufenem CSRF korrekt abgewiesen. Danach frischer GET im bestehenden Chrome und genau eine autorisierte FPM-Messung; keine erneute Passworteingabe und kein doppelter Test.
- Ausschließlich fünf manifestgebundene eigene Tabellen nach Eigentumsprüfung entfernt; **null Tabellen** anschließend erneut mit eigener authentifizierter Verbindung nachgewiesen. Quell-Datenbank bleibt bestehen; Restore-Datenbank unverändert.
- Alle 20 Testquellen vor Entfernung gegen GitHub-Blob-Hashes geprüft. Eigene private Passwort-/Konfigurationsdateien, Code, Manifest, Mess-/Offlineberichte, Schlösser und temporärer HTTPS-Einstieg vollständig entfernt. CSRF-Cookie nach FPM abgelaufen, keine serverseitigen Sitzungsdateien angelegt.
- Einstieg HTTP 404; neutrale Startseite HTTP 200, in Chrome sichtbar und vollständig bytegleich zu Git-Blob 333a115eb2d83a45d7ff0a6a27709826a1a4e94c. Ungespeicherten deaktivierten Plesk-Dialog abgebrochen; weiterhin **neun** Aufgaben, keine neue Cron-Aufgabe.
- Keine Produktions-, Restore-, fixlab-, AGENTS-, Workflow- oder Deployment-Secret-Änderungen. Kein Zugriff auf E:. Providerarbeit ausschließlich in der bestehenden verbundenen Chrome-Sitzung.
- Genau ein Abschluss-Commit mit [skip ci]; identischer SHA zuerst über vorhandenen Validierungsworkflow auf Prüfbranch, Deployment übersprungen, danach main. Konkreter Lauf/SHA und Validierungsergebnis im Abschlusskommentar von Issue #5.

### KI-Kontrollzentrum separat

Der reguläre Recorder wurde für den neuen Auftrag aufgerufen. Nachrichteneingang 18.10.2026 **10:29:33,001 MESZ** bestätigt, aber im strukturierten Describe-/Plan-Statusweg blieb der geschlossene frühere Backup-Auftrag. Deshalb kein belegter neuer strukturierter Start, kein bestätigtes Describe/Plan oder laufender Million-Auftrag im Kontrollzentrum. Gemäß ausdrücklich aktualisiertem Nutzerauftrag ist diese Erfassungslücke kein fachliches Abbruchkriterium. Keine IDs, Start-/Stop-Ereignisse, Statushistorie oder Abschlussbewertung erfunden; kein Eingriff in fixlab.

**Einordnung:** Die freigegebene Million-Stufe erfüllt Korrektheits-, begrenzte Query- und Größenkriterien. Kein allgemeiner Last-/Parallelitäts-/Dauer-, Produktiv-, endgültiger Schema- oder Migrationsnachweis. **Issue #5 bleibt offen.** Keine weitere Skalierungs-, Optimierungs-, Schema- oder Produktionsphase begonnen.


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

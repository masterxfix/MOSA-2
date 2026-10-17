# MOSA 2 – Phase 1: isolierte Datenbank-Testplattform

**Status:** 100.000er-Test durchgeführt und bereinigt · Korrektheit bestätigt, breites Zeitfenster über Zielwert · Issue #5 und weitere Freigaben offen
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

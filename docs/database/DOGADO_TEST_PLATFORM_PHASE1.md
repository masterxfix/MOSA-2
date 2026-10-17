# MOSA 2 – Phase 1: isolierte Datenbank-Testplattform

**Status:** Phase 1A: Plattform, HTTPS und neutrale Startseite live bestätigt · Phase 1B bleibt offen
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

# Dogado – Infrastruktur, Pfade, Zugänge und Deployment

**Dokumentationsstand:** 20.10.2026  
**Repository-Grundlage:** `c190deff9f4fe514ac4519e2fd950b3876264cbb`  
**Geltung:** Zentrale Übersicht für MOSA 2; MOSA/fixlab wird nur als vorhandene Referenz beschrieben.

Hier sind die bisher verteilten Dogado-Informationen zusammengeführt. Die ursprünglichen Dokumente und Nachweise bleiben erhalten und sind direkt verlinkt. Historische Kontobefunde, aktuelle Codevorgaben und noch offene Live-Nachweise werden getrennt angegeben. Diese Zusammenführung verändert keine Hosting-Einstellungen, Zugänge, Dateien auf Dogado oder Datenbanken.

## Schnellzugriff

- [Domains, Serverpfade und WinSCP-Zuordnung](#1-domains-serverpfade-und-winscp-zuordnung)
- [Dateien der Testseite](#2-dateien-der-testseite)
- [Dateiübertragung und Deployment](#3-dateiübertragung-und-deployment)
- [Hosting, PHP und Datenbank](#4-hosting-php-und-datenbank)
- [Zugänge, Passwörter und Schutz](#5-zugänge-passwörter-und-schutz)
- [Scheduler und Sicherungen](#6-scheduler-und-sicherungen)
- [Offene Zuordnungen und Nachweise](#7-offene-zuordnungen-und-nachweise)
- [Quellen und Pflege](#8-quellen-und-pflege)

## 1. Domains, Serverpfade und WinSCP-Zuordnung

**Webadresse, Plesk-Dokumentstamm, physischer Serverpfad und sichtbarer FTP-/SFTP-Pfad sind unterschiedliche Angaben.** Ein in WinSCP angezeigtes `/` darf nicht ohne Kenntnis des verwendeten Kontos mit dem gesamten Server-Dateibaum gleichgesetzt werden.

| Bereich | Webadresse / Zweck | Dokumentierte Verzeichnisangabe | Nachweisgrenze |
| --- | --- | --- | --- |
| Bestehendes MOSA | `https://scharwerk.de/dashboard_neu/` | Beim dokumentierten MOSA-Dateizugang: CloudPit-Pfad `httpdocs/scharwerk.de/dashboard_neu`; FTP-Basis `/httpdocs/scharwerk.de`; sichtbares Uploadziel `/dashboard_neu` | Gilt für den damaligen dedizierten MOSA-Dateizugang, nicht automatisch für jedes WinSCP-Profil. |
| MOSA-2-Testseite | `https://mosa2-test.scharwerk.de/` | Eigener Dokumentstamm `mosa2-test.<Testdomain>` außerhalb der bisherigen MOSA-Verzeichnisse; konkret benannte Testdomain: `mosa2-test.scharwerk.de` | Vollständiger physischer Serverpfad und Abbildung auf den aktuell verwendeten Dateizugang sind in den hier zusammengeführten Nachweisen nicht eindeutig belegt. |
| Bisheriges MOSA-2-Workflowziel | `https://mosa.scharwerk.de/` | Plesk-Dokumentstamm laut Deploymentdokument: `mosa.scharwerk.de`; im Uploader erlaubter physischer Zielpfad: `/var/www/vhosts/web213.server10.configcenter.info/mosa.scharwerk.de` | Code-/Dokumentationsvorgabe für diesen anderen Host; kein Beleg für einen erfolgreichen authentifizierten SFTP-Zugriff und kein Pfadnachweis für die Testseite. |
| Weitere MOSA-2-Adresse | `mosa2.scharwerk.de` | In den Testaufträgen ausdrücklich von Änderungen ausgenommen | Nicht mit `mosa2-test.scharwerk.de` oder dem Workflowziel gleichsetzen. |

Quellen: [Testplattform, Phase 1A](../database/DOGADO_TEST_PLATFORM_PHASE1.md), [bisherige Deploymentdokumentation](../DEPLOYMENT.md), [Issue #8](https://github.com/masterxfix/MOSA-2/issues/8), [MOSA-Dateizugang](https://github.com/masterxfix/fixlab/blob/main/docs/17_LOKALE_ARBEITSWEISE.md).

### Beobachtung aus dem WinSCP-Abgleich am 20.10.2026

Die vom Nutzer gezeigte Verbindung zeigte zunächst `/scharwerk.de/` und danach `/` mit mehreren bestehenden Website-Verzeichnissen. `mosa2-test.scharwerk.de` war in dieser Ansicht nicht sichtbar. Das ist eine Screenshot-Beobachtung aus dem Projektgespräch, keine eigenständige Serverinventur.

Daraus folgt weder, dass die Dateien fehlen, noch welcher Benutzer beziehungsweise welches Basisverzeichnis tatsächlich verwendet wurde. Ein außerhalb des sichtbaren Bereichs liegender Testordner ist eine mögliche Erklärung, aber noch kein bestätigter Kontobefund. Insbesondere ist der sichtbare Ordner `test.scharwerk.de` nicht die benannte MOSA-2-Testdomain.

**Keine Ersatzordner anlegen und keine Dateien verschieben, nur weil der Testordner in einer Verbindung nicht sichtbar ist.** Für die eindeutige Zuordnung fehlen noch:

| Benötigte Angabe | Stand |
| --- | --- |
| Vollständiger physischer Dokumentstamm der Testseite | Aus dem bereits erfolgten Deployment oder den Hosting-Einstellungen konkret nachzutragen; nicht aus dem Pfad von `mosa.scharwerk.de` ableiten. |
| Verwendetes Dateiübertragungsprofil und Protokoll | Für die aktuelle WinSCP-Verbindung noch nicht zugeordnet; keine Passwörter dokumentieren. |
| Basisverzeichnis dieses Kontos | Nicht durch die sichtbare Bezeichnung `/` allein bestimmt. |
| Testziel innerhalb genau dieses FTP-/SFTP-Namensraums | Noch nicht nachgewiesen. |

## 2. Dateien der Testseite

Die folgende Struktur ist **relativ zum tatsächlichen Dokumentstamm der Testseite**. Sie ist keine Aussage darüber, an welcher Stelle WinSCP diesen Dokumentstamm anzeigt.

```text
<Test-Dokumentstamm>/
├── index.html
├── assets/
│   ├── css/main.css
│   └── js/
│       ├── market.js
│       └── page_load_time.js
└── api/
    ├── market.php
    └── read_model.php
```

| Datei | Aufgabe |
| --- | --- |
| `index.html` | Projektübersicht und zusätzlicher Marktdatenbereich; keine fest eingetragenen Kurse als Ersatz für DB-Daten. |
| `assets/css/main.css` | Gemeinsame Gestaltung und responsive Darstellung. |
| `assets/js/market.js` | Lädt `api/market.php` nach und stellt Kurse, Einheiten, Zeiten und Status dar. |
| `assets/js/page_load_time.js` | Vorhandene Anzeige der Seitenladezeit. |
| `api/market.php` | GET-Endpunkt, geschützte Konfiguration und Datenbankverbindung. |
| `api/read_model.php` | Begrenzte, ausschließlich lesende Current-Abfragen. |

Der Endpunkt referenziert die Konfiguration über `dirname(__DIR__, 2) . '/mosa2-market-read-private/access.php'`. Damit liegt sie nach dem vorgesehenen Layout außerhalb des Test-Dokumentstamms. Daraus wird hier kein ungeprüfter absoluter Serverpfad konstruiert. Der Code prüft unter anderem Dateimodus und Symlink-Eigenschaft; ob ein Ablageort außerhalb **aller** Webroots liegt, gehört zum Einrichtungsnachweis.

Collector-, Migrations- und Testquellen unter `scripts/` beziehungsweise `docs/database/` sind keine regulären öffentlichen Webdateien. Private Laufordner, Sicherungen und Zugangskonfigurationen gehören nicht in GitHub oder ein öffentliches Uploadpaket.

Quellen: [Endpunkt](../../api/market.php), [Leseweg](../../api/read_model.php), [Anzeigevertrag](../database/CURRENT_DISPLAY.md), [Webdateien im Uploader](../../scripts/deploy_sftp.py).

## 3. Dateiübertragung und Deployment

### Bewährter MOSA-Weg: gespeichertes WinSCP-Profil und FTPS

Die MOSA-Dokumentation beschreibt `scripts/deploy_dogado.ps1` und den zugehörigen VS-Code-Task als vorhandene Deployment-Automatik. Sie verwenden ein lokal gespeichertes WinSCP-Profil über `FIXLAB_WINSCP_SITE`; die dokumentierte Sitzung heißt `MOSA_Dogado_VSCode`. Zugangsdaten werden nicht ins Repository übernommen oder in eine Sandbox exportiert.

Für den damaligen Zugang sind `server10.configcenter.info`, **Port 21 mit explizitem TLS (FTPS)** sowie die Zuordnung `/httpdocs/scharwerk.de` → sichtbares `/` dokumentiert. Das MOSA-Ziel ist damit `/dashboard_neu`. Dies ist **nicht SFTP**.

Das vorhandene Gate lässt nur bestimmte Einzeldateien und Pfade zu; insbesondere ist es keine allgemeine Freigabe für MOSA-2-HTML, CSS oder einen anderen Webroot. Ein normales gespeichertes Benutzerprofil kann in einer Codex-Sandbox fehlen, ohne dass das Profil im normalen Benutzerkontext fehlt. Die MOSA-Dokumentation sieht für eine direkte Codex-Ausführung eine gezielte Berechtigung für den konkreten bestehenden Deployment-Task vor, keinen allgemeinen Vollzugriff.

**Offen:** Erreicht ein bereits vorhandener Dateizugang den MOSA-2-Testordner? Das ist vor einer Wiederverwendung anhand der tatsächlichen Pfadzuordnung festzustellen. Diese Dokumentation legt keinen neuen Benutzer an und erweitert kein bestehendes Gate.

Quelle: [MOSA – lokale Arbeitsweise und Deployment](https://github.com/masterxfix/fixlab/blob/main/docs/17_LOKALE_ARBEITSWEISE.md).

### Vorhandener MOSA-2-Weg: SFTP-Code, noch auf anderem Ziel

[`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) und [`scripts/deploy_sftp.py`](../../scripts/deploy_sftp.py) beschreiben einen SFTP-Upload. Der Workflow wird durch einen Push auf `main` beziehungsweise manuell gestartet; sein Deployjob ist auf `main` und das Repository begrenzt. Sein Ziel ist **`mosa.scharwerk.de`, nicht die Testseite**.

Zugelassene Zielangaben im Code sind ausschließlich `mosa.scharwerk.de`, `/mosa.scharwerk.de` und `/var/www/vhosts/web213.server10.configcenter.info/mosa.scharwerk.de`. Der aufgelöste Zielpfad wird erneut geprüft. Ein abweichender Testpfad wird dadurch nicht automatisch unterstützt.

Benötigte GitHub-Secret-Namen, ausdrücklich ohne Werte:

```text
MOSA_DEPLOY_HOST
MOSA_DEPLOY_PORT
MOSA_DEPLOY_USER
MOSA_DEPLOY_PASSWORD
MOSA_DEPLOY_PATH
MOSA_DEPLOY_HOST_KEY_SHA256
```

Die ursprüngliche Deploymentdokumentation meldet für den 16.10.2026 noch keine hinterlegten Secrets und keinen authentifizierten SFTP-Test. Das ist ein historischer Stand, keine neue Prüfung der aktuellen Einrichtung. Sie nennt laut damaliger Anbieterreferenz SFTP auf Port 22 mit dem primären FTP-Benutzer; eine zusätzliche FTP-Anmeldung wird nicht automatisch als SFTP-tauglich behandelt.

Der Uploader ermittelt alle versionierten Webdateien nach seinen Ausschlüssen. Er erstellt fehlende Unterverzeichnisse, schreibt temporäre Uploaddateien, liest deren Inhalt zurück, prüft SHA-256 und ersetzt die endgültige Datei per `posix_rename`. Es gibt keine Remote-Löschung. Die Atomarität gilt pro Datei, nicht für das Gesamtpaket; ein Fehler kann einen teilweise aktualisierten Stand oder temporäre Dateien hinterlassen. Der Code ist kein Nachweis einer vorhandenen Rückfallsicherung jeder alten Zieldatei.

**Nicht als Testsite-Upload starten:** Der bestehende Hauptbranch-Workflow ist nicht der richtige Weg für die laufenden Testseitenänderungen. Bei reinen Dokumentationscommits wird `[skip ci]` verwendet; diese Zusammenführung löst keinen manuellen Workflow aus.

Quelle: [bisherige Deploymentdokumentation mit Detailvertrag](../DEPLOYMENT.md).

### Tatsächlich berichteter Zwischenweg: Plesk, einmalige PHP-Ausführung

Für die letzten Textänderungen meldete Codex im Projektgespräch eine direkte Serverbearbeitung über die Plesk-Maske „Aufgabe planen“: Dateistand prüfen, betroffene Dateien sichern, Inhalte ersetzen, anschließend die Webseite prüfen. Dafür wurde ein PHP-CLI-Befehl mit `/opt/plesk/php/8.4/bin/php -r ...` über „Jetzt ausführen“ gestartet. Laut Rückmeldung wurde keine Aufgabe gespeichert oder aktiviert; danach wurde die Maske mit „Abbrechen“ verlassen.

Dieser Bericht beschreibt einen einmaligen Ausführungsweg, keinen regelmäßigen Job. Die konkrete Rückmeldung ersetzt weder ein vollständiges Serverprotokoll noch einen Nachweis des Dateiübertragungswegs. Sie erklärt die dabei entstandene Abhängigkeit von einer Hosting-Anmeldung. Auch die historischen Plattformtests dokumentieren Plesks einmalige Ausführung ohne gespeicherten Cronjob.

**Browserwahl und Upload bleiben getrennt:** [AGENTS.md](../../AGENTS.md) legt Google Chrome als Standardbrowser fest, nicht Plesk als allgemeine Deploymentpflicht. Der angestrebte normale Ablauf ist Repository → eindeutig zugeordneter Datei-Upload zur Testseite → Inhaltsabgleich → kurze Sichtprüfung. Ob ein vorhandener Zugang dafür bereits ausreicht, bleibt die oben benannte offene Zuordnung.

## 4. Hosting, PHP und Datenbank

Die folgenden Laufzeit- und Kontowerte sind **dokumentierte Messstände vom 17.10.2026**, keine bei dieser Zusammenführung erneut ausgeführte Liveprüfung.

| Bereich | Dokumentierter Befund |
| --- | --- |
| Hosting | WEB M 3.0; 150 GB Speicher, 50 Datenbanken; damals 4 von 50 FTP-Accounts in oneHome sichtbar. |
| Verwaltung | Dogado oneHome, Plesk/CloudPit-Expertenpanel und phpMyAdmin. |
| Testplattform | Eigene MOSA-2-Testdatenbank und eigener Dokumentstamm im bestehenden Hosting-Abonnement; kein eigener Server oder Betriebssystembenutzer. |
| Testdatenbank | MySQL `8.0.26-16`, InnoDB; Datenbank und zugehöriger Testbenutzer mit Suffix `mosa2_test`. Vollständige Zugangsdaten werden hier nicht wiederholt. |
| Lokaler Test-DB-Endpunkt | `127.0.0.1:3307`; Zugriff bei Einrichtung auf lokal begrenzt. |
| Bestehender älterer DB-Bestand | MySQL 5.7 auf Port 3306; nicht mit der isolierten Testdatenbank verwechseln. |
| Web-PHP der Testseite | PHP `8.4.26`, FPM/FastCGI; `pdo_mysql` vorhanden. |
| PHP-CLI | PHP `8.4.12`; dokumentierter Aufrufpfad `/opt/plesk/php/8.4/bin/php`. |
| Web-PHP-Limits | `memory_limit` 256 MB; `max_execution_time` und `max_input_time` 900 s; Upload- und POST-Limit 64 MB. |
| Weitere Module | Unter anderem curl, intl, mbstring, mysqli/mysqlnd, OpenSSL, PDO, session, sodium, zip; OPcache aktiv. |
| PHP 8.5 | Im Konto als Option vorhanden, nicht automatisch gewählter MOSA-2-Standard. |
| Zeitzone der Aufgabenmaske | Europe/Berlin; am Prüfdatum UTC+02:00. Fachliche DB-Zeiten werden explizit als UTC behandelt. |

Das anfänglich irreführende phpMyAdmin-Serverlabel „MySQL 5.7“ wurde durch die tatsächliche SQL-Ausgabe `VERSION()` für den neuen Port korrigiert. Maßgeblich ist der konkrete Verbindungsnachweis, nicht das UI-Label. Die ursprünglichen DB-Voreinstellungen `utf8mb3`, `NO_ENGINE_SUBSTITUTION` und Zeitzone `SYSTEM` sind historische Ausgangswerte, keine empfohlenen Sollwerte des heutigen Schemas.

Das versionierte Modell verwendet unter anderem InnoDB, utf8mb4, exakte DECIMAL-Werte und ausdrücklich behandelte UTC-Zeitpunkte. Die Migrationen 1–3 besitzen historische Live-Nachweise; Migration 4 und der Current-Anzeigepfad sind im Repository implementiert. Im Projektgespräch wurde ein erfolgreicher Live-Apply von Migration 4 gemeldet. Der bloße SQL-Dateibestand oder eine sichtbare Kurstabelle ersetzen aber nicht den vollständigen Abschlussnachweis von Issue #41.

Der Webpfad liest vorbereitete Current-Daten und ruft keinen Provider auf. Die damalige Testansicht umfasst zwei Assets; der Lesevertrag ist auf maximal zehn begrenzt. Das ist keine Freigabe für Scheduler, größere Batches oder Produktion.

Quellen: [Plattformqualifikation](../database/DOGADO_PLATFORM_QUALIFICATION.md), [Testplattform und Laufzeitprüfungen](../database/DOGADO_TEST_PLATFORM_PHASE1.md), [Migrationen](../database/migrations/README.md), [Current-Anzeige](../database/CURRENT_DISPLAY.md), [Issue #41](https://github.com/masterxfix/MOSA-2/issues/41).

## 5. Zugänge, Passwörter und Schutz

### Unterschiedliche Zugangszwecke

| Zugang | Aufgabe | Nicht damit gleichsetzen |
| --- | --- | --- |
| oneHome/Plesk-Verwaltung | Hosting-Konfiguration und administrativer Zugriff | Keine automatisch wiederverwendbare PHP-Datenbankanmeldung. |
| FTP-/FTPS-/SFTP-Zugang | Dateien übertragen, innerhalb seines tatsächlichen Verzeichnisbereichs | Weder DB-Passwort noch zwingend dieselbe Sitzung wie Plesk. |
| Schreibender Test-DB-Benutzer | Freigegebene Tests, Migrationen und Datenübernahmen | Kein Benutzer, der für jeden Teiltest neu angelegt werden muss. |
| Nur-Lese-DB-Zugang | Gespeicherte Daten für die Oberfläche lesen | Löst allein nicht die Isolation der Passwortablage. |
| Web-Zugriffsschutz | Geschützte Testseite vor unauthentifizierten Aufrufen abschirmen | Eigenständig gegenüber Datei- und DB-Zugang. |

Der ursprüngliche Testbenutzer wurde ausschließlich der Testdatenbank zugeordnet und mit „Lesen und Schreiben“ eingerichtet. CREATE, ALTER, INDEX, INSERT, SELECT, UPDATE, DELETE und DROP wurden in Phase 1B praktisch geprüft. Der neuere Reader-Vertrag sieht separat geprüfte SELECT-/SHOW-VIEW-Rechte auf genau der Testdatenbank vor.

### Gemeinsames Systemkonto und dauerhafte Ablage

[Issue #12, Entscheidung vom 19.10.2026](https://github.com/masterxfix/MOSA-2/issues/12#issuecomment-6261006214) hielt fest: Testseite und andere Websites laufen unter demselben Systemkonto `web213`; `0700/0600` trennt solche Prozesse nicht voneinander. Eine exklusiv isolierte native Secret-Verwaltung war nicht nachgewiesen. Eine dauerhafte Test-DB-Anmeldung wurde deshalb damals nicht eingerichtet; kurzlebige Schreibanmeldungen blieben der vorgesehene Weg für seltene Schemaarbeiten.

Der spätere [Current-/Reader-Vertrag](../database/CURRENT_DISPLAY.md) beschreibt eine gesondert freizugebende permanente Nur-Lese-Konfiguration: privates Verzeichnis `0700`, Datei `0600`, außerhalb der Webroots, keine Secrets in GitHub oder HTTP-Antworten. Der aktuelle Endpunkt erwartet weiterhin das Feld `password`. Diese Implementierung ist **kein Nachweis einer inzwischen getrennten Betriebssystemidentität**. Ein dauerhaft eingerichteter Reader und die tatsächliche Freigabe beziehungsweise verbleibende gemeinsame Laufzeitgrenze sind getrennt zu dokumentieren.

### Nutzeranforderung zu Passwörtern

Für Issue #41 wurde verlangt: keine fortlaufenden Passwortaufforderungen; vorhandene geeignete Zugänge im freigegebenen Gesamtlauf verwenden; keine neuen Konten oder Formulare je Teilprüfung. Später wurde die Entfernung der Passwortauthentifizierung ausschließlich der Test-DB-Anwendungskonten nach funktionierender Anzeige verlangt, soweit der Hoster dies unterstützt. Sie betrifft nicht Produktion, Plesk-Verwaltung oder den Webschutz.

**Stand dieser Zusammenführung: Eine tatsächliche Passwortentfernung ist nicht bestätigt.** Der Reader-Code mit einem Passwort-Konfigurationsfeld beweist weder dessen aktuellen Inhalt noch eine erfolgreiche Umstellung. Keine Passwortwerte auslesen oder veröffentlichen, um diese Dokumentation zu vervollständigen. Eine technische Hostergrenze ist konkret zu benennen; bloß die Konfigurationsdatei zu löschen würde keinen funktionierenden passwortlosen Zugriff herstellen.

Quellen: [Ablaufklarstellung in #41](https://github.com/masterxfix/MOSA-2/issues/41#issuecomment-6294287539), [Nutzerentscheidung zur Homepage und Passwortentfernung](https://github.com/masterxfix/MOSA-2/issues/41#issuecomment-6294795958), [Reader-Endpunkt](../../api/market.php).

### Schutz der Testseite

[Issue #9](https://github.com/masterxfix/MOSA-2/issues/9) beschreibt den Schutz des gesamten Test-Dokumentstamms einschließlich Assets bei weiterhin aktivem HTTPS. Der Abschlussbericht von [Issue #40](https://github.com/masterxfix/MOSA-2/issues/40#issuecomment-6292628102) dokumentiert anonym HTTP 401 und HTTP 404 am entfernten temporären Gateway. Das sind damalige Nachweise, keine aktuelle Sitzungskontrolle. Eine vorhandene HTTPS- oder Browseranmeldung belegt keine DB-Rechte und umgekehrt.

## 6. Scheduler und Sicherungen

Die Plattformaufnahme vom 17.10.2026 fand neun bestehende geplante Aufgaben. Diese historische Anzahl ist keine Aussage über die heutige Anzahl. „Befehl ausführen“, „URL abrufen“ und „PHP-Skript ausführen“ waren verfügbar. Eine einmalige Ausführung über „Jetzt ausführen“ darf nicht mit dem Speichern eines regelmäßigen Jobs gleichgesetzt werden. Für reine Textänderungen wurde keine regelmäßige Aufgabe beauftragt.

Im damaligen Backup-Dialog waren 15 Kalendertage vom 03. bis 17.10.2026 und mehrere Wiederherstellungszeitpunkte sichtbar. DB-Restore bot Überschreiben oder Wiederherstellung in eine neue Datenbank; Webspace-Restore bot Überschreiben, separates Verzeichnis oder ZIP-Archiv. Bei dieser Bestandsaufnahme wurde nichts wiederhergestellt. Die sichtbare Historie ist keine vertragliche Aufbewahrungs- oder aktuelle Wiederherstellungsgarantie.

Der Testsite-Vertrag sieht vor Dateiänderungen eine Sicherung der betroffenen Originale, Inhaltsabgleich nach Übertragung und geschützte Rückfallinformationen vor. Temporäre Gateways und Hilfsdateien werden nach dem jeweiligen Nachweis entfernt. Keine bestehenden Aufgaben, Sicherungen oder fremden Dateien im Rahmen einer Dokumentationsbereinigung löschen.

Quellen: [Plattformaufnahme, Scheduler und Backups](../database/DOGADO_PLATFORM_QUALIFICATION.md), [historischer einmaliger CLI-Weg](../database/DOGADO_TEST_PLATFORM_PHASE1.md), [Testsite-Abnahme und Bereinigung](../database/CURRENT_DISPLAY.md).

## 7. Offene Zuordnungen und Nachweise

| Thema | Tatsächlich noch zu klären | Keine daraus folgende Zusatzmaßnahme |
| --- | --- | --- |
| Testsite-Pfad | Exakter Serverpfad plus Abbildung auf das verwendete Dateiübertragungsprofil | Keine neuen Ordner, Domains oder Datenbanken anlegen. |
| Normaler Testsite-Upload | Ob ein bestehender Zugang den Testordner erreicht; fester Zielschutz und geeigneter Dateiumfang | Nicht den bestehenden Workflow auf `mosa.scharwerk.de` starten. |
| Passwortentfernung | Ergebnis und verbleibender Authentifizierungsmodus, nicht nur die Anweisung | Keine erneute Passwortanforderung oder automatische Kontoänderung durch diese Dokumentation. |
| Abschluss von #41 | Tatsächlicher Live-/Commit-/Abnahmenachweis; zuletzt im geprüften Issue noch offen | Kein Abschluss allein aufgrund der Doku oder einer Testanzahl. |

Eine fehlende Pfadzuordnung ist eine Dokumentations- beziehungsweise Zugriffsfrage, kein Anlass für einen neuen Datenbankentwurf. Neue bestätigte Erkenntnisse werden hier mit Quelle nachgetragen; Vermutungen werden nicht als Tatsachen übernommen.

## 8. Quellen und Pflege

| Quelle | Enthält |
| --- | --- |
| [AGENTS.md](../../AGENTS.md) | Projektgrenzen; Chrome für Browseraktionen, keine pauschale Browserpflicht für Uploads. |
| [docs/DEPLOYMENT.md](../DEPLOYMENT.md) | Bisheriger SFTP-Vertrag für `mosa.scharwerk.de`, Secret-Namen, Pfadschutz und Fehlergrenzen. |
| [DOGADO_PLATFORM_QUALIFICATION.md](../database/DOGADO_PLATFORM_QUALIFICATION.md) | Historische Kontoaufnahme: Tarif, PHP/MySQL, Scheduler, Backups und unbestätigte Fähigkeiten. |
| [DOGADO_TEST_PLATFORM_PHASE1.md](../database/DOGADO_TEST_PLATFORM_PHASE1.md) | Anlage der separaten Testplattform sowie PHP-/PDO-/Rechte- und Laufzeitprüfungen. |
| [CURRENT_DISPLAY.md](../database/CURRENT_DISPLAY.md) | Current-/Reader-Vertrag, private Konfiguration, Schema 4 und Abnahmegrenzen. |
| [Migrationen](../database/migrations/README.md) | Versioniertes Schema und historische Live-Nachweise. |
| [Issue #8, Deploymentnachweis](https://github.com/masterxfix/MOSA-2/issues/8#issuecomment-6251399765) | Testseiten-Dateien übertragen und zurückgelesen; dort kein vollständiges WinSCP-Pfadmapping. |
| [Issue #9](https://github.com/masterxfix/MOSA-2/issues/9) | Webschutz der Testsubdomain. |
| [Issue #12, Entscheidung](https://github.com/masterxfix/MOSA-2/issues/12#issuecomment-6261006214) | Gemeinsame Systemidentität und frühere Ablehnung dauerhafter Test-DB-Secret-Ablage. |
| [Issue #40, Abschluss](https://github.com/masterxfix/MOSA-2/issues/40#issuecomment-6292628102) | Begrenzter Mehrasset-Nachweis, keine Produktion, damaliger Schutz- und Cleanupstand. |
| [Issue #41](https://github.com/masterxfix/MOSA-2/issues/41) | Erste DB-Anzeige, Nutzerentscheidungen und noch zu vervollständigender Abschluss. |
| [MOSA/fixlab: lokale Arbeitsweise](https://github.com/masterxfix/fixlab/blob/main/docs/17_LOKALE_ARBEITSWEISE.md) | Bestehendes WinSCP-/FTPS-Verfahren und damaliges Pfadmapping für MOSA; keine automatische MOSA-2-Freigabe. |

Die Originalquellen werden nicht verschoben oder gelöscht, damit vorhandene Links und technische Nachweise erhalten bleiben. Weitere Dogado-Betriebsinformationen werden an dieser zentralen Stelle ergänzt. Keine Passwörter, Cookies, Tokens, Codes, privaten Zugangskonfigurationen oder Secret-Werte aufnehmen. Beobachtungsdatum und Nachweisumfang nennen; eine Dokumentationsänderung ist keine Freigabe für einen Servereingriff.

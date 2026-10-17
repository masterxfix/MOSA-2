# MOSA 2 – Phase 0: Dogado-Plattformqualifikation

## 1. Kurzfazit

**Prüfstand: 17.10.2026 · Status: teilweise; Kontoprüfung ausstehend.**

Die offizielle Dogado-Dokumentation beschreibt MySQL 5.7/8.0, PHP 8.4,
DB-Zugriffssteuerung, SSH/SFTP, Cron und Backup/Restore. Das belegt das allgemeine
Angebot, aber weder den gebuchten Tarif noch die tatsächlich verfügbaren Optionen
im bereitgestellten Konto. Eine endgültige Plattformfreigabe ist deshalb offen.

Vorläufiger Testkandidat: **MySQL 8.0 + PHP 8.4 + lokaler DB-Zugriff**, vorbehaltlich
Kontobestätigung, Wartungsstatus und Kompatibilität. Keine Änderung der DB-Architektur.

In diesem Lauf wurden keine Aktionen im Dogado-Konto ausgeführt, Konfigurationen, Datenbanken,
Benutzer oder Dateien auf Dogado verändert, Zugangsdaten erfasst oder Tests auf dem
Hosting ausgeführt. Kein Deployment. Die nächste Testphase ist nicht freigegeben.

## 2. Im Dogado-Konto bestätigt

**Keine account-spezifischen Befunde.** Der aktuelle Browserzugang wurde in diesem
Lauf neu geprüft: Sowohl die Browser-Inventarisierung über `cua_repl` als auch die
alternative Computer-Use-Initialisierung über `node_repl` scheiterten bereits am
Start der Werkzeuglaufzeit. Eine Chrome-Tab-Liste und der angemeldete Dogado-Zustand
konnten nicht gelesen werden. Das ist kein Nachweis eines Fehlers bei Dogado oder
einer abgelaufenen Anmeldung. Konkret fehlt der aktuelle Chrome-Zugriff.

GitHub und der auf C: begrenzte Dateizugriff waren verfügbar; die unabhängige
Dokumentationsprüfung wurde fortgesetzt. Allgemeine Quellen werden ausdrücklich
nicht zu Kontobefunden hochgestuft. Issue #4 bleibt bis zur Kontoprüfung offen.

## 3. Durch Dogado-Dokumentation bestätigt

Alle folgenden Quellen wurden am 17.10.2026 gelesen. Angaben gelten ausschließlich
als allgemeine Dokumentation; Kontozustand und Vertragsumfang sind noch abzugleichen.

| Bereich | Offiziell dokumentierter Befund und Grenze |
| --- | --- |
| DB-Versionen / Host / Port | Dogado führt MySQL 5.7 und 8.0 in seiner [Datenbankübersicht](https://help.dogado.de/hc/de/sections/40680531398801-Datenbanken). Die [Verbindungsdokumentation](https://help.dogado.de/hc/de/articles/30150113244817) nennt beispielhaft `localhost:3306` für 5.7 und `127.0.0.1:3307` für 8.0; maßgeblich bleiben die tatsächlichen Verbindungsdetails. Das bestätigt keine aktuelle Auswahlliste oder weiteren Versionen im Konto. |
| DB-Verwaltung / Rechte | oneHome zeigt SQL-Version, zugeordnete Benutzer und Datenbanken sowie einen phpMyAdmin-Zugang. Eine Benutzerverwaltung ist beschrieben; konkrete SQL-GRANT-Rechte und verfügbare Quoten sind damit nicht bewiesen. [Übersicht](https://help.dogado.de/hc/de/articles/28701086312209) |
| DB-Zugriff | Pro DB-Benutzer sind lokaler Zugriff, zusätzlicher externer Zugriff oder festgelegte IP-Adressen dokumentiert. Die tatsächliche Einstellung, externe Adresse, TLS-Unterstützung und Erreichbarkeit bleiben ungeprüft. [Zugriffssteuerung](https://help.dogado.de/hc/de/articles/27402680955409) |
| Migration / Import / Export | Ein Versionswechsel 5.7 → 8.0 wird als Export/Import statt direkter Umstellung beschrieben. phpMyAdmin unterstützt SQL-Export und Import; bei zu großen Dateien oder Zeitlimits wird SSH-Import genannt. Keine konkreten Importgrenzen oder verlustfreie Migration zugesichert. [Versionswechsel](https://help.dogado.de/hc/de/articles/24039454806289), [Export](https://help.dogado.de/hc/de/articles/25399634267665), [Import](https://help.dogado.de/hc/de/articles/25399928393489) |
| PHP | Die [PHP-Info-Übersicht](https://help.dogado.de/hc/de/articles/30783660021265) verlinkt unter anderem 8.4, 8.3, 8.2 und 8.1; das ist keine vollständige aktuelle Konto-Auswahlliste oder Supportzusage. `memory_limit`, `max_execution_time` und `upload_max_filesize` werden als tarifabhängig und nicht individuell anpassbar beschrieben. [PHP-Einstellungen](https://help.dogado.de/hc/de/articles/23639059019921) dokumentieren PHP-Wahl pro Domain/Subdomain sowie `allow_url_fopen`, `allow_url_include`, `display_errors` und OPcache. Werte und aktive Module im Konto bleiben offen. |
| Cron / Scheduler | oneHome dokumentiert URL-Aufruf, PHP-Skript und Befehlsausführung, Zeitplanung und Benachrichtigungen. Im Webhosting nennt Dogado Verfügbarkeit ab WEB M; daraus folgt keine Zusage für den vorhandenen Vertrag. Mindestintervall, Parallelität und Laufzeitlimits sind nicht belegt. [Cron-Jobs](https://help.dogado.de/hc/de/articles/22596259479697) |
| SSH / SFTP | SSH und SFTP sind über Port 22 mit dem primären FTP-Benutzer beschrieben; zusätzliche FTP-Benutzer sind dafür nicht nutzbar. Das begrenzt die dokumentierte Trennung eigener Transferkonten. Kein Nachweis für Root-Rechte, freie Paketinstallation, dauerhafte Prozesse oder die Freischaltung im Konto. [SSH](https://help.dogado.de/hc/de/articles/28529974109457), [SFTP](https://help.dogado.de/hc/de/articles/28533569940113) |
| Backup / Restore | Das Help Center beschreibt automatische Sicherung von Webdaten, Datenbanken und E-Mails alle 3 Stunden mit mindestens 7 Tagen Aufbewahrung. DB-Restore ist überschreibend oder in eine separate DB beschrieben; Webdaten zusätzlich in einen separaten Ordner oder als ZIP. Takt, Historie, freie Restore-Quota, Konsistenz und Wiederherstellungszeit im vorhandenen Vertrag sind unbestätigt. [Backup und Datensicherung](https://help.dogado.de/hc/de/articles/22559232450833) |
| Weitere Funktionen | Die [Hosting-Anleitungen](https://help.dogado.de/hc/de/articles/27369694900753) dokumentieren Subdomains, Let's Encrypt, WAF, Logs und Statistiken. Sinnvolle Prüfkandidaten für getrennte Testumgebung, HTTPS und Fehleranalyse; keine Konto-Bestätigung. |

## 4. Noch offen / praktisch zu testen

| Noch lesend im Konto zu klären | Später gesondert praktisch zu testen |
| --- | --- |
| Vollständige DB-Auswahlliste: 5.7, 8.0, gegebenenfalls weitere MySQL-/MariaDB-Versionen; zugehöriges Host/Port-Modell, Wartungs- und Upgradepolitik | Treiberkompatibilität, SQL-Modi, Zeichensätze/Kollationen, Transaktionen, JSON, Index- und Queryverhalten der gewählten Version |
| Vertragliche und freie DB-Anzahl, DB-Größenlimit, Benutzerzuordnung und verfügbare Rechte | Verbindungs-/Benutzerlimits, konkurrierende Transaktionen, Lock-Wartezeiten und Verhalten bei Fehlern |
| Lokaler/externer/IP-beschränkter Zugriff, DB-TLS und sichtbare phpMyAdmin-Funktionen und Importgrenzen | Lokaler TCP-Zugriff, nötige externe Verbindung ausschließlich mit begrenzter Freigabe; Import-/Exportdauer und Speicherbedarf |
| Vollständige PHP-Auswahlliste, Handler, OPcache, PDO/MySQL-, cURL-, mbstring-/intl-Module; Speicher-, Upload-, POST- und Laufzeitwerte; CLI-Pfade/-Versionen | Gleichheit und Unterschiede von Web- und CLI-Laufzeit, ausgehende HTTPS-Verbindungen und Fehlerbehandlung |
| Cron-Verfügbarkeit, Jobanzahl, Mindestintervall, Zeitzone und sichtbare Laufzeit-/Parallelitätsgrenzen; SSH-/SFTP-Einschränkungen | Überlappungsschutz, Wiederanlauf, begrenzte Collector-/KI-Jobs, Logs und Abbruch nach Zeitbudget |
| Webspace gesamt/frei, mögliche Datei-/Inode-/Dateigrößenlimits und Nutzungsvorgaben für Medien/Dokumente | Große Dateien nur nach eigener Freigabe; Durchsatz, Quota-Verhalten und Wiederherstellbarkeit |
| DB-/Webspace-Sicherungspunkte, Retention, Restore-Optionen und benötigte freie Quota | Konsistenter DB-/Dateistand, Restore ausschließlich in isoliertes Ziel, Vollständigkeit, gemessene RPO/RTO und unabhängiger Export |
| Ausgehende Ports/Netzwerkgrenzen, gegebenenfalls erlaubte VPN-/Worker-Funktionen | Erreichbarkeit erforderlicher Datenquellen; Anbindung eines Heimnetzes ist nicht nachgewiesen |

Für ausgehende Ports lieferte der verlinkte Help-Center-Artikel beim Abruf HTTP 404;
daraus wird weder Erreichbarkeit noch eine Portsperre abgeleitet.
Abweichungen zwischen Konto und Dokumentation konnten mangels Kontosicht nicht
geprüft werden. Beim späteren Abgleich hat der tatsächliche Kontozustand Vorrang.

## 5. Empfehlung für MOSA-2-Testplattform

**Planungsvorschlag, keine endgültige technische Festlegung:** MySQL 8.0 und PHP 8.4
zuerst prüfen, weil diese Kombination öffentlich dokumentiert ist. Vor Freigabe die
aktuellen Kontooptionen einschließlich neuerer Versionen sowie deren Wartungsdauer
vergleichen. MySQL 5.7 nur als mögliche Migrationsquelle behandeln.

Nach Kontobestätigung lokal verbinden, einen eigenen Testbereich und getrennte
DB-Zuordnung vorsehen und Cron für kurze, wiederaufnehmbare Jobs bewerten.
SFTP/SSH, OPcache, Logs und getrennten Restore nur nutzen, soweit tatsächlich
verfügbar. Produktionsdaten und MOSA bleiben unberührt.

Nicht voraussetzen: unbegrenzte DB-/Dateigröße, garantierte CPU/IOPS oder Parallelität,
Root-Zugriff, Docker, dauerhafte Worker, VPN/Heimnetzzugriff, beliebige ausgehende
Ports, ausreichend große Browserimporte oder ein bereits bewiesenes Restore.

Wesentliche Risiken: unbekannte Ressourcen für große Historientabellen; Kollations-
und SQL-Unterschiede bei Migrationen; fehlende freie Quota für parallele DBs/Restore;
unklare Konsistenz von DB- und Dateibackup; Medienwachstum und lange KI-/Collector-Jobs.
Große Dateien gemäß bestehender Planung außerhalb der DB halten. Ein externer
Worker oder separater Dateispeicher bleibt eine spätere Entscheidung nach Messung.

## 6. Nächste Testphase

**Nur vorbereitet, nicht durchgeführt; ausdrücklich gesondert freizugeben.**

1. Zuerst die offene Konto-Bestandsaufnahme vervollständigen, Vertragslimits und
   freie Quota bestätigen; Testversionen und einen begrenzten Ressourcenrahmen festlegen.
2. Danach isolierte MOSA-2-Test-DB und Testbereich mit synthetischen Daten vorsehen.
   Vorschlag: zunächst 10.000, dann 100.000 Historienzeilen; 1 Million erst nach
   gesonderter Größen-/Lastfreigabe. Current-Lesewege und History-Abfragen getrennt messen.
3. Indizes und EXPLAIN, Sortierung/Pagination, Migration mit Checkpoints und
   Wiederholbarkeit prüfen; paralleles Lesen/Schreiben zunächst mit zwei Clients.
4. p50/p95 für Abfragen und Seiten sowie DB-Zeit messen; gegen die bestehenden
   Ziele im [Datenbank-README](README.md#performance-budget) vergleichen. Abbruchgrenzen
   vorab festlegen; keine Lastannahmen aus allgemeinen Hosting-Angaben ableiten.
5. Synthetischen Export/Import und Restore in getrennte Ziele samt Prüfsummen,
   Zeilenzahlen und Zeitmessung testen. Cron/CLI-Version, Jobüberlappung,
   Wiederanlauf und ausgehendes HTTPS begrenzt prüfen.
6. Erst nach Konto- und Messnachweis DB-Version, Laufzeit und Betriebsgrenzen
   verbindlich festlegen. Issue #4 erst nach erfüllter Kontoprüfung abschließen.

# MOSA 2 – Phase 0: Dogado-Plattformqualifikation

## 1. Kurzfazit

**Prüfstand: 17.10.2026 · Status: read-only Konto-Bestandsaufnahme abgeschlossen.**

Die vorhandene angemeldete interne Browser-Sitzung wurde inventarisiert und genutzt.
Das Konto bietet **WEB M 3.0, 50 Datenbanken, 150 GB Speicher, MySQL 5.7 und MySQL 8
sowie PHP bis 8.5**. Der Expertenzugang zu Plesk und phpMyAdmin funktioniert.
Die bisherigen Browserblockaden beschreiben nicht mehr den aktuellen Zustand.

Empfehlung für die ausdrücklich erst später freizugebende Testumgebung:
**MySQL 8.0 + PHP 8.4/FPM + lokaler DB-Zugriff** als Ausgangspunkt;
PHP 8.5 zusätzlich auf Kompatibilität vergleichen. Die Bestandsaufnahme ist keine
Freigabe einer endgültigen DB-Architektur oder eines produktiven Versionswechsels.

Es wurden keine Datenbanken, Benutzer, Rechte, Einstellungen oder Hostingdateien
verändert, keine Passwörter angezeigt oder kopiert und keine SQL-, Import-, Export-,
Restore-, Cron- oder Lasttests ausgeführt. Formulare und Restore-Assistenten wurden
nur gelesen und ohne Speichern bzw. Ausführung verlassen. Kein Deployment.

## 2. Im Dogado-Konto bestätigt

Nachweisweg: vorhandener interner Dogado-Tab → oneHome → jeweiliger Menüpunkt;
über den bestehenden Expertenzugang zusätzlich Plesk und dessen Web Admin.
Accountnummern, Benutzernamen, DB-Namen und individuelle Serveradressen bleiben
aus dieser Dokumentation ausgespart. Angaben sind Beobachtungen dieses Prüfstands.

| Bereich / gelesene Ansicht | Tatsächlicher Kontobefund |
| --- | --- |
| Tarif / Ressourcen: oneHome-Dashboard, Plesk → Konto → Ressourcen | WEB M 3.0 aktiv; **3 von 50 Datenbanken**, rechnerisch 47 freie Plätze. **150 GB Speicher**. oneHome zeigt 6,32 GB belegt, Plesk 7725,7 MB; die unterschiedlichen Nutzungsanzeigen werden nicht gleichgesetzt. Plesk bezeichnet Traffic als unbegrenzt und erlaubt laut Ressourcenansicht Überbeanspruchung von Speicher/Traffic; daraus folgt keine höhere vertragliche Speicherquote. |
| Weitere Quoten | oneHome: 4 von 50 FTP-Accounts. Plesk: 3 zusätzliche FTP-Konten genutzt, maximal 50 zusätzliche. Diese Zählweisen unterscheiden sich. Kein separates DB-Größen-, Connection-, Inode- oder CPU-/IOPS-Limit in den geprüften Ressourcenansichten ausgewiesen. |
| DB-Versionen: oneHome → Datenbanken → Anlageformular | Die aufgeklappte Auswahl enthält **MySQL 5.7** und **MySQL 8**, keine weitere Version und kein MariaDB. phpMyAdmin bezeichnet den zweiten Server als **MySQL 8.0**. Es wurde keine DB erstellt und keine Version umgestellt; die genaue 8.x-Patchversion bleibt ungeprüft. |
| DB-Host / Port: DB-Liste, Pfade und Ports | Alle drei vorhandenen DBs sind als **MySQL 5.7, localhost:3306** ausgewiesen. Das Konto nennt für externen Zugriff **3306 für 5.7 und 3307 für MySQL 8**. Die konkrete lokale MySQL-8-Verbindungsadresse wurde mangels bestehender 8er-Test-DB nicht verifiziert; 127.0.0.1:3307 bleibt hierfür zunächst Dokumentationsangabe. |
| DB-Größen / phpMyAdmin-Strukturübersicht | Eine vorhandene DB wird mit **6,1 GiB** und InnoDB-Tabellen angezeigt. Das ist eine Ist-Größe, keine zugesicherte Maximalgröße. Tabelleninhalt wurde nicht geöffnet; angezeigte InnoDB-Zeilenzahlen sind Schätzwerte und kein Benchmark. |
| DB-Benutzer / Rollen | Zwei Benutzer werden verwaltet; einer ist einer konkreten DB zugeordnet, beim anderen steht „Beliebige Datenbank“. Rollenwahl im Anlageformular: **Lesen und Schreiben, Nur lesen, Nur schreiben**. In einer vorhandenen Benutzeransicht sind „Lesen und Schreiben“ und „Nur lokalen Zugriff zulassen“ eingestellt. Dies ist eine Stichprobe, keine Aussage über sämtliche Benutzer oder SQL-GRANT-Details. |
| Lokaler / externer / IP-Zugriff | Im Konto sind **Nur lokalen Zugriff zulassen, Externen Zugriff zulassen, Benutzerdefinierte Verbindungen zulassen** angeboten. Plesk → Konto → Berechtigungen weist Remotezugriff für DB-Benutzer und Datenbankserverauswahl als erlaubt aus. Es wurde keine Zugriffsart geändert; konkrete IP-Freigaben, TLS und externe Verbindungsfähigkeit bleiben ungeprüft. |
| phpMyAdmin / Import / Export | Web Admin öffnet angemeldet **phpMyAdmin 5.2.3**. Sichtbar: Struktur, SQL, Suche, Abfrage, Import und Export. Export bietet Schnell/Angepasst und unter anderem SQL, CSV, JSON, XML und YAML. Import bietet unter anderem SQL/CSV/XML, gzip/zip sowie Teilimport bei nahendem PHP-Timeout mit Hinweis auf mögliche Transaktionsunterbrechung. Das Importformular nennt **„Maximal: 2.048 MiB“**. Keine Datei ausgewählt, kein Import/Export gestartet, keine SQL-Abfrage ausgeführt. |
| PHP-Auswahl: Domains → PHP-Einstellungen | Aufgeklappt verfügbar: **5.2/5.3 FastCGI; 5.4, 5.5, 5.6, 7.0–7.4, 8.0–8.5 FPM**. Bis einschließlich 8.1 mit Hinweis auf erforderlichen erweiterten Support. Eine bestehende Domain ist mit 8.4, weitere mit 8.3 ausgewiesen. Keine Version ausgewählt oder gespeichert. |
| PHP-Limits / Optionen | Die geprüfte oneHome-PHP-Ansicht zeigt nicht bearbeitbare Paketwerte: **max_memory_limit 256 MB; max_execution_time 900 s; max_input_time 900 s; upload_max_filesize 64 MB; post_max_size 64 MB**. Sichtbare Optionen: allow_url_fopen, allow_url_include, display_errors und opcache_enable. Das Versionsfeld zeigt zunächst „Bitte auswählen“; deshalb werden Formular-Schalterwerte nicht als verifizierte Laufzeitkonfiguration ausgegeben. Die Werte sind kein CLI- oder phpMyAdmin-Limitnachweis. |
| PHP / Werkzeuge: Pfade und Ports | Das Konto listet versionierte PHP-CLI-Pfade bis **/opt/plesk/php/8.5/bin/php**, darunter /opt/plesk/php/8.4/bin/php, sowie Python, Perl und ImageMagick. Vorhandene Pfadangaben beweisen keine getestete Version, Modulausstattung oder freie Paketinstallation. |
| Cron / Scheduler: Plesk → Geplante Aufgaben | **9 Aufgaben** sichtbar; darunter aktivierte Minutentakte und weitere periodische Zeitpläne. Das ungespeicherte Anlageformular bietet **Befehl ausführen, URL abrufen, PHP-Skript ausführen**, Cron-Stil sowie Stunden-/Tages-/Wochen-/Monats-/Jahresplanung. Angezeigte Zeitzone: **Europe/Berlin (UTC+02:00 zum Prüfzeitpunkt)**. Benachrichtigung: keine, nur Fehler oder jedes Mal. Keine Aufgabe angelegt, geändert, deaktiviert oder gestartet. Ein konfigurierter Minutentakt beweist keine Ausführungsgarantie. |
| SSH / SFTP / FTP | Port 22 und die Funktion „SSH/SFTP einrichten“ sind vorhanden. Plesk erlaubt die Verwaltung von SSH-Zugriff mit „Zugriff auf jeden Shell-Typ erlauben“. Primäre/sekundäre FTP-Konten und unterschiedliche Basisverzeichnisse sind sichtbar. Die Einrichtungsschaltfläche wurde nicht betätigt; aktueller Shell-Typ, Login, SFTP und Netzwerkzugriff wurden nicht praktisch getestet. |
| Backup-Historie: Sicherheit → Backups | **15 angebotene Kalendertage vom 03. bis 17.10.2026**. Für den 17.10. sind 03:50, 06:54 und 09:56 auswählbar. Das ist eine sichtbare Historie, keine vertragliche Retentions- oder exakte RPO-Garantie. Die separate Liste „Abgeschlossene Backups“ ist leer; dies bedeutet nicht, dass keine Sicherungspunkte vorhanden sind. |
| DB-Restore | Der Assistent bietet alle drei vorhandenen DBs aus dem gewählten Sicherungspunkt an. Schritt 3/4 zeigt **Überschreiben** oder **Wiederherstellen in einer neuen Datenbank**. Keine dieser Ausführungsarten ausgewählt oder gestartet; Assistent abgebrochen. |
| Webspace-Restore | Verzeichnisse sind einzeln auswählbar. Schritt 3/4 bietet **Überschreiben**, **Wiederherstellen in einem separaten Verzeichnis** und **Archivieren als ZIP im Stammverzeichnis**. Nur die Modi gelesen, anschließend abgebrochen; keine Dateien wiederhergestellt oder Archive erstellt. |
| Weitere sinnvolle Funktionen | Plesk-Expertenpanel, Web-FTP, Verzeichnisschutz, WAF-Verwaltung, Domain-/Subdomain-Verwaltung und Logs sind vorhanden. Dashboard meldet Firewall aktiv; Vertragsoptionen melden SSL/TLS-Unterstützung an. Plesk-Berechtigungen nennen zusätzlich REST-API sowie Ruby-Verwaltung; Funktions- und Sicherheitsumfang sind nicht praktisch geprüft. |

**Relevante Unterschiede:** PHP 8.5 ist im Konto verfügbar, obwohl die bisher
verwendete PHP-Info-Übersicht nur bis 8.4 verlinkt. Die sichtbare Backup-Historie
reicht weiter als die allgemein dokumentierten mindestens sieben Tage; daraus
entsteht keine zusätzliche Vertragszusage. Die Web-PHP-Uploadgrenze 64 MB und die
phpMyAdmin-Anzeige 2.048 MiB gehören zu unterschiedlichen Oberflächen.
Speicher- und FTP-Zählweisen unterscheiden sich zwischen oneHome und Plesk.
Für konkrete Planung gelten die jeweils bestätigte Kontoansicht und deren Kontext.

## 3. Nur durch offizielle Dokumentation bestätigt

Die vorhandenen offiziellen Quellen aus der Vorarbeit bleiben ergänzend gültig;
in diesem Lauf fand keine allgemeine Ersatzrecherche statt.

| Nur dokumentierter Punkt | Quelle / Grenze |
| --- | --- |
| MySQL 8.0 lokal beispielhaft 127.0.0.1:3307; konkrete Verbindungsdetails maßgeblich | [Verbindungsdaten](https://help.dogado.de/hc/de/articles/30150113244817). Port 3307 ist zusätzlich im Konto bestätigt; die lokale Adresse für eine neue Test-DB noch nicht. |
| Wechsel 5.7 → 8.0 über Export/Import, kein direkter Versionswechsel | [Versionswechsel](https://help.dogado.de/hc/de/articles/24039454806289). Keine Migration durchgeführt. |
| IP-Adressen für benutzerdefinierten DB-Zugriff; größere Importe alternativ per SSH | [Zugriffssteuerung](https://help.dogado.de/hc/de/articles/27402680955409), [Import](https://help.dogado.de/hc/de/articles/25399928393489). UI-Optionen bestätigt, Verbindungen und Importe ungetestet. |
| SSH/SFTP mit primärem FTP-Benutzer, zusätzliche FTP-Benutzer dafür nicht nutzbar | [SSH](https://help.dogado.de/hc/de/articles/28529974109457), [SFTP](https://help.dogado.de/hc/de/articles/28533569940113). Diese konkrete Einschränkung wurde nicht durch Login getestet. |
| Allgemein Sicherungen alle drei Stunden, mindestens sieben Tage Aufbewahrung | [Backup](https://help.dogado.de/hc/de/articles/22559232450833). Konto-Historie und Restore-Modi sind oben separat belegt; Konsistenz und Wiederherstellungszeit nicht. |
| PHP-Ressourcenlimits paketabhängig; Versions-/Optionsverwaltung | [PHP-Info](https://help.dogado.de/hc/de/articles/30783660021265), [PHP-Einstellungen](https://help.dogado.de/hc/de/articles/23639059019921). Tatsächliche Auswahl und sichtbare Paketwerte stehen oben. |
| Cron-Anwendungsfälle und allgemeine Verfügbarkeit ab WEB M | [Cron](https://help.dogado.de/hc/de/articles/22596259479697). Im vorhandenen Konto zusätzlich durch Plesk-Scheduler bestätigt. |

## 4. Noch offen / später praktisch zu testen

Die folgenden Punkte sind **kein ausstehender Browserzugriff**, sondern Grenzen der
zulässigen Bestandsaufnahme oder spätere Messaufgaben:

- MySQL-8-Patchversion, tatsächlicher lokaler Host, SQL-Modi, Kollationen, TLS,
  SQL-Einzelrechte sowie Wartungs-/Upgradepolitik; keine neue DB nur zur Ermittlung angelegt.
- Maximale DB-Größe, Verbindungs-/Benutzerlimits, Lock-Zeiten, CPU, RAM, IOPS,
  Prozesse, Datei-/Inodegrenzen und Speicherabrechnung; aus Ist-Größen nichts ableiten.
- Web-/CLI-PHP-Versionen und Module, effektive OPcache-Konfiguration,
  CLI-Laufzeitgrenzen, ausgehendes HTTPS und weitere Ports. Die Pfadliste ersetzt keine Messung.
- Tatsächliche lokale/externe/IP-beschränkte DB-Verbindungen und SFTP/SSH-Anmeldung.
  Keine Freigaben, Passwörter oder Shell-Einstellungen geändert.
- Scheduler-Ausführungsdauer, Parallelität, Jobanzahl-Limit, Überlappungsschutz,
  Wiederanlauf und Ausführungsgarantie. Bestehende Aufgaben nicht testweise gestartet.
- Upload/Import über angezeigte Grenzwerte, große Exporte und Datenmigration,
  konsistenter DB-/Dateistand, Restore-Prüfung, freie Quota beim Restore sowie RPO/RTO.
- Medien-/Dateidurchsatz, Eignung für große Archive, dauerhafte Worker,
  Docker/Root/Paketinstallation sowie VPN-/Heimnetz-Anbindung nicht zugesichert.
- Unterschiedliche Belegungsanzeigen vor einer kapazitätskritischen Migration klären;
  Vertragsgarantien zur Backup-Retention gesondert von sichtbaren Sicherungstagen behandeln.

## 5. Empfehlung für die MOSA-2-Testplattform

**MySQL 8.0, PHP 8.4/FPM und versionierte PHP-8.4-CLI** zunächst isoliert testen.
MySQL 8.0 ist im Serverselektor ausdrücklich benannt; MySQL 5.7 bleibt Quelle.
PHP 8.4 ist bereits für eine bestehende Domain ausgewiesen. **PHP 8.5** als
zusätzlichen Kandidaten vergleichen, bevor der endgültige Laufzeitstandard feststeht.
Die Verfügbarkeit alleine entscheidet weder Kompatibilität noch langfristigen Support.

Nach ausdrücklicher Freigabe: eigene Test-DB und eigener Testbereich, lokale
DB-Verbindung, getrennte Rollen und kurze, wiederaufnehmbare Cron-Jobs. Logs,
OPcache, SSH/SFTP und Restore in getrennte Ziele nur nach erforderlicher Prüfung nutzen.
Große Dateien entsprechend dem bestehenden Datenbankplan außerhalb der DB ablegen.

Risiken bleiben Shared-Hosting-Ressourcen für große Historien, SQL-/Kollationswechsel,
lange KI-/Collector-Jobs, ungemessene Parallelität, Backups von DB und Dateien sowie
wachsende Medienbestände. Root, dauerhafte Worker und Heimnetzzugriff nicht voraussetzen.
Keine bestehende Architektur oder produktive Laufzeit wurde geändert.

## 6. Nächste ausdrücklich freizugebende Testphase

**Nur vorbereitet, nicht durchgeführt.**

1. Isolierte MySQL-8-Test-DB und Testbereich mit begrenztem Ressourcenbudget vorsehen;
   lokale Verbindung und Rechte, genaue DB-/PHP-Versionen sowie Module prüfen.
2. Synthetische Historien mit zunächst 10.000 und 100.000 Zeilen; 1 Million erst nach
   eigener Größen-/Lastfreigabe. Current-Lesewege und History getrennt messen.
3. EXPLAIN/Indizes, Filter, Sortierung/Pagination, Checkpoint-Migration und
   Wiederholbarkeit prüfen; paralleles Lesen/Schreiben zunächst mit zwei Clients.
4. p50/p95 und gesamte DB-Zeit gegen die [bestehenden Performanceziele](README.md#performance-budget)
   messen; Abbruchgrenzen vorab festlegen. PHP 8.4 und 8.5 vergleichen.
5. Synthetischen Export/Import und DB-/Datei-Restore ausschließlich in getrennte
   Ziele samt Zeilenzahlen, Prüfsummen, Konsistenz- und Zeitprüfung testen.
6. Begrenzte Cron-/CLI-Jobs, Überlappungsschutz, Wiederanlauf und nötige
   Netzwerkverbindungen prüfen. Erst nach diesen Ergebnissen die Plattform festlegen.

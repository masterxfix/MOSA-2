# Einmaliger Dogado-seitiger DroneShield-Modellpilot

Ausgangscommit f39e5c238f109d7bec766c13ea1596829e3c8c61, voriger Versuch ohne
API-POST wegen fehlendem Runner-Secret. Neue ausdrückliche Nutzerfreigabe erlaubt
stattdessen die serverseitige Nutzung des bestehenden MOSA-Schlüssels.
Kein neuer Schlüssel und kein API-Secret für GitHub.

Der vorhandene Read-only-Leser und Snapshot-Adapter laufen auf dem Actions-Runner.
Nur ISIN AU000000DRO2 mit 14 Observations, 7 Current, FY2025/FY2024 und AUD wird
akzeptiert. Keine Fixtures im Live-Pfad. Snapshot und geprüfte Modulquellen werden
über den bestehenden gepinnten SSH-Kanal in einen dateilosen Python-3.11-Prozess
übertragen (höchstens 64 KiB Eingabe). Es werden keine Python-Dateien deployed.
Dort werden exakt dieselben assessment.py und responses_transport.py im flüchtigen
Arbeitsspeicher geladen, keine zweite Finanz- oder KI-Implementierung.

Ausschließlich der Serverprozess öffnet den exakt dokumentierten Pfad:
/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php
Kein Scan, kein Alternativpfad und kein Ausweichen aus einem Chroot. Ein nicht
sichtbarer/lesbarer Pfad stoppt als CONFIG_NOT_VISIBLE_OR_READABLE vor jedem POST.
Prüfung: O_NOFOLLOW, reguläre Datei, Owner 10317/1003, Modus 0600 oder 0640;
PHP prüft zusätzlich unveränderten realpath/Inode, Rechte, Größe und Inhalts-Hash.
Dateizugriffszeit gehört nicht zur Inhaltsänderung. Abweichende Rechte werden
nicht repariert. PHP /opt/plesk/php/8.4/bin/php -n liest ausschließlich diese
Konfiguration als Array und entnimmt OPENAI_API_KEY entsprechend dem bestehenden
Loader-Vertrag (php/openai_runtime_config.php wurde auf GitHub read-only geprüft).
Ausgaben/Warnungen werden abgefangen. Schlüssel und Konfigurationshash fließen
nur über eine interne Prozesspipe auf Dogado, niemals über SSH nach GitHub.
Kein Kopieren der Konfigurationsdatei, kein Secret-Export/Artefakt und keine
Änderung der alten MOSA-Installation. Nach Erfolg werden Hash/Schlüssel lokal
nochmals unverändert geprüft.

Neuer Workflow fundamentals-assessment-dogado-once.yml, manuell auf main,
Run-/Attempt-Nummer 1, exakter Commit plus
MOSA2-DRONESHIELD-DOGADO-AI-ONCE-20261101:<commit>. Vor POST exklusive Reservierung
fundamentals-ai-droneshield-dogado-20261101-01.consumed im qualifizierten privaten
MOSA-2-locks-Bereich. Bestehende create_file/read_file/checked-Funktionen prüfen
Owner, Mode, no-follow, exklusiven Write, fsync und Readback. Marker bindet
Commit, ISIN, Input-Digest, Modell, Workflow und Pilotkennung. Auch bei Timeout
bleibt er verbraucht. Kein Retry und keine Reparaturanfrage.

Kosten: offizielle Modellseite am 01.11.2026 erneut geprüft:
https://developers.openai.com/api/docs/models/gpt-6.1-sol
Standard 2 USD/Million Input, 10 USD/Million Output. Vorhandene konservative
Preisfreigabe 2,75/11 berücksichtigt zusätzlich veröffentlichte Cache-Schreib-
und Regionalzuschläge. Sie ist maximal 24 Stunden gültig. Standard-tier explizit,
keine Fast-/Ultrafast-Modi, Tools oder Websuche. Tatsächlicher Requestumfang
inklusive Schema plus Reserve, maximal 4000 Ausgabetokens inklusive Reasoning,
60-Sekunden-Transporttimeout und 64-KiB-Antwortgrenze. Kosten >0,10 USD stoppen
vor Marker/POST. Keine tatsächliche Rechnung behaupten; bei fehlender Usage
Kostenstatus UNKNOWN. Die alte Konfiguration kann das Modell nicht überschreiben.

Auf Dogado: strikte unabhängige Prüfung von Schema, Digest, Invocation, allen
Fakten/Werten/Einheiten/Quellen/Rundungen, Berechnungen und Interpretationen.
Nur eine begrenzte, vorab definierte Zusammenfassung kommt über SSH zurück,
kein Roh-Response und keine umfangreichen Snapshots. Der Runner prüft die
Antwortbindung und danach den realen DB-Snapshot erneut. Keine KI-Bewertung
wird dauerhaft gespeichert. Offline-Tests verwenden ausschließlich Fake-Transport
und Fake-Schlüssel. Die tatsächliche Sichtbarkeit der bestehenden privaten
Konfiguration wird erst im einzigen freigegebenen Actions-Lauf nachgewiesen.

# Bestehender MOSA-Schlüssel: ausdrücklich autorisierter Einmalpilot

Ausgangscommit: 8f9a01a0f2c5f5b3df6cfc5af7cbffc89ba12e66.
Der Nutzer verwirft den 0600-Änderungsweg ausdrücklich. Keine chmod/chown,
keine Web-PHP-UID-Diagnose, kein neues Secret, keine Schlüsselkopie und
keine Änderung/kein Deployment der bestehenden MOSA-Installation.

Die lokale Policy akzeptiert 0644 ausschließlich am bereits fest eingebauten
CONFIG-Pfad in assessment_dogado_remote.py, bei Prozess UID/GID 10317/1003,
Datei-Owner/Gruppe 10317/1003, regulärer Datei und genau einem Hardlink.
Alle anderen Pfade behalten die bestehende restriktive Mode-Policy.
Python/PHP entscheiden identisch. Exakte Eltern werden unverändert no-follow
gegen fremden Owner, Symlinks, Schreibrechte und spezielle Bits geprüft.
O_NOFOLLOW, fstat und Device/Inode/Mode/Owner/Gruppe/Größe/mtime/ctime/nlink
binden den Zugriff; PHP vergleicht Inhaltshash und Metadaten vor/nach require.
Nach dem Modellaufruf werden Hash, Schlüssel und Identität intern erneut verglichen.
Keine Konfigurationsbytes, Hashes oder Schlüssel gelangen nach GitHub.

Sicherheitsrisiko bleibt offen: 0644 und Eltern mit 0710/0750 beweisen keine
Isolation gegenüber sämtlichen anderen lokalen Konten, Gruppen oder ACLs.
LOCAL_READ_ISOLATION_UNPROVEN ist ausdrücklich keine Sicherheitsreparatur.
Aus vorhandenen exakten Elternmodi konkret nachweisbare vollständige
Welt-Traversierbarkeit stoppt als CONFIG_OTHER_READ_ACCESS vor dem Key-Lesen.
Keine Konto-/Verzeichnisscans oder probeweisen Zugriffe fremder Identitäten.

Neuer manueller Workflow fundamentals-assessment-existing-mosa-once.yml,
Run/Attempt 1, exakter Main-Commit und
MOSA2-DRONESHIELD-EXISTING-MOSA-AI-ONCE-20261101:<commit>.
Neue exklusive Reservierung fundamentals-ai-droneshield-existing-mosa-20261101-01
über vorhandene private Markerfunktionen; erst nach Sicherheits-/Kostenpreflight,
unmittelbar vor genau einem POST. Unbekanntes Ergebnis bleibt verbraucht.
Kein Retry und keine früheren Workflows erneut starten.

Vorhandener realer Read-only-Snapshot: DroneShield AU000000DRO2, 14 Fakten,
7 Current, FY2025/FY2024, AUD. Bestehende Analyse-, Schema-, Digest-, Fakten-,
Berechnungs-, Quellen- und Interpretationsprüfung. Nur geprüfte Code-/Kennzahl-/
Periodenmetadaten für eine deutsche Zusammenfassung, keine freie Modellprosa.
Unabhängiger abschließender DB-Readback. Keine DB-Schreiboperation.

Offizielle Preise am 01.11.2026 16:07 UTC erneut geöffnet/geprüft:
https://developers.openai.com/api/docs/models/gpt-6.1-sol
Standard 2 USD/M Input und 10 USD/M Output. Konservative vorhandene Freigabe
2,75/11 berücksichtigt Cache-Write- und Regionalaufschläge, maximal 24 Stunden.
Explizit default tier, keine Tools, medium, höchstens 4000 Outputtokens inkl.
Reasoning, tatsächliche Requestbytes plus Reserve als Inputobergrenze.
Kosten müssen vor POST <=0,10 USD sein; Usage ergibt nur eine konservative
Kostenschätzung, keine Abrechnungsbestätigung.

Fokussierte Offline-Tests: exakte 0644-Ausnahme und Python/PHP-Parität,
Fremdpfad/Owner/Gruppe/Symlink/Hardlink/Sonderrechte abgewiesen,
Identitätsänderung und konkret weltlesbarer Pfad stoppen ohne Key/Marker/POST;
bestehende Referenz-, Kosten-, Transport-, Einmalmarker- und Secret-Tests.

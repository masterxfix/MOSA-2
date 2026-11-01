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

## Zweite ausdrückliche Freigabe nach aa0b35a

Der vorhandene Workflow wird gezielt für Run Number 2 / Attempt 1 angepasst,
kein neuer Workflow. Autorisierung MOSA2-DRONESHIELD-SECOND-AI-20261101:<commit>.
Runner nutzt shared.guard mit reusable_manual und prüft zusätzlich exakt Run 2;
Workflow prüft Run 2 sowohl im Job-Guard als auch im Shell-Schritt.
Die Workflow-Historie enthielt vor Vorbereitung nur Run 1 (41324852699).
Vor dem einzigen Dispatch muss das erneut bestätigt sein.
Neue Profilkennung fundamentals-ai-droneshield-existing-mosa-20261101-02;
vorhandene exklusive Reservierungsfunktionen unverändert. Alter Marker bleibt
verbraucht und unverändert. Höchstens ein weiterer POST, niemals Retry.

Preisquelle am 01.11.2026 16:51:12 UTC frisch geprüft: unverändert Standard
2 USD/M Input und 10 USD/M Output; konservative Freigabe weiterhin 2,75/11.
Der vollständige Request einschließlich Interpretationsvertrag geht ins Budget.
Frischer echter Snapshot über den bestehenden Read-only-DB-Weg, keine Fixtures.

Usage und konservative Kosten werden bereits unmittelbar nach Antwortempfang
vor fachlicher Validierung in den begrenzten Bericht übernommen. Bei Ablehnung
bleibt der Kostenstatus ESTIMATE_UNVALIDATED_RESPONSE. Keine Rohantwort speichern.
Bei Erfolg enthält die Ausgabe nur geprüfte Codes/Referenzen und eine kompakte
Projektion der bestätigten öffentlichen Fakten und deterministischen Berechnungen
für die deutsche Zusammenfassung. Der bestehende 8192-Byte-Ergebnisrahmen bleibt.

Konfigurations-Hash/Identität werden nach Möglichkeit auch nach Modellfehlern
serverintern unverändert nachgeprüft. Kein neuer UID-/Rechte-Diagnoseweg und keine
Änderung der bewährten Schutz-/Schlüsselzugriffsfunktionen. Finaler unabhängiger
DB-Readback erfolgt auch nach Validierungsfehler oder unklarem Remote-Ergebnis;
ein zusätzlicher Readbackfehler überschreibt den ersten Modellfehler nicht.
Keine DB-Schreiboperation, Rechteänderung, Secrets, Migration oder Deployment.
Keine Chrome-Prüfung gemäß ausdrücklicher auftragsspezifischer Ausnahme.

Fokussierte vorhandene Tests, erweitert um Run-2-Grenzen, getrennte exklusive
Reservierung, Kosteninformation bei Ablehnung, begrenzte Finanzprojektion und
Readback unter Erhalt des Erstfehlers. Die 41 Tests des Ausgangscommits sind
Grundlage; keine erneute allgemeine Fundamentals-Suite.

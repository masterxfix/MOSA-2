# Metadatenbasierter Konfigurationsschutz und einmaliger Pilot

Ausgangscommit f8737cc2eae312f1044bb78a16a2d760efa7cf2b. Der alte Fehler
CONFIG_PROTECTION war eine Sammelprüfung; daraus ist das konkrete abweichende
Merkmal nicht rekonstruierbar. Der neue einmalige Lauf ermittelt Metadaten vor
jedem Schlüsselzugriff. Er darf nur bei vollständiger sicherer Prüfung fortfahren.

Nur der exakt dokumentierte CONFIG-Pfad und seine bekannten Eltern werden geprüft,
keine Auflistung, keine Suche, kein Ausweichen. Eltern werden root-beginnend per
no-follow/dir_fd traversiert. Öffentliche Diagnose: numerischer Dateityp, UID/GID,
Modus numerisch und oktal, Symlinkflag, nlink, Prozess-UID/GID, Lesbarkeit sowie
Statuscodes. Eltern nur über Positionsnummer, keine privaten Pfade in Logs.
Index 0 ist root; weitere Indizes entsprechen den CONFIG-Pfadkomponenten bis
zum unmittelbaren Elternverzeichnis. legacy_deviations nennt die Bedingungen,
die von der alten FILE_TYPE/UID/GID/MODE-Prüfung abweichen; first_failure bezeichnet
die erste nach neuer Politik tatsächlich unsichere Eigenschaft.

Dateipolitik, identisch in Python/PHP:
- Prozessidentität weiterhin exakt UID 10317 / GID 1003, real und effektiv.
- Reguläre Datei, keine Symlinks, genau ein Hardlink.
- Owner exakt bestätigte Prozess-UID 10317, keine fremden Owner.
- Modus 0600 oder 0640, keine anderen/speziellen Rechte.
- Bei 0600 ist GID kein Zugangsträger und darf deshalb abweichen.
- Bei 0640 muss die leseberechtigte Gruppe die bestätigte Prozessgruppe 1003 sein.
- Eltern: echte Verzeichnisse ohne Symlink; Owner root oder Prozess-UID;
  keine Gruppen-/Welt-Schreibrechte oder speziellen Modebits.
- os.access und no-follow-open/fstat prüfen Lesbarkeit/Stabilität ohne Inhaltsread.

Erst danach wird der bestehende PHP-Arrayvertrag gelesen. PHP wiederholt dieselbe
Datei-/Elternpolitik, realpath-, Inode-/Mode-/Owner-/Größen-/Hardlink-Prüfung und
Inhalts-Hashbindung. Die atime-Änderung durch erlaubtes Lesen gilt nicht als
Inhaltsänderung. Keine chmod-/chown-/Gruppenänderung oder Schlüsselkopie.
Ein unsicherer Befund stoppt vor PHP-Key-Lesen, Marker und OpenAI-POST.
Die tatsächliche Eigenschaft wird erst durch den Live-Lauf nachgewiesen; sichere
Gruppenabweichungen werden nur bei den dort gemessenen passenden Bedingungen
akzeptiert. 0644 wird auch bei HTTP 403 nicht akzeptiert.

Neuer Workflow fundamentals-assessment-protection-once.yml mit Run/Attempt 1,
exaktem Main-Commit und MOSA2-DRONESHIELD-PROTECTION-AI-ONCE-20261101:<commit>.
Neue Markerkennung fundamentals-ai-droneshield-protection-20261101-01, Bindung
an Commit/ISIN/Input-Digest/Modell/Workflow unverändert. Frühere Workflows werden
nicht erneut gestartet. Höchstens ein POST; unklare Ergebnisse bleiben verbraucht.
Bestehender ResponsesAdapter/Transport, Daten-, Preis- und Kostenprüfung bleiben
unverändert. Offizielle Modellpreise wurden für diesen Auftrag erneut geprüft;
die bestehende maximal 24 Stunden gültige konservative Preisfreigabe gilt nur
innerhalb ihres Zeitfensters. Keine Modell- oder Budgetausweichlösung.

Offline: Metadatenmatrix sicher/unsicher, abweichende Gruppen, Symlink/Hardlink,
Python/PHP-Entscheidungsparität, kein Key-/Markerzugriff bei unsicherem Modus,
Fake-Erfolg mit genau einem POST, fehlende Konfiguration, Secret-Redaktion und
bestehende Einmal-/Kosten-/Referenztests. Keine Live-Diagnosewiederholung.
Bei sicherer Konfiguration folgt im selben genehmigten Lauf der bestehende Pilot.

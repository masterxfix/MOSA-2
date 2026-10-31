# Schema 6: explizite Software- und Releasekompatibilität

## Ergebnis und strikt getrennte Freigaben

| Aussage | Nachweis |
| --- | --- |
| Software unterstützt Schema 6 | JA, ausschließlich explizites Opt-in |
| Isolierte MySQL-8-Kompatibilität | PASS, MySQL 8.0.46 |
| Auf Dogado installiert | NEIN |
| 0005/0006 auf Dogado angewendet | NEIN |
| Collector, Scheduler oder produktiver Betrieb freigegeben | NEIN |

Einziger Actions-Lauf:
[41210299524](https://github.com/masterxfix/MOSA-2/actions/runs/41210299524),
Job [124563706097](https://github.com/masterxfix/MOSA-2/actions/runs/41210299524/job/124563706097).
Exakter geprüfter Kandidatencommit:
`3f925fa4290360c309279f48f6a9cb795dd726d8`.
Alle vier zusätzlichen Integrationsfälle PASS, Laufzeit der Tests 17 Sekunden.
Keine erneute Dogado-Verbindung, kein Backup/Restore und keine Wiederholung der
100.288-Observation-/Performance-Qualifikation aus 41205801735.

## Gemeinsamer exakter Vertrag

`CollectorSchema5\\selected` akzeptiert nun ausdrücklich 6 zusätzlich zu 4/5;
Standard bleibt 4, keine automatische Schemaerkennung und kein Fallback.
Die historischen Envelopes 3/4/5 bleiben unverändert. Envelope 6 verlangt genau
26 Tabellen, Ledger-Versionen 1–6, sechs Original-SQL-Hashes und sechs richtige
Migrationsschlüssel. Auch die Dateibytes aller sechs SQL-Artefakte werden für
Version 6 gegen die eingefrorenen Hashes geprüft. Keine Migration wurde geändert.

`schema5.php` delegiert Version 6 an die schmale Erweiterung `schema6.php`.
Der bisherige eingeschränkte Parser verarbeitet weiterhin Spalten, Indizes,
komposite FKs und CHECKs; lediglich 0006s auto-increment BIGINT-Spalten werden
zusätzlich erkannt. Nummerierte 0001/2/3-Artefakte werden byteidentisch in einem
temporären privaten Arbeitsverzeichnis bereitgestellt und wieder entfernt.
Keine zweite allgemeine Parser- oder Kursauswahllogik.

Der bestehende vollständige `Phase3K\\structure`-Checker prüft in beiden
Schema-6-Runtime-/Current-Pfaden alle alten und neuen Tabellen:
**26 Tabellen, 310 Spalten, 26 Primärschlüssel, 19 weitere Unique-Indizes,
64 weitere Indizes, 60 Foreign Keys und 62 CHECKs**.
Datentyp, Nullability, Default, Kollation, AUTO_INCREMENT-Spalten, SHOW CREATE,
Indexreihenfolge, FK-Ziele/-Regeln und kanonische vollständige CHECK-Ausdrücke
bleiben verbindlich. Unbekannte zusätzliche Tabellen oder Spalten scheitern.

Die fünf neuen Tabellen:
`m2_provider_fetches`, `m2_fundamental_metrics`, `m2_fundamental_units`,
`m2_fundamental_observations`, `m2_fundamental_current`.
Ihre fünf leeren Bestände sind im Test zulässig; kein Fundamentals-Seed installiert.

## Sperren und vorhandener Kursdatenweg

Ledger 5/6 und die unveränderten 0005-Initialanker sind gemeinsame Voraussetzungen
von vollständigem Snapshot und bounded Runtime-Prüfung. Der Collector-Job bleibt
deaktiviert/UNWIRED, das Modul Version 5 / LOCKED, Status IDLE, stop_latched=1,
unresolved=0. Keine aktive/vorherige Reservierung, kein pending asset, Token oder
Zyklus; cycles/days/requests leer. Version 6 darf diesen Bootstrap nicht lockern.

`acquisitionAllowed` erlaubt ausschließlich die bisherigen Versionen 3/4;
5 und 6 bleiben ausdrücklich gesperrt, unbekannte Versionen scheitern ebenfalls.
Der Integrationstest erreicht den tatsächlichen Runtime-Pfad mit einem
Provider-Tripwire: `schema6_collector_locked`, kein Commit, **0 Provideranfragen**.
Ein Schema-Opt-in erteilt weder Providerrechte noch Ausführungsfreigaben.
Alle vorhandenen execution_enabled-/rights_confirmed-Schalter bleiben unverändert.

Current-Planer, vorhandene Current-Transaktion, unabhängiger Readback und Replay
werden weiterverwendet. Auch bei Schema 6 benötigen deaktivierte Routen eine
ausdrückliche Projektionserlaubnis; ohne Erlaubnis scheitert der synthetische Test.
Die API-Dateien und die bestehende gemeinsame Quote-Selection sind unverändert.

## Isolierter MySQL-Nachweis

Ausschließlich der vorhandene bewachte GitHub-MySQL-8-Service über Loopback3307.
Die bestehende Migration5-Fixture erzeugt Schema 4 und fünf synthetische gültige
Marktkurs-/Observation-v2-Ketten. Dies sind bestehende synthetische Frankfurt-
Fixtures, kein erneuter Abruf oder eine Kopie privater Dogado-Tradegate-Daten.
Danach unveränderte 0005 samt gesperrtem Bootstrap/Ledger5 und unveränderte 0006
samt synthetischem Ledger6. Keine echte Datenbank oder Zugangskonfiguration.

Vier gezielte Integrationsfälle:
1. Übergang 4→5→6, sechs unveränderte SQL-Hashes, 26 Tabellen und Ledger 1–6.
   Fünf Current-/Observation-Reader-Ergebnisse vor/nach Erweiterung identisch;
   gemeinsame Provenanceprüfungen gültig. Current fünfmal UNCHANGED, neuer
   unabhängiger Readback PASS, Replay fünfmal UNCHANGED. Übrige alte Fakten
   unverändert, neue fünf Tabellen leer und Collector gesperrt.
2. Falsche Schema-/Tabellen-/Ledger-Kombinationen, fehlender Ledger6, falscher
   Schlüssel, falscher Hash und unbekannte Tabelle werden abgewiesen.
3. Aktivierter Job, entsperrtes Modul, fehlender Stop-Latch, unresolved/pending
   asset, laufender Zyklus oder bereits vorhandene Tagesaktivität werden abgewiesen.
4. Zusätzliche Fundamental-Spalte, fehlender neuer Index und beschädigte
   Current-Provenance werden abgewiesen; keine unzulässige Current-Änderung.

Offline: **31 unterschiedliche fokussierte Tests PASS**, einschließlich neuer
Schema-6-Fälle, bisheriger expliziter Versionswahl, Inventar-/Diagnose-Guards,
Current-Metadaten und zehn Quote-Selection-Regressionen. Fünf PHP-Syntaxprüfungen
PASS. Zwei im geschlossenen Paketcheck gefundene fehlende Abhängigkeitskanten
wurden vollständig ergänzt und fokussiert nachgeprüft; keine Guard-Abschwächung.

## Separater reproduzierbarer Releasevertrag

Neues explizites Profil `schema6` in `collector_release.py`, eigener Vertrag
`collector_release_contract_schema6_v1.json`, **61 vollständig gepinnte Dateien**.
Defaultprofil und historische 33-Dateien-Vertragsdatei unverändert; auch die
historische Schema-5-Vertragsdatei wird nicht umgeschrieben.
Das neue Profil unterstützt die expliziten Versionen 4/5/6, Default 4,
execution_enabled=false, upload_enabled=false. Keine neue ausführende Entry-Route.

Geschlossener Abhängigkeitsgraph einschließlich aller sechs Originalmigrationen,
gemeinsamer Parser-/Current-/Reader-Dateien und historischer Scope-Abhängigkeit.
Jeder Blob ist fest gebunden; Build/Verify verlangen außerdem einen vollständigen
Git-Commit und byteidentische Arbeitsdateien. Manifest enthält Commit, Vertrags-
SHA-256 und sämtliche Dateihashes. Falscher Commit, fehlende Dateien, unbekannte
Abhängigkeiten oder geänderte Bytes bleiben Fehler. Keine Secrets, Tests,
Remote-/Deploy-Programme im Paket.

Am geprüften Kandidaten erfolgreich gebildet und unabhängig mit dem vorhandenen
Verifier bestätigt:
- Payload: **395937 Bytes**, 61 Dateien.
- Archiv-SHA-256: `67249d72fd21770936a36f44874f5439f888b7b9c9d9e0ffd46df990ca5cb91d`.
- Manifest-SHA-256: `2a0d482c40573de2292719b4e6b98d67e26a42c9df2b1a5e33dcb1591073cf98`.
- [Manifest-Artefakt](https://github.com/masterxfix/MOSA-2/actions/runs/41210299524/artifacts/13045498769),
  sieben Tage bis 07.11.2026; ZIP-SHA-256
  `550129b5829a41d14cbe322d7bf6742844d3a30487ca29f0fe4a0cae1cfd7a3c`.

Diese Hashes gelten exakt für den genannten Kandidatencommit. Der Abschlusscommit
auf main enthält dieselben geprüften ausführbaren Dateien und zusätzlichen
Ergebnistext; ein späteres Installationspaket ist erneut an dessen ausdrücklich
freigegebenen Vollcommit zu binden. Keine Installation oder Deployment ausgelöst.
Die bestehenden gepinnten Laufzeit-/Pfadprüfungen und deaktivierte Beispielkonfiguration
bleiben bestehen; CI-PHP ist kein neuer Nachweis der Dogado-Laufzeit.

## Vor Dogado-Apply weiterhin offen

Der echte Bestand bleibt beim zuletzt separat bestätigten Schema 4:
[Inventar 41208789503](https://github.com/masterxfix/MOSA-2/actions/runs/41208789503).
Die Softwarequalifikation ersetzt keine Live-Sicherung oder Apply-Freigabe.

Weiter nötig: kontrollierte durchgehende MOSA-2-Schreib-/DDL-Ruhe, geprüfter
schema-begrenzter Live-Backup-Weg mit Ressourcen/privater Schlüsselverwahrung,
echtes verschlüsseltes Vollbackup und unabhängiger vollständiger isolierter
Restore; ausdrücklich freigegebene private Installation des exakt gebundenen
Schema-6-Pakets mit frischem Bestandsvergleich, separate Migrationserlaubnis und
unabhängiger Postcheck nach 0005/0006. Collector-/Provider-/Scheduler-Freigaben
bleiben davon getrennt. Keine neuen Secrets oder Benutzer erforderlich behauptet.

MySQL-DDL ist über mehrere Statements nicht atomar. Bei Teilfehlern/unklaren
Bestätigungen weiterhin STOP ohne Retry, Reparatur oder behaupteten Rollback.
Der bestehende Applyplan in SCHEMA6_DOGADO_PREPARE.md bleibt verbindlich.

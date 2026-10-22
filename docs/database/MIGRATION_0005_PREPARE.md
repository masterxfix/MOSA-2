# Migration 0005: PREPARE, keine Dogado-Anwendung

Ausgangsrevision: `bc1f1faaff17d40eaa1362caf97d3395fe069009`.
Bestehender isolierter Persistenznachweis: Actions `39741590684` (268 Tests).
Der neue manuelle Workflow-Scope `migration5` prueft den jeweiligen exakten
`expected_commit`. Ein freigegebener APPLY-Executor ist **nicht** Bestandteil
dieses Auftrags. Migrationen 0001 bis 0005 bleiben byteidentisch.

## Exakter Vertrag

0005 SHA-256: `2521552c548370806bc311798f12be39f16b102733aeb74ac9c01337e7e46333`.
Vier InnoDB-Tabellen ergaenzen Schema 4 (17 Tabellen) zu Schema 5 (21 Tabellen).
Es gibt vier Primaerschluessel, drei weitere Unique-Vertraege und neun FKs.
Die impliziten Kindindizes werden ebenfalls exakt geprueft. FKs der neuen
Tabellen haben den explizit erwarteten MySQL-Default NO ACTION; historische
RESTRICT-FKs behalten ihren bisherigen Vertrag. CHECKs, Typen, Nullability,
Defaults, Kollationen, JSON-Auswahl und Datums-/Zeitformate werden mit dem
vorhandenen Metadatenpruefer verglichen. Der eingeschraenkte Ausdrucksparser
unterstuetzt zusaetzlich BETWEEN, JSON_TYPE/JSON_LENGTH und ASCII-Statusliterale;
Operanden, Reihenfolge, Grenzwerte und Literalbytes bleiben bedeutend.

DATETIME(6) enthaelt keine Zeitzone; der spaetere Executor muss UTC setzen und
belegen. Hash-/UUID-/ISIN-Inhalte der JSON-Auswahl sind zusaetzliche bestehende
Runtime-Vertraege, keine von der DDL allein garantierten Eigenschaften.

Nach Bootstrap: genau ein Providerzustand IDLE/INITIAL_LOCK, stop_latched=1,
unresolved=0, keine aktiven/vorherigen Zyklen, kein Operationstoken; alle drei
anderen Collector-Tabellen leer. Job `collector_reservations_v1` ist deaktiviert
und UNWIRED; Modul `collector_reservations` ist Version 5 / LOCKED.
Keine Betriebsfreigabe, keine Rechtebestaetigung, kein Scheduler.

0005 schreibt **keinen** Schema-Ledger-Eintrag. Ein spaeterer freigegebener
Executor muss nach den fuenf DDL-Schritten die drei unveraenderten Bootstrap-
Statements plus Ledger 5 (`0005_collector_reservations`, exakter SQL-SHA) in einer
eigenen atomaren DML-Transaktion bestaetigen. Die DDL davor ist nicht rollbackbar.

## Kompatibilitaet und verbindliche Blocker

`schema_contract.php` erhaelt die exakten Versionen 3 und 4 und ergaenzt Version 5
nur bei ausdruecklichem Opt-in. Globale Bestandspruefung und Runtime verwenden
diesen gemeinsamen Vertrag; zusaetzliche Tabellen oder falsche Ledger bleiben
Fehler. `schema5.php` erweitert den vorhandenen strukturellen Schema-4-Pruefer.
Kein Wildcard-Tabellensatz und kein Ignorieren unbekannter Migrationen.

Der bestehende Current-Webleser und die Observation-Anzeige brauchen keinen
globalen Tabellensatz; ihre Daten-/Provenancepruefungen bleiben unveraendert.
Der historische Current-Refresh bleibt bewusst auf CONTRACT schema_version=4.
Die installierte Collector-Version und ihre bisherige Schema-4-Konfiguration werden in
diesem Auftrag **nicht** geaendert; ihre Schema-5-Kompatibilitaet ist nicht nachgewiesen.
Sie koennen nach 0005 blockieren. Vor einer
Dogado-Anwendung sind daher ein separat gepruefter Kompatibilitaets-/Releaseweg
und die Entscheidung ueber den weiterhin gesperrten Current-Refresh verbindlich.
Das neue Python-Persistenzmodul bleibt rein injiziert/synthetisch verdrahtet.

Weitere zwingende Blocker: gesonderte exakte Migrationsfreigabe; frischer
identischer Ausgangsnachweis; gepruefte Sicherung und isolierter Restore;
vollstaendige Metadaten-Sichtbarkeit fuer Trigger/Routinen/Events. SELECT-only
kann deren Abwesenheit nicht abschliessend beweisen. Sichtbare Objekte blockieren;
ein sichtbarer Nullzaehler ersetzt keinen Berechtigungsnachweis.
Providerrechte, beide execution_enabled=false und rights_confirmed=false bleiben
unveraendert. Auch ein spaeterer erfolgreicher Schemawechsel erlaubt keinen Start.

## Ein READ-ONLY-Preflight und geschuetzter Plan

`collector-release-offline.yml`, Scope migration5, fuehrt zunaechst alle
isolierten Tests aus. Nur auf main mit read_preflight=true folgt genau ein
separater Job ueber vorhandene SSH-Secrets und den bestehenden SELECT-Benutzer.
Keine Writer-DB-Secrets, keine Uploads, kein Deployment. Dieselbe vorhandene
Identitaets-, MySQL-8.0-, Grant- und READ-ONLY-Transaktionspruefung laeuft vor
Metadaten oder Current. Der Callback benutzt diese eine Verbindung, keine zweite
Anbindung. SQL und Rueckgaben sind begrenzt; Fehlertexte bleiben privat.

Die sechs Metadatenabfragen stammen direkt aus dem bestehenden Schema-Pruefer.
Die private Aufnahme wird lokal in diesen unveraenderten Pruefpfad eingespielt.
Zlib/gzencode ist Voraussetzung und wird vor der DB-Verbindung geprueft.
Gzip/Base64 haelt das bestehende 64-KiB-SSH-Limit ein; die entpackten Metadaten
sind auf 2 MB begrenzt und mit Laenge/SHA-256 verifiziert. Keine Erhoehung des
Transportlimits. Der isolierte Test prueft den vollstaendigen Fuenf-Aktien-Wire.
Geprueft werden exakte Struktur, Ledger/Checksummen, vier fehlende 0005-Objekte,
freie Job-/Modulanker und sichtbare Namenskonflikte. Die vorhandene begrenzte
Fuenf-Aktien-Current-Aufnahme wird mit dem urspruenglichen verschluesselten Plan
aus PREPARE 39634298612 verglichen. Fehlt dieses Artefakt, wird fehlender
historischer Nachweis gemeldet und blockiert; kein lokaler Anhang wird erwartet.

Der Lauf erzeugt einen **nicht ausfuehrbaren**, exakt an GITHUB_SHA, Laufkennung,
SQL-SHA, Metadaten-/Ledger-Fingerprint, Current-Nachweis, acht Schritt-Hashes,
Zielstruktur, Ledger 5 und Sperrstatus gebundenen Plan. Er ist mit dem bestehenden
SSH-Secret ueber den vorhandenen AES-GCM/HKDF-Evidenzweg verschluesselt und als
`migration5-plan-encrypted-prepare-only` sieben Tage in Actions gespeichert.
Entschluesselung folgt `deploy_test_sftp.persist_backup`: HKDF-SHA256/32 Byte,
Salt/Nonce im Envelope, Info und AAD `mosa2-testsite-web-backup-v1`; `files` enthaelt
Base64 `migration5-plan.json`. Es wird kein Passwort/Secret neu eingerichtet.
Oeffentlich erscheinen nur Status, SQL-/Plan-SHA, Version und begrenzte Codes.

## Teilzustaende: ausschliesslich lesen und STOP

| Bestaetigter letzter Schritt | Rein lesend erkennbarer Zustand | Konsequenz |
| --- | --- | --- |
| keiner | Exakt Schema 4, Ledger 1-4, keine vier Tabellen/Anker | Nur PREPARE moeglich |
| DDL 1 | state vorhanden; kein cycles/days/requests | PARTIAL_OR_CONFLICT |
| DDL 2 | state + cycles, state noch ohne active/last-FKs | PARTIAL_OR_CONFLICT |
| DDL 3 | state + cycles, beide zusaetzlichen FKs vorhanden | PARTIAL_OR_CONFLICT |
| DDL 4 | zusaetzlich days, requests fehlt | PARTIAL_OR_CONFLICT |
| DDL 5 | alle vier Tabellen, keine Anker/Ledger 5 | PARTIAL_OR_CONFLICT |
| Bootstrap 6/7/8 einzeln sichtbar | Job-/Modul-/Providerzeile nur teilweise vorhanden | PARTIAL_OR_CONFLICT |
| Bootstrap + Ledger noch unbestaetigt | Metadaten, drei Anker, Ledger getrennt erfassen | Ergebnis unbekannt; STOP |
| alles bestaetigt | Exakt Schema 5, Ledger 1-5, Initialsperren | SCHEMA5_LOCKED_COMPLETE, erneute Anwendung gesperrt |
| beliebige andere Kombination | Tabellenmaske, Anker, Ledger und vollstaendige Metadaten vergleichen | UNKNOWN_OR_DRIFT bzw. PARTIAL_OR_CONFLICT |

Alle Kombinationen unbekannter Objekte, falscher Hashes, falscher Anker und
fehlender oder vorgezogener Ledger werden geschlossen abgewiesen. Die Maske ist
kein Resume-Punkt. Kein Retry, kein automatisches Reparieren, DROP oder RESET.
Nach Verbindungsabbruch niemals einen moeglichen DDL-/DML-Commit als Rollback
melden. Erst separater READ-ONLY-Nachweis, dann neuer ausdruecklicher Auftrag.

## Spaetere Sicherung, Abschluss und Rueckfall

Vor jeder spaeteren Anwendung: Betrieb weiterhin gesperrt, bestehende Writer
nachweislich ruhigstellen; frischen globalen Schema-4-Fingerprint und separate
Zeilenhashes aller 17 Tabellen sichern. Vollstaendige logische Datensicherung
inklusive Ledger, jobs, module_state, Original-Observations und Current sowie
SHOW CREATE und AUTO_INCREMENT-Metadaten benoetigt. Konsistenz muss ueber den
gesamten Sicherungszeitpunkt gewaehrleistet sein, nicht aus zwei losen Dumps
behauptet werden. Sicherungs-/DDL-Drift muss unmittelbar vor Ausfuehrung blockieren.

Kein Klartext-Dump im Webroot, im Repository oder in Actions-Logs. Geschuetzte
Aufbewahrung ausserhalb aller Webroots, bestehender verschluesselter Evidenzweg,
SHA-256 ueber unveraenderten Dump und separates Manifest; Berechtigungen,
Aufbewahrung und Ablauf vorab festlegen. Wiederherstellbarkeit erst nach einem
vollstaendigen Restore auf separater isolierter Instanz mit unabhaengigem
Schema-/Ledger-/Zeilenhashvergleich bestaetigen. Heute findet keine Live-Sicherung
und kein Restore statt; dieser Nachweis bleibt vor APPLY offen.

Spaeterer Executor: vorhandener nichtinteraktiver Zugang, expliziter Einmalclaim,
exklusiver Migrations-/Current-Schutz, frischer Bestandsvergleich, unveraenderter
SQL-Hash, genau fuenf DDLs, anschliessend gesperrter Bootstrap + Ledger atomar.
Danach neue unabhaengige READ-ONLY-Verbindung: exakte Schema-5-Struktur, alle
Constraints, Ledger 1-5, alte Zeilen ausser den drei geplanten Anker-/Ledger-
Ergaenzungen identisch, gueltige Current-Provenance, unveraenderte Routen und
Observation-/Bars-Bestaende. Erneute Anwendung muss blockieren.

Rueckfall ist **kein** versprochener MySQL-DDL-Rollback. Bei Teilzustand bleibt
alles gesperrt; Sicherung zuerst isoliert pruefen, dann fachlich zwischen einem
separat genehmigten gezielten Reparaturplan und einem geprueften Restore auf eine
isolierte Ersatzdatenbank entscheiden. Keine automatische produktive Loeschung
oder Umschaltung. Auch Recovery erfordert einen gesonderten Auftrag.

## Nachweisgrenzen

Die synthetischen MySQL-8-Tests laufen ausschliesslich im GitHub-Service ueber
die bestehende Guard-Factory (Loopback/Port, MySQL 8, Service-Datenbank). Nur dort
sind DDL, DML und Fixture-Neuaufbau erlaubt. Sie pruefen unveraenderte 0005,
Schema 4/5, alle neun FKs und sieben Unique-Vertraege, CHECKs, jeden der acht
Abbruchpunkte, Konflikte, Readback, Replay-Sperre, die bisherigen Runtime-/Current-
Vertraege sowie identische fuenf Current-/Observation-Anzeigen und Provenance.
Dies ist weder ein Dogado-Migrations- noch ein Wiederherstellungsnachweis.

Die tatsaechlichen Actions-Ergebnisse und die einmalige private Bestandspruefung
werden im Abschlussbericht mit den exakten Lauf-/Commitlinks ausgewiesen.

## Backup-Berechtigungsnachweis (22.10.2026)

Eigenstaendiger Pruefmodus `backup-permissions` im vorhandenen manuellen
Actions-Workflow. Bestehender gepinnter SSH-Tunnel und unveraenderte
`Phase2\connection` pruefen das bestehende DB-Konto, Testschema, Port und
MySQL-Version. Eine nachgewiesene READ-ONLY-Transaktion liest ausschliesslich
Grants und begrenzte Trigger-/Routine-/Event-Metadaten samt SHOW CREATE.
Keine Geschaeftsdaten, Sperren, Rechteaenderungen, Sicherung oder Migration.
Roh-Grants, Objektidentitaeten und Definitionen werden nicht protokolliert.

Null sichtbare Objekte gelten nur zusammen mit schemaweiten Enumerationsrechten
als vollstaendig; vorhandene Definitionen muessen zusaetzlich lesbar sein.
Unaufgeloeste Rollen oder unerkannte Grants brechen den Nachweis ab.
Das vorhandene Backup-Verfahren haelt einen globalen Read-Lock und prueft
globale RELOAD- und SELECT-Rechte; schemaweites LOCK TABLES ersetzt RELOAD nicht.
Routine-Enumerationsrechte allein garantieren keine fremden Definitionen.
Referenzen: [MySQL Routine-Rechte](https://dev.mysql.com/doc/refman/8.0/en/stored-routines-privileges.html),
[MySQL FLUSH](https://dev.mysql.com/doc/refman/8.0/en/flush.html).

Ergebnis des exakt einmaligen Live-Prueflaufs: ausstehend.

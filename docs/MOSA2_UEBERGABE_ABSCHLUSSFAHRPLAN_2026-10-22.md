# MOSA 2 – Übergabe und Abschlussfahrplan (22.10.2026)

**Zweck:** Den nächsten Chat ohne neue, kostspielige Grundsatz- und Testschleifen fortsetzen. Grundlage sind der tatsächlich überprüfte GitHub-/Testsite-Stand und die bestehenden Projektnormen aus [AGENTS.md](../AGENTS.md). **Dies ist keine Migrations-, Collector-, Design- oder Backup-Ausführungsfreigabe.**

## Nutzerfeedback und Ziel

- Der Nutzer bewertet den heutigen Arbeitstag ausdrücklich als **ohne ausreichenden nutzbaren Fortschritt gegenüber gestern**. Weitere viele Codex-Tokens, CI-Läufe, Vorbereitungen und technische Teilerfolge **ohne nutzbares Ergebnis auf der Seite** sind nicht akzeptabel.
- Ziel des nächsten Abschnitts: **die blockierte Datenbank-/Collector-Vorbereitung geordnet abschließen** und anschließend **sichtbar aktuelle, nachweislich gespeicherte Marktdaten** anbieten – ohne neue Sonderarchitektur.
- Nicht ungefragt Farben, Typografie, Logos oder Design wechseln. Die ursprüngliche dunkelblaue Gestaltung wurde wiederhergestellt; Änderungen erfordern die ausdrückliche, konkrete Nutzerfreigabe gemäß `AGENTS.md`.
- Die nächste Bearbeitung muss einen **eindeutig überprüfbaren Meilenstein** liefern, nicht eine weitere breite Bestandsaufnahme.

## Verifizierter Iststand (22.10.2026)

| Bereich | Tatsächlicher Stand und Beleg |
| --- | --- |
| Repository | `masterxfix/MOSA-2`, `main` bei [`229e049`](https://github.com/masterxfix/MOSA-2/commit/229e049c939be9a690c5c7aaeb03c356b64b4323) vor dieser Übergabe |
| Testwebseite | [mosa2-test.scharwerk.de](https://mosa2-test.scharwerk.de/) online; ursprüngliche Blau-/Schriftgestaltung und neues Layout deployed, drei Dateien samt SHA-256 geprüft ([Actions 39782036683](https://github.com/masterxfix/MOSA-2/actions/runs/39782036683)). |
| Webdaten | Fünf bestätigte Current-Aktien: PNE, Carl Zeiss Meditec, DroneShield, BYD, Ubtech Robotics. Current- und Observation-Webleser zeigen gespeicherte Daten einschließlich Quelle/Provenienz; die Kurse sind **veraltet**, keine automatische Aktualisierung. |
| Dogado-Datenbank | **Schema 4**, 17 Tabellen, Ledger 1–4; Migration `0005` **nicht** angewendet. |
| Schema 5 | `0005` sowie gesperrter 53-Dateien-Release-Kandidat und explizite Schema-4/5-Kompatibilität sind **offline/synthetisch** nachgewiesen ([Schema-5-Vertrag](database/SCHEMA5_RELEASE_CANDIDATE.md)), **nicht auf Dogado installiert**. |
| Backup-Software | Verschlüsseltes synthetisches Backup/Restore inkl. 17 Tabellen, fünf Current-Objekten und Provenienz **335/335 Regressionen PASS** ([Actions 39765129791](https://github.com/masterxfix/MOSA-2/actions/runs/39765129791)); das ist **kein echter Dogado-Backup-Nachweis**. |
| Schema-Export ohne globale Rechte | Einmaliger synthetischer `mysqldump --single-transaction` ohne globale Rechte inkl. isoliertem Restore PASS ([Actions 39768976953](https://github.com/masterxfix/MOSA-2/actions/runs/39768976953)). Nur bei nachweislich routinenfreiem Bestand und gesicherter DDL-/Schreibruhe geeignet. |
| Berechtigungen | Dogado-Konto: Schema-Rechte einschließlich SELECT/SHOW VIEW/TRIGGER/EVENT/LOCK TABLES; kein globales RELOAD/FLUSH_TABLES, kein globales SELECT und **kein PROCESS**. Objekte aktuell keine Trigger/Routinen/Events ([Actions 39767648960](https://github.com/masterxfix/MOSA-2/actions/runs/39767648960), [39785579068](https://github.com/masterxfix/MOSA-2/actions/runs/39785579068)). |
| Letzter echter Backup-Versuch | **Nicht gestartet**: Live-Precheck konnte fremde Sitzungen bzw. DDL-Ruhe mit bestehenden Rechten nicht vollständig nachweisen. Kein echter Dump, kein Restore, kein Backup-Artefakt. Prüf-Entwurf [`58cbbd4`](https://github.com/masterxfix/MOSA-2/commit/58cbbd4c623cf723a95b6f978be04238b2b985e4) **nicht** auf `main`. |
| Zusätzlicher Fehlversuch | Synthetischer Schema-READ-Lock-Test [39774956523](https://github.com/masterxfix/MOSA-2/actions/runs/39774956523) scheiterte an `localhost`-Testkonto versus Docker-TCP-Quellhost. Unfertiger Entwurf [`370b14b`](https://github.com/masterxfix/MOSA-2/commit/370b14b7729510ab9b27391bd8ccd6309afc9cb8) **nicht** übernehmen. |
| Regelbetrieb | Beide `execution_enabled=false`; `rights_confirmed=false`, dokumentiertes Providerlimit und MOSA-Gesamtbaseline fehlen. **Kein Scheduler, keine automatischen Provideraufrufe oder Collector-Freigabe.** |

**Kernproblem:** Zusätzliche Testläufe können fehlende Hosting-Garantien nicht ersetzen. Insbesondere beweist selbst die Erteilung von `PROCESS` **keine dauerhafte DDL-Ruhe**. Den nicht möglichen Beweis nicht erneut mit immer neuen Diagnosen erzwingen.

## Verbindlicher Abschlussfahrplan mit Stop-Gates

### 1. Hosting-Entscheidung statt weiterer Tests

**Ein nächster eng begrenzter Auftrag**, ohne Codeänderung und zunächst ohne CI:

- Über den **bereits vorhandenen** Dogado-/Plesk-Zugang bzw. Support klären, ob Dogado **ein konsistentes Backup der isolierten Datenbank `h29077_mosa2_test`** bereitstellen kann, das vollständig exportierbar und auf unabhängiger MySQL-8-Instanz wiederherstellbar ist. Explizit nach **Tabellen, Daten, Ledger, DDL, Metadaten, Snapshot-/DDL-Schutz, Abrufmöglichkeit und Datenbank-Scope** fragen.
- Alternativ verbindliche **exklusive DDL-/Schreibruhe während eines schema-begrenzten Exports** inklusive unbekannter fremder Schreiber durch Betreiber-/Wartungsfenster klären. Eigene `SHOW PROCESSLIST`-Stichproben und `PROCESS` sind **kein gleichwertiger Ersatz**.
- Nur vorhandene nicht-interaktive Zugänge; keine überraschenden Passwörter. Falls ein unumgänglicher Nutzerzugriff nötig wäre: **vorab** gemäß AGENTS.md ankündigen.
- **Ergebnis:** eine dokumentierte **JA/NEIN-Entscheidung samt konkretem, technisch zulässigem Backup-Weg**. Bei NEIN: Backup/Migration als **extern blockiert** markieren und nicht denselben Nachweis erneut entwickeln oder testen.

### 2. Einmaliger echter Backup- und Restore-Nachweis (nur nach JA)

- Separat für **genau diesen echten Export** freigeben lassen; vorab frischen Schema-4-, Objekt- und Current-/Observation-Ausgangsnachweis erstellen. Benötigten Speicher/Client und begrenzte Laufzeit prüfen.
- Existierenden, fachlich passenden Exportweg benutzen; **keine Erweiterung des synthetischen CI-Executors um ungeprüften Dogado-Zugriff**. Private verschlüsselte Aufbewahrung **außerhalb Webroots**, keine Klartextdaten in Logs, öffentlichem Repository oder Artefakten. Schlüsselzugriff und Löschfrist konkret nachweisen.
- Ein Backup **einmalig** durchführen und auf isolierter MySQL-8-Instanz mit den bereits bewiesenen **vollständigen** Struktur-, Ledger-, Datensatz- und fünf-Aktien-Provenienzprüfungen wiederherstellen.
- **Ergebnis:** `REAL_SCHEMA4_BACKUP_RESTORE_PASS` nur bei vollständiger Gleichheit. Bei nicht gesichertem Ergebnis **STOP**, keine automatischen Wiederholungen.

### 3. Schema 5 kontrolliert abschließen (nur nach echtem PASS)

- 53-Dateien-Schema-5-Kandidat mit vorhandener Prüflogik gegen **Schema 4** qualifizieren; Client-/PHP-Pins, private Installationslage und alte Consumer berücksichtigen. Collector weiterhin **gesperrt**.
- **Vor Migration eine gesonderte konkrete Nutzerfreigabe einholen.** Exakten `0005`-Hash und frische Datenbank-Fingerprints vergleichen, konkurrierende Schreiber kontrolliert stoppen, DDL und Bootstrap/Ledger ausschließlich nach [Migration-0005-Vertrag](database/MIGRATION_0005_PREPARE.md) ausführen.
- Wegen MySQL-DDL-Autocommit **keinen automatischen Rollback oder Resume behaupten**. Bei unbekanntem/partiellem Zustand stoppen und separat lesend klassifizieren.
- **Ergebnis:** Dogado hat **exakt Schema 5 (21 Tabellen), Ledger 1–5, drei gesperrte Bootstrap-Anker, unveränderte fünf Current-Datensätze/Observations**, Website lesbar, keine Collector-Aktivierung.

### 4. Sichtbare Funktion und späterer Regelbetrieb getrennt behandeln

- Nach dem Schemaabschluss einen **separat freigegebenen, kontrollierten manuellen Collector-Lauf** für bereits qualifizierte Aktien nur dann durchführen, wenn dafür auch die tatsächlichen **Provider-Nutzungsrechte** geklärt sind. Erfolg heißt: **neue Observation mit überprüfbarer ID/Zeit/Quelle in der bestehenden Marktdatenseite sichtbar**. Für eine neue Current-Schreibaktion gelten gesonderte bestehende Freigabeverträge; alte einmalige Current-Freigabe ist verbraucht und darf nicht wiederverwendet werden.
- Erst danach die Lastgrenzen und das Zusammenspiel mit dem **unveränderten MOSA** klären. **Ohne bestätigte Providerrechte und dokumentierte MOSA-Gesamtlast keine Automatik, kein 60-Sekunden-Takt und kein Entsperren.**
- **Ergebnis:** Funktionaler, sichtbarer Fortschritt; Automatik nur bei späterer eigener Freigabe.

## Kosten-, Umfangs- und Abschlussdisziplin

- **Keine** erneuten synthetischen Vollregressionen für unveränderte Komponenten, kein neuer Backup-Framework- oder Sperrtest ohne konkret nachgewiesene Lücke. Pro eng begrenztem Auftrag möglichst **0–1 GitHub-Actions-Lauf**, höchstens drei nach AGENTS.md und **keine automatische Wiederholung**.
- Jeden Schritt nur anhand **eines klaren PASS/BLOCKED-Ergebnisses mit Beleg** abschließen; technische Actions-`success`-Anzeige nicht als Erfolg eines blockierten Fachziels darstellen.
- **Keine Änderung der Website-Farben, Schriftarten, Markenmerkmale, APIs oder Funktionen** außerhalb des ausdrücklich freigegebenen Auftrags. `masterxfix/fixlab` bleibt unverändert.
- Bei externem Backup-Blocker nicht weitere Wochen in denselben Nachweis investieren: **Schema 4 unverändert nutzbar lassen** und nur davon unabhängige, freigegebene Arbeit verfolgen.

## Nächster Chat – erster Arbeitsauftrag

1. `AGENTS.md`, **dieses Dokument** und nur die konkret verlinkten Nachweise lesen; GitHub-`main` frisch überprüfen.
2. **Nicht** sofort neuen CI-, Migrations-, Backup- oder Designauftrag starten.
3. **Einzige erste Aufgabe:** die **Dogado-Backup-/Wartungsoption verbindlich klären** (Schritt 1); Ergebnis **JA/NEIN samt Begründung**. Erst anschließend den einzigen erforderlichen nächsten technischen Schritt festlegen.
4. Die Nutzerbewertung des bisherigen Ablaufs respektieren: **nachweisbarer Nutzen vor weiterer Vorbereitung**, keinen weiteren unbestimmten Fahrplan und keine neuen Schleifen.

**Keine Maßnahme dieses Dokuments gilt als bereits durchgeführt oder genehmigt.**

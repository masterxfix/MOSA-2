# Phase 3O – kontrollierter Observation-v2-Writer-Test

**Status: Phase 3O live erfolgreich; echter Writer, vier Unitpfade und zwei
unabhängige Post-Readbacks bestätigt, Cleanup abgeschlossen. Lokale Regression
374/375 (nur bekanntes Windows-budget_not_private). Abschlusscommit und exakter
Linux-Nachweis werden in Issue #31 dokumentiert. Frühere Stopps bleiben erhalten.**
Start exakt `7bff257175a177ecee3554e70fcf9fb6f60b0cf4`.
Die ausdrückliche Freigabe für ausschließlich synthetische Testtransaktionen
mit vollständigem Rollback und unabhängigem Readback steht in
[Issue #31](https://github.com/masterxfix/MOSA-2/issues/31#issuecomment-6284703837).
Kein B8, echte neue Marktdaten, Current-/Bars-Write, Schema-/Ledgeränderung
oder Produktionsdeploy freigegeben.

## Zwingende Runtimegrenze vor DB und Passwort

Der exakte unveränderte Phase-3N-Writer bleibt einzige fachliche Wahrheit.
`scripts/phase3o/live_plan.py` importiert ihn, lädt seinen qualifizierten
Unitkatalog und übergibt Route-/Observation-/Existing-Snapshots an WriterPlanner.
Der Wrapper hat keine eigene Kanonisierung, Hashbildung oder DB-Funktion.
Er transportiert rohe Bytes durch explizite Base64-Tags; eine Spaltensequenz
wird im JSON-Transport als Array dargestellt. Numerische Fachwerte bleiben
unverändert. Credentials sind kein zulässiges Requestfeld.

`scripts/phase3o/runtime_probe.php` ist ausschließlich ein privater CLI-Probe-
Starter, kein DB-Executor und kein HTTP-Gateway. Er ruft den Python-Wrapper mit
festen synthetischen Inputs auf und vergleicht dessen vollständige Antwort mit
lokalen Golden-Plänen. Nur im Kindprozess wird der bereits verwendete PHP-CLI-
Pfad für den bestehenden Phase-3N-Valueadapter ausgewählt. Keine Installation,
Hostingkonfiguration oder Erweiterungsberechtigung wird verändert.

Bei einem nicht ausführbaren exakten Laufweg gilt **RUNTIME_GAP**, sofortiger
Stopp vor DB/Passwort. Keine alternative Writerlogik oder Runtimeinstallation.
Ein Probeversuch wird im privaten Bericht festgehalten; kein automatischer Retry.

## Offlineprüfung des Runtime-/Transport-Gates im ursprünglichen Lauf

Vier synthetische Fälle werden aus dem normativen Manifest erzeugt: EUR, GBP,
POINT und GBX. Feste Testzeitpunkte, fester synthetischer Preis und erfundene
IDs; keine realen Marktwerte, Provider, Ticker oder ISINs. Die IDs dienen nur
dieser credentialfreien Runtimeprüfung und werden niemals als DB-IDs ausgegeben.
Eine spätere Testtransaktion müsste ausschließlich tatsächlich generierte IDs
verwenden. Die Beispielwerte sind keine vorbereitete SQL-Insertdatei.

Phase-3N-Tests 27/27 unverändert bestanden. Neue Gate-Tests 6/6 nach Korrektur
zweier Testfehler: Tuple-/JSON-Array-Grenze explizit vergleichen und isolierte
Kopie für den in-memory Konfliktsnapshot verwenden. Geprüft: direkte Parität
mit dem tatsächlichen Writer, deterministischer Stdio-Aufruf, 32 rohe Bytes,
18 kanonische Felder, 21 DB-Planfelder, Format 2, gebundene Units/Routes,
Duplicate/Conflict-Transport, Requestbegrenzung und fehlende DB-/SQL-Fähigkeit.
PHP-Lint erfolgreich. Der vollständige DB-Executor/Rollback-Testharness ist
damit ausdrücklich noch nicht implementiert oder qualifiziert.

## Transfer und ursprünglicher Runtime-Stopp

Secretfreies Paket mit elf Dateien privat außerhalb des Webroots übertragen.
Bestehende Quellen entsprechen den exakten Git-Objektbytes des Ausgangscommits;
neue Gatequellen und synthetische Fixtures sind lokal hashgebunden. Alle elf
Serverdateien wurden nach dem Schreiben per SHA-256 zurückgelesen und bestätigt.
Verzeichnis 0700, Dateien 0600. Transferbeweis ist kein DB-Funktionsnachweis.

Nach der vom Nutzer abgeschlossenen Zwei-Faktor-Anmeldung lief der private
CLI-Probe-Starter genau einmal. Der tatsächliche unveränderte Phase-3N-Writer
wurde importiert und über WriterPlanner aufgerufen; sein bestehender
Python→PHP-Subprozesspfad scheiterte mit:

```text
RUNTIME_GAP
TypeError: __init__() got an unexpected keyword argument 'capture_output'
```

Der Python-Prozess gab eine strukturierte RUNTIME_GAP-Antwort zurück, stderr war
leer. Python 3 ist vorhanden; seine vorhandene Subprozess-API unterstützt das
vom Phase-3N-Valueadapter verwendete Argument nicht. Damit sind weder vollständige
Writerpläne noch der weitere PHP-Adapterlauf für das Hosting bestätigt. Kein
Retry, kein Ersatzwriter, keine Installation oder Konfigurationsänderung.
0 DB-Verbindungen und 0 DB-Writes; kein Passwort angefordert oder verarbeitet.

## Sicherheitsbereinigung und Aussagegrenzen

Alle elf temporären Serverquellen nach Hashprüfung entfernt; Readback bestätigt
0 verbliebene Paketquellen. Private Runtime-, Versions-, Hash- und Cleanup-
Nachweise bleiben mit 0700/0600 erhalten. SHA-256 des privaten Runtimeberichts:
`4420ff148523f3c84dfd27e9373c403924c9fc4f8308de02ece01ed2a71e79f7`.
Kein Gateway, keine öffentliche Gatewayroute, Zugangskonfiguration, Session,
Cookie, Passwortreferenz, Lock oder Transportdatei angelegt. Deshalb ist
Gateway=404 kein ausgeführter Cleanupnachweis und wird nicht behauptet.
Homepagebytes unverändert; anonymer HTTPS-Aufruf liefert HTTP 401.

Der letzte bestätigte Phase-3M-Zustand (Units 4, Legacy/v1 unverändert,
Ledger v1/v2/v3, Current/Bars 0) bleibt historischer Ausgangsnachweis und ist
keine aktuelle Phase-3O-Messung. Graph, Inserts, canonical-/dedupe-Parität aus
DB-Readbacks, live-snapshot-basierte Rejects, Rollback und zwei unabhängige
Readbacks sind noch nicht ausgeführt.

## Lokale Abschlussprüfung

Gesammelte lokale Regression: **353/354 bestanden**; ausschließlich der bekannte
Windows-POSIX-Berechtigungstest `budget_not_private` scheitert. Die 27 Phase-3N-
und sechs neuen Phase-3O-Tests sind darin grün. `scripts/deploy_sftp.py validate`
bestätigt drei deploybare Webdateien; PHP-Lint des neuen CLI-Starters und
`git diff --check` erfolgreich. Kein SFTP-Deploy ausgeführt.
Die geschützten Phase-3N-/v1-/Unitmanifestquellen bleiben gegenüber dem exakten
Startcommit unverändert. Keine zusätzlichen DB-Tests nach dem Runtime-Stopp.

Kein Abschlusscommit/Push oder neuer Linux-Nachweis; diese sind nur nach
vollständigem Phase-3O-Live-Erfolg zulässig. Issue #31 bleibt offen. Keine
Abschlussbewertung für einen unvollständigen Auftrag. Phase 3P wird nicht begonnen.
Der Stopp ist in [Issue #31 dokumentiert](https://github.com/masterxfix/MOSA-2/issues/31#issuecomment-6285245995).

KI-Kontrollzentrum separat: Start regulär versucht, PROMPT_RECEIPT_MISSING;
Describe und Plan jeweils einmal ohne verfügbare native Turnzuordnung
abgewiesen. Keine IDs oder Ereignisse erfunden; Freigabe zur fachlichen
Fortsetzung trotz Erfassungslücke beachtet.

## Autorisierte Fortsetzung nach dem Runtime-Stopp

Der ursprüngliche Stopp und seine Nachweise oben bleiben erhalten. Der neue
Fortsetzungsauftrag erlaubt ausschließlich eine generische Korrektur der
Prozesskommunikation und danach die bereits freigegebene Phase-3O-Prüfung.
Der lokale uncommittete Arbeitsstand bleibt erhalten; kein Zwischencommit.

Vor Codeänderung wurde die tatsächlich vorhandene Prozess-API im privaten
Hostingbereich ohne DB geprüft. `subprocess.run`, bytebasierter Input, getrennte
PIPEs und Timeout funktionieren. Die relevanten Signaturen und ein UTF-8-
Byte-Roundtrip sind privat aufgezeichnet. Ein erster Diagnoseaufruf ergab keinen
verwertbaren Rückgabewert; der korrigierte ASCII-sichere Diagnoseaufruf sicherte
auch stderr und bestand. Diese Diagnoseaufrufe waren keine Writer- oder DB-Läufe.

`observation_v2.shared` verwendet nun explizite UTF-8-Inputbytes, stdout/stderr
als PIPE, striktes UTF-8-Decode beider Ausgaben und eine explizite Returncode-
Prüfung. Timeout bleibt zehn Sekunden. Keine Versionsverzweigung, kein Netzwerk,
keine neue Abhängigkeit. Canonicalization, Dedupe, Dispatcher, Katalog und
Routenbindung bleiben unverändert; der bestehende PHP-Adapter wird wiederverwendet.

Gezielte Tests: **39/39 bestanden** (27 Phase 3N, zwölf Phase 3O). Die sechs
neuen Transporttests prüfen die ältere gemeinsame Prozess-API, echte UTF-8-
Inputbytes und stdout, nichtleeres stderr, ungültiges UTF-8 auf beiden Kanälen,
nonzero Exit, Timeout ohne Retry, ungültiges JSON und Adapter-Reject. Die
eingefrorenen vollständigen vier Pläne einschließlich canonical_bytes und
dedupe_key sowie alle acht v1-Golden-Vektoren bestehen ohne Fixtureänderung.
Gesammelte Regression nach dem Transportfix: **359/360 bestanden**; ausschließlich
die bekannte Windows-Abweichung `budget_not_private`. Validate, PHP-Lint und
Diff-Check bestanden; geschützte v1-/Katalog-/Dispatcher-/Manifestdateien
unverändert.

Der erneute Hosting-Preflight im bestehenden privaten Bereich ist vollständig
**RUNTIME_READY**: echter Phase-3N-Python-Writer, vorhandener PHP-value_adapter,
vollständige Gleichheit aller vier Antworten mit den eingefrorenen lokalen
Plänen einschließlich canonical_bytes und roher 32-Byte-Keys; Exitcode 0 und
stderr leer. Kein DB-Zugriff, Passwort, Gateway oder Netzwerkzugriff des Writers.
Alle elf übertragenen Dateien zuvor per Server-SHA-256 zurückgelesen.
Der Transferauftrag hatte zunächst keine Abschlussanzeige; ein zusätzlicher
rein lesender Hashreadback bestätigte elf Dateien und keinen bisherigen Probe-
Versuch. Erst danach wurde der neue Writerlauf einmal gestartet.

Danach wurde der dünne `live_writer.php` implementiert: tatsächliche Pläne aus
dem Python-Wrapper, Bindung an echte Routensnapshots, exakte 21 Spalten,
Base64-Bytegrenze, Hashprüfung bereits gelieferter kanonischer Bytes und
ausschließlich prepared INSERTs. Keine neue Canonicalization. Der synthetische
Graph umfasst eine Source, vier Entities/Assets, vier Routes und vier
Observations in genau einer expliziten InnoDB-Transaktion. Erfolg und Fehler
enden mit ROLLBACK; kein Commitpfad, keine Bestandsupdates oder Ledgerwrites.

`state_integrity.php` verwendet den bestehenden Phase-3M-Zustandsschutz und
prüft zusätzlich vollständige Units, feste Bestandszahlen und fehlende
synthetische Keys. Der Fachhash bindet Schema, Legacy-PKs/-Werte/-Keys, Ledger
und Units; AUTO_INCREMENT bleibt diagnostisch ohne historische Gleichheits-
oder MAX(PK)-Freigabebedingung. Zwei neue Verbindungen für die Post-Readbacks.
Die exakten privaten Phase-3M-Baselinebytes werden getrennt von ihrem fachlich
normalisierten Hash gebunden; diese beiden Hasharten werden nicht verwechselt.

Der neue Gateway verwendet die bestehenden Phase-3M-HTTPS-/Origin-/CSRF-
Primitiven. GET und technischer POST führen weder Writer noch DB aus; das
Passwortformular wird erst nach dem protokollierten Dry-Run angeboten.
Passwort bleibt ausschließlich im laufenden PHP-Prozess.

Phase-3O-Tests nach Harness-Erweiterung **14/14 grün**. Der PHP-Testdouble
verbindet sich niemals mit einer DB und prüft die tatsächlichen Executor-
und Transaktionsfunktionen: vier exakte Parametersätze, 19 korrumpierte Pläne
vor prepare abgewiesen, Transaktionspflicht, Rollback bei Erfolg, Guard- und
SQL-Fehler, kein Commit, geschützte Ledger-/Fremdtabellen und Fachhashbindung
bei Units/PKs, aber nicht bei Counterdiagnostik. Request-/CSRF-Negativfälle,
statische Scopeprüfung und Lints ebenfalls grün. Gesammelte Regression nach
dieser Erweiterung **361/362 bestanden**; ausschließlich `budget_not_private`.
Validate, sämtliche geänderten PHP-Lints und Diff-Checks bestanden. Kein Deploy
aus dem Regressionstest; die entsprechende Logzeile stammt aus dem Mocktest.

Serverseitig sind insgesamt 25 erforderliche secretfreie Quellen/SQL-
Parserinputs nach SHA-256 bestätigt. Die drei Migrationsdateien werden nur
geparst, nicht ausgeführt. Die private Phase-3M-Baseline ist über ihren
Originalbericht und Dateihash gebunden; Offline-Schemaparser bestätigt 17 Tabellen.
Der Runtimebericht der erfolgreichen Fortsetzung hat SHA-256
`956998f6bdbb6b76ca9eb3d62fcd1f61a2fd94a187bdb0e50fd9fbe83d165d6e`.
Große Plesk-Aufträge hatten keine vollständige Abschlussanzeige; zusätzliche
rein lesende Prüfungen bestätigten Dateihashes, Konfiguration und Parserstatus.
Kein Transfer, Writerlauf oder DB-Versuch wurde deshalb wiederholt.

Temporärer Gateway erstellt; ohne Auth HTTP 401, Homepagebytes unverändert.
Der tatsächliche Browser-GET und ein technischer POST ohne Passwort beweisen
HTTPS, POST, exakte Origin, signiertes Cookie/CSRF, Secure, HttpOnly,
SameSite Strict, no-store und noindex. Private GET-/POST-/Formularnachweise:
0 DB-Verbindungen, 0 DB-Writes, 0 Gateway-Writerläufe. Keine Credentials in URL.
Zusätzlicher kompakter Readback bestätigt: kein Live-Lock/Start, keine DB-
Baselineaufnahme und erfolgreicher Runtimebericht unverändert. Erst danach
wurde das Passwortformular für die notwendige Nutzereingabe bereitgehalten.

Aktueller Haltepunkt: **Test-DB-Passwort fehlt**. Live-Preflight, Graph, Inserts,
DB-canonical-/Hashparität, Duplicate/Conflict/Rejects aus DB-Readbacks, Rollback
und zwei Post-Readbacks sind noch ausstehend. Die historischen Bestandszahlen
werden nicht als aktuelle DB-Messung ausgegeben. Noch kein Abschlusscommit,
Push, Linux-Abschlusslauf, Migrationsstatusupdate oder Issueabschluss. Gateway
und private temporäre Quellen bleiben ausschließlich für diesen laufenden Test
bereit; vollständiger Cleanup folgt nach dem tatsächlichen Testlauf.

## Ergebnis nach der notwendigen Passworteingabe

Der Nutzer hat den vorbereiteten Lauf gestartet. Er scheiterte bereits in der
read-only Vorprüfung mit `counter_table_set`, bevor die Live-Baseline akzeptiert,
der DB-Lock erworben oder die synthetische Testtransaktion begonnen wurde.
Der Report meldet `ok=false`, `stage=stopped`, `rolled_back=false`; letzteres
ist ausdrücklich kein fehlgeschlagener Rollback synthetischer Writes: es gab
noch keine synthetische Transaktion. Die read-only Aufnahmefunktion besitzt
ihren eigenen finally-Rollback; die Verbindung wurde anschließend geschlossen.

Eine zusätzliche Diagnose verglich ausschließlich gespeicherte Artefakte,
ohne weitere DB-Verbindung. Vollständig identisch zur gebundenen Phase-3M-
Baseline: Legacy-Rows und ihr Hash, Units, Ledger, Umgebung und normalisierte
Struktur. Aktuelle read-only Aufnahme: Units 4, Current 0, Bars 0.
Der gespeicherte Counter-Tabellensatz umfasst zwölf Tabellen, während der
übernommene Prüfer aus historischen nicht-NULL-Counterwerten nur neun erwartet.
`compareState` leitet diesen Satz aus dem Metadatenwert AUTO_INCREMENT ab,
anstatt aus der qualifizierten Spaltendefinition. Das ist eine fehlerhafte
Prüferannahme; die Artefakte belegen keine fachliche Baselineabweichung.
Ihre Übernahme in den Phase-3O-Harness war ein Fehler. Der Checker muss vor
einem später separat autorisierten Versuch offline entsprechend qualifiziert
werden; diese Erkenntnis ist keine Erlaubnis zum Umgehen oder Wiederholen
des bereits gestoppten Live-Laufs.

SHA-256 des privaten Stoppberichts:
`2018690e9cfc754ee3e75359d6b69b172f6b05e31d1352a118e3875b485204c5`.
SHA-256 der gespeicherten aktuellen Vorprüfungsaufnahme:
`79dea80aaed6adfd0d30508aeda4757a921e8fdb30b52ab12e8b409b75c89437`.
Keine synthetischen INSERTs, kein persistierender DB-Write und kein Retry.
In-Transaction-Writerparität, live Duplicate/Conflict/Reject, synthetischer
Rollback und zwei unabhängige Post-Readbacks wurden nicht ausgeführt und
bleiben unbewiesen. Die read-only Aufnahme ersetzt diese Akzeptanzkriterien nicht.

Sicherheitsbereinigung bestätigt: alle 25 temporären Paketquellen nach
Hashprüfung entfernt, 0 verbleibende Quellen, Gatewaydatei und Route entfernt,
Zugangskonfiguration und Startlock entfernt. Passwortreferenz verworfen,
CSRF-Cookie durch den Gateway-finally-Zweig abgelaufen. Private Nachweise
bleiben mit 0700/0600 erhalten. Der angemeldete Browser bestätigt Gateway 404;
anonyme Homepage weiterhin 401 und Homepagebytes unverändert. Cleanup selbst
ohne DB-Verbindung oder DB-Writes. Keine Transportdatei auf dem Server angelegt.

Nur Dokumentation nach dem Stopp geändert; keine unnötige Wiederholung der
zuletzt bestandenen lokalen Codeprüfung (361/362, allein budget_not_private;
Phase 3N 27/27, Phase 3O 14/14). Kein Abschlusscommit, Push, Linux-Abschlusslauf,
Migrationsstatusupdate oder Produktionsdeploy. Issue #31 bleibt offen; keine
Abschlussbewertung für diesen unvollständigen Auftrag. B8/Produktion nein.

Auch der neue native Recorderstart scheitert an PROMPT_RECEIPT_MISSING;
Describe/Plan jeweils einmal ohne erfundene Turn-ID versucht und abgewiesen.

## Autorisierte Fortsetzung nach CHECKER_BUG_CONFIRMED

Der neue Auftrag und [Issue-Kommentar](https://github.com/masterxfix/MOSA-2/issues/31#issuecomment-6285911747)
erlauben die generische Korrektur des Counterprüfers und einen neuen kontrollierten
Phase-3O-Versuch. Alte Berichte, Aufnahme und Cleanup bleiben erhalten.

Der bestehende gemeinsame Phase-3M-Prüfer bietet nun `counterColumns`: aus den
qualifizierten Spaltenmetadaten `COLUMN_NAME`/`EXTRA`, mit dem Attributtoken
`auto_increment`. Der erwartete Tabellensatz kommt aus der strukturell gegen die
Baseline geprüften aktuellen Aufnahme. Historische konkrete Counterwerte oder
deren non-NULL-Keyset werden dafür nicht mehr verwendet. Die Erfassung über
INFORMATION_SCHEMA.COLUMNS verwendet entsprechend EXTRA containing
auto_increment. Counterdiagnostik muss exakt diese Tabellen und die strukturell
gebundene Spalte enthalten; PKs, Counts, Rowhashes, Grants, Schema und Ledger
bleiben strikt. Units werden zusätzlich vollständig verglichen.

Die vorhandenen Parser qualifizieren 0001 mit zehn und 0002 mit zwei
AUTO_INCREMENT-Spalten: **12 strukturelle Countertabellen**. Keine tabellen-
spezifische Ausnahmeliste, kein Reset, keine historische Countergleichheit und
keine Relation Counter zu MAX(PK) als Freigabebedingung. MIN/MAX innerhalb der
PK-Evidenz bleiben reine Integritätsprüfungen der tatsächlich erfassten PK-Sätze.

Phase-3O-Tests **22/22**, Phase 3N **27/27**, gemeinsame Unit-/State-Tests
**34/34** bestanden. Neue Regression bildet historisch neun gesetzte Counter
bei zwölf strukturellen Spalten nach. Geänderte Counter auch unterhalb MAX(PK)
werden bei gleichem Fachzustand akzeptiert. Entfernte/zusätzliche strukturelle
Counterspalten, fehlende oder falsch gebundene Diagnostik, Rowcounts, PKs,
Fachwerte, Hashes, Ledger, Grants und gleichzahlige manipulierte Units werden
abgewiesen. Die gemeinsame ältere Testfixture wurde an die echten
INFORMATION_SCHEMA-Spaltennamen angepasst; keine Schutzprüfung entfernt.

Gesammelte Regression nach dem Guardfix: **369/370 bestanden**, ausschließlich
die bekannte Windows-Abweichung `budget_not_private`. Validate, PHP-Lints
aller geänderten Dateien und Diff-Check bestanden. Kein Zwischencommit.

Neues secretfreies Paket mit 25 erforderlichen Quellen und SQL-Parserinputs in
einem neuen privaten Unterbereich übertragen; Server-SHA-256 aller 25 Dateien
bestätigt. Die bisherigen privaten Nachweise bleiben unverändert. Der echte
Phase-3N-Writer besteht erneut **RUNTIME_READY**, mit allen vier vollständigen
Goldenplänen, unveränderten kanonischen Bytes/Keys, Exitcode 0 und leerem stderr.
0 DB-Verbindungen, 0 DB-Writes, kein Gateway-Writerlauf beim Runtime-Dry-Run.

Anschließend wurde die durch SHA-256 gebundene gespeicherte read-only Aufnahme
des vorherigen Stopps mit dem neuen tatsächlichen gemeinsamen Prüfer verglichen.
Ergebnis: akzeptiert, zwölf strukturelle Countertabellen, alle Fach-/Unit-/
Ledger-/Schema-/PK-/Rowhash-Prüfungen grün, kein Reset. Das Ergebnis steht privat
in `saved-preflight-recheck.json`; ausdrücklich **keine neue DB-Messung**.

Neuer temporärer Gateway vorbereitet. Ohne Auth 401; Homepagebytes unverändert.
Tatsächlicher Browser-GET und technischer POST ohne Passwort bestätigen HTTPS,
POST, exakte Origin, signierten CSRF-/Cookiepfad, Secure/HttpOnly/SameSite Strict,
no-store und noindex. Vollständiger kompakter privater Nachweis in `ready.json`:
0 DB-Verbindungen, 0 DB-Writes, 0 Gateway-Writerläufe; kein Live-Startlock und
keine neue DB-Baselineaufnahme. Erfolgreicher Runtimebericht unverändert.
Erst danach das Passwortformular bereitgehalten; bislang kein Passwort verarbeitet.

Der spätere aktuelle Live-Preflight muss mit der ausschließlich im Formular
übergebenen Passwortreferenz vor jeder synthetischen Transaktion laufen.
Ohne diese Referenz kann zuvor nur die gespeicherte read-only Aufnahme mit
dem korrigierten Guard erneut qualifiziert werden; dies ist keine neue DB-Messung.
Aktueller Haltepunkt ist ausschließlich die notwendige Passworteingabe.
Graph, Inserts, In-Transaction-Parität, Live-Duplicate/Conflict/Reject, Rollback
und zwei unabhängige Post-Readbacks stehen aus. Temporäre Quellen/Gateway bleiben
für diesen einen neuen Lauf bereit; der Cleanup folgt danach. Kein Commit,
Push, Linux-Abschlusslauf oder Issueabschluss vor vollständigem Erfolg.
Native Erfassung erneut PROMPT_RECEIPT_MISSING; Describe/Plan einmal abgewiesen,
ohne Ereignisse oder Turn-IDs zu erfinden. Keine Abschlussbewertung.

## Ergebnis des nach Guardfix gestarteten neuen Laufs

Der Nutzer startete den vorbereiteten neuen Lauf. Die aktuelle read-only
Vorprüfung wurde akzeptiert und als `baseline-live.json` gespeichert;
`structural_counter_tables=12`. Damit ist der ursprüngliche Countertabellen-
Prüferfehler auch im aktuellen DB-Preflight behoben. Der dedizierte DB-Lock
wurde erworben und am Ende freigegeben (`lock_released=true`).

Der Lauf stoppte danach mit `failure={kind:guard,reason:php_cli}`. Der tatsächliche
FPM-Aufruf scheiterte an der statischen Dateisystem-/Executable-Prüfung des
freigegebenen PHP-CLI-Pfads, bevor der Python-Prozess im DB-Test gestartet
wurde. Der vorherige erfolgreiche CLI-Runtime-Dry-Run ist damit kein Nachweis
dieser zusätzlichen FPM-Guardbedingung. Deren konkrete Hostingursache wurde
nicht weiter untersucht; keine Hostingänderung und kein Ersatzpfad.

Gemäß dem deterministischen, hashgeprüften Aufrufpfad war der synthetische
Graph zu diesem Zeitpunkt bereits vollständig innerhalb der Testtransaktion
angelegt (eine Source, vier Entities/Assets, vier Routes). Es gab noch keinen
Observation-v2-INSERT, keinen Live-Writerplan und keine In-Transaction-Parität,
Duplicate-/Conflict-/Reject-Prüfung. Der finally-Zweig von `rollbackTransaction`
führte ROLLBACK aus; bei einem fehlgeschlagenen Rollback hätte dessen Guard
den ursprünglichen php_cli-Fehler ersetzt.

Der äußere Bericht enthält trotzdem `rolled_back=false`: Das Flag wird bisher
erst nach erfolgreicher Rückkehr der Testfunktion gesetzt und erfasst den
bereits im inneren Fehlerpfad erfolgten Rollback nicht. Der Originalbericht
wurde nicht umgeschrieben. Diese zusätzliche Berichtslücke bleibt offen.

Die erste neue Post-Verbindung erfasste einen vollständigen Zustand, wurde
aber mit `readback_failure={kind:guard,reason:structure_changed}` abgewiesen.
Deshalb wurde weder `readback-1.json` als akzeptiert gespeichert noch die zweite
unabhängige Verbindung ausgeführt. **Zwei erfolgreiche Post-Readbacks fehlen.**

Eine nachfolgende Diagnose nutzte ausschließlich diese gespeicherte Aufnahme,
ohne weitere DB-Verbindung. Rows, Rowhash, Units, Ledger und Umgebung sind exakt
gleich zur akzeptierten aktuellen Baseline. Units 4, Current 0, Bars 0. Der
fachliche Graphrollback ist durch diese eine Post-Aufnahme gestützt; sie wird
nicht als zwei bestandene Readbacks ausgegeben.

Die sieben Struktur-Differenzpfade enden ausschließlich in verschachtelten
`comparisons/*/show_create_table`-Diagnosen. Dort wurden die vollständigen
SHOW-CREATE-Strings mit fortgeschriebenen AUTO_INCREMENT-Tabellenoptionen
aufbewahrt. Die bisherige Normalisierung erfasst nur das oberste show_create
und die Tabellenmetadaten, nicht diese Diagnosekopien. Ein reiner Artefakt-
Vergleich bestätigt vollständige Strukturgleichheit nach ausschließlicher
Normalisierung dieser Counteroptionen. Kein Reset, DDL oder Schemawechsel;
die Aufnahme selbst hatte bereits die qualifizierten Spalten/Indizes/FKs/CHECKs
gegen das Repositoryschema geprüft. Dies erklärt den zweiten Prüferstopp,
ersetzt aber den fehlenden freigegebenen Zweifach-Readback nicht.

Privater Stoppbericht SHA-256:
`3dcf81f46bab367bca6b8febe4a72b388efd2c6b15e68f2a8d43bdbed37fde2c`.
Gespeicherte erste Post-Aufnahme SHA-256:
`4e4e7f46cc9a906e0610dd80b159f7010adb9f91e56804f8fa9daf870ef1013f`.
Diagnosen separat in `stop-diagnosis.json` und `stop-summary.json`, privat.
Kein erneuter DB- oder Testversuch nach dem Fehler.

Cleanup bestätigt: 25 temporäre Quellen nach Hashprüfung entfernt, 0 verbleibend;
Gatewaydatei und Route, Zugangskonfiguration und Startlock entfernt. Passwort
verworfen, CSRF-Cookie durch den Gateway-finally-Zweig abgelaufen. Private
Nachweise 0700/0600. Gateway im angemeldeten Browser 404, Homepage anonym 401
und byteidentisch. Cleanup ohne DB-Verbindung oder DB-Write.

Die zuletzt vollständige lokale Prüfung bleibt 369/370 (nur budget_not_private),
gezielt Phase 3O 22/22 und Phase 3N 27/27. Nach dem Stopp nur Dokumentation
geändert, keine redundante Regression. Kein Abschlusscommit, Push, Linux-
Abschlusslauf, Migrationsstatusupdate oder Produktionsdeploy. Issue #31 bleibt
offen; keine Abschlussbewertung. Kein B8 und keine Produktion.

## Autorisierte Fortsetzung nach php_cli-/Readback-Stopp

Der neue Auftrag bestätigt drei Prüferfehler. Der bisherige uncommittete
Arbeitsstand und alle privaten Stoppnachweise bleiben erhalten. Keine erneute
DB-Verbindung für die Offlinekorrektur, kein Zwischencommit.

`writerPlans` führt keine statische Binary-/Executable- oder FPM-SAPI-Prüfung
mehr aus. Ein expliziter Prozess-PATH ist Ausführungsparameter, kein
Capabilitynachweis. `capabilityGateway` verwendet im späteren HTTP-/FPM-Kontext
denselben `writerPlans`-Aufruf wie der DB-Executor: echter Phase-3N-Python-Writer,
bestehender PHP-value_adapter und vollständiger Vergleich der vier eingefrorenen
Goldenpläne. Nur dieser tatsächliche Aufruf kann RUNTIME_READY begründen; der
historische CLI-Probebericht autorisiert keinen DB-Lauf mehr. Der Probe ist
einmalig, secretfrei und öffnet keine DB-Verbindung. Ein RUNTIME_GAP stoppt ihn.

Der private Capabilitybericht bindet die verifizierten Quellhashes und den
Prozess-PATH. Status, Gatewaykontext, vollständige Golden-/Byte-/Key-Parität,
sauberer Prozessausgang und 0 DB-Verbindungen/-Writes sind erforderlich.
Diese Bindung wird vor der ersten DB-Verbindung und nochmals nach dem aktuellen
read-only Preflight vor der synthetischen Transaktion kontrolliert. Der
Passwortgateway wird erst nach erfolgreichem FPM-Probe bereitgestellt.

Der gemeinsame Phase-3M-Vergleich erzeugt jetzt rekursiv einen expliziten
Comparison-State für alle `show_create`-/`show_create_table`-Kopien. Nur die
unquoted dezimale AUTO_INCREMENT-Tabellenoption nach dem CREATE-TABLE-Körper
und der numerische Tabellenmetadatenwert werden normalisiert. Gequotete
Strings/Kommentare/Identifier, Spaltenattribute und sämtliche übrigen DDL-
Details bleiben exakt. Rohe Aufnahmen werden nicht verändert. Fachvergleich
und Hash verwenden dieselbe zentrale Funktion.

Das Rollbackreporting trennt Transaktionsstart, tatsächlichen Rollbackversuch,
Rückgabewert und danach geschlossenen Transaktionszustand sowie jeden der beiden
unabhängigen Post-Readbacks. Der finally-Zweig führt genau einen Rollbackversuch
aus; eine Rollbackexception bleibt sichtbar. Vor beginTransaction bleiben Start
und Versuch false. Erst beide neu verbundenen, fachlich akzeptierten Readbacks
können den vollständigen Abschluss bestätigen. Ein technischer Rollback allein
genügt nicht. Kein Retry nach einem Livefehler.

Gezielt Phase 3O **27/27**, Phase 3N **27/27** bestanden. Neue Tests decken
Top-Level-, verschachtelte und sieben parallele Diagnosekopien ab, außerdem
echte Änderungen an Spalten-AUTO_INCREMENT, Typ/Default/PK/Unique/Index/FK/CHECK,
Engine/Charset/Collation/weiteren Optionen und einem gequoteten Counterliteral.
Der erste Testlauf hatte drei falsch escapte PHP-Callbacknamen in den neuen
Hashprüfungen; korrigiert, danach vollständig grün. Rollbackkontrollfluss mit
Fehler vor Start, direkt nach Start, nach 13 Graph-Inserts, nach erstem
Observation-Insert, normalem Ende und Rollbackexception geprüft. Completion
benötigt alle sechs Nachweise; veralteter Quell-/PATH-Fingerprint und fehlende
Capabilitynachweise werden abgewiesen.

Gesammelte lokale Regression **374/375 bestanden**; ausschließlich die bekannte
Windows-Abweichung `budget_not_private`. Validate, alle Phase-3O-PHP-Lints,
gemeinsamer State-Prüfer und Diff-Check bestanden. Die Deploymentausgabe in der
Testsuite stammt aus dem bestehenden Mocktest, kein Produktionsdeploy.
Native Auftragserfassung weiterhin PROMPT_RECEIPT_MISSING; Describe und Plan
jeweils einmal ohne erfundene Turn-ID abgewiesen. Kein Abschlussrating.

Die vorhandene verbundene Chrome-Sitzung wurde aktuell geprüft: Dogado und
Plesk sind angemeldet. Kein erneuter manueller Anmeldeschritt erforderlich.
27 secretfreie Quellen/Parserinputs in einen frischen privaten Unterbereich
übertragen, alle Server-SHA-256 bestätigt. Der große Transferauftrag zeigte
zunächst keine Abschlussanzeige; ein separater rein lesender Readback bestätigte
die vollständige Installation, ohne den Transfer oder Probe zu wiederholen.
Der tatsächliche neue gemeinsame Vergleich akzeptiert die hashgebundene
gespeicherte erste Post-Aufnahme des vorherigen Stopps einschließlich identischem
Fachhash. Das ist Artefaktqualifikation ohne neue DB-Verbindung.

Anschließend bestand der neue Probe genau einmal über den authentifizierten
HTTPS-Gateway im tatsächlichen späteren FPM-Ausführungskontext:
**RUNTIME_READY**, echter Phase-3N-Writer und bestehender PHP-value_adapter,
alle vier vollständigen Goldenpläne, kanonische Bytes und rohe Dedupe-Keys exakt,
Prozessausgang sauber. Keine zusätzliche SAPI-/Binary-Capabilityprüfung.
Der private Bericht bindet alle aktuellen Quellhashes und den Prozess-PATH.
Capabilitybericht SHA-256:
`c02287ff091f1dd218e161f38b9c4a53d1cc66cd8a384d6d810e170a89dd8167`.
0 DB-Verbindungen, 0 DB-Writes; keine Hosting-/Runtimeänderung.

Erst danach wurde am selben geschützten Pfad der Passwortgateway bereitgestellt.
Der tatsächliche Browser-GET und technische POST ohne Passwort wurden ausgeführt.
Der private kompakte Readback bestätigt HTTPS, POST, exakte Origin, CSRF,
Secure/HttpOnly/SameSite Strict, no-store und noindex. Weiterhin 0 DB-Verbindungen,
0 DB-Writes, 0 Gateway-Writerläufe, kein Live-Startlock und keine aktuelle DB-
Baselineaufnahme. Der tatsächliche FPM-Capabilitybericht bleibt unverändert
gebunden. Gateway anonym 401, Homepagebytes unverändert. Passwortformular im
Browser bereitgehalten; Plesk-Einmalformular ohne Speichern geschlossen,
weiterhin neun bestehende geplante Aufgaben. Haltepunkt: notwendige Eingabe des
Test-DB-Passworts ausschließlich im Formular.
Aktueller DB-Preflight, synthetische Writes,
DB-Parität, Duplicate/Conflict/Rejects, Rollback und beide neuen unabhängigen
Post-Readbacks bleiben bis zur notwendigen Passworteingabe ausstehend. Kein
Abschlusscommit/Push, Linux-Abschlusslauf, Migrationsstatusupdate oder Issue-
Abschluss vor vollständigem Live-Erfolg. Kein B8 und keine Produktion.

## Finaler kontrollierter Live-Lauf nach Passworteingabe

Der Nutzer hat den vorbereiteten Test gestartet. Der aktuelle read-only Preflight
bestätigte die isolierte Test-DB, Schema-/Ledger-Version 3, 17 Tabellen, zwölf
strukturelle AUTO_INCREMENT-Tabellen, vier unveränderte Units und den vollständigen
Legacybestand. Nach der Vorprüfung wurde die erfolgreiche Capabilitybindung des
aktuellen deployten Harness erneut kontrolliert, noch vor Transaktionsstart und
Graph. Der dedizierte DB-Lock wurde erworben.

Genau eine rollbackbare InnoDB-Testtransaktion erzeugte ausschließlich den
synthetischen Graph (eine Source, vier Entities, vier Assets, vier Routes) und
vier v2-Observations. Die tatsächlichen generierten Route-IDs wurden gelesen
und dem echten Phase-3N-WriterPlanner übergeben. Alle vier Entscheidungen INSERT;
der PHP-Executor verwendete ausschließlich die validierten Pläne mit 21 exakt
gebundenen Parametern. Keine zweite Kanonisierung oder manuelle Keyerzeugung.

Für EUR, GBP, GBX und POINT bestätigt: Format 2, kanonische Bytes identisch,
Dedupe-Key identisch und 32 rohe Bytes, sämtliche DB-Fachwerte identisch zum
Plan, gebundene Route/Unit und native Werte unverändert. DB-Readbacks wurden als
existing snapshots erneut an denselben Writer gegeben: jeweils
DUPLICATE_UNCHANGED ohne weiteren INSERT. Kontrollierte ausschließlich in-memory
inkonsistente Snapshots mit gleichem Key ergaben jeweils CONFLICT ohne Write.

Alle sieben Fälle REJECT, ohne daraus folgende DB-Writes: Route-/Unit-Mismatch,
POINT mit Currency, GBX mit Currency GBX, v2 gegen v1-Route, Volume ohne Unit,
unvollständige Quantity-Basis und derived statt native.

Danach tatsächlicher ROLLBACK im finally, kein Commit synthetischer Daten,
kein Retry. Der private Bericht enthält alle sechs getrennten Zustände true:
transaction_started, rollback_attempted, rollback_call_succeeded,
rollback_transaction_closed, post_rollback_readback_1_confirmed und
post_rollback_readback_2_confirmed. DB-Lock freigegeben; Bericht ok=true,
stage=complete. Ein technischer Rollback wurde erst zusammen mit beiden
fachlich akzeptierten Readbacks als vollständig bestätigt gewertet.

Zwei jeweils neue unabhängige DB-Verbindungen bestätigten denselben Fachhash
wie die aktuelle Preflightbaseline. Jeweils Entities 7, Assets 7, Identifier 7,
Sources 4, Routes 8, Observations 8, Checkpoints 5, Units 4, Current 0, Bars 0,
Ledger v1/v2/v3. Keine synthetischen Keys/Rows verblieben. Sämtliche Legacy-PKs,
Fachwerte und rohen Dedupe-Keys unverändert; die acht v1-Formatmarker und neuen
Unitfelder weiterhin NULL (durch die gemeinsame aktuelle Struktur-/Added-Values-
Prüfung kontrolliert). Nur technische Counteroptionen dürfen fortschreiten.

Private Bericht-SHA-256:
`51d0ea41d92cfcf035f5623c143b2e3285c6d5dec5c363e8bdc9269b87b56b87`.
Die zwei unabhängig erfassten Readbackdateien haben identische Bytes, jeweils:
`11057b4b239955ee274cbeab12857a65c2ef0d16d8ddc40e1683931d85b8a423`.
Nachgelagerte Prüfung ausschließlich gespeicherter Artefakte bestätigte alle
vier Unitpfade, 17 synthetische Gesamtinserts/vier Observation-Inserts, sieben
Rejects und beide vollständigen Fachzustände nochmals ohne DB-Verbindung.

Cleanup: Passwortreferenz im Gateway-finally verworfen, CSRF-Cookie abgelaufen;
27/27 temporäre Quellen hashgeprüft entfernt, 0 verbleibend. Gatewaydatei/-Route,
Zugangskonfiguration und beide Startlocks entfernt. Keine Session oder
Transportdatei auf dem Server angelegt. Private Nachweise mit 0700/0600 erhalten.
Authentifizierter Browser bestätigt Gateway 404, anonyme Homepage 401,
Homepagebytes unverändert. Plesk-Einmalformular ohne Speichern beendet; weiterhin
neun bestehende geplante Aufgaben. Cleanup ohne DB-Verbindung/-Write.

Die seit der letzten vollständigen Regression folgenden Änderungen betreffen
nur Dokumentation. 27/27 Phase-3O- und 27/27 Phase-3N-Tests, Gesamtsuite 374/375
unter Windows (allein budget_not_private), Validate, PHP-Lints und Diff-Check
bleiben der lokale Nachweis. Der einzige Abschlusscommit wird mit [skip ci]
nach origin/main gepusht. Vom exakt selben Commit wird der bestehende Workflow
manuell auf einem temporären Nicht-main-Prüfbranch gestartet; dessen Deployjob
ist dadurch skipped. Commit, Linux-Run-ID/-Ergebnis und Branchlöschung werden
zusammen in Issue #31 als endgültiger Git-/CI-Nachweis festgehalten.

## Aussagegrenzen und vorbereiteter nächster Schritt

Bewiesen ist genau dieser kontrollierte synthetische Test mit vier normativen
Unittypen und vollständigem Rollback. Kein produktiver Collector, kein
Parallelbetriebs-/Lastnachweis, keine Übernahme weiterer echter Marktwerte.
Keine Schema-/Ledgeränderung, kein Current-/Bars-Write, kein B8-Import und
kein Produktionsdeploy. Die Gesamtmigration bleibt offen.

Phase 3P ist ausschließlich als read-only Qualifikation vorbereitet: B8-
Identität gegen bestehende Identifier und Belege abgleichen; tatsächliche Source
und bisherige Route belegen; native GBX-Semantik samt monetärer GBP-Zuordnung
aus den normativen Definitionen prüfen; Zeit-/Payload-Evidenz und Provenienz
qualifizieren; danach die notwendige unveränderliche unit-aware Routenrevision
beschreiben. Keine Route anlegen oder umdeuten und keine Observation importieren.
Die fachliche B8-Prüfung ist in Phase 3O nicht ausgeführt.

# Phase 3K – Unit-Schema live validiert

Status des DB-Laufs: **erfolgreich**. Ausgangspunkt:
`b7f352db4ee68a2e1e6d657a512131fa1881701f`.
Migration 0003 SHA-256:
`199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee`.

## Bestätigter Abschluss des DB-Laufs

Die kontrollierte Fortsetzung nach DDL 3 endete erfolgreich am
**2026-10-19T18:17:10+00:00**. Der vollständige read-only Resume-Preflight
bestätigte 17 Tabellen / 170 Spalten / 17 PK / 10 zusätzliche UNIQUEs /
33 weitere Indizes / 30 FKs / 31 CHECKs, leere Units, Ledger v1/v2,
unveränderte Original-Fachdaten und Grants und keinerlei DDL-4/5-Anteile.
DDL 1–3 wurden nicht wiederholt. Nach privater Sicherung wurden ausschließlich
DDL 4 und 5 ausgeführt und jeweils vollständig validiert.

**Endschema: 17 Tabellen / 186 Spalten / 17 PK / 10 zusätzliche UNIQUEs /
39 nicht-eindeutige Indizes / 36 FKs / 37 CHECKs.**
Der zuvor beobachtete CHECK-Stopp trat nach der generischen Korrektur nicht mehr auf;
sämtliche CHECKs bestanden den Vergleich Migration/INFORMATION_SCHEMA/SHOW CREATE.

Die rollbackbaren synthetischen Proben bestanden: Basis 1/1, Minor 1/100,
POINT ohne currency und Quantity; zehn erwartete Ablehnungen einschließlich
denominator/version 0, unbekannter FK, unvollständiger Unit-/Quantitybindung,
Quantity 0/negativ, route_revision 0, fehlender Quoteunit und NULL currency
bei Legacy. Vollständiger Rollback bestätigt; keine permanenten Testzeilen,
keine Unit-Seeds und keine Auto-Increment-Änderungen.

Ledger v3 wurde erst danach transaktional geschrieben, vor Commit gelesen
und über neue Verbindungen unabhängig bestätigt:
`0003_market_units`, obige Checksum, `applied_at` UTC
**2026-10-19 18:17:09.921125**. v1/v2 unverändert.
Zwei unabhängige Final-Readbacks mit unterschiedlichen Verbindungen bestanden;
beide privaten Endzustandsdateien haben identische SHA-256-Werte.

Alle bisherigen Fachwerte und binären Dedupe-Keys sind gegenüber dem Original
unverändert: Entities/Assets/Identifier je 7, Sources 4, Routes 8,
Observations 8, Checkpoints 5, Current 0, Bars 0; übrige Fachbestände unverändert.
Routenrevision überall 1, neue Route-/Observation-Unitfelder NULL,
observation_format_version NULL und Units 0. Grants unverändert.

Pre-State/Restore-Export des exakten Resume-Zustands: 17 CREATEs und
48 vorhandene Fach-/Ledgerzeilen (65 Statements), privat 0700/0600.
Originale und beide Vorläufe bleiben erhalten. Sicherungs- und beide
Final-Readback-Dateihashes wurden vor der Bereinigung erneut verifiziert.
Kein tatsächlicher Restore und keine destruktive Zielvorbereitung.

Passwort ausschließlich im laufenden Prozess, nie Datei/Chat/URL/Log.
Gateway-Verzeichnis, Zugangskonfiguration, ausführbare Quellen, Transport-/Delta-
Paket und Lock wurden entfernt. Private Belege verbleiben unter
`mosa2_phase3k_resume3_a152ca` mit 0700/0600. Authentifizierter Gateway: **404**;
unauthentifizierte Testhomepage: **401**. Zugangskonfiguration und Lock fehlen.

Die statische Homepage wird ausschließlich um 17 Tabellen / Schema-Version 3
aktualisiert; bestehende Shell, CSS, Navigation-Timing-Anzeige und Ladeverhalten
bleiben erhalten. Ihr neuer exakter Bytehash ist zusätzlich im Regressionstest
geschützt. Nur diese Datei wird nach Commit und Linux-Nachweis auf die isolierte
Testhomepage übertragen; Produktionsdeployment bleibt **skipped**.

Der exakte Abschlusscommit, zugehörige Linux-Run, abschließender 401-/404-Nachweis
und anschließend gemessene Desktop-/Mobile-Ladezeiten werden im Abschlusskommentar
zu [Issue #26](https://github.com/masterxfix/MOSA-2/issues/26) verknüpft.
Keine Produktionsfreigabe, kein Writer-v2 und kein B8-Import.

Die folgenden Abschnitte erhalten die beiden vorherigen Stopps und ihre damaligen
Aussagegrenzen als Verlauf; sie beschreiben nicht den oben bestätigten Endzustand.

## Fortsetzung nach DDL 3 – CHECK-Diagnose

Klassifikation: **CHECKER_BUG_CONFIRMED**. Die bereits gespeicherte Datei
`check-failure.json` hat SHA-256
`163d00e637f7a935340241266356796abdbfeb6931c964ff1044745a75ee8c11`.
Migration und gespeichertes SHOW CREATE enthalten dieselben Operanden in
derselben Reihenfolge und dieselbe abschließende Wahrheitsprüfung `IS TRUE`.
MySQL stellt lediglich `A OR (B OR C)` als `(A OR B) OR C` dar.
Der bisherige Prüfer verglich binäre Bäume einschließlich dieser irrelevanten
Assoziation. Die INFORMATION_SCHEMA-Zeile des fehlgeschlagenen Vergleichs
wurde damals nicht separat persistiert; der gespeicherte SHOW-CREATE-Ausdruck
belegt bereits die Ursache. Der neue Live-Preflight muss weiterhin auch den
vollständigen Dreifachvergleich Migration/INFORMATION_SCHEMA/SHOW CREATE bestehen.

Der unabhängige Phase-3J-Auswerter bestätigt alle 16 NULL-/Nicht-NULL-Zustände
des konkreten CHECKs. Zusätzlich sind für AND und OR alle 27 Kombinationen
von TRUE/FALSE/UNKNOWN für die Assoziativität geprüft. Keine neue DB-Verbindung
für diese Klassifikation.

Die Korrektur normalisiert ausschließlich benachbarte Knoten mit demselben
AND-/OR-Operator. Reihenfolge, gemischte Gruppierung, Vergleiche, Identifier,
Literalbytes und `IS TRUE` bleiben erhalten. Keine Constraint-/Tabellensonderlogik,
keine Kommutativität, keine Distributivität und keine schwache Textbereinigung.
Gezielte Mutationen prüfen andere Spalten, NULL/NOT-NULL-Wechsel, vertauschte
Operatorlogik, fehlende Zweige/IS TRUE sowie falsche/doppelte Constraintnamen.
Künftige fehlgeschlagene CHECK-Dreifachvergleiche werden vor dem Guard-Abbruch
privat mit Originaltext und Normalisierung gesichert.

Nach tatsächlicher Korrektur: CHECK-Tests **14/14**, Phase-3K-Tests **21/21**,
vollständige lokale Suite einschließlich 0001/0002/0003-Fixtures **257/258**;
nur bekannte Windows-Ausnahme `budget_not_private`. Validator, PHP-Lint und
Diff-Prüfung bestanden.

Der aktuelle Runner akzeptiert ausschließlich den vollständigen Zustand nach
DDL 3: 17/170/17/10/33/30/31, leere Units, nur Ledger v1/v2, unveränderte
Fachdaten/Grants gegenüber der Original-Sicherung, Routenrevision 1 und neue
Route-/Observation-Unitfelder NULL. Jegliche DDL-4/5-Anteile führen zum Stopp.
Nur DDL 4 und 5 dürfen nach erneutem privaten Resume-Export ausgeführt werden;
die tatsächliche Ausführungsfunktion wird gegen jeden Replay von DDL 1–3 getestet.
Originale und vorherige Resume-Berichte/Pre-States/Restore-Dateien sind über
ihre gespeicherten Hashes verkettet. Korrigierende DDLs bleiben ausgeschlossen.

Neun Quellen wurden im privaten Verzeichnis `mosa2_phase3k_resume3_a152ca`
außerhalb des Webroots über den Plesk-Textweg bereitgestellt und serverseitig
per SHA-256 gegen lokale Repositorybytes geprüft; 0700/0600 und PHP-Lint bestanden.
Auch die privaten Original-/Vorlauf-Artefakte und der korrigierte Vergleich des
gespeicherten CHECKs bestanden auf dem Server ohne DB-Verbindung.
Stand vor der Passwortübergabe: Live-Resume nach DDL 3 noch nicht gestartet.
Der erfolgreiche Lauf und sein Endzustand sind oben dokumentiert.

## Fortsetzung aus dem Teilzustand

Klassifikation anhand des bereits gespeicherten SHOW CREATE:
**CHECKER_BUG_CONFIRMED**. Der archivierte SHOW-CREATE-Text hat SHA-256
`b790bd10691811fc52aecd854cd21bfad35277dc37ef5d5636ddc95435c8edec`.
Alle zwölf Spalten, PK, zusätzliche UNIQUE-/Stützindizes, der dreispaltige
Self-FK einschließlich beider Spaltenreihenfolgen und DELETE RESTRICT sowie
alle fünf CHECK-Ausdrucksbäume entsprechen DDL 1. Der unabhängige Vergleich
mit der Phase-3J-Fixture konsumiert sämtliche SHOW-CREATE-Klauseln.
Hierfür wurde keine neue DB-Verbindung geöffnet.

Ursache: MySQL trennt FK-Spalten in SHOW CREATE mit Komma und Leerzeichen;
der bisherige Teilstringvergleich erwartete Kommas ohne Leerzeichen.
Der generische FK-Parser vergleicht nun Constraintnamen, geordnete Spalten,
Zieltabelle, geordnete Zielspalten und Löschregel. Fehlende/zusätzliche FKs,
falsche Reihenfolgen/Ziele, unbekannte Syntax und unzulässige Aktionen werden
weiterhin abgelehnt. Keine Sonderbehandlung für eine Tabelle oder Constraint.

Gezielte Phase-3K-Tests: **19/19**. Gesamtsuite nach Korrektur: **251/252**,
ausschließlich bekannte Windows-Abweichung `budget_not_private`.
Validator, PHP-Lint und Diff-Prüfung bestanden. Ein erster gezielter Lauf
scheiterte am nicht beschreibbaren Sandbox-Tempverzeichnis; derselbe Test
bestand mit einem Tempverzeichnis im autorisierten Workspace unverändert.

Der Resume-Runner akzeptiert ausschließlich das vollständige Schema nach
DDL 1, leere Units, Ledger v1/v2, unveränderte Grants/Legacywerte gegenüber
dem hashgebundenen Original-Pre-State und keinerlei Teil von DDL 2–5.
Er exportiert vor weiteren DDLs den vollständigen Resume-Pre-State mit
17 Tabellen und 48 bestehenden Zeilen. Ausschließlich DDL 2–5 werden danach
einmalig ausgeführt, jeweils mit vollständigem Zwischencheck. DDL 1 bleibt
ausgeschlossen; kein Retry oder korrigierender DDL-Eingriff.

### Tatsächliches Resume-Ergebnis

Der einmalige Resume-Lauf endete am **2026-10-19T17:53:50+00:00** erneut
fail-closed. Der vollständige Live-Resume-Preflight bestand: DDL 1 korrekt,
Units leer, nur Ledger v1/v2, keinerlei DDL-2–5-Anteile und sämtliche alten
Fachwerte/Grants unverändert gegenüber dem hashgebundenen Original-Pre-State.
Der Resume-Pre-State und der vollständige Restore-Export (17 CREATEs,
48 bestehende Zeilen; zusammen 65 Statements) wurden vor DDL 2 privat gesichert
und ihre Hashes vor der Bereinigung erneut verifiziert. Kein tatsächlicher Restore.

DDL 2 (`m2_asset_source_routes`) wurde ausgeführt und vollständig validiert:
17 Tabellen / 161 Spalten / 17 PK / 10 zusätzliche UNIQUEs / 30 weitere Indizes /
27 FKs / 28 CHECKs. Der Legacy-Datenhash nach DDL 2 entspricht exakt dem
gespeicherten Original; neue Routenrevisionen/-Unitfelder bestanden den Guard.

DDL 3 (`m2_market_observations`) wurde ausgeführt. Im nachfolgenden
Strukturvergleich stoppte der Guard
`unit_check_expression:ck_market_observations_volume`.
Der ursprüngliche FK-Fehler trat nicht mehr auf. Zum neuen CHECK-Befund wurden
erwarteter Ausdruck, gespeicherter SHOW-CREATE-Ausdruck und beide ASTs privat
in `check-failure.json` gesichert; die Ausdrucksbäume unterscheiden sich.
Das allein beweist weder eine reale semantische Schemaabweichung noch eine
unbedenkliche Servernormalisierung. Keine Vermutung und keine weitere Reparatur.

Erfasster SHOW-CREATE-Teilstand nach DDL 3:
**17 Tabellen / 170 Spalten / 17 PK / 10 zusätzliche UNIQUEs / 33 weitere Indizes /
30 FKs / 31 CHECKs**. Diese Zählung ist kein bestandener vollständiger Postcheck.
**DDL 4–5, Constrainttests und Ledger v3 wurden nicht ausgeführt.**
Kein Retry, kein DROP, keine korrigierenden DDLs und keine Seeds.
Der vollständige Legacy-Vergleich nach DDL 3 und ein unabhängiger Final-Readback
sind nicht bestanden; der letzte vollständige Legacy-Nachweis ist nach DDL 2.

Der erneute Quellen-Transfer lief ausschließlich über den vorhandenen
Plesk-Textweg. Alle neun Quellen-SHA-256, PHP-Lint und 0700/0600 bestanden
vor einer neuen DB-Verbindung. Der erste Browser-GET benutzte noch den früheren
Gateway-Einstieg aus dem PHP-Cache. Eine gezielte Cache-Invalidierung ohne
DB-Verbindung beseitigte das; die kurzlebige Diagnose-Datei entfernte sich selbst.
Anschließend bestand der tatsächliche secretfreie GET/POST-Formularlauf erneut
HTTPS, exakte Origin/CSRF, Secure/HttpOnly/SameSite Strict, no-store/noindex,
0 DB-Verbindungen und 0 DB-Writes.

Nach dem Abbruch wurden Gateway-Verzeichnis, Zugangskonfiguration, ausführbare
Quellen, Transport-/Delta-Paket und Lock entfernt. Ursprüngliche Artefakte bleiben
unverändert erhalten; zusätzliche Resume-Berichte/Restore-Artefakte liegen privat
unter `mosa2_phase3k_resume_a152ca` mit 0700/0600. Gateway **404** im authentifizierten
Browser; Testhomepage ohne Authentifizierung **401** und SHA-256 unverändert:
`e2d87e36d84703e7fa6e0c629ffb2a3b89451ff45602d15651bf1e69e3099c05`.

Status weiterhin **incomplete**, Issue #26 offen. Kein Abschlusscommit, Push,
Linux-Abschlussnachweis oder Homepage-Update, da der vollständig erfolgreiche
Apply fehlt. Die Performance-Abnahme der aktualisierten Homepage ist damit
nicht erfolgt; kein <2s-Erfolg wird behauptet. Produktionsdeploy **skipped**.
Keine Produktion, Writer-v2 oder B8-Übernahme.

## Tatsächlicher Ablauf am 19.10.2026

Neun secretfreie Quellen wurden über den vorhandenen Plesk-Textweg privat
außerhalb des Webroots bereitgestellt. Alle SHA-256-Werte entsprachen den
lokalen Repositorybytes, einschließlich der Windows-Zeilenenden von
`phase2/postcheck.php`. Verzeichnisse 0700, Dateien 0600, PHP-Lint erfolgreich.
Vor diesem Nachweis wurde keine DB-Verbindung geöffnet.

Der secretfreie Gateway-Dry-Run bestand HTTPS, zulässige Methode, exakte
POST-Origin, gültiges/ungültiges/abgelaufenes CSRF sowie tatsächlich gesendete
Secure-, HttpOnly-, SameSite-Strict-, no-store- und noindex-Header. Der erfolgreiche
Browser-POST bestätigte Origin/CSRF mit 0 DB-Verbindungen und 0 DB-Writes.
Das bestehende Passwort wurde durch den Nutzer direkt eingegeben und nur im
laufenden Prozess verwendet; keine Passwortdatei und kein gespeicherter POST.

Der Live-Preflight und der private Pre-State-/Restore-Export bestanden.
Vorher: 16 Tabellen, 140 Spalten, 16 PK, 9 zusätzliche UNIQUEs, 26 weitere
Indizes, 23 FKs, 19 CHECKs; Ledger v1/v2. Der Export umfasst die vollständigen
16 Tabellen und 48 vorhandenen Zeilen; Hashprüfung bestanden. Eine tatsächliche
Restore-Ausführung wurde nicht vorgenommen.

DDL 1 (CREATE `m2_units`) wurde ausgeführt. Der anschließende unabhängige
SHOW-CREATE-Abgleich stoppte am Guard `show_fk:m2_units`.
Der Bericht endete um **2026-10-19T17:26:04+00:00**, Stage `ddl_1`,
Failure `kind=guard`, `reason=show_fk:m2_units`.
Die genaue Darstellungsabweichung war beim ursprünglichen Stopp noch nicht
qualifiziert; ihre spätere Klärung steht oben. Der damalige Teilzustand enthält 17 Tabellen
einschließlich `m2_units`.

**Kein Retry, keine Reparatur und kein DROP. DDL 2–5 wurden nicht ausgeführt.**
Kein Ledger-v3-Eintrag, keine Constrainttests, keine Unit-Seeds, kein Writer-v2,
kein B8-Import. Vollständiger Legacy-Vergleich nach dem Apply und unabhängiger
Final-Readback sind nicht bestanden und werden nicht behauptet. Die gewünschten
Endzahlen 17/186/17/10/39/36/37 sind kein bestätigter Endzustand.

## Sicherheit und Nachweise

Private Berichte, Pre-State, Restore-SQL, Restore-Plan und Teil-Schema verbleiben
unter `mosa2_phase3k_private_a152ca` außerhalb des Webroots mit 0700/0600.
Backup-Hashes wurden vor der Bereinigung erneut geprüft. Temporäre Quellen,
ausführbare Dateien, Zugangskonfiguration, Transportpaket und Lock wurden
entfernt. Gateway und dessen öffentliches Verzeichnis wurden entfernt;
authentifizierter Browser bestätigt **404**. Testhomepage ohne Authentifizierung
bestätigt **401**; sie wurde nicht aktualisiert.

Offline zuvor: **244/245**, ausschließlich bekannte Windows-Abweichung
`budget_not_private`; zwölf neue gezielte Tests bestanden, Validator und
Diffprüfung bestanden. Keine erneute vollständige Suite nach dem Live-Abbruch.
Kein Abschlusscommit, Push oder Linux-Erfolgsnachweis, da diese Schritte im
Auftrag einen vollständig erfolgreichen Apply voraussetzen.
Produktionsdeploy **skipped**, keine Produktion.

KI-Kontrollzentrum separat: nativer Recorder und Describe/Plan wurden regulär
versucht; die native Zuordnung fehlte. Keine IDs, Eingangsnachweise oder
Stop-Ereignisse rekonstruiert; keine Abschlussbewertung für den Teilzustand.

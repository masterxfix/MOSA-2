# Phase 2 – CHECK-Korrektur und zweiter isolierter Apply

**Ergebnis: teilweise, keine technische Schemafreigabe. Issue #7 bleibt offen.**
Ausgangscommit: `727278dfedb40de16174179172a33ee711a4026a`.
Apply: **2026-10-18 13:15:42 UTC**. Genau ein Apply in diesem Auftrag.
Der historische erste Versuch in `PHASE2_APPLY_ATTEMPT.md` bleibt unverändert.

## CHECK-Ursache und nachgewiesene Korrektur

Der frühere Tokenvergleich entfernte `_utf8mb4` nur unmittelbar vor einem
normalen Anführungszeichen. Der echte Server liefert in INFORMATION_SCHEMA
jedoch zusätzliche Backslashes vor den Literalbegrenzern:

```text
(`status` in (_utf8mb4\'active\',_utf8mb4\'inactive\',_utf8mb4\'archived\'))
```

SHOW CREATE TABLE liefert dagegen:

```text
CONSTRAINT `ck_entities_status` CHECK ((`status` in (_utf8mb4'active',_utf8mb4'inactive',_utf8mb4'archived')))
```

Die Byteprüfung bestätigte `5c27` (Backslash + Apostroph), nicht nur JSON-Escaping.
Die vollständige ursprüngliche Diagnose einschließlich SHOW CREATE und
Vergleichsentscheidung ist in `PHASE2_CHECK_DIAGNOSTIC.json` gesichert.
Dies erklärt den alten Parserfehler; ein fehlerhafter DDL-CHECK wurde nicht
nachgewiesen. Die Migration blieb bytegleich, SHA-256:
`9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`.

Der gemeinsame Parser konsumiert jeden Token und bildet einen Ausdrucksbaum.
Klammern werden ausschließlich gemäß Parserstruktur behandelt; Priorität,
AND/OR-Struktur, Operatoren, Reihenfolge, Bezeichner und Literalinhalt bleiben
erhalten. Unbekannte Syntax führt zur Abweichung, nicht zum Ignorieren.

Die nach Live-Beobachtung ergänzte Regel akzeptiert ausschließlich vollständige
`_utf8mb4`-Literale mit unverändertem ASCII-Kleinbuchstabeninhalt oder leerem
Inhalt. INFORMATION_SCHEMA-Delimiter und SHOW-CREATE-Delimiter werden getrennt
gelesen. Voraussetzung sind qualifizierte Server-/Session-Einstellungen und
dreifache Übereinstimmung mit Migration und SHOW CREATE. Andere Zeichensätze,
Escapes im Inhalt, veränderte Werte, Funktionen oder Logik bleiben abgewiesen.
Die [MySQL-Dokumentation zu Introducern](https://dev.mysql.com/doc/refman/8.0/en/charset-introducer.html)
beschreibt deren Zeichensatz-/Kollationswirkung; deshalb gibt es kein pauschales
Entfernen beliebiger Introducer.

Nach positiven und negativen Regressionstests wurde nur der Postcheck am bereits
angelegten Schema fortgesetzt: kein DROP und kein zweiter Apply für diese Korrektur.

## Live-Nachweise und Grenze

Preflight: bestehende isolierte Testdatenbank, korrekte Identität/Version/Port,
0 Tabellen, keine Routinen/Trigger/Events, unveränderte Grants, FK-Prüfung an,
UTC, UTF8 und strikter Session-Modus. Keine globalen Änderungen.

Der vollständige Strukturcheck bestätigte:

- 13 Tabellen und 96 Spalten mit Typen, NULL-Regeln, Defaults und AUTO_INCREMENT;
- InnoDB, UTF8, Tabellen- und Maschinenfeldkollationen;
- 13 Primary Keys, 7 Unique Keys, 16 sekundäre Indizes;
- 14 Foreign Keys samt Zielen und RESTRICT-Regeln;
- alle 9 erzwungenen CHECKs einschließlich dreifachem Ausdrucksvergleich.

Der praktische Test erreichte danach `wrong_rejection:foreign_key`.
Der damalige Prüfer erwartete 1452 bei einer Änderung des Primärschlüssels eines
bereits durch Identifier/Routen referenzierten Assets. Dieser Test vermischte
fehlenden Parent mit RESTRICT-Abhängigkeiten. Die tatsächlich empfangene Nummer
wurde vom damaligen Fehlerwrapper nicht erhalten; **1451 ist eine begründete
Erklärung, kein gesicherter Live-Messwert**.

Die vorhergehenden Status-/Boolean-/Attempt-Prüfungen liefen bis zu diesem Punkt
ohne Ausnahme. Ihre Einzelergebnisse wurden beim Abbruch nicht zurückgegeben;
kein vollständiges Constraint-Testat. Die 11 EXPLAINs und der Ledger-Schritt
wurden nicht erreicht. Kein Ledger-Eintrag angelegt.

Der gemeinsame Prüfer verwendet jetzt einen neuen Relationship-Kinddatensatz mit
fehlendem Parent. Eine unerwartete Fehlernummer wird künftig explizit erhalten,
ohne vertraulichen Datenbank-Fehlertext. Offline-Regressionsprüfungen decken beide
Korrekturen ab. Diese FK-Korrektur ist **noch nicht live bestätigt**.

Der Fehlerpfad rollte die synthetische Transaktion zurück und entfernte seine
13 Tabellen in umgekehrter FK-Reihenfolge nach exaktem Eigentümerschaftsabgleich.
Bericht: 0 Tabellen übrig. Kein erneuter Apply nach diesem Rückbau.
Restore-Testdatenbank und Produktion blieben unberührt.

## Reproduzierbarkeit

Gemeinsamer Code: `scripts/phase2/postcheck.php`, `check_expression.php` und
`password_gateway.php`; Regressionstests: `tests/test_check_expression.py`.
Kein Deployment-Hook. Nur für ausdrücklich autorisierte isolierte Testläufe.
`--apply-postcheck` lehnt einen begonnenen Lauf ab; `--resume-postcheck` verlangt
den dokumentierten CHECK-Prüfhalt, dieselben 13 eigenen leeren Tabellen und
denselben Migrationsdigest. Resume führt keine CREATEs aus.

Das HTTPS-Einmalformular wurde vor der Passworteingabe durch einen echten
Origin-/Cookie-/CSRF-POST ohne Passwort geprüft. Ein maskiertes Feld; eine
erfolgreiche Übernahme. Kein Passwortreset und keine neue Datenbank.

## Kontrollzentrum

Regulären Recorder benutzt. Describe/Plan für den echten Auftrag wurden einmal
versucht und mit `No open laboratory order for this exact native turn`
abgewiesen. Erfassungslücke separat, keine erfundenen Ereignisse oder IDs und
keine Abschlussbewertung für diesen unvollständigen Auftrag.

## Offline-Prüfungen

- 9 neue Testmethoden mit positiven/negativen Unterfällen erfolgreich;
  darunter PHP-Lints sämtlicher Phase-2-Dateien und Erhalt unerwarteter Errnos.
- Alle 23 bestehenden Phase-2-Schema-Tests erfolgreich.
- Gesamtlauf unter Windows: 56 Tests, davon 55 erfolgreich; bestehender
  Phase-1B-Test scheitert an POSIX-Dateirechten (`budget_not_private`). Ein
  zusätzlicher Sandbox-Tempdateifehler entfiel außerhalb der Sandbox.
- Deployment-Paketprüfung: 1 unveränderte Webdatei erfolgreich validiert.
- Kein produktives Deployment. Die entsprechende Konsolenausgabe der
  Deployment-Unit-Tests stammt vom simulierten Transport.

## Abschließende Bereinigung

Unabhängige neue Verbindung bestätigte am **2026-10-18 13:27:33 UTC** erneut
0 Tabellen sowie die unveränderten Preflight-Grenzen. Anschließend wurden
ausschließlich die vollständig abgeglichenen eigenen privaten/public Dateien
entfernt: Passwort, Zugriffskonfiguration, Formular, SQL-Kopie, Prüfskripte,
Berichte und Locks. Private und öffentliche Laufverzeichnisse entfernt.
Die neutrale Teststartseite blieb hashgleich.
Anschließend: temporärer Einstieg HTTP 404; neutrale Startseite HTTP 200 und
unverändert. Ungespeichertes Plesk-Formular abgebrochen; weiterhin dieselben
9 bestehenden Aufgaben, keine neue dauerhafte Aufgabe.

Ein zusätzlicher Web-Download für die Diagnose wurde vom Sicherheitsprüfer
blockiert und nicht ausgeführt. Die Originaldiagnose wurde stattdessen vollständig
über die autorisierte Plesk-Ausgabe gelesen und lokal gesichert. Keine Secrets
oder Verbindungsdaten in dieser Diagnose.

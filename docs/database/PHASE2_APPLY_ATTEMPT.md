# Phase 2 – kontrollierter Apply-Versuch vom 18.10.2026

**Ergebnis: teilweise; keine technische Schema-Freigabe.** Issue #7 bleibt offen.
Start: `50e04b019fd864347965e74ee468b0e78e0c00d6`.
Apply-Beginn: **2026-10-18 11:18:16 UTC** (13:18:16 Europe/Berlin).

## Nachgewiesener Preflight

- Ausschließlich bestehende isolierte Testdatenbank `h29077_mosa2_test`;
  authentifiziert als `h29077_mosa2_test@localhost`.
- PDO-Verbindung über `127.0.0.1:3307`, Server `8.0.26-16`.
- Vor DDL exakt 0 Tabellen.
- Bestehende Grants unverändert: global ausschließlich USAGE; ALL PRIVILEGES
  ausschließlich auf dem exakt maskierten Schema `h29077\_mosa2\_test`.
- Session UTC `+00:00`, utf8mb4 / utf8mb4_0900_ai_ci,
  FOREIGN_KEY_CHECKS=1, strikter Modus aus Phase 1:
  STRICT_TRANS_TABLES, ERROR_FOR_DIVISION_BY_ZERO, NO_ZERO_DATE,
  NO_ZERO_IN_DATE, NO_ENGINE_SUBSTITUTION, ONLY_FULL_GROUP_BY.
- Keine globalen Einstellungen, Rechte oder Benutzer verändert.
- Unveränderte SQL-Datei aus dem Startcommit, providerseitiger SHA-256:
  `9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd`.

## Apply und Abbruch

Alle **13 CREATE TABLEs** der unveränderten Migration wurden in gespeicherter
FK-Reihenfolge von MySQL erfolgreich ausgeführt. Kein SQL-Syntaxfehler trat auf.

Der anschließende Struktur-Postcheck brach mit dem internen Vergleichsfehler
`check_expressions:m2_entities` ab. `mysql_error` war NULL: der Fehler entstand
im Testcode beim Abgleich der CHECK-Ausdrücke, nicht als MySQL-DDL-Fehler.
Die genaue vom Server gelieferte CHECK-Darstellung wurde vor dem Abbruch nicht
im Fehlerbericht erhalten. Deshalb ist weder eine fachliche CHECK-Abweichung
noch ein reiner Normalisierungsfehler bewiesen. Keine großzügigere
Vergleichsregel nachgeschoben, kein blinder zweiter Apply.

Die vorherigen Metadatenprüfungen der ersten Tabelle liefen durch; daraus folgt
**keine vollständige Bestätigung des gesamten Schemas**. Praktische Constraint-
Tests und die elf EXPLAIN-Prüfungen wurden nicht mehr erreicht. Der Ledger wurde
nicht befüllt. Keine Performance-, Produktions- oder weitere Testfreigabe.

## Sicherer Fehlerzustand

Der Testlauf entfernte ausschließlich seine 13 erfolgreich angelegten Tabellen
in umgekehrter FK-Reihenfolge. Vor dem Entfernen wurde die vollständige Menge
der vorhandenen Tabellen mit der Liste der eigenen erfolgreichen CREATEs
abgeglichen; Foreign-Key-Prüfungen blieben eingeschaltet.
Der Fehlerbericht bestätigte **0 verbleibende Tabellen** und keinen
Eigentümerschaftsblocker. Keine synthetischen Fachdaten wurden eingefügt.
Die Restore-Testdatenbank wurde weder verbunden noch verändert.

Erneute unabhängige Leerstandsprüfung und Ressourcenbereinigung:
**2026-10-18 11:20:01 UTC**. Passwort, private Konfiguration, Testcode,
SQL-Kopie, Berichte, Sperrdateien und öffentlicher Einstieg wurden vollständig
aus den ausschließlich für diesen Lauf angelegten Verzeichnissen entfernt.
Danach Einstieg HTTP 404, neutrale Teststartseite HTTP 200 und unveränderter
Git-Blob-Hash `333a115eb2d83a45d7ff0a6a27709826a1a4e94c` bestätigt.
Die Plesk-Aufgabenliste enthält weiterhin dieselben neun bestehenden Aufgaben;
keine neue dauerhafte Aufgabe wurde gespeichert.

Der neue, nicht vollständig live validierte Postcheck-Prototyp wird nicht als
fertiger Repository-Testcode veröffentlicht. Die sechs vorab erfolgreichen
Offline-Vertragstests/PHP-Lints dieses Prototyps ersetzen keinen Live-Nachweis.
Die ursprüngliche Migration, Spezifikation und bisherigen Schema-Tests bleiben
unverändert. Ein Folgeauftrag muss zuerst den Vergleich mit vollständiger
Fehlerdiagnostik korrigieren, bevor ein erneuter kontrollierter Apply erfolgen darf.

## Zugang und Kontrollzentrum

Das Passwort wurde ausschließlich über ein maskiertes, IP-/Host-/HTTPS-/POST-/
Origin-/CSRF-geschütztes Einmalformular übernommen und privat temporär mit 0600
gespeichert. Ein Formularfehler (`Referrer-Policy: no-referrer`) wurde vor der
erfolgreichen Übernahme auf `same-origin` korrigiert; die strikte Origin-Prüfung
blieb erhalten. Deshalb war eine zusätzliche Nutzereingabe notwendig.

Regulärer Recorder aufgerufen. Describe/Plan für den tatsächlichen Auftrag
wurden mit `No open laboratory order for this exact native turn` abgewiesen.
Diese bekannte Erfassungslücke ist vom fachlichen Postcheck-Fehler getrennt;
keine vollständige Kontrollzentrum-Sichtbarkeit und keine Abschlussbewertung.

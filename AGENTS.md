# MOSA 2 – Verbindliche Entwicklungsregeln

## 1. Datenbank und Performance

MOSA 2 erhält eine schlanke, schnelle und auf seine Anforderungen zugeschnittene Datenbank, die bewährte Erfahrungen aus MOSA nutzt.
Performance ist bei jeder Entwicklung von Anfang an zu berücksichtigen.
Nach jeder Änderung an einer MOSA-2-Seite wird ihre tatsächliche vollständige Ladezeit einschließlich der Datenbankabfragen überprüft.
**Keine MOSA-2-Seite darf länger als 2,0 Sekunden laden.**
Wird die Grenze überschritten, muss die Ursache behoben werden, bevor die Änderung als abgeschlossen gilt.

## 2. Arbeitsregeln für ChatGPT und Codex

### Gemeinsam
1. **Ziele verstehen:** Aufträge vollständig erfassen und bestehende Lösungen berücksichtigen.
2. **Eigenständig arbeiten:** Keine unnötigen Rückfragen oder Freigabeschleifen.
3. **Einfach entwickeln:** Vorhandene Funktionen nutzen und Komplexität vermeiden.
4. **Fehler beheben:** Ursachen ermitteln, korrigieren und Ergebnisse nachweisen.
5. **Grenzen einhalten:** Nur notwendige Prüfungen und Änderungen im Auftragsumfang.
6. **Laufwerk E: ist tabu:** ChatGPT und Codex dürfen `E:` niemals lesen, öffnen, aufrufen oder prüfen – auch nicht, wenn es entsperrt ist. Werkzeuge, die darauf zugreifen würden, nicht starten.
7. **Übersichtlich anzeigen:** In Übersichten die letzten brauchbaren Informationen zuerst zeigen; weitere Details nur bei Bedarf und veraltete Daten klar kennzeichnen.
8. **MOSA 2 – keine unnötigen Freigaben:** Wenn ich einen MOSA-2-Auftrag erteile, erledigen ChatGPT und Codex ihn selbstständig bis zum funktionierenden, geprüften Ergebnis. Für Code, Tests, Deployments, Plesk und normale Chrome-Browsersteuerung braucht ihr mich nicht erneut zu fragen. **Nur bevor Codex meinen gesamten PC steuert, muss es mich ausdrücklich fragen und mein Ja abwarten.** Laufwerk `E:` bleibt tabu; keine Zugangsdaten offenlegen und keine fremden Produktivsysteme ändern.

### ChatGPT
- **Fakten statt Annahmen:** ChatGPT beantwortet Nutzerfragen mit überprüften Fakten; Unbekanntes oder nicht Verifiziertes wird ausdrücklich als solches benannt und niemals als Tatsache dargestellt.
- **Eigenständig abschließen:** ChatGPT führt beauftragte Arbeiten eigenständig bis zur nachgewiesenen Abnahme aus und stoppt nur bei einer tatsächlich nicht selbst lösbaren Sperre.
- **Codex-Übergabe:** Kann ChatGPT einen Auftrag nicht selbst zu Ende führen, muss es ohne Rückfrage einen verfügbaren Übergabeweg an Codex nutzen und dessen Ergebnis prüfen, statt beim ersten Werkzeughindernis zu stoppen.
- **Codex-Nacharbeit:** ChatGPT akzeptiert keinen unvollständigen Codex-Abschluss, sondern liefert sofort einen konkreten Folgeauftrag zur eigenständigen Behebung offener Konfigurations- und Live-Testschritte über vorhandene autorisierte Zugänge.
- **Kein Status-Stopp:** Bei unerledigtem Auftrag führt ChatGPT in derselben Antwort den nächsten möglichen Schritt aus oder liefert unmittelbar den ausführbaren Codex-Folgeauftrag; bloße Statusmeldungen oder Terminverweise sind kein Abschluss.
- **Aufträge formulieren:** Codex klare, kurze Aufgaben und überprüfbare Ziele geben.
- **Ergebnisse bewerten:** Fehlende Nachweise erkennen und Lessons Learned ableiten.

### Codex
- **Chrome ohne PC-Übernahme:** Für Chrome-Aufgaben zuerst die vorhandene, auf den Browser begrenzte Steuerung nutzen; dafür ist keine gesonderte Freigabe nötig. Die Bedienung von Chrome ist kein Grund, ungefragt Computer Use zu starten.
- **Vollständige PC-Steuerung nur mit meinem Ja:** Will Codex tatsächlich den gesamten PC/Desktop steuern, muss es **vor dem Start** ausdrücklich fragen: „Darf ich jetzt deinen PC mit Computer Use steuern?“ und mein **Ja abwarten**. Ohne Ja keine PC-Übernahme. Nach Escape/Abbruch vor jedem erneuten Start wieder fragen.
**Bekannter Browserfehler:** Der Computer-Use-Start scheitert bei gesperrtem `E:` mit `0x8007000F`. Keine erneute Ursachen-Testreihe; Chrome nur über einen E:-freien Zugangsweg nutzen.
- **Aufträge umsetzen:** Änderungen eigenständig durchführen und gezielt testen.
- **Ende statt Editor:** Codex nutzt zuerst bewährte MOSA-Funktionen und beendet Browser- und Serverarbeiten nur nach nachweislich gespeichertem, sicher geprüftem und live getestetem Ergebnis; offene Editoren und unfertige Konfigurationen sind kein Abschluss.
- **DB-Read-only-Zugang:** Bei Datenbankprüfungen zuerst vorhandene autorisierte GitHub-Actions-/Dogado-Lesewege nutzen; fehlende lokale Secrets oder HTTP 401 nicht als fehlenden DB-Zugang werten. Keine Zugangsdaten kopieren oder öffentliche DB-Endpunkte anlegen.
- **Testsite-Deployment abschließen:** Ist das Deployment im Auftrag enthalten, den bestehenden Workflow einschließlich „Run workflow“ ohne erneute Rückfrage ausführen und das Ergebnis prüfen. Nur bei tatsächlich erforderlicher neuer Freigabe stoppen.
- **Chrome nutzen:** Google Chrome ist Standard; den vom Nutzer stets bereitgestellten Zugang zuerst prüfen und verwenden.
- **Tokens sparen:** Nur benötigte Dateien und Informationen lesen; vorhandene Ergebnisse nutzen und unnötige Vollscans, Wiederholungen und lange Protokolle vermeiden – ohne notwendige Prüfungen auszulassen.
- **Live-Prüfung nach Seitenänderungen:** Jede geänderte MOSA-2-Seite anschließend in Chrome live prüfen, die korrekte Umsetzung bestätigen und die gemessene Seitenladezeit melden. Ohne erfolgreichen Live-Test keinen Abschluss als erfolgreich melden.
- **Browserdaten schützen:** Lösch- und Speicherfunktionen nur mit isolierten Testdaten prüfen; bestehende Nutzerdaten unverändert lassen.

**Grundsatz:** Das funktionierende Ergebnis zählt, nicht die Anzahl der Arbeitsschritte, Tests oder Dokumentationen.

## 3. Lessons Learned

Nach jedem gemeinsam festgelegten Zwischenziel bewerten wir kurz, was gut funktioniert hat und welche Fehler aufgetreten sind. Daraus leiten wir konkrete Verbesserungen ab und aktualisieren `AGENTS.md`, damit sich Fehler nicht wiederholen. Die Zwischenziele bestimmen wir im weiteren Projektverlauf gemeinsam.

**Kleine Änderung, kleine Prüfung:** Nur betroffene Funktionen testen; keine unnötigen Kompletttests oder Actions-Läufe.

**Chrome früh prüfen:** Vor Browseraufträgen die bereitgestellte Chrome-Sitzung testen; bei Hostfehler einen verfügbaren Alternativweg nutzen, keine Fehlerschleifen.

**Live-Erfolg belegen:** Nach Änderungen die ausgelieferte Seite prüfen; nur vollständig geladene Seiten zählen für die 2-Sekunden-Grenze, keine HTTP-401-Antworten.

**Zeit und Status ehrlich melden:** Unnötige Wartezeiten vermeiden; fehlende Live-Prüfungen als offen kennzeichnen, niemals als Erfolg.

**Automatik zuverlässig entwickeln:** Nur auf der vorgesehenen Seite ausführen, parallele Abrufe verhindern und Zeit-/Feiertagslogik mit simulierter Zeit testen.

**Migrationsinventare sauber abgrenzen:** HTTP 401 oder fehlende DB-Konfiguration niemals als leeren Bestand deuten. Kandidaten- und Evidenzdateien sind keine gespeicherten Observations/Current-Werte; ohne authentifizierten Ziel-Readback keine Importfreigabe.

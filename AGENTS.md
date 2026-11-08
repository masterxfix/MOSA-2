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

### ChatGPT
- **Aufträge formulieren:** Codex klare, kurze Aufgaben und überprüfbare Ziele geben.
- **Ergebnisse bewerten:** Fehlende Nachweise erkennen und Lessons Learned ableiten.

### Codex
**Bekannter Browserfehler:** Der Computer-Use-Start scheitert bei gesperrtem `E:` mit `0x8007000F`. Keine erneute Ursachen-Testreihe; Chrome nur über einen E:-freien Zugangsweg nutzen.
- **Aufträge umsetzen:** Änderungen eigenständig durchführen und gezielt testen.
- **Chrome nutzen:** Google Chrome ist Standard; den vom Nutzer stets bereitgestellten Zugang zuerst prüfen und verwenden.
- **Tokens sparen:** Nur benötigte Dateien und Informationen lesen; vorhandene Ergebnisse nutzen und unnötige Vollscans, Wiederholungen und lange Protokolle vermeiden – ohne notwendige Prüfungen auszulassen.
- **Live-Prüfung nach Seitenänderungen:** Jede geänderte MOSA-2-Seite anschließend in Chrome live prüfen, die korrekte Umsetzung bestätigen und die gemessene Seitenladezeit melden. Ohne erfolgreichen Live-Test keinen Abschluss als erfolgreich melden.

**Grundsatz:** Das funktionierende Ergebnis zählt, nicht die Anzahl der Arbeitsschritte, Tests oder Dokumentationen.

## 3. Lessons Learned

Nach jedem gemeinsam festgelegten Zwischenziel bewerten wir kurz, was gut funktioniert hat und welche Fehler aufgetreten sind. Daraus leiten wir konkrete Verbesserungen ab und aktualisieren `AGENTS.md`, damit sich Fehler nicht wiederholen. Die Zwischenziele bestimmen wir im weiteren Projektverlauf gemeinsam.

**Kleine Änderung, kleine Prüfung:** Nur betroffene Funktionen testen; keine unnötigen Kompletttests oder Actions-Läufe.

**Chrome früh prüfen:** Vor Browseraufträgen die bereitgestellte Chrome-Sitzung testen; bei Hostfehler einen verfügbaren Alternativweg nutzen, keine Fehlerschleifen.

**Live-Erfolg belegen:** Nach Änderungen die ausgelieferte Seite prüfen; nur vollständig geladene Seiten zählen für die 2-Sekunden-Grenze, keine HTTP-401-Antworten.

**Zeit und Status ehrlich melden:** Unnötige Wartezeiten vermeiden; fehlende Live-Prüfungen als offen kennzeichnen, niemals als Erfolg.

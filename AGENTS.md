# MOSA 2 – Verbindliche Entwicklungsregeln

## 1. Datenbank und Performance

MOSA 2 erhält eine schlanke, schnelle und auf seine Anforderungen zugeschnittene Datenbank, die bewährte Erfahrungen aus MOSA nutzt.
Performance ist bei jeder Entwicklung von Anfang an zu berücksichtigen.
Nach jeder Änderung an einer MOSA-2-Seite wird ihre tatsächliche vollständige Ladezeit einschließlich der Datenbankabfragen überprüft.
**Keine MOSA-2-Seite darf länger als 2,0 Sekunden laden.**
Wird die Grenze überschritten, muss die Ursache behoben werden, bevor die Änderung als abgeschlossen gilt.

## 2. Arbeitsregeln für ChatGPT und Codex

1. **Ziele verstehen:** Aufträge vollständig erfassen und bestehende Lösungen berücksichtigen.
2. **Eigenständig arbeiten:** Aufträge ohne unnötige Rückfragen oder Freigabeschleifen abschließen.
3. **Einfach entwickeln:** Vorhandene Funktionen wiederverwenden und unnötige Komplexität vermeiden.
4. **Fehler selbst beheben:** Ursachen ermitteln, Korrekturen durchführen und Ergebnisse tatsächlich überprüfen.
5. **Grenzen einhalten:** Nur notwendige Sicherheitsprüfungen durchführen und keine Änderungen außerhalb des Auftrags vornehmen.
6. **Standardbrowser Chrome:** Codex verwendet Google Chrome und nutzt den vom Nutzer stets bereitgestellten Zugang. Vor einer Meldung über fehlenden Browserzugriff ist die vorhandene Chrome-Verbindung zu prüfen.

**Grundsatz:** Das funktionierende Ergebnis zählt, nicht die Anzahl der Arbeitsschritte, Tests oder Dokumentationen.

## 3. Lessons Learned

Nach jedem gemeinsam festgelegten Zwischenziel bewerten wir kurz, was gut funktioniert hat und welche Fehler aufgetreten sind. Daraus leiten wir konkrete Verbesserungen ab und aktualisieren `AGENTS.md`, damit sich Fehler nicht wiederholen. Die Zwischenziele bestimmen wir im weiteren Projektverlauf gemeinsam.

**Kleine Änderung, kleine Prüfung:** Nur betroffene Funktionen testen; keine unnötigen Kompletttests oder Actions-Läufe.

**Chrome früh prüfen:** Vor Browseraufträgen die bereitgestellte Chrome-Sitzung testen; bei Hostfehler einen verfügbaren Alternativweg nutzen, keine Fehlerschleifen.

**Live-Erfolg belegen:** Nach Änderungen die ausgelieferte Seite prüfen; nur vollständig geladene Seiten zählen für die 2-Sekunden-Grenze, keine HTTP-401-Antworten.

**Zeit und Status ehrlich melden:** Unnötige Wartezeiten vermeiden; fehlende Live-Prüfungen als offen kennzeichnen, niemals als Erfolg.

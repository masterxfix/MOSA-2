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

**Grundsatz:** Das funktionierende Ergebnis zählt, nicht die Anzahl der Arbeitsschritte, Tests oder Dokumentationen.

## 3. Lessons Learned

Nach jedem gemeinsam festgelegten Zwischenziel bewerten wir kurz, was gut funktioniert hat und welche Fehler aufgetreten sind. Daraus leiten wir konkrete Verbesserungen ab und aktualisieren `AGENTS.md`, damit sich Fehler nicht wiederholen. Die Zwischenziele bestimmen wir im weiteren Projektverlauf gemeinsam.

**Änderungen klein prüfen:** Nur passende Tests durchführen; Deployment-Workflows für kleine HTML-Änderungen von unnötigen Kompletttests entlasten.

**Browserzugang früh prüfen:** Vor einem verpflichtenden Live-Test zuerst sicherstellen, dass Codex eine authentifizierte Chrome-Sitzung tatsächlich steuern kann. Bei Hostfehler einen verfügbaren Alternativweg nutzen oder die Prüfung offen melden, statt erfolglose Versuche zu wiederholen. HTTP 401 zählt nicht als Ladezeitmessung.

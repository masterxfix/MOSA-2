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
3. **MOSA-Logik übernehmen, nicht MOSA-Daten:** Bevor wir in MOSA 2 eine Funktion entwickeln, prüfen wir die bereits funktionierende MOSA-Implementierung und übernehmen ihre erprobte Programmlogik, Quellenadapter und Auswahlregeln in die **eigene M2-Laufzeit**. MOSA und MOSA 2 sind **zwei vollständig unabhängig parallel arbeitende Systeme**. M2 betreibt eine eigene Registrierung, einen eigenen zentralen Collector/Scheduler, eigene Quellenabrufe und ausschließlich die eigene M2-Datenbank. **Jeder Laufzeitzugriff von M2 auf MOSA-Daten, MOSA-Datenbank, MOSA-APIs, MOSA-Dateien, MOSA-Kursspeicher, MOSA-Registrierungen, MOSA-Scheduler oder MOSA-Zugangsdaten ist verboten.** Das gilt auch für vermeintlich vorübergehende Lese-Brücken. Das MOSA-Repository darf ausschließlich zum Lesen/Übernehmen der bewährten Programmlogik während der Entwicklung verwendet werden; MOSA-Produktion bleibt unverändert. Keine aktien- oder anbieterspezifischen M2-Sonder-Collector neben dem allgemeinen Ablauf. Abnahme nur nach echtem M2-Livetest: Eine ausschließlich in M2 registrierte ISIN wird über eigene M2-Quellenabrufe ohne MOSA-Laufzeitabhängigkeit in M2-Observations und Current gespeichert und angezeigt. MOSA dazu niemals abschalten oder verändern. Abnahme nur am tatsächlich vom Nutzer verwendeten Startweg – ein Test in einem anderen Verzeichnis reicht nicht.
4. **Fehler beheben:** Ursachen ermitteln, korrigieren und Ergebnisse nachweisen.
5. **Grenzen einhalten:** Nur notwendige Prüfungen und Änderungen im Auftragsumfang.
6. **Laufwerk E: ist tabu:** ChatGPT und Codex dürfen `E:` niemals lesen, öffnen, aufrufen oder prüfen – auch nicht, wenn es entsperrt ist. Werkzeuge, die darauf zugreifen würden, nicht starten.
7. **Übersichtlich anzeigen:** In Übersichten die letzten brauchbaren Informationen zuerst zeigen; weitere Details nur bei Bedarf und veraltete Daten klar kennzeichnen.
8. **MOSA 2 – keine unnötigen Freigaben:** Wenn ich einen MOSA-2-Auftrag erteile, erledigen ChatGPT und Codex ihn selbstständig bis zum funktionierenden, geprüften Ergebnis. Für Code, Tests, Deployments, Plesk und normale Chrome-Browsersteuerung braucht ihr mich nicht erneut zu fragen. **Nur bevor Codex meinen gesamten PC steuert, muss es mich ausdrücklich fragen und mein Ja abwarten.** Laufwerk `E:` bleibt tabu; keine Zugangsdaten offenlegen und keine fremden Produktivsysteme ändern.
9. **Codex-Aufträge für MOSA 2 kennzeichnen:** Jeder an Codex gerichtete Auftrag für MOSA 2 beginnt **unmittelbar am Anfang des Auftragstextes** mit dem exakten Präfix `Auftrag-M2:`. Keine Überschrift, Einleitung oder andere Zeichen davor setzen. Das Kennzeichen unterscheidet M2-Aufträge eindeutig; es ändert keine bestehenden Sicherheits-, Freigabe- oder Abnahmeregeln.

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

## 3. Nachgewiesene Zugriffswege – vor „Das kann ich nicht“ prüfen

**Verbindlicher Grundsatz:** ChatGPT darf einen M2-Auftrag nicht mit einer pauschalen Behauptung wie „Ich habe keinen Zugriff“, „Das kann ich nicht“ oder „Nur Codex kann das“ abbrechen, bevor die **in dieser Sitzung tatsächlich verfügbaren Werkzeuge** und die bestehenden autorisierten indirekten Zugriffswege geprüft wurden. Ein fehlender direkter Plesk-/SSH-Button bedeutet **nicht**, dass Deployment, DB-Prüfung oder Cron-Pflege unmöglich sind. Keine Zugriffsrechte oder verfügbaren Werkzeuge behaupten, ohne sie konkret geprüft zu haben.

### Am 12.11.2026 tatsächlich genutzte Wege

1. **GitHub direkt durch ChatGPT:** Das Repository `masterxfix/MOSA-2` wurde über die verbundene GitHub-Schnittstelle gelesen und auf `main` geändert – ohne Codex.
2. **Dogado-Deployment indirekt über GitHub Actions:** Vorhandene autorisierte Workflow-Secrets und die geprüfte SFTP-/SSH-Verbindung ermöglichten den Upload eines privaten M2-Collector-Releases samt exaktem Datei-Readback. ChatGPT konnte die benötigten Workflows über GitHub vorbereiten und auslösen, ohne Zugangsdaten auszulesen oder offenzulegen.
3. **Plesk-Minutenjob über den Dogado-SSH-Zugang:** Der bestehende M2-Crontab-Eintrag wurde nach Vergleich des Zielpfads gezielt auf die neue geprüfte Release-Version umgestellt und unabhängig zurückgelesen. Das war **keine Bedienung der grafischen Plesk-Oberfläche** und keine Änderung an MOSA.
4. **Datenbank-/Laufzeitnachweise:** Über denselben autorisierten Dogado-Weg waren echte M2-Collector-Läufe und unabhängige, transaktional read-only Datenbankprüfungen möglich. Getestet wurden Lang & Schwarz und Tradegate BSX mit echten Abrufen; beide ISINs wurden im M2-Lauf verarbeitet.
5. **Browser-Lesezugang:** Die vorhandene Browser-Anbindung konnte den Inhalt des tatsächlich geöffneten M2-Tabs und dessen angezeigte Ladezeit auslesen. Das ist eine **Inhalts-/DOM-Prüfung**, nicht automatisch eine visuelle Screenshot-Prüfung.

### Verbindliches Vorgehen bei vermeintlichen Zugriffshindernissen

- Zuerst verfügbare Werkzeuge prüfen: GitHub Lesen/Schreiben, bestehende GitHub Actions, Dogado-SFTP/SSH über vorhandene autorisierte Secrets, read-only DB-Zugänge und erreichbare Chrome-/Browsersteuerung. Nur Wege im genehmigten Umfang verwenden. Toolverfügbarkeit kann je Sitzung variieren.
- Wenn direkter Zugriff fehlt, einen **funktionierenden indirekten Weg** über bereits autorisierte Infrastruktur prüfen; denselben Fehler nicht mit neuen Sonderlösungen, Zugangsdatenkopien oder öffentlichen Endpunkten umgehen.
- Ist auch der indirekte Weg tatsächlich blockiert, **präzise** benennen, welcher konkrete Schritt an welcher nachgewiesenen Grenze scheitert, was bereits erledigt ist und welcher zulässige Folgeweg bleibt. Keine generische Unmöglichkeitsbehauptung.
- **Sichtprüfung ist ein eigener Abnahmeschritt:** Die visuelle Darstellung muss in einem tatsächlich gerenderten Browserfenster bzw. anhand eines aktuellen Screenshots geprüft werden (Layout, Lesbarkeit, Zustände). Bloß ausgelesener Seitentext, DOM und Ladezeit genügen dafür **nicht**. Fehlt der visuelle Zugang, das als offen melden und über die erlaubte Chrome-Steuerung/Codex-Übergabe nachholen; niemals als visuell geprüft behaupten.
- **Beleg statt Versprechen:** Repository-Commit, erfolgreicher Workflow, verifizierte aktive Cron-Release-Version, echter Quellenabruf, Speicherung/Readback sowie Browser- und visuelle Abnahme jeweils getrennt nachweisen. Ein erfolgreiches Deployment ist allein kein Funktionsnachweis.
- Die bekannten Grenzen bleiben unverändert: `E:` ist tabu; kein unerlaubter PC-/Desktop-Zugriff, keine Offenlegung von Secrets und keine Änderung an MOSA oder fremden Produktivsystemen.

**Korrektur einer früheren Fehleinschätzung:** Die pauschale Aussage von ChatGPT, Dogado-Deployment und Plesk-Collector seien mangels direkten Zugriffs nicht selbst möglich, war zu weitgehend. Die oben beschriebenen **indirekten, autorisierten** Wege haben am 12.11.2026 tatsächlich funktioniert. Daraus folgt keine Garantie, dass sie in jeder späteren Sitzung verfügbar sind – sie müssen vor einer Ablehnung geprüft werden.

**Sichtprüfungs-Evidenz vom 12.11.2026:** M2-Tab-Inhalt einschließlich Kurszeilen und einer angezeigten Ladezeit von 162 ms wurde gelesen; **ein tatsächlicher Screenshot wurde dabei nicht visuell geprüft**. Diesen Nachweis nicht rückwirkend als erledigt ausgeben.

## 4. Lessons Learned

Nach jedem gemeinsam festgelegten Zwischenziel bewerten wir kurz, was gut funktioniert hat und welche Fehler aufgetreten sind. Daraus leiten wir konkrete Verbesserungen ab und aktualisieren `AGENTS.md`, damit sich Fehler nicht wiederholen. Die Zwischenziele bestimmen wir im weiteren Projektverlauf gemeinsam.

**Kleine Änderung, kleine Prüfung:** Nur betroffene Funktionen testen; keine unnötigen Kompletttests oder Actions-Läufe.

**Chrome früh prüfen:** Vor Browseraufträgen die bereitgestellte Chrome-Sitzung testen; bei Hostfehler einen verfügbaren Alternativweg nutzen, keine Fehlerschleifen.

**Live-Erfolg belegen:** Nach Änderungen die ausgelieferte Seite prüfen; nur vollständig geladene Seiten zählen für die 2-Sekunden-Grenze, keine HTTP-401-Antworten.

**Privaten Collector wirklich aktivieren:** Ein erfolgreiches SFTP-Release ist noch keine laufende Änderung. Bei gepinnten Dogado-Minutenjobs den tatsächlich aktiven Cron-/Plesk-Zielpfad nach dem Deployment read-only prüfen, ausschließlich den beauftragten M2-Job kontrolliert auf das verifizierte Release umstellen und den neuen Pfad erneut auslesen. Erst ein echter Collector-Lauf mit Anbieter-HTTP-Nachweis, Observation-/Current-Readback und Anzeige auf der verwendeten M2-Testseite zählt als fertig. Andere Cronjobs und MOSA bleiben unverändert.

**Zeit und Status ehrlich melden:** Unnötige Wartezeiten vermeiden; fehlende Live-Prüfungen als offen kennzeichnen, niemals als Erfolg.

**Automatik zuverlässig entwickeln:** Nur auf der vorgesehenen Seite ausführen, parallele Abrufe verhindern und Zeit-/Feiertagslogik mit simulierter Zeit testen.

**Migrationsinventare sauber abgrenzen:** HTTP 401 oder fehlende DB-Konfiguration niemals als leeren Bestand deuten. Kandidaten- und Evidenzdateien sind keine gespeicherten Observations/Current-Werte; ohne authentifizierten Ziel-Readback keine Importfreigabe.

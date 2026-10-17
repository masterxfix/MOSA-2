# Sicherheitsvorfall 2026-10-17 – Codex / Laufwerk E:

**Status:** offen · Meldung an OpenAI vorbereitet · BSI-Meldung vorgesehen  
**Einstufung:** möglicher Privacy-/Security-Boundary-Fehler  
**Betroffene Umgebung:** Windows · ChatGPT Desktop / Codex · interner Browser  

## Kurzfassung

Während einer ausschließlich browserbasierten, read-only Dogado-Prüfung scheiterte der Codex-Browserzugriff wiederholt, solange das fachlich unbeteiligte und BitLocker-geschützte Laufwerk `E:` vorhanden und gesperrt war.

Nach dem Entsperren von `E:` funktionierte der Browserzugriff ohne erkennbare Änderung an Browser-, Dogado- oder Codex-Einstellungen. Nachdem `E:` später dauerhaft aus dem System entfernt worden war, funktionierte der Browserzugriff weiterhin und die Dogado-Prüfung konnte erfolgreich abgeschlossen werden.

Daraus ergibt sich eine reproduzierbare und nicht akzeptable Abhängigkeit zwischen der Codex-/Browser-Werkzeuginitialisierung und einem für den Auftrag vollständig irrelevanten, vertraulichen lokalen Laufwerk.

Dieser Befund beweist **nicht**, dass Dateien oder Inhalte von `E:` gelesen oder übertragen wurden. Er begründet aber den Verdacht, dass eine lokale Werkzeug-, Sandbox- oder Launcher-Komponente verfügbare Laufwerke enumeriert, initialisiert oder in eine Berechtigungslogik einbezieht.

## Bestätigte Beobachtungen

- Dogado war im internen Browser geöffnet und angemeldet.
- Die Aufgabe erforderte ausschließlich eine read-only Prüfung der Dogado-Weboberfläche.
- Für die Aufgabe war kein Zugriff auf lokale Dateien oder Laufwerke erforderlich.
- Laufwerk `E:` war BitLocker-verschlüsselt, streng vertraulich und fachlich vollständig unabhängig von MOSA, Codex, Dogado und dem Browserauftrag.
- Solange `E:` vorhanden und gesperrt war, scheiterte die Codex-/Browser-Werkzeuginitialisierung wiederholt vor dem Zugriff auf die vorhandene Browser-Sitzung.
- Zuvor ausgegebene Diagnosen bezogen sich auf eine unerwünschte `E:`-Initialisierung bzw. eine lokale Tool-/Launcher-Laufzeit.
- Browser-, Dogado- und Browser-Use-Einstellungen wurden nicht verändert.
- Nach dem Entsperren von `E:` funktionierte der Zugriff auf die bereits vorhandene angemeldete Dogado-Sitzung.
- `E:` wurde anschließend dauerhaft aus dem System entfernt.
- Nach der Entfernung funktionierte der Browserzugriff weiterhin.
- Die account-spezifische Dogado-Prüfung wurde danach erfolgreich abgeschlossen.
- Um ca. 13:25 Uhr wurde der erfolgreiche Abschluss der Dogado-Prüfung gemeldet.
- Um ca. 13:33 Uhr wurde der Browserzugriff erneut geprüft.
- Dabei waren alle drei vorhandenen Browser-Tabs erreichbar und die angemeldete Dogado-Seite „Backups – Sicherheit“ lesbar.
- Es wurden bei diesen Prüfungen keine Dogado-Einstellungen oder Daten verändert.

## Reproduzierbarer Zusammenhang

```text
E: vorhanden und gesperrt
→ Codex-/Browser-Werkzeugzugriff scheitert

E: entsperrt
→ Browserzugriff funktioniert

E: dauerhaft entfernt
→ Browserzugriff funktioniert weiterhin
```

## Nicht bewiesen

Folgende Aussagen werden ausdrücklich **nicht** als Tatsache behauptet:

- Es ist nicht bewiesen, dass Dateiinhalte von `E:` gelesen wurden.
- Es ist nicht bewiesen, dass Datei- oder Verzeichnisnamen erfasst wurden.
- Es ist nicht bewiesen, dass Metadaten von `E:` gelesen wurden.
- Es ist nicht bewiesen, dass Daten von `E:` an OpenAI übertragen wurden.
- Es ist nicht bewiesen, dass absichtliche Ausspähung stattgefunden hat.
- Es ist nicht bewiesen, dass dauerhaft alle Laufwerke überwacht werden.

## Sicherheits- und Datenschutzbewertung

Bereits die Abhängigkeit eines Browserwerkzeugs von einem sachfremden, vertraulichen Laufwerk ist problematisch.

Ein Werkzeug für eine Webaufgabe darf nicht voraussetzen, dass unbeteiligte lokale Laufwerke entsperrt, lesbar oder initialisierbar sind. Auch eine rein technische Enumerierung, Metadatenerfassung oder Berechtigungsinitialisierung kann eine unzulässige Überschreitung der erwarteten Vertrauens- und Arbeitsgrenze darstellen.

Der Vorfall wird daher als möglicher Privacy-/Security-Boundary-Fehler behandelt und an OpenAI gemeldet. Eine Meldung an das BSI ist ebenfalls vorgesehen.

## Chronologie

1. Dogado-Qualifikationsauftrag mit bereits geöffneter und angemeldeter Browser-Sitzung gestartet.
2. Codex meldete mehrfach fehlenden Browserzugriff bzw. scheiternde Tool-/Launcher-Initialisierung.
3. Hinweise auf eine unerwünschte Abhängigkeit von Laufwerk `E:` wurden sichtbar.
4. Mehrere alternative Erklärungen zu Browserkontext, Chrome/Opera oder Einstellungen erwiesen sich als unzutreffend.
5. `E:` wurde testweise entsperrt.
6. Ohne erkennbare Änderung an Browser oder Dogado funktionierte der Browserzugriff.
7. `E:` wurde anschließend dauerhaft aus dem System entfernt.
8. Der Browserzugriff funktionierte weiterhin.
9. Die Dogado-Kontoprüfung wurde erfolgreich abgeschlossen.
10. Browserzugriff wurde danach erneut erfolgreich bestätigt.

## Relevante MOSA-2-Nachweise

- Dogado-Abschlusscommit: [`294e570de0bb284e629139f5082d59a5dc6ea68d`](https://github.com/masterxfix/MOSA-2/commit/294e570de0bb284e629139f5082d59a5dc6ea68d)
- GitHub Issue #4 wurde nach erfolgreicher account-spezifischer Prüfung geschlossen.
- Die vertrauliche Laufwerksgrenze ist zusätzlich in `AGENTS.md` und `docs/security/README.md` dokumentiert.

Screenshots und Chatverläufe existieren als weitere Beweismittel. Sie werden wegen möglicher sensibler Inhalte nicht ungeprüft in das Repository geladen.

## Bereits ergriffene Maßnahmen

- Laufwerk `E:` wurde dauerhaft aus dem System entfernt.
- Weitere unnötige Reproduktionstests wurden beendet.
- `E:` wurde verbindlich aus dem MOSA-/Codex-Arbeitsbereich ausgeschlossen.
- Lokale Daten und Laufwerke dürfen für MOSA-Aufträge nicht enumeriert, initialisiert oder verwendet werden.
- Der Vorfall wird nicht als bewiesener Datendiebstahl dargestellt, sondern als technisch zu untersuchender Sicherheits- und Datenschutzgrenzen-Vorfall.

## Fragen an OpenAI

OpenAI soll insbesondere beantworten:

1. Enumerieren ChatGPT Desktop, Codex, der interne Browser, MXC, Launcher oder Sandbox-Komponenten lokale Laufwerke bei Start oder Berechtigungsinitialisierung?
2. Welche konkreten Operationen wurden gegen Laufwerk `E:` versucht?
3. Wurden Laufwerkskennung, Dateisystem, BitLocker-Status, Kapazität, freier Speicher, Verzeichnisnamen, Dateinamen, Dateimetadaten oder Dateiinhalte gelesen?
4. Wurden Informationen zu `E:` lokal verarbeitet oder an OpenAI übertragen?
5. Welche Client- und Serverlogs können die tatsächlichen Zugriffe belegen?
6. Warum scheiterte der Browserzugriff bei gesperrtem `E:`, funktionierte aber nach Entsperrung bzw. Entfernung?
7. Wie kann ein lokales Laufwerk dauerhaft technisch von sämtlichen ChatGPT-/Codex-Werkzeugen ausgeschlossen werden?
8. Ist dieses Verhalten bekannt, beabsichtigt oder dokumentiert?
9. Kann OpenAI schriftlich bestätigen, welche Daten oder Metadaten tatsächlich verarbeitet oder übertragen wurden?

## Geplanter Meldeweg

1. Offizielle Meldung an OpenAI Support bzw. Security.
2. Ticket-/Report-ID, Absendezeitpunkt und Antwort sichern.
3. Zusätzlich Security-Meldung über den von OpenAI vorgesehenen Schwachstellenkanal, soweit passend.
4. Anschließend Meldung an das BSI mit Bezug auf die OpenAI-Ticketnummer und den dokumentierten reproduzierbaren Zusammenhang.
5. Weitere Stellen werden erst nach Auswertung der ersten Reaktionen festgelegt.

---

# Vorbereiteter englischer Bericht an OpenAI

## Subject

**Potential privacy/security boundary issue: Codex browser tooling depended on unrelated encrypted drive E:**

## Report

I am reporting a potential privacy and security boundary issue involving the ChatGPT Desktop / Codex browser tooling on Windows.

### Executive summary

Codex browser access to an already open and authenticated internal browser session repeatedly failed while an unrelated BitLocker-encrypted drive E: was present and locked.

The requested task was a read-only inspection of a Dogado web account and required no access to local files or drives.

After drive E: was unlocked, browser access succeeded without any relevant change to the browser or Dogado configuration.

Drive E: was later permanently removed from the system. Browser access continued to work and the Dogado inspection was completed successfully.

This creates a reproducible correlation between the state or presence of an unrelated confidential local drive and the availability of the Codex browser tooling.

### Confirmed observations

- Windows system using ChatGPT Desktop / Codex and the integrated browser.
- Incident date: 17 October 2026, Europe/Berlin timezone.
- Dogado was already open and authenticated in the integrated browser.
- The task required only read-only browser access.
- No local file or drive access was required for the task.
- Drive E: was BitLocker-encrypted, strictly confidential and unrelated to MOSA, Codex, Dogado or the browser task.
- While E: was present and locked, Codex repeatedly failed before accessing the existing browser session.
- Earlier diagnostic messages referred to local tool or launcher initialization involving drive E:.
- No relevant browser or Dogado settings were changed.
- After E: was unlocked, access to the existing authenticated Dogado browser session succeeded.
- E: was later permanently removed from the system.
- Browser access continued to function after its removal.
- The Dogado account inspection was then completed successfully.
- At approximately 13:25 local time, Codex reported successful completion.
- At approximately 13:33 local time, browser access was tested again.
- Codex reported that all three existing tabs were reachable and that the authenticated Dogado page “Backups – Sicherheit” was readable.
- No account changes were made.

### Expected behavior

Browser access to an existing authenticated web session must not depend on the state or presence of an unrelated local drive.

Codex should not enumerate, initialize, inspect or require access to local drives that are outside the requested task and project scope.

### Observed behavior

- E: present and locked: browser/tool initialization failed.
- E: unlocked: browser access succeeded.
- E: removed from the system: browser access continued to succeed.

### Security and privacy concern

This behavior suggests that a Codex or browser-tooling component may enumerate or initialize available local drives, or include them in a permissions or sandbox setup step.

It is currently unknown whether filenames, directory names, drive metadata, encryption status, free-space information, file metadata or file contents were accessed, processed or transmitted.

I am not claiming that file contents were accessed or exfiltrated. I am requesting a technical investigation and written clarification.

### Questions requiring investigation

1. Does ChatGPT Desktop, Codex, the integrated browser tooling, MXC, a launcher or a sandbox component enumerate all available local drives during startup or permissions initialization?
2. What exact system calls or operations were attempted against drive E:?
3. Were any of the following accessed: drive name or identifier, encryption or BitLocker status, filesystem type, free-space or capacity information, directory names, filenames, file metadata or file contents?
4. Was any information from drive E: processed by an OpenAI component?
5. Was any information related to drive E: transmitted to OpenAI systems?
6. Which local and server-side logs are available to determine exactly what was accessed?
7. Why did browser access fail while E: was locked but succeed after it was unlocked or removed?
8. How can a local drive be permanently excluded from every ChatGPT Desktop and Codex tool?
9. Is this behavior known, intended or documented?
10. Can OpenAI confirm in writing whether any data or metadata from E: was accessed or transmitted?

### Requested response

Please:

- assign an incident or ticket number;
- preserve relevant client and server logs;
- perform a technical security and privacy investigation;
- confirm the exact access attempted against drive E:;
- confirm whether any information was transmitted;
- provide a method to permanently exclude unrelated drives;
- notify me of the investigation result in writing.

### Evidence

Screenshots are available showing:

- repeated Codex/browser failures while E: was locked;
- the authenticated Dogado page already open in the integrated browser;
- browser settings already enabled;
- successful browser access after E: was unlocked;
- successful browser access after E: was permanently removed;
- successful completion of the Dogado account inspection;
- later confirmation that all three browser tabs were reachable.

Sensitive information in screenshots will be redacted before attachment.

## Noch einzutragende Angaben vor dem Absenden

- genaue Windows-Version;
- genaue ChatGPT-Desktop-Version;
- sichtbare Codex-/Tool-Version, falls verfügbar;
- Konto-/Tarifbezeichnung;
- exakter Absendezeitpunkt;
- Ticket-/Report-ID;
- Liste der tatsächlich beigefügten, geschwärzten Screenshots.

# Historische Fundamentaldaten auf Anfrage

Die Testsite zeigt standardmäßig Geschäftsjahre ab 2025. Die Zeitraumwahl
filtert gespeicherte Ergebnisse sofort. Ältere Observations bleiben abrufbar.
Ein Klick auf „Fehlende Berichte anfordern“ erzeugt eine begrenzte Anfrage
für eine aktive Aktie, bis zu zehn Geschäftsjahre und FY, FQ oder beide Typen.
Die Testsite-Anmeldung, HTTPS und der eigene Browser-Origin sind Voraussetzung.
Ein ETF kann keine Anfrage erzeugen.

## Ausführung

Der Web-Endpunkt verwendet dieselbe lesende DB-Konfiguration wie die
Fundamentaldatenansicht. Er legt eine private Anfrage unterhalb des bereits
geprüften Collector-Verzeichnisses ab. Derselbe Anmeldekontext und Zeitraum
liefern dieselbe ID. Die Oberfläche liest Status und nach Bestätigung den
gespeicherten Bestand separat. Der Seitenaufbau wartet nur auf den Leseweg.

Der Workflow [MOSA-2 testsite historical fundamentals](../../.github/workflows/fundamentals-history.yml)
verwendet den bestehenden gepinnten Testsite-SSH-/DB-Zugang. In `main` richtet
`setup` das private Verzeichnis ein. `process` akzeptiert eine konkrete
Anfrage-ID. Beide manuellen Operationen binden die Autorisierung an den exakten
Main-Commit nach dem Muster `MOSA2-HISTORY-<operation>:<commit>:<request_id>`.
Für `setup` bleibt der Teil nach dem letzten Doppelpunkt leer.

Die optionale Repository-Variable `MOSA2_HISTORY_ENABLED=true` lässt denselben
Workflow zweimal pro Stunde höchstens eine authentifizierte Anfrage übernehmen.
Der Takt startet bei leerer Warteschlange weder einen DB-Import noch einen
Providerabruf. GitHub bestimmt die tatsächliche Startzeit des geplanten Jobs.

Jede Übernahme und jede Berichtsreservierung bleiben dauerhaft nachvollziehbar.
Der Worker verarbeitet maximal acht Berichte pro Job, prüft vor dem Abruf
die vorhandenen Kennzahl-/Perioden-Slots und liest den Bestand nach der
Qualifikation erneut. Ein vollständig vorhandener Slot erzeugt keinen
erneuten Import. Eine laufende oder unklare Anfrage bleibt beansprucht.
Ein späterer Versuch darf erst nach unabhängiger Prüfung separat autorisiert
werden. Frühere Einmal-Executions sind von den neuen Berichtsreservierungen
getrennt.

## Quellen und fachliche Grenzen

Der Worker verwendet die bestehende Berichtsregistrierung und die ESEF-Profile.
Die historische ESEF-Ergänzung ist ein Quellenprofil, das denselben LEI-, Namen-,
Konsolidierungs-, Perioden-, Einheiten- und Evidence-Vertrag benutzt.
Die Auswahl legt ein Geschäftsjahr auf seinen Originalbericht fest.
Spätere Vorjahresspalten können einen geänderten Konsolidierungskreis abbilden
und sind für diese Auswahl ausgeschlossen. Abweichende Werte, Einheiten oder
Periodengrenzen in schon belegten Slots stoppen die betroffene Übernahme.
YTD ist ein eigener fachlicher Typ und wird nicht als FQ gespeichert. Snapshots
bleiben als Stichtagswerte erkennbar. Unbelegte Werte bleiben offen.

Die Anfrage akzeptiert alle aktiven Aktien. Automatische Berichtsabrufe sind
auf qualifizierte offizielle Profile begrenzt. Für ungeprüfte Publikationsorte,
unbekannte Formate und zusätzliche Quartale wird eine Quellenlücke gemeldet.
Der vorhandene HTML-Tabellen- und Evidence-Weg kann auch offizielle
Ergebnismeldungen mit explizitem Spaltenvertrag nutzen. OHB liefert damit
FY 2023–2025 und die separat bezeichneten ersten Quartale 2025 und 2026.
In der Q1-2026-Meldung angepasste Q1-2025-Vergleichswerte ersetzen den
ursprünglichen Q1-2025-Bericht nicht. Neue qualifizierte Profile erweitern
denselben Weg.

## Nachprüfung

Der generische Fundamental-Writer prüft die Evidenz erneut, speichert nur
qualifizierte Lücken und schreibt mit `publish_current=false`. Der Readback
verwendet eine andere DB-Verbindung im Read-only-Modus. Er prüft die neuen
Fakten, sämtliche erwarteten Deltas, unveränderte Current-Zuordnungen und
Fremdbestände sowie den History-Index und dessen Laufzeit.

Die lokalen Tests decken vollständige und teilweise vorhandene Zeiträume,
Wiederholungen, Quellenlücken, Konflikte, Vergleichsspalten, Stichtage und
YTD, Current-Schutz, einen manipulierten Readback und Fehler nach Commit ab.
Die Seitenladezeit in der Ansicht umfasst Navigation und Darstellung der
gespeicherten Daten. Die Dauer eines separat angeforderten Jobs ist davon
unabhängig.

## Testsite-Nachweise vom 09.11.2026

- [PR #55](https://github.com/masterxfix/MOSA-2/pull/55) enthält den Worker,
  die Ansicht und die Quellenprofile. Der fokussierte Testlauf nach der
  OHB-Erweiterung umfasst 92 erfolgreiche Tests.
- Das [erste Web-Deployment](https://github.com/masterxfix/MOSA-2/actions/runs/42658515269)
  von `0c22044` verifizierte alle vier Testsite-Dateien per SHA-256. Chrome
  zeigte auf dem regulären Startweg 156 ms einschließlich Datenabruf und
  bei NEL 17 Observations und 13 Current-Zuordnungen.
- Das [zweite Web-Deployment](https://github.com/masterxfix/MOSA-2/actions/runs/42659513043)
  verifizierte die vier korrigierten Dateien erneut per SHA-256. Chrome zeigte
  **173 ms einschließlich Datenabruf**. Die Auswahl FY2024 machte die drei
  gespeicherten NEL-Jahreswerte unmittelbar sichtbar.
- NEL FY2023 war im Browser leer. Die authentifizierte Anfrage erreichte
  den Endpunkt. Der Worker war auf diesem Stand noch nicht eingerichtet,
  weshalb die Anfrage nicht gespeichert wurde. Das ist kein Importnachweis.
- Das [offizielle NEL-ESEF-Paket](https://nelhydrogen.com/press-release/nel-asa-annual-report-2023/)
  mit SHA-256 `42cb2ff57f8614ba840d668584dd4f584fc0b9ab7ea427a28232d472e003dcd0`
  lieferte isoliert drei belegte FY2023-Flusswerte. Der PHP-Evidence-Vertrag
  und der transaktionale Test ohne Current-Schreibvorgang bestanden.
- Der vorhandene Einmaltransport und der isolierte PHP-Evidence-Test
  bestätigten fünf offizielle OHB-Tabellen. OHB erschien nicht unter den
  neun aktiven Aktien der Testsite. Die Qualifikation war ein Offline-Test
  des Schreibpfads mit echten öffentlichen Berichten.
- Der [unabhängige Read-only-Lauf](https://github.com/masterxfix/MOSA-2/actions/runs/42659760276)
  bestätigte den unveränderten Testbestand von 17 NEL-Observations und
  13 Current-Zuordnungen. Jede vorhandene NEL-Zeile und alle Fingerprints
  der Fremd- und Marktdaten stimmten mit dem vorherigen Readback überein.
  Es gab keine FY2023-Observation, keinen Providerabruf und keinen DB-Write.
- Für die Live-Abnahme sind der reguläre Merge, die einmalige private
  Einrichtung, eine authentifizierte FY2023-Anfrage und der unabhängige
  Read-only-Vergleich gegen den [vorigen NEL-Readback](https://github.com/masterxfix/MOSA-2/actions/runs/42652866710)
  erforderlich. Erwartet werden drei zusätzliche FY2023-Observations bei
  unverändert 13 Current-Zuordnungen sowie unveränderte Fremd- und Marktdaten.

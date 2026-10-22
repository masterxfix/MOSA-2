# Gemeinsamer Collector-Zyklus: ausschließlich Simulation

Stand 22.10.2026, Ausgangsrevision `665738a`. Kein Scheduler und keine Live-Anbindung.

| Stand | Aussagegrenze |
| --- | --- |
| Bestehender Collector | Funktionale Einmalläufe sind bereits belegt; seine Implementierung und das installierte Release bleiben unverändert. |
| Gemeinsame Ablaufsteuerung | `scripts/collector_cycle.py` kombiniert die vorhandenen Betriebsplan-, Budget- und Monitoringentscheidungen als reine In-Memory-Funktion. |
| Lokaler Dry-Run | `scripts/collector_cycle_dry_run.py` liest ein explizites JSON von stdin und gibt ausschließlich einen technischen Simulationsbericht aus. Keine Uhrschleife, kein Prozessstart, kein Transport oder DB-Modul. |
| Rechte, Grenzen, Baseline | Keine neuen realen Freigaben: Providerrechte, belastbare Providerlimits und frische MOSA-Baseline fehlen weiterhin. |
| Kontingentsicherheit | Keine atomare Reservierung, kein dauerhafter Zähler und kein persistenter Lock implementiert. `atomic_reservation=false`, `execution_authorized=false`. |

Beide bestehenden Konfigurationen bleiben bytegleich, `execution_enabled=false`,
`rights_confirmed=false`. Die positive Testfixture enthält ausschließlich als
synthetisch bezeichnete Rechte-/Limit-/Kalenderannahmen im Arbeitsspeicher. Sie
ist weder eine Änderung der Konfiguration noch eine Ausführungsfreigabe.

## Versionierter gemeinsamer Zeitvertrag

`mosa2-collector-operation-plan-v1` bleibt als historischer Vertrag unverändert:
Handelsfenster, feste Intervalle und Überspringen geschlossener Tage. Die alten
Tests bleiben erhalten. Der neue gemeinsame Dry-Run verlangt ausdrücklich
`mosa2-collector-operation-plan-v2` mit `schedule_policy=BERLIN_60_900_V1`.
Eine v1-Eingabe wird nicht stillschweigend umgedeutet.

V2 verwendet die gemeinsamen Scope-, Qualifikations-, Kalender-, Zustands- und
Budgetprüfungen des Betriebsplaners. Seine Schlüssel entsprechen v1, jedoch
entfallen `weekdays`, `windows`, `interval_seconds`; stattdessen ist
`schedule_policy` erforderlich. Der Takt wird zentral in
`collector_operation_plan.cadence_seconds/is_slot` definiert. Budget-Lastmodell
und gemeinsame Simulation verwenden genau diese Funktionen.

Europe/Berlin, lokale halb offene Fenster: Montag–Freitag [06:00, Folgetag 00:00)
60 Sekunden; nachts, am Wochenende und an bekannten Feiertagen 900 Sekunden.
Im explizit genehmigten, datierten Kalender sind `open_dates` unter v2 bekannte
normale Tage und `closed_dates` bekannte Feiertage mit langsamem Takt. Diese
Bedeutung gilt ausschließlich für v2. Fehlende Daten, widersprüchliche Listen,
fehlende Kalenderzustimmung im Budgetvorschlag oder fehlende Abdeckung blockieren,
auch am Wochenende. Feiertagsdefinition und Freigabe werden nicht erfunden.

Nur exakt ausgerichtete UTC-Minuten-/Viertelstundenpunkte sind Kandidaten.
Die UTC-Laufkennung unterscheidet die wiederholte Berliner Stunde im Herbst;
es entstehen 92/100 eindeutige langsame Zyklen an den DST-Sonntagen. Keine
nachgeholten Zyklen, kein Start zwischen Taktpunkten und keine Parallelität.
Ein aktiver/ungeklärter Vorgänger blockiert; verpasste Taktpunkte verfallen.
Nach Abschluss eines langen Laufs kann erst ein neuer zukünftiger Taktpunkt
in Betracht kommen. Abschlusszeit und Receipt müssen zusammenpassen. Bei
Überschreitung der konfigurierten maximalen Laufdauer ist Prüfung erforderlich.
Auch Mitternacht wechselt korrekt vom schnellen zum langsamen Raster.
`next_theoretical_at` ist ein strikt zukünftiger theoretischer Taktpunkt, keine
Freigabe; bei unbekanntem Folgetagskalender bleibt er null.

## Zulassung, MOSA-Schutz und Stopps

Der Zyklus verlangt fünf eindeutige Aktien in erhaltener Reihenfolge sowie die
vorhandene frische vollständige `USE_EXISTING_ROUTE`-/Equity-/Venue-Qualifikation.
Die Attestierung ist injiziert und ersetzt keine spätere DB-/Runtime-Prüfung.
Zustand und Qualifikation müssen frisch sein; aktive, fehlgeschlagene, ungeklärte,
doppelte oder widersprüchlich belegte Vorgänger blockieren. Die bestehende
Receipt-Projektion verbirgt unbekannte Vorgänge nicht hinter späterem Erfolg.

`provider_budget_plan.admission` prüft weiterhin eigene und kombinierte Grenzen,
frische Providerzähler und MOSA-Baseline, MOSA-Vorrang und höchstens einen
gleichzeitigen MOSA-2-Request. `simulation=True` untersucht diese Voraussetzungen
trotz deaktivierter Ausführung, erzeugt aber keine Berechtigung. Dokumentierte
Providerlimits sind zusätzlich zwingend: `documented_provider_limit` enthält
`evidence_ref`, `per_60s`, `per_day`, `parallel`. Kombinierte interne Grenzen dürfen
diese nachgewiesenen Werte nicht übersteigen. Positive Testwerte sind ausschließlich
synthetische Annahmen; fünf Requests pro Zyklus sind nur eine interne Obergrenze.

Der gemeinsame Pfad nutzt `observe(strict=True)`: 429 mit optionalem, lediglich
beratendem Retry-After, 401/403, Timeout, Fehlertrend, überhöhte Latenz, ungültige
Payloads, Dedupe-/Provenance-Konflikte und MOSA-Beeinträchtigung setzen die
MOSA-2-Stoppsperre. Fehlende Pflichttelemetrie blockiert. Die bestehenden v1-
Monitoringtests mit ihren historischen Schwellen bleiben erhalten. Eine spätere
200-Antwort oder das Verstreichen von Retry-After hebt die Sperre nicht auf.
Keine Reset-Funktion, automatische Wiederaufnahme, Umgehung oder Wiederholung.
`monitoring_state` kann nur als Simulationszustand in den nächsten Aufruf
zurückgegeben werden; echte dauerhafte Speicherung ist nicht implementiert.

Optionale `simulated_attempts` modellieren einen sequenziellen Präfix der
Assetliste (`asset`, `outcome=SUCCESS|FAILED|TIMEOUT`), stoppen beim ersten Fehler
und zählen auch gescheiterte Versuche. Ein zweiter Versuch derselben Aktie im
gleichen Zyklus wird anhand des expliziten simulierten Ledgers abgewiesen.
Es werden weder Requests ausgeführt noch Budgets reserviert. Die Ausgabe nennt
simulierte Zähler getrennt von stets null tatsächlichen Requests. Fehler halten
die simulierte Stoppsperre gesetzt; ein Admission-Ergebnis ist kein Lauf-Erfolg.

## Lokal ausführen und prüfen

JSON-Eingabe: `now` mit Zeitzone, `operation_config` v2, `budget_config` sowie
`evidence` mit `operation_state`, `qualification`, `budget_state`, `mosa_baseline`,
`monitoring_previous`, `monitoring_event`, `receipts`; optional `simulated_attempts`.
Die vollständige synthetische Eingabe ist in `tests/test_collector_cycle.py:fixture`
nachvollziehbar. Kein Secret, Kurswert oder echter Provideraufruf wird benötigt.
Beispiel in PowerShell mit der lokalen Python-Testumgebung:

```powershell
$env:PYTHONPATH='.;tests'
.venv\Scripts\python.exe -B -c "import json; from test_collector_cycle import fixture; print(json.dumps(fixture()))" | .venv\Scripts\python.exe -B scripts/collector_cycle_dry_run.py
```

Unter Linux entsprechend `python3` und `PYTHONPATH=.:tests`; unter Windows werden
IANA-Zeitzonendaten (`tzdata`) für die bestehende ZoneInfo-Abhängigkeit benötigt.
Die Ausgabe enthält Zeitpunkt, Takt, Scope, erwartete Requests, Budgetentscheidung,
Gesamtentscheidung, festen Sperrgrund und nächsten theoretischen Zyklus. Sie gibt
keine Rohantworten, Zugangsdaten, SQL oder Preise aus und täuscht keine Aktualisierung vor.

Der vorhandene manuelle Workflow `collector-release-offline.yml` erhält dafür
`verification_scope=cycle`: nur neue Zyklustests und bestehende Betriebsplan-,
Budget- und synthetische Collector-Regressionen. Ohne Secrets, Hostingkontakt,
DB-Verbindung, Releasebau oder Deployment. Der bisherige Modus `release` bleibt erhalten.

## Vor jeder späteren Live-Anbindung separat erforderlich

Rechte und belastbare Provider-/Gesamtlimits belegen; MOSA-Baseline sowie Kalender
und Scope qualifizieren. Danach Zustandsadapter, dauerhaften Stopplatch und eine
echte atomare Reservierung unter gemeinsamem Lock implementieren: Zulassung und
gesamte verfügbare Providerkapazität gemeinsam prüfen, einen Versuch vor Versand
unwiderruflich zählen, genau einen Request je Aktie zulassen, Abbrüche/ungeklärte
Ergebnisse separat abgleichen. MOSA hat Vorrang. Keine dieser Live-Voraussetzungen
wird durch erfolgreiche Offline-Tests oder RUN_ELIGIBLE ersetzt.

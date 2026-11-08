# NEL ASA – Read-only-Migrationsinventar

Stand: 2026-11-08  
Unternehmen: NEL ASA  
ISIN: `NO0010081235`  
Quellrevision MOSA: `masterxfix/fixlab` `origin/main` `33782c3614586a025daa8c9c839cba9f6e931094`  
Zielrevision MOSA 2 zum Berichtsbeginn: `270c1de507c6fff95319550820916f994967ee13`

## Ergebnisstatus

Die MOSA-Dateiquellen wurden ausschließlich lesend ausgewertet. Ein aktueller
MOSA-Datenbank-Readback war lokal nicht möglich, weil die dokumentierte
Verbindungskonfiguration nicht vorhanden war. Der MOSA-2-Fundamental-Endpunkt
auf der Testsite wurde für die konkrete ISIN ausschließlich per `GET` geprüft
und antwortete mit HTTP `401`. Damit liegt für MOSA 2 kein gültiger aktueller
Datenbank-Readback vor. Werte aus älteren Berichten oder historischen
Aktionsläufen werden ausdrücklich nicht als aktueller Bestand verwendet.

## Tatsächlich untersuchte Quellen und Grenzen

### MOSA

Untersucht wurden auf `origin/main`:

- `php/nel_fundamentals_reference.php`: strukturierte NEL-Referenzwerte,
- `data/monitoring_candidates/nel_asa_q2_2026.json`: lokaler, als
  `manual_candidate` markierter Q2-Faktenkandidat,
- `data/asset_registry.json`: Asset-Stammsatz,
- `php/nel_company_valuation_read_model.php`: Verwendung der Referenzwerte
  im bestehenden Read Model, ohne neue Abfrage,
- `php/nel_asa_lab_reader.php` und der zugehörige
  `database_connection_smoke.php`: der vorhandene Leser ist auf den
  Stammsatz `fixlab_assets` begrenzt und liefert keine Fundamentaldaten.

Die lokale fixlab-Arbeitskopie enthielt daneben bereits fremde, nicht zu
diesem Auftrag gehörende Änderungen. Sie wurde nicht verändert.

### MOSA 2

Untersucht wurden die read-only-Schnittstelle und das vorhandene Modell:

- `api/fundamentals.php`: vorhandener authentifizierter GET-Endpunkt,
- `api/fundamentals_read.php`: bounded reader mit
  `SET SESSION TRANSACTION READ ONLY`, gezielten Joins und getrennten
  `m2_fundamental_observations`-/`m2_fundamental_current`-Ergebnissen,
- `docs/database/migrations/0006_fundamentals_and_payload_provenance.sql`:
  Modell- und Bindungsdefinitionen,
- `docs/database/FUNDAMENTALS_ARCHITECTURE.md` und
  `docs/database/README.md`: fachlicher und technischer Modellvertrag.

Nicht untersucht wurden Kurs-, OHLCV-, Chart-, technische Indikator- oder
Collector-Daten. Es wurden keine Provider aufgerufen, keine Migration, kein
Collector und keine Datenbank-Schreiboperation ausgeführt.

### Konkreter Readback-Blocker

- Die dokumentierte lokale MOSA-Konfiguration
  `C:\GitHub\dashboard_neu_config\database.php` war nicht vorhanden; die
  vorgesehenen `FIXLAB_DB_*`-Umgebungsvariablen waren nicht gesetzt.
- Die lokale MOSA-2-Private-Konfiguration
  `mosa2-market-read-private/access.php` war nicht vorhanden.
- Der gezielte aktuelle Aufruf
  `https://mosa2-test.scharwerk.de/api/fundamentals.php?isin=NO0010081235`
  antwortete mit HTTP `401`. Das ist kein gültiger Datenbank-Readback.

Der Blocker ist damit ein fehlender/authentifizierter Datenzugang, nicht ein
nachgewiesener leerer MOSA-2-Datenbestand. Die tatsächliche Anzahl von
NEL-Observations, Current-Zeilen, Perioden, Quellen, Einheiten, Dubletten und
Widersprüchen in `h29077_mosa2_test` bleibt offen.

## MOSA-Bestand aus der aktuellen Repository-Revision

| Bestand | Anzahl | Zeitraum / Einordnung | Verwertbarkeit |
|---|---:|---|---|
| NEL-Asset-Stammsatz | 1 | Asset `nel_asa`, Symbol `NEL.OL`, NOK | Identität, keine Fundamentalkennzahl |
| Strukturierte Referenzwerte | 2 | Aktienzahl wirksam 2025-03-25; Eigenkapital zum 2026-06-30 | fachlich prüfbare Snapshots, aber kein Mehrjahresverlauf |
| Q2-Faktenkandidat | 1 Datensatz / 7 Faktpunkte | veröffentlicht 2026-07-15; Q2 2026, Vergleiche zu Q2 2025 und Vorquartal | bestätigte Evidenz, noch kein normierter Fundamental-Import |

### Strukturierte Referenzwerte

- Aktienzahl: `1.838.457.834`, wirksam zum 2025-03-25, im Code am
  2026-07-23 verifiziert; Quelle: Euronext Oslo / NEL-Share-Capital-Mitteilung.
- Eigenkapital: `NOK 3.601.586.000` zum 2026-06-30, Bericht veröffentlicht am
  2026-07-15; Quelle: NEL ASA Q2 and half-year 2026 report.

Diese beiden Werte sind in `nel_fundamentals_reference.php` als Referenz
gespeichert. Eine historische Aktienzahlreihe, Kapitalmaßnahmen oder ein
Verwässerungsledger ist dort nicht vorhanden.

### Q2-Faktenkandidat

Der Kandidat ist als `source_status: confirmed` und `candidate_status:
manual_candidate` gespeichert und enthält:

- Umsatz aus Kundenverträgen Q2 2026: NOK 153 Mio.; 12 % unter Q2 2025.
- EBITDA Q2 2026: NOK -155 Mio.; darin NOK 70 Mio. Belastung aus dem
  Iwatani-Vergleich.
- Auftragseingang Q2 2026: NOK 230 Mio.; 224 % über Q2 2025.
- Auftragsbestand zum Quartalsende: NOK 1.213 Mio.; 3 % unter Vorjahr und
  9 % über Vorquartal.
- Cashbestand zum Quartalsende: NOK 1.328 Mio. gegenüber NOK 1.928 Mio. im
  Vorjahr.
- NOK 296 Mio. des Auftragsbestands mit erheblichem Verzögerungs- oder
  Stornierungsrisiko.
- Ein verzögertes HYDS-Projekt mit weiter geplanter Wasserstoffproduktion
  2028.

Der Kandidat enthält keine normalisierten Einheiten-/Metric-Keys,
Observation-IDs, Feldpfade, Fetch-/Datei-Hashes oder vollständige
Periodenfelder. Er darf daher nicht stillschweigend als bereits importierte
Fundamental-History behandelt werden.

## MOSA / MOSA 2 – Kennzahlenvergleich

Die MOSA-2-Spalte ist wegen des dokumentierten 401-Blocks als **nicht
ausgelesen** markiert. „Fehlt“ bedeutet deshalb nur „in den zugänglichen
MOSA-2-Quellen nicht nachgewiesen“ und nicht „in der Datenbank sicher nicht
vorhanden“.

| Kennzahl / Bereich | MOSA-Bestand | MOSA-2 aktueller Readback | Klassifikation |
|---|---|---|---|
| Umsatz | Q2 2026: NOK 153 Mio. aus Kandidat | nicht ausgelesen | Vergleich offen; Definition „aus Kundenverträgen“ beibehalten |
| EBITDA | Q2 2026: NOK -155 Mio.; Sondereffekt beschrieben | nicht ausgelesen | Vergleich offen; Bereinigungsdefinition nicht ergänzen |
| EBIT | kein gespeicherter Wert gefunden | nicht ausgelesen | in MOSA nicht nachgewiesen |
| Jahres-/Quartalsergebnis | kein gespeicherter Wert gefunden | nicht ausgelesen | in MOSA nicht nachgewiesen |
| Operativer Cashflow / Free Cashflow | keine Werte gefunden | nicht ausgelesen | in MOSA nicht nachgewiesen |
| Liquidität / Cash | Q2 2026: NOK 1.328 Mio.; Vergleichswert NOK 1.928 Mio. | nicht ausgelesen | Vergleich offen; Quartalsend-Snapshot |
| Schulden / Finanzierungsbedarf | kein quantifizierter Wert; leerer Finanzierungsentwurf | nicht ausgelesen | in MOSA nicht verwertbar nachgewiesen |
| Auftragseingang | Q2 2026: NOK 230 Mio. | nicht ausgelesen | Vergleich offen; Periodenart muss `fq` sein |
| Auftragsbestand | Q2 2026: NOK 1.213 Mio.; Risikoqualifier NOK 296 Mio. | nicht ausgelesen | Vergleich offen; Betrag und Qualifier getrennt modellieren |
| Segmente / Produktionskapazitäten | keine belastbaren Kennzahlen gefunden | nicht ausgelesen | in MOSA nicht nachgewiesen |
| Aktienanzahl | 1.838.457.834, Snapshot mit Wirksamkeitsdatum | nicht ausgelesen | potentiell migrationsfähig, Historie fehlt |
| Kapitalmaßnahmen / Verwässerung | keine Maßnahmenhistorie gefunden | nicht ausgelesen | in MOSA nicht nachgewiesen |
| Eigenkapital | NOK 3.601.586.000 zum 2026-06-30 | nicht ausgelesen | potentiell migrationsfähig, Source-Bindung erhalten |

Dubletten, widersprüchliche Werte, konkurrierende Sources, Einheiten- oder
Währungsfehler in MOSA 2 konnten ohne die Observation-/Current-Abfrage nicht
festgestellt werden. Innerhalb der zugänglichen MOSA-Dateien wurden keine
Mehrfachversionen der zwei Referenzwerte gefunden.

## Migrationsbewertung und Prioritäten

### Priorität 0 – vor jedem Import

Den authentifizierten, read-only Zugriff auf `h29077_mosa2_test` herstellen
und je NEL-Asset gezielt `m2_assets`/`m2_asset_identifiers`,
`m2_fundamental_observations` und `m2_fundamental_current` samt Sources,
Units, Fetch-/File-Provenienz und Perioden auslesen. Erst danach darf ein
MOSA/MOSA-2-Vergleich als vollständig gelten.

### Priorität 1 – erstes kleines Importpaket

Nach erfolgreichem Readback und erneuter Quellbelegprüfung:

1. Q2 2026 Umsatz aus Kundenverträgen,
2. Q2 2026 EBITDA einschließlich separat dokumentiertem Iwatani-Effekt,
3. Q2-2026 Cashbestand,
4. Q2-2026 Auftragseingang,
5. Q2-2026 Auftragsbestand und der NOK-296-Mio.-Risikobetrag als getrennte,
   klar definierte Fakten.

Alle fünf Gruppen benötigen die offizielle Report-Datei, eindeutige
Feldpfade, `NOK`-Einheiten und `fq`-/Snapshot-Perioden. Die Kandidatendatei
allein reicht wegen fehlender Fetch-/File-Provenienz noch nicht als
Importnachweis.

### Priorität 2 – geprüfte Snapshots

Aktienzahl und Eigenkapital in das vorhandene MOSA-2-Modell übernehmen, wenn
die Quellen als reproduzierbare Evidence-Files vorliegen. Aktienzahl,
Wirksamkeitsdatum und Kapitalmaßnahmen dürfen nicht zu einer einzigen
„aktuellen“ Zahl verschmolzen werden.

### Priorität 3 – historische Analyse

Gezielt nachliefern: mehrere FY-/FQ-Werte für Umsatz, EBIT, EBITDA,
Jahres-/Quartalsergebnis, operativen Cashflow, Free Cashflow, Cash,
Schulden/Finanzierungsbedarf und Auftragseingang/-bestand. Fehlende
Kennzahlen bleiben offen; keine Schätzungen aus Prozentvergleichen.

Das vorhandene MOSA-2-Fundamentalmodell ist ausreichend: append-only
`m2_fundamental_observations`, kleine gebundene
`m2_fundamental_current`-Projektion sowie Source-/Fetch-/File-Provenienz.
Eine NEL-Sonderarchitektur ist nicht empfohlen.

## Bestätigte Ergebnisse und offene Punkte

**Bestätigt:** Zwei strukturierte MOSA-Referenzwerte, ein Q2-2026-
Faktenkandidat mit sieben Faktpunkten, keine nachgewiesene MOSA-Historie für
EBIT/Nettoergebnis/Cashflows/Schulden/Segmente/Kapazitäten und keine
Providerabrufe oder Schreiboperationen im Rahmen dieser Bestandsaufnahme.

**Offen:** Vollständiger aktueller MOSA-Datenbankbestand, vollständiger
MOSA-2-Datenbankbestand, tatsächliche MOSA-2-Zeilenanzahl, Perioden-/Unit-/
Source-Bindungen, Dubletten und fachliche Widersprüche. Diese Punkte können
nur mit einem funktionierenden authentifizierten Read-only-Zugang zur
jeweiligen Datenbank belastbar beantwortet werden.


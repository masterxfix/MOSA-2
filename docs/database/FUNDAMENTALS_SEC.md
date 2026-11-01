# SEC Company Facts: manueller FY-Pilot

Auftrag 01.11.2026, Ausgangscommit `1e205abc98ebfa5925a335f895a1bdd31d41725f`.
Vorbereitung und synthetische Tests sind kein Live-Importnachweis. Der einmalige
Actions-Bericht weist tatsächliche Abrufe, Inserts, Readbacks und Laufzeiten aus.

## Gemeinsamer Vertrag

`sec_xbrl.py` verarbeitet beliebige vorab identifizierte SEC-Emittenten. Der Parser
enthält keine NVIDIA-/Rigetti-Abzweigung. Pilotzuordnungen stehen im Runner:
NVIDIA, ISIN US67066G1040, CIK 0001045810; Rigetti Computing, ISIN US76655K1034,
CIK 0001838359. Verifikation vor Import: vorhandene aktive MOSA-Identität plus
CIK und Emittentenname der tatsächlichen Antwort; offizielle 10-K-Referenzen:
[NVIDIA FY2026](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm),
[Rigetti FY2025](https://www.sec.gov/Archives/edgar/data/1838359/000110465926023454/rgti-20251231x10k.htm).

| US-GAAP-Tag | Kennzahl | Abgrenzung |
|---|---|---|
| RevenueFromContractWithCustomerExcludingAssessedTax | revenue | Ausgewiesene Vertragserlöse ohne erhobene Steuern; kein Gesamtleistungs-Tag |
| OperatingIncomeLoss | operating_income (neu) | Kein ungeprüftes EBIT |
| NetIncomeLoss | profit_attributable_to_owners | Ergebnis der Anteilseigner, ohne nicht beherrschende Anteile |
| ProfitLoss | profit_after_tax | Gesamtergebnis einschließlich nicht beherrschender Anteile; eigener Tag, kein Synonym für NetIncomeLoss |
| NetCashProvidedByUsedInOperatingActivities | operating_cashflow | Netto-Cashflow, kein Kassenbestand |

Alle vorhandenen Katalogdefinitionen bleiben exakt gleich; USD wird unskaliert
registriert. Keine alternativen Tags werden als gleichwertig behandelt. Fehlende
Tags/Einheiten bleiben Lücken, insbesondere EBIT/EBITDA. Andere Umsatzarten und
Erweiterungstaxonomien sind nicht automatisch durch Vertragserlöse abgedeckt.
[FASB-Revenue-Leitfaden](https://xbrl.fasb.org/impguidance/Rev2_TIG/Revenue.htm).

`fy`/`fp` bezeichnen bei Company Facts das meldende Filing, auch bei Vorjahreszeilen.
Jedes angeforderte FY benötigt deshalb einen aktuellen 10-K-Anker: jüngstes
jährliches Periodenende innerhalb seines Filing-FY, eindeutiger Anfang.
Zulässig sind 364/365/366/371 Tage und zwei direkt aufeinanderfolgende FY;
Quartale und Rumpfjahre sind ausgeschlossen. Die FY-Bezeichnung wird nicht aus
dem Kalenderende erzeugt. Monatsbasierte FY/FQ bleiben unverändert validiert.
Die Analyse vergleicht zusätzlich zusammenhängende 52/53-Wochenjahre, keine
verschobenen oder unterbrochenen Vergleichsperioden.

Identische Mehrfachmeldungen werden mit ihren kompakten Herkunftsreferenzen
erhalten; die deterministische Auswahl bevorzugt den ursprünglichen aktuellen
10-K. Widersprüchliche Werte, auch 10-K/A, stoppen vor Speicherung. Es gibt keine
automatische Restatement- oder Current-Überschreibungspolitik.

## Evidence, Speicherung und Ausführung

Offizielle [API-Dokumentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[Fair Access](https://www.sec.gov/about/developer-resources) und
[User-Agent-Vorgaben](https://www.sec.gov/about/webmaster-frequently-asked-questions).
Der User-Agent enthält MOSA-2/masterxfix und die vorhandene Autoren-Kontaktadresse
des exakt ausgeführten Repository-Commits. Leere/abweichende/noreply-Adressen
stoppen vor Zugriff; keine erfundene Kontaktadresse, neue Secrets oder Abos.

Nur `fundamentals-sec-once.yml`, manuell auf main, Run 1/Attempt 1, exakte
Commitbindung und `MOSA2-SEC-FY-ONCE-20261101:<SHA>`. Je Emittent exklusiver
privater Marker; höchstens ein Company-Facts-GET, sequenziell, keine Redirects,
Retries oder Bulk-Daten. 403/429 beendet den Lauf. Kein Modellaufruf.

Antworten verbleiben im RAM (max. 16 MiB). Nur qualifizierte Fakten mit genauer
JSON-Position, CIK, ISIN-Zuordnung, Tag, Originalwert/-einheit, Perioden,
Accession, Form, Filing-Datum und Rollen (aktuell/Vergleich/Berichtigung) werden
als kompaktes Evidence gespeichert. Zeitstempel und SHA-256 der nicht erhaltenen
HTTP-Antwort bleiben separat von Größe/Hash des gespeicherten Evidence-JSON.
Keine behauptete Wiederherstellbarkeit der vollständigen Originalantwort.

Bestehende geschützte Archivfunktionen speichern ausschließlich neues Evidence;
der gemeinsame Schema-6-Writer validiert es unabhängig. Je Aktie eine atomare
Transaktion, separate Readback-Verbindung, unveränderte Altbestände, bounded
Current-/History-Abfragen mit PRIMARY/ix_fund_obs_period und EXPLAIN ANALYZE.
DB-Iteratorzeit und Clientzeit über Tunnel werden getrennt berichtet. Unbekanntes
Schreibergebnis stoppt; auch der zweite Emittent wird dann nicht begonnen.
Abschließend neuer Read-only-Snapshot und deterministische Analyse beider Aktien,
einschließlich unverändertem Assessment-Inputvalidator. Keine KI-Auswertung.

## Weitere Quellenfamilien

| Aktien | Offizieller Zugang | Gemeinsamer Ausbau |
|---|---|---|
| NEL ASA | [IR-Jahresberichte](https://nelhydrogen.com/press-release/nel-asa-annual-report-2025/), ESEF-ZIP neben PDF | ESEF/iXBRL, IFRS, Emittenten-/Konzernkontexte und Einheiten qualifizieren |
| Pandora | [IR-Jahresbericht](https://pandoragroup.com/news/27816), ESEF-Paket PAND-2025-12-31-en | Derselbe ESEF/iXBRL-Adapter |
| BYD | [IR](https://www.bydglobal.com/cn/investor-relations), HKEXnews, Aktie 01211 | Gemeinsamer HKEX-Berichtszugang; Struktur und Rechnungslegungsstandard separat qualifizieren |
| Ubtech Robotics | [Finanzberichte](https://www.ubtrobot.com/en/financial), HKEXnews, Aktie 09880 | Derselbe HKEX-Zugang, Berichtsextraktion noch nicht qualifiziert |

Nächster Ausbau: ESEF/iXBRL deckt zwei weitere Aktien strukturiert ab. HKEX deckt
ebenfalls zwei ab, benötigt jedoch zusätzlich qualifizierte Berichtsextraktion.
Diese Quellen wurden nur zugeordnet; keine vier zusätzlichen Collector gebaut
und keine weiteren Datenpakete importiert. Scheduler und Collector bleiben gesperrt.


## Umsatz-Ergänzung: Run 2 / Attempt 1

Ausgangsbestand 59/30, NVIDIA 6/3, Rigetti 8/4. Neue Autorisierung
`MOSA2-SEC-REVENUE-20261101:<SHA>`, neue private Kennungen mit Suffix `-02`;
`-01` bleibt verbraucht. Derselbe manuelle Workflow wird ausschließlich für Run 2
gebunden. Keine weiteren Workflowdateien oder KI-Aufrufe.

Die offiziellen, oben verlinkten konsolidierten 10-K-Ergebnisrechnungen zeigen
NVIDIA 215938/130497 Mio. USD, Rigetti 7088/10790 Tausend USD. Die Inline-XBRL-Tags
der Original-HTML-Berichte wurden vor dem Live-Lauf ausschließlich im Speicher
geprüft: NVIDIA `Revenues`; Rigetti enthält `RevenueFromContractWithCustomerIncludingAssessedTax`
und `Revenues`. Das bloße Vorkommen eines Tags ist kein Nachweis eines geeigneten
Konzernkontexts. Erst der tatsächliche Company-Facts-Datensatz (gesamter Emittent,
USD, qualifizierte Jahresperiode) samt Kontrollwertvergleich qualifiziert den Fakt.

`sec_revenue_reviews.json` enthält ausschließlich unabhängige Berichtskontrollen,
Tag, Zeitraum und Berichtsposition. Importwerte stammen immer aus der tatsächlichen
SEC-Antwort. Der Parser verwendet diese generischen Reviews, keine Firmennamen.
Original-Tag, SEC-Konzeptdefinition und -label sowie Review bleiben im Evidence.
Alle konkurrierenden Revenue-Tags derselben Jahresperiode müssen wertgleich sein;
andernfalls Stopp. Keine Segmentaddition oder pauschale Gleichsetzung der Tags.
Nur Umsatzfakten werden ergänzt. Bestehende Beobachtungen und Current-Referenzen
werden im abschließenden unabhängigen Snapshot vollständig verglichen.

Die frühere Bewertung der etwa 523 ms als Verletzung des SQL-20-ms-Ziels war
unzutreffend. History-Iterator ca. 0,05 ms und PRIMARY/History-Index waren bereits
bestätigt. Run 2 ergänzt je Import eine SELECT-1-Probe mit Client- und
EXPLAIN-Iteratorzeit; Current/History werden wie zuvor getrennt gemessen.
SSH-Aufbau wird zusätzlich separat berichtet. Das erlaubt die Einordnung des
Netzwerk-/Tunnelanteils, aber keine isolierte Messung jedes Netzwerksegments.
Keine Webseiten-Latenz daraus ableiten. Vor der Messung ist keine langsame SQL-
Abfrage und kein konkreter überflüssiger Roundtrip belegt; deshalb keine
Indexänderung oder spekulative Performanceoptimierung.

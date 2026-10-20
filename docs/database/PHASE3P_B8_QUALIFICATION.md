# Phase 3P – B8 ausschließlich read-only qualifiziert

**Endklassifikation: READONLY_EVIDENCE_REQUIRED.** Untersuchung abgeschlossen,
kein Import vorbereitet. Ausgangspunkt exakt
`9585438dd6f3ea1648967ea357f576fc28ee8ef5`, [Issue #32](https://github.com/masterxfix/MOSA-2/issues/32).
B8 wurde eindeutig wiedergefunden. Im hashgebundenen Phase-3O-Zielreadback gibt
es keinen passenden Identifier und damit kein belegtes bestehendes Zielasset.
Das ist fehlende Zuordnung, kein nachgewiesener Identitätswiderspruch.
Eine konkrete Legacyroute, nächste reale Routenrevision und tatsächlicher
B8-Writerplan bleiben deshalb offen. Keine Identität oder Route erfunden.

## Verwendete Evidenz und Fingerprintbindung

Nur B8 aus der eingefrorenen privaten Phase-3H-Matrix verwendet; keine neue
Kandidatenauswahl und keine erneute fachliche Analyse von B1–B7. Geprüft wurden
Matrixdatei gegen ihren Abschlussbeleg, Matrix-Selbstfingerprint, genau ein
B8-Eintrag, dessen Kandidaten-/Originalzeilenfingerprints, derselbe Kandidat im
Originalsnapshot sowie dessen gebundene Parent-Dateien. Zusätzlich stimmt der
bereits in Phase 3I gesicherte B8-Beleg exakt mit diesem Eintrag überein.

| Privater Beleg, ohne private Inhalte | SHA-256 |
| --- | --- |
| Phase-3H-Matrixdatei | `ffa86b91d7956d59463dbaa8a424c4a78027feb8a6c329b117033c0fe8944831` |
| Originalsnapshot | `2d859b76fdccef821c24c5a35716bf9ba1c11f3be7e6f68e4d68c6a4b58cad67` |
| B8-Kandidat | `727988c70a1a39bb8751b89336dd7d31d48142b3f67242e742ac6b58d8dccd20` |
| B8-Originalzeile | `7146250f9173faddd80fc577c9f51c58f1dc787a1a85dc9765bd5eb23a768ef0` |
| Phase-3O-Readback 1 und unabhängig erfasster Readback 2, jeweils | `11057b4b239955ee274cbeab12857a65c2ef0d16d8ddc40e1683931d85b8a423` |

Die Originalzeile stimmt mit der gespeicherten Quellzeile überein. Der bereits
eingefrorene same-run/asset/source/provider-Kontext enthält genau einen
zugehörigen Sourceversuch; Identifier, Providerinstrument und Venue stimmen
überein. Ursprüngliche Reasons exakt `unit_scale_required` und
`current_route_unselected`. Der Quellbezug gehört nicht zu den acht bereits
importierten Referenzen. Das allein ersetzt keinen semantischen Reimportvergleich.

Die Zielprüfung las ausschließlich die beiden vorhandenen privaten Phase-3O-
Readbackdateien, prüfte deren oben genannten Dateihash und filterte auf den
Fingerprint des B8-Identifiers. Ergebnis: **0 passende Identifier, 0 daraus
auflösbare Assets/Entities und 0 zuordenbare Assetroutes**. Die vorhandene
Source `provider:yahoo_finance_chart` hat Typ `market_data` und passt zum
historischen Provider. Keine neue aktuelle DB-Aufnahme in Phase 3P.

Ein zusätzlicher enger Vergleich prüfte den B8-Schlüssel unabhängig von der
ISIN-Auflösung: der bestehende Phase-3D-Importvertrag verwendet Rollenart
`quote` und `market-v1:` plus SHA-256 des eingefrorenen proposed_route_key.
Dieser unverändert aus dem B8-Originalreport abgeleitete Schlüssel findet
ebenfalls **0 Routen** in der vorhandenen Yahoo-Source; deren zwei bestehenden
Routen haben Rolle quote. Es wurde keine dem B8-Schlüssel widersprechende
Assetbelegung gefunden. Dies ergänzt die fehlende Identitätszuordnung, ersetzt sie
aber nicht. Die konkrete historische Providerkey-Serialisierung wird nicht als
heutige neu erzeugte Unit-/Currencykennung umgedeutet.

Private Werte, Instrumentnamen/-kennungen, numerische IDs, Quellzeilenreferenzen,
Marktwerte und konkrete historische Zeitwerte bleiben außerhalb Git. Die
Snapshots wurden nicht geändert. Browser/Plesk diente nur dem Lesen gespeicherter
Artefakte; ein eng begrenzter Lookup fand dort keine Phase-3H-Verzeichnisse,
die tatsächliche Matrix wurde anschließend lokal gefunden. Keine DB-Verbindung,
kein Gateway, Passwort, Providerabruf oder Serverupload. Keine Aufgabe gespeichert.

## Historische Producersemantik

Ausschließlich fixlab-Commit
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`, niemals heutiges main:

- [market_collection_bundle.php, Zeilen 8–9](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_collection_bundle.php#L8):
  GBp und GBX werden als GBX erhalten; Epochsekunden und explizite Offsetzeiten
  werden nach UTC mit Mikrosekunden dargestellt.
- [Zeilen 13–23](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_collection_bundle.php#L13):
  Der Yahoo-Chart-Provider prüft Symbol und Currency. Snapshot-`last_price`
  stammt aus `regularMarketPrice`, `quoted_at` aus `regularMarketTime`.
  Chart-OHLCV läuft separat über timestamp[]/indicators.quote und series=chart;
  der Snapshot erhält series=snapshot. Die Zahl wird dezimal dargestellt,
  vor Speicherung aber nicht durch 100 geteilt oder nach GBP umgerechnet.
- [mosa_market_collection_runner.php, Zeilen 56–77 und 144–148](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_collection_runner.php#L56):
  Provider, Source, registriertes Instrument und Sammelkontext werden an den
  Bundle-Normalisierer übergeben. Native Currency kommt aus geprüfter Chartmeta.
- [Zeilen 80–85 und 109–115](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_collection_runner.php#L80):
  Der getrennte FX-Pfad verwendet bei GBX einen Skalenfaktor und erzeugt eine
  ausdrücklich derived EUR-Zeile. Das verändert nicht die native Snapshotzeile.
  B8 ist laut Originalzeile market_quote/snapshot, ohne Derivation oder FX-Felder
  und ohne Barwerte. Keine Derived-/FX- oder OHLC-Zeile wird als B8 verwendet.

Die unveränderten historischen Git-Blobs der beiden Hauptdateien sind
`065c10ce6da5166ca7314f662ee57f7fbdf8e20a` und
`8c4cc8afe3b9eef28ecb50cb0251e87fbc7781ba` und stimmen mit Phase 3H überein.
Nur für den Erfassungszeitbeleg wurde zusätzlich der tatsächliche Includeweg
[source_registry, Zeile 6](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_source_registry.php#L6)
zu [mosa_market_discovery.php, Zeilen 15–18](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_discovery.php#L15)
gelesen: UTC wird ausdrücklich gesetzt. Keine Datei in fixlab geändert.

## Identität, Source und reale Route

Der Quellidentifier ist eine syntaktisch und im bisherigen Evaluator fachlich
qualifizierte globale ISIN; derselbe Identifier und Providerinstrumentkontext
stehen im eingefrorenen Sourceversuch. Dies bestätigt die Quellbindung, aber
noch keinen freigegebenen Stammdatensatz mit belegtem Namen und Assetklasse.
Im vollständigen gespeicherten Zielidentifierbestand fehlt die passende globale
Zuordnung. Kein bestehendes Asset wird anhand eines ähnlichen Tickers gewählt;
auch keine neue zweite Identität angelegt.

Die bestehende Yahoo-Source kann nach erfolgreicher Identitätsqualifikation
wiederverwendet werden. Für eine bloße Unitbindung wird keine neue Source nötig.
Mangels Zielasset ist keine konkrete B8-Legacyroute nachgewiesen. Deshalb werden
weder route_type, bestehende physische ID noch tatsächliche Revisionsnummer
behauptet. Ein vorhandener anderer Instrument-/Assetkontext ist keine Ersatzroute.

## Bedingter Sollvertrag einer späteren unit-aware Route

Nur nach eindeutiger Asset-/Source-/Routengruppenqualifikation:

| Feld | Erforderlicher Vertrag |
| --- | --- |
| Physische Route-ID | Neu; erst vom später autorisierten DB-Schritt vergeben |
| asset_id / source_id | Qualifizierte Zielidentität / vorhandene passende Source |
| route_type | Belegte bestehende fachliche Rollenart unverändert; momentan OPEN |
| external_key | Belegter historischer Providerinstrumentkey unverändert; konkrete Zielserialisierung OPEN |
| route_revision | Nächste konfliktfreie positive Revision der belegten Gruppe; reale Nummer OPEN |
| unit_contract_version | mosa2-market-unit-v1 |
| quote_unit_key / version | GBX / 1 |
| quantity_basis_unit_key / version / amount | NULL / NULL / NULL |
| volume_unit_key / version | NULL / NULL |

Falls eine qualifizierte Legacyroute vorhanden ist, bleibt sie vollständig
unverändert und bekommt keine Unitfelder nachgetragen. V2 verwendet eine neue
physische Revision. Fehlt die Routengruppe, ist ihre erstmalige Anlage ein
gesondert zu klärender Vertrag; es wird keine angeblich vorhandene Legacyroute
oder konkrete Revision erfunden. Aktuell ist eine neue physische unit-aware
Route erforderlich, die Beziehung zu einer tatsächlichen Legacyrevision offen.

[Migration 0003](migrations/0003_market_units.sql) bindet beide UNIQUEs an Revision:
Source/route_type/external_key/route_revision und
Asset/Source/route_type/route_revision. Der neue reine Offlinehelper beschreibt
für einen **bereits qualifizierten** Legacysnapshot max(Revision)+1, prüft beide
UNIQUEs, positive UINT32-Grenzen und abweichende Instrument-/Assetbindung über
Revisionen. Er erhält external_key und route_type exakt, statt Unitstrings
anzuhängen. Er vergibt keine physische ID und reserviert keine Revision in der DB.
Ein späterer Write braucht erneuten aktuellen Preflight und atomare Konfliktprüfung.
Für B8 ist diese konkrete Prüfung wegen fehlender Zielgruppe nicht ausführbar.

## Unit-, Zeit-, Volume- und Provenienzvertrag

Die vier normativen Units sind gemäß Phase 3M und Phase-3O-Finalbeleg vorhanden;
GBX@1 ist monetär, Basis GBP@1, Faktor exakt 1/100. Ziel: currency=GBP,
quote_unit=GBX@1, Vertrag mosa2-market-unit-v1 und unveränderte native Zahl P.
P/100 ist ausschließlich eine Basisprojektion in GBP, keine zweite Observation.
Keine Mengenbasis wird erfunden. Es wurde keine neue Unit angelegt.

`market_at` übernimmt das separat gespeicherte `quoted_at` gemäß UTC-
Producervertrag (Snapshotmarktzeit regularMarketTime). `observed_at` übernimmt
das davon verschiedene gespeicherte `collected_at`, den UTC-Sammel-/Erfassungs-
zeitpunkt des MOSA-Laufs. Das ist keine Behauptung eines gesondert gemessenen
Response-Endzeitpunkts. Kein Gleichsetzen, Runden oder erneuter Offsetshift.

Die Originalzeile enthält einen Snapshot-Volume-Wert. Historisch projiziert der
Producer `regularMarketVolume` nach volume_units. Das ist kumuliertes Tagesvolumen,
kein qualifiziertes Punkt-Handelsvolumen mit eigener Unit. Bereits der bestehende
[Phase-3D-Evaluator](../../scripts/phase3d/dry_run.php) übernimmt dafür ausschließlich
belegtes point_volume. Dieser Beleg fehlt bei B8. Daher verlangt der bedingte
Historyvertrag volume=NULL und beide volume_unit-Felder=NULL; die Originalevidenz
wird erhalten. Der vorhandene Tageswert wird weder umgedeutet noch in die History
kopiert, keine Stückeinheit erfunden.

Grenze: Der ursprüngliche Snapshot dokumentiert ausdrücklich keinen extrahierten
Raw-Providerpayload und keine unabhängig hashgeprüfte tatsächlich deployte
Producerrevision. Die gespeicherte native Zeile samt Kontext und der historische
Codevertrag sind belegt; ein bytegenauer Replay von regularMarketPrice/
regularMarketTime aus dem damaligen Providerpayload ist dadurch nicht bewiesen.
Dieser verbleibende Provenienzbedarf wird nicht durch heutige Providerdaten ersetzt.

## Duplicate-/Reimportprüfung und Writer-Dry-Run

Der B8-Quellbezug ist von den acht abgeschlossenen Importreferenzen verschieden.
Ohne aufgelöstes Zielasset kann jedoch der semantische Vergleich gegen alle acht
v1-Facts über Asset, Source, market_at, observed_at und Route-/Provenienzkontext
nicht vollständig durchgeführt werden. **Kein bekannter Reimportkonflikt, endgültige
Freigabe OPEN.** Unterschiedliche v1-/v2-Dedupe-Domains wären kein Ausschlussbeweis.

**Tatsächlicher B8-v2-Dry-Run: NOT_RUN – fehlende qualifizierte Zielidentität und
Route.** Keine erfundenen realen IDs und kein INSERT-Ergebnis für B8 ausgegeben.
Der Offlinehelper ruft für vollständig qualifizierte Eingaben unmittelbar den
unveränderten Phase-3N-WriterPlanner auf; keine zweite Canonicalization, Hash- oder
Reimportlogik. Ausschließlich synthetische Ersatzinstrumente beweisen INSERT mit
GBX/GBP und getrennten Zeiten, NULL-Volume, fehlende Mutation und Ablehnung eines
bereits vorhandenen v1-Facts über eine neue v2-Route. Das qualifiziert den Helper,
ersetzt aber keinen tatsächlichen B8-Plan.

## Ergebnismatrix

PASS bezieht sich jeweils nur auf die genannte Beweisebene. OPEN bedeutet fehlende
Evidenz, nicht bewiesene Falschheit. N/A bezeichnet ausdrücklich ausgeschlossenen Umfang.

| Kriterium | Status | Evidenz / Grenze |
| --- | --- | --- |
| Kandidatenfingerprint eindeutig | PASS | Matrix, Selbsthash, Parentdateien, Originalzeile und Phase-3I-B8-Beleg identisch |
| Asset eindeutig | OPEN | Kein belegtes bestehendes Zielasset, Name/Klasse nicht freigegeben |
| Identifier eindeutig | OPEN | Quell-ISIN/Kontext gebunden; passende Zielzuordnung fehlt |
| Source eindeutig | PASS | Native Providerzeile, Sourceversuch, historischer Producer und vorhandene Yahoo-Source |
| Historische Snapshotsemantik | PASS | Gespeicherter Snapshot und historischer regularMarketPrice-/regularMarketTime-Vertrag |
| Native GBX-Semantik | PASS | Originalzeile GBX; historische GBp/GBX-Erhaltung ohne GBP-Skalierung |
| currency GBP | PASS | Normativer GBX-Vertrag, keine Zahlentransformation |
| Unit GBX@1 | PASS | Phase 3M/3O und unverändertes normatives Manifest |
| market_at belegt | PASS | Separat gespeicherter UTC-Marktzeitpunkt; kein Raw-Payload-Replay behauptet |
| observed_at belegt | PASS | Davon verschiedener UTC-Sammel-/Erfassungszeitpunkt |
| Volume-Semantik belegt | PASS | Tagesvolumen bleibt Evidenz; kein point_volume, Historyvertrag NULL/NULL |
| Keine Derived-/FX-Verwechslung | PASS | market_quote, keine Derivation/FX-Felder, getrennter historischer Derivedpfad |
| Keine Bar-Verwechslung | PASS | series=snapshot, Barfelder NULL, separater historischer Chartpfad |
| Payload-/Deployment-Provenienz vollständig | OPEN | Rawpayload und unabhängiger Deploymenthash im Originalsnapshot nicht gesichert |
| Vorhandene Legacyroute qualifiziert | OPEN | Ohne Zielasset keine konkrete B8-Route nachgewiesen |
| Neue unit-aware Revision konfliktfrei beschreibbar | OPEN | Allgemeiner Vertrag klar; tatsächliche Rolle/Gruppe/Revision nicht qualifiziert |
| Kein v1-Reimportkonflikt | OPEN | Quellreferenz disjunkt, Factkoordinaten mangels Asset nicht vollständig vergleichbar |
| B8-v2-Writer-Dry-Run erfolgreich | OPEN | NOT_RUN; nur synthetische Helpertests erfolgreich |
| Current ausdrücklich ungelöst | N/A | current_route_unselected bleibt außerhalb Historyqualifikation |

## Genau fehlende Evidenz und Abschlussgrenze

Zuerst erforderlich: autoritativer historischer Instrument-/Identifierbeleg samt
Assetname und Assetklasse sowie eine bestätigte Zuordnung zu einem bestehenden
Zielasset. Der gespeicherte vollständige Zielbestand enthält diese ISIN-Zuordnung
nicht. Eine bloße Wiederholung derselben DB-Abfrage erzeugt keinen Stammdatenbeleg;
eine spätere eventuell notwendige Stammdatenanlage braucht einen eigenen Auftrag.
Keine künstliche zweite Identität oder Source anlegen.

Danach benötigt: qualifizierte reale Route/Rollenart und Providerkey-Serialisierung,
Snapshot-Provenienz bis zum damaligen Payload beziehungsweise ein ausdrücklich
qualifizierter gleichwertiger historischer Nachweis, konkrete revisionsbewusste
Konfliktprüfung und vollständiger v1-Factvergleich. Erst nach Schließen dieser
Punkte tatsächlichen B8-v2-Plan erzeugen. Keine Importvorbereitung solange Ergebnis
READONLY_EVIDENCE_REQUIRED. Kein Passwort/Gateway und keine aktuelle DB-Abfrage
erforderlich, um diese Lücken festzustellen.

DB-Verbindungen 0, DB-Writes 0, B8 nicht importiert. Keine Route, Observation,
Unit, Checkpoint, Current, Bar, Ledger oder Schema geändert; keine Produktion.
Currentauswahl, Priorität, Frische, Fallback und Cross-Source-Arbitration bleiben
vollständig außerhalb. Die abgeschlossene Untersuchung hebt keine Importsperre auf.

## Tests und Git-/CI-Nachweis

Zwölf neue Tests ausschließlich mit synthetischen Ersatzwerten: nativer GBX/GBP-
Vertrag und rationale Projektion, neue Revision statt Legacyänderung, beide
revision-aware UNIQUEs, Instrument-/Assetkonflikte über Revisionen, unveränderte
Providerkeys/Rollen, kanonische ID-Typen vor Gruppierung/UNIQUE-Vergleich,
getrennte Zeiten, v1/v2-Reimportschutz, NULL-/unqualifiziertes
Volume, reine Planung ohne Mutation oder Currentauswahl und ohne fixlab-Schreibpfad.
Ein zusätzlicher Projektionscheck erwartete zunächst aufgefüllte Dezimalstellen;
der bestehende exakte Helper liefert kanonisch ohne nachgestellte Nullen.
Die Testerwartung wurde an diesen unveränderten bestehenden Vertrag korrigiert.
Keine privaten B8-Daten in Code, Tests oder Fixtures.

Abschließende gezielte Prüfung **12/12 bestanden**, gesamte lokale Regression
**386/387 bestanden**, ausschließlich bekanntes Windows-budget_not_private.
Validate bestätigt drei deploybare Webdateien, Diff-Check erfolgreich; kein PHP
geändert. Die erste Gesamtsuite hatte vor der zusätzlichen ID-Typabsicherung
385/386 mit derselben einzigen Abweichung; danach wurde die vollständige Suite
wegen dieser Codeänderung nochmals ausgeführt. Die Deploymentausgabe in der Suite
stammt ausschließlich aus dem bestehenden Mocktest, kein tatsächlicher Deploy.
Exakter Abschlusscommit, vollständiger Linux-Run, Deploy skipped und Löschung
des temporären Prüfbranches werden in Issue #32 dokumentiert. Native Erfassung
separat: Start PROMPT_RECEIPT_MISSING, Describe/Plan jeweils einmal Invalid
laboratory identity; keine IDs oder Ereignisse erfunden. Dies ist keine fachliche
Evidenzlücke und verhindert den beauftragten read-only Abschluss nicht.

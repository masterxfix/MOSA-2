# Phase 3Q – verbleibende B8-Evidenz

**Endklassifikation: AUTHORITATIVE_SOURCE_REQUIRED.** Die Untersuchung ist
abgeschlossen; B8 bleibt gesperrt. Start exakt auf
`af71b163487f3d745803c6a3579c9bf9259db4b4`,
[Issue #33](https://github.com/masterxfix/MOSA-2/issues/33).

Die historische Identity einschließlich Name und Klasse wurde gefunden. Im
vorhandenen Zielreadback fehlt der Identifier weiterhin: **Neue Stammdatenanlage
erforderlich.** Keine Stammdatenanlage durchgeführt. Vollständige Provenienz
fehlt; eine dauerhafte Unverfügbarkeit ist nicht belegt. Weder Importfreigabe
noch eigenmächtige Akzeptanz einer Provenienzlücke.

## Ausgangslage und eng begrenzte Suche

[Phase 3P](PHASE3P_B8_QUALIFICATION.md) hatte Source, Snapshotsemantik, native
GBX-Zahl, monetäre Basis GBP und zwei getrennte gespeicherte UTC-Zeiten bestätigt.
Historyvolume bleibt mangels qualifizierter Unit NULL. Diese Ergebnisse werden
nicht neu interpretiert; B1–B7 wurden nicht erneut analysiert.

Zuerst die bestehenden privaten H-/I-/P-Belege mit Originalsnapshot,
Originalzeile, same-run Sourceversuch und Parentdateien korreliert. Danach die
bereits vorhandenen privaten historischen JSON-Artefakte der Phasen 3DB–3K nur
auf die gebundenen B8-Identifier/Providerinstrumente geprüft. Zusätzliche Treffer
in den 3DD-Importvorschlägen wiederholen den Kandidaten; sie liefern keinen
eigenständigen Stammdaten- oder Rawpayloadbeleg. Die damaligen gezielten
Instrument-/Identity-/Registry-/Portfolioauszüge enthalten keinen B8-Stammsatz.
Sie waren auf andere Objekte begrenzt und beweisen keine Abwesenheit in der
vollständigen alten Installation.

Erst anschließend gezielte historische Git-Dateien über GitHub read-only
gelesen, ausschließlich fixlab-Commit
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`:

- `data/asset_registry.json` und Metadaten von `data/assets`: kein B8-Eintrag.
- `php/mosa_invested_instrument.php`, `mosa_market_identity.php`,
  `mosa_market_source_registry.php`, `mosa_user_relationship.php` und
  `mosa_portfolio_asset_bridge_setup.php`: konkrete private Speicherverträge und
  Identifier-/Objekt-/Sourcebezüge. Die privaten Stammdatendateien sind nicht
  im historischen Git-Baum enthalten; `data/private` enthält nur Schutz und
  Beispielkonfiguration, `data/private_import` nur Schutz.
- `php/mosa_logo_mapping.php`: genau ein Treffer der gebundenen Quellkennung;
  ausdrücklich versionierte Freigabe aus MOSA-Metadaten und damaliger Prüfung,
  `approved=true`, `locked=true`, Name, Objektklasse und Objektkey vorhanden.
- Die gezielten Collection-/Identity-/Instrument-Backfilltests: ein synthetischer
  Collectiontest bestätigt dieselbe Instrument-/Venue-/Quoteart-Konfiguration.
  Seine Preise, Zeiten, Sourcekey-Suffixe und Payloads sind Testdaten und werden
  nicht als historische B8-Evidenz übernommen.
- Die zwei historischen Collector-Hauptdateien bestätigen den in Phase 3P
  beschriebenen Producervertrag; Git-Blobs unverändert. Kein heutiges fixlab-main.

Keine Repository-Vollsuche, Browser-/Dogado-Aktion, DB-Verbindung, Passwort,
Gateway, Provideranfrage oder Änderung an fixlab.

## Fingerprintbindung und Identity

| Beleg | SHA-256 bzw. Git-Blob |
| --- | --- |
| H-Matrixdatei | `ffa86b91d7956d59463dbaa8a424c4a78027feb8a6c329b117033c0fe8944831` |
| Originalsnapshot | `2d859b76fdccef821c24c5a35716bf9ba1c11f3be7e6f68e4d68c6a4b58cad67` |
| B8-Kandidat | `727988c70a1a39bb8751b89336dd7d31d48142b3f67242e742ac6b58d8dccd20` |
| B8-Originalzeile | `7146250f9173faddd80fc577c9f51c58f1dc787a1a85dc9765bd5eb23a768ef0` |
| O-Finalreadbacks, jeweils | `11057b4b239955ee274cbeab12857a65c2ef0d16d8ddc40e1683931d85b8a423` |
| Historisches Mapping, Git-Blob | `3f8a0902eaaf2d7f4d649bb2eaad76dadd237447` |
| Historisches Mapping, SHA-256 | `da14df9eb3befe0d45a27781fd5717893a5c08ec8d22d0a8743caafcd3897223` |
| Private kombinierte Identity, kanonisches sortiertes JSON | `ac15fb6992b4c4a035e861bb42b3ca0e42af1978e2af9a333f64ada7a384e541` |

Die private Identity-Evidence-Struktur enthält `source_identifier_type`,
`source_identifier_value`, `historical_name`, `historical_asset_class`,
`historical_provider_instrument`, `historical_source_type`, `evidence_reference`
sowie historischen Objektkey und explizit fehlendes Zielasset. Historischer
Objektkey zusätzlich gegen die deterministische Ableitung aus dem Namen geprüft.
Mapping-Identifier entspricht exakt der Quellkennung; Providerinstrument und
Sourcekontext kommen aus dem gebundenen Original/Sourceversuch, nicht vom
Logoanbieter. Kein widersprüchlicher B8-Datensatz in den ausgewerteten Quellen.

Historischer Name/Klasse: **PASS** als ausdrücklich freigegebene historische
MOSA-Metadaten. Das Mapping ist eine Identitäts-/Logoassoziation, kein heutiger
MOSA-2-Stammdatensatz und keine Freigabe für dessen Anlage. Echte Namen, ISIN,
Ticker, Objektkeys, Sourcekeys, Zeilen-/Run-IDs, Marktwerte und konkrete Zeiten
bleiben ausschließlich privat. Die Originalartefakte wurden nicht verändert.

## Zielasset, Source und zwei unterschiedliche Routengruppen

| Prüfung | Ergebnis |
| --- | --- |
| Historische Instrumentidentity, Name/Klasse | PASS |
| Passender MOSA-2-Identifier / daraus auflösbares Zielasset | OPEN; im vorhandenen globalen Identifierbestand jeweils 0 Treffer |
| Neue Stammdatenanlage | erforderlich, noch nicht durchgeführt |
| Vorhandene passende Source | PASS; genau eine, Typ `market_data` |
| Alte MOSA-Producergruppe Instrument/Source/Provider/Venue/Snapshot | PASS, durch Original und same-run Versuch gebunden |
| Tatsächliche MOSA-2-Legacyroute für genau B8 | fehlt; auch direkter Lookup des eingefrorenen Importschlüssels ergab 0 Treffer |
| Künftige MOSA-2-Routengruppe | erstmals anzulegen, nach getrennter Stammdatenqualifikation |
| Reale Route-ID / nächste reale Revision | OPEN; keine ID oder Revisionszahl erfunden |

Die O-Zielbefunde wurden aus dem privaten P-Abschlussbeleg mit gespeicherter
Hashbindung übernommen. Die beiden ursprünglichen O-Serverdateien sind lokal
nicht verfügbar; in Phase 3Q weder neu heruntergeladen noch neu gehasht. Somit
historischer Zielstand, keine neue Aussage über eine aktuell gelesene Datenbank.

Die historische Providerinstrument-/Sourcekey-Serialisierung ist privat aus
Original und Versuch belegt. Davon getrennt ist der Phase-3D-MOSA-2-Importvertrag:
Rolle `quote`, opaker `market-v1:`-Schlüssel aus SHA-256 des eingefrorenen
`proposed_route_key`. Das ist ein reproduzierbarer **Vorschlag**, keine existierende
B8-Route und kein unveränderter Yahoo-Ticker. Keine Umschreibung in einen
Unit-/Currencykey und keine Übernahme einer fremden Route. Tatsächliche
`route_type`-/`external_key`-Bindung einer Zielroute bleibt OPEN. Aus dem alten
MOSA-Producerkontext folgt keine bereits angelegte MOSA-2-Legacyroute.

Der bedingte Unitvertrag bleibt `mosa2-market-unit-v1`, GBX@1, GBP, native Zahl,
NULL-Mengenbasis und NULL-Volumeunit. Erst nach qualifizierter realer Identity/
Routengruppe darf eine konkrete neue unveränderliche Revision vorgeschlagen
werden. Beide Schema-3-UNIQUEs gelten unverändert:
`source_id/route_type/external_key/route_revision` und
`asset_id/source_id/route_type/route_revision`. Keine Legacyroute mutieren.

## Provenienz und genau eine nächste autoritative Quelle

**Provenienz: OPEN.** Originalmanifest sagt ausdrücklich: kein unabhängig
hashbestätigter Deploymentstand und kein extrahierter Raw-JSON-Pfad. In den
ausgewerteten privaten historischen Artefakten wurde kein zusätzlicher
B8-Rawpayload oder unabhängiger historischer Deploymenthash gefunden. Die
historischen Git-Blobs belegen den versionierten Vertrag, nicht dessen damalige
tatsächliche Ausführung auf dem Quellserver. Der Collector erzeugt zwar
`payload_archive_candidates` und Payloadhashes; das belegt weder die damalige
Archivierung noch eine heutige Wiederherstellbarkeit des konkreten B8-Payloads.
Testpayloads ersetzen diese Nachweise nicht. Dauerhafter Verlust ist **nicht**
nachgewiesen; daher keine Klassifikation als akzeptanzfähige Provenienzlücke.

**Genau eine nächste Quelle:** der historische Sicherungsstand der alten
MOSA-Installation, der den privat fingerprintgebundenen B8-Collectionlauf
abdeckt, einschließlich seines Collector-Dateistands und Payloadarchivs.
Das ist ein einzelner zusammengehöriger Sicherungsstand, keine Suche nach
aktuellen Ersatzdaten. Seine genaue Sicherungs-ID ist derzeit **nicht bekannt**.

| Frage | Präzise Grenze des nächsten read-only Auftrags |
| --- | --- |
| Welche Information fehlt? | Unveränderte damalige Antwortbytes oder unabhängig gebundener Ausschnitt; Hash-/Run-/Instrumentbezug; unabhängig gesicherter tatsächlich eingesetzter Collector-Dateistand und dessen Commit-/Hashbindung |
| Warum diese Quelle? | Nur ein zur ursprünglichen Sammlung gehöriger Sicherungsstand kann noch vorhandene Rawbytes und damals installierte Dateien gemeinsam zeitlich und sachlich binden |
| Bekannt/verfügbar? | Alte Installation und private Lauf-/Zeilenfingerprints bekannt; konkretes Backup, Aufbewahrung und Inhalt bisher nicht bestätigt. Kein vorhandenes vollständiges Backup behauptet |
| Technischer Zugriff? | Ein bereitgestellter Offline-Sicherungsstand wäre ohne DB-/Providerverbindung eng filterbar. Ob ein passender Sicherungsstand beim Betreiber existiert und exportierbar ist, wurde in diesem Auftrag nicht geprüft |
| Spätere Nutzeraktion? | Erst in einem separaten Auftrag gegebenenfalls Sicherungsstand auswählen/bereitstellen oder Zugriff ausdrücklich freigeben; konkrete Zugangsvoraussetzungen sind unbekannt. Jetzt keine Nutzeraktion angefordert |

Danach getrennt Stammdatenanlage vorbereiten, weil die historische Identity jetzt
belegt ist, das Zielasset aber fehlt. Das ist kein zweiter Datenbeschaffungsauftrag
und keine automatische Anlage. Falls die eine Sicherungsquelle nachweislich
keinen Rawpayload/Deploymentbezug mehr liefern kann, erst dann die dauerhafte
Provenienzlücke und ihr Restrisiko neu beurteilen; keine stillschweigende Lockerung.

## Reimport und tatsächlicher Writerplan

Vollständiger semantischer Vergleich gegen die acht v1-Facts: **OPEN**, weil
das Zielasset nicht aufgelöst ist. Kein NO_MATCH allein aus abweichenden
Hashdomains, Quellreferenzen oder einer neuen Route behauptet. Der vorhandene
Phase-3N-Reimportschutz bleibt unverändert.

Tatsächlicher B8-v2-Dry-Run: **NOT_RUN**. Keine erfundenen IDs für einen INSERT-
Nachweis. Der neue generische Evidenzgate delegiert nur bei vollständiger
Identity, genau einem Zielidentifier/Asset, Source, qualifizierter vorhandener
Zielroute/Revision, vollständiger Provenienz und NO_MATCH an den echten
Phase-3N-Writer über den bestehenden Phase-3P-Helper. Jeder Writer-REJECT oder
CONFLICT hebt eine vorläufige Bereitschaft auf. Fehlende Gruppen bleiben OPEN;
dieser Helper erstellt auch bei synthetischen Tests keine neue Gruppe.

## Tests, Abschluss und Erfassungsgrenze

Neue Tests ausschließlich synthetisch: vollständige/fehlende/widersprüchliche
Identity, fehlendes Zielasset/neue Stammdaten, vorhandene/fehlende Routengruppe,
vollständige/offene/nachweislich verlorene Provenienz, v1 MATCH/OPEN/NO_MATCH,
Writer nur mit vollständigen Voraussetzungen, echte Writer-Reimportablehnung,
Identity-/Revisionsbindung und native Offlineplanung ohne Netzwerkzugriff.
13/13 neue Tests erfolgreich. Lokale Gesamtsuite 399/400; ausschließlich das
bekannte Windows-`budget_not_private`. Validator (drei Webdateien), Diff-Prüfung
und Schutzprüfung gegen echte private Werte erfolgreich. Die private tatsächliche
B8-Identity wurde außerdem durch denselben Gate klassifiziert: PASS für Identity,
AUTHORITATIVE_SOURCE_REQUIRED, neue Stammdaten erforderlich, Revision OPEN,
Reimport OPEN, Dry-Run NOT_RUN. Kein echter Writerplan dabei erzeugt.
Keine PHP-Datei geändert. Exakter Linux-Abschlusscommit/Run mit Produktionsdeploy
skipped wird in Issue #33 festgehalten; der temporäre Prüfbranch wird danach gelöscht.

Nativen Start, Describe und Plan jeweils einmal regulär versucht. Start und
weitere Schrittmeldungen scheitern am fehlenden nativen Promptbeleg
(`PROMPT_RECEIPT_MISSING`); Describe/Plan melden ungültige Laboridentität.
Keine Turn-ID, Ereignisse oder Zeitpunkte erfunden. Dies ist eine separate
Erfassungslücke, kein fachlicher Importnachweis.

DB-Verbindungen **0**, DB-Writes **0**, B8 importiert **nein**. Kein Provider,
Browser, Dogado, Gateway, Passwort, Asset-/Identifier-/Route-/Observationwrite,
Current/Bars, Ledger, Produktion oder fixlab-Änderung. Der Issue-Abschluss
bestätigt die abgeschlossene Suche und Klassifikation, keine Importfreigabe.

# Phase 3I – allgemeiner Quote-/Quantity-Unit-Vertrag

**Entscheidung am 19.10.2026, Issue #24, Ausgangspunkt `40f62e4`: Variante C.**
Native Zahl unverändert erhalten, explizite versionierte Einheit referenzieren
und eine Basiseinheit ausschließlich deterministisch projizieren. Currency,
Preiseinheit und gegebenenfalls Mengenbasis sind getrennte Begriffe.
**Additive fachliche Schemaerweiterung erforderlich**, einschließlich kontrolliert
angepasster Routen-Unique-Verträge. Dies ist nur ein logischer Zielentwurf: keine
SQL-Datei/Migration 0003, keine Implementierung, DB-Aktion oder Datenübernahme.

## Problem und Beweisgrenze

B8 ist die in Phase 3H eingefrorene native GBX-Snapshotquote. Der private Befund
wurde gegen den dort gesicherten Matrixfingerprint geprüft; keine neue Auswahl
oder erneute Analyse aller acht Fälle. Native Preiszahl und UTC-Zeiten bleiben
unangetastet. Historische Quellsemantik bleibt fixlab
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`: der bekannte Producer erhält GBX;
der 0.01-Faktor des FX-Pfads ersetzt keinen allgemeinen Unit-Vertrag.
B6/B7 und B5 sind ausschließlich konzeptionelle Wiederverwendbarkeits-Gegenproben.
Keine realen Identitäten, Quellreferenzen oder Einzelmarktwerte stehen hier.

Observation, Current und Bars enthalten heute currency und DECIMAL-Preisfelder,
aber keine unabhängige Unit-/Basis-/Versionsreferenz. Eine Zahl in Pence mit
currency=GBP ist ohne zusätzlichen Vertrag mehrdeutig. GBX als neue scheinbare
ISO-Währung oder XXX als Ersatz für Punkte löst das Problem nicht.

Referenzen: [Phase-3H-Befund](PHASE3H_BLOCKED_CASES.md),
[Marktdatenstruktur](MARKET_DATA_PHASE3.md),
[Sources/Routes](CORE_SCHEMA_PHASE2.md),
[Observation-v1](PHASE3C_MARKET_FLOW.md),
[Feldmapping](PHASE3D_FIELD_MAPPING.md) und die unveränderten Funktionen in
`scripts/phase3c/market_flow.php`.

## Drei Varianten und Entscheidung

| Kriterium | A: nur native Unit | B: nur normalisierte Basiseinheit | C: native Quantity + versionierter Unit-Vertrag |
| --- | --- | --- | --- |
| Datenverlust | Zahl erhalten, Einheitenrelation ohne Zusatzvertrag offen | Native Zahl/Einheit ohne separates Audit verloren | Native Zahl und unveränderliche Definition erhalten |
| Audit / Reproduktion | Unitlabel allein reicht nicht | Zusätzlich Originalwert, Faktor und Rundung nachweisen | Referenz auf feste Definition + Originalevidenz |
| Observations | Native History möglich, Umrechnung unbestimmt | History speichert bereits transformierten Wert | Native History; Normalisierung nur Projektion |
| Current | Einheit muss mitkopiert werden | Einheitlich, aber Herkunftssemantik leicht verdeckt | Gleicher Vertrag wie zugrunde liegende Observation |
| Bars | Gemeinsames OHLC-Unitlabel nötig | Alle OHLC skalieren; Originalbasis zusätzlich sichern | Ein Unitvertrag für alle vier nativen Preisfelder |
| Dedupe | Unitlabel ohne Version unzureichend | Gleich aussehende Outputs verdecken andere Inputs | v2 bindet Unitdefinition und Basis explizit |
| Historische Migration | Native Einheit belegen, Relation später offen | Separater reversibler Transformationsnachweis nötig | Explizite Version, keine rückwirkende Konvertierung |
| Punkte | Möglich, aber Dimension unbestimmt | Keine Geld-Basiseinheit für Punkte | Eigene nichtmonetäre Dimension |
| Mengenbasis später | Zusätzlicher Vertrag nötig | Zusätzlicher Vertrag nötig | Optionaler unabhängiger Nenner vorgesehen |
| Queries | Einfach native lesen, Vergleich offen | Einfach bei gleicher Basiseinheit | Nativer Hot Path einfach; Projektion braucht kleinen Kataloglookup |
| Schemaaufwand | Unitfelder, später weitere Definitionen | Unit-/Auditfelder trotz Normalisierung | Ein kleiner Unitkatalog + explizite Referenzfelder |

**C ist der kleinste vollständige allgemeine Vertrag.** A würde für verbindliche
Versionierung und Skalierung ohnehin zu C wachsen. B spart die Originalprovenienz
nicht und würde den nativen B8-Wert als bereits umgerechnete History behandeln.
Kein Derived-/FX-Graph und keine Future-Implementierung werden vorgezogen.

## Fachliche Begriffe

- `currency`: Geldwährung der Basis des monetären Zählers, soweit vorhanden.
  Für native GBX-Zahlen künftig GBP **nur zusammen mit expliziter GBX-Unit**;
  bei POINT fachlich NULL. Keine implizite Zahlenkonvertierung durch dieses Feld.
- `quote_unit`: Einheit der nativen Preis-/Messzahl. EUR/GBP/NOK als volle
  monetäre Einheiten, GBX als Untereinheit von GBP, POINT als nichtmonetäre Einheit.
- `quantity_basis_unit`: optionaler separat quantifizierter Nenner, z. B. eine
  Energie- oder Mengeneinheit. `quantity_basis_amount` ist dessen positive Anzahl.
  Bei einfachem B8/POINT beide NULL: kein separat quantifizierter Nenner, keine
  erfundene Stück-/Kontraktgröße. Unbekannte erforderliche Basis darf nicht durch
  NULL als angeblich nicht vorhanden dargestellt werden.
- `volume_unit`: gegebenenfalls Einheit des Volumenwerts, unabhängig von Preis-
  oder Mengenbasis. Ein Preis pro Mengeneinheit beweist keine Volumeneinheit.
- Native Observation: tatsächlich beobachtete Zahl mit Unit und Evidenz;
  normalisierte Darstellung: deterministische Repräsentation derselben Tatsache.

POINT ist keine universelle Vergleichbarkeit verschiedener Indizes: deren
fachliche Identität und Bezugsbasis bleiben separat nachzuweisen.

## Ein unveränderlicher Unitkatalog

Logisch eine neue Tabelle `m2_units`, keine Tabelle pro Provider oder Einheit.
Die stabile Identität ist `(unit_key, unit_version)`; Version positive Ganzzahl.
Zulässige Unitkeys sind kanonische ASCII-Schlüssel mit binärer Vergleichssemantik.

| Attribut | Verbindliche Bedeutung |
| --- | --- |
| unit_key, unit_version | Öffentlicher Einheitenbegriff und unveränderliche Definitionsrevision |
| dimension | monetary, index_point oder konkrete physische/quantitative Dimension |
| base_unit_key, base_unit_version | Explizite Referenz auf eingefrorene Basiseinheit derselben Dimension |
| monetary_currency_code | Genehmigter echter Geldwährungscode beim monetären Zähler, sonst NULL |
| scale_numerator, scale_denominator | Positive kanonische Ganzzahlstrings; exakt gekürzter rationaler Faktor zur Basis |
| contract_version | Validierungs-/Definitionsvertrag, initial `mosa2-market-unit-v1` |
| status | Nur eingefrorene/frozen Definitionen dürfen referenziert werden |
| definition_reference | Versionierte fachliche Entscheidungs-/Definitionsevidenz, kein Providerpayload |

Basisdefinitionen referenzieren sich selbst mit 1/1. Andere Definitionen zeigen
**direkt** auf eine solche Basis; keine Faktorenketten und keine Zyklen außer der
Selbstreferenz der Basis. Dimension und monetary_currency_code müssen passen.
EUR und GBP besitzen getrennte monetäre Basen; 1/1 ist kein EUR→GBP-Wechselkurs.
Einheitenskalierung ist linear ohne Offset; affine/logarithmische Einheiten sind
nicht Teil dieses Vertrags. Faktoren >0, Nenner niemals 0, gcd=1; keine FLOAT/
DOUBLE-Felder oder IEEE-Zwischenrechnung. Numerische Grenzen müssen vor späterer
Implementierung begrenzt und overflow-sicher mit Ganzzahlarithmetik geprüft werden.

| Unitdefinition (illustrativ) | Dimension | Basis | currency | Faktor |
| --- | --- | --- | --- | --- |
| EUR@1 | monetary | EUR@1 | EUR | 1/1 |
| GBP@1 | monetary | GBP@1 | GBP | 1/1 |
| GBX@1 | monetary | GBP@1 | GBP | 1/100 |
| POINT@1 | index_point | POINT@1 | NULL | 1/1 |

Nach Verwendung sind **alle semantischen Eigenschaften unveränderlich**. Auch
Basisversion und Faktor dürfen nicht umgehängt werden. Eine andere Bedeutung
benötigt neue Definitionsversion und neue explizite Bindung. Drafts sind nicht
referenzierbar. Rücknahme künftiger Nutzung erfolgt über eine getrennte
administrative Freigabe, nicht durch Änderung historischer Definitionen.
Kein Preis, Provider, Asset, Ticker, FX-Kurs oder Rollen-/Routenrang im Katalog.
Damit gehören häufige Fachattribute in normale Felder und FKs, nicht in JSON.

## Exakte Projektion und Quantity-Basis

Für native Zahl P und Quote-Faktor n/d ist die Basisdarstellung exakt P × n/d.
Falls ein expliziter Nenner mit Anzahl A und Mengenfaktor qn/qd vorhanden ist,
ist der Preis je einer Basismengeneinheit exakt P × n/d ÷ (A × qn/qd).
Nur gleiche Dimensionen beziehungsweise derselbe geldwährungsgebundene Zähler
sind konvertierbar; FX ist eine andere Operation und bleibt außerhalb Phase 3I.

Native Inputs bleiben Dezimalstrings im bestehenden Preispräzisionsrahmen.
Projection rechnet über ganze Zahlen/rationale Zahlen. Ist ein Ergebnis in der
angeforderten Dezimalskala nicht exakt darstellbar oder zu groß, liefert sie
`normalization_unrepresentable`; kein Abschneiden oder implizites Runden. Die
native Tatsache wird dadurch nicht umgeschrieben. Eine spätere Anzeige darf nur
mit ausdrücklich eigener Darstellungs-/Rundungsregel runden, niemals den History-
Payload verändern. Bid/Ask und OHLC verwenden denselben Faktor, NULL bleibt NULL.

Optionaler Mengenbasisvertrag ist **jetzt konzeptionell vorgesehen**. Damit sind
Geldbetrag pro Energieeinheit, pro Volumeneinheit oder später pro belegter
Kontrakteinheit ausdrückbar. Dies bestätigt keine Future-Identität, Laufzeit,
Rollsemantik oder Assetfreigabe. B8 benötigt keinen solchen zusätzlichen Nenner.
Volumen ist eine separate Quantity mit eigener Einheit und eigener Evidenz.

## Bindung: Route und Datensatz (C)

Nur Datensatzbindung erleichtert widersprüchliche Werte derselben Route; reine
Routenbindung macht eine spätere Routenänderung historisch gefährlich und den
Key abhängig von einem Lookup. Daher explizite Bindung auf **beiden Ebenen**:

- Eine physische Route-ID bezeichnet künftig genau eine unveränderliche
  Routenrevision mit Unit-Vertrag, Quote-Unitversion und optionaler Mengenbasis.
- Observation/Current/Bar tragen dieselben versionierten Fachreferenzen explizit.
  Ein späterer Writer prüft vollständige Gleichheit mit ihrer Routenrevision,
  einschließlich Mengenbasis und gegebenenfalls Volumeneinheit.
- Provider-/Instrumentkennung bleibt `external_key`; **keine Unit oder Revision
  hineincodieren**. `route_type` bleibt fachliche Rolle, kein Unit-Suffix. Kein
  erfundener Provider/Sourcewechsel für eine bloße Einheitenskalierung.

Eine echte Änderung der vom Provider gelieferten Unit erzeugt eine **neue
physische Route mit eigener ID** und expliziter `route_revision`, keine Mutation
der alten Route. Die fachliche Routengruppe bleibt Asset + Source + Rollenart.
Providerwechsel verwendet die wirklich andere Source und ihre eigene Route.
Eine bloße GBP-Anzeigeprojektion erzeugt überhaupt keine neue Route.

Die zwei bestehenden UNIQUEs würden eine weitere Revision desselben Instruments
blockieren. Der logische Folgeentwurf erweitert beide ausdrücklich um
`route_revision`: Source/Rollenart/external_key/Revision und
Asset/Source/Rollenart/Revision. Revision ist eine positive Nummer innerhalb der
Routengruppe, kein Einheiten- oder Providerstring. Mehrdeutige Instrumentzuordnung
über Revisionen bleibt ein Konflikt; eine andere externe Kennung darf nicht zur
Umgehung eines Identitätskonflikts dienen. Parallele aktive Revisionen erfordern
später einen getrennten Freigabe-/Zeitvertrag; hier keine Current-Arbitration.
Die kontrollierte Anpassung dieser Constraints ist Teil einer **späteren**
Schemafreigabe, heute bleiben beide UNIQUEs bytegleich.

## Observation-v1 bleibt unverändert

`mosa2-observation-v1` plus LF und das feste kompakte JSON bleiben exakt:
`asset_id, source_id, route_id, currency, market_at, observed_at, price, bid, ask, volume`.
Keine zusätzlichen Unitfelder, andere NULL-/Dezimalregeln oder Kataloglookups in
`normalizeObservation`, `canonicalObservation` oder `dedupeKey`. Alle acht
bestehenden Observations und ihre 32-Byte-Keys werden nicht gelesen, umgeschrieben
oder neu gehasht. Der Sourcecode bleibt byte-identisch zum Ausgangscommit.

Expliziter Legacy-Lesevertrag `legacy-monetary-v1`: nur die bereits fachlich als
einfache monetäre Quotes freigegebenen v1-Zeilen haben logisch Unit=currency,
Skala 1/1, keine zusätzliche Mengenbasis. Das ist ein versionierter Lesemantel,
keine Änderung ihrer gespeicherten Bedeutung und kein Backfill. Er behauptet
keine bisher unbekannte Volumeneinheit und gilt nicht automatisch für beliebige
Dreilettercodes, GBX oder XXX. Nicht qualifizierter Altbestand bleibt unresolved.
Bestehende v1-Dubletten bleiben über ihren ursprünglichen Key erkennbar.

## Vorgeschlagener Observation-v2-Dedupe

Noch keine Funktion oder Writerimplementierung. Vorgesehene kanonische Bytes:
`mosa2-observation-v2` + LF + kompaktes UTF-8-JSON in folgender fester Reihenfolge:

1. Die zehn v1-Felder in unveränderter Reihenfolge; bei v2 darf currency fachlich
   NULL für nichtmonetäre Werte sein, Preis-/Zeit-/ID-Normalisierung sonst gleich.
2. `unit_contract_version` (initial `mosa2-market-unit-v1`).
3. `quote_unit_key`, `quote_unit_version`.
4. `quantity_basis_unit_key`, `quantity_basis_unit_version`, `quantity_basis_amount`.
5. `volume_unit_key`, `volume_unit_version`.

Unitkeys und Vertragsversion sind kanonische ASCII-Strings; positive Unitversionen
sind Dezimalstrings ohne führende Nullen. Alle Felder sind explizit vorhanden;
optionale Paare beziehungsweise Basis-Triple sind entweder vollständig belegt
oder vollständig NULL. Basisanzahl positiv, kanonischer Dezimalstring mit Skala 8;
bei vorhandenem Nenner wird auch Anzahl 1 explizit angegeben. Bei non-NULL volume
muss dessen eigene Unitversion belegt sein; NULL volume besitzt NULL-Unitreferenzen.
Currency muss exakt zur eingefrorenen Quote-Unitdefinition passen. Native GBP und
native GBX haben auch bei derselben Geldwährung verschiedene Unitidentitäten.

Unitdefinitionen werden vor dem Hash geprüft. Key+Version+Vertragsversion binden
die **unveränderliche** Basis/Faktor/Dimension; ein veränderbarer Kataloglookup ist
unzulässig. Faktoränderung unter gleichem Key+Version wird abgewiesen; neue
Definitionsversion verändert die kanonischen Bytes und damit den Dedupe-Key.
Faktoren müssen deshalb nicht redundant als veränderbare Zahlen im Zeilenhash
stehen. Physische route_id identifiziert bereits eine feste Routenrevision.
SHA-256 über die v2-Bytes liefert wieder 32 rohe Bytes. Die neue Domain trennt v1
und v2; Keygleichheit verlangt weiterhin vollständige Payloadgleichheit.

Unterschiedliche Hashdomains dürfen nicht zum doppelten Import derselben alten
Tatsache führen: Ein späterer Dispatcher trennt v1-Replay und v2-Neudaten über
expliziten Format-/Routenvertrag. Kein v2-Reimport der vorhandenen acht v1-Zeilen
und kein automatisches Upgrade im Replay. Neue unit-aware Routen dürfen nicht
über die unveränderte, nur formal dreiletterprüfende v1-Funktion eingeschleust
werden. Dieser zusätzliche äußere Schutz gehört in einen späteren Writer.

## Native, Current und Bars

Eine GBP-Darstellung aus einer nativen GBX-Observation ist ausschließlich eine
View-/Berechnungs-/Anzeigeprojektion mit Verweis auf dieselbe native Tatsache:
**keine zweite native History-Zeile, kein neuer Source und keine neue Route**.
Ein materialisierter Derived-/FX-Graph wäre ein eigener späterer Vertrag.

Current kopiert native Zahl, currency, Format und vollständige Unit-/Basisbindung
seiner zulässigen Observation atomar. Native Zahl in GBX und currency=GBP sind nur
mit expliziter GBX-Unit sinnvoll. Normalisierte Views sind als solche benannt;
keine Mischung in derselben Current-Zeile. Bestehende Zeitregeln und die separat
notwendige Routenauswahl bleiben bestehen; keine Cross-Source-/Route-Auswahl hier.
Tagespreisfelder dürfen nur aus demselben Unitvertrag projiziert werden, Tages-
volumen bleibt gesondert. Keine neue Current-Zeile in diesem Auftrag.

Für eine Bar gilt genau eine Quote-Unit-/Basisversion gemeinsam für O/H/L/C.
Volumen besitzt eine eigene Quantity-Semantik. B6/B7 können exakt GBX@1 aus B8
verwenden; Intervall, Ende, Session, Adjustment und Revision bleiben ungelöst.

**Baridentität bleibt fachlich** Asset + physische Route-ID + Intervall + Start,
weil jede physische Route-ID exakt eine unveränderliche Unitrevision bezeichnet.
Unitbindung ist zusätzlich im Payload enthalten und gegen Route geprüft: gleicher
Schlüssel mit abweichendem Unit-/OHLCV-Payload ist Konflikt, kein Update. Echte
Unitänderung nutzt eine neue Route-ID und kann alte Bars nicht umdeuten. Damit
reicht der bisherige vierteilige Bar-UNIQUE unter dieser zusätzlichen Invariante;
ohne unveränderliche Routenrevision würde er fachlich nicht genügen.
Keine stillen Barrevisionen und kein Bar-Write werden dadurch freigegeben.

## B8 und Wiederverwendbarkeit, ohne reale Werte

B8 wird logisch als native positive Zahl P mit currency=GBP,
quote_unit=GBX@1, unit_contract=mosa2-market-unit-v1 und ohne separate Mengenbasis
modelliert. Source/Route und Unit-Provenienz müssen später belegt und referenziert
werden. Die GBP-Projektion ist exakt P/100. P bleibt im nativen Datensatz erhalten.
Keine hier genannte Zahl ist der echte B8-Marktwert.

B6/B7 übernehmen dieselbe Quote-Unitdefinition für ihre vier OHLC-Preisfelder;
ihre übrigen Barblocker werden nicht aufgehoben. B5 kann currency=NULL,
quote_unit=POINT@1 und Faktor 1/1 verwenden; keine XXX-Pseudowährung erforderlich.
Seine Index-/Assetidentität bleibt separat offen. Keine neuen Aussagen zur
Importierbarkeit anderer gesperrter Fälle.

## Minimaler logischer Schemaentwurf

Entscheidung **C: fachlich additive Schemaerweiterung notwendig**, keine bloße
Umdeutung vorhandener currency-/external_key-/JSON-Felder. Eine neue Katalogtabelle
und Referenzen an vier vorhandenen Tabellen reichen für den Unit-Grundvertrag.

| Objekt | Später benötigte fachliche Erweiterung |
| --- | --- |
| m2_units (neu) | Composite-PK Unitkey/Version, Basis-FK, Dimension, Geldwährung nullable, exakter Ganzzahlbruch, Vertrag, frozen-Status und Definitionsevidenz |
| m2_asset_source_routes | route_revision; unit_contract_version; Quote-Unit-FK; optionale Mengenbasis-FK/Anzahl und Volume-Unit-FK; immutable semantische Revision |
| m2_market_observations | observation_format_version; Unitvertrag und gleiche Quote-/Basis-/Volume-Referenzen wie Route; native Zahlen und bestehender Dedupe-Key |
| m2_market_current | Format und Quote-/Basisbindung der Observation; optionale separate Tagesvolumenbindung, falls dieses Feld später überhaupt befüllt wird |
| m2_market_bars | Unitvertrag, Quote-/Basisbindung für alle OHLC-Werte und separate Volume-Unitreferenz |

**Legacy/nullability:** Neue Unit-/Formatfelder zunächst nullable nur für explizit
als Legacy-v1 behandelte unveränderte Altzeilen. NULL ist dort keine automatische
Unit-Freigabe. Für jede neue v2-Zeile sind Format/Unitvertrag und Quote-FK zwingend;
quantity-Triple nullable nur bei fachlich nicht vorhandenem Nenner; Volume-Paar
nullable nur bei NULL-Volumen. Später conditional Checks und vollständige FK-
Paare, keine halb belegten Referenzen. Currency für v1 weiterhin nicht NULL;
für v2 nur bei nichtmonetärer Quote-Unit NULL, monetär exakt kataloggebunden.
Native Zahl und currency ohne Unit in einem v2-Datensatz werden abgewiesen.

Bestehende Route-IDs und alle FKs bleiben erhalten. route_revision kann in einer
späteren freigegebenen Schemaänderung technisch mit Startwert 1 eingeführt werden;
das macht Legacy-Routen nicht automatisch zu unit-aware Routen. Ihre Unitfelder
bleiben NULL. Für einen neuen Unitvertrag wird eine neue physische Routenrevision
angelegt; keine alte Route bekommt nachträglich eine andere semantische Bindung.

**Constraints/Indizes:** Basis- und Unitreferenzen über zusammengesetzte FKs mit
ON DELETE RESTRICT, passende FK-Indizes; frozen-/Dimensions-/Currency-/Routen-
Konsistenz zusätzlich zentral vor Write prüfen. Die zwei Routen-UNIQUEs müssen
wie oben beschrieben um Revision erweitert werden, nicht um versteckte Unit-
Strings. Das ist ausdrücklich keine rein hinzufügende Indexoperation; der spätere
Migrationsplan muss Constraintwechsel und Null-/Legacy-Schutz gesondert beweisen.
Bar-UNIQUE und vorhandene Zeitfensterindizes bleiben fachlich erhalten.
Observation UNIQUE(dedupe_key) kann bleiben; Format/Payloadprüfung verhindert
Domain-/Legacyverwechslung. Current-PK bleibt asset_id. Keine spekulativen großen
Unit-History-Indizes; tatsächliche spätere Querypläne separat nachweisen.

## Fachliche Prüffälle und offene Implementierungsschritte

| Synthetischer Fall | Erwartung |
| --- | --- |
| EUR@1 / GBP@1 | Native Zahl und Geldwährung erhalten, Basisprojektion 1/1 |
| GBX@1 → GBP@1 | Exakt 1/100 ohne Float oder Rundung, native Zahl bleibt erhalten |
| POINT@1 | currency=NULL, Faktor 1/1, keine Geldwährung/XXX nötig |
| Nenner 0, negativer Faktor, nicht gekürzter Faktor | Ungültige Definition, keine Nutzung |
| Ergebnis mit periodischer Dezimaldarstellung | Exaktheitsfehler statt impliziter Rundung |
| Native vs. Projektion | Nur eine native Tatsache; Projektion ist keine weitere History |
| v1 vor/nach Entwurf | Kanonische Bytes/Hash und echter PHP-Source unverändert |
| v2 bei Unitkey-/Versions-/Mengenbasisänderung | Andere kanonische Identität; nicht zur Route passende Bindung vorher abweisen |
| B6/B7 / B5 | Derselbe Unitgrundvertrag, übrige Blocker bleiben bestehen |

Die Unit-/Hash-Prüffälle werden nur synthetisch als private Entwurfsgegenprobe
geprüft; sie sind **keine implementierte v2-Laufzeit oder Writerfreigabe**.
Vollständige bestehende Regressionen, Webdateivalidierung und Diff-Prüfung bleiben
verbindlich. Keine geänderten PHP-Dateien, kein neuer Adapter notwendig.

Offen für eine separat freizugebende Implementierung: physische Spalten-/Längen-
und Ganzzahlgrenzen, atomarer Constraintwechsel der Routen, Checks/FK-Abdeckung,
parallelitätssichere Routenrevisionen und Dispatcher-/Replay-Nachweis. Neue
normative Einheiten brauchen belegte Definitionen; konkrete B8-Stammdaten-/
Routenevidenz bleibt nachzuholen. B8 ist fachlich modellierbar, **noch nicht
importierbar**. Kein Live-Zielzustand wurde in Phase 3I geprüft.

Keine Migration 0003, SQL-/DB- oder Datenänderung, kein Browser/Dogado/Plesk,
Provider-Fetch, Import oder Deployment. Die acht bestehenden Observations,
Homepage, dynamisches Ladezeitscript, v1-Funktionen und Migrationen bleiben
unverändert. Alle weiteren Schema-/Evidenz-/Importarbeiten benötigen eigene
Freigabegrenzen; diese Phase endet mit Dokumentation, Tests und Nachweisen.

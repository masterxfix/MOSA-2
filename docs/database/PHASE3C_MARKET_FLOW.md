# MOSA 2 – Phase 3C: kontrollierter Marktdaten-Schreibfluss

**Status:** Spezifikation; noch nicht live ausgeführt  
**Grundlage:** Phase 3B am 19.10.2026 erfolgreich abgeschlossen; 16 Tabellen, Ledger v1+v2, alle 15 Nicht-Ledger-Tabellen leer  
**Ziel:** Den fachlichen Schreibfluss History → Current mit kleinen synthetischen Beispieldaten reproduzierbar nachweisen, bevor echte MOSA-Marktdaten übernommen werden.

## Scope

Phase 3C prüft ausschließlich:

- normalisierte synthetische Marktbeobachtungen;
- deterministischen Dedupe-Schlüssel;
- append-only History;
- transaktionale Current-Aktualisierung;
- Schutz gegen Rückschreiben älterer Marktzeitpunkte;
- deterministische Behandlung desselben Marktzeitpunkts innerhalb derselben Route;
- Route-/Asset-/Source-Konsistenz vor dem Schreiben;
- begrenzte History-/Bar-Lesewege und deren Laufzeiten;
- vollständigen Rollback der synthetischen Daten.

Nicht Teil dieser Phase:

- echte MOSA-Daten;
- produktive Collector oder Scheduler;
- Provider-Sonderlogik;
- Cross-Source-Arbitration für Current;
- Depot, News, KI oder Prognosen;
- Produktivdeployment.

## Schreibvertrag

Für eine synthetische Observation gilt:

1. Eingabe fachlich validieren.
2. Asset, Source und Route müssen existieren.
3. Die Route muss zum selben Asset und zur selben Source gehören.
4. Dedupe-Schlüssel zentral und deterministisch aus dem kanonischen Observation-Payload bilden.
5. Observation append-only in `m2_market_observations` schreiben.
6. Bereits vorhandener identischer Dedupe-Schlüssel erzeugt keine zweite History-Zeile.
7. Current wird innerhalb derselben Transaktion geprüft und ggf. aktualisiert.
8. Ein älterer `market_at` darf Current niemals überschreiben.
9. Bei gleichem `market_at` innerhalb derselben Route gewinnt nur ein neueres `observed_at`; bei identischem `observed_at` bleibt Current unverändert.
10. Fehler führen zum vollständigen Rollback.

Cross-Source-/Cross-Route-Auswahl für einen Asset-Current wird in Phase 3C nicht erfunden. Die Tests verwenden pro Testfall eine eindeutig ausgewählte Route.

## Dedupe

Der Dedupe-Schlüssel ist SHA-256 über eine zentrale kanonische Darstellung mindestens dieser Felder:

- asset_id
- source_id
- route_id
- currency
- market_at
- price
- bid
- ask
- volume

NULL-Werte und DECIMAL-Werte müssen eindeutig und stabil serialisiert werden. Keine provider- oder asset-spezifische Sonderlogik.

## Testfälle

Mindestens nachweisen:

- erste Observation erzeugt genau eine History-Zeile und Current;
- identische Observation erneut: keine zweite History-Zeile, Current unverändert;
- neuere Observation: History wächst um eins, Current wird aktualisiert;
- ältere Observation: History wächst um eins, Current bleibt auf dem neueren Stand;
- gleicher Marktzeitpunkt, neueres observed_at auf derselben Route: Current wird deterministisch aktualisiert;
- gleicher Marktzeitpunkt und identisches observed_at: Current bleibt unverändert;
- falsche Route-/Asset-/Source-Kombination wird vor dem Schreiben abgewiesen;
- absichtlich erzeugter Fehler rollt Observation und Current gemeinsam zurück;
- mehrere Assets beeinflussen sich nicht gegenseitig.

## Live-Test in Phase 3C

Der spätere Live-Nachweis verwendet nur wenige synthetische Assets/Sources/Routes und bleibt vollständig rollbackfähig. Nach dem Test müssen alle 15 Nicht-Ledger-Tabellen wieder leer sein; Ledger v1+v2 bleiben unverändert.

## Performance-Ziele

Auf der isolierten Testplattform:

- Current-Lesen ideal < 20 ms;
- begrenzte Observation-/Bar-Abfragen < 100 ms;
- keine ungebundenen Full Scans.

Die Messung ist ein kleiner Funktions-/Latenznachweis, keine Last- oder Produktivfreigabe.

## Ablauf

### 3C-A – Repository-Prüfcode

- zentrale, providerneutrale Schreib-/Dedupe-Logik für den Testpfad;
- deterministische Offline-Regressionstests;
- keine DB-Verbindung.

### 3C-B – isolierter Live-Nachweis

Erst nach separater Freigabe:

- Preflight: 16 Tabellen, Ledger v1+v2, alle 15 Nicht-Ledger-Tabellen leer;
- synthetische Core-/Asset-/Route-Fixtures in einer Transaktion;
- Schreibvertrag vollständig prüfen;
- Lesezeiten messen;
- vollständiger Rollback;
- finaler unabhängiger Leerstandscheck.

## Erfolgskriterium

Phase 3C ist erfolgreich, wenn der History→Current-Schreibvertrag deterministisch nachgewiesen ist, Dedupe und zeitliche Regeln funktionieren, Fehler atomar zurückrollen, die vorgesehenen Lesewege im Budget bleiben und nach dem Live-Test keine synthetischen Fachdaten zurückbleiben.

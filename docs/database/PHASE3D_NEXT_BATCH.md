# Phase 3D-D – zweites Marktdatenpaket (nur Planung)

## Ergebnis

Die exakt fünf eingefrorenen Restkandidaten wurden gezielt geprüft. Ein einziger
SELECT auf `fixlab_portfolio_assets` ergab fünf passende aktive Datensätze.
Die frühere negative `fixlab_assets`-Prüfung bleibt unverändert gültig.

| Nachweis | Anzahl |
| --- | ---: |
| Geprüfte feste Restkandidaten | 5 |
| Eindeutiger gespeicherter Portfolio-Name | 5 |
| Gültiger Frankfurt-STOCK-Beleg im selben Identitätskontext | 5 |
| Passende ETF-Referenz | 0 |
| Namens-/Klassen-/Identitätskonflikte | 0 |
| Klasse explizit belegt (`stock` → `equity`) | 5 |
| Weiterhin fachlich gesperrt | 0 |
| Paket-2-geeignet | 5 |
| Ausgewähltes Paket (P2-A1 bis P2-A3) | 3 |
| Wegen Paketgrenze zurückgestellt | 2 |
| Assets bestehend / neu | 0 / 3 |
| Sources bestehend / neu (unterschiedliche Katalogobjekte) | 1 / 1 |
| Routes bestehend / neu | 0 / 3 |
| Bedingt geplante Inserts nach Katalogauflösung | 3 |
| Bereits abschließend belegte `expected_insert` / `expected_duplicate` | 0 / 0 |
| Endgültiger Dedupe-Key noch offen | 3 |

## Beweiskette und Grenzen

Namen stammen unverändert aus dem gespeicherten `display_name`, abgeglichen mit
vorhandenen Instrument-/Market-Identity-Belegen. Die Klassenregel stammt aus
`php/mosa_market_live_quote_runner.php` im Quellprojekt: eine gültige gespeicherte
Frankfurt-Registrierung (`found`) für denselben Benutzer, Asset-Schlüssel und
dieselbe ISIN liefert explizit `stock`. Der vollständige Registrierungskontext,
nicht der Provider allein, ist der Beleg. ETF erfordert einen gültigen bestehenden
Referenzvertrag und eine passende aktive Beziehung. Gleichzeitiger STOCK-/ETF-
Beleg sperrt. Namen, Währungen, Symbole oder ISIN-Präfixe erzeugen keine Klasse.

Die private Beweiskette enthält je Kandidat Identitätsfingerprints, Portfolio-
Zeilenfingerprint, gespeicherte Registrierungen, expliziten Roh-Typbeleg,
Konsistenzprüfung und Eligibility. Reale Namen, Identitäten, Benutzerkontexte,
Marktzeilen und private Quellreferenzen werden nicht veröffentlicht.

Das private Manifest bindet Snapshot, ursprünglichen Dry Run, Phase-3D-C-
Zielreport, bisherigen Sperrbefund, die negative Registry-Prüfung, neue gezielte
Belege und Quellvertragsversionen über Fingerprints. Zwei Offline-Läufe sind
bytegleich. Es enthält die drei Paketkennungen, belegte Namen/Klassen,
Source-/Route-Planung und normalisierte Observations, jedoch keine Credentials.
Der Manifest-Fingerprint ist SHA-256 des kanonischen JSON ohne sein eigenes Feld.

Die Auswahl bevorzugt bestehende Assets, Sources und Routes, anschließend die
stabile private Quellreferenz; maximal drei. Die drei früher importierten Fälle
und die acht ursprünglich nicht transformierbaren Fälle bleiben ausgeschlossen.
Source-/Route-Zustände beziehen sich ausschließlich auf den verifizierten privaten
Phase-3D-C-Zielreport, nicht auf einen frisch abgefragten Datenbankstand.

Neue Assets und Routes besitzen noch keine realen IDs. Daher bleibt der finale
Dedupe-Key null; die Aktion heißt `planned_insert_after_catalog_resolution`.
Nur bei vollständig belegten realen IDs verwendet der Offline-Planer direkt die
zentrale Phase-3C-Normalisierung und Dedupe-Funktion. Keine Ersatz-IDs und keine
zweite Hashlogik. Vor einem später freizugebenden Import sind Katalog, aktuelle
Zielkonflikte, echte IDs und Dedupe erneut kontrolliert aufzulösen.

## Offline-Logik und Tests

`scripts/phase3d/next_batch.php` verarbeitet ausschließlich zuvor extrahierte
Evidenz. Es besitzt keinen DB-/Quellreader, Provider-Fetch oder Schreibadapter.
ETF-Evidenz ist eine ausdrücklich vorvalidierte Hülle: ursprünglicher
Referenzvalidator und aktive Identitäts-/Beziehungsprüfung müssen erfolgreich
sein. Die hier tatsächlich geprüften fünf Fälle haben keine ETF-Treffer.
Synthetische Tests prüfen Namen, Kontext, STOCK/ETF-Konflikte, fehlende Typbelege,
Paketgrenze, deterministische Priorität und Wiederverwendung des Phase-3C-Dedupe.

## Ausführungsgrenze

Kein MOSA-2-DB-Zugang, Passwort, Gateway, Import, Checkpoint-Write oder DDL.
Kein Current, keine Bars, kein Collector/Scheduler, kein Provider-Aufruf.
Quelle nur read-only; keine Quelländerung. Homepage und Ladezeit bleiben
unverändert. Kein Deployment und keine Produktionsaktion. Ein separater späterer
Testimport benötigt eine eigene Freigabe.

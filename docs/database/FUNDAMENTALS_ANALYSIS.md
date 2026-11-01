# Universeller Analysevertrag

`mosa2-ai-analysis-input-v1` wird bei Bedarf aus Schema 6 erzeugt, ohne Speicherung.
Alle Assets mit asset_class=equity werden berücksichtigt; ETF und andere Klassen
werden anhand des DB-Feldes ausgeschlossen. Je Aktie: Identität/ISIN, vorhandene
Fakten, Current-Referenzen, Perioden, Quellen, fehlende Kernkennzahlen und Warnungen.
Fehlende Daten sagen nichts über ihre Beschaffbarkeit aus: Verfügbarkeit wird nicht
behauptet. Registrierte Quellen sind keine nachgewiesene Aktienabdeckung.
Marktpreisquellen werden getrennt von belegten Fundamentalquellen ausgewiesen.

Fakten referenzieren Observation, Fetch, Feldposition und Datei-Hash. Herkunft über
Source-Typ/Parser; kuratierte Werte bleiben als manuell recherchiert und gerundet
gekennzeichnet. Originalarchive werden weder geöffnet noch verändert. Nicht belegte
Präzision anderer Quellen bleibt unbekannt. Jede Berechnung enthält ihre Observation-IDs.

Veränderungen nur zwischen aufeinanderfolgenden Jahren derselben Metrik, Quelle,
Einheit, Periodenart, Quartal und Kalendergrenzen. Kein FY/FQ-Mix, keine Währungs-
umrechnung. Margen skalieren Originaleinheiten rational und verlangen gleiche
Periode, Quelle und Währung. Positive Umsatzbasis ist erforderlich. Wachstum aus
negativer oder Nullbasis wird ausgelassen und mit Warnung erklärt. Keine Nullersetzung.
Mehrdeutige Perioden sind nicht automatisch aufzulösen. Decimal-Ergebnisse sind
berechnete Werte, keine zusätzliche Genauigkeit der gerundeten Ausgangsfakten.

Der zukünftige Modell-Ausgabevertrag heißt `mosa2-ai-assessment-v1`:
- input_contract und input_digest: genaue Zuordnung zum gehashten Eingabepaket;
- model_id, generated_at und invocation_id: Nachweis eines tatsächlichen Modellaufrufs;
- factual_claims: Text mit Observation-IDs;
- calculation_claims: Text mit Berechnungsreferenzen;
- interpretations: klar gekennzeichnete Schlussfolgerungen mit Faktenreferenzen;
- uncertainties und missing_information: offene Fragen ohne geschätzte Ersatzwerte.
Keine Kauf-/Verkaufsempfehlungen oder erfundenen Prognosen. Ohne Modellaufruf
bleibt interpretations leer; regelbasierte Ergebnisse sind keine ausgeführte KI.

Manueller Workflow fundamentals-analysis.yml, exakter Main-Commit und
MOSA2-ANALYSIS:<commit>, Versuch 1. Nur SELECT/EXPLAIN und Read-only-Transaktion;
keine Providerrequests oder Archive. Begrenzung: 128 Assets, 256 Fakten pro Aktie,
128 Quellen, 256 globale Fundamentalzeilen zur Bestandsschutzprüfung; Überschreitung
stoppt statt still abzuschneiden. Aktueller kleiner Bestand wird vollständig gelesen.
Current-PK und History-Index werden mittels bestehendem EXPLAIN ANALYZE geprüft;
Clientzeiten enthalten Tunnel/Netz, SSH-Aufbau wird separat gemessen. Globale
Bestandsfingerprints sind expliziter Beweis-Modus, kein normaler UI-Abfragepfad.
Öffentliche Zusammenfassung enthält ausschließlich Unternehmensdaten, keine Depots.

Nächster Schritt: Modellzugang, Kostenobergrenze und Aufrufautorisierung klären,
danach einen einzelnen Modellaufruf mit Referenzprüfung gegen diesen Vertrag bauen.

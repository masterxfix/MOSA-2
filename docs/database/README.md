# MOSA 2 – Datenbank

Dieser Bereich beschreibt die geplante Datenbank für MOSA 2. Die neue Struktur wird **parallel zu MOSA** aufgebaut. MOSA wird nicht abgeschaltet, sondern bleibt weiterhin nutzbar und dient als Spielwiese/Labor für neue Ideen und Funktionen.

## Priorität 1: saubere Datenmigration

Die bereits in MOSA vorhandenen, wertvollen Daten müssen kontrolliert nach MOSA 2 übernommen werden. Dabei gilt:

- keine 1:1-Kopie der alten Datenbank;
- MOSA wird nur **read-only** als Quelle gelesen;
- Daten werden auf die neue MOSA-2-Struktur abgebildet, geprüft und erst dann übernommen;
- Migrationen müssen wiederholbar sein und dürfen keine Dubletten erzeugen;
- große Datenmengen werden schrittweise mit Checkpoints übernommen;
- nach jedem Import werden fachliche Ergebnisse zwischen MOSA und MOSA 2 verglichen;
- technische Altlasten werden nicht automatisch mitmigriert.

MOSA bleibt während der gesamten Migration eigenständig nutzbar.

## Arbeitsmodell MOSA → MOSA 2

MOSA bleibt die experimentelle Umgebung. Neue Ideen können dort weiter ausprobiert und entwickelt werden. **Nur ausgereifte und fachlich bestätigte Funktionen oder Datenmodelle werden gezielt in MOSA 2 übernommen.**

MOSA 2 ist damit nicht der sofortige Ersatz für MOSA, sondern die stabile, saubere Zielarchitektur.

## Ziele

- **Sehr schnelle Seiten:** normal unter 1 Sekunde, p95 unter 1,5 Sekunden, harte Grenze 2 Sekunden.
- **Geringe Latenz:** normale Seiten sollen nur kleine, gezielte DB-Abfragen benötigen.
- **Keine Sonderlocken:** NEL, PNE, Rheinmetall usw. nutzen dieselbe Datenlogik.
- **Klare Identitäten:** ein Asset besitzt eine eindeutige interne ID; ISIN, WKN und Provider-Symbole sind nur zugeordnete Kennungen.
- **Saubere Trennung:** aktueller Zustand und große Historien werden getrennt gespeichert.
- **Nachvollziehbar und sicher:** Schema und Migrationen werden in GitHub versioniert und kontrolliert ausgeführt.

## Grundprinzip

MOSA hat gezeigt, dass große Historienabfragen eine eigentlich schnelle Seite massiv verlangsamen können. Nach passend aufgebauten Indizes fiel ein kritischer MOSA-Abfrageweg von mehreren Sekunden auf wenige Millisekunden.

MOSA 2 wird deshalb vom **schnellen Leseweg** aus geplant:

```text
Collector / Verarbeitung
        ↓
History / Wahrheit
        ↓
Current / fertiger Zustand
        ↓
Webseite
```

Eine normale Webseite soll den aktuellen Zustand direkt lesen und nicht bei jedem Aufruf aus Millionen historischen Datensätzen neu berechnen.

## Geplante Struktur

Die Namen sind zunächst Arbeitsnamen.

| Bereich | Tabellen / Aufgabe |
| --- | --- |
| Identität | `m2_assets`, `m2_asset_identifiers`, `m2_sources`, `m2_asset_source_routes` |
| Markt aktuell | `m2_market_current` |
| Markt Historie | `m2_market_observations`, `m2_market_bars` |
| Collector | `m2_collector_current`, `m2_collector_runs`, `m2_source_attempts` |
| Depot | `m2_accounts`, `m2_portfolio_transactions`, `m2_cashflows`, `m2_positions_current`, `m2_portfolio_current` |
| News | `m2_news_items`, `m2_news_assets`, `m2_news_state`, `m2_news_analysis` |
| MOSA-Status | `m2_story_current`, `m2_action_current`, `m2_asset_state`, `m2_dashboard_current` |
| Betrieb | `m2_schema_migrations`, `m2_sync_checkpoint`, `m2_job_state` |

## Wichtige Regeln

1. **Current und History bleiben getrennt.** History ist für Charts, Analyse und Nachvollziehbarkeit; normale Seiten lesen Current-Daten.
2. **Keine externen APIs oder KI im normalen Seitenaufruf.** Diese Arbeit erfolgt vorher; die Seite zeigt nur das gespeicherte Ergebnis.
3. **Keine Asset-Sonderlogik.** Unterschiede zwischen Assets und Datenquellen werden über Daten und Konfiguration abgebildet.
4. **Indizes werden mit dem Query geplant.** Kritische Abfragen erhalten von Anfang an einen Index passend zu Filter und Sortierung.
5. **History-Abfragen sind begrenzt.** Immer Asset/Zeitraum/LIMIT statt ungebundener Vollsuche.
6. **MOSA und MOSA 2 bleiben getrennt.** Kein Trigger- oder Dual-Write-Zwang. Daten werden kontrolliert und mit Checkpoints übernommen.
7. **DB-Änderungen sind eigene, kontrollierte Schritte.** Preview → Check → ausdrückliche Freigabe → Apply → Postcheck.

## Parallelaufbau

1. Leeres MOSA-2-Schema und Performance-Grundtests.
2. Asset- und Identitätsmodell aufbauen.
3. Wertvolle MOSA-Daten kontrolliert und zunächst in kleinen Paketen übernehmen.
4. MOSA 2 im Shadow-Modus gegen MOSA vergleichen.
5. Historie schrittweise und per Checkpoint übernehmen.
6. Nur ausgereifte Funktionen nach fachlicher Bestätigung in MOSA 2 übernehmen.

## Performance-Budget

| Ebene | Ziel |
| --- | ---: |
| normale DB-Abfrage | ideal < 20 ms |
| zugelassene langsamere DB-Abfrage | < 100 ms |
| gesamte DB-Zeit einer normalen Seite | < 200 ms |
| normaler Seitenaufruf | < 1,0 s |
| p95 Seitenaufruf | < 1,5 s |
| harte Obergrenze | **2,0 s** |

Dieses Dokument ist der Ausgangspunkt. Detailtabellen, Keys, Indizes und Migrationsschritte werden hier schrittweise ergänzt, bevor produktive Daten übernommen werden.

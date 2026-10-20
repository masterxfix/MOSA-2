# Phase 3L – normative Unit-Seeds, vollständig offline

Issue #28; Ausgangspunkt `a52ac032dea35a2c9548d5d11abd50515e359163`.
Das [Manifest](seeds/0001_market_units_v1.json) ist die einzige Datenquelle.
Die generische [Python-Logik](../../scripts/phase3l/unit_seed.py) nutzt nur die
Standardbibliothek, keine DB-Verbindung, Credentials, Provider oder SQL-Ausführung.
Ausführung vom Repository: `python scripts/phase3l/unit_seed.py`.
Gezielte Tests: `python -m unittest discover -s tests -p test_unit_seeds_phase3.py -v`.

## Vier eingefrorene Definitionen

Alle Definitionen: Version `1`, Vertrag `mosa2-market-unit-v1`, Status `frozen`.
Keine Provider-, Asset-, Ticker-, Routen-, Marktwert- oder FX-Bindung.

| Unit | Dimension | direkte Basis | Geldwährung | Faktor |
|---|---|---|---|---|
| EUR@1 | monetary | EUR@1 | EUR | 1/1 |
| GBP@1 | monetary | GBP@1 | GBP | 1/1 |
| POINT@1 | index_point | POINT@1 | NULL | 1/1 |
| GBX@1 | monetary | GBP@1 | GBP | 1/100 |

EUR/GBP sind volle native Geldeinheiten. GBX ist die Pence-Sterling-Quoteeinheit,
keine eigene Geldwährung; currency bleibt GBP. Die native Zahl bleibt erhalten.
Eine GBP-Darstellung ist eine exakte Projektion derselben Tatsache: keine zweite
Observation, künstliche Route oder FX-Konvertierung. POINT ist nichtmonetär;
keine XXX-Pseudowährung, keine behauptete Vergleichbarkeit verschiedener Indizes.
Asset-/Indexidentität ist ein eigener Vertrag.

## Kanonische Definition und SHA-256

Einziger normativer Serialisierer: `canonical_definition`. Bytes sind exakt
`mosa2-unit-definition-v1` + ein LF + kompaktes UTF-8-JSON, ohne abschließendes LF.
Feste Feldreihenfolge:

1. unit_key
2. unit_version
3. unit_contract_version
4. dimension_key
5. base_unit_key
6. base_unit_version
7. monetary_currency_code
8. scale_numerator
9. scale_denominator
10. status

Alle Integer werden als positive kanonische Dezimalstrings serialisiert, ohne
Pluszeichen/führende Nullen. JSON null bleibt explizit null. ASCII-Schlüssel,
Python-Ganzzahlen und feste JSON-Optionen machen den Hash unabhängig von Locale,
Whitespace, Eingabeschlüsselreihenfolge, Rechner, OS, Pfad und Git-Commit.
Kein SQL-Text oder Beschreibungstext fließt ein. Der öffentliche Hexhash bezeichnet
genau 32 rohe SHA-256-Bytes für das spätere `BINARY(32)`-Feld (`bytes.fromhex`).

`definition_reference` verweist auf Phase 3I und diesen Vertrag. Sie ist nicht
persistiert und nicht im Definitionhash, aber im Paketfingerprint gebunden.
Das erste Paket enthält bewusst kein `created_at`: Der spätere freizugebende
Insertplan muss einen eingefrorenen UTC-DATETIME(6)-Wert bestimmen. Die generische
Logik akzeptiert optional einen solchen expliziten Metadatenwert; er beeinflusst
den Definitionhash nicht und wird, wenn vorhanden, im Paketfingerprint gebunden.
Es wird nie eine aktuelle Laufzeit erzeugt. Unbekannte Felder werden abgewiesen.
Andere Vertragsversionen/Statuswerte werden bereits vor der Hashbildung abgelehnt;
die kanonische Feldliste bindet beide Werte ausdrücklich für zukünftige Verträge.

| Unit | definition_sha256 (Hex) |
|---|---|
| EUR@1 | `4d2e721264795c68d1d5434cdab7c53199ba4270c1cd43114200f9e86de1c4c4` |
| GBP@1 | `dcf7b65464052cd34b4e98a0fc7abcf32b53543117af2a612965f0ed3f4fb10a` |
| POINT@1 | `29c50d2fad8e5176e9c4204579c1b33b9e7883f3afe8fe3cbfc097efd72b7092` |
| GBX@1 | `c80d04b9e0b1ee996242364ffbfea7b37fbda9c23f746356072b43cce551ddd6` |

## Paketfingerprint und deterministische Reihenfolge

`manifest_format=mosa2-unit-seed-manifest-v1`, `package_key=market-units-v1`,
`package_version=1` (kanonischer String). Paketbytes:
`mosa2-unit-package-v1` + LF + kompaktes UTF-8-JSON ohne abschließendes LF.
Feste Reihenfolge: manifest_format, package_key, package_version,
unit_contract_version, definitions. `package_sha256` selbst ist ausgeschlossen.
Definitionszeilen bestehen aus den zehn normalisierten Feldern, gefolgt von
definition_sha256, definition_reference und optional created_at, genau in dieser
Reihenfolge. Definitionhashes werden vor Paketbildung vollständig validiert.

Sortierung: erst Self-Bases, dann abhängige Units; innerhalb jeder Gruppe
ASCII-unit_key und numerische unit_version. Für dieses Paket ergibt das
**EUR@1, GBP@1, POINT@1, GBX@1**. Auch bei anders sortiertem Eingabearray bleibt
der Fingerprint identisch. Er bindet alle Definitionen, deren Hashes und Evidenz
sowie Paketidentität/-version. Freigabeanker:

`b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee`

## Validierung und exakte rationale Rechnung

Die gemeinsame Engine kennt keine Sonderfälle für einzelne Unitkeys. Sie prüft
Pflichtfelder, erlaubte Zusatzmetadaten, kanonische ASCII-Keys (Unitkeys
`[A-Z][A-Z0-9_]{0,63}`, Dimension `[a-z][a-z0-9_]{0,63}`), positive Versionen
bis 4294967295, Faktorgrenzen bis 38 Dezimalstellen, gcd=1, frozen und bekannten
Vertrag. Floats, bool, Exponenten, nichtkanonische Integerstrings, Null/negative
Faktoren und doppelte JSON-Member/Unitidentitäten werden abgewiesen.

Monetary verlangt einen echten fachlich genehmigten Währungscode; syntaktisch
drei ASCII-Großbuchstaben, XXX ausdrücklich ausgeschlossen. Das Tool ersetzt
keine Währungscode-Governance; EUR/GBP sind hier normativ festgelegt. Andere
Dimensionen verlangen NULL. Basisreferenzen müssen existieren und dieselbe
Dimension/Geldwährung haben. Self-Bases verlangen 1/1. Jede abgeleitete Unit
zeigt direkt auf eine Self-Base; keine Ketten A→B→C und keine anderen Zyklen.
Hashabweichungen oder unbekannte normative Felder stoppen die Validierung.

`project_exact` rechnet ausschließlich über Ganzzahlen und rationale Brüche.
Synthetisch: native `12345` GBX ergibt exakt `123.45` GBP; 1/1 bleibt exakt.
2/200 wird als nicht gekürzt abgelehnt, ebenso Nenner 0 und negative Faktoren.
Native Dezimalstrings respektieren DECIMAL(32,8); Ausgabeskala 0..8. Periodische,
zu große oder in dieser Skala nicht exakt darstellbare Ergebnisse liefern
`normalization_unrepresentable`; kein Runden, keine FLOAT-/DOUBLE-Zwischenwerte.

## Späterer Insertplan und Aussagegrenzen

Grundlage ist ausschließlich der dokumentierte [Phase-3K-Endzustand](PHASE3K_UNIT_SCHEMA_LIVE.md):
Schema 3, 17 Tabellen, Ledger v3, Units 0, unveränderte acht Observations,
Current/Bars 0. Dieser Auftrag hat den Zustand **nicht** erneut live abgefragt.
Migration 0003, Observation-v1 und Homepage einschließlich Ladezeitdateien bleiben
byteidentisch. Es wird keine SQL-Vorschau gepflegt oder ausgeführt.

Vor einem späteren Insert: eigene ausdrückliche Freigabe, exakter Paketfingerprint,
isoliertes genehmigtes Ziel, Schema-/Versionsprüfung, frozen UTC-created_at-Plan,
vollständige Semantikprüfung und konfliktfreier Istzustand. Geplante Reihenfolge
EUR, GBP, POINT, dann GBX (GBP existiert zuvor).
Die Dokumentation und Phase-3K-Proben belegen Self-Base grundsätzlich, jedoch
hier keinen überprüften Einzel-INSERT-Ablauf für exakt diese Definitionen unter
MySQL 8.0.26-16. Deshalb **separater kontrollierter praktischer Precheck** der
Self-FKs mit rollbackbaren synthetischen Zeilen vor jedem normativen Insert;
bei Scheitern stoppen. Keine FK-Deaktivierung, Schemaänderung oder geratenes
Insertverhalten. Dieser praktische Precheck wurde hier nicht ausgeführt.

**Keine Seeds live, keine DB-Verbindung, kein Ledgerwrite, kein Writer-v2,
kein B8-Import, kein Browser/Provider/Gateway/Dogado/Plesk, kein Deployment,
keine Produktion.** B8 bleibt bis zu separaten Seed-, Writer- und
Identitäts-/Routenevidenzfreigaben gesperrt. Der nächste Schritt benötigt eine
eigene ausdrückliche Freigabe; dieses Paket löst ihn nicht aus.

## Prüfnachweise

Gezielte Seedtests: **29/29** bestanden. Vollständige lokale Windows-Regression:
**286/287**, ausschließlich bekannte Abweichung `budget_not_private`.
Deployment-Dateivalidierung und `git diff --check` bestanden; keine geänderten
PHP-Dateien. Der erste gezielte Lauf erforderte eine Korrektur der Testhilfe
(Mutationen zwischen Negativfällen isolieren) und ein beschreibbares temporäres
Verzeichnis im Workspace; der anschließende Lauf bestand vollständig.
Der exakte Abschlusscommit, Linux-Ergebnis/Run-ID und der Nachweis des skipped
Produktionsdeployments werden im Abschlusskommentar zu Issue #28 festgehalten.
Der native Recorderstart scheiterte an `PROMPT_RECEIPT_MISSING`; Describe und
Plan wurden jeweils einmal versucht und fanden keinen offenen Auftrag für den
tatsächlichen nativen Turn. Keine Ereignisse/IDs/Erfolgsnachweise rekonstruiert.

# Current-Anzeige: gemeinsamer qualifizierter Leseumfang

Der Current-Endpunkt liest die fünf bereits qualifizierten ISIN-Beziehungen aus
`api/qualified_scope.php`. Physische Asset-/Route-IDs werden per begrenztem SELECT
aufgelöst. Der frühere numerische private Zwei-Asset-Scope ist für Current nicht
mehr maßgeblich; private Konfiguration und Zugang bleiben unverändert.

Ausschließlich `m2_market_current` liefert die angezeigten Werte. Die exakt
referenzierte Observation v2 wird mit der gemeinsamen Source-/Route-/Unit- und
Dedupe-Prüfung verglichen. Fehlendes Current bleibt fehlend; ungültige Bindungen
brechen geschlossen ab. Alter und Kennzeichnung verwenden den Marktzeitpunkt.
Dezimalwerte bleiben Strings. Deaktivierte Routen werden beim Lesen weder
aktiviert noch als Ausführungsgenehmigung behandelt.

Die vorhandene Auswahl liegt einmalig als reiner Web-Kern unter
`api/market_core/`; die bisherigen CLI-Module verwenden diesen selben Kern.
Der eingefrorene v1-Vertrag bleibt byteidentisch. Seine kleinen Parser-Primitiven
liegen für den Web-Kern in einem getrennten Namespace; ein Test prüft ihren
Funktionskörper bytegleich gegen v1. Die Kursauswahl selbst existiert nur einmal. Der lokale Unit-Katalog
ist bytegleich zum unveränderlichen normativen Seed und weiterhin SHA-256-gepinnt.
Kein CLI-Einstieg, Provider oder Writer gehört zum Web-Paket. Observation-Auswahl,
Query und Anzeigeverhalten bleiben unverändert; die Bindungsfunktionen sind
zwischen beiden Lesern geteilt.

## Testsite-Paket und Nachweis

Der manuelle Testsite-Workflow verlangt einen exakten Commit und einen expliziten
vollständigen Lese-Paketsatz. Vor dem Upload sichert er vorhandene Dateien
verschlüsselt als Actions-Artefakt (30 Tage, AES-GCM mit HKDF und vorhandenem
SSH-Secret). Wiederherstellung: HKDF-SHA256, 32 Byte, Salt aus Envelope,
Info/AAD `mosa2-testsite-web-backup-v1`, Nonce aus Envelope; danach JSON mit
`before`-Hashes und Base64-`files`. Keine neuen Zugangsdaten. Der Upload prüft
die Ausgangshashes erneut sowie temporäre und endgültige SHA-256-Readbacks.
Private Konfiguration, CLI-Module und installierter Collector bleiben außerhalb
des Pakets.

Ein anschließender eigenständiger READ-ONLY-Reconcile kann zusätzlich einen
SHA-256 über die fünf angezeigten nativen Current-Werte, Einheiten, Quellen und
beide Zeitpunkte liefern. Private Werte/IDs erscheinen dabei nicht in Actions.
Der Browserabgleich verwendet dieselbe geordnete JSON-Tupelform aus
`scripts/current_web_verify.php`. Der Hash ist ein Vergleichsnachweis; er ersetzt
keinen Provenance-Nachweis (diesen liefert Reconcile gesondert).

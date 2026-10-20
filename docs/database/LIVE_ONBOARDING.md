# Gemeinsames Live-Onboarding

`scripts/market_collector/onboarding.php` extrahiert die allgemeine Phase-3D-Asset-/ISIN-Auflösung. Der Phase-3D-Importer und der Livepfad verwenden denselben reinen Planer und INSERT-Executor. Qualifizierte Namen werden exakt verglichen; widersprechende Identitäten und mehrere Kandidaten sind Konflikte. Historische Importe behalten zusätzlich ihre fingerprintgebundenen Zeitstempelprüfungen.

`planAssetIdentity` entscheidet zwischen EXISTING_MATCH, BIND_IDENTIFIER, CREATE_ASSET_AND_IDENTIFIER und CONFLICT. `applyAssetIdentityPlan` bestätigt den Plan gegen den Transaktionsbestand und liest die Bindung nach INSERT zurück. UPDATE, UPSERT und heuristische Reparaturen sind nicht Bestandteil des Vertrags.

`planMarketRoute` verarbeitet qualifizierte Eingaben durch den vorhandenen Phase-3D-Routenalgorithmus. Der externe Schlüssel verwendet dessen market-v1-SHA-256-Vertrag. Beide UNIQUE-Gruppen von Migration 0003 werden geprüft. Neue Gruppen beginnen mit Revision 1; bestehende Gruppen erhalten die nächste positive Folgerevision. Unitbindung und Revision sind immutable; eine bestehende Route wird niemals verändert. Neue Live-Routen sind deaktiviert und wählen kein Current aus.

`live_persistence.php` plant alle Voraussetzungen und Deltas vor dem Providerabruf. Ein identifiergebundener Lock wartet nicht. Die einmalige anonyme HTTPS-Antwort wird vor der Schreibtransaktion erworben; es gibt noch keine erfundene Route-ID. Innerhalb einer einzigen Transaktion werden der Plan erneut bestätigt, Asset/Identifier und Route angelegt und die unveränderte Antwort mit tatsächlichen IDs durch Collector, Provideradapter, gemeinsamen Normalizer und Phase-3N WriterPlanner verarbeitet. INSERT, exakter Readback und DUPLICATE_UNCHANGED mit identischen Canonical Bytes und Dedupe-Key sind Voraussetzungen des COMMIT.

Ein Fehler rollt alle neuen fachlichen Zeilen zurück. Es gibt keinen Teilcommit, Retry oder zweiten Providerrequest. Eine unabhängige Verbindung prüft nach COMMIT bzw. Rollback die tatsächlichen Deltas und alle bisherigen Zeilen. Sources, vier Units, Ledger v1/v2/v3, Checkpoints, Current und Bars bleiben unverändert. Der Phase-3O-Executor erhält dafür einen expliziten Zeitstempel; sein historischer Standardwert bleibt erhalten.

Providerwissen und Requestsemantik bleiben im jeweiligen Adapter bzw. seinem qualifizierten historischen Sourcekontext. Zugangsdaten erreichen weder den Python-Prozess noch Dateien, URLs oder Providerrequests. Reale Assetdaten stehen ausschließlich im privaten Auftragsmanifest; die zwölf neuen Planertests verwenden synthetische Daten.

Der kontrollierte erste reale Datensatz und der unabhängige Live-Nachweis werden in [Issue #37](https://github.com/masterxfix/MOSA-2/issues/37) dokumentiert. Historische Migrationsevidenzen sind keine zusätzliche Freigabevoraussetzung für andere vollständig qualifizierte neue Live-Facts. Keine Produktion und keine Freigabe für Parallel- oder Dauerbetrieb.

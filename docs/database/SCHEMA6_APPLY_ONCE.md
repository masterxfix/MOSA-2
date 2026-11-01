# Einmaliger Dogado-Apply 0005/0006

Expliziter Nutzerauftrag vom 01.11.2026: ausschließlich `h29077_mosa2_test`,
ein manueller Actions-Lauf, keine Wiederholung. Ausführungskennung
`MOSA2-SCHEMA6-20261101-01`. Der neue Workflow akzeptiert nur Laufnummer 1,
Versuch 1, main und den exakt autorisierten Commit. Ein Fehler verbraucht diesen
Weg; keine automatische Reparatur oder weitere Freigabe durch diesen Executor.

Wiederverwendet werden der gepinnte SSH-Tunnel, die feste PDO-Identität,
die unveränderten Migrationen sowie die qualifizierten Struktur-, Ledger-,
Bootstrap- und Provenance-Prüfer. Keine Serverdateien oder Runtime-Deployments.
Vor DDL werden schemaweite Rechte (globale Rechte ausschließlich USAGE),
17 Tabellen, Ledger 1–4, fünf Currents, 28 Observations und Ruhe-Signale geprüft.
Alle 17 Ausgangstabellen erhalten verlustfreie, begrenzte Zeilen-Fingerprints.
Die bestehenden kooperativen Migrations-/Current-/Scheduler-Locks bleiben bis
zum unabhängigen Postcheck gehalten; andere sichtbare Testschema-Sitzungen
und andere aktive Repository-Actions führen zum Stopp. Dies ist kein globales
Prozess- oder Croninventar und keine Sperre nichtkooperierender externer Zugänge.

0005: fünf Original-DDLs, drei gesperrte Bootstrap-Anweisungen und Ledger 5 in
einer Transaktion, Schema-5-Prüfung. 0006: fünf Original-CREATEs, vollständige
Strukturprüfung vor Ledger 6. Danach frische unabhängige READ-ONLY-Verbindung:
26 Tabellen, Ledger 1–6, alle ursprünglichen Zeilen unverändert (nur die geplanten
neuen Bootstrap-/Ledger-Zeilen aus dem Vergleich ausgeschlossen), fünf gültige
Provenance-Ketten, leere Fundamentals, Collector LOCKED/disabled/stop_latched.

Kein neues Backup-System und kein Dump. Der Nutzer hat den kleinen Testbestand
ausdrücklich als wiederherstellbar eingestuft; frühere weitergehende
Backup-Projektvoraussetzungen werden durch diesen konkreten Auftrag ersetzt.
Keine Providerabfragen, Seeds, Collector-/Scheduler-Aktivierung oder Produktion.

Vor jedem DDL und Commit wird ein fester Status ausgegeben. Fehler oder Timeout
nach Schreibbeginn bedeuten PARTIAL_OR_UNKNOWN, niemals behaupteten Rollback.
Der öffentliche Bericht enthält nur Prüfergebnisse und Hashes, keine Zeilen,
SQL-Fehler oder Zugangsdaten. Erfolg verlangt abschließendes SUCCESS aus der
echten unabhängigen Dogado-Verbindung; Offline-Tests allein sind Vorbereitung.

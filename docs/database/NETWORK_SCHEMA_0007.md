# M2 Netzwerk- und Smart-Home-Datenmodell – Migration 0007

Status: **Migration 0007 am 13.11.2026 erfolgreich auf der M2-Dogado-Testdatenbank angewendet.**
Isolierter MySQL-8.0.36-Schema-/Constraint-Test: [Lauf 43392585643](https://github.com/masterxfix/MOSA-2/actions/runs/43392585643).
Kontrollierter Dogado-Apply mit unabhängigem Read-only-Postcheck: [Lauf 43393673529](https://github.com/masterxfix/MOSA-2/actions/runs/43393673529).
16 neue Tabellen, insgesamt 42, Ledger 1–7, Modul `network=PREPARED` (keine Integrationen/JOBS aktiviert).
Migration 0007 SHA-256: `2ee91ab2b4b2c490e651990f5b5ce4f34ffd84a4afba5e6c0455740ba7944da7`.

## Istzustand, geprüft am 13.11.2026

Der gesicherte read-only Dogado-Prüflauf [43391862338](https://github.com/masterxfix/MOSA-2/actions/runs/43391862338)
bestätigte auf der **ausschließlich eigenen** Testdatenbank `h29077_mosa2_test`:
MySQL 8.0.26-16, 26 Tabellen, Ledger 0001–0006 mit korrekten bisherigen Checksums,
0 `m2_network_*`-Tabellen, 4 Core-Entities und 4 Finanz-Assets.
Die Ergebnisse beruhen auf einer eigenen read-only DB-Identität und nicht auf der Webanzeige.

## Ziel und Abgrenzung

M2 bleibt **eine Datenbank** und ein modularer Core. Finanzwerte, Assets, Market-Collector,
Sitzungen, NOVA/Codex, MOSA-Produktivsystem, private Router und Smart-Home-Geräte
werden durch Migration 0007 **nicht geändert**. Kein Scan, kein Datenimport, keine API,
kein Cron, kein Trigger, keine neue Berechtigung, kein Seed und kein Geräte-Schaltbefehl.

Die Migration enthält ausschließlich 16 `CREATE TABLE`-Anweisungen und erhält 0001–0006
byte-identisch. Im erfolgreich protokollierten One-time-Apply wurden der Schema-Ledgereintrag
7 und der noch nicht angebundene Modulzustand `network=PREPARED` gesetzt.

## Generisches Modell

| Tabelle | Verantwortung |
| --- | --- |
| `m2_network_sites` | Physische oder logische Standorte über `m2_entities` |
| `m2_network_domains` | Getrennte Routing-/Adressräume pro Standort, auch VPN/VRF |
| `m2_network_segments` | LAN, VLAN, WLAN/SSID, Mesh oder andere Segmenttypen |
| `m2_network_prefixes` | IPv4/IPv6-Präfixe mit Adressfamilie, Segment- und Domain-Bezug |
| `m2_network_devices` | Router, Switch, AP, Pi, Host, Smart-Home-Aktor, Sensor, Hub |
| `m2_network_device_identifiers` | Seriennummern, externe UIDs, OpenHAB-/UniFi-Kennungen etc. |
| `m2_network_interfaces` | Ethernet-Ports, WLAN, VPN, Bridge, Zigbee-, Thread-Interfaces |
| `m2_network_interface_segments` | Port- und WLAN-Zuordnungen: tagged/untagged/associated |
| `m2_network_links` | Paare von Interfaces für physische/logische Topologie |
| `m2_network_ip_current` | Genau eine aktuelle Zuordnung pro Domain/IPv4-/IPv6-Adresse |
| `m2_network_ip_observations` | Append-only IP-Vergabe/Freigabe/Beobachtung/Konflikt |
| `m2_network_services` | SSH, HTTP(S), MQTT, SNMP, openHAB, RTSP usw. pro Gerät |
| `m2_network_integrations` | Konnektoren, **standardmäßig deaktiviert**, ohne Credentials |
| `m2_network_metric_definitions` | Typisierte Messgrößen und Einheiten, kein Gerätespezialcode |
| `m2_network_metric_observations` | Append-only Werte mit Quelle, Zeit, Dedupe und Entity |
| `m2_network_metric_current` | Schneller letzter Zustand pro Entity und Kennzahl |

Bestehende gemeinsame `m2_entities`, `m2_relationships`, `m2_sources`,
`m2_files`, `m2_events`, `m2_jobs` und `m2_module_state` werden wiederverwendet.
Keine neue Universal-JSON-Tabelle. Die Fachattribute sind normiert; seltene
Roh-Belege können später durch `m2_files` außerhalb der Datenbank gespeichert werden.

## Datenqualität, Identität, Sicherheit

- **Core-Entitäten**: alle Site-/Segment-/Device-/Interface-/Service-Fachdatensätze
  haben eine dazugehörige Entity. Writer müssen den passenden `entity_type`
  vor dem Insert prüfen (FK allein kann diesen Typ nicht einschränken).
- **IPAM**: IPv4 als 4 Bytes, IPv6 als 16 Bytes in `VARBINARY(16)`; niemals IP
  als sortierbarer Text. Eindeutigkeit gilt pro Routing-Domain und IP-Familie.
  Unterschiedliche Domains können dieselbe private IP benutzen. Präfix-ID und
  Domain sind durch gemeinsamen FK konsistent.
- **CIDR-Validierung**: der künftige gemeinsame Writer muss Prüfbits maskieren,
  Host-Adresse und Prefix auf Zugehörigkeit prüfen, canonical CIDR normalisieren,
  Broadcast-/Netzwerk-/Gateway-Sonderfälle fachlich behandeln und Überlappungen
  ermitteln. DDL kontrolliert Familie/Länge, aber nicht Netzzugehörigkeit.
- **Identitäten**: MAC/EUI darf an Interfaces vorkommen; Seriennummern,
  OpenHAB-/UniFi-IDs etc. werden mit Namensraum gespeichert. Hashes, rotierende
  MACs und wiederverwendete IDs dürfen keine stillen Identitätsfusionen auslösen.
  Konflikte aktiver Kennungen prüft später der zentrale Writer.
- **Topologie**: jeder Link ist kanonisch nach aufsteigender Interface-ID
  gespeichert; ein doppeltes Linkpaar wird verhindert. Wiederholte Zustandsänderungen
  gehören in die Historie, nicht als neue parallele Links.
- **Historie**: Observations append-only; Current nur durch einen
  autorisierten, monotonen Writer aktualisieren. Source/FK/Origin-Kette und
  deduplizierende Ereignisschlüssel verhindern Phantomwerte.
- **Geheimnisse**: keine Passwörter, API-Schlüssel, MQTT-Credentials, PINs,
  FIDO-Daten, Wi-Fi-PSKs oder ungefilterten Router-Konfigurationsdumps in M2.
  Dienst-Endpunkte enthalten niemals eingebettete Anmeldedaten oder Token.
- **Netzgrenzen**: Dogado wird später ausschließlich über einen authentifizierten
  ausgehenden Transport von den autorisierten privaten Agents versorgt; keine
  öffentliche Datenbank, kein offener Port zum Heimnetz, keine Browser-Secrets.
- **Steuerung**: Geräteaktionen sind **nicht** Bestandteil von Schema 0007.
  Später nur mit explizitem Rechte-/Auditmodell, gesonderter Authentisierung
  und klaren Lese-/Schreibberechtigungen für NOVA/Automationen.
- **Keine Sonderlocken**: Hersteller-/Protokolladapter erzeugen dieselben
  normalisierten Geräte-, Interface-, Mess- und Quellendatensätze.

## Für die nächsten Implementierungsphasen vorbereitet

- FRITZ!Box- und UniFi-Inventar, DHCP/ARP/NDP, Verbindungsstatus, VLANs,
  Wi-Fi-Clients, IPv6-Präfixwechsel, VPN-Peers.
- Raspberry Pi, OpenClaw/NOVA, openHAB, Dienste, Verfügbarkeit,
  Firmware/OS-Versionen, Monitoring, Zertifikatslaufzeiten.
- Aqara, TP-Link, LG, Zigbee/Thread/Matter: Sensor-/Schalterzustände,
  Energieleistung, Batterie, RSSI und Gerätebeziehungen.
- Historische Port-/Adressbewegungen, Statuswechsel und Zeitreihen.

**Wichtig:** Dies sind Datenmodell-Fähigkeiten, keine bereits laufenden Collector
oder freigeschalteten Gerätefunktionen. Geräte und echte Topologie werden erst
durch verifizierte Messungen/Importe in die private M2-Datenbank eingetragen.

## Performance-Vertrag

Kleine `current`-Tabellen werden nach Entity/Metric und Domain/IP gelesen.
History ausschließlich über `(subject,metric,time)` bzw. `(domain,IP,time)`,
begrenzt durch Zeitraum/LIMIT. Kein History-Scan beim Seitenaufbau.
Normale Seiten unter 1 s, p95 unter 1,5 s, harte Grenze 2,0 s einschließlich DB.

Wichtige Indexpfade: `uq_net_ip_domain_address`,
`ix_net_device_site_kind`, `ix_net_metric_obs_subject`,
`PRIMARY(subject_entity_id,metric_key)`.
 
## Abgeschlossene Abnahme und dokumentierter Apply-Vertrag

1. Dogado **read-only**: exakter DB-Name, MySQL-Version, Ledger 1..6,
   Tabelleliste, keine unbekannten `m2_network_*`-Reste, Tabellen-/Asset-Bestand.
2. Isoliertes MySQL 8: unveränderte SQL-Datei, 16 Tabellen, FKs, CHECKs,
   IPv4-/Domain-Konflikte, Observation→Current-Provenienz, EXPLAIN.
3. Einmaliger additiver Apply auf **`h29077_mosa2_test`**:
   Vorbedingungen erneut prüfen; aktive M2-Scheduler-Sperre beachten;
   jede DDL einzeln bestätigen, bei Teilfehler **stoppen, nicht blind erneut ausführen**.
   MySQL-DDL commitet implizit. Keine ALTER/DROP vorhandener Tabellen.
4. Ledger 7 nur nach vollständiger Strukturprüfung, SHA-256 von 0007 und
   `network=PREPARED` in einer abschließenden kleinen Transaktion.
5. Unabhängiger **read-only** Postcheck: Ledger 1–7 korrekt, 42 Tabellen,
   genau 16 leere `m2_network_*`-Tabellen, alter Bestand unverändert,
   keine neuen aktivierten Jobs. Abnahmeevidenz in GitHub-Run-Logs.
6. Keine Seiten verändert: kein UI-Deployment. Browser- und Netzwerkfunktionstests
   erfolgen erst nach expliziter Geräteintegration; keine voreilige Vollabnahme.

## Offene Fachentscheidungen

Spätere zentrale Writer müssen aktive Segmentmitgliedschaften zeitlich überlappungsfrei
halten, dynamische Adresseinträge gegen tatsächliche DHCP-Lease-/Prefix-Quelle prüfen,
vor Überschreiben alter Current-Werte den Quellenzeitpunkt vergleichen und
Discovery-Dubletten auflösen. Das ist bewusst kein Platzhalter-Sondercollector.

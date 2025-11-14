# Fritz!Box VPN für Home Assistant

[🇩🇪 Deutsch](README_DE.md) | [🇬🇧 English](README.md)

Diese Integration ermöglicht die Steuerung von WireGuard VPN-Verbindungen auf einer AVM Fritz!Box direkt über Home Assistant.

## Features

- Automatische Erkennung aller WireGuard VPN-Verbindungen
- Ein-/Ausschalten von VPN-Verbindungen über Switch Entities
- Einfache Konfiguration über die Home Assistant UI
- Unterstützung mehrerer VPN-Verbindungen
- Automatische Konfiguration aus vorhandenen Fritz!Box Tools
- Automatische FritzBox-Erkennung via SSDP/UPnP
- Konfigurierbares Update-Intervall (5-300 Sekunden)

## Installation

### Über HACS (empfohlen)

1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu Integrations
3. Klicken Sie auf Custom repositories
4. Fügen Sie dieses Repository hinzu:
   - Repository: `https://github.com/rosch100/fritzbox-vpn`
   - Category: Integration
5. Suchen Sie nach Fritz!Box VPN und installieren Sie es
6. Starten Sie Home Assistant neu

### Manuelle Installation

1. Kopieren Sie den `custom_components/fritzbox_vpn` Ordner in Ihr Home Assistant `custom_components` Verzeichnis
2. Starten Sie Home Assistant neu

## Konfiguration

### Automatische Erkennung (Empfohlen)

1. Gehen Sie zu Einstellungen > Geräte & Dienste
2. Klicken Sie auf Integration hinzufügen
3. Falls eine FritzBox im Netzwerk gefunden wird, wird sie automatisch erkannt
4. Die Integration versucht, Zugangsdaten aus Fritz!Box Tools zu verwenden, falls verfügbar
5. Geben Sie bei Bedarf Ihre Zugangsdaten ein und klicken Sie auf Absenden

### Manuelle Konfiguration

1. Gehen Sie zu Einstellungen > Geräte & Dienste
2. Klicken Sie auf Integration hinzufügen
3. Geben Sie die folgenden Informationen ein:
   - FritzBox IP-Adresse: z.B. `192.168.178.1`
   - Benutzername: Ihr FritzBox Benutzername
   - Passwort: Ihr FritzBox Passwort
4. Klicken Sie auf Absenden

Die Integration erkennt automatisch alle WireGuard VPN-Verbindungen auf Ihrer FritzBox und erstellt für jede eine Switch Entity.

### Update-Intervall konfigurieren

Sie können das Update-Intervall (wie oft die Integration den VPN-Status prüft) in den Integrations-Optionen konfigurieren:

1. Gehen Sie zu Einstellungen > Geräte & Dienste
2. Finden Sie Ihre Fritz!Box VPN Integration
3. Klicken Sie auf Konfigurieren
4. Passen Sie das Update-Intervall an (5-300 Sekunden, Standard: 30 Sekunden)
5. Klicken Sie auf Absenden

Das Update-Intervall bestimmt, wie häufig die Integration die FritzBox nach VPN-Status-Updates abfragt. Niedrigere Werte bieten häufigere Updates, können aber den Netzwerkverkehr und die FritzBox-Last erhöhen. Höhere Werte reduzieren den Netzwerkverkehr, können aber Status-Updates verzögern.

### Sicherheit

Alle Zugangsdaten (Benutzername und Passwort) werden sicher von Home Assistant gespeichert:
- Zugangsdaten werden verschlüsselt im sicheren Speicher von Home Assistant gespeichert
- Sie werden niemals in Logs oder Konfigurationsdateien exponiert
- Der Zugriff ist auf die Integration selbst beschränkt

## Verwendung

Nach der Konfiguration finden Sie für jede VPN-Verbindung folgende Entitäten:

### Switch
- Zweck: VPN-Verbindungen ein- und ausschalten (Aktiviert/Deaktiviert)
- Entitäts-ID: `switch.fritzbox_vpn_<connection_uid>_switch`
- Name: Verwendet den VPN-Verbindungsnamen vom Gerät
- Status: Zeigt an, ob die VPN aktiviert (ein) oder deaktiviert (aus) ist

### Binary Sensor

1. Connected Binary Sensor
   - Zweck: Zeigt an, ob die VPN-Verbindung aktiv verbunden ist
   - Entitäts-ID: `binary_sensor.fritzbox_vpn_<connection_uid>_connected`
   - Wert: `on` wenn verbunden, `off` wenn nicht verbunden

### Sensor

1. Status Sensor
   - Zweck: Zeigt den kombinierten VPN-Status als Text an
   - Entitäts-ID: `sensor.fritzbox_vpn_<connection_uid>_status`
   - Werte: 
     - `connected` - VPN ist aktiviert und verbunden
     - `enabled` - VPN ist aktiviert, aber nicht verbunden
     - `disabled` - VPN ist deaktiviert
     - `unknown` - Status konnte nicht ermittelt werden

2. UID Sensor (standardmäßig deaktiviert)
   - Zweck: Zeigt die eindeutige Verbindungs-ID (Connection UID)
   - Entitäts-ID: `sensor.fritzbox_vpn_<connection_uid>_uid`
   - Wert: Die Connection UID als Zeichenkette (gleich wie `<connection_uid>`)

3. VPN UID Sensor (standardmäßig deaktiviert)
   - Zweck: Zeigt die interne VPN UID der FritzBox
   - Entitäts-ID: `sensor.fritzbox_vpn_<connection_uid>_vpn_uid`
   - Wert: Die interne VPN UID als Zeichenkette (aus `conn.get('uid')`)

Sie können diese Entitäten verwenden, um:
- VPN-Verbindungen ein- und auszuschalten (switch)
- Verbindungsstatus zu überwachen (connected binary sensor)
- Detaillierte Statusinformationen anzuzeigen (status sensor)
- Technische Identifikatoren abzurufen (UID sensors, disabled by default)
- Automatisierungen basierend auf dem Verbindungsstatus zu erstellen

### Status-Attribute

Jede VPN-Switch-Entity bietet folgende Attribute:

- name: Der Name der VPN-Verbindung (wie auf der FritzBox konfiguriert)
- uid: Die eindeutige Verbindungs-ID (Connection UID)
- vpn_uid: Die interne VPN-UID der FritzBox
- active: `true` wenn die VPN-Verbindung aktiviert ist, `false` wenn deaktiviert
- connected: `true` wenn die VPN-Verbindung aktiv verbunden ist, `false` wenn nicht verbunden
- status: Textuelle Statusbeschreibung:
  - `"connected"` - VPN ist aktiviert und verbunden
  - `"active_not_connected"` - VPN ist aktiviert, aber nicht verbunden
  - `"inactive"` - VPN ist deaktiviert
  - `"unknown"` - Status konnte nicht ermittelt werden

## Voraussetzungen

- AVM FritzBox mit WireGuard VPN-Unterstützung
- FritzBox Firmware mit aktiviertem WireGuard
- Benutzer mit entsprechenden Berechtigungen auf der FritzBox

## Unterstützung

Bei Problemen oder Fragen:
- Erstellen Sie ein Issue auf GitHub
- Überprüfen Sie die Home Assistant Logs



## Lizenz

Dieses Projekt ist unter der [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) lizenziert, der gleichen Lizenz wie [Home Assistant](https://github.com/home-assistant/core/blob/dev/LICENSE.md), um Kompatibilität und Konsistenz mit dem Home Assistant Ökosystem sicherzustellen.

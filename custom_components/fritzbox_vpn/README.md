# FritzBox VPN Integration für Home Assistant

Diese Integration ermöglicht die Steuerung von WireGuard VPN-Verbindungen auf einer AVM FritzBox direkt über Home Assistant.

**Hinweis**: Das Logo wird automatisch aus dem [Home Assistant Brands-Repository](https://github.com/home-assistant/brands) geladen, sobald es dort registriert ist. Das lokale Logo (`logo.png`) dient als Fallback.

## Features

- ✅ Automatische Erkennung aller WireGuard VPN-Verbindungen
- ✅ Ein-/Ausschalten von VPN-Verbindungen über Switch Entities
- ✅ Automatische Status-Updates (konfigurierbares Intervall, Standard: 30 Sekunden)
- ✅ Einfache Konfiguration über die Home Assistant UI
- ✅ Unterstützung mehrerer VPN-Verbindungen
- ✅ **Konfigurierbares Update-Intervall** (5-300 Sekunden)
- ✅ **Automatische FritzBox-Erkennung via SSDP/UPnP**
- ✅ **Automatische Konfiguration aus vorhandener FritzBox-Integration**
- ✅ **Sichere Speicherung der Zugangsdaten** (verschlüsselt durch Home Assistant)

## Installation

### Über HACS (empfohlen)

1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu **Integrations**
3. Klicken Sie auf **Custom repositories**
4. Fügen Sie dieses Repository hinzu:
   - Repository: `https://github.com/rosch100/fritzbox-vpn`
   - Category: **Integration**
5. Suchen Sie nach **FritzBox VPN** und installieren Sie es
6. Starten Sie Home Assistant neu

### Manuelle Installation

1. Kopieren Sie den `custom_components/fritzbox_vpn` Ordner in Ihr Home Assistant `custom_components` Verzeichnis
2. Starten Sie Home Assistant neu

## Konfiguration

### Automatische Erkennung (Empfohlen)

1. Gehen Sie zu **Einstellungen** > **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen**
3. Suchen Sie nach **FritzBox VPN**
4. Falls eine FritzBox im Netzwerk gefunden wird, wird sie automatisch erkannt
5. Die Integration versucht, Zugangsdaten aus einer vorhandenen FritzBox-Integration zu verwenden, falls verfügbar
6. Geben Sie bei Bedarf Ihre Zugangsdaten ein und klicken Sie auf **Absenden**

### Manuelle Konfiguration

1. Gehen Sie zu **Einstellungen** > **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen**
3. Suchen Sie nach **FritzBox VPN**
4. Geben Sie die folgenden Informationen ein:
   - **FritzBox IP-Adresse**: z.B. `192.168.178.1`
   - **Benutzername**: Ihr FritzBox Benutzername
   - **Passwort**: Ihr FritzBox Passwort
5. Klicken Sie auf **Absenden**

**Hinweis**: Falls bereits die offizielle FritzBox-Integration konfiguriert ist, werden IP-Adresse und Benutzername automatisch vorausgefüllt. Sie müssen nur das Passwort eingeben (oder leer lassen, falls die gleichen Zugangsdaten verwendet werden).

Die Integration erkennt automatisch alle WireGuard VPN-Verbindungen auf Ihrer FritzBox und erstellt für jede eine Switch Entity.

### Update-Intervall konfigurieren

Sie können das Update-Intervall (wie oft die Integration den VPN-Status prüft) in den Integrations-Optionen konfigurieren:

1. Gehen Sie zu **Einstellungen** > **Geräte & Dienste**
2. Finden Sie Ihre **FritzBox VPN** Integration
3. Klicken Sie auf **Konfigurieren**
4. Passen Sie das **Update-Intervall** an (5-300 Sekunden, Standard: 30 Sekunden)
5. Klicken Sie auf **Absenden**

Das Update-Intervall bestimmt, wie häufig die Integration die FritzBox nach VPN-Status-Updates abfragt. Niedrigere Werte bieten häufigere Updates, können aber den Netzwerkverkehr und die FritzBox-Last erhöhen. Höhere Werte reduzieren den Netzwerkverkehr, können aber Status-Updates verzögern.

### Sicherheit

Alle Zugangsdaten (Benutzername und Passwort) werden sicher von Home Assistant gespeichert:
- Zugangsdaten werden verschlüsselt im sicheren Speicher von Home Assistant gespeichert
- Sie werden niemals in Logs oder Konfigurationsdateien exponiert
- Der Zugriff ist auf die Integration selbst beschränkt

## Verwendung

Nach der Konfiguration finden Sie für jede VPN-Verbindung folgende Entitäten:

### Switch-Entität
- **Entitäts-ID**: `switch.fritzbox_vpn_<connection_uid>_switch`
- **Name**: Verwendet den VPN-Verbindungsnamen vom Gerät (via `has_entity_name`)
- **Icon**: `mdi:vpn`
- **Zweck**: VPN-Verbindungen ein- und ausschalten (Aktiviert/Deaktiviert)
- **Status**: Zeigt an, ob die VPN aktiviert (ein) oder deaktiviert (aus) ist

### Binary Sensor-Entität

1. **Connected Binary Sensor** (standardmäßig aktiviert)
   - **Entitäts-ID**: `binary_sensor.fritzbox_vpn_<connection_uid>_connected`
   - **Name**: "Connected" (via `has_entity_name`)
   - **Icon**: `mdi:connection`
   - **Zweck**: Zeigt an, ob die VPN-Verbindung aktiv verbunden ist
   - **Wert**: `on` wenn verbunden, `off` wenn nicht verbunden
   - **Device Class**: `connectivity`

### Sensor-Entitäten

1. **Status Sensor** (standardmäßig aktiviert)
   - **Entitäts-ID**: `sensor.fritzbox_vpn_<connection_uid>_status`
   - **Name**: "Status" (via `has_entity_name`)
   - **Icon**: `mdi:information`
   - **Zweck**: Zeigt den kombinierten VPN-Status als Text an
   - **Werte**: 
     - `connected` - VPN ist aktiviert und verbunden
     - `enabled` - VPN ist aktiviert, aber nicht verbunden
     - `disabled` - VPN ist deaktiviert
     - `unknown` - Status konnte nicht ermittelt werden

2. **UID Sensor** (standardmäßig deaktiviert)
   - **Entitäts-ID**: `sensor.fritzbox_vpn_<connection_uid>_uid`
   - **Name**: "UID" (via `has_entity_name`)
   - **Icon**: `mdi:identifier`
   - **Zweck**: Zeigt die eindeutige Verbindungs-ID (Connection UID)
   - **Wert**: Die Connection UID als Zeichenkette (gleich wie `<connection_uid>`)

3. **VPN UID Sensor** (standardmäßig deaktiviert)
   - **Entitäts-ID**: `sensor.fritzbox_vpn_<connection_uid>_vpn_uid`
   - **Name**: "VPN UID" (via `has_entity_name`)
   - **Icon**: `mdi:identifier`
   - **Zweck**: Zeigt die interne VPN UID der FritzBox
   - **Wert**: Die interne VPN UID als Zeichenkette (aus `conn.get('uid')`)

Die Entitäts-IDs basieren auf der eindeutigen ID (UID) der VPN-Verbindung. Die Anzeigenamen zeigen den tatsächlichen Namen der VPN-Verbindung an.

Sie können diese Entitäten verwenden, um:
- VPN-Verbindungen ein- und auszuschalten (Switch)
- Verbindungsstatus zu überwachen (Connected Binary Sensor)
- Detaillierte Statusinformationen anzuzeigen (Status Sensor)
- Technische Identifikatoren abzurufen (UID Sensoren, standardmäßig deaktiviert)
- Automatisierungen basierend auf dem Verbindungsstatus zu erstellen

### Status-Attribute

Jede VPN-Switch-Entity bietet folgende Attribute:

- **name**: Der Name der VPN-Verbindung (wie auf der FritzBox konfiguriert)
- **uid**: Die eindeutige Verbindungs-ID (Connection UID)
- **vpn_uid**: Die interne VPN-UID der FritzBox
- **active**: `true` wenn die VPN-Verbindung aktiviert ist, `false` wenn deaktiviert
- **connected**: `true` wenn die VPN-Verbindung aktiv verbunden ist, `false` wenn nicht verbunden
- **status**: Textuelle Statusbeschreibung:
  - `"connected"` - VPN ist aktiviert und verbunden
  - `"active_not_connected"` - VPN ist aktiviert, aber nicht verbunden
  - `"inactive"` - VPN ist deaktiviert
  - `"unknown"` - Status konnte nicht ermittelt werden

## Automatisierungen

Sie können die VPN-Switches in Automatisierungen verwenden, um VPN-Verbindungen basierend auf verschiedenen Bedingungen automatisch ein- und auszuschalten.

## Voraussetzungen

- AVM FritzBox mit WireGuard VPN-Unterstützung
- FritzBox Firmware mit aktiviertem WireGuard
- Benutzer mit entsprechenden Berechtigungen auf der FritzBox

## Unterstützung

Bei Problemen oder Fragen:
- Erstellen Sie ein Issue auf GitHub
- Überprüfen Sie die Home Assistant Logs

## Logo

Das Logo wird automatisch aus dem [Home Assistant Brands-Repository](https://github.com/home-assistant/brands) geladen, sobald es dort registriert ist. Das lokale Logo dient als Fallback.

## Lizenz

MIT License

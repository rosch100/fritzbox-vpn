# FritzBox VPN Integration für Home Assistant

Diese Integration ermöglicht die Steuerung von WireGuard VPN-Verbindungen auf einer AVM FritzBox direkt über Home Assistant.

## Features

- ✅ Automatische Erkennung aller WireGuard VPN-Verbindungen
- ✅ Ein-/Ausschalten von VPN-Verbindungen über Switch Entities
- ✅ Automatische Status-Updates alle 30 Sekunden
- ✅ Einfache Konfiguration über die Home Assistant UI
- ✅ Unterstützung mehrerer VPN-Verbindungen

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

1. Gehen Sie zu **Einstellungen** > **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen**
3. Suchen Sie nach **FritzBox VPN**
4. Geben Sie die folgenden Informationen ein:
   - **FritzBox IP-Adresse**: z.B. `192.168.178.1`
   - **Benutzername**: Ihr FritzBox Benutzername
   - **Passwort**: Ihr FritzBox Passwort
5. Klicken Sie auf **Absenden**

Die Integration erkennt automatisch alle WireGuard VPN-Verbindungen auf Ihrer FritzBox und erstellt für jede eine Switch Entity.

## Verwendung

Nach der Konfiguration finden Sie für jede VPN-Verbindung eine Switch Entity unter:
- **Entitäten**: `switch.fritzbox_vpn_<connection_name>`

Sie können diese Switches verwenden, um:
- VPN-Verbindungen ein- und auszuschalten
- Den aktuellen Status zu überwachen
- Automatisierungen zu erstellen

## Automatisierungen

Beispiel-Automatisierung:

```yaml
automation:
  - alias: "VPN bei App-Start aktivieren"
    trigger:
      - platform: state
        entity_id: media_player.apple_tv
        to: "playing"
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.attributes.app_name in ['Netflix', 'Disney+'] }}"
    action:
      - service: switch.turn_on
        entity_id: switch.fritzbox_vpn_mathias_vermont
```

## Voraussetzungen

- AVM FritzBox mit WireGuard VPN-Unterstützung
- FritzBox Firmware mit aktiviertem WireGuard
- Benutzer mit entsprechenden Berechtigungen auf der FritzBox

## Unterstützung

Bei Problemen oder Fragen:
- Erstellen Sie ein Issue auf GitHub
- Überprüfen Sie die Home Assistant Logs

## Lizenz

MIT License


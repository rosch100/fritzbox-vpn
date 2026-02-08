# Fritz!Box VPN für Home Assistant

[🇩🇪 Deutsch](README.de.md) | [🇬🇧 English](README.md)

Diese Integration ermöglicht die Steuerung von WireGuard VPN-Verbindungen auf einer AVM Fritz!Box direkt über Home Assistant.

## Features

- Automatische Erkennung aller WireGuard VPN-Verbindungen
- Ein-/Ausschalten von VPN-Verbindungen über Switch Entities
- Einfache Konfiguration über die Home Assistant UI
- Unterstützung mehrerer VPN-Verbindungen
- Automatische Konfiguration aus vorhandenen Fritz!Box Tools
- Automatische FritzBox-Erkennung via SSDP/UPnP
- Konfigurierbares Update-Intervall (5 Sekunden bis 1 Stunde; Standard 30 s)
- Session-Caching: nur ein Login pro Integrations-Load (kein Login bei jedem Poll), dadurch bleiben Router-Zugangs-Benachrichtigungen per E-Mail gering

## Installation

1. Öffnen Sie HACS in Home Assistant
2. Gehen Sie zu Integrations
3. Suchen Sie nach "Fritz!Box VPN" und installieren Sie es
4. Starten Sie Home Assistant neu

### Beta-Version zum Testen

Um eine Beta-Version zu installieren (z. B. zum Testen von Fixes vor der nächsten stabilen Version):

1. In HACS die Karte der Integration **Fritz!Box VPN** öffnen.
2. Auf **⋮** (drei Punkte) oben rechts klicken und **Erneut herunterladen** wählen.
3. **Beta-Versionen anzeigen** aktivieren und kurz warten, bis die Liste aktualisiert ist.
4. Gewünschte Beta-Version (z. B. `0.9.0b1`) auswählen und bestätigen.
5. Home Assistant neu starten.

Beta-Releases erscheinen als GitHub-Vorabversionen (Tags wie `v0.9.0b1`).

## Konfiguration

### Automatische Erkennung (Empfohlen)

1. Gehen Sie zu Einstellungen > Geräte & Dienste
2. Klicken Sie auf Integration hinzufügen
3. Falls eine FritzBox im Netzwerk gefunden wird, wird sie automatisch erkannt
4. Die Integration versucht, Zugangsdaten aus Fritz!Box Tools zu verwenden, falls verfügbar
5. Geben Sie bei Bedarf Ihre Zugangsdaten ein und klicken Sie auf Absenden

**Hinweis:** Für die automatische Erkennung sollte UPnP in Ihrer FritzBox aktiviert sein (empfohlen, aber nicht erforderlich). Wenn UPnP deaktiviert ist, können Sie die Integration weiterhin manuell konfigurieren. TR-064 ist immer für API-Zugriffe erforderlich (siehe Abschnitt Voraussetzungen).

### Manuelle Konfiguration

1. Gehen Sie zu Einstellungen > Geräte & Dienste
2. Klicken Sie auf Integration hinzufügen
3. Geben Sie die folgenden Informationen ein:
   - FritzBox IP-Adresse: z.B. `192.168.178.1`
   - Benutzername: Ihr FritzBox Benutzername
   - Passwort: Ihr FritzBox Passwort
4. Klicken Sie auf Absenden

**Wichtig:** Stellen Sie sicher, dass TR-064 in Ihrer FritzBox aktiviert ist (siehe Abschnitt Voraussetzungen oben). Falls Sie Authentifizierungsfehler erhalten, überprüfen Sie, ob TR-064 aktiviert ist.

Die Integration erkennt automatisch alle WireGuard VPN-Verbindungen auf Ihrer FritzBox und erstellt für jede eine Switch Entity.

### Update-Intervall konfigurieren

Sie können das Update-Intervall (wie oft die Integration den VPN-Status prüft) in den Integrations-Optionen konfigurieren:

1. Gehen Sie zu Einstellungen > Geräte & Dienste
2. Finden Sie Ihre Fritz!Box VPN Integration
3. Klicken Sie auf Konfigurieren
4. Passen Sie das Update-Intervall an (5–3600 Sekunden, Standard: 30 Sekunden; maximal 1 Stunde).
5. Klicken Sie auf Absenden

Das Update-Intervall legt fest, wie oft die Integration die FritzBox abfragt. Niedrigere Werte = häufigere Updates, höhere Werte (bis 3600 s = 1 h) reduzieren Reconnects und Last.

**Reconnects und Last reduzieren:** Die Integration nutzt Session-Caching (ein Login pro Ladevorgang) und bei Abfragefehlern einen 5‑Minuten-Backoff vor dem nächsten Versuch. Für noch weniger Reconnects und FritzBox-Last das Update-Intervall auf 300 Sekunden (5 Min) oder höher setzen; Maximum ist 3600 (1 h).

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
  - `"enabled"` - VPN ist aktiviert, aber nicht verbunden
  - `"disabled"` - VPN ist deaktiviert
  - `"unknown"` - Status konnte nicht ermittelt werden

## Voraussetzungen

- AVM FritzBox mit WireGuard VPN-Unterstützung
- FritzBox Firmware mit aktiviertem WireGuard
- Benutzer mit entsprechenden Berechtigungen auf der FritzBox
- **TR-064 muss aktiviert sein** in den FritzBox-Einstellungen (erforderlich für API-Zugriff)
- **UPnP empfohlen** für automatische Erkennung via SSDP (optional, aber empfohlen)

### FritzBox-Einstellungen

Vor der Konfiguration der Integration müssen Sie die erforderlichen Einstellungen in Ihrer FritzBox aktivieren:

1. Öffnen Sie die FritzBox-Benutzeroberfläche
2. Gehen Sie zu **Heimnetz** > **Netzwerk** > **Netzwerkeinstellungen**
3. Klicken Sie auf **Zugriffseinstellungen im Heimnetz**
4. Aktivieren Sie **TR-064 (Zugriff für Apps erlauben)** - **Erforderlich** für API-Zugriff
5. Aktivieren Sie **UPnP (Statusinformationen über UPnP übertragen)** - **Empfohlen** für automatische Erkennung
6. Klicken Sie auf **Übernehmen**

**Hinweis:** 
- **TR-064 ist erforderlich** - Die Integration funktioniert nicht ohne diese Einstellung
- **UPnP ist empfohlen** - Ermöglicht die automatische Erkennung Ihrer FritzBox via SSDP. Wenn UPnP deaktiviert ist, können Sie die Integration weiterhin manuell konfigurieren, indem Sie die IP-Adresse eingeben

## Unterstützung

Bei Problemen oder Fragen:
- Erstellen Sie ein Issue auf GitHub
- Überprüfen Sie die Home Assistant Logs

## Buy me a coffee

Gefällt dir diese Integration? Dann lade mich gerne auf einen Kaffee ein! ☕ Deine Unterstützung hilft mir dabei, weiter an coolen Features zu arbeiten.

[![Buy Me A Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=rosch100&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://buymeacoffee.com/rosch100)

## Lizenz

Dieses Projekt ist unter der [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) lizenziert, der gleichen Lizenz wie [Home Assistant](https://github.com/home-assistant/core/blob/dev/LICENSE.md), um Kompatibilität und Konsistenz mit dem Home Assistant Ökosystem sicherzustellen.

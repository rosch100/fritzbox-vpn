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

Es wird **Home Assistant 2026.1.0** oder neuer benötigt.

1. Öffne HACS in Home Assistant
2. Geh zu Integrations
3. Such nach "Fritz!Box VPN" und installiere es
4. Starte Home Assistant neu

### Beta-Version zum Testen

Um eine Beta-Version zu installieren (z. B. zum Testen von Fixes vor der nächsten stabilen Version):

1. In HACS die Karte der Integration **Fritz!Box VPN** öffnen.
2. Auf **⋮** (drei Punkte) oben rechts klicken und **Erneut herunterladen** wählen.
3. **Beta-Versionen anzeigen** aktivieren und kurz warten, bis die Liste aktualisiert ist.
4. Gewünschte Beta-Version (z. B. `0.10.0b1`) auswählen und bestätigen.
5. Home Assistant neu starten.

Beta-Releases erscheinen als GitHub-Vorabversionen (Tags wie `v0.10.0b1`).

## Konfiguration

**Wichtig:** TR-064 ist immer für API-Zugriffe erforderlich (siehe Abschnitt Voraussetzungen). Für die automatische Erkennung sollte UPnP in deiner FritzBox aktiviert sein (empfohlen, aber nicht erforderlich). Wenn UPnP deaktiviert ist, kannst du die Integration weiterhin manuell konfigurieren.

### Automatische Erkennung (Empfohlen)

1. Geh zu Einstellungen > Geräte & Dienste
2. Klicke auf Integration hinzufügen
3. Falls eine FritzBox im Netzwerk gefunden wird, wird sie automatisch erkannt
4. Die Integration versucht, Zugangsdaten aus Fritz!Box Tools zu verwenden, falls verfügbar
5. Gib bei Bedarf deine Zugangsdaten ein und klicke auf Absenden

### Manuelle Konfiguration

1. Geh zu Einstellungen > Geräte & Dienste
2. Klicke auf Integration hinzufügen
3. Gib die folgenden Informationen ein:
   - FritzBox IP-Adresse: z.B. `192.168.178.1`
   - Benutzername: dein FritzBox Benutzername
   - Passwort: dein FritzBox Passwort
4. Klicke auf Absenden

Die Integration erkennt automatisch alle WireGuard VPN-Verbindungen auf deiner FritzBox und erstellt für jede eine Switch Entity.

### Update-Intervall konfigurieren

Du kannst das Update-Intervall (wie oft die Integration den VPN-Status prüft) in den Integrations-Optionen konfigurieren:

1. Geh zu Einstellungen > Geräte & Dienste
2. Finde deine Fritz!Box VPN Integration
3. Klicke auf Konfigurieren
4. Passe das Update-Intervall an (5–3600 Sekunden, Standard: 30 Sekunden; maximal 1 Stunde).
5. Klicke auf Absenden

Das Update-Intervall legt fest, wie oft die Integration die FritzBox abfragt. Niedrigere Werte = häufigere Updates, höhere Werte (bis 3600 s = 1 h) reduzieren Reconnects und Last.

**Reconnects und Last reduzieren:** Die Integration nutzt Session-Caching (ein Login pro Ladevorgang) und bei Abfragefehlern einen 5‑Minuten-Backoff vor dem nächsten Versuch. Für noch weniger Reconnects und FritzBox-Last das Update-Intervall auf 300 Sekunden (5 Min) oder höher setzen; Maximum ist 3600 (1 h).

### Optionen und Dienste

Unter **Einstellungen > Geräte & Dienste** die Fritz!Box-VPN-Integration auswählen und **Konfigurieren** öffnen:

- **Unavailable-Entitäten entfernen**: Wird nur angezeigt, wenn Entitäten zu VPN-Verbindungen gehören, die auf der Fritz!Box nicht mehr existieren. Entfernt diese Entitäten und Geräte und lädt die Integration neu.
- **Entitäts-ID-Suffixe reparieren**: Falls Entitäten ein Suffix `_2`, `_3`, … bekommen haben (z. B. nach Deaktivieren/Reaktivieren), werden die ursprünglichen Entitäts-IDs wiederhergestellt, damit Automatisierungen weiter funktionieren.

Die gleichen Aktionen stehen als **Dienste** zur Verfügung (Entwicklerwerkzeuge > Dienste): `fritzbox_vpn.remove_unavailable_entities` und `fritzbox_vpn.repair_entity_id_suffixes`. Optional kann bei mehreren Fritz!Box-VPN-Integrationen `config_entry_id` übergeben werden.

### Sicherheit

Alle Zugangsdaten (Benutzername und Passwort) werden sicher von Home Assistant gespeichert:
- Zugangsdaten werden verschlüsselt im sicheren Speicher von Home Assistant gespeichert
- Du wirst niemals in Logs oder Konfigurationsdateien exponiert
- Der Zugriff ist auf die Integration selbst beschränkt

## Verwendung

Nach der Konfiguration findest du für jede VPN-Verbindung folgende Entitäten:

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

Du kannst diese Entitäten verwenden, um:
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

Vor der Konfiguration der Integration musst du die erforderlichen Einstellungen in deiner FritzBox aktivieren:

1. Öffne die FritzBox-Benutzeroberfläche
2. Geh zu **Heimnetz** > **Netzwerk** > **Netzwerkeinstellungen**
3. Klicke auf **Zugriffseinstellungen im Heimnetz**
4. Aktiviere **TR-064 (Zugriff für Apps erlauben)** - **Erforderlich** für API-Zugriff
5. Aktiviere **UPnP (Statusinformationen über UPnP übertragen)** - **Empfohlen** für automatische Erkennung
6. Klicke auf **Übernehmen**

## Unterstützung

Bei Problemen oder Fragen:
- Erstelle ein [Issue auf GitHub](https://github.com/rosch100/fritzbox-vpn/issues)
- Überprüfe die Home Assistant Logs

### Debug-Logging

1. Installiere die Beta-Version.
2. Öffne die Integrationsseite: **Einstellungen → Geräte & Dienste → Fritz!Box VPN**.
3. Öffne das **Optionsmenü (⋮)** (oben rechts) und wähle **Enable debug logging**.
4. Klicke **Neu laden** (Integration reload), damit das nächste Update den neuen Log-Level nutzt.
5. Reproduziere das Problem (oder warte auf das nächste Update).
6. Deaktiviere Debug-Logging wieder. Das Logfile wird automatisch heruntergeladen. Hänge das Log dem GitHub-Issue an.
7. (Optional) Öffne **Einstellungen → System → Logs** und verwende **Download**, um `home-assistant.log` zu erhalten.

## Buy me a coffee

Gefällt dir diese Integration? Dann lade mich gerne auf einen Kaffee ein! ☕ Deine Unterstützung hilft mir dabei, weiter an coolen Features zu arbeiten.

[![Buy Me A Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=rosch100&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://buymeacoffee.com/rosch100)

## Lizenz

Dieses Projekt ist unter der [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) lizenziert, der gleichen Lizenz wie [Home Assistant](https://github.com/home-assistant/core/blob/dev/LICENSE.md), um Kompatibilität und Konsistenz mit dem Home Assistant Ökosystem sicherzustellen.

# Installation der FritzBox VPN Custom Component

## Voraussetzungen

- Home Assistant (Version 2023.1.0 oder höher)
- HACS (Home Assistant Community Store) installiert
- AVM FritzBox mit WireGuard VPN-Unterstützung
- FritzBox Benutzer mit entsprechenden Berechtigungen

## Installation über HACS

### Schritt 1: HACS vorbereiten

1. Öffnen Sie Home Assistant
2. Gehen Sie zu **HACS** im Seitenmenü
3. Falls HACS noch nicht installiert ist, folgen Sie der [HACS Installation](https://hacs.xyz/docs/installation/manual)

### Schritt 2: Custom Repository hinzufügen

1. In HACS, gehen Sie zu **Integrations**
2. Klicken Sie auf die drei Punkte (⋮) oben rechts
3. Wählen Sie **Custom repositories**
4. Fügen Sie folgendes hinzu:
   - **Repository**: `https://github.com/yourusername/fritzbox-vpn`
   - **Category**: Wählen Sie **Integration**
5. Klicken Sie auf **Add**

### Schritt 3: Integration installieren

1. Suchen Sie nach **FritzBox VPN** in HACS
2. Klicken Sie auf die Integration
3. Klicken Sie auf **Download**
4. Warten Sie, bis der Download abgeschlossen ist
5. **Starten Sie Home Assistant neu**

### Schritt 4: Integration konfigurieren

1. Gehen Sie zu **Einstellungen** > **Geräte & Dienste**
2. Klicken Sie auf **Integration hinzufügen** (unten rechts)
3. Suchen Sie nach **FritzBox VPN**
4. Geben Sie die folgenden Informationen ein:
   - **FritzBox IP-Adresse**: z.B. `192.168.178.1`
   - **Benutzername**: Ihr FritzBox Benutzername
   - **Passwort**: Ihr FritzBox Passwort
5. Klicken Sie auf **Absenden**

Die Integration erkennt automatisch alle WireGuard VPN-Verbindungen auf Ihrer FritzBox.

## Manuelle Installation (ohne HACS)

### Schritt 1: Dateien kopieren

1. Kopieren Sie den gesamten `custom_components/fritzbox_vpn` Ordner in Ihr Home Assistant `custom_components` Verzeichnis
   - Standard-Pfad: `/config/custom_components/fritzbox_vpn`
2. Stellen Sie sicher, dass die Verzeichnisstruktur korrekt ist:
   ```
   /config/custom_components/fritzbox_vpn/
   ├── __init__.py
   ├── config_flow.py
   ├── const.py
   ├── coordinator.py
   ├── manifest.json
   ├── switch.py
   └── translations/
       ├── de.json
       └── en.json
   ```

### Schritt 2: Home Assistant neu starten

1. Gehen Sie zu **Einstellungen** > **System** > **Hardware**
2. Klicken Sie auf die drei Punkte (⋮) oben rechts
3. Wählen Sie **Home Assistant neu starten**

### Schritt 3: Integration konfigurieren

Folgen Sie **Schritt 4** aus der HACS-Installation.

## Verifizierung

Nach der Installation sollten Sie:

1. In **Einstellungen** > **Geräte & Dienste** die Integration **FritzBox VPN** sehen
2. Für jede VPN-Verbindung eine Switch Entity finden:
   - Entity ID: `switch.fritzbox_vpn_<connection_name>`
   - Name: `FritzBox VPN <connection_name>`

## Fehlerbehebung

### Integration wird nicht gefunden

- Stellen Sie sicher, dass die Dateien im richtigen Verzeichnis sind
- Überprüfen Sie die `manifest.json` Datei
- Starten Sie Home Assistant neu

### Authentifizierung fehlgeschlagen

- Überprüfen Sie Benutzername und Passwort
- Stellen Sie sicher, dass der Benutzer die entsprechenden Berechtigungen hat
- Versuchen Sie, sich direkt über die FritzBox Web-UI anzumelden

### Keine VPN-Verbindungen gefunden

- Stellen Sie sicher, dass WireGuard VPN auf Ihrer FritzBox aktiviert ist
- Überprüfen Sie, ob VPN-Verbindungen in der FritzBox konfiguriert sind
- Überprüfen Sie die Home Assistant Logs für Fehlermeldungen

### Logs überprüfen

1. Gehen Sie zu **Einstellungen** > **System** > **Logs**
2. Filtern Sie nach `fritzbox_vpn`
3. Überprüfen Sie die Fehlermeldungen

## Unterstützung

Bei Problemen:
- Überprüfen Sie die [README.md](README.md)
- Erstellen Sie ein Issue auf GitHub
- Überprüfen Sie die Home Assistant Community Foren


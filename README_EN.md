# FritzBox VPN Integration for Home Assistant

This integration allows you to control WireGuard VPN connections on an AVM FritzBox directly through Home Assistant.

## Features

- ✅ Automatic detection of all WireGuard VPN connections
- ✅ Turn VPN connections on/off via Switch entities
- ✅ Automatic status updates every 30 seconds
- ✅ Easy configuration through the Home Assistant UI
- ✅ Support for multiple VPN connections

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click on **Custom repositories**
4. Add this repository:
   - Repository: `https://github.com/rosch100/fritzbox-vpn`
   - Category: **Integration**
5. Search for **FritzBox VPN** and install it
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/fritzbox_vpn` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click on **Add Integration**
3. Search for **FritzBox VPN**
4. Enter the following information:
   - **FritzBox IP Address**: e.g. `192.168.178.1`
   - **Username**: Your FritzBox username
   - **Password**: Your FritzBox password
5. Click **Submit**

The integration automatically detects all WireGuard VPN connections on your FritzBox and creates a Switch entity for each one.

## Usage

After configuration, you will find a Switch entity for each VPN connection:
- **Entities**: `switch.fritzbox_vpn_<connection_uid>`
  
The entity ID is based on the unique ID (UID) of the VPN connection. The display name shows the actual name of the VPN connection.

You can use these switches to:
- Turn VPN connections on and off
- Monitor the current status
- Create automations

### Status Attributes

Each VPN switch entity provides the following attributes:

- **name**: The name of the VPN connection (as configured on the FritzBox)
- **uid**: The unique connection ID (Connection UID)
- **vpn_uid**: The internal VPN UID of the FritzBox
- **active**: `true` if the VPN connection is activated, `false` if deactivated
- **connected**: `true` if the VPN connection is actively connected, `false` if not connected
- **status**: Textual status description:
  - `"verbunden"` - VPN is activated and connected
  - `"aktiviert (nicht verbunden)"` - VPN is activated but not connected
  - `"deaktiviert"` - VPN is deactivated
  - `"unbekannt"` - Status could not be determined

## Automations

You can use the VPN switches in automations to automatically turn VPN connections on and off based on various conditions.

## Requirements

- AVM FritzBox with WireGuard VPN support
- FritzBox firmware with WireGuard enabled
- User with appropriate permissions on the FritzBox

## Support

For problems or questions:
- Create an issue on GitHub
- Check the Home Assistant logs

## Logo

The logo is automatically loaded from the [Home Assistant Brands Repository](https://github.com/home-assistant/brands) once it is registered there. The local logo serves as a fallback.

## License

MIT License


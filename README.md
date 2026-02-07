# Fritz!Box VPN for Home Assistant

[🇩🇪 Deutsch](README.de.md) | [🇬🇧 English](README.md)

This integration allows you to control WireGuard VPN connections on an AVM Fritz!Box directly through Home Assistant.

## Features

- Automatic detection of all WireGuard VPN connections
- Turn VPN connections on/off via Switch entities
- Easy configuration through the Home Assistant UI
- Support for multiple VPN connections
- Automatic configuration from existing Fritz!Box Tools
- Automatic FritzBox discovery via SSDP/UPnP
- Configurable update interval (5-300 seconds)
- Session caching: only one login per integration load (no login on every poll), so router access notifications by email stay minimal

## Installation

1. Open HACS in Home Assistant
2. Go to Integrations
3. Search for "Fritz!Box VPN" and install it
4. Restart Home Assistant

### Testing beta versions

To install a beta release (e.g. for testing fixes before the next stable release):

1. In HACS, open the **Fritz!Box VPN** integration card.
2. Click the **⋮** (three dots) in the top right and choose **Redownload**.
3. Enable **Show beta versions**, wait for the list to refresh.
4. Select the desired beta version (e.g. `0.9.0b1`) and confirm.
5. Restart Home Assistant.

Beta releases are published as GitHub Pre-releases (tags like `v0.9.0b1`).

## Configuration

### Automatic Discovery (Recommended)

1. Go to Settings > Devices & Services
2. Click on Add Integration
3. If a FritzBox is found on your network, it will be automatically discovered
4. The integration will try to use credentials from Fritz!Box Tools if available
5. Enter your credentials if needed and click Submit

**Note:** For automatic discovery to work, UPnP should be enabled in your FritzBox (recommended, but not required). If UPnP is disabled, you can still configure the integration manually. TR-064 is always required for API access (see Requirements section).

### Manual Configuration

1. Go to Settings > Devices & Services
2. Click on Add Integration
3. Enter the following information:
   - FritzBox IP Address: e.g. `192.168.178.1`
   - Username: Your FritzBox username
   - Password: Your FritzBox password
4. Click Submit

**Important:** Make sure TR-064 is enabled in your FritzBox (see Requirements section above). If you encounter authentication errors, check that TR-064 is enabled.

The integration automatically detects all WireGuard VPN connections on your FritzBox and creates a Switch entity for each one.

### Update Interval Configuration

You can configure the update interval (how often the integration checks for VPN status changes) in the integration options:

1. Go to Settings > Devices & Services
2. Find your Fritz!Box VPN integration
3. Click on Configure
4. Adjust the Update interval (5-300 seconds, default: 30 seconds)
5. Click Submit

The update interval determines how frequently the integration polls the FritzBox for VPN status updates. Lower values provide more frequent updates but may increase network traffic and FritzBox load. Higher values reduce network traffic but may delay status updates.

### Security

All credentials (username and password) are securely stored by Home Assistant:
- Credentials are encrypted and stored in Home Assistant's secure storage
- They are never exposed in logs or configuration files
- Access is restricted to the integration itself

## Usage

After configuration, you will find the following entities for each VPN connection:

### Switch
- Purpose: Turn VPN connections on and off (Enabled/Disabled)
- Entity ID: `switch.fritzbox_vpn_<connection_uid>_switch`
- Name: Uses the VPN connection name from the device
- Status: Shows if the VPN is activated (on) or deactivated (off)

### Binary Sensor

1. Connected Binary Sensor
   - Purpose: Shows if the VPN connection is actively connected
   - Entity ID: `binary_sensor.fritzbox_vpn_<connection_uid>_connected`
   - Value: `on` if connected, `off` if not connected

### Sensor

1. Status Sensor
   - Purpose: Shows the combined VPN status as text
   - Entity ID: `sensor.fritzbox_vpn_<connection_uid>_status`
   - Values: 
     - `connected` - VPN is enabled and connected
     - `enabled` - VPN is enabled but not connected
     - `disabled` - VPN is disabled
     - `unknown` - Status could not be determined

2. UID Sensor (disabled by default)
   - Purpose: Shows the unique connection ID (Connection UID)
   - Entity ID: `sensor.fritzbox_vpn_<connection_uid>_uid`
   - Value: The connection UID string (same as `<connection_uid>`)

3. VPN UID Sensor (disabled by default)
   - Purpose: Shows the internal VPN UID of the FritzBox
   - Entity ID: `sensor.fritzbox_vpn_<connection_uid>_vpn_uid`
   - Value: The internal VPN UID string (from `conn.get('uid')`)

You can use these entities to:
- Turn VPN connections on and off (switch)
- Monitor connection status (connected binary sensor)
- View detailed status information (status sensor)
- Access technical identifiers (UID sensors, disabled by default)
- Create automations based on connection status

### Status Attributes

Each VPN switch entity provides the following attributes:

- name: The name of the VPN connection (as configured on the FritzBox)
- uid: The unique connection ID (Connection UID)
- vpn_uid: The internal VPN UID of the FritzBox
- active: `true` if the VPN connection is activated, `false` if deactivated
- connected: `true` if the VPN connection is actively connected, `false` if not connected
- status: Textual status description:
  - `"connected"` - VPN is activated and connected
  - `"enabled"` - VPN is activated but not connected
  - `"disabled"` - VPN is deactivated
  - `"unknown"` - Status could not be determined

## Requirements

- AVM FritzBox with WireGuard VPN support
- FritzBox firmware with WireGuard enabled
- User with appropriate permissions on the FritzBox
- **TR-064 must be enabled** in the FritzBox settings (required for API access)
- **UPnP recommended** for automatic discovery via SSDP (optional, but recommended)

### FritzBox Settings

Before configuring the integration, you need to enable the required settings in your FritzBox:

1. Open the FritzBox web interface
2. Go to **Home Network** > **Network** > **Network settings**
3. Click on **Access Settings in the Home Network**
4. Enable **TR-064 (Permit access for apps)** - **Required** for API access
5. Enable **UPnP (Transmit status information over UPnP)** - **Recommended** for automatic discovery
6. Click **Apply**

**Note:** 
- **TR-064 is required** - The integration cannot work without it
- **UPnP is recommended** - Enables automatic discovery of your FritzBox via SSDP. If UPnP is disabled, you can still configure the integration manually by entering the IP address

## Support

For problems or questions:
- Create an issue on GitHub
- Check the Home Assistant logs

## Buy me a coffee

Like this integration? Feel free to buy me a coffee! ☕ Your support helps me continue working on cool features.

[![Buy Me A Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=rosch100&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://buymeacoffee.com/rosch100)

## License

This project is licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0), the same license as [Home Assistant](https://github.com/home-assistant/core/blob/dev/LICENSE.md), to ensure compatibility and consistency with the Home Assistant ecosystem.

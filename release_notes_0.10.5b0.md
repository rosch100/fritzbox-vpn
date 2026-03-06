## Added

- **Service** `fritzbox_vpn.remove_unavailable_entities`: Removes entity registry entries for VPN connections that no longer exist on the Fritz!Box and reloads the integration. Call from Developer Tools → Services or from a dashboard button; optional parameter `config_entry_id` when using multiple integrations.

## Fixed

- **Options dialog**: "Unknown error" no longer appears; menu shows the correct description ("Choose an action"). The "Remove unavailable entities" step no longer crashes (compatible with recent Home Assistant versions).

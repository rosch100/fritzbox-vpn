# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.11.0] - 2026-03-07

### Changed

- **Home Assistant 2026.1.0** or newer required.
- **Options**: Remove unavailable entities and repair entity IDs with `_2`, `_3`, … suffix (Integration → Configure).
- **Services**: `fritzbox_vpn.remove_unavailable_entities`, `fritzbox_vpn.repair_entity_id_suffixes` (optional `config_entry_id`).
- Entity IDs stay stable when a VPN connection disappears temporarily and reappears.

[0.11.0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.11.0

## [0.10.9b0] - 2026-03-07 (Beta)

### Changed

- **Home Assistant**: Integration requires Home Assistant **2026.1.0** or newer.
- **Options**: In the integration options you can remove unavailable entities (only shown when there are orphaned entities) and repair entity IDs that got a `_2`, `_3`, … suffix so automations keep working.
- **Services**: `fritzbox_vpn.remove_unavailable_entities` and `fritzbox_vpn.repair_entity_id_suffixes`; optional `config_entry_id` when using multiple Fritz!Box VPN entries.
- **Stability**: When VPN connections disappear temporarily, entity IDs are kept so they stay the same when the connection reappears.

[0.10.9b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.9b0

## [0.10.8b0] - 2026-03-07 (Beta)

### Changed

- Options menu: „Remove unavailable entities“ only appears when there are orphaned entities.
- After removing a VPN connection on the Fritz!Box, entity IDs remain stable when the connection is added again (no automatic removal from registry for temporary outages).

[0.10.8b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.8b0

## [0.10.7b0] - 2026-03-07 (Beta)

### Fixed

- HACS validation passes (invalid key removed from manifest).

[0.10.7b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.7b0

## [0.10.6b0] - 2026-03-07 (Beta)

### Fixed

- Options step „Remove unavailable entities“ no longer crashes on newer Home Assistant versions.

[0.10.6b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.6b0

## [0.10.5b0] - 2026-03-07 (Beta)

### Added

- **Service** `fritzbox_vpn.remove_unavailable_entities`: Removes entities for VPN connections that no longer exist on the Fritz!Box and reloads the integration. Call via Developer Tools > Services or a button; optional `config_entry_id` when you have multiple entries.

### Fixed

- Options dialog no longer shows „Unknown error“; menu shows the correct description. Step „Remove unavailable entities“ works on newer Home Assistant versions.

[0.10.5b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.5b0

## [0.10.4b0] - 2026-03-06 (Beta)

### Changed

- Update interval is validated and normalized in one place; configuration and polling use the same limits (5–3600 s).

[0.10.4b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.4b0

## [0.10.3b0] - 2026-03-06 (Beta)

### Added

- **Dynamic entities**: New VPN connections on the Fritz!Box are detected automatically; switch, sensor and binary sensor entities are added without reloading the integration.

### Changed

- When VPN connections were removed on the Fritz!Box, a clear log message appears and you can remove obsolete entities under Settings > Devices & Services > Entities. Affected entities show as „unavailable“.

### Fixed

- VPN on/off works reliably again (API sometimes uses `activated` instead of `active`; status is normalized when reading).

[0.10.3b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.3b0

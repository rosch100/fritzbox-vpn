# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.10.8b0] - 2026-03-07 (Beta)

### Added

- **Dokumentation**: HACS- und Home-Assistant-Konformitätsprüfung (`docs/HACS_AND_HOMEASSISTANT_COMPLIANCE.md`) inkl. Link zum Brands-Eintrag [custom_integrations/fritzbox_vpn](https://github.com/home-assistant/brands/tree/master/custom_integrations/fritzbox_vpn).

### Changed

- **Refactor**: `config_flow`: Hilfsfunktion `_resolve_current_uids`; `__init__`: `_entry_ids_for_cleanup_service` für den Service; `switch`: gemeinsame Toggle-Logik in `_async_toggle_connection(enable)`.
- **Options**: Option „Unavailable-Entitäten entfernen“ wird nur angezeigt, wenn tatsächlich verwaiste Einträge vorhanden sind.
- **Auto-Cleanup**: Entfernt nur aus `known_uids`, nicht aus Entity/Device-Registry – Entity-IDs bleiben bei wieder erscheinenden VPN-Verbindungen stabil.

### Removed

- Alte Release-Notes-Dateien (`release_notes_0.10.4b0.md` bis `0.10.6b0.md`).

[0.10.8b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.8b0

## [0.10.7b0] - 2026-03-07 (Beta)

### Fixed

- **HACS**: Ungültigen Schlüssel `domains` aus `hacs.json` entfernt (HACS-Validation läuft durch).

[0.10.7b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.7b0

## [0.10.6b0] - 2026-03-07 (Beta)

### Fixed

- Options-Schritt „Unavailable-Entitäten entfernen“ stürzt unter neueren Home-Assistant-Versionen nicht mehr ab (API-Anpassung `async_show_form`).

[0.10.6b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.6b0

## [0.10.5b0] - 2026-03-07 (Beta)

### Added

- **Service** `fritzbox_vpn.remove_unavailable_entities`: Entfernt nicht mehr vorhandene Entitäten und lädt die Integration neu. Aufruf z. B. über Entwicklerwerkzeuge → Dienste oder eine Schaltfläche; optionaler Parameter `config_entry_id` bei mehreren Integrationen.

### Fixed

- **Options-Dialog**: Kein „Unknown error“ mehr; Menü zeigt die richtige Beschreibung („Wählen Sie eine Aktion“). Schritt „Unavailable-Entitäten entfernen“ stürzt nicht mehr ab (kompatibel mit neueren Home-Assistant-Versionen).

[0.10.5b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.5b0

## [0.10.4b0] - 2026-03-06 (Beta)

### Changed

- **Refactor (SSOT, weniger Redundanz)**:
  - Unique-ID-Präfix und Suffixe zentral in `const.py` (`UNIQUE_ID_PREFIX`, `UNIQUE_ID_SUFFIX_*`); alle Plattformen und der Options-Flow nutzen diese Konstanten. Parsing von `connection_uid` aus Entity-`unique_id` erfolgt über bekannte Suffixe (korrekt auch bei `vpn_uid`).
  - Update-Intervall: Einmalige Normalisierung in `coordinator.normalize_update_interval()`; Config-Flow und Coordinator nutzen diese Funktion, keine doppelte Konvertierungs-/Bereichslogik mehr.
  - Options-Flow: Hilfsfunktionen `_get_orphaned_entity_entries`, `_remove_orphaned_entities_and_clear_known_uids`, `_build_configure_schema`; Schritte „Configure“ und „Unavailable-Entitäten entfernen“ kürzer und klarer.

[0.10.4b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.4b0

## [0.10.3b0] - 2026-03-06 (Beta)

### Added

- **Dynamische Entitäten**: Neue VPN-Verbindungen auf der Fritz!Box werden automatisch erkannt; Switch-, Sensor- und Binary-Sensor-Entitäten werden ohne Neuladen der Integration ergänzt.
- Testskript `scripts/test_live_fritzbox_vpn.py` und `scripts/.env.example` für lokale Tests gegen eine Live-Fritz!Box (optional, nur für Entwicklung).

### Changed

- **Nicht mehr verfügbare Verbindungen**: Wenn VPN-Verbindungen auf der Fritz!Box entfernt wurden, erscheint eine klare Log-Warnung inkl. Hinweis, obsolete Entitäten unter Einstellungen > Geräte & Dienste > Entitäten zu entfernen. Betroffene Entitäten werden als „unavailable“ angezeigt.
- Refactor: Log-Meldungen und API-Schlüssel zentral in `const.py` (SSOT); robustere XML-Auswertung bei leerem Login-Response; einheitliche Fehlerbehandlung beim VPN-Toggle.

### Fixed

- VPN Ein/Aus funktioniert wieder zuverlässig: API-Antwort nutzt teils `activated` statt `active`; Status wird beim Einlesen normalisiert, Request-Body als Integer gesendet.

[0.10.3b0]: https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.10.3b0

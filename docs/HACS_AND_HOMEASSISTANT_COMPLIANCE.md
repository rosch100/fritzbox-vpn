# HACS- und Home-Assistant-Konformität

Stand: Prüfung am Repo-Stand (nach Refactor).

## HACS-Konformität

### Erfüllt

| Anforderung | Status |
|-------------|--------|
| **Struktur** | `custom_components/fritzbox_vpn/` – alle Integrationsdateien im richtigen Verzeichnis |
| **Eine Integration pro Repo** | Nur ein Unterverzeichnis unter `custom_components/` (`fritzbox_vpn`) |
| **manifest.json** (Pflichtfelder) | `domain`, `name`, `version`, `codeowners`, `issue_tracker`, `documentation` alle gesetzt |
| **README.md im Repo-Root** | Vorhanden (inkl. Link zu README.de.md) |
| **info.md** | Optional; mit `render_readme: true` in `hacs.json` wird die README angezeigt – ausreichend |
| **hacs.json** | Im Repo-Root, mit `name`, `render_readme`, `homeassistant` |

### Optional / Empfehlungen

- **GitHub Releases**: Erwünscht, aber nicht Pflicht. Beta-Releases (z. B. `v0.10.0b1`) sind dokumentiert – in Ordnung.
- **Brands/Icon**: Es wird das Standard-Icon geladen und genutzt. Ein Eintrag für diese Integration existiert im [home-assistant/brands](https://github.com/home-assistant/brands)-Repo: [custom_integrations/fritzbox_vpn](https://github.com/home-assistant/brands/tree/master/custom_integrations/fritzbox_vpn) (icon.png, logo.png inkl. @2x-Varianten). Icons werden unter [brands.home-assistant.io](https://brands.home-assistant.io/) bereitgestellt.
- **hacs.json** – optional ergänzbar:
  - `"domains": ["fritzbox_vpn"]` zur expliziten Zuordnung
  - `"persistent_directory": ".storage"` nur, falls persistente Dateien außerhalb von HA nötig sind (hier nicht erforderlich)

---

## Home-Assistant-Konformität

### manifest.json

| Feld | Wert | Bewertung |
|------|------|-----------|
| domain | `fritzbox_vpn` | OK |
| name | `Fritz!Box VPN` | OK |
| version | `0.10.7b0` | OK (SemVer-kompatibel) |
| codeowners | `["@rosch100"]` | OK (gültiges GitHub-Handle mit `@`) |
| issue_tracker | `https://github.com/rosch100/fritzbox-vpn/issues` | OK |
| documentation | `https://github.com/rosch100/fritzbox-vpn` | OK |
| config_flow | `true` | OK (UI-Setup) |
| dependencies | `["ssdp"]` | OK |
| integration_type | `device` | OK |
| iot_class | `local_polling` | OK |
| requirements | `["aiohttp>=3.8.0"]` | OK |

### Quality Scale (Überblick)

- **Config Flow**: Vorhanden – Setup über UI möglich.
- **Dokumentation**: README mit Installation, Konfiguration, Optionen.
- **Issue-Tracker**: Verlinkt.
- **Translations**: `translations/de.json` und `translations/en.json` vorhanden.

Für höhere Stufen (Silver/Gold) ggf. weitere offizielle [Quality-Scale-Regeln](https://developers.home-assistant.io/docs/core/integration-quality-scale/) prüfen (z. B. Tests, Stabilität, Entitäts-/Geräte-Modelle).

---

## Kurzfassung

- **HACS**: Konform; Icon/Brand-Eintrag: [custom_integrations/fritzbox_vpn](https://github.com/home-assistant/brands/tree/master/custom_integrations/fritzbox_vpn).
- **Home Assistant**: manifest.json vollständig und konsistent, Config Flow, Dokumentation und Übersetzungen vorhanden – konform für den Einsatz als Custom Integration.

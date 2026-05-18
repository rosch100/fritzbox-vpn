# Home Assistant documentation PR

Draft for [home-assistant/home-assistant.io](https://github.com/home-assistant/home-assistant.io).

## Submit

1. Fork `home-assistant/home-assistant.io`, branch from `current`.
2. Copy `fritzbox_vpn.markdown` to `source/_integrations/fritzbox_vpn.markdown`.
3. Adjust `ha_release` in the front matter to the Home Assistant version that will ship the integration (placeholder: `2026.2`).
4. Open a PR **after** the matching `home-assistant/core` PR is accepted (or reference both PRs in the description).
5. Run the site's validation locally if you build docs (optional).

## Core PR dependency

The integration must exist in `homeassistant/components/fritzbox_vpn/` and `fritzboxvpn` must be on PyPI at the version pinned in `manifest.json` before the docs page goes live.

## Brand

No separate brand file is needed if `fritzbox_vpn` is listed under `homeassistant/brands/fritzbox.json` in core (same FRITZ! brand as `fritz` / `fritzbox`).

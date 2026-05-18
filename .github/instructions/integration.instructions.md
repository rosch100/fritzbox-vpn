---
applyTo: "custom_components/fritzbox_vpn/**"
---

# Fritz!Box VPN integration code

## SSDP and config flow

- Extend `ssdp_unique_id.py` for new discovery rules; call it from `config_flow.py`.
- `unique_id_for_discovery`, `uuid_from_discovery`, `host_from_ssdp`, and `is_fritzbox_router_discovery` are the public SSDP API.
- Link-local hosts may be aborted; hostnames like `fritz.box` are valid.

## Home Assistant patterns

- Use existing coordinators and `DATA_*` keys in `const.py`.
- Config flow: guard validation errors; do not swallow exceptions.
- Entity `unique_id` must remain stable across restarts (prefixes in `const.py`).

## Tests required for changes here

- SSDP/helpers: `tests/test_ssdp_unique_id.py`
- SSDP config flow steps: `tests/test_config_flow_ssdp.py` (flow handler mocks, no full integration socket)

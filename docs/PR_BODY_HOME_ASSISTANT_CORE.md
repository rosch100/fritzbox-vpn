Fixes #165036

## Proposed change

SSDP: set stable `unique_id` when UDN is missing (fallback `host`); when an entry exists for that host, update it to the discovery UDN. Prevents repeaters from showing as "new" after restart.

Same pattern as [Fritz!Box VPN](https://github.com/rosch100/fritzbox-vpn): SSDP step always sets `unique_id` (host or USN), then `_abort_if_unique_id_configured` — see `config_flow.async_step_ssdp` there.

## Type of change

- [x] Bugfix (non-breaking change which fixes an issue)

## Additional information

- This PR fixes or closes issue: fixes #165036  
  Does not fix #163330 (entity unique_id collisions): that issue is about **entity** unique_ids (e.g. switch `avm_wrapper.unique_id` + slug) colliding when multiple devices have similar SSIDs; this change only touches **config entry** unique_id in SSDP.

## Checklist

- [x] The code change is tested and works locally.
- [x] I have followed the [development checklist][dev-checklist]

[dev-checklist]: https://developers.home-assistant.io/docs/development_checklist/

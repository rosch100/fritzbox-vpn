Fixes #165036

- Use `host` as unique_id when UDN is missing.
- When entry found by host, set `unique_id=uuid` when UDN present (migrates `unique_id=host`).

Testing: Add repeater via discovery, restart HA; repeater should not reappear as new.

[Fritz!Box VPN](https://github.com/rosch100/fritzbox-vpn); may help #163330.

# fritzboxvpn

Async Python library for the AVM Fritz!Box Web UI API (WireGuard and supported IPSec user VPN connections).

Used by the Home Assistant `fritzbox_vpn` integration (HACS and Core).

Set `include_ipsec=True` on `FritzBoxVPNSession` to include IPSec user
connections from the FRITZ!OS VPN REST API. If that endpoint is unavailable,
the legacy fallback can enumerate WireGuard connections only.

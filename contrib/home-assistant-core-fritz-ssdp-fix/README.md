# Fritz SSDP unique_id fix (home-assistant/core)

Fixes #165036: repeaters no longer show as "new" after restart.

**Changes:** Use `host` as unique_id when UDN is missing; when an entry exists by host, set `unique_id=uuid` whenever UDN is present.

**Apply** (from core repo root):
```bash
git checkout -b fix/fritz-ssdp-repeater-unique-id
git apply < path/to/fritz-ssdp-unique-id.patch
git add homeassistant/components/fritz/config_flow.py
git commit -m "Fix FRITZ!Box Tools SSDP: stable unique_id and migrate entry to UDN (#165036)"
git push origin fix/fritz-ssdp-repeater-unique-id
```

**PR:** Base `home-assistant:dev`, body from `PR_DESCRIPTION.md`.  
Ref: [Fritz!Box VPN](https://github.com/rosch100/fritzbox-vpn); may help #163330.

---

## PR erstellen

1. Fork [home-assistant/core](https://github.com/home-assistant/core).
2. Clone, upstream, branch:
   ```bash
   git clone https://github.com/DEIN_USER/core.git && cd core
   git remote add upstream https://github.com/home-assistant/core.git
   git fetch upstream && git checkout -b fix/fritz-ssdp-repeater-unique-id upstream/dev
   ```
3. `git apply < path/to/fritz-ssdp-unique-id.patch`
4. `git add homeassistant/components/fritz/config_flow.py` → commit (message above) → `git push origin fix/fritz-ssdp-repeater-unique-id`
5. GitHub: Compare & pull request → Base `home-assistant/dev`, Titel/Body aus README/PR_DESCRIPTION.md.

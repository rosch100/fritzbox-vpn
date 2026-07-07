# Agent-Anleitung (fritzbox-vpn)

Kurzreferenz für **Coding-Agents** (Cursor, Copilot): projektspezifische Invarianten und lokale Checks. Nutzer-Doku: `README.md`. Review-Hinweise: `.github/copilot-instructions.md`.

## Architektur

| Bereich | Pfad |
|--------|------|
| Integration | `custom_components/fritzbox_vpn/` |
| SSDP / `unique_id` (SSOT) | `ssdp_unique_id.py` |
| Config Flow | `config_flow.py` |
| Daten / Polling | `coordinator.py`, `sensor.py`, `switch.py` |
| Tests | `tests/` |

## Invarianten

- SSDP/`unique_id` nur in `ssdp_unique_id.py` — nicht in `config_flow.py` duplizieren.
- Nur Fritz!Box-**Router** discovern, keine FRITZ!Repeater.
- Keine stillen Fallbacks: fehlende Discovery-Daten → Abort/Fehler, keine Dummy-`unique_id`.
- Breaking Changes: Release Notes in `docs/releases/v{version}.md` (Workflow `release.yml`, HACS/HA-Update-Dialog).
- Mindestversion HA: `hacs.json` / `manifest.json`.

## Qualität & Tests

Ziel **Gold** (`custom_components/fritzbox_vpn/quality_scale.yaml`), Coverage ≥ 85 %.

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements-test.txt
.venv/bin/ruff check custom_components tests
.venv/bin/pytest tests/ --cov=custom_components/fritzbox_vpn -q
```

Vor Merge: CI-Jobs `Ruff`, `pytest`, `HACS validate`, `hassfest`.

## Core-Vorbereitung

API-Library `fritzboxvpn/` (PyPI vor Core-Merge), Core-Pfad unter `home-assistant-core/homeassistant/components/fritzbox_vpn/`. Details: `docs/pypi-publish.md`, `docs/home-assistant-io/fritzbox_vpn.markdown`.

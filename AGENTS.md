# Agent-Anleitung (fritzbox-vpn)

Home-Assistant-Custom-Integration für WireGuard-VPN auf AVM Fritz!Box.

## Architektur

| Bereich | Pfad |
|--------|------|
| Integration | `custom_components/fritzbox_vpn/` |
| SSDP / `unique_id` (SSOT) | `ssdp_unique_id.py` |
| Config Flow | `config_flow.py` |
| Daten / Polling | `coordinator.py`, `sensor.py`, `switch.py` |
| Tests | `tests/` (pytest + `pytest-homeassistant-custom-component`) |

## Wichtige Regeln

- **SSDP-Logik nur in `ssdp_unique_id.py`:** UUID aus UDN/USN, Host aus Location, `unique_id_for_discovery`, Router vs. Repeater (`is_fritzbox_router_discovery`). Nicht in `config_flow` duplizieren.
- **Repeater:** Diese Integration discovert nur **Router**, keine FRITZ!Repeater (anders als `homeassistant.components.fritz` im Core).
- **Keine stillen Fallbacks:** Fehlende Discovery-Daten explizit behandeln (Abort/Fehler), keine Dummy-`unique_id`.
- **Home Assistant:** Mindestversion siehe `manifest.json`; Tests mit der Version aus `scripts/requirements-test.txt`.

## Tests lokal

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements-test.txt
.venv/bin/pytest tests/ --cov -q
.venv/bin/ruff check custom_components tests
```

`tests/conftest.py` setzt `hass_config_dir` auf das Repo-Root und aktiviert Custom Integrations.

## CI (GitHub Actions)

- **tests.yml** – pytest + Coverage (`.coveragerc`, `fail_under` für `ssdp_unique_id.py`)
- **lint.yml** – Ruff (`pyproject.toml`)
- **hacs.yml** / **hassfest.yml** – HACS- und Manifest-Validierung
- **codeql.yml** – Sicherheitsanalyse Python
- **dependency-review.yml** – PR-Abhängigkeitsprüfung
- **Dependabot** – wöchentlich Actions + pip

## Änderungen an Workflows

Path-Filter und `concurrency` mit bestehenden Workflows abgleichen. `checkout@v6`, `setup-python@v6` beibehalten.

## Verwandtes Core-PR

Stabile SSDP-`unique_id` für FRITZ! (inkl. Repeater) liegt in `home-assistant/core` PR #165042 (`fritz/config_flow.py`). Bei SSDP-Änderungen Konzept mit Core abstimmen, Router/Repeater-Filter nur hier.

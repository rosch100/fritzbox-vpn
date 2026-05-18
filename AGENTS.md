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
- **Home Assistant:** Mindestversion in `hacs.json` und `manifest.json` (2026.1.0); Tests: `scripts/requirements-test.txt`.

## Quality Scale

Ziel: **Gold** (siehe `custom_components/fritzbox_vpn/quality_scale.yaml`): Reauth, Diagnostics, Übersetzungen, **≥85 % Test-Coverage** (`pytest --cov`). Offizielles Badge erst nach Aufnahme in Home Assistant Core.

## Tests lokal

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements-test.txt
.venv/bin/ruff check custom_components tests
.venv/bin/pytest tests/ --cov=custom_components/fritzbox_vpn -q
```

`tests/conftest.py` setzt `hass_config_dir` auf das Repo-Root und aktiviert Custom Integrations.

## GitHub Copilot Code Review

- **Automatisch:** Ruleset „Copilot code review“ (alle Branches, Review bei jedem Push).
- **Konfiguration:** `.github/rulesets/copilot-code-review.json`, Richtlinien in `.github/copilot-instructions.md` und `.github/instructions/*.instructions.md`.
- **Settings:** Repository → Copilot → Code review → Custom Instructions aktiviert lassen.

## CI / Automation (Übersicht)

| Workflow | Trigger | Zweck |
|----------|---------|--------|
| **ci.yml** | PR/Push (Pfade), nightly, manual | Ruff, pytest, HACS, hassfest |
| **actionlint.yml** | `.github/**` | Workflow-Syntax |
| **dependency-review.yml** | PR (Deps) | Sicherheit Abhängigkeiten (fail high+) |
| **release.yml** | Tags `v*` | GitHub Release + Manifest-Versionscheck |
| **stale.yml** | täglich | Inaktive Issues/PRs |
| **Dependabot** | wöchentlich | Actions + pip |
| **CodeQL** | Default Setup (GitHub) | Python + Actions, kein `codeql.yml` (Konflikt) |

PR-Checks heißen: `Ruff`, `pytest`, `HACS validate`, `hassfest`.

**Geschütztes `main`:** Ruleset „Required CI checks“ – Änderungen nur per **Pull Request**; vor Merge müssen `Ruff`, `pytest`, `HACS validate`, `hassfest` grün sein.

## Verwandtes Core-PR

Stabile SSDP-`unique_id` für FRITZ! (inkl. Repeater) liegt in `home-assistant/core` PR #165042. Bei SSDP-Änderungen Konzept mit Core abstimmen; Router/Repeater-Filter nur hier.

# Copilot instructions (fritzbox-vpn)

Home Assistant custom integration for WireGuard VPN on AVM Fritz!Box routers.

## Build and validate

Always run these before approving changes:

```bash
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements-test.txt
.venv/bin/ruff check custom_components tests
.venv/bin/pytest tests/ --cov -q
```

- Minimum Home Assistant version: see `custom_components/fritzbox_vpn/manifest.json`
- Test deps: `scripts/requirements-test.txt`
- Coverage gate: `.coveragerc` (`ssdp_unique_id.py` ≥ 95%)

## Architecture (do not break)

- **SSDP SSOT:** All SSDP/`unique_id` logic lives in `custom_components/fritzbox_vpn/ssdp_unique_id.py` only.
  Do not duplicate UUID/host parsing or router-vs-repeater checks in `config_flow.py`.
- **Router only:** This integration discovers Fritz!Box **routers**, not FRITZ!Repeaters (unlike `homeassistant.components.fritz` in core).
- **No silent fallbacks:** Missing discovery data must abort or error explicitly; never invent placeholder `unique_id` or credentials.
- **Secrets:** Never log or commit passwords; use existing masking helpers where applicable.

## Code review focus

Flag as blocking when you see:

- Duplicated SSDP logic outside `ssdp_unique_id.py`
- Repeater discovery enabled or repeater-specific flows added by mistake
- Dummy defaults for failed API/SSDP instead of explicit errors
- New code without tests for `config_flow` / SSDP changes
- Breaking changes to `manifest.json` version without release notes in `docs/releases/v{version}.md` (used by `.github/workflows/release.yml` for HACS/HA update dialog)

Prefer suggestions over nits for line length in legacy files (Ruff ignores `E501`).

## CI expectations

PRs should pass the **CI** workflow jobs: `Ruff`, `pytest`, `HACS validate`, `hassfest`.

Also: Actionlint (workflow changes), Dependency review (requirements/manifest), CodeQL via GitHub default setup.

See also `AGENTS.md` and `.github/instructions/*.instructions.md`.

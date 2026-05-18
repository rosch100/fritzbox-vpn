---
applyTo: "tests/**"
---

# Test suite

- Use `pytest-homeassistant-custom-component`; `tests/conftest.py` sets `hass_config_dir` to repo root.
- SSDP tests: mock `SsdpServiceInfo`; do not open real SSDP sockets in unit tests.
- Prefer testing `ssdp_unique_id` functions directly before full config-flow integration.
- Keep coverage for `ssdp_unique_id.py` above the `.coveragerc` `fail_under` threshold.

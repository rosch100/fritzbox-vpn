## Summary

<!-- Kurz: Was ändert sich und warum? -->

## Test plan

- [ ] CI grün (`Ruff`, `pytest`, `HACS validate`, `hassfest`) bzw. lokal: `ruff check` + `pytest tests/ --cov -q`
- [ ] Bei SSDP/`config_flow`: `tests/test_ssdp_unique_id.py` und `tests/test_config_flow_ssdp.py`
- [ ] Bei Manifest/Strings: HACS- und hassfest-Workflow beachtet

## Checklist

- [ ] Copilot Code Review abgewartet (läuft automatisch bei Push)
- [ ] Keine Secrets oder Zugangsdaten im Diff
- [ ] SSDP-Helfer nur in `ssdp_unique_id.py` (keine Duplikate in `config_flow`)
- [ ] Version in `manifest.json` nur bei Release-relevanten Änderungen angepasst

## Summary

<!-- Kurz: Was ändert sich und warum? -->

## Test plan

- [ ] `pytest tests/ --cov -q` lokal oder CI grün
- [ ] Bei SSDP/`config_flow`: `tests/test_ssdp_unique_id.py` und `tests/test_config_flow_ssdp.py`
- [ ] Bei Manifest/Strings: HACS- und hassfest-Workflow beachtet

## Checklist

- [ ] Keine Secrets oder Zugangsdaten im Diff
- [ ] SSDP-Helfer nur in `ssdp_unique_id.py` (keine Duplikate in `config_flow`)
- [ ] Version in `manifest.json` nur bei Release-relevanten Änderungen angepasst

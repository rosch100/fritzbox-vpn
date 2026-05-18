# Repository rulesets

## Copilot code review (aktiv)

`copilot-code-review.json` – automatische Copilot-Reviews auf PRs (alle Branches, bei jedem Push).

## Required CI checks (optional)

`required-ci.json` ist **deaktiviert** (`enforcement: disabled`), weil `main` derzeit keinen Branch-Schutz hat.

Zum Aktivieren:

1. Settings → Rules → Rulesets → Import `required-ci.json`
2. Enforcement auf **Active** setzen
3. Prüfen, dass die Check-Namen mit dem **CI**-Workflow übereinstimmen: `Ruff`, `pytest`, `HACS validate`, `hassfest`

## CodeQL

Kein eigener Workflow im Repo – **GitHub CodeQL Default Setup** ist aktiv (Python + Actions, wöclich). Ein zusätzlicher `codeql.yml` würde mit Default Setup kollidieren.

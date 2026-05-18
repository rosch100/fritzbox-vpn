# Repository rulesets

## Copilot code review (aktiv)

`copilot-code-review.json` – automatische Copilot-Reviews auf PRs (alle Branches, bei jedem Push).

## Required CI checks (aktiv)

`required-ci.json` – Schutz für **`main`**:

1. **Pull Request erforderlich** (0 Approvals) – kein direkter Push auf `main`
2. **Pflicht-Checks:** `Ruff`, `pytest`, `HACS validate`, `hassfest` (Workflow **CI**)

Ruleset-ID: **16545012** – [Einstellungen](https://github.com/rosch100/fritzbox-vpn/rules/16545012)

Änderungen: Feature-Branch → PR → CI grün → Merge.

## CodeQL

Kein eigener Workflow im Repo – **GitHub CodeQL Default Setup** ist aktiv (Python + Actions, wöclich). Ein zusätzlicher `codeql.yml` würde mit Default Setup kollidieren.

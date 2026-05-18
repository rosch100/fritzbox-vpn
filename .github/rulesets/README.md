# Repository rulesets

## Copilot code review (aktiv)

`copilot-code-review.json` – automatische Copilot-Reviews auf PRs (alle Branches, bei jedem Push).

## Required CI checks (aktiv)

`required-ci.json` – Pflicht-Checks auf **`main`** vor Merge:

- `Ruff`, `pytest`, `HACS validate`, `hassfest` (Workflow **CI**)
- `strict_required_status_checks_policy`: false
- `do_not_enforce_on_create`: true

Ruleset-ID: **16545012** – [Einstellungen](https://github.com/rosch100/fritzbox-vpn/rules/16545012)

Re-Import nur nötig nach manueller Löschung des Rulesets.

## CodeQL

Kein eigener Workflow im Repo – **GitHub CodeQL Default Setup** ist aktiv (Python + Actions, wöclich). Ein zusätzlicher `codeql.yml` würde mit Default Setup kollidieren.

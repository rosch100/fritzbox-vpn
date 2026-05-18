# Repository rulesets

## Copilot code review

`copilot-code-review.json` aktiviert automatische **GitHub Copilot Code Reviews** für Pull Requests:

- alle Branches (`~ALL`)
- erneut bei jedem Push (`review_on_push`)
- keine Draft-PRs (`review_draft_pull_requests: false`)

### Neu importieren

1. Repository → **Settings** → **Rules** → **Rulesets**
2. **New ruleset** → **Import a ruleset**
3. Datei `copilot-code-review.json` wählen und speichern

Das Ruleset ist auf `rosch100/fritzbox-vpn` bereits aktiv (ID in den Repo-Settings sichtbar).

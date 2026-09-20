# GitHub Issue Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add English-only GitHub Issue Forms (bug + feature) to `fritzbox-vpn`, with diagnostics JSON upload, no `.log` attachments, and README links to the issue chooser.

**Architecture:** YAML under `.github/ISSUE_TEMPLATE/` is the SSOT (no hub, no sync). Maintainer reply copy lives in `docs/issue-templates/README.md` (not shown by GitHub). User READMEs (`README.md`, `README.de.md`) only change Support/Diagnostics/debug-logging so they match the forms.

**Tech Stack:** GitHub Issue Forms (YAML, including `upload`), `gh` for labels, Python YAML parse for local checks. No new pytest/CI (spec non-goal).

## Global Constraints

- Language: English only in forms, chooser (`config.yml` contact links), and maintainer reply template.
- No German text in `.github/ISSUE_TEMPLATE/` YAML (no umlauts `äöüÄÖÜß`, no second file set).
- `upload` only for diagnostics JSON: `validations.accept: ".json"`; not required; never `.log` in `accept`.
- Every body element except `markdown` has a unique `id` (`A–Z`/`a–z`/`0–9`/`-`/`_`).
- Required checkboxes use `options[].required: true`.
- YAML UTF-8 without BOM; no trailing whitespace (`git diff --check`).
- Do not change `diagnostics.py`, logging, `manifest.json` `issue_tracker`, or add CI/label-bots.
- Do not add `bug_report_de.yml` / `feature_request_de.yml` or a contact link to `README.de.md`.
- Labels `bug` and `enhancement` must exist; GitHub does not auto-create them from the form.
- Repo: `/Users/roschmac/Entwicklung/HomeAutomation/HomeAssistant/fritzbox-vpn`

## File structure

| File | Responsibility |
| --- | --- |
| `.github/ISSUE_TEMPLATE/config.yml` | Chooser: blank issues off for contributors; English docs contact link |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Bug form (fields + privacy rules) |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Feature form |
| `docs/issue-templates/README.md` | Maintainer reply if secrets/logs are attached |
| `README.md` | English Support / Diagnostics / Debug logging |
| `README.de.md` | German Support / Diagnose / Debug-Logging (points at English chooser) |
| `docs/superpowers/specs/2026-09-20-github-issue-templates-design.md` | Mark design approved |

---

### Task 1: Issue form YAML + maintainer README

**Files:**
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `docs/issue-templates/README.md`
- Modify: `docs/superpowers/specs/2026-09-20-github-issue-templates-design.md` (status line only)

**Interfaces:**
- Consumes: spec field tables and English-only language rule
- Produces: GitHub forms `bug_report.yml` / `feature_request.yml` / `config.yml`; field ids listed in the YAML below (`searched-issues`, `summary`, `expected`, `actual`, `reproduce`, `ha-version`, `ha-install-type`, `integration-version`, `install-source`, `fritzbox`, `setup`, `availability-mode`, `diagnostics-json`, `debug-excerpt`, `confirm-no-secrets`, `confirm-no-log`, `confirm-redacted`, `problem`, `solution`, `alternatives`, `affected-flow`)

- [ ] **Step 1: Confirm templates are missing**

Run from repo root:

```bash
test ! -e .github/ISSUE_TEMPLATE/bug_report.yml
test ! -e .github/ISSUE_TEMPLATE/feature_request.yml
test ! -e .github/ISSUE_TEMPLATE/config.yml
test ! -e docs/issue-templates/README.md
```

Expected: all four `test` commands exit 0.

- [ ] **Step 2: Write `config.yml`**

Create `.github/ISSUE_TEMPLATE/config.yml` with exactly:

```yaml
blank_issues_enabled: false
contact_links:
  - name: Documentation
    url: https://github.com/rosch100/fritzbox-vpn/blob/main/README.md
    about: Installation, configuration, troubleshooting
```

- [ ] **Step 3: Write `bug_report.yml`**

Create `.github/ISSUE_TEMPLATE/bug_report.yml` with exactly:

```yaml
name: Bug report
description: Report a problem with Fritz!Box VPN in Home Assistant
title: "[Bug]: "
labels: [bug]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for reporting a bug.

        **Do not attach secrets or log files.**

        1. Do not attach a full `home-assistant.log`.
        2. Do not upload `.log` files (including the integration debug download as a file).
        3. Do not attach Fritz!Box backups, WireGuard `.conf`, or `.storage` / HAR / LocalStorage dumps.
        4. Prefer **Download diagnostics** (JSON) from Settings → Devices & Services → Fritz!Box VPN → ⋮. Passwords are redacted; host and VPN names are not. Redact VPN names if they should not be public.
        5. You may paste a **redacted debug excerpt as text** (Enable debug logging → reproduce → Disable debug logging → copy relevant lines only). Do not attach that download as a `.log` file.
        6. Never post Fritz!Box passwords, Home Assistant secrets, session cookies, WireGuard private keys, PSKs, public or private keys, OTP, or unnecessary login names.

        Allowed after redaction: integration error messages, HTTP status without query secrets, Home Assistant version, integration version, Fritz!OS, reproduction steps, diagnostics JSON, and a redacted debug excerpt as text.

        You can still drag files onto textareas. Do not attach `.log` files there either.
  - type: checkboxes
    id: searched-issues
    attributes:
      label: Existing issues
      description: Search https://github.com/rosch100/fritzbox-vpn/issues before filing.
      options:
        - label: I have searched existing issues
          required: true
  - type: input
    id: summary
    attributes:
      label: Short summary
      description: One line describing the failure.
      placeholder: VPN switch stays unavailable after Fritz!Box reboot
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected behavior
      description: What should have happened.
    validations:
      required: true
  - type: textarea
    id: actual
    attributes:
      label: Actual behavior
      description: What happened instead.
    validations:
      required: true
  - type: textarea
    id: reproduce
    attributes:
      label: Steps to reproduce
      description: Numbered steps another person can follow.
      value: |
        1.
        2.
        3.
    validations:
      required: true
  - type: input
    id: ha-version
    attributes:
      label: Home Assistant version
      description: Core version from Settings → About (for example 2026.9.0).
      placeholder: "2026.9.0"
    validations:
      required: true
  - type: dropdown
    id: ha-install-type
    attributes:
      label: HA installation type
      options:
        - Home Assistant OS
        - Container
        - Core
        - Supervised
        - unclear
    validations:
      required: true
  - type: input
    id: integration-version
    attributes:
      label: Integration version
      description: Version string only (for example 1.2.7). Source is the Install source field.
      placeholder: "1.2.7"
    validations:
      required: true
  - type: dropdown
    id: install-source
    attributes:
      label: Install source
      options:
        - HACS
        - manual
        - Beta/pre-release
        - unclear
    validations:
      required: true
  - type: input
    id: fritzbox
    attributes:
      label: Fritz!Box model and Fritz!OS
      description: For example 7590 AX, Fritz!OS 8.20.
      placeholder: 7590 AX, Fritz!OS 8.20
    validations:
      required: true
  - type: dropdown
    id: setup
    attributes:
      label: Setup
      options:
        - SSDP/discovery
        - credentials from Fritz!Box Tools
        - manual
        - unclear
    validations:
      required: true
  - type: dropdown
    id: availability-mode
    attributes:
      label: Availability mode
      description: Integration option. Use unclear if you did not change it.
      options:
        - Graceful
        - Strict
        - Persistent
        - unclear
    validations:
      required: false
  - type: upload
    id: diagnostics-json
    attributes:
      label: Diagnostics JSON
      description: Settings → Devices & Services → Fritz!Box VPN → ⋮ → Download diagnostics. Redact VPN names if they should not be public. JSON only.
    validations:
      required: false
      accept: ".json"
  - type: textarea
    id: debug-excerpt
    attributes:
      label: Redacted debug log excerpt
      description: Paste relevant lines only. Do not upload a `.log` file.
      render: shell
    validations:
      required: false
  - type: checkboxes
    id: confirm-no-secrets
    attributes:
      label: No secrets
      options:
        - label: I am not posting passwords, cookies, OTP, WireGuard keys, PSKs, or other secrets
          required: true
  - type: checkboxes
    id: confirm-no-log
    attributes:
      label: No log files
      options:
        - label: I am not attaching a `.log` file or a full home-assistant.log
          required: true
  - type: checkboxes
    id: confirm-redacted
    attributes:
      label: Redaction
      options:
        - label: I have redacted VPN names and other personal data where needed
          required: true
```

- [ ] **Step 4: Write `feature_request.yml`**

Create `.github/ISSUE_TEMPLATE/feature_request.yml` with exactly:

```yaml
name: Feature request
description: Suggest an enhancement for Fritz!Box VPN
title: "[Feature]: "
labels: [enhancement]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for the idea.

        Do not include logs, credentials, personal example data, or WireGuard key material.
  - type: checkboxes
    id: searched-issues
    attributes:
      label: Existing issues
      description: Search https://github.com/rosch100/fritzbox-vpn/issues before filing.
      options:
        - label: I have searched existing issues
          required: true
  - type: textarea
    id: problem
    attributes:
      label: Problem / motivation
      description: What is missing or painful today.
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: Proposed solution
      description: What you would like the integration to do.
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives
      description: Other approaches you considered.
    validations:
      required: false
  - type: dropdown
    id: affected-flow
    attributes:
      label: Affected flow
      options:
        - Setup/SSDP
        - Switch (VPN on/off)
        - Status/Connected
        - Availability/recovery
        - Options/services
        - Core/PyPI
        - Other
    validations:
      required: false
  - type: checkboxes
    id: confirm-no-secrets
    attributes:
      label: No credentials or personal examples
      options:
        - label: I am not posting credentials, personal example data, or key material
          required: true
```

- [ ] **Step 5: Write maintainer README**

Create `docs/issue-templates/README.md` with exactly:

```markdown
# Issue templates

SSOT for GitHub Issue Forms: `.github/ISSUE_TEMPLATE/`
(`bug_report.yml`, `feature_request.yml`, `config.yml`).

English only. Do not add a German form set. Change the YAML in this repo;
there is no sync script.

## Maintainer reply (secrets or log files)

If a reporter attaches a full `home-assistant.log`, a `.log` file, a backup,
or secrets:

1. Comment on the issue in English:

   The attachment is too broad or likely contains secrets. Please use
   **Download diagnostics** (JSON) and/or a redacted debug excerpt as text.
   Do not attach `home-assistant.log` or `.log` files.

2. Ask the reporter to remove the attachment or clean the issue.

3. Do not redistribute the attachment.

## Labels

Forms apply `bug` and `enhancement`. Those labels must already exist
(`gh label list --repo rosch100/fritzbox-vpn`). GitHub does not create
missing labels from the form YAML.
```

- [ ] **Step 6: Mark the design spec approved**

In `docs/superpowers/specs/2026-09-20-github-issue-templates-design.md`, replace the status block:

```markdown
Status: **Entwurf** (an MoneyMoney-Spec 2026-09-06 angelehnt);
Conformity-Remediation 2026-09-20; Sprache nur Englisch 2026-09-20
```

with:

```markdown
Status: **Design freigegeben**; Conformity-Remediation 2026-09-20;
Sprache nur Englisch 2026-09-20
```

- [ ] **Step 7: Parse YAML and reject German umlauts**

Run from repo root (PyYAML is available via the Home Assistant test venv):

```bash
.venv/bin/python -c "
from pathlib import Path
import yaml
root = Path('.github/ISSUE_TEMPLATE')
forbidden = set('äöüÄÖÜß')
ids_bug = set()
for name in ('config.yml', 'bug_report.yml', 'feature_request.yml'):
    path = root / name
    text = path.read_text(encoding='utf-8')
    assert not text.startswith('\ufeff'), path
    hits = sorted(ch for ch in forbidden if ch in text)
    assert not hits, (path, hits)
    data = yaml.safe_load(text)
    assert data is not None, path
cfg = yaml.safe_load((root / 'config.yml').read_text(encoding='utf-8'))
assert cfg['blank_issues_enabled'] is False
assert len(cfg['contact_links']) == 1
assert cfg['contact_links'][0]['name'] == 'Documentation'
assert 'README.de.md' not in cfg['contact_links'][0]['url']
bug = yaml.safe_load((root / 'bug_report.yml').read_text(encoding='utf-8'))
assert bug['labels'] == ['bug']
assert bug['title'] == '[Bug]: '
feat = yaml.safe_load((root / 'feature_request.yml').read_text(encoding='utf-8'))
assert feat['labels'] == ['enhancement']
assert feat['title'] == '[Feature]: '
upload = [item for item in bug['body'] if item.get('type') == 'upload']
assert len(upload) == 1
assert upload[0]['validations']['accept'] == '.json'
assert upload[0]['validations'].get('required') is False
assert '.log' not in upload[0]['validations']['accept']
print('issue templates ok')
"
```

Expected stdout: `issue templates ok`

If `.venv` is missing, create it first with `python3.14 -m venv .venv` and ` .venv/bin/pip install -r scripts/requirements-test.txt`, then rerun.

- [ ] **Step 8: Whitespace check**

```bash
git diff --check
```

Expected: no output, exit 0.

- [ ] **Step 9: Commit**

```bash
git add .github/ISSUE_TEMPLATE/config.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml \
  .github/ISSUE_TEMPLATE/feature_request.yml \
  docs/issue-templates/README.md \
  docs/superpowers/specs/2026-09-20-github-issue-templates-design.md
git commit -m "docs: add English GitHub issue forms"
```

---

### Task 2: Verify GitHub labels `bug` and `enhancement`

**Files:**
- None in git (remote GitHub labels only)

**Interfaces:**
- Consumes: form `labels: [bug]` and `labels: [enhancement]` from Task 1
- Produces: both labels present on `rosch100/fritzbox-vpn`

- [ ] **Step 1: List labels**

```bash
gh label list --repo rosch100/fritzbox-vpn --limit 50
```

Expected: lines containing `bug` and `enhancement`.

- [ ] **Step 2: Create a missing label (only if Step 1 did not list it)**

If `bug` is missing:

```bash
gh label create bug --repo rosch100/fritzbox-vpn --description "Something isn't working" --color d73a4a
```

If `enhancement` is missing:

```bash
gh label create enhancement --repo rosch100/fritzbox-vpn --description "New feature or request" --color a2eeef
```

If both already exist, skip this step.

- [ ] **Step 3: Re-list to confirm**

```bash
gh label list --repo rosch100/fritzbox-vpn --json name --jq '.[].name' | grep -x bug
gh label list --repo rosch100/fritzbox-vpn --json name --jq '.[].name' | grep -x enhancement
```

Expected: `bug` then `enhancement`, both exit 0.

No git commit (no tracked files).

---

### Task 3: README Support, Diagnostics, and debug logging

**Files:**
- Modify: `README.md` (sections `## Diagnostics`, `## Support`, `### Debug logging`)
- Modify: `README.de.md` (sections `## Diagnose`, `## Unterstützung`, `### Debug-Logging`)

**Interfaces:**
- Consumes: chooser URL `https://github.com/rosch100/fritzbox-vpn/issues/new/choose`; diagnostics JSON preferred; no `home-assistant.log` / `.log` attachments
- Produces: bilingual user docs that do not contradict the English forms

- [ ] **Step 1: Update English Diagnostics**

In `README.md`, replace:

```markdown
Under **Settings → Devices & Services → Fritz!Box VPN → ⋮ → Download diagnostics** you get a redacted JSON report (no passwords): host, update interval, VPN count, and per-connection names/status.
```

with:

```markdown
Under **Settings → Devices & Services → Fritz!Box VPN → ⋮ → Download diagnostics** you get a JSON report without passwords: host, update interval, VPN count, and per-connection names/status. Attach that JSON on a [GitHub bug report](https://github.com/rosch100/fritzbox-vpn/issues/new/choose). Redact VPN names if they should not be public. Do not attach `home-assistant.log`.
```

- [ ] **Step 2: Update English Support and debug logging**

In `README.md`, replace the `## Support` section through the end of `### Debug logging` (stop before `## Buy me a coffee`) with:

```markdown
## Support

For problems or ideas, open a [GitHub issue](https://github.com/rosch100/fritzbox-vpn/issues/new/choose) (Bug report or Feature request). Prefer **Download diagnostics** over Home Assistant log files (see below).

### Debug logging

1. Open the integration page: **Settings → Devices & Services → Fritz!Box VPN**.
2. Open the **options menu (⋮)** (top right) and select **Enable debug logging**.
3. Click **Reload** so the next update uses the new log level.
4. Reproduce the issue (or wait for the next update).
5. Select **Disable debug logging**. Home Assistant may download a log file — **do not attach that file** to the GitHub issue.
6. Paste a **redacted excerpt** (relevant lines only) into the bug form. Prefer **Download diagnostics** (JSON) on the same menu.
7. Do **not** use **Settings → System → Logs → Download** (`home-assistant.log`).
```

- [ ] **Step 3: Update German Diagnose**

In `README.de.md`, replace:

```markdown
Unter **Einstellungen → Geräte & Dienste → Fritz!Box VPN → ⋮ → Diagnose herunterladen** erhältst du eine JSON-Datei ohne Passwörter: Host, Intervall, Anzahl VPNs, Namen/Status je Verbindung.
```

with:

```markdown
Unter **Einstellungen → Geräte & Dienste → Fritz!Box VPN → ⋮ → Diagnose herunterladen** erhältst du eine JSON-Datei ohne Passwörter: Host, Intervall, Anzahl VPNs, Namen/Status je Verbindung. Diese JSON kannst du einem [GitHub-Bug-Report](https://github.com/rosch100/fritzbox-vpn/issues/new/choose) anhängen (Formulare sind auf Englisch). VPN-Namen bei Bedarf schwärzen. Nicht `home-assistant.log` anhängen.
```

- [ ] **Step 4: Update German Unterstützung and Debug-Logging**

In `README.de.md`, replace the `## Unterstützung` section through the end of `### Debug-Logging` (stop before `## Buy me a coffee`) with:

```markdown
## Unterstützung

Bei Problemen oder Ideen öffne ein [GitHub-Issue](https://github.com/rosch100/fritzbox-vpn/issues/new/choose) (Bug report oder Feature request; Formulare auf Englisch). Bevorzuge **Diagnose herunterladen** gegenüber Home-Assistant-Logdateien (siehe unten).

### Debug-Logging

1. Öffne die Integrationsseite: **Einstellungen → Geräte & Dienste → Fritz!Box VPN**.
2. Öffne das **Optionsmenü (⋮)** (oben rechts) und wähle **Enable debug logging**.
3. Klicke **Neu laden**, damit das nächste Update den neuen Log-Level nutzt.
4. Reproduziere das Problem (oder warte auf das nächste Update).
5. Wähle **Disable debug logging**. Home Assistant bietet ggf. einen Log-Download an — **diese Datei nicht** an das GitHub-Issue anhängen.
6. Füge einen **redigierten Ausschnitt** (nur relevante Zeilen) als Text in das Bug-Formular ein. Bevorzuge **Diagnose herunterladen** (JSON) im selben Menü.
7. **Nicht** unter **Einstellungen → System → Logs → Download** die `home-assistant.log` verwenden.
```

- [ ] **Step 5: Confirm old issue URL and log-attach wording are gone**

```bash
grep -n 'fritzbox-vpn/issues)' README.md README.de.md
grep -n 'home-assistant.log' README.md README.de.md
grep -n 'Attach the downloaded log' README.md
grep -n 'Hänge das Log' README.de.md
```

Expected:

- First `grep`: no matches (links must be `issues/new/choose`, not `/issues)`).
- Second `grep`: matches only in the new “do not attach / nicht anhängen” sentences.
- Third and fourth `grep`: no matches.

- [ ] **Step 6: Whitespace check**

```bash
git diff --check -- README.md README.de.md
```

Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add README.md README.de.md
git commit -m "docs: point support at issue forms and diagnostics JSON"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
| --- | --- |
| `bug_report.yml` / `feature_request.yml` / `config.yml` | 1 |
| `docs/issue-templates/README.md` maintainer reply | 1 |
| English only; no DE form set; no DE contact link | 1 (YAML + umlaut check) |
| Diagnostics JSON `upload` `.json`; no `.log` accept | 1 |
| Bug fields, confirmations, availability mode, install source vs version | 1 |
| Feature fields + no-secrets checkbox | 1 |
| Labels `bug` / `enhancement` | 2 |
| README EN+DE chooser link; no attach `home-assistant.log` | 3 |
| No `diagnostics.py` / CI / hub sync | not in plan (non-goals) |

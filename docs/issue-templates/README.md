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
   **Download diagnostics** (JSON, drag-and-drop) and/or paste a useful
   log excerpt as text. Do not attach `home-assistant.log` or `.log` files.

2. Ask the reporter to remove the attachment or clean the issue.

3. Do not redistribute the attachment.

## Labels

Forms apply `bug` and `enhancement`. Those labels must already exist
(`gh label list --repo rosch100/fritzbox-vpn`). GitHub does not create
missing labels from the form YAML.

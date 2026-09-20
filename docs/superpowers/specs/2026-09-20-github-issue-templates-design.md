# GitHub Issue Templates für fritzbox-vpn

Datum: 2026-09-20

Status: **Design freigegeben**; Conformity-Remediation 2026-09-20;
Sprache nur Englisch 2026-09-20

Quelle: Design *GitHub Issue Templates für MoneyMoney-Plugins*
(2026-09-06). Liegt nicht in diesem Repo; lokal z. B. unter
`/Users/roschmac/Entwicklung/MoneyMoney/docs/superpowers/specs/2026-09-06-github-issue-templates-design.md`.

## Ziel

Im Repo [rosch100/fritzbox-vpn](https://github.com/rosch100/fritzbox-vpn)
**ausschließlich englischsprachige** GitHub Issue Forms (Bug + Feature)
bereitstellen. Melder werden zu Home-Assistant- und Fritz!Box-VPN-
relevanten Angaben geführt. Diagnose ist explizit und nach Best Practice
geregelt:

- bevorzugte Quelle ist die **HA diagnostics JSON** (Passwörter werden von
  `diagnostics.py` redigiert; Host und VPN-Namen stehen unredigiert in
  der Datei und müssen bei Bedarf vom Melder geschwärzt werden);
- der **integration debug log** (Download über das ⋮-Menü der
  Integration) darf als **redigierter Textausschnitt** ins Formular;
- das vollständige `home-assistant.log`, `.log`-Datei-Uploads,
  Fritz!Box-Backups und WireGuard-Schlüsselmaterial sind verboten.

## Entscheidungen (fest)

| Thema | Wahl |
| --- | --- |
| Issue-Arten | Bug-Report + Feature-Request |
| Ablage | `.github/ISSUE_TEMPLATE/` im Repo (SSOT; kein Hub, kein Sync) |
| Pflege | YAML im Repo; knappe Maintainer-Antwortvorlage unter `docs/issue-templates/` |
| Sprache | Nur Englisch (Forms, Chooser, Maintainer-Vorlage) |
| Form | GitHub Issue Forms (YAML), inkl. `upload` für diagnostics JSON |
| Diagnose | Diagnostics JSON bevorzugt (Upload `.json`); Debug-Ausschnitt als Text; kein `.log`-Upload, kein vollständiges `home-assistant.log` |

## Sprache

GitHub Issue Forms haben keine Locale. **Ein** Formular-Set, **nur
Englisch**. Keine deutsche Übersetzung in YAML, Markdown, `description`,
Checkbox-Labels oder Contact-Links.

| Schicht | Sprache |
| --- | --- |
| `name`, `description`, `title`-Prefix | Englisch |
| Feld-`label`, Dropdown-Optionen, Checkbox-`label` | Englisch |
| Markdown (privacy, diagnostics), Feld-`description` | Englisch |
| `config.yml` Contact-Links (`name`, `about`) | Englisch |
| Maintainer-Antwortvorlage | Englisch |
| `README.md` | Englisch (bestehende Nutzer-Doku) |
| `README.de.md` | Deutsch (bestehende Nutzer-Doku; kein Text in den Forms) |

`README.de.md` bleibt die deutsche Nutzer-Dokumentation und verlinkt
den englischen Issue-Chooser. Die Forms selbst enthalten keinen
deutschen Text.

## Abweichungen von der MoneyMoney-Spec

| MoneyMoney | fritzbox-vpn | Grund |
| --- | --- | --- |
| Acht Plugin-Repos + Hub-SSOT + Sync-Skript | Ein Repo; YAML liegt direkt unter `.github/ISSUE_TEMPLATE/` | Kein Hub; Sync wäre YAGNI |
| Hub ohne eigene Issue-Templates | Entfällt | — |
| MoneyMoney-Protokollfenster; keine Logdateien | HA diagnostics JSON-Upload + redigierter Debug-Text; `.log`-Uploads und vollständiges `home-assistant.log` verboten | HA-Debug-Download ist auswertbar und integrationsbezogen; das App-Log von MoneyMoney war für Maintainer unlesbar |
| MoneyMoney-/Extension-/macOS-Version, Auth-Weg | HA version, HA installation type, integration version, install source, Fritz!OS/model, setup path, availability mode | Anderer Stack |
| Labels in acht Repos anlegen | Labels `bug` und `enhancement` existieren bereits | Nur prüfen, nicht neu anlegen |
| README-Link nur in Plugin-READMEs | Bestehende Abschnitte `Support` / `Unterstützung` in `README.md` und `README.de.md` | Nutzer-Doku bleibt zweisprachig; Forms nicht |
| Forms nur Deutsch | Forms nur Englisch | HA-Community und bestehende Issues sind überwiegend Englisch |
| Contact-Link zum Hub | Ein Contact-Link auf `README.md` (Englisch) | Kein Hub; Chooser ohne deutschen Text |
| Diagnose-Hinweis als textarea | Diagnostics JSON als GitHub-`upload` (`accept: ".json"`) | Aktuelle Form-API (Changelog 2026-03-05); kein Textarea-Workaround für Dateien |

## Scope

### Repo

- [fritzbox-vpn](https://github.com/rosch100/fritzbox-vpn) (Custom Integration
  + Library `fritzboxvpn/`)

### Nicht-Ziele

- Support-/Frage-Template
- Deutscher Text in Forms, Chooser oder Maintainer-Vorlage
- Zweites Formular-Set (`bug_report_de.yml` / `feature_request_de.yml`)
- Locale-Switch oder GitHub-I18n
- Hub, Sync-Skript, Spiegelung in andere Repos
- Issue-Templates für Home Assistant Core oder `home-assistant.io`
- CI, Label-Bots, Issue-Forms-Validierung außerhalb GitHub
- Änderung der Logging-Implementierung oder von `diagnostics.py`
- Blank Issues für Contributor beibehalten (werden für Read/Triage
  ausgeschaltet; Maintainer sehen GitHub-seitig weiter „Blank issue
  (Maintainers only)“)
- `.log` im `upload`-`accept` (würde `home-assistant.log` einladen)
- Contact-Link auf `README.de.md` im Issue-Chooser

## Dateistruktur

### SSOT im Repo

| Datei | Zweck |
| --- | --- |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Bug-Form (Englisch) |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Feature-Form (Englisch) |
| `.github/ISSUE_TEMPLATE/config.yml` | Template-Auswahl; Blank Issues für Contributor aus |
| `docs/issue-templates/README.md` | Pflege, Maintainer-Antwortvorlage (Englisch) |

Die YAML-Dateien sind die produktive SSOT. Die Maintainer-README wird
**nicht** von GitHub als Issue-Template angezeigt und braucht keinen
Link aus der Nutzer-README.

### GitHub-Form-Constraints

- Jedes Body-Element außer `markdown` hat eine eindeutige `id`
  (nur `A–Z`/`a–z`/`0–9`/`-`/`_`).
- Pflicht-Checkboxen über `options[].required: true` (nicht nur
  `validations.required` am Block).
- YAML UTF-8 ohne BOM.
- `upload` nur für diagnostics JSON: `validations.accept: ".json"`, nicht required.
- Kein deutscher Text in `name`, `description`, `label`, `options`,
  Markdown oder Contact-Links.

### Kein Sync

Ein Sync-Skript entfällt. Änderungen an den Forms erfolgen direkt im
gleichen Repo und denselben PRs wie die übrige Doku.

## README (EN + DE)

Keine neue Überschrift. Die bestehenden Abschnitte `## Support`
(`README.md`) und `## Unterstützung` (`README.de.md`) anpassen —
jeweils in der Sprache der Datei:

- Issue-Link von `https://github.com/rosch100/fritzbox-vpn/issues` auf
  `https://github.com/rosch100/fritzbox-vpn/issues/new/choose`.
- Debug-Logging-Absätze an die Diagnose-Regeln dieses Specs anpassen:

  1. Diagnostics JSON herunterladen und im Bug-Form-Upload anhängen
     (bevorzugt; VPN-Namen bei Bedarf schwärzen).
  2. Optional Integrations-Debug-Log über ⋮ → Enable debug logging,
     reproduzieren, Debug-Logging wieder aus. Nur einen **redigierten
     Ausschnitt als Text** ins Formular, keine `.log`-Datei anhängen.
  3. **Nicht** `home-assistant.log` (System → Logs → Download) anhängen.
  4. Kein langer Datenschutz-Text in der README (Detail steht im
     englischen Bug-Template).

Der Abschnitt `## Diagnostics` / `## Diagnose` in beiden READMEs bleibt;
er beschreibt denselben JSON-Download und darf den Issue-Form-Upload
kurz erwähnen, ohne die Regeln zu widersprechen.

## Datenschutz & Logs (Best Practice)

### Hintergrund

Home Assistant bietet zwei integrationsbezogene Diagnosewege:

1. **Download diagnostics** (⋮ auf der Integrationskarte): JSON.
   `diagnostics.py` redigiert `username`/`password` (und Alias-Keys).
   Unredigiert bleiben u. a. Host, Intervall, Verfügbarkeitsmodus,
   VPN-Namen und Status. VPN-Namen können personenbezogen sein
   (z. B. Vornamen) und müssen vom Melder geschwärzt werden, wenn sie
   nicht öffentlich sein sollen.
2. **Enable debug logging** auf derselben Karte: HA setzt Debug für die
   Integrations-Logger (`custom_components.fritzbox_vpn` bzw. Paketpfad
   plus Manifest-`loggers`, hier `fritzboxvpn`). Nach **Disable debug
   logging** bietet HA einen Download an. Das ist **nicht** das
   vollständige `home-assistant.log`. Der Download darf **nicht** als
   Datei ins Issue; nur ein geprüfter Textausschnitt.

Das vollständige `home-assistant.log` (Settings → System → Logs →
Download) enthält Logs **aller** Integrationen, Recorder-Details und oft
Secrets. Anhängen ist verboten.

Unabhängig vom Dateiformat: **keine** Fritz!Box-Backups, keine
WireGuard-Konfigurationen, keine Private Keys, PSKs oder sonstiges
Schlüsselmaterial, keine HA-`.storage`-Dumps, keine `configuration.yaml`
mit Passwörtern, keine HAR-/LocalStorage-Dumps.

### Regeln für Melder (im Bug-Template sichtbar, nur Englisch)

1. Do not attach a full `home-assistant.log`.
2. Do not upload `.log` files (including the integration debug download).
3. Do not attach Fritz!Box backups, WireGuard `.conf`, or
   `.storage`/HAR/LocalStorage dumps.
4. Instead: HA diagnostics JSON (upload field; redact VPN names if needed)
   and/or a redacted debug excerpt as text.
5. Never post: Fritz!Box passwords, HA secrets, session cookies,
   WireGuard private keys, PSKs, public or private keys, OTP, unnecessary
   login names.
6. Allowed after redaction: integration errors, HTTP status without query
   secrets, HA version, integration version, Fritz!OS, reproduction steps,
   diagnostics JSON, redacted debug excerpt as text.

### Feature-Template

Short English markdown: no logs, no credentials, no personal example
data, no key material.
Required checkbox (English label): no credentials, no personal examples,
no keys.

### Maintainer-Antwortvorlage (Pflichtinhalt der `docs/issue-templates/README.md`)

Nur Englisch. Öffentliche Issue-Kommentare auf Englisch.

Wenn trotz Hinweis ein vollständiges `home-assistant.log`, eine
`.log`-Datei, ein Backup oder Secrets angehängt werden:

1. Comment on the issue: the attachment is too broad or likely contains
   secrets; please use diagnostics JSON or a redacted debug excerpt as
   text.
2. Ask the reporter to remove the attachment or clean the issue.
3. Do not redistribute the attachment.

## Bug-Formular (`bug_report.yml`)

Form-Metadaten (GitHub-Pflicht): `name`, `description`, `title` (Prefix
`"[Bug]: "`), `labels: [bug]`, `body`. Alle sichtbaren Strings Englisch.

| Element | Typ | Pflicht |
| --- | --- | --- |
| Privacy / log notice | markdown | — |
| Searched existing issues | checkboxes | ja |
| Short summary | input | ja |
| Expected behavior | textarea | ja |
| Actual behavior | textarea | ja |
| Steps to reproduce | textarea | ja |
| Home Assistant version | input | ja |
| HA installation type | dropdown: Home Assistant OS, Container, Core, Supervised, unclear | ja |
| Integration version | input | ja |
| Install source | dropdown: HACS, manual, Beta/pre-release, unclear | ja |
| Fritz!Box model and Fritz!OS | input | ja |
| Setup | dropdown: SSDP/discovery, credentials from Fritz!Box Tools, manual, unclear | ja |
| Availability mode | dropdown: Graceful, Strict, Persistent, unclear | nein |
| Diagnostics JSON | upload, `accept: ".json"` | nein |
| Redacted debug log excerpt | textarea, `render: shell` | nein |
| Confirmation: no secrets / no key material | checkboxes | ja |
| Confirmation: no `.log` file and no full `home-assistant.log` | checkboxes | ja |
| Confirmation: content redacted (including VPN names if needed) | checkboxes | ja |

`Integration version` is the version string only (e.g. `1.2.7`).
Origin is exclusively the `Install source` dropdown.

### Labels

Die Forms setzen `labels: [bug]` bzw. `labels: [enhancement]`. Beide
Labels existieren bereits im Repo. Vor dem Merge der Templates einmal
prüfen (`gh label list`). Fehlt ein Label, legt GitHub es **nicht**
automatisch an (Issue ohne Label). Keine alternative „ohne Labels“-
Variante — eine Policy, keine Verzweigung.

## Feature-Formular (`feature_request.yml`)

Form-Metadaten: `name`, `description`, `title` (Prefix `"[Feature]: "`),
`labels: [enhancement]`, `body`. Alle sichtbaren Strings Englisch.

| Element | Typ | Pflicht |
| --- | --- | --- |
| Privacy short notice | markdown | — |
| Searched existing issues | checkboxes | ja |
| Problem / motivation | textarea | ja |
| Proposed solution | textarea | ja |
| Alternatives | textarea | nein |
| Affected flow | dropdown: Setup/SSDP, Switch (VPN on/off), Status/Connected, Availability/recovery, Options/services, Core/PyPI, Other | nein |
| No credentials / no personal examples / no keys | checkboxes | ja |

## `config.yml`

```yaml
blank_issues_enabled: false
contact_links:
  - name: Documentation
    url: https://github.com/rosch100/fritzbox-vpn/blob/main/README.md
    about: Installation, configuration, troubleshooting
```

`blank_issues_enabled: false` blendet Blank Issues für Read/Triage aus.
Rollen Write/Maintain/Admin sehen weiter „Blank issue (Maintainers only)“.
Akzeptanzkriterium „Blank Issues aus“ meint die Contributor-Ansicht.

## Akzeptanzkriterien

1. Repo enthält `.github/ISSUE_TEMPLATE/{bug_report,feature_request,config}.yml`
   und `docs/issue-templates/README.md` (inkl. englischer
   Maintainer-Antwortvorlage).
2. „New issue“ zeigt Bug- und Feature-Form auf Englisch; Blank Issues
   sind in der Contributor-Ansicht aus; ein Contact-Link auf README.md.
3. Bug-Form nennt explizit auf Englisch: diagnostics JSON bevorzugt
   (`upload` `.json`); debug only as redacted text; no `.log` uploads;
   full `home-assistant.log` forbidden; no secrets, backups, or key
   material.
4. Alle sichtbaren Form-/Chooser-Strings sind Englisch. Kein deutscher
   Text in YAML/Markdown/`description`. Kein zweites YAML-Set.
5. `README.md` (`## Support`) und `README.de.md` (`## Unterstützung`)
   verlinken auf `issues/new/choose` und widersprechen den
   Diagnose-Regeln nicht (kein „attach `home-assistant.log` / debug log
   file“).
6. Labels `bug` und `enhancement` existieren (bereits erfüllt; vor Merge
   verifizieren).
7. Keine Secrets oder Klartext-Beispiele mit echten Credentials in den
   Templates.
8. Bug-Form trennt Integration version (input) und Install source
   (dropdown); enthält HA installation type; diagnostics JSON is
   `upload`, not textarea.

## Risiken

| Risiko | Mitigation |
| --- | --- |
| Melder hängen trotzdem `home-assistant.log` oder `.log` an | English template text, kein `.log` in `accept`; Maintainer-Antwortvorlage; README-Debug-Abschnitt anpassen |
| VPN-Namen in der Diagnose-JSON sind personenbezogen | Template + Upload-Beschreibung: redact names if they should not be public |
| README (EN/DE) driftet von den Forms | Beide READMEs im selben PR wie die YAML ändern; bestehende Support-Abschnitte, keine parallele Überschrift |
| Deutschsprachige Melder ohne DE-Forms | Bewusste Wahl; `README.de.md` erklärt den Chooser auf Deutsch, Forms bleiben Englisch |
| Blank Issues bleiben für Maintainer sichtbar | Dokumentiertes GitHub-Verhalten; Contributor sehen nur die Forms |
| Textarea erlaubt trotzdem Drag-and-Drop von Dateien | Markdown-Verbot + Pflicht-Checkbox „no `.log` file“ |

## Umsetzungsreihenfolge (für Plan)

1. YAML unter `.github/ISSUE_TEMPLATE/` und `docs/issue-templates/README.md`
   anlegen (nur Englisch)
2. Labels `bug` / `enhancement` prüfen
3. Abschnitte `Support` / `Unterstützung` und Debug-Logging in
   `README.md` und `README.de.md` anpassen (Link `issues/new/choose`,
   Diagnose-Regeln, jeweilige Dateisprache)

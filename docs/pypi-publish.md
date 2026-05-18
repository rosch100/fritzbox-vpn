# PyPI publish setup for `fritzboxvpn`

The Home Assistant Core integration depends on the library on PyPI (`fritzboxvpn==…` in `manifest.json`). This workflow publishes from `fritzboxvpn/pyproject.toml` when a tag `v*` is pushed or when triggered manually.

## 1. Version bump

Before a release, set the library version in `fritzboxvpn/pyproject.toml` and the pinned requirement in:

- `custom_components/fritzbox_vpn/manifest.json`
- `home-assistant-core` `manifest.json` / `requirements_all.txt` (Core PR)

Integration version (`manifest.json` `"version"`) and library version (`pyproject.toml`) are independent; only the **library** version is uploaded to PyPI.

## 2. Authentication (choose one)

### Option A — Trusted publishing (recommended)

1. Log in at [pypi.org](https://pypi.org/).
2. Open **[Account → Publishing](https://pypi.org/manage/account/publishing/)**.
3. **Add a new pending publisher** (works before the project exists):

   | Field | Value |
   |--------|--------|
   | PyPI project name | `fritzboxvpn` |
   | Owner | `rosch100` |
   | Repository name | `fritzbox-vpn` |
   | Workflow name | `publish-pypi.yml` |
   | Environment name | `pypi` |

   Names must match **exactly** (case-sensitive). The GitHub environment `pypi` already exists in this repo.

4. Run **Actions → Publish fritzboxvpn to PyPI → Run workflow** with `confirm=publish`, or push a tag `v*`.

On first successful upload, PyPI creates the project and activates the publisher.

### Option B — API token (quick alternative)

1. PyPI → **Account settings → API tokens** → create a token scoped to `fritzboxvpn` (or entire account for first upload).
2. GitHub → **Settings → Environments → pypi → Environment secrets** → add:

   | Name | Value |
   |------|--------|
   | `PYPI_API_TOKEN` | `pypi-…` (the token; username is always `__token__`) |

3. Re-run the publish workflow. When `PYPI_API_TOKEN` is set, the workflow uses the token instead of OIDC.

## 3. Manual publish (local)

```bash
cd fritzboxvpn
python -m pip install --upgrade build twine
python -m build
twine check dist/*
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-… twine upload dist/*
```

## 4. Verify

```bash
python -m pip index versions fritzboxvpn
python -m pip install "fritzboxvpn==1.0.0"
```

## Troubleshooting

| Error | Cause | Fix |
|--------|--------|-----|
| `invalid-publisher`: no corresponding publisher | Trusted publisher not configured on PyPI | Complete [Option A](#option-a--trusted-publishing-recommended) |
| `invalid-publisher` but publisher looks correct | Typo in repo/workflow/environment name | Compare with workflow log claims (`repository`, `workflow_ref`, `environment`) |
| **403 / invalid token** | Wrong or missing API token | [Option B](#option-b--api-token-quick-alternative) |
| **File already exists** | Version already on PyPI | Bump `version` in `fritzboxvpn/pyproject.toml` |
| **Core CI cannot install** | Pin mismatch | Published version must match `manifest.json` `requirements` |

### Claims from a failed run (for debugging)

If trusted publishing fails, the workflow log lists OIDC claims, e.g.:

```
sub: repo:rosch100/fritzbox-vpn:environment:pypi
repository: rosch100/fritzbox-vpn
workflow_ref: rosch100/fritzbox-vpn/.github/workflows/publish-pypi.yml@refs/heads/main
environment: pypi
```

Use these values when configuring the pending publisher on PyPI.

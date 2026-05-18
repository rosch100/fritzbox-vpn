# PyPI publish setup for `fritzboxvpn`

The Home Assistant Core integration depends on the library on PyPI (`fritzboxvpn==…` in `manifest.json`). This workflow publishes from `fritzboxvpn/pyproject.toml` when a tag `v*` is pushed or when triggered manually.

## 1. Version bump

Before a release, set the library version in `fritzboxvpn/pyproject.toml` and the pinned requirement in:

- `custom_components/fritzbox_vpn/manifest.json`
- `home-assistant-core` `manifest.json` / `requirements_all.txt` (Core PR)

Integration version (`manifest.json` `"version"`) and library version (`pyproject.toml`) are independent; only the **library** version is uploaded to PyPI.

## 2. Trusted publishing (recommended)

1. Register the project on [PyPI](https://pypi.org/) as `fritzboxvpn` (if not already).
2. PyPI → **Publishing** → **Add a new pending publisher**:
   - PyPI project name: `fritzboxvpn`
   - Owner: `rosch100`
   - Repository: `fritzbox-vpn`
   - Workflow name: `publish-pypi.yml`
   - Environment name: `pypi`
3. GitHub → repository **Settings** → **Environments** → create **`pypi`** (optional: required reviewers for manual runs only).

On tag push (e.g. `v1.2.0`) or **Actions → Publish fritzboxvpn to PyPI → Run workflow** (confirm with `publish`), the workflow builds and uploads `fritzboxvpn/dist/*`.

## 3. Manual publish (local)

```bash
cd fritzboxvpn
python -m pip install --upgrade build twine
python -m build
twine check dist/*
twine upload dist/*   # needs PyPI token or trusted environment
```

## 4. Verify

```bash
python -m pip index versions fritzboxvpn
python -m pip install "fritzboxvpn==1.0.0"
```

## Troubleshooting

| Issue | Action |
|--------|--------|
| **403 / invalid token** | Check trusted publisher owner/repo/workflow/environment names match exactly |
| **File already exists** | Bump `version` in `fritzboxvpn/pyproject.toml`; PyPI versions are immutable |
| **Core CI cannot install** | Ensure published version matches `manifest.json` `requirements` pin |

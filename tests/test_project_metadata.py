"""Regression tests for project metadata/config files.

These guard the Python 3.14 / Home Assistant 2026.8.0 CVE-floor bump so the CI
workflow, contributor docs, and pinned test requirements cannot silently drift
out of sync with each other again.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VENV_SETUP_RE = re.compile(r"^python3\.(\d+) -m venv \.venv$", re.MULTILINE)
CI_PYTHON_VERSION_RE = re.compile(r'PYTHON_VERSION:\s*"3\.(\d+)"')


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_ci_workflow_pins_python_3_14() -> None:
    """The CI workflow builds/tests against Python 3.14."""
    content = _read(".github/workflows/ci.yml")

    match = CI_PYTHON_VERSION_RE.search(content)
    assert match is not None, "PYTHON_VERSION env var not found in ci.yml"
    assert match.group(1) == "14"


def test_copilot_instructions_venv_uses_python_3_14() -> None:
    """Copilot instructions create the venv with python3.14."""
    content = _read(".github/copilot-instructions.md")

    match = VENV_SETUP_RE.search(content)
    assert match is not None, "venv setup line not found in copilot-instructions.md"
    assert match.group(1) == "14"
    assert "python3 -m venv .venv" not in content


def test_agents_md_venv_uses_python_3_14() -> None:
    """AGENTS.md creates the venv with python3.14."""
    content = _read("AGENTS.md")

    match = VENV_SETUP_RE.search(content)
    assert match is not None, "venv setup line not found in AGENTS.md"
    assert match.group(1) == "14"
    assert "python3 -m venv .venv" not in content


def test_docs_and_ci_agree_on_python_version() -> None:
    """Docs and CI must agree on the Python minor version."""
    copilot_version = VENV_SETUP_RE.search(
        _read(".github/copilot-instructions.md")
    ).group(1)
    agents_version = VENV_SETUP_RE.search(_read("AGENTS.md")).group(1)
    ci_version = CI_PYTHON_VERSION_RE.search(
        _read(".github/workflows/ci.yml")
    ).group(1)

    assert copilot_version == agents_version == ci_version


def test_requirements_test_pins_ha_cve_floor() -> None:
    """requirements-test.txt pins Home Assistant past the 2026.8.0 CVE floor."""
    content = _read("scripts/requirements-test.txt")

    assert "homeassistant>=2026.8.0" in content
    # The previous pin capped HA below 2026.2.0; that ceiling must be gone.
    assert "<2026.2.0" not in content


def test_requirements_test_pins_pytest_homeassistant_custom_component() -> None:
    """requirements-test.txt pins pytest-homeassistant-custom-component correctly."""
    content = _read("scripts/requirements-test.txt")

    match = re.search(
        r"pytest-homeassistant-custom-component>=([\d.]+)", content
    )
    assert match is not None
    assert match.group(1) == "0.13.356"


def test_requirements_test_file_is_pip_installable_format() -> None:
    """Every non-comment, non-blank requirement line is a valid pip requirement spec."""
    content = _read("scripts/requirements-test.txt")
    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert lines, "requirements-test.txt should not be empty"
    for line in lines:
        assert line.startswith("-e ") or re.match(
            r"^[A-Za-z0-9_.-]+(\[[A-Za-z0-9,_-]+\])?(>=|==|<=|~=)[\d.]+$", line
        ), f"unexpected requirement format: {line!r}"
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from desktop_pet import __version__


ROOT = Path(__file__).resolve().parent.parent


def test_release_versions_are_consistent():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    installer = (ROOT / "installer.iss").read_text(encoding="utf-8")
    fallback = re.search(r'#define MyAppVersion "([^"]+)"', installer)

    assert __version__ == "0.4.0"
    assert project["project"]["version"] == __version__
    assert fallback is not None and fallback.group(1) == __version__


def test_release_build_names_include_version():
    build = (ROOT / "build.ps1").read_text(encoding="utf-8")
    installer = (ROOT / "installer.iss").read_text(encoding="utf-8")

    assert "FEIXUE-v$ver-windows-x64.zip" in build
    assert "SHA256SUMS.txt" in build
    assert "FEIXUESetup-{#MyAppVersion}" in installer

"""Tests for configuration."""
import re
from pathlib import Path


def test_version_format():
    """VERSION file must match MAJOR.NNN format."""
    version_path = Path(__file__).resolve().parents[1] / "VERSION"
    assert version_path.exists(), "VERSION file not found"
    version = version_path.read_text().strip()
    assert re.match(r"^\d+\.\d{3}$", version), f"VERSION '{version}' does not match MAJOR.NNN"

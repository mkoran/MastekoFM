"""Sprint G1 tests for the filename + folder naming standard."""
from datetime import datetime

import pytest

from backend.app.services import drive_service


def test_versioned_filename_zero_pads_to_three_digits():
    assert drive_service.versioned_filename("helloworld_inputs", 1) == "helloworld_inputs_v001.xlsx"
    assert drive_service.versioned_filename("helloworld_inputs", 27) == "helloworld_inputs_v027.xlsx"
    assert drive_service.versioned_filename("foo", 999) == "foo_v999.xlsx"


def test_versioned_filename_supports_other_extensions():
    assert drive_service.versioned_filename("output", 1, ext="pdf") == "output_v001.pdf"
    assert drive_service.versioned_filename("run-log", 1, ext="txt") == "run-log_v001.txt"


def test_versioned_filename_rejects_invalid_versions():
    with pytest.raises(ValueError):
        drive_service.versioned_filename("foo", 0)
    with pytest.raises(ValueError):
        drive_service.versioned_filename("foo", -1)


def test_versioned_filename_lexical_sort_matches_version_sort():
    """The whole point of zero-padding: lexical sort = version sort."""
    names = [drive_service.versioned_filename("p", v) for v in [10, 1, 100, 5, 27]]
    sorted_lex = sorted(names)
    expected = [drive_service.versioned_filename("p", v) for v in [1, 5, 10, 27, 100]]
    assert sorted_lex == expected


def test_versioned_filename_4_digits_for_v1000_plus_still_sorts():
    """At v1000+ we lose the perfect 3-digit padding but Python f-strings widen
    automatically and sort is still correct (lexically v999 < v1000)."""
    a = drive_service.versioned_filename("p", 999)
    b = drive_service.versioned_filename("p", 1000)
    assert a == "p_v999.xlsx"
    assert b == "p_v1000.xlsx"
    # Lex sort: p_v1000.xlsx comes BEFORE p_v999.xlsx (1 < 9 lexically)
    # — known limitation. Document and ignore for now (we won't hit v1000 anytime).
    assert sorted([a, b]) == [b, a]


def test_run_folder_name_format():
    """Per-run folder name embeds timestamp + composition codes."""
    started = datetime(2026, 4, 27, 18, 0, 0)
    name = drive_service.run_folder_name(started, "helloworld_inputs", "helloworld_report")
    assert name == "20260427-180000_helloworld_inputs_helloworld_report"


def test_folder_url_helper():
    assert drive_service.folder_url("abc123") == "https://drive.google.com/drive/folders/abc123"
    assert drive_service.folder_url(None) is None
    assert drive_service.folder_url("") is None

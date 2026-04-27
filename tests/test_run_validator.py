"""Tests for services/run_validator.py — three-way composition compatibility."""
from backend.app.services import run_validator


def _model(input_tabs, output_tabs):
    return {"input_tabs": input_tabs, "output_tabs": output_tabs, "m_tabs": [], "calc_tabs": []}


def _pack(input_tabs, output_tabs=None, m_tabs=None, calc_tabs=None):
    return {
        "input_tabs": input_tabs,
        "output_tabs": output_tabs or [],
        "m_tabs": m_tabs or [],
        "calc_tabs": calc_tabs or [],
    }


def _tpl(m_tabs, output_tabs=None):
    return {"m_tabs": m_tabs, "output_tabs": output_tabs or ["O_Report"]}


def test_compatible_helloworld():
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers"], ["O_Results"]),
        _pack(["I_Numbers"]),
        _tpl(["M_Results"]),
    )
    assert errors == []


def test_pack_missing_input_tab():
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers", "I_Other"], ["O_Results"]),
        _pack(["I_Numbers"]),
        _tpl(["M_Results"]),
    )
    assert any("I_Other" in e and "missing" in e for e in errors)


def test_pack_with_unexpected_calc_tab():
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers"], ["O_Results"]),
        _pack(["I_Numbers"], calc_tabs=["Calc"]),
        _tpl(["M_Results"]),
    )
    assert any("only I_ tabs" in e for e in errors)


def test_pack_with_unexpected_output_tab():
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers"], ["O_Results"]),
        _pack(["I_Numbers"], output_tabs=["O_Sneaky"]),
        _tpl(["M_Results"]),
    )
    assert any("only I_ tabs" in e for e in errors)


def test_template_requires_unprovided_output():
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers"], ["O_Results"]),
        _pack(["I_Numbers"]),
        _tpl(["M_Returns"]),  # no O_Returns in Model
    )
    assert any("O_Returns" in e for e in errors)


def test_template_with_no_m_tabs_is_ok():
    """A purely static OutputTemplate (no M_ tabs) is technically valid — it just
    doesn't pull from Model. It would still render whatever's in its O_ tabs."""
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers"], ["O_Results"]),
        _pack(["I_Numbers"]),
        _tpl([], output_tabs=["O_Report"]),
    )
    assert errors == []


def test_multiple_errors_all_surfaced():
    errors = run_validator.validate_run_composition(
        _model(["I_Numbers", "I_Other"], ["O_Results"]),
        _pack(["I_Numbers"], calc_tabs=["Calc"]),
        _tpl(["M_Returns"]),
    )
    assert len(errors) >= 3  # missing input + extra calc + missing output

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ihc_tool.main import run_batch


def _codes(case_output, which):
    return {x["code"] for x in case_output["validation"][which]}


def test_tc_04_negative_with_percent_is_failed(tmp_path: Path):
    out = run_batch(Path("corner_cases.txt"), "Specimen A", tmp_path / "o.json")
    case = out[3]  # TC-04
    assert case["status"] == "failed"
    assert "CONTRADICTORY_RESULT_PERCENT" in _codes(case, "errors")


def test_tc_05_invalid_and_unusual_pattern(tmp_path: Path):
    out = run_batch(Path("corner_cases.txt"), "Specimen A", tmp_path / "o.json")
    case = out[4]  # TC-05
    assert case["status"] == "failed"
    assert "INVALID_PATTERN" in _codes(case, "errors")
    assert "UNUSUAL_PATTERN" in _codes(case, "warnings")


def test_tc_16_grouped_positive_negative_lists(tmp_path: Path):
    out = run_batch(Path("corner_cases.txt"), "Specimen A", tmp_path / "o.json")
    case = out[15]  # TC-16
    assert case["status"] == "ok"
    assert not case["validation"]["errors"]


def test_tc_17_grouped_and_clause_results(tmp_path: Path):
    out = run_batch(Path("corner_cases.txt"), "Specimen A", tmp_path / "o.json")
    case = out[16]  # TC-17
    assert case["status"] == "ok"
    assert any(m["marker_canonical"] == "TTF1" and m["result"] == "Positive" for m in case["ihc"]["markers"])


def test_tc_18_percent_range_needs_review(tmp_path: Path):
    out = run_batch(Path("corner_cases.txt"), "Specimen A", tmp_path / "o.json")
    case = out[17]  # TC-18
    assert case["status"] == "needs_review"
    assert "PERCENT_APPROXIMATE" in _codes(case, "warnings")


def test_tc_20_no_markers_found(tmp_path: Path):
    out = run_batch(Path("corner_cases.txt"), "Specimen A", tmp_path / "o.json")
    case = out[19]  # TC-20
    assert case["status"] == "failed"
    assert "NO_MARKERS_FOUND" in _codes(case, "errors")

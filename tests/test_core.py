import json
import subprocess
import sys

import pytest

from groundcite import (
    BRACKET_ID,
    NUMERIC,
    SOURCE_N,
    THREEGPP,
    check_quotes,
    custom,
    extract_citations,
    factual_sentences,
    guard,
    validate,
)

GOOD = (
    "The rear axle bolt torque is 520 Nm [2]. "
    "Tighten in a star pattern after the wheel is seated [2][3]."
)


def test_all_citations_resolve():
    report = validate(GOOD, sources=[1, 2, 3])
    assert report.ok
    assert report.cited_refs == ["2", "3"]
    assert report.unresolved_refs == []
    assert report.coverage == 1.0


def test_invented_source_fails():
    text = GOOD + " The torque for the front bolt is 450 Nm [7]."
    report = validate(text, sources=[1, 2, 3])
    assert not report.ok
    assert report.unresolved_refs == ["7"]
    assert "not in the supplied sources" in report.problems[0]


def test_uncited_sentence_fails_full_coverage():
    text = GOOD + " The bolt is made of hardened steel and rated for heavy duty."
    report = validate(text, sources=[1, 2, 3])
    assert not report.ok
    assert report.sentence_count == 3
    assert report.cited_sentence_count == 2
    assert len(report.uncited_sentences) == 1


def test_partial_coverage_allowed():
    text = GOOD + " The bolt is made of hardened steel and rated for heavy duty."
    report = validate(text, sources=[1, 2, 3], min_coverage=0.5)
    assert report.ok


def test_no_citation_at_all_fails_by_default():
    report = validate("The torque is 520 Nm for every axle bolt on this model.", sources=[1])
    assert not report.ok
    assert "cites no source" in report.problems[0]
    report = validate("The torque is 520 Nm for every axle bolt on this model.", sources=[1],
                      require_any_citation=False, min_coverage=0.0)
    assert report.ok


def test_empty_answer_is_ok():
    assert validate("", sources=[1]).ok


def test_source_n_pattern():
    text = "Replace the filter every 40,000 km (Source 3). Use OEM parts only [source 1]."
    report = validate(text, sources=[1, 2, 3], pattern=SOURCE_N)
    assert report.ok
    assert report.cited_refs == ["3", "1"]


def test_bracket_id_pattern_is_case_insensitive():
    text = "Coolant capacity is 38 litres [SB-2231]. Bleed the system after refilling [Manual-CH4]."
    report = validate(text, sources=["sb-2231", "MANUAL-ch4"], pattern=BRACKET_ID)
    assert report.ok
    report = validate(text, sources=["sb-2231"], pattern=BRACKET_ID)
    assert report.unresolved_refs == ["manual-ch4"]


def test_threegpp_pattern_normalises_clause_words():
    text = ("The UE starts T304 on reconfigurationWithSync (TS 38.331 §5.3.5.5.2). "
            "Expiry triggers re-establishment (TS 38.331 clause 5.3.5.5.2).")
    assert extract_citations(text, THREEGPP) == ["TS 38.331 §5.3.5.5.2"]
    assert validate(text, sources=["TS 38.331 §5.3.5.5.2"], pattern=THREEGPP).ok


def test_custom_pattern_requires_ref_group():
    with pytest.raises(ValueError):
        custom(r"\{\d+\}")
    pat = custom(r"\{(?P<ref>\d+)\}", name="braces")
    assert validate("Torque is 520 Nm {4}.", sources=[4], pattern=pat).ok


def test_factual_sentences_skips_scaffolding():
    md = "# Heading\n\n| a | b |\n|---|---|\nThere are three cases:\n- first case is the simplest one [1]\n```\ncode here\n```\nShort.\n"
    sentences = factual_sentences(md)
    assert sentences == ["first case is the simplest one [1]"]


def test_quotes_checked_against_source_text():
    texts = {2: "Torque the rear axle bolt to 520 Nm using a\ncalibrated wrench."}
    missing = check_quotes({2: ["520 nm using a calibrated wrench", "600 Nm"]}, texts)
    assert missing == ["2: 600 Nm"]
    report = validate(GOOD, sources=[1, 2, 3], quotes={2: ["600 Nm"]}, source_texts=texts)
    assert not report.ok and report.missing_quotes == ["2: 600 Nm"]


def test_quotes_need_source_texts():
    with pytest.raises(ValueError):
        validate(GOOD, sources=[1, 2, 3], quotes={2: ["x"]})


def test_guard_returns_refusal_on_failure():
    ok_text, report = guard(GOOD, sources=[1, 2, 3])
    assert ok_text == GOOD and report.ok
    refused, report = guard(GOOD + " Front bolt is 450 Nm [9].", sources=[1, 2, 3], refusal="NO")
    assert refused == "NO" and not report.ok


def test_report_is_json_serialisable():
    json.dumps(validate(GOOD, sources=[1, 2, 3]).to_dict())


def test_cli_exit_codes(tmp_path):
    answer = tmp_path / "a.md"
    answer.write_text(GOOD, encoding="utf-8")
    ok = subprocess.run([sys.executable, "-m", "groundcite.cli", "check", str(answer),
                         "--sources", "1", "2", "3"], capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.startswith("OK")
    bad = subprocess.run([sys.executable, "-m", "groundcite.cli", "check", str(answer),
                          "--sources", "1", "--json"], capture_output=True, text=True)
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["unresolved_refs"] == ["2", "3"]

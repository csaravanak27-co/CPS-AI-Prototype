import pytest
from vulnquest.harness import ModelSecurityHarness, HarnessResult
from vulnquest.ai_provider import MockProvider

def test_harness_single_evaluation():
    harness = ModelSecurityHarness(provider=MockProvider())
    res = harness.evaluate_sample("VQ001", 'c.execute("SELECT * FROM u WHERE id=" + uid)\n')
    assert isinstance(res, HarnessResult)
    assert res.rule_id == "VQ001"
    assert res.syntax_ok is True
    assert res.remediated is True
    assert res.no_new_vulns is True
    assert res.api_preserved is True
    assert res.is_fully_successful() is True

def test_harness_suite_execution():
    harness = ModelSecurityHarness(provider=MockProvider())
    scorecard = harness.run_suite(max_samples=4)
    assert scorecard["total_evaluated"] == 4
    assert scorecard["metrics"]["syntax_validity_rate"] == 1.0
    assert scorecard["metrics"]["remediation_rate"] == 1.0
    assert scorecard["metrics"]["safety_rate"] == 1.0
    assert len(scorecard["results"]) == 4

def test_harness_to_markdown():
    harness = ModelSecurityHarness(provider=MockProvider())
    scorecard = harness.run_suite(max_samples=2)
    md = ModelSecurityHarness.to_markdown(scorecard)
    assert "Scorecard" in md
    assert "Syntax Validity" in md
    assert "VQ001" in md

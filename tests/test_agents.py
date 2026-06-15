import pytest
import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from models import Experience, AppConfig
from store import ExperienceStore
from agents.clarifier import _has_metric, _parse_raw_bullets
from agents.gap_bridge import _extract_jd_requirements

def test_has_metric():
    assert _has_metric("Improved efficiency by 20%")
    assert _has_metric("Managed a team of 5")
    assert _has_metric("Reduced latency")
    assert not _has_metric("Built a new feature")
    assert not _has_metric("Wrote documentation")

def test_parse_raw_bullets():
    raw = """
    - Built a new API
    * Improved latency by 50%
    Wrote docs
    """
    bullets = _parse_raw_bullets(raw)
    assert len(bullets) == 3
    assert bullets[0].text == "Built a new API"
    assert not bullets[0].has_metric

    assert bullets[1].text == "Improved latency by 50%"
    assert bullets[1].has_metric

    assert bullets[2].text == "Wrote docs"
    assert not bullets[2].has_metric

@patch('agents.gap_bridge._llm_call')
def test_extract_jd_requirements(mock_llm_call):
    config = AppConfig()
    # Test JSON parsing
    mock_llm_call.return_value = '["Python dev", "React experience"]'
    reqs = _extract_jd_requirements("some text", "fake_key", "model", config)
    assert reqs == ["Python dev", "React experience"]

    # Test Markdown wrapped JSON parsing
    mock_llm_call.return_value = '```json\n["AWS"]\n```'
    reqs = _extract_jd_requirements("some text", "fake_key", "model", config)
    assert reqs == ["AWS"]

    # Test plain text fallback
    mock_llm_call.return_value = "Needs Python experience\nNeeds React experience"
    reqs = _extract_jd_requirements("some text", "fake_key", "model", config)
    assert len(reqs) == 2
    assert "Needs Python experience" in reqs

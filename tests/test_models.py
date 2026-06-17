import os
import json
from models import AppConfig, load_config, save_config, Experience, Bullet

def test_config_load_save(tmp_path):
    config_file = tmp_path / "config.json"
    config = AppConfig(llm_retry_max=5, llm_wait_time=10)
    save_config(config, str(config_file))

    loaded_config = load_config(str(config_file))
    assert loaded_config.llm_retry_max == 5
    assert loaded_config.llm_wait_time == 10

def test_config_default_when_missing():
    config = load_config("nonexistent.json")
    assert config.llm_retry_max == 3
    assert config.llm_wait_time == 5

def test_experience_all_text():
    bullet1 = Bullet(id="b1", text="Built a feature.", has_metric=False, source="user_raw", is_active=True, created_at="2025-01-01T00:00:00Z")
    bullet2 = Bullet(id="b2", text="Deleted a feature.", has_metric=False, source="user_raw", is_active=False, created_at="2025-01-01T00:00:00Z")

    exp = Experience(
        id="e1", role="SWE", company="Tech Corp", team_or_division="Backend",
        employment_type="full_time", created_at="2025-01-01T00:00:00Z", updated_at="2025-01-01T00:00:00Z",
        bullets=[bullet1, bullet2], skills=["Python", "React"], industry="Software"
    )

    text = exp.all_text()
    assert "SWE" in text
    assert "Tech Corp" in text
    assert "Backend" in text
    assert "Software" in text
    assert "Built a feature." in text
    assert "Deleted a feature." not in text  # Inactive bullet should be excluded
    assert "Python" in text
    assert "React" in text

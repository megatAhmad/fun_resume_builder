import os
import json
from models import load_config, save_config, AppConfig

def test_config_model_default(tmp_path):
    os.environ["RESUME_MODEL"] = "test/model"
    config = load_config(str(tmp_path / "missing.json"))
    assert config.llm_model == "test/model"

    config.llm_model = "saved/model"
    save_config(config, str(tmp_path / "config.json"))
    loaded = load_config(str(tmp_path / "config.json"))
    assert loaded.llm_model == "saved/model"

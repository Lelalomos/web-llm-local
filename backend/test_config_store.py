import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config_store import DEFAULT_APP_CONFIG, load_app_config, save_app_config, validate_app_config


class ConfigStoreTests(unittest.TestCase):
    def test_validate_app_config_rejects_unknown_keys(self):
        with self.assertRaisesRegex(Exception, "unknown config keys"):
            validate_app_config({"bad_key": True})

    def test_save_and_load_config_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_path = config_dir / "app_config.json"
            config_payload = {
                "default_model": "qwen2.5:0.5b",
                "default_system_prompt": "Be concise.",
                "default_web_search_mode": "off",
                "skill_markdown_enabled": False,
                "skill_prompt_max_chars": 1000,
                "web_search_context_max_chars": 2000,
                "chat_max_continuations": 1,
                "default_options": {"num_predict": 321},
            }

            with patch("config_store.CONFIG_DIR", config_dir), patch("config_store.CONFIG_PATH", config_path):
                saved = save_app_config(config_payload)
                loaded = load_app_config()

        self.assertEqual(saved, config_payload)
        self.assertEqual(loaded, config_payload)

    def test_load_app_config_creates_default_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "config"
            config_path = config_dir / "app_config.json"

            with patch("config_store.CONFIG_DIR", config_dir), patch("config_store.CONFIG_PATH", config_path):
                loaded = load_app_config()
                stored_text = config_path.read_text(encoding="utf-8")

        self.assertEqual(loaded, DEFAULT_APP_CONFIG)
        self.assertEqual(json.loads(stored_text), DEFAULT_APP_CONFIG)


if __name__ == "__main__":
    unittest.main()

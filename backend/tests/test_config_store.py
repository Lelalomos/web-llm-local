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
                "chat_memory_prompt_max_chars": 1500,
                "search_provider": "searxng",
                "searxng_enabled": True,
                "searxng_url": "http://searxng:8080",
                "searxng_timeout_seconds": 8,
                "meilisearch_enabled": True,
                "meilisearch_url": "http://meilisearch:7700",
                "meilisearch_index": "web_search_results",
                "meilisearch_timeout_seconds": 3,
                "chat_max_continuations": 1,
                "memory_used": {
                    "general": True,
                    "code_writer": True,
                    "code_reviewer": True,
                    "code_editor": False,
                    "bug_fixer": False,
                    "upload_file": False,
                },
                "chat_summary_prompt": "Summarize memory using this custom prompt.",
                "task_mode_interpreter_enabled": True,
                "task_mode_interpreter_model": "qwen2.5:0.5b",
                "task_mode_interpreter_timeout_seconds": 8,
                "search_context_enhancer_enabled": True,
                "search_context_enhancer_model": "qwen2.5:0.5b",
                "search_context_enhancer_timeout_seconds": 45,
                "search_context_enhancer_max_chars": 6000,
                "ocr_engine": "qwen_vl",
                "pdf_extraction_mode": "page_image_ocr",
                "vision_ocr_model": "qwen3-vl:latest",
                "vision_ocr_timeout_seconds": 120,
                "vision_ocr_prompt": "Extract text",
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

    def test_validate_app_config_rejects_invalid_ocr_engine(self):
        with self.assertRaisesRegex(Exception, "ocr_engine must be"):
            validate_app_config({"ocr_engine": "bad_engine"})

    def test_validate_app_config_rejects_invalid_pdf_extraction_mode(self):
        with self.assertRaisesRegex(Exception, "pdf_extraction_mode must be"):
            validate_app_config({"pdf_extraction_mode": "bad_mode"})

    def test_validate_app_config_rejects_empty_chat_summary_prompt(self):
        with self.assertRaisesRegex(Exception, "chat_summary_prompt must be"):
            validate_app_config({"chat_summary_prompt": ""})

    def test_validate_app_config_rejects_invalid_memory_prompt_limit(self):
        with self.assertRaisesRegex(Exception, "chat_memory_prompt_max_chars must be"):
            validate_app_config({"chat_memory_prompt_max_chars": 12001})

    def test_default_web_search_context_fits_small_model_context(self):
        self.assertEqual(DEFAULT_APP_CONFIG["web_search_context_max_chars"], 2500)

    def test_validate_app_config_accepts_partial_memory_used(self):
        config = validate_app_config({"memory_used": {"general": True, "code_writer": True, "upload_file": False}})

        self.assertEqual(config["memory_used"], {"general": True, "code_writer": True, "upload_file": False})

    def test_validate_app_config_rejects_unknown_memory_task_mode(self):
        with self.assertRaisesRegex(Exception, "memory_used has unknown task modes"):
            validate_app_config({"memory_used": {"general": True, "bad_mode": False}})

    def test_validate_app_config_rejects_non_boolean_memory_value(self):
        with self.assertRaisesRegex(Exception, "memory_used.general must be a boolean"):
            validate_app_config({"memory_used": {"general": "yes"}})


if __name__ == "__main__":
    unittest.main()

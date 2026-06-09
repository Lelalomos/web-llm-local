import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skill_loader import inject_skill_context, load_skill_markdown


class SkillLoaderTests(unittest.TestCase):
    def test_load_skill_markdown_reads_sorted_markdown_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "b.md").write_text("Second file", encoding="utf-8")
            (skill_dir / "a.md").write_text("First file", encoding="utf-8")

            with patch("skill_loader.SKILL_DIR", skill_dir):
                text = load_skill_markdown(2000)

        self.assertIn("a.md", text)
        self.assertIn("First file", text)
        self.assertIn("b.md", text)
        self.assertTrue(text.index("a.md") < text.index("b.md"))

    def test_default_skill_dir_is_project_root_skill_folder(self):
        import skill_loader

        self.assertEqual(skill_loader.SKILL_DIR.name, "skill")
        self.assertEqual(skill_loader.SKILL_DIR, skill_loader.PROJECT_ROOT / "skill")

    def test_inject_skill_context_prepends_system_message(self):
        payload = {"messages": [{"role": "user", "content": "hello"}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skill"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "rules.md").write_text("Always answer clearly.", encoding="utf-8")

            with patch("skill_loader.SKILL_DIR", skill_dir):
                injected = inject_skill_context(payload, 2000)

        self.assertTrue(injected)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("rules.md", payload["messages"][0]["content"])
        self.assertIn("Always answer clearly.", payload["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()

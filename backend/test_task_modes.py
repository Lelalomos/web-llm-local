import unittest

from task_modes import apply_task_mode


class TaskModeTests(unittest.TestCase):
    def test_code_writer_injects_system_prompt_and_disables_thinking(self):
        payload = {"task_mode": "code_writer", "messages": [{"role": "user", "content": "write python"}]}

        task_mode = apply_task_mode(payload)

        self.assertEqual(task_mode, "code_writer")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("coding assistant", payload["messages"][0]["content"])
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"]["num_predict"], 1600)

    def test_existing_system_prompt_is_preserved(self):
        payload = {
            "task_mode": "bug_fixer",
            "messages": [
                {"role": "system", "content": "base rules"},
                {"role": "user", "content": "fix this bug"},
            ],
        }

        apply_task_mode(payload)

        self.assertIn("base rules", payload["messages"][0]["content"])
        self.assertIn("debugging assistant", payload["messages"][0]["content"])
        self.assertEqual(payload["options"]["num_predict"], 1200)

    def test_general_mode_does_not_modify_payload(self):
        payload = {"task_mode": "general", "messages": [{"role": "user", "content": "hello"}]}

        task_mode = apply_task_mode(payload)

        self.assertEqual(task_mode, "general")
        self.assertEqual(len(payload["messages"]), 1)
        self.assertNotIn("think", payload)

    def test_code_reviewer_uses_shorter_output_budget(self):
        payload = {"task_mode": "code_reviewer", "messages": [{"role": "user", "content": "review this"}]}

        apply_task_mode(payload)

        self.assertEqual(payload["options"]["num_predict"], 900)

    def test_task_mode_raises_low_config_output_budget(self):
        payload = {
            "task_mode": "code_writer",
            "messages": [{"role": "user", "content": "write rust"}],
            "options": {"num_predict": 900},
        }

        apply_task_mode(payload)

        self.assertEqual(payload["options"]["num_predict"], 1600)


if __name__ == "__main__":
    unittest.main()

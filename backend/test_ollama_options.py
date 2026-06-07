import os
import unittest
from unittest.mock import patch

from ollama_options import apply_gpu_defaults


class ApplyGpuDefaultsTests(unittest.TestCase):
    def test_injects_e2b_profile_by_default(self):
        payload = {"model": "gemma4:e2b", "messages": [{"role": "user", "content": "hi"}]}

        updated_payload = apply_gpu_defaults(payload)

        self.assertEqual(updated_payload["options"]["num_gpu"], 999)
        self.assertEqual(updated_payload["options"]["num_ctx"], 2048)
        self.assertEqual(updated_payload["options"]["num_batch"], 128)

    def test_preserves_existing_num_gpu(self):
        payload = {
            "model": "gemma4:e2b",
            "messages": [{"role": "user", "content": "hi"}],
            "options": {"num_gpu": 12},
        }

        updated_payload = apply_gpu_defaults(payload)

        self.assertEqual(updated_payload["options"]["num_gpu"], 12)

    def test_skips_unload_request(self):
        payload = {"model": "gemma4:12b", "messages": [], "keep_alive": 0}

        updated_payload = apply_gpu_defaults(payload)

        self.assertNotIn("options", updated_payload)

    def test_reads_optional_context_and_batch_from_env_for_e2b(self):
        payload = {"model": "gemma4:e2b", "messages": [{"role": "user", "content": "hi"}]}

        with patch.dict(
            os.environ,
            {
                "OLLAMA_GEMMA4_E2B_NUM_GPU": "321",
                "OLLAMA_GEMMA4_E2B_NUM_CTX": "1024",
                "OLLAMA_GEMMA4_E2B_NUM_BATCH": "64",
            },
            clear=False,
        ):
            updated_payload = apply_gpu_defaults(payload)

        self.assertEqual(
            updated_payload["options"],
            {"num_gpu": 321, "num_ctx": 1024, "num_batch": 64},
        )

    def test_large_gemma_avoids_forced_full_gpu_offload(self):
        payload = {"model": "gemma4:12b", "messages": [{"role": "user", "content": "hi"}]}

        updated_payload = apply_gpu_defaults(payload)

        self.assertNotIn("num_gpu", updated_payload["options"])
        self.assertEqual(updated_payload["options"]["num_ctx"], 1024)
        self.assertEqual(updated_payload["options"]["num_batch"], 32)


if __name__ == "__main__":
    unittest.main()

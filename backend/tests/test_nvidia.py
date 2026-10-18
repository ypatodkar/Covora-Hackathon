import io
import json
import os
import unittest
from unittest.mock import patch

from services import nvidia


class NvidiaApiTests(unittest.TestCase):
    def test_chat_uses_nvidia_key_and_preserves_conversation(self):
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": "  Hello  "}}]}).encode())
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key", "NVIDIA_CHAT_MODEL": ""}), patch.object(nvidia, "urlopen", return_value=response) as open_url:
            result = nvidia.generate_response("Be brief", "Hi", [{"role": "assistant", "content": "Earlier"}])

        self.assertEqual(result, "Hello")
        request = open_url.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://integrate.api.nvidia.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(payload["model"], nvidia.DEFAULT_CHAT_MODEL)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(payload["reasoning_budget"], 0)
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "assistant", "user"])
        self.assertEqual(payload["messages"][-1]["content"], "Hi")

    def test_embedding_uses_query_mode_and_checks_dimensions(self):
        response = io.BytesIO(json.dumps({"data": [{"embedding": [0.1] * nvidia.EMBEDDING_DIM}]}).encode())
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}), patch.object(nvidia, "urlopen", return_value=response) as open_url:
            vector = nvidia.embedding("test", "query")

        payload = json.loads(open_url.call_args.args[0].data)
        self.assertEqual(len(vector), 2048)
        self.assertEqual(payload["model"], nvidia.EMBEDDING_MODEL)
        self.assertEqual(payload["input_type"], "query")

    def test_missing_key_fails_before_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(nvidia, "urlopen") as open_url:
            with self.assertRaisesRegex(RuntimeError, "NVIDIA_API_KEY is not set"):
                nvidia.generate_response("system", "hello")
        open_url.assert_not_called()

    def test_optional_followups_timeout_without_failing_the_answer(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key"}), patch.object(nvidia, "urlopen", side_effect=TimeoutError("timed out")) as open_url:
            with self.assertLogs("services.nvidia", level="WARNING"):
                result = nvidia.generate_follow_up_questions("What is recursion?", "A function calling itself.")
        self.assertEqual(result, [])
        self.assertEqual(open_url.call_args.kwargs["timeout"], 10)


if __name__ == "__main__":
    unittest.main()

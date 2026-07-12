import io
import json
import os
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from content_ops.providers.deepseek import DeepSeekClient


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class DeepSeekTests(unittest.TestCase):
    def test_missing_key_fails_without_network_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
                DeepSeekClient.from_env()

    def test_complete_json_parses_content_and_usage(self):
        calls = []

        def transport(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(
                {
                    "model": "deepseek-v4-flash",
                    "choices": [
                        {"message": {"content": '{"items": [1]}'}}
                    ],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 30,
                        "prompt_cache_hit_tokens": 20,
                    },
                }
            )

        client = DeepSeekClient("secret", transport=transport)
        result = client.complete_json(
            stage="candidate",
            system="Return JSON",
            payload={"sources": []},
        )
        self.assertEqual(result.data, {"items": [1]})
        self.assertEqual(result.usage.input_tokens, 120)
        self.assertEqual(result.usage.output_tokens, 30)
        self.assertEqual(result.usage.cached_tokens, 20)
        body = json.loads(calls[0][0].data.decode("utf-8"))
        self.assertEqual(body["model"], "deepseek-v4-flash")
        self.assertEqual(body["response_format"], {"type": "json_object"})

    def test_invalid_json_is_retried_twice_then_fails(self):
        attempts = 0

        def transport(request, timeout):
            nonlocal attempts
            attempts += 1
            return FakeResponse(
                {
                    "model": "deepseek-v4-flash",
                    "choices": [{"message": {"content": "not-json"}}],
                    "usage": {},
                }
            )

        client = DeepSeekClient("secret", transport=transport, max_retries=2)
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            client.complete_json(stage="candidate", system="JSON", payload={})
        self.assertEqual(attempts, 3)

    def test_transient_network_and_server_errors_are_retried(self):
        attempts = 0

        def transport(request, timeout):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise URLError("temporary")
            if attempts == 2:
                raise HTTPError(
                    request.full_url,
                    503,
                    "busy",
                    {},
                    io.BytesIO(b"{}"),
                )
            return FakeResponse(
                {
                    "model": "deepseek-v4-flash",
                    "choices": [{"message": {"content": '{"ok": true}'}}],
                    "usage": {},
                }
            )

        client = DeepSeekClient("secret", transport=transport, max_retries=2)
        result = client.complete_json(
            stage="candidate", system="JSON", payload={}
        )
        self.assertEqual(result.data, {"ok": True})
        self.assertEqual(attempts, 3)

    def test_auth_error_is_not_retried(self):
        attempts = 0

        def transport(request, timeout):
            nonlocal attempts
            attempts += 1
            raise HTTPError(
                request.full_url,
                401,
                "unauthorized",
                {},
                io.BytesIO(b"{}"),
            )

        client = DeepSeekClient("secret", transport=transport, max_retries=2)
        with self.assertRaises(HTTPError):
            client.complete_json(stage="candidate", system="JSON", payload={})
        self.assertEqual(attempts, 1)

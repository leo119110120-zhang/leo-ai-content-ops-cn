from collections.abc import Callable
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from content_ops.providers import ModelResult, ModelUsage


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout: int = 90,
        max_retries: int = 2,
        transport: Callable = urlopen,
    ):
        self.api_key = api_key
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport

    @classmethod
    def from_env(cls, **kwargs):
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise ValueError("DEEPSEEK_API_KEY is required")
        return cls(key, **kwargs)

    def complete_json(
        self,
        *,
        stage: str,
        system: str,
        payload: dict,
        thinking: bool = False,
    ) -> ModelResult:
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            request = self._request(stage, system, payload, thinking)
            try:
                with self.transport(request, timeout=self.timeout) as response:
                    raw = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                if error.code < 500 and error.code != 429:
                    raise
                last_error = error
                continue
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                continue
            try:
                data = json.loads(raw["choices"][0]["message"]["content"])
            except (
                KeyError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as error:
                last_error = error
                continue
            usage = raw.get("usage", {})
            return ModelResult(
                data=data,
                usage=ModelUsage(
                    int(usage.get("prompt_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                    int(usage.get("prompt_cache_hit_tokens", 0)),
                ),
                model=str(raw.get("model", self.model)),
            )
        if isinstance(last_error, json.JSONDecodeError):
            raise ValueError("DeepSeek did not return valid JSON") from last_error
        raise RuntimeError("DeepSeek request failed after retries") from last_error

    def _request(
        self,
        stage: str,
        system: str,
        payload: dict,
        thinking: bool,
    ) -> Request:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "thinking": {
                "type": "enabled" if thinking else "disabled"
            },
        }
        return Request(
            self.endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Content-Stage": stage,
            },
            method="POST",
        )

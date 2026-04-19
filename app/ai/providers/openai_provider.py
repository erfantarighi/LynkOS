from __future__ import annotations

import json

import httpx

from app.ai.providers.base import AIProviderError


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        if not self._api_key:
            raise AIProviderError("LYNKOS_AI_API_KEY is missing")
        payload = {
            "model": self._model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{user_prompt}\n\n"
                        f"Return JSON that validates against this schema:\n{json.dumps(schema)}"
                    ),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
            res.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(str(exc)) from exc
        try:
            data = res.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("non-string response content")
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIProviderError(f"invalid provider response: {exc}") from exc

from __future__ import annotations

from typing import Protocol


class AIProviderError(RuntimeError):
    pass


class AIProvider(Protocol):
    async def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        ...

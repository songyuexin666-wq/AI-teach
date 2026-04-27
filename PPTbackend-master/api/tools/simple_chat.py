from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List

import openai

from api.tools.base import BaseTool, ToolContext


class SimpleChatTool(BaseTool):
    name = "simple_chat"
    description = "Use the configured OpenAI-compatible model for general teaching chat."

    def _get_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model = os.getenv("AI_MODEL", "qwen-plus")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        return openai.OpenAI(api_key=api_key, base_url=base_url), model

    async def call(
        self,
        context: ToolContext,
        *,
        system_prompt: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        client, model = self._get_client()
        payload = [{"role": "system", "content": system_prompt}] + messages
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=payload,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = (response.choices[0].message.content or "").strip()
        return {"content": content, "role": "assistant", "model": model}

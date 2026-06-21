"""
LLM 适配层 — 封装 LLM API 调用，支持流式输出。

参考 Hermes Studio 的 AgentBridgeClient 设计思路：
- 统一接口，底层可切换 OpenAI / Anthropic / Ollama
- 流式输出用 async generator
- 阶段 1 只支持 OpenAI 兼容 API
"""

from __future__ import annotations

import os
from typing import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass
class LLMResponse:
    """LLM 返回的结构化响应"""
    content: str           # 文本内容
    tool_calls: list[dict]  # 工具调用列表（[{name, args, id}, ...]）


class LLMClient:
    """
    LLM 客户端 — 阶段 1 使用 OpenAI 兼容 API。

    自动支持：
    - OpenAI 官方 API
    - Ollama 本地模型（设置 base_url=http://localhost:11434/v1）
    - 任何 OpenAI 兼容的第三方 API（Groq、DeepSeek、OpenRouter 等）

    用法：
        client = LLMClient()  # 自动从环境变量读取配置
        async for chunk in client.stream_chat(messages, tools):
            print(chunk, end="")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "sk-placeholder")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", None)
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """
        流式对话 — 逐 token 产出文本。

        这是 Agent 循环的核心调用。每次 yield 一个 delta 字符串，
        上层（Agent / WebSocket）负责分发到各个客户端。
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        stream = await self._client.chat.completions.create(**kwargs)

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        非流式对话 — 一次返回完整结果（含 tool_calls）。

        用于 Agent 需要完整解析 tool_call 的场景。
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": tc.function.arguments,
                })

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
        )

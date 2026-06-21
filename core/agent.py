"""
Agent 主循环 — 整个系统的"大脑"。

这是 Hermes Studio 的 handle-bridge-run.ts 的 Python 实现。
核心逻辑：
1. 接收用户输入
2. 调用 LLM，流式返回文本
3. 如果 LLM 返回 tool_call → 执行工具 → 把结果发回 LLM → 继续
4. 直到 LLM 不再调用工具，返回最终回复

这个循环就是 Claude Code / Hermes Studio / ChatGPT 的底层工作原理。
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncIterator
from dataclasses import dataclass, field

from .llm import LLMClient
from .tools import ToolRegistry
from .memory import Memory


SYSTEM_PROMPT = """你是 Hermes Studio —— 一个 AI 编程助手，运行在 Arch Linux 上。

你的能力：
- 与用户对话，回答编程、技术问题
- 使用工具读取文件、执行命令、获取系统信息
- 写代码时直接输出，不要用 run_command 去创建文件

使用工具的准则：
- 需要查看文件内容 → read_file
- 需要执行系统命令 → run_command（仅限单条命令，不支持 heredoc/pipeline/重定向）
- 需要系统信息 → system_info
- 用户要求写代码时，直接在你的回复中输出代码块，不要调用工具
- 工具执行结果返回后，基于结果用中文回复
- 简洁直接

诚实原则：
- 你是云端 API 驱动的 AI，不是本地模型。用户问你的模型/运行方式时如实回答
- 不要假装你是本地运行的模型或声称使用本地 GPU 显存"""


@dataclass
class AgentEvent:
    """Agent 循环产生的事件 — 用于流式推送到各个客户端"""
    type: str           # "text" | "tool_start" | "tool_end" | "done" | "error"
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""


class Agent:
    """
    AI Agent 引擎 — 平台无关的核心。

    用法：
        agent = Agent()
        async for event in agent.run("帮我看看系统信息", session_id="demo"):
            print(event)
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        tools: ToolRegistry | None = None,
        memory: Memory | None = None,
    ):
        from .tools import create_builtin_registry
        self.llm = llm or LLMClient()
        self.tools = tools or create_builtin_registry()
        self.memory = memory or Memory()

    async def run(
        self,
        user_input: str,
        session_id: str | None = None,
        max_tool_rounds: int = 10,
    ) -> AsyncIterator[AgentEvent]:
        """
        Agent 主循环 — 处理一次用户输入。

        流程：
        1. 加载历史记忆
        2. 构建消息列表（system + history + user）
        3. 调用 LLM
           - 如果返回文本 → 流式输出
           - 如果返回 tool_call → 执行工具 → 追加结果 → 回到步骤 3
        4. 保存对话到记忆

        max_tool_rounds 防止无限循环（LLM 反复调用工具不退出）。
        """
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"

        # 1. 加载历史
        history = self.memory.load(session_id)
        self.memory.trim(session_id, max_messages=40)

        # 2. 构建消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        # 保存用户消息
        self.memory.append(session_id, "user", user_input)

        tool_schemas = self.tools.get_all_schemas()
        full_response = ""

        # 3. Agent 循环
        for round_num in range(max_tool_rounds):
            # 调用 LLM（非流式 — 阶段 1 先保证正确性）
            response = await self.llm.chat_with_tools(messages, tool_schemas)

            # 情况 A: 有工具调用 → 执行工具，结果加入对话，继续循环
            if response.tool_calls:
                # 把 assistant 的 tool_call 消息加入
                assistant_tool_calls = []
                for tc in response.tool_calls:
                    tool_name = tc["name"]
                    tool_args = (
                        json.loads(tc["args"])
                        if isinstance(tc["args"], str)
                        else tc["args"]
                    )

                    yield AgentEvent(
                        type="tool_start",
                        tool_name=tool_name,
                        tool_args=tool_args,
                    )

                    result = self.tools.execute(tool_name, tool_args)

                    yield AgentEvent(
                        type="tool_end",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        tool_result=result,
                    )

                    assistant_tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args, ensure_ascii=False),
                        },
                    })
                    # 工具结果加入消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                # assistant 的工具调用声明加入消息（放在 tool results 前面）
                messages.insert(
                    -(len(response.tool_calls)),
                    {
                        "role": "assistant",
                        "content": response.content or None,
                        "tool_calls": assistant_tool_calls,
                    },
                )

                # 继续循环，LLM 会基于工具结果生成最终回复
                continue

            # 情况 B: 有文本回复且无工具调用 → 结束
            if response.content:
                full_response = response.content
                yield AgentEvent(type="text", content=response.content)
                break

            # 情况 C: 既无文本也无工具调用 → 异常，结束
            break

        # 5. 保存助手回复
        if full_response.strip():
            self.memory.append(session_id, "assistant", full_response)

        yield AgentEvent(type="done", content=full_response)

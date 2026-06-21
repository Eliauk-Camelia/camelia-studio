"""
CLI 适配器 — 终端聊天客户端。

参考 Hermes Studio 的多端架构：
- 这是第一个"端"（Adapter）
- 后续可加 Web 端、Telegram Bot 等
- 所有端共享同一个 Agent 引擎，只是 I/O 方式不同
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from core.agent import Agent, AgentEvent


async def run_cli():
    """
    命令行 AI 对话客户端。

    用法：
        python -m adapters.cli
        python -m adapters.cli --session my_chat
    """
    agent = Agent()
    session_id = f"cli_{uuid.uuid4().hex[:8]}"

    print("╔══════════════════════════════════╗")
    print("║   Hermes Studio — CLI Client    ║")
    print("║   输入消息开始对话，/quit 退出   ║")
    print("╚══════════════════════════════════╝")
    print()

    while True:
        try:
            user_input = input("▸ 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "/q"):
            print("再见！")
            break

        print()  # 空行分隔

        # Agent 循环 — 流式输出
        first_chunk = True
        async for event in agent.run(user_input, session_id):
            if event.type == "text":
                if first_chunk:
                    print("▸ AI: ", end="", flush=True)
                    first_chunk = False
                print(event.content, end="", flush=True)
            elif event.type == "tool_start":
                print(f"\n  🔧 调用工具: {event.tool_name}")
            elif event.type == "tool_end":
                preview = event.tool_result[:150].replace("\n", " ")
                print(f"  ✅ 完成: {preview}...")
            elif event.type == "done":
                print()
            elif event.type == "error":
                print(f"\n  ❌ 错误: {event.content}")

        print()  # 结尾空行


if __name__ == "__main__":
    asyncio.run(run_cli())

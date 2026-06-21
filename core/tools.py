"""
Tool 注册与执行引擎 — Agent 的"手"。

参考 Hermes Studio 的 Tool Calling 机制：
- 每个 Tool 有 name / description / parameters (JSON Schema)
- ToolRegistry 统一管理所有可用工具
- Agent 通过 function_call 来调用工具
"""

from __future__ import annotations

import subprocess
import platform
from pathlib import Path
from typing import Any, Callable
from dataclasses import dataclass, field


@dataclass
class Tool:
    """
    一个可被 Agent 调用的工具。

    schema 字段使用 OpenAI Function Calling 格式，
    这样 LLM 能理解工具的用途和参数。
    """
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., str]  # 实际执行的函数

    def to_openai_schema(self) -> dict[str, Any]:
        """转为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """
    工具注册表 — Agent 的所有能力都注册在这里。

    新增能力 = 写一个 Tool + register，Agent 循环不需要改。
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """返回所有工具的 OpenAI schema，用于构造 LLM 请求"""
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        """执行指定工具，返回结果字符串"""
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未知工具 '{name}'"
        try:
            return tool.handler(**args)
        except Exception as e:
            return f"工具执行失败: {e}"


# ─── 内置工具 ───────────────────────────────────


def _read_file(path: str) -> str:
    """读取文件内容"""
    p = Path(path).expanduser()
    if not p.exists():
        return f"文件不存在: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    # 限制返回长度，避免超出 LLM 上下文
    if len(content) > 8000:
        content = content[:8000] + f"\n... (截断，共 {len(content)} 字符)"
    return content


def _run_command(command: str) -> str:
    """执行系统命令并返回输出"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip() or result.stderr.strip()
        if len(output) > 4000:
            output = output[:4000] + "\n... (截断)"
        return output or "(命令无输出)"
    except subprocess.TimeoutExpired:
        return "命令执行超时 (30s)"
    except Exception as e:
        return f"命令执行失败: {e}"


def _system_info() -> str:
    """获取系统信息"""
    return (
        f"操作系统: {platform.system()} {platform.release()}\n"
        f"架构: {platform.machine()}\n"
        f"Python: {platform.python_version()}\n"
        f"主机名: {platform.node()}"
    )


def create_builtin_registry() -> ToolRegistry:
    """
    创建预置工具注册表。

    阶段 1 只有 3 个基础工具。
    阶段 2 会加入 MSPM0 硬件控制工具。
    阶段 3 可以注册任意自定义工具。
    """
    registry = ToolRegistry()
    registry.register(Tool(
        name="read_file",
        description="读取本地文件内容。用于查看代码、配置、日志等文本文件。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的绝对路径或相对路径"}
            },
            "required": ["path"],
        },
        handler=_read_file,
    ))
    registry.register(Tool(
        name="run_command",
        description="在终端执行 shell 命令并返回输出。用于编译代码、运行脚本、查看系统状态。",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"}
            },
            "required": ["command"],
        },
        handler=_run_command,
    ))
    registry.register(Tool(
        name="system_info",
        description="获取当前系统信息（操作系统、架构、Python 版本等）。",
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=_system_info,
    ))
    return registry

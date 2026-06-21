"""
消息协议定义 — 所有客户端和 Agent 核心之间的通信契约。

参考 Hermes Studio 的 AgentBridge 设计：
- 所有消息遵循统一的 JSON 格式
- source 字段标记消息来源（cli / web / telegram / ...）
- 同一个 session_id 可以在多个端之间共享
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from dataclasses import dataclass, field, asdict
from datetime import datetime


class MessageType(str, Enum):
    """消息类型枚举"""
    CHAT = "chat"                # 用户对话消息
    SYSTEM = "system"            # 系统消息（连接/断开/错误）
    TOOL_CALL = "tool_call"      # Agent 发起的工具调用
    TOOL_RESULT = "tool_result"  # 工具执行结果
    STREAM = "stream"            # LLM 流式输出增量
    ERROR = "error"              # 错误消息
    PONG = "pong"                # 心跳响应


class MessageSource(str, Enum):
    """消息来源 — 多端互通的标记字段"""
    CLI = "cli"
    WEB = "web"
    TELEGRAM = "telegram"
    SYSTEM = "system"


@dataclass
class Message:
    """
    统一消息结构 — 所有端和 Agent 核心之间只传这一种格式。

    对应 Hermes Studio 中 AgentBridgeMessage 的设计。
    """
    type: MessageType
    content: str = ""
    session_id: str = ""
    source: MessageSource = MessageSource.SYSTEM
    # 工具调用相关
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    # 元数据
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().timestamp()

    def to_json(self) -> dict[str, Any]:
        """序列化为 JSON，方便通过 WebSocket/HTTP 传输"""
        data = asdict(self)
        data["type"] = self.type.value
        data["source"] = self.source.value
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Message:
        """从 JSON 反序列化"""
        return cls(
            type=MessageType(data.get("type", "chat")),
            content=data.get("content", ""),
            session_id=data.get("session_id", ""),
            source=MessageSource(data.get("source", "system")),
            tool_name=data.get("tool_name", ""),
            tool_args=data.get("tool_args", {}),
            tool_result=data.get("tool_result", ""),
            timestamp=data.get("timestamp", 0.0),
            metadata=data.get("metadata", {}),
        )

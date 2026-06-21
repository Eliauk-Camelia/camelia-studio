"""
记忆管理 — Session 对话历史的持久化存储。

参考 Hermes Studio 的 session-store.ts：
- 每个 session_id 对应一组对话消息
- 自动保存到 ~/.hermes-studio/sessions/
- 支持基本的上下文窗口管理
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Memory:
    """
    对话记忆管理器 — 负责存储和加载对话历史。

    阶段 1：简单的 JSON 文件存储。
    阶段 2：可升级为 SQLite（像 Hermes Studio 那样），支持向量搜索。
    """

    def __init__(self, storage_dir: str | None = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".hermes-studio" / "sessions"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """会话文件路径"""
        safe_id = session_id.replace("/", "_").replace("..", "_")
        return self.storage_dir / f"{safe_id}.json"

    def load(self, session_id: str) -> list[dict[str, Any]]:
        """
        加载会话历史。

        返回格式与 OpenAI Chat Completion 的 messages 格式一致：
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
        """
        path = self._session_path(session_id)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return []

    def save(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """保存会话历史"""
        path = self._session_path(session_id)
        path.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息到会话末尾"""
        messages = self.load(session_id)
        messages.append({"role": role, "content": content})
        self.save(session_id, messages)

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return [
            p.stem for p in self.storage_dir.glob("*.json")
        ]

    def clear(self, session_id: str) -> None:
        """清除指定会话"""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    def trim(self, session_id: str, max_messages: int = 50) -> None:
        """
        裁剪会话历史到最近 N 条消息。

        对应 Hermes Studio 的 compression.ts 中的上下文压缩功能。
        阶段 1 只做简单截断，阶段 3 可升级为 LLM 智能摘要。
        """
        messages = self.load(session_id)
        if len(messages) > max_messages:
            self.save(session_id, messages[-max_messages:])

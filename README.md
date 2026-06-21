# Hermes Studio

本地 AI Agent 平台 — 受 [Hermes Studio](https://github.com/EKKOLearnAI/hermes-studio) 启发。

## 架构

```
┌──────────────────────────────────────────────────┐
│                   Adapters (多端)                 │
│  CLI │ Web UI │ Telegram Bot │ ... (按需扩展)      │
└──────────────────────┬───────────────────────────┘
                       │ WebSocket / HTTP
┌──────────────────────▼───────────────────────────┐
│                 Message Bus (bus/)                │
│  FastAPI + WebSocket │ Protocol │ Session 管理    │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│                 Agent Core (core/)                │
│  Agent Loop │ LLM Client │ Tool Registry │ Memory │
└──────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API Key (OpenAI 兼容)
export OPENAI_API_KEY="sk-xxx"

# 可选：使用 Ollama 本地模型
export OPENAI_BASE_URL="http://localhost:11434/v1"
export LLM_MODEL="qwen2.5:7b"

# 启动 Web 服务
python main.py

# 或终端模式
python main.py --cli
```

## 技术栈

- **Agent 引擎**: Python asyncio
- **消息总线**: FastAPI + WebSocket
- **LLM**: OpenAI 兼容 API (OpenAI / Ollama / DeepSeek / Groq ...)
- **存储**: JSON 文件 (阶段 1)

## 项目结构

```
├── core/           # Agent 引擎（平台无关）
│   ├── agent.py    # Agent 主循环
│   ├── llm.py      # LLM 适配器
│   ├── memory.py   # 对话记忆
│   └── tools.py    # Tool 注册引擎
├── bus/            # 消息总线
│   ├── server.py   # FastAPI + WebSocket
│   └── protocol.py # 消息协议
├── adapters/       # 平台适配器
│   ├── cli.py      # 终端客户端
│   └── web/        # Web 前端
├── hardware/       # 硬件控制（阶段 2）
├── main.py         # 入口
└── requirements.txt
```

## 开发路线

- [x] 阶段 1: Agent 骨架 + CLI + Web 界面
- [ ] 阶段 2: MSPM0/STM32 硬件控制 Tool
- [ ] 阶段 3: 多端互通 (Telegram Bot / 微信)

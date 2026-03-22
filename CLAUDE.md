# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**XianyuAutoAgent** is an AI-powered customer service bot for Xianyu (Alibaba's secondhand marketplace platform). It automates customer support 24/7 using LLM-based responses with multiple specialist agents for different scenarios. The project runs exclusively as an **Electron desktop application**.

## Architecture

The system has a multi-agent architecture with distinct concerns:

1. **Electron Main Process** (`electron/main/index.js`)
   - Creates BrowserWindow and manages app lifecycle
   - Spawns Python bridge subprocess via `pythonManager.js`
   - Registers IPC handlers via `ipcHandlers.js`
   - Manages SQLite config/prompts via `dbManager.js`

2. **Python Bridge** (`python/bridge.py`)
   - IPC bridge between Electron and Python backend (JSON lines over stdin/stdout)
   - Listens for commands: `start`, `stop`, `reload_config`, `login`
   - Emits log/status events back to Electron renderer

3. **WebSocket Connection Layer** (`python/main.py`, `XianyuLive` class)
   - Maintains persistent WebSocket connection to Xianyu's messaging service
   - Handles token refresh and reconnection logic
   - Manages message routing and manual/auto mode toggling

4. **LLM Response Generation** (`python/XianyuAgent.py`, `XianyuReplyBot` class)
   - Routes user messages to appropriate specialist agents via intent classification
   - Four specialist agents: `classify` (intent detection), `price` (negotiation), `tech` (technical support), `default` (general replies)
   - Safety filtering prevents exposing contact info (WeChat, QQ, etc.)

5. **Context Management** (`python/context_manager.py`, `ChatContextManager` class)
   - SQLite database stores conversation history per chat session
   - Tracks negotiation attempt counts per conversation

6. **API Integration** (`python/XianyuApis.py`, `XianyuApis` class)
   - HTTP wrapper for Xianyu platform endpoints (token refresh, auth)
   - Manages session cookies and authentication headers

## Key Configuration

All configuration is stored in SQLite (`%APPDATA%\XianyuAutoAgent\app_config.db`) and managed via the Electron UI Settings page. No `.env` file is used.

| Variable | Purpose | Default |
|----------|---------|---------|
| `API_KEY` | LLM API key (Qwen-compatible) | Required |
| `COOKIES_STR` | Xianyu session cookies | Required |
| `MODEL_BASE_URL` | LLM API endpoint | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `MODEL_NAME` | LLM model name | qwen-max |
| `TOGGLE_KEYWORDS` | Toggle manual/auto mode | 。(Chinese period) |
| `SIMULATE_HUMAN_TYPING` | Add reply delays | False |
| `HEARTBEAT_INTERVAL` | WebSocket heartbeat (seconds) | 15 |
| `HEARTBEAT_TIMEOUT` | Heartbeat timeout (seconds) | 5 |
| `TOKEN_REFRESH_INTERVAL` | Token refresh interval (seconds) | 3600 |
| `MANUAL_MODE_TIMEOUT` | Manual mode duration (seconds) | 3600 |
| `MESSAGE_EXPIRE_TIME` | Message expiration (ms) | 300000 |

## Custom Prompts

LLM prompts are stored in the SQLite database (`prompts` table) and editable via the Electron UI:

- `classify_prompt` - Intent classification logic
- `price_prompt` - Price negotiation strategy
- `tech_prompt` - Technical support responses
- `default_prompt` - General customer service replies

## Development Commands

```bash
# Install Python dependencies
pip install -r python/requirements.txt

# Install Electron dependencies
cd electron
npm install

# Run in development mode (Vite + Electron with hot reload)
cd electron
npm run dev
```

## Project Structure

```
├── electron/               # Electron desktop app
│   ├── main/               # Main process (index.js, pythonManager.js, ipcHandlers.js, dbManager.js)
│   ├── preload/            # Preload scripts
│   ├── renderer/           # Vue 3 frontend (Vite)
│   └── package.json
├── python/                 # Python backend (Electron bridge mode)
│   ├── bridge.py           # IPC bridge entry point
│   ├── main.py             # XianyuLive WebSocket handler
│   ├── XianyuAgent.py      # LLM response generation & agent routing
│   ├── XianyuApis.py       # HTTP API wrapper for platform
│   ├── context_manager.py  # SQLite conversation storage
│   ├── config_manager.py   # SQLite config & prompts manager
│   ├── login_browser.py    # Pure-CDP QR code login (Chrome/Edge via aiohttp + websockets)
│   ├── utils/
│   │   └── xianyu_utils.py # Utility functions (cookies, signatures, crypto)
│   └── requirements.txt
├── scripts/                # Build scripts
├── installer/              # Inno Setup installer config
└── data/                   # Local SQLite data (chat history)
```

## Key Design Patterns

### Electron ↔ Python IPC
- Electron sends JSON commands to Python via stdin: `{"cmd": "start"}`
- Python emits JSON events to Electron via stdout: `{"type": "log", "level": "info", "message": "..."}`

### Intent-Based Routing
`XianyuReplyBot.generate_reply()` → `IntentRouter` classifies intent → routes to specialist agent → LLM generates response

### Conversation Context
All messages stored in SQLite with (user_id, item_id, chat_id) as key. Context retrieved for each message to maintain conversation continuity.

### Token & Connection Management
- Token auto-refreshes every `TOKEN_REFRESH_INTERVAL` seconds
- Heartbeat keepalive every `HEARTBEAT_INTERVAL` seconds
- Connection auto-restarts on token refresh
- Manual mode temporarily disables auto-reply for human takeover

### Message Processing
Messages are validated before processing:
- `is_chat_message()` - Filters actual customer messages
- `is_system_message()` - Ignores system notifications
- `is_typing_status()` - Ignores "typing..." indicators
- `is_sync_package()` - Handles message synchronization

## Common Issues & Solutions

**Token Expiration**: Use the "扫码登录" button in the UI to refresh cookies automatically, or update `COOKIES_STR` in Settings.

**WebSocket Disconnects**: Automatic reconnection triggers on token refresh. Check logs for "Token刷新成功" messages.

**Message Not Replied**: Verify message passes `is_chat_message()` filter. Check logs for intent classification result and which agent was selected.

**LLM Response Issues**: Edit prompts via the UI Prompts page. Safety filter blocks responses containing contact info.

## Dependencies

### Python (`python/requirements.txt`)
- `openai` - LLM API client (Qwen-compatible)
- `websockets` - WebSocket connection handling
- `loguru` - Structured logging
- `requests` - HTTP requests for API calls
- `aiohttp` - HTTP client for CDP browser control (QR code login)

### Node.js (`electron/package.json`)
- `electron` - Desktop app framework
- `vue` + `vite` - Frontend UI
- `better-sqlite3` - SQLite for config & prompts storage

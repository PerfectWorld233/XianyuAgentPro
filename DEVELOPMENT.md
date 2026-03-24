# XianyuAutoAgent 开发指南

> 闲鱼 AI 客服机器人 · Electron + Python 桌面应用

---

## 环境要求

| 工具 | 版本要求 |
|------|---------|
| Node.js | >= 18.x |
| Python | >= 3.10 |
| npm | >= 9.x |

---

## 一、初始安装

### 1. 安装 Python 依赖

```bash
cd python
pip install -r requirements.txt
```

### 2. 安装 Playwright 浏览器（扫码登录所需）

```bash
playwright install chromium
```

### 3. 安装 Electron 依赖

```bash
cd electron
npm install
```

> `postinstall` 脚本会自动执行 `electron-rebuild` 重新编译 `better-sqlite3` 原生模块，无需手动操作。

---

## 二、启动开发模式

```bash
cd electron
npm run dev
```

该命令同时启动：
- **Vite 开发服务器**（http://localhost:5173）— Vue 前端热重载
- **Electron 主进程** — 加载 Vite Dev Server，自动打开 DevTools

Electron 启动后会自动以子进程方式启动 `python/bridge.py`（通过 stdin/stdout JSON 通信）。

---

## 三、项目结构

```
XianyuAgentPro/
├── electron/
│   ├── main/
│   │   ├── index.js          # Electron 主进程入口
│   │   ├── pythonManager.js  # Python 子进程管理（spawn/stdin/stdout）
│   │   ├── ipcHandlers.js    # IPC 事件注册
│   │   └── dbManager.js      # SQLite 配置/提示词管理
│   ├── preload/
│   │   └── preload.js        # 预加载脚本（contextBridge 暴露 API）
│   ├── renderer/
│   │   └── src/              # Vue 3 前端（Vite）
│   │       ├── views/        # 页面组件
│   │       └── stores/       # Pinia 状态管理
│   └── package.json
├── python/
│   ├── bridge.py             # IPC 桥入口（读 stdin，写 stdout）
│   ├── main.py               # WebSocket 连接层（XianyuLive）
│   ├── XianyuAgent.py        # LLM 路由与回复生成
│   ├── XianyuApis.py         # 闲鱼 HTTP API 封装
│   ├── context_manager.py    # SQLite 对话历史
│   ├── config_manager.py     # SQLite 配置读写
│   ├── login_browser.py      # Playwright 扫码登录
│   └── utils/
│       └── xianyu_utils.py   # Cookie、签名、加解密工具
└── DEVELOPMENT.md
```

---

## 四、IPC 通信协议

### Electron → Python（stdin，JSON Lines）

```json
{"cmd": "start"}
{"cmd": "stop"}
{"cmd": "reload_config"}
{"cmd": "login"}
```

### Python → Electron（stdout，JSON Lines）

```json
{"type": "log",    "level": "info",  "message": "...", "time": "ISO8601"}
{"type": "status", "running": true}
{"type": "error",  "code": "...",    "message": "..."}
{"type": "login_result", "success": true, "cookies": "..."}
```

---

## 五、配置说明

所有配置存储于 SQLite 数据库：

- **Windows**：`%APPDATA%\XianyuAutoAgent\app_config.db`

通过 Electron UI「设置」页面管理，无需手动编辑文件。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `API_KEY` | LLM API Key（兼容 Qwen） | 必填 |
| `COOKIES_STR` | 闲鱼会话 Cookie | 必填 |
| `MODEL_BASE_URL` | LLM API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME` | 模型名称 | `qwen-max` |
| `TOGGLE_KEYWORDS` | 切换人工/自动模式关键词 | `。` |
| `SIMULATE_HUMAN_TYPING` | 模拟人工打字延迟 | `False` |
| `HEARTBEAT_INTERVAL` | WebSocket 心跳间隔（秒） | `15` |
| `TOKEN_REFRESH_INTERVAL` | Token 刷新间隔（秒） | `3600` |
| `MANUAL_MODE_TIMEOUT` | 人工接管超时（秒） | `3600` |

---

## 六、构建生产版本

```bash
cd electron

# 1. 构建 Vue 前端
npm run build:renderer

# 2. 打包 Electron（生成安装程序）
npm run build:electron

# 或一步完成
npm run build
```

> 生产模式下，Electron 会加载 `electron/renderer/dist/index.html`，并调用打包好的 `bridge.exe`（位于 `resources/python-dist/bridge/`）。

---

## 七、常见问题

**Q: `better-sqlite3` 编译失败**

```bash
cd electron
npm run postinstall
# 或
npx electron-rebuild -f -w better-sqlite3
```

**Q: Python 进程无法启动**

检查 `python` 命令是否在 PATH 中：

```bash
python --version
```

若使用虚拟环境，确保在启动 `npm run dev` 前已激活。

**Q: Playwright 找不到浏览器**

```bash
playwright install chromium
```

**Q: Token 过期 / WebSocket 断开**

点击 UI「扫码登录」按钮重新获取 Cookie，或在设置页手动更新 `COOKIES_STR`。

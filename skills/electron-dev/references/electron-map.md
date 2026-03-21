# Electron 项目结构和文件职责

## 目录总览

```
electron/
├── main/
│   ├── index.js          # Electron 主进程入口
│   ├── pythonManager.js  # Python 子进程管理 + stdout 解析
│   ├── ipcHandlers.js    # IPC 通道注册
│   └── dbManager.js      # better-sqlite3 配置读写（主进程侧）
├── preload/
│   └── preload.js        # contextBridge — 向渲染进程暴露 API
└── renderer/             # Vue 3 SPA
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue           # 侧边导航布局
        ├── router/index.js
        ├── stores/
        │   ├── botStore.js   # 机器人运行状态 + 日志列表
        │   └── configStore.js
        ├── components/
        │   ├── LogViewer.vue   # 实时日志滚动区域
        │   └── StatusBadge.vue # 运行状态指示
        └── views/
            ├── Dashboard.vue  # 控制台：启动/停止/扫码登录/日志
            ├── Settings.vue   # 配置编辑器
            └── Prompts.vue    # 4 个 Prompt 文本编辑器
```

---

## 主进程文件

### `main/index.js` - Electron 主进程入口

**职责**：
- 创建 `BrowserWindow`（1100×700，最小 800×600）
- 统一 userData 路径：`%APPDATA%\XianyuAutoAgent\`
- 初始化 `dbManager`、`pythonManager`、注册 IPC 处理器
- 开发模式加载 Vite dev URL；生产模式加载 `renderer/dist/index.html`

**关键变量**：
- `process.env.VITE_DEV_SERVER_URL` — 开发模式标志（concurrently 注入）

---

### `main/pythonManager.js` - Python 子进程管理

**职责**：
- spawn Python 子进程（开发：`python bridge.py`；生产：`bridge.exe`）
- 逐行解析 stdout JSON → `dispatch()` 分发到各 listener 和渲染进程
- 将命令序列化为 JSON line 写入 stdin

**关键函数**：
- `startPython()` — 启动子进程，绑定 stdout/stderr/exit 事件
- `stopPython()` — 发送 SIGTERM
- `sendCommand(cmd)` — 写入 stdin（若进程未启动则先 start 再延迟发送）
- `dispatch(msg)` — 按 `msg.type` 分发到 listeners 并 `webContents.send('bot:<type>', msg)`

**listeners 字典**（type → callback[]）：
```js
{ log: [], status: [], error: [], login_result: [] }
```
> 新增 Python 消息类型时，必须在此字典加入对应 key，否则 dispatch 不会转发。

**环境变量注入**：
```js
env: { PYTHONUNBUFFERED: '1', BRIDGE_MODE: '1', ...process.env }
```

---

### `main/ipcHandlers.js` - IPC 通道注册

**已注册通道**：

| 通道 | 方向 | 实现 |
|------|------|------|
| `bot:start` | 渲染→主 | `sendCommand({cmd:'start'})` |
| `bot:stop` | 渲染→主 | `sendCommand({cmd:'stop'})` |
| `bot:login` | 渲染→主 | `sendCommand({cmd:'login'})` |
| `config:get` | 渲染→主 | `dbManager.getConfig()` |
| `config:save` | 渲染→主 | `dbManager.saveConfig(data)` + `reload_config` |
| `prompts:get` | 渲染→主 | `dbManager.getPrompts()` |
| `prompts:save` | 渲染→主 | `dbManager.savePrompts(data)` + `reload_config` |

**新增 IPC 通道步骤**：
1. `ipcHandlers.js` — `ipcMain.handle('channel:name', handler)`
2. `preload.js` — `contextBridge` 中新增暴露函数
3. Vue 组件 — 调用 `window.electronAPI.xxx()`

---

### `main/dbManager.js` - SQLite 配置读写

**职责**：主进程直接用 `better-sqlite3`（同步）读写 `app_config.db`

**数据库路径**：`app.getPath('appData') + '/XianyuAutoAgent/app_config.db'`
> 与 Python `config_manager.py` 操作同一个文件

**方法**：
- `getConfig() -> object` — 读取全部 config 表键值
- `saveConfig(data)` — 批量写入 config 表
- `getPrompts() -> object` — 读取全部 prompts 表
- `savePrompts(data)` — 批量写入 prompts 表

---

## Preload 脚本

### `preload/preload.js` - contextBridge

向渲染进程暴露的 `window.electronAPI` 方法：

```
botStart()        botStop()         botLogin()
onBotStatus(cb)   onBotLog(cb)      onBotError(cb)
onLoginResult(cb)
removeAllListeners(channel)
getConfig()       saveConfig(data)
getPrompts()      savePrompts(data)
```

> `on*` 系列是 push 推送（`ipcRenderer.on`），其余是 request-response（`ipcRenderer.invoke`）。

---

## 渲染进程文件

### `stores/botStore.js` - 机器人状态

- `running: false` — 来自 `bot:status` 事件
- `logs: []` — 来自 `bot:log` 事件，每条包含 `{level, message, time}`
- `clearLogs()` — 清空日志列表

### `views/Dashboard.vue` - 控制台

- 启动 / 停止按钮（按 `botStore.running` 禁用）
- **扫码登录**按钮（`loginState` 控制 pending/success/failed 三态）
- `LogViewer` 实时展示日志

### `views/Settings.vue` - 配置编辑

四分组表单 → `config:save` IPC → Python 自动 `reload_config`

### `views/Prompts.vue` - Prompt 编辑

四 Tab（意图分类 / 议价 / 技术 / 默认）→ `prompts:save` IPC

---

## Python 桥接层

### `python/bridge.py` - IPC 桥接入口

**关键类**：`BridgeManager`

- `build_live_instance()` — 从 DB 读取配置，实例化 `XianyuLive` + `XianyuReplyBot` + `ChatContextManager`
- `start_bot()` / `stop_bot()` — 启动/停止 asyncio bot task
- `handle_login()` — 调用 `login_browser.browser_login()`
- `run()` — stdin 命令调度主循环（命令通过独立线程读取，经 `asyncio.Queue` 传入）

**emit 函数**（输出到 stdout）：
```python
emit_status(running: bool)                  # {"type": "status", "running": ...}
emit_error(code: str, message: str)         # {"type": "error", "code": ..., "message": ...}
emit_login_result(success: bool, msg: str)  # {"type": "login_result", ...}
# 日志统一由 stdout_json_sink 处理          # {"type": "log", "level": ..., "message": ..., "time": ...}
```

**新增命令**：在 `run()` 的 `while True` 循环内加 `elif action == "new_cmd":` 分支。

---

### `python/config_manager.py` - SQLite 配置管理

**关键类**：`AppConfigManager(db_path)`

| 方法 | 说明 |
|------|------|
| `seed_defaults(prompt_dir)` | 首次启动写入默认配置和 Prompts（表非空时跳过） |
| `get_config() -> dict` | 读取全部 config 键值 |
| `get_value(key, default)` | 读取单个配置 |
| `set_value(key, value)` | 写入单个配置（upsert） |
| `set_many(data)` | 批量写入配置 |
| `get_all_prompts() -> dict` | 读取全部 prompts |
| `set_many_prompts(data)` | 批量写入 prompts |
| `update_cookies(cookie_str)` | 更新 COOKIES_STR（登录成功后调用） |

**新增配置项**：在 `DEFAULT_CONFIG` 字典中添加 key，同步更新 `Settings.vue`。注意 `seed_defaults` 仅在表为空时生效，对已有 DB 需调用 `set_value` 补写。

**新增 Prompt 类型**：在 `PROMPT_NAMES` 列表中添加，同步更新 `Prompts.vue` Tab。

---

## 通信协议速查

### Python → Electron (stdout JSON lines)

```jsonc
{"type": "log",          "level": "info|debug|warning|error", "message": "...", "time": "ISO"}
{"type": "status",       "running": true}
{"type": "error",        "code": "WIND_CONTROL", "message": "..."}
{"type": "login_result", "success": true, "message": "登录成功，Cookie 已自动保存"}
```

### Electron → Python (stdin JSON lines)

```jsonc
{"cmd": "start"}
{"cmd": "stop"}
{"cmd": "reload_config"}
{"cmd": "login"}
```

---

## 数据存储

| 文件 | 路径 | 用途 |
|------|------|------|
| `app_config.db` | `%APPDATA%\XianyuAutoAgent\` | 配置 + Prompts（Python & Electron 共享） |
| `chat_history.db` | `%APPDATA%\XianyuAutoAgent\` | 聊天记录（Python 独占） |

---

## 构建产物

| 目录 | 内容 |
|------|------|
| `build/python-dist/bridge/` | PyInstaller 打包的 `bridge.exe` 及依赖 |
| `build/electron-dist/win-unpacked/` | electron-builder 解包目录 |
| `build/installer-output/` | Inno Setup 安装包 `.exe` |

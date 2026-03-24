# XianyuAutoAgent 调试指南

---

## 一、开发模式调试

### 前端（Vue 渲染进程）

启动 `npm run dev` 后，Electron 会自动打开 Chrome DevTools。

- **Elements / Console / Network**：标准 DevTools 面板
- 前端 IPC 调用通过 `window.electronAPI.*` 暴露（见 `preload/preload.js`）
- Pinia Store 状态可在 Console 输入 `$pinia` 查看

手动打开 DevTools（若未自动打开）：

```
Ctrl+Shift+I  （Windows）
```

### 主进程（Electron Main）

在 `electron/main/index.js` 中，Electron 以 `--inspect` 模式启动时可用 Node.js 调试器。

临时在代码中加日志：

```js
console.log('[DEBUG]', someVar)
```

日志输出在启动 Electron 的终端窗口中可见。

---

## 二、Python 后端调试

### 查看 Python 日志

所有 Python 日志通过 stdout 以 JSON Lines 格式发送给 Electron，在 UI「日志」面板实时显示。

日志级别：`debug` / `info` / `warning` / `error`

### 独立运行 bridge.py（脱离 Electron）

在开发时可单独测试 Python 逻辑：

```bash
cd python
set BRIDGE_MODE=1
python bridge.py
```

然后手动向 stdin 发送命令（输入后按 Enter）：

```
{"cmd": "start"}
{"cmd": "stop"}
```

### 使用 loguru 输出详细日志

`bridge.py` 和 `main.py` 使用 `loguru`，可临时调低日志级别：

```python
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")
```

### 调试 LLM 路由

在 `XianyuAgent.py` 的 `generate_reply()` 方法中，意图分类结果会写入日志。
关注日志中的 `intent:` 字段，确认消息被路由到正确的 Agent（`price` / `tech` / `default`）。

---

## 三、SQLite 数据库检查

配置数据库路径：`%APPDATA%\XianyuAutoAgent\app_config.db`

使用任意 SQLite 工具（如 [DB Browser for SQLite](https://sqlitebrowser.org/)）打开：

```sql
-- 查看所有配置
SELECT * FROM config;

-- 查看所有提示词
SELECT name, substr(content, 1, 100) FROM prompts;

-- 查看对话历史
SELECT * FROM chat_history ORDER BY created_at DESC LIMIT 20;
```

---

## 四、IPC 通信调试

### 监听 Electron → Python 命令

在 `pythonManager.js` 的 `sendCommand()` 函数中加日志：

```js
function sendCommand(cmd) {
  console.log('[IPC→Python]', JSON.stringify(cmd))
  // ...
}
```

### 监听 Python → Electron 事件

在 `pythonManager.js` 的 readline 回调中加日志：

```js
rl.on('line', (line) => {
  console.log('[Python→IPC]', line)
  // ...
})
```

### 前端监听 IPC 事件

在 Vue 组件或 Store 中：

```js
window.electronAPI.onBotLog((msg) => {
  console.log('[bot:log]', msg)
})
```

---

## 五、WebSocket 调试

WebSocket 连接状态通过 `status` 事件上报：

```json
{"type": "status", "running": true}
{"type": "status", "running": false}
```

排查 WebSocket 断连：

1. 检查 UI 日志中是否有 `Token刷新成功` 或 `连接断开` 关键词
2. 确认 `COOKIES_STR` 未过期（点击「扫码登录」刷新）
3. 检查心跳超时参数：`HEARTBEAT_INTERVAL` / `HEARTBEAT_TIMEOUT`

---

## 六、常见错误排查

| 错误现象 | 排查步骤 |
|---------|---------|
| 前端白屏 | 检查终端 Vite 编译输出；打开 DevTools Console 查看 JS 错误 |
| Python 进程未启动 | 检查终端 `[stderr]` 日志；确认 `python` 命令可用 |
| IPC 无响应 | 确认 `preload.js` 中已注册对应 `contextBridge` API；检查 `ipcHandlers.js` 注册 |
| LLM 不回复 | 确认 `API_KEY` 和 `MODEL_BASE_URL` 正确；检查日志中的 intent 分类结果 |
| 消息被过滤 | 检查安全过滤器日志（`safety filter`）；消息含联系方式会被拦截 |
| SQLite 锁定 | 关闭其他占用 `.db` 文件的进程（如 DB Browser） |

---

## 七、热重载说明

- **前端代码**（`renderer/src/`）：保存即热重载，无需重启
- **主进程代码**（`electron/main/`）：需重启 `npm run dev`
- **Python 代码**（`python/`）：需在 UI 中点击「停止」后「启动」，或重启整个应用
- **配置变更**：通过 UI 保存后，点击「重载配置」按钮（发送 `{"cmd": "reload_config"}` 给 Python）

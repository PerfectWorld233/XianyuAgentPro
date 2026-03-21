# Electron 开发测试工作流

## 环境准备（首次）

```bash
# 1. 安装 Python 依赖（含 playwright）
pip install -r python/requirements.txt
playwright install chromium

# 2. 安装 Electron 依赖
cd electron
npm install
# postinstall 自动执行 electron-rebuild -f -w better-sqlite3
```

---

## 本地开发运行

```bash
cd electron
npm run dev
```

等价于：
```
concurrently
  "vite --config vite.config.js"          # 启动 Vite dev server (port 5173)
  "wait-on http://localhost:5173 &&
   cross-env VITE_DEV_SERVER_URL=http://localhost:5173 electron ."
```

- Electron 检测到 `VITE_DEV_SERVER_URL` → 加载该 URL 并自动打开 DevTools
- Python bridge 以 `python python/bridge.py` 形式启动（非打包模式）
- Vue 修改后 Vite 热更新，刷新 Electron 渲染进程即可看到变化
- 主进程 (`main/index.js`) 修改需要重启 `npm run dev`

---

## 调试指南

### 调试渲染进程（Vue）

开发模式下 DevTools 自动打开，直接使用：
- **Console** — 查看 `console.log`、Vue 警告
- **Vue DevTools**（需安装扩展）— 查看组件树、Pinia store 状态
- **Network** — 观察 IPC 调用（无实际网络请求，但可用于检查资源加载）

### 调试主进程（Node.js）

在终端窗口直接查看 `npm run dev` 的输出，主进程 `console.log` 输出在此。

也可以用 VSCode 启动调试：
```json
// .vscode/launch.json
{
  "type": "node",
  "request": "launch",
  "name": "Electron Main",
  "runtimeExecutable": "${workspaceFolder}/electron/node_modules/.bin/electron",
  "args": [".", "--inspect=5858"],
  "cwd": "${workspaceFolder}/electron",
  "env": { "VITE_DEV_SERVER_URL": "http://localhost:5173" }
}
```

### 调试 Python bridge

开发模式下 Python 进程的 stdout 被 Electron 消费，stderr 输出到终端。

单独测试 bridge（无 Electron）：
```bash
cd python
# 发送 start 命令后 Ctrl+C 退出
echo '{"cmd":"start"}' | python bridge.py

# 测试扫码登录（会弹出 Chromium）
echo '{"cmd":"login"}' | python bridge.py
```

---

## 常见开发任务

### 任务 1：新增 IPC 通道

**必须同时修改三处**：

**① `electron/main/ipcHandlers.js`**
```js
ipcMain.handle('myfeature:action', (_event, data) => {
  // 处理逻辑
  return { ok: true }
})
```

**② `electron/preload/preload.js`**
```js
myFeatureAction: (data) => ipcRenderer.invoke('myfeature:action', data),
onMyFeatureEvent: (cb) => ipcRenderer.on('myfeature:event', (_e, msg) => cb(msg)),
```

**③ Vue 组件中调用**
```js
const result = await window.electronAPI.myFeatureAction(data)
```

---

### 任务 2：新增 Python → Electron 推送消息类型

**必须同时修改两处**：

**① `electron/main/pythonManager.js`**
```js
// listeners 字典加入新 type
const listeners = { log: [], status: [], error: [], login_result: [], my_new_type: [] }
```
> `dispatch()` 会自动按 `bot:<type>` 转发，无需其他修改。

**② `python/bridge.py`**
```python
def emit_my_new_type(data):
    payload = {"type": "my_new_type", ...data}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
```

**③ `electron/preload/preload.js`**
```js
onMyNewType: (cb) => ipcRenderer.on('bot:my_new_type', (_e, msg) => cb(msg)),
```

---

### 任务 3：修改配置 schema

配置存储在 SQLite `app_config.db` 的 `config` 表，Python 和 Electron 共享同一文件。

修改时需同步：
- `python/config_manager.py` — `DEFAULT_CONFIG` 字典加入新 key 及默认值（`seed_defaults()` 仅在表为空时执行，已有 DB 需用 `set_value` 手动写入或清库重启）
- `electron/main/dbManager.js` — `getConfig()` / `saveConfig()` 逻辑（通常无需改）
- `electron/renderer/src/views/Settings.vue` — 表单新增对应输入项

---

### 任务 4：新增 bridge 命令或推送消息类型

**新增 Electron → Python 命令**：
1. `python/bridge.py` `BridgeManager.run()` — 在命令分发 `if action == ...` 分支中添加处理逻辑
2. `electron/main/ipcHandlers.js` — 新增 IPC 通道，调用 `sendCommand({cmd: 'new_cmd'})`
3. `electron/preload/preload.js` + Vue 组件 — 同步暴露和调用

**新增 Python → Electron 推送消息类型**：
1. `python/bridge.py` — 添加 `emit_xxx()` 函数：
   ```python
   def emit_xxx(data):
       payload = {"type": "xxx", ...}
       sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
       sys.stdout.flush()
   ```
2. `electron/main/pythonManager.js` `listeners` 字典 — 加入 `xxx: []`
3. `electron/preload/preload.js` — 暴露 `onXxx: (cb) => ipcRenderer.on('bot:xxx', (_e, msg) => cb(msg))`
4. Vue 组件 — 调用 `window.electronAPI.onXxx(cb)`

---

### 任务 4：修改前端 UI 样式

项目使用原生 CSS（`<style scoped>`），无 CSS 框架依赖。

全局颜色变量定义在 `App.vue` 或各组件内。常用颜色参考：
```css
/* 主色调 */
--blue:   #4a9eff
--green:  #a6e3a1
--red:    #f38ba8
--gray:   #e2e8f0
--text:   #1e2030
--muted:  #475569
```

---

## 打包与构建

### 全量打包（推荐）

```bat
scripts\build-all.bat
```

### 分步打包

```bat
# Step 1: Python bridge（PyInstaller）
scripts\build-python.bat
# 输出: build\python-dist\bridge\bridge.exe

# Step 2: Vue 渲染进程（Vite）
cd electron
npm run build:renderer
# 输出: electron\renderer\dist\

# Step 3: Electron 打包（electron-builder）
npm run build:electron
# 输出: build\electron-dist\win-unpacked\

# Step 4: 制作安装包（需安装 Inno Setup 6）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
# 输出: build\installer-output\XianyuAutoAgent-Setup-x.x.x.exe
```

### electron-builder 配置

`electron/electron-builder.yml` 关键配置：
```yaml
target: dir    # 输出解包目录（供 Inno Setup 消费）
extraResources:
  - from: ../build/python-dist/bridge/
    to: python-dist/bridge/
```

> 生产环境 Python 可执行文件路径：`process.resourcesPath + '/python-dist/bridge/bridge.exe'`

---

## 问题排查速查表

| 问题 | 排查位置 | 常见原因 |
|------|---------|---------|
| Python 进程没有启动 | `pythonManager.js` `startPython()` | Python 路径错误；`spawn` 失败 |
| 日志不显示在 UI | `botStore.js` + `pythonManager.js` | listeners 缺少对应 type key |
| IPC invoke 返回 undefined | `ipcHandlers.js` | handler 没有 return 值 |
| 配置保存后未生效 | `dbManager.js` + `bridge.py` | `reload_config` 未触发；db 路径不一致 |
| `better-sqlite3` 报 MODULE_NOT_FOUND | `electron/` 目录 | 需重新 `npm install` + electron-rebuild |
| 打包后白屏 | `electron-builder.yml` | `renderer/dist/` 未构建；路径配置错误 |
| 扫码登录无反应 | `login_browser.py` | playwright 未安装；`unb` cookie 轮询超时 |
| 安装包缺少 Python 文件 | `electron-builder.yml` `extraResources` | python-dist 路径配置不正确 |

---

## 调试技巧

### 查看 SQLite 数据库内容

```bash
# Windows 需安装 sqlite3 CLI 或使用 DB Browser for SQLite
sqlite3 "%APPDATA%\XianyuAutoAgent\app_config.db"
.tables
SELECT * FROM config;
SELECT * FROM prompts;
```

### 手动验证 Python bridge

```bash
cd python
python -c "
import asyncio
from config_manager import AppConfigManager
import os

db = os.path.join(os.environ['APPDATA'], 'XianyuAutoAgent', 'app_config.db')
m = AppConfigManager(db)
print(m.get_config())
"
```

### 检查 Electron 主进程内存 / 崩溃

开发模式终端直接查看异常堆栈，生产模式崩溃日志位于：
```
%APPDATA%\XianyuAutoAgent\Crashpad\
```

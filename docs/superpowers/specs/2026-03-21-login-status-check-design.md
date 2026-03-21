# 闲鱼登录状态检测 — 设计文档

**日期**: 2026-03-21
**状态**: 已批准

---

## 需求背景

当前应用启动后直接进入控制台，没有检查用户是否已登录闲鱼。若 Cookie 未配置或已失效，用户点击「启动」才会报错，体验差。

**目标**: 应用启动及定期运行时自动检测登录状态，未登录时在控制台顶部显示提示横幅引导用户扫码登录。

---

## 设计决策

| 问题 | 决策 |
|------|------|
| 如何检测登录状态 | 本地快检（Cookie 含 `unb`）+ 异步 HTTP 验证双重策略 |
| 触发时机 | 启动时 + 每小时定期轮询 |
| 登录引导 UI | Dashboard 顶部嵌入式提示横幅（不跳转路由，不弹窗） |

---

## 架构

```
用户启动应用
  └─► App.vue onMounted
        ├─ 注册 onLoginStatus 回调 → botStore.setLoginStatus(...)
        ├─ checkLogin() ──► IPC: bot:check_login
        └─ setInterval(checkLogin, 3600000)  // 每小时轮询

IPC: bot:check_login
  └─► Python bridge: {"cmd": "check_login"}
        ├─ 快检: COOKIES_STR 含非空 unb 字段？
        │    否 → emit login_status(false, "")，停止
        └─ 实例化临时 XianyuApis，加载 cookies_str
             └─ 调用已有 hasLogin() → GET https://passport.goofish.com/newlogin/hasLogin.do
                  ├─ 已登录 → emit login_status(true, username)
                  └─ 否 → emit login_status(false, "")

Python stdout emit {"type": "login_status", ...}
  └─► pythonManager.js dispatch（listeners.login_status 路由）
        └─► mainWindow.webContents.send('bot:login_status', payload)
              └─► App.vue onLoginStatus 回调
                    └─► botStore.setLoginStatus(status, username)
                          └─► Dashboard.vue 响应式渲染横幅
```

---

## 各层变更说明

### 1. `python/XianyuApis.py`

新增方法 `check_login_status(cookies_str: str) -> tuple[bool, str]`：

1. 快检：解析 `cookies_str`，查找 `unb=` 且值非空；失败则直接返回 `(False, "")`
2. 实例化临时 `XianyuApis`，将 `cookies_str` 加载到其 `session`（与现有 `XianyuApis.__init__` 中 `_load_cookies` 同样逻辑）
3. 调用已有的 `self.hasLogin()`（GET `https://passport.goofish.com/newlogin/hasLogin.do`），超时 5 秒
4. 解析响应 JSON，返回 `(True, username)` 或 `(False, "")`

> **注意**：`BridgeManager` 不持久化 `XianyuApis` 实例（实例在 `build_live_instance()` 内部创建），因此 `check_login_status` 每次调用时创建临时实例，不依赖 bot 是否运行。

### 2. `python/bridge.py`

新增输出函数：
```python
def emit_login_status(logged_in: bool, username: str):
    payload = {"type": "login_status", "logged_in": logged_in, "username": username}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
```

在命令分发循环中新增：
```python
elif action == "check_login":
    asyncio.create_task(self.handle_check_login())
```

新增方法 `handle_check_login()`：读取 `COOKIES_STR`，调用 `XianyuApis.check_login_status()`，然后 `emit_login_status()`。

### 3. `electron/main/pythonManager.js`

在 `listeners` 对象中新增 `login_status` 条目，使 dispatch 能路由该事件类型到 renderer：

```js
const listeners = {
  log: [],
  status: [],
  error: [],
  login_result: [],
  login_status: [],   // 新增
}
```

### 4. `electron/main/ipcHandlers.js`

新增：
```js
ipcMain.handle('bot:check_login', () => {
  sendCommand({ cmd: 'check_login' })
})
```

### 5. `electron/preload/preload.js`

新增两个 API：
```js
checkLogin: () => ipcRenderer.invoke('bot:check_login'),
onLoginStatus: (cb) => ipcRenderer.on('bot:login_status', (_event, msg) => cb(msg)),
```

### 6. `electron/renderer/src/stores/botStore.js`

新增状态和 action：
```js
loginStatus: 'unknown',   // 'unknown' | 'checking' | 'logged_in' | 'logged_out'
loginUsername: '',

setLoginStatus(status, username = '') {
  this.loginStatus = status
  this.loginUsername = username
}
```

### 7. `electron/renderer/src/App.vue`

`onMounted` 中：
1. 注册 `onLoginStatus` 回调 → `botStore.setLoginStatus(msg.logged_in ? 'logged_in' : 'logged_out', msg.username)`
2. 调用 `botStore.setLoginStatus('checking')` 后调用 `checkLogin()`
3. 设置每小时定时器（保存 timer id）

`onUnmounted` 中：
1. 清除定时器
2. `removeAllListeners('bot:login_status')`

> `checkLogin()` 和定时器统一在 `App.vue` 管理，`Dashboard.vue` 仅通过 `botStore` 读取状态。

### 8. `electron/renderer/src/views/Dashboard.vue`

- 从 `botStore` 读取 `loginStatus` 和 `loginUsername`
- 顶部横幅逻辑：
  - `checking` → 灰色横幅「正在检测登录状态…」
  - `logged_out` → 橙色横幅「未检测到闲鱼登录，请先扫码登录才能启动机器人 [立即扫码登录]」
  - `logged_in` → 不显示横幅（或绿色小徽章「已登录」）
  - `unknown` → 不显示横幅
- 「立即扫码登录」按钮复用现有 `doLogin()` 逻辑
- 登录成功后（`onLoginResult` success）：`botStore.setLoginStatus('checking')`，然后调用 `window.electronAPI.checkLogin()`

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| Python 进程未就绪时调用 `check_login` | IPC 调用使用 `Promise.race([invoke, timeout(5000)])`，超时后 `loginStatus` 保持 `unknown` |
| HTTP 请求网络超时 | Python 侧 5s 超时，返回 `(False, "")`，前端显示未登录横幅 |
| Cookie 格式异常或无 `unb` | 快检失败，直接返回 `(False, "")`，跳过 HTTP 请求 |
| 已登录后 Cookie 被撤销 | 每小时轮询检测到 `logged_out`，横幅重新出现 |

---

## 测试要点

- [ ] 首次安装（无 Cookie）：启动后立即显示未登录横幅
- [ ] 有效 Cookie：启动后横幅隐藏，显示已登录状态
- [ ] 过期 Cookie（有 `unb` 但 HTTP 验证失败）：显示未登录横幅
- [ ] 扫码登录成功后：横幅自动消失，`checkLogin` 自动重新触发
- [ ] 每小时轮询：Cookie 失效时横幅重新出现
- [ ] `onLoginStatus` 监听在组件卸载时正确清除

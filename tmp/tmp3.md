Plan to implement                                                                                                    │
│                                                                                                                      │
│ 计划：XianyuAutoAgent 改造为 PC 桌面应用                                                                             │
│                                                                                                                      │
│ 背景                                                                                                                 │
│                                                                                                                      │
│ 将 XianyuAutoAgent（Python WebSocket 闲鱼客服机器人）改造为 Windows 桌面软件。                                       │
│ - 前端：Electron + Vue 3 + Vite                                                                                      │
│ - 通信：stdio 管道（JSON 行协议）                                                                                    │
│ - 配置存储：SQLite（原 .env 变量 + prompts 文件内容全部入库）                                                        │
│ - Python 入口：新建 bridge.py 封装                                                                                   │
│ - 打包：PyInstaller → electron-builder → Inno Setup                                                                  │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 最终目录结构                                                                                                         │
│                                                                                                                      │
│ XianyuAutoAgent/                                                                                                     │
│ ├── python/                    # Python 后端（复制/重构原有文件）                                                    │
│ │   ├── bridge.py              # NEW: IPC 桥接入口                                                                   │
│ │   ├── config_manager.py      # NEW: SQLite 配置 CRUD                                                               │
│ │   ├── main.py                # MODIFY: 接受 config dict 而非 os.getenv                                             │
│ │   ├── XianyuAgent.py         # MODIFY: 接受 config/prompt_overrides dict                                           │
│ │   ├── XianyuApis.py          # MODIFY: 支持 config_manager 回写 cookies                                            │
│ │   ├── context_manager.py     # 不改动                                                                              │
│ │   ├── utils/                                                                                                       │
│ │   │   └── xianyu_utils.py    # 不改动                                                                              │
│ │   ├── prompts/               # 保留为种子数据（example txt 文件）                                                  │
│ │   ├── requirements.txt       # 新增 pyinstaller                                                                    │
│ │   └── bridge.spec            # PyInstaller spec                                                                    │
│ │                                                                                                                    │
│ ├── electron/                  # Electron 壳 + Vue 3 前端                                                            │
│ │   ├── package.json                                                                                                 │
│ │   ├── vite.config.js                                                                                               │
│ │   ├── electron-builder.yml                                                                                         │
│ │   ├── main/                                                                                                        │
│ │   │   ├── index.js           # Electron 主进程                                                                     │
│ │   │   ├── pythonManager.js   # 子进程管理 + stdio 解析                                                             │
│ │   │   ├── ipcHandlers.js     # IPC 通道注册                                                                        │
│ │   │   └── dbManager.js       # better-sqlite3 操作（主进程侧）                                                     │
│ │   ├── preload/                                                                                                     │
│ │   │   └── preload.js         # contextBridge API                                                                   │
│ │   └── renderer/              # Vue 3 SPA                                                                           │
│ │       ├── index.html                                                                                               │
│ │       └── src/                                                                                                     │
│ │           ├── main.js                                                                                              │
│ │           ├── App.vue        # 侧边导航布局                                                                        │
│ │           ├── router/index.js                                                                                      │
│ │           ├── stores/                                                                                              │
│ │           │   ├── botStore.js                                                                                      │
│ │           │   └── configStore.js                                                                                   │
│ │           ├── components/                                                                                          │
│ │           │   ├── LogViewer.vue                                                                                    │
│ │           │   └── StatusBadge.vue                                                                                  │
│ │           └── views/                                                                                               │
│ │               ├── Dashboard.vue  # 启动/停止 + 实时日志                                                            │
│ │               ├── Settings.vue   # 配置编辑器                                                                      │
│ │               └── Prompts.vue    # 4 个 prompt 文本编辑器                                                          │
│ │                                                                                                                    │
│ ├── installer/                                                                                                       │
│ │   └── setup.iss              # Inno Setup 脚本                                                                     │
│ │                                                                                                                    │
│ ├── scripts/                                                                                                         │
│ │   ├── build-python.bat       # PyInstaller 打包                                                                    │
│ │   └── build-all.bat          # 全量构建流水线                                                                      │
│ │                                                                                                                    │
│ └── build/                     # 构建输出（gitignore）                                                               │
│     ├── python-dist/           # PyInstaller 输出                                                                    │
│     ├── electron-dist/         # electron-builder 输出                                                               │
│     └── installer-output/      # Inno Setup 输出                                                                     │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第一步：新建 python/config_manager.py                                                                                │
│                                                                                                                      │
│ 数据库路径：%APPDATA%\XianyuAutoAgent\app_config.db（与聊天记录库分离）                                              │
│                                                                                                                      │
│ 表结构                                                                                                               │
│                                                                                                                      │
│ -- 配置键值表                                                                                                        │
│ CREATE TABLE IF NOT EXISTS config (                                                                                  │
│     key TEXT PRIMARY KEY NOT NULL,                                                                                   │
│     value TEXT NOT NULL,                                                                                             │
│     updated_at DATETIME DEFAULT CURRENT_TIMESTAMP                                                                    │
│ );                                                                                                                   │
│                                                                                                                      │
│ -- Prompt 内容表                                                                                                     │
│ CREATE TABLE IF NOT EXISTS prompts (                                                                                 │
│     name TEXT PRIMARY KEY NOT NULL,                                                                                  │
│     content TEXT NOT NULL,                                                                                           │
│     updated_at DATETIME DEFAULT CURRENT_TIMESTAMP                                                                    │
│ );                                                                                                                   │
│                                                                                                                      │
│ AppConfigManager 方法                                                                                                │
│                                                                                                                      │
│ - __init__(db_path) — 建连接，建表，调 seed_defaults                                                                 │
│ - seed_defaults(prompt_dir) — 若表为空则写入 12 个默认配置 + 读 *_example.txt 写入 4 个 prompt                       │
│ - get_config() -> dict — 返回全部键值                                                                                │
│ - get_value(key, default='') -> str                                                                                  │
│ - set_value(key, value) / set_many(data: dict)                                                                       │
│ - get_prompt(name) -> str / get_all_prompts() -> dict                                                                │
│ - set_prompt(name, content) / set_many_prompts(data: dict)                                                           │
│ - update_cookies(cookie_str) — 替换 update_env_cookies()                                                             │
│                                                                                                                      │
│ 默认配置种子                                                                                                         │
│                                                                                                                      │
│ ┌────────────────────────┬───────────────────────────────────────────────────┐                                       │
│ │          key           │                      默认值                       │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ API_KEY                │ (空)                                              │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ COOKIES_STR            │ (空)                                              │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ MODEL_BASE_URL         │ https://dashscope.aliyuncs.com/compatible-mode/v1 │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ MODEL_NAME             │ qwen-max                                          │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ TOGGLE_KEYWORDS        │ 。                                                │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ SIMULATE_HUMAN_TYPING  │ False                                             │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ HEARTBEAT_INTERVAL     │ 15                                                │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ HEARTBEAT_TIMEOUT      │ 5                                                 │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ TOKEN_REFRESH_INTERVAL │ 3600                                              │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ TOKEN_RETRY_INTERVAL   │ 300                                               │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ MANUAL_MODE_TIMEOUT    │ 3600                                              │                                       │
│ ├────────────────────────┼───────────────────────────────────────────────────┤                                       │
│ │ MESSAGE_EXPIRE_TIME    │ 300000                                            │                                       │
│ └────────────────────────┴───────────────────────────────────────────────────┘                                       │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第二步：修改 python/XianyuApis.py                                                                                    │
│                                                                                                                      │
│ 改动 1：__init__ 接受可选 config_manager=None 参数。                                                                 │
│                                                                                                                      │
│ 改动 2：update_env_cookies() 判断 BRIDGE_MODE 环境变量：                                                             │
│ def update_env_cookies(self):                                                                                        │
│     cookie_str = '; '.join([f"{c.name}={c.value}" for c in self.session.cookies])                                    │
│     if self.config_manager:                                                                                          │
│         self.config_manager.update_cookies(cookie_str)                                                               │
│         return                                                                                                       │
│     # 原有 .env 写入逻辑保留（开发者直接跑 main.py 时用）                                                            │
│                                                                                                                      │
│ 改动 3：get_token() 中原来调用 input() 等待用户输入 cookie 的交互逻辑，在 BRIDGE_MODE='1' 时改为：                   │
│ if os.environ.get('BRIDGE_MODE') == '1':                                                                             │
│     # 向 stdout 发送结构化错误，让 Electron 引导用户去设置页更新 Cookie                                              │
│     print(json.dumps({"type":"error","code":"WIND_CONTROL",                                                          │
│           "message":"触发风控，请在设置页面更新Cookie后重新启动机器人"}), flush=True)                                │
│     sys.exit(1)                                                                                                      │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第三步：修改 python/XianyuAgent.py                                                                                   │
│                                                                                                                      │
│ 改动 1：XianyuReplyBot.__init__ 签名：                                                                               │
│ def __init__(self, config: dict, prompt_overrides: dict = None):                                                     │
│                                                                                                                      │
│ 改动 2：OpenAI 客户端改为从 config 读取：                                                                            │
│ self.client = OpenAI(                                                                                                │
│     api_key=config.get("API_KEY"),                                                                                   │
│     base_url=config.get("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),                      │
│ )                                                                                                                    │
│ self.config = config                                                                                                 │
│                                                                                                                      │
│ 改动 3：_init_system_prompts 接受 prompt_overrides dict，若非 None 则从 dict                                         │
│ 加载，否则走原有文件加载逻辑（保持开发兼容性）。                                                                     │
│                                                                                                                      │
│ 改动 4：_call_llm 中 os.getenv("MODEL_NAME", "qwen-max") → self.config.get("MODEL_NAME", "qwen-max")                 │
│                                                                                                                      │
│ 改动 5：reload_prompts(prompt_overrides=None) 接受新参数。                                                           │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第四步：修改 python/main.py                                                                                          │
│                                                                                                                      │
│ 改动 1：XianyuLive.__init__ 签名：                                                                                   │
│ def __init__(self, cookies_str: str, config: dict, config_manager=None):                                             │
│                                                                                                                      │
│ 改动 2：构造函数中 8 处 os.getenv(KEY, default) 全部替换为 config.get(KEY, default)：                                │
│ - HEARTBEAT_INTERVAL（行 31）                                                                                        │
│ - HEARTBEAT_TIMEOUT（行 32）                                                                                         │
│ - TOKEN_REFRESH_INTERVAL（行 39）                                                                                    │
│ - TOKEN_RETRY_INTERVAL（行 40）                                                                                      │
│ - MANUAL_MODE_TIMEOUT（行 48）                                                                                       │
│ - MESSAGE_EXPIRE_TIME（行 52）                                                                                       │
│ - TOGGLE_KEYWORDS（行 55）                                                                                           │
│ - SIMULATE_HUMAN_TYPING（行 58）                                                                                     │
│                                                                                                                      │
│ 改动 3：self.xianyu = XianyuApis(config_manager=config_manager) 传入 config_manager。                                │
│                                                                                                                      │
│ 改动 4：ChatContextManager 使用绝对路径（由 bridge.py 注入）：接受 db_path 参数传给                                  │
│ ChatContextManager(db_path=db_path)。                                                                                │
│                                                                                                                      │
│ 不改动：if __name__ == '__main__' 块保留，用于开发者直接 python main.py（读 .env）。                                 │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第五步：新建 python/bridge.py                                                                                        │
│                                                                                                                      │
│ 职责                                                                                                                 │
│                                                                                                                      │
│ 1. 确定 %APPDATA%\XianyuAutoAgent\ 路径，创建目录                                                                    │
│ 2. 实例化 AppConfigManager，调用 seed_defaults                                                                       │
│ 3. 安装 loguru 自定义 sink → 将每条日志 JSON 化输出到 stdout                                                         │
│ 4. 启动 asyncio 事件循环                                                                                             │
│ 5. 在独立线程中读 stdin（Windows 上 asyncio 读 stdin 有兼容问题）                                                    │
│ 6. 通过 asyncio.Queue 在主循环中调度命令（start/stop/reload_config）                                                 │
│ 7. 管理 XianyuLive.main() asyncio Task 的生命周期                                                                    │
│                                                                                                                      │
│ Stdout JSON Sink                                                                                                     │
│                                                                                                                      │
│ def stdout_json_sink(message):                                                                                       │
│     record = message.record                                                                                          │
│     payload = {                                                                                                      │
│         "type": "log",                                                                                               │
│         "level": record["level"].name.lower(),                                                                       │
│         "message": record["message"],                                                                                │
│         "time": record["time"].isoformat(),                                                                          │
│     }                                                                                                                │
│     sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")                                                 │
│     sys.stdout.flush()                                                                                               │
│                                                                                                                      │
│ Windows 安全的 stdin 读取（独立线程）                                                                                │
│                                                                                                                      │
│ def stdin_thread(cmd_queue, loop):                                                                                   │
│     for line in sys.stdin:                                                                                           │
│         line = line.strip()                                                                                          │
│         if line:                                                                                                     │
│             try:                                                                                                     │
│                 cmd = json.loads(line)                                                                               │
│                 loop.call_soon_threadsafe(cmd_queue.put_nowait, cmd)                                                 │
│             except:                                                                                                  │
│                 pass                                                                                                 │
│                                                                                                                      │
│ 命令调度                                                                                                             │
│                                                                                                                      │
│ - {"cmd":"start"} → 若未运行则加载配置、实例化 bot、启动 asyncio Task                                                │
│ - {"cmd":"stop"} → cancel Task，等待完成（最多 5s），发 {"type":"status","running":false}                            │
│ - {"cmd":"reload_config"} → stop → 重新加载配置 → 重新实例化 → start                                                 │
│                                                                                                                      │
│ PyInstaller 资源路径                                                                                                 │
│                                                                                                                      │
│ def get_resource_path(rel):                                                                                          │
│     if hasattr(sys, '_MEIPASS'):                                                                                     │
│         return os.path.join(sys._MEIPASS, rel)                                                                       │
│     return os.path.join(os.path.dirname(__file__), rel)                                                              │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第六步：Electron 主进程                                                                                              │
│                                                                                                                      │
│ electron/main/index.js                                                                                               │
│                                                                                                                      │
│ - 创建 BrowserWindow（1100×700，最小 800×600）                                                                       │
│ - 调用 app.setPath('userData', ...) 统一数据目录                                                                     │
│ - 加载 Vite dev URL（开发）或 renderer/dist/index.html（生产）                                                       │
│ - 引入并初始化 pythonManager、ipcHandlers、dbManager                                                                 │
│                                                                                                                      │
│ electron/main/pythonManager.js                                                                                       │
│                                                                                                                      │
│ // spawn 选项                                                                                                        │
│ const proc = spawn(exe, args, {                                                                                      │
│   env: { ...process.env, PYTHONUNBUFFERED: '1', BRIDGE_MODE: '1' },                                                  │
│   stdio: ['pipe', 'pipe', 'pipe'],                                                                                   │
│ })                                                                                                                   │
│                                                                                                                      │
│ // 逐行解析 stdout                                                                                                   │
│ const rl = readline.createInterface({ input: proc.stdout })                                                          │
│ rl.on('line', onLine)                                                                                                │
│                                                                                                                      │
│ // onLine 解析 JSON：type=log/status/error 分发到对应 IPC push                                                       │
│                                                                                                                      │
│ Python 可执行文件路径：                                                                                              │
│ - 开发：python bridge.py                                                                                             │
│ - 生产：path.join(process.resourcesPath, 'python-dist/bridge/bridge.exe')                                            │
│                                                                                                                      │
│ electron/main/dbManager.js                                                                                           │
│                                                                                                                      │
│ 使用 better-sqlite3（同步，无回调）在主进程直接读写 app_config.db：                                                  │
│ - getConfig() -> object                                                                                              │
│ - saveConfig(data) — 批量 UPDATE                                                                                     │
│ - getPrompts() -> object                                                                                             │
│ - savePrompts(data) — 批量 UPDATE                                                                                    │
│                                                                                                                      │
│ 数据库路径与 Python 侧一致：app.getPath('appData') + '/XianyuAutoAgent/app_config.db'                                │
│                                                                                                                      │
│ electron/main/ipcHandlers.js                                                                                         │
│                                                                                                                      │
│ ┌──────────────┬─────────────────┬──────────────────────────────────────────────────────────────────┐                │
│ │     通道     │      方向       │                               实现                               │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ bot:start    │ 渲染→主         │ pythonManager.sendCommand({cmd:'start'})                         │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ bot:stop     │ 渲染→主         │ pythonManager.sendCommand({cmd:'stop'})                          │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ bot:status   │ 主→渲染（push） │ Python status 事件触发                                           │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ bot:log      │ 主→渲染（push） │ Python log 事件触发                                              │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ bot:error    │ 主→渲染（push） │ Python error 事件触发                                            │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ config:get   │ 渲染→主         │ dbManager.getConfig()                                            │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ config:save  │ 渲染→主         │ dbManager.saveConfig(data) + sendCommand({cmd:'reload_config'})  │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ prompts:get  │ 渲染→主         │ dbManager.getPrompts()                                           │                │
│ ├──────────────┼─────────────────┼──────────────────────────────────────────────────────────────────┤                │
│ │ prompts:save │ 渲染→主         │ dbManager.savePrompts(data) + sendCommand({cmd:'reload_config'}) │                │
│ └──────────────┴─────────────────┴──────────────────────────────────────────────────────────────────┘                │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第七步：Preload 脚本                                                                                                 │
│                                                                                                                      │
│ electron/preload/preload.js 通过 contextBridge 暴露：                                                                │
│ - botStart() / botStop()                                                                                             │
│ - onBotStatus(cb) / onBotLog(cb) / onBotError(cb)                                                                    │
│ - removeAllListeners(channel)                                                                                        │
│ - getConfig() / saveConfig(data)                                                                                     │
│ - getPrompts() / savePrompts(data)                                                                                   │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第八步：Vue 3 前端                                                                                                   │
│                                                                                                                      │
│ App.vue 布局                                                                                                         │
│                                                                                                                      │
│ 左侧固定导航栏（三个路由链接）+ 右侧 <router-view>                                                                   │
│                                                                                                                      │
│ Dashboard.vue                                                                                                        │
│                                                                                                                      │
│ - StatusBadge.vue：绿色"运行中" / 红色"已停止"                                                                       │
│ - 启动 / 停止按钮（按状态禁用）                                                                                      │
│ - 清空日志按钮                                                                                                       │
│ - LogViewer.vue：滚动区域，按 level 着色，自动滚底，可手动滚回查看历史                                               │
│                                                                                                                      │
│ Settings.vue                                                                                                         │
│                                                                                                                      │
│ 分四组表单：                                                                                                         │
│ 1. 必填：API_KEY（密码框+显示切换）、COOKIES_STR（textarea）                                                         │
│ 2. 模型：MODEL_BASE_URL、MODEL_NAME（含下拉建议）                                                                    │
│ 3. 行为：TOGGLE_KEYWORDS、SIMULATE_HUMAN_TYPING（toggle）                                                            │
│ 4. 高级（可折叠）：6 个数字型配置                                                                                    │
│                                                                                                                      │
│ 底部：保存按钮（调用 config:save IPC，触发 reload_config）                                                           │
│                                                                                                                      │
│ Prompts.vue                                                                                                          │
│                                                                                                                      │
│ Tab 页签：意图分类 / 价格谈判 / 技术咨询 / 默认回复                                                                  │
│ 每 tab：<textarea> 等宽字体 + 字符计数 + "恢复默认"按钮                                                              │
│ 底部：保存按钮                                                                                                       │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第九步：PyInstaller 打包                                                                                             │
│                                                                                                                      │
│ python/bridge.spec 关键配置：                                                                                        │
│ a = Analysis(['bridge.py'], ...)                                                                                     │
│ # console=True 是必须的（Electron 读取 stdout）                                                                      │
│ exe = EXE(..., console=True, ...)                                                                                    │
│ # datas 包含 prompts/*.txt 作为种子数据                                                                              │
│ datas=[('prompts/*.txt', 'prompts')]                                                                                 │
│ # hiddenimports 包含所有项目模块和 openai/websockets 动态导入                                                        │
│                                                                                                                      │
│ 构建命令：                                                                                                           │
│ pyinstaller bridge.spec --distpath ..\build\python-dist --workpath ..\build\python-work --clean                      │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第十步：Electron 打包配置                                                                                            │
│                                                                                                                      │
│ electron/electron-builder.yml：                                                                                      │
│ target: dir   # 输出解包目录供 Inno Setup 消费                                                                       │
│ extraResources:                                                                                                      │
│   - from: ../build/python-dist/bridge/                                                                               │
│     to: python-dist/bridge/                                                                                          │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第十一步：Inno Setup 脚本                                                                                            │
│                                                                                                                      │
│ installer/setup.iss 关键点：                                                                                         │
│ - 源：build/electron-dist/win-unpacked/*                                                                             │
│ - 目标：{autopf}\XianyuAutoAgent                                                                                     │
│ - 用户数据（%APPDATA%\XianyuAutoAgent\）卸载时不删除（保留聊天记录和配置）                                           │
│ - 中文界面支持（ChineseSimplified.isl）                                                                              │
│ - 桌面快捷方式可选                                                                                                   │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 第十二步：全量构建脚本                                                                                               │
│                                                                                                                      │
│ scripts/build-all.bat：                                                                                              │
│ 1. PyInstaller → build/python-dist/                                                                                  │
│ 2. Vite build → electron/renderer/dist/                                                                              │
│ 3. electron-builder → build/electron-dist/win-unpacked/                                                              │
│ 4. Inno Setup ISCC → build/installer-output/XianyuAutoAgent-Setup-x.x.x.exe                                          │
│                                                                                                                      │
│ ---                                                                                                                  │
│ 关键注意事项                                                                                                         │
│                                                                                                                      │
│ 1. better-sqlite3 需重编译：npm postinstall 运行 electron-rebuild -f -w better-sqlite3                               │
│ 2. PyInstaller console=True：必须，否则 Electron 读不到 stdout                                                       │
│ 3. PYTHONUNBUFFERED=1：Electron spawn 时在 env 中设置，确保 flush 实时                                               │
│ 4. Windows stdin asyncio 兼容：用独立线程 + loop.call_soon_threadsafe 替代 asyncio.connect_read_pipe                 │
│ 5. PyInstaller 资源路径：使用 sys._MEIPASS 查找 prompts 种子文件                                                     │
│ 6. ChatContextManager db_path：bridge.py 中传入绝对路径（APPDATA 目录）                                              │
│ 7. main.py 保持向后兼容：if __name__ == '__main__' 块保留，开发者仍可直接 python main.py + .env                      │
│                                                                                                                      │
│ 实施顺序                                                                                                             │
│                                                                                                                      │
│ 1. config_manager.py → 2. XianyuApis.py → 3. XianyuAgent.py → 4. main.py → 5. bridge.py → 6. 测试 Python 栈 → 7.     │
│ bridge.spec + 打包测试 → 8. Electron 主进程框架 → 9. IPC 通道 → 10. preload → 11. Vue 3 UI → 12. electron-builder →  │
│ 13. Inno Setup → 14. 全量构建测试                   
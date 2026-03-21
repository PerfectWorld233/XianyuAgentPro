# 项目结构和文件职责

## 核心文件

### `main.py` - 主入口和 WebSocket 连接管理
**职责**：
- 应用启动和初始化
- WebSocket 连接建立
- 消息接收和路由
- Token 刷新管理
- 心跳保活机制
- 人工/自动模式切换
- 连接重启和错误处理

**关键类**：`XianyuLive`

**常见修改**：
- 调整心跳间隔 (`HEARTBEAT_INTERVAL`)
- 修改消息过滤逻辑 (`is_chat_message()`, `is_system_message()` 等)
- 改进重连策略
- 添加新的消息类型判断

### `XianyuAgent.py` - LLM 回复生成和路由
**职责**：
- 从 `prompts/` 目录加载提示词
- 意图分类和专家路由
- 调用 LLM 生成回复
- 安全过滤（禁止联系方式等敏感信息）
- 多个专家 Agent 的协调

**关键类**：`XianyuReplyBot`, `IntentRouter`, `ClassifyAgent`, `PriceAgent`, `TechAgent`, `DefaultAgent`

**常见修改**：
- 编辑 `prompts/` 目录下的 prompt 文件调整 AI 行为
- 更新安全过滤规则
- 改进意图路由逻辑

### `XianyuApis.py` - HTTP API 和 Cookie 管理
**职责**：
- Xianyu 平台 API 调用
- Cookie 和 Session 管理
- Token 刷新
- 身份验证

**关键类**：`XianyuApis`

**常见修改**：
- 调整 HTTP 请求头
- 优化 Cookie 管理逻辑
- 处理 API 响应

### `context_manager.py` - SQLite 对话历史管理
**职责**：
- SQLite 数据库初始化和表结构管理
- 存储对话历史消息
- 议价次数统计
- 商品信息缓存
- 上下文检索

**关键类**：`ChatContextManager`

**常见修改**：
- 调整数据库 schema
- 优化查询性能
- 修改数据保留策略

### `utils/xianyu_utils.py` - 工具函数
**职责**：
- Cookie 解析和转换
- 签名生成
- 加密/解密
- Device ID、UUID 生成

**常见修改**：
- 修复签名算法
- 更新加密方法
- 优化 ID 生成逻辑

## Prompt 文件

位置：`prompts/` 目录

系统会优先加载用户自定义的 prompt：
- 如果 `*_prompt.txt` 存在 -> 使用自定义
- 否则 -> 使用 `*_prompt_example.txt`

### 四个 Prompt 文件的用途

| 文件名 | 用途 | 示例修改 |
|--------|------|--------|
| `classify_prompt.txt` | 意图分类（价格/技术/通用） | 调整分类规则，支持新的意图类型 |
| `price_prompt.txt` | 议价专家行为 | 修改降价幅度、谈判策略 |
| `tech_prompt.txt` | 技术支持回复 | 改进技术方案、支持新产品 |
| `default_prompt.txt` | 默认通用回复 | 调整客服语气、服务承诺 |

## 配置和环保变量

位置：`.env` 文件

关键配置见 `CLAUDE.md` 中的环境变量表

## 数据目录

位置：`data/` 目录

- `chat_history.db` - SQLite 数据库，存储所有对话历史
- 该目录会在首次运行时自动创建

## Python 桥接层（桌面版专用）

### `python/bridge.py` - Electron IPC 桥接入口

**职责**：
- 作为 Electron 子进程启动（`BRIDGE_MODE=1`）
- 通过 stdin 接收 JSON 指令，通过 stdout 输出 JSON 事件
- 管理机器人生命周期（启动 / 停止 / 重载配置）
- 将 loguru 日志重定向为 JSON 行输出到 stdout

**关键类**：`BridgeManager`

**关键函数**：
- `emit_status(running)` — 推送运行状态
- `emit_error(code, message)` — 推送错误事件
- `emit_login_result(success, message)` — 推送登录结果
- `stdout_json_sink(message)` — loguru sink，将所有日志转为 JSON 行

**命令处理逻辑**（`BridgeManager.run()`）：
| 命令 | 行为 |
|------|------|
| `start` | 调用 `build_live_instance()` 实例化 bot 并启动 asyncio task |
| `stop` | cancel bot task，等待最多 5s |
| `reload_config` | 先停止 bot，再 `init_config()` 重读 DB，再重新启动 |
| `login` | 启动 `browser_login()` task（防重复） |

**stdin 读取**：使用独立线程（`stdin_thread`）避免 Windows asyncio stdin 不可靠问题，通过 `asyncio.Queue` 传递到主循环。

**PyInstaller 兼容**：`get_resource_path()` 自动适配打包后 `sys._MEIPASS` 路径。

**常见修改**：
- 新增命令类型 → 在 `run()` 的 `if action == ...` 分支中添加
- 新增推送消息类型 → 添加新的 `emit_xxx()` 函数，并同步更新 `pythonManager.js` 的 `listeners` 字典
- 修改启动参数 → 在 `build_live_instance()` 中调整

---

### `python/config_manager.py` - SQLite 配置管理

**职责**：
- 维护 `app_config.db` 中的 `config` 和 `prompts` 两张表
- 首次运行时写入默认配置（`seed_defaults()`）
- 供 bridge.py 和 login_browser.py 读写配置和 Cookie

**关键类**：`AppConfigManager`

**数据库路径**：`%APPDATA%\XianyuAutoAgent\app_config.db`（与 Electron `dbManager.js` 共享同一文件）

**主要方法**：
| 方法 | 说明 |
|------|------|
| `get_config() -> dict` | 读取全部 config 键值 |
| `get_value(key, default)` | 读取单个配置项 |
| `set_value(key, value)` | 写入单个配置项（upsert） |
| `set_many(data: dict)` | 批量写入配置项 |
| `get_prompt(name) -> str` | 读取单个 prompt |
| `get_all_prompts() -> dict` | 读取全部 prompts |
| `set_prompt(name, content)` | 写入单个 prompt |
| `set_many_prompts(data: dict)` | 批量写入 prompts |
| `update_cookies(cookie_str)` | 更新 COOKIES_STR（登录后调用） |

**默认配置键**（`DEFAULT_CONFIG`）：`API_KEY`、`COOKIES_STR`、`MODEL_BASE_URL`、`MODEL_NAME`、`TOGGLE_KEYWORDS`、`SIMULATE_HUMAN_TYPING`、`HEARTBEAT_INTERVAL`、`HEARTBEAT_TIMEOUT`、`TOKEN_REFRESH_INTERVAL`、`TOKEN_RETRY_INTERVAL`、`MANUAL_MODE_TIMEOUT`、`MESSAGE_EXPIRE_TIME`

**Prompt 初始化**（`seed_defaults()`）：仅在 prompts 表为空时执行，从 `prompts/` 目录读取 `*_prompt.txt`（优先）或 `*_prompt_example.txt` 写入 DB。

**常见修改**：
- 新增配置项 → 在 `DEFAULT_CONFIG` 字典中添加键值，并同步更新 `Settings.vue` 表单
- 新增 prompt 类型 → 在 `PROMPT_NAMES` 列表中添加，并在 `Prompts.vue` 新增 Tab

## Docker 支持

- `Dockerfile` - 容器化配置
- `docker-compose.yml` - 多容器编排

## 特殊注意

1. **Cookie 过期** - Cookie 的 unb 字段作为用户 ID，失效时需重新获取
2. **Token 机制** - Token 每小时刷新一次，可通过环境变量调整
3. **消息过滤** - 多层过滤确保只处理真实的客户消息
4. **LLM 兼容性** - 默认使用通义千问，但支持任何 OpenAI 兼容的 API

## 文件访问频率（开发时）

**高频修改**：
- `prompts/*.txt` - 调试 AI 行为
- `.env` - 配置变更

**中频修改**：
- `XianyuAgent.py` - 改进路由和过滤逻辑
- `main.py` - 处理连接问题

**低频修改**：
- `context_manager.py` - 数据库优化
- `XianyuApis.py` - API 调整（平台更新时）

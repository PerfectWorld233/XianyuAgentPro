# RAG 本地知识库功能设计文档

**日期：** 2026-03-30
**状态：** 已批准
**项目：** XianyuAgentPro

---

## 1. 功能概述

为 XianyuAutoAgent 添加本地知识库 RAG（Retrieval Augmented Generation）功能，使 AI 客服在回复买家时能自动检索相关知识，提升回答的准确性和专业性。

**核心能力：**
- 用户可手动编辑知识条目（问题 + 答案）
- 支持通过商品图片或聊天记录 AI 自动生成知识条目（用户审核后入库）
- 每条用户消息自动触发知识库检索，将相关知识注入 LLM system prompt

---

## 2. 知识库结构

### 2.1 知识条目

每条知识为简单问答对，包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键，自增 |
| `item_id` | TEXT \| NULL | 关联商品 ID；NULL 表示全局通用知识 |
| `question` | TEXT | 问题 |
| `answer` | TEXT | 答案 |
| `embedding` | BLOB | 序列化的 numpy 向量（float32），NULL 表示待索引 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |

**知识分两类：**
- **全局知识**（`item_id = NULL`）：跨商品通用，如议价话术、售后政策等
- **商品知识**（`item_id = "xxx"`）：与特定商品绑定，如成色描述、配件说明等

### 2.2 SQLite 数据库

`knowledge` 表建在现有的 `app_config.db` 中（`%APPDATA%\XianyuAutoAgent\app_config.db`），原因：
- Node.js 主进程已通过 `dbManager.js` 直接访问此库
- CRUD 操作（list/add/update/delete）由 Node.js 直接读写，无需经过 Python IPC（与现有 `config:get`/`prompts:save` 模式一致）
- 仅 embedding 生成和 FAISS 索引构建需要 Python 处理

```sql
CREATE TABLE IF NOT EXISTS knowledge (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     TEXT,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    embedding   BLOB,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_item_id ON knowledge(item_id);
```

### 2.3 FAISS 索引文件

- 索引路径：`%APPDATA%\XianyuAutoAgent\knowledge.index`
- 映射文件：`%APPDATA%\XianyuAutoAgent\knowledge_index_map.json`（FAISS 向量 ID → SQLite row ID）
- 索引类型：`IndexFlatIP`（内积相似度，向量归一化后等价于余弦相似度）
- **重建策略**：条目增删改后调用 Python `knowledge:rebuild_index` 命令全量重建；不依赖 mtime 比较

---

## 3. Python 后端架构

### 3.1 新增模块

```
python/knowledge_base/
├── __init__.py
├── manager.py      # embedding 生成 + FAISS 索引管理 + AI 生成
└── retriever.py    # 检索接口，供 main.py 调用
```

Python 端**不负责** CRUD（增删改查由 Node.js 直接操作 SQLite），仅负责：
- 生成 embedding（需调用 Qwen API）
- 构建和维护 FAISS 索引
- 检索知识库
- AI 从图片/聊天记录生成 Q&A（待审核）

### 3.2 KnowledgeManager（manager.py）

```python
class KnowledgeManager:
    async def rebuild_index() -> None
        # 从 app_config.db knowledge 表读取所有条目
        # 对 embedding=NULL 的条目调用 Qwen embedding API 补全
        # 将向量写回 SQLite
        # 构建 FAISS IndexFlatIP，持久化到 .index 文件
        # 更新 knowledge_index_map.json

    async def generate_from_image(image_path: str) -> List[Dict[str, str]]
        # 调用 LLM multimodal API（base64 编码图片）
        # 返回 [{question, answer}] 列表，不写库

    async def generate_from_chat_log(chat_text: str) -> List[Dict[str, str]]
        # 调用 LLM 提炼聊天记录中的 Q&A
        # 返回 [{question, answer}] 列表，不写库
```

**异步设计**：所有方法为 `async`，与 `main.py` 的 asyncio 事件循环兼容。

**AI 生成的模型要求**：`generate_from_image` 需要 multimodal 模型。实现时检查 `MODEL_NAME` 是否支持 vision（通过配置项 `VISION_MODEL` 单独指定，默认与 `MODEL_NAME` 相同）。若模型不支持，返回错误提示而非崩溃。

### 3.3 KnowledgeRetriever（retriever.py）

```python
class KnowledgeRetriever:
    async def search(query: str, item_id: str = None, top_k: int = 3) -> List[Dict]
        # 1. 调用 Qwen embedding API 向量化 query（async）
        # 2. FAISS 检索商品知识（按 item_id 过滤映射表）
        # 3. FAISS 检索全局知识（item_id=NULL 的条目）
        # 4. 合并按相似度排序，返回 Top-K 去重
```

**懒加载**：首次调用时加载 FAISS 索引到内存，后续复用；`rebuild_index()` 完成后重置内存缓存。

**降级处理**：知识库为空、索引文件不存在、或 `KNOWLEDGE_ENABLED=False` 时，直接返回 `[]`，不影响现有回复流程。

### 3.4 集成到消息处理流程（main.py）

检索在 `main.py` 的消息处理循环中调用，**早于** `generate_reply()`，结果作为参数传入：

```python
# main.py 消息处理（简化）
retrieved_knowledge = await retriever.search(user_msg, item_id=item_id, top_k=top_k)
reply = await self.bot.generate_reply(user_msg, item_desc, context, knowledge=retrieved_knowledge)
```

`XianyuReplyBot.generate_reply()` 签名扩展：

```python
async def generate_reply(user_msg, item_desc, context, knowledge=None) -> str:
    # ...现有逻辑...
    if knowledge:
        kb_context = "\n".join([f"Q: {r['question']}\nA: {r['answer']}" for r in knowledge])
        system_prompt += f"\n\n【相关知识库】\n{kb_context}"
```

> **注意**：`generate_reply()` 目前是同步方法，整个 Agent 类链（`BaseAgent._call_llm()`、`PriceAgent.generate()`、`TechAgent.generate()`、`ClassifyAgent.generate()`）均为同步调用。为避免大规模重构，采用 `asyncio.to_thread()` 将同步调用包装到线程池执行。knowledge 检索（async）在 `main.py` 中先行完成，结果传入同步的 `generate_reply()`：
>
> ```python
> # main.py 调用方式
> retrieved_knowledge = await retriever.search(user_msg, item_id=item_id)
> reply = await asyncio.to_thread(self.bot.generate_reply, user_msg, item_desc, context, retrieved_knowledge)
> ```
>
> 这样无需改动现有 Agent 类，`generate_reply()` 保持同步签名，只接收已计算好的 `knowledge` 列表作为额外参数。

### 3.5 bridge.py 新增命令

```python
# 触发 FAISS 索引重建（CRUD 后由 Node.js 调用）
{"cmd": "knowledge:rebuild_index"}

# AI 从图片生成 Q&A（返回待审核列表）
{"cmd": "knowledge:generate_from_image", "image_path": "..."}

# AI 从聊天记录生成 Q&A
{"cmd": "knowledge:generate_from_chat", "chat_text": "..."}
```

Python 响应通过 stdout JSON-lines 广播（与 `generate_prompts_result` 完全一致）：
```json
{"type": "knowledge_generate_result", "data": [...]}
{"type": "knowledge_generate_error", "message": "..."}
```

渲染进程监听 `bot:knowledge_generate_result` 事件更新 UI，无需 request_id 路由。并发 AI 生成请求在 `bridge.py` 通过 `generate_task` 守卫串行化。

### 3.6 新增配置项

在 `config_manager.py` 的 `DEFAULT_CONFIG` 中新增：

| 配置键 | 说明 | 默认值 |
|--------|------|--------|
| `EMBEDDING_MODEL` | Embedding 模型名称 | `text-embedding-v3` |
| `KNOWLEDGE_TOP_K` | 检索返回最大条数 | `3` |
| `KNOWLEDGE_ENABLED` | 是否启用知识库 | `True` |
| `VISION_MODEL` | 图片生成用的 multimodal 模型 | `（同 MODEL_NAME）` |

### 3.7 依赖更新

`python/requirements.txt` 新增：
```
faiss-cpu
numpy
```

---

## 4. Electron UI

### 4.1 知识库管理页面（KnowledgeBase.vue）

**路由：** `/knowledge`
**侧边栏：** 新增"知识库"入口（书本图标）

**页面布局：**

```
┌─────────────────────────────────────────────────┐
│  知识库管理                    [+ 新增条目]       │
├─────────────────────────────────────────────────┤
│  筛选：[全部 ▼]  [搜索关键词...]                  │
├──────┬──────────────────┬──────────────┬────────┤
│ 范围 │ 问题             │ 答案预览     │ 操作   │
├──────┼──────────────────┼──────────────┼────────┤
│ 全局 │ 怎么议价？       │ 您好，这个...│ 编辑删除│
│ #123 │ 这个手机成色？   │ 95新，轻微...│ 编辑删除│
└──────┴──────────────────┴──────────────┴────────┘

  [AI 从图片生成]  [AI 从聊天记录生成]
```

**AI 生成流程（抽屉式面板）：**
1. **图片生成**：点击"AI 从图片生成" → 调用 `dialog.showOpenDialog`（主进程）弹出文件选择对话框 → 获取本地路径 → 发送 `knowledge:generateFromImage` IPC → 显示 AI 提炼的 Q&A 列表，每条可勾选 → 点击"确认入库"批量写入
2. **聊天记录生成**：粘贴聊天文本 → 发送 `knowledge:generateFromChat` IPC → 同样的审核流程

> 图片路径获取方式：主进程通过 `dialog.showOpenDialog` 返回路径，渲染进程不直接访问文件系统。

### 4.2 IPC 接口

**CRUD 操作**（Node.js 直接操作 SQLite，与 `config:get`/`prompts:save` 模式一致）：

| IPC 事件 | 参数 | 返回 | 实现 |
|----------|------|------|------|
| `knowledge:list` | `{ item_id? }` | `Entry[]` | dbManager 直接查询 |
| `knowledge:add` | `{ question, answer, item_id? }` | `{ id }` | dbManager 写入，再触发 rebuild |
| `knowledge:update` | `{ id, question, answer }` | `void` | dbManager 更新，再触发 rebuild |
| `knowledge:delete` | `{ id }` | `void` | dbManager 删除，再触发 rebuild |

**AI 生成操作**（需经过 Python，使用与 `generate_prompts` 相同的广播模式）：

| IPC 事件 | 参数 | 返回 | 实现 |
|----------|------|------|------|
| `knowledge:generateFromImage` | `void`（主进程内部弹出文件对话框获取路径） | `void`（结果通过事件推送） | 主进程弹 dialog → 发送 Python 命令 → 渲染进程监听 `bot:knowledge_generate_result` 广播事件 |
| `knowledge:generateFromChat` | `{ chat_text }` | `void`（结果通过事件推送） | 发送 Python 命令 → 渲染进程监听 `bot:knowledge_generate_result` 广播事件 |
| `knowledge:batchAdd` | `{ entries: QAPair[], item_id? }` | `void` | dbManager 批量写入，再触发 rebuild |

**AI 生成响应模式**：与现有 `generate_prompts` 完全一致——`ipcHandlers.js` 调用 `sendCommand()` 后立即返回（fire-and-forget），Python 完成后通过 stdout 推送 `{type: "knowledge_generate_result", data: [...]}` 事件，`pythonManager.js` 将其广播为 `mainWindow.webContents.send('bot:knowledge_generate_result', data)`，渲染进程监听该事件更新 UI。并发 AI 生成请求在 `bridge.py` 中串行化（同 `generate_task` 守卫）。

**索引重建**由 Node.js 在每次 CRUD 写操作后自动触发，调用 `bridge.sendCommand({cmd: "knowledge:rebuild_index"})`；结果仅记录日志，不阻塞 UI。

---

## 5. 数据流

### 5.1 添加知识（手动）

```
渲染进程 → knowledge:add IPC
                ↓
        dbManager 写入 SQLite (question, answer, embedding=NULL)
                ↓
        bridge.sendCommand({cmd: "knowledge:rebuild_index"})
                ↓
        Python KnowledgeManager.rebuild_index()
          ├── 读取 embedding=NULL 的条目
          ├── 调用 Qwen embedding API（async）
          ├── 将 embedding 写回 SQLite
          └── 构建 FAISS 索引，持久化文件
                ↓
        Python 推送 {type: "knowledge_rebuild_result", ...}（日志）
```

### 5.2 添加知识（AI 生成）

```
渲染进程点击"AI 从图片生成"
        ↓
主进程 dialog.showOpenDialog → 获取 image_path
        ↓
bridge.sendCommand({cmd: "knowledge:generate_from_image", image_path})
        ↓
Python 调用 LLM Vision API → 返回 [{question, answer}] 列表
        ↓
Python 推送 {type: "knowledge_generate_result", data: [...]}
        ↓
主进程广播 mainWindow.webContents.send('bot:knowledge_generate_result', data)
        ↓
渲染进程监听 bot:knowledge_generate_result → 展示审核列表 → 用户勾选确认
        ↓
knowledge:batchAdd IPC → dbManager 批量写入 → 触发 rebuild_index
```

### 5.3 消息回复

```
买家消息 (WebSocket)
      ↓
ChatContextManager (获取历史)
      ↓
KnowledgeRetriever.search(user_msg, item_id)  ← 在 main.py 调用
      ├── 向量化 query (Embedding API, async)
      ├── FAISS 检索商品知识 (item_id 过滤)
      ├── FAISS 检索全局知识
      └── 合并 Top-K 结果
      ↓
XianyuReplyBot.generate_reply(user_msg, item_desc, context, knowledge=retrieved)
      ├── IntentRouter 分类意图
      ├── 选择 Agent (price/tech/default)
      ├── system_prompt + 知识库上下文（若有检索结果）
      └── LLM 生成回答（同步 OpenAI，在 asyncio.to_thread 中执行）
      ↓
_safe_filter() → 发送回复
```

---

## 6. 关键约束

- **知识库 CRUD 在 Node.js 直接操作 SQLite**：与现有 config/prompts 模式一致，无需 Python 中转，避免 IPC 响应路由问题
- **SQLite WAL 模式**：`app_config.db` 初始化时启用 WAL 模式（`PRAGMA journal_mode=WAL`），确保 Node.js（better-sqlite3）和 Python（sqlite3 模块）并发读写时不产生 `database is locked` 错误；Python 的 embedding 写回操作在短事务内完成
- **Embedding 和索引构建在 Python 异步处理**：所有 Qwen embedding API 调用为 async，不阻塞 asyncio 事件循环
- **检索在 main.py 调用**：`item_id` 在 `main.py` 中可得，检索结果作为参数传入 `generate_reply()`，避免修改 `generate_reply()` 的 SQLite 读取逻辑
- **Embedding 复用 API_KEY**：使用现有 `API_KEY` 调用 embedding 和 AI 生成接口
- **索引重建策略**：每次 CRUD 后触发全量重建，不做 mtime 比较（条目量少时成本低，逻辑简单）
- **知识库为空时降级**：索引不存在或 `KNOWLEDGE_ENABLED=False` 时跳过检索，不影响现有回复逻辑
- **AI 生成结果不直接入库**：图片/聊天记录生成的内容必须经用户审核确认后才写入

---

## 7. 文件变更清单

### 新增文件
- `python/knowledge_base/__init__.py`
- `python/knowledge_base/manager.py`
- `python/knowledge_base/retriever.py`
- `electron/renderer/src/views/KnowledgeBase.vue`

### 修改文件
- `python/main.py` — 在消息处理循环中调用 `KnowledgeRetriever.search()`，结果传给 `generate_reply()`
- `python/XianyuAgent.py` — 扩展 `generate_reply()` 签名接收 `knowledge` 参数（保持同步）
- `python/config_manager.py` — 新增 4 个配置键
- `python/bridge.py` — 注册 `knowledge:rebuild_index`、`knowledge:generate_from_image`、`knowledge:generate_from_chat` 命令
- `python/requirements.txt` — 新增 faiss-cpu、numpy
- `electron/main/ipcHandlers.js` — 新增 knowledge:* IPC 处理器（CRUD 直接操作 SQLite，AI 生成走 Python IPC）
- `electron/main/dbManager.js` — 新增 knowledge 表初始化和 CRUD 方法
- `electron/renderer/src/App.vue` — 新增 /knowledge 路由和侧边栏入口

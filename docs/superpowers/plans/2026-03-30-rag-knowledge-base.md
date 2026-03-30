# RAG 本地知识库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 XianyuAutoAgent 添加本地知识库 RAG 功能，使 AI 客服在回复买家时自动检索相关 Q&A 知识并注入 LLM system prompt，同时提供知识库管理 UI 供用户手动编辑和 AI 生成知识条目。

**Architecture:** `knowledge` 表存储在现有 `app_config.db`（SQLite），Node.js 主进程直接读写做 CRUD；Python 后端异步处理 embedding 生成（Qwen API）和 FAISS 索引管理；检索在 `main.py` 中于 `generate_reply()` 调用前完成，结果以参数形式传入。

**Tech Stack:** Python (faiss-cpu, numpy, openai async), Node.js (better-sqlite3), Vue 3, Electron IPC (ipcMain.handle + fire-and-forget broadcast)

---

## File Map

### New Files
| File | Responsibility |
|------|----------------|
| `python/knowledge_base/__init__.py` | 包入口，导出 KnowledgeManager, KnowledgeRetriever |
| `python/knowledge_base/manager.py` | embedding 生成 + FAISS 索引构建 + AI 生成 Q&A |
| `python/knowledge_base/retriever.py` | FAISS 检索，懒加载索引，降级处理 |
| `electron/renderer/src/views/KnowledgeBase.vue` | 知识库管理页面（列表 + 编辑 + AI 生成） |

### Modified Files
| File | Change |
|------|--------|
| `python/requirements.txt` | 新增 faiss-cpu, numpy |
| `python/config_manager.py` | DEFAULT_CONFIG 新增 4 个配置键 |
| `python/bridge.py` | 注册 knowledge:rebuild_index / generate_from_image / generate_from_chat 命令 |
| `python/XianyuAgent.py` | generate_reply() 新增 knowledge 参数 |
| `python/main.py` | 消息处理循环中调用 KnowledgeRetriever.search()，结果传给 generate_reply() |
| `electron/main/dbManager.js` | 新增 knowledge 表初始化 + CRUD 方法，启用 WAL 模式 |
| `electron/main/ipcHandlers.js` | 注册 knowledge:* IPC 处理器 |
| `electron/renderer/src/App.vue` | 新增 /knowledge 路由和侧边栏入口 |
| `electron/renderer/src/router/index.js` | 新增 /knowledge 路由 |

---

## Task 1: Python 依赖 + 配置键

**Files:**
- Modify: `python/requirements.txt`
- Modify: `python/config_manager.py`

- [ ] **Step 1: 添加 Python 依赖**

编辑 `python/requirements.txt`，末尾追加：
```
faiss-cpu
numpy
```

- [ ] **Step 2: 新增配置键**

编辑 `python/config_manager.py`，在 `DEFAULT_CONFIG` 字典中追加 4 个新键（保持与现有格式一致）：

找到：
```python
DEFAULT_CONFIG = {
    "API_KEY": "",
```

在字典末尾（`}` 之前）追加：
```python
    "EMBEDDING_MODEL": "text-embedding-v3",
    "KNOWLEDGE_TOP_K": "3",
    "KNOWLEDGE_ENABLED": "True",
    "VISION_MODEL": "",
```

> `VISION_MODEL` 默认空字符串，运行时代码中若为空则回退到 `MODEL_NAME`。

- [ ] **Step 3: 提交**

```bash
git add python/requirements.txt python/config_manager.py
git commit -m "feat: add knowledge base config keys and dependencies"
```

---

## Task 2: SQLite knowledge 表 + Node.js CRUD（dbManager.js）

**Files:**
- Modify: `electron/main/dbManager.js`

`dbManager.js` 当前有：
- `db.exec(...)` 创建 config 和 prompts 表
- `getConfig()`, `saveConfig()`, `getPrompts()`, `savePrompts()` 函数
- `module.exports` 导出上述函数

- [ ] **Step 1: 在 db.exec() 中追加 knowledge 表创建和 WAL 模式**

找到 `electron/main/dbManager.js` 中的 `db.exec(`` ... ``)` 块（第 10-21 行），将其替换为以下内容（在原 SQL 末尾的反引号之前追加新内容）：

```javascript
  db.exec(`
    CREATE TABLE IF NOT EXISTS config (
      key TEXT PRIMARY KEY NOT NULL,
      value TEXT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS prompts (
      name TEXT PRIMARY KEY NOT NULL,
      content TEXT NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    PRAGMA journal_mode=WAL;
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
  `)
```

- [ ] **Step 2: 添加 knowledge CRUD 函数**

在 `module.exports` 之前，追加以下函数：

```javascript
function listKnowledge(itemId) {
  if (itemId !== undefined && itemId !== null) {
    return db.prepare('SELECT id, item_id, question, answer, created_at, updated_at FROM knowledge WHERE item_id = ? ORDER BY id DESC').all(itemId)
  }
  return db.prepare('SELECT id, item_id, question, answer, created_at, updated_at FROM knowledge ORDER BY id DESC').all()
}

function addKnowledge({ question, answer, itemId }) {
  const stmt = db.prepare(
    "INSERT INTO knowledge (item_id, question, answer) VALUES (?, ?, ?)"
  )
  const result = stmt.run(itemId ?? null, question, answer)
  return { id: result.lastInsertRowid }
}

function updateKnowledge({ id, question, answer }) {
  db.prepare(
    "UPDATE knowledge SET question = ?, answer = ?, embedding = NULL, updated_at = datetime('now') WHERE id = ?"
  ).run(question, answer, id)
}

function deleteKnowledge(id) {
  db.prepare('DELETE FROM knowledge WHERE id = ?').run(id)
}

function batchAddKnowledge(entries, itemId) {
  const stmt = db.prepare(
    "INSERT INTO knowledge (item_id, question, answer) VALUES (?, ?, ?)"
  )
  const run = db.transaction((items) => {
    for (const { question, answer } of items) {
      stmt.run(itemId ?? null, question, answer)
    }
  })
  run(entries)
}
```

- [ ] **Step 3: 将新函数加入 module.exports**

找到 `module.exports = {` 行，将新函数追加进去：
```javascript
module.exports = {
  // ...existing exports...
  listKnowledge,
  addKnowledge,
  updateKnowledge,
  deleteKnowledge,
  batchAddKnowledge,
}
```

- [ ] **Step 4: 验证（手动）**

运行 `cd electron && npm run dev`，确认 app 启动无报错，SQLite 文件中 knowledge 表已创建。

- [ ] **Step 5: 提交**

```bash
git add electron/main/dbManager.js
git commit -m "feat: add knowledge table to SQLite and Node.js CRUD methods"
```

---

## Task 3: Electron IPC handlers（ipcHandlers.js）

**Files:**
- Modify: `electron/main/ipcHandlers.js`

- [ ] **Step 1: 导入新 dbManager 函数**

在 `ipcHandlers.js` 顶部找到 `require('./dbManager')` 行，将 `listKnowledge`, `addKnowledge`, `updateKnowledge`, `deleteKnowledge`, `batchAddKnowledge` 加入解构导入：

```javascript
const {
  getConfig, saveConfig,
  getPrompts, savePrompts,
  listKnowledge, addKnowledge, updateKnowledge, deleteKnowledge, batchAddKnowledge,
} = require('./dbManager')
```

- [ ] **Step 2: 在 registerIpcHandlers 中注册 knowledge CRUD handlers**

在 `registerIpcHandlers` 函数内，`prompts` 相关 handler 之后追加：

```javascript
  // Knowledge CRUD (direct SQLite, no Python IPC needed)
  ipcMain.handle('knowledge:list', (_event, { itemId } = {}) => {
    return listKnowledge(itemId)
  })

  ipcMain.handle('knowledge:add', (_event, { question, answer, itemId }) => {
    const result = addKnowledge({ question, answer, itemId })
    sendCommand({ cmd: 'knowledge:rebuild_index' })
    return result
  })

  ipcMain.handle('knowledge:update', (_event, { id, question, answer }) => {
    updateKnowledge({ id, question, answer })
    sendCommand({ cmd: 'knowledge:rebuild_index' })
    return { ok: true }
  })

  ipcMain.handle('knowledge:delete', (_event, { id }) => {
    deleteKnowledge(id)
    sendCommand({ cmd: 'knowledge:rebuild_index' })
    return { ok: true }
  })

  ipcMain.handle('knowledge:batchAdd', (_event, { entries, itemId }) => {
    batchAddKnowledge(entries, itemId)
    sendCommand({ cmd: 'knowledge:rebuild_index' })
    return { ok: true }
  })

  // AI generation handlers (fire-and-forget to Python, result comes back as broadcast event)
  ipcMain.handle('knowledge:generateFromImage', async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'webp', 'gif'] }],
    })
    if (canceled || filePaths.length === 0) return { canceled: true }
    sendCommand({ cmd: 'knowledge:generate_from_image', image_path: filePaths[0] })
    return { ok: true }
  })

  ipcMain.handle('knowledge:generateFromChat', (_event, { chatText }) => {
    sendCommand({ cmd: 'knowledge:generate_from_chat', chat_text: chatText })
    return { ok: true }
  })
```

- [ ] **Step 3: 将 dialog 加入 electron 导入（必须执行）**

打开 `electron/main/ipcHandlers.js`，找到文件顶部导入 `electron` 的行（当前只有 `ipcMain` 或 `ipcMain, shell`），**将 `dialog` 加入**：

```javascript
const { ipcMain, dialog } = require('electron')
```

> 这是强制步骤，不是可选确认。`knowledge:generateFromImage` handler 调用了 `dialog.showOpenDialog()`，若缺少此导入将在运行时崩溃。

- [ ] **Step 4: 确认 pythonManager 的 sendCommand 已导入**

检查文件顶部是否有 `const { sendCommand } = require('./pythonManager')`，若无则添加。

- [ ] **Step 5: 提交**

```bash
git add electron/main/ipcHandlers.js
git commit -m "feat: register knowledge IPC handlers in Electron main process"
```

---

## Task 4: preload.js 暴露 knowledge API

**Files:**
- Modify: `electron/preload/index.js`（或项目实际 preload 文件路径）

- [ ] **Step 1: 确认 preload 文件路径**

查看 `electron/main/index.js` 中 `webPreferences.preload` 指向的文件。

- [ ] **Step 2: 在 contextBridge.exposeInMainWorld 中暴露 knowledge 方法**

找到现有 `electronAPI` 对象（已有 `onBotLog`, `startBot` 等），追加：

```javascript
// Knowledge base
listKnowledge: (opts) => ipcRenderer.invoke('knowledge:list', opts),
addKnowledge: (data) => ipcRenderer.invoke('knowledge:add', data),
updateKnowledge: (data) => ipcRenderer.invoke('knowledge:update', data),
deleteKnowledge: (data) => ipcRenderer.invoke('knowledge:delete', data),
batchAddKnowledge: (data) => ipcRenderer.invoke('knowledge:batchAdd', data),
generateFromImage: () => ipcRenderer.invoke('knowledge:generateFromImage'),
generateFromChat: (data) => ipcRenderer.invoke('knowledge:generateFromChat', data),
onKnowledgeGenerateResult: (cb) => ipcRenderer.on('bot:knowledge_generate_result', (_e, msg) => cb(msg)),
onKnowledgeGenerateError: (cb) => ipcRenderer.on('bot:knowledge_generate_error', (_e, msg) => cb(msg)),
// 清理两个知识库事件监听器（在 KnowledgeBase.vue onUnmounted 中调用）
removeAllKnowledgeListeners: () => {
  ipcRenderer.removeAllListeners('bot:knowledge_generate_result')
  ipcRenderer.removeAllListeners('bot:knowledge_generate_error')
},
```

- [ ] **Step 3: 提交**

```bash
git add electron/preload/
git commit -m "feat: expose knowledge base API in preload bridge"
```

---

## Task 5: Python knowledge_base 模块（manager.py + retriever.py）

**Files:**
- Create: `python/knowledge_base/__init__.py`
- Create: `python/knowledge_base/manager.py`
- Create: `python/knowledge_base/retriever.py`

- [ ] **Step 1: 创建包入口 `__init__.py`**

```python
# python/knowledge_base/__init__.py
from .manager import KnowledgeManager
from .retriever import KnowledgeRetriever

__all__ = ["KnowledgeManager", "KnowledgeRetriever"]
```

- [ ] **Step 2: 创建 `manager.py`**

```python
# python/knowledge_base/manager.py
import asyncio
import base64
import json
import os
import sqlite3
from typing import List, Dict, Optional

import numpy as np
import faiss
from loguru import logger
from openai import AsyncOpenAI


class KnowledgeManager:
    """
    负责：
    - 从 SQLite 读取 knowledge 条目
    - 调用 Qwen embedding API 为条目生成向量
    - 构建并持久化 FAISS IndexFlatIP 索引
    - 调用 LLM 从图片/聊天记录生成 Q&A（不写库，返回待审核列表）
    """

    def __init__(self, config: dict):
        self.config = config
        self.db_path = config["DB_PATH"]  # app_config.db 的绝对路径
        data_dir = os.path.dirname(self.db_path)
        self.index_path = os.path.join(data_dir, "knowledge.index")
        self.map_path = os.path.join(data_dir, "knowledge_index_map.json")
        self._async_client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.config.get("API_KEY"),
                base_url=self.config.get("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            )
        return self._async_client

    async def _embed(self, texts: List[str]) -> np.ndarray:
        """批量生成 embedding，返回 float32 numpy array，shape=(len(texts), dim)"""
        model = self.config.get("EMBEDDING_MODEL", "text-embedding-v3")
        client = self._get_client()
        response = await client.embeddings.create(input=texts, model=model)
        vectors = np.array([item.embedding for item in response.data], dtype=np.float32)
        # 归一化（IndexFlatIP + 归一化 = 余弦相似度）
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms

    async def rebuild_index(self) -> None:
        """
        从 knowledge 表读取所有条目，对 embedding=NULL 的条目生成 embedding 并写回，
        然后全量重建 FAISS 索引并持久化。
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, question, answer, embedding FROM knowledge"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            logger.info("[KnowledgeManager] 知识库为空，跳过索引构建")
            # 清理旧索引文件
            for p in (self.index_path, self.map_path):
                if os.path.exists(p):
                    os.remove(p)
            return

        # 找出需要生成 embedding 的条目
        need_embed = [r for r in rows if r["embedding"] is None]
        if need_embed:
            logger.info(f"[KnowledgeManager] 为 {len(need_embed)} 条条目生成 embedding...")
            texts = [r["question"] for r in need_embed]
            vectors = await self._embed(texts)
            conn = sqlite3.connect(self.db_path)
            try:
                for row, vec in zip(need_embed, vectors):
                    conn.execute(
                        "UPDATE knowledge SET embedding = ?, updated_at = datetime('now') WHERE id = ?",
                        (vec.tobytes(), row["id"])
                    )
                conn.commit()
            finally:
                conn.close()
            # 重新读取（含刚写入的 embedding）
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT id, question, answer, embedding FROM knowledge"
                ).fetchall()
            finally:
                conn.close()

        # 构建 FAISS 索引
        all_vecs = []
        id_map = []
        for r in rows:
            if r["embedding"] is None:
                continue
            vec = np.frombuffer(r["embedding"], dtype=np.float32)
            all_vecs.append(vec)
            id_map.append(r["id"])

        if not all_vecs:
            logger.warning("[KnowledgeManager] 没有有效向量，跳过索引构建")
            return

        dim = len(all_vecs[0])
        matrix = np.stack(all_vecs)
        index = faiss.IndexFlatIP(dim)
        index.add(matrix)

        faiss.write_index(index, self.index_path)
        with open(self.map_path, "w", encoding="utf-8") as f:
            json.dump(id_map, f)

        logger.info(f"[KnowledgeManager] FAISS 索引构建完成，共 {len(id_map)} 条")

    async def generate_from_image(self, image_path: str) -> List[Dict[str, str]]:
        """
        调用 LLM vision API 从商品图片提炼 Q&A。
        返回 [{question, answer}] 列表，不写入数据库。
        """
        vision_model = self.config.get("VISION_MODEL") or self.config.get("MODEL_NAME", "qwen-max")
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")

        client = self._get_client()
        response = await client.chat.completions.create(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "请根据图片内容，提炼出买家可能会问的问题及对应的回答，"
                            "用于闲鱼二手交易的客服知识库。"
                            "以 JSON 数组格式输出，每个元素包含 question 和 answer 字段。"
                            "只输出 JSON，不要有其他文字。示例：\n"
                            '[{"question":"成色怎么样","answer":"95新，正常使用痕迹"}]'
                        ),
                    },
                ],
            }],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        # 容错：去掉可能的 markdown 代码块
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:])
            content = content.rstrip("`").strip()
        return json.loads(content)

    async def generate_from_chat_log(self, chat_text: str) -> List[Dict[str, str]]:
        """
        调用 LLM 从聊天记录提炼 Q&A。
        返回 [{question, answer}] 列表，不写入数据库。
        """
        model = self.config.get("MODEL_NAME", "qwen-max")
        client = self._get_client()
        response = await client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": (
                    "以下是一段闲鱼二手交易的聊天记录，请提炼出其中有价值的买家常见问题和对应的卖家回答，"
                    "用于知识库。以 JSON 数组格式输出，每个元素包含 question 和 answer 字段。"
                    "只输出 JSON，不要有其他文字。\n\n"
                    f"聊天记录：\n{chat_text}"
                ),
            }],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:])
            content = content.rstrip("`").strip()
        return json.loads(content)
```

- [ ] **Step 3: 创建 `retriever.py`**

```python
# python/knowledge_base/retriever.py
import json
import os
import sqlite3
from typing import List, Dict, Optional

import numpy as np
import faiss
from loguru import logger
from openai import AsyncOpenAI


class KnowledgeRetriever:
    """
    负责：
    - 懒加载 FAISS 索引到内存
    - 向量化 query 并检索 Top-K 相关 Q&A
    - 知识库为空时优雅降级（返回空列表）
    """

    def __init__(self, config: dict):
        self.config = config
        self.db_path = config["DB_PATH"]
        data_dir = os.path.dirname(self.db_path)
        self.index_path = os.path.join(data_dir, "knowledge.index")
        self.map_path = os.path.join(data_dir, "knowledge_index_map.json")
        self._index: Optional[faiss.Index] = None
        self._id_map: Optional[List[int]] = None
        self._async_client: Optional[AsyncOpenAI] = None
        # item_id 到其在 id_map 中的位置集合的映射（用于过滤）
        self._item_positions: Optional[dict] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.config.get("API_KEY"),
                base_url=self.config.get("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            )
        return self._async_client

    def invalidate_cache(self):
        """rebuild_index 完成后调用，重置内存索引缓存"""
        self._index = None
        self._id_map = None
        self._item_positions = None

    def _load_index(self) -> bool:
        """加载 FAISS 索引到内存。返回 True 表示成功，False 表示无索引（降级）。"""
        if self._index is not None:
            return True
        if not os.path.exists(self.index_path) or not os.path.exists(self.map_path):
            return False
        try:
            self._index = faiss.read_index(self.index_path)
            with open(self.map_path, encoding="utf-8") as f:
                self._id_map = json.load(f)  # list of SQLite row ids

            # 构建 item_id → positions 映射（用于按 item_id 过滤）
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("SELECT id, item_id FROM knowledge").fetchall()
            finally:
                conn.close()

            id_to_item = {r["id"]: r["item_id"] for r in rows}
            self._item_positions = {}
            for pos, row_id in enumerate(self._id_map):
                item_id = id_to_item.get(row_id)
                key = item_id if item_id is not None else "__global__"
                self._item_positions.setdefault(key, set()).add(pos)
            return True
        except Exception as e:
            logger.warning(f"[KnowledgeRetriever] 加载 FAISS 索引失败: {e}")
            return False

    async def search(self, query: str, item_id: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """
        检索与 query 最相关的 Top-K 知识条目。
        - 先搜 item_id 对应的商品知识
        - 再搜全局知识（item_id=NULL）
        - 合并去重，按相似度排序
        降级：索引不存在或 KNOWLEDGE_ENABLED=False 时返回 []。
        """
        if self.config.get("KNOWLEDGE_ENABLED", "True") != "True":
            return []

        if not self._load_index():
            return []

        model = self.config.get("EMBEDDING_MODEL", "text-embedding-v3")
        client = self._get_client()
        try:
            response = await client.embeddings.create(input=[query], model=model)
            vec = np.array(response.data[0].embedding, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            query_vec = vec.reshape(1, -1)
        except Exception as e:
            logger.warning(f"[KnowledgeRetriever] embedding 失败，降级跳过检索: {e}")
            return []

        # 搜索全部向量，取 top_k * 4 候选（便于过滤后仍有足够结果）
        k = min(top_k * 4, self._index.ntotal)
        scores, indices = self._index.search(query_vec, k)
        scores = scores[0].tolist()
        indices = indices[0].tolist()

        # 确定允许的 positions
        allowed_positions = set()
        if item_id and item_id in self._item_positions:
            allowed_positions |= self._item_positions[item_id]
        if "__global__" in self._item_positions:
            allowed_positions |= self._item_positions["__global__"]

        # 过滤 + 收集候选 row_ids
        candidates = []
        seen_ids = set()
        for idx, score in zip(indices, scores):
            if idx < 0:
                continue
            if idx not in allowed_positions:
                continue
            row_id = self._id_map[idx]
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            candidates.append((row_id, score))
            if len(candidates) >= top_k:
                break

        if not candidates:
            return []

        # 从 SQLite 读取完整内容
        row_ids = [c[0] for c in candidates]
        score_map = {c[0]: c[1] for c in candidates}
        placeholders = ",".join("?" * len(row_ids))
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                f"SELECT id, question, answer, item_id FROM knowledge WHERE id IN ({placeholders})",
                row_ids
            ).fetchall()
        finally:
            conn.close()

        result = [
            {"id": r["id"], "question": r["question"], "answer": r["answer"],
             "item_id": r["item_id"], "score": score_map[r["id"]]}
            for r in rows
        ]
        result.sort(key=lambda x: x["score"], reverse=True)
        return result[:top_k]
```

- [ ] **Step 4: 验证 Python 模块可导入**

```bash
cd python
python -c "from knowledge_base import KnowledgeManager, KnowledgeRetriever; print('OK')"
```

Expected: `OK`（需先安装 faiss-cpu 和 numpy：`pip install faiss-cpu numpy`）

- [ ] **Step 5: 提交**

```bash
git add python/knowledge_base/
git commit -m "feat: add KnowledgeManager and KnowledgeRetriever modules"
```

---

## Task 6: bridge.py 注册 knowledge 命令

**Files:**
- Modify: `python/bridge.py`

`bridge.py` 当前在 `XianyuBridge` 类中有一个 `dispatch_command` 或命令处理循环（`if action == "start": ...`），还有 `generate_task` 属性用于防止并发。

- [ ] **Step 1: 在 `XianyuBridge.__init__` 中初始化 knowledge 成员**

找到 `__init__` 方法中 `self.generate_task = None` 这一行附近，追加：

```python
self.knowledge_task: asyncio.Task | None = None
self.knowledge_manager: 'KnowledgeManager | None' = None
```

- [ ] **Step 2: 在 `init_config`（或 bot 初始化）中实例化 KnowledgeManager，并注入 DB_PATH**

找到初始化 `self.bot` 的代码块（`init_config` 方法或类似），在其末尾**先注入 DB_PATH，再实例化**：

```python
from knowledge_base import KnowledgeManager, KnowledgeRetriever

# 必须先注入 DB_PATH，KnowledgeManager/KnowledgeRetriever 构造函数会直接访问 config["DB_PATH"]
self.config["DB_PATH"] = self.config_manager.db_path

self.knowledge_manager = KnowledgeManager(self.config)
self.knowledge_retriever = KnowledgeRetriever(self.config)
```

> `self.config_manager.db_path` 是 `AppConfigManager` 实例的 `db_path` 属性（在 `config_manager.py` 中 `__init__` 里设置）。缺少 `DB_PATH` 注入会导致 `KeyError` 崩溃。

- [ ] **Step 3: 在命令处理循环中添加 3 个新命令**

找到命令处理的 `elif action == "generate_prompts":` 块，在其之后、`else: logger.warning(...)` 之前追加：

```python
elif action == "knowledge:rebuild_index":
    if not self.knowledge_task or self.knowledge_task.done():
        self.knowledge_task = asyncio.create_task(
            self._handle_rebuild_index()
        )
    else:
        logger.debug("[knowledge] 索引重建已在进行中，忽略重复请求")

elif action == "knowledge:generate_from_image":
    image_path = cmd.get("image_path", "")
    if not image_path:
        self._emit_knowledge_error("image_path 不能为空")
    elif not self.knowledge_task or self.knowledge_task.done():
        self.knowledge_task = asyncio.create_task(
            self._handle_generate_from_image(image_path)
        )
    else:
        self._emit_knowledge_error("AI 生成已在进行中，请稍后再试")

elif action == "knowledge:generate_from_chat":
    chat_text = cmd.get("chat_text", "")
    if not chat_text.strip():
        self._emit_knowledge_error("聊天记录不能为空")
    elif not self.knowledge_task or self.knowledge_task.done():
        self.knowledge_task = asyncio.create_task(
            self._handle_generate_from_chat(chat_text)
        )
    else:
        self._emit_knowledge_error("AI 生成已在进行中，请稍后再试")
```

- [ ] **Step 4: 添加处理方法和辅助函数**

在 `XianyuBridge` 类末尾追加：

```python
def _emit_knowledge_error(self, message: str):
    import sys
    payload = {"type": "knowledge_generate_error", "message": message}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()

async def _handle_rebuild_index(self):
    try:
        await self.knowledge_manager.rebuild_index()
        # 重建完成后使 retriever 缓存失效
        if hasattr(self, 'knowledge_retriever'):
            self.knowledge_retriever.invalidate_cache()
        import sys
        sys.stdout.write(json.dumps({"type": "knowledge_rebuild_result", "success": True}) + "\n")
        sys.stdout.flush()
    except Exception as e:
        logger.error(f"[knowledge] 索引重建失败: {e}")

async def _handle_generate_from_image(self, image_path: str):
    import sys
    try:
        result = await self.knowledge_manager.generate_from_image(image_path)
        payload = {"type": "knowledge_generate_result", "data": result}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception as e:
        logger.error(f"[knowledge] 图片生成 Q&A 失败: {e}")
        self._emit_knowledge_error(str(e))

async def _handle_generate_from_chat(self, chat_text: str):
    import sys
    try:
        result = await self.knowledge_manager.generate_from_chat_log(chat_text)
        payload = {"type": "knowledge_generate_result", "data": result}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception as e:
        logger.error(f"[knowledge] 聊天记录生成 Q&A 失败: {e}")
        self._emit_knowledge_error(str(e))
```

- [ ] **Step 5: 提交**

```bash
git add python/bridge.py
git commit -m "feat: register knowledge commands in bridge.py"
```

---

## Task 7: XianyuAgent.py 扩展 generate_reply 签名

**Files:**
- Modify: `python/XianyuAgent.py`

`generate_reply` 当前签名：`def generate_reply(self, user_msg: str, item_desc: str, context: List[Dict]) -> str:`

- [ ] **Step 1: 扩展 generate_reply 签名，接收 knowledge 参数**

找到 `generate_reply` 方法定义，修改签名并在 `format_history` 调用之后、`detect` 调用之前注入知识库上下文：

**修改前：**
```python
def generate_reply(self, user_msg: str, item_desc: str, context: List[Dict]) -> str:
    """生成回复主流程"""
    formatted_context = self.format_history(context)

    detected_intent = self.router.detect(user_msg, item_desc, formatted_context)
```

**修改后：**
```python
def generate_reply(self, user_msg: str, item_desc: str, context: List[Dict], knowledge: List[Dict] = None) -> str:
    """生成回复主流程"""
    formatted_context = self.format_history(context)

    if knowledge:
        kb_lines = "\n".join([f"Q: {k['question']}\nA: {k['answer']}" for k in knowledge])
        formatted_context = f"【相关知识库】\n{kb_lines}\n\n【对话历史】\n{formatted_context}"

    detected_intent = self.router.detect(user_msg, item_desc, formatted_context)
```

- [ ] **Step 2: 确认 List 导入**

文件顶部已有 `from typing import List, Dict`，若无则添加。

- [ ] **Step 3: 提交**

```bash
git add python/XianyuAgent.py
git commit -m "feat: extend generate_reply to accept knowledge context"
```

---

## Task 8: main.py 集成 KnowledgeRetriever

**Files:**
- Modify: `python/main.py`

目标：在 `handle_message` 中，`context = self.context_manager.get_context_by_chat(chat_id)` 之后、`bot.generate_reply()` 之前，调用 retriever 并将结果传入。

- [ ] **Step 1: 在 XianyuLive.__init__ 中获取 retriever 引用**

找到 `XianyuLive.__init__` 的参数，追加 `knowledge_retriever=None`：

```python
def __init__(self, ..., knowledge_retriever=None):
    ...
    self.knowledge_retriever = knowledge_retriever
```

然后在 `bridge.py` 的 `build_live_instance()` 方法（Bot 每次启动时重建 `XianyuLive` 的地方，约在第 155-159 行）中，在构造 `XianyuLive(...)` 时传入 retriever：

```python
self.live = XianyuLive(
    ...,                                          # 原有参数不变
    knowledge_retriever=self.knowledge_retriever,  # 新增参数
)
```

> `build_live_instance()` 是 Bot 每次 `start` 时调用的方法，必须在这里传入，否则重启 Bot 后 retriever 引用丢失。

- [ ] **Step 2: 在 handle_message 中调用检索**

找到：
```python
context = self.context_manager.get_context_by_chat(chat_id)
```

在其后、`bot_reply = self.bot.generate_reply(...)` 之前，追加：

```python
# 知识库检索
knowledge = []
if self.knowledge_retriever:
    try:
        top_k = int(self.config.get("KNOWLEDGE_TOP_K", "3"))
        knowledge = await self.knowledge_retriever.search(
            send_message, item_id=item_id, top_k=top_k
        )
        if knowledge:
            logger.info(f"[RAG] 检索到 {len(knowledge)} 条相关知识")
    except Exception as e:
        logger.warning(f"[RAG] 知识库检索失败，降级继续: {e}")
        knowledge = []
```

- [ ] **Step 3: 修改 generate_reply 调用，使用 asyncio.to_thread**

**修改前：**
```python
bot_reply = self.bot.generate_reply(
    send_message,
    item_description,
    context=context
)
```

**修改后：**
```python
bot_reply = await asyncio.to_thread(
    self.bot.generate_reply,
    send_message,
    item_description,
    context,
    knowledge,
)
```

> 注意：`asyncio.to_thread` 需要 Python 3.9+。如需兼容更低版本，改用 `asyncio.get_event_loop().run_in_executor(None, lambda: self.bot.generate_reply(...))` 。

- [ ] **Step 4: 确认 import asyncio**

文件顶部已有 `import asyncio`，若无则添加。

- [ ] **Step 5: 提交**

```bash
git add python/main.py
git commit -m "feat: integrate KnowledgeRetriever into message processing loop"
```

---

## Task 9: Electron 前端路由 + 侧边栏

**Files:**
- Modify: `electron/renderer/src/App.vue`
- Modify: `electron/renderer/src/router/index.js`

- [ ] **Step 1: 在 App.vue 侧边栏追加知识库入口**

找到 `<ul class="nav-links">` 内的最后一个 `<li>` 条目（通常是"提示词"），在其后追加：

```vue
<li>
  <router-link to="/knowledge" class="nav-item" active-class="active">
    <span class="nav-icon">📚</span>
    <span>知识库</span>
  </router-link>
</li>
```

- [ ] **Step 2: 在 router/index.js 追加 /knowledge 路由**

找到 `routes` 数组，在末尾追加：

```javascript
import KnowledgeBase from '../views/KnowledgeBase.vue'

// 在 routes 数组中追加：
{ path: '/knowledge', component: KnowledgeBase },
```

- [ ] **Step 3: 提交**

```bash
git add electron/renderer/src/App.vue electron/renderer/src/router/index.js
git commit -m "feat: add knowledge base route and sidebar nav item"
```

---

## Task 10: KnowledgeBase.vue 主页面

**Files:**
- Create: `electron/renderer/src/views/KnowledgeBase.vue`

页面功能：
1. 列表展示知识条目（支持按"全部/全局/商品ID"筛选，关键词搜索）
2. 新增/编辑/删除单条
3. "AI 从图片生成"按钮（触发主进程文件对话框）
4. "AI 从聊天记录生成"按钮（文本输入区）
5. AI 生成结果审核面板（可勾选，批量入库）

- [ ] **Step 1: 创建 KnowledgeBase.vue**

```vue
<template>
  <div class="knowledge-page">
    <div class="page-header">
      <h2>知识库管理</h2>
      <button class="btn-primary" @click="openAddModal">+ 新增条目</button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filterItemId">
        <option value="">全部</option>
        <option value="__global__">全局通用</option>
      </select>
      <input v-model="searchKeyword" placeholder="搜索关键词..." class="search-input" />
    </div>

    <!-- 知识条目列表 -->
    <table class="knowledge-table">
      <thead>
        <tr>
          <th>范围</th>
          <th>问题</th>
          <th>答案预览</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in filteredEntries" :key="entry.id">
          <td class="scope-cell">{{ entry.item_id ? `#${entry.item_id}` : '全局' }}</td>
          <td>{{ entry.question }}</td>
          <td class="answer-preview">{{ entry.answer.slice(0, 40) }}{{ entry.answer.length > 40 ? '...' : '' }}</td>
          <td class="action-cell">
            <button class="btn-sm" @click="openEditModal(entry)">编辑</button>
            <button class="btn-sm btn-danger" @click="deleteEntry(entry.id)">删除</button>
          </td>
        </tr>
        <tr v-if="filteredEntries.length === 0">
          <td colspan="4" class="empty-tip">暂无知识条目</td>
        </tr>
      </tbody>
    </table>

    <!-- AI 生成按钮 -->
    <div class="ai-actions">
      <button class="btn-secondary" @click="triggerGenerateFromImage" :disabled="isGenerating">
        {{ isGenerating ? 'AI 生成中...' : 'AI 从图片生成' }}
      </button>
      <button class="btn-secondary" @click="showChatPanel = true" :disabled="isGenerating">
        AI 从聊天记录生成
      </button>
    </div>

    <!-- 聊天记录输入面板 -->
    <div v-if="showChatPanel" class="chat-panel">
      <h3>从聊天记录生成知识</h3>
      <textarea v-model="chatText" placeholder="粘贴聊天记录..." rows="8"></textarea>
      <div class="panel-actions">
        <button class="btn-primary" @click="generateFromChat" :disabled="!chatText.trim() || isGenerating">生成</button>
        <button class="btn-secondary" @click="showChatPanel = false">取消</button>
      </div>
    </div>

    <!-- AI 生成结果审核面板 -->
    <div v-if="pendingEntries.length > 0" class="review-panel">
      <h3>AI 生成结果（请审核后入库）</h3>
      <div v-for="(entry, idx) in pendingEntries" :key="idx" class="pending-entry">
        <input type="checkbox" v-model="entry.selected" />
        <div class="qa-content">
          <div><strong>Q:</strong> {{ entry.question }}</div>
          <div><strong>A:</strong> {{ entry.answer }}</div>
        </div>
      </div>
      <div class="review-actions">
        <select v-model="pendingItemId" class="item-id-select">
          <option value="">全局通用</option>
        </select>
        <button class="btn-primary" @click="confirmBatchAdd" :disabled="!hasSelectedPending">
          确认入库（{{ selectedPendingCount }} 条）
        </button>
        <button class="btn-secondary" @click="pendingEntries = []">放弃</button>
      </div>
    </div>

    <!-- 新增/编辑 弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ editingEntry ? '编辑条目' : '新增条目' }}</h3>
        <label>范围（商品 ID，留空为全局）</label>
        <input v-model="formItemId" placeholder="可选，如 123456" />
        <label>问题</label>
        <input v-model="formQuestion" placeholder="买家可能会问的问题" />
        <label>答案</label>
        <textarea v-model="formAnswer" rows="4" placeholder="对应的回答"></textarea>
        <div class="modal-actions">
          <button class="btn-primary" @click="saveEntry" :disabled="!formQuestion.trim() || !formAnswer.trim()">保存</button>
          <button class="btn-secondary" @click="closeModal">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const entries = ref([])
const filterItemId = ref('')
const searchKeyword = ref('')
const isGenerating = ref(false)
const showChatPanel = ref(false)
const chatText = ref('')
const pendingEntries = ref([])
const pendingItemId = ref('')
const showModal = ref(false)
const editingEntry = ref(null)
const formItemId = ref('')
const formQuestion = ref('')
const formAnswer = ref('')

const filteredEntries = computed(() => {
  let list = entries.value
  if (filterItemId.value === '__global__') {
    list = list.filter(e => !e.item_id)
  } else if (filterItemId.value) {
    list = list.filter(e => e.item_id === filterItemId.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(e =>
      e.question.toLowerCase().includes(kw) || e.answer.toLowerCase().includes(kw)
    )
  }
  return list
})

const hasSelectedPending = computed(() => pendingEntries.value.some(e => e.selected))
const selectedPendingCount = computed(() => pendingEntries.value.filter(e => e.selected).length)

async function loadEntries() {
  entries.value = await window.electronAPI.listKnowledge()
}

function openAddModal() {
  editingEntry.value = null
  formItemId.value = ''
  formQuestion.value = ''
  formAnswer.value = ''
  showModal.value = true
}

function openEditModal(entry) {
  editingEntry.value = entry
  formItemId.value = entry.item_id || ''
  formQuestion.value = entry.question
  formAnswer.value = entry.answer
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function saveEntry() {
  const itemId = formItemId.value.trim() || undefined
  if (editingEntry.value) {
    await window.electronAPI.updateKnowledge({
      id: editingEntry.value.id,
      question: formQuestion.value,
      answer: formAnswer.value,
    })
  } else {
    await window.electronAPI.addKnowledge({
      question: formQuestion.value,
      answer: formAnswer.value,
      itemId,
    })
  }
  closeModal()
  await loadEntries()
}

async function deleteEntry(id) {
  if (!confirm('确认删除此条目？')) return
  await window.electronAPI.deleteKnowledge({ id })
  await loadEntries()
}

async function triggerGenerateFromImage() {
  const result = await window.electronAPI.generateFromImage()
  if (result?.canceled) return
  isGenerating.value = true
}

async function generateFromChat() {
  if (!chatText.value.trim()) return
  await window.electronAPI.generateFromChat({ chatText: chatText.value })
  isGenerating.value = true
  showChatPanel.value = false
}

async function confirmBatchAdd() {
  const selected = pendingEntries.value.filter(e => e.selected)
  await window.electronAPI.batchAddKnowledge({
    entries: selected.map(e => ({ question: e.question, answer: e.answer })),
    itemId: pendingItemId.value || undefined,
  })
  pendingEntries.value = []
  await loadEntries()
}

// 监听 AI 生成结果广播
onMounted(async () => {
  await loadEntries()
  window.electronAPI.onKnowledgeGenerateResult((msg) => {
    isGenerating.value = false
    pendingEntries.value = (msg.data || []).map(e => ({ ...e, selected: true }))
  })
  window.electronAPI.onKnowledgeGenerateError((msg) => {
    isGenerating.value = false
    alert(`AI 生成失败：${msg.message}`)
  })
})

onUnmounted(() => {
  // 清理 IPC 监听器，防止页面切换后的内存泄漏
  window.electronAPI.removeAllKnowledgeListeners?.()
})
</script>

<style scoped>
.knowledge-page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.search-input { flex: 1; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; }
.knowledge-table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
.knowledge-table th, .knowledge-table td { padding: 10px 12px; border-bottom: 1px solid #eee; text-align: left; }
.knowledge-table th { background: #f5f5f5; font-weight: 600; }
.scope-cell { white-space: nowrap; color: #666; }
.answer-preview { color: #888; font-size: 13px; }
.action-cell { white-space: nowrap; }
.empty-tip { color: #aaa; text-align: center; padding: 24px; }
.ai-actions { display: flex; gap: 12px; margin-bottom: 16px; }
.chat-panel, .review-panel { background: #f9f9f9; border: 1px solid #ddd; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.chat-panel textarea { width: 100%; margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
.panel-actions, .review-actions, .modal-actions { display: flex; gap: 8px; margin-top: 12px; }
.pending-entry { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 12px; }
.qa-content { flex: 1; }
.item-id-select { padding: 6px; border: 1px solid #ddd; border-radius: 4px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: #fff; border-radius: 8px; padding: 24px; min-width: 400px; max-width: 560px; width: 100%; }
.modal h3 { margin-top: 0; }
.modal label { display: block; margin: 12px 0 4px; font-size: 13px; color: #555; }
.modal input, .modal textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
.btn-primary { padding: 8px 16px; background: #1677ff; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
.btn-primary:disabled { background: #a0c4ff; cursor: not-allowed; }
.btn-secondary { padding: 8px 16px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; }
.btn-sm { padding: 4px 10px; font-size: 12px; background: #f0f0f0; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; margin-right: 4px; }
.btn-danger { color: #ff4d4f; }
</style>
```

- [ ] **Step 2: 验证页面在开发环境可访问**

```bash
cd electron && npm run dev
```

导航到"知识库"，确认页面渲染正常，列表为空（暂无条目）。

- [ ] **Step 3: 提交**

```bash
git add electron/renderer/src/views/KnowledgeBase.vue
git commit -m "feat: add KnowledgeBase.vue management page"
```

---

## Task 11: 端到端冒烟测试

**目标：** 验证完整数据流从 UI → SQLite → Python embedding → FAISS → 消息检索 全部正常。

- [ ] **Step 1: 启动开发环境**

```bash
cd electron && npm run dev
```

确保已在 Settings 页设置有效的 `API_KEY` 和 `MODEL_BASE_URL`。

- [ ] **Step 2: 手动添加一条知识**

在"知识库"页面点击"+ 新增条目"，填写：
- 问题：`这个商品还在吗`
- 答案：`在的，欢迎下单`
- 范围：留空（全局）

保存。查看控制台日志，确认出现 `[KnowledgeManager] FAISS 索引构建完成` 日志。

- [ ] **Step 3: 验证 FAISS 索引文件已生成**

检查 `%APPDATA%\XianyuAutoAgent\` 目录，确认存在 `knowledge.index` 和 `knowledge_index_map.json`。

- [ ] **Step 4: 测试 AI 生成（聊天记录）**

点击"AI 从聊天记录生成"，粘贴一段模拟聊天记录（如 `买家：包邮吗\n卖家：包邮的`），点击"生成"。确认审核面板出现提炼的 Q&A 条目，勾选后"确认入库"，验证列表更新。

- [ ] **Step 5: 验证消息回复中知识被注入**

启动 Bot（需要有效 COOKIES_STR），发送一条与知识库匹配的消息，查看控制台日志确认出现 `[RAG] 检索到 N 条相关知识`，且 Bot 回复中体现了知识库内容。

- [ ] **Step 6: 提交最终 tag**

```bash
git add -A
git commit -m "feat: RAG knowledge base - complete implementation"
```

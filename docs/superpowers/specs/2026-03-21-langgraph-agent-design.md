# XianyuAutoAgent — LangGraph Agent Enhancement Design

**Date:** 2026-03-21
**Target:** `python/` backend (Desktop app mode only)
**Reference:** `D:\pythonProject\github\XianyuAgentBot`
**Integration approach:** Direct Port (Approach A)

---

## 1. Problem Statement

The current `python/XianyuAgent.py` implements a simple intent-routing bot with four specialist agents (classify, price, tech, default). It lacks:

- Multi-stage conversation flow (opening → requirements → pricing → negotiation → closing)
- Pricing reference system (no knowledge base)
- Buyer emotion awareness
- Human handover notifications
- Standalone local test environment
- GUI management for the knowledge base

This design adds all seven requested features to the `python/` desktop app backend without breaking the existing Electron frontend beyond adding new UI views.

---

## 2. Architecture Overview

### New File Structure

```
python/
├── agent/                        # NEW — LangGraph agent system
│   ├── __init__.py
│   ├── graph.py                  # State machine + process_message() entry point
│   ├── knowledge.py              # FAISS (optional) + keyword knowledge base search
│   ├── emotion.py                # Keyword-rule sentiment analyzer
│   ├── notify.py                 # Feishu webhook notifications
│   └── guardrails.py             # Input/output safety filters
├── storage/
│   └── database.py               # NEW — Extended SQLite schema (threads, metrics)
├── knowledge/
│   ├── cases.json                # Case library (empty; user-populated)
│   └── skills.json               # Optional skills inventory
├── local_chat.py                 # NEW — Standalone debug REPL
├── bridge.py                     # MODIFIED — imports process_message; feature flag
├── config_manager.py             # MODIFIED — new config keys
├── main.py                       # MODIFIED — injects graph instead of XianyuReplyBot
└── XianyuAgent.py                # KEPT unchanged (fallback if USE_LANGGRAPH=False)
```

### Data Flow

```
WebSocket message (main.py)
  ↓ user_msg, item_desc, thread_id
process_message(graph, ...)
  ├─ analyze_context node
  │    ├─ keyword sentiment analysis
  │    └─ LLM stage/requirement extraction (ANALYSIS_PROMPT)
  ├─ select_strategy node
  │    ├─ PRICING: search_cases() → KnowledgeBase.search() → FAISS or keyword
  │    └─ unknown case: send_reminder() → Feishu POST + set is_handover
  ├─ call_model node
  │    └─ LLM with system prompt (base + item_desc + stage context + strategy)
  └─ tool executor (conditional)
       ├─ search_cases → JSON case list
       └─ send_reminder → Feishu card + handover flag
  ↓ reply string
send_msg() → Xianyu WebSocket
```

---

## 3. LangGraph State Machine

### AgentState (TypedDict)

| Field | Type | Purpose |
|---|---|---|
| `messages` | `Annotated[Sequence[BaseMessage], add_messages]` | Full conversation (LangGraph managed) |
| `stage` | `str \| None` | Current stage (see Stage constants) |
| `requirements` | `dict \| None` | Extracted buyer requirements |
| `bargain_count` | `int` | Times buyer bargained in this thread |
| `quoted_price` | `int \| None` | Last price bot quoted |
| `floor_price` | `int \| None` | Minimum acceptable price (from cases) |
| `emotion` | `dict \| None` | Last sentiment result |
| `strategy` | `str \| None` | Current reply strategy instruction |
| `last_prompt` | `str \| None` | System prompt for debugging |
| `item_desc` | `str \| None` | Product description (injected per call) |
| `user_id` | `str \| None` | Buyer user ID |
| `user_name` | `str \| None` | Buyer display name |

### Stage Constants

```python
class Stage:
    GREETING     = "开场"         # Initial greeting, no requirements yet
    REQUIREMENT  = "需求收集"     # Gathering project type / budget / deadline
    PRICING      = "询价"         # Buyer gives budget; search cases; quote price
    NEGOTIATION  = "议价"         # Buyer bargains; hold or offer small concession
    CLOSING      = "成交引导"     # Buyer agrees; guide to checkout / WeChat
    COMPLETED    = "已完成"       # Deal recorded
```

### Graph Nodes

**`analyze_context(state) → dict`**
1. Get latest user message
2. Run keyword sentiment analyzer → `state["emotion"]`
3. Call LLM with ANALYSIS_PROMPT to extract JSON `{stage, requirements, is_bargaining, expected_price}`
4. Fallback: if LLM fails, use keyword rules for stage detection
5. If `is_bargaining=True`, increment `bargain_count`
6. If buyer gives `expected_price` and stage == REQUIREMENT, advance to PRICING
7. Returns updated state fields

**`select_strategy(state) → dict`**
Based on resolved stage, builds a strategy instruction string:
- GREETING: prompt buyer to share requirements
- REQUIREMENT: ask for missing info (type / tech stack / budget / deadline)
- PRICING: call `search_cases(query)` tool; compute `floor_price`; decide to accept/counter
- NEGOTIATION: hold price if `bargain_count >= 2`; small concession if `bargain_count == 1`
- CLOSING: confirm order; guide to "我想要" button

**`call_model(state) → dict`**
- Builds system prompt: base system prompt + item_desc + stage context + strategy
- Saves `last_prompt` for debugging
- Binds `search_cases` and `send_reminder` tools only for PRICING/NEGOTIATION/CLOSING
- Calls LLM API; returns `AIMessage` (with optional `tool_calls`)

**Tool executor node (conditional)**
- `search_cases(query, top_k=3)` → JSON string of matching cases
- `send_reminder(message, notice_type)` → Feishu POST; sets `is_handover=True`

### Conditional Routing

```python
def should_continue(state) -> str:
    last_msg = state["messages"][-1]
    return "tools" if hasattr(last_msg, "tool_calls") and last_msg.tool_calls else "__end__"

def should_reply_after_tools(state) -> str:
    # If handover tool was called, skip final reply
    tool_msgs = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    for msg in tool_msgs[-3:]:
        if "handover" in msg.content.lower():
            return "__end__"
    return "call_model"
```

### State Persistence

Uses `langgraph-checkpoint-sqlite` with `SqliteSaver` pointing to the same `chat_history.db`. Thread ID is the Xianyu `chat_id`. State snapshots persist across bot restarts.

---

## 4. FAISS Knowledge Base

### Knowledge Files

- `python/knowledge/cases.json` — array of case objects (empty initially)
- `python/knowledge/skills.json` — optional skills list

### Case Object Schema

```json
{
  "id": 1,
  "title": "案例标题",
  "description": "详细描述",
  "tags": ["Python", "FastAPI", "MySQL"],
  "price": 1500,
  "duration": "7天",
  "complexity": "medium"
}
```

### KnowledgeBase Class (`python/agent/knowledge.py`)

**`search(query, top_k=3) → List[Dict]`**
- If `EMBEDDING_MODEL` is configured in config: use FAISS semantic search (lazy-loaded index, cached embeddings)
- Always supplemented by keyword scoring (title=3pts, description=2pts, tags=1pt each)
- Final score: `semantic_score * 0.7 + keyword_score * 0.3` (or keyword-only if no FAISS)
- Returns cases with `_score`, `_semantic_score`, `_keyword_score` fields

**Index management:**
- FAISS index cached to `python/knowledge/.faiss_index`
- Embeddings cached to `python/knowledge/.embeddings_cache.pkl`
- Auto-rebuilds if `cases.json` is modified (mtime check)
- `rebuild_index()` method for manual refresh

**`search_cases` LangGraph tool:**
```python
@tool
def search_cases(query: str, top_k: int = 3) -> str:
    """Search the case library for similar projects and pricing reference."""
    results = kb.search(query, top_k)
    if not results:
        return json.dumps({"found": False, "cases": []})
    return json.dumps({"found": True, "cases": results})
```

---

## 5. Sentiment Analysis

**File:** `python/agent/emotion.py`
**Method:** Keyword rules only (no transformer model download)

### EmotionAnalyzer Class

**`analyze(text: str, context: str = "") → Dict`**

Keyword sets:
```python
POSITIVE = {"好", "可以", "行", "ok", "不错", "满意", "谢谢", "下单", "要了", "成交"}
NEGATIVE = {"贵", "太贵", "便宜点", "不行", "算了", "不要", "差", "再便宜", "能不能便宜"}
URGENCY  = {"急", "今天", "明天", "赶紧", "快点", "尽快"}
```

Scoring:
- Count positive/negative/urgency keyword hits in `text`
- If positive > negative → `"positive"`, confidence = positive / total
- If negative > positive → `"negative"`, confidence = negative / total
- Otherwise → `"neutral"`, confidence = 0.5
- Urgency flag added separately as `"is_urgent": bool`

Return format:
```python
{"sentiment": "positive|negative|neutral", "confidence": 0.0-1.0, "method": "rule", "is_urgent": bool}
```

### Strategy Influence

In `select_strategy`:
- If `sentiment == "negative"` and `stage == NEGOTIATION`: add "表示理解买家担忧，强调性价比" to strategy
- If `sentiment == "positive"` and `stage == CLOSING`: add "买家态度积极，可以催促下单" to strategy
- If `is_urgent == True`: add "买家有紧迫感，强调可快速交付" to strategy

---

## 6. Feishu Notifications

**File:** `python/agent/notify.py`
**Trigger:** Handover only (when `send_reminder(notice_type='handover')` is called)

### Implementation

```python
def send_feishu_card(message: str, thread_id: str, notice_type: str = "handover") -> Dict:
    webhook_url = config.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        return {"success": True, "message": "Webhook未配置，已跳过通知"}

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🔴 需要人工跟进"},
                "template": "orange"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**会话ID:** {thread_id}\n{message}"}},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "请及时处理，避免影响买家体验"}]}
            ]
        }
    }
    resp = requests.post(webhook_url, json=card, timeout=5)
    return {"success": resp.status_code == 200, "message": resp.text}
```

**Config key:** `FEISHU_WEBHOOK_URL` (empty string = disabled; soft-fail if not set)

---

## 7. Extended SQLite Schema

**File:** `python/storage/database.py`
**DB location:** Same `chat_history.db` used by `ChatContextManager` (adds new tables, no schema conflicts)

### New Tables

**`threads`** — Per-conversation metadata
```sql
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    user_id TEXT,
    item_id TEXT,
    bargain_count INTEGER DEFAULT 0,
    is_handover INTEGER DEFAULT 0,
    handover_time DATETIME,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    total_rounds INTEGER DEFAULT 0,
    stage_reached TEXT,
    is_deal INTEGER DEFAULT 0,
    deal_price REAL
);
```

**`call_metrics`** — LLM call tracking
```sql
CREATE TABLE IF NOT EXISTS call_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    thread_id TEXT,
    stage TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms REAL,
    success INTEGER DEFAULT 1,
    error TEXT,
    tools_called TEXT
);
```

### Database Class

Key methods:
- `is_handover(thread_id) → bool`
- `set_handover(thread_id, is_handover: bool)`
- `update_thread(thread_id, **kwargs)` — upsert thread metadata
- `save_message(thread_id, role, content, emotion, strategy, stage)` — extended message record
- `get_history(thread_id, limit=50) → List[Dict]`
- `record_call_metric(thread_id, stage, tokens, latency, tools)` — usage tracking

---

## 8. Local Debug REPL

**File:** `python/local_chat.py`

```
Usage:
  python local_chat.py [--item "product description"]

Commands:
  /quit              Exit
  /clear             Start new session
  /item <desc>       Set product description
  /debug             Toggle debug output (stage / emotion / strategy)
  /history           Show current session ID
  /prompt            Show last system prompt (first 500 chars)
  /tools             Show last tool call results
```

Imports `create_workflow`, `process_message` from `agent/graph.py`. Works without Xianyu cookies. Uses `knowledge/cases.json` for FAISS/keyword search.

---

## 9. Bridge & Config Changes

### config_manager.py

New default keys added to `DEFAULT_CONFIG`:
```python
"FEISHU_WEBHOOK_URL": "",
"EMBEDDING_MODEL": "",          # e.g. text-embedding-v3; empty = keyword-only
"USE_LANGGRAPH": "True",        # Feature flag: "True" uses new graph, "False" uses old XianyuReplyBot
```

New prompt key in `prompts` table: `agent_system_prompt` (base LLM system prompt for the new graph).

### bridge.py

In `build_live_instance()`:
```python
use_langgraph = config.get("USE_LANGGRAPH", "True").lower() == "true"
if use_langgraph:
    from agent.graph import create_workflow, process_message
    graph = create_workflow(db_path=db_path)
    live = XianyuLive(cookies_str, config, config_manager)
    live.set_graph(graph, process_message)  # new method
else:
    # existing XianyuReplyBot path
    bot = XianyuReplyBot(config, prompt_overrides)
    live = XianyuLive(cookies_str, config, config_manager)
    live.set_bot(bot)
```

### main.py (python/)

`handle_message()` checks `self.graph` vs `self.bot`:
- If graph: calls `process_message(self.graph, user_msg, item_desc, user_id, user_name, thread_id)`
- If bot: existing `self.bot.generate_reply()` path

---

## 10. Electron GUI Changes

### New Settings fields (Settings.vue)

- `FEISHU_WEBHOOK_URL` — text input, placeholder "https://open.feishu.cn/open-apis/bot/v2/hook/..."
- `EMBEDDING_MODEL` — text input, placeholder "text-embedding-v3 (可选，留空使用关键词搜索)"
- `USE_LANGGRAPH` — toggle switch, default on

### New View: Knowledge Base (/knowledge)

Route added to Vue Router. New `KnowledgeBase.vue` component:
- Table listing all cases from `knowledge/cases.json`
- Add button → modal form (title, description, tags, price, duration, complexity)
- Edit / Delete per-row actions
- Cases saved via new IPC channel: `knowledge:getCases`, `knowledge:saveCases`
- Electron main: reads/writes `knowledge/cases.json` (relative to Python binary or `__file__`)

### IPC additions (ipcHandlers.js)

```javascript
ipcMain.handle('knowledge:getCases', async () => { /* read cases.json */ })
ipcMain.handle('knowledge:saveCases', async (_, cases) => { /* write cases.json */ })
```

### Navigation (App.vue / router)

Add "知识库" menu item linking to `/knowledge`.

---

## 11. Dependencies (python/requirements.txt additions)

```
langchain>=0.3.0
langchain-openai>=0.2.0
langgraph>=0.2.0
langgraph-checkpoint-sqlite>=3.0.0
faiss-cpu>=1.7.4            # Optional; only needed if EMBEDDING_MODEL configured
numpy>=1.24.0
```

Note: `transformers` and `torch` are NOT added (keyword-only sentiment).

---

## 12. Error Handling & Graceful Degradation

| Component | Failure mode | Fallback |
|---|---|---|
| FAISS index | Import fails / no embeddings | Keyword-only search |
| EMBEDDING_MODEL | Not configured | Skip vector search |
| Feishu webhook | Not configured or HTTP error | Log warning, continue |
| LangGraph analyze_context LLM call | Timeout / error | Keyword-based stage detection |
| call_model | LLM error | Return `"-"` (no reply) |
| USE_LANGGRAPH=False | Feature flag off | Original XianyuReplyBot path |

---

## 13. Out of Scope

- Transformer-based sentiment model (user chose keyword-only)
- Deal/order confirmed Feishu notification (user chose handover-only)
- Initial case library data (user will populate)
- Changes to root-level `main.py` / `XianyuAgent.py` (CLI mode not targeted)
- Monitoring/evaluation dashboards (not requested)

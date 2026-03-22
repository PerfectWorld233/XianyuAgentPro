import sqlite3
import os
from datetime import datetime
from loguru import logger


DEFAULT_CONFIG = {
    "API_KEY": "",
    "COOKIES_STR": "",
    "MODEL_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "MODEL_NAME": "qwen-max",
    "TOGGLE_KEYWORDS": "。",
    "SIMULATE_HUMAN_TYPING": "False",
    "HEARTBEAT_INTERVAL": "15",
    "HEARTBEAT_TIMEOUT": "5",
    "TOKEN_REFRESH_INTERVAL": "3600",
    "TOKEN_RETRY_INTERVAL": "300",
    "MANUAL_MODE_TIMEOUT": "3600",
    "MESSAGE_EXPIRE_TIME": "300000",
}

PROMPT_NAMES = ["classify_prompt", "price_prompt", "tech_prompt", "default_prompt"]

DEFAULT_PROMPTS = {
    "classify_prompt": """你是一个闲鱼客服意图分类器。
根据用户消息，判断其意图，返回以下之一：
- price：用户在询价或砍价（含"多少钱"、"便宜点"、"能少吗"、"最低"等）
- tech：用户在询问商品参数、规格、使用方法等技术问题
- no_reply：系统消息、物流通知、已读回执等无需回复的内容
- default：其他普通咨询、寒暄、催发货等

只返回上述标签之一，不要有任何解释。""",

    "price_prompt": """角色说明：
你是一位经验丰富的闲鱼卖家专员，擅长在保持友好关系的前提下守住价格底线，并引导买家进行价格协商。

你的策略：
1. 优惠有限：设定明确优惠上限，100元以下商品价格让步不超过10%。
2. 递减让步原则：每次报价从最大让步开始，之后逐渐减小优惠幅度。
3. 价值强调：突出商品品质和价值，转移价格焦点。
4. 配件诱导：适时提供小配件免费赠送来促成交易。

底价策略：
1. 第一次还价：报出比底价高20%的价格（留出空间）。
2. 第二次还价：让步到底价+10%。
3. 第三次及以后：坚守底价，强调不能再降。

回复要求：
- 语气友好，不卑不亢
- 每次回复不超过50字
- 使用"亲"等亲切称呼""",

    "tech_prompt": """角色说明：
你是一位专业的商品技术专员，对该商品的技术参数、使用方法和常见问题了如指掌。当用户询问的是商品技术或使用问题，你都能给出专业、易懂的解答。

回答要求：
1. 专业易懂：用专业知识，但将复杂术语转化为通俗语言，让普通用户也能理解。
2. 商品对比：客观分析同类商品的优缺点，为不同使用场景推荐最适合的选择。
3. 诚信回答：基于商品信息和客观常识，确保回答准确，不过度夸大商品性能。

回复要求：
- 每次回复不超过80字
- 条理清晰，直接回答问题""",

    "default_prompt": """角色说明：
你是一位专业的电商客服，专注于为商品销售和服务，对商品使用咨询、售后问题和综合问题、还价、交货时间和售后等都有丰富的实战经验。回答问题时有时会涉及到技术与售后技巧，但也要注意，销售的商品为商品，大部分没有官方保修，不能快递免费寄回，要仔细阅读商品信息为准。

对话回复要求：
1. 使用短句，每句不超过10字，总字数不超过40字
2. 使用"全新"、"超值"、"实惠"等积极词汇
3. 结尾加购买引导，如"喜欢可以直接拍哦～"
4. 语气亲切自然，像朋友推荐商品"""
}


class AppConfigManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    name TEXT PRIMARY KEY NOT NULL,
                    content TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def seed_defaults(self, prompt_dir: str):
        """Seed default config and prompts if tables are empty."""
        with self._conn() as conn:
            # Seed config
            existing = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]
            if existing == 0:
                now = datetime.now().isoformat()
                conn.executemany(
                    "INSERT OR IGNORE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                    [(k, v, now) for k, v in DEFAULT_CONFIG.items()]
                )
                logger.info("已写入默认配置")

            # Seed prompts
            existing_prompts = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
            if existing_prompts == 0:
                now = datetime.now().isoformat()
                for name, content in DEFAULT_PROMPTS.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO prompts (name, content, updated_at) VALUES (?, ?, ?)",
                        (name, content, now)
                    )
                logger.info("已写入默认 Prompt")

            conn.commit()

    def _load_seed_prompt(self, prompt_dir: str, name: str) -> str:
        """Load prompt from file, trying custom then example."""
        for filename in [f"{name}.txt", f"{name}_example.txt"]:
            path = os.path.join(prompt_dir, filename)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        logger.warning(f"未找到 prompt 文件: {name}")
        return ""

    def get_config(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("SELECT key, value FROM config").fetchall()
        return {k: v for k, v in rows}

    def get_value(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_value(self, key: str, value: str):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now)
            )
            conn.commit()

    def set_many(self, data: dict):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                [(k, v, now) for k, v in data.items()]
            )
            conn.commit()

    def get_prompt(self, name: str) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT content FROM prompts WHERE name = ?", (name,)).fetchone()
        return row[0] if row else ""

    def get_all_prompts(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("SELECT name, content FROM prompts").fetchall()
        return {name: content for name, content in rows}

    def set_prompt(self, name: str, content: str):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO prompts (name, content, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at",
                (name, content, now)
            )
            conn.commit()

    def set_many_prompts(self, data: dict):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO prompts (name, content, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at",
                [(name, content, now) for name, content in data.items()]
            )
            conn.commit()

    def update_cookies(self, cookie_str: str):
        self.set_value("COOKIES_STR", cookie_str)
        logger.debug("已更新数据库中的 COOKIES_STR")

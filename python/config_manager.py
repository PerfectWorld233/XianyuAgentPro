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
                for name in PROMPT_NAMES:
                    content = self._load_seed_prompt(prompt_dir, name)
                    if content:
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

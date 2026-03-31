# python/knowledge_base/manager.py
import base64
import json
import os
import re
import sqlite3
from typing import List, Dict, Optional

import numpy as np
import faiss
from loguru import logger
from openai import AsyncOpenAI

EMBED_BATCH_SIZE = 25


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
            # Fix 3: chunk API calls to stay within the 25-text limit per request
            all_vectors = []
            for i in range(0, len(texts), EMBED_BATCH_SIZE):
                batch = texts[i:i + EMBED_BATCH_SIZE]
                batch_vecs = await self._embed(batch)
                all_vectors.append(batch_vecs)
            vectors = np.vstack(all_vectors)
            # Fix 2: wrap writes in a transaction
            conn = sqlite3.connect(self.db_path)
            try:
                with conn:
                    for row, vec in zip(need_embed, vectors):
                        conn.execute(
                            "UPDATE knowledge SET embedding = ?, updated_at = datetime('now') WHERE id = ?",
                            (vec.tobytes(), row["id"])
                        )
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

        # Fix 1: normalize vectors loaded from SQLite before adding to FAISS
        # np.frombuffer returns a read-only array, so .copy() is required before division
        all_vecs = []
        id_map = []
        for r in rows:
            if r["embedding"] is None:
                continue
            vec = np.frombuffer(r["embedding"], dtype=np.float32).copy()
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
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
        # Fix 7: use regex for robust markdown code fence stripping
        if content.startswith("```"):
            content = re.sub(r'^```[^\n]*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()
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
        # Fix 7: use regex for robust markdown code fence stripping
        if content.startswith("```"):
            content = re.sub(r'^```[^\n]*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()
        return json.loads(content)

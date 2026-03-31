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

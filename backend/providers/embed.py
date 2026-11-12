"""向量化 —— AIHubMix text-embedding-v4(与 VLM 同一个 key)。

无 key 时用 _hash_embed 兜底(确定性哈希向量),保证链路能跑、检索有结果,
只是语义质量退化;有 key 后自动切回真 embedding。
"""
from __future__ import annotations

import hashlib
from typing import Optional

from openai import OpenAI

from config import load_config, require_env


def _client() -> OpenAI:
    cfg = load_config()["aihubmix"]
    return OpenAI(api_key=require_env("AIHUBMIX_API_KEY"), base_url=cfg["base_url"])


def embed(text: str) -> list[float]:
    cfg = load_config()["aihubmix"]
    client = _client()
    resp = client.embeddings.create(model=cfg["embed_model"], input=text[:2000])
    return resp.data[0].embedding


def hash_embed(text: str, dim: int = 1024) -> list[float]:
    """确定性伪 embedding(无 key 兜底):把词哈希进固定维度,做 L2 归一化。"""
    vec = [0.0] * dim
    for tok in text.replace(",", " ").split():
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]

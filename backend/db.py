"""SQLite 数据层 —— 三张表对应方案里的收录/知识/日志。

向量不走 sqlite 扩展(系统 Python 不支持加载扩展),而是把 embedding 以
float32 blob 存进 visual_memory,检索时用 numpy 暴力算余弦(500~数千条 <1ms)。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from config import ROOT, load_config

SCHEMA = """
-- 原始素材(收录进来的图,尚未理解)
CREATE TABLE IF NOT EXISTS source_material (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path    TEXT NOT NULL,           -- 相对 data/uploads 的路径
    source       TEXT,                    -- upload | url | batch
    upload_batch TEXT,                    -- 批次/任务 id
    orig_desc    TEXT,                    -- 收录时填的原始描述
    status       TEXT DEFAULT 'pending',  -- pending | analyzed | reviewed
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);

-- 理解后的领域知识(人工审核定稿即写入 embedding)
CREATE TABLE IF NOT EXISTS visual_memory (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id  INTEGER NOT NULL REFERENCES source_material(id),
    title        TEXT,
    description  TEXT,                    -- 用于生成 embedding 的综合描述
    region       TEXT,
    era          TEXT,
    visual_tags  TEXT,                    -- JSON 数组
    culture_tags TEXT,                    -- JSON 数组
    story_tags   TEXT,                    -- JSON 数组
    emotion_tags TEXT,                    -- JSON 数组
    embedding    BLOB,                    -- float32 向量
    reviewed     INTEGER DEFAULT 0,       -- 是否人工审核过
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);

-- 收录历史
CREATE TABLE IF NOT EXISTS collection_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch       TEXT,
    source      TEXT,
    count       INTEGER,
    status      TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
"""

_JSON_FIELDS = ("visual_tags", "culture_tags", "story_tags", "emotion_tags")


def db_path() -> Path:
    return ROOT / load_config()["database"]["path"]


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = connect()
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """把一行转 dict,并把 JSON 字段解析回列表,去掉 embedding blob。"""
    d = dict(row)
    for f in _JSON_FIELDS:
        if f in d and isinstance(d[f], str):
            try:
                d[f] = json.loads(d[f])
            except Exception:
                d[f] = []
    d.pop("embedding", None)
    return d


if __name__ == "__main__":
    init_db()
    print("DB initialised at", db_path())

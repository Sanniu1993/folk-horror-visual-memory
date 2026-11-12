"""Module 2/4 —— 视觉理解落库 + 审核定稿 + 向量检索(numpy 暴力 KNN)。"""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Optional

import numpy as np

from config import ROOT, load_config
from db import connect, row_to_dict
from providers import embed as embed_mod
from providers import vlm as vlm_mod


# ---------- 向量打包 ----------

def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="float32")


def _embed_text(text: str) -> list[float]:
    """有 key 走 AIHubMix,失败/无 key 退回哈希兜底(链路不断)。"""
    try:
        return embed_mod.embed(text)
    except Exception:
        dim = load_config()["aihubmix"]["embed_dim"]
        return embed_mod.hash_embed(text, dim)


def _synthesize(mem: dict[str, Any]) -> str:
    """把标题/地域/年代/各类标签/描述综合成一句,用于生成 embedding 与增强 prompt。"""
    parts = [mem.get("title", ""), mem.get("region", ""), mem.get("era", "")]
    for f in ("culture_tags", "story_tags", "emotion_tags", "visual_elements"):
        v = mem.get(f) or []
        if isinstance(v, list):
            parts += v
    parts.append(mem.get("description", ""))
    return ",".join(str(p) for p in parts if p)


# ---------- Module 2:理解 ----------

def analyze_material(material_id: int, use_mock: bool = False) -> dict[str, Any]:
    """对一张素材跑 VLM,写入 visual_memory 草稿(reviewed=0,暂不算 embedding)。"""
    con = connect()
    try:
        row = con.execute("SELECT * FROM source_material WHERE id=?", (material_id,)).fetchone()
        if row is None:
            raise ValueError(f"material {material_id} 不存在")
        img = ROOT / load_config()["paths"]["uploads"] / row["file_path"]
        result = vlm_mod.mock(img) if use_mock else vlm_mod.understand(img)

        existing = con.execute("SELECT id FROM visual_memory WHERE material_id=?",
                               (material_id,)).fetchone()
        fields = (
            result.get("title"), result.get("description"),
            result.get("region"), result.get("era"),
            json.dumps(result.get("visual_elements", []), ensure_ascii=False),
            json.dumps(result.get("culture_tags", []), ensure_ascii=False),
            json.dumps(result.get("story_tags", []), ensure_ascii=False),
            json.dumps(result.get("emotion_tags", []), ensure_ascii=False),
        )
        if existing:
            con.execute(
                "UPDATE visual_memory SET title=?,description=?,region=?,era=?,"
                "visual_tags=?,culture_tags=?,story_tags=?,emotion_tags=?,reviewed=0 WHERE id=?",
                (*fields, existing["id"]))
            mem_id = existing["id"]
        else:
            cur = con.execute(
                "INSERT INTO visual_memory(material_id,title,description,region,era,"
                "visual_tags,culture_tags,story_tags,emotion_tags,reviewed) "
                "VALUES (?,?,?,?,?,?,?,?,?,0)", (material_id, *fields))
            mem_id = cur.lastrowid
        con.execute("UPDATE source_material SET status='analyzed' WHERE id=?", (material_id,))
        con.commit()
        return get_memory(mem_id)
    finally:
        con.close()


# ---------- Module 3:审核定稿 ----------

def save_review(memory_id: int, edited: dict[str, Any]) -> dict[str, Any]:
    """人工审核修改后保存:更新字段 + 计算 embedding + 标记 reviewed。"""
    con = connect()
    try:
        row = con.execute("SELECT * FROM visual_memory WHERE id=?", (memory_id,)).fetchone()
        if row is None:
            raise ValueError(f"memory {memory_id} 不存在")
        mem = row_to_dict(row)
        mem.update(edited)  # 应用人工修改

        text = _synthesize(mem)
        vec = _embed_text(text)
        con.execute(
            "UPDATE visual_memory SET title=?,description=?,region=?,era=?,"
            "visual_tags=?,culture_tags=?,story_tags=?,emotion_tags=?,embedding=?,reviewed=1 "
            "WHERE id=?",
            (mem.get("title"), mem.get("description"), mem.get("region"), mem.get("era"),
             json.dumps(mem.get("visual_tags", []), ensure_ascii=False),
             json.dumps(mem.get("culture_tags", []), ensure_ascii=False),
             json.dumps(mem.get("story_tags", []), ensure_ascii=False),
             json.dumps(mem.get("emotion_tags", []), ensure_ascii=False),
             _pack(vec), memory_id))
        con.execute("UPDATE source_material SET status='reviewed' WHERE id=?",
                    (mem["material_id"],))
        con.commit()
        return get_memory(memory_id)
    finally:
        con.close()


# ---------- 查询 ----------

def get_memory(memory_id: int) -> dict[str, Any]:
    con = connect()
    try:
        row = con.execute("SELECT * FROM visual_memory WHERE id=?", (memory_id,)).fetchone()
        return row_to_dict(row) if row else {}
    finally:
        con.close()


def list_materials(status: Optional[str] = None,
                   exclude_reviewed: bool = False) -> list[dict[str, Any]]:
    """列素材 + 其 memory(供收录/审核列表)。exclude_reviewed=True 时不返回已入库的。"""
    con = connect()
    try:
        q = ("SELECT sm.*, vm.id AS memory_id, vm.reviewed FROM source_material sm "
             "LEFT JOIN visual_memory vm ON vm.material_id = sm.id")
        conds, args = [], []
        if status:
            conds.append("sm.status=?"); args.append(status)
        if exclude_reviewed:
            conds.append("sm.status != 'reviewed'")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY sm.id DESC"
        return [dict(r) for r in con.execute(q, tuple(args)).fetchall()]
    finally:
        con.close()


def list_memories() -> list[dict[str, Any]]:
    """列已审核入库的视觉记忆(供 Memory 库页查看/编辑/删除)。"""
    con = connect()
    try:
        rows = con.execute(
            "SELECT vm.*, sm.file_path, sm.orig_desc, sm.source "
            "FROM visual_memory vm JOIN source_material sm ON sm.id = vm.material_id "
            "WHERE vm.reviewed=1 ORDER BY vm.id DESC").fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        con.close()


def delete_memory(memory_id: int, remove_material: bool = True) -> dict[str, Any]:
    """从 Memory 库删除一条:删 visual_memory;remove_material=True 时连同素材与图片文件一并删除。

    remove_material=False 则保留素材、把状态退回 analyzed(等于"撤回入库,回到审核")。
    """
    con = connect()
    try:
        row = con.execute("SELECT * FROM visual_memory WHERE id=?", (memory_id,)).fetchone()
        if row is None:
            raise ValueError(f"memory {memory_id} 不存在")
        material_id = row["material_id"]
        file_row = con.execute("SELECT file_path FROM source_material WHERE id=?",
                               (material_id,)).fetchone()
        con.execute("DELETE FROM visual_memory WHERE id=?", (memory_id,))
        if remove_material:
            con.execute("DELETE FROM source_material WHERE id=?", (material_id,))
        else:
            con.execute("UPDATE source_material SET status='analyzed' WHERE id=?",
                        (material_id,))
        con.commit()
        if remove_material and file_row:
            fp = ROOT / load_config()["paths"]["uploads"] / file_row["file_path"]
            try:
                fp.unlink(missing_ok=True)
            except Exception:
                pass  # 文件删不掉不影响数据一致性
        return {"deleted": memory_id, "material_id": material_id,
                "removed_material": remove_material}
    finally:
        con.close()


# ---------- Module 4:检索 ----------

def retrieve(query_text: str, top_k: Optional[int] = None) -> list[dict[str, Any]]:
    """按 query 向量检索已审核的视觉记忆,返回 Top-K(带相似度)。"""
    k = top_k or load_config()["retrieval"]["top_k"]
    qv = np.array(_embed_text(query_text), dtype="float32")
    con = connect()
    try:
        rows = con.execute(
            "SELECT * FROM visual_memory WHERE reviewed=1 AND embedding IS NOT NULL").fetchall()
    finally:
        con.close()
    if not rows:
        return []
    # 只比对与 query 同维度的向量(避免 mock 哈希向量与真 embedding 混存时维度不一崩溃)。
    rows = [r for r in rows if len(_unpack(r["embedding"])) == qv.shape[0]]
    if not rows:
        return []
    mats = np.stack([_unpack(r["embedding"]) for r in rows])
    sims = mats @ qv / (np.linalg.norm(mats, axis=1) * np.linalg.norm(qv) + 1e-9)
    order = np.argsort(-sims)[:k]
    out = []
    for i in order:
        d = row_to_dict(rows[int(i)])
        d["score"] = round(float(sims[int(i)]), 4)
        out.append(d)
    return out

"""FastAPI —— 收录 / 理解 / 审核 / 检索 / 增强 的 API + 前端托管。

运行:
    uvicorn main:app --reload --app-dir backend
打开 http://127.0.0.1:8100
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import collection
import memory as memory_mod
import prompt_enhance
from config import ROOT, load_config
from db import init_db
from providers import llm

init_db()
app = FastAPI(title="Chinese Folk Horror Visual Memory System", version="0.1.0")

UPLOADS = ROOT / load_config()["paths"]["uploads"]
UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")
FRONTEND = ROOT / "frontend"

PLAIN_PROMPT = "A Chinese horror scene"  # 对照组:未增强的裸 prompt


# ---------- 收录 ----------
class FolderReq(BaseModel):
    folder: str


@app.post("/api/collect/folder")
def collect_folder(req: FolderReq) -> dict[str, Any]:
    try:
        return collection.import_folder(req.folder)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.post("/api/collect/upload")
async def collect_upload(file: UploadFile = File(...), orig_desc: str = Form("")) -> dict[str, Any]:
    data = await file.read()
    return collection.add_single(data, file.filename or "img.jpg", orig_desc)


# ---------- 理解 ----------
@app.post("/api/analyze/{material_id}")
def analyze(material_id: int, mock: bool = False) -> dict[str, Any]:
    try:
        return memory_mod.analyze_material(material_id, use_mock=mock)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/analyze_batch")
def analyze_batch(mock: bool = False) -> dict[str, Any]:
    """把所有 pending 素材跑一遍理解。"""
    todo = [m for m in memory_mod.list_materials(status="pending")]
    done, errors = 0, []
    for m in todo:
        try:
            memory_mod.analyze_material(m["id"], use_mock=mock); done += 1
        except Exception as e:
            errors.append({"id": m["id"], "error": str(e)})
    return {"analyzed": done, "errors": errors}


# ---------- 审核 ----------
class ReviewReq(BaseModel):
    edited: dict[str, Any]


@app.post("/api/review/{memory_id}")
def review(memory_id: int, req: ReviewReq) -> dict[str, Any]:
    try:
        return memory_mod.save_review(memory_id, req.edited)
    except Exception as e:
        raise HTTPException(400, str(e))


# ---------- 列表 ----------
@app.get("/api/materials")
def materials(status: Optional[str] = None,
              exclude_reviewed: bool = False) -> list[dict[str, Any]]:
    return memory_mod.list_materials(status, exclude_reviewed=exclude_reviewed)


@app.get("/api/memories")
def memories() -> list[dict[str, Any]]:
    """已入库 Memory 列表(供 Memory 库页)。"""
    return memory_mod.list_memories()


# ---------- 纯检索(对外服务:供其它系统按 query 取视觉记忆,无 LLM 无副作用)----------
class RetrieveReq(BaseModel):
    query: str
    top_k: Optional[int] = None


@app.post("/api/retrieve")
def retrieve(req: RetrieveReq) -> dict[str, Any]:
    """按文本 query 向量检索已入库记忆,返回 Top-K(带相似度 + 图片 url)。

    这是给外部系统(如 ai-horror-generator)对接用的稳定接口:只做检索,
    不触发理解/审核/写库,天然只读、幂等、可随时下线(调用方 fail-open)。
    """
    q = (req.query or "").strip()
    if not q:
        return {"query": q, "memories": []}
    mems = memory_mod.retrieve(q, top_k=req.top_k)
    return {"query": q,
            "memories": [{**m, "url": f"/uploads/{_file_of(m['material_id'])}"}
                         for m in mems]}


@app.get("/api/memory/{memory_id}")
def get_memory(memory_id: int) -> dict[str, Any]:
    m = memory_mod.get_memory(memory_id)
    if not m:
        raise HTTPException(404, "not found")
    return m


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int, remove_material: bool = True) -> dict[str, Any]:
    try:
        return memory_mod.delete_memory(memory_id, remove_material=remove_material)
    except ValueError as e:
        raise HTTPException(404, str(e))


# ---------- 故事 → 检索 → 增强(核心闭环 / demo money-shot)----------
class StoryReq(BaseModel):
    story: str


@app.post("/api/story")
def story(req: StoryReq) -> dict[str, Any]:
    story_req = llm.analyze_story(req.story)
    query = story_req.get("query") or req.story
    memories = memory_mod.retrieve(query)
    enhanced = prompt_enhance.enhance(story_req, memories)
    return {
        "story_req": story_req,
        "query": query,
        "memories": [{**m, "url": f"/uploads/{_file_of(m['material_id'])}"} for m in memories],
        "plain_prompt": PLAIN_PROMPT,
        "enhanced_prompt": enhanced,
    }


def _file_of(material_id: int) -> str:
    from db import connect
    con = connect()
    try:
        r = con.execute("SELECT file_path FROM source_material WHERE id=?", (material_id,)).fetchone()
        return r["file_path"] if r else ""
    finally:
        con.close()


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    from db import connect
    con = connect()
    try:
        total = con.execute("SELECT COUNT(*) c FROM source_material").fetchone()["c"]
        reviewed = con.execute("SELECT COUNT(*) c FROM visual_memory WHERE reviewed=1").fetchone()["c"]
        analyzed = con.execute("SELECT COUNT(*) c FROM source_material WHERE status='analyzed'").fetchone()["c"]
        return {"materials": total, "analyzed": analyzed, "reviewed": reviewed}
    finally:
        con.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    # no-store:前端改动后普通刷新即可生效,避免浏览器缓存旧页面。
    return FileResponse(str(FRONTEND / "index.html"),
                        headers={"Cache-Control": "no-store, must-revalidate"})

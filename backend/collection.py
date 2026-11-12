"""Module 1 —— 批量素材收录。扫描文件夹,把图片复制进 uploads,入库 source_material。"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from config import ROOT, load_config
from db import connect

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _uploads_dir() -> Path:
    d = ROOT / load_config()["paths"]["uploads"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def import_folder(folder: str, source: str = "batch") -> dict[str, Any]:
    """递归导入一个文件夹下的所有图片。返回批次信息。"""
    src = Path(folder).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"目录不存在:{src}")
    files = [p for p in src.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
    batch = uuid.uuid4().hex[:12]
    up = _uploads_dir()
    con = connect()
    try:
        n = 0
        for p in files:
            dest_name = f"{batch}_{n:04d}{p.suffix.lower()}"
            shutil.copy2(p, up / dest_name)
            con.execute(
                "INSERT INTO source_material(file_path, source, upload_batch, orig_desc) "
                "VALUES (?,?,?,?)",
                (dest_name, source, batch, p.parent.name),  # 用父目录名当原始描述/分类
            )
            n += 1
        con.execute(
            "INSERT INTO collection_log(batch, source, count, status) VALUES (?,?,?,?)",
            (batch, source, n, "imported"),
        )
        con.commit()
    finally:
        con.close()
    return {"batch": batch, "count": n, "source": source}


def add_single(file_bytes: bytes, filename: str, orig_desc: str = "",
               source: str = "upload") -> dict[str, Any]:
    """单张上传(网页手动收录用)。"""
    batch = uuid.uuid4().hex[:12]
    ext = Path(filename).suffix.lower() or ".jpg"
    dest_name = f"{batch}_0000{ext}"
    (_uploads_dir() / dest_name).write_bytes(file_bytes)
    con = connect()
    try:
        cur = con.execute(
            "INSERT INTO source_material(file_path, source, upload_batch, orig_desc) "
            "VALUES (?,?,?,?)", (dest_name, source, batch, orig_desc))
        con.commit()
        mid = cur.lastrowid
    finally:
        con.close()
    return {"material_id": mid, "file_path": dest_name, "batch": batch}

"""视觉理解 Agent —— Qwen-VL(AIHubMix OpenAI 兼容接口)。

输入一张图 -> 输出中国民俗文化视角的结构化 JSON。若无 key 或调用失败,
调用方可捕获异常处理;另提供 mock() 便于无 key 时先跑通链路。
"""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from openai import OpenAI

from config import load_config, require_env

SYSTEM = "你是一名中国民俗文化视觉研究专家,只输出 JSON,不要多余文字。"

PROMPT = """分析这张图片,用于中国民俗恐怖故事的视觉素材库。严格按以下 JSON 输出:
{
  "title": "简短中文标题",
  "type": "location | architecture | person | object | ritual | atmosphere",
  "region": "地域(如 贵州;不确定填 unknown)",
  "era": "年代(如 1990s;不确定填 unknown)",
  "visual_elements": ["画面元素英文关键词,3-8个"],
  "culture_tags": ["民俗/文化关联,中文,如 祖先崇拜、土葬"],
  "story_tags": ["适合的故事类型,中文,如 尸煞、冥婚、祖宅、葬礼"],
  "emotion_tags": ["氛围情绪,中文,如 孤独、阴森、神秘"],
  "description": "一句英文描述,可直接用于图像生成提示词",
  "horror_value": "1-5 的恐怖氛围价值(整数)"
}
只输出这个 JSON。"""


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def _client() -> OpenAI:
    cfg = load_config()["aihubmix"]
    return OpenAI(api_key=require_env("AIHUBMIX_API_KEY"), base_url=cfg["base_url"])


def understand(image_path: Path) -> dict[str, Any]:
    """调用 Qwen-VL 分析图片,返回解析后的 dict。"""
    cfg = load_config()["aihubmix"]
    client = _client()
    resp = client.chat.completions.create(
        model=cfg["vlm_model"],
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
            ]},
        ],
        temperature=0.3,
    )
    text = resp.choices[0].message.content or "{}"
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def mock(image_path: Path) -> dict[str, Any]:
    """无 key 时的占位结果,用于先跑通链路。"""
    return {
        "title": f"[mock] {image_path.stem}",
        "type": "location", "region": "贵州", "era": "1990s",
        "visual_elements": ["stone wall", "wooden door", "mountain village"],
        "culture_tags": ["农村", "祖先崇拜"],
        "story_tags": ["祖宅", "葬礼"],
        "emotion_tags": ["孤独", "神秘"],
        "description": "A lonely old stone house in a Guizhou mountain village at dusk",
        "horror_value": 3,
    }

"""故事拆解 Agent —— DeepSeek。把一句故事拆成结构化视觉需求。"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from config import load_config, require_env

SYSTEM = """你是中国民俗恐怖故事的视觉导演。把用户的故事/设定拆成结构化视觉需求,
只输出 JSON:
{
  "location": "地点(如 贵州农村)",
  "era": "年代(如 1990s)",
  "scene": ["核心场景英文关键词"],
  "emotion": "整体情绪(英文)",
  "requirements": ["需要出现的视觉要素,英文,如 mountain village, traditional funeral, night atmosphere"],
  "query": "用于检索视觉记忆的一句中文描述(融合 地点/年代/场景/民俗/氛围)"
}"""


def analyze_story(story: str) -> dict[str, Any]:
    cfg = load_config()["deepseek"]
    client = OpenAI(api_key=require_env("DEEPSEEK_API_KEY"), base_url=cfg["base_url"])
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": story}],
        temperature=cfg.get("temperature", 0.4),
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content or "{}")

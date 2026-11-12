"""Module 7 —— Prompt 增强。把检索到的视觉记忆「综合」(而非拼接)成一条干净、
地道的英文生成提示。综合优先用 DeepSeek;失败则退回结构化拼接兜底。
"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from config import load_config, require_env

SYSTEM = """You are a prompt engineer for Chinese folk-horror image generation.
Given a story's visual requirements and several retrieved reference visual-memory
entries (region/era/elements/culture), SYNTHESIZE ONE coherent English image prompt.
Merge overlapping details, resolve conflicts, keep it concrete and culturally accurate
(correct Chinese region, era, folk elements; East-Asian people). Do NOT list tags;
write a flowing prompt. Output ONLY JSON: {"prompt": "..."}"""


def _memory_brief(memories: list[dict[str, Any]]) -> str:
    lines = []
    for m in memories:
        lines.append(
            f"- {m.get('title','')} | region={m.get('region','')} era={m.get('era','')} "
            f"| elements={m.get('visual_tags', [])} | culture={m.get('culture_tags', [])} "
            f"| {m.get('description','')}")
    return "\n".join(lines)


def enhance(story_req: dict[str, Any], memories: list[dict[str, Any]]) -> str:
    """返回增强后的英文 prompt。"""
    user = (
        "Story visual requirements:\n" + json.dumps(story_req, ensure_ascii=False, indent=2)
        + "\n\nRetrieved visual memory:\n" + _memory_brief(memories)
        + "\n\nNow synthesize the final image prompt."
    )
    try:
        cfg = load_config()["deepseek"]
        client = OpenAI(api_key=require_env("DEEPSEEK_API_KEY"), base_url=cfg["base_url"])
        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            temperature=0.4, response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content or "{}").get("prompt", "").strip() \
            or _fallback(story_req, memories)
    except Exception:
        return _fallback(story_req, memories)


def _fallback(story_req: dict[str, Any], memories: list[dict[str, Any]]) -> str:
    """无 key/失败时的结构化拼接兜底。"""
    bits: list[str] = []
    if story_req.get("location"):
        bits.append(str(story_req["location"]))
    if story_req.get("era"):
        bits.append(str(story_req["era"]))
    bits += [str(x) for x in story_req.get("requirements", [])]
    for m in memories[:3]:
        bits += [str(x) for x in (m.get("visual_tags") or [])][:3]
    seen, uniq = set(), []
    for b in bits:
        if b and b not in seen:
            seen.add(b); uniq.append(b)
    tail = "Chinese folk horror style, cinematic realistic photography, misty, cold tone, film grain"
    return ", ".join(uniq + [tail])

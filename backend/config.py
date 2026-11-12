"""配置加载:读取 config.yaml + .env(项目根目录)。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """把项目根 .env 的 KEY=VALUE 读进环境变量(已存在的不覆盖)。"""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config() -> dict[str, Any]:
    _load_dotenv()
    with open(ROOT / "config.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val or val.startswith("sk-xxxx"):
        raise RuntimeError(
            f"{name} 未设置。请在项目根建 .env(参考 .env.example)并填入真实 key。"
        )
    return val

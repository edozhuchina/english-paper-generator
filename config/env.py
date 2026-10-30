"""极简 .env 读取器（避免为此引入额外依赖）。

行为：
1. 读取项目根目录 .env，KEY=VALUE 形式，忽略 # 注释与空行
2. 只在不覆盖已存在环境变量的前提下注入 os.environ
3. 文件不存在时静默跳过（生产环境用真实环境变量）
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    with ENV_FILE.open(encoding="utf-8") as fp:
        for raw in fp:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def get_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

"""A 股代码字典：优先读 desktop 缓存 JSON，否则尝试 akshare。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import D_DATA_DIR

CACHE_FILE = Path(D_DATA_DIR) / "stock_names_cache.json"

_codes: dict[str, str] | None = None


def load_stock_codes_dict() -> dict[str, str]:
    global _codes
    if _codes is not None:
        return _codes
    _codes = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            raw = data.get("stock_codes_dict") or {}
            for k, v in raw.items():
                if k and v:
                    _codes[str(k).strip()] = str(v).strip()
        except OSError:
            pass
    if len(_codes) >= 4000:
        return _codes
    try:
        import akshare as ak  # type: ignore
    except ImportError:
        return _codes

    try:
        df = ak.stock_info_a_code_name()
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                c, n = row.get("code"), row.get("name")
                if c is not None and n is not None:
                    _codes[str(c).strip()] = str(n).strip()
    except Exception:
        pass
    try:
        dfk = ak.stock_info_kcb_name_code()
        if dfk is not None and not dfk.empty:
            for _, row in dfk.iterrows():
                c, n = row.get("SECURITY_CODE_A"), row.get("SECURITY_NAME_A")
                if c is not None and n is not None:
                    _codes[str(c).strip()] = str(n).strip()
    except Exception:
        pass
    return _codes


def invalidate_cache() -> None:
    global _codes
    _codes = None

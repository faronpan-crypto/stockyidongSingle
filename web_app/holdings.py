"""多组持仓网格（每组 80 槽位），对应 desktop holding_stocks_1 … _14。"""
from __future__ import annotations

import json
from typing import Any

from .db import HOLDINGS_JSON

# 与桌面 position_trading_notebook 标签文案对齐（持仓 7–14 刷新后变为 MMDD，存在 tab_titles）
GROUP_LABELS: dict[str, str] = {
    "1": "持仓",
    "2": "龙头股",
    "3": "15Min",
    "4": "Main",
    "5": "持仓历史股",
    "6": "同花顺",
    "7": "持仓1",
    "8": "持仓2",
    "9": "持仓3",
    "10": "持仓4",
    "11": "持仓5",
    "12": "持仓6",
    "13": "持仓7",
    "14": "持仓8",
}


def _default_tab_titles() -> dict[str, str]:
    return {str(i): GROUP_LABELS[str(i)] for i in range(7, 15)}


def _default_state() -> dict[str, Any]:
    return {
        "groups": {str(i): [None] * 80 for i in range(1, 15)},
        "group_labels": GROUP_LABELS.copy(),
        "tab_titles": _default_tab_titles(),
    }


DEFAULT_STATE = _default_state()


def display_tab_title(state: dict[str, Any], group_id: str) -> str:
    """侧边栏/子标签显示名：tab_titles 优先（多为 MMDD），否则 group_labels。"""
    tt = state.get("tab_titles") or {}
    if tt.get(group_id):
        return str(tt[group_id])
    gl = state.get("group_labels") or GROUP_LABELS
    return str(gl.get(group_id, GROUP_LABELS.get(group_id, group_id)))


def load_holdings() -> dict[str, Any]:
    HOLDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not HOLDINGS_JSON.exists():
        save_holdings(json.loads(json.dumps(DEFAULT_STATE)))
        return json.loads(json.dumps(DEFAULT_STATE))
    try:
        with open(HOLDINGS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(DEFAULT_STATE))
    groups = data.get("groups") or {}
    for k in range(1, 15):
        key = str(k)
        g = groups.get(key)
        if not isinstance(g, list):
            g = [None] * 80
        while len(g) < 80:
            g.append(None)
        groups[key] = g[:80]
    data["groups"] = groups
    data.setdefault("group_labels", GROUP_LABELS.copy())
    # tab_titles：旧文件可能没有
    tt = data.get("tab_titles")
    if not isinstance(tt, dict):
        data["tab_titles"] = _default_tab_titles()
    else:
        for i in range(7, 15):
            k = str(i)
            tt.setdefault(k, GROUP_LABELS[k])
        data["tab_titles"] = tt
    return data


def save_holdings(state: dict[str, Any]) -> None:
    HOLDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(HOLDINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

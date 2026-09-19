"""
股票异动 Web 版：架构对齐 desktop `StockKeywordAnalyzerGUI` 核心分区：
- 仓位（情绪/大V/昨日 + 三维分数 → 仓位百分比）
- 多组持仓网格（80 位 × 14 组，持久化 JSON）
- 资讯表 news_info（与桌面共用同一 SQLite）
- 从资讯刷新（按日六位代码频次，对齐 get_news_stocks_by_date_and_frequency）
- 任务（白名单子进程调用 src 下爬虫脚本）
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db as dbmod
from .holdings import GROUP_LABELS, load_holdings, save_holdings
from .news_digest import get_news_stocks_by_date_and_frequency
from .position import compute_position, kelly_fraction
from .stock_dict import invalidate_cache

_WEB_ROOT = Path(__file__).resolve().parent
_SRC_DIR = _WEB_ROOT.parent / "src"
_STATIC = _WEB_ROOT / "static"

ALLOWED_CRAWL_SCRIPTS = frozenset(
    {
        "jiuyan_gongshe_crawler.py",
        "jiuyangongshe_crawler.py",
        "taoguba_100_posts_crawler.py",
    }
)

app = FastAPI(title="股票异动 Web", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    dbmod.init_database()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db": dbmod.DB_PATH}


@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
        "db_path": dbmod.DB_PATH,
        "holdings_path": str(dbmod.HOLDINGS_JSON),
        "static_from": str(_STATIC),
        "group_labels": GROUP_LABELS,
    }


# --- 仓位 ---
class PositionBody(BaseModel):
    emotion: str = "阴天"
    v_judge: str = "阴天"
    yesterday: str = "阴天"
    fundamental: int = Field(20, ge=0, le=30)
    technical: int = Field(20, ge=0, le=30)
    sentiment_dim: int = Field(20, ge=0, le=30)
    prev_three_dimension_total: int | None = None


@app.post("/api/position/compute")
def api_position_compute(body: PositionBody) -> dict[str, Any]:
    r = compute_position(
        body.emotion,
        body.v_judge,
        body.yesterday,
        body.fundamental,
        body.technical,
        body.sentiment_dim,
        body.prev_three_dimension_total,
    )
    return {
        "position_percent": round(r.position_percent, 2),
        "total_emotion_score": r.total_emotion_score,
        "three_dimension_total": r.three_dimension_total,
        "t_trading_hint": r.t_trading_hint,
        "new_position_allowed": r.new_position_allowed,
        "indicator_rgb": list(r.rgb),
    }


class KellyBody(BaseModel):
    odds_b: float = Field(..., gt=0)
    win_prob_p: float = Field(..., gt=0, lt=1)


@app.post("/api/kelly")
def api_kelly(body: KellyBody) -> dict[str, float]:
    f, pct = kelly_fraction(body.odds_b, body.win_prob_p)
    return {"kelly_ratio": round(f, 6), "kelly_percent": round(pct, 4)}


# --- 资讯 ---
class NewsCreate(BaseModel):
    tab_name: str
    content: str = ""


@app.get("/api/news")
def list_news(limit: int = 200, q: str | None = None) -> dict[str, Any]:
    limit = max(1, min(limit, 2000))
    conn = dbmod.get_connection()
    cur = conn.cursor()
    if q:
        cur.execute(
            """
            SELECT id, tab_name, substr(content, 1, 500) AS snippet, created_at, updated_at
            FROM news_info
            WHERE tab_name LIKE ? OR content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"%{q}%", f"%{q}%", limit),
        )
    else:
        cur.execute(
            """
            SELECT id, tab_name, substr(content, 1, 500) AS snippet, created_at, updated_at
            FROM news_info
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    rows = cur.fetchall()
    conn.close()
    items = [
        {
            "id": r[0],
            "tab_name": r[1],
            "snippet": r[2],
            "created_at": r[3],
            "updated_at": r[4],
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


@app.get("/api/news/{news_id}")
def get_news(news_id: int) -> dict[str, Any]:
    conn = dbmod.get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, tab_name, content, created_at, updated_at FROM news_info WHERE id = ?",
        (news_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "id": row[0],
        "tab_name": row[1],
        "content": row[2] or "",
        "created_at": row[3],
        "updated_at": row[4],
    }


@app.post("/api/news")
def create_news(body: NewsCreate) -> dict[str, Any]:
    tab = (body.tab_name or "").strip()
    if not tab:
        raise HTTPException(status_code=400, detail="tab_name required")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = dbmod.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO news_info (tab_name, content, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (tab, body.content or "", now, now),
    )
    nid = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": nid, "ok": True}


@app.get("/api/news-digest")
def news_digest(ndays: int = 8) -> dict[str, Any]:
    ndays = max(1, min(ndays, 30))
    days, meta = get_news_stocks_by_date_and_frequency(ndays)
    return {"days": days, "meta": meta}


@app.post("/api/stock-dict/reload")
def reload_stock_dict() -> dict[str, bool]:
    invalidate_cache()
    return {"ok": True}


# --- 持仓 ---
@app.get("/api/holdings")
def api_holdings_get() -> dict[str, Any]:
    return load_holdings()


class HoldingsPatch(BaseModel):
    group_id: str = Field(..., pattern=r"^(?:[1-9]|1[0-4])$")
    index: int = Field(..., ge=0, le=79)
    name: str = ""
    code: str = ""


@app.post("/api/holdings/cell")
def api_holdings_cell(body: HoldingsPatch) -> dict[str, Any]:
    state = load_holdings()
    g = state["groups"].setdefault(body.group_id, [None] * 80)
    while len(g) < 80:
        g.append(None)
    name, code = body.name.strip(), body.code.strip()
    if not name and not code:
        g[body.index] = None
    else:
        g[body.index] = {"name": name, "code": code}
    save_holdings(state)
    return {"ok": True}


class HoldingsBulk(BaseModel):
    group_id: str = Field(..., pattern=r"^(?:[1-9]|1[0-4])$")
    cells: list[dict[str, Any]]  # {index, name, code} or null to clear


@app.post("/api/holdings/bulk")
def api_holdings_bulk(body: HoldingsBulk) -> dict[str, Any]:
    state = load_holdings()
    g = state["groups"].setdefault(body.group_id, [None] * 80)
    while len(g) < 80:
        g.append(None)
    for item in body.cells:
        idx = int(item.get("index", -1))
        if idx < 0 or idx > 79:
            continue
        if item.get("clear"):
            g[idx] = None
            continue
        n = str(item.get("name") or "").strip()
        c = str(item.get("code") or "").strip()
        g[idx] = None if (not n and not c) else {"name": n, "code": c}
    save_holdings(state)
    return {"ok": True}


@app.post("/api/holdings/refresh-from-news")
def api_holdings_refresh_from_news(ndays: int = 8) -> dict[str, Any]:
    """对齐桌面 `_refresh_holding_tabs_from_news`：最近 N 天 → 组 7–14，标签改为 MMDD。"""
    ndays = max(1, min(ndays, 30))
    days, meta = get_news_stocks_by_date_and_frequency(ndays)
    if not days:
        return {"ok": False, "meta": meta}
    state = load_holdings()
    titles: dict[str, str] = state.setdefault("tab_titles", {})
    for i, day in enumerate(days):
        if i >= 8:
            break
        gid = str(7 + i)
        stocks = day.get("stocks") or []
        g = state["groups"].setdefault(gid, [None] * 80)
        while len(g) < 80:
            g.append(None)
        for j in range(80):
            if j < len(stocks):
                s = stocks[j]
                g[j] = {
                    "name": str(s.get("name") or ""),
                    "code": str(s.get("code") or ""),
                }
            else:
                g[j] = None
        mmdd = str(day.get("date_mmdd") or "")
        titles[gid] = mmdd if mmdd else GROUP_LABELS[gid]
    save_holdings(state)
    return {"ok": True, "meta": meta, "tab_titles": titles}


# --- 数据库概览（只读） ---
def _table_count(table: str) -> int:
    try:
        conn = dbmod.get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(1) FROM {table}")
        n = int(cur.fetchone()[0])
        conn.close()
        return n
    except Exception:
        return -1


@app.get("/api/stats")
def api_stats() -> dict[str, Any]:
    tables = [
        "news_info",
        "stock_data",
        "stock_logic",
        "crawled_articles",
        "kelly_records",
        "lhb_records",
        "ths_realtime_data",
        "trading_system_configs",
    ]
    return {"db_path": dbmod.DB_PATH, "counts": {t: _table_count(t) for t in tables}}


@app.get("/api/stock-logic")
def api_stock_logic(limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    conn = dbmod.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, stock_name, logic, date, source, created_at
        FROM stock_logic
        ORDER BY date DESC, created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    cols = ["id", "stock_name", "logic", "date", "source", "created_at"]
    return {"items": [dict(zip(cols, r)) for r in rows]}


@app.get("/api/kelly-records")
def api_kelly_records(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    conn = dbmod.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes, created_at
        FROM kelly_records
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    cols = [
        "id",
        "stock_name",
        "calc_time",
        "odds",
        "win_prob",
        "kelly_ratio",
        "suggestion",
        "notes",
        "created_at",
    ]
    return {"items": [dict(zip(cols, r)) for r in rows]}


# --- 爬虫任务（本机子进程；仅允许名单内脚本） ---
class RunScriptBody(BaseModel):
    script: str
    timeout_sec: int = 600


@app.post("/api/tasks/run-crawler")
async def run_crawler(body: RunScriptBody) -> dict[str, Any]:
    name = Path(body.script).name
    if name not in ALLOWED_CRAWL_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"script not allowed: {name}")
    script_path = _SRC_DIR / name
    if not script_path.is_file():
        raise HTTPException(status_code=404, detail=f"file missing: {script_path}")

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script_path),
        cwd=str(_SRC_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=max(30, body.timeout_sec)
        )
    except asyncio.TimeoutError:
        proc.kill()
        return {"ok": False, "error": "timeout", "script": name}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "script": name,
        "stdout_tail": (stdout or b"").decode("utf-8", errors="replace")[-4000:],
        "stderr_tail": (stderr or b"").decode("utf-8", errors="replace")[-4000:],
    }


if _STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC), name="assets")


@app.get("/")
async def index_page() -> FileResponse:
    idx = _STATIC / "index.html"
    if not idx.is_file():
        raise HTTPException(status_code=500, detail="static index missing")
    return FileResponse(idx)

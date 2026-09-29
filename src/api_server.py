#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StockAnalyzer API Server —— 供 iOS App 调用的 Flask REST 后端

复用 stockyidong 核心逻辑：
  - utils.config.DB_PATH             数据库路径
  - data.db.init_database()          DB 初始化
  - ui._akshare_fetcher.fetch_index_daily() / fetch_daily_kline()  K线
  - logic.spot.get_realtime_spot_row()                                 实时行情
  - logic.indicators.*                                                 技术指标

数据源优先级：腾讯 qt.gtimg.cn (最快) → akshare → tushare

启动方式：
  cd /Users/faronpan/Agent/stockyidong_project/src
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 api_server.py

端口：默认 5000，可通过环境变量 API_PORT 覆盖
"""
import os
import sys
import time
import json
import sqlite3
import threading
import requests as _http

# ============ sys.path & 模块导入 ============
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from flask import Flask, jsonify, request
from flask_cors import CORS

# 复用项目核心模块
from utils.config import DB_PATH, TS_DEFAULT_TOKEN
from data.db import init_database

# 可选模块（延迟导入避免影响启动）
def _try_import(name, from_path=None):
    try:
        mod = __import__(from_path or name, fromlist=[name]) if from_path else __import__(name)
        return mod
    except Exception:
        return None

# ============ Flask App ============
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

_START_TIME = time.time()


# ======================================================================
# 持仓表（首次启动时创建）
# ======================================================================
_POSITIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    buy_price REAL NOT NULL,
    shares INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, name)
)
"""

def _ensure_positions_table():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_POSITIONS_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


# ======================================================================
# 腾讯实时行情解析（指数 + 个股）
# ======================================================================
# 腾讯行情字段索引（~ 分隔）：
#   [0] 市场类型 (1=sh, 51=sz)
#   [1] 名称  [2] 代码  [3] 昨收  [4] 今开  [5] 当前价
#   [6] 成交量(手)  [31] 涨跌额  [32] 涨跌幅%  [33] 今高  [34] 今低
_TENCENT_FIELDS = {
    "name": 1, "code": 2, "prev_close": 3, "open": 4, "price": 5,
    "volume": 6, "change": 31, "pct": 32, "high": 33, "low": 34,
}


def _tencent_codes_to_tq(codes):
    """代码列表 → 腾讯行情查询串。
    指数如 000001/399001 需加 sh/sz 前缀；
    个股直接 6 位代码，前缀按首位判断。
    """
    out = []
    for c in codes:
        c = c.strip()
        if not c:
            continue
        # 已带前缀（sh/sz/bj）
        if c.startswith(("sh", "sz", "bj")) and len(c) > 2:
            out.append(c)
        else:
            c6 = c[-6:].zfill(6)
            if c6.startswith(("43", "83", "87", "92")):
                out.append(f"bj{c6}")
            elif c6.startswith(("6", "5", "9")):
                out.append(f"sh{c6}")
            else:
                out.append(f"sz{c6}")
    return out


def _parse_tencent_quote(text):
    """解析腾讯行情返回文本 → {code: dict}"""
    result = {}
    if not text:
        return result
    for part in text.strip().split(";"):
        if "=" not in part:
            continue
        key, data = part.split("=", 1)
        items = data.strip('"').split("~")
        # 腾讯返回格式: v_前缀, 如 v_sh000001，注意每行可能带前导 \n
        code = key.strip().replace("v_", "")
        f = _TENCENT_FIELDS
        def _f(idx):
            if idx < len(items):
                v = items[idx].strip()
                try:
                    return float(v) if v else None
                except ValueError:
                    return v or None
            return None
        result[code] = {
            "name": items[f["name"]] if f["name"] < len(items) else "",
            "code": items[f["code"]] if f["code"] < len(items) else "",
            "price": _f(f["price"]),
            "prev_close": _f(f["prev_close"]),
            "open": _f(f["open"]),
            "high": _f(f["high"]),
            "low": _f(f["low"]),
            "volume": _f(f["volume"]),
            "change": _f(f["change"]),
            "pct": _f(f["pct"]),
        }
    return result


# ============ 指数定义 ============
INDEX_LIST = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
]


# ======================================================================
# API 1: 系统状态
# ======================================================================
@app.get("/api/v1/health")
def api_health():
    init_database()
    _ensure_positions_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1").fetchone()
        db_ok = True
        conn.close()
    except Exception:
        db_ok = False
    return jsonify({
        "status": "ok",
        "db": "connected" if db_ok else "disconnected",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    })


# ======================================================================
# API 2: 行情 — 指数实时
# ======================================================================
@app.get("/api/v1/indices")
def api_indices():
    """返回三大指数实时行情（腾讯源）"""
    try:
        tq_codes = [c for c, _ in INDEX_LIST]
        url = f"https://qt.gtimg.cn/q={','.join(tq_codes)}"
        r = _http.get(url,
                      headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com/"},
                      timeout=8)
        if r.status_code != 200:
            return jsonify({"error": f"tencent http {r.status_code}"}), 502

        parsed = _parse_tencent_quote(r.text)
        out = {}
        for tq, cn_name in INDEX_LIST:
            row = parsed.get(tq)
            if row:
                out[tq] = {
                    "name": cn_name,
                    "price": row["price"],
                    "pct": row["pct"],
                    "change": row["change"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "prev_close": row["prev_close"],
                }
            else:
                out[tq] = {"name": cn_name, "error": "no_data"}
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================
# API 3: 行情 — 指数日K线
# ======================================================================
@app.get("/api/v1/indices/<code>/kline")
def api_index_kline(code):
    """指数日K线。code 形如 sh000001"""
    days = int(request.args.get("days", 60))
    try:
        from ui._akshare_fetcher import fetch_index_daily
        df = fetch_index_daily(symbol=code, days=days)
        if df is None or len(df) == 0:
            return jsonify({"error": "no_data"}), 404

        name = next((n for c, n in INDEX_LIST if c == code), code)
        data = []
        for _, row in df.iterrows():
            data.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "open": round(float(row["open"]), 2),
                "close": round(float(row["close"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "volume": int(float(row["volume"])) if row.get("volume") else 0,
                "pct_chg": round(float(row["pct_chg"]), 2) if "pct_chg" in row else None,
            })
        return jsonify({"code": code, "name": name, "data": data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================
# API 4: 行情 — 个股实时（批量）
# ======================================================================
@app.get("/api/v1/stocks/realtime")
def api_stocks_realtime():
    """批量个股实时行情。query: codes=601689,000001"""
    codes_param = request.args.get("codes", "")
    codes = [c.strip() for c in codes_param.split(",") if c.strip()]
    if not codes:
        return jsonify({"error": "codes required"}), 400
    codes = codes[:50]  # 限制单次数量

    try:
        tq_codes = _tencent_codes_to_tq(codes)
        url = f"https://qt.gtimg.cn/q={','.join(tq_codes)}"
        r = _http.get(url,
                      headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com/"},
                      timeout=8)
        if r.status_code != 200:
            return jsonify({"error": f"tencent http {r.status_code}"}), 502
        parsed = _parse_tencent_quote(r.text)
        # 把 sh/sz 前缀 key 映射回原始 6 位代码
        out = {}
        for orig in codes:
            c6 = orig[-6:].zfill(6)
            # 尝试各种带前缀的 key
            hit = None
            for prefix in ("sh", "sz", "bj"):
                key = f"{prefix}{c6}"
                if key in parsed:
                    hit = parsed[key]
                    break
            if hit:
                out[c6] = hit
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================
# API 5: 选股 — 大跌预警（市场广度）
# ======================================================================
@app.get("/api/v1/scan/crash-warning")
def api_scan_crash_warning():
    """市场广度 + 涨跌家数 + 涨停跌停 — 用于判断是否恐慌
    带 10 秒超时保护，超时则返回降级数据
    """
    result_holder = {"data": None}
    done_event = threading.Event()

    def _worker():
        try:
            signals = []
            up = dn = flat = zt = dt = total = None
            try:
                import akshare as ak
                import pandas as pd
                spot = ak.stock_zh_a_spot_em()
                if spot is not None and len(spot) > 0:
                    total = len(spot)
                    up = int((spot["涨跌幅"] > 0).sum())
                    dn = int((spot["涨跌幅"] < 0).sum())
                    flat = total - up - dn
                    zt = int((spot["涨跌幅"] >= 9.5).sum())
                    dt = int((spot["涨跌幅"] <= -9.5).sum())
            except Exception as e_ak:
                print(f"[crash-warning] akshare fail: {e_ak}")

            if total is None:
                result_holder["data"] = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "signals": [{"name": "数据源", "value": "离线", "level": "gray", "desc": "非交易时段或网络不可用"}],
                    "recommendation": "数据暂不可用",
                    "confidence": 0,
                }
                return

            signals.append({
                "name": "涨跌家数", "value": up, "down": dn, "flat": flat, "total": total,
                "level": "red" if up < 800 else ("yellow" if up < 1600 else "green"),
                "desc": "恐慌区" if up < 800 else ("观望区" if up < 1600 else "安全区"),
            })
            signals.append({
                "name": "涨停家数", "value": zt,
                "level": "green" if zt >= 30 else ("yellow" if zt >= 10 else "red"),
                "desc": "市场活跃度" if zt >= 10 else "赚钱效应弱",
            })
            signals.append({
                "name": "跌停家数", "value": dt,
                "level": "red" if dt >= 50 else ("yellow" if dt >= 20 else "green"),
                "desc": "恐慌加剧" if dt >= 20 else "恐慌有限",
            })

            ratio = up / max(dn, 1)
            signals.append({
                "name": "涨跌比", "value": round(ratio, 2),
                "level": "red" if ratio < 0.5 else ("yellow" if ratio < 1.2 else "green"),
                "desc": f"{up}涨 / {dn}跌 / {flat}平",
            })

            score = 0
            if up < 800: score += 2
            elif up < 1600: score += 1
            if dt >= 50: score += 2
            elif dt >= 20: score += 1
            if ratio < 0.5: score += 2
            elif ratio < 1.2: score += 1

            if score >= 5:
                rec, conf = "建议减仓观望，市场恐慌明显", 0.85
            elif score >= 3:
                rec, conf = "谨慎操作，控制仓位", 0.65
            elif score >= 1:
                rec, conf = "市场中性，可正常操作", 0.5
            else:
                rec, conf = "市场情绪良好，可积极操作", 0.7

            result_holder["data"] = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "signals": signals, "recommendation": rec, "confidence": conf,
            }
        except Exception as e:
            print(f"[crash-warning] worker exception: {e}")
        finally:
            done_event.set()

    # 启动线程 + 10 秒超时
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    done_event.wait(timeout=10)

    if result_holder["data"] is not None:
        return jsonify(result_holder["data"])

    # 超时降级
    print("[crash-warning] TIMEOUT → 降级返回")
    return jsonify({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "signals": [{"name": "数据源", "value": "超时", "level": "gray", "desc": "行情接口响应慢，请稍后重试"}],
        "recommendation": "数据暂不可用，请稍后刷新",
        "confidence": 0,
    })


# ======================================================================
# API 6: 选股 — 低位突破 MA20
# ======================================================================
@app.get("/api/v1/scan/low-break20")
def api_scan_low_break20():
    """简单版：拉全市场 spot_em 数据，计算 MA20，筛选现价 > MA20 且距 MA20 不超过 5% 的"""
    limit = int(request.args.get("limit", 30))
    try:
        import akshare as ak
        import pandas as pd
        spot = ak.stock_zh_a_spot_em()
        if spot is None or len(spot) == 0:
            return jsonify({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "stocks": []})

        # 取前 2000 只（过滤 ST + 成交额 > 5000w）
        spot = spot[~spot["名称"].str.contains("ST", na=False)]
        if "成交额" in spot.columns:
            spot = spot[pd.to_numeric(spot["成交额"], errors="coerce") > 5e7]

        results = []
        # 最多计算 300 只
        for _, row in spot.head(300).iterrows():
            try:
                code = str(row.get("代码", ""))[-6:]
                name = str(row.get("名称", ""))
                price = float(row.get("最新价", 0))
                pct = float(row.get("涨跌幅", 0))
                if price <= 0:
                    continue

                # 计算 MA20（用 akshare 历史数据）
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                    if hist is None or len(hist) < 20:
                        continue
                    closes = pd.to_numeric(hist["收盘"], errors="coerce").dropna()
                    ma20 = float(closes.tail(20).mean())
                    if ma20 <= 0:
                        continue
                    # 条件：现价 > MA20 且距 MA20 不超过 5%
                    above_ma20 = price > ma20
                    dist_pct = (price - ma20) / ma20 * 100
                    if above_ma20 and dist_pct <= 5.0:
                        results.append({
                            "code": code,
                            "name": name,
                            "price": round(price, 2),
                            "pct": round(pct, 2),
                            "ma20": round(ma20, 2),
                            "above_ma20": above_ma20,
                            "distance_pct": round(dist_pct, 2),
                            "signal_score": round(70 + (5 - dist_pct) * 4, 1),
                        })
                except Exception:
                    continue
            except Exception:
                continue

        # 按距 MA20 距离升序（刚突破的排前面），取 top N
        results.sort(key=lambda x: x["distance_pct"])
        results = results[:limit]

        return jsonify({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": results,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================
# API 7: 选股 — 带血筹码（距 60 日低点 ≤ 5%）
# ======================================================================
@app.get("/api/v1/scan/blood-chips")
def api_scan_blood_chips():
    """全市场基本面 OK + 距 60 日低点 ≤ 5% 的错杀股"""
    limit = int(request.args.get("limit", 30))
    try:
        import akshare as ak
        import pandas as pd
        spot = ak.stock_zh_a_spot_em()
        if spot is None or len(spot) == 0:
            return jsonify({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "stocks": []})

        # 过滤 ST + 换手率正常
        spot = spot[~spot["名称"].str.contains("ST", na=False)]
        results = []
        scanned = 0

        for _, row in spot.head(500).iterrows():
            scanned += 1
            try:
                code = str(row.get("代码", ""))[-6:]
                name = str(row.get("名称", ""))
                price = float(row.get("最新价", 0))
                pct = float(row.get("涨跌幅", 0))
                if price <= 0:
                    continue

                # 拉历史数据计算 60 日低点
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                    if hist is None or len(hist) < 60:
                        continue
                    closes = pd.to_numeric(hist["收盘"], errors="coerce").dropna()
                    low_60 = float(closes.tail(60).min())
                    if low_60 <= 0:
                        continue
                    dist_to_low = (price - low_60) / low_60 * 100
                    if dist_to_low <= 5.0:
                        # 闪崩型：7 天前的价格比现在高 ≥ 6%
                        close_7d_ago = float(closes.iloc[-7]) if len(closes) >= 7 else price
                        gap_pct = (price - close_7d_ago) / close_7d_ago * 100
                        results.append({
                            "code": code,
                            "name": name,
                            "price": round(price, 2),
                            "pct": round(pct, 2),
                            "gap_pct": round(gap_pct, 2),
                            "low_60d": round(low_60, 2),
                            "dist_to_low_pct": round(dist_to_low, 2),
                            "type": "闪崩型" if gap_pct < -6 else "低位震荡",
                        })
                except Exception:
                    continue
            except Exception:
                continue

        results.sort(key=lambda x: x["dist_to_low_pct"])
        results = results[:limit]

        return jsonify({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": results,
            "scanned_count": scanned,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================
# API 8: 持仓 CRUD
# ======================================================================
@app.get("/api/v1/positions")
def api_get_positions():
    """获取所有持仓 + 关联实时行情"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM positions ORDER BY id DESC").fetchall()
        conn.close()

        positions = [dict(r) for r in rows]
        # 批量获取实时行情
        if positions:
            codes = [p["code"] for p in positions]
            try:
                tq_codes = _tencent_codes_to_tq(codes)
                url = f"https://qt.gtimg.cn/q={','.join(tq_codes)}"
                r = _http.get(url,
                              headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com/"},
                              timeout=8)
                if r.status_code == 200:
                    parsed = _parse_tencent_quote(r.text)
                    for p in positions:
                        c6 = p["code"][-6:].zfill(6)
                        hit = None
                        for prefix in ("sh", "sz", "bj"):
                            key = f"{prefix}{c6}"
                            if key in parsed:
                                hit = parsed[key]
                                break
                        if hit:
                            cur = hit["price"]
                            p["current_price"] = cur
                            p["profit"] = round((cur - p["buy_price"]) * p["shares"], 2)
                            p["profit_pct"] = round((cur - p["buy_price"]) / p["buy_price"] * 100, 2) if p["buy_price"] else 0
                            p["name"] = p.get("name") or hit["name"]
            except Exception as e:
                print(f"[positions] realtime fail: {e}")

        return jsonify({"positions": positions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/v1/positions")
def api_add_position():
    """新增持仓
    body: {"code":"601689","name":"拓普集团","buy_price":52.30,"shares":1000}
    """
    try:
        data = request.get_json() or {}
        code = (data.get("code") or "").strip()[-6:].zfill(6)
        name = (data.get("name") or "").strip()
        buy_price = float(data.get("buy_price") or 0)
        shares = int(data.get("shares") or 0)
        if not code or not name or buy_price <= 0 or shares <= 0:
            return jsonify({"error": "invalid params: code/name/buy_price/shares required"}), 400

        conn = sqlite3.connect(DB_PATH)
        try:
            # 已存在则更新
            exist = conn.execute("SELECT id FROM positions WHERE code=?", (code,)).fetchone()
            if exist:
                conn.execute("UPDATE positions SET name=?, buy_price=?, shares=? WHERE id=?",
                             (name, buy_price, shares, exist[0]))
                pid = exist[0]
            else:
                cur = conn.execute(
                    "INSERT INTO positions (code, name, buy_price, shares) VALUES (?, ?, ?, ?)",
                    (code, name, buy_price, shares))
                pid = cur.lastrowid
            conn.commit()
            return jsonify({"id": pid, "success": True})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.put("/api/v1/positions/<int:pid>")
def api_update_position(pid):
    """更新持仓"""
    try:
        data = request.get_json() or {}
        conn = sqlite3.connect(DB_PATH)
        try:
            updates = []
            params = []
            for field in ("name", "buy_price", "shares"):
                if field in data:
                    updates.append(f"{field}=?")
                    v = data[field]
                    if field == "shares":
                        v = int(v)
                    elif field == "buy_price":
                        v = float(v)
                    params.append(v)
            if not updates:
                return jsonify({"error": "no fields to update"}), 400
            params.append(pid)
            conn.execute(f"UPDATE positions SET {','.join(updates)} WHERE id=?", params)
            conn.commit()
            return jsonify({"success": True})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.delete("/api/v1/positions/<int:pid>")
def api_delete_position(pid):
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM positions WHERE id=?", (pid,))
            conn.commit()
            return jsonify({"success": True})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================================
# 启动
# ======================================================================
def main():
    init_database()
    _ensure_positions_table()
    port = int(os.environ.get("API_PORT", 5000))
    host = os.environ.get("API_HOST", "0.0.0.0")
    print("=" * 60)
    print(f"  StockAnalyzer API Server 启动")
    print(f"  监听地址: http://{host}:{port}")
    print(f"  健康检查: http://{host}:{port}/api/v1/health")
    print(f"  大盘指数: http://{host}:{port}/api/v1/indices")
    print(f"  数据库:   {DB_PATH}")
    print("=" * 60)
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

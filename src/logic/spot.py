# 迁移自 stockyidong mac003.py ranges=[(1833, 1835), (1837, 1837), (1839, 1839), (1840, 1842), (1843, 1854), (1855, 1861), (1862, 1869), (1870, 1885), (1886, 1901), (1902, 1948), (1949, 1971), (1972, 2015)]
import os
import sys
import time
import threading
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

_stock_data_cache = {}
_cache_timestamp = {}
_spot_snapshot_cache = {'timestamp': 0, 'data': None}

_spot_market_cache = {}

_AKSHARE_LOCK_TO_TUSHARE = False

def _should_skip_akshare():
    """当 AKShare 已失败且 Tushare 可用时,后续跳过 AKShare。"""
    return bool(_AKSHARE_LOCK_TO_TUSHARE and TS_AVAILABLE and (TS_DEFAULT_TOKEN or "").strip())

def _mark_akshare_failed(reason=""):
    """记录 AKShare 部分接口失败,后续相关路径优先锁定为 Tushare 兜底。
    注意: 不全局禁用 AKSHARE_AVAILABLE —— 实时新闻/红绿灯等仍需 akshare。"""
    global _AKSHARE_LOCK_TO_TUSHARE
    if _AKSHARE_LOCK_TO_TUSHARE:
        return
    if TS_AVAILABLE and (TS_DEFAULT_TOKEN or "").strip():
        _AKSHARE_LOCK_TO_TUSHARE = True
        if reason:
            print(f"AKShare部分接口失败,后续相关路径切换为Tushare兜底: {reason}")
        else:
            print("AKShare部分接口失败,后续相关路径切换为Tushare兜底")

def _normalize_a_share_code6(stock_code):
    if stock_code is None:
        return ""
    digits = re.sub(r'\D', '', str(stock_code))
    if not digits:
        return ""
    return digits[-6:].zfill(6)

def _format_ts_code_for_spot(code6):
    """A 股代码 -> Tushare ts_code(与 StockKeywordAnalyzerGUI._format_ts_code 一致)"""
    if not code6:
        return ""
    c = code6.zfill(6)
    if c.startswith(("5", "6", "9")):
        return f"{c}.SH"
    return f"{c}.SZ"

def _spot_market_key_and_fetcher(code6):
    """返回 (cache_key, 无参可调用接口)。按所沪深/科创/创业板/北交所拉全量,单行查询更可靠。"""
    if not AKSHARE_AVAILABLE or _should_skip_akshare():
        return "em", None
    c = (code6 or "").zfill(6)
    if c.startswith("68"):
        return "kc", ak.stock_kc_a_spot_em
    if c.startswith("30"):
        return "cy", ak.stock_cy_a_spot_em
    if c.startswith(("43", "83", "87", "92")):
        return "bj", ak.stock_bj_a_spot_em
    if c.startswith("6"):
        return "sh", ak.stock_sh_a_spot_em
    if c.startswith(("0", "3")):
        return "sz", ak.stock_sz_a_spot_em
    return "em", ak.stock_zh_a_spot_em

def _row_from_ak_spot_df(spot_df, code6):
    if spot_df is None or getattr(spot_df, "empty", True):
        return None
    code_col = None
    for cand in ("代码", "code", "股票代码"):
        if cand in spot_df.columns:
            code_col = cand
            break
    if not code_col:
        return None
    want = (code6 or "").zfill(6)
    ser = spot_df[code_col].astype(str).str.replace(r"\D", "", regex=True).str[-6:].str.zfill(6)
    row = spot_df[ser == want]
    if row.empty:
        return None
    return row.iloc[0]

def _spot_row_from_tushare(code6):
    """Tushare:实时价(若有)+ 最近日线收盘价算涨跌幅,不依赖东财全表。"""
    if not TS_AVAILABLE:
        return None
    tok = (TS_DEFAULT_TOKEN or "").strip()
    if not tok:
        return None
    c6 = (code6 or "").zfill(6)
    ts_code = _format_ts_code_for_spot(c6)
    if not ts_code:
        return None
    try:
        import os

        import tushare as ts
        os.environ["TUSHARE_TOKEN"] = tok
        pro = ts.pro_api()
        price = None
        try:
            dfq = ts.realtime_quote(ts_code=ts_code, src="dc")
            if dfq is not None and not dfq.empty and "price" in dfq.columns:
                pv = dfq.iloc[0]["price"]
                if pd.notna(pv):
                    price = float(pv)
        except Exception:
            pass
        dfd = pro.daily(ts_code=ts_code, limit=5)
        if dfd is None or dfd.empty:
            return None
        dfd = dfd.sort_values("trade_date", ascending=True)
        last_close = float(dfd.iloc[-1]["close"])
        prev_close = float(dfd.iloc[-2]["close"]) if len(dfd) > 1 else last_close
        use_px = price if price and 0.01 < price < 50000 else last_close
        pct = (use_px - prev_close) / prev_close * 100 if prev_close else 0.0
        return pd.Series(
            {
                "代码": c6,
                "最新价": use_px,
                "昨收": prev_close,
                "涨跌幅": round(pct, 2),
                "最高": use_px,
                "最低": use_px,
            }
        )
    except Exception as e_v:
        print(f"Tushare 取涨跌幅/行情失败 {c6}: {e_v}")
        return None

def _spot_row_from_akshare_market(code6, cache_duration):
    import time
    global _spot_market_cache
    if not AKSHARE_AVAILABLE or _should_skip_akshare():
        return None
    mkey, fetcher = _spot_market_key_and_fetcher(code6)
    if fetcher is None:
        return None
    now = time.time()
    ent = _spot_market_cache.get(mkey) or {}
    last_ts = ent.get("timestamp", 0)
    df = ent.get("data")
    if last_ts == 0 or (now - last_ts) > cache_duration:
        try:
            df = fetcher()
        except Exception as e_m:
            print(f"AKShare {mkey} 行情接口失败: {e_m}")
            _mark_akshare_failed(str(e_m))
            df = None
        _spot_market_cache[mkey] = {"timestamp": now, "data": df}
    if df is None:
        return None
    return _row_from_ak_spot_df(df, code6)

def get_realtime_spot_row(stock_code, cache_duration=120):
    """获取实时行情一行(Series):优先 Tushare(日线+实时价),再东财分市场,最后东财全表快照。
    说明:stock_zh_a_spot_em() 在部分版本/时段只返回少量股票,仅用该表会导致多数代码「拿不到涨跌幅」。
    """
    import time
    code6 = _normalize_a_share_code6(stock_code)
    if not code6:
        return None
    try:
        tr = _spot_row_from_tushare(code6)
        if tr is not None:
            return tr
    except Exception as e_t:
        print(f"Tushare 行情链路异常 {code6}: {e_t}")
    try:
        mr = _spot_row_from_akshare_market(code6, cache_duration)
        if mr is not None:
            return mr
    except Exception as e_m:
        print(f"AKShare 分市场行情异常 {code6}: {e_m}")
    if _should_skip_akshare():
        return None
    try:
        global _spot_snapshot_cache
        now = time.time()
        last_ts = _spot_snapshot_cache.get("timestamp", 0)
        spot_df = _spot_snapshot_cache.get("data")
        if last_ts == 0 or (now - last_ts) > cache_duration:
            spot_df = ak.stock_zh_a_spot_em()
            _spot_snapshot_cache["data"] = spot_df
            _spot_snapshot_cache["timestamp"] = now
        if spot_df is None or spot_df.empty:
            return None
        row = _row_from_ak_spot_df(spot_df, code6)
        return row
    except Exception as e:
        _mark_akshare_failed(str(e))
        try:
            _spot_snapshot_cache["data"] = None
            _spot_snapshot_cache["timestamp"] = time.time()
        except Exception:
            pass
        print(f"获取实时行情失败: {e}")
        return None

__all__ = ['_format_ts_code_for_spot', '_mark_akshare_failed', '_normalize_a_share_code6', '_row_from_ak_spot_df', '_should_skip_akshare', '_spot_market_key_and_fetcher', '_spot_row_from_akshare_market', '_spot_row_from_tushare', 'get_realtime_spot_row']

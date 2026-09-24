# -*- coding: utf-8 -*-
from datetime import datetime
import pandas as pd
"""
公共 akshare 数据获取工具 (优先于 tushare)

为什么需要这个文件?
  Tushare daily/daily_basic 在本机器因积分不足 + 限频被熔断后,
  所有调用点都会抛异常导致功能白屏。本模块提供:
    1. akshare 优先的日K拉取 (新浪 stock_zh_a_daily + 直连兜底)
    2. 实时 PE/市值/换手率 (东财 spot_em, 网络封则返回 None)
    3. 统一的 code6 → market prefix 转换

被以下模块使用:
  - tab_math.py (_hm_calc_for_stock 游资心法)
  - tab_stock_detail.py (_get_daily_kline_data 日K线图)
  - tab_cangwei.py / tab_hot.py (盘中行情 fallback)
  - stockyidong mac003.py / mac.py (_ts_patch_pro_api 熔断后自动切 akshare)
"""

import pandas as pd
import json
import time


def _code6_to_sina(code6: str) -> str:
    """纯6位 → 新浪前缀 sh/sz/bj"""
    c = str(code6).strip()
    if c.startswith(("43", "83", "87", "92")):
        return "bj" + c
    elif c.startswith(("6", "5", "9")):
        return "sh" + c
    else:
        return "sz" + c


def _code6_to_ts(code6: str) -> str:
    """纯6位 → tushare ts_code"""
    c = str(code6).strip()
    if c.startswith(("43", "83", "87", "92")):
        return c + ".BJ"
    elif c.startswith(("6", "5", "9")):
        return c + ".SH"
    else:
        return c + ".SZ"


def fetch_daily_kline(code6: str, days: int = 250, adjust: str = "qfq") -> pd.DataFrame | None:
    """
    拉日K线 (前复权, 默认250根) — 五级降级
    当前机器实测可用源: 同花顺 > 新浪 (间歇性反爬) > 腾讯 (限频) > 东财 (网络封)
    返回 DataFrame 列: date, open, high, low, close, volume
    失败返回 None
    """
    code6 = str(code6).strip()

    # ==== 方案1: akshare 新浪 stock_zh_a_daily (最稳, 偶发反爬) ====
    try:
        import akshare as ak
        sym = _code6_to_sina(code6)
        df = ak.stock_zh_a_daily(symbol=sym, adjust=adjust)
        if df is not None and len(df) > 0:
            df = df.rename(columns={"vol": "volume"})
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.sort_values("date").tail(days).reset_index(drop=True)
            if len(df) >= 30:
                return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        pass

    # ==== 方案2: 新浪直连 JSON (akshare 解析 bug 时兜底) ====
    try:
        import requests
        sym = _code6_to_sina(code6)
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {"symbol": sym, "scale": "240", "ma": "no", "datalen": str(days)}
        r = requests.get(url, params=params, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"})
        if r.status_code == 200 and r.text.startswith("["):
            data = json.loads(r.text)
            df = pd.DataFrame(data).rename(columns={"day": "date"})
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").tail(days).reset_index(drop=True)
            if len(df) >= 30:
                return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        pass

    # ==== 方案3: akshare 腾讯 (stock_zh_a_hist_tx, 限频冷却后可用) ====
    try:
        import akshare as ak
        prefix = "sh" if code6.startswith(("6", "5", "9")) else "sz"
        for sym in [prefix + code6, code6]:
            try:
                df = ak.stock_zh_a_hist_tx(symbol=sym, adjust=adjust,
                                           start_date="20240101", end_date="20991231")
                if df is not None and len(df) > 0:
                    df = df.rename(columns={"close": "close_raw"})
                    df = df.rename(columns={"date": "date", "open": "open",
                                            "high": "high", "low": "low",
                                            "close_raw": "close", "amount": "amount"})
                    df["volume"] = df["amount"].astype(float) / df["close"].astype(float)
                    for c in ["open", "high", "low", "close", "volume"]:
                        df[c] = pd.to_numeric(df[c], errors="coerce")
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").tail(days).reset_index(drop=True)
                    if len(df) >= 30:
                        return df[["date", "open", "high", "low", "close", "volume"]]
            except Exception:
                continue
    except Exception:
        pass

    # ==== 方案4: akshare 东方财富 (stock_zh_a_hist, 被网络封时失败) ====
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol=code6, period="daily", adjust=adjust,
                                start_date="20240101", end_date="20991231")
        if df is not None and len(df) > 0:
            df = df.rename(columns={"日期": "date", "开盘": "open", "最高": "high",
                                    "最低": "low", "收盘": "close", "成交量": "volume"})
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").tail(days).reset_index(drop=True)
            if len(df) >= 30:
                return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        pass

    # ==== 方案5: 同花顺直连 (终极兜底, 当前机器实测最稳定) ====
    try:
        import requests
        ths_prefix = "hs" if code6.startswith(("6", "5", "9")) else ("sz" if not code6.startswith(("43", "83", "87", "92")) else "bj")
        ths_url = f"https://d.10jqka.com.cn/v6/line/{ths_prefix}{code6}/01/last{days + 30}.js"
        r = requests.get(ths_url, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://stockpage.10jqka.com.cn/"})
        if r.status_code == 200 and "(" in r.text and "data" in r.text:
            p = r.text.index("(") + 1
            data = json.loads(r.text[p:r.text.rindex(")")])
            if "data" in data and data["data"]:
                rows = []
                for line in data["data"].strip().split(";"):
                    parts = line.split(",")
                    if len(parts) >= 7:
                        rows.append({
                            "date": parts[0], "open": float(parts[1]),
                            "high": float(parts[2]), "low": float(parts[3]),
                            "close": float(parts[4]), "volume": float(parts[5]),
                        })
                if rows:
                    df = pd.DataFrame(rows)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").tail(days).reset_index(drop=True)
                    if len(df) >= 30:
                        return df[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        pass

    # ==== 都失败 ====
    return None


def fetch_realtime_basic(code6: str) -> dict:
    """
    实时基本面快照 (PE/市值/换手率)
    返回 dict: {"pe": float|None, "mv": float|None, "tr": float|None}
    东财网络封时全部返回 None
    """
    result = {"pe": None, "mv": None, "tr": None}
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == code6]
        if len(row):
            r = row.iloc[0]
            # 字段名随 akshare 版本可能变化, 逐个尝试
            for key in ["市盈率-动态", "市盈率"]:
                v = r.get(key)
                if v is not None and str(v) not in ("nan", "", "-"):
                    try: result["pe"] = float(v); break
                    except: pass
            for key in ["总市值", "总市值(亿)"]:
                v = r.get(key)
                if v is not None and str(v) not in ("nan", "", "-"):
                    try:
                        fv = float(v)
                        result["mv"] = fv * 1e8 if fv < 1e5 else fv  # 亿→元
                        break
                    except: pass
            for key in ["换手率-今", "换手率"]:
                v = r.get(key)
                if v is not None and str(v) not in ("nan", "", "-"):
                    try: result["tr"] = float(v); break
                    except: pass
    except Exception:
        pass
    return result


def fetch_index_daily(symbol: str = "sh000001", days: int = 30) -> pd.DataFrame | None:
    """
    拉指数日线 (上证指数/深证成指等)
    symbol: "sh000001" (上证), "sz399001" (深证成指), "sz399006" (创业板)
    返回 DataFrame 列: date, open, high, low, close, volume, pct_chg

    降级链 (按最新日期比谁更新):
      方案1: akshare stock_zh_index_daily
      方案2: 腾讯 web.ifzq.gtimg.cn 指数直连 (实测数据最新)
      方案3: tushare index_daily (熔断风险)

    策略: 先同时拉 akshare + 腾讯, 选最新日期更靠后的那个.
          如果一个失败就用另一个.
    """
    # 归一化 symbol → 腾讯用 sh/sz 前缀
    code = symbol.replace("sh","").replace("sz","").replace("bj","")
    prefix = "sh" if symbol.startswith("sh") else ("sz" if symbol.startswith("sz") else "bj")

    _today = pd.Timestamp(datetime.now().date())

    # ======== 同时拉 akshare + 腾讯, 比谁更新 ========
    ak_df = None
    tencent_df = None

    # akshare
    try:
        import akshare as ak
        _df = ak.stock_zh_index_daily(symbol=symbol)
        if _df is not None and len(_df) > 0:
            ak_df = _df.copy()
            ak_df["date"] = pd.to_datetime(ak_df["date"])
    except Exception:
        pass

    # 腾讯
    try:
        import requests as _req_gt
        _url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{days+5},qfq"
        _r = _req_gt.get(_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        if _r.status_code == 200:
            _j = _r.json()
            _arr = _j["data"][f"{prefix}{code}"].get("day") or _j["data"][f"{prefix}{code}"].get("qfqday")
            if _arr and len(_arr) > 0:
                _rows = []
                for _row in _arr:
                    _rows.append({
                        "date": _row[0],
                        "open": float(_row[1]),
                        "close": float(_row[2]),
                        "high": float(_row[3]),
                        "low": float(_row[4]),
                        "volume": float(_row[5]) if len(_row) > 5 else 0,
                    })
                tencent_df = pd.DataFrame(_rows)
                tencent_df["date"] = pd.to_datetime(tencent_df["date"])
    except Exception:
        pass

    # 比谁的最新日期更靠后
    ak_latest = ak_df["date"].max() if ak_df is not None else pd.Timestamp.min
    tc_latest = tencent_df["date"].max() if tencent_df is not None else pd.Timestamp.min

    if tencent_df is not None and tc_latest >= ak_latest:
        # 腾讯更新 或 腾讯可用而 akshare 空
        df = tencent_df
        source = "腾讯"
    elif ak_df is not None:
        df = ak_df
        source = "akshare"
    else:
        df = None
        source = "无"

    print(f"[fetch_index] akshare最新={ak_latest.date() if ak_latest != pd.Timestamp.min else '无'}, "
          f"腾讯最新={tc_latest.date() if tc_latest != pd.Timestamp.min else '无'}, "
          f"选={source}", flush=True)

    if df is not None and len(df) > 0:
        df = _postprocess_index(df, days)
        if df is not None:
            return df

    # ======== 最后兜底: tushare ========
    try:
        import tushare as _ts_idx
        _ts_code = f"{prefix}{code}.SH" if prefix == "sh" else f"{prefix}{code}.SZ"
        _pro = _ts_idx.pro_api()
        _ts_df = _pro.index_daily(ts_code=_ts_code)
        if _ts_df is not None and len(_ts_df) > 0:
            _ts_df = _ts_df.rename(columns={"trade_date":"date", "vol":"volume"})
            _ts_df["date"] = pd.to_datetime(_ts_df["date"])
            _ts_df = _ts_df.sort_values("date").tail(days).reset_index(drop=True)
            _ts_df["pct_chg"] = _ts_df["close"].pct_change() * 100
            _ts_df = _ts_df.dropna(subset=["pct_chg"]).reset_index(drop=True)
            if len(_ts_df) > 0:
                return _ts_df[["date", "open", "high", "low", "close", "volume", "pct_chg"]]
    except Exception:
        pass

    return None


def _postprocess_index(df: pd.DataFrame, days: int) -> pd.DataFrame | None:
    """统一后处理: 排序、截断、pct_change、dropna"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").tail(days).reset_index(drop=True)
    df["pct_chg"] = df["close"].pct_change() * 100
    df = df.dropna(subset=["pct_chg"]).reset_index(drop=True)
    return df[["date", "open", "high", "low", "close", "volume", "pct_chg"]]


def fetch_daily_full_via_akshare(code6: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """
    模拟 tushare pro.daily() 接口签名, 供熔断后偷偷替换使用
    返回列 (与 tushare daily 对齐): trade_date, open, high, low, close, vol, amount, pct_chg
    start_date/end_date 格式: YYYYMMDD
    """
    from datetime import datetime as _dt
    df = fetch_daily_kline(code6, days=400)
    if df is None or len(df) == 0:
        return None
    # 统一 date 为 datetime 再过滤
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    start = _dt.strptime(start_date, "%Y%m%d")
    end = _dt.strptime(end_date, "%Y%m%d")
    df = df[(df["date"] >= start) & (df["date"] <= end)]
    if len(df) == 0:
        return None
    df = df.rename(columns={"date": "trade_date", "volume": "vol"})
    df["trade_date"] = df["trade_date"].dt.strftime("%Y%m%d")
    df["pct_chg"] = df["close"].pct_change() * 100
    return df.reset_index(drop=True)

# -*- coding: utf-8 -*-
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
    当前机器: akshare stock_zh_index_daily 稳定可用 (5/5 成功)
    """
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or len(df) == 0:
            return None
        df = df.copy()
        # date 可能是 datetime.date, 统一转 datetime 再格式化
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").tail(days).reset_index(drop=True)
        df["pct_chg"] = df["close"].pct_change() * 100
        # 去掉 pct_change() 第一行 NaN, 避免下游 Canvas 崩
        df = df.dropna(subset=["pct_chg"]).reset_index(drop=True)
        return df[["date", "open", "high", "low", "close", "volume", "pct_chg"]]
    except Exception:
        return None


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

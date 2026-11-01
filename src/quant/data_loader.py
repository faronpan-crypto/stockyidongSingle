"""统一数据加载器 — tushare 优先，akshare 后备"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

TS_CODE_MAP = {"上证指数": "000001.SH", "深证成指": "399001.SZ", "创业板指": "399006.SZ"}


def get_tushare():
    """获取 tushare pro 实例"""
    import tushare as ts
    from utils.config import TS_DEFAULT_TOKEN
    token = os.environ.get("TUSHARE_TOKEN", "") or TS_DEFAULT_TOKEN
    if not token:
        raise RuntimeError("TUSHARE_TOKEN 未配置")
    ts.set_token(token)
    return ts.pro_api()


def get_index_hist(target="上证指数", start_date=None, end_date=None, days_back=3650):
    """获取指数历史日线数据

    Args:
        target: '上证指数' / '深证成指' / '创业板指'
        start_date: 'YYYYMMDD' 或 None (= days_back 天前)
        end_date: 'YYYYMMDD' 或 None (= 最近交易日)
        days_back: start_date 为空时的默认回溯天数

    Returns:
        DataFrame: [trade_date, open, high, low, close, vol, amount, pct_chg]
    """
    code = TS_CODE_MAP.get(target, target)
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

    pro = get_tushare()
    df = pro.index_daily(ts_code=code, start_date=start_date, end_date=end_date)
    if df is None or len(df) == 0:
        return pd.DataFrame()
    df = df.sort_values("trade_date").reset_index(drop=True)
    return df


def get_trade_date(target_date=None):
    """找最近交易日"""
    if target_date is None:
        target_date = datetime.now().strftime("%Y%m%d")
    pro = get_tushare()
    cal_start = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=14)).strftime("%Y%m%d")
    cal = pro.trade_cal(exchange="SSE", start_date=cal_start, end_date=target_date)
    if cal is None or len(cal) == 0:
        return target_date
    open_days = cal[cal["is_open"] == 1]["cal_date"]
    if len(open_days) == 0:
        return target_date
    return str(open_days.sort_values().iloc[-1])


def get_breadth(trade_date):
    """获取当日市场宽广度

    Returns:
        dict: {up, dn, flat, red_pct, limit_up, limit_dn, up_amt, dn_amt, trin}
    """
    pro = get_tushare()
    basic = pro.daily_basic(trade_date=trade_date, fields="ts_code")
    daily = pro.daily(trade_date=trade_date, fields="ts_code,pct_chg,amount")
    if basic is None or daily is None or len(basic) == 0 or len(daily) == 0:
        return {"error": "daily_basic/daily 返回空"}
    df = basic.merge(daily, on="ts_code", how="inner")
    up = len(df[df["pct_chg"] > 0])
    dn = len(df[df["pct_chg"] < 0])
    flat = len(df) - up - dn
    up_amt = df[df["pct_chg"] > 0]["amount"].sum()
    dn_amt = df[df["pct_chg"] < 0]["amount"].sum()
    trin = ((up / max(dn, 1)) / (up_amt / max(dn_amt, 1))) if dn > 0 and dn_amt > 0 else 1.0
    return {
        "total": len(df), "up": up, "dn": dn, "flat": flat,
        "red_pct": up / max(up + dn + flat, 1) * 100,
        "limit_up": len(df[df["pct_chg"] >= 9.5]),
        "limit_dn": len(df[df["pct_chg"] <= -9.5]),
        "trin": trin,
        "trin_label": ("强" if trin < 0.7 else ("中性" if trin < 1.3 else "弱")),
    }

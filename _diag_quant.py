#!/usr/bin/env python3
"""量化预测诊断脚本 — 独立测试 scan 逻辑"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 先导入模块级函数
import numpy as np
def _ema(arr, n):
    arr = np.array(arr, dtype=float)
    k = 2.0 / (n + 1)
    result = np.empty_like(arr); result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = arr[i] * k + result[i-1] * (1 - k)
    return result

def _rsi(arr, n=14):
    arr = np.array(arr, dtype=float)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0); losses = np.where(deltas < 0, -deltas, 0)
    if len(gains) < n: return 50.0
    avg_gain = np.mean(gains[:n]); avg_loss = np.mean(losses[:n])
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
    rs = avg_gain / max(avg_loss, 1e-10)
    return 100 - 100 / (1 + rs)

from src.utils.config import TS_DEFAULT_TOKEN
_token = os.environ.get("TUSHARE_TOKEN","") or TS_DEFAULT_TOKEN
print(f"🔑 Token: {'已找到' if _token else '缺失!'}")

import tushare as ts
os.environ["TUSHARE_TOKEN"] = _token
ts.set_token(_token)
pro = ts.pro_api()

from datetime import datetime, timedelta

print("\n" + "="*60)
print("📅 Step 1: 获取交易日")
print("="*60)
_today = datetime.now().strftime("%Y%m%d")
print(f"  今天: {_today}")
_cal_start = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")
_cal = pro.trade_cal(exchange="SSE", start_date=_cal_start, end_date=_today)
if _cal is not None and len(_cal) > 0:
    _open = _cal[_cal["is_open"]==1]["cal_date"]
    if len(_open) > 0:
        trade_date = str(_open.sort_values().iloc[-1])
        print(f"  最近交易日: {trade_date}")

print("\n" + "="*60)
print("📈 Step 2: 获取指数数据")
print("="*60)
_index_map = {"000001.SH":"上证指数","399001.SZ":"深证成指","399006.SZ":"创业板指"}
for code, name in _index_map.items():
    print(f"\n  --- {name} ({code}) ---")
    try:
        hist = pro.index_daily(ts_code=code, 
            start_date=(datetime.now()-timedelta(days=500)).strftime("%Y%m%d"), 
            end_date=trade_date)
        if hist is None:
            print(f"  ❌ 返回 None")
            continue
        print(f"  ✅ 行数: {len(hist)}")
        if len(hist) >= 5:
            hist = hist.sort_values("trade_date")
            print(f"  日期范围: {hist['trade_date'].iloc[0]} ~ {hist['trade_date'].iloc[-1]}")
            closes = hist["close"].astype(float).values
            ma20 = float(np.mean(closes[-20:])) if len(closes)>=20 else None
            ma60 = float(np.mean(closes[-60:])) if len(closes)>=60 else None
            ma250 = float(np.mean(closes[-250:])) if len(closes)>=250 else None
            close_now = float(closes[-1])
            print(f"  收盘={close_now:.2f}  MA20={ma20}  MA60={ma60}  MA250={ma250}")
            if ma20: print(f"  偏离MA20: {(close_now-ma20)/ma20*100:.2f}%")
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        import traceback; traceback.print_exc()

print("\n" + "="*60)
print("📊 Step 3: Breadth (daily_basic + daily)")
print("="*60)
try:
    _basic = pro.daily_basic(trade_date=trade_date, fields="ts_code,turnover_rate,volume_ratio")
    _daily = pro.daily(trade_date=trade_date, fields="ts_code,pct_chg,amount,vol")
    print(f"  daily_basic: {'None' if _basic is None else len(_basic)} rows")
    print(f"  daily: {'None' if _daily is None else len(_daily)} rows")
    if _basic is not None and _daily is not None and len(_basic)>0 and len(_daily)>0:
        _df = _basic.merge(_daily, on="ts_code", how="inner")
        print(f"  merge 后: {len(_df)} rows")
        up = len(_df[_df["pct_chg"]>0])
        dn = len(_df[_df["pct_chg"]<0])
        print(f"  上涨={up}  下跌={dn}  红盘率={up/max(up+dn,1)*100:.1f}%")
        limit_up = len(_df[_df["pct_chg"]>=9.5])
        limit_dn = len(_df[_df["pct_chg"]<=-9.5])
        print(f"  涨停={limit_up}  跌停={limit_dn}")
        up_amt = _df[_df["pct_chg"]>0]["amount"].sum()
        dn_amt = _df[_df["pct_chg"]<0]["amount"].sum()
        trin = ((up/max(dn,1))/(up_amt/max(dn_amt,1))) if dn>0 and dn_amt>0 else 1.0
        print(f"  TRIN={trin:.3f}")
except Exception as e:
    print(f"  ❌ Breadth 异常: {e}")
    import traceback; traceback.print_exc()

print("\n" + "="*60)
print("✅ 诊断完成")
print("="*60)

#!/usr/bin/env python3
"""解析 yidong 持仓清单 + 并行拉取每只今日日线(涨跌幅/量能/市值)，落盘 CSV。"""
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

EXPORT = "/Users/faronpan/Agent/stockyidong_project/src/stockyidong_20260828_144514.txt"
OUT = "/tmp/holdings_chg_20260828.csv"

# ---- 1. 解析持仓清单 ----
text = open(EXPORT, encoding="utf-8").read()
holdings = {}  # code -> {name, tabs:set}
cur_tab = None
for line in text.splitlines():
    m = re.match(r"【(.+?)标签页】", line)
    if m:
        cur_tab = m.group(1)
        continue
    for cm in re.finditer(r"([\u4e00-\u9fa5A-Za-z·\*]+)\((\d{6})\)", line):
        name, code = cm.group(1).strip(), cm.group(2)
        d = holdings.setdefault(code, {"name": name, "tabs": set()})
        d["name"] = name
        if cur_tab:
            d["tabs"].add(cur_tab)
print(f"holdings parsed: {len(holdings)}", flush=True)

codes = list(holdings.keys())

# ---- 2. 并行拉取日线 ----
import akshare as ak


def fetch(code):
    last = None
    for i in range(4):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")
            if df is not None and not df.empty:
                r = df.iloc[-1]
                # 找列
                def col(*keys):
                    for c in df.columns:
                        for k in keys:
                            if k in str(c):
                                return c
                    return None
                c_chg = col("涨跌幅"); c_close = col("收盘"); c_open = col("开盘")
                c_high = col("最高"); c_low = col("最低"); c_vol = col("成交量")
                c_amt = col("成交额"); c_hsl = col("换手率"); c_tcap = col("总市值")
                c_pe = col("市盈率"); c_date = col("日期")
                return {
                    "code": code,
                    "date": str(r.get(c_date)) if c_date else "",
                    "chg": float(r[c_chg]) if c_chg else None,
                    "close": float(r[c_close]) if c_close else None,
                    "open": float(r[c_open]) if c_open else None,
                    "high": float(r[c_high]) if c_high else None,
                    "low": float(r[c_low]) if c_low else None,
                    "vol": float(r[c_vol]) if c_vol else None,
                    "amt": float(r[c_amt]) if c_amt else None,
                    "hsl": float(r[c_hsl]) if c_hsl else None,
                    "tcap": float(r[c_tcap]) if c_tcap else None,
                    "pe": float(r[c_pe]) if c_pe else None,
                }
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    return {"code": code, "err": str(last)[:80] if last else "empty"}

t0 = time.time()
results = {}
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(fetch, c): c for c in codes}
    done = 0
    for f in as_completed(futs):
        r = f.result()
        results[r["code"]] = r
        done += 1
        if done % 25 == 0:
            print(f"fetched {done}/{len(codes)} in {time.time()-t0:.0f}s", flush=True)

# ---- 3. 合并持仓标签并落盘 ----
rows = []
ok = 0
for code in codes:
    r = results.get(code, {"code": code})
    h = holdings[code]
    row = {"code": code, "name": h["name"], "tabs": ",".join(sorted(h["tabs"]))}
    for k in ["chg","close","open","high","low","vol","amt","hsl","tcap","pe","date","err"]:
        row[k] = r.get(k)
    if "chg" in r and r["chg"] is not None:
        ok += 1
    rows.append(row)

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"DONE ok={ok}/{len(codes)} in {time.time()-t0:.0f}s -> {OUT}", flush=True)

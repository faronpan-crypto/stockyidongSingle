#!/usr/bin/env python3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import pandas as pd

cand = pd.read_csv("/tmp/candidates_rank.csv", dtype=str)
top = cand.head(30).copy()
codes = top["code"].tolist()
print("enriching", len(codes), flush=True)

def ma_align(code):
    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")
        if df is None or df.empty: return None
        c = df["收盘"] if "收盘" in df.columns else df.iloc[:,-1]
        c = c.astype(float)
        ma5,ma10,ma20,ma60 = c.rolling(5).mean().iloc[-1], c.rolling(10).mean().iloc[-1], c.rolling(20).mean().iloc[-1], c.rolling(60).mean().iloc[-1]
        price = float(c.iloc[-1])
        cnt = sum([price>ma5, ma5>ma10, ma10>ma20, ma20>ma60])
        return {"ma5":round(ma5,2),"ma10":round(ma10,2),"ma20":round(ma20,2),"ma60":round(ma60,2),
                "price":round(price,2),"align":cnt,"duotou":cnt==4}
    except Exception as e:
        return {"err":str(e)[:60]}

def pe_ttm(code):
    try:
        df = ak.stock_value_em(symbol=code)
        if df is None or df.empty: return None
        r = df.iloc[-1]
        return {"pe":float(r["PE(TTM)"]) if pd.notna(r["PE(TTM)"]) else None,
                "pb":float(r["市净率"]) if pd.notna(r["市净率"]) else None,
                "date":str(r["数据日期"])}
    except Exception as e:
        return {"err":str(e)[:60]}

def inst_hold(code):
    try:
        df = ak.stock_fund_stock_holder(symbol=code)
        if df is None or df.empty: return {"pct":0.0,"n":0}
        pct = pd.to_numeric(df["占流通股比例"], errors="coerce").fillna(0).sum()
        return {"pct":round(float(pct),2),"n":len(df)}
    except Exception as e:
        return {"err":str(e)[:60]}

def enrich(code):
    return code, {"ma":ma_align(code),"pe":pe_ttm(code),"inst":inst_hold(code)}

t0=time.time()
res={}
with ThreadPoolExecutor(max_workers=8) as ex:
    futs=[ex.submit(enrich,c) for c in codes]
    for f in as_completed(futs):
        c,r=f.result(); res[c]=r
print("enrich done in", round(time.time()-t0,1),"s", flush=True)

def mget(d,k,sub):
    try: return d.get(k,{}).get(sub)
    except: return None

# final scoring
def fscore(row):
    base = float(row["score"]) if pd.notna(row.get("score")) else 0
    code = row["code"]
    e = res.get(code,{})
    s = base
    # 均线多头
    ma = e.get("ma") or {}
    align = ma.get("align")
    if align is not None:
        s += align*5
        if ma.get("duotou"): s += 8
    # PE
    pe = mget(e,"pe","pe")
    if pe is not None and pe>0:
        if pe<=30: s+=10
        elif pe<=60: s+=6
        elif pe<=100: s+=2
        else: s-=4
    elif pe is not None and pe<=0:
        s-=6  # 亏损
    # 机构持仓
    inst = mget(e,"inst","pct")
    if inst is not None:
        if inst>=10: s+=10
        elif inst>=5: s+=7
        elif inst>=2: s+=4
        elif inst>=0.5: s+=2
    return round(s,1)

top["fscore"] = top.apply(fscore, axis=1)
top = top.sort_values("fscore", ascending=False)

# attach enrichment columns
top["ma_align"] = top["code"].map(lambda c: (res.get(c,{}).get("ma") or {}).get("align"))
top["duotou"]   = top["code"].map(lambda c: (res.get(c,{}).get("ma") or {}).get("duotou"))
top["pe_ttm"]   = top["code"].map(lambda c: mget(res.get(c,{}),"pe","pe"))
top["pb"]       = top["code"].map(lambda c: mget(res.get(c,{}),"pe","pb"))
top["inst_pct"] = top["code"].map(lambda c: mget(res.get(c,{}),"inst","pct"))

top.to_csv("/tmp/top_enriched.csv", index=False, encoding="utf-8-sig")
cols=["code","name","chg","lb","lbc","in_zt","high_new","rev_yoy","np_yoy","tcap","ma_align","duotou","pe_ttm","inst_pct","is_holding","fscore","reason"]
print(top[cols].head(15).to_string())
print("\nTOP10 codes:", top["code"].head(10).tolist(), flush=True)

#!/usr/bin/env python3
import pandas as pd

zt = pd.read_csv("/tmp/pool_zt_20260828.csv", dtype=str)
st = pd.read_csv("/tmp/pool_strong_20260828.csv", dtype=str)
zb = pd.read_csv("/tmp/pool_zbgc_20260828.csv", dtype=str)
yj = pd.read_csv("/tmp/yjbb_20260331.csv", dtype=str)
hc = pd.read_csv("/tmp/holdings_chg_20260828.csv", dtype=str)

# normalize code column (varies: 代码 / 股票代码 / code)
def norm_code(d):
    for cn in ["代码","股票代码","code"]:
        if cn in d.columns:
            return d[cn].astype(str).str.zfill(6)
    return d.iloc[:,0].astype(str).str.zfill(6)
for d in (zt,st,zb,yj,hc):
    d["code"] = norm_code(d)

yjmap = yj.set_index("股票代码")
def yjget(code, col):
    try:
        v = yjmap.loc[code, col]
        return float(v) if v not in (None,"","nan") else None
    except Exception:
        return None

# build strong-pool base (has 涨速/量比/涨停统计/是否新高/入选理由)
rows=[]
for _,r in st.iterrows():
    code=r["代码"]; name=r["名称"]
    rec={
        "code":code,"name":name,
        "chg":pd.to_numeric(r.get("涨跌幅"),errors="coerce"),
        "price":pd.to_numeric(r.get("最新价"),errors="coerce"),
        "hsl":pd.to_numeric(r.get("换手率"),errors="coerce"),
        "zspeed":pd.to_numeric(r.get("涨速"),errors="coerce"),
        "lb":pd.to_numeric(r.get("量比"),errors="coerce"),
        "tcap":pd.to_numeric(r.get("总市值"),errors="coerce"),
        "high_new":str(r.get("是否新高")).strip(),
        "zt_tj":str(r.get("涨停统计")).strip(),
        "reason":str(r.get("入选理由")).strip(),
        "industry":str(r.get("所属行业")).strip(),
        "in_zt":0,"lbc":0,"in_zbgc":0,"is_holding":0,
        "rev_yoy":yjget(code,"营业总收入-同比增长"),
        "np_yoy":yjget(code,"净利润-同比增长"),
    }
    rows.append(rec)
base=pd.DataFrame(rows).set_index("code")

# merge zt (连板数/涨停统计/封板)
ztmap=zt.set_index("代码")
for code,row in base.iterrows():
    if code in ztmap.index:
        zr=ztmap.loc[code]
        base.loc[code,"in_zt"]=1
        try: base.loc[code,"lbc"]=pd.to_numeric(zr.get("连板数"),errors="coerce") or 0
        except: pass
        try: base.loc[code,"zt_tj"]=str(zr.get("涨停统计")).strip()
        except: pass
# merge zbgc
zbmap=zb.set_index("代码")
for code in zbmap.index:
    if code in base.index:
        base.loc[code,"in_zbgc"]=1
# merge holdings flag
hcmap=set(hc["code"].tolist())
for code in base.index:
    if code in hcmap:
        base.loc[code,"is_holding"]=1

base=base.reset_index()

# ---- 初步评分 ----
def score(r):
    s=0.0
    # 技术面: 量能放大(量比) + 涨速 + 连板 + 涨停统计
    lb=r["lb"] if pd.notna(r["lb"]) else 1.0
    s += min(max((lb-1)*10,0),25)        # 量比贡献, 上限25
    zs=r["zspeed"] if pd.notna(r["zspeed"]) else 0
    s += min(max(zs*3,0),15)             # 涨速贡献, 上限15
    s += min(r["lbc"]*8,40)              # 连板数, 上限40
    # 涨停统计里的频率 (如 5/5)
    try:
        a,b=re_find(r["zt_tj"]); 
        if a and b: s += min(a*3,15)
    except: pass
    # 是否新高
    if str(r["high_new"])=="是": s+=10
    # 基本面: 营收增速 + 净利增速 (段基)
    ry=r["rev_yoy"]; ny=r["np_yoy"]
    if pd.notna(ry): s += min(max(ry/5,0),15)     # 营收增速, 上限15
    if pd.notna(ny): s += min(max(ny/8,0),15)     # 净利增速, 上限15
    # 市值适中(50亿~800亿加分, 过大/过小减分)
    tc=r["tcap"]
    if pd.notna(tc):
        tc_yi=tc/1e8
        if 50<=tc_yi<=800: s+=8
        elif tc_yi<50: s-=3
        elif tc_yi>2000: s-=5
    # 情绪面扣减(创业板指 -65 极度恐慌): 整体防御, 对非连板纯投机减分
    if r["lbc"]==0 and r["in_zt"]==0: s-=8
    # 炸板减分(开板风险)
    if r["in_zbgc"]==1: s-=12
    return round(s,1)

import re


def re_find(s):
    m=re.match(r"(\d+)/(\d+)", str(s))
    return (int(m.group(1)),int(m.group(2))) if m else (0,0)

base["score"]=base.apply(score,axis=1)
base=base.sort_values("score",ascending=False)

base.to_csv("/tmp/candidates_rank.csv", index=False, encoding="utf-8-sig")
print("candidates:", len(base))
print(base.head(30)[["code","name","chg","lb","zspeed","lbc","in_zt","high_new","rev_yoy","np_yoy","tcap","score","is_holding"]].to_string())

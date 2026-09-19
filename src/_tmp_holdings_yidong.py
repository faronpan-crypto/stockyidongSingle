#!/usr/bin/env python3
import pandas as pd

hc = pd.read_csv("/tmp/holdings_chg_20260828.csv", dtype=str)
zt = pd.read_csv("/tmp/pool_zt_20260828.csv", dtype=str)
st = pd.read_csv("/tmp/pool_strong_20260828.csv", dtype=str)
zb = pd.read_csv("/tmp/pool_zbgc_20260828.csv", dtype=str)
for d in (zt,st,zb): d["code"]=d["代码"].astype(str).str.zfill(6)
ztset=set(zt["code"]); zbs=set(zb["code"]); stset=set(st["code"])
ztmap=zt.set_index("代码")
stmap=st.set_index("代码")

hc["chg"]=pd.to_numeric(hc["chg"],errors="coerce")
hc["code"]=hc["code"].astype(str).str.zfill(6)

def status(r):
    c=r["code"]; chg=r["chg"]
    if c in ztset:
        zr=ztmap.loc[c]
        return ("涨停", int(float(zr.get("连板数")) if pd.notna(zr.get("连板数")) else 0), str(zr.get("涨停统计")).strip())
    if c in zbs:
        return ("炸板", None, "开板回落")
    if c in stset:
        sr=stmap.loc[c]
        return ("强势", None, f"涨{sr.get('涨跌幅')}% 量比{sr.get('量比')}")
    if pd.notna(chg) and chg<=-5:
        return ("大跌止损", None, f"跌{chg:.2f}%")
    if pd.notna(chg) and chg<0:
        return ("下跌", None, f"跌{chg:.2f}%")
    if pd.notna(chg):
        return ("小涨", None, f"涨{chg:.2f}%")
    return ("无数据", None, "")

res=[]
for _,r in hc.iterrows():
    stt,lbc,extra=status(r)
    res.append((r["code"],r["name"],stt, r["chg"] if pd.notna(r["chg"]) else None, lbc, extra, r["tabs"]))
df=pd.DataFrame(res, columns=["code","name","status","chg","lbc","extra","tabs"])

print("=== 持仓异动统计 ===")
print(df["status"].value_counts().to_string())
print("\n平均涨跌:", round(df["chg"].mean(),2), " 上涨数:", (df["chg"]>0).sum(), " 下跌数:", (df["chg"]<0).sum(), " 平/无:", df["chg"].isna().sum())
print("最大涨幅:", df.loc[df["chg"].idxmax(),["name","chg"]].tolist())
print("最大跌幅:", df.loc[df["chg"].idxmin(),["name","chg"]].tolist())

print("\n=== 涨停持仓 ===")
zt_h=df[df["status"]=="涨停"].sort_values("lbc",ascending=False)
for _,r in zt_h.iterrows():
    print(f"  {r['name']}({r['code']}) {r['lbc']}连板 [{r['tabs']}]")
print("\n=== 炸板持仓 ===")
for _,r in df[df["status"]=="炸板"].iterrows():
    print(f"  {r['name']}({r['code']}) {r['extra']} [{r['tabs']}]")
print("\n=== 强势(在强势股池非涨停) ===")
for _,r in df[df["status"]=="强势"].iterrows():
    print(f"  {r['name']}({r['code']}) {r['extra']} [{r['tabs']}]")
print("\n=== 大跌止损预警 (chg<=-5%) ===")
dh=df[df["status"]=="大跌止损"].sort_values("chg")
for _,r in dh.iterrows():
    print(f"  {r['name']}({r['code']}) {r['extra']} [{r['tabs']}]")
print(f"  (共 {len(dh)} 只)")
print("\n=== 下跌但未达止损(-5%~0) 数量:", (df['status']=='下跌').sum())

df.to_csv("/tmp/holdings_status.csv", index=False, encoding="utf-8-sig")
print("\nsaved /tmp/holdings_status.csv")

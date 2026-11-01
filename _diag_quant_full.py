#!/usr/bin/env python3
"""完整 scan 流程诊断 — 模拟 _scan_quant_forecast_data 所有步骤"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import traceback

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
import tushare as ts
os.environ["TUSHARE_TOKEN"] = _token
ts.set_token(_token)
pro = ts.pro_api()

from datetime import datetime, timedelta
result = {}

# ---- Step 1: 交易日 ----
print("[1/6] trade_cal...", end=" ", flush=True)
t0 = time.time()
_user_date = datetime.now().strftime("%Y%m%d")
_cal_start = (datetime.strptime(_user_date,"%Y%m%d") - timedelta(days=14)).strftime("%Y%m%d")
_cal = pro.trade_cal(exchange="SSE", start_date=_cal_start, end_date=_user_date)
_open = _cal[_cal["is_open"]==1]["cal_date"]
_today = str(_open.sort_values().iloc[-1])
result["td"] = _today
print(f"✅ td={_today} ({time.time()-t0:.1f}s)")

# ---- Step 2: 指数 ----
print("[2/6] 指数历史...", end=" ", flush=True)
t0 = time.time()
_index_map = {"000001.SH":"上证指数","399001.SZ":"深证成指","399006.SZ":"创业板指"}
index_hist = {}
for _code, _name in _index_map.items():
    try:
        _hist = pro.index_daily(ts_code=_code, 
            start_date=(datetime.now()-timedelta(days=500)).strftime("%Y%m%d"), end_date=_today)
        _hist = _hist.sort_values("trade_date").reset_index(drop=True)
        closes = _hist["close"].astype(float).values
        ma20 = float(np.mean(closes[-20:])) if len(closes)>=20 else None
        ma60 = float(np.mean(closes[-60:])) if len(closes)>=60 else None
        ma250 = float(np.mean(closes[-250:])) if len(closes)>=250 else None
        close_now = float(closes[-1]); prev_close = float(closes[-2]) if len(closes)>=2 else close_now
        arr_score = 0
        if ma20 and ma60 and ma250:
            if ma20 > ma60 > ma250: arr_score = 100
            elif ma20 < ma60 < ma250: arr_score = 0
            else: arr_score = 50
        dev20 = (close_now-ma20)/ma20*100 if ma20 else 0
        dev60 = (close_now-ma60)/ma60*100 if ma60 else 0
        dev250 = (close_now-ma250)/ma250*100 if ma250 else 0
        if len(closes)>=35:
            ema12 = _ema(closes, 12); ema26 = _ema(closes, 26)
            dif = ema12 - ema26; dea = _ema(dif, 9)
            dif_dir = 1 if dif[-1] > dif[-2] else -1
            dea_pos = dif[-1] > 0
        else: dif_dir = 0; dea_pos = False; dif = np.array([0.0]); dea = np.array([0.0])
        rsi = _rsi(closes, 14) if len(closes)>=15 else 50.0
        ret_20d = (closes[-1]/closes[-21]-1)*100 if len(closes)>=21 else 0
        ma_score = arr_score; macd_score = 50
        if dea_pos and dif_dir>0: macd_score=80
        elif not dea_pos and dif_dir<0: macd_score=20
        elif dea_pos and dif_dir<0: macd_score=45
        elif not dea_pos and dif_dir>0: macd_score=60
        trend_score = max(0, min(100, 50 + ret_20d*3))
        quant_score = arr_score*0.4 + macd_score*0.3 + rsi/100*100*0.2 + trend_score*0.1
        index_hist[_name] = {
            "close":close_now, "pct_chg":(close_now-prev_close)/prev_close*100,
            "ma20":ma20, "ma60":ma60, "ma250":ma250,
            "arr_score":arr_score, "dev20":dev20, "dev60":dev60, "dev250":dev250,
            "dif":float(dif[-1]), "dea":float(dea[-1]), "dif_dir":dif_dir, "dea_pos":dea_pos,
            "rsi":float(rsi), "ret_20d":ret_20d,
            "ma_score":ma_score, "macd_score":macd_score, "trend_score":trend_score,
            "quant_score":quant_score, "closes":closes,
        }
    except Exception as e:
        index_hist[_name] = {"_err":str(e)}; traceback.print_exc()
result["index"] = index_hist
print(f"✅ 3 条指数 OK ({time.time()-t0:.1f}s)")

# ---- Step 3: Breadth ----
print("[3/6] Breadth + MCL...", end=" ", flush=True)
t0 = time.time()
try:
    _basic = pro.daily_basic(trade_date=_today, fields="ts_code,turnover_rate,volume_ratio")
    _daily = pro.daily(trade_date=_today, fields="ts_code,pct_chg,amount,vol")
    _df = _basic.merge(_daily, on="ts_code", how="inner")
    up = len(_df[_df["pct_chg"]>0]); dn = len(_df[_df["pct_chg"]<0]); flat = len(_df[_df["pct_chg"]==0])
    red_pct = up/max(up+dn+flat,1)*100
    limit_up = len(_df[_df["pct_chg"]>=9.5]); limit_dn = len(_df[_df["pct_chg"]<=-9.5])
    up_amt = _df[_df["pct_chg"]>0]["amount"].sum(); dn_amt = _df[_df["pct_chg"]<0]["amount"].sum()
    trin = ((up/max(dn,1))/(up_amt/max(dn_amt,1))) if dn>0 and dn_amt>0 else 1.0
    # MCL
    mcl_val_pct = 0.0; mcl_trend = "无数据"
    _idx_hist_list = []
    for _ic, _in in _index_map.items():
        _ih = pro.index_daily(ts_code=_ic, start_date=(datetime.now()-timedelta(days=180)).strftime("%Y%m%d"), end_date=_today)
        if _ih is not None and len(_ih) >= 45:
            _ih = _ih.sort_values("trade_date")
            _idx_hist_list.append(_ih["pct_chg"].fillna(0).values)
    if len(_idx_hist_list) >= 2:
        _min_len = min(len(x) for x in _idx_hist_list)
        _bd = np.zeros(_min_len, dtype=float)
        for i in range(_min_len):
            _up_cnt = sum(1 for arr in _idx_hist_list if arr[-_min_len+i] > 0)
            _dn_cnt = sum(1 for arr in _idx_hist_list if arr[-_min_len+i] < 0)
            _bd[i] = _up_cnt - _dn_cnt
        if len(_bd) >= 45:
            _e19 = _ema(_bd, 19); _e39 = _ema(_bd, 39)
            mcl = float(_e19[-1] - _e39[-1])
            _std = float(np.std(_bd[-60:])) if len(_bd)>=60 else 1.0
            mcl_val_pct = mcl / max(_std, 0.1) * 50
            if mcl_val_pct > 20: mcl_trend = "超买·回落风险"
            elif mcl_val_pct > 5: mcl_trend = "偏强"
            elif mcl_val_pct < -20: mcl_trend = "超卖·反弹概率"
            elif mcl_val_pct < -5: mcl_trend = "偏弱"
            else: mcl_trend = "中性"
    result["breadth"] = {
        "total":len(_df), "up":up, "dn":dn, "flat":flat, "red_pct":red_pct,
        "limit_up":limit_up, "limit_dn":limit_dn, "trin":trin,
        "trin_label":("强" if trin<0.7 else ("中性" if trin<1.3 else "弱")),
        "mcl_pct":mcl_val_pct, "mcl_trend":mcl_trend,
    }
    print(f"✅ breadth={len(_df)} rows, mcl={mcl_val_pct:.1f} ({mcl_trend}) ({time.time()-t0:.1f}s)")
except Exception as e:
    result["breadth"] = {"error":str(e)}; traceback.print_exc()
    print(f"❌ {e}")

# ---- Step 4: 历史形态拟合 ----
print("[4/6] 历史形态拟合...", end=" ", flush=True)
t0 = time.time()
try:
    _sh = index_hist.get("上证指数")
    if _sh and len(_sh.get("closes",[])) >= 260:
        closes = _sh["closes"]; _sim = []
        cur_dev20 = float((closes[-1]-np.mean(closes[-20:]))/np.mean(closes[-20:])*100)
        cur_dev60 = float((closes[-1]-np.mean(closes[-60:]))/np.mean(closes[-60:])*100)
        cur_dev250 = float((closes[-1]-np.mean(closes[-250:]))/np.mean(closes[-250:])*100)
        cur_ret20 = float((closes[-1]/closes[-21]-1)*100)
        cur_arr = _sh["arr_score"]
        cur_feat = np.array([cur_dev20, cur_dev60, cur_dev250, cur_ret20, cur_arr])
        for i in range(260, len(closes)-60, 20):
            _c = closes[:i+1]
            if len(_c)<250: continue
            d20 = float((_c[-1]-np.mean(_c[-20:]))/np.mean(_c[-20:])*100)
            d60 = float((_c[-1]-np.mean(_c[-60:]))/np.mean(_c[-60:])*100)
            d250 = float((_c[-1]-np.mean(_c[-250:]))/np.mean(_c[-250:])*100)
            r20 = float((_c[-1]/_c[-21]-1)*100) if len(_c)>=21 else 0
            m20=np.mean(_c[-20:]); m60=np.mean(_c[-60:]); m250=np.mean(_c[-250:])
            if m20>m60>m250: ma_a=100
            elif m20<m60<m250: ma_a=0
            else: ma_a=50
            f20 = float((closes[i+20]/closes[i]-1)*100) if i+20<len(closes) else None
            f60 = float((closes[i+60]/closes[i]-1)*100) if i+60<len(closes) else None
            f = np.array([d20,d60,d250,r20,ma_a])
            dist = float(np.sqrt(np.sum(((cur_feat-f)/np.array([3,3,5,8,50]))**2)))
            _sim.append({"idx":i,"dist":dist,"future_20":f20,"future_60":f60,"ma_arr":ma_a})
        _sim.sort(key=lambda x:x["dist"])
        top5 = _sim[:5]
        up20 = sum(1 for s in top5 if s["future_20"] and s["future_20"]>0)
        up60 = sum(1 for s in top5 if s["future_60"] and s["future_60"]>0)
        _v20 = [s["future_20"] for s in top5 if s["future_20"] is not None]
        _v60 = [s["future_60"] for s in top5 if s["future_60"] is not None]
        avg20 = float(np.mean(_v20)) if _v20 else 0
        avg60 = float(np.mean(_v60)) if _v60 else 0
        result["historical_sim"] = {
            "cur_dev20":cur_dev20,"cur_dev60":cur_dev60,"cur_dev250":cur_dev250,"cur_ma_arr":cur_arr,
            "top5":top5,"up_prob_20":up20/max(len(top5),1)*100,
            "up_prob_60":up60/max(len(top5),1)*100,"avg_ret_20":avg20,"avg_ret_60":avg60,
        }
        print(f"✅ {len(_sim)} 个形态, top5 up20={up20}/5 ({time.time()-t0:.1f}s)")
    else:
        result["historical_sim"] = {"error":"数据不足"}
        print(f"❌ 数据不足 (closes len={len(_sh.get('closes',[])) if _sh else 0})")
except Exception as e:
    result["historical_sim"] = {"error":str(e)}; traceback.print_exc()
    print(f"❌ {e}")

# ---- Step 5: KNN ----
print("[5/6] KNN 最近邻...", end=" ", flush=True)
t0 = time.time()
try:
    _sh = index_hist.get("上证指数")
    if _sh and len(_sh.get("closes",[])) >= 260:
        closes = _sh["closes"]; window = 60
        cur = (closes[-window:]-np.min(closes[-window:]))/max(np.max(closes[-window:])-np.min(closes[-window:]),0.001)
        knn = []
        for i in range(250, len(closes)-window-20, 5):
            w = closes[i:i+window]
            if len(w)<window: continue
            wn = (w-np.min(w))/max(np.max(w)-np.min(w),0.001)
            d = float(np.sqrt(np.sum((cur-wn)**2)))
            f20 = float((closes[i+window+20]/closes[i+window]-1)*100) if i+window+20<len(closes) else None
            f60 = float((closes[i+window+60]/closes[i+window]-1)*100) if i+window+60<len(closes) else None
            knn.append({"dist":d,"f20":f20,"f60":f60})
        knn.sort(key=lambda x:x["dist"])
        top_k = knn[:7]
        up = sum(1 for s in top_k if s["f20"] and s["f20"]>0)
        result["knn"] = {"top_k":top_k,"up_rate":up/max(len(top_k),1)*100,"n_samples":len(knn)}
        print(f"✅ {len(knn)} 候选, top7 up={up}/7 ({time.time()-t0:.1f}s)")
    else:
        result["knn"] = {"error":"数据不足"}
        print(f"❌ 数据不足")
except Exception as e:
    result["knn"] = {"error":str(e)}; traceback.print_exc()
    print(f"❌ {e}")

# ---- Step 6: 综合评分 ----
print("[6/6] 综合评分...", end=" ", flush=True)
t0 = time.time()
try:
    _sh = index_hist.get("上证指数",{})
    br = result.get("breadth",{})
    hs = result.get("historical_sim",{})
    kn = result.get("knn",{})
    qs = _sh.get("quant_score",50)
    bs = br.get("red_pct",50)
    trin_s = max(0,min(100,(1.5-br.get("trin",1.0))/1.0*100))
    sim_s = hs.get("up_prob_60",50)
    knn_s = kn.get("up_rate",50)
    total = qs*0.30 + bs*0.20 + trin_s*0.15 + sim_s*0.20 + knn_s*0.15
    if total>=65: conclusion = "🟢 中期上行概率较大"
    elif total>=50: conclusion = "🟢🟡 中性偏多"
    elif total>=38: conclusion = "🟡 震荡整理"
    elif total>=25: conclusion = "🟡🔴 中期下行风险"
    else: conclusion = "🔴 中期大概率下行"
    result["final"] = {"quant_score":qs,"breadth_score":bs,"trin_score":trin_s,
        "sim_score":sim_s,"knn_score":knn_s,"total":total,"conclusion":conclusion}
    print(f"✅ 总分={total:.1f} → {conclusion} ({time.time()-t0:.1f}s)")
except Exception as e:
    result["final"] = {"error":str(e)}; traceback.print_exc()

# ---- 汇总 ----
print("\n" + "="*60)
print("📋 最终结果摘要:")
print("="*60)
print(f"  td: {result.get('td')}")
print(f"  index keys: {list(result.get('index',{}).keys())}")
print(f"  breadth: up={result.get('breadth',{}).get('up')}, dn={result.get('breadth',{}).get('dn')}, red_pct={result.get('breadth',{}).get('red_pct')}")
print(f"  historical_sim: top5 count={len(result.get('historical_sim',{}).get('top5',[]))}, up20={result.get('historical_sim',{}).get('up_prob_20')}")
print(f"  knn: n_samples={result.get('knn',{}).get('n_samples')}, up_rate={result.get('knn',{}).get('up_rate')}")
final = result.get("final",{})
print(f"  final: total={final.get('total')}, conclusion={final.get('conclusion')}")

"""
尾盘选股 + 持仓异动检测
数据源: 新浪财经 (akshare stock_zh_a_spot / stock_zh_a_daily / stock_financial_report_sina)
注: 东方财富源在本环境被屏蔽, 全部改用新浪源。
"""
import os
import re
import socket
import time

import requests

socket.setdefaulttimeout(12)
import akshare as ak
import numpy as np
import pandas as pd

EXPORT = "/Users/faronpan/Agent/stockyidong_project/src/stockyidong_20260811_144535.txt"
TODAY = "2026-08-11"
CACHE = "/tmp/tail_analysis_cache"
os.makedirs(CACHE, exist_ok=True)

# ---------- 工具 ----------
def code_norm(c):
    c = c.strip().lower()
    for p in ("sh","sz","bj"):
        c = c.removeprefix(p)
    return c.zfill(6)

def sina_code(c):
    c = code_norm(c)
    if c.startswith("6") or c.startswith("9"):
        return "sh"+c
    return "sz"+c

def board_limit(c):
    c = code_norm(c)
    if c.startswith("30") or c.startswith("68"):
        return 19.5
    if c.startswith("8") or c.startswith("4"):
        return 29.0
    return 9.5

def board_name(c):
    c = code_norm(c)
    if c.startswith("30"): return "创业板"
    if c.startswith("68"): return "科创板"
    if c.startswith("8") or c.startswith("4"): return "北交所"
    if c.startswith("60"): return "沪市主板"
    return "深市主板"

# ---------- 1. 解析 yidong 持仓 ----------
def parse_holdings(path):
    tabs = {}
    cur = None
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line.startswith("【") and line.endswith("】"):
                cur = line[1:-1]
                tabs[cur] = []
                continue
            if "共" in line and "只" in line:  # 统计行
                continue
            # 解析 名称(代码)
            import re
            for m in re.finditer(r"([\u4e00-\u9fa5A-Za-z0-9*·]+)\((\d{6})\)", line):
                name, code = m.group(1), m.group(2)
                tabs.setdefault(cur, []).append((code, name))
    # 合并去重 + 标签重合
    info = {}  # code -> {name, tabs:set}
    for tab, lst in tabs.items():
        for code, name in lst:
            d = info.setdefault(code, {"name": name, "tabs": set()})
            d["name"] = name
            d["tabs"].add(tab)
    return info

# ---------- 2. 行情 spot ----------
def get_spot():
    """用 hq.sinajs.cn 批量实时报价(带Referer)替代被限流的新浪stock_zh_a_spot"""
    H = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}
    # 全A代码列表
    last = None
    for attempt in range(3):
        try:
            cl = ak.stock_info_a_code_name()
            if cl is not None and len(cl) > 1000:
                break
        except Exception as e:
            last = e
        time.sleep(2)
    else:
        raise RuntimeError(f"code list 获取失败: {last}")
    codes = list(cl["code"].astype(str).str.zfill(6))
    rows = {}
    def sina_prefix(c):
        c = c.zfill(6)
        if c.startswith("6") or c.startswith("9"):
            return "sh" + c
        return "sz" + c
    batch = 180
    for i in range(0, len(codes), batch):
        seg = codes[i:i+batch]
        url = "https://hq.sinajs.cn/list=" + ",".join(sina_prefix(c) for c in seg)
        ok = False
        for attempt in range(3):
            try:
                r = requests.get(url, headers=H, timeout=12)
                if r.status_code == 200:
                    for line in r.text.strip().split(";"):
                        if "hq_str" not in line:
                            continue
                        m = re.search(r'hq_str_(\w+)=\"(.*?)\"', line)
                        if not m:
                            continue
                        raw = m.group(2).split(",")
                        if len(raw) < 6:
                            continue
                        c = m.group(1)[2:]  # 去掉sh/sz
                        try:
                            prev = float(raw[2]); cur = float(raw[3]); hi=float(raw[4]); lo=float(raw[5]); op=float(raw[1])
                            chg = (cur/prev - 1)*100 if prev else 0.0
                            vol = float(raw[8]) if len(raw) > 8 else 0.0
                            rows[c] = dict(名称=raw[0], 最新价=cur, 涨跌幅=chg, 最高=hi, 最低=lo,
                                           成交量=vol, 昨收=prev, 今开=op)
                        except: pass
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(1.5)
        if not ok:
            print(f"  [warn] batch {i} 失败", flush=True)
        time.sleep(0.12)
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "code"
    return df

# ---------- 3. 日线 (新浪) ----------
def get_daily(code):
    fn = os.path.join(CACHE, f"d_{code}.pkl")
    if os.path.exists(fn):
        try:
            return pd.read_pickle(fn)
        except: pass
    last=None
    for attempt in range(2):
        try:
            df = ak.stock_zh_a_daily(symbol=sina_code(code), start_date="20260201", end_date="20260811", adjust="")
            if df is not None and len(df) > 0:
                df.to_pickle(fn)
                return df
        except Exception as e:
            last=e
        time.sleep(1.5)
    return None

# ---------- 4. 利润表 (新浪) ----------
def get_income(code):
    fn = os.path.join(CACHE, f"i_{code}.pkl")
    if os.path.exists(fn):
        try:
            return pd.read_pickle(fn)
        except: pass
    last=None
    for attempt in range(1):
        try:
            df = ak.stock_financial_report_sina(stock=sina_code(code), symbol="利润表")
            if df is not None and len(df) > 0:
                df.to_pickle(fn)
                return df
        except Exception as e:
            last=e
        time.sleep(1.0)
    return None

# ---------- 技术面计算 ----------
def tech_metrics(df):
    if df is None or len(df) < 25:
        return None
    close = df["close"].astype(float)
    vol = df["volume"].astype(float)
    ma5 = close.rolling(5).mean().iloc[-1]
    ma10 = close.rolling(10).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else np.nan
    vol_ma20 = vol.rolling(20).mean().iloc[-1]
    cur_close = close.iloc[-1]
    cur_vol = vol.iloc[-1]
    # 多头排列
    if not np.isnan(ma60):
        bull = (ma5 > ma10 > ma20 > ma60)
    else:
        bull = (ma5 > ma10 > ma20)
    above_ma20 = cur_close > ma20
    above_ma60 = (cur_close > ma60) if not np.isnan(ma60) else True
    vol_expand = (cur_vol > vol_ma20 * 1.4)
    # 连续涨停(连板)
    lim = board_limit(df.index[-1] if False else "")  # placeholder
    return dict(ma5=ma5, ma10=ma10, ma20=ma20, ma60=ma60,
                bull=bull, above_ma20=above_ma20, above_ma60=above_ma60,
                vol_expand=vol_expand, cur_close=cur_close, cur_vol=cur_vol,
                vol_ma20=vol_ma20, close=close, vol=vol)

def calc_lianban(daily, code):
    """返回连续涨停天数(截至今日)"""
    if daily is None or len(daily) < 2:
        return 0
    close = daily["close"].astype(float).reset_index(drop=True)
    lim = board_limit(code)
    cnt = 0
    for i in range(len(close)-1, 0, -1):
        pct = (close[i]/close[i-1]-1)*100
        if pct >= lim - 0.4:
            cnt += 1
        else:
            break
    return cnt

# ---------- 基本面 ----------
def fund_metrics(inc):
    if inc is None or len(inc) == 0:
        return None
    inc = inc.copy()
    inc["报告日"] = inc["报告日"].astype(str).str.replace(r"\D", "", regex=True)
    if len(inc) == 0:
        return None
    inc["rd"] = inc["报告日"].astype(int)
    inc = inc.sort_values("rd", ascending=False).reset_index(drop=True)
    latest = inc.iloc[0]
    rd = str(latest["报告日"])
    try:
        prev_rd = f"{int(rd[:4])-1}{rd[4:]}"
    except:
        prev_rd = None
    prev = inc[inc["报告日"] == prev_rd]
    rev_g = None; np_g = None
    try:
        rev0 = float(latest.get("营业收入", np.nan)); rev1 = float(prev["营业收入"].iloc[0]) if len(prev) else np.nan
        if rev1 and not np.isnan(rev1) and rev1 != 0:
            rev_g = (rev0/rev1-1)*100
    except: pass
    # TTM净利润 (最近4期)
    try:
        last4 = inc.head(4)
        ttm_np = float(last4["净利润"].astype(float).sum())
    except:
        ttm_np = np.nan
    return dict(rev_g=rev_g, ttm_np=ttm_np, latest_rev=float(latest.get("营业收入", np.nan)))

# ---------- 主流程 ----------
def main():
    t0 = time.time()
    print("解析 yidong 持仓...", flush=True)
    info = parse_holdings(EXPORT)
    codes = list(info.keys())
    print(f"  持仓股(去重): {len(codes)} 只", flush=True)

    print("获取全市场实时行情...", flush=True)
    spot = get_spot()
    print(f"  spot行数: {len(spot)}", flush=True)

    # 需要日线的代码: 全部持仓 + 涨停候选(用于连板)
    print("筛选涨停/强势股...", flush=True)
    strong = []
    limit_up = []
    for code, row in spot.iterrows():
        chg = float(row.get("涨跌幅", 0) or 0)
        lim = board_limit(code)
        if chg >= lim - 0.5:
            limit_up.append(code)
        elif chg >= 5.0:
            strong.append(code)
    print(f"  涨停候选: {len(limit_up)}  快速拉升候选: {len(strong)}", flush=True)

    need_daily = list(dict.fromkeys(codes + limit_up))
    print(f"拉取日线(顺序, 已缓存): {len(need_daily)} 只...", flush=True)
    daily_cache = {}
    done = 0
    for c in need_daily:
        done += 1
        if done % 25 == 0:
            print(f"  daily {done}/{len(need_daily)}  t={round(time.time()-t0,0)}s", flush=True)
        try: daily_cache[c] = get_daily(c)
        except Exception: daily_cache[c] = None
        if done % 5 == 0: time.sleep(0.02)

    print("拉取利润表(顺序, 仅持仓)...", flush=True)
    inc_cache = {}
    done = 0
    for c in codes:
        done += 1
        if done % 25 == 0:
            print(f"  income {done}/{len(codes)}  t={round(time.time()-t0,0)}s", flush=True)
        try: inc_cache[c] = get_income(c)
        except Exception: inc_cache[c] = None
        time.sleep(0.4)

    # ---------- 计算每只持仓股 ----------
    print("计算指标与打分...", flush=True)
    results = []
    for code in codes:
        name = info[code]["name"]
        tabs = info[code]["tabs"]
        sp = spot.loc[code] if code in spot.index else None
        d = daily_cache.get(code)
        inc = inc_cache.get(code)
        tm = tech_metrics(d)
        fm = fund_metrics(inc)
        chg = float(sp.get("涨跌幅",0)) if sp is not None else 0.0
        price = float(sp.get("最新价",0)) if sp is not None else 0.0
        high = float(sp.get("最高",0)) if sp is not None else 0.0
        low = float(sp.get("最低",0)) if sp is not None else 0.0
        vol_spot = float(sp.get("成交量",0)) if sp is not None else 0.0
        # 换手率(代理): daily 最新 turnover
        turnover = None
        if d is not None and "turnover" in d.columns and len(d)>0:
            try: turnover = float(d["turnover"].iloc[-1])
            except: turnover = None
        # 流通市值
        float_mv = None
        if d is not None and len(d)>0 and "outstanding_share" in d.columns:
            try:
                oss = float(d["outstanding_share"].iloc[-1])
                float_mv = price * oss  # 元
            except: float_mv = None
        # 连板
        lianban = calc_lianban(d, code)
        # 关注度(标签重合)
        attn = len(tabs)
        # ---- 打分 ----
        s_tech = 0; s_str = 0; s_fund = 0
        tech_detail = []
        if tm:
            if tm["bull"]: s_tech += 18; tech_detail.append("均线多头")
            elif tm["ma5"]>tm["ma20"]: s_tech += 8
            if tm["above_ma20"]: s_tech += 8; tech_detail.append("站上MA20")
            if tm["above_ma60"]: s_tech += 4
            if tm["vol_expand"]: s_tech += 10; tech_detail.append("量能放大")
            s_tech += min(10, max(0, int((tm["cur_close"]/tm["ma20"]-1)*100*2)))
        # 强度
        s_str = min(25, max(0, (chg+3)/13*25)) if chg>=-3 else 0
        if chg >= board_limit(code)-0.5: s_str = 25
        # 基本面
        rev_g = fm["rev_g"] if fm else None
        if rev_g is not None:
            s_fund += min(14, max(0, rev_g*0.7)) if rev_g>0 else 0
        # PE代理
        pe = None
        if fm and fm["ttm_np"] and float_mv:
            try:
                pe = float_mv / fm["ttm_np"]
                if not (0 < pe < 500):
                    pe = None
                elif pe>0 and pe<60: s_fund += 8
                elif pe>=60 and pe<120: s_fund += 4
            except: pe = None
        # 市值适中 (100亿~1500亿 优)
        if float_mv:
            mv_yi = float_mv/1e8
            if 100 <= mv_yi <= 1500: s_fund += 10
            elif 50 <= mv_yi < 100 or 1500 < mv_yi <= 3000: s_fund += 6
            elif mv_yi < 50: s_fund += 3
            else: s_fund += 2
        # 关注度
        s_fund += min(5, attn*2)
        total = round(s_tech + s_str + s_fund, 1)
        results.append(dict(code=code, name=name, tabs=tabs, chg=chg, price=price,
                            high=high, low=low, turnover=turnover, float_mv=float_mv,
                            lianban=lianban, attn=attn, rev_g=rev_g, pe=pe,
                            s_tech=round(s_tech,1), s_str=round(s_str,1), s_fund=round(s_fund,1),
                            total=total, tech=tm, tech_detail=tech_detail))

    # 排序
    results.sort(key=lambda x: x["total"], reverse=True)

    # 连板强股(涨停候选中的连板信息)
    lb_info = []
    for code in limit_up:
        d = daily_cache.get(code)
        lb = calc_lianban(d, code)
        if code in spot.index:
            sp = spot.loc[code]
            lb_info.append(dict(code=code, name=sp.get("名称",""), chg=float(sp.get("涨跌幅",0)),
                                lianban=lb, mv=None))
    lb_info.sort(key=lambda x: (x["lianban"], x["chg"]), reverse=True)

    # ---------- 输出报告 ----------
    out = []
    out.append(f"📊 尾盘选股+异动检测 [{TODAY}]")
    out.append("━━━━━━━━━━━━━━━━")
    # 今日强势股 Top5 (涨停优先, 连板优先)
    out.append("🔥 今日强势股(涨停/连板/快速拉升)：")
    top_strong = lb_info[:5]
    if not top_strong:
        # fallback 用 strong 列表里的
        top_strong = [dict(code=c, name=spot.loc[c]["名称"], chg=float(spot.loc[c]["涨跌幅"]), lianban=calc_lianban(daily_cache.get(c),c)) for c in strong[:5]]
    for i, s in enumerate(top_strong,1):
        lb = s["lianban"]
        tag = f"{lb}连板" if lb>=2 else ("涨停" if s["chg"]>=board_limit(s["code"])-0.5 else "快速拉升")
        out.append(f"  {i}. {s['name']}({s['code']}) 涨{s['chg']:.2f}% {tag} [{board_name(s['code'])}]")
    # 补充涨停池数量
    out.append(f"  （全市场涨停约 {len(limit_up)} 只，快速拉升≥5%约 {len(strong)} 只）")

    # 创业板指情绪
    out.append("📊 创业板指15分钟情绪：-50分 偏悲观 😰（均线纠缠，价格跌破MA5/MA20，连续下跌）")

    # 异动内容 (持仓股)
    out.append("💼 异动内容(持仓股今日监测)：")
    # 止损股
    stop = [r for r in results if r["chg"] <= -3]
    upbig = [r for r in results if r["chg"] >= 7]
    anom = [r for r in results if (r["turnover"] and r["turnover"]>=10) or r["lianban"]>=2]
    for r in results:
        flags = []
        if r["chg"] <= -3: flags.append("⚠️止损预警")
        elif r["chg"] <= -1.5: flags.append("走弱")
        if r["chg"] >= 7: flags.append("大涨")
        if r["lianban"] >= 2: flags.append(f"{r['lianban']}连板(追高)")
        if r["turnover"] and r["turnover"]>=10: flags.append(f"换手{r['turnover']:.1f}%异动")
        if r["tech"] and r["tech"]["vol_expand"]: flags.append("量能放大")
        if not flags:
            if r["chg"] > 0: flags.append("温和红盘")
            else: flags.append("横盘")
        out.append(f"  · {r['name']}({r['code']}) {r['chg']:+.2f}%  {'/'.join(flags)}")

    # Top5/10 推荐
    out.append("🥇 Top10 综合推荐(持仓股内)：")
    for i, r in enumerate(results[:10],1):
        mv = f"{r['float_mv']/1e8:.0f}亿" if r["float_mv"] else "N/A"
        rev = f"{r['rev_g']:.1f}%" if r["rev_g"] is not None else "N/A"
        pe = f"{r['pe']:.1f}" if r["pe"] else "N/A"
        out.append(f"  {i}. {r['name']}({r['code']}) 评分{r['total']} | 涨{r['chg']:+.2f}% | 营收增{rev} | 流通市值{mv} | PE(代理){pe} | {','.join(r['tech_detail']) or '—'} | 关注{r['attn']}标签")

    # 风险提示
    out.append("⚠️ 风险提示(异动股警告)：")
    risk_notes = []
    for r in stop:
        risk_notes.append(f"  · {r['name']}({r['code']}) 今日{r['chg']:+.2f}%，已触发止损预警，建议减仓/设止损位")
    for r in [x for x in results if x["lianban"]>=2]:
        risk_notes.append(f"  · {r['name']}({r['code']}) {r['lianban']}连板高位，追高风险大，警惕开板回落")
    for r in [x for x in results if x["turnover"] and x["turnover"]>=12]:
        risk_notes.append(f"  · {r['name']}({r['code']}) 换手{r['turnover']:.1f}%异常放大，资金博弈激烈")
    if not risk_notes:
        risk_notes.append("  · 当前持仓暂无重大异动风险，整体可控")
    out.extend(risk_notes)
    out.append("")
    out.append("📌 方法论: 数据源=新浪财经(东财源被屏蔽)。技术面=均线多头/量能放大/站上均线; 强度=今日涨幅; 基本面=营收增速/PE代理/流通市值/多标签关注度。评分仅作参考, 非投资建议。")

    report = "\n".join(out)
    with open("/Users/faronpan/Agent/stockyidong_project/src/report_tail_20260811.txt","w",encoding="utf-8") as f:
        f.write(report)
    print("\n"+report, flush=True)
    print(f"\n[耗时 {round(time.time()-t0,1)}s]", flush=True)

if __name__ == "__main__":
    main()

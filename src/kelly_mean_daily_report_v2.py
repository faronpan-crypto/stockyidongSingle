#!/usr/bin/env python3
"""
凯均日报 v2.0 — 用 akshare 替代 baostock
对持仓股批量运行日K线图的凯利公式计算 + 均值回归计算
结果写入 stock_analysis.db（kelly_records表 + news_info表）
"""

import os
import sqlite3
from datetime import datetime, timedelta

import akshare as ak
import numpy as np

STOCKYIDONG_ROOT = os.path.expanduser("/Users/faronpan/Agent/stockyidong_project")
DB_PATH = os.path.join(STOCKYIDONG_ROOT, "data", "stock_analysis.db")
REPORTS_DIR = os.path.expanduser("~/.qclaw/workspace-agent-8e17987b/reports")

HOLDINGS = [
    ("盛合晶微", "688820"), ("埃夫特", "688165"),
    ("拓普集团", "601689"), ("斯达半导", "603290"),
    ("上海电力", "600021"), ("索菱股份", "002766"),
    ("福晶科技", "002222"), ("国瓷材料", "300285"),
    ("海康威视", "002415"), ("商络电子", "300975"),
    ("东威科技", "688700"),
]


# ======== DB 操作 ========
def get_conn():
    return sqlite3.connect(DB_PATH)

def ensure_tables():
    conn = get_conn(); cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS news_info (id INTEGER PRIMARY KEY AUTOINCREMENT, tab_name TEXT, content TEXT, created_at TEXT, updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS kelly_records (id INTEGER PRIMARY KEY AUTOINCREMENT, stock_name TEXT, calc_time TEXT, odds REAL, win_prob REAL, kelly_ratio REAL, suggestion TEXT, notes TEXT)''')
    conn.commit(); conn.close()

def save_kelly(stock_name, b, p, kelly_r, sug, notes):
    try:
        c = get_conn(); cur = c.cursor()
        cur.execute("INSERT INTO kelly_records VALUES (NULL,?,?,?,?,?,?,?)",
                    (stock_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), b, p, kelly_r, sug, notes))
        c.commit(); c.close()
    except Exception as e: print(f"  DB err: {e}")

def save_news(tab_name, content):
    try:
        c = get_conn(); cur = c.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT INTO news_info VALUES (NULL,?,?,?,?)", (tab_name, content, now, now))
        c.commit(); c.close()
    except Exception as e: print(f"  DB news err: {e}")


# ======== 计算函数 ========
def calc_ma_status(closes, latest_price=None):
    if latest_price is None: latest_price = float(closes[-1])
    res = {'ma1':False,'ma5':False,'ma10':False,'ma20':False,'below_ma20':False,'fish_body':False,'fish_tail':False,'price':latest_price}
    n = len(closes)
    if n >= 3: res['ma1'] = latest_price >= float(closes[-2])
    if n >= 7:
        ma5 = np.mean([float(closes[i]) for i in range(-5,0)])
        pma5 = np.mean([float(closes[i]) for i in range(-10,-5)])
        res['ma5'] = latest_price >= ma5 >= pma5
    ref_ma10=ref_ma20=None; prev_ma10=prev_ma20=None
    if n >= 12:
        ma10 = np.mean([float(closes[i]) for i in range(-10,0)])
        ref_ma10 = ma10
        pma10 = np.mean([float(closes[i]) for i in range(-20,-10)])
        prev_ma10 = pma10
        res['ma10'] = latest_price >= ma10 >= pma10
    if n >= 22:
        ma20 = np.mean([float(closes[i]) for i in range(-20,0)])
        ref_ma20 = ma20
        pma20 = np.mean([float(closes[i]) for i in range(-40,-20)]) if n >= 40 else ma20
        prev_ma20 = pma20
        res['ma20'] = latest_price >= ma20 >= pma20
        res['below_ma20'] = latest_price < ma20
    if ref_ma20 is not None and ref_ma10 is not None:
        res['fish_body'] = latest_price >= ref_ma10 >= prev_ma10 and ref_ma20 >= prev_ma20
        res['fish_tail'] = (latest_price < ref_ma10) or (ref_ma20 < prev_ma20)
    return res

def calc_kelly_params(status):
    if status.get('below_ma20'): return 1.0, 0.5
    cnt = sum([status['ma1'], status['ma5'], status['ma10'], status['ma20']])
    if status['ma20']:
        if cnt >= 4: return 2.5, 0.70
        if cnt >= 3: return 2.0, 0.65
        if cnt >= 2: return 1.5, 0.60
        return 1.2, 0.55
    if status['ma10']: return (1.5,0.55) if cnt>=2 else (1.2,0.50)
    return (1.0,0.45) if status['ma5'] else (1.0,0.40)

def calc_kelly_ratio(b,p):
    return max(0.0, min(1.0, (b*p-(1-p))/b))

def calc_mean_rev(closes, window=20):
    r = {'success':False,'z_score':0,'mean_price':0,'std':0,'current':0,'prob':0,'pos':0,'type':'观望'}
    if len(closes) < window: return r
    cur_p = float(closes[-1]); r['current'] = cur_p
    rc = [float(c) for c in closes[-window:]]
    mn = np.mean(rc); sd = np.std(rc, ddof=1)
    r['mean_price']=round(mn,2); r['std']=round(sd,2)
    z = (cur_p - mn)/sd if sd > 0 else 0; r['z_score']=round(z,4)
    az = abs(z)
    r['prob'] = {k:v for k,v in [(3,95),(2,85),(1.5,75),(1,65),(0.5,55)]}.get(min(k for k in [3,2,1.5,1,0.5] if az>=k), 50)
    bp = min(az*0.15, 0.5)
    if z < -0.5: r['pos']=round(bp*100,1); r['type']='买入'
    elif z > 0.5: r['pos']=round(-bp*100,1); r['type']='卖出'
    else: r['pos']=0; r['type']='观望'
    r['success']=True; return r

def get_sug(kelly, status):
    if kelly <= 0: return '不开仓'
    if status.get('below_ma20'): return '谨慎观察'
    if status.get('fish_body'): return '加仓'
    if status.get('fish_tail'): return '减仓'
    if kelly >= 0.3: return '可开仓'
    if kelly >= 0.15: return '轻仓'
    return '观望'

def fetch_ak(symbol, days=60):
    """akshare获取日K数据"""
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                start_date=start, end_date=end, adjust="qfq")
        if df.empty: return [],[],[]
        return df['日期'].tolist(), df['收盘'].tolist(), df['涨跌幅'].tolist()
    except Exception as e:
        print(f"  akshare err: {e}")
        return [],[],[]


def main():
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    print("="*60)
    print(f"  凯均日报 v2.0 — {today}")
    print("="*60)
    ensure_tables()
    
    results = []
    for idx, (name, code) in enumerate(HOLDINGS, 1):
        print(f"\n[{idx}/{len(HOLDINGS)}] {name}({code})")
        dates, closes, pcts = fetch_ak(code)
        if len(closes) < 20:
            print(f"  ⚠️ 数据不足{len(closes)}条，跳过")
            results.append((name,code,{'skip':True}))
            continue
        
        lp = closes[-1]; lpc = pcts[-1]; ld = dates[-1]
        
        # 均线
        ms = calc_ma_status(closes, lp)
        # 凯利
        b, p = calc_kelly_params(ms)
        kr = calc_kelly_ratio(b, p)
        sug = get_sug(kr, ms)
        notes = ' '.join(f"{k}={'Y' if v else 'N'}" for k,v in ms.items() if isinstance(v,bool))
        save_kelly(name, b, p, kr, sug, notes)
        # 均值回归
        mr = calc_mean_rev(closes)
        
        r = {'name':name,'code':code,'price':lp,'pct':lpc,'date':ld,
             'ms':ms,'b':b,'p':p,'kelly':kr,'sug':sug,'mr':mr}
        results.append(r)
        
        ma_ms = ' | '.join(f"{k}={'✅' if ms[k] else '❌'}" for k in ['ma1','ma5','ma10','ma20'])
        fish = "鱼身" if ms.get('fish_body') else ("鱼尾" if ms.get('fish_tail') else "-")
        print(f"  {ld} 收{lp:.2f} ({lpc:+.2f}%)")
        print(f"  {ma_ms} | {fish}")
        print(f"  凯利: b={b:.1f} p={p:.2f} → {sug}({kr*100:.0f}%)")
        if mr['success']: print(f"  均值回归: Z={mr['z_score']:.2f} 均值{mr['mean_price']:.2f} → {mr['type']} ({mr['prob']:.0f}%)")
    
    valid = [r for r in results if isinstance(r,dict) and not r.get('ms',{}).get('skip')]
    
    # ======== 生成报告 ========
    lines = []
    lines.append(f"# 📊 凯均日报 - {today[:10]}")
    lines.append(f"**生成时间：** {today}  |  **数据源：** akshare")
    lines.append(f"**股票数量：** {len(valid)} 只  |  **计算方法：** 凯利公式 f=(b·p-(1-p))/b + 均值回归Z-score")
    lines.append("")
    
    # 表1: 凯利
    lines.append("## 一、凯利公式仓位建议")
    lines.append("")
    lines.append("| 股票 | 价格 | 涨跌 | MA1 | MA5 | MA10 | MA20 | 鱼身/尾 | 凯利% | 操作建议 |")
    lines.append("|------|------|------|-----|-----|------|------|---------|-------|----------|")
    for r in sorted(valid, key=lambda x: x['kelly'], reverse=True):
        m = r['ms']; f = "鱼身" if m.get('fish_body') else ("🐟尾" if m.get('fish_tail') else "⚪")
        lines.append(f"| {r['name']}({r['code']}) | {r['price']:.2f} | {r['pct']:+.2f}% | "
                     f"{'✅' if m['ma1'] else '❌'} | {'✅' if m['ma5'] else '❌'} | "
                     f"{'✅' if m['ma10'] else '❌'} | {'✅' if m['ma20'] else '❌'} | {f} | "
                     f"{r['kelly']*100:.0f}% | **{r['sug']}** |")
    
    # 表2: 均值回归
    lines.append(""); lines.append("---"); lines.append("")
    lines.append("## 二、均值回归分析")
    lines.append("")
    lines.append("| 股票 | 当前价 | MA20均值 | Z-score | 标准差 | 回归概率 | 建议 |")
    lines.append("|------|--------|----------|---------|--------|---------|------|")
    for r in sorted(valid, key=lambda x: abs(x['mr']['z_score']) if x['mr']['success'] else 0, reverse=True):
        mr = r['mr']
        if not mr['success']: continue
        icon = "🟢" if mr['type']=='买入' else ("🔴" if mr['type']=='卖出' else "⚪")
        lines.append(f"| {r['name']}({r['code']}) | {mr['current']:.2f} | {mr['mean_price']:.2f} | "
                     f"{mr['z_score']:.2f} | {mr['std']:.2f} | {mr['prob']:.0f}% | {icon} {mr['type']} |")
    
    # 汇总
    lines.append(""); lines.append("---"); lines.append("")
    lines.append("## 三、操作汇总")
    lines.append("")
    
    can_open = [r for r in valid if r['sug'] in ('可开仓','加仓')]
    caution = [r for r in valid if r['sug'] in ('不开仓','谨慎观察','减仓')]
    hold = [r for r in valid if r['sug'] in ('轻仓','观望')]
    
    if can_open:
        lines.append(f"### 🟢 可开仓/加仓 ({len(can_open)})")
        for r in can_open:
            z = f" (Z={r['mr']['z_score']:.2f})" if r['mr']['success'] else ""
            lines.append(f"- **{r['name']}({r['code']})**: 凯利{r['kelly']*100:.0f}% → {r['sug']}{z}")
    if caution:
        lines.append(f"\n### 🔴 谨慎/减仓 ({len(caution)})")
        for r in caution:
            z = f" (Z={r['mr']['z_score']:.2f})" if r['mr']['success'] else ""
            lines.append(f"- **{r['name']}({r['code']})**: 凯利{r['kelly']*100:.0f}% → {r['sug']}{z}")
    if hold:
        lines.append(f"\n### ⚪ 持有/观望 ({len(hold)})")
        for r in hold:
            z = f" (Z={r['mr']['z_score']:.2f})" if r['mr']['success'] else ""
            lines.append(f"- **{r['name']}({r['code']})**: 凯利{r['kelly']*100:.0f}% → {r['sug']}{z}")
    
    # 均值回归预警
    extreme = [r for r in valid if r['mr']['success'] and abs(r['mr']['z_score']) >= 1.5]
    if extreme:
        lines.append("\n### ⚠️ 均值回归预警 (|Z|≥1.5)")
        for r in sorted(extreme, key=lambda x: abs(x['mr']['z_score']), reverse=True):
            mr = r['mr']
            d = "超卖(看涨)" if mr['z_score'] < -1.5 else "超买(看跌)"
            lines.append(f"- **{r['name']}({r['code']})**: Z={mr['z_score']:.2f}, {d}, 回归概率{mr['prob']:.0f}%")
    
    lines.append("\n---")
    lines.append(f"\n*报告生成：{today} | 数据：akshare | 算法：凯利公式+均值回归Z-score*")
    
    report = "\n".join(lines)
    
    # ======== 输出 ========
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fn = f"kelly_mean_daily_{datetime.now().strftime('%Y%m%d')}.md"
    fp = os.path.join(REPORTS_DIR, fn)
    with open(fp, 'w', encoding='utf-8') as f: f.write(report)
    print(f"\n✅ 报告已保存: {fp}")
    
    save_news(f"凯均日报-{today[:10]}", report)
    print("✅ 已写入数据库 news_info")
    
    print("\n" + "="*60)
    print(report)
    print("="*60)

if __name__ == "__main__":
    main()

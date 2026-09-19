#!/usr/bin/env python3
"""斯东克三组持仓多维分析 v2 —— 数据源: 腾讯行情(qt.gtimg.cn) + 腾讯K线(ifzq)"""
import math
import re
import sys
import time
import warnings

warnings.filterwarnings('ignore')
from collections import defaultdict

import numpy as np
import pandas as pd
import requests

FILE = sys.argv[1]
S = requests.Session()
S.headers.update({'User-Agent': 'Mozilla/5.0'})

def mk(code):
    return ('sh' if code[0] in '65' else ('bj' if code[0] == '9' or code[:2] in ('43','83','87','92') else 'sz')) + code

def parse(fp):
    txt = open(fp, encoding='utf-8').read()
    g = {}
    for name, body in re.findall(r'【(.*?)标签页】\n(.*?)(?=\n\n|共 \d+ 只)', txt, re.DOTALL):
        g[name] = {c: n.strip() for n, c in re.findall(r'([^、\n()（）]+)[（(](\d{6})[）)]', body)}
    return g

groups = parse(FILE)
res = defaultdict(list)
names = {}
for gname, d in groups.items():
    for c, n in d.items():
        res[c].append(gname); names[c] = n

codes = sorted(res)
print('组合规模:', {k: len(v) for k, v in groups.items()}, '| 去重合计:', len(codes))

# ---------- 快照 ----------
quotes = {}
for i in range(0, len(codes), 40):
    batch = codes[i:i+40]
    try:
        r = S.get('https://qt.gtimg.cn/q=' + ','.join(mk(c) for c in batch), timeout=15)
        r.encoding = 'gbk'
        for line in r.text.strip().split('\n'):
            if '="' not in line: continue
            f = line.split('="')[1].rstrip('";').split('~')
            if len(f) < 50: continue
            def num(idx):
                try: return float(f[idx])
                except: return np.nan
            quotes[f[2]] = dict(名称=f[1], 现价=num(3), 昨收=num(4), 涨跌幅=num(32),
                                最高=num(33), 最低=num(34), 成交额万=num(37), 换手率=num(38),
                                PE_TTM=num(39), 振幅=num(43), 流通市值亿=num(44), 总市值亿=num(45),
                                PB=num(46), 量比=num(49), 时间=f[30])
    except Exception as e:
        print('quote batch fail', i, str(e)[:60])
    time.sleep(0.3)
print('快照获取:', len(quotes), '/', len(codes), '| 数据时间:', list(quotes.values())[0]['时间'] if quotes else 'NA')
miss = [c for c in codes if c not in quotes]
if miss: print('未取到:', [(c, names[c]) for c in miss])

# ---------- K线技术面 ----------
def kline(code, n=260):
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mk(code)},day,,,{n},qfq'
    j = S.get(url, timeout=15).json()
    d = j['data'][mk(code)]
    arr = d.get('qfqday') or d.get('day')
    df = pd.DataFrame([x[:6] for x in arr], columns=['date','open','close','high','low','vol'])
    for c in ['open','close','high','low','vol']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

tech = {}
for idx, c in enumerate(codes):
    try:
        df = kline(c)
        if len(df) < 30: continue
        cl = df['close']; vol = df['vol']
        last = cl.iloc[-1]
        ma5, ma10, ma20, ma60 = [cl.rolling(w).mean().iloc[-1] if len(cl) >= w else np.nan for w in (5,10,20,60)]
        # RSI14
        diff = cl.diff(); up = diff.clip(lower=0).rolling(14).mean().iloc[-1]; dn = (-diff.clip(upper=0)).rolling(14).mean().iloc[-1]
        rsi = 100 - 100/(1+up/dn) if dn and dn > 0 else 100.0
        # MACD
        e12 = cl.ewm(span=12).mean(); e26 = cl.ewm(span=26).mean()
        dif = e12 - e26; dea = dif.ewm(span=9).mean(); macd = (dif - dea).iloc[-1] * 2
        hi60 = cl.tail(60).max(); lo60 = cl.tail(60).min()
        hi250 = cl.tail(250).max(); lo250 = cl.tail(250).min()
        tech[c] = dict(
            R5=round((last/cl.iloc[-6]-1)*100, 2) if len(cl) > 6 else np.nan,
            R20=round((last/cl.iloc[-21]-1)*100, 2) if len(cl) > 21 else np.nan,
            R60=round((last/cl.iloc[-61]-1)*100, 2) if len(cl) > 61 else np.nan,
            MA5=round(ma5,2), MA20=round(ma20,2), MA60=round(ma60,2) if not math.isnan(ma60) else np.nan,
            多头排列=int(last > ma5 > ma20 > ma60) if not math.isnan(ma60) else 0,
            距MA20=round((last/ma20-1)*100, 2) if ma20 else np.nan,
            距60日高=round((last/hi60-1)*100, 2),
            距年高=round((last/hi250-1)*100, 2),
            年内位置=round((last-lo250)/(hi250-lo250)*100, 1) if hi250 > lo250 else np.nan,
            RSI14=round(rsi, 1), MACD柱=round(macd, 3),
            量能比=round(vol.tail(5).mean()/vol.tail(20).mean(), 2) if vol.tail(20).mean() else np.nan,
            波动率20=round(cl.pct_change().tail(20).std()*100, 2),
            最新K日=df['date'].iloc[-1],
        )
    except Exception as e:
        print('kline fail', c, names[c], str(e)[:50])
    time.sleep(0.12)
print('K线获取:', len(tech), '/', len(codes))

rows = []
for c in codes:
    r = {'代码': c, '名称': names[c], '共振': len(res[c]), '组合': '+'.join(res[c])}
    r.update(quotes.get(c, {})); r.update(tech.get(c, {}))
    rows.append(r)
df = pd.DataFrame(rows)
df.to_csv('/Users/faronpan/Agent/stockyidong_project/src/sdk_full_20260804.csv', index=False, encoding='utf-8-sig')

pd.set_option('display.width', 400); pd.set_option('display.max_rows', 400); pd.set_option('display.max_columns', 60)
show = ['代码','名称','共振','现价','涨跌幅','换手率','量比','PE_TTM','PB','总市值亿','R5','R20','R60','距MA20','距60日高','年内位置','RSI14','MACD柱','量能比','多头排列']
print('\n===== 共振>=2 明细 (按共振/R20) =====')
print(df[df['共振']>=2].sort_values(['共振','R20'], ascending=False)[show].to_string(index=False))
print('\n===== 全部143只 R20 前30 =====')
print(df.sort_values('R20', ascending=False).head(30)[show].to_string(index=False))
print('\n===== 全部143只 R20 后15 =====')
print(df.sort_values('R20').head(15)[show].to_string(index=False))
print('\n===== 最新K线日期分布 =====')
print(df['最新K日'].value_counts().to_dict())

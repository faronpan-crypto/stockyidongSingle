#!/usr/bin/env python3
"""斯东克 三组持仓 多维度分析 (实盘数据: akshare)"""
import re
import sys
import warnings

warnings.filterwarnings('ignore')
from collections import defaultdict

import akshare as ak
import pandas as pd

FILE = sys.argv[1]

def parse(fp):
    txt = open(fp, encoding='utf-8').read()
    groups = {}
    for name, body in re.findall(r'【(.*?)标签页】\n(.*?)(?=\n\n|共 \d+ 只)', txt, re.DOTALL):
        pairs = re.findall(r'([^、\n()（）]+)[（(](\d{6})[）)]', body)
        groups[name] = {c: n.strip() for n, c in pairs}
    return groups

groups = parse(FILE)
for k, v in groups.items():
    print(f'{k}: {len(v)}')

# 共振度
res = defaultdict(list)
for g, d in groups.items():
    for c in d:
        res[c].append(g)

print('\n=== 共振统计 ===')
r3 = sorted([c for c in res if len(res[c]) == 3])
r2 = sorted([c for c in res if len(res[c]) == 2])
allnames = {}
for g, d in groups.items():
    allnames.update(d)
print('三组共振:', [(c, allnames[c]) for c in r3])
print('两组共振:', [(c, allnames[c], '+'.join(res[c])) for c in r2])
print('总去重:', len(res))

# 实时行情快照
print('\n=== 拉取全市场快照 ===')
spot = ak.stock_zh_a_spot_em()
spot['代码'] = spot['代码'].astype(str).str.zfill(6)
spot = spot.set_index('代码')
print('快照条数:', len(spot), '字段:', list(spot.columns))

cols = ['名称','最新价','涨跌幅','换手率','量比','市盈率-动态','市净率','总市值','5分钟涨跌','60日涨跌幅','年初至今涨跌幅','成交额']
have = [c for c in cols if c in spot.columns]

rows = []
for c in res:
    if c in spot.index:
        r = spot.loc[c, have].to_dict()
        r['代码'] = c
        r['共振'] = len(res[c])
        r['组合'] = '+'.join(res[c])
        rows.append(r)
    else:
        rows.append({'代码': c, '名称': allnames[c], '共振': len(res[c]), '组合': '+'.join(res[c]), '最新价': None})
df = pd.DataFrame(rows)
df.to_csv('/Users/faronpan/Agent/stockyidong_project/src/sdk_snapshot_20260804.csv', index=False, encoding='utf-8-sig')
print('缺失行情:', df[df['最新价'].isna()][['代码','名称']].to_dict('records'))

pd.set_option('display.width', 300)
pd.set_option('display.max_rows', 300)
print('\n=== 共振>=2 全量行情 ===')
sub = df[df['共振'] >= 2].sort_values(['共振','60日涨跌幅'], ascending=[False, False])
print(sub[['代码','名称','共振','组合','最新价','涨跌幅','换手率','量比','市盈率-动态','市净率','总市值','60日涨跌幅','年初至今涨跌幅']].to_string(index=False))

# 板块热度
print('\n=== 行业板块热度 Top20 / Bottom10 ===')
try:
    bi = ak.stock_board_industry_name_em()
    bi = bi.sort_values('涨跌幅', ascending=False)
    print(bi[['板块名称','涨跌幅','总市值','换手率','领涨股票']].head(20).to_string(index=False))
    print('...')
    print(bi[['板块名称','涨跌幅','换手率','领涨股票']].tail(10).to_string(index=False))
except Exception as e:
    print('板块数据失败:', e)

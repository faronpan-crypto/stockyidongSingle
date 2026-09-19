#!/usr/bin/env python3
"""
🚢 轮船策略选股系统 v1.0
结合巴菲特/芒格/段永平基本面思维 + 技术面热点
"""
import time
import warnings

warnings.filterwarnings('ignore')

from datetime import datetime

import akshare as ak
import pandas as pd

# 等待一下避免被限流
time.sleep(3)

def get_safe(fn, *args, **kwargs):
    """安全获取数据，失败返回空DataFrame"""
    for i in range(3):
        try:
            time.sleep(2)
            return fn(*args, **kwargs)
        except Exception as e:
            if i < 2:
                time.sleep(3)
            else:
                print(f"获取失败: {str(e)[:60]}")
                return pd.DataFrame()

print("=" * 60)
print("🚢 轮船策略选股系统 v1.0")
print("=" * 60)
print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 1. 大盘点睛
print("\n📊 ① 大盘点睛")
print("-" * 40)
try:
    idx = ak.stock_zh_index_spot_em()
    major = idx[idx['代码'].isin(['000001','399001','399006','000688'])]
    for _, row in major.iterrows():
        print(f"  {row['名称']:8} {row['最新价']:>8.2f}  {row['涨跌幅']:>6.2%}")
except Exception:
    print("  大盘API暂时不可用")

# 2. 热门板块
print("\n📈 ② 热门板块 TOP5")
print("-" * 40)
board = get_safe(ak.stock_board_concept_name_em)
if len(board) > 0:
    hot = board.nlargest(5, '涨跌幅')
    for i, (_, row) in enumerate(hot.iterrows(), 1):
        print(f"  {i}. {row['板块名称']:12} {row['涨跌幅']:>6.2%}  {row['领涨股票']}")

# 3. 涨停池
print("\n🔥 ③ 涨停池")
print("-" * 40)
zt = get_safe(ak.stock_zt_pool_em)
print(f"  今日涨停: {len(zt)} 只")
if len(zt) > 0:
    zt_sorted = zt.sort_values('涨跌幅', ascending=False).head(5)
    for _, row in zt_sorted.iterrows():
        name = row.get('名称', 'N/A')
        pct = row.get('涨跌幅', 0)
        code = row.get('代码', '')
        print(f"    {code} {name:<8} {pct:>6.2%}")

# 4. 强势股池
print("\n💪 ④ 强势股池")
print("-" * 40)
qs = get_safe(ak.stock_zt_pool_strong_em)
print(f"  强势股: {len(qs)} 只")
if len(qs) > 0:
    qs_top = qs.sort_values('涨跌幅', ascending=False).head(5)
    for _, row in qs_top.iterrows():
        name = row.get('名称', 'N/A')
        pct = row.get('涨跌幅', 0)
        code = row.get('代码', '')
        print(f"    {code} {name:<8} {pct:>6.2%}")

# 5. 轮船核心信号
print("\n🚢 ⑤ 轮船核心信号")
print("-" * 40)
signals = []
if len(zt) > 0:
    for _, row in zt.iterrows():
        code = row.get('代码', '')
        name = row.get('名称', 'N/A')
        pct = row.get('涨跌幅', 0)
        signals.append({'code': code, 'name': name, 'pct': pct, 'source': '涨停池'})

signals = sorted(signals, key=lambda x: x['pct'], reverse=True)[:10]
if signals:
    print("  重点关注:")
    for s in signals[:5]:
        print(f"    {s['code']} {s['name']:<8} {s['pct']:>6.2%} [{s['source']}]")
else:
    print("  今日信号清淡")

print("\n" + "=" * 60)
print("✅ 轮船策略运行完成")
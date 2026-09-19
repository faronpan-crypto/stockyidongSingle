#!/usr/bin/env python3
"""
🚀 「坐电梯」自动选股系统
每天收盘后(15:10)自动运行，生成7策略筛选+共振分析
数据源: akshare (东方财富)
"""
import sys
from datetime import datetime, timedelta

import akshare as ak


def get_today_str():
    """获取今天日期字符串"""
    now = datetime.now()
    # 如果在15:00之前，用前一个交易日（简单处理，工作日回退）
    if now.hour < 15 and now.weekday() < 5:
        # 还没收盘，用昨天
        target = now - timedelta(days=1)
        while target.weekday() >= 5:
            target -= timedelta(days=1)
        return target.strftime('%Y%m%d')
    # 已收盘
    if now.weekday() >= 5:
        # 周末，用周五
        target = now - timedelta(days=now.weekday() - 4)
        return target.strftime('%Y%m%d')
    return now.strftime('%Y%m%d')

def run_screening(date_str=None):
    if not date_str:
        date_str = get_today_str()
    
    now = datetime.now()
    report_time = now.strftime('%Y-%m-%d %H:%M')
    
    lines = []
    lines.append("=" * 70)
    lines.append("🚀 「坐电梯」选股系统 — 自动运行")
    lines.append(f"   日期: {date_str} | 生成时间: {report_time}")
    lines.append("=" * 70)
    
    # === 基础数据获取 ===
    lines.append("\n📡 获取基础数据...")
    try:
        zt = ak.stock_zt_pool_em(date=date_str)
        zbgc = ak.stock_zt_pool_zbgc_em(date=date_str)
        strong = ak.stock_zt_pool_strong_em(date=date_str)
        prev_zt = ak.stock_zt_pool_previous_em(date=date_str)
    except Exception as e:
        lines.append(f"❌ 获取数据失败: {e}")
        return "\n".join(lines)
    
    lines.append(f"  涨停: {len(zt)}只 | 炸板: {len(zbgc)}只 | 强势: {len(strong)}只 | 昨日涨停: {len(prev_zt)}只")
    
    # === 7大策略 ===
    strategies = {}
    
    # 策略1: 回封强势
    s1 = zt[(zt['炸板次数'] <= 2) & (zt['封板资金'] > 50000000) & (zt['换手率'] < 25)].sort_values('封板资金', ascending=False)
    strategies['回封强势'] = s1
    
    # 策略2: 连板接力
    s2 = zt[(zt['连板数'] >= 2) & (zt['封板资金'] > 30000000)].sort_values('连板数', ascending=False)
    strategies['连板接力'] = s2
    
    # 策略3: 炸板低吸(反包)
    s3 = zbgc[(zbgc['涨跌幅'] > 5) & (zbgc['换手率'] > 10) & (zbgc['成交额'] > 300000000)].sort_values('涨跌幅', ascending=False)
    strategies['炸板低吸(反包)'] = s3
    
    # 策略4: 昨板今强(二波)
    s4 = prev_zt[(prev_zt['涨跌幅'] > 3)].sort_values('涨跌幅', ascending=False)
    strategies['昨板今强(二波)'] = s4
    
    # 策略5: 高换手异动
    s5 = strong[(strong['换手率'] > 15) & (strong['成交额'] > 500000000) & (strong['涨跌幅'] > 3)].sort_values('换手率', ascending=False)
    strategies['高换手异动'] = s5
    
    # 策略6: 首板优选(1进2候选)
    s6 = zt[(zt['连板数'] == 1) & (zt['封板资金'] > 50000000) & (zt['换手率'] > 3) & (zt['换手率'] < 25)].sort_values('首次封板时间')
    strategies['首板优选(1进2)'] = s6
    
    # 策略7: 龙头反包
    s7 = strong[(strong['涨停统计'].str.contains('/', na=False)) & (strong['涨跌幅'] > 0) & (strong['换手率'] > 10)].sort_values('涨跌幅', ascending=False)
    strategies['龙头反包'] = s7
    
    # === 输出各策略 ===
    for name, df in strategies.items():
        lines.append(f"\n{'─'*70}")
        lines.append(f"🎯 策略: {name} ({len(df)}只)")
        lines.append(f"{'─'*70}")
        
        if len(df) == 0:
            lines.append("  无符合条件的个股")
            continue
        
        for i, (_, row) in enumerate(df.iterrows(), 1):
            code = row.get('代码', '')
            name_s = row.get('名称', '')
            chg = row.get('涨跌幅', 0)
            amt = row.get('成交额', 0)
            turn = row.get('换手率', 0)
            fb = row.get('封板资金', 0) if '封板资金' in row.index else 0
            lb = row.get('连板数', 0) if '连板数' in row.index else 0
            zbt = row.get('首次封板时间', '') if '首次封板时间' in row.index else ''
            zbc = row.get('炸板次数', 0) if '炸板次数' in row.index else 0
            industry = row.get('所属行业', '')
            reason = row.get('入选理由', '') if '入选理由' in row.index else ''
            
            parts = [f"  {i}. {name_s}({code}) | 涨幅:{chg:.1f}% | 换手:{turn:.1f}% | 成交:{amt/10000:.0f}万"]
            if fb > 0:
                parts.append(f"封板:{fb/10000:.0f}万")
            if lb > 0:
                parts.append(f"{lb}板")
            if zbc > 0:
                parts.append(f"炸板{zbc}次")
            if reason:
                parts.append(reason)
            lines.append(" | ".join(parts))
    
    # === 共振分析 ===
    lines.append(f"\n{'='*70}")
    lines.append("⚡ 多策略共振票（出现在2个以上策略中）")
    lines.append(f"{'='*70}")
    
    all_codes = {}
    for name, df in strategies.items():
        for _, row in df.iterrows():
            code = row.get('代码', '')
            if code not in all_codes:
                all_codes[code] = {'strategies': [], 'name': row.get('名称', '')}
            all_codes[code]['strategies'].append(name)
    
    resonance = {c: v for c, v in all_codes.items() if len(v['strategies']) >= 2}
    
    if resonance:
        # 按策略数量降序
        for code, info in sorted(resonance.items(), key=lambda x: -len(x[1]['strategies']))[:15]:
            strat_str = ', '.join(info['strategies'])
            lines.append(f"  ⚡ {info['name']}({code}): [{len(info['strategies'])}策略] {strat_str}")
    else:
        lines.append("  今日无多策略共振票")
    
    # === 风险提示 ===
    lines.append(f"\n{'='*70}")
    lines.append("⚠️ 风险提示")
    lines.append(f"{'='*70}")
    lines.append("  • 高连板股(≥3板)注意分歧风险")
    lines.append("  • 炸板次数≥3的票封板不稳定")
    lines.append("  • 换手率>30%的票筹码松动")
    lines.append("  • 本系统仅做数据筛选，不构成投资建议")
    
    return "\n".join(lines)

if __name__ == '__main__':
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    print(run_screening(date_str))

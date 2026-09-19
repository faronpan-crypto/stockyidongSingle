#!/usr/bin/env python3
"""
holdings_analyzer.py — 斯东克持仓诊断分析引擎
读取 stockyidong_export.py 导出的持仓数据，
结合 auto_screener.py 的选股策略结果，进行多维度诊断评分。

用法：
  python3 holdings_analyzer.py                    # 分析最新导出数据
  python3 holdings_analyzer.py --date 20260505    # 指定日期
  python3 holdings_analyzer.py --export-report    # 保存完整报告
"""

import argparse
import os
import re
from datetime import datetime
from pathlib import Path

# ============== 配置 ==============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_CONFIG  = os.path.join(SCRIPT_DIR, "config", "ai_config.json")
EXPORT_DIR  = SCRIPT_DIR   # 与 export 脚本同目录

# ============== 工具函数 ==============

def parse_stock(text: str):
    """从 'XX股份(000000)' 提取名称和代码"""
    m = re.search(r'([^(（]+)\(([^)]+)\)', text)
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, None)

def load_export(date_str=None):
    """加载最新或指定日期的导出文件"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    pattern = f"stockyidong_{date_str}_*.txt"
    files = sorted(Path(EXPORT_DIR).glob(pattern), reverse=True)
    if not files:
        return None
    with open(files[0], encoding='utf-8') as f:
        return files[0].name, f.read()

def load_screener(date_str=None):
    """加载最新选股结果（从 auto_screener.py 运行时获取的数据）"""
    # 从 logs 或最新输出缓存中读取
    log_dir = os.path.join(SCRIPT_DIR, "logs")
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    pattern = f"*{date_str}*.log"
    log_files = sorted(Path(log_dir).glob(pattern), reverse=True)
    
    # 也可从今日市场数据缓存读取
    # 实际运行时，cron 会同时触发 auto_screener 输出
    # 此处设计为接受参数或读取缓存

def analyze_holdings(content: str, screener_data=None):
    """
    核心分析逻辑
    content: 持仓导出文本
    screener_data: 选股策略数据（若有）
    返回结构化结果
    """
    result = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'tabs': {},
        'all_stocks': [],
        'analyzed': [],
        'summary': {}
    }
    
    # 解析各标签页
    current_tab = None
    for line in content.split('\n'):
        if line.startswith('【') and line.endswith('】'):
            tab = line.strip('【】')
            if tab in ['龙头股', '15分钟', '同花顺']:
                current_tab = tab
                result['tabs'][tab] = {'stocks': [], 'count': 0}
        elif line.startswith('共 ') and line.endswith(' 只'):
            if current_tab:
                result['tabs'][current_tab]['count'] = int(re.search(r'共 (\d+)', line).group(1))
        elif '、' in line and '(' in line and '无' not in line:
            stocks = [s.strip() for s in line.split('、') if '(' in s]
            if current_tab and stocks:
                for s in stocks:
                    name, code = parse_stock(s)
                    if name:
                        result['all_stocks'].append({'name': name, 'code': code, 'tab': current_tab})
    
    # 去重（同股跨标签出现）
    unique = {}
    for s in result['all_stocks']:
        key = s['code']
        if key not in unique:
            unique[key] = s
    
    result['unique_stocks'] = list(unique.values())
    result['summary']['total_unique'] = len(unique)
    
    return result

def score_stocks(stocks, screener=None):
    """
    多维度评分
    screener: 选股策略列表（来自 auto_screener 的各策略 TOP 列表）
    
    评分维度：
    - 策略共振度（0-30分）：出现在多少策略中
    - 连板加分（0-20分）：是否为2板+、3板+
    - 封板强度（0-20分）：封单/成交比例
    - 板块联动（0-15分）：所属板块今日表现
    - 换手健康（0-15分）：5-25% 为健康区间
    """
    scored = []
    
    # 解析 screener 数据（格式：名称(代码) | 涨幅 | 换手 | 成交 | 封板 | N板）
    strategy_stocks = {}
    if screener:
        # 从 screener 输出解析各策略的股票
        for line in screener.split('\n'):
            if '|' in line and '(' in line:
                name, code = parse_stock(line)
                if name:
                    # 解析策略标签（从行首找）
                    for tag in ['回封强势', '连板接力', '炸板低吸', '昨板今强', '高换手异动', '首板优选', '龙头反包']:
                        if tag in line:
                            if tag not in strategy_stocks:
                                strategy_stocks[tag] = {}
                            strategy_stocks[tag][code] = {'name': name, 'line': line}
    
    for stock in stocks:
        code = stock['code']
        name = stock['name']
        
        score = 0
        reasons = []
        
        # 策略共振度
        resonance = sum(1 for tag, data in strategy_stocks.items() if code in data)
        resonance_score = min(30, resonance * 8)
        score += resonance_score
        if resonance > 0:
            strategies = [tag for tag, data in strategy_stocks.items() if code in data]
            reasons.append(f'共振{resonance}策略: {"/".join(strategies[:3])}')
        
        # 从 screener 数据中找详细指标
        line_data = None
        for tag, data in strategy_stocks.items():
            if code in data:
                line_data = data[code]['line']
                break
        
        # 连板加分（从行中解析）
        ban_match = re.search(r'(\d+)板', line_data or '')
        if ban_match:
            ban = int(ban_match.group(1))
            if ban >= 2:
                score += min(20, ban * 7)
                reasons.append(f'连板{ban}板')
        
        # 封板强度（从行中解析封板金额和成交金额）
        seal_match = re.search(r'封板:(\d+)万', line_data or '')
        vol_match  = re.search(r'成交:(\d+)万', line_data or '')
        if seal_match and vol_match:
            seal = float(seal_match.group(1))
            vol  = float(vol_match.group(1))
            ratio = (seal / vol * 100) if vol > 0 else 0
            score += min(20, ratio * 2)
            if ratio > 20:
                reasons.append(f'封板强({ratio:.0f}%)')
        
        # 换手率健康
        turnover_match = re.search(r'换手:([\d.]+)%', line_data or '')
        if turnover_match:
            turnover = float(turnover_match.group(1))
            if 5 <= turnover <= 25:
                score += 15
                reasons.append(f'换手健康({turnover}%)')
            elif turnover > 30:
                score -= 5
                reasons.append('⚠️换手过高')
        
        # 炸板风险
        if '炸板' in (line_data or ''):
            zb_match = re.search(r'炸板(\d+)次', line_data or '')
            if zb_match and int(zb_match.group(1)) >= 3:
                score -= 10
                reasons.append('⚠️炸板风险')
        
        scored.append({
            'name': name,
            'code': code,
            'tab': stock['tab'],
            'score': round(score, 1),
            'reasons': reasons
        })
    
    # 按评分降序
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored

def format_report(result, scored):
    """生成 Markdown 格式报告"""
    lines = []
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    lines.append(f"📊 **持仓诊断报告 {date_str} — 斯东克**")
    lines.append("")
    lines.append("**【总体概况】**")
    unique_count = result['summary'].get('total_unique', len(result.get('unique_stocks', [])))
    lines.append(f"- 去重后持仓：{unique_count} 只")
    
    # 各标签页统计
    for tab, data in result.get('tabs', {}).items():
        count = data.get('count', 0)
        lines.append(f"- {tab}：{count} 只")
    
    lines.append("")
    lines.append("**【TOP15 推荐关注】**（综合评分排序）")
    
    top15 = scored[:15]
    if not top15:
        lines.append("*今日无评分数据，请确认导出了最新持仓数据*")
    else:
        medals = ['🥇', '🥈', '🥉'] + [f'{i+4}.' for i in range(11)]
        for i, s in enumerate(top15):
            medal = medals[i] if i < 3 else f'{i+1}.'
            reasons_str = ' | '.join(s['reasons'][:2]) if s['reasons'] else ''
            lines.append(f"{medal} **{s['name']}({s['code']})** | 评分:{s['score']} | {reasons_str}")
    
    lines.append("")
    lines.append("**【风险提示】**")
    # 找出低分/炸板风险
    risky = [s for s in scored if s['score'] < 20 or any('⚠️' in r for r in s['reasons'])]
    if risky:
        for s in risky[:5]:
            lines.append(f"⚠️ {s['name']}({s['code']})：{', '.join([r for r in s['reasons'] if '⚠️' in r])}")
    else:
        lines.append("暂无明显风险提示")
    
    lines.append("")
    lines.append("**【明日操作建议】**")
    # 从 top 中提取方向
    hot_stocks = scored[:5]
    if hot_stocks:
        lines.append(f"1. 重点关注：**{hot_stocks[0]['name']}**（评分最高，共振强）")
        if len(hot_stocks) >= 3:
            names = '、'.join([s['name'] for s in hot_stocks[:3]])
            lines.append(f"2. 关注共振标的：{names}")
        lines.append("3. 方向：关注AI算力/半导体、有色金属等主线")
    
    lines.append("")
    lines.append("⚠️ *本报告仅供参考，不构成投资建议。数据来源：StockYiDong + 斯东克多策略系统*")
    
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='斯东克持仓诊断分析')
    parser.add_argument('--date', default=None, help='指定日期 YYYYMMDD')
    parser.add_argument('--screener', default=None, help='选股数据文件路径')
    parser.add_argument('--export-report', action='store_true', help='保存完整报告')
    args = parser.parse_args()
    
    date_str = args.date or datetime.now().strftime('%Y%m%d')
    
    # 读取持仓导出
    export = load_export(date_str)
    if not export:
        print("⚠️ 未找到持仓导出文件，请先运行 stockyidong_export.py")
        return
    
    filename, content = export
    print(f"[斯东克] 读取持仓: {filename}")
    
    # 读取选股数据
    screener_data = None
    if args.screener:
        with open(args.screener, encoding='utf-8') as f:
            screener_data = f.read()
    
    # 分析
    result = analyze_holdings(content, screener_data)
    scored = score_stocks(result.get('unique_stocks', []), screener_data)
    
    # 输出
    report = format_report(result, scored)
    print()
    print(report)
    
    # 保存
    if args.export_report:
        out_path = os.path.join(EXPORT_DIR, f"holdings_report_{date_str}.md")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n[已保存] {out_path}")

if __name__ == '__main__':
    main()
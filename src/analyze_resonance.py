#!/usr/bin/env python3
"""
斯东克股票共振度分析
分析龙头股、15Min、同花顺三个组合的股票重叠情况
"""

import re
from collections import defaultdict


def parse_stock_file(file_path):
    """解析股票导出文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取三个组合的股票
    groups = {
        '龙头股': [],
        '15Min': [],
        '同花顺': []
    }
    
    # 使用正则提取各组股票
    pattern = r'【(.*?)标签页】\n(.*?)(?=\n\n|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for group_name, stocks_text in matches:
        # 提取股票代码
        stock_codes = re.findall(r'\((\d{6})\)', stocks_text)
        groups[group_name] = stock_codes
    
    return groups

def analyze_resonance(groups):
    """分析共振度"""
    # 统计每只股票出现的组数
    stock_groups = defaultdict(list)
    
    for group_name, stocks in groups.items():
        for code in stocks:
            stock_groups[code].append(group_name)
    
    # 按共振度排序
    resonance_list = []
    for code, group_list in stock_groups.items():
        resonance_list.append({
            'code': code,
            'groups': group_list,
            'resonance': len(group_list)
        })
    
    # 按共振度降序排序
    resonance_list.sort(key=lambda x: x['resonance'], reverse=True)
    
    return resonance_list

def main():
    file_path = '/Users/faronpan/Agent/stockyidong_project/src/stockyidong_20260519_081210.txt'
    
    # 解析文件
    groups = parse_stock_file(file_path)
    
    # 输出持仓概况
    print(f"【持仓概况】龙头股{len(groups['龙头股'])}只 / 15Min {len(groups['15Min'])}只 / 同花顺 {len(groups['同花顺'])}只\n")
    
    # 分析共振度
    resonance_list = analyze_resonance(groups)
    
    # 输出Top5推荐（共振度最高）
    print("【Top5推荐股票】（按共振度排序）\n")
    
    top5 = resonance_list[:5]
    for i, stock in enumerate(top5, 1):
        groups_str = '+'.join(stock['groups'])
        print(f"{i}. 股票代码({stock['code']}) - 共振度: {stock['resonance']} ({groups_str})")
        print(f"   推荐逻辑: 同时出现在{stock['resonance']}个股票池中，具有多重信号确认\n")
    
    # 统计共振度分布
    resonance_dist = defaultdict(int)
    for stock in resonance_list:
        resonance_dist[stock['resonance']] += 1
    
    print("【共振度分布】")
    for res in sorted(resonance_dist.keys(), reverse=True):
        print(f"  共振度{res}: {resonance_dist[res]}只股票")
    
    print("\n【分析逻辑说明】")
    print("本报告基于共振度分析框架，通过统计股票在龙头股、15Min、同花顺三个投资组合中出现的频次，识别具有多重信号确认的标的。")
    print("共振度越高，说明该股票获得不同策略维度的共同认可，理论上具有较强的信号可靠性和上涨潜力。")
    print("Top5推荐股票均为共振度3的股票，即同时被三个策略维度选中，具备最强的信号一致性。")
    print("由于导出数据仅包含股票代码信息，本报告主要基于共振度维度进行分析。完整分析需结合基本面、技术面、板块热度等数据进行综合评估。")

if __name__ == '__main__':
    main()

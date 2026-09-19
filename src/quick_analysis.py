#!/usr/bin/env python3
import re
from collections import Counter
from datetime import datetime

# Read the exported file
with open('/Users/faronpan/Agent/stockyidong_project/src/stockyidong_20260602_143013.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Parse stocks by section
sections = {'龙头股': [], '15Min': [], '同花顺': []}
current_section = None

for line in content.split('\n'):
    if '【龙头股标签页】' in line:
        current_section = '龙头股'
        continue
    elif '【15Min标签页】' in line:
        current_section = '15Min'
        continue
    elif '【同花顺标签页】' in line:
        current_section = '同花顺'
        continue
    elif line.strip().startswith('共'):
        current_section = None
        continue
    
    if current_section and line.strip():
        stocks = re.findall(r'([^\s、()]+)\((\d{6})\)', line)
        for name, code in stocks:
            sections[current_section].append({'name': name, 'code': code})

# Calculate resonance
all_stocks = {}
for category, stocks in sections.items():
    for stock in stocks:
        key = f"{stock['name']}({stock['code']})"
        if key not in all_stocks:
            all_stocks[key] = {'name': stock['name'], 'code': stock['code'], 'categories': []}
        all_stocks[key]['categories'].append(category)

for stock in all_stocks.values():
    stock['resonance_score'] = len(stock['categories'])

# Sector analysis
sector_keywords = {
    '半导体芯片': ['芯片', '半导体', '集成电路', '晶圆', '兆易', '长电', '通富', '华天', '晶方', '中芯', '澜起', '海光', '利扬', '江波龙'],
    'AI算力': ['中际旭创', '新易盛', '天孚通信', '光迅科技', '华工科技', '工业富联', '海光'],
    '5G通信': ['通信', '中际', '新易盛', '天孚', '光迅'],
    '光伏新能源': ['光伏', '协鑫', '阳光', '双良'],
    '电力电网': ['电力', '华电', '京能', '大唐'],
    '新材料': ['材料', '巨石', '中材', '天通', '国际复材'],
    'PCB': ['沪电', '深南', '宏和'],
    '锂电池': ['锂业', '多氟多', '天赐'],
    '医药医疗': ['医药', '医疗', '美诺华'],
    '白酒消费': ['茅台', '泸州老窖'],
}

sector_count = Counter()
stock_sectors = {}

for category, stocks in sections.items():
    for stock in stocks:
        key = f"{stock['name']}({stock['code']})"
        if key not in stock_sectors:
            stock_sectors[key] = []
        
        matched = set()
        for sector, keywords in sector_keywords.items():
            if any(kw in stock['name'] for kw in keywords):
                matched.add(sector)
                sector_count[sector] += 1
        
        for sector in matched:
            if sector not in stock_sectors[key]:
                stock_sectors[key].append(sector)

# Comprehensive scoring
sector_weights = {
    '半导体芯片': 10, 'AI算力': 10, '5G通信': 8, '光伏新能源': 7,
    '锂电池': 7, '电力电网': 5, '新材料': 5, 'PCB': 6, '医药医疗': 4
}

for stock in all_stocks.values():
    score = stock['resonance_score'] * 10
    key = f"{stock['name']}({stock['code']})"
    if key in stock_sectors:
        for sector in stock_sectors[key]:
            score += sector_weights.get(sector, 3)
    if '龙头股' in stock['categories']:
        score += 15
    stock['total_score'] = score
    stock['sectors'] = stock_sectors.get(key, [])

# Sort by score
sorted_stocks = sorted(all_stocks.values(), key=lambda x: x['total_score'], reverse=True)

# Generate report
report = []
report.append("=" * 60)
report.append("【斯东克股票分析报告】")
report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report.append("=" * 60)
report.append("")
report.append("【持仓概况】")
report.append(f"龙头股: {len(sections['龙头股'])} 只")
report.append(f"15Min: {len(sections['15Min'])} 只")
report.append(f"同花顺: {len(sections['同花顺'])} 只")
report.append("")
report.append("【板块热度TOP5】")
for i, (sector, count) in enumerate(sector_count.most_common(5), 1):
    report.append(f"{i}. {sector}: {count} 只股票")
report.append("")
report.append("【Top5推荐股票】")
for i, stock in enumerate(sorted_stocks[:5], 1):
    categories_str = '+'.join(stock['categories'])
    sectors_str = ', '.join(stock['sectors']) if stock['sectors'] else '未分类'
    report.append(f"{i}. {stock['name']}({stock['code']})")
    report.append(f"   综合评分: {stock['total_score']}")
    report.append(f"   出现组别: {categories_str}")
    report.append(f"   所属板块: {sectors_str}")
    logic = []
    if stock['resonance_score'] >= 3:
        logic.append("三组合共振")
    elif stock['resonance_score'] == 2:
        logic.append("两组合共振")
    if '龙头股' in stock['categories']:
        logic.append("龙头股标签")
    if stock['sectors']:
        logic.append(f"属于热门板块({sectors_str})")
    report.append(' + '.join(logic) if logic else "综合表现良好")
    report.append("")
report.append("【分析逻辑说明】")
report.append("本分析基于多维度评分体系:")
report.append("1. 共振度(30分): 股票在龙头股/15Min/同花顺三组出现次数")
report.append("2. 板块热度(3-10分): 半导体/AI算力等高景气赛道加分更多")
report.append("3. 龙头标签(15分): 入选龙头股标签说明具备领涨特质")
report.append("推荐逻辑: 优先选择多组共振+热门板块+龙头标签的股票")
report.append("")
report.append("=" * 60)
report.append("报告结束")
report.append("=" * 60)

report_content = '\n'.join(report)

# Write to file
output_file = '/Users/faronpan/Agent/stockyidong_project/src/斯东克股票分析报告_20260602_143013.txt'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(report_content)

print(report_content)

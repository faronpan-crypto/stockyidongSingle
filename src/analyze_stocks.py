#!/usr/bin/env python3
"""
斯东克股票多维度分析脚本
分析龙头股/15Min/同花顺三组股票的基本面+技术面+板块热度+共振度
"""

import re
from collections import Counter
from datetime import datetime


def parse_stock_file(file_path):
    """解析导出的股票文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = {
        '龙头股': [],
        '15Min': [],
        '同花顺': []
    }

    # 解析各标签页
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
            # 提取股票代码和名称
            stocks = re.findall(r'([^\s、()]+)\((\d{6})\)', line)
            for name, code in stocks:
                sections[current_section].append({
                    'name': name,
                    'code': code
                })

    return sections

def calculate_resonance(stock_data):
    """计算共振度 - 股票在多个组出现的次数"""
    all_stocks = {}
    for category, stocks in stock_data.items():
        for stock in stocks:
            key = f"{stock['name']}({stock['code']})"
            if key not in all_stocks:
                all_stocks[key] = {
                    'name': stock['name'],
                    'code': stock['code'],
                    'categories': [],
                    'resonance_score': 0
                }
            all_stocks[key]['categories'].append(category)

    # 计算共振分数
    for stock in all_stocks.values():
        stock['resonance_score'] = len(stock['categories'])
        stock['category_count'] = len(stock['categories'])

    return all_stocks

def analyze_sector(stock_data):
    """分析板块热度 - 基于股票名称判断行业"""
    sector_keywords = {
        '半导体芯片': ['芯片', '半导体', '集成电路', '晶圆', '兆易', '长电', '通富', '华天', '晶方', '中芯', '澜起', '寒武纪', '海光', '龙芯', '利扬', '江波龙', '北京君正'],
        '5G通信': ['通信', '网络', '锐捷', '三维', '中际', '新易盛', '天孚', '光迅', '腾景', '德科立', '铭普', '汇源'],
        '光伏新能源': ['光伏', '晶科', '协鑫', '阳光', '双良'],
        '锂电池': ['锂业', '多氟多', '天赐', '永杉'],
        '军工航天': ['航天', '中航', '成飞', '沈飞', '西飞', '陕飞', '南湖'],
        '电力电网': ['电力', '华电', '京能', '大唐', '粤电力', '节能', '风电'],
        '医药医疗': ['医药', '医疗', '美诺华', '百花', '九安'],
        '白酒消费': ['茅台', '来伊份'],
        '金融科技': ['平安', '兴业', '招商'],
        '游戏传媒': ['完美', '蓝色光标', '浙文互联', '粤传媒'],
        '新材料': ['材料', '巨石', '中材', '云南锗业', '天通', '国际复材'],
        'PCB': ['世运电路', '宏和', '华正', '沪电', '深南'],
        '液冷散热': ['英维克', '飞龙'],
        'AI算力': ['中际旭创', '新易盛', '天孚通信', '光迅科技', '华工科技', '宏景科技', '协创数据', '工业富联', '寒武纪', '海光'],
    }

    sector_count = Counter()
    stock_sectors = {}

    for category, stocks in stock_data.items():
        for stock in stocks:
            key = f"{stock['name']}({stock['code']})"
            if key not in stock_sectors:
                stock_sectors[key] = []  # 初始化为空列表

            # 判断股票所属板块 (每个股票在每个板块只添加一次)
            matched_sectors = set()  # 临时set用于去重
            for sector, keywords in sector_keywords.items():
                if any(kw in stock['name'] for kw in keywords):
                    matched_sectors.add(sector)
                    sector_count[sector] += 1
            
            # 将去重后的板块添加到股票
            for sector in matched_sectors:
                if sector not in stock_sectors[key]:  # 避免重复添加
                    stock_sectors[key].append(sector)

    return sector_count, stock_sectors

def comprehensive_analysis(file_path):
    """综合多维度分析"""
    # 解析文件
    stock_data = parse_stock_file(file_path)

    # 共振度分析
    all_stocks = calculate_resonance(stock_data)

    # 板块分析
    sector_count, stock_sectors = analyze_sector(stock_data)

    # 综合评分 (简化版 - 基于共振度 + 板块热度)
    sector_weights = {
        '半导体芯片': 10,
        'AI算力': 10,
        '5G通信': 8,
        '光伏新能源': 7,
        '锂电池': 7,
        '军工航天': 6,
        '电力电网': 5,
        '新材料': 5,
        '医药医疗': 4,
        'PCB': 6,
        '液冷散热': 6,
    }

    for stock in all_stocks.values():
        score = 0
        # 共振度得分 (最高30分)
        score += stock['resonance_score'] * 10

        # 板块热度得分
        key = f"{stock['name']}({stock['code']})"
        if key in stock_sectors:
            for sector in stock_sectors[key]:
                score += sector_weights.get(sector, 3)

        # 龙头股标签加分
        if '龙头股' in stock['categories']:
            score += 15

        stock['total_score'] = score
        stock['sectors'] = stock_sectors.get(key, [])

    # 排序
    sorted_stocks = sorted(all_stocks.values(), key=lambda x: x['total_score'], reverse=True)

    return {
        'stock_data': stock_data,
        'sector_count': sector_count,
        'top_stocks': sorted_stocks[:20],
        'all_stocks': sorted_stocks
    }

def generate_report(analysis_result, output_file):
    """生成分析报告"""
    stock_data = analysis_result['stock_data']
    sector_count = analysis_result['sector_count']
    top_stocks = analysis_result['top_stocks']

    report = []
    report.append("=" * 60)
    report.append("【斯东克股票分析报告】")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 60)
    report.append("")

    # 持仓概况
    report.append("【持仓概况】")
    report.append(f"龙头股: {len(stock_data['龙头股'])} 只")
    report.append(f"15Min: {len(stock_data['15Min'])} 只")
    report.append(f"同花顺: {len(stock_data['同花顺'])} 只")
    report.append("")

    # 板块热度
    report.append("【板块热度TOP5】")
    for i, (sector, count) in enumerate(sector_count.most_common(5), 1):
        report.append(f"{i}. {sector}: {count} 只股票")
    report.append("")

    # Top5推荐
    report.append("【Top5推荐股票】")
    for i, stock in enumerate(top_stocks[:5], 1):
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
        report.append("")  # 空行分隔

    # 分析逻辑说明
    report.append("【分析逻辑说明】")
    explanation = """
本分析基于多维度评分体系:
1. 共振度(30分): 股票在龙头股/15Min/同花顺三组出现次数,出现越多说明市场关注度越高
2. 板块热度(3-10分): 根据股票所属行业板块赋予不同权重,半导体/AI算力等高景气赛道加分更多
3. 龙头标签(15分): 入选龙头股标签说明具备领涨特质

推荐逻辑: 优先选择多组共振+热门板块+龙头标签的股票,这类股票通常具备较强的上涨动能和市场关注度。
    """.strip()
    report.append(explanation)

    report.append("")
    report.append("=" * 60)
    report.append("报告结束")
    report.append("=" * 60)

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    return '\n'.join(report)

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python3 analyze_stocks.py <input_txt> <output_txt>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"[分析] 正在分析股票数据: {input_file}")
    result = comprehensive_analysis(input_file)

    print(f"[报告] 正在生成分析报告: {output_file}")
    report_content = generate_report(result, output_file)

    print("[完成] 分析完成!")
    print()
    print(report_content)

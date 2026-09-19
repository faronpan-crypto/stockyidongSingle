#!/usr/bin/env python3
"""
extract_news_stocks.py — 提取最近N天资讯中的股票

功能：
1. 从数据库读取最近N天的资讯
2. 提取股票代码（六位代码）
3. 尝试获取股票名称
4. 保存到文件（TXT和CSV格式）

用法：
  python3 extract_news_stocks.py              # 提取最近10天
  python3 extract_news_stocks.py --ndays 5   # 提取最近5天
  python3 extract_news_stocks.py --export    # 保存 to 文件
"""

import argparse
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime

# 数据库路径
DB_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "stock_analysis.db"))

def extract_stock_codes_from_news(ndays=10):
    """
    从数据库读取最近ndays天的资讯，提取股票代码
    返回：[('code', count, 'name'), ...] 按出现次数降序
    """
    print(f"[1/3] 读取最近 {ndays} 天资讯...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"✗ 读取数据库失败: {e}")
        return []
    
    if not rows:
        print("✗ news_info 表为空")
        return []
    
    print(f"✓ 从数据库读取到 {len(rows)} 条资讯记录")
    
    # 按日期分组，取最近ndays天
    by_date = {}
    for row in rows:
        rid, content, created_at = row
        if not created_at:
            continue
        date_ymd = created_at[:10]
        if date_ymd not in by_date:
            by_date[date_ymd] = []
        if content:
            by_date[date_ymd].append(content)
    
    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    
    if not sorted_dates:
        print(f"✗ 最近 {ndays} 天无资讯")
        return []
    
    print(f"✓ 找到最近 {ndays} 天的资讯，日期范围: {sorted_dates[-1]} 至 {sorted_dates[0]}")
    
    # 合并这些日期的正文，提取股票代码
    merged = " ".join(piece for d in sorted_dates for piece in by_date[d])
    codes = re.findall(r'\d{6}', merged)
    
    if not codes:
        print("✗ 资讯中未找到六位股票代码")
        return []
    
    # 统计出现次数
    counter = Counter(codes)
    most_common = counter.most_common(100)  # 取前100只
    
    print(f"✓ 提取到 {len(most_common)} 只股票")
    
    # 尝试获取股票名称
    print("\n[2/3] 获取股票名称...")
    
    stock_list = []
    for idx, (code, count) in enumerate(most_common, 1):
        print(f"  [{idx}/{len(most_common)}] {code}...", end=' ')
        
        # 尝试从 akshare 获取股票名称
        name = None
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=code)
            if df is not None and not df.empty:
                # 查找股票名称
                for _, row in df.iterrows():
                    if '股票简称' in row.values or '名称' in row.values:
                        name = row.iloc[1]
                        break
        except Exception:
            pass
        
        if name:
            print(f"✓ {name}")
            stock_list.append((code, count, name))
        else:
            print("? 未知")
            stock_list.append((code, count, "未知"))
    
    return stock_list

def save_to_file(stock_list, ndays=10):
    """
    保存股票列表到文件
    """
    print("\n[3/3] 保存结果...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存为 TXT
    txt_file = f"news_stocks_{ndays}days_{timestamp}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"最近 {ndays} 天资讯中的股票\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"共 {len(stock_list)} 只股票\n")
        f.write("=" * 60 + "\n\n")
        
        f.writelines(f"{idx}. {code} | {name} | 资讯出现 {count} 次\n" for idx, (code, count, name) in enumerate(stock_list, 1))
    
    print(f"✓ 已保存到 {txt_file}")
    
    # 保存为 CSV
    csv_file = f"news_stocks_{ndays}days_{timestamp}.csv"
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write("序号,代码,名称,资讯出现次数\n")
        f.writelines(f"{idx},{code},{name},{count}\n" for idx, (code, count, name) in enumerate(stock_list, 1))
    
    print(f"✓ 已保存到 {csv_file}")
    
    return txt_file, csv_file

def main():
    print("=" * 60)
    print("提取最近N天资讯中的股票")
    print("=" * 60)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='提取最近N天资讯中的股票')
    parser.add_argument('--ndays', type=int, default=10, help='最近几天（默认10天）')
    parser.add_argument('--export', action='store_true', help='保存 to 文件')
    args = parser.parse_args()
    
    # 提取股票
    stock_list = extract_stock_codes_from_news(ndays=args.ndays)
    
    if not stock_list:
        print("\n✗ 未找到股票")
        return
    
    # 输出到控制台
    print(f"\n{'=' * 60}")
    print(f"最近 {args.ndays} 天资讯中的股票（前20只）：")
    print("=" * 60)
    
    for idx, (code, count, name) in enumerate(stock_list[:20], 1):
        print(f"{idx}. {code} | {name} | 资讯出现 {count} 次")
    
    if len(stock_list) > 20:
        print(f"\n... 共 {len(stock_list)} 只股票，显示前20只")
    
    # 保存 to 文件
    if args.export:
        txt_file, csv_file = save_to_file(stock_list, ndays=args.ndays)
        print("\n✓ 结果已保存")
        print(f"  TXT: {txt_file}")
        print(f"  CSV: {csv_file}")
    
    print(f"\n{'=' * 60}")
    print("提取完成！")
    print("=" * 60)
    print("\n后续步骤建议：")
    print("1. 用 stockyidong_mac 程序打开这些股票")
    print("2. 手动检查技术指标（均线、MACD、KDJ等）")
    print("3. 或者用能用的数据接口批量分析")

if __name__ == "__main__":
    main()

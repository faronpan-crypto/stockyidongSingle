#!/usr/bin/env python3
"""
query_news_stocks.py — 纯数据库查询，提取最近N天资讯中的股票

功能：
1. 从数据库读取最近N天的资讯（纯SQL查询）
2. 用正则表达式提取股票代码（六位代码）
3. 统计出现次数，按频次降序输出
4. 不调用任何网络接口（akshare/tushare等）

用法：
  python3 query_news_stocks.py              # 查询最近10天
  python3 query_news_stocks.py --ndays 5   # 查询最近5天
  python3 query_news_stocks.py --export    # 保存 to 文件
"""

import argparse
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta

# 数据库路径
DB_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "stock_analysis.db"))

def query_news_stocks_from_db(ndays=10):
    """
    从数据库查询最近ndays天的资讯，提取股票代码
    返回：[('code', count), ...] 按出现次数降序
    """
    print(f"[1/2] 查询最近 {ndays} 天资讯...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 计算起始日期
        start_date = (datetime.now() - timedelta(days=ndays)).strftime('%Y-%m-%d')
        
        # 查询最近ndays天的资讯
        cursor.execute(
            "SELECT id, content, created_at FROM news_info WHERE created_at >= ? ORDER BY created_at DESC",
            (start_date,)
        )
        rows = cursor.fetchall()
        conn.close()
        
    except Exception as e:
        print(f"✗ 查询数据库失败: {e}")
        return []
    
    if not rows:
        print(f"✗ 最近 {ndays} 天无资讯")
        return []
    
    print(f"✓ 找到 {len(rows)} 条资讯记录")
    
    # 提取股票代码（六位代码）
    all_codes = []
    for row in rows:
        rid, content, created_at = row
        if not content:
            continue
        
        # 使用正则表达式提取六位代码
        codes = re.findall(r'\b\d{6}\b', content)
        all_codes.extend(codes)
    
    if not all_codes:
        print("✗ 资讯中未找到六位股票代码")
        return []
    
    # 统计出现次数
    counter = Counter(all_codes)
    most_common = counter.most_common(100)  # 取前100只
    
    print(f"✓ 提取到 {len(most_common)} 只股票")
    return most_common

def try_get_stock_name_from_db(code):
    """
    尝试从数据库获取股票名称
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 尝试从不同的表查询股票名称
        for table in ['stock_list', 'stocks', 'stock_info', 'stock_data']:
            try:
                cursor.execute(f"SELECT name FROM {table} WHERE code = ?", (code,))
                row = cursor.fetchone()
                if row:
                    conn.close()
                    return row[0]
            except sqlite3.OperationalError:
                continue
        
        conn.close()
    except Exception:
        pass
    
    return None

def main():
    print("=" * 60)
    print("查询最近N天资讯中的股票（纯数据库查询）")
    print("=" * 60)
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='查询最近N天资讯中的股票')
    parser.add_argument('--ndays', type=int, default=10, help='最近几天（默认10天）')
    parser.add_argument('--export', action='store_true', help='保存 to 文件')
    args = parser.parse_args()
    
    # 查询股票
    stock_codes = query_news_stocks_from_db(ndays=args.ndays)
    
    if not stock_codes:
        print("\n✗ 未找到股票代码")
        return
    
    # 尝试获取股票名称
    print("\n[2/2] 尝试获取股票名称...")
    
    stock_list = []
    for idx, (code, count) in enumerate(stock_codes, 1):
        name = try_get_stock_name_from_db(code)
        if name:
            stock_list.append((code, count, name))
        else:
            stock_list.append((code, count, "未知"))
    
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
        print("\n保存结果...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存为 TXT
        txt_file = f"news_stocks_{args.ndays}days_{timestamp}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"最近 {args.ndays} 天资讯中的股票\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"共 {len(stock_list)} 只股票\n")
            f.write("=" * 60 + "\n\n")
            
            for idx, (code, count, name) in enumerate(stock_list, 1):
                f.write(f"{idx}. {code} | {name} | 资讯出现 {count} 次\n")
        
        print(f"✓ 已保存到 {txt_file}")
        
        # 保存为 CSV
        csv_file = f"news_stocks_{args.ndays}days_{timestamp}.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("序号,代码,名称,资讯出现次数\n")
            for idx, (code, count, name) in enumerate(stock_list, 1):
                f.write(f"{idx},{code},{name},{count}\n")
        
        print(f"✓ 已保存到 {csv_file}")
    
    print(f"\n{'=' * 60}")
    print("查询完成！")
    print("=" * 60)
    print("\n后续步骤：")
    print("1. 用 stockyidong_mac 程序打开这些股票")
    print("2. 手动检查技术指标（均线、MACD、KDJ等）")
    print("3. 或者用能用的数据接口批量分析")

if __name__ == "__main__":
    main()

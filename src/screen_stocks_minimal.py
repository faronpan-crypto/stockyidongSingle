#!/usr/bin/env python3
"""
screen_stocks_minimal.py — 最小可行版筛选脚本

功能：
1. 从数据库读取最近ndays天的资讯
2. 提取股票代码（六位代码）
3. 对每只股票获取日线数据，检查均线多头发散
4. 输出符合条件的股票

特点：
- 不预先加载股票名称字典（避免慢）
- 直接使用akshare获取数据和股票名称
- 添加请求延时
"""

import os
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta

# 数据库路径
DB_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "stock_analysis.db"))

def get_recent_news_stock_codes(ndays=10):
    """
    从数据库读取最近ndays天的资讯，提取股票代码
    返回：[(code, count), ...] 按出现次数降序
    """
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
    
    # 合并这些日期的正文，提取股票代码
    merged = " ".join(piece for d in sorted_dates for piece in by_date[d])
    codes = re.findall(r'\d{6}', merged)
    
    if not codes:
        print("✗ 资讯中未找到六位股票代码")
        return []
    
    # 统计出现次数
    counter = Counter(codes)
    most_common = counter.most_common(50)  # 只取前50只
    
    print(f"✓ 从最近 {ndays} 天资讯中提取到 {len(most_common)} 只股票")
    return most_common

def check_ma_condition(code, name=None):
    """
    检查股票是否满足均线条件：MA10 > MA20 > MA60（多头排列+发散）
    返回：(是否符合, 理由)
    """
    try:
        import akshare as ak
        
        # 获取日线数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is None or len(df) < 60:
            return False, f"数据不足（{len(df) if df is not None else 0}条）"
        
        # 确保列名正确
        # akshare 返回的列名可能是中文
        df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'amplitude', 'turnover', 'turnover_rate']
        
        # 转换为数值类型
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        
        # 计算均线
        ma10 = df['close'].rolling(window=10).mean()
        ma20 = df['close'].rolling(window=20).mean()
        ma60 = df['close'].rolling(window=60).mean()
        
        # 检查最近一天
        latest = -1
        
        # 条件1：多头排列
        if ma10.iloc[latest] <= ma20.iloc[latest] or ma20.iloc[latest] <= ma60.iloc[latest]:
            return False, "均线未多头排列"
        
        # 条件2：发散（最近5天间距扩大）
        diff_10_20_now = ma10.iloc[latest] - ma20.iloc[latest]
        diff_20_60_now = ma20.iloc[latest] - ma60.iloc[latest]
        
        diff_10_20_5days = ma10.iloc[latest-5] - ma20.iloc[latest-5]
        diff_20_60_5days = ma20.iloc[latest-5] - ma60.iloc[latest-5]
        
        if diff_10_20_now <= diff_10_20_5days or diff_20_60_now <= diff_20_60_5days:
            return False, "均线未发散"
        
        return True, f"MA10={ma10.iloc[latest]:.2f}, MA20={ma20.iloc[latest]:.2f}, MA60={ma60.iloc[latest]:.2f}"
        
    except Exception as e:
        return False, f"获取数据时出错: {e}"

def main():
    print("=" * 60)
    print("最小可行版筛选脚本")
    print("=" * 60)
    
    # 1. 获取最近10天的资讯股
    print("\n[1/3] 获取最近10天资讯股...")
    stock_codes = get_recent_news_stock_codes(ndays=10)
    
    if not stock_codes:
        print("✗ 未找到股票代码")
        return
    
    print(f"✓ 找到 {len(stock_codes)} 只股票")
    
    # 2. 检查每只股票的均线条件
    print(f"\n[2/3] 检查均线条件（共 {len(stock_codes)} 只）...")
    
    results = []
    for idx, (code, count) in enumerate(stock_codes, 1):
        print(f"  [{idx}/{len(stock_codes)}] {code} (资讯出现{count}次)...", end=' ')
        
        # 添加延时
        if idx > 1:
            time.sleep(1)
        
        try:
            # 检查均线条件
            result, reason = check_ma_condition(code)
            
            if result:
                print(f"✓ {reason}")
                results.append((code, count, reason))
            else:
                print(f"✗ {reason}")
        except Exception as e:
            print(f"✗ 出错: {e}")
    
    # 3. 输出结果
    print(f"\n[3/3] 完成！找到 {len(results)} 只符合条件的股票")
    print("=" * 60)
    
    if results:
        print("\n符合条件的股票（均线多头发散）：")
        for idx, (code, count, reason) in enumerate(results, 1):
            print(f"{idx}. {code} (资讯出现{count}次) - {reason}")
    else:
        print("\n未找到符合条件的股票")
    
    print("\n" + "=" * 60)
    print("提示：")
    print("1. 本脚本只检查了日线均线条件")
    print("2. 60分钟条件需要人工确认")
    print("3. 可以使用 stockyidong_mac 程序手动检查")
    print("=" * 60)

if __name__ == "__main__":
    main()

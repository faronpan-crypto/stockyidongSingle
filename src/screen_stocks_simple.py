#!/usr/bin/env python3
"""
screen_stocks_simple.py — 简化版技术指标筛选脚本

功能：
1. 获取最近ndays日的资讯股
2. 只筛选日线条件：10、20、60均线多头发散
3. 60分钟条件标记为"需人工确认"
4. 添加请求延时，避免被服务器拒绝

用法：
  python3 screen_stocks_simple.py              # 筛选最近10日资讯股
  python3 screen_stocks_simple.py --ndays 10  # 指定天数
  python3 screen_stocks_simple.py --export    # 保存结果到文件
"""

import argparse
import os
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta

# ============== 配置 ==============
# 数据库路径
_PROJECT_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "stock_analysis.db")
DB_PATH = os.path.normpath(_PROJECT_LOCAL_DB)

# 全局变量
STOCK_CODES_DICT = None

# ============== 工具函数 ==============
def load_stock_names():
    """加载股票代码字典"""
    global STOCK_CODES_DICT
    if STOCK_CODES_DICT is not None:
        return
    
    try:
        # 尝试从数据库加载
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 尝试不同的表名
        for table in ['stock_list', 'stocks', 'stock_info']:
            try:
                cursor.execute(f"SELECT code, name FROM {table}")
                rows = cursor.fetchall()
                if rows:
                    STOCK_CODES_DICT = {row[0]: row[1] for row in rows}
                    print(f"✓ 从数据库表 {table} 加载 {len(STOCK_CODES_DICT)} 只股票")
                    conn.close()
                    return
            except sqlite3.OperationalError:
                continue
        conn.close()
    except Exception as e:
        print(f"从数据库加载股票列表失败: {e}")
    
    # 如果数据库加载失败，尝试使用 akshare 获取
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        STOCK_CODES_DICT = dict(zip(df['code'], df['name']))
        print(f"✓ 从 akshare 加载 {len(STOCK_CODES_DICT)} 只股票")
    except Exception as e:
        print(f"从 akshare 加载股票列表失败: {e}")
        STOCK_CODES_DICT = {}

def get_recent_news_stocks(ndays=10, meta=None):
    """
    获取最近ndays天的资讯股
    """
    global STOCK_CODES_DICT
    
    if meta is not None:
        meta.clear()
        meta["ndays"] = ndays
    
    # 加载股票字典
    try:
        load_stock_names()
    except Exception:
        pass
    
    if STOCK_CODES_DICT is None:
        if meta is not None:
            meta["reason"] = "no_stock_dict"
        return []
    
    # 连接数据库
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"✗ 从资讯表读取失败: {e}")
        if meta is not None:
            meta["reason"] = "db_error"
            meta["error"] = str(e)
        return []
    
    if meta is not None:
        meta["news_row_count"] = len(rows)
    
    if not rows:
        if meta is not None:
            meta["reason"] = "no_rows"
        return []
    
    # 按日期分组
    by_date = {}
    for row in rows:
        rid, tab_name, content, created_at = row
        if not created_at:
            continue
        date_ymd = created_at[:10] if len(created_at) >= 10 else created_at
        if date_ymd not in by_date:
            by_date[date_ymd] = []
        if content:
            by_date[date_ymd].append(content)
    
    # 取最近 ndays 个日期
    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    
    if not sorted_dates:
        if meta is not None:
            meta["reason"] = "no_valid_dates"
        return []
    
    # 合并这些日期的正文
    merged = " ".join(piece for d in sorted_dates for piece in by_date[d])
    
    # 提取股票代码
    codes = re.findall(r'\d{6}', merged)
    valid = [c for c in codes if c in STOCK_CODES_DICT]
    counter = Counter(valid)
    most_common = counter.most_common(80)
    
    stocks = [(STOCK_CODES_DICT[code], code) for code, _ in most_common]
    
    if meta is not None:
        meta["days_merged"] = len(sorted_dates)
        meta["merged_dates_ymd"] = sorted_dates
        meta["total_stock_count"] = len(stocks)
    
    print(f"✓ 找到最近 {ndays} 天资讯股 {len(stocks)} 只")
    return stocks

# ============== 技术指标计算 ==============
def calculate_ma(data, period):
    """计算移动平均线"""
    return data['close'].rolling(window=period).mean()

def check_ma_bullish_divergence(data):
    """
    检查10、20、60均线多头发散
    条件：
    1. MA10 > MA20 > MA60（多头排列）
    2. 三条均线向上开口扩大（发散）
    """
    if len(data) < 60:
        return False, "数据不足60天"
    
    # 计算均线
    ma10 = calculate_ma(data, 10)
    ma20 = calculate_ma(data, 20)
    ma60 = calculate_ma(data, 60)
    
    # 最近一天的数据
    latest = -1
    
    # 检查多头排列
    if ma10.iloc[latest] <= ma20.iloc[latest] or ma20.iloc[latest] <= ma60.iloc[latest]:
        return False, "均线未形成多头排列"
    
    # 检查发散（均线向上开口扩大）
    # 方法：比较最近5天和最近1天的均线间距
    diff_10_20_now = ma10.iloc[latest] - ma20.iloc[latest]
    diff_20_60_now = ma20.iloc[latest] - ma60.iloc[latest]
    
    diff_10_20_5days_ago = ma10.iloc[latest-5] - ma20.iloc[latest-5]
    diff_20_60_5days_ago = ma20.iloc[latest-5] - ma60.iloc[latest-5]
    
    # 间距扩大（当前间距 > 5天前间距）
    if diff_10_20_now <= diff_10_20_5days_ago or diff_20_60_now <= diff_20_60_5days_ago:
        return False, "均线未发散"
    
    return True, "10、20、60均线多头发散"

def analyze_stock_daily(stock_code):
    """
    分析日线技术指标
    返回：(是否符合条件, 理由)
    """
    try:
        # 使用 akshare 获取日线数据
        import akshare as ak
        
        # 获取最近180天的日线数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is None or len(df) < 60:
            return False, f"日线数据不足（{len(df) if df is not None else 0}条）"
        
        # 重命名列（根据实际返回结果调整）
        # akshare 返回的列名可能是中文
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount'
        }
        df = df.rename(columns=column_mapping)
        
        # 确保数值列是float类型
        for col in ['open', 'close', 'high', 'low', 'volume', 'amount']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        # 检查均线条件
        result, reason = check_ma_bullish_divergence(df)
        return result, reason
        
    except Exception as e:
        return False, f"获取日线数据失败: {e}"

# ============== 主函数 ==============
def screen_stocks(ndays=10, export=False):
    """主筛选函数"""
    print("=" * 60)
    print("简化版技术指标筛选脚本（只筛选日线条件）")
    print("=" * 60)
    
    # 1. 获取最近ndays天的资讯股
    print(f"\n[1/3] 获取最近 {ndays} 天资讯股...")
    meta = {}
    stocks = get_recent_news_stocks(ndays=ndays, meta=meta)
    
    if not stocks:
        print(f"✗ 未找到资讯股（原因：{meta.get('reason', 'unknown')}）")
        return
    
    print(f"✓ 找到 {len(stocks)} 只资讯股")
    
    # 2. 对每只股票进行日线技术分析
    print(f"\n[2/3] 开始日线技术分析（共 {len(stocks)} 只股票）...")
    print("（添加请求延时，避免被服务器拒绝）")
    
    results = []
    for idx, (name, code) in enumerate(stocks, 1):
        print(f"  [{idx}/{len(stocks)}] 分析 {name}({code})...", end=' ')
        
        # 添加延时（每次请求后暂停1秒）
        if idx > 1:
            time.sleep(1)
        
        try:
            # 检查日线条件
            daily_signal, daily_reason = analyze_stock_daily(code)
            
            if not daily_signal:
                print(f"✗ {daily_reason}")
                continue
            
            # 符合条件
            print(f"✓ {daily_reason}")
            
            results.append({
                'name': name,
                'code': code,
                'daily_signal': daily_reason,
                '60min_check': '需人工确认（60分钟条件）'
            })
            
        except Exception as e:
            print(f"✗ 分析失败: {e}")
            continue
    
    # 3. 输出结果
    print(f"\n[3/3] 分析完成，找到 {len(results)} 只符合条件的股票")
    print("=" * 60)
    
    if results:
        print("\n符合条件的股票（日线条件）：")
        for idx, r in enumerate(results, 1):
            print(f"\n{idx}. {r['name']}({r['code']})")
            print(f"   日线: {r['daily_signal']}")
            print(f"   60分钟: {r['60min_check']}")
    else:
        print("\n未找到符合条件的股票")
    
    # 4. 保存结果
    if export and results:
        print("\n保存结果...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"screen_result_simple_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("简化版技术指标筛选结果（只筛选日线条件）\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"资讯天数: 最近 {ndays} 天\n")
            f.write(f"符合条件的股票: {len(results)} 只\n")
            f.write("=" * 60 + "\n\n")
            
            for idx, r in enumerate(results, 1):
                f.write(f"{idx}. {r['name']}({r['code']})\n")
                f.write(f"   日线: {r['daily_signal']}\n")
                f.write(f"   60分钟: {r['60min_check']}\n\n")
        
        print(f"✓ 结果已保存到 {filename}")
    
    print("\n" + "=" * 60)
    print("筛选完成！")
    print("=" * 60)
    print("\n提示：")
    print("1. 本脚本只筛选了日线条件（10、20、60均线多头发散）")
    print("2. 60分钟条件需要人工确认（黄金坑、金叉共振、底背离）")
    print("3. 可以使用 stockyidong_mac 程序手动检查60分钟条件")

# ============== 命令行入口 ==============
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='简化版技术指标筛选脚本（只筛选日线条件）')
    parser.add_argument('--ndays', type=int, default=10, help='最近几天资讯（默认10天）')
    parser.add_argument('--export', action='store_true', help='保存结果到文件')
    
    args = parser.parse_args()
    
    screen_stocks(ndays=args.ndays, export=args.export)

#!/usr/bin/env python3
"""
screen_stocks_by_tech.py — 技术指标筛选脚本

功能：
1. 获取最近10日资讯股（参考 get_news_stocks_merged_recent_days 逻辑）
2. 计算技术指标：
   - 日线：10、20、60均线多头发散
   - 60分钟线：钱龙风警线黄金坑、MACD&KDJ金叉共振、KDJ底背离
3. 筛选符合条件的股票

用法：
  python3 screen_stocks_by_tech.py              # 筛选最近10日资讯股
  python3 screen_stocks_by_tech.py --ndays 10  # 指定天数
  python3 screen_stocks_by_tech.py --export    # 保存结果到文件
"""

import argparse
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta

# ============== 配置 ==============
# 数据库路径（参考 stockyidong mac.py 的逻辑）
_PROJECT_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "stock_analysis.db")
DB_PATH = os.path.normpath(_PROJECT_LOCAL_DB)

# 全局变量
STOCK_CODES_DICT = None

# ============== 工具函数 ==============
def load_stock_names():
    """加载股票代码字典（参考原函数逻辑）"""
    global STOCK_CODES_DICT
    if STOCK_CODES_DICT is not None:
        return
    
    try:
        # 尝试从数据库加载
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name FROM stock_list")
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            STOCK_CODES_DICT = {row[0]: row[1] for row in rows}
            print(f"✓ 从数据库加载 {len(STOCK_CODES_DICT)} 只股票")
            return
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
    参考 get_news_stocks_merged_recent_days 逻辑
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

def calculate_macd(data, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    ema_fast = data['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = data['close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return dif, dea, macd

def calculate_kdj(data, n=9, m1=3, m2=3):
    """计算KDJ指标"""
    low_n = data['low'].rolling(window=n).min()
    high_n = data['high'].rolling(window=n).max()
    
    rsv = (data['close'] - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)
    
    k = rsv.ewm(com=m1-1, adjust=False).mean()
    d = k.ewm(com=m2-1, adjust=False).mean()
    j = 3 * k - 2 * d
    
    return k, d, j

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
    # 方法1：均线间距扩大
    diff_10_20_now = ma10.iloc[latest] - ma20.iloc[latest]
    diff_20_60_now = ma20.iloc[latest] - ma60.iloc[latest]
    
    diff_10_20_prev = ma10.iloc[latest-5] - ma20.iloc[latest-5]
    diff_20_60_prev = ma20.iloc[latest-5] - ma60.iloc[latest-5]
    
    if diff_10_20_now <= diff_10_20_prev or diff_20_60_now <= diff_20_60_prev:
        return False, "均线未发散"
    
    return True, "10、20、60均线多头发散"

def check_golden_pit(data):
    """
    检查钱龙风警线黄金坑
    简化版：J值跌破20后回升
    """
    if len(data) < 20:
        return False, "数据不足"
    
    _, _, j = calculate_kdj(data)
    
    # 检查最近5天是否有J值跌破20后回升
    for i in range(-5, -1):
        if j.iloc[i-1] <= 20 and j.iloc[i] > 20:
            return True, f"J值黄金坑（{j.iloc[i]:.2f}）"
    
    return False, "未出现黄金坑"

def check_macd_kdj_golden_cross(data):
    """
    检查MACD & KDJ 金叉共振
    条件：MACD金叉 且 KDJ金叉（同一天或相邻2天内）
    """
    if len(data) < 30:
        return False, "数据不足"
    
    # 计算指标
    dif, dea, macd = calculate_macd(data)
    k, d, j = calculate_kdj(data)
    
    # 检查最近3天
    for i in range(-3, -1):
        # MACD金叉：DIF上穿DEA
        macd_cross = (dif.iloc[i-1] <= dea.iloc[i-1]) and (dif.iloc[i] > dea.iloc[i])
        
        # KDJ金叉：K上穿D
        kdj_cross = (k.iloc[i-1] <= d.iloc[i-1]) and (k.iloc[i] > d.iloc[i])
        
        if macd_cross and kdj_cross:
            return True, "MACD & KDJ 金叉共振"
    
    return False, "未出现金叉共振"

def check_kdj_bottom_divergence(data):
    """
    检查KDJ底背离
    条件：股价创新低，但J值未创新低
    """
    if len(data) < 20:
        return False, "数据不足"
    
    _, _, j = calculate_kdj(data)
    
    # 找最近20天的最低价
    recent_low = data['close'].iloc[-20:].min()
    recent_j_low = j.iloc[-20:].min()
    
    # 当前价格
    current_price = data['close'].iloc[-1]
    current_j = j.iloc[-1]
    
    # 底背离：当前价格接近最低点，但J值明显高于最低点时的J值
    if current_price <= recent_low * 1.02:  # 当前价格在最低点2%以内
        if current_j > recent_j_low * 1.2:  # 当前J值比最低点时的J值高20%以上
            return True, f"KDJ底背离（价格{current_price:.2f}，J值{current_j:.2f}）"
    
    return False, "未出现底背离"

def analyze_stock_60min(stock_code):
    """
    分析60分钟周期的技术指标
    返回：(信号列表, 理由列表)
    """
    signals = []
    reasons = []
    
    try:
        # 使用 akshare 获取60分钟数据
        import akshare as ak
        
        # 获取最近60天的数据（60分钟线，约240根K线）
        end_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
        
        df = ak.stock_zh_a_hist_min_em(
            symbol=stock_code,
            period='60',
            start_date=start_date,
            end_date=end_date,
            adjust='qfq'
        )
        
        if df is None or len(df) < 100:
            return [], [f"60分钟数据不足（{len(df) if df is not None else 0}条）"]
        
        # 列名可能是中文，需要重命名
        # 根据实际返回结果调整
        column_mapping = {
            '时间': 'time',
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
        
        # 检查各项条件
        signal, reason = check_golden_pit(df)
        if signal:
            signals.append('黄金坑')
            reasons.append(reason)
        
        signal, reason = check_macd_kdj_golden_cross(df)
        if signal:
            signals.append('金叉共振')
            reasons.append(reason)
        
        signal, reason = check_kdj_bottom_divergence(df)
        if signal:
            signals.append('KDJ底背离')
            reasons.append(reason)
        
    except Exception as e:
        return [], [f"获取60分钟数据失败: {e}"]
    
    return signals, reasons

# ============== 主函数 ==============
def screen_stocks(ndays=10, export=False):
    """主筛选函数"""
    print("=" * 60)
    print("技术指标筛选脚本")
    print("=" * 60)
    
    # 1. 获取最近ndays天的资讯股
    print(f"\n[1/4] 获取最近 {ndays} 天资讯股...")
    meta = {}
    stocks = get_recent_news_stocks(ndays=ndays, meta=meta)
    
    if not stocks:
        print(f"✗ 未找到资讯股（原因：{meta.get('reason', 'unknown')}）")
        return
    
    print(f"✓ 找到 {len(stocks)} 只资讯股")
    
    # 2. 对每只股票进行技术分析
    print(f"\n[2/4] 开始技术分析（共 {len(stocks)} 只股票）...")
    
    results = []
    for idx, (name, code) in enumerate(stocks, 1):
        print(f"  [{idx}/{len(stocks)}] 分析 {name}({code})...", end=' ')
        
        try:
            # 获取日线数据
            import akshare as ak
            df_day = ak.stock_zh_a_hist(
                symbol=code,  # 这里应该是 code，不是 stock_code
                period="daily",
                start_date=(datetime.now() - timedelta(days=180)).strftime('%Y%m%d'),
                end_date=datetime.now().strftime('%Y%m%d'),
                adjust="qfq"
            )
            
            if df_day is None or len(df_day) < 60:
                print("✗ 日线数据不足")
                continue
            
            # 重命名列
            df_day = df_day.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            })
            
            # 检查均线条件
            ma_signal, ma_reason = check_ma_bullish_divergence(df_day)
            
            if not ma_signal:
                print(f"✗ {ma_reason}")
                continue
            
            # 检查60分钟条件
            signals_60min, reasons_60min = analyze_stock_60min(code)
            
            if not signals_60min:
                print("✗ 60分钟无信号")
                continue
            
            # 符合条件
            print(f"✓ {ma_reason} | {', '.join(signals_60min)}")
            
            results.append({
                'name': name,
                'code': code,
                'ma_signal': ma_reason,
                '60min_signals': ', '.join(signals_60min),
                '60min_reasons': '; '.join(reasons_60min)
            })
            
        except Exception as e:
            print(f"✗ 分析失败: {e}")
            continue
    
    # 3. 输出结果
    print(f"\n[3/4] 分析完成，找到 {len(results)} 只符合条件的股票")
    print("=" * 60)
    
    if results:
        print("\n符合条件的股票：")
        for idx, r in enumerate(results, 1):
            print(f"\n{idx}. {r['name']}({r['code']})")
            print(f"   日线: {r['ma_signal']}")
            print(f"   60分钟: {r['60min_signals']}")
            print(f"   详情: {r['60min_reasons']}")
    
    # 4. 保存结果
    if export and results:
        print("\n[4/4] 保存结果...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"screen_result_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("技术指标筛选结果\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"资讯天数: 最近 {ndays} 天\n")
            f.write(f"符合条件的股票: {len(results)} 只\n")
            f.write("=" * 60 + "\n\n")
            
            for idx, r in enumerate(results, 1):
                f.write(f"{idx}. {r['name']}({r['code']})\n")
                f.write(f"   日线: {r['ma_signal']}\n")
                f.write(f"   60分钟: {r['60min_signals']}\n")
                f.write(f"   详情: {r['60min_reasons']}\n\n")
        
        print(f"✓ 结果已保存到 {filename}")
    
    print("\n" + "=" * 60)
    print("筛选完成！")
    print("=" * 60)

# ============== 命令行入口 ==============
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='技术指标筛选脚本')
    parser.add_argument('--ndays', type=int, default=10, help='最近几天资讯（默认10天）')
    parser.add_argument('--export', action='store_true', help='保存结果到文件')
    
    args = parser.parse_args()
    
    screen_stocks(ndays=args.ndays, export=args.export)

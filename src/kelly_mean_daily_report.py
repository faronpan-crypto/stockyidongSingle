#!/usr/bin/env python3
"""
凯均日报生成器 v1.0
对持仓股批量运行日K线图的凯利公式计算 + 均值回归计算
结果写入 stock_analysis.db（kelly_records表 + news_info表）
同时生成凯均日报文件
"""

import os
import sqlite3
import traceback
from datetime import datetime, timedelta

import baostock as bs
import numpy as np

# ============================================================
# 配置
# ============================================================

STOCKYIDONG_PROJECT_ROOT = os.path.expanduser("/Users/faronpan/Agent/stockyidong_project")
DB_PATH = os.path.join(STOCKYIDONG_PROJECT_ROOT, "data", "stock_analysis.db")
REPORTS_DIR = os.path.expanduser("~/.qclaw/workspace-agent-8e17987b/reports")

# ============================================================
# 持仓列表（从记忆库和历史对话中提取）
# ============================================================

HOLDINGS = [
    ("盛合晶微", "688820", "688820.SH"),
    ("埃夫特",   "688165", "688165.SH"),
    ("拓普集团", "601689", "601689.SH"),
    ("斯达半导", "603290", "603290.SH"),
    ("上海电力", "600021", "600021.SH"),
    ("索菱股份", "002766", "002766.SZ"),
    ("福晶科技", "002222", "002222.SZ"),
    ("国瓷材料", "300285", "300285.SZ"),
    ("海康威视", "002415", "002415.SZ"),
    ("商络电子", "300975", "300975.SZ"),
    ("东威科技", "688700", "688700.SH"),
    ("英诺赛科", "02577",  "02577.HK"),
]


# ============================================================
# 数据库操作
# ============================================================

def get_db_conn():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    """确保所需表存在"""
    conn = get_db_conn()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS news_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_name TEXT NOT NULL,
            content TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS kelly_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_name TEXT NOT NULL,
            calc_time TEXT,
            odds REAL,
            win_prob REAL,
            kelly_ratio REAL,
            suggestion TEXT,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


def save_kelly_to_db(stock_name, odds, win_prob, kelly_ratio, suggestion, notes):
    """保存凯利计算结果到数据库"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO kelly_records (stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (stock_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              odds, win_prob, kelly_ratio, suggestion, notes))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  保存凯利记录失败: {e}")
        return False


def save_news_to_db(tab_name, content):
    """保存内容到资讯表"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO news_info (tab_name, content, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (tab_name, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  保存资讯失败: {e}")
        return False


# ============================================================
# 计算函数（移植自 stockyidong mac.py）
# ============================================================

def calculate_ma_status(closes, latest_price=None):
    """
    检测均线状态，移植自 stockyidong mac.py _check_ma_status
    closes: list of float（最近N个交易日收盘价，最新的在最后）
    """
    if latest_price is None:
        latest_price = float(closes[-1])
    
    result = {
        'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False,
        'below_ma20': False, 'ma10_distance_pct': None,
        'fish_body': False, 'fish_tail': False,
        'current_price': latest_price,
    }
    
    # 1日线
    if len(closes) >= 3:
        ref_price = float(closes[-2])
        result['ma1'] = latest_price >= ref_price
    
    # 5日线
    if len(closes) >= 7:
        ma5 = np.mean([float(closes[i]) for i in range(len(closes)-5, len(closes))])
        prev_ma5 = np.mean([float(closes[i]) for i in range(len(closes)-10, len(closes)-5)])
        result['ma5'] = (latest_price >= ma5 >= prev_ma5)
    
    # 10日线
    ref_ma10 = None
    prev_ma10 = None
    if len(closes) >= 12:
        ref_ma10 = np.mean([float(closes[i]) for i in range(len(closes)-10, len(closes))])
        prev_ma10 = np.mean([float(closes[i]) for i in range(len(closes)-20, len(closes)-10)])
        ma10_crossed = latest_price >= ref_ma10
        ma10_uptrend = ref_ma10 >= prev_ma10
        result['ma10'] = ma10_crossed and ma10_uptrend
        
        if ref_ma10 > 0:
            result['ma10_distance_pct'] = abs((latest_price - ref_ma10) / ref_ma10) * 100
    
    # 20日线
    ref_ma20 = None
    prev_ma20 = None
    if len(closes) >= 22:
        ma20_vals = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
        ref_ma20 = np.mean(ma20_vals)
        prev_ma20_vals = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
        prev_ma20 = np.mean(prev_ma20_vals) if len(prev_ma20_vals) >= 20 else ref_ma20
        ma20_crossed = latest_price >= ref_ma20
        ma20_uptrend = ref_ma20 >= prev_ma20
        result['ma20'] = ma20_crossed and ma20_uptrend
        result['below_ma20'] = latest_price < ref_ma20
    
    # 鱼身/鱼尾
    if ref_ma20 is not None and ref_ma10 is not None:
        above_ma10 = latest_price >= ref_ma10
        ma10_up = ref_ma10 >= prev_ma10
        ma20_up = ref_ma20 >= prev_ma20
        ma20_down = ref_ma20 < prev_ma20
        result['fish_body'] = bool(above_ma10 and ma10_up and ma20_up)
        result['fish_tail'] = bool((latest_price < ref_ma10) or ma20_down)
    
    return result


def calculate_kelly_params(ma_status):
    """
    根据均线状态计算盈亏比b和胜率p
    移植自 stockyidong mac.py _calculate_kelly_params
    """
    ma1 = ma_status.get('ma1', False)
    ma5 = ma_status.get('ma5', False)
    ma10 = ma_status.get('ma10', False)
    ma20 = ma_status.get('ma20', False)
    below_ma20 = ma_status.get('below_ma20', False)
    
    if below_ma20:
        return 1.0, 0.5
    
    # 根据均线站上数量和趋势赋予不同的b和p
    count = sum([ma1, ma5, ma10, ma20])
    
    if ma20:  # 站上20日线且20线上行
        if count >= 4:
            return 2.5, 0.70  # 多头排列，胜率高
        elif count >= 3:
            return 2.0, 0.65
        elif count >= 2:
            return 1.5, 0.60
        else:
            return 1.2, 0.55
    elif ma10:  # 站上10日线未站上20日线
        if count >= 2:
            return 1.5, 0.55
        else:
            return 1.2, 0.50
    elif ma5:
        return 1.0, 0.45
    else:
        return 1.0, 0.40


def calculate_kelly_ratio(b, p):
    """f = (bp - q) / b, q = 1 - p"""
    q = 1 - p
    kelly = (b * p - q) / b
    kelly = max(0.0, min(1.0, kelly))
    return kelly


def calculate_mean_reversion(closes, window=20):
    """
    均值回归计算，移植自 stockyidong mac.py _calculate_mean_reversion
    
    Returns:
        dict with z_score, mean_price, std, reversion_prob, suggested_position
    """
    result = {
        'success': False,
        'z_score': 0.0,
        'mean_price': 0.0,
        'std_deviation': 0.0,
        'current_price': 0.0,
        'reversion_probability': 0.0,
        'suggested_position': 0.0,
        'position_type': '观望',
        'message': '',
    }
    
    if len(closes) < window:
        result['message'] = f'数据不足，需要{window}条K线'
        return result
    
    current_price = float(closes[-1])
    result['current_price'] = current_price
    
    recent_closes = [float(c) for c in closes[-window:]]
    mean_price = np.mean(recent_closes)
    std_dev = np.std(recent_closes, ddof=1)
    
    result['mean_price'] = round(mean_price, 2)
    result['std_deviation'] = round(std_dev, 2)
    
    if std_dev > 0:
        z_score = (current_price - mean_price) / std_dev
    else:
        z_score = 0.0
    result['z_score'] = round(z_score, 4)
    
    # 回归概率
    abs_z = abs(z_score)
    if abs_z >= 3.0:
        reversion_prob = 0.95
    elif abs_z >= 2.0:
        reversion_prob = 0.85
    elif abs_z >= 1.5:
        reversion_prob = 0.75
    elif abs_z >= 1.0:
        reversion_prob = 0.65
    elif abs_z >= 0.5:
        reversion_prob = 0.55
    else:
        reversion_prob = 0.50
    
    result['reversion_probability'] = round(reversion_prob * 100, 1)
    
    # 建议仓位
    base_position = min(abs_z * 0.15, 0.5)
    if z_score < -0.5:
        result['suggested_position'] = round(base_position * 100, 1)
        result['position_type'] = '买入'
    elif z_score > 0.5:
        result['suggested_position'] = round(-base_position * 100, 1)
        result['position_type'] = '卖出'
    else:
        result['suggested_position'] = 0.0
        result['position_type'] = '观望'
    
    result['success'] = True
    return result


def get_kelly_suggestion(kelly_ratio, ma_status):
    """生成凯利公式操作建议"""
    below_ma20 = ma_status.get('below_ma20', False)
    fish_body = ma_status.get('fish_body', False)
    fish_tail = ma_status.get('fish_tail', False)
    
    if kelly_ratio <= 0:
        return "不开仓"
    elif below_ma20:
        return "谨慎观察"
    elif fish_body:
        return "加仓"
    elif fish_tail:
        return "减仓"
    elif kelly_ratio >= 0.3:
        return "可开仓"
    elif kelly_ratio >= 0.15:
        return "轻仓"
    else:
        return "观望"


# ============================================================
# 主计算逻辑
# ============================================================

def fetch_stock_data(stock_code, days=60):
    """获取股票日K数据"""
    bs_code = f"sz.{stock_code}" if stock_code.startswith(('00', '30')) else f"sh.{stock_code}"
    
    start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
    end_date = datetime.now().strftime('%Y%m%d')
    
    rs = bs.query_history_k_data_plus(
        bs_code,
        'date,open,high,low,close,preclose,volume,amount,pctChg,turn',
        start_date=start_date, end_date=end_date,
        frequency='d', adjustflag='2'
    )
    
    dates, opens, highs, lows, closes, volumes, pcts, turns = [], [], [], [], [], [], [], []
    while rs.error_code == '0' and rs.next():
        row = rs.get_row_data()
        if row[0] and row[4]:
            dates.append(row[0])
            opens.append(float(row[1]))
            highs.append(float(row[2]))
            lows.append(float(row[3]))
            closes.append(float(row[4]))
            volumes.append(float(row[6]) if row[6] else 0)
            pcts.append(float(row[8]) if row[8] else 0.0)
            turns.append(float(row[9]) if row[9] else 0.0)
    
    return dates, closes, pcts


def run_analysis():
    """对所有持仓股运行凯利+均值回归计算"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    print("=" * 60)
    print(f"  凯均日报生成 - {today_str}")
    print("=" * 60)
    
    # 确保数据库表存在
    ensure_tables()
    
    # 登录baostock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"baostock登录失败: {lg.error_msg}")
        return
    
    results = []
    
    for idx, (name, code, _) in enumerate(HOLDINGS, 1):
        print(f"\n[{idx}/{len(HOLDINGS)}] {name}({code})")
        
        try:
            dates, closes, pcts = fetch_stock_data(code)
            
            if len(closes) < 20:
                print(f"  ⚠️ 数据不足（{len(closes)}条），跳过")
                results.append((name, code, None, None, '数据不足'))
                continue
            
            latest_price = closes[-1]
            latest_pct = pcts[-1] if pcts else 0
            latest_date = dates[-1] if dates else today_str
            
            # --- 均线状态 ---
            ma_status = calculate_ma_status(closes, latest_price)
            
            # --- 凯利公式 ---
            b, p = calculate_kelly_params(ma_status)
            kelly = calculate_kelly_ratio(b, p)
            kelly_pct = kelly * 100
            suggestion = get_kelly_suggestion(kelly, ma_status)
            
            # --- 均值回归 ---
            mr = calculate_mean_reversion(closes)
            
            # --- 保存到数据库 ---
            kelly_notes = (
                f"ma1={'Y' if ma_status['ma1'] else 'N'} "
                f"ma5={'Y' if ma_status['ma5'] else 'N'} "
                f"ma10={'Y' if ma_status['ma10'] else 'N'} "
                f"ma20={'Y' if ma_status['ma20'] else 'N'} "
                f"鱼身={'Y' if ma_status.get('fish_body') else 'N'} "
                f"鱼尾={'Y' if ma_status.get('fish_tail') else 'N'}"
            )
            save_kelly_to_db(name, b, p, kelly, suggestion, kelly_notes)
            
            result_entry = {
                'name': name, 'code': code,
                'price': latest_price, 'pct': latest_pct,
                'date': latest_date,
                'ma_status': ma_status,
                'b': b, 'p': p,
                'kelly': kelly, 'kelly_pct': kelly_pct,
                'suggestion': suggestion,
                'mr': mr,
            }
            results.append(result_entry)
            
            print(f"  最新价: {latest_price:.2f} ({latest_pct:+.2f}%)")
            print(f"  均线: MA1={'✅' if ma_status['ma1'] else '❌'} "
                  f"MA5={'✅' if ma_status['ma5'] else '❌'} "
                  f"MA10={'✅' if ma_status['ma10'] else '❌'} "
                  f"MA20={'✅' if ma_status['ma20'] else '❌'}")
            print(f"  鱼身={'✅' if ma_status.get('fish_body') else '❌'} "
                  f"鱼尾={'✅' if ma_status.get('fish_tail') else '❌'}")
            print(f"  凯利: b={b:.1f} p={p:.2f} → {suggestion} ({kelly_pct:.1f}%)")
            print(f"  均值回归: Z={mr['z_score']:.2f} 概率={mr['reversion_probability']:.1f}% → {mr['position_type']}")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            traceback.print_exc()
            results.append((name, code, None, None, str(e)))
    
    bs.logout()
    
    # ============================================================
    # 生成凯均日报
    # ============================================================
    report_lines = []
    report_lines.append(f"# 📊 凯均日报 - {today_str}")
    report_lines.append(f"**生成时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"**股票数量：** {len([r for r in results if isinstance(r, dict)])} 只")
    report_lines.append("")
    
    # 按凯利建议分类
    can_open = [r for r in results if isinstance(r, dict) and r['suggestion'] in ('可开仓', '加仓')]
    hold = [r for r in results if isinstance(r, dict) and r['suggestion'] in ('轻仓', '观望')]
    caution = [r for r in results if isinstance(r, dict) and r['suggestion'] in ('不开仓', '谨慎观察', '减仓')]
    
    report_lines.append("## 一、凯利公式仓位建议")
    report_lines.append("")
    report_lines.append("| 股票 | 价格 | 涨跌幅 | MA1 | MA5 | MA10 | MA20 | 鱼身/尾 | 凯利 | 建议 |")
    report_lines.append("|------|------|--------|-----|-----|------|------|---------|------|------|")
    
    for r in sorted(results, key=lambda x: x['kelly_pct'] if isinstance(x, dict) and x['kelly'] else 0, reverse=True):
        if not isinstance(r, dict):
            continue
        ms = r['ma_status']
        ma_str = f"{'✅' if ms['ma1'] else '❌'} | {'✅' if ms['ma5'] else '❌'} | {'✅' if ms['ma10'] else '❌'} | {'✅' if ms['ma20'] else '❌'}"
        fish_str = f"{'鱼身' if ms.get('fish_body') else '鱼尾' if ms.get('fish_tail') else '-'}"
        report_lines.append(
            f"| {r['name']}({r['code']}) | {r['price']:.2f} | {r['pct']:+.2f}% | "
            f"{ma_str} | {fish_str} | {r['kelly_pct']:.0f}% | **{r['suggestion']}** |"
        )
    
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## 二、均值回归分析")
    report_lines.append("")
    report_lines.append(f"| 股票 | 当前价 | MA{20} | Z-score | 标准差 | 回归概率 | 建议操作 |")
    report_lines.append("|------|--------|--------|---------|--------|---------|---------|")
    
    for r in results:
        if not isinstance(r, dict):
            continue
        mr = r['mr']
        if mr['success']:
            op_icon = "🟢" if mr['position_type'] == '买入' else ("🔴" if mr['position_type'] == '卖出' else "⚪")
            report_lines.append(
                f"| {r['name']}({r['code']}) | {mr['current_price']:.2f} | {mr['mean_price']:.2f} | "
                f"{mr['z_score']:.2f} | {mr['std_deviation']:.2f} | {mr['reversion_probability']:.1f}% | "
                f"{op_icon} **{mr['position_type']}** |"
            )
    
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    # 汇总
    report_lines.append("## 三、操作汇总")
    report_lines.append("")
    
    if can_open:
        report_lines.append(f"### 🟢 可开仓/加仓 ({len(can_open)})")
        for r in can_open:
            mr = r['mr']
            z_note = f" (Z={mr['z_score']:.2f})" if mr['success'] else ""
            report_lines.append(f"- **{r['name']}({r['code']})**: 凯利{r['kelly_pct']:.0f}% → {r['suggestion']}{z_note}")
        report_lines.append("")
    
    if caution:
        report_lines.append(f"### 🔴 谨慎/减仓 ({len(caution)})")
        for r in caution:
            mr = r['mr']
            z_note = f" (Z={mr['z_score']:.2f})" if mr['success'] else ""
            report_lines.append(f"- **{r['name']}({r['code']})**: 凯利{r['kelly_pct']:.0f}% → {r['suggestion']}{z_note}")
        report_lines.append("")
    
    # 均值回归预警
    extreme_z = [r for r in results if isinstance(r, dict) and r['mr']['success'] and abs(r['mr']['z_score']) >= 1.5]
    if extreme_z:
        report_lines.append("### ⚠️ 均值回归预警 (|Z|≥1.5)")
        for r in sorted(extreme_z, key=lambda x: abs(x['mr']['z_score']), reverse=True):
            mr = r['mr']
            direction = "超卖（看涨）" if mr['z_score'] < -1.5 else "超买（看跌）"
            report_lines.append(f"- **{r['name']}({r['code']})**: Z={mr['z_score']:.2f}, {direction}, 概率{mr['reversion_probability']:.1f}%")
        report_lines.append("")
    
    report_lines.append("---")
    report_lines.append("")
    report_lines.append(f"*报告生成：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 数据源：baostock*")
    report_lines.append(f"*凯利公式：f = (b*p - q)/b | 均值回归：Z-score窗口{20}日*")
    
    report_text = "\n".join(report_lines)
    
    # 保存到文件
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_filename = f"kelly_mean_daily_{datetime.now().strftime('%Y%m%d')}.md"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\n{'=' * 60}")
    print(f"  报告已保存: {report_path}")
    
    # 写入数据库news_info表
    save_news_to_db(f"凯均日报-{today_str}", report_text)
    print(f"  已写入数据库: {DB_PATH}")
    
    # 也保存到每日记忆文件
    memory_dir = os.path.expanduser("~/.qclaw/workspace-agent-8e17987b/memory")
    os.makedirs(memory_dir, exist_ok=True)
    memory_file = os.path.join(memory_dir, f"{today_str}.md")
    with open(memory_file, 'a', encoding='utf-8') as f:
        f.write(f"\n\n---\n## 凯均日报 {datetime.now().strftime('%H:%M')}\n\n")
        f.write(f"生成文件: {report_filename}\n")
        f.write("数据库: 已写入 news_info + kelly_records\n\n")
    
    print(f"  已追加到memory: {memory_file}")
    print(f"{'=' * 60}")
    print("\n生成的凯均日报内容：")
    print("=" * 60)
    print(report_text)
    
    return report_path, report_text


if __name__ == "__main__":
    run_analysis()

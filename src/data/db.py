"""
数据库操作模块。从 stockyidong mac003.py 提取。

本模块只依赖 sqlite3 + utils.config.DB_PATH,不依赖 tkinter/akshare/tushare。
主文件用 `from data.db import *` 保持零行为变化。
"""
import sqlite3
from datetime import datetime

from utils.config import DB_PATH

__all__ = [
    "JUDGMENT_CACHE_TTL_SECONDS",
    "init_database",
    "_ensure_judgment_cache_table",
    "save_judgment_cache_snapshot",
    "load_fresh_judgment_cache",
    "has_lhb_records",
    "save_lhb_records",
    "save_stock_to_db",
    "save_article_to_db",
    "save_news_info_to_db",
    "save_kelly_record_to_db",
    "save_stock_logic_to_db",
    "get_stock_logic_from_db",
    "delete_stock_logic_from_db",
    "update_stock_logic_in_db",
]

# 研判表缓存有效期 (秒),默认 3 小时
JUDGMENT_CACHE_TTL_SECONDS = 3 * 3600


# ==================== 初始化 ====================
def init_database():
    """初始化股票数据库"""
    db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 创建股票数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL,
            change_pct REAL,
            volume REAL,
            turnover REAL,
            market_cap REAL,
            pe_ratio REAL,
            sector TEXT,
            theme TEXT,
            analysis_result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, date)
        )
    ''')
    # 创建爬取文章表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawled_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            content TEXT,
            url TEXT,
            publish_time TEXT,
            views INTEGER,
            likes INTEGER,
            replies INTEGER,
            crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建股票逻辑表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_logic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_name TEXT NOT NULL,
            logic TEXT,
            date TEXT NOT NULL,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建资讯表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_name TEXT NOT NULL,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建评注表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER NOT NULL,
            comment_text TEXT NOT NULL,
            author TEXT,
            color TEXT,
            font_family TEXT,
            font_size INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (news_id) REFERENCES news_info(id) ON DELETE CASCADE
        )
    ''')
    # 创建凯利公式记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kelly_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_name TEXT NOT NULL,
            calc_time TEXT NOT NULL,
            odds REAL NOT NULL,
            win_prob REAL NOT NULL,
            kelly_ratio REAL NOT NULL,
            suggestion TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建交易体系配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trading_system_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            stock_type TEXT,
            sector TEXT,
            strategy TEXT,
            market_status TEXT,
            peripheral_sentiment REAL,
            position REAL,
            stop_loss REAL,
            take_profit REAL,
            target_price REAL,
            config_advice TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建龙虎榜记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lhb_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            name TEXT,
            close REAL,
            pct_change REAL,
            turnover_rate REAL,
            amount REAL,
            l_sell REAL,
            l_buy REAL,
            l_amount REAL,
            net_amount REAL,
            net_rate REAL,
            amount_rate REAL,
            float_values REAL,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trade_date, ts_code, reason)
        )
    ''')
    # 创建同花顺实时数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ths_realtime_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            current_price REAL,
            change_pct REAL,
            circulation_market_value REAL,
            volume_ratio REAL,
            four_min_change_rate REAL,
            main_net_amount REAL,
            net_amount_ratio REAL,
            turnover_rate REAL,
            pe_ratio REAL,
            amplitude REAL,
            good_news TEXT,
            limit_up_count INTEGER,
            save_date TEXT NOT NULL,
            save_time TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ths_stock_code ON ths_realtime_data(stock_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ths_save_date ON ths_realtime_data(save_date)')
    # 系统研判缓存
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS judgment_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            raw_context TEXT NOT NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_judgment_cache_created ON judgment_cache(created_at)')
    # 创建情绪历史记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_time TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            m1_today REAL,
            m1_yday REAL,
            m2_up INTEGER,
            m2_down INTEGER,
            m2_flat INTEGER,
            m2_total INTEGER,
            m3_count INTEGER,
            m4_count INTEGER,
            m5_hs300 REAL,
            m5_zz500 REAL,
            m5_kc30 REAL,
            m5_avg REAL,
            raw_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_history_date ON sentiment_history(snapshot_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sentiment_history_time ON sentiment_history(snapshot_time)')
    conn.commit()
    conn.close()
    return db_path


# ==================== 研判缓存 ====================
def _ensure_judgment_cache_table():
    """确保 judgment_cache 表存在"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS judgment_cache (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, raw_context TEXT NOT NULL)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_judgment_cache_created ON judgment_cache(created_at)")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"确保研判表存在失败: {e}")


def save_judgment_cache_snapshot(raw_context: str):
    """将系统研判原始汇总写入 judgment_cache"""
    if not raw_context or not str(raw_context).strip():
        return
    _ensure_judgment_cache_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO judgment_cache (created_at, raw_context) VALUES (?, ?)", (ts, raw_context))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"保存研判表失败: {e}")


def load_fresh_judgment_cache(max_age_seconds=None):
    """读取研判表最新一条;若在有效期内则返回 (raw_context, created_at),否则 (None, None)"""
    if max_age_seconds is None:
        max_age_seconds = JUDGMENT_CACHE_TTL_SECONDS
    _ensure_judgment_cache_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT created_at, raw_context FROM judgment_cache ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None, None
        created_at, raw = row[0], row[1]
        dt = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - dt).total_seconds() > float(max_age_seconds):
            return None, None
        return raw, created_at
    except Exception as e:
        print(f"读取研判表失败: {e}")
        return None, None


# ==================== 龙虎榜 ====================
def has_lhb_records(trade_date):
    """检查指定日期的龙虎榜数据是否已保存"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM lhb_records WHERE trade_date = ?", (trade_date,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"检查龙虎榜数据失败: {e}")
        return False


def save_lhb_records(records):
    """批量保存龙虎榜数据"""
    if not records:
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        insert_sql = '''
            INSERT OR IGNORE INTO lhb_records (
                trade_date, ts_code, name, close, pct_change, turnover_rate,
                amount, l_sell, l_buy, l_amount, net_amount, net_rate,
                amount_rate, float_values, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        prepared = []
        for row in records:
            prepared.append((
                row.get('trade_date'), row.get('ts_code'), row.get('name'),
                row.get('close'), row.get('pct_change'), row.get('turnover_rate'),
                row.get('amount'), row.get('l_sell'), row.get('l_buy'),
                row.get('l_amount'), row.get('net_amount'), row.get('net_rate'),
                row.get('amount_rate'), row.get('float_values'), row.get('reason')
            ))
        cursor.executemany(insert_sql, prepared)
        inserted = cursor.rowcount
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        print(f"保存龙虎榜记录失败: {e}")
        return 0


# ==================== 股票数据 ====================
def save_stock_to_db(stock_code, stock_name, date, price=None, change_pct=None,
                     volume=None, turnover=None, market_cap=None, pe_ratio=None,
                     sector=None, theme=None, analysis_result=None):
    """保存股票数据到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO stock_data
            (stock_code, stock_name, date, price, change_pct, volume, turnover,
             market_cap, pe_ratio, sector, theme, analysis_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (stock_code, stock_name, date, price, change_pct, volume, turnover,
              market_cap, pe_ratio, sector, theme, analysis_result))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存股票数据到数据库失败: {e}")
        return False


def save_article_to_db(source, title, author=None, content=None, url=None,
                       publish_time=None, views=0, likes=0, replies=0):
    """保存爬取的文章到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO crawled_articles
            (source, title, author, content, url, publish_time, views, likes, replies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (source, title, author, content, url, publish_time, views, likes, replies))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存文章到数据库失败: {e}")
        return False


def save_news_info_to_db(tab_name, content):
    """保存资讯到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO news_info (tab_name, content, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (tab_name, content, current_time, current_time))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存资讯到数据库失败: {e}")
        return False


# ==================== 凯利公式 ====================
def save_kelly_record_to_db(stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes):
    """保存凯利公式计算结果到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO kelly_records
            (stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存凯利公式记录失败: {e}")
        return False


# ==================== 股票逻辑 ====================
def save_stock_logic_to_db(stock_name, logic, date, source=None):
    """保存股票逻辑到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stock_logic (stock_name, logic, date, source)
            VALUES (?, ?, ?, ?)
        ''', (stock_name, logic, date, source))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存股票逻辑到数据库失败: {e}")
        return False


def get_stock_logic_from_db(start_date=None, end_date=None, stock_name=None, logic_content=None):
    """从数据库获取股票逻辑"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        query = "SELECT * FROM stock_logic WHERE 1=1"
        params = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if stock_name:
            query += " AND stock_name = ?"
            params.append(stock_name)
        if logic_content:
            query += " AND logic LIKE ?"
            params.append(f'%{logic_content}%')
        query += " ORDER BY date DESC, created_at DESC"
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        columns = ['id', 'stock_name', 'logic', 'date', 'source', 'created_at']
        return [dict(zip(columns, row)) for row in results]
    except Exception as e:
        print(f"获取股票逻辑失败: {e}")
        return []


def delete_stock_logic_from_db(logic_id):
    """从数据库删除股票逻辑"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM stock_logic WHERE id = ?', (logic_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"删除股票逻辑失败: {e}")
        return False


def update_stock_logic_in_db(logic_id, stock_name=None, logic=None, date=None, source=None):
    """更新数据库中的股票逻辑"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        updates = []
        params = []
        if stock_name is not None:
            updates.append("stock_name = ?")
            params.append(stock_name)
        if logic is not None:
            updates.append("logic = ?")
            params.append(logic)
        if date is not None:
            updates.append("date = ?")
            params.append(date)
        if source is not None:
            updates.append("source = ?")
            params.append(source)
        if updates:
            params.append(logic_id)
            query = f"UPDATE stock_logic SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"更新股票逻辑失败: {e}")
        return False

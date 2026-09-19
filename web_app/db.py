"""SQLite 路径与表初始化：与 desktop `stockyidong.py` 中 `init_database` 对齐。"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# 数据根目录（与 desktop 一致）
D_DATA_DIR = (os.environ.get("STOCK_ANALYZER_DATA_DIR") or r"D:\StockAnalyzer").strip() or r"D:\StockAnalyzer"
D_DB_DIR = os.path.join(D_DATA_DIR, "Database")

_WEB_APP_DIR = Path(__file__).resolve().parent
_STOCKYIDONG_PROJECT_ROOT = _WEB_APP_DIR.parent
_PROJECT_LOCAL_DB = _STOCKYIDONG_PROJECT_ROOT / "data" / "stock_analysis.db"

_db_override = (
    (os.environ.get("STOCK_ANALYSIS_DB") or os.environ.get("STOCK_ANALYSIS_DB_PATH") or "")
    .strip()
    .strip('"')
)
if _db_override:
    DB_PATH = str(Path(_db_override).expanduser().resolve())
elif _PROJECT_LOCAL_DB.is_file():
    DB_PATH = str(_PROJECT_LOCAL_DB.resolve())
else:
    DB_PATH = str(Path(D_DB_DIR) / "stock_analysis.db")

HOLDINGS_JSON = _STOCKYIDONG_PROJECT_ROOT / "web_data" / "holdings_state.json"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_database() -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_logic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_name TEXT NOT NULL,
            logic TEXT,
            date TEXT NOT NULL,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_name TEXT NOT NULL,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute(
        """
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
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ths_stock_code ON ths_realtime_data(stock_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ths_save_date ON ths_realtime_data(save_date)")
    conn.commit()
    conn.close()
    HOLDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH

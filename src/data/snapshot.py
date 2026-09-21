# 迁移自 stockyidong mac003.py ranges=[(347, 425), (426, 490)]
import re
import sqlite3
from collections import Counter
from datetime import datetime
from utils.config import DB_PATH
import logic.stock_names as _stock_names  # ⚠️ 不用 from xxx import *,避免 L10 的 STOCK_CODES_DICT={} 脱钩

def _get_codes():
    """每次实时取 logic.stock_names.STOCK_CODES_DICT 最新值,避免跨模块变量赋值脱钩"""
    try:
        load_fn = getattr(_stock_names, "load_stock_names", None)
        if load_fn:
            load_fn()
    except Exception:
        pass
    d = _stock_names.STOCK_CODES_DICT
    return d if (d is not None and len(d) > 0) else None

def get_news_stocks_by_date_and_frequency(ndays=8, meta=None):
    """从 news_info 按日期分组,每日期合并 content 提取股票并按出现频次降序,返回最近 ndays 天的数据。
    返回: [{"date_ymd": "YYYY-MM-DD", "date_mmdd": "MMDD", "stocks": [(name, code), ...]}, ...],最多 ndays 项。
    若 meta 传入 dict,会写入诊断字段(reason、error、news_row_count 等),便于界面提示。"""
    if meta is not None:
        meta.clear()
        meta["ndays"] = ndays
    STOCK_CODES_DICT = _get_codes()
    if STOCK_CODES_DICT is None:
        if meta is not None:
            meta["reason"] = "no_stock_dict"
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"从资讯表读取失败: {e}")
        print(f"  数据库: {DB_PATH}")
        print(
            "  若含 disk full:请保证 D: 上数据目录有足够空间;本程序启动时已尽量将 SQLITE_TMPDIR/TEMP 指到 <数据目录>\\temp。"
            " 若仍报错请彻底退出后重开,或手动设置 SQLITE_TMPDIR 后再启动。"
        )
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
    # 按日期分组 (created_at 格式 "YYYY-MM-DD HH:MM:SS")
    by_date = {}
    for row in rows:
        _rid, _tab_name, content, created_at = row
        if not created_at:
            continue
        date_ymd = created_at[:10] if len(created_at) >= 10 else created_at
        if date_ymd not in by_date:
            by_date[date_ymd] = []
        if content:
            by_date[date_ymd].append(content)
    # 取最近 ndays 个日期(按日期降序)
    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    if not sorted_dates:
        if meta is not None:
            meta["reason"] = "no_valid_dates"
            meta["hint"] = "news_info 有记录但 created_at 为空或格式异常,无法按日归类。"
        return []
    result = []
    total_parsed_codes = 0
    for date_ymd in sorted_dates:
        merged = " ".join(by_date[date_ymd])
        codes = re.findall(r'\d{6}', merged)
        valid = [c for c in codes if c in STOCK_CODES_DICT]
        counter = Counter(valid)
        most_common = counter.most_common(80)
        stocks = [(STOCK_CODES_DICT[code], code) for code, _ in most_common]
        total_parsed_codes += len(stocks)
        date_mmdd = date_ymd[5:7] + date_ymd[8:10]  # MMDD
        result.append({"date_ymd": date_ymd, "date_mmdd": date_mmdd, "stocks": stocks})
    if meta is not None:
        meta["days_with_news"] = len(result)
        meta["total_stock_slots"] = total_parsed_codes
        if total_parsed_codes == 0:
            meta["reason"] = "no_codes_in_news"
            meta["hint"] = (
                "资讯正文里没有出现可识别的 A 股六位代码(或代码不在本地股票字典中)。"
                "请先确认已加载股票列表,且资讯内容含 600519 这类代码。"
            )
    return result

def get_news_stocks_merged_recent_days(ndays=5, meta=None):
    """从 news_info 取最近 ndays 个「有资讯的日期」,合并这些日期的全部正文,按六位代码出现频次降序,返回 [(name, code), ...] 最多 80 条。"""
    if meta is not None:
        meta.clear()
        meta["ndays"] = ndays
    STOCK_CODES_DICT = _get_codes()
    if STOCK_CODES_DICT is None:
        if meta is not None:
            meta["reason"] = "no_stock_dict"
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"从资讯表读取失败: {e}")
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
    by_date = {}
    for row in rows:
        _rid, _tab_name, content, created_at = row
        if not created_at:
            continue
        date_ymd = created_at[:10] if len(created_at) >= 10 else created_at
        if date_ymd not in by_date:
            by_date[date_ymd] = []
        if content:
            by_date[date_ymd].append(content)
    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    if not sorted_dates:
        if meta is not None:
            meta["reason"] = "no_valid_dates"
            meta["hint"] = "news_info 有记录但 created_at 为空或格式异常,无法按日归类。"
        return []
    merged = " ".join(piece for d in sorted_dates for piece in by_date[d])
    codes = re.findall(r"\d{6}", merged)
    valid = [c for c in codes if c in STOCK_CODES_DICT]
    counter = Counter(valid)
    most_common = counter.most_common(80)
    stocks = [(STOCK_CODES_DICT[code], code) for code, _ in most_common]
    if meta is not None:
        meta["days_merged"] = len(sorted_dates)
        meta["merged_dates_ymd"] = sorted_dates
        meta["total_stock_slots"] = len(stocks)
        if not stocks:
            meta["reason"] = "no_codes_in_news"
            meta["hint"] = (
                "资讯正文里没有出现可识别的 A 股六位代码(或代码不在本地股票字典中)。"
                "请先确认已加载股票列表,且资讯内容含 600519 这类代码。"
            )
    return stocks

__all__ = ['get_news_stocks_by_date_and_frequency', 'get_news_stocks_merged_recent_days']

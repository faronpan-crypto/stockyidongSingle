"""从 news_info 按日汇总六位代码频次，与 desktop `get_news_stocks_by_date_and_frequency` 一致。"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from typing import Any

from .db import get_connection
from .stock_dict import load_stock_codes_dict


def get_news_stocks_by_date_and_frequency(ndays: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {"ndays": ndays}
    codes_dict = load_stock_codes_dict()
    if not codes_dict:
        meta["reason"] = "no_stock_dict"
        meta["hint"] = "请运行桌面版生成 stock_names_cache.json 或安装 akshare 后重试。"
        return [], meta
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        meta["reason"] = "db_error"
        meta["error"] = str(e)
        return [], meta

    meta["news_row_count"] = len(rows)
    if not rows:
        meta["reason"] = "no_rows"
        return [], meta

    by_date: dict[str, list[str]] = {}
    for _rid, _tab, content, created_at in rows:
        if not created_at:
            continue
        date_ymd = created_at[:10] if len(str(created_at)) >= 10 else str(created_at)
        by_date.setdefault(date_ymd, [])
        if content:
            by_date[date_ymd].append(content)

    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    if not sorted_dates:
        meta["reason"] = "no_valid_dates"
        return [], meta

    result = []
    total_parsed = 0
    for date_ymd in sorted_dates:
        merged = " ".join(by_date[date_ymd])
        found = re.findall(r"\d{6}", merged)
        valid = [c for c in found if c in codes_dict]
        counter = Counter(valid)
        most_common = counter.most_common(80)
        stocks = [{"name": codes_dict[code], "code": code} for code, _ in most_common]
        total_parsed += len(stocks)
        date_mmdd = date_ymd[5:7] + date_ymd[8:10]
        result.append(
            {"date_ymd": date_ymd, "date_mmdd": date_mmdd, "stocks": stocks}
        )
    meta["days_with_news"] = len(result)
    meta["total_stock_slots"] = total_parsed
    if total_parsed == 0:
        meta["reason"] = "no_codes_in_news"
    return result, meta

#!/usr/bin/env python3
"""
将「半导体清洗设备招投标监测报告」写入 stockyidong_mac 的 news_info 表。

用法:
  python3 save_bid_report.py report.md          # 写入文件内容
  cat report.md | python3 save_bbid_report.py   # 从 stdin 读取
  python3 save_bid_report.py report.md --date 2026-07-24   # 指定日期(默认今天)

写入规则:
  tab_name = "🧪 半导体清洗设备招投标｜YYYY-MM-DD"
  同一天若存在旧报告则先删除再插入(整日仅保留最新一份)。
  workspace 顶层文件由 lobster-daily-sync 统一管理（每次同步时写入）。

⚠️ 注意：不要在此脚本内直接写 workspace 文件，
         应由 lobster-daily-sync 每3小时统一写入，避免 mtime 冲突导致重复同步。
"""

import argparse
import datetime
import os
import sqlite3
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_DB = os.path.join(_PROJECT_ROOT, "data", "stock_analysis.db")

TAB_PREFIX = "🧪 半导体清洗设备招投标｜"


def read_content(path=None):
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def save(content: str, date_str: str) -> int:
    tab_name = TAB_PREFIX + date_str
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    con = sqlite3.connect(_PROJECT_DB)
    cur = con.cursor()
    # 去重：同日期先删后插
    cur.execute("DELETE FROM news_info WHERE tab_name = ?", (tab_name,))
    cur.execute(
        "INSERT INTO news_info (tab_name, content, created_at, updated_at) VALUES (?,?,?,?)",
        (tab_name, content, now, now),
    )
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return new_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="-", help="报告 .md 路径，缺省读 stdin")
    ap.add_argument("--date", default=datetime.date.today().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    content = read_content(args.path).strip()
    if not content:
        print("错误: 报告内容为空", file=sys.stderr)
        sys.exit(1)
    new_id = save(content, args.date)
    print(f"✅ 已写入 news_info: id={new_id} | tab_name={TAB_PREFIX}{args.date} | 字数={len(content)}")
    print("   （文件由 lobster-daily-sync 统一管理写入 workspace，勿在此脚本内操作）")


if __name__ == "__main__":
    main()

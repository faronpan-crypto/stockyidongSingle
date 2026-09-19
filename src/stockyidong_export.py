#!/usr/bin/env python3
"""
stockyidong_export.py
读取 stockyidong_mac.py 持仓数据，输出到同名文件夹。

用法：
  python3 stockyidong_export.py                    # 输出到脚本同目录
  python3 stockyidong_export.py --out ~/Desktop/   # 指定输出目录
"""

import argparse
import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config", "ai_config.json")

TABS = [
    ("holding_stocks_2", "龙头股标签页"),
    ("holding_stocks_3", "15Min标签页"),
    ("holding_stocks_6", "同花顺标签页"),
]

def load_holdings():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def format_holdings(config):
    lines = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"StockYiDong 持股导出  ({now_str})")
    lines.append("=" * 50)
    for key, tab_name in TABS:
        stocks = config.get(key, [])
        valid = [s for s in stocks if s.get("stock_name", "").strip()]
        if valid:
            stock_list = "、".join(
                f"{s['stock_name']}({s['stock_code']})"
                for s in valid
            )
        else:
            stock_list = "（无）"
        lines.append(f"\n【{tab_name}】")
        lines.append(stock_list)
        lines.append(f"共 {len(valid)} 只\n")
    return "\n".join(lines)

def export(out_dir=None):
    if out_dir is None:
        out_dir = SCRIPT_DIR
    config = load_holdings()
    content = format_holdings(config)
    os.makedirs(out_dir, exist_ok=True)
    now = datetime.now()
    filename = f"stockyidong_{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}.txt"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath, content

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    filepath, content = export(args.out)
    print(f"[OK] 已导出: {filepath}")
    print("\n" + content)
"""HotMixin 迁移脚本 - 最简化版, 逐行复制"""
import ast, sys, os

MAIN = "stockyidong mac003.py"
with open(MAIN, 'r', encoding='utf-8') as f:
    all_lines = f.readlines()  # 每行都带 \n

tree = ast.parse("".join(all_lines))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "StockKeywordAnalyzerGUI")

KEYWORDS = ["hot", "热门", "概念", "板块", "sector", "行业", "领涨", "hotmoney", "北向", "资金流向"]
hot_nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef) 
             and any(k in n.name.lower() for k in KEYWORDS)]
hot_nodes.sort(key=lambda n: n.lineno)
print(f"找到 {len(hot_nodes)} 个 Hot 方法")

# ====== 1. 写 ui/tab_hot.py ======
with open("ui/tab_hot.py", 'w', encoding='utf-8') as out:
    # 头
    out.write('"""HotMixin - 热门/板块/北向/hotmoney"""\n')
    out.write('import os, sys, re, json, time, threading, traceback\n')
    out.write('import tkinter as tk\n')
    out.write('from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext\n')
    out.write('try: import pandas as pd\nexcept: pd = None\n')
    out.write('try: import akshare as ak\nexcept: ak = None\n')
    out.write('from utils.network import safe_call\n')
    out.write('\n\nclass HotMixin:\n')
    out.write('    """热门板块/选股/北向资金/hotmoney"""\n')
    out.write('\n')
    
    # 逐方法逐行写
    for idx, node in enumerate(hot_nodes):
        s, e = node.lineno, getattr(node, 'end_lineno', node.lineno)
        for j in range(s-1, e):
            out.write(all_lines[j])  # 原始行, 带 \n
        out.write('\n')  # 方法间空行
    
    out.write('\n__all__ = ["HotMixin"]\n')

# 验证
with open("ui/tab_hot.py") as f: content = f.read()
try:
    ast.parse(content)
    print(f"✅ ui/tab_hot.py 语法 OK ({content.count(chr(10))} 行)")
except SyntaxError as e:
    print(f"❌ HotMixin 语法错误 L{e.lineno}: {e.msg}")
    sys.exit(1)

# ====== 2. 重写主文件 ======
# 构建 remove set (含装饰器)
remove_set = set()
for node in hot_nodes:
    s, e = node.lineno, getattr(node, 'end_lineno', node.lineno)
    for ln in range(s, e+1):
        remove_set.add(ln)
    for ln in range(s-2, max(0, s-15), -1):
        stripped = all_lines[ln].lstrip()
        if stripped.startswith('@') or stripped.strip() == '':
            remove_set.add(ln + 1)
        else:
            break

# 逐行写主文件
with open(MAIN, 'w', encoding='utf-8') as out:
    cls_idx = None
    wrote_hot_import = False
    for i, line in enumerate(all_lines):
        ln = i + 1
        if ln in remove_set:
            continue
        
        # 加 HotMixin import (在 Wencai 之后)
        if "from ui.tab_wencai import WencaiMixin" in line and not wrote_hot_import:
            out.write(line)
            out.write("from ui.tab_hot import HotMixin\n")
            wrote_hot_import = True
            continue
        
        # 改类签名
        if line.startswith("class StockKeywordAnalyzerGUI"):
            cls_idx = i
            # 改 "...WencaiMixin):" → "...WencaiMixin, HotMixin):"
            import re
            new_line = re.sub(
                r'(class StockKeywordAnalyzerGUI\([^)]+\))\)(\s*)$',
                lambda m: m.group(1) + ", HotMixin):" + m.group(2),
                line
            )
            out.write(new_line)
            continue
        
        out.write(line)

# 验证
with open(MAIN) as f: main_content = f.read()
try:
    ast.parse(main_content)
    print(f"✅ 主文件语法通过 (减 {len(all_lines) - main_content.count(chr(10))} 行)")
except SyntaxError as e:
    print(f"❌ 主文件语法错误 L{e.lineno}: {e.msg}")
    sys.exit(1)

print("\n🎉 HotMixin 迁移完成!")

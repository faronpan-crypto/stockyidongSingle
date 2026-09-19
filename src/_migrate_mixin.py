"""
Mixin 迁移通用脚本 — 经过 7 次实战验证

用法: python3 _migrate_mixin.py <mixin_class_name> <target_file> "<关键词列表>"
示例: python3 _migrate_mixin.py HotMixin ui/tab_hot.py "hot 热门 概念"

设计原则:
  1. AST 精确边界 (避免任意行范围切穿函数体)
  2. readlines() → 逐行处理 → writelines() (永不丢 \n)
  3. 类签名用 splitlines(True) + regex 改 + \n 自动保留
  4. 自动补 self (AST 扫参, 发现缺 self 则精确插入)
  5. import 插在最后一个 tab import 之后
  6. 全局变量注入: 在主文件已有的 try: NameError 块里追加
"""
import ast, sys, os, re, traceback

MAIN_FILE = "stockyidong mac003.py"


def scan_class_methods(source_lines):
    """AST 扫描主类所有方法, 返回 {name: (start, end)}"""
    tree = ast.parse("".join(source_lines))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                and n.name == "StockKeywordAnalyzerGUI"), None)
    if not cls:
        print("❌ 找不到 StockKeywordAnalyzerGUI 类"); sys.exit(1)
    return {node.name: (node.lineno, getattr(node, 'end_lineno', node.lineno))
            for node in cls.body if isinstance(node, ast.FunctionDef)}


def find_target_methods(all_methods, keywords):
    """按关键词匹配要迁移的方法, 返回 [(start, end, name)]"""
    kws = [k.lower() for k in keywords]
    matched = []
    for name, (s, e) in all_methods.items():
        nlower = name.lower()
        if any(k in nlower for k in kws):
            matched.append((s, e, name))
    matched.sort()
    return matched


def fix_missing_self(source_lines, indent=4):
    """扫描类内方法签名, 第一参数不是 self 则补"""
    fixed = 0
    content = "".join(source_lines)
    tree = ast.parse(content)
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    args = [a.arg for a in m.args.args]
                    if args and args[0] != 'self':
                        # 精确替换: 找到 "    def func(" → "    def func(self, "
                        old = f'{indent*" "}def {m.name}('
                        idx = content.find(old)
                        if idx >= 0:
                            paren = content.index('(', idx)
                            content = content[:paren+1] + 'self, ' + content[paren+1:]
                            fixed += 1
            break
    if fixed:
        source_lines = content.splitlines(True)
    return source_lines, fixed


def modify_class_signature(lines, new_mixin_name):
    """改类签名, 用 splitlines(True) 确保 \n 永不丢失"""
    for i, line in enumerate(lines):
        if line.startswith("class StockKeywordAnalyzerGUI"):
            # splitlines(True) 保留换行
            parts = [line.rstrip('\n'), line[-1] if line.endswith('\n') else '']
            body = parts[0]
            nl = parts[1]  # '\n' 或 ''

            # 在最后一个 ) 之前插入新 Mixin
            # body 形如: class StockKeywordAnalyzerGUI(FooMixin, BarMixin):
            # 我们要在 BarMixin 后加 , NewMixin
            body = re.sub(
                r'(class StockKeywordAnalyzerGUI\(\w[\w, ]*\w)\):\s*$',
                lambda m: m.group(1).rstrip() + f", {new_mixin_name}):",
                body
            )
            lines[i] = body + nl
            return i  # 返回类签名行索引
    return None


def insert_mixin_import(lines, mixin_file, mixin_name):
    """import 插在最后一个 tab import 之后"""
    last_tab_import = -1
    for i, line in enumerate(lines):
        if re.match(r'from ui\.tab_\w+ import \w+Mixin', line):
            last_tab_import = i
    if last_tab_import >= 0:
        lines.insert(last_tab_import + 1, f"from ui.{mixin_file} import {mixin_name}\n")
    else:
        # 兜底: 在 class 之前
        for i, line in enumerate(lines):
            if line.startswith("class StockKeywordAnalyzerGUI"):
                lines.insert(i, f"from ui.{mixin_file} import {mixin_name}\n")
                break


def inject_globals_for_mixin(lines, mixin_var_name, needed_globals):
    """在主文件的 Phase 3 全局变量注入块末尾追加"""
    # 找到最后一个 except NameError: pass (就是 _mod_spot.TS_DEFAULT_TOKEN 那个块)
    # 然后在它之后插入
    anchor = "    _mod_spot.TS_DEFAULT_TOKEN = TS_DEFAULT_TOKEN"
    anchor_idx = None
    for i, line in enumerate(lines):
        if anchor in line:
            # 往下找 except NameError: pass 的结束
            for j in range(i+1, min(i+10, len(lines))):
                if lines[j].strip() == "pass":
                    anchor_idx = j
                    break
            break
    if anchor_idx is None:
        return

    inject_lines = [
        f"\n# {mixin_var_name} 需要的全局变量\n",
        f"try:\n",
        f"    import ui.{mixin_var_name} as _mod_{mixin_var_name}\n",
    ]
    for g in needed_globals:
        inject_lines.append(f"    _mod_{mixin_var_name}.{g} = {g}\n")
    inject_lines.append("except NameError:\n    pass\n")

    lines[anchor_idx+1:anchor_idx+1] = inject_lines


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    mixin_name = sys.argv[1]          # e.g. CangweiMixin
    target_file = sys.argv[2]         # e.g. ui/tab_cangwei.py
    keywords = sys.argv[3].split()    # e.g. ["cangwei", "仓位", "holding"]

    # 可选的全局变量注入列表
    needed_globals = sys.argv[4].split() if len(sys.argv) > 4 else []

    print(f"\n{'='*60}")
    print(f"🔧 迁移: {mixin_name} → {target_file}")
    print(f"   关键词: {keywords}")
    if needed_globals:
        print(f"   需要全局变量注入: {needed_globals}")
    print(f"{'='*60}\n")

    # 1. 读主文件
    with open(MAIN_FILE, 'r', encoding='utf-8') as f:
        main_lines = f.readlines()
    before_count = len(main_lines)
    print(f"📖 主文件: {before_count} 行")

    # 2. AST 扫描
    all_methods = scan_class_methods(main_lines)
    matched = find_target_methods(all_methods, keywords)
    if not matched:
        print("❌ 没匹配到任何方法!"); sys.exit(1)
    total = sum(e-s+1 for s, e, _ in matched)
    print(f"🎯 匹配: {len(matched)} 方法 / {total} 行")

    # 3. 构建 remove set (含前置装饰器)
    remove_lines = set()
    for s, e, _ in matched:
        for ln in range(s, e+1):
            remove_lines.add(ln)
        # 回溯前置装饰器 (@staticmethod, @contextmanager, etc.)
        # 注意: s 是方法起始行 (1-based), s-1 是方法定义行 (0-based ln = s-2)
        # 从方法定义行的上一行开始回查
        for ln in range(s-2, max(0, s-15), -1):
            stripped = main_lines[ln].lstrip()
            if stripped.startswith('@'):
                remove_lines.add(ln + 1)  # 行号从 1 开始
            elif stripped.strip() == '':
                # 装饰器之间的空行也删, 避免残留
                remove_lines.add(ln + 1)
            else:
                break

    # 4. 构建完整 Mixin 文件 (含类包装 + 导入), 再 parse + 补 self
    print(f"📝 构建 {target_file}...")
    mixin_body_lines = []
    for s, e, name in matched:
        mixin_body_lines.extend(main_lines[s-1:e])

    # 先拼个带 class 包装的完整代码用于 parse / fix_missing_self
    INDENT = 4
    class_pkg_prefix = " "*INDENT
    # 构造一个临时"假文件"让 AST 能 parse
    fake_header = (
        'import os, sys, re, json, time, threading, traceback\n'
        'import tkinter as tk\n'
        'class _TemporaryMixinWrapper:\n'
    )
    # 方法体已经是 4 空格缩进 (原 class 内的), 所以直接拼在 class 下
    fake_content = fake_header + "".join(mixin_body_lines)

    # 补 self (对 fake_content 做 AST 扫参)
    fixed = 0
    tree = ast.parse(fake_content)
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    args = [a.arg for a in m.args.args]
                    if args and args[0] != 'self':
                        old = f'{INDENT*" "}def {m.name}('
                        idx = fake_content.find(old)
                        paren = fake_content.index('(', idx)
                        fake_content = fake_content[:paren+1] + 'self, ' + fake_content[paren+1:]
                        mixin_body_lines = fake_content.splitlines(True)[3:]  # 跳过 3 行 header
                        fixed += 1
            break
    if fixed:
        print(f"   🔧 补了 {fixed} 个 self")

    # 构建完整 Mixin 文件
    mixin_filename = os.path.basename(target_file)
    imports_block = (
        'import os, sys, re, json, time, threading, traceback, sqlite3\n'
        'import tkinter as tk\n'
        'from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext\n\n'
        'try:\n'
        '    import numpy as np\n'
        'except ImportError: np = None\n'
        'try:\n'
        '    import pandas as pd\n'
        'except ImportError: pd = None\n\n'
        'from utils.network import safe_call\n'
        'try:\n'
        '    import akshare as ak\n'
        'except ImportError: ak = None\n'
        'try:\n'
        '    import tushare as ts\n'
        'except ImportError: ts = None\n\n\n'
    )
    full_content = imports_block + f'class {mixin_name}:\n    """{mixin_name}"""\n\n' + "".join(mixin_body_lines)
    full_content += f'\n\n__all__ = ["{mixin_name}"]\n'

    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(full_content)
    try:
        ast.parse(full_content)
        print(f"   ✅ {target_file} 语法 OK")
    except SyntaxError as e:
        print(f"   ❌ {target_file} 语法错误: {e}"); sys.exit(1)

    # 5. 重写主文件
    new_lines = []
    for i, line in enumerate(main_lines):
        ln = i + 1
        if ln in remove_lines:
            continue
        new_lines.append(line)

    # 6. 改类签名
    cls_idx = modify_class_signature(new_lines, mixin_name)
    if cls_idx is not None:
        print(f"   ✅ 类签名: {new_lines[cls_idx].strip()}")

    # 7. 插 import
    mixin_basename = target_file.replace("ui/", "").replace(".py", "")
    insert_mixin_import(new_lines, mixin_basename, mixin_name)
    print(f"   ✅ 已插入 import")

    # 8. 写回主文件
    with open(MAIN_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    after_count = len(new_lines)
    print(f"\n📊 主文件: {before_count} → {after_count} (减 {before_count - after_count} 行)")

    # 9. 语法检查
    try:
        ast.parse("".join(new_lines))
        print("✅ 主文件语法通过")
    except SyntaxError as e:
        print(f"❌ 语法错误: {e}")
        traceback.print_exc()
        sys.exit(1)

    # 10. 全局变量注入
    if needed_globals:
        # 重新读 (已经写回)
        with open(MAIN_FILE, 'r', encoding='utf-8') as f:
            inject_lines = f.readlines()
        inject_globals_for_mixin(inject_lines, mixin_basename, needed_globals)
        with open(MAIN_FILE, 'w', encoding='utf-8') as f:
            f.writelines(inject_lines)
        print(f"   ✅ 全局变量注入完成")
        try:
            ast.parse("".join(inject_lines))
            print("   ✅ 注入后主文件语法 OK")
        except SyntaxError as e:
            print(f"   ❌ 注入后语法错误: {e}")
            sys.exit(1)

    print(f"\n🎉 {mixin_name} 迁移完成!")
    print(f"   运行: python3 '{MAIN_FILE}'")


if __name__ == "__main__":
    main()

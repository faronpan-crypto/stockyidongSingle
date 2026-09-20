"""
自动修复循环: 启动 GUI → 扫日志里的 NameError/AttributeError → 自动补 import → 重启 → 迭代
用法: python3 _auto_fix.py [max_iterations=10]
"""
import subprocess, time, os, re, sys, glob, ast, signal

SRC = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(SRC, "stockyidong mac003.py")
LOG = "/tmp/auto_fix.log"
PY311 = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

# 所有可 import 的符号 (模块 → [符号列表])
MODULE_SYMBOLS = {
    "utils.config": ["*"],
    "logic.stock_names": ["*"],
    "logic.dapan_fetcher": ["*"],
    "logic.indicators": ["*"],
    "logic.spot": ["*"],
    "logic.wordcloud": ["*"],
    "logic.crawlers": ["*"],
    "data.db": ["*"],
    "data.snapshot": ["*"],
    "utils.network": ["*"],
    "utils.suppress": ["*"],
    "utils.text_extract": ["*"],
}
# 额外的具体符号映射 (一些函数在子模块里但我们显式 import *)
KNOWN_FALLBACKS = {
    "jieba": ["import jieba"],
    "datetime": ["from datetime import datetime, timedelta"],
    "timedelta": ["from datetime import timedelta"],
    "sqlite3": ["import sqlite3"],
}

def kill_gui():
    subprocess.run(["pkill", "-9", "-f", "mac003|stockyidong"], 
                   capture_output=True, timeout=5)
    time.sleep(1)

def clean_cache():
    for d in ["__pycache__", "ui/__pycache__", "logic/__pycache__", 
              "data/__pycache__", "utils/__pycache__", "config/__pycache__"]:
        p = os.path.join(SRC, d)
        if os.path.isdir(p):
            subprocess.run(["rm", "-rf", p], capture_output=True)

def launch_gui():
    """启动 GUI, 返回 PID"""
    with open(LOG, "w") as f:
        p = subprocess.Popen(
            [PY311, "-u", MAIN], cwd=SRC,
            stdout=f, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid  # 独立进程组
        )
    return p.pid

def read_log():
    try:
        with open(LOG) as f:
            return f.read()
    except:
        return ""

def extract_name_errors(log):
    """从日志里提取所有 NameError: name 'XXX' is not defined 中的 XXX"""
    errors = []
    # Pattern 1: name 'get_xxx' is not defined
    for m in re.finditer(r"name '([a-zA-Z_][a-zA-Z0-9_]*)' is not defined", log):
        name = m.group(1)
        if name not in ("Exception", "self", "cls"):
            errors.append(name)
    # Pattern 2: AttributeError: 'NoneType' object has no attribute 'xxx'
    # (不处理, 那是运行时逻辑错, 不是缺 import)
    return list(set(errors))

def find_tab_uses(name, tabs):
    """哪些 tab 文件用了这个名字"""
    users = []
    for f in tabs:
        try:
            content = open(f).read()
            # 简单匹配: 非 import 行里有这个名字
            for line in content.split("\n"):
                if name in line and not line.startswith("import") and not line.startswith("from"):
                    # 更精确: \bname\b
                    if re.search(rf'\b{re.escape(name)}\b', line):
                        users.append(f)
                        break
        except:
            pass
    return users

def find_module_for_name(name):
    """找到这个名字应该从哪个模块 import"""
    # 遍历所有子模块, 看谁 export 了这个名字
    for mod_path, mod_name in [
        ("utils/config.py", "utils.config"),
        ("logic/stock_names.py", "logic.stock_names"),
        ("logic/dapan_fetcher.py", "logic.dapan_fetcher"),
        ("logic/indicators.py", "logic.indicators"),
        ("logic/spot.py", "logic.spot"),
        ("logic/wordcloud.py", "logic.wordcloud"),
        ("logic/crawlers.py", "logic.crawlers"),
        ("data/db.py", "data.db"),
        ("data/snapshot.py", "data.snapshot"),
        ("utils/network.py", "utils.network"),
        ("utils/suppress.py", "utils.suppress"),
        ("utils/text_extract.py", "utils.text_extract"),
    ]:
        full = os.path.join(SRC, mod_path)
        if not os.path.exists(full): continue
        try:
            src = open(full).read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == name:
                        return mod_name
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == name:
                            return mod_name
        except:
            continue
    # stdlib fallback
    if name in ("datetime", "timedelta"):
        return "datetime_stdlib"
    if name == "sqlite3":
        return "sqlite3_stdlib"
    if name == "jieba":
        return "jieba_third"
    return None

def add_import(filepath, import_line):
    """给文件加一行 import, 如果还没有"""
    content = open(filepath).read()
    if import_line in content:
        return False
    # 加在文件最开头 (跳过注释和空行)
    lines = content.split("\n")
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith("#"):
            insert_at = i
            break
    lines.insert(insert_at, import_line)
    open(filepath, "w").write("\n".join(lines))
    return True

def main():
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    tabs = sorted(glob.glob(os.path.join(SRC, "ui/tab_*.py")))
    
    print(f"🚀 自动修复循环 (最多 {max_iter} 轮)")
    print(f"   目标: {len(tabs)} 个 tab 文件")
    print()
    
    total_fixes = 0
    
    for iteration in range(1, max_iter + 1):
        print(f"=== 第 {iteration} 轮 ===")
        
        # 1. 清理 + 启动
        kill_gui()
        clean_cache()
        pid = launch_gui()
        print(f"   启动 PID={pid}, 等待 12s ...")
        time.sleep(12)
        
        # 2. 读日志
        log = read_log()
        errors = extract_name_errors(log)
        
        # 过滤掉 Tushare 限频等噪音
        errors = [e for e in errors if "Tushare" not in e and "akshare" not in e]
        
        if not errors:
            print(f"   ✅ 零 NameError! 🎉")
            break
        
        print(f"   发现 {len(errors)} 个 NameError: {errors[:5]}{'...' if len(errors)>5 else ''}")
        
        # 3. 逐个修复
        round_fixes = 0
        for name in errors:
            mod = find_module_for_name(name)
            if not mod:
                print(f"   ⚠️  找不到 '{name}' 在哪个模块, 跳过")
                continue
            
            # 确定 import 行
            if mod == "datetime_stdlib":
                import_line = "from datetime import datetime, timedelta"
            elif mod == "sqlite3_stdlib":
                import_line = "import sqlite3"
            elif mod == "jieba_third":
                import_line = "try:\n    import jieba\nexcept ImportError:\n    jieba = None"
            else:
                import_line = f"from {mod} import *"
            
            # 找哪些 tab 用了这个名字
            users = find_tab_uses(name, tabs)
            if not users:
                # 可能是在主文件里用的
                users = [MAIN]
            
            for f in users:
                if add_import(f, import_line):
                    round_fixes += 1
                    print(f"      + {os.path.basename(f)} ← {import_line.split(chr(10))[0]} (for '{name}')")
        
        total_fixes += round_fixes
        print(f"   本轮修了 {round_fixes} 处")
    
    kill_gui()
    print(f"\n🎉 完成! 总共修了 {total_fixes} 处 import")
    print(f"   日志: {LOG}")

if __name__ == "__main__":
    main()

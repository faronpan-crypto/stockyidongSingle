"""
Phase 2 精确迁移脚本 — 用 AST 边界确保完整函数体。
"""
import os, sys, re, ast

MAIN = "stockyidong mac003.py"
with open(MAIN, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"原主文件: {len(lines)} 行")

# ============ 精确分桶 (AST 边界) ============
# 每个桶: (target, [(start, end), ...], imports_block, is_append)
# 范围都包含了全局变量 + 它们下面的函数

buckets = [
    # --- utils/suppress.py ---
    {
        "target": "utils/suppress.py",
        "ranges": [(97, 109), (110, 124), (126, 136), (137, 151), (153, 161)],
        "imports": (
            "import os\n"
            "import sys\n"
            "import contextlib\n"
            "import io\n"
            "import warnings\n"
        ),
    },
    # --- utils/config.py (追加 _ts_patch + _akshare_fund_flow + 常量) ---
    {
        "target": "utils/config.py",
        "ranges": [(173, 174), (176, 214), (225, 236), (3010, 3045), (3046, 3073)],
        "imports": (
            "import sys\n"
            "import time\n"
            "import threading\n"
            "import json\n"
            "import re\n"
            "from urllib.parse import urljoin\n"
        ),
        "append": True,
    },
    # --- logic/crawlers.py ---
    {
        "target": "logic/crawlers.py",
        "ranges": [(492, 757), (759, 820), (822, 1006)],
        "imports": (
            "import os\n"
            "import sys\n"
            "import re\n"
            "import time\n"
            "import json\n"
            "import base64\n"
            "import requests\n"
            "from bs4 import BeautifulSoup\n"
        ),
    },
    # --- logic/stock_names.py ---
    {
        "target": "logic/stock_names.py",
        "ranges": [(1007, 1024), (1025, 1029), (1030, 1235), (1236, 1361),
                   (1362, 1382), (1383, 1392), (1393, 1438), (1439, 1490)],
        "imports": (
            "import os\n"
            "import sys\n"
            "import re\n"
            "import json\n"
            "import time\n"
            "import sqlite3\n"
            "from collections import Counter\n"
            "# STOCK_CODES_DICT 来自主文件全局变量\n"
        ),
    },
    # --- data/snapshot.py ---
    {
        "target": "data/snapshot.py",
        "ranges": [(347, 425), (426, 490)],
        "imports": (
            "import re\n"
            "from collections import Counter\n"
            "from datetime import datetime\n"
            "from utils.config import DB_PATH\n"
        ),
    },
    # --- logic/dapan_fetcher.py ---
    {
        "target": "logic/dapan_fetcher.py",
        "ranges": [(1493, 1533), (1534, 1546), (1547, 1559), (1562, 1576),
                   (1578, 1592), (1593, 1625), (1626, 1646), (1647, 1666),
                   (1668, 1713),
                   (2016, 2034), (2036, 2038), (2039, 2041), (2042, 2044),
                   (2045, 2104),
                   (2683, 2776)],
        "imports": (
            "import os\n"
            "import sys\n"
            "import re\n"
            "import time\n"
            "try:\n"
            "    import akshare as ak\n"
            "except ImportError:\n"
            "    ak = None\n"
            "try:\n"
            "    import tushare as ts\n"
            "except ImportError:\n"
            "    ts = None\n"
        ),
    },
    # --- logic/indicators.py ---
    {
        "target": "logic/indicators.py",
        "ranges": [(1714, 1732), (1733, 1759), (1760, 1774), (1775, 1788), (1789, 1831)],
        "imports": (
            "import numpy as np\n"
            "import pandas as pd\n"
        ),
    },
    # --- logic/spot.py ---
    {
        "target": "logic/spot.py",
        "ranges": [(1833, 1835), (1837, 1837), (1839, 1839),
                   (1840, 1842), (1843, 1854), (1855, 1861), (1862, 1869),
                   (1870, 1885), (1886, 1901), (1902, 1948), (1949, 1971),
                   (1972, 2015)],
        "imports": (
            "import os\n"
            "import sys\n"
            "import time\n"
            "import threading\n"
            "try:\n"
            "    import akshare as ak\n"
            "    AKSHARE_AVAILABLE = True\n"
            "except ImportError:\n"
            "    AKSHARE_AVAILABLE = False\n"
        ),
    },
    # --- logic/wordcloud.py ---
    {
        "target": "logic/wordcloud.py",
        "ranges": [(2105, 2181), (2182, 2277), (2278, 2423), (2424, 2682)],
        "imports": (
            "import os\n"
            "import sys\n"
            "import re\n"
            "import io\n"
            "import base64\n"
            "import threading\n"
            "import warnings\n"
            "from collections import Counter\n"
            "try:\n"
            "    import jieba\n"
            "except ImportError:\n"
            "    jieba = None\n"
            "try:\n"
            "    import matplotlib\n"
            "    matplotlib.use('TkAgg')\n"
            "    import matplotlib.pyplot as plt\n"
            "except ImportError:\n"
            "    plt = None\n"
            "try:\n"
            "    import numpy as np\n"
            "except ImportError:\n"
            "    np = None\n"
            "try:\n"
            "    import pandas as pd\n"
            "except ImportError:\n"
            "    pd = None\n"
            "try:\n"
            "    from wordcloud import WordCloud\n"
            "except ImportError:\n"
            "    WordCloud = None\n"
            "try:\n"
            "    from PIL import Image, ImageDraw, ImageFont\n"
            "except ImportError:\n"
            "    Image = None\n"
        ),
    },
    # --- utils/text_extract.py ---
    {
        "target": "utils/text_extract.py",
        "ranges": [(2777, 2780), (2781, 2787), (2788, 2817), (2819, 2857),
                   (2858, 2887), (2888, 2908), (2910, 2949), (2950, 2984),
                   (2985, 3009)],
        "imports": (
            "import os\n"
            "import re\n"
            "import io\n"
            "import shutil\n"
            "import tempfile\n"
            "import zipfile\n"
            "from datetime import datetime\n"
            "try:\n"
            "    from bs4 import BeautifulSoup\n"
            "except ImportError:\n"
            "    BeautifulSoup = None\n"
        ),
    },
]

# 收集所有要删除的行
remove_lines = set()
for bucket in buckets:
    for s, e in bucket["ranges"]:
        for ln in range(s, e + 1):
            remove_lines.add(ln)

print(f"待删除行数: {len(remove_lines)}")

# ============ 写目标文件 ============
errors = []
for bucket in buckets:
    target = bucket["target"]
    ranges = sorted(bucket["ranges"], key=lambda x: x[0])
    imports_block = bucket["imports"]
    is_append = bucket.get("append", False)
    
    code_parts = []
    symbols = []
    for start, end in ranges:
        block = "".join(lines[start-1:end])
        code_parts.append(block)
        for m in re.finditer(r'^(def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)', block, re.MULTILINE):
            symbols.append(m.group(2))
        for m in re.finditer(r'^([A-Z][A-Z0-9_]*)\s*=', block, re.MULTILINE):
            symbols.append(m.group(1))
    
    symbols = sorted(set(symbols))
    
    header = f'# 迁移自 stockyidong mac003.py ranges={ranges}\n'
    full_code = imports_block.rstrip() + "\n\n" + "\n".join(code_parts)
    content = header + full_code.rstrip() + f'\n\n__all__ = {symbols}\n'
    
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 立即验证
    try:
        with open(target, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        mark = "📎" if is_append else "✍️"
        print(f"  {mark} {target} ✅ ({len(symbols)} symbols)")
    except SyntaxError as e:
        print(f"  ❌ {target}: {e}")
        errors.append(target)

if errors:
    print(f"\n❌ {len(errors)} 个目标文件语法错误, 停在写主文件之前")
    sys.exit(1)

# ============ 重写主文件 ============
print("\n=== 重写主文件 ===")

IMPORT_BLOCKS = []
for bucket in buckets:
    target = bucket["target"]
    if target == "utils/config.py":
        continue  # Phase 1 已 import
    mod_path = target.replace("/", ".").replace(".py", "")
    ranges_str = ", ".join(f"{s}-{e}" for s, e in sorted(bucket["ranges"]))
    IMPORT_BLOCKS.append(f"from {mod_path} import *  # L{ranges_str}")

IMPORT_BLOCK = "\n# ==================== Phase 2 模块化导入 ====================\n" + "\n".join(IMPORT_BLOCKS) + "\n\n"

new_lines = []
for i, line in enumerate(lines):
    ln = i + 1
    if ln in remove_lines:
        continue
    new_lines.append(line)
    if ln == 76:
        new_lines.append(IMPORT_BLOCK)

with open(MAIN, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"原: {len(lines)} 行 → 新: {len(new_lines)} 行 (减 {len(lines) - len(new_lines)} 行)")

# 验证主文件
try:
    with open(MAIN, 'r', encoding='utf-8') as f:
        ast.parse(f.read())
    print("✅ 主文件语法通过")
except SyntaxError as e:
    print(f"❌ 主文件语法错误: {e}")
    sys.exit(1)

print("\n🎉 Phase 2 迁移完成, 所有文件语法正确!")

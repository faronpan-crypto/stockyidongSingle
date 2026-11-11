# -*- coding: utf-8 -*-
"""
🌐 股票多站同步打开模块

单击股票 → 同时在多个财经网站打开该股票页面

支持网站 (可配置开关):
  • 新浪财经      https://finance.sina.com.cn/realstock/{prefix}{code}.shtml
  • 东方财富      https://quote.eastmoney.com/{prefix}{code}.html
  • 同花顺        http://stockpage.10jqka.com.cn/{code}/
  • 韭研公社      https://www.jiuyangongshe.com/search?q={name}
  • 知乎          https://www.zhihu.com/search?q={name}&type=content
  • 淘股吧        https://www.taoguba.com.cn/search?keyword={name}
  • 选股宝        https://www.xuanstock.com/search?keyword={name}
  • 百度          https://www.baidu.com/s?wd={name}+股票

作者设置持久化: settings.json (每个 key=True/False)
"""

import json, os, webbrowser, threading as _th
from urllib.parse import quote

# ═══════ 网站列表 (按 code/name 格式化) ═══════
SITES = [
    {"key": "sina",     "name": "新浪财经",   "icon": "🔵",
     "fmt_code": "https://finance.sina.com.cn/realstock/{prefix}{code}.shtml",
     "fmt_name": "https://search.sina.com.cn/?q={name}&c=news",
     "default": True},
    {"key": "eastmoney","name": "东方财富",   "icon": "🔴",
     "fmt_code": "https://quote.eastmoney.com/{prefix}{code}.html",
     "fmt_name": "https://so.eastmoney.com/news/s?keyword={name}",
     "default": True},
    {"key": "ths",      "name": "同花顺",     "icon": "🟢",
     "fmt_code": "http://stockpage.10jqka.com.cn/{code}/",
     "fmt_name": "http://search.10jqka.com.cn/search?query={name}",
     "default": True},
    {"key": "jiuyan",   "name": "韭研公社",   "icon": "🥬",
     "fmt_code": None,
     "fmt_name": "https://www.jiuyangongshe.com/search?q={name}",
     "default": False},
    {"key": "zhihu",    "name": "知乎",       "icon": "💬",
     "fmt_code": None,
     "fmt_name": "https://www.zhihu.com/search?q={name}&type=content",
     "default": False},
    {"key": "taoguba",  "name": "淘股吧",     "icon": "🍜",
     "fmt_code": None,
     "fmt_name": "https://www.taoguba.com.cn/search?keyword={name}",
     "default": False},
    {"key": "xuanstock","name": "选股宝",     "icon": "📋",
     "fmt_code": None,
     "fmt_name": "https://www.xuanstock.com/search?keyword={name}",
     "default": False},
    {"key": "baidu",    "name": "百度搜索",   "icon": "🔍",
     "fmt_code": None,
     "fmt_name": "https://www.baidu.com/s?wd={name}+股票",
     "default": False},
]

# ═══════ 设置持久化 ═══════
def _settings_path():
    return os.path.join(os.path.expanduser("~"), ".stock_web_open.json")

def load_settings():
    """加载用户设置, 返回 {key: bool}"""
    p = _settings_path()
    defaults = {s["key"]: s["default"] for s in SITES}
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k in defaults: defaults[k] = bool(v)
        except: pass
    return defaults

def save_settings(s):
    """保存设置"""
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[stock_web_open❌] save: {e}")


# ═══════ 工具: 代码转新浪前缀 ═══════
def _code_to_prefix(code):
    code = str(code).strip()
    # 去除 sh/sz/bj 前缀
    code_clean = code
    for pref in ("sh", "sz", "bj"):
        if code.startswith(pref): code_clean = code[2:]; break
    if code_clean.startswith(("6", "9")): return "sh", code_clean
    elif code_clean.startswith(("0", "3")): return "sz", code_clean
    elif code_clean.startswith(("4", "8")): return "bj", code_clean
    return "sh", code_clean


# ═══════ 主函数: 同时打开所有选中的网站 ═══════
def open_stock_web(code, name="", sites=None):
    """
    同时在所有启用的财经网站打开某只股票

    code: 6 位数字或带 sh/sz/bj 前缀
    name: 股票中文名 (用于搜索类网站)
    sites: None=从设置文件读, 或传 dict {key: bool} 覆盖
    """
    if sites is None: sites = load_settings()
    if not name: name = ""

    prefix, code_clean = _code_to_prefix(code)
    opened = 0
    urls = []
    for s in SITES:
        if not sites.get(s["key"], False): continue
        # 优先 code URL, 没有用 name 搜索
        if s["fmt_code"]:
            url = s["fmt_code"].format(prefix=prefix, code=code_clean)
        elif s["fmt_name"] and name:
            url = s["fmt_name"].format(name=quote(name))
        else:
            continue
        urls.append((s["name"], url))

    # 后台线程打开 (不阻塞 UI)
    def _open_all():
        for sname, url in urls:
            try:
                webbrowser.open(url, new=2)  # new=2 → 新标签页
                opened += 1
            except Exception as e:
                print(f"[stock_web_open⚠️] {sname}: {e}")
    _th.Thread(target=_open_all, daemon=True).start()
    return len(urls)


# ═══════ 设置弹窗 ═══════
def show_settings_dialog(parent, on_save=None):
    """在 parent (Toplevel) 上弹出设置面板"""
    import tkinter as tk
    import tkinter.ttk as ttk

    dlg = tk.Toplevel(parent)
    dlg.title("🌐 股票多站打开 · 设置"); dlg.geometry("520x620")
    dlg.configure(bg="#1E1E1E"); dlg.transient(parent)

    tk.Label(dlg, text="🌐 股票多站同步打开 — 设置", bg="#1E1E1E", fg="#FFD54F",
             font=("", 15, "bold")).pack(pady=(14, 4))
    tk.Label(dlg, text="单击股票后, 同时在勾选的网站打开该股票页面",
             bg="#1E1E1E", fg="#888", font=("", 11)).pack()

    tk.Label(dlg, text="  (不勾选任何网站则不打开任何网页)",
             bg="#1E1E1E", fg="#EF5350", font=("", 10)).pack(pady=(2, 8))

    # 全选/全不选
    btns = tk.Frame(dlg, bg="#1E1E1E"); btns.pack(pady=4)
    def _all_on():
        for v in vars.values(): v.set(True)
    def _all_off():
        for v in vars.values(): v.set(False)
    def _revert():
        for k, v in vars.items(): v.set(not v.get())
    tk.Button(btns, text="✅ 全选", command=_all_on, bg="#37474F", fg="#FFF",
              relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=4)
    tk.Button(btns, text="❌ 全不选", command=_all_off, bg="#37474F", fg="#FFF",
              relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=4)
    tk.Button(btns, text="🔄 反选", command=_revert, bg="#37474F", fg="#FFF",
              relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=4)

    # 网站列表
    list_f = tk.LabelFrame(dlg, text=" 勾选要打开的网站 ", fg="#FFD54F", bg="#1E1E1E",
                           font=("", 11, "bold"), padx=12, pady=8)
    list_f.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

    current = load_settings()
    vars = {}
    for s in SITES:
        row = tk.Frame(list_f, bg="#262626")
        row.pack(fill=tk.X, pady=3)
        v = tk.BooleanVar(value=current.get(s["key"], s["default"]))
        vars[s["key"]] = v

        tk.Checkbutton(row, text="", variable=v, bg="#262626", selectcolor="#1E1E1E",
                       activebackground="#262626").pack(side=tk.LEFT)
        tk.Label(row, text=s["icon"], bg="#262626", font=("", 16)).pack(side=tk.LEFT, padx=(2, 8))
        tk.Label(row, text=s["name"], bg="#262626", fg="#FFF",
                 font=("", 12, "bold")).pack(side=tk.LEFT)

        # URL 预览
        if s["fmt_code"]:
            _preview = s["fmt_code"].format(prefix="{sh/sz}", code="000001")
        else:
            _preview = s["fmt_name"].format(name="贵州茅台")
        tk.Label(row, text=_preview, bg="#262626", fg="#78909C",
                 font=("", 9)).pack(side=tk.RIGHT, padx=8)

    # 预览 + 保存
    bottom = tk.Frame(dlg, bg="#1E1E1E"); bottom.pack(pady=10)
    tk.Button(bottom, text="🧪 测试打开 (贵州茅台 600519)",
              command=lambda: (open_stock_web("600519", "贵州茅台", {k: v.get() for k, v in vars.items()}),
                               dlg.lift()),
              bg="#4FC3F7", fg="#111", relief=tk.FLAT, padx=16, pady=6,
              font=("", 11, "bold")).pack(side=tk.LEFT, padx=6)

    def _save():
        s = {k: v.get() for k, v in vars.items()}
        save_settings(s)
        dlg.destroy()
        if on_save: on_save(s)

    tk.Button(bottom, text="💾 保存设置", command=_save,
              bg="#66BB6A", fg="#111", relief=tk.FLAT, padx=20, pady=6,
              font=("", 12, "bold")).pack(side=tk.LEFT, padx=6)
    tk.Button(bottom, text="取消", command=dlg.destroy,
              bg="#555", fg="#FFF", relief=tk.FLAT, padx=14, pady=6).pack(side=tk.LEFT, padx=6)

    return dlg

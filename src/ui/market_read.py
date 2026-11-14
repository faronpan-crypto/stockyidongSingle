"""
📖 见文 · AI文章生成
══════════════════════════════════════════
功能:
  ① 📝 粘贴文本 / 🔗 输入URL / 📄 选文件 三种输入
  ② 🎨 作家风格区 (鲁迅/余华/莫言/金庸/王小波/刘慈欣/彼得·林奇/霍华德·马克斯等 20+ 风格)
  ③ 🌐 多语种输出 (中/英/日/韩/法/德/西/阿等 12 种)
  ④ 🤖 AI 生成: 客观分析 → 选风格润色 → 指定语种输出
  ⑤ 💾 保存到本地 (docx / md / txt) + 一键复制
"""
import tkinter as _tk
import tkinter.ttk as _ttk
import tkinter.filedialog as _fd
import tkinter.scrolledtext as _st
import tkinter.messagebox as _mb
import threading as _th
import time as _time
import json as _json
import os as _os
import re as _re
import hashlib as _hashlib
import hmac as _hmac
import secrets as _secrets
import webbrowser as _wb
import datetime as _dt

_BG = "#121212"; _PANEL = "#1E1E2E"; _CARD = "#2D2D44"
_FG = "#EDEDEF"; _MUTED = "#9AA0B2"; _GOLD = "#F5B041"
_ACCENT = "#E74C3C"; _GREEN = "#58D68D"; _BLUE = "#5DADE2"; _PURPLE = "#BB8FCE"

# ═══════════════════════════════════════════════════════
# 🎨 作家风格库 (20+ 位, 含金融 + 文学)
# ═══════════════════════════════════════════════════════
_WRITER_STYLES = [
    # ── 金融投资 ──
    {"id": "peter_lynch",     "name": "彼得·林奇",     "icon": "💰", "cat": "投资大师",
     "prompt": "用彼得·林奇的风格写 — 通俗易懂, 喜欢用生活类比(购物/电影/婚姻), 把枯燥的财务指标讲成小故事, 既有专业判断又有散户情怀, 标题活泼, 段落短, 多用感叹号和反问句。"},
    {"id": "howard_marks",    "name": "霍华德·马克斯", "icon": "🎯", "cat": "投资大师",
     "prompt": "用霍华德·马克斯的风格写 — 深度思考, 关注周期/风险/逆向, 喜欢用'最重要的事'(The Most Important Thing)的框架, 语言沉稳但一针见血, 会提醒读者风险和不确定性。"},
    {"id": "buffett",         "name": "巴菲特",         "icon": "🎩", "cat": "投资大师",
     "prompt": "用巴菲特的风格写 — 简洁直白, 喜欢用'伯克希尔的例子', 强调长期持有/护城河/管理层, 乐观但不盲目, 语言像致股东信一样朴实有力。"},
    {"id": "livermore",       "name": "利弗莫尔",       "icon": "📈", "cat": "操盘手",
     "prompt": "用杰西·利弗莫尔的风格写 — 像《股票作手回忆录》那样, 第一人称叙事, 强调趋势/关键点/金字塔加仓/严格止损, 语言有传奇色彩, 带交易员的直觉和决断。"},
    {"id": "dalio",           "name": "达利欧",         "icon": "🔬", "cat": "投资大师",
     "prompt": "用雷·达利欧的风格写 — 像《原则》那样, 把复杂的市场分解成'机器'和'因果律', 用逻辑框架+数据驱动, 语言冷静客观, 喜欢分点阐述原则。"},
    {"id": "taleb",           "name": "塔勒布",         "icon": "🦢", "cat": "投资大师",
     "prompt": "用纳西姆·塔勒布的风格写 — 像《反脆弱》《黑天鹅》那样, 关注尾部风险/非线性/选择权, 喜欢用寓言和对比(脆弱vs强韧vs反脆弱), 语言犀利有哲理。"},
    {"id": "mao_butterfly",   "name": "毛羽(蝴蝶)",     "icon": "🦋", "cat": "游资",
     "prompt": "用A股游资'蝴蝶'毛羽的风格写 — 短线实战, 关注情绪周期/龙头/接力/核按钮, 用A股圈的黑话和术语, 节奏快, 像淘股吧热帖。"},
    {"id": "xuxu",            "name": "徐翔风格",       "icon": "🎯", "cat": "游资",
     "prompt": "用徐翔风格写 — 简短凌厉, 像《我在泽熙学到的七堂课》里的节奏, 看重确定性/仓位管理/顺势, 语言干脆不啰嗦。"},
    # ── 文学 ──
    {"id": "luxun",           "name": "鲁迅",           "icon": "🖋️", "cat": "文学巨匠",
     "prompt": "用鲁迅的风格写 — 深刻犀利, 带杂文的辛辣和讽刺, 关注国民性/社会本质, 语言凝练有力, 有时冷嘲热讽, 有时沉重慨叹。"},
    {"id": "yuhua",           "name": "余华",           "icon": "📖", "cat": "文学巨匠",
     "prompt": "用余华的风格写 — 冷静叙述, 用最朴素的语言讲最残酷的故事, 像《活着》《许三观卖血记》那样, 克制而有力量, 白描手法。"},
    {"id": "moyan",           "name": "莫言",           "icon": "🎭", "cat": "文学巨匠",
     "prompt": "用莫言的风格写 — 魔幻现实主义, 想象力奔放, 喜欢用民间故事/神话/传奇的手法, 语言狂欢化, 充满色彩和气味。"},
    {"id": "wangxiaobo",      "name": "王小波",         "icon": "💫", "cat": "文学巨匠",
     "prompt": "用王小波的风格写 — 幽默机智, 理性浪漫, 喜欢用'特立独行的猪'式的隐喻, 语言流畅, 有逻辑又有趣味, 带理工科思维。"},
    {"id": "jinyong",         "name": "金庸",           "icon": "⚔️", "cat": "文学巨匠",
     "prompt": "用金庸的风格写 — 章回体/武侠笔法, 把现实比江湖, 语言古朴典雅, 有侠义精神, 善用比喻和典故。"},
    {"id": "liu_cixin",       "name": "刘慈欣",         "icon": "🚀", "cat": "科幻",
     "prompt": "用刘慈欣的风格写 — 硬科幻/宏大叙事, 把市场/经济想象成宇宙/物理系统, 像《三体》那样从宇宙尺度思考, 语言冷静理性。"},
    {"id": "shanghai",        "name": "海明威",         "icon": "🎣", "cat": "外国文学",
     "prompt": "用海明威的风格写 — 冰山理论, 短句为主, 少形容词, 用最简单的词讲最深刻的道理, 像《老人与海》那样硬派。"},
    {"id": "dostoevsky",      "name": "陀思妥耶夫斯基", "icon": "📕", "cat": "外国文学",
     "prompt": "用陀思妥耶夫斯基的风格写 — 内心独白/存在主义, 关注人性/道德/救赎, 语言深沉厚重, 有思辨张力。"},
    # ── 新媒体 ──
    {"id": "wechat_vlog",     "name": "公众号爆款",     "icon": "📱", "cat": "新媒体",
     "prompt": "用微信公众号爆款文的风格写 — 标题党+金句开头+故事引入+干货输出+结尾升华, 多用emoji和分段, 适合手机阅读。"},
    {"id": "zhihu",           "name": "知乎高赞",       "icon": "🔍", "cat": "新媒体",
     "prompt": "用知乎高赞回答的风格写 — 先给结论再展开, 分点清晰, 有数据有论据, 语言理性客观, 像一个懂行的人分享经验。"},
    {"id": "xiaohongshu",     "name": "小红书风格",     "icon": "📕", "cat": "新媒体",
     "prompt": "用小红书种草文的风格写 — 活泼亲切, 大量emoji, 短句, 用'姐妹们''家人们'的口吻, 像闺蜜分享。"},
    {"id": "douyin",          "name": "抖音口播",       "icon": "🎤", "cat": "新媒体",
     "prompt": "用抖音口播文案的风格写 — 前3秒抓人, 节奏快, 有停顿提示, 口语化, 带钩子和反转。"},
]

# ═══════════════════════════════════════════════════════
# 🌐 语种列表
# ═══════════════════════════════════════════════════════
_LANGUAGES = [
    ("zh-CN", "简体中文 🇨🇳"),
    ("zh-TW", "繁體中文 🇭🇰"),
    ("en",    "English 🇺🇸"),
    ("ja",    "日本語 🇯🇵"),
    ("ko",    "한국어 🇰🇷"),
    ("fr",    "Français 🇫🇷"),
    ("de",    "Deutsch 🇩🇪"),
    ("es",    "Español 🇪🇸"),
    ("it",    "Italiano 🇮🇹"),
    ("ru",    "Русский 🇷🇺"),
    ("ar",    "العربية 🇸🇦"),
    ("pt",    "Português 🇧🇷"),
    ("th",    "ไทย 🇹🇭"),
    ("vi",    "Tiếng Việt 🇻🇳"),
]

# ═══════════════════════════════════════════════════════
# 🔑 AI 代理调用 (自动从 ai_config.json 读 provider/model, 跟主程序一致)
# ═══════════════════════════════════════════════════════
def _ai_call(messages, max_tokens=3000, timeout=60):
    """统一 AI 代理调用 — 从 src/config/ai_config.json 读当前 provider"""
    try:
        import requests
        # 1) 读 ai_config.json 获取当前 provider + model
        cfg_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                 "config", "ai_config.json")
        provider = "deepseek"; model = "deepseek-chat"
        try:
            if _os.path.exists(cfg_path):
                with open(cfg_path) as f:
                    cfg = _json.load(f)
                provider = cfg.get("active_provider", "deepseek")
                model = cfg.get("providers", {}).get(provider, {}).get("model", model)
        except Exception: pass

        # 2) secret
        secret_path = "/tmp/stock_ai_proxy.secret"
        if not _os.path.exists(secret_path):
            return None, "❌ AI 代理 secret 不存在 — 请先在主程序点🤖AI设置启动代理"
        secret = open(secret_path).read().strip()

        # 3) 构造签名
        nonce = _secrets.token_hex(8)
        ptoken = _hmac.new(secret.encode(), ("ai_proxy" + nonce).encode(),
                           _hashlib.sha256).hexdigest()[:16]
        h = {"Content-Type": "application/json",
             "X-Nonce": nonce, "X-Proxy-Token": ptoken}
        b = {"provider": provider, "model": model,
             "max_tokens": max_tokens, "messages": messages, "temperature": 0.7}

        # 4) 调用代理
        r = requests.post("http://127.0.0.1:8787/v1/chat/completions",
                          headers=h, json=b, timeout=timeout)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"], None
        # 友好错误映射
        err = r.text[:200]
        if r.status_code == 502 and "未配置" in err:
            return None, "❌ 代理 API Key 未配置 — 请在🤖AI设置里填 key"
        if r.status_code == 401:
            return None, "❌ 代理签名校验失败 — 请重启主程序(代理可能已重启)"
        if r.status_code == 429:
            return None, "⚠️ AI 调用限额已达上限, 请稍后重试"
        return None, f"❌ AI {r.status_code}: {err}"
    except ImportError:
        return None, "❌ requests 未安装, 请: pip install requests"
    except Exception as e:
        return None, f"❌ AI 代理调用异常: {e}"


def _fetch_url_text(url):
    """从 URL 抓取正文 (用 requests + 简单文本提取)"""
    try:
        import requests as _req
        from urllib.parse import urlparse
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
        r = _req.get(url, headers=headers, timeout=15)
        r.encoding = r.apparent_encoding
        html = r.text
        # 简单去除标签 (不依赖 BeautifulSoup)
        text = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
        text = _re.sub(r'<[^>]+>', '', text)
        text = _re.sub(r'\s+\n', '\n', text)
        text = _re.sub(r'[ \t]+', ' ', text)
        text = text.strip()[:8000]  # 截取前8000字
        domain = urlparse(url).netloc
        return f"[来源: {domain}]\n{text}", None
    except Exception as e:
        return None, f"❌ 抓取失败: {e}"


# ═══════════════════════════════════════════════════════
# 🪟 主窗口
# ═══════════════════════════════════════════════════════
def _show_market_read_dialog(parent_root=None):
    """📖 见文 — 文本/URL → AI 风格化写文章"""
    root = parent_root or _tk.Tk()
    win = _tk.Toplevel(root)
    win.title("📖 见文 · AI文章生成器")
    win.configure(bg=_BG)
    win.geometry("1200x820")
    try:
        win.attributes("-topmost", True); win.attributes("-topmost", False)
    except Exception: pass

    # ── Banner ──
    banner = _tk.Frame(win, bg=_PURPLE, height=48); banner.pack(fill=_tk.X)
    banner.pack_propagate(False)
    _tk.Label(banner, text="📖  见文 · AI 风格化文章生成器",
              font=("Microsoft YaHei", 13, "bold"),
              bg=_PURPLE, fg="white").pack(side=_tk.LEFT, padx=14, pady=10)
    status_var = _tk.StringVar(value="⏳ 输入文本 / URL / 文件 → 选作家风格 → 选语种 → 生成")
    _tk.Label(banner, textvariable=status_var, font=("Microsoft YaHei", 10),
              bg=_PURPLE, fg="#F5EEF8").pack(side=_tk.LEFT, pady=14)

    # ── 主体 Paned (ttk.PanedWindow 支持 weight) ──
    paned = _ttk.PanedWindow(win, orient=_tk.HORIZONTAL)
    paned.pack(fill=_tk.BOTH, expand=True, padx=4, pady=4)

    # ═══════════════════════════════════════════════════════
    # 左侧: 输入 + 风格 + 语种
    # ═══════════════════════════════════════════════════════
    left = _tk.Frame(paned, bg=_PANEL)
    paned.add(left, weight=1)

    # 输入区标题
    _tk.Label(left, text="📝 输入源", bg=_PANEL, fg=_GOLD,
              font=("Microsoft YaHei", 11, "bold")).pack(anchor=_tk.W, padx=8, pady=(8, 4))

    # Tab 切换
    input_nb = _ttk.Notebook(left)
    input_nb.pack(fill=_tk.X, padx=8, pady=(0, 6))

    # Tab1: 粘贴文本
    tab_text = _tk.Frame(input_nb, bg=_PANEL); input_nb.add(tab_text, text="  直接粘贴  ")
    text_input = _st.ScrolledText(tab_text, height=8, bg=_CARD, fg=_FG,
                                  font=("Menlo", 11), wrap=_tk.WORD,
                                  insertbackground=_FG, bd=0, relief=_tk.FLAT)
    text_input.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)
    text_input.insert("1.0", "把要分析的文字粘贴到这里...\n\n可以是一段新闻、研报摘录、社交媒体帖子、盘后复盘笔记...")

    # Tab2: URL
    tab_url = _tk.Frame(input_nb, bg=_PANEL); input_nb.add(tab_url, text="  🔗 URL  ")
    url_frame = _tk.Frame(tab_url, bg=_PANEL); url_frame.pack(fill=_tk.X, padx=6, pady=6)
    _tk.Label(url_frame, text="网页 URL:", bg=_PANEL, fg=_MUTED,
              font=("", 10)).pack(side=_tk.LEFT)
    url_var = _tk.StringVar()
    url_entry = _tk.Entry(url_frame, textvariable=url_var, bg=_CARD, fg=_FG,
                          insertbackground=_FG, font=("", 11), relief=_tk.FLAT, bd=4)
    url_entry.pack(side=_tk.LEFT, fill=_tk.X, expand=True, padx=6)
    url_btn = _tk.Button(url_frame, text="🔍 抓取", bg=_BLUE, fg="white",
                         font=("", 10, "bold"), relief=_tk.FLAT, padx=10)
    url_btn.pack(side=_tk.LEFT, padx=4)
    url_preview = _st.ScrolledText(tab_url, height=6, bg=_CARD, fg=_MUTED,
                                   font=("Menlo", 10), wrap=_tk.WORD, bd=0, relief=_tk.FLAT)
    url_preview.pack(fill=_tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # Tab3: 文件
    tab_file = _tk.Frame(input_nb, bg=_PANEL); input_nb.add(tab_file, text="  📄 文件  ")
    file_frame = _tk.Frame(tab_file, bg=_PANEL); file_frame.pack(fill=_tk.X, padx=6, pady=6)
    file_var = _tk.StringVar(value="(未选择文件)")
    _tk.Label(file_frame, textvariable=file_var, bg=_PANEL, fg=_MUTED,
              font=("", 10)).pack(side=_tk.LEFT, padx=6)
    file_btn = _tk.Button(file_frame, text="📂 选择文件", bg=_BLUE, fg="white",
                          font=("", 10, "bold"), relief=_tk.FLAT, padx=8)
    file_btn.pack(side=_tk.LEFT)
    file_text = _st.ScrolledText(tab_file, height=6, bg=_CARD, fg=_MUTED,
                                 font=("Menlo", 10), wrap=_tk.WORD, bd=0, relief=_tk.FLAT)
    file_text.pack(fill=_tk.BOTH, expand=True, padx=6, pady=(0, 6))

    # ── 🎨 作家风格区 ──
    _tk.Label(left, text="🎨 作家风格 (点击选中, 可叠加最多3位)",
              bg=_PANEL, fg=_GOLD, font=("Microsoft YaHei", 11, "bold")).pack(anchor=_tk.W, padx=8, pady=(10, 4))

    style_canvas = _tk.Canvas(left, bg=_PANEL, highlightthickness=0, height=160)
    style_scrollbar = _tk.Scrollbar(left, orient=_tk.VERTICAL, command=style_canvas.yview)
    style_inner = _tk.Frame(style_canvas, bg=_PANEL)
    style_inner.bind("<Configure>", lambda e: style_canvas.configure(scrollregion=style_canvas.bbox("all")))
    style_canvas.create_window((0, 0), window=style_inner, anchor=_tk.NW)
    style_canvas.configure(yscrollcommand=style_scrollbar.set)
    style_canvas.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True, padx=(8, 0), pady=4)
    style_scrollbar.pack(side=_tk.RIGHT, fill=_tk.Y, pady=4)

    selected_styles = []  # id 列表, 最多3个
    style_buttons = {}    # id → button ref

    def _toggle_style(writer_id):
        if writer_id in selected_styles:
            selected_styles.remove(writer_id)
            style_buttons[writer_id].configure(bg=_CARD, fg=_FG, relief=_tk.FLAT)
        else:
            if len(selected_styles) >= 3:
                _mb.showinfo("提示", "最多叠加 3 位作家风格")
                return
            selected_styles.append(writer_id)
            style_buttons[writer_id].configure(bg=_PURPLE, fg="white", relief=_tk.SOLID, bd=2)
        selected_text = " + ".join(_WRITER_MAP[w]["name"] for w in selected_styles)
        sel_var.set(f"已选: {selected_text}" if selected_text else "未选择 (默认客观分析)")

    # 按 cat 分组渲染
    _WRITER_MAP = {w["id"]: w for w in _WRITER_STYLES}
    _cats = sorted(set(w["cat"] for w in _WRITER_STYLES))
    for cat in _cats:
        cat_frame = _tk.Frame(style_inner, bg=_PANEL)
        cat_frame.pack(fill=_tk.X, padx=4, pady=2)
        _tk.Label(cat_frame, text=f"  {cat}", bg=_PANEL, fg=_MUTED,
                  font=("", 9, "bold")).pack(side=_tk.LEFT)
        for w in _WRITER_STYLES:
            if w["cat"] != cat: continue
            btn = _tk.Button(cat_frame, text=f"{w['icon']} {w['name']}",
                            bg=_CARD, fg=_FG, font=("", 9), relief=_tk.FLAT,
                            padx=6, pady=2, cursor="hand2", bd=0,
                            command=lambda wid=w["id"]: _toggle_style(wid))
            btn.pack(side=_tk.LEFT, padx=2, pady=2)
            style_buttons[w["id"]] = btn

    sel_var = _tk.StringVar(value="未选择 (默认客观分析)")
    _tk.Label(left, textvariable=sel_var, bg=_PANEL, fg=_GOLD,
              font=("", 10)).pack(anchor=_tk.W, padx=10, pady=2)

    # ── 🌐 语种选择 ──
    lang_frame = _tk.Frame(left, bg=_PANEL); lang_frame.pack(fill=_tk.X, padx=8, pady=(8, 4))
    _tk.Label(lang_frame, text="🌐 输出语种:", bg=_PANEL, fg=_GOLD,
              font=("Microsoft YaHei", 11, "bold")).pack(side=_tk.LEFT)
    lang_var = _tk.StringVar(value="zh-CN")
    lang_combo = _ttk.Combobox(lang_frame, textvariable=lang_var, state="readonly",
                              values=[f"{c[0]}|{c[1]}" for c in _LANGUAGES],
                              width=28, font=("", 10))
    lang_combo.current(0)
    lang_combo.pack(side=_tk.LEFT, padx=6)

    # ── 生成按钮 ──
    btn_frame = _tk.Frame(left, bg=_PANEL); btn_frame.pack(fill=_tk.X, padx=8, pady=12)
    gen_btn = _tk.Button(btn_frame, text="✨ 生成文章", bg=_ACCENT, fg="white",
                         font=("Microsoft YaHei", 12, "bold"), relief=_tk.FLAT,
                         padx=20, pady=6, cursor="hand2")
    gen_btn.pack(fill=_tk.X, pady=2)
    _tk.Label(btn_frame, text="⏱ 预计 10-60 秒 · 字数越多越慢",
              bg=_PANEL, fg=_MUTED, font=("", 9)).pack()

    # 绑定 URL 抓取
    def _do_fetch_url():
        url = url_var.get().strip()
        if not url:
            _mb.showwarning("提示", "请输入 URL")
            return
        url_preview.delete("1.0", _tk.END)
        url_preview.insert("1.0", "⏳ 正在抓取...")
        url_btn.configure(state=_tk.DISABLED, text="抓取中...")
        def _work():
            text, err = _fetch_url_text(url)
            win.after(0, lambda: (
                url_preview.delete("1.0", _tk.END),
                url_preview.insert("1.0", text or f"❌ {err}"),
                url_btn.configure(state=_tk.NORMAL, text="🔍 抓取")
            ))
        _th.Thread(target=_work, daemon=True).start()
    url_btn.configure(command=_do_fetch_url)

    # 绑定文件选择
    def _do_pick_file():
        path = _fd.askopenfilename(
            filetypes=[("文本", "*.txt *.md *.csv *.log"), ("全部", "*.*")])
        if not path: return
        file_var.set(f"📄 {_os.path.basename(path)}")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            file_text.delete("1.0", _tk.END)
            file_text.insert("1.0", content[:10000])
        except Exception as e:
            _mb.showerror("错误", str(e))
    file_btn.configure(command=_do_pick_file)

    # ═══════════════════════════════════════════════════════
    # 右侧: 输出结果
    # ═══════════════════════════════════════════════════════
    right = _tk.Frame(paned, bg=_PANEL)
    paned.add(right, weight=2)

    # 工具栏
    out_bar = _tk.Frame(right, bg=_PANEL); out_bar.pack(fill=_tk.X, padx=8, pady=(8, 4))
    _tk.Label(out_bar, text="📄 生成结果", bg=_PANEL, fg=_GOLD,
              font=("Microsoft YaHei", 11, "bold")).pack(side=_tk.LEFT)
    # ⚠️ output_text 必须最先创建，否则下面的 .bind() 立即执行会炸
    output_text = _st.ScrolledText(right, bg=_CARD, fg=_FG, font=("Menlo", 11),
                                  wrap=_tk.WORD, bd=0, relief=_tk.FLAT,
                                  insertbackground=_FG, padx=10, pady=10)
    output_text.pack(fill=_tk.BOTH, expand=True, padx=8, pady=(0, 8))
    output_text.insert("1.0", "✨ 点左边「生成文章」按钮开始...\n\n支持:\n  • 粘贴文本 / 输入URL / 选择文件 三种输入\n  • 20+ 作家风格 (投资/文学/新媒体)\n  • 12 种语种输出\n  • 自动客观分析 + 风格化重写")
    # ── 🔊 朗读 + 🖍️划词 功能 ──
    _tts_proc = {"proc": None}  # 用 dict 存, 避免闭包变量问题

    def _do_speak():
        """朗读全文或选中文本"""
        # 先停掉之前的
        _do_stop()
        sel = output_text.get("sel.first", "sel.last").strip() if output_text.tag_ranges("sel") else ""
        text = sel if sel else output_text.get("1.0", _tk.END).strip()
        if not text:
            _mb.showwarning("提示", "没有内容可朗读")
            return
        # 截短 (say 命令参数过长会崩)
        if len(text) > 3000:
            text = text[:3000] + "\n...(已截断)"
        import subprocess
        _tts_proc["proc"] = subprocess.Popen(
            ["say", "-v", "Tingting", text],  # Tingting = 普通话女声
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        status_var.set("🔊 朗读中... (点⏹停止)")

    def _do_stop():
        """停止朗读"""
        try:
            p = _tts_proc["proc"]
            if p and p.poll() is None:
                p.terminate()
                _tts_proc["proc"] = None
        except Exception: pass
        # macOS 可能残留 say 进程
        import subprocess
        subprocess.run(["pkill", "-f", "say"], capture_output=True)
        status_var.set("⏹ 朗读已停止")

    def _do_highlight():
        """给选中文本加高亮 (黄色背景)"""
        try:
            sel_first = output_text.index("sel.first")
            sel_last = output_text.index("sel.last")
        except Exception:
            _mb.showwarning("提示", "请先选中要高亮的文字")
            return
        output_text.tag_add("highlight_yellow", sel_first, sel_last)
        output_text.tag_config("highlight_yellow", background="#F5B041", foreground="black")
        status_var.set(f"🖍️ 已高亮 ({sel_first} → {sel_last})")

    def _do_clear_highlight():
        """清除所有高亮"""
        for tag in output_text.tag_names():
            if tag.startswith("highlight"):
                output_text.tag_remove(tag, "1.0", _tk.END)
        status_var.set("🗑️ 高亮已清除")

    # 工具栏按钮
    _tk.Button(out_bar, text="🔊 朗读", bg=_PURPLE, fg="white",
               font=("", 9, "bold"), relief=_tk.FLAT, padx=8,
               command=_do_speak).pack(side=_tk.RIGHT, padx=2)
    _tk.Button(out_bar, text="⏹ 停止", bg=_ACCENT, fg="white",
               font=("", 9), relief=_tk.FLAT, padx=8,
               command=_do_stop).pack(side=_tk.RIGHT, padx=2)
    _tk.Button(out_bar, text="🖍️ 划词高亮", bg=_GOLD, fg="#333",
               font=("", 9, "bold"), relief=_tk.FLAT, padx=8,
               command=_do_highlight).pack(side=_tk.RIGHT, padx=2)
    _tk.Button(out_bar, text="🗑️ 清高亮", bg=_MUTED, fg="white",
               font=("", 9), relief=_tk.FLAT, padx=8,
               command=_do_clear_highlight).pack(side=_tk.RIGHT, padx=2)

    # 右键菜单
    rmenu = _tk.Menu(win, tearoff=0, bg=_PANEL, fg=_FG,
                    activebackground=_PURPLE, activeforeground="white",
                    relief=_tk.FLAT, bd=1)
    rmenu.add_command(label="🔊 朗读选中文本", command=_do_speak)
    rmenu.add_command(label="🖍️ 高亮选中", command=_do_highlight)
    rmenu.add_separator()
    rmenu.add_command(label="📋 复制", command=lambda: (
        win.clipboard_clear(),
        win.clipboard_append(output_text.get("sel.first", "sel.last"))))
    rmenu.add_command(label="🗑️ 清除所有高亮", command=_do_clear_highlight)

    def _show_rmenu(e):
        try: rmenu.tk_popup(e.x_root, e.y_root)
        finally: rmenu.grab_release()
    output_text.bind("<Button-3>", _show_rmenu)
    # macOS 右键是 Button-2
    output_text.bind("<Button-2>", _show_rmenu)

    # 复制/保存 (最右边)
    _tk.Button(out_bar, text="📋复制", bg=_BLUE, fg="white",
               font=("", 9), relief=_tk.FLAT, padx=8,
               command=lambda: (
                   win.clipboard_clear(),
                   win.clipboard_append(output_text.get("1.0", _tk.END)),
                   _mb.showinfo("已复制", "文章已复制到剪贴板"))
               ).pack(side=_tk.RIGHT, padx=2)
    _tk.Button(out_bar, text="💾TXT", bg=_GREEN, fg="white",
               font=("", 9), relief=_tk.FLAT, padx=6,
               command=lambda: _save_output(output_text, "txt")).pack(side=_tk.RIGHT, padx=2)
    _tk.Button(out_bar, text="💾MD", bg=_GREEN, fg="white",
               font=("", 9), relief=_tk.FLAT, padx=6,
               command=lambda: _save_output(output_text, "md")).pack(side=_tk.RIGHT, padx=2)

    def _save_output(widget, fmt):
        content = widget.get("1.0", _tk.END).strip()
        if not content:
            _mb.showwarning("提示", "没有内容可保存")
            return
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = _fd.asksaveasfilename(
            defaultextension=f".{fmt}",
            initialfile=f"见文_{ts}.{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            _mb.showinfo("已保存", f"→ {path}")
        except Exception as e:
            _mb.showerror("错误", str(e))

    # ═══════════════════════════════════════════════════════
    # ✨ 生成主逻辑
    # ═══════════════════════════════════════════════════════
    def _collect_input():
        """从三个 Tab 里取内容"""
        tab = input_nb.index(input_nb.select())
        if tab == 0:  # 直接粘贴
            t = text_input.get("1.0", _tk.END).strip()
            if not t or t.startswith("把要分析的文字"): return None, "请输入要分析的文本"
            return t, None
        elif tab == 1:  # URL
            t = url_preview.get("1.0", _tk.END).strip()
            if not t or t.startswith("⏳") or t.startswith("❌"): return None, "请先输入并抓取 URL"
            return t, None
        else:  # 文件
            t = file_text.get("1.0", _tk.END).strip()
            if not t: return None, "请选择文件"
            return t, None

    def _build_prompt(input_text, writer_ids, lang_code):
        """构造 AI prompt"""
        # 1) 客观分析阶段
        sys1 = ("你是一个严谨的市场/文本分析师。请先对用户提供的文本进行客观分析:\n"
                "1. 核心观点摘要 (3-5句话)\n"
                "2. 关键数据/事件/信号提取\n"
                "3. 逻辑优缺点 (是否有偏见/数据支撑/遗漏)\n"
                "4. 隐含假设和可能被忽略的角度\n"
                "用简洁的中文输出分析结论, 不要编造数据。")

        # 2) 风格化写作阶段
        if writer_ids:
            writer_prompts = [_WRITER_MAP[w]["prompt"] for w in writer_ids]
            style_desc = "\n".join(f"- {_WRITER_MAP[w]['name']}: {_WRITER_MAP[w]['prompt']}" for w in writer_ids)
            if len(writer_ids) == 1:
                style_instruction = f"请严格按照以下作家风格写:\n{style_desc}"
            else:
                style_instruction = (f"请融合以下 {len(writer_ids)} 位作家的风格, 写出一篇自然融合的文章:\n{style_desc}\n"
                                    "不要罗列风格名, 要让它们自然地融合在语言里。")
        else:
            style_instruction = "用客观、专业但易懂的语言写, 适合普通读者。"

        # 3) 语种
        lang_name = dict(_LANGUAGES).get(lang_code, lang_code)
        lang_instruction = f"⚠️ 重要: 最终输出必须使用【{lang_name}】撰写, 全文保持该语种, 不要混合其他语言。"

        user_msg = f"""【待分析文本开始】
{input_text[:6000]}
【待分析文本结束】

请按以下步骤工作:
第一步: 先做客观分析 (不需要展示给读者, 在脑内完成即可)
第二步: 基于分析结论, 写一篇完整的文章
{style_instruction}
第三步: {lang_instruction}

输出格式:
- 吸引人的标题 (含 em optionally)
- 分 3-5 个小节, 每节有小标题
- 总字数 800-2000 字
- 结尾加「风险提示 / 免责声明」"""

        return [
            {"role": "system", "content": sys1},
            {"role": "user", "content": user_msg},
        ]

    def _do_generate():
        content, err = _collect_input()
        if err:
            _mb.showwarning("提示", err); return
        lang_code = lang_var.get().split("|")[0] if "|" in lang_var.get() else lang_var.get()
        writer_ids = list(selected_styles)

        # UI 状态
        gen_btn.configure(state=_tk.DISABLED, text="⏳ AI 正在写...")
        output_text.delete("1.0", _tk.END)
        output_text.insert("1.0", f"⏳ 正在分析 + 生成...\n\n"
                            f"作家风格: {' + '.join(_WRITER_MAP[w]['name'] for w in writer_ids) if writer_ids else '客观分析'}\n"
                            f"输出语种: {dict(_LANGUAGES).get(lang_code, lang_code)}\n\n"
                            f"预计 10-60 秒, 请稍候...")
        status_var.set("⏳ AI 生成中...")

        messages = _build_prompt(content, writer_ids, lang_code)

        def _work():
            result, e = _ai_call(messages, max_tokens=3500, timeout=90)
            win.after(0, lambda: (
                _render_result(result, e),
                gen_btn.configure(state=_tk.NORMAL, text="✨ 生成文章"),
                status_var.set("✅ 完成" if result else f"❌ {e}")
            ))

        def _render_result(result, err):
            output_text.delete("1.0", _tk.END)
            if result:
                meta = (f"---\n"
                        f"📝 见文 AI 生成\n"
                        f"🕐 {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                        f"🎨 风格: {' + '.join(_WRITER_MAP[w]['name'] for w in writer_ids) if writer_ids else '客观分析'}\n"
                        f"🌐 语种: {dict(_LANGUAGES).get(lang_code, lang_code)}\n"
                        f"---\n\n")
                output_text.insert("1.0", meta + result)
            else:
                output_text.insert("1.0", f"❌ 生成失败\n\n{err}")

        _th.Thread(target=_work, daemon=True).start()

    gen_btn.configure(command=_do_generate)

    # ── Paned 初始位置 ──
    win.update_idletasks()
    paned.sashpos(0, 420)

    # 滚轮绑定 (只绑到 style_canvas, 不污染全局)
    def _on_mousewheel(e): style_canvas.yview_scroll(int(-e.delta / 120), "units")
    def _bind_mousewheel_rec(widget):
        widget.bind("<MouseWheel>", _on_mousewheel)
        for c in widget.winfo_children(): _bind_mousewheel_rec(c)
    _bind_mousewheel_rec(style_canvas)

    return win

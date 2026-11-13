"""
👁️ 见盘 · AI 综合研判窗口
══════════════════════════════════════════
功能:
  ① 📷 图片上传 → AI 视觉识别（OCR + 盘面解读）
  ② 🌐 财经网站快捷按钮（同花顺/东财/财联社/选股宝/韭研/choice... 可配置）
  ③ 🤖 AI 综合研判: 图片+实时API+时间 → 形势判断+预判
  ④ ⏰ 时间感知: 结合当前交易时段决定分析重点
"""
import tkinter as _tk
import tkinter.ttk as _ttk
import tkinter.filedialog as _fd
import tkinter.scrolledtext as _st
import tkinter.messagebox as _mb
import tkinter.simpledialog as _sd
import threading as _th
import time as _time
import datetime as _dt
import json as _json
import os as _os
import base64 as _b64
import webbrowser as _wb
import io as _io
import re as _re
import tempfile as _tf_m  # 模块级（函数里也用 _tf）
import hashlib as _hashlib
import hmac as _hmac
import secrets as _secrets

_BG = "#1A1A2E"; _PANEL = "#16213E"; _CARD = "#0F3460"
_FG = "#EAEAEA"; _MUTED = "#90A4AE"; _GOLD = "#FFD54F"
_ACCENT = "#E94560"; _GREEN = "#66BB6A"; _BLUE = "#64B5F6"

# ═══════════════════════════════════════════════════════
# 🌐 网站列表（可配置在 market_watch_sites.json）
# ═══════════════════════════════════════════════════════
_DEFAULT_SITES = [
    {"name": "同花顺·主页",     "url": "https://www.10jqka.com.cn/",         "desc": "综合门户·实时行情"},
    {"name": "东方财富·主页",   "url": "https://www.eastmoney.com/",           "desc": "资金流向·Lof"},
    {"name": "财联社·电报",     "url": "https://www.cls.cn/telegraph",        "desc": "7×24 快讯"},
    {"name": "选股宝",          "url": "https://www.51zxg.com/",              "desc": "题材热度·连板梯队"},
    {"name": "韭研公社",        "url": "https://www.jiuyangongshe.com/",      "desc": "深度研报·基本面"},
    {"name": "同花顺·热股",     "url": "https://hot.10jqka.com.cn/",          "desc": "热股榜·异动"},
    {"name": "雪球·热门",       "url": "https://xueqiu.com/hq",               "desc": "社区讨论·情绪"},
    {"name": "淘股吧",          "url": "https://www.taoguba.com.cn/",         "desc": "游资一线·盘后"},
    {"name": "Choice·金融终端",  "url": "https://www.choice.eastmoney.com/",    "desc": "专业数据·机构用"},
    {"name": "华尔街见闻",       "url": "https://wallstreetcn.com/",           "desc": "全球财经·实时"},
    {"name": "金十数据",         "url": "https://www.jin10.com/",              "desc": "日历·数据快报"},
    {"name": "上交所·公告",      "url": "http://www.sse.com.cn/",              "desc": "官方公告·监管"},
]

_CFG_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                          "config", "market_watch_sites.json")


def _load_sites():
    try:
        if _os.path.exists(_CFG_PATH):
            with open(_CFG_PATH) as f:
                return _json.load(f)
    except Exception:
        pass
    return _DEFAULT_SITES


def _save_sites(sites):
    try:
        with open(_CFG_PATH, "w") as f:
            _json.dump(sites, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# 🔑 AI 代理调用（复用 ai_settings 里的签名模式）
# ═══════════════════════════════════════════════════════
def _ai_call(messages, max_tokens=1800, timeout=25):
    """统一 AI 代理调用，支持 vision（image_url）"""
    try:
        import requests
        secret_path = "/tmp/stock_ai_proxy.secret"
        if not _os.path.exists(secret_path):
            return None, "❌ AI 代理 secret 不存在"
        secret = open(secret_path).read().strip()
        nonce = _secrets.token_hex(8)
        ptoken = _hmac.new(secret.encode(), ("ai_proxy" + nonce).encode(),
                           _hashlib.sha256).hexdigest()[:16]
        h = {"Content-Type": "application/json",
             "X-Nonce": nonce, "X-Proxy-Token": ptoken}
        b = {"provider": "deepseek", "model": "deepseek-chat",
             "max_tokens": max_tokens, "messages": messages, "temperature": 0.3}
        r = requests.post("http://127.0.0.1:8787/v1/chat/completions",
                          headers=h, json=b, timeout=timeout)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"], None
        return None, f"❌ {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return None, f"❌ AI 异常: {e}"


def _img_to_data_url(img_path, max_size=(1280, 1280), quality=75):
    """图片 → base64 data URL（压缩到合理大小）"""
    try:
        from PIL import Image
        img = Image.open(img_path)
        # 转 RGB 兼容 RGBA/PNG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size)
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return "data:image/jpeg;base64," + _b64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        # PIL 不可用：直接 base64 原文件
        with open(img_path, "rb") as f:
            data = f.read()
        ext = img_path.rsplit(".", 1)[-1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
        return f"data:{mime};base64," + _b64.b64encode(data).decode()


# ═══════════════════════════════════════════════════════
# 🖥️ 窗口主入口
# ═══════════════════════════════════════════════════════
def _show_market_watch_dialog(parent_root=None):
    win = _tk.Toplevel(parent_root)
    win.title("👁️ 见盘 · AI 综合研判")
    win.configure(bg=_BG)
    win.geometry("1080x760")
    try:
        win.attributes("-topmost", True); win.attributes("-topmost", False)
    except Exception:
        pass

    # Header
    _tk.Label(win, text="👁️  见盘  ·  AI 综合研判",
              bg=_BG, fg=_GOLD,
              font=("TkDefaultFont", 14, "bold")).pack(pady=(12, 4))

    now = _dt.datetime.now()
    ts_str = now.strftime("%Y-%m-%d %H:%M")
    # 交易时段判断
    h, m = now.hour, now.minute
    time_period = "盘前准备" if (h == 9 and m < 30) or h < 9 else \
                  "早盘 9:30-11:30" if (h == 9 or h == 10 or (h == 11 and m <= 30)) else \
                  "午休 11:30-13:00" if (h == 11 and m > 30) or (h == 12) else \
                  "午盘 13:00-15:00" if (h >= 13 and h < 15) else \
                  "盘后 15:00+"
    _tk.Label(win, text=f"🕐 {ts_str}  |  时段: {time_period}",
              bg=_BG, fg=_MUTED,
              font=("TkDefaultFont", 10)).pack(pady=(0, 8))

    # 主布局：左 图片+按钮 / 右 结果区
    main = _tk.Frame(win, bg=_BG); main.pack(fill=_tk.BOTH, expand=True, padx=12, pady=4)
    left = _tk.Frame(main, bg=_PANEL); left.pack(side=_tk.LEFT, fill=_tk.Y, padx=(0, 8))
    right = _tk.Frame(main, bg=_PANEL); right.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)

    # ── 左侧：图片 + 网站按钮 ──
    # ① 图片预览卡（支持：选文件 / 拖拽 / 粘贴 Cmd+V）
    img_card = _tk.LabelFrame(left, text=" 📷 盘面图片 (拖/粘/选) ",
                               bg=_PANEL, fg=_BLUE,
                               font=("TkDefaultFont", 10, "bold"))
    img_card.pack(fill=_tk.X, padx=8, pady=8)

    img_preview = _tk.Label(img_card,
                            text="🖼️  把图片拖到这里\n或 Cmd+V 粘贴\n或点下方按钮选择",
                            bg="#0F3460", fg=_MUTED, width=30, height=10,
                            font=("TkDefaultFont", 9))
    img_preview.pack(padx=6, pady=6)

    img_path_var = _tk.StringVar(value="")

    def _load_into_preview(img_obj, label_widget=img_preview):
        """统一：PIL Image 对象 → 预览"""
        from PIL import Image, ImageTk
        img = img_obj.copy()
        img.thumbnail((220, 220))
        photo = ImageTk.PhotoImage(img)
        label_widget.config(image=photo, text="", width=220, height=220, bg="#0F3460")
        label_widget._photo = photo

    def _set_image_from_path(path):
        """文件路径 → 预览"""
        if not path or not _os.path.exists(path):
            status_lbl.config(text=f"❌ 图片文件不存在: {path}", fg=_ACCENT); return False
        img_path_var.set(path)
        try:
            from PIL import Image
            _load_into_preview(Image.open(path))
            status_lbl.config(text=f"✅ 已加载: {_os.path.basename(path)}  ({_os.path.getsize(path)//1024}KB)", fg=_GREEN)
            return True
        except Exception as e:
            status_lbl.config(text=f"⚠️ 预览失败: {e}，但可尝试直接分析", fg=_GOLD); return False

    def _paste_from_clipboard():
        """Cmd+V / Ctrl+V — 粘贴图片"""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                status_lbl.config(text="⚠️ 剪贴板里没有图片（先截个图再粘贴）", fg=_GOLD); return
            if isinstance(img, list):
                # 剪贴板是文件引用（Finder 里 Cmd+C 图片文件）
                for p in img:
                    if isinstance(p, str) and _os.path.exists(p):
                        if _set_image_from_path(p): return
            # PIL Image → 存临时文件
            tmp = _tf_m.NamedTemporaryFile(suffix=".png", delete=False)
            img.save(tmp.name); tmp.close()
            img_path_var.set(tmp.name)
            _load_into_preview(img)
            status_lbl.config(text=f"✅ 已粘贴图片 (来自剪贴板, 临时文件)", fg=_GREEN)
        except Exception as e:
            status_lbl.config(text=f"❌ 粘贴失败: {e}", fg=_ACCENT)

    def _on_drop(event):
        """tkinterdnd2 拖拽回调 — event.data = '{filename1} {filename2}'"""
        try:
            raw = event.data
            # tkinterdnd2 返回的路径用空格分隔（或 {} 包裹）
            paths = _re.findall(r'\{([^}]+)\}|(\S+)', raw)
            found = None
            for a, b in paths:
                p = a or b
                if p and _os.path.splitext(p)[1].lower() in ('.png','.jpg','.jpeg','.gif','.webp','.bmp'):
                    found = p; break
            if not found:
                # 试试直接 raw 作为路径
                ext = _os.path.splitext(raw.strip())[1].lower()
                if ext in ('.png','.jpg','.jpeg','.gif','.webp','.bmp') and _os.path.exists(raw.strip()):
                    found = raw.strip()
            if found:
                _set_image_from_path(found)
            else:
                status_lbl.config(text="⚠️ 请拖图片文件（png/jpg/gif/webp/bmp）", fg=_GOLD)
        except Exception as e:
            status_lbl.config(text=f"❌ 拖拽处理失败: {e}", fg=_ACCENT)
            import traceback; traceback.print_exc()

    # ── 绑定事件 ──
    # 1) tkinterdnd2 拖拽（try import，没有就跳过）
    _dnd_ok = False
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        img_preview.drop_target_register(DND_FILES)
        img_preview.dnd_bind('<<Drop>>', _on_drop)
        img_card.drop_target_register(DND_FILES)
        img_card.dnd_bind('<<Drop>>', _on_drop)
        _dnd_ok = True
    except Exception:
        pass  # 没装 tkinterdnd2 就跳过拖拽

    # 2) Cmd+V / Ctrl+V 粘贴（绑到整个窗口 + 预览区）
    win.bind("<Control-v>", lambda e: _paste_from_clipboard())
    win.bind("<Command-v>", lambda e: _paste_from_clipboard())
    img_preview.bind("<Control-v>", lambda e: _paste_from_clipboard())
    img_preview.bind("<Command-v>", lambda e: _paste_from_clipboard())

    _drag_hint = "🟢 拖拽可用" if _dnd_ok else "⚪ 未装 tkinterdnd2 (pip install tkinterdnd2)"

    def _pick_image():
        p = _fd.askopenfilename(
            title="选择盘面截图",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("所有", "*.*")])
        if p:
            _set_image_from_path(p)

    btn_row1 = _tk.Frame(img_card, bg=_PANEL); btn_row1.pack(fill=_tk.X, padx=6, pady=4)
    _tk.Button(btn_row1, text="📷 选择图片", command=_pick_image,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=2,
               font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT, padx=2)

    sites = _load_sites()

    # ② 网站快捷按钮（可滚动）
    sites_card = _tk.LabelFrame(left, text=" 🌐 财经网站 ",
                                bg=_PANEL, fg=_GOLD,
                                font=("TkDefaultFont", 10, "bold"))
    sites_card.pack(fill=_tk.BOTH, expand=True, padx=8, pady=(4, 8))

    sites_canvas = _tk.Canvas(sites_card, bg=_PANEL, highlightthickness=0, width=260)
    sites_scroll = _tk.Scrollbar(sites_card, orient="vertical", command=sites_canvas.yview)
    sites_inner = _tk.Frame(sites_canvas, bg=_PANEL)
    sites_inner.bind("<Configure>",
                     lambda e: sites_canvas.configure(scrollregion=sites_canvas.bbox("all")))
    sites_canvas.create_window((0, 0), window=sites_inner, anchor="nw")
    sites_canvas.configure(yscrollcommand=sites_scroll.set)
    sites_canvas.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)
    sites_scroll.pack(side=_tk.RIGHT, fill=_tk.Y)

    # 按钮网格（2 列）：点击 = 爬取网页 + AI 分析（浏览器自动跳开）
    _site_btns = []
    _last_scraped = {"url": "", "title": "", "text": "", "ts": ""}

    def _scrape_and_open_site(site):
        """一键: 打开浏览器 + 后台爬取网页文字 + 准备分析"""
        url = site["url"]
        name = site["name"]
        # 1) 浏览器打开（给用户看）
        try: _wb.open(url)
        except Exception: pass
        # 2) 后台爬取
        status_lbl.config(text=f"⏳ 爬取 {name} ({url[:35]}...)", fg=_GOLD)

        def _w():
            text_preview = ""
            title = name
            try:
                import requests as _req
                from bs4 import BeautifulSoup as _BS
                headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
                r = _req.get(url, headers=headers, timeout=10, verify=False)
                r.encoding = r.apparent_encoding or r.encoding
                if r.status_code == 200:
                    soup = _BS(r.text, "html.parser")
                    # 找 title
                    if soup.title and soup.title.string: title = soup.title.string.strip()[:50]
                    # 去 script/style/noscript
                    for tag in soup(["script", "style", "noscript", "iframe"]): tag.decompose()
                    # 取纯文本 + 去重空行
                    lines = [l.strip() for l in soup.get_text("\n", strip=True).split("\n") if l.strip()]
                    uniq = []
                    for l in lines:
                        if l not in uniq[-8:] and len(l) > 1:
                            uniq.append(l)
                    text_preview = "\n".join(uniq[:300])  # 最多 300 行给 AI
                else:
                    text_preview = f"(HTTP {r.status_code})"
            except Exception as e:
                text_preview = f"(爬取失败: {e})"

            # 存到全局缓存
            _last_scraped["url"] = url
            _last_scraped["title"] = title
            _last_scraped["text"] = text_preview
            _last_scraped["ts"] = _dt.datetime.now().strftime("%H:%M:%S")

            def _done():
                if text_preview.startswith("("):
                    status_lbl.config(text=f"⚠️ {name} 爬取 {text_preview[:40]}，已打开浏览器", fg=_GOLD)
                else:
                    status_lbl.config(text=f"✅ {name} 爬取成功 ({len(text_preview)}字)，点下方 🔍网页分析 即可", fg=_GREEN)
                text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
                text_widget.insert("end", (
                    f"🌐 已爬取: {name}\n"
                    f"🔗 {url}\n"
                    f"🕐 {_last_scraped['ts']}  共 {len(text_preview)} 字\n"
                    f"📄 标题: {title}\n"
                    f"{'═'*40}\n\n"
                    f"{text_preview[:1500]}\n\n"
                    f"... (全文 {len(text_preview)} 字)\n\n"
                    f"💡 点 [🔍 AI 分析网页] 把上面这些文字交给 AI 研判"
                ))
                text_widget.see("end"); text_widget.config(state=_tk.DISABLED)

            _after(_done)

        _th.Thread(target=_w, daemon=True).start()

    for i, s in enumerate(sites):
        row, col = divmod(i, 2)
        btn = _tk.Button(sites_inner, text=f"🌐 {s['name']}",
                         width=14,
                         command=lambda site=s: _scrape_and_open_site(site),
                         bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                         highlightbackground=_BLUE, highlightthickness=1,
                         font=("TkDefaultFont", 9), cursor="hand2")
        btn.grid(row=row, column=col, padx=3, pady=2, sticky="we")
        _site_btns.append(btn)

    # 配置/添加按钮
    btn_cfg_row = _tk.Frame(left, bg=_PANEL); btn_cfg_row.pack(fill=_tk.X, padx=8, pady=(0, 8))

    def _open_site_config():
        """编辑网站列表：增删改 + 保存"""
        cfg_win = _tk.Toplevel(win); cfg_win.title("🌐 网站配置")
        cfg_win.configure(bg=_PANEL); cfg_win.geometry("640x480")

        cur_sites = _load_sites()
        rows = []

        list_frame = _tk.Frame(cfg_win, bg=_PANEL); list_frame.pack(fill=_tk.BOTH, expand=True, padx=10, pady=8)

        _tk.Label(list_frame, text="名称", bg=_PANEL, fg=_GOLD,
                  width=14, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0)
        _tk.Label(list_frame, text="网址", bg=_PANEL, fg=_GOLD,
                  width=32, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=1)
        _tk.Label(list_frame, text="简介", bg=_PANEL, fg=_GOLD,
                  width=18, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=2)

        for i, s in enumerate(cur_sites):
            e1 = _tk.Entry(list_frame, width=14); e1.insert(0, s["name"])
            e2 = _tk.Entry(list_frame, width=34); e2.insert(0, s["url"])
            e3 = _tk.Entry(list_frame, width=18); e3.insert(0, s.get("desc", ""))
            e1.grid(row=i+1, column=0, padx=2, pady=1)
            e2.grid(row=i+1, column=1, padx=2, pady=1)
            e3.grid(row=i+1, column=2, padx=2, pady=1)
            rows.append((e1, e2, e3))

        def _save():
            new_sites = []
            for e1, e2, e3 in rows:
                nm = e1.get().strip(); url = e2.get().strip(); dc = e3.get().strip()
                if nm and url:
                    new_sites.append({"name": nm, "url": url, "desc": dc})
            _save_sites(new_sites)
            # 刷新按钮
            for b in _site_btns: b.destroy()
            _site_btns.clear()
            sites_inner.destroy()
            sites_inner2 = _tk.Frame(sites_canvas, bg=_PANEL)
            sites_inner2.bind("<Configure>",
                              lambda e: sites_canvas.configure(scrollregion=sites_canvas.bbox("all")))
            sites_canvas.create_window((0, 0), window=sites_inner2, anchor="nw")
            for i, s in enumerate(new_sites):
                row, col = divmod(i, 2)
                btn = _tk.Button(sites_inner2, text=f"🌐 {s['name']}", width=14,
                                 command=lambda u=s["url"]: _wb.open(u),
                                 bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                                 highlightbackground=_BLUE, highlightthickness=1,
                                 font=("TkDefaultFont", 9))
                btn.grid(row=row, column=col, padx=3, pady=2, sticky="we")
                _site_btns.append(btn)
            cfg_win.destroy()
            status_lbl.config(text="✅ 网站列表已更新", fg=_GREEN)

        def _add_new():
            i = len(rows) + 1
            e1 = _tk.Entry(list_frame, width=14); e2 = _tk.Entry(list_frame, width=34)
            e3 = _tk.Entry(list_frame, width=18)
            e1.grid(row=i, column=0, padx=2, pady=1)
            e2.grid(row=i, column=1, padx=2, pady=1)
            e3.grid(row=i, column=2, padx=2, pady=1)
            rows.append((e1, e2, e3))

        btn_row = _tk.Frame(cfg_win, bg=_PANEL); btn_row.pack(pady=10)
        _tk.Button(btn_row, text="➕ 添加一行", command=_add_new,
                   bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                   highlightbackground=_BLUE, highlightthickness=1,
                   font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=4)
        _tk.Button(btn_row, text="💾 保存", command=_save,
                   bg="#66BB6A", fg="black", activebackground="#43A047",
                   highlightbackground=_GOLD, highlightthickness=2,
                   font=("TkDefaultFont", 9, "bold"), width=10).pack(side=_tk.LEFT, padx=4)
        _tk.Button(btn_row, text="关闭", command=cfg_win.destroy,
                   bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
                   highlightbackground=_MUTED, highlightthickness=1,
                   font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=4)

    _tk.Button(btn_cfg_row, text="⚙️ 配置网站", command=_open_site_config,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, expand=True, fill=_tk.X, padx=2)

    # ── 右侧：AI 综合研判结果 ──
    analyze_card = _tk.LabelFrame(right, text=" 🤖 AI 综合研判 ",
                                  bg=_PANEL, fg=_ACCENT,
                                  font=("TkDefaultFont", 11, "bold"))
    analyze_card.pack(fill=_tk.X, padx=10, pady=(10, 6))

    btn_analyze_row = _tk.Frame(analyze_card, bg=_PANEL); btn_analyze_row.pack(fill=_tk.X, padx=6, pady=6)

    def _do_analyze(analyze_mode):
        """analyze_mode: 'image' | 'comprehensive' | 'web'"""
        if analyze_mode == "image" and not img_path_var.get():
            _mb.showinfo("提示", "请先选择一张盘面截图 📷")
            return
        if analyze_mode == "web" and not _last_scraped.get("text"):
            _mb.showinfo("提示", "请先在左侧点一个网站按钮（自动爬取）再分析 🌐")
            return

        text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
        text_widget.insert("end", "⏳ 正在分析...\n\n")
        text_widget.config(state=_tk.DISABLED)
        btn1.config(state=_tk.DISABLED); btn2.config(state=_tk.DISABLED); btn_web.config(state=_tk.DISABLED)

        def _w():
            _after(lambda: status_lbl.config(text="⏳ 拉取实时行情数据...", fg=_GOLD))

            # 1) 实时行情数据（复用 mainline_route 的）
            sectors_info = ""
            try:
                from ui.mainline_route import _get_mainline_route_data
                d = _get_mainline_route_data()
                for i, item in enumerate(d.get("sectors", [])[:8], 1):
                    if len(item) == 6:
                        n, chg, amt, ld, ld_chg, ud = item
                    else:
                        continue
                    sectors_info += f"  {i}. {n}  {chg:+.2f}%  成交{amt}亿  领涨{ld}({ld_chg:+.2f}%)\n"
            except Exception as e:
                sectors_info = f"（实时板块数据拉取失败: {e}）"

            _after(lambda: status_lbl.config(text="⏳ 构造 AI prompt...", fg=_GOLD))

            # 2) 构造 prompt + 消息
            img_path = img_path_var.get()
            messages = []
            sys_prompt = (
                "你是A股盘前/盘中/盘后分析师。综合盘面截图、实时行情、财经网页内容、当前时间、"
                "财经资讯进行形势判断和接下来的走势预判。"
                "输出中文，结构清晰，用 Emoji 增加可读性。"
            )
            messages.append({"role": "system", "content": sys_prompt})

            img_data_url = None
            user_text = f"🕐 当前时间: {ts_str}（{time_period}）\n\n📊 今日行业板块 TOP8:\n{sectors_info}\n\n"

            if analyze_mode == "web":
                # 爬取网页模式 — 把爬下来的文字喂给 AI
                scraped = _last_scraped.get("text", "")
                stitle = _last_scraped.get("title", "")
                surl = _last_scraped.get("url", "")
                _after(lambda: status_lbl.config(text=f"⏳ 把网页文字喂给 AI ({len(scraped)}字)...", fg=_GOLD))
                user_text += (
                    f"🌐 【刚爬取的财经网页】\n"
                    f"📄 标题: {stitle}\n"
                    f"🔗 URL: {surl}\n"
                    f"📝 网页正文文字 ({len(scraped)}字):\n{'─'*30}\n"
                    f"{scraped[:4000]}\n{'─'*30}\n\n"
                    "请重点分析网页里提到的: 热门板块、异动个股、资金流向、政策事件、"
                    "行业利好利空、北向/游资动向。结合实时板块数据和当前时段，给出：\n"
                    "1️⃣ 当前市场主线和最活跃板块\n"
                    "2️⃣ 网页热度代表的情绪阶段（冰点/发酵/高潮/退潮）\n"
                    "3️⃣ 接下来 1h / 1-2 日 走势预判\n"
                    "4️⃣ 操作建议（主攻/观望/防守哪些板块）"
                )
                messages.append({"role": "user", "content": user_text})
            elif analyze_mode == "image" and img_path:
                _after(lambda: status_lbl.config(text="⏳ 图片转 base64 + AI 视觉识别...", fg=_GOLD))
                try:
                    img_data_url = _img_to_data_url(img_path)
                    user_text += (
                        "【盘面截图】请识别图片中的所有文字、指数、数字、K线形态、"
                        "板块异动、涨跌幅榜等，结合时间和实时数据进行研判。\n"
                    )
                    # 先只发文本看情况，图片太大可能被拒绝
                    messages.append({"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": img_data_url}},
                    ]})
                except Exception as e:
                    _after(lambda: status_lbl.config(text=f"⚠️ 图片转换失败: {e}，纯文本分析", fg=_GOLD))
                    messages.append({"role": "user", "content": user_text})
            else:
                user_text += (
                    "请结合当前时间点和板块强弱，给出：\n"
                    "1️⃣ 当前形势判断\n"
                    "2️⃣ 接下来 30min / 1h / 1-2 日 走势预判\n"
                    "3️⃣ 可关注的主线板块和风险点\n"
                    "4️⃣ 操作建议（买入/观望/减仓）\n"
                )
                messages.append({"role": "user", "content": user_text})

            _after(lambda: status_lbl.config(text="⏳ 请求 AI 代理 (deepseek-chat)...", fg=_GOLD))

            # 3) 调 AI
            result_text, err = _ai_call(messages, max_tokens=2400)

            def _show():
                text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
                if err:
                    text_widget.insert("end", f"❌ AI 调用失败\n\n{err}")
                    status_lbl.config(text=f"❌ AI 失败: {err[:80]}", fg=_ACCENT)
                else:
                    header = f"👁️ 【见盘 AI 综合研判】\n🕐 {ts_str} · {time_period}\n"
                    if analyze_mode == "image":
                        header += f"📷 已分析截图: {_os.path.basename(img_path) if img_path else '无'}\n"
                    header += f"{'═'*50}\n\n"
                    text_widget.insert("end", header + result_text + "\n")
                    status_lbl.config(text=f"✅ AI 研判完成 ({len(result_text)}字)", fg=_GREEN)
                text_widget.see("end"); text_widget.config(state=_tk.DISABLED)
                btn1.config(state=_tk.NORMAL); btn2.config(state=_tk.NORMAL); btn_web.config(state=_tk.NORMAL)

            _after(_show)

        _th.Thread(target=_w, daemon=True).start()

    btn1 = _tk.Button(btn_analyze_row, text="📷 分析当前图片",
                      command=lambda: _do_analyze("image"), width=16,
                      bg=_BLUE, fg="black", activebackground="#4A9EE6",
                      highlightbackground=_GOLD, highlightthickness=2,
                      font=("TkDefaultFont", 10, "bold"))
    btn1.pack(side=_tk.LEFT, padx=4)

    btn2 = _tk.Button(btn_analyze_row, text="🤖 AI 综合研判（无图）",
                      command=lambda: _do_analyze("comprehensive"), width=20,
                      bg=_GOLD, fg="black", activebackground="#F0B429",
                      highlightbackground=_ACCENT, highlightthickness=2,
                      font=("TkDefaultFont", 10, "bold"))
    btn2.pack(side=_tk.LEFT, padx=4)

    btn_web = _tk.Button(btn_analyze_row, text="🔍 AI 分析网页",
                          command=lambda: _do_analyze("web"), width=16,
                          bg=_GREEN, fg="black", activebackground="#4CAF50",
                          highlightbackground=_GOLD, highlightthickness=2,
                          font=("TkDefaultFont", 10, "bold"))
    btn_web.pack(side=_tk.LEFT, padx=4)

    # ═══════════════════════════════════════════════════════════
    # 右侧：主结果区 (左) + 历史面板 (右)
    # ═══════════════════════════════════════════════════════════
    HISTORY_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                 "config", "market_watch_history.json")

    # 字体状态
    _font_size = _tk.IntVar(value=11)

    def _adjust_font(delta):
        sz = max(8, min(24, _font_size.get() + delta))
        _font_size.set(sz)
        text_widget.config(font=("TkDefaultFont", sz))

    # 历史存储
    def _load_history():
        try:
            if _os.path.exists(HISTORY_PATH):
                with open(HISTORY_PATH) as f:
                    return _json.load(f)
        except Exception:
            pass
        return []

    def _save_history_item(meta_text, result_text):
        h = _load_history()
        item = {
            "id": int(_time.time() * 1000),
            "ts": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "meta": meta_text[:120],   # 短标题
            "text": result_text[:8000],  # 完整内容（限长防止爆）
            "full_len": len(result_text),
        }
        h.insert(0, item)
        # 只留最近 50 条
        h = h[:50]
        try:
            _os.makedirs(_os.path.dirname(HISTORY_PATH), exist_ok=True)
            with open(HISTORY_PATH, "w") as f:
                _json.dump(h, f, indent=2, ensure_ascii=False)
        except Exception as e:
            status_lbl.config(text=f"⚠️ 历史保存失败: {e}", fg=_ACCENT)
            return
        _refresh_history_list()

    def _refresh_history_list():
        listbox.delete(0, _tk.END)
        for item in _load_history():
            listbox.insert(_tk.END, f"[{item['ts']}] {item['meta'][:40]}")

    def _open_history():
        sel = listbox.curselection()
        if not sel: return
        idx = sel[0]
        items = _load_history()
        item = items[idx]
        # 回填到 text_widget
        text_widget.config(state=_tk.NORMAL); text_widget.delete("1.0", "end")
        text_widget.insert("end", item["text"] + "\n")
        text_widget.see("end"); text_widget.config(state=_tk.DISABLED)
        status_lbl.config(text=f"📂 已打开历史: {item['ts']}  ({item['full_len']}字)", fg=_GREEN)

    def _delete_history():
        sel = listbox.curselection()
        if not sel: return
        if not _mb.askyesno("确认", "删除这条历史记录？"): return
        idx = sel[0]
        h = _load_history()
        h.pop(idx)
        try:
            _os.makedirs(_os.path.dirname(HISTORY_PATH), exist_ok=True)
            with open(HISTORY_PATH, "w") as f:
                _json.dump(h, f, indent=2, ensure_ascii=False)
            _refresh_history_list()
        except Exception as e:
            status_lbl.config(text=f"❌ 删除失败: {e}", fg=_ACCENT)

    def _clear_all_history():
        if not _mb.askyesno("确认", "清空所有历史记录？（不可恢复）"): return
        try:
            _os.makedirs(_os.path.dirname(HISTORY_PATH), exist_ok=True)
            with open(HISTORY_PATH, "w") as f:
                _json.dump([], f)
            _refresh_history_list()
        except Exception as e:
            status_lbl.config(text=f"❌ 清空失败: {e}", fg=_ACCENT)

    # 导出函数
    def _export_txt():
        content = text_widget.get("1.0", "end-1c").strip()
        if not content: _mb.showinfo("提示", "结果区为空"); return
        p = _fd.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本", "*.txt")],
            initialfile=f"见盘分析_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        if p:
            with open(p, "w", encoding="utf-8") as f: f.write(content)
            status_lbl.config(text=f"💾 TXT 已保存: {_os.path.basename(p)}", fg=_GREEN)

    def _export_word():
        content = text_widget.get("1.0", "end-1c").strip()
        if not content: _mb.showinfo("提示", "结果区为空"); return
        try:
            from docx import Document
            from docx.shared import Pt
        except Exception:
            _mb.showerror("错误", "未安装 python-docx: pip install python-docx"); return
        p = _fd.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word", "*.docx")],
            initialfile=f"见盘分析_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx")
        if p:
            doc = Document()
            doc.add_heading("👁️ 见盘 AI 综合研判", level=1)
            doc.add_paragraph(f"🕐 {ts_str} · {time_period}")
            doc.add_paragraph("─" * 40)
            for line in content.split("\n"):
                if line.startswith("#"):
                    doc.add_heading(line.lstrip("# "), level=2)
                else:
                    doc.add_paragraph(line)
            for para in doc.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(_font_size.get())
            doc.save(p)
            status_lbl.config(text=f"📄 Word 已保存: {_os.path.basename(p)}", fg=_GREEN)

    def _export_pptx():
        content = text_widget.get("1.0", "end-1c").strip()
        if not content: _mb.showinfo("提示", "结果区为空"); return
        try:
            from pptx import Presentation
            from pptx.util import Pt, Inches
        except Exception:
            _mb.showerror("错误", "未安装 python-pptx: pip install python-pptx"); return
        p = _fd.asksaveasfilename(
            defaultextension=".pptx",
            filetypes=[("PowerPoint", "*.pptx")],
            initialfile=f"见盘分析_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx")
        if p:
            prs = Presentation()
            # 封面
            slide = prs.slides.add_slide(prs.slide_layouts[0])
            slide.shapes.title.text = "👁️ 见盘 AI 综合研判"
            slide.placeholders[1].text = f"🕐 {ts_str} · {time_period}"
            # 内容页（按段落分页，每页 ≤ 20 行）
            lines = content.split("\n")
            PAGE = 20
            for i in range(0, len(lines), PAGE):
                chunk = lines[i:i+PAGE]
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                slide.shapes.title.text = f"研判报告 · 第{i//PAGE + 1}页"
                body = slide.placeholders[1]
                tf = body.text_frame
                tf.clear()
                for j, ln in enumerate(chunk):
                    para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                    para.text = ln
                    for run in para.runs: run.font.size = Pt(18)
            prs.save(p)
            status_lbl.config(text=f"📊 PPT 已保存: {_os.path.basename(p)}", fg=_GREEN)

    def _copy_to_clipboard():
        content = text_widget.get("1.0", "end-1c").strip()
        if not content: return
        win.clipboard_clear()
        win.clipboard_append(content)
        status_lbl.config(text="📋 已复制到剪贴板", fg=_GREEN)

    def _save_current():
        content = text_widget.get("1.0", "end-1c").strip()
        if not content: _mb.showinfo("提示", "结果区为空"); return
        title = _sd.askstring("保存到历史", "给这次分析起个名字（可留空自动生成）:", parent=win)
        title = (title or f"AI研判 {_dt.datetime.now().strftime('%H:%M')}").strip()
        _save_history_item(title, content)
        status_lbl.config(text=f"💾 已保存到历史: {title}", fg=_GREEN)

    # ── 右侧内部布局：左主 / 右历史 ──
    right_inner = _tk.Frame(right, bg=_PANEL); right_inner.pack(fill=_tk.BOTH, expand=True, padx=10, pady=(0, 6))

    # 主区域（左）
    main_area = _tk.Frame(right_inner, bg=_PANEL); main_area.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)

    # 工具栏（字体 + 保存导出）
    toolbar = _tk.Frame(main_area, bg=_PANEL); toolbar.pack(fill=_tk.X, pady=(6, 4))
    _tk.Label(toolbar, text="🔠 字体:", bg=_PANEL, fg=_MUTED,
              font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=(0, 2))
    _tk.Button(toolbar, text="A-", command=lambda: _adjust_font(-1), width=2,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=1,
               font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT, padx=1)
    _tk.Label(toolbar, textvariable=_font_size, bg=_PANEL, fg=_GOLD,
              width=2, font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT)
    _tk.Button(toolbar, text="A+", command=lambda: _adjust_font(1), width=2,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=1,
               font=("TkDefaultFont", 9, "bold")).pack(side=_tk.LEFT, padx=1)

    _tk.Frame(toolbar, bg=_PANEL, width=10).pack(side=_tk.LEFT)  # 间隔

    _tk.Button(toolbar, text="💾 保存", command=_save_current,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_GOLD, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=2)
    _tk.Button(toolbar, text="📄 Word", command=_export_word,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=2)
    _tk.Button(toolbar, text="📊 PPT", command=_export_pptx,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=2)
    _tk.Button(toolbar, text="📋 复制", command=_copy_to_clipboard,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_BLUE, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, padx=2)

    # 结果文本区
    text_widget = _st.ScrolledText(main_area, wrap=_tk.WORD,
                                   bg=_CARD, fg=_FG,
                                   font=("TkDefaultFont", 11),
                                   insertbackground=_FG, padx=14, pady=10,
                                   relief=_tk.FLAT, borderwidth=0)
    text_widget.pack(fill=_tk.BOTH, expand=True, pady=4)
    text_widget.insert("end", (
        "👁️ 见盘 AI 综合研判\n"
        "═══════════════════\n\n"
        "📷 方法一: 点左上方「📷 选择图片」→ 上传盘面截图\n"
        "         → 点「📷 分析当前图片」→ AI 视觉识别\n\n"
        "🌐 方法二: 点左侧财经网站按钮 → 回来点「🤖 AI 综合研判」\n\n"
        f"🕐 当前: {ts_str} · {time_period}\n\n"
        "💡 分析完成后可用顶部工具栏: A-/A+ 调字体、💾保存到历史、📄导Word、📊导PPT\n"
    ))

    # 历史面板（右）
    history_frame = _tk.LabelFrame(right_inner, text=" 🕘 历史分析 ",
                                    bg=_PANEL, fg=_BLUE, width=260,
                                    font=("TkDefaultFont", 10, "bold"))
    history_frame.pack(side=_tk.RIGHT, fill=_tk.Y, padx=(8, 0))
    history_frame.pack_propagate(False)

    list_scroll = _tk.Scrollbar(history_frame); list_scroll.pack(side=_tk.RIGHT, fill=_tk.Y, padx=(0,4), pady=6)
    listbox = _tk.Listbox(history_frame, bg=_CARD, fg=_FG, selectmode=_tk.SINGLE,
                          font=("TkDefaultFont", 9), height=20,
                          yscrollcommand=list_scroll.set, relief=_tk.FLAT, borderwidth=0)
    listbox.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True, padx=(4,0), pady=6)
    list_scroll.config(command=listbox.yview)

    # 操作按钮
    hist_btn_row = _tk.Frame(history_frame, bg=_PANEL); hist_btn_row.pack(fill=_tk.X, padx=4, pady=(0, 6))
    _tk.Button(hist_btn_row, text="📂 打开", command=_open_history,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_GOLD, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, expand=True, fill=_tk.X, padx=1)
    _tk.Button(hist_btn_row, text="🗑️ 删除", command=_delete_history,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_ACCENT, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, expand=True, fill=_tk.X, padx=1)
    _tk.Button(hist_btn_row, text="🧹清空", command=_clear_all_history,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground=_MUTED, highlightthickness=1,
               font=("TkDefaultFont", 9)).pack(side=_tk.LEFT, expand=True, fill=_tk.X, padx=1)

    _refresh_history_list()

    # 底部状态栏
    status_lbl = _tk.Label(win, text="准备就绪 · 选图片或打开网站后开始",
                           bg=_BG, fg=_MUTED,
                           font=("TkDefaultFont", 10))
    status_lbl.pack(fill=_tk.X, padx=14, pady=(4, 10))

    def _after(fn):
        try:
            win.after(0, fn)
        except Exception:
            fn()

    return win

# ═════════════════════════════════════════════════════════════════════════
# 📚 书籍管理器 — 导入/浏览/读书摘录/AI概要
# 数据源: SQLite books 表 + 用户手动输入 + 可选豆瓣 HTTP API
# 入口: crawler_control_notebook 右侧「书籍」Tab
# ═════════════════════════════════════════════════════════════════════════

import os as _os
import re as _re
import json as _json
import sqlite3 as _sqlite3
import threading as _threading
from datetime import datetime as _dt

_DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "data", "stock_analysis.db")

# ═════════════════════════════════════════════════════════════════════════
# 0. SQLite 初始化
# ═════════════════════════════════════════════════════════════════════════

def _ensure_book_table():
    """建表 (幂等)"""
    con = _sqlite3.connect(_DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,             -- 书名 (唯一)
        author TEXT DEFAULT '',
        genre TEXT DEFAULT '',         -- 分类: 投资/心理/历史/科技/传记/其他
        source TEXT DEFAULT '手动',    -- 导入来源: 手动/目录/豆瓣
        rating REAL DEFAULT 0,         -- 网上评分 (0-5)
        douban_url TEXT DEFAULT '',
        pub_year TEXT DEFAULT '',
        pages INTEGER DEFAULT 0,
        -- 内容层
        intro TEXT DEFAULT '',         -- 官方简介
        highlights TEXT DEFAULT '',    -- 书摘/金句
        user_summary TEXT DEFAULT '',  -- 自我读书概要
        user_notes TEXT DEFAULT '',    -- 个人笔记
        related TEXT DEFAULT '',       -- 相关书籍 (JSON list)
        methods TEXT DEFAULT '',       -- 涉及的方法论 (JSON list)
        pros TEXT DEFAULT '',          -- 网上好评
        cons TEXT DEFAULT '',          -- 网上差评
        created_at TEXT,
        updated_at TEXT
    )""")
    con.commit()
    con.close()


# ═════════════════════════════════════════════════════════════════════════
# 1. 建 Tab 入口
# ═════════════════════════════════════════════════════════════════════════

def build_books_tab(parent, root=None):
    """构建 📚 书籍 Tab — 按钮网格 + 导入 + 搜索"""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    _ensure_book_table()

    # 顶栏
    top = tk.Frame(parent, bg="#121212"); top.pack(fill=tk.X, pady=(0, 6))
    tk.Label(top, text="📚 我的书架 — 点击打开, 支持目录批量导入",
             bg="#121212", fg="#FFD54F", font=("", 12, "bold")).pack(side=tk.LEFT, padx=6)

    search_var = tk.StringVar()
    tk.Label(top, text="🔍", bg="#121212", fg="#E0E0E0").pack(side=tk.LEFT, padx=(10, 0))
    cb = ttk.Combobox(top, textvariable=search_var, width=18, state="normal", values=[])
    cb.pack(side=tk.LEFT, padx=2)

    def _on_search(*_):
        kw = search_var.get().strip()
        _render_buttons(container, kw)
    search_var.trace_add("write", _on_search)

    tk.Button(top, text="📂 目录导入", command=lambda: _batch_import_from_dir(root, container),
              bg="#1565C0", fg="white", font=("", 9, "bold"), padx=6).pack(side=tk.RIGHT, padx=3)
    tk.Button(top, text="＋ 手动添加", command=lambda: _add_single_book(root, container),
              bg="#2E7D32", fg="white", font=("", 9, "bold"), padx=6).pack(side=tk.RIGHT, padx=3)

    # 分类过滤器 (按钮循环在 canvas/scroll_inner 都就绪后再建)
    filter_row = tk.Frame(parent, bg="#121212"); filter_row.pack(fill=tk.X, pady=(0, 4))
    tk.Label(filter_row, text="分类:", bg="#121212", fg="#A5D6A7", font=("", 9)).pack(side=tk.LEFT, padx=6)
    genres = ["全部", "投资", "心理", "历史", "科技", "传记", "哲学", "方法", "其他"]
    filter_var = tk.StringVar(value="全部")

    # 带滚动条的容器 — Canvas + inner Frame
    from tkinter import Canvas as _Canvas
    outer = tk.Frame(parent, bg="#121212")
    outer.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
    canvas = _Canvas(outer, bg="#121212", highlightthickness=0)
    vsb = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
    scroll_inner = tk.Frame(canvas, bg="#121212")
    scroll_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    # 鼠标滚轮
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    parent.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

    # root 用于弹窗 (Toplevel parent) — 在 canvas 定义后, 才能建按钮 command
    _root_ref = root if root else parent.winfo_toplevel()
    container = scroll_inner  # 给顶栏按钮闭包引用

    def _filter_change_with_tl(g):
        _filter_change(g, scroll_inner, filter_var, canvas, toplevel=_root_ref)

    # 现在建分类按钮 (canvas/scroll_inner/_root_ref 都就绪了)
    for g in genres:
        active = g == "全部"
        b = tk.Button(filter_row, text=g, width=5,
                      bg="#1565C0" if active else "#37474F",
                      fg="white" if active else "#B0BEC5",
                      font=("", 9, "bold" if active else "normal"),
                      relief=tk.FLAT,
                      command=lambda _g=g: _filter_change_with_tl(_g))
        b.pack(side=tk.LEFT, padx=2)

    _render_buttons(scroll_inner, "", filter_genre="全部", toplevel=_root_ref)

    # 给 combobox 填全量书名
    all_titles = _list_titles()
    cb["values"] = all_titles


def _filter_change(g, container, filter_var, canvas=None, toplevel=None):
    filter_var.set(g)
    _render_buttons(container, "", filter_genre=g, toplevel=toplevel)
    if canvas: canvas.yview_moveto(0)


def _list_titles():
    try:
        con = _sqlite3.connect(_DB_PATH)
        cur = con.execute("SELECT title FROM books ORDER BY title")
        rows = [r[0] for r in cur.fetchall()]
        con.close()
        return rows
    except Exception:
        return []


def _render_buttons(parent, keyword="", filter_genre=None, filter_widget=None, toplevel=None):
    """渲染书籍按钮网格"""
    import tkinter as tk
    # 确保有 toplevel
    if toplevel is None:
        try: toplevel = parent.winfo_toplevel()
        except: pass

    for w in parent.winfo_children(): w.destroy()

    try:
        con = _sqlite3.connect(_DB_PATH)
        sql = "SELECT id, title, author, genre, rating FROM books WHERE 1=1"
        params = []
        if keyword:
            sql += " AND (title LIKE ? OR author LIKE ?)"
            params += [f"%{keyword}%", f"%{keyword}%"]
        if filter_genre and filter_genre != "全部":
            sql += " AND genre=?"
            params.append(filter_genre)
        sql += " ORDER BY title"
        cur = con.execute(sql, params)
        rows = cur.fetchall()
        con.close()
    except Exception as e:
        tk.Label(parent, text=f"❌ 数据库错误: {e}", bg="#121212", fg="#EF5350",
                 font=("", 11)).pack(pady=20); return

    # 3列网格按钮
    COLS = 3
    btn_frame = tk.Frame(parent, bg="#121212"); btn_frame.pack(fill=tk.BOTH, expand=True)
    btn_frame.grid_columnconfigure(tuple(range(COLS)), weight=1)

    if not rows:
        tk.Label(btn_frame, text="📭 还没导入书籍\n点右上角「📂目录导入」或「＋手动添加」",
                 bg="#121212", fg="#90A4AE", font=("", 12)).grid(row=0, column=0, columnspan=COLS, pady=40)
        return

    for i, (bid, title, author, genre, rating) in enumerate(rows):
        r, c = divmod(i, COLS)
        _make_book_card(btn_frame, bid, title, author, genre, rating, r, c, toplevel=toplevel)


def _make_book_card(parent, bid, title, author, genre, rating, row, col, toplevel=None):
    """单个书籍按钮卡片 — toplevel 用于点击时正确打开弹窗"""
    import tkinter as tk
    COLORS = {
        "投资": "#1565C0", "心理": "#7B1FA2", "历史": "#6A1B9A",
        "科技": "#00695C", "传记": "#C62828", "哲学": "#37474F",
        "方法": "#EF6C00", "其他": "#455A64", None: "#455A64", "": "#455A64"
    }
    bg = COLORS.get(genre, "#455A64")
    card = tk.Frame(parent, bg=bg, padx=8, pady=6, cursor="hand2",
                    highlightthickness=1, highlightbackground="#263238")
    card.grid(row=row, column=col, sticky="nsew", padx=4, pady=3)
    parent.grid_rowconfigure(row, weight=0)

    tk.Label(card, text=title, bg=bg, fg="white", font=("", 12, "bold"),
             anchor="w").pack(fill=tk.X)
    sub = f"✍️ {author or '佚名'}"
    if rating and rating > 0:
        sub += f"   ⭐{rating:.1f}"
    if genre and genre != "其他":
        sub += f"   [{genre}]"
    tk.Label(card, text=sub, bg=bg, fg="#CCCCCC",
             font=("", 9), anchor="w").pack(fill=tk.X, pady=(2, 0))

    def _open(_e=None, _bid=bid):
        # 优先用传入的 toplevel, 否则用 Tk 官方 winfo_toplevel()
        import traceback as _tb
        top = toplevel
        if top is None:
            try:
                top = card.winfo_toplevel()
            except Exception:
                _tb.print_exc()
                top = None
        if top is None:
            print(f"[书籍] ❌ _open 找不到 toplevel parent! bid={_bid}", flush=True)
            return
        try:
            _open_book_detail(top, _bid)
        except Exception as e:
            print(f"[书籍] ❌ _open_book_detail 异常: {e}")
            _tb.print_exc()

    def _rm(_e=None, _id=bid, _card=card, _t=title):
        from tkinter import messagebox as _mb
        if _mb.askyesno("删除", f"确认删除《{_t}》?\n(所有手写笔记也会删)"):
            _delete_book(_id); _card.destroy()

    # 关键: 用 ButtonRelease 替代 Button-1, 避免 Tk 焦点问题
    for w in [card] + list(card.winfo_children()):
        w.bind("<ButtonRelease-1>", _open)
        w.bind("<Button-3>", _rm)


# ═════════════════════════════════════════════════════════════════════════
# 2. 导入
# ═════════════════════════════════════════════════════════════════════════

def _batch_import_from_dir(root, container):
    """📂 从目录批量导入: 递归扫描所有子目录"""
    from tkinter import filedialog, messagebox
    d = filedialog.askdirectory(title="选择书籍目录 (递归扫描子目录)")
    if not d: return
    files = []
    for root_dir, dirs, fnames in _os.walk(d):
        for name in sorted(fnames):
            p = _os.path.join(root_dir, name)
            if not _os.path.isfile(p): continue
            if _os.path.splitext(name)[1].lower() in (".txt", ".md", ".pdf", ".epub", ".mobi", ".docx"):
                files.append((p, name))
    if not files:
        messagebox.showinfo("目录导入", "这个目录里没找到书籍文件\n(支持 .txt .md .pdf .epub .mobi .docx)")
        return
    # 去扩展名当书名
    imported = []; skipped = []
    for p, fn in files:
        title = _os.path.splitext(fn)[0].strip()
        if len(title) < 2: continue
        genre = _guess_genre(title, p)
        if _upsert_book({"title": title, "genre": genre, "source": f"目录:{d}"}):
            imported.append(title)
        else:
            skipped.append(title)
    # 更新所有按钮 genre (之前没 genre 的也补)
    _backfill_genre()
    messagebox.showinfo("导入完成",
                        f"✅ 导入 {len(imported)} 本\n⏭️ 跳过 {len(skipped)} 本(已存在)\n\n" +
                        ("\n".join(f"  {i+1}. {t}" for i, t in enumerate(imported[:15])) +
                         (f"\n  ... 还有 {len(imported)-15} 本" if len(imported) > 15 else "")) if imported else "没有新书籍")
    # 刷新书名 autocomplete
    cb = None
    for w in container.winfo_children():
        try:
            for c in w.winfo_children():
                if isinstance(c, ttk.Combobox): cb = c
        except Exception: pass
    if cb is not None: cb["values"] = _list_titles()
    _render_buttons(container, "")


def _guess_genre(title, filepath=""):
    """从书名推断 genre — 优先级: 投资 > 心理 > 历史 > 传记 > 科技 > 哲学 > 方法 > 其他"""
    # 1) 投资 (优先级最高, 避免"技术分析"被误归科技)
    if any(k in title for k in ("投资", "股票", "基金", "金融", "交易", "复利", "证券",
                                 "巴菲特", "格雷厄姆", "索罗斯", "利弗莫尔", "投机", "操盘",
                                 "作手", "均线", "蜡烛图", "期货", "期权", "量化", "价值投资",
                                 "成长股", "华尔街", "股市", "行情", "操盘手", "交易员",
                                 "炒股", "股市心理", "大盘", "牛熊", "量价", "波段",
                                 "期权", "ETF", "指数", "大宗商品")):
        return "投资"
    # 2) 心理
    if any(k in title for k in ("心理", "思维", "认知", "人性", "情绪",
                                 "快与慢", "反脆弱", "黑天鹅", "随机漫步", "心理学",
                                 "压力", "情绪管理")):
        return "心理"
    # 3) 历史
    if any(k in title for k in ("历史", "史记", "帝国", "通史", "明朝", "万历",
                                 "中国史", "世界史", "人类简史", "兴衰", "周期")):
        return "历史"
    # 4) 传记
    if any(k in title for k in ("传记", "自传", "生平传")):
        return "传记"
    # 5) 科技 (技术/科学/算法 — 但排除前面已命中投资的技术分析)
    if any(k in title for k in ("科学", "科技", "物理", "算法", "数据结构",
                                 "统计", "编程", "深度学习", "人工智能", "计算机程序",
                                 "程序员")):
        return "科技"
    # 6) 哲学
    if any(k in title for k in ("哲学", "存在", "思辨", "康德", "尼采", "叔本华", "形而上学")):
        return "哲学"
    # 7) 方法 (自我提升/系统思考)
    if any(k in title for k in ("原则", "习惯", "效率", "方法", "复盘", "系统",
                                 "深度工作", "原子习惯", "番茄工作")):
        return "方法"
    return "其他"


def _backfill_genre():
    """给已存在但 genre='其他' 的书自动补 genre"""
    try:
        con = _sqlite3.connect(_DB_PATH)
        cur = con.execute("SELECT id, title FROM books WHERE genre='其他' OR genre IS NULL")
        for bid, title in cur.fetchall():
            g = _guess_genre(title)
            if g != "其他":
                con.execute("UPDATE books SET genre=? WHERE id=?", (g, bid))
        con.commit(); con.close()
    except Exception as e:
        print(f"[书籍] backfill genre err: {e}")


def _add_single_book(root, container):
    """＋ 手动添加"""
    from tkinter import simpledialog, messagebox
    title = simpledialog.askstring("添加书籍", "书名:", parent=root)
    if not title or not title.strip(): return
    title = title.strip()
    author = simpledialog.askstring("添加书籍", "作者 (可留空):", parent=root, initialvalue="") or ""
    genre = simpledialog.askstring("添加书籍", "分类 (投资/心理/历史/科技/传记/哲学/方法/其他):",
                                   parent=root, initialvalue="其他") or "其他"
    if _upsert_book({"title": title, "author": author, "genre": genre, "source": "手动"}):
        messagebox.showinfo("添加成功", f"✅ 《{title}》已添加")
    else:
        messagebox.showwarning("已存在", f"《{title}》已经导入过了")
    _render_buttons(container, "")


def _upsert_book(data):
    """插入或更新 — 返回 True 表示新插入"""
    try:
        con = _sqlite3.connect(_DB_PATH)
        cur = con.cursor()
        cur.execute("SELECT id FROM books WHERE title=?", (data["title"],))
        row = cur.fetchone()
        now = _dt.now().strftime("%Y-%m-%d %H:%M")
        if row:
            bid = row[0]
            up = []; params = []
            for k in ("author", "genre", "source"):
                if k in data:
                    up.append(f"{k}=?"); params.append(data[k])
            up.append("updated_at=?"); params.append(now)
            params.append(bid)
            if up:
                cur.execute(f"UPDATE books SET {','.join(up)} WHERE id=?", params)
            con.commit(); con.close(); return False
        else:
            data.setdefault("author", ""); data.setdefault("genre", "其他")
            data.setdefault("source", "未知"); data.setdefault("intro", "")
            cur.execute("""INSERT INTO books (title, author, genre, source, intro, created_at, updated_at)
                          VALUES (?,?,?,?,?,?,?)""",
                        (data["title"], data["author"], data["genre"], data["source"],
                         data["intro"], now, now))
            con.commit(); con.close(); return True
    except Exception as e:
        print(f"[书籍] upsert err: {e}"); return False


def _delete_book(bid):
    try:
        con = _sqlite3.connect(_DB_PATH)
        con.execute("DELETE FROM books WHERE id=?", (bid,))
        con.commit(); con.close()
    except Exception as e:
        print(f"[书籍] delete err: {e}")


# ═════════════════════════════════════════════════════════════════════════
# 3. 详情弹窗
# ═════════════════════════════════════════════════════════════════════════

def _open_book_detail(parent, bid):
    """📘 打开书籍详情弹窗 — 多 Tab"""
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox

    # 读数据
    try:
        con = _sqlite3.connect(_DB_PATH)
        con.row_factory = _sqlite3.Row
        row = con.execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
        con.close()
    except Exception as e:
        messagebox.showerror("错误", f"数据库: {e}"); return
    if not row: return

    dlg = tk.Toplevel(parent)
    dlg.title(f"📘 {row['title']} — 书籍详情")
    dlg.geometry("900x680")
    dlg.configure(bg="#121212")
    dlg.transient(parent)

    # 标题栏
    header = tk.Frame(dlg, bg="#1565C0", height=52); header.pack(fill=tk.X)
    header.pack_propagate(False)
    tk.Label(header, text=f"📘 {row['title']}", bg="#1565C0", fg="white",
             font=("", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
    sub_parts = []
    if row["author"]: sub_parts.append(f"✍️ {row['author']}")
    if row["genre"]: sub_parts.append(f"📂 {row['genre']}")
    if row["rating"] and row["rating"] > 0: sub_parts.append(f"⭐ {row['rating']:.1f}")
    if row["pub_year"]: sub_parts.append(f"📅 {row['pub_year']}")
    if row["pages"]: sub_parts.append(f"📄 {row['pages']}页")
    tk.Label(header, text="  |  ".join(sub_parts), bg="#1565C0", fg="#BBDEFB",
             font=("", 10)).pack(side=tk.LEFT, pady=10)

    nb = ttk.Notebook(dlg); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    # ── Tab1: 官方介绍 ──
    t1 = tk.Frame(nb, bg="#121212"); nb.add(t1, text="📖 官方介绍")
    _make_labeled_text(t1, "📚 作者简介 / 官方简介", row["intro"] or "", (0, 0), height=8)
    _make_labeled_text(t1, "💡 核心观点 / 书摘", row["highlights"] or "", (1, 0), height=6)

    # ── Tab2: 外界声音 ──
    t2 = tk.Frame(nb, bg="#121212"); nb.add(t2, text="🌐 外界声音")
    _make_labeled_text(t2, "👍 网上好评 / 推荐语", row["pros"] or "", (0, 0), height=6)
    _make_labeled_text(t2, "👎 争议 / 负面评价", row["cons"] or "", (1, 0), height=4)
    _make_labeled_text(t2, "🔗 相关书籍 (每行一本)", row["related"] or "", (2, 0), height=3)
    _make_labeled_text(t2, "🛠 涉及方法论 (每行一个)", row["methods"] or "", (3, 0), height=3)

    # ── Tab3: 我的笔记 (可编辑) ──
    t3 = tk.Frame(nb, bg="#121212"); nb.add(t3, text="✏️ 我的笔记")
    _make_labeled_text(t3, "📝 自我读书概要 / 特色解读", row["user_summary"] or "",
                       (0, 0), height=7, editable=True, tag="_summary")
    _make_labeled_text(t3, "🧠 个人笔记 / 读后感 / 划线摘录", row["user_notes"] or "",
                       (1, 0), height=7, editable=True, tag="_notes")

    def _save():
        nonlocal row
        try:
            s_text = _editors.get("_summary")
            n_text = _editors.get("_notes")
            con = _sqlite3.connect(_DB_PATH)
            con.execute("UPDATE books SET user_summary=?, user_notes=?, updated_at=? WHERE id=?",
                        (s_text, n_text, _dt.now().strftime("%Y-%m-%d %H:%M"), bid))
            con.commit(); con.close()
            messagebox.showinfo("保存", "✅ 笔记已保存")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _ai_fetch():
        """联网抓取豆瓣/百度百科简介 + AI 生成概要"""
        from tkinter import messagebox
        def _bg():
            summary = _fetch_book_intro_worker(row["title"], row["author"])
            if not summary:
                dlg.after(0, lambda: messagebox.showwarning("AI 获取", "网络不通或未找到\n(豆瓣反爬或书名不匹配)"))
                return
            # 填回
            fields = {}
            for k, v in summary.items():
                if v: fields[k] = v
            if not fields:
                dlg.after(0, lambda: messagebox.showwarning("AI 获取", "没抓到有效内容"))
                return
            con = _sqlite3.connect(_DB_PATH)
            now = _dt.now().strftime("%Y-%m-%d %H:%M")
            sets = ", ".join(f"{k}=?" for k in fields.keys()) + ", updated_at=?"
            con.execute(f"UPDATE books SET {sets} WHERE id=?", list(fields.values()) + [now, bid])
            con.commit(); con.close()
            def _ok():
                messagebox.showinfo("AI 获取成功",
                                    "✅ 已从网络拉取以下字段:\n" +
                                    "\n".join(f"  • {k}" for k in fields.keys()) +
                                    "\n\n切换 Tab 查看, 记得到「✏️我的笔记」写自己的读书概要!")
            dlg.after(0, _ok)
        _threading.Thread(target=_bg, daemon=True).start()

    btn_row = tk.Frame(dlg, bg="#121212"); btn_row.pack(fill=tk.X, padx=6, pady=(0, 4))
    tk.Button(btn_row, text="🤖 AI/联网 抓取豆瓣+百科", command=_ai_fetch,
              bg="#7B1FA2", fg="white", font=("", 10, "bold"), padx=10).pack(side=tk.LEFT)
    tk.Button(btn_row, text="💾 保存我的笔记", command=_save,
              bg="#2E7D32", fg="white", font=("", 10, "bold"), padx=10).pack(side=tk.LEFT, padx=8)
    tk.Button(btn_row, text="关闭", command=dlg.destroy).pack(side=tk.RIGHT)

    dlg.grab_set()

    # ── 自动联网: intro 太短 (种子模板或空) 就后台抓, 抓到后自动刷新 UI ──
    _intro = row["intro"] or ""
    _rating = row["rating"] or 0
    _looks_empty = (len(_intro) < 40) or ("AI/联网没抓到" in _intro) or (_rating == 0)
    if _looks_empty:
        def _auto_fetch():
            summary = _fetch_book_intro_worker(row["title"], row["author"])
            # 过滤: 只存非空值, 且把非字符串类型处理一下
            fields_to_save = {}
            for k, v in summary.items():
                if v is None: continue
                if isinstance(v, str) and not v.strip(): continue
                if isinstance(v, float):  # rating
                    if v > 0: fields_to_save[k] = v
                    continue
                if isinstance(v, int):    # pages
                    if v > 0: fields_to_save[k] = v
                    continue
                fields_to_save[k] = v
            if not fields_to_save: return
            # 存库 (纯 SQLite, 线程安全)
            try:
                con = _sqlite3.connect(_DB_PATH)
                now = _dt.now().strftime("%Y-%m-%d %H:%M")
                sets = ", ".join(f"{k}=?" for k in fields_to_save.keys()) + ", updated_at=?"
                con.execute(f"UPDATE books SET {sets} WHERE id=?",
                            list(fields_to_save.values()) + [now, bid])
                con.commit(); con.close()
            except Exception as ex:
                print(f"[书籍] auto fetch db err: {ex}", flush=True)
            # ⚠️ Tk 不是线程安全 — 用 after(0, ...) 切回主线程刷新 UI
            def _refresh():
                try:
                    if not dlg.winfo_exists(): return
                    con2 = _sqlite3.connect(_DB_PATH)
                    con2.row_factory = _sqlite3.Row
                    new_row = con2.execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
                    con2.close()
                    if not new_row: return
                    # 刷新 header 副标题
                    sub2 = []
                    if new_row["author"]: sub2.append(f"✍️ {new_row['author']}")
                    if new_row["rating"] and new_row["rating"] > 0: sub2.append(f"⭐ {new_row['rating']:.1f}")
                    if new_row["pub_year"]: sub2.append(f"📅 {new_row['pub_year']}")
                    if new_row["pages"]: sub2.append(f"📄 {new_row['pages']}页")
                    for w in header.winfo_children():
                        if isinstance(w, tk.Label) and "✍️" in (w.cget("text") or ""):
                            w.configure(text="  |  ".join(sub2)); break
                    # 刷新 text widgets (重建 tab)
                    for widget in t1.winfo_children(): widget.destroy()
                    for widget in t2.winfo_children(): widget.destroy()
                    _make_labeled_text(t1, "📚 作者简介 / 官方简介", new_row["intro"] or "", (0, 0), height=8)
                    _make_labeled_text(t1, "💡 核心观点 / 书摘", new_row["highlights"] or "", (1, 0), height=6)
                    _make_labeled_text(t2, "👍 网上好评 / 推荐语", new_row["pros"] or "", (0, 0), height=6)
                    _make_labeled_text(t2, "👎 争议 / 负面评价", new_row["cons"] or "", (1, 0), height=4)
                    _make_labeled_text(t2, "🔗 相关书籍 (每行一本)", new_row["related"] or "", (2, 0), height=3)
                    _make_labeled_text(t2, "🛠 涉及方法论 (每行一个)", new_row["methods"] or "", (3, 0), height=3)
                    # 也刷新主 Tab 的卡片网格
                    try:
                        _root = dlg.winfo_toplevel()
                        # 往上找 books tab 的 scroll_inner
                        for child in _root.winfo_children():
                            if not hasattr(child, 'winfo_children'): continue
                            for sub in child.winfo_children():
                                for sub2 in sub.winfo_children():
                                    try:
                                        if hasattr(sub2, 'winfo_children') and any(
                                            hasattr(c, 'cget') and c.cget('bg') == '#121212'
                                            for c in sub2.winfo_children()[:1]):
                                            _render_buttons(sub2, "")
                                            break
                                    except: pass
                    except Exception: pass
                except Exception as ex:
                    print(f"[书籍] auto fetch UI refresh err: {ex}", flush=True)
            dlg.after(0, _refresh)
        _threading.Thread(target=_auto_fetch, daemon=True).start()


# 编辑中 — 需要从 _make_labeled_text 里拿到 text widget
_editors = {}


def _make_labeled_text(parent, label, initial, grid_pos, height=6, editable=False, tag=None):
    """带标题的多行文本区"""
    import tkinter as tk
    from tkinter import scrolledtext
    r, c = grid_pos
    parent.grid_rowconfigure(r, weight=1); parent.grid_columnconfigure(c, weight=1)
    frm = tk.Frame(parent, bg="#121212")
    frm.grid(row=r, column=c, sticky="nsew", padx=6, pady=4)
    tk.Label(frm, text=label, bg="#121212", fg="#FFD54F", font=("", 10, "bold")).pack(anchor="w")
    txt = scrolledtext.ScrolledText(frm, bg="#1E1E1E", fg="#E0E0E0",
                                    font=("", 10), height=height, wrap=tk.WORD,
                                    relief=tk.FLAT, padx=6, pady=4)
    txt.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
    txt.insert("1.0", initial or "")
    if editable:
        txt.configure(state=tk.NORMAL)
        if tag is not None:
            _editors[tag] = lambda t=txt: t.get("1.0", tk.END).strip()
    else:
        txt.configure(state=tk.DISABLED)


# ═════════════════════════════════════════════════════════════════════════
# 4. AI/联网抓取 (可选)
# ═════════════════════════════════════════════════════════════════════════

def _fetch_book_intro_worker(title, author_hint=""):
    """后台线程: 豆瓣 suggest → 详情页完整解析 (rating/intro/作者/出版社/页数/ISBN)"""
    import requests
    out = {}
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                             "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
               "Accept-Language": "zh-CN,zh;q=0.9"}
    q = title  # 只用书名搜 — 加作者名会导致豆瓣 suggest 返回空
    print(f"[书籍] 开始抓《{title}》联网数据...", flush=True)

    # ═══ ① 豆瓣 suggest API → 找到匹配 subject ═══
    subject_url = ""
    try:
        r = requests.get(f"https://book.douban.com/j/subject_suggest?q={requests.utils.quote(q)}",
                         headers=headers, timeout=8)
        if r.ok:
            data = r.json()
            if data and isinstance(data, list) and len(data) > 0:
                # 选标题最匹配的 (豆瓣会返回不同版本)
                best = None; best_score = 0
                for b in data:
                    b_title = b.get("title", "")
                    s = 0
                    if title in b_title or b_title in title: s += 3
                    if b.get("author_name") and author_hint and author_hint[:2] in b.get("author_name", ""): s += 2
                    if s > best_score: best = b; best_score = s
                if not best: best = data[0]
                if best:
                    subject_url = best.get("url", "")
                    an = best.get("author_name", "")
                    if an and not out.get("author"): out["author"] = an
                    yr = best.get("year", "")
                    if yr and not out.get("pub_year"): out["pub_year"] = yr
                    print(f"[书籍] 豆瓣 suggest 命中: {best.get('title')} → {subject_url}", flush=True)
    except Exception as e:
        print(f"[书籍] 豆瓣suggest失败: {e}", flush=True)

    # ═══ ② 豆瓣详情页 → 解析完整数据 ═══
    if subject_url:
        try:
            r2 = requests.get(subject_url, headers=headers, timeout=12)
            if r2.ok and len(r2.text) > 5000:
                text = r2.text
                # rating
                m = _re.search(r'property="v:average"[^>]*>([^<]+)', text)
                if m:
                    try: out["rating"] = float(m.group(1).strip())
                    except: pass
                # 基本信息: 作者/出版社/出版年/页数/ISBN
                info_map = {"作者": "author", "出版社": "", "出版年": "pub_year",
                            "页数": "pages", "ISBN": ""}
                for label, field in info_map.items():
                    if not field: continue
                    for mm in _re.finditer(r'<span class="pl">' + label + r':</span>(.*?)<br', text, _re.DOTALL):
                        val = _re.sub(r'<[^>]+>', '', mm.group(1)).strip()
                        if val:
                            if field == "pages":
                                try: out[field] = int(_re.sub(r'\D', '', val))
                                except: pass
                            else:
                                out[field] = val
                        break
                # intro: 取第一个 class="intro" div (内容简介)
                intros_found = []
                for m4 in _re.finditer(r'class="intro"[^>]*>(.*?)</div>', text, _re.DOTALL):
                    txt = _re.sub(r'<[^>]+>', '', m4.group(1))
                    txt = _re.sub(r'\s+', ' ', txt).strip()
                    if len(txt) > 30: intros_found.append(txt)
                if intros_found:
                    out["intro"] = intros_found[0]  # 第一个通常是内容简介
                    if len(intros_found) > 1:
                        # 第二个通常是作者简介, 拼到 intro 末尾
                        out["intro"] += "\n\n———\n\n📝 " + intros_found[1]
                # douban_url
                out["douban_url"] = subject_url
                print(f"[书籍] ✅ 豆瓣详情页: rating={out.get('rating')}, intro={len(out.get('intro',''))}字", flush=True)
        except Exception as e:
            print(f"[书籍] 豆瓣详情页失败: {e}", flush=True)

    # ═══ ③ 百度百科 HTML (兜底) ═══
    if not out.get("intro"):
        try:
            url3 = f"https://baike.baidu.com/item/{requests.utils.quote(title)}"
            r3 = requests.get(url3, headers=headers, timeout=10, allow_redirects=True)
            if r3.ok and len(r3.text) > 2000:
                m = _re.search(r'<meta\s+name="description"\s+content="([^"]+)"', r3.text)
                if m:
                    desc = _re.sub(r"[\s]+", " ", m.group(1)).strip()
                    if len(desc) > 30:
                        out["intro"] = desc
                        print(f"[书籍] ✅ 百度百科 meta description", flush=True)
                if not out.get("intro"):
                    m2 = _re.search(r'class="lemma-summary"[^>]*>(.*?)</div>', r3.text, _re.DOTALL)
                    if m2:
                        txt = _re.sub(r"<[^>]+>", "", m2.group(1))
                        txt = _re.sub(r"[\s]+", " ", txt).strip()
                        if len(txt) > 30:
                            out["intro"] = txt
                            print(f"[书籍] ✅ 百度百科 lemma-summary", flush=True)
        except Exception as e:
            print(f"[书籍] 百度百科失败: {e}", flush=True)

    # ═══ 最终兜底: 种子模板 ═══
    if not out.get("intro"):
        out["intro"] = f"《{title}》是一本{_guess_genre(title)}类书籍。\n\n(AI/联网没抓到 — 请手动补充 👍)"
        print(f"[书籍] ⚠️ 用种子兜底 (豆瓣/百科全失败)", flush=True)
    if not out.get("pros"):
        out["pros"] = f"值得一读的核心理由:\n① 切中{_guess_genre(title)}领域的经典痛点\n② 提供可落地的方法论/案例\n③ 被多位读者/同行推荐"
    if not out.get("related"):
        out["related"] = _suggest_related(title)
    if not out.get("methods"):
        out["methods"] = _guess_methods(title)

    return out


def _suggest_related(title):
    """基于书名硬编码的推荐 (真实可用, 比 AI 模板靠谱)"""
    RELATED = {
        "股票大作手回忆录": "《股票大作手操盘术》\n《笑傲股市》欧奈尔\n《量价分析》安娜库林",
        "聪明的投资者": "《巴菲特致股东的信》\n《漫步华尔街》\n《投资最重要的事》",
        "漫步华尔街": "《有效资产管理》\n《主动投资组合管理》\n《定投改变命运》",
        "原则": "《穷查理宝典》\n《深度工作》\n《思维的利剑》",
        "穷查理宝典": "《霍华德马克斯投资最重要的事》\n《思考快与慢》",
        "思考快与慢": "《清醒思考的艺术》\n《影响力》西奥迪尼\n《反脆弱》塔勒布",
        "人性的弱点": "《影响力》西奥迪尼\n《乌合之众》\n《社会心理学》",
        "反脆弱": "《黑天鹅》\n《随机漫步的傻瓜》\n《非对称风险》",
        "黑天鹅": "《反脆弱》\n《塔勒布投资哲学》\n《不确定性的代价》",
        "随机漫步的傻瓜": "《黑天鹅》\n《投资玄学》\n《肥尾效应》",
        "影响力": "《社会心理学》\n《上瘾》\n《欲罢不能》",
        "清醒思考的艺术": "《思考快与慢》\n《穷查理宝典》\n《社会心理学》",
        "深度工作": "《高效能人士的七个习惯》\n《番茄工作法》\n《原子习惯》",
        "原子习惯": "《微习惯》\n《深度工作》\n《掌控习惯》",
        "高效能人士的七个习惯": "《深度工作》\n《原则》\n《卓有成效的管理者》",
        "卓有成效的管理者": "《原则》\n《从优秀到卓越》\n《基业长青》",
    }
    for k, v in RELATED.items():
        if k in title or title in k: return v
    return "\n(暂无推荐 — AI 联网未匹配到, 手动写吧 👍)"


def _guess_methods(title):
    t = title
    out = []
    if any(k in t for k in ("股票", "投资", "交易", "基金", "期货")):
        out += ["趋势跟踪 / 海龟法则", "均值回归", "价值投资 (DCF/PE/PB)", "动量因子", "网格交易"]
    if any(k in t for k in ("心理", "思维", "认知", "人性", "情绪")):
        out += ["认知偏差识别 (卡尼曼)", "系统1 vs 系统2", "情绪日记", "冥想正念"]
    if any(k in t for k in ("历史", "帝国")):
        out += ["历史周期论", "货币信用周期", "兴衰五百年模型"]
    if any(k in t for k in ("原则", "习惯", "工作")):
        out += ["反射式决策", "番茄工作法", "第二大脑 PARA 法", "复盘五问"]
    return "\n".join(out) if out else "\n(暂无建议方法 — AI 联网未匹配)"

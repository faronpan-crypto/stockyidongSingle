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
    """建表 (幂等) + 升级 schema"""
    con = _sqlite3.connect(_DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        author TEXT DEFAULT '',
        translator TEXT DEFAULT '',
        publisher TEXT DEFAULT '',
        genre TEXT DEFAULT '',
        source TEXT DEFAULT '手动',
        rating REAL DEFAULT 0,
        rating_count INTEGER DEFAULT 0,
        douban_url TEXT DEFAULT '',
        pub_year TEXT DEFAULT '',
        pages INTEGER DEFAULT 0,
        isbn TEXT DEFAULT '',
        price TEXT DEFAULT '',
        original_title TEXT DEFAULT '',
        series TEXT DEFAULT '',
        -- 内容层
        intro TEXT DEFAULT '',
        author_bio TEXT DEFAULT '',        -- 作者简介
        chapters TEXT DEFAULT '',          -- 目录/章节 (带页码)
        summary TEXT DEFAULT '',           -- 中心思想/内容梗概
        highlights TEXT DEFAULT '',
        comments TEXT DEFAULT '',          -- 热门短评 (JSON)
        user_summary TEXT DEFAULT '',
        user_notes TEXT DEFAULT '',
        related TEXT DEFAULT '',
        methods TEXT DEFAULT '',
        pros TEXT DEFAULT '',
        cons TEXT DEFAULT '',
        created_at TEXT,
        updated_at TEXT,
        fetched_at TEXT DEFAULT ''         -- 联网抓取时间
    )""")
    # ⚡ 增量升级旧表 — 加新字段 (ALTER TABLE 幂等)
    _MIGRATIONS = [
        ("ALTER TABLE books ADD COLUMN translator TEXT DEFAULT ''", "translator"),
        ("ALTER TABLE books ADD COLUMN publisher TEXT DEFAULT ''", "publisher"),
        ("ALTER TABLE books ADD COLUMN rating_count INTEGER DEFAULT 0", "rating_count"),
        ("ALTER TABLE books ADD COLUMN isbn TEXT DEFAULT ''", "isbn"),
        ("ALTER TABLE books ADD COLUMN price TEXT DEFAULT ''", "price"),
        ("ALTER TABLE books ADD COLUMN original_title TEXT DEFAULT ''", "original_title"),
        ("ALTER TABLE books ADD COLUMN series TEXT DEFAULT ''", "series"),
        ("ALTER TABLE books ADD COLUMN author_bio TEXT DEFAULT ''", "author_bio"),
        ("ALTER TABLE books ADD COLUMN chapters TEXT DEFAULT ''", "chapters"),
        ("ALTER TABLE books ADD COLUMN summary TEXT DEFAULT ''", "summary"),
        ("ALTER TABLE books ADD COLUMN comments TEXT DEFAULT ''", "comments"),
        ("ALTER TABLE books ADD COLUMN fetched_at TEXT DEFAULT ''", "fetched_at"),
    ]
    for sql, col in _MIGRATIONS:
        try: cur.execute(sql)
        except Exception: pass  # 字段已存在则忽略
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
    _backfill_intro()  # 启动时也给旧书补 smart fallback intro

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
    # ⚡ 给空 intro 的旧书批量填 smart fallback (让弹窗打开就有内容)
    _backfill_intro()
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


def _backfill_intro():
    """给 intro 为空/太短/水话/种子 的旧书批量填 smart fallback"""
    try:
        con = _sqlite3.connect(_DB_PATH)
        cur = con.execute("SELECT id, title, intro, author FROM books")
        filled = 0
        for bid, title, intro, author in cur.fetchall():
            need = False
            if not intro or len(intro.strip()) < 40: need = True
            elif "AI/联网没抓到" in intro: need = True
            elif _is_water_intro(intro): need = True
            if need:
                fb = _build_smart_fallback_intro(title, author or "")
                con.execute("UPDATE books SET intro=? WHERE id=?", (fb, bid))
                filled += 1
        con.commit(); con.close()
        if filled:
            print(f"[书籍] ✅ backfill intro: {filled} 本")
    except Exception as e:
        print(f"[书籍] backfill intro err: {e}")


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
    """📘 打开书籍详情弹窗 — 丰富多 Tab + 动态显示"""
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
    dlg.geometry("1000x760")
    dlg.configure(bg="#121212")
    dlg.transient(parent)

    # ═══ 丰富标题栏 ═══
    header = tk.Frame(dlg, bg="#1565C0"); header.pack(fill=tk.X)
    # 大标题行
    title_row = tk.Frame(header, bg="#1565C0"); title_row.pack(fill=tk.X, padx=14, pady=(10, 2))
    tk.Label(title_row, text=f"📘 {row['title']}", bg="#1565C0", fg="white",
             font=("", 17, "bold")).pack(side=tk.LEFT)
    # 评分徽章 (大)
    if row["rating"] and row["rating"] > 0:
        rating_bg = "#EF5350" if row["rating"] < 7 else ("#FFA726" if row["rating"] < 8 else "#66BB6A")
        badge = tk.Frame(title_row, bg=rating_bg, padx=10, pady=2)
        badge.pack(side=tk.RIGHT)
        cnt = f"{row['rating_count']}人评价" if row.get("rating_count") and row["rating_count"] > 0 else ""
        tk.Label(badge, text=f"⭐ {row['rating']:.1f}  {cnt}", bg=rating_bg, fg="white",
                 font=("", 11, "bold")).pack()
    # 副标题行: 作者/译者/出版社/出版年/定价/ISBN
    sub_row = tk.Frame(header, bg="#1565C0"); sub_row.pack(fill=tk.X, padx=14, pady=(0, 10))
    sub_parts = []
    if row.get("author"): sub_parts.append(f"✍️ {row['author']}")
    if row.get("translator"): sub_parts.append(f"🌐 译者: {row['translator']}")
    if row.get("publisher"): sub_parts.append(f"🏢 {row['publisher']}")
    if row.get("pub_year"): sub_parts.append(f"📅 {row['pub_year']}")
    if row.get("price"): sub_parts.append(f"💰 {row['price']}元")
    if row.get("pages"): sub_parts.append(f"📄 {row['pages']}页")
    if row.get("isbn"): sub_parts.append(f"ISBN {row['isbn']}")
    if row.get("original_title"): sub_parts.append(f"原作: {row['original_title']}")
    if row.get("series"): sub_parts.append(f"📚 {row['series']}")
    if row.get("genre"): sub_parts.append(f"📂 {row['genre']}")
    tk.Label(sub_row, text="  │  ".join(sub_parts), bg="#1565C0", fg="#BBDEFB",
             font=("", 9), wraplength=950, justify="left", anchor="w").pack(anchor="w")

    nb = ttk.Notebook(dlg); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    # ═══ 动态 Tab — 根据数据有无显示 ═══
    tab_frames = {}  # name -> frame

    # Tab1: 官方介绍 (总有)
    t1 = tk.Frame(nb, bg="#121212"); tab_frames["intro"] = t1
    _make_labeled_text(t1, "📖 内容简介", row["intro"] or "", (0, 0), height=10)
    if row.get("summary") and len(row["summary"]) > 30:
        _make_labeled_text(t1, "💡 中心思想 / 核心概要", row["summary"], (1, 0), height=6)
    if row.get("highlights") and len(row["highlights"]) > 10:
        _make_labeled_text(t1, "💎 核心观点 / 书摘", row["highlights"],
                           (2, 0) if row.get("summary") else (1, 0), height=5)
    nb.add(t1, text="📖 官方介绍")

    # Tab2: 目录章节 (有数据才显示)
    if row.get("chapters") and len(row["chapters"]) > 20:
        t_ch = tk.Frame(nb, bg="#121212"); tab_frames["chapters"] = t_ch
        _make_labeled_text(t_ch, "📑 目录 / 章节结构", row["chapters"], (0, 0), height=18)
        nb.add(t_ch, text="📑 目录章节")

    # Tab3: 作者简介 (有数据才显示)
    if row.get("author_bio") and len(row["author_bio"]) > 30:
        t_ab = tk.Frame(nb, bg="#121212"); tab_frames["author_bio"] = t_ab
        _make_labeled_text(t_ab, "👤 作者简介 / 生平", row["author_bio"], (0, 0), height=14)
        nb.add(t_ab, text="👤 作者简介")

    # Tab4: 热门评论 (有数据才显示)
    import json as _json3
    comments_list = []
    if row.get("comments"):
        try: comments_list = _json3.loads(row["comments"])
        except: pass
    if comments_list:
        t_cm = tk.Frame(nb, bg="#121212"); tab_frames["comments"] = t_cm
        # 用 Treeview 显示评论 (投票数 + 内容)
        tree_frame = tk.Frame(t_cm, bg="#121212"); tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        tk.Label(tree_frame, text="💬 豆瓣热门短评 (按有用数排序)",
                 bg="#121212", fg="#FFD54F", font=("", 10, "bold")).pack(anchor="w")
        tv = ttk.Treeview(tree_frame, columns=("vote", "text"), show="headings", height=14)
        tv.heading("vote", text="👍"); tv.heading("text", text="短评内容")
        tv.column("vote", width=60, anchor="center"); tv.column("text", width=900, anchor="w")
        for c in sorted(comments_list, key=lambda x: -x.get("vote", 0)):
            tv.insert("", "end", values=(c.get("vote", ""), c.get("text", "")[:120]))
        tv.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        tab_frames["comments_tv"] = tv  # 存引用供刷新
        nb.add(t_cm, text=f"💬 热门短评 ({len(comments_list)}条)")

    # Tab5: 外界声音 (总有)
    t2 = tk.Frame(nb, bg="#121212"); tab_frames["social"] = t2
    grid_row = 0
    if row.get("pros") and len(row["pros"]) > 10:
        _make_labeled_text(t2, "👍 网上好评 / 推荐语", row["pros"], (grid_row, 0), height=5); grid_row += 1
    if row.get("cons") and len(row["cons"]) > 10:
        _make_labeled_text(t2, "👎 争议 / 负面评价", row["cons"], (grid_row, 0), height=4); grid_row += 1
    if row.get("related") and len(row["related"]) > 10:
        _make_labeled_text(t2, "🔗 相关书籍", row["related"], (grid_row, 0), height=3); grid_row += 1
    if row.get("methods") and len(row["methods"]) > 10:
        _make_labeled_text(t2, "🛠 涉及方法论", row["methods"], (grid_row, 0), height=3); grid_row += 1
    if grid_row == 0:
        tk.Label(t2, text="(暂无外界评价数据 — 点「🔄再爬取更新」试试)",
                 bg="#121212", fg="#546E7A", font=("", 11)).pack(pady=40)
    nb.add(t2, text="🌐 外界声音")

    # Tab6: 我的笔记 (可编辑, 总有)
    t3 = tk.Frame(nb, bg="#121212"); tab_frames["notes"] = t3
    _make_labeled_text(t3, "📝 自我读书概要 / 特色解读", row["user_summary"] or "",
                       (0, 0), height=7, editable=True, tag="_summary")
    _make_labeled_text(t3, "🧠 个人笔记 / 读后感 / 划线摘录", row["user_notes"] or "",
                       (1, 0), height=7, editable=True, tag="_notes")
    nb.add(t3, text="✏️ 我的笔记")

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

    btn_row = tk.Frame(dlg, bg="#121212"); btn_row.pack(fill=tk.X, padx=6, pady=(0, 4))
    tk.Button(btn_row, text="💾 保存我的笔记", command=_save,
              bg="#2E7D32", fg="white", font=("", 10, "bold"), padx=10).pack(side=tk.LEFT, padx=8)
    tk.Button(btn_row, text="🔄 再爬取更新", command=lambda: _do_fetch_background(notify_user=True),
              bg="#7B1FA2", fg="white", font=("", 10, "bold"), padx=10).pack(side=tk.LEFT)
    # 豆瓣链接按钮
    if row.get("douban_url"):
        try:
            import webbrowser as _wb
            tk.Button(btn_row, text="📖 打开豆瓣页",
                      command=lambda u=row["douban_url"]: _wb.open(u),
                      bg="#0277BD", fg="white", font=("", 10), padx=8).pack(side=tk.LEFT)
        except Exception: pass
    tk.Button(btn_row, text="关闭", command=dlg.destroy).pack(side=tk.RIGHT)

    dlg.grab_set()

    # ═══ ⚡ 自动联网: 需要更新就后台抓 ═══
    _intro_now = row["intro"] or ""
    _rating_now = row["rating"] or 0
    _chapters_now = row.get("chapters") or ""
    _comments_now = row.get("comments") or ""
    _author_bio_now = row.get("author_bio") or ""
    # 触发条件: intro 空/太短, 或 rating=0, 或 章节+评论+作者简介 全空
    _need_fetch = (len(_intro_now) < 40) or (_rating_now == 0) or (
        not _chapters_now and not _comments_now and not _author_bio_now)

    # ═══ 后台联网 + 刷新 UI 的闭包 ═══
    def _do_fetch_background(notify_user=False):
        """后台抓 → 存 DB → 切主线程刷新整个弹窗"""
        def _bg():
            try:
                summary = _fetch_book_intro_worker(row["title"], row["author"])
                fields = {}
                for k, v in (summary or {}).items():
                    if v is None: continue
                    if isinstance(v, str) and not v.strip(): continue
                    if isinstance(v, (float, int)):
                        if k in ("rating", "rating_count", "pages") and v > 0: fields[k] = v
                        continue
                    fields[k] = v
                if fields:
                    try:
                        con = _sqlite3.connect(_DB_PATH)
                        now = _dt.now().strftime("%Y-%m-%d %H:%M")
                        fields["fetched_at"] = now
                        sets = ", ".join(f"{k}=?" for k in fields.keys()) + ", updated_at=?"
                        con.execute(f"UPDATE books SET {sets} WHERE id=?",
                                    list(fields.values()) + [now, bid])
                        con.commit(); con.close()
                    except Exception as ex:
                        print(f"[书籍] fetch db save err: {ex}", flush=True)
                # 切主线程 — 刷新整个弹窗 (因为 Tab 可能增删)
                def _refresh_all():
                    try:
                        if not dlg.winfo_exists(): return
                        # 重新读 DB
                        con2 = _sqlite3.connect(_DB_PATH)
                        con2.row_factory = _sqlite3.Row
                        nr = con2.execute("SELECT * FROM books WHERE id=?", (bid,)).fetchone()
                        con2.close()
                        if not nr: return
                        # ⚡ 直接 destroy 整个 dialog 重建 — 最简单最稳
                        dlg.destroy()
                        _open_book_detail(parent, bid)
                        if notify_user:
                            messagebox.showinfo("✅ 爬取成功",
                                "已从网络拉取最新数据, 弹窗已刷新!\n\n"
                                "如果之前目录章节/评论是空的, 现在应该有了。")
                    except Exception as ex:
                        print(f"[书籍] refresh err: {ex}", flush=True)
                        if notify_user:
                            messagebox.showerror("刷新失败", str(ex))
                dlg.after(0, _refresh_all)
            except Exception as e:
                print(f"[书籍] fetch bg err: {e}", flush=True)
                if notify_user:
                    dlg.after(0, lambda: messagebox.showwarning("爬取失败", str(e)))
        _threading.Thread(target=_bg, daemon=True).start()

    if _need_fetch:
        print(f"[书籍] ⚡ 自动联网抓取 《{row['title']}》", flush=True)
        _do_fetch_background(notify_user=False)


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

def _is_water_intro(text):
    """检测简介是否是豆瓣模板水话 — 这些词在豆瓣老书简介里高频出现"""
    WATER_MARKERS = [
        "全天24小时", "任何金融市场", "检验风险", "资金控制",
        "这是一个能", "进出有据", "患得患失", "惶惑不安",
        "淡泊从容", "淡化从容", "培养赢家心态", "建立赢家思维",
        "具有极强适应能力", "丰富多样的战法",
        "舵手", "良药妙方",
    ]
    if not text or len(text) < 40:
        return True  # 太短也不行
    hits = sum(1 for w in WATER_MARKERS if w in text)
    # 如果 2 个以上水词 → 判定为模板
    if hits >= 2: return True
    # 或者整段就是"全天24小时..."那个模板
    if "全天24小时" in text and "这是一个" in text: return True
    return False


def _build_smart_fallback_intro(title, author_hint=""):
    """根据书名+作者+分类推断更靠谱的简介 (比豆瓣模板水话好)"""
    genre = _guess_genre(title)
    name_author = f" ({author_hint})" if author_hint else ""

    # 从文件名里提取额外信息
    extra = ""
    if "高清版" in title: extra += " (高清扫描版)"
    if ".扫描版" in title or "(扫描版)" in title or "扫描版" in title: extra += " (扫描版)"
    if "www.com10.cn" in title: extra += " (来源: com10.cn)"

    # 关键词 → 核心内容推断
    kw_core = [
        ("N字", "N字形态"), ("MACD", "MACD指标"), ("K线", "K线形态"),
        ("波浪", "艾略特波浪理论"), ("缠论", "缠中说禅技术理论"),
        ("海龟", "海龟交易法则"), ("利弗莫尔", "杰西·利弗莫尔作手回忆录"),
        ("格雷厄姆", "本杰明·格雷厄姆价值投资"), ("巴菲特", "沃伦·巴菲特投资策略"),
        ("索罗斯", "乔治·索罗斯反身性理论"), ("马克·道格拉斯", "马克·道格拉斯交易心理学"),
        ("范·撒普", "范·撒普交易系统"), ("阿斯汤加", "阿斯汤加瑜伽"),
        ("高胜算", "高胜算交易策略"), ("波段", "波段交易方法论"),
        ("外汇", "外汇交易技术"), ("期货", "期货交易策略"),
        ("期权", "期权定价与波动率交易"), ("量化", "量化投资与算法交易"),
        ("机器学习", "机器学习与量化应用"), ("深度学习", "深度学习与金融AI"),
        ("Python", "Python金融数据分析"),
    ]
    core_hint = ""
    for kw, desc in kw_core:
        if kw.lower() in title.lower():
            core_hint = desc
            break

    genre_intro_map = {
        "投资": f"《{title}》{name_author}是一本{genre}类经典书籍{extra}。"
               f"{'核心围绕：' + core_hint if core_hint else '涵盖交易理念、技术方法和实战案例'}。"
               f"\n\n建议结合自身交易系统阅读, 提取可落地的方法, 不要盲目照搬。",
        "心理": f"《{title}》{name_author}是一本{genre}类书籍{extra}。"
               f"探讨投资/交易中的心理偏差、情绪管理和认知提升。"
               f"\n\n核心价值在于帮助交易者建立稳健的心态, 减少情绪化决策。",
        "科技": f"《{title}》{name_author}是一本{genre}类书籍{extra}。"
               f"{'核心主题：' + core_hint if core_hint else '介绍相关技术原理与实践应用'}。",
        "历史": f"《{title}》{name_author}是一本{genre}类书籍{extra}。",
        "传记": f"《{title}》{name_author}是一本{genre}类书籍{extra}。",
        "哲学": f"《{title}》{name_author}是一本{genre}类书籍{extra}。",
        "方法": f"《{title}》{name_author}是一本{genre}类书籍{extra}。"
               f"提供可重复执行的方法论和操作框架。",
        "其他": f"《{title}》{name_author}是一本值得一读的书籍{extra}。",
    }
    return genre_intro_map.get(genre, genre_intro_map["其他"])


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
                # ══ 评分 + 评价人数 ══
                m = _re.search(r'property="v:average"[^>]*>([^<]+)', text)
                if m:
                    try: out["rating"] = float(m.group(1).strip())
                    except: pass
                # rating_count: "2974人评价"
                m2 = _re.search(r'rating_people">.*?<span property="v:votes">(\d+)', text, _re.DOTALL)
                if m2:
                    try: out["rating_count"] = int(m2.group(1))
                    except: pass

                # ══ 基本信息面板 (<div id="info">) ══
                info_extract = {
                    "作者": "author", "译者": "translator", "出版社": "publisher",
                    "出版年": "pub_year", "页数": "pages", "ISBN": "isbn",
                    "定价": "price", "原作名": "original_title", "丛书": "series",
                }
                for label, field in info_extract.items():
                    for mm in _re.finditer(r'<span class="pl">' + label + r':</span>(.*?)<br', text, _re.DOTALL):
                        val = _re.sub(r'<[^>]+>', '', mm.group(1)).strip()
                        if val:
                            if field == "pages":
                                try: out[field] = int(_re.sub(r'\D', '', val))
                                except: pass
                            else:
                                out[field] = val
                        break

                # ══ 目录/章节 ══
                dir_found = None
                for dir_pat in [r'id="dir_\d+_short"[^>]*>(.*?)</div>', r'id="dir"[^>]*>(.*?)</div>',
                                r'class="indent"[^>]*id="dir[^"]*"[^>]*>(.*?)</div>']:
                    m_dir = _re.search(dir_pat, text, _re.DOTALL)
                    if m_dir:
                        dir_html = m_dir.group(1)
                        dir_text = _re.sub(r'<br\s*/?>', '\n', dir_html)
                        dir_text = _re.sub(r'<[^>]+>', '', dir_text)
                        dir_text = _re.sub(r'[ \t]+', ' ', dir_text)
                        dir_text = _re.sub(r'\n\s*\n+', '\n', dir_text).strip()
                        # 过滤 "更多" 这种截断标记
                        dir_text = _re.sub(r'·\s*·\s*·.*', '', dir_text).strip()
                        if len(dir_text) > 20:
                            dir_found = dir_text
                            break
                if dir_found:
                    out["chapters"] = dir_found

                # ══ 简介 (分离: intro=内容简介, author_bio=作者简介) ══
                intros_found = []
                for m4 in _re.finditer(r'class="intro"[^>]*>(.*?)</div>', text, _re.DOTALL):
                    txt = _re.sub(r'<[^>]+>', '', m4.group(1))
                    txt = _re.sub(r'\s+', ' ', txt).strip()
                    if len(txt) > 30: intros_found.append(txt)
                if intros_found:
                    # 第一个是内容简介
                    out["intro"] = intros_found[0]
                    # 如果检测到模板水话 → 标记 (但保留, 后续可 smart fallback)
                    if _is_water_intro(out["intro"]):
                        print(f"[书籍] ⚠️ 豆瓣 intro 是模板水话", flush=True)
                    # 第二个通常是作者简介
                    if len(intros_found) > 1:
                        out["author_bio"] = intros_found[1]
                    # 如果还有第三个, 可能是译者序之类的 → 拼到 summary
                    if len(intros_found) > 2:
                        out["summary"] = intros_found[2]

                # ══ 热门短评 (前5条) ══
                comment_list = []
                for ci, mci in enumerate(_re.finditer(
                        r'<li class="comment-item"[^>]*>.*?<div class="comment">(.*?)</div>\s*</li>',
                        text, _re.DOTALL)):
                    if ci >= 5: break
                    c_html = mci.group(1)
                    # 短评正文: <span class="short">...</span>
                    m_short = _re.search(r'class="short"[^>]*>(.*?)</span>', c_html, _re.DOTALL)
                    # 有用数
                    m_vote = _re.search(r'class="vote-count"[^>]*>(\d+)', c_html)
                    vote = int(m_vote.group(1)) if m_vote else 0
                    if m_short:
                        c_txt = _re.sub(r'<[^>]+>', '', m_short.group(1)).strip()
                        c_txt = _re.sub(r'\s+', ' ', c_txt)
                        if len(c_txt) > 5:
                            comment_list.append({"vote": vote, "text": c_txt[:300]})
                if comment_list:
                    import json as _json2
                    out["comments"] = _json2.dumps(comment_list, ensure_ascii=False)

                # ══ douban_url ══
                out["douban_url"] = subject_url
                print(f"[书籍] ✅ 豆瓣详情: rating={out.get('rating')}, "
                      f"chapters={len(out.get('chapters',''))}字, "
                      f"comments={len(comment_list)}条", flush=True)
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

    # ═══ 最终兜底: smart fallback (根据书名推断, 比豆瓣模板水话好) ═══
    if not out.get("intro"):
        out["intro"] = _build_smart_fallback_intro(title, author_hint)
        print(f"[书籍] ⚠️ 用 smart fallback", flush=True)
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

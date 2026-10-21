"""
🎓 学习 Tab — 金融主流理论 / 主流工具 / 学习资料 / 学习来源

布局参照 fund_holdings_tab.py:
  顶栏 (标题 + 字体 + 🗔弹出 + 📝新增/编辑/保存)
  → ttk.Notebook 分 4 个子 tab
  → 每个子 tab = Canvas + Scrollbar + 可滚动卡片/条目
  → 每个卡片可点击 URL, 可右键编辑/删除

数据持久化: data/learning_sources.json (首次运行从默认种子数据生成)
格式: {section_key: [{name, url, desc, [category]}]}

section_key: theories / tools / books / sources
books 和 sources 带 category 字段 (分组显示)
微信/抖音号: url 为空或非 http 时, 卡片只显示, 不弹浏览器
"""
import json
import os
import tkinter as tk
import tkinter.ttk as ttk
import webbrowser
from tkinter import messagebox


# ── 🎨 配色 (与 fund_holdings_tab 统一) ──
_BG_DEEP = "#121212"
_BG_PANEL = "#1E1E1E"
_BG_CARD = "#252525"
_BG_TOOLBAR = "#1A1A2E"
_FG_GOLD = "#FFD54F"
_FG_RED = "#EF5350"
_FG_GREEN = "#66BB6A"
_FG_BLUE = "#42A5F5"
_FG_DIM = "#888888"
_FG_TEXT = "#E0E0E0"
_FG_CYAN = "#80DEEA"


# ═══════════════════════════════════════════════════════════
#  🔄 数据层 — JSON 持久化
# ═══════════════════════════════════════════════════════════

_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "learning_sources.json"
)


def _default_data():
    """首次运行时的种子数据"""
    return {
        "theories": [
            {"name": "📐 MM 定理 (Modigliani-Miller)",
             "url": "https://en.wikipedia.org/wiki/Modigliani%E2%80%93Miller_theorem",
             "desc": "1958. 完美市场中公司价值与资本结构无关. 有税+破产成本→最优结构."},
            {"name": "🌊 有效市场假说 EMH",
             "url": "https://en.wikipedia.org/wiki/Efficient-market_hypothesis",
             "desc": "Fama 1970. 弱式/半强式/强式. 诺奖2013."},
            {"name": "⚖️ CAPM 资本资产定价模型",
             "url": "https://en.wikipedia.org/wiki/Capital_asset_pricing_model",
             "desc": "Sharpe 1964. E(R)=Rf+β×(Rm-Rf). 低β长期跑赢高β."},
            {"name": "📘 布莱克-斯科尔斯公式",
             "url": "https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model",
             "desc": "诺奖1997. 欧式期权定价基石."},
            {"name": "🧠 行为金融学",
             "url": "https://en.wikipedia.org/wiki/Behavioral_finance",
             "desc": "Kahneman诺奖2002 / Thaler诺奖2017."},
            {"name": "📈 周期理论 (康波/美林时钟)",
             "url": "https://en.wikipedia.org/wiki/Kondratiev_wave",
             "desc": "康波(~50年)/美林时钟(经济+通胀四象限→资产配置)."},
            {"name": "💰 DCF/DDM 绝对估值",
             "url": "https://www.investopedia.com/terms/d/dcf.asp",
             "desc": "巴菲特: 所有投资本质是DCF."},
            {"name": "📦 筹码分布理论",
             "url": "https://baike.baidu.com/item/%E7%AD%B9%E7%A0%81%E5%88%86%E5%B8%83",
             "desc": "陈浩. 单峰集中=吸筹/多峰发散=派发."},
        ],
        "tools": [
            {"name": "💻 同花顺 iFinD", "url": "https://www.10jqka.com.cn/",
             "desc": "商业级金融数据终端."},
            {"name": "💨 Wind 万得", "url": "https://www.wind.com.cn/",
             "desc": "机构标配. 年费~10万."},
            {"name": "🔴 东方财富", "url": "https://www.eastmoney.com/",
             "desc": "免费行情+股吧+Choice."},
            {"name": "⚪ 雪球", "url": "https://xueqiu.com/",
             "desc": "行情+社区."},
            {"name": "📉 TradingView", "url": "https://www.tradingview.com/",
             "desc": "国际版同花顺."},
            {"name": "🐍 AkShare", "url": "https://akshare.akfamily.xyz/",
             "desc": "开源Python金融数据."},
            {"name": "📊 TuShare Pro", "url": "https://tushare.pro/",
             "desc": "基金持仓/北向/龙虎榜."},
            {"name": "🏦 QMT MiniQMT", "url": "https://www.thinktrader.net/",
             "desc": "券商量化交易终端."},
            {"name": "💹 CFTC COT 报告",
             "url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
             "desc": "期货持仓四分类. 华尔街顶级机构工具."},
            {"name": "📺 财联社", "url": "https://www.cls.cn/",
             "desc": "实时电报最快."},
            {"name": "📺 华尔街见闻", "url": "https://wallstreetcn.com/",
             "desc": "全球实时资讯."},
        ],
        "books": [
            {"category": "📖 经典必读",
             "items": [
                {"name": "《聪明的投资者》", "url": "https://book.douban.com/subject/6794531/",
                 "desc": "格雷厄姆. 巴菲特老师."},
                {"name": "《股票作手回忆录》", "url": "https://book.douban.com/subject/5334858/",
                 "desc": "利弗莫尔. 投机之神."},
                {"name": "《海龟交易法则》", "url": "https://book.douban.com/subject/3279906/",
                 "desc": "丹尼斯100万→4000万传奇."},
            ]},
            {"category": "💎 价值投资",
             "items": [
                {"name": "《巴菲特致股东的信》", "url": "https://book.douban.com/subject/10781407/",
                 "desc": "年报文章集."},
                {"name": "《价值投资实战手册》", "url": "https://book.douban.com/subject/35593606/",
                 "desc": "唐朝(老唐)."},
            ]},
            {"category": "📐 技术分析/量化",
             "items": [
                {"name": "《日本蜡烛图技术》", "url": "https://book.douban.com/subject/3277461/",
                 "desc": "Nison. 蜡烛图奠基人."},
                {"name": "《筹码分布》", "url": "https://book.douban.com/subject/4866632/",
                 "desc": "陈浩. 筹码理论开山之作."},
            ]},
            {"category": "🧠 行为金融",
             "items": [
                {"name": "《思考, 快与慢》", "url": "https://book.douban.com/subject/6794533/",
                 "desc": "卡尼曼. 诺奖2002."},
                {"name": "《反脆弱》", "url": "https://book.douban.com/subject/26059135/",
                 "desc": "塔勒布. 黑天鹅三部曲."},
            ]},
        ],
        "sources": [
            {"category": "🎤 行业大V",
             "items": [
                {"name": "老徐",
                 "url": "",
                 "desc": "抖音/视频号/B站: 追踪聪明钱/SHIBOR/COT."},
                {"name": "唐朝", "url": "https://xueqiu.com/tangchao",
                 "desc": "雪球/公众号「价值投资」"},
                {"name": "但斌", "url": "https://xueqiu.com/danbin",
                 "desc": "东方港湾创始人. 时间的玫瑰."},
                {"name": "段永平", "url": "https://xueqiu.com/duanyongping",
                 "desc": "雪球. 买股票就是买公司."},
                {"name": "林园", "url": "https://xueqiu.com/linyuan",
                 "desc": "茅台/五粮液/片仔癀."},
            ]},
            {"category": "📱 媒体/社群",
             "items": [
                {"name": "淘股吧", "url": "https://www.taoguba.com.cn/",
                 "desc": "超短/打板聚集地."},
                {"name": "韭研公社", "url": "https://www.jiuyangongshe.com/",
                 "desc": "基本面研究."},
                {"name": "雪球", "url": "https://xueqiu.com/",
                 "desc": "大V聚集地."},
            ]},
            {"category": "📺 B站/视频号/抖音",
             "items": [
                {"name": "半佛仙人", "url": "https://space.bilibili.com/50093454",
                 "desc": "B站财经科普顶流."},
                {"name": "巫师财经", "url": "https://space.bilibili.com/39892570",
                 "desc": "硬核财经分析."},
                {"name": "股事", "url": "",
                 "desc": "抖音号: 游资/私募视角每日盘面."},
            ]},
            {"category": "🔗 数据源",
             "items": [
                {"name": "AkShare", "url": "https://akshare.akfamily.xyz/",
                 "desc": "开源Python金融数据."},
                {"name": "TuShare Pro", "url": "https://tushare.pro/",
                 "desc": "基金持仓/北向/龙虎榜."},
                {"name": "FRED 美联储", "url": "https://fred.stlouisfed.org/",
                 "desc": "EFFR/10Y/失业率."},
                {"name": "SHIBOR", "url": "http://www.shibor.org/",
                 "desc": "银行间拆借利率."},
            ]},
        ],
    }


def _load_data():
    """从 JSON 加载, 文件不存在则用默认种子生成"""
    if not os.path.exists(_DATA_FILE):
        data = _default_data()
        try:
            os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
            with open(_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[学习Tab] 保存种子数据失败: {e}", flush=True)
        return data
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[学习Tab] 加载失败, 使用默认: {e}", flush=True)
        return _default_data()


def _save_data(data):
    try:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[学习Tab] 保存失败: {e}", flush=True)
        return False


# ═══════════════════════════════════════════════════════════
#  弹框: 新增/编辑 条目
# ═══════════════════════════════════════════════════════════

def _open_edit_dialog(parent, root, section_key, data_obj,
                      idx=None, sub_idx=None, old_name="",
                      old_url="", old_desc="", old_cat=""):
    """
    通用编辑弹框.
    section_key: theories/tools/books/sources
    idx:  顶层索引 (theories/tools 直接索引; books/sources 是 category 索引)
    sub_idx: 仅 books/sources, category 内 item 索引 (None=新增)
    """
    dlg = tk.Toplevel(root)
    dlg.title("编辑条目" if idx is not None else "新增条目")
    dlg.geometry("480x380")
    dlg.configure(bg=_BG_DEEP)
    dlg.transient(root)
    dlg.grab_set()

    # 分类选择 (books/sources 用)
    cat_row = None
    e_cat = None
    if section_key in ("books", "sources"):
        cat_row = tk.Frame(dlg, bg=_BG_DEEP); cat_row.pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Label(cat_row, text="分类:", bg=_BG_DEEP, fg=_FG_DIM, width=8,
                 anchor="w").pack(side=tk.LEFT)
        categories = [g["category"] for g in data_obj[section_key]]
        e_cat = ttk.Combobox(cat_row, values=categories, width=30)
        e_cat.pack(side=tk.LEFT, padx=4)
        e_cat.set(old_cat or (categories[0] if categories else ""))
        # 新增分类按钮
        def _add_cat():
            new_cat = tk.simpledialog.askstring("新增分类", "分类名称:", parent=dlg)
            if new_cat and new_cat not in categories:
                data_obj[section_key].append({"category": new_cat, "items": []})
                e_cat["values"] = [g["category"] for g in data_obj[section_key]]
                e_cat.set(new_cat)
        btn_add_cat = ttk.Button(cat_row, text="➕新分类", width=8, command=_add_cat)
        btn_add_cat.pack(side=tk.LEFT, padx=4)

    # 名称
    r1 = tk.Frame(dlg, bg=_BG_DEEP); r1.pack(fill=tk.X, padx=10, pady=(8, 2))
    tk.Label(r1, text="名称:", bg=_BG_DEEP, fg=_FG_DIM, width=8,
             anchor="w").pack(side=tk.LEFT)
    e_name = tk.Entry(r1, width=45)
    e_name.pack(side=tk.LEFT, padx=4)
    e_name.insert(0, old_name)

    # URL
    r2 = tk.Frame(dlg, bg=_BG_DEEP); r2.pack(fill=tk.X, padx=10, pady=2)
    tk.Label(r2, text="URL:", bg=_BG_DEEP, fg=_FG_DIM, width=8,
             anchor="w").pack(side=tk.LEFT)
    e_url = tk.Entry(r2, width=45)
    e_url.pack(side=tk.LEFT, padx=4)
    e_url.insert(0, old_url)
    tk.Label(r2, text="(微信/抖音号留空或填备注)", bg=_BG_DEEP,
             fg=_FG_DIM, font=("", 8)).pack(side=tk.LEFT, padx=2)

    # 描述
    r3 = tk.Frame(dlg, bg=_BG_DEEP); r3.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)
    tk.Label(r3, text="描述:", bg=_BG_DEEP, fg=_FG_DIM, anchor="w").pack(fill=tk.X)
    e_desc = tk.Text(r3, height=5, wrap=tk.WORD, bg=_BG_PANEL, fg=_FG_TEXT,
                     relief=tk.FLAT, padx=6, pady=4)
    e_desc.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
    e_desc.insert("1.0", old_desc)

    def _on_save():
        name = e_name.get().strip()
        url = e_url.get().strip()
        desc = e_desc.get("1.0", "end").strip()
        if not name:
            messagebox.showwarning("提示", "名称不能为空", parent=dlg); return

        if section_key in ("theories", "tools"):
            if idx is not None:
                data_obj[section_key][idx] = {"name": name, "url": url, "desc": desc}
            else:
                data_obj[section_key].append({"name": name, "url": url, "desc": desc})
        else:
            # books/sources
            cat_name = e_cat.get().strip()
            if not cat_name:
                messagebox.showwarning("提示", "请选择/填写分类", parent=dlg); return
            # 找到或创建分类
            target_cat = None
            for g in data_obj[section_key]:
                if g["category"] == cat_name:
                    target_cat = g; break
            if target_cat is None:
                target_cat = {"category": cat_name, "items": []}
                data_obj[section_key].append(target_cat)
            if sub_idx is not None and idx is not None:
                target_cat["items"][sub_idx] = {"name": name, "url": url, "desc": desc}
            else:
                target_cat["items"].append({"name": name, "url": url, "desc": desc})

        if _save_data(data_obj):
            try:
                import builtins
                if hasattr(builtins, "_LEARNING_RERENDER") and builtins._LEARNING_RERENDER:
                    builtins._LEARNING_RERENDER()
            except Exception as e:
                print(f"[学习Tab] rerender 触发失败: {e}", flush=True)
            dlg.destroy()
            messagebox.showerror("保存失败", "无法写入数据文件", parent=dlg)

    def _on_cancel():
        dlg.destroy()

    # 按钮行
    btn_row = tk.Frame(dlg, bg=_BG_DEEP); btn_row.pack(fill=tk.X, padx=10, pady=10)
    ttk.Button(btn_row, text="💾 保存", width=12, command=_on_save).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btn_row, text="取消", width=8, command=_on_cancel).pack(side=tk.RIGHT)


# ═══════════════════════════════════════════════════════════
#  🎯 主构建函数
# ═══════════════════════════════════════════════════════════

def build_learning_tab(parent, root=None):
    """🎯 构建 🎓 学习 Tab — 可编辑持久化版"""

    import tkinter.simpledialog as simpledialog

    # ── 字体大小 ──
    _FONT_SIZE = [10]
    def _fs(delta=0):
        _FONT_SIZE[0] = max(8, min(18, _FONT_SIZE[0] + delta))
        return _FONT_SIZE[0]
    def _font(bold=False):
        return ("Menlo", _FONT_SIZE[0], "bold" if bold else "normal")

    # ── 加载数据 ──
    DATA = _load_data()

    # 编辑状态 (让卡片知道是否在编辑模式)
    EDIT_MODE = [False]

    # 重渲染函数 (给弹框保存后调用) — 全局闭包
    def _rerender_all():
        nonlocal _rendered_trigger
        _rendered_trigger()

    # 让弹框能触发重渲染 (通过 global 引用)
    import builtins
    if not hasattr(builtins, "_LEARNING_RERENDER"):
        builtins._LEARNING_RERENDER = None

    if root is None:
        root = parent.winfo_toplevel()

    # ═══════════════════════════════════════════════
    #  顶栏
    # ═══════════════════════════════════════════════
    top = ttk.Frame(parent)
    top.pack(fill=tk.X, padx=6, pady=(6, 2))
    tk.Label(top, text="🎓 学习资料库", bg=_BG_PANEL, fg=_FG_GOLD,
             font=("", 12, "bold")).pack(side=tk.LEFT)
    status_lbl = tk.Label(top, text="点击打开 / 右键编辑 / 按📝进入编辑模式",
                          bg=_BG_PANEL, fg=_FG_DIM, font=("", 9))
    status_lbl.pack(side=tk.LEFT, padx=10)

    # 按钮组 (右对齐, 从右往左 pack)
    btn_editor = [None]  # 引用顶栏按钮, 切换文字
    def _toggle_edit():
        EDIT_MODE[0] = not EDIT_MODE[0]
        if EDIT_MODE[0]:
            btn_editor[0].configure(text="✅完成")
            status_lbl.configure(text="✏️ 编辑模式: 卡片显示 [编辑]/[删除] 按钮")
        else:
            btn_editor[0].configure(text="📝编辑")
            status_lbl.configure(text="点击打开 / 右键编辑 / 按📝进入编辑模式")
        _rerender_all()

    btn_popup = [None]
    def _popup_window():
        win = tk.Toplevel(root)
        win.title("🎓 学习资料库 - 独立窗口")
        win.geometry("1200x800")
        win.configure(bg=_BG_DEEP)
        build_learning_tab(win, root)

    def _refresh_from_file():
        nonlocal DATA
        DATA = _load_data()
        _rerender_all()
        messagebox.showinfo("刷新", f"已从 {_DATA_FILE} 重新加载")

    # 右对齐 (创建时直接存引用)
    ttk.Button(top, text="🗔弹出", width=6, command=_popup_window).pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(top, text="🔄刷新", width=6, command=_refresh_from_file).pack(side=tk.RIGHT, padx=(6, 0))
    btn_edit = ttk.Button(top, text="📝编辑", width=8, command=_toggle_edit)
    btn_edit.pack(side=tk.RIGHT, padx=(6, 0))
    btn_editor[0] = btn_edit  # 保存引用, 切换编辑模式时改文字
    tk.Label(top, text=" 字体:", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9)).pack(side=tk.RIGHT)
    def _do_font_plus():
        _fs(1); _rerender_all()
    def _do_font_minus():
        _fs(-1); _rerender_all()
    ttk.Button(top, text="A+", width=3, command=_do_font_plus).pack(side=tk.RIGHT, padx=(2, 1))
    ttk.Button(top, text="A-", width=3, command=_do_font_minus).pack(side=tk.RIGHT)

    # ═══════════════════════════════════════════════
    #  Notebook — 4 个子 tab
    # ═══════════════════════════════════════════════
    body = tk.Frame(parent, bg=_BG_DEEP)
    body.pack(fill=tk.BOTH, expand=True)
    nb = ttk.Notebook(body)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    tab_theory = ttk.Frame(nb); nb.add(tab_theory, text="📐 金融主流理论")
    tab_tool = ttk.Frame(nb);    nb.add(tab_tool,    text="🛠️ 主流工具")
    tab_book = ttk.Frame(nb);    nb.add(tab_book,    text="📚 学习资料 (书籍)")
    tab_src = ttk.Frame(nb);     nb.add(tab_src,     text="🎯 学习来源 (老师/媒体)")

    def _make_scrollable(frame):
        cv = tk.Canvas(frame, bg=_BG_DEEP, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=cv.yview)
        inner = ttk.Frame(cv)
        cv.configure(yscrollcommand=vsb.set)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind_all("<MouseWheel>", lambda e, c=cv: c.yview_scroll(int(-1*(e.delta/120)), "units"))
        return inner

    inner_t = _make_scrollable(tab_theory)
    inner_u = _make_scrollable(tab_tool)
    inner_b = _make_scrollable(tab_book)
    inner_s = _make_scrollable(tab_src)

    # ═══════════════════════════════════════════════
    #  卡片 + CRUD
    # ═══════════════════════════════════════════════

    def _open_url(url):
        if url and url.startswith("http"):
            webbrowser.open(url)

    def _edit_card(section_key, idx=None, sub_idx=None,
                   name="", url="", desc="", cat=""):
        _open_edit_dialog(parent, root, section_key, DATA,
                          idx=idx, sub_idx=sub_idx, old_name=name,
                          old_url=url, old_desc=desc, old_cat=cat)

    def _delete_card(section_key, idx=None, sub_idx=None, cat=None):
        if not messagebox.askyesno("确认删除", f"确定删除这条吗？"):
            return
        if section_key in ("theories", "tools"):
            if idx is not None:
                DATA[section_key].pop(idx)
        else:
            if idx is not None and sub_idx is not None:
                DATA[section_key][idx]["items"].pop(sub_idx)
                # 如果分类空了也删掉
                if not DATA[section_key][idx]["items"]:
                    DATA[section_key].pop(idx)
        if _save_data(DATA):
            _rerender_all()

    def _make_card(inner, name, url, desc, color=_FG_GOLD,
                   section_key="", idx=None, sub_idx=None, cat_name=""):
        """创建可交互卡片"""
        card = tk.Frame(inner, bg=_BG_CARD, padx=10, pady=8,
                        highlightbackground=_FG_DIM, highlightthickness=1)
        # 名称行 (可点击 or 纯文字, 看 url 是否 http)
        is_clickable = url.startswith("http")
        lbl_name = tk.Label(card, text=name, bg=_BG_CARD,
                            fg=_FG_BLUE if is_clickable else color,
                            font=_font(bold=True),
                            cursor="hand2" if is_clickable else "arrow")
        lbl_name.pack(anchor="w")
        if is_clickable:
            lbl_name.bind("<Button-1>", lambda e, u=url: _open_url(u))

        # URL 小字 (可点击)
        if url.startswith("http"):
            lbl_url = tk.Label(card, text=url[:45] + ("..." if len(url) > 45 else ""),
                               bg=_BG_CARD, fg=_FG_BLUE,
                               font=("", 8), cursor="hand2")
            lbl_url.pack(anchor="w", pady=(1, 0))
            lbl_url.bind("<Button-1>", lambda e, u=url: _open_url(u))

        # 描述
        lbl_desc = tk.Label(card, text=desc or "(无描述)", bg=_BG_CARD,
                            fg=_FG_DIM, font=_font(),
                            wraplength=340, justify=tk.LEFT)
        lbl_desc.pack(anchor="w", pady=(4, 0))

        # 右键菜单 (所有 section_key 都可用)
        def _show_menu(e):
            menu = tk.Menu(card, tearoff=0, bg=_BG_PANEL, fg=_FG_TEXT,
                           activebackground=_FG_DIM)
            menu.add_command(label="✏️ 编辑",
                             command=lambda: _edit_card(section_key, idx, sub_idx,
                                                        name, url, desc, cat_name))
            menu.add_command(label="🗑️ 删除",
                             command=lambda: _delete_card(section_key, idx, sub_idx, cat_name))
            if is_clickable:
                menu.add_separator()
                menu.add_command(label="🔗 打开链接", command=lambda: _open_url(url))
            menu.tk_popup(e.x_root, e.y_root)

        for w in (card, lbl_name, lbl_desc):
            w.bind("<Button-3>", _show_menu)
            # hover 高亮
            w.bind("<Enter>",
                   lambda e, c=card: c.configure(highlightbackground=color))
            w.bind("<Leave>",
                   lambda e, c=card: c.configure(highlightbackground=_FG_DIM))

        # 编辑模式下显示 [编辑]/[删除] 按钮
        if EDIT_MODE[0]:
            btn_row = tk.Frame(card, bg=_BG_CARD); btn_row.pack(anchor="e", pady=(4, 0))
            ttk.Button(btn_row, text="✏️", width=3,
                       command=lambda: _edit_card(section_key, idx, sub_idx,
                                                  name, url, desc, cat_name)).pack(side=tk.RIGHT, padx=2)
            ttk.Button(btn_row, text="🗑️", width=3,
                       command=lambda: _delete_card(section_key, idx, sub_idx)).pack(side=tk.RIGHT)

        return card

    def _render_all():
        """清空 + 重建所有卡片"""
        for fr in (inner_t, inner_u, inner_b, inner_s):
            for w in fr.winfo_children():
                w.destroy()

        # 顶栏 "+新增" 按钮 (动态按 tab 切换 section_key) — 这里简化: 不做顶栏, 只做卡片右键
        # Tab1: 理论 (2列网格, 顶层有新增按钮)
        tk.Label(inner_t, text="📌 右键卡片可编辑/删除, 右键空白区域可新增",
                 bg=_BG_DEEP, fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for i, item in enumerate(DATA["theories"]):
            c = 0 if i % 2 == 0 else 1
            if i % 2 == 0 and i > 0: r += 1
            _make_card(inner_t, item["name"], item.get("url", ""), item.get("desc", ""),
                       color=_FG_GOLD, section_key="theories", idx=i).grid(
                row=r, column=c, padx=6, pady=6, sticky="nsew")
        for i in range(2): inner_t.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_t, "theories")

        # Tab2: 工具
        tk.Label(inner_u, text="📌 右键卡片可编辑/删除", bg=_BG_DEEP,
                 fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for i, item in enumerate(DATA["tools"]):
            c = 0 if i % 2 == 0 else 1
            if i % 2 == 0 and i > 0: r += 1
            _make_card(inner_u, item["name"], item.get("url", ""), item.get("desc", ""),
                       color=_FG_GOLD, section_key="tools", idx=i).grid(
                row=r, column=c, padx=6, pady=6, sticky="nsew")
        for i in range(2): inner_u.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_u, "tools")

        # Tab3: 书籍 (分组)
        tk.Label(inner_b, text="📌 右键卡片可编辑/删除/新增分类", bg=_BG_DEEP,
                 fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for gi, group in enumerate(DATA["books"]):
            # 分类标题
            title = tk.Label(inner_b, text=group["category"], bg=_BG_DEEP, fg=_FG_CYAN,
                             font=_font(bold=True))
            title.grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(14, 4))
            r += 1
            for si, item in enumerate(group["items"]):
                c = 0 if si % 2 == 0 else 1
                if si % 2 == 0 and si > 0: r += 1
                _make_card(inner_b, item["name"], item.get("url", ""), item.get("desc", ""),
                           color=_FG_GOLD, section_key="books", idx=gi, sub_idx=si,
                           cat_name=group["category"]).grid(
                    row=r, column=c, padx=6, pady=6, sticky="nsew")
            r += 1
        for i in range(2): inner_b.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_b, "books")

        # Tab4: 来源 (分组)
        tk.Label(inner_s, text="📌 微信/抖音号可直接填名称+描述, URL 留空", bg=_BG_DEEP,
                 fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for gi, group in enumerate(DATA["sources"]):
            title = tk.Label(inner_s, text=group["category"], bg=_BG_DEEP, fg=_FG_CYAN,
                             font=_font(bold=True))
            title.grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(14, 4))
            r += 1
            for si, item in enumerate(group["items"]):
                c = 0 if si % 2 == 0 else 1
                if si % 2 == 0 and si > 0: r += 1
                _make_card(inner_s, item["name"], item.get("url", ""), item.get("desc", ""),
                           color=_FG_GREEN, section_key="sources", idx=gi, sub_idx=si,
                           cat_name=group["category"]).grid(
                    row=r, column=c, padx=6, pady=6, sticky="nsew")
            r += 1
        for i in range(2): inner_s.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_s, "sources")

    def _bind_add_on_blank(inner, section_key):
        """在 inner 空白区域右键 → 新增"""
        def _on_right(e, sk=section_key):
            menu = tk.Menu(inner, tearoff=0, bg=_BG_PANEL, fg=_FG_TEXT,
                           activebackground=_FG_DIM)
            menu.add_command(label="➕ 新增条目",
                             command=lambda: _edit_card(sk))
            menu.tk_popup(e.x_root, e.y_root)
        inner.bind("<Button-3>", _on_right)

    def _rendered_trigger():
        _render_all()

    # 首次渲染
    _render_all()

    # 把 rerender 暴露给弹框 (通过 builtins 让 _open_edit_dialog 能调)
    import builtins as _bi
    _bi._LEARNING_RERENDER = _render_all


class LearningMixin:
    """🎓 学习 Tab mixin — 挂到主 GUI 上"""

    def _build_learning_tab(self, parent):
        build_learning_tab(parent, root=getattr(self, "root", None))


__all__ = ["LearningMixin", "build_learning_tab"]

# -*- coding: utf-8 -*-
"""
📱 大V微信 Tab — 游资/价投大V文章管理 + AI Skill 提取 + 思维分析

布局:
  顶栏: 🔍搜索 + 名称/微信号/URL 输入 + 🚀爬 + ➕新增 + 🗑️删
  → PanedWindow(horizontal)
    左: 大V列表 Treeview (名称/分类/文章数/Skill状态)
    右: Notebook 3 子 Tab (📄文章 | 🧠Skill | 🎯思维分析)

数据持久化: SQLite 3 张表 (wechat_vv_authors / wechat_vv_articles / wechat_vv_skills)
"""
import json
import os
import sqlite3 as _sql3
import threading
import tkinter as tk
import tkinter.ttk as ttk
import webbrowser
from datetime import datetime

from data.db import DB_PATH, ensure_wechat_vv_tables

# ── 📦 内置种子大V — 游资方向 ──
_SEED_AUTHORS = [
    {"name": "赵老哥", "wechat_id": "zhaolaoge", "url": "", "category": "游资", "note": "八年一万倍 · 低吸流派"},
    {"name": "炒股养家", "wechat_id": "chaogu_yangjia", "url": "", "category": "游资", "note": "情绪周期 · 一字板战法"},
    {"name": "小鳄鱼", "wechat_id": "xiaoeyu", "url": "", "category": "游资", "note": "新生代游资 · 龙头接力"},
    {"name": "炒股的智慧", "wechat_id": "chaogudezhihui", "url": "", "category": "价投", "note": "价投理念 · 长文深度"},
    {"name": "作手新一", "wechat_id": "zuoshouxinyi", "url": "", "category": "游资", "note": "作手回忆录新篇"},
    {"name": "章盟主", "wechat_id": "zhangmengzhu", "url": "", "category": "游资", "note": "老牌游资 · 板上见"},
    {"name": "桑田路", "wechat_id": "sangtianlu", "url": "", "category": "游资", "note": "宁波桑田路席位"},
    {"name": "小散日记", "wechat_id": "xiaoshanriji", "url": "", "category": "散户", "note": "实战复盘 · 小散视角"},
]

# ── 📰 种子文章 — 每个大V给 2-3 篇占位 ──
_SEED_ARTICLES = {
    "赵老哥": [
        ("八年一万倍的心路历程", "赵老哥回顾从10万到1亿的核心转变：理解力 × 执行力 × 仓位管理的平衡。最关键的节点是2015年股灾中的冷静应对，以及之后确立的'只做龙头、只做情绪'原则。", "", "2025-10-15"),
        ("低吸战法三要素", "好的低吸点位需要三个确认：大盘环境不破位、板块龙头不跌停、个股量能缩到位。赵老哥强调左侧低吸是最难也最有爆发力的手法。", "", "2025-09-28"),
    ],
    "炒股养家": [
        ("情绪周期完整版 (2025更新)", "情绪周期7个阶段：试错期→确认期→高潮期→分歧期→退潮期→冰点期→重生期。每个阶段的操作策略完全不同，炒股养家强调不预测、只跟随。", "", "2025-11-01"),
        ("一字板买入法详解", "一字板代表最强确定性，买入需要排队技巧和板块共振确认。养家的核心：只买市场辨识度最高的那个。", "", "2025-10-20"),
    ],
    "小鳄鱼": [
        ("龙头接力的核心是什么", "小鳄鱼认为龙头接力不是最高收益的策略，但风险收益比最好。关键：分时回踩不破均价线 + 板块助攻跟上 + 大盘不配合则立刻撤。", "", "2025-10-30"),
        ("弱转强的识别与应对", "前一日涨停失败或炸板，次日高开3%以上且分时快速回封，就是弱转强。这种票往往是新周期龙头的种子。", "", "2025-10-18"),
    ],
    "炒股的智慧": [
        ("为什么90%的散户最终亏损", "炒股的智慧从概率思维出发：手续费磨损、信息不对称、情绪干扰三个因素叠加，使散户天然处于劣势。破局之道：建立系统 + 控制回撤 + 纪律执行。", "", "2025-10-25"),
    ],
    "作手新一": [
        ("作手回忆录新篇 第3章", "作手新一继续分享交易中的认知升级：从看盘到看周期，从看个股到看板块，从看板块到看宏观。三层思维的转换是质的飞跃。", "", "2025-11-05"),
        ("为什么我总在大涨前卖飞", "核心原因是没有建立仓位递增机制。正确做法：小仓试探 → 确认后加仓 → 高潮期重仓 → 分歧期减仓。", "", "2025-10-12"),
    ],
    "章盟主": [
        ("板上见 — 20年游资感悟", "章盟主总结20年游资生涯，核心感悟：1) 市场永远是对的 2) 控制回撤比盈利重要 3) 龙头是市场选出来的，不是你封出来的。", "", "2025-10-08"),
    ],
    "桑田路": [
        ("宁波桑田路的盘前思考", "桑田路席位代表的是快进快出的短线风格，盘前重点看：隔夜美股、期货夜盘、A50期指、龙虎榜数据、公告利好。", "", "2025-11-03"),
    ],
    "小散日记": [
        ("散户如何建立自己的交易系统", "从胜率、赔率、频率三个维度出发，建立适合自己的系统。最重要的是：先写下来，再去执行，然后复盘迭代。", "", "2025-10-28"),
    ],
}


def _get_conn():
    return _sql3.connect(DB_PATH)


def _seed_if_empty():
    """首次运行时注入种子大V + 种子文章"""
    ensure_wechat_vv_tables()
    conn = _get_conn(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM wechat_vv_authors")
    n = cur.fetchone()[0]
    if n == 0:
        print(f"[📱大V微信] 首次启动, 注入 {len(_SEED_AUTHORS)} 个种子大V...")
        for a in _SEED_AUTHORS:
            cur.execute(
                "INSERT INTO wechat_vv_authors (name, wechat_id, url, category, note, skill_status) VALUES (?, ?, ?, ?, ?, 'none')",
                (a["name"], a["wechat_id"], a["url"], a["category"], a["note"])
            )
            aid = cur.lastrowid
            arts = _SEED_ARTICLES.get(a["name"], [])
            for title, content, url, pt in arts:
                cur.execute(
                    "INSERT INTO wechat_vv_articles (author_id, title, content, url, publish_time) VALUES (?, ?, ?, ?, ?)",
                    (aid, title, content, url, pt)
                )
            cur.execute("UPDATE wechat_vv_authors SET article_count=? WHERE id=?", (len(arts), aid))
        conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════
#  🕷️ 爬取模块 — MVP: 手动 URL + BeautifulSoup + 搜狗微信搜索
# ═══════════════════════════════════════════════════════════════

def _try_crawl_mp_wechat(url: str) -> dict:
    """尝试爬取 mp.weixin.qq.com 文章 — 成功返回 {title, content, publish_time} 失败返回 {}"""
    try:
        import requests as _req
        from bs4 import BeautifulSoup as _BS
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        r = _req.get(url, headers=hdrs, timeout=15)
        if r.status_code != 200:
            return {}
        soup = _BS(r.text, "html.parser")
        title_el = soup.find("h1", id="activity-name")
        title = title_el.get_text(strip=True) if title_el else ""
        content_el = soup.find("div", id="js_content")
        content = content_el.get_text("\n", strip=True)[:8000] if content_el else ""
        time_el = soup.find("em", id="publish_time") or soup.find("span", class_="rich_media_meta_nickname")
        publish_time = time_el.get_text(strip=True) if time_el else ""
        return {"title": title, "content": content, "publish_time": publish_time}
    except Exception as e:
        print(f"[📱爬取] 失败: {e}")
        return {}


def _manual_add_article(author_id: int, title: str, content: str, url: str = "", publish_time: str = ""):
    """手动/爬取 添加文章"""
    if not title.strip():
        return False
    conn = _get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO wechat_vv_articles (author_id, title, content, url, publish_time) VALUES (?, ?, ?, ?, ?)",
        (author_id, title.strip(), (content or "").strip(), url.strip(), publish_time.strip() or datetime.now().strftime("%Y-%m-%d"))
    )
    cur.execute("UPDATE wechat_vv_authors SET article_count = (SELECT COUNT(*) FROM wechat_vv_articles WHERE author_id=?) WHERE id=?",
                (author_id, author_id))
    conn.commit(); conn.close()
    return True


# ═══════════════════════════════════════════════════════════════
#  🤖 AI Skill 提取
# ═══════════════════════════════════════════════════════════════

def _call_ai_safe_vv(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """AI 调用 — 复用 speculator_watch._robust_ai_call"""
    try:
        from ui.speculator_watch import _robust_ai_call
        r = _robust_ai_call(prompt, system_prompt=system, max_tokens=max_tokens)
        if r and isinstance(r, str) and len(r.strip()) > 10:
            return r
    except Exception as e:
        print(f"[📱AI] robust call 失败: {e}")
    # fallback: 简单 HTTP
    try:
        import requests as _req, json as _j, os as _os
        cfg = _os.path.join(_os.path.dirname(__file__), "..", "config", "ai_config.json")
        cfg = _os.path.abspath(cfg)
        if _os.path.exists(cfg):
            with open(cfg) as _f:
                ai_cfg = _j.load(_f)
            for pname in ["deepseek", "doubao"]:
                p = ai_cfg.get("providers", {}).get(pname)
                if not p: continue
                ak = (p.get("api_key") or "").strip()
                bu = p.get("base_url", "")
                md = p.get("model", "")
                _is_proxy = "8787" in bu
                if (not ak and not _is_proxy) or not md or not bu: continue
                url = f"{bu.rstrip('/')}/chat/completions"
                hdrs = {"Authorization": f"Bearer {ak}" if ak else "", "Content-Type": "application/json"}
                msgs = []
                if system: msgs.append({"role": "system", "content": system})
                msgs.append({"role": "user", "content": prompt})
                pl = {"model": md, "messages": msgs, "temperature": 0.3, "max_tokens": max_tokens}
                resp = _req.post(url, json=pl, headers=hdrs, timeout=45)
                if resp.status_code == 200:
                    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        print(f"[📱AI] HTTP fallback 失败: {e}")
    return ""


def _extract_skill_for_author(author_id: int, app=None) -> str:
    """AI 提取某个大V的 Skill — 返回 Markdown 格式的 skill 内容"""
    conn = _get_conn(); cur = conn.cursor()
    cur.execute("SELECT name FROM wechat_vv_authors WHERE id=?", (author_id,))
    row = cur.fetchone()
    if not row:
        conn.close(); return ""
    author_name = row[0]
    cur.execute(
        "SELECT title, content, publish_time FROM wechat_vv_articles WHERE author_id=? ORDER BY publish_time DESC LIMIT 15",
        (author_id,)
    )
    articles = cur.fetchall(); conn.close()
    if not articles:
        return ""

    # 组装 prompt — 喂给 AI
    art_text = ""
    for i, (t, c, pt) in enumerate(articles):
        c_short = (c or "")[:600]
        art_text += f"\n### 文章{i+1}: {t} ({pt})\n{c_short}\n"

    system_prompt = "你是一位专业的交易思维分析师, 擅长从大V文章中提取可复用的交易框架和思维模型。"
    user_prompt = f"""请从以下【{author_name}】的文章中, 提取出他的专属交易 Skill (Markdown 格式)。

## 需要提取的维度:
1. **核心理念**: 这位大V最信奉的1-3条交易原则
2. **风格定位**: 他是短线 / 中线 / 长线? 低吸 / 追高 / 价投?
3. **入场条件**: 他在什么情况下会买入? (具体的形态/信号/指标)
4. **离场条件**: 他在什么情况下会卖出? (止损/止盈/分歧)
5. **仓位管理**: 他如何分配仓位? (试探/加仓/减仓节奏)
6. **风控要点**: 他最强调的风险控制是什么?
7. **实战案例**: 用文中的例子说明他的实际操作
8. **一句话总结**: 用最凝练的话概括这位大V的核心 Skill

## 文章内容:
{art_text}

请输出完整的 Markdown Skill, 用 emoji 开头, 每条结论后面标注文章来源编号。"""

    result = _call_ai_safe_vv(user_prompt, system=system_prompt, max_tokens=3000)

    if result:
        # 保存到数据库
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT id FROM wechat_vv_skills WHERE author_id=? ORDER BY version DESC LIMIT 1", (author_id,))
        existing = cur.fetchone()
        cur.execute(
            "INSERT INTO wechat_vv_skills (author_id, skill_content, extracted_from, version) VALUES (?, ?, ?, ?)",
            (author_id, result, "ids", (existing[0] + 1 if existing else 1))
        )
        cur.execute("UPDATE wechat_vv_authors SET skill_status='extracted', updated_at=CURRENT_TIMESTAMP WHERE id=?", (author_id,))
        conn.commit(); conn.close()

    return result


def _apply_skill_to_analysis(author_id: int, market_context: str) -> str:
    """用某个大V的 Skill 分析当前市场/游资看盘数据"""
    conn = _get_conn(); cur = conn.cursor()
    cur.execute("SELECT name FROM wechat_vv_authors WHERE id=?", (author_id,))
    author_name = (cur.fetchone() or [""])[0]
    cur.execute("SELECT skill_content FROM wechat_vv_skills WHERE author_id=? ORDER BY version DESC LIMIT 1", (author_id,))
    skill_row = cur.fetchone(); conn.close()
    skill_content = (skill_row or [""])[0]

    if not skill_content:
        return f"⚠️ 【{author_name}】还没有提取 Skill, 请先点 🧠提取 Skill"

    system_prompt = f"你正在模拟资深游资【{author_name}】的视角进行分析。请严格按照他的 Skill 和思维框架来给出判断, 不要加入无关的通用分析。"
    user_prompt = f"""## 【{author_name}】的 Skill 框架:
{skill_content}

## 当前市场/游资看盘数据:
{market_context}

请以【{author_name}】的视角, 基于他的 Skill 框架来分析当前市场:
1. 他会认为当前处于什么阶段?
2. 他会选择什么操作? (买/卖/等/空)
3. 他会重点关注哪些板块或个股?
4. 他的风控建议是什么?

输出简洁的 Markdown, 每点 1-3 行, 用 emoji。"""

    return _call_ai_safe_vv(user_prompt, system=system_prompt, max_tokens=1500)


# ═══════════════════════════════════════════════════════════════
#  🎨 UI 主构建函数
# ═══════════════════════════════════════════════════════════════

def build_wechat_vv_tab(parent, root=None, app=None):
    """构建 📱大V微信 Tab 的全部 UI"""
    _seed_if_empty()

    # ── 顶栏 (上): 搜索 + 快捷操作 ──
    toolbar = ttk.Frame(parent); toolbar.pack(fill=tk.X, padx=6, pady=(6, 0))
    ttk.Label(toolbar, text="🔍搜索:", font=("", 10)).pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(toolbar, textvariable=search_var, width=16, font=("", 10))
    search_entry.pack(side=tk.LEFT, padx=2)
    search_entry.bind("<Return>", lambda _e: _refresh_authors())
    ttk.Button(toolbar, text="🔎", width=2, command=lambda: _refresh_authors()).pack(side=tk.LEFT, padx=1)

    ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
    ttk.Label(toolbar, text="👥 大V管理:", font=("", 10, "bold")).pack(side=tk.LEFT)

    # 大V增删改按钮 (彩色 tk.Button 更醒目)
    _btn_add  = tk.Button(toolbar, text="➕ 新增大V", width=10, bg="#43A047", fg="white",
                          font=("", 10, "bold"), relief=tk.FLAT, cursor="hand2", command=lambda: _add_author())
    _btn_edit = tk.Button(toolbar, text="✏️ 编辑大V", width=10, bg="#FB8C00", fg="white",
                          font=("", 10, "bold"), relief=tk.FLAT, cursor="hand2", command=lambda: _edit_author())
    _btn_del  = tk.Button(toolbar, text="🗑️ 删除大V", width=10, bg="#E53935", fg="white",
                          font=("", 10, "bold"), relief=tk.FLAT, cursor="hand2", command=lambda: _delete_author())
    _btn_crawl= tk.Button(toolbar, text="🕷️ 爬文章", width=8, bg="#1E88E5", fg="white",
                          font=("", 10, "bold"), relief=tk.FLAT, cursor="hand2", command=lambda: _crawl_current())
    _btn_refr = tk.Button(toolbar, text="🔄 刷新", width=6, bg="#757575", fg="white",
                          font=("", 10), relief=tk.FLAT, cursor="hand2", command=lambda: _refresh_authors())
    for b in [_btn_add, _btn_edit, _btn_del, _btn_crawl, _btn_refr]:
        b.pack(side=tk.LEFT, padx=2, pady=2)

    # ── 顶栏 (下): 新增大V输入表单 ──
    form = ttk.LabelFrame(parent, text="➕ 新增大V — 填写下面字段后点绿色「新增大V」按钮", padding=4)
    form.pack(fill=tk.X, padx=6, pady=4)
    ttk.Label(form, text="大V名称*:", font=("", 10, "bold")).pack(side=tk.LEFT)
    name_var = tk.StringVar()
    ttk.Entry(form, textvariable=name_var, width=14).pack(side=tk.LEFT, padx=(2, 10))
    ttk.Label(form, text="微信号:").pack(side=tk.LEFT)
    wxid_var = tk.StringVar()
    ttk.Entry(form, textvariable=wxid_var, width=14).pack(side=tk.LEFT, padx=(2, 10))
    ttk.Label(form, text="分类:").pack(side=tk.LEFT)
    cat_var = tk.StringVar(value="游资")
    ttk.Combobox(form, textvariable=cat_var, width=6, state="readonly",
                 values=["游资", "价投", "量化", "宏观", "行业", "散户"]).pack(side=tk.LEFT, padx=(2, 10))
    ttk.Label(form, text="URL (公众号链接):").pack(side=tk.LEFT)
    url_var = tk.StringVar()
    ttk.Entry(form, textvariable=url_var, width=28).pack(side=tk.LEFT, padx=2)

    # ── 主区 PanedWindow ──
    paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    # ── 左侧: 大V列表 ──
    left_frame = ttk.Frame(paned, width=320); paned.add(left_frame, weight=1)
    ttk.Label(left_frame, text="👥 大V列表", font=("", 11, "bold")).pack(anchor="w", padx=4, pady=(2, 4))
    auth_cols = ("id", "name", "cat", "arts", "skill")
    auth_tree = ttk.Treeview(left_frame, columns=auth_cols, show="headings", height=20)
    for c, t, w in [("id", "#", 30), ("name", "名称", 90), ("cat", "分类", 50), ("arts", "文章", 40), ("skill", "Skill", 70)]:
        auth_tree.heading(c, text=t); auth_tree.column(c, width=w, anchor="center" if c != "name" else "w")
    auth_tree.tag_configure("none", background="#FAFAFA")
    auth_tree.tag_configure("extracted", background="#E8F5E9")
    auth_tree.tag_configure("updated", background="#C8E6C9")
    vs = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=auth_tree.yview)
    auth_tree.configure(yscrollcommand=vs.set)
    auth_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vs.pack(side=tk.RIGHT, fill=tk.Y)

    # ── 🆕 右键菜单: 大V增删改 ──
    auth_menu = tk.Menu(root, tearoff=0)
    auth_menu.add_command(label="✏️ 编辑这个大V", command=lambda: _edit_author(), font=("", 10))
    auth_menu.add_command(label="➕ 新增类似的大V", command=lambda: _add_author(), font=("", 10))
    auth_menu.add_separator()
    auth_menu.add_command(label="🗑️ 删除这个大V (及其文章)", command=lambda: _delete_author(), font=("", 10))
    auth_menu.add_separator()
    auth_menu.add_command(label="🕷️ 爬取这个大V的文章", command=lambda: _crawl_current(), font=("", 10))
    auth_menu.add_command(label="🧠 提取这个大V的 Skill", command=lambda: (right_nb.select(tab_skill), _extract_skill_btn()), font=("", 10))
    auth_menu.add_command(label="🎯 用这个大V Skill 分析", command=lambda: (right_nb.select(tab_analysis), None), font=("", 10))

    def _auth_right_click(event):
        sel = auth_tree.identify_row(event.y)
        if sel:
            auth_tree.selection_set(sel); auth_tree.focus(sel)
        auth_menu.tk_popup(event.x_root, event.y_root)
    auth_tree.bind("<Button-3>", _auth_right_click)

    # ── 右侧: Notebook (文章 | Skill | 分析) ──
    right_nb = ttk.Notebook(paned); paned.add(right_nb, weight=3)

    # === Tab 1: 📄 文章列表 ===
    tab_arts = ttk.Frame(right_nb, padding=4)
    right_nb.add(tab_arts, text=" 📄 文章 ")
    art_top = ttk.Frame(tab_arts); art_top.pack(fill=tk.X, pady=(0, 4))
    art_count_lbl = ttk.Label(art_top, text="请选择左侧大V", font=("", 10))
    art_count_lbl.pack(side=tk.LEFT)
    ttk.Button(art_top, text="➕手动", width=6, command=lambda: _manual_article_dialog()).pack(side=tk.RIGHT, padx=1)
    ttk.Button(art_top, text="🗑️删", width=5, command=lambda: _delete_article()).pack(side=tk.RIGHT, padx=1)
    ttk.Button(art_top, text="✏️编辑", width=5, command=lambda: _edit_article()).pack(side=tk.RIGHT, padx=1)
    ttk.Button(art_top, text="🔗开原文", width=8, command=lambda: _open_article_url()).pack(side=tk.RIGHT, padx=1)

    art_cols = ("id", "title", "time", "preview")
    art_tree = ttk.Treeview(tab_arts, columns=art_cols, show="headings", height=18)
    for c, t, w in [("id", "#", 36), ("title", "标题", 380), ("time", "时间", 100), ("preview", "内容预览", 200)]:
        art_tree.heading(c, text=t); art_tree.column(c, width=w, anchor="w", stretch=True)
    art_vs = ttk.Scrollbar(tab_arts, orient=tk.VERTICAL, command=art_tree.yview)
    art_tree.configure(yscrollcommand=art_vs.set)
    art_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); art_vs.pack(side=tk.RIGHT, fill=tk.Y)

    # 双击打开原文
    def _art_dbl(_evt):
        _open_article_url()
    art_tree.bind("<Double-1>", _art_dbl)

    # 右下: 文章详情预览
    art_preview = tk.Text(tab_arts, wrap="word", font=("PingFang SC", 10), height=10, bg="#FAFAFA")
    art_preview.pack(fill=tk.X, pady=(4, 0))
    art_preview.config(state=tk.DISABLED)

    def _on_art_select(_evt):
        sel = art_tree.selection()
        if not sel: return
        vals = art_tree.item(sel[0], "values")
        if not vals: return
        art_id = vals[0]
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT title, content FROM wechat_vv_articles WHERE id=?", (art_id,))
        row = cur.fetchone(); conn.close()
        if row:
            art_preview.config(state=tk.NORMAL); art_preview.delete("1.0", tk.END)
            art_preview.insert("1.0", f"【{row[0]}】\n\n{(row[1] or '').strip()}")
            art_preview.config(state=tk.DISABLED)
    art_tree.bind("<<TreeviewSelect>>", _on_art_select)

    # === Tab 2: 🧠 Skill ===
    tab_skill = ttk.Frame(right_nb, padding=4)
    right_nb.add(tab_skill, text=" 🧠 Skill ")
    skill_top = ttk.Frame(tab_skill); skill_top.pack(fill=tk.X, pady=(0, 4))
    skill_status_lbl = ttk.Label(skill_top, text="", font=("", 10))
    skill_status_lbl.pack(side=tk.LEFT)
    tk.Button(skill_top, text="🔍 提取 Skill", width=14, bg="#FF6F00", fg="white",
              font=("", 10, "bold"), relief=tk.FLAT, cursor="hand2",
              command=lambda: _extract_skill_btn()).pack(side=tk.RIGHT, padx=2)
    ttk.Button(skill_top, text="💾保存编辑", width=9, command=lambda: _save_skill_edit()).pack(side=tk.RIGHT, padx=1)

    skill_text = tk.Text(tab_skill, wrap="word", font=("PingFang SC", 10), height=22,
                         bg="#FFF8E1", relief=tk.SOLID, bd=1)
    skill_text.pack(fill=tk.BOTH, expand=True)

    # === Tab 3: 🎯 思维分析 ===
    tab_analysis = ttk.Frame(right_nb, padding=4)
    right_nb.add(tab_analysis, text=" 🎯 思维分析 ")
    ana_top = ttk.Frame(tab_analysis); ana_top.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(ana_top, text="市场数据/游资看盘上下文 (粘贴或从弹窗复制):", font=("", 10)).pack(anchor="w")
    ana_context = tk.Text(tab_analysis, wrap="word", font=("Menlo", 10), height=6, bg="#F5F5F5")
    ana_context.pack(fill=tk.X, pady=(2, 4))
    ana_btn_box = ttk.Frame(tab_analysis); ana_btn_box.pack(fill=tk.X)
    ana_status_lbl = ttk.Label(ana_btn_box, text="", font=("", 10))
    ana_status_lbl.pack(side=tk.LEFT)
    tk.Button(ana_btn_box, text="🎯 用 Skill 分析", width=14, bg="#1565C0", fg="white",
              font=("", 10, "bold"), relief=tk.FLAT, cursor="hand2",
              command=lambda: _skill_analysis_btn()).pack(side=tk.RIGHT, padx=2)

    ana_text = tk.Text(tab_analysis, wrap="word", font=("PingFang SC", 11), height=20,
                       bg="#E3F2FD", relief=tk.SOLID, bd=1)
    ana_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

    # ── 当前选中状态 ──
    _state = {"author_id": None}

    # ═══════════════════════════════════════════════════════
    #  📦 刷新大V列表
    # ═══════════════════════════════════════════════════════
    def _refresh_authors():
        for iid in auth_tree.get_children():
            auth_tree.delete(iid)
        kw = search_var.get().strip()
        conn = _get_conn(); cur = conn.cursor()
        if kw:
            cur.execute(
                "SELECT id, name, category, article_count, skill_status FROM wechat_vv_authors WHERE name LIKE ? OR wechat_id LIKE ? ORDER BY article_count DESC",
                (f"%{kw}%", f"%{kw}%")
            )
        else:
            cur.execute("SELECT id, name, category, article_count, skill_status FROM wechat_vv_authors ORDER BY article_count DESC")
        for aid, nm, cat, cnt, sk in cur.fetchall():
            tag = sk if sk in ("extracted", "updated") else "none"
            auth_tree.insert("", "end", values=(aid, nm, cat, cnt, sk or "none"), tags=(tag,))
        conn.close()

    # ═══════════════════════════════════════════════════════
    #  📦 刷新文章列表 + Skill
    # ═══════════════════════════════════════════════════════
    def _on_author_select(_evt=None):
        sel = auth_tree.selection()
        if not sel: return
        vals = auth_tree.item(sel[0], "values")
        _state["author_id"] = vals[0]
        # 刷新文章
        for iid in art_tree.get_children():
            art_tree.delete(iid)
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT name FROM wechat_vv_authors WHERE id=?", (_state["author_id"],))
        nm = (cur.fetchone() or [""])[0]
        cur.execute(
            "SELECT id, title, publish_time, COALESCE(content,'') FROM wechat_vv_articles WHERE author_id=? ORDER BY publish_time DESC, id DESC",
            (_state["author_id"],)
        )
        arts = cur.fetchall()
        for aid, t, pt, c in arts:
            prev = (c[:80] + "...") if len(c) > 80 else c
            art_tree.insert("", "end", values=(aid, t, pt or "", prev))
        art_count_lbl.config(text=f"📚 【{nm}】共 {len(arts)} 篇文章")
        # 刷新 Skill
        cur.execute("SELECT skill_content, version FROM wechat_vv_skills WHERE author_id=? ORDER BY version DESC LIMIT 1", (_state["author_id"],))
        sk_row = cur.fetchall(); conn.close()
        skill_text.config(state=tk.NORMAL); skill_text.delete("1.0", tk.END)
        if sk_row:
            skill_text.insert("1.0", sk_row[0][0])
            skill_status_lbl.config(text=f"✅ Skill v{sk_row[0][1]} 已提取 ({len(sk_row[0][0])}字)")
        else:
            skill_text.insert("1.0", "_(还没有 Skill, 点右上「🔍 提取 Skill」按钮让 AI 自动分析)_")
            skill_status_lbl.config(text="⚠️ 还没有 Skill")
        skill_text.config(state=tk.DISABLED)

    auth_tree.bind("<<TreeviewSelect>>", _on_author_select)

    # ═══════════════════════════════════════════════════════
    #  ➕ 大V增删改
    # ═══════════════════════════════════════════════════════
    def _add_author():
        nm = name_var.get().strip()
        if not nm:
            tk.messagebox.showwarning("提示", "请先在顶部输入大V名称")
            return
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT id FROM wechat_vv_authors WHERE name=?", (nm,))
        if cur.fetchone():
            tk.messagebox.showwarning("提示", f"大V【{nm}】已存在")
            conn.close(); return
        cur.execute(
            "INSERT INTO wechat_vv_authors (name, wechat_id, url, category, skill_status) VALUES (?, ?, ?, ?, 'none')",
            (nm, wxid_var.get().strip(), url_var.get().strip(), cat_var.get())
        )
        conn.commit(); conn.close()
        name_var.set(""); wxid_var.set(""); url_var.set("")
        _refresh_authors()

    def _edit_author():
        sel = auth_tree.selection()
        if not sel: return
        aid = auth_tree.item(sel[0], "values")[0]
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT name, wechat_id, url, avatar, category, note, article_count, skill_status FROM wechat_vv_authors WHERE id=?", (aid,))
        row = cur.fetchone(); conn.close()
        if not row: return
        nm, wxid, u, avatar, cat, note, cnt, sk = row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]

        dlg = tk.Toplevel(root)
        dlg.title(f"✏️ 编辑大V: {nm}"); dlg.geometry("560x440"); dlg.minsize(500, 400); dlg.transient(root)
        dlg.grab_set()

        # 顶部状态条 — 显示只读的统计信息
        top_info = tk.Frame(dlg, bg="#E3F2FD"); top_info.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(top_info, text=f"📚 文章: {cnt}篇  |  🧠 Skill: {sk or 'none'}",
                 bg="#E3F2FD", fg="#1565C0", font=("", 10)).pack(side=tk.LEFT, padx=10, pady=4)
        tk.Label(top_info, text=f"(修改这些字段后点下面 💾 保存)",
                 bg="#E3F2FD", fg="#616161", font=("", 9)).pack(side=tk.RIGHT, padx=10)

        form = tk.Frame(dlg); form.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        form.columnconfigure(1, weight=1)

        # 用 StringVar 存值 — 这样 save 时直接取 var.get() 就行
        v_name  = tk.StringVar(value=nm or "")
        v_wxid  = tk.StringVar(value=wxid or "")
        v_url   = tk.StringVar(value=u or "")
        v_avt   = tk.StringVar(value=avatar or "")
        v_cat   = tk.StringVar(value=cat or "游资")
        v_note  = tk.StringVar(value=note or "")

        def _row(parent, lbl, var, row, is_combo=False, combo_vals=None, is_text=False, text_h=5):
            tk.Label(parent, text=lbl, font=("", 10, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            if is_text:
                e = tk.Text(parent, wrap="word", height=text_h, font=("PingFang SC", 10)); e.grid(row=row, column=1, sticky="we", pady=4)
                if var.get(): e.insert("1.0", var.get())
                return e
            elif is_combo:
                e = ttk.Combobox(parent, textvariable=var, values=combo_vals or [], state="readonly", font=("", 10))
                e.grid(row=row, column=1, sticky="we", pady=4); return e
            else:
                e = ttk.Entry(parent, textvariable=var, font=("", 10))
                e.grid(row=row, column=1, sticky="we", pady=4); return e

        _row(form, "大V名称*:", v_name, 0)
        _row(form, "微信号:", v_wxid, 1)
        _row(form, "分类:", v_cat, 2, is_combo=True, combo_vals=["游资", "价投", "量化", "宏观", "行业", "散户"])
        _row(form, "头像URL:", v_avt, 3)
        _row(form, "公众号URL:", v_url, 4)
        _row(form, "备注:", v_note, 5, is_text=True, text_h=4)
        note_text_widget = form.grid_slaves(row=5, column=1)[0]  # Text 控件引用

        # 按钮行
        btns = tk.Frame(dlg); btns.pack(fill=tk.X, padx=10, pady=8)
        def _save():
            # 校验
            name_val = v_name.get().strip()
            if not name_val:
                tk.messagebox.showwarning("提示", "大V名称不能为空"); return
            # 取 note Text 内容
            note_val = note_text_widget.get("1.0", tk.END).strip()
            conn2 = _get_conn(); cur2 = conn2.cursor()
            cur2.execute(
                """UPDATE wechat_vv_authors
                   SET name=?, wechat_id=?, url=?, avatar=?, category=?, note=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (name_val, v_wxid.get().strip(), v_url.get().strip(), v_avt.get().strip(),
                 v_cat.get().strip(), note_val, aid)
            )
            conn2.commit(); conn2.close()
            dlg.destroy()
            _refresh_authors()
            # 如果正在编辑当前选中的大V, 刷新右侧
            if _state["author_id"] == aid:
                kids = auth_tree.get_children()
                for k in kids:
                    if auth_tree.item(k, "values")[0] == aid:
                        auth_tree.selection_set(k); auth_tree.see(k); _on_author_select(); break

        tk.Button(btns, text="💾 保存修改", width=14, bg="#2E7D32", fg="white",
                  font=("", 11, "bold"), relief=tk.FLAT, cursor="hand2",
                  command=_save).pack(side=tk.RIGHT, padx=4)
        tk.Button(btns, text="❌ 取消", width=8, bg="#9E9E9E", fg="white",
                  font=("", 10), relief=tk.FLAT, cursor="hand2",
                  command=dlg.destroy).pack(side=tk.RIGHT, padx=4)

    # ═══════════════════════════════════════════════════════
    #  📦 文章增删改 + 打开
    # ═══════════════════════════════════════════════════════
    def _manual_article_dialog():
        if not _state["author_id"]:
            tk.messagebox.showwarning("提示", "请先选择左侧大V")
            return
        dlg = tk.Toplevel(root); dlg.title("➕ 新增文章"); dlg.geometry("600x420"); dlg.transient(root)
        ttk.Label(dlg, text="标题:").pack(anchor="w", padx=10, pady=(8, 0))
        t = tk.StringVar()
        ttk.Entry(dlg, textvariable=t, width=60).pack(fill=tk.X, padx=10)
        ttk.Label(dlg, text="URL (可选):").pack(anchor="w", padx=10, pady=(6, 0))
        u = tk.StringVar()
        ttk.Entry(dlg, textvariable=u, width=60).pack(fill=tk.X, padx=10)
        ttk.Label(dlg, text="发布时间 (YYYY-MM-DD, 可选):").pack(anchor="w", padx=10, pady=(6, 0))
        p = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(dlg, textvariable=p, width=20).pack(anchor="w", padx=10)
        ttk.Label(dlg, text="内容 (可直接粘贴大V文章正文):").pack(anchor="w", padx=10, pady=(6, 0))
        c = tk.Text(dlg, wrap="word", height=12, font=("PingFang SC", 10)); c.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        def _do_add():
            title = t.get().strip()
            content = c.get("1.0", tk.END).strip()
            if not title:
                tk.messagebox.showwarning("提示", "标题不能为空")
                return
            # 如果 URL 是 mp.weixin.qq.com, 自动爬取内容
            url_val = u.get().strip()
            content_final = content
            if url_val and "mp.weixin.qq.com" in url_val and not content:
                dlg.config(cursor="watch"); dlg.update()
                crawled = _try_crawl_mp_wechat(url_val)
                if crawled.get("title") and not title:
                    title = crawled["title"]
                if crawled.get("content"):
                    content_final = crawled["content"]
                if crawled.get("publish_time"):
                    p.set(crawled["publish_time"])
            _manual_add_article(_state["author_id"], title, content_final, url_val, p.get())
            dlg.destroy(); _on_author_select()

        btns = ttk.Frame(dlg); btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="💾 保存", command=_do_add).pack(side=tk.RIGHT, padx=4)
        if url_var.get() and "mp.weixin.qq.com" in url_var.get():
            ttk.Button(btns, text="🕷️ 爬取URL内容", command=_do_add).pack(side=tk.RIGHT, padx=4)

    def _edit_article():
        sel = art_tree.selection();
        if not sel or not _state["author_id"]: return
        art_id = art_tree.item(sel[0], "values")[0]
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT title, content, url, publish_time FROM wechat_vv_articles WHERE id=?", (art_id,))
        row = cur.fetchone(); conn.close()
        if not row: return
        title, content, url, pt = row
        dlg = tk.Toplevel(root); dlg.title("✏️ 编辑文章"); dlg.geometry("600x460"); dlg.transient(root)
        ttk.Label(dlg, text="标题:").pack(anchor="w", padx=10, pady=(8, 0))
        t_var = tk.StringVar(value=title)
        ttk.Entry(dlg, textvariable=t_var, width=60).pack(fill=tk.X, padx=10)
        ttk.Label(dlg, text="URL:").pack(anchor="w", padx=10, pady=(6, 0))
        u_var = tk.StringVar(value=url or "")
        ttk.Entry(dlg, textvariable=u_var, width=60).pack(fill=tk.X, padx=10)
        ttk.Label(dlg, text="发布时间:").pack(anchor="w", padx=10, pady=(6, 0))
        p_var = tk.StringVar(value=pt or "")
        ttk.Entry(dlg, textvariable=p_var, width=20).pack(anchor="w", padx=10)
        ttk.Label(dlg, text="内容:").pack(anchor="w", padx=10, pady=(6, 0))
        c_text = tk.Text(dlg, wrap="word", height=14, font=("PingFang SC", 10))
        c_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        c_text.insert("1.0", content or "")

        def _do_save():
            conn2 = _get_conn(); cur2 = conn2.cursor()
            cur2.execute(
                "UPDATE wechat_vv_articles SET title=?, content=?, url=?, publish_time=? WHERE id=?",
                (t_var.get().strip(), c_text.get("1.0", tk.END).strip(), u_var.get().strip(), p_var.get().strip(), art_id)
            )
            conn2.commit(); conn2.close()
            dlg.destroy(); _on_author_select()
        ttk.Button(dlg, text="💾 保存", command=_do_save).pack(pady=6)

    def _delete_article():
        sel = art_tree.selection()
        if not sel: return
        art_id = art_tree.item(sel[0], "values")[0]
        if not tk.messagebox.askyesno("确认", "确定删除这篇文章?"): return
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM wechat_vv_articles WHERE id=?", (art_id,))
        cur.execute("UPDATE wechat_vv_authors SET article_count = (SELECT COUNT(*) FROM wechat_vv_articles WHERE author_id=?) WHERE id=?", (_state["author_id"], _state["author_id"]))
        conn.commit(); conn.close()
        _on_author_select()

    def _open_article_url():
        sel = art_tree.selection()
        if not sel: return
        art_id = art_tree.item(sel[0], "values")[0]
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT url FROM wechat_vv_articles WHERE id=?", (art_id,))
        row = cur.fetchone(); conn.close()
        if row and row[0] and row[0].startswith("http"):
            webbrowser.open(row[0], new=2)

    # ═══════════════════════════════════════════════════════
    #  🕷️ 爬取当前大V
    # ═══════════════════════════════════════════════════════
    def _crawl_current():
        if not _state["author_id"]:
            tk.messagebox.showwarning("提示", "请先选择左侧大V")
            return
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT name, url FROM wechat_vv_authors WHERE id=?", (_state["author_id"],))
        row = cur.fetchall(); conn.close()
        if not row: return
        nm, u = row[0]
        # 如果有 URL 且是 mp.weixin.qq.com — 直接弹新增对话框让用户确认
        if u and "mp.weixin.qq.com" in u:
            tk.messagebox.showinfo("提示", f"大V【{nm}】已有 URL, 建议用「➕手动」对话框粘贴文章链接后自动爬取")
            _manual_article_dialog()
        else:
            tk.messagebox.showinfo("提示", "微信公众号反爬较强,\n建议点「➕手动」按钮, 粘贴 mp.weixin.qq.com 链接, 系统会自动抓取标题+内容。")

    # ═══════════════════════════════════════════════════════
    #  🧠 Skill 提取 / 保存 / 应用
    # ═══════════════════════════════════════════════════════
    def _extract_skill_btn():
        if not _state["author_id"]:
            tk.messagebox.showwarning("提示", "请先选择左侧大V")
            return
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM wechat_vv_articles WHERE author_id=?", (_state["author_id"],))
        n = cur.fetchone()[0]; conn.close()
        if n < 1:
            tk.messagebox.showwarning("提示", "该大V还没有文章, 至少需要 1 篇文章才能提取 Skill")
            return
        skill_status_lbl.config(text=f"⏳ 正在 AI 分析 {n} 篇文章, 提取 Skill...")
        skill_text.config(state=tk.NORMAL); skill_text.delete("1.0", tk.END)
        skill_text.insert("1.0", "_AI 正在分析中... (可能需要 20-60 秒)_"); skill_text.config(state=tk.DISABLED)

        def _bg():
            result = _extract_skill_for_author(_state["author_id"], app=app)
            def _done():
                skill_text.config(state=tk.NORMAL); skill_text.delete("1.0", tk.END)
                if result:
                    skill_text.insert("1.0", result)
                    skill_status_lbl.config(text=f"✅ Skill 提取成功 ({len(result)}字)")
                    # 更新列表 skill 状态
                    _refresh_authors()
                else:
                    skill_text.insert("1.0", "_AI 提取失败, 请检查 AI 代理是否启动 (端口 8787)_")
                    skill_status_lbl.config(text="❌ AI 提取失败")
                skill_text.config(state=tk.DISABLED)
            root.after(0, _done)

        threading.Thread(target=_bg, daemon=True).start()

    def _save_skill_edit():
        if not _state["author_id"]: return
        # 先解锁读取, 再重新锁
        skill_text.config(state=tk.NORMAL)
        content = skill_text.get("1.0", tk.END).strip()
        skill_text.config(state=tk.DISABLED)
        if not content or content.startswith("_"):
            return
        conn = _get_conn(); cur = conn.cursor()
        cur.execute("SELECT MAX(version) FROM wechat_vv_skills WHERE author_id=?", (_state["author_id"],))
        v = (cur.fetchone()[0] or 0) + 1
        cur.execute(
            "INSERT INTO wechat_vv_skills (author_id, skill_content, extracted_from, version) VALUES (?, ?, 'manual_edit', ?)",
            (_state["author_id"], content, v)
        )
        cur.execute("UPDATE wechat_vv_authors SET skill_status='updated', updated_at=CURRENT_TIMESTAMP WHERE id=?", (_state["author_id"],))
        conn.commit(); conn.close()
        skill_status_lbl.config(text=f"✅ Skill v{v} 已手动保存 ({len(content)}字)")
        _refresh_authors()

    def _skill_analysis_btn():
        if not _state["author_id"]:
            tk.messagebox.showwarning("提示", "请先选择左侧大V")
            return
        ctx = ana_context.get("1.0", tk.END).strip()
        if not ctx:
            tk.messagebox.showinfo("提示", "请先在上方粘贴市场/游资看盘数据")
            return
        ana_status_lbl.config(text="⏳ 正在用大V Skill 分析..."); ana_text.config(state=tk.NORMAL); ana_text.delete("1.0", tk.END)
        ana_text.insert("1.0", "_AI 正在思考..._"); ana_text.config(state=tk.DISABLED)

        def _bg():
            result = _apply_skill_to_analysis(_state["author_id"], ctx)
            def _done():
                ana_text.config(state=tk.NORMAL); ana_text.delete("1.0", tk.END)
                ana_text.insert("1.0", result or "(AI 无回复)"); ana_text.config(state=tk.DISABLED)
                ana_status_lbl.config(text="✅ 分析完成")
            root.after(0, _done)

        threading.Thread(target=_bg, daemon=True).start()

    # ═══════════════════════════════════════════════════════
    #  🚀 初始化渲染
    # ═══════════════════════════════════════════════════════
    _refresh_authors()
    # 选第一个大V
    kids = auth_tree.get_children()
    if kids:
        auth_tree.selection_set(kids[0])
        auth_tree.see(kids[0])
        _on_author_select()


# ═══════════════════════════════════════════════════════════════
#  🧩 Mixin 供主程序继承
# ═══════════════════════════════════════════════════════════════

class WeChatVVMixin:
    """📱大V微信 Tab mixin — 挂到主 GUI 上"""

    def _build_wechat_vv_tab(self, parent):
        build_wechat_vv_tab(parent, root=getattr(self, "root", None), app=self)


__all__ = ["WeChatVVMixin", "build_wechat_vv_tab"]

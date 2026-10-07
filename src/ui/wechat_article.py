"""
📱 微信公众号日报生成器 — v2 完整版

8 个并行采集任务 → 多 Tab 实时日志 → 全完成后 AI 汇总 → 公众号 HTML

数据源:
  📊 大盘指数 (腾讯行情 qt.gtimg.cn)
  🔥 龙头股/涨跌停 (akshare + 腾讯)
  🖼️ 情绪周期截图 (SQLite sentiment_history → matplotlib 画图 → base64)
  🕷️ 淘股吧+韭研公社爬取 (SQLite crawled_articles)
  💰 带血筹码+龙虎榜 (SQLite stock_analysis + lhb_records)
  🌏 全球市场 (腾讯行情)
  💥 历史对照 (SQLite crash_rally_events)
"""

import os as _os
import sqlite3 as _sqlite3
import datetime as _dt
import threading as _th
import concurrent.futures as _cf
import tkinter as _tk
import tkinter.messagebox as _mb
import tkinter.ttk as _ttk
import time as _time
import re as _re
import base64 as _b64
import io as _io
import json as _json


# ========================================================
#  模板 + Prompt (扩展: 加入图片/爬取/带血筹码)
# ========================================================

TEMPLATES = {
    "daily": ("📰 每日晚报", "大盘+情绪+龙头+爬取+带血筹码+全球+历史", "daily_evening"),
    "hotspot": ("🔥 热点题材", "龙头+板块+情绪周期+爬取逻辑", "hotspot"),
    "crash": ("💥 暴跌复盘", "跌幅+情绪冰点+带血筹码机会+历史对照", "crash_review"),
    "weekly": ("📅 周度策略", "本周复盘+下周预判+带血筹码扫描+爬取汇总", "weekly_strategy"),
}

PROMPTS = {
    "daily_evening": """你是A股资深财经博主。基于以下今日市场数据，写一篇公众号日报。

【日期】{date}

【大盘指数】{market_indices}

【龙头股/涨跌停】{leader_stocks}

【情绪周期位置】{sentiment_desc}

【全球市场】{global_markets}

【淘股吧/韭研公社爬取热门观点】{crawled_hot}

【带血筹码扫描 (Skill)】{blood_chips}

【趋势三阶段扫描 (Skill)】{trend_phases}

【龙虎榜近3日】{lhb}

【历史对照】{history_context}

【要求】
1. 标题抓眼球 (20字内, 带emoji)
2. 分7段: 大盘概况 → 情绪解读(结合周期位置) → 龙头/涨停梯队 → 爬取热门观点 → 带血筹码机会 → 趋势三阶段分析 → 明日展望
3. 每段配小标题 (emoji + 加粗)
4. 口语化, 像和朋友聊天, 不要官话
5. 结尾给一个明确的操作建议 (仓位/方向/警惕)
6. 输出 Markdown""",

    "hotspot": """你是A股题材猎手。
【龙头/涨跌停】{leader_stocks} | 【情绪周期】{sentiment_desc} | 【爬取热门】{crawled_hot}
【带血筹码】{blood_chips} | 【趋势三阶段】{trend_phases}
写一篇800字热点分析, 标题🔥+题材关键词, 输出 Markdown""",

    "crash_review": """你是A股熊市生存者。
【大盘】{market_indices} | 【情绪周期】{sentiment_desc} | 【带血筹码机会】{blood_chips}
【历史对照】{history_context}
写暴跌复盘, 给3条生存法则, 输出 Markdown""",

    "weekly_strategy": """你是A股周度策略师。
【大盘】{market_indices} | 【龙头】{leader_stocks} | 【情绪】{sentiment_desc}
【爬取】{crawled_hot} | 【带血筹码】{blood_chips} | 【趋势三阶段】{trend_phases}
写下周策略, 明确说"乐观/中性/悲观", 输出 Markdown""",
}


# ========================================================
#  DB 路径
# ========================================================

def _stock_db():
    """找 stock_analysis.db — 优先 data/ 目录 (17张表), 其次 ~/.qclaw/ (仅 crash_rally)"""
    here = _os.path.dirname(_os.path.abspath(__file__))  # src/ui/
    project_root = _os.path.dirname(_os.path.dirname(here))  # 项目根 (往上 2 级: ui→src→根)
    paths = [
        _os.path.join(project_root, "data", "stock_analysis.db"),
        _os.path.expanduser("~/.qclaw/stock_analysis.db"),
    ]
    for p in paths:
        if _os.path.exists(p): return p
    return paths[0]


# ========================================================
#  8 个并行采集任务
# ========================================================

TASK_KEYS = ["indices", "leader", "sentiment", "crawled", "lhb_blood", "skill_blood", "skill_trend", "global", "history"]
TASK_LABELS = {
    "indices": "📊 大盘指数",
    "leader": "🔥 龙头/涨跌停",
    "sentiment": "🖼️ 情绪周期",
    "crawled": "🕷️ 爬取资讯",
    "lhb_blood": "💰 龙虎榜",
    "skill_blood": "🩸 带血筹码扫描",
    "skill_trend": "📈 趋势三阶段",
    "global": "🌏 全球市场",
    "history": "💥 历史对照",
}

# Skill 路径
_SKILL_BLOOD = _os.path.expanduser("~/.qclaw/skills/blood-chips-scanner")
_SKILL_TREND = _os.path.expanduser("~/.trae-cn/skills/trend-phase-scanner/scripts")

# SSL 全局修复 (新浪财经需要)
import ssl as _ssl
try:
    _ssl._create_default_https_context = _ssl._create_unverified_context
except Exception:
    pass

# 每个任务返回 str, 但 sentiment 额外返回 image_base64

# -------- 1. 大盘指数 --------
def fetch_indices(cb):
    import requests as _rq
    idx = [("sh000001", "上证指数"), ("sz399001", "深证成指"),
           ("sz399006", "创业板指"), ("sh000688", "科创50")]
    cb("📡 腾讯行情...")
    r = _rq.get(f"https://qt.gtimg.cn/q={','.join(c for c,_ in idx)}", timeout=5)
    by_code = {cp.split("_")[-1]: vp.strip('"').split("~")
               for line in r.text.strip().split(";") if "=" in line
               for cp, vp in [line.split("=", 1)]}
    results = []
    for code, name in idx:
        v = by_code.get(code, [])
        if len(v) > 32:
            results.append(f"· {name}: {v[3]} ({v[32]}%)")
            cb(f"✅ {name} = {v[3]} ({v[32]}%)")
        else:
            results.append(f"· {name}: (无数据)")
    return "\n".join(results)

# -------- 2. 龙头股/涨跌停 --------
def fetch_leader(cb):
    try:
        import akshare as ak
        cb("📡 akshare 涨停池...")
        today = _dt.date.today().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=today)
        n_zt = len(df)
        cb(f"✅ 涨停 {n_zt} 只")
        # Top 10 连板
        top = df.head(10)
        lines = [f"🔥 今日涨停 {n_zt} 只\n"]
        for _, row in top.iterrows():
            name = row.get('名称', row.get('股票名称', '?'))
            code = row.get('代码', row.get('股票代码', ''))
            pct = row.get('涨跌幅', row.get('最新价', '?'))
            lines.append(f"  · {name}({code}) +{pct}%")
        # 成交额
        if '成交额' in df.columns:
            total_yi = df['成交额'].sum() / 1e8
            lines.append(f"\n📊 涨停板总成交额: {total_yi:.0f} 亿")
            cb(f"✅ 涨停总成交额 {total_yi:.0f} 亿")
        return "\n".join(lines)
    except Exception as e:
        cb(f"⚠️ akshare: {e}")
        return f"(涨跌停数据不可用: {e})"

# -------- 3. 情绪周期 + 画图 --------
def fetch_sentiment(cb):
    db = _stock_db()
    cb(f"📂 连接 {db}")
    conn = _sqlite3.connect(db); cur = conn.cursor()
    # 最近 60 天
    cur.execute(
        "SELECT snapshot_date, m1_today, m2_up, m2_down, m2_flat, "
        "m3_count, m4_count, m5_avg FROM sentiment_history "
        "ORDER BY snapshot_date DESC LIMIT 60"
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        cb("⚠️ sentiment_history 无数据")
        return "(情绪周期无数据: 请先在情绪周期Tab采集)"

    rows.reverse()  # 升序画图
    dates = [r[0] for r in rows]
    m1 = [r[1] if r[1] is not None else 0 for r in rows]  # 情绪指数
    m2_up = [r[2] or 0 for r in rows]
    m2_down = [r[3] or 0 for r in rows]
    m3 = [r[5] or 0 for r in rows]  # 涨停数

    cb(f"✅ 获取 {len(rows)} 天情绪数据")

    # 判断当前周期位置
    last_m1 = m1[-1] if m1 else 0
    last_m3 = m3[-1] if m3 else 0
    if last_m1 < 30: phase = "❄️ 冰点 (谨慎抄底)"
    elif last_m1 < 50: phase = "📉 退潮 (观望为主)"
    elif last_m1 < 70: phase = "🌊 复苏 (可小仓位)"
    else: phase = "🔥 高潮 (警惕接力)"
    cb(f"📍 情绪周期位置: {phase} (指数={last_m1:.1f}, 涨停={last_m3})")

    # 画图 → base64
    img_b64 = _draw_sentiment_chart(dates, m1, m2_up, m2_down, m3, cb)

    desc = f"情绪指数={last_m1:.1f} 涨停={last_m3}只 周期位置:{phase}"
    if img_b64:
        cb(f"🖼️ 情绪周期图已生成 ({len(img_b64)//1024}KB base64)")
        # 存到全局让 HTML 渲染时用
        _LAST_SENTIMENT_IMG["b64"] = img_b64
        _LAST_SENTIMENT_IMG["desc"] = desc
    return desc


def _draw_sentiment_chart(dates, m1, up, down, zt_counts, cb):
    """matplotlib 情绪周期双栏图 → PNG bytes → base64"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime as _dt2

        # 中文字体
        plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 7),
                                              gridspec_kw={'height_ratios': [3, 2, 1]})
        fig.patch.set_facecolor('#1a1a2e')

        # X 轴日期
        x_idx = list(range(len(dates)))

        # 上: 情绪指数 + 周期线
        ax1.set_facecolor('#16213e')
        ax1.plot(x_idx, m1, color='#4ecdc4', linewidth=2, label='情绪指数')
        ax1.axhline(y=30, color='#e94560', linestyle='--', alpha=0.5, label='冰点30')
        ax1.axhline(y=70, color='#ffd700', linestyle='--', alpha=0.5, label='高潮70')
        ax1.fill_between(x_idx, 30, 70, alpha=0.05, color='#4ecdc4')
        ax1.set_ylim(0, 100)
        ax1.set_title('情绪周期 (近60天)', color='#eee', fontsize=13, pad=10)
        ax1.tick_params(colors='#aaa')
        ax1.legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', labelcolor='#eee')
        ax1.grid(True, alpha=0.2, color='#444')

        # 中: 涨跌家数
        ax2.set_facecolor('#16213e')
        width = 0.35
        ax2.bar([i - width/2 for i in x_idx], up, width, color='#e94560', label='上涨', alpha=0.8)
        ax2.bar([i + width/2 for i in x_idx], down, width, color='#4CAF50', label='下跌', alpha=0.8)
        ax2.set_title('涨跌家数', color='#eee', fontsize=10)
        ax2.tick_params(colors='#aaa')
        ax2.legend(loc='upper right', fontsize=8, facecolor='#1a1a2e', labelcolor='#eee')
        ax2.grid(True, alpha=0.2, color='#444')

        # 下: 涨停数
        ax3.set_facecolor('#16213e')
        ax3.bar(x_idx, zt_counts, color='#ffd700', alpha=0.8)
        ax3.set_title('涨停家数', color='#eee', fontsize=10)
        ax3.tick_params(colors='#aaa')
        ax3.grid(True, alpha=0.2, color='#444')

        # X 轴标签 (稀疏)
        tick_step = max(1, len(dates) // 8)
        for ax in [ax1, ax2, ax3]:
            ax.set_xticks(x_idx[::tick_step])
            ax.set_xticklabels([dates[i][-5:] for i in range(0, len(dates), tick_step)],
                               color='#aaa', fontsize=8, rotation=30)
            for spine in ax.spines.values():
                spine.set_color('#444')

        plt.tight_layout(pad=1.5)

        buf = _io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return _b64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        cb(f"⚠️ 情绪图画图失败: {e}")
        return None

_LAST_SENTIMENT_IMG = {"b64": None, "desc": None}

# -------- 4. 淘股吧/韭研公社爬取 --------
def fetch_crawled(cb):
    db = _stock_db()
    cb(f"📂 连接 crawled_articles...")
    conn = _sqlite3.connect(db); cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='crawled_articles'"
    )
    if not cur.fetchone():
        conn.close()
        cb("⚠️ 无 crawled_articles 表")
        return "(爬取数据请在一键爬取Tab先采集)"

    # 近爬取的热文 (publish_time 全 NULL → 用 crawled_at)
    cb("📊 查询近期爬取热文...")
    cur.execute(
        "SELECT source, title, content, crawled_at, views, likes, replies "
        "FROM crawled_articles ORDER BY COALESCE(crawled_at, publish_time) DESC LIMIT 30"
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        cb("⚠️ crawled_articles 空表")
        return "(爬取数据: 请在一键爬取Tab先采集)"

    cb(f"✅ {len(rows)} 条爬取热文")
    # 按来源分组
    by_source = {}
    for src, title, content, ct, views, likes, replies in rows:
        src_name = src or "未知来源"
        if src_name not in by_source: by_source[src_name] = []
        by_source[src_name].append((title or "(无标题)", content or "", views or 0))

    lines = []
    for src, items in by_source.items():
        lines.append(f"\n【{src}】({len(items)}条热文)")
        cb(f"  👉 {src}: {len(items)} 条")
        for title, content, views in items[:5]:
            lines.append(f"  📰 {title} (👁{views})")
            summary = content[:120].replace("\n", " ").strip()
            if summary: lines.append(f"    {summary}...")
    return "\n".join(lines)

# -------- 5. 带血筹码 + 龙虎榜 --------
def fetch_lhb(cb):
    """龙虎榜 (DB lhb_records 1394条)"""
    db = _stock_db()
    conn = _sqlite3.connect(db); cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lhb_records'")
    if not cur.fetchone():
        conn.close(); return "(无 lhb_records)"
    cur.execute("SELECT COUNT(*) FROM lhb_records")
    cb(f"✅ lhb_records {cur.fetchone()[0]} 条")
    cur.execute("SELECT name, trade_date, reason, net_amount, pct_change "
                "FROM lhb_records ORDER BY trade_date DESC LIMIT 10")
    lhb = cur.fetchall()
    conn.close()
    if not lhb: return "(近3天龙虎榜空)"
    out = ["\n【🐉 龙虎榜近3日】"]
    for name, td, reason, net, pct in lhb:
        net_str = f"{net/1e8:.1f}亿" if net and abs(net) > 1e7 else f"{net/1e4:.0f}万" if net else "-"
        out.append(f"  · {name} ({td}) {reason or ''} 净{net_str} {pct:+.2f}%")
    cb(f"  → {len(lhb)} 条")
    return "\n".join(out)


def fetch_skill_blood(cb):
    """🩸 带血筹码 Skill (~/.qclaw/skills/blood-chips-scanner)"""
    import sys as _sys, os as _os
    if _SKILL_BLOOD not in _sys.path:
        _sys.path.insert(0, _SKILL_BLOOD)
    try:
        import scanner as bcs
    except ImportError as e:
        cb(f"⚠️ 不能导入 blood-chips-scanner: {e}")
        return f"(带血筹码 Skill 未安装: {e})"

    cb("🔍 扫描全市场带血筹码 (4937只 A股)...")
    result = bcs.scan_market(top_n=50, verbose=False)
    report = bcs.generate_report(result)
    # 提取核心行: 血腥区 + 偏低区
    lines = report.split("\n")
    blood_lines = [l for l in lines if '🩸' in l or ('|' in l and not l.startswith('---'))]
    cb(f"✅ 扫描完成, 报告 {len(report)} 字")
    # 返回精简版 (完整 Markdown 报告前 800 字)
    return report[:1000]


def fetch_skill_trend(cb):
    """📈 趋势三阶段 Skill (~/.trae-cn/skills/trend-phase-scanner)"""
    import sys as _sys
    if _SKILL_TREND not in _sys.path:
        _sys.path.insert(0, _SKILL_TREND)
    try:
        import trend_phase_scanner as tps
    except ImportError as e:
        cb(f"⚠️ 不能导入 trend-phase-scanner: {e}")
        return f"(趋势三阶段 Skill 未安装: {e})"

    cb("🔍 取扫描候选股...")
    candidates = _get_trend_candidates(cb)
    if not candidates:
        cb("⚠️ 无候选股")
        return "(趋势三阶段: 无候选股)"

    cb(f"🔍 扫描 {len(candidates)} 只股票 (每只要拉 120 天K线)...")
    results = []
    for name, code in candidates[:25]:  # tuple: (name, code)
        try:
            r = tps.process((code, name))  # 要 tuple!
            if r: results.append(r)
            else: cb(f"   → {name}: 数据不足或无信号")
        except Exception as e:
            cb(f"   → {name}: 失败({e})")

    if not results:
        cb("⚠️ 无有效结果")
        return "(趋势三阶段: 扫描无结果, 股票数据不足)"

    cb(f"✅ {len(results)} 只有效结果")
    groups = {"初期": [], "中期": [], "末期": [], "下跌/超卖": []}
    for r in results:
        phase = r.get("phase", "")
        nm = r.get("name", "?"); sc = r.get("score", 0)
        entry = f"  · {nm} — {phase} (得分:{sc})"
        matched = False
        for gkey in groups:
            if gkey in phase or (gkey == "下跌/超卖" and ("下跌" in phase or "超卖" in phase)):
                groups[gkey].append(entry); matched = True; break
        if not matched and phase:
            groups.setdefault("其他", []).append(entry)

    out = ["\n【📈 趋势三阶段扫描 (Top25)】"]
    for gkey, items in groups.items():
        if items:
            out.append(f"\n  ▶ {gkey} ({len(items)}只):")
            out.extend(items)
    return "\n".join(out)


def _get_trend_candidates(cb):
    """取扫描候选股 → list of (name, code) tuples"""
    import sqlite3 as _sc
    try:
        conn = _sc.connect(_stock_db())
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT name, ts_code FROM lhb_records ORDER BY trade_date DESC LIMIT 30")
        rows = cur.fetchall()
        conn.close()
        cb(f"   → lhb_records 候选 {len(rows)} 只")
        out = []
        for name, tscode in rows:
            if not name or not tscode: continue
            code = tscode.split(".")[0]  # e.g. "601868"
            market = "sh" if code.startswith(("6","9","5")) else "sz"
            out.append((name, market + code))  # 补 sh/sz 前缀
        return out
    except Exception as e:
        cb(f"   ⚠️ 候选获取失败: {e}")
        return []


# -------- 8. 全球市场 --------
def fetch_global(cb):
    import requests as _rq
    gl = [("usDJI","道琼斯"),("usIXIC","纳斯达克"),("usINX","标普500"),
          ("hkHSI","恒生"),("hkHSCEI","国企指数"),("gb_$dji","日经225")]
    cb(f"📡 {len(gl)} 个全球指数...")
    try:
        r = _rq.get(f"https://qt.gtimg.cn/q={','.join(c for c,_ in gl)}", timeout=5)
        by_code = {cp.split("_")[-1]: vp.strip('"').split("~")
                   for line in r.text.strip().split(";") if "=" in line
                   for cp, vp in [line.split("=", 1)]}
        results = []
        for code, name in gl:
            v = by_code.get(code, [])
            if len(v) > 32:
                results.append(f"· {name}: {v[3]} ({v[32]}%)")
                cb(f"✅ {name}")
            else:
                results.append(f"· {name}: (无数据)")
        return "\n".join(results)
    except Exception as e:
        return f"(全球行情失败: {e})"


# -------- 9. 历史对照 --------
def fetch_history(cb):
    db = _stock_db()
    conn = _sqlite3.connect(db); cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    if "crash_rally_events" not in tables:
        conn.close(); return "(无 crash_rally_events)"
    cur.execute("SELECT COUNT(*) FROM crash_rally_events")
    cb(f"✅ crash_rally_events {cur.fetchone()[0]} 条")
    cur.execute(
        "SELECT event_date, event_type, index_name, index_pct, trigger "
        "FROM crash_rally_events ORDER BY event_date DESC LIMIT 5"
    )
    rows = cur.fetchall()
    conn.close()
    out = []
    for row in rows:
        d, etype, idx, pct, trigger = row
        out.append(f"· {d} [{etype}] {idx} {pct}% — {trigger or '-'}")
        cb(f"  → {d} {etype} {idx}")
    return "\n".join(out) if out else "(无历史数据)"


FETCHERS = {
    "indices": fetch_indices, "leader": fetch_leader,
    "sentiment": fetch_sentiment, "crawled": fetch_crawled,
    "lhb_blood": fetch_lhb, "skill_blood": fetch_skill_blood,
    "skill_trend": fetch_skill_trend,
    "global": fetch_global, "history": fetch_history,
}


# ========================================================
#  AI 汇总 + Markdown → 公众号 HTML (含 base64 图片)
# ========================================================

def _generate_markdown(results, template_key, call_ai_fn, skip_flag=None):
    facts = {
        "date": _dt.date.today().isoformat(),
        "market_indices": results.get("indices", "(无)"),
        "leader_stocks": results.get("leader", "(无)"),
        "sentiment_desc": results.get("sentiment", "(无)"),
        "crawled_hot": results.get("crawled", "(无)"),
        "lhb": results.get("lhb_blood", "(无)"),
        "blood_chips": results.get("skill_blood", "(无)"),
        "trend_phases": results.get("skill_trend", "(无)"),
        "global_markets": results.get("global", "(无)"),
        "history_context": results.get("history", "(无)"),
    }
    tpl = PROMPTS.get(template_key, PROMPTS["daily_evening"])
    prompt = tpl.format(**{k: str(v)[:800] for k, v in facts.items()})

    if skip_flag and skip_flag():
        return _fallback_md(facts, template_key)

    if call_ai_fn:
        try:
            # call_ai_model 内部 HTTP 可能阻塞 60s+
            # 用 daemon 线程 + Event 实现 30s 可中断调用
            import threading as _th2
            result_holder = {"val": None, "err": None}
            done_evt = _th2.Event()

            def _ai_thread():
                try:
                    result_holder["val"] = call_ai_fn(prompt, max_tokens=1500)
                except Exception as e:
                    result_holder["err"] = str(e)
                finally:
                    done_evt.set()

            _th2.Thread(target=_ai_thread, daemon=True).start()

            # 等最多 30s, 每秒检查 skip_flag
            t0 = _time.time()
            while not done_evt.is_set():
                done_evt.wait(timeout=1.0)
                if skip_flag and skip_flag():
                    print(f"[📱] 用户跳过 AI (等了 {_time.time()-t0:.0f}s)")
                    return _fallback_md(facts, template_key)
                if _time.time() - t0 > 30:
                    print("[📱] AI 30s 超时, 降级模板稿")
                    return _fallback_md(facts, template_key)

            if result_holder["err"]:
                print(f"[📱] AI 错误: {result_holder['err']}")
                return _fallback_md(facts, template_key)

            result = result_holder["val"]
            if skip_flag and skip_flag():
                return _fallback_md(facts, template_key)
            if isinstance(result, str) and len(result) > 50:
                clean = result.strip()
                if clean.startswith("```"):
                    lines = clean.split("\n")
                    clean = "\n".join(lines[1:])
                    if clean.endswith("```"): clean = clean[:-3]
                return clean.strip()
        except Exception as e:
            print(f"[📱] AI 异常, 降级: {e}")

    return _fallback_md(facts, template_key)


def _fallback_md(facts, template_key):
    d = facts["date"]
    return f"""# 📊 {d} A股日报(模板稿)

## 一、大盘指数
{facts.get('market_indices', '(无)')}

## 二、龙头/涨跌停
{facts.get('leader_stocks', '(无)')}

## 三、情绪周期
{facts.get('sentiment_desc', '(无)')}

## 四、爬取热门
{facts.get('crawled_hot', '(无)')}

## 五、带血筹码 (Skill)
{facts.get('blood_chips', '(无)')}

## 六、趋势三阶段 (Skill)
{facts.get('trend_phases', '(无)')}

## 七、龙虎榜近3日
{facts.get('lhb', '(无)')}

## 八、全球市场
{facts.get('global_markets', '(无)')}

## 九、历史对照
{facts.get('history_context', '(无)')}

## 十、明日展望
⚠️ 模板稿 — 请配置 AI Key 获得智能分析。

---
*自动生成于 stockyidong*"""


def _md_to_wechat_html(md_text):
    """Markdown → 公众号兼容 HTML, 嵌入情绪周期 base64 图片"""
    lines = md_text.split("\n")
    html_parts = []

    # 如果有情绪周期图, 插在合适位置
    sent_b64 = _LAST_SENTIMENT_IMG.get("b64")
    sent_desc = _LAST_SENTIMENT_IMG.get("desc")

    for line in lines:
        line = line.rstrip()
        if not line:
            html_parts.append('<p style="margin:10px 0;"></p>'); continue

        # 遇到情绪周期段 → 插图片
        if sent_b64 and ("情绪周期" in line or "情绪位置" in line or "📊" in line[:10]):
            img_html = (
                f'<div style="margin:16px 0;padding:12px;background:#1a1a2e;border-radius:8px;">'
                f'<img src="data:image/png;base64,{sent_b64}" '
                f'style="max-width:100%;border-radius:6px;display:block;margin:0 auto;">'
                f'<p style="text-align:center;color:#888;font-size:12px;margin-top:8px;">'
                f'🖼️ 情绪周期图 — {sent_desc or ""}</p></div>'
            )
            html_parts.append(img_html)
            sent_b64 = None  # 只插一次

        if line.startswith("# "):
            t = line[2:].strip()
            html_parts.append(f'<h1 style="font-size:22px;font-weight:bold;color:#1a1a2e;text-align:center;margin:20px 0;">{t}</h1>'); continue
        if line.startswith("## "):
            t = line[3:].strip()
            html_parts.append(f'<h2 style="font-size:18px;font-weight:bold;color:#16213e;margin:18px 0 10px;border-left:4px solid #e94560;padding-left:10px;">{t}</h2>'); continue
        if line.startswith("### "):
            t = line[4:].strip()
            html_parts.append(f'<h3 style="font-size:16px;font-weight:bold;color:#0f3460;margin:14px 0 8px;">{t}</h3>'); continue
        if line.strip() == "---":
            html_parts.append('<hr style="border:none;border-top:1px dashed #ccc;margin:20px 0;">'); continue
        if line.startswith("- ") or line.startswith("* ") or line.startswith("· "):
            t = line[2:].strip() if line[:2] in ("- ", "* ") else line[2:].strip()
            html_parts.append(f'<p style="margin:4px 0;padding-left:20px;color:#444;font-size:14px;line-height:1.7;">• {_inline(t)}</p>'); continue
        html_parts.append(f'<p style="margin:8px 0;color:#333;font-size:15px;line-height:1.8;">{_inline(line)}</p>')

    body = "\n".join(html_parts)
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股日报</title>
</head>
<body style="margin:0;padding:20px;background:#f5f5f5;">
<section style="max-width:677px;margin:0 auto;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
{body}</section>
</body>
</html>'''


def _inline(text):
    text = _re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#e94560;">\1</strong>', text)
    text = _re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


# ========================================================
#  GUI — 7 个并行任务 Tab + 汇总 Tab
# ========================================================

def show_wechat_dialog(parent=None, call_ai_fn=None):
    win = _tk.Toplevel(parent) if parent else _tk.Tk()
    win.title("📱 微信日报生成器 (7 源并行)")
    win.geometry("980x850")
    win.configure(bg="#1a1a2e")

    # ===== 顶部: 模板选择 =====
    top = _tk.Frame(win, bg="#1a1a2e"); top.pack(fill=_tk.X, padx=10, pady=10)
    _tk.Label(top, text="📋 模板:", bg="#1a1a2e", fg="#eee", font=("", 11)).pack(side=_tk.LEFT)
    template_var = _tk.StringVar(value="daily")
    cb = _ttk.Combobox(top, textvariable=template_var, state="readonly", width=28,
                      values=list(TEMPLATES.keys()))
    cb.pack(side=_tk.LEFT, padx=6)
    tdesc_lbl = _tk.Label(top, text=TEMPLATES["daily"][1], bg="#1a1a2e", fg="#888", font=("", 10))
    tdesc_lbl.pack(side=_tk.LEFT, padx=8)
    cb.bind("<<ComboboxSelected>>", lambda e: tdesc_lbl.config(
        text=TEMPLATES.get(template_var.get(), ("", "", ""))[1]))

    # ===== Notebook: 9 任务 Tab + 1 汇总 Tab =====
    nb = _ttk.Notebook(win)
    nb.pack(fill=_tk.BOTH, expand=True, padx=10, pady=(0, 5))

    task_ui = {}
    task_states = {k: {"status": "pending", "logs": [], "result": "", "t0": None, "t1": None}
                   for k in TASK_KEYS}

    for key in TASK_KEYS:
        label = TASK_LABELS[key]
        tab = _tk.Frame(nb, bg="#0f0f1a")
        nb.add(tab, text=f"⚪ {label}")

        header = _tk.Frame(tab, bg="#0f0f1a"); header.pack(fill=_tk.X, padx=8, pady=6)
        indicator = _tk.Label(header, text="⚪", bg="#0f0f1a", fg="#555", font=("", 14))
        indicator.pack(side=_tk.LEFT, padx=(0, 8))
        _tk.Label(header, text=label, bg="#0f0f1a", fg="#eee", font=("", 11, "bold")).pack(side=_tk.LEFT)
        tstat_var = _tk.StringVar(value="待执行")
        _tk.Label(header, textvariable=tstat_var, bg="#0f0f1a", fg="#888", font=("", 10)).pack(side=_tk.RIGHT)

        bar = _ttk.Progressbar(header, length=200, mode="determinate")
        bar.pack(side=_tk.RIGHT, padx=10)

        txt = _tk.Text(tab, height=12, bg="#0a0a12", fg="#aaa", font=("Menlo", 10),
                       wrap="word", state=_tk.DISABLED, relief=_tk.FLAT, bd=0)
        txt.pack(fill=_tk.BOTH, expand=True, padx=8, pady=(0, 6))

        # 提前配好颜色 tag
        for c in ["#aaa", "#4ecdc4", "#4CAF50", "#ff9800", "#e94560", "#ffd700"]:
            txt.tag_config(c, foreground=c)

        task_ui[key] = {"tab": tab, "text": txt, "indicator": indicator,
                        "bar": bar, "status_var": tstat_var}

    # 汇总 Tab
    summary_tab = _tk.Frame(nb, bg="#0f0f1a")
    nb.add(summary_tab, text="📝 汇总 (等待 0/7)")
    sum_header = _tk.Frame(summary_tab, bg="#0f0f1a"); sum_header.pack(fill=_tk.X, padx=8, pady=6)
    sum_status_var = _tk.StringVar(value="9 个任务并行采集中...")
    _tk.Label(sum_header, textvariable=sum_status_var, bg="#0f0f1a", fg="#4ecdc4",
              font=("", 11, "bold")).pack(side=_tk.LEFT)
    sum_txt = _tk.Text(summary_tab, bg="#0a0a12", fg="#eee", font=("Menlo", 10),
                       wrap="word", height=22)
    sum_txt.pack(fill=_tk.BOTH, expand=True, padx=8, pady=(0, 6))
    sum_txt.insert("1.0", "(等待 9 个采集任务完成后 AI 自动汇总...)")

    # ===== 底部: 主进度 + 按钮 =====
    bot = _tk.Frame(win, bg="#1a1a2e"); bot.pack(fill=_tk.X, padx=10, pady=8)
    main_bar = _ttk.Progressbar(bot, length=350, mode="determinate")
    main_bar.pack(side=_tk.LEFT, padx=6, fill=_tk.X, expand=True)
    main_pct = _tk.StringVar(value="0%")
    _tk.Label(bot, textvariable=main_pct, bg="#1a1a2e", fg="#4ecdc4",
              font=("", 10, "bold")).pack(side=_tk.LEFT, padx=8)

    gen_btn = _tk.Button(bot, text="🚀 并行采集 + AI 生成", command=lambda: None,
                         bg="#e94560", fg="white", font=("", 11),
                         activebackground="#c73e54", relief=_tk.FLAT, padx=12)
    gen_btn.pack(side=_tk.LEFT, padx=6)
    skip_btn = _tk.Button(bot, text="⏭ 跳过AI", state=_tk.DISABLED,
                          bg="#555", fg="white", font=("", 10), relief=_tk.FLAT)
    skip_btn.pack(side=_tk.LEFT, padx=4)
    save_btn = _tk.Button(bot, text="💾 导出HTML", state=_tk.DISABLED,
                          bg="#0f3460", fg="white", font=("", 10), relief=_tk.FLAT)
    save_btn.pack(side=_tk.LEFT, padx=4)

    # ===== 工具方法 =====

    def _task_log(key, msg, color="#aaa"):
        task_states[key]["logs"].append(msg)
        ui = task_ui[key]
        win.after(0, lambda u=ui, m=msg, c=color: _append_text(u["text"], m, c))

    def _append_text(txt_widget, msg, color="#aaa"):
        txt_widget.config(state=_tk.NORMAL)
        txt_widget.insert(_tk.END, msg + "\n", color)
        txt_widget.see(_tk.END)
        txt_widget.config(state=_tk.DISABLED)

    def _update_task_ui(key, status, detail="", pct=0):
        ui = task_ui[key]; label = TASK_LABELS[key]
        if status == "running":
            ui["indicator"].config(text="🔵", fg="#4ecdc4")
            ui["status_var"].set(f"进行中 {detail}")
            nb.tab(ui["tab"], text=f"🔵 {label}")
        elif status == "done":
            ui["indicator"].config(text="✅", fg="#4CAF50")
            ui["status_var"].set(f"完成 {detail}")
            nb.tab(ui["tab"], text=f"✅ {label}")
        elif status == "failed":
            ui["indicator"].config(text="❌", fg="#e94560")
            ui["status_var"].set(f"失败 {detail}")
            nb.tab(ui["tab"], text=f"❌ {label}")
        ui["bar"]["value"] = pct

    def _update_main():
        done_count = sum(1 for k in TASK_KEYS if task_states[k]["status"] in ("done", "failed"))
        base_pct = done_count / len(TASK_KEYS) * 65
        if task_states.get("_ai") == "running":
            pct = base_pct + 15
        elif task_states.get("_done"):
            pct = 100
        else:
            pct = base_pct
        main_bar["value"] = pct
        main_pct.set(f"{int(pct)}%")
        nb.tab(summary_tab, text=f"📝 汇总 ({done_count}/{len(TASK_KEYS)} 完成)")

    skip_flag = {"canceled": False}
    result_md = {"content": "", "html": ""}

    # ===== 主执行 =====

    def _run_parallel():
        results = {}
        ts_all = _time.time()

        with _cf.ThreadPoolExecutor(max_workers=9) as pool:
            futures = {}
            for key in TASK_KEYS:
                task_states[key]["status"] = "running"
                task_states[key]["t0"] = _time.time()
                win.after(0, lambda k=key: _update_task_ui(k, "running"))
                win.after(0, _update_main)

                def make_cb(k=key):
                    def cb(msg): _task_log(k, msg)
                    return cb

                fut = pool.submit(_run_one, key, FETCHERS[key], make_cb())
                futures[fut] = key

            for fut in _cf.as_completed(futures):
                key = futures[fut]
                try:
                    result = fut.result()
                    results[key] = result
                    task_states[key]["status"] = "done"
                    task_states[key]["result"] = result
                    task_states[key]["t1"] = _time.time()
                    dt = task_states[key]["t1"] - task_states[key]["t0"]
                    _task_log(key, f"⏱ 完成 ({dt:.1f}s)", "#4CAF50")
                    win.after(0, lambda k=key, d=dt: _update_task_ui(k, "done", f"{d:.1f}s", 100))
                except Exception as e:
                    results[key] = f"(失败: {e})"
                    task_states[key]["status"] = "failed"
                    _task_log(key, f"❌ 失败: {e}", "#e94560")
                    win.after(0, lambda k=key: _update_task_ui(k, "failed", str(e)[:30]))
                win.after(0, _update_main)

        # AI 汇总
        task_states["_ai"] = "running"
        win.after(0, lambda: sum_status_var.set("🤖 AI 汇总 9 任务..."))
        win.after(0, _update_main)

        ai_i = {"i": 0}
        def _ai_tick():
            ai_i["i"] += 1
            win.after(0, lambda: sum_status_var.set(f"🤖 AI 汇总... {ai_i['i']}s (可⏭跳过)"))
            if task_states.get("_ai") == "running":
                win.after(1000, _ai_tick)
        win.after(1000, _ai_tick)

        t_ai0 = _time.time()
        md = _generate_markdown(results, template_var.get(), call_ai_fn,
                                 skip_flag=lambda: skip_flag["canceled"])
        t_ai = _time.time() - t_ai0
        task_states["_ai"] = "done"

        html = _md_to_wechat_html(md)
        task_states["_done"] = True
        t_total = _time.time() - ts_all

        # 汇总耗时
        summary_lines = ["📊 各任务耗时:\n"]
        for key in TASK_KEYS:
            s = task_states[key]
            if s["t0"] and s["t1"]:
                summary_lines.append(f"  {TASK_LABELS[key]}: {s['t1']-s['t0']:.1f}s ✅")
            else:
                summary_lines.append(f"  {TASK_LABELS[key]}: ❌")
        summary_lines.append(f"\n🤖 AI 汇总: {t_ai:.1f}s")
        summary_lines.append(f"🖼️ 情绪周期图: {'包含' if _LAST_SENTIMENT_IMG.get('b64') else '无'}")
        summary_lines.append(f"🎉 总耗时: {t_total:.1f}s")
        header_text = "\n".join(summary_lines) + "\n" + "="*50 + "\n\n"

        win.after(0, lambda: sum_txt.delete("1.0", _tk.END))
        win.after(0, lambda h=header_text, m=md: sum_txt.insert("1.0", h + m))
        win.after(0, lambda: sum_status_var.set(f"✅ 全部完成! 总耗时 {t_total:.1f}s | 💾导出"))
        win.after(0, _update_main)
        win.after(0, lambda: main_bar.__setitem__("value", 100))
        win.after(0, lambda: main_pct.set("100%"))

        result_md["content"] = md
        result_md["html"] = html

        def _enable():
            gen_btn.config(state=_tk.NORMAL, text="🎨 重新采集")
            save_btn.config(state=_tk.NORMAL)
            skip_btn.config(state=_tk.DISABLED)
        win.after(0, _enable)

    def _run_one(key, fetcher, cb):
        cb(f"🚀 启动 {TASK_LABELS[key]}...")
        t0 = _time.time()
        try:
            result = fetcher(cb)
            cb(f"⏱ 完成 ({_time.time()-t0:.1f}s)")
            return result
        except Exception as e:
            cb(f"❌ 异常: {e}")
            raise

    # ===== 按钮 =====

    def _on_generate():
        global _LAST_SENTIMENT_IMG
        _LAST_SENTIMENT_IMG = {"b64": None, "desc": None}
        for key in TASK_KEYS:
            task_states[key] = {"status": "pending", "logs": [], "result": "", "t0": None, "t1": None}
            ui = task_ui[key]
            ui["text"].config(state=_tk.NORMAL); ui["text"].delete("1.0", _tk.END); ui["text"].config(state=_tk.DISABLED)
            _update_task_ui(key, "pending")
        for k in ("_ai", "_done"): task_states.pop(k, None)
        skip_flag["canceled"] = False
        gen_btn.config(state=_tk.DISABLED, text="⏳ 采集中...")
        skip_btn.config(state=_tk.NORMAL)
        save_btn.config(state=_tk.DISABLED)
        sum_txt.delete("1.0", _tk.END)
        sum_txt.insert("1.0", "(9 个任务并行采集中...)")
        sum_status_var.set("🚀 启动 9 个并行任务!")
        win.after(0, _update_main)
        _th.Thread(target=_run_parallel, daemon=True).start()

    def _on_skip():
        skip_flag["canceled"] = True
        sum_status_var.set("⏭ 跳过 AI, 用模板汇总")

    def _on_save_html():
        if not result_md["html"]: return
        import tkinter.filedialog as _fd
        path = _fd.asksaveasfilename(
            defaultextension=".html",
            initialfile=f"wechat_{template_var.get()}_{_dt.date.today()}.html",
            filetypes=[("HTML", "*.html")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(result_md["html"])
            _mb.showinfo("导出成功", f"已保存:\n{path}\n\n(可用浏览器打开预览, 复制内容到公众号编辑器)")

    gen_btn.config(command=_on_generate)
    skip_btn.config(command=_on_skip)
    save_btn.config(command=_on_save_html)

    win.focus_set()
    return win


if __name__ == "__main__":
    show_wechat_dialog()

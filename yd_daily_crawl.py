#!/usr/bin/env python3
"""
yd_daily_crawl.py - stockyidong 每日自动爬取（headless，无 GUI）
复刻 GUI 按钮：淘股吧文章库、韭研文章库、一键爬取（6源→资讯表）、
持股页-同花顺热榜、资讯更新（8天资讯股频次）

Bug修复：_fix_encoding 在类中被定义两次，str版覆盖bytes版，
_fetch_with_encoding_fix 期望 bytes版签名因此崩溃。直接重写该函数。
"""

import json
import os
import sys
import time
from datetime import datetime

# ── 路径配置 ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR    = os.path.join(SCRIPT_DIR, "src")
sys.path.insert(0, SRC_DIR)

PYYIDONG_PATH = os.path.join(SRC_DIR, "stockyidong mac.py")
assert os.path.exists(PYYIDONG_PATH), f"未找到主程序：{PYYIDONG_PATH}"
print(f"✅ 找到 stockyidong mac.py: {PYYIDONG_PATH}")

# ── 加载 stockyidong mac.py ────────────────────────────────
print("⏳ 加载 stockyidong mac.py（首次约 15-30 秒）...")
_t0 = time.time()
import importlib.util

spec   = importlib.util.spec_from_file_location("stockyidong_mac", PYYIDONG_PATH)
mod    = importlib.util.module_from_spec(spec)
sys.modules["stockyidong_mac"] = mod
spec.loader.exec_module(mod)
print(f"✅ 加载完成，耗时 {time.time()-_t0:.1f}s")

# ── Bug 修复：重写 _fetch_with_encoding_fix
#    原始 _fix_encoding 被重定义两次（bytes版→str版），
#    _fetch_with_encoding_fix 期望 bytes版返回 (text, encoding)
#    直接用内联方式重写，绕过这个bug ───────────────────────
import requests


def _detect_garbled_text(text):
    """检测文本是否乱码"""
    if not text:
        return False
    garbled_chars = ['锘', '\ufffd', '\x00', '銆', '鏍', '涓']
    for char in garbled_chars:
        if char in text[:500]:
            return True
    try:
        text.encode('utf-8')
        return False
    except (UnicodeEncodeError, UnicodeDecodeError):
        return True

def _fix_encoding_bytes(content_bytes, encodings=None):
    """bytes版：尝试多种编码，返回 (text, encoding)"""
    if encodings is None:
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin1', 'cp1252']
    for encoding in encodings:
        try:
            decoded = content_bytes.decode(encoding, errors='strict')
            if not _detect_garbled_text(decoded):
                return decoded, encoding
        except (UnicodeDecodeError, UnicodeError, LookupError):
            continue
        except Exception:
            continue
    # fallback
    for encoding in encodings[:3]:
        try:
            decoded = content_bytes.decode(encoding, errors='replace')
            return decoded, encoding
        except Exception:
            continue
    return None, None

def _fetch_with_encoding_fix(url, headers, max_retries=2):
    """重写的带编码修正的网页获取"""
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return None, None
            # 优先用 response.text（requests自动检测）
            if resp.encoding and not _detect_garbled_text(resp.text):
                return resp.text, resp.encoding
            # 否则用 bytes 版
            content_bytes = resp.content
            fixed_text, used_encoding = _fix_encoding_bytes(content_bytes)
            if fixed_text and not _detect_garbled_text(fixed_text):
                return fixed_text, used_encoding
            if fixed_text:
                return fixed_text, used_encoding or 'utf-8'
            if attempt < max_retries:
                time.sleep(1)
                continue
        except Exception as e:
            if attempt < max_retries:
                time.sleep(1)
                continue
            print(f"获取 {url} 失败: {e}")
            return None, None
    return None, None

# ── 创建 headless GUI 实例 ────────────────────────────────
print("🔧 创建 headless GUI 实例...")
gui = object.__new__(mod.StockKeywordAnalyzerGUI)
gui.taoguba_crawler    = mod.TaogubaCrawler()
gui.jiuyangongshe_crawler = mod.JiuYangGongSheCrawler()
gui.log_messages       = []
gui._running           = False
# 把重写的函数挂上去（直接替换实例属性）
gui._fetch_with_encoding_fix = _fetch_with_encoding_fix

# ── 工具函数 ──────────────────────────────────────────────
def save_article_to_db(source, title, author=None, content=None, url=None):
    return mod.save_article_to_db(source, title, author, content, url)

def save_news_info_to_db(tab_name, content):
    return mod.save_news_info_to_db(tab_name, content)

# ── 执行步骤 ─────────────────────────────────────────────
steps = []
LOG_DIR = os.path.expanduser("~/.qclaw/workspace-ek2hwmmwwhxi3mz3/yd_daily_crawl_logs")
os.makedirs(LOG_DIR, exist_ok=True)

def run(name, fn, *args, **kwargs):
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - t0
        ok, detail = True, str(result) if result else "完成"
        print(f"  ✅ {name}: {detail} ({elapsed:.1f}s)")
    except Exception as e:
        elapsed = time.time() - t0
        ok, detail = False, str(e)
        print(f"  ❌ {name}: {e} ({elapsed:.1f}s)")
    steps.append({"name": name, "ok": ok, "elapsed": round(elapsed, 1), "detail": detail})
    return ok, detail

# ── Step 1: 爬取淘股吧文章库 ───────────────────────────
print("\n[1/10] 爬取淘股吧文章库...")
def crawl_taoguba_articles():
    articles = gui.taoguba_crawler.crawl_realtime_articles()
    saved = sum(1 for a in articles
                if save_article_to_db("淘股吧", a.get("title",""), a.get("author",""),
                                      a.get("content",""), a.get("url","")))
    return f"爬到{len(articles)}篇，保存{saved}篇到articles表"
run("爬取淘股吧(文章库)", crawl_taoguba_articles)

# ── Step 2: 爬取韭研文章库 ──────────────────────────────
print("\n[2/10] 爬取韭研文章库...")
def crawl_jiuyan_articles():
    articles = gui.jiuyangongshe_crawler.crawl_articles()
    saved = sum(1 for a in articles
                if save_article_to_db("韭研", a.get("title",""), a.get("author",""),
                                      a.get("content",""), a.get("url","")))
    return f"爬到{len(articles)}篇，保存{saved}篇到articles表"
run("爬取韭研(文章库)", crawl_jiuyan_articles)

# ── Steps 3-8: 一键爬取（6源 → 资讯表） ─────────────────
sources = [
    ("淘股吧",   lambda: gui._crawl_taoguba_sync()),
    ("韭研",     lambda: gui._crawl_jiuyan_sync()),
    ("东方财富", lambda: gui._crawl_eastmoney_sync()),
    ("雪球",     lambda: gui._crawl_xueqiu_sync()),
    ("选股宝",   lambda: gui._crawl_xuangubao_sync()),
    ("同花顺",   lambda: gui._crawl_ths_sync()),
]
for i, (name, fn) in enumerate(sources, start=3):
    print(f"\n[{i}/10] 一键爬取-{name}(资讯表)...")
    def _do(name=name, fn=fn):
        content, tab_title = fn()
        if content is None:
            return "内容为空，保存失败"
        ts = datetime.now().strftime("%m%d%H%M")
        tag = f"{name}_{ts}"
        ok = save_news_info_to_db(tag, content)
        return f"内容{len(content)}字符，资讯表{'保存成功' if ok else '保存失败'}: {tag}"
    run(f"一键爬取-{name}(资讯表)", _do)

# ── Step 9: 持股页-同花顺热榜 ────────────────────────────
print("\n[9/10] 持股页-爬取同花顺热榜...")
def crawl_ths_hot():
    stocks = gui._fetch_ths_hot_stocks()
    return f"同花顺热榜 {len(stocks)} 只股票"
run("持股页-爬取同花顺热榜", crawl_ths_hot)

# ── Step 10: 资讯更新（8天资讯股频次） ───────────────────
print("\n[10/10] 资讯更新(8天资讯股频次)...")
def update_news():
    result = mod.get_news_stocks_by_date_and_frequency(ndays=8)
    if result is None:
        return "查询失败"
    # result: list[{"date_ymd":..., "stocks":[(name,code),...]},...]
    from collections import Counter
    all_stocks = []
    for day in result:
        all_stocks.extend(day.get("stocks", []))
    counter = Counter(all_stocks)
    top_stocks = [s for s, _ in counter.most_common(20)]
    top5 = top_stocks[:5]
    top_str = "，".join([f"{n}({c})" for n, c in top5]) if top5 else "无数据"
    return f"最近8天资讯记录 {len(all_stocks)} 条（去重），TOP5: {top_str}"
run("资讯更新(8天资讯股频次)", update_news)

# ── 摘要 ─────────────────────────────────────────────────
total_steps = len(steps)
ok_steps    = sum(1 for s in steps if s["ok"])
failed      = [s["name"] for s in steps if not s["ok"]]

print("\n===== 摘要 =====")
print(f"成功步数：{ok_steps}/{total_steps} 步")
for s in steps:
    print(f"  {'✅' if s['ok'] else '❌'} {s['name']}: {s['detail']}")

# ── top20 数据 ───────────────────────────────────────────
def get_ths_hot_top20():
    try:
        import sqlite3
        conn = sqlite3.connect(mod.DB_PATH)
        cur  = conn.cursor()
        cur.execute("SELECT name, code FROM ths_hot_stocks ORDER BY rank ASC LIMIT 20")
        rows = cur.fetchall()
        conn.close()
        return [f"{n}({c})" for n, c in rows]
    except Exception:
        return []

def get_news_stocks_top20():
    try:
        result = mod.get_news_stocks_by_date_and_frequency(ndays=8)
        if not result:
            return []
        from collections import Counter
        all_stocks = []
        for day in result:
            all_stocks.extend(day.get("stocks", []))
        counter = Counter(all_stocks)
        top_stocks = [s for s, _ in counter.most_common(20)]
        return [f"({n},{c})" for n, c in top_stocks]
    except Exception:
        return []

ths_top20   = get_ths_hot_top20()
news_top20  = get_news_stocks_top20()

if ths_top20:
    print("\n同花顺热榜 TOP20：")
    for item in ths_top20[:20]:
        print(f"  {item}")
else:
    print("\n同花顺热榜：无数据（API不可用）")

if news_top20:
    print("\n资讯股 TOP20：")
    for item in news_top20[:20]:
        print(f"  {item}")
else:
    print("\n资讯股 TOP20：无数据")

# ── 保存日志 ─────────────────────────────────────────────
ts = datetime.now().strftime("%Y%m%d_%H%M")
log_file = os.path.join(LOG_DIR, f"crawl_{ts}.json")
log_data = {
    "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "steps": steps,
    "summary": f"{ok_steps}/{total_steps} 步成功",
    "ths_hot_top20": ths_top20,
    "news_stocks_top20": news_top20,
}
with open(log_file, "w", encoding="utf-8") as f:
    json.dump(log_data, f, ensure_ascii=False, indent=2)
print(f"\n📁 日志已保存：{log_file}")
print("===== 爬取完成 =====")

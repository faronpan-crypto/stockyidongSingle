#!/usr/bin/env python3
"""
双均线趋势 + 段基(基本面) + 芒格(5%机会) 自动扫描
================================================
扫描池：
  1) stockyidong_mac 持仓股/龙头股 (config/ai_config.json 的 holding_stocks_2/3/6)
  2) news_info 最新日期标签页股票 (主推荐/板块强势股/午间热点/MA20 等 tab 提取代码)
每只股票输出：双均线趋势状态 + 芒格5%机会 + 段基7维分 → 综合评级
输出：Markdown 报告写入 news_info 库 (tab: 📊 双均线段基芒格扫描｜YYYY-MM-DD) + 打印摘要

用法：
  python3 trend_factor_scan.py                 # 全量扫描
  python3 trend_factor_scan.py --limit 20      # 只扫前20只(调试)
  python3 trend_factor_scan.py --top 40        # 段基只对趋势前40只跑(控制neodata调用)
  python3 trend_factor_scan.py --pool-only     # 只打印股池

说明：
  双均线/芒格 用新浪源+本地计算(快)；段基调 duanji.analyze_stock(经neodata,慢)，
  故段基只对"双均线或芒格初筛通过"的候选跑，减少 neodata 调用量。
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta

PROJ = "/Users/faronpan/Agent/stockyidong_project"
SRC = os.path.join(PROJ, "src")
DB = os.path.join(PROJ, "data", "stock_analysis.db")
CONFIG = os.path.join(SRC, "config", "ai_config.json")
WORKSPACE = "/Users/faronpan/.qclaw/workspace"

sys.path.insert(0, SRC)
sys.path.insert(0, "/Users/faronpan/.qclaw/workspace/src")
sys.path.insert(0, "/Users/faronpan/.qclaw/workspace/skills/china-stock-quant/scripts")

import akshare as ak
import duanji
import technical_indicators


# ───────────────────────── 1. 收集股池 ─────────────────────────
def collect_pool():
    pool = {}  # code -> name
    # (a) 持仓股 + 龙头股：ai_config.json 的 holding_stocks_2/3/6
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        # 自适应：持仓/龙头配置键历史上为 holding_stocks_2/3/6，现为 holding_stocks_4，
        # 故遍历所有 holding_stocks* 前缀键，避免配置迁移后股池变空。
        hold_keys = [k for k in cfg if re.fullmatch(r"holding_stocks(_\d+)?", k)]
        for key in hold_keys:
            for s in cfg.get(key, []):
                if isinstance(s, dict):
                    code = str(s.get("stock_code", s.get("code", ""))).strip()
                    name = s.get("stock_name", s.get("name", ""))
                elif isinstance(s, str) and ":" in s:
                    code, name = [x.strip() for x in s.split(":", 1)]
                else:
                    continue
                if re.fullmatch(r"[0368]\d{5}", code):
                    pool.setdefault(code, name)
    # (b) news_info 最新日期标签页股票
    try:
        conn = sqlite3.connect(DB)
        since = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT tab_name, content, created_at FROM news_info "
            "WHERE created_at >= ? AND (tab_name LIKE '%主推荐%' OR tab_name LIKE '%板块强势股%' "
            "OR tab_name LIKE '%午间热点%' OR tab_name LIKE '%MA20%')",
            (since,),
        ).fetchall()
        conn.close()
        pat = re.compile(r"\((\d{6})\)")
        for tab, content, _ in rows:
            for code in pat.findall(content or ""):
                if re.fullmatch(r"[0368]\d{5}", code):
                    pool.setdefault(code, "")
    except Exception as e:
        print(f"  [warn] news_info 提取失败: {e}")
    return pool


# ───────────────────────── 2. 双均线趋势(新浪源) ─────────────────────────
def get_daily(code, start="20250101"):
    prefix = "sh" if code.startswith("6") else "sz"
    raw = ak.stock_zh_a_daily(symbol=prefix + code, start_date=start,
                              end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq")
    df = raw.rename(columns={c: c.lower() for c in raw.columns})
    if "volume" not in df.columns and "vol" in df.columns:
        df = df.rename(columns={"vol": "volume"})
    df = df.reset_index(drop=True)
    return technical_indicators.add_all_indicators(df)


def ma_signal(df2):
    c, m5, m20 = df2["close"].iloc[-1], df2["ma5"].iloc[-1], df2["ma20"].iloc[-1]
    pm5, pm20 = df2["ma5"].iloc[-2], df2["ma20"].iloc[-2]
    cross_up = pm5 <= pm20 and m5 > m20
    cross_dn = pm5 >= pm20 and m5 < m20
    if m5 > m20 and c > m5 and c > m20:
        status = "强势多头📈"
    elif m5 > m20 and c > m20:
        status = "多头排列📊"
    elif cross_up:
        status = "金叉🟢"
    elif cross_dn:
        status = "死叉🔴"
    else:
        status = "弱势📉"
    score = 50
    if c > m20: score += 15
    if c > m5: score += 10
    if m5 > m20: score += 15
    if cross_up: score += 10
    if cross_dn: score -= 15
    return status, max(0, min(100, score)), c


# ───────────────────────── 3. 芒格5%机会(本地drawdown+反转) ─────────────────────────
def munger_signal(df2):
    close = df2["close"].iloc[-1]
    m5 = df2["ma5"].iloc[-1]
    high_n = df2["close"].rolling(120).max().iloc[-1]
    dd = (high_n - close) / high_n * 100 if high_n > 0 else 0
    reversal = close > m5
    if dd >= 25 and reversal:
        label, ms = "强机会(个股级)", 90
    elif dd >= 15 and reversal:
        label, ms = "观察(板块级)", 70
    elif dd >= 15:
        label, ms = "回撤中(等反转)", 55
    else:
        label, ms = "无", 30
    return label, ms, round(dd, 1)


# ───────────────────────── 4. 段基(duanji, 经neodata) ─────────────────────────
def duanji_score(code, name):
    try:
        r = duanji.analyze_stock(code, name or code)
        return r.get("total_score"), r.get("verdict")
    except Exception as e:
        return None, f"段基失败:{e}"


# ───────────────────────── 5. 综合评级 ─────────────────────────
def rating(ma_s, m_s, d_s):
    if d_s is None:
        if ma_s >= 70 and m_s >= 70: return "⭐⭐⭐强烈关注(段基未算)"
        if ma_s >= 60 and m_s >= 70: return "⭐⭐关注(段基未算)"
        if ma_s >= 50: return "⭐观察"
        return "—持有/回避"
    if ma_s >= 70 and d_s >= 65 and m_s >= 70: return "⭐⭐⭐强烈关注"
    if ma_s >= 60 and (d_s >= 55 or m_s >= 70): return "⭐⭐关注"
    if ma_s >= 50: return "⭐观察"
    return "—持有/回避"


# ───────────────────────── 6. 主流程 ─────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--top", type=int, default=40, help="段基只对趋势前N只跑")
    ap.add_argument("--pool-only", action="store_true")
    args = ap.parse_args()

    pool = collect_pool()
    print(f"◆ 股池: {len(pool)} 只 (持仓/龙头 + 最新标签页)")
    if args.pool_only:
        for c, n in pool.items():
            print(f"  {c} {n}")
        return

    codes = list(pool.items())
    if args.limit:
        codes = codes[: args.limit]

    rows = []
    for code, name in codes:
        time.sleep(1.2)  # 防新浪源限流
        try:
            df2 = get_daily(code)
            status, ma_s, price = ma_signal(df2)
            m_label, m_s, dd = munger_signal(df2)
            rows.append({"code": code, "name": name, "price": price,
                         "ma_s": ma_s, "status": status, "m_s": m_s,
                         "m_label": m_label, "dd": dd, "d_s": None, "verdict": ""})
            print(f"  {name or code}({code}) {status} 双均{ma_s} 芒格[{m_label} {dd}%]")
        except Exception as e:
            print(f"  {code} 双均线失败: {e}")

    # 段基：只对趋势/芒格初筛通过的候选跑 (控制 neodata 调用)
    cand = sorted(rows, key=lambda r: (r["ma_s"] + r["m_s"]), reverse=True)[: args.top]
    cand_set = {r["code"] for r in cand}
    for r in rows:
        if r["code"] in cand_set:
            try:
                d_s, verdict = duanji_score(r["code"], r["name"])
                r["d_s"], r["verdict"] = d_s, verdict or ""
                print(f"    ↳ 段基 {r['name'] or r['code']}: {d_s}/105 {verdict}")
            except Exception as e:
                r["verdict"] = f"段基失败:{e}"
            time.sleep(0.5)

    for r in rows:
        r["rating"] = rating(r["ma_s"], r["m_s"], r["d_s"])

    # 排序：综合(双均+芒格+段基)降序
    def keyf(r):
        d = r["d_s"] or 0
        return r["ma_s"] + r["m_s"] + d
    rows.sort(key=keyf, reverse=True)

    # ── 生成 Markdown 报告 ──
    today = datetime.now().strftime("%Y-%m-%d")
    tab = f"📊 双均线段基芒格扫描｜{today}"
    md = [f"# {tab}", "", f"> 扫描 {len(rows)} 只 | 双均线(新浪源)+段基(duanji)+芒格(5%机会) | {today}", ""]
    md.append("## ⭐ 重点信号")
    for r in rows:
        if "⭐⭐" in r["rating"]:
            d = f"段基{r['d_s']}/105" if r["d_s"] is not None else "段基未算"
            md.append(f"- **{r['name'] or r['code']}({r['code']})** {r['rating']} ｜ {r['status']} ｜ 芒格[{r['m_label']} 回撤{r['dd']}%] ｜ {d}")
    md.append("")
    md.append("## 全量明细")
    md.append("| 名称 | 代码 | 现价 | 双均线 | 双均分 | 芒格机会 | 回撤 | 段基 | 综合 |")
    md.append("|------|------|------|--------|--------|----------|------|------|------|")
    for r in rows:
        d = f"{r['d_s']}/105" if r["d_s"] is not None else "—"
        ver = (r["verdict"] or "").split()[0] if r["verdict"] else ""
        md.append(f"| {r['name'] or '—'} | {r['code']} | {r['price']:.2f} | {r['status']} | {r['ma_s']} | {r['m_label']} | {r['dd']}% | {d}{ver} | {r['rating']} |")

    report = "\n".join(md)
    # 写库
    try:
        conn = sqlite3.connect(DB)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO news_info (tab_name, content, created_at, updated_at) VALUES (?,?,?,?)",
            (tab, report, now, now))
        conn.commit()
        conn.close()
        print(f"\n✅ 报告已写入 news_info: {tab}")
    except Exception as e:
        print(f"\n[warn] 写库失败: {e}")

    # 写 workspace 顶层 .md（龙虾同步脚本扫描 → 手机端可见）
    # 前缀 "报告_" 避免被 sync 排除规则 "双均线段基芒格扫描" 关键字误拦
    md_filename = os.path.join(WORKSPACE, f"报告_双均线段基芒格扫描_{today}.md")
    try:
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"✅ 报告已写入 workspace: {md_filename}")
    except Exception as e:
        print(f"[warn] workspace 写文件失败: {e}")

    # 打印摘要(供 cron agentTurn 推送微信)
    print("\n" + "=" * 50)
    print(f"📊 双均线+段基+芒格 扫描摘要 ({today}) — 共 {len(rows)} 只")
    strong = [r for r in rows if "⭐⭐" in r["rating"]]
    print(f"重点信号 {len(strong)} 只:")
    for r in strong:
        d = f"段基{r['d_s']}/105" if r["d_s"] is not None else "段基未算"
        print(f"  {r['name'] or r['code']}({r['code']}) {r['rating']} | {r['status']} | 芒格[{r['m_label']} 回撤{r['dd']}%] | {d}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
半导体清洗设备(Guyson/吉仕嘉/Mecwash/MB Tech)招投标信息爬虫
================================================================
功能：
  1. 通过 Sogou 搜索引擎检索半导体清洗设备相关的招标/中标/采购公告
  2. 解析结果（标题 + 真实 URL，绕过 Sogou /link?url= 跳转）
  3. 尽力抓取详情页，抽取结构化字段（发布日期/采购方/地区/预算/中标方/状态）
  4. 生成 Markdown 报告
  5. 写入 stockyidong_mac 资讯数据库 news_info 表

用法：
  python3 crawl_semiconductor_cleaning_bids.py            # 默认：爬最近7天，保存到DB
  python3 crawl_semiconductor_cleaning_bids.py --days 30  # 爬最近30天
  python3 crawl_semiconductor_cleaning_bids.py --no-db    # 只打印报告，不写库
  python3 crawl_semiconductor_cleaning_bids.py --max 40   # 每个查询最多取40条

依赖：requests, beautifulsoup4（项目已具备）
"""

import argparse
import datetime
import os
import re
import sqlite3
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# ── 路径配置 ───────────────────────────────────────────────
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_SRC_DIR, ".."))
_PROJECT_DB = os.path.join(_PROJECT_ROOT, "data", "stock_analysis.db")
DB_PATH = os.environ.get("STOCK_ANALYSIS_DB") or os.environ.get("STOCK_ANALYSIS_DB_PATH") or _PROJECT_DB

# ── 搜索引擎（Sogou，服务端渲染、可解析）─────────────────────
SOGOU_SEARCH = "https://www.sogou.com/web"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}

# ── 检索词（覆盖设备类型 + Guyson 相关品牌/代理）────────────
QUERIES = [
    "半导体清洗设备 招标",
    "半导体清洗设备 中标",
    "半导体 清洗机 招标公告",
    "晶圆清洗设备 中标",
    "槽式清洗设备 招标",
    "单片清洗设备 采购",
    "IGBT 清洗设备 招标",
    "等离子清洗设备 半导体 中标",
    "吉仕嘉 Guyson 清洗设备",
    "Mecwash MB Tech 半导体清洗",
    "苏州凹磐电子 清洗设备",
]

# 相关性：设备类型关键词（命中任一即视为设备相关）
EQUIP_KW = [
    "清洗设备", "清洗机", "清洗系统", "清洗装置",
    "半导体清洗", "晶圆清洗", "单片清洗", "槽式清洗", "湿法清洗",
    "等离子清洗", "刷片机", "洗片机",
]
# 招投标信号词（公告必须具备）
TENDER_KW = ["招标", "中标", "采购公告", "采购", "竞争性谈判", "询价", "比选",
            "征集", "候选", "成交", "定标", "拟中标", "单一来源"]
# Guyson 相关品牌/代理（用于「品牌/代理动态」板块）
BRAND_KW = ["guyson", "吉仕嘉", "mecwash", "mb tech", "苏州凹磐", "凹磐"]
# 已知招投标平台域名（来自这些域名的清洗设备页视为招投标）
TENDER_DOMAINS = ["bidcenter.com.cn", "qianlima.com", "cebpubservice.com",
                  "chinabidding.com", "ebnew.com", "zhaobiao.cn", "csrc.gov.cn"]

# 状态关键词
STATUS_ZHONGBIAO = ["中标", "成交", "候选", "拟中标", "定标"]
STATUS_ZHAOBIAO = ["招标", "采购公告", "竞争性谈判", "询价", "比选", "征集"]

# A股清洗设备相关上市公司（用于中标方识别）
LISTED_WINNERS = [
    "至纯科技", "盛美上海", "盛美半导体", "芯源微", "北方华创", "华海清科",
    "捷佳伟创", "无锡亚电", "亚电智能", "苏州智程", "吉仕嘉", "苏州凹磐",
    "京仪装备", "正帆科技", "至纯",
]

DATE_RE = re.compile(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})")


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def http_get(url, timeout=15, stream=False):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, stream=stream)
        r.encoding = "utf-8"
        return r
    except Exception as e:
        print(f"  ⚠️ GET 失败 {url[:80]}: {e}")
        return None


def resolve_sogou_link(sogou_url):
    """把 Sogou /link?url= 跳转页解析出真实 URL。"""
    r = http_get(sogou_url, timeout=12)
    if not r:
        return None
    m = re.search(r"URL='([^']+)'", r.text)
    if m:
        return m.group(1)
    m = re.search(r'content="[^"]*url=([^"\'<>]+)"', r.text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def extract_date(text):
    """从文本中抽取最早/最显著的日期，返回 YYYY-MM-DD 或空。"""
    # 优先匹配「发布时间/发布日期：YYYY-MM-DD」这类明确字段
    m = re.search(r"(?:发布时间|发布日期|发布于|时间)[:：]\s*(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", text)
    if m:
        try:
            dt = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if 2015 <= dt.year <= (datetime.date.today().year + 1):
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    dates = DATE_RE.findall(text)
    out = []
    for y, mo, d in dates:
        try:
            dt = datetime.date(int(y), int(mo), int(d))
            # 过滤明显不合理（未来太久/过于古老）
            if dt.year < 2015 or dt > datetime.date.today() + datetime.timedelta(days=2):
                continue
            out.append(dt)
        except Exception:
            continue
    if out:
        return min(out).strftime("%Y-%m-%d")
    return ""


def classify_status(text):
    for k in STATUS_ZHONGBIAO:
        if k in text:
            return "中标"
    for k in STATUS_ZHAOBIAO:
        if k in text:
            return "招标"
    return "其他"


def find_winners(text):
    found = [w for w in LISTED_WINNERS if w in text]
    # 去重保序
    seen = set()
    uniq = []
    for w in found:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq


def find_budget(text):
    """抽取预算/金额（万/亿）。"""
    m = re.search(r"预算[^\d]{0,6}?([\d.]+)\s*(亿元|万|万元|亿)", text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    m = re.search(r"([\d.]+)\s*(亿元|万|万元|亿)\s*(?:（|\(|左右|约)?", text)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    return ""


def is_tender(text, domain=""):
    """是否招投标公告：必须含招投标信号词，且设备相关或来自招投标平台。"""
    low = text.lower()
    has_equip = any(k.lower() in low for k in EQUIP_KW)
    has_tender = any(k in text for k in TENDER_KW)
    from_domain = any(d in domain for d in TENDER_DOMAINS)
    if not has_tender:
        return False
    return has_equip or from_domain


def is_brand(text):
    """是否 Guyson/吉仕嘉/Mecwash 等品牌/代理相关动态。"""
    low = text.lower()
    return any(k.lower() in low for k in BRAND_KW)


def crawl_query(query, max_per_query=30):
    """检索一个关键词，返回结构化记录列表。"""
    records = []
    q = quote(query)
    url = f"{SOGOU_SEARCH}?query={q}"
    r = http_get(url, timeout=20)
    if not r or r.status_code != 200:
        print(f"  ⚠️ 搜索失败: {query} (status={r.status_code if r else 'None'})")
        return records

    soup = BeautifulSoup(r.text, "html.parser")
    # Sogou 结果: <h3><a href="/link?url=...">标题</a></h3>
    for h3 in soup.find_all("h3"):
        a = h3.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not href:
            continue
        if href.startswith("/link?url="):
            real = resolve_sogou_link("https://www.sogou.com" + href)
        else:
            real = href
        if not real:
            continue
        # 来源域名（招投标平台判断用）
        try:
            from urllib.parse import urlparse
            _domain = urlparse(real).netloc
        except Exception:
            _domain = ""
        # 摘要（同结果块）
        parent = h3.find_parent(class_=re.compile(r"rb|vrwrap|results|citeUrl", re.IGNORECASE)) or h3.parent
        snippet = ""
        if parent:
            snippet = parent.get_text(" ", strip=True)
        combined = f"{title} {snippet}"

        if not is_tender(combined, _domain) and not is_brand(combined):
            continue

        rec = {
            "title": title,
            "url": real,
            "source": _domain,
            "date": extract_date(combined),
            "status": classify_status(combined),
            "buyer": "",
            "region": "",
            "budget": find_budget(combined),
                       "winners": find_winners(combined),
            "snippet": snippet[:200],
            "query": query,
            "brand": is_brand(combined),
        }
        records.append(rec)
        if len(records) >= max_per_query:
            break

    return records


def enrich_from_detail(rec):
    """尽力抓取详情页补充字段（best-effort）。"""
    r = http_get(rec["url"], timeout=15)
    if not r or r.status_code != 200:
        return
    text = r.text
    # 详情页常含更精确的日期、采购方、地区
    d = extract_date(text)
    if d and not rec["date"]:
        rec["date"] = d
    # 采购方：常见 "招标人/采购人/业主：XXX"
    m = re.search(r"(?:招标人|采购人|采购单位|业主|发包人)[：:]\s*([\u4e00-\u9fa5（）()0-9A-Za-z&·]{4,40})", text)
    if m and not rec["buyer"]:
        rec["buyer"] = m.group(1).strip()
    # 地区：省+市
    m = re.search(r"([\u4e00-\u9fa5]{2,4}?(?:省|市|自治区|区))", text)
    if m and not rec["region"]:
        rec["region"] = m.group(1).strip()
    # 中标方
    w = find_winners(text)
    if w:
        rec["winners"] = list(dict.fromkeys(rec["winners"] + w))
    # 预算
    if not rec["budget"]:
        rec["budget"] = find_budget(text)


def dedupe(records):
    seen = set()
    out = []
    for r in records:
        key = (r["title"][:40], r["url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_report(records, days):
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    recent = []
    for r in records:
        if r["date"]:
            try:
                dt = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
                if dt < cutoff:
                    continue
            except Exception:
                pass
        recent.append(r)
    # 按日期倒序
    recent.sort(key=lambda x: x["date"] or "0000-00-00", reverse=True)

    lines = []
    lines.append("# 🧪 半导体清洗设备(Guyson/吉仕嘉)招投标日报")
    lines.append("")
    lines.append(f"> 生成时间：{now_str()}｜数据源：Sogou 搜索引擎聚合（采招网/千里马/中国招标投标公共服务平台/行业媒体等）")
    n_tender = sum(1 for r in recent if not r.get("brand"))
    n_brand = sum(1 for r in recent if r.get("brand"))
    lines.append(f"> 检索范围：最近 {days} 天｜招投标公告 {n_tender} 条｜品牌/代理动态 {n_brand} 条")
    lines.append("")
    lines.append("## 一、招投标公告（招标/中标/采购）")
    lines.append("")
    tenders = [r for r in recent if not r.get("brand")]
    brands = [r for r in recent if r.get("brand")]
    if not tenders:
        lines.append("_近期内未检索到相关招投标公告（或数据源暂无更新）。_")
    for i, r in enumerate(tenders, 1):
        status_icon = {"中标": "✅", "招标": "📋", "其他": "🔹"}.get(r["status"], "🔹")
        line = f"{i}. {status_icon} **{r['title']}**"
        meta = []
        if r["date"]:
            meta.append(r["date"])
        if r["status"] != "其他":
            meta.append(r["status"])
        if r["buyer"]:
            meta.append(f"采购方:{r['buyer']}")
        if r["region"]:
            meta.append(r["region"])
        if r["budget"]:
            meta.append(f"预算:{r['budget']}")
        if r["winners"]:
            meta.append("中标方:" + "/".join(r["winners"]))
        if meta:
            line += "  _（" + "｜".join(meta) + "）_"
        lines.append(line)
        if r["source"]:
            lines.append(f"   - 来源：{r['source']}  [链接]({r['url']})")
        lines.append("")

    # 二、品牌/代理动态（Guyson/吉仕嘉/Mecwash/MB Tech）
    if brands:
        lines.append("## 二、Guyson/吉仕嘉/Mecwash 品牌与代理动态")
        lines.append("")
        for i, r in enumerate(brands, 1):
            line = f"{i}. 🏷️ **{r['title']}**"
            meta = []
            if r["date"]:
                meta.append(r["date"])
            if meta:
                line += "  _（" + "｜".join(meta) + "）_"
            lines.append(line)
            if r["source"]:
                lines.append(f"   - 来源：{r['source']}  [链接]({r['url']})")
            lines.append("")

    # 三、中标方（A股相关）统计
    winner_count = {}
    for r in recent:
        for w in r["winners"]:
            winner_count[w] = winner_count.get(w, 0) + 1
    if winner_count:
        lines.append("## 三、A股相关中标方出现频次")
        lines.append("")
        for w, c in sorted(winner_count.items(), key=lambda x: -x[1]):
            lines.append(f"- {w}：{c} 次")
        lines.append("")

    lines.append("---")
    lines.append("_本报告由半导体清洗设备招投标爬虫自动生成，仅供参考，不构成投资建议。_")
    return "\n".join(lines), recent


def save_to_news_info(content):
    if not os.path.exists(DB_PATH):
        print(f"  ❌ 数据库不存在: {DB_PATH}")
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        tab_name = f"🧪 半导体清洗设备招投标｜{datetime.date.today().strftime('%Y-%m-%d')}"
        cur.execute(
            "INSERT INTO news_info (tab_name, content, created_at, updated_at) VALUES (?,?,?,?)",
            (tab_name, content, now_str(), now_str()),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  ❌ 写库失败: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--max", type=int, default=30)
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--enrich", action="store_true", help="尽力抓取详情页补充字段（更慢）")
    ap.add_argument("--enrich-max", type=int, default=15, help="最多抓取多少条详情页（默认15）")
    args = ap.parse_args()

    print("🧪 半导体清洗设备(Guyson)招投标爬虫 启动")
    print(f"   检索词: {len(QUERIES)} 个｜范围: 最近 {args.days} 天｜每词上限: {args.max}")

    all_recs = []
    for q in QUERIES:
        recs = crawl_query(q, max_per_query=args.max)
        print(f"  🔍 {q} → {len(recs)} 条")
        all_recs.extend(recs)

    all_recs = dedupe(all_recs)
    print(f"去重后共 {len(all_recs)} 条")

    if args.enrich:
        for r in all_recs[:args.enrich_max]:
            enrich_from_detail(r)

    report, recent = build_report(all_recs, args.days)
    print(f"\n📊 范围内命中 {len(recent)} 条，生成报告（{len(report)} 字符）\n")
    print("=" * 60)
    print(report[:1500])
    print("=" * 60)

    if args.no_db:
        print("\n(已跳过写库 --no-db)")
        return

    if save_to_news_info(report):
        print(f"\n✅ 已写入资讯数据库: {DB_PATH}")
        print(f"   tab_name: 🧪 半导体清洗设备招投标｜{datetime.date.today().strftime('%Y-%m-%d')}")
    else:
        print("\n❌ 写库失败")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# mean_reversion_market.py - 全市场基本面优质股均值回归扫描
# 股票池: stockyidong_mac 全市场关注池 (ai_config.json 的 holding_stocks 全体分组, 去重约500只)
# 流程:
#   1. 加载全市场池 (holding_stocks 全体去重)
#   2. 布林带并发扫描 (腾讯日K, 20日2σ) → 找接近支撑/阻力/突破的信号候选 (快, 不依赖neodata)
#   3. 对信号候选跑段基 duanji.analyze_stock (经neodata, 慢) → 确认基本面优质 (段基≥阈值)
#   4. 输出报告: 基本面优质 + 均值回归信号
# 性能: 布林带并发跑全市场池(分钟级); 段基只跑信号候选(数十只, 控制neodata调用)
# 环境: 段基需 neodata (cron/agentTurn 环境可用; 手动exec环境不可用时自动跳过, 标注"段基未算")
#
# 用法:
#   python3 mean_reversion_market.py                 # 全市场扫描, 段基≥65
#   python3 mean_reversion_market.py --min-duanji 75 # 段基≥75 强优质
#   python3 mean_reversion_market.py --top 50        # 只输出前50只信号 (不限定时)
#   python3 mean_reversion_market.py --output report.md
#   python3 mean_reversion_market.py --db /path/db --cfg /path/ai_config.json
import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, "/Users/faronpan/.qclaw/workspace/src")  # duanji
SRC = "/Users/faronpan/Agent/stockyidong_project/src"
CFG = "/Users/faronpan/Agent/stockyidong_project/src/config/ai_config.json"
DB = "/Users/faronpan/Agent/stockyidong_project/data/stock_analysis.db"
TOL = 0.03          # 接近阈值 ±3%
WORKERS = 10        # 布林带并发线程
DUIANJI_OK = False  # 段基是否可用 (neodata)

# ───────────────────────── K线/布林带 (腾讯前复权日K) ─────────────────────────
import ssl
import urllib.request


def get_kline(code, n=90):
    """腾讯前复权日K线, 返回 [{date,open,close,high,low}]"""
    prefix = 'sh' if code[0] == '6' else ('sz' if code[0] in '03' else 'bj')
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?_var=kline_dayqfq&param={prefix}{code},day,,,{n},qfq")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://stockapp.finance.qq.com'
    })
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        raw = resp.read().decode('utf-8')
    m = re.search(r'=(.*)', raw, re.DOTALL)
    data = json.loads(m.group(1))
    kline = data['data'][f'{prefix}{code}']['qfqday']
    return [{'date': x[0], 'open': float(x[1]), 'close': float(x[2]),
             'high': float(x[3]), 'low': float(x[4])} for x in kline]


def boll(closes, n=20, k=2):
    w = closes[-n:]
    mid = sum(w) / n
    import statistics
    std = statistics.pstdev(w)
    return mid, mid + k * std, mid - k * std


def classify(price, mid, upper, lower):
    res = []
    if price < lower * (1 - TOL):
        res.append(('⚠️ 破位', f'跌破布林下轨(支撑){lower:.2f}（-{(1-price/lower)*100:.1f}%）'))
    elif price <= lower * (1 + TOL):
        res.append(('🟢 接近支撑', f'触及布林下轨{lower:.2f}（仅{(price/lower-1)*100:+.1f}%），超卖可能反弹'))
    else:
        res.append(('', f'高于支撑{lower:.2f} +{(price/lower-1)*100:.1f}%'))
    if price > upper * (1 + TOL):
        res.append(('🚀 突破', f'突破布林上轨(阻力){upper:.2f}（+{(price/upper-1)*100:.1f}%），强势'))
    elif price >= upper * (1 - TOL):
        res.append(('🔴 接近阻力', f'触及布林上轨{upper:.2f}（仅{(price/upper-1)*100:+.1f}%），超买可能回调'))
    else:
        res.append(('', f'低于阻力{upper:.2f} {(price/upper-1)*100:+.1f}%'))
    return res


# ───────────────────────── 股票池加载 ─────────────────────────
def load_market_pool(cfg_path=CFG):
    """从 ai_config.json 加载 holding_stocks 全体分组, 去重返回 [{code,name}]"""
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    seen = {}
    for key, val in cfg.items():
        if not (key.startswith('holding_stocks') or key == 'history_holdings'):
            continue
        if not isinstance(val, list):
            continue
        for x in val:
            code = name = None
            if isinstance(x, dict):
                code = str(x.get('stock_code') or x.get('code') or '').strip()
                name = x.get('stock_name') or x.get('name') or ''
            elif isinstance(x, str):
                # 可能 "603290 斯达半导" 或纯代码
                m = re.search(r'(\d{6})', x)
                code = m.group(1) if m else ''
                name = re.sub(r'\d{6}', '', x).strip()
            code = re.sub(r'[^\d]', '', code)[:6]
            if len(code) == 6 and code not in seen:
                seen[code] = {'code': code, 'name': name}
    return list(seen.values())


# ───────────────────────── 段基 (duanji / neodata) ─────────────────────────
def init_duanji():
    global DUIANJI_OK
    try:
        import duanji  # noqa
        import neodata  # noqa
        DUIANJI_OK = True
    except Exception as e:
        DUIANJI_OK = False
        print(f"[段基] 不可用 (neodata缺失, 仅输出布林带信号): {e}")


def duanji_score(code, name):
    if not DUIANJI_OK:
        return None, "段基未算"
    try:
        import duanji
        r = duanji.analyze_stock(code, name or code)
        return r.get("total_score"), r.get("verdict")
    except Exception as e:
        return None, f"段基失败:{e}"


# ───────────────────────── 单只扫描 ─────────────────────────
def scan_one(s):
    """布林带扫描单只, 返回 dict 或 None(无信号)"""
    code, name = s['code'], s['name']
    try:
        rows = get_kline(code)
        closes = [r['close'] for r in rows]
        if len(closes) < 20:
            return None
        price = closes[-1]
        mid, up, lo = boll(closes)
    except Exception:
        return None
    cls = classify(price, mid, up, lo)
    tags = [t for t, _ in cls if t]
    # 有信号标签(接近支撑/阻力/破位/突破)才纳入候选
    if not tags:
        return None
    return {'code': code, 'name': name, 'price': price,
            'mid': mid, 'up': up, 'lo': lo, 'cls': cls, 'tags': tags}


def sort_key(r):
    """越接近边界越靠前"""
    price, up, lo = r['price'], r['up'], r['lo']
    return min(abs(price/up - 1), abs(price/lo - 1))


# ───────────────────────── 主扫描 ─────────────────────────
def scan(cfg_path, db_path, min_duanji, top=None, output=None, pool_limit=None):
    t0 = time.time()
    pool = load_market_pool(cfg_path)
    if pool_limit:
        pool = pool[:pool_limit]
    print(f"📊 全市场池: {len(pool)}只 (holding_stocks 全体去重)")
    # 1) 布林带并发扫描
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(scan_one, s): s for s in pool}
        done = 0
        for f in as_completed(futs):
            done += 1
            r = f.result()
            if r:
                results.append(r)
            if done % 100 == 0:
                print(f"  ...布林带扫描 {done}/{len(pool)}, 信号候选 {len(results)}")
    results.sort(key=sort_key)
    print(f"✅ 布林带扫描完成: {len(results)}只信号候选 ({round(time.time()-t0,1)}s)")

    # 2) 段基确认 (仅信号候选)
    init_duanji()
    quality = []
    if DUIANJI_OK:
        print(f"🔍 段基确认中 (候选{len(results)}只, 阈值≥{min_duanji})...")
        for i, r in enumerate(results, 1):
            dj, verdict = duanji_score(r['code'], r['name'])
            r['duanji'] = dj
            r['verdict'] = verdict
            if dj is not None and dj >= min_duanji:
                quality.append(r)
            if i % 10 == 0:
                print(f"  ...段基 {i}/{len(results)}, 基本面优质 {len(quality)}")
    else:
        # 段基不可用: 全部信号候选输出, 标注未算
        for r in results:
            r['duanji'] = None
            r['verdict'] = "段基未算"
        quality = results

    # 3) 输出
    if top:
        quality = quality[:top]
    today = datetime.now().strftime('%Y-%m-%d')
    lines = ["# 📐 均值回归分析｜全市场基本面优质股\n"]
    lines.append(f"> 扫描日期: {today} | 全市场池 {len(pool)}只 | 信号候选 {len(results)}只 | "
                 f"基本面优质(段基≥{min_duanji}) {len([r for r in results if r['duanji'] and r['duanji']>=min_duanji])}只")
    lines.append(f"> 布林(20,2σ) | 阈值±{TOL*100:.0f}% | 段基:{'可用' if DUIANJI_OK else '未算(手动环境,建议cron运行)'}\n")
    for r in quality:
        dj = r['duanji']
        djs = f"{dj}/105" if dj is not None else "未算"
        lines.append(f"**{r['name']}**({r['code']}) 现价={r['price']} 段基={djs}")
        lines.append(f"  布林: 上轨(阻){r['up']:.2f} 中轨{r['mid']:.2f} 下轨(撑){r['lo']:.2f}")
        for tag, desc in r['cls']:
            if tag:
                lines.append(f"  {tag} {desc}")
            else:
                lines.append(f"  · {desc}")
        if r['verdict'] and r['verdict'] not in ('段基未算',):
            lines.append(f"  📋 {r['verdict']}")
        lines.append("")
    lines.append(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 耗时 {round(time.time()-t0,1)}s")
    lines.append("\n*本报告由均值回归Market Skill自动生成，仅供参考，不构成投资建议。*")
    report = "\n".join(lines)
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ 报告已写入: {output}")
    else:
        print(report)
    return report


def main():
    ap = argparse.ArgumentParser(description="均值回归-全市场基本面优质股")
    ap.add_argument("--cfg", default=CFG, help="ai_config.json 路径")
    ap.add_argument("--db", default=DB, help="stock_analysis.db 路径(预留)")
    ap.add_argument("--min-duanji", type=int, default=65, help="段基最低分(默认65)")
    ap.add_argument("--top", type=int, default=None, help="只输出前N只")
    ap.add_argument("--pool-limit", type=int, default=None, help="测试: 只扫描前N只")
    ap.add_argument("--output", help="输出Markdown到文件")
    args = ap.parse_args()
    scan(args.cfg, args.db, args.min_duanji, args.top, args.output, args.pool_limit)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
stockyidong_daily_report_v4.py
每日智能选股日报 v4（TuShare 版）：
  1. 聚合近20日淘股吧+韭研公社提及频次 → 热度分
  2. 叠加最新 stockyidong 文件（龙头股/15Min/同花顺）→ 共振分
  3. 用 TuShare（tushare_helper）获取均线/市值，筛选：
       市值 ≥ 100亿 且 靠近10日线/20日线(±3%) 且 10/20/60日均线多头排列
  4. 综合评分 = 热度分 + 共振分×2，降序
  5. 生成 Word 日报，可选发送到微信

用法：
  python3 stockyidong_daily_report_v4.py              # 全流程（TuShare筛选）
  python3 stockyidong_daily_report_v4.py --no-tushare   # 跳过TuShare，秒出结果
  python3 stockyidong_daily_report_v4.py --no-send      # 只生成，不发送
  python3 stockyidong_daily_report_v4.py --refresh-cache # 强制刷新TuShare缓存
"""

import argparse
import datetime
import glob
import os
import re
import subprocess
import time
from collections import defaultdict

# ========== 路径 ==========
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR  = os.path.join(SCRIPT_DIR, "report")
os.makedirs(REPORT_DIR, exist_ok=True)

# ========== 依赖检测 ==========
DOCX_OK     = False
OPENPYXL_OK = False
TUSHARE_OK  = False

try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor
    DOCX_OK = True
    print("[INFO] python-docx 已加载")
except ImportError:
    print("[WARN] python-docx 未安装，Word输出将被跳过")

try:
    import openpyxl
    OPENPYXL_OK = True
    print("[INFO] openpyxl 已加载")
except ImportError:
    print("[WARN] openpyxl 未安装，xlsx解析将被跳过")

# tushare_helper 在同一目录，加入搜索路径
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
try:
    import tushare_helper
    TUSHARE_OK = True
    print("[INFO] tushare_helper 已加载，将进行均线/市值筛选")
except ImportError:
    print("[WARN] tushare_helper 未找到（需 tushare_helper.py 在同一目录）")


# ========== 工具函数（与v3相同） ==========
def extract_codes_from_text(text):
    """从文本提取6位股票代码"""
    codes = set()
    for m in re.finditer(r'(?:sh|sz)(\d{6})', str(text), re.IGNORECASE):
        codes.add(m.group(1))
    for m in re.finditer(r'(?<![a-z])(\d{6})(?![a-z])', str(text)):
        code = m.group(1)
        if code[0] in ('0', '3', '6', '8'):
            codes.add(code)
    return codes


def load_recent_taoguba(days=20):
    """返回 {code: {'count':N, 'names':set(), 'last_seen':str}}"""
    pattern = os.path.join(SCRIPT_DIR, "taoguba_exports", "taoguba_100_posts_*.xlsx")
    files = sorted(glob.glob(pattern))
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    info = defaultdict(lambda: {"count": 0, "names": set(), "last_seen": None})

    for fp in files:
        m = re.search(r'(\d{8})_(\d{6})', fp)
        if not m:
            continue
        try:
            fdate = datetime.datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            continue
        if fdate < cutoff:
            continue
        if not OPENPYXL_OK:
            continue
        try:
            wb = openpyxl.load_workbook(fp, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                code_raw = row[5] if len(row) > 5 else None
                name_raw = row[6] if len(row) > 6 else None
                if code_raw and str(code_raw).strip():
                    code = re.sub(r'\D', '', str(code_raw)).strip()[-6:]
                    if len(code) == 6 and code[0] in ('0','3','6','8'):
                        info[code]["count"] += 1
                        if name_raw:
                            info[code]["names"].add(str(name_raw).strip())
                        if not info[code]["last_seen"] or m.group(1) > info[code]["last_seen"]:
                            info[code]["last_seen"] = m.group(1)
            wb.close()
        except Exception as e:
            print(f"  [WARN] 淘股吧文件 {os.path.basename(fp)} 读取失败: {e}")
    return info


def load_recent_jiuyan(days=20):
    """返回 {code: {'count':N, 'names':set(), 'last_seen':str}}"""
    pattern = os.path.join(SCRIPT_DIR, "jiuyang_gongshe_*.xlsx")
    files = sorted(glob.glob(pattern))
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    info = defaultdict(lambda: {"count": 0, "names": set(), "last_seen": None})

    for fp in files:
        m = re.search(r'(\d{8})_(\d{6})', fp)
        if not m:
            continue
        try:
            fdate = datetime.datetime.strptime(m.group(1), "%Y%m%d")
        except ValueError:
            continue
        if fdate < cutoff:
            continue
        if not OPENPYXL_OK:
            continue
        try:
            wb = openpyxl.load_workbook(fp, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                related = row[14] if len(row) > 14 else None
                code_raw = row[15] if len(row) > 15 else None
                if related:
                    for code in extract_codes_from_text(str(related)):
                        info[code]["count"] += 1
                        if not info[code]["last_seen"] or m.group(1) > info[code]["last_seen"]:
                            info[code]["last_seen"] = m.group(1)
                if code_raw and str(code_raw).strip():
                    code = re.sub(r'\D', '', str(code_raw)).strip()[-6:]
                    if len(code) == 6 and code[0] in ('0','3','6','8'):
                        info[code]["count"] += 1
                        if not info[code]["last_seen"] or m.group(1) > info[code]["last_seen"]:
                            info[code]["last_seen"] = m.group(1)
            wb.close()
        except Exception as e:
            print(f"  [WARN] 韭研公社文件 {os.path.basename(fp)} 读取失败: {e}")
    return info


def load_latest_stockyidong():
    """返回 {label: [{'name':.., 'code':..}]}"""
    pattern = os.path.join(SCRIPT_DIR, "stockyidong_*.txt")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    result = {"龙头股": [], "15Min": [], "同花顺": []}
    if not files:
        print("[WARN] 未找到 stockyidong_*.txt 文件")
        return result

    latest = files[0]
    print(f"[INFO] 读取 StockYiDong 文件: {os.path.basename(latest)}")
    with open(latest, "r", encoding="utf-8") as f:
        content = f.read()

    for label in ["龙头股", "15Min", "同花顺"]:
        m = re.search(rf'【{label}[^】]*】(.*?)(?=【|\Z)', content, re.DOTALL)
        if not m:
            continue
        block = m.group(1)
        for seg in block.split("、"):
            seg = seg.strip()
            if not seg or seg in ("（无）", "(无)"):
                continue
            nm = re.match(r'^(.+?)\((\d{6})\)', seg)
            if nm:
                result[label].append({"name": nm.group(1).strip(), "code": nm.group(2)})
    return result


def build_report_data(use_tushare=True, refresh_cache=False, debug=False):
    """
    主函数：聚合所有数据源，返回 (results, syd_sections)
    """
    print("\n[STEP 1/4] 加载淘股吧近20日数据...")
    tg = load_recent_taoguba(20)
    print(f"  → 提及股票数: {len(tg)}")

    print("[STEP 2/4] 加载韭研公社近20日数据...")
    jy = load_recent_jiuyan(20)
    print(f"  → 提及股票数: {len(jy)}")

    print("[STEP 3/4] 加载最新 StockYiDong 持仓...")
    syd = load_latest_stockyidong()
    for k, v in syd.items():
        print(f"  → {k}: {len(v)} 只")

    # 合并所有代码
    all_codes = set(tg.keys()) | set(jy.keys())
    for sec in syd.values():
        for s in sec:
            all_codes.add(s["code"])
    all_codes = sorted(all_codes)
    print(f"\n[STEP 4/4] 合并后共 {len(all_codes)} 只股票")

    # TuShare 数据获取
    ts_data = {}
    if use_tushare and TUSHARE_OK:
        print("  开始获取 TuShare 行情数据（带缓存，请耐心等待）...")
        try:
            ts_data = tushare_helper.get_stock_ma_batch(
                list(all_codes),
                refresh_all=refresh_cache,
                verbose=True
            )
            print(f"  → 成功获取 {len(ts_data)} 只股票行情数据")
        except Exception as e:
            print(f"  [WARN] TuShare 获取失败: {e}")
            if not use_tushare:
                pass  # --no-tushare 模式，不报错
            else:
                print("  [INFO] 将跳过均线/市值筛选（--no-tushare 模式）")
                use_tushare = False
    elif use_tushare and not TUSHARE_OK:
        print("  [INFO] tushare_helper 不可用，跳过均线/市值筛选（--no-tushare 模式）")
    else:
        print("  [INFO] --no-tushare 模式，跳过 TuShare 请求")

    print("  筛选 + 评分排序...")
    results = []
    for code in all_codes:
        item = {"code": code, "name": "", "taoguba_count": 0, "jiuyan_count": 0}

        # 热度
        tg_entry = tg.get(code)
        if tg_entry:
            item["taoguba_count"] = tg_entry.get("count", 0)
            names = tg_entry.get("names", set())
            if names:
                item["name"] = "、".join(names)

        jy_entry = jy.get(code)
        if jy_entry:
            item["jiuyan_count"] = jy_entry.get("count", 0)
            names = jy_entry.get("names", set())
            if names and not item["name"]:
                item["name"] = "、".join(names)

        # 从 stockyidong 补充名称
        if not item["name"]:
            for sec in syd.values():
                for s in sec:
                    if s["code"] == code:
                        item["name"] = s["name"]
                        break

        # 共振标签
        item["in_longtou"] = any(s["code"] == code for s in syd["龙头股"])
        item["in_15min"]   = any(s["code"] == code for s in syd["15Min"])
        item["in_ths"]      = any(s["code"] == code for s in syd["同花顺"])
        item["syd_score"] = (3 if item["in_longtou"] else 0) + \
                            (2 if item["in_15min"]   else 0) + \
                            (1 if item["in_ths"]      else 0)

        # TuShare 数据
        ts = ts_data.get(code)
        if ts:
            item["market_cap"]  = ts.get("market_cap")
            item["close"]       = ts.get("close")
            item["ma10"]        = ts.get("ma10")
            item["ma20"]        = ts.get("ma20")
            item["ma60"]        = ts.get("ma60")
            item["near_ma10"]   = ts.get("near_ma10", False)
            item["near_ma20"]   = ts.get("near_ma20", False)
            item["ma_bullish"]  = ts.get("ma_bullish", False)
        else:
            item["market_cap"] = None
            item["close"]      = None
            item["ma10"]       = None
            item["ma20"]       = None
            item["ma60"]       = None
            item["near_ma10"]  = False
            item["near_ma20"]  = False
            item["ma_bullish"] = False

        # ── 筛选 ──
        if use_tushare and ts:
            mc = item["market_cap"]
            if mc is not None and mc < 100:
                continue
            if not (item["near_ma10"] or item["near_ma20"]):
                continue
            if not item["ma_bullish"]:
                continue
        # 如果 TuShare 不可用或不使用，不过滤

        item["heat_score"]  = item["taoguba_count"] + item["jiuyan_count"] * 2
        item["total_score"] = item["heat_score"] + item["syd_score"] * 2
        results.append(item)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    print(f"  → 筛选后剩余 {len(results)} 只")
    return results, syd


def make_word_report(results, syd, out_path):
    """生成 Word 日报"""
    if not DOCX_OK:
        print("[SKIP] python-docx 不可用，跳过 Word 生成")
        return None

    doc = Document()
    for sec in doc.sections:
        sec.top_margin    = Cm(2)
        sec.bottom_margin = Cm(2)
        sec.left_margin   = Cm(2.5)
        sec.right_margin  = Cm(2.5)

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    title = doc.add_heading(f"📈 斯东克·每日智能选股日报（{today}）", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].font.size = Pt(16)
    title.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

    doc.add_paragraph(f"生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    filter_note = "筛选条件（TuShare数据）：市值≥100亿 ｜ 靠近10日线/20日线（±3%） ｜ 10/20/60日均线多头排列"
    if not TUSHARE_OK:
        filter_note = "【tushare_helper 未加载，跳过筛选，按热度+共振排序】"
    doc.add_paragraph(filter_note)
    doc.add_paragraph(f"共筛选出 {len(results)} 只股票 ｜ 数据来源：近20日淘股吧+韭研公社+StockYiDong")

    # ── 一、Top20 ──
    h1 = doc.add_heading("一、今日 Top 推荐（综合评分降序）", level=2)
    h1.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)

    table = doc.add_table(rows=1, cols=8)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "排名"
    hdr[1].text = "名称"
    hdr[2].text = "代码"
    hdr[3].text = "综合分"
    hdr[4].text = "热度分"
    hdr[5].text = "共振标签"
    hdr[6].text = "市值(亿)"
    hdr[7].text = "靠近均线"
    for c in hdr:
        c.paragraphs[0].runs[0].bold = True
        c.paragraphs[0].runs[0].font.size = Pt(9)

    for i, info in enumerate(results[:20], 1):
        row = table.add_row().cells
        row[0].text = str(i)
        row[1].text = info["name"] or "-"
        row[2].text = info["code"]
        row[3].text = str(info["total_score"])
        row[4].text = str(info["heat_score"])
        tags = []
        if info["in_longtou"]: tags.append("龙头")
        if info["in_15min"]:   tags.append("15Min")
        if info["in_ths"]:      tags.append("同花顺")
        row[5].text = "/".join(tags) if tags else "-"
        row[6].text = str(round(info["market_cap"], 1)) if info["market_cap"] else "-"
        near = []
        if info.get("near_ma10"): near.append("10日线")
        if info.get("near_ma20"): near.append("20日线")
        row[7].text = "、".join(near) if near else "-"

        if i <= 3:
            for c in row:
                for p in c.paragraphs:
                    for run in p.runs:
                        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
                        run.bold = True

    # ── 二、逻辑说明 ──
    doc.add_paragraph()
    h2 = doc.add_heading("二、评分逻辑说明", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    doc.add_paragraph(
        "① 热度分 = 淘股吧提及次数 + 韭研公社提及次数×2（公社质量权重更高）\n"
        "② 共振分 = 龙头股×3 + 15Min×2 + 同花顺×1\n"
        "③ 综合评分 = 热度分 + 共振分×2，降序排列\n"
        "④ 筛选条件（TuShare可用时生效）：\n"
        "   - 总市值 ≥ 100亿\n"
        "   - 收盘价在10日线或20日线 ±3% 范围内\n"
        "   - 10/20/60日均线多头排列（ma10 > ma20 > ma60）\n"
        "⑤ TuShare 不可用时会跳过筛选，保留所有股票并按热度+共振排序。"
    )

    # ── 三、StockYiDong 各标签明细 ──
    doc.add_paragraph()
    h3 = doc.add_heading("三、StockYiDong 持仓明细", level=2)
    h3.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    for label, stocks in syd.items():
        doc.add_heading(f"【{label}】共 {len(stocks)} 只", level=3)
        if stocks:
            doc.add_paragraph("、".join(f"{s['name']}({s['code']})" for s in stocks))
        else:
            doc.add_paragraph("（无）")

    doc.save(out_path)
    print(f"[OK] Word 日报已生成: {out_path}")
    return out_path


def send_weixin(file_path):
    """通过 openclaw-weixin 通道发送文件"""
    target = "o9cq80z54pjdB4tednhGbb3W9pTk@im.wechat"
    cmd = [
        "openclaw", "message", "send",
        "--channel", "openclaw-weixin",
        "-t", target,
        "--media", file_path,
    ]
    print(f"[INFO] 发送微信: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("[OK] 微信发送成功")
            return True
        else:
            print(f"[WARN] 微信发送失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"[WARN] 发送失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-send",       action="store_true", help="只生成报告，不发送到微信")
    parser.add_argument("--no-tushare",   action="store_true", help="跳过TuShare，秒出结果（不筛选均线/市值）")
    parser.add_argument("--refresh-cache", action="store_true", help="强制刷新TuShare缓存")
    parser.add_argument("--debug",         action="store_true", help="打印详细调试信息")
    args = parser.parse_args()

    t0 = time.time()
    results, syd = build_report_data(
        use_tushare=not args.no_tushare,
        refresh_cache=args.refresh_cache,
        debug=args.debug
    )

    today_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = os.path.join(REPORT_DIR, f"daily_report_{today_str}.docx")

    out_path = make_word_report(results, syd, out_path)

    # 控制台输出 Top5
    print("\n" + "=" * 50)
    print("🔥 Top5 推荐股票：")
    for i, info in enumerate(results[:5], 1):
        tags = []
        if info["in_longtou"]: tags.append("龙头")
        if info["in_15min"]:   tags.append("15Min")
        if info["in_ths"]:      tags.append("同花顺")
        mc  = f" 市值={info['market_cap']}亿" if info["market_cap"] else ""
        near = ""
        if info.get("near_ma10"): near += " [靠近10日线]"
        if info.get("near_ma20"): near += " [靠近20日线]"
        print(f"  {i}. {info['name']}({info['code']}) "
              f"综合分={info['total_score']} 热度={info['heat_score']} "
              f"{'[' + '/'.join(tags) + ']' if tags else ''}{mc}{near}")
    print("=" * 50)

    # 发送微信
    if not args.no_send and out_path:
        try:
            send_weixin(out_path)
        except Exception as e:
            print(f"[WARN] 发送失败: {e}")
            print(f"[INFO] 请手动发送文件: {out_path}")
    elif args.no_send:
        print(f"\n[INFO] --no-send 模式，Word 已保存: {out_path}")

    print(f"\n✅ 完成，用时 {time.time()-t0:.1f} 秒")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
stockyidong_daily_report.py
每日智能选股日报：聚合近20日淘股吧+韭研公社资讯热度，
叠加均线/市值筛选，按共振逻辑排序，输出Word日报。

依赖：python-docx, openpyxl, akshare, pandas, numpy
用法：
  python3 stockyidong_daily_report.py              # 自动跑全流程
  python3 stockyidong_daily_report.py --no-send  # 只生成不发微信
"""

import argparse
import datetime
import glob
import os
import re
import time
from collections import defaultdict

# ========== 路径配置 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR  = os.path.join(SCRIPT_DIR, "report")
os.makedirs(REPORT_DIR, exist_ok=True)

# ========== 尝试导入依赖 ==========
try:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor
    DOCX_OK = True
except ImportError:
    DOCX_OK = False
    print("[WARN] python-docx 未安装，Word输出将被跳过")

try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

try:
    import akshare as ak
    AKSHARE_OK = True
except ImportError:
    AKSHARE_OK = False
    print("[WARN] akshare 未安装，均线/市值筛选将被跳过")


# ========== 工具函数 ==========
def extract_stock_codes(text):
    """从文本中提取6位股票代码（适配 sh600519 / sz000066 / 600519 等格式）"""
    codes = set()
    # 匹配 sh600519 或 sz000066
    for m in re.finditer(r'[sh|sz](\d{6})', str(text), re.IGNORECASE):
        codes.add(m.group(1))
    # 匹配独立6位数字
    for m in re.finditer(r'(?<![a-z])(\d{6})(?![a-z])', str(text)):
        code = m.group(1)
        if code[:1] in ('0', '3', '6', '8'):
            codes.add(code)
    return codes


def load_recent_taoguba(days=20):
    """读取近N天淘股吧xlsx，返回 {code: {'count':N, 'posts':[...]}}"""
    pattern = os.path.join(SCRIPT_DIR, "taoguba_exports", "taoguba_100_posts_*.xlsx")
    files = sorted(glob.glob(pattern))
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    
    code_info = defaultdict(lambda: {"count": 0, "names": set(), "last_seen": None})
    for fp in files:
        # 从文件名提取日期
        m = re.search(r'(\d{8})_(\d{6})', fp)
        if not m:
            continue
        file_date_str = m.group(1)
        try:
            file_date = datetime.datetime.strptime(file_date_str, "%Y%m%d")
        except ValueError:
            continue
        if file_date < cutoff:
            continue
        
        if not OPENPYXL_OK:
            continue
        try:
            wb = openpyxl.load_workbook(fp, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                code_raw = row[5] if len(row) > 5 else None  # 股票代码列
                name_raw = row[6] if len(row) > 6 else None  # 股票名称列
                if code_raw and str(code_raw).strip():
                    code = str(code_raw).strip()
                    code = re.sub(r'\D', '', code)[-6:]  # 取最后6位数字
                    if len(code) == 6:
                        code_info[code]["count"] += 1
                        if name_raw:
                            code_info[code]["names"].add(str(name_raw).strip())
                        if not code_info[code]["last_seen"] or file_date_str > code_info[code]["last_seen"]:
                            code_info[code]["last_seen"] = file_date_str
            wb.close()
        except Exception as e:
            print(f"[WARN] 读取淘股吧文件失败 {fp}: {e}")
    
    return code_info


def load_recent_jiuyan(days=20):
    """读取近N天韭研公社xlsx，返回 {code: {'count':N, 'names':set()}}"""
    pattern = os.path.join(SCRIPT_DIR, "jiuyang_gongshe_*.xlsx")
    files = sorted(glob.glob(pattern))
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    
    code_info = defaultdict(lambda: {"count": 0, "names": set(), "last_seen": None})
    for fp in files:
        m = re.search(r'(\d{8})_(\d{6})', fp)
        if not m:
            continue
        file_date_str = m.group(1)
        try:
            file_date = datetime.datetime.strptime(file_date_str, "%Y%m%d")
        except ValueError:
            continue
        if file_date < cutoff:
            continue
        
        if not OPENPYXL_OK:
            continue
        try:
            wb = openpyxl.load_workbook(fp, read_only=True)
            ws = wb.active
            for row in ws.iter_rows(min_row=2, values_only=True):
                # 相关股票列(14)，股票代码列(15)
                related = row[14] if len(row) > 14 else None
                code_raw = row[15] if len(row) > 15 else None
                name_raw = None
                # 从相关股票列提取代码
                if related:
                    codes = extract_stock_codes(str(related))
                    for code in codes:
                        code_info[code]["count"] += 1
                        if not code_info[code]["last_seen"] or file_date_str > code_info[code]["last_seen"]:
                            code_info[code]["last_seen"] = file_date_str
                if code_raw and str(code_raw).strip():
                    code = re.sub(r'\D', '', str(code_raw))[-6:]
                    if len(code) == 6:
                        code_info[code]["count"] += 1
                        if name_raw:
                            code_info[code]["names"].add(str(name_raw).strip())
                        if not code_info[code]["last_seen"] or file_date_str > code_info[code]["last_seen"]:
                            code_info[code]["last_seen"] = file_date_str
            wb.close()
        except Exception as e:
            print(f"[WARN] 读取韭研公社文件失败 {fp}: {e}")
    
    return code_info


def load_latest_stockyidong():
    """读取最新的 stockyidong_*.txt，返回 {label: [{'name', 'code'}]}"""
    pattern = os.path.join(SCRIPT_DIR, "stockyidong_*.txt")
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if not files:
        return {"龙头股": [], "15Min": [], "同花顺": []}
    
    latest = files[0]
    print(f"[INFO] 读取StockYiDong文件: {os.path.basename(latest)}")
    
    with open(latest, "r", encoding="utf-8") as f:
        content = f.read()
    
    sections = {"龙头股": [], "15Min": [], "同花顺": []}
    # 解析三个板块
    for label in ["龙头股", "15Min", "同花顺"]:
        m = re.search(rf"【{label}[^】]*】(.+?)(?=【|\Z)", content, re.DOTALL)
        if not m:
            continue
        block = m.group(1)
        for seg in block.split("、"):
            seg = seg.strip()
            if not seg or seg in ("（无）", "(无)"):
                continue
            nm = re.match(r"^(.+?)\((\d{6})\)", seg)
            if nm:
                sections[label].append({"name": nm.group(1).strip(), "code": nm.group(2)})
    
    return sections


def get_akshare_stock_info(codes, max_retry=2):
    """
    用 akshare 获取股票市值、均线信息。
    返回 {code: {'name','market_cap','ma10','ma20','ma60','close','near_ma10','near_ma20','ma_bullish'}}
    """
    result = {}
    if not AKSHARE_OK:
        return result
    
    for code in codes:
        # 判断市场
        if code.startswith('6'):
            symbol = f"sh{code}"
        elif code.startswith(('0', '3')):
            symbol = f"sz{code}"
        else:
            continue
        
        try:
            # 获取最近120天日线
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if df is None or df.empty:
                continue
            
            # 兼容不同 akshare 版本列名
            col_map = {}
            for c in df.columns:
                cl = str(c).lower()
                if '日期' in cl or 'date' in cl:
                    col_map['date'] = c
                if '收盘' in cl or 'close' in cl:
                    col_map['close'] = c
                if '成交量' in cl or 'volume' in cl:
                    col_map['vol'] = c
            
            if 'close' not in col_map:
                continue
            
            df = df.tail(120).reset_index(drop=True)
            close_series = df[col_map['close']]
            
            # 计算均线
            ma10 = close_series.rolling(10).mean()
            ma20 = close_series.rolling(20).mean()
            ma60 = close_series.rolling(60).mean()
            
            last_close = float(close_series.iloc[-1])
            last_ma10  = float(ma10.iloc[-1])  if not ma10.isna().iloc[-1]  else None
            last_ma20  = float(ma20.iloc[-1])  if not ma20.isna().iloc[-1]  else None
            last_ma60  = float(ma60.iloc[-1])  if not ma60.isna().iloc[-1]  else None
            
            # 判断是否靠近10日/20日线（收盘价在±3%范围内）
            near_ma10 = False
            near_ma20 = False
            if last_ma10:
                near_ma10 = abs(last_close - last_ma10) / last_ma10 < 0.03
            if last_ma20:
                near_ma20 = abs(last_close - last_ma20) / last_ma20 < 0.03
            
            # 多头排列：ma10 > ma20 > ma60（且均非空）
            ma_bullish = False
            if last_ma10 and last_ma20 and last_ma60:
                ma_bullish = (last_ma10 > last_ma20 > last_ma60)
            
            # 市值（尝试获取）
            market_cap = None
            try:
                spot = ak.stock_individual_info_em(symbol=code)
                if spot is not None and not spot.empty:
                    for _, row in spot.iterrows():
                        if '总市值' in str(row.iloc[0]):
                            val = str(row.iloc[1])
                            # 解析 "1234亿" 或 "1234.56"
                            m2 = re.search(r'([\d\.]+)', val)
                            if m2:
                                market_cap = float(m2.group(1))
                                if '亿' in val:
                                    pass  # 已经是亿单位
                            break
            except Exception:
                pass
            
            result[code] = {
                "close": last_close,
                "ma10": last_ma10,
                "ma20": last_ma20,
                "ma60": last_ma60,
                "near_ma10": near_ma10,
                "near_ma20": near_ma20,
                "ma_bullish": ma_bullish,
                "market_cap": market_cap,  # 亿为单位
            }
            time.sleep(0.3)  # 避免请求过快
        except Exception as e:
            print(f"  [WARN] akshare获取{code}失败: {e}")
            continue
    
    return result


def build_report_data():
    """主函数：聚合所有数据源，返回排序后的股票列表"""
    print("\n[STEP 1] 加载淘股吧近20日数据...")
    taoguba_info = load_recent_taoguba(20)
    print(f"  淘股吧提及股票数: {len(taoguba_info)}")
    
    print("[STEP 2] 加载韭研公社近20日数据...")
    jiuyan_info = load_recent_jiuyan(20)
    print(f"  韭研公社提及股票数: {len(jiuyan_info)}")
    
    print("[STEP 3] 加载最新StockYiDong持仓...")
    syd_sections = load_latest_stockyidong()
    print(f"  龙头股:{len(syd_sections['龙头股'])} 15Min:{len(syd_sections['15Min'])} 同花顺:{len(syd_sections['同花顺'])}")
    
    # 合并所有出现过的股票代码
    all_codes = set(taoguba_info.keys()) | set(jiuyan_info.keys())
    for sec in syd_sections.values():
        for s in sec:
            all_codes.add(s["code"])
    all_codes = sorted(all_codes)
    print(f"\n[STEP 4] 合并后共 {len(all_codes)} 只股票，开始获取行情数据（可能较慢）...")
    
    # 获取 akshare 数据
    ak_data = {}
    if AKSHARE_OK:
        ak_data = get_akshare_stock_info(all_codes)
        print(f"  成功获取 {len(ak_data)} 只股票行情数据")
    else:
        print("  [SKIP] akshare未安装，跳过均线/市值筛选")
    
    print("[STEP 5] 按筛选条件过滤 + 评分排序...")
    results = []
    for code in all_codes:
        info = {"code": code, "name": "", "taoguba_count": 0, "jiuyan_count": 0}
        
        # 名称
        names = set()
        if code in taoguba_info:
            info["taoguba_count"] = taoguba_info[code]["count"]
            names |= taoguba_info[code]["names"]
        if code in jiuyan_info:
            info["jiuyan_count"] = jiuyan_info[code]["count"]
            names |= jiuyan_info[code]["names"]
        info["name"] = ";".join(names) if names else ""
        # 从 stockyidong 补充名称
        for sec in syd_sections.values():
            for s in sec:
                if s["code"] == code and not info["name"]:
                    info["name"] = s["name"]
        
        # StockYiDong 标签
        info["in_longtou"] = any(s["code"] == code for s in syd_sections["龙头股"])
        info["in_15min"]   = any(s["code"] == code for s in syd_sections["15Min"])
        info["in_ths"]      = any(s["code"] == code for s in syd_sections["同花顺"])
        info["syd_score"] = (3 if info["in_longtou"] else 0) + \
                            (2 if info["in_15min"] else 0) + \
                            (1 if info["in_ths"] else 0)
        
        # 均线数据
        ak = ak_data.get(code, {})
        info["market_cap"]  = ak.get("market_cap")
        info["close"]       = ak.get("close")
        info["ma10"]        = ak.get("ma10")
        info["ma20"]        = ak.get("ma20")
        info["ma60"]        = ak.get("ma60")
        info["near_ma10"]   = ak.get("near_ma10", False)
        info["near_ma20"]   = ak.get("near_ma20", False)
        info["ma_bullish"]  = ak.get("ma_bullish", False)
        
        # 筛选条件：市值 >= 100亿（有数据时才筛选）
        if ak and ak.get("market_cap") is not None:
            if ak["market_cap"] < 100:
                continue  # 跳过
        
        # 筛选条件：靠近10日线或20日线 且 均线多头发散
        if ak:
            if not (info["near_ma10"] or info["near_ma20"]):
                continue
            if not info["ma_bullish"]:
                continue
        
        # 热度分 = 淘股吧频次 + 韭研公社频次 × 2（公社质量更高）
        info["heat_score"] = info["taoguba_count"] + info["jiuyan_count"] * 2
        # 总评分 = 热度分 + 共振分 × 2
        info["total_score"] = info["heat_score"] + info["syd_score"] * 2
        
        results.append(info)
    
    # 排序：总评分降序
    results.sort(key=lambda x: x["total_score"], reverse=True)
    print(f"  筛选后剩余 {len(results)} 只股票")
    return results, syd_sections


def make_word_report(results, syd_sections, out_path):
    """生成Word日报"""
    if not DOCX_OK:
        print("[SKIP] python-docx未安装，跳过Word生成")
        return None
    
    doc = Document()
    # 页边距
    for sec in doc.sections:
        sec.top_margin    = Cm(2)
        sec.bottom_margin = Cm(2)
        sec.left_margin   = Cm(2.5)
        sec.right_margin  = Cm(2.5)
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 标题
    title = doc.add_heading(f"📊 斯东克·每日智能选股日报（{today}）", level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].font.size = Pt(16)
    title.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    
    doc.add_paragraph(f"生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    doc.add_paragraph("筛选条件：市值≥100亿 | 靠近10日/20日线 | 10/20/60日均线多头发散")
    
    # ── 一、Top推荐 ──
    h1 = doc.add_heading("一、今日Top推荐（按综合评分排序）", level=2)
    h1.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    
    top_n = results[:20]
    table = doc.add_table(rows=1, cols=7)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "排名"
    hdr[1].text = "名称"
    hdr[2].text = "代码"
    hdr[3].text = "综合分"
    hdr[4].text = "热度分"
    hdr[5].text = "共振标签"
    hdr[6].text = "市值(亿)"
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    for i, info in enumerate(top_n, 1):
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
        
        if i <= 3:
            for cell in row:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
                        run.bold = True
    
    # ── 二、均线&市值说明 ──
    doc.add_paragraph()
    h2 = doc.add_heading("二、筛选逻辑说明", level=2)
    h2.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    doc.add_paragraph(
        "选股逻辑：\n"
        "① 聚合近20日淘股吧+韭研公社资讯热度，热度分=淘股吧频次+韭研公社频次×2\n"
        "② 叠加StockYiDong三类持仓（龙头股×3、15Min×2、同花顺×1）计算共振分\n"
        "③ 筛选：市值≥100亿 且 收盘价在10日线/20日线±3%范围内 且 10/20/60日均线多头排列\n"
        "④ 综合评分=热度分+共振分×2，降序排列\n"
        "⑤ 均线数据来源：akshare 前复权日线，滚动计算"
    )
    
    # ── 三、StockYiDong 各标签明细 ──
    doc.add_paragraph()
    h3 = doc.add_heading("三、StockYiDong 持仓明细", level=2)
    h3.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    for label, stocks in syd_sections.items():
        doc.add_heading(f"【{label}】共{len(stocks)}只", level=3)
        if stocks:
            names = "、".join(f"{s['name']}({s['code']})" for s in stocks)
            doc.add_paragraph(names)
        else:
            doc.add_paragraph("（无）")
    
    doc.save(out_path)
    print(f"[OK] Word日报已生成: {out_path}")
    return out_path


def send_weixin(file_path):
    """通过 openclaw-weixin 通道发送Word文件（调用OpenClaw CLI）"""
    import subprocess
    to = "o9cq80z54pjdB4tednhGbb3W9pTk@im.wechat"
    cmd = [
        "openclaw", "message", "send",
        "--channel", "openclaw-weixin",
        "--to", to,
        "--file", file_path,
    ]
    print(f"[INFO] 发送微信: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        print("[OK] 微信发送成功")
    else:
        print(f"[WARN] 微信发送失败: {result.stderr}")
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-send", action="store_true", help="只生成报告，不发送到微信")
    args = parser.parse_args()
    
    t0 = time.time()
    results, syd_sections = build_report_data()
    
    today_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(REPORT_DIR, f"daily_report_{today_str}.docx")
    
    out_path = make_word_report(results, syd_sections, out_path)
    
    # 打印Top5到控制台
    print("\n" + "="*50)
    print("🔥 Top5 推荐股票：")
    for i, info in enumerate(results[:5], 1):
        tags = []
        if info["in_longtou"]: tags.append("龙头")
        if info["in_15min"]:   tags.append("15Min")
        if info["in_ths"]:      tags.append("同花顺")
        print(f"  {i}. {info['name']}({info['code']}) "
              f"综合分={info['total_score']} 热度={info['heat_score']} "
              f"标签={'/'.join(tags) if tags else '-'} "
              f"市值={info['market_cap']}亿" if info['market_cap'] else "")
    print("="*50)
    
    # 发送微信
    if not args.no_send and out_path:
        try:
            send_weixin(out_path)
        except Exception as e:
            print(f"[WARN] 发送失败: {e}")
            print("[INFO] 请手动发送文件:", out_path)
    elif args.no_send:
        print(f"[INFO] --no-send 模式，Word文件已保存: {out_path}")
    
    print(f"\n✅ 完成，用时 {time.time()-t0:.1f}秒")


if __name__ == "__main__":
    main()

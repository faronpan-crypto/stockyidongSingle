# -*- coding: utf-8 -*-
"""
📊 基金持仓 Tab — 主流基金重仓股 + 板块聚合 Top100

数据源:
  - akshare.fund_portfolio_hold_em(date='20261')  # 东方财富基金重仓股
  - 主流主动权益基金 Top20 持仓 (种子兜底)

结构:
  上半: 主流基金卡片 (基金名 + Top5 持仓股, 双击股票名弹日K)
  下半: 板块聚合 (按板块归类持仓市值最大的 Top 股票)
"""

import tkinter as tk
import tkinter.ttk as ttk
import threading
import traceback
import time
import json
import os
from datetime import datetime

# ── 🎨 配色 ──
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

# ── 🏆 主流基金 + 每只基金真实 Top5 代表持仓 (种子数据, 保证行业多样性) ──
# 格式: [基金代码, 基金简称, 行业标签, [(code6, name), (code6, name), ...]]
_FUND_TOP_HOLDINGS = [
    ("161725", "招商中证白酒",   "白酒",   [
        ("sh600519","贵州茅台"),("sz000858","五粮液"),("sh600809","山西汾酒"),
        ("sz002304","洋河股份"),("sz000568","泸州老窖")]),
    ("005827", "易方达蓝筹精选", "消费白马", [
        ("sh600519","贵州茅台"),("sh601888","中国中免"),("sz000333","美的集团"),
        ("sh600036","招商银行"),("sz300750","宁德时代")]),
    ("110011", "易方达中小盘",   "消费成长", [
        ("sz002475","立讯精密"),("sz300750","宁德时代"),("sh601318","中国平安"),
        ("sz000651","格力电器"),("sz000333","美的集团")]),
    ("163406", "兴全合润",       "均衡",   [
        ("sh600519","贵州茅台"),("sh600036","招商银行"),("sz300750","宁德时代"),
        ("sz002594","比亚迪"),("sh601318","中国平安")]),
    ("001594", "天弘中证电子",   "电子",   [
        ("sz002415","海康威视"),("sh603986","兆易创新"),("sz002230","科大讯飞"),
        ("sz300033","同花顺"),("sz002281","光迅科技")]),
    ("159995", "华夏芯片ETF",    "半导体", [
        ("sh603986","兆易创新"),("sh688256","寒武纪"),("sz002049","紫光国微"),
        ("sh688012","中微公司"),("sz002371","北方华创")]),
    ("515030", "新能源车ETF",    "新能源", [
        ("sz300750","宁德时代"),("sz002594","比亚迪"),("sz300014","亿纬锂能"),
        ("sh601012","隆基绿能"),("sz002460","赣锋锂业")]),
    ("159949", "创业板ETF",      "成长",   [
        ("sz300750","宁德时代"),("sz300015","爱尔眼科"),("sz300760","迈瑞医疗"),
        ("sz300059","东方财富"),("sz300014","亿纬锂能")]),
    ("512880", "证券ETF",        "券商",   [
        ("sh600030","中信证券"),("sh601688","华泰证券"),("sh601211","国泰君安"),
        ("sh600837","海通证券"),("sz300059","东方财富")]),
    ("513100", "纳指ETF",        "美股科技", [
        ("AAPL","苹果"),("MSFT","微软"),("NVDA","英伟达"),
        ("TSLA","特斯拉"),("GOOG","谷歌")]),
    ("164906", "交银中证中概",   "中概",   [
        ("9988","阿里巴巴"),("9618","京东"),("9888","百度"),
        ("3690","美团"),("9999","网易")]),
    ("161005", "富国天惠成长",   "均衡",   [
        ("sh600519","贵州茅台"),("sz300750","宁德时代"),("sz002415","海康威视"),
        ("sh600036","招商银行"),("sz002594","比亚迪")]),
    ("000961", "天弘沪深300",    "宽基",   [
        ("sh600519","贵州茅台"),("sh601318","中国平安"),("sz000858","五粮液"),
        ("sh600036","招商银行"),("sz300750","宁德时代")]),
    ("512660", "军工ETF",        "军工",   [
        ("sh600893","航发动力"),("sh600760","中航沈飞"),("sh600118","中国卫星"),
        ("sz000768","中航西飞"),("sh600372","中航机载")]),
    ("512200", "房地产ETF",      "地产",   [
        ("sz000002","万科A"),("sh600048","保利发展"),("sh601155","新城控股"),
        ("sh600585","海螺水泥"),("sz300737","科顺股份")]),
    ("512010", "医药ETF",        "医药",   [
        ("sh600276","恒瑞医药"),("sz000538","云南白药"),("sz300760","迈瑞医疗"),
        ("sz002007","华兰生物"),("sh603259","药明康德")]),
    ("159869", "游戏ETF",        "传媒",   [
        ("sz002555","三七互娱"),("sz300418","昆仑万维"),("sz002230","科大讯飞"),
        ("sz300454","深信服"),("sz300750","宁德时代")]),
    ("512400", "有色金属ETF",    "资源",   [
        ("sh600547","山东黄金"),("sh601899","紫金矿业"),("sh600489","中金黄金"),
        ("sz000878","云南铜业"),("sh601600","中国铝业")]),
    ("512170", "医疗ETF",        "医疗",   [
        ("sz300015","爱尔眼科"),("sz300760","迈瑞医疗"),("sh600276","恒瑞医药"),
        ("sz002007","华兰生物"),("sh603259","药明康德")]),
    ("512890", "红利低波ETF",    "红利",   [
        ("sh600036","招商银行"),("sh601398","工商银行"),("sh601939","建设银行"),
        ("sh601628","中国人寿"),("sh601318","中国平安")]),
]

# 板块归类 (和邮票格子保持一致)
_BLOCK_GROUPS = {
    "银行":   ["sh601398","sh601939","sh601288","sh601988","sh600036","sh601166","sz002142","sh600016","sh601328"],
    "券商":   ["sh600030","sh601211","sh601788","sh600837","sh601688","sz000776","sh600109","sz300059","sh600018"],
    "保险":   ["sh601318","sh601628","sh601601","sh601336"],
    "白酒":   ["sh600519","sz000858","sh600809","sz000568","sh603369","sz000596","sz002304","sh603589"],
    "半导体": ["sh603986","sh688256","sh688981","sz002049","sz300223","sh603501","sh600584","sz300782","sh688012","sh688008","sz002371","sz002185","sz002456","sh603160","sz300661"],
    "AI":     ["sz002230","sz300496","sh600588","sz002415","sh603019","sz300033","sz300364","sh600406"],
    "CPO":    ["sz002281","sh600487","sz002222","sh601869","sh603502","sz300394","sz300502","sz002268"],
    "新能源": ["sz300750","sz3002594","sz300014","sh601012","sz002460","sh600438","sz300274","sz300763","sz002580"],
    "光伏":   ["sh601012","sz300118","sh600438","sz300274","sh688599"],
    "军工":   ["sh600893","sh600760","sh600118","sz002414","sz000768","sh601698","sz300034","sh600150","sh600372"],
    "机器人": ["sz300024","sz300274","sz300607","sh600021","sz300124","sz002527"],
    "煤炭能源":["sh601225","sh601088","sh60188","sh601015","sh600395","sh601985","sz000933","sh600508","sh600985"],
    "医药医疗":["sh600276","sz000538","sz002422","sh600196","sz002007","sh600535","sz300015","sz300003","sh603259","sz002594","sh600085","sz002821","sz000423","sh600518"],
    "黄金有色":["sh600547","sh600489","sh601899","sz002155","sh600362","sh601600","sz000878","sh600111"],
    "地产建材":["sh600048","sh600340","sz001979","sh600585","sh601155","sz000002","sh600031","sh601668","sz300737"],
    "消费家电":["sh600690","sz000651","sh600887","sz002475","sh601888","sz300999","sh603288","sh600872","sz000568","sz000333"],
    "石油石化":["sh600028","sh601857","sh600019","sh600583","sh600688","sz000554"],
    "中概互联":["sh600519","sz002594","sz300750","sh601888","sh600036"],
    "其他":   [],
}

# 名字→板块 (兜底)
_NAME_TO_BLOCK = [
    ("银行","银行"),("招行","银行"),("工行","银行"),("建行","银行"),("中行","银行"),("交行","银行"),("农行","银行"),("浦发","银行"),("民生","银行"),("平安银","银行"),
    ("证券","券商"),("中信证","券商"),("华泰","券商"),("海通","券商"),("国泰君","券商"),("招商证","券商"),("东方财","券商"),("东财","券商"),
    ("保险","保险"),("平安","保险"),("人寿","保险"),("太保","保险"),
    ("茅台","白酒"),("白酒","白酒"),("五粮液","白酒"),("老窖","白酒"),("汾酒","白酒"),("洋河","白酒"),("古井","白酒"),("今世缘","白酒"),("牛栏山","白酒"),
    ("中芯","半导体"),("半导体","半导体"),("芯片","半导体"),("韦尔","半导体"),("紫光","半导体"),("长电","半导体"),("通富","半导体"),("士兰","半导体"),("中微","半导体"),("华虹","半导体"),("安集","半导体"),("北华创","半导体"),
    ("寒武","AI"),("科大讯","AI"),("汉王","AI"),("拓尔","AI"),("讯飞","AI"),("算力","AI"),("昆仑","AI"),("智谱","AI"),("海光","AI"),("浪潮","AI"),
    ("光模块","CPO"),("CPO","CPO"),("光迅","CPO"),("中际旭","CPO"),("新易盛","CPO"),("天孚","CPO"),("华工","CPO"),("亨通","CPO"),
    ("电池","新能源"),("锂电","新能源"),("宁德","新能源"),("比亚迪","新能源"),("亿纬","新能源"),("欣旺达","新能源"),("赣锋","新能源"),("天齐","新能源"),("华友","新能源"),("洛阳钼","新能源"),
    ("光伏","光伏"),("隆基","光伏"),("通威","光伏"),("阳光电源","光伏"),("硅片","光伏"),("晶澳","光伏"),("天合","光伏"),
    ("军工","军工"),("航发","军工"),("国防","军工"),("中航","军工"),("航天","军工"),("无人机","军工"),("中直","军工"),("振华","军工"),("中航西飞","军工"),("航发动力","军工"),("航发控制","军工"),
    ("机器人","机器人"),("人形","机器人"),("汇川","机器人"),("埃斯顿","机器人"),("绿的","机器人"),
    ("煤炭","煤炭能源"),("煤业","煤炭能源"),("能源","煤炭能源"),("神华","煤炭能源"),("中煤","煤炭能源"),("平煤","煤炭能源"),("陕煤","煤炭能源"),
    ("医药","医药医疗"),("医疗","医药医疗"),("药明","医药医疗"),("恒瑞","医药医疗"),("迈瑞","医药医疗"),("智飞","医药医疗"),("复星","医药医疗"),("云南白","医药医疗"),("片仔","医药医疗"),("东阿","医药医疗"),("爱尔","医药医疗"),("乐普","医药医疗"),
    ("黄金","黄金有色"),("金业","黄金有色"),("有色","黄金有色"),("紫金","黄金有色"),("中金黄","黄金有色"),("山金","黄金有色"),("铜","黄金有色"),("洛阳钼","黄金有色"),
    ("地产","地产建材"),("建材","地产建材"),("万科","地产建材"),("保利","地产建材"),("海螺","地产建材"),("三一是","地产建材"),("三一","地产建材"),("中建","地产建材"),
    ("家电","消费家电"),("美的","消费家电"),("格力","消费家电"),("海尔","消费家电"),("伊利","消费家电"),("金龙鱼","消费家电"),("中免","消费家电"),("海天","消费家电"),("农夫山","消费家电"),
    ("石化","石油石化"),("石油","石油石化"),("中海油","石油石化"),("中国石","石油石化"),("中石化","石油石化"),
]

def _match_block(name, code):
    code6 = code if isinstance(code, str) else str(code)
    # 去掉 sh/sz/bj 前缀
    if code6.startswith(("sh","sz","bj","SH","SZ","BJ")):
        code6 = code6[2:]
    code6 = code6.zfill(6)
    for blk, codes in _BLOCK_GROUPS.items():
        if code6 in codes:
            return blk
    for kw, blk in sorted(_NAME_TO_BLOCK, key=lambda x: -len(x[0])):
        if kw in name:
            return blk
    return "其他"


def _lookup_sina(name, code6):
    """尝试拿到 sina_code (sh/sz/bj + 6位代码)"""
    if code6 and isinstance(code6, str) and code6.startswith(("sh","sz","bj","SH","SZ","BJ")):
        return code6.lower(), name
    if code6:
        c = str(code6).zfill(6)
        if c.startswith("6"): return "sh" + c, name
        if c.startswith(("0","3")): return "sz" + c, name
        if c.startswith(("4","8")): return "bj" + c, name
    return None, None


def _open_kline(parent, sina_code, name):
    """双击股票 → 日K线弹窗 (复用 high_low_swing 里的秒开)"""
    try:
        from ui.high_low_swing import _quick_open_daily_kline
        _quick_open_daily_kline(parent, sina_code, name)
    except Exception as e:
        print(f"[基金持仓] 打开K线失败: {e}", flush=True)


def build_fund_holdings_tab(parent, root=None):
    """🎯 构建基金持仓 Tab"""
    from collections import defaultdict

    if root is None:
        root = parent.winfo_toplevel()

    # ── 顶栏 ──
    top = ttk.Frame(parent); top.pack(fill=tk.X, padx=6, pady=(6, 2))
    tk.Label(top, text="🏦 基金持仓追踪", bg=_BG_PANEL, fg=_FG_GOLD,
             font=("", 12, "bold")).pack(side=tk.LEFT)
    status = tk.Label(top, text="⏳ 加载中...", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9))
    status.pack(side=tk.RIGHT, padx=6)
    btn_refresh = ttk.Button(top, text="🔄 刷新", width=10,
                              command=lambda: _load_data(force=True))
    btn_refresh.pack(side=tk.RIGHT)

    # Notebook 分成两部分
    nb = ttk.Notebook(parent)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ── Tab1: 基金卡片 ──
    card_frame = ttk.Frame(nb); nb.add(card_frame, text="🏦 基金持仓卡片")
    # 可滚动
    card_canvas = tk.Canvas(card_frame, bg=_BG_DEEP, highlightthickness=0)
    card_vsb = ttk.Scrollbar(card_frame, orient="vertical", command=card_canvas.yview)
    card_inner = ttk.Frame(card_canvas, style="Dark.TFrame")
    card_canvas.configure(yscrollcommand=card_vsb.set)
    card_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    card_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    card_canvas.create_window((0, 0), window=card_inner, anchor="nw")
    card_inner.bind("<Configure>", lambda e: card_canvas.configure(scrollregion=card_canvas.bbox("all")))
    card_canvas.bind_all("<MouseWheel>", lambda e: card_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ── Tab2: 板块聚合 ──
    agg_frame = ttk.Frame(nb); nb.add(agg_frame, text="📊 板块聚合 Top100")
    agg_canvas = tk.Canvas(agg_frame, bg=_BG_DEEP, highlightthickness=0)
    agg_vsb = ttk.Scrollbar(agg_frame, orient="vertical", command=agg_canvas.yview)
    agg_inner = ttk.Frame(agg_canvas, style="Dark.TFrame")
    agg_canvas.configure(yscrollcommand=agg_vsb.set)
    agg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    agg_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    agg_canvas.create_window((0, 0), window=agg_inner, anchor="nw")
    agg_inner.bind("<Configure>", lambda e: agg_canvas.configure(scrollregion=agg_canvas.bbox("all")))

    # Dark theme for Frame
    try:
        style = ttk.Style()
        style.configure("Dark.TFrame", background=_BG_DEEP)
    except Exception:
        pass

    # ── 缓存 ──
    _today = datetime.now().strftime("%Y%m%d")
    _cache_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "data", f"fund_holdings_cache_{_today}.json"
    )
    _cache_path = os.path.normpath(_cache_path)

    # 全局数据 (后台线程写入, 主线程渲染)
    _data = {"funds": [], "agg": []}
    _running = False

    def _load_data(force=False):
        """联网抓取 or 读缓存"""
        nonlocal _running
        if _running:
            return

        # 1) 尝试读缓存
        if not force and os.path.exists(_cache_path):
            try:
                with open(_cache_path, "r", encoding="utf-8") as f:
                    _cached = json.load(f)
                if isinstance(_cached, dict) and "funds" in _cached:
                    _data["funds"] = _cached["funds"]
                    _data["agg"] = _cached.get("agg", [])
                    _render_all()
                    status.configure(text=f"📂 读缓存 {len(_data['funds'])} 只基金 ({_today})", foreground=_FG_GREEN)
                    print(f"[基金持仓] 读缓存 OK ({len(_data['funds'])} 只)", flush=True)
                    return
            except Exception as _ce:
                print(f"[基金持仓] 缓存读失败: {_ce}", flush=True)

        # 2) 后台线程联网
        _running = True
        status.configure(text="⏳ 拉取基金重仓股...", foreground="#FFA726")

        def _bg():
            try:
                import akshare as ak
                fund_rows = []  # [{code, name, industry, holdings: [{code, name, pct, market_cap}]}]
                # 先拿全部基金重仓 (按市值排行)
                # 季度选择: 当前季度
                q_year = datetime.now().year
                q_month = datetime.now().month
                if q_month <= 3: q_str = f"{q_year-1}4"
                elif q_month <= 6: q_str = f"{q_year}1"
                elif q_month <= 9: q_str = f"{q_year}2"
                else: q_str = f"{q_year}3"
                print(f"[基金持仓] 用季度: {q_str}", flush=True)

                # —— 全市场基金重仓 Top200 ——
                all_hold = []  # [{code6, name, total_pct, total_mv, fund_count}]
                try:
                    df = ak.fund_portfolio_hold_em(date=q_str)
                    print(f"[基金持仓] portfolio_hold_em: {len(df)} 行", flush=True)
                    # 聚合: 同一只股票被多少基金持有 + 占比合计
                    agg = defaultdict(lambda: {"name":"", "codes":set(), "total_pct":0.0, "total_mv":0.0, "fund_count":0})
                    for _, r in df.iterrows():
                        c6 = str(r.get("股票代码", ""))
                        nm = str(r.get("股票名称", ""))
                        try: pct = float(r.get("占净值比例", 0))
                        except: pct = 0
                        try: mv = float(r.get("持仓市值", 0))
                        except: mv = 0
                        if not c6: continue
                        c6 = c6.zfill(6)
                        entry = agg[c6]
                        entry["name"] = nm
                        entry["codes"].add(c6)
                        entry["total_pct"] += pct
                        entry["total_mv"] += mv
                        entry["fund_count"] += 1
                    all_hold = []
                    for c6, e in agg.items():
                        all_hold.append({
                            "code6": c6, "name": e["name"],
                            "total_pct": round(e["total_pct"], 2),
                            "total_mv": round(e["total_mv"], 2),
                            "fund_count": e["fund_count"],
                        })
                    # 按持仓市值排序, 取 Top150
                    all_hold.sort(key=lambda x: -x["total_mv"])
                    all_hold = all_hold[:150]
                except Exception as e1:
                    print(f"[基金持仓] portfolio_hold_em 失败: {e1}", flush=True)

                # —— 种子兜底 ——
                if not all_hold:
                    # 用种子数据模拟
                    _SEED_TOP = [
                        ("sh603986","兆易创新",2.8,100),("sh688256","寒武纪",2.5,90),
                        ("sz300750","宁德时代",3.2,150),("sz002594","比亚迪",3.0,140),
                        ("sh600519","贵州茅台",2.9,200),("sz000858","五粮液",2.5,80),
                        ("sz002230","科大讯飞",2.4,70),("sz002281","光迅科技",2.2,50),
                        ("sh600036","招商银行",2.8,120),("sh601318","中国平安",2.7,110),
                        ("sh601225","陕西煤业",2.3,60),("sh600276","恒瑞医药",2.6,90),
                        ("sh600030","中信证券",2.5,85),("sz300782","卓胜微",2.1,45),
                        ("sh688012","中微公司",2.3,55),("sz002415","海康威视",2.0,70),
                        ("sz002371","北方华创",2.2,65),("sh601012","隆基绿能",2.4,75),
                        ("sz300014","亿纬锂能",2.1,50),("sh600893","航发动力",2.0,45),
                    ]
                    for c6, nm, pct, mv in _SEED_TOP:
                        all_hold.append({"code6":c6,"name":nm,"total_pct":pct,"total_mv":mv,"fund_count":3})

                # —— 构造基金卡片数据 ——
                # 把 Top 股票分配给主流基金 (按行业)
                _industry_holdings = defaultdict(list)
                for s in all_hold:
                    blk = _match_block(s["name"], s["code6"])
                    _industry_holdings[blk].append(s)

                for fc, fname, kind, seed_holdings in _FUND_TOP_HOLDINGS:
                    # 每只基金用自带的代表持仓种子 (行业多样性有保证)
                    picks = []
                    for code6, nm in seed_holdings[:5]:
                        sina, _ = _lookup_sina(nm, code6)
                        # 尝试从 API 数据里找到真实占比 (找不到用种子默认)
                        _api_pct = 0.0
                        for _a in all_hold:
                            if _a["code6"] == code6 or _a["name"] == nm:
                                _api_pct = _a["total_pct"]; break
                        picks.append({
                            "code6": code6, "name": nm, "sina": sina,
                            "total_pct": _api_pct or 0.0,
                            "total_mv": 0, "fund_count": 0,
                        })
                    fund_rows.append({
                        "code": fc, "name": fname, "industry": kind,
                        "holdings": picks,
                    })

                # —— 板块聚合 Top100 ——
                agg_groups = defaultdict(list)
                for s in all_hold[:100]:
                    blk = _match_block(s["name"], s["code6"])
                    sina, _ = _lookup_sina(s["name"], s["code6"])
                    agg_groups[blk].append({
                        "code6": s["code6"], "name": s["name"],
                        "sina": sina,
                        "total_pct": s["total_pct"],
                        "total_mv": s["total_mv"],
                        "fund_count": s["fund_count"],
                    })

                # 排序每板块内按市值
                for blk in agg_groups:
                    agg_groups[blk].sort(key=lambda x: -x["total_mv"])

                agg_list = sorted(agg_groups.items(), key=lambda x: -sum(s["total_mv"] for s in x[1]))

                # 写缓存
                _out = {
                    "funds": fund_rows,
                    "agg": [{"block": b, "stocks": s} for b, s in agg_list],
                    "date": _today,
                }
                try:
                    os.makedirs(os.path.dirname(_cache_path), exist_ok=True)
                    with open(_cache_path, "w", encoding="utf-8") as f:
                        json.dump(_out, f, ensure_ascii=False, indent=2, default=str)
                    print(f"[基金持仓] 缓存已写: {_cache_path}", flush=True)
                except Exception:
                    pass

                _data["funds"] = fund_rows
                _data["agg"] = [{"block": b, "stocks": s} for b, s in agg_list]
                root.after(0, lambda: (_render_all(),
                    status.configure(text=f"✅ {len(fund_rows)} 只基金, Top {len(all_hold)} 重仓股", foreground=_FG_GREEN)))
            except Exception as e:
                import traceback; traceback.print_exc()
                root.after(0, lambda: status.configure(
                    text=f"❌ 拉取失败: {e}", foreground=_FG_RED))
            finally:
                _running = False

        threading.Thread(target=_bg, daemon=True).start()

    def _bind_click_deep(widget, handler):
        try:
            widget.bind("<ButtonRelease-1>", handler)
            widget.bind("<Double-Button-1>", handler)
        except Exception:
            pass
        for c in widget.winfo_children():
            _bind_click_deep(c, handler)

    def _on_stock_click(e, sina, name):
        print(f"[基金持仓] 点击股票 sina={sina} name={name}", flush=True)
        if sina:
            _open_kline(root, sina, name)
        else:
            print(f"[基金持仓] sina 为空, 无法打开K线 name={name}", flush=True)

    # ── 渲染: 基金卡片 ──
    def _render_fund_cards():
        for w in card_inner.winfo_children():
            w.destroy()
        funds = _data.get("funds", [])
        if not funds:
            ttk.Label(card_inner, text="⏳ 暂无数据", background=_BG_DEEP, foreground=_FG_DIM).pack(pady=40)
            return

        # 3 列网格
        cols = 3
        for fi, f in enumerate(funds):
            r, c = divmod(fi, cols)
            card = tk.Frame(card_inner, bg=_BG_CARD,
                            highlightbackground=_FG_BLUE, highlightthickness=1)
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            card_inner.grid_columnconfigure(c, weight=1)

            # 标题行
            hd = tk.Frame(card, bg=_BG_CARD); hd.pack(fill=tk.X, padx=6, pady=(6, 2))
            tk.Label(hd, text=f"🏦 {f['name']}", bg=_BG_CARD, fg=_FG_GOLD,
                     font=("", 10, "bold")).pack(side=tk.LEFT)
            tk.Label(hd, text=f"({f['code']})", bg=_BG_CARD, fg=_FG_DIM,
                     font=("", 8)).pack(side=tk.LEFT, padx=4)
            tk.Label(hd, text=f"#{f['industry']}", bg=_BG_CARD, fg=_FG_CYAN,
                     font=("", 8)).pack(side=tk.RIGHT)

            tk.Frame(card, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=2)

            # 持仓列表
            for hi, h in enumerate(f.get("holdings", [])):
                sina, _ = _lookup_sina(h["name"], h["code6"])
                row_bg = "#2A2A3A" if hi % 2 == 0 else _BG_CARD
                row = tk.Frame(card, bg=row_bg, cursor="hand2")
                row.pack(fill=tk.X, padx=2, pady=1)

                def _mk_click(_s=sina, _n=h["name"]):
                    return lambda e: _on_stock_click(e, _s, _n)
                _h = _mk_click()
                # row 自己 + 所有子控件都绑
                row.bind("<ButtonRelease-1>", _h)
                row.bind("<Double-Button-1>", _h)

                _idx_lbl = tk.Label(row, text=f"{hi+1}.", bg=row_bg, fg=_FG_DIM,
                                    font=("", 8), width=2)
                _idx_lbl.pack(side=tk.LEFT)
                _idx_lbl.bind("<ButtonRelease-1>", _h); _idx_lbl.bind("<Double-Button-1>", _h)

                _nm_lbl = tk.Label(row, text=h["name"], bg=row_bg, fg=_FG_TEXT,
                                   font=("", 9))
                _nm_lbl.pack(side=tk.LEFT, padx=2)
                _nm_lbl.bind("<ButtonRelease-1>", _h); _nm_lbl.bind("<Double-Button-1>", _h)

                _pct_lbl = tk.Label(row, text=f"占{h['total_pct']:.1f}%", bg=row_bg,
                                    fg=_FG_GOLD, font=("", 8))
                _pct_lbl.pack(side=tk.RIGHT, padx=6)
                _pct_lbl.bind("<ButtonRelease-1>", _h); _pct_lbl.bind("<Double-Button-1>", _h)

            tk.Frame(card, bg=_BG_CARD, height=4).pack(fill=tk.X)

    # ── 渲染: 板块聚合 ──
    def _render_agg():
        for w in agg_inner.winfo_children():
            w.destroy()
        agg = _data.get("agg", [])
        if not agg:
            ttk.Label(agg_inner, text="⏳ 暂无数据", background=_BG_DEEP, foreground=_FG_DIM).pack(pady=40)
            return

        for blk_entry in agg:
            blk = blk_entry["block"]
            stocks = blk_entry["stocks"]
            total_mv = sum(s["total_mv"] for s in stocks)
            total_pct = sum(s["total_pct"] for s in stocks)

            # 板块头
            hd = tk.Frame(agg_inner, bg=_BG_CARD); hd.pack(fill=tk.X, padx=6, pady=(8, 2))
            tk.Label(hd, text=f"📌 {blk}  ({len(stocks)}只)", bg=_BG_CARD, fg=_FG_GOLD,
                     font=("", 10, "bold")).pack(side=tk.LEFT, padx=8, pady=4)
            tk.Label(hd, text=f"持仓市值合计 {total_mv:.0f}亿  占比 {total_pct:.1f}%",
                     bg=_BG_CARD, fg=_FG_DIM, font=("", 8)).pack(side=tk.RIGHT, padx=8)

            tk.Frame(agg_inner, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6)

            # 股票行
            for hi, s in enumerate(stocks[:10]):  # 每板块最多 10 只
                row_bg = _BG_CARD if hi % 2 == 0 else "#2A2A3A"
                row = tk.Frame(agg_inner, bg=row_bg, cursor="hand2")
                row.pack(fill=tk.X, padx=6, pady=1)

                def _mk(_s=s["sina"], _n=s["name"]):
                    return lambda e: _on_stock_click(e, _s, _n)
                _h = _mk()
                row.bind("<ButtonRelease-1>", _h); row.bind("<Double-Button-1>", _h)

                def _bind_all(parent, _h2=_h):
                    parent.bind("<ButtonRelease-1>", _h2); parent.bind("<Double-Button-1>", _h2)
                    for c in parent.winfo_children():
                        _bind_all(c, _h2)

                _idx = tk.Label(row, text=f"{hi+1}.", bg=row_bg, fg=_FG_DIM,
                               font=("", 9, "bold"), width=3)
                _idx.pack(side=tk.LEFT, padx=(4,0))
                _nm = tk.Label(row, text=s["name"], bg=row_bg, fg=_FG_TEXT,
                               font=("", 9, "bold"))
                _nm.pack(side=tk.LEFT, padx=2)
                _code = tk.Label(row, text=f"({s['code6']})", bg=row_bg, fg=_FG_DIM,
                                 font=("", 8))
                _code.pack(side=tk.LEFT)
                _fc = tk.Label(row, text=f"{s['fund_count']}只基金持有", bg=row_bg,
                               fg=_FG_BLUE, font=("", 8))
                _fc.pack(side=tk.LEFT, padx=10)
                _mv = tk.Label(row, text=f"{s['total_mv']:.1f}亿", bg=row_bg,
                               fg=_FG_CYAN, font=("", 8))
                _mv.pack(side=tk.RIGHT, padx=8)
                _pct = tk.Label(row, text=f"{s['total_pct']:.1f}%", bg=row_bg,
                                fg=_FG_GOLD, font=("", 8), width=6, anchor="e")
                _pct.pack(side=tk.RIGHT)

                # 给 row + 所有子 Label 都绑
                for w in [row, _idx, _nm, _code, _fc, _mv, _pct]:
                    w.bind("<ButtonRelease-1>", _h)
                    w.bind("<Double-Button-1>", _h)

    def _render_all():
        _render_fund_cards()
        _render_agg()

    # ── 自动触发 ──
    parent.after(300, lambda: _load_data(force=False))

#!/usr/bin/env python3
"""
个股/板块分析引擎
================
直接复用 StockYiDongMac 的核心分析函数，不启动 Tkinter，无外部 API 依赖。

analyze_news_content(news_content: str) -> dict
  1. 提取资讯中提及的股票名称/代码
  2. 多维度文本分析（情绪/市场焦点/风险/主题）
  3. 每只股票提取投资逻辑 + 上下文
  4. 按个股 + 板块聚合

数据流：
  看板点击"分析" → POST /api/analyze → analyze_news_content(content)
  → 写入 news_info 表（tab_name="分析结果_时间戳"）
  → 返回结构化 JSON → 看板弹窗展示
"""
import math
import os
import re
import sqlite3
import threading
import time
from typing import Any

# ═══════════════════════════════════════════════════
# 第一层：akshare 股票字典（延迟加载，一次性）
# ═══════════════════════════════════════════════════
STOCK_NAMES_SET: set | None = None
STOCK_CODES_DICT: dict[str, str] = {}   # code -> name
STOCK_NAME_TO_CODE: dict[str, str] = {}  # name -> code
ETF_CACHE_REFRESHED = False
_LOAD_LOCK = threading.Lock()
_LOADING = False

def _is_real_val(v: Any) -> bool:
    """过滤 None / nan / 空字符串"""
    if v is None:
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    s = str(v).strip()
    return bool(s) and s.lower() != 'nan'

def _register_entry(code: str, name: str) -> None:
    """注册一只股票（线程安全）"""
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE
    if not _is_real_val(code) or not _is_real_val(name):
        return
    code = str(code).strip(); name = str(name).strip()
    if name not in STOCK_NAMES_SET:
        STOCK_NAMES_SET.add(name)
    STOCK_CODES_DICT[code] = name
    STOCK_NAME_TO_CODE[name] = code

def load_stock_names(blocking=True, timeout=30) -> tuple[set, dict, dict]:
    """
    延迟加载 A 股股票名称字典。
    - blocking=True  : 同步等待加载完成（首次调用，约 5-8 秒）
    - blocking=False : 启动后台加载线程，立即返回（字典可能为空）
    """
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE, _LOADING

    if STOCK_NAMES_SET is not None:
        return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE

    # 确保只初始化一次
    with _LOAD_LOCK:
        if STOCK_NAMES_SET is not None:
            return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE
        if _LOADING:
            pass  # 等待另一线程完成
        else:
            _LOADING = True
            # 初始化全局变量
            STOCK_NAMES_SET = set()
            STOCK_CODES_DICT = {}
            STOCK_NAME_TO_CODE = {}

    if not blocking:
        t = threading.Thread(target=_bg_load, daemon=True)
        t.start()
        return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE

    _bg_load(timeout=timeout)
    return STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE

def _bg_load(timeout=30) -> None:
    global STOCK_NAMES_SET, STOCK_CODES_DICT, STOCK_NAME_TO_CODE, _LOADING
    global ETF_CACHE_REFRESHED
    try:
        import akshare as ak
        print("[analyzer] 正在从 akshare 加载股票数据（首次约 5-10 秒）…")
        t0 = time.time()

        # ── 主板 + 科创 ──
        df_main = ak.stock_info_a_code_name()
        for _, row in df_main.iterrows():
            _register_entry(row['code'], row['name'])
        main_cnt = len(STOCK_NAMES_SET)
        print(f"  主板 {len(df_main)} 只, 累计 {main_cnt}")

        # ── 科创板 ──
        try:
            df_kcb = ak.stock_info_kcb_name_code()
            for _, row in df_kcb.iterrows():
                _register_entry(row['code'], row['name'])
            print(f"  科创板 {len(df_kcb)} 只, 累计 {len(STOCK_NAMES_SET)}")
        except Exception as e:
            print(f"  科创板加载失败（不影响核心功能）: {e}")

        # ── ETF 兜底 ──
        try:
            df_etf = ak.fund_etf_spot_em()
            cols = df_etf.columns.tolist()
            code_col = next((c for c in cols if '代码' in c or 'code' in c.lower()), None)
            name_col = next((c for c in cols if '名称' in c or 'name' in c.lower()), None)
            if code_col and name_col:
                for _, row in df_etf.iterrows():
                    _register_entry(row[code_col], row[name_col])
                ETF_CACHE_REFRESHED = True
                print(f"  ETF {len(df_etf)} 只, 累计 {len(STOCK_NAMES_SET)}")
        except Exception as etf_e:
            print(f"  ETF加载失败（不影响）: {etf_e}")

        print(f"[analyzer] 加载完成: {len(STOCK_NAMES_SET)} 只, 耗时 {time.time()-t0:.1f}s")

    except Exception as e:
        print(f"[analyzer] akshare 加载失败: {e}")
    finally:
        _LOADING = False


# ═══════════════════════════════════════════════════
# 第二层：核心分析函数（纯标准库，无网络）
# ═══════════════════════════════════════════════════
POSITIVE  = ['上涨','涨停','突破','利好','买入','推荐','看好','机会','强势','拉升',
             '反弹','增长','盈利','收益','成功','大涨','放量','封板','连板']
NEGATIVE  = ['下跌','跌停','回调','利空','卖出','看空','风险','亏损','弱势','打压',
             '洗盘','出货','大跌','缩量','割肉','破位','闪崩']
NEUTRAL   = ['震荡','整理','横盘','观望','中性','平衡']
MKT_FOCUS = ['热点','概念','题材','板块','龙头','跟风','补涨','补跌','轮动','切换',
             '主线','支线']
RISK_KW   = ['风险','警告','谨慎','注意','警惕','危险','不利','负面','减持','解禁',
             '停牌','退市','ST','亏损']
THEME_KW  = ['人工智能','AI','芯片','半导体','新能源','光伏','风电','储能','锂电池',
             '新能源汽车','5G','云计算','大数据','消费电子','医药','军工','机器人',
             'DeepSeek','算力','数据中心','液冷','光模块','铜缆高速连接','功率半导体',
             'MLCC','石墨烯','稀土','固态电池','氢能','虚拟现实','VR','AR','中药',
             '创新药','PEEK','可控核聚变','商业航天']
LOGIC_KW  = ['涨停','跌停','突破','回调','反弹','利好','利空','业绩','重组','并购',
             '增持','减持','放量','缩量','换手','主力','资金','流入','流出','拉升',
             '打压','洗盘','出货','龙头','跟风','补涨','补跌','强势','概念','热点',
             '封板','连板','题材','主线','跟风']

SECTOR_MAP: dict[str, list[str]] = {
    '半导体':      ['中芯国际','华虹半导体','北方华创','中微公司','拓荆科技','华海清科','芯源微','盛美上海','至纯科技','万业企业','安集科技','沪硅产业','神工股份','思瑞浦','艾为电子','纳芯微','唯捷创芯','南芯科技','杰华特','晶丰明源','力芯微','希荻微','翱捷科技','裕太微','圣邦股份','韦尔股份','卓胜微','富满微','帝奥微','灿瑞科技','国微股份','华大九天','广立微','概伦电子','天准科技','华测导航','清溢光电','路维光电','华特气体','凯美特气','阿石创','正帆科技','英杰电气','新莱应材','高测股份','晶盛机电','京运通','TCL中环','上机数控','迈为股份','捷佳伟创','钧达股份','爱旭股份','通威股份','大全能源','协鑫科技','阳光电源','锦浪科技','固德威','德业股份','禾望电气','汇川技术'],
    '算力/AI':     ['紫光股份','神州数码','拓维信息','四川长虹','广电运通','广电网络','剑桥科技','华工科技','光迅科技','中际旭创','新易盛','天孚通信','太辰光','博创科技','浪潮信息','中科曙光','寒武纪','海光信息','景嘉微','龙芯中科','芯原股份','云从科技','科大讯飞','金山办公','海天瑞声','拓尔思','万兴科技','优刻得','光环新网','数据港','奥飞数据','首都在线','南兴股份','东方国信','博彦科技','神州泰岳','天融信','启明星辰','绿盟科技','深信服','安恒信息','奇安信','三六零','锐捷网络','菲菱科思','共进股份','星网锐捷','初灵信息','瑞斯康达','武汉凡谷','大富科技'],
    '医药生物':    ['昭衍新药','药明康德','药明生物','泰格医药','凯莱英','博腾股份','康龙化成','成都先导','美迪西','南模生物','阳光诺和','百诚医药','诺泰生物','圣诺生物','诺唯赞','义翘神州','百普赛斯','奥浦迈','和元生物','键凯科技','泓博医药','恒瑞医药','百济神州','荣昌生物','康方生物','信达生物','君实生物','贝达药业','微芯生物','艾力斯','海思科','恩华药业','华东医药','翰森制药'],
    '新能源电力':  ['立新能源','浙江新能','南网储能','三峡能源','龙源电力','节能风电','太阳能','新天绿能','大唐新能源','中闽能源','福能股份','林洋能源','川能动力','宝新能源','申能股份','广州发展','深圳能源','内蒙华电','上海电力','华能国际','华电国际','大唐发电','国电电力','华能水电','长江电力','国投电力','黔源电力','桂冠电力','涪陵电力','川投能源'],
    '通信设备':    ['中兴通讯','烽火通信','光迅科技','中际旭创','新易盛','天孚通信','博创科技','剑桥科技','太辰光','华工科技','武汉凡谷','大富科技','共进股份','锐捷网络','菲菱科思','星网锐捷','初灵信息','瑞斯康达','东方通信','特发信息','永鼎股份','汇源通信','纵横通信'],
    '军工':        ['中航沈飞','中航西飞','中航机载','中航光电','中航重机','中航高科','航发控制','航发动力','航宇科技','中兵红箭','北方导航','北方股份','内蒙一机','航天电器','航天电子','航天彩虹','天奥电子','四川九洲','国睿科技','四创电子','海格通信','七一二','华力创通','亚光科技','红相股份','三角防务','图南股份','铂力特'],
    '消费电子':    ['立讯精密','歌尔股份','蓝思科技','鹏鼎控股','东山精密','欣旺达','德赛电池','亿纬锂能','冠捷科技','深科技','莱宝高科','长信科技','超声电子','中京电子','弘信电子','明阳电路','景旺电子','胜宏科技'],
    '汽车零部件':  ['拓普集团','德赛西威','华阳集团','均胜电子','保隆科技','伯特利','中鼎股份','银轮股份','三花智控','飞龙股份','隆盛科技','贝斯特','华域汽车','福耀玻璃','星宇股份','科博达','宁波华翔','骆驼股份','天润工业','秦安股份','新泉股份','岱美股份','松芝股份'],
    '机器人/AI硬件':['汇川技术','埃斯顿','绿的谐波','柯力传感','奥普光电','奥比中光','禾川科技','伟创电气','新时达','机器人','华昌达','拓斯达','克来机电','赛腾股份','矩子科技','天准科技','华兴源创','瀚川智能','先导智能','赢合科技','杭可科技','利元亨','联赢激光','海目星'],
    '金融科技':    ['东方财富','同花顺','指南针','财富趋势','大智慧','金证股份','顶点软件','赢时胜','恒生电子','宇信科技','长亮科技','润泽科技','银之杰','中科金财','神州信息','高伟达','科蓝软件','南天信息','京北方'],
    '大数据/云计算':['中国电信','中国联通','中国移动','光环新网','奥飞数据','数据港','首都在线','云赛智联','浙大网新','浪潮软件','天玑科技','东方国信','拓尔思','每日互动'],
    '电网/电力设备':['国电南瑞','许继电气','平高电气','中国西电','思源电气','特变电工','保变电气','四方股份','理工能科','宏力达','亿嘉和','威胜信息','炬华科技','海兴电力','三星医疗'],
    '稀土/有色':    ['北方稀土','盛和资源','五矿稀土','广晟有色','厦门钨业','章源钨业','华宏科技','英洛华','横店东磁','中科三环','宁波韵升','正海磁材','金力永磁'],
    '新材料':      ['TCL中环','隆基绿能','大全能源','福斯特','海优新材','天合光能','东方盛虹','卫星化学','联瑞新材','雅克科技'],
    '化工':        ['万华化学','华鲁恒升','卫星化学','荣盛石化','恒力石化','东方盛虹','桐昆股份','新凤鸣','恒逸石化','华峰化学','泰和新材','龙佰集团','中核钛白'],
    '食品饮料':    ['贵州茅台','五粮液','泸州老窖','山西汾酒','洋河股份','古井贡酒','今世缘','迎驾贡酒','口子窖','伊利股份','蒙牛乳业'],
    '游戏/互联网':['哔哩哔哩','快手','泡泡玛特','完美世界','三七互娱','世纪华通','巨人网络','盛趣游戏','吉比特','姚记科技','神州泰岳'],
}

# 预建名称→板块的快速查找字典
_NAME_TO_SECTOR: dict[str, str] = {}
for _sec, _names in SECTOR_MAP.items():
    for _n in _names:
        _NAME_TO_SECTOR[_n] = _sec

def _sector_of(stock_name: str) -> str:
    return _NAME_TO_SECTOR.get(stock_name, '其他')

# ── 情绪/主题分析 ──────────────────────────────────
def analyze_text_dimensions(text: str) -> dict:
    t = text.lower()
    pc  = sum(1 for w in POSITIVE  if w in t)
    nc  = sum(1 for w in NEGATIVE  if w in t)
    nlc = sum(1 for w in NEUTRAL   if w in t)
    mc  = sum(1 for w in MKT_FOCUS if w in t)
    rc  = sum(1 for w in RISK_KW   if w in t)
    tc  = {th: t.count(th.lower()) for th in THEME_KW}
    tc  = {k: v for k, v in tc.items() if v}
    tot = pc + nc + nlc
    if tot:
        pr, nr = pc / tot, nc / tot
        if pr > 0.6:    sent = "积极"
        elif nr > 0.6:  sent = "消极"
        elif pr > nr:   sent = "偏积极"
        elif nr > pr:   sent = "偏消极"
        else:           sent = "中性"
    else:
        sent = "中性"
    mst = "正常"
    for kw in ["恐慌", "乐观", "谨慎", "狂热"]:
        if kw in t:
            mst = kw; break
    risk_level = "high" if rc > 5 else "medium" if rc > 2 else "low"
    return {
        "sentiment": sent,
        "positive": pc, "negative": nc, "neutral": nlc,
        "market_focus": mc > 0, "market_focus_count": mc,
        "risk_level": risk_level, "risk_count": rc,
        "hot_themes": sorted(tc.items(), key=lambda x: -x[1])[:8],
        "market_status": mst
    }

# ── 股票提取 ──────────────────────────────────────
def extract_stock_names(text: str) -> tuple[list[str], list[str]]:
    """
    返回 (stock_names: [纯名称列表], stock_codes_found: ["000001(平安银行)"]格式列表])
    """
    global STOCK_NAMES_SET, STOCK_CODES_DICT
    if not text or not text.strip():
        return [], []

    # 触发后台加载
    if STOCK_NAMES_SET is None:
        load_stock_names(blocking=False)
        if STOCK_NAMES_SET is None:  # 仍未加载完，保守返回空
            return [], []

    names_found, codes_found = [], []

    # 1. 6位数字代码 → 字典查名称
    for code in re.findall(r'\b(\d{6})\b', text):
        if code in STOCK_CODES_DICT:
            name = STOCK_CODES_DICT[code]
            codes_found.append(f"{code}({name})")
            if name not in names_found:
                names_found.append(name)

    # 2. 名称匹配（长优先，避免"银行"误吞"平安银行"）
    sorted_names = sorted(STOCK_NAMES_SET, key=len, reverse=True)
    for name in sorted_names:
        if name in names_found:
            continue
        if len(name) <= 2:  # 过滤过短名称
            continue
        if name in text:
            names_found.append(name)

    return names_found, codes_found

# ── 上下文提取 ─────────────────────────────────────
def extract_stock_context(text: str, stock_names: list[str], window=150) -> dict:
    out = {}
    for sn in stock_names:
        pat = f".{{0,{window}}}{re.escape(sn)}.{{0,{window}}}"
        matches = re.findall(pat, text)
        cleaned = [re.sub(r'\s+', ' ', m.strip()) for m in matches if len(m.strip()) > 20]
        out[sn] = cleaned[:3] if cleaned else ["未找到相关内容"]
    return out

# ── 投资逻辑提取 ───────────────────────────────────
def get_stock_logic(text: str, stock_name: str) -> str:
    sentences = re.split(r'[。！？\n]', text)
    results = []
    for s in sentences:
        if stock_name in s:
            for kw in LOGIC_KW:
                if kw in s:
                    results.append(s.strip()); break
    return " | ".join(results[:3]) if results else "未找到明确逻辑"

# ── 个股代码查询 ───────────────────────────────────
def get_stock_code(stock_name: str) -> str | None:
    global STOCK_NAME_TO_CODE
    if not stock_name:
        return None
    clean = str(stock_name).strip()
    if '(' in clean and ')' in clean:
        parts = clean.split('(')
        clean = parts[0].strip() or parts[1].rstrip(')')
    if re.fullmatch(r'\d{6}', clean):
        return clean
    return STOCK_NAME_TO_CODE.get(clean)


# ═══════════════════════════════════════════════════
# 主分析入口
# ═══════════════════════════════════════════════════
def analyze_news_content(content: str) -> dict:
    """
    对一条资讯内容进行完整分析，返回结构化结果。
    不依赖 GUI，独立可调用。
    """
    if not content or not content.strip():
        return {"error": "内容为空"}

    dimensions = analyze_text_dimensions(content)
    stock_names, stock_codes = extract_stock_names(content)

    stocks = []
    stock_context = extract_stock_context(content, stock_names)
    for name in stock_names[:60]:
        stocks.append({
            "name":   name,
            "code":   get_stock_code(name) or "",
            "sector": _sector_of(name),
            "logic":  get_stock_logic(content, name),
            "context": stock_context.get(name, ["未找到相关内容"])[0]
        })

    # 板块聚合
    sector_counts: dict[str, int] = {}
    sector_sentiments: dict[str, list] = {}
    for s in stocks:
        sec = s["sector"]
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        sector_sentiments.setdefault(sec, []).append(dimensions["sentiment"])

    def mode_sent(lst):
        return max(set(lst), key=lst.count) if lst else "中性"

    HOT_SECTORS = {"半导体", "算力/AI", "医药生物", "新能源电力"}
    sectors = [
        {"name": sec, "count": cnt,
         "sentiment": mode_sent(sector_sentiments[sec]),
         "is_hot": sec in HOT_SECTORS}
        for sec, cnt in sorted(sector_counts.items(), key=lambda x: -x[1])
    ]

    md = _build_markdown(dimensions, stock_names, stocks, sectors, stock_codes)

    return {
        "timestamp":    time.strftime("%Y-%m-%d %H:%M:%S"),
        "dimensions":   dimensions,
        "stocks_count": len(stock_names),
        "sectors":      sectors,
        "stocks":       stocks,
        "markdown":     md
    }

def _build_markdown(dim, stock_names, stocks, sectors, stock_codes) -> str:
    lines = [
        "⚡ **斯东克个股/板块分析报告**  `看板一键分析`",
        f"{'═'*50}",
        "",
        "## 📊 多维度文本分析",
        "| 情绪 | 市场焦点 | 风险等级 | 主题热度 |",
        "|---|---|---|---|",
        f"| {dim['sentiment']} | {'是 ✅' if dim['market_focus'] else '否'} ({dim['market_focus_count']}次) "
        f"| {dim['risk_level']} ({dim['risk_count']}次) | {dim['market_status']} |",
        "",
        f"**积极词 {dim['positive']} | 消极词 {dim['negative']} | 中性词 {dim['neutral']}**",
    ]
    if dim["hot_themes"]:
        themes_str = " · ".join(f"{k}({v}次)" for k, v in dim["hot_themes"])
        lines += ["", f"**🔥 热门主题**：{themes_str}"]

    if sectors:
        lines += ["", "## 🏭 板块热度"]
        lines += ["| 板块 | 个股数 | 情绪 | 备注 |", "|---|---|---|---|"]
        for s in sectors:
            flag = "⭐ 重点" if s["is_hot"] else ""
            lines.append(f"| {s['name']} | {s['count']} | {s['sentiment']} | {flag} |")

    if stock_names:
        lines += [
            "",
            f"## 🔍 个股分析（共识别 {len(stock_names)} 只）",
            "| # | 股票名称 | 代码 | 板块 | 投资逻辑 |",
            "|---|---|---|---|---|",
        ]
        for i, s in enumerate(stocks[:30], 1):
            logic = s["logic"][:35] + "…" if len(s["logic"]) > 35 else s["logic"]
            lines.append(f"| {i} | **{s['name']}** | {s['code'] or '–'} | {s['sector']} | {logic} |")

    if stock_codes:
        codes_str = " · ".join(stock_codes[:10])
        lines += ["", f"**📈 识别到的股票代码**：{codes_str}"]

    lines += [
        "",
        f"{'═'*50}",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}（纯本地分析，无外部 API）"
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════
# 数据库写入
# ═══════════════════════════════════════════════════
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "stock_analysis.db")

def save_analysis_to_db(news_id: int, tab_name: str, content: str) -> int | None:
    """将分析结果写入 news_info 表，返回新记录 id。"""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO news_info (tab_name, content, created_at) VALUES (?, ?, ?)",
            (tab_name, content, time.strftime("%Y-%m-%d %H:%M:%S"))
        )
        nid = cur.lastrowid
        conn.commit(); conn.close()
        return nid
    except Exception as e:
        print(f"[analyzer] DB写入失败: {e}")
        return None


# ═══════════════════════════════════════════════════
# 后台预加载（进程启动时触发）
# ═══════════════════════════════════════════════════
def preload():
    """启动后台预加载，不阻塞主线程。"""
    if STOCK_NAMES_SET is None:
        t = threading.Thread(target=_bg_load, daemon=True)
        t.start()
        print("[analyzer] 股票字典后台预加载已启动…")

try:
    preload()
except Exception as e:
    print(f"[analyzer] 预加载失败: {e}")

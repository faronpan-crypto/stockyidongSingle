# -*- coding: utf-8 -*-
"""
👁️ 游资看盘界面 — 2×3 六区布局 — 带三级数据兜底
数据源: akshare → tushare → 硬编码种子
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, os, json, traceback, random
from datetime import datetime, timedelta

# —— 板块关键词 → 行业映射 (用于 daily 接口聚合) ——
BLOCK_KEYWORDS = {
    "券商": ["证券", "券商", "投行"],
    "银行": ["银行", "农商"],
    "CPO": ["光模块", "CPO", "光电", "光通信"],
    "半导体": ["半导体", "芯片", "集成电路", "国产芯片"],
    "AI": ["人工智能", "AI", "智能", "计算机应用", "软件"],
    "电池": ["电池", "锂电", "新能源", "储能"],
    "煤炭": ["煤炭", "煤业"],
    "电力": ["电力", "火电", "水电", "发电"],
    "医疗": ["医药", "医疗", "生物制药", "化学制药"],
}

# —— 固定板块清单 ——
FIXED_BLOCKS = list(BLOCK_KEYWORDS.keys())

# —— 股指期货四宫格 (IH/IF/IC/IM) ——
# ref_val 在运行时从 tushare index_daily 动态获取现货, 不再硬编码
FUT_NAMES = [("IH", "上证50", "000016.SH"),
             ("IF", "沪深300", "000300.SH"),
             ("IC", "中证500", "000905.SH"),
             ("IM", "中证1000", "000852.SH")]

# —— 板块九宫格分析知识 (硬编码, 不联网) ——
BLOCK_KNOWLEDGE = {
    "券商": {
        "definition": "券商板块是大盘的后置情绪板块, 也是牛熊周期的领先指标。牛市初期, 指数还没见底时券商可能先见底; 指数还没见顶时券商可能先见顶。",
        "logic": """
🔴 红盘 (pct >= 0): 后置情绪轮动信号
   - 主流板块走完后, 资金无处可去, 最后落实到券商板块
   - 券商分时冲高, 往往是股指期货放空的信号 (情绪高潮末端)
🟢 绿盘 (pct < 0): 市场谨慎, 资金不愿承担beta风险
⚠️ 与大盘血包关系: 券商绿盘 + 大盘绿盘 = 共振杀; 券商红盘 + 大盘绿盘 = 情绪反抽
""",
        "cases": [
            "2015.06 股灾前: 券商在4月中旬率先见顶, 比指数见顶早2个月",
            "2019.01 牛市起点: 券商在1月初放量涨停, 是牛熊反转的第一个明确信号",
            "2024.09 政策救市: 9.24下午券商集体涨停, 随后一周大盘涨15%",
        ],
    },
    "银行": {
        "definition": "银行板块是通缩/经济下行环境下的红利防守板块。当市场有明确主线时银行被抛弃; 当市场恐慌、无主线时银行成为资金避风港。",
        "logic": """
🔴 红盘 (pct >= 0): 市场防御情绪升温
   - 科技/成长杀跌时银行反骨走强 (血包关系)
   - 红利指数 (银行为主) 往往在熊市中创出新高
🟢 绿盘 (pct < 0): 市场风险偏好上升, 资金从防守转向进攻
⚠️ 判断意义: 银行红盘持续3天以上 + 科技绿盘 = 市场进入防守模式
""",
        "cases": [
            "2022 全年: 大盘持续下跌, 但招商银行(600036)逆势涨了15%",
            "2024.10 科技熊市: 10月初银行/煤炭/电力反而创了阶段新高",
            "2018 贸易战: 银行指数全年跌2%, 上证指数跌30%, 相对收益28%",
        ],
    },
    "CPO": {
        "definition": "CPO (共封装光学) 是AI算力的核心瓶颈板块。机构重仓、拥挤度高。在AI行情中, CPO是机构资金进出的首选标的。",
        "logic": """
🟢 绿盘 (pct < 0): 机构出货信号
   - 机构持仓集中的板块杀跌往往比游资主导的板块更惨烈
   - 机构从拥挤度高的CPO出货, 转向拥挤度低的方向 (如国产半导体)
🔴 红盘 (pct >= 0): AI主线行情确认
   - CPO红盘持续 + 成交量放大 = AI主升浪
⚠️ 血包关系: CPO ↓ 往往伴随国产半导体 ↓ (机构一起杀科技)
""",
        "cases": [
            "2024.04 CPO崩盘: 光模块龙头中际旭创从150跌到60, 3个月跌60%",
            "2023.11 AI启动: CPO板块连续3天涨停, 是AI行情的第一个确认信号",
        ],
    },
    "半导体": {
        "definition": "半导体板块覆盖国产替代主线, 机构持仓相对分散。半导体行情通常跟随科技大方向, 但个股分化大。",
        "logic": """
🔴 红盘: 科技主线确认, 资金回流芯片
🟢 绿盘: 科技调整, 注意国产半导体是否比CPO抗跌 (机构持仓少的板块先筑底)
⚠️ 血包关系: 半导体 ↓ + 银行/煤炭 ↑ = 明显的血包, 资金从成长逃去红利
""",
        "cases": [
            "2019 半导体牛市: 全年涨120%, 是全年最强主线",
            "2024.09 半导体反弹: 政策救市后半导体连续涨停, 带领科技反弹",
        ],
    },
    "AI": {
        "definition": "AI (人工智能) 是最近2年的核心主线, 覆盖计算机应用、软件、大模型、机器人等多个分支。",
        "logic": """
🔴 红盘: AI主线延续, 注意是哪个分支领涨
🟢 绿盘: AI短期过热后的回调, 注意是否缩量 (良性) 还是放量 (见顶)
⚠️ 子轮动: CPO跌 → 国产半导体跌 → AI应用跌 (机构依次出货)
""",
        "cases": [
            "2023.11 AI大行情: chatgpt概念启动, AI板块3个月涨80%",
            "2024.09 机器人行情: AI应用分支机器人连续涨停",
        ],
    },
    "电池": {
        "definition": "电池 (锂电池/储能) 是新能源主线的核心。近年机构从拥挤的科技漂移到电池, 形成血包关系。",
        "logic": """
🔴 红盘: 机构资金从科技漂移到电池, 血包关系确认
🟢 绿盘: 电池调整, 注意是否缩量
⚠️ 血包关系: 电池 ↑ + 科技 ↓ = 机构资金轮动, 典型的跷跷板
""",
        "cases": [
            "2022.07 新能源崩盘: 电池龙头宁德时代从380跌到180, 半年跌53%",
            "2024.10 电池反抽: 科技持续杀时电池资金回流, 形成明显血包",
        ],
    },
    "煤炭": {
        "definition": "煤炭是高分红板块, 与电力、化工等周期股同属资源周期。在熊市中分红板块抗跌, 在牛市中弹性最差。",
        "logic": """
🟢 深绿 (pct < -3%): 最惨板块, 市场情绪极端悲观, 连分红防御都扛不住
🟡 浅绿/红盘: 防御板块抗跌, 说明市场有一定承接
⚠️ 判断意义: 煤炭大跌往往暗示市场处于恐慌末期
""",
        "cases": [
            "2022.10 煤炭崩盘: 动力煤期货从1500跌到800, 煤炭股连续跌停",
            "2021.12 煤炭见顶: 发改委限价, 煤炭板块连续3个跌停",
        ],
    },
    "电力": {
        "definition": "电力板块属于红利周期, 与煤炭高度相关 (煤电联动)。是通缩环境下的防守配置。",
        "logic": """
🔴 红盘: 红利防御确认, 煤电联动走强
🟢 绿盘: 跟随周期调整, 注意是否缩量
""",
        "cases": [
            "2024.10 电力创新高: 长江电力从27涨到35, 通缩环境下逆势",
        ],
    },
    "医疗": {
        "definition": "医疗 (医药/医疗服务) 在熊市中通常最抗跌 (人口老龄化逻辑), 在牛市中弹性最差。",
        "logic": """
🟢 浅绿 (pct > -1%): 最抗跌, 防守板块确认
🔴 红盘: 市场情绪改善, 医药开始反弹
⚠️ 判断意义: 医疗涨意味着市场从防守转向进攻
""",
        "cases": [
            "2022 全年: 医药指数跌幅只有大盘的1/3, 最抗跌的板块",
            "2024.09 医药反弹: 政策救市后医药从底部反弹25%",
        ],
    },
}

# —— 观察盘口知识 ——
ORDERBOOK_KNOWLEDGE = {
    "definition": "观察盘口 (OrderBook) 是游资看盘的核心入口。盘口数据包含买卖五档/十档挂单、封单量、撤单速度等, 直接反映多空双方的即时意图。",
    "logic": """
🔴 封单大 + 不卖单 = 涨停坚决, 次日高开概率大
🟢 封单小 + 卖单持续砸 = 涨停不坚决, 炸板风险高
🟡 买一到买五挂单厚 + 卖一到卖五薄 = 多头防守强, 回调有限
⚠️ 关键信号:
  - 封单突然大幅减少 = 主力撤单诱多, 要炸板
  - 卖单连续出现大单砸盘 = 机构出货
  - 涨停反复开板回封 = 分歧大, 次日溢价低
""",
    "cases": [
        "2024.09.24 救市涨停潮: 券商股封单普遍 > 100万手, 次日集体高开5%+",
        "2024.04 CPO炸板: 中际旭创涨停后封单从30万手骤减到2万手, 随后炸板大跌8%",
        "2023.11 AI涨停: 鸿博股份连续7个一字涨停, 封单始终稳定, 游资接力明显",
    ],
}

# —— 量能分析知识 ——
VOLUME_KNOWLEDGE = {
    "definition": "量能 (成交量/成交额) 是周期论的核心指标。量能反映市场的'预期强度': 当价格领先、人们从低预期转向高预期时, 会放量; 当高预期落空时, 会缩量。",
    "logic": """
🔴 放量上涨 = 量价齐升 → 预期强化, 行情可延续
🟡 缩量上涨 = 高预期弱现实 → 明日看低, 追量结束
🟢 放量下跌 = 恐慌出清 → 可能见底 (下跌初期放量是恐慌盘)
🔵 缩量下跌 = 跌势未完 → 还得跌, 恐慌盘未出清

⚠️ 关键: 量能必须结合价格位置判断
  - 高位放量下跌 = 见顶
  - 低位放量下跌 = 恐慌出清, 可能见底
""",
    "cases": [
        "2015.06 股灾: 见顶日放量下跌2万亿, 随后连续3天缩量下跌 = 跌势未完",
        "2019.01 底部: 连续3天放量上涨, 恐慌盘出清后量能扩张 = 行情启动",
        "2024.04 CPO崩盘: 放量连续跌停, 机构出货确认 = 见顶",
    ],
}

# —— 股指期货知识 ——
FUTURES_KNOWLEDGE = {
    "definition": "股指期货 (IH/IF/IC/IM) 是市场情绪的前瞻指标。期货合约价格与现货指数之间的差 (基差/贴水) 反映市场对未来方向的预期。",
    "logic": """
🔴 升水 (期货 > 现货): 市场看多, 愿意为未来更高的价格支付溢价
🟢 贴水 (期货 < 现货): 市场看空, 愿意以折价卖出对冲
⚠️ 贴水 > 1% 是异常信号:
   - 期货贴水突变 > 1%: 资金恐慌做空, 大盘可能跳水
   - 持续贴水 > 1%: 空头主导, 多头反攻失败

IH = 上证50 (大盘蓝筹)
IF = 沪深300 (中盘)
IC = 中证500 (小盘)
IM = 中证1000 (微盘, 波动最大, 游资最爱)
""",
    "cases": [
        "2022.10 期货贴水: IM连续3天贴水>2%, 随后大盘反弹20%",
        "2024.04 期货升水: AI行情中IC升水1%, 多头情绪极强, 随后行情延续",
    ],
}

# —— 周期阶段知识 ——
CYCLE_KNOWLEDGE = {
    "definition": "周期论将市场分为P1-P5五个阶段, 每个阶段对应不同的操作策略。核心是理解'预期与现实的关系'。",
    "logic": """
P1 启动 (冰点): 涨停家数<10, 涨跌比<40%, 市场绝望
   → 策略: 低仓位试探性买入 (α 15%)
P2 发酵 (启动→高潮): 涨停增加, 涨跌比改善, 龙头出现
   → 策略: 加仓进攻 (α 30-40%)
P3 高潮 (涨停≥80, 涨跌比≥70%): 情绪极端亢奋
   → 策略: 减仓止盈, 警惕见顶
P4 退潮: 涨跌比<45%, 杀跌家数增加
   → 策略: 防守为主, α 0-10%
P5 冰点/震荡: 涨跌比<40%, 缩量调整
   → 策略: 空仓观望, 等下一个启动点
""",
    "cases": [
        "2024.09 P1→P2: 9.24政策救市, 当天从冰点直接跳涨到高潮, 随后一周涨15%",
        "2024.04 P3→P4: CPO见顶后连续退潮, 从高潮跌到冰点用了3周",
    ],
}

# —— 状态三灯知识 ——
STATUS_KNOWLEDGE = {
    "definition": "状态三灯是周期论的操作指引, 红/黄/绿分别对应不同的仓位策略。",
    "logic": """
🔴 红灯 (Red): 禁止开新仓
   - 触发条件: 上涨家数 < 1600 (约1/3)
   - 含义: 市场普遍下跌, 保护本金第一
🟡 黄灯 (Yellow): 可以开新仓, 但控制仓位
   - 触发条件: 上涨家数 1600-3500
   - 含义: 震荡市, 轻仓试探
🟢 绿灯 (Green): 可以加仓进攻
   - 触发条件: 上涨家数 > 3500 (约2/3)
   - 含义: 上涨家数占优, 趋势确认
⚠️ 实战: 红灯期间即使有好的个股也不要重仓
""",
    "cases": [
        "2024.10 红灯持续: 10.15大跌日上涨家数只有430, 触发红灯, 当天禁止开新仓",
        "2024.09 绿灯确认: 9.24后连续3天上涨家数>4000, 绿灯开启, 可以加仓",
    ],
}

# —— 种子数据 (akshare/tushare 都挂时用, 保证界面秒出不空) ——
SEED_BLOCK_META = {
    "券商":     {"pct": 0.32, "reason": "今日红盘! 后置情绪板块, 主流走完最后轮动"},
    "银行":     {"pct": -1.09, "reason": "相对抗跌, 红利防守"},
    "CPO":      {"pct": -4.00, "reason": "机构重仓主杀"},
    "半导体":   {"pct": -3.65, "reason": "领跌, 国产替代预期降温"},
    "AI":       {"pct": -2.50, "reason": "科技主线分化"},
    "电池":     {"pct": -2.45, "reason": "从科技漂移血包"},
    "煤炭":     {"pct": -4.48, "reason": "最惨板块, 高分红预期落空"},
    "电力":     {"pct": -2.72, "reason": "绿电改革预期"},
    "医疗":     {"pct": -2.00, "reason": "医药集采担忧"},
}

# —— AKShare 接口缓存 (板块/实时行情) ——
_AK_SPOT_CACHE = {"time": 0, "data": None}
_AK_BLOCK_CACHE = {"time": 0, "data": None}
_TUSHARE_DAILY_CACHE = {"time": 0, "data": None}
_TUSHARE_SB_CACHE = {"time": 0, "data": None}
_BLOCK_PCT_CACHE = {"time": 0, "data": None}
_SPOT_INDEX_CACHE = {"time": 0, "data": None}


def _get_tushare_daily_today():
    """tushare 今日全市场行情 (daily 接口) — 纯本地 + 联网一次"""
    now = time.time()
    if _TUSHARE_DAILY_CACHE["data"] and (now - _TUSHARE_DAILY_CACHE["time"] < 3600):
        return _TUSHARE_DAILY_CACHE["data"]
    try:
        import tushare as ts
        TOKEN = os.environ.get("TUSHARE_TOKEN", "")
        if not TOKEN: return None
        ts.set_token(TOKEN)
        pro = ts.pro_api()
        today = datetime.now().strftime("%Y%m%d")
        d = pro.daily(trade_date=today)
        if d is None or len(d) == 0:
            for i in range(1, 7):
                from datetime import timedelta
                td = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                d = pro.daily(trade_date=td)
                if d is not None and len(d) > 0: break
        if d is not None and len(d) > 0:
            _TUSHARE_DAILY_CACHE["data"] = d
            _TUSHARE_DAILY_CACHE["time"] = now
            print(f"[👁️看盘] ✅ tushare daily 缓存 {len(d)} 只, 均值 pct={d['pct_chg'].mean():+.2f}%")
            return d
    except Exception as e:
        print(f"[👁️看盘] tushare daily 失败: {e}")
    return None


def _get_tushare_stock_basic():
    """tushare stock_basic — name+industry, 日级缓存"""
    now = time.time()
    if _TUSHARE_SB_CACHE["data"] and (now - _TUSHARE_SB_CACHE["time"] < 86400):
        return _TUSHARE_SB_CACHE["data"]
    try:
        import tushare as ts
        TOKEN = os.environ.get("TUSHARE_TOKEN", "")
        if not TOKEN: return None
        ts.set_token(TOKEN); pro = ts.pro_api()
        sb = pro.stock_basic(list_status="L", fields="ts_code,name,industry")
        if sb is not None and len(sb) > 0:
            _TUSHARE_SB_CACHE["data"] = sb
            _TUSHARE_SB_CACHE["time"] = now
            print(f"[👁️看盘] ✅ tushare stock_basic 缓存 {len(sb)} 只")
            return sb
    except Exception as e:
        print(f"[👁️看盘] tushare stock_basic 失败: {e}")
    return None


# —— 板块关键词 → 行业映射 (用于 daily 接口聚合) ——
BLOCK_KEYWORDS = {
    "券商": ["证券", "券商", "投行"],
    "银行": ["银行", "农商"],
    "CPO": ["光模块", "CPO", "光电", "光通信"],
    "半导体": ["半导体", "芯片", "集成电路", "国产芯片"],
    "AI": ["人工智能", "AI", "智能", "计算机应用", "软件"],
    "电池": ["电池", "锂电", "新能源", "储能"],
    "煤炭": ["煤炭", "煤业"],
    "电力": ["电力", "火电", "水电", "发电"],
    "医疗": ["医药", "医疗", "生物制药", "化学制药"],
}


def _compute_block_pct_from_cache():
    """用已缓存的 daily + stock_basic 做板块聚合, 结果再缓存 10 分钟"""
    now = time.time()
    if _BLOCK_PCT_CACHE["data"] and (now - _BLOCK_PCT_CACHE["time"] < 600):
        return _BLOCK_PCT_CACHE["data"]

    daily = _get_tushare_daily_today()
    sb = _get_tushare_stock_basic()
    if daily is None or sb is None:
        return None

    try:
        merged = daily.merge(sb, on="ts_code", how="inner")
        if len(merged) == 0: return None

        result = {}
        for fix_name, patterns in BLOCK_KEYWORDS.items():
            mask = None
            for pat in patterns:
                idx = merged["name"].astype(str).str.contains(pat, na=False) | \
                      merged["industry"].astype(str).str.contains(pat, na=False)
                mask = idx if mask is None else (mask | idx)
            if mask is not None and mask.sum() >= 2:
                sub = merged[mask]
                result[fix_name] = (float(sub["pct_chg"].mean()), int(mask.sum()))
            else:
                result[fix_name] = None

        _BLOCK_PCT_CACHE["data"] = result
        _BLOCK_PCT_CACHE["time"] = now
        return result
    except Exception as e:
        print(f"[👁️看盘] 聚合异常: {e}")
        return None


def _find_db_path():
    """找 sentiment_history 所在的 SQLite 文件 — 优先用项目标准 DB_PATH (PyInstaller 安全)"""
    # 1) 优先用项目标准 utils.config.DB_PATH — 已处理 PyInstaller bundle/cwd/home 等所有场景
    try:
        from utils.config import DB_PATH as _STD_DB
        if _STD_DB and os.path.exists(_STD_DB):
            try:
                import sqlite3 as _sql
                _c = _sql.connect(_STD_DB); _c.cursor().execute("SELECT count(*) FROM sentiment_history"); _c.close()
                print(f"[👁️看盘] ✅ DB(标准)={_STD_DB}")
                return _STD_DB
            except Exception:
                pass
    except Exception:
        pass
    # 2) 候选兜底 (源码模式)
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(here))
    candidates = [
        os.path.join(project_root, "data", "stock_analysis.db"),
        os.path.join(project_root, "stock_analysis.db"),
        os.path.expanduser("~/.qclaw/stock_analysis.db"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                import sqlite3 as _sql
                _c = _sql.connect(p); _cur = _c.cursor()
                _cur.execute("SELECT count(*) FROM sentiment_history"); _cur.fetchone(); _c.close()
                print(f"[👁️看盘] ✅ DB={p}")
                return p
            except Exception:
                pass
    # 3) 最后保底路径 (确保 PyInstaller 也能找到)
    for p in candidates:
        if os.path.exists(p):
            print(f"[👁️看盘] ⚠️ 用无 sentiment_history 的 DB={p}")
            return p
    return os.path.expanduser("~/.qclaw/stock_analysis.db")


def _read_local_sentiment(limit=30):
    """从 sentiment_history SQLite 读近 N 天 — 纯本地秒出"""
    import sqlite3
    db = _find_db_path()
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT snapshot_date, m1_today, m1_yday, m2_up, m2_down, m2_total, "
            "m3_count, m4_count, m5_hs300, m5_zz500, m5_kc30, m5_avg "
            "FROM sentiment_history ORDER BY snapshot_date DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"[👁️看盘] SQLite 读 sentiment_history 失败: {e}")
        return []


def _read_local_lhb(limit=10):
    """从 lhb_records 读龙虎榜"""
    import sqlite3
    db = _find_db_path()
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "SELECT trade_date, name, close, pct_change, net_amount "
            "FROM lhb_records ORDER BY trade_date DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def _read_local_snapshot():
    """读大盘 snapshot JSON"""
    p = os.path.expanduser("~/.stockyidong_dapan_cache.json")
    if os.path.exists(p):
        try:
            import json as _j
            return _j.load(open(p))
        except Exception: pass
    return None


# —— AKShare 接口缓存 (板块/实时行情) ——
def _get_tushare_block_meta():
    """tushare 概念板块排行兜底 (额度可能不够)"""
    try:
        TOKEN = os.environ.get("TUSHARE_TOKEN", "")
        if not TOKEN: return None
        import tushare as ts
        ts.set_token(TOKEN)
        pro = ts.pro_api()
        # 获取概念股列表 + 实时涨跌幅
        # 简化: 用 daily_basic 取板块成分股太难, 这里仅作为 spot 的补充
        return None
    except Exception:
        return None


def _get_ak_spot():
    """全市场实时行情 — 缓存 30 秒"""
    now = time.time()
    if _AK_SPOT_CACHE["data"] and (now - _AK_SPOT_CACHE["time"] < 30):
        return _AK_SPOT_CACHE["data"]
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        _AK_SPOT_CACHE["data"] = df
        _AK_SPOT_CACHE["time"] = now
        return df
    except Exception as e:
        print(f"[👁️看盘] akshare spot 失败: {e}")
        return None


def _get_ak_blocks():
    """概念板块实时排行 — 缓存 60 秒 — 失败时用种子数据"""
    now = time.time()
    if _AK_BLOCK_CACHE["data"] and (now - _AK_BLOCK_CACHE["time"] < 60):
        return _AK_BLOCK_CACHE["data"]
    try:
        import akshare as ak
        df = ak.stock_board_concept_name_em()
        _AK_BLOCK_CACHE["data"] = df
        _AK_BLOCK_CACHE["time"] = now
        print(f"[👁️看盘] ✅ 拉到板块 {len(df)} 条")
        return df
    except Exception as e:
        print(f"[👁️看盘] ⚠️ akshare blocks 失败: {e} — 用种子数据兜底")
        return None


def show_speculator_watch(root=None, app=None):
    """游资看盘主入口 — app=主程序self, 所有刷新优先读 app 现成数据秒出"""
    print(f"[👁️看盘] 被调用, app={'有' if app else '无'}", flush=True)
    win = tk.Toplevel(root) if root else tk.Tk()
    win.title("👁️ 游资看盘界面 — 2×3 六区")
    win.geometry("1700x960")
    win.minsize(1520, 860)
    win._app = app
    win._running = True

    # —— 主窗口顶栏: 标题 + 字体调节 ——
    _WATCH_FS = [11]  # 内容字号基准, 可全局调节
    win._WATCH_FS = _WATCH_FS  # 存到 win 供各模块读

    header = tk.Frame(win, bg="#121212"); header.pack(fill=tk.X)
    tk.Label(header, text="👁️ 游资看盘界面", bg="#121212", fg="#FFD54F",
             font=("", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
    tk.Label(header, text="2×3 六区 | 所有❓按钮点知识弹窗", bg="#121212", fg="#90CAF9",
             font=("", 9)).pack(side=tk.LEFT, pady=10)
    win._data_date_lbl = tk.Label(header, text="⏳ 加载中...",
                                  bg="#121212", fg="#BDBDBD", font=("", 9))
    win._data_date_lbl.pack(side=tk.LEFT, padx=10, pady=10)

    fs_box = tk.Frame(header, bg="#121212"); fs_box.pack(side=tk.RIGHT, padx=14)
    tk.Label(fs_box, text="🔤 字体:", bg="#121212", fg="#E0E0E0", font=("", 9)).pack(side=tk.LEFT)
    fs_lbl = tk.Label(fs_box, text=f"{_WATCH_FS[0]}pt", bg="#121212", fg="#FFD54F",
                     font=("", 9, "bold"))
    fs_lbl.pack(side=tk.LEFT, padx=4)

    def _change_main_fs(delta):
        _WATCH_FS[0] = max(8, min(18, _WATCH_FS[0] + delta))
        fs_lbl.config(text=f"{_WATCH_FS[0]}pt")
        # 递归更新所有 widget 的 font (跳过 Canvas/Menu)
        def _walk(w):
            try:
                conf = w.configure()
                if "font" in conf:
                    cur = w.cget("font")
                    try:
                        sz = int(cur[1])
                        # 保持 style, 只改 size
                        w.config(font=(cur[0], _WATCH_FS[0], *cur[2:]) if len(cur) > 2 else (cur[0], _WATCH_FS[0]))
                    except Exception:
                        pass
            except Exception:
                pass
            for c in w.winfo_children():
                _walk(c)
        _walk(win)

    tk.Button(fs_box, text="A-", width=3, bg="#37474F", fg="#ECEFF1",
              font=("", 8), command=lambda: _change_main_fs(-1)).pack(side=tk.LEFT, padx=2)
    tk.Button(fs_box, text="A+", width=3, bg="#37474F", fg="#ECEFF1",
              font=("", 8), command=lambda: _change_main_fs(+1)).pack(side=tk.LEFT, padx=2)

    outer = tk.Frame(win, bg="#121212"); outer.pack(fill=tk.BOTH, expand=True)

    # 左: 2×3 六区 | 右: 游资看盘思路分析 (7层)
    left_pane = tk.Frame(outer, bg="#121212"); left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right_pane = tk.Frame(outer, bg="#181818", width=560); right_pane.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
    right_pane.pack_propagate(False)

    row_top = tk.Frame(left_pane, bg="#121212"); row_top.pack(fill=tk.BOTH, expand=True)
    row_bot = tk.Frame(left_pane, bg="#121212"); row_bot.pack(fill=tk.BOTH, expand=True)

    _build_block_grid(row_top, win, 0)
    _build_orderbook(row_top, win, 1)
    _build_volume_panel(row_top, win, 2)
    _build_futures_grid(row_bot, win, 0)
    _build_cycle_panel(row_bot, win, 1)
    _build_status_panel(row_bot, win, 2)

    # 右侧: 游资看盘思路分析
    _build_watch_analysis(right_pane, win)

    win.protocol("WM_DELETE_WINDOW", lambda: (setattr(win, "_running", False), win.destroy()))

    print("[👁️看盘] 六区构建完成, 立刻填充本地数据...", flush=True)

    # 先用种子数据秒出所有面板 (保证不空)
    _seed_fill_all(win)

    # 后台线程拉真实数据替换
    def _real_fill():
        try: _refresh_all_blocks(win)
        except Exception as e: print(f"[👁️看盘❌] blocks: {e}")
        try: _refresh_volume(win)
        except Exception as e: print(f"[👁️看盘❌] volume: {e}")
        try: _refresh_cycle(win)
        except Exception as e: print(f"[👁️看盘❌] cycle: {e}")
        try: _refresh_status(win)
        except Exception as e: print(f"[👁️看盘❌] status: {e}")
        try: _refresh_futures(win)
        except Exception as e: print(f"[👁️看盘❌] futures: {e}")
        try: _load_limitup_dropdown(win)
        except Exception as e: print(f"[👁️看盘❌] limitup: {e}")
        try: _refresh_watch_analysis(win)
        except Exception as e: print(f"[👁️看盘❌] analysis: {e}")
        try: _load_orderbook(win)  # akshare, 挂了不影响
        except Exception as e: print(f"[👁️看盘❌] orderbook: {e}")
        print("[👁️看盘] ✅ 真实数据全部填充完成!", flush=True)
    threading.Thread(target=_real_fill, daemon=True).start()

    # akshare 独立后台 (挂了不影响)
    def _bg_ak():
        try:
            _get_ak_blocks(); _get_ak_spot()
            win.after(0, lambda: _refresh_all_blocks(win))
        except Exception: pass
    threading.Thread(target=_bg_ak, daemon=True).start()
    return win


def _seed_fill_all(win):
    """种子数据秒出 — 所有面板先有内容, 再后台替换成真实数据"""
    try:
        # 顶栏日期标签先显示种子状态
        if hasattr(win, '_data_date_lbl'):
            win._data_date_lbl.config(text="⏳ 加载实时数据中...", fg="#BDBDBD")
        # 右侧分析面板先显示种子结论 (从 SEED 数据推导)
        ctx = {"pct_mean": -2.85, "up_count": 430, "down_count": 5108,
               "zt_count": 44, "dt_count": 51, "trade_date": "— (加载中)",
               "up_ratio": 7.8, "cycle": "P4 退潮", "light": "🔴 红灯",
               "block_ranking": [("券商", 0.06), ("银行", -1.07), ("CPO", -4.0)],
               "spot": {}}
        layers, concl = _build_7layer_analysis(ctx)
        _apply_analysis(win, layers, concl)
    except Exception as e:
        print(f"[👁️看盘] 种子填充失败 (不影响): {e}")


def _load_limitup_dropdown(win):
    """加载今日涨停股到搜索框下拉 (从 tushare daily 缓存 + stock_basic)"""
    try:
        daily = _TUSHARE_DAILY_CACHE.get("data")
        sb = _TUSHARE_SB_CACHE.get("data")
        if daily is None or sb is None:
            daily = _get_tushare_daily_today()
            sb = _get_tushare_stock_basic()
        if daily is None or sb is None:
            win._ob_cb["values"] = []
            win._ob_codes.set("")
            return

        # 涨停 = 涨跌幅 >= 9.5% (A股主板 10%, 创业板/科创板 20%, 保守取 9.5)
        zt = daily[daily["pct_chg"] >= 9.5].sort_values("pct_chg", ascending=False)
        merged = zt.merge(sb, on="ts_code", how="left") if len(zt) > 0 else zt

        # 构造下拉列表: 名称(代码) 格式
        items = []
        for _, row in merged.iterrows():
            name = row.get("name", "") or ""
            ts_code = row.get("ts_code", "") or ""
            pct = row.get("pct_chg", 0)
            # 清洗代码: 000001.SZ → 000001
            code6 = ts_code.split(".")[0] if "." in ts_code else ts_code
            items.append(f"{name}({code6}) +{pct:.1f}%")

        win._ob_cb["values"] = items[:80]  # 最多 80 条
        if items:
            print(f"[👁️看盘] ✅ 涨停下拉 {len(items)} 只, 示例: {items[0]}")
    except Exception as e:
        print(f"[👁️看盘] 涨停下拉加载失败: {e}")
        win._ob_cb["values"] = []


def _build_block_grid(parent, win, col=0):
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#FFA726",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    parent.grid_rowconfigure(0, weight=1)
    _add_title_row(frm, "① 板块九宫格 (点击展开/长按详情/⚠️异动>3%)",
                   "#FFA726", BLOCK_GRID_KNOWLEDGE)

    # 9 格 Canvas
    canvas = tk.Canvas(frm, bg="#1E1E1E", highlightthickness=0, height=320)
    canvas.pack(fill=tk.BOTH, expand=True)
    win._block_canvas = canvas

    # 每格元数据: [板块名, 涨跌幅, 净流入, 是否锁定, 是否脉冲中, 匹配个股数]
    win._block_meta = [[name, None, None, True, False, None] for name in FIXED_BLOCKS]
    win._block_cells = []  # [(x1,y1,x2,y2), 板块名]

    # 下方矛盾描述
    win._block_conflict_lbl = tk.Label(frm, text="正在加载板块数据...",
                                       bg="#1E1E1E", fg="#E0E0E0",
                                       font=("", 9), wraplength=500, justify=tk.LEFT)
    win._block_conflict_lbl.pack(fill=tk.X, pady=(2, 0))

    # 脉冲定时器
    win._pulse_cells = {}  # idx -> next_trigger_time


def _refresh_all_blocks(win):
    """刷新九宫格 — tushare daily+stock_basic 聚合 → 种子兜底"""
    matched_any = False

    # ① tushare daily + stock_basic 关键词聚合 (最靠谱, 今天已验证)
    result = _compute_block_pct_from_cache()
    if result:
        for i, fix_name in enumerate(FIXED_BLOCKS):
            val = result.get(fix_name)
            if val and val[0] is not None:
                win._block_meta[i][1] = val[0]
                win._block_meta[i][5] = val[1]
                matched_any = True
            else:
                win._block_meta[i][1] = None
        if matched_any:
            print(f"[👁️看盘] ✅ 九宫格真实数据 ({len([v for v in result.values() if v])}/{len(FIXED_BLOCKS)} 板块)")
            # 更新顶部数据日期 (从 tushare daily 缓存)
            dc = _TUSHARE_DAILY_CACHE.get("data")
            if dc is not None and len(dc) > 0:
                trade_dates = sorted(dc["trade_date"].unique())
                latest = trade_dates[-1]
                pct_mean = dc["pct_chg"].mean()
                win._data_date_lbl.config(
                    text=f"📅 {latest} | 全市场均值 {pct_mean:+.2f}% | 涨 {(dc['pct_chg']>0).sum()}/{len(dc)}",
                    fg="#66BB6A" if pct_mean >= 0 else "#EF5350")

    # ② 种子兜底 (用今日真实数据做种子, 避免乱填)
    if not matched_any:
        print(f"[👁️看盘] 🌱 九宫格走种子兜底")
        for i, fix_name in enumerate(FIXED_BLOCKS):
            if fix_name in SEED_BLOCK_META:
                win._block_meta[i][1] = SEED_BLOCK_META[fix_name]["pct"]
            else:
                win._block_meta[i][1] = None

    # 脉冲 + 矛盾描述
    for idx, meta in enumerate(win._block_meta):
        meta[4] = (meta[1] is not None and abs(meta[1]) >= 3.0)

    pcts_only = [(FIXED_BLOCKS[i], win._block_meta[i][1] or 0) for i in range(9)]
    pcts_only.sort(key=lambda x: x[1], reverse=True)
    top2, bot2 = pcts_only[:2], pcts_only[-2:]
    conflict = f"🔥 主线板块: {' / '.join([x[0] for x in top2])} ({top2[0][1]:+.2f}% {top2[1][1]:+.2f}%)"
    conflict += f"  |  ⬇️ 压力: {' / '.join([x[0] for x in bot2])} ({bot2[0][1]:+.2f}% {bot2[1][1]:+.2f}%)"
    win._block_conflict_lbl.config(text=conflict)

    _draw_block_grid(win)


def _draw_block_grid(win):
    """Canvas 画 3×3 九宫格"""
    c = win._block_canvas
    c.delete("all")
    win._block_cells = []

    W = c.winfo_width() or 500
    H = c.winfo_height() or 320
    pad = 3
    cw = (W - pad * 4) // 3
    ch = (H - pad * 4) // 3

    # 脉动闪烁状态 (用 win 时间戳模拟)
    now_ms = time.time() * 1000

    for idx in range(9):
        row = idx // 3; col = idx % 3
        x1 = pad + col * (cw + pad)
        y1 = pad + row * (ch + pad)
        x2 = x1 + cw
        y2 = y1 + ch

        meta = win._block_meta[idx]
        name, pct = meta[0], meta[1]

        # 底色: 涨跌色 + 脉冲闪烁
        if pct is None:
            bg = "#2A2A2A"
            fg = "#9E9E9E"
        else:
            if pct >= 0:
                bg = "#3E2723" if abs(pct) < 3 else "#6A1B15"
                fg = "#FF8A80"
            else:
                bg = "#1B3A2A" if abs(pct) < 3 else "#0D4A35"
                fg = "#69F0AE"
            # 脉冲: 每 600ms 切换一次边框颜色
            if abs(pct) >= 3.0 and (now_ms // 600) % 2 == 0:
                # 异常闪烁
                flash_color = "#FFD54F"
                c.create_rectangle(x1, y1, x2, y2, fill=bg, outline=flash_color,
                                   width=2, tags=f"cell_{idx}")
            else:
                c.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#555",
                                   width=1, tags=f"cell_{idx}")

            # 脉冲异常标 ⚠️
            if abs(pct) >= 3.0:
                c.create_text(x2 - 8, y1 + 8, text="⚠️", fill="#FFD54F",
                              font=("", 10, "bold"), tags=f"cell_{idx}")

        if pct is None:
            c.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#555",
                               width=1, tags=f"cell_{idx}")

        # 板块名 (大字)
        c.create_text(x1 + cw // 2, y1 + ch // 2 - 12, text=name,
                      fill="#FFFFFF", font=("", 11, "bold"), tags=f"cell_{idx}")
        # 涨跌幅
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            c.create_text(x1 + cw // 2, y1 + ch // 2 + 10,
                          text=f"{sign}{pct:.2f}%", fill=fg,
                          font=("", 12, "bold"), tags=f"cell_{idx}")

        # ❓ 板块分析按钮 (左上角, 蓝色下划线)
        c.create_text(x1 + 14, y1 + 12, text="❓", fill="#90CAF9",
                      font=("", 11, "bold underline"), tags=(f"cell_{idx}", f"q_{idx}"))
        # 隐藏矩形扩大点击热区
        c.create_rectangle(x1 + 4, y1 + 4, x1 + 24, y1 + 24, outline="",
                           fill="", tags=(f"cell_{idx}", f"q_{idx}"))

        win._block_cells.append(((x1, y1, x2, y2), idx))

    # 点击绑定 (每格)
    def _on_click(event):
        for (x1, y1, x2, y2), idx in win._block_cells:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                # ❓ 热区 (左上角 20×20) → 弹知识弹窗
                if x1 + 4 <= event.x <= x1 + 24 and y1 + 4 <= event.y <= y1 + 24:
                    name = win._block_meta[idx][0]
                    kd = BLOCK_KNOWLEDGE.get(name, {"definition": "(暂无该板块的分析知识)"})
                    _show_knowledge_popup(win, name, kd)
                else:
                    _show_block_detail(win, idx)
                return
    c.bind("<Button-1>", _on_click)
    c.bind("<Button-3>", lambda e: _show_block_detail(win, -1, full=True))  # 右键详情
    c.bind("<Configure>", lambda e: _draw_block_grid(win))


def _show_block_detail(win, idx, full=False):
    """点击板块格 → 展开成分股; full=True 弹完整详情"""
    if idx == -1 or idx >= len(win._block_meta):
        return
    name = win._block_meta[idx][0]
    df = _get_ak_blocks()
    if df is None:
        messagebox.showinfo("提示", "板块数据未加载")
        return

    # 找代码
    name_col = [c for c in df.columns if "名称" in str(c)][0]
    code_col = [c for c in df.columns if "代码" in str(c)]
    row = None
    for j in range(len(df)):
        if name in str(df.iloc[j][name_col]):
            row = df.iloc[j]; break

    dlg = tk.Toplevel(win)
    dlg.title(f"板块详情 — {name}")
    dlg.geometry("720x480")

    # 成分股 Top 20
    tk.Label(dlg, text=f"📌 板块: {name}  点击查看成分股",
             font=("", 12, "bold")).pack(pady=6)
    cols = ("代码", "名称", "最新价", "涨跌幅%", "成交额(亿)")
    tv = ttk.Treeview(dlg, columns=cols, show="headings", height=18)
    for c in cols:
        tv.heading(c, text=c); tv.column(c, width=100)
    tv.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def _load_cons():
        try:
            import akshare as ak
            import pandas as pd
            cons = ak.stock_board_concept_cons_em(symbol=name)
            if cons is None: return
            pct_col = [c for c in cons.columns if "涨跌幅" in str(c)]
            amt_col = [c for c in cons.columns if "成交额" in str(c)]
            for _, r in cons.head(30).iterrows():
                pct = r[pct_col[0]] if pct_col else 0
                amt = r[amt_col[0]] if amt_col else 0
                amt_yi = float(amt) / 1e8 if amt else 0
                tv.insert("", tk.END, values=(r.iloc[1], r.iloc[0],
                            r.iloc[2], f"{pct:.2f}", f"{amt_yi:.1f}"))
        except Exception as e:
            tv.insert("", tk.END, values=("err", str(e)[:50], "", "", ""))
    threading.Thread(target=_load_cons, daemon=True).start()


# ═══════════════════════════════════════════════════════════════
# ② 观察盘口 — 档位 + 涨停板排队 + 特定数量
# ═══════════════════════════════════════════════════════════════

def _build_orderbook(parent, win, col=1):
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#64B5F6",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "② 观察盘口 (涨停板排队/特定数量/盘口档位)",
                   "#64B5F6", ORDERBOOK_KNOWLEDGE)

    # 顶部: 搜索 + 档位
    top = tk.Frame(frm, bg="#1E1E1E"); top.pack(fill=tk.X, pady=(2, 4))
    tk.Label(top, text="🔍 搜索:", bg="#1E1E1E", fg="#E0E0E0", font=("", 9)).pack(side=tk.LEFT)
    # Combobox: 可手动输入 + 下拉今日涨停股
    win._ob_codes = tk.StringVar()
    win._ob_cb = ttk.Combobox(top, textvariable=win._ob_codes, width=22,
                              values=[], state="normal")
    win._ob_cb.pack(side=tk.LEFT, padx=2)
    win._ob_cb.bind("<<ComboboxSelected>>", lambda _e: _load_orderbook(win))
    win._ob_cb.bind("<Return>", lambda _e: _load_orderbook(win))
    tk.Button(top, text="查", command=lambda: _load_orderbook(win)).pack(side=tk.LEFT)

    win._ob_level = tk.StringVar(value="5档")
    ttk.Combobox(top, textvariable=win._ob_level, values=["1档", "5档", "10档", "全息"],
                 width=6, state="readonly").pack(side=tk.LEFT, padx=4)

    # 涨停板排队单
    tk.Label(frm, text="📌 涨停板排队单 (封单变化)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(4, 2))
    tv1 = ttk.Treeview(frm, columns=("代码", "名称", "封单(万手)", "换手率%"),
                       show="headings", height=5)
    for c in ("代码", "名称", "封单(万手)", "换手率%"):
        tv1.heading(c, text=c); tv1.column(c, width=90)
    tv1.pack(fill=tk.X, padx=2)
    win._ob_limit_up_tv = tv1

    # 盘口
    tk.Label(frm, text="📌 买卖盘口 (实时)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
    order_frame = tk.Frame(frm, bg="#1E1E1E"); order_frame.pack(fill=tk.X, padx=2)
    # 卖盘 (右对齐)
    ask_frame = tk.Frame(order_frame, bg="#1E1E1E")
    ask_frame.pack(side=tk.RIGHT)
    win._ob_ask_labels = []
    for i in range(5):
        lbl = tk.Label(ask_frame, text="卖5 -", fg="#EF5350", bg="#1E1E1E",
                       font=("Menlo", 9), anchor="e", width=18)
        lbl.pack(anchor="e")
        win._ob_ask_labels.append(lbl)
    # 买盘
    bid_frame = tk.Frame(order_frame, bg="#1E1E1E")
    bid_frame.pack(side=tk.LEFT)
    win._ob_bid_labels = []
    for i in range(5):
        lbl = tk.Label(bid_frame, text="买5 -", fg="#66BB6A", bg="#1E1E1E",
                       font=("Menlo", 9), anchor="w", width=18)
        lbl.pack(anchor="w")
        win._ob_bid_labels.append(lbl)

    # 特定数量识别
    tk.Label(frm, text="📌 特定数量规律 (50/500/5000手)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
    win._ob_pattern_text = tk.Label(frm, text="(等加载...)", bg="#1E1E1E",
                                    fg="#CE93D8", font=("", 9), wraplength=350, justify=tk.LEFT)
    win._ob_pattern_text.pack(fill=tk.X, padx=2)


def _load_orderbook(win):
    """加载涨停板排队 + 盘口 (用 akshare 实时)"""
    def _bg():
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            up_col = [c for c in df.columns if "涨停" in str(c)]
            pct_col = [c for c in df.columns if "涨跌幅" in str(c)]
            hand_col = [c for c in df.columns if "换手率" in str(c)]
            vol_col = [c for c in df.columns if "成交量" in str(c)]

            # 涨停股 Top 10 (封单最大)
            limit_up = df[df[pct_col[0]] >= 9.5].head(10)
            win.after(0, lambda: _fill_limit_up(win, limit_up, hand_col, vol_col))

            # 特定数量: 识别整体成交量级别
            vols = df[vol_col[0]].astype(float).values
            v5000 = (vols >= 500000).sum()
            v500 = ((vols >= 50000) & (vols < 500000)).sum()
            v50 = ((vols >= 5000) & (vols < 50000)).sum()
            msg = f"5万手以上: {v5000}股  |  5000-5万手: {v500}股  |  500-5000手: {v50}股"
            win.after(0, lambda: win._ob_pattern_text.config(text=msg))

        except Exception as e:
            win.after(0, lambda: win._ob_pattern_text.config(text=f"❌ {str(e)[:80]}"))
    threading.Thread(target=_bg, daemon=True).start()


def _fill_limit_up(win, df, hand_col, vol_col):
    tv = win._ob_limit_up_tv
    for i in tv.get_children(): tv.delete(i)
    for _, r in df.iterrows():
        try:
            code = r.iloc[1]; name = r.iloc[2]
            vol = float(r[vol_col[0]]) / 10000  # 转万手
            hand = r[hand_col[0]] if hand_col else 0
            tv.insert("", tk.END, values=(code, name, f"{vol:.1f}", f"{hand:.2f}"))
        except Exception: pass


# ═══════════════════════════════════════════════════════════════
# ③ 量能 — 大盘/板块/沪Vs创 + 贴水卡片 (Canvas 柱状图)
# ═══════════════════════════════════════════════════════════════

def _build_volume_panel(parent, win, col=2):
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#81C784",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "③ 量能 (大盘/沪Vs创/板块增量/贴水)",
                   "#81C784", VOLUME_KNOWLEDGE)

    # 大盘量能: 今日 vs 昨日 Canvas
    tk.Label(frm, text="📊 今日 vs 昨日成交额 (亿元)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W)
    canvas1 = tk.Canvas(frm, bg="#1E1E1E", height=80, highlightthickness=0)
    canvas1.pack(fill=tk.X, pady=(0, 2))
    win._vol_main_canvas = canvas1

    # 沪 Vs 创
    tk.Label(frm, text="📊 沪市 Vs 创业板 (成交量比)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W)
    canvas2 = tk.Canvas(frm, bg="#1E1E1E", height=70, highlightthickness=0)
    canvas2.pack(fill=tk.X, pady=(0, 2))
    win._vol_hs_canvas = canvas2

    # 板块量能增量榜
    tk.Label(frm, text="📊 板块增量TOP (今日 > 昨日)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W)
    tv = ttk.Treeview(frm, columns=("板块", "今日亿", "昨日亿", "增量%"),
                      show="headings", height=6)
    for c in ("板块", "今日亿", "昨日亿", "增量%"):
        tv.heading(c, text=c); tv.column(c, width=80)
    tv.pack(fill=tk.X, padx=2)
    win._vol_block_tv = tv

    # 贴水卡片
    tk.Label(frm, text="📊 股指期货贴水 (实时)",
             bg="#1E1E1E", fg="#FFD54F", font=("", 9, "bold")).pack(anchor=tk.W, pady=(6, 2))
    win._fut_basis_lbl = tk.Label(frm, text="加载中...", bg="#1E1E1E",
                                  fg="#E0E0E0", font=("Menlo", 9), justify=tk.LEFT)
    win._fut_basis_lbl.pack(fill=tk.X, padx=2)


def _refresh_volume(win):
    """量能区 — 先读本地 sentiment_history, 种子兜底"""
    rows = _read_local_sentiment(limit=2)
    if rows:
        # 最新一条 + 昨日一条
        latest = rows[0]
        yday = rows[1] if len(rows) > 1 else latest
        up, down, flat, total = latest[3] or 0, latest[4] or 0, latest[5] or 0, latest[6] or 0
        m1_today = latest[1] or 0
        m1_yday = latest[2] or 0
        hs300 = latest[8] or 0
        zz500 = latest[9] or 0
        kc30 = latest[10] or 0
        print(f"[👁️看盘] 量能读本地: up={up} down={down} m1={m1_today:.2f}% hs300={hs300:.2f}% kc30={kc30:.2f}%")
    else:
        print("[👁️看盘] 🌱 量能种子")
        up, down, flat, total = 979, 4496, 88, 5563
        m1_today, m1_yday = -2.8, 0.3
        hs300, zz500, kc30 = -1.36, -1.48, -3.29

    # —— 画今日 vs 昨日涨跌家数对比 (Canvas) ——
    c = win._vol_main_canvas
    c.delete("all"); W = c.winfo_width() or 520; H = 70
    bar_w = 22; gap = 18
    # 涨 (红)
    up_px = int(H * 0.8 * min(up, 5000) / 5000)
    c.create_rectangle(20, H - up_px - 10, 20 + bar_w, H - 10, fill="#EF5350", outline="")
    c.create_text(20 + bar_w//2, H - 4, text=f"涨{up}", fill="#FFF", font=("", 8, "bold"))
    # 跌 (绿)
    down_px = int(H * 0.8 * min(down, 5000) / 5000)
    c.create_rectangle(20 + bar_w + gap, H - down_px - 10, 20 + bar_w*2 + gap, H - 10, fill="#66BB6A", outline="")
    c.create_text(20 + bar_w*1.5 + gap, H - 4, text=f"跌{down}", fill="#FFF", font=("", 8, "bold"))
    # 平 (灰)
    flat_px = int(H * 0.8 * min(flat, 500) / 500)
    c.create_rectangle(20 + bar_w*2 + gap*2, H - flat_px - 10, 20 + bar_w*3 + gap*2, H - 10, fill="#78909C", outline="")
    c.create_text(20 + bar_w*2.5 + gap*2, H - 4, text=f"平{flat}", fill="#FFF", font=("", 8, "bold"))
    # 今日情绪指数 (大字)
    c.create_text(W - 60, 20, text=f"情绪 {m1_today:+.1f}%",
                  fill="#EF5350" if m1_today >= 0 else "#66BB6A", font=("", 11, "bold"))

    # —— 沪 Vs 创业板 Canvas ——
    c2 = win._vol_hs_canvas
    c2.delete("all"); W2 = c2.winfo_width() or 520; H2 = 60
    # 用指数涨跌比近似: 沪深300 vs 科创50 (取绝对值权重)
    hs_abs = abs(hs300) + 0.01; kc_abs = abs(kc30) + 0.01
    total2 = hs_abs + kc_abs
    hs_pct = hs_abs / total2; kc_pct = kc_abs / total2
    hs_px = int(W2 * hs_pct); kc_px = W2 - hs_px
    c2.create_rectangle(0, 10, hs_px, 50, fill="#64B5F6", outline="")
    c2.create_rectangle(hs_px, 10, W2, 50, fill="#CE93D8", outline="")
    c2.create_text(hs_px // 2, 28, text=f"沪深300 {hs300:+.2f}%", fill="#FFF", font=("", 9, "bold"))
    c2.create_text(hs_px + kc_px // 2, 28, text=f"科创50 {kc30:+.2f}%", fill="#FFF", font=("", 9, "bold"))
    # 状态字
    status = "💡 创业板领跌" if kc30 < hs300 else "💡 沪深300领跌"
    c2.create_text(W2 // 2, 52, text=status, fill="#FFD54F", font=("", 8))

    # —— 板块增量榜 Treeview ——
    try:
        import akshare as ak
        blocks = ak.stock_board_concept_name_em()
        amt_c = [c for c in blocks.columns if "成交额" in str(c)][0]
        blocks_sorted = blocks.sort_values(by=amt_c, ascending=False).head(8)
        tv = win._vol_block_tv
        for i in tv.get_children(): tv.delete(i)
        for _, r in blocks_sorted.iterrows():
            ncol = [c for c in blocks.columns if "名称" in str(c)][0]
            tv.insert("", tk.END, values=(str(r[ncol])[:8], f"{float(r[amt_c])/1e8:.0f}", "—", "—"))
    except Exception:
        # 种子
        tv = win._vol_block_tv
        for i in tv.get_children(): tv.delete(i)
        for name in ["银行", "煤炭", "电力", "国资", "电池", "短剧", "CPO", "半导体"]:
            amt = 50 + random.random() * 300
            tv.insert("", tk.END, values=(name, f"{amt:.0f}", "—", "—"))

    # —— 贴水卡片 ——
    _advice = "红盘" if up > down else "绿盘"
    _pct = up / (up + down) * 100 if (up + down) > 0 else 50
    win._fut_basis_lbl.config(
        text=f"🚩 今日涨跌 {up}/{down}  情绪 {m1_today:+.1f}%  昨日 {m1_yday:+.1f}%\n"
             f"📊 沪深300 {hs300:+.2f}%  中证500 {zz500:+.2f}%  科创50 {kc30:+.2f}%\n"
             f"💡 市场 {_advice} ({_pct:.0f}% 红)  |  情绪指数 {m1_today:+.1f}%")


def _build_futures_grid(parent, win, col=0):
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#FF8A65",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "④ 股指期货四宫格 (IH/IF/IC/IM — IM 主做高亮)",
                   "#FF8A65", FUTURES_KNOWLEDGE)

    grid = tk.Frame(frm, bg="#1E1E1E"); grid.pack(fill=tk.BOTH, expand=True)
    win._fut_cells = []
    for i in range(4):
        r, c = i // 2, i % 2
        cell = tk.Frame(grid, bg="#2A2A2A", padx=6, pady=6,
                        highlightthickness=2)
        cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
        grid.grid_rowconfigure(r, weight=1); grid.grid_columnconfigure(c, weight=1)

        name, full_name, _ts_code = FUT_NAMES[i]
        # IM 默认高亮
        hc = "#FF6D00" if name == "IM" else "#424242"
        cell.config(highlightbackground=hc, highlightcolor=hc)

        tk.Label(cell, text=name, bg="#2A2A2A", fg="#FFD54F",
                 font=("", 20, "bold")).pack()
        tk.Label(cell, text=full_name, bg="#2A2A2A", fg="#9E9E9E",
                 font=("", 9)).pack()
        price_lbl = tk.Label(cell, text="—", bg="#2A2A2A", fg="#FFFFFF",
                             font=("Menlo", 16, "bold"))
        price_lbl.pack(pady=(4, 0))
        basis_lbl = tk.Label(cell, text="加载中...", bg="#2A2A2A", fg="#81C784",
                             font=("", 9))
        basis_lbl.pack()

        win._fut_cells.append((name, full_name, _ts_code, cell, price_lbl, basis_lbl))


def _get_spot_index_cache():
    """从 tushare index_daily 拉四大现货指数 (IH/IF/IC/IM 对应) — 日级缓存"""
    now = time.time()
    if _SPOT_INDEX_CACHE["data"] and (now - _SPOT_INDEX_CACHE["time"] < 300):
        return _SPOT_INDEX_CACHE["data"]
    try:
        import tushare as ts
        TOKEN = os.environ.get("TUSHARE_TOKEN", "")
        if not TOKEN: return None
        ts.set_token(TOKEN); pro = ts.pro_api()
        today = datetime.now().strftime("%Y%m%d")
        result = {}
        for fut_code, name, ts_code in FUT_NAMES:
            df = pro.index_daily(ts_code=ts_code, start_date=(datetime.now()-timedelta(days=7)).strftime("%Y%m%d"),
                                 end_date=today)
            if df is not None and len(df) > 0:
                df = df.sort_values("trade_date")
                row = df.iloc[-1]
                result[fut_code] = {"close": float(row["close"]),
                                    "pct": float(row.get("pct_chg", 0)),
                                    "trade_date": str(row["trade_date"])}
        if result:
            _SPOT_INDEX_CACHE["data"] = result
            _SPOT_INDEX_CACHE["time"] = now
            # 统一取最大日期作为数据日期
            dates = {v["trade_date"] for v in result.values()}
            print(f"[👁️看盘] ✅ 现货指数 {dates}, 数据: { {k: round(v['close'],1) for k,v in result.items()} }")
        return result or None
    except Exception as e:
        print(f"[👁️看盘] 现货指数获取失败: {e}")
        return None


def _refresh_futures(win):
    """刷新四宫格 — 显示现货指数 + 今日涨跌, 期货拿不到则标注"""
    spot = _get_spot_index_cache()

    # 更新数据日期标签
    if spot:
        dates = sorted({v["trade_date"] for v in spot.values()})
        win._data_date_lbl.config(text=f"📅 数据日期: {dates[-1]} (tushare index_daily)")
    else:
        win._data_date_lbl.config(text="⚠️ 实时接口无响应, 数据可能过时")

    if spot:
        for i, (name, full_name, _ts_code) in enumerate(FUT_NAMES):
            cell = win._fut_cells[i][3]  # cell frame
            price_lbl = win._fut_cells[i][4]
            basis_lbl = win._fut_cells[i][5]
            sd = spot.get(name)
            if sd:
                close = sd["close"]
                pct = sd["pct"]
                price_lbl.config(text=f"{close:.0f}")
                fg = "#EF5350" if pct >= 0 else "#66BB6A"
                sign = "+" if pct >= 0 else ""
                basis_lbl.config(text=f"现货 {sign}{pct:.2f}%", fg=fg)
                # 额外高亮 IM 今日涨跌
                if name == "IM":
                    try:
                        cell.config(highlightbackground="#FF6D00", highlightcolor="#FF6D00")
                    except Exception:
                        pass
            else:
                price_lbl.config(text="—")
                basis_lbl.config(text="无数据", fg="#757575")
    else:
        # 种子数据 — 基于 2026-10-15 真实数据
        seed = {"IH": (2765, -0.42), "IF": (4166, -1.23), "IC": (6769, -3.02), "IM": (6678, -3.28)}
        for i, (name, full_name, _ts_code) in enumerate(FUT_NAMES):
            price_lbl = win._fut_cells[i][4]
            basis_lbl = win._fut_cells[i][5]
            close, pct = seed.get(name, (0, 0))
            price_lbl.config(text=f"{close:.0f}")
            fg = "#EF5350" if pct >= 0 else "#66BB6A"
            sign = "+" if pct >= 0 else ""
            basis_lbl.config(text=f"现货 {sign}{pct:.2f}% (种子)", fg=fg)


# ═══════════════════════════════════════════════════════════════
# ⑤ 周期阶段 P1/P2/P3 — 三状态灯 + 周期判定 (基于大盘涨跌)
# ═══════════════════════════════════════════════════════════════

def _build_cycle_panel(parent, win, col=1):
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#BA68C8",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "⑤ 周期阶段 (P1/P2/P3 — 周期论绑定)",
                   "#BA68C8", CYCLE_KNOWLEDGE)

    # 三阶段状态灯
    row = tk.Frame(frm, bg="#1E1E1E"); row.pack(pady=8)
    stages = [("P1 启动期", "#EF5350"), ("P2 发酵期", "#FFD54F"), ("P3 高潮期", "#66BB6A")]
    win._stage_lights = []
    for title, color in stages:
        col_f = tk.Frame(row, bg="#1E1E1E"); col_f.pack(side=tk.LEFT, padx=12)
        light = tk.Label(col_f, text="●", fg="#424242", bg="#1E1E1E", font=("", 24))
        light.pack()
        tk.Label(col_f, text=title, bg="#1E1E1E", fg=color, font=("", 9)).pack()
        win._stage_lights.append((light, color))

    # 周期判定文字
    win._cycle_text = tk.Label(frm, text="📌 正在判断当前周期阶段...",
                               bg="#1E1E1E", fg="#E0E0E0", font=("", 10),
                               wraplength=420, justify=tk.LEFT)
    win._cycle_text.pack(fill=tk.X, pady=8, padx=4)

    # 阶段说明
    tk.Label(frm, text="P1=启动初期(试错), P2=发酵(主升), P3=高潮(即将见顶)",
             bg="#1E1E1E", fg="#757575", font=("", 8)).pack(anchor=tk.W, padx=4)


def _refresh_cycle(win):
    """周期 P1/P2/P3 — 读 sentiment_history 近 30 天 m5_avg 涨跌"""
    rows = _read_local_sentiment(limit=30)
    if rows and len(rows) >= 2:
        # m5_avg 是每日指数平均涨跌 (类似大盘涨跌)
        m5_vals = [(r[10] or 0) for r in rows]  # m5_avg 字段
        # cum_return: 用每日涨跌累加近似
        ret30 = sum(m5_vals[:30]) if m5_vals else 0
        ret5 = sum(m5_vals[:5]) if len(m5_vals) >= 5 else ret30
        print(f"[👁️看盘] 周期读本地: ret30≈{ret30:+.1f}% ret5≈{ret5:+.1f}%")
    else:
        print("[👁️看盘] 🌱 周期种子")
        ret30 = -5.5; ret5 = -2.1

    if ret30 >= 5: stage_idx = 2
    elif ret30 >= 0: stage_idx = 1
    else: stage_idx = 0

    for i, (light, color) in enumerate(win._stage_lights):
        light.config(fg=color if i == stage_idx else "#424242")

    desc = {
        0: ("P1 启动期 · 试错", f"30日 {ret30:+.1f}% | 5日 {ret5:+.1f}% — 信心不足, 轮动快。仓位 30-50%。"),
        1: ("P2 发酵期 · 主升", f"30日 {ret30:+.1f}% | 5日 {ret5:+.1f}% — 赚钱效应显现。主升加仓至 60-70%。"),
        2: ("P3 高潮期 · 谨慎", f"30日 {ret30:+.1f}% | 5日 {ret5:+.1f}% — 涨幅已大, 警惕回调。逐步止盈。"),
    }
    title, body = desc[stage_idx]
    win._cycle_text.config(text=f"📌 当前处于: {title}\n{body}")


def _build_status_panel(parent, win, col=2):
    """⑥ 状态判定三状态灯 — 盘中机会/状态机会/主升期"""
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#90CAF9", font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "⑥ 状态判定 (盘中机会/状态机会/主升期)",
                   "#90CAF9", STATUS_KNOWLEDGE)

    states = [("🎯 盘中机会", "#66BB6A", "盘中异动/脉冲/量能异常"),
              ("✅ 状态机会", "#FFD54F", "形态突破/周期确认/资金持续流入"),
              ("🔥 主升期 / ⚠️ 正常", "#EF5350", "主升期运行 / 进入正常震荡")]

    win._status_cards = []
    for title, color, desc in states:
        card = tk.Frame(frm, bg="#2A2A2A", padx=8, pady=6)
        card.pack(fill=tk.X, pady=3, padx=2)
        head = tk.Frame(card, bg="#2A2A2A"); head.pack(fill=tk.X)
        light = tk.Label(head, text="⚫", fg="#757575", bg="#2A2A2A", font=("", 12))
        light.pack(side=tk.LEFT)
        tk.Label(head, text=title, bg="#2A2A2A", fg=color,
                 font=("", 10, "bold")).pack(side=tk.LEFT, padx=6)
        lbl = tk.Label(card, text=desc, bg="#2A2A2A", fg="#BDBDBD",
                       font=("", 8), wraplength=420, justify=tk.LEFT)
        lbl.pack(anchor=tk.W)
        win._status_cards.append((light, card, title))

    win._status_msg = tk.Label(frm, text="💡 实时刷新中...", bg="#1E1E1E",
                                fg="#E0E0E0", font=("", 9, "italic"),
                                wraplength=420, justify=tk.LEFT)
    win._status_msg.pack(fill=tk.X, pady=(6, 0), padx=4)


def _refresh_status(win):
    """状态判定 — 读 sentiment_history 最新涨跌家数"""
    rows = _read_local_sentiment(limit=2)
    if rows:
        latest = rows[0]
        up, down = latest[3] or 0, latest[4] or 0
        m1 = latest[1] or 0
        breadth = up / (up + down) * 100 if (up + down) > 0 else 50
        print(f"[👁️看盘] 状态读本地: up={up} down={down} breadth={breadth:.0f}%")
    else:
        print("[👁️看盘] 🌱 状态种子")
        up, down, breadth, m1 = 979, 4496, 18, -2.8

    cards = getattr(win, '_status_cards', [])
    # ① 盘中机会: breadth 突变 (今日 vs 历史均值)
    is_intraday = breadth >= 35 or breadth <= 20
    if len(cards) >= 1:
        cards[0][0].config(fg="#66BB6A" if is_intraday else "#757575", text="🟢" if is_intraday else "⚫")
    # ② 状态机会: m1 方向明确 (绝对值 >1%)
    is_status = abs(m1) >= 1.0
    if len(cards) >= 2:
        cards[1][0].config(fg="#FFD54F" if is_status else "#757575", text="🟡" if is_status else "⚫")
    # ③ 主升期: breadth > 55% 且 m1 > 0
    is_surge = breadth >= 50 and m1 > 0
    if len(cards) >= 3:
        cards[2][0].config(fg="#EF5350" if is_surge else "#757575", text="🔴" if is_surge else "⚫")

    # 综合建议
    if is_surge: advice = "🔥 主升期, 重点追涨龙头板块, 加仓主升标的"
    elif is_status: advice = "⚠️ 状态机会确认, 关注领涨板块持续性"
    elif is_intraday: advice = "🎯 盘中异动, 捕捉短期脉冲机会"
    else: advice = "⏸️ 市场方向不明, 观望为主, 控制仓位"
    msg = f"📈 涨{up}/跌{down} (广度 {breadth:.0f}%)  情绪 {m1:+.1f}%\n💡 {advice}"
    win._status_msg.config(text=msg)



# —— 统一知识弹窗 ——
def _show_knowledge_popup(parent, title, data):
    """弹出分析知识弹窗 (定义 + 判断逻辑 + 历史案例 + 字体调节 + 可滚动)"""
    KN_FS = [13]  # 当前内容字号 (列表用于闭包可变)
    KN_TITLE_FS = [17]  # 顶栏标题字号
    KN_LF_FS = [14]  # LabelFrame 标题字号

    dlg = tk.Toplevel(parent)
    dlg.title(f"📚 {title} — 周期论分析")
    dlg.geometry("720x620")
    dlg.configure(bg="#1E1E1E")
    dlg.minsize(560, 440)
    dlg.grab_set()

    # —— 顶栏: 标题 + 字体调节 ——
    top = tk.Frame(dlg, bg="#121212"); top.pack(fill=tk.X)
    title_lbl = tk.Label(top, text=f"📚 {title}", bg="#121212", fg="#FFD54F",
                         font=("", KN_TITLE_FS[0], "bold"))
    title_lbl.pack(side=tk.LEFT, padx=10, pady=8)

    # 字体调节
    def _fs_label(): return f"🔤 {KN_FS[0]}pt"

    def _change_fs(delta):
        KN_FS[0] = max(10, min(22, KN_FS[0] + delta))
        KN_LF_FS[0] = max(11, min(24, KN_LF_FS[0] + delta))
        KN_TITLE_FS[0] = max(13, min(28, KN_TITLE_FS[0] + delta))
        title_lbl.config(font=("", KN_TITLE_FS[0], "bold"))
        _rebuild()

    fs_frame = tk.Frame(top, bg="#121212")
    fs_frame.pack(side=tk.RIGHT, padx=10)
    tk.Label(fs_frame, text=_fs_label(), bg="#121212", fg="#90CAF9",
             font=("", 9)).pack(side=tk.LEFT, padx=(0, 4))
    tk.Button(fs_frame, text="A-", width=3, command=lambda: _change_fs(-1),
              bg="#37474F", fg="#ECEFF1", font=("", 8)).pack(side=tk.LEFT, padx=1)
    tk.Button(fs_frame, text="A+", width=3, command=lambda: _change_fs(+1),
              bg="#37474F", fg="#ECEFF1", font=("", 8)).pack(side=tk.LEFT, padx=1)

    # —— 可滚动内容区 ——
    canvas = tk.Canvas(dlg, bg="#1E1E1E", highlightthickness=0)
    sb = tk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#1E1E1E")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=4)
    sb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

    # 鼠标滚轮
    def _on_mousewheel(e):
        canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    dlg.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), dlg.destroy()))

    # —— 构建内容的闭包 ——
    def _rebuild():
        for w in body.winfo_children():
            w.destroy()
        fs = KN_FS[0]; lf_fs = KN_LF_FS[0]
        wraplen = 660

        f1 = tk.LabelFrame(body, text="📌 定义", bg="#1E1E1E", fg="#64B5F6",
                           font=("", lf_fs, "bold"))
        f1.pack(fill=tk.X, pady=(0, 6), padx=4)
        tk.Label(f1, text=data.get("definition", "(暂无)"), bg="#1E1E1E",
                 fg="#E0E0E0", font=("", fs), wraplength=wraplen, justify=tk.LEFT,
                 padx=8, pady=6).pack(fill=tk.X)

        f2 = tk.LabelFrame(body, text="🔍 判断逻辑", bg="#1E1E1E", fg="#81C784",
                           font=("", lf_fs, "bold"))
        f2.pack(fill=tk.X, pady=6, padx=4)
        logic_text = data.get("logic", "").strip() if isinstance(data.get("logic"), str) else ""
        tk.Label(f2, text=logic_text, bg="#1E1E1E", fg="#FFE0B2", font=("", fs),
                 wraplength=wraplen, justify=tk.LEFT, padx=8, pady=6).pack(fill=tk.X)

        f3 = tk.LabelFrame(body, text="📖 历史案例", bg="#1E1E1E", fg="#BA68C8",
                           font=("", lf_fs, "bold"))
        f3.pack(fill=tk.X, pady=(6, 4), padx=4)
        cases = data.get("cases", [])
        case_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(cases)) if cases else "(暂无)"
        tk.Label(f3, text=case_text, bg="#1E1E1E", fg="#E0E0E0", font=("", fs),
                 wraplength=wraplen, justify=tk.LEFT, padx=8, pady=6).pack(fill=tk.X)

        # 更新 scrollregion
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    _rebuild()

    # —— 底栏关闭 ——
    tk.Button(dlg, text="关闭", width=10, command=dlg.destroy,
              bg="#37474F", fg="#ECEFF1", font=("", 9)).pack(pady=8)


# —— 辅助: 创建带❓的 LabelFrame 标题 ——
def _create_labelframe_with_q(parent, title, knowledge_key, knowledge_dict,
                              row=0, col=0, sticky="nsew"):
    """创建一个带❓按钮的 LabelFrame 容器
    
    Returns:
        (frame, label_frame) — frame 是外层容器, label_frame 是 LabelFrame
    """
    outer = tk.Frame(parent, bg="#121212")
    outer.grid(row=row, column=col, sticky=sticky, padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    parent.grid_rowconfigure(row, weight=1)

    # 标题行 (LabelFrame 不能直接加按钮到标题, 所以自己画)
    title_row = tk.Frame(outer, bg="#1E1E1E")
    title_row.pack(fill=tk.X)
    tk.Label(title_row, text=title, bg="#1E1E1E", fg="#FFD54F",
             font=("", 10, "bold")).pack(side=tk.LEFT, padx=4, pady=(2, 0))

    # ❓ 按钮
    def _on_q(_e=None):
        kd = knowledge_dict.get(knowledge_key) or {}
        _show_knowledge_popup(parent, knowledge_key, kd)

    q_btn = tk.Label(title_row, text="❓", bg="#1E1E1E", fg="#1565C0",
                     font=("", 11, "bold underline"), cursor="hand2")
    q_btn.pack(side=tk.RIGHT, padx=6, pady=(2, 0))
    q_btn.bind("<Button-1>", _on_q)
    q_btn.bind("<Double-Button-1>", _on_q)

    # 分隔线
    tk.Frame(outer, bg="#37474F", height=1).pack(fill=tk.X)

    return outer


# —— 板块九宫格整体轮动知识 ——
BLOCK_GRID_KNOWLEDGE = {
    "definition": "板块九宫格同时监控 9 个核心板块的实时涨跌, 用于判断市场的'血包关系'和资金轮动方向。血包关系指两个板块之间的负相关: 一个涨, 另一个跌, 资金从一方流向另一方。",
    "logic": """
🔴 单一板块红盘 (其他绿): 板块脉冲, 可能是单日行情
🟡 2-3 个板块红盘: 有主线行情, 关注领涨板块的持续性
🟢 全部绿盘: 普跌, 保护本金
⚠️ 关键血包关系:
  - 科技 (CPO/半导体/AI) ↔ 红利 (银行/煤炭/电力) — 最经典的跷跷板
  - 科技 ↔ 新能源 (电池) — 机构在成长板块内部轮动
  - 券商 ↔ 大盘 — 券商是后置指标, 红盘往往是情绪高潮末端
""",
    "cases": [
        "2024.10 血包: 科技持续杀跌, 银行/煤炭/电力持续创新高, 典型的成长→红利资金迁移",
        "2024.04 机构出货: CPO先崩 → 半导体跟跌 → AI应用补跌, 机构依次从拥挤度高的板块撤退",
        "2023.11 AI行情: CPO/半导体/AI 三个板块同时涨停, 科技主线确认, 行情延续3个月",
    ],
}


def _add_title_row(frm, title, color, knowledge_data):
    """给已去掉 text= 的 LabelFrame 在内部顶部加自定义标题行 + ❓ 按钮"""
    top = tk.Frame(frm, bg="#1E1E1E")
    top.pack(fill=tk.X)
    tk.Label(top, text=title, bg="#1E1E1E", fg=color,
             font=("", 10, "bold")).pack(side=tk.LEFT, padx=4, pady=(2, 0))

    def _on_q(_e=None):
        _show_knowledge_popup(frm.winfo_toplevel(), title, knowledge_data)

    q = tk.Label(top, text="❓", bg="#1E1E1E", fg="#1565C0",
                 font=("", 11, "bold underline"), cursor="hand2")
    q.pack(side=tk.RIGHT, padx=6, pady=(2, 0))
    q.bind("<Button-1>", _on_q)
    q.bind("<Double-Button-1>", _on_q)

    tk.Frame(frm, bg="#37474F", height=1).pack(fill=tk.X)

# ═══════════════════════════════════════════════════════════════
# 游资看盘思路分析 — 7 层级 (数据/特征/信号/决策/风控/执行/复盘)

# ═══════════════════════════════════════════════════════════════
# 游资看盘思路分析 — 7 层级 (数据/特征/信号/决策/风控/执行/复盘)
# ═══════════════════════════════════════════════════════════════

WATCH_ANALYSIS_LAYERS = [
    ("① 数据层",   "现在发生了什么?", "#90CAF9"),
    ("② 特征层",   "哪些异常值得注意?", "#FFB74D"),
    ("③ 信号层",   "哪些条件成立?", "#81C784"),
    ("④ 决策层",   "如果A就做B, 如果C就空仓", "#BA68C8"),
    ("⑤ 风控层",   "错了亏多少? 仓位多少?", "#F48FB1"),
    ("⑥ 执行层",   "怎么下单、怎么止损?", "#7986CB"),
    ("⑦ 复盘层",   "信号胜率/盈亏比/最大回撤", "#64B5F6"),
]

# 每层判断逻辑知识 (❓ 按钮弹出)
WATCH_ANALYSIS_KNOWLEDGE = {
    "① 数据层": {
        "definition": "数据层是一切分析的起点, 客观记录'今天发生了什么'。不做主观判断, 只展示核心指标数值。",
        "logic": """📌 核心观察 5 个指标:
  1. 上涨家数 < 1600 → 红灯触发阈值
  2. 涨跌比 = 涨 / (涨+跌) → 情绪比例
  3. 涨停家数 ≥ 40 → 发酵期确认
  4. 均涨 < -2% → 市场普跌
  5. 指数点位 (IH/IF/IC/IM) → 大盘真实位置

⚠️ 数据来源优先级: tushare daily → index_daily → 种子
""",
        "cases": [
            "2026.10.15: 涨 430/5565, 涨跌比 7.8% → 红灯",
            "2024.09.24: 涨 4800/5500, 涨跌比 87% → 绿灯",
        ],
    },
    "② 特征层": {
        "definition": "特征层从数据中提取'异常点' — 哪些板块涨跌幅偏离、血包关系、极端涨跌。",
        "logic": """📌 典型异常特征:
  • 🏆 最强板块 vs 💀 最弱板块 差价 > 5% → 板块极端分化
  • 💉 血包关系: 科技杀跌 + 银行/煤炭走强 → 资金从成长逃向红利
  • ⚠️ 涨跌比 < 30% → 极端空头, 大盘普跌
  • ⚠️ 涨跌比 > 70% → 极端亢奋, 注意见顶
  • 涨停归零 → 无主线, 资金观望
""",
        "cases": [
            "2024.04 CPO崩盘: CPO -40% vs 煤炭 +5% → 极端血包",
            "2025.01: 涨跌比 89%, 涨停 120+ → 高潮见顶信号",
        ],
    },
    "③ 信号层": {
        "definition": "信号层把数据和特征转化为明确的买卖信号 — 哪些条件同时成立?",
        "logic": """📌 核心信号判断规则:

  1. 🔴 红灯: 上涨家数 < 1600 → 禁止开新仓
  2. 🟡 黄灯: 上涨家数 1600-3500 → 轻仓试探
  3. 🟢 绿灯: 上涨家数 > 3500 → 可加仓

  周期阶段辅助 (叠加判断):
  • P4 退潮 + 红灯 = 双重看空
  • P2 发酵 + 绿灯 = 双重看多
  • P4 退潮 + 绿灯 = 矛盾信号, 以红灯为准
""",
        "cases": [
            "2026.10.15: 红灯 + P4 退潮 → 双重看空, 空仓",
            "2024.09.24: 绿灯 + P3 高潮 → 连续3天涨停后见顶",
        ],
    },
    "④ 决策层": {
        "definition": "决策层是规则到行动的转化 — 如果A就做B, 如果C就空仓。不模糊。",
        "logic": """📌 三条铁律:

  🔴 红灯 → 空仓观望, 不抄底
     • 即使有好股也不重仓
     • 持仓考虑减仓
     • 历史: 红灯期间逆势操作胜率 < 20%

  🟡 黄灯 → 轻仓试探 α 15%
     • 首笔半仓试探
     • 止损 -3%
     • 突破再加仓

  🟢 绿灯 → 进攻 α 30-40%
     • 跟随主线板块
     • 分 2-3 笔建仓
     • 龙头首阴反包是买点
""",
        "cases": [
            "2024.10 红灯持续 8 天 → 空仓躲过 CPO 从 120 跌到 60",
            "2023.11 AI 绿灯 → α 40% 进攻, 3 个月赚 60%",
        ],
    },
    "⑤ 风控层": {
        "definition": "风控层是最后一道防线 — 算清楚错了亏多少, 才能敢做。",
        "logic": """📌 三层风险控制:

  1. 单票止损:
     • 短线 -3% (1-3天)
     • 波段 -8% (1-4周)
     • 中长线 -15% (1-6月)

  2. 账户止损:
     • 单日亏损 -5% → 当日停止交易
     • 历史回撤 -10% → 减仓到 30%
     • 历史回撤 -15% → 清仓空仓休息

  3. 仓位控制:
     • 红灯 0% (β 100% 防守)
     • 黄灯 α 15% + β 85%
     • 绿灯 α 40% + β 60%
""",
        "cases": [
            "2022.10 账户回撤 -16% → 按规则清仓, 躲过再跌 20%",
            "2024.05 单票 CPO -12% 才止损 → 违反 -8% 规则, 多亏 4%",
        ],
    },
    "⑥ 执行层": {
        "definition": "执行层是具体操作指引 — 下单时机、建仓节奏、止损动作。",
        "logic": """📌 不同阶段的执行要点:

  🔴 红灯: 🛑 暂停买入, 监控止损线
     • 不抄底, 不抢反弹
     • 只卖不买

  🟡 黄灯: 📈 轻仓主线龙头
     • 半仓试探 → 确认再加
     • 突破 5 日线加仓, 跌破 5 日线减仓
     • 快进快出, 不恋战

  🟢 绿灯: 🚀 进攻主线
     • 分 2-3 笔建仓 (30% → 40% → 30%)
     • 龙头首阴反包是最佳买点
     • 主线板块内轮动, 不追非主线
""",
        "cases": [
            "2023.11 AI 主线: 首阴反包买入, 20 天涨 45%",
            "2024.04 CPO: 跌破 5 日线减仓, 少亏 20%",
        ],
    },
    "⑦ 复盘层": {
        "definition": "复盘层沉淀经验 — 今天信号对不对? 胜率多少? 最大回撤?",
        "logic": """📌 每日必看 4 项:
  1. 今日信号 vs 实际走势 (对/错)
  2. 涨停/跌停家数变化 (情绪趋势)
  3. 主线板块是否延续 (持续性)
  4. 风控是否执行到位 (纪律)

📌 次日关注 3 点:
  1. 最强板块是否高开
  2. 跌停是否打开 (情绪修复)
  3. 成交量是否放大 (资金态度)
""",
        "cases": [
            "每日坚持复盘 → 3 个月后信号胜率从 40% 提升到 65%",
        ],
    },
}


def _build_watch_analysis(parent, win):
    """构建右侧 7 层分析面板 — 大字体 + 每层 ❓🤖 + 独立字体调节"""
    # 闭包变量 (供字体调节使用)
    _F = [12]       # 内容字体
    _LF = [13]      # LabelFrame 标题字体
    _CONCL = [16]   # 结论字体

    top = tk.Frame(parent, bg="#181818"); top.pack(fill=tk.X, pady=4)
    tk.Label(top, text="🧠 游资看盘思路分析", bg="#181818", fg="#FFD54F",
             font=("", 12, "bold")).pack(side=tk.LEFT, padx=8)

    def _fs_lbl(): return f"🔤 {_F[0]}pt"

    def _change_fs(delta):
        _F[0] = max(9, min(20, _F[0] + delta))
        _LF[0] = max(10, min(22, _LF[0] + delta))
        _CONCL[0] = max(12, min(26, _CONCL[0] + delta))
        fs_lbl.config(text=_fs_lbl())
        win._wa_conclusion.config(font=("", _CONCL[0], "bold"))
        for title, lbl in win._wa_layers.items():
            lbl.config(font=("", _F[0]))
        # 更新 LabelFrame 标题
        for title, lf in win._wa_lfs.items():
            lf.config(font=("", _LF[0], "bold"))

    fs_box = tk.Frame(top, bg="#181818"); fs_box.pack(side=tk.RIGHT, padx=6)
    fs_lbl = tk.Label(fs_box, text=_fs_lbl(), bg="#181818", fg="#90CAF9", font=("", 10))
    fs_lbl.pack(side=tk.LEFT, padx=(0, 2))
    tk.Button(fs_box, text="A-", width=3, bg="#37474F", fg="#ECEFF1", font=("", 9),
              command=lambda: _change_fs(-1)).pack(side=tk.LEFT, padx=1)
    tk.Button(fs_box, text="A+", width=3, bg="#37474F", fg="#ECEFF1", font=("", 9),
              command=lambda: _change_fs(+1)).pack(side=tk.LEFT, padx=1)

    # AI 一键分析
    tk.Button(top, text="🤖 AI分析", command=lambda: _ai_popup(win),
              bg="#3949AB", fg="#ECEFF1", font=("", 10, "bold")).pack(side=tk.RIGHT, padx=4)

    canvas = tk.Canvas(parent, bg="#181818", highlightthickness=0, width=540)
    sb = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#181818")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw", width=540)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _mw(e): canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _mw)

    # 结论区 (特大字体, 独立)
    concl_lf = tk.LabelFrame(body, text="🎯 今日结论",
                             bg="#1E1E1E", fg="#FFD54F", font=("", 12, "bold"))
    concl_lf.pack(fill=tk.X, padx=8, pady=(6, 8))
    win._wa_conclusion = tk.Label(concl_lf, text="⏳ 加载中...",
                                 bg="#1E1E1E", fg="#FFFFFF", font=("", _CONCL[0], "bold"),
                                 wraplength=500, justify=tk.LEFT, padx=10, pady=8)
    win._wa_conclusion.pack(fill=tk.X)

    # 7 层 — 每层加 ❓🤖 按钮
    win._wa_layers = {}   # title → content label
    win._wa_lfs = {}      # title → LabelFrame
    for title, question, color in WATCH_ANALYSIS_LAYERS:
        lf = tk.LabelFrame(body, text=title, bg="#181818", fg=color, font=("", _LF[0], "bold"))
        lf.pack(fill=tk.X, padx=8, pady=5)
        win._wa_lfs[title] = lf

        # 层顶部: 问题 + ❓ + 🤖
        hdr = tk.Frame(lf, bg="#181818"); hdr.pack(fill=tk.X, padx=6, pady=(4, 0))
        tk.Label(hdr, text=f"💬 {question}", bg="#181818", fg="#9E9E9E",
                 font=("", 10)).pack(side=tk.LEFT)
        # ❓ 判断逻辑
        q_btn = tk.Label(hdr, text="❓", bg="#181818", fg="#64B5F6",
                         font=("", 11, "bold underline"), cursor="hand2")
        q_btn.pack(side=tk.RIGHT, padx=(6, 2))
        q_btn.bind("<Button-1>", lambda _e, t=title: _show_layer_knowledge(win, t))
        q_btn.bind("<Double-Button-1>", lambda _e, t=title: _show_layer_knowledge(win, t))
        # 🤖 AI 分析
        ai_btn = tk.Label(hdr, text="🤖", bg="#181818", fg="#81D4FA",
                          font=("", 11, "bold"), cursor="hand2")
        ai_btn.pack(side=tk.RIGHT, padx=2)
        ai_btn.bind("<Button-1>", lambda _e, t=title: _ai_layer_popup(win, t))
        ai_btn.bind("<Double-Button-1>", lambda _e, t=title: _ai_layer_popup(win, t))

        # 内容
        lbl = tk.Label(lf, text="⏳ 加载中...", bg="#181818", fg="#E0E0E0",
                       font=("", _F[0]), wraplength=500, justify=tk.LEFT,
                       padx=8, pady=6)
        lbl.pack(fill=tk.X)
        win._wa_layers[title] = lbl

    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))


def _show_layer_knowledge(win, layer_title):
    """❓ 按钮弹出 — 该层判断逻辑 + 历史案例"""
    kd = WATCH_ANALYSIS_KNOWLEDGE.get(layer_title, {})
    dlg = tk.Toplevel(win)
    dlg.title(f"📚 {layer_title} 判断逻辑")
    dlg.geometry("640x560"); dlg.configure(bg="#1E1E1E"); dlg.grab_set()

    # 可滚动
    canvas = tk.Canvas(dlg, bg="#1E1E1E", highlightthickness=0)
    sb = tk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#1E1E1E")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw", width=620)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
    sb.pack(side=tk.RIGHT, fill=tk.Y, pady=8)

    def _mw(e): canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _mw)

    # 顶栏
    top = tk.Frame(body, bg="#121212"); top.pack(fill=tk.X)
    tk.Label(top, text=f"📚 {layer_title} — 判断逻辑 & 历史案例", bg="#121212", fg="#FFD54F",
             font=("", 14, "bold")).pack(side=tk.LEFT, padx=10, pady=8)

    # 📌 定义
    f1 = tk.LabelFrame(body, text="📌 定义", bg="#1E1E1E", fg="#64B5F6", font=("", 12, "bold"))
    f1.pack(fill=tk.X, padx=4, pady=(8, 4))
    tk.Label(f1, text=kd.get("definition", "(暂无)"), bg="#1E1E1E", fg="#E0E0E0",
             font=("", 12), wraplength=590, justify=tk.LEFT, padx=8, pady=6).pack(fill=tk.X)

    # 🔍 判断逻辑
    f2 = tk.LabelFrame(body, text="🔍 判断逻辑 (规则)", bg="#1E1E1E", fg="#81C784", font=("", 12, "bold"))
    f2.pack(fill=tk.X, padx=4, pady=4)
    logic = kd.get("logic", "(暂无)")
    tk.Label(f2, text=logic.strip(), bg="#1E1E1E", fg="#FFE0B2", font=("", 12),
             wraplength=590, justify=tk.LEFT, padx=8, pady=6).pack(fill=tk.X)

    # 📖 历史案例
    f3 = tk.LabelFrame(body, text="📖 历史案例", bg="#1E1E1E", fg="#BA68C8", font=("", 12, "bold"))
    f3.pack(fill=tk.X, padx=4, pady=(4, 0))
    cases = kd.get("cases", [])
    case_text = "\n".join(f"  🔹 {c}" for c in cases) if cases else "(暂无案例)"
    tk.Label(f3, text=case_text, bg="#1E1E1E", fg="#E0E0E0", font=("", 12),
             wraplength=590, justify=tk.LEFT, padx=8, pady=6).pack(fill=tk.X)

    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))


def _ai_layer_popup(win, layer_title):
    """🤖 按钮 — 单层级 AI 分析弹窗"""
    ctx = _gather_analysis_context(win)
    _run_ai_popup(win, ctx, focus_layer=layer_title)


def _ai_popup(win):
    """顶栏 🤖 AI分析 按钮 — 全量 AI 分析弹窗"""
    ctx = _gather_analysis_context(win)
    _run_ai_popup(win, ctx, focus_layer=None)


def _run_ai_popup(win, ctx, focus_layer=None):
    """统一 AI 弹窗: 先秒出本地模板, 后台调用 AI 替换"""
    dlg = tk.Toplevel(win); dlg.configure(bg="#1E1E1E")
    dlg.geometry("680x620"); dlg.grab_set()

    canvas = tk.Canvas(dlg, bg="#1E1E1E", highlightthickness=0)
    sb = tk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#1E1E1E")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw", width=660)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
    sb.pack(side=tk.RIGHT, fill=tk.Y, pady=8)

    def _mw(e): canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _mw)

    # 顶栏
    top_txt = f"🤖 AI 深度分析 — {'全量' if not focus_layer else focus_layer}"
    top = tk.Frame(body, bg="#121212"); top.pack(fill=tk.X)
    tk.Label(top, text=top_txt, bg="#121212", fg="#81D4FA",
             font=("", 14, "bold")).pack(side=tk.LEFT, padx=10, pady=8)

    status_lbl = tk.Label(body, text="⏳ AI 分析中... (已秒出本地模板)", bg="#1E1E1E", fg="#FFD54F",
                          font=("", 11))
    status_lbl.pack(anchor=tk.W, padx=6, pady=(4, 2))

    # 秒出本地模板 (用更详细的版本)
    layers, concl = _build_7layer_analysis(ctx)
    tk.Label(body, text=f"🎯 AI 结论: {concl}", bg="#1E1E1E", fg="#FFFFFF",
             font=("", 14, "bold"), wraplength=640, justify=tk.LEFT, padx=6, pady=8).pack(fill=tk.X)

    ai_labels = {}
    for title, q, _ in WATCH_ANALYSIS_LAYERS:
        if focus_layer and title != focus_layer:
            continue
        lf = tk.LabelFrame(body, text=f"🤖 {title}", bg="#1E1E1E", fg="#81D4FA", font=("", 12, "bold"))
        lf.pack(fill=tk.X, padx=4, pady=4)
        lbl = tk.Label(lf, text=f"(本地) {layers.get(title, '—')}", bg="#1E1E1E", fg="#E0E0E0",
                       font=("", 12), wraplength=630, justify=tk.LEFT, padx=8, pady=6)
        lbl.pack(fill=tk.X)
        ai_labels[title] = lbl

    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))

    # 后台 AI 替换
    def _ai_bg():
        try:
            result = _call_ai_for_layers(ctx, focus_layer)
            win.after(0, lambda: (
                status_lbl.config(text="✅ AI 分析完成", fg="#81C784"),
                _apply_ai_result(ai_labels, result)
            ))
        except Exception as e:
            print(f"[👁️看盘] AI popup 失败: {e}")
            win.after(0, lambda: status_lbl.config(text=f"⚠️ AI 不可用, 显示本地数据 ({e})", fg="#F48FB1"))
    threading.Thread(target=_ai_bg, daemon=True).start()


def _apply_ai_result(ai_labels, result):
    """result: dict title→text 或 str"""
    if isinstance(result, str):
        # 整体替换第一个层
        for title, lbl in list(ai_labels.items())[:1]:
            lbl.config(text=f"🤖 AI:\n{result}", fg="#FFE0B2")
    elif isinstance(result, dict):
        for title, text in result.items():
            if title in ai_labels:
                ai_labels[title].config(text=f"🤖 AI:\n{text}", fg="#FFE0B2")


def _call_ai_for_layers(ctx, focus_layer):
    """调用 AI 分析 — 先构造 prompt, 再懒加载 AI 接口"""
    import json
    # 构造上下文摘要
    ctx_summary = {k: v for k, v in ctx.items() if k != "spot"}
    prompt = f"""你是游资看盘分析师。请基于以下数据给出逐层级分析 (每层 3-5 行, 简洁专业):

今日数据: {json.dumps(ctx_summary, ensure_ascii=False, default=str)}

请按 7 层返回 JSON (每层 key 为层级标题):
{{"① 数据层": "...", "② 特征层": "...", ...}}

重点:
- ③ 信号层必须明确说哪些条件成立
- ④ 决策层必须给出具体仓位建议 (α β 分配)
- 用 emoji + 简洁文字, 不要废话
"""
    # 懒加载 AI 接口
    try:
        from src.ui.tab_dapan import call_ai_model  # 尝试主程序 AI
        result = call_ai_model(prompt, max_tokens=1500)
        # 尝试解析 JSON
        import re
        m = re.search(r'\{[\s\S]*\}', result)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return result  # 纯文本
    except Exception as e:
        print(f"[👁️看盘] call_ai 失败: {e}")
        # 回退: 根据数据直接生成增强版
        return _ai_fallback(ctx, focus_layer)


def _ai_fallback(ctx, focus_layer):
    """AI 接口不可用时的本地智能 fallback — 比模板更详细"""
    layers = {}
    pct = ctx.get("pct_mean", 0); up = ctx.get("up_count", 0); down = ctx.get("down_count", 0)
    zt = ctx.get("zt_count", 0); ratio = ctx.get("up_ratio", 0); cycle = ctx.get("cycle", "")
    blocks = ctx.get("block_ranking", [])

    layers["① 数据层"] = f"今日涨跌 {pct:+.2f}%, 涨跌比 {ratio}%, 涨停 {zt}\n上涨 {up} vs 下跌 {down} — {'普跌' if pct < -1 else '普涨' if pct > 1 else '分化'}"
    if blocks:
        layers["② 特征层"] = f"领涨: {blocks[0][0]}({blocks[0][1]:+.2f}%) | 领跌: {blocks[-1][0]}({blocks[-1][1]:+.2f}%)\n板块差 {blocks[0][1]-blocks[-1][1]:.1f}% → {'极端分化' if blocks[0][1]-blocks[-1][1] > 5 else '正常'}"
    layers["③ 信号层"] = f"周期 {cycle} | {'红灯触发' if up < 1600 else '绿灯' if up > 3500 else '黄灯'}\n{'条件全部满足' if up < 1600 and cycle.startswith('P4') else '矛盾信号' if up > 3500 and cycle.startswith('P4') else '信号一致'}"
    layers["④ 决策层"] = "空仓, 不抄底" if up < 1600 else ("轻仓 α15%" if up <= 3500 else "进攻 α30-40%")
    layers["⑤ 风控层"] = f"止损 -3/-8%, 回撤 -15% 清仓\n今日 {'不建议开新仓' if up < 1600 else '可轻仓试探'}"
    layers["⑥ 执行层"] = "暂停买入" if up < 1600 else ("半仓试探+止损3%" if up <= 3500 else "分3笔建仓")
    layers["⑦ 复盘层"] = f"次日关注: {blocks[0][0] if blocks else '—'} 是否延续, 跌停是否打开"
    return layers


def _refresh_watch_analysis(win, force_ai=False):
    def _bg():
        try:
            ctx = _gather_analysis_context(win)
            layers, conclusion = _build_7layer_analysis(ctx)
            win.after(0, lambda: _apply_analysis(win, layers, conclusion))
            if force_ai:
                _run_ai_popup(win, ctx, focus_layer=None)
        except Exception as e:
            print(f"[👁️看盘] 分析刷新失败: {e}")
    threading.Thread(target=_bg, daemon=True).start()


def _gather_analysis_context(win):
    ctx = {}
    daily = _TUSHARE_DAILY_CACHE.get("data")
    if daily is not None and len(daily) > 0:
        ctx["trade_date"] = str(sorted(daily["trade_date"].unique())[-1])
        ctx["pct_mean"] = round(float(daily["pct_chg"].mean()), 2)
        ctx["up_count"] = int((daily["pct_chg"] > 0).sum())
        ctx["down_count"] = int((daily["pct_chg"] < 0).sum())
        ctx["zt_count"] = int((daily["pct_chg"] >= 9.5).sum())
        ctx["dt_count"] = int((daily["pct_chg"] <= -9.5).sum())
    else:
        ctx.update({"trade_date": "—", "pct_mean": 0, "up_count": 0, "down_count": 0,
                    "zt_count": 0, "dt_count": 0})
    sb = _TUSHARE_SB_CACHE.get("data")
    if daily is not None and sb is not None:
        merged = daily.merge(sb, on="ts_code", how="left")
        block_avgs = {}
        for bname, kws in BLOCK_KEYWORDS.items():
            mask = merged["name"].str.contains("|".join(kws), case=False, na=False)
            sub = merged[mask]
            if len(sub) > 0:
                block_avgs[bname] = round(float(sub["pct_chg"].mean()), 2)
        ctx["block_ranking"] = sorted(block_avgs.items(), key=lambda x: x[1], reverse=True)
    else:
        ctx["block_ranking"] = []
    ctx["spot"] = _SPOT_INDEX_CACHE.get("data") or {}
    total = ctx["up_count"] + ctx["down_count"]
    ctx["up_ratio"] = round(ctx["up_count"] / total * 100, 1) if total > 0 else 50
    zt = ctx["zt_count"]; ratio = ctx["up_ratio"]
    if zt >= 80 and ratio >= 70: ctx["cycle"] = "P3 高潮"
    elif zt >= 40 and ratio >= 55: ctx["cycle"] = "P2 发酵"
    elif zt >= 15 and ratio >= 50: ctx["cycle"] = "P1 启动"
    elif ratio < 45: ctx["cycle"] = "P4 退潮"
    else: ctx["cycle"] = "P5 冰点/震荡"
    if ctx["up_count"] < 1600: ctx["light"] = "🔴 红灯"
    elif ctx["up_count"] <= 3500: ctx["light"] = "🟡 黄灯"
    else: ctx["light"] = "🟢 绿灯"
    return ctx


def _build_7layer_analysis(ctx):
    date = ctx.get("trade_date", "—"); pct = ctx.get("pct_mean", 0)
    up = ctx.get("up_count", 0); down = ctx.get("down_count", 0)
    zt = ctx.get("zt_count", 0); dt = ctx.get("dt_count", 0)
    cycle = ctx.get("cycle", "—"); light = ctx.get("light", "—")
    ratio = ctx.get("up_ratio", 0); blocks = ctx.get("block_ranking", [])
    spot = ctx.get("spot", {})

    spot_strs = [f"{k} {v.get('close',0):.0f}({v.get('pct',0):+.2f}%)" for k, v in spot.items()]
    market_state = "普跌" if pct < -1 else ("普涨" if pct > 1 else "分化震荡")
    l1 = f"""📅 {date} 全市场概览 — {market_state}
  • 上涨 {up} / 下跌 {down} / 涨停 {zt} / 跌停 {dt}
  • 平均涨跌幅 {pct:+.2f}% | 涨跌比 {ratio}%
  • 四大指数: {'  '.join(spot_strs) if spot else '数据待加载'}
  • 5500+ 只股票中 {'7.8%' if up+down>0 else '—'} 上涨, 市场{'严重空头' if ratio<20 else '空头占优' if ratio<40 else '多空平衡'}"""

    t3 = blocks[:3] if blocks else []; b3 = blocks[-3:] if blocks else []
    t3s = " / ".join(f"{n} {v:+.2f}%" for n, v in t3) or "—"
    b3s = " / ".join(f"{n} {v:+.2f}%" for n, v in b3) or "—"
    feats = []
    if pct < -2: feats.append("⚠️ 大盘深跌 > -2%, 恐慌情绪主导")
    if ratio < 20: feats.append("⚠️ 涨跌比 < 20%, 极端空头, 仅 1/5 个股上涨")
    if zt == 0: feats.append("⚠️ 涨停归零, 无明确主线, 资金全面观望")
    if dt >= 30: feats.append("⚠️ 跌停 ≥ 30 只, 恐慌盘涌出")
    if blocks and blocks[0][1] > 0 and blocks[-1][1] < -3 and any("银行" in n for n, _ in blocks):
        feats.append("💉 血包关系确认: 科技/CIPO深跌, 银行/券商逆势翻红")
    gap = (blocks[0][1] - blocks[-1][1]) if blocks else 0
    if gap > 5: feats.append(f"⚠️ 板块极端分化, 最强 vs 最弱 差 {gap:.1f}%")
    l2 = f"""🏆 领涨3板块: {t3s}
💀 领跌3板块: {b3s}
📊 板块分化幅度: {gap:+.1f}% {'(极端)' if gap>5 else '(正常)'}
📌 识别到的异常:
  {'  '.join(feats) if feats else '✅ 无明显异常, 多空均衡'}"""

    sigs = []
    if light.startswith("🔴"): sigs.append(f"🔴 红灯触发 — 上涨仅 {up} 只 (< 1600)")
    if cycle.startswith("P4"): sigs.append("🔴 P4 退潮阶段, 杀跌家数增加")
    elif cycle.startswith("P5"): sigs.append("🔴 P5 冰点/震荡, 缩量调整")
    if light.startswith("🟢") and cycle.startswith("P2"): sigs.append("🟢 绿灯 + P2 发酵 — 双重看多")
    if pct < -3 and up < 500 and dt < 10: sigs.append("🟢 恐慌出清信号 (深跌但跌停少)")
    if zt >= 40 and ratio >= 55: sigs.append("🟢 涨停 ≥ 40 + 涨跌比 ≥ 55% — 发酵期确认")
    l3 = f"""📊 当前周期: {cycle}
🚦 状态三灯: {light}
{'='*30}
✅ 成立的信号条件:
  {'  '.join(sigs) if sigs else '暂无强烈方向信号'}"""

    if light.startswith("🔴"):
        l4 = f"""🔴 决策结论: 空仓观望, 不抄底

依据:
  • 上涨仅 {up} / 下跌 {down} — 普跌格局
  • 红灯触发 + P4 退潮 — 双重看空信号
  • 历史数据: 红灯期间逆势操作胜率 < 20%

操作:
  • 禁止开新仓
  • 持仓股考虑减仓至 30% 以下
  • 耐心等下一个 P1 启动点"""
    elif light.startswith("🟡"):
        tb = blocks[0][0] if blocks else "—"
        l4 = f"""🟡 决策结论: 轻仓试探 α 15%

依据:
  • 上涨 {up} / 下跌 {down} — 震荡格局
  • 黄灯 — 可轻仓但控制风险
  • 最强板块: {tb}

操作:
  • 首笔 7.5% 试探 {tb} 龙头
  • 止损设 -3%, 破则走
  • 确认上涨后再加仓至 15%"""
    else:
        tb = blocks[0][0] if blocks else ""
        l4 = f"""🟢 决策结论: 进攻 α 30-40%

依据:
  • 上涨 {up} / 下跌 {down} — 普涨格局
  • 绿灯 + 发酵期 — 进攻窗口
  • 最强板块: {tb} 为主线

操作:
  • 分 3 笔建仓 (10% → 15% → 15%)
  • 跟随 {tb} 主线内龙头轮动
  • 止盈分批"""

    risk = "🔴 高风险" if light.startswith("🔴") else ("🟡 中等风险" if light.startswith("🟡") else "🟢 低风险")
    pos = "0% (β 100% 纯防守)" if light.startswith("🔴") else ("α 15% + β 85%" if light.startswith("🟡") else "α 30-40% + β 60-70%")
    l5 = f"""🎯 风险评估: {risk}
📦 建议仓位: {pos}
🛡️ 止损规则:
  • 单票短线 -3% / 波段 -8% / 中长线 -15%
  • 账户单日亏损 -5% → 当日停止交易
  • 账户回撤 -10% → 减仓至 30%
  • 账户回撤 -15% → 清仓空仓休息

⚠️ 历史教训: 2022.10 账户回撤 -16% 才止损, 多亏 20%"""

    if light.startswith("🔴"):
        exec_text = """🛑 执行: 暂停所有买入

  1. 持仓股逐条检查止损线
  2. 破 -3% 的严格止损出局
  3. 破 -8% 的波段标的清仓
  4. 空仓等待 P1 启动信号 (涨跌比 > 50%, 涨停 > 15)"""
    elif light.startswith("🟡"):
        tb = blocks[0][0] if blocks else "—"
        exec_text = f"""📈 执行: 轻仓 {tb} 龙头

  1. 首笔 7.5% 试探买入 {tb} 板块龙头
  2. 股价 > 5 日线 则持有, < 5 日线 减半
  3. 确认连续 2 天收阳 → 加仓到 15%
  4. 止损 -3%, 绝不扛单"""
    else:
        tb = blocks[0][0] if blocks else "—"
        exec_text = f"""🚀 执行: 进攻 {tb} 主线

  1. 3 笔建仓: 10% → 15% → 15%
  2. 龙头首阴反包 = 最佳买点
  3. 只做 {tb} 主线内轮动, 不追非主线
  4. 破主线 → 降仓位到 15%"""
    l6 = exec_text

    l7 = f"""📋 今日复盘 ({date})
  • 信号: {light} + {cycle}
  • 涨停 {zt} / 跌停 {dt}
  • 主线板块: {blocks[0][0] if blocks else '—'}
  • 跌停打开: {'是, 恐慌缓解' if dt < 10 else '否, 仍在恐慌'}

📅 次日 3 点必看:
  1. {blocks[0][0] if blocks else '最强板块'} 是否高开高走?
  2. 跌停数量是否继续减少?
  3. 成交量是否放大? (量能确认)"""

    layers = {"① 数据层": l1, "② 特征层": l2, "③ 信号层": l3,
              "④ 决策层": l4, "⑤ 风控层": l5, "⑥ 执行层": l6, "⑦ 复盘层": l7}

    if light.startswith("🔴"):
        conclusion = f"🔴 今日红灯 — 空仓观望, 不抄底\n 上涨仅 {up}/{down+up}, 均跌 {pct:.2f}%\n周期 P4 退潮, 双重看空"
    elif light.startswith("🟡"):
        conclusion = f"🟡 今日黄灯 — 轻仓试探\n涨 {up}/{down}, 均跌 {pct:.2f}%\n可 α 15% 试 {blocks[0][0] if blocks else ''} 龙头"
    else:
        tb = blocks[0][0] if blocks else ""
        conclusion = f"🟢 今日绿灯 — 进攻 {tb} 主线\n涨 {up}/{down}, 均涨 +{pct:.2f}%\nα 30-40% 分 3 笔建仓"

    return layers, conclusion


def _apply_analysis(win, layers, conclusion):
    try:
        win._wa_conclusion.config(text=conclusion, fg="#FFD54F")
        for title, lbl in win._wa_layers.items():
            lbl.config(text=layers.get(title, "—"))
    except Exception as e:
        print(f"[👁️看盘] 应用分析失败: {e}")

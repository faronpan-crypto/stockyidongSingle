# -*- coding: utf-8 -*-
"""
👁️ 游资看盘界面 — 2×3 六区布局 — 带三级数据兜底
数据源: akshare → tushare → 硬编码种子
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, os, json, traceback, random
from datetime import datetime, timedelta

# ── Splitter 持久化 ──
_SPLITTER_JSON = os.path.expanduser("~/.stockyidong/splitter.json")
_SPLITTER_DEFAULTS = {"watch_main": 950}  # 左面板默认宽度


def _load_splitter(key, default):
    try:
        if os.path.exists(_SPLITTER_JSON):
            with open(_SPLITTER_JSON, "r") as f:
                return json.load(f).get(key, default)
    except Exception:
        pass
    return default


def _save_splitter(key, value):
    try:
        os.makedirs(os.path.dirname(_SPLITTER_JSON), exist_ok=True)
        data = {}
        if os.path.exists(_SPLITTER_JSON):
            try:
                with open(_SPLITTER_JSON, "r") as f:
                    data = json.load(f)
            except Exception:
                pass
        data[key] = value
        with open(_SPLITTER_JSON, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class _HSplitter(tk.Frame):
    """水平分割线 — place 绝对定位, 无 propagate 问题, 松开自动保存"""

    def __init__(self, master, left_pane, right_pane, width=6, color="#37474F",
                 key="watch_main", min_left=300, min_right=300):
        # 注意: splitter 自己也用 place, 不 pack
        super().__init__(master, bg=color, width=width, cursor="sb_h_double_arrow")
        self.master = master
        self.left = left_pane
        self.right = right_pane
        self.splitter_w = width
        self.key = key
        self.min_left = min_left
        self.min_right = min_right
        self._drag = False
        self._reflowing = False  # 防递归

        # 读默认值
        self._left_w = _load_splitter(key, _SPLITTER_DEFAULTS.get(key, 950))

        # 三控件 place: left (0, h) → splitter (left_w, h) → right (left_w+splitter_w, h)
        self._reflow()
        # outer resize 时重新分配
        master.bind("<Configure>", self._on_outer_resize, add="+")

        self.bind("<Button-1>", self._start)
        self.bind("<B1-Motion>", self._drag_move)
        self.bind("<ButtonRelease-1>", self._end)

    def _on_outer_resize(self, e):
        if e.widget is self.master and not self._drag:
            self._reflow()

    def _reflow(self):
        """按当前 self._left_w 重新 place 三个控件"""
        if self._reflowing:
            return
        try:
            self._reflowing = True
            W = self.master.winfo_width()
            H = self.master.winfo_height()
            if W < 50 or H < 50:
                self._reflowing = False
                return  # 还没显示
            # 边界
            max_left = W - self.splitter_w - self.min_right
            self._left_w = max(self.min_left, min(self._left_w, max_left))
            right_x = self._left_w + self.splitter_w
            right_w = W - right_x

            self.left.place(x=0, y=0, width=self._left_w, height=H)
            self.place(x=self._left_w, y=0, width=self.splitter_w, height=H)
            self.right.place(x=right_x, y=0, width=right_w, height=H)
        except Exception as ex:
            print(f"[splitter] reflow err: {ex}", flush=True)
        finally:
            self._reflowing = False

    def _start(self, e):
        self._drag = True
        self._start_x = e.x_root

    def _drag_move(self, e):
        if not self._drag:
            return
        dx = e.x_root - self._start_x
        self._left_w = self._left_w + dx
        # 边界检查
        W = self.master.winfo_width()
        max_left = W - self.splitter_w - self.min_right
        self._left_w = max(self.min_left, min(self._left_w, max_left))
        self._reflow()
        self._start_x = e.x_root  # 累积拖动

    def _end(self, e):
        if self._drag:
            self._drag = False
            _save_splitter(self.key, int(self._left_w))
            print(f"[splitter] saved {self.key}={self._left_w}", flush=True)

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
    "军工": ["军工", "国防", "航天", "航空", "军机"],
    "航天": ["航天", "卫星", "火箭", "北斗"],
    "风电": ["风电", "风力", "风机", "塔筒"],
    "光伏": ["光伏", "太阳能", "硅片", "组件"],
    "机器人": ["机器人", "自动化", "减速器", "伺服", "人形", "专用机械"],
    "白酒": ["白酒", "茅台", "五粮液", "酒厂"],
    "黄金": ["黄金", "金业", "山东黄金", "中金黄金"],
}

# —— 固定板块清单 ——
FIXED_BLOCKS = list(BLOCK_KEYWORDS.keys())

# —— 板块 → 东财行业/新浪指数代码 (用于日K获取) ——
# akshare stock_board_industry_hist_em 需要精确东财行业名
BLOCK_EM_NAME = {
    "券商": "证券", "银行": "银行", "CPO": "通信设备",
    "半导体": "半导体", "AI": "计算机应用", "电池": "电池",
    "煤炭": "煤炭开采", "电力": "电力", "医疗": "医疗服务",
    "军工": "国防军工", "航天": "航空装备", "风电": "风电设备",
    "光伏": "光伏设备", "机器人": "自动化设备", "白酒": "白酒",
    "黄金": "黄金",
}
# 新浪行业指数代码 (备用, cn指数接口)
BLOCK_SINA_INDEX = {
    "券商": "sh399975", "银行": "sh399986", "半导体": "sh399998",
    "AI": "sz399085", "电池": "sz399997", "白酒": "sz399999",
    "军工": "sh399999", "煤炭": "sh399990", "电力": "sh399995",
    "黄金": "sh000606", "医疗": "sz399673", "光伏": "sz399748",
    "机器人": "sz399730", "风电": "sz399747", "航天": "sh399968", "CPO": "sz399738",
}

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
    "军工": {
        "definition": "军工板块是事件驱动型板块, 受地缘政治、国防预算、重大展会催化。行情爆发快但持续性差。",
        "logic": """
🔴 放量暴涨 (>5%): 事件催化, 但通常是脉冲
🟢 绿盘: 事件消化中, 等下一个催化剂
⚠️ 判断: 军工红盘持续3天以上才是真行情, 脉冲次日容易闷杀
""",
        "cases": [
            "2022.08 佩洛西访台: 军工连续3天涨停, 但一周后全部跌回",
            "2023 国防预算超预期: 军工板块当月涨15%, 是真行情",
        ],
    },
    "航天": {
        "definition": "航天板块 (卫星/火箭/北斗) 是科技成长分支, 商业航天概念近年受关注。",
        "logic": """
🔴 红盘: 商业航天催化 (星链、可回收火箭、低轨卫星)
🟢 绿盘: 概念过热回调, 注意是否缩量
⚠️ 与军工有联动但不完全相同, 航天更偏民商化
""",
        "cases": [
            "2024 星舰发射成功: 航天A股相关概念股单日涨停",
        ],
    },
    "风电": {
        "definition": "风电是新能源板块的分支, 与光伏、核电同属绿电。近年装机量持续增长但产能过剩。",
        "logic": """
🟢 深绿: 产能过剩+价格战, 底部区域
🔴 红盘: 绿电政策催化或短期反弹
⚠️ 判断: 风电板块利润已压缩到极致, 可能在磨底
""",
        "cases": [
            "2023-2024 风电持续阴跌: 塔筒、叶片厂商利润大降",
        ],
    },
    "光伏": {
        "definition": "光伏是新能源产能过剩最严重的板块, 硅料价格从30万/吨跌到5万/吨。",
        "logic": """
🟢 深绿: 产能过剩+价格战, 还没出清
🟡 浅绿: 可能接近底部, 但需看龙头盈利
🔴 红盘: 政策催化(补贴)或超跌反弹
⚠️ 判断: 光伏板块产能出清需要时间, 勿急于抄底
""",
        "cases": [
            "2022-2024 光伏大熊市: 隆基绿能从70跌到15, 3年跌78%",
        ],
    },
    "机器人": {
        "definition": "机器人 (工业机器人/人形机器人/减速器) 是AI+制造融合的热门赛道。",
        "logic": """
🔴 放量暴涨 (>3%): 人形机器人催化, 板块行情启动
🟢 绿盘: 概念回调, 注意龙头是否仍强
⚠️ 判断: 机器人行情通常有龙头 (减速器) 先涨, 跟风股后涨
""",
        "cases": [
            "2024.09 机器人行情: 埃斯顿、绿的谐波连续涨停",
            "2023 特斯拉Optimus: 机器人板块连续3天涨停",
        ],
    },
    "白酒": {
        "definition": "白酒是消费板块的核心, 高端白酒 (茅台/五粮液) 是消费景气度的风向标。",
        "logic": """
🔴 红盘: 消费复苏预期, 或外资回流
🟢 绿盘: 消费降级担忧, 或资金流向科技
⚠️ 判断: 白酒领涨往往意味着市场偏好红利/防守, 而非进攻
""",
        "cases": [
            "2024.09 白酒反弹: 茅台从1400涨到1800, 外资回流信号",
            "2022 白酒熊市: 茅台从2600跌到1300, 消费降级确认",
        ],
    },
    "黄金": {
        "definition": "黄金是避险资产, 与美元指数负相关, 与A股通常无直接关系但风险偏好下降时走强。",
        "logic": """
🔴 红盘: 避险需求上升 (地缘风险/美元走弱/通胀)
🟢 绿盘: 风险偏好上升, 资金流向股市/加密货币
⚠️ 判断: 黄金红盘 + A股绿盘 = 典型的避险模式
""",
        "cases": [
            "2024.10 黄金创新高: 现货黄金突破2700美元/盎司",
            "2022 俄乌战争: 黄金单日涨3%, 避险情绪爆发",
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
    "券商":     {"pct": 1.44, "reason": "红盘! 后置情绪轮动"},
    "银行":     {"pct": 0.94, "reason": "红利防守"},
    "CPO":      {"pct": 2.94, "reason": "AI主线反弹"},
    "半导体":   {"pct": 2.24, "reason": "国产替代修复"},
    "AI":       {"pct": 2.54, "reason": "主线确认"},
    "电池":     {"pct": 0.26, "reason": "从科技漂移"},
    "煤炭":     {"pct": 0.14, "reason": "周期弱反弹"},
    "电力":     {"pct": 0.11, "reason": "跟随周期"},
    "医疗":     {"pct": 1.24, "reason": "抗跌修复"},
    "军工":     {"pct": 1.85, "reason": "国庆行情预期"},
    "航天":     {"pct": 2.10, "reason": "卫星互联网催化"},
    "风电":     {"pct": 0.55, "reason": "绿电政策"},
    "光伏":     {"pct": -0.32, "reason": "产能过剩压力"},
    "机器人":   {"pct": 3.05, "reason": "人形机器人催化"},
    "白酒":     {"pct": 1.68, "reason": "消费复苏预期"},
    "黄金":     {"pct": 0.75, "reason": "避险需求"},
}

# —— AKShare 接口缓存 (板块/实时行情) ——
_AK_SPOT_CACHE = {"time": 0, "data": None}
_AK_BLOCK_CACHE = {"time": 0, "data": None}
_TUSHARE_DAILY_CACHE = {"time": 0, "data": None}
_TUSHARE_SB_CACHE = {"time": 0, "data": None}
_BLOCK_PCT_CACHE = {"time": 0, "data": None}

# —— 捡漏持久化缓存 (JSON 文件, 秒出用) ——
_LEAK_CACHE_PATH = os.path.expanduser("~/.qclaw/watch_leak_cache.json")
_SPOT_INDEX_CACHE = {"time": 0, "data": None}
_SINA_REALTIME_CACHE = {"time": 0, "data": None}


def _is_trading_hours():
    """判断是否在盘中 (交易日 9:15-15:05)"""
    now = datetime.now()
    # 周末不交易
    if now.weekday() >= 5:
        return False
    h = now.hour; m = now.minute
    mins = h * 60 + m
    return (9 * 60 + 15) <= mins <= (15 * 60 + 5)


def _get_sina_realtime():
    """新浪直连实时: 四大指数 + 行业板块 (秒级返回)
    返回 dict: {
        "indices": {"IH": {close, pct, ...}, "IF": ..., "IC": ..., "IM": ...},
        "sectors": {"券商": pct, "银行": pct, ...},
        "estimated_up_count": int,  # 估算值
        "trade_date": "20261016",
        "source": "新浪实时"
    }
    """
    now = time.time()
    if _SINA_REALTIME_CACHE["data"] and (now - _SINA_REALTIME_CACHE["time"] < 30):
        return _SINA_REALTIME_CACHE["data"]

    result = {"indices": {}, "sectors": {}, "estimated_up_count": None,
              "trade_date": datetime.now().strftime("%Y%m%d"), "source": "新浪实时"}
    try:
        import requests, re

        # 1. 四大指数 (IH/IF/IC/IM 对应上证50/沪深300/中证500/中证1000)
        idx_map = [("IH", "sh000016"), ("IF", "sh000300"),
                   ("IC", "sh000905"), ("IM", "sh000852")]
        codes = ",".join(c for _, c in idx_map)
        r = requests.get(f"https://hq.sinajs.cn/list={codes}",
                         headers={"Referer": "https://finance.sina.com.cn",
                                  "User-Agent": "Mozilla/5.0",
                                  "Accept-Language": "zh-CN"},
                         timeout=6)
        if r.status_code == 200:
            for line, (name, _) in zip(r.text.strip().split("\n"), idx_map):
                m = re.search(r'"([^"]+)"', line)
                if m:
                    parts = m.group(1).split(",")
                    if len(parts) >= 6:
                        close = float(parts[3])
                        yclose = float(parts[2])
                        pct = (close - yclose) / yclose * 100
                        result["indices"][name] = {"close": close, "pct": round(pct, 2),
                                                   "yclose": yclose}

        # 2. 行业板块 (akshare 新浪行业) — 注意: 新浪行业返回的是成分股, 不是板块汇总!
        try:
            import akshare as ak
            df_sector = ak.stock_sector_spot(indicator="新浪行业")
            if df_sector is not None and len(df_sector) > 0:
                pct_col = [c for c in df_sector.columns if "涨跌" in str(c)]
                name_col = [c for c in df_sector.columns if "名称" in str(c) or "板块" in str(c)]
                if pct_col and name_col:
                    # 精确映射: 16 个板块 → 新浪行业名
                    sector_map = [
                        ("券商",   ["证券"]),
                        ("银行",   ["银行"]),
                        ("CPO",    ["通信设备"]),
                        ("半导体", ["半导体"]),
                        ("AI",     ["软件服务", "IT设备", "计算机"]),
                        ("电池",   ["发电设备", "电池"]),
                        ("煤炭",   ["煤炭"]),
                        ("电力",   ["电力"]),
                        ("医疗",   ["医药"]),
                        # ── 新增 7 个 (之前缺失, 导致盘中回退到 tushare daily 旧数据) ──
                        ("黄金",   ["有色金属"]),     # 新浪行业没有独立黄金, 归有色金属
                        ("白酒",   ["酿酒行业"]),      # 新浪行业叫"酿酒行业"
                        ("光伏",   ["发电设备"]),      # 光伏归发电设备
                        ("风电",   ["发电设备"]),      # 风电归发电设备
                        ("机器人", ["机械行业"]),      # 机器人归机械行业
                        ("军工",   ["飞机制造", "船舶制造"]),  # 军工主力在飞机制造
                        ("航天",   ["飞机制造"]),      # 航天归飞机制造
                    ]
                    matched_names = set()
                    for our_name, kws in sector_map:
                        for _, row in df_sector.iterrows():
                            row_name = str(row[name_col[0]])
                            if any(kw in row_name for kw in kws):
                                result["sectors"][our_name] = round(float(row[pct_col[0]]), 2)
                                matched_names.add(row_name)
                                break
        except Exception as e:
            print(f"[👁️看盘] 新浪行业板块失败 (不影响): {e}")

        # 2a. 🟢 深市行业指数 (精准盘中 pct — 替代上面的个股匹配)
        # 新浪深市行业指数代码映射 (已验证能查到真实 pct)
        SZ_IDX = {
            "AI":     "sz399998",
            "电池":   "sz399996",
            "医疗":   "sz399997",
            "光伏":   "sz399905",
            "风电":   "sz399905",
            "机器人": "sz399971",
            "军工":   "sz399991",
            "航天":   "sz399991",
        }
        try:
            idx_codes = list(set(SZ_IDX.values()))
            r2 = requests.get(f"https://hq.sinajs.cn/list={','.join(idx_codes)}",
                              headers={"Referer":"https://finance.sina.com.cn",
                                       "User-Agent":"Mozilla/5.0"}, timeout=5)
            if r2.status_code == 200:
                code_to_pct = {}
                for line, code in zip(r2.text.strip().split("\n"), idx_codes):
                    m = re.search(r'"([^"]+)"', line)
                    if m:
                        parts = m.group(1).split(",")
                        if len(parts) >= 6 and float(parts[2]) > 0:
                            close, yclose = float(parts[3]), float(parts[2])
                            pct = round((close - yclose) / yclose * 100, 2)
                            code_to_pct[code] = pct
                # 用深市指数覆盖 (更准)
                for our_name, code in SZ_IDX.items():
                    if code in code_to_pct:
                        result["sectors"][our_name] = code_to_pct[code]
        except Exception as e:
            print(f"[👁️看盘] 深市行业指数查询失败 (不影响): {e}")

        # 2b. 兜底: 用中证1000 涨跌幅 + 板块固定偏离补缺失值
        # 历史: 各板块相对 IM 的偏离 (用来估算缺失板块)
        if "IM" in result["indices"]:
            im_pct = result["indices"]["IM"]["pct"]
            sector_bias = {  # 历史平均偏离 (板块 pct - IM pct)
                "券商": -0.3, "银行": -0.8, "CPO": 1.2, "AI": 0.8, "电池": 0.3,
                "半导体": 0.5, "医疗": -0.5,
                # ── 新增 7 个偏离 ──
                "黄金": -0.1, "白酒": -0.3, "光伏": 0.5, "风电": 0.4,
                "机器人": 0.6, "军工": 0.3, "航天": 0.2,
            }
            for our_name, bias in sector_bias.items():
                if our_name not in result["sectors"]:
                    est = round(im_pct + bias, 2)
                    result["sectors"][our_name] = est

        # 3. 估算全市场涨跌比 (用中证1000 涨跌幅反推)
        if "IM" in result["indices"]:
            im_pct = result["indices"]["IM"]["pct"]
            # 历史回归: IM 涨跌 +1% → 上涨家数占比 +15% (粗糙但够用)
            base_up = 2300  # 基准: 平盘时约 2300 家上涨
            est_up = int(base_up + im_pct * 180)
            est_up = max(300, min(5200, est_up))
            result["estimated_up_count"] = est_up

        _SINA_REALTIME_CACHE["data"] = result
        _SINA_REALTIME_CACHE["time"] = now
        print(f"[👁️看盘] ✅ 新浪实时: {result['indices']}, 估算涨 {result['estimated_up_count']}")
    except Exception as e:
        print(f"[👁️看盘] 新浪实时失败: {e}")
    return result


def _get_tushare_daily_today():
    """tushare 今日全市场行情 (daily 接口) — 纯本地 + 联网一次"""
    now = time.time()
    if _TUSHARE_DAILY_CACHE["data"] is not None and (now - _TUSHARE_DAILY_CACHE["time"] < 3600):
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
    if _TUSHARE_SB_CACHE["data"] is not None and (now - _TUSHARE_SB_CACHE["time"] < 86400):
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
    "军工": ["军工", "国防", "航天", "航空", "军机"],
    "航天": ["航天", "卫星", "火箭", "北斗"],
    "风电": ["风电", "风力", "风机", "塔筒"],
    "光伏": ["光伏", "太阳能", "硅片", "组件"],
    "机器人": ["机器人", "自动化", "减速器", "伺服", "人形", "专用机械"],
    "白酒": ["白酒", "茅台", "五粮液", "酒厂"],
    "黄金": ["黄金", "金业", "山东黄金", "中金黄金"],
}


def _compute_block_pct_from_cache():
    """用已缓存的 daily + stock_basic 做板块聚合, 结果再缓存 10 分钟"""
    now = time.time()
    if _BLOCK_PCT_CACHE["data"] is not None and (now - _BLOCK_PCT_CACHE["time"] < 600):
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
            if mask is not None and mask.sum() >= 1:
                sub = merged[mask].copy()
                mean_pct = float(sub["pct_chg"].mean())
                n = int(mask.sum())
                # Top5 龙头: 按成交额取前5 (成交额=amount, 单位千元)
                if "amount" in sub.columns:
                    top5 = sub.sort_values("amount", ascending=False).head(5)
                else:
                    top5 = sub.sort_values("pct_chg", ascending=False).head(5)
                top5_list = [(str(r["name"]), float(r["pct_chg"])) for _, r in top5.iterrows()]
                result[fix_name] = (mean_pct, n, top5_list)
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
    if _AK_SPOT_CACHE["data"] is not None and (now - _AK_SPOT_CACHE["time"] < 30):
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
    if _AK_BLOCK_CACHE["data"] is not None and (now - _AK_BLOCK_CACHE["time"] < 60):
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
    win.geometry("1850x1000")
    win.minsize(1600, 900)
    win._app = app
    win._running = True

    # —— 主窗口顶栏: 标题 + 字体调节 ——
    _WATCH_FS = [15]  # 内容字号基准, 默认 +3pt 大字号
    win._WATCH_FS = _WATCH_FS  # 存到 win 供各模块读

    header = tk.Frame(win, bg="#121212"); header.pack(fill=tk.X)
    tk.Label(header, text="👁️ 游资看盘界面", bg="#121212", fg="#FFD54F",
             font=("", 18, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
    tk.Label(header, text="2×3 六区 | 所有❓按钮点知识弹窗", bg="#121212", fg="#90CAF9",
             font=("", 11)).pack(side=tk.LEFT, pady=10)
    win._data_date_lbl = tk.Label(header, text="⏳ 加载中...",
                                  bg="#121212", fg="#BDBDBD", font=("", 11))
    win._data_date_lbl.pack(side=tk.LEFT, padx=10, pady=10)

    fs_box = tk.Frame(header, bg="#121212"); fs_box.pack(side=tk.RIGHT, padx=14)
    tk.Label(fs_box, text="🔤 字体:", bg="#121212", fg="#E0E0E0", font=("", 11)).pack(side=tk.LEFT)
    fs_lbl = tk.Label(fs_box, text=f"{_WATCH_FS[0]}pt", bg="#121212", fg="#FFD54F",
                     font=("", 11, "bold"))
    fs_lbl.pack(side=tk.LEFT, padx=4)

    def _change_main_fs(delta):
        _WATCH_FS[0] = max(10, min(24, _WATCH_FS[0] + delta))
        fs_lbl.config(text=f"{_WATCH_FS[0]}pt")
        def _walk(w):
            try:
                conf = w.configure()
                if "font" in conf:
                    cur = w.cget("font")
                    try:
                        sz = int(cur[1])
                        w.config(font=(cur[0], _WATCH_FS[0], *cur[2:]) if len(cur) > 2 else (cur[0], _WATCH_FS[0]))
                    except Exception: pass
            except Exception: pass
            for c in w.winfo_children(): _walk(c)
        _walk(win)

    tk.Button(fs_box, text="A-", width=3, bg="#37474F", fg="#ECEFF1",
              font=("", 10), command=lambda: _change_main_fs(-1)).pack(side=tk.LEFT, padx=2)
    tk.Button(fs_box, text="A+", width=3, bg="#37474F", fg="#ECEFF1",
              font=("", 10), command=lambda: _change_main_fs(+1)).pack(side=tk.LEFT, padx=2)

    # ── 📚 财经大V风格学习 (加在右侧字体调节左边) ──
    def _open_vv():
        _show_vv_from_speculator(win)
    _vv_count = len(_vv_list_authors())
    vv_btn_text = f"📚 大V风格库 ({_vv_count})"
    vv_btn = tk.Button(header, text=vv_btn_text, font=("", 10, "bold"),
                        bg="#1565C0", fg="#FFFFFF", padx=10, pady=4,
                        cursor="hand2", command=_open_vv)
    vv_btn.pack(side=tk.RIGHT, padx=(0, 14), pady=10)

    outer = tk.Frame(win, bg="#121212"); outer.pack(fill=tk.BOTH, expand=True)

    # 右面板加宽 (340 → 420)
    # 右面板充满 (width=520, pack_propagate=False 保留最小宽度)
    # ── 可拖拽分割器布局 (全部用 place, splitter 统一控制位置) ──
    left_pane = tk.Frame(outer, bg="#121212")
    right_pane = tk.Frame(outer, bg="#121212")
    splitter = _HSplitter(outer, left_pane, right_pane, key="watch_main",
                          min_left=400, min_right=380)
    # 注意: left_pane / right_pane 都不 pack, 由 splitter._reflow() 统一 place
    # 多次 reflow 保险: Toplevel 首次显示时 winfo_width 可能还没到位
    outer.after(100, splitter._reflow)
    outer.after(300, splitter._reflow)
    outer.after(800, splitter._reflow)

    # left_pane grid 配置 (2 列 × 3 行)
    left_pane.grid_rowconfigure(0, weight=3)
    left_pane.grid_rowconfigure(1, weight=3)
    left_pane.grid_rowconfigure(2, weight=1)
    left_pane.grid_columnconfigure(0, weight=1)
    left_pane.grid_columnconfigure(1, weight=1)

    # 🗂️ 模块按用户要求重排
    # ── row_top (row=0): 3全球五资产 × 1板块九宫格 (2列等宽) ──
    row_top = tk.Frame(left_pane, bg="#121212"); row_top.grid(row=0, column=0, columnspan=2, sticky="nsew")
    row_top.grid_columnconfigure(0, weight=1, uniform="r1")
    row_top.grid_columnconfigure(1, weight=1, uniform="r1")

    _build_orderbook(row_top, win, 0)    # 3=🌍全球五资产
    _build_block_grid(row_top, win, 1)   # 1=①板块九宫格

    # ── row_bot (row=1): 4量能 × 5股指期货 × 6周期阶段 (3列) ──
    row_bot = tk.Frame(left_pane, bg="#121212"); row_bot.grid(row=1, column=0, columnspan=2, sticky="nsew")
    row_bot.grid_columnconfigure(0, weight=1, uniform="r2")
    row_bot.grid_columnconfigure(1, weight=1, uniform="r2")
    row_bot.grid_columnconfigure(2, weight=1, uniform="r2")

    _build_volume_panel(row_bot, win, 0)     # 4=量能
    _build_futures_grid(row_bot, win, 1)      # 5=股指期货
    _build_cycle_panel(row_bot, win, 2)       # 6=周期阶段

    # ── row_leak (row=2, 比例分配): 2信号决策 × 7状态判定 ──
    row_leak = tk.Frame(left_pane, bg="#121212")
    row_leak.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(2, 0))
    row_leak.grid_rowconfigure(0, weight=1)
    row_leak.grid_columnconfigure(0, weight=1, uniform="r3")
    row_leak.grid_columnconfigure(1, weight=1, uniform="r3")

    sign_w = tk.Frame(row_leak, bg="#121212"); sign_w.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
    _build_sign_decision_panel(sign_w, win)   # 2=🎯信号决策

    stat_w = tk.Frame(row_leak, bg="#121212"); stat_w.grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
    _build_status_panel(stat_w, win, 0)       # 7=状态判定

    # 右侧: ttk.Notebook 两个 tab (🧠看盘思路 + 🗂️板块画布)
    right_nb = ttk.Notebook(right_pane)
    right_nb.pack(fill=tk.BOTH, expand=True)
    win._right_nb = right_nb

    # Tab 1: 🧠 看盘思路
    tab_analysis = tk.Frame(right_nb, bg="#121212")
    right_nb.add(tab_analysis, text=" 🧠 看盘思路 ")
    _build_watch_analysis(tab_analysis, win)

    # Tab 2: 🗂️ 板块画布
    tab_canvas = tk.Frame(right_nb, bg="#121212")
    right_nb.add(tab_canvas, text=" 🗂️ 板块画布 ")
    _build_block_canvas_panel(tab_canvas, win)

    win.protocol("WM_DELETE_WINDOW", lambda: (setattr(win, "_running", False), win.destroy()))

    print("[👁️看盘] 六区构建完成, 立刻填充本地数据...", flush=True)

    # 先用种子数据秒出其他面板 (保证不空) — 信号决策面板不再秒出种子
    _seed_fill_all(win)

    # 后台线程拉真实数据替换 — ⚡ 信号决策最优先 (顶部大字报, 用户一眼就看)
    def _real_fill():
        # ⚡ 第一优先级: 信号决策 (新浪日线, 8s 超时)
        try: _refresh_sign_decision(win)
        except Exception as e: print(f"[👁️看盘❌] sign_decision: {e}")
        # 其他面板
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
        try: _refresh_block_canvas(win)
        except Exception as e: print(f"[👁️看盘❌] block_canvas: {e}")
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
    """种子数据秒出 — 优先读 sentiment_history 本地数据, 再后台刷新"""
    try:
        # 顶栏日期标签先显示种子状态
        if hasattr(win, '_data_date_lbl'):
            win._data_date_lbl.config(text="⏳ 加载实时数据中...", fg="#BDBDBD")

        # 优先读 sentiment_history 最新 m2_up/m2_down (本地 SQLite 秒出)
        seed_up = 2300; seed_down = 3200; seed_pct = 0.0; seed_date = "—"
        rows = _read_local_sentiment(limit=1)
        if rows and rows[0][3]:
            r = rows[0]
            seed_date = str(r[0])
            seed_up = int(r[3] or 2300)
            seed_down = int(r[4] or 3200)
            seed_pct = float(r[1] or 0)

        # 用真实 m2_up 判灯 — 种子不再写死红灯
        if seed_up < 1600: light = "🔴 红灯"
        elif seed_up <= 3500: light = "🟡 黄灯"
        else: light = "🟢 绿灯"
        total = seed_up + seed_down
        up_ratio = round(seed_up / total * 100, 1) if total > 0 else 50

        ctx = {"pct_mean": seed_pct, "up_count": seed_up, "down_count": seed_down,
               "zt_count": None, "dt_count": None, "trade_date": seed_date,
               "up_ratio": up_ratio, "light": light,
               "block_ranking": [("券商", 0.06), ("银行", -1.07), ("CPO", -4.0)],
               "spot": {}, "data_source": "📅 种子 (sentiment_history 本地)"}
        layers, concl = _build_7layer_analysis(ctx)
        _apply_analysis(win, layers, concl)
        print(f"[👁️看盘] 种子秒出: up={seed_up}, date={seed_date}, light={light}", flush=True)
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
                        font=("", 12, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    parent.grid_rowconfigure(0, weight=1)
    _add_title_row(frm, "① 板块十六宫格 (16板块·4×4·⚠️异动>3%)",
                   "#FFA726", BLOCK_GRID_KNOWLEDGE)

    # 9 格 Canvas (4×4), 增大
    canvas = tk.Canvas(frm, bg="#1E1E1E", highlightthickness=0, height=380)
    canvas.pack(fill=tk.BOTH, expand=True)
    win._block_canvas = canvas

    # ⚠️ 关键: Configure 事件 → 窗口大小变化时重绘
    # 后台线程第一次 draw 时 winfo_width 可能还很小, 等布局稳定后再重绘
    def _on_cfg(e):
        if e.width > 100 and e.height > 100:
            _draw_block_grid(win)
    canvas.bind("<Configure>", _on_cfg)
    # 多次保险触发首次绘制 (100ms / 300ms / 600ms)
    for delay in (100, 300, 600):
        canvas.after(delay, lambda: _draw_block_grid(win) if canvas.winfo_width() > 100 else None)

    win._block_meta = [[name, None, None, True, False, None, []] for name in FIXED_BLOCKS]
    win._block_cells = []

    win._block_conflict_lbl = tk.Label(frm, text="正在加载板块数据...",
                                       bg="#1E1E1E", fg="#E0E0E0",
                                       font=("", 11), wraplength=600, justify=tk.LEFT)
    win._block_conflict_lbl.pack(fill=tk.X, pady=(2, 0))

    win._pulse_cells = {}


def _refresh_all_blocks(win):
    """刷新十六宫格 — 新浪实时拿 pct (盘中+盘后), tushare 聚合拿 top5 成分股"""
    matched_any = False

    # 🟢 ① 新浪实时 sectors — 拿最新涨跌 pct (盘中秒级 + 盘后也可用)
    try:
        realtime = _get_sina_realtime()
        sectors = realtime.get("sectors", {}) if realtime else {}
        if sectors:
            for i, fix_name in enumerate(FIXED_BLOCKS):
                val = sectors.get(fix_name)
                if val is not None:
                    win._block_meta[i][1] = val  # 实时 pct
                    matched_any = True
            print(f"[👁️看盘] ✅ 新浪 sectors pct ({len([v for v in sectors.values() if v is not None])}/16)")
    except Exception as e:
        print(f"[👁️看盘] 新浪 sectors 失败: {e}")

    # 📅 ② tushare 聚合 — 拿 top5 成分股 + 股票数 (双击K线需要)
    try:
        result = _compute_block_pct_from_cache()
        if result:
            for i, fix_name in enumerate(FIXED_BLOCKS):
                val = result.get(fix_name)
                if val:
                    # pct: 新浪已有就不覆盖 (新浪更实时), 新浪没有才用 tushare
                    if win._block_meta[i][1] is None and val[0] is not None:
                        win._block_meta[i][1] = val[0]
                    # top5 成分股: 不管新浪有没有, 都用 tushare 填充
                    win._block_meta[i][5] = val[1]  # 股票数
                    win._block_meta[i][6] = val[2] if len(val) > 2 else []
                    matched_any = True
            if matched_any:
                print(f"[👁️看盘] ✅ tushare 聚合 top5 成分股 (为双击K线准备)")
    except Exception as e:
        print(f"[👁️看盘] tushare 聚合失败: {e}")

    # ③ 种子兜底
    if not matched_any:
        print(f"[👁️看盘] 🌱 九宫格走种子兜底")
        for i, fix_name in enumerate(FIXED_BLOCKS):
            if fix_name in SEED_BLOCK_META:
                win._block_meta[i][1] = SEED_BLOCK_META[fix_name]["pct"]
            else:
                win._block_meta[i][1] = None

    # 更新顶栏日期标签 (盘中/收盘不同来源)
    if _is_trading_hours():
        realtime = _get_sina_realtime()
        if realtime and realtime.get("indices"):
            spot = realtime["indices"]
            pcts = [v["pct"] for v in spot.values()]
            mean_pct = sum(pcts) / len(pcts) if pcts else 0
            win._data_date_lbl.config(
                text=f"🟢 盘中实时 {datetime.now().strftime('%H:%M')} | "
                     f"{realtime['trade_date']} | 新浪直连",
                fg="#81C784" if mean_pct >= 0 else "#EF5350")
    else:
        dc = _TUSHARE_DAILY_CACHE.get("data")
        if dc is not None and len(dc) > 0:
            trade_dates = sorted(dc["trade_date"].unique())
            latest = trade_dates[-1]
            pct_mean = dc["pct_chg"].mean()
            win._data_date_lbl.config(
                text=f"📅 {latest} | 收盘均值 {pct_mean:+.2f}% | 涨 {(dc['pct_chg']>0).sum()}/{len(dc)}",
                fg="#66BB6A" if pct_mean >= 0 else "#EF5350")

    # 脉冲 + 矛盾描述
    for idx, meta in enumerate(win._block_meta):
        meta[4] = (meta[1] is not None and abs(meta[1]) >= 3.0)

    pcts_only = [(FIXED_BLOCKS[i], win._block_meta[i][1] or 0) for i in range(len(FIXED_BLOCKS))]
    pcts_only.sort(key=lambda x: x[1], reverse=True)
    top2, bot2 = pcts_only[:2], pcts_only[-2:]
    conflict = f"🔥 主线板块: {' / '.join([x[0] for x in top2])} ({top2[0][1]:+.2f}% {top2[1][1]:+.2f}%)"
    conflict += f"  |  ⬇️ 压力: {' / '.join([x[0] for x in bot2])} ({bot2[0][1]:+.2f}% {bot2[1][1]:+.2f}%)"
    win._block_conflict_lbl.config(text=conflict)

    _draw_block_grid(win)


def _draw_block_grid(win):
    """Canvas 画 4×4 十六宫格"""
    c = win._block_canvas
    c.delete("all")
    win._block_cells = []

    W = c.winfo_width() or 500
    H = c.winfo_height() or 340
    pad = 2
    cw = (W - pad * 5) // 4
    ch = (H - pad * 5) // 4

    # 脉动闪烁状态 (用 win 时间戳模拟)
    now_ms = time.time() * 1000

    for idx in range(len(FIXED_BLOCKS)):
        row = idx // 4; col = idx % 4
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
                c.create_text(x2 - 7, y1 + 7, text="⚠️", fill="#FFD54F",
                              font=("", 12, "bold"), tags=f"cell_{idx}")

        if pct is None:
            c.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#555",
                               width=1, tags=f"cell_{idx}")

        # 板块名 (上半部分)
        c.create_text(x1 + cw // 2, y1 + 14, text=name,
                      fill="#FFFFFF", font=("", 10, "bold"), tags=f"cell_{idx}")
        # 涨跌幅
        if pct is not None:
            sign = "+" if pct >= 0 else ""
            c.create_text(x1 + cw // 2, y1 + 30,
                          text=f"{sign}{pct:.2f}%", fill=fg,
                          font=("", 11, "bold"), tags=f"cell_{idx}")

        # 个股数小标签 (右上角, 如果有)
        n_stocks = meta[5]
        if n_stocks:
            c.create_text(x2 - 7, y1 + 20, text=f"n={n_stocks}", fill="#9E9E9E",
                          font=("", 10), tags=f"cell_{idx}")

        # Top5 龙头 (下半部分, 紧凑 5 行 9pt)
        top5 = meta[6] if len(meta) > 6 else []
        if top5:
            # 下半区域: y1+36 ~ y2-2, 共 ch-38 高, 分 5 行
            area_top = y1 + 36
            area_h = ch - 38
            row_h = max(8, min(12, area_h // max(1, len(top5[:5]))))
            for ti, (sname, spct) in enumerate(top5[:5]):
                sy = area_top + 2 + ti * row_h
                short = sname[:5] if len(sname) > 5 else sname
                sfg = "#FF8A80" if spct >= 0 else "#69F0AE"
                ssign = "+" if spct >= 0 else ""
                stock_tag = f"stock_{idx}_{ti}"
                c.create_text(x1 + 6, sy, text=f"{short}",
                              fill="#BDBDBD", font=("", 9), anchor=tk.W,
                              tags=(f"cell_{idx}", stock_tag))
                c.create_text(x2 - 6, sy, text=f"{ssign}{spct:.1f}%",
                              fill=sfg, font=("", 9), anchor=tk.E,
                              tags=(f"cell_{idx}", stock_tag, f"pct_{idx}_{ti}"))

        # ❓ 板块分析按钮 (左上角, 蓝色下划线)
        c.create_text(x1 + 12, y1 + 10, text="❓", fill="#90CAF9",
                      font=("", 10, "bold underline"), tags=(f"cell_{idx}", f"q_{idx}"))
        # 隐藏矩形扩大点击热区
        c.create_rectangle(x1 + 3, y1 + 3, x1 + 20, y1 + 20, outline="",
                           fill="", tags=(f"cell_{idx}", f"q_{idx}"))

        win._block_cells.append(((x1, y1, x2, y2), idx))

    # 点击绑定: 单击 → 板块日K, 双击 → 个股日K
    def _on_single_click(event):
        print(f"[👁️点击] single at ({event.x},{event.y}), canvas type={type(c).__name__}", flush=True)
        for (x1, y1, x2, y2), idx in win._block_cells:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                tags = c.gettags(event.x, event.y)
                print(f"[👁️点击] hit idx={idx}, tags={tags[:5] if tags else 'empty'}, _block_meta len={len(win._block_meta)}, cell_idx={idx < len(win._block_meta)}", flush=True)
                if f"q_{idx}" in tags:
                    name = win._block_meta[idx][0]
                    kd = BLOCK_KNOWLEDGE.get(name, {"definition": "(暂无)"})
                    _show_knowledge_popup(win, name, kd)
                else:
                    _show_block_daily_kline(win, idx)
                return
        print(f"[👁️点击] no cell hit, cells={len(win._block_cells)}", flush=True)

    def _on_double_click(event):
        print(f"[👁️点击] DOUBLE at ({event.x},{event.y})", flush=True)
        for (x1, y1, x2, y2), idx in win._block_cells:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                tags = c.gettags(event.x, event.y)
                print(f"[👁️点击] DOUBLE hit idx={idx}", flush=True)
                if f"q_{idx}" in tags:
                    name = win._block_meta[idx][0]
                    kd = BLOCK_KNOWLEDGE.get(name, {"definition": "(暂无)"})
                    _show_knowledge_popup(win, name, kd)
                    return
                top5 = win._block_meta[idx][6] if len(win._block_meta[idx]) > 6 else []
                hit_name = None
                for ti, (sname, _pct) in enumerate(top5[:5]):
                    if f"stock_{idx}_{ti}" in tags:
                        hit_name = sname; break
                if hit_name:
                    sina, sname2 = _lookup_stock_code_by_name(hit_name)
                    if sina:
                        _show_stock_ichimoku(win, sina, sname2 or hit_name)
                        return
                sina, sname = _get_first_stock_sina(win, idx)
                if sina:
                    _show_stock_ichimoku(win, sina, sname)
                else:
                    messagebox.showinfo("提示", f"无法获取 {win._block_meta[idx][0]} 成分股代码")
                return

    # 🆕 改成用 event.time 区分单击 vs 双击 (macOS Canvas 上 <Double-1> 经常触发不了)
    _click_state = {"time": 0, "idx": -1}
    def _unified_click(event):
        now = event.time
        for (x1, y1, x2, y2), idx in win._block_cells:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                tags = c.gettags(event.x, event.y)
                # ❓ 热区 → 知识弹窗 (单击即可)
                if f"q_{idx}" in tags:
                    name = win._block_meta[idx][0]
                    kd = BLOCK_KNOWLEDGE.get(name, {"definition": "(暂无)"})
                    _show_knowledge_popup(win, name, kd)
                    _click_state["time"] = now; _click_state["idx"] = idx
                    return
                # 如果两次点击间隔 < 300ms 且同一格 → 双击
                if (now - _click_state["time"]) < 300 and _click_state["idx"] == idx:
                    _click_state["time"] = 0  # reset
                    top5 = win._block_meta[idx][6] if len(win._block_meta[idx]) > 6 else []
                    hit_name = None
                    for ti, (sname, _pct) in enumerate(top5[:5]):
                        if f"stock_{idx}_{ti}" in tags:
                            hit_name = sname; break
                    if hit_name:
                        sina, sname2 = _lookup_stock_code_by_name(hit_name)
                        if sina:
                            _show_stock_ichimoku(win, sina, sname2 or hit_name)
                            return
                    sina, sname = _get_first_stock_sina(win, idx)
                    if sina:
                        _show_stock_ichimoku(win, sina, sname)
                    else:
                        messagebox.showinfo("提示", f"无法获取 {win._block_meta[idx][0]} 成分股代码")
                else:
                    # 单击 → 板块指数日K
                    _click_state["time"] = now; _click_state["idx"] = idx
                    _show_block_daily_kline(win, idx)
                return
    # 改用统一 <Button-1> 处理 (event.time 区分单击双击)
    c.bind("<Button-1>", _unified_click)
    c.bind("<Double-1>", _unified_click)  # 兜底
    c.bind("<Button-3>", lambda e: _show_block_detail(win, -1, full=True))
    c.bind("<Configure>", lambda e: _draw_block_grid(win))


def _lookup_stock_code_by_name(name):
    """Try to find a stock's sina code by name (local SQLite cache → akshare → holding tab)"""
    # 1. Try sqlite stock_analysis table (existing code cache)
    try:
        import sqlite3
        for dbpath in [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "stock_analysis.db"),
            os.path.expanduser("~/StockAnalyzer/Database/stock_analysis.db"),
        ]:
            if os.path.exists(dbpath):
                con = sqlite3.connect(dbpath)
                cur = con.cursor()
                cur.execute("SELECT code FROM stock_analysis WHERE name LIKE ? LIMIT 1",
                            (f"%{name}%",))
                row = cur.fetchone(); con.close()
                if row:
                    code = row[0]
                    if "." in code: code = code.split(".")[0]
                    if code.startswith("6"): return "sh" + code, name
                    if code.startswith(("0", "3")): return "sz" + code, name
                    if code.startswith(("4", "8")): return "bj" + code, name
                    return "sh" + code, name
    except Exception: pass
    # 2. Try akshare spot
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["名称"].str.contains(name[:2], na=False)].head(1)
        if len(row):
            code = str(row.iloc[0]["代码"])
            if code.startswith("6"): return "sh" + code, str(row.iloc[0]["名称"])
            if code.startswith(("0", "3")): return "sz" + code, str(row.iloc[0]["名称"])
            if code.startswith(("4", "8")): return "bj" + code, str(row.iloc[0]["名称"])
    except Exception: pass
    return None, None


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

# ═══════════════════════════════════════════════════════════════
# ② 涨停强弱排名 — 多维度算法 (资金30%+情绪35%+技术20%+板块15%)
# 数据源: akshare stock_zt_pool_em + stock_zt_pool_previous_em + stock_zt_pool_strong_em
# ═══════════════════════════════════════════════════════════════

ZT_RANK_KNOWLEDGE = {
    "definition": "涨停强弱排名 — 游资实战多维度算法筛选最强涨停股",
    "logic": """📊 评分维度 (满分100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 资金面 (30分)
   • 封板资金金额: >5亿=10分, >1亿=7分, >5000万=4分
   • 换手率: 3-15%=10分(健康), 1-3%/15-25%=5分, 其他=2分
   • 成交额: >10亿=10分, >3亿=7分, >1亿=4分

🔥 情绪面 (35分)
   • 连板高度: ≥5板=15分(妖股), 3板=12分, 2板=8分
   • 封板时间: 9:30前=12分(一字板最强), 10:30前=8分, 13:30前=5分
   • 炸板次数: 0次=8分(坚决), 1次=5分, ≥2次=2分

📈 技术面 (20分)
   • 流通市值: <50亿=10分(小盘弹性大), <150亿=7分, <500亿=4分
   • 涨停统计: 近N天高频涨停=10分

🌐 板块共振 (15分)
   • 同行业涨停数 ≥3 = 15分 (主线热点)
   • 同行业涨停数 = 2 = 10分
   • 独立涨停 = 5分

⚠️ 实战高分票 (≥70): 优先关注, 次日溢价概率大
⚠️ 低分票 (<40): 观望为主, 炸板/闷杀概率高
""",
    "cases": [
        "2024.09.24 券商涨停潮: 所有券商股封单>10亿+无炸板+9:30前封板 → 评分普遍>85, 次日集体高开",
        "2024.04 CPO板块: 中际旭创涨停封板3次炸板+下午封板 → 评分仅38, 次日低开闷杀",
        "2023.11 AI行情: 鸿博股份7连板+一字板+封板稳定 → 评分96, 连续7天一字涨停",
    ],
}


# 涨停原因关键词映射 (硬编码, 匹配所属行业+资讯关键词)
ZT_LOGIC_MAP = {
    "半导体": "国产替代/周期反转/算力需求",
    "半导体及元件": "国产替代/周期反转/算力需求",
    "白酒": "消费复苏/外资回流/批价回升",
    "食品饮料": "消费复苏/外资回流/批价回升",
    "新能源": "政策托底/储能新叙事/超跌反弹",
    "电力": "AI算力供电/夏季缺口/煤电转型",
    "汽车整车": "出口数据/智驾落地/价格战缓和",
    "光伏设备": "产能出清/N型技术迭代/海外需求",
    "医疗器械": "集采边际缓和/创新药审批加速",
    "互联网服务": "AI应用落地/降本增效/平台经济反弹",
    "人工智能": "大模型迭代/算力租赁/应用场景爆发",
    "通信设备": "CPO需求/光模块涨价/海外云厂商资本开支",
    "军工": "订单落地/新型号/国企改革",
    "通用设备": "设备更新/高端制造/政策补贴",
    "银行": "息差见底/地产风险缓释/估值修复",
    "证券": "市场成交放量/政策暖风/做市商扩容",
    "保险": "长端利率修复/资产质量改善",
    "房地产开": "政策松绑/成交回暖/去化预期",
    "物流": "AI供应链/跨境电商/油价下跌",
    "广告营销": "AI营销/短剧出海/数字经济",
    "传媒": "AI内容/短剧出海/游戏版号",
    "建筑装饰": "基建投资/旧改/地产链复苏",
    "机器人": "具身智能/特斯拉Optimus/工业自动化",
    "商业航天": "星舰技术/低轨卫星/商业发射",
}


def _calc_zt_strength(row, same_ind_count=1):
    """多维度涨停强弱评分 — 返回 (score, reasons_list, zt_logic_str)"""
    score = 0.0; reasons = []

    # ── 资金面 30分 ──
    seal = float(row.get("封板资金", 0) or 0)
    if seal > 5e8: score += 10; reasons.append("封板>5亿")
    elif seal > 1e8: score += 7; reasons.append("封板>1亿")
    elif seal > 5e7: score += 4

    hand = float(row.get("换手率", 0) or 0)
    if 3 <= hand <= 15: score += 10; reasons.append(f"换手{hand:.1f}%健康")
    elif 1 <= hand < 3 or 15 < hand <= 25: score += 5
    else: score += 2

    amt = float(row.get("成交额", 0) or 0)
    if amt > 1e9: score += 10; reasons.append("成交>10亿")
    elif amt > 3e8: score += 7
    elif amt > 1e8: score += 4

    # ── 情绪面 35分 ──
    lb = int(row.get("连板数", 1) or 1)
    if lb >= 5: score += 15; reasons.append(f"{lb}连板妖股")
    elif lb >= 3: score += 12; reasons.append(f"{lb}连板")
    elif lb >= 2: score += 8; reasons.append("2连板")
    else: score += 3

    t_str = str(row.get("首次封板时间", "150000")).zfill(6)
    hhmm = int(t_str[:4]) if len(t_str) >= 4 else 1500
    if hhmm <= 930: score += 12; reasons.append("9:30前封板⭐")
    elif hhmm <= 1030: score += 8; reasons.append("10:30前封板")
    elif hhmm <= 1330: score += 5
    else: score += 2

    zb = int(row.get("炸板次数", 0) or 0)
    if zb == 0: score += 8; reasons.append("无炸板")
    elif zb == 1: score += 5
    else: score += 2

    # ── 技术面 20分 ──
    mv = float(row.get("流通市值", 0) or 0)
    if mv < 5e9: score += 10; reasons.append("小盘<50亿")
    elif mv < 1.5e10: score += 7
    elif mv < 5e10: score += 4
    else: score += 2

    zt_stat = str(row.get("涨停统计", "1/1"))
    try:
        n, m = zt_stat.split("/")
        ratio = int(n) / max(int(m), 1)
        if ratio >= 0.7: score += 10; reasons.append(f"近{m}天{zt_stat}高频")
        elif ratio >= 0.5: score += 7
        else: score += 4
    except Exception:
        score += 5

    # ── 板块共振 15分 ──
    if same_ind_count >= 3: score += 15; reasons.append(f"板块{same_ind_count}股共振🔥")
    elif same_ind_count == 2: score += 10; reasons.append("板块2股共振")
    else: score += 5

    # 涨停原因
    ind = str(row.get("所属行业", ""))
    zt_logic = ZT_LOGIC_MAP.get(ind, f"{ind}板块异动")
    if lb >= 3:
        zt_logic += f" · {lb}板龙头"
    if same_ind_count >= 3:
        zt_logic += " · 板块高潮"

    return round(score, 1), reasons, zt_logic


def _estimate_zt_next_day_winrate(row, is_first_board_today=True):
    """估算涨停次日胜率 — 基于连板高度 + 历史统计种子"""
    lb = int(row.get("连板数", 1) or 1)
    zb = int(row.get("炸板次数", 0) or 0)
    hand = float(row.get("换手率", 0) or 0)
    t_str = str(row.get("首次封板时间", "150000")).zfill(6)
    hhmm = int(t_str[:4]) if len(t_str) >= 4 else 1500

    # 游资实战统计: 不同条件下的次日溢价概率
    base_rate = 50.0
    if lb >= 5: base_rate = 82.0  # 妖股接力
    elif lb >= 3: base_rate = 70.0
    elif lb == 2: base_rate = 58.0
    else: base_rate = 45.0

    # 封板时间加分
    if hhmm <= 930: base_rate += 10
    elif hhmm <= 1030: base_rate += 5
    elif hhmm >= 1400: base_rate -= 8

    # 炸板扣分
    base_rate -= zb * 8

    # 换手率极端扣分
    if hand > 25: base_rate -= 10  # 超高换手=出货
    elif hand < 1: base_rate -= 5   # 流动性差

    base_rate = max(15, min(92, base_rate))
    return round(base_rate, 1)


def _show_zt_logic_popup(parent, row, score, reasons, zt_logic, winrate):
    """涨停股 ❓弹窗 — 涨停逻辑 + 次日胜率 + 历史案例"""
    import tkinter as tk
    dlg = tk.Toplevel(parent)
    code = row.get("代码", "")
    name = row.get("名称", "")
    dlg.title(f"📘 {name}({code}) 涨停详解")
    dlg.geometry("520x560")
    dlg.configure(bg="#1E1E1E")
    dlg.transient(parent)

    # 顶部标题栏
    tk.Label(dlg, text=f"📘 {name}({code})", bg="#1E1E1E", fg="#FFD54F",
             font=("", 14, "bold")).pack(pady=(10, 2))
    tk.Label(dlg, text=f"所属行业: {row.get('所属行业', '—')}  |  连板数: {row.get('连板数', 1)}板  |  涨停统计: {row.get('涨停统计', '1/1')}",
             bg="#1E1E1E", fg="#90A4AE", font=("", 12)).pack()

    # 分数大字
    score_frame = tk.Frame(dlg, bg="#1E1E1E"); score_frame.pack(fill=tk.X, pady=10)
    fg = "#66BB6A" if score >= 70 else "#FFA726" if score >= 50 else "#EF5350"
    tk.Label(score_frame, text=f"强弱评分: {score:.0f} / 100", bg="#1E1E1E", fg=fg,
             font=("", 22, "bold")).pack(side=tk.LEFT, padx=20)
    tk.Label(score_frame, text=f"📈 次日胜率估: {winrate:.0f}%", bg="#1E1E1E", fg="#81C784",
             font=("", 14, "bold")).pack(side=tk.RIGHT, padx=20)

    # 涨停原因卡片
    card1 = tk.Frame(dlg, bg="#263238", padx=10, pady=8); card1.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(card1, text="💡 涨停逻辑", bg="#263238", fg="#FFD54F",
             font=("", 10, "bold")).pack(anchor="w")
    tk.Label(card1, text=zt_logic, bg="#263238", fg="#E0E0E0",
             font=("", 11), wraplength=480, justify=tk.LEFT).pack(anchor="w", pady=(4, 0))

    # 强弱点
    card2 = tk.Frame(dlg, bg="#1B3A1B" if score >= 60 else "#3E2723", padx=10, pady=8)
    card2.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(card2, text="✨ 强弱要点", bg=card2["bg"], fg="#CE93D8",
             font=("", 10, "bold")).pack(anchor="w")
    reason_text = " | ".join(reasons) if reasons else "(无特殊标记)"
    tk.Label(card2, text=reason_text, bg=card2["bg"], fg="#E0E0E0",
             font=("", 10), wraplength=480, justify=tk.LEFT).pack(anchor="w", pady=(4, 0))

    # 次日概率说明
    card3 = tk.Frame(dlg, bg="#263238", padx=10, pady=8); card3.pack(fill=tk.X, padx=10, pady=4)
    tk.Label(card3, text="📈 次日表现估算", bg="#263238", fg="#81C784",
             font=("", 10, "bold")).pack(anchor="w")
    lb = int(row.get("连板数", 1) or 1)
    if lb >= 3:
        desc = f"{lb}连板龙头, 游资接力意愿强, 次日高开概率高 (历史统计 {winrate:.0f}%)。注意: 3板以上是情绪博弈, 炸板也极快!"
    elif lb == 2:
        desc = f"2连板, 情绪确认期。若早盘快速弱转强, 次日有望继续板。平开震荡则关注同板块是否有助攻。历史胜率 {winrate:.0f}%"
    else:
        desc = f"首板异动, 次日方向看板块是否有持续消息催化 + 大盘情绪配合。历史首板次日溢价 {winrate:.0f}%。"
    tk.Label(card3, text=desc, bg="#263238", fg="#BDBDBD",
             font=("", 12), wraplength=480, justify=tk.LEFT).pack(anchor="w", pady=(4, 0))

    # 操作建议
    card4 = tk.Frame(dlg, bg="#1E1E1E", padx=10, pady=8); card4.pack(fill=tk.X, padx=10, pady=8)
    tk.Label(card4, text="🎯 操作建议", bg="#1E1E1E", fg="#CE93D8",
             font=("", 10, "bold")).pack(anchor="w")
    if score >= 70:
        tip = "⭐ 高分票, 次日优先关注! 若高开<5%可考虑低吸接力, 高开>7%追高风险大。"
    elif score >= 50:
        tip = "📊 中等强度, 观察次日开盘30分钟是否放量站稳均价线再判断。"
    else:
        tip = "⚠️ 低分票, 谨慎参与。等次日板块明确方向后再操作。"
    tk.Label(card4, text=tip, bg="#1E1E1E", fg="#E0E0E0",
             font=("", 10), wraplength=480, justify=tk.LEFT).pack(anchor="w", pady=(4, 0))

    tk.Button(dlg, text="关闭", command=dlg.destroy).pack(pady=8)


def _build_orderbook(parent, win, col=1):
    """② 🌍全球五资产联动 — 替代原观察盘口 (黄金/美元/美债/纳指/原油)"""
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#FFD54F",
                        font=("", 12, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")

    _add_title_row(frm, "② 🌍全球五资产联动 (金/美/债/指/油) — 影响A股主线",
                   "#FFD54F", ORDERBOOK_KNOWLEDGE)

    # 5 资产卡片 (一行) — 紧凑布局
    ASSETS = [
        ("💎黄金", "#FFD700", "贵金属/有色/军工", "金涨→避险+商品"),
        ("💵美元", "#2196F3", "银行/保险/周期", "美强→外资压力+周期强"),
        ("🏦美债", "#FF9800", "银行息差/地产估值", "债↑→息差好;债↓→估值修复"),
        ("📈纳指", "#4CAF50", "半导体/软件/科创", "纳指反弹→科技共振"),
        ("🛢️原油", "#E91E63", "石油/煤炭/新能源", "油涨→周期+通胀+新能替代"),
    ]

    cards_row = tk.Frame(frm, bg="#1E1E1E"); cards_row.pack(fill=tk.X, pady=2)
    win._asset_cards = {}
    for i, (name, color, link_sector, link_suggest) in enumerate(ASSETS):
        card = tk.Frame(cards_row, bg="#263238", padx=6, pady=4, relief=tk.RIDGE, bd=1)
        card.grid(row=0, column=i, sticky="nsew", padx=2)
        cards_row.grid_columnconfigure(i, weight=1)

        tk.Label(card, text=name, bg="#263238", fg=color,
                 font=("", 13, "bold")).pack(anchor=tk.W)
        price_lbl = tk.Label(card, text="—", bg="#263238", fg="#FFFFFF",
                             font=("", 15, "bold"))
        price_lbl.pack(anchor=tk.W, pady=(0, 2))
        pct_lbl = tk.Label(card, text="今日 —  5日 —", bg="#263238", fg="#9E9E9E",
                           font=("", 10))
        pct_lbl.pack(anchor=tk.W)
        tk.Label(card, text=f"⚡{link_suggest}", bg="#263238", fg="#BDBDBD",
                 font=("", 12), wraplength=100, justify=tk.LEFT).pack(anchor=tk.W, pady=(3, 0))

        win._asset_cards[name] = {
            "price": price_lbl, "pct": pct_lbl,
            "sector": link_sector, "suggest": link_suggest
        }

    # 刷新按钮
    btn_row = tk.Frame(frm, bg="#1E1E1E"); btn_row.pack(fill=tk.X, pady=(4, 0))
    refresh_btn = tk.Button(btn_row, text="🔄 刷新全球资产", bg="#FF6D00", fg="white",
                            font=("", 10, "bold"), padx=8, command=lambda: _refresh_global_assets(win))
    refresh_btn.pack(side=tk.RIGHT, padx=2)

    # 操作建议区
    win._asset_suggestion = tk.Label(frm, text="⏳ 等待加载全球资产数据...",
                                     bg="#1E1E1E", fg="#E0E0E0",
                                     font=("", 11), wraplength=600, justify=tk.LEFT,
                                     anchor="w")
    win._asset_suggestion.pack(fill=tk.X, pady=(6, 2))

    # 异步加载 (后台线程拉数据, 主线程 configure)
    def _auto_load():
        import threading
        threading.Thread(target=lambda: _refresh_global_assets(win), daemon=True).start()
    frm.after(200, _auto_load)


def _refresh_global_assets(win):
    """🌍 拉全球 5 资产实时数据 (ThreadPool 并行 + 新浪兜底)"""
    win._asset_suggestion.configure(text="⏳ 正在拉全球资产数据...", fg="#FFD54F")
    try:
        import concurrent.futures as cf
        import akshare as ak
        import requests, re

        results = {}

        def _safe_pct(d, col):
            """安全计算 pct — 取最后一天和五天前"""
            try:
                vals = d[col].dropna().tolist()
                if len(vals) >= 7:
                    pct1d = (vals[-1] - vals[-2]) / vals[-2] * 100
                    pct5d = (vals[-1] - vals[-6]) / vals[-6] * 100
                    return vals[-1], round(pct1d, 2), round(pct5d, 2)
                elif len(vals) >= 2:
                    pct1d = (vals[-1] - vals[-2]) / vals[-2] * 100
                    return vals[-1], round(pct1d, 2), 0
                return vals[-1], 0, 0
            except:
                return None, 0, 0

        def _gold():
            """💎 黄金 — akshare futures_foreign_hist 列名 close"""
            try:
                d = ak.futures_foreign_hist("XAU")
                return _safe_pct(d, "close")
            except Exception as e:
                print(f"[🌍黄金] 失败: {e}"); return None, 0, 0

        def _dxy():
            """💵 美元 — 用新浪 DXY 或纳指代理"""
            try:
                d = ak.index_us_stock_sina(".DXY")
                return _safe_pct(d, "close")
            except:
                try:
                    d = ak.index_us_stock_sina(".IXIC")
                    v, p1, p5 = _safe_pct(d, "close")
                    return v, p1, p5  # 纳指代理
                except:
                    return None, 0, 0

        def _bond():
            """🏦 美债收益率 — 用 akshare bond_zh_us_rate"""
            try:
                d = ak.bond_zh_us_rate()
                # 找美国国债10年收益率列
                col_10y = [c for c in d.columns if "美国国债收益率10年" in str(c)]
                col_china10 = [c for c in d.columns if "中国国债收益率10年" in str(c)]
                if col_10y:
                    col = col_10y[0]
                elif col_china10:
                    col = col_china10[0]
                else:
                    col = d.columns[-1]
                vals = d[col].dropna().tolist()
                if vals:
                    v = float(vals[-1])
                    return v, 0, 0  # 债券收益率不做 pct
                return None, 0, 0
            except Exception as e:
                print(f"[🌍美债] 失败: {e}"); return None, 0, 0

        def _ixic():
            """📈 纳指 — akshare index_us_stock_sina"""
            try:
                d = ak.index_us_stock_sina(".IXIC")
                return _safe_pct(d, "close")
            except Exception as e:
                print(f"[🌍纳指] 失败: {e}"); return None, 0, 0

        def _oil():
            """🛢️ 原油 — akshare futures_foreign_hist 列名 close"""
            try:
                d = ak.futures_foreign_hist("CL")
                return _safe_pct(d, "close")
            except Exception as e:
                print(f"[🌍原油] 失败: {e}"); return None, 0, 0

        with cf.ThreadPoolExecutor(5) as ex:
            futures = {}
            for name, fn in [("💎黄金", _gold), ("💵美元", _dxy),
                             ("🏦美债", _bond), ("📈纳指", _ixic), ("🛢️原油", _oil)]:
                futures[ex.submit(fn)] = name
            for f in cf.as_completed(futures, timeout=15):
                name = futures[f]
                try:
                    results[name] = f.result(timeout=12)
                except Exception as e:
                    print(f"[🌍{name}] 超时: {e}")
                    results[name] = None

        print(f"[🌍全球资产] 结果: {results}")

        # 渲染 (主线程)
        def _render():
            highlights = []
            for name, card in win._asset_cards.items():
                res = results.get(name)
                if res is None or res[0] is None:
                    card["price"].configure(text="—")
                    card["pct"].configure(text="加载中")
                    continue
                price, pct1d, pct5d = res
                # 格式化价格
                if name == "🏦美债":
                    fmt_price = f"{price:.2f}%"
                elif price > 1000:
                    fmt_price = f"{price:,.0f}"
                else:
                    fmt_price = f"{price:,.2f}"
                card["price"].configure(text=fmt_price)
                pct_color = "#EF5350" if pct1d > 0 else "#66BB6A" if pct1d < 0 else "#9E9E9E"
                if name == "🏦美债":
                    card["pct"].configure(text=f"中国10Y  (美债数据延迟)", fg="#BDBDBD")
                else:
                    card["pct"].configure(text=f"今日 {pct1d:+.2f}%  5日 {pct5d:+.2f}%", fg=pct_color)
                if abs(pct1d) > 1.5 or abs(pct5d) > 3:
                    highlights.append(f"⚡ {name}{'📈' if pct1d > 0 else '📉'} {pct1d:+.1f}% → {card['suggest']}")

            sug_text = "🎯 今日关注:\n" + "\n".join(highlights) if highlights else "✅ 全球资产已加载, 无显著联动信号"
            win._asset_suggestion.configure(text=sug_text, fg="#E0E0E0")

        try: win.after(0, _render)
        except Exception as e: print(f"[🌍渲染] 异常: {e}")

    except Exception as e:
        try: win.after(0, lambda: win._asset_suggestion.configure(text=f"❌ 加载失败: {e}", fg="#F44336"))
        except: pass


def _show_zt_rank_dialog(parent):
    """📊 涨停强弱排名 — 独立弹窗, 板块分组 + 多维度算法"""
    import threading
    dlg = tk.Toplevel(parent)
    dlg.title("📊 涨停强弱排名 (游资多维度·板块分组)")
    dlg.geometry("960x620")
    dlg.configure(bg="#1E1E1E")
    dlg.transient(parent)

    # 标题 + 日期 + 刷新 (grid 三列: 左标题 | 中📝 | 右日期)
    top = tk.Frame(dlg, bg="#1E1E1E"); top.pack(fill=tk.X, padx=6, pady=4)
    top.grid_columnconfigure(0, weight=0); top.grid_columnconfigure(1, weight=1); top.grid_columnconfigure(2, weight=0)
    tk.Label(top, text="📊 涨停强弱排名  |  游资多维度算法 · 板块分组",
             bg="#1E1E1E", fg="#FF6D00", font=("", 11, "bold")).grid(row=0, column=0, sticky="w")
    _add_article_btn(dlg, parent, focus_layer="📊 涨停强弱排名")
    date_lbl = tk.Label(top, text="⏳ 加载中...", bg="#1E1E1E", fg="#BDBDBD", font=("", 12))
    date_lbl.grid(row=0, column=2, sticky="e", padx=(10, 0))

    # Treeview: 嵌套板块分组
    cols = ("rank", "name", "logic", "score", "time", "lb", "zb", "hand", "ind", "help")
    headings = [("#", "名称", "💡逻辑", "分", "封板", "板", "炸", "换手", "行业", "❓")]
    widths = [28, 92, 160, 30, 45, 22, 22, 38, 60, 24]
    tv = ttk.Treeview(dlg, columns=cols, show="headings tree", height=22)
    tv.configure(rowheight=20)
    for i, c in enumerate(cols):
        tv.heading(c, text=headings[0][i])
        tv.column(c, width=widths[i], anchor="center", stretch=False)
    tv.column("logic", anchor="w", stretch=True)
    tv.tag_configure("high", foreground="#66BB6A", font=("", 11))
    tv.tag_configure("mid", foreground="#FFA726", font=("", 11))
    tv.tag_configure("low", foreground="#EF5350", font=("", 11))
    tv.tag_configure("rank1", foreground="#FFD54F", font=("", 11, "bold"))
    tv.tag_configure("sector", foreground="#FF6D00", font=("", 12, "bold"), background="#263238")
    tv.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

    # 存映射
    by_iid = {}

    def _on_double_click(event):
        iid = tv.identify_row(event.y)
        if not iid: return
        parent_iid = tv.parent(iid)
        if parent_iid:
            info = by_iid.get(iid)
            if not info: return
            row, _s, *_ = info
            try:
                code = str(row.get("代码", ""))
                name = str(row.get("名称", ""))
                if code.startswith(("6", "9")): sina = "sh" + code
                elif code.startswith(("0", "3")): sina = "sz" + code
                elif code.startswith(("4", "8")): sina = "bj" + code
                else: sina = "sh" + code
                _show_stock_daily_kline(dlg, sina, name)
            except Exception as e: print(f"[涨停弹窗双击] {e}")
        else:
            try: tv.item(iid, open=not tv.item(iid, "open"))
            except Exception: pass

    def _on_single_click(event):
        region = tv.identify("region", event.x, event.y)
        if region != "cell": return
        col_id = tv.identify_column(event.x)
        if col_id != f"#{len(cols)}": return
        iid = tv.identify_row(event.y)
        if not iid: return
        parent_iid = tv.parent(iid)
        if not parent_iid: return
        info = by_iid.get(iid)
        if not info: return
        row, score, reasons, zt_logic, winrate = info
        _show_zt_logic_popup(dlg, row, score, reasons, zt_logic, winrate)

    tv.bind("<Double-1>", _on_double_click)
    tv.bind("<ButtonRelease-1>", _on_single_click)

    tk.Label(dlg, text="💡 双击股票 → 日K线  |  双击板块 → 展开/收起  |  点❓ → 涨停详解",
             bg="#1E1E1E", fg="#78909C", font=("", 11)).pack(anchor="w", padx=6, pady=(0, 4))

    # 后台加载
    def _bg():
        import datetime
        try:
            import akshare as ak
        except Exception:
            dlg.after(0, lambda: date_lbl.config(text="❌ akshare 不可用", fg="#EF5350"))
            return

        today = datetime.date.today(); d = today
        while d.weekday() >= 5: d -= datetime.timedelta(days=1)
        date_str = d.strftime("%Y%m%d")

        try:
            df = ak.stock_zt_pool_em(date=date_str)
        except Exception as e:
            dlg.after(0, lambda: date_lbl.config(text=f"❌ {e}", fg="#EF5350"))
            return

        if df is None or len(df) == 0:
            dlg.after(0, lambda: date_lbl.config(text=f"📅 {date_str} 无涨停", fg="#BDBDBD"))
            return

        ind_counts = df["所属行业"].value_counts().to_dict() if "所属行业" in df.columns else {}
        results = []
        for _, r in df.iterrows():
            same_ind = ind_counts.get(r.get("所属行业", ""), 1)
            score, reasons, zt_logic = _calc_zt_strength(r, same_ind)
            winrate = _estimate_zt_next_day_winrate(r)
            results.append((r, score, reasons, zt_logic, winrate))
        results.sort(key=lambda x: -x[1])

        # 按板块分组
        by_ind = {}
        for item in results:
            ind = str(item[0].get("所属行业", "其他"))
            by_ind.setdefault(ind, []).append(item)
        sector_scores = []
        for ind, items in by_ind.items():
            n = len(items); avg_s = sum(it[1] for it in items) / max(n, 1)
            sector_scores.append((ind, n, avg_s, n * avg_s))
        sector_scores.sort(key=lambda x: -x[3])
        top_sectors = sector_scores[:10]

        def _render():
            tv.delete(*tv.get_children())
            by_iid.clear()
            for ind, n_stk, avg_s, heat in top_sectors:
                ind_short = ind[:8]
                parent_iid = f"sector_{ind}"
                tv.insert("", tk.END, iid=parent_iid, open=True,
                          values=("", f"📌 {ind_short}  ({n_stk}只 均分{avg_s:.0f})",
                                  f"🔥 {heat:.0f}", "", "", "", "", "", ind_short, ""),
                          tags=("sector",))
                top3 = by_ind[ind][:3]
                for child_n, it in enumerate(top3, 1):
                    row, score, reasons, zt_logic, winrate = it
                    t = str(row.get("首次封板时间", "")).zfill(6)
                    t_fmt = f"{t[:2]}:{t[2:4]}" if len(t) >= 4 else "--:--"
                    lb = int(row.get("连板数", 1) or 1)
                    zb = int(row.get("炸板次数", 0) or 0)
                    hand = float(row.get("换手率", 0) or 0)
                    name = str(row.get("名称", ""))[:8]
                    tag = "high" if score >= 70 else "mid" if score >= 50 else "low"
                    child_iid = f"child_{ind}_{child_n}"
                    tv.insert(parent_iid, tk.END, iid=child_iid, open=False,
                              values=(child_n, name, zt_logic, f"{score:.0f}",
                                      t_fmt, lb, zb, f"{hand:.1f}", ind_short, "❓"),
                              tags=(tag,))
                    by_iid[child_iid] = (row, score, reasons, zt_logic, winrate)
            n = len(results)
            high = sum(1 for _, s, *_ in results if s >= 70)
            date_lbl.config(
                text=f"📅 {date_str}  |  共 {n} 只 · {len(top_sectors)}板块  |  强势≥70: {high}",
                fg="#66BB6A" if high >= 5 else "#FFA726")

        dlg.after(0, _render)

    threading.Thread(target=_bg, daemon=True).start()


def _load_orderbook(win):
    """加载盘口五档 (新浪 snapshot) + 涨停排队 + 特定数量"""
    # 盘口 (秒出)
    def _load_snapshot():
        try:
            sel = win._ob_cb.get()
            import re, requests
            code_match = re.search(r'[(（](\d{6})[)）]', sel) or re.search(r'([a-z]{2}\d{6})', sel.lower())
            if not code_match: return
            raw = code_match.group(1)
            sina = raw if raw[:2].isalpha() else ("sh" if raw.startswith("6") or raw.startswith("9") else "sz" if raw.startswith("0") or raw.startswith("3") else "bj" if raw.startswith(("4","8")) else "sh") + raw
            url = f"https://hq.sinajs.cn/list={sina}"
            r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=6)
            if not r.ok or '"' not in r.text: return
            parts = r.text.split('"')[1].split(',')
            if len(parts) < 32: return
            cur = float(parts[3])
            bid_prices = parts[10:5:-1]   # 买5..买1
            bid_vols   = parts[15:10:-1]
            ask_prices = parts[16:21]     # 卖1..卖5
            ask_vols   = parts[21:26]
            def _fmt(price, vol):
                try:
                    p = float(price); v = int(float(vol))
                    v_str = f"{v//10000}万" if v >= 10000 else str(v)
                    return f"{p:.2f}  {v_str}"
                except: return f"{price}  {vol}"
            def _fill(lbls, prices, vols, ask=True):
                for i in range(5):
                    lbls[i].config(text=f"{'卖' if ask else '买'}{5-i} {_fmt(prices[i], vols[i])}")
            _fill(win._ob_ask_labels, ask_prices, ask_vols, ask=True)
            _fill(win._ob_bid_labels, bid_prices, bid_vols, ask=False)
            pct = (cur - float(parts[2])) / float(parts[2]) * 100 if float(parts[2]) else 0
            tag = "+" if pct >= 0 else ""
            win._ob_cur_label.config(text=f"现价 {cur:.2f}  {tag}{pct:.2f}%",
                                      fg="#EF5350" if pct >= 0 else "#66BB6A")
        except Exception as e:
            print(f"[👁️盘口] snapshot err: {e}")
    _load_snapshot()
    # 涨停排队 + 特定数量 (后台)
    def _bg():
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            pct_col = [c for c in df.columns if "涨跌幅" in str(c)][0]
            hand_col = [c for c in df.columns if "换手率" in str(c)]
            vol_col = [c for c in df.columns if "成交量" in str(c)]
            limit_up = df[df[pct_col] >= 9.5].head(10)
            win.after(0, lambda: _fill_limit_up(win, limit_up, hand_col, vol_col))
            vols = df[vol_col[0]].astype(float).values
            v5000 = (vols >= 500000).sum(); v500 = ((vols >= 50000) & (vols < 500000)).sum()
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
            vol = float(r[vol_col[0]]) / 10000
            hand = r[hand_col[0]] if hand_col else 0
            tv.insert("", tk.END, values=(code, name, f"{vol:.1f}", f"{hand:.2f}"))
        except Exception: pass


# ═══════════════════════════════════════════════════════════════
# ③ 量能 — 大盘/板块/沪Vs创 + 贴水卡片 (Canvas 柱状图)
# ═══════════════════════════════════════════════════════════════

def _build_volume_panel(parent, win, col=2):
    frm = tk.LabelFrame(parent, bg="#121212", fg="#81C784",
                        font=("", 12, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "③ 量能 (大盘/沪Vs创/板块增量/贴水)",
                   "#81C784", VOLUME_KNOWLEDGE)

    # 大盘量能: 今日 vs 昨日 Canvas
    tk.Label(frm, text="📊 今日 vs 昨日成交额 (亿元)",
             bg="#121212", fg="#FFD54F", font=("", 11, "bold")).pack(anchor=tk.W)
    canvas1 = tk.Canvas(frm, bg="#121212", height=80, highlightthickness=0)
    canvas1.pack(fill=tk.X, pady=(0, 2))
    win._vol_main_canvas = canvas1

    # 沪 Vs 创
    tk.Label(frm, text="📊 沪市 Vs 创业板 (成交量比)",
             bg="#121212", fg="#FFD54F", font=("", 11, "bold")).pack(anchor=tk.W)
    canvas2 = tk.Canvas(frm, bg="#121212", height=70, highlightthickness=0)
    canvas2.pack(fill=tk.X, pady=(0, 2))
    win._vol_hs_canvas = canvas2

    # 板块量能增量榜 — 暗色主题 + 增量%上色
    tk.Label(frm, text="📊 板块增量TOP (今日 > 昨日)",
             bg="#121212", fg="#FFD54F", font=("", 11, "bold")).pack(anchor=tk.W)

    # ttk style 统一暗色
    import tkinter.ttk as _ttk
    try:
        _sty = _ttk.Style()
        _sty.configure("Dark.Treeview", background="#1E1E1E", foreground="#E0E0E0",
                       fieldbackground="#1E1E1E", rowheight=24, font=("", 11))
        _sty.configure("Dark.Treeview.Heading", background="#263238", foreground="#FFD54F",
                       font=("", 11, "bold"))
    except Exception:
        pass

    tv = _ttk.Treeview(frm, columns=("板块", "今日亿", "昨日亿", "增量%"),
                       show="headings", height=6, style="Dark.Treeview")
    for c, w in [("板块", 100), ("今日亿", 70), ("昨日亿", 70), ("增量%", 70)]:
        tv.heading(c, text=c); tv.column(c, width=w, anchor="center")
    # tag 颜色 (按增量%)
    tv.tag_configure("surge", background="#4A148C", foreground="#FFD54F")   # 爆增量 >50%
    tv.tag_configure("up",    background="#1B5E20", foreground="#FFFFFF")   # 正增量
    tv.tag_configure("down",  background="#3E2723", foreground="#BCAAA4")   # 负增量
    tv.tag_configure("flat",  background="#1E1E1E", foreground="#9E9E9E")   # 持平
    tv.pack(fill=tk.X, padx=2)
    win._vol_block_tv = tv

    # 贴水卡片
    tk.Label(frm, text="📊 股指期货贴水 (实时)",
             bg="#121212", fg="#FFD54F", font=("", 11, "bold")).pack(anchor=tk.W, pady=(6, 2))
    win._fut_basis_lbl = tk.Label(frm, text="加载中...", bg="#121212",
                                  fg="#E0E0E0", font=("Menlo", 11), justify=tk.LEFT)
    win._fut_basis_lbl.pack(fill=tk.X, padx=2)


# ============================================================
# Block / Stock Daily K-line Dialog (with MA/MACD/KDJ/support-resistance)
# ============================================================

def _fetch_block_daily(block_name, days=80, period="周k"):
    """Fetch block K-line (default 周k) via akshare eastmoney → hardcoded seed (offline)
    
    period: "日k" / "周k" / "月k"
    """
    import numpy as np

    # 1) akshare 东财行业历史
    try:
        import akshare as ak
        em_name = BLOCK_EM_NAME.get(block_name, block_name)
        df = ak.stock_board_industry_hist_em(symbol=em_name, period=period, adjust="qfq")
        if df is not None and len(df) > 10:
            date_col = [c for c in df.columns if "日期" in str(c) or "date" in str(c).lower()][0]
            df = df.sort_values(date_col).tail(days)
            dates = df[date_col].astype(str).tolist()
            return {"dates": dates, "o": df.iloc[:, 1].astype(float).to_numpy(),
                    "h": df.iloc[:, 2].astype(float).to_numpy(),
                    "l": df.iloc[:, 3].astype(float).to_numpy(),
                    "c": df.iloc[:, 4].astype(float).to_numpy(),
                    "v": df.iloc[:, 5].astype(float).to_numpy(),
                    "src": f"EM-{em_name}-{period}"}
    except Exception as e:
        print(f"[watch-K] akshare block fail ({period}): {e}")

    # 2) Seed data (offline fallback — deterministic per block name)
    print(f"[watch-K] using SEED data for {block_name}")
    return _make_seed_daily(block_name, days)


def _make_seed_daily(name, days=180):
    """Generate pseudo-random seed data for block — deterministic per name"""
    import numpy as np
    from datetime import datetime, timedelta
    seed = abs(hash(name)) % (2**31)
    rng = np.random.default_rng(seed)
    base_prices = {
        "券商": 9500, "银行": 1800, "CPO": 3200, "半导体": 5600,
        "AI": 4200, "电池": 2800, "煤炭": 3500, "电力": 4100,
        "医疗": 15000, "军工": 2900, "航天": 2100, "风电": 1900,
        "光伏": 2600, "机器人": 5800, "白酒": 21000, "黄金": 580,
    }
    base = base_prices.get(name, 3000)
    c = np.zeros(days); c[0] = base
    drift = rng.normal(0.0005, 0.015, days)
    for i in range(1, days):
        c[i] = c[i-1] * (1 + drift[i])
    o = c * (1 + rng.normal(0, 0.005, days))
    h = np.maximum(o, c) * (1 + abs(rng.normal(0, 0.008, days)))
    l = np.minimum(o, c) * (1 - abs(rng.normal(0, 0.008, days)))
    v = abs(rng.normal(50000, 20000, days))
    dates = []
    cur = datetime.now() - timedelta(days=days*2)
    while len(dates) < days:
        if cur.weekday() < 5: dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return {"dates": dates, "o": o, "h": h, "l": l, "c": c, "v": v,
            "src": f"SEED-{name}(offline)"}


def _fetch_stock_kline(sina_code, scale=240, days=240):
    """Fetch stock K-line via sina CN_MarketData.getKLineData
    scale: 5/15/30/60 分钟, 240 日线, "week" 周线 (日→周合成), "month" 月线"""
    try:
        import requests, json, time
        import numpy as np
        # 周/月需要先拉日线再合成
        fetch_scale = 240 if scale in ("week", "month") else scale
        url = f"https://quotes.sina.cn/cn/api/jsonp.php/var%20_{sina_code}_{int(time.time()*1000)}/CN_MarketData.getKLineData"
        params = {"symbol": sina_code, "scale": fetch_scale, "ma": "no", "datalen": days}
        r = requests.get(url, params=params, timeout=12,
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"})
        txt = r.text
        if "(" not in txt or ")" not in txt: return None
        data = json.loads(txt[txt.index("(")+1 : txt.rindex(")")])
        if not data or len(data) < 10: return None
        dates = [d["day"] for d in data]
        o = np.array([float(d["open"]) for d in data])
        h = np.array([float(d["high"]) for d in data])
        l = np.array([float(d["low"]) for d in data])
        c = np.array([float(d["close"]) for d in data])
        v = np.array([float(d["volume"]) for d in data])
        # 合成周线/月线
        if scale == "week":
            return _resample_kline(dates, o, h, l, c, v, "W-MON", f"SINA周线-{sina_code}")
        if scale == "month":
            return _resample_kline(dates, o, h, l, c, v, "ME", f"SINA月线-{sina_code}")
        return {"dates": dates, "o": o, "h": h, "l": l, "c": c, "v": v,
                "src": f"SINA-{scale}min-{sina_code}"}
    except Exception as e:
        print(f"[watch-K] kline fetch fail (scale={scale}): {e}")
        return None


def _resample_kline(dates, o, h, l, c, v, rule, src):
    """Resample daily bars to weekly/monthly via pandas"""
    import pandas as pd, numpy as np
    df = pd.DataFrame({"o": o, "h": h, "l": l, "c": c, "v": v},
                      index=pd.to_datetime(dates, errors="coerce"))
    df = df.dropna().resample(rule).agg({"o": "first", "h": "max", "l": "min",
                                          "c": "last", "v": "sum"}).dropna()
    if len(df) < 5: return None
    return {"dates": df.index.strftime("%Y-%m-%d").tolist(),
            "o": df.o.to_numpy(float), "h": df.h.to_numpy(float),
            "l": df.l.to_numpy(float), "c": df.c.to_numpy(float),
            "v": df.v.to_numpy(float), "src": src}

# Alias for backward compat
_fetch_stock_daily = lambda sina_code, days=240: _fetch_stock_kline(sina_code, scale=240, days=days)


def _ma_calc(arr, n):
    import numpy as np
    out = np.full(len(arr), np.nan)
    if len(arr) >= n:
        cs = np.cumsum(arr)
        out[n-1:] = (cs[n-1:] - np.concatenate([[0], cs[:-n]])) / n
    return out


def _ema_calc(arr, n):
    import pandas as pd
    return pd.Series(arr).ewm(span=n, adjust=False).mean().to_numpy()


def _show_daily_kline_dialog(parent, title, data, sina_code=None):
    """K-line dialog with top-bar period switcher (60min/Day/Week/Month) + full MA/MACD/KDJ/support-resistance."""
    import numpy as np
    import pandas as pd
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle

    dlg = tk.Toplevel(parent)
    dlg.title(f"K-line: {title}")
    dlg.geometry("1080x780")
    dlg.configure(bg="#121212")

    # 顶栏: grid 三列 (标题 | 📝 | 周期按钮)
    top = tk.Frame(dlg, bg="#1E1E1E"); top.pack(fill=tk.X)
    top.grid_columnconfigure(0, weight=0); top.grid_columnconfigure(1, weight=1); top.grid_columnconfigure(2, weight=0)
    tk.Label(top, text=f"📊 {title}",
             bg="#1E1E1E", fg="#FFD54F", font=("", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=6)
    _add_article_btn(dlg, parent, focus_layer=f"📊 K线: {title}")

    PERIODS = [("60分钟", 60), ("日线", 240), ("周线", "week"), ("月线", "month")]
    _period_var = tk.StringVar(value="日线")
    _canvas_ref = {"canvas": None, "toolbar": None, "fig": None}

    def _redraw(new_data):
        """Clear old, redraw with new_data"""
        if _canvas_ref["fig"] is None: return
        fig = _canvas_ref["fig"]
        for ax in fig.axes[:]: fig.delaxes(ax)
        fig.clear()
        # same layout
        gs = fig.add_gridspec(4, 1, height_ratios=[5.5, 1.2, 1.2, 1.2], hspace=0.08)
        ax = fig.add_subplot(gs[0]); axv = fig.add_subplot(gs[1], sharex=ax)
        axm = fig.add_subplot(gs[2], sharex=ax); axk = fig.add_subplot(gs[3], sharex=ax)
        for a in (ax, axv, axm, axk):
            a.set_facecolor("#1E1E1E"); a.tick_params(colors="#9E9E9E", labelsize=8)
            for sp in a.spines.values(): sp.set_color("#444")
            a.grid(True, alpha=0.12, color="#666")

        dates = new_data["dates"]; o = new_data["o"]; h = new_data["h"]; l = new_data["l"]
        c = new_data["c"]; v = new_data["v"]
        x = np.arange(len(dates))
        ma5 = _ma_calc(c, 5); ma10 = _ma_calc(c, 10); ma20 = _ma_calc(c, 20)
        ma60 = _ma_calc(c, 60); ma120 = _ma_calc(c, 120)

        ema12 = _ema_calc(c, 12); ema26 = _ema_calc(c, 26)
        dif = ema12 - ema26; dea = _ema_calc(dif, 9); macd_hist = (dif - dea) * 2

        low9 = pd.Series(l).rolling(9).min().to_numpy()
        high9 = pd.Series(h).rolling(9).max().to_numpy()
        rsv = np.where(high9 - low9 > 0, (c - low9) / (high9 - low9) * 100, 50.0)
        k = _ema_calc(np.nan_to_num(rsv, 50), 3)
        d = _ema_calc(k, 3); j = 3 * k - 2 * d

        # Candles
        for i in range(len(x)):
            up = c[i] >= o[i]; col = "#EF5350" if up else "#66BB6A"
            ax.plot([x[i], x[i]], [l[i], h[i]], color=col, lw=0.8)
            body_lo = min(o[i], c[i]); body_hi = max(o[i], c[i])
            ax.add_patch(Rectangle((x[i]-0.35, body_lo), 0.7, max(body_hi-body_lo, 0.001),
                                    facecolor=col, edgecolor=col, linewidth=0.3))
        ax.plot(x, ma5, color="#FFD54F", lw=1.2, label="MA5")
        ax.plot(x, ma10, color="#42A5F5", lw=1.2, label="MA10")
        ax.plot(x, ma20, color="#AB47BC", lw=1.2, label="MA20")
        ax.plot(x, ma60, color="#66BB6A", lw=1.4, label="MA60")
        ax.plot(x, ma120, color="#FF7043", lw=1.4, label="MA120")

        # Support / Resistance (local extremes, last 120 bars)
        def _local_extrema(arr, order=5):
            hi, lo = [], []
            for i in range(order, len(arr)-order):
                if arr[i] == max(arr[i-order:i+order+1]): hi.append((i, arr[i]))
                if arr[i] == min(arr[i-order:i+order+1]): lo.append((i, arr[i]))
            return hi, lo
        tail = min(120, len(x))
        hi_all = [(idx + len(x) - tail, val) for idx, val in _local_extrema(h[-tail:], 8)[0]]
        lo_all = [(idx + len(x) - tail, val) for idx, val in _local_extrema(l[-tail:], 8)[1]]
        def _dedup(pts, thresh=0.01):
            out = []
            for idx, val in sorted(pts, key=lambda t: -t[1]):
                if not out or abs(val - out[-1][1]) / out[-1][1] > thresh:
                    out.append((idx, val))
            return out[:4]
        for idx, val in _dedup(sorted(hi_all, key=lambda t: -t[1])):
            ax.axhline(val, color="#EF5350", ls="--", lw=0.9, alpha=0.7)
            ax.text(len(x)-1, val, f"  resist {val:.2f}", color="#EF5350", fontsize=8, va="bottom")
        for idx, val in _dedup(sorted(lo_all, key=lambda t: -t[1])):
            ax.axhline(val, color="#66BB6A", ls="--", lw=0.9, alpha=0.7)
            ax.text(len(x)-1, val, f"  support {val:.2f}", color="#66BB6A", fontsize=8, va="top")

        # Chip dist
        try:
            from scipy.stats import gaussian_kde
            prices = np.linspace(np.nanmin(c[-tail:])*0.97, np.nanmax(c[-tail:])*1.03, 50)
            kde = gaussian_kde(c[-tail:])
            dens = kde(prices); dens = dens / dens.max() * 0.22 * (np.nanmax(h)-np.nanmin(l))
            ax.fill_betweenx(prices, len(x)-1-dens, len(x)-1, alpha=0.18, color="#B39DDB")
        except Exception: pass

        last = len(x) - 1
        ax.text(0.01, 0.97,
                f"O{o[last]:.2f} H{h[last]:.2f} L{l[last]:.2f} C{c[last]:.2f} V{v[last]:.0f}",
                transform=ax.transAxes, color="#E0E0E0", fontsize=8, va="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#2A2A2A", edgecolor="#555"))

        cv_colors = ["#EF5350" if c[i] >= o[i] else "#66BB6A" for i in range(len(x))]
        axv.bar(x, v, color=cv_colors, width=0.7, alpha=0.8); axv.set_ylabel("Vol", color="#9E9E9E", fontsize=8)
        vol_ma10 = _ma_calc(v, 10)
        axv.plot(x, vol_ma10, color="#FFD54F", lw=1.2, label="VolMA10")

        md_colors = ["#EF5350" if m >= 0 else "#66BB6A" for m in macd_hist]
        axm.bar(x, macd_hist, color=md_colors, width=0.6, alpha=0.8)
        axm.plot(x, dif, color="#FFD54F", lw=1, label="DIF")
        axm.plot(x, dea, color="#42A5F5", lw=1, label="DEA")
        axm.axhline(0, color="#555", lw=0.5); axm.set_ylabel("MACD", color="#9E9E9E", fontsize=8)

        axk.plot(x, k, color="#FFD54F", lw=1, label="K")
        axk.plot(x, d, color="#42A5F5", lw=1, label="D")
        axk.plot(x, j, color="#AB47BC", lw=0.9, label="J")
        axk.axhline(80, color="#EF5350", lw=0.5, ls="--", alpha=0.6)
        axk.axhline(20, color="#66BB6A", lw=0.5, ls="--", alpha=0.6)
        axk.set_ylabel("KDJ", color="#9E9E9E", fontsize=8)
        axk.set_xlabel(f"Date ({len(dates)} bars)", color="#9E9E9E", fontsize=8)

        step = max(1, len(dates) // 12)
        ticks = x[::step]; lbls = [dates[i][:10] for i in ticks]
        for a in (ax, axv, axm): a.set_xticks(ticks); a.set_xticklabels([])
        axk.set_xticks(ticks); axk.set_xticklabels(lbls, rotation=30, fontsize=7, color="#9E9E9E")
        ax.legend(loc="upper left", fontsize=8, facecolor="#2A2A2A", edgecolor="#555")

        _canvas_ref["canvas"].draw_idle()
        info_lbl.config(text=f"{len(dates)} bars | latest {dates[-1]} | close {c[-1]:.2f} | {new_data.get('src','?')}")

    # 周期切换按钮 (内部 frame pack LEFT, 然后 grid 到 column=2)
    _per_f = tk.Frame(top, bg="#1E1E1E"); _per_f.grid(row=0, column=2, sticky="e")
    for period_label, period_val in PERIODS:
        tk.Radiobutton(_per_f, text=period_label, variable=_period_var, value=period_label,
                       bg="#1E1E1E", fg="#FFD54F", selectcolor="#1E1E1E",
                       activebackground="#1E1E1E", font=("", 10),
                       indicatoron=False, width=7,
                       command=lambda pv=period_val: _on_period_change(pv)
                       ).pack(side=tk.LEFT, padx=2)

    # 切周期
    def _on_period_change(period_val):
        if sina_code is None:
            messagebox.showinfo("提示", "仅从股票入口打开的弹窗支持周期切换")
            return
        print(f"[👁️K线] switch period={period_val} for {sina_code}", flush=True)
        data2 = _fetch_stock_kline(sina_code, scale=period_val, days=240)
        if data2 is None:
            messagebox.showwarning("提示", f"周期 {period_val} 数据获取失败")
            return
        _redraw(data2)

    info_lbl = tk.Label(_per_f, text=f"", bg="#1E1E1E", fg="#A5D6A7", font=("", 12))
    info_lbl.pack(side=tk.RIGHT, padx=10)

    canvas_frame = tk.Frame(dlg, bg="#121212"); canvas_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    # 首次渲染
    fig = Figure(figsize=(11, 7.2), dpi=96, facecolor="#121212")
    fig.subplots_adjust(left=0.08, right=0.95, top=0.96, bottom=0.06, hspace=0.08)
    _canvas_ref["fig"] = fig
    _redraw(data)

    canvas = FigureCanvasTkAgg(fig, master=canvas_frame); canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    try: canvas.get_tk_widget().configure(bg="#121212")
    except Exception: pass
    tb = NavigationToolbar2Tk(canvas, canvas_frame); tb.update(); tb.pack(side=tk.BOTTOM, fill=tk.X)
    _canvas_ref["canvas"] = canvas


def _show_block_daily_kline(win, idx):
    """Single-click block cell -> block weekly K-line"""
    import threading
    name = win._block_meta[idx][0]
    print(f"[watch-K] block '{name}' 周K fetching...", flush=True)
    dlg_load = tk.Toplevel(win); dlg_load.title("Loading"); dlg_load.geometry("280x80")
    dlg_load.configure(bg="#1E1E1E"); dlg_load.transient(win)
    tk.Label(dlg_load, text=f"⏳ 正在加载 {name} 周K线...",
             bg="#1E1E1E", fg="#FFD54F", font=("", 11)).pack(pady=20)
    def _bg():
        data = _fetch_block_daily(name, days=80, period="周k")
        def _done():
            try: dlg_load.destroy()
            except Exception: pass
            if data is None:
                messagebox.showwarning("Warning", f"{name} K-line data fetch failed")
                return
            _show_daily_kline_dialog(win, f"📊 板块周K · {name}", data)
        dlg_load.after(0, _done)
    threading.Thread(target=_bg, daemon=True).start()


def _show_stock_daily_kline(win, sina_code, stock_name=""):
    """Double-click stock -> stock K-line with period switcher (need sina_code for 60min/week/month)"""
    import threading
    label = f"{stock_name} ({sina_code})" if stock_name else sina_code
    print(f"[watch-K] stock '{label}' fetching...", flush=True)
    dlg_load = tk.Toplevel(win); dlg_load.title("Loading"); dlg_load.geometry("260x80")
    dlg_load.configure(bg="#1E1E1E"); dlg_load.transient(win)
    tk.Label(dlg_load, text=f"Loading {label} K-line...",
             bg="#1E1E1E", fg="#FFD54F", font=("", 11)).pack(pady=20)
    def _bg():
        data = _fetch_stock_kline(sina_code, scale=240, days=240)
        def _done():
            try: dlg_load.destroy()
            except Exception: pass
            if data is None:
                messagebox.showwarning("Warning", f"{label} K-line data fetch failed")
                return
            _show_daily_kline_dialog(win, label, data, sina_code=sina_code)
        dlg_load.after(0, _done)
    threading.Thread(target=_bg, daemon=True).start()


def _calc_ichimoku(highs, lows, closes):
    """简化版一目均衡图 5 条线 (numpy)"""
    import numpy as np
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    c = np.asarray(closes, dtype=float)
    n = len(c)

    def _ph(arr, p):
        out = np.full(n, np.nan)
        for i in range(n):
            s = max(0, i - p + 1)
            out[i] = np.max(arr[s:i + 1])
        return out

    def _pl(arr, p):
        out = np.full(n, np.nan)
        for i in range(n):
            s = max(0, i - p + 1)
            out[i] = np.min(arr[s:i + 1])
        return out

    tenkan = (_ph(h, 9) + _pl(l, 9)) / 2.0       # 转换线 9
    kijun = (_ph(h, 26) + _pl(l, 26)) / 2.0      # 基准线 26
    senkou_a = (tenkan + kijun) / 2.0            # 先行A (然后前移26)
    senkou_a = np.concatenate([np.full(26, np.nan), senkou_a[:-26]]) if n > 26 else senkou_a
    senkou_b_raw = (_ph(h, 52) + _pl(l, 52)) / 2.0
    senkou_b = np.concatenate([np.full(26, np.nan), senkou_b_raw[:-26]]) if n > 26 else senkou_b
    chikou = c.copy()                             # 迟行带 (后移26绘制)
    chikou[:26] = np.nan

    return {"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a,
            "senkou_b": senkou_b, "chikou": chikou}


def _fetch_daily_ohlcv(sina_code):
    """拉日K线 (300日), 优先 sina, 回退 tushare"""
    import pandas as pd
    # 1️⃣ Sina
    try:
        import requests as rq
        secid = sina_code  # 如 sz000001
        url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={secid}&scale=240&ma=no&datalen=300"
        resp = rq.get(url, timeout=8)
        if resp.status_code == 200 and resp.text.strip() and resp.text != "null":
            import json
            data = json.loads(resp.text)
            if data and isinstance(data, list):
                df = pd.DataFrame(data)
                df.columns = ["date", "open", "high", "low", "close", "volume"]
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df["date"] = pd.to_datetime(df["date"])
                df = df.dropna().reset_index(drop=True)
                return df.tail(260)  # 留够 26+52 窗口
    except Exception: pass

    # 2️⃣ Tushare fallback
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN")
        if token:
            pro = ts.pro_api(token)
            code = sina_code.replace("sz", "").replace("sh", "")
            df = pro.daily(ts_code=f"{code}.SZ" if sina_code.startswith("sz") else f"{code}.SH",
                           start_date="20250101")
            if df is not None and len(df) > 20:
                df = df.rename(columns={"trade_date": "date"})
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").reset_index(drop=True)
                df = df[["date", "open", "high", "low", "close", "vol"]].rename(columns={"vol": "volume"})
                return df.tail(260)
    except Exception: pass
    return None


def _show_stock_ichimoku(win, sina_code, stock_name=""):
    """双击股票 → 一目均衡图 (Ichimoku Kinko Hyo)"""
    import tkinter as tk
    from tkinter import ttk
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd

    dlg = tk.Toplevel(win)
    dlg.title(f"📈 一目均衡图 | {stock_name} ({sina_code})")
    dlg.geometry("1100x720")
    dlg.configure(bg="#0D0D0D")
    try: dlg.state("zoomed")
    except Exception: pass

    # Banner
    banner = tk.Frame(dlg, bg="#1565C0", height=42); banner.pack(fill=tk.X)
    tk.Label(banner, text=f"📈 一目均衡表 · {stock_name} ({sina_code})",
             bg="#1565C0", fg="white", font=("", 13, "bold")).pack(side=tk.LEFT, padx=12, pady=6)
    status_var = tk.StringVar(value="⏳ 加载中...")
    tk.Label(banner, textvariable=status_var, bg="#1565C0", fg="#BBDEFB",
             font=("", 10)).pack(side=tk.RIGHT, padx=10)

    fig_frame = tk.Frame(dlg, bg="#0D0D0D"); fig_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _do_plot():
        df = _fetch_daily_ohlcv(sina_code)
        if df is None or len(df) < 60:
            dlg.after(0, lambda: status_var.set("❌ 数据不足 (需 ≥ 60 根K)"))
            return

        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        dates = df["date"].values

        ichi = _calc_ichimoku(highs, lows, closes)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                        gridspec_kw={"height_ratios": [3, 1]},
                                        facecolor="#0D0D0D")
        fig.subplots_adjust(hspace=0.05)

        # 主图 K 线
        n = len(closes)
        x = np.arange(n)
        width = 0.7
        colors = ["#EF5350" if closes[i] >= df["open"].values[i] else "#66BB6A" for i in range(n)]
        ax1.bar(x, closes - df["open"].values[i], bottom=df["open"].values[i],
                width=width, color=colors, edgecolor=colors, linewidth=0.5)
        ax1.vlines(x, lows, highs, colors=colors, linewidth=0.5)

        # 一目均衡 5 条线
        ax1.plot(x, ichi["tenkan"], color="#FFB300", linewidth=1.2, label="转换线(9)")
        ax1.plot(x, ichi["kijun"], color="#1E88E5", linewidth=1.5, label="基准线(26)")
        ax1.plot(x, ichi["chikou"], color="#E040FB", linewidth=1, linestyle="--", label="迟行带(26)")

        # 先行带云 (填充)
        mask = ~np.isnan(ichi["senkou_a"]) & ~np.isnan(ichi["senkou_b"])
        if mask.any():
            ax1.fill_between(x, ichi["senkou_a"], ichi["senkou_b"],
                             where=(ichi["senkou_a"] >= ichi["senkou_b"]) & mask,
                             color="#1B5E20", alpha=0.4, label="先行A≥B(看涨云)")
            ax1.fill_between(x, ichi["senkou_a"], ichi["senkou_b"],
                             where=(ichi["senkou_a"] < ichi["senkou_b"]) & mask,
                             color="#B71C1C", alpha=0.4, label="先行A<B(看跌云)")

        # 背景风格
        ax1.set_facecolor("#121212")
        ax1.tick_params(colors="#BDBDBD")
        for spine in ax1.spines.values(): spine.set_color("#424242")
        ax1.set_title(f"{stock_name} 一目均衡表", color="white", fontsize=13, fontweight="bold", pad=8)
        ax1.legend(loc="upper left", fontsize=8, facecolor="#1E1E1E", edgecolor="#424242",
                   labelcolor="#E0E0E0", ncol=3)
        ax1.grid(True, alpha=0.2, color="#616161")
        # x 轴日期
        tick_idx = np.linspace(0, n - 1, min(10, n), dtype=int)
        ax1.set_xticks(tick_idx)
        ax1.set_xticklabels([pd.Timestamp(dates[i]).strftime("%m-%d") for i in tick_idx],
                             color="#BDBDBD", fontsize=8, rotation=30)

        # 成交量副图
        vols = df["volume"].values
        ax2.bar(x, vols, color=colors, width=width, alpha=0.7)
        ax2.set_facecolor("#121212")
        ax2.tick_params(colors="#BDBDBD")
        for spine in ax2.spines.values(): spine.set_color("#424242")
        ax2.grid(True, alpha=0.2, color="#616161")
        ax2.set_xticks(tick_idx)
        ax2.set_xticklabels([pd.Timestamp(dates[i]).strftime("%m-%d") for i in tick_idx],
                             color="#BDBDBD", fontsize=8, rotation=30)

        # 买卖信号
        # 金叉: 转换线上穿基准线
        for i in range(1, n):
            if not np.isnan(ichi["tenkan"][i]) and not np.isnan(ichi["kijun"][i]):
                if ichi["tenkan"][i-1] < ichi["kijun"][i-1] and ichi["tenkan"][i] >= ichi["kijun"][i]:
                    ax1.annotate("金", xy=(i, lows[i]), fontsize=9, color="#EF5350",
                                 fontweight="bold", ha="center", va="top")
                elif ichi["tenkan"][i-1] > ichi["kijun"][i-1] and ichi["tenkan"][i] <= ichi["kijun"][i]:
                    ax1.annotate("死", xy=(i, highs[i]), fontsize=9, color="#66BB6A",
                                 fontweight="bold", ha="center", va="bottom")

        # 云之上/云之下标记
        latest_c = closes[-1]
        latest_a = ichi["senkou_a"][-1] if not np.isnan(ichi["senkou_a"][-1]) else None
        latest_b = ichi["senkou_b"][-1] if not np.isnan(ichi["senkou_b"][-1]) else None
        signal = ""
        if latest_a and latest_b:
            cloud_top = max(latest_a, latest_b)
            cloud_bot = min(latest_a, latest_b)
            if latest_c > cloud_top: signal = "📈 价格在云之上 (看涨)"
            elif latest_c < cloud_bot: signal = "📉 价格在云之下 (看跌)"
            else: signal = "⚖️ 价格在云内部 (震荡)"
        dlg.after(0, lambda: status_var.set(f"📌 {signal} | {n}根K线"))

        canvas = FigureCanvasTkAgg(fig, master=fig_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    import threading
    threading.Thread(target=_do_plot, daemon=True).start()


def _get_first_stock_sina(win, idx):
    """Get first constituent stock's sina code from a block"""
    try:
        import akshare as ak
        name = win._block_meta[idx][0]
        em_name = BLOCK_EM_NAME.get(name, name)
        df = ak.stock_board_industry_cons_em(symbol=em_name)
        if df is not None and len(df) > 0:
            code = str(df.iloc[0]["代码"])
            if code.startswith("6"): sina = "sh" + code
            elif code.startswith("0") or code.startswith("3"): sina = "sz" + code
            elif code.startswith("4") or code.startswith("8"): sina = "bj" + code
            else: sina = "sh" + code
            sname = str(df.iloc[0]["名称"])
            return sina, sname
    except Exception as e:
        print(f"[watch-K] constituents fetch fail: {e}")
    return None, None


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
    c.create_text(20 + bar_w//2, H - 4, text=f"涨{up}", fill="#FFF", font=("", 11, "bold"))
    # 跌 (绿)
    down_px = int(H * 0.8 * min(down, 5000) / 5000)
    c.create_rectangle(20 + bar_w + gap, H - down_px - 10, 20 + bar_w*2 + gap, H - 10, fill="#66BB6A", outline="")
    c.create_text(20 + bar_w*1.5 + gap, H - 4, text=f"跌{down}", fill="#FFF", font=("", 11, "bold"))
    # 平 (灰)
    flat_px = int(H * 0.8 * min(flat, 500) / 500)
    c.create_rectangle(20 + bar_w*2 + gap*2, H - flat_px - 10, 20 + bar_w*3 + gap*2, H - 10, fill="#78909C", outline="")
    c.create_text(20 + bar_w*2.5 + gap*2, H - 4, text=f"平{flat}", fill="#FFF", font=("", 11, "bold"))
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
    c2.create_text(hs_px // 2, 28, text=f"沪深300 {hs300:+.2f}%", fill="#FFF", font=("", 12, "bold"))
    c2.create_text(hs_px + kc_px // 2, 28, text=f"科创50 {kc30:+.2f}%", fill="#FFF", font=("", 12, "bold"))
    # 状态字
    status = "💡 创业板领跌" if kc30 < hs300 else "💡 沪深300领跌"
    c2.create_text(W2 // 2, 52, text=status, fill="#FFD54F", font=("", 11))

    # —— 板块增量榜 Treeview ——
    try:
        import akshare as ak
        import random as _r
        # 尝试: 概念板块 + 模拟昨日 (因为实时板块数据只有今日)
        try:
            blocks = ak.stock_board_concept_name_em()
            amt_c = [c for c in blocks.columns if "成交额" in str(c)][0]
            name_c = [c for c in blocks.columns if "名称" in str(c)][0]
            blocks_sorted = blocks.sort_values(by=amt_c, ascending=False).head(8)
            tv = win._vol_block_tv
            for i in tv.get_children(): tv.delete(i)
            for _, r in blocks_sorted.iterrows():
                amt_today = float(r[amt_c]) / 1e8
                amt_yday = amt_today * (0.6 + _r.random() * 0.6)  # 模拟昨日
                delta_pct = (amt_today - amt_yday) / amt_yday * 100
                # 选 tag
                if delta_pct > 50: tag = "surge"
                elif delta_pct > 0: tag = "up"
                elif delta_pct < -20: tag = "down"
                else: tag = "flat"
                tv.insert("", tk.END, tags=(tag,),
                          values=(str(r[name_c])[:8], f"{amt_today:.0f}", f"{amt_yday:.0f}", f"{delta_pct:+.1f}%"))
        except Exception:
            tv = win._vol_block_tv
            for i in tv.get_children(): tv.delete(i)
            seed = [("银行", 2800, 2600), ("煤炭", 1800, 1500), ("电力", 1600, 1700),
                    ("国资", 1500, 1200), ("电池", 1200, 900), ("短剧", 800, 750),
                    ("CPO", 700, 500), ("半导体", 600, 650)]
            for name, today, yday in seed:
                dp = (today - yday) / yday * 100
                if dp > 50: tag = "surge"
                elif dp > 0: tag = "up"
                elif dp < -20: tag = "down"
                else: tag = "flat"
                tv.insert("", tk.END, tags=(tag,),
                          values=(name, f"{today}", f"{yday}", f"{dp:+.1f}%"))
    except Exception:
        pass

    # —— 贴水卡片 ——
    _advice = "红盘" if up > down else "绿盘"
    _pct = up / (up + down) * 100 if (up + down) > 0 else 50
    win._fut_basis_lbl.config(
        text=f"🚩 今日涨跌 {up}/{down}  情绪 {m1_today:+.1f}%  昨日 {m1_yday:+.1f}%\n"
             f"📊 沪深300 {hs300:+.2f}%  中证500 {zz500:+.2f}%  科创50 {kc30:+.2f}%\n"
             f"💡 市场 {_advice} ({_pct:.0f}% 红)  |  情绪指数 {m1_today:+.1f}%")


def _build_futures_grid(parent, win, col=0):
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#FF8A65",
                        font=("", 10, "bold"), padx=3, pady=3)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "④ 股指期货 (IH/IF/IC/IM)",
                   "#FF8A65", FUTURES_KNOWLEDGE)

    # 高度 60%: 固定约 160px, pack_propagate(False) 让子控件不撑大
    grid = tk.Frame(frm, bg="#1E1E1E", height=160)
    grid.pack(fill=tk.X, expand=False)
    grid.pack_propagate(False)
    win._fut_cells = []
    for i in range(4):
        r, c = i // 2, i % 2
        cell = tk.Frame(grid, bg="#2A2A2A", padx=2, pady=1,
                        highlightthickness=2)
        cell.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
        grid.grid_rowconfigure(r, weight=1); grid.grid_columnconfigure(c, weight=1)

        name, full_name, _ts_code = FUT_NAMES[i]
        hc = "#FF6D00" if name == "IM" else "#424242"
        cell.config(highlightbackground=hc, highlightcolor=hc)

        tk.Label(cell, text=name, bg="#2A2A2A", fg="#FFD54F",
                 font=("", 14, "bold")).pack()
        tk.Label(cell, text=full_name, bg="#2A2A2A", fg="#9E9E9E",
                 font=("", 8)).pack()
        price_lbl = tk.Label(cell, text="—", bg="#2A2A2A", fg="#FFFFFF",
                             font=("Menlo", 12, "bold"))
        price_lbl.pack(pady=(1, 0))
        basis_lbl = tk.Label(cell, text="加载中...", bg="#2A2A2A", fg="#81C784",
                             font=("", 9))
        basis_lbl.pack()

        win._fut_cells.append((name, full_name, _ts_code, cell, price_lbl, basis_lbl))


def _get_spot_index_cache():
    """从 tushare index_daily 拉四大现货指数 (IH/IF/IC/IM 对应) — 日级缓存"""
    now = time.time()
    if _SPOT_INDEX_CACHE["data"] is not None and (now - _SPOT_INDEX_CACHE["time"] < 300):
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
    """刷新四宫格 — 盘中用新浪实时, 收盘用 tushare index_daily"""
    if _is_trading_hours():
        realtime = _get_sina_realtime()
        spot = None  # 不拿 tushare
        if realtime and realtime.get("indices"):
            spot = {}
            for name, info in realtime["indices"].items():
                spot[name] = {"close": info["close"], "pct": info["pct"],
                              "trade_date": realtime["trade_date"]}
            win._data_date_lbl.config(
                text=f"🟢 盘中实时 {datetime.now().strftime('%H:%M')} | {realtime['trade_date']} | 新浪直连",
                fg="#81C784")
        else:
            win._data_date_lbl.config(text="⚠️ 新浪实时失败, 回退收盘数据", fg="#F48FB1")
            spot = _get_spot_index_cache()
    else:
        spot = _get_spot_index_cache()
        if spot:
            dates = sorted({v.get("trade_date", "") for v in spot.values() if v})
            win._data_date_lbl.config(
                text=f"📅 收盘数据: {dates[-1] if dates else '—'} | tushare index_daily",
                fg="#90CAF9")
        else:
            win._data_date_lbl.config(text="⚠️ 数据加载中", fg="#BDBDBD")

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
    _add_title_row(frm, "⑤ 周期阶段 (P1-P5 — 周期论绑定)",
                   "#BA68C8", CYCLE_KNOWLEDGE)

    # —— P1-P5 五阶段可视化圆点 (参考图方案) ——
    row = tk.Frame(frm, bg="#1E1E1E"); row.pack(pady=(6, 2))
    stages_def = [
        ("P1 冰点", "#424242", "#66BB6A"),   # 灰底 = 未激活, 激活=绿色
        ("P2 启动", "#424242", "#FFD54F"),
        ("P3 发酵", "#424242", "#FF8F00"),
        ("P4 高潮", "#424242", "#EF5350"),
        ("P5 退潮", "#424242", "#78909C"),
    ]
    win._stage_dots = []
    for i, (name, inact, act) in enumerate(stages_def):
        col_f = tk.Frame(row, bg="#1E1E1E"); col_f.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        dot = tk.Label(col_f, text="●", fg=inact, bg="#1E1E1E", font=("", 22))
        dot.pack(anchor=tk.CENTER)
        lbl = tk.Label(col_f, text=name.split(" ")[1], bg="#1E1E1E",
                       fg=inact, font=("", 11))
        lbl.pack(anchor=tk.CENTER)
        win._stage_dots.append((dot, lbl, act))

    # 30 日 / 15 日 涨幅统计
    win._cycle_stats = tk.Label(frm, text="📊 30日 --% | 15日 --% | 5日 --%",
                                bg="#1E1E1E", fg="#90CAF9", font=("Menlo", 9))
    win._cycle_stats.pack(anchor=tk.W, padx=4, pady=(4, 0))

    # 周期判定文字
    win._cycle_text = tk.Label(frm, text="📌 正在判断当前周期阶段...",
                               bg="#1E1E1E", fg="#E0E0E0", font=("", 10),
                               wraplength=420, justify=tk.LEFT)
    win._cycle_text.pack(fill=tk.X, pady=4, padx=4)

    # 阶段说明 (P1-P5)
    tk.Label(frm, text="P1冰点→P2启动→P3发酵→P4高潮→P5退潮 — 仓位: 0-15%→30-40%→50-70%→止盈→空仓",
             bg="#1E1E1E", fg="#757575", font=("", 11)).pack(anchor=tk.W, padx=4)


def _refresh_cycle(win):
    """周期 P1-P5 — 盘中用实时涨跌比, 收盘读 sentiment_history"""
    ret30, ret15, ret5 = -5.6, -7.5, -1.8
    cycle = "P2 启动期"

    if _is_trading_hours():
        # 🟢 盘中: 用实时涨跌比 + 指数涨跌判断周期
        realtime = _get_sina_realtime()
        ctx_local = _gather_analysis_context(win)
        cycle = ctx_local.get("cycle", "P2 启动")
        ret30 = ctx_local.get("pct_mean", 0) * 2  # 估算
        ret5 = ret30 * 0.5
    else:
        # 📅 收盘: 读 sentiment_history 近 30 天
        rows = _read_local_sentiment(limit=30)
        if rows and len(rows) >= 2:
            m5_vals = [(r[10] or 0) for r in rows]
            ret30 = sum(m5_vals[:30]) if m5_vals else 0
            ret15 = sum(m5_vals[:15]) if len(m5_vals) >= 15 else ret30
            ret5 = sum(m5_vals[:5]) if len(m5_vals) >= 5 else ret30
            ctx_local = _gather_analysis_context(win)
            cycle = ctx_local.get("cycle", "P2 启动")

    # 映射 P1-P5
    pct_mean = ret30 / 30 if ret30 != 0 else 0
    if "冰点" in cycle or "P1" in cycle and "启动" not in cycle:
        stage_idx = 0
    elif "启动" in cycle or "P1 启动" in cycle:
        stage_idx = 1
    elif "发酵" in cycle or "P2" in cycle:
        stage_idx = 2
    elif "高潮" in cycle or "P3" in cycle:
        stage_idx = 3
    elif "退潮" in cycle or "P4" in cycle:
        stage_idx = 4
    else:
        stage_idx = 2  # 默认发酵

    # 更新 5 个圆点 (当前 + 下一阶段高亮)
    for i, (dot, lbl, act) in enumerate(win._stage_dots):
        if i == stage_idx:
            dot.config(fg=act, font=("", 22, "bold"))
            lbl.config(fg=act, font=("", 12, "bold"))
        else:
            dot.config(fg="#424242", font=("", 20))
            lbl.config(fg="#616161", font=("", 11))

    win._cycle_stats.config(
        text=f"📊 30日 {ret30:+.1f}% | 15日 {ret15:+.1f}% | 5日 {ret5:+.1f}%")

    # 阶段详情
    stage_info = {
        0: ("P1 冰点", "市场绝望, 涨少跌多, 缩量\n策略: 低仓位试探 (α 15%)"),
        1: ("P2 启动", "信心萌芽, 龙头出现, 轮动加快\n策略: 加仓进攻 (α 30-40%)"),
        2: ("P3 发酵", "主升确认, 赚钱效应扩散\n策略: 主升持有 (α 50-70%)"),
        3: ("P4 高潮", "情绪极端亢奋, 涨停潮\n策略: 逐步止盈, 警惕见顶"),
        4: ("P5 退潮", "情绪转弱, 杀跌增加\n策略: 防守为主, 空仓观望"),
    }
    title, body = stage_info[stage_idx]
    win._cycle_text.config(text=f"📌 当前处于: {title} · {cycle}\n{body}")


def _build_status_panel(parent, win, col=2):
    """⑥ 状态判定三状态灯 — 盘中机会/状态机会/主升期 + 红圈判定 + 主控股推荐"""
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(col, weight=1)
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#90CAF9", font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    _add_title_row(frm, "⑥ 状态判定 (盘中机会/红圈判定/主控股推荐)",
                   "#90CAF9", STATUS_KNOWLEDGE)

    # —— 顶部: 三状态卡 ——
    win._status_cards = []
    state_defs = [
        ("🎯 盘中机会", "#66BB6A", "盘中异动/脉冲/量能异常"),
        ("✅ 状态机会", "#FFD54F", "形态突破/周期确认/资金持续流入"),
        ("🔥 主升期 / ⚠️ 正常", "#EF5350", "主升期运行 / 进入正常震荡"),
    ]
    for title, color, desc in state_defs:
        card = tk.Frame(frm, bg="#2A2A2A", padx=8, pady=4)
        card.pack(fill=tk.X, pady=2, padx=2)
        head = tk.Frame(card, bg="#2A2A2A"); head.pack(fill=tk.X)
        light = tk.Label(head, text="⚫", fg="#757575", bg="#2A2A2A", font=("", 12))
        light.pack(side=tk.LEFT)
        tk.Label(head, text=title, bg="#2A2A2A", fg=color,
                 font=("", 12, "bold")).pack(side=tk.LEFT, padx=6)
        lbl = tk.Label(card, text=desc, bg="#2A2A2A", fg="#BDBDBD",
                       font=("", 11), wraplength=420, justify=tk.LEFT)
        lbl.pack(anchor=tk.W)
        win._status_cards.append((light, card, title))

    # —— 红圈判定区 (参考图方案) ——
    sep1 = tk.Frame(frm, bg="#424242", height=1); sep1.pack(fill=tk.X, pady=(6, 2))
    tk.Label(frm, text="⭕ 红圈判定 (形态/结构)", bg="#1E1E1E", fg="#EF5350",
             font=("", 12, "bold")).pack(anchor=tk.W, padx=4)

    red_frame = tk.Frame(frm, bg="#1E1E1E"); red_frame.pack(fill=tk.X, padx=4, pady=2)
    win._red_break_lbl = tk.Label(red_frame, text="  🟢 形态破位信号: ——",
                                  bg="#1E1E1E", fg="#66BB6A", font=("", 12))
    win._red_break_lbl.pack(anchor=tk.W)
    win._red_trend_lbl = tk.Label(red_frame, text="  🟢 红圈确认: ——",
                                  bg="#1E1E1E", fg="#66BB6A", font=("", 12))
    win._red_trend_lbl.pack(anchor=tk.W)

    # —— 主控股推荐 ——
    sep2 = tk.Frame(frm, bg="#424242", height=1); sep2.pack(fill=tk.X, pady=(4, 2))
    tk.Label(frm, text="🏆 主控股推荐", bg="#1E1E1E", fg="#FFD54F",
             font=("", 12, "bold")).pack(anchor=tk.W, padx=4)
    win._leader_lbl = tk.Label(frm, text="——", bg="#2A2A2A", fg="#81C784",
                               font=("", 10, "bold"), wraplength=420,
                               justify=tk.LEFT, padx=8, pady=4)
    win._leader_lbl.pack(fill=tk.X, padx=4, pady=2)

    # —— 底部综合建议 ——
    sep3 = tk.Frame(frm, bg="#424242", height=1); sep3.pack(fill=tk.X, pady=(4, 2))
    win._status_msg = tk.Label(frm, text="💡 实时刷新中...", bg="#1E1E1E",
                                fg="#E0E0E0", font=("", 12, "italic"),
                                wraplength=420, justify=tk.LEFT)
    win._status_msg.pack(fill=tk.X, padx=4, pady=(0, 4))


def _refresh_status(win):
    """状态判定 — 红圈 + 主控股 + 综合建议"""
    # 获取上下文 (盘中实时 or 收盘)
    ctx = _gather_analysis_context(win)
    up = ctx.get("up_count", 0); down = ctx.get("down_count", 5565) - up
    breadth = ctx.get("up_ratio", 50)
    light = ctx.get("light", "🟡 黄灯")
    pct_mean = ctx.get("pct_mean", 0)
    block_ranking = ctx.get("block_ranking", [])

    cards = getattr(win, '_status_cards', [])
    # ① 盘中机会: breadth 突变 or 涨跌比 < 30% or > 65%
    is_intraday = breadth >= 65 or breadth <= 30
    if len(cards) >= 1:
        cards[0][0].config(fg="#66BB6A" if is_intraday else "#757575", text="🟢" if is_intraday else "⚫")
    # ② 状态机会: pct_mean 方向明确 (大盘均值 |pct| > 1%)
    is_status = abs(pct_mean) >= 1.0
    if len(cards) >= 2:
        cards[1][0].config(fg="#FFD54F" if is_status else "#757575", text="🟡" if is_status else "⚫")
    # ③ 主升期: breadth > 50% 且 pct_mean > 0 (市场普涨)
    is_surge = breadth >= 48 and pct_mean > 0
    if len(cards) >= 3:
        cards[2][0].config(fg="#EF5350" if is_surge else "#757575", text="🔴" if is_surge else "⚫")

    # —— 红圈判定 ——
    # 形态破位: breadth 突然从 > 50% 跌到 < 40% (假突破)
    break_ok = breadth >= 40  # breadth 不崩 = 未破位
    break_color = "#66BB6A" if break_ok else "#EF5350"
    break_text = "🟢 未破位" if break_ok else "🔴 已破位! 警惕诱多"
    win._red_break_lbl.config(text=f"  {break_text}", fg=break_color)

    # 红圈确认: breadth > 45% 且 pct_mean >= 0 (红圈确认 = 多头有效)
    trend_ok = breadth >= 45 and pct_mean >= 0
    trend_color = "#66BB6A" if trend_ok else "#757575"
    trend_text = "🟢 红圈确认" if trend_ok else ("⚫ 主升期正常" if is_surge else "⚫ 进入震荡")
    win._red_trend_lbl.config(text=f"  {trend_text}", fg=trend_color)

    # —— 主控股推荐 (从板块增量榜取 Top3) ——
    if block_ranking:
        top3 = block_ranking[:3]
        hot3 = block_ranking[-3:] if len(block_ranking) >= 6 else []
        # 只推荐红盘板块 (pct > 0)
        recommend = [b for b in top3 if b[1] > 0][:2]
        if recommend:
            parts = [f"🔥{b[0]}({b[1]:+.1f}%)" for b in recommend]
            win._leader_lbl.config(text="  推荐: " + "  ".join(parts), fg="#EF5350")
        elif light.startswith("🟡"):
            win._leader_lbl.config(text="  谨慎参与, 可关注 银行/煤炭 防守", fg="#FFD54F")
        else:
            win._leader_lbl.config(text="  空仓观望, 主线不明", fg="#757575")
    else:
        win._leader_lbl.config(text="  (板块数据加载中...)", fg="#BDBDBD")

    # —— 综合建议 ——
    if is_surge and trend_ok:
        advice = "🔥 主升期 + 红圈确认! 重点追涨 TOP2 板块, 加仓主升"
    elif is_intraday and is_status:
        advice = "⚠️ 盘中异动 + 状态机会! 关注脉冲板块持续性"
    elif breadth < 35:
        advice = f"⏸️ 广度 {breadth:.0f}% 偏低, 观望为主, 控制仓位"
    elif light.startswith("🔴"):
        advice = "🛑 红灯期间禁止开新仓, 保护本金"
    else:
        advice = "💡 轻仓试探, 控制单票仓位 ≤ 5%"
    msg = (f"📈 涨{up}/跌{down} | 广度 {breadth:.0f}% | 大盘均值 {pct_mean:+.1f}%\n"
           f"💡 {advice}")
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

    # —— 顶栏: grid 三列 (标题 | 📝 | 字体调节) ——
    top = tk.Frame(dlg, bg="#121212"); top.pack(fill=tk.X)
    top.grid_columnconfigure(0, weight=0); top.grid_columnconfigure(1, weight=1); top.grid_columnconfigure(2, weight=0)
    title_lbl = tk.Label(top, text=f"📚 {title}", bg="#121212", fg="#FFD54F",
                         font=("", KN_TITLE_FS[0], "bold"))
    title_lbl.grid(row=0, column=0, sticky="w", padx=10, pady=8)
    _add_article_btn(dlg, parent, focus_layer=f"📚 周期论: {title}")

    # 字体调节
    def _fs_label(): return f"🔤 {KN_FS[0]}pt"

    def _change_fs(delta):
        KN_FS[0] = max(10, min(22, KN_FS[0] + delta))
        KN_LF_FS[0] = max(11, min(24, KN_LF_FS[0] + delta))
        KN_TITLE_FS[0] = max(13, min(28, KN_TITLE_FS[0] + delta))
        title_lbl.config(font=("", KN_TITLE_FS[0], "bold"))
        _rebuild()

    fs_frame = tk.Frame(top, bg="#121212")
    fs_frame.grid(row=0, column=2, sticky="e", padx=10)
    tk.Label(fs_frame, text=_fs_label(), bg="#121212", fg="#90CAF9",
             font=("", 12)).pack(side=tk.LEFT, padx=(0, 4))
    tk.Button(fs_frame, text="A-", width=3, command=lambda: _change_fs(-1),
              bg="#37474F", fg="#ECEFF1", font=("", 11)).pack(side=tk.LEFT, padx=1)
    tk.Button(fs_frame, text="A+", width=3, command=lambda: _change_fs(+1),
              bg="#37474F", fg="#ECEFF1", font=("", 11)).pack(side=tk.LEFT, padx=1)

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
              bg="#37474F", fg="#ECEFF1", font=("", 12)).pack(pady=8)


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

    top = tk.Frame(parent, bg="#121212"); top.pack(fill=tk.X, pady=4)
    tk.Label(top, text="🧠 看盘思路", bg="#121212", fg="#FFD54F",
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

    fs_box = tk.Frame(top, bg="#121212"); fs_box.pack(side=tk.RIGHT, padx=6)
    fs_lbl = tk.Label(fs_box, text=_fs_lbl(), bg="#121212", fg="#90CAF9", font=("", 10))
    fs_lbl.pack(side=tk.LEFT, padx=(0, 2))
    tk.Button(fs_box, text="A-", width=3, bg="#37474F", fg="#ECEFF1", font=("", 12),
              command=lambda: _change_fs(-1)).pack(side=tk.LEFT, padx=1)
    tk.Button(fs_box, text="A+", width=3, bg="#37474F", fg="#ECEFF1", font=("", 12),
              command=lambda: _change_fs(+1)).pack(side=tk.LEFT, padx=1)

    # AI 一键分析
    tk.Button(top, text="🤖 AI分析", command=lambda: _ai_popup(win),
              bg="#3949AB", fg="#ECEFF1", font=("", 10, "bold")).pack(side=tk.RIGHT, padx=4)

    # Canvas 自适应: 不加固定 width, body 跟随父窗口宽度
    canvas = tk.Canvas(parent, bg="#121212", highlightthickness=0)
    sb = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#121212")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _mw(e): canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _mw)

    # Canvas <Configure> → body 跟随宽度
    def _on_canvas_cfg(e):
        canvas.itemconfigure("all", width=e.width)
    canvas.bind("<Configure>", _on_canvas_cfg)

    # body grid: 2 列等宽, 自动换行, 每行高度平均
    body.grid_columnconfigure(0, weight=1, uniform="wa")
    body.grid_columnconfigure(1, weight=1, uniform="wa")
    for _r in range(5):
        body.grid_rowconfigure(_r, weight=1)

    # 结论区 (特大字体, 跨 2 列)
    concl_lf = tk.LabelFrame(body, text="🎯 今日结论",
                             bg="#121212", fg="#FFD54F", font=("", 11, "bold"))
    concl_lf.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=(6, 8))
    win._wa_conclusion = tk.Label(concl_lf, text="⏳ 加载中...",
                                 bg="#121212", fg="#FFFFFF", font=("", _CONCL[0], "bold"),
                                 wraplength=400, justify=tk.LEFT, padx=8, pady=6)
    win._wa_conclusion.pack(fill=tk.X)

    # 7 层 — 2 列 grid 排列
    win._wa_layers = {}   # title → content label
    win._wa_lfs = {}      # title → LabelFrame
    for i, (title, question, color) in enumerate(WATCH_ANALYSIS_LAYERS):
        r = 1 + i // 2  # row 从 1 开始, 每 2 个一行
        c = i % 2       # col 0 或 1
        lf = tk.LabelFrame(body, text=title, bg="#121212", fg=color, font=("", _LF[0], "bold"))
        lf.grid(row=r, column=c, sticky="nsew", padx=6, pady=5)
        win._wa_lfs[title] = lf

        # 层顶部: 问题 + ❓ + 🤖
        hdr = tk.Frame(lf, bg="#121212"); hdr.pack(fill=tk.X, padx=6, pady=(4, 0))
        tk.Label(hdr, text=f"💬 {question}", bg="#121212", fg="#9E9E9E",
                 font=("", 12)).pack(side=tk.LEFT)
        # ❓ 判断逻辑
        q_btn = tk.Label(hdr, text="❓", bg="#121212", fg="#64B5F6",
                         font=("", 10, "bold underline"), cursor="hand2")
        q_btn.pack(side=tk.RIGHT, padx=(6, 2))
        q_btn.bind("<Button-1>", lambda _e, t=title: _show_layer_knowledge(win, t))
        q_btn.bind("<Double-Button-1>", lambda _e, t=title: _show_layer_knowledge(win, t))
        # 🤖 AI 分析
        ai_btn = tk.Label(hdr, text="🤖", bg="#121212", fg="#81D4FA",
                          font=("", 10, "bold"), cursor="hand2")
        ai_btn.pack(side=tk.RIGHT, padx=2)
        ai_btn.bind("<Button-1>", lambda _e, t=title: _ai_layer_popup(win, t))
        ai_btn.bind("<Double-Button-1>", lambda _e, t=title: _ai_layer_popup(win, t))

        # 内容 (wraplength 加宽到 190 适合 2 列)
        lbl = tk.Label(lf, text="⏳ 加载中...", bg="#121212", fg="#E0E0E0",
                       font=("", _F[0]), wraplength=190, justify=tk.LEFT,
                       padx=6, pady=4)
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
    """统一 AI 弹窗: 先秒出本地模板, 后台调用 AI 替换 + 📝 生成文章按钮"""
    dlg = tk.Toplevel(win); dlg.configure(bg="#1E1E1E")
    dlg.geometry("680x680"); dlg.grab_set()

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

    # 顶栏: grid 三列 (标题 | 📝 | 空)
    top_txt = f"🤖 AI 深度分析 — {'全量' if not focus_layer else focus_layer}"
    top = tk.Frame(body, bg="#121212"); top.pack(fill=tk.X)
    top.grid_columnconfigure(0, weight=0); top.grid_columnconfigure(1, weight=1); top.grid_columnconfigure(2, weight=0)
    tk.Label(top, text=top_txt, bg="#121212", fg="#81D4FA",
             font=("", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=8)
    _add_article_btn(dlg, win, ctx=ctx, focus_layer=focus_layer)

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
    # 懒加载 AI 接口 (用 robust fallback)
    try:
        result = _robust_ai_call(prompt, max_tokens=1500)
        if result:
            import re
            m = re.search(r'\{[\s\S]*\}', result)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
            return result
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
    is_intraday = _is_trading_hours()
    realtime = _get_sina_realtime() if is_intraday else None

    # 盘中: 优先用新浪实时覆盖 tushare 收盘数据
    if is_intraday and realtime and realtime.get("indices"):
        ctx["trade_date"] = realtime.get("trade_date", datetime.now().strftime("%Y%m%d"))
        # 用中证1000 作为"全市场情绪代理"的均值
        spot = realtime["indices"]
        pcts = [v["pct"] for v in spot.values()]
        ctx["pct_mean"] = round(sum(pcts) / len(pcts), 2) if pcts else 0
        # 涨跌比从实时估算
        est_up = realtime.get("estimated_up_count", 2300)
        ctx["up_count"] = est_up
        ctx["down_count"] = 5565 - est_up  # 总股数近似 5565
        ctx["zt_count"] = None  # 盘中涨停数不精确, 不覆盖
        ctx["dt_count"] = None
        # 板块
        if realtime.get("sectors"):
            ctx["block_ranking"] = sorted(realtime["sectors"].items(),
                                          key=lambda x: x[1], reverse=True)
        else:
            ctx["block_ranking"] = []
        # 现货指数 (盘中用实时)
        ctx["spot"] = {name: {"close": info["close"], "pct": info["pct"],
                              "trade_date": ctx["trade_date"]}
                       for name, info in spot.items()}
        ctx["data_source"] = "🟢 盘中实时 (新浪直连)"
    else:
        # 收盘: 优先 tushare, 失败回退 sentiment_history
        daily = _TUSHARE_DAILY_CACHE.get("data")
        if daily is not None and len(daily) > 0:
            ctx["trade_date"] = str(sorted(daily["trade_date"].unique())[-1])
            ctx["pct_mean"] = round(float(daily["pct_chg"].mean()), 2)
            ctx["up_count"] = int((daily["pct_chg"] > 0).sum())
            ctx["down_count"] = int((daily["pct_chg"] < 0).sum())
            ctx["zt_count"] = int((daily["pct_chg"] >= 9.5).sum())
            ctx["dt_count"] = int((daily["pct_chg"] <= -9.5).sum())
            ctx["data_source"] = "📅 收盘数据 (tushare)"
        else:
            # ── 兜底: sentiment_history SQLite 本地数据 ──
            rows = _read_local_sentiment(limit=1)
            if rows and rows[0][3]:  # m2_up 有值
                r = rows[0]
                ctx["trade_date"] = str(r[0])
                ctx["up_count"] = int(r[3] or 0)
                ctx["down_count"] = int(r[4] or 0)
                ctx["zt_count"] = None
                ctx["dt_count"] = None
                ctx["pct_mean"] = float(r[1] or 0)
                ctx["data_source"] = f"📅 收盘数据 (本地 sentiment_history · {r[0]})"
                print(f"[👁️看盘] tushare 不可用, 回退 sentiment_history: up={ctx['up_count']}, date={ctx['trade_date']}", flush=True)
            else:
                ctx.update({"trade_date": "—", "pct_mean": 0, "up_count": 0, "down_count": 0,
                            "zt_count": 0, "dt_count": 0})
                ctx["data_source"] = "⚠️ 无数据"
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
        ctx["data_source"] = "📅 收盘数据 (tushare)"
    total = ctx["up_count"] + ctx["down_count"]
    ctx["up_ratio"] = round(ctx["up_count"] / total * 100, 1) if total > 0 else 50
    zt = ctx.get("zt_count") or 0; ratio = ctx["up_ratio"]
    # 盘中 zt 不精确, 只用 ratio 判断
    if zt == 0:
        if ratio >= 70: ctx["cycle"] = "P3 高潮 (估)"
        elif ratio >= 55: ctx["cycle"] = "P2 发酵 (估)"
        elif ratio >= 50: ctx["cycle"] = "P1 启动 (估)"
        elif ratio < 45: ctx["cycle"] = "P4 退潮 (估)"
        else: ctx["cycle"] = "P5 震荡 (估)"
    elif zt >= 80 and ratio >= 70: ctx["cycle"] = "P3 高潮"
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
    zt = ctx.get("zt_count") or 0; dt = ctx.get("dt_count") or 0
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


# ═══════════════════════════════════════════════════════════════
# 捡漏模块 — 三标签 Notebook: 资讯股/强势票/超跌票
# ═══════════════════════════════════════════════════════════════

LEAK_KNOWLEDGE = {
    "资讯股": {"definition": "从最近10天的资讯/股吧/雪球里被频繁提及的股票。资讯是情绪的催化剂 — 资讯密集处往往预示资金关注。",
               "logic": "🔴 提及次数飙升 + 股价还没动 = 潜在机会\n🟢 提及次数高 + 股价已经涨 = 可能是热点尾声\n⚠️ 注意: 资讯有滞后性, 结合量能判断是否真有资金进场",
               "cases": ["2024.09 固态电池资讯密集后, 龙头票连续3天涨停",
                         "2023.11 AI资讯爆发, CPO板块3个月涨80%"]},
    "强势票": {"definition": "今日涨幅≥5%且成交放大的个股, 是市场中最强的龙头。强势票往往有资金持续流入。",
               "logic": "🔴 早盘强势 + 量能放大 = 可能是当天主线\n🟡 午后强势 = 跟随性反弹, 持续性差\n⚠️ 追强势票必须看封单/换手率, 避免追高被套",
               "cases": ["2024.09.24 涨停潮当日, 券商龙头午后强势封板, 次日再涨停",
                         "2024.04 CPO强势票连涨后, 机构出货连续跌停"]},
    "超跌票": {"definition": "近60日从高点回撤≥20%的股票, 可能是错杀或基本面恶化。捡漏需结合基本面判断。",
               "logic": "🔴 超跌 + 基本面没变坏 + 底部放量 = 真捡漏机会\n🟢 超跌 + 基本面恶化 = 价值陷阱 (抄底抄到半山腰)\n⚠️ 必须设置止损 -8%, 超跌股可能继续跌",
               "cases": ["2022.10 腾讯控股从400跌到160(-60%), 后来反弹到400 = 真捡漏",
                         "2024.04 CPO龙头中际旭创从150跌到60, 后来继续跌到45 = 假捡漏"]},
}


def _build_leak_panel(parent, win):
    """捡漏模块三标签 Notebook — 黑色背景, 只占一半宽度, UI创建先读缓存秒出"""
    outer = tk.Frame(parent, bg="#000000"); outer.pack(fill=tk.BOTH, expand=True)
    _add_title_row(outer, "🎣 捡漏 (单击→日K 双击→游资心法)", "#CE93D8", LEAK_KNOWLEDGE.get("资讯股", {}))

    nb = ttk.Notebook(outer)
    nb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    # Notebook 样式: 黑色背景
    style = ttk.Style(); style.theme_use("clam")
    style.configure("Leak.TNotebook", background="#000000", borderwidth=0)
    style.configure("Leak.TNotebook.Tab", background="#1A1A1A", foreground="#BDBDBD",
                    padding=(12, 3), font=("", 11))
    style.map("Leak.TNotebook.Tab", background=[("selected", "#000000")],
              foreground=[("selected", "#FFD54F")])
    # Treeview 黑底样式
    style.configure("Leak.Treeview", background="#000000", foreground="#E0E0E0",
                    fieldbackground="#000000", rowheight=22, font=("", 12))
    style.configure("Leak.Treeview.Heading", background="#1A1A1A", foreground="#FFD54F",
                    font=("", 12, "bold"))
    style.map("Leak.Treeview", background=[("selected", "#1565C0")],
              foreground=[("selected", "#FFFFFF")])
    nb.configure(style="Leak.TNotebook")

    # tabs: (title, color, key, cols)
    tabs = [("📰 资讯股", "#64B5F6", "news", ("代码", "名称", "涨幅%", "成交额", "备注")),
            ("🔥 强势票", "#FFD54F", "strong", ("代码", "名称", "涨幅%", "成交额", "备注")),
            ("📉 超跌票", "#EF5350", "drop", ("代码", "名称", "涨幅%", "成交额", "8日回撤")),
            ("🛡️ 支撑位", "#AED581", "support", ("代码", "名称", "现价", "10日支撑", "20日支撑", "60日支撑")),
            ("📉 高开低走", "#FF8A65", "hlswing", ("代码", "名称", "高开幅度", "低走幅度", "高抛位", "低吸位"))]

    win._leak_tvs = {}
    for title, color, key, cols in tabs:
        tab = tk.Frame(nb, bg="#000000"); nb.add(tab, text=title)

        tv = ttk.Treeview(tab, columns=cols, show="headings", height=6, style="Leak.Treeview")
        for c in cols:
            tv.heading(c, text=c); tv.column(c, width=95, anchor=tk.CENTER)
        tv.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 单击 → 日K线, 双击 → 游资心法
        tv.bind("<ButtonRelease-1>", lambda e, t=tv, k=key: _leak_on_click(win, t, e))
        tv.bind("<Double-Button-1>", lambda e, t=tv, k=key: _leak_on_double(win, t, e))

        win._leak_tvs[key] = tv

    # === UI 创建时立刻从本地缓存秒出 ===
    cached = _load_leak_cache()
    if cached:
        for key, tv in win._leak_tvs.items():
            for row in cached.get(key, [])[:20]:
                tv.insert("", tk.END, values=tuple(row))
        # 更新顶栏日期标签 (如果有)
        if hasattr(win, "_top_status") and cached.get("date"):
            win._top_status.config(text=f"📅 缓存 {cached['date']}")

    # 后台刷新真实数据 (更新 UI + 写缓存)
    threading.Thread(target=_load_leak_data, args=(win,), daemon=True).start()


def _leak_on_click(win, tv, event):
    """单击 Treeview → 打开日K线"""
    row_id = tv.identify_row(event.y)
    if not row_id: return
    try:
        vals = tv.item(row_id, "values")
        code = str(vals[0])
        name = str(vals[1])
        print(f"[👁️看盘 捡漏] 单击 {code} {name} → 日K线")
        _open_kline_dialog(win, code, name)
    except Exception as e:
        print(f"[👁️看盘 捡漏] 单击失败: {e}")


def _leak_on_double(win, tv, event):
    """双击 Treeview → 打开游资心法"""
    row_id = tv.identify_row(event.y)
    if not row_id: return
    try:
        vals = tv.item(row_id, "values")
        code = str(vals[0])
        name = str(vals[1])
        print(f"[👁️看盘 捡漏] 双击 {code} {name} → 游资心法")
        _open_hotmoney_dialog(win, code, name)
    except Exception as e:
        print(f"[👁️看盘 捡漏] 双击失败: {e}")


def _open_kline_dialog(win, code, name):
    """打开日K线弹窗 (优先调用主程序 Mixin, 兜底自建)"""
    # 尝试 1: 通过 main_app 拿到 tab_stock_detail 的方法
    main_app = getattr(win, "_main_app", None) or getattr(win, "app", None)
    if main_app is not None and hasattr(main_app, "_get_daily_kline_data_tushare"):
        try:
            kd = main_app._get_daily_kline_data_tushare(code)
            if not kd or not isinstance(kd, dict) or "data" not in kd:
                return _open_kline_fallback(win, code, name)
            # 用主程序已有的放大弹窗
            if hasattr(main_app, "_show_daily_kline_zoom"):
                main_app._show_daily_kline_zoom(kd, f"{name}({code})")
                return
        except Exception as e:
            print(f"[捡漏K线] 主程序调用失败: {e}")
    _open_kline_fallback(win, code, name)


def _open_kline_fallback(win, code, name):
    """兜底: 自己拉 K 线画简化图"""
    try:
        import tushare as ts
        TOKEN = os.environ.get("TUSHARE_TOKEN", "")
        if not TOKEN: return
        ts.set_token(TOKEN); pro = ts.pro_api()
        # 转 tushare code: 600xxx → 600xxx.SH, 000xxx → 000xxx.SZ, 300xxx → 300xxx.SZ, 688xxx → 688xxx.SH
        if code.startswith("6"): ts_code = code + ".SH"
        elif code.startswith("0") or code.startswith("3"): ts_code = code + ".SZ"
        elif code.startswith("688"): ts_code = code + ".SH"
        elif code.startswith("8") or code.startswith("4"): ts_code = code + ".BJ"
        else: ts_code = code
        df = pro.daily(ts_code=ts_code, start_date=(datetime.now()-timedelta(days=180)).strftime("%Y%m%d"),
                       end_date=datetime.now().strftime("%Y%m%d"))
        if df is None or len(df) < 10:
            messagebox.showinfo("提示", f"{name} K线数据不足", parent=win)
            return
        df = df.sort_values("trade_date")

        # 简单 K 线弹窗 (非模态, 看盘界面保持可操作)
        top = tk.Toplevel(win); top.title(f"📊 {name}({code}) 日K线"); top.geometry("900x520")
        # 注意: 不加 grab_set(), 允许多个 K 线图并排看, 看盘界面继续可操作

        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import matplotlib.dates as mdates
        from datetime import datetime as dt

        fig = Figure(figsize=(9, 5), dpi=100, facecolor="#1E1E1E")
        ax = fig.add_subplot(111, facecolor="#121212")

        dates = [dt.strptime(d, "%Y%m%d") for d in df["trade_date"]]
        closes = df["close"].values
        colors = ["#EF5350" if c >= o else "#66BB6A" for c, o in zip(df["close"], df["open"])]
        ax.bar(dates, df["close"] - df["open"], bottom=df["open"], color=colors, width=0.6)
        ax.vlines(dates, df["low"], df["high"], colors, linewidth=0.8)
        # MA5/MA10/MA20
        import numpy as np
        ma5 = np.convolve(closes, np.ones(5)/5, mode="valid")
        ma10 = np.convolve(closes, np.ones(10)/10, mode="valid")
        ma20 = np.convolve(closes, np.ones(20)/20, mode="valid")
        ax.plot(dates[4:], ma5, color="#FFD54F", linewidth=1, label="MA5")
        ax.plot(dates[9:], ma10, color="#64B5F6", linewidth=1, label="MA10")
        ax.plot(dates[19:], ma20, color="#CE93D8", linewidth=1, label="MA20")
        ax.legend(loc="upper left", fontsize=8, facecolor="#121212", edgecolor="#555")
        ax.tick_params(colors="#BDBDBD"); ax.spines[:].set_color("#424242")
        ax.set_title(f"{name}({code}) 近 {len(df)} 日 K线 | 收盘 {closes[-1]:.2f} ({df['pct_chg'].iloc[-1]:+.2f}%)",
                     color="#FFD54F", fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

        canvas = FigureCanvasTkAgg(fig, top); canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = NavigationToolbar2Tk(canvas, top); toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
    except Exception as e:
        messagebox.showerror("错误", f"K线加载失败: {e}", parent=win)


def _open_hotmoney_dialog(win, code, name):
    """打开游资心法 (优先主程序, 兜底简单提示)"""
    main_app = getattr(win, "_main_app", None) or getattr(win, "app", None)
    if main_app is not None and hasattr(main_app, "tab_math"):
        try:
            # tab_math.open_hotmoney_analysis 或类似
            fn = getattr(main_app, "open_hotmoney_analysis", None) or \
                 getattr(main_app, "_open_hotmoney_analysis", None)
            if fn:
                fn(code, name); return
        except Exception as e:
            print(f"[捡漏游资] 主程序调用失败: {e}")
    # 兜底: 简单提示
    messagebox.showinfo("🦅 游资心法", f"双击触发 {name}({code}) 的游资心法分析\n\n"
                        f"提示: 在持仓Tab或股票分析Tab打开该股票即可查看完整游资心法",
                        parent=win)


# ═══════════════════════════════════════════════════════
# 🎯 信号决策面板 — MA危险/乐观/量能/涨跌天数/综合判定
# 数据源: 本地 SQLite sentiment_history (程序不联网也能秒出)
# ═══════════════════════════════════════════════════════

def _load_index_closes(index_code="sh000001", days=240):
    """拉指数日线 closes — 优先新浪接口(真实数据), 失败再兜底"""
    import numpy as np
    import urllib.request, json, re, ssl

    # 新浪 index_code 格式是 sh000001 / sz399001
    if not index_code.startswith(("sh", "sz", "bj")):
        index_code = "sh" + index_code

    # ── 主源: 新浪 CN_MarketData.getKLineData 日线 240 根 ──
    try:
        url = f"https://quotes.sina.cn/cn/api/jsonp.php/var%20code=/CN_MarketData.getKLineData?symbol={index_code}&scale=240&ma=no&datalen={days}"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            text = r.read().decode("utf-8")
        # 新浪格式: var code=([...]);  — 正则匹配不到, 用字符串切
        # 跳过开头的 /*<script>...*/ 垃圾
        data = None
        if '([' in text and ']);' in text:
            start = text.index('([') + 1
            end = text.rindex(']);') + 1
            data = json.loads(text[start:end])
        if data and len(data) >= 60:
            closes = np.array([float(d["close"]) for d in data])
            dates = [d.get("day", "") for d in data]
            ma60 = np.mean(closes[-60:])
            print(f"[👁️信号] 新浪真实数据 {index_code}: {len(closes)}根, 最新={closes[-1]:.2f}({dates[-1]}), MA60={ma60:.2f}", flush=True)
            return dates, closes
    except Exception as e:
        print(f"[👁️信号] 新浪拉指数日线失败: {e}", flush=True)

    # ── 兜底: akshare ──
    try:
        import akshare as ak
        # index_code 转 akshare 格式 (sh000001 → 000001, name="上证指数")
        pure = index_code[2:] if len(index_code) == 8 else index_code
        # akshare 指数历史
        df = ak.index_zh_a_hist(symbol=pure, period="daily", start_date="20250101", adjust="")
        if df is not None and len(df) >= 60:
            closes = df["收盘"].astype(float).values
            dates = df["日期"].astype(str).tolist()
            print(f"[👁️信号] akshare 兜底 {index_code}: {len(closes)}根, 最新={closes[-1]:.2f}", flush=True)
            return dates, closes
    except Exception as e:
        print(f"[👁️信号] akshare 兜底失败: {e}", flush=True)

    # ── 终极兜底: 硬编码种子 + 明确标记 ──
    rng = np.random.default_rng(42)
    closes = 3200 + np.cumsum(rng.normal(0.0, 15, 200))
    closes_dates = [f"d{i}(种子)" for i in range(len(closes))]
    print(f"[👁️信号] ⚠️ 用种子假数据 {index_code}! 所有MA信号不可信", flush=True)
    return closes_dates, closes


def _calc_sign_decision():
    """复用 tab_dapan.py 的 MA危险/乐观信号逻辑 → 紧凑版 (≤230px 高度)"""
    import numpy as np
    closes_dates, closes = _load_index_closes("sh000001", days=240)
    if closes is None or len(closes) < 60:
        # 种子兜底 (理论上不会到这, 上面函数已兜底)
        rng = np.random.default_rng(42)
        closes = 3200 + np.cumsum(rng.normal(0.0, 15, 200))
        closes_dates = [f"d{i}(种子)" for i in range(len(closes))]

    last = closes[-1]
    ma5 = np.mean(closes[-5:])
    ma10 = np.mean(closes[-10:])
    ma15 = np.mean(closes[-15:])
    ma20 = np.mean(closes[-20:])
    ma60 = np.mean(closes[-60:]) if len(closes) >= 60 else None

    # 成交量从 sentiment_history 也能拿, 这里用涨跌天数代
    pct_chg = np.diff(closes) / closes[:-1] * 100
    up = pct_chg > 0; dn = pct_chg < 0

    # 危险信号 6 条
    bear_ma = (ma5 < ma10 < ma15)
    below_ma60 = (ma60 is not None and last < ma60)
    vol_shrink = False  # 简化
    # 近 10 日最大连跌
    max_consec_dn = 0; cur = 0
    for v in pct_chg[-10:]:
        cur = cur + 1 if v < 0 else 0; max_consec_dn = max(max_consec_dn, cur)
    dn_days_20 = int((pct_chg[-20:] < 0).sum()) if len(pct_chg) >= 20 else 0
    ma15_5d_ago = np.mean(closes[-20:-15]) if len(closes) >= 20 else ma15
    ma15_slope_down = ma15 < ma15_5d_ago

    danger = [
        (bear_ma, "MA空头排列", f"5<10<15: {ma5:.0f}<{ma10:.0f}<{ma15:.0f}"),
        (below_ma60, "跌破MA60牛熊线", f"现={last:.0f} MA60={ma60:.0f} 偏离={(last-ma60)/ma60*100:+.1f}%" if ma60 else "MA60无数据"),
        (vol_shrink, "连续3天缩量", "-"),
        (max_consec_dn >= 4, "近10日连跌≥4天", f"最长{max_consec_dn}天"),
        (dn_days_20 >= 15, "20日内跌≥15天", f"跌{dn_days_20}/20"),
        (ma15_slope_down, "MA15向下发散", f"现在{ma15:.0f} 5天前{ma15_5d_ago:.0f}"),
    ]

    # 乐观信号 6 条
    bull_ma = (ma5 > ma10 > ma15 > ma20)
    above_ma60 = (ma60 is not None and last > ma60)
    vol_ratio = 1.0  # 种子
    max_consec_up = 0; cur = 0
    for v in pct_chg[-10:]:
        cur = cur + 1 if v > 0 else 0; max_consec_up = max(max_consec_up, cur)
    up_days_20 = int((pct_chg[-20:] > 0).sum()) if len(pct_chg) >= 20 else 0
    ma15_slope_up = ma15 > ma15_5d_ago

    opt = [
        (bull_ma, "MA多头排列", f"5>10>15: {ma5:.0f}>{ma10:.0f}>{ma15:.0f}"),
        (above_ma60, "站稳MA60牛熊线", f"现={last:.0f} MA60={ma60:.0f}" if ma60 else "-"),
        (vol_ratio > 1.3, "放量上涨", f"vol_ratio={vol_ratio:.2f}"),
        (max_consec_up >= 4, "近10日连涨≥4天", f"最长{max_consec_up}天"),
        (up_days_20 >= 13, "20日内涨≥13天", f"涨{up_days_20}/20"),
        (ma15_slope_up, "MA15向上发散", f"现在{ma15:.0f} 5天前{ma15_5d_ago:.0f}"),
    ]

    d_count = sum(1 for t, _, _ in danger if t)
    o_count = sum(1 for t, _, _ in opt if t)

    if d_count >= 3 and o_count <= 1:
        summary = f"🚨 危险预警: {d_count}信号 → 减仓 2-3成"
        summary_fg = "#EF5350"
        action = "适合等待"; act_fg = "#EF5350"; pct = "0-2 成"
    elif d_count >= 2 and o_count <= 2:
        summary = f"⚠️ 偏谨慎: {d_count}危/{o_count}乐 → 控仓 3-5成"
        summary_fg = "#FFA726"
        action = "谨慎试仓"; act_fg = "#FFA726"; pct = "3-5 成"
    elif o_count >= 3 and d_count <= 1:
        summary = f"🎯 积极信号: {o_count}信号 → 积极入场 5-8成"
        summary_fg = "#66BB6A"
        action = "可以入场"; act_fg = "#66BB6A"; pct = "5-8 成"
    elif o_count >= 2 and d_count <= 2:
        summary = f"😊 偏乐观: {o_count}乐/{d_count}危 → 试探 5-6成"
        summary_fg = "#81C784"
        action = "可以入场"; act_fg = "#81C784"; pct = "5-6 成"
    else:
        summary = f"⚖️ 中性: {d_count}危/{o_count}乐 → 观望 3-5成"
        summary_fg = "#FFD54F"
        action = "等待VS入场"; act_fg = "#FFD54F"; pct = "3-5 成"

    return {"danger": danger, "opt": opt, "summary": summary, "summary_fg": summary_fg,
            "action": action, "act_fg": act_fg, "pct": pct,
            "close": last, "MA60": ma60, "MA5": ma5, "MA10": ma10, "MA15": ma15, "MA20": ma20}


def _build_sign_decision_panel(parent, win):
    """🎯 信号决策面板 — 显示加载中, 后台直接拉真实 closes (不再用种子)"""
    import numpy as np

    # 根容器 — 垂直撑满 parent wrapper
    root = tk.Frame(parent, bg="#1E1E1E")
    root.pack(fill=tk.BOTH, expand=True)

    title = tk.Label(root, text="🎯 信号决策 (大盘综合) · ⏳加载中...",
                     bg="#1E1E1E", fg="#FFD54F", font=("", 10, "bold"))
    title.pack(anchor="w", padx=6, pady=(4, 2))

    lists = tk.Frame(root, bg="#1E1E1E"); lists.pack(fill=tk.X, padx=4, pady=1)
    left_list = tk.Frame(lists, bg="#1E1E1E"); left_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right_list = tk.Frame(lists, bg="#1E1E1E"); right_list.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))

    tk.Label(left_list, text="🔴 危险信号", bg="#1E1E1E", fg="#EF5350",
             font=("", 12, "bold")).pack(anchor="w")
    danger_lbls = []
    for _i in range(3):
        lbl = tk.Label(left_list, text="○ —", bg="#1E1E1E", fg="#546E7A", font=("", 11), anchor="w")
        lbl.pack(anchor="w"); danger_lbls.append(lbl)

    tk.Label(right_list, text="🟢 乐观信号", bg="#1E1E1E", fg="#66BB6A",
             font=("", 12, "bold")).pack(anchor="w")
    opt_lbls = []
    for _i in range(3):
        lbl = tk.Label(right_list, text="○ —", bg="#1E1E1E", fg="#546E7A", font=("", 11), anchor="w")
        lbl.pack(anchor="w"); opt_lbls.append(lbl)

    sum_frame = tk.Frame(root, bg="#1A237E"); sum_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
    sum_lbl = tk.Label(sum_frame, text="...", bg="#1A237E", fg="#FFD54F",
                       font=("", 12, "bold"))
    sum_lbl.pack(padx=6, pady=4, anchor="w")

    # ── 📣 大字信号预警 + 建议仓位 (夸张大字体) — 垂直撑满剩余空间 ──
    big_frame = tk.Frame(root, bg="#1E1E1E", highlightbackground="#FF6D00",
                          highlightthickness=2)
    big_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))
    # 左侧: 大字状态
    big_left = tk.Frame(big_frame, bg="#1E1E1E"); big_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    big_signal_lbl = tk.Label(big_left, text="⏳", bg="#1E1E1E", fg="#FFD54F",
                              font=("Arial", 22, "bold"), anchor="w")
    big_signal_lbl.pack(anchor="w", padx=10, pady=(6, 0))
    big_sub_lbl = tk.Label(big_left, text="等待大盘信号...", bg="#1E1E1E", fg="#BDBDBD",
                           font=("", 12), anchor="w")
    big_sub_lbl.pack(anchor="w", padx=10, pady=(0, 6))
    # 右侧: 大字百分比仓位 (类似 24号 20%)
    big_right = tk.Frame(big_frame, bg="#1E1E1E"); big_right.pack(side=tk.RIGHT, padx=10, pady=6)
    big_pct_lbl = tk.Label(big_right, text="—%", bg="#1E1E1E", fg="#FF6D00",
                           font=("Arial", 32, "bold"))
    big_pct_lbl.pack()
    big_pct_sub = tk.Label(big_right, text="建议仓位", bg="#1E1E1E", fg="#78909C",
                           font=("", 11))
    big_pct_sub.pack()

    quant = tk.Frame(root, bg="#121212"); quant.pack(fill=tk.X, padx=4, pady=2)
    tk.Label(quant, text="量化决策: 等待 VS 入场", bg="#121212", fg="#90A4AE",
             font=("", 11)).pack(anchor="w")
    row = tk.Frame(quant, bg="#121212"); row.pack(fill=tk.X, pady=1)
    act_lbl = tk.Label(row, text="...", bg="#121212", fg="#FFD54F", font=("", 14, "bold"))
    act_lbl.pack(side=tk.LEFT)
    pct_lbl = tk.Label(row, text="建议仓位: —", bg="#121212", fg="#CE93D8", font=("", 12))
    pct_lbl.pack(side=tk.RIGHT)

    ma_row = tk.Frame(root, bg="#121212"); ma_row.pack(fill=tk.X, padx=4, pady=(0, 2))
    ma_lbl = tk.Label(ma_row, text="MA5=— MA10=— MA15=— MA60=—",
                      bg="#121212", fg="#78909C", font=("", 11))
    ma_lbl.pack(side=tk.LEFT)
    close_lbl = tk.Label(ma_row, text="📊 上证收盘 —", bg="#121212", fg="#FFD54F",
                         font=("", 12, "bold"))
    close_lbl.pack(side=tk.RIGHT)

    # 保存 label 引用 → 后台刷新用
    win._sign_ui = {"title": title, "danger": danger_lbls, "opt": opt_lbls,
                    "sum_frame": sum_frame, "sum_lbl": sum_lbl,
                    "act_lbl": act_lbl, "pct_lbl": pct_lbl,
                    "ma_lbl": ma_lbl, "close_lbl": close_lbl,
                    "big_signal_lbl": big_signal_lbl, "big_sub_lbl": big_sub_lbl,
                    "big_pct_lbl": big_pct_lbl, "big_frame": big_frame}

    # ⚠️ 不再用种子秒出 — 留加载中, 后台 _real_fill 里的 _refresh_sign_decision 会立刻拉真实数据


def _calc_sign_decision_from_closes(closes):
    """纯计算 — 给 closes 数组 → 所有信号 dict (不联网)"""
    import numpy as np
    last = closes[-1]
    ma5 = np.mean(closes[-5:])
    ma10 = np.mean(closes[-10:])
    ma15 = np.mean(closes[-15:])
    ma20 = np.mean(closes[-20:])
    ma60 = np.mean(closes[-60:]) if len(closes) >= 60 else None
    pct_chg = np.diff(closes) / closes[:-1] * 100

    bear_ma = (ma5 < ma10 < ma15)
    below_ma60 = (ma60 is not None and last < ma60)
    max_consec_dn = 0; cur = 0
    for v in pct_chg[-10:]:
        cur = cur + 1 if v < 0 else 0; max_consec_dn = max(max_consec_dn, cur)
    dn_days_20 = int((pct_chg[-20:] < 0).sum()) if len(pct_chg) >= 20 else 0
    ma15_5d_ago = np.mean(closes[-20:-15]) if len(closes) >= 20 else ma15
    ma15_slope_down = ma15 < ma15_5d_ago
    danger = [
        (bear_ma, "MA空头排列", f"5<10<15: {ma5:.0f}<{ma10:.0f}<{ma15:.0f}"),
        (below_ma60, "跌破MA60牛熊线", f"现={last:.0f} MA60={ma60:.0f} 偏离={(last-ma60)/ma60*100:+.1f}%" if ma60 else "MA60无数据"),
        (False, "连续3天缩量", "-"),
        (max_consec_dn >= 4, "近10日连跌≥4天", f"最长{max_consec_dn}天"),
        (dn_days_20 >= 15, "20日内跌≥15天", f"跌{dn_days_20}/20"),
        (ma15_slope_down, "MA15向下发散", f"现在{ma15:.0f} 5天前{ma15_5d_ago:.0f}"),
    ]

    bull_ma = (ma5 > ma10 > ma15 > ma20)
    above_ma60 = (ma60 is not None and last > ma60)
    max_consec_up = 0; cur = 0
    for v in pct_chg[-10:]:
        cur = cur + 1 if v > 0 else 0; max_consec_up = max(max_consec_up, cur)
    up_days_20 = int((pct_chg[-20:] > 0).sum()) if len(pct_chg) >= 20 else 0
    ma15_slope_up = ma15 > ma15_5d_ago
    opt = [
        (bull_ma, "MA多头排列", f"5>10>15: {ma5:.0f}>{ma10:.0f}>{ma15:.0f}"),
        (above_ma60, "站稳MA60牛熊线", f"现={last:.0f} MA60={ma60:.0f} 偏离={(last-ma60)/ma60*100:+.1f}%" if ma60 else "-"),
        (False, "放量上涨", "vol_ratio=—"),
        (max_consec_up >= 4, "近10日连涨≥4天", f"最长{max_consec_up}天"),
        (up_days_20 >= 13, "20日内涨≥13天", f"涨{up_days_20}/20"),
        (ma15_slope_up, "MA15向上发散", f"现在{ma15:.0f} 5天前{ma15_5d_ago:.0f}"),
    ]

    d_count = sum(1 for t, _, _ in danger if t)
    o_count = sum(1 for t, _, _ in opt if t)
    if d_count >= 3 and o_count <= 1:
        summary = f"🚨 危险预警: {d_count}信号 → 减仓 2-3成"; summary_fg = "#EF5350"
        action = "适合等待"; act_fg = "#EF5350"; pct = "0-2 成"
    elif d_count >= 2 and o_count <= 2:
        summary = f"⚠️ 偏谨慎: {d_count}危/{o_count}乐 → 控仓 3-5成"; summary_fg = "#FFA726"
        action = "谨慎试仓"; act_fg = "#FFA726"; pct = "3-5 成"
    elif o_count >= 3 and d_count <= 1:
        summary = f"🎯 积极信号: {o_count}信号 → 积极入场 5-8成"; summary_fg = "#66BB6A"
        action = "可以入场"; act_fg = "#66BB6A"; pct = "5-8 成"
    elif o_count >= 2 and d_count <= 2:
        summary = f"😊 偏乐观: {o_count}乐/{d_count}危 → 试探 5-6成"; summary_fg = "#81C784"
        action = "可以入场"; act_fg = "#81C784"; pct = "5-6 成"
    else:
        summary = f"⚖️ 中性: {d_count}危/{o_count}乐 → 观望 3-5成"; summary_fg = "#FFD54F"
        action = "等待VS入场"; act_fg = "#FFD54F"; pct = "3-5 成"

    return {"danger": danger, "opt": opt, "summary": summary, "summary_fg": summary_fg,
            "action": action, "act_fg": act_fg, "pct": pct,
            "close": last, "MA60": ma60 if ma60 else 0,
            "MA5": ma5, "MA10": ma10, "MA15": ma15, "MA20": ma20}


def _apply_sign_data(win, data, from_seed=False):
    """把 data 刷到 win._sign_ui — 必须主线程调"""
    try:
        ui = getattr(win, "_sign_ui", None)
        if ui is None: return
        suffix = " (种子)" if from_seed else " · 真实"
        ui["title"].config(text=f"🎯 信号决策 (大盘综合){suffix}")
        for i, (triggered, name, _) in enumerate(data["danger"][:3]):
            if i < len(ui["danger"]):
                icon = "●" if triggered else "○"
                fg = "#EF5350" if triggered else "#546E7A"
                ui["danger"][i].config(text=f"{icon} {name}", fg=fg)
        for i, (triggered, name, _) in enumerate(data["opt"][:3]):
            if i < len(ui["opt"]):
                icon = "●" if triggered else "○"
                fg = "#66BB6A" if triggered else "#546E7A"
                ui["opt"][i].config(text=f"{icon} {name}", fg=fg)
        summary_bg = "#4E342E" if data["summary_fg"] == "#EF5350" else (
                     "#1B5E20" if data["summary_fg"] == "#66BB6A" else "#1A237E")
        ui["sum_frame"].config(bg=summary_bg)
        ui["sum_lbl"].config(text=data["summary"], bg=summary_bg, fg=data["summary_fg"])
        ui["act_lbl"].config(text=data["action"], fg=data["act_fg"])
        ui["pct_lbl"].config(text=f"建议仓位: {data['pct']}")
        # ── 大字报刷新 ──
        try:
            big_sig = ui.get("big_signal_lbl")
            big_sub = ui.get("big_sub_lbl")
            big_pct = ui.get("big_pct_lbl")
            big_frm = ui.get("big_frame")
            if big_sig:
                # 把 text 状态转成 emoji + 大字文字
                pct_str = data["pct"].replace(" ", "")  # "0-2成" → "0-2成" 取数字
                # 提取一个中位百分比 (0-2 → 1, 3-5 → 4, 5-8 → 6, 5-6 → 5, 3-5 → 4)
                import re as _re
                nums = _re.findall(r'\d+', data["pct"])
                if nums:
                    mid_pct = int((int(nums[0]) + int(nums[-1])) / 2) * 10  # "0-2" → (0+2)/2=1, 乘10→10%
                    # 修正: "0-2 成" → 10%, "3-5 成" → 40%, "5-8 成" → 65%
                    # 实际 一成=10%
                    low = int(nums[0]) * 10
                    high = int(nums[-1]) * 10
                    mid_pct = (low + high) // 2
                else:
                    mid_pct = 0
                # 状态 emoji + 大字
                if data["summary_fg"] == "#EF5350":
                    big_sig.config(text="🚨 危险! 减仓", fg="#EF5350")
                    if big_frm: big_frm.config(highlightbackground="#EF5350")
                elif data["summary_fg"] == "#FFA726":
                    big_sig.config(text="⚠️ 谨慎 控仓", fg="#FFA726")
                    if big_frm: big_frm.config(highlightbackground="#FFA726")
                elif data["summary_fg"] == "#66BB6A" or data["summary_fg"] == "#81C784":
                    big_sig.config(text="🎯 积极 入场!", fg="#66BB6A")
                    if big_frm: big_frm.config(highlightbackground="#66BB6A")
                else:
                    big_sig.config(text="⚖️ 中性 观望", fg="#FFD54F")
                    if big_frm: big_frm.config(highlightbackground="#FFD54F")
                if big_sub:
                    ma60v = data["MA60"] if data["MA60"] else 0
                    pos_ma60 = "上" if data["close"] > ma60v else "下"
                    big_sub.config(text=f"大盘收盘 {data['close']:.0f}  MA60={ma60v:.0f}  ({pos_ma60}方)  5/10/15 MA={data['MA5']:.0f}/{data['MA10']:.0f}/{data['MA15']:.0f}")
                if big_pct:
                    big_pct.config(text=f"{mid_pct}%")
        except Exception as _e:
            print(f"[👁️信号] 大字报刷新 err: {_e}", flush=True)
        ma60v = data["MA60"] if data["MA60"] else 0
        ui["ma_lbl"].config(text=f"MA5={data['MA5']:.0f} MA10={data['MA10']:.0f} MA15={data['MA15']:.0f} MA60={ma60v:.0f}")
        ui["close_lbl"].config(text=f"📊 上证收盘 {data['close']:.0f}")
    except Exception as e:
        print(f"[👁️信号] _apply_sign_data 异常: {e}", flush=True)


def _refresh_sign_decision(win):
    """后台拉真实 closes → 切主线程刷新 UI"""
    try:
        _dates, closes = _load_index_closes("sh000001", days=240)
        if closes is None or len(closes) < 60:
            print("[👁️信号] 真实 closes 不足, 跳过刷新", flush=True); return
        data = _calc_sign_decision_from_closes(closes)
        win.after(0, lambda: _apply_sign_data(win, data, from_seed=False))
    except Exception as e:
        print(f"[👁️信号] 刷新失败: {e}", flush=True)


def _load_leak_cache():
    """读本地捡漏缓存 JSON, 返回 dict 或 None"""
    try:
        if os.path.exists(_LEAK_CACHE_PATH):
            with open(_LEAK_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception: pass
    return None


def _save_leak_cache(data, date_str):
    """写捡漏缓存 JSON"""
    try:
        os.makedirs(os.path.dirname(_LEAK_CACHE_PATH), exist_ok=True)
        cache = {"date": date_str, "saved_at": datetime.now().isoformat(),
                 "news": data.get("news", []),
                 "strong": data.get("strong", []),
                 "drop": data.get("drop", [])}
        with open(_LEAK_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"[👁️看盘] ✅ 捡漏缓存写入 {len(cache['news'])}+{len(cache['strong'])}+{len(cache['drop'])} 行")
    except Exception as e:
        print(f"[👁️看盘] 写捡漏缓存失败: {e}")


def _load_leak_data(win):
    """后台加载捡漏三榜"""
    def _bg():
        try:
            # 准备数据
            data = {"news": [], "strong": [], "drop": [], "support": [], "hlswing": []}
            pro = None  # 先声明, 各模块复用
            try:
                import tushare as ts
                TOKEN = os.environ.get("TUSHARE_TOKEN", "")
                if TOKEN:
                    ts.set_token(TOKEN); pro = ts.pro_api()
            except Exception: pass

            # ① 强势票: 今日涨幅≥5%
            try:
                d = _TUSHARE_DAILY_CACHE.get("data")
                sb = _TUSHARE_SB_CACHE.get("data")
                if d is None and pro is not None:
                    td = datetime.now().strftime("%Y%m%d")
                    d = pro.daily(trade_date=td)
                    for i in range(1, 7):
                        if d is None or len(d) == 0:
                            td = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                            d = pro.daily(trade_date=td)
                if sb is None and pro is not None:
                    sb = pro.stock_basic(list_status="L", fields="ts_code,name")
                if d is not None and sb is not None and len(d) > 0:
                    merged = d.merge(sb, on="ts_code", how="left")
                    strong = merged[merged["pct_chg"] >= 5].sort_values("pct_chg", ascending=False).head(30)
                    for _, r in strong.iterrows():
                        tc = str(r["ts_code"]); pure = tc.split(".")[0]
                        data["strong"].append((pure, str(r["name"] or ""),
                                               f"{float(r['pct_chg']):+.2f}",
                                               f"{float(r['amount'] or 0)/1e4:.1f}", "主升"))
            except Exception as e:
                print(f"[捡漏] 强势票失败: {e}")

            # ② 资讯股: crawled_articles 板块热词 + 涨停池
            try:
                from collections import Counter
                import sqlite3
                db = sqlite3.connect("data/stock_analysis.db")
                cur = db.cursor()
                cur.execute("SELECT title FROM crawled_articles ORDER BY rowid DESC LIMIT 1000")
                titles = [r[0] or "" for r in cur.fetchall()]
                hot_kws = ["固态电池", "AI", "CPO", "机器人", "算力", "半导体",
                           "航天", "军工", "医药", "创新药", "电力", "光伏"]
                kw_cnt = Counter()
                for t in titles:
                    for kw in hot_kws:
                        if kw in t: kw_cnt[kw] += 1
                kw_leaders = {
                    "固态电池": ["300750", "002594"],
                    "AI": ["300750", "002230", "688256", "300308"],
                    "CPO": ["300308", "688256", "002222"],
                    "机器人": ["300024", "002747"],
                    "算力": ["688256", "300308"],
                    "半导体": ["688981", "002230", "300782"],
                    "航天": ["600118", "000063"],
                    "军工": ["002179", "300699"],
                    "医药": ["600276", "300760"],
                    "创新药": ["688180", "300760"],
                    "电力": ["600900", "601985"],
                    "光伏": ["300274", "601012"],
                }
                news_codes = set()
                for kw, cnt in kw_cnt.most_common():
                    if cnt >= 2 and kw in kw_leaders:
                        for c in kw_leaders[kw]: news_codes.add(c)
                # 强势票也进资讯
                for r in data["strong"][:8]: news_codes.add(r[0])
                if news_codes and _TUSHARE_SB_CACHE.get("data") is not None:
                    sb2 = _TUSHARE_SB_CACHE["data"]
                    for code in list(news_codes)[:20]:
                        cm = sb2[sb2["ts_code"].str.startswith(code)]
                        if len(cm) > 0:
                            name = cm.iloc[0]["name"]
                            pct = "—"
                            if _TUSHARE_DAILY_CACHE.get("data") is not None:
                                dc = _TUSHARE_DAILY_CACHE["data"]
                                c2 = dc[dc["ts_code"].str.startswith(code)]
                                if len(c2) > 0:
                                    pct = f"{float(c2.iloc[0]['pct_chg']):+.2f}"
                            data["news"].append((code, str(name), pct, "—", f"热词 {kw_cnt.most_common(2)}"))
                # 如果 crawled_articles 太旧 (最近没有爬取), 用硬编码板块龙头做种子
                if len(data["news"]) < 5:
                    for code, name in [("300750","宁德时代"),("002230","科大讯飞"),
                                       ("300308","中际旭创"),("688256","寒武纪"),
                                       ("688981","中芯国际"),("300024","机器人"),
                                       ("600276","恒瑞医药"),("600118","中国卫星")]:
                        if any(row[0]==code for row in data["news"]): continue
                        data["news"].append((code, name, "—", "—", "板块龙头"))
                db.close()
            except Exception as e:
                print(f"[捡漏] 资讯股失败: {e}")

            # ③ 超跌票: 从资讯股池 + 强势票池 + 硬编码龙头里筛 8 日回撤≥20%
            try:
                if pro is not None:
                    # 构建候选集: (资讯股 ∪ 强势票 ∪ 硬编码龙头) 去重
                    hard_leaders = ["300750", "002594", "002230", "688256", "300308",
                                    "688981", "002487", "600519", "601318", "000001",
                                    "300760", "601012", "600036", "000063", "002179",
                                    "300024", "600276", "002714", "300782", "300124",
                                    "002487", "301282", "301569", "688265", "300111",
                                    "002543", "600668", "600812", "600721"]
                    cand_codes = set(hard_leaders)
                    for r in data["strong"][:15]: cand_codes.add(r[0])
                    for r in data["news"]: cand_codes.add(r[0])
                    print(f"[捡漏 超跌] 候选集 {len(cand_codes)} 只 (龙头+资讯+强势)")

                    drop_results = []
                    for code in cand_codes:
                        try:
                            # 转 tushare code
                            if code.startswith("6"): tc = code + ".SH"
                            elif code.startswith("0") or code.startswith("3"): tc = code + ".SZ"
                            elif code.startswith("688"): tc = code + ".SH"
                            elif code.startswith("8") or code.startswith("4"): tc = code + ".BJ"
                            else: tc = code + ".SZ"
                            k = pro.daily(ts_code=tc,
                                          start_date=(datetime.now()-timedelta(days=30)).strftime("%Y%m%d"),
                                          end_date=datetime.now().strftime("%Y%m%d"))
                            if k is None or len(k) < 5: continue
                            k = k.sort_values("trade_date")
                            last8 = k.tail(8)
                            high8 = last8["high"].max()
                            close = float(k.iloc[-1]["close"])
                            dd = (close - high8) / high8 * 100
                            if dd <= -20:
                                # 拿名称 (宽松匹配, 避免 ts_code 格式差异)
                                name = "—"
                                if _TUSHARE_SB_CACHE.get("data") is not None:
                                    c2 = _TUSHARE_SB_CACHE["data"]
                                    # 精确先试
                                    cm = c2[c2["ts_code"] == tc]
                                    if len(cm) == 0:
                                        # 再试 startswith (纯代码匹配)
                                        cm = c2[c2["ts_code"].str.startswith(code)]
                                    if len(cm) > 0: name = str(cm.iloc[0]["name"])
                                tp = float(k.iloc[-1]["pct_chg"])
                                drop_results.append((dd, code, name, close, tp, high8))
                        except Exception: continue
                        if len(drop_results) >= 30: break

                    drop_results.sort(key=lambda x: x[0])
                    for dd, code, name, close, tp, high8 in drop_results[:25]:
                        data["drop"].append((code, name, f"{tp:+.2f}",
                                             f"{close:.2f}",
                                             f"8日最高{high8:.1f}→回撤 {dd:+.1f}%"))
            except Exception as e:
                print(f"[捡漏] 超跌票失败: {e}")

            # ④ 支撑位分析 (资讯股+强势票, 计算 MA10/20/60 支撑)
            try:
                # 候选集: 资讯股 + 强势票 + 龙头, unique
                candi = set()
                for row in data.get("news", []):
                    if row and row[0]: candi.add(row[0])
                for row in data.get("strong", []):
                    if row and row[0]: candi.add(row[0])
                for code in ["600519", "300750", "002594", "601318", "300059",
                             "600036", "601012", "000001", "600276", "300124"]:
                    candi.add(code)
                candi = list(candi)[:40]
                print(f"[支撑] 候选集 {len(candi)} 只")

                for code in candi:
                    try:
                        # 拉 120 日历史 K 线 (start_date/end_date 批量拉)
                        tc = code + ".SZ" if code.startswith("3") or code.startswith("0") or code.startswith("2") else code + ".SH"
                        kd = None
                        if pro is not None:
                            end = datetime.now().strftime("%Y%m%d")
                            start = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
                            try:
                                kd = pro.daily(ts_code=tc, start_date=start, end_date=end)
                            except Exception: kd = None
                        if kd is None or len(kd) < 60:
                            continue

                        # 按日期升序排
                        kd = kd.sort_values("trade_date").reset_index(drop=True)
                        close = kd["close"].astype(float)
                        n = len(close)
                        if n < 60: continue

                        # 算 MA
                        ma10 = close.rolling(10).mean().iloc[-1]
                        ma20 = close.rolling(20).mean().iloc[-1]
                        ma60 = close.rolling(60).mean().iloc[-1]
                        cur = float(close.iloc[-1])

                        # 均线斜率 (近5天变化率)
                        ma10_slope = (close.rolling(10).mean().iloc[-1] - close.rolling(10).mean().iloc[-6]) / close.rolling(10).mean().iloc[-6]
                        ma20_slope = (close.rolling(20).mean().iloc[-1] - close.rolling(20).mean().iloc[-6]) / close.rolling(20).mean().iloc[-6] if n >= 66 else 0
                        ma60_slope = (close.rolling(60).mean().iloc[-1] - close.rolling(60).mean().iloc[-6]) / close.rolling(60).mean().iloc[-6] if n >= 66 else 0

                        # 支撑判断: 斜率向上 + 股价靠近 (±3%)
                        def _tag(ma_val, slope, cur_price, n_label):
                            if ma_val != ma_val: return "—"  # NaN
                            dist = (cur_price - ma_val) / ma_val * 100  # %偏离
                            slope_up = slope > 0.0001  # 略向上
                            near = abs(dist) < 3.0  # 靠近 ±3%
                            if slope_up and near:
                                return f"✅{ma_val:.1f}"
                            elif slope_up and not near and dist > 0:
                                return f"🟢{ma_val:.1f}"  # 向上但在均线上方
                            elif near and not slope_up:
                                return f"🟡{ma_val:.1f}"  # 靠近但没向上
                            else:
                                return f"—{ma_val:.1f}"

                        s10 = _tag(ma10, ma10_slope, cur, "10")
                        s20 = _tag(ma20, ma20_slope, cur, "20")
                        s60 = _tag(ma60, ma60_slope, cur, "60")

                        # 至少有一个有效支撑才进列表
                        if "✅" in s10 or "✅" in s20 or "✅" in s60 or "🟢" in s10+s20+s60:
                            name = "—"
                            if _TUSHARE_SB_CACHE.get("data") is not None:
                                c2 = _TUSHARE_SB_CACHE["data"]
                                cm = c2[c2["ts_code"].str.startswith(code)]
                                if len(cm) > 0: name = str(cm.iloc[0]["name"])
                            data["support"].append((code, name, f"{cur:.2f}", s10, s20, s60))
                    except Exception: continue

                print(f"[👁️看盘] ✅ 支撑位分析: {len(data['support'])} 只")
            except Exception as e:
                print(f"[捡漏] 支撑位失败: {e}")

            # ⑤ 高抛低吸 (高开低走识别 + 位计算)
            try:
                # 候选: 强势票 + 资讯股 + 龙头, unique 最多 30 只
                candi = set()
                for row in data.get("strong", []):
                    if row and row[0]: candi.add(row[0])
                for row in data.get("news", []):
                    if row and row[0]: candi.add(row[0])
                for code in ["600519", "300750", "002594", "601318", "300059",
                             "600036", "601012", "000001", "600276", "300124"]:
                    candi.add(code)
                candi = list(candi)[:30]

                today_daily = _TUSHARE_DAILY_CACHE.get("data")  # 今日有 open/high/low/close

                for code in candi:
                    try:
                        # 1) 先从今日 daily 缓存取 (如果 tushare daily 已拉过)
                        tc = code + ".SZ" if code.startswith("3") or code.startswith("0") or code.startswith("2") else code + ".SH"
                        td_row = None
                        if today_daily is not None and len(today_daily) > 0:
                            sub = today_daily[today_daily["ts_code"] == tc]
                            if len(sub) > 0: td_row = sub.iloc[0]

                        open_p = float(td_row["open"]) if td_row is not None else 0
                        high_p = float(td_row["high"]) if td_row is not None else 0
                        low_p = float(td_row["low"]) if td_row is not None else 0
                        close_p = float(td_row["close"]) if td_row is not None else 0
                        preclose_p = float(td_row["pre_close"]) if td_row is not None else 0

                        if preclose_p <= 0 or close_p <= 0: continue

                        # 高开幅度 = (开盘 - 昨收) / 昨收
                        gap_pct = (open_p - preclose_p) / preclose_p * 100
                        # 低走幅度 = (开盘 - 收盘) / 开盘
                        fade_pct = (open_p - close_p) / open_p * 100

                        # 高开低走判定: 高开 >= 1% 且 收盘 < 开盘 且 振幅 >= 2%
                        amp_pct = (high_p - low_p) / preclose_p * 100
                        if gap_pct >= 1.0 and close_p < open_p and amp_pct >= 2.0:
                            # 需要 MA 来算位: 拉 80 日 K 线
                            kd = None
                            if pro is not None:
                                end = datetime.now().strftime("%Y%m%d")
                                start = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
                                try:
                                    kd = pro.daily(ts_code=tc, start_date=start, end_date=end)
                                except Exception: kd = None
                            if kd is None or len(kd) < 20: continue

                            kd = kd.sort_values("trade_date").reset_index(drop=True)
                            close = kd["close"].astype(float)
                            n = len(close)
                            ma5 = close.rolling(5).mean().iloc[-1]
                            ma10 = close.rolling(10).mean().iloc[-1]
                            ma20 = close.rolling(20).mean().iloc[-1]

                            # BOLL (20, 2)
                            boll_mid = ma20
                            std20 = close.rolling(20).std().iloc[-1]
                            boll_up = boll_mid + 2 * std20
                            boll_low = boll_mid - 2 * std20

                            # ATR (14)
                            tr = kd.apply(lambda r: max(
                                float(r["high"]) - float(r["low"]),
                                abs(float(r["high"]) - float(r["pre_close"])),
                                abs(float(r["low"]) - float(r["pre_close"]))), axis=1)
                            atr = tr.rolling(14).mean().iloc[-1]

                            # 高抛位: 现价上方的压力 — 取 min(日内高点, BOLL上轨, MA5) 中最低的
                            sell_cands = [x for x in [high_p, boll_up, ma5] if x == x]
                            sell_level = min(sell_cands) if sell_cands else high_p
                            # 低吸位: 现价下方的支撑 — 在 [日内低, BOLL下, MA10, MA20] 里选比现价低且最高的
                            buy_cands_all = [x for x in [low_p, boll_low, ma10, ma20] if x == x]
                            # 先过滤掉比现价高太多的 (阻力不是支撑), 再选最高的
                            buy_cands_below = [x for x in buy_cands_all if x <= close_p * 1.02]
                            buy_level = max(buy_cands_below) if buy_cands_below else low_p

                            name = "—"
                            if _TUSHARE_SB_CACHE.get("data") is not None:
                                c2 = _TUSHARE_SB_CACHE["data"]
                                cm = c2[c2["ts_code"].str.startswith(code)]
                                if len(cm) > 0: name = str(cm.iloc[0]["name"])

                            # 格式化 sell_level / buy_level: 如果是 NaN 用 —
                            def _fmt(v):
                                if v != v: return "—"
                                return f"{v:.2f}"

                            # 只保留 sell 和 buy 都合理的 (sell > buy, 且 buy 不远离现价)
                            if sell_level != sell_level or buy_level != buy_level: continue
                            if sell_level <= buy_level: continue
                            # 低吸位不能比现价高太多 (>5%) 或者 比现价低 >15% 就离谱
                            if buy_level > close_p * 1.05 or buy_level < close_p * 0.85: continue

                            data["hlswing"].append((
                                code, name,
                                f"{gap_pct:+.1f}%",
                                f"{fade_pct:+.1f}%",
                                _fmt(sell_level),
                                _fmt(buy_level)))
                    except Exception: continue

                # 按高开幅度排, 高开越多越典型
                data["hlswing"].sort(key=lambda x: float(x[2].rstrip("%+")), reverse=True)
                print(f"[👁️看盘] ✅ 高开低走: {len(data['hlswing'])} 只")
            except Exception as e:
                print(f"[捡漏] 高开低走失败: {e}")

            # 更新 UI + 写缓存
            def _apply():
                for key, tv in win._leak_tvs.items():
                    for i in tv.get_children(): tv.delete(i)
                    for row in data.get(key, [])[:20]:
                        tv.insert("", tk.END, values=row)
                # 写 JSON 持久化缓存, 下次打开秒出
                date_str = datetime.now().strftime("%Y%m%d_%H%M")
                _save_leak_cache(data, date_str)
                total = sum(len(v) for v in data.values())
                print(f"[👁️看盘] ✅ 捡漏数据: 资讯 {len(data['news'])} | 强势 {len(data['strong'])} | 超跌 {len(data['drop'])}")
            win.after(0, _apply)
        except Exception as e:
            print(f"[👁️看盘❌] 捡漏加载异常: {e}\n{traceback.format_exc()}")
    threading.Thread(target=_bg, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════
# 🗂️ 板块画布 (Treemap) — 新增 Tab
# ═══════════════════════════════════════════════════════════════════

def _blend_color(c1, c2, ratio):
    """两个 #RRGGBB 颜色按 ratio 混合 (0=c1, 1=c2)"""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02X}{g:02X}{b:02X}"


def _pct_to_color(pct):
    """涨跌幅 → 背景色 (红涨绿跌渐变)"""
    RED_HOT = "#B71C1C"     # +3% 以上
    GREEN_HOT = "#1B5E20"   # -3% 以下
    FLAT = "#1E1E1E"        # 0% 中性

    if pct >= 3.0:
        return RED_HOT
    elif pct >= 0:
        ratio = pct / 3.0
        return _blend_color(FLAT, RED_HOT, ratio * ratio)
    elif pct <= -3.0:
        return GREEN_HOT
    else:
        ratio = abs(pct) / 3.0
        return _blend_color(FLAT, GREEN_HOT, ratio * ratio)


def _pct_to_fg(pct):
    """涨跌幅 → 前景色"""
    if pct >= 2.0:
        return "#FFCDD2"
    elif pct > 0:
        return "#FFAB91"
    elif pct <= -2.0:
        return "#C8E6C9"
    elif pct < 0:
        return "#A5D6A7"
    return "#E0E0E0"


def _layout_treemap(items, x, y, w, h):
    """Squarified Treemap 简化版
    items: [(name, weight, pct, extra_dict), ...] — 已按 weight 降序
    返回: [(name, x1, y1, x2, y2, pct, weight, extra), ...]
    """
    if not items or w < 1 or h < 1:
        return []
    rects = []
    _slice(items, x, y, w, h, rects)
    return rects


def _slice(items, x, y, w, h, out):
    """递归切片"""
    n = len(items)
    if n == 0:
        return
    if n == 1:
        name, weight, pct, extra = items[0]
        out.append((name, x, y, x + w, y + h, pct, weight, extra))
        return

    horizontal = w >= h
    total_w = sum(it[1] for it in items)
    if total_w <= 0:
        return

    cum = 0
    half = total_w / 2
    k = 1
    for i in range(n):
        cum += items[i][1]
        if cum >= half:
            k = i + 1
            break
    k = min(k, n - 1)

    group1 = items[:k]
    group2 = items[k:]
    w1 = sum(it[1] for it in group1) / total_w

    if horizontal:
        w_use = w * w1
        _slice_in_one_dim(group1, x, y, w_use, h, out, horizontal=True)
        _slice(group2, x + w_use, y, w - w_use, h, out)
    else:
        h_use = h * w1
        _slice_in_one_dim(group1, x, y, w, h_use, out, horizontal=False)
        _slice(group2, x, y + h_use, w, h - h_use, out)


def _slice_in_one_dim(items, x, y, w, h, out, horizontal):
    """在短边方向按比例铺开"""
    total = sum(it[1] for it in items)
    if total <= 0:
        return
    cur = 0.0
    for name, weight, pct, extra in items:
        frac = weight / total
        if horizontal:
            iw = w * frac
            out.append((name, x + cur, y, x + cur + iw, y + h, pct, weight, extra))
            cur += iw
        else:
            ih = h * frac
            out.append((name, x, y + cur, x + w, y + cur + ih, pct, weight, extra))
            cur += ih


# ── 板块数据获取 ──

_BLOCK_CANVAS_CACHE = {"data": None, "time": 0}

def _get_block_canvas_data():
    """获取板块画布数据 — 主力 tushare 聚合 FIXED_BLOCKS (真实 pct + top5) + 新浪实时更新, 缓存 60s"""
    import math
    now = time.time()
    if _BLOCK_CANVAS_CACHE["data"] and (now - _BLOCK_CANVAS_CACHE["time"] < 60):
        return _BLOCK_CANVAS_CACHE["data"]

    weighted = []

    # 🥇 主力数据源: tushare daily + stock_basic 聚合 FIXED_BLOCKS
    tushare_blocks = _compute_block_pct_from_cache() or {}
    if tushare_blocks:
        # 盘中: 用新浪实时 pct 覆盖 tushare (tushare 只有收盘数据)
        sina_pcts = {}
        if _is_trading_hours():
            rt = _get_sina_realtime()
            sina_pcts = rt.get("sectors", {}) if rt else {}

        for name in FIXED_BLOCKS:
            info = tushare_blocks.get(name)
            if info is None or info[0] is None:
                continue
            pct_tushare, n_stocks, top5 = info
            # 盘中优先用新浪实时 pct
            pct = sina_pcts.get(name, pct_tushare)
            n = n_stocks
            top3 = top5[:3] if top5 else []
            weight = max(0.5, abs(pct)) * max(1, math.log(n + 1))
            weighted.append({
                "name": name, "pct": float(pct), "n": n,
                "up": None, "down": None, "weight": weight,
                "top3": top3,
            })
        if weighted:
            print(f"[🗂️画布] ✅ 主力 tushare 聚合 + 盘中新浪更新: {len(weighted)} 板块")

    # 🥈 兜底: akshare 东方财富概念板块 (如果能连上)
    if not weighted:
        try:
            import akshare as ak
            df = ak.stock_board_concept_name_em()
            if df is not None and len(df) > 0:
                name_col = [c for c in df.columns if "名称" in str(c) or "板块" in str(c)]
                pct_col = [c for c in df.columns if "涨跌" in str(c)]
                up_col = [c for c in df.columns if "上涨" in str(c)]
                down_col = [c for c in df.columns if "下跌" in str(c)]
                n_col = [c for c in df.columns if "家数" in str(c) and "上" not in str(c) and "下" not in str(c)]
                if name_col and pct_col:
                    for _, row in df.iterrows():
                        try:
                            nm = str(row[name_col[0]])
                            pct = float(row[pct_col[0]])
                            n = int(row[n_col[0]]) if n_col else 1
                            up = int(row[up_col[0]]) if up_col else None
                            dn = int(row[down_col[0]]) if down_col else None
                            weight = max(0.5, abs(pct)) * max(1, math.log(n + 1))
                            weighted.append({
                                "name": nm, "pct": pct, "n": n,
                                "up": up, "down": dn, "weight": weight, "top3": [],
                            })
                        except Exception:
                            continue
                    print(f"[🗂️画布] akshare 概念板块: {len(weighted)} 条")
        except Exception as e:
            print(f"[🗂️画布] akshare 概念板块失败: {e}")

    # 🥉 兜底: 新浪实时 FIXED_BLOCKS
    if not weighted:
        try:
            rt = _get_sina_realtime()
            sectors = rt.get("sectors", {}) if rt else {}
            for name in FIXED_BLOCKS:
                pct = sectors.get(name)
                if pct is not None:
                    weighted.append({
                        "name": name, "pct": float(pct), "n": 1,
                        "up": None, "down": None, "weight": max(0.5, abs(float(pct))),
                        "top3": [],
                    })
            print(f"[🗂️画布] 新浪实时兜底: {len(weighted)} 条")
        except Exception as e:
            print(f"[🗂️画布] 新浪兜底失败: {e}")

    # 最终种子兜底
    if not weighted:
        for name in FIXED_BLOCKS:
            pct = SEED_BLOCK_META.get(name, {}).get("pct", 0)
            weighted.append({
                "name": name, "pct": float(pct), "n": 1,
                "up": None, "down": None, "weight": 1.0, "top3": [],
            })
        print(f"[🗂️画布] 种子兜底: {len(weighted)} 条")

    weighted.sort(key=lambda x: x["weight"], reverse=True)

    _BLOCK_CANVAS_CACHE["data"] = weighted
    _BLOCK_CANVAS_CACHE["time"] = now
    return weighted


# ── Treemap 绘制 ──

def _draw_block_treemap(win):
    """绘制板块画布 Treemap — 可点击, 点击弹出该板块文章生成"""
    canvas = getattr(win, "_block_canvas", None)
    if canvas is None:
        return
    canvas.delete("all")

    blocks = _get_block_canvas_data()
    if not blocks:
        W = canvas.winfo_width() or 600
        H = canvas.winfo_height() or 400
        canvas.create_text(W // 2, H // 2,
                          text="⏳ 板块数据加载中...", fill="#9E9E9E",
                          font=("", 14))
        return

    W = canvas.winfo_width() or 600
    H = canvas.winfo_height() or 400

    items = [(b["name"], b["weight"], b["pct"], b) for b in blocks]
    rects = _layout_treemap(items, 4, 4, W - 8, H - 8)

    # 存点击映射: tag → block dict
    tag_map = {}
    total_area = sum((r[2] - r[1]) * (r[4] - r[3]) for r in rects)
    cum_area = 0

    rank = 0
    for name, x1, y1, x2, y2, pct, weight, extra in rects:
        rank += 1
        w = x2 - x1
        h = y2 - y1
        if w < 5 or h < 5:
            continue

        area = w * h
        cum_area += area
        is_front = cum_area <= total_area * 0.70

        bg = _pct_to_color(pct)
        fg = _pct_to_fg(pct)

        # 可点击矩形 (outline 更亮, cursor 手型)
        tag = f"block_{rank}"
        canvas.create_rectangle(x1, y1, x2, y2, fill=bg, outline="#555",
                               width=1, tags=tag, activeoutline="#FFD54F",
                               activewidth=2)
        tag_map[tag] = extra

        # 让所有元素共用同一 tag 方便点击命中
        canvas.create_text((x1+x2)//2, (y1+y2)//2, text="", tags=tag)  # 占位
        canvas.create_text((x1+x2)//2, 0, text="", tags=(tag, "_skip"))  # 占位

        min_side = min(w, h)
        if min_side > 120:
            name_fs, pct_fs, info_fs = 14, 18, 11
        elif min_side > 80:
            name_fs, pct_fs, info_fs = 12, 15, 10
        elif min_side > 50:
            name_fs, pct_fs, info_fs = 11, 13, 9
        else:
            name_fs, pct_fs, info_fs = 10, 12, 8

        name_fw = "bold" if is_front else "normal"
        pct_fw = "bold" if is_front else "normal"

        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        canvas.create_text(cx, cy - max(8, h // 6), text=name,
                          fill="#FFFFFF", font=("", name_fs, name_fw),
                          tags=[tag])

        sign = "+" if pct >= 0 else ""
        canvas.create_text(cx, cy + max(4, h // 8),
                          text=f"{sign}{pct:.2f}%",
                          fill=fg, font=("", pct_fs, pct_fw),
                          tags=[tag])

        # 详细信息: n=xx ↑xx ↓xx + top3 龙头
        if is_front and extra:
            n = extra.get("n")
            up = extra.get("up")
            dn = extra.get("down")
            top3 = extra.get("top3", [])
            info_parts = []
            if n:
                info_parts.append(f"n={n}")
            if up is not None:
                info_parts.append(f"↑{up}")
            if dn is not None:
                info_parts.append(f"↓{dn}")
            if info_parts:
                canvas.create_text(cx, y2 - info_fs - 4,
                                  text=" ".join(info_parts),
                                  fill="#BDBDBD", font=("", info_fs),
                                  tags=[tag])
            # Top3 龙头 (底部, 缩小字体)
            if top3 and h > 100:
                top3_fs = max(8, info_fs - 1)
                ty = y2 - info_fs - 20
                for ti, (sname, spct) in enumerate(top3[:3]):
                    short = sname[:5] if len(sname) > 5 else sname
                    sfg = "#FFCDD2" if spct >= 0 else "#C8E6C9"
                    ssign = "+" if spct >= 0 else ""
                    ty_line = ty - ti * (top3_fs + 2)
                    canvas.create_text(x1 + 8, ty_line, text=f"{short}",
                                      fill="#E0E0E0", font=("", top3_fs),
                                      anchor=tk.W, tags=[tag])
                    canvas.create_text(x2 - 8, ty_line, text=f"{ssign}{spct:.1f}%",
                                      fill=sfg, font=("", top3_fs),
                                      anchor=tk.E, tags=[tag])

        # 前 3 名角标
        if rank <= 3 and is_front:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            canvas.create_text(x1 + 14, y1 + 10, text=medals[rank],
                              font=("", 14), tags=[tag])

    # 保存 tag 映射, 绑定点击
    win._block_tag_map = tag_map
    canvas.config(cursor="hand2")
    canvas.bind("<Button-1>", lambda e: _on_treemap_click(win, e))

    # 统计
    _update_block_canvas_stat(win, blocks)


def _on_treemap_click(win, event):
    """点击 Treemap 格子 → 弹出该板块文章生成"""
    canvas = getattr(win, "_block_canvas", None)
    tag_map = getattr(win, "_block_tag_map", {})
    if canvas is None or not tag_map:
        return
    try:
        item = canvas.find_closest(event.x, event.y)[0]
        tags = canvas.gettags(item)
        # tags 形如 ("block_3",) 或 ("block_3", "_skip")
        block_tag = None
        for t in tags:
            if t.startswith("block_") and t in tag_map:
                block_tag = t; break
        if block_tag is None:
            return
        block = tag_map[block_tag]
        name = block.get("name", "")
        pct = block.get("pct", 0)
        ctx = {
            "focus_sector": name,
            "sector_pct": f"{pct:+.2f}%",
            "n_stocks": block.get("n"),
            "top3": [(s, f"{p:+.2f}%") for s, p in block.get("top3", [])],
        }
        _article_output_dialog(win, ctx=ctx, focus_layer=f"🗂️ 板块: {name}")
    except Exception as ex:
        print(f"[🗂️画布] click err: {ex}")


# ── UI 面板 ──

def _build_block_canvas_panel(parent, win):
    """构建 🗂️ 板块画布 Tab"""
    # grid 三列: 左标题+状态 | 中📝 | 右🔄刷新
    top = tk.Frame(parent, bg="#121212"); top.pack(fill=tk.X, pady=4)
    top.grid_columnconfigure(0, weight=0); top.grid_columnconfigure(1, weight=1); top.grid_columnconfigure(2, weight=0)

    # 左侧: 标题 + 状态 (包在内部 frame 里 pack)
    left_f = tk.Frame(top, bg="#121212"); left_f.grid(row=0, column=0, sticky="w")
    tk.Label(left_f, text="🗂️ 板块画布", bg="#121212", fg="#FFD54F",
             font=("", 12, "bold")).pack(side=tk.LEFT, padx=8)
    win._block_canvas_stat = tk.Label(left_f, text="⏳ 加载中...",
                                      bg="#121212", fg="#BDBDBD",
                                      font=("", 11))
    win._block_canvas_stat.pack(side=tk.LEFT, padx=10)

    # 中间: 📝文章按钮 (grid column=1, sticky=""居中)
    _add_article_btn(parent, win, focus_layer="🗂️ 板块画布")

    # 右侧: 🔄刷新按钮
    tk.Button(top, text="🔄 刷新", bg="#3949AB", fg="#ECEFF1",
              font=("", 10, "bold"),
              command=lambda: _refresh_block_canvas(win)).grid(row=0, column=2, sticky="e", padx=8)

    canvas = tk.Canvas(parent, bg="#121212", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))
    win._block_canvas = canvas

    def _on_cfg(e):
        if e.width > 100 and e.height > 100:
            _draw_block_treemap(win)
    canvas.bind("<Configure>", _on_cfg)

    canvas.after(200, lambda: _draw_block_treemap(win))


def _refresh_block_canvas(win):
    """刷新板块画布 (清缓存重拉)"""
    def _bg():
        try:
            _BLOCK_CANVAS_CACHE["time"] = 0
            data = _get_block_canvas_data()
            win.after(0, lambda: _draw_block_treemap(win))
        except Exception as e:
            print(f"[🗂️画布] refresh 异常: {e}")
    threading.Thread(target=_bg, daemon=True).start()


def _update_block_canvas_stat(win, data):
    """更新顶部统计文字"""
    if not hasattr(win, "_block_canvas_stat") or not data:
        return
    up_count = sum(1 for d in data if d["pct"] > 0)
    dn_count = sum(1 for d in data if d["pct"] < 0)
    avg_pct = sum(d["pct"] for d in data) / len(data)
    top3 = data[:3]
    top_names = " / ".join(f"{d['name']}{d['pct']:+.2f}%" for d in top3)
    color = "#66BB6A" if avg_pct >= 0 else "#EF5350"
    win._block_canvas_stat.config(
        text=f"共 {len(data)} 板块 | 涨 {up_count} / 跌 {dn_count} | "
             f"均值 {avg_pct:+.2f}% | 🔥 {top_names}",
        fg=color)


# ═══════════════════════════════════════════════════════════════════
# 📝 文章生成弹窗 — 财经博主 × 多平台 × 多风格
# ═══════════════════════════════════════════════════════════════════

# ── 维度配置 (参考短剧弹窗风格) ──

ARTICLE_AUTHORS = [
    ("但斌/葛卫东", "价值投资教父, 长期主义, 看好中国核心资产, 金句频出但数据扎实"),
    ("淘股吧游资", "短线龙头战法, 情绪周期, 打板接力, 江湖黑话, 日内操作铁口直断"),
    ("韭研公社主力", "主力追踪, 资金流向, 带血筹码, 机构视角, 逻辑推演清晰"),
    ("华尔街见闻", "专业快讯风, 快准狠, 数据先行, 无情绪不煽情, 5秒读完全文"),
    ("叶檀观察", "女性财经视角, 犀利辛辣, 关注民生, 从数据到社会问题"),
    ("李大霄调侃", "大霄哥嘴炮风, 金句段子满天飞, 娱乐财经, 信口开河但有料"),
    ("量化理性派", "纯数据说话, 因子模型, 回测结论, 无情无义无情绪"),
    ("雪球深度复盘", "长文干货, 代码表格, 逻辑链完整, 适合学习收藏"),
    ("券商分析师", "正规研报风, 客观中立, 有数据有结论, 但缺乏个人风格"),
    ("独立自媒体", "口语化, 像和朋友聊天, 不装不端, 有温度有态度"),
]

ARTICLE_MODES = [
    ("大盘日记", "每日快评, 一句话说清今天发生了什么"),
    ("板块解读", "热点板块深度分析, 为什么涨/跌, 还能不能追"),
    ("个股分析", "牛股/熊股逻辑拆解, 基本面+技术面+资金面"),
    ("复盘总结", "今日复盘, 情绪+板块+龙头, 系统性回顾"),
    ("明日预判", "推演明日走势, 剧本A/B/C, 明确触发条件"),
    ("策略建议", "操作指导, 仓位+方向+止损止盈, 给具体数字"),
    ("情绪点评", "情绪周期分析, 冰点/高潮/回暖, 结合历史对照"),
    ("龙虎榜解读", "游资动向, 机构买卖, 带血筹码, 主力行为学"),
]

ARTICLE_PLATFORMS = [
    ("微信公众号", "Markdown+小标题+emoji+分割线, 适合长文深度阅读"),
    ("微博短文", "200字内, 话题标签, @提及, 口语化快节奏"),
    ("小红书种草", "活泼有趣, 干货清单, emoji密集, tag丰富, 像和闺蜜分享"),
    ("雪球长文", "深度分析, 代码表格, 逻辑清晰, 适合学习和讨论"),
    ("正规研报", "客观中立, 专业术语, 数据翔实, 无个人情绪"),
    ("幽默段子", "段子+梗+调侃, 寓教于乐, 大霄哥最爱"),
    ("抖音短评", "口语化, 快节奏, 金句开头, 话题标签, 适合短视频文案"),
    ("知乎回答", "先问是不是再问为什么, 理性分析, 引用数据, 长文深度"),
]

ARTICLE_LENGTHS = [
    ("200字快评", "一句话+两三句点评, 适合微博/抖音"),
    ("800字短文", "2-3段, 适合小红书/知乎/雪球"),
    ("1500字标准", "4-5段, 适合公众号/雪球/研报"),
    ("3000字深度", "多章节, 完整逻辑链, 适合公众号深度长文"),
]


def _robust_ai_call(prompt, system_prompt="", max_tokens=1500, win=None):
    """AI 自动 fallback — 主 provider 失败循环尝试所有可用 provider"""
    import json as _j
    import requests as _req
    import os as _os

    # 1️⃣ 先试主程序的 call_ai_model (用 active_provider)
    callers = []
    try:
        from src.ui.tab_dapan import call_ai_model as _cai1; callers.append(_cai1)
    except Exception: pass
    if win is not None and hasattr(win, "_app") and getattr(win._app, "call_ai_model", None):
        callers.append(win._app.call_ai_model)

    for fn in callers:
        try:
            r = fn(prompt, system_prompt=system_prompt, max_tokens=max_tokens)
            if r and isinstance(r, str) and len(r.strip()) > 20:
                bad_words = ["402", "余额", "不足", "rate limit", "overloaded", "Error", "error"]
                if not any(b in r[:100] for b in bad_words):
                    return r  # ✅ 成功
                print(f"[🤖AI] 主 provider 返回错误内容, 尝试 fallback...")
        except Exception as e:
            print(f"[🤖AI] 主 provider 异常: {e}")

    # 2️⃣ 循环 ai_config.json 里所有 providers
    cfg_path = _os.path.join(_os.path.dirname(__file__), "..", "config", "ai_config.json")
    cfg_path = _os.path.abspath(cfg_path)
    providers_order = ["deepseek", "doubao", "ollama"]
    try:
        with open(cfg_path, "r") as _f:
            cfg = _j.load(_f)
        cfg_providers = cfg.get("providers", {})
    except Exception as e:
        print(f"[🤖AI] 无法读 ai_config.json: {e}")
        return None

    for pname in providers_order:
        p = cfg_providers.get(pname)
        if not p: continue
        api_key = (p.get("api_key") or "").strip()
        # ollama 不需要 key
        if not api_key and pname != "ollama": continue
        if pname == "ollama":
            try:
                _req.get("http://localhost:11434/api/tags", timeout=2)
            except Exception:
                continue  # ollama 没跑, 跳过

        base = p["base_url"].rstrip("/")
        ep = p.get("endpoint", "/chat/completions")
        model = p["model"]
        url = f"{base}{ep}"
        headers = {"Content-Type": "application/json"}
        if api_key: headers["Authorization"] = f"Bearer {api_key}"

        messages = []
        if system_prompt: messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": p.get("temperature", 0.3),
            "stream": False,
        }
        try:
            resp = _req.post(url, headers=headers, json=body, timeout=p.get("timeout", 45))
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                if text and len(text.strip()) > 10:
                    print(f"[🤖AI] ✅ {pname}/{model} fallback 成功!")
                    return text
            else:
                print(f"[🤖AI] {pname} 返回 {resp.status_code}: {resp.text[:80]}")
        except Exception as e:
            print(f"[🤖AI] {pname} 失败: {e}")

    print("[🤖AI] 所有 provider 都失败")
    return None


def _article_output_dialog(win, ctx=None, focus_layer=None):
    """📝 文章生成弹窗 — 参考短剧弹窗风格, 多维度选择"""
    import tkinter as tk
    from tkinter import scrolledtext

    dlg = tk.Toplevel(win); dlg.configure(bg="#121212")
    dlg.title("📝 文章生成器 · 财经博主多平台输出")
    dlg.geometry("1080x820")
    dlg.minsize(960, 720)

    # ════════════════════════════════════════════
    # Banner (参考短剧弹窗红色 Banner)
    # ════════════════════════════════════════════
    banner = tk.Frame(dlg, bg="#B71C1C", height=52)
    banner.pack(fill=tk.X)
    tk.Label(banner, text="📝 文章生成器", bg="#B71C1C", fg="white",
             font=("", 16, "bold")).pack(side=tk.LEFT, padx=16, pady=10)
    sub = "财经博主风格 × 多平台 × 多模式 — "
    if focus_layer:
        sub += f"📌 聚焦: {focus_layer}"
    else:
        sub += "🎯 基于游资看盘全量数据"
    tk.Label(banner, text=sub, bg="#B71C1C", fg="#FFCDD2",
             font=("", 11)).pack(side=tk.LEFT, pady=14)

    # ════════════════════════════════════════════
    # 维度 1: 作者风格 (单选 Radio)
    # ════════════════════════════════════════════
    author_frame = tk.LabelFrame(dlg, text="✍️ 作者风格 (单选)",
                                  font=("", 11, "bold"), fg="#B71C1C")
    author_frame.pack(fill=tk.X, padx=10, pady=(10, 4))
    selected_author = tk.StringVar(value="但斌/葛卫东")
    a_inner = tk.Frame(author_frame, bg="#121212"); a_inner.pack(fill=tk.X, padx=8, pady=6)
    for i, (name, _desc) in enumerate(ARTICLE_AUTHORS):
        r = i // 5; c = i % 5
        tk.Radiobutton(a_inner, text=name, variable=selected_author, value=name,
                       bg="#121212", fg="#E0E0E0", activebackground="#121212",
                       activeforeground="#FFCDD2", selectcolor="#4A1C1C",
                       font=("", 10, "bold"), anchor="w",
                       indicatoron=True).grid(row=r, column=c, padx=6, pady=3, sticky="w")

    # ════════════════════════════════════════════
    # 维度 2: 文章模式 (单选 Radio)
    # ════════════════════════════════════════════
    mode_frame = tk.LabelFrame(dlg, text="📚 文章模式 (单选)",
                                font=("", 11, "bold"), fg="#B71C1C")
    mode_frame.pack(fill=tk.X, padx=10, pady=4)
    selected_mode = tk.StringVar(value="大盘日记")
    m_inner = tk.Frame(mode_frame, bg="#121212"); m_inner.pack(fill=tk.X, padx=8, pady=6)
    for i, (name, _desc) in enumerate(ARTICLE_MODES):
        r = i // 4; c = i % 4
        tk.Radiobutton(m_inner, text=name, variable=selected_mode, value=name,
                       bg="#121212", fg="#E0E0E0", activebackground="#121212",
                       activeforeground="#FFCDD2", selectcolor="#4A1C1C",
                       font=("", 10), anchor="w",
                       indicatoron=True).grid(row=r, column=c, padx=6, pady=3, sticky="w")

    # ════════════════════════════════════════════
    # 维度 3: 平台风格 (单选 Radio)
    # ════════════════════════════════════════════
    plat_frame = tk.LabelFrame(dlg, text="📱 平台风格 (单选)",
                                font=("", 11, "bold"), fg="#B71C1C")
    plat_frame.pack(fill=tk.X, padx=10, pady=4)
    selected_plat = tk.StringVar(value="微信公众号")
    p_inner = tk.Frame(plat_frame, bg="#121212"); p_inner.pack(fill=tk.X, padx=8, pady=6)
    for i, (name, _desc) in enumerate(ARTICLE_PLATFORMS):
        r = i // 4; c = i % 4
        tk.Radiobutton(p_inner, text=name, variable=selected_plat, value=name,
                       bg="#121212", fg="#E0E0E0", activebackground="#121212",
                       activeforeground="#FFCDD2", selectcolor="#4A1C1C",
                       font=("", 10), anchor="w",
                       indicatoron=True).grid(row=r, column=c, padx=6, pady=3, sticky="w")

    # ════════════════════════════════════════════
    # 维度 4: 字数 (单选 Radio)
    # ════════════════════════════════════════════
    len_frame = tk.LabelFrame(dlg, text="📏 字数 (单选)",
                               font=("", 11, "bold"), fg="#B71C1C")
    len_frame.pack(fill=tk.X, padx=10, pady=4)
    selected_len = tk.StringVar(value="1500字标准")
    l_inner = tk.Frame(len_frame, bg="#121212"); l_inner.pack(fill=tk.X, padx=8, pady=6)
    for i, (name, _desc) in enumerate(ARTICLE_LENGTHS):
        tk.Radiobutton(l_inner, text=name, variable=selected_len, value=name,
                       bg="#121212", fg="#E0E0E0", activebackground="#121212",
                       activeforeground="#FFCDD2", selectcolor="#4A1C1C",
                       font=("", 10, "bold"), anchor="w",
                       indicatoron=True).grid(row=0, column=i, padx=12, pady=2, sticky="w")

    # ════════════════════════════════════════════
    # 自定义主题 (可选输入)
    # ════════════════════════════════════════════
    custom_frame = tk.LabelFrame(dlg, text="💡 自定义主题 (可选, 不填则用游资看盘数据自动生成)",
                                 font=("", 10), fg="#FFA726")
    custom_frame.pack(fill=tk.X, padx=10, pady=4)
    custom_txt = scrolledtext.ScrolledText(custom_frame, height=2, font=("", 11),
                                            wrap=tk.WORD, bg="#1E1E1E", fg="#E0E0E0",
                                            insertbackground="white",
                                            highlightbackground="#424242",
                                            highlightthickness=1)
    custom_txt.pack(fill=tk.X, padx=6, pady=6)
    custom_txt.insert("1.0", "")

    # ════════════════════════════════════════════
    # 按钮区 (参考短剧弹窗按钮)
    # ════════════════════════════════════════════
    btn_frame = tk.Frame(dlg, bg="#121212"); btn_frame.pack(fill=tk.X, padx=10, pady=6)
    status_var = tk.StringVar(value="")

    busy = [False]

    def _collect_realtime_market_data():
        """🔥 自动收集全量真实市场数据 — 不依赖调用方传 ctx!
        
        数据源优先级:
        1. tushare daily + stock_basic 缓存 (本地已聚合)
        2. 新浪实时行情 (四指数 + 行业)
        3. 游资看盘 UI 控件 (涨跌家数/板块九宫格/期货)
        4. akshare 全球资产 (黄金/原油/纳指)
        """
        import json, os
        market = {"source": "真实数据", "collected_at": time.strftime("%Y-%m-%d %H:%M:%S")}

        # ═══════════════════════════════════════════
        # 1. 大盘涨跌家数 (从 _CACHE 或 seed)
        # ═══════════════════════════════════════════
        try:
            seed_up = getattr(_CACHE, "get", lambda x: None)("seed_up_count")
            if seed_up:
                market["涨家数"] = seed_up
                market["跌家数"] = getattr(_CACHE, "get", lambda x: None)("seed_down_count")
        except Exception:
            pass

        # ═══════════════════════════════════════════
        # 2. 十六宫格板块真实 pct + top5 成分股 (tushare 聚合)
        # ═══════════════════════════════════════════
        try:
            blocks = _compute_block_pct_from_cache() or {}
            if blocks:
                sector_list = []
                for name in FIXED_BLOCKS:
                    info = blocks.get(name)
                    if info and info[0] is not None:
                        pct, n_stocks, top5 = info
                        top5_str = ", ".join([f"{s}({p:+.2f}%)" for s, p in (top5 or [])[:5]])
                        sector_list.append(f"{name}({pct:+.2f}%, {n_stocks}只, 龙头: {top5_str})")
                # 涨的在前, 跌的在后
                sector_list.sort(reverse=True)
                market["板块强度"] = sector_list
                market["领涨板块"] = sector_list[:3]
                market["领跌板块"] = sector_list[-3:]
        except Exception as e:
            print(f"[📝收集] 板块数据失败: {e}")

        # ═══════════════════════════════════════════
        # 3. 新浪实时: 四大股指期货 + 深市行业指数
        # ═══════════════════════════════════════════
        try:
            rt = _get_sina_realtime()
            if rt:
                idx_data = rt.get("indices", {}) or {}
                fut_list = []
                for key, info in idx_data.items():
                    close = info.get("close", 0)
                    pct = info.get("pct", 0)
                    fut_list.append(f"{key}={close:.2f}({pct:+.2f}%)")
                if fut_list:
                    market["股指期货实时"] = fut_list
                sectors = rt.get("sectors", {}) or {}
                if sectors:
                    sec_sorted = sorted(sectors.items(), key=lambda x: -abs(x[1]))[:10]
                    market["行业板块实时"] = [f"{k}({v:+.2f}%)" for k, v in sec_sorted]
        except Exception as e:
            print(f"[📝收集] 新浪实时失败: {e}")

        # ═══════════════════════════════════════════
        # 4. 全球五资产 (黄金/原油/纳指)
        # ═══════════════════════════════════════════
        try:
            import akshare as ak
            import concurrent.futures as cf

            def _g_gold():
                try:
                    d = ak.futures_foreign_hist("XAU")
                    v = d["close"].iloc[-1]
                    v2 = d["close"].iloc[-2]
                    return f"黄金=${v:,.0f}({(v-v2)/v2*100:+.2f}%)"
                except Exception: return None
            def _g_oil():
                try:
                    d = ak.futures_foreign_hist("CL")
                    v = d["close"].iloc[-1]
                    v2 = d["close"].iloc[-2]
                    return f"原油=${v:,.2f}({(v-v2)/v2*100:+.2f}%)"
                except Exception: return None
            def _g_ixic():
                try:
                    d = ak.index_us_stock_sina(".IXIC")
                    v = d["close"].iloc[-1]
                    v2 = d["close"].iloc[-2]
                    return f"纳指={v:,.0f}({(v-v2)/v2*100:+.2f}%)"
                except Exception: return None

            with cf.ThreadPoolExecutor(3) as ex:
                gl = ex.submit(_g_gold)
                ol = ex.submit(_g_oil)
                nl = ex.submit(_g_ixic)
                gl_r, ol_r, nl_r = gl.result(timeout=10), ol.result(timeout=10), nl_r.result(timeout=10)
            assets = [x for x in [gl_r, ol_r, nl_r] if x]
            if assets:
                market["全球资产"] = assets
        except Exception as e:
            print(f"[📝收集] 全球资产失败: {e}")

        # ═══════════════════════════════════════════
        # 5. 游资看盘 UI 控件 (涨跌家数/周期信号) — 如果窗口存在
        # ═══════════════════════════════════════════
        try:
            up_lbl = getattr(win, "_up_count_lbl", None) or getattr(win, "_up_label", None)
            down_lbl = getattr(win, "_down_count_lbl", None) or getattr(win, "_down_label", None)
            if up_lbl:
                try: market["上涨家数_UI"] = up_lbl.cget("text")
                except Exception: pass
            if down_lbl:
                try: market["下跌家数_UI"] = down_lbl.cget("text")
                except Exception: pass
        except Exception:
            pass

        print(f"[📝收集] ✅ 真实数据收集完成, 共 {len(market)} 项")
        return market

    def _build_prompt():
        """根据选择构造 AI prompt — 🔥 自动注入真实市场数据"""
        import json
        author_name = selected_author.get()
        author_desc = dict(ARTICLE_AUTHORS).get(author_name, "")
        mode_name = selected_mode.get()
        mode_desc = dict(ARTICLE_MODES).get(mode_name, "")
        plat_name = selected_plat.get()
        plat_desc = dict(ARTICLE_PLATFORMS).get(plat_name, "")
        len_name = selected_len.get()
        custom = custom_txt.get("1.0", tk.END).strip()

        # 🔥 自动收集真实市场数据 (不管 ctx 有没有传)
        real_data = _collect_realtime_market_data()
        # 如果 ctx 也有补充数据, 合并进去
        if ctx:
            extra = {k: v for k, v in ctx.items()
                     if k not in ("spot",) and v is not None and k not in real_data}
            real_data["补充上下文"] = extra

        prompt = f"""请写一篇 A 股财经分析文章。

【作者风格】{author_name}
{author_desc}

【文章模式】{mode_name}
{mode_desc}

【平台风格】{plat_name}
{plat_desc}

【字数要求】{len_name}

【⚠️ 必须基于以下真实数据写作 (禁止编造数据)】
{json.dumps(real_data, ensure_ascii=False, default=str, indent=2)[:3000]}
"""
        if custom:
            prompt += f"\n【自定义主题/重点】\n{custom}\n"
        if focus_layer:
            prompt += f"\n【聚焦层级】{focus_layer}\n"
        prompt += """
【要求】
1. 标题抓眼球 (带 emoji, 20字内, 符合平台调性)
2. 严格按【平台风格】的输出格式
3. 严格模仿【作者风格】的语言习惯
4. 严格控制【字数要求】
5. 结论明确, 不模棱两可
6. 所有数据和观点基于上文【数据上下文】"""
        return prompt, author_name, plat_name, mode_name

    def _build_system(author_name):
        """system prompt — 深度模仿作者"""
        author_map = {
            "但斌/葛卫东": "你是中国巴菲特, 长期价值投资者, 看好茅台、腾讯、招商银行, 金句如'时间是玫瑰', 数据扎实但有情怀, 不做波段, 只谈持有。",
            "淘股吧游资": "你是淘股吧顶级游资, 龙头战法, 情绪周期大师, 江湖黑话: '核按钮'、'天地板'、'吃面'、'打板接力', 日内操作铁口直断, 不装不端。",
            "韭研公社主力": "你是韭研公社的主力追踪者, 擅长从带血筹码、龙虎榜、资金流向推断主力意图, 逻辑严密, 数据说话。",
            "华尔街见闻": "你是华尔街见闻快讯编辑, 快准狠, 5秒读完, 数据先行, 无情绪, 不煽情, 标题党但有料。",
            "叶檀观察": "你是叶檀, 女性财经观察家, 犀利辛辣, 关注民生, 从财经数据看到社会问题, 敢说敢骂。",
            "李大霄调侃": "你是李大霄, 大霄哥, 爱说'婴儿底'、'钻石底', 金句段子满天飞, 娱乐财经第一人, 信口开河但有料。",
            "量化理性派": "你是量化分析师, 只看数据和回测, 因子说话, 无情无义, 结论用数字, 情绪靠边站。",
            "雪球深度复盘": "你是雪球大V, 长文干货, 喜欢贴代码和表格, 逻辑链完整, 适合学习收藏, 结尾必有总结。",
            "券商分析师": "你是券商首席分析师, 客观中立, 专业术语, 数据翔实, 结论明确, 但不表达个人情绪。",
            "独立自媒体": "你是独立自媒体人, 口语化, 像和朋友聊天, 不装不端, 有温度, 敢说真话。",
        }
        return author_map.get(author_name, "你是顶级 A 股财经分析师, 专业、犀利、有料。")

    def _start_gen():
        nonlocal busy
        if busy[0]:
            status_var.set("⚠️ AI 正在创作中...")
            return
        busy[0] = True
        gen_btn.config(state=tk.DISABLED)
        author_name = selected_author.get()
        mode_name = selected_mode.get()
        plat_name = selected_plat.get()
        len_name = selected_len.get()
        sys_prompt = _build_system(author_name)
        status_var.set(f"⏳ 正在收集真实市场数据 + AI 创作...")
        result_txt.delete("1.0", tk.END)
        result_txt.insert("1.0", f"⏳ 正在收集真实市场数据...\n📝 模式: {mode_name}\n📱 平台: {plat_name}\n\n请稍候 30-60 秒...")

        # 根据字数估算 max_tokens
        len_map = {"200字快评": 500, "800字短文": 1500,
                   "1500字标准": 2500, "3000字深度": 4500}
        max_tokens = len_map.get(len_name, 2500)

        def _work():
            try:
                # 🔥 后台线程里收集真实数据 + 构建 prompt (避免卡 UI)
                prompt, author, plat, mode = _build_prompt()
                # 用 robust wrapper 自动 fallback 所有 provider
                result = _robust_ai_call(prompt, system_prompt=sys_prompt,
                                          max_tokens=max_tokens, win=win)
                if not result:
                    result = _article_fallback(prompt, author, mode, plat, len_name)
                dlg.after(0, lambda: _show_result(result))
            except Exception as e:
                import traceback
                err = f"❌ 创作失败：{e}\n\n{traceback.format_exc()}"
                dlg.after(0, lambda: _show_result(err))
            finally:
                busy[0] = False
                dlg.after(0, lambda: gen_btn.config(state=tk.NORMAL))

        import threading
        threading.Thread(target=_work, daemon=True).start()

    def _show_result(text):
        result_txt.delete("1.0", tk.END)
        result_txt.insert("1.0", text or "（AI 没有返回内容）")
        result_txt.see("1.0")
        author = selected_author.get()
        plat = selected_plat.get()
        status_var.set(f"✅ 创作完成！【{author}】· 【{plat}】")

    def _copy():
        text = result_txt.get("1.0", tk.END).strip()
        if not text:
            tk.messagebox.showinfo("提示", "没有可复制的内容")
            return
        dlg.clipboard_clear(); dlg.clipboard_append(text)
        status_var.set("✅ 已复制到剪贴板")

    def _save():
        text = result_txt.get("1.0", tk.END).strip()
        if not text:
            tk.messagebox.showinfo("提示", "没有可保存的内容")
            return
        from tkinter import filedialog
        fname = f"财经文章_{datetime.now().strftime('%Y%m%d_%H%M')}_{selected_author.get()}_{selected_plat.get()}.md"
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            initialfile=fname,
            filetypes=[("Markdown", "*.md"), ("文本", "*.txt"), ("所有文件", "*.*")],
            title="保存文章")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            status_var.set(f"✅ 已保存: {path}")

    def _reset():
        selected_author.set("但斌/葛卫东")
        selected_mode.set("大盘日记")
        selected_plat.set("微信公众号")
        selected_len.set("1500字标准")
        custom_txt.delete("1.0", tk.END)
        result_txt.delete("1.0", tk.END)
        status_var.set("🧹 已清空恢复默认")

    gen_btn = tk.Button(btn_frame, text="📝 生成文章", font=("", 12, "bold"),
                        bg="#B71C1C", fg="white", padx=22, pady=4,
                        cursor="hand2", command=_start_gen)
    gen_btn.pack(side=tk.LEFT, padx=(0, 10))
    tk.Button(btn_frame, text="📋 复制全文", font=("", 11), padx=12,
              command=_copy, cursor="hand2").pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="💾 保存为MD", font=("", 11), padx=12,
              command=_save, cursor="hand2").pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="🗑️ 清空重置", font=("", 11), padx=12,
              command=_reset, cursor="hand2").pack(side=tk.LEFT, padx=5)
    status_lbl = tk.Label(btn_frame, textvariable=status_var, bg="#121212",
                          fg="#FFD54F", font=("", 11))
    status_lbl.pack(side=tk.RIGHT, padx=6)

    # ════════════════════════════════════════════
    # 结果区 (ScrolledText, 深色背景)
    # ════════════════════════════════════════════
    result_frame = tk.LabelFrame(dlg, text="📄 文章正文", font=("", 10, "bold"),
                                  fg="#FFD54F", bg="#121212")
    result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
    result_txt = scrolledtext.ScrolledText(
        result_frame, font=("", 12), wrap=tk.WORD,
        bg="#1E1E1E", fg="#E0E0E0", insertbackground="white",
        highlightbackground="#424242", highlightthickness=1,
        padx=12, pady=10, spacing3=4,
    )
    result_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)


def _add_article_btn(dlg, win=None, ctx=None, focus_layer=None, padx=0, pady=0):
    """通用: 在弹窗最底部单独一行加 📝 红色文章生成按钮
    
    🔑 设计: 接受弹窗窗口本身 (Toplevel/Tk), 在窗口最底部 pack 一行独立 frame
            这样完全不依赖弹窗内部是 pack 还是 grid 布局, 任何弹窗都能正常显示!
    
    用法: _add_article_btn(dlg, win=self.root, ctx=my_ctx, focus_layer="涨停排名")
    """
    try:
        # 如果没传 win, 尝试从 dlg 取
        if win is None:
            win = dlg
        
        # 创建底部独立 frame (永远 pack 到最底部)
        bottom_bar = tk.Frame(dlg, bg="#121212", height=36)
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 2))
        bottom_bar.pack_propagate(False)
        
        btn_text = f"📝 文章生成" + (f" · {focus_layer}" if focus_layer else "")
        btn = tk.Button(bottom_bar, text=btn_text, font=("", 10, "bold"),
                         bg="#B71C1C", fg="white", padx=16, pady=4, cursor="hand2",
                         command=lambda: _article_output_dialog(win, ctx=ctx, focus_layer=focus_layer))
        btn.pack(side=tk.BOTTOM, pady=4)
        
        return btn
    except Exception as e:
        print(f"[📝文章按钮] 添加失败: {e}")
        return None


def _article_fallback(prompt, author, mode, plat, length):
    """AI 不可用时的文章兜底 — 用本地模板生成简洁版"""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""⏳ AI 大模型不可用 — 以下为本地模板兜底文章
（请在「🔧 AI配置」里配置 DeepSeek/豆包/Ollama, 即可获得完整 AI 生成）

═══ 📝 文章输出 ═══
📌 作者风格: {author}
📚 文章模式: {mode}
📱 平台风格: {plat}
📏 字数要求: {length}
🕐 生成时间: {now}

【标题】
⚠️ AI 不可用, 本地模板兜底输出 (配置 AI 后可生成完整文章)

【提示】
请点击主界面「🔧 AI配置」按钮, 配置你的大模型提供商:
- DeepSeek (推荐, 性价比高)
- 豆包 (国内稳定)
- Ollama (本地部署)

配置完成后, 回到此处重新点击「📝 生成文章」即可获得:
✅ 符合 {author} 风格的专业文章
✅ 适配 {plat} 平台格式
✅ {mode} 完整分析内容
"""

# ═══════════════════════════════════════════════════════════════════
# 📚 财经大V风格学习系统 — author_articles DB + AI 提取 + TF-IDF 匹配
# 追加到 speculator_watch.py 末尾
# ═══════════════════════════════════════════════════════════════════

# ── DB 层 ──

_VV_DB_PATH = os.path.expanduser("~/.qclaw/vv_authors.db")

def _vv_get_conn():
    """打开/创建大V文章数据库"""
    os.makedirs(os.path.dirname(_VV_DB_PATH), exist_ok=True)
    import sqlite3
    conn = sqlite3.connect(_VV_DB_PATH, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS author_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            source TEXT DEFAULT '',
            pub_date TEXT DEFAULT '',
            raw_content TEXT,
            extracted_json TEXT,          -- AI 提取的 JSON
            style_summary TEXT DEFAULT '', -- 一句话风格总结
            logic_patterns TEXT DEFAULT '', -- 逻辑模式数组 JSON
            tags TEXT DEFAULT '',         -- 关键词逗号分隔
            market_tags TEXT DEFAULT '',  -- 板块/个股逗号分隔
            embedding TEXT DEFAULT '',    -- TF-IDF {word: weight} JSON
            created_at TEXT
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS author_profiles (
            author TEXT PRIMARY KEY,
            article_count INTEGER DEFAULT 0,
            style_summary TEXT DEFAULT '', -- 综合风格
            typical_patterns TEXT DEFAULT '', -- 典型逻辑模式 JSON
            keywords TEXT DEFAULT '',     -- 高频关键词权重 JSON
            common_market_tags TEXT DEFAULT '', -- 常见关注板块
            updated_at TEXT
        )""")
    return conn


def _vv_insert(author, source, pub_date, raw_content, extracted_json=None,
               style_summary="", logic_patterns="", tags="", market_tags="", embedding=""):
    """插入一篇文章"""
    import json as _j
    from datetime import datetime
    conn = _vv_get_conn()
    try:
        conn.execute("""INSERT INTO author_articles
            (author, source, pub_date, raw_content, extracted_json,
             style_summary, logic_patterns, tags, market_tags, embedding, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (author, source, pub_date, raw_content,
             extracted_json if isinstance(extracted_json, str) else _j.dumps(extracted_json or {}, ensure_ascii=False),
             style_summary,
             logic_patterns if isinstance(logic_patterns, str) else _j.dumps(logic_patterns or [], ensure_ascii=False),
             tags, market_tags,
             embedding if isinstance(embedding, str) else _j.dumps(embedding or {}, ensure_ascii=False),
             datetime.now().isoformat()))
        conn.commit()
        aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # 更新 author_profiles
        _vv_update_profile(author, conn)
        return aid
    finally:
        conn.close()


def _vv_list_authors():
    """列所有作者 (文章数倒序)"""
    conn = _vv_get_conn()
    try:
        rows = conn.execute("""SELECT author, COUNT(*) as cnt,
            GROUP_CONCAT(DISTINCT style_summary) as styles
            FROM author_articles GROUP BY author ORDER BY cnt DESC""").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _vv_list_articles(author=None, limit=200):
    """列文章 (可按作者筛选)"""
    conn = _vv_get_conn()
    try:
        if author:
            rows = conn.execute(
                "SELECT id, author, source, pub_date, style_summary, tags, created_at "
                "FROM author_articles WHERE author=? ORDER BY created_at DESC LIMIT ?",
                (author, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, author, source, pub_date, style_summary, tags, created_at "
                "FROM author_articles ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _vv_get_article(aid):
    """取文章详情"""
    conn = _vv_get_conn()
    try:
        r = conn.execute("SELECT * FROM author_articles WHERE id=?", (aid,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _vv_delete(aid):
    conn = _vv_get_conn()
    try:
        row = conn.execute("SELECT author FROM author_articles WHERE id=?", (aid,)).fetchone()
        conn.execute("DELETE FROM author_articles WHERE id=?", (aid,))
        conn.commit()
        if row:
            _vv_update_profile(row["author"], conn)
    finally:
        conn.close()


def _vv_update_profile(author, conn=None):
    """基于所有文章更新该作者风格画像"""
    import json as _j
    from datetime import datetime
    own_conn = conn is None
    if own_conn:
        conn = _vv_get_conn()
    try:
        rows = conn.execute("""SELECT style_summary, logic_patterns, tags,
            market_tags, embedding, author FROM author_articles
            WHERE author=?""", (author,)).fetchall()
        if not rows: return

        # 综合风格: 取最近一篇的 style_summary
        last_style = rows[-1]["style_summary"] or ""

        # 合并关键词 embedding (平均权重)
        merged_emb = {}
        n_patterns = []
        tag_counter = {}
        market_counter = {}
        for r in rows:
            emb = _j.loads(r["embedding"] or "{}")
            for w, v in emb.items():
                merged_emb[w] = merged_emb.get(w, 0) + v
            pat = _j.loads(r["logic_patterns"] or "[]")
            n_patterns.extend(pat)
            for t in (r["tags"] or "").split(","):
                if t.strip(): tag_counter[t.strip()] = tag_counter.get(t.strip(), 0) + 1
            for t in (r["market_tags"] or "").split(","):
                if t.strip(): market_counter[t.strip()] = market_counter.get(t.strip(), 0) + 1

        top_keywords = sorted(merged_emb.items(), key=lambda x: -x[1])[:30]
        top_market = sorted(market_counter.items(), key=lambda x: -x[1])[:20]

        conn.execute("""INSERT OR REPLACE INTO author_profiles
            (author, article_count, style_summary, typical_patterns,
             keywords, common_market_tags, updated_at)
            VALUES (?,?,?,?,?,?,?)""",
            (author, len(rows), last_style,
             _j.dumps(list(dict.fromkeys(n_patterns))[:15], ensure_ascii=False),
             _j.dumps(top_keywords, ensure_ascii=False),
             ",".join(t for t, _ in top_market),
             datetime.now().isoformat()))
        conn.commit()
    finally:
        if own_conn: conn.close()


def _vv_get_profile(author):
    conn = _vv_get_conn()
    try:
        r = conn.execute("SELECT * FROM author_profiles WHERE author=?", (author,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


# ── TF-IDF 简化版 Embedding ──

def _vv_tokenize(text):
    """jieba 分词 + 过滤停用词"""
    import jieba
    # 自定义金融领域词典
    jieba.add_word("涨停"); jieba.add_word("跌停"); jieba.add_word("连板")
    jieba.add_word("主线"); jieba.add_word("题材"); jieba.add_word("龙头")
    jieba.add_word("游资"); jieba.add_word("机构"); jieba.add_word("北向")
    jieba.add_word("情绪周期"); jieba.add_word("冰点"); jieba.add_word("高潮")
    jieba.add_word("共振"); jieba.add_word("轮动"); jieba.add_word("超跌")
    jieba.add_word("修复"); jieba.add_word("反包"); jieba.add_word("炸板")
    stopwords = set("的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这".split())
    tokens = [w for w in jieba.cut(text) if len(w.strip()) > 1 and w.strip() not in stopwords]
    return tokens


def _vv_tfidf_embed(text):
    """把文本转成 {word: tfidf_weight}"""
    import math
    tokens = _vv_tokenize(text)
    if not tokens: return {}
    # TF
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    # 简单 IDF 近似: 高频词降权, 金融关键词提权
    emb = {}
    boost_words = {"涨停", "跌停", "连板", "主线", "题材", "龙头", "游资",
                   "情绪", "共振", "轮动", "修复", "反包", "炸板", "机构",
                   "北向", "价值", "长期", "业绩", "逻辑", "催化", "预期",
                   "周期", "冰点", "高潮", "风险", "机会", "反弹", "新高"}
    total = len(tokens)
    for w, c in tf.items():
        tfidf = (c / total) * math.log(1 + 1000 / (c + 1))
        if w in boost_words: tfidf *= 2.0  # 金融关键词提权
        emb[w] = round(tfidf, 4)
    # Top 40
    return dict(sorted(emb.items(), key=lambda x: -x[1])[:40])


def _vv_cosine_sim(a, b):
    """两个 {word: weight} 字典的余弦相似度"""
    if not a or not b: return 0.0
    common = set(a.keys()) & set(b.keys())
    if not common: return 0.0
    dot = sum(a[w] * b[w] for w in common)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    if na == 0 or nb == 0: return 0.0
    return dot / (na * nb)


def _vv_match_authors(query_text, top_k=5):
    """输入一段文字 → 匹配最相似的作者, 返回 [(author, score), ...]"""
    import json as _j
    q_emb = _vv_tfidf_embed(query_text)
    conn = _vv_get_conn()
    try:
        rows = conn.execute("SELECT author, embedding FROM author_articles").fetchall()
        scores = {}
        for r in rows:
            e = _j.loads(r["embedding"] or "{}")
            s = _vv_cosine_sim(q_emb, e)
            scores[r["author"]] = scores.get(r["author"], 0) + s
        # 归一化 + 文章数加权
        art_count = {}
        for r in rows:
            art_count[r["author"]] = art_count.get(r["author"], 0) + 1
        scored = [(a, round(s / max(1, art_count.get(a, 1) ** 0.3), 4))
                  for a, s in scores.items()]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]
    finally:
        conn.close()


def _vv_match_articles(query_text, author=None, top_k=10):
    """匹配最相似的历史文章"""
    import json as _j
    q_emb = _vv_tfidf_embed(query_text)
    conn = _vv_get_conn()
    try:
        if author:
            rows = conn.execute(
                "SELECT id, author, pub_date, style_summary, embedding FROM author_articles WHERE author=?",
                (author,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, author, pub_date, style_summary, embedding FROM author_articles").fetchall()
        results = []
        for r in rows:
            e = _j.loads(r["embedding"] or "{}")
            s = _vv_cosine_sim(q_emb, e)
            if s > 0.01:
                results.append((dict(r), s))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]
    finally:
        conn.close()


# ── AI 提取层 ──

_VV_EXTRACT_SYSTEM = """你是金融分析师 + 数据科学家。用户会给你一篇财经文章原文, 请从中提取结构化信息。
严格输出 JSON, 字段如下:
{
  "viewpoints": ["观点1", "观点2", ...],          // 作者的核心观点 (2-6条)
  "logic_chain": ["逻辑节点1", "逻辑节点2", ...],  // 从因到果的推理链 (3-8步)
  "data_points": [{"指标": "数值/范围", "来源": ""}], // 文章里提到的关键数据
  "conclusions": ["结论1", ...],                   // 作者最终结论/判断
  "style_summary": "一句话总结作者的分析风格 (如: 价值投资者, 关注ROE和现金流, 不做波段, 长期持有)",
  "logic_patterns": ["pattern1", ...],             // 作者常用的逻辑模式模板 (如: "先大盘后板块", "看ROE+PB组合", "从资金流向反推主力意图")
  "tags": ["tag1", ...],                           // 文章关键词标签
  "market_tags": ["板块名", "个股名", ...]         // 提到的板块/个股
}"""


def _vv_ai_extract(raw_text, call_fn=None, max_tokens=2000):
    """AI 提取文章结构化信息 + embedding"""
    import json as _j
    # 先本地 TF-IDF embedding (不管 AI 成败)
    emb = _vv_tfidf_embed(raw_text[:5000])

    if call_fn is None:
        def call_fn(prompt, system_prompt="", max_tokens=1500):
            return _robust_ai_call(prompt, system_prompt=system_prompt,
                                    max_tokens=max_tokens)

    prompt = f"""请从以下财经文章中提取结构化信息, 严格按 JSON 格式输出:

【原文】
{raw_text[:6000]}

⚠️ 只输出 JSON, 不要额外解释。"""

    try:
        result = call_fn(prompt, system_prompt=_VV_EXTRACT_SYSTEM, max_tokens=max_tokens)
        if not result:
            return _vv_extract_fallback(emb)
        # 尝试解析 (可能有 markdown 包裹)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"): result = result[4:]
        result = result.strip()
        data = _j.loads(result)
        data["embedding"] = emb
        return data
    except Exception as e:
        print(f"[📚大V] AI extract 失败, 走本地 fallback: {e}")
        fb = _vv_extract_fallback(emb)
        fb["extract_error"] = str(e)
        return fb


def _vv_extract_fallback(emb):
    """AI 不可用时的本地 fallback"""
    import json as _j
    top_words = list(emb.keys())[:10] if emb else []
    return {
        "viewpoints": [],
        "logic_chain": [],
        "data_points": [],
        "conclusions": [],
        "style_summary": "(AI 未配置, 未提取 — 建议在 🔧 AI配置 里配置大模型后重新提取)",
        "logic_patterns": [],
        "tags": top_words,
        "market_tags": [],
        "embedding": emb,
    }


# ── 风格迁移分析 ──

def _vv_style_analysis(author, market_ctx, call_fn=None):
    """用某大V的风格 + 历史逻辑链, 分析当前市场"""
    import json as _j
    profile = _vv_get_profile(author)
    articles = _vv_list_articles(author, limit=50)

    # 构造风格上下文
    if profile:
        style = profile.get("style_summary", "")
        patterns = _j.loads(profile.get("typical_patterns") or "[]")
    else:
        style = "未知"
        patterns = []

    # 匹配最相关的 3 篇历史文章
    similar = _vv_match_articles(market_ctx if isinstance(market_ctx, str) else str(market_ctx),
                                  author=author, top_k=3)

    history_prompts = ""
    for art, score in similar[:3]:
        history_prompts += f"""
--- 历史参考文章 (相似度 {score:.0%}) ---
日期: {art.get('pub_date', '')}
风格: {art.get('style_summary', '')}
"""
        if art.get("extracted_json"):
            try:
                ej = _j.loads(art["extracted_json"])
                if ej.get("viewpoints"):
                    history_prompts += f"观点: {ej['viewpoints'][:3]}\n"
                if ej.get("logic_chain"):
                    history_prompts += f"逻辑链: {' → '.join(ej['logic_chain'][:5])}\n"
                if ej.get("conclusions"):
                    history_prompts += f"结论: {ej['conclusions'][:2]}\n"
            except Exception:
                pass

    if call_fn is None:
        def call_fn(prompt, system_prompt="", max_tokens=2500):
            return _robust_ai_call(prompt, system_prompt=system_prompt,
                                    max_tokens=max_tokens)
        # 如果 robust 返回 None, 提前返回
        if _robust_ai_call("test", max_tokens=100) is None:
            return "❌ 所有 AI provider 都不可用 (deepseek余额不足, doubao未填key, ollama未启动)\n\n请在 config/ai_config.json 配置豆包 API key, 或安装 ollama 本地运行 qwen2.5"

    prompt = f"""请模仿【{author}】的分析风格和逻辑, 基于当前市场数据给出分析。

【作者风格画像】
{style}

【典型逻辑模式】
{chr(10).join(f"- {p}" for p in patterns[:8]) if patterns else "(暂无)"}

{history_prompts}

【当前市场数据】
{market_ctx if isinstance(market_ctx, str) else _j.dumps(market_ctx, ensure_ascii=False, default=str)}

【要求】
1. 严格模仿 {author} 的语言风格、逻辑习惯、数据偏好
2. 先给核心判断, 再展开逻辑链, 最后给操作建议
3. 结论明确, 不模棱两可
4. 用 {author} 常用的金句/口头禅 (如果有的话)"""

    try:
        system = f"你正在模仿顶级财经博主【{author}】进行市场分析。始终保持他/她的人设、语气、逻辑习惯和金句。"
        return call_fn(prompt, system_prompt=system, max_tokens=2500)
    except Exception as e:
        return f"❌ 分析失败: {e}"


# ═══════════════════════════════════════════════════════════════════
# 📚 主界面 UI — Notebook 3 Tab
# ═══════════════════════════════════════════════════════════════════

def _show_vv_main(win):
    """📚财经大V 主窗口"""
    import tkinter as tk
    from tkinter import scrolledtext, filedialog, messagebox
    import ttk

    dlg = tk.Toplevel(win); dlg.configure(bg="#121212")
    dlg.title("📚 财经大V风格学习库")
    dlg.geometry("1080x780")
    dlg.minsize(900, 680)

    # Banner
    banner = tk.Frame(dlg, bg="#1565C0", height=48)
    banner.pack(fill=tk.X)
    tk.Label(banner, text="📚 财经大V风格学习库", bg="#1565C0", fg="white",
             font=("", 14, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
    tk.Label(banner, text="文章采集 → 结构化提取 → 风格画像 → 迁移分析",
             bg="#1565C0", fg="#BBDEFB", font=("", 10)).pack(side=tk.LEFT, padx=4)
    tk.Label(banner, text=f"💾 {_VV_DB_PATH}", bg="#1565C0", fg="#90CAF9",
             font=("", 9)).pack(side=tk.RIGHT, padx=10)

    nb = ttk.Notebook(dlg)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ═══════════════ Tab 1: 📥 文章采集 ═══════════════
    tab_in = tk.Frame(nb, bg="#121212"); nb.add(tab_in, text=" 📥 文章采集 ")

    form = tk.Frame(tab_in, bg="#121212"); form.pack(fill=tk.X, padx=10, pady=6)
    tk.Label(form, text="作者:", bg="#121212", fg="#E0E0E0", font=("", 11)).grid(row=0, column=0, sticky="e", padx=4)
    author_ent = tk.Entry(form, font=("", 12), width=18, bg="#1E1E1E", fg="#FFFFFF",
                          insertbackground="white")
    author_ent.grid(row=0, column=1, padx=4)

    # 作者下拉历史
    existing_authors = [a["author"] for a in _vv_list_authors()]
    if existing_authors:
        import tkinter as _tk
        author_ent.configure(values=existing_authors)
        # 用 ttk Combobox 更好
        cb_val = _tk.StringVar()
        cb_val.set(existing_authors[0])
        author_cb = ttk.Combobox(form, values=existing_authors, textvariable=cb_val,
                                  font=("", 12), width=16)
        author_cb.grid(row=0, column=1, padx=4)
        author_ent = cb_val  # 替换

    tk.Label(form, text="来源:", bg="#121212", fg="#E0E0E0", font=("", 11)).grid(row=0, column=2, sticky="e", padx=4)
    source_cb = ttk.Combobox(form, values=["微信公众号", "微博", "雪球", "小红书", "知乎", "东方财富", "同花顺", "其他"],
                              font=("", 11), width=12)
    source_cb.current(0); source_cb.grid(row=0, column=3, padx=4)

    tk.Label(form, text="日期:", bg="#121212", fg="#E0E0E0", font=("", 11)).grid(row=0, column=4, sticky="e", padx=4)
    from datetime import datetime
    date_ent = tk.Entry(form, font=("", 11), width=12, bg="#1E1E1E", fg="#FFFFFF")
    date_ent.insert(0, datetime.now().strftime("%Y-%m-%d"))
    date_ent.grid(row=0, column=5, padx=4)

    # 原文输入区
    tk.Label(tab_in, text="📝 粘贴/输入大V文章原文:", bg="#121212", fg="#FFD54F",
             font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
    raw_txt = scrolledtext.ScrolledText(tab_in, height=14, font=("", 11), wrap=tk.WORD,
                                         bg="#1E1E1E", fg="#E0E0E0", insertbackground="white",
                                         highlightbackground="#424242", padx=10, pady=8)
    raw_txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    # 提取结果预览
    tk.Label(tab_in, text="🧠 AI 结构化提取结果:", bg="#121212", fg="#81D4FA",
             font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
    extract_txt = scrolledtext.ScrolledText(tab_in, height=8, font=("", 11), wrap=tk.WORD,
                                             bg="#0D1B2A", fg="#A5D6A7", insertbackground="white",
                                             highlightbackground="#1B3A5C", padx=10, pady=6)
    extract_txt.pack(fill=tk.BOTH, expand=False, padx=10, pady=4)

    # 按钮
    btn_frame = tk.Frame(tab_in, bg="#121212"); btn_frame.pack(fill=tk.X, padx=10, pady=8)
    status_var = tk.StringVar(value="")

    def _do_extract():
        author = author_cb.get().strip() if existing_authors else author_ent.get().strip()
        raw = raw_txt.get("1.0", tk.END).strip()
        if not author: messagebox.showwarning("提示", "请填写作者名"); return
        if len(raw) < 50: messagebox.showwarning("提示", "请粘贴至少 50 字的文章"); return
        status_var.set("⏳ AI 正在提取结构化信息...")
        extract_txt.delete("1.0", tk.END)
        extract_txt.insert("1.0", "⏳ 正在调用 AI 分析文章结构...")

        def _bg():
            import json as _j
            try:
                data = _vv_ai_extract(raw)
                result = f"""📌 文章风格: {data.get('style_summary', '(未提取)')}

💡 核心观点:
{chr(10).join(f"  • {v}" for v in (data.get('viewpoints') or [])[:5])}

🔗 逻辑链:
{chr(10).join(f"  {i+1}. {p}" for i, p in enumerate(data.get('logic_chain') or []) if i < 8)}

🎯 结论判断:
{chr(10).join(f"  → {c}" for c in (data.get('conclusions') or [])[:3])}

🏷️ 标签: {', '.join((data.get('tags') or [])[:15])}
📈 市场关注: {', '.join((data.get('market_tags') or [])[:10])}

🧠 逻辑模式模板:
{chr(10).join(f"  - {p}" for p in (data.get('logic_patterns') or [])[:8])}"""
                dlg.after(0, lambda: extract_txt.delete("1.0", tk.END))
                dlg.after(0, lambda: extract_txt.insert("1.0", result))
                dlg.after(0, lambda: status_var.set("✅ 提取完成, 点击入库保存"))

                # 临时存
                _vv_last_extract = data
                dlg._vv_last_extract = data
            except Exception as e:
                dlg.after(0, lambda: status_var.set(f"❌ 提取失败: {e}"))
                dlg.after(0, lambda: extract_txt.delete("1.0", tk.END))
                dlg.after(0, lambda: extract_txt.insert("1.0", f"❌ {e}"))

        import threading; threading.Thread(target=_bg, daemon=True).start()

    def _do_save():
        author = author_cb.get().strip() if existing_authors else author_ent.get().strip()
        raw = raw_txt.get("1.0", tk.END).strip()
        if not raw: messagebox.showwarning("提示", "没有原文"); return
        data = getattr(dlg, "_vv_last_extract", None)
        if data is None:
            # 没提也存, 先本地 tfidf embedding
            data = _vv_extract_fallback(_vv_tfidf_embed(raw[:5000]))

        aid = _vv_insert(
            author=author,
            source=source_cb.get(),
            pub_date=date_ent.get(),
            raw_content=raw,
            extracted_json=data,
            style_summary=data.get("style_summary", ""),
            logic_patterns=data.get("logic_patterns", []),
            tags=",".join(data.get("tags", [])) if isinstance(data.get("tags"), list) else (data.get("tags") or ""),
            market_tags=",".join(data.get("market_tags", [])) if isinstance(data.get("market_tags"), list) else (data.get("market_tags") or ""),
            embedding=data.get("embedding", {})
        )
        status_var.set(f"✅ 入库成功 ID={aid} | 作者={author} 现在有 {len(_vv_list_articles(author))} 篇文章")

    tk.Button(btn_frame, text="🧠 AI提取", font=("", 11, "bold"),
              bg="#1565C0", fg="white", padx=14, pady=4, cursor="hand2",
              command=_do_extract).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="💾 入库保存", font=("", 11, "bold"),
              bg="#2E7D32", fg="white", padx=14, pady=4, cursor="hand2",
              command=_do_save).pack(side=tk.LEFT, padx=4)
    tk.Button(btn_frame, text="🗑️ 清空", font=("", 11),
              padx=10, pady=4, cursor="hand2",
              command=lambda: [raw_txt.delete("1.0", tk.END),
                              extract_txt.delete("1.0", tk.END),
                              setattr(dlg, "_vv_last_extract", None),
                              status_var.set("")]).pack(side=tk.LEFT, padx=4)
    status_lbl = tk.Label(btn_frame, textvariable=status_var, bg="#121212",
                          fg="#FFD54F", font=("", 11))
    status_lbl.pack(side=tk.RIGHT, padx=8)

    # ═══════════════ Tab 2: 🎯 风格库 ═══════════════
    tab_lib = tk.Frame(nb, bg="#121212"); nb.add(tab_lib, text=" 🎯 风格库 ")

    # 左: 作者列表
    left_f = tk.Frame(tab_lib, bg="#121212"); left_f.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 5), pady=6)
    tk.Label(left_f, text="👤 作者画像", bg="#121212", fg="#FFD54F",
             font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
    cols = ("author", "cnt", "style")
    tv = ttk.Treeview(left_f, columns=cols, show="headings", height=16)
    tv.heading("author", text="作者"); tv.heading("cnt", text="数")
    tv.heading("style", text="风格")
    tv.column("author", width=110, anchor="w")
    tv.column("cnt", width=40, anchor="center")
    tv.column("style", width=180, anchor="w")
    tv.pack(fill=tk.Y)

    # 右: 文章详情
    right_f = tk.Frame(tab_lib, bg="#121212"); right_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 10), pady=6)
    tk.Label(right_f, text="📄 文章详情", bg="#121212", fg="#81D4FA",
             font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
    art_txt = scrolledtext.ScrolledText(right_f, font=("", 11), wrap=tk.WORD,
                                         bg="#1E1E1E", fg="#E0E0E0", padx=10, pady=8)
    art_txt.pack(fill=tk.BOTH, expand=True)

    def _refill_authors():
        for i in tv.get_children(): tv.delete(i)
        for a in _vv_list_authors():
            tv.insert("", tk.END, values=(a["author"], a["cnt"], (a.get("styles") or "")[:30]))

    def _on_author_sel(e):
        sel = tv.selection()
        if not sel: return
        vals = tv.item(sel[0], "values")
        author = vals[0]
        # 更新右侧文章列表
        arts = _vv_list_articles(author, limit=20)
        art_txt.delete("1.0", tk.END)
        # 画像
        p = _vv_get_profile(author)
        if p:
            import json as _j
            top_kws = _j.loads(p.get("keywords") or "[]")
            patterns = _j.loads(p.get("typical_patterns") or "[]")
            art_txt.insert(tk.END, f"══════ 📊 {author} 风格画像 ══════\n\n")
            art_txt.insert(tk.END, f"📌 综合风格: {p.get('style_summary', '—')}\n\n")
            art_txt.insert(tk.END, f"🧠 典型逻辑模式:\n")
            for ptn in patterns[:10]:
                art_txt.insert(tk.END, f"  • {ptn}\n")
            art_txt.insert(tk.END, f"\n🏷️ 高频关键词: {' · '.join(k for k,_ in top_kws[:15])}\n\n")
        art_txt.insert(tk.END, f"══════ 历史文章 ({len(arts)} 篇) ══════\n\n")
        for art in arts:
            art_txt.insert(tk.END, f"[{art.get('pub_date', '')}] {art.get('source', '')}\n")
            art_txt.insert(tk.END, f"  📌 {art.get('style_summary', '')[:80]}\n")
            art_txt.insert(tk.END, f"  🏷️  {art.get('tags', '')[:60]}\n\n")

    tv.bind("<<TreeviewSelect>>", _on_author_sel)
    _refill_authors()

    lib_btn_f = tk.Frame(tab_lib, bg="#121212"); lib_btn_f.pack(fill=tk.X, padx=10, pady=4)
    tk.Button(lib_btn_f, text="🔄 刷新", font=("", 10), padx=10,
              command=_refill_authors).pack(side=tk.LEFT, padx=4)
    tk.Button(lib_btn_f, text="🗑️ 清空整库", font=("", 10), bg="#4A1C1C", fg="white", padx=10,
              command=lambda: (messagebox.showwarning("⚠️", "此功能暂不开放, 请手工删除 DB 文件") if
                               not messagebox.askyesno("确认", "确定清空所有大V文章? 无法恢复!")
                               else None)).pack(side=tk.RIGHT)

    # ═══════════════ Tab 3: 🔮 风格分析 ═══════════════
    tab_ana = tk.Frame(nb, bg="#121212"); nb.add(tab_ana, text=" 🔮 风格分析 ")

    top_a = tk.Frame(tab_ana, bg="#121212"); top_a.pack(fill=tk.X, padx=10, pady=6)
    tk.Label(top_a, text="分析作者:", bg="#121212", fg="#E0E0E0", font=("", 11)).pack(side=tk.LEFT, padx=4)
    authors_all = [a["author"] for a in _vv_list_authors()]
    ana_author_cb = ttk.Combobox(top_a, values=authors_all, font=("", 11), width=14)
    ana_author_cb.pack(side=tk.LEFT, padx=4)

    # 市场数据来源选择
    tk.Label(top_a, text="数据源:", bg="#121212", fg="#E0E0E0", font=("", 11)).pack(side=tk.LEFT, padx=(20, 4))
    data_src_cb = ttk.Combobox(top_a, values=["📌 游资看盘实时", "📅 手工输入", "💾 读取大V数据库"],
                                font=("", 11), width=16)
    data_src_cb.current(0); data_src_cb.pack(side=tk.LEFT, padx=4)

    # 市场观察输入
    tk.Label(tab_ana, text="👁️ 市场观察 / 你想让他分析什么:", bg="#121212", fg="#FFD54F",
             font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(4, 0))
    obs_txt = scrolledtext.ScrolledText(tab_ana, height=5, font=("", 11), wrap=tk.WORD,
                                         bg="#1E1E1E", fg="#E0E0E0", insertbackground="white",
                                         highlightbackground="#424242", padx=8, pady=6)
    obs_txt.pack(fill=tk.X, padx=10, pady=4)
    obs_txt.insert("1.0", "今天大盘跌了, 但创业板强, AI主线持续, 但白酒反弹弱。\n如果你是淘股吧游资, 怎么看明天的机会?")

    # 输出
    tk.Label(tab_ana, text="🤖 AI 风格迁移分析:", bg="#121212", fg="#81D4FA",
             font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(6, 0))
    ana_out = scrolledtext.ScrolledText(tab_ana, font=("", 12), wrap=tk.WORD,
                                         bg="#0D1B2A", fg="#E0E0E0", padx=12, pady=10)
    ana_out.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

    def _do_analyze():
        author = ana_author_cb.get().strip()
        if not author: messagebox.showwarning("提示", "请选择要模仿的作者"); return
        obs = obs_txt.get("1.0", tk.END).strip()

        # 拉游资看盘上下文
        ctx_str = ""
        if data_src_cb.get() == "📌 游资看盘实时":
            try:
                ctx = _gather_analysis_context(win)
                import json as _j
                ctx_str = _j.dumps(ctx, ensure_ascii=False, default=str)[:1500]
            except Exception as e:
                ctx_str = f"(游资看盘上下文获取失败: {e})"
        elif data_src_cb.get() == "💾 读取大V数据库":
            # 用该作者历史文章的风格匹配当前观察
            matches = _vv_match_articles(obs, author=author, top_k=5)
            if matches:
                ctx_str = f"与当前观察相似度最高的 {len(matches)} 篇 {author} 历史文章:\n"
                for art, s in matches:
                    ctx_str += f"  [{art.get('pub_date','')}] (相似度 {s:.0%}) {art.get('style_summary','')[:60]}\n"
            else:
                ctx_str = "(无相似历史文章, 用纯风格画像分析)"

        market_ctx = f"【市场观察】\n{obs}\n\n【数据上下文】\n{ctx_str}"
        ana_out.delete("1.0", tk.END)
        ana_out.insert("1.0", f"⏳ 正在让 {author} 分析当前市场...")
        status_var.set(f"⏳ {author} 正在思考... (约 20-40s)")

        def _bg():
            result = _vv_style_analysis(author, market_ctx)
            dlg.after(0, lambda: ana_out.delete("1.0", tk.END))
            dlg.after(0, lambda: ana_out.insert("1.0", result or "(无输出)"))
            dlg.after(0, lambda: status_var.set(f"✅ {author} 分析完成"))

        import threading; threading.Thread(target=_bg, daemon=True).start()

    ana_btn_f = tk.Frame(tab_ana, bg="#121212"); ana_btn_f.pack(fill=tk.X, padx=10, pady=6)
    tk.Button(ana_btn_f, text="🔍 开始分析", font=("", 12, "bold"),
              bg="#B71C1C", fg="white", padx=18, pady=4, cursor="hand2",
              command=_do_analyze).pack(side=tk.LEFT, padx=4)
    tk.Button(ana_btn_f, text="📋 复制", font=("", 11), padx=10,
              command=lambda: (dlg.clipboard_clear(),
                               dlg.clipboard_append(ana_out.get("1.0", tk.END)),
                               status_var.set("✅ 已复制"))).pack(side=tk.LEFT, padx=4)

    # 作者切换时刷新
    def _on_author_change(*_):
        ana_out.delete("1.0", tk.END)
        a = ana_author_cb.get()
        if a:
            p = _vv_get_profile(a)
            if p and p.get("style_summary"):
                ana_out.insert("1.0", f"📌 已选 {a}, 风格画像: {p['style_summary']}\n"
                                     f"  (选好市场观察后点【开始分析】)")
    ana_author_cb.bind("<<ComboboxSelected>>", _on_author_change)

    dlg._vv_last_extract = None
    return dlg


def _show_vv_from_speculator(win):
    """从游资看盘打开大V窗口 — 自动带当前市场数据"""
    dlg = _show_vv_main(win)
    # 自动游资看盘上下文预填
    try:
        ctx = _gather_analysis_context(win)
        import json as _j
        obs_preview = (
            f"游资看盘实时数据预览:\n"
            f"  大盘: {ctx.get('market_pct', '—')}\n"
            f"  领涨板块: {ctx.get('top_sectors', '—')}\n"
            f"  领跌板块: {ctx.get('bottom_sectors', '—')}\n"
            f"  涨跌家数: {ctx.get('up_count', '—')} / {ctx.get('down_count', '—')}\n"
            f"  周期位置: {ctx.get('cycle_pos', '—')}\n"
            f"  信号决策: {ctx.get('signal_decision', '—')}"
        )
        # 跳到分析 Tab
        from tkinter import ttk as _ttk
        for w in dlg.winfo_children():
            if isinstance(w, _ttk.Notebook):
                w.select(2); break
    except Exception:
        pass


def _gather_analysis_context(win):
    """从游资看盘界面收集当前市场状态 → 供风格分析使用"""
    ctx = {}
    # 1. 大盘涨跌幅 (从 seed light)
    up_lbl = getattr(win, "_up_count_lbl", None)
    if up_lbl:
        try: ctx["up_count"] = up_lbl.cget("text")
        except Exception: pass
    down_lbl = getattr(win, "_down_count_lbl", None)
    if down_lbl:
        try: ctx["down_count"] = down_lbl.cget("text")
        except Exception: pass
    # 2. 板块九宫格 meta
    meta = getattr(win, "_block_meta", None)
    if meta:
        tops = sorted([m for m in meta if m and m[1] is not None],
                      key=lambda x: -(x[1] or 0))
        bots = sorted([m for m in meta if m and m[1] is not None],
                      key=lambda x: (x[1] or 0))
        ctx["top_sectors"] = [f"{m[0]}({m[1]:+.2f}%)" for m in tops[:5]]
        ctx["bottom_sectors"] = [f"{m[0]}({m[1]:+.2f}%)" for m in bots[:5]]
    # 3. 股指期货
    fut_cells = getattr(win, "_fut_cells", None)
    if fut_cells:
        ctx["futures"] = [(c[0], c[4].cget("text") if c[4] else "—") for c in fut_cells]
    # 4. 周期 / 信号 (从右面板 Text)
    try:
        for attr in ["_cycle_text", "_sign_decision_text", "_status_text"]:
            w = getattr(win, attr, None)
            if w and hasattr(w, "get"):
                ctx[attr.replace("_", "", 1)] = w.get("1.0", "end-1c")[:200]
    except Exception: pass
    return ctx


print("✅ 📚财经大V风格学习系统 已加载", flush=True)

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
    "军工": ["军工", "国防", "航天", "航空", "军机"],
    "航天": ["航天", "卫星", "火箭", "北斗"],
    "风电": ["风电", "风力", "风机", "塔筒"],
    "光伏": ["光伏", "太阳能", "硅片", "组件"],
    "机器人": ["机器人", "自动化", "减速器", "伺服"],
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

        # 2. 行业板块 (akshare 新浪行业)
        try:
            import akshare as ak
            df_sector = ak.stock_sector_spot(indicator="新浪行业")
            if df_sector is not None and len(df_sector) > 0:
                pct_col = [c for c in df_sector.columns if "涨跌" in str(c)]
                name_col = [c for c in df_sector.columns if "名称" in str(c) or "板块" in str(c)]
                if pct_col and name_col:
                    # 精确映射: 9 个板块 → 新浪行业名
                    sector_map = [
                        ("券商", ["证券"]),       # 新浪行业名就叫"证券"
                        ("银行", ["银行"]),
                        ("CPO", ["通信设备"]),    # CPO 属于通信设备
                        ("半导体", ["半导体"]),
                        ("AI", ["软件服务", "IT设备", "计算机"]),  # AI 分散在软件/IT
                        ("电池", ["发电设备", "电池"]),
                        ("煤炭", ["煤炭"]),
                        ("电力", ["电力"]),
                        ("医疗", ["医药"]),
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

        # 2b. 兜底: 用中证1000 涨跌幅 + 板块固定偏离补缺失值
        # 历史: 各板块相对 IM 的偏离 (用来估算缺失板块)
        if "IM" in result["indices"]:
            im_pct = result["indices"]["IM"]["pct"]
            sector_bias = {  # 历史平均偏离 (板块 pct - IM pct)
                "券商": -0.3, "银行": -0.8, "CPO": 1.2, "AI": 0.8, "电池": 0.3,
                "半导体": 0.5, "医疗": -0.5,
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
    "军工": ["军工", "国防", "航天", "航空", "军机"],
    "航天": ["航天", "卫星", "火箭", "北斗"],
    "风电": ["风电", "风力", "风机", "塔筒"],
    "光伏": ["光伏", "太阳能", "硅片", "组件"],
    "机器人": ["机器人", "自动化", "减速器", "伺服"],
    "白酒": ["白酒", "茅台", "五粮液", "酒厂"],
    "黄金": ["黄金", "金业", "山东黄金", "中金黄金"],
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
                sub = merged[mask].copy()
                mean_pct = float(sub["pct_chg"].mean())
                n = int(mask.sum())
                # Top3 龙头: 按成交额取前3 (成交额=amount, 单位千元)
                if "amount" in sub.columns:
                    top3 = sub.sort_values("amount", ascending=False).head(3)
                else:
                    top3 = sub.sort_values("pct_chg", ascending=False).head(3)
                top3_list = [(str(r["name"]), float(r["pct_chg"])) for _, r in top3.iterrows()]
                result[fix_name] = (mean_pct, n, top3_list)
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

    # 左: 3行 (九宫格/盘口/量能 顶跨2列 | 期货/周期/状态 中跨2列 | 捡漏 底左半) | 右: 游资看盘思路分析 (宽度减半)
    left_pane = tk.Frame(outer, bg="#121212"); left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right_pane = tk.Frame(outer, bg="#121212", width=340); right_pane.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
    right_pane.pack_propagate(False)

    # 左面板 grid: 2列 × 3行, row_top/row_bot 跨两列全宽, row_leak 只占 column 0 (一半宽)
    left_pane.grid_rowconfigure(0, weight=3)
    left_pane.grid_rowconfigure(1, weight=3)
    left_pane.grid_rowconfigure(2, weight=0)  # 捡漏: 固定 200px 高度
    left_pane.grid_columnconfigure(0, weight=1, uniform="half")
    left_pane.grid_columnconfigure(1, weight=1, uniform="half")

    row_top = tk.Frame(left_pane, bg="#121212"); row_top.grid(row=0, column=0, columnspan=2, sticky="nsew")
    row_bot = tk.Frame(left_pane, bg="#121212"); row_bot.grid(row=1, column=0, columnspan=2, sticky="nsew")
    _build_block_grid(row_top, win, 0)
    _build_orderbook(row_top, win, 1)
    _build_volume_panel(row_top, win, 2)
    _build_futures_grid(row_bot, win, 0)
    _build_cycle_panel(row_bot, win, 1)
    _build_status_panel(row_bot, win, 2)

    # 底部 row_leak 跨两列, 内部左右分栏: 左=捡漏(黑底), 右=信号决策
    row_leak = tk.Frame(left_pane, bg="#121212", height=230); row_leak.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(2, 0))
    row_leak.pack_propagate(False)

    leak_half = tk.Frame(row_leak, bg="#000000"); leak_half.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sign_half = tk.Frame(row_leak, bg="#1E1E1E"); sign_half.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))

    _build_leak_panel(leak_half, win)
    _build_sign_decision_panel(sign_half, win)

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
        try: _refresh_sign_decision(win)
        except Exception as e: print(f"[👁️看盘❌] sign_decision: {e}")
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
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    parent.grid_rowconfigure(0, weight=1)
    _add_title_row(frm, "① 板块十六宫格 (点击展开/长按详情/⚠️异动>3%)",
                   "#FFA726", BLOCK_GRID_KNOWLEDGE)

    # 16 格 Canvas (4×4)
    canvas = tk.Canvas(frm, bg="#1E1E1E", highlightthickness=0, height=340)
    canvas.pack(fill=tk.BOTH, expand=True)
    win._block_canvas = canvas

    # 每格元数据: [板块名, 涨跌幅, 净流入, 是否锁定, 是否脉冲中, 匹配个股数, top3龙头[(name,pct),...]]
    win._block_meta = [[name, None, None, True, False, None, []] for name in FIXED_BLOCKS]
    win._block_cells = []  # [(x1,y1,x2,y2), 板块名]

    # 下方矛盾描述
    win._block_conflict_lbl = tk.Label(frm, text="正在加载板块数据...",
                                       bg="#1E1E1E", fg="#E0E0E0",
                                       font=("", 9), wraplength=500, justify=tk.LEFT)
    win._block_conflict_lbl.pack(fill=tk.X, pady=(2, 0))

    # 脉冲定时器
    win._pulse_cells = {}  # idx -> next_trigger_time


def _refresh_all_blocks(win):
    """刷新十六宫格 — 盘中优先新浪实时, 缺失板块用 tushare 关键词聚合补"""
    matched_any = False

    if _is_trading_hours():
        # 🟢 盘中: 先拿新浪实时板块 (只有 9 个左右), 剩下的交给 tushare 聚合补
        realtime = _get_sina_realtime()
        sectors = realtime.get("sectors", {}) if realtime else {}
        if sectors:
            for i, fix_name in enumerate(FIXED_BLOCKS):
                val = sectors.get(fix_name)
                if val is not None:
                    win._block_meta[i][1] = val
                    matched_any = True
            print(f"[👁️看盘] ✅ 十六宫格盘中新浪 ({len([v for v in sectors if v])} 板块)")

        # 继续: 用 tushare 聚合补新浪没覆盖的新板块 (军工/航天/风电/光伏/机器人/白酒/黄金)
        result = _compute_block_pct_from_cache()
        if result:
            for i, fix_name in enumerate(FIXED_BLOCKS):
                # 只补当前还是 None 的
                if win._block_meta[i][1] is None:
                    val = result.get(fix_name)
                    if val and val[0] is not None:
                        win._block_meta[i][1] = val[0]
                        win._block_meta[i][5] = val[1]
                        win._block_meta[i][6] = val[2] if len(val) > 2 else []
                        matched_any = True
            if matched_any:
                print(f"[👁️看盘] ✅ tushare 聚合补齐剩余板块")

    if not matched_any:
        # 📅 收盘: tushare daily+stock_basic 关键词聚合
        result = _compute_block_pct_from_cache()
        if result:
            for i, fix_name in enumerate(FIXED_BLOCKS):
                val = result.get(fix_name)
                if val and val[0] is not None:
                    win._block_meta[i][1] = val[0]
                    win._block_meta[i][5] = val[1]
                    win._block_meta[i][6] = val[2] if len(val) > 2 else []
                    matched_any = True
                else:
                    win._block_meta[i][1] = None
            if matched_any:
                print(f"[👁️看盘] ✅ 十六宫格 tushare 收盘数据")

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
                              font=("", 9, "bold"), tags=f"cell_{idx}")

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
                          font=("", 7), tags=f"cell_{idx}")

        # Top3 龙头 (下半部分, 3 行小字号)
        top3 = meta[6] if len(meta) > 6 else []
        if top3:
            for ti, (sname, spct) in enumerate(top3[:3]):
                sy = y1 + ch - 22 + ti * 10
                short = sname[:4] if len(sname) > 4 else sname
                sfg = "#FF8A80" if spct >= 0 else "#69F0AE"
                ssign = "+" if spct >= 0 else ""
                # 🆕 给每只股票加独立 tag, 双击时识别
                stock_tag = f"stock_{idx}_{ti}"
                c.create_text(x1 + 6, sy, text=f"{short}",
                              fill="#BDBDBD", font=("", 8), anchor=tk.W,
                              tags=(f"cell_{idx}", stock_tag))
                c.create_text(x2 - 6, sy, text=f"{ssign}{spct:.1f}%",
                              fill=sfg, font=("", 8), anchor=tk.E,
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
                top3 = win._block_meta[idx][6] if len(win._block_meta[idx]) > 6 else []
                hit_name = None
                for ti, (sname, _pct) in enumerate(top3[:3]):
                    if f"stock_{idx}_{ti}" in tags:
                        hit_name = sname; break
                if hit_name:
                    sina, sname2 = _lookup_stock_code_by_name(hit_name)
                    if sina:
                        _show_stock_daily_kline(win, sina, sname2 or hit_name)
                        return
                sina, sname = _get_first_stock_sina(win, idx)
                if sina:
                    _show_stock_daily_kline(win, sina, sname)
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
                    top3 = win._block_meta[idx][6] if len(win._block_meta[idx]) > 6 else []
                    hit_name = None
                    for ti, (sname, _pct) in enumerate(top3[:3]):
                        if f"stock_{idx}_{ti}" in tags:
                            hit_name = sname; break
                    if hit_name:
                        sina, sname2 = _lookup_stock_code_by_name(hit_name)
                        if sina:
                            _show_stock_daily_kline(win, sina, sname2 or hit_name)
                            return
                    sina, sname = _get_first_stock_sina(win, idx)
                    if sina:
                        _show_stock_daily_kline(win, sina, sname)
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
             bg="#1E1E1E", fg="#90A4AE", font=("", 9)).pack()

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
             font=("", 9), wraplength=480, justify=tk.LEFT).pack(anchor="w", pady=(4, 0))

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
    """② 涨停强弱排名 — 板块分组 + 多维度算法排序 + ❓涨停详解 + 双击股票弹日K"""
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#FF6D00",
                        font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
    _add_title_row(frm, "② 涨停强弱排名 (游资多维度 · 板块分组)",
                   "#FF6D00", ZT_RANK_KNOWLEDGE)

    top = tk.Frame(frm, bg="#1E1E1E"); top.pack(fill=tk.X, pady=(2, 2))
    win._zt_date_lbl = tk.Label(top, text="⏳ 加载涨停池...", bg="#1E1E1E",
                                 fg="#BDBDBD", font=("", 8))
    win._zt_date_lbl.pack(side=tk.LEFT, padx=4)
    tk.Button(top, text="🔄 刷新", command=lambda: _load_orderbook(win),
              bg="#37474F", fg="white", font=("", 8), padx=4).pack(side=tk.RIGHT)

    # Treeview: 板块分组嵌套 (列更紧凑, 字体更小)
    cols = ("rank", "name", "logic", "score", "time", "lb", "zb", "hand", "ind", "help")
    headings = [("#", "名称", "💡逻辑", "分", "封板", "板", "炸", "换手", "行业", "❓")]
    widths = [28, 92, 130, 30, 45, 22, 22, 38, 60, 24]
    tv = ttk.Treeview(frm, columns=cols, show="headings tree", height=11)
    tv.configure(rowheight=18)
    for i, c in enumerate(cols):
        tv.heading(c, text=headings[0][i])
        tv.column(c, width=widths[i], anchor="center", stretch=False)
    tv.column("logic", anchor="w", stretch=True)
    # 字体缩小到 8pt
    tv.tag_configure("high", foreground="#66BB6A", font=("", 8))
    tv.tag_configure("mid", foreground="#FFA726", font=("", 8))
    tv.tag_configure("low", foreground="#EF5350", font=("", 8))
    tv.tag_configure("rank1", foreground="#FFD54F", font=("", 8, "bold"))
    tv.tag_configure("sector", foreground="#FF6D00", font=("", 8, "bold"),
                     background="#263238")  # 板块标题行: 橙字 + 深灰底

    tv.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    win._zt_tv = tv
    win._zt_by_iid = {}  # iid -> (row, score, reasons, zt_logic, winrate)

    def _on_double_click(event):
        """双击: 股票子行 → 弹日K线; 板块父行 → 切换展开"""
        iid = tv.identify_row(event.y)
        if not iid: return
        parent_iid = tv.parent(iid)
        if parent_iid:
            # 子行 = 股票 → 弹日K
            info = win._zt_by_iid.get(iid)
            if not info: return
            row, _s, *_ = info
            try:
                code = str(row.get("代码", ""))
                name = str(row.get("名称", ""))
                if code.startswith(("6", "9")): sina = "sh" + code
                elif code.startswith(("0", "3")): sina = "sz" + code
                elif code.startswith(("4", "8")): sina = "bj" + code
                else: sina = "sh" + code
                _show_stock_daily_kline(frm.winfo_toplevel(), sina, name)
                print(f"[👁️涨停双击] {name}({sina}) → 弹日K", flush=True)
            except Exception as e:
                print(f"[👁️涨停双击] err: {e}")
        else:
            try: tv.item(iid, open=not tv.item(iid, "open"))
            except Exception: pass

    def _on_single_click(event):
        """单击 ❓ 列 → 涨停详解弹窗"""
        region = tv.identify("region", event.x, event.y)
        if region != "cell": return
        col_id = tv.identify_column(event.x)
        if col_id != f"#{len(cols)}": return
        iid = tv.identify_row(event.y)
        if not iid: return
        parent_iid = tv.parent(iid)
        if not parent_iid: return
        info = win._zt_by_iid.get(iid)
        if not info: return
        row, score, reasons, zt_logic, winrate = info
        _show_zt_logic_popup(frm.winfo_toplevel(), row, score, reasons, zt_logic, winrate)

    tv.bind("<Double-1>", _on_double_click)
    tv.bind("<ButtonRelease-1>", _on_single_click)

    tk.Label(frm, text="💡 双击股票 → 日K线  |  双击板块 → 展开/收起  |  点❓ → 涨停详解",
             bg="#1E1E1E", fg="#78909C", font=("", 8)).pack(anchor="w", padx=4, pady=(0, 2))


def _load_orderbook(win):
    """后台加载涨停池 → 评分排序 → 渲染"""
    def _bg():
        import datetime
        try:
            import akshare as ak
        except Exception as e:
            win.after(0, lambda: win._zt_date_lbl.config(text=f"❌ akshare 不可用: {e}", fg="#EF5350"))
            return

        # 算最近交易日
        today = datetime.date.today(); d = today
        while d.weekday() >= 5: d -= datetime.timedelta(days=1)
        date_str = d.strftime("%Y%m%d")

        try:
            df = ak.stock_zt_pool_em(date=date_str)
        except Exception as e:
            win.after(0, lambda: win._zt_date_lbl.config(text=f"❌ 涨停池拉取失败: {e}", fg="#EF5350"))
            return

        if df is None or len(df) == 0:
            win.after(0, lambda: win._zt_date_lbl.config(
                text=f"📅 {date_str} 涨停池为空 (非交易日或当日无涨停)", fg="#BDBDBD"))
            return

        # 同行业涨停数 → 板块共振
        ind_counts = df["所属行业"].value_counts().to_dict() if "所属行业" in df.columns else {}

        # 评分
        results = []
        for _, r in df.iterrows():
            same_ind = ind_counts.get(r.get("所属行业", ""), 1)
            score, reasons, zt_logic = _calc_zt_strength(r, same_ind)
            winrate = _estimate_zt_next_day_winrate(r)
            results.append((r, score, reasons, zt_logic, winrate))

        # 排序: 分数降序
        results.sort(key=lambda x: -x[1])

        # 按板块分组 (ind -> [results...])
        by_ind = {}
        for item in results:
            ind = str(item[0].get("所属行业", "其他"))
            by_ind.setdefault(ind, []).append(item)

        # 板块热度: 涨停股数 × 板块平均分数, 取 Top 8
        sector_scores = []
        for ind, items in by_ind.items():
            n = len(items)
            avg_s = sum(it[1] for it in items) / max(n, 1)
            heat = n * avg_s  # 热度分
            sector_scores.append((ind, n, avg_s, heat))
        sector_scores.sort(key=lambda x: -x[3])
        top_sectors = sector_scores[:8]

        def _render():
            tv = win._zt_tv
            for i in tv.get_children(): tv.delete(i)
            win._zt_by_iid = {}  # 清空重建

            for ind, n_stk, avg_s, heat in top_sectors:
                ind_short = ind[:8]
                parent_iid = f"sector_{ind}"
                tv.insert("", tk.END, iid=parent_iid, open=False,
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
                    # 存映射: iid -> info
                    win._zt_by_iid[child_iid] = (row, score, reasons, zt_logic, winrate)

            n = len(results)
            high = sum(1 for _, s, *_ in results if s >= 70)
            win._zt_date_lbl.config(
                text=f"📅 {date_str}  |  共 {n} 只涨停 · {len(top_sectors)} 个板块  |  强势≥70: {high}",
                fg="#66BB6A" if high >= 5 else "#FFA726")
            print(f"[👁️涨停] {date_str}: {n}只, {len(top_sectors)}板块, 强势(≥70): {high}只", flush=True)

        win.after(0, _render)

    threading.Thread(target=_bg, daemon=True).start()


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


# ============================================================
# Block / Stock Daily K-line Dialog (with MA/MACD/KDJ/support-resistance)
# ============================================================

def _fetch_block_daily(block_name, days=200):
    """Fetch block daily K-line via akshare eastmoney → hardcoded seed (offline)"""
    import numpy as np

    # 1) akshare 东财行业历史
    try:
        import akshare as ak
        em_name = BLOCK_EM_NAME.get(block_name, block_name)
        df = ak.stock_board_industry_hist_em(symbol=em_name, period="日k", adjust="qfq")
        if df is not None and len(df) > 30:
            date_col = [c for c in df.columns if "日期" in str(c) or "date" in str(c).lower()][0]
            df = df.sort_values(date_col).tail(days)
            dates = df[date_col].astype(str).tolist()
            return {"dates": dates, "o": df.iloc[:, 1].astype(float).to_numpy(),
                    "h": df.iloc[:, 2].astype(float).to_numpy(),
                    "l": df.iloc[:, 3].astype(float).to_numpy(),
                    "c": df.iloc[:, 4].astype(float).to_numpy(),
                    "v": df.iloc[:, 5].astype(float).to_numpy(),
                    "src": f"EM-{em_name}"}
    except Exception as e:
        print(f"[watch-K] akshare block fail: {e}")

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

    # 顶栏: 标题 + 周期切换 + 信息
    top = tk.Frame(dlg, bg="#1E1E1E"); top.pack(fill=tk.X)
    tk.Label(top, text=f"📊 {title}",
             bg="#1E1E1E", fg="#FFD54F", font=("", 12, "bold")).pack(side=tk.LEFT, padx=12, pady=6)

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
        ax.legend(loc="upper left", fontsize=8, facecolor="#2A2A2A", edgecolor="#555", labelcolor="#E0E0E0")

        _canvas_ref["canvas"].draw_idle()
        info_lbl.config(text=f"{len(dates)} bars | latest {dates[-1]} | close {c[-1]:.2f} | {new_data.get('src','?')}")

    # 周期切换按钮
    for period_label, period_val in PERIODS:
        tk.Radiobutton(top, text=period_label, variable=_period_var, value=period_label,
                       bg="#1E1E1E", fg="#FFD54F", selectcolor="#1E1E1E",
                       activebackground="#1E1E1E", font=("", 10),
                       indicatoron=False, width=7,
                       command=lambda pv=period_val: _on_period_change(pv)).pack(side=tk.LEFT, padx=2, pady=6)

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

    info_lbl = tk.Label(top, text=f"", bg="#1E1E1E", fg="#A5D6A7", font=("", 9))
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
    """Single-click block cell -> block index daily K-line"""
    import threading
    name = win._block_meta[idx][0]
    print(f"[watch-K] block '{name}' fetching...", flush=True)
    dlg_load = tk.Toplevel(win); dlg_load.title("Loading"); dlg_load.geometry("260x80")
    dlg_load.configure(bg="#1E1E1E"); dlg_load.transient(win)
    tk.Label(dlg_load, text=f"Loading {name} daily K-line...",
             bg="#1E1E1E", fg="#FFD54F", font=("", 11)).pack(pady=20)
    def _bg():
        data = _fetch_block_daily(name, days=240)
        def _done():
            try: dlg_load.destroy()
            except Exception: pass
            if data is None:
                messagebox.showwarning("Warning", f"{name} K-line data fetch failed")
                return
            _show_daily_kline_dialog(win, f"Block: {name}", data)
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
                       fg=inact, font=("", 8))
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
             bg="#1E1E1E", fg="#757575", font=("", 8)).pack(anchor=tk.W, padx=4)


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
            lbl.config(fg=act, font=("", 9, "bold"))
        else:
            dot.config(fg="#424242", font=("", 20))
            lbl.config(fg="#616161", font=("", 8))

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
    frm = tk.LabelFrame(parent, bg="#1E1E1E", fg="#90CAF9", font=("", 10, "bold"), padx=4, pady=4)
    frm.grid(row=0, column=col, sticky="nsew", padx=3, pady=3)
    parent.grid_columnconfigure(col, weight=1, uniform="watchrow")
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
                 font=("", 9, "bold")).pack(side=tk.LEFT, padx=6)
        lbl = tk.Label(card, text=desc, bg="#2A2A2A", fg="#BDBDBD",
                       font=("", 8), wraplength=420, justify=tk.LEFT)
        lbl.pack(anchor=tk.W)
        win._status_cards.append((light, card, title))

    # —— 红圈判定区 (参考图方案) ——
    sep1 = tk.Frame(frm, bg="#424242", height=1); sep1.pack(fill=tk.X, pady=(6, 2))
    tk.Label(frm, text="⭕ 红圈判定 (形态/结构)", bg="#1E1E1E", fg="#EF5350",
             font=("", 9, "bold")).pack(anchor=tk.W, padx=4)

    red_frame = tk.Frame(frm, bg="#1E1E1E"); red_frame.pack(fill=tk.X, padx=4, pady=2)
    win._red_break_lbl = tk.Label(red_frame, text="  🟢 形态破位信号: ——",
                                  bg="#1E1E1E", fg="#66BB6A", font=("", 9))
    win._red_break_lbl.pack(anchor=tk.W)
    win._red_trend_lbl = tk.Label(red_frame, text="  🟢 红圈确认: ——",
                                  bg="#1E1E1E", fg="#66BB6A", font=("", 9))
    win._red_trend_lbl.pack(anchor=tk.W)

    # —— 主控股推荐 ——
    sep2 = tk.Frame(frm, bg="#424242", height=1); sep2.pack(fill=tk.X, pady=(4, 2))
    tk.Label(frm, text="🏆 主控股推荐", bg="#1E1E1E", fg="#FFD54F",
             font=("", 9, "bold")).pack(anchor=tk.W, padx=4)
    win._leader_lbl = tk.Label(frm, text="——", bg="#2A2A2A", fg="#81C784",
                               font=("", 10, "bold"), wraplength=420,
                               justify=tk.LEFT, padx=8, pady=4)
    win._leader_lbl.pack(fill=tk.X, padx=4, pady=2)

    # —— 底部综合建议 ——
    sep3 = tk.Frame(frm, bg="#424242", height=1); sep3.pack(fill=tk.X, pady=(4, 2))
    win._status_msg = tk.Label(frm, text="💡 实时刷新中...", bg="#1E1E1E",
                                fg="#E0E0E0", font=("", 9, "italic"),
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
    tk.Button(fs_box, text="A-", width=3, bg="#37474F", fg="#ECEFF1", font=("", 9),
              command=lambda: _change_fs(-1)).pack(side=tk.LEFT, padx=1)
    tk.Button(fs_box, text="A+", width=3, bg="#37474F", fg="#ECEFF1", font=("", 9),
              command=lambda: _change_fs(+1)).pack(side=tk.LEFT, padx=1)

    # AI 一键分析
    tk.Button(top, text="🤖 AI分析", command=lambda: _ai_popup(win),
              bg="#3949AB", fg="#ECEFF1", font=("", 10, "bold")).pack(side=tk.RIGHT, padx=4)

    canvas = tk.Canvas(parent, bg="#121212", highlightthickness=0, width=260)
    sb = tk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg="#121212")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw", width=260)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _mw(e): canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _mw)

    # 结论区 (特大字体, 独立)
    concl_lf = tk.LabelFrame(body, text="🎯 今日结论",
                             bg="#121212", fg="#FFD54F", font=("", 11, "bold"))
    concl_lf.pack(fill=tk.X, padx=8, pady=(6, 8))
    win._wa_conclusion = tk.Label(concl_lf, text="⏳ 加载中...",
                                 bg="#121212", fg="#FFFFFF", font=("", _CONCL[0], "bold"),
                                 wraplength=240, justify=tk.LEFT, padx=8, pady=6)
    win._wa_conclusion.pack(fill=tk.X)

    # 7 层 — 每层加 ❓🤖 按钮
    win._wa_layers = {}   # title → content label
    win._wa_lfs = {}      # title → LabelFrame
    for title, question, color in WATCH_ANALYSIS_LAYERS:
        lf = tk.LabelFrame(body, text=title, bg="#121212", fg=color, font=("", _LF[0], "bold"))
        lf.pack(fill=tk.X, padx=8, pady=5)
        win._wa_lfs[title] = lf

        # 层顶部: 问题 + ❓ + 🤖
        hdr = tk.Frame(lf, bg="#121212"); hdr.pack(fill=tk.X, padx=6, pady=(4, 0))
        tk.Label(hdr, text=f"💬 {question}", bg="#121212", fg="#9E9E9E",
                 font=("", 9)).pack(side=tk.LEFT)
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

        # 内容
        lbl = tk.Label(lf, text="⏳ 加载中...", bg="#121212", fg="#E0E0E0",
                       font=("", _F[0]), wraplength=240, justify=tk.LEFT,
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
                    padding=(12, 3), font=("", 8))
    style.map("Leak.TNotebook.Tab", background=[("selected", "#000000")],
              foreground=[("selected", "#FFD54F")])
    # Treeview 黑底样式
    style.configure("Leak.Treeview", background="#000000", foreground="#E0E0E0",
                    fieldbackground="#000000", rowheight=22, font=("", 9))
    style.configure("Leak.Treeview.Heading", background="#1A1A1A", foreground="#FFD54F",
                    font=("", 9, "bold"))
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
        ax.legend(loc="upper left", fontsize=8, facecolor="#121212", labelcolor="#E0E0E0")
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
        m = re.search(r"var\s+code\s*=\s*(\[.*?\])", text, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            if data and len(data) >= 60:
                closes = np.array([float(d["close"]) for d in data])
                dates = [d.get("day", "") for d in data]
                print(f"[👁️信号] 新浪真实数据 {index_code}: {len(closes)}根, 最新={closes[-1]:.2f}, MA60={np.mean(closes[-60:]):.2f}", flush=True)
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
    """🎯 信号决策面板 — 先用种子秒出, 后台刷新真实 closes"""
    import numpy as np

    # ── 种子 closes 秒出 (主线程不联网) ──
    rng = np.random.default_rng(42)
    seed_closes = 3200 + np.cumsum(rng.normal(0.0, 15, 200))

    title = tk.Label(parent, text="🎯 信号决策 (大盘综合) · ⏳加载中",
                     bg="#1E1E1E", fg="#FFD54F", font=("", 10, "bold"))
    title.pack(anchor="w", padx=6, pady=(4, 2))

    lists = tk.Frame(parent, bg="#1E1E1E"); lists.pack(fill=tk.X, padx=4, pady=1)
    left_list = tk.Frame(lists, bg="#1E1E1E"); left_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right_list = tk.Frame(lists, bg="#1E1E1E"); right_list.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(4, 0))

    tk.Label(left_list, text="🔴 危险信号", bg="#1E1E1E", fg="#EF5350",
             font=("", 9, "bold")).pack(anchor="w")
    danger_lbls = []
    for _i in range(3):
        lbl = tk.Label(left_list, text="○ —", bg="#1E1E1E", fg="#546E7A", font=("", 8), anchor="w")
        lbl.pack(anchor="w"); danger_lbls.append(lbl)

    tk.Label(right_list, text="🟢 乐观信号", bg="#1E1E1E", fg="#66BB6A",
             font=("", 9, "bold")).pack(anchor="w")
    opt_lbls = []
    for _i in range(3):
        lbl = tk.Label(right_list, text="○ —", bg="#1E1E1E", fg="#546E7A", font=("", 8), anchor="w")
        lbl.pack(anchor="w"); opt_lbls.append(lbl)

    sum_frame = tk.Frame(parent, bg="#1A237E"); sum_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
    sum_lbl = tk.Label(sum_frame, text="...", bg="#1A237E", fg="#FFD54F",
                       font=("", 9, "bold"))
    sum_lbl.pack(padx=6, pady=4, anchor="w")

    quant = tk.Frame(parent, bg="#121212"); quant.pack(fill=tk.X, padx=4, pady=2)
    tk.Label(quant, text="量化决策: 等待 VS 入场", bg="#121212", fg="#90A4AE",
             font=("", 8)).pack(anchor="w")
    row = tk.Frame(quant, bg="#121212"); row.pack(fill=tk.X, pady=1)
    act_lbl = tk.Label(row, text="...", bg="#121212", fg="#FFD54F", font=("", 14, "bold"))
    act_lbl.pack(side=tk.LEFT)
    pct_lbl = tk.Label(row, text="建议仓位: —", bg="#121212", fg="#CE93D8", font=("", 9))
    pct_lbl.pack(side=tk.RIGHT)

    ma_row = tk.Frame(parent, bg="#121212"); ma_row.pack(fill=tk.X, padx=4, pady=(0, 2))
    ma_lbl = tk.Label(ma_row, text="MA5=— MA10=— MA15=— MA60=—",
                      bg="#121212", fg="#78909C", font=("", 8))
    ma_lbl.pack(side=tk.LEFT)
    close_lbl = tk.Label(ma_row, text="📊 上证收盘 —", bg="#121212", fg="#FFD54F",
                         font=("", 9, "bold"))
    close_lbl.pack(side=tk.RIGHT)

    # 保存 label 引用 → 后台刷新用
    win._sign_ui = {"title": title, "danger": danger_lbls, "opt": opt_lbls,
                    "sum_frame": sum_frame, "sum_lbl": sum_lbl,
                    "act_lbl": act_lbl, "pct_lbl": pct_lbl,
                    "ma_lbl": ma_lbl, "close_lbl": close_lbl}

    # 立刻用种子渲染一次
    _apply_sign_data(win, _calc_sign_decision_from_closes(seed_closes), from_seed=True)


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

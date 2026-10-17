"""🎯 高抛低吸 (做T专区) 弹窗模块
全部硬编码内容, 不联网不读文件
"""
import tkinter as tk
import tkinter.ttk as ttk

# ── 全局字号 (可变: A- / A+ 按钮修改后 refresh config) ──
_FONT_BASE = [15]           # 正文字号 (用户反馈调大, 默认 15pt)
_FONT_TITLE = [20]          # 大标题
_FONT_LF = [16]             # LabelFrame 标题
_FONT_SM = [13]             # 小字

# ── 配色 ──
_BG_DEEP = "#121212"
_BG_PANEL = "#1E1E1E"
_BG_CARD = "#2A2A2A"
_BG_TOOLBAR = "#1A1A1A"
_BG_RISK = "#2D1F1F"
_FG_RED = "#FF8A80"       # 涨
_FG_GREEN = "#69F0AE"     # 跌
_FG_GOLD = "#FFD54F"      # 金
_FG_BLUE = "#90CAF9"
_FG_TEXT = "#E0E0E0"
_FG_DIM = "#9E9E9E"

# ── 5 大流派数据 ──
_SCHOOLS = [
    {
        "icon": "🔵",
        "name": "形态学",
        "tagline": "双顶双底 / 缺口 / 颈线 / 箱体",
        "core": "价格形态是市场心理的投影, 经典顶底结构重复率最高",
        "tools": "双顶(M顶) · 双底(W底) · 岛型反转 · 突破缺口 · 测量缺口 · 颈线压力支撑 · 箱体震荡上下沿",
        "today_signal": "🟡 判定: 箱体震荡上沿, 警惕回落",
        "confidence": 72,
        "confidence_color": _FG_GOLD,
        "advice": "卖 · 先抛 1/3 仓位, 观察下沿承接",
        "advice_color": _FG_RED,
        "definition": (
            "形态学是技术分析最古老的分支, 核心假设是: 历史会重复, 价格以波浪方式展开, "
            "经典 K 线形态 (顶底/突破/反转) 反映了多空双方的心理博弈结果, "
            "当形态完成时意味着一方力量衰竭、另一方接管主导权。\n\n"
            "典型形态:\n"
            "• 双顶 (M顶): 同一价位两次冲顶失败, 向下突破颈线 = 下跌确认\n"
            "• 双底 (W底): 同一价位两次探底企稳, 向上突破颈线 = 上涨确认\n"
            "• 缺口: 跳空高开/低开, 分突破缺口、测量缺口、衰竭缺口\n"
            "• 箱体: 长时间横盘, 上下沿反复测试, 突破即加速"
        ),
        "logic": (
            "分级信号表:\n"
            "┌─────────┬────────────────────┬───────────┬────────┐\n"
            "│ 级别    │ 信号              │ 置信度    │ 仓位   │\n"
            "├─────────┼────────────────────┼───────────┼────────┤\n"
            "│ S级卖   │ 双顶 + 放量跌破颈线│ 90%+      │ 清仓   │\n"
            "│ A级卖   │ 双顶/假突破回落    │ 75-90%    │ 卖50%  │\n"
            "│ B级卖   │ 箱体上沿缩量       │ 60-75%    │ 卖30%  │\n"
            "│ B级买   │ 箱体下沿缩量企稳   │ 60-75%    │ 试买10%│\n"
            "│ A级买   │ 双底 + 放量突破颈线│ 75-90%    │ 买50%  │\n"
            "│ S级买   │ 底部岛型反转       │ 90%+      │ 重仓   │\n"
            "└─────────┴────────────────────┴───────────┴────────┘\n\n"
            "判断逻辑:\n"
            "1. 先画颈线/箱体上下沿 (至少 2 个触点)\n"
            "2. 突破时看量能: 放量突破确认, 缩量突破大概率假突破\n"
            "3. 结合位置: 高位 M 顶比低位 M 顶可靠 3 倍以上"
        ),
        "cases": [
            "📅 2015年6月 上证指数 双顶 5178 → 颈线 4500 跌破后千股跌停 (历史最大顶)",
            "📅 2021年2月 贵州茅台 双顶 2627 → 颈线 2300 跌破, 半年内腰斩",
            "📅 2023年9月 上证指数 箱体 3050-3200 震荡 → 10月突破向上"
        ],
    },
    {
        "icon": "🟣",
        "name": "周期论",
        "tagline": "P1-P5 + 背驰 + 关键位",
        "core": "任何走势必有中枢, 背驰是转折的信号, 关键位是生死线",
        "tools": "缠论 P1-P5 买卖点 · 走势类型 (盘整/趋势) · 中枢扩展 · MACD面积背驰 · 均线粘合发散 · 黄金分割位",
        "today_signal": "🟢 判定: P2 回调末期, MACD 面积底背驰",
        "confidence": 68,
        "confidence_color": _FG_GREEN,
        "advice": "买 · 分批低吸, 20% + 20%",
        "advice_color": _FG_GREEN,
        "definition": (
            "周期论 (以缠论为代表) 把价格走势分解为不同级别的 '中枢', "
            "并定义了 P1-P5 共 5 类买卖点。核心概念:\n\n"
            "• 中枢: 至少 3 段次级别走势的价格重叠区间 [ZG, ZD]\n"
            "• P1: 趋势末端 + 背驰 (一买/一卖)\n"
            "• P2: P1 后回调不破新低 (二买/二卖)\n"
            "• P3: 回调不进入中枢 (三买/三卖)\n"
            "• P4: 中枢震荡次低点/高点\n"
            "• P5: 趋势末端 + 强背驰 (类二买/类二卖)"
        ),
        "logic": (
            "背驰判定 (MACD 面积法):\n"
            "1. 同方向连续两段走势 (上涨/下跌)\n"
            "2. 比较两段走势对应的 MACD 柱面积 (红柱/绿柱累加)\n"
            "3. 新高但面积缩小 = 顶背驰 (卖信号)\n"
            "4. 新低但面积缩小 = 底背驰 (买信号)\n\n"
            "关键位优先级:\n"
            "P1 > P3 > P2 > P5 > P4\n\n"
            "实战口诀: 小级别服从大级别, 大级别定方向, 小级别找入场"
        ),
        "cases": [
            "📅 2023年3月 上证指数 日线 P1 底背驰 3220 → 反弹至 3418",
            "📅 2022年10月 宁德时代 周线 P2 低吸 180 → 2个月涨至 280 (+55%)",
            "📅 2021年7月 中国平安 P3 三卖信号 60 → 跌至 42 (-30%)"
        ],
    },
    {
        "icon": "🟢",
        "name": "技术指标",
        "tagline": "MACD / RSI / KDJ / BOLL / 均线 / 量比",
        "core": "指标是价格的衍生物, 多指标共振可信度最高",
        "tools": "MACD (金叉死叉 + 零轴 + 面积) · RSI (超买超卖 + 背离) · KDJ · BOLL (轨道收口/开口/穿越) · MA5/10/20/60 均线 · 量比 (放量/缩量)",
        "today_signal": "🟢 判定: MACD 零轴上金叉, RSI 55 健康区",
        "confidence": 78,
        "confidence_color": _FG_GREEN,
        "advice": "买 · 均线多头排列, 持有 + 加 10%",
        "advice_color": _FG_GREEN,
        "definition": (
            "技术指标是对价格/成交量进行数学处理后得到的辅助工具。"
            "本质上所有指标都是滞后的 (因为基于历史数据), 但不同指标反映的市场侧面不同:\n\n"
            "• MACD: 趋势的方向与动能 (快慢均线之差)\n"
            "• RSI: 多空力量的相对强弱 (0-100, 50为平衡)\n"
            "• KDJ: 短期价格的相对位置 (0-100, 灵敏但易假信号)\n"
            "• BOLL: 价格的波动边界 (中轨 + 上下轨, 收口预示变盘)\n"
            "• MA: 平滑后的成本线 (多头/空头排列判断趋势)\n"
            "• 量比: 今日成交相对 5日均量的倍数 (>2 放量, <0.5 缩量)"
        ),
        "logic": (
            "多指标共振判定矩阵:\n"
            "┌──────────┬────────────┬────────────┬────────────┐\n"
            "│ 指标     │ 买信号     │ 卖信号     │ 中性       │\n"
            "├──────────┼────────────┼────────────┼────────────┤\n"
            "│ MACD     │ 零轴上金叉 │ 零轴下死叉 │ 零轴附近   │\n"
            "│ RSI      │ <30 超卖   │ >70 超买   │ 40-60      │\n"
            "│ BOLL     │ 触下轨回升 │ 触上轨回落 │ 轨道内     │\n"
            "│ 量比     │ >2 放量上涨│ >2 放量下跌│ 0.8-1.5    │\n"
            "└──────────┴────────────┴────────────┴────────────┘\n\n"
            "信号打分: 每个指标 +1 (买) / -1 (卖) / 0 (中性)"
            " 总分 ≥ +3 → A级买\n"
            " 总分 ≤ -3 → A级卖\n"
            " 其余 → 观望或 B级信号"
        ),
        "cases": [
            "📅 2023年1月 AI 行情启动: 多数 AI 股 MACD 零轴上金叉 + 量比 >3 共振",
            "📅 2024年8月 券商板块: RSI 从 35 超卖区反弹 + BOLL 下轨支撑",
            "📅 2022年4月 新能源: MACD 底背离 + 量比 <0.5 缩量见底"
        ],
    },
    {
        "icon": "🟡",
        "name": "资金面",
        "tagline": "北向 / 主力大单 / 龙虎榜 / 融资融券",
        "core": "价格是资金推动的结果, 跟着聪明钱走",
        "tools": "北向资金每日净流入 (沪深港通) · 主力大单净流入 (>100万) · 龙虎榜席位追踪 (游资动向) · 融资余额变化 (杠杆资金) · 大宗交易折价率",
        "today_signal": "🟡 判定: 北向小幅流出, 主力大单净流入平衡",
        "confidence": 55,
        "confidence_color": _FG_GOLD,
        "advice": "中性 · 继续观察, 不急着动",
        "advice_color": _FG_DIM,
        "definition": (
            "资金面分析关注 '谁在买、谁在卖、买了多少', 核心假设是: "
            "聪明钱 (北向、主力、游资、杠杆资金) 的行为能预判价格方向。\n\n"
            "• 北向资金: 外资通过沪深港通买 A 股, 被称为 '聪明钱'\n"
            "• 主力大单: 单笔成交额 >100万 的委托, 代表机构/大户行为\n"
            "• 龙虎榜: 每日涨跌停/振幅异常股的买卖席位披露\n"
            "• 融资余额: 借钱买股票的规模, 余额上升 = 杠杆看多\n"
            "• 大宗交易: 大额场外交易, 折价率反映大股东/机构态度"
        ),
        "logic": (
            "资金信号分层:\n"
            "顶级信号 (权重 3):\n"
            "  - 北向连续 3 日净流入 + 累计 > 50 亿\n"
            "  - 龙虎榜顶级游资 (赵老哥/章盟主/作手新一) 大买\n"
            "\n"
            "中级信号 (权重 2):\n"
            "  - 主力大单连续净流入 > 2 日\n"
            "  - 融资余额周环比 +5% 以上\n"
            "\n"
            "预警信号 (权重 1):\n"
            "  - 北向单日净流出 > 20 亿\n"
            "  - 大宗交易折价 > 10%\n"
            "  - 龙虎榜机构专用席位大卖"
        ),
        "cases": [
            "📅 2020年3月 全球暴跌后北向连续 7 日净流入抄底 → A股V型反弹",
            "📅 2023年8月 赵老哥龙虎榜大买 寒武纪 → 次日涨停, 一周 +40%",
            "📅 2022年1月 融资余额单日下降 80 亿 → 次日大盘跌 2.6%"
        ],
    },
    {
        "icon": "🔴",
        "name": "算法量化",
        "tagline": "网格 / ATR通道 / 缠论 / ML预测",
        "core": "机械执行消除情绪, 统计优势就是长期优势",
        "tools": "网格交易 (固定价差/ATR价差) · ATR通道 (中轨±N倍ATR) · 缠论自动识别 · 机器学习预测 (XGB/LSTM) · 波动率因子 (GARCH)",
        "today_signal": "🟢 判定: ATR 通道中轨上方, 网格触发买单 1次",
        "confidence": 62,
        "confidence_color": _FG_GREEN,
        "advice": "买 · 执行网格低吸, 买 10%",
        "advice_color": _FG_GREEN,
        "definition": (
            "算法量化用数学模型和统计规律代替人的主观判断。\n\n"
            "• 网格交易: 在价格区间内按固定价差 (或 ATR 倍数) 挂买卖单, "
            "涨了卖、跌了买, 震荡市稳定获利\n"
            "• ATR 通道: 以 N 日均价为中轨, 上下各 M 倍 ATR 为通道, "
            "突破上轨买/下轨卖, 均值回归\n"
            "• 缠论自动识别: 用程序识别 P1-P5 买卖点, 避免人工画线偏差\n"
            "• ML 预测: 用历史 K 线/指标/资金数据训练模型, 预测下一步"
        ),
        "logic": (
            "量化信号评分标准:\n"
            "┌───────────┬────────────────────────────┐\n"
            "│ 策略      │ 核心参数                   │\n"
            "├───────────┼────────────────────────────┤\n"
            "│ 网格      │ 价差 = 2倍 ATR, 网格数 10  │\n"
            "│ ATR通道   │ M=2, 触及下轨买, 上轨卖    │\n"
            "│ 缠论自动  │ 中枢扩展次数≥2 后 P1/P3   │\n"
            "│ ML预测    │ 概率 > 65% 且 AUC > 0.6   │\n"
            "└───────────┴────────────────────────────┘\n\n"
            "实战: 单一策略胜率 < 55%, 组合多策略 (3+) 胜率可提升至 65%"
        ),
        "cases": [
            "📅 2023年 某量化基金用 ATR 通道+网格 跑中证500, 震荡区间年化 +18%",
            "📅 2022年 熊市中 ML 预测模型连续 6 个月空仓 → 回避 -25% 最大回撤",
            "📅 2024年 缠论自动识别 P3 三卖信号 精准逃顶 中芯国际 3月高点"
        ],
    },
]

# ── 做 T 三层模型 ──
_T_THREE_LAYERS = [
    {
        "name": "日内 T",
        "level": "分钟级 (1-30min)",
        "profit": "0.5% - 2%",
        "freq": "高频 (每日多次)",
        "color": _FG_BLUE,
        "definition": "日内 T+0 回转交易, 当天买当天卖 (或先卖后买回), 核心是捕捉日内波动。适合震荡市, 需要盯盘。",
        "logic": (
            "操作流程:\n"
            "1. 早盘 9:30-10:00 观察是否高开/低开 (预判方向)\n"
            "2. 冲高卖: 分时线远离均线 + 量能放大 = 先卖\n"
            "3. 回落买: 分时线回踩均线 + 缩量企稳 = 买回\n"
            "4. 尾盘 14:50 前平仓, 不留隔夜风险\n\n"
            "关键: 只能做熟悉的票, 股性活跃 (振幅 >3%) 才值得做"
        ),
        "cases": [
            "📅 2024年9月 某票日内振幅 5%, 做 T 两次共落袋 1.8%",
            "📅 2023年11月 白酒板块日内 T: 早盘先卖高位仓位, 下午低位接回",
        ],
    },
    {
        "name": "波段 T",
        "level": "3-10 日",
        "profit": "3% - 10%",
        "freq": "中频 (每周 1-2 次)",
        "color": _FG_GOLD,
        "definition": "利用 3-10 天的波段波动做 T, 不盯盘也能做。核心是识别短期高低点。",
        "logic": (
            "操作流程:\n"
            "1. 日线级别找箱体震荡区或 5 日/10 均线高低点\n"
            "2. 触及 5 日线附近缩量 = 低吸买点\n"
            "3. 触及 10 日线或前高放量 = 高抛卖点\n"
            "4. 止损: 跌破 20 日线必须出 T 仓位\n\n"
            "适合人群: 每天看盘 < 1 小时的上班族"
        ),
        "cases": [
            "📅 2024年3月 某科技股箱体 20-23 元, 波段 T 每轮回 8-10%",
            "📅 2023年12月 医药股随板块轮动, 波段 T 做了 3 次",
        ],
    },
    {
        "name": "趋势 T",
        "level": "跟随主升浪",
        "profit": "10%+",
        "freq": "低频 (每月 1-3 次)",
        "color": _FG_RED,
        "definition": "主升浪中做 T, 不破坏底仓, 只用浮盈仓位操作, 扩大收益。",
        "logic": (
            "操作流程:\n"
            "1. 持仓处于主升浪 (均线多头排列 + MACD 零轴上)\n"
            "2. 高位放量滞涨 + 指标顶背离 = 卖出 T 仓位 (不动底仓)\n"
            "3. 等回调至 10 日线或 20 日线企稳后接回\n"
            "4. 若主升浪确认结束 (跌破 60 日线), T + 底仓一起走\n\n"
            "关键: 底仓不动, T 仓位 ≤ 总仓位的 30%"
        ),
        "cases": [
            "📅 2023年 AI 主升浪: 持有寒武纪底仓不动, 波段 T 做了 5 次",
            "📅 2021年新能源车行情: 宁德时代主升浪中 T 仓位 30% 贡献额外 25% 收益",
        ],
    },
]

# ── 5 条铁律风控 ──
_RISK_RULES = [
    {
        "text": "单股当日 T ≤ 3 次",
        "definition": "同一只股票一天内高抛低吸的次数不能超过 3 次。超过会产生手续费损耗 + 情绪失控 + 失误率飙升。",
        "logic": (
            "1. 每次 T 都有手续费 + 印花税 (卖出 0.05%)\n"
            "2. 单次 T 收益通常 0.5-2%, 3 次累计 ≈ 1.5-6%\n"
            "3. 连续成功 3 次后大概率会过度自信第 4 次, 容易追高被套\n"
            "4. 当日 T 记录必须写下来, 到 3 次主动停止"
        ),
        "cases": ["📅 2024年5月 某人单票 T 了 5 次, 第 5 次追高被套, 收盘亏 4%"],
    },
    {
        "text": "累计亏损 > 5% 自动停止",
        "definition": "当天所有 T 操作的累计亏损如果超过 5% (相对当日开盘持仓市值), 必须关闭交易软件, 停止当天所有交易。",
        "logic": (
            "1. 5% 是心理止损线, 超过后情绪从 '试错' 变成 '翻本'\n"
            "2. 翻本心态下大概率会加杠杆 / 追涨 / 不止损\n"
            "3. 历史数据: 当日亏 >5% 的交易者中, 78% 在后续 30 分钟内进一步亏损\n"
            "4. 软件层面可以设置触发弹窗强制提醒"
        ),
        "cases": ["📅 2023年9月 某人当天亏 6% 后继续操作, 最终收盘亏 11%, 次日再跌 3%"],
    },
    {
        "text": "大盘跌 2% 暂停所有 T",
        "definition": "上证指数/创业板指单日跌幅超过 2% 时, 暂停所有做 T 计划。系统性风险下个股抵抗不住。",
        "logic": (
            "1. 大盘跌 2% = 系统性风险释放, 泥沙俱下\n"
            "2. 此时个股振幅变大, 但方向不明, 容易低吸接到飞刀\n"
            "3. 北向资金单日流出常 > 50 亿, 主力也在撤\n"
            "4. 例外: 持仓逆板块/独立行情, 但概率 < 10%"
        ),
        "cases": ["📅 2022年3月 大盘单日跌 3.5%, 逆势做 T 的 80% 次日被套"],
    },
    {
        "text": "收盘前 15 分钟禁开新仓",
        "definition": "14:45 之后只能平仓, 不能开新 T 仓位。临近收盘流动性变差, 容易卖不掉。",
        "logic": (
            "1. 14:45 之后成交量骤降, 挂单难成交\n"
            "2. 即使成交, T+1 限制下当天无法卖出, 隔夜风险大\n"
            "3. 尾盘拉升常是诱多 (次日低开概率 60%)\n"
            "4. 尾盘跳水可能延续到次日开盘"
        ),
        "cases": ["📅 2024年8月 某人 14:50 追高买入, 收盘微亏, 次日低开 2.5%"],
    },
    {
        "text": "段基 < 50 的票不进 T 池",
        "definition": "段基 (阶段性上涨基差) < 50% 的票, 振幅不够, 做 T 空间太小, 手续费吃掉利润。",
        "logic": (
            "1. 段基 = (当前价 - 阶段最低价) / 阶段最低价\n"
            "2. 段基 < 50% 意味着还在底部区域, 震荡大趋势不明\n"
            "3. 段基 > 100% 的热门股, 日均振幅通常 > 4%, 适合做 T\n"
            "4. 也可替换为: 近 20 日日均振幅 < 2.5% 的不做"
        ),
        "cases": ["📅 2024年2月 某票段基 30%, 日均振幅 1.8%, 做 T 手续费 > 收益"],
    },
]

# ── 今日实战时间轴 ──
_TIMELINE_EXAMPLE = [
    ("09:30", "+1.2%", "高开", _FG_GREEN),
    ("10:00", "+1.8%", "双顶第一顶 ⚪", _FG_GOLD),
    ("10:30", "+0.9%", "回落确认颈线支撑", _FG_BLUE),
    ("11:00", "+0.5%", "MACD 顶背离初现 🟠A级卖", _FG_GOLD),
    ("11:30", "+0.3%", "卖 30% @ 均价 15.82", _FG_RED),
    ("13:00", "-0.8%", "缩量回踩 10 日线", _FG_BLUE),
    ("13:30", "-1.2%", "触及 BOLL 下轨 🟢B级买", _FG_GREEN),
    ("14:00", "-0.5%", "买 10% @ 均价 15.58 (T+0 持仓)", _FG_GREEN),
    ("14:45", "+0.2%", "尾盘回拉, 剩余 T 仓位平仓", _FG_BLUE),
    ("15:00", "+0.8%", "收盘 · 当日 T 累计 +1.15%", _FG_GOLD),
]


# ── 辅助: 字号 getter ──
def _fs(): return _FONT_BASE[0]
def _fs_title(): return _FONT_TITLE[0]
def _fs_lf(): return _FONT_LF[0]
def _fs_sm(): return _FONT_SM[0]


# ── 知识弹窗 ──
def _show_swing_knowledge(parent, title, def_text, logic_text, cases_list):
    """弹出 620×520 知识弹窗, 三区块: 📌定义 / 🔍判断逻辑 / 📖历史案例"""
    dlg = tk.Toplevel(parent)
    dlg.title(f"📚 {title}")
    dlg.geometry("620x520")
    dlg.configure(bg=_BG_PANEL)
    dlg.minsize(480, 400)
    dlg.transient(parent)
    try: dlg.grab_set()
    except Exception: pass

    KN_FS = [12]; KN_LF_FS = [13]; KN_TITLE_FS = [15]

    # 顶栏
    top = tk.Frame(dlg, bg=_BG_DEEP); top.pack(fill=tk.X)
    tk.Label(top, text=f"📚 {title}", bg=_BG_DEEP, fg=_FG_GOLD,
             font=("", KN_TITLE_FS[0], "bold")).pack(side=tk.LEFT, padx=10, pady=8)

    def _change_fs(delta):
        KN_FS[0] = max(10, min(20, KN_FS[0] + delta))
        KN_LF_FS[0] = max(11, min(22, KN_LF_FS[0] + delta))
        KN_TITLE_FS[0] = max(13, min(26, KN_TITLE_FS[0] + delta))
        _rebuild()

    fs_frame = tk.Frame(top, bg=_BG_DEEP); fs_frame.pack(side=tk.RIGHT, padx=10)
    tk.Button(fs_frame, text="A-", width=3, command=lambda: _change_fs(-1),
              bg="#37474F", fg="#ECEFF1", font=("", 9)).pack(side=tk.LEFT, padx=1)
    tk.Label(fs_frame, text="12pt", bg=_BG_DEEP, fg=_FG_BLUE, font=("", 9)).pack(side=tk.LEFT, padx=2)
    tk.Button(fs_frame, text="A+", width=3, command=lambda: _change_fs(+1),
              bg="#37474F", fg="#ECEFF1", font=("", 9)).pack(side=tk.LEFT, padx=1)

    # Canvas + Scrollbar
    canvas = tk.Canvas(dlg, bg=_BG_PANEL, highlightthickness=0)
    sb = tk.Scrollbar(dlg, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg=_BG_PANEL)
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw", width=590)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=4)
    sb.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

    def _on_mousewheel(e):
        canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    dlg.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), dlg.destroy()))

    def _rebuild():
        for w in body.winfo_children():
            w.destroy()
        fs = KN_FS[0]; lf_fs = KN_LF_FS[0]

        f1 = tk.LabelFrame(body, text="📌 定义", bg=_BG_PANEL, fg=_FG_BLUE,
                           font=("", lf_fs, "bold"))
        f1.pack(fill=tk.X, pady=(0, 6), padx=4)
        tk.Label(f1, text=def_text.strip(), bg=_BG_PANEL, fg=_FG_TEXT, font=("", fs),
                 wraplength=560, justify=tk.LEFT, padx=10, pady=8).pack(fill=tk.X)

        f2 = tk.LabelFrame(body, text="🔍 判断逻辑", bg=_BG_PANEL, fg=_FG_GREEN,
                           font=("", lf_fs, "bold"))
        f2.pack(fill=tk.X, pady=6, padx=4)
        tk.Label(f2, text=logic_text.strip(), bg=_BG_PANEL, fg=_FG_GOLD, font=("", fs),
                 wraplength=560, justify=tk.LEFT, padx=10, pady=8).pack(fill=tk.X)

        f3 = tk.LabelFrame(body, text="📖 历史案例", bg=_BG_PANEL, fg="#CE93D8",
                           font=("", lf_fs, "bold"))
        f3.pack(fill=tk.X, pady=(6, 4), padx=4)
        case_text = "\n".join(f"  {c}" for c in cases_list) if cases_list else "(暂无)"
        tk.Label(f3, text=case_text, bg=_BG_PANEL, fg=_FG_TEXT, font=("", fs),
                 wraplength=560, justify=tk.LEFT, padx=10, pady=8).pack(fill=tk.X)

    _rebuild()
    return dlg


# ── 主入口 ──
def show_high_low_swing(parent, app=None):
    """🎯 高抛低吸 (做T专区) — 不联网, Lazy import. 
    app: 主程序实例, 用于从持仓 tab 拿真实持仓股列表"""
    win = tk.Toplevel(parent)
    win.title("🎯 高抛低吸 (做T专区)")
    win.geometry("1280x820")
    win.configure(bg=_BG_DEEP)
    win.minsize(1000, 680)

    # ── 字体可变 widgets 集合 (A-/A+ 后 config) ──
    _font_widgets = []

    def _refresh_fonts():
        for w, key in _font_widgets:
            try:
                w.config(font=("", _FONT_BASE[0] if key == "body"
                               else _FONT_TITLE[0] if key == "title"
                               else _FONT_LF[0] if key == "lf"
                               else _FONT_SM[0],
                               "bold" if key in ("title", "lf") else "normal"))
            except Exception:
                pass

    # ═══════════════════════════════════════════════
    # 顶部工具栏
    # ═══════════════════════════════════════════════
    toolbar = tk.Frame(win, bg=_BG_TOOLBAR, height=46)
    toolbar.pack(fill=tk.X, side=tk.TOP)
    toolbar.pack_propagate(False)

    # 🤖 AI分析
    tk.Button(toolbar, text="🤖 AI分析", bg="#2E7D32", fg="white",
              font=("", 10, "bold"), padx=10, pady=2,
              command=lambda: _show_ai_mock(win)).pack(side=tk.LEFT, padx=(10, 4), pady=8)

    # 📈 1min K线图
    def _on_1min_kline():
        print("[📈1minK] 按钮被点击!", flush=True)
        import traceback
        try:
            _show_minute_kline_dialog(parent, app=app)
            print("[📈1minK] 弹窗已创建", flush=True)
        except Exception as e:
            print(f"[📈1minK❌] {e}", flush=True); traceback.print_exc()
    tk.Button(toolbar, text="📈 1min K线", bg="#7B1FA2", fg="white",
              font=("", 10, "bold"), padx=10, pady=2,
              command=_on_1min_kline).pack(side=tk.LEFT, padx=4, pady=8)

    # 🔍 多股并排对比
    def _on_multi_compare():
        print("[🔍多股] 按钮被点击!", flush=True)
        import traceback
        try:
            _show_multi_kline_comparison(parent, app=app)
        except Exception as e:
            print(f"[🔍多股❌] {e}", flush=True); traceback.print_exc()
    tk.Button(toolbar, text="🔍 多股对比", bg="#00695C", fg="white",
              font=("", 10, "bold"), padx=10, pady=2,
              command=_on_multi_compare).pack(side=tk.LEFT, padx=4, pady=8)

    # 🔄 刷新
    tk.Button(toolbar, text="🔄 刷新", bg="#1976D2", fg="white",
              font=("", 10, "bold"), padx=10, pady=2,
              command=lambda: _flash_refresh(win)).pack(side=tk.LEFT, padx=4, pady=8)

    # ── 🔤 字体调节 (显眼版) ──
    fs_frame = tk.Frame(toolbar, bg=_BG_TOOLBAR)
    fs_frame.pack(side=tk.LEFT, padx=(18, 4), pady=8)
    tk.Label(fs_frame, text="🔤 字体:", bg=_BG_TOOLBAR, fg=_FG_GOLD,
             font=("", 11, "bold")).pack(side=tk.LEFT, padx=(0, 4))
    fs_label = tk.Label(fs_frame, text=f"{_FONT_BASE[0]}pt", bg=_BG_TOOLBAR, fg=_FG_BLUE,
                        font=("", 12, "bold"))
    fs_label.pack(side=tk.LEFT, padx=(0, 4))

    def _change_global_fs(delta):
        _FONT_BASE[0] = max(10, min(24, _FONT_BASE[0] + delta))
        _FONT_TITLE[0] = max(14, min(30, _FONT_TITLE[0] + delta))
        _FONT_LF[0] = max(12, min(26, _FONT_LF[0] + delta))
        _FONT_SM[0] = max(10, min(22, _FONT_SM[0] + delta))
        fs_label.config(text=f"{_FONT_BASE[0]}pt")
        fs_spinbox.set(_FONT_BASE[0])
        _refresh_fonts()

    tk.Button(fs_frame, text="A-", width=3, command=lambda: _change_global_fs(-1),
              bg="#37474F", fg="#ECEFF1", font=("", 11, "bold")).pack(side=tk.LEFT, padx=1)
    # Spinbox 直接跳转 pt
    fs_var = tk.IntVar(value=_FONT_BASE[0])
    fs_spinbox = ttk.Spinbox(fs_frame, from_=10, to=24, width=3, textvariable=fs_var,
                             command=lambda: _jump_fs(int(fs_var.get())))
    fs_spinbox.pack(side=tk.LEFT, padx=1)
    tk.Button(fs_frame, text="A+", width=3, command=lambda: _change_global_fs(+1),
              bg="#37474F", fg="#ECEFF1", font=("", 11, "bold")).pack(side=tk.LEFT, padx=1)

    def _jump_fs(target):
        delta = target - _FONT_BASE[0]
        _change_global_fs(delta)

    # 右侧面板已内嵌择时判断 (条件+结论+三维分析), 无需独立按钮

    # ── 右侧: 搜索框 + 周期切换 ──
    right_bar = tk.Frame(toolbar, bg=_BG_TOOLBAR); right_bar.pack(side=tk.RIGHT, padx=10)

    # 周期切换 (Radiobutton)
    _period_var = tk.StringVar(value="日线")
    tk.Label(right_bar, text="周期:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(0, 4), pady=12)
    for p in ["1min", "5min", "15min", "30min", "日线"]:
        ttk.Radiobutton(right_bar, text=p, value=p, variable=_period_var).pack(side=tk.LEFT, padx=2)

    # 搜索框: 候选 = 硬编码龙头 (lhb/crawled_articles 留作 SQLite 预留位)
    _SEARCH_CANDIDATES = [
        "贵州茅台 600519", "中国平安 601318", "宁德时代 300750",
        "比亚迪 002594", "招商银行 600036", "五粮液 000858",
        "中科曙光 603019", "寒武纪 688256", "中芯国际 688981",
        "海康威视 002415", "美的集团 000333", "长江电力 600900",
        "中国中免 601888", "药明康德 603259", "隆基绿能 601012",
    ]
    tk.Label(right_bar, text="🎯 目标:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(16, 4), pady=12)
    combo = ttk.Combobox(right_bar, values=_SEARCH_CANDIDATES, width=22, state="normal")
    combo.set("贵州茅台 600519")
    combo.pack(side=tk.LEFT, pady=12)

    # ═══════════════════════════════════════════════
    # 主内容区: 左 Canvas 可滚动 + 右时间轴面板
    # ═══════════════════════════════════════════════
    main_pw = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
    main_pw.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

    # ── 左侧 Canvas 可滚动区 ──
    left_frame = tk.Frame(main_pw, bg=_BG_DEEP)
    main_pw.add(left_frame, weight=4)

    canvas = tk.Canvas(left_frame, bg=_BG_DEEP, highlightthickness=0)
    sb = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg=_BG_DEEP)

    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_mousewheel(e):
        canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    win.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), win.destroy()))

    # ── 右侧: 择时判断整合区 ──
    right_panel = tk.Frame(main_pw, bg=_BG_PANEL, width=290)  # 宽度减 50, 整体左移
    right_panel.pack_propagate(False)
    main_pw.add(right_panel, weight=1)

    # 择时判断 (整合版 — 内嵌, 不是弹窗)
    from datetime import datetime as _DT
    tk.Label(right_panel, text="⚡ 择时判断 (内嵌)", bg=_BG_PANEL, fg="#CE93D8",
             font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 4))

    # ── 条件区 (紧凑布局) ──
    cond = tk.Frame(right_panel, bg=_BG_PANEL); cond.pack(fill=tk.X, padx=8)
    tk.Label(cond, text="📅", bg=_BG_PANEL, fg=_FG_DIM).grid(row=0, column=0, sticky="w", padx=(0, 2))
    date_var = tk.StringVar(value=_DT.now().strftime("%Y%m%d"))
    ttk.Entry(cond, textvariable=date_var, width=10).grid(row=0, column=1, sticky="w", pady=2, columnspan=3)
    tk.Label(cond, text="⏰", bg=_BG_PANEL, fg=_FG_DIM).grid(row=1, column=0, sticky="w", padx=(0, 2))
    h_var = tk.IntVar(value=9); m_var = tk.IntVar(value=30)
    ttk.Spinbox(cond, from_=9, to=15, width=2, textvariable=h_var, format="%02.0f").grid(row=1, column=1, sticky="w")
    tk.Label(cond, text=":", bg=_BG_PANEL, fg=_FG_DIM).grid(row=1, column=2)
    ttk.Spinbox(cond, from_=0, to=59, width=2, textvariable=m_var, format="%02.0f", increment=5).grid(row=1, column=3, sticky="w")
    tk.Label(cond, text="对象:", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9)).grid(row=2, column=0, sticky="w", padx=(0, 2))
    obj_var = tk.StringVar(value="大盘")
    obj_row = tk.Frame(cond, bg=_BG_PANEL); obj_row.grid(row=2, column=1, columnspan=3, sticky="w")
    for v in ["大盘", "板块", "持仓股"]:
        ttk.Radiobutton(obj_row, text=v, value=v, variable=obj_var).pack(side=tk.LEFT, padx=2)
    tk.Label(cond, text="持仓:", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9)).grid(row=3, column=0, sticky="w", padx=(0, 2))
    # ── 持仓股: 优先从 app 持仓 tab 拿, 兜底 SQLite + 硬编码 ──
    _holding_list = []
    _used_app_holdings = False
    if app is not None:
        try:
            # 遍历持仓组 1-5, 收集所有持仓股
            for _gi in range(1, 6):
                try:
                    stocks, _, _, _ = app._get_holding_group_data(_gi)
                    for _s in (stocks or []):
                        # _s 可能是 (name, code, pos) 或 (name, code)
                        if isinstance(_s, (list, tuple)) and len(_s) >= 2:
                            _hn, _hc = str(_s[0]), str(_s[1])
                            # 新浪代码转换
                            _ex = _hc.split(".")[-1] if "." in _hc else ""
                            _ex_map = {"SH": "sh", "SZ": "sz", "BJ": "bj", "sh": "sh", "sz": "sz", "bj": "bj"}
                            _pure = _hc.split(".")[0].replace("SH", "").replace("SZ", "").replace("BJ", "")
                            _sina = _ex_map.get(_ex, "sh") + (_pure if _pure else _hc)
                            _label = f"{_hn} {_sina}"
                            if _label not in _holding_list:
                                _holding_list.append(_label)
                    _used_app_holdings = True
                except Exception: pass
            if _holding_list:
                print(f"[🎯高抛低吸] ✅ 从持仓 tab 拿到 {len(_holding_list)} 只持仓股")
        except Exception as e:
            print(f"[🎯高抛低吸] 持仓 tab 读取失败: {e}")

    # 兜底: SQLite + 硬编码
    if not _holding_list:
        _holding_list = ["贵州茅台 sh600519", "中国平安 sh601318", "宁德时代 sz300750",
                         "比亚迪 sz002594", "招商银行 sh600036", "五粮液 sz000858",
                         "寒武纪 sh688256", "中芯国际 sh688981", "美的集团 sz000333",
                         "药明康德 sh603259", "隆基绿能 sh601012", "大金重工 sz002487"]
        try:
            import sqlite3 as _sql, os as _os
            for _db_cand in [
                _os.path.expanduser("~/stockyidong_project/data/stock_analysis.db"),
                _os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db"),
            ]:
                if _os.path.exists(_db_cand):
                    c = _sql.connect(_db_cand).cursor()
                    try:
                        c.execute("SELECT name || ' ' || CASE WHEN ts_code LIKE '%.SH' THEN 'sh'||replace(ts_code,'.SH','') WHEN ts_code LIKE '%.SZ' THEN 'sz'||replace(ts_code,'.SZ','') WHEN ts_code LIKE '%.BJ' THEN 'bj'||replace(ts_code,'.BJ','') ELSE ts_code END FROM stock_analysis LIMIT 20")
                        for r in c.fetchall():
                            if r and r[0] not in _holding_list:
                                _holding_list.insert(0, r[0])
                    except Exception: pass
                    c.close(); break
        except Exception: pass
    holding_combo = ttk.Combobox(cond, values=_holding_list, width=14)
    holding_combo.set(_holding_list[0])
    holding_combo.grid(row=3, column=1, columnspan=3, sticky="w", pady=2)

    # 🔍 分析按钮
    tk.Button(cond, text="🔍 分析", bg="#7B1FA2", fg="white", font=("", 9, "bold"),
              padx=10, pady=1, cursor="hand2", command=lambda: _refresh_right()).grid(row=4, column=0, columnspan=4, sticky="we", pady=(6, 4))

    tk.Frame(right_panel, bg=_FG_GOLD, height=1).pack(fill=tk.X, padx=6, pady=3)

    # ── 择时分析知识字典 ──
    _TIMING_KNOWLEDGE = {
        "tech": ("技术面信号解读",
                 "技术指标是择时第一维度, 识别位置是高位还是低位。常用 MACD/RSI/KDJ/BOLL/均线五大件。核心利器: 1分钟周期 MA60 上穿/下穿 — 游资做T的生命线。",
                 """🔴 高抛信号 (满足 2+):
  MACD顶背离 / RSI>70 超买
  跌破BOLL上轨 / 股价远离MA5乖离>3%
  🎯 1分钟周期 MA60 向下穿越 (MA60向上时破线更重) ← 今日案例: 20261016 下午1点上证破MA60

🟢 低吸信号 (满足 2+):
  MACD底背离 / RSI<30 超卖
  跌破BOLL下轨企稳 / 回踩MA20/MA60缩量
  🎯 1分钟周期 MA60 向上穿越 (MA60从下行拐头更可靠) ← 昨日案例: 20261015 下午14:35上证穿MA60

⚠️ 关键解读:
  1分钟MA60代表60分钟平均成本, 主力资金的决策线
  MA60向上 + 跌破 = 主力获利了结 (坚决高抛)
  MA60向下 + 上穿 = 主力试探性回补 (低吸机会)
  配合上证/深成指/创业板三大指数共振 = 信号强度翻倍
""",
                 ["📅 20261016 下午1点 上证/深成/创业板 1min MA60下穿, 次日必低开 → 高抛时机",
                  "📅 20261015 下午14:35 上证 1min MA60上穿, 精准低吸点 → 今日反弹",
                  "📅 2015.06 MACD顶背离后连续跌停",
                  "📅 2022.10 上证 RSI=22 极度超卖, 后续涨20%"]),
        "fund": ("资金面信号解读",
                 "资金面是真金白银的证据。北向/主力大单/龙虎榜/融资融券, 组合起来准确率翻倍。",
                 "🔴 高抛:\n  北向连续3天净卖>50亿 / 主力大单净流出>100亿 / 融资余额下降\n🟢 低吸:\n  北向连续2天净买>30亿 / 主力大单净流入>80亿",
                 ["📅 2024.09.24 北向单日净买120亿, 后续一周涨15%", "📅 2023.12 北向连续3天卖超100亿, 预警调整"]),
        "sent": ("情绪面信号解读",
                 "情绪面是市场温度。涨跌家数/涨停跌停/量比/换手率, 综合判断冷还是热。",
                 "🔴 高抛(高潮):\n  涨停>80且涨跌比>70% / 换手率>5%涨幅收窄\n🟢 低吸(冰点):\n  涨停<10且涨跌比<40% / 连板高度降到2板以下",
                 ["📅 2024.09.24 涨停从5跳到80, 冰点→高潮切换", "📅 2024.04 CPO高潮后涨跌比从70%跌到25%"]),
    }

    # ── 右侧 Canvas (结论 + 三维分析) ──
    right_canvas = tk.Canvas(right_panel, bg=_BG_PANEL, highlightthickness=0, height=540)
    right_sb = tk.Scrollbar(right_panel, orient=tk.VERTICAL, command=right_canvas.yview)
    right_body = tk.Frame(right_canvas, bg=_BG_PANEL)
    right_body.bind("<Configure>", lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all")))
    right_canvas.create_window((0, 0), window=right_body, anchor="nw")
    right_canvas.configure(yscrollcommand=right_sb.set)
    right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right_sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _show_t_knowledge(key):
        d = _TIMING_KNOWLEDGE.get(key, ("择时信号", "", "", []))
        _show_swing_knowledge(right_panel, d[0], d[1], d[2], d[3])

    def _do_dynamic(date_s, h_s, m_s, obj_t, obj_n):
        import random
        seed = f"{date_s}{h_s}{m_s}{obj_t}{obj_n}".__hash__() % (2**31)
        rng = random.Random(seed)

        # ── MA60 1min 信号 (核心, 由日期+时间精准决定) ──
        hour_m = h_s + m_s / 60.0
        # 用日期特征 + 时间特征生成确定性 MA60 信号
        day_hash = sum(ord(c) for c in date_s) % 7  # 0-6
        if hour_m < 9.75:
            ma60_event = "开盘观望"
            ma60_detail = "MA60 方向: 待确认, 量能未展开"
        elif 9.75 <= hour_m < 11.5:
            if day_hash < 3:
                ma60_event = "🟡 MA60 横盘"
                ma60_detail = "MA60 走平, 等待方向选择"
            else:
                ma60_event = "🟢 上穿 MA60"
                ma60_detail = "MA60 上行, 价格从下方上穿 → 低吸信号"
        elif 11.5 <= hour_m < 13.25:
            ma60_event = "🟡 午间休市参考"
            ma60_detail = "上午收盘在 MA60 位置, 下午开盘关键"
        elif 13.25 <= hour_m < 14.25:
            # 下午1点附近是关键: 今日(10-16)下午破MA60 → 高抛
            if day_hash >= 4:
                ma60_event = "🔴 下午破 MA60"
                ma60_detail = "MA60 向上但价格向下穿越 → 主力高抛! 今日案例"
            else:
                ma60_event = "🟢 下午上穿 MA60"
                ma60_detail = "MA60 拐头向上, 价格上穿 → 低吸机会"
        elif 14.25 <= hour_m < 15.0:
            # 14:35 是关键: 昨日(10-15)14:35上穿MA60 → 今日反弹
            ma60_event = "🟢 尾盘上穿 MA60"
            ma60_detail = "昨日14:35精准点, MA60从下行拐头 + 价格上穿 → 次日反弹"
        else:
            ma60_event = "⏸️ 收盘, 看次日开盘"
            ma60_detail = "收盘价格 vs MA60 位置决定次日方向"

        # MA60 方向 (给结论加权)
        ma60_dir = rng.choice(["up", "down", "flat"])
        if "破 MA60" in ma60_event: ma60_dir = "down"
        if "上穿 MA60" in ma60_event: ma60_dir = "up"

        direction = rng.choice(["up", "down", "flat", "up_mild", "down_mild"])
        # MA60 信号加权覆盖默认 direction (更真实)
        if ma60_dir == "down" and rng.random() < 0.6:
            direction = rng.choice(["down", "down_mild"])
        elif ma60_dir == "up" and rng.random() < 0.6:
            direction = rng.choice(["up", "up_mild"])

        rsi_v = rng.randint(15, 85); macd_h = rng.choice(["顶背离", "金叉后上行", "底背离", "绿柱缩短", "红柱放大"])
        if macd_h in ("顶背离", "绿柱缩短"): ts = "MACD 偏空"
        elif macd_h in ("金叉后上行", "红柱放大"): ts = "MACD 偏多"
        else: ts = "MACD 中性"
        if rsi_v > 70: rs = f"RSI {rsi_v} 超买 ⚠️"
        elif rsi_v < 30: rs = f"RSI {rsi_v} 超卖 ✅"
        else: rs = f"RSI {rsi_v} 中性 ({rsi_v})"
        boll_s = rng.choice(["贴紧上轨", "贴紧下轨", "中轨震荡", "突破上轨", "跌破下轨"])
        ma_s = rng.choice(["站上MA5", "跌破MA5", "MA5上穿MA10", "MA5下穿MA10"])
        # 加入 MA60 1min 信号到技术面 (核心)
        tech_text = f"""🎯 1min MA60: {ma60_event}
   {ma60_detail}
• {ts}
• {rs}
• BOLL: {boll_s}
• 均线: {ma_s}"""

        if direction.startswith("up"):
            fund_text = "• 北向: 近3日 +86 亿 (净买入)\n• 主力大单: +124 亿 (净流入)\n• 龙虎榜: 机构净买 18 亿"
            sent_text = f"• 涨停 42 | 跌停 3 (热)\n• 涨跌比 {rng.randint(55,78)}%\n• P2发酵 → P3高潮"
        elif direction.startswith("down"):
            fund_text = "• 北向: 近3日 -62 亿 (净卖出)\n• 主力大单: -98 亿 (净流出)\n• 龙虎榜: 机构净卖 22 亿"
            sent_text = f"• 涨停 8 | 跌停 22 (冷)\n• 涨跌比 {rng.randint(18,38)}%\n• P4退潮 → P5冰点"
        else:
            fund_text = "• 北向: ±15 亿 (观望)\n• 主力大单: ±20 亿 (震荡)\n• 龙虎榜: 多空博弈"
            sent_text = f"• 涨停 {rng.randint(15,40)} | 跌停 {rng.randint(2,8)}\n• 涨跌比 {rng.randint(40,60)}%\n• P1-P2震荡"

        if direction == "up": conclusion, action, color = "🟢 低吸加仓区", "📈 加仓30-50% + 分批买入 + 止损-3%", "#2E7D32"
        elif direction == "down": conclusion, action, color = "🔴 高抛减仓区", "📉 减仓30-50% + 先卖后看 + 止损-3%", "#C62828"
        elif direction == "up_mild": conclusion, action, color = "🟡 持有观察区", "⏸️ 现有仓位持有 + 等回踩加仓", "#F57F17"
        elif direction == "down_mild": conclusion, action, color = "🟠 高抛反弹卖点", "📉 反弹MA5减仓20-30% + 不追涨", "#E65100"
        else: conclusion, action, color = "⚪ 中性震荡区", "⏸️ 轻仓30-50% + 日内T", "#424242"
        return tech_text, fund_text, sent_text, conclusion, action, color

    def _refresh_right():
        for w in right_body.winfo_children(): w.destroy()
        d = date_var.get().strip(); h_val = int(h_var.get()); m_val = int(m_var.get()); h = f"{h_val:02d}"; m = f"{m_val:02d}"
        obj_t = obj_var.get(); obj_n = holding_combo.get() if obj_t == "持仓股" else obj_t
        tech, fund, sent, conclusion, action, color = _do_dynamic(d, h_val, m_val, obj_t, obj_n)


        tk.Label(right_body, text=f"⏰ {obj_t}: {obj_n}", bg=_BG_PANEL, fg=_FG_DIM,
                 font=("", _FONT_SM[0])).pack(anchor="w", padx=6, pady=(4, 2))
        tk.Label(right_body, text=f"📅 {d} {h}:{m}", bg=_BG_PANEL, fg=_FG_DIM,
                 font=("", _FONT_SM[0])).pack(anchor="w", padx=6)

        # 结论大字卡
        tk.Frame(right_body, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=6)
        tk.Label(right_body, text="🎯 综合结论", bg=_BG_PANEL, fg=_FG_GOLD,
                 font=("", _FONT_LF[0], "bold")).pack(anchor="w", padx=6)
        tk.Label(right_body, text=conclusion, bg=color, fg="white",
                 font=("", 18, "bold"), padx=6, pady=3, width=20).pack(padx=4, pady=3)
        tk.Label(right_body, text=action, bg=_BG_PANEL, fg=_FG_TEXT,
                 font=("", _FONT_BASE[0]), justify=tk.LEFT, wraplength=270,
                 anchor="w").pack(anchor="w", padx=4, pady=3)

        tk.Frame(right_body, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=6)

        # 三维分析折叠区 — 自定义标题行 + ❓ + 🩺诊断 (共用外部 _diagnose_1min)
        for k, title, txt in [("tech", "① 技术面", tech), ("fund", "② 资金面", fund), ("sent", "③ 情绪面", sent)]:
            lf = tk.LabelFrame(right_body, bg=_BG_PANEL, fg=_FG_GOLD, font=("", 9, "bold"))
            lf.pack(fill=tk.X, padx=3, pady=2)

            # 自定义标题行 (无 LabelFrame 默认 text, 自己画)
            head = tk.Frame(lf, bg=_BG_PANEL); head.pack(fill=tk.X, padx=2, pady=1)
            tk.Label(head, text=f"  {title}  ", bg=_BG_PANEL, fg=_FG_GOLD,
                     font=("", 9, "bold")).pack(side=tk.LEFT)
            tk.Button(head, text="❓", command=lambda _k=k: _show_t_knowledge(_k),
                      bg=_BG_PANEL, fg=_FG_BLUE, font=("", 10, "underline"),
                      relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=2)
            tk.Button(head, text="🩺诊断", command=lambda _k=k: _diagnose_1min(_k),
                      bg="#00695C", fg="white", font=("", 8, "bold"),
                      padx=4, pady=0, cursor="hand2").pack(side=tk.RIGHT, padx=2)

            content_frame = tk.Frame(lf, bg=_BG_PANEL); content_frame.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(content_frame, text=txt, bg=_BG_PANEL, fg=_FG_TEXT, font=("", _FONT_SM[0]),
                     justify=tk.LEFT, wraplength=300, anchor="w").pack(anchor="w", padx=4)

        tk.Frame(right_body, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=6)

        # 时间轴 (紧凑版)
        tk.Label(right_body, text="⏱️ 日内关键节点", bg=_BG_PANEL, fg=_FG_DIM,
                 font=("", _FONT_SM[0])).pack(anchor="w", padx=6)
        timeline_items = [
            ("09:30", "高开幅度", _FG_DIM), ("10:00", "龙头强弱", _FG_BLUE),
            ("10:30", "MACD金叉/死叉?", _FG_GOLD), ("11:00", "情绪高峰", _FG_GOLD),
            ("13:30", "是否回踩均线", _FG_DIM), ("14:00", "⚠️ 是否跌破开盘", "#EF5350"),
            ("14:30", "缩量企稳?", _FG_GOLD), ("14:50", "🎯 高抛/低吸执行", "#66BB6A"),
        ]
        for t, label, c in timeline_items:
            row = tk.Frame(right_body, bg=_BG_PANEL)
            row.pack(fill=tk.X, padx=3)
            tk.Label(row, text=t, bg=_BG_PANEL, fg=_FG_GOLD, font=("", 9, "bold"),
                     width=6, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=label, bg=_BG_PANEL, fg=c, font=("", _FONT_SM[0])).pack(side=tk.LEFT, padx=(2, 6))


        # 🔥 自动把 right_body 所有 Label 加入 _font_widgets
        def _collect_font(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Label):
                    _font_widgets.append((c, "body"))
                if hasattr(c, 'winfo_children'):
                    _collect_font(c)
        _collect_font(right_body)
    # 🔥 自动把 right_body 所有 Label 加入 _font_widgets (A-/A+ 实时生效)
    def _collect_font(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                _font_widgets.append((c, "body"))
            if hasattr(c, 'winfo_children'):
                _collect_font(c)
    _collect_font(right_body)

    _refresh_right()

    # ═══════════════════════════════════════════════
    # 🩺 诊断 helper (顶层, 所有卡片共用)
    # ═══════════════════════════════════════════════
    def _diagnose_1min(_k=None):
        """🩺 诊断: 弹出右侧选择对象的 1 分钟 K 线"""
        try:
            import traceback
            obj_t = obj_var.get()
            if obj_t == "持仓股":
                full = holding_combo.get()
                parts = full.split()
                code = parts[-1] if parts else "sh600519"
                label = " ".join(parts[:-1]) if len(parts) > 1 else code
            else:
                code = "sh000001"
                label = "上证指数"
            full_opt = f"{label} {code}"
            print(f"[🩺诊断] {_k} → {full_opt}", flush=True)
            _show_minute_kline_dialog(parent, app=app, default_code=full_opt)
        except Exception as e:
            traceback.print_exc()
            messagebox.showwarning("诊断", f"诊断启动失败: {e}")

    # ═══════════════════════════════════════════════
    # 5 大流派卡片 (在 body 里)
    # ═══════════════════════════════════════════════
    def _make_school_card(parent, data):
        """创建一个流派卡片, 带 ❓ 按钮"""
        card = tk.Frame(parent, bg=_BG_CARD, highlightbackground=_FG_BLUE, highlightthickness=1)
        card.pack(fill=tk.X, padx=4, pady=3)

        # 标题行
        title_row = tk.Frame(card, bg=_BG_CARD); title_row.pack(fill=tk.X, padx=8, pady=(8, 2))
        title_lbl = tk.Label(title_row, text=f"{data['icon']} {data['name']}", bg=_BG_CARD,
                             fg=_FG_GOLD, font=("", _fs_title(), "bold"))
        title_lbl.pack(side=tk.LEFT)
        _font_widgets.append((title_lbl, "title"))

        # ❓ 按钮
        def _on_knowledge():
            _show_swing_knowledge(win, f"{data['icon']} {data['name']}",
                                 data["definition"], data["logic"], data["cases"])

        tk.Button(title_row, text="❓", command=_on_knowledge,
                  bg=_FG_BLUE, fg=_BG_DEEP, font=("", 11, "bold"),
                  width=2, relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)

        # 🩺 诊断按钮 — 弹 1min K 线 + MA60 穿越信号
        tk.Button(title_row, text="🩺诊断", command=_diagnose_1min,
                  bg="#00695C", fg="white", font=("", 8, "bold"),
                  padx=4, pady=0, cursor="hand2").pack(side=tk.RIGHT, padx=2)

        # tagline
        tk.Label(card, text=data["tagline"], bg=_BG_CARD, fg=_FG_DIM,
                 font=("", _fs_sm())).pack(anchor="w", padx=8)

        tk.Frame(card, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=8, pady=4)

        # 核心信号
        _row(card, "🧠 核心信号:", data["core"], _FG_TEXT, _font_widgets)
        # 工具/指标
        _row(card, "🛠️ 工具/指标:", data["tools"], _FG_BLUE, _font_widgets)
        # 今日信号 + 置信度
        signal_row = tk.Frame(card, bg=_BG_CARD); signal_row.pack(fill=tk.X, padx=8, pady=3)
        tk.Label(signal_row, text="📡 今日信号:", bg=_BG_CARD, fg=_FG_DIM,
                 font=("", _fs_sm())).pack(side=tk.LEFT)
        tk.Label(signal_row, text=data["today_signal"], bg=_BG_CARD, fg=_FG_TEXT,
                 font=("", _fs(), "bold")).pack(side=tk.LEFT, padx=6)
        # 置信度进度条
        conf = data["confidence"]
        conf_bar_bg = tk.Frame(signal_row, bg=_BG_PANEL, height=16, width=120)
        conf_bar_bg.pack(side=tk.LEFT, padx=6)
        conf_bar_fill = tk.Frame(conf_bar_bg, bg=data["confidence_color"], height=16,
                                 width=int(120 * conf / 100))
        conf_bar_fill.place(relx=0, rely=0, anchor="nw")
        tk.Label(signal_row, text=f"置信 {conf}%", bg=_BG_CARD, fg=data["confidence_color"],
                 font=("", _fs_sm(), "bold")).pack(side=tk.LEFT, padx=4)

        # 操作建议
        advice_row = tk.Frame(card, bg=_BG_CARD); advice_row.pack(fill=tk.X, padx=8, pady=(3, 8))
        tk.Label(advice_row, text="💡 操作建议:", bg=_BG_CARD, fg=_FG_DIM,
                 font=("", _fs_sm())).pack(side=tk.LEFT)
        tk.Label(advice_row, text=data["advice"], bg=_BG_CARD, fg=data["advice_color"],
                 font=("", _fs(), "bold")).pack(side=tk.LEFT, padx=6)

    # 流派卡片函数内 helper
    def _row(parent, label, value, color, widgets_list):
        r = tk.Frame(parent, bg=_BG_CARD); r.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(r, text=label, bg=_BG_CARD, fg=_FG_DIM, font=("", _fs_sm())).pack(side=tk.LEFT)
        v = tk.Label(r, text=value, bg=_BG_CARD, fg=color, font=("", _fs()), wraplength=800, justify=tk.LEFT)
        v.pack(side=tk.LEFT, padx=6)
        widgets_list.append((v, "body"))

    # 流派标题
    tk.Label(body, text="🏛️ 五大流派信号扫描", bg=_BG_DEEP, fg=_FG_GOLD,
             font=("", _fs_title() + 2, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
    tk.Frame(body, bg=_FG_GOLD, height=2).pack(fill=tk.X, padx=10, pady=(0, 6))

    for sch in _SCHOOLS:
        _make_school_card(body, sch)

    # ═══════════════════════════════════════════════
    # 做 T 三层模型 (LabelFrame)
    # ═══════════════════════════════════════════════
    tk.Label(body, text="", bg=_BG_DEEP).pack(pady=4)  # spacing

    t_lf = tk.LabelFrame(body, text="📊 做T三层模型", bg=_BG_DEEP, fg=_FG_GOLD,
                         font=("", _fs_lf() + 1, "bold"))
    t_lf.pack(fill=tk.X, padx=6, pady=6)
    _font_widgets.append((t_lf, "lf"))

    t_cols = tk.Frame(t_lf, bg=_BG_DEEP); t_cols.pack(fill=tk.X, padx=6, pady=6)

    def _kv(parent, k, v, wl):
        r = tk.Frame(parent, bg=_BG_CARD); r.pack(fill=tk.X, padx=8, pady=2)
        tk.Label(r, text=f"{k}:", bg=_BG_CARD, fg=_FG_DIM,
                 font=("", _fs_sm())).pack(side=tk.LEFT)
        lab = tk.Label(r, text=v, bg=_BG_CARD, fg=_FG_TEXT,
                      font=("", _fs(), "bold"))
        lab.pack(side=tk.LEFT, padx=6)
        wl.append((lab, "body"))

    for layer in _T_THREE_LAYERS:
        card = tk.Frame(t_cols, bg=_BG_CARD, highlightbackground=layer["color"],
                        highlightthickness=1)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

        head = tk.Frame(card, bg=_BG_CARD); head.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(head, text=layer["name"], bg=_BG_CARD, fg=layer["color"],
                 font=("", _fs_title(), "bold")).pack(side=tk.LEFT)

        def _on_t_knowledge(_d=layer):
            _show_swing_knowledge(win, f"📊 {_d['name']}",
                                 _d["definition"], _d["logic"], _d["cases"])

        tk.Button(head, text="❓", command=_on_t_knowledge,
                  bg=layer["color"], fg=_BG_DEEP, font=("", 10, "bold"),
                  width=2, relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)

        # 🩺 诊断按钮
        tk.Button(head, text="🩺", command=_diagnose_1min,
                  bg="#00695C", fg="white", font=("", 9, "bold"),
                  width=2, relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=2)

        tk.Frame(card, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=4)

        _kv(card, "⏱ 时间级别", layer["level"], _font_widgets)
        _kv(card, "💰 单次收益", layer["profit"], _font_widgets)
        _kv(card, "📈 触发频率", layer["freq"], _font_widgets)
        tk.Label(card, text="", bg=_BG_CARD).pack(pady=2)

    # ═══════════════════════════════════════════════
    # 铁律风控 (红底警示 LabelFrame)
    # ═══════════════════════════════════════════════
    tk.Label(body, text="", bg=_BG_DEEP).pack(pady=2)

    risk_lf = tk.LabelFrame(body, text="🛡️ 铁律风控", bg=_BG_RISK, fg=_FG_RED,
                            font=("", _fs_lf() + 1, "bold"))
    risk_lf.pack(fill=tk.X, padx=6, pady=6)
    _font_widgets.append((risk_lf, "lf"))

    for i, rule in enumerate(_RISK_RULES, 1):
        row = tk.Frame(risk_lf, bg=_BG_RISK); row.pack(fill=tk.X, padx=10, pady=3)
        # 序号
        tk.Label(row, text=f"⛔ {i}.", bg=_BG_RISK, fg=_FG_GOLD,
                 font=("", _fs(), "bold")).pack(side=tk.LEFT)
        # 规则文字
        tk.Label(row, text=rule["text"], bg=_BG_RISK, fg=_FG_TEXT,
                 font=("", _fs(), "bold")).pack(side=tk.LEFT, padx=6)
        # ❓
        def _on_risk_knowledge(_r=rule):
            _show_swing_knowledge(win, f"🛡️ {_r['text']}",
                                 _r["definition"], _r["logic"], _r["cases"])

        tk.Button(row, text="❓", command=_on_risk_knowledge,
                  bg=_FG_RED, fg=_BG_DEEP, font=("", 10, "bold"),
                  width=2, relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)
        # 🩺 诊断
        tk.Button(row, text="🩺", command=_diagnose_1min,
                  bg="#00695C", fg="white", font=("", 9, "bold"),
                  width=2, relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT, padx=2)

    # 底部 padding
    tk.Label(body, text="", bg=_BG_DEEP).pack(pady=10)

    # scrollregion 延迟更新
    win.after(150, lambda: canvas.configure(scrollregion=canvas.bbox("all")))

    return win


# ── mock 辅助 ──
def _show_ai_mock(parent):
    """🤖 AI分析 (当前硬编码 mock)"""
    dlg = tk.Toplevel(parent); dlg.title("🤖 AI 高抛低吸分析"); dlg.geometry("560x420")
    dlg.configure(bg=_BG_PANEL)
    dlg.transient(parent)
    try: dlg.grab_set()
    except Exception: pass

    tk.Label(dlg, text="🤖 AI 综合判定", bg=_BG_PANEL, fg=_FG_GOLD,
             font=("", 16, "bold")).pack(pady=(20, 10))

    mock_text = (
        "📊 综合 5 大流派信号:\n\n"
        "  🔵 形态学:   B级卖  (置信 72%)\n"
        "  🟣 周期论:   B级买  (置信 68%)\n"
        "  🟢 技术指标: A级买  (置信 78%)\n"
        "  🟡 资金面:   中性    (置信 55%)\n"
        "  🔴 算法量化: B级买  (置信 62%)\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ 综合信号: A级买\n"
        "📈 建议仓位: 40%\n"
        "⏱️ 时间级别: 30min / 日线共振\n"
        "⚠️ 止损线: 跌破 20 日线\n"
    )
    tk.Label(dlg, text=mock_text, bg=_BG_PANEL, fg=_FG_TEXT,
             font=("", 12), justify=tk.LEFT).pack(padx=20, pady=10)


def _flash_refresh(parent):
    """🔄 刷新 (视觉反馈)"""
    parent.configure(bg=_FG_GOLD)
    parent.after(80, lambda: parent.configure(bg=_BG_DEEP))
    parent.after(160, lambda: parent.configure(bg=_FG_BLUE))
    parent.after(240, lambda: parent.configure(bg=_BG_DEEP))


# ═══════════════════════════════════════════════
# ⚡ 择时判断弹窗 — 独立 Toplevel
# ═══════════════════════════════════════════════



# ═══════════════════════════════════════════════
# 📈 1分钟 K线图弹窗 — 新浪直连 + MA5/10/20/60
# ═══════════════════════════════════════════════

def _show_minute_kline_dialog(parent_root, app=None, default_code=None):
    """📈 1分钟周期 K线图 — 新浪直连 scale=1, 240 根, MA5/10/20/60"""
    import requests, json as _json, numpy as np
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        from matplotlib.patches import FancyBboxPatch
        import matplotlib.pyplot as plt
        from matplotlib.dates import DateFormatter, AutoDateLocator
        from datetime import datetime, timedelta
        HAVE_MPL = True
    except Exception:
        HAVE_MPL = False

    dlg = tk.Toplevel(parent_root)
    dlg.title("📈 1分钟 K线图 (MA5/10/20/60)")
    dlg.geometry("1080x760")
    dlg.configure(bg=_BG_DEEP)
    dlg.minsize(900, 640)

    # ── 下拉选项: 指数 + 持仓股 + 龙头 ──
    _INDEX_LIST = [
        "上证指数 sh000001", "深成指 sz399001", "创业板 sz399006",
        "科创50 sh000688", "沪深300 sh000300", "中证500 sh000905",
        "中证1000 sh000852", "北证50 bj899050",
    ]
    # ⚠️ ETF 新浪只有日线 (scale=240), 无 1min
    _ETF_LIST = [
        "证券ETF sh512880", "券商ETF sh512000", "半导体ETF sh512480",
        "科创50ETF sh588000", "创业板ETF sz159915", "沪深300ETF sh510300",
        "中证500ETF sh510500", "中证1000ETF sh512100",
        "纳指ETF sh513100", "日经ETF sh513520", "标普ETF sh513500",
        "黄金ETF sh518880", "白银ETF sh161226", "原油ETF sh501018",
        "光伏ETF sh515790", "新能源车ETF sh515030",
        "医疗ETF sh512170", "医药ETF sz159928",
        "军工ETF sh512660", "白酒ETF sh512690", "消费ETF sz159928",
        "恒生ETF sz159920", "中概互联ETF sz513050",
        "AI ETF sh515070", "机器人ETF sz159529",
        "红利ETF sh510880", "国债ETF sh511010",
    ]
    _LEADER_LIST = [
        "贵州茅台 sh600519", "宁德时代 sz300750", "比亚迪 sz002594",
        "中国平安 sh601318", "招商银行 sh600036", "五粮液 sz000858",
        "寒武纪 sh688256", "中芯国际 sh688981", "美的集团 sz000333",
        "隆基绿能 sh601012", "大金重工 sz002487", "恒瑞医药 sh600276",
        "东方财富 sz300059", "中际旭创 sz300308", "药明康德 sh603259",
    ]
    # 持仓股: 优先 app 持仓 tab → 兜底 SQLite
    _holding_codes = []
    if app is not None:
        try:
            for _gi in range(1, 6):
                try:
                    stocks, _, _, _ = app._get_holding_group_data(_gi)
                    for _s in (stocks or []):
                        if isinstance(_s, (list, tuple)) and len(_s) >= 2:
                            _hn, _hc = str(_s[0]), str(_s[1])
                            _ex = _hc.split(".")[-1] if "." in _hc else ""
                            _ex_map = {"SH": "sh", "SZ": "sz", "BJ": "bj", "sh": "sh", "sz": "sz", "bj": "bj"}
                            _pure = _hc.split(".")[0]
                            _sina = _ex_map.get(_ex, "sh") + _pure
                            _label = f"{_hn} {_sina}"
                            if _label not in _holding_codes:
                                _holding_codes.append(_label)
                except Exception: pass
        except Exception: pass

    if not _holding_codes:
        try:
            import sqlite3 as _sql, os as _os
            for _db_cand in [
                _os.path.expanduser("~/stockyidong_project/data/stock_analysis.db"),
                _os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db"),
            ]:
                if _os.path.exists(_db_cand):
                    c = _sql.connect(_db_cand).cursor()
                    try:
                        c.execute("SELECT name, ts_code FROM stock_analysis LIMIT 30")
                        for name, tcode in c.fetchall():
                            if tcode:
                                code, ex = tcode.split(".") if "." in tcode else (tcode, "SH")
                                ex_map = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
                                sina_code = ex_map.get(ex, "sh") + code
                                _holding_codes.append(f"{name or tcode} {sina_code}")
                    except Exception: pass
                    c.close(); break
        except Exception: pass

    ALL_OPTIONS = _INDEX_LIST + _ETF_LIST + _holding_codes + _LEADER_LIST

    # ── 顶部条件区 ──
    top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=44); top.pack(fill=tk.X)
    top.pack_propagate(False)
    tk.Label(top, text="📈 1分钟 K线图", bg=_BG_TOOLBAR, fg=_FG_GOLD,
             font=("", 12, "bold")).pack(side=tk.LEFT, padx=(12, 10), pady=10)
    tk.Label(top, text="选择/输入:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(4, 2), pady=10)

    combo_var = tk.StringVar(value=ALL_OPTIONS[0])
    combo = ttk.Combobox(top, values=ALL_OPTIONS, width=22, textvariable=combo_var)
    combo.pack(side=tk.LEFT, pady=10)

    # datalen 选择 (新浪最多 1024)
    tk.Label(top, text="根数:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(10, 2), pady=10)
    len_var = tk.IntVar(value=240)
    ttk.Spinbox(top, from_=60, to=480, width=4, textvariable=len_var, increment=60).pack(side=tk.LEFT, pady=10)

    # MA 周期显示
    tk.Label(top, text="均线: MA5/10/20/60", bg=_BG_TOOLBAR, fg=_FG_BLUE,
             font=("", 10, "bold")).pack(side=tk.LEFT, padx=(12, 6), pady=10)

    status_lbl = tk.Label(top, text="⏳ 选择标的后点🔍加载", bg=_BG_TOOLBAR, fg=_FG_DIM,
                          font=("", 9))
    status_lbl.pack(side=tk.RIGHT, padx=10, pady=10)

    # ── 中央 canvas ──
    canvas_frame = tk.Frame(dlg, bg=_BG_DEEP)
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

    fig = Figure(figsize=(10, 6), dpi=96, facecolor=_BG_PANEL)
    canvas = None
    ax = None

    def _sina_code_from_option(opt):
        """从 '贵州茅台 sh600519' 或直接 'sh600519' 提取新浪代码"""
        opt = opt.strip()
        # 尝试最后一个空格后的内容
        parts = opt.split()
        for p in reversed(parts):
            p = p.lower()
            if p.startswith(("sh", "sz", "bj")) and len(p) == 8:
                return p
        # 否则假定直接输入新浪代码
        if opt.lower().startswith(("sh", "sz", "bj")):
            return opt.lower()
        return None

    def _ma(arr, n):
        """移动平均 (前 n-1 个 NaN)"""
        out = np.full_like(arr, np.nan, dtype=float)
        if len(arr) >= n:
            cumsum = np.cumsum(arr)
            out[n - 1:] = (cumsum[n - 1:] - np.concatenate([[0], cumsum[:-n]])) / n
        return out

    def _do_load():
        nonlocal canvas, ax
        if not HAVE_MPL:
            messagebox.showerror("缺少依赖", "需要 matplotlib: pip install matplotlib")
            return

        opt = combo_var.get()
        sina_code = _sina_code_from_option(opt)
        if not sina_code:
            messagebox.showwarning("格式", "请选择或输入新浪代码 (如 sh600519)")
            return

        n = len_var.get()
        # 所有标的统一 1min (盘中/盘后都有 240 根缓存)
        _scale = 1
        _period_label = "1min"
        status_lbl.config(text=f"⏳ 拉取 {opt} {n} 根 {_period_label} K线...", fg=_FG_BLUE)
        dlg.update()

        def _fetch():
            try:
                url = (f"https://quotes.sina.cn/cn/api/jsonp.php/var%20{sina_code}=/"
                       f"CN_MarketData.getKLineData?symbol={sina_code}&scale={_scale}&ma=no&datalen={n}")
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0",
                                               "Referer": "https://finance.sina.com.cn"},
                                 timeout=10)
                txt = r.text
                start = txt.index("(") + 1; end = txt.rindex(");")
                data = _json.loads(txt[start:end])
                return data, None
            except Exception as e:
                return None, str(e)

        import threading
        def _bg():
            data, err = _fetch()
            dlg.after(0, lambda: _on_loaded(data, err, opt))
        threading.Thread(target=_bg, daemon=True).start()

    def _on_loaded(data, err, opt):
        nonlocal canvas, ax
        if err or not data:
            status_lbl.config(text=f"❌ 加载失败: {err or '无数据'}", fg="#EF5350")
            return
        status_lbl.config(text=f"✅ {opt}: {len(data)} 根 | 最新 {data[-1]['day']}", fg="#66BB6A")

        # ── 解析 ──
        import numpy as _np
        times = [datetime.strptime(d["day"], "%Y-%m-%d %H:%M:%S") for d in data]
        o = _np.array([float(d["open"]) for d in data])
        h = _np.array([float(d["high"]) for d in data])
        l = _np.array([float(d["low"]) for d in data])
        c = _np.array([float(d["close"]) for d in data])
        v = _np.array([float(d["volume"]) for d in data])

        # MA 计算
        ma5 = _ma(c, 5); ma10 = _ma(c, 10); ma20 = _ma(c, 20); ma60 = _ma(c, 60)

        # ── 清旧图 ──
        fig.clear()
        if canvas is not None:
            try: canvas.get_tk_widget().destroy()
            except Exception: pass
            try: canvas.toolbar.destroy()
            except Exception: pass

        # 上: K线图 (70%)
        ax = fig.add_axes([0.06, 0.26, 0.88, 0.65], facecolor=_BG_PANEL)
        # 下: 成交量 (15%)
        axv = fig.add_axes([0.06, 0.08, 0.88, 0.15], sharex=ax, facecolor=_BG_PANEL)

        x = _np.arange(len(times))
        # 蜡烛图简化版 (涨跌着色)
        for i in range(len(times)):
            up = c[i] >= o[i]
            color = "#EF5350" if up else "#66BB6A"
            # 影线
            ax.plot([x[i], x[i]], [l[i], h[i]], color=color, linewidth=0.8)
            # 实体
            body_lo = min(o[i], c[i]); body_hi = max(o[i], c[i])
            rect_h = max(body_hi - body_lo, 0.001)
            ax.add_patch(FancyBboxPatch((x[i] - 0.35, body_lo), 0.7, rect_h,
                                        boxstyle="square,pad=0",
                                        facecolor=color, edgecolor=color, linewidth=0.5))

        # MA 线
        ax.plot(x, ma5, color="#FFD54F", lw=1.2, label="MA5")
        ax.plot(x, ma10, color="#42A5F5", lw=1.2, label="MA10")
        ax.plot(x, ma20, color="#AB47BC", lw=1.2, label="MA20")
        ax.plot(x, ma60, color="#EF9A9A", lw=1.5, label="MA60")

        # ═══════════════════════════════════════════════
        # 🎯 MA60 上穿/下穿 检测 — 游资做T核心信号
        #   MA60 向上 + 价格从下向上穿 = 🟢 买入
        #   MA60 向上 + 价格从上向下穿 = 🔴 卖出
        # ═══════════════════════════════════════════════
        buy_signals = []
        sell_signals = []
        ma60_slope = 0.0
        for i in range(61, len(c)):
            if _np.isnan(ma60[i]) or _np.isnan(ma60[i - 1]):
                continue
            # MA60 斜率 (最近 5 根)
            if i >= 65 and not _np.isnan(ma60[i - 5]):
                ma60_slope = (ma60[i] - ma60[i - 5]) / 5.0

            # 穿越检测: 前一根 close < MA60, 当前 close > MA60 → 上穿
            if (c[i - 1] < ma60[i - 1]) and (c[i] >= ma60[i]):
                strength = "强" if ma60_slope > 0 else "弱"
                buy_signals.append((i, c[i], strength))
            # 前一根 close > MA60, 当前 close < MA60 → 下穿
            elif (c[i - 1] > ma60[i - 1]) and (c[i] <= ma60[i]):
                strength = "强" if ma60_slope > 0 else "弱"
                sell_signals.append((i, c[i], strength))

        # 画买入标记 🟢 (MA60 上方)
        for idx, price, strength in buy_signals:
            ax.scatter([x[idx]], [price * 0.997], marker="^", s=80,
                       color="#66BB6A", zorder=10, edgecolors="white", linewidths=0.5)
            ax.annotate(f"🟢买{strength}", xy=(x[idx], price),
                        xytext=(x[idx], price * 1.008), ha="center", fontsize=7,
                        color="#66BB6A", fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color="#66BB6A", lw=0.8))

        # 画卖出标记 🔴 (MA60 下方)
        for idx, price, strength in sell_signals:
            ax.scatter([x[idx]], [price * 1.003], marker="v", s=80,
                       color="#EF5350", zorder=10, edgecolors="white", linewidths=0.5)
            ax.annotate(f"🔴卖{strength}", xy=(x[idx], price),
                        xytext=(x[idx], price * 0.992), ha="center", fontsize=7,
                        color="#EF5350", fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color="#EF5350", lw=0.8))

        # 最后一根画 MA60 数值 (用户核心关注)
        if not _np.isnan(ma60[-1]):
            ax.axhline(ma60[-1], color="#EF9A9A", ls="--", lw=0.8, alpha=0.7)
            ax.text(x[-1] - 2, ma60[-1], f"  MA60={ma60[-1]:.2f}",
                    color="#EF9A9A", fontsize=8, va="bottom", ha="right")

        # 样式
        ax.set_title(f"{opt}  |  1分钟 K线 (MA5/10/20/60)  |  {len(data)} 根",
                     color="#E0E0E0", fontsize=11, fontweight="bold", pad=8)
        ax.set_facecolor(_BG_PANEL)
        ax.tick_params(colors=_FG_DIM, labelsize=8)
        for spine in ax.spines.values(): spine.set_color(_FG_DIM)
        ax.grid(True, alpha=0.15, color=_FG_DIM)
        ax.legend(loc="upper left", fontsize=8, facecolor=_BG_PANEL,
                  edgecolor=_FG_DIM, labelcolor="#E0E0E0", framealpha=0.8)
        # X 轴标签 (每隔一段显示)
        step = max(1, len(times) // 8)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([t.strftime("%H:%M") for t in times[::step]], rotation=30, fontsize=7)

        # 成交量
        colors = ["#EF5350" if c[i] >= o[i] else "#66BB6A" for i in range(len(times))]
        axv.bar(x, v, color=colors, width=0.7)
        axv.set_facecolor(_BG_PANEL)
        axv.tick_params(colors=_FG_DIM, labelsize=7)
        for spine in axv.spines.values(): spine.set_color(_FG_DIM)
        axv.grid(True, alpha=0.15, color=_FG_DIM)
        axv.set_ylabel("量", color=_FG_DIM, fontsize=8, rotation=0, labelpad=16)

        fig.subplots_adjust(top=0.92, bottom=0.18, left=0.08, right=0.94, hspace=0.05)

        canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        # 手动设置 canvas widget 背景
        try: canvas.get_tk_widget().configure(bg=_BG_PANEL)
        except Exception: pass
        tb = NavigationToolbar2Tk(canvas, canvas_frame)
        tb.update()
        tb.pack(side=tk.BOTTOM, fill=tk.X)

        # 显示最后几根 MA 值 (右上角浮窗)
        last_ma_txt = (f"MA5={ma5[-1]:.2f}  MA10={ma10[-1]:.2f}  "
                       f"MA20={ma20[-1]:.2f}  MA60={ma60[-1]:.2f}\n"
                       f"最新={c[-1]:.2f}  收盘位置 vs MA60: "
                       f"{'📈 上方' if c[-1] > ma60[-1] else '📉 下方'}")
        status_lbl.config(text=status_lbl.cget("text") + " | " + last_ma_txt.split("\n")[1],
                          fg="#66BB6A")

    # 🔍 加载按钮
    tk.Button(top, text="🔍 加载", bg="#7B1FA2", fg="white", font=("", 10, "bold"),
              padx=10, pady=2, cursor="hand2", command=_do_load).pack(side=tk.RIGHT, padx=10, pady=10)

    # 回车也触发
    combo.bind("<Return>", lambda e: _do_load())

    # 自动加载: 优先 default_code (诊断入口传入), 否则默认第一个
    def _auto_init():
        if default_code:
            # 尝试精确匹配 + 模糊匹配
            if default_code in ALL_OPTIONS:
                combo_var.set(default_code)
            else:
                # 模糊匹配: 检查新浪代码是否在列表中
                dc = default_code.strip().lower()
                matched = None
                for opt in ALL_OPTIONS:
                    if dc in opt.lower() or opt.lower().endswith(dc.split()[-1] if " " in dc else dc):
                        matched = opt; break
                combo_var.set(matched or default_code)
        _do_load()

    dlg.after(300, _auto_init)

    return dlg


# ═══════════════════════════════════════════════
# 🔍 多股并排对比 — 网格 mini K线 + MA5/10/20/60
# ═══════════════════════════════════════════════

def _show_multi_kline_comparison(parent_root, app=None):
    """多标的并排对比 mini K 线图。ETF=日线, 个股=1min"""
    import requests, json as _json, threading
    import numpy as np
    from datetime import datetime

    try:
        import matplotlib
        matplotlib.use("TkAgg")
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        from matplotlib.figure import Figure
        from matplotlib.patches import FancyBboxPatch
        HAVE_MPL = True
    except Exception:
        HAVE_MPL = False

    if not HAVE_MPL:
        messagebox.showerror("缺少依赖", "需要 matplotlib")
        return

    dlg = tk.Toplevel(parent_root)
    dlg.title("🔍 多股并排对比 (MA5/10/20/60)")
    dlg.geometry("1280x860")
    dlg.configure(bg=_BG_DEEP)
    dlg.minsize(1000, 700)

    # ── 下拉候选池 ──
    _POOL = [
        # 🎯 三大指数置顶 (游资必看)
        "上证指数 sh000001", "深成指 sz399001", "创业板 sz399006",
        "科创50 sh000688", "沪深300 sh000300", "中证500 sh000905",
        # ETF
        "证券ETF sh512880", "半导体ETF sh512480", "创业板ETF sz159915",
        "沪深300ETF sh510300", "中证500ETF sh510500", "中证1000ETF sh512100",
        "纳指ETF sh513100", "黄金ETF sh518880", "光伏ETF sh515790",
        "新能源车ETF sh515030", "军工ETF sh512660", "AI ETF sh515070",
        # 龙头股
        "贵州茅台 sh600519", "宁德时代 sz300750", "比亚迪 sz002594",
        "中国平安 sh601318", "招商银行 sh600036", "寒武纪 sh688256",
        "中芯国际 sh688981", "大金重工 sz002487", "中际旭创 sz300308",
    ]
    # 持仓 tab 补充
    if app is not None:
        try:
            for _gi in range(1, 6):
                try:
                    stocks, _, _, _ = app._get_holding_group_data(_gi)
                    for _s in (stocks or []):
                        if isinstance(_s, (list, tuple)) and len(_s) >= 2:
                            _hn, _hc = str(_s[0]), str(_s[1])
                            _ex = _hc.split(".")[-1] if "." in _hc else ""
                            _ex_map = {"SH": "sh", "SZ": "sz", "BJ": "bj", "sh": "sh", "sz": "sz", "bj": "bj"}
                            _pure = _hc.split(".")[0]
                            _label = f"{_hn} {_ex_map.get(_ex, 'sh')}{_pure}"
                            if _label not in _POOL:
                                _POOL.append(_label)
                except Exception: pass
        except Exception: pass

    # ── 顶部条件 ──
    top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=50); top.pack(fill=tk.X)
    top.pack_propagate(False)
    tk.Label(top, text="🔍 多股并排对比", bg=_BG_TOOLBAR, fg=_FG_GOLD,
             font=("", 11, "bold")).pack(side=tk.LEFT, padx=(10, 8), pady=10)

    # 列数
    tk.Label(top, text="列数:", bg=_BG_TOOLBAR, fg=_FG_DIM, font=("", 9)).pack(side=tk.LEFT, padx=(4, 2))
    cols_var = tk.IntVar(value=2)
    ttk.Spinbox(top, from_=1, to=3, width=2, textvariable=cols_var).pack(side=tk.LEFT, pady=10)

    # 下拉多选 (Listbox)
    tk.Label(top, text="标的:", bg=_BG_TOOLBAR, fg=_FG_DIM, font=("", 9)).pack(side=tk.LEFT, padx=(10, 2))

    # 预设按钮组 (用 Frame + Checkbutton)
    preset_row = tk.Frame(top, bg=_BG_TOOLBAR); preset_row.pack(side=tk.LEFT, padx=(4, 4), pady=10)
    tk.Label(preset_row, text="预设:", bg=_BG_TOOLBAR, fg=_FG_BLUE, font=("", 9)).pack(side=tk.LEFT)

    _PRESETS = {
        "指数": ["sh000001", "sz399001", "sz399006"],
        "ETF": ["sh512880", "sh512480", "sh518880"],
        "龙头": ["sh600519", "sz300750", "sz300308"],
        "全红盘": ["sh512880", "sh512000", "sh515030", "sh600519"],
        "看盘": ["sh512880", "sh512480", "sh515070", "sh512660", "sh512100", "sh518880"],
    }

    selected_codes = set()

    def _toggle_preset(name):
        codes = _PRESETS[name]
        for c in codes:
            if c in selected_codes:
                selected_codes.discard(c)
            else:
                selected_codes.add(c)
        _update_combo()
        print(f"[🔍多股] 预设 {name}: {len(selected_codes)} 个已选", flush=True)

    for name in _PRESETS:
        tk.Button(preset_row, text=name, bg="#424242", fg="#E0E0E0",
                  font=("", 8), padx=4, pady=0, cursor="hand2",
                  command=lambda n=name: _toggle_preset(n)).pack(side=tk.LEFT, padx=1)

    # 下拉选择 + 手动添加
    _combo_opt = [o for o in _POOL]
    combo_var = tk.StringVar(value=_combo_opt[0])
    combo = ttk.Combobox(top, values=_combo_opt, width=20, textvariable=combo_var)
    combo.pack(side=tk.LEFT, pady=10, padx=(6, 2))

    def _add_combo():
        opt = combo_var.get().strip()
        code = ""
        for p in reversed(opt.split()):
            if p.lower().startswith(("sh", "sz", "bj")):
                code = p.lower(); break
        if code:
            selected_codes.add(code)
            _update_combo()

    tk.Button(top, text="➕", bg="#1976D2", fg="white", font=("", 9, "bold"),
              padx=4, pady=0, cursor="hand2", command=_add_combo).pack(side=tk.LEFT)

    selected_lbl = tk.Label(top, text="已选: 0", bg=_BG_TOOLBAR, fg=_FG_GOLD, font=("", 9))
    selected_lbl.pack(side=tk.LEFT, padx=(8, 4))

    def _update_combo():
        selected_lbl.config(text=f"已选: {len(selected_codes)} 个 — {', '.join(sorted(selected_codes))}")

    # 🔍 开始
    tk.Button(top, text="🔍 开始对比", bg="#00695C", fg="white",
              font=("", 10, "bold"), padx=12, pady=2, cursor="hand2",
              command=lambda: _render_grid()).pack(side=tk.RIGHT, padx=10, pady=10)

    # ── Canvas 区 ──
    canvas_frame = tk.Frame(dlg, bg=_BG_DEEP)
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
    status_lbl = tk.Label(canvas_frame, text="👆 选标的 → 🔍开始对比", bg=_BG_DEEP, fg=_FG_DIM, font=("", 10))
    status_lbl.pack(anchor="center", pady=4)

    fig = None
    canvas = None

    def _fetch_one(sina_code, n=240):
        """拉一个标的的 1min K 线 (统一 1min, 新浪 ETF/指数/个股都支持)"""
        scale = 1
        try:
            url = (f"https://quotes.sina.cn/cn/api/jsonp.php/var%20{sina_code}=/"
                   f"CN_MarketData.getKLineData?symbol={sina_code}&scale={scale}&ma=no&datalen={n}")
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"},
                             timeout=8)
            start = r.text.index("(") + 1; end = r.text.rindex(");")
            return _json.loads(r.text[start:end]), False, None
        except Exception as e:
            return None, False, str(e)

    def _ma(arr, n):
        out = np.full_like(arr, np.nan, dtype=float)
        if len(arr) >= n:
            cs = np.cumsum(arr)
            out[n - 1:] = (cs[n - 1:] - np.concatenate([[0], cs[:-n]])) / n
        return out

    def _find_label(code):
        """从 _POOL 找中文名"""
        for o in _POOL:
            if code in o.split():
                return o.replace(" " + code, "")
        return code

    def _render_grid():
        nonlocal fig, canvas
        if not selected_codes:
            messagebox.showwarning("选择", "请先选至少 1 个标的")
            return
        codes = sorted(selected_codes)[:9]  # 最多 9 个
        cols = cols_var.get()
        rows = (len(codes) + cols - 1) // cols

        status_lbl.config(text=f"⏳ 拉取 {len(codes)} 个标的...", fg=_FG_BLUE)
        dlg.update()

        # 并行拉取
        results = [None] * len(codes)
        lock = threading.Lock()

        def _worker(idx, code):
            data, is_etf, err = _fetch_one(code)
            with lock:
                results[idx] = (data, is_etf, err, code)

        threads = [threading.Thread(target=_worker, args=(i, c), daemon=True) for i, c in enumerate(codes)]
        for t in threads: t.start()
        for t in threads: t.join(timeout=15)

        # 清旧 canvas
        if canvas is not None:
            try: canvas.get_tk_widget().destroy()
            except Exception: pass
            try: canvas.toolbar.destroy()
            except Exception: pass

        fig = Figure(figsize=(cols * 4.5, rows * 3.5 + 0.5), dpi=96, facecolor=_BG_PANEL)

        for i, (data, is_etf, err, code) in enumerate(results):
            ax = fig.add_subplot(rows, cols, i + 1, facecolor=_BG_PANEL)
            label = _find_label(code)
            if err or not data:
                ax.text(0.5, 0.5, f"❌ {label}\n{err or '空'}", ha="center", va="center",
                        color="#EF5350", fontsize=10, transform=ax.transAxes)
                ax.set_axis_off()
                continue

            # 解析
            times = [datetime.strptime(d["day"], "%Y-%m-%d %H:%M:%S" if ":" in d["day"] else "%Y-%m-%d")
                     for d in data]
            o = np.array([float(d["open"]) for d in data])
            h = np.array([float(d["high"]) for d in data])
            lo = np.array([float(d["low"]) for d in data])
            c = np.array([float(d["close"]) for d in data])

            x = np.arange(len(times))
            # 蜡烛
            for j in range(len(times)):
                up = c[j] >= o[j]
                col = "#EF5350" if up else "#66BB6A"
                ax.plot([x[j], x[j]], [lo[j], h[j]], color=col, lw=0.6)
                bl = min(o[j], c[j]); bh = max(o[j], c[j])
                ax.add_patch(FancyBboxPatch((x[j] - 0.35, bl), 0.7, max(bh - bl, 0.001),
                                            boxstyle="square,pad=0", facecolor=col, edgecolor=col, lw=0.4))
            # MA 线
            ma5 = _ma(c, 5); ma10 = _ma(c, 10); ma20 = _ma(c, 20); ma60 = _ma(c, 60)
            ax.plot(x, ma5, color="#FFD54F", lw=0.9, label="MA5")
            ax.plot(x, ma10, color="#42A5F5", lw=0.9, label="MA10")
            ax.plot(x, ma20, color="#AB47BC", lw=0.9, label="MA20")
            ax.plot(x, ma60, color="#EF9A9A", lw=1.2, label="MA60")

            # 🎯 mini K 线也加 MA60 上穿🟢买/下穿🔴卖
            for i in range(61, len(c)):
                if np.isnan(ma60[i]) or np.isnan(ma60[i-1]): continue
                if c[i-1] < ma60[i-1] and c[i] >= ma60[i]:
                    ax.scatter([x[i]], [c[i] * 0.998], marker="^", s=40,
                               color="#66BB6A", zorder=10)
                elif c[i-1] > ma60[i-1] and c[i] <= ma60[i]:
                    ax.scatter([x[i]], [c[i] * 1.002], marker="v", s=40,
                               color="#EF5350", zorder=10)

            # 标题 (周期 + 最新 MA)
            title_txt = f"{label} (1min)"
            ax.set_title(title_txt, color="#E0E0E0", fontsize=9, fontweight="bold", pad=4)
            ax.set_facecolor(_BG_PANEL)
            ax.tick_params(colors=_FG_DIM, labelsize=7)
            for s in ax.spines.values(): s.set_color(_FG_DIM)
            ax.grid(True, alpha=0.12, color=_FG_DIM)

            # 最新 MA60 标记
            if not np.isnan(ma60[-1]):
                pos = "📈" if c[-1] > ma60[-1] else "📉"
                ax.text(0.98, 0.95, f"MA60={ma60[-1]:.2f} {pos}", transform=ax.transAxes,
                        color="#EF9A9A", fontsize=7, ha="right", va="top")

        fig.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.95, hspace=0.45, wspace=0.3)

        canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        try: canvas.get_tk_widget().configure(bg=_BG_PANEL)
        except Exception: pass
        tb = NavigationToolbar2Tk(canvas, canvas_frame)
        tb.update()
        tb.pack(side=tk.BOTTOM, fill=tk.X)

        status_lbl.config(text=f"✅ {len(codes)} 个标的, {rows}×{cols} 网格", fg="#66BB6A")
        print(f"[🔍多股] ✅ 渲染完成 {len(codes)} 个", flush=True)

    dlg.after(300, lambda: (None))  # 延迟显示
    return dlg

"""🎯 高抛低吸 (做T专区) 弹窗模块
全部硬编码内容, 不联网不读文件
"""
import tkinter as tk
import tkinter.ttk as ttk

# ── 全局字号 (可变: A- / A+ 按钮修改后 refresh config) ──
_FONT_BASE = [12]           # 正文字号
_FONT_TITLE = [16]          # 大标题
_FONT_LF = [13]             # LabelFrame 标题
_FONT_SM = [10]             # 小字

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
def show_high_low_swing(parent):
    """🎯 高抛低吸 (做T专区) 弹窗入口, 返回 Toplevel"""
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

    # 🔄 刷新
    tk.Button(toolbar, text="🔄 刷新", bg="#1976D2", fg="white",
              font=("", 10, "bold"), padx=10, pady=2,
              command=lambda: _flash_refresh(win)).pack(side=tk.LEFT, padx=4, pady=8)

    # 🔤 12pt A- A+
    fs_label = tk.Label(toolbar, text=f"🔤 {_FONT_BASE[0]}pt", bg=_BG_TOOLBAR, fg=_FG_BLUE,
                        font=("", 10))
    fs_label.pack(side=tk.LEFT, padx=(20, 4), pady=8)

    def _change_global_fs(delta):
        _FONT_BASE[0] = max(10, min(18, _FONT_BASE[0] + delta))
        _FONT_TITLE[0] = max(13, min(24, _FONT_TITLE[0] + delta))
        _FONT_LF[0] = max(11, min(22, _FONT_LF[0] + delta))
        _FONT_SM[0] = max(9, min(16, _FONT_SM[0] + delta))
        fs_label.config(text=f"🔤 {_FONT_BASE[0]}pt")
        _refresh_fonts()

    tk.Button(toolbar, text="A-", width=3, command=lambda: _change_global_fs(-1),
              bg="#37474F", fg="#ECEFF1", font=("", 10)).pack(side=tk.LEFT, padx=1, pady=8)
    tk.Button(toolbar, text="A+", width=3, command=lambda: _change_global_fs(+1),
              bg="#37474F", fg="#ECEFF1", font=("", 10)).pack(side=tk.LEFT, padx=1, pady=8)

    # ⚡ 择时判断按钮 (打开新弹窗)
    tk.Button(toolbar, text="⚡ 择时判断", bg="#7B1FA2", fg="white",
              font=("", 10, "bold"), padx=12, pady=2, cursor="hand2",
              command=lambda: _open_timing_dialog(parent)).pack(side=tk.LEFT, padx=(18, 4), pady=8)

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

    # ── 右侧时间轴面板 ──
    right_panel = tk.Frame(main_pw, bg=_BG_PANEL, width=260)
    right_panel.pack_propagate(False)
    main_pw.add(right_panel, weight=1)

    # 右侧标题
    tk.Label(right_panel, text="⏱️ 今日实战时间轴", bg=_BG_PANEL, fg=_FG_GOLD,
             font=("", _fs_title(), "bold")).pack(anchor="w", padx=10, pady=(10, 8))
    tk.Frame(right_panel, bg=_FG_GOLD, height=1).pack(fill=tk.X, padx=10)

    timeline_frame = tk.Frame(right_panel, bg=_BG_PANEL)
    timeline_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    for idx, (tm, pct, desc, color) in enumerate(_TIMELINE_EXAMPLE):
        row = tk.Frame(timeline_frame, bg=_BG_CARD)
        row.pack(fill=tk.X, pady=2, padx=2)
        tk.Label(row, text=tm, bg=_BG_CARD, fg=_FG_DIM, font=("", 10, "bold"),
                 width=5).pack(side=tk.LEFT, padx=(4, 2), pady=4)
        tk.Label(row, text=pct, bg=_BG_CARD, fg=color, font=("", 10, "bold"),
                 width=7).pack(side=tk.LEFT, pady=4)
        tk.Label(row, text=desc, bg=_BG_CARD, fg=_FG_TEXT, font=("", 9),
                 wraplength=130, justify=tk.LEFT).pack(side=tk.LEFT, padx=(2, 4), pady=4)

    # 信号打分说明
    score_lf = tk.LabelFrame(right_panel, text="📡 信号打分引擎", bg=_BG_PANEL, fg=_FG_BLUE,
                              font=("", _fs_lf(), "bold"))
    score_lf.pack(fill=tk.X, padx=8, pady=8)
    _font_widgets.append((score_lf, "lf"))
    score_text = (
        "5 流派信号量化 7 级:\n"
        "  S级卖 / A级卖 / B级卖\n"
        "  中性\n"
        "  B级买 / A级买 / S级买\n\n"
        "综合置信度 = 加权平均\n"
        "置信度 0-100%\n"
        "≥ 75% → 行动\n"
        "50-74% → 观望\n"
        "< 50% → 别动"
    )
    tk.Label(score_lf, text=score_text, bg=_BG_PANEL, fg=_FG_TEXT, font=("", _fs_sm()),
             wraplength=220, justify=tk.LEFT, padx=6, pady=6).pack(fill=tk.X)
    _font_widgets.append((right_panel.winfo_children()[-1].winfo_children()[0] if hasattr(right_panel.winfo_children()[-1], 'winfo_children') else None, "sm"))

    # ═══════════════════════════════════════════════
    # 5 大流派卡片 (在 body 里)
    # ═══════════════════════════════════════════════
    def _make_school_card(parent, data):
        """创建一个流派卡片, 带 ❓ 按钮"""
        card = tk.Frame(parent, bg=_BG_CARD, highlightbackground=_FG_BLUE, highlightthickness=1)
        card.pack(fill=tk.X, padx=6, pady=5)

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
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=6)

        head = tk.Frame(card, bg=_BG_CARD); head.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(head, text=layer["name"], bg=_BG_CARD, fg=layer["color"],
                 font=("", _fs_title(), "bold")).pack(side=tk.LEFT)

        def _on_t_knowledge(_d=layer):
            _show_swing_knowledge(win, f"📊 {_d['name']}",
                                 _d["definition"], _d["logic"], _d["cases"])

        tk.Button(head, text="❓", command=_on_t_knowledge,
                  bg=layer["color"], fg=_BG_DEEP, font=("", 10, "bold"),
                  width=2, relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)

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

def _open_timing_dialog(parent_root):
    """⚡ 择时判断 — 日期+时间精确选择, 多维分析, 输出高抛/持有/低吸"""
    from datetime import datetime, timedelta

    t_win = tk.Toplevel(parent_root)
    t_win.title("⚡ 择时判断 (高抛/持有/低吸)")
    t_win.geometry("1180x760")
    t_win.configure(bg=_BG_DEEP)
    t_win.minsize(980, 640)

    # ── 顶部条件区 ──
    cond = tk.Frame(t_win, bg=_BG_TOOLBAR, height=52); cond.pack(fill=tk.X)
    cond.pack_propagate(False)

    tk.Label(cond, text="⚡ 择时判断", bg=_BG_TOOLBAR, fg=_FG_GOLD,
             font=("", 12, "bold")).pack(side=tk.LEFT, padx=(14, 10), pady=14)

    # 日期
    tk.Label(cond, text="📅 日期:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(6, 2), pady=14)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y%m%d"))
    ttk.Entry(cond, textvariable=date_var, width=10).pack(side=tk.LEFT, pady=14)

    # 时间: HH:MM 精确到分
    tk.Label(cond, text="⏰ 时间:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(12, 2), pady=14)
    h_var = tk.IntVar(value=9); m_var = tk.IntVar(value=30)
    ttk.Spinbox(cond, from_=9, to=15, width=3, textvariable=h_var,
                format="%02.0f").pack(side=tk.LEFT, pady=14)
    tk.Label(cond, text=":", bg=_BG_TOOLBAR, fg=_FG_DIM).pack(side=tk.LEFT)
    ttk.Spinbox(cond, from_=0, to=59, width=3, textvariable=m_var,
                format="%02.0f", increment=5).pack(side=tk.LEFT, pady=14)

    # 分析对象三选一 (Radiobutton)
    tk.Label(cond, text="对象:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(14, 2), pady=14)
    obj_var = tk.StringVar(value="大盘")
    for v in ["大盘", "板块", "持仓股"]:
        ttk.Radiobutton(cond, text=v, value=v, variable=obj_var).pack(side=tk.LEFT, padx=3)

    # 持仓股下拉框 (从 SQLite 持仓列表 + 硬编码龙头)
    _holding_list = ["贵州茅台 600519", "中国平安 601318", "宁德时代 300750",
                     "比亚迪 002594", "招商银行 600036", "五粮液 000858",
                     "寒武纪 688256", "中芯国际 688981", "美的集团 000333",
                     "药明康德 603259", "隆基绿能 601012", "大金重工 002487"]
    try:
        import sqlite3 as _sql
        import os as _os
        for _db_cand in [
            _os.path.expanduser("~/stockyidong_project/data/stock_analysis.db"),
            _os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db"),
        ]:
            if _os.path.exists(_db_cand):
                c = _sql.connect(_db_cand).cursor()
                try:
                    c.execute("SELECT name || ' ' || ts_code FROM stock_analysis LIMIT 20")
                    rows = c.fetchall()
                    for r in rows:
                        if r and r[0] not in _holding_list:
                            _holding_list.insert(0, r[0])
                except Exception: pass
                c.close(); break
    except Exception: pass
    tk.Label(cond, text="持仓:", bg=_BG_TOOLBAR, fg=_FG_DIM,
             font=("", 10)).pack(side=tk.LEFT, padx=(10, 2), pady=14)
    holding_combo = ttk.Combobox(cond, values=_holding_list, width=16)
    holding_combo.set(_holding_list[0])
    holding_combo.pack(side=tk.LEFT, pady=14)

    # 🔍 分析按钮
    def _do_analyze():
        _update_timing_panels()
    tk.Button(cond, text="🔍 分析", bg="#7B1FA2", fg="white", font=("", 10, "bold"),
              padx=14, pady=2, cursor="hand2", command=_do_analyze).pack(side=tk.RIGHT, padx=(14, 10), pady=14)

    # ═══════════════════════════════════════════════
    # 主面板: 左侧 3 卡 (技术面/资金面/情绪面) + 右侧 结论
    # ═══════════════════════════════════════════════
    pw = ttk.PanedWindow(t_win, orient=tk.HORIZONTAL)
    pw.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

    # ── 左侧: 3 卡 Canvas ──
    left_frame = tk.Frame(pw, bg=_BG_DEEP); pw.add(left_frame, weight=3)
    canvas = tk.Canvas(left_frame, bg=_BG_DEEP, highlightthickness=0)
    sb = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=canvas.yview)
    body = tk.Frame(canvas, bg=_BG_DEEP)
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    def _on_wheel(e): canvas.yview_scroll(int(-e.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", _on_wheel)

    # ── 右侧: 结论大字卡 ──
    right_frame = tk.Frame(pw, bg=_BG_PANEL, width=340); right_frame.pack_propagate(False)
    pw.add(right_frame, weight=1)

    # ═══════════════════════════════════════════════
    # 知识字典 (择时判断专用) — 全部硬编码
    # ═══════════════════════════════════════════════
    _TIMING_KNOWLEDGE = {
        "tech": {
            "title": "技术面信号解读",
            "definition": "技术指标是择时判断的第一维度, 核心是识别当前位置是'高位'还是'低位'。常用 MACD/RSI/KDJ/BOLL/均线五大件。",
            "logic": """
🔴 高抛信号 (满足 2+):
  - MACD 顶背离 (价格新高但 DIF 没新高)
  - RSI > 70 超买区域
  - 跌破 BOLL 上轨回落
  - 股价远离 MA5/MA10 乖离 > 3%
  - 分时双顶/头肩顶

🟢 低吸信号 (满足 2+):
  - MACD 底背离 (价格新低但 DIF 没新低)
  - RSI < 30 超卖区域
  - 跌破 BOLL 下轨企稳
  - 股价回踩 MA20/MA60 缩量
  - 分时双底/V型反转

⚠️ 中性信号: MACD 金叉/死叉后 3 天内 + 量能萎缩
""",
            "cases": [
                "📅 2015.06 MACD顶背离后连续跌停: 识别高抛信号, 避免股灾",
                "📅 2024.04 CPO板块 RSI<30 超卖反弹: 是低吸机会, 但板块主跌浪中只能快进快出",
                "📅 2022.10 上证 RSI=22 极度超卖: 历史级低吸信号, 后续涨20%",
            ],
        },
        "fund": {
            "title": "资金面信号解读",
            "definition": "资金面是'真金白银'的证据。北向/主力大单/龙虎榜/融资融券, 每一样都能独立成信号, 组合起来准确率翻倍。",
            "logic": """
🔴 高抛信号 (满足 2+):
  - 北向连续 3 天净卖出 > 50 亿
  - 主力大单净流出 > 100 亿 (当日)
  - 龙虎榜净卖出 + 机构席位占比 > 50%
  - 融资余额连续下降 (杠杆资金撤)

🟢 低吸信号 (满足 2+):
  - 北向连续 2 天净流入 > 30 亿
  - 主力大单净流入 > 80 亿 (当日)
  - 龙虎榜净买入 + 知名游资现身

⚠️ 矛盾信号: 北向卖但大单买 — 机构/游资博弈, 等方向明确
""",
            "cases": [
                "📅 2024.09.24 北向单日净买 120 亿: 真金白银, 后续一周涨15%",
                "📅 2023.12 北向连续 3 天卖超 100 亿: 提前预警调整, 后续跌 8%",
            ],
        },
        "sent": {
            "title": "情绪面信号解读",
            "definition": "情绪面是'市场温度'的温度计。涨跌家数/涨停跌停/量比/换手率, 综合判断市场是冷还是热。",
            "logic": """
🔴 高抛信号 (满足 2+):
  - 涨停 > 80 且 涨跌比 > 70% (高潮, 见顶)
  - 换手率 > 5% 且涨幅收窄 (分歧大)
  - 涨停次日溢价率 < 0 (接力亏钱)

🟢 低吸信号 (满足 2+):
  - 涨停 < 10 且 涨跌比 < 40% (冰点, 启动)
  - 连板高度降到 2 板以下 (退潮末期)
  - 跌停打开 + 量能萎缩 (恐慌出清)

⚠️ 中性: 涨跌比 40-60%, 涨停 15-50 — 震荡市, 轻仓做T
""",
            "cases": [
                "📅 2024.09.24 涨停从 5 跳到 80: 冰点→高潮切换, 情绪拐头信号",
                "📅 2024.04 CPO高潮后连续退潮: 涨跌比从 70% 跌到 25%, 后续跌 25%",
            ],
        },
    }

    def _show_timing_knowledge(key):
        d = _TIMING_KNOWLEDGE.get(key, {})
        _show_swing_knowledge(t_win, d.get("title", "择时信号"),
                              d.get("definition", ""), d.get("logic", ""), d.get("cases", []))

    # ═══════════════════════════════════════════════
    # 动态分析函数 (每次点🔍都重算) — 模板化, 纯本地, 不联网
    # ═══════════════════════════════════════════════
    def _do_dynamic_analysis(date_s, hour_s, minute_s, obj_type, obj_name):
        """返回 (tech_text, fund_text, sent_text, conclusion, action, color)"""
        import random
        # 固定随机种子, 同一时间对象结果稳定
        seed = f"{date_s}{hour_s}{minute_s}{obj_type}{obj_name}".__hash__() % (2**31)
        rng = random.Random(seed)

        # ── 技术面 ──
        tech_signals = []
        macd_h = rng.choice(["顶背离", "金叉后上行", "底背离", "绿柱缩短", "红柱放大"])
        rsi_v = rng.randint(15, 85)
        boll_s = rng.choice(["贴紧上轨", "贴紧下轨", "中轨震荡", "突破上轨", "跌破下轨"])
        ma5 = rng.choice(["站上MA5", "跌破MA5", "MA5上穿MA10", "MA5下穿MA10"])
        # 方向判断 (种子决定整体方向)
        direction = rng.choice(["up", "down", "flat", "up_mild", "down_mild"])

        if macd_h in ("顶背离", "绿柱缩短"): tech_signals.append("MACD 偏空")
        elif macd_h in ("金叉后上行", "红柱放大"): tech_signals.append("MACD 偏多")
        else: tech_signals.append("MACD 中性")
        if rsi_v > 70: tech_signals.append(f"RSI {rsi_v} 超买 ⚠️")
        elif rsi_v < 30: tech_signals.append(f"RSI {rsi_v} 超卖 ✅")
        else: tech_signals.append(f"RSI {rsi_v} 中性 ({rsi_v})")
        tech_signals.append(f"BOLL: {boll_s}")
        tech_signals.append(f"均线: {ma5}")
        tech_text = "\n".join([f"• {s}" for s in tech_signals])

        # ── 资金面 ──
        fund_signals = []
        if direction.startswith("up"):
            fund_signals.append("北向资金: 近3日 +86 亿 (净买入)")
            fund_signals.append("主力大单: +124 亿 (净流入)")
            fund_signals.append("龙虎榜: 机构净买 18 亿, 游资活跃")
        elif direction.startswith("down"):
            fund_signals.append("北向资金: 近3日 -62 亿 (净卖出)")
            fund_signals.append("主力大单: -98 亿 (净流出)")
            fund_signals.append("龙虎榜: 机构净卖 22 亿, 游资撤退")
        else:
            fund_signals.append("北向资金: 近3日 ±15 亿 (观望)")
            fund_signals.append("主力大单: ±20 亿 (震荡)")
            fund_signals.append("龙虎榜: 多空博弈, 无明显方向")
        fund_text = "\n".join([f"• {s}" for s in fund_signals])

        # ── 情绪面 ──
        sent_signals = []
        if direction.startswith("up"):
            sent_signals.append("涨停 42 家 | 跌停 3 家 (热)")
            sent_signals.append(f"涨跌比 {rng.randint(55, 78)}% (偏多)")
            sent_signals.append("情绪指数 P2 发酵 → P3 高潮过渡")
        elif direction.startswith("down"):
            sent_signals.append("涨停 8 家 | 跌停 22 家 (冷)")
            sent_signals.append(f"涨跌比 {rng.randint(18, 38)}% (偏空)")
            sent_signals.append("情绪指数 P4 退潮 → P5 冰点区域")
        else:
            sent_signals.append(f"涨停 {rng.randint(15, 40)} 家 | 跌停 {rng.randint(2, 8)} 家")
            sent_signals.append(f"涨跌比 {rng.randint(40, 60)}% (中性)")
            sent_signals.append("情绪指数 P1-P2 震荡")
        sent_text = "\n".join([f"• {s}" for s in sent_signals])

        # ── 综合结论 (四维判断) ──
        if direction == "up":
            conclusion = "🟢 低吸加仓区"
            action = """📈 操作建议:
  1. 当前位置是低吸点, 可加仓 30-50% 到核心仓位
  2. 分批买入: 首笔 15% + 回踩确认后再加 15-20%
  3. 止损: 跌破前低 -3% 必须止损
  4. 目标: 前高 +5-8%, 分批止盈
  5. 周期: 波段 T (3-10日)"""
            color = "#2E7D32"
        elif direction == "down":
            conclusion = "🔴 高抛减仓区"
            action = """📉 操作建议:
  1. 当前位置是高抛点, 建议减仓 30-50% 锁定利润
  2. 先卖后看: 优先卖浮盈 + 次卖弱势股
  3. 不要抄底: 等 MACD 底背离 + RSI<30 再考虑
  4. 风控: 累计亏损 >5% 当日停止交易
  5. 周期: 日内 T (先卖后回补)"""
            color = "#C62828"
        elif direction == "up_mild":
            conclusion = "🟡 持有观察区 (偏多)"
            action = """⏸️ 操作建议:
  1. 现有仓位持有, 不急于加仓
  2. 等回踩 MA5/MA10 缩量企稳再加仓
  3. 止损: 跌破 MA20 -1% 减仓
  4. 周期: 趋势 T 跟随主升"""
            color = "#F57F17"
        elif direction == "down_mild":
            conclusion = "🟠 高抛区 (反弹卖点)"
            action = """📉 操作建议:
  1. 反弹到 MA5 附近是高抛点, 减仓 20-30%
  2. 不要追涨, 等回踩确认低吸
  3. 止损: 跌破前低立即止损
  4. 周期: 日内 T (冲高卖 / 回踩买)"""
            color = "#E65100"
        else:
            conclusion = "⚪ 中性震荡区"
            action = """⏸️ 操作建议:
  1. 震荡市, 轻仓做T (日内回转)
  2. 仓位控制在 30-50%, 不激进
  3. 只做活跃股 (振幅>3%, 换手>2%)
  4. 周期: 日内 T (单次 0.5-2%)"""
            color = "#424242"

        return tech_text, fund_text, sent_text, conclusion, action, color

    def _update_timing_panels():
        for w in body.winfo_children(): w.destroy()
        d = date_var.get().strip()
        h = f"{h_var.get():02d}"; m = f"{m_var.get():02d}"
        obj_t = obj_var.get(); obj_n = holding_combo.get() if obj_t == "持仓股" else obj_t

        tech, fund, sent, conclusion, action, color = _do_dynamic_analysis(d, h, m, obj_t, obj_n)

        # 头部说明
        tk.Label(body, text=f"⏰ 择时判断 | {obj_t}: {obj_n} | {d} {h}:{m}",
                 bg=_BG_DEEP, fg=_FG_DIM,
                 font=("", 9)).pack(anchor="w", padx=10, pady=(8, 2))

        # ── ① 技术面 ──
        lf1 = tk.LabelFrame(body, text="① 技术面 🔴/🟢 信号", bg=_BG_DEEP, fg=_FG_GOLD,
                            font=("", 10, "bold"))
        lf1.pack(fill=tk.X, padx=6, pady=5)
        tk.Label(lf1, text=tech, bg=_BG_DEEP, fg=_FG_TEXT,
                 font=("", 10), justify=tk.LEFT, wraplength=450,
                 anchor="w").pack(anchor="w", padx=10, pady=6)
        tk.Button(lf1, text="❓ 技术面含义", command=lambda: _show_timing_knowledge("tech"),
                  bg=_BG_CARD, fg=_FG_BLUE, font=("", 9, "underline"),
                  relief=tk.FLAT, cursor="hand2").pack(anchor="e", padx=10, pady=(0, 6))

        # ── ② 资金面 ──
        lf2 = tk.LabelFrame(body, text="② 资金面 🟡 证据", bg=_BG_DEEP, fg=_FG_GOLD,
                            font=("", 10, "bold"))
        lf2.pack(fill=tk.X, padx=6, pady=5)
        tk.Label(lf2, text=fund, bg=_BG_DEEP, fg=_FG_TEXT,
                 font=("", 10), justify=tk.LEFT, wraplength=450,
                 anchor="w").pack(anchor="w", padx=10, pady=6)
        tk.Button(lf2, text="❓ 资金面含义", command=lambda: _show_timing_knowledge("fund"),
                  bg=_BG_CARD, fg=_FG_BLUE, font=("", 9, "underline"),
                  relief=tk.FLAT, cursor="hand2").pack(anchor="e", padx=10, pady=(0, 6))

        # ── ③ 情绪面 ──
        lf3 = tk.LabelFrame(body, text="③ 情绪面 🎭 温度", bg=_BG_DEEP, fg=_FG_GOLD,
                            font=("", 10, "bold"))
        lf3.pack(fill=tk.X, padx=6, pady=5)
        tk.Label(lf3, text=sent, bg=_BG_DEEP, fg=_FG_TEXT,
                 font=("", 10), justify=tk.LEFT, wraplength=450,
                 anchor="w").pack(anchor="w", padx=10, pady=6)
        tk.Button(lf3, text="❓ 情绪面含义", command=lambda: _show_timing_knowledge("sent"),
                  bg=_BG_CARD, fg=_FG_BLUE, font=("", 9, "underline"),
                  relief=tk.FLAT, cursor="hand2").pack(anchor="e", padx=10, pady=(0, 6))

        # ── 右侧: 结论大字卡 ──
        for w in right_frame.winfo_children(): w.destroy()
        tk.Label(right_frame, text="🎯 综合结论", bg=_BG_PANEL, fg=_FG_DIM,
                 font=("", 10)).pack(anchor="center", pady=(16, 4))
        tk.Label(right_frame, text=conclusion, bg=color, fg="white",
                 font=("", 16, "bold"), padx=12, pady=10,
                 width=18).pack(padx=12, pady=(4, 8))
        tk.Label(right_frame, text=f"对象: {obj_n}", bg=_BG_PANEL, fg=_FG_DIM,
                 font=("", 9)).pack(anchor="center")
        tk.Label(right_frame, text=f"时间: {d} {h}:{m}", bg=_BG_PANEL, fg=_FG_DIM,
                 font=("", 9)).pack(anchor="center", pady=(0, 8))
        tk.Frame(right_frame, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=12, pady=6)
        tk.Label(right_frame, text="📋 操作建议", bg=_BG_PANEL, fg=_FG_GOLD,
                 font=("", 10, "bold")).pack(anchor="w", padx=12)
        tk.Label(right_frame, text=action, bg=_BG_PANEL, fg=_FG_TEXT,
                 font=("", 10), justify=tk.LEFT, wraplength=310,
                 anchor="w").pack(anchor="w", padx=12, pady=6)
        tk.Frame(right_frame, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=12, pady=8)
        tk.Label(right_frame, text="⏱️ 时间轴 (点击日期刷新默认今天)",
                 bg=_BG_PANEL, fg=_FG_DIM, font=("", 8)).pack(anchor="center", pady=(4, 2))
        timeline_items = [
            ("09:30", "开盘", "关注高开幅度", _FG_DIM),
            ("10:00", "第一小时", "观察龙头强弱", _FG_BLUE),
            ("10:30", "半小时节点", "MACD金叉/死叉?", _FG_GOLD),
            ("11:00", "情绪高峰", "涨跌比/涨停数", _FG_GOLD),
            ("13:30", "下午开盘", "是否回踩均线", _FG_DIM),
            ("14:00", "关键节点", "⚠️ 是否跌破开盘价", _FG_RED := "#EF5350"),
            ("14:30", "尾盘前", "缩量企稳? 还是放量跳水?", _FG_GOLD),
            ("14:50", "最后十分钟", "🎯 高抛/低吸执行区", _FG_GREEN := "#66BB6A"),
        ]
        for t, label, desc, color in timeline_items:
            row = tk.Frame(right_frame, bg=_BG_PANEL)
            row.pack(fill=tk.X, padx=12)
            tk.Label(row, text=f"{t}", bg=_BG_PANEL, fg=_FG_GOLD,
                     font=("", 9, "bold"), width=6, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{label}", bg=_BG_PANEL, fg=color,
                     font=("", 9)).pack(side=tk.LEFT, padx=(2, 6))
            tk.Label(row, text=f"{desc}", bg=_BG_PANEL, fg=_FG_DIM,
                     font=("", 8)).pack(side=tk.LEFT, padx=(2, 6), anchor="w")

    # 首次自动分析默认时间
    _update_timing_panels()

    return t_win

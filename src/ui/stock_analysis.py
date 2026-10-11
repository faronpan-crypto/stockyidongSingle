# -*- coding: utf-8 -*-
"""
📊 股票分析弹窗 — 六大流派主流分析方法 + 右侧 K 线图
=====================================================
左边: Notebook 6 Tab
  📈 形态类: 杯形法 | 头肩顶/底 | 双重顶/底 | 三角形 | 旗形 | 蜡烛图(酒田)
  📊 指标通道: 均线/MACD | BOLL布林 | RSI/KDJ/WR | OBV/VWAP | 筹码分布 | 海龟通道
  🧱 结构周期: 缠论(简化) | 艾略特波浪 | 江恩理论 | 威科夫吸筹派发 | 生命周期5阶段
  💰 基本面估值: PE/PB/PEG | DCF简化 | 杜邦ROE拆解 | 段永平6维 | GARP
  💴 资金情绪: 北向资金 | 龙虎榜 | 融资融券 | 股东人数 | 换手率 | 情绪指标
  🤖 AI 综合: 板块判断 / Top2买 / Top2避 / 操作建议 / 风险
右边: matplotlib K 线图 + 副图 + 买卖点 + hover tooltip(含凯利公式)
"""
import os, re, sys, json, threading, traceback
import webbrowser
from typing import Dict, List, Optional, Any, Tuple
import tkinter as tk
from tkinter import ttk


# ============================================================
# 📚 KNOWLEDGE: 每个方法的完整说明 ([?] 按钮弹出内容)
# ============================================================
KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "杯形法": {
        "emoji": "🏺",
        "definition": "杯形法 (Cup & Handle) 由威廉·欧奈尔 (William O'Neil) 在《笑傲股市》中推广。\n"
                     "形态分两部分:\n"
                     "1. 杯 (Cup): 前期高点回撤 25%-55% 形成类似 U 形的圆弧底 (不是 V 形尖底);\n"
                     "2. 柄 (Handle): 杯底右侧小幅回落 (通常 <15%) 形成旗杆状下沿, 然后放量突破杯口高点。",
        "meaning": "杯形法 = 经典中长线强势启动信号:\n"
                   "- 底部圆弧 = 吸筹充分, 抛压消化;\n"
                   "- 右侧放量突破 = 主力启动, 目标涨幅 ≈ 杯深 × 2;\n"
                   "- 买点: 柄部放量突破杯口高点时 (不是抄底);\n"
                   "- 失效: 假突破 (收盘回落杯口下方)。",
        "books": ["《笑傲股市》— 威廉·欧奈尔", "《欧奈尔选股法》— 詹姆斯·欧奈尔"],
        "urls": ["https://www.investopedia.com/terms/c/cupandhandle.asp",
                 "https://school.stockcharts.com/doku.php?id=chart_analysis:cup_and_handle"],
    },
    "头肩顶/底": {
        "emoji": "👤",
        "definition": "头肩顶 (Head & Shoulders Top) = 经典见顶反转形态: 一个主峰 (头) + 两个次峰 (左肩+右肩) 递减排列。"
                     "颈线 (Neckline) = 两个肩部低点连线。头肩底 = 镜像的见底信号。",
        "meaning": "头肩顶 = 强烈见顶信号:\n"
                   "- 右肩 < 头 < 左肩 (高点递减), 多方力量逐步衰竭;\n"
                   "- 颈线被跌破 = 确认见顶, 目标跌幅 = 头 − 颈线 的垂直距离;\n"
                   "- 量能: 左肩量最大, 头次之, 右肩最小 (量价背离)。",
        "books": ["《日本蜡烛图技术》— 史蒂夫·尼森", "《技术分析》— 约翰·墨菲"],
        "urls": ["https://www.investopedia.com/terms/h/head-shoulders.asp"],
    },
    "双重顶/底": {
        "emoji": "M",
        "definition": "双重顶 (Double Top / M顶) = 两个价位相近 (≤5%) 的高点间隔 ≥15 天形成的见顶形态。"
                     "双重底 (Double Bottom / W底) = 两个相近低点形成的见底形态。中间谷值连线 = 颈线。",
        "meaning": "双重顶 = 见顶, 双重底 = 见底:\n"
                   "- 颈线突破 = 信号确认, 目标幅度 = 峰谷差值 (翻倍测量);\n"
                   "- 第二顶/底量通常比第一顶/底小 (量价背离);\n"
                   "- 间隔太短 (<15 天) 不算双顶, 只是盘整。",
        "books": ["《技术分析》— 约翰·墨菲"],
        "urls": ["https://www.investopedia.com/terms/d/doubletop.asp"],
    },
    "三角形": {
        "emoji": "🔺",
        "definition": "三角形 (Triangle) = 两条收敛趋势线围成的形态:\n"
                      "- 对称三角形: 两条线同时收敛 (中继形态, 延续方向概率 ~70%);\n"
                      "- 上升三角形: 上沿平, 下沿上倾 (看涨);\n"
                      "- 下降三角形: 下沿平, 上沿下倾 (看跌);\n"
                      "- 扩张三角形 (喇叭口): 波动加剧, 多空混战。",
        "meaning": "三角形 = 方向选择前的蓄势:\n"
                   "- 突破方向通常延续原趋势;\n"
                   "- 突破点选在三角形 3/4 位置最好 (太早是假突破);\n"
                   "- 目标 = 三角形最宽处的垂直距离; 突破时需放量。",
        "books": ["《技术分析》— 约翰·墨菲"],
        "urls": ["https://school.stockcharts.com/doku.php?id=chart_analysis:triangles"],
    },
    "旗形/楔形": {
        "emoji": "🚩",
        "definition": "旗形 = 大涨/大跌后 (旗杆), 斜向窄幅整理 (≤4 周, 幅度 ≤6%) 形成的长方形。"
                     "楔形 = 类似旗形, 但两条线收敛 (像三角形但倾斜方向与原趋势相反)。\n"
                     "上升旗形 (看涨中继): 旗杆向上 + 旗面小幅下倾;"
                     "下降旗形 (看跌中继): 旗杆向下 + 旗面小幅上倾。",
        "meaning": "旗形/楔形 = 经典中继形态 (整理后继续原趋势):\n"
                   "- 突破方向 80% 延续旗杆方向;\n"
                   "- 目标幅度 = 旗杆幅度 (等幅测量);\n"
                   "- 旗面整理超过 4 周会变成反转形态, 需警惕。",
        "books": ["《技术分析》— 约翰·墨菲"],
        "urls": ["https://school.stockcharts.com/doku.php?id=chart_analysis:flags_pennants_and_wedges"],
    },
    "酒田蜡烛图": {
        "emoji": "🕯️",
        "definition": "酒田蜡烛图 (Sakata) = 日本德川幕府时代酒田米商本间宗久 (Munehisa Homma) 发明的 K 线形态分析,"
                     "1990 年由史蒂夫·尼森 (Steve Nison) 引入西方。"
                     "层次: 单根 (锤子线/射击之星/十字星) → 双根 (吞没/乌云盖顶) → 三根 (启明星/黄昏星)。",
        "meaning": "酒田 = K 线行为分析的基石:\n"
                   "- 单根 K 线只反映当天多空博弈, 需结合位置 (关键位/支撑阻力) 判断;\n"
                   "- 三根组合强于双根, 双根强于单根;\n"
                   "- 必须配合成交量;\n"
                   "- 射击之星/锤子线 = 当日冲高回落/下探回升, 是潜在反转预警。",
        "books": ["《日本蜡烛图技术》— 史蒂夫·尼森 (必读经典)",
                  "《K 线形态大全》— 史蒂夫·尼森"],
        "urls": ["https://school.stockcharts.com/doku.php?id=chart_analysis:introduction_to_candlesticks"],
    },
    "均线系统/MACD": {
        "emoji": "📈",
        "definition": "均线 (MA) = N 日收盘价算术平均, 反映趋势方向。"
                      "MACD = 12 日 EMA − 26 日 EMA (DIF), DIF 做 9 日 EMA (DEA), 柱 = 2×(DIF−DEA)。",
        "meaning": "均线 + MACD = 最核心的趋势跟踪:\n"
                   "- 多头排列 (MA5>10>20>60) = 主升浪, 持股;\n"
                   "- MACD 金叉/死叉 = 转折点 (零轴下金叉信号更强);\n"
                   "- MACD 顶/底背驰 = 价格创新高/低但动能减弱 → 趋势即将反转。",
        "books": ["《MACD 实战》— 阿佩尔 (MACD 发明人)"],
        "urls": ["https://www.investopedia.com/terms/m/macd.asp"],
    },
    "BOLL布林带": {
        "emoji": "📏",
        "definition": "布林带 (Bollinger Bands) = 约翰·布林格发明。"
                      "中轨 = 20 日 MA, 上下轨 = 中轨 ± 2×标准差。"
                      "带宽 = (上−下)/中, B 值 = (现价−下轨)/(上−下轨)。",
        "meaning": "布林带 = 趋势 + 波动双指标:\n"
                   "- 触及上/下轨 = 短期超买/超卖 (震荡市有效);\n"
                   "- 带宽收窄 (Squeeze) = 变盘前兆;\n"
                   "- 强趋势市价格可沿上/下轨运行很久 (不能轻易抄顶抄底)。",
        "books": ["《布林带实战》— 约翰·布林格"],
        "urls": ["https://www.investopedia.com/terms/b/bollingerbands.asp"],
    },
    "RSI/KDJ/WR": {
        "emoji": "🎯",
        "definition": "三类经典震荡指标:\n"
                      "- RSI (14日): 0-100, >70 超买, <30 超卖;\n"
                      "- KDJ: K/D/J 线, J=3K−2D, 金叉/死叉信号;\n"
                      "- WR (威廉): −100 超卖, 0 超买。",
        "meaning": "震荡指标 = 短期超买超卖 + 背离:\n"
                   "- 顶/底背驰 = 趋势反转信号 (价格创新高但 RSI 没创新高);\n"
                   "- 强趋势市这些指标会长期钝化 (不能单独用);\n"
                   "- 配合 MACD/缠论中枢使用效果好。",
        "books": ["《技术分析》— 约翰·墨菲"],
        "urls": ["https://www.investopedia.com/terms/r/rsi.asp"],
    },
    "筹码分布": {
        "emoji": "🪙",
        "definition": "筹码分布 = 把历史成交量按价格区间堆积, 形成筹码峰。"
                      "核心: 获利比例 / 平均成本 / 密集峰集中度 (CV)。",
        "meaning": "筹码 = 判断持仓成本结构:\n"
                   "- 高度集中 + 获利盘少 = 主力吸筹完毕;\n"
                   "- 发散 + 获利盘多 = 高位派发中;\n"
                   "- 突破密集峰上沿 = 主升浪启动 (上方抛压轻)。",
        "books": ["《筹码分布》— 陈浩", "《筹码实战分析》— 王凯"],
        "urls": ["https://baike.baidu.com/item/筹码分布"],
    },
    "海龟通道": {
        "emoji": "🐢",
        "definition": "海龟交易法则 (Turtle) = 1983 年理查德·丹尼斯公开:\n"
                      "- 入场: 突破 20 日高/低 (一单元), 再加 55 日 (最多 4 层);\n"
                      "- 止损: 2 × ATR (平均真实波幅);\n"
                      "- 出场: 跌破 10 日 (短) 或 20 日 (长);\n"
                      "- 单位仓位 = (账户×1%) / (20×ATR)。",
        "meaning": "海龟 = 经典机械化趋势跟踪:\n"
                   "- 胜率 ~40% 但盈亏比 3:1+, 长期正期望;\n"
                   "- 核心: 严格止损 + 让利润奔跑;\n"
                   "- 缺点: 震荡市来回打脸 (需要大级别过滤)。",
        "books": ["《海龟交易法则》— 柯蒂斯·费思 (Way of the Turtle)"],
        "urls": ["https://www.investopedia.com/terms/t/turtletrading.asp"],
    },
    "缠论": {
        "emoji": "🌀",
        "definition": "缠论 = 博客主「缠中说禅」(2006-2008) 发表的完整走势分析体系,"
                      "从底层到上层:\n"
                      "  1. 包含处理 → 2. 分型 → 3. 笔 → 4. 中枢 [ZG,ZD] →\n"
                      "  5. 背驰 (价格新高/低但 MACD 动能衰减) →\n"
                      "  6. 6 类买卖点 (一买/二买/三买 + 一卖/二卖/三卖)",
        "meaning": "缠论 = 目前 A 股最完整的结构化分析体系:\n"
                   "- 一买/一卖 = 趋势背驰后的反转点 (风险最低);\n"
                   "- 三买 = 中枢上方回踩不进中枢 (强势中继); 三卖反之;\n"
                   "- 中枢 = 多空博弈区, 价格离开中枢即为趋势启动。",
        "books": ["《缠论》原博客 108 课 — 缠中说禅 (免费可查)",
                  "《缠论解析》— 白云", "《缠论图解》— 先锋"],
        "urls": ["https://baike.baidu.com/item/缠论"],
    },
    "艾略特波浪": {
        "emoji": "🌊",
        "definition": "艾略特波浪 = 拉尔夫·艾略特 (1930s):\n"
                      "- 完整周期 = 上升 5 浪 (1-2-3-4-5) + 调整 3 浪 (A-B-C);\n"
                      "- 主升浪 (3 浪) 不能是最短;\n"
                      "- 2 浪不跌破 1 浪起点, 4 浪不进入 1 浪区间;\n"
                      "- 斐波那契关系: 回撤 0.382/0.5/0.618, 扩展 1.618/2.618。",
        "meaning": "波浪 = 预测大级别周期位置:\n"
                   "- 识别当前处于第几浪, 决定战略方向;\n"
                   "- 5 浪常伴随 MACD 顶背驰 (见顶信号);\n"
                   "- C 浪通常等于 A 浪跌幅或 1.618 倍;\n"
                   "- 主观成分大, 建议结合缠论/MACD 验证。",
        "books": ["《波浪原理》— 拉尔夫·艾略特 (原著)",
                  "《艾略特波浪理论》— 普莱切特 (最权威解读)"],
        "urls": ["https://www.investopedia.com/terms/e/elliottwavetheory.asp"],
    },
    "江恩理论": {
        "emoji": "📐",
        "definition": "江恩 (W.D. Gann, 1878-1955): 用数学几何研究价格时间关系:\n"
                      "- 角度线: 1×1 (45°平衡线), 2×1 (26.25°下跌支撑), 1×2 (63.75°上涨阻力);\n"
                      "- 时间周期: 7/30/360 天及其等分 (45/90/180/270);\n"
                      "- 价格分割: 1/8/1/4/1/3/3/8/1/2/5/8/2/3/3/4/7/8。",
        "meaning": "江恩 = 时间与价格对称分析:\n"
                   "- 45°线是最重要的趋势线;\n"
                   "- 价格回撤常落在 1/2/1/3/2/3 位置;\n"
                   "- 部分内容带神秘主义色彩, 实证效果有争议。",
        "books": ["《江恩华尔街 45 年》— 威廉·江恩"],
        "urls": ["https://www.investopedia.com/terms/g/gannline.asp"],
    },
    "威科夫吸筹派发": {
        "emoji": "📦",
        "definition": "威科夫 (Richard Wyckoff, 1873-1934): 观察主力行为:\n"
                      "- 吸筹区 (Accumulation): 低位横盘 + 下跌缩量上涨放量, Spring 弹簧底是最后一跌;\n"
                      "- 派发区 (Distribution): 高位震荡 + 上涨缩量下跌放量, UTAD 是最后一冲;",
        "meaning": "威科夫 = 量价关系经典:\n"
                   "- Spring = 最好买点, UTAD = 最好卖点;\n"
                   "- 配合 OBV/VWAP 使用效果更好。",
        "books": ["《威科夫操盘法》— 汤姆·塞茨", "《量价分析》— 安娜·库林"],
        "urls": ["https://www.investopedia.com/terms/w/wyckoffmethod.asp"],
    },
    "生命周期5阶段": {
        "emoji": "📅",
        "definition": "股票生命周期 = 5 阶段:\n"
                      "  1. 吸筹 (Accumulation) — 低位横盘, OBV 上行股价不动\n"
                      "  2. 整理 (Consolidation) — 小幅上涨后再横盘, 洗盘\n"
                      "  3. 拉升 (Breakout / Markup) — 放量突破, 主升浪\n"
                      "  4. 派发 (Distribution) — 高位震荡, 量价背离\n"
                      "  5. 下跌 (Decline / Markdown) — 均线空头排列",
        "meaning": "生命周期 = 战略定仓位:\n"
                   "- 吸筹 = 左侧轻仓, 拉升 = 右侧满仓, 派发 = 减仓, 下跌 = 空仓;\n"
                   "- 是缠论中枢+MACD+量价的综合框架。",
        "books": ["《股票大作手回忆录》— 杰西·利弗莫尔 (思想源头)"],
        "urls": [],
    },
    "PE/PB/PEG": {
        "emoji": "📊",
        "definition": "三大经典估值:\n"
                      "- PE = 市值/净利润 (TTM, 静态), 动态 PE 用预测净利润;\n"
                      "- PB = 市值/净资产 (银行/周期股更适用);\n"
                      "- PEG = PE/净利润增长率(%), 理想值 = 1。",
        "meaning": "PE/PB/PEG = 判断贵贱:\n"
                   "- PE 分位数 <20% = 便宜, >80% = 贵;\n"
                   "- PEG <1 被低估, >2 被高估;\n"
                   "- 但高成长公司 PE 可以很高 (不能只看 PE)。",
        "books": ["《聪明的投资者》— 本杰明·格雷厄姆", "《估值的艺术》— 尼古拉斯·斯密德林"],
        "urls": ["https://www.investopedia.com/terms/p/pe.asp"],
    },
    "杜邦ROE拆解": {
        "emoji": "🔬",
        "definition": "杜邦 = 把 ROE 拆解为:\n"
                      "  ROE = 净利率 × 资产周转率 × 权益乘数\n"
                      "核心: 找出 ROE 高的来源 — 是赚钱能力? 运营效率? 还是杠杆?",
        "meaning": "杜邦 = 拆解 ROE 质量:\n"
                   "- 净利率高 = 品牌/定价权 (消费/医药);\n"
                   "- 周转率高 = 运营效率 (零售);\n"
                   "- 乘数高 = 高杠杆 (警惕, 周期见顶后崩塌);\n"
                   "- 健康 ROE = 净利率+周转率双高, 乘数适中。",
        "books": ["《财务报表分析与股票估值》— 郭永清"],
        "urls": ["https://www.investopedia.com/terms/d/dupontanalysis.asp"],
    },
    "段永平6维": {
        "emoji": "👤",
        "definition": "段永平 (步步高/OPPO/网易/苹果投资人) 的选股六维:\n"
                      "  好行业 → 好公司 → 好价格 → 好产品 → 好机制 → 好治理",
        "meaning": "段永平 = A 股/港股最接地气的价值投资框架:\n"
                   "- 行业是天花板, 管理层是根本 (一票否决);\n"
                   "- 好价格是安全边际, 再好公司买贵了也亏钱;\n"
                   "- 产品/机制/治理 = 护城河的具体体现。",
        "books": ["《段永平投资问答录》— 雪球整理", "《价值投资实战手册》— 唐朝"],
        "urls": ["https://xueqiu.com/tag/zqyw"],
    },
    "北向资金": {
        "emoji": "🌐",
        "definition": "北向资金 = 通过沪股通 + 深股通从香港买入 A 股的外资。"
                      "每日: 净流入额 (亿元) + 十大成交股, 累计持仓超 1.5 万亿。",
        "meaning": "北向 = 聪明钱信号:\n"
                   "- 持续净流入 = 外资看好 A 股;\n"
                   "- 大幅净流出 = 短期风险 (通常比内资先知先觉);\n"
                   "- 外资集中买入的行业/个股常有超额收益。",
        "books": [],
        "urls": ["https://www.wallstreetcn.com/northmoney"],
    },
    "龙虎榜": {
        "emoji": "🐉",
        "definition": "龙虎榜 = 沪深交易所每日异动股买卖前五席位。"
                      "上榜条件: 涨跌幅 ±9% / 换手 ≥20% / 连续涨停。"
                      "席位: 机构专用 / 游资营业部 / 沪港通专用。",
        "meaning": "龙虎榜 = 捕捉短线强势股 + 机构动向:\n"
                   "- 机构净买入 = 中长线看好;\n"
                   "- 知名游资 (赵老哥/章盟主) = 短线信号;\n"
                   "- 欢乐海岸等一日游席位 = 次日大概率低开。",
        "books": [],
        "urls": ["https://data.eastmoney.com/stock/lhb.html"],
    },
    "融资融券": {
        "emoji": "📈",
        "definition": "融资融券 = 借钱买股 (融资) / 借券卖股 (融券)。"
                      "A 股融资余额超 1.5 万亿, 是重要的市场杠杆情绪指标。",
        "meaning": "融资余额 = 市场杠杆情绪:\n"
                   "- 持续上升 + 爆量 = 看多情绪到顶 (历史顶部特征);\n"
                   "- 持续下降 + 去杠杆 = 见底信号;\n"
                   "- 融资余额/流通市值 ≥4% 警惕。",
        "books": [],
        "urls": ["https://data.eastmoney.com/rzrq.html"],
    },
}


# ========= 点击按钮弹出方法说明窗 =========
def _show_method_knowledge(parent_win: tk.Tk, method_name: str):
    """弹出 Toplevel, 展示某个方法的完整说明 + 可点击 URL"""
    # 精确匹配 → 去掉括号内容后匹配 (处理 "缠论(简化)" 这种变体)
    info = KNOWLEDGE.get(method_name)
    if not info:
        _base = re.sub(r"[（(].*?[)）]", "", method_name).strip()
        info = KNOWLEDGE.get(_base)
    if not info: return
    top = tk.Toplevel(parent_win)
    top.title(f"{info.get('emoji','❓')} {method_name} — 方法说明")
    top.geometry("620x560")
    top.configure(bg="#FFFDF5")
    top.attributes("-topmost", True)

    header = tk.Frame(top, bg="#FFFDF5"); header.pack(fill=tk.X, padx=14, pady=(12, 4))
    tk.Label(header, text=f"{info.get('emoji','')} {method_name}", bg="#FFFDF5",
             fg="#4527A0", font=("", 14, "bold")).pack(anchor="w")
    sep = tk.Frame(top, bg="#E8EAF6", height=1); sep.pack(fill=tk.X, padx=14)

    body_frame = tk.Frame(top, bg="#FFFDF5"); body_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)
    sb = ttk.Scrollbar(body_frame, orient=tk.VERTICAL)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    txt = tk.Text(body_frame, bg="#FFFDF5", fg="#333", font=("", 10), wrap=tk.WORD,
                  relief=tk.FLAT, yscrollcommand=sb.set, padx=4, pady=4)
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.configure(command=txt.yview)

    def _add_section(title, content, section_color="#4527A0"):
        txt.insert("end", f"\n{title}\n", "title")
        txt.insert("end", f"{content}\n", "body")

    _add_section("📖 定义", info.get("definition", ""), "#4527A0")
    _add_section("🎯 操作意义", info.get("meaning", ""), "#2E7D32")

    if info.get("books"):
        _add_section("📚 推荐书籍",
                     "\n".join(f"  • {b}" for b in info["books"]), "#6A1B9A")
    if info.get("urls"):
        txt.insert("end", "\n🌐 参考网站 (点击可打开):\n", "title")
        for u in info["urls"]:
            tag = f"url_{hash(u) % 1000000}"
            txt.insert("end", f"  🔗 {u}\n", tag)
            txt.tag_config(tag, foreground="#1565C0", underline=True)
            txt.tag_bind(tag, "<Button-1>", lambda _e, url=u: webbrowser.open(url))

    # 样式
    txt.tag_config("title", font=("", 11, "bold"), foreground="#4527A0", spacing3=4)
    txt.tag_config("body", font=("", 10), foreground="#333", lmargin1=8, lmargin2=8, spacing1=2)
    txt.configure(state=tk.NORMAL)  # 保持 NORMAL 以便 URL 可点击
    # 拦截按键防止误编辑
    for _ev in ("<Key>", "<BackSpace>", "<Delete>", "<Ctrl-a>", "<Ctrl-v>", "<Ctrl-x>"):
        txt.bind(_ev, lambda _e: "break")

    # 关闭按钮
    close_btn = tk.Button(top, text="关闭", command=top.destroy,
                          bg="#4527A0", fg="white", font=("", 10),
                          relief=tk.FLAT, padx=20, pady=4)
    close_btn.pack(pady=(0, 10))
    txt.see("1.0")


# ========= 数据获取 =========
def _fetch_kline_data(ts_code: str, days: int = 180) -> Optional[Dict]:
    import pandas as pd, numpy as np
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        if token:
            ts.set_token(token); pro = ts.pro_api()
            df = pro.daily(ts_code=ts_code, limit=days,
                           fields="ts_code,trade_date,open,high,low,close,vol,amount")
            if df is not None and len(df) >= 30:
                df = df.sort_values("trade_date").reset_index(drop=True)
                data = pd.DataFrame({
                    "日期": df["trade_date"], "开盘": df["open"].astype(float),
                    "收盘": df["close"].astype(float), "最高": df["high"].astype(float),
                    "最低": df["low"].astype(float),
                    "成交量": df["vol"].astype(float), "成交额": df["amount"].astype(float),
                })
                closes = data["收盘"].values.astype(float)
                ma_values = {}
                for ma_name, p in [("ma5",5),("ma10",10),("ma20",20),("ma60",60)]:
                    if len(closes) >= p:
                        ma_values[ma_name] = np.convolve(closes, np.ones(p)/p, mode="valid").tolist()
                return {"data": data, "ma_values": ma_values, "trade_dates": df["trade_date"].tolist()}
    except Exception as e: print(f"[K线] tushare 失败 {e}")
    return None


def _fetch_fundamentals(ts_code: str) -> Dict:
    import numpy as np
    fund = {}
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token: return fund
        ts.set_token(token); pro = ts.pro_api()
        db = pro.daily_basic(ts_code=ts_code, limit=1,
                             fields="turnover_rate,pe_ttm,pb,total_mv,circ_mv")
        if db is not None and len(db) > 0:
            r = db.iloc[0]
            for k in ["pe_ttm","pb","total_mv","circ_mv","turnover_rate"]:
                fund[k] = float(r[k]) if r.get(k) and not str(r.get(k)).startswith(".") else None
        fi = pro.fina_indicator(ts_code=ts_code, limit=2,
                                fields="roe,roe_dt,revenue_yoy,n_income_yoy,gross_margin")
        if fi is not None and len(fi) > 0:
            for k in ["roe","roe_dt","revenue_yoy","n_income_yoy","gross_margin"]:
                fund[k] = float(fi.iloc[0][k]) if fi.iloc[0].get(k) else None
    except Exception as e: print(f"[基本面] {e}")
    return fund


# ========= 名称 ↔ 代码 双向映射 =========
_NAME_CODE_CACHE_PATH = os.path.expanduser("~/.qclaw/stock_name_code.json")
_NAME_CODE_CACHE: Optional[Dict] = None  # {"ts_code->name": {...}, "name->ts_code": {...}, "ts": 0}

def _load_name_code_map(force=False) -> Dict:
    """从 tushare stock_basic 拉全量 5500 只, 本地 JSON 缓存 (TTL 7 天)"""
    global _NAME_CODE_CACHE
    import time
    if not force and _NAME_CODE_CACHE is not None and _NAME_CODE_CACHE.get("ts", 0) > time.time() - 7*86400:
        return _NAME_CODE_CACHE
    # 先读磁盘缓存
    if not force and os.path.exists(_NAME_CODE_CACHE_PATH):
        try:
            with open(_NAME_CODE_CACHE_PATH, "r") as f:
                _NAME_CODE_CACHE = json.load(f)
            if _NAME_CODE_CACHE.get("ts", 0) > time.time() - 7*86400 and _NAME_CODE_CACHE.get("nc"):
                return _NAME_CODE_CACHE
        except Exception: pass
    # tushare 拉
    nc: Dict[str, str] = {}  # ts_code -> name
    cn: Dict[str, str] = {}  # name -> ts_code
    try:
        import tushare as ts
        token = os.environ.get("TUSHARE_TOKEN", "")
        if token:
            ts.set_token(token); pro = ts.pro_api()
            df = pro.stock_basic(exchange="", list_status="L",
                                 fields="ts_code,symbol,name,area,industry,list_date")
            if df is not None and len(df) > 0:
                for _, r in df.iterrows():
                    tsc = str(r["ts_code"]); nm = str(r["name"])
                    nc[tsc] = nm; cn[nm] = tsc
                print(f"[名称映射] tushare stock_basic OK ({len(nc)} 只)")
    except Exception as e:
        print(f"[名称映射] tushare 失败: {e}")
    # akshare 兜底 (无 tushare token 或 限流时)
    if not nc:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
                for _, r in df.iterrows():
                    code6 = str(r.get("代码","")).strip()
                    nm = str(r.get("名称","")).strip()
                    if not code6 or not nm or not code6.isdigit(): continue
                    suffix = ".SH" if code6.startswith(("6","9","5")) else ".SZ" if code6.startswith(("3","0","4")) else ".BJ"
                    tsc = code6 + suffix
                    nc[tsc] = nm; cn[nm] = tsc
                print(f"[名称映射] akshare 兜底 OK ({len(nc)} 只)")
        except Exception as e:
            print(f"[名称映射] akshare 兜底也失败: {e}")
    _NAME_CODE_CACHE = {"nc": nc, "cn": cn, "ts": time.time()}
    # 写磁盘
    try:
        os.makedirs(os.path.dirname(_NAME_CODE_CACHE_PATH), exist_ok=True)
        with open(_NAME_CODE_CACHE_PATH, "w") as f:
            json.dump(_NAME_CODE_CACHE, f, ensure_ascii=False)
    except Exception: pass
    return _NAME_CODE_CACHE


def _resolve_code(input_str: str) -> Optional[str]:
    """把任意输入 (代码/中文名/带括号) → tushare ts_code (如 002300.SZ)"""
    if not input_str: return None
    s = input_str.strip()
    # ① 括号提取 "紫薇股份 (002300.SZ)" 或 "(002300.SZ)"
    m = re.search(r"\((\d{6}\.(?:SH|SZ|BJ))\)", s)
    if m: return m.group(1)
    # ② 去掉 sh/sz/bj 前缀
    s2 = re.sub(r"^(sh|sz|bj|SH|SZ|BJ)", "", s)
    # ③ 已有完整后缀
    if re.match(r"^\d{6}\.(SH|SZ|BJ)$", s2): return s2
    # ④ 纯 6 位数字
    if s2.isdigit() and len(s2) == 6:
        suffix = ".SH" if s2.startswith(("6","9","5")) else ".SZ" if s2.startswith(("3","0","4")) else ".BJ"
        return s2 + suffix
    # ⑤ 中文名 → 查映射
    if re.search(r"[\u4e00-\u9fa5]", s):
        mp = _load_name_code_map()
        cn_map = mp.get("cn", {})
        # 精确匹配
        if s in cn_map: return cn_map[s]
        # 模糊匹配 (包含)
        for nm, tsc in cn_map.items():
            if s in nm or nm in s: return tsc
    return None


def _fetch_stock_name(ts_code: str) -> str:
    """ts_code → 中文名, 失败返回原代码"""
    mp = _load_name_code_map()
    nc_map = mp.get("nc", {})
    return nc_map.get(ts_code, ts_code)


def _detect_local_extremes(arr, order=5):
    """找 arr 里的局部极值, order=窗口大小"""
    import numpy as np
    peaks, troughs = [], []
    for i in range(order, len(arr)-order):
        if all(arr[i] >= arr[i-j] for j in range(1, order+1)) and \
           all(arr[i] >= arr[i+j] for j in range(1, order+1)):
            peaks.append((i, float(arr[i])))
        if all(arr[i] <= arr[i-j] for j in range(1, order+1)) and \
           all(arr[i] <= arr[i+j] for j in range(1, order+1)):
            troughs.append((i, float(arr[i])))
    return peaks, troughs


# ========= 形态检测 (简化版) =========
def _detect_cup_handle(highs, lows, closes) -> Dict:
    """杯形法: N日高点回撤 25%-50% 后右侧回到高点附近, 低点在中间"""
    import numpy as np
    result = {"found": False, "desc": "—", "confidence": 0}
    if len(closes) < 60: return result
    n = len(closes); H = highs; L = lows
    # 找最近 120 天内的最高点
    win = min(n, 120); peak_i = int(np.argmax(H[-win:])) + (n-win); peak_h = H[peak_i]
    # 回撤 25%-50% 找杯底
    left = L[max(0, peak_i-30):peak_i]
    if len(left) < 10: return result
    trough_i_local = int(np.argmin(left))
    trough_i = max(0, peak_i-30) + trough_i_local; trough_l = L[trough_i]
    cup_depth = (peak_h - trough_l) / peak_h
    if not (0.20 <= cup_depth <= 0.55): return result
    # 杯底要在区间中间 (30%-70%)
    pos_ratio = trough_i / peak_i if peak_i > 0 else 0
    if not (0.25 <= pos_ratio <= 0.85): return result
    # 右侧杯点: 杯底之后应有反弹接近 peak_h
    right = H[trough_i:n]
    if len(right) < 5: return result
    right_max = np.max(right); right_pct = right_max / peak_h
    if right_pct >= 0.85:
        result["found"] = True; result["confidence"] = int(min(95, 60 + cup_depth*60))
        result["desc"] = f"✅ 杯形法成立! 杯幅{cup_depth*100:.0f}% 右高{right_pct*100:.0f}% 位置{pos_ratio*100:.0f}%"
    return result


def _detect_head_shoulders(highs) -> Dict:
    """头肩顶/底: 3 个递减(顶)或递增(底)高点"""
    import numpy as np
    result = {"found": False, "desc": "—", "pattern": ""}
    peaks, troughs = _detect_local_extremes(highs, order=5)
    if len(peaks) < 3: return result
    # 找最近 3 个峰
    p = peaks[-3:]
    h1, h2, h3 = p[0][1], p[1][1], p[2][1]
    # 头肩顶: h1≈h3, h2>h1, h2>h3
    neckline = min((p[0][1]+p[2][1])/2, *[t[1] for t in troughs if p[0][0] < t[0] < p[2][0]]) if troughs else (p[0][1]+p[2][1])/2
    if abs(h1-h3)/h2 < 0.08 and h2 > h1*1.03 and h2 > h3*1.03:
        result["found"] = True; result["pattern"] = "头肩顶"
        result["desc"] = f"⚠️ 头肩顶! 左肩{h1:.1f} 头{h2:.1f} 右肩{h3:.1f} 颈线{neckline:.1f} 破位看{h2-(h2-neckline):.1f}"
    return result


def _detect_double_top(highs, lows) -> Dict:
    """双重顶(M) / 双重底(W)"""
    import numpy as np
    result = {"found": False, "desc": "—", "pattern": ""}
    peaks, troughs = _detect_local_extremes(highs, order=5)
    troughs_l, _ = _detect_local_extremes(lows, order=5)
    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        if abs(p1[1]-p2[1])/p1[1] < 0.05 and p2[0] - p1[0] >= 15:
            # 颈线 (中间低点)
            mid_troughs = [t for t in troughs_l if p1[0] < t[0] < p2[0]]
            neck = mid_troughs[0][1] if mid_troughs else min(p1[1], p2[1])*0.97
            result["found"] = True; result["pattern"] = "双重顶(M)"
            result["desc"] = f"⚠️ 双重顶! 左{p1[1]:.1f} 右{p2[1]:.1f} 颈线{neck:.1f} 破位目标{neck-(p1[1]-neck):.1f}"
    if len(troughs_l) >= 2:
        t1, t2 = troughs_l[-2], troughs_l[-1]
        if abs(t1[1]-t2[1])/t1[1] < 0.05 and t2[0] - t1[0] >= 15:
            mid_peaks = [p for p in peaks if t1[0] < p[0] < t2[0]]
            neck = mid_peaks[0][1] if mid_peaks else max(t1[1], t2[1])*1.03
            result["found"] = True; result["pattern"] = "双重底(W)"
            result["desc"] = f"✅ 双重底(W)! 左{t1[1]:.1f} 右{t2[1]:.1f} 颈线{neck:.1f} 突破目标{neck+(neck-t1[1]):.1f}"
    return result


def _detect_triangle(highs, lows) -> Dict:
    """三角形 (收窄高低点)"""
    import numpy as np
    result = {"found": False, "desc": "—", "pattern": ""}
    peaks, troughs = _detect_local_extremes(highs, order=6)
    _, troughs_l = _detect_local_extremes(lows, order=6)
    if len(peaks) >= 2 and len(troughs_l) >= 2:
        p1, p2 = peaks[-2], peaks[-1]; t1, t2 = troughs_l[-2], troughs_l[-1]
        hi_contract = p2[1] < p1[1] - 0.01 * p1[1]
        lo_contract = t2[1] > t1[1] + 0.01 * t1[1]
        width1 = p1[1] - t1[1]; width2 = p2[1] - t2[1]
        if hi_contract and lo_contract and width2 < width1*0.9:
            result["found"] = True; result["pattern"] = "收敛三角形"
            result["desc"] = f"🔺 收敛三角形! 幅度收窄{width1:.1f}→{width2:.1f} 方向待突破 (突破目标≈幅度)"
        elif not hi_contract and not lo_contract:
            result["found"] = True; result["pattern"] = "扩张三角形"
            result["desc"] = f"🔻 扩张三角形! 幅度变大{width1:.1f}→{width2:.1f} 波动加剧"
    return result


def _detect_ema_trend(closes) -> Dict:
    """均线系统+MACD趋势"""
    import numpy as np
    result = {"ma_trend": "", "macd": "", "trend_score": 0}
    def ema(a, w):
        r = np.empty_like(a); r[0]=a[0]; k=2/(w+1)
        for i in range(1,len(a)): r[i]=a[i]*k+r[i-1]*(1-k); return r
    if len(closes) < 30: return result
    e5 = ema(closes.astype(float), 5); e20 = ema(closes.astype(float), 20); e60 = ema(closes.astype(float), 60)
    c = closes[-1]; e5_l, e20_l, e60_l = e5[-1], e20[-1], e60[-1]
    if c > e5_l > e20_l > e60_l:
        result["ma_trend"] = "🟢 多头排列 (主升浪); result['trend_score'] = 80"
    elif c < e5_l < e20_l < e60_l:
        result["ma_trend"] = "🔴 空头排列 (主跌浪); result['trend_score'] = 10"
    else:
        result["ma_trend"] = "🟡 均线交叉震荡"; result["trend_score"] = 40
    # MACD
    dif = ema(closes.astype(float),12) - ema(closes.astype(float),26)
    dea = ema(dif,9); macd = (dif-dea)*2
    if dif[-1] > dea[-1] and dif[-2] <= dea[-2]: result["macd"] = "🟢 MACD零轴下金叉(买入信号)"
    elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]: result["macd"] = "🔴 MACD零轴上死叉(卖出信号)"
    elif dif[-1] > dea[-1] and dif[-1] > 0: result["macd"] = "🟢 MACD零轴上多头"
    elif dif[-1] < dea[-1] and dif[-1] < 0: result["macd"] = "🔴 MACD零轴下空头"
    else: result["macd"] = "🟡 MACD中性"
    return result


def _detect_boll(closes, highs, lows) -> Dict:
    """布林带状态"""
    import numpy as np
    result = {"status": "", "width": 0, "desc": ""}
    if len(closes) < 20: return result
    c20 = np.convolve(closes.astype(float), np.ones(20)/20, mode="valid")
    s20 = np.array([np.std(closes[i:i+20]) for i in range(len(closes)-19)])
    u = c20 + 2*s20; d = c20 - 2*s20
    c_last = closes[-1]; u_last = u[-1]; d_last = d[-1]; mid_last = c20[-1]
    boll_w = (u_last - d_last) / mid_last
    result["width"] = float(boll_w*100)
    if c_last >= u_last: result["status"] = "🔴 触及上轨 (超买/突破)"; result["desc"] = f"收{c_last:.1f} 上轨{u_last:.1f}"
    elif c_last <= d_last: result["status"] = "🟢 触及下轨 (超卖/支撑)"; result["desc"] = f"收{c_last:.1f} 下轨{d_last:.1f}"
    elif c_last > mid_last: result["status"] = "🟢 中轨上方 (多头)"; result["desc"] = f"收{c_last:.1f} 中轨{mid_last:.1f}"
    else: result["status"] = "🔴 中轨下方 (空头)"; result["desc"] = f"收{c_last:.1f} 中轨{mid_last:.1f}"
    if boll_w < 0.04:
        result["width_desc"] = "⚠️ 带宽收窄 (变盘在即)"
    elif boll_w > 0.12:
        result["width_desc"] = "⚠️ 带宽过宽 (可能见顶)"
    else:
        result["width_desc"] = "带宽正常"
    return result


def _detect_rsi_kdj(closes, highs, lows) -> Dict:
    """RSI14 + KDJ"""
    import numpy as np
    result = {"rsi": 50.0, "rsi_level": "", "kdj_k": 50.0, "kdj_d": 50.0, "kdj_level": ""}
    if len(closes) < 20: return result
    # RSI 14
    d = np.diff(closes.astype(float))
    g = np.where(d > 0, d, 0); l = np.where(d < 0, -d, 0)
    ag = np.mean(g[-14:]); al = np.mean(l[-14:])
    rs = ag / max(al, 0.001); result["rsi"] = float(100 - 100/(1+rs))
    r = result["rsi"]
    if r > 70: result["rsi_level"] = "🔴 RSI超买(>70) 谨慎追高"
    elif r < 30: result["rsi_level"] = "🟢 RSI超卖(<30) 可能反弹"
    else: result["rsi_level"] = f"🟡 RSI中性 ({r:.0f})"
    # KDJ 9
    kd_k = 50.0; kd_d = 50.0
    for i in range(9, len(closes)):
        rv = max(highs[i-8:i+1]) - min(lows[i-8:i+1])
        rsv = (closes[i] - min(lows[i-8:i+1])) / max(rv,0.001)*100
        kd_k = kd_k*2/3 + rsv*1/3; kd_d = kd_d*2/3 + kd_k*1/3
    result["kdj_k"] = float(kd_k); result["kdj_d"] = float(kd_d)
    if kd_k > 80: result["kdj_level"] = "🔴 KDJ高位 (>80) 注意死叉"
    elif kd_k < 20: result["kdj_level"] = "🟢 KDJ低位 (<20) 关注金叉"
    elif kd_k > kd_d and kd_k < 80: result["kdj_level"] = "🟢 KDJ金叉形成"
    elif kd_k < kd_d and kd_k > 20: result["kdj_level"] = "🔴 KDJ死叉形成"
    else: result["kdj_level"] = f"🟡 KDJ中性 K={kd_k:.0f} D={kd_d:.0f}"
    return result


def _detect_bollinger_alt(closes) -> Dict:
    """筹码分布简化: 用 VOL * (close * pct_range) 近似"""
    import numpy as np
    if len(closes) < 60: return {"peak": 0, "desc": "数据不足"}
    closes = closes.astype(float)
    last60 = closes[-60:]
    median = np.median(last60); mean = np.mean(last60)
    std = np.std(last60)
    cv = std/mean
    if cv < 0.04: result = "🔒 高度集中 (低波动), 筹码稳定"
    elif cv < 0.08: result = "🟡 中度集中"
    else: result = "⚠️ 筹码分散 (高波动)"
    return {"mean": float(mean), "median": float(median), "cv": float(cv), "desc": result}


def _detect_turtle(closes, highs, lows) -> Dict:
    """海龟交易法: 唐奇安通道"""
    import numpy as np
    if len(highs) < 22: return {"desc": "数据不足"}
    h22 = np.max(highs[-22:]); l22 = np.min(lows[-22:])
    h55 = np.max(highs[-55:]) if len(highs) >= 55 else h22
    c = closes[-1]
    atr = np.mean(highs[-14:]-lows[-14:])
    if c >= h22: status = f"🟢 突破20日高{h22:.1f} 多头信号"
    elif c <= l22: status = f"🔴 跌破20日低{l22:.1f} 空头信号"
    else: status = f"🟡 通道内 [{l22:.1f}, {h22:.1f}]"
    return {"h22": float(h22), "l22": float(l22), "atr": float(atr), "desc": status}


def _detect_lifecycle(closes, vols) -> Tuple[str, str]:
    """复用 stock_compare._detect_lifecycle"""
    try:
        from stock_compare import _detect_lifecycle as _lc
        return _lc(closes, vols)
    except Exception:
        import numpy as np
        closes = closes.astype(float); n = len(closes)
        if n < 60: return ("unknown", "—")
        h = np.max(closes[-60:]); l = np.min(closes[-60:])
        cur = closes[-1]; pos = (cur - l) / max(h-l, 0.001)
        chg_20 = (cur - closes[-20]) / closes[-20] if n>=20 else 0
        if pos < 0.3 and chg_20 < 0.05: return ("accumulation", "💎吸筹低位30% 缩量")
        elif pos < 0.55: return ("consolidation", "🪨整理中位 方向不明")
        elif chg_20 > 0.15 and pos > 0.55: return ("breakout", "🚀拉升阶段+15% 爆量")
        elif chg_20 < -0.15 and pos < 0.5: return ("decline", "📉下跌阶段 -15%")
        elif pos > 0.8 and chg_20 < 0: return ("distribution", "📦出货高位回落")
        return ("unknown", "—")


def _calc_dupont(fund: Dict) -> Dict:
    """杜邦 ROE 拆解简化版"""
    result = {"roe": None, "components": []}
    roe = fund.get("roe") or fund.get("roe_dt")
    if roe is None: return result
    result["roe"] = float(roe)
    pb = fund.get("pb") or 1.0
    pe = fund.get("pe_ttm") or 15.0
    gross = fund.get("gross_margin") or 25.0
    # 简化杜邦 5 分解 (实际用 tushare fina_indicator 更准, 这里是占位估算)
    roe_pct = float(roe)
    result["components"] = [
        ("🧮 ROE", f"{roe_pct:.1f}%", "#1565C0"),
        ("💰 毛利率", f"{gross:.1f}%", "#333"),
        ("📐 PB估值", f"{pb:.2f}", "#333"),
        ("📈 PE估值", f"{pe:.1f}", "#333"),
    ]
    if roe_pct > 15: result["rating"] = "⭐⭐⭐⭐⭐ 优秀ROE"
    elif roe_pct > 10: result["rating"] = "⭐⭐⭐⭐ 良好"
    elif roe_pct > 5: result["rating"] = "⭐⭐⭐ 一般"
    else: result["rating"] = "⚠️ ROE偏低"
    return result


# ========= UI 弹窗 =========
def show_stock_analysis_dialog(parent_win=None, call_ai_fn=None, auto_code=None, auto_name=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import webbrowser, numpy as np

    win = tk.Toplevel(parent_win) if parent_win else tk.Tk()
    win.title("📊 单票深度分析 — 六大流派 25+ 方法 + K线辅助线"); win.geometry("1420x900"); win.minsize(1180, 780)
    win.configure(bg="#ECEFF1")

    # ===== 顶栏 =====
    top = tk.Frame(win, bg="#283593"); top.pack(fill=tk.X)
    tk.Label(top, text="📊 股票分析 (六大流派主流方法)", bg="#283593", fg="#FFD54F",
             font=("", 13, "bold")).pack(side=tk.LEFT, padx=14, pady=9)
    tk.Label(top, text="股票:", bg="#283593", fg="white", font=("", 10)).pack(side=tk.LEFT)
    stock_var = tk.StringVar()
    combo = ttk.Combobox(top, textvariable=stock_var, width=18, state="normal")
    combo.pack(side=tk.LEFT, padx=6)
    ttk.Button(top, text="🔍 分析", command=lambda: None).pack(side=tk.LEFT, padx=4)
    status_var = tk.StringVar(value="⏳ 加载候选列表...")
    tk.Label(top, textvariable=status_var, bg="#283593", fg="#90A4AE",
             font=("", 8)).pack(side=tk.RIGHT, padx=14)

    # ===== PanedWindow 水平 =====
    pw = tk.PanedWindow(win, orient=tk.HORIZONTAL, bg="#ECEFF1", sashwidth=6)
    pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ===== 左侧: Notebook 6 Tab =====
    left_f = tk.Frame(pw, bg="#ECEFF1")
    pw.add(left_f, minsize=420)
    nb = ttk.Notebook(left_f); nb.pack(fill=tk.BOTH, expand=True)
    tabs = {
        "📈 形态": tk.Frame(nb, bg="#FFFFFF"),
        "📊 指标": tk.Frame(nb, bg="#FFFFFF"),
        "🧱 结构": tk.Frame(nb, bg="#FFFFFF"),
        "💰 估值": tk.Frame(nb, bg="#FFFFFF"),
        "💴 资金": tk.Frame(nb, bg="#FFFFFF"),
        "🤖 AI建议": tk.Frame(nb, bg="#FFFDE7"),
    }
    for t, f in tabs.items():
        f.pack_propagate(False)
        nb.add(f, text=t)

    # ===== 右侧: K 线 =====
    right_f = tk.Frame(pw, bg="#FAFAFA")
    pw.add(right_f, minsize=600)
    rt = tk.Frame(right_f, bg="#FAFAFA"); rt.pack(fill=tk.X, pady=(0,4))
    ttk.Label(rt, text="K线图 + 指标 + 买卖点 (hover 查看胜率+凯利公式)",
              font=("", 11, "bold"), background="#FAFAFA", foreground="#1565C0").pack(side=tk.LEFT, padx=6)
    ivars = {}
    for code, lbl in [("VOL","VOL"),("MACD","MACD"),("WR2","WR2"),("KDJ","KDJ"),("BOLL","BOLL")]:
        ivars[code] = tk.BooleanVar(value=code in ("VOL","MACD","KDJ"))
        ttk.Checkbutton(rt, text=lbl, variable=ivars[code]).pack(side=tk.LEFT, padx=3)
    bs_var = tk.BooleanVar(value=True); bt_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(rt, text="🛒买卖点", variable=bs_var).pack(side=tk.LEFT, padx=(10,3))
    ttk.Checkbutton(rt, text="💡胜率+凯利", variable=bt_var).pack(side=tk.LEFT, padx=3)
    # ===== 辅助线 =====
    _aux_frame = tk.Frame(rt, bg=rt.cget("background")); _aux_frame.pack(side=tk.LEFT, padx=(12,0))
    aux_vars = {}
    for _k, _lbl, _def in [("sr","支撑阻力",True),("gann","江恩",False),
                            ("fib","斐波那契",True),("gold","黄金分割",True),("zs","缠论中枢",False)]:
        aux_vars[_k] = tk.BooleanVar(value=_def)
        ttk.Checkbutton(_aux_frame, text=_lbl, variable=aux_vars[_k]).pack(side=tk.LEFT, padx=2)
    chart_inner = tk.Frame(right_f, bg="#FAFAFA"); chart_inner.pack(fill=tk.BOTH, expand=True, pady=4)

    # ===== 状态缓存 =====
    _current_kline = None; _current_fund: Dict = {}
    _hover_cache: Dict = {"bs": {}, "bt": {}}
    _current_name = ""

    # ===== 方法定义: (title, emoji, 一句话说明, get_result_fn(kline_data, fund) -> list[str] or dict) =====
    METHODS = {
        "📈 形态": [
            ("杯形法", "🏺", "杯底右侧放量突破=吸筹完毕启动", lambda kd,fd: _fmt_cup(kd)),
            ("头肩顶/底", "👤", "左肩-头-右肩递减=见顶信号", lambda kd,fd: _fmt_hs(kd)),
            ("双重顶/底", "M", "两个等高峰破颈线=目标幅度", lambda kd,fd: _fmt_dt(kd)),
            ("三角形", "🔺", "收窄幅度=方向待突破", lambda kd,fd: _fmt_tri(kd)),
            ("旗形/楔形", "🚩", "急涨后斜向整理=中继整理", lambda kd,fd: _fmt_flag(kd)),
            ("酒田蜡烛图", "🕯️", "锤子/吞没/十字星等K线组合", lambda kd,fd: _fmt_sakata(kd)),
        ],
        "📊 指标": [
            ("均线系统/MACD", "📈", "多头排列=主升浪 空头=主跌浪", lambda kd,fd: _fmt_ema(kd)),
            ("BOLL布林带", "📏", "触及上轨=超买 下轨=超卖 收窄=变盘", lambda kd,fd: _fmt_boll(kd)),
            ("RSI/KDJ/WR", "🎯", "70超买 30超卖 金叉/死叉", lambda kd,fd: _fmt_rsi(kd)),
            ("筹码分布", "🪙", "低波动=高度集中 高波动=分散", lambda kd,fd: _fmt_chip(kd)),
            ("海龟通道", "🐢", "20日高低突破+ATR 分批进", lambda kd,fd: _fmt_turtle(kd)),
        ],
        "🧱 结构": [
            ("缠论(简化)", "🌀", "分型→笔→中枢→背驰 (简化版)", lambda kd,fd: _fmt_chan(kd)),
            ("艾略特波浪", "🌊", "主升1-5浪 / 调整A-B-C", lambda kd,fd: _fmt_wave(kd)),
            ("江恩理论", "📐", "重要高低位预测 (简化)", lambda kd,fd: _fmt_gan(kd)),
            ("威科夫吸筹派发", "📦", "吸筹→派发→出货 量价关系", lambda kd,fd: _fmt_wyckoff(kd)),
            ("生命周期5阶段", "📅", "吸筹/整理/拉升/出货/下跌", lambda kd,fd: _fmt_lc(kd)),
        ],
        "💰 估值": [
            ("PE/PB/PEG", "📊", "估值分位判断贵贱", lambda kd,fd: _fmt_pe(fd)),
            ("杜邦ROE拆解", "🔬", "ROE5分解 (简化)", lambda kd,fd: _fmt_dupont(fd)),
            ("段永平6维", "👤", "好行业好公司好价格好管理层…", lambda kd,fd: _fmt_duan(fd, kd)),
            ("DCF简化", "💵", "两阶段自由现金流 (占位)", lambda kd,fd: _fmt_dcf(fd, kd)),
        ],
        "💴 资金": [
            ("北向资金", "🌐", "沪股通/深股通净流入", lambda kd,fd: _fmt_north()),
            ("龙虎榜", "🐉", "近90天上榜次数+机构席位", lambda kd,fd: _fmt_lhb()),
            ("融资融券", "📈", "融资余额变化趋势", lambda kd,fd: _fmt_margin()),
            ("股东人数", "👥", "人数减少=筹码集中", lambda kd,fd: _fmt_holders()),
            ("换手率", "🔄", "低换手吸筹 高换手出货", lambda kd,fd: _fmt_turnover(fd, kd)),
        ],
    }

    # ========= 形态方法 getter =========
    def _get_closes(kd):
        if not kd: return np.array([])
        return kd["data"]["收盘"].values.astype(float)
    def _get_ohlcv(kd):
        if not kd: return None
        d = kd["data"]
        return d["开盘"].values.astype(float), d["收盘"].values.astype(float), d["最高"].values.astype(float), d["最低"].values.astype(float), d["成交量"].values.astype(float)

    def _fmt_cup(kd):
        o, c, h, l, v = _get_ohlcv(kd) or (None,None,None,None,None)
        if h is None: return ["⚠️ 请先分析股票"]
        r = _detect_cup_handle(h, l, c)
        return [r["desc"], f"置信度: {r['confidence']}/100"] if r["found"] else [r["desc"], "建议: 杯形法是中长线强形态, 需右侧放量突破"]

    def _fmt_hs(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if h is None: return ["⚠️ 请先分析股票"]
        r = _detect_head_shoulders(h)
        return [r["desc"]] if r["found"] else ["未检测到头肩形态", "⚠️ 但近期走势需警惕"]

    def _fmt_dt(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if h is None: return ["⚠️ 请先分析股票"]
        r = _detect_double_top(h, l)
        return [r["desc"]] if r["found"] else ["未检测到双M/W"]

    def _fmt_tri(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if h is None: return ["⚠️ 请先分析股票"]
        r = _detect_triangle(h, l)
        return [r["desc"]] if r["found"] else ["未检测到明显三角形"]

    def _fmt_flag(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if h is None: return ["⚠️ 请先分析股票"]
        # 简化: 急涨(10日>15%)后连续横盘(7日振幅<6%)
        n = len(c)
        if n >= 30:
            chg10 = (c[-1]-c[-10])/c[-10]; amp7 = (h[-7:].max()-l[-7:].min())/c[-1]
            if chg10 > 0.12 and amp7 < 0.06: return ["🚩 可能是旗形 (急涨+窄幅整理)", "目标≈前高延伸前幅度"]
            if chg10 < -0.12 and amp7 < 0.06: return ["🚩 可能是熊市旗形 (急跌+整理)", "⚠️ 大概率续跌"]
        return ["未检测到旗形/楔形"]

    def _fmt_sakata(kd):
        o, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if o is None or len(c) < 3: return ["⚠️ 请先分析股票"]
        bars = []
        for i in range(-5, 0):
            body = c[i]-o[i]; hl = h[i]-l[i]
            upper = h[i]-max(o[i],c[i]); lower = min(o[i],c[i])-l[i]
            if lower > hl*0.5 and abs(body) < hl*0.3: bars.append(f"🕯️ 锤子线 (T-{-i})")
            elif upper > hl*0.5 and abs(body) < hl*0.3: bars.append(f"🕯️ 射击之星 (T-{-i})")
            elif abs(body) < hl*0.1 and hl > 0: bars.append(f"🕯️ 十字星 (T-{-i})")
        return bars if bars else ["近期蜡烛图无明显信号"]

    def _fmt_ema(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None: return ["⚠️ 请先分析股票"]
        r = _detect_ema_trend(c)
        return [r["ma_trend"], r["macd"], f"趋势评分 {r['trend_score']}/100"]

    def _fmt_boll(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None: return ["⚠️ 请先分析股票"]
        r = _detect_boll(c, h, l)
        return [r["status"], r["desc"], r["width_desc"], f"带宽 {r['width']:.1f}%"]

    def _fmt_rsi(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None: return ["⚠️ 请先分析股票"]
        r = _detect_rsi_kdj(c, h, l)
        return [r["rsi_level"], r["kdj_level"]]

    def _fmt_chip(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None: return ["⚠️ 请先分析股票"]
        r = _detect_bollinger_alt(c)
        return [r["desc"], f"变异系数 CV={r['cv']*100:.1f}%"]

    def _fmt_turtle(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if h is None: return ["⚠️ 请先分析股票"]
        r = _detect_turtle(c, h, l)
        return [r["desc"], f"20日最高 {r['h22']:.1f} ATR {r['atr']:.1f}"]

    def _fmt_chan(kd):
        _, c, h, l, _ = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None or len(c) < 60: return ["⚠️ 缠论需 60 日以上 K 线"]
        try:
            from ui.chanlun import analyze_chan, format_chan_report
            result = analyze_chan(None, h, l, c)
            return format_chan_report(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return [f"缠论分析出错: {e}"]

    def _fmt_wave(kd):
        closes = _get_closes(kd)
        if len(closes) < 60: return ["⚠️ 需60日K线"]
        try:
            from stock_compare import _detect_elliott_wave
            return [_detect_elliott_wave(closes)]
        except Exception as e: return [f"波浪分析: 简化版 ({e})"]

    def _fmt_gan(kd):
        closes = _get_closes(kd)
        if len(closes) < 60: return ["⚠️ 需60日K线"]
        h = np.max(closes[-60:]); l = np.min(closes[-60:]); cur = closes[-1]
        gann_targets = [l + (h-l)*r for r in [0, 0.125, 0.25, 0.333, 0.5, 0.667, 0.75, 0.875, 1.0]]
        near = min(gann_targets, key=lambda x: abs(x - cur))
        pct = (cur-near)/(h-l)*100 if h != l else 0
        return [f"📐 当前价 {cur:.1f} 接近江恩位 {near:.1f} ({pct:.0f}%)",
                f"60日高低 [{l:.1f}, {h:.1f}] 8分位参考",
                "⚠️ 江恩理论数学性强, 实战辅助参考"]

    def _fmt_wyckoff(kd):
        _, c, h, l, v = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None or len(c) < 60: return ["⚠️ 需60日K线"]
        h60 = np.max(h); l60 = np.min(l)
        pos = (c[-1]-l60)/(h60-l60)
        v_ratio = np.mean(v[-10:])/max(np.mean(v[-30:-10]), 1)
        if pos < 0.35 and v_ratio < 0.8: return ["🧱 威科夫吸筹阶段! 低位缩量", "主力在收集筹码 耐心等待突破"]
        elif pos > 0.7 and v_ratio > 1.2: return ["🧱 威科夫派发阶段! 高位放量", "⚠️ 主力在出货 警惕回调"]
        elif pos > 0.85: return ["🧱 派发末期/出货! 高位滞涨", "⚠️ 减仓为主"]
        return ["🧱 威科夫阶段不明朗, 等待特征出现"]

    def _fmt_lc(kd):
        _, c, h, l, v = _get_ohlcv(kd) or (None,None,None,None,None)
        if c is None: return ["⚠️ 请先分析股票"]
        lc_phase, lc_desc = _detect_lifecycle(c, v)
        return [lc_desc]

    def _fmt_pe(fd):
        if not fd: return ["⚠️ 请先分析股票"]
        pe = fd.get("pe_ttm"); pb = fd.get("pb"); mv = fd.get("total_mv")
        lines = []
        if pe:
            if pe < 15: lines.append(f"✅ PE {pe:.1f} (低估/合理)")
            elif pe < 30: lines.append(f"🟡 PE {pe:.1f} (中等)")
            elif pe < 50: lines.append(f"⚠️ PE {pe:.1f} (偏高)")
            else: lines.append(f"🔴 PE {pe:.1f} (高估/亏损)")
        if pb:
            if pb < 1.5: lines.append(f"✅ PB {pb:.2f} (低市净)")
            elif pb < 4: lines.append(f"🟡 PB {pb:.2f} (中等)")
            else: lines.append(f"⚠️ PB {pb:.2f} (高)")
        if mv: lines.append(f"💰 总市值 {mv/10000:.0f} 亿")
        return lines or ["⚠️ 估值数据不足, tushare熔断时需手动填 daily_basic"]

    def _fmt_dupont(fd):
        d = _calc_dupont(fd)
        if not d["roe"]: return ["⚠️ 无ROE数据"]
        return [f"💎 ROE = {d['roe']:.1f}%", d.get("rating",""), f"毛利率 = {fd.get('gross_margin', 0):.1f}%"] if d else ["ROE无数据"]

    def _fmt_duan(fd, kd):
        """段永平6维简化: 好行业/好公司/好价格/好管理层/好商业模式/好文化"""
        lines = ["👤 段永平 6 维评估 (简化)", "—"*20]
        rev = fd.get("revenue_yoy") or 0; profit = fd.get("n_income_yoy") or 0
        roe = fd.get("roe") or 0; pe = fd.get("pe_ttm") or 15
        gscore = 0
        gscore += 1 if rev > 5 else 0; gscore += 1 if profit > 5 else 0
        gscore += 1 if roe > 12 else 0; gscore += 1 if pe < 25 else 0
        gscore += 1 if roe > rev else 0  # ROE > 营收增速 = 护城河质量
        if gscore >= 4:
            lines.append(f"⭐⭐⭐⭐⭐ 好公司 (6维中 {gscore}/5 通过)")
        elif gscore >= 3:
            lines.append(f"⭐⭐⭐⭐ 不错 ({gscore}/5 通过)")
        elif gscore >= 2:
            lines.append(f"⚠️ 一般 ({gscore}/5 通过)")
        else:
            lines.append(f"🔴 不推荐 ({gscore}/5 通过)")
        return lines

    def _fmt_dcf(fd, kd):
        """DCF 简化占位 (需 WACC 和自由现金流, 用 tushare fina_cf 更准)"""
        pe = fd.get("pe_ttm") or 15
        roe = fd.get("roe") or 10
        # 简化 DCF 估值 = EPS * (ROE/g)  / (WACC-g)
        # 这里用 PE 分位做粗略估值
        if pe < 0: return ["⚠️ DCF需EPS/FCF数据, 暂无可计算"]
        lines = [f"💵 DCF 简化占位 (完整版需 WACC + FCF)"]
        lines.append(f"当前 PE = {pe:.1f} / ROE = {roe:.1f}%")
        if pe < 20: lines.append("💡 PE<20 + ROE>12% 组合在A股通常有安全边际")
        return lines

    def _fmt_north():
        try:
            import tushare as ts; ts.set_token(os.environ.get("TUSHARE_TOKEN",""))
            df = ts.pro_api().moneyflow_hsgt(last=5)
            if df is not None and len(df) > 0:
                last = df.iloc[0]
                sh = float(last.get("ggt_ss",0) or 0)/1e8; sz = float(last.get("ggt_sz",0) or 0)/1e8
                lines = [f"🌐 近5日北向: 沪股通{sh:+.1f}亿 深股通{sz:+.1f}亿"]
                if sh+sz > 50: lines.append("✅ 连续净流入 外资看好")
                elif sh+sz < -50: lines.append("⚠️ 连续净流出 外资撤离")
                else: lines.append("🟡 外资无明显方向")
                return lines
        except Exception as e: pass
        return ["⚠️ tushare 熔断或无权限, 无法拉北向资金"]

    def _fmt_lhb():
        try:
            import sqlite3, glob
            c6 = (stock_var.get().strip()).split(".")[0].replace("sh","").replace("sz","").replace("bj","")
            for root, _, files in os.walk(os.path.expanduser("~/Agent/stockyidong_project")):
                for f in files:
                    if f.endswith(".db") and "stock" in f.lower():
                        try:
                            conn = sqlite3.connect(os.path.join(root, f))
                            cur = conn.cursor()
                            cur.execute("SELECT COUNT(*) FROM lhb_records WHERE stock_code LIKE ?", (f"%{c6}%",))
                            cnt = cur.fetchone()[0]; conn.close()
                            if cnt > 0:
                                return [f"🐉 近90天上榜 {cnt} 次", "💡 频繁上榜 = 机构/游资活跃"]
                        except Exception: pass
        except Exception: pass
        return ["⚠️ SQLite lhb_records 空, 请先爬龙虎榜"]

    def _fmt_margin():
        try:
            import tushare as ts; ts.set_token(os.environ.get("TUSHARE_TOKEN",""))
            df = ts.pro_api().margin_detail(last=5)
            if df is not None and len(df) > 0: return ["📈 融资融券近5日数据已拿到", "⚠️ 暂未按个股过滤"]
        except Exception: pass
        return ["⚠️ 融资融券接口限流或无权限"]

    def _fmt_holders():
        try:
            import tushare as ts; ts.set_token(os.environ.get("TUSHARE_TOKEN",""))
            df = ts.pro_api().top10_holders(ts_code=_get_tsc())
            if df is not None and len(df) > 0:
                return [f"👥 十大股东已更新, 共{len(df)}条"]
        except Exception: pass
        return ["⚠️ tushare top10_holders 限流"]

    def _fmt_turnover(fd, kd):
        tr = fd.get("turnover_rate")
        _, c, h, l, v = _get_ohlcv(kd) or (None,None,None,None,None)
        lines = []
        if tr:
            if tr < 1: lines.append(f"🟢 换手率低 {tr:.1f}% 筹码稳定")
            elif tr < 3: lines.append(f"🟡 换手率正常 {tr:.1f}%")
            elif tr < 8: lines.append(f"⚠️ 换手率偏高 {tr:.1f}% 活跃")
            else: lines.append(f"🔴 换手率极高 {tr:.1f}% 可能出货")
        if v is not None and len(v) >= 20:
            v_ratio = np.mean(v[-5:])/max(np.mean(v[-20:-5]), 1)
            lines.append(f"量比(5/20) = {v_ratio:.2f} {'放量' if v_ratio>1.3 else '缩量' if v_ratio<0.7 else '正常'}")
        return lines or ["⚠️ 换手率数据不足"]

    def _get_tsc():
        code = stock_var.get().strip(); t6 = re.sub(r"^(sh|sz|bj|SH|SZ|BJ)", "", code)
        if "." in t6: return t6
        return t6 + (".SH" if t6.startswith(("6","9","5")) else ".SZ" if t6.startswith(("3","0","4")) else ".BJ")

    # ========= 渲染左侧 Tab =========
    def _build_tab(tab_name, method_list):
        # 清旧
        for w in tabs[tab_name].winfo_children(): w.destroy()
        inner = tk.Frame(tabs[tab_name], bg="#FFFFFF"); inner.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(inner, bg="#FFFFFF", highlightthickness=0); canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(inner, orient=tk.VERTICAL, command=canvas.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=sb.set)
        body = tk.Frame(canvas, bg="#FFFFFF"); canvas.create_window((0,0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        for title, emoji, desc, fn in method_list:
            lf = tk.LabelFrame(body, text=f"  {emoji} {title}  ", bg="#FFFFFF", fg="#4527A0",
                               font=("", 10, "bold"), relief=tk.GROOVE, bd=1)
            lf.pack(fill=tk.X, padx=6, pady=4)
            # [?] 方法说明按钮 — 右侧挂一个小按钮
            _kn_key = title if title in KNOWLEDGE else re.sub(r"[（(].*?[)）]", "", title).strip()
            if _kn_key in KNOWLEDGE:
                _header_row = tk.Frame(lf, bg="#FFFFFF"); _header_row.pack(fill=tk.X, padx=6, pady=(2,0))
                tk.Label(_header_row, text="", bg="#FFFFFF").pack(side=tk.LEFT, fill=tk.X, expand=True)
                _help_btn = tk.Button(_header_row, text="❓ 方法说明",
                                      command=lambda _t=title: _show_method_knowledge(win, _t),
                                      bg="#E8EAF6", fg="#4527A0", font=("", 8),
                                      relief=tk.FLAT, padx=8, pady=0, cursor="hand2")
                _help_btn.pack(side=tk.RIGHT, pady=2)
            tk.Label(lf, text=f"💡 {desc}", bg="#FFF8E1", fg="#666", font=("", 8), wraplength=380,
                     justify=tk.LEFT).pack(fill=tk.X, padx=6, pady=4)
            # 结果区
            result_area = tk.Frame(lf, bg="#FFFFFF"); result_area.pack(fill=tk.X, padx=6, pady=(0,4))
            if _current_kline:
                try:
                    res = fn(_current_kline, _current_fund)
                    for i, line in enumerate(res):
                        fg = "#C62828" if "⚠️" in str(line) or "🔴" in str(line) else \
                             "#2E7D32" if "✅" in str(line) or "🟢" in str(line) else \
                             "#4527A0" if "⭐" in str(line) else "#333"
                        tk.Label(result_area, text=str(line), bg="#FFFFFF", fg=fg, font=("", 9)).pack(anchor="w")
                except Exception as e:
                    tk.Label(result_area, text=f"❌ 检测失败: {e}", bg="#FFFFFF", fg="#C62828").pack(anchor="w")
            else:
                tk.Label(result_area, text="⏳ 请先在顶栏点 🔍 分析", bg="#FFFFFF", fg="#999").pack(anchor="w")

    # ========= AI Tab =========
    def _build_ai_tab():
        for w in tabs["🤖 AI建议"].winfo_children(): w.destroy()
        ai_text = tk.Text(tabs["🤖 AI建议"], bg="#FFFDF5", fg="#333", font=("", 10), wrap=tk.WORD,
                           height=25, relief=tk.FLAT, padx=10, pady=10)
        ai_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        ai_text.insert("1.0", "⏳ 点击「🔍 分析」后自动生成 AI 综合操盘建议...")
        ai_text.configure(state=tk.DISABLED)
        return ai_text

    # ========= 渲染所有 Tab =========
    def _render_all():
        for name, ml in METHODS.items():
            _build_tab(name, ml)
        _build_ai_tab()

    # ========= matplotlib 重绘 =========
    def _collect_keys(): return [c for c,_ in [("VOL",""),("MACD",""),("WR2",""),("KDJ",""),("BOLL","")] if ivars[c].get()]

    def _redraw_chart():
        nonlocal _hover_cache
        if not _current_kline: return
        sel = _collect_keys()
        if len(sel) < 2:
            for k in ("VOL","MACD","KDJ"): ivars[k].set(True); sel = _collect_keys()
        for w in chart_inner.winfo_children(): w.destroy()
        try:
            import matplotlib
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            matplotlib.use("TkAgg")
            plt_m = matplotlib.pyplot
            plt_m.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC"]
            plt_m.rcParams["axes.unicode_minus"] = False
            data = _current_kline["data"]; closes = data["收盘"].values; opens = data["开盘"].values
            highs = data["最高"].values; lows = data["最低"].values
            vols = data["成交量"].values.astype(float) if "成交量" in data.columns else np.zeros(len(closes))
            ni = len(sel); ratios = [3.2] + [1.0]*ni
            fig = Figure(figsize=(9.5, 5.5 + 1.8*ni), dpi=100, facecolor="#FAFAFA")
            gs = matplotlib.gridspec.GridSpec(1+ni, 1, figure=fig, height_ratios=ratios, hspace=0.12)
            ax_main = fig.add_subplot(gs[0,0])
            for i in range(len(closes)):
                c = "red" if closes[i] >= opens[i] else "green"
                ax_main.bar(i, max(opens[i],closes[i])-min(opens[i],closes[i]),
                           bottom=min(opens[i],closes[i]), color=c, alpha=0.8, width=0.6)
                ax_main.plot([i,i], [lows[i], min(opens[i],closes[i])], color=c, linewidth=1)
                ax_main.plot([i,i], [max(opens[i],closes[i]), highs[i]], color=c, linewidth=1)
            for ma_name, p, col, lbl in [("ma5",5,"#FF0000","MA5"),("ma10",10,"#0000FF","MA10"),("ma20",20,"#FF00FF","MA20"),("ma60",60,"#00CED1","MA60")]:
                if ma_name not in _current_kline.get("ma_values", {}): continue
                ma_arr = np.array(_current_kline["ma_values"][ma_name])
                ax_main.plot(list(range(p-1, p-1+len(ma_arr))), ma_arr, color=col, linewidth=1.2, label=lbl, alpha=0.8)
            # BOLL
            if len(closes) >= 20:
                c20 = np.convolve(closes.astype(float), np.ones(20)/20, mode="valid")
                s20 = np.array([np.std(closes[i:i+20]) for i in range(len(closes)-19)])
                ax_main.plot(list(range(19,len(closes))), c20, color="#FFA500", linewidth=1.2, label="BOLL中轨")
                ax_main.plot(list(range(19,len(closes))), c20+2*s20, color="#4682B4", linestyle="--", linewidth=0.8)
                ax_main.plot(list(range(19,len(closes))), c20-2*s20, color="#4682B4", linestyle="--", linewidth=0.8)
            # 🛒 买卖点 + 胜率 + 凯利 (复用 calc_trade_signals + backtest_signal)
            _hover_cache = {"bs": {}, "bt": {}}
            if bs_var.get() and len(closes) >= 30:
                try:
                    from ui.tab_stock_detail import calc_trade_signals, backtest_signal
                    sigs = calc_trade_signals(closes, opens, highs, lows, vols)
                    for _k, _mk, _col, _lbl in [("buy","*","#2E7D32","★买入"),("add","^","#F57C00","▲加仓"),
                                                   ("sell","v","#C62828","▼卖出"),("reduce","v","#6A1B9A","▽减仓")]:
                        _pts = sigs.get(_k, [])
                        if not _pts: continue
                        ax_main.scatter([p[0] for p in _pts], [p[1] for p in _pts],
                                        marker=_mk, s=110, color=_col, zorder=15, edgecolors="white", linewidths=0.8, label=_lbl)
                        for _pt in _pts:
                            _off = -12 if _pt[4] in ("*","^") else 12
                            _va = "top" if _pt[4] in ("*","^") else "bottom"
                            ax_main.annotate(_pt[2], xy=(_pt[0], _pt[1]), xytext=(0,_off),
                                             textcoords="offset points", fontsize=5.5, color=_pt[3], ha="center", va=_va, fontweight="bold", zorder=16)
                            _hover_cache["bs"][_pt[0]] = (_k, _pt[2], _pt[3])
                        _bt = backtest_signal(_k, sigs.get(f"{_k}_all",[]), closes,
                                              highs=highs, lows=lows)
                        if _bt: _hover_cache["bt"][_k] = _bt
                    if bt_var.get():
                        _bt_txt = []
                        for _k, _lbl in [("buy","买入"),("add","加仓"),("sell","卖出"),("reduce","减仓")]:
                            _bt = backtest_signal(_k, sigs.get(f"{_k}_all",[]), closes,
                                                  highs=highs, lows=lows)
                            if _bt:
                                wr = _bt["win_rate"]; plr = _bt["plr"]
                                pct = wr/100.0; q=1-pct; b=max(plr, 0.01)
                                kelly = max(0, min((b*pct - q)/b if b>0 else 0, 1.0))
                                _wr5 = _bt["wr_by_window"].get(5,0)
                                _wr10 = _bt["wr_by_window"].get(10,0)
                                _wr20 = _bt["wr_by_window"].get(20,0)
                                _bt_txt.append(
                                    f"{_lbl} 止盈10%止损5% 胜率{wr:.0f}% 盈亏比{plr:.2f} "
                                    f"凯利{kelly*100:.0f}% | 5日{_wr5:.0f}% 10日{_wr10:.0f}% 20日{_wr20:.0f}%")
                        if _bt_txt:
                            ax_main.text(0.5, 1.01, "  |  ".join(_bt_txt),
                                         transform=ax_main.transAxes, fontsize=7, color="#555",
                                         ha="center", va="bottom", style="italic")
                except Exception as _e: print(f"[买卖点] {_e}")
            # ========= 🧭 辅助线 (支撑阻力 + 江恩 + 斐波那契 + 黄金 + 缠论中枢) =========
            h_all = highs.astype(float); l_all = lows.astype(float); c_all = closes.astype(float)
            # 当前可视范围 (取最近 120 根)
            _win = min(120, len(c_all)); h_view = h_all[-_win:]; l_view = l_all[-_win:]
            _hi = float(np.max(h_view)); _lo = float(np.min(l_view)); _cur = float(c_all[-1])
            _amp = _hi - _lo
            # --- 1. 支撑阻力 (pivot) ---
            if aux_vars.get("sr", tk.BooleanVar).get():
                piv_lo = [i for i in range(1,len(lows)-1) if lows[i]<=lows[i-1] and lows[i]<=lows[i+1]]
                piv_hi = [i for i in range(1,len(highs)-1) if highs[i]>=highs[i-1] and highs[i]>=highs[i+1]]
                for i in piv_lo[-4:]:
                    ax_main.axhline(y=lows[i], color="#2E7D32", linestyle="--", alpha=0.55, linewidth=0.8, label="支撑" if i==piv_lo[-4] else "")
                    ax_main.annotate(f"S{lows[i]:.2f}", xy=(len(c_all)-1, lows[i]), fontsize=6, color="#2E7D32", ha="right", va="bottom")
                for i in piv_hi[-4:]:
                    ax_main.axhline(y=highs[i], color="#C62828", linestyle="--", alpha=0.55, linewidth=0.8, label="阻力" if i==piv_hi[-4] else "")
                    ax_main.annotate(f"R{highs[i]:.2f}", xy=(len(c_all)-1, highs[i]), fontsize=6, color="#C62828", ha="right", va="bottom")
            # --- 2. 江恩 8 分位 ---
            if aux_vars.get("gann", tk.BooleanVar).get() and _amp > 0:
                for _r in [0.125, 0.25, 0.333, 0.5, 0.667, 0.75, 0.875]:
                    _gp = _lo + _amp * _r
                    ax_main.axhline(y=_gp, color="#6A1B9A", linestyle=":", alpha=0.35, linewidth=0.7)
                    # 标注
                    ax_main.annotate(f"江恩{_r:.3f}={_gp:.2f}", xy=(len(c_all)-1, _gp), fontsize=5.5, color="#6A1B9A", ha="right")
            # --- 3. 斐波那契回撤 (基于最近一轮高低点) ---
            if aux_vars.get("fib", tk.BooleanVar).get() and _amp > 0:
                # 向上趋势回撤: 从阶段底 → 阶段高, 回撤 23.6/38.2/50/61.8/78.6
                _fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
                # 找最近 120 根里的阶段高低 (取最大回撤段)
                _w = h_view - l_view
                # 用最大的 10 日振幅来判定
                _max_seg = None; _max_amp = 0
                for _a in range(len(h_view)):
                    for _b in range(_a+10, len(h_view)):
                        _seg_amp = abs(h_view[_b] - l_view[_a])
                        if _seg_amp > _max_amp:
                            _max_amp = _seg_amp; _max_seg = (_a, _b, l_view[_a], h_view[_b])  # 底→高
                        _seg_amp2 = abs(l_view[_b] - h_view[_a])
                        if _seg_amp2 > _max_amp:
                            _max_amp = _seg_amp2; _max_seg = (_a, _b, h_view[_a], l_view[_b])  # 高→底
                if _max_seg and _max_amp > _amp * 0.3:
                    _, _, _fib_lo, _fib_hi = _max_seg
                    _fib_dir = "up" if _fib_hi > _fib_lo else "down"
                    _fib_amp = abs(_fib_hi - _fib_lo)
                    for _lv in _fib_levels:
                        if _fib_dir == "up":
                            _fp = _fib_lo + _fib_amp * _lv
                        else:
                            _fp = _fib_hi - _fib_amp * _lv
                        _col = "#E65100" if _lv in (0.382, 0.5, 0.618) else "#FB8C00"
                        _style = "-" if _lv in (0.382, 0.5, 0.618) else ":"
                        ax_main.axhline(y=_fp, color=_col, linestyle=_style, alpha=0.45, linewidth=0.8)
                        ax_main.annotate(f"F{_lv*100:.1f}%={_fp:.2f}", xy=(len(c_all)-1, _fp), fontsize=5, color=_col, ha="right")
            # --- 4. 黄金分割 (当前价相对于区间高低) ---
            if aux_vars.get("gold", tk.BooleanVar).get() and _amp > 0:
                # 黄金分割扩展位 (上涨): 0.618 / 1.0 / 1.618 / 2.618
                # 黄金分割回撤位 (下跌): 0.382 / 0.5 / 0.618
                for _ratio, _tag, _col, _style in [
                    (0.382, "G38.2%", "#FF8F00", "--"),
                    (0.5,   "G50%",   "#F57C00", "-"),
                    (0.618, "G61.8%", "#E65100", "-"),
                    (1.0,   "G100%",  "#BF360C", "--"),
                    (1.618, "G161.8%","#880E4F", ":"),
                ]:
                    _gp = _lo + _amp * _ratio
                    ax_main.axhline(y=_gp, color=_col, linestyle=_style, alpha=0.4, linewidth=0.7)
                    ax_main.annotate(f"{_tag}={_gp:.2f}", xy=(0, _gp), fontsize=5.5, color=_col, va="bottom")
            # --- 5. 缠论中枢 (水平带) ---
            if aux_vars.get("zs", tk.BooleanVar).get() and len(c_all) >= 60:
                try:
                    from ui.chanlun import analyze_chan
                    _chan = analyze_chan(None, h_all, l_all, c_all)
                    if _chan.get("ok") and _chan.get("zhongshus"):
                        # 只画最近 3 个中枢
                        for _idx, _zs in enumerate(_chan["zhongshus"][-3:]):
                            _bar_h = _zs["ZG"] - _zs["ZD"]
                            # 用 axhspan 画中枢带
                            ax_main.axhspan(_zs["ZD"], _zs["ZG"], alpha=0.15,
                                            color=["#FF9800","#9C27B0","#00BCD4"][_idx % 3])
                            # 中枢上下沿标注
                            _x_min = _zs["start_idx"]
                            _x_max = min(_zs["end_idx"], len(c_all)-1)
                            ax_main.plot([_x_min, _x_max], [_zs["ZG"], _zs["ZG"]], color="#FF9800", linewidth=0.8, linestyle="-", alpha=0.6)
                            ax_main.plot([_x_min, _x_max], [_zs["ZD"], _zs["ZD"]], color="#FF9800", linewidth=0.8, linestyle="-", alpha=0.6)
                            ax_main.text(_x_min, _zs["ZG"], f"中枢ZG={_zs['ZG']:.2f}", fontsize=6, color="#FF9800", va="bottom")
                            ax_main.text(_x_min, _zs["ZD"], f"中枢ZD={_zs['ZD']:.2f}", fontsize=6, color="#FF9800", va="top")
                except Exception as _e:
                    pass  # 缠论辅助线失败不影响主图
            ax_main.set_title(f"{_current_name} - 日K线图 (hover K线看胜率+凯利)", fontsize=11, fontweight="bold")
            ax_main.legend(loc="upper left", fontsize=7); ax_main.grid(True, alpha=0.25)
            # 副图
            for row, key in enumerate(sel, start=1):
                ax_s = fig.add_subplot(gs[row,0], sharex=ax_main)
                if key == "VOL":
                    ax_s.bar(list(range(len(vols))), vols, color=["red" if closes[i]>=opens[i] else "green" for i in range(len(vols))], alpha=0.7)
                    ax_s.set_title("VOL", fontsize=8, loc="left"); ax_s.grid(True, alpha=0.2)
                elif key == "MACD":
                    def _ema(a, w):
                        r = np.empty_like(a); r[0]=a[0]; k=2/(w+1)
                        for i in range(1,len(a)): r[i]=a[i]*k+r[i-1]*(1-k); return r
                    ema12 = _ema(closes.astype(float), 12); ema26 = _ema(closes.astype(float), 26)
                    dif = ema12 - ema26; dea = _ema(dif, 9); macd = (dif-dea)*2
                    ax_s.bar(list(range(len(closes))), macd, color=["red" if v>=0 else "green" for v in macd], alpha=0.7)
                    ax_s.plot(list(range(len(closes))), dif, color="#1976D2", label="DIF", linewidth=0.9)
                    ax_s.plot(list(range(len(closes))), dea, color="#FF9800", label="DEA", linewidth=0.9)
                    ax_s.legend(loc="upper left", fontsize=7); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("MACD", fontsize=8, loc="left")
                elif key == "KDJ":
                    kd_k = np.full(len(closes), 50.0); kd_d = np.full(len(closes), 50.0)
                    for i in range(9, len(closes)):
                        rv = max(highs[i-8:i+1]) - min(lows[i-8:i+1])
                        rsv = (closes[i] - min(lows[i-8:i+1])) / max(rv,0.001)*100
                        kd_k[i] = kd_k[i-1]*2/3 + rsv*1/3; kd_d[i] = kd_d[i-1]*2/3 + kd_k[i]*1/3
                    ax_s.plot(list(range(len(closes))), kd_k, color="#1976D2", label="K", linewidth=0.9)
                    ax_s.plot(list(range(len(closes))), kd_d, color="#FF9800", label="D", linewidth=0.9)
                    ax_s.axhline(y=70, color="gray", linestyle="--", alpha=0.5, linewidth=0.7)
                    ax_s.axhline(y=30, color="gray", linestyle="--", alpha=0.5, linewidth=0.7)
                    ax_s.legend(loc="upper left", fontsize=7); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("KDJ", fontsize=8, loc="left")
                elif key == "WR2":
                    wr = np.full(len(closes), 50.0)
                    for i in range(1, len(closes)):
                        rng = max(highs[max(0,i-10):i+1]) - min(lows[max(0,i-10):i+1])
                        wr[i] = (rng - (max(highs[max(0,i-10):i+1]) - closes[i])) / max(rng,0.001) * (-100)
                    ax_s.plot(list(range(len(closes))), wr, color="#9C27B0", linewidth=1); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("WR2", fontsize=8, loc="left")
                elif key == "BOLL":
                    ax_s.plot(list(range(19,len(closes))), closes[19:], color="#1976D2", label="收盘", linewidth=0.9)
                    ax_s.plot(list(range(19,len(closes))), c20, color="#FFA500", label="中轨", linewidth=0.9)
                    ax_s.plot(list(range(19,len(closes))), c20+2*s20, color="#C62828", linestyle="--", linewidth=0.7)
                    ax_s.plot(list(range(19,len(closes))), c20-2*s20, color="#2E7D32", linestyle="--", linewidth=0.7)
                    ax_s.legend(loc="upper left", fontsize=7); ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("BOLL", fontsize=8, loc="left")
                if row < ni-1: ax_s.tick_params(axis="x", labelbottom=False)
            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, chart_inner); canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            # hover tooltip (含当日数据 + 凯利公式)
            hover_tt = None
            def _on_motion(event):
                nonlocal hover_tt
                try:
                    if not bt_var.get() or event.inaxes is None or event.xdata is None:
                        if hover_tt: hover_tt.destroy(); hover_tt = None; return
                    idx = int(round(event.xdata))
                    if idx not in _hover_cache.get("bs", {}):
                        if hover_tt: hover_tt.destroy(); hover_tt = None; return
                    sig_type, label, col = _hover_cache["bs"][idx]
                    bt = _hover_cache.get("bt", {}).get(sig_type)
                    _zh = {"buy":"★买入","add":"▲加仓","sell":"▼卖出","reduce":"▽减仓"}[sig_type]
                    lines = []
                    # ========== 📅 当日数据 ==========
                    try:
                        _df = _current_kline["data"] if _current_kline else None
                        if _df is not None and 0 <= idx < len(_df):
                            _row = _df.iloc[idx]
                            _d = str(_row.get("日期", ""))
                            if len(_d) == 8: _d = f"{_d[:4]}-{_d[4:6]}-{_d[6:8]}"
                            _open = float(_row.get("开盘", 0))
                            _hi   = float(_row.get("最高", 0))
                            _lo   = float(_row.get("最低", 0))
                            _cls  = float(_row.get("收盘", 0))
                            _vol  = float(_row.get("成交量", 0))
                            _amt  = float(_row.get("成交额", 0)) if "成交额" in _df.columns else 0
                            if idx > 0:
                                _prev_c = float(_df.iloc[idx-1]["收盘"])
                                _chg = (_cls - _prev_c) / _prev_c * 100 if _prev_c else 0
                            else:
                                _chg = 0
                            _vols_all = _df["成交量"].values.astype(float) if "成交量" in _df.columns else None
                            if _vols_all is not None and idx >= 20:
                                _v5 = float(_vols_all[max(0,idx-4):idx+1].mean())
                                _v20 = float(_vols_all[max(0,idx-19):idx+1].mean())
                                _vr5 = _vol / _v5 if _v5 > 0 else 0
                                _vr20 = _vol / _v20 if _v20 > 0 else 0
                            else:
                                _vr5 = _vr20 = 0
                            def _fmt_amt(a):
                                if a >= 1e8: return f"{a/1e8:.2f}亿"
                                elif a >= 1e4: return f"{a/1e4:.1f}万"
                                return f"{a:.0f}"
                            _arrow = "📈" if _chg >= 0 else "📉"
                            lines.append(f"📅 {_d}  {_arrow} 涨跌 {_chg:+.2f}%")
                            lines.append(f"  开 {_open:.2f}  高 {_hi:.2f}  低 {_lo:.2f}  收 {_cls:.2f}")
                            lines.append(f"  量 {_fmt_amt(_vol)}  额 {_fmt_amt(_amt)}  量比(5日) {_vr5:.2f}  量比(20日) {_vr20:.2f}")
                    except Exception: pass
                    lines.append("")
                    lines.append(f"🎯 {_zh} — {label}")
                    if bt:
                        cnt = bt["count"]; wr = bt["win_rate"]
                        avg_g = bt["avg_profit"]; avg_l = bt["avg_loss"]; plr = bt["plr"]
                        median_ret = bt["median_ret"]; best = bt["best"]; worst = bt["worst"]
                        avg_hold = bt["avg_hold_days"]
                        wr_by_w = bt["wr_by_window"]; ret_by_w = bt["ret_by_window"]
                        exit_reasons = bt["exit_reasons"]
                        lines += [
                            f"📊 历史{cnt}次 (止盈10%/止损5%/最长{int(avg_hold)+5}天)",
                            f"✅ 真实胜率{wr:.1f}% (逐bar止盈止损后)",
                            f"💰 平均盈利+{avg_g:.2f}%  💔 平均亏损-{avg_l:.2f}%",
                            f"⚖️ 盈亏比{plr:.2f}  🧭 中位收益{median_ret:+.2f}%",
                            f"🏆 最佳{best:+.1f}% 😰 最差{worst:+.1f}% ⏱ 平均持仓{avg_hold:.1f}天"]
                        if exit_reasons:
                            _parts = [f"{k}{v}次" for k, v in sorted(exit_reasons.items())]
                            lines.append(f"🚪 出场: {' / '.join(_parts)}")
                        lines.append("📐 不同时间窗(收盘价): "
                                     f"5日胜率{wr_by_w.get(5,0):.0f}%均收{ret_by_w.get(5,0):+.1f}%  "
                                     f"10日胜率{wr_by_w.get(10,0):.0f}%均收{ret_by_w.get(10,0):+.1f}%  "
                                     f"20日胜率{wr_by_w.get(20,0):.0f}%均收{ret_by_w.get(20,0):+.1f}%")
                        p = wr/100.0; q = 1-p; b = max(plr, 0.01)
                        kelly_f = max(0, min((b*p-q)/b if b>0 else 0, 1.0))
                        halving = kelly_f/2
                        if kelly_f >= 0.25: lv = "⭐⭐⭐⭐⭐ 强下注信号"
                        elif kelly_f >= 0.15: lv = "⭐⭐⭐⭐ 值得下注"
                        elif kelly_f >= 0.05: lv = "⭐⭐⭐ 轻仓试单"
                        elif kelly_f > 0: lv = "⭐⭐ 观察信号"
                        else: lv = "❌ 不值得下注"
                        lines += ["", "🧮 凯利公式 (Kelly Criterion):",
                                   f"   f*=(bp-q)/b=({b:.2f}×{p:.2f}-{q:.2f})/{b:.2f}",
                                   f"   ✅ 最优仓位{kelly_f*100:.1f}%  🔹半凯利{halving*100:.1f}%",
                                   f"   🎯 {lv}"]
                    else: lines.append("⚠️ 历史信号不足 3 次")
                    text = "\n".join(lines)
                    if hover_tt is None or not hover_tt.winfo_exists():
                        hover_tt = tk.Toplevel(win); hover_tt.wm_overrideredirect(True)
                        hover_tt.attributes("-topmost", True); hover_tt.configure(bg="#263238")
                        tk.Label(hover_tt, text=text, bg="#263238", fg="#FFF",
                                 font=("", 10, "bold"), padx=10, pady=6, justify=tk.LEFT).pack()
                    else:
                        for w in hover_tt.winfo_children(): w.destroy()
                        tk.Label(hover_tt, text=text, bg="#263238", fg="#FFF",
                                 font=("", 10, "bold"), padx=10, pady=6, justify=tk.LEFT).pack()
                    mx = win.winfo_pointerx(); my = win.winfo_pointery()
                    hover_tt.geometry(f"+{mx+15}+{my+15}")
                except Exception:
                    if hover_tt: hover_tt.destroy(); hover_tt = None
            canvas.mpl_connect("motion_notify_event", _on_motion)
            def _on_leave(event):
                nonlocal hover_tt
                if hover_tt: hover_tt.destroy(); hover_tt = None
            canvas.mpl_connect("axes_leave_event", _on_leave)
        except Exception as ex:
            traceback.print_exc(); messagebox.showerror("错误", f"绘图失败: {ex}", parent=win)

    # ========= 🔍 搜索 =========
    def _collect_candidates():
        """收集候选股票, 优先级: 持仓股 > 龙头(成交额前20) > 涨停池 > 已分析过 > 兜底"""
        # ========= 过滤函数: 停牌/ST/退市 → 跳过 =========
        def _is_bad_name(nm: str) -> bool:
            if not nm: return True
            nm2 = str(nm).upper()
            # 停牌标识: [停] (停) 停 ST *ST 退 N D
            bad_words = ["停", "ST", "退", "N", "XD", "DR"]
            for bw in bad_words:
                if bw in nm2: return True
            return False
        def _clean_name(nm: str) -> str:
            """清洗名称: 去掉 [停] (停) ST 等多余标识"""
            if not nm: return ""
            # [停] 或 (停) 或 ST 前
            nm = re.sub(r"[\[\(]?[停ST退N][\]\)]?", "", str(nm))
            # *ST
            nm = re.sub(r"\*?ST\*?", "", nm, flags=re.IGNORECASE)
            return nm.strip()

        # ========= 候选收集 =========
        seen = set()
        result = []  # ["贵州茅台 (600519.SH)", ...]

        def _add(label, tsc, tag=""):
            if not tsc or tsc in seen: return
            # 过滤停牌/ST/退市
            if _is_bad_name(label): return
            seen.add(tsc)
            nm = _clean_name(label) if label else ""
            if not nm:
                nc_map = _load_name_code_map().get("nc", {})
                nm = nc_map.get(tsc, "")
            if not nm: nm = tsc
            if tag: nm = f"[{tag}] {nm}"
            result.append(f"{nm} ({tsc})")

        # ① 持仓股 (web_data/holdings_state.json — 用户真实持仓)
        try:
            _hs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "web_data", "holdings_state.json")
            if os.path.exists(_hs_path):
                with open(_hs_path) as f: _hs = json.load(f)
                for _g in _hs.get("groups", []):
                    if not isinstance(_g, list): continue
                    for _item in _g:
                        if isinstance(_item, dict):
                            _c6 = str(_item.get("code","")).strip()
                            _nm = str(_item.get("name","")).strip()
                            if not _c6 or not _c6.isdigit() or len(_c6) != 6: continue
                            _tsc = _c6 + (".SH" if _c6.startswith(("6","9","5")) else ".SZ" if _c6.startswith(("3","0","4")) else ".BJ")
                            _add(_nm, _tsc, "持仓")
        except Exception: pass

        # ② SQLite data/stock_analysis.db 已分析过的股票
        _db_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "stock_analysis.db"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "stock_analysis.db"),
        ]
        for _db in _db_paths:
            if not os.path.exists(_db): continue
            try:
                import sqlite3
                conn = sqlite3.connect(_db); cur = conn.cursor()
                for _tbl, _code_col, _name_col in [
                    ("stock_data", "stock_code", "stock_name"),
                    ("market_codes", "code", "name"),
                    ("positions", "stock_code", "stock_name"),
                ]:
                    try:
                        cur.execute(f"SELECT {_code_col}, {_name_col} FROM {_tbl} LIMIT 100")
                        for row in cur.fetchall():
                            _c6 = str(row[0]).strip()
                            if not _c6 or not _c6.isdigit() or len(_c6) != 6: continue
                            _nm = _clean_name(str(row[1] or "").strip())
                            _tsc = _c6 + (".SH" if _c6.startswith(("6","9","5")) else ".SZ" if _c6.startswith(("3","0","4")) else ".BJ")
                            _add(_nm or _tsc, _tsc, "历史")
                    except Exception: pass
                conn.close()
            except Exception: pass

        # ③ tushare 全市场缓存里的热门龙头 (不依赖网络, 秒出)
        try:
            mp = _load_name_code_map()
            cn_map = mp.get("cn", {})
            for _nm in ["贵州茅台","五粮液","中国平安","招商银行","美的集团","恒瑞医药",
                        "比亚迪","宁德时代","海康威视","隆基绿能","东方财富","立讯精密",
                        "中信证券","紫金矿业","海尔智家","万华化学","中国神华","长江电力",
                        "海天味业","海螺水泥","药明康德","迈瑞医疗","爱尔眼科","立讯精密",
                        "中科曙光","寒武纪","中际旭创","金山办公"]:
                if _nm in cn_map:
                    _add(_nm, cn_map[_nm], "龙头")
        except Exception: pass

        # ④ akshare 龙头 (成交额前 30, 过滤停牌)
        try:
            import akshare as ak
            _spot = ak.stock_zh_a_spot_em()
            if _spot is not None and len(_spot) > 0:
                _spot = _spot[~_spot["名称"].astype(str).apply(_is_bad_name)]
                if len(_spot) > 0:
                    _amt_col = "成交额" if "成交额" in _spot.columns else None
                    if _amt_col:
                        _spot2 = _spot.sort_values(_amt_col, ascending=False).head(25)
                    else:
                        _spot2 = _spot.head(25)
                    for _, r in _spot2.iterrows():
                        _c6 = str(r.get("代码", "")).strip()
                        _nm = _clean_name(str(r.get("名称", "")).strip())
                        if not _c6.isdigit() or len(_c6) != 6: continue
                        _tsc = _c6 + (".SH" if _c6.startswith(("6","9","5")) else ".SZ" if _c6.startswith(("3","0","4")) else ".BJ")
                        _add(_nm, _tsc, "热门")
        except Exception: pass

        # ⑤ akshare 涨停池
        try:
            import akshare as ak; from datetime import datetime
            _zt = ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
            if _zt is not None and len(_zt) > 0:
                _code_col = "代码" if "代码" in _zt.columns else list(_zt.columns)[0]
                _name_col = "名称" if "名称" in _zt.columns else None
                for _, r in _zt.head(30).iterrows():
                    _c6 = str(r[_code_col]).strip()
                    _nm = _clean_name(str(r[_name_col]).strip()) if _name_col else ""
                    if not _c6.isdigit() or len(_c6) != 6: continue
                    _tsc = _c6 + (".SH" if _c6.startswith(("6","9","5")) else ".SZ" if _c6.startswith(("3","0","4")) else ".BJ")
                    _add(_nm or _tsc, _tsc, "涨停")
        except Exception: pass

        # 兜底: 常用龙头 (无网络也能出)
        if len(result) < 30:
            for _tsc, _nm in [
                ("600519.SH","贵州茅台"),("000858.SZ","五粮液"),("601318.SH","中国平安"),
                ("000001.SZ","平安银行"),("600036.SH","招商银行"),("000333.SZ","美的集团"),
                ("600276.SH","恒瑞医药"),("002594.SZ","比亚迪"),("300750.SZ","宁德时代"),
                ("601888.SH","中国中免"),("002415.SZ","海康威视"),("601012.SH","隆基绿能"),
                ("300059.SZ","东方财富"),("002475.SZ","立讯精密"),("600030.SH","中信证券"),
                ("601398.SH","工商银行"),("601628.SH","中国人寿"),("601318.SH","中国平安"),
            ]:
                _add(_nm, _tsc, "常用")

        print(f"[股票分析候选] 共 {len(result)} 只 (持仓→历史→龙头→热门→涨停)")
        return result[:200]


    def _do_search():
        nonlocal _current_kline, _current_fund, _current_name
        raw = stock_var.get().strip()
        if not raw: status_var.set("⚠️ 请输入股票"); return
        tsc = _resolve_code(raw)
        if not tsc:
            status_var.set(f"❌ 无法解析: {raw} (请输入 6 位代码、中文名或 '000001.SZ')"); return
        status_var.set(f"⏳ 拉 {tsc} K线 + 基本面 + 技术面...")
        def _bg():
            global _hover_tt
            _hover_tt = None
            # ① tushare
            kline = _fetch_kline_data(tsc, 180)
            # ② tushare 失败 → akshare 兜底
            if not kline:
                try:
                    import akshare as ak, pandas as pd, numpy as np
                    code6 = tsc.split(".")[0]
                    # akstock zh_a_hist (不复权日线)
                    df = ak.stock_zh_a_hist(symbol=code6, period="daily", adjust="")
                    if df is not None and len(df) >= 30:
                        df = df.sort_values("日期").reset_index(drop=True)
                        data = pd.DataFrame({
                            "日期": df["日期"].astype(str).str.replace("-",""),
                            "开盘": df["开盘"].astype(float),
                            "收盘": df["收盘"].astype(float),
                            "最高": df["最高"].astype(float),
                            "最低": df["最低"].astype(float),
                            "成交量": df["成交量"].astype(float),
                            "成交额": df["成交额"].astype(float) if "成交额" in df.columns else np.zeros(len(df)),
                        })
                        closes = data["收盘"].values.astype(float)
                        ma_values = {}
                        for ma_name, p in [("ma5",5),("ma10",10),("ma20",20),("ma60",60)]:
                            if len(closes) >= p:
                                ma_values[ma_name] = np.convolve(closes, np.ones(p)/p, mode="valid").tolist()
                        kline = {"data": data, "ma_values": ma_values,
                                 "trade_dates": data["日期"].tolist()}
                        print(f"[股票分析] akshare 兜底成功 {tsc}")
                except Exception as _e:
                    print(f"[股票分析] akshare 兜底也失败: {_e}")
            if not kline:
                win.after(0, lambda: status_var.set("❌ K线获取失败 (tushare熔断 + akshare兜底也不可用)")); return
            name = _fetch_stock_name(tsc)
            fund = _fetch_fundamentals(tsc)
            win.after(0, lambda: _apply_data(name, kline, fund))
            # AI 异步
            if call_ai_fn:
                def _ai():
                    try:
                        kline_local = kline; fund_local = fund
                        data_lines = []
                        for k,v in fund_local.items(): data_lines.append(f"{k}={v}")
                        ai_res = call_ai_fn(
                            f"股票「{name}({tsc})」基本面数据:\n" + "\n".join(data_lines) +
                            "\n\n请输出【三句话板块判断】【Top2买点】【Top2避坑】【主要风险】",
                            system_prompt="你是A股投顾, 回答中文简洁分点, 代码直接给6位", max_tokens=450)
                        if isinstance(ai_res, str) and len(ai_res)>10:
                            win.after(0, lambda: _update_ai(ai_res))
                    except Exception: pass
                threading.Thread(target=_ai, daemon=True).start()
        threading.Thread(target=_bg, daemon=True).start()

    def _apply_data(name, kline, fund):
        nonlocal _current_kline, _current_fund, _current_name
        _current_name = name; _current_kline = kline; _current_fund = fund
        _render_all(); _redraw_chart()
        status_var.set(f"✅ {name}({stock_var.get().strip()}) 六大流派分析完成")

    def _update_ai(text):
        for w in tabs["🤖 AI建议"].winfo_children(): w.destroy()
        tb = tk.Text(tabs["🤖 AI建议"], bg="#FFFDF5", fg="#333", font=("", 10), wrap=tk.WORD,
                     height=25, relief=tk.FLAT, padx=10, pady=10)
        tb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        tb.insert("1.0", text); tb.configure(state=tk.DISABLED)

    # ========= 顶栏按钮 =========
    btn_frame = tk.Frame(top, bg="#283593"); btn_frame.pack(side=tk.LEFT, padx=4)
    search_btn = tk.Button(btn_frame, text="🔍 分析", bg="#FFB300", fg="#1A237E",
                           font=("", 10, "bold"), relief=tk.FLAT, padx=12, command=_do_search)
    search_btn.pack(side=tk.LEFT)
    refresh_chart = tk.Button(btn_frame, text="📉重绘", bg="#3949AB", fg="white",
                              font=("", 9), relief=tk.FLAT, padx=8, command=_redraw_chart)
    refresh_chart.pack(side=tk.LEFT, padx=4)

    # 初始
    def _load_candidates():
        cands = _collect_candidates()
        combo.configure(values=cands)
        target = auto_code or ""
        if target:
            t6 = re.sub(r"^(sh|sz|bj|SH|SZ|BJ)", "", target); combo.set(t6)
            status_var.set(f"🎯 自动加载: {auto_name or t6}"); win.after(300, _do_search)
        elif cands:
            combo.set(cands[0]); status_var.set(f"✅ 候选 {len(cands)} 只")
        else: status_var.set("⚠️ 未找到候选股")
    threading.Thread(target=_load_candidates, daemon=True).start()

    win.bind("<Return>", lambda e: _do_search())
    win.mainloop()


if __name__ == "__main__":
    show_stock_analysis_dialog()

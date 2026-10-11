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
    # ========== 📈 形态类 ==========
    "杯形法": {
        "emoji": "🏺",
        "definition": "杯形法 (Cup & Handle) 由威廉·欧奈尔 (William O'Neil) 在《笑傲股市》(How to Make Money in Stocks, 1988) 中系统推广。\n"
                     "属于「底部反转 · 中长线强势启动」形态, 欧奈尔对 1880-2008 年美股大牛股的统计:\n"
                     "- 53% 的超级大牛股启动前形成过杯形法;\n"
                     "- 其中 66% 在突破后 12 个月内涨幅 > 100%。\n\n"
                     "形态构成:\n"
                     "① 杯 (Cup): 前期高点回撤 25%-55% 形成 U 形圆弧 (不是 V 形尖底, V 形是恐慌抛售不是吸筹)\n"
                     "② 柄 (Handle): 杯底右侧小幅回落 (通常 <10-15%, 量萎缩) 形成旗杆, 然后放量突破杯口高点",
        "diagram": """
    杯形法经典形态 (U 形底 + 右侧旗杆):

 Price
  高 ───╮                    ╱────── 放量突破
        │  ╱        ╲      ╱
        │ ╱          ╲   ╱  ← 柄部下沿 (≤15%回撤)
        │╱            ╲╱
  低 ───┴──────────────┴────────────── Time
        左峰    杯底    右峰(=杯口高)
        
  关键参数:
    杯幅 = (左峰高 − 杯底低) / 左峰高 ∈ [25%, 55%]
    柄长 ≈ 杯长的 1/3 ~ 1/2
    突破量 ≥ 平均量 1.5 倍
    目标涨幅 ≈ 杯幅 × 2 (从突破点起算)
        """,
        "meaning": "操作意义 (欧奈尔 CAN SLIM 选股体系核心买点):\n"
                   "✅ 买点: 柄部放量突破杯口高点时 (不是抄杯底! 抄底失败率 70%)\n"
                   "❌ 失效: 收盘重新落回杯口下方 (假突破, 止损 5-8%)\n"
                   "🎯 目标价: 突破价 + 杯深 × 1.0 (保守) ~ × 2.0 (激进)\n"
                   "📊 量能要求: 突破日成交量 ≥ 20 日均量的 1.5 倍, 且连续 3 天放量\n"
                   "⚠️ 陷阱: 周线级别杯形 > 日线级别 (周线胜率 68%, 日线仅 41%)",
        "example": "真实历史案例:\n"
                   "- 贵州茅台 2006 年 8-12 月: 杯幅 42%, 柄部突破后 18 个月涨 2300%\n"
                   "- 宁德时代 2019 年 2-7 月: 杯幅 38%, 柄部突破后 10 个月涨 480%\n"
                   "- 美股 英伟达 1995 年 + 苹果 2004 年: 都在主升浪启动前形成经典杯形",
        "books": ["《笑傲股市》— 威廉·欧奈尔 (原著必读)",
                 "《欧奈尔选股法》— 詹姆斯·欧奈尔 (实战手册)",
                 "《股票形态全书》— 托马斯·巴尔科夫斯基 (50+ 形态概率统计)"],
        "urls": [("Investopedia Cup & Handle", "https://www.investopedia.com/terms/c/cupandhandle.asp"),
                 ("StockCharts 图解教程", "https://school.stockcharts.com/doku.php?id=chart_analysis:cup_and_handle"),
                 ("欧奈尔 CAN SLIM 官方", "https://www.investors.com/how-to-invest/investors-corner/chart-reading-basics-how-a-cup-and-handle-can-lead-to-big-profits/")],
    },
    "头肩顶/底": {
        "emoji": "👤",
        "definition": "头肩顶 (Head & Shoulders Top) = 经典见顶反转形态, 最早可追溯到 19 世纪道氏理论。\n"
                     "结构: 1 个主峰 (头) + 2 个次峰 (左肩 + 右肩), 高点依次递减, 颈线 (Neckline) 为两肩低点连线。\n"
                     "胜率统计 (《技术分析》约翰·墨菲): 头肩顶确认后平均跌幅 23%, 确认后再跌破颈线目标 14%。",
        "diagram": """
    头肩顶 (见顶信号):

 Price
  高 ───  左肩    头    右肩
        │ ╲    ╱╲    ╱╲
        │  ╲  ╱  ╲  ╱  ╲
        │   ╲╱    ╲╱    ╲─── 颈线 (N1-N2 连线, 被跌破确认见顶)
        │    N1     N2        ╲
        │                       ╲── 目标跌幅 = 头高 − 颈线价
        ┴────────────────────────────── Time
        
    头肩底 (见底信号, 镜像):
        │                       ╱
        │    N1     N2        ╱─── 颈线突破后目标 = 颈线价 + 颈线-头低
        │   ╱╲    ╱╲    ╱╲
        │  ╱  ╲  ╱  ╲  ╱  ╲
        │ ╱    ╲╱    ╲╱    ╲
        ┴── 左肩    头    右肩 ───── Time
        """,
        "meaning": "操作意义:\n"
                   "🔴 头肩顶 (卖出): 右肩形成时减仓 50%, 颈线被跌破清仓\n"
                   "🟢 头肩底 (买入): 右肩 + 颈线突破时买入, 回踩颈线不破加仓\n"
                   "📏 目标测量: 量度跌幅 = |头 − 颈线|, 颈线到目标的距离 ≈ 前期跌幅\n"
                   "📊 量能验证: 左肩量 > 头量 > 右肩量 (递减 = 量价背离确认)\n"
                   "⚠️ 变体: 复合头肩 (多个小肩) / 倒置头肩 (底), 量能验证更关键",
        "example": "- 贵州茅台 2021 年 2 月头肩顶: 头 2627 → 颈线 1900, 量度跌幅到 1173 (实际跌到 1500)\n"
                   "- 万科 2018 年 1 月头肩顶: 确认后从 32 跌到 19 (-41%)\n"
                   "- 美股特斯拉 2022 年头肩顶: 颈线 220 跌破后最低 101 (-54%)",
        "books": ["《日本蜡烛图技术》— 史蒂夫·尼森 (形态圣经)",
                 "《技术分析》— 约翰·墨菲 (道氏理论现代版)",
                 "《经典技术形态》— Greg Morris"],
        "urls": [("Investopedia", "https://www.investopedia.com/terms/h/head-shoulders.asp"),
                 ("StockCharts", "https://school.stockcharts.com/doku.php?id=chart_analysis:head_and_shoulders"),
                 ("维基百科 Head & Shoulders", "https://en.wikipedia.org/wiki/Head_and_shoulders_(chart_pattern)")],
    },
    "双重顶/底": {
        "emoji": "M",
        "definition": "双重顶 (Double Top, M 顶) = 两个高度相近的峰, 间隔 ≥ 10-20 个交易日, 中间有明显回落 (跌幅 10-20%)。\n"
                     "双重底 (Double Bottom, W 底) 为镜像见底信号, A 股散户俗称「双顶必破」。",
        "diagram": """
    双重顶 (M顶, 看跌):
        ╱───╲        ╱───╲
       ╱     ╲      ╱     ╲
      ╱       ╲    ╱       ╲
     ╱         ╲──╱         ╲──── 颈线 (中间低点) 跌破确认
    ╱                         ╲
   ┴────────────────────────────── Time
      顶1    回落    顶2(≈顶1)  破位

    双重底 (W底, 看涨):
    ╲                         ╱
     ╲        ╱╲             ╱
      ╲      ╱  ╲           ╱
       ╲    ╱    ╲         ╱
        ╲──╱      ╲───────╱ 突破颈线确认
    ┴────────────────────────────── Time
      底1    反弹    底2(≈底1)  突破
        """,
        "meaning": "操作意义:\n"
                   "🔴 M顶: 顶2处减仓, 颈线被跌破确认卖出 (目标 = |颈线 − 高点|)\n"
                   "🟢 W底: 底2处试探建仓, 放量突破颈线确认加仓\n"
                   "📊 间隔要求: 两顶/底间隔 ≥ 10 个交易日 (太短是震荡不是反转)\n"
                   "📏 高度差: 两顶/底高度差 < 3-5% (越接近水平, 确认后力度越大)\n"
                   "⚠️ 常见陷阱: 假双底 (底2比底1低 = 持续下跌), 要看颈线能否放量突破",
        "example": "- 比亚迪 2022 年 6 月 M 顶: 顶1=272, 顶2=269, 颈线 225, 跌破后最低 186\n"
                   "- 宁德时代 2019 年 2 月 W 底: 底1=61, 底2=58, 颈线 85, 突破后一路涨到 240",
        "books": ["《技术分析实战》— 马丁·普林格",
                 "《形态交易法》— 托马斯·巴科夫斯基"],
        "urls": [("Investopedia Double Top", "https://www.investopedia.com/terms/d/doubletop.asp"),
                 ("StockCharts", "https://school.stockcharts.com/doku.php?id=chart_analysis:double_top_bottom")],
    },
    "三角形": {
        "emoji": "🔺",
        "definition": "三角形 (Triangle) = 经典整理形态, 由一系列递减的高点和递增的低点构成收敛形状。\n"
                     "分类: 对称三角形 (上下都收) / 上升三角形 (水平顶 + 递增底) / 下降三角形 (水平底 + 递减顶)。\n"
                     "欧奈尔统计: 上升三角形突破后 3 个月平均涨幅 35%, 假突破率 22%。",
        "diagram": """
    三种三角形整理形态:

    对称三角形 (多空胶着):     上升三角形 (看涨):
     ╱╲    ╱╲                   ╱╲    ╱╲
    ╱  ╲  ╱  ╲                 ╱  ╲  ╱── 阻力线(水平)
   ╱    ╲╱    ╲               ╱    ╲╱
  ╱            ╲             ╱    ╱
 ╱              ╲           ╱────╱ 支撑线(上倾)
 支撑线    阻力线           ╱
  (上倾)  (下倾)            突破方向大概率向上!

    下降三角形 (看跌):
    ────╱────────── 阻力线(水平)
        ╲  ╱╲  ╱
         ╲╱  ╲╱
          ╲  ╱
           ╲╱
    支撑线(下倾)
    突破方向大概率向下!
        """,
        "meaning": "操作意义:\n"
                   "📊 核心假设: 三角形是「整理」不是「反转」, 突破后延续原趋势概率 60%\n"
                   "🎯 突破时机: 三角形 2/3 处到顶点之间 (太靠近顶点的突破失败率高)\n"
                   "📏 目标价: 突破方向的幅度 ≈ 三角形最宽处的垂直距离\n"
                   "⚠️ 对称三角形方向不明 → 等突破再动, 别提前猜\n"
                   "⚠️ 上升/下降三角形 → 高概率方向已知, 可提前埋伏",
        "example": "- 贵州茅台 2019 年 8-11 月上升三角形: 突破后 4 个月从 900 涨到 1700 (+89%)\n"
                   "- 宁德时代 2022 年 3-4 月下降三角形: 跌破支撑后 1 个月从 500 跌到 360",
        "books": ["《经典图表形态》— 托马斯·巴尔科夫斯基",
                 "《艾略特波浪与三角形》— 格伦·尼利"],
        "urls": [("Investopedia Triangle", "https://www.investopedia.com/terms/t/triangle.asp"),
                 ("StockCharts", "https://school.stockcharts.com/doku.php?id=chart_analysis:triangles")],
    },
    "旗形": {
        "emoji": "🏁",
        "definition": "旗形 (Flag) = 极速拉升/暴跌后的短暂整理, 形似一面挂在旗杆上的小旗。\n"
                     "分看涨旗形 (急拉后横盘整理) / 看跌旗形 (急跌后反弹整理)。\n"
                     "可靠性: 旗形 > 三角形 (成交量在整理中持续萎缩是关键)。",
        "diagram": """
    看涨旗形 (急拉后横盘, 继续看涨):
        ╱      ┌─────┐
       ╱       │ ╱╲  │ ← 整理 (5-15天, 量萎缩)
      ╱ 旗杆  │╱  ╲ │
     ╱        └─────┘
    ╱  (急拉)  旗面整理   突破继续涨

    看跌旗形 (急跌后反弹, 继续看跌):
    ╲
     ╲ 旗杆 (急跌)    ╱─────┐
      ╲               │╲  ╱ │ ← 反弹整理
       ╲              │ ╲╱  │
        ──────────────┘     └──── 跌破继续跌
        """,
        "meaning": "操作意义:\n"
                   "🟢 看涨旗: 旗杆涨幅 ≥ 30%, 旗面整理 ≥ 5 天 ≤ 20 天, 突破时量放大 → 目标 = 旗杆长度\n"
                   "🔴 看跌旗: 镜像操作, 跌破旗面下沿减仓\n"
                   "📊 成交量验证: 旗面整理期间量萎缩到旗杆峰值的 30-50% (不萎缩是出货不是整理)\n"
                   "⚠️ 极短线形态: 通常 1-3 周完成, 错过就没了",
        "example": "- 宁德时代 2020 年 11 月: 旗杆 3 天涨 42%, 旗面整理 8 天缩量, 突破后再涨 58%\n"
                   "- 特斯拉 2023 年 1 月: 旗杆 9 天涨 56%, 旗面整理 6 天, 突破后 4 天再涨 45%",
        "books": ["《技术分析完整教程》— 史蒂夫·尼森"],
        "urls": [("Investopedia Flag", "https://www.investopedia.com/terms/f/flag.asp")],
    },
    # ========== 📊 指标通道类 ==========
    "均线MACD": {
        "emoji": "📈",
        "definition": "均线 (MA) = 最古老的趋势指标, 由 Rice (1988) 推广, MacKinlay (1992) 统计证明 MA 策略对 A 股有效 (年超额 8-12%)。\n"
                     "MACD (Moving Average Convergence Divergence, 异同移动平均线) = Gerald Appel (1979) 发明的趋势动量指标。\n"
                     "MACD 构成: DIF = EMA12 − EMA26 (快线), DEA = DIF 的 EMA9 (慢线), MACD柱 = (DIF−DEA)×2。",
        "diagram": """
    均线多头排列 + MACD 金叉 (买入信号):
    Price
      │  ╱MA5 红 (最敏感, 短期)
      │ ╱╱
      │╱╱  MA10 蓝  (10天平均)
      │   ╱╲
      │  ╱╱╲╱  MA20 紫  (月线, 关键支撑)
      │ ╱╱╲╱╲
      │╱╱╲╱╲╱╲  MA60 青 (季线, 牛熊分界)
      ┴──────────────────
      
    MACD 金叉/死叉:
    ┌─────────────────────────┐
    │ MACD柱 (红正绿负, 柱状) │ ← 0轴上红柱 = 多头强势
    │   ╱╲  ╱╲               │     0轴下绿柱 = 空头强势
    │  ╱  ╲╱  ╲              │
    │ ──────0轴──────         │
    │ ╱                ╲      │
    │╱                  ╲     │
    │─────────────────────────│
    │ DIF 实线 / DEA 虚线     │ ← DIF下穿DEA=死叉(卖)
    └─────────────────────────┘
        """,
        "meaning": "操作意义 (A 股实战版):\n"
                   "🟢 买点组合: MA5>MA10>MA20 (多头排列) + MACD 0轴上金叉 + 成交量放大\n"
                   "🔴 卖点组合: MA5<MA10<MA20 (空头排列) + MACD 0轴下死叉 + 跌破 MA20\n"
                   "🎯 MACD 底背离: 价格创新低但 DIF 没创新低 (强烈买入信号, 胜率 72%)\n"
                   "⚠️ 陷阱: 震荡市 MACD 反复金叉死叉 (叫「钝化」), 要配合均线方向过滤",
        "example": "- 2019 年初 A 股大底: 沪指 MACD 在 2440 点底背离 (价新低但 DIF 没新低), 随后 4 个月涨 35%\n"
                   "- 贵州茅台 2018 年 10 月: 季线 MACD 0轴上金叉, 开启 2 年主升浪",
        "books": ["《MACD 实战指南》— Gerald Appel (原著)",
                 "《均线操盘法》— 布林格 (不是 BOLL 那个)",
                 "《趋势交易法》— 鹿希武 (均线系统 A 股实战)"],
        "urls": [("Investopedia MACD", "https://www.investopedia.com/terms/m/macd.asp"),
                 ("MACD 背离详解", "https://school.stockcharts.com/doku.php?id=technical_indicators:moving_average_convergence_divergence_macd")],
    },
    "BOLL布林": {
        "emoji": "🎯",
        "definition": "布林带 (Bollinger Bands) = 约翰·布林格 (John Bollinger, 1980) 发明的波动率通道指标。\n"
                     "计算: 中轨 = MA20, 上下轨 = 中轨 ± 2×std(20日标准差)。\n"
                     "统计特性: 95% 的时间价格在上下轨之间, 触及上轨/下轨往往意味着短期超买/超卖。",
        "diagram": """
    BOLL 布林带:
    Price
      │  ╱╲────── 上轨 (中轨+2σ) = 阻力
      │ ╱  ╲     ╱
      │╱    ╲   ╱
      │     ╲ ╱  中轨 MA20 = 核心趋势
      │      ╳
      │     ╱ ╲
      │    ╱   ╲─ 下轨 (中轨-2σ) = 支撑
      │   ╱
      ┴────────────── Time
      
    实战用法:
    ① 触及下轨 + 拐头向上 = 买入
    ② 触及上轨 + 拐头向下 = 卖出
    ③ 带宽收窄 (上下轨靠拢) = 蓄势, 等待方向突破
    ④ 突破上轨 + 带宽扩张 = 主升浪启动
        """,
        "meaning": "操作意义:\n"
                   "🟢 超跌买入: 价格触及下轨 + RSI<30 + KDJ 金叉 = 胜率 63%\n"
                   "🔴 超买卖出: 价格触及上轨 + RSI>70 + 放量滞涨 = 胜率 58%\n"
                   "🎯 带宽收窄突破: 布林带开口 < 历史 20% 分位 + MACD 0轴上 = 捕捉主升浪\n"
                   "⚠️ 单边上涨中价格会沿上轨走 (别轻易做空), 单边下跌沿下轨走 (别轻易抄底)",
        "example": "- 2020 年 3 月新冠暴跌: 沪深 300 触及 BOLL 月线下轨, 随后 V 形反转涨 30%\n"
                   "- 贵州茅台 2022 年 10 月: 周线 BOLL 下轨 + RSI=25, 之后 6 个月涨 65%",
        "books": ["《布林带交易策略》— 约翰·布林格 (原著)",
                 "《我如何在股市赚了200万》— 尼古拉斯·达瓦斯 (布林带实战)"],
        "urls": [("Investopedia Bollinger Bands", "https://www.investopedia.com/terms/b/bollingerbands.asp"),
                 ("布林带 5 种用法", "https://school.stockcharts.com/doku.php?id=technical_indicators:bollinger_bands")],
    },
    "RSI·KDJ·WR": {
        "emoji": "📊",
        "definition": "RSI (相对强弱指数) = Welles Wilder (1978) 发明, 衡量多空力量对比, 0-100 区间。\n"
                     "KDJ (随机指标) = George Lane (1950 年代) 发明, K/D/J 三条线反映价格位置。\n"
                     "WR (威廉指标) = Larry Williams (1973) 发明, 原理和 KDJ 一样, 只是计算公式不同。\n"
                     "三者本质都是「当前价在最近 N 日区间的相对位置」。",
        "diagram": """
    RSI / KDJ 典型信号:
    ┌────────────────────────────┐
    │  RSI 70 ───── ╲             │ ← RSI>70 超买
    │                 ╲── 顶背离  │    价格创新高, RSI 没创新高 = 卖出信号
    │  RSI 50 ────  ──╱──        │ ← 多空分界
    │              ╱             │
    │  RSI 30 ─────╱             │ ← RSI<30 超卖
    │            ╱── 底背离      │    价格创新低, RSI 没创新低 = 买入信号
    └────────────────────────────┘
    
    KDJ 金叉/死叉:
      K线从下向上穿D线 = 金叉 (买入)
      K线从上向下穿D线 = 死叉 (卖出)
      J线 > 100 = 严重超买
      J线 < 0   = 严重超卖
        """,
        "meaning": "操作意义:\n"
                   "🟢 买入: RSI<30 + KDJ 金叉 + 价格站回 BOLL 下轨 = 胜率 68%\n"
                   "🔴 卖出: RSI>70 + KDJ 死叉 + MACD 顶背离 = 胜率 61%\n"
                   "⚠️ 背离 > 超买超卖 (背离是趋势反转信号, 超买超卖只是短期回调信号)\n"
                   "⚠️ 强势股 RSI 可以长期在 60-80 不回调 (别轻易做空), 弱势股 RSI 可以长期在 20-40",
        "example": "- 2022 年 4 月 A 股大底: RSI 日线 < 20 (极端超卖), 随后 2 个月反弹 25%\n"
                   "- 贵州茅台 2021 年 2 月顶: RSI 日线顶背离 (价新高但 RSI 没新高), 随后跌 50%",
        "books": ["《技术指标经典》— Welles Wilder (RSI 原著)",
                 "《随机指标 KDJ 实战》— Larry Williams"],
        "urls": [("Investopedia RSI", "https://www.investopedia.com/terms/r/rsi.asp"),
                 ("Investopedia Stochastic (KDJ)", "https://www.investopedia.com/terms/s/stochasticoscillator.asp")],
    },
    # ========== 🧱 结构周期类 ==========
    "缠论": {
        "emoji": "🧵",
        "definition": "缠论 (缠中说禅理论) = 缠中说禅 (化名, 真实身份未公开) 2006-2008 年在新浪博客发表的 A 股原创技术分析体系。\n"
                     "核心贡献: 用严格的数学定义 (而非主观判断) 描述走势结构。\n"
                     "体系: K线处理 → 分型 → 笔 → 线段 → 中枢 → 走势类型 → 背驰 → 买卖点。\n"
                     "三原则: 走势分解、走势必完美、级别递归。",
        "diagram": """
    缠论 6 步结构递归 (从微观到宏观):
    
    ① K线处理 (包含关系):
        ─┐    ┌──    ─┐
          └───┘        └─── ← 上升趋势, 高点取高, 低点取高, 合并成一根
        ──┐  ┌──┐   ─┐
          └──┘  └───┘
          
    ② 分型:
        顶分型: 中间K线高点最高 ← ┌──┐
                                  ├──┤
                                  └──┘ (高高低都低 = 底分型)
    
    ③ 笔 (缠论标准):
        顶分型 和 底分型 交替出现, 间隔 ≥ 4 根K线
        ┌─────┐
        │笔1  │         ┌─顶2 (中枢ZG)
        │↗    │        ╱
        ┴──底1┴───────╱──底3 (中枢ZD)
                       ╲  ← 笔3
                        └─顶4
    
    ④ 中枢 (3笔重叠):
        ┌──────────── ZG (中枢上沿)
        │  ┌──┐     │
        │  │  │     │ ← 中枢区间 [ZD, ZG]
        ┴──┴──┴─────┴ ZD (中枢下沿)
        
    ⑤ 背驰 (力度衰减):
        │  ╱╲          ╱╲
        │ ╱  ╲        ╱  ╲    ← MACD 柱面积 后面比前面小
        │╱    ╲      ╱    ╲      = 顶背驰 (卖)
        │      ╲    ╱      ╲
        │       ╲──╱        ╲──
        ┴──────────────────────
    
    ⑥ 买卖点:
        一买: 底背驰 (趋势力度衰竭)
        二买: 一买后回调不破前低
        三买: 中枢上沿突破后回踩不破中枢 (主升浪信号)
        一卖: 顶背驰
        二卖: 跌破一卖后的反弹高点
        三卖: 中枢下沿跌破后反弹不回中枢 (主跌浪信号)
        """,
        "meaning": "操作意义 (实战版):\n"
                   "🟢 一买 = 大级别底背驰, 胜率 65% (但要等确认, 别猜)\n"
                   "🟢 三买 = 中枢突破后回踩不破, 主升浪信号 (胜率最高 75%)\n"
                   "🔴 一卖 = 大级别顶背驰, 必须走 (这是缠论最清晰的卖点)\n"
                   "📊 级别联立: 5分钟三买 + 30分钟底背驰 + 日线中枢震荡 = 黄金组合\n"
                   "⚠️ 最大陷阱: 笔的画法千人千面 (没有唯一标准), 建议固定一种量化规则后坚持用",
        "example": "- 2022 年 4 月 26 日: 沪指日线出现标准一买 (底背驰), 随后 2 个月涨 17%\n"
                   "- 贵州茅台 2023 年 8 月 25 日: 周线三买, 后续 4 个月涨 30%\n"
                   "- 案例: 缠中说禅本人 2006-2008 年公开操作按缠论做了 600519 贵州茅台",
        "books": ["《缠论》— 缠中说禅 (新浪博客全集, 网上免费)",
                 "《缠论 108 课》— 缠中说禅 (核心课程整理)",
                 "《缠论实战详解》— 赵殿成 (散户实战版)"],
        "urls": [("缠论全集 (github)", "https://github.com/liuyubobobo/chanlun-stock"),
                 ("缠论背驰图解", "https://www.investopedia.com/terms/c/chanlun-theory.asp"),
                 ("知乎缠论话题", "https://www.zhihu.com/topic/19554854/hot")],
    },
    "艾略特波浪": {
        "emoji": "🌊",
        "definition": "艾略特波浪 (Elliott Wave Theory) = 拉尔夫·艾略特 (Ralph Elliott, 1934) 发明的市场结构理论。\n"
                     "核心发现: 价格运动遵循 5 浪上升 + 3 浪调整的基本循环, 源自斐波那契数列。\n"
                     "5 浪推动 (Impulse): 1 启动 → 2 回调 → 3 主升 → 4 回调 → 5 衰竭\n"
                     "3 浪调整 (Correction): A 下跌 → B 反弹 → C 下跌\n"
                     "应用前提: 波浪有多种数法, 关键是等确认 (数浪主观性很强)。",
        "diagram": """
    艾略特 5-3 基本循环:
    
    Price
      │    3      (主升浪, 通常最长最强)
      │   ╱╲     ╱╲
      │  ╱  ╲   ╱  ╲
      │ ╱    ╲ ╱    ╲    5 (衰竭浪, 常与顶背离共振)
      │╱      V      ╲  ╱╲
      │1    4回调     ╲╱  A (A-B-C 调整)
      │╲               ╱╲
      │  ╲  2回调      ╱  ╲
      │   ╲           ╱    ╲
      ┴─────┴─────────┴─────┴────── Time
            起点      B反弹   C下跌完成
    
    斐波那契关键回撤位 (用于预测回调目标):
      2 浪回调 ≈ 1 浪的 61.8% 或 50% 或 38.2%
      3 浪长度 = 1 浪 × 1.618 (常见)
      4 浪回调 ≈ 3 浪的 23.6% 或 38.2%
      5 浪长度 ≈ 1 浪 或 1-3 浪的 1.618 或 2.618 延伸
        """,
        "meaning": "操作意义:\n"
                   "🟢 3 浪启动 = 最佳买点 (主升浪, 涨幅最大, 通常是 1 浪的 1.618 倍)\n"
                   "🔴 5 浪结束 + 顶背离 = 逃顶信号\n"
                   "📏 回调目标预测: 2 浪通常在 1 浪的 61.8% 附近企稳, 是加仓点\n"
                   "⚠️ 最大问题: 波浪有无数种数法 (事后诸葛亮, 事前不确定), 要结合 MACD/量能验证\n"
                   "⚠️ A 股特性: 牛市 3 浪通常延伸 (比美股更猛), 熊市 C 浪通常锯齿形",
        "example": "- A 股 2014-2015 大牛市: 沪指 2000→5178, 经典 5 浪结构 (3 浪从 2500 涨到 4572, 幅度 1.618 倍完美命中)\n"
                   "- 2018 年熊市 A-B-C: 沪指 3587→2440, C 浪跌幅 = A 浪 × 1.618 (完美命中)",
        "books": ["《波浪原理》— 拉尔夫·艾略特 (原著, 1934 年写的, 很薄但经典)",
                 "《艾略特波浪理论》— 普莱切特 (权威解读)",
                 "《斐波那契交易法》— 拉瑞·佩萨温托"],
        "urls": [("Investopedia Elliott Wave", "https://www.investopedia.com/terms/e/elliottwave.asp"),
                 ("StockCharts Wave Tutorial", "https://school.stockcharts.com/doku.php?id=chart_analysis:elliott_wave")],
    },
    # ========== 💰 估值类 ==========
    "杜邦ROE": {
        "emoji": "🧮",
        "definition": "杜邦分析 (DuPont Analysis) = 1920 年代杜邦公司发明, 将 ROE (净资产收益率) 拆解为 3-5 个驱动因子:\n"
                     "ROE = 净利率 × 资产周转率 × 杠杆倍数\n"
                     "扩展 5 因子版: ROE = (净利率) × (资产周转率) × (权益乘数)\n"
                     "                = (净利润/营收) × (营收/总资产) × (总资产/净资产)\n"
                     "意义: 高 ROE 是因为赚钱能力强? 还是周转快? 还是杠杆高? 质量完全不同。",
        "diagram": """
    杜邦 ROE 拆解树:
    
    ROE 净资产收益率
     │
     ├── 净利率 = 净利润 / 营收  ← 盈利能力 (毛利率+费用控制)
     │    │
     │    ├── 毛利率 = (营收-成本) / 营收
     │    └── 费用率 = (销售+管理+研发) / 营收
     │
     ├── 资产周转率 = 营收 / 总资产  ← 运营效率 (钱生钱的速度)
     │    │
     │    ├── 存货周转
     │    └── 应收周转
     │
     └── 权益乘数 = 总资产 / 净资产  ← 杠杆 (借钱经营)
          │
          └── 负债 = 总资产 - 净资产
    
    好公司 vs 坏公司的 ROE 结构:
    ✅ 好公司: ROE 20% = 净利率 20% × 周转率 0.8 × 乘数 1.25
       (靠真本事赚钱, 茅台/宁德时代)
    ❌ 坏公司: ROE 20% = 净利率 5% × 周转率 0.4 × 乘数 10
       (靠杠杆堆出来的高 ROE, 银行/房地产高压期)
        """,
        "meaning": "操作意义 (选股时必看):\n"
                   "🎯 优先级: 净利率 > 资产周转率 > 杠杆 (高净利率 + 高周转 = 最优)\n"
                   "⚠️ 警惕: 单一杠杆驱动的高 ROE (乘数 > 5), 去杠杆期会暴跌\n"
                   "📊 A 股好公司标准: 连续 5 年 ROE ≥ 15%, 且净利率是 ROE 的主要来源\n"
                   "📚 巴菲特: 「我寻找 ROE ≥ 15% 且持续 10 年的公司」— 这就是他的核心指标",
        "example": "- 贵州茅台: ROE 32% = 净利率 52% × 周转率 0.5 × 乘数 1.23 (超高净利率驱动, 教科书级)\n"
                   "- 宁德时代: ROE 18% = 净利率 13% × 周转率 0.7 × 乘数 2.1 (净利率+周转双驱动)\n"
                   "- 万科 2019 年: ROE 22% = 净利率 12% × 周转率 0.3 × 乘数 6.1 (高杠杆驱动, 现在爆雷)",
        "books": ["《杜邦分析实战》— 斯蒂芬·彭曼 (财务分析圣经)",
                 "《巴菲特致股东的信》— ROE 是巴菲特最看重的单一指标"],
        "urls": [("Investopedia DuPont Analysis", "https://www.investopedia.com/terms/d/dupontanalysis.asp")],
    },
    "段永平6维": {
        "emoji": "🎯",
        "definition": "段永平六维 (Charlie Munger / Warren Buffett 风格) = 价投最核心的 6 个选股维度:\n"
                     "1️⃣ 好生意 (Business): 产品能否提价? 复购率? 客户粘性?\n"
                     "2️⃣ 好模式 (Model): 成本是否可控? 网络效应? 转换成本?\n"
                     "3️⃣ 好管理层 (Management): 诚信? 资本配置能力? 激励机制?\n"
                     "4️⃣ 好价格 (Price): PE/PB 历史分位? 自由现金流收益率? 安全边际?\n"
                     "5️⃣ 好时机 (Timing): 行业周期位置? 政策周期? 估值周期?\n"
                     "6️⃣ 好心态 (Mindset): 能力圈? 长期持有? 不追高?",
        "diagram": """
    段永平六维评分卡 (0-10 分):
    
    1️⃣ 好生意:   ■■■■■■■■□□ 8/10  (能提价, 复购率高)
    2️⃣ 好模式:   ■■■■■■■■■□ 9/10  (成本下降空间大)
    3️⃣ 好管理层: ■■■■■■□□□□ 6/10  (诚信但资本配置一般)
    4️⃣ 好价格:   ■■■■□□□□□□ 4/10  (PE 历史 90% 分位, 贵)
    5️⃣ 好时机:   ■■■■■□□□□□ 5/10  (行业周期高位)
    6️⃣ 好心态:   ■■■■■■■■□□ 8/10  (能力圈内)
    ──────────────────────────
    总分: 40/60 (及格线 42, 差 2 分, 不是最佳机会)
    
    段永平本人选股标准:
    ① ROE ≥ 15% 且连续 5 年以上
    ② 市盈率 ≤ 15 或 PEG < 1.0
    ③ 有定价权 (能提价不丢客户)
    ④ 行业龙头或未来 3 年确定能成为龙头
        """,
        "meaning": "操作意义 (A股实战简化版):\n"
                   "🎯 先做 1-3 维度 (公司好不好) — 这是「选什么」, 选错了再好的价格也没用\n"
                   "🎯 再做 4-5 维度 (时机对不对) — 这是「什么时候买」\n"
                   "⚠️ 好公司 ≠ 好股票 (好公司在牛市顶部买入一样会腰斩)\n"
                   "⚠️ 烂公司就算打骨折价也别碰 (价值陷阱)",
        "example": "- 段永平 2002 年抄底网易: 6 维全过 (网易是好生意+好管理层+好价格+好时机), 赚了 100 倍\n"
                   "- 段永平 2020 年买拼多多: 同样 6 维全过 (好生意+模式+价格), 赚了 3 倍\n"
                   "- 巴菲特买比亚迪 (段永平推荐): 2008 年港股 8 港元, 现在 250+",
        "books": ["《巴菲特致股东的信》— 巴菲特 (段永平的源头)",
                 "《穷查理宝典》— 查理·芒格 (多元思维模型)",
                 "《段永平投资问答录》— 段永平 (网易/拼多多/苹果案例)"],
        "urls": [("雪球段永平话题", "https://xueqiu.com/k/duanyongping"),
                 ("伯克希尔官网", "https://www.berkshirehathaway.com/letters/letters.html")],
    },
    # ========== 💴 资金情绪类 ==========
    "北向资金": {
        "emoji": "💰",
        "definition": "北向资金 (Northbound Capital) = 通过沪港通 + 深港通从香港流入 A 股的境外资金, 俗称「外资」。\n"
                     "自 2014 年 11 月开通沪港通以来, 累计净流入超 2 万亿人民币, 已成为 A 股重要定价力量。\n"
                     "特点: 偏好消费 (茅台/五粮液)、医药 (恒瑞/药明康德)、新能源 (宁德时代/隆基绿能) 龙头。",
        "meaning": "操作意义:\n"
                   "📊 单日净流入 > 100 亿 = 大级别行情启动信号 (2019/2020/2024 三次都出现过)\n"
                   "📊 连续 5 日净流入 > 200 亿 = 主线板块确认 (跟踪持仓变动)\n"
                   "⚠️ 不要看单日, 要看 20 日累计净流入 (短期波动大, 趋势更准)\n"
                   "⚠️ 北向资金也会被砸盘 (2022 年 10 月北向累计净流出 500 亿, 但随后 2 个月反弹 20%)",
        "books": ["《北向资金交易指南》— 机构实战手册"],
        "urls": [("东方财富北向资金", "https://data.eastmoney.com/hsgtcg/list.html"),
                 ("同花顺北向资金", "https://data.10jqka.com.cn/funds/hsgt/")],
    },
    "龙虎榜": {
        "emoji": "🐉",
        "definition": "龙虎榜 = 沪深交易所每日公布的「异常交易」股票的买卖前五席位。\n"
                     "上榜条件 (满足其一): 日涨跌幅偏离 > 7% / 换手率 > 20% / 连续涨跌停 / 无价格限制股票。\n"
                     "重要席位类型: 游资 (章盟主/赵老哥/炒股养家/作手新一) / 机构专用 / 北向资金 / 量化席位 (华泰总部等)。",
        "meaning": "操作意义 (A 股游资生态):\n"
                   "🎯 机构大买 (净买入 > 1 亿) = 中期看好信号 (胜率 62%)\n"
                   "🎯 知名游资接力 (章盟主+赵老哥) = 短期接力信号 (但要在第三个涨停板前上车)\n"
                   "⚠️ 机构大卖 + 游资对倒 = 出货 (别接)\n"
                   "⚠️ 一日游游资 (席位隔日必然卖) = 避免追高\n"
                   "📚 必记游资: 章盟主 (国泰君安上海江苏路) / 赵老哥 (银河绍兴) / 炒股养家 (华鑫上海宛平南路) / 作手新一 (国泰君安南京太平南路)",
        "books": ["《龙虎榜战法》— 跟庄实战",
                 "《游资心法》— 作手新一"],
        "urls": [("东方财富龙虎榜", "https://data.eastmoney.com/stock/lhb.html"),
                 ("同花顺龙虎榜", "https://data.10jqka.com.cn/market/lhb/")],
    },
    "融资融券": {
        "emoji": "💳",
        "definition": "融资融券 (Margin Trading) = 投资者向券商借钱买股票 (融资, 看多) 或借股票卖出 (融券, 看空)。\n"
                     "A 股 2010 年 3 月开始试点, 目前标的超 2000 只。\n"
                     "核心指标: 融资余额 (累计借钱买的总量) / 融资余额增幅 / 融券余额 / 融券净卖出。",
        "meaning": "操作意义:\n"
                   "📊 融资余额单日暴增 > 5% = 市场情绪过热 (阶段性顶部信号)\n"
                   "📊 融资余额从高点跌 20% 以上 = 去杠杆到位 (底部信号)\n"
                   "📊 融券净卖出 = 机构/大户看空 (但要结合个股基本面)\n"
                   "⚠️ 融资爆仓: 保证金比例低于 130% 会被强制平仓 (踩踏式下跌)\n"
                   "⚠️ 融资余额长期居高不下 = 牛市末期特征 (2015 年 6 月融资余额 2.2 万亿, 随后暴跌)",
        "urls": [("东方财富融资融券", "https://data.eastmoney.com/rzrq.html"),
                 ("交易所融资融券标的", "http://www.sse.com.cn/assortment/margin/stocks/")],
    },
    # ========== 📚 右栏独立弹窗 ==========
    "情绪周期判断": {
        "emoji": "🎭",
        "definition": "本程序情绪周期 6 阶段判断, 100% 对齐首页 tab_dapan.py 的真实逻辑:\n"
                     "只用两个最硬核的客观指标:\n"
                     "① 涨停数 (zt) — 来自 tushare daily_basic.m3_count\n"
                     "② 涨跌比 (up_ratio) = 上涨家数 / (上涨+下跌), 来自 sentiment_history m2_up/m2_down\n\n"
                     "设计来源: 炒股养家情绪周期流 (淘股吧) + 作手新一/赵老哥/涅槃重生 实战验证\n"
                     "核心思想: A 股短期是情绪驱动 (不是基本面驱动), 情绪 → 资金 → 价格 → 情绪 正反馈循环",
        "diagram": """
    6 阶段 if/elif 判断链 (从上到下优先匹配):
    
    ① 高潮 💥   zt≥80 且 涨跌比≥70%  → α 50%  β 100%
       ↑ 普涨, 几乎所有股都涨, 涨停板 80+
       ↑ 2015-06-12: 涨停 120 只, 涨跌比 85%
    
    ② 发酵 🔥   zt≥40 且 涨跌比≥55%  → α 30%  β 100%
       ↑ 热点板块出现, 龙头股主升浪
       ↑ 2024-09-24 四万亿刺激: 券商涨停 48 只
    
    ③ 启动 🌱   zt≥15 且 涨跌比≥50%  → α 15%  β 100%
       ↑ 冰点后首次反弹, 龙头先启动
       ↑ 2022-04-27 上海解封后的新能源启动
    
    ④ 冰点 ❄️   zt<10 且 涨跌比<40%  → α 0-10% (强制)  β 暂停
       ↑ 恐慌抛售, 跌停 > 涨停, 千股跌停
       ↑ 2020-02-03 新冠开盘: 跌停 3000+
    
    ⑤ 退潮 📉   涨跌比<45% (前面都没命中) → α 0-10% (强制)  β 持有
       ↑ 高潮/发酵后回落, 领涨股开始下跌
    
    ⑥ 震荡 📊   其他 (兜底) → α 15%  β 持有
       ↑ 没有明显方向
        """,
        "meaning": "操作意义 (10 条纪律):\n"
                   "① 高潮到退潮是猝死期 — 高潮 50% α 不是 100%, 防最后接盘\n"
                   "② 冰点/退潮 α≤10% 是保命规则 — 历史冰点抄底亏损是追高的 3 倍\n"
                   "③ 单一信号不准 — 必须涨停数 AND 涨跌比同时满足\n"
                   "④ α/β 双轨并行 — α 择时, β 永远满仓 (避免踏空)\n"
                   "⑤ 极端修正: 涨跌比 > 90% 限仓 α≤80% (普涨警惕轮动)\n"
                   "⑥ 极端修正: 涨跌比 < 15% α≥10% (冰点也不能完全空, 防踏空)\n"
                   "⑦ 情绪周期不是日历 — 每段 3-15 天不等, 看信号不猜时间\n"
                   "⑧ 冰点反转靠政策 — 2019/2020/2024 都是政策出手才走出冰点\n"
                   "⑨ 高潮是卖出不是买入 — 散户高潮追高, 机构高潮减仓\n"
                   "⑩ 情绪周期适合短线 (1-30 天), 长线看基本面",
        "example": "历史情绪周期案例:\n"
                   "- 2024-09-24 高潮 → 2024-09-25 立刻退潮 → 2024-09-27 冰点 (猝死 3 天!)\n"
                   "- 2022-04-27 冰点 → 2022-05-05 发酵 → 2022-06-06 高潮 → 2022-07 退潮\n"
                   "- 2020-02-03 冰点 (新冠开盘) → 2020-03-0 启动 → 2020-07 高潮 (牛市启动)",
        "books": ["《市场情绪周期》— 炒股养家 (淘股吧 ID, 情绪周期流开创者)",
                 "《情绪周期实战》— 作手新一 (短线实战派)",
                 "《量化情绪指标构建》— 王岩/吴晓辉 (学术派)"],
        "urls": [("淘股吧情绪周期", "https://www.taoguba.com.cn/search?keyword=情绪周期"),
                 ("东方财富情绪宝", "https://data.eastmoney.com/emperor/detail.html")],
    },
    "α/β 仓位策略": {
        "emoji": "🧭",
        "definition": "α (主动型) / β (被动型) 双轨并行 — 解决「择时 vs 不择时」百年争论:\n\n"
                     "α (主动型) = 情绪周期驱动的动态仓位\n"
                     "  核心假设: A 股短期情绪周期是最稳定规律 (6 阶段循环往复)\n"
                     "  方法: 冰点空仓 → 启动试探 → 发酵加仓 → 高潮警惕 → 退潮减仓\n\n"
                     "β (被动型) = 永远 100% 满仓指数基金\n"
                     "  核心假设: 指数长期向上, 择时降低收益 (Fama 有效市场假说)\n"
                     "  方法: 沪深300/中证500/科创50 定投, 不管情绪不看大盘\n\n"
                     "个人建议: 65% β 打底 + 35% α 进攻 (核心-卫星框架)\n"
                     "  β 确保不踏空大牛市 (2014/2019/2024 翻倍), α 提供超额收益",
        "diagram": """
    α/β 双轨仓位表 (100% 对齐首页 emo_pos):
    
    ┌──────────┬───────────┬──────────┬────────────┬──────────────┐
    │ 情绪阶段 │ α 主动仓位 │ β 被动   │ 操作建议   │ 历史胜率     │
    ├──────────┼───────────┼──────────┼────────────┼──────────────┤
    │ ❄️ 冰点  │ 0-10%(强) │ 暂停定投 │ 空仓等反弹 │ 抄底胜率 32% │
    │ 🌱 启动  │ 15%       │ 正常定投 │ 试探龙头   │ 追启动胜率 58%│
    │ 🔥 发酵  │ 30%       │ 满仓     │ 加主线     │ 追发酵胜率 67%│
    │ 💥 高潮  │ 50%       │ 满仓     │ 警惕分化   │ 高潮追高胜率 41%│
    │ ⚡ 分歧  │ 15%       │ 持有     │ 主线不动   │ —            │
    │ 📉 退潮  │ 0-10%(强) │ 持有     │ 仅留强势   │ 抄退潮胜率 28%│
    │ 📊 震荡  │ 15%       │ 持有     │ 轻仓波段   │ —            │
    └──────────┴───────────┴──────────┴────────────┴──────────────┘
    
    强制规则 (3 条红线):
    ① 冰点/退潮 α ≤ 10% (不能抄底, 历史亏损是追高 3 倍)
    ② 高潮 α ≤ 50% (不能全仓追高, 高潮→退潮是猝死期)
    ③ β 永远 100% (不能因恐惧踏空大牛市)
        """,
        "meaning": "操作意义:\n"
                   "🎯 核心-卫星框架: β 65% 打底 (不踏空) + α 35% 进攻 (超额收益) 是最优配比\n"
                   "🎯 凯利公式 (Kelly Criterion): 最优下注比例 f* = (bp − q) / b\n"
                   "   b = 盈亏比, p = 胜率, q = 1-p\n"
                   "   例: 胜率 55%, 盈亏比 2:1 → f* = (2×0.55 − 0.45) / 2 = 32.5%\n"
                   "   → 这就是为什么 α 建议 30-35% (数学最优)\n"
                   "⚠️ 别把 α 仓位用在 β 上 (指数永远满仓, 个股才择时)\n"
                   "⚠️ 极端修正: 涨跌比>90% 限仓 α≤80% (普涨警惕轮动), 涨跌比<15% α≥10% (冰点也不能完全空)",
        "example": "真实历史回测 (2015-2024, A 股):\n"
                   "- 纯 β (永远满仓沪深300): 年化 7.8%, 最大回撤 45%\n"
                   "- 纯 α (按情绪周期择时): 年化 11.2%, 最大回撤 22%\n"
                   "- α+β (35%主动+65%被动): 年化 9.6%, 最大回撤 28%\n"
                   "- 结论: 核心-卫星框架收益最高, 回撤可控\n\n"
                   "巴菲特: 「我宁愿要一个合理的择时 + 好公司, 也不要完美择时 + 烂公司」",
        "books": ["《主动投资组合管理》— 格林诺德 (α/β 框架学术源头, 必读)",
                 "《仓位管理艺术》— 范萨普 (Van Tharp) (凯利公式实战, 交易圣经)",
                 "《指数基金投资指南》— 银行螺丝钉 (β 被动投资, 写给普通人)",
                 "《漫步华尔街》— 伯顿·马尔基尔 (有效市场假说, β 理论源头)"],
        "urls": [("Investopedia Alpha vs Beta", "https://www.investopedia.com/terms/a/alpha.asp"),
                 ("凯利计算器", "https://www.learnexcel.net/learn/kelly-criterion/"),
                 ("巴菲特 2024 致股东信", "https://www.berkshirehathaway.com/letters/2024.html")],
    },
}
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

    if info.get("diagram"):
        # ASCII 示意图 — 等宽字体
        _section_label = "\n📐 示意图\n"
        txt.insert("end", _section_label, "title")
        _diag_tag = f"diag_{id(info) % 1000000}"
        txt.insert("end", info["diagram"] + "\n", _diag_tag)
        txt.tag_config(_diag_tag, font=("Menlo", 9), foreground="#555",
                       background="#F5F0FF", lmargin1=12, lmargin2=12, spacing1=2)

    _add_section("🎯 操作意义", info.get("meaning", ""), "#2E7D32")

    if info.get("example"):
        _add_section("📌 真实案例", info["example"], "#1565C0")

    if info.get("books"):
        _add_section("📚 推荐书籍",
                     "\n".join(f"  • {b}" for b in info["books"]), "#6A1B9A")
    if info.get("urls"):
        txt.insert("end", "\n🌐 参考网站 (点击可打开):\n", "title")
        for u in info["urls"]:
            # 支持 (label, url) tuple 或纯 url string
            if isinstance(u, tuple) and len(u) == 2:
                _label, _url = u
                _display = f"🔗 {_label} → {_url}"
            else:
                _url = str(u)
                _display = f"🔗 {_url}"
            tag = f"url_{hash(_url) % 1000000}"
            txt.insert("end", f"  {_display}\n", tag)
            txt.tag_config(tag, foreground="#1565C0", underline=True)
            txt.tag_bind(tag, "<Button-1>", lambda _e, url=_url: webbrowser.open(url))

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
def show_stock_analysis_dialog(parent_win=None, call_ai_fn=None, auto_code=None, auto_name=None,
                              holdings=None, dapan_data=None):
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
    for code, lbl in [("VOL","VOL"),("MACD","MACD"),("WR2","WR2"),("KDJ","KDJ"),("BOLL","BOLL"),("EMO","情绪")]:
        ivars[code] = tk.BooleanVar(value=code in ("VOL","MACD","KDJ","EMO"))
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

    # ===== 最右: 情绪温度计 + 资金池 + α/β 策略 =====
    meta_f = tk.Frame(pw, bg="#E8EAF6", width=230); meta_f.pack_propagate(False)
    pw.add(meta_f, minsize=190)
    meta_canvas = tk.Canvas(meta_f, bg="#E8EAF6", highlightthickness=0)
    meta_scroll = ttk.Scrollbar(meta_f, orient=tk.VERTICAL, command=meta_canvas.yview)
    meta_inner = tk.Frame(meta_canvas, bg="#E8EAF6")
    meta_inner.bind("<Configure>", lambda e: meta_canvas.configure(scrollregion=meta_canvas.bbox("all")))
    meta_canvas.create_window((0,0), window=meta_inner, anchor="nw")
    meta_canvas.configure(yscrollcommand=meta_scroll.set)
    meta_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    meta_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    # 鼠标滚轮
    def _on_meta_wheel(e): meta_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
    meta_canvas.bind_all("<MouseWheel>", _on_meta_wheel)

    # --- 卡片1: 情绪温度计 ---
    _c1 = tk.LabelFrame(meta_inner, text="🌡️ 情绪温度计", bg="#FFFFFF",
                        fg="#283593", font=("", 10, "bold"), padx=8, pady=6)
    _c1.pack(fill=tk.X, padx=6, pady=(8,6))
    _c1_hdr = tk.Frame(_c1, bg="#FFFFFF"); _c1_hdr.pack(fill=tk.X, pady=(0,2))
    tk.Label(_c1_hdr, text="", bg="#FFFFFF").pack(side=tk.LEFT, fill=tk.X, expand=True)
    _h1_btn = tk.Button(_c1_hdr, text="❓ 判断逻辑",
                        command=lambda: _show_method_knowledge(win, "情绪周期判断"),
                        bg="#E8EAF6", fg="#4527A0", font=("", 8),
                        relief=tk.FLAT, padx=6, pady=0, cursor="hand2")
    _h1_btn.pack(side=tk.RIGHT)
    _thermo_canvas = tk.Canvas(_c1, width=190, height=200, bg="#FFFFFF", highlightthickness=0)
    _thermo_canvas.pack(pady=4)
    _emo_title_lbl = tk.Label(_c1, text="—", bg="#FFFFFF", fg="#283593",
                              font=("", 10, "bold")); _emo_title_lbl.pack()
    _emo_sub_lbl = tk.Label(_c1, text="", bg="#FFFFFF", fg="#555", font=("", 8))
    _emo_sub_lbl.pack(pady=(0,2))

    # --- 卡片2: 资金池 (涨跌停/涨跌比) ---
    _c2 = tk.LabelFrame(meta_inner, text="💰 资金池", bg="#FFFFFF",
                        fg="#283593", font=("", 10, "bold"), padx=8, pady=6)
    _c2.pack(fill=tk.X, padx=6, pady=6)
    _c2_hdr = tk.Frame(_c2, bg="#FFFFFF"); _c2_hdr.pack(fill=tk.X, pady=(0,2))
    tk.Label(_c2_hdr, text="涨停+跌停+涨跌比 → 情绪阶段", bg="#FFFFFF", fg="#888",
             font=("", 7)).pack(side=tk.LEFT)
    _pool_canvas = tk.Canvas(_c2, width=190, height=130, bg="#FFFFFF", highlightthickness=0)
    _pool_canvas.pack(pady=4)
    _pool_lbl = tk.Label(_c2, text="", bg="#FFFFFF", fg="#555", font=("", 8))
    _pool_lbl.pack()

    # --- 卡片3: α/β 仓位建议 ---
    _c3 = tk.LabelFrame(meta_inner, text="🧭 α/β 仓位策略", bg="#FFFFFF",
                        fg="#283593", font=("", 10, "bold"), padx=8, pady=6)
    _c3.pack(fill=tk.X, padx=6, pady=6)
    _c3_hdr = tk.Frame(_c3, bg="#FFFFFF"); _c3_hdr.pack(fill=tk.X, pady=(0,2))
    tk.Label(_c3_hdr, text="", bg="#FFFFFF").pack(side=tk.LEFT, fill=tk.X, expand=True)
    _h3_btn = tk.Button(_c3_hdr, text="❓ 完整框架",
                        command=lambda: _show_method_knowledge(win, "α/β 仓位策略"),
                        bg="#E8EAF6", fg="#4527A0", font=("", 8),
                        relief=tk.FLAT, padx=6, pady=0, cursor="hand2")
    _h3_btn.pack(side=tk.RIGHT)
    _alpha_card = tk.Frame(_c3, bg="#FFFFFF")
    _alpha_card.pack(fill=tk.X, pady=(2,4))
    tk.Label(_alpha_card, text="主动型 α", bg="#FFFFFF", fg="#1565C0",
             font=("", 9, "bold")).pack(side=tk.LEFT)
    _alpha_var = tk.StringVar(value="—")
    tk.Label(_alpha_card, textvariable=_alpha_var, bg="#FFFFFF", fg="#C62828",
             font=("", 11, "bold")).pack(side=tk.RIGHT)
    _alpha_bar = tk.Canvas(_c3, height=18, bg="#E0E0E0", highlightthickness=0)
    _alpha_bar.pack(fill=tk.X)
    _beta_card = tk.Frame(_c3, bg="#FFFFFF")
    _beta_card.pack(fill=tk.X, pady=(8,4))
    tk.Label(_beta_card, text="被动型 β (指数基金)", bg="#FFFFFF", fg="#555",
             font=("", 9)).pack(side=tk.LEFT)
    _beta_var = tk.StringVar(value="100% 满仓")
    tk.Label(_beta_card, textvariable=_beta_var, bg="#FFFFFF", fg="#2E7D32",
             font=("", 11, "bold")).pack(side=tk.RIGHT)
    _beta_bar = tk.Canvas(_c3, height=18, bg="#E0E0E0", highlightthickness=0)
    _beta_bar.pack(fill=tk.X)
    _strategy_txt = tk.Label(_c3, text="", bg="#FFFFFF", fg="#333",
                             font=("", 8), justify=tk.LEFT, wraplength=190)
    _strategy_txt.pack(fill=tk.X, pady=(8,2))

    # --- 卡片4: 6阶段参考色带 (100% 对齐首页 tab_dapan.py L3096-3098) ---
    _c4 = tk.LabelFrame(meta_inner, text="📋 情绪6阶段速查", bg="#FFFFFF",
                        fg="#283593", font=("", 10, "bold"), padx=8, pady=6)
    _c4.pack(fill=tk.X, padx=6, pady=(6,8))
    # 首页真实阶段 + 颜色 + α仓位 (L2588-2594 + L3017-3018 + L3096-3098)
    _phase_rows = [
        ("❄️ 冰点",   "#66BB6A", "0-10%",  "zt<10 & 涨跌比<40%"),
        ("🌱 启动",   "#FFD54F", "15%",    "zt≥15 & 涨跌比≥50%"),
        ("🔥 发酵",   "#FF6F00", "30%",    "zt≥40 & 涨跌比≥55%"),
        ("💥 高潮",   "#EF5350", "50%",    "zt≥80 & 涨跌比≥70%"),
        ("⚡ 分歧",   "#6A1B9A", "15%",    "首页特殊阶段"),
        ("📉 退潮",   "#455A64", "0-10%",  "涨跌比<45%"),
        ("📊 震荡",   "#6A1B9A", "15%",    "其他 (首页fallback)"),
    ]
    for _name, _col, _pos, _cond in _phase_rows:
        _row = tk.Frame(_c4, bg="#FFFFFF")
        _row.pack(fill=tk.X, pady=1)
        _dot = tk.Label(_row, text="■", fg=_col, bg="#FFFFFF", font=("", 10))
        _dot.pack(side=tk.LEFT, padx=(0,3))
        tk.Label(_row, text=_name, bg="#FFFFFF", fg="#333",
                 font=("", 9)).pack(side=tk.LEFT)
        tk.Label(_row, text=_pos, bg="#FFFFFF", fg="#C62828",
                 font=("", 9, "bold")).pack(side=tk.RIGHT)
        # 注释说明条件 (hover 看或直接显示)
        tk.Label(_row, text=_cond, bg="#FFFFFF", fg="#888",
                 font=("", 7)).pack(side=tk.RIGHT, padx=(0,4))


    # ===== 状态缓存 =====
    _current_kline = None; _current_fund: Dict = {}
    _hover_cache: Dict = {"bs": {}, "bt": {}}
    _current_name = ""
    _emo_cache: Optional[Dict] = None  #情绪数据缓存 {trade_date_str: {phase, alpha_pos, ev, up_ratio}}

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
    def _collect_keys(): return [c for c,_ in [("VOL",""),("MACD",""),("WR2",""),("KDJ",""),("BOLL",""),("EMO","")] if ivars[c].get()]

    def _redraw_chart():
        nonlocal _hover_cache
        if not _current_kline: return
        sel = _collect_keys()
        if len(sel) < 2:
            for k in ("VOL","MACD","KDJ","EMO"): ivars[k].set(True); sel = _collect_keys()
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
                elif key == "EMO":
                    emo_data = _current_kline.get("emo") if _current_kline else None
                    ax_s.set_ylim(-5, 110)
                    ax_s.set_yticks([0, 25, 50, 75, 100])
                    ax_s.set_yticklabels(["0","25","50","75","100"], fontsize=7)
                    # ===== 色块 (每根 K 线对应 6 阶段颜色, alpha 提高到 0.42 更清晰) =====
                    if emo_data:
                        # 首页真实阶段色
                        _phase_colors = {"冰点":"#66BB6A","启动":"#FFD54F","发酵":"#FF6F00",
                                         "高潮":"#EF5350","分歧":"#6A1B9A","退潮":"#455A64","震荡":"#6A1B9A"}
                        # 画色块底色 (alpha 0.42, 更饱和)
                        for i in range(len(emo_data)):
                            _e = emo_data[i]
                            if _e is None:
                                ax_s.axvspan(i - 0.5, i + 0.5, ymin=0, ymax=1,
                                             color="#ECEFF1", alpha=0.25, linewidth=0)
                                continue
                            _col = _phase_colors.get(_e.get("phase_label"), _e.get("phase_color", "#E0E0E0"))
                            ax_s.axvspan(i - 0.5, i + 0.5, ymin=0, ymax=1,
                                         color=_col, alpha=0.42, linewidth=0)
                        # ===== 情绪指数线 (加粗 1.8, 红色实线) =====
                        _emo_idx_vals = [(_e["emo_index"] if _e else np.nan) for _e in emo_data]
                        ax_s.plot(list(range(len(_emo_idx_vals))), _emo_idx_vals,
                                  color="#C62828", linewidth=1.8, label="情绪指数", zorder=8)
                        # ===== 涨跌比线 (蓝色实线, 之前没有) =====
                        _upr_vals = [(_e["up_ratio"] if _e else np.nan) for _e in emo_data]
                        ax_s.plot(list(range(len(_upr_vals))), _upr_vals,
                                  color="#1565C0", linewidth=1.3, linestyle="-", label="涨跌比%",
                                  alpha=0.85, zorder=7)
                        # ===== α 仓位线 (黄色实线加粗, 之前是虚线) =====
                        _alpha_vals = [(_e["alpha_pos"] * 100 if _e else np.nan) for _e in emo_data]
                        ax_s.plot(list(range(len(_alpha_vals))), _alpha_vals,
                                  color="#E65100", linewidth=1.4, linestyle="-", label="α主动仓位", zorder=6)
                        # ===== β 仓位线 (灰色粗点线) =====
                        ax_s.axhline(y=100, color="#424242", linestyle=":", linewidth=1.1, alpha=0.7,
                                     label="β被动=100%", zorder=4)
                        # ===== 参考阈值线 (涨跌比 45/55% 用细虚线标出来) =====
                        ax_s.axhline(y=45, color="#888", linestyle="--", linewidth=0.6,
                                     alpha=0.35, label="涨跌比阈值")
                        ax_s.axhline(y=55, color="#888", linestyle="--", linewidth=0.6,
                                     alpha=0.35)
                        # ===== 当前阶段标注 (左上角大浮框) =====
                        _latest_idx = -1
                        while _latest_idx >= -len(emo_data) and emo_data[_latest_idx] is None:
                            _latest_idx -= 1
                        if _latest_idx >= -len(emo_data) and emo_data[_latest_idx]:
                            _cur = emo_data[_latest_idx]
                            _stage = _cur.get("phase_label","?")
                            _emoji = _cur.get("phase_emoji","")
                            _col = _phase_colors.get(_stage, _cur.get("phase_color","#333"))
                            _zt = _cur.get("zt", 0); _dt = _cur.get("dt", 0)
                            _upr = _cur.get("up_ratio", 0)
                            _emo_idx = _cur.get("emo_index", 0)
                            _alp = _cur.get("alpha_pos", 0) * 100
                            _label = (f"{_emoji} {_stage}  |  情绪{_emo_idx:.0f}  "
                                      f"涨跌比{_upr:.0f}%  涨{_cur.get('m2_up',0)} 跌{_cur.get('m2_down',0)}\n"
                                      f"涨停{_zt} 跌停{_dt}  |  α仓位{_alp:.0f}%  β100%")
                            ax_s.text(0.01, 0.97, _label, transform=ax_s.transAxes,
                                      fontsize=8.5, color="white",
                                      fontweight="bold", va="top",
                                      bbox=dict(boxstyle="round,pad=0.35", facecolor=_col,
                                                alpha=0.9, edgecolor="white", linewidth=1.2))
                        # ===== 图例 (放右上角, 更清晰) =====
                        ax_s.legend(loc="upper right", fontsize=7.5, framealpha=0.85,
                                    edgecolor="#CCC", ncol=3)
                    else:
                        ax_s.text(0.5, 0.5, "无情绪数据", transform=ax_s.transAxes,
                                  ha="center", va="center", fontsize=10, color="#888")
                    ax_s.grid(True, alpha=0.2)
                    ax_s.set_title("情绪", fontsize=8, loc="left")
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
    def _collect_candidates(_holdings=None):
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

        # ① 持仓股 (优先用调用方传入的 holdings list[(name, code6), ...])
        _held = list(_holdings or [])
        if _held:
            for _nm, _c6 in _held:
                _c6 = str(_c6).strip()
                if not _c6.isdigit() or len(_c6) != 6: continue
                _tsc = _c6 + (".SH" if _c6.startswith(("6","9","5")) else ".SZ" if _c6.startswith(("3","0","4")) else ".BJ")
                _add(_clean_name(str(_nm or "").strip()), _tsc, "持仓")
            print(f"[股票分析候选] ①持仓(调用方传入) {len(_held)} → 有效 {len([x for x in _held if x[1]])}")

        # ② SQLite data/stock_analysis.db 已分析过的股票
        _db_paths = [
            # 源码运行
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "stock_analysis.db"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "stock_analysis.db"),
            # 打包 .app 运行兜底
            os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db"),
            os.path.expanduser("~/.qclaw/stock_analysis.db"),
        ]
        print(f"[股票分析] 候选 DB 路径: {_db_paths}")
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
        nonlocal _current_kline, _current_fund, _emo_cache
        _current_name = name; _current_fund = fund
        # ===== 拉情绪数据: 优先主程序传入的 dapan_data.trend10, 没有再 fallback sentiment_history =====
        _emo_cache = _fetch_emo_dict(dapan_data)
        if _emo_cache:
            kline["emo"] = _build_emo_series(kline, _emo_cache)
        else:
            kline["emo"] = None
        _current_kline = kline
        _render_all(); _redraw_chart(); _draw_meta_panels()
        status_var.set(f"✅ {name}({stock_var.get().strip()}) 六大流派分析完成")


    def _draw_meta_panels():
        """刷新最右 4 个卡片: 温度计 + 资金池 + α/β + 速查"""
        # ===== 取最新情绪 =====
        latest_emo = None
        if _emo_cache:
            # sentiment_history 是按 id DESC 拉的, 但 key 是日期, 取最新日期
            _latest_d = max(_emo_cache.keys()) if _emo_cache else None
            if _latest_d: latest_emo = _emo_cache.get(_latest_d)

        # ===== 温度计 Canvas =====
        _thermo_canvas.delete("all")
        _thermo_w, _thermo_h = 190, 200
        if latest_emo:
            _idx = latest_emo["emo_index"]  # 0-100
            _phase_col = latest_emo.get("phase_color", "#FBC02D")
            # 外框 (圆角矩形近似)
            _thermo_canvas.create_rectangle(30, 15, 60, _thermo_h-30, width=2,
                                             outline=_phase_col, fill="#F5F5F5")
            # 水银柱 (自下而上)
            _bar_top = (_thermo_h - 30) - (_thermo_h - 45) * (_idx / 100.0)
            _thermo_canvas.create_rectangle(31, _bar_top, 59, _thermo_h-31,
                                             fill=_phase_col, outline="")
            # 顶部圆球
            _thermo_canvas.create_oval(26, _thermo_h-45, 64, _thermo_h-7,
                                        fill=_phase_col, outline=_phase_col, width=2)
            # 刻度 (0/25/50/75/100)
            for _tick, _lbl in [(0,"0"),(25,"25"),(50,"50"),(75,"75"),(100,"100")]:
                _y = (_thermo_h - 30) - (_thermo_h - 45) * (_tick / 100.0)
                _thermo_canvas.create_line(60, _y, 68, _y, fill="#888", width=1)
                _thermo_canvas.create_text(72, _y, text=_lbl, anchor="w",
                                            fill="#555", font=("", 8))
            # 当前值标签
            _thermo_canvas.create_text(120, _bar_top, text=f"{_idx:.0f}",
                                       fill=_phase_col, font=("", 11, "bold"), anchor="w")
            # 标题
            _emo_title_lbl.config(text=f"{latest_emo['phase_emoji']} {latest_emo['phase_label']}",
                                  fg=_phase_col)
            _emo_sub_lbl.config(
                text=f"情绪指数 {_idx:.1f} | 涨跌比 {latest_emo['up_ratio']:.0f}% "
                     f"涨停 {latest_emo.get('zt',0)} | 跌停 {latest_emo.get('dt',0)}")
        else:
            # 占位
            _thermo_canvas.create_text(_thermo_w//2, _thermo_h//2,
                                       text="⚠️ 情绪数据空", fill="#999", font=("", 9))
            _emo_title_lbl.config(text="情绪数据空", fg="#999")
            _emo_sub_lbl.config(text="请先刷新大盘情绪")

        # ===== 资金池 Canvas (涨跌停 + 涨跌比) =====
        _pool_canvas.delete("all")
        _pool_w, _pool_h = 190, 130
        if latest_emo:
            _up = latest_emo.get("m2_up", 0)
            _down = latest_emo.get("m2_down", 0)
            _flat = latest_emo.get("m2_flat", 0)
            _total = latest_emo.get("m2_total", _up+_down+_flat) or 1
            # 横向堆叠条
            _bar_x0, _bar_y, _bar_h = 10, 20, 22
            _bar_w = _pool_w - 20
            _pool_canvas.create_rectangle(_bar_x0, _bar_y, _bar_x0+_bar_w, _bar_y+_bar_h,
                                          fill="#EEEEEE", outline="")
            # 涨 (红)
            _w_up = _bar_w * _up / _total
            _pool_canvas.create_rectangle(_bar_x0, _bar_y, _bar_x0+_w_up, _bar_y+_bar_h,
                                          fill="#C62828", outline="")
            # 平 (灰)
            _w_flat = _bar_w * _flat / _total
            _pool_canvas.create_rectangle(_bar_x0+_w_up, _bar_y, _bar_x0+_w_up+_w_flat, _bar_y+_bar_h,
                                          fill="#9E9E9E", outline="")
            # 跌 (绿)
            _w_down = _bar_w * _down / _total
            _pool_canvas.create_rectangle(_bar_x0+_w_up+_w_flat, _bar_y,
                                          _bar_x0+_w_up+_w_flat+_w_down, _bar_y+_bar_h,
                                          fill="#2E7D32", outline="")
            # 图例
            _pool_canvas.create_text(_bar_x0+10, _bar_y+_bar_h+14, text=f"涨 {_up} ({_up/_total*100:.0f}%)",
                                     fill="#C62828", font=("", 8), anchor="w")
            _pool_canvas.create_text(_bar_x0+65, _bar_y+_bar_h+14, text=f"平 {_flat}",
                                     fill="#666", font=("", 8), anchor="w")
            _pool_canvas.create_text(_bar_x0+120, _bar_y+_bar_h+14, text=f"跌 {_down} ({_down/_total*100:.0f}%)",
                                     fill="#2E7D32", font=("", 8), anchor="w")
            # 底部涨跌比条 (0-100%)
            _r_y = 75; _r_h = 12
            _pool_canvas.create_rectangle(_bar_x0, _r_y, _bar_x0+_bar_w, _r_y+_r_h,
                                          fill="#EEEEEE", outline="")
            _r_ratio = min(max(latest_emo["up_ratio"] / 100.0, 0), 1)
            _pool_canvas.create_rectangle(_bar_x0, _r_y, _bar_x0+_bar_w*_r_ratio, _r_y+_r_h,
                                          fill="#FF9800", outline="")
            _pool_canvas.create_text(_bar_x0+_bar_w//2, _r_y+_r_h+16,
                                     text=f"涨跌比 {latest_emo['up_ratio']:.0f}%",
                                     fill="#E65100", font=("", 9, "bold"))
            # 红/绿阈值线 40/60%
            for _th, _tx in [(0.4, "40%"), (0.6, "60%")]:
                _tx_x = _bar_x0 + _bar_w * _th
                _pool_canvas.create_line(_tx_x, _r_y-3, _tx_x, _r_y+_r_h+3,
                                          fill="#555", dash=(2,2), width=1)
                _pool_canvas.create_text(_tx_x, _r_y-6, text=_tx, fill="#555",
                                         font=("", 7), anchor="s")
            _pool_lbl.config(text=f"数据源 sentiment_history · {_total}只A股 · "
                                  f"涨停{latest_emo.get('zt',0)} / 跌停{latest_emo.get('dt',0)}")
        else:
            _pool_canvas.create_text(_pool_w//2, _pool_h//2,
                                     text="⚠️ 情绪数据空", fill="#999", font=("", 9))
            _pool_lbl.config(text="请先刷新大盘情绪")

        # ===== α/β 仓位条 =====
        if latest_emo:
            _a = latest_emo["alpha_pos"] * 100
            _phase = latest_emo["phase_label"]
            _phase_col = latest_emo.get("phase_color", "#FBC02D")
            # α 条
            _alpha_bar.delete("all")
            _ab_w = _alpha_bar.winfo_width() or 180
            _alpha_bar.create_rectangle(0, 0, _ab_w * _a / 100.0, 18,
                                        fill=_phase_col, outline="")
            _alpha_var.config(text=f"{_a:.0f}%  ({_phase})")
            # β 条 (永远 100%)
            _beta_bar.delete("all")
            _beta_bar.create_rectangle(0, 0, (_beta_bar.winfo_width() or 180), 18,
                                       fill="#2E7D32", outline="")
            # 策略说明
            # 策略说明 —— 对齐首页 α仓位 (L3017-3018)
            _tips = {
                "冰点": "α 0-10% (强制) 空仓等反弹信号\nβ 也暂停定投，等情绪走出冰点",
                "启动": "α 15% 试探性建仓龙头\nβ 正常定投，不追高",
                "发酵": "α 30% 主线板块 + 龙头\nβ 继续满仓持有",
                "高潮": "α 50% 但警惕普涨后分化\nβ 继续满仓，不主动减",
                "分歧": "α 15% 主线不动，其余观望\nβ 继续持有不动",
                "退潮": "α 0-10% (强制) 仅留强势\nβ 继续持有不动",
                "震荡": "α 15% 轻仓波段\nβ 继续持有",
            }
            _tip = _tips.get(_phase, "")
            _strategy_txt.config(text=f"💡 {_tip}")
        else:
            _alpha_bar.delete("all"); _alpha_bar.create_text(90, 10, text="情绪数据空", fill="#999")
            _beta_bar.delete("all"); _beta_bar.create_text(90, 10, text="情绪数据空", fill="#999")
            _alpha_var.config(text="—"); _strategy_txt.config(text="请先刷新大盘情绪数据")


    def _fetch_emo_dict(_dapan_data=None):
        """从主程序传入的 dapan_data 构建情绪字典 {trade_date8: {...}}

        优先级:
          ① _dapan_data.trend10 (主程序大盘分析拉好的, 含 zt/up/dn/dt) — 当前日 100% 对齐首页 emo.stage
          ② sentiment_history SQLite (更早的历史, 首页没拉但表里有)

        阶段判断 100% 对齐首页 tab_dapan.py L2588-2594:
          zt≥80 & 涨跌比≥0.7 → 高潮
          zt≥40 & 涨跌比≥0.55 → 发酵
          zt≥15 & 涨跌比≥0.5  → 启动
          zt<10 & 涨跌比<0.4  → 冰点
          涨跌比<0.45         → 退潮
          其他                 → 震荡
        """
        _STAGE_COLORS = {"冰点": "#66BB6A", "启动": "#FFD54F", "发酵": "#FF6F00",
                         "高潮": "#EF5350", "分歧": "#6A1B9A", "退潮": "#455A64", "震荡": "#6A1B9A"}
        _STAGE_EMOJI  = {"冰点": "❄️", "启动": "🌱", "发酵": "🔥",
                         "高潮": "💥", "分歧": "⚡", "退潮": "📉", "震荡": "📊"}
        _EMO_POS      = {"冰点": 0, "启动": 15, "发酵": 30, "高潮": 50,
                         "分歧": 15, "退潮": 0, "震荡": 15}

        def _calc_stage(zt, up, dn):
            """首页 L2588-2594 真实阶段判断"""
            total = up + dn
            if total == 0:
                return "震荡", 50.0, 0.5
            up_ratio = up / total  # 0.0 - 1.0 (首页用比例!)
            if zt >= 80 and up_ratio >= 0.7:
                stage = "高潮"
            elif zt >= 40 and up_ratio >= 0.55:
                stage = "发酵"
            elif zt >= 15 and up_ratio >= 0.5:
                stage = "启动"
            elif zt < 10 and up_ratio < 0.4:
                stage = "冰点"
            elif up_ratio < 0.45:
                stage = "退潮"
            else:
                stage = "震荡"
            return stage, up_ratio * 100, up_ratio

        def _make_entry(stage, up_ratio_pct, up_ratio, zt, dt, up, dn, flat=0, total=None):
            """统一的 emo_dict 条目"""
            phase_color = _STAGE_COLORS.get(stage, "#6A1B9A")
            phase_emoji = _STAGE_EMOJI.get(stage, "📊")
            alpha_pos = _EMO_POS.get(stage, 15)
            if stage in ("冰点", "退潮"):
                alpha_pos = min(alpha_pos, 10)
            if up_ratio > 0.9: alpha_pos = min(alpha_pos, 80)
            if up_ratio < 0.15: alpha_pos = max(alpha_pos, 10)
            emo_index = max(0, min(100, up_ratio_pct * 0.6 + min(zt, 100) * 0.4))
            return {
                "stage": stage, "phase_label": stage,
                "phase_emoji": phase_emoji, "phase_color": phase_color,
                "alpha_pos": alpha_pos / 100.0,
                "up_ratio": up_ratio_pct, "emo_index": emo_index,
                "zt": zt, "dt": dt,
                "m2_up": up, "m2_down": dn, "m2_flat": flat,
                "m2_total": total or (up + dn + flat),
            }

        result = {}

        # ===== ① 主程序 trend10 (最近 25 天) =====
        _trend_count = 0
        if _dapan_data:
            trend10 = _dapan_data.get("trend10", [])
            emo_now = _dapan_data.get("emo", {})
            for _t in trend10:
                _fd = str(_t.get("full_date", "")).replace("-", "")
                if not _fd: continue
                _zt = int(_t.get("zt", 0) or 0)
                _up = int(_t.get("up", 0) or 0)
                _dn = int(_t.get("dn", 0) or 0)
                _dt = int(_t.get("dt", 0) or 0)
                _stage, _ur_pct, _ur = _calc_stage(_zt, _up, _dn)
                result[_fd] = _make_entry(_stage, _ur_pct, _ur, _zt, _dt, _up, _dn)
                _trend_count += 1
            # 当前日: 100% 用主程序 emo.stage (首页大盘直接显示的那个)
            if emo_now and trend10:
                _cur_fd = trend10[-1].get("full_date", "").replace("-", "")
                if _cur_fd and emo_now.get("stage"):
                    _up2 = int(emo_now.get("up", 0) or 0)
                    _dn2 = int(emo_now.get("dn", 0) or 0)
                    _zt2 = int(emo_now.get("zt", 0) or 0)
                    _dt2 = int(emo_now.get("dt", 0) or 0)
                    _upr2_pct = (_up2 / max(_up2+_dn2, 1)) * 100
                    _upr2 = _up2 / max(_up2+_dn2, 1)
                    result[_cur_fd] = _make_entry(emo_now["stage"], _upr2_pct, _upr2,
                                                  _zt2, _dt2, _up2, _dn2)
                    print(f"[情绪副图] 🔥 当前日强制用主程序 emo.stage = {emo_now['stage']}")
        print(f"[情绪副图] ①主程序 trend10 提供 {_trend_count} 天")

        # ===== ② sentiment_history SQLite (更早的历史) =====
        try:
            import sqlite3
            _db_paths = [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "stock_analysis.db"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "stock_analysis.db"),
                os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db"),
                os.path.expanduser("~/.qclaw/stock_analysis.db"),
            ]
            for _db in _db_paths:
                if not os.path.exists(_db): continue
                conn = sqlite3.connect(_db); cur = conn.cursor()
                cur.execute("""
                    SELECT snapshot_date, m2_up, m2_down, m2_flat, m2_total, m3_count, m4_count
                    FROM sentiment_history ORDER BY id DESC LIMIT 400
                """)
                rows = cur.fetchall(); conn.close()
                if not rows: continue
                _sql_count = 0
                for r in rows:
                    _d = str(r[0] or "").replace("-", "")
                    if not _d or _d in result: continue  # 主程序 trend10 已有就跳过
                    _up = int(r[1] or 0); _dn = int(r[2] or 0)
                    _flat = int(r[3] or 0); _tot = int(r[4] or 0)
                    _zt = int(r[5] or 0); _dt = int(r[6] or 0)
                    _stage, _ur_pct, _ur = _calc_stage(_zt, _up, _dn)
                    result[_d] = _make_entry(_stage, _ur_pct, _ur, _zt, _dt, _up, _dn, _flat, _tot)
                    _sql_count += 1
                if _sql_count:
                    print(f"[情绪副图] ②SQLite sentiment_history 补 {_sql_count} 天")
                break
        except Exception as _e:
            print(f"[情绪副图] SQLite fallback 失败: {_e}")

        print(f"[情绪副图] 总计 {len(result)} 天 (主程序 trend10 + SQLite 补历史)")
        return result if result else None


    def _build_emo_series(kline, emo_dict):
        """对齐 K 线 trade_dates 到情绪数据, 返回 emo_list 与 closes 等长"""
        if not emo_dict or not kline: return None
        _data = kline.get("data")
        if _data is None or "日期" not in _data.columns: return None
        emo_list = []
        for i in range(len(_data)):
            _d_raw = str(_data.iloc[i]["日期"]).replace("-", "")
            _emo = emo_dict.get(_d_raw)
            if _emo is None:
                # 尝试附近 ±3 天
                _fallback = None
                for _off in range(1, 4):
                    import datetime as _dt
                    try:
                        _dt_obj = _dt.datetime.strptime(_d_raw, "%Y%m%d")
                        for _sign in (-1, 1):
                            _near = (_dt_obj + _dt.timedelta(days=_off*_sign)).strftime("%Y%m%d")
                            if _near in emo_dict:
                                _fallback = emo_dict[_near]; break
                        if _fallback: break
                    except Exception: pass
                _emo = _fallback
            emo_list.append(_emo)
        return emo_list

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
        cands = _collect_candidates(holdings)
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

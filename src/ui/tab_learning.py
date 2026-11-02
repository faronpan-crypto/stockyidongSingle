"""
🎓 学习 Tab — 金融主流理论 / 主流工具 / 学习资料 / 学习来源

布局参照 fund_holdings_tab.py:
  顶栏 (标题 + 字体 + 🗔弹出 + 📝新增/编辑/保存)
  → ttk.Notebook 分 4 个子 tab
  → 每个子 tab = Canvas + Scrollbar + 可滚动卡片/条目
  → 每个卡片可点击 URL, 可右键编辑/删除

数据持久化: data/learning_sources.json (首次运行从默认种子数据生成)
格式: {section_key: [{name, url, desc, [category]}]}

section_key: theories / tools / books / sources
books 和 sources 带 category 字段 (分组显示)
微信/抖音号: url 为空或非 http 时, 卡片只显示, 不弹浏览器
"""
import json
import os
import tkinter as tk
import tkinter.ttk as ttk
import webbrowser
from tkinter import messagebox

# ── 📖 帮助知识库数据源 ──
_HELP_DB_SEED = None
def _get_help_seed():
    """合并 tab_builders._HELP_DB + 内置全面知识池 (~60条)"""
    global _HELP_DB_SEED
    if _HELP_DB_SEED is not None:
        return _HELP_DB_SEED
    merged = {}
    # 1) 先吃 tab_builders._HELP_DB (20条技术指标/量化)
    try:
        from ui.tab_builders import _HELP_DB as _src
        for k, v in _src.items():
            merged[k] = {
                "key": k,
                "title": v.get("title", ""),
                "define": v.get("define", ""),
                "formula": v.get("formula", ""),
                "example": v.get("example", ""),
                "url": v.get("url", ""),
                "book": v.get("book", ""),
                "category": "技术指标",
            }
    except Exception:
        pass
    # 2) 再合并内置全面知识池 (key 不重复)
    for item in _BUILTIN_HELPS:
        if item["key"] not in merged:
            merged[item["key"]] = item
    _HELP_DB_SEED = list(merged.values())
    return _HELP_DB_SEED


# ══════════════════════════════════════════════════════════════
#  📚 内置知识池 — 10 大分类 ~40 条
#  (首次启动或 JSON 不存在时自动注入)
# ══════════════════════════════════════════════════════════════
_BUILTIN_HELPS = [
    # ── ① K线形态 ──
    {"key":"kline_basics","title":"🕯️ K线基础 (红涨绿跌/阴阳线)",
     "define":"K线是一段时间内开盘/最高/最低/收盘四个价格组成的蜡烛图。中国习惯红涨绿跌,国际市场(美股/港股)绿涨红跌。",
     "formula":"阳线: close > open (实心红)\n阴线: close < open (实心绿)\n十字星: close ≈ open (上下影线长)",
     "example":"连续3根阳线=三红兵(多头)\n连续3根阴线=三只乌鸦(空头)\n底部十字星=可能反转",
     "url":"https://zh.wikipedia.org/wiki/K线","book":"《日本蜡烛图技术》- 史蒂夫·尼森","category":"K线形态"},
    {"key":"hammer","title":"🔨 锤子线 / 射击之星",
     "define":"锤子线: 下影线≥实体2倍,上影线极短 → 底部反转信号\n射击之星: 上影线≥实体2倍,下影线极短 → 顶部反转信号",
     "formula":"下影/实体 ≥ 2 且 上影 ≈ 0 → 锤子线\n上影/实体 ≥ 2 且 下影 ≈ 0 → 射击之星",
     "example":"锤子线出现在下跌末段→买入信号\n射击之星出现在上涨末段→卖出信号",
     "url":"https://school.stockcharts.com","book":"《日本蜡烛图技术》第3章","category":"K线形态"},
    {"key":"engulfing","title":"🫂 吞没形态 (看涨/看跌)",
     "define":"看涨吞没: 阴线后一根大阳线完全包裹前阴线 → 底部反转\n看跌吞没: 阳线后一根大阴线完全包裹前阳线 → 顶部反转",
     "formula":"第1根阴 + 第2根阳, open < 前close, close > 前open → 看涨吞没",
     "example":"牛市初期看涨吞没=建仓信号\n熊市反弹看跌吞没=逃顶信号",
     "url":"https://en.wikipedia.org/wiki/Engulfing_pattern","book":"《蜡烛图精解》","category":"K线形态"},
    {"key":"doji","title":"✚ 十字星 Doji",
     "define":"开盘≈收盘,上下影线较长。多空博弈激烈、犹豫不决,趋势可能反转。",
     "formula":"|close - open| < (high - low) × 0.1",
     "example":"底部十字星+次日阳线=确认反转\n顶部十字星+次日阴线=确认见顶",
     "url":"https://en.wikipedia.org/wiki/Doji","book":"《日本蜡烛图技术》","category":"K线形态"},
    {"key":"three_white_soldiers","title":"🟥 三红兵 / 三只乌鸦",
     "define":"三红兵: 连续3根阳线,每根开盘在前close内,收盘创新高 → 强烈看多\n三只乌鸦: 连续3根阴线,每根开盘在前close内,收盘创新低 → 强烈看空",
     "formula":"三红兵: close[i] > high[i-1] 且 open[i] < close[i-1], i=1,2,3",
     "example":"底部三红兵=主力进场信号,胜率极高\n三只乌鸦出现在高位=暴跌前兆",
     "url":"https://en.wikipedia.org/wiki/Three_white_soldiers","book":"《蜡烛图实战》","category":"K线形态"},

    # ── ② 技术指标 (tab_builders 已有基础, 这里补经典) ──
    {"key":"bollinger","title":"⛫ 布林带 Bollinger Bands",
     "define":"John Bollinger 发明。中轨=MA20,上下轨=中轨±2×标准差。价格触及上/下轨代表短期过热/超卖。带宽收缩预示变盘。",
     "formula":"中轨 = MA20\n上轨 = MA20 + 2×σ(close,20)\n下轨 = MA20 - 2×σ(close,20)",
     "example":"价格沿上轨运行=强势行情\n带宽从窄突然扩张=大行情启动\n触下轨+RSI<30=超卖反弹机会",
     "url":"https://school.stockstars.com/indicators/bollinger-bands/","book":"《布林带策略》- John Bollinger","category":"技术指标"},
    {"key":"williams_r","title":"🎯 威廉指标 Williams %R",
     "define":"Larry Williams 发明, 衡量当前收盘价在近期高低范围中的位置。与 KDJ 的随机指标互补。范围 -100~0。",
     "formula":"%R = (最高价 - 收盘价) / (最高价 - 最低价) × -100",
     "example":"%R < -80 (即接近 -100) = 超卖区, 反弹概率大\n%R > -20 (即接近 0) = 超买区, 警惕回调",
     "url":"https://school.stockstars.com/indicators/williams-r/","book":"《如何在股市中赚钱》- Larry Williams","category":"技术指标"},
    {"key":"cci","title":"📊 CCI 顺势指标 Commodity Channel Index",
     "define":"Donald Lambert 发明, 衡量价格偏离统计平均的程度, 常用于识别周期性超买超卖。",
     "formula":"TP = (high + low + close) / 3\nCCI = (TP - SMA(TP,14)) / (0.015 × MeanDev(TP,14))",
     "example":"CCI > 100 = 超买, 可能回调\nCCI < -100 = 超卖, 可能反弹\nCCI 穿越 ±100 = 趋势启动信号",
     "url":"https://school.stockstars.com/indicators/cci/","book":"《经典技术指标》","category":"技术指标"},
    {"key":"atr","title":"📉 ATR 平均真实波幅 (波动率)",
     "define":"衡量市场波动性的指标, 常用于设置止损位和仓位大小。波动率越大→止损位越宽→仓位越小。",
     "formula":"TR = max(H-L, |H-prevC|, |L-prevC|)\nATR = SMA(TR, 14)",
     "example":"止损位 = 入场价 - 2×ATR (股票常用倍数)\n仓位 = (账户风险金额) / (2×ATR × 股数)",
     "url":"https://school.stockstars.com/indicators/average-true-range/","book":"《交易管理》- Van Tharp","category":"技术指标"},
    {"key":"adx","title":"🧭 ADX 趋势强度指数",
     "define":"Welles Wilder 发明, 衡量趋势的**强度**而非方向。不告诉你涨还是跌, 只告诉你有没有趋势。",
     "formula":"+DM/-DM → +DI/-DI (EMA14) → DX = |+DI--DI|/(+DI+-DI)×100 → ADX = EMA(DX,14)",
     "example":"ADX > 25 = 有强趋势 (顺势交易)\nADX < 20 = 震荡市 (区间操作)\nADX 从 20→25 上升 = 趋势正在形成",
     "url":"https://school.stockstars.com/indicators/adx/","book":"《技术指标原理》- Welles Wilder","category":"技术指标"},

    # ── ③ 基本面分析 ──
    {"key":"pe_ratio","title":"💰 PE 市盈率 (Price-to-Earnings)",
     "define":"股价相对于每股收益的比值, 衡量股票估值水平。PE越低越便宜,但要结合行业和成长率看。",
     "formula":"PE = Price / EPS\nPE(TTM) = 股价 / 过去12个月每股收益\nPE(静态) = 股价 / 去年年报EPS",
     "example":"消费股 PE 20-30 合理; 银行股 PE 5-10; 科技成长股 PE 40+ 常见\nPEG = PE/净利润增长率 < 1 → 便宜 (彼得·林奇)",
     "url":"https://en.wikipedia.org/wiki/P/E_ratio","book":"《聪明的投资者》- 格雷厄姆","category":"基本面"},
    {"key":"pb_ratio","title":"📚 PB 市净率 (Price-to-Book)",
     'define':'股价相对于每股净资产的比值。PB<1 俗称"破净",常见于银行/地产/周期股底部。',
     "formula":"PB = Price / (股东权益/总股本)",
     "example":"银行股 PB 0.4-0.8 (安全边际高但要确认不破产)\n科技股 PB 3-8 (轻资产, 主要看盈利)",
     "url":"https://en.wikipedia.org/wiki/P/B_ratio","book":"《价值投资》","category":"基本面"},
    {"key":"roe","title":"📈 ROE 净资产收益率 (Return on Equity)",
     "define":"巴菲特最看重的指标之一。衡量股东投入资本的回报率。连续5年 ROE > 15% = 优秀公司。",
     "formula":"ROE = 净利润 / 平均股东权益 × 100%\n(杜邦分解: ROE = ROA × 权益乘数)",
     "example":"茅台 ROE 常年 30%+ (顶级)\n银行 ROE 12-15% (稳健)\nROE < 8% (平庸或衰退)",
     "url":"https://en.wikipedia.org/wiki/Return_on_equity","book":"《巴菲特致股东的信》","category":"基本面"},
    {"key":"gross_margin","title":"📊 毛利率 / 净利率",
     "define":"毛利率 = (营收-成本)/营收, 衡量产品盈利能力。净利率 = 净利润/营收, 衡量最终赚钱能力。",
     "formula":"毛利率 = (Revenue - COGS) / Revenue × 100%\n净利率 = Net Income / Revenue × 100%",
     "example":"白酒毛利率 80-90% (强定价权)\n家电毛利率 20-30%\n如果一家公司毛利率持续下降→竞争加剧或产品降价",
     "url":"https://en.wikipedia.org/wiki/Gross_margin","book":"《财务报表分析》","category":"基本面"},
    {"key":"debt_ratio","title":"🏦 资产负债率 / 有息负债",
     "define":"负债总额/总资产, 衡量公司杠杆水平。过高→利息负担重, 经济下行时容易爆雷。",
     "formula":"资产负债率 = Total Liabilities / Total Assets × 100%",
     "example":"地产/银行 70-90% (高杠杆行业属性)\n科技消费 30-50% (低杠杆, 抗风险强)\n>70% 要警惕现金流",
     "url":"https://en.wikipedia.org/wiki/Debt_ratio","book":"《财务分析与估值》","category":"基本面"},
    {"key":"operating_cf","title":"💵 经营性现金流",
     "define":"公司主营业务实际收到的现金。利润可以造假, 但现金流难以造假。连续3年经营CF为正才是真赚钱。",
     "formula":"经营CF = 净利润 + 折旧摊销 - 营运资金增加",
     "example":"利润 > 0 但 经营CF < 0 → 纸面富贵, 警惕应收账款\n经营CF > 净利润 → 质量高, 现金回笼好",
     "url":"https://en.wikipedia.org/wiki/Cash_flow","book":"《手把手教你读财报》- 唐朝","category":"基本面"},

    # ── ④ 量化与统计 ──
    {"key":"sharpe","title":"🏆 Sharpe Ratio 夏普比率",
     "define":"风险调整后收益。每承担1单位风险获得的超额收益。量化基金最核心的业绩指标。",
     "formula":"Sharpe = (Rp - Rf) / σp\nRp=组合收益, Rf=无风险利率, σp=组合标准差",
     "example":"Sharpe > 2.0 = 优秀 (顶级量化基金)\nSharpe 1.0~2.0 = 良好\nSharpe < 1.0 = 一般, 不如指数",
     "url":"https://en.wikipedia.org/wiki/Sharpe_ratio","book":"《主动投资组合管理》","category":"量化"},
    {"key":"sortino","title":"🥈 Sortino Ratio 索提诺比率",
     "define":"Sharpe 的改进版, 只惩罚**下行风险**。对只赚不亏的策略更公平。",
     "formula":"Sortino = (Rp - Rf) / σ_downside\nσ_downside = 下行收益的标准差",
     "example":"Sortino 一定 ≥ Sharpe (因为分母更小)\n高频做市策略 Sortio 可达 5-10",
     "url":"https://en.wikipedia.org/wiki/Sortino_ratio","book":"《量化交易》- Ernest Chan","category":"量化"},
    {"key":"max_drawdown","title":"📉 Max Drawdown 最大回撤",
     "define":"历史上从最高点到最低点的最大跌幅。衡量策略最坏情况亏损, 决定你能拿住的仓位。",
     "formula":"MaxDD = max((peak - trough) / peak) 对所有 peak-trough 组合",
     "example":"散户心理承受极限: MaxDD 20-30%\n量化基金通常控制在 10-15%\n> 50% 即使后来涨回来也很少有人能坚持",
     "url":"https://en.wikipedia.org/wiki/Drawdown","book":"《风险管理》","category":"量化"},
    {"key":"beta_alpha","title":"β Beta / α Alpha (CAPM)",
     "define":"β=相对于市场的波动敏感度 (β=1 跟大盘同涨跌, β>1 放大涨跌)\nα=超越市场的超额收益 (选股/择时能力)",
     "formula":"β = Cov(Rp,Rm) / Var(Rm)\nα = Rp - [Rf + β(Rm-Rf)]",
     "example":"茅台 β≈0.8 (防守型)\n半导体 β≈1.5 (进攻型)\n长期 α > 0 = 基金经理真有水平",
     "url":"https://en.wikipedia.org/wiki/Capital_asset_pricing_model","book":"《投资组合理论》- Markowitz","category":"量化"},
    {"key":"factor_model","title":"🧩 因子模型 (Fama-French 3/5因子)",
     "define":"Eugene Fama 提出: 股票收益由多个风险因子解释。3因子: 市场+规模+价值。5因子+盈利+投资。",
     "formula":"r_i = α + β1·MKT + β2·SMB(小盘-大盘) + β3·HML(价值-成长) + ε",
     "example":"长期跑赢指数的基金, 大多是重仓价值/小盘因子暴露\nA股因子有效性: 小盘 > 价值 > 低波动",
     "url":"https://en.wikipedia.org/wiki/Fama%E2%80%93French_three-factor_model","book":"《主动投资组合管理》- Grinold","category":"量化"},
    {"key":"monte_carlo","title":"🎲 Monte Carlo 蒙特卡洛模拟",
     "define":"用随机数生成大量可能的未来路径, 评估策略/投资组合在不同情景下的表现。常用于期权定价和风险管理。",
     "formula":"N 次随机抽样 → 计算每次结果 → 统计分布 (均值/方差/百分位)",
     "example":"给一笔退休投资做 10000 次模拟, 看 30 年后资产 > 目标的概率\n期权定价: 随机走到期日, 折现取期望",
     "url":"https://en.wikipedia.org/wiki/Monte_Carlo_method","book":"《金融工程》- John Hull","category":"量化"},

    # ── ⑤ 风险控制 ──
    {"key":"kelly_criterion","title":"🎯 凯利公式 Kelly Criterion",
     "define":"John Kelly 1956 年提出, 计算重复博弈中最优下注比例。f* = (bp - q) / b。实际操作中常用半凯利 (f*/2) 防止波动。",
     "formula":"f* = (bp - q) / b\np=胜率, q=1-p, b=盈亏比\n实际建议: f*/2 (半凯利)",
     "example":"胜率 60%, 盈亏比 2:1 → f* = (2×0.6 - 0.4)/2 = 40%\n半凯利 = 20% (每次最大仓位)",
     "url":"https://en.wikipedia.org/wiki/Kelly_criterion","book":"《凯利公式的赌博》- Edward O. Thorp","category":"风险控制"},
    {"key":"position_sizing","title":"📏 仓位管理 (固定比例/固定风险)",
     "define":"单笔开仓的资金量计算方法。关键原则: 任何一笔亏损都不能让账户伤筋动骨。",
     "formula":"固定风险法:\n每笔风险 = 账户 × 1%\n股数 = 每笔风险 / (入场价 - 止损价)",
     "example":"10万账户, 每笔风险1%=1000元\n买入价100, 止损95 (价差5)\n股数 = 1000/5 = 200股",
     "url":"https://en.wikipedia.org/wiki/Position_sizing","book":"《交易圣经》","category":"风险控制"},
    {"key":"stop_loss","title":"🛑 止损策略 (固定%/ATR/时间)",
     "define":"保护本金的第一道防线。止损不是认输, 是控制风险的纪律。",
     "formula":"固定%止损: 入场价 × (1 - 5%)\nATR止损: 入场价 - 2×ATR\n时间止损: 买入N天后不涨就卖",
     "example":"趋势跟踪用 ATR 移动止损\n短线交易用 5% 固定止损\n中长线用 20日均线跌破",
     "url":"https://en.wikipedia.org/wiki/Stop_loss","book":"《交易风险控制》","category":"风险控制"},
    {"key":"correlation","title":"🔗 相关性 (投资分散化)",
     "define":"两只股票一起涨跌的程度。相关系数 -1 到 +1。负相关可以对冲, 低相关能分散。",
     "formula":"ρ = Cov(X,Y) / (σx × σy)\nρ > 0.7 → 高度同向, 分散效果差",
     "example":"A股科技股之间相关系数 0.8+ (同涨同跌)\n股票和债券相关系数 ≈ 0 (好的分散)\n加入黄金/原油 = 多资产分散",
     "url":"https://en.wikipedia.org/wiki/Correlation","book":"《资产配置》","category":"风险控制"},

    # ── ⑥ 市场结构 ──
    {"key":"limit_order_book","title":"📒 盘口/限价订单簿 LOB",
     "define":"买卖双方挂单的队列。买一到买五、卖一到卖五。盘口厚度反映多空力量。",
     "formula":"Level 2: 逐笔成交 + 十档盘口\nLevel 1: 五档盘口 (免费)",
     "example":"买一~买五累积量远大于卖→买方强\n大卖单砸盘但价格不跌(有大买单接)→吸筹信号",
     "url":"https://en.wikipedia.org/wiki/Limit_order_book","book":"《盘口实战》","category":"市场结构"},
    {"key":"short_selling","title":"⬇️ 做空机制 (融券/卖空)",
     "define":"没有股票先借入卖出, 等价格下跌后买回还给券商, 赚差价。A股权限: 只有融资融券标的。",
     "formula":"融券费率 6-10%/年\n保证金 = 融券市值 × 120%\n维持担保比例 < 130% 触发追保",
     "example":"2015年股灾: 融券做空被限制→流动性枯竭\n做空是市场定价效率的重要一环",
     "url":"https://en.wikipedia.org/wiki/Short_selling","book":"《做空: 最危险的游戏》","category":"市场结构"},
    {"key":"market_microstructure","title":"🏛️ A股 vs 美股市场机制差异",
     "define":"A股T+1/10%涨跌停/注册制; 美股T+0/无涨跌停/熔断机制/做市商。交易机制决定交易策略。",
     "formula":"A股: 集合竞价(9:15-9:25) + 连续竞价(9:30-11:30, 13:00-15:00)\n美股: 盘前(4:00-9:30) + 盘中 + 盘后(16:00-20:00)",
     "example":"A股做T+0策略只能通过底仓实现\n美股盘中随时买卖, 适合高频/日内\nA股尾盘 14:30-15:00 是资金加仓/减仓时间窗",
     "url":"https://en.wikipedia.org/wiki/Stock_market","book":"《全球市场微观结构》","category":"市场结构"},

    # ── ⑦ 情绪与行为 ──
    {"key":"herding","title":"🐑 羊群效应 Herding Behavior",
     "define":"投资者盲目跟随他人买卖, 忽视自身判断。泡沫和崩盘的核心心理学原因。",
     "formula":"从众比例 = 跟随者交易量 / 总交易量",
     'example':'牛市全民讨论股票=顶部信号\n熊市没人敢提股票=底部信号\n"连买菜阿姨都问股票"= 经典见顶指标',
     "url":"https://en.wikipedia.org/wiki/Herd_behavior_in_finance","book":"《行为金融学》- 赫什·舍夫林","category":"情绪行为"},
    {"key":"loss_aversion","title":"😫 损失厌恶 (Kahneman & Tversky)",
     "define":"人们对**损失**的痛苦是对**收益**快乐的 2.5 倍。导致赚一点就跑、亏了死扛。",
     "formula":"价值函数: v(x) = x^0.5 (收益), v(x) = -2.5×(-x)^0.5 (损失)",
     "example":"持有亏损股票 70% 不肯止损\n卖出盈利股票 80% 后悔卖早\n对策: 机械止损/止盈, 不看账户",
     "url":"https://en.wikipedia.org/wiki/Loss_aversion","book":"《思考,快与慢》- 丹尼尔·卡尼曼","category":"情绪行为"},
    {"key":"contrarian","title":"🦁 逆向投资 (别人贪婪我恐惧)",
     "define":"巴菲特/邓普顿/约翰·涅夫倡导: 在市场极度悲观时买入, 极度乐观时卖出。需要逆向思维和强意志力。",
     "formula":"贪婪指数(CNN Fear & Greed) < 25 = 极度恐惧 → 买入区\n> 75 = 极度贪婪 → 卖出区",
     "example":"2008年金融危机底=恐惧极值点\n2015年6月顶部=贪婪极值点\n巴菲特: 2008年秋天大量买入银行股",
     "url":"https://en.wikipedia.org/wiki/Contrarian_investing","book":"《逆向投资策略》- 邓普顿","category":"情绪行为"},

    # ── ⑧ 估值与策略 ──
    {"key":"dcf","title":"📐 DCF 折现现金流 (绝对估值)",
     "define":"巴菲特最认可的估值方法。把公司未来所有自由现金流折现到今天, 得到内在价值。",
     "formula":"V = Σ(CFt / (1+WACC)^t) + TV\nWACC = 加权平均资本成本\nTV = 终值 (永续增长法)",
     "example":"茅台 DCF 估值: 未来10年+永续期现金流折回 → 得出内在价值\n难点: 假设增长率和折现率的微小变化会导致估值巨大波动",
     "url":"https://en.wikipedia.org/wiki/Discounted_cash_flow","book":"《估值: 难点、解决方案与相关案例》","category":"估值策略"},
    {"key":"dividend_discount","title":"💵 DDM 股利折现模型 (Gordon Growth)",
     "define":"假设公司每年分红固定增长, 股价 = 下年股利/(必要收益率-增长率)。适合稳定分红公司。",
     "formula":"P = D1 / (r - g)\nD1=下年股利, r=必要收益率, g=分红增长率",
     "example":"银行股常用 DDM 估值 (分红稳定)\n如果 g ≥ r, 模型失效 (要改成多阶段)",
     "url":"https://en.wikipedia.org/wiki/Dividend_discount_model","book":"《股票估值》","category":"估值策略"},
    {"key":"graham_number","title":"🧮 格雷厄姆公式 (安全边际)",
     "define":"格雷厄姆为防御型投资者设计的估值公式。要求 PE ≤ 15, PB ≤ 1.5, 或两者相乘 ≤ 22.5。",
     "formula":"PE × PB ≤ 22.5\n同时要求: 市盈率 ≤ 15 且 市净率 ≤ 1.5",
     "example":"2018年底茅台 PE≈20 PB≈6 → PE×PB=120 → 不符合 (但质量好可以放宽)\n银行股 PE×PB < 8 → 非常便宜",
     "url":"https://en.wikipedia.org/wiki/Benjamin_Graham","book":"《聪明的投资者》- 格雷厄姆","category":"估值策略"},
    {"key":"moat","title":"🏰 护城河 Moat (巴菲特概念)",
     "define":"公司抵御竞争者入侵的能力。5种类型: 品牌、网络效应、转换成本、成本优势、专有技术。",
     "formula":"护城河 = (定价权 × 成本优势 × 客户粘性) 的综合",
     "example":"茅台 = 品牌护城河 (提价权)\n微信 = 网络效应护城河\nCostco = 成本优势护城河\n苹果 = 生态系统护城河",
     "url":"https://en.wikipedia.org/wiki/Economic_moat","book":"《巴菲特的护城河》","category":"估值策略"},

    # ── ⑨ 宏观与周期 ──
    {"key":"美林时钟","title":"🕰️ 美林时钟 (经济+通胀四象限)",
     "define":"根据 GDP 增长和 CPI 通胀的升降组合, 把经济周期分成 4 个阶段, 每个阶段有最优资产配置。",
     "formula":"复苏(↑GDP↓CPI)→股票\n过热(↑GDP↑CPI)→大宗商品\n衰退(↓GDP↑CPI)→债券\n萧条(↓GDP↓CPI)→现金",
     "example":"2020年疫情后=复苏, 股票领涨\n2022年=过热→衰退, 债强股弱\nA股 2024 年典型萧条→复苏过渡期",
     "url":"https://en.wikipedia.org/wiki/Asset_allocation","book":"《资产配置的艺术》","category":"宏观周期"},
    {"key":"kondratiev","title":"🌊 康波周期 (约 50 年)",
     "define":"Nikolai Kondratieff 1920年代提出的长经济周期。技术革命驱动: 机械化→电气→IT→生物科技。",
     "formula":"周期 50-60 年, 分四阶段: 繁荣→衰退→萧条→回升",
     "example":"当前处于 IT 周期尾部 (2000-2030), 生物/新能源周期初期\n萧条期: 持有黄金和国债\n回升期: 持有成长股",
     "url":"https://en.wikipedia.org/wiki/Kondratiev_wave","book":"《康波周期论》- 周金涛 (中文最佳解读)","category":"宏观周期"},
    {"key":"fed_policy","title":"🏦 美联储货币政策 (加息/降息)",
     "define":"美联储通过调整联邦基金利率影响全球流动性。加息→美元强/新兴市场崩/成长股跌; 降息→风险资产普涨。",
     "formula":"联邦基金利率 ↑ → 10Y美债收益率 ↑ → 股票估值 ↓\n利率倒挂 (2Y > 10Y) → 经济衰退预警",
     "example":"2022年美联储加息到5% → 纳斯达克跌33%\n2024年降息预期 → 美股创新高\nA股也受美联储政策显著影响 (北向资金)",
     "url":"https://en.wikipedia.org/wiki/Federal_Reserve","book":"《货币政策与金融市场》","category":"宏观周期"},

    # ── ⑩ 实战技巧 ──
    {"key":"opening_trend","title":"🌅 开盘趋势判断 (集合竞价)",
     "define":"9:25 集合竞价结束后的价格和量能, 往往暗示全天走势。是专业交易员重要的观察点。",
     "formula":"高开 > 2% + 量能放大 > 1.5倍 → 强势, 大概率向上\n低开 > 2% + 量能萎缩 → 弱势, 大概率向下\n平开 + 量能正常 → 震荡",
     "example":"牛市中高开高走概率 70%\n熊市中高开低走概率 60%\n关注集合竞价涨停板数判断情绪",
     "url":"","book":"《盘口实战指南》","category":"实战技巧"},
    {"key":"volume_price","title":"📈 量价关系 (量在价先)",
     "define":"成交量是价格的先行指标。地量见地价, 天量见天价。缩量上涨警惕回调, 放量上涨较健康。",
     "formula":"量增价涨 = 健康上涨 (资金推动)\n量缩价涨 = 虚涨 (无资金接盘)\n量增价跌 = 恐慌抛售\n量缩价跌 = 卖压衰竭",
     "example":"底部连续缩量横盘后突然放量突破 → 启动信号\n顶部放巨量滞涨 → 派发信号",
     "url":"https://en.wikipedia.org/wiki/Volume_(finance)","book":"《量价实战新法》","category":"实战技巧"},
    {"key":"fish_pattern","title":"🐟 鱼身鱼尾均线形态",
     "define":"MA5/MA10/MA20 三条均线多头排列向上发散 = 鱼身 (主升浪)\nMA10/MA20 开始走平或向下 = 鱼尾 (见顶)",
     "formula":"鱼身: MA20 > MA10 > MA5, 三条线均向上\n鱼尾: MA5 下穿 MA10, MA20 走平",
     "example":"经典牛股: 鱼身持续 2-6 个月, 涨幅 50-200%\n鱼尾阶段往往伴随放量滞涨, 聪明钱出货",
     "url":"","book":"《均线战法》","category":"实战技巧"},
]

_HELP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "help_knowledge.json"
)
def _load_helps():
    """加载帮助知识库 JSON, 不存在则从 _HELP_DB 种子生成"""
    if not os.path.exists(_HELP_FILE):
        items = _get_help_seed()
        try:
            os.makedirs(os.path.dirname(_HELP_FILE), exist_ok=True)
            with open(_HELP_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return items
    try:
        with open(_HELP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _get_help_seed()

def _save_helps(items):
    try:
        os.makedirs(os.path.dirname(_HELP_FILE), exist_ok=True)
        with open(_HELP_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


# ── 🎨 配色 (与 fund_holdings_tab 统一) ──
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


# ═══════════════════════════════════════════════════════════
#  🔄 数据层 — JSON 持久化
# ═══════════════════════════════════════════════════════════

_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "learning_sources.json"
)


def _default_data():
    """首次运行时的种子数据"""
    return {
        "theories": [
            {"name": "📐 MM 定理 (Modigliani-Miller)",
             "url": "https://en.wikipedia.org/wiki/Modigliani%E2%80%93Miller_theorem",
             "desc": "1958. 完美市场中公司价值与资本结构无关. 有税+破产成本→最优结构."},
            {"name": "🌊 有效市场假说 EMH",
             "url": "https://en.wikipedia.org/wiki/Efficient-market_hypothesis",
             "desc": "Fama 1970. 弱式/半强式/强式. 诺奖2013."},
            {"name": "⚖️ CAPM 资本资产定价模型",
             "url": "https://en.wikipedia.org/wiki/Capital_asset_pricing_model",
             "desc": "Sharpe 1964. E(R)=Rf+β×(Rm-Rf). 低β长期跑赢高β."},
            {"name": "📘 布莱克-斯科尔斯公式",
             "url": "https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model",
             "desc": "诺奖1997. 欧式期权定价基石."},
            {"name": "🧠 行为金融学",
             "url": "https://en.wikipedia.org/wiki/Behavioral_finance",
             "desc": "Kahneman诺奖2002 / Thaler诺奖2017."},
            {"name": "📈 周期理论 (康波/美林时钟)",
             "url": "https://en.wikipedia.org/wiki/Kondratiev_wave",
             "desc": "康波(~50年)/美林时钟(经济+通胀四象限→资产配置)."},
            {"name": "💰 DCF/DDM 绝对估值",
             "url": "https://www.investopedia.com/terms/d/dcf.asp",
             "desc": "巴菲特: 所有投资本质是DCF."},
            {"name": "📦 筹码分布理论",
             "url": "https://baike.baidu.com/item/%E7%AD%B9%E7%A0%81%E5%88%86%E5%B8%83",
             "desc": "陈浩. 单峰集中=吸筹/多峰发散=派发."},
        ],
        "tools": [
            {"name": "💻 同花顺 iFinD", "url": "https://www.10jqka.com.cn/",
             "desc": "商业级金融数据终端."},
            {"name": "💨 Wind 万得", "url": "https://www.wind.com.cn/",
             "desc": "机构标配. 年费~10万."},
            {"name": "🔴 东方财富", "url": "https://www.eastmoney.com/",
             "desc": "免费行情+股吧+Choice."},
            {"name": "⚪ 雪球", "url": "https://xueqiu.com/",
             "desc": "行情+社区."},
            {"name": "📉 TradingView", "url": "https://www.tradingview.com/",
             "desc": "国际版同花顺."},
            {"name": "🐍 AkShare", "url": "https://akshare.akfamily.xyz/",
             "desc": "开源Python金融数据."},
            {"name": "📊 TuShare Pro", "url": "https://tushare.pro/",
             "desc": "基金持仓/北向/龙虎榜."},
            {"name": "🏦 QMT MiniQMT", "url": "https://www.thinktrader.net/",
             "desc": "券商量化交易终端."},
            {"name": "💹 CFTC COT 报告",
             "url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
             "desc": "期货持仓四分类. 华尔街顶级机构工具."},
            {"name": "📺 财联社", "url": "https://www.cls.cn/",
             "desc": "实时电报最快."},
            {"name": "📺 华尔街见闻", "url": "https://wallstreetcn.com/",
             "desc": "全球实时资讯."},
        ],
        "books": [
            {"category": "📖 经典必读",
             "items": [
                {"name": "《聪明的投资者》", "url": "https://book.douban.com/subject/6794531/",
                 "desc": "格雷厄姆. 巴菲特老师."},
                {"name": "《股票作手回忆录》", "url": "https://book.douban.com/subject/5334858/",
                 "desc": "利弗莫尔. 投机之神."},
                {"name": "《海龟交易法则》", "url": "https://book.douban.com/subject/3279906/",
                 "desc": "丹尼斯100万→4000万传奇."},
            ]},
            {"category": "💎 价值投资",
             "items": [
                {"name": "《巴菲特致股东的信》", "url": "https://book.douban.com/subject/10781407/",
                 "desc": "年报文章集."},
                {"name": "《价值投资实战手册》", "url": "https://book.douban.com/subject/35593606/",
                 "desc": "唐朝(老唐)."},
            ]},
            {"category": "📐 技术分析/量化",
             "items": [
                {"name": "《日本蜡烛图技术》", "url": "https://book.douban.com/subject/3277461/",
                 "desc": "Nison. 蜡烛图奠基人."},
                {"name": "《筹码分布》", "url": "https://book.douban.com/subject/4866632/",
                 "desc": "陈浩. 筹码理论开山之作."},
            ]},
            {"category": "🧠 行为金融",
             "items": [
                {"name": "《思考, 快与慢》", "url": "https://book.douban.com/subject/6794533/",
                 "desc": "卡尼曼. 诺奖2002."},
                {"name": "《反脆弱》", "url": "https://book.douban.com/subject/26059135/",
                 "desc": "塔勒布. 黑天鹅三部曲."},
            ]},
        ],
        "sources": [
            {"category": "🎤 行业大V",
             "items": [
                {"name": "老徐",
                 "url": "",
                 "desc": "抖音/视频号/B站: 追踪聪明钱/SHIBOR/COT."},
                {"name": "唐朝", "url": "https://xueqiu.com/tangchao",
                 "desc": "雪球/公众号「价值投资」"},
                {"name": "但斌", "url": "https://xueqiu.com/danbin",
                 "desc": "东方港湾创始人. 时间的玫瑰."},
                {"name": "段永平", "url": "https://xueqiu.com/duanyongping",
                 "desc": "雪球. 买股票就是买公司."},
                {"name": "林园", "url": "https://xueqiu.com/linyuan",
                 "desc": "茅台/五粮液/片仔癀."},
            ]},
            {"category": "📱 媒体/社群",
             "items": [
                {"name": "淘股吧", "url": "https://www.taoguba.com.cn/",
                 "desc": "超短/打板聚集地."},
                {"name": "韭研公社", "url": "https://www.jiuyangongshe.com/",
                 "desc": "基本面研究."},
                {"name": "雪球", "url": "https://xueqiu.com/",
                 "desc": "大V聚集地."},
            ]},
            {"category": "📺 B站/视频号/抖音",
             "items": [
                {"name": "半佛仙人", "url": "https://space.bilibili.com/50093454",
                 "desc": "B站财经科普顶流."},
                {"name": "巫师财经", "url": "https://space.bilibili.com/39892570",
                 "desc": "硬核财经分析."},
                {"name": "股事", "url": "",
                 "desc": "抖音号: 游资/私募视角每日盘面."},
            ]},
            {"category": "🔗 数据源",
             "items": [
                {"name": "AkShare", "url": "https://akshare.akfamily.xyz/",
                 "desc": "开源Python金融数据."},
                {"name": "TuShare Pro", "url": "https://tushare.pro/",
                 "desc": "基金持仓/北向/龙虎榜."},
                {"name": "FRED 美联储", "url": "https://fred.stlouisfed.org/",
                 "desc": "EFFR/10Y/失业率."},
                {"name": "SHIBOR", "url": "http://www.shibor.org/",
                 "desc": "银行间拆借利率."},
            ]},
        ],
    }


def _load_data():
    """从 JSON 加载, 文件不存在则用默认种子生成"""
    if not os.path.exists(_DATA_FILE):
        data = _default_data()
        try:
            os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
            with open(_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[学习Tab] 保存种子数据失败: {e}", flush=True)
        return data
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[学习Tab] 加载失败, 使用默认: {e}", flush=True)
        return _default_data()


def _save_data(data):
    try:
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[学习Tab] 保存失败: {e}", flush=True)
        return False


# ═══════════════════════════════════════════════════════════
#  弹框: 新增/编辑 条目
# ═══════════════════════════════════════════════════════════

def _open_edit_dialog(parent, root, section_key, data_obj,
                      idx=None, sub_idx=None, old_name="",
                      old_url="", old_desc="", old_cat=""):
    """
    通用编辑弹框.
    section_key: theories/tools/books/sources
    idx:  顶层索引 (theories/tools 直接索引; books/sources 是 category 索引)
    sub_idx: 仅 books/sources, category 内 item 索引 (None=新增)
    """
    dlg = tk.Toplevel(root)
    dlg.title("编辑条目" if idx is not None else "新增条目")
    dlg.geometry("480x380")
    dlg.configure(bg=_BG_DEEP)
    dlg.transient(root)
    dlg.grab_set()

    # 分类选择 (books/sources 用)
    cat_row = None
    e_cat = None
    if section_key in ("books", "sources"):
        cat_row = tk.Frame(dlg, bg=_BG_DEEP); cat_row.pack(fill=tk.X, padx=10, pady=(10, 2))
        tk.Label(cat_row, text="分类:", bg=_BG_DEEP, fg=_FG_DIM, width=8,
                 anchor="w").pack(side=tk.LEFT)
        categories = [g["category"] for g in data_obj[section_key]]
        e_cat = ttk.Combobox(cat_row, values=categories, width=30)
        e_cat.pack(side=tk.LEFT, padx=4)
        e_cat.set(old_cat or (categories[0] if categories else ""))
        # 新增分类按钮
        def _add_cat():
            new_cat = tk.simpledialog.askstring("新增分类", "分类名称:", parent=dlg)
            if new_cat and new_cat not in categories:
                data_obj[section_key].append({"category": new_cat, "items": []})
                e_cat["values"] = [g["category"] for g in data_obj[section_key]]
                e_cat.set(new_cat)
        btn_add_cat = ttk.Button(cat_row, text="➕新分类", width=8, command=_add_cat)
        btn_add_cat.pack(side=tk.LEFT, padx=4)

    # 名称
    r1 = tk.Frame(dlg, bg=_BG_DEEP); r1.pack(fill=tk.X, padx=10, pady=(8, 2))
    tk.Label(r1, text="名称:", bg=_BG_DEEP, fg=_FG_DIM, width=8,
             anchor="w").pack(side=tk.LEFT)
    e_name = tk.Entry(r1, width=45)
    e_name.pack(side=tk.LEFT, padx=4)
    e_name.insert(0, old_name)

    # URL
    r2 = tk.Frame(dlg, bg=_BG_DEEP); r2.pack(fill=tk.X, padx=10, pady=2)
    tk.Label(r2, text="URL:", bg=_BG_DEEP, fg=_FG_DIM, width=8,
             anchor="w").pack(side=tk.LEFT)
    e_url = tk.Entry(r2, width=45)
    e_url.pack(side=tk.LEFT, padx=4)
    e_url.insert(0, old_url)
    tk.Label(r2, text="(微信/抖音号留空或填备注)", bg=_BG_DEEP,
             fg=_FG_DIM, font=("", 8)).pack(side=tk.LEFT, padx=2)

    # 描述
    r3 = tk.Frame(dlg, bg=_BG_DEEP); r3.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)
    tk.Label(r3, text="描述:", bg=_BG_DEEP, fg=_FG_DIM, anchor="w").pack(fill=tk.X)
    e_desc = tk.Text(r3, height=5, wrap=tk.WORD, bg=_BG_PANEL, fg=_FG_TEXT,
                     relief=tk.FLAT, padx=6, pady=4)
    e_desc.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
    e_desc.insert("1.0", old_desc)

    def _on_save():
        name = e_name.get().strip()
        url = e_url.get().strip()
        desc = e_desc.get("1.0", "end").strip()
        if not name:
            messagebox.showwarning("提示", "名称不能为空", parent=dlg); return

        if section_key in ("theories", "tools"):
            if idx is not None:
                data_obj[section_key][idx] = {"name": name, "url": url, "desc": desc}
            else:
                data_obj[section_key].append({"name": name, "url": url, "desc": desc})
        else:
            # books/sources
            cat_name = e_cat.get().strip()
            if not cat_name:
                messagebox.showwarning("提示", "请选择/填写分类", parent=dlg); return
            # 找到或创建分类
            target_cat = None
            for g in data_obj[section_key]:
                if g["category"] == cat_name:
                    target_cat = g; break
            if target_cat is None:
                target_cat = {"category": cat_name, "items": []}
                data_obj[section_key].append(target_cat)
            if sub_idx is not None and idx is not None:
                target_cat["items"][sub_idx] = {"name": name, "url": url, "desc": desc}
            else:
                target_cat["items"].append({"name": name, "url": url, "desc": desc})

        if _save_data(data_obj):
            try:
                import builtins
                if hasattr(builtins, "_LEARNING_RERENDER") and builtins._LEARNING_RERENDER:
                    builtins._LEARNING_RERENDER()
            except Exception as e:
                print(f"[学习Tab] rerender 触发失败: {e}", flush=True)
            dlg.destroy()
            messagebox.showerror("保存失败", "无法写入数据文件", parent=dlg)

    def _on_cancel():
        dlg.destroy()

    # 按钮行
    btn_row = tk.Frame(dlg, bg=_BG_DEEP); btn_row.pack(fill=tk.X, padx=10, pady=10)
    ttk.Button(btn_row, text="💾 保存", width=12, command=_on_save).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btn_row, text="取消", width=8, command=_on_cancel).pack(side=tk.RIGHT)


# ═══════════════════════════════════════════════════════════
#  🎯 主构建函数
# ═══════════════════════════════════════════════════════════

def build_learning_tab(parent, root=None):
    """🎯 构建 🎓 学习 Tab — 可编辑持久化版"""

    import tkinter.simpledialog as simpledialog

    # ── 字体大小 ──
    _FONT_SIZE = [10]
    def _fs(delta=0):
        _FONT_SIZE[0] = max(8, min(18, _FONT_SIZE[0] + delta))
        return _FONT_SIZE[0]
    def _font(bold=False):
        return ("Menlo", _FONT_SIZE[0], "bold" if bold else "normal")

    # ── 加载数据 ──
    DATA = _load_data()

    # 编辑状态 (让卡片知道是否在编辑模式)
    EDIT_MODE = [False]

    # 重渲染函数 (给弹框保存后调用) — 全局闭包
    def _rerender_all():
        nonlocal _rendered_trigger
        _rendered_trigger()

    # 让弹框能触发重渲染 (通过 global 引用)
    import builtins
    if not hasattr(builtins, "_LEARNING_RERENDER"):
        builtins._LEARNING_RERENDER = None

    if root is None:
        root = parent.winfo_toplevel()

    # ═══════════════════════════════════════════════
    #  顶栏
    # ═══════════════════════════════════════════════
    top = ttk.Frame(parent)
    top.pack(fill=tk.X, padx=6, pady=(6, 2))
    tk.Label(top, text="🎓 学习资料库", bg=_BG_PANEL, fg=_FG_GOLD,
             font=("", 12, "bold")).pack(side=tk.LEFT)
    status_lbl = tk.Label(top, text="点击打开 / 右键编辑 / 按📝进入编辑模式",
                          bg=_BG_PANEL, fg=_FG_DIM, font=("", 9))
    status_lbl.pack(side=tk.LEFT, padx=10)

    # 按钮组 (右对齐, 从右往左 pack)
    btn_editor = [None]  # 引用顶栏按钮, 切换文字
    def _toggle_edit():
        EDIT_MODE[0] = not EDIT_MODE[0]
        if EDIT_MODE[0]:
            btn_editor[0].configure(text="✅完成")
            status_lbl.configure(text="✏️ 编辑模式: 卡片显示 [编辑]/[删除] 按钮")
        else:
            btn_editor[0].configure(text="📝编辑")
            status_lbl.configure(text="点击打开 / 右键编辑 / 按📝进入编辑模式")
        _rerender_all()

    btn_popup = [None]
    def _popup_window():
        win = tk.Toplevel(root)
        win.title("🎓 学习资料库 - 独立窗口")
        win.geometry("1200x800")
        win.configure(bg=_BG_DEEP)
        build_learning_tab(win, root)

    def _refresh_from_file():
        nonlocal DATA
        DATA = _load_data()
        _rerender_all()
        messagebox.showinfo("刷新", f"已从 {_DATA_FILE} 重新加载")

    # 右对齐 (创建时直接存引用)
    ttk.Button(top, text="🗔弹出", width=6, command=_popup_window).pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(top, text="🔄刷新", width=6, command=_refresh_from_file).pack(side=tk.RIGHT, padx=(6, 0))
    btn_edit = ttk.Button(top, text="📝编辑", width=8, command=_toggle_edit)
    btn_edit.pack(side=tk.RIGHT, padx=(6, 0))
    btn_editor[0] = btn_edit  # 保存引用, 切换编辑模式时改文字
    tk.Label(top, text=" 字体:", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9)).pack(side=tk.RIGHT)
    def _do_font_plus():
        _fs(1); _rerender_all()
    def _do_font_minus():
        _fs(-1); _rerender_all()
    ttk.Button(top, text="A+", width=3, command=_do_font_plus).pack(side=tk.RIGHT, padx=(2, 1))
    ttk.Button(top, text="A-", width=3, command=_do_font_minus).pack(side=tk.RIGHT)

    # ═══════════════════════════════════════════════
    #  Notebook — 4 个子 tab
    # ═══════════════════════════════════════════════
    body = tk.Frame(parent, bg=_BG_DEEP)
    body.pack(fill=tk.BOTH, expand=True)
    nb = ttk.Notebook(body)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    tab_theory = ttk.Frame(nb); nb.add(tab_theory, text="📐 金融主流理论")
    tab_tool = ttk.Frame(nb);    nb.add(tab_tool,    text="🛠️ 主流工具")
    tab_book = ttk.Frame(nb);    nb.add(tab_book,    text="📚 学习资料 (书籍)")
    tab_src = ttk.Frame(nb);     nb.add(tab_src,     text="🎯 学习来源 (老师/媒体)")
    tab_help = ttk.Frame(nb);    nb.add(tab_help,    text="📖 帮助知识库")

    def _make_scrollable(frame):
        cv = tk.Canvas(frame, bg=_BG_DEEP, highlightthickness=0)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=cv.yview)
        inner = ttk.Frame(cv)
        cv.configure(yscrollcommand=vsb.set)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind_all("<MouseWheel>", lambda e, c=cv: c.yview_scroll(int(-1*(e.delta/120)), "units"))
        return inner

    inner_t = _make_scrollable(tab_theory)
    inner_u = _make_scrollable(tab_tool)
    inner_b = _make_scrollable(tab_book)
    inner_s = _make_scrollable(tab_src)
    inner_h = _make_scrollable(tab_help)

    # ── Tab5 帮助知识库顶栏 (搜索 + 新增 + 状态) ──
    _help_search_var = tk.StringVar()
    _help_search_var.trace_add("write", lambda *_: _rerender_all())
    help_top = ttk.Frame(tab_help); help_top.pack(fill=tk.X, padx=6, pady=(4,0))
    tk.Label(help_top, text="🔍", bg=_BG_DEEP, fg=_FG_CYAN, font=("", 11)).pack(side=tk.LEFT)
    help_search_entry = ttk.Entry(help_top, textvariable=_help_search_var, width=30)
    help_search_entry.pack(side=tk.LEFT, padx=4)
    ttk.Button(help_top, text="🔎搜索", width=6, command=lambda: _rerender_all()).pack(side=tk.LEFT, padx=2)
    ttk.Separator(help_top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
    ttk.Button(help_top, text="➕新增", width=7, command=lambda: _open_help_edit()).pack(side=tk.LEFT, padx=2)
    ttk.Button(help_top, text="💾写回_HELP_DB", width=14,
               command=lambda: _write_back_help_db()).pack(side=tk.LEFT, padx=2)
    _help_status_lbl = tk.Label(help_top, text="📚 加载中...", bg=_BG_DEEP, fg=_FG_DIM, font=("", 10))
    _help_status_lbl.pack(side=tk.RIGHT, padx=6)

    def _write_back_help_db():
        """把 JSON 帮助条目写回 tab_builders._HELP_DB (让 ❓ 按钮立即生效)"""
        items = _get_helps()
        try:
            import ui.tab_builders as _tb
            new_db = {h["key"]: {k: h.get(k, "") for k in ("title","define","formula","example","url","book")}
                      for h in items if h.get("key")}
            _tb._HELP_DB.clear(); _tb._HELP_DB.update(new_db)
            messagebox.showinfo("✅ 写回成功",
                                f"已把 {len(new_db)} 条帮助写回 _HELP_DB\n重启 App 后永久生效 (JSON 已自动持久化)")
        except Exception as e:
            messagebox.showerror("❌ 写回失败", str(e), parent=parent)

    # ═══════════════════════════════════════════════
    #  卡片 + CRUD
    # ═══════════════════════════════════════════════

    def _open_url(url):
        if url and url.startswith("http"):
            webbrowser.open(url)

    def _edit_card(section_key, idx=None, sub_idx=None,
                   name="", url="", desc="", cat=""):
        _open_edit_dialog(parent, root, section_key, DATA,
                          idx=idx, sub_idx=sub_idx, old_name=name,
                          old_url=url, old_desc=desc, old_cat=cat)

    def _delete_card(section_key, idx=None, sub_idx=None, cat=None):
        if not messagebox.askyesno("确认删除", f"确定删除这条吗？"):
            return
        if section_key in ("theories", "tools"):
            if idx is not None:
                DATA[section_key].pop(idx)
        else:
            if idx is not None and sub_idx is not None:
                DATA[section_key][idx]["items"].pop(sub_idx)
                # 如果分类空了也删掉
                if not DATA[section_key][idx]["items"]:
                    DATA[section_key].pop(idx)
        if _save_data(DATA):
            _rerender_all()

    def _make_card(inner, name, url, desc, color=_FG_GOLD,
                   section_key="", idx=None, sub_idx=None, cat_name=""):
        """创建可交互卡片"""
        card = tk.Frame(inner, bg=_BG_CARD, padx=10, pady=8,
                        highlightbackground=_FG_DIM, highlightthickness=1)
        # 名称行 (可点击 or 纯文字, 看 url 是否 http)
        is_clickable = url.startswith("http")
        lbl_name = tk.Label(card, text=name, bg=_BG_CARD,
                            fg=_FG_BLUE if is_clickable else color,
                            font=_font(bold=True),
                            cursor="hand2" if is_clickable else "arrow")
        lbl_name.pack(anchor="w")
        if is_clickable:
            lbl_name.bind("<Button-1>", lambda e, u=url: _open_url(u))

        # URL 小字 (可点击)
        if url.startswith("http"):
            lbl_url = tk.Label(card, text=url[:45] + ("..." if len(url) > 45 else ""),
                               bg=_BG_CARD, fg=_FG_BLUE,
                               font=("", 8), cursor="hand2")
            lbl_url.pack(anchor="w", pady=(1, 0))
            lbl_url.bind("<Button-1>", lambda e, u=url: _open_url(u))

        # 描述
        lbl_desc = tk.Label(card, text=desc or "(无描述)", bg=_BG_CARD,
                            fg=_FG_DIM, font=_font(),
                            wraplength=340, justify=tk.LEFT)
        lbl_desc.pack(anchor="w", pady=(4, 0))

        # 右键菜单 (所有 section_key 都可用)
        def _show_menu(e):
            menu = tk.Menu(card, tearoff=0, bg=_BG_PANEL, fg=_FG_TEXT,
                           activebackground=_FG_DIM)
            menu.add_command(label="✏️ 编辑",
                             command=lambda: _edit_card(section_key, idx, sub_idx,
                                                        name, url, desc, cat_name))
            menu.add_command(label="🗑️ 删除",
                             command=lambda: _delete_card(section_key, idx, sub_idx, cat_name))
            if is_clickable:
                menu.add_separator()
                menu.add_command(label="🔗 打开链接", command=lambda: _open_url(url))
            menu.tk_popup(e.x_root, e.y_root)

        for w in (card, lbl_name, lbl_desc):
            w.bind("<Button-3>", _show_menu)
            # hover 高亮
            w.bind("<Enter>",
                   lambda e, c=card: c.configure(highlightbackground=color))
            w.bind("<Leave>",
                   lambda e, c=card: c.configure(highlightbackground=_FG_DIM))

        # 编辑模式下显示 [编辑]/[删除] 按钮
        if EDIT_MODE[0]:
            btn_row = tk.Frame(card, bg=_BG_CARD); btn_row.pack(anchor="e", pady=(4, 0))
            ttk.Button(btn_row, text="✏️", width=3,
                       command=lambda: _edit_card(section_key, idx, sub_idx,
                                                  name, url, desc, cat_name)).pack(side=tk.RIGHT, padx=2)
            ttk.Button(btn_row, text="🗑️", width=3,
                       command=lambda: _delete_card(section_key, idx, sub_idx)).pack(side=tk.RIGHT)

        return card

    def _render_all():
        """清空 + 重建所有卡片"""
        for fr in (inner_t, inner_u, inner_b, inner_s, inner_h):
            for w in fr.winfo_children():
                w.destroy()

        # 顶栏 "+新增" 按钮 (动态按 tab 切换 section_key) — 这里简化: 不做顶栏, 只做卡片右键
        # Tab1: 理论 (2列网格, 顶层有新增按钮)
        tk.Label(inner_t, text="📌 右键卡片可编辑/删除, 右键空白区域可新增",
                 bg=_BG_DEEP, fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for i, item in enumerate(DATA["theories"]):
            c = 0 if i % 2 == 0 else 1
            if i % 2 == 0 and i > 0: r += 1
            _make_card(inner_t, item["name"], item.get("url", ""), item.get("desc", ""),
                       color=_FG_GOLD, section_key="theories", idx=i).grid(
                row=r, column=c, padx=6, pady=6, sticky="nsew")
        for i in range(2): inner_t.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_t, "theories")

        # Tab2: 工具
        tk.Label(inner_u, text="📌 右键卡片可编辑/删除", bg=_BG_DEEP,
                 fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for i, item in enumerate(DATA["tools"]):
            c = 0 if i % 2 == 0 else 1
            if i % 2 == 0 and i > 0: r += 1
            _make_card(inner_u, item["name"], item.get("url", ""), item.get("desc", ""),
                       color=_FG_GOLD, section_key="tools", idx=i).grid(
                row=r, column=c, padx=6, pady=6, sticky="nsew")
        for i in range(2): inner_u.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_u, "tools")

        # Tab3: 书籍 (分组)
        tk.Label(inner_b, text="📌 右键卡片可编辑/删除/新增分类", bg=_BG_DEEP,
                 fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for gi, group in enumerate(DATA["books"]):
            # 分类标题
            title = tk.Label(inner_b, text=group["category"], bg=_BG_DEEP, fg=_FG_CYAN,
                             font=_font(bold=True))
            title.grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(14, 4))
            r += 1
            for si, item in enumerate(group["items"]):
                c = 0 if si % 2 == 0 else 1
                if si % 2 == 0 and si > 0: r += 1
                _make_card(inner_b, item["name"], item.get("url", ""), item.get("desc", ""),
                           color=_FG_GOLD, section_key="books", idx=gi, sub_idx=si,
                           cat_name=group["category"]).grid(
                    row=r, column=c, padx=6, pady=6, sticky="nsew")
            r += 1
        for i in range(2): inner_b.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_b, "books")

        # Tab4: 来源 (分组)
        tk.Label(inner_s, text="📌 微信/抖音号可直接填名称+描述, URL 留空", bg=_BG_DEEP,
                 fg=_FG_DIM, font=("", 9)).grid(row=0, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        r = 1
        for gi, group in enumerate(DATA["sources"]):
            title = tk.Label(inner_s, text=group["category"], bg=_BG_DEEP, fg=_FG_CYAN,
                             font=_font(bold=True))
            title.grid(row=r, column=0, columnspan=2, sticky="w", padx=6, pady=(14, 4))
            r += 1
            for si, item in enumerate(group["items"]):
                c = 0 if si % 2 == 0 else 1
                if si % 2 == 0 and si > 0: r += 1
                _make_card(inner_s, item["name"], item.get("url", ""), item.get("desc", ""),
                           color=_FG_GREEN, section_key="sources", idx=gi, sub_idx=si,
                           cat_name=group["category"]).grid(
                    row=r, column=c, padx=6, pady=6, sticky="nsew")
            r += 1
        for i in range(2): inner_s.columnconfigure(i, weight=1)
        _bind_add_on_blank(inner_s, "sources")

        # ════════════════════════════════════════════════
        #  Tab5: 📖 帮助知识库 — 彩色卡片 + 搜索 + CRUD
        # ════════════════════════════════════════════════
        # 懒加载帮助数据
        if not hasattr(_render_all, "_helps"):
            _render_all._helps = _load_helps()  # 首次加载存闭包
        helps = _render_all._helps
        # 搜索过滤
        kw = _help_search_var.get().strip().lower()
        filtered = helps
        if kw:
            filtered = [h for h in helps
                        if kw in (h.get("title","")+h.get("define","")+h.get("formula","")+h.get("example","")).lower()]
        _help_status_lbl.configure(text=f"📚 共 {len(helps)} 条, 搜索匹配 {len(filtered)} 条")
        # 渲染三列卡片网格
        for i, h in enumerate(filtered):
            r, c = divmod(i, 3)
            card_w = 340
            card = tk.Frame(inner_h, bg=_BG_CARD, width=card_w, height=210,
                            highlightthickness=1, highlightbackground=_FG_DIM)
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            inner_h.columnconfigure(c, weight=1)
            # 彩色顶条 (颜色轮询)
            _colors = ["#1565C0","#2E7D32","#E65100","#6A1B9A","#00695C","#C62828","#FF6F00","#283593"]
            _clr = _colors[i % len(_colors)]
            tk.Frame(card, bg=_clr, height=5).pack(fill=tk.X)
            # 标题
            tk.Label(card, text=h.get("title","(无标题)"), bg=_BG_CARD, fg=_clr,
                     font=("", 11, "bold"), anchor="w", wraplength=card_w-24,
                     justify="left").pack(fill=tk.X, padx=10, pady=(6, 2))
            # define (前2行)
            _define = h.get("define","")[:80] + ("..." if len(h.get("define",""))>80 else "")
            tk.Label(card, text=_define, bg=_BG_CARD, fg=_FG_DIM,
                     font=("", 9), anchor="w", wraplength=card_w-24,
                     justify="left").pack(fill=tk.X, padx=10, pady=(0, 4))
            # key 小标签
            _key = h.get("key","")
            if _key:
                tk.Label(card, text=f"🔑 {_key}", bg=_BG_CARD, fg=_FG_CYAN,
                         font=("", 8)).pack(anchor="w", padx=10, pady=(0, 2))
            # 操作行
            op = tk.Frame(card, bg=_BG_CARD); op.pack(fill=tk.X, padx=10, pady=(2, 6))
            ttk.Button(op, text="📖详情", width=7,
                       command=lambda idx=helps.index(h): _show_help_detail(helps[idx])).pack(side=tk.LEFT, padx=2)
            if EDIT_MODE[0]:
                ttk.Button(op, text="✏️编辑", width=7,
                           command=lambda idx=helps.index(h): _open_help_edit(idx)).pack(side=tk.LEFT, padx=2)
                ttk.Button(op, text="🗑️删", width=6,
                           command=lambda idx=helps.index(h): _delete_help(idx)).pack(side=tk.LEFT, padx=2)
        # 空态
        if not filtered:
            tk.Label(inner_h, text="📭 暂无匹配的帮助条目 (右键空白区域可新增)",
                     bg=_BG_DEEP, fg=_FG_DIM, font=("", 11)).grid(row=0, column=0, columnspan=3, pady=40)

    # ── Tab5: 帮助知识库 — 专用函数 ──
    def _init_help_ui():
        """在 inner_h 顶部注入搜索 + 新增栏 (只执行1次)"""
        if hasattr(_render_all, "_help_ui_ready") and _render_all._help_ui_ready:
            return
        _render_all._help_ui_ready = True
        # 这由 build_learning_tab 直接注入 (见下面)
    # 搜索 + 新增栏 (在 build_learning_tab 主体创建) — 用闭包 vars
    # 下面 _open_help_edit / _delete_help / _show_help_detail 都用 DATA, 不, 帮助数据单独存
    def _get_helps():
        if hasattr(_render_all, "_helps") and _render_all._helps:
            return _render_all._helps
        _render_all._helps = _load_helps()
        return _render_all._helps
    def _set_helps(items):
        _render_all._helps = items
        _save_helps(items)
    def _open_help_edit(idx=None):
        """帮助条目新增/编辑弹框"""
        items = _get_helps()
        is_new = idx is None
        old = {} if is_new else items[idx]
        dlg = tk.Toplevel(root); dlg.title("➕ 新增帮助" if is_new else "✏️ 编辑帮助")
        dlg.geometry("680x620"); dlg.configure(bg=_BG_DEEP); dlg.transient(root); dlg.grab_set()
        def _row(parent, label):
            f = tk.Frame(parent, bg=_BG_DEEP); f.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(f, text=label, bg=_BG_DEEP, fg=_FG_CYAN, font=("", 10)).pack(side=tk.LEFT)
            return f
        # key
        f1 = _row(dlg, "🔑 Key (唯一标识, ❓ 按钮用这个关联):")
        v_key = tk.StringVar(value=old.get("key","")); tk.Entry(f1, textvariable=v_key, width=40).pack(side=tk.LEFT, padx=6)
        # title
        f2 = _row(dlg, "📌 标题:")
        v_title = tk.StringVar(value=old.get("title","")); tk.Entry(f2, textvariable=v_title, width=60).pack(side=tk.LEFT, padx=6)
        # define
        tk.Label(dlg, text="📖 定义:", bg=_BG_DEEP, fg=_FG_CYAN, font=("", 10)).pack(anchor="w", padx=12, pady=(8,0))
        txt_define = tk.Text(dlg, height=4, wrap=tk.WORD, bg=_BG_PANEL, fg=_FG_TEXT, relief=tk.FLAT)
        txt_define.pack(fill=tk.X, padx=12, pady=2); txt_define.insert("1.0", old.get("define",""))
        # formula
        tk.Label(dlg, text="🧮 公式:", bg=_BG_DEEP, fg=_FG_CYAN, font=("", 10)).pack(anchor="w", padx=12, pady=(6,0))
        txt_formula = tk.Text(dlg, height=4, wrap=tk.WORD, bg=_BG_PANEL, fg=_FG_TEXT, relief=tk.FLAT)
        txt_formula.pack(fill=tk.X, padx=12, pady=2); txt_formula.insert("1.0", old.get("formula",""))
        # example
        tk.Label(dlg, text="💡 用例/信号:", bg=_BG_DEEP, fg=_FG_CYAN, font=("", 10)).pack(anchor="w", padx=12, pady=(6,0))
        txt_example = tk.Text(dlg, height=4, wrap=tk.WORD, bg=_BG_PANEL, fg=_FG_TEXT, relief=tk.FLAT)
        txt_example.pack(fill=tk.X, padx=12, pady=2); txt_example.insert("1.0", old.get("example",""))
        # url + book
        f3 = _row(dlg, "🔗 参考URL:")
        v_url = tk.StringVar(value=old.get("url","")); tk.Entry(f3, textvariable=v_url, width=60).pack(side=tk.LEFT, padx=6)
        f4 = _row(dlg, "📚 推荐书籍:")
        v_book = tk.StringVar(value=old.get("book","")); tk.Entry(f4, textvariable=v_book, width=60).pack(side=tk.LEFT, padx=6)
        def _save():
            new_item = {
                "key": v_key.get().strip() or (v_title.get().strip()[:8] or "help"),
                "title": v_title.get().strip() or "(无标题)",
                "define": txt_define.get("1.0","end").strip(),
                "formula": txt_formula.get("1.0","end").strip(),
                "example": txt_example.get("1.0","end").strip(),
                "url": v_url.get().strip(),
                "book": v_book.get().strip(),
            }
            cur = _get_helps()
            if is_new: cur.append(new_item)
            else: cur[idx] = new_item
            _set_helps(cur)
            dlg.destroy(); _rerender_all()
        btns = tk.Frame(dlg, bg=_BG_DEEP); btns.pack(pady=14)
        ttk.Button(btns, text="💾保存", width=12, command=_save).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="取消", width=10, command=dlg.destroy).pack(side=tk.LEFT, padx=8)
    def _delete_help(idx):
        items = _get_helps()
        if idx < 0 or idx >= len(items): return
        if not messagebox.askyesno("确认删除", f"确定删除帮助条目 \"{items[idx].get('title','')}\" ?", parent=parent):
            return
        items.pop(idx); _set_helps(items); _rerender_all()
    def _show_help_detail(h):
        """帮助条目完整详情弹窗 (深蓝顶栏 + 彩色分区)"""
        w = tk.Toplevel(root); w.title(h.get("title","帮助详情"))
        w.geometry("720x580"); w.configure(bg="#1565C0"); w.transient(root); w.grab_set()
        # 深蓝顶栏
        header = tk.Frame(w, bg="#1565C0", height=52); header.pack(fill=tk.X)
        tk.Label(header, text=h.get("title","(无标题)"), bg="#1565C0", fg="white",
                 font=("Microsoft YaHei", 15, "bold")).pack(side=tk.LEFT, padx=18, pady=12)
        _key = h.get("key","")
        if _key:
            tk.Label(header, text=f"🔑 {_key}", bg="#1565C0", fg="#BBDEFB",
                     font=("", 11)).pack(side=tk.RIGHT, padx=18, pady=16)
        body = tk.Frame(w, bg="#F5F5F5"); body.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)
        def _card(title, color, content):
            if not content: return
            c = tk.Frame(body, bg="white", highlightthickness=1, highlightbackground="#E0E0E0")
            c.pack(fill=tk.X, pady=6)
            tk.Frame(c, bg=color, height=4).pack(fill=tk.X)
            tk.Label(c, text=title, bg="white", fg=color,
                     font=("Microsoft YaHei", 13, "bold"), anchor="w").pack(fill=tk.X, padx=12, pady=(6,2))
            tk.Label(c, text=content, bg="white", fg="#37474F",
                     font=("Microsoft YaHei", 11), anchor="w", justify="left",
                     wraplength=670).pack(fill=tk.X, padx=12, pady=(0,8))
        _card("📖 定义", "#2E7D32", h.get("define",""))
        _card("🧮 公式", "#1565C0", h.get("formula",""))
        _card("💡 用例 / 信号", "#E65100", h.get("example",""))
        ref = ""
        if h.get("url"): ref += f"网址: {h['url']}\n"
        if h.get("book"): ref += f"书籍: {h['book']}"
        if ref: _card("🔗 参考", "#6A1B9A", ref)
        # 打开链接
        if h.get("url","").startswith("http"):
            tk.Button(body, text="🔗 打开参考链接", bg="#1565C0", fg="white",
                      font=("", 11), relief=tk.FLAT, padx=20,
                      command=lambda: webbrowser.open(h["url"])).pack(pady=(6,0))
        ttk.Button(body, text="关闭", command=w.destroy).pack(pady=(8,0))

    def _bind_add_on_blank(inner, section_key):
        """在 inner 空白区域右键 → 新增"""
        def _on_right(e, sk=section_key):
            menu = tk.Menu(inner, tearoff=0, bg=_BG_PANEL, fg=_FG_TEXT,
                           activebackground=_FG_DIM)
            menu.add_command(label="➕ 新增条目",
                             command=lambda: _edit_card(sk))
            menu.tk_popup(e.x_root, e.y_root)
        inner.bind("<Button-3>", _on_right)
    # 帮助知识库空白区域右键新增
    inner_h.bind("<Button-3>", lambda e: _open_help_edit())

    def _rendered_trigger():
        _render_all()

    # 首次渲染
    _render_all()

    # 把 rerender 暴露给弹框 (通过 builtins 让 _open_edit_dialog 能调)
    import builtins as _bi
    _bi._LEARNING_RERENDER = _render_all


class LearningMixin:
    """🎓 学习 Tab mixin — 挂到主 GUI 上"""

    def _build_learning_tab(self, parent):
        build_learning_tab(parent, root=getattr(self, "root", None))


__all__ = ["LearningMixin", "build_learning_tab"]

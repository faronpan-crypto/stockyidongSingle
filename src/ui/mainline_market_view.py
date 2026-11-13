# -*- coding: utf-8 -*-
"""
💡 市场认识 Tab —— 宏观逻辑 + 普通人策略 + 风险评估
来源: 耶鲁大学经济学博士 / 私募基金管理人 李斌 对话观点
"""

import tkinter as tk
from tkinter import ttk, scrolledtext


def _build_market_view_tab(nb_notebook, root=None):
    """在主线资金 Notebook 里加 Tab4: 💡市场认识"""
    tab = tk.Frame(nb_notebook, bg="#FAFAFA")
    nb_notebook.add(tab, text="  💡 市场认识  ")

    # Banner
    banner = tk.Frame(tab, bg="#6A1B9A", height=48)
    banner.pack(fill=tk.X, padx=6, pady=(6, 4))
    banner.pack_propagate(False)
    tk.Label(banner, text="💡 市场认识 · 宏观逻辑 / 普通人策略 / 风险评估",
             font=("Microsoft YaHei", 12, "bold"),
             bg="#6A1B9A", fg="white").pack(side=tk.LEFT, padx=14)
    tk.Label(banner, text="观点来源: 耶鲁大学经济学博士 · 私募基金管理人 李斌",
             font=("", 9), bg="#6A1B9A", fg="#CE93D8").pack(side=tk.LEFT, padx=8, pady=14)

    # ═══════════════════════════════════════════════════════════
    # 字体调节条 (用户要求: 字体可调节)
    # ═══════════════════════════════════════════════════════════
    ctrl = tk.Frame(tab, bg="#FAFAFA")
    ctrl.pack(fill=tk.X, padx=6, pady=(0, 4))
    tk.Label(ctrl, text="🔧字体:", bg="#FAFAFA", fg="#555", font=("", 9)).pack(side=tk.LEFT)
    size_var = tk.IntVar(value=9)
    size_cb = ttk.Combobox(ctrl, textvariable=size_var, width=4, state="readonly",
                           values=["8", "9", "10", "11", "12", "14"])
    size_cb.pack(side=tk.LEFT, padx=4)

    bg_var = tk.StringVar(value="#FAFAFA")
    tk.Label(ctrl, text="🎨背景:", bg="#FAFAFA", fg="#555", font=("", 9)).pack(side=tk.LEFT, padx=(10, 0))
    bg_cb = ttk.Combobox(ctrl, textvariable=bg_var, width=10, state="readonly",
                         values=["#FAFAFA", "#FFFFFF", "#FFFDE7", "#E8F5E9", "#E3F2FD", "#FCE4EC", "#1A1A2E"])
    bg_cb.pack(side=tk.LEFT, padx=4)

    # ═══════════════════════════════════════════════════════════
    # Notebook 分三大模块
    # ═══════════════════════════════════════════════════════════
    nb_inner = ttk.Notebook(tab)
    nb_inner.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    refs = {"size_var": size_var, "bg_var": bg_var, "text_widgets": []}

    # ---- Tab1: 宏观逻辑 ----
    tab_macro = tk.Frame(nb_inner, bg="#FAFAFA")
    nb_inner.add(tab_macro, text="  🌍 宏观优先级  ")
    _add_text_panel(tab_macro, MACRO_TEXT, refs, "#E1BEE7")

    # ---- Tab2: A股行情判断 ----
    tab_a = tk.Frame(nb_inner, bg="#FAFAFA")
    nb_inner.add(tab_a, text="  📉 A股行情  ")
    _add_text_panel(tab_a, ASTOCK_TEXT, refs, "#FFE0B2")

    # ---- Tab3: 普通人策略 ----
    tab_strategy = tk.Frame(nb_inner, bg="#FAFAFA")
    nb_inner.add(tab_strategy, text="  🎯 普通人策略  ")
    _add_text_panel(tab_strategy, STRATEGY_TEXT, refs, "#C8E6C9")

    # ---- Tab4: 风险承受力评估 ----
    tab_risk = tk.Frame(nb_inner, bg="#FAFAFA")
    nb_inner.add(tab_risk, text="  ⚖️ 风险评估  ")
    _add_text_panel(tab_risk, RISK_TEXT, refs, "#FFCDD2")

    # ---- Tab5: 核心口诀 & 免责 ----
    tab_core = tk.Frame(nb_inner, bg="#FAFAFA")
    nb_inner.add(tab_core, text="  🎯 核心口诀  ")
    _add_text_panel(tab_core, CORE_TEXT, refs, "#B3E5FC")

    # ---- 绑定字体/背景调节 ----
    def _apply_style(_e=None):
        sz = size_var.get()
        bg = bg_var.get()
        for tw in refs["text_widgets"]:
            try:
                tw.config(font=("", sz), bg=bg)
            except Exception:
                pass
    size_cb.bind("<<ComboboxSelected>>", _apply_style)
    bg_cb.bind("<<ComboboxSelected>>", _apply_style)

    return tab


def _add_text_panel(parent, content, refs, accent):
    """在父容器里加一个带装饰的 ScrolledText"""
    card = tk.Frame(parent, bg=accent, highlightthickness=1, highlightbackground=accent)
    card.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    inner = tk.Frame(card, bg="#FAFAFA")
    inner.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

    st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=8, pady=6, spacing1=2, spacing3=4)
    st.pack(fill=tk.BOTH, expand=True)

    # 标签样式
    st.tag_configure("h1", font=("", 13, "bold"), foreground="#4A148C", spacing1=8, spacing3=4)
    st.tag_configure("h2", font=("", 11, "bold"), foreground="#6A1B9A", spacing1=6, spacing3=3)
    st.tag_configure("h3", font=("", 10, "bold"), foreground="#1565C0", spacing1=4)
    st.tag_configure("bullet", font=("", 9), foreground="#424242")
    st.tag_configure("ok", foreground="#2E7D32", font=("", 9, "bold"))
    st.tag_configure("warn", foreground="#E65100", font=("", 9, "bold"))
    st.tag_configure("danger", foreground="#C62828", font=("", 9, "bold"))
    st.tag_configure("tip", foreground="#1565C0", font=("", 9, "bold"))
    st.tag_configure("rule", foreground="#4A148C", font=("", 10, "bold"))
    st.tag_configure("quote", foreground="#757575", font=("", 9, "italic"))

    # 按行解析插入 (支持简单标记)
    for line in content.split("\n"):
        _tag = None
        _l = line
        if _l.startswith("███") or _l.startswith("【"):
            _tag = "h1"
        elif _l.startswith("## "):
            _l = _l[3:]; _tag = "h2"
        elif _l.startswith("### "):
            _l = _l[4:]; _tag = "h3"
        elif _l.startswith("✅") or _l.startswith("🟢") or _l.startswith("🟩"):
            _tag = "ok"
        elif _l.startswith("⚠️") or _l.startswith("🟡") or _l.startswith("🟨"):
            _tag = "warn"
        elif _l.startswith("🚫") or _l.startswith("🔴") or _l.startswith("❌") or _l.startswith("❌"):
            _tag = "danger"
        elif _l.startswith("💡") or _l.startswith("📌") or _l.startswith("👉"):
            _tag = "tip"
        elif _l.startswith("┌") or _l.startswith("└") or _l.startswith("│"):
            _tag = "rule"
        elif _l.startswith('"') or _l.startswith("'"):
            _tag = "quote"
        st.insert(tk.END, _l + "\n", _tag)

    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)
    return st


# ═══════════════════════════════════════════════════════════
# 五大模块文本
# ═══════════════════════════════════════════════════════════

MACRO_TEXT = """███ 一、宏观优先级排序 (李斌博士观点)

## 核心判断: 人民币汇率 > 化债 > 产业升级 > 股市

  🥇 第一优先级: 人民币汇率稳定
     —— 汇率是资产定价的"锚", 汇率不稳则所有资产价格都会剧烈波动

  🥈 第二优先级: 地方政府化债
     —— 地方债务压力是经济最大的"灰犀牛", 化债推进决定了财政空间

  🥉 第三优先级: 产业升级带动就业
     —— 科技/高端制造能否接棒地产, 决定了经济转型是否成功

  🏅 第四优先级: 股市稳定
     —— 股市是宏观结果, 不是宏观原因, 优先级排最后

## 地产时代结束 → 科技时代到来

  📌 地产周期即将结束, 经济将向科技方向转型
  📌 土地财政 → 股权财政 (长期趋势)
  📌 中国股市正从"地产红利"切换到"科技红利"

## 外部风险

  🚫 警惕美国 AI 科技波动引发的全球流动性危机
     外部冲击对 A 股影响不可忽视, 尤其是外资敏感板块

## 资产估值参考

  📊 当前不加杠杆的散户平均回撤: 40%-50%
  📊 两融账户平均回撤: 60%
  🥇 黄金: 长期战略储备价值, 短期受美债高息压制有下行压力
"""

ASTOCK_TEXT = """███ 二、A股行情判断

## 当前位置

  🔍 上证指数 3600 点左右
  📍 处于"情绪冰点"的"真实超跌区域"

## 短期 (1-2 个月): 磨底阶段

  📌 超跌 ≠ 立即反转
  📌 短期行情主要受情绪主导
  📌 磨底周期通常 1-2 个月, 期间反复震荡
  📌 不要期待 V 型反转, 底部结构需要时间筑造

## 中长期 (1-3 年): 看宏观是否落地

  ✅ 若汇率稳定 + 化债推进 + 科技落地 → 长期牛市基础成立
  ⚠️ 若宏观三大优先级推进受阻 → 震荡格局延续
  🌏 中国股市尚未成为美国式"长期定投市场", 转型期波动大

## 操作心态

  🚫 避免"赌反弹"心态
  🚫 切勿加杠杆 (即使在底部区域)
  ✅ 已被套者: 避免频繁交易, 等待情绪修复
  ✅ 持币者: 不必急于入场, 耐心等待磨底结束
"""

STRATEGY_TEXT = """███ 三、普通人友好策略 (按难度排序)

## 第一步: 先做 3 个"自我诊断"

  💼 资金属性: 用"3-5年不用的闲钱", 严禁生活费/借贷/杠杆
  🧠 风险承受力: 能接受单日-20%不失眠 → 可碰波动资产
  ⏰ 时间与能力: 没时间/不懂财报 → 放弃个股, 选被动策略

## 第二步: 匹配 4 类友好策略

### ✅ 策略 1: 被动指数投资 (90% 人最优解) — 躺赢首选

  逻辑: A股长期"牛短熊长", 主动交易易亏
  工具: 沪深300ETF / 科创50ETF (低成本分散)
  执行: 每月定投 + 大跌(-20%)加仓, 目标年化 8-12%
  纪律: "拿得住" — 历史证明坚持5年胜率超90%

### ✅ 策略 2: 核心资产 + 高股息 — 稳健进阶

  配置: 宽基ETF(60%) + 红利/消费龙头(30%) + 现金(10%)
  红利股抗跌, 现金防踏空
  执行: 股息再投, 季度再平衡 (股涨减、跌加)

### ⚠️ 策略 3: 低估值个股 — 价值挖掘 (愿学财报者)

  筛选: ROE>10%、股息>3%、负债<60%
  逻辑: 找"低PE/PB + 高分红 + 现金流稳"公司
  纪律: 单股<10%仓位, 设-15%止损 (防价值陷阱)

### ⚠️ 策略 4: 行业ETF — 主题博弈 (想抓趋势者)

  工具: AI/新能源/半导体 等行业ETF (不碰个股)
  执行: 只做"右侧"(ETF突破MA20 + 放量), 快进快出
  纪律: 亏5%必砍 — 短期情绪主导, 别恋战

## 第三步: 3 条生存铁律

  🔧 仓位纪律: 单策略<30%, 总股票仓位=(100-年龄)%
     例: 30岁→70%, 50岁→50%
     🚫 绝不加杠杆 (杠杆是职业工具, 普通人用必爆)

  🔧 止损止盈:
     被动策略: 不止损 (定投摊薄), 止盈看目标 (年化10%减1/3)
     主动策略: 个股-15% / ETF-8% 无条件止损, 翻倍卖1/2

  🔧 心态管理:
     ✅ 不盯盘 (每周看1次), 避免情绪交易
     ✅ 把炒股当"认知工具", 亏了当学费, 赚了是奖励
     🚫 实体赚不到钱 → 别妄想股市"捷径" (跳级必亏)
"""

RISK_TEXT = """███ 四、风险承受力评估 (三维度)

## 核心公式

  📐 风险承受力 = min(财务能力, 心理耐受, 资金时间)
  💡 短板定仓位!

## 维度 1: 客观财务评估 (基础)

  📊 算"风险本金":
     风险本金 = 总存款 - 应急金(3-6月生活费) - 短期负债
     例: 10万存款 - 3万应急 = 7万风险本金

  📊 记"亏损底线":
     新手: 单笔最大可接受亏损 = 风险本金 × 5%
     有经验: 风险本金 × 10%
     超线必减仓

## 维度 2: 主观心理校准 (关键)

  🧪 情景测试:
     20万亏至12万 → 选"止损拿10万"更理性 (避免沉没成本)
     50万二选一 → 选确定50万 = 风险厌恶, 选对赌 = 警惕冲动

  🧪 真实体验:
     用1-2万试错 (买宽基ETF)
     跌10%时观察 → 频繁看盘想割肉=承受弱, 能按计划持有=合格

  🚫 避认知偏差: 别信"能扛20%"口号, 真实波动中情绪易失控

## 维度 3: 资金时间维度 (约束)

  ⏳ 短期 (<3年, 购房/教育): 禁个股/行业ETF → 货币基金/短债
  ⏳ 中期 (3-5年, 创业/养老): 可配 30%-50% 宽基ETF
  ⏳ 长期 (>5年, 子女/退休): 可 70%+ 指数定投, 忽略短期波动

## 工具与实操建议

  🛠️ 官方问卷: 券商"投资者适当性测评" (C1-C5分类), 仅作参考
  🔄 动态调整: 结婚/生子/换工作需重评, 每季度回顾
  🚶 新手路径: 模拟盘 → 小资金试错 → 复盘反应 → 匹配策略
     弱 → 指数定投
     强 → 学行业轮动

## 重要提醒

  💡 风险承受力 = "能亏多少不影响生活", 非"能赚多少"
  💡 目标是长期稳健, 而非短期赌涨跌
"""

CORE_TEXT = """███ 🎯 核心口诀 & 新手路线

## 李斌博士核心口诀

  ┌─────────────────────────────────────────────┐
  │ 闲钱配指数, 能力配个股;                    │
  │ 纪律控仓位, 心态定盈亏。                    │
  └─────────────────────────────────────────────┘

## 最简路径 (战胜 90% 交易者)

  ✅ 如果做不到"不盯盘、不止损不交易"
  ✅ 直接选 沪深300ETF 定投
  ✅ 这是普通人"战胜 90% 交易者"的最简路径

## 新手成长路线

  1️⃣ 先从"指数定投 + 模拟盘"起步
  2️⃣ 1 年稳定盈利再扩仓
  3️⃣ 策略需"3 个月验证"
     • 被动: 定投胜率 > 80% 合格
     • 主动: 止损执行率 100% 才合格
  4️⃣ 所有策略需适配宏观
     当前汇率/化债优先, 科技需等"硬场景落地"信号
     别盲目追热点 — 宏观错, 策略再精也亏

## 三个不要

  🚫 不要全职炒股 (非职业路径)
  🚫 不要加杠杆 (普通人用必爆)
  🚫 不要把股市当唯一收入来源

## 投入比例建议

  💡 非专业人士投入股市的资产占比 → 总资产 5% 以下
  💡 视为"交学费"的学习工具, 而非收入来源

## ── 免责声明 ──

  📌 以上内容均为嘉宾个人观点, 不构成任何投资建议
  📌 市场有风险, 投资需谨慎
  📌 选择适合自己的策略, 核心是先认清"能力边界", 再匹配市场逻辑
  📌 炒股像开赛车 — 非必备技能, 普通人硬拼短线必亏
"""

# -*- coding: utf-8 -*-
「「「
💡 有效市场假说 (EMH) 知识弹窗
理论 + 各国应用 + 行业应用 + 投资启示
「「「
import tkinter as tk
from tkinter import ttk, scrolledtext


# ═══════════════════════════════════════════════════════════════
# 📚 结构化知识数据
# ═══════════════════════════════════════════════════════════════

EMH_THEORY = {
    「弱式有效市场「: {
        「color「: 「#4CAF50「,
        「icon「: 「🌱「,
        「core「: 「价格已反映所有历史交易信息（价格、成交量等），股价变动「随机游走「「,
        「tech_analysis「: 「❌ 技术分析（K线、均线）无法持续获超额收益（历史规律会被套利迅速抹平）「,
        「fundamental「: 「✅ 基本面分析或内幕信息可以获利「,
        「reality「: 「✅ 现实存在 — 新兴市场常见「,
    },
    「半强式有效市场「: {
        「color「: 「#2196F3「,
        「icon「: 「🌊「,
        「core「: 「价格已反映所有公开信息（财报、政策、新闻等），信息公布后价格瞬间消化「,
        「tech_analysis「: 「❌ 技术分析无效「,
        「fundamental「: 「❌ 基本面分析也难持续跑赢市场（机构算法交易领先）「,
        「reality「: 「✅ 现实主流 — 发达市场接近此态「,
    },
    「强式有效市场「: {
        「color「: 「#9C27B0「,
        「icon「: 「🌟「,
        「core「: 「价格反映所有信息（公开 + 内幕），任何信息（含内幕）都无法获超额收益「,
        「tech_analysis「: 「❌ 完全无效「,
        「fundamental「: 「❌ 完全无效「,
        「reality「: 「❌ 仅理论存在 — 现实中因内幕交易可获利且需监管，此形式几乎不存在「,
    },
}

EMH_CORE_INSIGHT = 「「「
🎯 核心启示
═══════════════════════════════════════

  弱式 / 半强式下 主动管理难持续战胜市场
  普通投资者最优策略 = 低成本指数基金

  强式仅理论存在
  也解释了各国禁止内幕交易的必要性
「「「

COUNTRY_APPLICATION = {
    「🇺🇸 美国（发达市场标杆）「: {
        「regime「: 「半强式主导「,
        「weak「: 「技术分析难持续盈利（20年93%主动大盘基金跑输标普500），高频/量化靠非技术数据（订单流）套利「,
        「semi「: 「财报/政策秒消化（CPI公布后纳指微秒波动），机构转向因子投资（价值/质量）或事件研究，指数基金成主流（先锋500规模超万亿）「,
        「strong「: 「《内幕交易法》+SEC执法（2025罚没超4亿美元），「中国墙「隔离研究与交易，现实中无强式「,
    },
    「🇨🇳 中国（新兴转轨）「: {
        「regime「: 「弱式为主、半强式增强「,
        「weak「: 「技术分析短期有效（散户占比60%+致趋势惯性），但长期难盈利（量化需量价+舆情/产业链数据）「,
        「semi「: 「公开信息消化慢（财报/重组后股价漂移常见），机构靠「预期差「获超额收益，指数化加速（沪深300ETF年增30%）「,
        「strong「: 「内幕交易仍存（2025证监会查处42起），监管靠大数据稽查，离强式远「,
    },
    「🇪🇺 欧盟（英/德/法）「: {
        「regime「: 「半强式「,
        「weak「: 「同美国，技术分析难持续盈利「,
        「semi「: 「指数基金普及（欧洲斯托克600 ETF超5000亿欧元），MiFID II强化信息披露「,
        「strong「: 「监管严格，无强式「,
    },
    「🇯🇵 日本「: {
        「regime「: 「半强式但效率打折「,
        「weak「: 「僵尸企业/交叉持股降低效率「,
        「semi「: 「指数化依赖政府养老金（GPIF持有东证ETF超60万亿日元）「,
        「strong「: 「无「,
    },
    「🇮🇳 印度 / 🇸🇬 东南亚「: {
        「regime「: 「弱式为主「,
        「weak「: 「散户主导、信息披露弱，技术分析流行「,
        「semi「: 「被动投资渗透率 < 5%「,
        「strong「: 「监管待完善「,
    },
    「🇧🇷 巴西 / 🇷🇺 俄罗斯「: {
        「regime「: 「弱式 + 政策驱动「,
        「weak「: 「国企权重高，技术分析短期有效「,
        「semi「: 「半强式受政治干预（如巴西国企私有化消息提前泄露）「,
        「strong「: 「远未达到「,
    },
}

INDUSTRY_APPLICATION = {
    「🏦 半强式有效主导（信息易标准化）「: {
        「金融板块（银行/券商/保险）「: 「财报（净息差/承保理赔）、政策（利率/监管）秒消化；技术分析无效；机构靠「预期差「（实际vs一致预期）短机会；指数基金最优「,
        「大宗商品（能源/工业金属）「: 「期货市场「库存数据/供需报告「公开后价格瞬间反应（EIA原油库存、LME铜库存）；高频交易主导；技术分析仅短期噪音「,
        「消费（必选/可选）「: 「高频数据（同店销售/线上GMV）、渠道跟踪（经销商库存）驱动定价；茅台提价后股价跳涨；被动投资为主流「,
    },
    「🔬 弱式有效为主（信息模糊/情绪驱动）「: {
        「科技（成长/AI/半导体）「: 「未来现金流难预测（AI公司无盈利但估值波动）；散户/主题资金放大趋势（2023 AI泡沫）；技术分析短期有效（趋势跟踪盈利）；长期回归基本面「,
        「房地产/REITs「: 「数据滞后（房价/空置率）、非标准化（地段差异）；价格反映历史趋势（弱式）；公开数据消化慢；基本面需实地尽调「,
        「加密货币「: 「无财报/监管弱；价格由情绪/资金驱动（2021比特币泡沫）；技术分析（均线/RSI）广泛盈利；半强式失效「,
    },
    「⚗️ 特殊行业（介于弱/半强或反直觉）「: {
        「医药（创新药/生物科技）「: 「「临床数据/审批结果「公开后跳涨/跌（半强式瞬时）；但管线价值模糊（二期临床失败估值腰斩）；核心是「非公开临床洞见「（接近强式边缘）「,
        「公用事业（电力/水务）「: 「监管定价（费率/补贴）+ 稳定现金流；价格锚定基本面（半强式）；波动小；适合指数配置「,
        「碳金融（碳配额/CCER）「: 「政策主导（欧盟ETS/中国碳市场）；政策信号消化慢（弱式）；机构靠政策预判套利（半强式待成熟）「,
    },
}

INVESTMENT_INSIGHT = 「「「
🎯 行业应用启示
═══════════════════════════════════════

  半强式行业（金融/商品/消费）
    → 放弃技术幻想
    → 用低成本指数/因子策略（价值/质量）
    → 避「追新闻「

  弱式行业（科技/加密）
    → 技术分析仅短期择时
    → 需风控（止损/仓位）
    → 长期锚定基本面（AI看市占率）

  医药/碳金融
    → 核心是「信息优势「（临床数据/政策预判）
    → 普通投资者需分散或专业基金

  ⚠️ 全行业共性
    → 强式有效不存在
    → 警惕「内幕消息「骗局
    → 监管（医药数据披露、碳市场反操纵）是效率前提

═══════════════════════════════════════

📌 驱动差异 vs 策略选择

  发达市场  → 机构/算法定价（半强式） → 指数 + 因子 最优
  新兴市场  → 散户/情绪主导（弱式）   → 基本面 + 事件驱动

  监管重心
    发达 → 防内幕交易
    新兴 → 补披露（注册制、SEBI强制财报电子化）

═══════════════════════════════════════

💎 一句话总结

  美国/欧盟 = 半强式实践模板
  中国/印度 = 弱式转半强式动态样本

  对投资者：
    发达市场 → 敬畏市场 = 指数化
    新兴市场 → 敬畏市场 = 避技术陷阱 + 抓信息差

  核心规律：
    行业信息「可验证性「决定效率层级
    金融/商品/消费因数据透明 → 接近半强式（被动最优）
    科技/加密因模糊性       → 停留在弱式（主动需风控）
    医药/碳金融靠信息优势   → 专业者机会
「「「


# ═══════════════════════════════════════════════════════════════
# 🎨 弹窗 UI
# ═══════════════════════════════════════════════════════════════

def show_emh_panel(parent, app=None):
    「「「💡 有效市场假说知识面板「「「
    win = tk.Toplevel(parent)
    win.title(「💡 有效市场假说 (EMH) — 理论与应用「)
    win.geometry(「1020x760「)
    win.configure(bg=「#FAFAFA「)
    win.transient(parent)

    # ══ 顶栏 ══
    top = tk.Frame(win, bg=「#1A237E「, height=52)
    top.pack(fill=tk.X)
    tk.Label(top, text=「💡 有效市场假说 EMH「,
             font=(「「, 14, 「bold「), bg=「#1A237E「, fg=「white「).pack(side=tk.LEFT, padx=14, pady=12)
    tk.Label(top, text=「尤金·法玛 1970  |  资产价格反映信息程度「,
             font=(「「, 10), bg=「#1A237E「, fg=「#B39DDB「).pack(side=tk.LEFT, padx=4, pady=12)

    # ══ Notebook ══
    nb = ttk.Notebook(win)
    nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # ── Tab1: 理论 ──
    tab_theory = tk.Frame(nb, bg=「#FAFAFA「)
    nb.add(tab_theory, text=「📚 EMH 理论「)
    _build_theory_tab(tab_theory)

    # ── Tab2: 各国应用 ──
    tab_country = tk.Frame(nb, bg=「#FAFAFA「)
    nb.add(tab_country, text=「🌍 各国应用对比「)
    _build_country_tab(tab_country)

    # ── Tab3: 行业应用 ──
    tab_industry = tk.Frame(nb, bg=「#FAFAFA「)
    nb.add(tab_industry, text=「🏭 行业应用差异「)
    _build_industry_tab(tab_industry)

    # ── Tab4: 投资启示 ──
    tab_insight = tk.Frame(nb, bg=「#FAFAFA「)
    nb.add(tab_insight, text=「💎 投资启示「)
    _build_insight_tab(tab_insight)


# ═══════════════════════════════════════════════════════════════
# 📚 Tab1: 理论
# ═══════════════════════════════════════════════════════════════

def _build_theory_tab(parent):
    # 三卡片横排
    cards_row = tk.Frame(parent, bg=「#FAFAFA「)
    cards_row.pack(fill=tk.X, padx=10, pady=10)

    keys = [「弱式有效市场「, 「半强式有效市场「, 「强式有效市场「]
    for i, k in enumerate(keys):
        info = EMH_THEORY[k]
        card = tk.Frame(cards_row, bg=「white「,
                        highlightbackground=info[「color「],
                        highlightthickness=2)
        card.grid(row=0, column=i, sticky=「nsew「, padx=6, pady=6)
        cards_row.grid_columnconfigure(i, weight=1)

        # 标题条
        header = tk.Frame(card, bg=info[「color「])
        header.pack(fill=tk.X)
        tk.Label(header, text=f「{info['icon']} {k}「,
                 font=(「「, 11, 「bold「), bg=info[「color「], fg=「white「,
                 pady=8).pack(anchor=「center「)

        # 内容
        body = tk.Frame(card, bg=「white「)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(body, text=「核心:「, bg=「white「, fg=「#616161「,
                 font=(「「, 9, 「bold「), anchor=「w「).pack(fill=tk.X)
        tk.Label(body, text=info[「core「], bg=「white「, fg=「#212121「,
                 font=(「「, 9), wraplength=280, justify=「left「,
                 anchor=「w「).pack(fill=tk.X, pady=(0, 8))

        tk.Label(body, text=info[「tech_analysis「], bg=「white「,
                 fg=「#C62828「 if 「❌「 in info[「tech_analysis「] else 「#2E7D32「,
                 font=(「「, 9), wraplength=280, justify=「left「,
                 anchor=「w「).pack(fill=tk.X, pady=2)
        tk.Label(body, text=info[「fundamental「], bg=「white「,
                 fg=「#2E7D32「 if 「✅「 in info[「fundamental「] else 「#C62828「,
                 font=(「「, 9), wraplength=280, justify=「left「,
                 anchor=「w「).pack(fill=tk.X, pady=2)
        tk.Label(body, text=info[「reality「], bg=「white「,
                 fg=「#2E7D32「 if 「✅「 in info[「reality「] else 「#9E9E9E「,
                 font=(「「, 9, 「italic「), wraplength=280, justify=「left「,
                 anchor=「w「).pack(fill=tk.X, pady=(6, 0))

    # 核心启示大框
    insight_fr = tk.LabelFrame(parent, text=「🎯 核心启示「, font=(「「, 11, 「bold「),
                               bg=「#E8EAF6「, fg=「#1A237E「)
    insight_fr.pack(fill=tk.X, padx=10, pady=(0, 10))
    tk.Label(insight_fr, text=EMH_CORE_INSIGHT, bg=「#E8EAF6「, fg=「#283593「,
             font=(「「, 10), justify=「left「, anchor=「w「,
             padx=12, pady=10).pack(fill=tk.X)

    # 信息层级对比表
    cmp_fr = tk.LabelFrame(parent, text=「📊 信息覆盖范围对比「, font=(「「, 10, 「bold「),
                           bg=「#FAFAFA「)
    cmp_fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    cols = (「层级「, 「历史价量「, 「公开信息「, 「内幕信息「, 「技术分析「, 「基本面分析「, 「现实存在「)
    tv = ttk.Treeview(cmp_fr, columns=cols, show=「headings「, height=5)
    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=100, anchor=「center「)
    tv.column(「层级「, width=140, anchor=「w「)

    rows = [
        (「🌱 弱式有效「,     「✅「, 「❌「, 「❌「, 「❌ 无效「, 「✅ 可用「, 「✅ 新兴市场「),
        (「🌊 半强式有效「,   「✅「, 「✅「, 「❌「, 「❌ 无效「, 「❌ 难跑赢「, 「✅ 发达市场「),
        (「🌟 强式有效「,     「✅「, 「✅「, 「✅「, 「❌ 无效「, 「❌ 无效「, 「❌ 仅理论「),
    ]
    for r in rows:
        tv.insert(「「, tk.END, values=r)
    tv.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)


# ═══════════════════════════════════════════════════════════════
# 🌍 Tab2: 各国应用
# ═══════════════════════════════════════════════════════════════

def _build_country_tab(parent):
    # 国家选择
    top_ctrl = tk.Frame(parent, bg=「#FAFAFA「)
    top_ctrl.pack(fill=tk.X, padx=10, pady=8)

    tk.Label(top_ctrl, text=「选择市场:「, bg=「#FAFAFA「,
             font=(「「, 10, 「bold「)).pack(side=tk.LEFT, padx=(0, 8))

    keys = list(COUNTRY_APPLICATION.keys())
    var = tk.StringVar(value=keys[0])
    cb = ttk.Combobox(top_ctrl, textvariable=var, values=keys,
                      width=30, state=「readonly「)
    cb.pack(side=tk.LEFT)

    # 详情卡
    detail = tk.Frame(parent, bg=「#FAFAFA「)
    detail.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    # 标题 +  regime 标签
    header = tk.Frame(detail, bg=「white「,
                      highlightbackground=「#1A237E「, highlightthickness=1)
    header.pack(fill=tk.X, pady=(0, 8))
    lbl_title = tk.Label(header, text=「「, bg=「white「, fg=「#1A237E「,
                         font=(「「, 14, 「bold「), anchor=「w「)
    lbl_title.pack(side=tk.LEFT, padx=14, pady=12)
    lbl_regime = tk.Label(header, text=「「, bg=「#1A237E「, fg=「white「,
                          font=(「「, 10, 「bold「), padx=14, pady=4)
    lbl_regime.pack(side=tk.RIGHT, padx=14)

    # 三级详情
    info_frame = tk.Frame(detail, bg=「#FAFAFA「)
    info_frame.pack(fill=tk.BOTH, expand=True)

    def _clear_frame(f):
        for w in f.winfo_children():
            w.destroy()

    def _render(country_key):
        _clear_frame(info_frame)
        d = COUNTRY_APPLICATION[country_key]
        lbl_title.config(text=country_key)
        lbl_regime.config(text=f「  {d['regime']}  「)

        sections = [
            (「🌱 弱式表现「, d[「weak「], 「#4CAF50「),
            (「🌊 半强式表现「, d[「semi「], 「#2196F3「),
            (「🌟 强式表现「, d[「strong「], 「#9C27B0「),
        ]
        for i, (title, content, color) in enumerate(sections):
            sf = tk.Frame(info_frame, bg=「white「,
                          highlightbackground=color, highlightthickness=1)
            sf.grid(row=i // 2, column=i % 2, sticky=「nsew「, padx=5, pady=5)
            info_frame.grid_columnconfigure(i % 2, weight=1)

            tk.Label(sf, text=title, bg=color, fg=「white「,
                     font=(「「, 10, 「bold「), pady=6).pack(fill=tk.X)
            tk.Label(sf, text=content, bg=「white「, fg=「#37474F「,
                     font=(「「, 9), wraplength=450, justify=「left「,
                     anchor=「w「, padx=10, pady=10).pack(fill=tk.BOTH, expand=True)

    cb.bind(「<<ComboboxSelected>>「, lambda e: _render(var.get()))
    _render(keys[0])

    # 底部总结对比表
    sum_fr = tk.LabelFrame(parent, text=「📊 全球市场效率阶梯「, font=(「「, 10, 「bold「),
                           bg=「#FAFAFA「)
    sum_fr.pack(fill=tk.X, padx=10, pady=(0, 10))

    cols = (「市场「, 「效率层级「, 「特征「, 「策略偏好「)
    tv = ttk.Treeview(sum_fr, columns=cols, show=「headings「, height=6)
    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=200 if c == 「特征「 or c == 「策略偏好「 else 120,
                  anchor=「w「 if c in (「特征「, 「策略偏好「) else 「center「)

    summary_rows = [
        (「🇺🇸 美国「,     「半强式「,     「机构主导/算法定价/监管严格「,           「指数 + 因子投资「),
        (「🇪🇺 欧盟「,     「半强式「,     「同美国，MiFID II强化披露「,             「指数基金普及「),
        (「🇯🇵 日本「,     「半强式偏弱「, 「僵尸企业/交叉持股降低效率「,            「政府养老金主导指数化「),
        (「🇨🇳 中国「,     「弱式→半强式「, 「散户60%+/预期差/注册制推进「,           「基本面 + 事件驱动 + 指数化加速「),
        (「🇮🇳 印度/东南亚「, 「弱式「,     「散户主导/信息披露弱「,                 「技术分析流行/被动<5%「),
        (「🇧🇷 巴西/俄「,   「弱式+政策「,  「国企权重高/政治干预「,                  「政策驱动为主「),
    ]
    for r in summary_rows:
        tv.insert(「「, tk.END, values=r)
    tv.pack(fill=tk.X, padx=6, pady=6)


# ═══════════════════════════════════════════════════════════════
# 🏭 Tab3: 行业应用
# ═══════════════════════════════════════════════════════════════

def _build_industry_tab(parent):
    # 三个分组
    colors = {
        「🏦 半强式有效主导（信息易标准化）「: 「#2196F3「,
        「🔬 弱式有效为主（信息模糊/情绪驱动）「: 「#FF9800「,
        「⚗️ 特殊行业（介于弱/半强或反直觉）「: 「#9C27B0「,
    }

    for group_title, industries in INDUSTRY_APPLICATION.items():
        color = colors.get(group_title, 「#616161「)

        grp = tk.LabelFrame(parent, text=group_title, font=(「「, 11, 「bold「),
                            bg=「#FAFAFA「, fg=color)
        grp.pack(fill=tk.X, padx=10, pady=8)

        row_fr = tk.Frame(grp, bg=「#FAFAFA「)
        row_fr.pack(fill=tk.X, padx=6, pady=6)

        for i, (ind_name, ind_desc) in enumerate(industries.items()):
            card = tk.Frame(row_fr, bg=「white「,
                            highlightbackground=color, highlightthickness=1)
            card.grid(row=0, column=i, sticky=「nsew「, padx=4, pady=4)
            row_fr.grid_columnconfigure(i, weight=1)

            tk.Label(card, text=ind_name, bg=color, fg=「white「,
                     font=(「「, 10, 「bold「), pady=5, wraplength=280,
                     justify=「center「).pack(fill=tk.X)
            tk.Label(card, text=ind_desc, bg=「white「, fg=「#37474F「,
                     font=(「「, 9), wraplength=280, justify=「left「,
                     anchor=「w「, padx=10, pady=10).pack(fill=tk.BOTH, expand=True)

    # 行业决策树
    tree_fr = tk.LabelFrame(parent, text=「🧭 行业效率决策树 — 我该用什么策略？「,
                            font=(「「, 11, 「bold「), bg=「#FFF3E0「, fg=「#E65100「)
    tree_fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    tree_text = (
        「┌─ 信息是否易标准化 / 公开可验证？\n「
        「│\n「
        「├─ YES → 半强式有效\n「
        「│   ├── 金融/商品/消费\n「
        「│   ├── 技术分析 ❌  →  放弃技术幻想\n「
        「│   ├── 基本面 ❌    →  也难持续跑赢\n「
        「│   └── 最优策略 ✅  →  低成本指数基金 / 因子策略\n「
        「│\n「
        「├─ NO, 信息模糊 / 情绪驱动\n「
        「│   ├── 科技/加密/主题\n「
        「│   ├── 技术分析 ✅  →  短期择时有效\n「
        「│   ├── 基本面 ⚠️    →  长期锚定（但短期估值波动剧烈）\n「
        「│   └── 风控关键 ✅  →  止损 / 仓位管理\n「
        「│\n「
        「└─ PARTIAL, 部分可验证、部分靠洞见\n「
        「    ├── 医药/碳金融/创新药\n「
        「    ├── 公开数据 → 半强式瞬时（临床结果公布跳涨/跌）\n「
        「    ├── 非公开洞见 → 接近强式边缘\n「
        「    └── 普通投资者 → 分散化 / 专业基金\n「
    )
    tk.Label(tree_fr, text=tree_text, bg=「#FFF3E0「, fg=「#3E2723「,
             font=(「Menlo「, 10), justify=「left「, anchor=「w「,
             padx=12, pady=10).pack(fill=tk.BOTH, expand=True)


# ═══════════════════════════════════════════════════════════════
# 💎 Tab4: 投资启示
# ═══════════════════════════════════════════════════════════════

def _build_insight_tab(parent):
    text_widget = scrolledtext.ScrolledText(parent, font=(「「, 11),
                                            wrap=tk.WORD, padx=14, pady=14)
    text_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    text_widget.insert(「1.0「, INVESTMENT_INSIGHT)

    # 样式 tag
    text_widget.tag_configure(「title「, foreground=「#1A237E「,
                              font=(「「, 13, 「bold「))
    text_widget.tag_configure(「section「, foreground=「#283593「,
                              font=(「「, 11, 「bold「))
    text_widget.tag_configure(「warn「, foreground=「#C62828「)
    text_widget.tag_configure(「good「, foreground=「#2E7D32「)

    text_widget.config(state=「disabled「)

    # 底部快捷参考卡
    quick = tk.Frame(parent, bg=「#E8EAF6「, height=60)
    quick.pack(fill=tk.X, padx=8, pady=(0, 8))
    tk.Label(quick,
             text=「💎  敬畏效率边界：按行业选工具，敬畏市场 = 选对方法「,
             bg=「#E8EAF6「, fg=「#1A237E「, font=(「「, 11, 「bold「)).pack(pady=14)

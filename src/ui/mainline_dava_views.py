# -*- coding: utf-8 -*-
"""
🌟 大V观点聚合 — 经济学家 / 投资大师 / 商业大佬 / 顶级基金经理
数据来源: 微博 / 格隆汇 / Forisight / 澎湃新闻 / Oaktree Memos (2026年11月最新)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext


def _build_dava_views_tab(nb_notebook, root=None):
    """在主线资金 Notebook 里加: 🌟大V观点"""
    tab = tk.Frame(nb_notebook, bg="#FAFAFA")
    nb_notebook.add(tab, text="  🌟 大V观点  ")

    banner = tk.Frame(tab, bg="#E65100", height=44)
    banner.pack(fill=tk.X, padx=6, pady=(6, 4))
    banner.pack_propagate(False)
    tk.Label(banner, text="🌟 大V观点聚合 · 经济学家 / 投资大师 / 商业大佬 / 顶级基金经理",
             font=("Microsoft YaHei", 12, "bold"),
             bg="#E65100", fg="white").pack(side=tk.LEFT, padx=14)

    # 字体调节
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
                         values=["#FAFAFA", "#FFFFFF", "#FFF8E1", "#FFF3E0", "#E3F2FD", "#FCE4EC", "#1A1A2E"])
    bg_cb.pack(side=tk.LEFT, padx=4)
    _date_lbl = tk.Label(ctrl, text="📅 数据截至: 2026-11-13", bg="#FAFAFA", fg="#999", font=("", 8))
    _date_lbl.pack(side=tk.RIGHT, padx=8)

    # 分类 Notebook
    nb_inner = ttk.Notebook(tab)
    nb_inner.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    refs = {"size_var": size_var, "bg_var": bg_var, "text_widgets": []}

    # === 分类1: 经济学家 ===
    t1 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t1, text="  🎓 经济学家  ")
    _make_person_card(t1, "张五常", "香港大学经济学院教授 · 新制度经济学之父", "产权·交易费用·《经济解释》",
                      DAVA_ZHANGWCHANG, refs, "#FFE0B2")
    _make_person_card(t1, "林毅夫", "北大新结构经济学研究院院长", "新结构·比较优势·有为政府",
                      DAVA_LINYF, refs, "#FFCCBC")
    _make_person_card(t1, "付鹏", "新火集团首席经济学家", "FICC+C·全球宏观·一人对冲基金",
                      DAVA_FUPENG, refs, "#FFAB91")

    # === 分类2: 国际投资大师 ===
    t2 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t2, text="  🌍 国际投资大师  ")
    _make_person_card(t2, "霍华德·马克斯", "橡树资本(Oaktree)创始人 · 投资备忘录", "周期·风险控制·AI泡沫？",
                      DAVA_HOWARD, refs, "#B3E5FC")

    # === 分类3: 投资大V / 基金经理 ===
    t3 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t3, text="  💰 投资大V  ")
    _make_person_card(t3, "张坤", "易方达基金 · 顶流基金经理", "蓝筹精选·白酒→科技·生意模式",
                      DAVA_ZHANGKUN, refs, "#C8E6C9")
    _make_person_card(t3, "银行螺丝钉", "指数基金定投专家", "日更估值·星级系统·养老定投",
                      DAVA_SCREW, refs, "#A5D6A7")

    # === 分类4: 商业大佬 ===
    t4 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t4, text="  🚀 商业大佬  ")
    _make_person_card(t4, "马斯克", "SpaceX/Tesla/xAI 创始人", "万亿富翁·400亿GPU债·太空算力",
                      DAVA_MUSK, refs, "#81D4FA")
    _make_person_card(t4, "稻盛和夫", "京瓷/KDDI 创始人 · 经营之圣", "阿米巴·敬天爱人·六项精进",
                      DAVA_INAMORI, refs, "#F8BBD0")

    # === 分类5: 热门榜单 ===
    t5 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t5, text="  📋 热门榜单  ")
    _make_hot_list(t5, refs)

    # 绑定字体/背景调节
    def _apply_style(_e=None):
        sz = size_var.get(); bg = bg_var.get()
        for tw in refs["text_widgets"]:
            try: tw.config(font=("", sz), bg=bg)
            except Exception: pass
    size_cb.bind("<<ComboboxSelected>>", _apply_style)
    bg_cb.bind("<<ComboboxSelected>>", _apply_style)

    return tab


def _make_person_card(parent, name, title, tagline, content, refs, accent):
    """人物卡片 — 标题 + 完整内容"""
    card = tk.Frame(parent, bg=accent, highlightthickness=1, highlightbackground=accent)
    card.pack(fill=tk.X, padx=4, pady=4)

    head = tk.Frame(card, bg=accent)
    head.pack(fill=tk.X, padx=8, pady=(6, 2))
    tk.Label(head, text=f"👤 {name}", font=("Microsoft YaHei", 11, "bold"),
             bg=accent, fg="#BF360C").pack(side=tk.LEFT)
    tk.Label(head, text=f"  ·  {title}", font=("", 9),
             bg=accent, fg="#5D4037").pack(side=tk.LEFT)
    tk.Label(head, text=f"  [{tagline}]", font=("", 8),
             bg=accent, fg="#8D6E63").pack(side=tk.LEFT)

    inner = tk.Frame(card, bg="#FAFAFA")
    inner.pack(fill=tk.X, padx=4, pady=(0, 4))
    st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=6, pady=4, spacing1=1, spacing3=3,
                                   height=10)
    st.pack(fill=tk.X)

    st.tag_configure("sub", font=("", 10, "bold"), foreground="#BF360C", spacing1=6)
    st.tag_configure("bullet", foreground="#424242")
    st.tag_configure("hot", foreground="#C62828", font=("", 9, "bold"))
    st.tag_configure("info", foreground="#1565C0", font=("", 9, "bold"))
    st.tag_configure("src", foreground="#9E9E9E", font=("", 8, "italic"))
    st.tag_configure("quote", foreground="#6A1B9A", font=("", 9, "italic"))
    st.tag_configure("book", foreground="#2E7D32", font=("", 9, "bold"))
    st.tag_configure("link", foreground="#1565C0", font=("", 9, "underline"))

    for line in content.split("\n"):
        _tag = None
        if line.startswith("## "):
            st.insert(tk.END, line[3:] + "\n", "sub")
        elif line.startswith("🔥") or line.startswith("🚨") or line.startswith("⚠️"):
            st.insert(tk.END, line + "\n", "hot")
        elif line.startswith("💡") or line.startswith("📌") or line.startswith("✅"):
            st.insert(tk.END, line + "\n", "info")
        elif line.startswith("📖") or line.startswith("📚"):
            st.insert(tk.END, line + "\n", "book")
        elif line.startswith("🔗") or line.startswith("http"):
            st.insert(tk.END, line + "\n", "link")
        elif line.startswith("📅") or line.startswith("📰") or line.startswith("["):
            st.insert(tk.END, line + "\n", "src")
        elif line.startswith('"'):
            st.insert(tk.END, line + "\n", "quote")
        else:
            st.insert(tk.END, line + "\n")
    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)
    return st


def _make_hot_list(parent, refs):
    """热门榜单 — 综合排行"""
    card = tk.Frame(parent, bg="#F1F8E9", highlightthickness=1, highlightbackground="#8BC34A")
    card.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    inner = tk.Frame(card, bg="#FAFAFA")
    inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=8, pady=6, spacing1=2, spacing3=4)
    st.pack(fill=tk.BOTH, expand=True)

    st.tag_configure("h1", font=("", 12, "bold"), foreground="#33691E", spacing1=8, spacing3=4)
    st.tag_configure("h2", font=("", 10, "bold"), foreground="#558B2F", spacing1=6)
    st.tag_configure("rank", font=("", 9, "bold"), foreground="#C62828")
    st.tag_configure("info", foreground="#1565C0")

    st.insert(tk.END, "## 🎯 2026年最值得关注的大V榜单\n\n", "h2")
    st.insert(tk.END, "### 🎓 宏观经济学 Top 5\n\n", "h2")
    _rank = [
        ("🥇 林毅夫", "新结构经济学 · 北大 · 主张有效市场+有为政府"),
        ("🥈 付鹏", "新火集团 · FICC+C全球宏观 · 一人对冲基金预言家"),
        ("🥉 张五常", "产权经济学泰斗 · 《经济解释》四卷本"),
        ("4️⃣ 吴敬琏", "改革派代表 · 市场活力=微观主体自主权+安全感"),
        ("5️⃣ 张忆东", "海通国际 · A股慢牛 · 三座大山已推翻"),
    ]
    for r, d in _rank:
        st.insert(tk.END, f"  {r}  —  {d}\n")

    st.insert(tk.END, "\n### 💰 基金经理 Top 3 (2026年三季报后)\n\n", "h2")
    _rank2 = [
        ("🥇 张坤", "易方达 · 独管亚洲精选重仓台积电/SK海力士/三星电子/谷歌"),
        ("🥈 谢治宇", "兴全合润 · 均衡风格代表"),
        ("🥉 葛兰", "中欧医疗健康 · 医疗赛道顶流"),
    ]
    for r, d in _rank2:
        st.insert(tk.END, f"  {r}  —  {d}\n")

    st.insert(tk.END, "\n### 🌍 国际投资大师 (必读)\n\n", "h2")
    _rank3 = [
        ("🥇 霍华德·马克斯", "橡树资本 · 周期+风险 · 2026.11最新 memo: AI外行思考"),
        ("🥈 巴菲特", "伯克希尔 · 2026年股东大会 · 日本五大商社加仓"),
        ("🥉 达利欧", "桥水 · 原则 · 去杠杆/漂亮去杠杆"),
    ]
    for r, d in _rank3:
        st.insert(tk.END, f"  {r}  —  {d}\n")

    st.insert(tk.END, "\n### 🚀 商业大佬 (改变世界)\n\n", "h2")
    _rank4 = [
        ("🥇 马斯克", "万亿富翁 · SpaceX上市 · 400亿债务买GPU"),
        ("🥈 黄仁勋", "英伟达 · AI算力垄断 · 季度营收300亿美"),
        ("🥉 稻盛和夫", "经营之圣 · 阿米巴 · 敬天爱人"),
    ]
    for r, d in _rank4:
        st.insert(tk.END, f"  {r}  —  {d}\n")

    st.insert(tk.END, "\n### 📌 游资心法说明\n", "h2")
    st.insert(tk.END, "  💡 炒股养家等游资心法观点已整合至「🔥主线资金 → 📈AI研判」Tab 的大V观点区\n")
    st.insert(tk.END, "     与简放、徐泽林等 AI 风格分析师的观点放在一起, 方便对比参考\n\n", "info")

    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)
    return st


# ═══════════════════════════════════════════════════════════
# 大V观点文本
# ═══════════════════════════════════════════════════════════

DAVA_ZHANGWCHANG = """📅 最新引用: 2026年8月 · 搜狐财经
📰 来源: 搜狐 / 雪球 / 经济参考报

## 👤 个人简介

  张五常 · 香港大学经济学院教授 · 新制度经济学创始人之一
  著作: 《经济解释》四卷本 (科学说需求/收入与成本/受价与觅价/制度的选择)
  2019年正式从港大退休, 但仍活跃在公共讨论中

## 🔥 核心贡献

  📌 交易费用理论 — 解释企业为什么存在 (Coase定理的延伸)
  📌 产权理论 — 产权清晰推动经济发展, 制度决定交易成本
  📌 佃农理论 — 200年没人想明白的分成合约, 他用交易费用解释了

## 📅 2026年最新观点

  ⚠️ 市场的核心在于产权的清晰、契约的严肃以及价格信号的绝对自由
  ⚠️ 当价格机制被行政之手无形冻结, 经济体便不可避免地陷入失重的迷茫

  🔍 房地产: 土地财政的旧逻辑渐行渐远, 正从"买房即暴富"神话回归"大宗耐用消费品"
  🔍 民企: 民间投资连续多月负区间滑行, 需给予微观主体足够的自主权与安全感
  🔍 外资: 跨国资本在周期面前高度理性, 固定资产投资稳步回撤

## 💡 经典思维方式

  1. 成本-收益分析: 任何选择都有代价, 看放弃了什么
  2. 激励-约束: 制度设计要让好人有好报, 坏人受约束
  3. 供需关系: 价格是信号, 扭曲价格会扭曲资源配置
  4. 边际递减: 多一单位带来的价值递减, 不要过度

## 📖 代表书籍

  📚 《经济解释》四卷本 (必读)
  📚 《佃农理论》(芝加哥大学出版社)
  📚 《卖桔者言》(散文集)
  📚 《五常学经济》

## 🔗 网络资源

  🔗 维基百科 张五常
  🔗 微信公众号 "张五常教授"
"""

DAVA_LINYF = """📅 最新专访: 2026年10月 · 中国经济网 / 2026年3月 · 人民网两会
📰 来源: 上海证券报 / 人民网 / 中国经济学年会

## 👤 个人简介

  林毅夫 · 北京大学新结构经济学研究院院长 · 全国政协常委
  新结构经济学创始人 · 世界银行前首席经济学家 (2008-2012)
  芝加哥大学经济学博士 · 发展经济学权威

## 🔥 核心贡献

  📌 新结构经济学 — 经济发展应立足比较优势, 而非照搬西方模式
  📌 有效市场 + 有为政府 — 市场是基础, 政府在结构变迁中发挥因势利导作用
  📌 后来者优势 — 发展中国家通过引进消化吸收再创新, 实现比发达国家更快增长

## 📅 2026年最新观点 (重磅)

  🎯 十五五目标: 维持 5% 左右年均增速, 为 2035 年人均 GDP 中等发达国家奠基
  🎯 大船优势: 中国是超大规模经济体 — 人才多/市场大/产业全/制度优
  🎯 有效劳动: 老龄化 ≠ 经济减速, 劳动力质量 × 教育水平 = 有效劳动提高
  🎯 银发经济: 老龄化催生新赛道, 供给侧调整 = 经济增长新来源

  🔍 新质生产力: 传统产业 + 新兴产业都可发展新质生产力, 关键是数字化/智能化/绿色化
  🔍 比较优势错位: 各地严格依据自身比较优势错位发展 → 避免重复建设
  🔍 全球南方: 金砖国家GDP (PPP计) 已超过七国集团, 应主动推动全球治理改革

## 💡 经典语录

  "小船在风浪中起伏大, 大船只要做好自己的工作, 就能乘风破浪"
  "挑战固然存在, 但中国的机遇更多"
  "理论的功能是帮助人们认识世界、改造世界。如果一个理论不能解释我们观察到的现象, 就要反思并构建新的理论"

## 📖 代表书籍

  📚 《新结构经济学》(剑桥大学出版社, 2014)
  📚 《繁荣的求索》(北大出版社, 2012)
  📚 《解读中国经济》(北大出版社, 2014)
  📚 《战胜命运》(与诺斯合著)

## 🔗 网络资源

  🔗 北京大学新结构经济学研究院官网
  🔗 第26届中国经济学年会主旨演讲 (2026.10)
"""

DAVA_FUPENG = """📅 最新专访: 2026年11月13日 · Forisight News 6小时对话
📰 来源: Forisight / 格隆汇 / 澎湃新闻

## 👤 个人简介

  付鹏 · 新火集团联合创始人 · 首席经济学家
  "FICC+C" 框架提出者 — 固定收益/外汇/大宗商品/加密货币
  前东北证券首席经济学家 · 前惠富投资合伙人
  微博粉丝超百万, 以深度宏观分析和加密货币讨论闻名

## 🔥 核心贡献

  📌 FICC+C 框架 — 将加密货币正式纳入全球宏观资产配置
  📌 利率作为独立宏观变量 — 跟踪美联储利率周期是核心
  📌 一人对冲基金预言 — AI 让散户时代终结, 头部玩家才活得下去

## 📅 2026年11月最新观点 (重磅)

  🚨 "我对 BTC 没有信仰 — BTC 四年周期已经结束"
  • 比特币从信仰变成资产, 机构入场后波动率大幅缩小
  • 传统金融与加密世界的研究策略将无区别
  • AI 让年轻人成为"一人对冲基金", 散户时代即将结束

  📌 全球配置:
  • FICC+C 多资产策略正在推出 — 固定收益+外汇+大宗商品+数字资产
  • 哑铃配置: 底层类现金/红利股, 上层 Alpha 押注科技
  • 不认同"股市是经济的晴雨表" — 股市 = 估值+价值+制度性红利

  📌 中产阶级建议:
  • 优先还房贷 (降低负债)
  • 半退休"老登们": 股息红利是好选择
  • Beta 资产跟着巴菲特风格走, Alpha 押注改变生产力的

  💡 "K型经济对应 K型流动性 — 现在是流动性分层阶段"
  💡 "赚钱是靠周期, 不是靠预测"

## 📖 代表书籍 / 专栏

  📚 微博长文《BTC 四年周期已结束》(2026.11)
  📚 Forisight 专访《FICC+C 框架详解》(2026.11)
  📚 《信用债投资指南》

## 🔗 网络资源

  🔗 微博 @付鹏 North
  🔗 Forisight News
  🔗 格隆汇专栏
"""

DAVA_HOWARD = """📅 最新备忘录: 2026年11月11日 《A Layman Thinks About AI》
📰 来源: Oaktree Capital Memos (官网中文译本)

## 👤 个人简介

  霍华德·马克斯 (Howard Marks) · 橡树资本 (Oaktree Capital) 联合创始人
  管理规模超 2000 亿美元 · 《投资最重要的事》作者
  以定期投资备忘录闻名 — 每次发布都引发全球投资界关注
  被巴菲特称为"我第一时间读的备忘录"

## 🔥 核心贡献

  📌 投资备忘录 — 定期发布的深度思考 (免费, 官网可下载)
  📌 周期思维 — 市场在恐惧和贪婪之间钟摆式摆动
  📌 风险控制 — "首先, 不要亏钱; 其次, 永远不要忘记第一条"
  📌 另类投资 — 不良债务/私募信贷/困境投资

## 📅 2026年11月最新备忘录 (重磅)

  备忘录标题: 《A Layman Thinks About AI》 (AI 外行思考)
  继 2025.12 《是泡沫吗?》 和 2026.2 《AI 高歌猛进》之后, 第三次讨论 AI

  🎯 核心问题: "AI 为用户创造的价值, 能否支撑数万亿美元的基础设施投资?"

  📌 三个判断维度:
  1. 技术本身能实现什么? (AI 潜力可能被低估)
  2. 企业资本开支能产生足够回报吗? (尚无定论)
  3. 投资者为股票和债券支付的价格合理吗? (需谨慎)

  📌 债务警示: 2026 年全球 AI 相关债务发行已接近 6000 亿美元
  • 约 4000 亿进入美国投资级债券市场 (占全年 1/5 新增供应)
  • 云厂商持续举债 → 可能推高其他借款人的资本成本

  💡 核心方法论 (马克斯的"好问题清单"):
  1. 要获得合理回报, 需要多少假设同时成立?
  2. 如果核心假设错了, 最大可能亏损是多少?
  3. 当前价格已经反映了多少乐观预期?
  4. 这项投资会让组合更多元化, 还是放大现有风险?

  🎯 "最重要的是知道自己不知道什么" — 这是马克斯反复强调的

## 📖 代表书籍

  📚 《投资最重要的事》(The Most Important Thing) — 必读!
  📚 《周期》(Mastering the Market Cycle)
  📚 《投资备忘录全集》(官网可免费下载全部历史备忘录)

## 🔗 网络资源

  🔗 橡树资本官网 Memos 专区 (全中文译本)
  🔗 微信公众号 "橡树资本 Oaktree"
  🔗 播客《The Memo by Howard Marks》(Art19)
"""

DAVA_ZHANGKUN = """📅 最新三季报: 2026年10月27日 · 易方达基金
📰 来源: 澎湃新闻 / 21世纪经济报道 / 易方达官方

## 👤 个人简介

  张坤 · 易方达基金 · 顶流基金经理
  管理规模约 293 亿元 · 代表作: 易方达蓝筹精选 / 亚洲精选
  以长期持有、深度研究、重仓消费蓝筹闻名
  被称为"中国版巴菲特" · 坚持"生意模式+竞争壁垒"选股框架

## 🔥 2026年三季度调仓 (重要!)

  🚨 独管产品 (亚洲精选) — 重仓全球 AI 半导体:
  • 台积电 (TSM) · SK海力士 · 三星电子 · 阿斯麦 · 科天半导体
  • 谷歌 (GOOGL) 新进前十, 大幅增持 244%
  • 阿里巴巴退出前十, 富途控股减仓 75%

  📌 共管产品 (蓝筹精选) — 历史首次买 AI 股后又减持电子:
  • 二季度建仓中芯国际/东山精密 → 三季度双双退出前十
  • 新易盛 (光模块) 新进前十, 增持 176%
  • 川投能源 (水电) 新进前十, 增持 20.94%
  • 白酒: 茅台/泸州老窖/山西汾酒继续收缩 (去白酒路线清晰)
  • 阿里巴巴唯一明显加仓

  📌 卸任: 9月30日卸任易方达优质企业三年持有, 交棒张琦

## 📅 2026年三季报观点

  💡 "生意模式 (产生充沛自由现金流) + 竞争壁垒 (显著领先地位)" 依然最重要
  💡 "长期向上的经济是企业长期成长的土壤 — 基础概率影响5-10年后公司价值"
  💡 "居民端预期各项指标仍未见起色 — 消费者信心指数从 110 降到 90, 呈 L 型"
  💡 "生育率不断下行, 新生儿 2025 年跌破 800 万 — 需避免周期性问题演变成结构性问题"
  💡 "经济持续保持活力的前提: 每一代人要相信自己会比上一代人生活得更好"
  💡 "比引导预期更有效的是: 政府资产负债表扩张"

  ⚠️ AI 板块判断:
  • 三季度 AI 科技板块局部泡沫特征突出
  • 涨价链公司和国产半导体被用远期空间法定价 — 忽视潜在周期性
  • 但底层模型能力跨越式发展, 是整个 AI 产业第一性原理
  • 选择公司的重要标准: 产业链地位的不可替代性

## 📌 三季报关键数据

  • 易方达蓝筹精选期末规模: 189.33 亿元 (减 14.83 亿)
  • 三季度净值: -4.58% (跑赢基准 -4.02%)
  • 隐形重仓股: 北方华创/寒武纪/中际旭创/江丰电子 (首次买入)

## 📖 代表理念

  📚 《巴菲特致股东信》(张坤每年推荐)
  📚 《聪明的投资者》
  📚 《竞争战略》(波特)

## 🔗 网络资源

  🔗 易方达基金官网 (定期报告可下载)
  🔗 雪球 @张坤粉丝团
"""

DAVA_SCREW = """📅 最新: 2026年10月 · 日更估值第3000+期
📰 来源: 银行螺丝钉 微博 / 公众号

## 👤 个人简介

  银行螺丝钉 · 指数基金定投专家 · 日更估值 3000+ 期 (从2014年起)
  五星级估值系统创始人 · 《指数基金投资指南》《定投十年财务自由》作者
  目标: 日更估值 10000 期 (已过 30%)

## 📅 2026年市场观察

  🔥 5月 A股回到 3.6-3.7 星 — 整体不再低估
  📌 小盘成长风格达高估, 需谨慎
  📌 其他风格多在正常估值区间
  💡 高估品种分批止盈, 资金转 365 天等债券稳健策略

## 📌 螺丝钉星级系统

  • 1⭐ 极度高估 · 2⭐ 高估 · 3⭐ 正常 · 4⭐ 低估 · 5⭐ 极度低估
  • 每天日更指数估值表 (沪深300/中证500/创业板/纳斯达克...)
  • 雷打不动, 3000+ 期不间断

## 🎯 定投三原则

  1️⃣ 低估买入, 正常持有, 高估卖出
  2️⃣ 分不同风格指数分散配置 (宽基/行业/海外)
  3️⃣ 定投 + 大跌加仓, 目标年化 8-12%

## 📌 养老投资指南 (2026年新书)

  • 养老三支柱: 基本养老 + 企业年金 + 个人养老金
  • 个人养老金账户: 适合高收入/高个税人群 (税递延划算)
  • 养老 FOF: 选目标日期 FOF (如"XX养老目标2045"), 自动调整股债比
  • 指数基金自配: 分散风格 + 定期再平衡 (股涨减/跌加)

## 📖 代表书籍

  📚 《指数基金投资指南》(2017)
  📚 《定投十年财务自由》(2019)
  📚 《个人养老金投资指南》(2026.3 新书!)

## 🔗 网络资源

  🔗 微信公众号 "银行螺丝钉" (每天推送估值表)
  🔗 微博 @银行螺丝钉
"""

DAVA_MUSK = """📅 最新: 2026年10-11月
📰 来源: 环球人物 / 证券时报 / 新浪财经

## 👤 个人简介

  马斯克 (Elon Musk) · 万亿富翁 (全球首位)
  SpaceX 创始人/CEO · Tesla CEO · xAI 创始人
  SpaceX 2026年6月纳斯达克上市 (SPCX) · 估值 1.77 万亿美元
  持 SpaceX 41% + Tesla 2600 亿美股权

## 🚀 2026年关键事件

  📌 SpaceX 上市 (6月) — 美股史上最大 IPO, 募资 750 亿美元
  📌 财富突破万亿美元 — 人类历史首位万亿富翁
  📌 400 亿美元债务融资 — 全部用于采购 GPU (三季度资本开支 195 亿, 84% 砸 AI)
  📌 SpaceX 合并 xAI — 轨道数据中心战略 (星链 + xAI 超级智能)

## 📌 AI 算力军备竞赛

  🚨 每赚 1 美元就要再投 2.18 美元进算力 — 烧钱速度远快于赚钱
  🚨 SpaceX 三季度资本开支 195 亿 → 其中 164 亿砸 AI 业务 (84%)
  🚨 SI 超级智能业务收入 75.6 亿 → 同比增长 830%

  🎯 马斯克判断:
  • 未来几周债务市场几乎完全切断资金渠道
  • 没有 AI 数据中心外独立收入的公司 → 200 多个新云服务商将面临死亡整合
  • 太空将在 2-3 年内成为 AI 算力成本最低的场所
    (恒定太阳能 + 无土地/散热成本)

## 📌 商业版图 (全部上市公司)

  • SpaceX (SPCX): 火箭 + 星链 + xAI (已合并) → 轨道数据中心
  • Tesla (TSLA): Robotaxi + 储能 → 德州获准 L4 自动驾驶
  • Neuralink: 脑机接口 → 估值 90 亿美元

## 💡 投资启示

  📌 马斯克财富 = 市场对未来能力的预支 (现金占比 < 0.1%)
  📌 所有资产高度集中, 随时可能因股价剧烈波动
  📌 每次他都在押注改变文明的方向 — 跨行星物种 / 超级智能 / 人机共生

## 🔗 网络资源

  🔗 SpaceX 官网
  🔗 X (Twitter) @ElonMusk (最常更新)
"""

DAVA_INAMORI = """📅 最新: 2026年10月 · 京瓷官方
📰 来源: 稻盛和夫官方网站 / 盛和塾

## 👤 个人简介

  稻盛和夫 (Inamori Kazuo) · 经营之圣 · 京瓷/KDDI 创始人
  27 岁创办京瓷 (Kyocera) · 52 岁创办 KDDI (日本第二大电信)
  78 岁临危受命破产的日本航空 (JAL), 1 年重回世界 500 强
  京瓷 50 年不亏损的奇迹 — 被称为"日本版巴菲特"

## 📖 2026年新书出版

  📚 《经营之心: 助力企业的"心"领导》文库版 (2026.10)
  • 统率众人 / 拓展事业 / 激活组织 / 开拓未来 四层面
  • 47 条经营语录 — 京瓷/KDDI/JAL 实践浓缩
  📚 《阿米巴经营》20 周年精装珍藏版 (2026.10)

## 🔧 京瓷现任 CEO 演进阿米巴 (2026)

  📌 佐久田浩 (现任京瓷 CEO) 推 "演进阿米巴"
  • 集团层面设立"经营计划办公室" (全局视角)
  • 聚焦: 业务领域 / 投资决策 / 资本配置 (ROIC 管理)
  • 决定 M&A / R&D / 新业务方向

## 💡 核心哲学

  1️⃣ 六项精进 (成就每个人):
     • 付出不亚于任何人的努力
     • 要谦虚, 不要骄傲
     • 要每天反省
     • 活着, 就要感谢
     • 积善行, 思利他
     • 不要有感性的烦恼

  2️⃣ 敬天爱人: 敬畏上天, 关爱众人 — 经营的最高理念

  3️⃣ 人人都是经营者: 把公司分成小单元 (阿米巴), 让每个员工感受到自己也是经营者

  💡 "企业管理本质上是心态管理, 经营者的心态决定整个组织的命运"

## 📖 代表书籍

  📚 《阿米巴经营》(核心必读)
  📚 《活法》(人生哲学)
  📚 《干法》(工作方法)
  📚 《经营之心》(2026 新书)
  📚 《利他的经营》

## 🔗 网络资源

  🔗 京瓷官方 (2026.10 新书发布)
  🔗 盛和塾 (中国) 官方
  🔗 稻盛和夫公益基金会
"""

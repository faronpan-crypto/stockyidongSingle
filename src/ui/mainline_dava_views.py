# -*- coding: utf-8 -*-
"""
🌟 名人堂 — 操盘手 / 投资家 / 无著述大佬 / 署名坑 / 阅读指南
数据来源: 中信出版书单 / 上海高级金融学院 / 央视网 / 经济参考报 (2026-11-13)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import webbrowser


# ═══════════════════════════════════════════════════════════════
# 📚 名人数据模型 (操盘手 vs 投资家 两派分开)
# ═══════════════════════════════════════════════════════════════

# --- 核心: 亲笔写过书的操盘手 ---
TRADERS = [
    {
        "name": "杰西·利弗莫尔",
        "name_en": "Jesse Livermore",
        "years": "1877–1940",
        "tagline": "投机之王 · 关键点买卖法 · 大起大落的一生",
        "logic": "只做龙头, 金字塔加仓 (盈利后加仓), 严格止损 (亏10%必砍), 价格沿最小阻力线运动, 熊市赚的钱牛市全部亏回去",
        "books": [
            {"title": "《股票大作手操盘术》", "title_en": "How to Trade in Stocks", "year": "1940", "note": "唯一亲笔! 关键点买卖法、金字塔加仓", "url": "https://zh.wikipedia.org/wiki/杰西·利弗莫尔"},
        ],
        "pitfall": "《股票作手回忆录》(1923) 不是他写的 — 作者是记者 Edwin Lefèvre, 化名'拉里·利文斯顿'小说体评传",
        "links": [("维基百科", "https://zh.wikipedia.org/wiki/杰西·利弗莫尔"), ("investopedia", "https://www.investopedia.com/terms/l/livermore.asp")],
        "accent": "#FFCDD2",
    },
    {
        "name": "安德烈·科斯托拉尼",
        "name_en": "André Kostolany",
        "years": "1906–1999",
        "tagline": "德国股神 · 反周期大师 · 狗和主人比喻股市",
        "logic": "股市=狗和主人: 狗跑在前面但最终回到主人身边; 反周期操作: 别人买时我卖; 经济是基础, 股市是狗; 长期看股市永远上涨; 不要做波段, 要做周期",
        "books": [
            {"title": "《大投机家》", "year": "1980s", "note": "一生13本, 全球约300万册", "url": "https://zh.wikipedia.org/wiki/安德烈·科斯托拉尼"},
            {"title": "《大投机家的证券心理学》", "year": "—", "note": "\"趋势=资金+心理\"", "url": ""},
        ],
        "pitfall": "是川银藏《股市之神》≠ 科斯托拉尼《股市神猎手》 — 中译名误配经典坑",
        "links": [("维基百科", "https://zh.wikipedia.org/wiki/安德烈·科斯托拉尼")],
        "accent": "#FFE0B2",
    },
    {
        "name": "是川银藏",
        "name_en": "Ginzo Arikawa",
        "years": "1897–1977",
        "tagline": "日本股神 · 三年不买股 · 乌龟三原则",
        "logic": "三年不买股, 研究三年才出手; 独立思考, 不看报纸不炒股; 买入: 所有人悲观时; 卖出: 所有人乐观时; 大赚小赔, 只买冷门股票",
        "books": [
            {"title": "《波乱的一生》", "title_en": "中译《股市之神》", "note": "乌龟三原则: 绝不追高/绝不买热门/绝不满仓", "url": "https://zh.wikipedia.org/wiki/是川银藏"},
        ],
        "pitfall": "中译《股市之神》≠ 科斯托拉尼《股市神猎手》 — 不同的人",
        "links": [("维基百科", "https://zh.wikipedia.org/wiki/是川银藏")],
        "accent": "#F8BBD0",
    },
    {
        "name": "W.D. 江恩",
        "name_en": "W. D. Gann",
        "years": "1878–1955",
        "tagline": "技术分析宗师 · 时间周期理论 · 争议最大的实战派",
        "logic": "时间周期: 7天/30天/90天/1年/10年/60年; 几何图形+价格回撤1/2、1/3、2/3; 时间窗口是第一要素; 转折点=时间+价格共振; 星相和数字学辅助",
        "books": [
            {"title": "《江恩华尔街45年》", "title_en": "45 Years in Wall Street", "year": "1949", "note": "业绩可验证性争议很大", "url": "https://zh.wikipedia.org/wiki/江恩"},
            {"title": "《股票行情的真谛》", "title_en": "The Truth of the Stock Tape", "url": ""},
        ],
        "pitfall": "著述最勤的一批实战者, 但其宣称的收益缺乏可验证记录 — 选书先明确想学什么",
        "links": [("维基百科", "https://zh.wikipedia.org/wiki/江恩")],
        "accent": "#D1C4E9",
    },
    {
        "name": "尼古拉斯·达瓦斯",
        "name_en": "Nicolas Darvas",
        "years": "1920–1977",
        "tagline": "箱体理论创始人 · 舞蹈演员转行 · 只看报价不看新闻",
        "logic": "箱体突破: 价格在狭窄区间整理后放量突破; 量价配合: 放量突破+缩量回调; 金字塔加仓: 突破确认后逐步加仓; 严格止损: 跌破箱体下沿立即出场",
        "books": [
            {"title": "《我如何在股市赚了200万美元》", "title_en": "How I Made $2,000,000 in the Stock Market", "year": "1960", "note": "箱体理论开山之作", "url": "https://zh.wikipedia.org/wiki/尼古拉斯·达瓦斯"},
        ],
        "pitfall": "",
        "links": [("维基百科", "https://zh.wikipedia.org/wiki/尼古拉斯·达瓦斯")],
        "accent": "#B3E5FC",
    },
    {
        "name": "维克托·斯波朗迪",
        "name_en": "Victor Sperandeo",
        "years": "—",
        "tagline": "职业操盘原理 · 华尔街终结者",
        "logic": "风险报酬比至少1:3才出手; 趋势=更高的高点+更高的低点; 三重移动平均线判断; 分批建仓分批止盈; 顺势交易不抄底",
        "books": [
            {"title": "《专业投机原理》", "title_en": "Trader Vic — Methods of a Wall Street Master", "year": "1993", "note": "被《巴伦周刊》称'华尔街终结者'", "url": "https://book.douban.com/subject/5980568/"},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/5980568/")],
        "accent": "#C8E6C9",
    },
    {
        "name": "马丁·舒华兹",
        "name_en": "Martin Schwartz",
        "years": "—",
        "tagline": "全美交易冠军 · 纪律第一 · 每天100万美元",
        "logic": "纪律第一: 每天止损不超1.5%; TICK指数+TRIN指标看市场内部结构; 短线快进快出; 开盘前30分钟黄金时间; 连亏3天休1天",
        "books": [
            {"title": "《交易冠军》", "title_en": "Pit Bull", "note": "全美交易大赛10次参赛9次冠军", "url": "https://book.douban.com/subject/1288208/"},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/1288208/")],
        "accent": "#A5D6A7",
    },
    {
        "name": "爱德华·索普",
        "name_en": "Edward Thorp",
        "years": "1932–",
        "tagline": "量化对冲之父 · 算牌法发明者 · 数学思维战胜市场",
        "logic": "凯利公式算最优下注比例; 统计套利: 配对交易/价差回归; 数学模型驱动无情绪; 市场低效处找统计优势; 期权定价和对冲",
        "books": [
            {"title": "《战胜一切市场的人》", "title_en": "A Man for All Markets", "year": "2017", "note": "数学家, 算牌法发明者, 量化投资源头", "url": "https://book.douban.com/subject/30169303/"},
            {"title": "《打败庄家》", "title_en": "Beat the Dealer", "year": "1962", "note": "21点算牌法开山之作", "url": ""},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/30169303/"), ("维基百科", "https://zh.wikipedia.org/wiki/爱德华·索普")],
        "accent": "#81D4FA",
    },
    {
        "name": "亚历山大·埃尔德",
        "name_en": "Alexander Elder",
        "years": "1951–",
        "tagline": "三重滤网系统 · 交易心理学 · 精神科医生转行",
        "logic": "三重滤网: 周线(长期趋势)→日线(中期方向)→分钟线(入场时机); MACD柱判断多空力量; 盈亏比至少2:1; 纪律和心态>技术指标; 交易是马拉松不是百米冲刺",
        "books": [
            {"title": "《以交易为生》", "title_en": "Trading for a Living", "year": "1993", "note": "精神科医生转行, 心理/方法/资金三支柱", "url": "https://book.douban.com/subject/1339452/"},
            {"title": "《走进我的交易室》", "title_en": "Come Into My Trading Room", "year": "2002", "url": ""},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/1339452/"), ("官网", "https://www.elder.com/")],
        "accent": "#B2DFDB",
    },
    {
        "name": "马克·道格拉斯",
        "name_en": "Mark Douglas",
        "years": "1947–2015",
        "tagline": "交易心理学奠基者 · 概率思维 · 纪律是唯一解药",
        "logic": "交易是概率游戏不是预测; 接受不确定性, 接受亏损是成本; 纪律对抗人性弱点; 输赢分布随机但胜率可算; 害怕亏损=过度交易=持续亏损; 心态>技术>资金管理",
        "books": [
            {"title": "《交易心理分析》", "title_en": "Trading in the Zone", "year": "2000", "note": "只谈信念结构, 交易心理学奠基", "url": "https://book.douban.com/subject/5437458/"},
            {"title": "《自律的交易者》", "title_en": "The Disciplined Trader", "year": "1990", "url": ""},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/5437458/")],
        "accent": "#C5CAE9",
    },
    {
        "name": "乔治·索罗斯",
        "name_en": "George Soros",
        "years": "1930–",
        "tagline": "反身性理论 · 量子基金 · 偏哲学不含赚钱技巧",
        "logic": "反身性: 市场参与者的思维与市场现实相互影响, 永远处于动态不平衡; 易错性: 人类对世界的认知永远是局部和扭曲的; 不做短线, 押注宏观大逻辑",
        "books": [
            {"title": "《金融炼金术》", "title_en": "The Alchemy of Finance", "year": "1987", "note": "偏哲学, 不含具体赚钱技巧", "url": "https://book.douban.com/subject/1073250/"},
            {"title": "《超越金融》", "title_en": "Soros on Soros", "year": "2010", "note": "比《金融炼金术》好懂得多", "url": ""},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/1073250/"), ("维基百科", "https://zh.wikipedia.org/wiki/乔治·索罗斯")],
        "accent": "#EF9A9A",
    },
    {
        "name": "迈克尔·斯坦哈特",
        "name_en": "Michael Steinhardt",
        "years": "1940–",
        "tagline": "宏观对冲早期 · 最直白的一手自传",
        "logic": "宏观对冲, 押注利率和汇率方向, 最直白的实战一手记录",
        "books": [
            {"title": "《No Bull: My Life In and Out of Markets》", "year": "2001", "note": "宏观对冲早期最直白的一手自传, 无中译", "url": ""},
        ],
        "pitfall": "",
        "links": [("维基百科", "https://zh.wikipedia.org/wiki/迈克尔·斯坦哈特")],
        "accent": "#FFCCBC",
    },
]


# --- 介于操盘手和投资家之间 ---
BETWEEN = [
    {
        "name": "威廉·欧奈尔",
        "name_en": "William O'Neil",
        "tagline": "CANSLIM 选股法 · 成长股技术派",
        "logic": "CANSLIM: 当季+年增长率/机构持股/新产品新概念/股价在52周新高附近/领涨股/市场方向/小盘股优先; 技术面+基本面双筛选",
        "books": [
            {"title": "《笑傲股市》", "title_en": "How to Make Money in Stocks", "year": "1988", "url": "https://book.douban.com/subject/1397351/"},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/1397351/")],
        "accent": "#FFF9C4",
    },
    {
        "name": "理查德·怀科夫",
        "name_en": "Richard D. Wyckoff",
        "years": "1873–1934",
        "tagline": "量价分析奠基者 · 吸筹派发模型",
        "logic": "庄家吸筹-拉升-派发模型; 量价配合判断机构行为; 弹簧/UTAD/LPS 等关键形态; 目前仍被主力资金研究者奉为圣经",
        "books": [
            {"title": "《Wyckoff 方法》系列讲义", "note": "量价分析奠基, 无标准中译本", "url": ""},
        ],
        "pitfall": "",
        "links": [("维基百科", "https://en.wikipedia.org/wiki/Richard_D._Wyckoff")],
        "accent": "#FFF176",
    },
    {
        "name": "范·K·撒普",
        "name_en": "Van K. Tharp",
        "tagline": "交易系统设计 · 头寸管理",
        "logic": "期望值为正的系统设计; 头寸管理是核心 (凯利公式/最优F); 交易系统=市场+方法+头寸+心理; 把交易当概率游戏",
        "books": [
            {"title": "《通向金融王国的自由之路》", "title_en": "Trade Your Way to Financial Freedom", "note": "系统设计经典", "url": "https://book.douban.com/subject/1139611/"},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/1139611/")],
        "accent": "#FFD54F",
    },
    {
        "name": "拉里·威廉斯",
        "name_en": "Larry R. Williams",
        "tagline": "短线交易冠军 · 期货大赛冠军",
        "logic": "R% 指标 (威廉指标); 期货短线交易; 年度收益114%; 以儿子命名的基金后来爆仓",
        "books": [
            {"title": "《短线交易秘诀》", "title_en": "Long-Term Secrets to Short-Term Trading", "url": "https://book.douban.com/subject/3279715/"},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/3279715/")],
        "accent": "#FFB74D",
    },
]


# --- 投资家 (基本面/估值) ---
INVESTORS = [
    {
        "name": "本杰明·格雷厄姆",
        "name_en": "Benjamin Graham",
        "years": "1894–1976",
        "tagline": "价值投资之父 · 巴菲特的老师",
        "logic": "安全边际: 价格低于内在价值30%才买; 市场先生比喻; 分散投资; 买股票=买企业的一部分; 长期持有+股息回报",
        "books": [
            {"title": "《证券分析》", "title_en": "Security Analysis", "year": "1934", "note": "价值投资圣经, 与多德合著", "url": "https://book.douban.com/subject/5243782/"},
            {"title": "《聪明的投资者》", "title_en": "The Intelligent Investor", "year": "1949", "note": "巴菲特推荐'最好的投资书'", "url": "https://book.douban.com/subject/5243787/"},
        ],
        "pitfall": "",
        "links": [("豆瓣-聪明的投资者", "https://book.douban.com/subject/5243787/")],
        "accent": "#DCEDC8",
    },
    {
        "name": "菲利普·费雪",
        "name_en": "Philip Fisher",
        "years": "1907–2004",
        "tagline": "成长股投资之父 · 闲聊法",
        "logic": "闲聊法: 向竞争对手/客户/供应商打听公司; 15要点: 公司是否有增长潜力/管理层是否优秀/研发投入等; 优秀公司长期持有",
        "books": [
            {"title": "《怎样选择成长股》", "title_en": "Common Stocks and Uncommon Profits", "year": "1958", "note": "成长股投资开山", "url": "https://book.douban.com/subject/1511024/"},
        ],
        "pitfall": "",
        "links": [("豆瓣读书", "https://book.douban.com/subject/1511024/")],
        "accent": "#C5E1A5",
    },
    {
        "name": "彼得·林奇",
        "name_en": "Peter Lynch",
        "years": "1944–",
        "tagline": "麦哲伦基金经理 · 十年十倍",
        "logic": "生活中发现好公司 (在超市看到的产品背后的公司); 快速增长期买入, 成熟期卖出; 10倍股理论; 不做宏观预测",
        "books": [
            {"title": "《彼得·林奇的成功投资》", "title_en": "One Up on Wall Street", "year": "1989", "url": "https://book.douban.com/subject/1070133/"},
            {"title": "《战胜华尔街》", "title_en": "Beating the Street", "year": "1993", "url": "https://book.douban.com/subject/1070135/"},
        ],
        "pitfall": "中译名误配: 马尔基尔《漫步华尔街》≠ 林奇 One Up on Wall Street; 后者与帕特·多尔西《股市真规则》也常被混作一本",
        "links": [("豆瓣-成功投资", "https://book.douban.com/subject/1070133/")],
        "accent": "#9CCC65",
    },
    {
        "name": "霍华德·马克斯",
        "name_en": "Howard Marks",
        "years": "1946–",
        "tagline": "橡树资本创始人 · 周期思维",
        "logic": "周期: 市场在恐惧和贪婪之间钟摆; 风险控制: 首先不要亏钱; 定期投资备忘录 (免费, 官网可下载); 另类投资 (不良债务/私募信贷)",
        "books": [
            {"title": "《投资最重要的事》", "title_en": "The Most Important Thing", "note": "必读!", "url": "https://book.douban.com/subject/1073248/"},
            {"title": "《周期》", "title_en": "Mastering the Market Cycle", "year": "2018", "url": "https://book.douban.com/subject/30101822/"},
        ],
        "pitfall": "",
        "links": [("橡树资本 Memos", "https://www.oaktreecapital.com/insights/memos"), ("豆瓣-周期", "https://book.douban.com/subject/30101822/")],
        "accent": "#7CB342",
    },
    {
        "name": "塞斯·卡拉曼",
        "name_en": "Seth Klarman",
        "years": "1957–",
        "tagline": "安全边际投资 · Baupost 基金",
        "logic": "深度价值, 安全边际, 事件驱动; 现金为王 (经常持有40%+现金); 逆向投资; 被誉为'年轻版巴菲特'",
        "books": [
            {"title": "《安全边际》", "title_en": "Margin of Safety", "year": "1991", "note": "已绝版, 无正式中文版, 二手超1000美元", "url": ""},
        ],
        "pitfall": "《安全边际》1991年出版后从未再版, 无正式中文版, 二手市场一本超1000美元",
        "links": [("维基百科", "https://en.wikipedia.org/wiki/Seth_Klarman")],
        "accent": "#558B2F",
    },
    {
        "name": "瑞·达利欧",
        "name_en": "Ray Dalio",
        "years": "1949–",
        "tagline": "桥水创始人 · 原则 · 去杠杆",
        "logic": "经济机器是如何运行的 (30分钟视频); 漂亮去杠杆 vs 丑陋去杠杆; 长期债务周期+短期债务周期; 货币+信贷+支出=经济",
        "books": [
            {"title": "《原则》", "title_en": "Principles", "year": "2017", "url": "https://book.douban.com/subject/27608237/"},
            {"title": "《债务危机》", "title_en": "Principles for Navigating Big Debt Crises", "year": "2018", "url": "https://book.douban.com/subject/30448294/"},
        ],
        "pitfall": "",
        "links": [("经济机器如何运行", "https://www.youtube.com/watch?v=PHe0bXAIuk0"), ("豆瓣-债务危机", "https://book.douban.com/subject/30448294/")],
        "accent": "#689F38",
    },
    {
        "name": "纳西姆·塔勒布",
        "name_en": "Nassim Nicholas Taleb",
        "years": "1960–",
        "tagline": "黑天鹅 · 反脆弱 · 厚尾分布",
        "logic": "黑天鹅: 稀有但影响巨大的事件; 反脆弱: 从混乱和冲击中获益 (而非只是耐受); 肥尾分布: 极端事件概率比正态分布大得多; 杠铃策略: 90%低风险+10%高风险",
        "books": [
            {"title": "《黑天鹅》", "title_en": "The Black Swan", "year": "2007", "url": "https://book.douban.com/subject/3350363/"},
            {"title": "《反脆弱》", "title_en": "Antifragile", "year": "2012", "note": "比《黑天鹅》更好", "url": "https://book.douban.com/subject/25888215/"},
            {"title": "《随机漫步的傻瓜》", "title_en": "Fooled by Randomness", "year": "2001", "url": "https://book.douban.com/subject/1472485/"},
        ],
        "pitfall": "",
        "links": [("豆瓣-反脆弱", "https://book.douban.com/subject/25888215/")],
        "accent": "#8BC34A",
    },
]


# --- 名气最大却没亲自写书的 ---
NO_BOOKS = [
    {"name": "巴菲特", "note": "只有历年《致股东的信》, 从无专著。中文市场所有'巴菲特著'都是他人编著。《滚雪球》是艾丽斯·施罗德的评传, 巴菲特没撰写过任何专业著作", "source": "中国经济网书评明确", "url": "https://www.berkshirehathaway.com/letters/letters.html"},
    {"name": "德鲁肯米勒", "note": "索罗斯大弟子, 量子基金核心, 本人无系统著作, 思想全靠杰克·施瓦格《金融怪杰》访谈保存", "source": "《金融怪杰》(1989)", "url": ""},
    {"name": "保罗·都铎·琼斯", "note": "Tudor Investment 创始人, 宏观对冲传奇, 无本人著作, 《金融怪杰》收录其访谈", "source": "《金融怪杰》(1989)", "url": ""},
    {"name": "理查德·丹尼斯", "note": "海龟交易法创始人, 公开招募学员著名实验, 无本人系统著作", "source": "海龟交易法则相关书籍为他人整理", "url": ""},
    {"name": "艾迪·塞柯塔", "note": "计算机化交易先驱, 量化鼻祖之一, 无本人专著, 《金融怪杰》有访谈", "source": "《金融怪杰》(1989)", "url": ""},
    {"name": "布鲁斯·科夫纳", "note": "Caxton Associates 创始人, 宏观对冲大佬, 无本人系统著作, 《金融怪杰》收录", "source": "《金融怪杰》(1989)", "url": ""},
    {"name": "吉姆·西蒙斯", "note": "文艺复兴科技创始人, 量化投资之王, 无著述。中文《征服市场的人》/繁体《洞悉市场的人》原书是《The Man Who Solved the Market》(2019), 作者《华尔街日报》记者 Gregory Zuckerman, 西蒙斯本人不配合采访", "source": "企鹅兰登书目 / 台湾馆藏目录", "url": "https://en.wikipedia.org/wiki/James_Simons"},
    {"name": "徐翔", "note": "无本人著作, 流传的《我在泽熙学到的七堂课》为其前助理叶展所写", "source": "叶展《泽熙投资》", "url": ""},
]


# --- 署名坑 ---
PITFALLS = [
    {
        "title": "《股票作手回忆录》不是利弗莫尔写的",
        "desc": "1923年出版, 作者是记者 Edwin Lefèvre, 以化名'拉里·利文斯顿'写成小说体评传。中文书商常把两本书合并署名'利弗莫尔著', 严格说是错的。利弗莫尔唯一亲笔是1940年《操盘术》。",
        "url": "https://zh.wikipedia.org/wiki/股票作手回忆录",
    },
    {
        "title": "'思想在书里'≠'本人撰写成书'",
        "desc": "《穷查理宝典》是芒格演讲汇编; 《邓普顿教你逆向投资》由其孙女劳伦·邓普顿执笔; 《巴菲特致股东的信》是信件汇编。书名冠名很容易误导读者以为是本人撰写。",
        "url": "",
    },
    {
        "title": "中译名误配经典",
        "desc": "是川银藏《股市之神》≠ 科斯托拉尼《股市神猎手》; 马尔基尔《漫步华尔街》≠ 林奇 One Up on Wall Street(《彼得·林奇的成功投资》); 后者与帕特·多尔西《股市真规则》也常被混作一本。",
        "url": "",
    },
    {
        "title": "《征服市场的人》不是西蒙斯写的",
        "desc": "原书《The Man Who Solved the Market》(2019), 作者是《华尔街日报》记者 Gregory Zuckerman。企鹅兰登书目和台湾馆藏目录均可查, 西蒙斯本人不配合采访。",
        "url": "https://www.penguinrandomhouse.com/books/555382/the-man-who-solved-the-market-by-gregory-zuckerman/",
    },
    {
        "title": "卡拉曼《安全边际》绝版了30年",
        "desc": "1991年出版后从未再版, 无正式中文版。二手市场一本超1000美元, 是价值投资者的'圣杯'。",
        "url": "",
    },
]


# --- 实用阅读指南 ---
READING_GUIDES = [
    {
        "topic": "📊 交易纪律与心理",
        "path": [
            ("《股票作手回忆录》", "当人性故事读, 市场最经典的教训书"),
            ("→ 斯波朗迪《专业投机原理》", "风险报酬比+纪律, 职业操盘框架"),
            ("→ 施瓦格《金融怪杰》", "17位交易冠军访谈录, 涵盖上面所有无著述大佬"),
            ("→ 埃尔德《以交易为生》", "三重框架+心理三支柱"),
            ("→ 道格拉斯《交易心理分析》", "概率思维+信念结构, 交易心理学集大成"),
        ],
        "url": "https://book.douban.com/subject/5980568/",
    },
    {
        "topic": "🌍 宏观与风险",
        "path": [
            ("索罗斯《超越金融》", "比《金融炼金术》好懂得多, 反身性理论入门"),
            ("→ 达利欧《债务危机》", "漂亮去杠杆vs丑陋去杠杆, 长期债务周期"),
            ("→ 塔勒布《反脆弱》", "比《黑天鹅》更系统, 杠铃策略"),
        ],
        "url": "https://book.douban.com/subject/30448294/",
    },
    {
        "topic": "💰 基本面/价值投资",
        "path": [
            ("格雷厄姆《聪明的投资者》", "价值投资入门, 安全边际+市场先生"),
            ("→ 费雪《怎样选择成长股》", "闲聊法+成长股15要点"),
            ("→ 林奇《彼得·林奇的成功投资》", "生活中发现10倍股, 最通俗的基本面书"),
            ("→ 马克斯《投资最重要的事》", "周期思维+风险控制, 必读!"),
        ],
        "url": "https://book.douban.com/subject/1070133/",
    },
    {
        "topic": "⚠️ 选书注意事项",
        "path": [
            ("别把'写过书'当成'操盘厉害'的代理变量", "业绩最硬的一批实战者(德鲁肯米勒/西蒙斯)恰恰都不写书"),
            ("著述最勤的江恩", "其宣称的收益缺乏可验证记录"),
            ("选书先明确想学什么", "交易纪律→心理书; 基本面→格雷厄姆系; 宏观→达利欧/塔勒布"),
        ],
        "url": "",
    },
]


# ═══════════════════════════════════════════════════════════════
# 🎨 UI 构建
# ═══════════════════════════════════════════════════════════════

def _build_dava_views_tab(nb_notebook, root=None):
    """在主线资金 Notebook 里加: 🌟名人堂"""
    tab = tk.Frame(nb_notebook, bg="#FAFAFA")
    nb_notebook.add(tab, text="  🌟 名人堂  ")

    banner = tk.Frame(tab, bg="#E65100", height=44)
    banner.pack(fill=tk.X, padx=6, pady=(6, 4))
    banner.pack_propagate(False)
    tk.Label(banner, text="🌟 名人堂 · 操盘手 vs 投资家 · 代表作/署名坑/阅读指南",
             font=("Microsoft YaHei", 12, "bold"),
             bg="#E65100", fg="white").pack(side=tk.LEFT, padx=14)

    # 字体 + 背景调节
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
    _date_lbl = tk.Label(ctrl, text="📅 数据来源: 中信出版/上高金/央视网/经济参考报 2026-11-13",
                         bg="#FAFAFA", fg="#999", font=("", 8))
    _date_lbl.pack(side=tk.RIGHT, padx=8)

    # 分类 Notebook
    nb_inner = ttk.Notebook(tab)
    nb_inner.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    refs = {"size_var": size_var, "bg_var": bg_var, "text_widgets": []}

    def _make_scrollable_tab(parent, bg="#FAFAFA"):
        """🆕 可滚动 Tab — Canvas + 滚动条 + 内部 Frame"""
        outer = tk.Frame(parent, bg=bg)
        canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=bg)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        # 内部 Frame 宽度跟随 Canvas 宽度拉伸
        def _on_canvas_config(e):
            canvas.itemconfigure(inner_id, width=e.width)
        canvas.bind("<Configure>", _on_canvas_config)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 鼠标滚轮 (Windows/macOS)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        def _on_mousewheel_linux_up(event): canvas.yview_scroll(-1, "units")
        def _on_mousewheel_linux_down(event): canvas.yview_scroll(1, "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner.bind("<MouseWheel>", _on_mousewheel)
        # 让 inner 也能接收滚轮事件 (递归绑定子控件)
        def _bind_wheel_recursive(w):
            try: w.bind("<MouseWheel>", _on_mousewheel)
            except Exception: pass
            try: w.bind("<Button-4>", _on_mousewheel_linux_up)
            except Exception: pass
            try: w.bind("<Button-5>", _on_mousewheel_linux_down)
            except Exception: pass
            for child in w.winfo_children():
                _bind_wheel_recursive(child)
        inner.bind("<Configure>", lambda e: _bind_wheel_recursive(inner))
        # 首次 render 后也绑定一次
        outer.after(100, lambda: _bind_wheel_recursive(inner))
        return inner

    # === Tab 1: 🎯 亲笔操盘手 ===
    t1_outer = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t1_outer, text="  🎯 亲笔操盘手  ")
    t1 = _make_scrollable_tab(t1_outer)
    for person in TRADERS:
        _make_person_card(t1, person, refs)

    # === Tab 2: ⚖️ 介于两派 ===
    t2_outer = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t2_outer, text="  ⚖️ 介于两派  ")
    t2 = _make_scrollable_tab(t2_outer)
    for person in BETWEEN:
        _make_person_card(t2, person, refs)

    # === Tab 3: 💰 投资家 ===
    t3_outer = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t3_outer, text="  💰 投资家  ")
    t3 = _make_scrollable_tab(t3_outer)
    for person in INVESTORS:
        _make_person_card(t3, person, refs)

    # === Tab 4: 🕊️ 名气大却无书 ===
    t4 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t4, text="  🕊️ 名气大却无书  ")
    _make_no_books_tab(t4, refs)

    # === Tab 5: 🚨 署名坑 ===
    t5 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t5, text="  🚨 署名坑  ")
    _make_pitfalls_tab(t5, refs)

    # === Tab 6: 📖 阅读指南 ===
    t6 = tk.Frame(nb_inner, bg="#FAFAFA"); nb_inner.add(t6, text="  📖 阅读指南  ")
    _make_reading_guide_tab(t6, refs)

    # 应用样式
    def _apply_style(_e=None):
        sz = size_var.get(); bg = bg_var.get()
        for tw in refs["text_widgets"]:
            try: tw.config(font=("", sz), bg=bg)
            except Exception: pass
    size_cb.bind("<<ComboboxSelected>>", _apply_style)
    bg_cb.bind("<<ComboboxSelected>>", _apply_style)

    return tab


def _open_url(url):
    """双击打开链接"""
    if url:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def _make_book_row(parent, book):
    """单行书籍卡片 — 书名+年份+备注+双击打开"""
    row = tk.Frame(parent, bg=parent.cget("bg"))
    row.pack(fill=tk.X, padx=6, pady=1)

    # 书名 (蓝, 下划线可点击感)
    title_txt = f"📖 {book['title']}"
    if book.get("title_en"):
        title_txt += f"  ({book['title_en']})"
    if book.get("year"):
        title_txt += f"  [{book['year']}]"
    lbl = tk.Label(row, text=title_txt, bg=parent.cget("bg"),
                   fg="#1565C0", font=("", 9, "underline"), cursor="hand2")
    lbl.pack(side=tk.LEFT, anchor="w")

    # 备注
    if book.get("note"):
        note_lbl = tk.Label(row, text=f" — {book['note']}", bg=parent.cget("bg"),
                            fg="#616161", font=("", 8))
        note_lbl.pack(side=tk.LEFT, anchor="w")

    if book.get("url"):
        lbl.bind("<Double-Button-1>", lambda e, u=book["url"]: _open_url(u))
        lbl.config(fg="#1976D2")  # 蓝色表示可点击


def _make_person_card(parent, person, refs):
    """人物卡片 — 标题 + 逻辑 + 代表作 + 链接"""
    accent = person.get("accent", "#FFF3E0")
    card = tk.Frame(parent, bg=accent, highlightthickness=1, highlightbackground=accent)
    card.pack(fill=tk.X, padx=4, pady=4)

    # 标题行
    head = tk.Frame(card, bg=accent)
    head.pack(fill=tk.X, padx=10, pady=(8, 2))
    name_lbl = tk.Label(head, text=f"👤 {person['name']}", font=("Microsoft YaHei", 11, "bold"),
                        bg=accent, fg="#BF360C")
    name_lbl.pack(side=tk.LEFT)
    if person.get("name_en"):
        tk.Label(head, text=f"  ({person['name_en']})", font=("", 9),
                 bg=accent, fg="#5D4037").pack(side=tk.LEFT)
    if person.get("years"):
        tk.Label(head, text=f"  {person['years']}", font=("", 8),
                 bg=accent, fg="#8D6E63").pack(side=tk.LEFT)
    tk.Label(head, text=f"  ·  {person['tagline']}", font=("", 9),
             bg=accent, fg="#6D4C41").pack(side=tk.LEFT, padx=4)

    # 内部内容区
    inner = tk.Frame(card, bg="#FAFAFA")
    inner.pack(fill=tk.X, padx=4, pady=(0, 6))

    st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=8, pady=6, spacing1=2, spacing3=4,
                                   height=4)
    st.pack(fill=tk.X)

    st.tag_configure("logic_sub", font=("", 9, "bold"), foreground="#BF360C", spacing1=4)
    st.tag_configure("logic", foreground="#424242")
    st.tag_configure("book_sub", font=("", 9, "bold"), foreground="#2E7D32", spacing1=4)
    st.tag_configure("pitfall_sub", font=("", 9, "bold"), foreground="#C62828", spacing1=4)
    st.tag_configure("pitfall", foreground="#6A1B9A", font=("", 8, "italic"))
    st.tag_configure("link_sub", font=("", 9, "bold"), foreground="#1565C0", spacing1=4)

    # 逻辑
    st.insert(tk.END, "🧠 核心逻辑:\n", "logic_sub")
    st.insert(tk.END, f"  {person['logic']}\n", "logic")

    # 坑
    if person.get("pitfall"):
        st.insert(tk.END, "\n🚨 署名坑:\n", "pitfall_sub")
        st.insert(tk.END, f"  {person['pitfall']}\n", "pitfall")

    st.config(state=tk.DISABLED, height=3)
    refs["text_widgets"].append(st)

    # 书籍行 (独立 frame, 可双击)
    if person.get("books"):
        book_frame = tk.Frame(inner, bg="#FAFAFA")
        book_frame.pack(fill=tk.X, pady=(2, 4))
        tk.Label(book_frame, text="📚 代表作:", bg="#FAFAFA", fg="#2E7D32",
                 font=("", 9, "bold")).pack(anchor="w", padx=6)
        for book in person["books"]:
            _make_book_row(book_frame, book)

    # 链接行
    if person.get("links"):
        link_frame = tk.Frame(inner, bg="#FAFAFA")
        link_frame.pack(fill=tk.X, pady=(0, 6))
        for label, url in person["links"]:
            if url:
                lk = tk.Label(link_frame, text=f"  🔗 {label}", bg="#FAFAFA",
                              fg="#1565C0", font=("", 8, "underline"), cursor="hand2")
                lk.pack(side=tk.LEFT, padx=(6, 2))
                lk.bind("<Double-Button-1>", lambda e, u=url: _open_url(u))

    return card


def _make_no_books_tab(parent, refs):
    """名气大却没写书的 — 简洁卡片"""
    st = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=10, pady=8, spacing1=2, spacing3=4)
    st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    st.tag_configure("h1", font=("", 11, "bold"), foreground="#C62828", spacing1=6, spacing3=4)
    st.tag_configure("name", font=("", 10, "bold"), foreground="#1565C0")
    st.tag_configure("note", foreground="#424242")
    st.tag_configure("src", foreground="#9E9E9E", font=("", 8, "italic"))
    st.tag_configure("hint", foreground="#6A1B9A", font=("", 9))
    st.tag_configure("link", foreground="#1565C0", font=("", 9, "underline"))

    st.insert(tk.END, "🔥 业绩最硬的一批实战者恰恰都不写书\n", "h1")
    st.insert(tk.END, "东西靠《金融怪杰》(1989, 杰克·施瓦格)访谈录留下来 — 共17位顶级交易员深度访谈\n\n", "hint")

    for p in NO_BOOKS:
        st.insert(tk.END, f"👤 {p['name']}\n", "name")
        st.insert(tk.END, f"  {p['note']}\n", "note")
        if p.get("source"):
            st.insert(tk.END, f"  📅 来源: {p['source']}\n", "src")
        if p.get("url"):
            st.insert(tk.END, f"  🔗 {p['url']}  (双击打开)\n", "link")
        st.insert(tk.END, "\n")

    def _on_link_click(event):
        stg = st.tag_nextrange("link", tk.SEL_FIRST)
        if stg:
            text = st.get(stg[0], stg[1])
            url = text.strip().replace("🔗 ", "").replace(" (双击打开)", "")
            if url.startswith("http"):
                _open_url(url)
    st.bind("<Double-Button-1>", _on_link_click)

    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)


def _make_pitfalls_tab(parent, refs):
    """署名坑 — 重点警示"""
    card = tk.Frame(parent, bg="#FFEBEE", highlightthickness=1, highlightbackground="#EF9A9A")
    card.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    inner = tk.Frame(card, bg="#FAFAFA")
    inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=10, pady=8, spacing1=2, spacing3=5)
    st.pack(fill=tk.BOTH, expand=True)

    st.tag_configure("h1", font=("", 12, "bold"), foreground="#C62828", spacing1=8, spacing3=4)
    st.tag_configure("h2", font=("", 10, "bold"), foreground="#BF360C", spacing1=6)
    st.tag_configure("p", foreground="#424242")
    st.tag_configure("tip", foreground="#6A1B9A", font=("", 9))
    st.tag_configure("link", foreground="#1565C0", font=("", 9, "underline"))

    st.insert(tk.END, "🚨 三个最容易踩的署名坑\n\n", "h1")
    for i, p in enumerate(PITFALLS, 1):
        st.insert(tk.END, f"{i}. {p['title']}\n", "h2")
        st.insert(tk.END, f"  {p['desc']}\n", "p")
        if p.get("url"):
            st.insert(tk.END, f"  🔗 {p['url']}  (双击打开)\n", "link")
        st.insert(tk.END, "\n")

    def _on_link_click(event):
        stg = st.tag_nextrange("link", tk.SEL_FIRST)
        if stg:
            text = st.get(stg[0], stg[1])
            url = text.strip().replace("🔗 ", "").replace(" (双击打开)", "")
            if url.startswith("http"):
                _open_url(url)
    st.bind("<Double-Button-1>", _on_link_click)

    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)


def _make_reading_guide_tab(parent, refs):
    """实用阅读指南"""
    st = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=("", 9), bg="#FAFAFA", fg="#212121",
                                   bd=0, relief=tk.FLAT, padx=10, pady=8, spacing1=2, spacing3=5)
    st.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    st.tag_configure("h1", font=("", 12, "bold"), foreground="#1565C0", spacing1=8, spacing3=4)
    st.tag_configure("h2", font=("", 10, "bold"), foreground="#2E7D32", spacing1=6)
    st.tag_configure("step", foreground="#BF360C", font=("", 9, "bold"))
    st.tag_configure("desc", foreground="#616161")
    st.tag_configure("hint", foreground="#6A1B9A", font=("", 9, "italic"))

    st.insert(tk.END, "📖 不太顺耳但更实用的判断: 别把'写过书'当成'操盘厉害'的代理变量\n\n", "h1")
    st.insert(tk.END, "业绩最硬的一批实战者恰恰都不写书 — 德鲁肯米勒/都铎·琼斯/西蒙斯\n", "hint")
    st.insert(tk.END, "反过来, 著述最勤的江恩, 其宣称的收益缺乏可验证记录\n\n", "hint")
    st.insert(tk.END, "所以选书先明确想学什么:\n\n")

    for guide in READING_GUIDES:
        st.insert(tk.END, f"🔶 {guide['topic']}\n", "h2")
        for i, (step, desc) in enumerate(guide["path"], 1):
            st.insert(tk.END, f"  {step}\n", "step")
            if desc:
                st.insert(tk.END, f"      → {desc}\n", "desc")
        st.insert(tk.END, "\n")

    # 底部免责
    st.insert(tk.END, "═" * 50 + "\n", "hint")
    st.insert(tk.END, "📅 数据来源: 中信出版书单 / 上海高级金融学院 / 央视网 / 经济参考报 (2026-11-13)\n", "desc")
    st.insert(tk.END, "  收益/名次数字多为传记与媒体口径, 非经审计净值序列, 不宜横向比较\n\n", "desc")
    st.insert(tk.END, "⚠️ 免责声明: 以上内容基于公开数据, 仅供参考, 不构成投资建议\n", "hint")

    st.config(state=tk.DISABLED)
    refs["text_widgets"].append(st)

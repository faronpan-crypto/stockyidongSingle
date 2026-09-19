#!/usr/bin/env python3
"""
股票舆情词云 v3 — 股票名/板块名/ETF名 三级过滤
"""
import json
import re
import sqlite3
import sys

sys.path.insert(0, '/Users/faronpan/Agent/stockyidong_project/src')
sys.path.insert(0, '/tmp/pylibs')

from collections import Counter

import matplotlib

matplotlib.use('Agg')
import jieba
from wordcloud import WordCloud

DB_PATH = '/Users/faronpan/Agent/stockyidong_project/data/stock_analysis.db'
FONT_PATH = '/System/Library/Fonts/Supplemental/Hiragino Sans GB.ttc'

# ── 1. 构建词库 ───────────────────────────────────────────────
print("📦 构建词库...")

stock_names = set()   # 股票名称
board_names = set()   # 板块名称
etf_names   = set()   # ETF名称

# ① 从 stock_logic 提取股票名
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT DISTINCT stock_name FROM stock_logic WHERE stock_name IS NOT NULL AND stock_name != ''")
for row in cur.fetchall():
    n = row[0].strip()
    if 2 <= len(n) <= 10:
        stock_names.add(n)
print(f"  ✅ 数据库股票: {len(stock_names)} 只")

# ② 从 stock_analysis word_details 提取
cur.execute("SELECT word_details FROM stock_analysis WHERE word_details IS NOT NULL LIMIT 200")
for row in cur.fetchall():
    try:
        for item in json.loads(row[0]):
            n = item.get('name', '')
            if n and 2 <= len(n) <= 12 and re.search(r'[\u4e00-\u9fff]', n):
                stock_names.add(n)
    except:
        pass
print(f"  ✅ 累计股票名: {len(stock_names)} 只")
conn.close()

# ③ 通用板块词（硬编码，覆盖主流+最新热点）
boards = [
    # 科技/AI
    "AI","人工智能","算力","光模块","CPO","光通信","PCB","半导体","芯片","集成电路",
    "先进封装","HBM","存储芯片","AI芯片","算力租赁","数据中心","液冷","云计算",
    "AI眼镜","AI手机","AIPC","机器人","工业母机","机器视觉","智能驾驶","车联网",
    "无人驾驶","算力","算力概念","脑机接口",
    # 新能源
    "新能源","锂电","锂离子","固态电池","钠离子","钙钛矿","HJT","TOPCon","光伏",
    "风电","储能","虚拟电厂","充电桩","氢能源","氢能","电网设备","特高压",
    # 消费/医药
    "医药","创新药","中药","医疗器械","眼科","牙科","辅助生殖","医疗反腐",
    "消费","零售","食品饮料","白酒","预制菜","新零售","电商","跨境电商",
    "美容","化妆品","医美","宠物","养老","银发经济","育婴",
    # 周期/制造
    "房地产","地产链","建材","家电","家具","装修装饰","汽车","重卡","商用车",
    "船舶","大飞机","军工","商业航天","低空经济","无人机","eVTOL","通用航空",
    "化工","化学制品","化纤","油气","石油","天然气","煤炭","有色金属","铜",
    "黄金","稀土","锗","镓","钨","小金属","钢铁","铁矿石","航运","油运","海运",
    # 金融/政策
    "券商","保险","银行","多元金融","金融科技","数字货币","跨境支付","征信",
    "国资","央企","地方国企","一带一路","出口优势","外销","内循环",
    # 农业/食品
    "农业","种业","猪肉","鸡肉","水产养殖","宠物食品","转基因",
    # 其他热点
    "业绩增长","高股息","红利","国企改革","重组","摘帽","次新",
    "室温超导","可控核聚变","量子科技","6G","5.5G","卫星互联网","星闪",
    "固态存储","折叠屏","屏下指纹","MR","AR","VR","游戏","短剧","影视",
    "教育","体育","旅游","酒店","航空","机场","物流","快递","冷链",
    "环保","碳中和","碳交易","新型电力","新型城镇化","城中村","水利",
    "网络安全","数据安全","信创","操作系统","基础软件","网络安全",
    # 通用行业
    "电力","公用事业","交通运输","建筑","建筑装饰","园林工程","环保工程",
    "仪器仪表","通用设备","专用设备","电机","电气自动化","通信设备",
    "光学光电子","元件","光学","消费电子","电子元件","印制电路板",
    "黑色金属","有色","钢铁","贵金属","工业金属","小金属","非金属材料",
]
board_names = set(b for b in boards if b)
print(f"  ✅ 板块词: {len(board_names)} 个")

# ④ ETF基金词（硬编码主流ETF）
etf_list = [
    "创业板ETF","科创50ETF","沪深300ETF","中证500ETF","中证1000ETF",
    "中证A50ETF","中证A500ETF","中证2000ETF","北证50ETF","上证50ETF",
    "上证指数ETF","深证100ETF","MSCI中国ETF","纳斯达克ETF","标普ETF",
    "日经ETF","恒生ETF","恒生科技ETF","恒生医疗ETF","国企改革ETF",
    "红利ETF","红利低波ETF","中证红利ETF","价值ETF","成长ETF",
    "消费ETF","医药ETF","医疗ETF","生物医药ETF","创新药ETF","中药ETF",
    "新能源ETF","光伏ETF","锂电ETF","碳中和ETF","环境治理ETF",
    "半导体ETF","芯片ETF","集成电路ETF","算力ETF","AI算力ETF",
    "机器人ETF","工业母机ETF","智能汽车ETF","汽车ETF","军工ETF",
    "国防ETF","油气ETF","能源ETF","煤炭ETF","有色ETF","黄金ETF",
    "食品饮料ETF","农业ETF","养殖ETF","房地产ETF","金融ETF","券商ETF",
    "银行ETF","保险主题ETF","科技ETF","科技50ETF","通信ETF",
    "游戏ETF","传媒ETF","教育ETF","旅游ETF","体育ETF","环保ETF",
]
etf_names = set(e for e in etf_list)
print(f"  ✅ ETF词: {len(etf_names)} 个")

# 合并词库
word_lib = stock_names | board_names | etf_names
print(f"  📊 词库合计: {len(word_lib)} 个词")

# ── 2. 读取资讯 ───────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT content FROM news_info ORDER BY id DESC LIMIT 300")
rows = cur.fetchall()
conn.close()
all_text = " ".join(r[0] or "" for r in rows)
print(f"\n📰 读取资讯 {len(rows)} 条")

# ── 3. jieba分词 ───────────────────────────────────────────────
seg_text = " ".join(jieba.cut(all_text))
words = seg_text.split()
print(f"  分词总数: {len(words)}")

# ── 4. 三级过滤 ───────────────────────────────────────────────
# 预过滤：长度>=2，必须含中文，且不是纯ASCII符号/纯数字
STOPWORDS = {
    "相关","作者","时间","评论","点赞","浏览","阅读","回复","点击","进入",
    "发布","来源","编辑","发表","关注","粉丝","首页","推荐","热门",
    "精华","加油","今日","昨天","今年","去年","明天","收盘",
    "开盘","最高","最低","涨停","跌停","成交","成交额","成交量","换手率",
    "市值","流通","总市","涨跌幅","振幅","上涨","下跌","持平","涨幅","跌幅",
    "我们","他们","这个","那个","什么","怎么","为什么","可以","不是","就是",
    "但是","因为","所以","如果","还是","已经","没有","一个","这些","那些",
    "自己","现在","应该","可能","需要","开始","进行","完成","问题","情况",
    "公司","中国","美国","市场","行情","投资","策略","分享","内容",
    "这是","那样","这里","那里","如何","这样","为何","只是","也是","都是","会是","只能","才会","正是","总是",
    "正在","之前","之后","之间","以上","以下","左右","大约",
    "明日","昨日","当天","盘中","盘后",
    "将要","即将",
    "投资有风险","风险提示","免责声明","本文仅供","据此操作","风险自担",
}
# 过滤含数字的股票代码类词（如 sh600105, 600105 等）
code_pattern = re.compile(r'^[a-z]{2}\d{6}$', re.IGNORECASE)

matched = []
for w in words:
    if len(w) < 2:
        continue
    if w in STOPWORDS:
        continue
    if code_pattern.match(w):
        continue
    if not re.search(r'[\u4e00-\u9fff]', w):
        continue
    # 纯数字/符号
    if re.fullmatch(r'[\d\.\-\+\%\/\(\)\[\]\{\}\,\.\。\，\！\？]+', w):
        continue
    if w in word_lib:
        matched.append(w)

freq = Counter(matched)
print(f"  ✅ 命中词库: {len(freq)} 个不同词")

if len(freq) < 10:
    print("  ⚠️ 命中不足，回退到含中文词过滤（去掉停用词）")
    raw = [w for w in words if len(w) >= 2
           and re.search(r'[\u4e00-\u9fff]', w)
           and w not in STOPWORDS
           and not code_pattern.match(w)]
    freq = Counter(raw)
    print(f"  回退后词数: {len(freq)}")

# ── 5. 生成词云 ────────────────────────────────────────────────
# 手动颜色函数：股票名→蓝色，板块→绿色，ETF→橙色
def get_color(word, **kwargs):
    if word in etf_names:
        return f"hsl({25 + random.randint(0,20)}, 85%, 50%)"   # 橙色
    if word in board_names:
        return f"hsl({130 + random.randint(0,20)}, 70%, 45%)" # 绿色
    # 股票默认蓝色渐变
    return f"hsl({210 + random.randint(0,30)}, 80%, {45 + random.randint(0,15)}%)"

wc = WordCloud(
    font_path=FONT_PATH,
    width=1600,
    height=900,
    background_color='white',
    max_words=300,
    max_font_size=160,
    min_font_size=12,
    prefer_horizontal=0.65,
    random_state=42,
)
wc.generate_from_frequencies(freq)

out_path = '/tmp/news_wordcloud_v2.png'
wc.to_file(out_path)
print(f"\n✅ 词云已保存: {out_path}")

print("\n🔝 TOP 40 高频词:")
for w, c in freq.most_common(40):
    tag = "🏛️ETF" if w in etf_names else ("📊板块" if w in board_names else "🏢股票")
    print(f"  {tag} {w:15s} ×{c}")

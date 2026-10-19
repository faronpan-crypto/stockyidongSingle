# -*- coding: utf-8 -*-
"""
📊 基金持仓 Tab — 主流基金重仓股 + 板块聚合 Top100

数据源:
  - akshare.fund_portfolio_hold_em(date='20261')  # 东方财富基金重仓股
  - 主流主动权益基金 Top20 持仓 (种子兜底)

结构:
  上半: 主流基金卡片 (基金名 + Top5 持仓股, 双击股票名弹日K)
  下半: 板块聚合 (按板块归类持仓市值最大的 Top 股票)
"""

import tkinter as tk
import tkinter.ttk as ttk
import threading
import traceback
import time
import json
import os
from datetime import datetime

# ── 🎨 配色 ──
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

# ── 🏆 主流基金 + 每只基金真实 Top5 代表持仓 (种子数据, 保证行业多样性) ──
# 格式: [基金代码, 基金简称, 行业标签, [(code6, name), (code6, name), ...]]
_FUND_TOP_HOLDINGS = [
    ("161725", "招商中证白酒",   "白酒",   [
        ("sh600519","贵州茅台"),("sz000858","五粮液"),("sh600809","山西汾酒"),
        ("sz002304","洋河股份"),("sz000568","泸州老窖")]),
    ("005827", "易方达蓝筹精选", "消费白马", [
        ("sh600519","贵州茅台"),("sh601888","中国中免"),("sz000333","美的集团"),
        ("sh600036","招商银行"),("sz300750","宁德时代")]),
    ("110011", "易方达中小盘",   "消费成长", [
        ("sz002475","立讯精密"),("sz300750","宁德时代"),("sh601318","中国平安"),
        ("sz000651","格力电器"),("sz000333","美的集团")]),
    ("163406", "兴全合润",       "均衡",   [
        ("sh600519","贵州茅台"),("sh600036","招商银行"),("sz300750","宁德时代"),
        ("sz002594","比亚迪"),("sh601318","中国平安")]),
    ("001594", "天弘中证电子",   "电子",   [
        ("sz002415","海康威视"),("sh603986","兆易创新"),("sz002230","科大讯飞"),
        ("sz300033","同花顺"),("sz002281","光迅科技")]),
    ("159995", "华夏芯片ETF",    "半导体", [
        ("sh603986","兆易创新"),("sh688256","寒武纪"),("sz002049","紫光国微"),
        ("sh688012","中微公司"),("sz002371","北方华创")]),
    ("515030", "新能源车ETF",    "新能源", [
        ("sz300750","宁德时代"),("sz002594","比亚迪"),("sz300014","亿纬锂能"),
        ("sh601012","隆基绿能"),("sz002460","赣锋锂业")]),
    ("159949", "创业板ETF",      "成长",   [
        ("sz300750","宁德时代"),("sz300015","爱尔眼科"),("sz300760","迈瑞医疗"),
        ("sz300059","东方财富"),("sz300014","亿纬锂能")]),
    ("512880", "证券ETF",        "券商",   [
        ("sh600030","中信证券"),("sh601688","华泰证券"),("sh601211","国泰君安"),
        ("sh600837","海通证券"),("sz300059","东方财富")]),
    ("513100", "纳指ETF",        "美股科技", [
        ("AAPL","苹果"),("MSFT","微软"),("NVDA","英伟达"),
        ("TSLA","特斯拉"),("GOOG","谷歌")]),
    ("164906", "交银中证中概",   "中概",   [
        ("9988","阿里巴巴"),("9618","京东"),("9888","百度"),
        ("3690","美团"),("9999","网易")]),
    ("161005", "富国天惠成长",   "均衡",   [
        ("sh600519","贵州茅台"),("sz300750","宁德时代"),("sz002415","海康威视"),
        ("sh600036","招商银行"),("sz002594","比亚迪")]),
    ("000961", "天弘沪深300",    "宽基",   [
        ("sh600519","贵州茅台"),("sh601318","中国平安"),("sz000858","五粮液"),
        ("sh600036","招商银行"),("sz300750","宁德时代")]),
    ("512660", "军工ETF",        "军工",   [
        ("sh600893","航发动力"),("sh600760","中航沈飞"),("sh600118","中国卫星"),
        ("sz000768","中航西飞"),("sh600372","中航机载")]),
    ("512200", "房地产ETF",      "地产",   [
        ("sz000002","万科A"),("sh600048","保利发展"),("sh601155","新城控股"),
        ("sh600585","海螺水泥"),("sz300737","科顺股份")]),
    ("512010", "医药ETF",        "医药",   [
        ("sh600276","恒瑞医药"),("sz000538","云南白药"),("sz300760","迈瑞医疗"),
        ("sz002007","华兰生物"),("sh603259","药明康德")]),
    ("159869", "游戏ETF",        "传媒",   [
        ("sz002555","三七互娱"),("sz300418","昆仑万维"),("sz002230","科大讯飞"),
        ("sz300454","深信服"),("sz300750","宁德时代")]),
    ("512400", "有色金属ETF",    "资源",   [
        ("sh600547","山东黄金"),("sh601899","紫金矿业"),("sh600489","中金黄金"),
        ("sz000878","云南铜业"),("sh601600","中国铝业")]),
    ("512170", "医疗ETF",        "医疗",   [
        ("sz300015","爱尔眼科"),("sz300760","迈瑞医疗"),("sh600276","恒瑞医药"),
        ("sz002007","华兰生物"),("sh603259","药明康德")]),
    ("512890", "红利低波ETF",    "红利",   [
        ("sh600036","招商银行"),("sh601398","工商银行"),("sh601939","建设银行"),
        ("sh601628","中国人寿"),("sh601318","中国平安")]),
]

# ── 📚 基金指南: 风格分类 + 介绍 + 持仓 + 择时笔记 ──
# 分类: Beta宽基 / Alpha主动 / 成长风格 / 周期行业 / 红利价值 / 行业主题
_FUND_GUIDE = [
    {
        "cat": "🌐 Beta宽基 (赚市场β)",
        "cat_desc": "纯指数复制,费率低(0.15%~0.5%),透明度高,适合定投/底仓. 核心逻辑: 国运+流动性",
        "funds": [
            {"name":"沪深300ETF","code":"510300","style":"宽基大盘",
             "intro":"A股核心300家龙头,含茅台/宁德/招行/平安,代表中国经济大盘",
             "holdings":[("sh600519","贵州茅台"),("sz300750","宁德时代"),("sh600036","招商银行"),("sh601318","中国平安"),("sz000858","五粮液")],
             "timing":"✅ M2增速上行+社融存量同比>10%时加仓\n✅ 美联储加息暂停/转向时加大配置\n❌ CPI-PPI剪刀差收窄至0以下时减仓\n📅 每月定投: 25号前后(股指期权交割日)波动大"},
            {"name":"中证500ETF","code":"510500","style":"中盘成长",
             "intro":"剔除沪深300后的中型公司,覆盖先进制造/新材料/医药,弹性大于300",
             "holdings":[("sz002415","海康威视"),("sh600570","恒生电子"),("sz300014","亿纬锂能"),("sz002024","苏宁易购"),("sh601989","中国重工")],
             "timing":"✅ 中小企业PMI>50且环比上升时买\n✅ 货币宽松(R007<2%)利好小票\n❌ 大盘蓝筹疯涨时500往往掉队"},
            {"name":"中证1000ETF","code":"512100","style":"小盘弹性",
             "intro":"最小的1000只股票,微盘股代表,高波动高收益,适合风险偏好高的投资者",
             "holdings":[("sz300418","昆仑万维"),("sz002230","科大讯飞"),("sz300454","深信服"),("sz300750","宁德时代"),("sh688036","传音控股")],
             "timing":"✅ 市场情绪冰点(涨停数<10)时左侧布局\n✅ 政策密集出台(如 Platform经济支持)时\n❌ 连续大涨3天+成交额破2万亿时追高风险大"},
            {"name":"创业板ETF","code":"159949","style":"科技成长",
             "intro":"深交所创新企业,新能源+医药+科技,宁德/迈瑞/爱尔为权重",
             "holdings":[("sz300750","宁德时代"),("sz300760","迈瑞医疗"),("sz300015","爱尔眼科"),("sz300014","亿纬锂能"),("sz300059","东方财富")],
             "timing":"✅ 新能源汽车月度销量同比>30%时\n✅ 创新药审批加速+医保谈判利好时\n❌ 美联储加息周期中科技股承压"},
            {"name":"科创50ETF","code":"588000","style":"硬科技",
             "intro":"上交所科创板,半导体/AI/生物医药硬科技,中芯/寒武纪为权重",
             "holdings":[("sh688981","中芯国际"),("sh688256","寒武纪"),("sh688012","中微公司"),("sh688111","金山办公"),("sh688008","澜起科技")],
             "timing":"✅ 国产替代政策加码+半导体周期见底时\n✅ AI大模型落地应用密集发布时\n❌ 美国对华半导体出口管制升级时短期承压"},
        ]
    },
    {
        "cat": "🏆 Alpha主动 (赚超额α)",
        "cat_desc": "基金经理选股/择时能力,费率1%~1.5%,适合没时间研究个股的投资者. 关键: 选对基金经理 > 选对赛道",
        "funds": [
            {"name":"易方达蓝筹精选","code":"005827","style":"消费+金融+科技",
             "intro":"张坤管理(已卸任但风格延续),茅台/五粮液/美华为核心持仓,长期持有消费白马",
             "holdings":[("sh600519","贵州茅台"),("sz000858","五粮液"),("sz000333","美的集团"),("sh601888","中国中免"),("sh600036","招商银行")],
             "timing":"✅ 白酒批价企稳回升时定投\n✅ 消费升级数据社零同比>8%时加仓\n❌ 白酒行业负面舆情(塑化剂/消费税)时回避"},
            {"name":"兴全合润","code":"163406","style":"均衡配置",
             "intro":"谢治宇管理,股债平衡+行业分散,下跌市抗跌,上涨市跟得上,适合保守型",
             "holdings":[("sh600519","贵州茅台"),("sh600036","招商银行"),("sz300750","宁德时代"),("sz002594","比亚迪"),("sh601318","中国平安")],
             "timing":"✅ 看不清市场方向时买均衡型\n✅ 股债性价比(沪深300盈利收益率/10Y国债)>2.5时加大仓位\n❌ 单边大牛市中可能跑输主题基金"},
            {"name":"富国天惠成长","code":"161005","style":"成长精选",
             "intro":"朱少醒管理15年+穿越牛熊,精选成长股,换手率低,长期持有",
             "holdings":[("sh600519","贵州茅台"),("sz300750","宁德时代"),("sz002415","海康威视"),("sh600036","招商银行"),("sz002594","比亚迪")],
             "timing":"✅ 市场恐慌下跌时反向买入\n✅ 基金连续3年跑输沪深300时可能是布局良机(均值回归)\n❌ 明星基金经理离职时谨慎"},
            {"name":"交银新成长","code":"519736","style":"成长+红利",
             "intro":"王崇管理,平衡成长确定性和估值安全边际,偏好低估值成长股",
             "holdings":[("sz000651","格力电器"),("sh600036","招商银行"),("sz300750","宁德时代"),("sh600887","伊利股份"),("sz002475","立讯精密")],
             "timing":"✅ 风格切换期(价值→成长或成长→价值)配置均衡型\n✅ 市场风格不明朗时的避风港"},
        ]
    },
    {
        "cat": "🚀 成长风格 (高弹性)",
        "cat_desc": "押注高增长赛道,新能源/半导体/AI/创新药. 高波动高收益,适合能持有3年+的投资者",
        "funds": [
            {"name":"新能源车ETF","code":"515030","style":"新能源",
             "intro":"宁德/比亚迪/亿纬锂能/隆基,覆盖电池/整车/光伏/风电产业链",
             "holdings":[("sz300750","宁德时代"),("sz002594","比亚迪"),("sz300014","亿纬锂能"),("sh601012","隆基绿能"),("sz002460","赣锋锂业")],
             "timing":"✅ 国内新能源汽车销量月同比>20%时\n✅ 锂价见底回升(碳酸锂>10万/吨)时\n❌ 欧盟反补贴调查+关税上涨时出口承压\n📅 Q1/Q3为新能源传统旺季前布局"},
            {"name":"芯片ETF","code":"159995","style":"半导体",
             "intro":"兆易/寒武纪/中微/北方华创,设计/制造/封测/设备全产业链",
             "holdings":[("sh603986","兆易创新"),("sh688256","寒武纪"),("sz002049","紫光国微"),("sh688012","中微公司"),("sz002371","北方华创")],
             "timing":"✅ WSTS半导体销售额同比转正+上行周期\n✅ 国产替代政策密集出台(大基金三期等)\n✅ AI算力需求爆发时连带芯片上涨\n❌ 美国对华半导体管制升级时短期暴跌"},
            {"name":"AI ETF","code":"515070","style":"人工智能",
             "intro":"科大讯飞/寒武纪/海天瑞声,覆盖大模型/算力/应用层",
             "holdings":[("sz002230","科大讯飞"),("sh688256","寒武纪"),("sh603728","海天瑞声"),("sz300418","昆仑万维"),("sz300454","深信服")],
             "timing":"✅ 大模型发布+应用落地(AI+医疗/教育/金融)催化时\n✅ 算力基础设施投资加码(东数西算)\n❌ 概念炒作过高(单月涨幅>30%)后获利回吐风险大"},
            {"name":"医药ETF","code":"512010","style":"创新药",
             "intro":"恒瑞/迈瑞/药明康德,创新药+医疗器械+医疗服务",
             "holdings":[("sh600276","恒瑞医药"),("sz300760","迈瑞医疗"),("sh603259","药明康德"),("sz002007","华兰生物"),("sz000538","云南白药")],
             "timing":"✅ 医保谈判利好(续约不降价/创新药单独通道)\n✅ 新药审批加速+FDA获批时\n❌ 集采扩面覆盖到创新药时回避"},
        ]
    },
    {
        "cat": "🔄 周期行业 (看供需)",
        "cat_desc": "强周期,跟随宏观经济/库存周期. 核心: 低买高卖,赚周期波动的钱. 关键指标: PPI/社融/库存天数",
        "funds": [
            {"name":"证券ETF","code":"512880","style":"券商",
             "intro":"中信/华泰/国泰君安,牛市风向标,两市成交额+政策直接影响",
             "holdings":[("sh600030","中信证券"),("sh601688","华泰证券"),("sh601211","国泰君安"),("sh600837","海通证券"),("sz300059","东方财富")],
             "timing":"✅ 两市成交额连续3日破万亿时\n✅ 监管出台利好(降印花税/两融扩容/IPO收紧)\n❌ 熊市缩量(日成交<4000亿)时回避\n📅 牛市第一波通常先动"},
            {"name":"有色金属ETF","code":"512400","style":"资源",
             "intro":"山东黄金/紫金矿业/中国铝业,黄金/铜/铝/锂,受益美元指数下行",
             "holdings":[("sh600547","山东黄金"),("sh601899","紫金矿业"),("sh600489","中金黄金"),("sz000878","云南铜业"),("sh601600","中国铝业")],
             "timing":"✅ 美元指数(DXY)跌破100+实际利率下行时黄金大涨\n✅ LME铜库存低位+供给扰动时\n❌ 美联储鹰派加息周期中黄金承压"},
            {"name":"煤炭ETF","code":"515220","style":"能源",
             "intro":"中国神华/陕西煤业/中煤能源,高股息+低估值+碳中和约束下供给刚性",
             "holdings":[("sh601088","中国神华"),("sh601225","陕西煤业"),("sh601898","中煤能源"),("sh600395","盘江股份"),("sz000983","西山煤电")],
             "timing":"✅ 冬季供暖需求旺季(11月~次年3月)\n✅ 长协价上调+现货价上涨时\n❌ 碳中和政策加码(供给侧改革)时短期利空但长期供给收缩利好"},
            {"name":"房地产ETF","code":"512200","style":"地产后周期",
             "intro":"万科/保利/海螺水泥,政策敏感度极高,看政治局会议定调",
             "holdings":[("sz000002","万科A"),("sh600048","保利发展"),("sh601155","新城控股"),("sh600585","海螺水泥"),("sz300737","科顺股份")],
             "timing":"✅ 政治局会议定调'支持合理住房需求'+限购限贷松绑\n✅ 30大中城市商品房成交面积环比转正时\n❌ 房企暴雷+信托违约潮中回避"},
            {"name":"军工ETF","code":"512660","style":"国防军工",
             "intro":"航发动力/中航沈飞/中国卫星,订单驱动+改革预期,十四五重点",
             "holdings":[("sh600893","航发动力"),("sh600760","中航沈飞"),("sh600118","中国卫星"),("sz000768","中航西飞"),("sh600372","中航机载")],
             "timing":"✅ 两会国防预算增速>7%时\n✅ 新型装备定型/阅兵/航展等事件催化\n❌ 和平预期升温+军费增速下滑时短期承压"},
        ]
    },
    {
        "cat": "💰 红利价值 (收息+打新)",
        "cat_desc": "高股息+低估值+稳定现金流. 适合稳健型/养老金/打新底仓. 核心策略: 股息率>5% + 盈利稳定",
        "funds": [
            {"name":"红利低波ETF","code":"512890","style":"红利",
             "intro":"银行+电信+公用事业,波动低股息高,长期复利利器",
             "holdings":[("sh601398","工商银行"),("sh601939","建设银行"),("sh600036","招商银行"),("sh601628","中国人寿"),("sh600941","中国移动")],
             "timing":"✅ 市场高估值(沪深300PE>14)时防御价值凸显\n✅ 利率下行周期中红利股相对收益率上升\n❌ 牛市狂热期红利跑输成长\n📅 适合作为打新底仓(门票股)"},
            {"name":"银行ETF","code":"512800","style":"金融",
             "intro":"四大行+股份制银行,股息率5%~7%,PB<0.5破净",
             "holdings":[("sh601398","工商银行"),("sh601939","建设银行"),("sh600036","招商银行"),("sh601288","农业银行"),("sh601328","交通银行")],
             "timing":"✅ 息差见底回升+不良率见顶时\n✅ 降准后银行负债成本下降\n❌ 地产风险传导+城投债风险时谨慎"},
            {"name":"电信ETF","code":"515880","style":"公用事业",
             "intro":"移动/联通/电信,高股息+AI算力需求新增长极",
             "holdings":[("sh600941","中国移动"),("sh601728","中国电信"),("sh600050","中国联通"),("sh600489","中金黄金"),("sh601857","中国石油")],
             "timing":"✅ 5G+AI算力基础设施投资加速时\n✅ 央企估值重塑政策(中特估)催化时\n❌ 通信资费下调压力时"},
        ]
    },
    {
        "cat": "🌟 行业主题 (事件驱动)",
        "cat_desc": "单一赛道集中持仓,高风险高收益. 核心: 踩对点,见好就收. 适合主动出击的投资者",
        "funds": [
            {"name":"招商中证白酒","code":"161725","style":"白酒",
             "intro":"茅台/五粮液/汾酒/泸州老窖,A股最核心的消费赛道,社交属性+定价权",
             "holdings":[("sh600519","贵州茅台"),("sz000858","五粮液"),("sh600809","山西汾酒"),("sz002304","洋河股份"),("sz000568","泸州老窖")],
             "timing":"✅ 春节/中秋旺季批价回升时\n✅ 白酒消费税利空出尽时\n❌ 年轻人喝白酒减少+老龄化长期利空\n📅 每年Q3(中秋)前布局,Q4兑现"},
            {"name":"游戏ETF","code":"159869","style":"传媒",
             "intro":"三七互娱/昆仑万维/科大讯飞,版号发放+AI赋能新逻辑",
             "holdings":[("sz002555","三七互娱"),("sz300418","昆仑万维"),("sz002230","科大讯飞"),("sz300454","深信服"),("sz002602","世纪华通")],
             "timing":"✅ 游戏版号月度发放正常化(每月≥80款)\n✅ AI+游戏落地(AI NPC/自动生成关卡)催化时\n❌ 未成年人防沉迷政策加码时"},
            {"name":"纳指ETF","code":"513100","style":"美股科技",
             "intro":"苹果/微软/英伟达/谷歌,全球最优质科技公司,英伟达占比超10%",
             "holdings":[("AAPL","苹果"),("MSFT","微软"),("NVDA","英伟达"),("TSLA","特斯拉"),("GOOG","谷歌")],
             "timing":"✅ 美联储降息周期开启时科技股弹性最大\n✅ AI产业周期(大模型+应用)持续时\n❌ 美元流动性收紧+美债收益率>5%时承压\n⚠️ T+0交易,可日内波段"},
            {"name":"恒生科技ETF","code":"513130","style":"中概",
             "intro":"腾讯/阿里/美团/京东,中国互联网核心资产,港股估值洼地",
             "holdings":[("9988","阿里巴巴"),("9618","京东"),("3690","美团"),("9999","网易"),("0700","腾讯控股")],
             "timing":"✅ 平台经济监管常态化+绿灯案例落地时\n✅ 港股通资金持续净流入时\n❌ 中美审计监管争端升级+美联储加息时\n⚠️ 港股流动性差,避免追涨杀跌"},
            {"name":"黄金ETF","code":"518880","style":"避险",
             "intro":"跟踪伦敦金现货价,避险+抗通胀+对冲美元信用风险",
             "holdings":[("sh600547","山东黄金"),("sh601899","紫金矿业"),("sh600489","中金黄金"),("sh601600","中国铝业"),("sh601857","中国石油")],
             "timing":"✅ 地缘冲突升级(战争/制裁)时\n✅ 美联储停止加息+市场开始预期降息\n✅ 央行增持黄金+全球去美元化加速\n❌ 风险偏好上升+美元指数走强时"},
        ]
    },
]

# ── 🤖 AI 择时判断引擎 ──

def _fetch_macro_data():
    """后台一次性拉所有宏观指标, 返回 dict"""
    import akshare as ak, numpy as np
    out = {}
    try:  # 沪深300 PE
        df = ak.stock_index_pe_lg(symbol="沪深300")
        out["hs300_pe"] = float(df["滚动市盈率"].iloc[-1])
    except Exception: out["hs300_pe"] = None
    try:  # 沪深300 近20日涨跌幅
        df = ak.stock_zh_index_daily(symbol="sh000300")
        last20 = df.tail(20)
        out["hs300_20d_pct"] = round((float(last20["close"].iloc[-1]) / float(last20["close"].iloc[0]) - 1) * 100, 2)
    except Exception: out["hs300_20d_pct"] = None
    try:  # 沪深300 近60日涨跌幅
        df = ak.stock_zh_index_daily(symbol="sh000300")
        last60 = df.tail(60)
        out["hs300_60d_pct"] = round((float(last60["close"].iloc[-1]) / float(last60["close"].iloc[0]) - 1) * 100, 2)
    except Exception: out["hs300_60d_pct"] = None
    try:  # PMI 制造业最新
        df = ak.macro_china_pmi()
        out["pmi"] = float(df["制造业-指数"].iloc[0])
        out["pmi_non_mfg"] = float(df["非制造业-指数"].iloc[0])
        out["pmi_prev"] = float(df["制造业-指数"].iloc[1])
    except Exception: out["pmi"] = None
    try:  # PPI 当月同比增长
        df = ak.macro_china_ppi()
        out["ppi"] = float(df["当月同比增长"].iloc[0])
    except Exception: out["ppi"] = None
    try:  # CPI 当月同比增长
        df = ak.macro_china_cpi()
        out["cpi"] = float(df["当月同比增长"].iloc[0])
    except Exception: out["cpi"] = None
    try:  # 10Y国债收益率 (最新一个交易日)
        df = ak.bond_china_yield(start_date="20261001", end_date="20991231")
        out["bond10y"] = float(df["10年"].iloc[0])
    except Exception: out["bond10y"] = None
    try:  # DXY 美元指数
        df = ak.index_us_stock_sina(symbol=".DXY")
        out["dxy"] = float(df["close"].iloc[-1])
    except Exception: out["dxy"] = None
    try:  # 两市成交额 + 涨停数
        df = ak.stock_market_activity_legu()
        for _, r in df.iterrows():
            if r["item"] == "真实涨停": out["limit_up"] = int(float(r["value"]))
            if r["item"] == "上涨": out["up_count"] = int(float(r["value"]))
            if r["item"] == "下跌": out["down_count"] = int(float(r["value"]))
        out["total_turnover_yi"] = None  # legu 接口没成交额
    except Exception: out["limit_up"] = None
    return out


def _assess_timing(macro, fund_style, fund_name=""):
    """单个基金择时判断
    返回 {"score": 0-100, "bull": [...], "bear": [...], "summary": str, "signals": [...]}"""
    if not macro or macro.get("hs300_pe") is None:
        return {"score": None, "bull": [], "bear": [], "summary": "⚠️ 宏观数据拉取失败, 请检查网络后点 🔄更新择时", "signals": []}

    bull, bear, signals = [], [], []

    def _check(condition_bull, label_bull, detail, bull_list, bear_list, score_dir):
        """统一检查 + 追加结果"""
        if score_dir > 0 and condition_bull:
            bull_list.append(f"✅ {label_bull} ({detail})")
            return 1
        elif score_dir < 0 and not condition_bull:
            bear_list.append(f"❌ 非 {label_bull} ({detail})")
            return -1
        elif score_dir < 0 and condition_bull:
            bull_list.append(f"⚠️ 虽然 {label_bull}, 但对{fund_name or '该风格'}偏空 ({detail})")
            return 0
        else:
            bear_list.append(f"❌ 未达 {label_bull} ({detail})")
            return 0

    hs300_pe = macro.get("hs300_pe") or 0
    hs300_20d = macro.get("hs300_20d_pct") or 0
    hs300_60d = macro.get("hs300_60d_pct") or 0
    pmi = macro.get("pmi")
    pmi_prev = macro.get("pmi_prev")
    ppi = macro.get("ppi")
    cpi = macro.get("cpi")
    bond10y = macro.get("bond10y")
    dxy = macro.get("dxy")
    limit_up = macro.get("limit_up")

    score = 50  # 中性

    # ── 全局条件 ──
    # 沪深300 PE 估值
    if hs300_pe and hs300_pe < 12:
        bull.append(f"✅ 沪深300 PE {hs300_pe:.1f} 低估区 (<12), 安全垫厚")
        score += 8
    elif hs300_pe and hs300_pe > 15:
        bear.append(f"❌ 沪深300 PE {hs300_pe:.1f} 偏高 (>15), 估值有压力")
        score -= 6
    else:
        bull.append(f"🟡 沪深300 PE {hs300_pe:.1f} 中性 (12~15)")

    # 20日涨跌
    if hs300_20d and hs300_20d < -5:
        bull.append(f"✅ 沪深300 20日跌 {hs300_20d:.1f}%, 可能超跌反弹")
        score += 5
    elif hs300_20d and hs300_20d > 8:
        bear.append(f"❌ 沪深300 20日涨 {hs300_20d:.1f}%, 短期过热")
        score -= 4

    # PMI
    if pmi is not None:
        if pmi > 50.5:
            bull.append(f"✅ 制造业PMI {pmi:.1f} 荣枯线以上, 经济扩张")
            score += 6
        elif pmi < 49.5:
            bear.append(f"❌ 制造业PMI {pmi:.1f} 荣枯线以下, 经济收缩")
            score -= 5
        else:
            bull.append(f"🟡 制造业PMI {pmi:.1f} 临界区 (49.5~50.5)")
        if pmi_prev and pmi > pmi_prev:
            bull.append(f"✅ PMI 环比回升 (上月 {pmi_prev:.1f} → 本月 {pmi:.1f})")
            score += 3

    # ── 风格特定条件 ──
    style = fund_style

    # Beta宽基 / 宽基大盘 / 宽基小盘 / 中盘成长 / 小盘弹性 / 科技成长 / 硬科技
    if "宽基" in style or style in ("中盘成长", "小盘弹性", "科技成长", "硬科技"):
        if ppi is not None and ppi > 0:
            bull.append(f"✅ PPI {ppi:.1f}% 转正, 工业利润改善 (利好周期+宽基)")
            score += 4
        elif ppi is not None and ppi < -1:
            bear.append(f"❌ PPI {ppi:.1f}% 通缩区, 工业利润承压")
            score -= 3
        # 利率对成长的影响
        if bond10y is not None and bond10y < 2.0:
            bull.append(f"✅ 10Y国债 {bond10y:.2f}% 低位, 成长股估值压力小")
            score += 5

    # 成长 / 新能源 / 半导体 / AI / 创新药 / 科技成长 / 硬科技
    if style in ("新能源", "半导体", "人工智能", "创新药", "科技成长", "硬科技", "高弹性") or "成长" in style or style in ("消费成长", "成长精选", "成长+红利"):
        if bond10y is not None and bond10y < 2.0:
            bull.append(f"✅ 利率低位 ({bond10y:.2f}%), 成长股贴现率低, 估值有支撑")
            score += 5
        if dxy is not None and dxy < 105:
            bull.append(f"✅ DXY {dxy:.1f} 偏弱, 外资流入A股成长板块")
            score += 4
        # 超跌反弹
        if hs300_20d and hs300_20d < -8:
            bull.append(f"✅ 指数超跌 {hs300_20d:.1f}%, 成长弹性大, 反弹空间足")
            score += 4

    # 周期行业 / 券商 / 资源 / 能源 / 地产后周期 / 国防军工
    if style in ("券商", "资源", "能源", "地产后周期", "国防军工") or "周期" in style:
        if ppi is not None and ppi > 0.5:
            bull.append(f"✅ PPI {ppi:.1f}% 上行, 周期品提价, 企业盈利改善")
            score += 7
        elif ppi is not None and ppi < -1.5:
            bear.append(f"❌ PPI {ppi:.1f}% 深度通缩, 周期股业绩承压")
            score -= 6
        # 券商看市场情绪
        if limit_up is not None and limit_up >= 50:
            bull.append(f"✅ 涨停 {limit_up} 只, 情绪偏热, 券商受益")
            score += 3

    # 红利 / 金融 / 公用事业
    if style in ("红利", "金融", "公用事业") or "红利" in style:
        if bond10y is not None and bond10y < 2.0:
            bull.append(f"✅ 10Y国债 {bond10y:.2f}% 低位, 红利股相对收益率上升")
            score += 6
        if hs300_pe and hs300_pe < 12:
            bull.append(f"✅ 大盘低估区 (PE {hs300_pe:.1f}), 红利价值凸显")
            score += 3

    # 白酒 / 消费白马 / 消费成长
    if style in ("白酒", "消费白马", "消费成长"):
        if pmi is not None and pmi > 50:
            bull.append(f"✅ PMI {pmi:.1f}>50, 消费景气, 白酒可选消费预期改善")
            score += 4
        if cpi is not None and 1 < cpi < 3:
            bull.append(f"✅ CPI {cpi:.1f}% 温和通胀, 白酒具备定价权")
            score += 3
        if hs300_pe and hs300_pe < 12:
            bull.append(f"✅ 大盘低估时消费龙头性价比高")
            score += 2

    # 美股科技 / 中概
    if style in ("美股科技", "中概"):
        if dxy is not None and dxy < 105:
            bull.append(f"✅ DXY {dxy:.1f}<105, 美元弱利好美股/港股")
            score += 6
        if bond10y is not None and bond10y < 2.5:
            bull.append(f"✅ 10Y美债收益率低位 (对应中国国债 {bond10y:.2f}%), 科技估值支撑")
            score += 4

    # 避险 (黄金)
    if style == "避险":
        if dxy is not None and dxy < 102:
            bull.append(f"✅ DXY {dxy:.1f}<102 弱美元周期, 黄金看涨")
            score += 7
        if bond10y is not None and bond10y < 2.0:
            bull.append(f"✅ 实际利率 = 名义 - 通胀预期, 当前 {bond10y:.2f}% 低位, 黄金机会")
            score += 5

    # 均衡类 / 宽基大盘
    if "均衡" in style or style == "宽基大盘":
        if hs300_pe and hs300_pe < 13 and (pmi or 50) >= 49.5:
            bull.append(f"✅ 估值合理 + 经济平稳, 均衡型基金适合当前环境")
            score += 4

    # 综合打分
    score = max(0, min(100, score))
    if score >= 70:
        verdict = "🟢 当下时机较佳, 可考虑加仓"
    elif score >= 55:
        verdict = "🟡 条件中性偏多, 持有为主, 不急追"
    elif score >= 45:
        verdict = "⚪ 条件中性, 方向不明朗"
    elif score >= 30:
        verdict = "🟠 条件中性偏空, 谨慎操作"
    else:
        verdict = "🔴 当下条件不利, 观望或减仓"

    # 格式化 summary
    macro_summary_parts = []
    if hs300_pe is not None: macro_summary_parts.append(f"沪深300PE={hs300_pe:.1f}")
    if hs300_20d is not None: macro_summary_parts.append(f"20日={hs300_20d:.1f}%")
    if pmi is not None: macro_summary_parts.append(f"PMI={pmi:.1f}")
    if ppi is not None: macro_summary_parts.append(f"PPI={ppi:.1f}%")
    if bond10y is not None: macro_summary_parts.append(f"10Y债={bond10y:.2f}%")
    if dxy is not None: macro_summary_parts.append(f"DXY={dxy:.1f}")
    macro_line = " | ".join(macro_summary_parts)

    summary = f"{verdict}\n📊 当日宏观: {macro_line}"

    return {
        "score": score,
        "bull": bull[:6],
        "bear": bear[:4],
        "summary": summary,
    }


# 板块归类 (和邮票格子保持一致)
_BLOCK_GROUPS = {
    "银行":   ["sh601398","sh601939","sh601288","sh601988","sh600036","sh601166","sz002142","sh600016","sh601328"],
    "券商":   ["sh600030","sh601211","sh601788","sh600837","sh601688","sz000776","sh600109","sz300059","sh600018"],
    "保险":   ["sh601318","sh601628","sh601601","sh601336"],
    "白酒":   ["sh600519","sz000858","sh600809","sz000568","sh603369","sz000596","sz002304","sh603589"],
    "半导体": ["sh603986","sh688256","sh688981","sz002049","sz300223","sh603501","sh600584","sz300782","sh688012","sh688008","sz002371","sz002185","sz002456","sh603160","sz300661"],
    "AI":     ["sz002230","sz300496","sh600588","sz002415","sh603019","sz300033","sz300364","sh600406"],
    "CPO":    ["sz002281","sh600487","sz002222","sh601869","sh603502","sz300394","sz300502","sz002268"],
    "新能源": ["sz300750","sz3002594","sz300014","sh601012","sz002460","sh600438","sz300274","sz300763","sz002580"],
    "光伏":   ["sh601012","sz300118","sh600438","sz300274","sh688599"],
    "军工":   ["sh600893","sh600760","sh600118","sz002414","sz000768","sh601698","sz300034","sh600150","sh600372"],
    "机器人": ["sz300024","sz300274","sz300607","sh600021","sz300124","sz002527"],
    "煤炭能源":["sh601225","sh601088","sh60188","sh601015","sh600395","sh601985","sz000933","sh600508","sh600985"],
    "医药医疗":["sh600276","sz000538","sz002422","sh600196","sz002007","sh600535","sz300015","sz300003","sh603259","sz002594","sh600085","sz002821","sz000423","sh600518"],
    "黄金有色":["sh600547","sh600489","sh601899","sz002155","sh600362","sh601600","sz000878","sh600111"],
    "地产建材":["sh600048","sh600340","sz001979","sh600585","sh601155","sz000002","sh600031","sh601668","sz300737"],
    "消费家电":["sh600690","sz000651","sh600887","sz002475","sh601888","sz300999","sh603288","sh600872","sz000568","sz000333"],
    "石油石化":["sh600028","sh601857","sh600019","sh600583","sh600688","sz000554"],
    "中概互联":["sh600519","sz002594","sz300750","sh601888","sh600036"],
    "其他":   [],
}

# 名字→板块 (兜底)
_NAME_TO_BLOCK = [
    ("银行","银行"),("招行","银行"),("工行","银行"),("建行","银行"),("中行","银行"),("交行","银行"),("农行","银行"),("浦发","银行"),("民生","银行"),("平安银","银行"),
    ("证券","券商"),("中信证","券商"),("华泰","券商"),("海通","券商"),("国泰君","券商"),("招商证","券商"),("东方财","券商"),("东财","券商"),
    ("保险","保险"),("平安","保险"),("人寿","保险"),("太保","保险"),
    ("茅台","白酒"),("白酒","白酒"),("五粮液","白酒"),("老窖","白酒"),("汾酒","白酒"),("洋河","白酒"),("古井","白酒"),("今世缘","白酒"),("牛栏山","白酒"),
    ("中芯","半导体"),("半导体","半导体"),("芯片","半导体"),("韦尔","半导体"),("紫光","半导体"),("长电","半导体"),("通富","半导体"),("士兰","半导体"),("中微","半导体"),("华虹","半导体"),("安集","半导体"),("北华创","半导体"),
    ("寒武","AI"),("科大讯","AI"),("汉王","AI"),("拓尔","AI"),("讯飞","AI"),("算力","AI"),("昆仑","AI"),("智谱","AI"),("海光","AI"),("浪潮","AI"),
    ("光模块","CPO"),("CPO","CPO"),("光迅","CPO"),("中际旭","CPO"),("新易盛","CPO"),("天孚","CPO"),("华工","CPO"),("亨通","CPO"),
    ("电池","新能源"),("锂电","新能源"),("宁德","新能源"),("比亚迪","新能源"),("亿纬","新能源"),("欣旺达","新能源"),("赣锋","新能源"),("天齐","新能源"),("华友","新能源"),("洛阳钼","新能源"),
    ("光伏","光伏"),("隆基","光伏"),("通威","光伏"),("阳光电源","光伏"),("硅片","光伏"),("晶澳","光伏"),("天合","光伏"),
    ("军工","军工"),("航发","军工"),("国防","军工"),("中航","军工"),("航天","军工"),("无人机","军工"),("中直","军工"),("振华","军工"),("中航西飞","军工"),("航发动力","军工"),("航发控制","军工"),
    ("机器人","机器人"),("人形","机器人"),("汇川","机器人"),("埃斯顿","机器人"),("绿的","机器人"),
    ("煤炭","煤炭能源"),("煤业","煤炭能源"),("能源","煤炭能源"),("神华","煤炭能源"),("中煤","煤炭能源"),("平煤","煤炭能源"),("陕煤","煤炭能源"),
    ("医药","医药医疗"),("医疗","医药医疗"),("药明","医药医疗"),("恒瑞","医药医疗"),("迈瑞","医药医疗"),("智飞","医药医疗"),("复星","医药医疗"),("云南白","医药医疗"),("片仔","医药医疗"),("东阿","医药医疗"),("爱尔","医药医疗"),("乐普","医药医疗"),
    ("黄金","黄金有色"),("金业","黄金有色"),("有色","黄金有色"),("紫金","黄金有色"),("中金黄","黄金有色"),("山金","黄金有色"),("铜","黄金有色"),("洛阳钼","黄金有色"),
    ("地产","地产建材"),("建材","地产建材"),("万科","地产建材"),("保利","地产建材"),("海螺","地产建材"),("三一是","地产建材"),("三一","地产建材"),("中建","地产建材"),
    ("家电","消费家电"),("美的","消费家电"),("格力","消费家电"),("海尔","消费家电"),("伊利","消费家电"),("金龙鱼","消费家电"),("中免","消费家电"),("海天","消费家电"),("农夫山","消费家电"),
    ("石化","石油石化"),("石油","石油石化"),("中海油","石油石化"),("中国石","石油石化"),("中石化","石油石化"),
]

def _match_block(name, code):
    code6 = code if isinstance(code, str) else str(code)
    # 去掉 sh/sz/bj 前缀
    if code6.startswith(("sh","sz","bj","SH","SZ","BJ")):
        code6 = code6[2:]
    code6 = code6.zfill(6)
    for blk, codes in _BLOCK_GROUPS.items():
        if code6 in codes:
            return blk
    for kw, blk in sorted(_NAME_TO_BLOCK, key=lambda x: -len(x[0])):
        if kw in name:
            return blk
    return "其他"


def _lookup_sina(name, code6):
    """尝试拿到 sina_code (sh/sz/bj + 6位代码)"""
    if code6 and isinstance(code6, str) and code6.startswith(("sh","sz","bj","SH","SZ","BJ")):
        return code6.lower(), name
    if code6:
        c = str(code6).zfill(6)
        if c.startswith("6"): return "sh" + c, name
        if c.startswith(("0","3")): return "sz" + c, name
        if c.startswith(("4","8")): return "bj" + c, name
    return None, None


def _open_kline(parent, sina_code, name):
    """双击股票 → 日K线弹窗 (复用 high_low_swing 里的秒开)"""
    try:
        from ui.high_low_swing import _quick_open_daily_kline
        _quick_open_daily_kline(parent, sina_code, name)
    except Exception as e:
        print(f"[基金持仓] 打开K线失败: {e}", flush=True)


def build_fund_holdings_tab(parent, root=None):
    """🎯 构建基金持仓 Tab"""
    from collections import defaultdict
    import webbrowser

    # ── 字体大小 (A-/A+ 按钮调节) ──
    _FUND_FONT_SIZE = [10]  # 用列表让闭包能修改
    def _fs(delta=0):
        _FUND_FONT_SIZE[0] = max(8, min(18, _FUND_FONT_SIZE[0] + delta))
        return _FUND_FONT_SIZE[0]
    def _font(bold=False):
        return ("", _FUND_FONT_SIZE[0], "bold" if bold else "normal")

    def _open_fund_web(code):
        """双击基金名 → 天天基金对应页面"""
        try:
            url = f"https://fund.eastmoney.com/{code}.html"
            webbrowser.open(url, new=2)
            print(f"[基金持仓] 打开基金网页 {url}", flush=True)
        except Exception as e:
            print(f"[基金持仓] 打开网页失败: {e}", flush=True)

    if root is None:
        root = parent.winfo_toplevel()

    # ── 顶栏 ──
    top = ttk.Frame(parent); top.pack(fill=tk.X, padx=6, pady=(6, 2))
    tk.Label(top, text="🏦 基金持仓追踪", bg=_BG_PANEL, fg=_FG_GOLD,
             font=("", 12, "bold")).pack(side=tk.LEFT)
    status = tk.Label(top, text="⏳ 加载中...", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9))
    status.pack(side=tk.RIGHT, padx=6)
    btn_refresh = ttk.Button(top, text="🔄 刷新", width=10,
                              command=lambda: _load_data(force=True))
    btn_refresh.pack(side=tk.RIGHT)
    # 字体调节
    tk.Label(top, text=" 字体:", bg=_BG_PANEL, fg=_FG_DIM, font=("", 9)).pack(side=tk.RIGHT)
    def _do_font_plus():
        _fs(1); _rerender_all()
    def _do_font_minus():
        _fs(-1); _rerender_all()
    ttk.Button(top, text="A+", width=3, command=_do_font_plus).pack(side=tk.RIGHT, padx=(2,1))
    ttk.Button(top, text="A-", width=3, command=_do_font_minus).pack(side=tk.RIGHT)
    # 择时更新按钮
    btn_timing = ttk.Button(top, text="🤖 🔄更新择时", width=14,
                            command=lambda: _load_timing(force=True))
    btn_timing.pack(side=tk.RIGHT, padx=(6, 0))

    # Notebook 分成两部分
    nb = ttk.Notebook(parent)
    nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    # ── Tab1: 基金卡片 ──
    card_frame = ttk.Frame(nb); nb.add(card_frame, text="🏦 基金持仓卡片")
    # 可滚动
    card_canvas = tk.Canvas(card_frame, bg=_BG_DEEP, highlightthickness=0)
    card_vsb = ttk.Scrollbar(card_frame, orient="vertical", command=card_canvas.yview)
    card_inner = ttk.Frame(card_canvas, style="Dark.TFrame")
    card_canvas.configure(yscrollcommand=card_vsb.set)
    card_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    card_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    card_canvas.create_window((0, 0), window=card_inner, anchor="nw")
    card_inner.bind("<Configure>", lambda e: card_canvas.configure(scrollregion=card_canvas.bbox("all")))
    card_canvas.bind_all("<MouseWheel>", lambda e: card_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ── Tab2: 板块聚合 ──
    agg_frame = ttk.Frame(nb); nb.add(agg_frame, text="📊 板块聚合 Top100")
    agg_canvas = tk.Canvas(agg_frame, bg=_BG_DEEP, highlightthickness=0)
    agg_vsb = ttk.Scrollbar(agg_frame, orient="vertical", command=agg_canvas.yview)
    agg_inner = ttk.Frame(agg_canvas, style="Dark.TFrame")
    agg_canvas.configure(yscrollcommand=agg_vsb.set)
    agg_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    agg_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    agg_canvas.create_window((0, 0), window=agg_inner, anchor="nw")
    agg_inner.bind("<Configure>", lambda e: agg_canvas.configure(scrollregion=agg_canvas.bbox("all")))

    # ── Tab3: 基金指南 (风格分类 + 介绍 + 择时) ──
    guide_frame = ttk.Frame(nb); nb.add(guide_frame, text="📚 基金指南 (Beta/Alpha/成长/周期)")
    guide_canvas = tk.Canvas(guide_frame, bg=_BG_DEEP, highlightthickness=0)
    guide_vsb = ttk.Scrollbar(guide_frame, orient="vertical", command=guide_canvas.yview)
    guide_inner = ttk.Frame(guide_canvas, style="Dark.TFrame")
    guide_canvas.configure(yscrollcommand=guide_vsb.set)
    guide_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    guide_vsb.pack(side=tk.RIGHT, fill=tk.Y)
    guide_canvas.create_window((0, 0), window=guide_inner, anchor="nw")
    guide_inner.bind("<Configure>", lambda e: guide_canvas.configure(scrollregion=guide_canvas.bbox("all")))

    # ── 🤖 择时缓存 ──
    _fund_timing_cache = {}  # {fund_code: {"score":, "bull":, "bear":, "summary":}}
    _fund_timing_running = False
    import threading as _th2, json as _json2, os as _os2
    from datetime import datetime as _dt2
    _TODAY = _dt2.now().strftime("%Y%m%d")
    _timing_cache_path = _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)),
                                          "..", "..", "data", f"fund_timing_cache_{_TODAY}.json")
    _timing_cache_path = _os2.path.normpath(_timing_cache_path)

    def _load_timing(force=False):
        """加载/重算所有基金的择时判断"""
        nonlocal _fund_timing_cache, _fund_timing_running
        if _fund_timing_running: return
        _fund_timing_running = True

        # 1) 读缓存 (非 force) — 但缓存必须是成功的 (score 非全 None)
        if not force and _os2.path.exists(_timing_cache_path):
            try:
                with open(_timing_cache_path, "r", encoding="utf-8") as f:
                    _cached = _json2.load(f)
                # 检查是不是成功缓存 (至少一只 score 不是 None)
                _any_ok = any(v.get("score") is not None for v in _cached.values())
                if _any_ok:
                    _fund_timing_cache = _cached
                    print(f"[基金择时] 读成功缓存 OK ({len(_fund_timing_cache)} 只基金)", flush=True)
                    _fund_timing_running = False
                    _render_timing_boxes()
                    return
                else:
                    print("[基金择时] 缓存是失败的, 忽略, 重算", flush=True)
            except Exception as e:
                print(f"[基金择时] 缓存读取失败: {e}", flush=True)

        # 2) 后台线程联网计算
        status.configure(text="🤖 择时计算中... (拉宏观数据)", foreground=_FG_GOLD)
        print("[基金择时] 开始拉宏观数据...", flush=True)

        def _bg():
            nonlocal _fund_timing_cache
            try:
                macro = _fetch_macro_data()
                print(f"[基金择时] 宏观数据拉完: {list(macro.keys())}", flush=True)
                results = {}
                for cat in _FUND_GUIDE:
                    for f in cat["funds"]:
                        key = f"{f['code']}|{f['name']}"
                        results[key] = _assess_timing(macro, f["style"], f["name"])
                _fund_timing_cache = results
                # 写缓存
                try:
                    _os2.makedirs(_os2.path.dirname(_timing_cache_path), exist_ok=True)
                    with open(_timing_cache_path, "w", encoding="utf-8") as f:
                        _json2.dump(results, f, ensure_ascii=False, indent=2)
                    print(f"[基金择时] 缓存写入 OK ({len(results)} 只)", flush=True)
                except Exception as e:
                    print(f"[基金择时] 缓存写入失败: {e}", flush=True)
                root.after(0, _render_timing_boxes)
            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"[基金择时] 计算失败: {e}", flush=True)
                root.after(0, lambda: status.configure(text=f"❌ 择时计算失败: {e}", foreground="#EF5350"))
            finally:
                _fund_timing_running = False

        threading.Thread(target=_bg, daemon=True).start()

    def _render_timing_boxes():
        """把 _fund_timing_cache 数据渲染到所有卡片底部 (重绘整个 Tab3)"""
        # 重新渲染 Tab3 (guide) — 因为 _render_guide 已经会自动读 _fund_timing_cache
        _render_guide()
        # 也更新状态
        if _fund_timing_cache:
            status.configure(text=f"🤖 择时 OK ({len(_fund_timing_cache)} 只)", foreground=_FG_GREEN)
        else:
            status.configure(text="🤖 择时无数据", foreground=_FG_DIM)

    # ── Tab3 需要先用, 提前定义 ──
    def _on_stock_click(e, sina, name):
        print(f"[基金持仓] 点击股票 sina={sina} name={name}", flush=True)
        if sina:
            _open_kline(root, sina, name)
        else:
            print(f"[基金持仓] sina 为空, 无法打开K线 name={name}", flush=True)

    def _render_guide():
        for w in guide_inner.winfo_children():
            w.destroy()
        for cat in _FUND_GUIDE:
            cat_hd = tk.Frame(guide_inner, bg=_BG_PANEL)
            cat_hd.pack(fill=tk.X, padx=8, pady=(14, 4))
            tk.Label(cat_hd, text=cat["cat"], bg=_BG_PANEL, fg=_FG_GOLD,
                     font=_font(bold=True)).pack(side=tk.LEFT, padx=10, pady=6)
            tk.Label(cat_hd, text=cat["cat_desc"], bg=_BG_PANEL, fg=_FG_DIM,
                     font=_font(), wraplength=800, justify=tk.LEFT).pack(side=tk.LEFT, padx=10)

            fund_row = tk.Frame(guide_inner, bg=_BG_DEEP)
            fund_row.pack(fill=tk.X, padx=8, pady=(0, 6))

            for fi, f in enumerate(cat["funds"]):
                card = tk.Frame(fund_row, bg=_BG_CARD,
                                highlightbackground=_FG_BLUE, highlightthickness=1)
                card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

                fund_code = f["code"]
                fund_sina, _ = _lookup_sina(f["name"], fund_code)
                if not fund_sina and fund_code and fund_code.isdigit() and len(fund_code) == 6:
                    if fund_code.startswith("6") or fund_code.startswith(("50","51","52","53","54","55","56","57","58","59")): fund_sina = "sh" + fund_code
                    elif fund_code.startswith(("4","8")): fund_sina = "bj" + fund_code
                    else: fund_sina = "sz" + fund_code
                hdr = tk.Frame(card, bg=_BG_CARD); hdr.pack(fill=tk.X, padx=6, pady=(6, 2))
                _gf = tk.Label(hdr, text=f"🎯 {f['name']}", bg=_BG_CARD, fg=_FG_GOLD,
                         font=_font(bold=True), cursor="hand2")
                _gf.pack(side=tk.LEFT)
                _gc = tk.Label(hdr, text=f"({fund_code})", bg=_BG_CARD, fg=_FG_DIM,
                         font=_font(), cursor="hand2")
                _gc.pack(side=tk.LEFT, padx=3)
                tk.Label(hdr, text=f"#{f['style']}", bg=_BG_CARD, fg=_FG_CYAN,
                         font=_font()).pack(side=tk.RIGHT)
                # 单击 → 日K / 双击 → 天天基金
                _p2 = [None]
                def _gclick(_s=fund_sina, _n=f["name"]):
                    if _p2[0] is not None:
                        try: root.after_cancel(_p2[0])
                        except: pass
                    _p2[0] = root.after(250, lambda: _open_kline(root, _s, _n) if _s else _open_fund_web(fund_code))
                def _gdbl(_c=fund_code):
                    if _p2[0] is not None:
                        try: root.after_cancel(_p2[0])
                        except: pass
                    _open_fund_web(_c)
                for w in [_gf, _gc, hdr]:
                    w.bind("<Button-1>", lambda e: _gclick())
                    w.bind("<Double-Button-1>", lambda e: _gdbl())

                tk.Frame(card, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=2)

                tk.Label(card, text=f["intro"], bg=_BG_CARD, fg=_FG_TEXT,
                         font=_font(), wraplength=280, justify=tk.LEFT).pack(
                    anchor="w", padx=8, pady=(2, 4))

                tk.Label(card, text="📦 Top5 持仓 (双击弹日K):", bg=_BG_CARD,
                         fg=_FG_BLUE, font=_font(bold=True)).pack(anchor="w", padx=8, pady=(2,0))

                for hi, (code6, nm) in enumerate(f["holdings"]):
                    sina, _ = _lookup_sina(nm, code6)
                    row_bg = "#2A2A3A" if hi % 2 == 0 else _BG_CARD
                    hrow = tk.Frame(card, bg=row_bg, cursor="hand2")
                    hrow.pack(fill=tk.X, padx=4, pady=1)
                    def _mk(_s=sina, _n=nm):
                        return lambda e: _on_stock_click(e, _s, _n)
                    _h = _mk()
                    hrow.bind("<ButtonRelease-1>", _h); hrow.bind("<Double-Button-1>", _h)
                    _n_lbl = tk.Label(hrow, text=f"  {hi+1}. {nm}", bg=row_bg, fg=_FG_TEXT,
                                      font=_font())
                    _n_lbl.pack(side=tk.LEFT, padx=4, pady=2)
                    _n_lbl.bind("<ButtonRelease-1>", _h); _n_lbl.bind("<Double-Button-1>", _h)
                    _c_lbl = tk.Label(hrow, text=f"({code6})", bg=row_bg, fg=_FG_DIM,
                                      font=_font())
                    _c_lbl.pack(side=tk.RIGHT, padx=4)
                    _c_lbl.bind("<ButtonRelease-1>", _h); _c_lbl.bind("<Double-Button-1>", _h)

                tk.Label(card, text="💡 择时笔记:", bg=_BG_CARD, fg=_FG_GREEN,
                         font=_font(bold=True)).pack(anchor="w", padx=8, pady=(6, 0))
                tk.Label(card, text=f["timing"], bg=_BG_CARD, fg=_FG_DIM,
                         font=_font(), wraplength=280, justify=tk.LEFT).pack(
                    anchor="w", padx=8, pady=(0, 4))

                # 🤖 AI 择时判断
                _tkey = f"{f['code']}|{f['name']}"
                _timing = _fund_timing_cache.get(_tkey)
                if _timing:
                    _score = _timing.get("score")
                    _score_str = f"{_score}/100" if _score is not None else "N/A"
                    if _score is not None:
                        if _score >= 70: _score_color = "#66BB6A"
                        elif _score >= 55: _score_color = "#FFD54F"
                        elif _score >= 45: _score_color = "#AAAAAA"
                        elif _score >= 30: _score_color = "#FF8A65"
                        else: _score_color = "#EF5350"
                    else:
                        _score_color = _FG_DIM
                    _ai = tk.Frame(card, bg="#1A2525", highlightbackground=_FG_BLUE, highlightthickness=1)
                    _ai.pack(fill=tk.X, padx=4, pady=(2, 6))
                    _score_row = tk.Frame(_ai, bg="#1A2525")
                    _score_row.pack(fill=tk.X, padx=6, pady=(4, 0))
                    tk.Label(_score_row, text="🤖 AI 择时", bg="#1A2525", fg=_FG_BLUE,
                             font=_font(bold=True)).pack(side=tk.LEFT)
                    tk.Label(_score_row, text=_score_str, bg="#1A2525", fg=_score_color,
                             font=_font(bold=True)).pack(side=tk.RIGHT)
                    # summary
                    _summary = _timing.get("summary", "")
                    if _summary:
                        tk.Label(_ai, text=_summary, bg="#1A2525", fg=_FG_TEXT,
                                 font=_font(), wraplength=280, justify=tk.LEFT).pack(
                            anchor="w", padx=6, pady=(2, 2))
                    # 符合 / 不符合
                    _lines = []
                    for _b in _timing.get("bull", [])[:3]:
                        _lines.append(_b)
                    for _b in _timing.get("bear", [])[:2]:
                        _lines.append(_b)
                    if _lines:
                        tk.Label(_ai, text="\n".join(_lines), bg="#1A2525", fg=_FG_DIM,
                                 font=_font(), wraplength=280, justify=tk.LEFT).pack(
                            anchor="w", padx=6, pady=(0, 6))
                else:
                    tk.Label(card, text="🤖 AI 择时: 加载中... (顶栏点🤖🔄更新择时)",
                             bg=_BG_CARD, fg=_FG_DIM, font=_font(),
                             wraplength=280, justify=tk.LEFT).pack(
                        anchor="w", padx=8, pady=(2, 6))

    # Dark theme for Frame
    try:
        style = ttk.Style()
        style.configure("Dark.TFrame", background=_BG_DEEP)
    except Exception:
        pass

    # ── 缓存 ──
    _today = datetime.now().strftime("%Y%m%d")
    _cache_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "data", f"fund_holdings_cache_{_today}.json"
    )
    _cache_path = os.path.normpath(_cache_path)

    # 全局数据 (后台线程写入, 主线程渲染)
    _data = {"funds": [], "agg": []}
    _running = False

    def _load_data(force=False):
        """联网抓取 or 读缓存"""
        nonlocal _running
        if _running:
            return

        # 1) 尝试读缓存
        if not force and os.path.exists(_cache_path):
            try:
                with open(_cache_path, "r", encoding="utf-8") as f:
                    _cached = json.load(f)
                if isinstance(_cached, dict) and "funds" in _cached:
                    _data["funds"] = _cached["funds"]
                    _data["agg"] = _cached.get("agg", [])
                    _render_all()
                    status.configure(text=f"📂 读缓存 {len(_data['funds'])} 只基金 ({_today})", foreground=_FG_GREEN)
                    print(f"[基金持仓] 读缓存 OK ({len(_data['funds'])} 只)", flush=True)
                    return
            except Exception as _ce:
                print(f"[基金持仓] 缓存读失败: {_ce}", flush=True)

        # 2) 后台线程联网
        _running = True
        status.configure(text="⏳ 拉取基金重仓股...", foreground="#FFA726")

        def _bg():
            try:
                import akshare as ak
                fund_rows = []  # [{code, name, industry, holdings: [{code, name, pct, market_cap}]}]
                # 先拿全部基金重仓 (按市值排行)
                # 季度选择: 当前季度
                q_year = datetime.now().year
                q_month = datetime.now().month
                if q_month <= 3: q_str = f"{q_year-1}4"
                elif q_month <= 6: q_str = f"{q_year}1"
                elif q_month <= 9: q_str = f"{q_year}2"
                else: q_str = f"{q_year}3"
                print(f"[基金持仓] 用季度: {q_str}", flush=True)

                # —— 全市场基金重仓 Top200 ——
                all_hold = []  # [{code6, name, total_pct, total_mv, fund_count}]
                try:
                    df = ak.fund_portfolio_hold_em(date=q_str)
                    print(f"[基金持仓] portfolio_hold_em: {len(df)} 行", flush=True)
                    # 聚合: 同一只股票被多少基金持有 + 占比合计
                    agg = defaultdict(lambda: {"name":"", "codes":set(), "total_pct":0.0, "total_mv":0.0, "fund_count":0})
                    for _, r in df.iterrows():
                        c6 = str(r.get("股票代码", ""))
                        nm = str(r.get("股票名称", ""))
                        try: pct = float(r.get("占净值比例", 0))
                        except: pct = 0
                        try: mv = float(r.get("持仓市值", 0))
                        except: mv = 0
                        if not c6: continue
                        c6 = c6.zfill(6)
                        entry = agg[c6]
                        entry["name"] = nm
                        entry["codes"].add(c6)
                        entry["total_pct"] += pct
                        entry["total_mv"] += mv
                        entry["fund_count"] += 1
                    all_hold = []
                    for c6, e in agg.items():
                        all_hold.append({
                            "code6": c6, "name": e["name"],
                            "total_pct": round(e["total_pct"], 2),
                            "total_mv": round(e["total_mv"], 2),
                            "fund_count": e["fund_count"],
                        })
                    # 按持仓市值排序, 取 Top150
                    all_hold.sort(key=lambda x: -x["total_mv"])
                    all_hold = all_hold[:150]
                except Exception as e1:
                    print(f"[基金持仓] portfolio_hold_em 失败: {e1}", flush=True)

                # —— 种子兜底 ——
                if not all_hold:
                    # 用种子数据模拟
                    _SEED_TOP = [
                        ("sh603986","兆易创新",2.8,100),("sh688256","寒武纪",2.5,90),
                        ("sz300750","宁德时代",3.2,150),("sz002594","比亚迪",3.0,140),
                        ("sh600519","贵州茅台",2.9,200),("sz000858","五粮液",2.5,80),
                        ("sz002230","科大讯飞",2.4,70),("sz002281","光迅科技",2.2,50),
                        ("sh600036","招商银行",2.8,120),("sh601318","中国平安",2.7,110),
                        ("sh601225","陕西煤业",2.3,60),("sh600276","恒瑞医药",2.6,90),
                        ("sh600030","中信证券",2.5,85),("sz300782","卓胜微",2.1,45),
                        ("sh688012","中微公司",2.3,55),("sz002415","海康威视",2.0,70),
                        ("sz002371","北方华创",2.2,65),("sh601012","隆基绿能",2.4,75),
                        ("sz300014","亿纬锂能",2.1,50),("sh600893","航发动力",2.0,45),
                    ]
                    for c6, nm, pct, mv in _SEED_TOP:
                        all_hold.append({"code6":c6,"name":nm,"total_pct":pct,"total_mv":mv,"fund_count":3})

                # —— 构造基金卡片数据 ——
                # 把 Top 股票分配给主流基金 (按行业)
                _industry_holdings = defaultdict(list)
                for s in all_hold:
                    blk = _match_block(s["name"], s["code6"])
                    _industry_holdings[blk].append(s)

                for fc, fname, kind, seed_holdings in _FUND_TOP_HOLDINGS:
                    # 每只基金用自带的代表持仓种子 (行业多样性有保证)
                    picks = []
                    for code6, nm in seed_holdings[:5]:
                        sina, _ = _lookup_sina(nm, code6)
                        # 尝试从 API 数据里找到真实占比 (找不到用种子默认)
                        _api_pct = 0.0
                        for _a in all_hold:
                            if _a["code6"] == code6 or _a["name"] == nm:
                                _api_pct = _a["total_pct"]; break
                        picks.append({
                            "code6": code6, "name": nm, "sina": sina,
                            "total_pct": _api_pct or 0.0,
                            "total_mv": 0, "fund_count": 0,
                        })
                    fund_rows.append({
                        "code": fc, "name": fname, "industry": kind,
                        "holdings": picks,
                    })

                # —— 板块聚合 Top100 ——
                agg_groups = defaultdict(list)
                for s in all_hold[:100]:
                    blk = _match_block(s["name"], s["code6"])
                    sina, _ = _lookup_sina(s["name"], s["code6"])
                    agg_groups[blk].append({
                        "code6": s["code6"], "name": s["name"],
                        "sina": sina,
                        "total_pct": s["total_pct"],
                        "total_mv": s["total_mv"],
                        "fund_count": s["fund_count"],
                    })

                # 排序每板块内按市值
                for blk in agg_groups:
                    agg_groups[blk].sort(key=lambda x: -x["total_mv"])

                agg_list = sorted(agg_groups.items(), key=lambda x: -sum(s["total_mv"] for s in x[1]))

                # 写缓存
                _out = {
                    "funds": fund_rows,
                    "agg": [{"block": b, "stocks": s} for b, s in agg_list],
                    "date": _today,
                }
                try:
                    os.makedirs(os.path.dirname(_cache_path), exist_ok=True)
                    with open(_cache_path, "w", encoding="utf-8") as f:
                        json.dump(_out, f, ensure_ascii=False, indent=2, default=str)
                    print(f"[基金持仓] 缓存已写: {_cache_path}", flush=True)
                except Exception:
                    pass

                _data["funds"] = fund_rows
                _data["agg"] = [{"block": b, "stocks": s} for b, s in agg_list]
                root.after(0, lambda: (_render_all(),
                    status.configure(text=f"✅ {len(fund_rows)} 只基金, Top {len(all_hold)} 重仓股", foreground=_FG_GREEN)))
            except Exception as e:
                import traceback; traceback.print_exc()
                root.after(0, lambda: status.configure(
                    text=f"❌ 拉取失败: {e}", foreground=_FG_RED))
            finally:
                _running = False

        threading.Thread(target=_bg, daemon=True).start()

    def _bind_click_deep(widget, handler):
        try:
            widget.bind("<ButtonRelease-1>", handler)
            widget.bind("<Double-Button-1>", handler)
        except Exception:
            pass
        for c in widget.winfo_children():
            _bind_click_deep(c, handler)

    # ── 渲染: 基金卡片 ──
    def _render_fund_cards():
        for w in card_inner.winfo_children():
            w.destroy()
        funds = _data.get("funds", [])
        if not funds:
            ttk.Label(card_inner, text="⏳ 暂无数据", background=_BG_DEEP, foreground=_FG_DIM).pack(pady=40)
            return

        # 3 列网格
        cols = 3
        for fi, f in enumerate(funds):
            r, c = divmod(fi, cols)
            card = tk.Frame(card_inner, bg=_BG_CARD,
                            highlightbackground=_FG_BLUE, highlightthickness=1)
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
            card_inner.grid_columnconfigure(c, weight=1)

            # 标题行: 单击弹日K / 双击跳天天基金
            hd = tk.Frame(card, bg=_BG_CARD); hd.pack(fill=tk.X, padx=6, pady=(6, 2))
            fund_code = f.get("code", "")
            fund_sina, _ = _lookup_sina(f['name'], fund_code)
            # A股 6位 code 构造 sina
            if not fund_sina and fund_code and fund_code.isdigit() and len(fund_code) == 6:
                fund_sina = ("sh" if fund_code.startswith("6") else "bj" if fund_code.startswith(("4","8")) else "sz") + fund_code
            _nm_lbl = tk.Label(hd, text=f"🏦 {f['name']}", bg=_BG_CARD, fg=_FG_GOLD,
                     font=_font(bold=True), cursor="hand2")
            _nm_lbl.pack(side=tk.LEFT)
            _code_lbl = tk.Label(hd, text=f"({fund_code})", bg=_BG_CARD, fg=_FG_DIM,
                     font=_font(), cursor="hand2")
            _code_lbl.pack(side=tk.LEFT, padx=4)
            _ind_lbl = tk.Label(hd, text=f"#{f['industry']}", bg=_BG_CARD, fg=_FG_CYAN,
                     font=_font())
            _ind_lbl.pack(side=tk.RIGHT)
            # 单击 → 日K (延迟 250ms 判断不是双击)
            _pending = [None]
            def _click(_s=fund_sina, _n=f['name']):
                if _pending[0] is not None:
                    try: root.after_cancel(_pending[0])
                    except: pass
                if _s: _open_kline(root, _s, _n)
                else: _open_fund_web(fund_code)
            def _dbl(_c=fund_code):
                if _pending[0] is not None:
                    try: root.after_cancel(_pending[0])
                    except: pass
                _open_fund_web(_c)
            def _on_btn1(_s=fund_sina, _n=f['name']):
                if _pending[0] is not None:
                    try: root.after_cancel(_pending[0])
                    except: pass
                _pending[0] = root.after(250, lambda: _open_kline(root, _s, _n) if _s else _open_fund_web(fund_code))
            for w in [_nm_lbl, _code_lbl, hd]:
                w.bind("<Button-1>", lambda e: _on_btn1())
                w.bind("<Double-Button-1>", lambda e: _dbl())

            tk.Frame(card, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6, pady=2)

            # 持仓列表
            for hi, h in enumerate(f.get("holdings", [])):
                sina, _ = _lookup_sina(h["name"], h["code6"])
                row_bg = "#2A2A3A" if hi % 2 == 0 else _BG_CARD
                row = tk.Frame(card, bg=row_bg, cursor="hand2")
                row.pack(fill=tk.X, padx=2, pady=1)

                def _mk_click(_s=sina, _n=h["name"]):
                    return lambda e: _on_stock_click(e, _s, _n)
                _h = _mk_click()
                # row 自己 + 所有子控件都绑
                row.bind("<ButtonRelease-1>", _h)
                row.bind("<Double-Button-1>", _h)

                _idx_lbl = tk.Label(row, text=f"{hi+1}.", bg=row_bg, fg=_FG_DIM,
                                    font=_font(), width=2)
                _idx_lbl.pack(side=tk.LEFT)
                _idx_lbl.bind("<ButtonRelease-1>", _h); _idx_lbl.bind("<Double-Button-1>", _h)

                _nm_lbl = tk.Label(row, text=h["name"], bg=row_bg, fg=_FG_TEXT,
                                   font=_font())
                _nm_lbl.pack(side=tk.LEFT, padx=2)
                _nm_lbl.bind("<ButtonRelease-1>", _h); _nm_lbl.bind("<Double-Button-1>", _h)

                _pct_lbl = tk.Label(row, text=f"占{h['total_pct']:.1f}%", bg=row_bg,
                                    fg=_FG_GOLD, font=_font())
                _pct_lbl.pack(side=tk.RIGHT, padx=6)
                _pct_lbl.bind("<ButtonRelease-1>", _h); _pct_lbl.bind("<Double-Button-1>", _h)

            tk.Frame(card, bg=_BG_CARD, height=4).pack(fill=tk.X)

    # ── 渲染: 板块聚合 ──
    def _render_agg():
        for w in agg_inner.winfo_children():
            w.destroy()
        agg = _data.get("agg", [])
        if not agg:
            ttk.Label(agg_inner, text="⏳ 暂无数据", background=_BG_DEEP, foreground=_FG_DIM).pack(pady=40)
            return

        for blk_entry in agg:
            blk = blk_entry["block"]
            stocks = blk_entry["stocks"]
            total_mv = sum(s["total_mv"] for s in stocks)
            total_pct = sum(s["total_pct"] for s in stocks)

            # 板块头
            hd = tk.Frame(agg_inner, bg=_BG_CARD); hd.pack(fill=tk.X, padx=6, pady=(8, 2))
            tk.Label(hd, text=f"📌 {blk}  ({len(stocks)}只)", bg=_BG_CARD, fg=_FG_GOLD,
                     font=("", 10, "bold")).pack(side=tk.LEFT, padx=8, pady=4)
            tk.Label(hd, text=f"持仓市值合计 {total_mv:.0f}亿  占比 {total_pct:.1f}%",
                     bg=_BG_CARD, fg=_FG_DIM, font=("", 8)).pack(side=tk.RIGHT, padx=8)

            tk.Frame(agg_inner, bg=_FG_DIM, height=1).pack(fill=tk.X, padx=6)

            # 股票行
            for hi, s in enumerate(stocks[:10]):  # 每板块最多 10 只
                row_bg = _BG_CARD if hi % 2 == 0 else "#2A2A3A"
                row = tk.Frame(agg_inner, bg=row_bg, cursor="hand2")
                row.pack(fill=tk.X, padx=6, pady=1)

                def _mk(_s=s["sina"], _n=s["name"]):
                    return lambda e: _on_stock_click(e, _s, _n)
                _h = _mk()
                row.bind("<ButtonRelease-1>", _h); row.bind("<Double-Button-1>", _h)

                def _bind_all(parent, _h2=_h):
                    parent.bind("<ButtonRelease-1>", _h2); parent.bind("<Double-Button-1>", _h2)
                    for c in parent.winfo_children():
                        _bind_all(c, _h2)

                _idx = tk.Label(row, text=f"{hi+1}.", bg=row_bg, fg=_FG_DIM,
                               font=_font(bold=True), width=3)
                _idx.pack(side=tk.LEFT, padx=(4,0))
                _nm = tk.Label(row, text=s["name"], bg=row_bg, fg=_FG_TEXT,
                               font=_font(bold=True))
                _nm.pack(side=tk.LEFT, padx=2)
                _code = tk.Label(row, text=f"({s['code6']})", bg=row_bg, fg=_FG_DIM,
                                 font=_font())
                _code.pack(side=tk.LEFT)
                _fc = tk.Label(row, text=f"{s['fund_count']}只基金持有", bg=row_bg,
                               fg=_FG_BLUE, font=_font())
                _fc.pack(side=tk.LEFT, padx=10)
                _mv = tk.Label(row, text=f"{s['total_mv']:.1f}亿", bg=row_bg,
                               fg=_FG_CYAN, font=_font())
                _mv.pack(side=tk.RIGHT, padx=8)
                _pct = tk.Label(row, text=f"{s['total_pct']:.1f}%", bg=row_bg,
                                fg=_FG_GOLD, font=_font(), width=6, anchor="e")
                _pct.pack(side=tk.RIGHT)

                # 给 row + 所有子 Label 都绑
                for w in [row, _idx, _nm, _code, _fc, _mv, _pct]:
                    w.bind("<ButtonRelease-1>", _h)
                    w.bind("<Double-Button-1>", _h)

    def _rerender_all():
        """字体调节后重绘所有 Tab"""
        _render_fund_cards()
        _render_agg()
        _render_guide()

    def _render_all():
        _render_fund_cards()
        _render_agg()

    # ── 自动触发 ──
    parent.after(300, lambda: _load_data(force=False))
    parent.after(2000, lambda: _load_timing(force=False))  # 择时等宏观数据

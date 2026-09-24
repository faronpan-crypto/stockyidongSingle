#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🗓️ 大跌大涨日历记录与预警系统 (crash_rally_calendar.py)
独立子程序，可由 stockyidong mac.py 主程序按钮调用，也可单独运行。
功能：
  1. 历史事件库 (SQLite crash_rally_events 表)
  2. 4 个 Tab：历史事件记录 / 事件日历视图 / 信号回测 / 盘中实时预警
  3. 内置 2018-2026 主要暴跌暴涨种子数据
  4. 腾讯行情接口拉取实时指数涨跌幅
依赖：sqlite3 / tkinter / requests (标准库+常用三方库)
"""
import os
import sys
import json
import sqlite3
import threading
import time
import datetime as _dt
from datetime import datetime as _dt2
import contextlib
import io
import traceback

# ---------- 第三方库 ----------
try:
    import requests
except Exception:
    requests = None

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

# ---------- 数据库路径 (复用主程序约定) ----------
_DB_DIR = os.path.join(os.path.expanduser("~"), ".qclaw")
os.makedirs(_DB_DIR, exist_ok=True)
DB_PATH = os.path.join(_DB_DIR, "stock_analysis.db")

# ---------- 字体/样式 ----------
FONT_MAIN = ("Microsoft YaHei", 10)
FONT_TITLE = ("Microsoft YaHei", 12, "bold")
FONT_SMALL = ("Microsoft YaHei", 9)
COLOR_BG = "#1A1A2E"
COLOR_FG = "#E0E0E0"
COLOR_CRASH = "#2E7D32"      # 绿 (大跌)
COLOR_RALLY = "#C62828"      # 红 (大涨)
COLOR_WARN = "#FF6F00"
COLOR_INFO = "#1565C0"


# ============================================================
# 一、数据库初始化
# ============================================================
def init_crash_rally_db():
    """初始化 crash_rally_events 表 (幂等)"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS crash_rally_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date TEXT NOT NULL,
            event_type TEXT NOT NULL,
            index_name TEXT,
            index_pct REAL,
            magnitude TEXT,
            trigger TEXT,
            trigger_detail TEXT,
            leading_signals TEXT,
            signal_days_before TEXT,
            recovery_days INTEGER DEFAULT -1,
            max_recover_pct REAL DEFAULT 0,
            notes TEXT,
            source_urls TEXT,
            related_stocks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_date, index_name)
        )
    ''')
    # 兼容老库: 若 related_stocks 列缺失则补上
    try:
        cur.execute("ALTER TABLE crash_rally_events ADD COLUMN related_stocks TEXT")
    except Exception:
        pass
    cur.execute('CREATE INDEX IF NOT EXISTS idx_cr_date ON crash_rally_events(event_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_cr_type ON crash_rally_events(event_type)')
    conn.commit()
    conn.close()


# ============================================================
# 二、种子数据 (2018-2026 主要暴跌暴涨)
# ============================================================
SEED_EVENTS = [
    # 2018
    ("2018-02-06", "crash", "上证", -3.35, "大跌", "外围冲击", "美股道指-4.6%史上最大点数跌幅",
     "北向3日流出200亿,BIAS20>5%", "1天前", -1, 0, "全球同步暴跌", ""),
    ("2018-02-09", "crash", "上证", -4.05, "大跌", "外围冲击", "美股连续大跌传导",
     "美股期指<-2%", "当天早盘", 30, 2.1, "随后1月反弹", ""),
    ("2018-03-23", "crash", "上证", -3.63, "大跌", "外围冲击", "中美贸易战首轮加征关税",
     "纳指期指<-1.5%,北向流出", "1天前", -1, 0, "贸易战开端", ""),
    ("2018-06-19", "crash", "上证", -3.78, "大跌", "外围冲击", "中美贸易战升级+股权质押爆雷",
     "跌停>200家", "当天", -1, 0, "股权质押风险", ""),
    ("2018-10-11", "crash", "上证", -5.22, "崩盘", "外围冲击", "美股前夜大跌传导",
     "纳指<-3%", "1天前", 45, 3.2, "政策底出现", ""),
    ("2018-10-18", "crash", "上证", -2.94, "刹跌", "技术破位", "指数跌破2500创4年新低",
     "RSI14<25,涨跌家数<300", "当天", 60, 4.5, "随后见底", ""),

    # 2019
    ("2019-02-25", "rally", "上证", 5.60, "大涨", "政策利好", "中美谈判超预期+央行吹风宽松",
     "情绪冰点后北向大涌入", "2天前", -1, 0, "春季躁动启动", ""),
    ("2019-05-06", "crash", "上证", -5.58, "崩盘", "外围冲击", "特朗普推特加征关税谈判破裂",
     "纳指期指<-2%", "1天前", 20, 1.8, "", ""),
    ("2019-05-10", "crash", "上证", -2.98, "刹跌", "外围冲击", "中美谈判破裂后续",
     "北向连续流出", "当天", 10, 1.2, "", ""),
    ("2019-08-06", "crash", "上证", -1.56, "刹跌", "外围冲击", "美股前夜大跌+人民币破7",
     "汇率贬值", "1天前", 5, 0.8, "", ""),

    # 2020
    ("2020-01-23", "crash", "上证", -2.75, "刹跌", "外围冲击", "武汉封城,新冠疫情爆发",
     "春节前最后交易日", "当天", 3, 1.5, "节后深跌", ""),
    ("2020-02-03", "crash", "上证", -7.72, "崩盘", "外围冲击", "春节后首日疫情恐慌集中释放",
     "跌停>3000家", "当天", 15, 5.2, "黄金坑", ""),
    ("2020-02-04", "rally", "上证", 4.87, "大涨", "政策利好", "央行逆回购1.2万亿+政策呵护",
     "情绪冰点反转", "1天前", -1, 0, "反弹启动", ""),
    ("2020-03-16", "crash", "上证", -3.40, "大跌", "外围冲击", "美股4天内3次熔断",
     "美股期指<-3%,VIX>60", "1天前", 10, 2.5, "全球流动性危机", ""),
    ("2020-03-20", "rally", "上证", 1.61, "小涨", "政策利好", "美联储无限QE+全球救市",
     "VIX见顶回落", "1天前", -1, 0, "全球反弹", ""),
    ("2020-07-06", "rally", "上证", 5.71, "大涨", "资金涌入", "北向大流入+券商股涨停潮",
     "北向单日流入200亿", "当天", -1, 0, "牛市启动", ""),
    ("2020-07-16", "crash", "上证", -4.50, "大跌", "情绪高潮", "连续大涨后获利盘出逃",
     "涨跌家数比极端", "1天前", 20, 1.5, "短线见顶", ""),

    # 2021
    ("2021-02-22", "crash", "上证", -1.45, "刹跌", "情绪高潮", "核心资产抱团瓦解",
     "龙头股闪崩,RSI>80", "1天前", 30, 2.0, "茅指数见顶", ""),
    ("2021-02-24", "crash", "上证", -1.99, "刹跌", "情绪高潮", "抱团股继续瓦解",
     "融资余额拐点", "当天", 45, 1.2, "", ""),
    ("2021-02-26", "crash", "创业板", -3.37, "大跌", "情绪高潮", "创业板抱团股崩塌",
     "BIAS20>8%", "1天前", 60, 3.5, "创业板见顶", ""),
    ("2021-07-02", "crash", "上证", -1.95, "刹跌", "行业崩塌", "双减政策教育股崩盘",
     "板块闪崩", "1天前", 20, 1.0, "", ""),
    ("2021-07-26", "crash", "上证", -2.34, "刹跌", "行业崩塌", "双减政策发酵+中概股大跌",
     "美股中概<-5%", "1天前", 30, 1.5, "", ""),
    ("2021-07-28", "crash", "上证", -2.02, "刹跌", "行业崩塌", "外资抛售中国资产",
     "北向连续3日大流出", "当天", 15, 0.8, "", ""),
    ("2021-09-29", "crash", "上证", -1.83, "刹跌", "情绪高潮", "限电限产+周期股见顶",
     "涨停潮次日", "1天前", 40, 1.8, "", ""),

    # 2022
    ("2022-03-07", "crash", "上证", -1.30, "刹跌", "外围冲击", "俄乌战争+大宗暴涨",
     "纳指<-2%", "1天前", 10, 0.8, "", ""),
    ("2022-03-15", "crash", "上证", -4.95, "大跌", "外围冲击", "俄乌战争发酵+中概退市担忧",
     "北向流出创纪录", "当天", 20, 2.5, "金融委会议救市", ""),
    ("2022-04-25", "crash", "上证", -5.13, "崩盘", "汇率贬值", "人民币破6.6,资本外流担忧",
     "北向单日流出43亿,融资余额3日降300亿", "1天前", 15, 2.0, "", ""),
    ("2022-04-26", "crash", "上证", -1.44, "刹跌", "汇率贬值", "汇率继续贬值+业绩雷",
     "业绩雷", "当天", 5, 1.5, "见底", ""),
    ("2022-09-15", "crash", "上证", -1.16, "刹跌", "外围冲击", "美股前夜大跌",
     "纳指<-2%", "1天前", 10, 0.5, "", ""),
    ("2022-09-16", "crash", "上证", -1.30, "刹跌", "外围冲击", "美股持续调整传导",
     "BIAS20<-4%", "当天", 15, 1.0, "", ""),
    ("2022-10-24", "crash", "上证", -2.02, "刹跌", "汇率贬值", "人民币破7.3",
     "北向流出", "1天前", 20, 1.2, "", ""),

    # 2023
    ("2023-08-04", "crash", "上证", -0.59, "刹跌", "情绪高潮", "券商股涨停潮次日见顶",
     "涨停>150", "1天前", 30, 1.5, "", ""),
    ("2023-08-11", "crash", "上证", -2.01, "刹跌", "情绪高潮", "券商股继续回落",
     "龙头股闪崩", "当天", 40, 0.8, "", ""),

    # 2024
    ("2024-01-22", "crash", "上证", -2.68, "刹跌", "流动性危机", "雪球产品敲入担忧+量化踩踏",
     "跌停>50家", "1天前", 20, 1.5, "", ""),
    ("2024-01-29", "crash", "上证", -4.00, "大跌", "政策收紧", "史上最严IPO核查+量化基金监管",
     "连续5日融资余额下降", "3天前", 10, 2.0, "", ""),
    ("2024-01-31", "crash", "上证", -1.48, "刹跌", "业绩地雷", "年报季业绩雷集中",
     "商誉减值", "当天", 15, 1.0, "", ""),
    ("2024-02-05", "crash", "上证", -1.02, "刹跌", "流动性危机", "雪球产品大规模敲入,量化踩踏",
     "跌停>80家,融资余额降速加快", "1天前", 3, 2.5, "见底", ""),
    ("2024-09-24", "rally", "上证", 4.15, "大涨", "政策利好", "央行降准降息组合拳,超预期宽松",
     "北向2日流入200亿,情绪冰点回升", "1天前", -1, 0, "9.24行情", ""),

    # 2025
    ("2025-04-07", "crash", "上证", -7.34, "崩盘", "外围冲击", "特朗普对等关税,全球暴跌",
     "纳指期指<-5%", "1天前", 10, 3.5, "关税战", ""),
    ("2025-07-07", "crash", "上证", -6.62, "崩盘", "外围冲击", "特朗普关税升级,全球市场恐慌",
     "纳指期指<-4%,北向流出创纪录", "1天前", 15, 4.0, "", ""),

    # 2026
    ("2026-09-24", "crash", "上证", 0.0, "未知", "未知/综合", "待填",
     "待填", "待填", -1, 0, "今天", ""),
]


def seed_events_if_empty():
    """表为空时插入种子数据"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM crash_rally_events")
        n = cur.fetchone()[0]
        if n == 0:
            for row in SEED_EVENTS:
                cur.execute('''
                    INSERT OR IGNORE INTO crash_rally_events
                    (event_date,event_type,index_name,index_pct,magnitude,trigger,
                     trigger_detail,leading_signals,signal_days_before,
                     recovery_days,max_recover_pct,notes,source_urls)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', row)
            conn.commit()
            print(f"[大跌大涨] 已插入 {len(SEED_EVENTS)} 条种子数据")
        else:
            print(f"[大跌大涨] 已有 {n} 条数据,跳过种子")
        conn.close()
    except Exception as e:
        print(f"[大跌大涨] 种子数据插入失败(跳过): {e}")


# ============================================================
# 三、数据抓取 (腾讯行情)
# ============================================================
class TencentQuote:
    """腾讯实时行情抓取"""
    def __init__(self):
        if requests is None:
            raise RuntimeError("requests 库未安装")
        self.s = requests.Session()
        self.s.headers.update({'User-Agent': 'Mozilla/5.0'})

    def get_index_realtime(self, codes=None):
        """获取指数实时行情
        codes: ['sh000001','sz399001','sz399006']
        返回 [{name,pct,price,prev,amount_wan}, ...]
        """
        if codes is None:
            codes = ["sh000001", "sz399001", "sz399006"]
        url = "https://qt.gtimg.cn/q=" + ",".join(codes)
        try:
            r = self.s.get(url, timeout=6)
            r.encoding = 'gbk'
            parts = r.text.strip().split(";")
            out = []
            for i, p in enumerate(parts):
                p = p.strip()
                if not p or '=' not in p:
                    continue
                body = p.split('=', 1)[1].strip('"')
                f = body.split("~")
                if len(f) < 40:
                    continue
                name = f[1] if len(f) > 1 else codes[i] if i < len(codes) else "?"
                price = float(f[3]) if len(f) > 3 and f[3] else 0
                prev = float(f[4]) if len(f) > 4 and f[4] else 0
                pct = float(f[32]) if len(f) > 32 and f[32] else 0.0
                amount_wan = float(f[37]) if len(f) > 37 and f[37] else 0
                out.append({"name": name, "price": price, "prev": prev,
                            "pct": pct, "amount_wan": amount_wan, "code": codes[i] if i < len(codes) else ""})
            return out
        except Exception as e:
            print(f"[大跌大涨] 实时行情抓取失败: {e}")
            return []

    def get_kline(self, code="sh000001", count=60):
        """获取日K线 (腾讯)
        返回 [{date,open,close,high,low,volume}]
        """
        url = f"https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={code},day,,,{count}"
        try:
            r = self.s.get(url, timeout=8)
            data = r.json()
            kls = data.get("data", {}).get(code, {}).get("day") or data.get("data", {}).get(code, {}).get("qianfuquan") or []
            out = []
            for k in kls[-count:]:
                if len(k) >= 6:
                    out.append({"date": k[0], "open": float(k[1]), "close": float(k[2]),
                                 "high": float(k[3]), "low": float(k[4]), "volume": float(k[5])})
            return out
        except Exception as e:
            print(f"[大跌大涨] K线抓取失败: {e}")
            return []


# ============================================================
# 四、历史事件自动扫描器 (完整版: K线扫描 + 规则归因 + 新闻抓取)
# ============================================================

# ---------- 4.1 规则引擎: 历史时间段归因字典 ----------
# 格式: (起始日期YYYY-MM-DD, 结束日期YYYY-MM-DD) -> (trigger, trigger_detail)
_TRIGGER_TIMELINE = [
    # ========== 2008 年 ==========
    ("2008-01-20", "2008-01-21", "外围冲击", "全球股市暴跌+美股花旗警告亏损+A股暴跌4%"),
    ("2008-06-01", "2008-06-17", "情绪高潮", "上调存款准备金率+越南金融危机传导+A股急跌"),
    ("2008-09-15", "2008-09-25", "外围冲击", "雷曼兄弟破产+全球金融危机全面爆发+美股单日暴跌504点"),
    ("2008-10-05", "2008-10-10", "外围冲击", "全球股市连跌+A股开启单边下跌+全球央行救市"),
    ("2008-11-09", "2008-11-11", "政策利好", "4万亿经济刺激计划出台+十大产业振兴规划"),
    # 2010 年
    ("2010-04-15", "2010-05-07", "政策收紧", "史上最严房地产调控+信贷收紧+上证从3200跌至2481"),
    ("2010-11-12", "2010-11-17", "政策收紧", "上调存款准备金率+楼市二次调控+大宗商品回落"),
    # 2011 欧债 + 全球流动性危机
    ("2011-08-05", "2011-08-09", "外围冲击", "美债评级下调+全球股市暴跌+A股跌破2600"),
    ("2011-09-12", "2011-09-28", "外围冲击", "欧债危机发酵+希腊违约担忧+全球央行流动性紧张"),
    # 2012 年
    ("2012-03-07", "2012-03-12", "外围冲击", "欧债危机升级+葡萄牙救助+A股急跌"),
    ("2012-09-21", "2012-09-24", "政策利好", "央行重启逆回购+温总理讲话提振信心+A股反弹"),
    # 2013 钱荒
    ("2013-06-19", "2013-06-25", "流动性危机", "银行间资金紧张+钱荒+SHIBOR飙升+A股暴跌"),
    ("2013-07-08", "2013-07-29", "政策收紧", "央行继续锁流动性+IPO重启+A股连跌4天"),
    # 2014 牛市启动
    ("2014-11-24", "2014-12-10", "资金涌入", "央行降息+沪深港通+融资余额激增+A股牛市启动"),
    # 2015 股灾 (akshare 有数据)
    ("2015-06-12", "2015-07-09", "去杠杆/股灾", "牛市见顶+配资清理+证监会严打场外配资"),
    ("2015-08-18", "2015-08-26", "去杠杆/股灾", "股灾2.0+证金救市"),
    ("2015-09-15", "2015-09-17", "去杠杆/股灾", "股灾3.0+美联储加息预期"),
    # 2016 熔断
    ("2016-01-04", "2016-01-14", "熔断机制", "A股首次实施涨跌停熔断机制触发多次熔断"),
    ("2016-01-26", "2016-02-01", "外围冲击", "全球股市暴跌+原油价格跌破27+A股急跌"),
    # 2016 英国脱欧
    ("2016-06-24", "2016-06-27", "外围冲击", "英国公投脱欧，全球市场恐慌"),
    # 2016 年底
    ("2016-12-09", "2016-12-13", "监管收紧", "险资举牌监管收紧+刘士余讲话"),
    # 2017 金融去杠杆
    ("2017-04-05", "2017-04-12", "监管收紧", "银监会严查同业+金融去杠杆"),
    # 2018 贸易战 (种子数据已覆盖, 这里补时间段)
    ("2018-03-22", "2019-06-30", "外围冲击", "中美贸易战首轮加征关税+后续多轮升级"),
    # 2018 股权质押风险
    ("2018-06-19", "2018-10-25", "流动性危机", "股权质押爆雷+贸易战叠加"),
    # 2019 春季躁动
    ("2019-02-18", "2019-03-07", "政策利好", "中美谈判预期+央行宽松吹风+春季躁动"),
    # 2019 科创板开市
    ("2019-07-22", "2019-07-24", "新股供应", "科创板首批25家公司上市"),
    # 2020 新冠疫情
    ("2020-01-20", "2020-04-30", "疫情冲击", "新冠疫情全球蔓延+春节后首日恐慌+全球流动性危机"),
    ("2020-02-24", "2020-03-23", "疫情冲击", "海外疫情爆发+美股4天内3次熔断"),
    # 2020 创业板注册制
    ("2020-08-24", "2020-08-24", "新股供应", "创业板首批注册制新股上市"),
    # 2020 9月科技股调整
    ("2020-09-09", "2020-09-10", "情绪高潮", "科技股高位+美国制裁华为升级"),
    # 2021 核心资产抱团瓦解
    ("2021-01-11", "2021-02-26", "情绪高潮", "茅指数见顶+核心资产抱团瓦解"),
    # 2021 双减 + 中概
    ("2021-07-01", "2021-08-31", "行业崩塌", "双减政策+中概股被SEC调查+教育股崩盘"),
    # 2021 能耗双控
    ("2021-09-15", "2021-10-15", "政策收紧", "能耗双控+拉闸限电+周期股见顶"),
    # 2022 俄乌战争
    ("2022-02-24", "2022-05-31", "外围冲击", "俄乌战争爆发+大宗商品暴涨+能源危机"),
    # 2022 上海疫情 + 人民币汇率
    ("2022-03-28", "2022-05-10", "疫情冲击", "上海封控+人民币贬值破6.6+外资流出"),
    # 2022 金融委救市 (4.29)
    ("2022-04-26", "2022-05-05", "政策利好", "金融委会议专题+国务院联防联控发布会"),
    # 2022 美联储加息
    ("2022-09-15", "2022-11-04", "外围冲击", "美联储激进加息+美元指数破114+全球央行跟加息"),
    # 2022 人民币破7.3
    ("2022-10-20", "2022-11-04", "汇率贬值", "人民币破7.3+外汇储备下降+港股暴跌"),
    # 2022 11月疫情政策转向
    ("2022-11-28", "2022-12-23", "政策利好", "防疫二十条+防疫新十条+地产三支箭+美联储降息预期"),
    # 2023 北向外资
    ("2023-05-09", "2023-06-01", "外围冲击", "北向外资持续流出+美元指数反弹+人民币贬值"),
    # 2023 7-8月 印花税传闻 + 券商行情
    ("2023-07-24", "2023-08-31", "政策预期", "印花税降半传闻+券商股涨停潮后见顶+地产链下行"),
    # 2023 9月 汇金增持四大行
    ("2023-09-25", "2023-10-25", "政策利好", "汇金增持四大行+量化新规+地产政策松绑"),
    # 2024 年初 雪球 + 量化踩踏
    ("2024-01-18", "2024-02-10", "流动性危机", "雪球产品敲入担忧+量化基金监管+史上最严IPO核查"),
    # 2024 两会
    ("2024-03-04", "2024-03-15", "政策预期", "两会政策预期+总理记者会+经济目标制定"),
    # 2024 4月 创业板见顶
    ("2024-04-23", "2024-04-30", "情绪高潮", "创业板指创新高+红利低波见顶+中报预披露雷"),
    # 2024 9.24 行情
    ("2024-09-23", "2024-10-15", "政策利好", "央行降准降息组合拳+存量房贷利率下调+9.24行情"),
    # 2024 10月特朗普胜选
    ("2024-11-04", "2024-11-20", "外围冲击", "特朗普大选获胜+关税政策预期+科技制裁升级"),
    # 2024 11月地产救市
    ("2024-11-20", "2024-12-15", "政策利好", "地产三大政策优化+央行MLF降利率+降准预期"),
    # 2025 关税战
    ("2025-04-02", "2025-05-15", "外围冲击", "特朗普对等关税+全球市场暴跌+纳指熔断"),
    # 2025 7月 关税升级
    ("2025-07-05", "2025-08-15", "外围冲击", "特朗普关税升级至50%+全球市场恐慌+北向流出创纪录"),
    # 2025 8月 全球央行救市
    ("2025-08-20", "2025-09-10", "政策利好", "全球央行联合降息+美联储紧急救市"),
]

# 新闻关键词 -> (trigger候选, 权重)
_NEWS_KEYWORDS = [
    ("贸易战", ("外围冲击", "中美贸易")),
    ("美联储", ("外围冲击", "美联储加息/降息")),
    ("加息", ("外围冲击", "美联储加息")),
    ("降息", ("政策利好", "央行降息")),
    ("降准", ("政策利好", "央行降准")),
    ("印花税", ("政策预期", "印花税调整")),
    ("疫情", ("疫情冲击", "新冠疫情")),
    ("封城", ("疫情冲击", "新冠疫情封控")),
    ("熔断", ("外围冲击", "美股熔断")),
    ("俄乌", ("外围冲击", "俄乌战争")),
    ("关税", ("外围冲击", "关税调整")),
    ("特朗普", ("外围冲击", "特朗普政策")),
    ("人民币", ("汇率贬值", "人民币汇率波动")),
    ("汇率", ("汇率贬值", "汇率波动")),
    ("外资", ("流动性危机", "北向外资流动")),
    ("北向", ("流动性危机", "北向资金流动")),
    ("爆雷", ("业绩地雷", "业绩雷")),
    ("业绩预亏", ("业绩地雷", "业绩雷")),
    ("商誉减值", ("业绩地雷", "商誉减值")),
    ("双减", ("行业崩塌", "双减政策")),
    ("地产", ("行业崩塌", "地产行业")),
    ("爆仓", ("流动性危机", "爆仓风险")),
    ("量化", ("流动性危机", "量化基金")),
    ("资金杠杆", ("流动性危机", "去杠杆")),
    ("IPO", ("新股供应", "IPO")),
    ("注册制", ("新股供应", "注册制")),
    ("救市", ("政策利好", "救市政策")),
    ("央行", ("政策利好", "央行货币政策")),
    ("政策利好", ("政策利好", "政策利好")),
    ("融资", ("技术破位", "融资余额")),
    ("放量", ("量价异常", "量能异动")),
    ("缩量", ("量价异常", "缩量整理")),
    ("北向大流入", ("资金涌入", "北向大资金流入")),
    ("央行逆回购", ("政策利好", "央行流动性投放")),
    ("流动性", ("流动性危机", "流动性紧张")),
]

# 指数代码映射 (akshare)
_INDEX_CODES = {
    "上证": "sh000001",
    "深证": "sz399001",
    "创业板": "sz399006",
    "科创50": "sh000688",
}

# 情绪阶段 → emoji + 颜色映射
EMO_STAGE_EMOJI = {
    "冰点":  ("🧊", "#80DEEA"),
    "启动":  ("🚀", "#A5D6A7"),
    "发酵":  ("🌱", "#66BB6A"),
    "高潮":  ("🔥", "#EF5350"),
    "分歧":  ("⚡", "#FFA726"),
    "退潮":  ("🌧️", "#78909C"),
    "震荡":  ("〰️", "#B0BEC5"),
    "📊暴跌": ("🩸", "#C62828"),
}

EMO_HIST_PATH = os.path.join(os.path.expanduser("~"),
                             ".qclaw/workspace-agent-85985980/stockyidong_emo_history.json")


def load_emo_history():
    """加载情绪周期历史 (幂等)"""
    try:
        if os.path.exists(EMO_HIST_PATH):
            with open(EMO_HIST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_emo_history(data):
    """保存情绪周期历史"""
    try:
        os.makedirs(os.path.dirname(EMO_HIST_PATH), exist_ok=True)
        with open(EMO_HIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[情绪周期] 保存失败: {e}")


def auto_fill_emo_for_date(date_str, progress_cb=None):
    """
    用 akshare 实时涨跌家数 + 上证日K 自动生成某天情绪周期数据并写回 JSON。
    返回 emo dict (stage, emo_score, pct, up, dn, zt, ths, pnl)
    """
    def _log(m):
        if progress_cb: progress_cb(m)
    try:
        import akshare as ak
    except Exception:
        _log("⚠️ akshare 不可用, 跳过情绪补全")
        return None

    try:
        target = date_str[:10]
        # 1. 拉当天涨跌家数 + 涨停
        up = dn = zt = dt = None
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
                # 简单统计: 涨跌停数 (limit_up / limit_down / 涨跌幅>0 / <0)
                df_pct = df["涨跌幅"].astype(float)
                up = int((df_pct > 0).sum())
                dn = int((df_pct < 0).sum())
                zt = int((df_pct >= 9.5).sum())
                dt = int((df_pct <= -9.5).sum())
                _log(f"  ✅ 涨跌家数: up={up} dn={dn} zt={zt} dt={dt}")
        except Exception as e:
            _log(f"  ⚠️ 实时涨跌家数失败: {type(e).__name__}: {e}")

        # 2. 拉上证日K 算涨跌幅
        pct = 0.0
        try:
            idx_df = ak.stock_zh_index_daily(symbol="sh000001")
            day_row = idx_df[idx_df["date"].astype(str).str[:10] == target]
            if len(day_row) > 0:
                idx = idx_df.index[day_row.index[0]]
                prev_close = idx_df.iloc[idx - 1]["close"] if idx > 0 else day_row.iloc[0]["open"]
                close_val = day_row.iloc[0]["close"]
                pct = round((close_val - prev_close) / prev_close * 100, 2)
                _log(f"  ✅ 上证涨跌幅: {pct:+.2f}%")
        except Exception as e:
            _log(f"  ⚠️ 日K涨跌幅失败: {type(e).__name__}: {e}")

        # 3. 算情绪阶段 + emo_score (复用 tab_dapan.py 逻辑)
        emo_score = 50.0
        stage = "震荡"
        ths = "?"

        if up is not None and dn is not None:
            total = up + dn
            up_ratio = up / total if total > 0 else 0.5
            # 同花顺方向
            if pct > 0.5: ths = "向上"
            elif pct < -0.5: ths = "向下"
            else: ths = "震荡"
            # emo_score 简化公式
            zt_norm = min(zt or 0, 80) / 80
            emo_score = round(up_ratio * 70 + zt_norm * 30 + (pct / 5) * 10, 1)
            emo_score = max(5.0, min(95.0, emo_score))
            # 阶段判断
            if pct <= -3: stage = "📊暴跌"
            elif pct >= 5 and up_ratio >= 0.7: stage = "高潮"
            elif (zt or 0) >= 40 and up_ratio >= 0.55: stage = "发酵"
            elif (zt or 0) >= 15 and up_ratio >= 0.5: stage = "启动"
            elif (zt or 0) < 10 and up_ratio < 0.4: stage = "冰点"
            elif up_ratio < 0.45: stage = "退潮"
            else: stage = "震荡"
        _log(f"  ✅ 情绪阶段: {stage} score={emo_score:.1f}")

        # 4. 组合返回
        emo = {
            "date": target,
            "stage": stage,
            "emo_score": emo_score,
            "pct": pct,
            "up": up, "dn": dn, "zt": zt, "dt": dt,
            "ths": ths,
            "pnl": "亏钱" if pct < 0 else ("赚钱" if pct > 0 else ""),
            "source": "auto_fill",
        }
        return emo
    except Exception as e:
        _log(f"  ❌ 情绪自动补全失败: {type(e).__name__}: {e}")
        return None


class HistoryScanner:
    """自动扫描历史暴涨暴跌 + 规则归因 + 新闻抓取"""

    CRASH_THRESHOLD = -3.0   # 暴跌阈值 (%)
    RALLY_THRESHOLD = 3.0    # 暴涨阈值 (%)
    USE_AKSHARE = True       # True=用 akshare 27年K线, False=退腾讯K线

    def __init__(self, progress_cb=None):
        self.progress = progress_cb or (lambda msg: None)
        self.quote = None
        self._ak_available = False
        try:
            import akshare as _ak
            self._ak = _ak
            self._ak_available = True
            self.progress(f"✅ akshare v{_ak.__version__} 可用")
        except Exception as e:
            self.progress(f"⚠️ akshare 不可用: {e}")
            self._ak_available = False

    # ---------- 核心入口: 扫描所有指数 ----------
    def scan_all_indices(self, years_back=20):
        """扫描所有指数, years_back=年数 (akshare 支持 27年, 腾讯只够最近 3-5 年)"""
        results = []
        indices = list(_INDEX_CODES.items())
        if not self._ak_available:
            # 降级: 用腾讯K线
            try:
                self.quote = TencentQuote()
            except Exception as e:
                self.progress(f"❌ 行情接口都不可用: {e}")
                return results
        for idx_name, idx_code in indices:
            self.progress(f"\n📈 扫描 {idx_name} ({idx_code})...")
            daily = self._fetch_daily(idx_code)
            if not daily:
                self.progress(f"  ❌ 无K线数据, 跳过")
                continue
            self.progress(f"  📊 拉到 {len(daily)} 根日K, 最新 {daily[-1]['date']}")
            idx_events = self._scan_kline(daily, idx_name)
            self.progress(f"  🔍 筛出 {len(idx_events)} 日异动 (|pct|>2%)")
            results.extend(idx_events)
        return results

    # ---------- 4.2 K线获取: akshare 优先, 腾讯兜底 ----------
    def _fetch_daily(self, code):
        """获取日K数据, 返回 [{date, open, close, high, low, volume}]"""
        # ---- 路线 1: akshare stock_zh_index_daily ----
        if self.USE_AKSHARE and self._ak_available:
            try:
                df = self._ak.stock_zh_index_daily(symbol=code)
                if df is not None and len(df) > 0:
                    out = []
                    for _, r in df.iterrows():
                        d = str(r.get("date", ""))[:10]
                        if not d: continue
                        out.append({
                            "date": d,
                            "open": float(r.get("open", 0)),
                            "close": float(r.get("close", 0)),
                            "high": float(r.get("high", 0)),
                            "low": float(r.get("low", 0)),
                            "volume": float(r.get("volume", 0)),
                        })
                    self.progress(f"  ✅ akshare K线 OK, {len(out)} 条")
                    return out
            except Exception as e:
                self.progress(f"  ⚠️ akshare 拉取失败: {type(e).__name__}: {e}")

        # ---- 路线 2: 腾讯 web.ifzq.gtimg.cn ----
        try:
            if self.quote is None:
                self.quote = TencentQuote()
            out = self.quote.get_kline(code, count=2000)
            if out:
                self.progress(f"  ✅ 腾讯 K线 OK, {len(out)} 条")
                return out
        except Exception as e:
            self.progress(f"  ⚠️ 腾讯 拉取失败: {type(e).__name__}: {e}")

        return []

    # ---------- 阈值扫描 ----------
    def _scan_kline(self, daily, idx_name):
        """遍历K线, 按阈值筛异动日"""
        events = []
        # 需要先算每日涨跌幅 (基于前一日收盘)
        closes = [d.get("close", 0) for d in daily]
        prev_closes = [closes[0]] + closes[:-1]  # 前一日收盘
        for i, d in enumerate(daily):
            if i == 0 or prev_closes[i] <= 0:
                continue
            pct = (d["close"] - prev_closes[i]) / prev_closes[i] * 100
            if pct <= self.CRASH_THRESHOLD or pct >= self.RALLY_THRESHOLD:
                ev = {
                    "event_date": d["date"],
                    "event_type": "crash" if pct < 0 else "rally",
                    "index_name": idx_name,
                    "index_pct": round(pct, 2),
                    "magnitude": self.classify_magnitude(pct),
                    "trigger": "",
                    "trigger_detail": "",
                    "source_urls": "auto_scan",
                }
                # 规则归因
                self._rule_attribute(ev)
                events.append(ev)
        return events

    @staticmethod
    def classify_magnitude(pct):
        if pct < -7: return "崩盘"
        if pct < -3: return "大跌"
        if pct < 0:  return "刹跌"
        if pct > 8:  return "暴涨"
        if pct > 3:  return "大涨"
        return "小涨"

    # ---------- 4.3 规则引擎归因 ----------
    def _rule_attribute(self, ev):
        """基于时间段字典归因 trigger + trigger_detail"""
        d = ev["event_date"]
        best_match = None
        best_priority = 99999  # 越小越优
        for start, end, trig, detail in _TRIGGER_TIMELINE:
            if start <= d <= end:
                # 匹配到了, 计算日期差(越小越近越可信)
                try:
                    import datetime as _dt
                    sd = _dt.date.fromisoformat(start)
                    ed = _dt.date.fromisoformat(end)
                    dd_cmp = _dt.date.fromisoformat(d)
                    # 匹配: 事件日期在时间段内即命中, 再按时间段跨度加权 (越小越精准)
                    span_days = (ed - sd).days + 1
                    dd = span_days
                    # 额外加分: 越接近时间段中心越可信
                    center = sd + _dt.timedelta(days=(span_days // 2))
                    dd += abs((dd_cmp - center).days) // 2
                except Exception:
                    dd = 9999
                priority = dd
                if priority < best_priority:
                    best_priority = priority
                    best_match = (trig, detail)
        if best_match:
            ev["trigger"], ev["trigger_detail"] = best_match
            return

        # 规则没命中, 用涨跌幅方向 + 节日效应兜底
        holiday = self._match_holiday(d)
        if holiday:
            if ev["event_type"] == "crash":
                ev["trigger"] = "节前效应"
                ev["trigger_detail"] = f"{holiday} 节前兑现压力+避险"
            else:
                ev["trigger"] = "节后效应"
                ev["trigger_detail"] = f"{holiday} 节后资金回流"
            return

        # 最终兜底: 用涨跌幅度方向做粗糙判断
        if ev["event_type"] == "crash":
            if abs(ev["index_pct"]) >= 5:
                ev["trigger"] = "外围冲击(待补)"
                ev["trigger_detail"] = f"日内跌幅{abs(ev['index_pct']):.1f}%, 请手动确认原因"
            else:
                ev["trigger"] = "情绪回落(待补)"
                ev["trigger_detail"] = f"日内跌幅{abs(ev['index_pct']):.1f}%, 请手动确认原因"
        else:
            if ev["index_pct"] >= 5:
                ev["trigger"] = "资金涌入(待补)"
                ev["trigger_detail"] = f"日内涨幅{ev['index_pct']:.1f}%, 请手动确认原因"
            else:
                ev["trigger"] = "情绪修复(待补)"
                ev["trigger_detail"] = f"日内涨幅{ev['index_pct']:.1f}%, 请手动确认原因"

    def _match_holiday(self, d_str):
        """匹配节日 (前后 3 交易日)"""
        from datetime import date, timedelta
        try:
            target = date.fromisoformat(d_str)
        except Exception:
            return None
        holidays = [
            ("春节", 1, 2015, 2030),
            ("国庆节", 10, 2015, 2030),
            ("劳动节", 5, 2015, 2030),
        ]
        for name, m, start_y, end_y in holidays:
            for y in range(start_y, end_y + 1):
                try:
                    hd = date(y, m, 1)
                except Exception:
                    continue
                delta = (target - hd).days
                if -5 <= delta <= 7:
                    return name
        return None

    # ---------- 4.4 近期新闻抓取 + 关键词匹配 ----------
    def enrich_with_news(self, events, days_window=15):
        """
        对近期事件(默认15天内, 注意: akshare stock_news_em 只返回各板块最新10条新闻,
        历史事件无法用新闻API回溯, 所以新闻增强仅对'当天异动'有效)。
        历史日期归因完全依赖规则引擎, 本函数只补近期窗口内规则未命中的事件。
        """
        if not self._ak_available:
            self.progress("⚠️ 新闻抓取需要 akshare, 当前不可用")
            return events

        from datetime import date, timedelta
        today = date.today()
        cutoff = today - timedelta(days=days_window)
        self.progress(f"📰 新闻增强窗口: {cutoff} ~ {today} (≈{days_window}天)")
        self.progress(f"  ⚠️ akshare stock_news_em 只返回最新10条新闻, 历史日期无法回溯, 仅当天异动能命中")

        # 找出所有需要新闻增强的日期 (在窗口内且 trigger 含 "待补")
        need_news = [
            ev for ev in events
            if cutoff <= date.fromisoformat(ev["event_date"]) <= today
            and ("待补" in ev.get("trigger", "") or not ev.get("trigger"))
        ]
        if not need_news:
            self.progress(f"📰 近期无需要新闻增强的事件 (窗口={days_window}天)")
            return events

        self.progress(f"📰 准备拉取近期财经新闻 ({len(need_news)} 个日期需要增强)...")
        # 拉取财经 + 宏观板块新闻 (各10条, 共约30-40条)
        news_pools = []
        for sym in ["财经", "宏观", "央行", "A股"]:
            try:
                df = self._ak.stock_news_em(symbol=sym)
                if df is not None and len(df) > 0:
                    news_pools.append(df)
                    self.progress(f"  ✅ stock_news_em('{sym}') 拉到 {len(df)} 条")
            except Exception as e:
                self.progress(f"  ⚠️ stock_news_em('{sym}') 失败: {type(e).__name__}")

        if not news_pools:
            self.progress("❌ 所有新闻接口均不可用, 跳过新闻增强")
            return events

        import pandas as pd
        all_news = pd.concat(news_pools, ignore_index=True)
        if "发布时间" not in all_news.columns:
            self.progress("❌ 新闻数据列缺失, 跳过新闻增强")
            return events

        # 遍历待增强事件, 在新闻池中按日期匹配
        for ev in need_news:
            ev_date = ev["event_date"]
            ev_pct = ev["index_pct"]
            # 按日期匹配新闻 (发布时间含 ev_date)
            matched = []
            for _, row in all_news.iterrows():
                pub_time = str(row.get("发布时间", ""))[:10]
                if pub_time == ev_date:  # 只匹配当天新闻 (更精准)
                    title = str(row.get("新闻标题", ""))
                    content = str(row.get("新闻内容", ""))
                    matched.append({
                        "title": title,
                        "content": content,
                        "url": str(row.get("新闻链接", "")),
                        "source": str(row.get("文章来源", "")),
                    })

            if matched:
                # 从 matched 新闻中提取关键词
                best_trigger, best_detail, best_url = self._extract_from_news(matched, ev_pct)
                if best_trigger and "待补" in ev.get("trigger", ""):
                    ev["trigger"] = best_trigger
                    ev["trigger_detail"] = best_detail
                    ev["source_urls"] = f"auto_scan_news|{best_url}"
                    self.progress(f"  📰 新闻增强 ✅ {ev_date} {best_trigger}: {best_detail[:30]}")
                elif best_trigger and not ev.get("trigger"):
                    ev["trigger"] = best_trigger
                    ev["trigger_detail"] = best_detail
                    ev["source_urls"] = f"auto_scan_news|{best_url}"
            else:
                self.progress(f"  📰 {ev_date}: 无匹配新闻, 保持规则归因")
        return events

    def _extract_from_news(self, matched_news, pct):
        """从一组新闻中找最相关的 trigger + detail + url"""
        # 评分: 每条新闻对每个关键词打分
        best_trigger = None
        best_detail = ""
        best_url = ""
        best_score = 0
        for news in matched_news:
            text = (news["title"] + " " + news["content"])[:500]
            for kw, (trig, detail) in _NEWS_KEYWORDS:
                cnt = text.count(kw)
                if cnt > 0:
                    score = cnt * 2
                    # 暴涨匹配积极关键词, 暴跌匹配消极关键词
                    if pct > 0 and ("利好" in trig or "涌入" in trig or "修复" in trig or "爆发" in trig):
                        score += 3
                    if pct < 0 and ("冲击" in trig or "收紧" in trig or "贬值" in trig or "地雷" in trig):
                        score += 3
                    if score > best_score:
                        best_score = score
                        best_trigger = trig
                        best_detail = f"{news['title'][:60]} ({detail})"
                        best_url = news["url"]
        return best_trigger, best_detail, best_url


# ============================================================
# 五、主 GUI 类
# ============================================================
class CrashRallyCalendarApp:
    """大跌大涨日历主应用"""

    # 触发原因字典
    TRIGGER_CRASH = ["外围冲击", "政策收紧", "汇率贬值", "流动性危机", "业绩地雷",
                     "行业崩塌", "技术破位", "情绪高潮", "未知/综合"]
    TRIGGER_RALLY = ["政策利好", "资金涌入", "技术修复", "外围传导", "情绪修复", "题材爆发"]
    MAGNITUDE_OPTS = ["刹跌", "大跌", "崩盘", "小涨", "大涨", "暴涨", "未知"]
    INDEX_OPTS = ["上证", "深证", "创业板", "科创50"]
    # 信号库 (类型, 描述, 量化标准) —— 来自需求 2.3
    SIGNAL_LIB = [
        ("涨跌家数极端", "上涨/下跌家数极度失衡", "涨跌家数比>10:1"),
        ("量能异常", "大幅放量(>前一日1.5倍)", "量比>2.0"),
        ("北向连续流出", "连续3日北向净卖出超百亿", "3日累计北向<-300亿"),
        ("MA乖离率过大", "指数离MA20乖离>5%", "BIAS20>5%"),
        ("RSI超买/超卖", "RSI>80或RSI<30", "RSI14>80或<30"),
        ("融资余额拐点", "融资余额大幅下降", "3日减少>500亿"),
        ("盘口异动", "早盘10:30前跌幅超1%", "10:30指数<昨收-1%"),
        ("情绪高潮/冰点", "涨停/跌停家数极端", "涨停>150或跌停>100"),
        ("美股期货大跌", "A股盘前期指持续走低", "纳指期指<-2%"),
        ("期指贴水扩大", "IH/IF贴水加深", "贴水>20点"),
        ("期权put/call比", "Put成交量异常放大", "PCR>1.5"),
        ("龙头股闪崩", "龙头股莫名其妙大跌", "当日>3只龙头闪崩"),
        ("新股破发率", "新股大面积破发", "破发率>50%"),
    ]
    SIGNAL_NAMES = [s[0] for s in SIGNAL_LIB]
    # 盘中预警阈值 (指标, 暴跌阈值, 暴涨阈值, 描述)
    ALERT_METRICS = [
        ("涨跌家数", "<800 或 >3500", ">2800", "情绪过热"),
        ("早盘30分钟量能", "放大>50%", "放大>80%", "较前5日均值"),
        ("北向实时净流入", "流出>50亿", "流入>100亿", "连续"),
        ("期指贴水", "扩大>30点", "收窄<-20点", ""),
        ("指数BIAS20", ">4% 或 <-4%", ">3%", ""),
        ("RSI14", ">80 或 <30", ">75", ""),
        ("涨停/跌停家数", "跌停>50 或 涨停>150", "涨停80-120", "情绪高潮"),
        ("美股盘前期指", "纳指<-2%", "纳指>+2%", ""),
    ]

    def __init__(self, root, parent_app=None):
        self.root = root
        self.parent = parent_app
        self.quote = None
        try:
            self.quote = TencentQuote()
        except Exception as e:
            print(f"[大跌大涨] 行情接口初始化失败(跳过): {e}")
        # 初始化 DB
        try:
            init_crash_rally_db()
            seed_events_if_empty()
        except Exception as e:
            print(f"[大跌大涨] DB 初始化失败(跳过): {e}")
        # 预警监控线程控制
        self._monitor_running = False
        self._monitor_thread = None
        # 构建 GUI
        self._build_gui()

    # ---------- GUI 构建 ----------
    def _build_gui(self):
        self.root.title("🗓️ 大跌大涨日历记录与预警系统")
        self.root.configure(bg=COLOR_BG)
        try:
            self.root.geometry("1280x780")
        except Exception:
            pass
        # 顶部标题栏
        top = tk.Frame(self.root, bg=COLOR_BG, height=40)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Label(top, text="🗓️ 大跌大涨日历", font=FONT_TITLE,
                 bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)
        tk.Label(top, text="记录历史暴跌暴涨·提炼提前信号·盘中实时预警",
                 font=FONT_SMALL, bg=COLOR_BG, fg="#9E9E9E").pack(side=tk.LEFT, padx=12)
        tk.Button(top, text="❓帮助", command=self._show_help,
                  font=FONT_SMALL).pack(side=tk.RIGHT)
        # Notebook
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        # 4 个 Tab
        try:
            self.tab_a = ttk.Frame(self.nb)
            self.nb.add(self.tab_a, text="📝 历史事件记录")
            self._build_tab_a(self.tab_a)
        except Exception as e:
            print(f"[大跌大涨] Tab A 构建失败(跳过): {e}")
        try:
            self.tab_b = ttk.Frame(self.nb)
            self.nb.add(self.tab_b, text="📅 事件日历视图")
            self._build_tab_b(self.tab_b)
        except Exception as e:
            print(f"[大跌大涨] Tab B 构建失败(跳过): {e}")
        try:
            self.tab_c = ttk.Frame(self.nb)
            self.nb.add(self.tab_c, text="🔍 信号回测")
            self._build_tab_c(self.tab_c)
        except Exception as e:
            print(f"[大跌大涨] Tab C 构建失败(跳过): {e}")
        try:
            self.tab_d = ttk.Frame(self.nb)
            self.nb.add(self.tab_d, text="🚨 盘中预警")
            self._build_tab_d(self.tab_d)
        except Exception as e:
            print(f"[大跌大涨] Tab D 构建失败(跳过): {e}")
        try:
            self.tab_e = ttk.Frame(self.nb)
            self.nb.add(self.tab_e, text="🔮 涨跌预测")
            self._build_tab_e(self.tab_e)
        except Exception as e:
            print(f"[大跌大涨] Tab E 构建失败(跳过): {e}")

    # ---------- Tab A: 历史事件记录 ----------
    def _build_tab_a(self, parent):
        # 左侧: 事件列表 + 右侧: 编辑区
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        # 左: 列表
        left = ttk.Frame(paned)
        paned.add(left, weight=2)
        tk.Label(left, text="📜 已记录事件", font=FONT_TITLE).pack(anchor="w")
        # 工具栏
        tb = tk.Frame(left, bg=COLOR_BG)
        tb.pack(fill=tk.X, pady=2)
        tk.Button(tb, text="🔄刷新", command=self._reload_list_a, font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Button(tb, text="➕新增", command=self._new_event_a, font=FONT_SMALL).pack(side=tk.LEFT, padx=4)
        tk.Button(tb, text="🗑️删除", command=self._del_event_a, font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Button(tb, text="📥导入CSV", command=self._import_csv_a, font=FONT_SMALL).pack(side=tk.LEFT, padx=4)
        tk.Button(tb, text="📤导出", command=self._export_csv_a, font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Button(tb, text="🔍自动扫描历史", command=self._start_auto_scan_a, font=FONT_SMALL,
                  bg="#1565C0", fg="white").pack(side=tk.LEFT, padx=8)
        # 列表 Treeview
        cols = ("date", "type", "index", "pct", "magnitude", "trigger")
        self.list_a = ttk.Treeview(left, columns=cols, show="headings", height=20)
        for c, t, w in [("date", "日期", 90), ("type", "类型", 60), ("index", "指数", 70),
                        ("pct", "涨跌幅%", 70), ("magnitude", "幅度", 60), ("trigger", "触发", 90)]:
            self.list_a.heading(c, text=t)
            self.list_a.column(c, width=w, anchor="center")
        self.list_a.pack(fill=tk.BOTH, expand=True, pady=4)
        self.list_a.bind("<<TreeviewSelect>>", self._on_select_a)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.list_a.yview)
        self.list_a.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill="y")
        # 右: 编辑表单
        right = ttk.Frame(paned)
        paned.add(right, weight=3)
        tk.Label(right, text="✏️ 事件详情", font=FONT_TITLE).pack(anchor="w")
        form = ttk.Frame(right)
        form.pack(fill=tk.X, pady=6)
        # 变量
        self.v_date = tk.StringVar()
        self.v_type = tk.StringVar(value="crash")
        self.v_index = tk.StringVar(value="上证")
        self.v_pct = tk.DoubleVar()
        self.v_magnitude = tk.StringVar(value="刹跌")
        self.v_trigger = tk.StringVar()
        self.v_detail = tk.StringVar()
        self.v_signals = tk.StringVar()
        self.v_sigdays = tk.StringVar()
        self.v_recover = tk.IntVar(value=-1)
        self.v_maxrecover = tk.DoubleVar()
        self.v_notes = tk.StringVar()
        self.v_urls = tk.StringVar()
        self.v_stocks = tk.StringVar()  # 关联持仓股票
        self._cur_edit_id = None
        # 表单布局
        def _row(r, label, var, opts=None, width=30):
            tk.Label(form, text=label, font=FONT_SMALL).grid(row=r, column=0, sticky="e", padx=4, pady=3)
            if opts:
                cb = ttk.Combobox(form, textvariable=var, values=opts, width=width)
            else:
                cb = ttk.Entry(form, textvariable=var, width=width)
            cb.grid(row=r, column=1, sticky="w", padx=4, pady=3)
            return cb
        _row(0, "日期(YYYY-MM-DD):", self.v_date)
        _row(1, "类型:", self.v_type, ["crash", "rally"])
        _row(2, "指数:", self.v_index, self.INDEX_OPTS)
        _row(3, "涨跌幅(%):", self.v_pct)
        _row(4, "幅度:", self.v_magnitude, self.MAGNITUDE_OPTS)
        _row(5, "触发类型:", self.v_trigger, self.TRIGGER_CRASH + self.TRIGGER_RALLY)
        _row(6, "触发详情:", self.v_detail)
        # 信号改成下拉+多选提示 (用下拉列出 SIGNAL_NAMES)
        _row(7, "提前信号(逗号分隔):", self.v_signals, self.SIGNAL_NAMES)
        _row(8, "信号提前几天:", self.v_sigdays)
        _row(9, "收复天数(-1=未收复):", self.v_recover)
        _row(10, "最大反弹/续跌%:", self.v_maxrecover)
        _row(11, "备注:", self.v_notes)
        _row(12, "参考来源(|分隔):", self.v_urls)
        _row(13, "关联股票(代码,分隔):", self.v_stocks)
        # 自动拉取涨跌幅按钮
        tk.Button(form, text="🔍拉取当日涨跌幅", command=self._auto_fetch_pct,
                  font=FONT_SMALL).grid(row=14, column=0, columnspan=2, pady=4)
        # 保存按钮
        btn_row = tk.Frame(right, bg=COLOR_BG)
        btn_row.pack(fill=tk.X, pady=6)
        tk.Button(btn_row, text="💾保存", command=self._save_event_a,
                  font=FONT_TITLE, bg="#2E7D32", fg="white").pack(side=tk.LEFT)
        tk.Button(btn_row, text="🆕清空", command=self._clear_form_a,
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=8)
        # 初始加载
        self._reload_list_a()

    def _reload_list_a(self):
        try:
            for it in self.list_a.get_children():
                self.list_a.delete(it)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT id,event_date,event_type,index_name,index_pct,magnitude,trigger FROM crash_rally_events ORDER BY event_date DESC")
            for row in cur.fetchall():
                eid, dt, et, idx, pct, mag, trg = row
                type_str = "🟢暴跌" if et == "crash" else ("🔴暴涨" if et == "rally" else "—")
                self.list_a.insert("", "end", iid=str(eid),
                                   values=(dt, type_str, idx or "", f"{pct or 0:.2f}", mag or "", trg or ""))
            conn.close()
        except Exception as e:
            print(f"[大跌大涨] 列表加载失败(跳过): {e}")

    def _on_select_a(self, evt):
        try:
            sel = self.list_a.selection()
            if not sel: return
            eid = sel[0]
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT * FROM crash_rally_events WHERE id=?", (eid,))
            r = cur.fetchone()
            conn.close()
            if not r: return
            self._cur_edit_id = r[0]
            self.v_date.set(r[1] or "")
            self.v_type.set(r[2] or "crash")
            self.v_index.set(r[3] or "上证")
            self.v_pct.set(r[4] or 0.0)
            self.v_magnitude.set(r[5] or "刹跌")
            self.v_trigger.set(r[6] or "")
            self.v_detail.set(r[7] or "")
            self.v_signals.set(r[8] or "")
            self.v_sigdays.set(r[9] or "")
            self.v_recover.set(r[10] if r[10] is not None else -1)
            self.v_maxrecover.set(r[11] or 0.0)
            self.v_notes.set(r[12] or "")
            self.v_urls.set(r[13] or "")
            # related_stocks 在第15列 (索引14, 因为 created_at 在 15)
            try:
                self.v_stocks.set(r[14] or "")
            except Exception:
                self.v_stocks.set("")
        except Exception as e:
            print(f"[大跌大涨] 选中事件失败(跳过): {e}")

    def _save_event_a(self):
        try:
            dt = self.v_date.get().strip()
            if not dt:
                messagebox.showwarning("提示", "请填写日期")
                return
            et = self.v_type.get().strip() or "crash"
            data = (dt, et, self.v_index.get().strip(), float(self.v_pct.get() or 0),
                    self.v_magnitude.get().strip(), self.v_trigger.get().strip(),
                    self.v_detail.get().strip(), self.v_signals.get().strip(),
                    self.v_sigdays.get().strip(), int(self.v_recover.get() or -1),
                    float(self.v_maxrecover.get() or 0), self.v_notes.get().strip(),
                    self.v_urls.get().strip(), self.v_stocks.get().strip())
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            if self._cur_edit_id:
                cur.execute('''
                    UPDATE crash_rally_events SET event_date=?,event_type=?,index_name=?,index_pct=?,
                    magnitude=?,trigger=?,trigger_detail=?,leading_signals=?,signal_days_before=?,
                    recovery_days=?,max_recover_pct=?,notes=?,source_urls=?,related_stocks=? WHERE id=?
                ''', data + (self._cur_edit_id,))
            else:
                cur.execute('''
                    INSERT OR REPLACE INTO crash_rally_events
                    (event_date,event_type,index_name,index_pct,magnitude,trigger,
                     trigger_detail,leading_signals,signal_days_before,recovery_days,
                     max_recover_pct,notes,source_urls,related_stocks)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', data)
            conn.commit()
            conn.close()
            messagebox.showinfo("成功", "事件已保存")
            self._reload_list_a()
            self._clear_form_a()
            try:
                self._render_calendar_b()
            except Exception:
                pass
        except Exception as e:
            print(f"[大跌大涨] 保存事件失败(跳过): {e}")
            messagebox.showerror("错误", f"保存失败: {e}")

    def _clear_form_a(self):
        self._cur_edit_id = None
        for v in [self.v_date, self.v_trigger, self.v_detail, self.v_signals,
                  self.v_sigdays, self.v_notes, self.v_urls, self.v_stocks]:
            v.set("")
        self.v_type.set("crash")
        self.v_index.set("上证")
        self.v_pct.set(0.0)
        self.v_magnitude.set("刹跌")
        self.v_recover.set(-1)
        self.v_maxrecover.set(0.0)

    def _new_event_a(self):
        self._clear_form_a()
        self.v_date.set(_dt2.now().strftime("%Y-%m-%d"))

    def _del_event_a(self):
        try:
            sel = self.list_a.selection()
            if not sel:
                messagebox.showwarning("提示", "请先选中事件")
                return
            eid = sel[0]
            if not messagebox.askyesno("确认", "确认删除该事件?"):
                return
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM crash_rally_events WHERE id=?", (eid,))
            conn.commit()
            conn.close()
            self._reload_list_a()
            self._clear_form_a()
            try:
                self._render_calendar_b()
            except Exception:
                pass
        except Exception as e:
            print(f"[大跌大涨] 删除失败(跳过): {e}")

    # ---------- 自动扫描历史 (完整版: K线+规则+新闻) ----------
    def _start_auto_scan_a(self):
        """在后台线程启动 HistoryScanner, 扫描完成后弹窗预览"""
        if getattr(self, "_scan_thread_running", False):
            messagebox.showinfo("提示", "扫描正在进行中, 请稍候")
            return
        # 创建进度弹窗 (非模态)
        self._scan_win = tk.Toplevel(self.root)
        self._scan_win.title("🔍 历史暴涨暴跌自动扫描")
        self._scan_win.geometry("680x420")
        self._scan_win.configure(bg=COLOR_BG)
        self._scan_win.grab_set()
        tk.Label(self._scan_win, text="🔍 扫描进行中...", font=FONT_TITLE,
                 bg=COLOR_BG, fg="#FFD700").pack(pady=6)
        self._scan_txt = tk.Text(self._scan_win, font=FONT_SMALL, wrap=tk.NONE,
                                 bg="#0D0D1F", fg=COLOR_FG, height=18)
        self._scan_txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._scan_txt.insert("1.0", "⏳ 初始化扫描器...\n")
        self._scan_txt.configure(state="disabled")

        def _progress(msg):
            """子线程里要 root.after 才能安全更新 UI"""
            try:
                self.root.after(0, lambda: self._append_scan_log(msg))
            except Exception:
                pass

        def _worker():
            self._scan_thread_running = True
            try:
                scanner = HistoryScanner(progress_cb=_progress)
                events = scanner.scan_all_indices()
                _progress(f"\n🔍 共筛出 {len(events)} 日异动 (阈值 |pct|>2%)")
                # 新闻增强 (仅对近30天内未命中规则的事件)
                events = scanner.enrich_with_news(events, days_window=60)
                # 去重: 同日期同指数只保留最极端的
                seen = {}
                for ev in events:
                    key = (ev["event_date"], ev["index_name"])
                    if key not in seen or abs(ev["index_pct"]) > abs(seen[key]["index_pct"]):
                        seen[key] = ev
                events = sorted(seen.values(), key=lambda x: -abs(x["index_pct"]))
                _progress(f"\n✅ 去重后剩 {len(events)} 条候选事件")
                self.root.after(0, lambda: self._scan_finished(events))
            except Exception as e:
                _progress(f"\n❌ 扫描失败: {type(e).__name__}: {e}")
                traceback.print_exc()
                self.root.after(0, lambda: self._scan_finished([]))
            finally:
                self._scan_thread_running = False

        threading.Thread(target=_worker, daemon=True).start()

    def _append_scan_log(self, msg):
        try:
            self._scan_txt.configure(state="normal")
            self._scan_txt.insert(tk.END, msg + "\n")
            self._scan_txt.see(tk.END)
            self._scan_txt.configure(state="disabled")
        except Exception:
            pass

    def _scan_finished(self, events):
        """扫描完成, 弹出预览窗口让用户确认再入库"""
        try:
            self._scan_win.destroy()
        except Exception:
            pass
        if not events:
            messagebox.showwarning("扫描完成", "未筛出任何异动事件 (可能 K线接口不可用)")
            return
        # 预览窗口
        prev = tk.Toplevel(self.root)
        prev.title(f"📋 扫描结果预览 (共 {len(events)} 条)")
        prev.geometry("1100x620")
        prev.configure(bg=COLOR_BG)
        prev.grab_set()
        tk.Label(prev, text=f"📋 扫描得到 {len(events)} 条候选暴涨暴跌事件, 勾选要入库的 (按涨跌幅绝对值排序)",
                 font=FONT_TITLE, bg=COLOR_BG, fg="#FFD700").pack(pady=6)

        # 筛选控制
        filter_bar = tk.Frame(prev, bg=COLOR_BG)
        filter_bar.pack(fill=tk.X, padx=6, pady=4)
        self._scan_thr = tk.StringVar(value="3.0")
        self._scan_only_todo = tk.BooleanVar(value=False)
        self._scan_crash = tk.BooleanVar(value=True)
        self._scan_rally = tk.BooleanVar(value=True)
        tk.Label(filter_bar, text="跌幅阈值|pct|≥:", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)
        tk.Entry(filter_bar, textvariable=self._scan_thr, width=6, font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Checkbutton(filter_bar, text="仅看trigger含(待补)", variable=self._scan_only_todo,
                       bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_BG,
                       activebackground=COLOR_BG).pack(side=tk.LEFT, padx=8)
        tk.Checkbutton(filter_bar, text="暴跌", variable=self._scan_crash,
                       bg=COLOR_BG, fg="#C62828", selectcolor=COLOR_BG,
                       activebackground=COLOR_BG).pack(side=tk.LEFT)
        tk.Checkbutton(filter_bar, text="暴涨", variable=self._scan_rally,
                       bg=COLOR_BG, fg="#2E7D32", selectcolor=COLOR_BG,
                       activebackground=COLOR_BG).pack(side=tk.LEFT)
        tk.Button(filter_bar, text="🔄应用筛选", command=lambda: self._refresh_scan_preview(events_tree, events),
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=8)
        tk.Button(filter_bar, text="✅全选", command=lambda: self._checkall_tree(events_tree, True),
                  font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Button(filter_bar, text="❌全不选", command=lambda: self._checkall_tree(events_tree, False),
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=4)

        # Treeview (带 checkbox)
        cols = ("sel", "date", "type", "index", "pct", "magnitude", "trigger", "trigger_detail")
        events_tree = ttk.Treeview(prev, columns=cols, show="headings", height=22)
        for c, t, w, anc in [
            ("sel", "✓", 30, "center"),
            ("date", "日期", 90, "center"),
            ("type", "类型", 60, "center"),
            ("index", "指数", 70, "center"),
            ("pct", "涨跌幅%", 80, "center"),
            ("magnitude", "幅度", 70, "center"),
            ("trigger", "触发原因", 120, "w"),
            ("trigger_detail", "详情(前50字)", 340, "w"),
        ]:
            events_tree.heading(c, text=t)
            events_tree.column(c, width=w, anchor=anc)
        events_tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        # 存储全量事件到 Treeview 的 tags 上
        events_tree._all_events = events
        self._refresh_scan_preview(events_tree, events)

        # 底部按钮
        btn_bar = tk.Frame(prev, bg=COLOR_BG)
        btn_bar.pack(fill=tk.X, padx=6, pady=6)
        tk.Button(btn_bar, text="💾 入库选中行",
                  command=lambda: self._batch_insert_events(events_tree, prev),
                  font=FONT_TITLE, bg="#2E7D32", fg="white", width=16).pack(side=tk.RIGHT)
        tk.Button(btn_bar, text="📊 显示统计",
                  command=lambda: self._show_scan_stats(events_tree),
                  font=FONT_SMALL).pack(side=tk.RIGHT, padx=8)

        # 点击第一列切换选中
        def _toggle_sel(evt):
            try:
                region = events_tree.identify("region", evt.x, evt.y)
                if region != "cell": return
                col = events_tree.identify_column(evt.x)
                if col != "#1": return  # 只响应第一列
                row = events_tree.identify_row(evt.y)
                if row:
                    cur = events_tree.set(row, "sel")
                    events_tree.set(row, "sel", "" if cur == "✓" else "✓")
                    tag = events_tree.item(row, "tags")[0]
                    if cur == "✓":
                        events_tree.item(row, tags=(tag, "unsel"))
                    else:
                        events_tree.item(row, tags=(tag, "sel"))
            except Exception:
                pass
        events_tree.bind("<Button-1>", _toggle_sel)
        # 颜色 tag
        events_tree.tag_configure("crash", background="#0A2A0A", foreground="#C8E6C9")  # 绿
        events_tree.tag_configure("rally", background="#2A0A0A", foreground="#FFCDD2")  # 红

    def _refresh_scan_preview(self, tree, events):
        """按筛选条件刷新预览, Treeview row 直接关联 filtered events 列表"""
        try:
            tree._filtered_events = []
            for it in tree.get_children():
                tree.delete(it)
            thr = abs(float(self._scan_thr.get() or 3.0))
            show_todo_only = self._scan_only_todo.get()
            show_crash = self._scan_crash.get()
            show_rally = self._scan_rally.get()
            for ev in events:
                if abs(ev["index_pct"]) < thr:
                    continue
                if ev["event_type"] == "crash" and not show_crash:
                    continue
                if ev["event_type"] == "rally" and not show_rally:
                    continue
                if show_todo_only and "待补" not in ev.get("trigger", "") and ev.get("trigger"):
                    continue
                ev_type = "🟢暴跌" if ev["event_type"] == "crash" else "🔴暴涨"
                detail = ev.get("trigger_detail", "")[:50]
                row_tag = "crash" if ev["event_type"] == "crash" else "rally"
                row_idx = len(tree._filtered_events)
                tree.insert("", "end", iid=str(row_idx), values=(
                    "✓",  # 默认全选
                    ev["event_date"], ev_type, ev["index_name"],
                    f"{ev['index_pct']:+.2f}", ev.get("magnitude", ""),
                    ev.get("trigger", "")[:20], detail
                ), tags=(row_tag, "sel"))
                tree._filtered_events.append(ev)
        except Exception as e:
            print(f"[大跌大涨] 预览刷新失败(跳过): {e}")

    def _checkall_tree(self, tree, checked):
        try:
            v = "✓" if checked else ""
            for row in tree.get_children():
                tree.set(row, "sel", v)
                tag = tree.item(row, "tags")[0]
                if checked:
                    tree.item(row, tags=(tag, "sel"))
                else:
                    tree.item(row, tags=(tag, "unsel"))
        except Exception:
            pass

    def _show_scan_stats(self, tree):
        """显示扫描结果统计"""
        try:
            all_events = getattr(tree, "_all_events", [])
            if not all_events:
                return
            total = len(all_events)
            crashes = [e for e in all_events if e["event_type"] == "crash"]
            rallies = [e for e in all_events if e["event_type"] == "rally"]
            trigger_counter = {}
            for e in all_events:
                t = e.get("trigger", "") or "未归因"
                trigger_counter[t] = trigger_counter.get(t, 0) + 1
            todo_count = sum(1 for e in all_events if "待补" in (e.get("trigger") or ""))
            lines = [f"📊 扫描结果统计 (共 {total} 条)", "="*40,
                     f"  🔴 暴跌: {len(crashes)} 次, 平均跌幅 {sum(e['index_pct'] for e in crashes)/len(crashes) if crashes else 0:.2f}%",
                     f"  🟢 暴涨: {len(rallies)} 次, 平均涨幅 {sum(e['index_pct'] for e in rallies)/len(rallies) if rallies else 0:.2f}%",
                     f"  📝 规则归因已覆盖: {total - todo_count} 条",
                     f"  ❓ 含'(待补)': {todo_count} 条 (可手动补)",
                     f"\n📌 Trigger 分布 Top10:"]
            for t, n in sorted(trigger_counter.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"  {t}: {n}")
            # 指数分布
            idx_counter = {}
            for e in all_events:
                idx_counter[e["index_name"]] = idx_counter.get(e["index_name"], 0) + 1
            lines.append("\n📌 指数分布:")
            for n, cnt in sorted(idx_counter.items(), key=lambda x: -x[1]):
                lines.append(f"  {n}: {cnt}")
            messagebox.showinfo("扫描统计", "\n".join(lines))
        except Exception as e:
            print(f"[大跌大涨] 统计失败(跳过): {e}")

    def _batch_insert_events(self, tree, parent_win):
        """把预览中勾选中的事件批量写入 DB (使用 _filtered_events 直接关联, 避免错配)"""
        try:
            filtered = getattr(tree, "_filtered_events", [])
            sel_rows = tree.get_children()
            selected_events = []
            for row_id in sel_rows:
                if tree.set(row_id, "sel") != "✓":
                    continue
                try:
                    idx = int(row_id)
                    if 0 <= idx < len(filtered):
                        selected_events.append(filtered[idx])
                except Exception:
                    continue
            if not selected_events:
                messagebox.showwarning("提示", "没有勾选任何行")
                return
            # 先统计将要跳过的已存在条数, 给用户明确提示
            conn0 = sqlite3.connect(DB_PATH)
            cur0 = conn0.cursor()
            n_existing = 0
            for ev in selected_events:
                cur0.execute('SELECT id FROM crash_rally_events WHERE event_date=? AND index_name=?',
                             (ev["event_date"], ev["index_name"]))
                if cur0.fetchone():
                    n_existing += 1
            conn0.close()
            n_new = len(selected_events) - n_existing
            confirmed = messagebox.askyesno(
                "确认入库",
                f"将批量入库 {len(selected_events)} 条事件:\n"
                f"  🆕 新增: {n_new} 条 (trigger={'auto_scan/auto_scan_news'})\n"
                f"  ⏭️ 已存在: {n_existing} 条 (将跳过)\n\n"
                f"✅ 规则覆盖: {sum(1 for e in selected_events if '(待补)' not in (e.get('trigger') or ''))}\n"
                f"❓ 含(待补): {sum(1 for e in selected_events if '(待补)' in (e.get('trigger') or ''))}\n\n"
                f"继续入库?",
            )
            if not confirmed:
                return
            n_inserted = 0
            n_skipped = 0
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            for ev in selected_events:
                cur.execute('SELECT id FROM crash_rally_events WHERE event_date=? AND index_name=?',
                            (ev["event_date"], ev["index_name"]))
                if cur.fetchone():
                    n_skipped += 1
                    continue
                cur.execute('''
                    INSERT INTO crash_rally_events
                    (event_date,event_type,index_name,index_pct,magnitude,trigger,trigger_detail,
                     leading_signals,signal_days_before,recovery_days,max_recover_pct,notes,source_urls)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    ev["event_date"], ev["event_type"], ev["index_name"],
                    ev["index_pct"], ev.get("magnitude", ""), ev.get("trigger", ""),
                    ev.get("trigger_detail", ""), "", "", -1, 0, "",
                    ev.get("source_urls", "auto_scan"),
                ))
                n_inserted += 1
            conn.commit()
            conn.close()
            messagebox.showinfo("入库完成",
                                f"✅ 新增 {n_inserted} 条\n"
                                f"⏭️ 跳过已存在 {n_skipped} 条\n"
                                f"📌 总计 {len(selected_events)} 条已处理")
            parent_win.destroy()
            self._reload_list_a()
            try:
                self._render_calendar_b()
            except Exception:
                pass
        except Exception as e:
            print(f"[大跌大涨] 批量入库失败(跳过): {e}")
            traceback.print_exc()
            messagebox.showerror("错误", f"入库失败: {e}")

    def _auto_fetch_pct(self):
        """根据日期+指数, 自动拉取当日涨跌幅"""
        try:
            dt = self.v_date.get().strip()
            idx = self.v_index.get().strip()
            if not dt or not idx:
                messagebox.showwarning("提示", "请先填日期和指数")
                return
            # 指数代码
            code_map = {"上证": "sh000001", "深证": "sz399001", "创业板": "sz399006", "科创50": "sh000688"}
            code = code_map.get(idx, "sh000001")
            if not self.quote:
                messagebox.showerror("错误", "行情接口未初始化")
                return
            kls = self.quote.get_kline(code, count=120)
            for k in kls:
                if k["date"].startswith(dt[:10]):
                    prev_close = 0
                    # 找前一天
                    for i, k2 in enumerate(kls):
                        if k2["date"].startswith(dt[:10]) and i > 0:
                            prev_close = kls[i-1]["close"]
                            break
                    if prev_close > 0:
                        pct = round((k["close"] - prev_close) / prev_close * 100, 2)
                    else:
                        pct = 0
                    self.v_pct.set(pct)
                    # 自动判定幅度
                    if pct < -5: mag = "崩盘"
                    elif pct < -3: mag = "大跌"
                    elif pct < 0: mag = "刹跌"
                    elif pct < 3: mag = "小涨"
                    elif pct < 8: mag = "大涨"
                    else: mag = "暴涨"
                    self.v_magnitude.set(mag)
                    self.v_type.set("crash" if pct < 0 else "rally")
                    messagebox.showinfo("成功", f"拉到 {dt} {idx} 涨跌幅={pct}%")
                    return
            messagebox.showwarning("未找到", f"K线中未找到 {dt}")
        except Exception as e:
            print(f"[大跌大涨] 自动拉取涨跌幅失败(跳过): {e}")
            messagebox.showerror("错误", f"拉取失败: {e}")

    def _import_csv_a(self):
        try:
            fp = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("All", "*.*")])
            if not fp: return
            import csv
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            n = 0
            with open(fp, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) < 6: continue
                    dt, et, idx, pct, mag, trg = row[0], row[1], row[2], float(row[3] or 0), row[4], row[5]
                    detail = row[6] if len(row) > 6 else ""
                    sig = row[7] if len(row) > 7 else ""
                    cur.execute('''
                        INSERT OR REPLACE INTO crash_rally_events
                        (event_date,event_type,index_name,index_pct,magnitude,trigger,trigger_detail,leading_signals)
                        VALUES (?,?,?,?,?,?,?,?)
                    ''', (dt, et, idx, pct, mag, trg, detail, sig))
                    n += 1
            conn.commit()
            conn.close()
            messagebox.showinfo("成功", f"导入 {n} 条")
            self._reload_list_a()
            self._render_calendar_b()
        except Exception as e:
            print(f"[大跌大涨] CSV导入失败(跳过): {e}")

    def _export_csv_a(self):
        try:
            fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not fp: return
            import csv
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT event_date,event_type,index_name,index_pct,magnitude,trigger,trigger_detail,leading_signals,signal_days_before,recovery_days,max_recover_pct,notes,source_urls FROM crash_rally_events ORDER BY event_date DESC")
            rows = cur.fetchall()
            conn.close()
            with open(fp, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["日期", "类型", "指数", "涨跌幅", "幅度", "触发", "详情", "信号", "信号提前几天", "收复天数", "最大反弹", "备注", "来源"])
                for r in rows:
                    w.writerow(r)
            messagebox.showinfo("成功", f"已导出 {len(rows)} 条到\n{fp}")
        except Exception as e:
            print(f"[大跌大涨] CSV导出失败(跳过): {e}")

    # ---------- Tab B: 事件日历视图 ----------
    def _build_tab_b(self, parent):
        # 顶部: 月份切换 + 统计
        top = tk.Frame(parent, bg=COLOR_BG)
        top.pack(fill=tk.X, padx=6, pady=4)
        tk.Button(top, text="◀上月", command=lambda: self._shift_month_b(-1), font=FONT_SMALL).pack(side=tk.LEFT)
        self.lbl_month_b = tk.Label(top, text="", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG, width=12)
        self.lbl_month_b.pack(side=tk.LEFT, padx=12)
        tk.Button(top, text="下月▶", command=lambda: self._shift_month_b(1), font=FONT_SMALL).pack(side=tk.LEFT)
        tk.Button(top, text="📍今天", command=self._jump_today_b, font=FONT_SMALL).pack(side=tk.LEFT, padx=8)
        tk.Button(top, text="📄导出月报MD", command=self._export_month_md_b, font=FONT_SMALL).pack(side=tk.LEFT, padx=8)
        tk.Button(top, text="📄导出年报MD", command=self._export_year_md_b, font=FONT_SMALL).pack(side=tk.LEFT)
        self.lbl_stats_b = tk.Label(top, text="", font=FONT_SMALL, bg=COLOR_BG, fg="#9E9E9E")
        self.lbl_stats_b.pack(side=tk.RIGHT)
        # 日历网格
        self.cal_frame_b = tk.Frame(parent, bg=COLOR_BG)
        self.cal_frame_b.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        # 详情面板 (高度 14 = 约2.3倍 原 6)
        self.detail_b = tk.Text(parent, height=14, font=FONT_MAIN, wrap=tk.WORD, bg="#0D0D1F", fg=COLOR_FG)
        self.detail_b.pack(fill=tk.X, padx=6, pady=4)
        self._view_month_b = _dt2.now().replace(day=1)
        self._render_calendar_b()

    def _shift_month_b(self, delta):
        try:
            ym = self._view_month_b
            new_m = ym.month + delta
            new_y = ym.year
            while new_m < 1: new_m += 12; new_y -= 1
            while new_m > 12: new_m -= 12; new_y += 1
            self._view_month_b = _dt2(new_y, new_m, 1)
            self._render_calendar_b()
        except Exception as e:
            print(f"[大跌大涨] 月份切换失败(跳过): {e}")

    def _jump_today_b(self):
        self._view_month_b = _dt2.now().replace(day=1)
        self._render_calendar_b()

    def _render_calendar_b(self):
        try:
            for w in self.cal_frame_b.winfo_children():
                w.destroy()
            ym = self._view_month_b
            self.lbl_month_b.config(text=f"{ym.year}年{ym.month}月")
            # 表头 (加一列情绪)
            for i, d in enumerate(["日", "一", "二", "三", "四", "五", "六"]):
                tk.Label(self.cal_frame_b, text=d, font=FONT_SMALL, bg=COLOR_BG, fg="#9E9E9E",
                         width=18, height=1).grid(row=0, column=i, padx=2, pady=2)
            # 查询当月事件 (一个日期可能多条, 按日期分组)
            month_str = f"{ym.year:04d}-{ym.month:02d}"
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""
                SELECT event_date,event_type,index_name,index_pct,magnitude,
                       trigger,trigger_detail,leading_signals,notes
                FROM crash_rally_events
                WHERE event_date LIKE ?
                ORDER BY event_date, ABS(index_pct) DESC
            """, (month_str + "%",))
            events_by_day = {}
            n_crash = n_rally = 0
            for r in cur.fetchall():
                day = int(r[0][8:10]) if len(r[0]) >= 10 else 0
                if not day: continue
                events_by_day.setdefault(day, []).append(r)
                if r[1] == "crash": n_crash += 1
                elif r[1] == "rally": n_rally += 1
            conn.close()

            # 加载情绪周期 JSON, 找出当月缺失日期
            emo_data = load_emo_history()
            missing_dates = []
            cal = _dt2(ym.year, ym.month, 1)
            days_in_month = (cal.replace(month=ym.month % 12 + 1, day=1) - _dt.timedelta(days=1)).day if ym.month != 12 else 31
            today = _dt2.now().date()
            # 先查哪些天缺失 → 后台补全, 渲染时已有数据的先显示
            for d in range(1, days_in_month + 1):
                date_str = f"{ym.year:04d}-{ym.month:02d}-{d:02d}"
                # 未来日期/或 akshare 还没出数据的跳过补全
                try:
                    d_obj = _dt2(ym.year, ym.month, d).date()
                    if d_obj > today:
                        continue  # 未来天不可能有数据
                except Exception:
                    pass
                if date_str not in emo_data:
                    missing_dates.append(date_str)
            # 如果有缺失日期 → 后台线程补全 (不阻塞渲染)
            if missing_dates and not getattr(self, "_emo_fill_running", False):
                self._emo_fill_running = True
                threading.Thread(target=self._emo_fill_worker,
                                 args=(missing_dates,), daemon=True).start()

            # 渲染日期格子
            start_wd = cal.weekday() + 1  # 周日=0
            if start_wd == 7: start_wd = 0
            for d in range(1, days_in_month + 1):
                r = (d + start_wd - 1) // 7 + 1
                c = (d + start_wd - 1) % 7
                day_events = events_by_day.get(d, [])
                date_str = f"{ym.year:04d}-{ym.month:02d}-{d:02d}"
                emo = emo_data.get(date_str, {})
                bg = COLOR_BG
                lines = [str(d)]

                # ---- 情绪周期行 (最顶部) ----
                if emo:
                    stage = emo.get("stage", "?")
                    score = emo.get("emo_score", 0)
                    emoji, emo_fg = EMO_STAGE_EMOJI.get(stage, ("❓", "#9E9E9E"))
                    emo_text = f"{emoji}{stage}{score:.0f}"
                else:
                    emo_text = "⏳待补"
                    emo_fg = "#616161"
                lines.append(emo_text)

                # ---- 事件行 ----
                if day_events:
                    worst = max(day_events, key=lambda e: abs(e[3] or 0))
                    et = worst[1]
                    pct = worst[3] or 0
                    if et == "crash":
                        bg = "#1A3A1A" if pct > -3 else "#0A2A0A"  # 绿 (A股: 跌绿)
                    elif et == "rally":
                        bg = "#4A1A1A" if pct < 3 else "#2A0A0A"  # 红 (A股: 涨红)
                    shown = day_events[:2]
                    for ev in shown:
                        icon = "🟢" if ev[1] == "crash" else "🔴"  # A股: 跌绿涨红
                        idx_short = (ev[2] or "")[:2]
                        lines.append(f"{icon}{idx_short}{ev[3]:+.1f}%")
                    if len(day_events) > 2:
                        lines.append(f"...+{len(day_events)-2}")
                elif _dt2(ym.year, ym.month, d).date() == today:
                    bg = "#1A237E"

                txt = "\n".join(lines)
                height = 2 + min(2, len(day_events))  # 动态高度
                cell = tk.Label(self.cal_frame_b, text=txt, font=FONT_SMALL, bg=bg, fg=COLOR_FG,
                                width=18, height=max(3, height), justify=tk.LEFT, anchor="nw")
                # 情绪行文字单独着色 (用 Canvas 更好, 简化起见只用 Emoji)
                cell.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                # 点击: 同时传事件列表 + 情绪数据
                click_data = {"events": day_events, "emo": emo}
                cell.bind("<Button-1>", lambda e, data=click_data: self._show_detail_b(data))
                # hover: 触发原因 + 情绪阶段
                try:
                    root = self.root
                    tooltip_parts = []
                    if day_events:
                        first_trig = day_events[0][5] or ""
                        if first_trig and "(待补)" not in first_trig:
                            tooltip_parts.append(first_trig)
                    if emo:
                        s = emo.get("stage", "")
                        sc = emo.get("emo_score", "")
                        if s: tooltip_parts.append(f"情绪: {s}({sc})")
                    if tooltip_parts:
                        cell.bind("<Enter>", lambda e, t=" | ".join(tooltip_parts): self._show_hover_tip(root, t))
                        cell.bind("<Leave>", lambda e: self._hide_hover_tip())
                except Exception:
                    pass

            # 顶部统计
            self.lbl_stats_b.config(text=f"🟢暴跌{n_crash}次  🔴暴涨{n_rally}次  |  📅共 {days_in_month} 天")
            # 详情清空
            self.detail_b.delete("1.0", tk.END)
        except Exception as e:
            print(f"[大跌大涨] 日历渲染失败(跳过): {e}")
            traceback.print_exc()

    def _emo_fill_worker(self, missing_dates):
        """后台线程补全缺失的情绪数据"""
        try:
            self.root.after(0, lambda: self._append_emo_log(f"🔄 后台补全 {len(missing_dates)} 个日期情绪数据..."))
            existing = load_emo_history()
            filled_count = 0
            for ds in missing_dates:
                # 只补当天 (akshare 实时接口只有当天数据)
                try:
                    target_dt = _dt2.fromisoformat(ds)
                    today_dt = _dt2.now().date()
                    if target_dt.date() != today_dt:
                        continue  # 不是今天的跳过 (历史日期没实时涨跌家数)
                except Exception:
                    continue
                if ds in existing:
                    continue
                emo = auto_fill_emo_for_date(ds, progress_cb=lambda m: self.root.after(0, lambda: self._append_emo_log(m)))
                if emo:
                    existing[ds] = emo
                    filled_count += 1
            if filled_count > 0:
                save_emo_history(existing)
                self.root.after(0, lambda: self._append_emo_log(f"✅ 补全 {filled_count} 条, 刷新日历..."))
                self.root.after(0, self._render_calendar_b)
            else:
                self.root.after(0, lambda: self._append_emo_log("⏭️ 无可用日期需要补全 (仅当天 akshare 有实时数据)"))
        except Exception as e:
            print(f"[情绪补全] 后台线程异常: {e}")
        finally:
            self._emo_fill_running = False

    def _append_emo_log(self, msg):
        """在详情区追加一行补全日志 (限长)"""
        try:
            self.detail_b.insert(tk.END, f"[自动补全] {msg}\n")
            self.detail_b.see(tk.END)
        except Exception:
            pass

    def _show_hover_tip(self, root, text):
        """显示悬浮提示 (trigger 简述)"""
        try:
            self._hover_tip.destroy()
        except Exception:
            pass
        x = root.winfo_pointerx() + 20
        y = root.winfo_pointery() + 20
        tip = tk.Toplevel(root)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tk.Label(tip, text=text, bg="#FFD700", fg="#000", font=FONT_SMALL,
                 padx=6, pady=2).pack()
        self._hover_tip = tip

    def _hide_hover_tip(self):
        try:
            self._hover_tip.destroy()
        except Exception:
            pass

    def _show_detail_b(self, click_data):
        """显示某一天的详情: 情绪周期 + 涨跌个数 + 领涨领跌板块(仅当天) + 暴涨暴跌事件"""
        try:
            self.detail_b.delete("1.0", tk.END)
            # 兼容两种格式: 老的 list[tuple] 和新的 dict
            if isinstance(click_data, dict):
                day_events = click_data.get("events", [])
                emo = click_data.get("emo", {})
            else:
                day_events = list(click_data) if isinstance(click_data, (list, tuple)) else [click_data]
                emo = {}
            day_date = day_events[0][0] if day_events else "?"
            # 存起来给后台线程回调用
            self._detail_last_date = day_date

            # ============ 情绪周期区块 ============
            if emo:
                stage = emo.get("stage", "?")
                score = emo.get("emo_score", 0)
                emoji, _ = EMO_STAGE_EMOJI.get(stage, ("❓", "#9E9E9E"))
                up_count = emo.get("up")
                dn_count = emo.get("dn")
                zt_count = emo.get("zt")
                dt_count = emo.get("dt")
                # 涨跌比例
                if up_count is not None and dn_count is not None:
                    total = up_count + dn_count
                    up_pct = up_count / total * 100 if total else 0
                    dn_pct = dn_count / total * 100 if total else 0
                    breadth = f"🔴 {up_count:>4d} ({up_pct:.0f}%)  🟢 {dn_count:>4d} ({dn_pct:.0f}%)  📊比 {up_pct:.0f}:{dn_pct:.0f}"
                else:
                    breadth = f"🔴 {up_count}  🟢 {dn_count}  (无比例)"
                emo_block = (
                    f"{'━'*52}\n"
                    f"💭 情绪周期  {emoji}{stage}  score={score:.0f}\n"
                    f"{'━'*52}\n"
                    f"  📈 上证涨跌:   {emo.get('pct', 0):+.2f}%  (同花顺方向: {emo.get('ths','?')})\n"
                    f"  💰 盈亏体感:   {emo.get('pnl','?')}\n"
                    f"  📊 涨跌家数:   {breadth}\n"
                    f"  🔥 涨停: {zt_count}  ❄️ 跌停: {dt_count}  📂 来源: {emo.get('source','手动')}\n\n"
                )
            else:
                emo_block = (
                    f"{'━'*52}\n"
                    f"💭 情绪周期  ⚠️ 无数据 (JSON 中缺失, 下次渲染自动补全)\n"
                    f"{'━'*52}\n\n"
                )

            # ============ 领涨领跌板块区块 (仅当天实时拉取) ============
            sector_block = ""
            try:
                today_str = _dt2.now().strftime("%Y-%m-%d")
                if day_date[:10] == today_str:
                    sector_block = "\n⏳ 正在加载实时板块数据 (后台拉取同花顺)...\n"
                    # 后台线程异步拉
                    threading.Thread(target=self._fetch_sector_worker, args=(day_date,), daemon=True).start()
                else:
                    sector_block = (
                        f"\n📋 领涨领跌板块: 📅 历史日期({day_date[:10]})无法实时回溯板块数据\n"
                        f"                 (akshare 实时接口只返回当天数据)\n"
                    )
            except Exception:
                pass

            # ============ 暴涨暴跌事件区块 ============
            events_block = f"\n📅 {day_date}  共 {len(day_events)} 条暴涨暴跌事件\n{'='*52}\n"
            if not day_events:
                events_block += "  (无暴涨暴跌事件)\n"
            for i, r in enumerate(day_events, 1):
                et = r[1]
                icon = "🟢" if et == "crash" else "🔴"  # A股: 跌绿涨红
                idx = r[2] or ""
                pct = r[3] or 0
                mag = r[4] or ""
                trig = r[5] or "(未归因)"
                detail = r[6] or "(无详情)"
                notes = r[8] or ""
                events_block += (
                    f"\n{i}. {icon} {idx}  {pct:+.2f}%  [{mag}]\n"
                    f"   🎯 原因: {trig}\n"
                    f"   📝 详情: {detail}\n"
                )
                if notes:
                    events_block += f"   📌 备注: {notes}\n"

            # 组合输出
            self.detail_b.insert(tk.END, emo_block)
            self.detail_b.insert(tk.END, sector_block)
            self.detail_b.insert(tk.END, events_block)
        except Exception as e:
            print(f"[大跌大涨] 详情显示失败(跳过): {e}")
            traceback.print_exc()

    def _fetch_sector_worker(self, day_date):
        """后台线程拉同花顺行业板块实时数据, 完成后追加到详情面板"""
        import time as _time
        try:
            import akshare as ak
            self.root.after(0, lambda: self._append_detail_line(f"\n🔄 拉取同花顺行业板块..."))
            df = ak.stock_board_industry_summary_ths()
            if df is None or len(df) == 0:
                self.root.after(0, lambda: self._append_detail_line("⚠️ 同花顺板块接口返回空\n"))
                return
            # 排序
            top_rise = df.sort_values("涨跌幅", ascending=False).head(5)
            top_fall = df.sort_values("涨跌幅", ascending=True).head(5)

            lines = [f"\n{'━'*52}", f"📋 领涨领跌板块  (同花顺行业板块)", f"{'━'*52}"]
            lines.append("🟢 领涨 TOP5:")
            for _, r in top_rise.iterrows():
                sector = str(r.get("板块", ""))
                pct = float(r.get("涨跌幅", 0))
                lead = str(r.get("领涨股", ""))
                lead_pct = float(r.get("领涨股-涨跌幅", 0)) if r.get("领涨股-涨跌幅") is not None else 0
                lines.append(f"  🟢 {sector:10s} {pct:+.2f}%  领涨:{lead}({lead_pct:+.2f}%)")
            lines.append("🔴 领跌 TOP5:")
            for _, r in top_fall.iterrows():
                sector = str(r.get("板块", ""))
                pct = float(r.get("涨跌幅", 0))
                lead = str(r.get("领涨股", ""))
                lead_pct = float(r.get("领涨股-涨跌幅", 0)) if r.get("领涨股-涨跌幅") is not None else 0
                lines.append(f"  🔴 {sector:10s} {pct:+.2f}%  领跌:{lead}({lead_pct:+.2f}%)")
            lines.append(f"{'━'*52}\n")
            output = "\n".join(lines)
            # 检查用户没切换到别的日期 (详情被覆盖了)
            current_date = getattr(self, "_detail_last_date", "")
            if current_date != day_date:
                return  # 已经切到别的日期了, 不追加
            self.root.after(0, lambda: self._replace_sector_section(output))
        except Exception as e:
            self.root.after(0, lambda: self._append_detail_line(f"⚠️ 板块拉取失败: {type(e).__name__}: {e}\n"))

    def _replace_sector_section(self, new_text):
        """替换详情中占位的 sector 区域 (先删后插)"""
        try:
            content = self.detail_b.get("1.0", tk.END)
            # 找到占位并替换
            if "⏳ 正在加载实时板块数据" in content:
                # 按分隔线定位, 从 "⏳" 到下一个 \n\n 结束
                start = content.find("⏳ 正在加载实时板块数据")
                end = content.find("\n\n", start)
                if end == -1:
                    end = len(content)
                new_content = content[:start] + new_text + content[end:]
                self.detail_b.delete("1.0", tk.END)
                self.detail_b.insert("1.0", new_content)
                self.detail_b.see(tk.END)
        except Exception as e:
            print(f"[大跌大涨] 板块替换失败(跳过): {e}")

    def _append_detail_line(self, text):
        try:
            self.detail_b.insert(tk.END, text)
            self.detail_b.see(tk.END)
        except Exception:
            pass

    def _export_month_md_b(self):
        """导出当月事件 Markdown 报告"""
        try:
            ym = self._view_month_b
            month_str = f"{ym.year:04d}-{ym.month:02d}"
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT event_date,event_type,index_name,index_pct,magnitude,trigger,trigger_detail,leading_signals,notes FROM crash_rally_events WHERE event_date LIKE ? ORDER BY event_date", (month_str + "%",))
            rows = cur.fetchall()
            conn.close()
            if not rows:
                messagebox.showinfo("提示", f"{month_str} 无事件记录")
                return
            fp = filedialog.asksaveasfilename(defaultextension=".md",
                                              initialfile=f"crash_rally_{month_str}.md",
                                              filetypes=[("Markdown", "*.md")])
            if not fp: return
            n_crash = sum(1 for r in rows if r[1] == "crash")
            n_rally = sum(1 for r in rows if r[1] == "rally")
            avg_crash = sum(r[3] for r in rows if r[1] == "crash") / n_crash if n_crash else 0
            content = f"# 📅 {month_str} 大跌大涨月报\n\n"
            content += f"- 暴跌: **{n_crash}** 次, 平均跌幅 **{avg_crash:.2f}%**\n"
            content += f"- 暴涨: **{n_rally}** 次\n\n"
            content += "## 事件列表\n\n"
            content += "| 日期 | 类型 | 指数 | 涨跌幅 | 幅度 | 触发 | 详情 | 信号 |\n"
            content += "|---|---|---|---|---|---|---|---|\n"
            for r in rows:
                t = "🔴暴跌" if r[1] == "crash" else "🟢暴涨"
                content += f"| {r[0]} | {t} | {r[2] or ''} | {r[3] or 0:.2f}% | {r[4] or ''} | {r[5] or ''} | {r[6] or ''} | {r[7] or ''} |\n"
            content += "\n## 触发原因分布\n\n"
            trig_count = {}
            for r in rows:
                t = r[5] or "未知"
                trig_count[t] = trig_count.get(t, 0) + 1
            for t, n in sorted(trig_count.items(), key=lambda x: -x[1]):
                content += f"- {t}: {n} 次\n"
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("成功", f"月报已导出:\n{fp}")
        except Exception as e:
            print(f"[大跌大涨] 月报导出失败(跳过): {e}")

    def _export_year_md_b(self):
        """导出当年事件 Markdown 报告"""
        try:
            ym = self._view_month_b
            year_str = f"{ym.year:04d}"
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT event_date,event_type,index_name,index_pct,magnitude,trigger,trigger_detail,leading_signals,notes FROM crash_rally_events WHERE event_date LIKE ? ORDER BY event_date", (year_str + "%",))
            rows = cur.fetchall()
            conn.close()
            if not rows:
                messagebox.showinfo("提示", f"{year_str} 无事件记录")
                return
            fp = filedialog.asksaveasfilename(defaultextension=".md",
                                              initialfile=f"crash_rally_{year_str}.md",
                                              filetypes=[("Markdown", "*.md")])
            if not fp: return
            n_crash = sum(1 for r in rows if r[1] == "crash")
            n_rally = sum(1 for r in rows if r[1] == "rally")
            avg_crash = sum(r[3] for r in rows if r[1] == "crash") / n_crash if n_crash else 0
            content = f"# 📅 {year_str} 年度大跌大涨回顾\n\n"
            content += f"- 全年暴跌: **{n_crash}** 次, 平均跌幅 **{avg_crash:.2f}%**\n"
            content += f"- 全年暴涨: **{n_rally}** 次\n\n"
            # 按月拆解
            by_month = {}
            for r in rows:
                m = r[0][5:7]
                if m not in by_month: by_month[m] = []
                by_month[m].append(r)
            content += "## 按月拆解\n\n"
            for m in sorted(by_month.keys()):
                evs = by_month[m]
                content += f"### {m}月 ({len(evs)} 事件)\n\n"
                for r in evs:
                    t = "🔴暴跌" if r[1] == "crash" else "🟢暴涨"
                    content += f"- **{r[0]}** {t} {r[2] or ''} {r[3] or 0:.2f}% [{r[4] or ''}] — {r[5] or ''}: {r[6] or ''}\n"
                content += "\n"
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("成功", f"年报已导出:\n{fp}")
        except Exception as e:
            print(f"[大跌大涨] 年报导出失败(跳过): {e}")

    # ---------- Tab C: 信号回测 ----------
    def _build_tab_c(self, parent):
        tk.Label(parent, text="🔍 信号历史命中率回测", font=FONT_TITLE,
                 bg=COLOR_BG, fg=COLOR_FG).pack(anchor="w", padx=6, pady=6)
        # 信号库列表
        cols = ("signal", "desc", "quant", "hit_crash", "hit_rally", "total", "rate")
        self.list_c = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for c, t, w in [("signal", "信号类型", 140), ("desc", "描述", 200),
                        ("quant", "量化标准", 180), ("hit_crash", "→暴跌", 60),
                        ("hit_rally", "→暴涨", 60), ("total", "总出现", 60), ("rate", "命中率%", 70)]:
            self.list_c.heading(c, text=t)
            self.list_c.column(c, width=w, anchor="w")
        self.list_c.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        # 信号组合推荐区
        tk.Label(parent, text="💡 高胜率信号组合推荐", font=FONT_TITLE,
                 bg=COLOR_BG, fg="#FFD700").pack(anchor="w", padx=6, pady=(10, 2))
        cols2 = ("combo", "hit", "total", "rate", "note")
        self.list_c2 = ttk.Treeview(parent, columns=cols2, show="headings", height=6)
        for c, t, w in [("combo", "信号组合", 320), ("hit", "命中", 60),
                        ("total", "总出现", 60), ("rate", "命中率%", 70), ("note", "说明", 200)]:
            self.list_c2.heading(c, text=t)
            self.list_c2.column(c, width=w, anchor="w")
        self.list_c2.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        tk.Button(parent, text="🔄刷新回测", command=self._reload_c,
                  font=FONT_SMALL).pack(pady=4)
        self._reload_c()

    def _reload_c(self):
        try:
            for it in self.list_c.get_children():
                self.list_c.delete(it)
            for it in self.list_c2.get_children():
                self.list_c2.delete(it)
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT leading_signals,event_type FROM crash_rally_events WHERE leading_signals != ''")
            stats = {}
            # 记录每个事件包含的信号集合, 用于组合分析
            event_sigs = []
            for sig_str, et in cur.fetchall():
                sigs = [s.strip() for s in sig_str.replace("，", ",").split(",") if s.strip()]
                event_sigs.append((sigs, et))
                for s in sigs:
                    if s not in stats:
                        stats[s] = {"crash": 0, "rally": 0, "total": 0}
                    stats[s]["total"] += 1
                    if et == "crash": stats[s]["crash"] += 1
                    elif et == "rally": stats[s]["rally"] += 1
            conn.close()
            # 信号库描述/量化标准映射
            sig_meta = {s[0]: (s[1], s[2]) for s in self.SIGNAL_LIB}
            for s, v in sorted(stats.items(), key=lambda x: -x[1]["total"]):
                rate = (v["crash"] + v["rally"]) / v["total"] * 100 if v["total"] else 0
                desc, quant = sig_meta.get(s, ("", ""))
                self.list_c.insert("", "end", values=(s, desc, quant, v["crash"], v["rally"], v["total"], f"{rate:.1f}"))
            # 组合分析: 找出 2-3 信号同时出现且命中率>阈值的组合
            combo_stats = {}
            for sigs, et in event_sigs:
                if len(sigs) < 2: continue
                # 两两组合
                import itertools
                for c in itertools.combinations(sorted(set(sigs)), 2):
                    key = " + ".join(c)
                    if key not in combo_stats:
                        combo_stats[key] = {"crash": 0, "rally": 0, "total": 0}
                    combo_stats[key]["total"] += 1
                    if et == "crash": combo_stats[key]["crash"] += 1
                    elif et == "rally": combo_stats[key]["rally"] += 1
            for combo, v in sorted(combo_stats.items(), key=lambda x: -x[1]["total"]):
                if v["total"] < 2: continue  # 至少出现2次
                hit = v["crash"] + v["rally"]
                rate = hit / v["total"] * 100 if v["total"] else 0
                if rate < 50: continue  # 命中率<50%不推荐
                note = "暴跌倾向" if v["crash"] > v["rally"] else ("暴涨倾向" if v["rally"] > v["crash"] else "双向")
                self.list_c2.insert("", "end", values=(combo, hit, v["total"], f"{rate:.1f}", note))
        except Exception as e:
            print(f"[大跌大涨] 信号回测加载失败(跳过): {e}")

    # ---------- Tab D: 盘中预警 ----------
    def _build_tab_d(self, parent):
        tk.Label(parent, text="🚨 盘中实时预警监控", font=FONT_TITLE,
                 bg=COLOR_BG, fg=COLOR_FG).pack(anchor="w", padx=6, pady=6)
        # 控制按钮
        ctrl = tk.Frame(parent, bg=COLOR_BG)
        ctrl.pack(fill=tk.X, padx=6, pady=4)
        self.btn_start_d = tk.Button(ctrl, text="▶️启动监控", command=self._start_monitor_d,
                                     font=FONT_SMALL, bg="#2E7D32", fg="white")
        self.btn_start_d.pack(side=tk.LEFT)
        self.btn_stop_d = tk.Button(ctrl, text="⏹️停止", command=self._stop_monitor_d,
                                    font=FONT_SMALL, bg="#C62828", fg="white", state="disabled")
        self.btn_stop_d.pack(side=tk.LEFT, padx=8)
        self.lbl_status_d = tk.Label(ctrl, text="状态: 未启动", font=FONT_SMALL, bg=COLOR_BG, fg="#9E9E9E")
        self.lbl_status_d.pack(side=tk.LEFT)
        tk.Button(ctrl, text="⚙️阈值配置", command=self._show_threshold_d,
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=12)
        tk.Button(ctrl, text="🔄手动刷新", command=self._manual_check_d, font=FONT_SMALL).pack(side=tk.RIGHT)
        # 实时指标看板
        board = tk.Frame(parent, bg=COLOR_BG)
        board.pack(fill=tk.X, padx=6, pady=4)
        self.lbl_sh_pct = tk.Label(board, text="上证: --", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG)
        self.lbl_sh_pct.pack(side=tk.LEFT, padx=12)
        self.lbl_sz_pct = tk.Label(board, text="深证: --", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG)
        self.lbl_sz_pct.pack(side=tk.LEFT, padx=12)
        self.lbl_cyb_pct = tk.Label(board, text="创业板: --", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG)
        self.lbl_cyb_pct.pack(side=tk.LEFT, padx=12)
        # 当前预警等级
        warn_bar = tk.Frame(parent, bg=COLOR_BG)
        warn_bar.pack(fill=tk.X, padx=6, pady=4)
        tk.Label(warn_bar, text="当前预警等级:", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG).pack(side=tk.LEFT)
        self.lbl_alert_level = tk.Label(warn_bar, text="🟢 正常", font=FONT_TITLE, bg=COLOR_BG, fg="#4CAF50")
        self.lbl_alert_level.pack(side=tk.LEFT, padx=12)
        # 阈值配置表 (默认值)
        self.thresholds = {
            "上证跌幅红警": -2.0, "上证跌幅黄警": -1.0, "上证涨幅绿警": 2.0,
        }
        # 预警历史
        tk.Label(parent, text="📋 预警历史", font=FONT_SMALL, bg=COLOR_BG, fg="#9E9E9E").pack(anchor="w", padx=6, pady=(8, 2))
        cols_d = ("time", "level", "signal", "msg", "false_alarm")
        self.list_d = ttk.Treeview(parent, columns=cols_d, show="headings", height=12)
        for c, t, w in [("time", "时间", 80), ("level", "等级", 80), ("signal", "触发信号", 180),
                        ("msg", "描述", 350), ("false_alarm", "误报?", 60)]:
            self.list_d.heading(c, text=t)
            self.list_d.column(c, width=w, anchor="w")
        self.list_d.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        # 阈值配置面板 (可展开)
        self.threshold_frame = tk.Frame(parent, bg=COLOR_BG)
        # 默认隐藏, 点按钮再显示

    def _show_threshold_d(self):
        try:
            msg = "当前阈值:\n"
            msg += f"  上证跌幅 < {self.thresholds.get('上证跌幅红警', -2.0)}% → 🔴红警\n"
            msg += f"  上证跌幅 < {self.thresholds.get('上证跌幅黄警', -1.0)}% → 🟡黄警\n"
            msg += f"  上证涨幅 > {self.thresholds.get('上证涨幅绿警', 2.0)}% → 🟢绿警\n\n"
            msg += "修改阈值请输入新值 (留空保持不变):"
            new_red = simpledialog.askstring("阈值", f"上证跌幅红警 (当前{self.thresholds['上证跌幅红警']}%):")
            if new_red and new_red.strip():
                try:
                    self.thresholds["上证跌幅红警"] = float(new_red.strip())
                except Exception:
                    pass
            new_yellow = simpledialog.askstring("阈值", f"上证跌幅黄警 (当前{self.thresholds['上证跌幅黄警']}%):")
            if new_yellow and new_yellow.strip():
                try:
                    self.thresholds["上证跌幅黄警"] = float(new_yellow.strip())
                except Exception:
                    pass
            messagebox.showinfo("阈值", f"已更新阈值:\n{self.thresholds}")
        except Exception as e:
            print(f"[大跌大涨] 阈值配置失败(跳过): {e}")

    def _start_monitor_d(self):
        if self._monitor_running:
            return
        self._monitor_running = True
        self.btn_start_d.config(state="disabled")
        self.btn_stop_d.config(state="normal")
        self.lbl_status_d.config(text="状态: 监控中...", fg="#4CAF50")
        self._monitor_thread = threading.Thread(target=self._monitor_loop_d, daemon=True)
        self._monitor_thread.start()

    def _stop_monitor_d(self):
        self._monitor_running = False
        self.btn_start_d.config(state="normal")
        self.btn_stop_d.config(state="disabled")
        self.lbl_status_d.config(text="状态: 已停止", fg="#9E9E9E")

    def _monitor_loop_d(self):
        while self._monitor_running:
            try:
                self._do_check_d()
            except Exception as e:
                print(f"[大跌大涨] 监控异常(跳过): {e}")
            # 60秒刷新一次
            for _ in range(60):
                if not self._monitor_running: break
                time.sleep(1)

    def _manual_check_d(self):
        threading.Thread(target=self._do_check_d, daemon=True).start()

    def _do_check_d(self):
        """实时检测预警信号"""
        try:
            if not self.quote: return
            indices = self.quote.get_index_realtime(["sh000001", "sz399001", "sz399006"])
            if not indices: return
            # 更新看板
            def _ui():
                try:
                    for idx in indices:
                        nm = idx["name"][:2]
                        pct = idx["pct"]
                        color = "#C62828" if pct < 0 else "#2E7D32"
                        if "上证" in nm or "000001" in idx.get("code", ""):
                            self.lbl_sh_pct.config(text=f"上证: {pct:+.2f}%", fg=color)
                        elif "深证" in nm or "深证成" in nm:
                            self.lbl_sz_pct.config(text=f"深证: {pct:+.2f}%", fg=color)
                        elif "创业板" in nm:
                            self.lbl_cyb_pct.config(text=f"创业板: {pct:+.2f}%", fg=color)
                except Exception:
                    pass
            try:
                self.root.after(0, _ui)
            except Exception:
                pass
            # 预警检测 (使用可配置阈值)
            sh = next((x for x in indices if "000001" in x.get("code", "")), None)
            if not sh: return
            pct = sh["pct"]
            now_str = _dt2.now().strftime("%H:%M:%S")
            red_th = self.thresholds.get("上证跌幅红警", -2.0)
            yellow_th = self.thresholds.get("上证跌幅黄警", -1.0)
            green_th = self.thresholds.get("上证涨幅绿警", 2.0)
            level = "🟢 正常"
            level_color = "#4CAF50"
            if pct < red_th:
                level = "🔴 红警"
                level_color = "#C62828"
                self._add_alert_d(now_str, "🔴红", "指数大跌", f"上证{pct:.2f}% 跌幅较大,建议减仓", "?")
                try:
                    self.root.after(0, lambda: messagebox.showwarning("🔴红色预警", f"上证{pct:.2f}%\n建议减仓/清仓观望"))
                except Exception:
                    pass
            elif pct < yellow_th:
                level = "🟡 黄警"
                level_color = "#FF6F00"
                self._add_alert_d(now_str, "🟡黄", "指数下跌", f"上证{pct:.2f}% 下跌中,关注", "?")
            elif pct > green_th:
                level = "🟢 强势"
                level_color = "#2E7D32"
                self._add_alert_d(now_str, "🟢绿", "指数大涨", f"上证{pct:.2f}% 涨幅较大", "?")
            try:
                self.root.after(0, lambda: self.lbl_alert_level.config(text=level, fg=level_color))
            except Exception:
                pass
        except Exception as e:
            print(f"[大跌大涨] 预警检测失败(跳过): {e}")

    def _add_alert_d(self, t, level, signal, msg, false_alarm="?"):
        def _ui():
            try:
                self.list_d.insert("", "0", values=(t, level, signal, msg, false_alarm))
                # 最多保留 100 条
                children = self.list_d.get_children()
                if len(children) > 100:
                    self.list_d.delete(children[-1])
            except Exception:
                pass
        try:
            self.root.after(0, _ui)
        except Exception:
            pass

    # ---------- 节假日字典 (公历日期, 用于节日效应) ----------
    # 格式: "YYYY-MM-DD" -> ("节日名", 假期起始天数偏移)
    # 偏移0=节日当天, 负数=节前, 正数=节后
    HOLIDAYS = {
        # 中秋节 (公历日期, 2018-2026)
        "2024-09-17": "中秋节", "2025-10-06": "中秋节", "2026-09-25": "中秋节",
        "2021-09-21": "中秋节", "2022-09-10": "中秋节", "2023-09-29": "中秋节",
        "2018-09-24": "中秋节", "2019-09-13": "中秋节", "2020-10-01": "中秋节",
        # 春节 (正月初一)
        "2018-02-16": "春节", "2019-02-05": "春节", "2020-01-25": "春节",
        "2021-02-12": "春节", "2022-02-01": "春节", "2023-01-22": "春节",
        "2024-02-10": "春节", "2025-01-29": "春节", "2026-02-17": "春节",
        # 国庆 (10月1日)
        "2018-10-01": "国庆节", "2019-10-01": "国庆节", "2020-10-01": "国庆节",
        "2021-10-01": "国庆节", "2022-10-01": "国庆节", "2023-10-01": "国庆节",
        "2024-10-01": "国庆节", "2025-10-01": "国庆节", "2026-10-01": "国庆节",
        # 劳动节
        "2018-05-01": "劳动节", "2019-05-01": "劳动节", "2020-05-01": "劳动节",
        "2021-05-01": "劳动节", "2022-05-01": "劳动节", "2023-05-01": "劳动节",
        "2024-05-01": "劳动节", "2025-05-01": "劳动节", "2026-05-01": "劳动节",
    }

    # ---------- 帮助 ----------
    def _show_help(self):
        try:
            help_text = """🗓️ 大跌大涨日历 使用说明

【Tab A 历史事件记录】
- 新增: 点➕新增,填日期/类型/指数,可点🔍拉取当日涨跌幅
- 编辑: 列表中点中事件,右侧表单自动填充,改完点💾保存
- 导入/导出CSV: 支持批量导入历史数据

【Tab B 事件日历视图】
- 月历视图,红色=暴跌,绿色=暴涨
- 点击日期格子查看事件详情
- ◀上月/下月▶切换,📍今天回到当前月
- 📄导出月报MD/年报MD: Markdown 格式事件报告

【Tab C 信号回测】
- 统计每个"提前信号"在历史事件中的命中率
- 💡高胜率信号组合推荐: 两两组合命中率>50%
- 可用于发现高胜率预警信号组合

【Tab D 盘中预警】
- ▶️启动监控后,每60秒刷新一次实时行情
- 自动检测上证指数涨跌,触发红/黄/绿预警
- 默认阈值: <-2%红警,<-1%黄警,>2%绿警
- ⚙️阈值配置: 可调整预警阈值
- 🔴红警触发弹窗提示
- 预警等级实时显示在看板上

数据库: ~/.qclaw/stock_analysis.db (表: crash_rally_events)
字段: event_date/event_type/index_name/index_pct/magnitude/trigger/trigger_detail/leading_signals/signal_days_before/recovery_days/max_recover_pct/notes/source_urls/related_stocks
"""
            messagebox.showinfo("帮助", help_text)
        except Exception as e:
            print(f"[大跌大涨] 帮助显示失败(跳过): {e}")

    # ============================================================
    # Tab E: 🔮 涨跌预测 (情绪周期 + 历史相似 + 节日效应)
    # ============================================================
    EMO_HIST_PATH = os.path.join(os.path.expanduser("~"),
                                 ".qclaw/workspace-agent-85985980/stockyidong_emo_history.json")

    def _build_tab_e(self, parent):
        """构建涨跌预测 Tab"""
        tk.Label(parent, text="🔮 涨跌预测 (情绪周期+历史相似+节日效应)",
                 font=FONT_TITLE, bg=COLOR_BG, fg="#FFD700").pack(anchor="w", padx=6, pady=6)
        # 当前情境输入
        inp = tk.LabelFrame(parent, text="当前情境", font=FONT_SMALL,
                            bg=COLOR_BG, fg=COLOR_FG)
        inp.pack(fill=tk.X, padx=6, pady=4)
        form = tk.Frame(inp, bg=COLOR_BG)
        form.pack(fill=tk.X, padx=6, pady=4)
        self.v_pred_date = tk.StringVar(value=_dt2.now().strftime("%Y-%m-%d"))
        self.v_pred_stage = tk.StringVar()
        self.v_pred_score = tk.StringVar()
        self.v_pred_pct5 = tk.StringVar()
        tk.Label(form, text="日期:", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG).grid(row=0, column=0, padx=4, pady=3, sticky="e")
        tk.Entry(form, textvariable=self.v_pred_date, width=14, font=FONT_SMALL).grid(row=0, column=1, padx=4)
        tk.Button(form, text="🔍自动读取情绪周期", command=self._auto_load_emo_e,
                  font=FONT_SMALL).grid(row=0, column=2, padx=8)
        tk.Label(form, text="情绪阶段:", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG).grid(row=1, column=0, padx=4, pady=3, sticky="e")
        tk.Label(form, textvariable=self.v_pred_stage, font=FONT_TITLE,
                 bg=COLOR_BG, fg="#4CAF50", width=10).grid(row=1, column=1, sticky="w")
        tk.Label(form, text="情绪分:", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG).grid(row=1, column=2, padx=4, sticky="e")
        tk.Label(form, textvariable=self.v_pred_score, font=FONT_TITLE,
                 bg=COLOR_BG, fg="#FFD700", width=6).grid(row=1, column=3, sticky="w")
        tk.Label(form, text="近5日涨跌:", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG).grid(row=2, column=0, padx=4, pady=3, sticky="e")
        tk.Label(form, textvariable=self.v_pred_pct5, font=FONT_SMALL,
                 bg=COLOR_BG, fg=COLOR_FG).grid(row=2, column=1, sticky="w")
        # 预测按钮
        btn = tk.Frame(parent, bg=COLOR_BG)
        btn.pack(fill=tk.X, padx=6, pady=4)
        tk.Button(btn, text="🔮 综合预测", command=self._predict_e,
                  font=FONT_TITLE, bg="#1565C0", fg="white", width=14).pack(side=tk.LEFT)
        tk.Button(btn, text="📊历史相似", command=self._find_similar_e,
                  font=FONT_SMALL).pack(side=tk.LEFT, padx=8)
        tk.Button(btn, text="🎎节日效应", command=self._holiday_effect_e,
                  font=FONT_SMALL).pack(side=tk.LEFT)
        # 预测结果输出区
        tk.Label(parent, text="📈 预测结果", font=FONT_TITLE,
                 bg=COLOR_BG, fg=COLOR_FG).pack(anchor="w", padx=6, pady=(8, 2))
        self.txt_pred_e = tk.Text(parent, height=22, font=FONT_MAIN, wrap=tk.WORD,
                                  bg="#0D0D1F", fg=COLOR_FG, relief="flat")
        self.txt_pred_e.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    def _auto_load_emo_e(self):
        """自动读取情绪周期 JSON 填充表单"""
        try:
            dt = self.v_pred_date.get().strip()[:10]
            if not os.path.exists(self.EMO_HIST_PATH):
                messagebox.showwarning("提示", f"情绪周期数据不存在:\n{self.EMO_HIST_PATH}")
                return
            with open(self.EMO_HIST_PATH) as f:
                emo = json.load(f)
            if not isinstance(emo, dict):
                messagebox.showwarning("提示", "情绪周期数据格式异常")
                return
            # 找最近的情绪记录 (当天或之前)
            target = None
            for k in sorted(emo.keys(), reverse=True):
                if k <= dt:
                    target = emo[k]
                    break
            if not target:
                messagebox.showwarning("提示", f"{dt} 之前无情绪周期数据")
                return
            self.v_pred_stage.set(target.get("stage", "?"))
            self.v_pred_score.set(str(target.get("emo_score", "?")))
            print(f"[预测] 已读取情绪周期 {dt}: {target.get('stage','?')} score={target.get('emo_score','?')}")
            # 拉取近5日涨跌幅
            if self.quote:
                kls = self.quote.get_kline("sh000001", count=10)
                last5 = kls[-6:] if len(kls) >= 6 else kls
                if len(last5) >= 2:
                    pct5 = (last5[-1]["close"] - last5[0]["close"]) / last5[0]["close"] * 100
                    self.v_pred_pct5.set(f"{pct5:+.2f}% ({last5[0]['date']}→{last5[-1]['date']})")
                else:
                    self.v_pred_pct5.set("数据不足")
            else:
                self.v_pred_pct5.set("行情接口未初始化")
        except Exception as e:
            print(f"[预测] 读取情绪周期失败(跳过): {e}")
            messagebox.showerror("错误", f"读取失败: {e}")

    def _find_similar_e(self):
        """历史相似情境匹配: 同情绪阶段+相似涨跌幅度, 看后续N日表现"""
        try:
            self.txt_pred_e.delete("1.0", tk.END)
            self.txt_pred_e.insert(tk.END, "📊 历史相似情境匹配...\n" + "="*50 + "\n\n")
            stage = self.v_pred_stage.get().strip()
            if not stage:
                self.txt_pred_e.insert(tk.END, "⚠️ 请先点🔍自动读取情绪周期\n")
                return
            # 读取情绪周期全部历史
            emo = {}
            if os.path.exists(self.EMO_HIST_PATH):
                with open(self.EMO_HIST_PATH) as f:
                    raw = json.load(f)
                if isinstance(raw, dict): emo = raw
            # 找同情绪阶段的历史日期
            same_stage_dates = []
            for d, v in emo.items():
                if v.get("stage") == stage and d < self.v_pred_date.get().strip()[:10]:
                    same_stage_dates.append((d, v))
            same_stage_dates.sort(key=lambda x: x[0])
            self.txt_pred_e.insert(tk.END, f"当前情绪阶段: {stage}\n")
            self.txt_pred_e.insert(tk.END, f"历史同阶段事件数: {len(same_stage_dates)}\n\n")
            if len(same_stage_dates) < 3:
                self.txt_pred_e.insert(tk.END, "⚠️ 同阶段历史样本不足3个,建议谨慎参考\n\n")
            # 拉取指数日K线, 计算每个同阶段日期后续1/3/5/10日涨跌
            if not self.quote:
                self.txt_pred_e.insert(tk.END, "⚠️ 行情接口未初始化, 无法计算后续涨跌\n")
                return
            kls = self.quote.get_kline("sh000001", count=400)
            kls_map = {k["date"]: k for k in kls}
            kls_list = kls
            stats = {"1日": [], "3日": [], "5日": [], "10日": []}
            for d, v in same_stage_dates:
                # 在 kls_list 中找位置
                idx = -1
                for i, k in enumerate(kls_list):
                    if k["date"] == d:
                        idx = i
                        break
                if idx < 0 or idx + 10 >= len(kls_list):
                    continue
                close0 = kls_list[idx]["close"]
                for n, key in [(1, "1日"), (3, "3日"), (5, "5日"), (10, "10日")]:
                    if idx + n < len(kls_list):
                        pct = (kls_list[idx + n]["close"] - close0) / close0 * 100
                        stats[key].append(pct)
            # 输出统计
            self.txt_pred_e.insert(tk.END, "📈 同情绪阶段后N日统计:\n")
            for key in ["1日", "3日", "5日", "10日"]:
                arr = stats[key]
                if not arr: continue
                up_n = sum(1 for x in arr if x > 0)
                avg = sum(arr) / len(arr)
                self.txt_pred_e.insert(
                    tk.END, f"  后{key}: 样本{len(arr)}次, 上涨{up_n}次({up_n/len(arr)*100:.0f}%), 平均{avg:+.2f}%\n")
            self.txt_pred_e.insert(tk.END, "\n")
            # 同情绪阶段+同触发信号匹配 crash_rally_events
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT event_date,trigger,leading_signals,index_pct FROM crash_rally_events WHERE trigger != '' ORDER BY event_date")
            ev_rows = cur.fetchall()
            conn.close()
            self.txt_pred_e.insert(tk.END, "🎯 同情绪阶段+大跌大涨事件:\n")
            match_count = 0
            for ev_date, trig, sigs, pct in ev_rows:
                # 检查事件日附近5日内情绪阶段是否匹配
                # 简化: 直接按事件日附近的情绪记录检查
                for d, v in emo.items():
                    if v.get("stage") == stage:
                        try:
                            ed = _dt2.strptime(ev_date, "%Y-%m-%d").date()
                            vd = _dt2.strptime(d, "%Y-%m-%d").date()
                            if abs((ed - vd).days) <= 3:
                                match_count += 1
                                self.txt_pred_e.insert(
                                    tk.END, f"  {ev_date} {trig} {pct:.2f}% 信号:{sigs}\n")
                                break
                        except Exception:
                            pass
            if match_count == 0:
                self.txt_pred_e.insert(tk.END, "  (无匹配事件)\n")
        except Exception as e:
            print(f"[预测] 历史相似匹配失败(跳过): {e}")
            self.txt_pred_e.insert(tk.END, f"\n❌ 失败: {e}\n")

    def _holiday_effect_e(self):
        """节日效应: 当前日期附近节日的历史前后涨跌统计"""
        try:
            self.txt_pred_e.delete("1.0", tk.END)
            self.txt_pred_e.insert(tk.END, "🎎 节日效应统计...\n" + "="*50 + "\n\n")
            dt_str = self.v_pred_date.get().strip()[:10]
            try:
                target = _dt2.strptime(dt_str, "%Y-%m-%d").date()
            except Exception:
                self.txt_pred_e.insert(tk.END, "⚠️ 日期格式错误\n")
                return
            # 找最近的节日
            nearest = None
            nearest_delta = 999
            for hd, name in self.HOLIDAYS.items():
                try:
                    hd_date = _dt2.strptime(hd, "%Y-%m-%d").date()
                    delta = (target - hd_date).days
                    if abs(delta) < abs(nearest_delta) and abs(delta) <= 15:
                        nearest = (hd, name, delta)
                        nearest_delta = delta
                except Exception:
                    pass
            if not nearest:
                self.txt_pred_e.insert(tk.END, "⚠️ 当前日期附近15天内无已知节日\n")
                return
            hd, name, delta = nearest
            pos = "节前%d天" % abs(delta) if delta < 0 else ("节后%d天" % delta if delta > 0 else "当天")
            self.txt_pred_e.insert(tk.END, f"最近节日: {name} ({hd}), 当前位置: {pos}\n\n")
            # 拉取指数K线, 找每年该节日前后5日的涨跌
            if not self.quote:
                self.txt_pred_e.insert(tk.END, "⚠️ 行情接口未初始化\n")
                return
            kls = self.quote.get_kline("sh000001", count=2000)
            # 找所有同名节日
            same_holidays = [(d, n) for d, n in self.HOLIDAYS.items() if n == name]
            same_holidays.sort()
            self.txt_pred_e.insert(tk.END, f"📊 {name} 历史效应 (前后5个交易日):\n")
            before_stats = []
            after_stats = []
            for hd2, _ in same_holidays:
                # 在 K线中找该日期附近
                try:
                    hd2_date = _dt2.strptime(hd2, "%Y-%m-%d").date()
                except Exception:
                    continue
                # 找节前5日和节后5日
                idx = -1
                for i, k in enumerate(kls):
                    try:
                        kd = _dt2.strptime(k["date"], "%Y-%m-%d").date()
                    except Exception:
                        continue
                    if kd >= hd2_date:
                        idx = i
                        break
                if idx < 0 or idx + 5 >= len(kls) or idx - 5 < 0:
                    continue
                # 节前5日涨跌: 节前第5日 → 节前1日
                before_pct = (kls[idx-1]["close"] - kls[idx-5]["close"]) / kls[idx-5]["close"] * 100
                # 节后5日涨跌: 节前1日 → 节后5日
                after_pct = (kls[idx+5]["close"] - kls[idx-1]["close"]) / kls[idx-1]["close"] * 100
                before_stats.append(before_pct)
                after_stats.append(after_pct)
                self.txt_pred_e.insert(tk.END, f"  {hd2}: 节前5日 {before_pct:+.2f}%, 节后5日 {after_pct:+.2f}%\n")
            if before_stats:
                avg_b = sum(before_stats) / len(before_stats)
                up_b = sum(1 for x in before_stats if x > 0)
                avg_a = sum(after_stats) / len(after_stats)
                up_a = sum(1 for x in after_stats if x > 0)
                self.txt_pred_e.insert(tk.END, "\n📈 统计:\n")
                self.txt_pred_e.insert(tk.END, f"  节前5日平均{avg_b:+.2f}%, 上涨{up_b}/{len(before_stats)}次\n")
                self.txt_pred_e.insert(tk.END, f"  节后5日平均{avg_a:+.2f}%, 上涨{up_a}/{len(after_stats)}次\n")
                if avg_a > 0.5 and up_a / len(after_stats) >= 0.6:
                    self.txt_pred_e.insert(tk.END, "\n✅ 节后偏涨, 历史胜率较高\n")
                elif avg_a < -0.5 and up_a / len(after_stats) <= 0.4:
                    self.txt_pred_e.insert(tk.END, "\n⚠️ 节后偏跌, 历史胜率较高\n")
                else:
                    self.txt_pred_e.insert(tk.END, "\n➖ 节后震荡为主, 无明显规律\n")
        except Exception as e:
            print(f"[预测] 节日效应失败(跳过): {e}")
            self.txt_pred_e.insert(tk.END, f"\n❌ 失败: {e}\n")

    def _predict_e(self):
        """综合预测: 综合情绪阶段+历史相似+节日效应给出结论"""
        try:
            self.txt_pred_e.delete("1.0", tk.END)
            self.txt_pred_e.insert(tk.END, "🔮 综合预测分析...\n" + "="*50 + "\n\n")
            stage = self.v_pred_stage.get().strip()
            score_str = self.v_pred_score.get().strip()
            if not stage:
                self.txt_pred_e.insert(tk.END, "⚠️ 请先点🔍自动读取情绪周期\n")
                return
            self.txt_pred_e.insert(tk.END, f"当前情绪阶段: {stage}\n")
            if score_str:
                try:
                    score = float(score_str)
                    self.txt_pred_e.insert(tk.END, f"情绪分: {score}\n")
                except Exception:
                    score = 50
            else:
                score = 50
            self.txt_pred_e.insert(tk.END, "\n")
            # ===== 规则1: 情绪阶段判断 =====
            self.txt_pred_e.insert(tk.END, "📊 规则1: 情绪阶段判断\n")
            if stage in ("高潮",):
                self.txt_pred_e.insert(tk.END, "  → 情绪高潮, 历史易见顶回落, 偏跌\n")
                emo_bias = -1
            elif stage in ("发酵",):
                self.txt_pred_e.insert(tk.END, "  → 情绪发酵, 趋势中继, 偏涨但需警惕\n")
                emo_bias = 0.5
            elif stage in ("启动",):
                self.txt_pred_e.insert(tk.END, "  → 情绪启动, 偏涨\n")
                emo_bias = 1
            elif stage in ("震荡",):
                self.txt_pred_e.insert(tk.END, "  → 情绪震荡, 中性\n")
                emo_bias = 0
            elif stage in ("分歧",):
                self.txt_pred_e.insert(tk.END, "  → 情绪分歧, 偏跌\n")
                emo_bias = -0.5
            elif stage in ("退潮",):
                self.txt_pred_e.insert(tk.END, "  → 情绪退潮, 偏跌\n")
                emo_bias = -1
            else:
                emo_bias = 0
            self.txt_pred_e.insert(tk.END, "\n")
            # ===== 规则2: 情绪分判断 =====
            self.txt_pred_e.insert(tk.END, "📊 规则2: 情绪分判断\n")
            if score >= 70:
                self.txt_pred_e.insert(tk.END, f"  → 情绪分{score}≥70, 过热易见顶\n")
                score_bias = -1
            elif score >= 60:
                self.txt_pred_e.insert(tk.END, f"  → 情绪分{score}, 偏强\n")
                score_bias = 0.5
            elif score >= 50:
                self.txt_pred_e.insert(tk.END, f"  → 情绪分{score}, 中性\n")
                score_bias = 0
            elif score >= 30:
                self.txt_pred_e.insert(tk.END, f"  → 情绪分{score}, 偏弱\n")
                score_bias = -0.5
            else:
                self.txt_pred_e.insert(tk.END, f"  → 情绪分{score}≤30, 过冷易反弹\n")
                score_bias = 1  # 超卖反弹
            self.txt_pred_e.insert(tk.END, "\n")
            # ===== 规则3: 节日效应 =====
            self.txt_pred_e.insert(tk.END, "📊 规则3: 节日效应\n")
            dt_str = self.v_pred_date.get().strip()[:10]
            try:
                target = _dt2.strptime(dt_str, "%Y-%m-%d").date()
            except Exception:
                target = _dt2.now().date()
            nearest = None
            nearest_delta = 999
            for hd, name in self.HOLIDAYS.items():
                try:
                    hd_date = _dt2.strptime(hd, "%Y-%m-%d").date()
                    delta = (target - hd_date).days
                    if abs(delta) < abs(nearest_delta) and abs(delta) <= 10:
                        nearest = (hd, name, delta)
                        nearest_delta = delta
                except Exception:
                    pass
            if nearest:
                hd, name, delta = nearest
                pos = "节前%d天" % abs(delta) if delta < 0 else ("节后%d天" % delta if delta > 0 else "当天")
                self.txt_pred_e.insert(tk.END, f"  → 临近{name} ({pos})\n")
                # 节前普遍偏谨慎, 节后普遍偏乐观
                if delta < 0 and abs(delta) <= 3:
                    self.txt_pred_e.insert(tk.END, "  → 节前3日内, 历史偏谨慎\n")
                    holiday_bias = -0.5
                elif delta > 0 and delta <= 3:
                    self.txt_pred_e.insert(tk.END, "  → 节后3日内, 历史偏乐观\n")
                    holiday_bias = 0.5
                else:
                    holiday_bias = 0
            else:
                self.txt_pred_e.insert(tk.END, "  → 无临近节日\n")
                holiday_bias = 0
            self.txt_pred_e.insert(tk.END, "\n")
            # ===== 综合结论 =====
            total_bias = emo_bias + score_bias + holiday_bias
            self.txt_pred_e.insert(tk.END, "="*50 + "\n")
            self.txt_pred_e.insert(tk.END, "🎯 综合预测结论:\n\n")
            if total_bias >= 1.5:
                verdict = "偏涨"
                action = "可考虑加仓/持股待涨"
                conf = "中"
                emoji = "📈"
            elif total_bias >= 0.5:
                verdict = "偏涨(谨慎)"
                action = "持股观望, 不追高"
                conf = "低"
                emoji = "📊"
            elif total_bias >= -0.5:
                verdict = "震荡"
                action = "高抛低吸, 控制仓位"
                conf = "中"
                emoji = "⚖️"
            elif total_bias >= -1.5:
                verdict = "偏跌(谨慎)"
                action = "减仓避险, 不抄底"
                conf = "低"
                emoji = "📉"
            else:
                verdict = "偏跌"
                action = "建议减仓/清仓观望"
                conf = "中"
                emoji = "⚠️"
            self.txt_pred_e.insert(tk.END, f"{emoji} 后市: {verdict}\n")
            self.txt_pred_e.insert(tk.END, f"📋 操作: {action}\n")
            self.txt_pred_e.insert(tk.END, f"🎲 置信度: {conf}\n")
            self.txt_pred_e.insert(tk.END, f"📊 综合得分: {total_bias:+.2f} (情绪{emo_bias:+.1f}+分数{score_bias:+.1f}+节日{holiday_bias:+.1f})\n\n")
            self.txt_pred_e.insert(tk.END, "⚠️ 风险提示:\n")
            self.txt_pred_e.insert(tk.END, "本预测基于历史统计, 不保证准确性, 请结合自身判断\n")
            self.txt_pred_e.insert(tk.END, "突发事件(政策/外围)会瞬间改变走势\n")
        except Exception as e:
            print(f"[预测] 综合预测失败(跳过): {e}")
            self.txt_pred_e.insert(tk.END, f"\n❌ 失败: {e}\n")


# ============================================================
# 五、主入口 (独立运行 / 被主程序调用)
# ============================================================
def open_crash_rally_calendar(parent_root=None):
    """被主程序调用入口
    parent_root: 主程序的 root (tk.Tk),如传入则在其下创建 Toplevel 窗口
    """
    if parent_root:
        win = tk.Toplevel(parent_root)
    else:
        win = tk.Tk()
    app = CrashRallyCalendarApp(win)
    return win, app


def main():
    root = tk.Tk()
    app = CrashRallyCalendarApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

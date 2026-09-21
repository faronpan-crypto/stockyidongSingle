from __future__ import annotations
from typing import Optional, Union

import os
import sys

# --- PATH 修复: Trae 启动 macOS 子进程时 PATH 缺 /opt/homebrew/bin,导致 shutil.which("node") 找不到 ---
_homebrew_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
_sep = ":"
_existing = set(os.environ.get("PATH", "").split(_sep))
for _hp in _homebrew_paths:
    if _hp not in _existing and os.path.isdir(_hp):
        os.environ["PATH"] += _sep + _hp
# 在导入任何GUI相关模块之前,设置matplotlib后端
# 这可以防止matplotlib在导入时自动初始化Tkinter导致的问题
import matplotlib

if sys.platform == "darwin":
    matplotlib.use('TkAgg')
else:
    matplotlib.use('TkAgg')
def _early_sqlite_temp_dir():
    """在 import sqlite3 之前设置临时目录;否则 Windows 上仍可能用 C:\\Users\\...\\Temp,C 盘满即报 database or disk is full。"""
    data_root = (os.environ.get("STOCK_ANALYZER_DATA_DIR") or r"D:\StockAnalyzer").strip() or r"D:\StockAnalyzer"
    tmp = os.path.join(data_root, "temp")
    try:
        os.makedirs(tmp, exist_ok=True)
    except Exception:
        return
    if (os.environ.get("SQLITE_TMPDIR") or "").strip():
        return
    try:
        os.environ["SQLITE_TMPDIR"] = os.path.normpath(tmp)
        # 部分 Windows/Python-sqlite 仍走 %TEMP%,与本进程统一指向数据盘
        if sys.platform == "win32":
            os.environ["TEMP"] = os.environ["SQLITE_TMPDIR"]
            os.environ["TMP"] = os.environ["SQLITE_TMPDIR"]
    except Exception:
        pass
_early_sqlite_temp_dir()
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

import jieba
import requests

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
import base64
import contextlib
import copy
import importlib.util
import io
import json
import random
import shutil
import sqlite3
import threading
import time
import warnings
import webbrowser
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urljoin

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageTk
from wordcloud import WordCloud

# ==================== Phase 2 模块化导入 ====================
from utils.suppress import *  # L97-109, 110-124, 126-136, 137-151, 153-161
from logic.crawlers import *  # L492-757, 759-820, 822-1006
from logic.stock_names import *  # L1007-1024, 1025-1029, 1030-1235, 1236-1361, 1362-1382, 1383-1392, 1393-1438, 1439-1490
from data.snapshot import *  # L347-425, 426-490
from logic.dapan_fetcher import *  # L1493-1533, 1534-1546, 1547-1559, 1562-1576, 1578-1592, 1593-1625, 1626-1646, 1647-1666, 1668-1713, 2016-2034, 2036-2038, 2039-2041, 2042-2044, 2045-2104, 2683-2776
from logic.indicators import *  # L1714-1732, 1733-1759, 1760-1774, 1775-1788, 1789-1831
from logic.spot import *  # L1833-1835, 1837-1837, 1839-1839, 1840-1842, 1843-1854, 1855-1861, 1862-1869, 1870-1885, 1886-1901, 1902-1948, 1949-1971, 1972-2015
from logic.wordcloud import *  # L2105-2181, 2182-2277, 2278-2423, 2424-2682
from utils.text_extract import *  # L2777-2780, 2781-2787, 2788-2817, 2819-2857, 2858-2887, 2888-2908, 2910-2949, 2950-2984, 2985-3009


# ==================== 模块化拆分:utils.data ====================
from utils.config import *          # 路径常量 + 配置 + DB_PATH (替代原 L219-L384)
from utils.network import safe_call, safe_ak, safe_requests  # 网络安全封装
from data.db import *               # 全部 DB 函数 (替代原 L495-L1114 中的纯 DB 函数)


# ==================== 明日涨跌预测(Skill) ====================
try:
    from tomorrow_predict import (
        StockPredictInput,
        StockPredictResult,
        batch_predict,
        predict_tomorrow,
    )
    TOMORROW_PREDICT_AVAILABLE = True
except ImportError:
    TOMORROW_PREDICT_AVAILABLE = False
    print("⚠️ tomorrow_predict 未找到,明日涨跌预测功能不可用")
# ==================== 错误抑制工具 ====================
# 创建一个静默的输出流类,用于完全抑制输出
# 全局错误抑制装饰器,用于包装可能产生错误的函数
try:
    import tushare as ts
    TS_AVAILABLE = True
except ImportError:
    ts = None
    TS_AVAILABLE = False

# ===== Tushare API 频率保护: 全局 sleep + 自动重试 (线程安全) =====
import time as _ts_time
import threading as _ts_threading



try:
    import tushare as _ts_mod_safe
    if not getattr(_ts_mod_safe.pro_api, '_ts_is_safe_patched', False):
        _ts_mod_safe.pro_api = _ts_patch_pro_api(_ts_mod_safe.pro_api)
        _ts_mod_safe.pro_api._ts_is_safe_patched = True
except Exception as _e_patch:
    print(f"⚠️ Tushare patch 失败: {_e_patch}")
    print(f"⚠️ Tushare patch 失败: {_e_patch}")

EXCEL_FILES_CONFIG_FILE = os.path.join(D_DATA_DIR, "excel_files_config.json")
DEFAULT_MARKET_NAV_CONFIG = {
    "indices": [
        {"name": "财联社情绪指数", "desc": "实时跟踪A股情绪温度", "url": "https://www.cls.cn/subject/1079"},
        {"name": "富时中国A50期指", "desc": "离岸A股方向,美股时段参考", "url": "https://finance.sina.com.cn/money/future/qhscfx/ftse50.shtml"},
        {"name": "美股主要股指", "desc": "全球风险偏好风向", "url": "https://finance.sina.com.cn/stock/usstock/sector.shtml"},
        {"name": "流动性指标(Shibor)", "desc": "短端利率,观察资金松紧", "url": "https://data.eastmoney.com/shibor/shibor_list.html"},
        {"name": "CPI/PPI数据", "desc": "通胀水平,影响政策节奏", "url": "https://data.eastmoney.com/cjsj/cpi.html"},
        {"name": "国债收益率曲线", "desc": "无风险利率,衡量估值压力", "url": "https://data.eastmoney.com/cjsj/zgyz_list.html"},
        {"name": "中国证监会官网", "desc": "政策发布、非法荐股警示、合法机构查询入口", "url": "http://www.csrc.gov.cn"},
        {"name": "巨潮资讯网", "desc": "证监会指定信息披露平台,上市公司公告/年报权威来源", "url": "http://www.cninfo.com.cn"},
        {"name": "中证指数有限公司", "desc": "指数编制机构,查询沪深300等成分股及估值", "url": "http://www.csindex.com.cn"}
    ],
    "portals": [
        {"name": "Tushare Pro", "desc": "数据接口开放平台,量化回测必备", "url": "https://tushare.pro/"},
        {"name": "JoinQuant 聚宽", "desc": "策略研究与实盘撮合", "url": "https://www.joinquant.com/"},
        {"name": "米筐 RiceQuant", "desc": "量化策略社区+云回测", "url": "https://www.ricequant.com/"},
        {"name": "BigQuant", "desc": "机器学习因子研究平台", "url": "https://bigquant.com/"},
        {"name": "东方财富网", "desc": "行情数据+社区+基金销售,主力持仓查询工具", "url": "https://www.eastmoney.com/"},
        {"name": "同花顺财经", "desc": "实时行情、智能选股、两融数据跟踪", "url": "https://www.10jqka.com.cn/"},
        {"name": "新浪财经", "desc": "全球市场覆盖,外汇/期货实时行情", "url": "https://finance.sina.com.cn/"},
        {"name": "雪球", "desc": "投资者社交平台,大V实盘分享", "url": "https://xueqiu.com/"},
        {"name": "选股宝", "desc": "热点题材挖掘,龙虎榜追踪", "url": "https://xuangubao.cn/"},
        {"name": "萝卜投研", "desc": "免费研报平台,行业数据可视化", "url": "https://robo.datayes.com/"},
        {"name": "财联社", "desc": "24小时电报快讯,政策/突发事件预警", "url": "https://www.cls.cn/"},
        {"name": "TradingView", "desc": "国际级K线分析工具,多市场技术指标", "url": "https://www.tradingview.com/"},
        {"name": "Wind资讯", "desc": "机构级资讯与数据终端", "url": "https://www.wind.com.cn/"},
        {"name": "中金在线", "desc": "综合财经门户,期货外汇全覆盖", "url": "https://www.cnfol.com/"}
    ],
    "hot_sources": [
        {"name": "同花顺热股榜", "url": "https://q.10jqka.com.cn/index/index/board/realTime/"},
        {"name": "东方财富股吧热帖", "url": "https://guba.eastmoney.com/rank/stock"},
        {"name": "雪球热榜", "url": "https://xueqiu.com/hq"},
        {"name": "选股宝龙虎榜", "url": "https://xuangubao.cn/bull"},
        {"name": "选股通主题库", "url": "https://xuangutong.com.cn/zhutiku"},
        {"name": "新浪财经热股", "url": "https://finance.sina.com.cn/stock/"},
        {"name": "财联社热门题材", "url": "https://www.cls.cn/leaderboard"},
        {"name": "知乎股票热议", "url": "https://www.zhihu.com/topic/19555515/hot"},
        {"name": "微博财经热搜", "url": "https://s.weibo.com/top/summary"},
        {"name": "淘股吧", "url": "https://www.taoguba.com.cn/"},
        {"name": "龙虎榜每日统计单", "url": ""},
        {"name": "龙虎榜机构交易单", "url": ""},
        {"name": "同花顺涨跌停榜单", "url": ""},
        {"name": "涨跌停和炸板数据", "url": ""},
        {"name": "涨停股票连板天梯", "url": ""},
        {"name": "涨停最强板块统计", "url": ""},
        {"name": "同花顺行业概念板块", "url": ""},
        {"name": "同花顺概念和行业指数行", "url": ""},
        {"name": "同花顺行业概念成分", "url": ""},
        {"name": "东方财富概念板块", "url": ""},
        {"name": "东方财富概念成分", "url": ""},
        {"name": "东财概念和行业指数行情", "url": ""},
        {"name": "开盘竞价成交(当日)", "url": ""},
        {"name": "市场游资最全名录", "url": ""},
        {"name": "游资交易每日明细", "url": ""},
        {"name": "同花顺App热榜数", "url": ""},
        {"name": "东方财富App热榜", "url": ""},
        {"name": "通达信板块信息", "url": ""},
        {"name": "通达信板块成分", "url": ""},
        {"name": "通达信板块行情", "url": ""},
        {"name": "榜单数据(开盘啦)", "url": ""},
        {"name": "题材数据(开盘啦)", "url": ""},
        {"name": "题材成分(开盘啦)", "url": ""},
        {"name": "MACD俱乐部", "desc": "技术指标讨论,公式编写教学", "url": "http://bbs.macd.cn/"},
        {"name": "360导航-财经网址", "desc": "聚合东方财富/和讯等头部入口", "url": "https://hao.360.com/sub/caijing_website_nav.html"},
        {"name": "123网址之家-财经导航", "desc": "覆盖期货/外汇/股票社区链接", "url": "https://www.1234wu.com/wz/90_1.html"}
    ],
    "dv_accounts": [
        {"name": "饭统戴老板", "desc": "长篇深度商业故事,洞察公司与经济史", "url": "https://weixin.sogou.com/weixin?type=1&query=%E9%A5%AD%E7%BB%9F%E6%88%B4%E8%80%81%E6%9D%BF"},
        {"name": "三折人生", "desc": "金融科普漫画,财经小白入门", "url": "https://weixin.sogou.com/weixin?type=1&query=%E4%B8%89%E6%8A%98%E4%BA%BA%E7%94%9F"},
        {"name": "券商中国", "desc": "证券时报旗下官媒,热点政策速递", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%88%B8%E5%95%86%E4%B8%AD%E5%9B%BD"},
        {"name": "咩咩说", "desc": "券商研究视角,宏观与行业思考", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%92%A9%E5%92%A9%E8%AF%B4"},
        {"name": "月风投资笔记", "desc": "私募经理吴悦风,宏观与个股解析", "url": "https://weixin.sogou.com/weixin?type=1&query=%E6%9C%88%E9%A3%8E%E6%8A%95%E8%B5%84%E7%AC%94%E8%AE%B0"},
        {"name": "英为财情", "desc": "全球行情+工具,美股/大宗商品深度", "url": "http://weixin.qq.com/r/nzhpcYvEHtZhrc8S922N"},
        {"name": "李迅雷金融与投资", "desc": "中泰证券首席,宏观策略观点", "url": "https://weixin.sogou.com/weixin?type=1&query=%E6%9D%8E%E8%BF%85%E9%9B%B7"},
        {"name": "定投十年赚十倍", "desc": "银行螺丝钉基金定投与估值表", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%AE%9A%E6%8A%95%E5%8D%81%E5%B9%B4%E8%B5%9A%E5%8D%81%E5%80%8D"},
        {"name": "图解金融", "desc": "图文并茂讲解金融知识", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%9B%BE%E8%A7%A3%E9%87%91%E8%9E%8D"},
        {"name": "金融街老裘", "desc": "财务研究与行业分析,偏个股基本面", "url": "https://weixin.sogou.com/weixin?type=1&query=%E9%87%91%E8%9E%8D%E8%A1%97%E8%80%81%E8%A3%98"}
    ],
    "ai_search_questions": []
}
# 全局设置matplotlib中文字体,避免字体警告
try:
    # 使用Windows系统常见的中文字体,避免使用不存在的字体
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'KaiTi', 'FangSong', 'Arial Unicode MS', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False
    # 禁用matplotlib字体查找警告
    warnings.filterwarnings('ignore', message='findfont: Font family.*not found', category=UserWarning)
    warnings.filterwarnings('ignore', message='Glyph.*missing from font', category=UserWarning)
except Exception:
    pass
try:
    import openpyxl
except ImportError:
    print("警告: openpyxl未安装,Excel导出功能可能不可用")
    openpyxl = None
# OCR功能已完全移除
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
# 全局变量
STOCK_NAMES_SET = None
STOCK_CODES_DICT = None
STOCK_NAME_TO_CODE = None
ETF_CACHE_REFRESHED = False
# 并发调用 load_stock_names() 时串行化,避免重复联网与全局字典竞态
STOCK_NAMES_LOAD_LOCK = threading.Lock()

# ==================== Phase 2: 全局变量注入到子模块 ====================
import logic.stock_names as _mod_stock_names
import data.snapshot as _mod_snapshot
import logic.dapan_fetcher as _mod_dapan
import logic.spot as _mod_spot
import logic.wordcloud as _mod_wordcloud
try:
    _mod_stock_names.AKSHARE_AVAILABLE = AKSHARE_AVAILABLE
    _mod_dapan.AKSHARE_AVAILABLE = AKSHARE_AVAILABLE
    _mod_spot.AKSHARE_AVAILABLE = AKSHARE_AVAILABLE
except NameError:
    pass
try:
    _mod_spot.TS_DEFAULT_TOKEN = TS_DEFAULT_TOKEN
except NameError:
    pass
# DapanMixin 需要的全局变量
try:
    import ui.tab_dapan as _mod_dapan_mixin
    _mod_dapan_mixin.AKSHARE_AVAILABLE = AKSHARE_AVAILABLE
    _mod_dapan_mixin.TS_AVAILABLE = TS_AVAILABLE
    _mod_dapan_mixin.D_DATA_DIR = D_DATA_DIR
except NameError:
    pass
# 延迟注入 STOCK_CODES_DICT (主类 __init__ 里才真正初始化)
_mod_stock_names.STOCK_CODES_DICT = STOCK_CODES_DICT
_mod_stock_names.STOCK_NAMES_SET = STOCK_NAMES_SET
_mod_stock_names.STOCK_NAME_TO_CODE = STOCK_NAME_TO_CODE
_mod_stock_names.ETF_CACHE_REFRESHED = ETF_CACHE_REFRESHED
_mod_stock_names.STOCK_NAMES_LOAD_LOCK = STOCK_NAMES_LOAD_LOCK
_mod_snapshot.STOCK_CODES_DICT = STOCK_CODES_DICT

# ==================== 数据库管理 ====================
# ==================== 淘股吧爬虫 ====================
# ==================== 韭研公社爬虫 ====================
# ==================== AI配置管理 ====================
# ETF数据获取功能已移除
# ETF热门数据获取功能已移除
# 龙虎榜相关功能已完全移除
# ETF相关功能已完全移除
# 股票5日分析功能已移除
# 均线位置分析功能已移除
# 添加全局缓存
# 东财分市场接口缓存:避免 stock_zh_a_spot_em 仅返回约一两百条时大部分代码匹配不到
# 一旦检测到 AKShare 数据链路失败,后续默认不再走 AKShare(优先稳定走 Tushare)
# 5日缓存函数已移除
# OCR相关函数已完全移除
# 重复的OCR函数已移除
# Phase 3: Mixin imports
from ui.tab_database import DatabaseMixin
from ui.tab_kelly import KellyMixin
from ui.tab_wordcloud import WordcloudMixin
from ui.tab_dapan import DapanMixin
from ui.tab_warning import WarningMixin
from ui.tab_cangwei import CangweiMixin
from ui.tab_wencai import WencaiMixin
from ui.tab_hot import HotMixin
from ui.tab_news import NewsMixin

# Phase 5: Bulk Mixin imports (indicator/config/analysis/db/stock_detail)
from ui.tab_indicator import IndicatorMixin
from ui.tab_config import ConfigMixin
from ui.tab_analysis import AnalysisMixin
from ui.tab_db_search import DbSearchMixin
from ui.tab_stock_detail import StockDetailMixin

# Phase 5b: More Mixins (screenshot/crawler/file_io/thread/format/holdings)
from ui.tab_screenshot import ScreenshotMixin
from ui.tab_crawler import CrawlerMixin
from ui.tab_file_io import FileIoMixin
from ui.tab_thread import ThreadMixin
from ui.tab_format import FormatMixin
from ui.tab_holdings import HoldingsMixin

# Phase 5c: Builders/Nav/Spider/Realtime/Checks/Math/Getters/Trade/EmoDeep/Token/Schedule/Buttons
from ui.tab_builders import BuildersMixin
from ui.tab_nav import NavMixin
from ui.tab_spider_reader import SpiderReaderMixin
from ui.tab_realtime import RealtimeMixin
from ui.tab_checks import ChecksMixin
from ui.tab_math import MathMixin
from ui.tab_getters import GettersMixin
from ui.tab_trade import TradeMixin
from ui.tab_emo_deep import EmoDeepMixin
from ui.tab_token import TokenMixin
from ui.tab_schedule import ScheduleMixin
from ui.tab_buttons import ButtonsMixin

from ui.tab_ai import AiMixin
from ui.tab_breadcrumb import BreadcrumbMixin
from ui.tab_default_config import DefaultConfigMixin
from ui.tab_export import ExportMixin
from ui.tab_finance import FinanceMixin
from ui.tab_inner_class import InnerClassMixin
from ui.tab_leader import LeaderMixin
from ui.tab_money_flow import MoneyFlowMixin
from ui.tab_nav2 import Nav2Mixin
from ui.tab_pipeline import PipelineMixin
from ui.tab_render import RenderMixin
from ui.tab_rest import RestMixin
from ui.tab_toplevel import ToplevelMixin
from ui.tab_web import WebMixin

class StockKeywordAnalyzerGUI(AiMixin, AnalysisMixin, BreadcrumbMixin, BuildersMixin, ButtonsMixin, CangweiMixin, ChecksMixin, ConfigMixin, CrawlerMixin, DapanMixin, DatabaseMixin, DbSearchMixin, DefaultConfigMixin, EmoDeepMixin, ExportMixin, FileIoMixin, FinanceMixin, FormatMixin, GettersMixin, HoldingsMixin, HotMixin, IndicatorMixin, InnerClassMixin, KellyMixin, LeaderMixin, MathMixin, MoneyFlowMixin, NavMixin, Nav2Mixin, NewsMixin, PipelineMixin, RealtimeMixin, RenderMixin, RestMixin, ScheduleMixin, ScreenshotMixin, SpiderReaderMixin, StockDetailMixin, ThreadMixin, TokenMixin, ToplevelMixin, TradeMixin, WarningMixin, WebMixin, WencaiMixin, WordcloudMixin):

    def __init__(self, root):
        self.root = root
        # 安全更新窗口方法 - macOS上直接跳过
        def _safe_update():
            try:
                if self.root and self.root.winfo_exists():
                    if sys.platform != "darwin":
                        self.root.tk.call('update')
                    return True
                return False
            except Exception:
                return False
        def _safe_update_idletasks():
            try:
                if self.root and self.root.winfo_exists():
                    if sys.platform != "darwin":
                        self.root.tk.call('update', 'idletasks')
                    return True
                return False
            except Exception:
                return False
        self._safe_update = _safe_update
        self._safe_update_idletasks = _safe_update_idletasks
        # 弹窗字体(相对系统默认 +2 为初值,写入 ai_config.json 的 popup_font_size)
        self._popup_font_min = 8
        self._popup_font_max = 28
        self._popup_windows = []
        # Skill 定时任务管理(多任务 + 持久化)
        self._scheduled_skills = []       # [{id, skill_name, params:[], times:[str], active:bool, last_fired:{date:set(time)}, notes:str}]
        self._skill_scheduler_after_id = None
        self._skill_scheduler_log = []    # [time_str, msg] 最近执行日志
        self._skill_schedule_path = os.path.expanduser("~/.qclaw/skill_schedule.json")
        self._load_scheduled_skills()
        # 初始化数据库(必须在界面创建前完成,因为后续操作可能依赖数据库)
        init_database()
        # 初始化AI配置管理器(快速操作,先完成)
        self.ai_config_manager = AIConfigManager()
        try:
            import tkinter.font as _tkfont_cfg
            _bdf0 = _tkfont_cfg.nametofont("TkDefaultFont")
            _p0 = int(_bdf0["size"]) + 2
        except Exception:
            _p0 = 11
        try:
            _svp = self.ai_config_manager.config.get("popup_font_size")
            if _svp is not None:
                _p0 = int(_svp)
        except Exception:
            pass
        _p0 = max(self._popup_font_min, min(self._popup_font_max, _p0))
        # 创建 Tkinter 变量
        self.popup_font_size_var = tk.IntVar(value=_p0)
        # 同花顺情绪指数:上行/震荡/下行(与开新仓流程中「1日线往上」「在1日线上」勾选框联动;每半小时弹窗提醒)
        _ths_t = self.ai_config_manager.config.get("ths_sentiment_trend", "震荡")
        if _ths_t not in ("上行", "震荡", "下行"):
            _ths_t = "震荡"
        self.ths_sentiment_trend_var = tk.StringVar(value=_ths_t)
        self.sentiment_index_ma1_uptrend_var = tk.BooleanVar(value=False)
        self.sentiment_index_ma1_above_var = tk.BooleanVar(value=False)
        self.sentiment_index_check_var = tk.BooleanVar(value=False)
        self._apply_ths_sentiment_trend_to_checkboxes(self.ths_sentiment_trend_var.get())
        self.sentiment_index_ma1_uptrend_var.trace_add("write", lambda *args: self._update_sentiment_index_check_coord())
        self.sentiment_index_ma1_above_var.trace_add("write", lambda *args: self._update_sentiment_index_check_coord())
        # 同花顺情绪指数提醒弹窗引用:最多同时并存 2 个,超出则停止弹出,待用户清除后再恢复
        self._ths_reminder_windows = []
        # 创建菜单栏
        self.menubar = tk.Menu(self.root)
        # 添加设置菜单
        settings_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="修改窗口标题", command=self._edit_window_title)
        # 应用菜单栏
        try:
            self.root.config(menu=self.menubar)
        except Exception:
            pass
        # 翻译配置(参照 translator_gui.py)
        self.translation_engines = {
            "百度翻译": {
                "api_url": "https://fanyi-api.baidu.com/api/trans/vip/translate",
                "app_id": "20191105000352960",
                "app_key": "ZKPLQb3WUi1NJ0TnhcZN"
            },
            "有道翻译": {
                "api_url": "https://openapi.youdao.com/api",
                "app_id": "3d7d5287500ee1ef",
                "app_key": "U4uLG6Ar04XzVj8ajJ3JTkW74QcRWcC7"
            },
            "Google翻译": {
                "api_url": "https://translation.googleapis.com/language/translate/v2",
                "api_key": "YOUR_GOOGLE_API_KEY"
            }
        }
        self.languages = {
            "中文": "zh",
            "英语": "en",
            "日语": "ja",
            "韩语": "ko",
            "法语": "fr",
            "德语": "de",
            "西班牙语": "es",
            "俄语": "ru",
            "阿拉伯语": "ar",
            "葡萄牙语": "pt",
            "意大利语": "it",
            "泰语": "th",
            "越南语": "vi",
            "印尼语": "id",
            "马来语": "ms"
        }
        self.translation_stop_flag = False
        # 线程同步事件
        self.batch_crawl_event = threading.Event()
        self.batch_crawl_event.set()
        self.one_click_analyze_event = threading.Event()
        self.one_click_analyze_event.set()
        self.one_click_news_event = threading.Event()
        self.one_click_news_event.set()
        self.pipeline_lock = threading.Lock()
        self.ts_client = None
        # 从配置文件读取Tushare配置
        tushare_config = self.ai_config_manager.get_tushare_config()
        self.ts_token = tushare_config.get("token") or TS_DEFAULT_TOKEN
        self.ts_account = tushare_config.get("account") or TS_DEFAULT_ACCOUNT
        # 初始化爬虫(延迟初始化,避免阻塞界面显示)
        self.taoguba_crawler = None
        self.jiuyangongshe_crawler = None
        self.market_nav_config = {}
        self.crawler_config = {}
        self.managed_stocks = []           # 当前管理的股票列表
        self.managed_stock_names = []      # 供开新仓下拉框使用的名称缓存
        self.holding_stocks = [None] * 80  # 存储80个持仓股,每个元素为(stock_name, stock_code)或None
        self.holding_labels = []           # 存储持仓股的标签(在UI创建时填充)
        self.holding_check_running = False # 持仓自动检测运行状态
        self.holding_check_thread = None   # 持仓自动检测线程
        self.holding_kelly_results = [None] * 80  # 存储80个持仓股的凯利公式结果,每个元素为{'ratio': float, 'b': float, 'p': float, 'ma_status': dict}
        self.holding_low_diff_results = [None] * 80  # 存储80个持仓股的5日最低点差%结果,每个元素为{'low_diff_pct': float}
        # 新增4个持仓组(持仓2、持仓3、持仓4、持仓5),都支持80个股票
        # 持仓2:龙头股
        self.holding_stocks_2 = [None] * 80
        self.holding_labels_2 = []
        self.holding_kelly_results_2 = [None] * 80
        self.holding_low_diff_results_2 = [None] * 80
        # 持仓3:15Min
        self.holding_stocks_3 = [None] * 80
        self.holding_labels_3 = []
        self.holding_kelly_results_3 = [None] * 80
        self.holding_low_diff_results_3 = [None] * 80
        # 持仓4:Main
        self.holding_stocks_4 = [None] * 80
        self.holding_labels_4 = []
        self.holding_kelly_results_4 = [None] * 80
        self.holding_low_diff_results_4 = [None] * 80
        # 持仓历史股:支持80个股票,但标签页只显示20个
        self.holding_stocks_5 = [None] * 80  # 扩展到80个
        self.holding_labels_5 = []
        self.holding_kelly_results_5 = [None] * 80  # 扩展到80个
        self.holding_low_diff_results_5 = [None] * 80
        # 持仓6:韭研标签页
        self.holding_stocks_6 = [None] * 80
        self.holding_labels_6 = []
        self.holding_kelly_results_6 = [None] * 80
        self.holding_low_diff_results_6 = [None] * 80
        # 持仓7-14:持仓1-持仓8(用于自动导入板块龙头股)
        for i in range(7, 15):
            setattr(self, f'holding_stocks_{i}', [None] * 80)
            setattr(self, f'holding_labels_{i}', [])
            setattr(self, f'holding_kelly_results_{i}', [None] * 80)
            setattr(self, f'holding_low_diff_results_{i}', [None] * 80)
        # ========== 持仓股振幅监控相关 ==========
        # 价格历史记录:{stock_code: [(timestamp, price, high, low), ...]}
        # 只保留1小时内的数据
        self.holding_price_history = {}  # 存储所有持仓股的价格历史
        self.holding_amplitude_monitor_running = False  # 监控运行状态
        self.holding_amplitude_monitor_thread = None  # 监控线程
        self.holding_amplitude_alerts = set()  # 已报警的股票(避免重复报警)
        self.holding_amplitude_check_interval = 60  # 检查间隔(秒),默认60秒
        self.holding_ma_alerts = set()  # 已报警的均线预警(避免重复报警)
        self.last_market_data = None  # 存储上次获取的市场数据
        self.market_data_update_interval = 300  # 市场数据更新间隔(秒),默认5分钟
        self.last_market_data_time = 0  # 上次获取市场数据的时间
        self.amplitude_alert_enabled = False  # 振幅预警开关(默认关闭)
        self.ma_alert_enabled = False  # 均线预警开关(默认关闭)
        self.break_ma1_alert_enabled = False  # 破1日预警开关(默认关闭)
        self.break_ma5_alert_enabled = False  # 破5日预警开关(默认关闭)
        self.break_ma20_alert_enabled = False  # 破20日预警开关(默认关闭)
        self.sector_sentiment_monitor_enabled = False  # 持仓情绪监测开关(默认关闭)
        self.sector_sentiment_monitor_running = False  # 持仓情绪监测运行状态
        self.sector_sentiment_window = None  # 持仓情绪监测窗口
        self.sos_alert_window = None  # SOS预警窗口
        self.sos_alert_timer = None  # SOS预警定时器
        self._emotion_lock_overlay = None  # 情绪下行时全屏拦截层
        self._emotion_lock_suppressed = False  # 密码解锁后为 True,直至情绪周期实际切换
        self._emotion_lock_prev_cycle = None
        self.sector_index_list = []  # 板块指数列表(最大30个)
        self.top16_sector_names = []  # 点击"查看"时获取的同花顺涨幅最大前16板块名;持仓1-8各显示2个
        self.holding_stock_monitor_enabled = False  # 持仓股监测开关(默认关闭)
        self.holding_stock_monitor_running = False  # 持仓股监测运行状态
        self.holding_stock_monitor_window = None  # 持仓股监测窗口
        self.main_below_ma1_alerted = set()  # Main持仓股低于1日线已报警记录(避免重复弹窗)
        self.hot_stock_15min_monitor_enabled = False  # 15分钟热门股监测开关(默认关闭)
        self.hot_stock_15min_monitor_running = False  # 15分钟热门股监测运行状态
        self.hot_stock_15min_monitor_window = None  # 15分钟热门股监测窗口
        self.holding_ma_alerts = set()  # 已报警的均线预警(避免重复报警)
        self.holding_break_ma_alerts = set()  # 已报警的破均线预警(避免重复报警)
        # ========== 凯利公式配置加载(程序启动时自动读取,用于仓位计算)==========
        # 从配置文件中读取凯利公式配置(盈亏比b和胜率p),程序启动时自动加载
        # 这样在仓位计算时不需要打开其他模块,可以直接使用已加载的配置
        self.kelly_config = self.ai_config_manager.config.get("kelly_config", {}).copy()  # 使用copy避免引用问题
        # 定义默认配置(与凯利公式设置按钮中的配置保持一致)
        default_configs = {
            "True_True_True_True": {"b": 3.0, "p": 0.8},
            "False_True_True_True": {"b": 3.0, "p": 0.8},
            "False_False_True_True": {"b": 3.0, "p": 0.7},
            "False_False_False_True": {"b": 2.0, "p": 0.5},
            "below_ma20": {"b": 0.3, "p": 0.3},
        }
        # 如果配置表中没有这些配置项,将默认值写入配置表(确保所有值都从配置表读取)
        config_updated = False
        for key, default_values in default_configs.items():
            if key not in self.kelly_config:
                self.kelly_config[key] = default_values.copy()
                config_updated = True
        # 如果更新了配置,保存到配置文件
        if config_updated:
            self.ai_config_manager.config["kelly_config"] = self.kelly_config.copy()
            self.ai_config_manager.save_config()
            print("[初始化] 已将默认凯利配置写入配置文件")
        # 打印加载的配置信息,确认配置已在程序启动时成功加载
        print(f"[初始化] 凯利公式配置已自动加载(程序启动时读取): {self.kelly_config}")
        print(f"[初始化] 配置项数量: {len(self.kelly_config)},仓位计算可直接使用此配置,无需打开其他模块")
        # 加载选择框状态配置
        self.crawler_checkbox_states = self.ai_config_manager.config.get("crawler_checkbox_states", {})
        self.market_nav_checkbox_states = self.ai_config_manager.config.get("market_nav_checkbox_states", {})
        self.auto_collect_enabled = self.ai_config_manager.config.get("auto_collect_enabled", False)
        # 如果自动化采集已开启,延迟启动(等待界面加载完成)
        if self.auto_collect_enabled:
            self.root.after(30000, self._start_auto_collect)  # 延后 30s  # 5秒后启动
        self._nav_editor_window = None
        self._stock_mgmt_window = None
        self.pending_waiting_reason = None
        # 全局 ttk 字号略放大,按钮/标签更易辨认(macOS Aqua 下过小或与背景对比弱时尤甚)
        try:
            _style = ttk.Style()
            # macOS 默认 aqua 主题对 ttk 颜色自定义支持很弱,常见现象是按钮像"无底色/无文字色"。
            # 切到 clam 后可稳定应用 foreground/background。
            if sys.platform == "darwin":
                try:
                    if _style.theme_use() == "aqua":
                        _style.theme_use("clam")
                except Exception:
                    pass
            if sys.platform == "darwin":
                _ui_font = ("PingFang SC", 12)
            else:
                _ui_font = ("Microsoft YaHei UI", 12)
            _style.configure(".", font=_ui_font)
            _style.configure("TButton", font=_ui_font)
            _style.configure("TLabel", font=_ui_font)
            _style.configure("TCheckbutton", font=_ui_font)
            _style.configure("TRadiobutton", font=_ui_font)
            _style.configure("TNotebook.Tab", font=_ui_font)
            _style.configure("TCombobox", font=_ui_font)
            _style.configure("TButton", foreground="#111827", background="#e5e7eb", padding=(5, 3))
            # 与自持仓标签页下方股票格子 tk.Label 一致:TkDefaultFont 13
            _style.configure(
                "HoldingToolbar.TButton",
                font=("TkDefaultFont", 13),
                foreground="#111827",
                background="#e5e7eb",
                padding=(2, 2),
            )
            _style.map(
                "HoldingToolbar.TButton",
                background=[("active", "#d1d5db"), ("pressed", "#9ca3af"), ("disabled", "#f3f4f6")],
                foreground=[
                    ("active", "#000000"),
                    ("pressed", "#000000"),
                    ("disabled", "#000000"),
                ],
            )
            _style.map(
                "TButton",
                background=[("active", "#d1d5db"), ("pressed", "#9ca3af"), ("disabled", "#f3f4f6")],
                foreground=[
                    ("active", "#000000"),
                    ("pressed", "#000000"),
                    ("disabled", "#000000"),
                ],
            )
            _style.configure("TLabel", foreground="#111827")
            # tk.Button 也统一黑色文字(部分窗口用了 tk.Button 而非 ttk.Button)
            self.root.option_add("*Button.Foreground", "#000000")
        except Exception:
            pass
        # 创建主框架(先创建界面,让用户看到);左右列宽约 3:1,左侧按钮多留横向空间
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=8)
        main_frame.columnconfigure(0, weight=6, uniform="mw")
        main_frame.columnconfigure(1, weight=4, uniform="mw")
        main_frame.rowconfigure(0, weight=1)
        # 立即更新界面,让用户看到窗口正在加载
        self._safe_update()
        self._safe_update_idletasks()
        # 左侧框架 - 输入区域(网格第 0 列,占 60% 宽度)
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        # 仓位/交易标签页控件框(共用一块位置,可以切换,调整高度)
        self.position_trading_notebook = ttk.Notebook(left_frame)
        # 垂直方向也要参与分配,否则「龙头股」等标签页里多行股票格子在部分系统上高度为 0,中间一片空白
        self.position_trading_notebook.pack(fill=tk.BOTH, expand=False, pady=(0, 1))
        # 高度与持仓内容匹配为主,腾出左侧下方工具条/快速爬取/导航可视区
        self.position_trading_notebook.configure(height=262)
        # ============ 🗺️ 大盘分析标签页 (重写版: 水温计+情绪地图+板块) ============
        dapan_tab = ttk.Frame(self.position_trading_notebook, padding=3)
        self.position_trading_notebook.add(dapan_tab, text="🗺️ 大盘分析")
        self._dapan_hld_col = {"red": "#C62828", "yellow": "#F57F17", "green": "#2E7D32", "gray": "#BDBDBD"}

        # ============ 顶部: 红绿灯 + 水温计 + 情绪周期 (一行) ============
        top_bar = tk.Frame(dapan_tab, bg="#1A237E"); top_bar.pack(fill=tk.X, pady=(0, 3))
        # 左: 红绿灯文字
        tk.Label(top_bar, text="🇨🇳 A股综合", bg="#1A237E", fg="white",
                 font=("", 11, "bold")).pack(side=tk.LEFT, padx=8, pady=3)
        hld_canvas = tk.Canvas(top_bar, width=28, height=28, bg="#1A237E", highlightthickness=0)
        hld_canvas.pack(side=tk.LEFT, padx=2); hld_canvas.create_oval(3,3,25,25, fill="#BDBDBD", outline="#424242", width=2)
        self._dapan_hld_canvas = hld_canvas
        self._hm_scores_cache = {}  # 游资心法得分缓存
        self._dapan_score_var = tk.StringVar(value="--")
        tk.Label(top_bar, textvariable=self._dapan_score_var, bg="#1A237E", fg="white",
                 font=("", 13, "bold")).pack(side=tk.LEFT, padx=4)
        self._dapan_level_var = tk.StringVar(value="⏳ 等待加载")
        tk.Label(top_bar, textvariable=self._dapan_level_var, bg="#1A237E", fg="#FFD54F",
                 font=("", 9, "bold")).pack(side=tk.LEFT, padx=4)

        # 中: 水温计 (垂直Canvas, 显示推荐仓位%)
        term_frame = tk.Frame(top_bar, bg="#1A237E"); term_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(term_frame, text="推荐仓位", bg="#1A237E", fg="#FFD54F",
                 font=("", 8)).pack(side=tk.LEFT, padx=(0, 2))
        term_canvas = tk.Canvas(term_frame, width=22, height=60, bg="#1A237E", highlightthickness=0)
        term_canvas.pack(side=tk.LEFT)
        # 画空温度计
        term_canvas.create_rectangle(8, 4, 14, 50, fill="#37474F", outline="#78909C", width=1)
        term_canvas.create_oval(6, 48, 16, 58, fill="#37474F", outline="#78909C", width=1)
        term_canvas.create_rectangle(10, 6, 12, 48, fill="#455A64", outline="")  # 默认空
        term_canvas.create_oval(8, 50, 14, 56, fill="#78909C", outline="")
        self._dapan_term_canvas = term_canvas
        self._dapan_term_pct_var = tk.StringVar(value="--%")
        tk.Label(term_frame, textvariable=self._dapan_term_pct_var, bg="#1A237E", fg="#FFD54F",
                 font=("", 12, "bold")).pack(side=tk.LEFT, padx=(0, 2))

        # 右: 情绪周期明确大字
        emo_big = tk.Frame(top_bar, bg="#1A237E"); emo_big.pack(side=tk.LEFT, padx=10)
        tk.Label(emo_big, text="🌊 情绪周期", bg="#1A237E", fg="#FFD54F", font=("", 8)).pack()
        self._dapan_emo_var = tk.StringVar(value="⏳ --")
        emo_lbl = tk.Label(emo_big, textvariable=self._dapan_emo_var, bg="#1A237E", fg="#FF6F00",
                           font=("", 14, "bold"))
        emo_lbl.pack()
        self._dapan_emo_lbl = emo_lbl

        # 中: 盘中警告小条 (实时指数+涨跌数+优良差危险)
        alert_frame = tk.Frame(top_bar, bg="#1A237E"); alert_frame.pack(side=tk.LEFT, padx=(12, 0))
        tk.Label(alert_frame, text="⚠️ 盘中", bg="#1A237E", fg="#FF8A65", font=("", 8)).pack(anchor="w")
        self._dapan_alert_var = tk.StringVar(value="⏳ 加载中")
        self._dapan_alert_lbl = tk.Label(alert_frame, textvariable=self._dapan_alert_var,
                                         bg="#1A237E", fg="#E0E0E0", font=("", 10, "bold"),
                                         anchor="w", justify=tk.LEFT)
        self._dapan_alert_lbl.pack()

        # 最右: 涨跌家数 + 刷新
        self._dapan_updn_var = tk.StringVar(value="")
        updn_frame = tk.Frame(top_bar, bg="#1A237E"); updn_frame.pack(side=tk.RIGHT)
        tk.Label(updn_frame, textvariable=self._dapan_updn_var, bg="#1A237E", fg="#E3F2FD",
                 font=("", 9)).pack(side=tk.RIGHT, padx=4)
        self._dapan_stop_btn = tk.Button(top_bar, text="⏹️", bg="#555", fg="white",
                                          font=("", 9, "bold"), padx=6, pady=0,
                                          cursor="hand2", state="disabled",
                                          command=lambda: self._dapan_stop_event.set())
        self._dapan_stop_btn.pack(side=tk.RIGHT, padx=2)
        tk.Button(top_bar, text="🔄", bg="#C62828", fg="white", font=("", 9, "bold"),
                  padx=6, pady=0, cursor="hand2",
                  command=lambda: self._bg_load_dapan()).pack(side=tk.RIGHT, padx=6)

        # ============ 10日情绪分 + 涨跌幅趋势条 (紧凑 Canvas) ============
        trend_bar = tk.Frame(dapan_tab, bg="#ECEFF1", height=160)
        trend_bar.pack(fill=tk.X, pady=(0, 3))
        trend_bar.pack_propagate(False)
        self._dapan_trend_canvas = tk.Canvas(trend_bar, bg="#ECEFF1", height=160,
                                              highlightthickness=1, highlightbackground="#B0BEC5")
        self._dapan_trend_canvas.pack(fill=tk.BOTH, expand=True)
        # 缓存 trend10 数据, 供 Canvas resize 时自动重绘
        self._dapan_trend_data = None
        self._dapan_trend_canvas.bind("<Configure>", lambda e: self._redraw_trend_if_width_ok())
        # 默认占位提示
        self._dapan_trend_canvas.create_text(200, 36, text="⏳ 加载最近10日趋势中...",
                                              fill="#90A4AE", font=("", 9))

        # ============ 情绪阶段可视化条 (明确标出当前位置) ============
        emo_strip = tk.Frame(dapan_tab, bg="#424242", height=26); emo_strip.pack(fill=tk.X, pady=(0, 3))
        emo_strip.pack_propagate(False)
        self._dapan_emo_strip_canvas = tk.Canvas(emo_strip, bg="#424242", height=26,
                                                  highlightthickness=0)
        self._dapan_emo_strip_canvas.pack(fill=tk.BOTH, expand=True)
        # 先画默认7阶段
        _emo_stages_def = [("冰点", "#2E7D32"), ("启动", "#F57F17"),
                           ("发酵", "#FF6F00"), ("高潮", "#C62828"),
                           ("分歧", "#6A1B9A"), ("退潮", "#455A64"),
                           ("冰点", "#2E7D32")]
        _seg_w = 90
        for _si, (_sn, _sc) in enumerate(_emo_stages_def):
            _x1 = _si * _seg_w + 2; _x2 = _x1 + _seg_w - 2
            self._dapan_emo_strip_canvas.create_rectangle(_x1, 2, _x2, 24, fill=_sc, outline="#555", width=1)
            self._col_text = "#E0E0E0"
            self._dapan_emo_strip_canvas.create_text((_x1+_x2)/2, 13, text=_sn, fill="white", font=("", 8, "bold"))

        # ============ 主区: 左四维度 + 右板块 ============
        # 自动触发首次加载 — 已禁用, 避免后台线程抢 GIL 卡死 UI
        # 用户切到大盘页点右上角"刷新"按钮手动触发
        # try:
        #     self.root.after(1500, self._bg_load_dapan)
        # except Exception as e:
        #     print(f"[大盘分析] 自动加载调度失败: {e}")

        # ✅ 启动时秒出旧数据: 读本地 snapshot → 没有 snapshot 则从 emo_history 渲染趋势
        try:
            self._try_load_dapan_snapshot()
        except Exception as _e_load:
            print(f"[大盘] snapshot 加载异常: {_e_load}", flush=True)

        # 仓位标签页
        position_tab = ttk.Frame(self.position_trading_notebook, padding=2)
        self.position_trading_notebook.add(position_tab, text="仓位")
        # 仓位分析框(在仓位标签页中,调整padding使其更紧凑)
        position_frame = ttk.LabelFrame(position_tab, text="仓位分析", padding=3)
        position_frame.pack(fill=tk.X, expand=False)
        # 定义选项和分值
        position_options = ["太阳", "晴天", "阴天", "下雨", "大雨", "暴雨", "飓风"]
        position_scores = {"太阳": 10, "晴天": 7, "阴天": 4, "下雨": 1, "大雨": -2, "暴雨": -5, "飓风": -8}
        # 三个下拉框(同一行,紧凑布局)
        combo_frame = ttk.Frame(position_frame)
        combo_frame.pack(fill=tk.X, pady=(0, 3))
        # 三个下拉框变量
        emotion_var = tk.StringVar(value="阴天")
        v_judge_var = tk.StringVar(value="阴天")
        yesterday_var = tk.StringVar(value="阴天")
        # 情绪价值下拉框
        ttk.Label(combo_frame, text="情绪:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        emotion_combo = ttk.Combobox(combo_frame, textvariable=emotion_var, values=position_options,
                                    state="readonly", width=7)
        emotion_combo.pack(side=tk.LEFT, padx=(0, 3))
        # 大V判断下拉框
        ttk.Label(combo_frame, text="大V:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        v_judge_combo = ttk.Combobox(combo_frame, textvariable=v_judge_var, values=position_options,
                                     state="readonly", width=7)
        v_judge_combo.pack(side=tk.LEFT, padx=(0, 3))
        # 昨日盘况下拉框
        ttk.Label(combo_frame, text="昨日:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        yesterday_combo = ttk.Combobox(combo_frame, textvariable=yesterday_var, values=position_options,
                                     state="readonly", width=7)
        yesterday_combo.pack(side=tk.LEFT, padx=(0, 3))
        # 安全流动利润按钮(整合三个分析界面)
        safety_liquidity_profit_button = ttk.Button(combo_frame, text="🛡️💧📈 安全流动利润",
                                                     command=self.show_safety_liquidity_profit_analysis, width=15)
        safety_liquidity_profit_button.pack(side=tk.LEFT, padx=(0, 3))
        # 基本面、技术面、情绪面下拉框(放在安全流动利润按钮后面)
        ttk.Label(combo_frame, text="基本面:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        fundamental_var = tk.StringVar(value="20")
        fundamental_values = [str(i) for i in range(31)]  # 0-30
        fundamental_combo = ttk.Combobox(combo_frame, textvariable=fundamental_var, values=fundamental_values,
                                       state="readonly", width=5)
        fundamental_combo.pack(side=tk.LEFT, padx=(0, 3))
        ttk.Label(combo_frame, text="技术面:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        technical_var = tk.StringVar(value="20")
        technical_values = [str(i) for i in range(31)]  # 0-30
        technical_combo = ttk.Combobox(combo_frame, textvariable=technical_var, values=technical_values,
                                     state="readonly", width=5)
        technical_combo.pack(side=tk.LEFT, padx=(0, 3))
        ttk.Label(combo_frame, text="情绪面:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        sentiment_var = tk.StringVar(value="20")
        sentiment_values = [str(i) for i in range(31)]  # 0-30
        sentiment_combo = ttk.Combobox(combo_frame, textvariable=sentiment_var, values=sentiment_values,
                                     state="readonly", width=5)
        sentiment_combo.pack(side=tk.LEFT)
        self.fundamental_var = fundamental_var
        self.technical_var = technical_var
        self.sentiment_var = sentiment_var
        # 关于做T下拉框(禁用状态)
        t_trading_frame = ttk.Frame(position_frame)
        t_trading_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(t_trading_frame, text="做T:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        t_trading_var = tk.StringVar(value="")
        t_trading_combo = ttk.Combobox(t_trading_frame, textvariable=t_trading_var,
                                       values=["下行趋势 不可以做T", "谨慎做T", "上行趋势 可以做T"],
                                       state="disabled", width=18)
        t_trading_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # 开新仓下拉框和按钮
        new_position_frame = ttk.Frame(position_frame)
        new_position_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(new_position_frame, text="2开新仓:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        new_position_var = tk.StringVar(value="禁止开新仓")
        new_position_combo = ttk.Combobox(new_position_frame, textvariable=new_position_var,
                                          values=["禁止开新仓", "可以开新仓"],
                                          state="readonly", width=18)
        new_position_combo.pack(side=tk.LEFT, padx=(0, 5))
        # 开新仓按钮组(初始状态为禁用)
        new_position_button = ttk.Button(new_position_frame, text="开龙头新仓", state="disabled")
        new_position_button.pack(side=tk.LEFT, padx=(0, 5))
        new_position_button2 = ttk.Button(new_position_frame, text="开强势股新仓", state="disabled")
        new_position_button2.pack(side=tk.LEFT, padx=(0, 5))
        new_position_button3 = ttk.Button(new_position_frame, text="开绩优股新仓", state="disabled")
        new_position_button3.pack(side=tk.LEFT, padx=(0, 5))
        new_position_button4 = ttk.Button(new_position_frame, text="开朋友新仓", state="disabled")
        new_position_button4.pack(side=tk.LEFT, padx=(0, 5))
        new_position_button5 = ttk.Button(new_position_frame, text="开均值回归新仓", state="disabled")
        new_position_button5.pack(side=tk.LEFT, padx=(0, 5))
        self.new_position_button = new_position_button
        self.new_position_button2 = new_position_button2
        self.new_position_button3 = new_position_button3
        self.new_position_button4 = new_position_button4
        self.new_position_button5 = new_position_button5
        # 移除这些按钮,它们将移到右侧的交易标签页中
        # 标注提示(紧凑)
        note_label = ttk.Label(position_frame, text="注:具体T的仓位请按照凯利公式计算执行",
                              font=("TkDefaultFont", 7), foreground="gray")
        note_label.pack(anchor=tk.W, pady=(0, 2))
        # 结果显示区域(紧凑)
        result_frame = ttk.Frame(position_frame)
        result_frame.pack(fill=tk.X)
        # 结果标签
        result_label = ttk.Label(result_frame, text="仓位:", font=("TkDefaultFont", 8, "bold"))
        result_label.pack(side=tk.LEFT, padx=(0, 3))
        # 仓位百分比显示
        position_result_var = tk.StringVar(value="+0%")
        position_result_label = ttk.Label(result_frame, textvariable=position_result_var,
                                         font=("TkDefaultFont", 8))
        position_result_label.pack(side=tk.LEFT, padx=(0, 3))
        # 颜色指示灯(Canvas,紧凑)
        light_canvas = tk.Canvas(result_frame, width=25, height=25, highlightthickness=1,
                                highlightbackground="gray")
        light_canvas.pack(side=tk.LEFT, padx=(0, 3))
        # 总分值显示(基本面+技术面+情绪面)
        total_score_var = tk.StringVar(value="总分: 0")
        self.total_score_var = total_score_var  # 保存为实例变量,供持仓检测使用
        total_score_label = ttk.Label(result_frame, textvariable=total_score_var,
                                     font=("TkDefaultFont", 8, "bold"), foreground="blue")
        total_score_label.pack(side=tk.LEFT, padx=(0, 10))
        # 警世通言功能区域
        warning_frame = ttk.Frame(result_frame)
        warning_frame.pack(side=tk.LEFT, padx=(0, 5))
        # 警世通言下拉框
        warning_type_var = tk.StringVar(value="失败")
        warning_combo = ttk.Combobox(warning_frame, textvariable=warning_type_var,
                                     values=["失败", "成功", "醒悟"],
                                     state="readonly", width=6)
        warning_combo.pack(side=tk.LEFT, padx=(0, 3))
        # 警世通言按钮
        def create_warning_tab():
            """创建警世通言标签页"""
            try:
                warning_type = warning_type_var.get()
                if not warning_type:
                    messagebox.showwarning("警告", "请选择警世通言类型")
                    return
                # 生成标签页名称:警示+下拉框文字+时间
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tab_name = f"警示{warning_type}{current_time}"
                # 创建新标签页
                tab_id = self.create_text_tab(tab_name)
                # 获取新创建的文本框
                text_widget = self.text_widgets[tab_id]['widget']
                # 添加初始内容
                initial_content = f"【警世通言 - {warning_type}】\n"
                initial_content += f"时间:{current_time}\n"
                initial_content += f"类型:{warning_type}\n"
                initial_content += "="*50 + "\n\n"
                initial_content += "请在此输入警世通言内容...\n"
                text_widget.insert("1.0", initial_content)
                # 不自动保存到资讯DB,只创建编辑标签页
                # 用户可以通过"保存到资讯DB"按钮手动保存
                # 更新最近记录显示
                self.update_warning_recent_records()
            except Exception as e:
                messagebox.showerror("错误", f"创建警世通言标签页失败:{e}")
        warning_button = ttk.Button(warning_frame, text="警世通言", command=create_warning_tab)
        warning_button.pack(side=tk.LEFT, padx=(0, 5))
        # 警示浏览按钮
        def browse_warnings():
            """浏览警示记录"""
            browse_news_records("警示")
        warning_browse_button = ttk.Button(warning_frame, text="警示", command=browse_warnings)
        warning_browse_button.pack(side=tk.LEFT, padx=(0, 5))
        # 开新仓记录浏览按钮
        def browse_new_position_records():
            """浏览开新仓记录"""
            browse_news_records("开新仓记录")
        new_position_browse_button = ttk.Button(warning_frame, text="开新仓记录", command=browse_new_position_records)
        new_position_browse_button.pack(side=tk.LEFT, padx=(0, 5))
        # 最近三条记录显示区域
        recent_frame = ttk.Frame(result_frame)
        recent_frame.pack(side=tk.LEFT)
        def get_recent_warning_records():
            """获取最近三条警世通言记录"""
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT tab_name, content, created_at
                    FROM news_info
                    WHERE tab_name LIKE '警示%'
                    ORDER BY created_at DESC
                    LIMIT 3
                ''')
                records = cursor.fetchall()
                conn.close()
                return records
            except Exception as e:
                print(f"获取最近警世通言记录失败: {e}")
                return []
        def show_warning_popup(content, title):
            """显示警世通言弹出框,并在预警内容下方显示股票逻辑"""
            popup = self._toplevel(self.root)
            popup.title(title)
            popup.geometry("800x700")
            # 创建文本框显示内容
            text_widget = tk.Text(popup, font=("Microsoft YaHei", 14), wrap=tk.WORD)
            scrollbar = tk.Scrollbar(popup, orient=tk.VERTICAL, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            # 配置文本标签样式
            text_widget.tag_configure("warning", foreground="red", font=("Microsoft YaHei", 14))
            text_widget.tag_configure("logic_title", foreground="blue", font=("Microsoft YaHei", 14, "bold"))
            text_widget.tag_configure("logic_content", foreground="black", font=("Microsoft YaHei", 13))
            text_widget.tag_configure("separator", foreground="gray", font=("Microsoft YaHei", 13))
            # 插入预警内容(使用红色标签)
            text_widget.insert("1.0", content, "warning")
            # 从预警内容中提取股票名称
            try:
                stock_names_list, _ = extract_stock_names(content)
                if stock_names_list:
                    # 去重,只保留纯股票名称(去掉代码部分)
                    unique_stocks = []
                    seen_names = set()
                    for stock in stock_names_list:
                        # 提取纯股票名称(去掉代码和括号)
                        if '(' in stock:
                            name = stock.split('(')[1].rstrip(')')
                        else:
                            name = stock
                        # 只保留2-6个中文字符的股票名称
                        if len(name) >= 2 and len(name) <= 6 and name not in seen_names:
                            unique_stocks.append(name)
                            seen_names.add(name)
                    # 为每个股票获取逻辑并显示
                    if unique_stocks:
                        text_widget.insert(tk.END, "\n\n" + "="*80 + "\n", "separator")
                        text_widget.insert(tk.END, "【股票逻辑信息】\n\n", "logic_title")
                        for stock_name in unique_stocks[:5]:  # 最多显示5只股票的逻辑
                            # 从数据库获取该股票的逻辑
                            logic_data = get_stock_logic_from_db(stock_name=stock_name)
                            if logic_data:
                                # 获取最新的逻辑记录
                                latest_logic = logic_data[0]
                                logic_text = latest_logic.get('logic', '')
                                logic_date = latest_logic.get('date', latest_logic.get('created_at', ''))
                                logic_source = latest_logic.get('source', '未知')
                                if logic_text:
                                    text_widget.insert(tk.END, f"股票:{stock_name}\n", "logic_title")
                                    text_widget.insert(tk.END, f"日期:{logic_date} | 来源:{logic_source}\n", "logic_content")
                                    text_widget.insert(tk.END, f"逻辑:{logic_text}\n", "logic_content")
                                    text_widget.insert(tk.END, "-"*80 + "\n\n", "separator")
                            else:
                                text_widget.insert(tk.END, f"股票:{stock_name} - 数据库中暂无逻辑记录\n\n", "logic_content")
            except Exception as e:
                print(f"获取股票逻辑失败: {e}")
            text_widget.config(state=tk.DISABLED)  # 只读
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 关闭按钮
            close_button = ttk.Button(popup, text="关闭", command=popup.destroy)
            close_button.pack(pady=10)
        def update_warning_recent_records():
            """更新最近三条记录显示"""
            try:
                # 清除旧的标签
                for widget in recent_frame.winfo_children():
                    widget.destroy()
                records = get_recent_warning_records()
                if not records:
                    label = ttk.Label(recent_frame, text="暂无记录", font=("TkDefaultFont", 8))
                    label.pack(side=tk.LEFT)
                    return
                for i, (tab_name, content, created_at) in enumerate(records):
                    # 提取类型(从"警示失败2024-01-01"中提取"失败")
                    warning_type = ""
                    for wtype in ["失败", "成功", "醒悟"]:
                        if wtype in tab_name:
                            warning_type = wtype
                            break
                    # 显示前10个字
                    display_text = content[:10] if content else ""
                    if len(content) > 10:
                        display_text += "..."
                    # 创建可点击的标签(前面加上编号1、2、3)
                    label_text = f"{i+1}.{warning_type}:{display_text}"
                    label = ttk.Label(recent_frame, text=label_text,
                                     font=("TkDefaultFont", 8),
                                     cursor="hand2", width=15)
                    label.pack(side=tk.LEFT, padx=(0, 3))
                    # 绑定点击事件
                    def make_popup_handler(c, t):
                        return lambda e: show_warning_popup(c, t)
                    label.bind("<Button-1>", make_popup_handler(content, tab_name))
            except Exception as e:
                print(f"更新最近记录显示失败: {e}")
        # 保存更新方法到实例变量
        self.update_warning_recent_records = update_warning_recent_records
        # 初始化显示最近记录
        update_warning_recent_records()
        def fetch_warning_records(limit=10):
            """从资讯数据库获取最新的警示通言记录"""
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT id, tab_name, content, created_at
                    FROM news_info
                    WHERE tab_name LIKE '警示%'
                    ORDER BY created_at DESC
                    LIMIT ?
                    ''',
                    (limit,)
                )
                rows = cursor.fetchall()
                conn.close()
                return rows
            except Exception as e:
                print(f"获取警示通言记录失败: {e}")
                return []
        # 定义浏览资讯记录的函数
        def browse_news_records(filter_type):
            """浏览资讯记录(警示或开新仓记录),支持左右切换"""
            browse_window = self._toplevel(self.root)
            if filter_type == "警示":
                browse_window.title("浏览警示记录")
                filter_pattern = "警示%"
            else:  # 开新仓记录
                browse_window.title("浏览开新仓记录")
                filter_pattern = "%开新仓记录%"
            browse_window.geometry("1000x700")
            # 主框架
            main_frame = ttk.Frame(browse_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 顶部信息栏
            info_frame = ttk.Frame(main_frame)
            info_frame.pack(fill=tk.X, pady=(0, 10))
            current_index_var = tk.StringVar(value="0 / 0")
            ttk.Label(info_frame, text="当前记录:", font=("TkDefaultFont", 12)).pack(side=tk.LEFT, padx=5)
            ttk.Label(info_frame, textvariable=current_index_var, font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, padx=5)
            record_title_var = tk.StringVar(value="")
            ttk.Label(info_frame, textvariable=record_title_var, font=("TkDefaultFont", 12, "bold"), foreground="blue").pack(side=tk.LEFT, padx=20)
            # 内容显示区域
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            # 左侧按钮
            left_button_frame = ttk.Frame(content_frame)
            left_button_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
            # 右侧按钮
            right_button_frame = ttk.Frame(content_frame)
            right_button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
            # 中间内容区域
            center_frame = ttk.Frame(content_frame)
            center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            # 根据情绪周期确定背景颜色
            if hasattr(self, 'get_emotion_bg_color'):
                browse_bg_color = self.get_emotion_bg_color()
            else:
                browse_bg_color = "white"
            # 内容文本框
            content_text = scrolledtext.ScrolledText(center_frame, wrap=tk.WORD, font=("TkDefaultFont", 11), bg=browse_bg_color)
            content_text.pack(fill=tk.BOTH, expand=True)
            # 保存引用以便后续更新背景颜色
            if not hasattr(self, '_browse_window_text_widgets'):
                self._browse_window_text_widgets = []
            self._browse_window_text_widgets.append(content_text)
            # 存储所有记录
            all_records = []
            current_record_index = 0
            def load_records():
                """从数据库加载记录"""
                nonlocal all_records, current_record_index
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, tab_name, content, created_at
                        FROM news_info
                        WHERE tab_name LIKE ?
                        ORDER BY created_at DESC
                    ''', (filter_pattern,))
                    all_records = cursor.fetchall()
                    conn.close()
                    if all_records:
                        current_record_index = 0
                        display_current_record()
                    else:
                        content_text.delete("1.0", tk.END)
                        content_text.insert("1.0", f"暂无{filter_type}记录")
                        current_index_var.set("0 / 0")
                        record_title_var.set("")
                except Exception as e:
                    messagebox.showerror("错误", f"加载记录失败: {e}", parent=browse_window)
            def display_current_record():
                """显示当前记录"""
                if not all_records or current_record_index < 0 or current_record_index >= len(all_records):
                    return
                record = all_records[current_record_index]
                _news_id, tab_name, content, created_at = record
                # 更新信息
                current_index_var.set(f"{current_record_index + 1} / {len(all_records)}")
                record_title_var.set(f"{tab_name} ({created_at})")
                # 显示内容
                content_text.config(state=tk.NORMAL)
                content_text.delete("1.0", tk.END)
                content_text.insert("1.0", content)
                content_text.config(state=tk.DISABLED)
            def previous_record():
                """上一条记录"""
                nonlocal current_record_index
                if all_records and current_record_index > 0:
                    current_record_index -= 1
                    display_current_record()
            def next_record():
                """下一条记录"""
                nonlocal current_record_index
                if all_records and current_record_index < len(all_records) - 1:
                    current_record_index += 1
                    display_current_record()
            # 左侧按钮(上一条)
            prev_button = ttk.Button(left_button_frame, text="◀ 上一条", command=previous_record, width=12)
            prev_button.pack(pady=10)
            # 右侧按钮(下一条)
            next_button = ttk.Button(right_button_frame, text="下一条 ▶", command=next_record, width=12)
            next_button.pack(pady=10)
            # 底部按钮栏
            bottom_frame = ttk.Frame(main_frame)
            bottom_frame.pack(fill=tk.X)
            ttk.Button(bottom_frame, text="刷新", command=load_records).pack(side=tk.LEFT, padx=5)
            ttk.Button(bottom_frame, text="关闭", command=browse_window.destroy).pack(side=tk.RIGHT, padx=5)
            # 初始加载
            load_records()
            # 绑定键盘快捷键
            browse_window.bind("<Left>", lambda e: previous_record())
            browse_window.bind("<Right>", lambda e: next_record())
            browse_window.focus_set()
        def update_position():
            """更新仓位计算结果"""
            try:
                # 获取三个下拉框的分值(情绪、大V、昨日)
                emotion_score = position_scores.get(emotion_var.get(), 0)
                v_judge_score = position_scores.get(v_judge_var.get(), 0)
                yesterday_score = position_scores.get(yesterday_var.get(), 0)
                # 获取基本面、技术面、情绪面的分值
                fundamental_score = int(fundamental_var.get() or 0)
                technical_score = int(technical_var.get() or 0)
                sentiment_score = int(sentiment_var.get() or 0)
                # 计算基本面+技术面+情绪面的总分值
                three_dimension_total = fundamental_score + technical_score + sentiment_score
                # 更新总分值显示
                total_score_var.set(f"总分: {three_dimension_total}")
                # 求和(原有的情绪、大V、昨日)
                total_score = emotion_score + v_judge_score + yesterday_score
                # 计算仓位百分比:百分比 = 总分 / 30 * 100
                position_percent = (total_score / 30.0) * 100
                # 确保百分比在0-100%范围内
                position_percent = max(0, min(100, position_percent))
                # 更新结果显示(紧凑显示)
                position_result_var.set(f"+{position_percent:.1f}%")
                # 更新颜色灯(新的渐变逻辑)
                # 0-50%:绿色→黄色渐变
                # 50-100%:黄色→红色渐变
                if position_percent <= 50:
                    # 0-50%: 绿色到黄色
                    ratio = position_percent / 50.0
                    red = int(255 * ratio)
                    green = 255
                    blue = 0
                else:
                    # 50-100%: 黄色到红色
                    ratio = (position_percent - 50) / 50.0
                    red = 255
                    green = int(255 * (1 - ratio))
                    blue = 0
                # 转换为十六进制颜色
                color = f"#{red:02x}{green:02x}{blue:02x}"
                # 绘制圆形指示灯
                light_canvas.delete("all")
                light_canvas.create_oval(3, 3, 22, 22, fill=color, outline="black", width=1)
                # 更新"关于做T"下拉框(始终禁用)
                if total_score < 0:
                    # 负数:下行趋势,不可以做T
                    t_trading_var.set("下行趋势 不可以做T")
                    t_trading_combo.config(state="disabled")
                elif position_percent <= 50:
                    # 0-50%:谨慎做T
                    t_trading_var.set("谨慎做T")
                    t_trading_combo.config(state="disabled")
                else:
                    # 51-100%:上行趋势,可以做T
                    t_trading_var.set("上行趋势 可以做T")
                    t_trading_combo.config(state="disabled")
                # 更新"开新仓"下拉框和按钮状态
                # 判断情绪指数是否下行:total_score < 0 或 three_dimension_total下降
                prev_three_dimension_total = getattr(update_position, 'prev_three_dimension_total', three_dimension_total)
                is_sentiment_down = (total_score < 0) or (three_dimension_total < prev_three_dimension_total)
                update_position.prev_three_dimension_total = three_dimension_total
                if is_sentiment_down or position_percent < 30:
                    # 情绪指数下行或低于30%:禁止开新仓
                    new_position_var.set("禁止开新仓")
                    new_position_combo.config(state="readonly")
                    new_position_button.config(state="disabled")
                    new_position_button2.config(state="disabled")
                    new_position_button3.config(state="disabled")
                    new_position_button4.config(state="disabled")
                    new_position_button5.config(state="disabled")
                else:
                    # 情绪指数上行且大于等于30%:可以开新仓
                    new_position_var.set("可以开新仓")
                    new_position_combo.config(state="readonly")
                    new_position_button.config(state="normal")
                    new_position_button2.config(state="normal")
                    new_position_button3.config(state="normal")
                    new_position_button4.config(state="normal")
                    new_position_button5.config(state="normal")
            except Exception as e:
                print(f"更新仓位计算失败: {e}")
        # 绑定下拉框变化事件
        emotion_combo.bind("<<ComboboxSelected>>", lambda e: update_position())
        v_judge_combo.bind("<<ComboboxSelected>>", lambda e: update_position())
        yesterday_combo.bind("<<ComboboxSelected>>", lambda e: update_position())
        fundamental_combo.bind("<<ComboboxSelected>>", lambda e: update_position())
        technical_combo.bind("<<ComboboxSelected>>", lambda e: update_position())
        sentiment_combo.bind("<<ComboboxSelected>>", lambda e: update_position())
        # 初始化显示总分值
        update_position()
        # ==================== 新增控件:情绪周期、主流板块、是否止损(同一行) ====================
        new_controls_frame = ttk.Frame(position_frame)
        new_controls_frame.pack(fill=tk.X, pady=(5, 0))
        # 情绪周期下拉框 + 红绿灯
        ttk.Label(new_controls_frame, text="1情绪周期:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        emotion_cycle_var = tk.StringVar(value="震荡")
        emotion_cycle_combo = ttk.Combobox(new_controls_frame, textvariable=emotion_cycle_var,
                                          values=["上行", "震荡", "下行"],
                                          state="readonly", width=8)
        emotion_cycle_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.emotion_cycle_var = emotion_cycle_var
        # 红绿灯控件(Canvas)
        emotion_light_canvas = tk.Canvas(new_controls_frame, width=20, height=20, highlightthickness=1,
                                        highlightbackground="gray")
        emotion_light_canvas.pack(side=tk.LEFT, padx=(0, 10))
        def update_emotion_light(*args):
            """更新情绪周期红绿灯,并控制开新仓按钮状态"""
            cycle = emotion_cycle_var.get()
            emotion_light_canvas.delete("all")
            if cycle == "上行":
                emotion_light_canvas.create_oval(2, 2, 18, 18, fill="green", outline="black", width=1)
                # 上行:可以开新仓
                if hasattr(self, 'new_position_button'):
                    self.new_position_button.config(state="normal")
                    self.new_position_button2.config(state="normal")
                    self.new_position_button3.config(state="normal")
                    self.new_position_button4.config(state="normal")
                    self.new_position_button5.config(state="normal")
            elif cycle == "震荡":
                emotion_light_canvas.create_oval(2, 2, 18, 18, fill="yellow", outline="black", width=1)
                # 震荡:可以开新仓
                if hasattr(self, 'new_position_button'):
                    self.new_position_button.config(state="normal")
                    self.new_position_button2.config(state="normal")
                    self.new_position_button3.config(state="normal")
                    self.new_position_button4.config(state="normal")
                    self.new_position_button5.config(state="normal")
            elif cycle == "下行":
                emotion_light_canvas.create_oval(2, 2, 18, 18, fill="red", outline="black", width=1)
                # 下行:禁止开新仓,按钮灰色不可按
                if hasattr(self, 'new_position_button'):
                    self.new_position_button.config(state="disabled")
                    self.new_position_button2.config(state="disabled")
                    self.new_position_button3.config(state="disabled")
                    self.new_position_button4.config(state="disabled")
                    self.new_position_button5.config(state="disabled")
                # 弹出SOS预警,并启动定时器每5分钟重新打开
                self._show_sos_alert()
                self._start_sos_alert_timer()
            else:
                # 上行或震荡:停止SOS预警定时器
                self._stop_sos_alert_timer()
        # 初始化红绿灯:从历史记录获取最新涨跌个数
        try:
            history = self._get_sentiment_history(limit=1)
            if history:
                latest_record = history[0]
                up_count = latest_record.get("m2_up")
                if up_count is not None:
                    if up_count < 1600:
                        emotion_cycle_var.set("下行")
                        # 红灯状态下,启动时自动跳过拦截层,不需要输入密码
                        self._emotion_lock_suppressed = True
                    elif up_count <= 3500:
                        emotion_cycle_var.set("震荡")
                    else:
                        emotion_cycle_var.set("上行")
        except Exception:
            pass
        # 绑定下拉框变化事件
        emotion_cycle_var.trace_add('write', update_emotion_light)
        # 初始调用一次
        update_emotion_light()
        # 技术指标下拉框
        ttk.Label(new_controls_frame, text="技术指标:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(20, 2))
        tech_indicator_var = tk.StringVar(value="MACD")
        tech_indicator_combo = ttk.Combobox(new_controls_frame, textvariable=tech_indicator_var,
                                          values=["MACD", "RSI", "KDJ", "BOLL", "MA", "VOL", "WR", "CCI", "OBV", "DMI"],
                                          state="readonly", width=8)
        tech_indicator_combo.pack(side=tk.LEFT, padx=(0, 5))
        def show_tech_indicator_analysis():
            """显示技术指标分析对话框"""
            indicator_name = tech_indicator_var.get()
            self._show_tech_indicator_dialog(indicator_name)
        tech_indicator_btn = ttk.Button(new_controls_frame, text="分析",
                                       command=show_tech_indicator_analysis, width=6)
        tech_indicator_btn.pack(side=tk.LEFT, padx=(0, 10))
        # 主流板块下拉框 + 设置按钮
        ttk.Label(new_controls_frame, text="主流板块:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        default_main_sectors = ["新能源", "人工智能", "芯片", "医药", "消费", "金融", "地产", "基建"]
        main_sectors = self.ai_config_manager.config.get("main_sectors", default_main_sectors.copy())
        if not main_sectors:
            main_sectors = default_main_sectors.copy()
        main_sector_var = tk.StringVar(value=main_sectors[0] if main_sectors else "")
        main_sector_combo = ttk.Combobox(new_controls_frame, textvariable=main_sector_var,
                                        values=main_sectors,
                                        state="readonly", width=12)
        main_sector_combo.pack(side=tk.LEFT, padx=(0, 5))
        def show_main_sector_settings():
            """显示主流板块设置对话框"""
            settings_window = self._toplevel(self.root)
            settings_window.title("主流板块设置")
            settings_window.geometry("400x500")
            settings_window.transient(self.root)
            ttk.Label(settings_window, text="请输入主流板块名称(每行一个):",
                     font=("TkDefaultFont", 12)).pack(pady=(10, 5))
            text_frame = ttk.Frame(settings_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            sector_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15, font=("TkDefaultFont", 12))
            sector_text.pack(fill=tk.BOTH, expand=True)
            current_sectors = self.ai_config_manager.config.get("main_sectors", default_main_sectors.copy())
            sector_text.insert("1.0", "\n".join(current_sectors))
            button_frame = ttk.Frame(settings_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            def save_sectors():
                content = sector_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "请输入至少一个板块名称", parent=settings_window)
                    return
                sectors = [line.strip() for line in content.split("\n") if line.strip()]
                if not sectors:
                    messagebox.showwarning("警告", "请输入至少一个板块名称", parent=settings_window)
                    return
                self.ai_config_manager.config["main_sectors"] = sectors
                self.ai_config_manager.save_config()
                main_sector_combo['values'] = sectors
                if sectors:
                    main_sector_var.set(sectors[0])
                messagebox.showinfo("成功", f"已保存 {len(sectors)} 个主流板块", parent=settings_window)
                settings_window.destroy()
            ttk.Button(button_frame, text="保存", command=save_sectors).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(button_frame, text="取消", command=settings_window.destroy).pack(side=tk.LEFT)
        main_sector_settings_btn = ttk.Button(new_controls_frame, text="主流板块设置",
                                             command=show_main_sector_settings, width=12)
        main_sector_settings_btn.pack(side=tk.LEFT, padx=(0, 10))
        # 是否止损下拉框 + 止损显示
        ttk.Label(new_controls_frame, text="是否止损:", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(0, 2))
        stop_loss_options = ["15分钟20下行", "60分钟5破10", "15分钟40破80", "日线破10", "日线破20", "均不是"]
        stop_loss_var = tk.StringVar(value="均不是")
        stop_loss_combo = ttk.Combobox(new_controls_frame, textvariable=stop_loss_var,
                                      values=stop_loss_options,
                                      state="readonly", width=15)
        stop_loss_combo.pack(side=tk.LEFT, padx=(0, 5))
        stop_loss_label = ttk.Label(new_controls_frame, text="止损",
                                   font=("TkDefaultFont", 8, "bold"), foreground="red")
        def update_stop_loss_display(*args):
            """更新止损显示"""
            value = stop_loss_var.get()
            if value != "均不是":
                stop_loss_label.pack(side=tk.LEFT)
            else:
                stop_loss_label.pack_forget()
        stop_loss_var.trace_add("write", update_stop_loss_display)
        update_stop_loss_display()
        # ==================== 空白处显示区域:情绪周期红绿灯(2倍大小+闪烁)、主流板块文字(3倍加粗)、牌权和值搏率下拉框 ====================
        blank_display_frame = ttk.Frame(position_frame)
        blank_display_frame.pack(fill=tk.X, pady=(10, 5))
        # 居中容器:使用pack居中布局
        center_container = ttk.Frame(blank_display_frame)
        center_container.pack(expand=True, fill=tk.X)
        # 红绿灯控件(2倍大小:40x40,原来20x20);三个2倍大灯放到爬取东方财富/同花顺按钮右边,此处只保留大号灯
        emotion_light_canvas_large = tk.Canvas(center_container, width=40, height=40, highlightthickness=1,
                                              highlightbackground="gray")
        emotion_light_canvas_large.pack(side=tk.LEFT, padx=15)
        # 三个2倍大灯在"交易"标签页爬取按钮右侧创建,此处用空列表,更新函数会遍历 self.emotion_light_2x_canvases
        self.emotion_light_2x_canvases = []
        # 闪烁状态变量
        emotion_blink_state = {"blinking": False, "visible": True, "timer_id": None}
        def update_emotion_light_large(*args):
            """更新情绪周期红绿灯(大号+三个2倍大灯在爬取按钮右侧,带闪烁)"""
            cycle = emotion_cycle_var.get()
            emotion_light_canvas_large.delete("all")
            for c in getattr(self, 'emotion_light_2x_canvases', []):
                try:
                    c.delete("all")
                    if emotion_blink_state["visible"]:
                        if cycle == "上行":
                            c.create_oval(4, 4, 36, 36, fill="green", outline="black", width=2)
                        elif cycle == "震荡":
                            c.create_oval(4, 4, 36, 36, fill="yellow", outline="black", width=2)
                        elif cycle == "下行":
                            c.create_oval(4, 4, 36, 36, fill="red", outline="black", width=2)
                except Exception:
                    pass
            if emotion_blink_state["visible"]:
                if cycle == "上行":
                    emotion_light_canvas_large.create_oval(4, 4, 36, 36, fill="green", outline="black", width=2)
                elif cycle == "震荡":
                    emotion_light_canvas_large.create_oval(4, 4, 36, 36, fill="yellow", outline="black", width=2)
                elif cycle == "下行":
                    emotion_light_canvas_large.create_oval(4, 4, 36, 36, fill="red", outline="black", width=2)
        def start_blinking():
            """开始闪烁"""
            # 如果已经在闪烁,先停止
            if emotion_blink_state["timer_id"] is not None:
                self.root.after_cancel(emotion_blink_state["timer_id"])
            emotion_blink_state["blinking"] = True
            emotion_blink_state["visible"] = True
            blink_emotion_light()
        def stop_blinking():
            """停止闪烁"""
            emotion_blink_state["blinking"] = False
            if emotion_blink_state["timer_id"] is not None:
                self.root.after_cancel(emotion_blink_state["timer_id"])
                emotion_blink_state["timer_id"] = None
            emotion_blink_state["visible"] = True
            update_emotion_light_large()
        def blink_emotion_light():
            """闪烁动画"""
            if emotion_blink_state["blinking"]:
                emotion_blink_state["visible"] = not emotion_blink_state["visible"]
                update_emotion_light_large()
                # 每500ms切换一次
                emotion_blink_state["timer_id"] = self.root.after(500, blink_emotion_light)
        # 绑定情绪周期变化;保存更新函数供爬取按钮右侧三灯刷新用
        self._update_emotion_lights = update_emotion_light_large
        def on_emotion_cycle_var_change(*args):
            update_emotion_light()
            update_emotion_light_large()
            start_blinking()
            update_text_bg_colors()
            self._emotion_cycle_changed_for_lock()
        emotion_cycle_var.trace_add("write", on_emotion_cycle_var_change)
        # 首次刷新(update_text_bg_colors 在下方才定义,此处由 初始化背景颜色 处调用)
        update_emotion_light()
        update_emotion_light_large()
        start_blinking()
        self._emotion_cycle_changed_for_lock()
        # 主流板块文字显示(3倍加粗)
        main_sector_display_label = ttk.Label(center_container, text="",
                                             font=("TkDefaultFont", 24, "bold"))
        main_sector_display_label.pack(side=tk.LEFT, padx=15)
        def update_main_sector_display(*args):
            """更新主流板块显示文字"""
            sector = main_sector_var.get()
            main_sector_display_label.config(text=sector)
        main_sector_var.trace_add("write", update_main_sector_display)
        update_main_sector_display()
        # 牌权下拉框和显示
        card_power_frame = ttk.Frame(center_container)
        card_power_frame.pack(side=tk.LEFT, padx=15)
        # 标签(24pt加粗)
        ttk.Label(card_power_frame, text="牌权:", font=("TkDefaultFont", 24, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        card_power_var = tk.StringVar(value="10%")
        # 下拉框(隐藏,仅用于选择)
        card_power_combo = ttk.Combobox(card_power_frame, textvariable=card_power_var,
                                       values=["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"],
                                       state="readonly", width=6)
        card_power_combo.pack(side=tk.LEFT, padx=(0, 5))
        # 显示选中的值(24pt加粗,与板块字样一致)
        card_power_display_label = ttk.Label(card_power_frame, text="10%",
                                            font=("TkDefaultFont", 24, "bold"))
        card_power_display_label.pack(side=tk.LEFT)
        def update_card_power_display(*args):
            """更新牌权显示文字"""
            value = card_power_var.get()
            card_power_display_label.config(text=value)
        card_power_var.trace_add("write", update_card_power_display)
        update_card_power_display()
        # 值搏率下拉框和显示
        value_risk_frame = ttk.Frame(center_container)
        value_risk_frame.pack(side=tk.LEFT, padx=15)
        # 标签(24pt加粗)
        ttk.Label(value_risk_frame, text="值搏率:", font=("TkDefaultFont", 24, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        value_risk_var = tk.StringVar(value="10%")
        # 下拉框(隐藏,仅用于选择)
        value_risk_combo = ttk.Combobox(value_risk_frame, textvariable=value_risk_var,
                                       values=["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"],
                                       state="readonly", width=6)
        value_risk_combo.pack(side=tk.LEFT, padx=(0, 5))
        # 显示选中的值(24pt加粗,与板块字样一致)
        value_risk_display_label = ttk.Label(value_risk_frame, text="10%",
                                             font=("TkDefaultFont", 24, "bold"))
        value_risk_display_label.pack(side=tk.LEFT)
        def update_value_risk_display(*args):
            """更新值搏率显示文字"""
            value = value_risk_var.get()
            value_risk_display_label.config(text=value)
        value_risk_var.trace_add("write", update_value_risk_display)
        update_value_risk_display()
        self.card_power_var = card_power_var
        self.value_risk_var = value_risk_var
        # 存储需要更新背景颜色的文本框引用
        self.text_widgets_for_bg_update = []
        def get_emotion_bg_color():
            """根据情绪周期获取背景颜色"""
            cycle = emotion_cycle_var.get()
            if cycle == "上行":  # 绿灯
                return "#e6ffe6"  # 淡绿色半透明
            elif cycle == "震荡":  # 黄灯
                return "#fff9e6"  # 淡黄色半透明
            elif cycle == "下行":  # 红灯,整个软件背景为红色
                return "#ffcccc"  # 红色背景
            else:
                return "white"  # 默认白色
        # 将函数保存为实例方法,以便在其他地方调用
        self.get_emotion_bg_color = get_emotion_bg_color
        def update_text_bg_colors():
            """根据情绪周期红绿灯状态更新所有相关文本框及整个软件背景颜色"""
            bg_color = get_emotion_bg_color()
            # 情绪周期红灯(下行)时,整个软件背景为红色
            try:
                self.root.configure(bg=bg_color)
            except Exception:
                pass
            try:
                style = ttk.Style()
                style.configure('TFrame', background=bg_color)
            except Exception:
                pass
            # 更新文本控制标签页中的所有文本框
            if hasattr(self, 'text_widgets'):
                for tab_info in self.text_widgets.values():
                    if 'widget' in tab_info:
                        try:
                            tab_info['widget'].config(bg=bg_color)
                        except:
                            pass
            # 更新全窗口浏览的文本框(如果存在)
            if hasattr(self, '_browse_window_text_widgets'):
                for text_widget in self._browse_window_text_widgets:
                    try:
                        text_widget.config(bg=bg_color)
                    except:
                        pass
            # 更新右侧分析框(如果存在)
            if hasattr(self, '_analysis_result_text_widgets'):
                for text_widget in self._analysis_result_text_widgets:
                    try:
                        text_widget.config(bg=bg_color)
                    except:
                        pass
        # 初始化背景颜色
        update_text_bg_colors()
        # 开新仓流程弹出界面
        def show_new_position_dialog(position_type="绩优股"):
            """显示开新仓流程对话框"""
            dialog = self._toplevel(self.root)
            dialog.title(f"开{position_type}新仓流程")
            dialog.geometry("1000x800")
            dialog.resizable(True, True)
            waiting_reason = getattr(self, "pending_waiting_reason", None)
            self.pending_waiting_reason = None
            # 传递主界面的变量到对话框
            dialog.total_score_var = total_score_var
            # 主容器框架
            main_container = ttk.Frame(dialog, padding=10)
            main_container.pack(fill=tk.BOTH, expand=True)
        # 创建左右分栏(左边60%,右边40%)
            paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
            paned.pack(fill=tk.BOTH, expand=True)
            # 左侧内容区域(可滚动)- 占60%
            left_pane = ttk.Frame(paned)
            paned.add(left_pane, weight=3)
            # 创建左侧滚动框架
            canvas = tk.Canvas(left_pane)
            scrollbar = ttk.Scrollbar(left_pane, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            main_frame = ttk.Frame(scrollable_frame, padding=15)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 右侧按钮区域 - 占40%
            right_pane = ttk.LabelFrame(paned, text="操作按钮", padding=15)
            paned.add(right_pane, weight=2)
            def set_default_right_pane_width():
                """默认将右侧操作区域调整为约40%宽度"""
                try:
                    total_width = paned.winfo_width()
                    if total_width <= 0:
                        total_width = dialog.winfo_width()
                    if total_width <= 0:
                        total_width = 1000  # 使用窗口初始宽度
                    left_width = int(total_width * 0.6)
                    paned.sashpos(0, left_width)
                except Exception as e:
                    print(f"设置开新仓左右比例失败: {e}")
            # 在界面渲染完成后设置默认宽度
            dialog.after(100, set_default_right_pane_width)
            # 股票名称输入区域(移到最上面)
            stock_name_frame = ttk.LabelFrame(main_frame, text="股票信息", padding=10)
            stock_name_frame.pack(fill=tk.X, pady=(0, 8))
            stock_name_row = ttk.Frame(stock_name_frame)
            stock_name_row.pack(fill=tk.X)
            ttk.Label(stock_name_row, text="股票名称:", font=("TkDefaultFont", 12)).pack(side=tk.LEFT, padx=(0, 5))
            stock_name_var = tk.StringVar()
            # 设置为可编辑的下拉框
            stock_name_combo = ttk.Combobox(stock_name_row, textvariable=stock_name_var, width=20, font=("TkDefaultFont", 12), state="normal")
            stock_name_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 初始化股票名称列表(保留最近50个)
            stock_names_list = []
            MAX_STOCK_LIST_SIZE = 50
            # 更新股票名称下拉框
            def update_stock_combo():
                # 限制列表大小为50
                if len(stock_names_list) > MAX_STOCK_LIST_SIZE:
                    stock_names_list[:] = stock_names_list[-MAX_STOCK_LIST_SIZE:]
                stock_name_combo['values'] = stock_names_list
            # 添加股票到列表(如果不存在则添加,保持最近50个)
            def add_stock_to_list(stock_name):
                if stock_name and stock_name.strip():
                    stock_name = stock_name.strip()
                    # 如果已存在,先移除
                    if stock_name in stock_names_list:
                        stock_names_list.remove(stock_name)
                    # 添加到末尾
                    stock_names_list.append(stock_name)
                    # 限制大小
                    if len(stock_names_list) > MAX_STOCK_LIST_SIZE:
                        stock_names_list[:] = stock_names_list[-MAX_STOCK_LIST_SIZE:]
                    update_stock_combo()
            # 批量添加股票到列表
            def add_stocks_to_list(stock_names):
                for stock_name in stock_names:
                    if stock_name and stock_name.strip():
                        stock_name = stock_name.strip()
                        # 如果已存在,先移除
                        if stock_name in stock_names_list:
                            stock_names_list.remove(stock_name)
                        # 添加到末尾
                        stock_names_list.append(stock_name)
                # 限制大小
                if len(stock_names_list) > MAX_STOCK_LIST_SIZE:
                    stock_names_list[:] = stock_names_list[-MAX_STOCK_LIST_SIZE:]
                update_stock_combo()
            # 初始化:将股票管理列表中的股票添加到下拉框
            if getattr(self, "managed_stock_names", None):
                add_stocks_to_list(self.managed_stock_names[-MAX_STOCK_LIST_SIZE:])
            # 股票名称管理按钮 - 打开股票数据库
            db_window_ref = [None]  # 使用列表存储引用,以便在回调中访问
            def manage_stock_names():
                """打开股票数据库,支持双击单个选择或批量选择导入"""
                db_window = None
                def on_stock_selected(stock_name):
                    """双击股票后的回调函数"""
                    if stock_name:
                        stock_name_var.set(stock_name)
                        add_stock_to_list(stock_name)
                        # 关闭数据库窗口
                        if db_window and db_window.winfo_exists():
                            db_window.destroy()
                def batch_import_stocks():
                    """批量导入选中的股票"""
                    if not db_window or not db_window.winfo_exists():
                        messagebox.showwarning("提示", "请先打开股票数据库", parent=dialog)
                        return
                    # 查找stock_tree并获取选中的股票
                    def find_stock_tree(widget):
                        """递归查找stock_tree"""
                        if isinstance(widget, ttk.Treeview):
                            return widget
                        for child in widget.winfo_children():
                            result = find_stock_tree(child)
                            if result:
                                return result
                        return None
                    try:
                        # 查找股票数据表格
                        stock_tree = None
                        for widget in db_window.winfo_children():
                            stock_tree = find_stock_tree(widget)
                            if stock_tree:
                                break
                        if stock_tree:
                            # 获取选中的项目
                            selections = stock_tree.selection()
                            if selections:
                                batch_stocks = []
                                for item_id in selections:
                                    item = stock_tree.item(item_id)
                                    values = item['values']
                                    if len(values) >= 2:
                                        stock_name = values[1]  # 股票名称在第二列
                                        if stock_name and stock_name.strip():
                                            batch_stocks.append(stock_name.strip())
                                if batch_stocks:
                                    add_stocks_to_list(batch_stocks)
                                    messagebox.showinfo("成功", f"已导入 {len(batch_stocks)} 只股票到下拉框", parent=dialog)
                                    # 如果只选中一个,也填入输入框
                                    if len(batch_stocks) == 1:
                                        stock_name_var.set(batch_stocks[0])
                                else:
                                    messagebox.showwarning("提示", "选中的记录中没有有效的股票名称", parent=dialog)
                            else:
                                messagebox.showwarning("提示", "请先在股票数据表中选择股票记录(可多选)", parent=dialog)
                        else:
                            messagebox.showwarning("提示", "未找到股票数据表,请确保已打开股票数据表标签页", parent=dialog)
                    except Exception as e:
                        messagebox.showerror("错误", f"批量导入失败: {e}", parent=dialog)
                # 打开股票数据库窗口,传入回调函数
                def on_stock_selected_with_close(stock_name):
                    """双击股票后的回调函数(带窗口关闭)"""
                    if stock_name:
                        stock_name_var.set(stock_name)
                        add_stock_to_list(stock_name)
                        # 查找并关闭数据库窗口
                        for widget in self.root.winfo_children():
                            if isinstance(widget, tk.Toplevel):
                                try:
                                    if "数据库管理" in widget.title():
                                        widget.destroy()
                                        break
                                except:
                                    pass
                # 打开股票数据库窗口
                db_window = self.show_unified_db_display(default_tab="stock", on_stock_double_click=on_stock_selected_with_close)
                db_window_ref[0] = db_window
                # 在数据库窗口中添加批量导入按钮
                def add_batch_import_button():
                    try:
                        # 查找数据库窗口中的按钮区域
                        for widget in db_window.winfo_children():
                            for child in widget.winfo_children():
                                if isinstance(child, ttk.Notebook):
                                    for tab_id in child.tabs():
                                        tab = child.nametowidget(tab_id)
                                        for tab_child in tab.winfo_children():
                                            if isinstance(tab_child, ttk.Frame):
                                                # 查找按钮框架
                                                for btn_frame in tab_child.winfo_children():
                                                    if isinstance(btn_frame, ttk.Frame):
                                                        # 添加批量导入按钮
                                                        batch_btn = ttk.Button(btn_frame, text="批量导入到开新仓",
                                                                              command=batch_import_stocks, width=15)
                                                        batch_btn.pack(side=tk.LEFT, padx=5)
                                                        return
                    except Exception as e:
                        print(f"添加批量导入按钮失败: {e}")
                # 延迟添加按钮,等待窗口创建完成
                db_window.after(200, add_batch_import_button)
            ttk.Button(stock_name_row, text="管理", command=manage_stock_names, width=8).pack(side=tk.LEFT, padx=(0, 15))
            # 当输入框失去焦点或按回车时,将输入的股票添加到列表
            def on_stock_name_enter(event):
                stock_name = stock_name_var.get().strip()
                if stock_name:
                    add_stock_to_list(stock_name)
            stock_name_combo.bind("<Return>", on_stock_name_enter)
            stock_name_combo.bind("<FocusOut>", lambda e: add_stock_to_list(stock_name_var.get().strip()))
            # 创建内容标签页Notebook(股票信息下方)
            content_notebook = ttk.Notebook(main_frame)
            content_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
            # 标签页1:1日线检测
            ma1_detection_tab = ttk.Frame(content_notebook, padding=10)
            content_notebook.add(ma1_detection_tab, text="1日线检测")
            # 创建1日线检测标签页的可滚动框架
            ma1_canvas = tk.Canvas(ma1_detection_tab)
            ma1_scrollbar = ttk.Scrollbar(ma1_detection_tab, orient="vertical", command=ma1_canvas.yview)
            ma1_scrollable_frame = ttk.Frame(ma1_canvas)
            ma1_scrollable_frame.bind(
                "<Configure>",
                lambda e: ma1_canvas.configure(scrollregion=ma1_canvas.bbox("all"))
            )
            ma1_canvas.create_window((0, 0), window=ma1_scrollable_frame, anchor="nw")
            ma1_canvas.configure(yscrollcommand=ma1_scrollbar.set)
            # 确保canvas窗口随内容调整大小和宽度
            def configure_canvas_width(event):
                canvas_width = event.width
                ma1_canvas.itemconfig(ma1_canvas.find_all()[0] if ma1_canvas.find_all() else None, width=canvas_width)
            ma1_canvas.bind("<Configure>", configure_canvas_width)
            # 确保scrollable_frame随内容更新scrollregion
            def update_scroll_region(event):
                ma1_canvas.configure(scrollregion=ma1_canvas.bbox("all"))
            ma1_scrollable_frame.bind("<Configure>", update_scroll_region)
            ma1_canvas.pack(side="left", fill="both", expand=True)
            ma1_scrollbar.pack(side="right", fill="y")
            ma1_tab_content = ttk.Frame(ma1_scrollable_frame, padding=10)
            ma1_tab_content.pack(fill=tk.BOTH, expand=True)
            # 先定义所有需要的变量(在使用之前)
            # 1日线检测区域变量
            stock_code_var = tk.StringVar(value="--")
            current_price_var = tk.StringVar(value="--")
            ma1_reference_var = tk.StringVar(value="--")
            ma1_prev_var = tk.StringVar(value="--")
            ma1_status_var = tk.StringVar(value="未检测")
            ma1_source_var = tk.StringVar(value="数据来源: 未检测")
            ma1_data_ready_var = tk.BooleanVar(value=False)
            ma1_crossed_var = tk.BooleanVar(value=False)
            ma1_uptrend_var = tk.BooleanVar(value=False)
            ts_account_var = tk.StringVar(value=self.ts_account or TS_DEFAULT_ACCOUNT)
            ts_token_var = tk.StringVar(value=self.ts_token or TS_DEFAULT_TOKEN)
            ts_status_var = tk.StringVar(value="已登录" if self.ts_client else "未登录")
            # 5日线检测区域变量
            ma5_reference_var = tk.StringVar(value="--")
            ma5_prev_var = tk.StringVar(value="--")
            ma5_status_var = tk.StringVar(value="未检测")
            ma5_data_ready_var = tk.BooleanVar(value=False)
            ma5_crossed_var = tk.BooleanVar(value=False)
            ma5_uptrend_var = tk.BooleanVar(value=False)
            # 10日线检测区域变量
            ma10_reference_var = tk.StringVar(value="--")
            ma10_prev_var = tk.StringVar(value="--")
            ma10_status_var = tk.StringVar(value="未检测")
            ma10_data_ready_var = tk.BooleanVar(value=False)
            ma10_crossed_var = tk.BooleanVar(value=False)
            ma10_uptrend_var = tk.BooleanVar(value=False)
            # 20日线检测区域变量
            ma20_reference_var = tk.StringVar(value="--")
            ma20_prev_var = tk.StringVar(value="--")
            ma20_status_var = tk.StringVar(value="未检测")
            ma20_data_ready_var = tk.BooleanVar(value=False)
            ma20_crossed_var = tk.BooleanVar(value=False)
            ma20_uptrend_var = tk.BooleanVar(value=False)
            volume_5day_avg_var = tk.StringVar(value="--")
            volume_10day_avg_var = tk.StringVar(value="--")
            volume_trend_var = tk.StringVar(value="未检测")
            # 创建检测区域容器(占60%宽度)
            # 使用PanedWindow来控制宽度比例
            detection_paned = ttk.PanedWindow(ma1_tab_content, orient=tk.HORIZONTAL)
            detection_paned.pack(fill=tk.X, pady=(0, 10))
            detection_container = ttk.Frame(detection_paned)
            detection_paned.add(detection_container, weight=3)  # 占60% (3/(3+2)=60%)
            # 右侧占位空间(40%)
            right_placeholder = ttk.Frame(detection_paned)
            detection_paned.add(right_placeholder, weight=2)  # 占40% (2/(3+2)=40%)
            # Tushare配置区域(统一配置,参照股票数据表的检测模块)
            tushare_config_frame = ttk.LabelFrame(detection_container, text="Tushare配置", padding=8)
            tushare_config_frame.pack(fill=tk.X, pady=(0, 10))
            ts_config_row1 = ttk.Frame(tushare_config_frame)
            ts_config_row1.pack(fill=tk.X, pady=2)
            ttk.Label(ts_config_row1, text="账号:", width=6).pack(side=tk.LEFT, padx=3)
            ttk.Entry(ts_config_row1, textvariable=ts_account_var, width=18).pack(side=tk.LEFT, padx=3)
            ttk.Label(ts_config_row1, text="Token:", width=6).pack(side=tk.LEFT, padx=3)
            ts_token_entry = ttk.Entry(ts_config_row1, textvariable=ts_token_var, width=22, show="*")
            ts_token_entry.pack(side=tk.LEFT, padx=3)
            # 先定义login_tushare_for_ma1函数(在按钮使用之前)
            def login_tushare_for_ma1(show_message=True):
                """登录Tushare"""
                if not TS_AVAILABLE:
                    if show_message:
                        messagebox.showerror("错误", "当前环境未安装tushare,请先安装", parent=dialog)
                    return False
                token = ts_token_var.get().strip() or TS_DEFAULT_TOKEN
                account = ts_account_var.get().strip() or TS_DEFAULT_ACCOUNT
                try:
                    self._ensure_tushare_client(token)
                    self.ts_account = account
                    self.ts_token = token
                    # 保存到配置文件
                    self.ai_config_manager.set_tushare_config(account=account, token=token)
                    ts_status_var.set("已登录")
                    ts_status_label.configure(foreground="green")
                    if show_message:
                        messagebox.showinfo("成功", "Tushare 登录成功", parent=dialog)
                    return True
                except Exception as exc:
                    ts_status_var.set("登录失败")
                    ts_status_label.configure(foreground="red")
                    if show_message:
                        messagebox.showerror("错误", f"Tushare 登录失败: {exc}", parent=dialog)
                    return False
            ttk.Button(ts_config_row1, text="登录", width=8, command=lambda: login_tushare_for_ma1(show_message=True)).pack(side=tk.LEFT, padx=5)
            initial_color = "green" if self.ts_client else "gray"
            ts_status_label = ttk.Label(ts_config_row1, textvariable=ts_status_var, foreground=initial_color)
            ts_status_label.pack(side=tk.LEFT, padx=3)
            # 添加按钮行(命令将在所有函数定义后设置)
            ts_config_row2 = ttk.Frame(tushare_config_frame)
            ts_config_row2.pack(fill=tk.X, pady=2)
            one_key_check_btn = ttk.Button(ts_config_row2, text="一键检测1,5,10,20日线", width=20)
            one_key_check_btn.pack(side=tk.LEFT, padx=5)
            default_detect_btn = ttk.Button(ts_config_row2, text="默认数据检测", width=15)
            default_detect_btn.pack(side=tk.LEFT, padx=5)
            # 定义reset函数和其他辅助函数
            def reset_ma1_state():
                """重置1日线检测状态"""
                ma1_data_ready_var.set(False)
                ma1_crossed_var.set(False)
                ma1_uptrend_var.set(False)
                current_price_var.set("--")
                ma1_reference_var.set("--")
                ma1_prev_var.set("--")
                ma1_status_var.set("未检测")
                ma1_source_var.set("数据来源: 未检测")
                stock_code_var.set("--")
            def reset_ma5_state():
                """重置5日线检测状态"""
                ma5_data_ready_var.set(False)
                ma5_crossed_var.set(False)
                ma5_uptrend_var.set(False)
                ma5_reference_var.set("--")
                ma5_prev_var.set("--")
                ma5_status_var.set("未检测")
            def reset_ma10_state():
                """重置10日线检测状态"""
                ma10_data_ready_var.set(False)
                ma10_crossed_var.set(False)
                ma10_uptrend_var.set(False)
                ma10_reference_var.set("--")
                ma10_prev_var.set("--")
                ma10_status_var.set("未检测")
            def reset_ma20_state():
                """重置20日线检测状态"""
                ma20_data_ready_var.set(False)
                ma20_crossed_var.set(False)
                ma20_uptrend_var.set(False)
                ma20_reference_var.set("--")
                ma20_prev_var.set("--")
                ma20_status_var.set("未检测")
            def reset_volume_trend():
                volume_5day_avg_var.set("--")
                volume_10day_avg_var.set("--")
                volume_trend_var.set("未检测")
            def format_volume_value(value: float) -> str:
                """格式化成交量,默认单位手"""
                if value is None:
                    return "--"
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return "--"
                if value >= 10000:
                    return f"{value / 10000:.2f}万手"
                return f"{value:.0f}手"
            def update_volume_trend(volumes):
                if not volumes or len(volumes) < 10:
                    reset_volume_trend()
                    return
                last5 = volumes[-5:]
                last10 = volumes[-10:]
                avg5 = sum(last5) / len(last5)
                avg10 = sum(last10) / len(last10)
                volume_5day_avg_var.set(format_volume_value(avg5))
                volume_10day_avg_var.set(format_volume_value(avg10))
                if avg5 > avg10:
                    change_pct = ((avg5 - avg10) / avg10 * 100) if avg10 else 0
                    volume_trend_var.set(f"成交量放大(+{change_pct:.1f}%)")
                elif avg5 < avg10:
                    change_pct = ((avg10 - avg5) / avg10 * 100) if avg10 else 0
                    volume_trend_var.set(f"成交量萎缩(-{change_pct:.1f}%)")
                else:
                    volume_trend_var.set("成交量持平")
            # 均线检测布局:2x2布局(上排1日/5日,下排10日/20日)
            ma_top_row = ttk.Frame(detection_container)
            ma_top_row.pack(fill=tk.X, pady=(0, 6))
            ma_bottom_row = ttk.Frame(detection_container)
            ma_bottom_row.pack(fill=tk.X, pady=(0, 6))
            def fetch_ma1_status(source="default", silent=False):
                """获取1日线状态,优先使用Tushare"""
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    if not silent:
                        messagebox.showwarning("警告", "请先输入股票名称", parent=dialog)
                    return False
                stock_code = get_stock_code_by_name(stock_name)
                if not stock_code:
                    if not silent:
                        messagebox.showerror("错误", f"无法获取 {stock_name} 的股票代码", parent=dialog)
                    return False
                volumes = None
                try:
                    # 如果明确指定tushare,先登录
                    if source == "tushare":
                        if not login_tushare_for_ma1(show_message=not silent):
                            return False
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=15, source="tushare", token=self.ts_token, return_volume=True
                        )
                        ma1_source_var.set(f"数据来源: Tushare(账号 {self.ts_account or '默认'})")
                    else:
                        # 默认模式:优先尝试Tushare,失败则使用AKShare
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=15, source="default", token=self.ts_token, return_volume=True
                        )
                        # 根据实际使用的数据源设置标签
                        if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                            ma1_source_var.set("数据来源: Tushare(自动)")
                        else:
                            ma1_source_var.set("数据来源: AKShare")
                    if isinstance(result, tuple) and len(result) == 3:
                        dates, closes, volumes = result
                    else:
                        _dates, closes = result
                except Exception as exc:
                    reset_ma1_state()
                    reset_volume_trend()
                    error_msg = str(exc)
                    print(f"获取1日线数据失败 (股票代码: {stock_code}): {error_msg}")
                    import traceback
                    traceback.print_exc()
                    if not silent:
                        messagebox.showerror("错误", f"获取1日线数据失败: {error_msg}\n股票代码: {stock_code}", parent=dialog)
                    return False
                if not closes or len(closes) < 3:
                    reset_ma1_state()
                    reset_volume_trend()
                    if not silent:
                        messagebox.showwarning("提示", "可用日线数据不足,无法判断1日线状态", parent=dialog)
                    return False
                stock_code_var.set(stock_code)
                # 优先获取实时价格或当日价格
                realtime_price = None
                try:
                    # 尝试使用tushare获取实时价格
                    if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                        try:
                            import tushare as ts
                            ts_token = self.ts_token or TS_DEFAULT_TOKEN
                            os.environ["TUSHARE_TOKEN"] = ts_token
                            ts_code = self._format_ts_code(stock_code)
                            # 先尝试实时行情
                            try:
                                df = ts.realtime_quote(ts_code=ts_code, src='dc')
                                if df is not None and not df.empty and 'price' in df.columns:
                                    realtime_price = float(df.iloc[0]['price'])
                                    if realtime_price > 0.01 and realtime_price < 10000:
                                        print(f"[tushare实时] {stock_code} 实时价格: {realtime_price}")
                            except:
                                pass  # 跳过 daily fallback, 实时失败用历史收盘价(外层已兜底)
                        except Exception as e:
                            print(f"获取实时价格失败 {stock_code}: {e}")
                except:
                    pass
                # 如果获取到实时价格,使用实时价格;否则使用历史收盘价
                if realtime_price and realtime_price > 0:
                    latest_price = realtime_price
                else:
                    latest_price = float(closes[-1])
                ref_price = float(closes[-2])
                prev_price = float(closes[-3])
                current_price_var.set(f"{latest_price:.2f}")
                ma1_reference_var.set(f"{ref_price:.2f}")
                ma1_prev_var.set(f"{prev_price:.2f}")
                crossed = latest_price >= ref_price
                uptrend = ref_price >= prev_price
                ma1_crossed_var.set(crossed)
                ma1_uptrend_var.set(uptrend)
                ma1_data_ready_var.set(True)
                update_volume_trend(volumes)
                trend_text = "向上" if uptrend else "未向上"
                cross_text = "已站上" if crossed else "未站上"
                ma1_status_var.set(f"{stock_name} {cross_text}1日线,1日线{trend_text}")
                # 设置颜色:已站上用红色粗体,否则用绿色
                if crossed:
                    ma1_status_label.configure(foreground="red", font=("TkDefaultFont", 11, "bold"))
                else:
                    ma1_status_label.configure(foreground="green", font=("TkDefaultFont", 11))
                return True
            # 1日线检测区域(上排左边)
            ma1_frame = ttk.LabelFrame(ma_top_row, text="1日线检测(必须条件)", padding=8)
            ma1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
            code_row = ttk.Frame(ma1_frame)
            code_row.pack(fill=tk.X, pady=2)
            ttk.Label(code_row, text="股票代码:", width=10).pack(side=tk.LEFT)
            ttk.Label(code_row, textvariable=stock_code_var, foreground="blue", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
            ttk.Label(code_row, textvariable=ma1_source_var, foreground="gray").pack(side=tk.RIGHT)
            price_row = ttk.Frame(ma1_frame)
            price_row.pack(fill=tk.X, pady=2)
            ttk.Label(price_row, text="最新价:", width=8).pack(side=tk.LEFT)
            ttk.Label(price_row, textvariable=current_price_var, foreground="green").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(price_row, text="参考1日线:", width=10).pack(side=tk.LEFT)
            ttk.Label(price_row, textvariable=ma1_reference_var, foreground="green").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(price_row, text="前一日:", width=8).pack(side=tk.LEFT)
            ttk.Label(price_row, textvariable=ma1_prev_var, foreground="green").pack(side=tk.LEFT)
            status_row = ttk.Frame(ma1_frame)
            status_row.pack(fill=tk.X, pady=2)
            ma1_status_label = tk.Label(status_row, textvariable=ma1_status_var, foreground="blue", font=("TkDefaultFont", 11))
            ma1_status_label.pack(side=tk.LEFT)
            ma1_cross_check = ttk.Checkbutton(
                ma1_frame, text="股价站上1日线", variable=ma1_crossed_var, state=tk.DISABLED
            )
            ma1_cross_check.pack(anchor=tk.W, pady=2)
            ma1_uptrend_check = ttk.Checkbutton(
                ma1_frame, text="1日线向上发散", variable=ma1_uptrend_var, state=tk.DISABLED
            )
            ma1_uptrend_check.pack(anchor=tk.W, pady=2)
            # 1日线检测按钮(移除Tushare配置,已统一到顶部)
            button_row = ttk.Frame(ma1_frame)
            button_row.pack(fill=tk.X, pady=4)
            ttk.Button(button_row, text="检测1日线", command=lambda: fetch_ma1_status("default")).pack(side=tk.LEFT, padx=5)
            def reset_ma5_state():
                """重置5日线检测状态"""
                ma5_data_ready_var.set(False)
                ma5_crossed_var.set(False)
                ma5_uptrend_var.set(False)
                ma5_reference_var.set("--")
                ma5_prev_var.set("--")
                ma5_status_var.set("未检测")
            def fetch_ma5_status(source="default", silent=False):
                """获取5日线状态,优先使用Tushare"""
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    if not silent:
                        messagebox.showwarning("警告", "请先输入股票名称", parent=dialog)
                    return False
                stock_code = get_stock_code_by_name(stock_name)
                if not stock_code:
                    if not silent:
                        messagebox.showerror("错误", f"无法获取 {stock_name} 的股票代码", parent=dialog)
                    return False
                volumes = None
                try:
                    if source == "tushare":
                        if not login_tushare_for_ma1(show_message=not silent):
                            return False
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=20, source="tushare", token=self.ts_token, return_volume=True
                        )
                    else:
                        # 默认模式:优先尝试Tushare,失败则使用AKShare
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=20, source="default", token=self.ts_token, return_volume=True
                        )
                    if isinstance(result, tuple) and len(result) == 3:
                        dates, closes, volumes = result
                    else:
                        _dates, closes = result
                except Exception as exc:
                    reset_ma5_state()
                    reset_volume_trend()
                    error_msg = str(exc)
                    print(f"获取5日线数据失败 (股票代码: {stock_code}): {error_msg}")
                    import traceback
                    traceback.print_exc()
                    if not silent:
                        messagebox.showerror("错误", f"获取5日线数据失败: {error_msg}\n股票代码: {stock_code}", parent=dialog)
                    return False
                if not closes or len(closes) < 7:
                    reset_ma5_state()
                    reset_volume_trend()
                    if not silent:
                        messagebox.showwarning("提示", "可用日线数据不足,无法判断5日线状态", parent=dialog)
                    return False
                # 优先获取实时价格或当日价格
                realtime_price = None
                try:
                    # 尝试使用tushare获取实时价格
                    if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                        try:
                            import tushare as ts
                            ts_token = self.ts_token or TS_DEFAULT_TOKEN
                            os.environ["TUSHARE_TOKEN"] = ts_token
                            ts_code = self._format_ts_code(stock_code)
                            # 先尝试实时行情
                            try:
                                df = ts.realtime_quote(ts_code=ts_code, src='dc')
                                if df is not None and not df.empty and 'price' in df.columns:
                                    realtime_price = float(df.iloc[0]['price'])
                                    if realtime_price > 0.01 and realtime_price < 10000:
                                        print(f"[tushare实时] {stock_code} 实时价格: {realtime_price}")
                            except:
                                pass  # 跳过 daily fallback, 实时失败用历史收盘价(外层已兜底)
                        except Exception as e:
                            print(f"获取实时价格失败 {stock_code}: {e}")
                except:
                    pass
                # 如果获取到实时价格,使用实时价格;否则使用历史收盘价
                if realtime_price and realtime_price > 0:
                    latest_price = realtime_price
                else:
                    latest_price = float(closes[-1])
                # 5日均价(最近5天)
                ma5_values = [float(closes[i]) for i in range(len(closes)-5, len(closes))]
                ref_ma5 = sum(ma5_values) / len(ma5_values)
                # 前一个5日均价(前5天)
                prev_ma5_values = [float(closes[i]) for i in range(len(closes)-10, len(closes)-5)]
                prev_ma5 = sum(prev_ma5_values) / len(prev_ma5_values) if len(prev_ma5_values) >= 5 else ref_ma5
                ma5_reference_var.set(f"{ref_ma5:.2f}")
                ma5_prev_var.set(f"{prev_ma5:.2f}")
                crossed = latest_price >= ref_ma5
                uptrend = ref_ma5 >= prev_ma5
                ma5_crossed_var.set(crossed)
                ma5_uptrend_var.set(uptrend)
                ma5_data_ready_var.set(True)
                update_volume_trend(volumes)
                trend_text = "向上" if uptrend else "未向上"
                cross_text = "已站上" if crossed else "未站上"
                ma5_status_var.set(f"{stock_name} {cross_text}5日线,5日线{trend_text}")
                # 设置颜色:已站上用红色粗体,否则用绿色
                if crossed:
                    ma5_status_label.configure(foreground="red", font=("TkDefaultFont", 11, "bold"))
                else:
                    ma5_status_label.configure(foreground="green", font=("TkDefaultFont", 11))
                return True
            # 10日线检测区域变量
            ma10_reference_var = tk.StringVar(value="--")
            ma10_prev_var = tk.StringVar(value="--")
            ma10_status_var = tk.StringVar(value="未检测")
            ma10_data_ready_var = tk.BooleanVar(value=False)
            ma10_crossed_var = tk.BooleanVar(value=False)
            ma10_uptrend_var = tk.BooleanVar(value=False)
            def reset_ma10_state():
                """重置10日线检测状态"""
                ma10_data_ready_var.set(False)
                ma10_crossed_var.set(False)
                ma10_uptrend_var.set(False)
                ma10_reference_var.set("--")
                ma10_prev_var.set("--")
                ma10_status_var.set("未检测")
                reset_volume_trend()
            def fetch_ma10_status(source="default", silent=False):
                """获取10日线状态,优先使用Tushare"""
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    if not silent:
                        messagebox.showwarning("警告", "请先输入股票名称", parent=dialog)
                    return False
                stock_code = get_stock_code_by_name(stock_name)
                if not stock_code:
                    if not silent:
                        messagebox.showerror("错误", f"无法获取 {stock_name} 的股票代码", parent=dialog)
                    return False
                volumes = None
                try:
                    if source == "tushare":
                        if not login_tushare_for_ma1(show_message=not silent):
                            return False
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=25, source="tushare", token=self.ts_token, return_volume=True
                        )
                    else:
                        # 默认模式:优先尝试Tushare,失败则使用AKShare
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=25, source="default", token=self.ts_token, return_volume=True
                        )
                    if isinstance(result, tuple) and len(result) == 3:
                        dates, closes, volumes = result
                    else:
                        _dates, closes = result
                        volumes = None
                except Exception as exc:
                    reset_ma10_state()
                    reset_volume_trend()
                    error_msg = str(exc)
                    print(f"获取10日线数据失败 (股票代码: {stock_code}): {error_msg}")
                    import traceback
                    traceback.print_exc()
                    if not silent:
                        messagebox.showerror("错误", f"获取10日线数据失败: {error_msg}\n股票代码: {stock_code}", parent=dialog)
                    return False
                if (not closes or len(closes) < 12) or (not volumes or len(volumes) < 10):
                    reset_ma10_state()
                    reset_volume_trend()
                    if not silent:
                        messagebox.showwarning("提示", "可用日线数据不足,无法判断10日线状态", parent=dialog)
                    return False
                # 优先获取实时价格或当日价格
                realtime_price = None
                try:
                    # 尝试使用tushare获取实时价格
                    if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                        try:
                            import tushare as ts
                            ts_token = self.ts_token or TS_DEFAULT_TOKEN
                            os.environ["TUSHARE_TOKEN"] = ts_token
                            ts_code = self._format_ts_code(stock_code)
                            # 先尝试实时行情
                            try:
                                df = ts.realtime_quote(ts_code=ts_code, src='dc')
                                if df is not None and not df.empty and 'price' in df.columns:
                                    realtime_price = float(df.iloc[0]['price'])
                                    if realtime_price > 0.01 and realtime_price < 10000:
                                        print(f"[tushare实时] {stock_code} 实时价格: {realtime_price}")
                            except:
                                pass  # 跳过 daily fallback, 实时失败用历史收盘价(外层已兜底)
                        except Exception as e:
                            print(f"获取实时价格失败 {stock_code}: {e}")
                except:
                    pass
                # 如果获取到实时价格,使用实时价格;否则使用历史收盘价
                if realtime_price and realtime_price > 0:
                    latest_price = realtime_price
                else:
                    latest_price = float(closes[-1])
                # 10日均价(最近10天)
                ma10_values = [float(closes[i]) for i in range(len(closes)-10, len(closes))]
                ref_ma10 = sum(ma10_values) / len(ma10_values)
                # 前一个10日均价(前10天)
                prev_ma10_values = [float(closes[i]) for i in range(len(closes)-20, len(closes)-10)]
                prev_ma10 = sum(prev_ma10_values) / len(prev_ma10_values) if len(prev_ma10_values) >= 10 else ref_ma10
                ma10_reference_var.set(f"{ref_ma10:.2f}")
                ma10_prev_var.set(f"{prev_ma10:.2f}")
                crossed = latest_price >= ref_ma10
                uptrend = ref_ma10 >= prev_ma10
                ma10_crossed_var.set(crossed)
                ma10_uptrend_var.set(uptrend)
                ma10_data_ready_var.set(True)
                update_volume_trend(volumes)
                trend_text = "向上" if uptrend else "未向上"
                cross_text = "已站上" if crossed else "未站上"
                ma10_status_var.set(f"{stock_name} {cross_text}10日线,10日线{trend_text}")
                # 设置颜色:已站上用红色粗体,否则用绿色
                if crossed:
                    ma10_status_label.configure(foreground="red", font=("TkDefaultFont", 11, "bold"))
                else:
                    ma10_status_label.configure(foreground="green", font=("TkDefaultFont", 11))
                return True
            # 20日线检测区域变量
            ma20_reference_var = tk.StringVar(value="--")
            ma20_prev_var = tk.StringVar(value="--")
            ma20_status_var = tk.StringVar(value="未检测")
            ma20_data_ready_var = tk.BooleanVar(value=False)
            ma20_crossed_var = tk.BooleanVar(value=False)
            ma20_uptrend_var = tk.BooleanVar(value=False)
            volume_5day_avg_var = tk.StringVar(value="--")
            volume_10day_avg_var = tk.StringVar(value="--")
            volume_trend_var = tk.StringVar(value="未检测")
            def format_volume_value(value: float) -> str:
                """格式化成交量,默认单位手"""
                if value is None:
                    return "--"
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return "--"
                if value >= 10000:
                    return f"{value / 10000:.2f}万手"
                return f"{value:.0f}手"
            def reset_volume_trend():
                volume_5day_avg_var.set("--")
                volume_10day_avg_var.set("--")
                volume_trend_var.set("未检测")
            def update_volume_trend(volumes):
                if not volumes or len(volumes) < 10:
                    reset_volume_trend()
                    return
                last5 = volumes[-5:]
                last10 = volumes[-10:]
                avg5 = sum(last5) / len(last5)
                avg10 = sum(last10) / len(last10)
                volume_5day_avg_var.set(format_volume_value(avg5))
                volume_10day_avg_var.set(format_volume_value(avg10))
                if avg5 > avg10:
                    change_pct = ((avg5 - avg10) / avg10 * 100) if avg10 else 0
                    volume_trend_var.set(f"成交量放大(+{change_pct:.1f}%)")
                elif avg5 < avg10:
                    change_pct = ((avg10 - avg5) / avg10 * 100) if avg10 else 0
                    volume_trend_var.set(f"成交量萎缩(-{change_pct:.1f}%)")
                else:
                    volume_trend_var.set("成交量持平")
            def reset_ma20_state():
                """重置20日线检测状态"""
                ma20_data_ready_var.set(False)
                ma20_crossed_var.set(False)
                ma20_uptrend_var.set(False)
                ma20_reference_var.set("--")
                ma20_prev_var.set("--")
                ma20_status_var.set("未检测")
            def fetch_ma20_status(source="default", silent=False):
                """获取20日线状态,优先使用Tushare"""
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    if not silent:
                        messagebox.showwarning("警告", "请先输入股票名称", parent=dialog)
                    return False
                stock_code = get_stock_code_by_name(stock_name)
                if not stock_code:
                    if not silent:
                        messagebox.showerror("错误", f"无法获取 {stock_name} 的股票代码", parent=dialog)
                    return False
                volumes = None
                try:
                    if source == "tushare":
                        if not login_tushare_for_ma1(show_message=not silent):
                            return False
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=45, source="tushare", token=self.ts_token, return_volume=True
                        )
                    else:
                        # 默认模式:优先尝试Tushare,失败则使用AKShare
                        result = self._fetch_recent_daily_closes(
                            stock_code, days=45, source="default", token=self.ts_token, return_volume=True
                        )
                    if isinstance(result, tuple) and len(result) == 3:
                        dates, closes, volumes = result
                    else:
                        _dates, closes = result
                except Exception as exc:
                    reset_ma20_state()
                    reset_volume_trend()
                    error_msg = str(exc)
                    print(f"获取20日线数据失败 (股票代码: {stock_code}): {error_msg}")
                    import traceback
                    traceback.print_exc()
                    if not silent:
                        messagebox.showerror("错误", f"获取20日线数据失败: {error_msg}\n股票代码: {stock_code}", parent=dialog)
                    return False
                if not closes or len(closes) < 22:
                    reset_ma20_state()
                    reset_volume_trend()
                    if not silent:
                        messagebox.showwarning("提示", "可用日线数据不足,无法判断20日线状态", parent=dialog)
                    return False
                # 优先获取实时价格或当日价格
                realtime_price = None
                try:
                    # 尝试使用tushare获取实时价格
                    if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                        try:
                            import tushare as ts
                            ts_token = self.ts_token or TS_DEFAULT_TOKEN
                            os.environ["TUSHARE_TOKEN"] = ts_token
                            ts_code = self._format_ts_code(stock_code)
                            # 先尝试实时行情
                            try:
                                df = ts.realtime_quote(ts_code=ts_code, src='dc')
                                if df is not None and not df.empty and 'price' in df.columns:
                                    realtime_price = float(df.iloc[0]['price'])
                                    if realtime_price > 0.01 and realtime_price < 10000:
                                        print(f"[tushare实时] {stock_code} 实时价格: {realtime_price}")
                            except:
                                pass  # 跳过 daily fallback, 实时失败用历史收盘价(外层已兜底)
                        except Exception as e:
                            print(f"获取实时价格失败 {stock_code}: {e}")
                except:
                    pass
                # 如果获取到实时价格,使用实时价格;否则使用历史收盘价
                if realtime_price and realtime_price > 0:
                    latest_price = realtime_price
                else:
                    latest_price = float(closes[-1])
                # 20日均价(最近20天)
                ma20_values = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
                ref_ma20 = sum(ma20_values) / len(ma20_values)
                # 前一个20日均价(前20天)
                prev_ma20_values = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
                prev_ma20 = sum(prev_ma20_values) / len(prev_ma20_values) if len(prev_ma20_values) >= 20 else ref_ma20
                ma20_reference_var.set(f"{ref_ma20:.2f}")
                ma20_prev_var.set(f"{prev_ma20:.2f}")
                crossed = latest_price >= ref_ma20
                uptrend = ref_ma20 >= prev_ma20
                ma20_crossed_var.set(crossed)
                ma20_uptrend_var.set(uptrend)
                ma20_data_ready_var.set(True)
                update_volume_trend(volumes)
                trend_text = "向上" if uptrend else "未向上"
                cross_text = "已站上" if crossed else "未站上"
                ma20_status_var.set(f"{stock_name} {cross_text}20日线,20日线{trend_text}")
                # 设置颜色:已站上用红色粗体,否则用绿色
                if crossed:
                    ma20_status_label.configure(foreground="red", font=("TkDefaultFont", 11, "bold"))
                else:
                    ma20_status_label.configure(foreground="green", font=("TkDefaultFont", 11))
                return True
            # 现在所有检测函数都已定义,可以正确定义run_all_tushare_checks并更新按钮
            def run_all_tushare_checks():
                """一键执行所有依赖Tushare的数据检测"""
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    messagebox.showwarning("警告", "请先输入股票名称", parent=dialog)
                    return
                checks = [
                    ("1日线", fetch_ma1_status),
                    ("5日线", fetch_ma5_status),
                    ("10日线", fetch_ma10_status),
                    ("20日线", fetch_ma20_status),
                ]
                failed = []
                for label, checker in checks:
                    if not checker("tushare", silent=True):
                        failed.append(label)
                if failed:
                    messagebox.showwarning(
                        "提示",
                        f"Tushare检测完成,但以下项目失败:{', '.join(failed)}",
                        parent=dialog
                    )
                else:
                    messagebox.showinfo("成功", "Tushare数据检测完成,所有均线已更新", parent=dialog)
            # 更新按钮的command
            one_key_check_btn.config(command=run_all_tushare_checks)
            default_detect_btn.config(command=lambda: [fetch_ma1_status("default"), fetch_ma5_status("default"),
                                                     fetch_ma10_status("default"), fetch_ma20_status("default")])
            def handle_stock_name_change_all(*_):
                """处理股票名称变化,重置所有均线状态"""
                reset_ma1_state()
                reset_ma5_state()
                reset_ma10_state()
                reset_ma20_state()
                reset_volume_trend()
            stock_name_var.trace_add("write", handle_stock_name_change_all)
            # 标签页3:主力净量
            main_net_flow_tab = ttk.Frame(content_notebook, padding=10)
            content_notebook.add(main_net_flow_tab, text="主力净量")
            # 主力净量显示框架
            net_flow_frame = ttk.LabelFrame(main_net_flow_tab, text="当日主力净量指标", padding=15)
            net_flow_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            # 主力净量变量
            main_net_flow_var = tk.StringVar(value="--")
            main_net_flow_status_var = tk.StringVar(value="未获取")
            # 显示区域
            info_label = ttk.Label(net_flow_frame, text="最近5天净资金流入统计最近5个交易日的资金流向总和,正值表示总体净流入,负值表示总体净流出。",
                                   wraplength=500, foreground="gray")
            info_label.pack(anchor=tk.W, pady=(0, 15))
            value_frame = ttk.Frame(net_flow_frame)
            value_frame.pack(fill=tk.X, pady=10)
            ttk.Label(value_frame, text="最近5天净资金流入:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, padx=(0, 10))
            main_net_flow_label = ttk.Label(value_frame, textvariable=main_net_flow_var,
                                          font=("TkDefaultFont", 14, "bold"), foreground="blue")
            main_net_flow_label.pack(side=tk.LEFT, padx=(0, 20))
            status_label = ttk.Label(value_frame, textvariable=main_net_flow_status_var,
                                   font=("TkDefaultFont", 11), foreground="gray")
            status_label.pack(side=tk.LEFT)
            # 每日详情显示区域
            detail_frame = ttk.LabelFrame(net_flow_frame, text="每日详情", padding=10)
            detail_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            detail_text_area = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD,
                                                         font=("TkDefaultFont", 11), state=tk.DISABLED)
            detail_text_area.pack(fill=tk.BOTH, expand=True)
            # 定义获取主力净量函数(在label创建之后,确保可以访问)
            def fetch_main_net_flow():
                """获取最近5天的净资金流入"""
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    messagebox.showwarning("警告", "请先输入股票名称", parent=dialog)
                    return
                stock_code = get_stock_code_by_name(stock_name)
                if not stock_code:
                    messagebox.showerror("错误", f"无法获取 {stock_name} 的股票代码", parent=dialog)
                    return
                try:
                    main_net_flow_status_var.set("获取中...")
                    # 清空详情文本区域
                    detail_text_area.config(state=tk.NORMAL)
                    detail_text_area.delete("1.0", tk.END)
                    detail_text_area.insert("1.0", "正在获取数据...")
                    detail_text_area.config(state=tk.DISABLED)
                    net_flow_5days = None
                    data_source = None
                    daily_details = []  # 存储每日详情
                    # 方法1: 优先尝试使用Tushare获取最近5天的资金流向
                    if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                        try:
                            # 确保Tushare客户端可用
                            if not self.ts_client:
                                self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                            ts_code = self._format_ts_code(stock_code)
                            # 获取最近5个交易日的数据
                            end_date = datetime.now().strftime("%Y%m%d")
                            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
                            # 获取最近30天的数据,然后取最近5天
                            df = self.ts_client.moneyflow(ts_code=ts_code, start_date=start_date, end_date=end_date)
                            if df is not None and not df.empty:
                                # 按日期排序,取最近5天
                                df_sorted = df.sort_values('trade_date', ascending=False).head(5)
                                if len(df_sorted) > 0:
                                    # 计算净主力资金流入总和(单位:元,需要转换为万元)
                                    if 'net_mf_amount' in df_sorted.columns:
                                        net_flow_5days = float(df_sorted['net_mf_amount'].sum()) / 10000  # 转换为万元
                                        data_source = f"Tushare({len(df_sorted)}天数据)"
                                        # 保存每日详情
                                        for _, row in df_sorted.iterrows():
                                            daily_val = float(row['net_mf_amount']) / 10000
                                            daily_details.append(f"{row['trade_date']}: {daily_val:+.2f}万元")
                                    elif 'net_amount' in df_sorted.columns:
                                        net_flow_5days = float(df_sorted['net_amount'].sum()) / 10000
                                        data_source = f"Tushare({len(df_sorted)}天数据)"
                                        # 保存每日详情
                                        for _, row in df_sorted.iterrows():
                                            daily_val = float(row['net_amount']) / 10000
                                            daily_details.append(f"{row['trade_date']}: {daily_val:+.2f}万元")
                        except Exception as e1:
                            print(f"Tushare获取最近5天净资金流入失败,切换到AKShare: {e1}")
                            import traceback
                            traceback.print_exc()
                    # 方法2: 如果Tushare失败或不可用,使用akshare获取历史数据并估算
                    if net_flow_5days is None:
                        try:
                            # 获取最近10天的历史数据(确保能取到至少5个交易日)
                            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                            if hist_data is not None and not hist_data.empty and len(hist_data) >= 5:
                                # 确保数据按日期排序
                                if "日期" in hist_data.columns:
                                    hist_data = hist_data.sort_values("日期")
                                elif "date" in hist_data.columns:
                                    hist_data = hist_data.sort_values("date")
                                # 取最近5天
                                recent_5days = hist_data.tail(5)
                                # 查找列名
                                close_col = None
                                date_col = None
                                volume_col = None
                                for col in recent_5days.columns:
                                    col_str = str(col)
                                    col_lower = col_str.lower()
                                    if close_col is None and ('收盘' in col_str or 'close' in col_lower):
                                        close_col = col
                                    if date_col is None and ('日期' in col_str or 'date' in col_lower):
                                        date_col = col
                                    if volume_col is None and ('成交量' in col_str or 'volume' in col_lower):
                                        volume_col = col
                                if close_col is None:
                                    raise ValueError(f"未找到收盘价列,可用列: {list(recent_5days.columns)}")
                                # 通过价格变化和成交量估算资金流向
                                # 上涨+放量 = 资金流入,下跌+放量 = 资金流出
                                total_net_flow = 0
                                daily_details = []
                                for i in range(len(recent_5days)):
                                    if i == 0:
                                        continue  # 第一天没有前一日数据
                                    current = recent_5days.iloc[i]
                                    prev = recent_5days.iloc[i-1]
                                    current_price = float(current[close_col])
                                    prev_price = float(prev[close_col])
                                    current_volume = float(current.get(volume_col, 0)) if volume_col else 0
                                    prev_volume = float(prev.get(volume_col, 0)) if volume_col else 0
                                    # 计算涨跌幅
                                    change_pct = ((current_price - prev_price) / prev_price) if prev_price > 0 else 0
                                    current_volume / prev_volume if prev_volume > 0 else 1
                                    # 估算当日资金流向:涨跌幅 * 成交额 * 系数
                                    # 成交额 = 成交量 * 收盘价
                                    turnover = current_volume * current_price
                                    # 简化估算:涨跌幅越大,流入越多(正相关)
                                    estimated_flow = turnover * change_pct * 0.3  # 系数0.3用于调整估算值
                                    total_net_flow += estimated_flow
                                    date_str = str(current.get(date_col, '')) if date_col else f"第{i+1}天"
                                    daily_details.append(f"{date_str}: {estimated_flow/10000:+.2f}万元")
                                net_flow_5days = total_net_flow / 10000  # 转换为万元
                                data_source = f"AKShare估算(最近{len(recent_5days)}天)"
                        except Exception as e2:
                            error_detail = f"AKShare获取最近5天净资金流入失败: {e2}"
                            print(f"股票代码: {stock_code}, {error_detail}")
                            import traceback
                            traceback.print_exc()
                            # 在详情区域显示错误
                            detail_text_area.config(state=tk.NORMAL)
                            detail_text_area.delete("1.0", tk.END)
                            detail_text_area.insert("1.0", f"AKShare获取失败: {e2!s}\n请检查股票代码是否正确或网络连接")
                            detail_text_area.config(state=tk.DISABLED)
                    # 显示结果
                    if net_flow_5days is not None:
                        if abs(net_flow_5days) < 0.01:
                            main_net_flow_var.set("0.00 万元")
                            main_net_flow_label.configure(foreground="blue")
                        else:
                            color = "red" if net_flow_5days > 0 else "green"
                            main_net_flow_var.set(f"{net_flow_5days:+.2f} 万元")
                            main_net_flow_label.configure(foreground=color)
                        # 显示详情到文本区域
                        detail_text_area.config(state=tk.NORMAL)
                        detail_text_area.delete("1.0", tk.END)
                        if daily_details:
                            detail_text = "每日净资金流入详情:\n" + "\n".join(daily_details)
                            detail_text_area.insert("1.0", detail_text)
                        else:
                            detail_text_area.insert("1.0", "暂无每日详情数据")
                        detail_text_area.config(state=tk.DISABLED)
                        main_net_flow_status_var.set(f"已获取({data_source})")
                    else:
                        main_net_flow_var.set("获取失败")
                        main_net_flow_status_var.set("无法获取数据")
                        detail_text_area.config(state=tk.NORMAL)
                        detail_text_area.delete("1.0", tk.END)
                        detail_text_area.insert("1.0", "获取失败:请检查网络连接或数据源")
                        detail_text_area.config(state=tk.DISABLED)
                        messagebox.showwarning("提示", "无法获取最近5天净资金流入数据,请检查网络连接或数据源", parent=dialog)
                except Exception as e:
                    main_net_flow_var.set("获取失败")
                    main_net_flow_status_var.set(f"错误: {str(e)[:30]}")
                    detail_text_area.config(state=tk.NORMAL)
                    detail_text_area.delete("1.0", tk.END)
                    detail_text_area.insert("1.0", f"获取失败:{e!s}")
                    detail_text_area.config(state=tk.DISABLED)
                    messagebox.showerror("错误", f"获取最近5天净资金流入失败: {e}", parent=dialog)
            # 按钮
            button_frame_netflow = ttk.Frame(net_flow_frame)
            button_frame_netflow.pack(fill=tk.X, pady=(10, 0))
            ttk.Button(button_frame_netflow, text="获取最近5天净流入", command=fetch_main_net_flow, width=20).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame_netflow, text="刷新", command=fetch_main_net_flow, width=15).pack(side=tk.LEFT, padx=5)
            # 说明文字
            note_text = "说明:\n1. 最近5天净资金流入为正值表示主力资金总体净流入,通常意味着看涨信号\n2. 为负值表示主力资金总体净流出,通常意味着看跌信号\n3. 数值越大,资金流入/流出越明显\n4. 如果使用AKShare估算,数据仅供参考,建议结合技术指标和基本面综合分析"
            note_label = ttk.Label(net_flow_frame, text=note_text, wraplength=500,
                                  justify=tk.LEFT, foreground="gray")
            note_label.pack(anchor=tk.W, pady=(15, 0))
            # 5日线检测区域(上排右边)
            ma5_frame = ttk.LabelFrame(ma_top_row, text="5日线检测(必须条件)", padding=8)
            ma5_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
            ma5_price_row = ttk.Frame(ma5_frame)
            ma5_price_row.pack(fill=tk.X, pady=2)
            ttk.Label(ma5_price_row, text="参考5日线:", width=10).pack(side=tk.LEFT)
            ttk.Label(ma5_price_row, textvariable=ma5_reference_var, foreground="green").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(ma5_price_row, text="前5日均价:", width=10).pack(side=tk.LEFT)
            ttk.Label(ma5_price_row, textvariable=ma5_prev_var, foreground="green").pack(side=tk.LEFT)
            ma5_status_row = ttk.Frame(ma5_frame)
            ma5_status_row.pack(fill=tk.X, pady=2)
            ma5_status_label = tk.Label(ma5_status_row, textvariable=ma5_status_var, foreground="blue", font=("TkDefaultFont", 11))
            ma5_status_label.pack(side=tk.LEFT)
            ma5_cross_check = ttk.Checkbutton(
                ma5_frame, text="股价站上5日线", variable=ma5_crossed_var, state=tk.DISABLED
            )
            ma5_cross_check.pack(anchor=tk.W, pady=2)
            ma5_uptrend_check = ttk.Checkbutton(
                ma5_frame, text="5日线向上发散", variable=ma5_uptrend_var, state=tk.DISABLED
            )
            ma5_uptrend_check.pack(anchor=tk.W, pady=2)
            ma5_button_row = ttk.Frame(ma5_frame)
            ma5_button_row.pack(fill=tk.X, pady=4)
            ttk.Button(ma5_button_row, text="默认数据检测", command=lambda: fetch_ma5_status("default")).pack(side=tk.LEFT, padx=5)
            # 10日线检测区域(下排左边)
            ma10_frame = ttk.LabelFrame(ma_bottom_row, text="10日线检测(必须条件)", padding=8)
            ma10_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
            ma10_price_row = ttk.Frame(ma10_frame)
            ma10_price_row.pack(fill=tk.X, pady=2)
            ttk.Label(ma10_price_row, text="参考10日线:", width=10).pack(side=tk.LEFT)
            ttk.Label(ma10_price_row, textvariable=ma10_reference_var, foreground="green").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(ma10_price_row, text="前10日均价:", width=10).pack(side=tk.LEFT)
            ttk.Label(ma10_price_row, textvariable=ma10_prev_var, foreground="green").pack(side=tk.LEFT)
            ma10_status_row = ttk.Frame(ma10_frame)
            ma10_status_row.pack(fill=tk.X, pady=2)
            ma10_status_label = tk.Label(ma10_status_row, textvariable=ma10_status_var, foreground="blue", font=("TkDefaultFont", 11))
            ma10_status_label.pack(side=tk.LEFT)
            volume_info_frame = ttk.Frame(ma10_frame)
            volume_info_frame.pack(fill=tk.X, pady=(4, 0))
            ttk.Label(volume_info_frame, text="5日均量:", width=8).pack(side=tk.LEFT)
            ttk.Label(volume_info_frame, textvariable=volume_5day_avg_var, foreground="purple").pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(volume_info_frame, text="10日均量:", width=9).pack(side=tk.LEFT)
            ttk.Label(volume_info_frame, textvariable=volume_10day_avg_var, foreground="purple").pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(ma10_frame, textvariable=volume_trend_var, foreground="blue").pack(anchor=tk.W, pady=(2, 0))
            ma10_cross_check = ttk.Checkbutton(
                ma10_frame, text="股价站上10日线", variable=ma10_crossed_var, state=tk.DISABLED
            )
            ma10_cross_check.pack(anchor=tk.W, pady=2)
            ma10_uptrend_check = ttk.Checkbutton(
                ma10_frame, text="10日线向上发散", variable=ma10_uptrend_var, state=tk.DISABLED
            )
            ma10_uptrend_check.pack(anchor=tk.W, pady=2)
            ma10_button_row = ttk.Frame(ma10_frame)
            ma10_button_row.pack(fill=tk.X, pady=4)
            ttk.Button(ma10_button_row, text="默认数据检测", command=lambda: fetch_ma10_status("default")).pack(side=tk.LEFT, padx=5)
            # 20日线检测区域(下排右边)
            ma20_frame = ttk.LabelFrame(ma_bottom_row, text="20日线检测(必须条件)", padding=8)
            ma20_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
            ma20_price_row = ttk.Frame(ma20_frame)
            ma20_price_row.pack(fill=tk.X, pady=2)
            ttk.Label(ma20_price_row, text="参考20日线:", width=10).pack(side=tk.LEFT)
            ttk.Label(ma20_price_row, textvariable=ma20_reference_var, foreground="green").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(ma20_price_row, text="前20日均价:", width=10).pack(side=tk.LEFT)
            ttk.Label(ma20_price_row, textvariable=ma20_prev_var, foreground="green").pack(side=tk.LEFT)
            ma20_status_row = ttk.Frame(ma20_frame)
            ma20_status_row.pack(fill=tk.X, pady=2)
            ma20_status_label = tk.Label(ma20_status_row, textvariable=ma20_status_var, foreground="blue", font=("TkDefaultFont", 11))
            ma20_status_label.pack(side=tk.LEFT)
            ma20_cross_check = ttk.Checkbutton(
                ma20_frame, text="股价站上20日线", variable=ma20_crossed_var, state=tk.DISABLED
            )
            ma20_cross_check.pack(anchor=tk.W, pady=2)
            ma20_uptrend_check = ttk.Checkbutton(
                ma20_frame, text="20日线向上发散", variable=ma20_uptrend_var, state=tk.DISABLED
            )
            ma20_uptrend_check.pack(anchor=tk.W, pady=2)
            ma20_button_row = ttk.Frame(ma20_frame)
            ma20_button_row.pack(fill=tk.X, pady=4)
            ttk.Button(ma20_button_row, text="默认数据检测", command=lambda: fetch_ma20_status("default")).pack(side=tk.LEFT, padx=5)
            # 显示主界面仓位计算结果(只读)
            ttk.Label(stock_name_row, text="主界面仓位:", font=("TkDefaultFont", 12)).pack(side=tk.LEFT, padx=(0, 5))
            position_value_label = ttk.Label(stock_name_row, textvariable=position_result_var,
                                            font=("TkDefaultFont", 12, "bold"), foreground="blue")
            position_value_label.pack(side=tk.LEFT)
            # 交易法则显示区域已移到右下区域
            # 案例管理已移到右侧"案例管理"标签页
            # 定义案例变量(用于保存)
            success_case_var = tk.StringVar()
            fail_case_var = tk.StringVar()
            # 三维问询按钮
            def show_three_dimension_analysis():
                """显示三维问询界面"""
                try:
                    win = self._toplevel(dialog)
                    win.title("三维问询分析")
                    win.geometry("1200x720")
                    win.transient(dialog)
                    win.resizable(True, True)
                    # 存储窗口状态
                    win._is_minimized = False
                    win._original_geometry = "1200x720"
                    # 配置窗口布局
                    win.columnconfigure(0, weight=1)
                    win.columnconfigure(1, weight=1)
                    win.rowconfigure(1, weight=1)
                    # 头部说明
                    header = ttk.Label(
                        win,
                        text="三维问询分析 - 股票指数基本面、外围市场情况、市场情绪",
                        anchor="center",
                        font=("Microsoft YaHei", 14, "bold")
                    )
                    header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
                    # 左侧:问题描述
                    left_frame = ttk.LabelFrame(win, text="问题描述", padding=10)
                    left_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
                    left_frame.columnconfigure(0, weight=1)
                    left_frame.rowconfigure(1, weight=1)
                    problem_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=20, font=("TkDefaultFont", 12))
                    problem_text.grid(row=1, column=0, sticky="nsew")
                    # 设置默认问题
                    default_question = """根据目前股票指数基本面,外围的市场情况,市场的情绪三个方面来分析,根据每个最高33.3分,加起来,看看可以得多少分。"""
                    problem_text.insert("1.0", default_question)
                    # 右侧:分析结果
                    right_frame = ttk.LabelFrame(win, text="分析结果", padding=10)
                    right_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
                    right_frame.columnconfigure(0, weight=1)
                    right_frame.rowconfigure(1, weight=1)
                    # 结果显示方式选择
                    display_mode_frame = ttk.Frame(right_frame)
                    display_mode_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
                    ttk.Label(display_mode_frame, text="结果显示方式:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
                    display_mode_var = tk.StringVar(value="累计显示")
                    ttk.Radiobutton(display_mode_frame, text="累计显示", variable=display_mode_var,
                                   value="累计显示").pack(side=tk.LEFT, padx=5)
                    ttk.Radiobutton(display_mode_frame, text="新标签页", variable=display_mode_var,
                                   value="新标签页").pack(side=tk.LEFT, padx=5)
                    # 根据情绪周期确定背景颜色
                    if hasattr(self, 'get_emotion_bg_color'):
                        result_bg_color = self.get_emotion_bg_color()
                    else:
                        result_bg_color = "white"
                    result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, height=20, font=("TkDefaultFont", 12),
                                                           state=tk.DISABLED, bg=result_bg_color)
                    result_text.grid(row=1, column=0, sticky="nsew")
                    self._enable_clickable_links(result_text)
                    self._enable_clickable_links(result_text)
                    # 保存引用以便后续更新背景颜色
                    if not hasattr(self, '_analysis_result_text_widgets'):
                        self._analysis_result_text_widgets = []
                    self._analysis_result_text_widgets.append(result_text)
                    # 底部:三个维度按钮
                    control_frame = ttk.LabelFrame(win, text="分析维度", padding=10)
                    control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
                    # 三个维度选项
                    dimension_options = {
                        "股票指数基本面": "分析当前股票指数(如上证指数、深证成指、创业板指等)的基本面情况,包括宏观经济环境、政策导向、估值水平、资金流向等",
                        "外围的市场情况": "分析外围市场情况,包括美股、港股、欧洲股市、日韩股市等主要市场的走势、政策变化、经济数据等",
                        "市场的情绪": "分析市场情绪,包括投资者情绪、恐慌指数、市场热度、资金风险偏好、技术面情绪等"
                    }
                    # 创建按钮
                    buttons_per_row = 3
                    row = 0
                    col = 0
                    for option_name, option_desc in dimension_options.items():
                        btn = ttk.Button(
                            control_frame,
                            text=option_name,
                            command=lambda name=option_name, desc=option_desc: run_dimension_analysis(name, desc),
                            width=25
                        )
                        btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
                        col += 1
                        if col >= buttons_per_row:
                            col = 0
                            row += 1
                    # 配置列权重
                    for i in range(buttons_per_row):
                        control_frame.columnconfigure(i, weight=1)
                    def get_dimension_prompt(dimension_name, dimension_desc, problem):
                        """生成维度分析提示"""
                        return f"""请针对以下维度进行专业分析:
分析维度:{dimension_name}
维度说明:{dimension_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该维度的当前状况和关键指标
2. 该维度对市场的影响程度
3. 该维度的评分(0-33.3分)及评分理由
4. 该维度的风险提示和注意事项
5. 基于该维度的投资建议"""
                    def run_dimension_analysis(option_name, option_desc):
                        """运行维度分析"""
                        problem = problem_text.get("1.0", tk.END).strip()
                        if not problem:
                            problem = default_question
                        # 获取显示方式
                        display_mode = display_mode_var.get()
                        # 生成提示
                        prompt = get_dimension_prompt(option_name, option_desc, problem)
                        # 存储分析状态
                        analysis_info = {
                            'option_name': option_name,
                            'option_desc': option_desc,
                            'display_mode': display_mode,
                            'target_text': None,
                            'tab_id': None,
                            'analysis_start_pos': None
                        }
                        # 根据显示方式处理
                        if display_mode == "新标签页":
                            # 创建新标签页
                            from datetime import datetime
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            tab_title = f"三维问询-{option_name}-{current_time}"
                            tab_id = self.create_result_tab(tab_title)
                            target_text = self.result_tabs[tab_id]['widget']
                            analysis_info['target_text'] = target_text
                            analysis_info['tab_id'] = tab_id
                            # 显示分析中
                            target_text.config(state=tk.NORMAL)
                            target_text.delete("1.0", tk.END)
                            target_text.insert(tk.END, f"[{option_name}] 正在分析...\n\n")
                            target_text.insert(tk.END, f"维度说明:{option_desc}\n\n")
                            target_text.config(state=tk.DISABLED)
                        else:
                            # 累计显示在当前界面
                            target_text = result_text
                            analysis_info['target_text'] = target_text
                            target_text.config(state=tk.NORMAL)
                            # 记录插入位置
                            analysis_info['analysis_start_pos'] = target_text.index(tk.END)
                            # 追加内容,不清空
                            current_content = target_text.get("1.0", tk.END)
                            if current_content.strip():
                                target_text.insert(tk.END, "\n" + "="*80 + "\n\n")
                            target_text.insert(tk.END, f"[{option_name}] 正在分析...\n\n")
                            target_text.insert(tk.END, f"维度说明:{option_desc}\n\n")
                            target_text.config(state=tk.DISABLED)
                        # 异步调用AI
                        def analyze():
                            try:
                                system_prompt = "你是一位资深的市场分析专家,能够从多个维度深入分析市场状况,提供专业的评分和建议。"
                                ai_result = self.call_ai_model(prompt, system_prompt)
                                if not ai_result:
                                    ai_result = f"【{option_name}分析】\n\n{option_desc}\n\n请结合您的问题进行深入分析。"
                            except Exception as e:
                                ai_result = f"AI分析失败: {e}\n\n{option_desc}"
                            def update_ui():
                                target_text = analysis_info['target_text']
                                display_mode = analysis_info['display_mode']
                                target_text.config(state=tk.NORMAL)
                                if display_mode == "新标签页":
                                    # 新标签页:替换内容
                                    target_text.delete("1.0", tk.END)
                                    target_text.insert(tk.END, f"[{analysis_info['option_name']}] 分析结果\n\n")
                                    target_text.insert(tk.END, f"维度说明:{analysis_info['option_desc']}\n\n")
                                    target_text.insert(tk.END, "="*50 + "\n\n")
                                    target_text.insert(tk.END, ai_result)
                                    target_text.see("1.0")
                                else:
                                    # 累计显示:删除"正在分析"部分,替换为结果
                                    start_pos = analysis_info.get('analysis_start_pos')
                                    if start_pos:
                                        # 删除从开始位置到末尾的内容
                                        target_text.delete(start_pos, tk.END)
                                        # 插入结果
                                        target_text.insert(tk.END, f"[{analysis_info['option_name']}] 分析结果\n\n")
                                        target_text.insert(tk.END, f"维度说明:{analysis_info['option_desc']}\n\n")
                                        target_text.insert(tk.END, "="*50 + "\n\n")
                                        target_text.insert(tk.END, ai_result + "\n")
                                        target_text.see(tk.END)
                                target_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                        threading.Thread(target=analyze, daemon=True).start()
                    def run_comprehensive_analysis():
                        """运行综合分析"""
                        problem = problem_text.get("1.0", tk.END).strip()
                        if not problem:
                            problem = default_question
                        # 获取显示方式
                        display_mode = display_mode_var.get()
                        # 存储分析状态
                        analysis_info = {
                            'display_mode': display_mode,
                            'target_text': None,
                            'tab_id': None,
                            'analysis_start_pos': None
                        }
                        # 根据显示方式处理
                        if display_mode == "新标签页":
                            # 创建新标签页
                            from datetime import datetime
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            tab_title = f"三维问询-综合分析-{current_time}"
                            tab_id = self.create_result_tab(tab_title)
                            target_text = self.result_tabs[tab_id]['widget']
                            analysis_info['target_text'] = target_text
                            analysis_info['tab_id'] = tab_id
                            target_text.config(state=tk.NORMAL)
                            target_text.delete("1.0", tk.END)
                            target_text.insert(tk.END, "正在综合分析三个维度...\n\n")
                            target_text.config(state=tk.DISABLED)
                        else:
                            # 累计显示在当前界面
                            target_text = result_text
                            analysis_info['target_text'] = target_text
                            target_text.config(state=tk.NORMAL)
                            # 记录插入位置
                            analysis_info['analysis_start_pos'] = target_text.index(tk.END)
                            # 追加内容,不清空
                            current_content = target_text.get("1.0", tk.END)
                            if current_content.strip():
                                target_text.insert(tk.END, "\n" + "="*80 + "\n\n")
                            target_text.insert(tk.END, "正在综合分析三个维度...\n\n")
                            target_text.config(state=tk.DISABLED)
                        def analyze():
                            try:
                                comprehensive_prompt = f"""请根据以下三个维度进行综合分析:
{problem}
请分别分析以下三个维度,每个维度最高33.3分,总分100分:
1. 股票指数基本面:分析当前股票指数的基本面情况
2. 外围的市场情况:分析外围市场的情况
3. 市场的情绪:分析市场情绪状况
请为每个维度提供:
- 当前状况分析
- 评分(0-33.3分)
- 评分理由
- 风险提示
最后提供:
- 总分(三个维度分数相加)
- 综合判断
- 投资建议"""
                                system_prompt = "你是一位资深的市场分析专家,能够从多个维度深入分析市场状况,提供专业的评分和建议。"
                                ai_result = self.call_ai_model(comprehensive_prompt, system_prompt)
                                if not ai_result:
                                    ai_result = "未获取到AI分析结果,请检查配置。"
                            except Exception as e:
                                ai_result = f"AI分析失败: {e}"
                            def update_ui():
                                target_text = analysis_info['target_text']
                                display_mode = analysis_info['display_mode']
                                target_text.config(state=tk.NORMAL)
                                if display_mode == "新标签页":
                                    # 新标签页:替换内容
                                    target_text.delete("1.0", tk.END)
                                    target_text.insert(tk.END, "【三维综合分析结果】\n\n")
                                    target_text.insert(tk.END, "="*50 + "\n\n")
                                    target_text.insert(tk.END, ai_result)
                                    target_text.see("1.0")
                                else:
                                    # 累计显示:删除"正在分析"部分,替换为结果
                                    start_pos = analysis_info.get('analysis_start_pos')
                                    if start_pos:
                                        # 删除从开始位置到末尾的内容
                                        target_text.delete(start_pos, tk.END)
                                        # 插入结果
                                        target_text.insert(tk.END, "【三维综合分析结果】\n\n")
                                        target_text.insert(tk.END, "="*50 + "\n\n")
                                        target_text.insert(tk.END, ai_result + "\n")
                                        target_text.see(tk.END)
                                target_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                        threading.Thread(target=analyze, daemon=True).start()
                    # 按钮区域
                    button_frame = ttk.Frame(control_frame)
                    button_frame.grid(row=row+1, column=0, columnspan=buttons_per_row, pady=(10, 0), sticky="ew")
                    ttk.Button(button_frame, text="综合分析",
                              command=run_comprehensive_analysis).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="清空",
                              command=lambda: [problem_text.delete("1.0", tk.END), result_text.config(state=tk.NORMAL), result_text.delete("1.0", tk.END), result_text.config(state=tk.DISABLED)]).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="复制结果",
                              command=lambda: self._copy_result(result_text)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="添加到咨询",
                              command=lambda: self._add_to_consultation(result_text)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="添加到警示",
                              command=lambda: self._add_to_warning(result_text)).pack(side=tk.LEFT, padx=5)
                    # 窗口控制按钮
                    control_btn_frame = ttk.Frame(win)
                    control_btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
                    def toggle_minimize():
                        """切换最小化/恢复"""
                        if win._is_minimized:
                            win.geometry(win._original_geometry)
                            win._is_minimized = False
                            minimize_btn.config(text="最小化")
                        else:
                            win._original_geometry = win.geometry()
                            win.geometry("200x50")
                            win._is_minimized = True
                            minimize_btn.config(text="恢复")
                    def toggle_maximize():
                        """切换最大化/恢复"""
                        try:
                            # Windows平台使用state('zoomed')
                            if win.state() == 'zoomed':
                                win.state('normal')
                                win.geometry(win._original_geometry)
                                maximize_btn.config(text="最大化")
                            else:
                                win._original_geometry = win.geometry()
                                win.state('zoomed')
                                maximize_btn.config(text="恢复")
                        except:
                            # 如果state不支持,尝试使用geometry
                            try:
                                current_geom = win.geometry()
                                if hasattr(win, '_is_maximized') and win._is_maximized:
                                    win.geometry(win._original_geometry)
                                    win._is_maximized = False
                                    maximize_btn.config(text="最大化")
                                else:
                                    win._original_geometry = current_geom
                                    # 获取屏幕尺寸
                                    screen_width = win.winfo_screenwidth()
                                    screen_height = win.winfo_screenheight()
                                    win.geometry(f"{screen_width}x{screen_height}+0+0")
                                    win._is_maximized = True
                                    maximize_btn.config(text="恢复")
                            except Exception as e:
                                messagebox.showinfo("提示", f"最大化功能不可用: {e}")
                    minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
                    minimize_btn.pack(side=tk.LEFT, padx=5)
                    maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
                    maximize_btn.pack(side=tk.LEFT, padx=5)
                    ttk.Button(control_btn_frame, text="隐藏", command=win.withdraw, width=10).pack(side=tk.LEFT, padx=5)
                    ttk.Button(control_btn_frame, text="显示", command=win.deiconify, width=10).pack(side=tk.LEFT, padx=5)
                    ttk.Button(control_btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.RIGHT, padx=5)
                except Exception as e:
                    messagebox.showerror("错误", f"打开三维问询界面失败: {e}")
                    import traceback
                    traceback.print_exc()
            # 必须条件和可选条件变量(用于右侧面板)
            # 默认必须条件
            default_required = [
                "主界面总分 > 40分",
                "同花顺情绪指数:1日线往上和在1日线上(两个勾选框都勾选)",
                "60分钟5日10日多头发散 或 15分钟多头发散",
                "股价需要站上1日线",
                "1日线保持向上发散",
                "股价需要站上5日线",
                "5日线保持向上发散",
                "股价需要站上10日线",
                "10日线保持向上发散",
                "股价需要站上20日线",
                "20日线保持向上发散",
                "仓位计算结果 >= 30%",
                "凯利公式计算结果 > 0"
            ]
            # 默认可选条件
            default_optional = [
                "基本面分析支持",
                "资金流向良好",
                "行业趋势向上"
            ]
            # 同花顺情绪指数变量:使用 self.sentiment_index_*(与定时弹窗「上行/震荡/下行」及配置联动)
            # 多头发散变量
            divergence_60m_var = tk.BooleanVar(value=False)
            divergence_15m_var = tk.BooleanVar(value=False)
            # 主界面总分检查变量
            main_score_check_var = tk.BooleanVar(value=False)
            # 更新主界面总分检查状态
            def update_main_score_check():
                try:
                    score_text = total_score_var.get().replace("总分: ", "").strip()
                    score = int(score_text) if score_text.isdigit() else 0
                    if score > 40:
                        main_score_check_var.set(True)
                    else:
                        main_score_check_var.set(False)
                except:
                    main_score_check_var.set(False)
            # 更新同花顺情绪指数检查状态(与主窗口 self.sentiment_index_* 及定时弹窗联动)
            def update_sentiment_index_check():
                self._update_sentiment_index_check_coord()
            # 绑定事件(同花顺勾选框的 trace 已在主窗口 __init__ 中注册)
            total_score_var.trace_add("write", lambda *args: update_main_score_check())
            update_main_score_check()
            # 凯利公式计算区域
            kelly_frame = ttk.LabelFrame(main_frame, text="凯利公式仓位计算", padding=10)
            kelly_frame.pack(fill=tk.X, pady=(0, 8))
            kelly_input_frame = ttk.Frame(kelly_frame)
            kelly_input_frame.pack(fill=tk.X)
            ttk.Label(kelly_input_frame, text="盈亏比 (b):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
            odds_var = tk.StringVar(value="1.0")
            ttk.Entry(kelly_input_frame, textvariable=odds_var, width=15).grid(row=0, column=1, padx=5, pady=5)
            ttk.Label(kelly_input_frame, text="胜率 (p):").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
            prob_var = tk.StringVar(value="0.5")
            ttk.Entry(kelly_input_frame, textvariable=prob_var, width=15).grid(row=0, column=3, padx=5, pady=5)
            kelly_result_var = tk.StringVar(value="0.00%")
            kelly_result_label = ttk.Label(kelly_input_frame, textvariable=kelly_result_var,
                                          font=("TkDefaultFont", 12, "bold"), foreground="blue")
            kelly_result_label.grid(row=0, column=4, padx=10, pady=5)
            kelly_calc_btn = ttk.Button(kelly_input_frame, text="计算凯利", command=lambda: calculate_kelly())
            kelly_calc_btn.grid(row=0, column=5, padx=5, pady=5)
            kelly_check_var = tk.BooleanVar(value=False)
            kelly_check = ttk.Checkbutton(kelly_frame, text="凯利公式计算结果确认", variable=kelly_check_var)
            kelly_check.pack(anchor=tk.W, padx=5, pady=3)
            def calculate_kelly():
                """计算凯利公式"""
                try:
                    odds_value = float(odds_var.get())
                    prob_value = float(prob_var.get())
                    if odds_value <= 0:
                        messagebox.showerror("输入错误", "盈亏比必须大于0")
                        return
                    if prob_value <= 0 or prob_value >= 1:
                        messagebox.showerror("输入错误", "胜率必须在0到1之间")
                        return
                    kelly_value = prob_value - (1 - prob_value) / odds_value
                    kelly_result_var.set(f"{kelly_value * 100:.2f}%")
                    if kelly_value > 0:
                        kelly_check_var.set(True)
                    else:
                        kelly_check_var.set(False)
                        messagebox.showwarning("警告", "凯利公式计算结果 <= 0,不建议开仓")
                except ValueError:
                    messagebox.showerror("输入错误", "请输入有效的数字")
            # 选股逻辑输入区域
            logic_frame = ttk.LabelFrame(main_frame, text="选股逻辑", padding=10)
            logic_frame.pack(fill=tk.X, pady=(0, 8))
            ttk.Label(logic_frame, text="选股逻辑:").grid(row=0, column=0, padx=5, pady=3, sticky=tk.NW)
            logic_text = scrolledtext.ScrolledText(logic_frame, height=3, wrap=tk.WORD)
            logic_text.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
            logic_frame.columnconfigure(1, weight=1)
            # 判断按钮
            def judge_new_position():
                """判断是否可以开新仓"""
                # 检查股票名称
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    messagebox.showwarning("警告", "请输入股票名称", parent=dialog)
                    return
                # 检查主界面总分
                try:
                    score_text = total_score_var.get().replace("总分: ", "").strip()
                    main_total_score = int(score_text) if score_text.isdigit() else 0
                except:
                    main_total_score = 0
                if main_total_score <= 40:
                    messagebox.showwarning("警告", f"主界面总分 {main_total_score} 分必须大于40分,不可以开仓", parent=dialog)
                    return
                # 检查同花顺情绪指数(两个勾选框都勾选上)
                if not self.sentiment_index_ma1_uptrend_var.get() or not self.sentiment_index_ma1_above_var.get():
                    messagebox.showwarning("警告", "同花顺情绪指数:必须勾选'1日线往上'和'在1日线上'两个条件,不可以开仓", parent=dialog)
                    return
                # 获取仓位类型,判断是否需要简化均线检测
                position_type = dialog.title().replace("开", "").replace("新仓流程", "")
                is_simplified_ma_check = position_type in ["朋友", "绩优股", "均值回归"]
                if is_simplified_ma_check:
                    # 朋友新仓、绩优股新仓、均值回归新仓:只检查20日均线
                    if not ma20_data_ready_var.get():
                        messagebox.showwarning("警告", "请先检测20日线状态", parent=dialog)
                    return
                    if not ma20_crossed_var.get():
                        messagebox.showwarning("警告", "股价未站上20日线,不可以开仓", parent=dialog)
                        return
                    if not ma20_uptrend_var.get():
                        messagebox.showwarning("警告", "20日线未向上发散,不可以开仓", parent=dialog)
                        return
                else:
                    # 其他仓位类型:检查所有均线
                    # 检查多头发散
                    # 检查1日线状态
                    if not ma1_data_ready_var.get():
                        messagebox.showwarning("警告", "请先检测1日线状态", parent=dialog)
                        return
                    if not ma1_crossed_var.get():
                        messagebox.showwarning("警告", "股价未站上1日线,不可以开仓", parent=dialog)
                        return
                    # 去除1日线向上发散条件检查
                    # if not ma1_uptrend_var.get():
                    #     messagebox.showwarning("警告", "1日线未向上发散,不可以开仓", parent=dialog)
                    #     return
                # 检查5日线状态
                if not ma5_data_ready_var.get():
                    messagebox.showwarning("警告", "请先检测5日线状态", parent=dialog)
                    return
                if not ma5_crossed_var.get():
                    messagebox.showwarning("警告", "股价未站上5日线,不可以开仓", parent=dialog)
                    return
                if not ma5_uptrend_var.get():
                    messagebox.showwarning("警告", "5日线未向上发散,不可以开仓", parent=dialog)
                    return
                # 检查10日线状态
                if not ma10_data_ready_var.get():
                    messagebox.showwarning("警告", "请先检测10日线状态", parent=dialog)
                    return
                if not ma10_crossed_var.get():
                    messagebox.showwarning("警告", "股价未站上10日线,不可以开仓", parent=dialog)
                    return
                if not ma10_uptrend_var.get():
                    messagebox.showwarning("警告", "10日线未向上发散,不可以开仓", parent=dialog)
                    return
                # 检查20日线状态
                if not ma20_data_ready_var.get():
                    messagebox.showwarning("警告", "请先检测20日线状态", parent=dialog)
                    return
                if not ma20_crossed_var.get():
                    messagebox.showwarning("警告", "股价未站上20日线,不可以开仓", parent=dialog)
                    return
                if not ma20_uptrend_var.get():
                    messagebox.showwarning("警告", "20日线未向上发散,不可以开仓", parent=dialog)
                    return
                # 检查凯利公式计算结果
                if not kelly_check_var.get():
                    messagebox.showwarning("警告", "请确认凯利公式计算结果", parent=dialog)
                    return
                # 获取主界面仓位值
                position_text = position_result_var.get().replace("+", "").replace("%", "")
                try:
                    main_position = float(position_text)
                except:
                    main_position = 0
                # 获取凯利公式仓位值
                kelly_result = kelly_result_var.get().replace("%", "")
                try:
                    kelly_percent = float(kelly_result)
                except:
                    kelly_percent = 0
                # 获取仓位类型,判断是否需要简化均线检测
                position_type = dialog.title().replace("开", "").replace("新仓流程", "")
                is_simplified_ma_check = position_type in ["朋友", "绩优股", "均值回归"]
                # 判断结果(所有条件都满足,去除1日线向上发散条件)
                if is_simplified_ma_check:
                    # 朋友新仓、绩优股新仓、均值回归新仓:只检查20日均线
                    can_open = (main_total_score > 40 and
                                   self.sentiment_index_ma1_uptrend_var.get() and  # 同花顺情绪指数:1日线往上
                                   self.sentiment_index_ma1_above_var.get() and  # 同花顺情绪指数:在1日线上
                                   ma20_data_ready_var.get() and
                                   ma20_crossed_var.get() and
                                   ma20_uptrend_var.get() and
                                   main_score_check_var.get() and
                                   self.sentiment_index_check_var.get() and  # 同花顺情绪指数检查
                                   kelly_check_var.get() and
                                   main_position >= 30)
                else:
                    # 其他仓位类型:检查所有均线
                    can_open = (main_total_score > 40 and
                               self.sentiment_index_ma1_uptrend_var.get() and  # 同花顺情绪指数:1日线往上
                               self.sentiment_index_ma1_above_var.get() and  # 同花顺情绪指数:在1日线上
                           (divergence_60m_var.get() or divergence_15m_var.get()) and
                           ma1_data_ready_var.get() and
                           ma1_crossed_var.get() and
                               # ma1_uptrend_var.get() and  # 去除1日线向上发散条件
                           ma5_data_ready_var.get() and
                           ma5_crossed_var.get() and
                           ma5_uptrend_var.get() and
                           ma10_data_ready_var.get() and
                           ma10_crossed_var.get() and
                           ma10_uptrend_var.get() and
                           ma20_data_ready_var.get() and
                           ma20_crossed_var.get() and
                           ma20_uptrend_var.get() and
                           main_score_check_var.get() and
                               self.sentiment_index_check_var.get() and  # 同花顺情绪指数检查
                           kelly_check_var.get() and
                           main_position >= 30)
                # 显示判断结果弹出框
                result_dialog = self._toplevel(dialog)
                result_dialog.title("开新仓判断结果")
                result_dialog.geometry("500x400")
                result_frame = ttk.Frame(result_dialog, padding=20)
                result_frame.pack(fill=tk.BOTH, expand=True)
                if can_open:
                    position_type = dialog.title().replace("开", "").replace("新仓流程", "")
                    result_text = f"{stock_name}\n可以开{position_type}新仓\n凯利公式仓位: {kelly_percent:.2f}%"
                    result_color = "green"
                else:
                    position_type = dialog.title().replace("开", "").replace("新仓流程", "")
                    result_text = f"{stock_name}\n不可以开{position_type}新仓\n原因:\n"
                    if main_total_score <= 40:
                        result_text += f"- 主界面总分 {main_total_score} 分 <= 40分\n"
                    if not self.sentiment_index_ma1_uptrend_var.get() or not self.sentiment_index_ma1_above_var.get():
                        result_text += "- 同花顺情绪指数:未勾选'1日线往上'或'在1日线上'\n"
                    # 获取仓位类型,判断是否需要简化均线检测
                    position_type = dialog.title().replace("开", "").replace("新仓流程", "")
                    is_simplified_ma_check = position_type in ["朋友", "绩优股", "均值回归"]
                    if is_simplified_ma_check:
                        # 朋友新仓、绩优股新仓、均值回归新仓:只检查20日均线
                        if not ma20_data_ready_var.get():
                            result_text += "- 未检测20日线状态\n"
                        if ma20_data_ready_var.get() and not ma20_crossed_var.get():
                            result_text += "- 股价尚未站上20日线\n"
                        if ma20_data_ready_var.get() and not ma20_uptrend_var.get():
                            result_text += "- 20日线未向上发散\n"
                    else:
                        # 其他仓位类型:检查所有均线
                        if not divergence_60m_var.get() and not divergence_15m_var.get():
                            result_text += "- 未满足多头发散条件(60分钟或15分钟)\n"
                        if not ma1_data_ready_var.get():
                            result_text += "- 未检测1日线状态\n"
                        if ma1_data_ready_var.get() and not ma1_crossed_var.get():
                            result_text += "- 股价尚未站上1日线\n"
                                # 去除1日线向上发散条件检查
                                # if ma1_data_ready_var.get() and not ma1_uptrend_var.get():
                                #     result_text += "- 1日线未向上发散\n"
                        if not ma5_data_ready_var.get():
                            result_text += "- 未检测5日线状态\n"
                        if ma5_data_ready_var.get() and not ma5_crossed_var.get():
                            result_text += "- 股价尚未站上5日线\n"
                        if ma5_data_ready_var.get() and not ma5_uptrend_var.get():
                            result_text += "- 5日线未向上发散\n"
                        if not ma10_data_ready_var.get():
                            result_text += "- 未检测10日线状态\n"
                        if ma10_data_ready_var.get() and not ma10_crossed_var.get():
                            result_text += "- 股价尚未站上10日线\n"
                        if ma10_data_ready_var.get() and not ma10_uptrend_var.get():
                            result_text += "- 10日线未向上发散\n"
                        if not ma20_data_ready_var.get():
                            result_text += "- 未检测20日线状态\n"
                        if ma20_data_ready_var.get() and not ma20_crossed_var.get():
                            result_text += "- 股价尚未站上20日线\n"
                        if ma20_data_ready_var.get() and not ma20_uptrend_var.get():
                            result_text += "- 20日线未向上发散\n"
                        if not main_score_check_var.get():
                            result_text += "- 主界面总分未满足条件\n"
                        if not self.sentiment_index_check_var.get():
                            result_text += "- 同花顺情绪指数:未勾选'1日线往上'或'在1日线上'\n"
                        if not kelly_check_var.get():
                            result_text += "- 凯利公式计算结果未确认\n"
                        if main_position < 30:
                            result_text += f"- 主界面仓位 {main_position:.1f}% < 30%\n"
                    result_color = "red"
                result_label = ttk.Label(result_frame, text=result_text,
                                        font=("TkDefaultFont", 14, "bold"),
                                        foreground=result_color,
                                        justify=tk.CENTER)
                result_label.pack(expand=True, fill=tk.BOTH)
                ttk.Button(result_frame, text="关闭", command=result_dialog.destroy).pack(pady=10)
            def confirm_new_position():
                """确认开新仓"""
                # 获取仓位类型
                position_type = dialog.title().replace("开", "").replace("新仓流程", "")
                # 检查股票名称
                stock_name = stock_name_var.get().strip()
                if not stock_name:
                    messagebox.showwarning("警告", "请输入股票名称", parent=dialog)
                    return
                # 检查主界面总分
                try:
                    score_text = total_score_var.get().replace("总分: ", "").strip()
                    main_total_score = int(score_text) if score_text.isdigit() else 0
                except:
                    main_total_score = 0
                if main_total_score <= 40:
                    messagebox.showwarning("警告", f"主界面总分 {main_total_score} 分必须大于40分,不可以开仓", parent=dialog)
                    return
                # 检查同花顺情绪指数(两个勾选框都勾选上)
                skip_mandatory_checks = bool(waiting_reason)
                # 获取仓位类型,判断是否需要简化均线检测
                is_simplified_ma_check = position_type in ["朋友", "绩优股", "均值回归"]
                if not skip_mandatory_checks:
                    if main_total_score <= 40:
                        messagebox.showwarning("警告", f"主界面总分 {main_total_score} 分必须大于40分,不可以开仓", parent=dialog)
                        return
                    if not self.sentiment_index_ma1_uptrend_var.get() or not self.sentiment_index_ma1_above_var.get():
                        messagebox.showwarning("警告", "同花顺情绪指数:必须勾选'1日线往上'和'在1日线上'两个条件,不可以开仓", parent=dialog)
                        return
                    if is_simplified_ma_check:
                        # 朋友新仓、绩优股新仓、均值回归新仓:只检查20日均线
                        if not ma20_data_ready_var.get():
                            messagebox.showwarning("警告", "请先检测20日线状态", parent=dialog)
                            return
                        if not ma20_crossed_var.get():
                            messagebox.showwarning("警告", "股价未站上20日线,不可以开仓", parent=dialog)
                            return
                        if not ma20_uptrend_var.get():
                            messagebox.showwarning("警告", "20日线未向上发散,不可以开仓", parent=dialog)
                            return
                    else:
                        # 其他仓位类型:检查所有均线
                        if not divergence_60m_var.get() and not divergence_15m_var.get():
                            messagebox.showwarning("警告", "必须满足:60分钟5日10日多头发散 或 15分钟多头发散", parent=dialog)
                            return
                        if not ma1_data_ready_var.get():
                            messagebox.showwarning("警告", "请先检测1日线状态", parent=dialog)
                            return
                        if not ma1_crossed_var.get():
                            messagebox.showwarning("警告", "股价未站上1日线,不可以开仓", parent=dialog)
                            return
                            # 去除1日线向上发散条件检查
                            # if not ma1_uptrend_var.get():
                            #     messagebox.showwarning("警告", "1日线未向上发散,不可以开仓", parent=dialog)
                            #     return
                        if not ma5_data_ready_var.get():
                            messagebox.showwarning("警告", "请先检测5日线状态", parent=dialog)
                            return
                        if not ma5_crossed_var.get():
                            messagebox.showwarning("警告", "股价未站上5日线,不可以开仓", parent=dialog)
                            return
                        if not ma5_uptrend_var.get():
                            messagebox.showwarning("警告", "5日线未向上发散,不可以开仓", parent=dialog)
                            return
                        if not ma10_data_ready_var.get():
                            messagebox.showwarning("警告", "请先检测10日线状态", parent=dialog)
                            return
                        if not ma10_crossed_var.get():
                            messagebox.showwarning("警告", "股价未站上10日线,不可以开仓", parent=dialog)
                            return
                        if not ma10_uptrend_var.get():
                            messagebox.showwarning("警告", "10日线未向上发散,不可以开仓", parent=dialog)
                            return
                        if not ma20_data_ready_var.get():
                            messagebox.showwarning("警告", "请先检测20日线状态", parent=dialog)
                            return
                        if not ma20_crossed_var.get():
                            messagebox.showwarning("警告", "股价未站上20日线,不可以开仓", parent=dialog)
                            return
                        if not ma20_uptrend_var.get():
                            messagebox.showwarning("警告", "20日线未向上发散,不可以开仓", parent=dialog)
                            return
                        if not main_score_check_var.get():
                            messagebox.showwarning("警告", "主界面总分必须大于40分", parent=dialog)
                            return
                        if not self.sentiment_index_check_var.get():
                            messagebox.showwarning("警告", "同花顺情绪指数:必须勾选'1日线往上'和'在1日线上'两个条件", parent=dialog)
                            return
                        if not is_simplified_ma_check:
                            if not divergence_60m_var.get() and not divergence_15m_var.get():
                                messagebox.showwarning("警告", "必须满足:60分钟5日10日多头发散 或 15分钟多头发散", parent=dialog)
                                return
                        if not kelly_check_var.get():
                            messagebox.showwarning("警告", "请确认凯利公式计算结果", parent=dialog)
                            return
                # 获取仓位计算结果(使用凯利公式结果)
                kelly_result = kelly_result_var.get().replace("%", "")
                try:
                    kelly_percent = float(kelly_result)
                except:
                    kelly_percent = 0
                # 获取主界面仓位值(用于显示)
                position_text = position_result_var.get().replace("+", "").replace("%", "")
                try:
                    main_position = float(position_text)
                except:
                    main_position = 0
                # 获取选股逻辑
                logic = logic_text.get("1.0", tk.END).strip()
                # 生成开新仓记录(包含完整的检测信息)
                current_date = datetime.now().strftime("%Y-%m-%d")
                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                record_text = f"开新仓 {stock_name} {kelly_percent:.2f}% {current_date}\n"
                record_text += "="*50 + "\n"
                record_text += f"股票名称: {stock_name}\n"
                record_text += f"股票代码: {stock_code_var.get()}\n"
                record_text += f"判断时间: {current_datetime}\n"
                record_text += f"主界面总分: {main_total_score}分\n"
                record_text += f"同花顺情绪指数: 1日线往上={'是' if self.sentiment_index_ma1_uptrend_var.get() else '否'}, 在1日线上={'是' if self.sentiment_index_ma1_above_var.get() else '否'}\n"
                record_text += f"多头发散: {'60分钟5日10日多头发散' if divergence_60m_var.get() else '15分钟多头发散'}\n"
                if waiting_reason:
                    record_text += f"等待理由: {waiting_reason}(自动跳过必须条件)\n"
                record_text += "\n【均线检测结果】\n"
                record_text += f"1日线状态: {'已检测' if ma1_data_ready_var.get() else '未检测'} / "
                record_text += f"{'股价已站上1日线' if ma1_crossed_var.get() else '股价未站上1日线'} / "
                record_text += f"{'1日线上升发散' if ma1_uptrend_var.get() else '1日线未上升'}\n"
                record_text += f"  数据来源: {ma1_source_var.get()}\n"
                record_text += f"  最新价: {current_price_var.get()} / 参考1日线: {ma1_reference_var.get()} / 前值: {ma1_prev_var.get()}\n"
                record_text += f"5日线状态: {'已检测' if ma5_data_ready_var.get() else '未检测'} / "
                record_text += f"{'股价已站上5日线' if ma5_crossed_var.get() else '股价未站上5日线'} / "
                record_text += f"{'5日线上升发散' if ma5_uptrend_var.get() else '5日线未上升'}\n"
                record_text += f"  参考5日线: {ma5_reference_var.get()} / 前值: {ma5_prev_var.get()}\n"
                record_text += f"10日线状态: {'已检测' if ma10_data_ready_var.get() else '未检测'} / "
                record_text += f"{'股价已站上10日线' if ma10_crossed_var.get() else '股价未站上10日线'} / "
                record_text += f"{'10日线上升发散' if ma10_uptrend_var.get() else '10日线未上升'}\n"
                record_text += f"  参考10日线: {ma10_reference_var.get()} / 前值: {ma10_prev_var.get()}\n"
                record_text += f"20日线状态: {'已检测' if ma20_data_ready_var.get() else '未检测'} / "
                record_text += f"{'股价已站上20日线' if ma20_crossed_var.get() else '股价未站上20日线'} / "
                record_text += f"{'20日线上升发散' if ma20_uptrend_var.get() else '20日线未上升'}\n"
                record_text += f"  参考20日线: {ma20_reference_var.get()} / 前值: {ma20_prev_var.get()}\n"
                record_text += "\n【仓位计算结果】\n"
                record_text += f"主界面仓位: {main_position:.2f}%\n"
                record_text += f"凯利公式仓位: {kelly_percent:.2f}%\n"
                record_text += f"日期: {current_date}\n"
                # 从文本框读取案例内容(这些控件在同一个对话框作用域内,可以直接访问)
                try:
                    success_case_content = success_case_text.get("1.0", tk.END).strip()
                    fail_case_content = fail_case_text.get("1.0", tk.END).strip()
                    if success_case_content:
                        record_text += f"\n成功案例: {success_case_content}\n"
                    if fail_case_content:
                        record_text += f"失败案例: {fail_case_content}\n"
                except NameError:
                    # 如果文本框尚未创建(理论上不应该发生),则跳过
                    pass
                record_text += f"\n选股逻辑:\n{logic}\n"
                record_text += "="*50 + "\n"
                record_text += "必须条件:\n"
                required_text = required_scroll.get("1.0", tk.END).strip()
                required_list = [line.strip() for line in required_text.split("\n") if line.strip()]
                for condition in required_list:
                    record_text += f"  ✓ {condition}\n"
                optional_text = optional_scroll.get("1.0", tk.END).strip()
                optional_list = [line.strip() for line in optional_text.split("\n") if line.strip()]
                if optional_list:
                    record_text += "\n可选条件:\n"
                    for condition in optional_list:
                        record_text += f"  ✓ {condition}\n"
                # 保存到资讯数据库
                try:
                    news_tab_name = f"开新仓-{position_type}-{stock_name}-{current_date}"
                    if save_news_info_to_db(news_tab_name, record_text):
                        print(f"开新仓记录已保存到资讯数据库: {news_tab_name}")
                except Exception as e:
                    print(f"保存到资讯数据库失败: {e}")
                # 如果失败案例框有内容,单独保存失败案例到资讯数据库
                try:
                    fail_case_content = fail_case_text.get("1.0", tk.END).strip()
                    if fail_case_content:
                        fail_case_tab_name = f"开新仓记录-失败案例-{position_type}-{stock_name}-{current_date}"
                        fail_case_record = "失败案例记录\n"
                        fail_case_record += "="*50 + "\n"
                        fail_case_record += f"股票名称: {stock_name}\n"
                        fail_case_record += f"股票代码: {stock_code_var.get()}\n"
                        fail_case_record += f"判断时间: {current_datetime}\n"
                        fail_case_record += f"失败案例内容:\n{fail_case_content}\n"
                        fail_case_record += "="*50 + "\n"
                        if save_news_info_to_db(fail_case_tab_name, fail_case_record):
                            print(f"失败案例已保存到资讯数据库: {fail_case_tab_name}")
                except Exception as e:
                    print(f"保存失败案例到资讯数据库失败: {e}")
                # 创建新标签页显示开新仓记录
                tab_name = f"开{position_type}新仓{stock_name}{kelly_percent:.1f}%{current_date}"
                tab_id = self.create_text_tab(tab_name)
                text_widget = self.text_widgets[tab_id]['widget']
                text_widget.insert("1.0", record_text)
                # 显示结果对话框(带打印按钮)
                result_dialog = self._toplevel(dialog)
                result_dialog.title(f"开{position_type}新仓确认")
                result_dialog.geometry("600x400")
                result_frame = ttk.Frame(result_dialog, padding=20)
                result_frame.pack(fill=tk.BOTH, expand=True)
                ttk.Label(result_frame, text=f"开{position_type}新仓记录已创建", font=("TkDefaultFont", 14, "bold")).pack(pady=10)
                result_text = scrolledtext.ScrolledText(result_frame, height=15, wrap=tk.WORD)
                result_text.pack(fill=tk.BOTH, expand=True, pady=10)
                result_text.insert("1.0", record_text)
                result_text.config(state=tk.DISABLED)
                def print_record():
                    """打印记录"""
                    try:
                        # 保存为文本文件用于打印
                        print_file = os.path.join(D_OUTPUT_DIR, f"开{position_type}新仓_{stock_name}_{current_date}.txt")
                        with open(print_file, "w", encoding="utf-8") as f:
                            f.write(record_text)
                        messagebox.showinfo("成功", f"记录已保存到:\n{print_file}\n\n可以使用系统打印功能打印此文件", parent=dialog)
                    except Exception as e:
                        messagebox.showerror("错误", f"保存打印文件失败: {e}", parent=dialog)
                def save_to_case():
                    """保存到案例(资讯数据库)"""
                    try:
                        # 使用"开新仓记录"作为标识
                        news_tab_name = f"开新仓记录-{position_type}-{stock_name}-{current_date}"
                        if save_news_info_to_db(news_tab_name, record_text):
                            messagebox.showinfo("成功", "开新仓记录已保存到案例数据库", parent=result_dialog)
                        else:
                            messagebox.showerror("错误", "保存到案例数据库失败", parent=result_dialog)
                    except Exception as e:
                        messagebox.showerror("错误", f"保存到案例数据库失败: {e}", parent=result_dialog)
                def show_cases():
                    """显示案例(打开资讯数据表,按案例排序)"""
                    try:
                        # 打开数据库管理窗口,默认显示资讯数据表
                        db_window = self.show_unified_db_display(default_tab="news")
                        # 等待窗口创建后,应用案例排序
                        def apply_case_sort():
                            try:
                                # 查找news_tree
                                def find_news_tree(parent):
                                    """递归查找资讯数据表的Treeview"""
                                    for child in parent.winfo_children():
                                        if isinstance(child, ttk.Notebook):
                                            # 找到资讯数据表标签页
                                            for i in range(child.index("end")):
                                                if child.tab(i, "text") == "资讯数据表":
                                                    tab = child.nametowidget(child.tabs()[i])
                                                    # 在tab中查找Treeview
                                                    for widget in tab.winfo_children():
                                                        if isinstance(widget, ttk.Frame):
                                                            for sub_widget in widget.winfo_children():
                                                                if isinstance(sub_widget, ttk.Treeview):
                                                                    return sub_widget
                                        elif isinstance(child, (ttk.Frame, tk.Frame)):
                                            result = find_news_tree(child)
                                            if result:
                                                return result
                                    return None
                                news_tree = find_news_tree(db_window)
                                if news_tree:
                                    # 从数据库加载数据,按案例排序
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    cursor.execute('''
                                        SELECT id, tab_name, content, created_at, updated_at
                                        FROM news_info
                                        ORDER BY
                                            CASE
                                                WHEN tab_name LIKE '%开新仓记录%' OR tab_name LIKE '%案例%' OR tab_name LIKE '%开新仓%' THEN 0
                                                ELSE 1
                                            END,
                                            created_at DESC
                                    ''')
                                    rows = cursor.fetchall()
                                    conn.close()
                                    # 清空现有数据
                                    news_tree.delete(*news_tree.get_children())
                                    # 插入排序后的数据
                                    for row in rows:
                                        news_id, tab_name, content, created_at, updated_at = row
                                        content_preview = content[:100] + "..." if content and len(content) > 100 else (content or "")
                                        news_tree.insert("", tk.END, values=(news_id, tab_name, content_preview, created_at, updated_at))
                                else:
                                    print("未找到资讯数据表的Treeview")
                            except Exception as e:
                                print(f"应用案例排序失败: {e}")
                                import traceback
                                traceback.print_exc()
                        # 延迟执行排序,确保窗口已完全创建
                        db_window.after(500, apply_case_sort)
                    except Exception as e:
                        messagebox.showerror("错误", f"打开案例数据表失败: {e}", parent=result_dialog)
                button_frame2 = ttk.Frame(result_frame)
                button_frame2.pack(fill=tk.X)
                ttk.Button(button_frame2, text="打印", command=print_record).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame2, text="保存到案例", command=save_to_case).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame2, text="显示案例", command=show_cases).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame2, text="关闭", command=lambda: [result_dialog.destroy(), dialog.destroy()]).pack(side=tk.LEFT, padx=5)
            # 右侧按钮区域(固定在右侧面板)
            # 判断按钮(突出显示)
            judge_btn = ttk.Button(right_pane, text="判断", command=judge_new_position,
                                  width=18)
            judge_btn.pack(fill=tk.X, padx=5, pady=10)
            # 确认开新仓按钮
            confirm_btn = ttk.Button(right_pane, text="确认开新仓", command=confirm_new_position, width=18)
            confirm_btn.pack(fill=tk.X, padx=5, pady=5)
            # 取消按钮
            cancel_btn = ttk.Button(right_pane, text="取消", command=dialog.destroy, width=18)
            cancel_btn.pack(fill=tk.X, padx=5, pady=5)
            # 添加分隔线
            separator = ttk.Separator(right_pane, orient=tk.HORIZONTAL)
            separator.pack(fill=tk.X, padx=5, pady=10)
            # 当前得分信息区域
            score_frame = ttk.LabelFrame(right_pane, text="当前得分", padding=10)
            score_frame.pack(fill=tk.X, padx=5, pady=5)
            if waiting_reason:
                ttk.Label(
                    score_frame,
                    text=f"等待理由:{waiting_reason}(已跳过必须条件)",
                    font=("TkDefaultFont", 11, "bold"),
                    foreground="#d97706"
                ).pack(fill=tk.X, pady=(0, 4))
            position_row = ttk.Frame(score_frame)
            position_row.pack(fill=tk.X, pady=2)
            ttk.Label(position_row, text="主界面仓位:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
            position_status_label = ttk.Label(position_row, textvariable=position_result_var,
                                              font=("TkDefaultFont", 12, "bold"), foreground="blue")
            position_status_label.pack(side=tk.LEFT, padx=(5, 0))
            kelly_row = ttk.Frame(score_frame)
            kelly_row.pack(fill=tk.X, pady=2)
            ttk.Label(kelly_row, text="凯利公式仓位:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
            kelly_status_label = ttk.Label(kelly_row, textvariable=kelly_result_var,
                                           font=("TkDefaultFont", 12, "bold"), foreground="green")
            kelly_status_label.pack(side=tk.LEFT, padx=(5, 0))
            total_row = ttk.Frame(score_frame)
            total_row.pack(fill=tk.X, pady=(6, 2))
            ttk.Label(total_row, text="主界面总分:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
            main_score_label = ttk.Label(total_row, textvariable=total_score_var,
                                         font=("TkDefaultFont", 12, "bold"), foreground="blue")
            main_score_label.pack(side=tk.LEFT, padx=(5, 10))
            main_score_check = ttk.Checkbutton(total_row, text="> 40 分", variable=main_score_check_var)
            main_score_check.pack(side=tk.LEFT)
            peripheral_row = ttk.Frame(score_frame)
            peripheral_row.pack(fill=tk.X, pady=2)
            ttk.Label(peripheral_row, text="同花顺情绪指数:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
            sentiment_index_ma1_uptrend_check = ttk.Checkbutton(peripheral_row, text="1日线往上", variable=self.sentiment_index_ma1_uptrend_var, command=update_sentiment_index_check)
            sentiment_index_ma1_uptrend_check.pack(side=tk.LEFT, padx=(5, 5))
            sentiment_index_ma1_above_check = ttk.Checkbutton(peripheral_row, text="在1日线上", variable=self.sentiment_index_ma1_above_var, command=update_sentiment_index_check)
            sentiment_index_ma1_above_check.pack(side=tk.LEFT, padx=(5, 10))
            sentiment_index_check = ttk.Checkbutton(peripheral_row, text="已确认(两个都勾选)", variable=self.sentiment_index_check_var, state="disabled")
            sentiment_index_check.pack(side=tk.LEFT)
            # 必须条件和可选条件Notebook(移到右侧面板)
            conditions_notebook = ttk.Notebook(right_pane)
            # 设置高度限制,避免占据过多空间
            conditions_notebook.configure(height=350)
            # 使用fill和expand,但高度已被限制
            conditions_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(10, 5))
            # 必须条件标签页
            required_tab = ttk.Frame(conditions_notebook, padding=10)
            conditions_notebook.add(required_tab, text="必须条件")
            # 必须条件文本区域
            required_scroll = scrolledtext.ScrolledText(required_tab, height=8, wrap=tk.WORD)
            required_scroll.pack(fill=tk.BOTH, expand=True)
            required_scroll.insert("1.0", "\n".join(default_required))
            # 必须条件检查输入区域
            required_check_frame = ttk.Frame(required_tab)
            required_check_frame.pack(fill=tk.X, pady=(5, 0))
            # 多头发散检查
            divergence_frame = ttk.Frame(required_check_frame)
            divergence_frame.pack(fill=tk.X, pady=2)
            divergence_60m_check = ttk.Checkbutton(divergence_frame, text="60分钟5日10日多头发散", variable=divergence_60m_var)
            divergence_60m_check.pack(side=tk.LEFT, padx=(0, 10))
            divergence_15m_check = ttk.Checkbutton(divergence_frame, text="15分钟多头发散", variable=divergence_15m_var)
            divergence_15m_check.pack(side=tk.LEFT)
            # 可选条件标签页
            optional_tab = ttk.Frame(conditions_notebook, padding=10)
            conditions_notebook.add(optional_tab, text="可选条件")
            # 可选条件文本区域
            optional_scroll = scrolledtext.ScrolledText(optional_tab, height=8, wrap=tk.WORD)
            optional_scroll.pack(fill=tk.BOTH, expand=True)
            optional_scroll.insert("1.0", "\n".join(default_optional))
            # 案例管理标签页
            case_management_tab = ttk.Frame(conditions_notebook, padding=10)
            conditions_notebook.add(case_management_tab, text="案例管理")
            # 成功案例区域
            success_case_frame = ttk.LabelFrame(case_management_tab, text="成功案例", padding=5)
            success_case_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            success_case_label_row = ttk.Frame(success_case_frame)
            success_case_label_row.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(success_case_label_row, text="成功案例:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(success_case_label_row, text="管理", command=lambda: manage_cases_from_news("success"), width=8).pack(side=tk.LEFT, padx=(0, 5))
            def mark_success():
                """标记为成功"""
                content = success_case_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "成功案例框为空,无法标记", parent=dialog)
                    return
                # 获取当前时间
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 在最后加上"成功"和时间
                success_case_text.insert(tk.END, f"\n成功 {current_time}")
                # 清除之前的标签并重新应用第一行样式
                success_case_text.tag_delete("success_first_line")
                # 获取第一行内容
                first_line = success_case_text.get("1.0", "1.end")
                if first_line:
                    # 配置第一行的样式:红色、粗体、15号字体
                    success_case_text.tag_add("success_first_line", "1.0", "1.end")
                    success_case_text.tag_config("success_first_line", foreground="red", font=("TkDefaultFont", 15, "bold"))
            ttk.Button(success_case_label_row, text="成功", command=mark_success, width=8).pack(side=tk.LEFT, padx=(0, 5))
            def mark_fail_from_success():
                """从成功案例标记为失败"""
                content = success_case_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "成功案例框为空,无法标记", parent=dialog)
                    return
                # 获取当前时间
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 在内容最后加上"失败"和时间
                content_with_fail = content + f"\n失败 {current_time}"
                # 将内容移到失败案例框并保存
                fail_case_text.delete("1.0", tk.END)
                fail_case_text.insert("1.0", content_with_fail)
                fail_case_var.set(content_with_fail[:50] + "..." if len(content_with_fail) > 50 else content_with_fail)
                # 清除之前的标签并重新应用第一行样式(绿色、粗体、15号字体)
                fail_case_text.tag_delete("fail_first_line")
                first_line = fail_case_text.get("1.0", "1.end")
                if first_line:
                    fail_case_text.tag_add("fail_first_line", "1.0", "1.end")
                    fail_case_text.tag_config("fail_first_line", foreground="green", font=("TkDefaultFont", 15, "bold"))
                # 清空成功案例框
                success_case_text.delete("1.0", tk.END)
                success_case_var.set("")
                messagebox.showinfo("成功", "已标记为失败并移到失败案例", parent=dialog)
            ttk.Button(success_case_label_row, text="失败", command=mark_fail_from_success, width=8).pack(side=tk.LEFT)
            success_case_text = scrolledtext.ScrolledText(success_case_frame, height=6, wrap=tk.WORD, font=("TkDefaultFont", 11))
            success_case_text.pack(fill=tk.BOTH, expand=True)
            # 初始化时从变量读取(如果有值)
            if success_case_var.get():
                success_case_text.insert("1.0", success_case_var.get())
            # 双击放大成功案例文本框
            def show_success_case_popup(event=None):
                """双击成功案例文本框弹出大窗口"""
                content = success_case_text.get("1.0", tk.END).strip()
                if not content:
                    return
                popup = self._toplevel(dialog)
                popup.title("成功案例")
                popup.geometry("800x600")
                popup_text = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("TkDefaultFont", 12))
                popup_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                popup_text.insert("1.0", content)
                popup_text.config(state=tk.DISABLED)
            success_case_text.bind("<Double-1>", show_success_case_popup)
            # 失败案例区域
            fail_case_frame = ttk.LabelFrame(case_management_tab, text="失败案例", padding=5)
            fail_case_frame.pack(fill=tk.BOTH, expand=True)
            fail_case_label_row = ttk.Frame(fail_case_frame)
            fail_case_label_row.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(fail_case_label_row, text="失败案例:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(fail_case_label_row, text="管理", command=lambda: manage_cases_from_news("fail"), width=8).pack(side=tk.LEFT, padx=(0, 5))
            def mark_success_from_fail():
                """从失败案例标记为成功"""
                content = fail_case_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "失败案例框为空,无法标记", parent=dialog)
                    return
                # 获取当前时间
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 在内容最后加上"成功"和时间
                content_with_success = content + f"\n成功 {current_time}"
                # 将内容移到成功案例框
                success_case_text.delete("1.0", tk.END)
                success_case_text.insert("1.0", content_with_success)
                success_case_var.set(content_with_success[:50] + "..." if len(content_with_success) > 50 else content_with_success)
                # 清除之前的标签并重新应用第一行样式(红色、粗体、15号字体)
                success_case_text.tag_delete("success_first_line")
                first_line = success_case_text.get("1.0", "1.end")
                if first_line:
                    success_case_text.tag_add("success_first_line", "1.0", "1.end")
                    success_case_text.tag_config("success_first_line", foreground="red", font=("TkDefaultFont", 15, "bold"))
                # 清空失败案例框
                fail_case_text.delete("1.0", tk.END)
                fail_case_var.set("")
                messagebox.showinfo("成功", "已标记为成功并移到成功案例", parent=dialog)
            ttk.Button(fail_case_label_row, text="成功", command=mark_success_from_fail, width=8).pack(side=tk.LEFT, padx=(0, 5))
            def mark_fail():
                """标记为失败"""
                content = fail_case_text.get("1.0", tk.END).strip()
                if not content:
                    messagebox.showwarning("警告", "失败案例框为空,无法标记", parent=dialog)
                    return
                # 获取当前时间
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # 在最后加上"失败"和时间
                fail_case_text.insert(tk.END, f"\n失败 {current_time}")
                # 清除之前的标签并重新应用第一行样式
                fail_case_text.tag_delete("fail_first_line")
                # 获取第一行内容
                first_line = fail_case_text.get("1.0", "1.end")
                if first_line:
                    # 配置第一行的样式:绿色、粗体、15号字体
                    fail_case_text.tag_add("fail_first_line", "1.0", "1.end")
                    fail_case_text.tag_config("fail_first_line", foreground="green", font=("TkDefaultFont", 15, "bold"))
            ttk.Button(fail_case_label_row, text="失败", command=mark_fail, width=8).pack(side=tk.LEFT)
            fail_case_text = scrolledtext.ScrolledText(fail_case_frame, height=6, wrap=tk.WORD, font=("TkDefaultFont", 11))
            fail_case_text.pack(fill=tk.BOTH, expand=True)
            # 初始化时从变量读取(如果有值)
            if fail_case_var.get():
                fail_case_text.insert("1.0", fail_case_var.get())
            # 双击放大失败案例文本框
            def show_fail_case_popup(event=None):
                """双击失败案例文本框弹出大窗口"""
                content = fail_case_text.get("1.0", tk.END).strip()
                if not content:
                    return
                popup = self._toplevel(dialog)
                popup.title("失败案例")
                popup.geometry("800x600")
                popup_text = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("TkDefaultFont", 12))
                popup_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                popup_text.insert("1.0", content)
                popup_text.config(state=tk.DISABLED)
            fail_case_text.bind("<Double-1>", show_fail_case_popup)
            # 警示通言标签页
            warning_tab = ttk.Frame(conditions_notebook, padding=10)
            conditions_notebook.add(warning_tab, text="警示通言")
            warning_list_frame = ttk.Frame(warning_tab)
            warning_list_frame.pack(fill=tk.BOTH, expand=True)
            warning_listbox = tk.Listbox(warning_list_frame, height=15, activestyle='none',
                                         fg="blue", cursor="hand2", font=("TkDefaultFont", 12, "underline"))
            warning_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            warning_scrollbar = ttk.Scrollbar(warning_list_frame, orient=tk.VERTICAL, command=warning_listbox.yview)
            warning_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            warning_listbox.configure(yscrollcommand=warning_scrollbar.set)
            warning_tab_info_var = tk.StringVar(value="共 0 条")
            ttk.Label(warning_tab, textvariable=warning_tab_info_var, font=("TkDefaultFont", 11)).pack(anchor=tk.W, pady=(5, 0))
            warning_tab_btn_frame = ttk.Frame(warning_tab)
            warning_tab_btn_frame.pack(fill=tk.X, pady=(5, 0))
            warning_records = []
            def refresh_warning_tab_links():
                nonlocal warning_records
                warning_records = fetch_warning_records(30)
                warning_listbox.delete(0, tk.END)
                if not warning_records:
                    warning_listbox.insert(tk.END, "暂无警示通言记录")
                    warning_tab_info_var.set("共 0 条")
                    return
                for idx, (_, tab_name, _, created_at) in enumerate(warning_records, start=1):
                    created_text = created_at or ""
                    display_name = f"{idx}. {tab_name} ({created_text})"
                    warning_listbox.insert(tk.END, display_name)
                warning_tab_info_var.set(f"共 {len(warning_records)} 条")
            def open_selected_warning(event=None):
                if not warning_records:
                    return
                selection = warning_listbox.curselection()
                if not selection:
                    return
                _, tab_name, content, _ = warning_records[selection[0]]
                show_warning_popup(content, tab_name)
            warning_listbox.bind("<Double-1>", open_selected_warning)
            ttk.Button(warning_tab_btn_frame, text="打开", command=open_selected_warning, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(warning_tab_btn_frame, text="刷新", command=refresh_warning_tab_links, width=10).pack(side=tk.LEFT, padx=5)
            refresh_warning_tab_links()
            # 定义从资讯数据表选择案例的函数
            def manage_cases_from_news(case_type):
                """从资讯数据表中选择案例(开新仓记录或警示)"""
                # 打开资讯数据表窗口
                news_window = self._toplevel(dialog)
                news_window.title(f"选择{'成功' if case_type == 'success' else '失败'}案例 - 资讯数据表")
                news_window.geometry("1000x700")
                # 查询条件:包含"开新仓记录"或"警示"的记录
                filter_frame = ttk.Frame(news_window, padding=10)
                filter_frame.pack(fill=tk.X)
                ttk.Label(filter_frame, text="筛选条件:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=5)
                ttk.Label(filter_frame, text="包含'开新仓记录'或'警示'的记录", font=("TkDefaultFont", 11), foreground="blue").pack(side=tk.LEFT, padx=5)
                # 数据列表
                list_frame = ttk.Frame(news_window, padding=10)
                list_frame.pack(fill=tk.BOTH, expand=True)
                columns = ("ID", "标签页名称", "内容预览", "创建时间")
                news_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
                for col in columns:
                    news_tree.heading(col, text=col)
                    if col == "ID":
                        news_tree.column(col, width=50, anchor=tk.CENTER)
                    elif col == "标签页名称":
                        news_tree.column(col, width=250, anchor=tk.CENTER)
                    elif col == "内容预览":
                        news_tree.column(col, width=400)
                    elif col == "创建时间":
                        news_tree.column(col, width=150, anchor=tk.CENTER)
                scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=news_tree.yview)
                news_tree.configure(yscrollcommand=scrollbar.set)
                news_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                # 加载数据
                def load_news_data():
                    news_tree.delete(*news_tree.get_children())
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        # 查询包含"开新仓记录"或"警示"的记录
                        cursor.execute('''
                            SELECT id, tab_name, content, created_at
                            FROM news_info
                            WHERE tab_name LIKE ? OR tab_name LIKE ? OR content LIKE ? OR content LIKE ?
                            ORDER BY created_at DESC
                        ''', ('%开新仓%', '%警示%', '%开新仓%', '%警示%'))
                        rows = cursor.fetchall()
                        conn.close()
                        for row in rows:
                            news_id, tab_name, content, created_at = row
                            content_preview = content[:100] + "..." if content and len(content) > 100 else (content or "")
                            news_tree.insert("", tk.END, values=(news_id, tab_name, content_preview, created_at))
                    except Exception as e:
                        messagebox.showerror("错误", f"查询失败: {e}", parent=news_window)
                # 选择按钮
                button_frame = ttk.Frame(news_window, padding=10)
                button_frame.pack(fill=tk.X)
                def select_case():
                    """选择当前记录并填入对应的文本框"""
                    selection = news_tree.selection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择一条记录", parent=news_window)
                        return
                    item = news_tree.item(selection[0])
                    news_id = item['values'][0]
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('SELECT content FROM news_info WHERE id = ?', (news_id,))
                        row = cursor.fetchone()
                        conn.close()
                        if row:
                            content = row[0]
                            # 根据内容判断应该填入哪个文本框
                            # 如果有"成功"或"无失败"两字,显示到成功案例框
                            # 如果有"失败"两字,显示到失败案例框
                            has_success = "成功" in content or "无失败" in content
                            has_fail = "失败" in content
                            if has_success and not has_fail:
                                # 显示到成功案例框
                                success_case_text.delete("1.0", tk.END)
                                success_case_text.tag_delete("success_first_line")
                                success_case_text.insert("1.0", content)
                                success_case_var.set(content[:50] + "..." if len(content) > 50 else content)
                                # 配置第一行样式:红色、粗体、15号字体
                                first_line = success_case_text.get("1.0", "1.end")
                                if first_line:
                                    success_case_text.tag_add("success_first_line", "1.0", "1.end")
                                    success_case_text.tag_config("success_first_line", foreground="red", font=("TkDefaultFont", 15, "bold"))
                                target_case = "成功"
                            elif has_fail:
                                # 显示到失败案例框
                                fail_case_text.delete("1.0", tk.END)
                                fail_case_text.tag_delete("fail_first_line")
                                fail_case_text.insert("1.0", content)
                                fail_case_var.set(content[:50] + "..." if len(content) > 50 else content)
                                # 配置第一行样式:绿色、粗体、15号字体
                                first_line = fail_case_text.get("1.0", "1.end")
                                if first_line:
                                    fail_case_text.tag_add("fail_first_line", "1.0", "1.end")
                                    fail_case_text.tag_config("fail_first_line", foreground="green", font=("TkDefaultFont", 15, "bold"))
                                target_case = "失败"
                            else:
                                # 根据case_type填入对应的文本框(默认行为)
                                if case_type == "success":
                                    success_case_text.delete("1.0", tk.END)
                                    success_case_text.tag_delete("success_first_line")
                                    success_case_text.insert("1.0", content)
                                    success_case_var.set(content[:50] + "..." if len(content) > 50 else content)
                                    target_case = "成功"
                                else:
                                    fail_case_text.delete("1.0", tk.END)
                                    fail_case_text.tag_delete("fail_first_line")
                                    fail_case_text.insert("1.0", content)
                                    fail_case_var.set(content[:50] + "..." if len(content) > 50 else content)
                                    target_case = "失败"
                            news_window.destroy()
                            messagebox.showinfo("成功", f"已选择记录并填入{target_case}案例", parent=dialog)
                    except Exception as e:
                        messagebox.showerror("错误", f"获取记录失败: {e}", parent=news_window)
                ttk.Button(button_frame, text="选择此记录", command=select_case, width=15).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="刷新", command=load_news_data, width=10).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="关闭", command=news_window.destroy, width=10).pack(side=tk.RIGHT, padx=5)
                load_news_data()
            # 市场维度确认框
            right_checkbox_frame = ttk.LabelFrame(optional_tab, text="市场维度确认", padding=10)
            right_checkbox_frame.pack(fill=tk.X, pady=(5, 0))
            # 三个维度确认框
            market_basic_var = tk.BooleanVar(value=False)
            market_basic_cb = ttk.Checkbutton(right_checkbox_frame, text="大盘基本面", variable=market_basic_var)
            market_basic_cb.pack(anchor=tk.W, pady=3)
            peripheral_var = tk.BooleanVar(value=False)
            peripheral_cb = ttk.Checkbutton(right_checkbox_frame, text="外围情况", variable=peripheral_var)
            peripheral_cb.pack(anchor=tk.W, pady=3)
            market_sentiment_var = tk.BooleanVar(value=False)
            market_sentiment_cb = ttk.Checkbutton(right_checkbox_frame, text="市场情绪", variable=market_sentiment_var)
            market_sentiment_cb.pack(anchor=tk.W, pady=3)
            # 三维问询按钮
            def show_three_dimension_analysis():
                """显示三维问询界面"""
                try:
                    win = self._toplevel(dialog)
                    win.title("三维问询分析")
                    win.geometry("1200x720")
                    win.transient(dialog)
                    win.resizable(True, True)
                    # 存储窗口状态
                    win._is_minimized = False
                    win._original_geometry = "1200x720"
                    # 配置窗口布局
                    win.columnconfigure(0, weight=1)
                    win.columnconfigure(1, weight=1)
                    win.rowconfigure(1, weight=1)
                    # 头部说明
                    header = ttk.Label(
                        win,
                        text="三维问询分析 - 股票指数基本面、外围市场情况、市场情绪",
                        anchor="center",
                        font=("Microsoft YaHei", 14, "bold")
                    )
                    header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
                    # 左侧:问题描述
                    left_frame = ttk.LabelFrame(win, text="问题描述", padding=10)
                    left_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
                    left_frame.columnconfigure(0, weight=1)
                    left_frame.rowconfigure(1, weight=1)
                    problem_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=20, font=("TkDefaultFont", 12))
                    problem_text.grid(row=1, column=0, sticky="nsew")
                    # 设置默认问题
                    default_question = """根据目前股票指数基本面,外围的市场情况,市场的情绪三个方面来分析,根据每个最高33.3分,加起来,看看可以得多少分。"""
                    problem_text.insert("1.0", default_question)
                    # 右侧:分析结果
                    right_frame = ttk.LabelFrame(win, text="分析结果", padding=10)
                    right_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
                    right_frame.columnconfigure(0, weight=1)
                    right_frame.rowconfigure(1, weight=1)
                    # 结果显示方式选择
                    display_mode_frame = ttk.Frame(right_frame)
                    display_mode_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
                    ttk.Label(display_mode_frame, text="结果显示方式:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
                    display_mode_var = tk.StringVar(value="累计显示")
                    ttk.Radiobutton(display_mode_frame, text="累计显示", variable=display_mode_var,
                                   value="累计显示").pack(side=tk.LEFT, padx=5)
                    ttk.Radiobutton(display_mode_frame, text="新标签页", variable=display_mode_var,
                                   value="新标签页").pack(side=tk.LEFT, padx=5)
                    # 根据情绪周期确定背景颜色
                    if hasattr(self, 'get_emotion_bg_color'):
                        result_bg_color = self.get_emotion_bg_color()
                    else:
                        result_bg_color = "white"
                    result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, height=20, font=("TkDefaultFont", 12),
                                                           state=tk.DISABLED, bg=result_bg_color)
                    result_text.grid(row=1, column=0, sticky="nsew")
                    # 保存引用以便后续更新背景颜色
                    if not hasattr(self, '_analysis_result_text_widgets'):
                        self._analysis_result_text_widgets = []
                    self._analysis_result_text_widgets.append(result_text)
                    # 底部:三个维度按钮
                    control_frame = ttk.LabelFrame(win, text="分析维度", padding=10)
                    control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
                    # 三个维度选项
                    dimension_options = {
                        "股票指数基本面": "分析当前股票指数(如上证指数、深证成指、创业板指等)的基本面情况,包括宏观经济环境、政策导向、估值水平、资金流向等",
                        "外围的市场情况": "分析外围市场情况,包括美股、港股、欧洲股市、日韩股市等主要市场的走势、政策变化、经济数据等",
                        "市场的情绪": "分析市场情绪,包括投资者情绪、恐慌指数、市场热度、资金风险偏好、技术面情绪等"
                    }
                    # 创建按钮
                    buttons_per_row = 3
                    row = 0
                    col = 0
                    for option_name, option_desc in dimension_options.items():
                        btn = ttk.Button(
                            control_frame,
                            text=option_name,
                            command=lambda name=option_name, desc=option_desc: run_dimension_analysis(name, desc),
                            width=25
                        )
                        btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
                        col += 1
                        if col >= buttons_per_row:
                            col = 0
                            row += 1
                    # 配置列权重
                    for i in range(buttons_per_row):
                        control_frame.columnconfigure(i, weight=1)
                    def get_dimension_prompt(dimension_name, dimension_desc, problem):
                        """生成维度分析提示"""
                        return f"""请针对以下维度进行专业分析:
分析维度:{dimension_name}
维度说明:{dimension_desc}
用户问题:{problem}
请提供以下方面的分析:
1. 该维度的当前状况和关键指标
2. 该维度对市场的影响程度
3. 该维度的评分(0-33.3分)及评分理由
4. 该维度的风险提示和注意事项
5. 基于该维度的投资建议"""
                    def run_dimension_analysis(option_name, option_desc):
                        """运行维度分析"""
                        problem = problem_text.get("1.0", tk.END).strip()
                        if not problem:
                            problem = default_question
                        # 获取显示方式
                        display_mode = display_mode_var.get()
                        # 生成提示
                        prompt = get_dimension_prompt(option_name, option_desc, problem)
                        # 存储分析状态
                        analysis_info = {
                            'option_name': option_name,
                            'option_desc': option_desc,
                            'display_mode': display_mode,
                            'target_text': None,
                            'tab_id': None,
                            'analysis_start_pos': None
                        }
                        # 根据显示方式处理
                        if display_mode == "新标签页":
                            # 创建新标签页
                            from datetime import datetime
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            tab_title = f"三维问询-{option_name}-{current_time}"
                            tab_id = self.create_result_tab(tab_title)
                            target_text = self.result_tabs[tab_id]['widget']
                            analysis_info['target_text'] = target_text
                            analysis_info['tab_id'] = tab_id
                            # 显示分析中
                            target_text.config(state=tk.NORMAL)
                            target_text.delete("1.0", tk.END)
                            target_text.insert(tk.END, f"[{option_name}] 正在分析...\n\n")
                            target_text.insert(tk.END, f"维度说明:{option_desc}\n\n")
                            target_text.config(state=tk.DISABLED)
                        else:
                            # 累计显示在当前界面
                            target_text = result_text
                            analysis_info['target_text'] = target_text
                            target_text.config(state=tk.NORMAL)
                            # 记录插入位置
                            analysis_info['analysis_start_pos'] = target_text.index(tk.END)
                            # 追加内容,不清空
                            current_content = target_text.get("1.0", tk.END)
                            if current_content.strip():
                                target_text.insert(tk.END, "\n" + "="*80 + "\n\n")
                            target_text.insert(tk.END, f"[{option_name}] 正在分析...\n\n")
                            target_text.insert(tk.END, f"维度说明:{option_desc}\n\n")
                            target_text.config(state=tk.DISABLED)
                        # 异步调用AI
                        def analyze():
                            try:
                                system_prompt = "你是一位资深的市场分析专家,能够从多个维度深入分析市场状况,提供专业的评分和建议。"
                                ai_result = self.call_ai_model(prompt, system_prompt)
                                if not ai_result:
                                    ai_result = f"【{option_name}分析】\n\n{option_desc}\n\n请结合您的问题进行深入分析。"
                            except Exception as e:
                                ai_result = f"AI分析失败: {e}\n\n{option_desc}"
                            def update_ui():
                                target_text = analysis_info['target_text']
                                display_mode = analysis_info['display_mode']
                                target_text.config(state=tk.NORMAL)
                                if display_mode == "新标签页":
                                    # 新标签页:替换内容
                                    target_text.delete("1.0", tk.END)
                                    target_text.insert(tk.END, f"[{analysis_info['option_name']}] 分析结果\n\n")
                                    target_text.insert(tk.END, f"维度说明:{analysis_info['option_desc']}\n\n")
                                    target_text.insert(tk.END, "="*50 + "\n\n")
                                    target_text.insert(tk.END, ai_result)
                                    target_text.see("1.0")
                                else:
                                    # 累计显示:删除"正在分析"部分,替换为结果
                                    start_pos = analysis_info.get('analysis_start_pos')
                                    if start_pos:
                                        # 删除从开始位置到末尾的内容
                                        target_text.delete(start_pos, tk.END)
                                        # 插入结果
                                        target_text.insert(tk.END, f"[{analysis_info['option_name']}] 分析结果\n\n")
                                        target_text.insert(tk.END, f"维度说明:{analysis_info['option_desc']}\n\n")
                                        target_text.insert(tk.END, "="*50 + "\n\n")
                                        target_text.insert(tk.END, ai_result + "\n")
                                        target_text.see(tk.END)
                                target_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                        threading.Thread(target=analyze, daemon=True).start()
                    def run_comprehensive_analysis():
                        """运行综合分析"""
                        problem = problem_text.get("1.0", tk.END).strip()
                        if not problem:
                            problem = default_question
                        # 获取显示方式
                        display_mode = display_mode_var.get()
                        # 存储分析状态
                        analysis_info = {
                            'display_mode': display_mode,
                            'target_text': None,
                            'tab_id': None,
                            'analysis_start_pos': None
                        }
                        # 根据显示方式处理
                        if display_mode == "新标签页":
                            # 创建新标签页
                            from datetime import datetime
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            tab_title = f"三维问询-综合分析-{current_time}"
                            tab_id = self.create_result_tab(tab_title)
                            target_text = self.result_tabs[tab_id]['widget']
                            analysis_info['target_text'] = target_text
                            analysis_info['tab_id'] = tab_id
                            target_text.config(state=tk.NORMAL)
                            target_text.delete("1.0", tk.END)
                            target_text.insert(tk.END, "正在综合分析三个维度...\n\n")
                            target_text.config(state=tk.DISABLED)
                        else:
                            # 累计显示在当前界面
                            target_text = result_text
                            analysis_info['target_text'] = target_text
                            target_text.config(state=tk.NORMAL)
                            # 记录插入位置
                            analysis_info['analysis_start_pos'] = target_text.index(tk.END)
                            # 追加内容,不清空
                            current_content = target_text.get("1.0", tk.END)
                            if current_content.strip():
                                target_text.insert(tk.END, "\n" + "="*80 + "\n\n")
                            target_text.insert(tk.END, "正在综合分析三个维度...\n\n")
                            target_text.config(state=tk.DISABLED)
                        def analyze():
                            try:
                                comprehensive_prompt = f"""请根据以下三个维度进行综合分析:
{problem}
请分别分析以下三个维度,每个维度最高33.3分,总分100分:
1. 股票指数基本面:分析当前股票指数的基本面情况
2. 外围的市场情况:分析外围市场的情况
3. 市场的情绪:分析市场情绪状况
请为每个维度提供:
- 当前状况分析
- 评分(0-33.3分)
- 评分理由
- 风险提示
最后提供:
- 总分(三个维度分数相加)
- 综合判断
- 投资建议"""
                                system_prompt = "你是一位资深的市场分析专家,能够从多个维度深入分析市场状况,提供专业的评分和建议。"
                                ai_result = self.call_ai_model(comprehensive_prompt, system_prompt)
                                if not ai_result:
                                    ai_result = "未获取到AI分析结果,请检查配置。"
                            except Exception as e:
                                ai_result = f"AI分析失败: {e}"
                            def update_ui():
                                target_text = analysis_info['target_text']
                                display_mode = analysis_info['display_mode']
                                target_text.config(state=tk.NORMAL)
                                if display_mode == "新标签页":
                                    # 新标签页:替换内容
                                    target_text.delete("1.0", tk.END)
                                    target_text.insert(tk.END, "【三维综合分析结果】\n\n")
                                    target_text.insert(tk.END, "="*50 + "\n\n")
                                    target_text.insert(tk.END, ai_result)
                                    target_text.see("1.0")
                                else:
                                    # 累计显示:删除"正在分析"部分,替换为结果
                                    start_pos = analysis_info.get('analysis_start_pos')
                                    if start_pos:
                                        # 删除从开始位置到末尾的内容
                                        target_text.delete(start_pos, tk.END)
                                        # 插入结果
                                        target_text.insert(tk.END, "【三维综合分析结果】\n\n")
                                        target_text.insert(tk.END, "="*50 + "\n\n")
                                        target_text.insert(tk.END, ai_result + "\n")
                                        target_text.see(tk.END)
                                target_text.config(state=tk.DISABLED)
                            if hasattr(self, "root") and self.root.winfo_exists():
                                self.root.after(0, update_ui)
                        threading.Thread(target=analyze, daemon=True).start()
                    # 按钮区域
                    button_frame = ttk.Frame(control_frame)
                    button_frame.grid(row=row+1, column=0, columnspan=buttons_per_row, pady=(10, 0), sticky="ew")
                    ttk.Button(button_frame, text="综合分析",
                              command=run_comprehensive_analysis).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="清空",
                              command=lambda: [problem_text.delete("1.0", tk.END), result_text.config(state=tk.NORMAL), result_text.delete("1.0", tk.END), result_text.config(state=tk.DISABLED)]).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="复制结果",
                              command=lambda: self._copy_result(result_text)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="添加到咨询",
                              command=lambda: self._add_to_consultation(result_text)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(button_frame, text="添加到警示",
                              command=lambda: self._add_to_warning(result_text)).pack(side=tk.LEFT, padx=5)
                    # 窗口控制按钮
                    control_btn_frame = ttk.Frame(win)
                    control_btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
                    def toggle_minimize():
                        """切换最小化/恢复"""
                        if win._is_minimized:
                            win.geometry(win._original_geometry)
                            win._is_minimized = False
                            minimize_btn.config(text="最小化")
                        else:
                            win._original_geometry = win.geometry()
                            win.geometry("200x50")
                            win._is_minimized = True
                            minimize_btn.config(text="恢复")
                    def toggle_maximize():
                        """切换最大化/恢复"""
                        try:
                            # Windows平台使用state('zoomed')
                            if win.state() == 'zoomed':
                                win.state('normal')
                                win.geometry(win._original_geometry)
                                maximize_btn.config(text="最大化")
                            else:
                                win._original_geometry = win.geometry()
                                win.state('zoomed')
                                maximize_btn.config(text="恢复")
                        except:
                            # 如果state不支持,尝试使用geometry
                            try:
                                current_geom = win.geometry()
                                if hasattr(win, '_is_maximized') and win._is_maximized:
                                    win.geometry(win._original_geometry)
                                    win._is_maximized = False
                                    maximize_btn.config(text="最大化")
                                else:
                                    win._original_geometry = current_geom
                                    # 获取屏幕尺寸
                                    screen_width = win.winfo_screenwidth()
                                    screen_height = win.winfo_screenheight()
                                    win.geometry(f"{screen_width}x{screen_height}+0+0")
                                    win._is_maximized = True
                                    maximize_btn.config(text="恢复")
                            except Exception as e:
                                messagebox.showinfo("提示", f"最大化功能不可用: {e}")
                    minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
                    minimize_btn.pack(side=tk.LEFT, padx=5)
                    maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
                    maximize_btn.pack(side=tk.LEFT, padx=5)
                    ttk.Button(control_btn_frame, text="隐藏", command=win.withdraw, width=10).pack(side=tk.LEFT, padx=5)
                    ttk.Button(control_btn_frame, text="显示", command=win.deiconify, width=10).pack(side=tk.LEFT, padx=5)
                    ttk.Button(control_btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.RIGHT, padx=5)
                except Exception as e:
                    messagebox.showerror("错误", f"打开三维问询界面失败: {e}")
                    import traceback
                    traceback.print_exc()
            three_dimension_btn = ttk.Button(right_checkbox_frame, text="三维问询", command=show_three_dimension_analysis, width=15)
            three_dimension_btn.pack(pady=(10, 0))
            # 警示通言列表(交易法则上方显示10条)
            warning_links_top_frame = ttk.LabelFrame(right_pane, text="警示通言 (前10条)", padding=10)
            warning_links_top_frame.pack(fill=tk.X, padx=5, pady=(10, 5))
            def populate_top_warning_links():
                for widget in warning_links_top_frame.winfo_children():
                    widget.destroy()
                records = fetch_warning_records(10)
                if not records:
                    ttk.Label(warning_links_top_frame, text="暂无警示通言记录", font=("TkDefaultFont", 11)).pack(anchor=tk.W)
                    return
                for idx, (_, tab_name, content, created_at) in enumerate(records, start=1):
                    date_text = created_at.split(" ")[0] if created_at else ""
                    display_text = f"{idx}. {tab_name} ({date_text})"
                    link_label = ttk.Label(warning_links_top_frame, text=display_text, foreground="blue", cursor="hand2")
                    link_label.pack(anchor=tk.W, pady=1)
                    link_label.bind("<Button-1>", lambda e, c=content, t=tab_name: show_warning_popup(c, t))
            populate_top_warning_links()
            # 交易法则显示区域(移到右下区域,当前状态下面)
            trading_rule_frame = ttk.LabelFrame(right_pane, text="交易法则", padding=10)
            trading_rule_frame.pack(fill=tk.X, padx=5, pady=(10, 5))
            trading_rule_text = """子攻操生现金流,低买高卖势位态。
就是1日线5日线10日20日线需要多头发散。
买入低于筹码成本价。
卖出高于筹码成本价。
选择通道低位底分型买入。"""
            trading_rule_label = ttk.Label(trading_rule_frame, text=trading_rule_text,
                                         font=("TkDefaultFont", 12, "bold"),
                                         foreground="blue", justify=tk.LEFT)
            trading_rule_label.pack(anchor=tk.W)
        # 创建通用的开新仓对话框函数
        def create_new_position_dialog(position_type="绩优股"):
            """创建开新仓对话框的通用函数"""
            return show_new_position_dialog(position_type)
        # 绑定开新仓按钮(恢复原来的对话框方式)
        new_position_button.config(command=lambda: create_new_position_dialog("龙头"))
        new_position_button2.config(command=lambda: create_new_position_dialog("强势股"))
        new_position_button3.config(command=lambda: create_new_position_dialog("绩优股"))
        new_position_button4.config(command=lambda: create_new_position_dialog("朋友"))
        new_position_button5.config(command=lambda: create_new_position_dialog("均值回归"))
        # 初始化显示
        update_position()
        # 保存引用以便后续使用
        self.position_vars = {
            'emotion': emotion_var,
            'v_judge': v_judge_var,
            'yesterday': yesterday_var,
            'result': position_result_var,
            'canvas': light_canvas,
            'total_score_var': total_score_var
        }
        self.main_sector_var = main_sector_var
        self.stop_loss_var = stop_loss_var
        self.new_position_var = new_position_var
        # 交易标签页(在仓位/交易标签页控件框中,调整padding使其更紧凑)
        trading_tab = ttk.Frame(self.position_trading_notebook, padding=2)
        self.position_trading_notebook.add(trading_tab, text="交易")
        # 左侧工具条:固定两行(全~新闻搜索)
        toolbar_frame = ttk.Frame(left_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 1))
        toolbar_row1 = ttk.Frame(toolbar_frame)
        toolbar_row1.pack(fill=tk.X, pady=(0, 1))
        toolbar_row2 = ttk.Frame(toolbar_frame)
        toolbar_row2.pack(fill=tk.X)
        tp = 2
        for idx_btn, (txt, w, cmd) in enumerate([
            ("全", 3, self.show_market_situation),
            ("自选股管理", 8, self.show_stock_management_dialog),
            ("最新N条分析", 9, self.analyze_latest_n_stocks),
            ("📊 批量股票分析", 9, self.show_batch_stock_analyzer),
            ("龙虎榜", 6, self.show_top_list_dialog),
        ]):
            ttk.Button(toolbar_row1, text=txt, width=w, command=cmd).pack(
                side=tk.LEFT, padx=(0 if idx_btn == 0 else tp, 0)
            )
        batch_crawl_news_btn = tk.Button(
            toolbar_row2, text="批量爬取资讯", width=10,
            command=self.batch_crawl_news, bg="yellow", fg="black",
            font=("TkDefaultFont", 10)
        )
        batch_crawl_news_btn.pack(side=tk.LEFT, padx=(0, tp))
        self.batch_crawl_news_btn = batch_crawl_news_btn
        for txt, w, cmd in [
            ("信号", 4, self.show_signal_all_holdings_detection),
            ("回测", 6, self.show_backtest_dialog),
            ("五星跟随", 7, self.show_five_star_follow_dialog),
            ("新闻搜索", 7, self.launch_keyword_search_app),
            ("K线图", 6, self.show_kline_dialog),
            ("韭淘热点", 7, self.show_jiutao_hot_spot_analysis),
        ]:
            ttk.Button(toolbar_row2, text=txt, width=w, command=cmd).pack(side=tk.LEFT, padx=(0, tp))
        # 快速爬取/文本控制标签页控件框(共用一块区域,可以切换)
        crawler_control_notebook = ttk.Notebook(left_frame)
        crawler_control_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        # 快速爬取标签页
        crawler_frame = ttk.Frame(crawler_control_notebook, padding=5)
        crawler_control_notebook.add(crawler_frame, text="快速爬取")
        # 工具标签页(快速爬取里的不常用按钮移过来)
        tools_frame = ttk.Frame(crawler_control_notebook, padding=5)
        crawler_control_notebook.add(tools_frame, text="工具")
        # 将咨询分析、投资、系统、赌博、交易体系、交割单分析按钮移到交易标签页
        trading_buttons_frame = ttk.LabelFrame(trading_tab, text="交易功能", padding=3)
        trading_buttons_frame.pack(fill=tk.X, expand=False, pady=2)
        _tf_pad = {"side": tk.LEFT, "padx": 1, "pady": 1, "fill": tk.X, "expand": True}
        _tf_w = 11
        # 买入信号标签:当日有买入信号时显示"本买"红色字
        self.buy_signal_label = ttk.Label(trading_buttons_frame, text="", font=("TkDefaultFont", 12, "bold"), foreground="red")
        self.buy_signal_label.pack(fill=tk.X, pady=(0, 1))
        trade_row_a = ttk.Frame(trading_buttons_frame)
        trade_row_a.pack(fill=tk.X, pady=1)
        ttk.Button(trade_row_a, text="📊 持仓实时", command=self.show_holding_realtime_stats, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_a, text="📋 粘贴实时", command=self.show_paste_realtime_stats, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_a, text="🛗 坐电梯", command=self.show_elevator_dialog, width=_tf_w).pack(**_tf_pad)
        trade_row_b = ttk.Frame(trading_buttons_frame)
        trade_row_b.pack(fill=tk.X, pady=1)
        ttk.Button(trade_row_b, text="💼 咨询分析", command=self.show_consultation_analysis, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_b, text="💰 投资", command=self.show_investment_analysis, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_b, text="📊 系统", command=self.show_investment_system, width=_tf_w).pack(**_tf_pad)
        trade_row_c = ttk.Frame(trading_buttons_frame)
        trade_row_c.pack(fill=tk.X, pady=1)
        ttk.Button(trade_row_c, text="🎲 赌博", command=self.show_gambling_analysis, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_c, text="📋 图文分析", command=self.show_delivery_analysis, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_c, text="📈 交易体系", command=self.show_trading_system, width=_tf_w).pack(**_tf_pad)
        ttk.Button(trade_row_c, text="📑 基本面", command=self.show_fundamental_analysis, width=_tf_w).pack(**_tf_pad)
        # 第四行:预警开关(拆两行,避免左侧被挤出可视区)
        alert_switch_row1 = ttk.Frame(trading_buttons_frame)
        alert_switch_row1.pack(fill=tk.X, pady=(3, 1))
        alert_switch_row1b = ttk.Frame(trading_buttons_frame)
        alert_switch_row1b.pack(fill=tk.X, pady=(0, 1))
        _al_pad = 4
        ttk.Label(alert_switch_row1, text="预警:", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        amplitude_switch_frame = ttk.Frame(alert_switch_row1)
        amplitude_switch_frame.pack(side=tk.LEFT, padx=_al_pad)
        ttk.Label(amplitude_switch_frame, text="振幅:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.amplitude_alert_var = tk.BooleanVar(value=False)  # 默认关闭
        amplitude_switch = ttk.Checkbutton(amplitude_switch_frame, variable=self.amplitude_alert_var,
                                           text="开", command=self._on_amplitude_alert_toggle)
        amplitude_switch.pack(side=tk.LEFT)
        ma_switch_frame = ttk.Frame(alert_switch_row1)
        ma_switch_frame.pack(side=tk.LEFT, padx=_al_pad)
        ttk.Label(ma_switch_frame, text="均线:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.ma_alert_var = tk.BooleanVar(value=False)  # 默认关闭
        ma_switch = ttk.Checkbutton(ma_switch_frame, variable=self.ma_alert_var,
                                    text="开", command=self._on_ma_alert_toggle)
        ma_switch.pack(side=tk.LEFT)
        break_ma1_switch_frame = ttk.Frame(alert_switch_row1)
        break_ma1_switch_frame.pack(side=tk.LEFT, padx=_al_pad)
        ttk.Label(break_ma1_switch_frame, text="破1:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.break_ma1_alert_var = tk.BooleanVar(value=False)  # 默认关闭
        break_ma1_switch = ttk.Checkbutton(break_ma1_switch_frame, variable=self.break_ma1_alert_var,
                                           text="开", command=self._on_break_ma1_alert_toggle)
        break_ma1_switch.pack(side=tk.LEFT)
        break_ma5_switch_frame = ttk.Frame(alert_switch_row1b)
        break_ma5_switch_frame.pack(side=tk.LEFT, padx=(6, _al_pad))
        ttk.Label(break_ma5_switch_frame, text="破5:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.break_ma5_alert_var = tk.BooleanVar(value=False)  # 默认关闭
        break_ma5_switch = ttk.Checkbutton(break_ma5_switch_frame, variable=self.break_ma5_alert_var,
                                           text="开", command=self._on_break_ma5_alert_toggle)
        break_ma5_switch.pack(side=tk.LEFT)
        break_ma20_switch_frame = ttk.Frame(alert_switch_row1b)
        break_ma20_switch_frame.pack(side=tk.LEFT, padx=_al_pad)
        ttk.Label(break_ma20_switch_frame, text="破20:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.break_ma20_alert_var = tk.BooleanVar(value=False)  # 默认关闭
        break_ma20_switch = ttk.Checkbutton(break_ma20_switch_frame, variable=self.break_ma20_alert_var,
                                            text="开", command=self._on_break_ma20_alert_toggle)
        break_ma20_switch.pack(side=tk.LEFT)
        cb_arbitrage_btn = ttk.Button(alert_switch_row1b, text="可转债", command=self._show_cb_arbitrage_popup)
        cb_arbitrage_btn.pack(side=tk.LEFT, padx=6)
        # 第二行:持仓情绪监测和板块指数下拉框
        alert_switch_row2 = ttk.Frame(trading_buttons_frame)
        alert_switch_row2.pack(fill=tk.X, pady=1)
        sector_sentiment_switch_frame = ttk.Frame(alert_switch_row2)
        sector_sentiment_switch_frame.pack(side=tk.LEFT, padx=4)
        ttk.Label(sector_sentiment_switch_frame, text="板块情绪:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.sector_sentiment_var = tk.BooleanVar(value=False)  # 默认关闭
        sector_sentiment_switch = ttk.Checkbutton(sector_sentiment_switch_frame, variable=self.sector_sentiment_var,
                                                  text="开", command=self._on_sector_sentiment_toggle)
        sector_sentiment_switch.pack(side=tk.LEFT)
        sector_sentiment_btn = ttk.Button(sector_sentiment_switch_frame, text="查看",
                                         command=self._show_sector_sentiment_monitor)
        sector_sentiment_btn.pack(side=tk.LEFT, padx=(4, 0))
        sector_index_frame = ttk.Frame(alert_switch_row2)
        sector_index_frame.pack(side=tk.LEFT, padx=4)
        ttk.Label(sector_index_frame, text="板块指数:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.sector_index_combo = ttk.Combobox(sector_index_frame, width=14, state="readonly")
        self.sector_index_combo.pack(side=tk.LEFT, padx=(0, 3))
        self._load_sector_index_list()  # 加载板块指数列表
        self.sector_index_combo['values'] = self.sector_index_list
        # 板块指数维护按钮
        sector_index_manage_btn = ttk.Button(sector_index_frame, text="维护",
                                            command=self._manage_sector_index_list)
        sector_index_manage_btn.pack(side=tk.LEFT, padx=(0, 3))
        chip_cost_btn = ttk.Button(alert_switch_row2, text="筹码成本", command=self._show_chip_cost_popup)
        chip_cost_btn.pack(side=tk.LEFT, padx=4)
        opportunity_btn = ttk.Button(alert_switch_row2, text="机会", command=self._show_opportunity_analysis)
        opportunity_btn.pack(side=tk.LEFT, padx=4)
        alert_switch_row3 = ttk.Frame(trading_buttons_frame)
        alert_switch_row3.pack(fill=tk.X, pady=1)
        alert_switch_row3b = ttk.Frame(trading_buttons_frame)
        alert_switch_row3b.pack(fill=tk.X, pady=1)
        holding_stock_monitor_frame = ttk.Frame(alert_switch_row3)
        holding_stock_monitor_frame.pack(side=tk.LEFT, padx=4)
        ttk.Label(holding_stock_monitor_frame, text="Main监测:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.holding_stock_monitor_var = tk.BooleanVar(value=False)  # 默认关闭
        holding_stock_monitor_switch = ttk.Checkbutton(holding_stock_monitor_frame, variable=self.holding_stock_monitor_var,
                                                       text="开", command=self._on_holding_stock_monitor_toggle)
        holding_stock_monitor_switch.pack(side=tk.LEFT)
        hot_stock_15min_monitor_frame = ttk.Frame(alert_switch_row3)
        hot_stock_15min_monitor_frame.pack(side=tk.LEFT, padx=4)
        ttk.Label(hot_stock_15min_monitor_frame, text="日K热门:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.hot_stock_15min_monitor_var = tk.BooleanVar(value=False)  # 默认关闭
        hot_stock_15min_monitor_switch = ttk.Checkbutton(hot_stock_15min_monitor_frame, variable=self.hot_stock_15min_monitor_var,
                                                         text="开", command=self._on_hot_stock_15min_monitor_toggle)
        hot_stock_15min_monitor_switch.pack(side=tk.LEFT)
        auto_collect_frame = ttk.Frame(alert_switch_row3b)
        auto_collect_frame.pack(side=tk.LEFT, padx=4)
        ttk.Label(auto_collect_frame, text="自动采集:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 3))
        self.auto_collect_var = tk.BooleanVar(value=self.auto_collect_enabled)
        auto_collect_switch = ttk.Checkbutton(auto_collect_frame, variable=self.auto_collect_var,
                                             text="开", command=self._on_auto_collect_toggle)
        auto_collect_switch.pack(side=tk.LEFT)
        # 创建持仓标签页(使用辅助函数)
        self._create_holding_tab(self.position_trading_notebook, "持仓", 1)
        # 创建持仓2、持仓3、持仓4、持仓历史股标签页
        self._create_holding_tab(self.position_trading_notebook, "龙头股", 2)
        self._create_holding_tab(self.position_trading_notebook, "15Min", 3)
        self._create_holding_tab(self.position_trading_notebook, "Main", 4)
        self._create_holding_tab(self.position_trading_notebook, "持仓历史股", 5)
        # 创建同花顺标签页(持仓6)
        self._create_holding_tab(self.position_trading_notebook, "同花顺", 6)
        # 创建持仓1-持仓8标签页(持仓7-14,用于从资讯表按日期+频次展示)
        self._create_holding_tab(self.position_trading_notebook, "持仓1", 7)
        self._create_holding_tab(self.position_trading_notebook, "持仓2", 8)
        self._create_holding_tab(self.position_trading_notebook, "持仓3", 9)
        self._create_holding_tab(self.position_trading_notebook, "持仓4", 10)
        self._create_holding_tab(self.position_trading_notebook, "持仓5", 11)
        self._create_holding_tab(self.position_trading_notebook, "持仓6", 12)
        self._create_holding_tab(self.position_trading_notebook, "持仓7", 13)
        self._create_holding_tab(self.position_trading_notebook, "持仓8", 14)
        # 从配置文件恢复标签页名称(如果有保存的名称;持仓7-14 之后由从资讯刷新覆盖)
        try:
            saved_tab_names = self.ai_config_manager.config.get("holding_tab_names", {})
            if saved_tab_names:
                for group_index_str, tab_name in saved_tab_names.items():
                    try:
                        group_index = int(group_index_str)
                        if 7 <= group_index <= 14:
                            continue  # 持仓7-14 由从资讯刷新设置 MMDD
                        notebook_index = group_index + 1
                        self.position_trading_notebook.tab(notebook_index, text=tab_name)
                        print(f"已恢复标签页 {group_index} 名称为: {tab_name}")
                    except Exception as e:
                        print(f"恢复标签页 {group_index_str} 名称失败: {e}")
        except Exception as e:
            print(f"读取保存的标签页名称失败: {e}")
        # 初次从资讯表加载最近8天数据到持仓7-14,并刷新 Main(最近5日合并频次):延后执行
        def _deferred_first_news_refresh():
            try:
                self._refresh_holding_tabs_from_news()
            except Exception as e:
                print(f"初次从资讯刷新持仓标签失败: {e}")
            try:
                self._refresh_main_from_news(silent=True)
            except Exception as e:
                print(f"初次从资讯刷新 Main 失败: {e}")
        try:
            self.root.after(15000, _deferred_first_news_refresh)  # 延后 15s 避免启动 GIL 竞争
        except Exception:
            try:
                self._refresh_holding_tabs_from_news()
            except Exception as e:
                print(f"初次从资讯刷新持仓标签失败: {e}")
        # 快速爬取:一键/工具按钮自动流式排列(约每行8个)
        batch_quick_frame = ttk.Frame(crawler_frame)
        batch_quick_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(
            batch_quick_frame,
            text="(按钮区自动换行:约每行8个)",
            font=("TkDefaultFont", 9),
            foreground="gray",
        ).pack(anchor=tk.W, padx=(0, 2), pady=(0, 3))
        quick_grid = ttk.Frame(batch_quick_frame)
        quick_grid.pack(fill=tk.X)
        # ===== 所有按钮的默认 tab 分配("quick"=快速爬取, "tools"=工具)=====
        # 按功能分组排序, grid会自动每行8个整齐排列
        _BUTTON_DEFAULTS = [
            # ---- 🏃 一键操作 (高频核心, quick) ----
            ("一键操作", self.one_click_pipeline, True, "quick"),
            ("一键思考", self.show_one_click_thinking, False, "quick"),
            ("一键爬虫", self.show_web_crawler, False, "quick"),
            ("🕷️ 蜘蛛读取", self.show_spider_reader, False, "quick"),
            ("一键爬取", self.batch_crawl_and_analyze, False, "quick"),
            ("一键分析", self.one_click_analyze_tabs, False, "quick"),
            ("一键资讯", self.one_click_save_news, False, "quick"),
            ("一键截图", self.one_click_screenshot, True, "quick"),
            # ---- 📡 爬取热门 (quick) ----
            ("爬取热门股", self._crawl_hot_stocks_combined, False, "quick"),
            ("热门股非去重", self._crawl_hot_stocks_full_no_dedup, False, "quick"),
            # ---- 🔍 选股/扫描 (quick) ----
            ("📊盘面诊断·做T还是持股", self._show_panpan_diagnosis, False, "quick"),
            ("🩸血腥筹码", self._show_blood_chips_dialog, False, "quick"),
            ("💼是否持有", self._show_should_hold_dialog, False, "quick"),
            ("🔥主线雷达", self._show_mainline_dialog, False, "quick"),
            ("🌱淘韭", self._show_taojiu_dialog, False, "quick"),
            ("坐电梯", self.show_elevator_dialog, False, "quick"),
            # ---- 🚦 红绿灯/大盘感知 (quick) ----
            ("🚦大盘风险", self._show_market_risk_dashboard, False, "quick"),
            ("🏦华尔街红绿灯", self._show_wall_street_traffic_light, False, "quick"),
            ("🇨🇳A股红绿灯", self._show_a_share_traffic_light, False, "quick"),
            ("⚠️盘中警告", self._show_intraday_alert_dialog, False, "quick"),
            ("📊持股仪表盘", self._show_portfolio_dashboard, False, "quick"),
            ("🦅游资心法", self._show_hotmoney_check, False, "quick"),
            ("🏅贵金属", self._show_precious_metals_dialog, False, "quick"),
            # ---- 💰 资金/持仓 (quick) ----
            ("📈资金方向", self._show_capital_direction_dialog, False, "quick"),
            ("💰是否加仓", self._show_add_position_dialog, False, "quick"),
            # ---- 🤖 AI分析 (quick) ----
            ("背离做T", self._show_divergence_t_v2, False, "quick"),
            ("✍️AI写手", self._show_ai_writer_dialog, False, "quick"),
            ("🎬短剧写手", self._show_short_drama_dialog, False, "quick"),
            ("📊舆情助手", self._show_public_opinion_dialog, False, "quick"),
            # ---- 📰 资讯分析 (quick) ----
            ("近期资讯分析", self.show_news_data_dialog, False, "quick"),
            ("资讯AI分析", self.show_monthly_comprehensive_analysis, False, "quick"),
            # ---- 🔧 Skill工具 (quick) ----
            ("Skill", self.show_iwencai_skillhub_dialog, False, "quick"),
            ("Skill浏览器", self._show_qclaw_skills_browser, False, "quick"),
            # ================================================
            # ---- 📰 新闻 (tools) ----
            ("突发新闻", self.show_breaking_news_dialog, False, "tools"),
            ("实时新闻", self.show_realtime_world_news_dialog, False, "tools"),
            ("📈量价齐升", self._show_volume_price_popup, False, "tools"),
            ("🎯ETF六军", self._show_etf20_popup, False, "tools"),
            # ---- 📊 研判 (tools) ----
            ("系统研判", self.show_system_judgment_dialog, False, "tools"),
            ("凯利设定", self._show_kelly_config, False, "tools"),
            ("情绪", self.show_market_sentiment_dialog, False, "tools"),
            ("行情统计", self.show_market_breadth_stats_dialog, False, "tools"),
            ("量化", self.show_quant_strategy_dialog, False, "tools"),
            # ---- 🔧 技术工具 (tools) ----
            ("关键词搜索", self.launch_keyword_search_app, False, "tools"),
            ("操作系统1", self.show_os1_trading_rules_dialog, False, "tools"),
            ("AI员工", self.show_ai_staff_dialog, False, "tools"),
            ("分析引擎", self.show_stock_analysis_engine_dialog, False, "tools"),
            ("OCR识别", self.open_ocr_crawler, False, "tools"),
            ("tushare", self.show_tushare_skills_dialog, False, "tools"),
            # ---- 💼 持仓/预测 (tools) ----
            ("自持股监测", self._show_self_holding_monitor_popup, False, "tools"),
            ("🧬生命周期", self._show_lifecycle_popup, False, "tools"),
            ("🎭情绪周期", self._show_emo_cycle_dialog, False, "tools"),
            ("🔮明日预测", self._show_tomorrow_predict_popup, False, "tools"),
            ("预测", self.show_news_prediction_analysis, False, "tools"),
        ]
        # 从配置加载自定义 tab 分配
        _saved = {}
        try:
            _saved = (self.ai_config_manager.config or {}).get("button_tab_assignments", {}) or {}
        except Exception:
            _saved = {}
        # _button_data: { txt: {"cmd": fn, "yellow": bool, "tab": str} }
        _button_data = {}
        for _txt, _cmd, _y, _default_tab in _BUTTON_DEFAULTS:
            _button_data[_txt] = {
                "cmd": _cmd,
                "yellow": _y,
                "tab": _saved.get(_txt, _default_tab),
            }
        # 编辑模式状态
        self._btn_edit_mode = False
        _quick_buttons = []   # (txt, widget)
        _tools_buttons = []
        _edit_btn_ref = {"quick": None, "tools": None}
        # 统一按钮宽度: 让 grid sticky="we" 自动拉伸填满列,按钮按文字自适应但设最小宽度防过窄
        def _text_width(_t):
            _w = 0
            for _c in _t:
                _w += 2 if ord(_c) > 127 else 1
            return _w
        _MAX_BTN_W = max(_text_width(_t) for _t, *_ in _BUTTON_DEFAULTS)
        # 按最长按钮文字算需要的 width, 加2留余量, 但不超过 20 (避免超宽)
        _BTN_MIN_WIDTH = max(10, min(20, _MAX_BTN_W // 2 + 3))
        def _build_button(_parent, _txt, _info):
            """创建按钮:不用固定 width 截断文字,靠 grid sticky='we' 自动拉伸等宽"""
            if _info["yellow"]:
                _b = tk.Button(_parent, text=_txt, bg="yellow", fg="black")
                # tk.Button 用 padx 控制最小宽度
                _b.config(padx=6)
            else:
                _b = ttk.Button(_parent, text=_txt)
                # ttk.Button 设置最小字符宽度,但让文字完整显示不截断
                try:
                    _b.config(width=max(_BTN_MIN_WIDTH, len(_txt) // 2 + 4))
                except Exception:
                    pass
            return _b
        def _apply_button_command(_b, _txt, _info):
            """根据编辑模式设置按钮 command 和样式"""
            if self._btn_edit_mode:
                _b.config(command=lambda t=_txt: _popup_move_menu(t, _b))
                # 编辑模式下边框变红
                try:
                    _b.config(highlightbackground="red", highlightthickness=2)
                except Exception:
                    pass
            else:
                _b.config(command=_info["cmd"])
                try:
                    _b.config(highlightbackground="systemWindowBackgroundColor", highlightthickness=0)
                except Exception:
                    pass
        def _popup_move_menu(_txt, _btn_widget):
            """编辑模式下右键/点击按钮弹出移动菜单"""
            _menu = tk.Menu(self.root, tearoff=0)
            _current_tab = _button_data[_txt]["tab"]
            _menu.add_command(
                label=f"移到 → 快速爬取 {'✓' if _current_tab=='quick' else ''}",
                command=lambda: _move_button(_txt, "quick"))
            _menu.add_command(
                label=f"移到 → 工具 {'✓' if _current_tab=='tools' else ''}",
                command=lambda: _move_button(_txt, "tools"))
            _menu.add_separator()
            _menu.add_command(label="取消", command=lambda: None)
            _menu.tk_popup(_btn_widget.winfo_rootx(), _btn_widget.winfo_rooty() + _btn_widget.winfo_height())
        def _move_button(_txt, _new_tab):
            """移动按钮到新 tab 并保存配置"""
            if _button_data[_txt]["tab"] == _new_tab:
                return
            _button_data[_txt]["tab"] = _new_tab
            # 保存到配置
            try:
                _assignments = {t: d["tab"] for t, d in _button_data.items()}
                self.ai_config_manager.config["button_tab_assignments"] = _assignments
                self.ai_config_manager.save_config()
            except Exception as e:
                print(f"保存按钮tab配置失败: {e}")
            _render_all()
        def _reflow_grid(_grid, _buttons):
            """统一的 grid 排列函数: 每行 8 个, 按钮拉伸填满列, 不截断文字"""
            try:
                _cols = 8
                for _b in _buttons:
                    _b.grid_forget()
                for _c in range(_cols):
                    _grid.grid_columnconfigure(_c, weight=1)
                for _i, _b in enumerate(_buttons):
                    _r, _c = divmod(_i, _cols)
                    _b.grid(row=_r, column=_c, sticky="we", padx=4, pady=3)
            except Exception:
                pass
        def _render_all():
            """按当前 tab 分配重新渲染两个 grid"""
            nonlocal _quick_buttons, _tools_buttons
            # 清空旧按钮
            for _txt, _b in _quick_buttons + _tools_buttons:
                _b.destroy()
            _quick_buttons = []
            _tools_buttons = []
            for _txt, _info in _button_data.items():
                _target_grid = quick_grid if _info["tab"] == "quick" else tools_grid
                _b = _build_button(_target_grid, _txt, _info)
                _apply_button_command(_b, _txt, _info)
                # 绑定右键菜单(始终可用)
                _b.bind("<Button-3>", lambda _e, t=_txt, b=_b: _popup_move_menu(t, b))
                if _info["tab"] == "quick":
                    _quick_buttons.append((_txt, _b))
                else:
                    _tools_buttons.append((_txt, _b))
                # 关键引用
                if _txt == "一键操作":
                    self.one_click_pipeline_btn = _b
                elif _txt == "一键截图":
                    self.one_click_screenshot_btn = _b
            _reflow_grid(quick_grid, [b for _, b in _quick_buttons])
            _reflow_grid(tools_grid, [b for _, b in _tools_buttons])
            # 刷新编辑按钮文字
            for _tab, _ref in _edit_btn_ref.items():
                if _ref is not None:
                    _count = len(_quick_buttons) if _tab == "quick" else len(_tools_buttons)
                    _label = "✏️退出编辑" if self._btn_edit_mode else f"✏️编辑({_count})"
                    _ref.config(text=_label)
        # ===== 工具标签页框架 =====
        tools_batch_frame = ttk.Frame(tools_frame)
        tools_batch_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(tools_batch_frame, text="工具(不常用功能集中在此,右键按钮可移动)",
                  font=("TkDefaultFont", 9), foreground="gray").pack(anchor=tk.W, padx=(0, 2), pady=(0, 3))
        tools_grid = ttk.Frame(tools_batch_frame)
        tools_grid.pack(fill=tk.X)
        # ===== 快速爬取 tab 顶部操作栏(编辑按钮 + 计数)=====
        quick_header = ttk.Frame(batch_quick_frame)
        quick_header.pack(fill=tk.X, pady=(0, 2))
        _edit_btn_ref["quick"] = ttk.Button(
            quick_header, text="✏️编辑", width=12,
            command=lambda: self._toggle_btn_edit_mode() if hasattr(self, '_toggle_btn_edit_mode') else None)
        _edit_btn_ref["quick"].pack(side=tk.LEFT)
        # 给 self 绑定编辑模式切换方法
        def _toggle_edit(self_=self):
            self_._btn_edit_mode = not self_._btn_edit_mode
            _render_all()
            if self_._btn_edit_mode:
                _edit_btn_ref["quick"].config(text="✏️退出编辑")
                try:
                    self_.root.bell()
                except Exception:
                    pass
            else:
                _edit_btn_ref["quick"].config(text="✏️编辑")
        self._toggle_btn_edit_mode = _toggle_edit  # type: ignore
        _edit_btn_ref["quick"].config(command=_toggle_edit)
        # ===== 初始渲染 =====
        _render_all()
        # 延迟绑定 configure 事件(grid 引用在闭包里了)
        def _bind_reflow():
            quick_grid.bind("<Configure>", lambda _e: _reflow_grid(quick_grid, [b for _, b in _quick_buttons]))
            tools_grid.bind("<Configure>", lambda _e: _reflow_grid(tools_grid, [b for _, b in _tools_buttons]))
        self.root.after(50, _bind_reflow)
        crawler_buttons_wrapper = ttk.Frame(crawler_frame)
        crawler_buttons_wrapper.pack(fill=tk.X)
        crawler_buttons_frame = ttk.Frame(crawler_buttons_wrapper)
        crawler_buttons_frame.pack(fill=tk.X)
        # 合并为单行按钮区(原两行并为一行)
        row1 = ttk.Frame(crawler_buttons_frame)
        row1.pack(fill=tk.X, pady=(0, 3))
        row2 = row1
        # 存储复选框变量
        self.crawler_checkboxes = {}
        # 存储市场导航复选框变量
        self.market_nav_checkboxes = {}
        # 保存行引用以便后续刷新
        self.crawler_row1 = row1
        self.crawler_row2 = row2
        # 从配置文件加载爬取按钮配置并创建按钮
        # 确保在创建按钮之前先加载配置(如果还没有加载的话)
        if not self.crawler_config or (isinstance(self.crawler_config, dict) and len(self.crawler_config) == 0):
            self.crawler_config = self.load_crawler_config()
        self._build_crawler_buttons(row1, row2)
        emotion_lights_strip = ttk.Frame(crawler_frame)
        emotion_lights_strip.pack(fill=tk.X, pady=(4, 0))
        emotion_lights_frame = ttk.Frame(emotion_lights_strip)
        emotion_lights_frame.pack(side=tk.LEFT, anchor=tk.W, padx=0, pady=2)
        # 情绪灯为红色时滚动播放的文本框(箭头位置)+ 管理弹窗录入
        self.emotion_red_scroll_after_id = None
        self.emotion_red_scroll_index = 0
        default_scroll_text = "情绪下行,谨慎操作\n禁止开新仓\n减仓观望"
        self.emotion_red_scroll_lines = [
            s.strip() for s in self.ai_config_manager.config.get("emotion_red_scroll_text", default_scroll_text).split("\n") if s.strip()
        ] or [default_scroll_text]
        scroll_text_frame = tk.Frame(emotion_lights_frame, width=156, height=76, highlightthickness=2, highlightbackground="#cc6666", bg="#ffcccc")
        scroll_text_frame.pack(side=tk.LEFT, padx=(0, 10), pady=2)
        scroll_text_frame.pack_propagate(False)
        self.emotion_red_scroll_label = tk.Label(scroll_text_frame, text="", font=("TkDefaultFont", 12, "bold"), wraplength=140, bg="#ffcccc", fg="red", justify=tk.LEFT)
        self.emotion_red_scroll_label.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        def _emotion_red_scroll_tick():
            self.emotion_red_scroll_after_id = None
            if not getattr(self, 'emotion_red_scroll_lines', None):
                return
            cycle = getattr(self, 'emotion_cycle_var', None)
            if cycle and cycle.get() != "下行":
                return
            lines = self.emotion_red_scroll_lines
            if lines:
                idx = self.emotion_red_scroll_index % len(lines)
                # 一次显示2到3行
                show_lines = lines[idx:idx+3]
                self.emotion_red_scroll_label.config(text="\n".join(show_lines))
                self.emotion_red_scroll_index += 1
            if cycle and cycle.get() == "下行":
                self.emotion_red_scroll_after_id = self.root.after(2500, _emotion_red_scroll_tick)
        def _update_emotion_red_scroll_visibility(*args):
            cycle = getattr(self, 'emotion_cycle_var', None)
            if not cycle:
                return
            if self.emotion_red_scroll_after_id:
                self.root.after_cancel(self.emotion_red_scroll_after_id)
                self.emotion_red_scroll_after_id = None
            if cycle.get() == "下行":
                self.emotion_red_scroll_index = 0
                _emotion_red_scroll_tick()
                scroll_text_frame.config(highlightbackground="#cc0000", bg="#ffcccc")
                self.emotion_red_scroll_label.config(bg="#ffcccc", fg="red")
            else:
                self.emotion_red_scroll_label.config(text="")
                scroll_text_frame.config(highlightbackground="#cc6666", bg="#e0e0e0")
                self.emotion_red_scroll_label.config(bg="#e0e0e0", fg="gray")
        def _open_emotion_red_scroll_manage():
            win = self._toplevel(self.root)
            win.title("情绪红灯滚动文字 - 管理")
            win.geometry("400x280")
            win.transient(self.root)
            ttk.Label(win, text="情绪周期为红色时,文本框将滚动播放以下内容(每行一条,可多行):", font=("TkDefaultFont", 11)).pack(anchor=tk.W, padx=10, pady=(10, 4))
            text_widget = tk.Text(win, height=10, width=50, wrap=tk.WORD, font=("TkDefaultFont", 12))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            text_widget.insert("1.0", "\n".join(self.emotion_red_scroll_lines))
            def _save_and_close():
                content = text_widget.get("1.0", tk.END).strip()
                self.ai_config_manager.config["emotion_red_scroll_text"] = content
                self.ai_config_manager.save_config()
                self.emotion_red_scroll_lines = [s.strip() for s in content.split("\n") if s.strip()] or ["情绪下行,谨慎操作"]
                if getattr(self, 'emotion_cycle_var', None) and self.emotion_cycle_var.get() == "下行":
                    self.emotion_red_scroll_index = 0
                    if self.emotion_red_scroll_after_id:
                        self.root.after_cancel(self.emotion_red_scroll_after_id)
                    _emotion_red_scroll_tick()
                win.destroy()
            btn_frame = ttk.Frame(win)
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            ttk.Button(btn_frame, text="保存并关闭", command=_save_and_close, width=12).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(btn_frame, text="取消", command=win.destroy, width=10).pack(side=tk.LEFT)
        ttk.Button(emotion_lights_frame, text="管理", width=6, command=_open_emotion_red_scroll_manage).pack(side=tk.LEFT, padx=(0, 8))
        # 右侧空白区域:Skill 下拉框(选择后弹出该 Skill 并展示帮助)
        skill_pick_frame = ttk.LabelFrame(emotion_lights_strip, text="Skill", padding=6)
        skill_pick_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(12, 0))
        ttk.Label(skill_pick_frame, text="选择:").pack(side=tk.LEFT)
        self.quick_skill_map = {"通用问财(OpenAPI)": {"id": "__generic__", "title": "通用问财(OpenAPI)", "skill_md": ""}}
        try:
            for s in self._discover_iwencai_skills_from_disk():
                label = f'{s.get("title","")} [{s.get("id","")}]'
                self.quick_skill_map[label] = s
        except Exception:
            pass
        self.quick_skill_var = tk.StringVar(value="通用问财(OpenAPI)")
        quick_skill_combo = ttk.Combobox(
            skill_pick_frame,
            textvariable=self.quick_skill_var,
            values=list(self.quick_skill_map.keys()),
            state="readonly",
            width=38,
        )
        quick_skill_combo.pack(side=tk.LEFT, padx=(6, 6), fill=tk.X, expand=True)
        def _open_selected_skill_popup(_event=None):
            key = self.quick_skill_var.get()
            ent = self.quick_skill_map.get(key)
            if ent:
                self._show_quick_skill_help_popup(ent)
        quick_skill_combo.bind("<<ComboboxSelected>>", _open_selected_skill_popup)
        ttk.Button(skill_pick_frame, text="打开", command=_open_selected_skill_popup, width=8).pack(side=tk.LEFT)
        if getattr(self, 'emotion_cycle_var', None):
            self.emotion_cycle_var.trace_add("write", _update_emotion_red_scroll_visibility)
        _update_emotion_red_scroll_visibility()
        self.emotion_light_2x_canvases = []
        for _ in range(2):
            c = tk.Canvas(emotion_lights_frame, width=40, height=40, highlightthickness=1, highlightbackground="gray")
            c.pack(side=tk.LEFT, padx=6)
            self.emotion_light_2x_canvases.append(c)
        if hasattr(self, '_update_emotion_lights'):
            self._update_emotion_lights()
        self.market_nav_container = ttk.Frame(crawler_frame)
        self.market_nav_container.pack(fill=tk.BOTH, expand=True, pady=(4, 3))
        # 延迟加载配置,避免阻塞界面显示
        if not self.market_nav_config or (isinstance(self.market_nav_config, dict) and len(self.market_nav_config) == 0):
            try:
                self.market_nav_config = self.load_market_nav_config()
            except Exception:
                self.market_nav_config = {}
        self._build_market_nav_section(self.market_nav_container)
        # 文本控制标签页(在快速爬取/文本控制标签页控件框中)
        control_frame = ttk.Frame(crawler_control_notebook, padding=5)
        crawler_control_notebook.add(control_frame, text="文本控制")
        # 字体大小控制
        font_frame = ttk.Frame(control_frame)
        font_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(font_frame, text="字体大小:").pack(side=tk.LEFT)
        ttk.Button(font_frame, text="A-", command=self.decrease_font_size).pack(side=tk.LEFT, padx=(5, 2))
        ttk.Button(font_frame, text="A+", command=self.increase_font_size).pack(side=tk.LEFT, padx=(2, 5))
        self.font_size_label = ttk.Label(font_frame, text="16")
        self.font_size_label.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(font_frame, text="弹窗字号:").pack(side=tk.LEFT, padx=(18, 2))
        try:
            _psb = ttk.Spinbox(
                font_frame,
                from_=self._popup_font_min,
                to=self._popup_font_max,
                width=4,
                textvariable=self.popup_font_size_var,
            )
            _psb.pack(side=tk.LEFT, padx=(0, 4))
        except Exception:
            ttk.Entry(font_frame, textvariable=self.popup_font_size_var, width=4).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(font_frame, text="应用到弹窗", command=self.commit_popup_font_size).pack(side=tk.LEFT, padx=(0, 6))
        # 查找功能
        search_frame = ttk.Frame(control_frame)
        search_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(search_frame, text="查找:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, width=20)
        self.search_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(search_frame, text="查找", command=self.search_text).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(search_frame, text="下一个", command=self.search_next).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(search_frame, text="上一个", command=self.search_prev).pack(side=tk.LEFT, padx=(0, 5))
        self.search_pos_label = ttk.Label(search_frame, text="")
        self.search_pos_label.pack(side=tk.LEFT, padx=(5, 0))
        # OCR功能已移除
        # 输入方式选择框架(移到文本控制标签页中)
        input_method_frame = ttk.LabelFrame(control_frame, text="文本导入方式", padding=10)
        input_method_frame.pack(fill=tk.X, pady=(0, 10))
        # 文本导入按钮
        ttk.Button(input_method_frame, text="上传Excel", command=self.load_excel).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(input_method_frame, text="粘贴网页", command=self.paste_webpage).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(input_method_frame, text="粘贴文本", command=self.paste_text).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(input_method_frame, text="读取文件", command=self.load_text_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(input_method_frame, text="合并上传", command=self.merge_upload).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(input_method_frame, text="清空内容", command=self.clear_content).pack(side=tk.LEFT, padx=(0, 5))
        # URL输入(移到文本控制标签页中)
        url_frame = ttk.Frame(control_frame)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(url_frame, text="URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)
        ttk.Button(url_frame, text="获取", command=self.get_from_url).pack(side=tk.LEFT, padx=(5, 0))
        # 资讯DB操作按钮框架(移到文本控制标签页中)
        news_db_frame = ttk.Frame(control_frame)
        news_db_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(news_db_frame, text="保存到资讯DB", command=self.save_current_tab_to_news_db).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(news_db_frame, text="查看资讯DB", command=self.show_news_db_display).pack(side=tk.LEFT, padx=(0, 0))
        # 输入标签(移到文本控制标签页中)
        input_label = ttk.Label(control_frame, text="富媒体输入框 - 支持多文件标签页:")
        input_label.pack(anchor=tk.W, pady=(0, 2))
        # 使用提示(移到文本控制标签页中)
        tip_label = ttk.Label(control_frame, text="💡 提示:直接按Ctrl+V粘贴剪贴板内容(文本/图片/网页)",
                             font=("TkDefaultFont", 11), foreground="gray")
        tip_label.pack(anchor=tk.W, pady=(0, 2))
        # 多标签页支持 - 使用ttk.Notebook(移到文本控制标签页中,让文本框整体上移)
        self.text_notebook = ttk.Notebook(control_frame)
        self.text_notebook.pack(fill=tk.BOTH, expand=True)
        # 存储所有标签页的文本框引用
        self.text_widgets = {}  # {tab_id: text_widget}
        self.tab_counter = 0
        # 创建词云标签页(专门用于显示词云)
        self.wordcloud_tab_id = self.create_text_tab("词云")
        self.wordcloud_tab_widget = self.text_widgets[self.wordcloud_tab_id]['widget']
        # 在词云标签页中添加初始说明
        self.wordcloud_tab_widget.insert("1.0", "词云历史记录\n")
        self.wordcloud_tab_widget.insert(tk.END, "="*50 + "\n")
        self.wordcloud_tab_widget.insert(tk.END, "此标签页将按时间顺序显示所有生成的词云图片\n")
        self.wordcloud_tab_widget.insert(tk.END, "最新的词云将显示在最下方\n")
        self.wordcloud_tab_widget.insert(tk.END, "="*50 + "\n\n")
        # 初始化词云图片列表(用于保存图片引用,防止被垃圾回收)
        self.wordcloud_images = []
        # 创建第一个默认标签页
        self.create_text_tab("未命名")
        # 注意:市场指数和热点导航标签页现在在_build_market_nav_section中创建
        # 不再在这里创建,因为它们已经移到快速爬取标签页的market_notebook中
        # 暴跌标签页(放在等待前)
        crash_tab = ttk.Frame(crawler_control_notebook, padding=10)
        crawler_control_notebook.add(crash_tab, text="暴跌")
        crash_top = ttk.Frame(crash_tab)
        crash_top.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(crash_top, text="刷新暴跌状态", command=self._refresh_crash_alert_display).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(crash_top, text="记录到资讯表", command=self._save_crash_alert_snapshot_to_news).pack(side=tk.LEFT)
        self.crash_alert_text_widget = scrolledtext.ScrolledText(crash_tab, height=12, wrap=tk.WORD)
        self.crash_alert_text_widget.pack(fill=tk.BOTH, expand=True)
        self.crash_alert_text_widget.config(state=tk.DISABLED)
        self._refresh_crash_alert_display()
        # 等待观察标签页
        waiting_tab = ttk.Frame(crawler_control_notebook, padding=10)
        crawler_control_notebook.add(waiting_tab, text="等待")
        waiting_sections = [
            ("趋势等回调", "trend_pullback"),
            ("震荡等低点", "range_low"),
            ("突破等回调", "breakout_pullback"),
            ("反转等放量", "reversal_volume"),
        ]
        self.waiting_reason_map = {}
        self.waiting_combo_widgets = []
        self.waiting_section_vars = {}
        self.waiting_source_widgets = []  # 存储数据源下拉框
        position_types = ["绩优股", "朋友", "强势股", "妖股", "均值回归"]
        data_sources = ["数据表", "自选表", "龙虎榜表"]
        for title, key in waiting_sections:
            section_frame = ttk.LabelFrame(waiting_tab, padding=10)
            section_frame.pack(fill=tk.X, pady=6)
            title_label = tk.Label(
                section_frame,
                text=title,
                font=("Microsoft YaHei", 16, "bold"),
                fg="#f7c646"
            )
            title_label.pack(anchor=tk.W, pady=(0, 6))
            self.waiting_reason_map[key] = title
            input_row = ttk.Frame(section_frame)
            input_row.pack(fill=tk.X, pady=2)
            ttk.Label(input_row, text="数据源:").pack(side=tk.LEFT)
            source_var = tk.StringVar(value=data_sources[0])
            source_combo = ttk.Combobox(input_row, textvariable=source_var, values=data_sources, state="readonly", width=10)
            source_combo.pack(side=tk.LEFT, padx=5)
            self.waiting_source_widgets.append(source_combo)
            ttk.Label(input_row, text="自选股:").pack(side=tk.LEFT, padx=(10, 0))
            stock_var = tk.StringVar()
            stock_combo = ttk.Combobox(input_row, textvariable=stock_var, state="readonly", width=25)
            stock_combo.pack(side=tk.LEFT, padx=5)
            self.waiting_combo_widgets.append(stock_combo)
            # 绑定数据源变化事件
            source_combo.bind("<<ComboboxSelected>>", lambda e, combo=stock_combo, src=source_var: self._update_waiting_stock_combo(combo, src.get()))
            ttk.Label(input_row, text="类型:").pack(side=tk.LEFT, padx=(10, 0))
            type_var = tk.StringVar(value=position_types[0])
            type_combo = ttk.Combobox(
                input_row, textvariable=type_var,
                values=position_types, state="readonly", width=10
            )
            type_combo.pack(side=tk.LEFT, padx=5)
            btn_row = ttk.Frame(section_frame)
            btn_row.pack(fill=tk.X, pady=6)
            ttk.Button(
                btn_row,
                text="开新仓",
                command=lambda k=key: self._open_waiting_new_position(k)
            ).pack(side=tk.LEFT)
            notes_entry = ttk.Entry(section_frame)
            notes_entry.pack(fill=tk.X, pady=(4, 0))
            self.waiting_section_vars[key] = {
                "stock_var": stock_var,
                "type_var": type_var,
                "stock_combo": stock_combo,
                "notes_entry": notes_entry,
            }
        self._update_waiting_combo_values()
        # 成长标签页(放在等待后)
        growth_tab = ttk.Frame(crawler_control_notebook, padding=10)
        crawler_control_notebook.add(growth_tab, text="成长")
        growth_top = ttk.Frame(growth_tab)
        growth_top.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(growth_top, text="指数范围:").pack(side=tk.LEFT)
        self.growth_index_options = ["科创", "上证", "中证", "创业板", "半导体", "人工智能"]
        self.growth_index_selections = ["中证", "科创"]
        self.growth_type_options = [
            "成长股", "周期股", "蓝筹",
            "问财-高股息", "问财-低估值", "问财-高景气",
            "Skill-情绪龙头", "Skill-趋势加强", "Skill-机构偏好",
        ]
        self.growth_type_selections = ["成长股"]
        self.growth_index_summary_var = tk.StringVar(value="中证、科创")
        self.growth_type_summary_var = tk.StringVar(value="成长股")
        ttk.Button(
            growth_top,
            text="选择指数",
            command=self._open_growth_index_selector
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(growth_top, textvariable=self.growth_index_summary_var).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(growth_top, text="股票类型:").pack(side=tk.LEFT)
        ttk.Button(
            growth_top,
            text="选择类型",
            command=self._open_growth_type_selector
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(growth_top, textvariable=self.growth_type_summary_var).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(growth_top, text="刷新候选", command=self._refresh_growth_candidates).pack(side=tk.LEFT, padx=(6, 10))
        ttk.Label(growth_top, text="候选:").pack(side=tk.LEFT)
        self.growth_stock_combo = ttk.Combobox(growth_top, state="readonly", width=26)
        self.growth_stock_combo.pack(side=tk.LEFT, padx=5)
        self.growth_text_widget = scrolledtext.ScrolledText(growth_tab, height=12, wrap=tk.WORD)
        self.growth_text_widget.pack(fill=tk.BOTH, expand=True)
        self.growth_text_widget.config(state=tk.DISABLED)
        self.growth_candidate_list = []
        # 启动不自动刷新成长股候选:问财链路无 Cookie 时查询必失败且曾导致首窗 179s 出不来;
        # 即便有 Cookie 同步查询也会卡主线程。需要时点击「刷新候选」按钮再查(已加挂起守卫,秒级返回)。
        # 配置文本颜色标签(6种颜色:红橙绿蓝紫黑)
        color_tags = [
            ("red", "red"), ("orange", "orange"), ("green", "green"),
            ("blue", "blue"), ("purple", "purple"), ("black", "black")
        ]
        # 为当前活动标签页配置颜色
        current_text = self.get_active_text_widget()
        if current_text is not None:
            try:
                for tag_name, color in color_tags:
                    current_text.tag_configure(tag_name, foreground=color)
            except (tk.TclError, AttributeError):
                # 如果widget还未完全创建或已被销毁,跳过配置
                pass
        # 创建图片显示区域
        self.image_display_frame = ttk.Frame(left_frame)
        self.image_display_frame.pack(fill=tk.X, pady=(5, 0))
        # 存储图片的字典
        self.images = {}
        self.image_counter = 0
        # 更新界面,显示左侧框架
        self._safe_update()
        # 右侧框架 - 分析结果和词云(网格第 1 列,占 40% 宽度)
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        # 保存右侧框架引用,供持仓股点击时使用
        self.right_frame = right_frame
        # 更新界面,显示右侧框架
        self._safe_update()
        # 创建右侧面板的PanedWindow,支持上下分割
        right_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)
        # 上半部分:情绪区间标签页(大盘结构与盘面指标)
        holding_analysis_frame = ttk.LabelFrame(right_paned, text="情绪区间", padding=5)
        right_paned.add(holding_analysis_frame, weight=1)
        # 内容区域(使用标签页展示结构化指标)
        self.holding_analysis_container = ttk.Frame(holding_analysis_frame)
        self.holding_analysis_container.pack(fill=tk.BOTH, expand=True)
        self._build_sentiment_zone_tabs(self.holding_analysis_container)
        # 下半部分:原有的分析结果和词云区域
        bottom_right_frame = ttk.Frame(right_paned)
        right_paned.add(bottom_right_frame, weight=2)
        # 顶部按钮框架 - 移到右边上方(先 pack 右侧「字体」区,避免窄屏时被挤到看不见)
        button_frame = ttk.Frame(bottom_right_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        # 右侧控制区域(字体大小等)- 先于左侧按钮 pack,保证始终可见
        right_control_area = ttk.Frame(button_frame)
        right_control_area.pack(side=tk.RIGHT, padx=(10, 0), anchor=tk.NE)
        # 字体调节:浅色底板 + 明确前景色,避免与系统主题撞色导致「看不见」
        _font_panel_bg = "#ebebeb"
        _font_panel_fg = "#101010"
        _font_panel_hi = "#6a6a6a"
        if sys.platform == "darwin":
            _font_panel_lbl = ("PingFang SC", 14)
            _font_panel_btn = ("PingFang SC", 15, "bold")
        else:
            _font_panel_lbl = ("Microsoft YaHei UI", 13)
            _font_panel_btn = ("Microsoft YaHei UI", 14, "bold")
        font_panel = tk.Frame(
            right_control_area,
            bg=_font_panel_bg,
            padx=6,
            pady=4,
            highlightbackground=_font_panel_hi,
            highlightthickness=1,
        )
        font_panel.pack(side=tk.TOP)
        font_row1 = tk.Frame(font_panel, bg=_font_panel_bg)
        font_row1.pack(side=tk.TOP, pady=(0, 3))
        tk.Label(font_row1, text="字体:", bg=_font_panel_bg, fg=_font_panel_fg, font=_font_panel_lbl).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        self.font_size_var = tk.StringVar(value="16")
        font_size_combo = ttk.Combobox(
            font_row1,
            textvariable=self.font_size_var,
            values=["10", "11", "12", "13", "14", "15", "16", "18", "20", "22", "24"],
            width=5,
            state="readonly",
        )
        font_size_combo.pack(side=tk.LEFT, padx=(0, 2))
        font_size_combo.bind("<<ComboboxSelected>>", self.change_font_size)
        font_row2 = tk.Frame(font_panel, bg=_font_panel_bg)
        font_row2.pack(side=tk.TOP)
        tk.Button(
            font_row2,
            text="A-",
            command=self.decrease_font_size,
            font=_font_panel_btn,
            width=3,
            bg="#dcdcdc",
            fg=_font_panel_fg,
            activebackground="#cfcfcf",
            activeforeground=_font_panel_fg,
            relief=tk.GROOVE,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(
            font_row2,
            text="A+",
            command=self.increase_font_size,
            font=_font_panel_btn,
            width=3,
            bg="#dcdcdc",
            fg=_font_panel_fg,
            activebackground="#cfcfcf",
            activeforeground=_font_panel_fg,
            relief=tk.GROOVE,
        ).pack(side=tk.LEFT)
        # 左侧按钮区域
        left_button_area = ttk.Frame(button_frame)
        left_button_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 第一行按钮(主要功能按钮)
        button_row1 = ttk.Frame(left_button_area)
        button_row1.pack(fill=tk.X, pady=(0, 5))
        # 分析按钮 - 同时生成分析结果和词云
        analyze_button = ttk.Button(button_row1, text="分析股票并生成词云", command=self.analyze_and_generate, width=18)
        analyze_button.pack(side=tk.LEFT, padx=(0, 5))
        # 参考一览按钮(替换原"市场行情")
        reference_button = ttk.Button(button_row1, text="📘 参考一览", command=self.show_reference_overview, width=12)
        reference_button.pack(side=tk.LEFT, padx=(0, 5))
        # 热点词云按钮(直接调用日/周/月词云)
        hotlist_button = ttk.Button(button_row1, text="🔥 热点词云", command=self.show_hotlists_overview, width=12)
        hotlist_button.pack(side=tk.LEFT, padx=(0, 5))
        # 导出按钮
        export_button = ttk.Button(button_row1, text="导出长图", command=self.export_analysis_and_wordcloud, width=10)
        export_button.pack(side=tk.LEFT, padx=(0, 5))
        # 打开数据表按钮
        open_db_button = ttk.Button(button_row1, text="打开数据表", command=self.show_db_display, width=12)
        open_db_button.pack(side=tk.LEFT, padx=(0, 5))
        # 新增Excel导出按钮
        excel_export_button = ttk.Button(button_row1, text="导出Excel", command=self.export_to_excel_ui, width=10)
        excel_export_button.pack(side=tk.LEFT, padx=(0, 5))
        # 第二行按钮(辅助功能按钮)
        button_row2 = ttk.Frame(left_button_area)
        button_row2.pack(fill=tk.X, pady=(0, 5))
        # 保存股票数据到数据库按钮
        save_stock_db_button = ttk.Button(button_row2, text="保存股票数据到数据库", command=self.save_stock_data_to_db, width=18)
        save_stock_db_button.pack(side=tk.LEFT, padx=(0, 5))
        # DB显示按钮
        db_display_button = ttk.Button(button_row2, text="DB显示", command=self.show_db_display, width=10)
        db_display_button.pack(side=tk.LEFT, padx=(0, 5))
        # AI配置和分析按钮
        ai_config_button = ttk.Button(button_row2, text="AI配置", command=self.show_ai_config, width=10)
        ai_config_button.pack(side=tk.LEFT, padx=(0, 5))
        ai_analyze_button = ttk.Button(button_row2, text="AI分析", command=self.run_ai_analysis, width=10)
        ai_analyze_button.pack(side=tk.LEFT, padx=(0, 5))
        # AI提问按钮(确保可见)
        ai_question_button = ttk.Button(button_row2, text="AI提问", command=self.show_ai_question, width=10)
        ai_question_button.pack(side=tk.LEFT, padx=(0, 5))
        # 结果标签和按钮框架
        result_header_frame = ttk.Frame(bottom_right_frame)
        result_header_frame.pack(fill=tk.X, pady=(0, 5))
        result_label = ttk.Label(result_header_frame, text="股票分析结果:")
        result_label.pack(side=tk.LEFT, anchor=tk.W)
        # 右侧结果区域的资讯DB操作按钮
        result_news_db_frame = ttk.Frame(result_header_frame)
        result_news_db_frame.pack(side=tk.RIGHT)
        ttk.Button(result_news_db_frame, text="保存到资讯DB", command=self.save_current_result_tab_to_news_db).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(result_news_db_frame, text="查看资讯DB", command=self.show_news_db_display).pack(side=tk.LEFT, padx=(0, 0))
        # 结果文本框改为多标签页(支持AI分析结果显示在新标签页)
        self.result_notebook = ttk.Notebook(bottom_right_frame)
        self.result_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # 创建默认结果标签页
        self.result_tabs = {}
        self.result_tab_counter = 0
        default_tab_id = self.create_result_tab("分析结果")
        self.result_text = self.result_tabs[default_tab_id]['widget']
        # 配置文本颜色标签(为默认结果文本框)
        self._configure_result_text_tags(self.result_text)
        # 初始化OCR相关变量
        self.screenshot_save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Screenshots")
        os.makedirs(self.screenshot_save_dir, exist_ok=True)
        # 初始化Chrome路径配置(从配置文件读取或使用自动检测)
        self.chrome_path_config = None
        self._load_chrome_config()
        # 创建OCR识别器标签页
        ocr_tab_id = self.create_result_tab("OCR识别器")
        self.ocr_tab_widget = self.result_tabs[ocr_tab_id]['widget']
        # 创建分析标签页(用于显示OCR识别结果)
        analysis_tab_id = self.create_result_tab("分析")
        self.analysis_tab_widget = self.result_tabs[analysis_tab_id]['widget']
        # 创建底部框架,包含词云和AI配置(水平布局)
        bottom_frame = ttk.Frame(bottom_right_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        # 词云显示区域(左侧)
        wordcloud_container = ttk.LabelFrame(bottom_frame, text="词云显示", padding=10)
        wordcloud_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        # 词云操作按钮框架
        wordcloud_button_frame = ttk.Frame(wordcloud_container)
        wordcloud_button_frame.pack(fill=tk.X, pady=(0, 5))
        def copy_wordcloud():
            """拷贝词云图片到剪贴板"""
            try:
                wordcloud_path = os.path.join(D_OUTPUT_DIR, "wordcloud.png")
                if not os.path.exists(wordcloud_path):
                    messagebox.showwarning("警告", "词云图片不存在,请先生成词云")
                    return
                # 尝试使用win32clipboard
                try:
                    from io import BytesIO

                    import win32clipboard
                    from PIL import Image
                    img = Image.open(wordcloud_path)
                    # 确保是RGB格式
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    output = BytesIO()
                    img.save(output, "BMP")
                    data = output.getvalue()[14:]  # 跳过BMP文件头
                    output.close()
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                    finally:
                        win32clipboard.CloseClipboard()
                    messagebox.showinfo("成功", "词云图片已复制到剪贴板")
                except ImportError:
                    messagebox.showerror("错误",
                        "需要安装pywin32库才能使用复制功能\n\n"
                        "请运行以下命令安装:\npip install pywin32\n\n"
                        "或者使用'保存'按钮将图片保存到文件")
                except Exception as e:
                    messagebox.showerror("错误", f"复制词云图片失败: {e}\n\n请尝试使用'保存'按钮将图片保存到文件")
            except Exception as e:
                messagebox.showerror("错误", f"复制词云图片失败: {e}\n\n请尝试使用'保存'按钮将图片保存到文件")
        def save_wordcloud():
            """保存词云图片到文件"""
            try:
                wordcloud_path = os.path.join(D_OUTPUT_DIR, "wordcloud.png")
                if not os.path.exists(wordcloud_path):
                    messagebox.showwarning("警告", "词云图片不存在,请先生成词云")
                    return
                # 获取保存路径
                filename = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")],
                    initialfile=f"wordcloud_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                if filename:
                    shutil.copy(wordcloud_path, filename)
                    messagebox.showinfo("成功", f"词云图片已保存到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存词云图片失败: {e}")
        ttk.Button(wordcloud_button_frame, text="拷贝", command=copy_wordcloud).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(wordcloud_button_frame, text="保存", command=save_wordcloud).pack(side=tk.LEFT, padx=(0, 5))
        self.wordcloud_label = ttk.Label(wordcloud_container, text="点击'分析股票并生成词云'按钮生成词云")
        self.wordcloud_label.pack(fill=tk.BOTH, expand=True)
        # 情绪指标(中间)
        indicator_container = ttk.LabelFrame(bottom_frame, text="情绪指标", padding=10)
        indicator_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 0))
        self.sentiment_value_label = ttk.Label(indicator_container, text="中性", font=("TkDefaultFont", 14, "bold"), foreground="orange")
        self.sentiment_value_label.pack(anchor=tk.CENTER, pady=(0, 6))
        self.sentiment_canvas = tk.Canvas(indicator_container, width=60, height=84, highlightthickness=0)
        self.sentiment_canvas.pack()
        self._sentiment_lights = {"red": (30, 14, 10), "yellow": (30, 42, 10), "green": (30, 70, 10)}
        try:
            self.update_sentiment_indicator("中性")
        except Exception:
            pass
        # AI配置区域(右侧)
        ai_config_container = ttk.LabelFrame(bottom_frame, text="AI大模型配置", padding=10)
        ai_config_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        # AI配置信息显示和AI分析按钮
        ai_info_frame = ttk.Frame(ai_config_container)
        ai_info_frame.pack(fill=tk.BOTH, expand=True)
        self.ai_config_info = scrolledtext.ScrolledText(ai_info_frame, height=6, width=40,
                                                       font=("TkDefaultFont", 12))
        self.ai_config_info.pack(fill=tk.BOTH, expand=True)
        # AI分析按钮(点击后对左边文本框文字进行AI分析)
        ai_analyze_btn = ttk.Button(ai_info_frame, text="AI分析", command=self.run_ai_analysis)
        ai_analyze_btn.pack(fill=tk.X, pady=(5, 0))
        # 显示当前AI配置
        self.update_ai_config_display()
        # 绑定标签页切换事件
        self.text_notebook.bind('<<NotebookTabChanged>>', lambda e: self.update_text_input_reference())
        # 创建右键菜单
        self.create_context_menu()
        # 初始化变量
        self.font_size = 16
        self.search_positions = []
        self.current_search_index = -1
        self.last_analysis_result = ""
        self.export_dir = D_EXPORT_DIR
        self.highlight_timer = None # 用于延迟高亮
        self.text_input = None  # 保持向后兼容,指向当前活动标签页
        self.wordcloud_stocks_data = []  # 保存词云中的股票数据(股票名称、逻辑、时间、来源)
        # 更新text_input指向当前活动标签页
        self.update_text_input_reference()
        # 同花顺情绪指数:启动后约 5 秒先弹一次,之后每半小时再提醒
        try:
            self.root.after(15000, self._th_reminder_tick)  # 延后 15s
        except Exception:
            pass

def main():
    try:
        # conda 下用绝对路径启动 python 时,未 activate 则 PATH 不含 env 的 bin,同目录的 node 无法被 pywencai 找到
        try:
            _bd = os.path.dirname(os.path.abspath(sys.executable))
            _node = os.path.join(_bd, "node")
            if os.path.isfile(_node) and os.access(_node, os.X_OK):
                os.environ["PATH"] = _bd + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
        # macOS 特定设置
        if sys.platform == "darwin":
            os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
        # 检查是否有图形显示环境
        display_env = os.environ.get('DISPLAY', '')
        if sys.platform == "darwin":
            # macOS 使用不同的显示系统
            pass
        elif not display_env:
            print("错误: 未检测到图形显示环境 (DISPLAY 环境变量为空)")
            print("请在图形界面环境中运行此程序,或设置正确的 DISPLAY 环境变量")
            print("在 macOS 上,请确保使用支持图形界面的终端或使用 pythonw 运行")
            return
        # 创建主窗口
        root = tk.Tk()
        # 🔧 Tk 回调异常钩子（把 silent crash 打到文件）
        import traceback as _tb_global
        def _tk_err_hook(exc_type, exc_val, exc_tb):
            try:
                _log = os.path.expanduser("~/Desktop/tk_traceback.log")
                with open(_log, "a") as _f:
                    _f.write("\n" + "="*60 + "\n")
                    _tb_global.print_exception(exc_type, exc_val, exc_tb, file=_f)
            except Exception:
                pass
        root.report_callback_exception = _tk_err_hook
        # 立即显示窗口框架,让用户看到程序正在启动
        root.title(APP_CONFIG.get("window_title", DEFAULT_APP_CONFIG["window_title"]))
        root.geometry("1580x940")
        try:
            root.minsize(1280, 820)
        except Exception:
            pass
        # 无本地缓存时会联网拉取全市场股票名(可能 10s+),延后到 GUI 创建后再启动
        def _preload_stock_names():
            try:
                load_stock_names()
            except Exception as e:
                print(f"后台预加载股票名称列表失败: {e}")
        root.after(3000, lambda: threading.Thread(target=_preload_stock_names, daemon=True).start())
        # 创建应用实例(在创建过程中会逐步显示界面)
        try:
            app = StockKeywordAnalyzerGUI(root)
        except Exception as e:
            import traceback
            error_msg = f"初始化应用失败: {e!s}\n{traceback.format_exc()}"
            print(error_msg)
            try:
                from tkinter import messagebox
                messagebox.showerror("初始化错误", error_msg, parent=root)
            except:
                pass
            try:
                if root.winfo_exists():
                    root.destroy()
            except:
                pass
            return
        # 再次确保窗口可见并置于最前
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
        except Exception as e:
            print(f"Warning: Failed to show window: {e}")
        # 检查是否有打开数据表的标记文件
        marker_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".open_ths_data_table")
        if os.path.exists(marker_file):
            try:
                # 删除标记文件
                os.remove(marker_file)
                # 延迟打开数据表窗口,确保主窗口已完全初始化
                root.after(500, lambda: app.show_unified_db_display(default_tab="ths"))
            except Exception as e:
                print(f"自动打开数据表窗口失败: {e}")
        print(f"🚀 about to enter mainloop at {__import__('time').time()}", flush=True)
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"程序启动失败: {e!s}\n{traceback.format_exc()}"
        print(error_msg)
        try:
            from tkinter import messagebox
            messagebox.showerror("启动错误", error_msg)
        except:
            print("无法显示错误对话框,错误信息已打印到控制台")
            input("按回车键退出...")
if __name__ == "__main__":
    main()
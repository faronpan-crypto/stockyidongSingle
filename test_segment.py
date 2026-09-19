import os
import sys


def _early_sqlite_temp_dir():
    """在 import sqlite3 之前设置临时目录；否则 Windows 上仍可能用 C:\\Users\\...\\Temp，C 盘满即报 database or disk is full。"""
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
        # 部分 Windows/Python-sqlite 仍走 %TEMP%，与本进程统一指向数据盘
        if sys.platform == "win32":
            os.environ["TEMP"] = os.environ["SQLITE_TMPDIR"]
            os.environ["TMP"] = os.environ["SQLITE_TMPDIR"]
    except Exception:
        pass


_early_sqlite_temp_dir()

import re

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
import contextlib
import io
import json
import sqlite3
import threading
import warnings
from collections import Counter
from datetime import datetime

import matplotlib


# ==================== 错误抑制工具 ====================
@contextlib.contextmanager
def suppress_stderr():
    """临时抑制stderr输出的上下文管理器"""
    old_stderr = sys.stderr
    try:
        # 创建一个空的StringIO对象来捕获所有stderr输出
        sys.stderr = io.StringIO()
        yield
    except Exception:
        # 即使发生异常也要恢复stderr
        pass
    finally:
        sys.stderr = old_stderr

@contextlib.contextmanager
def suppress_all_output():
    """临时抑制stdout和stderr输出的上下文管理器"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        # 同时抑制stdout和stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        yield
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

# 创建一个静默的输出流类，用于完全抑制输出
class SilentIO(io.StringIO):
    """静默的IO类，完全抑制所有输出"""
    def write(self, *args, **kwargs):
        # 完全忽略所有写入操作
        pass
    
    def flush(self, *args, **kwargs):
        # 忽略刷新操作
        pass
    
    def getvalue(self):
        # 返回空字符串
        return ""

@contextlib.contextmanager
def suppress_tkinterweb_errors():
    """专门用于抑制TkinterWeb错误的上下文管理器"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        # 使用静默IO完全抑制输出
        sys.stdout = SilentIO()
        sys.stderr = SilentIO()
        yield
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

# 全局错误抑制装饰器，用于包装可能产生错误的函数
def suppress_all_errors(func):
    """装饰器：抑制函数执行过程中的所有stderr输出"""
    def wrapper(*args, **kwargs):
        with suppress_stderr():
            try:
                return func(*args, **kwargs)
            except Exception:
                return None
    return wrapper

try:
    import tushare as ts
    TS_AVAILABLE = True
except ImportError:
    ts = None
    TS_AVAILABLE = False

# ==================== 路径配置 ====================
# 数据根目录（与 _early_sqlite_temp_dir 一致；可用环境变量 STOCK_ANALYZER_DATA_DIR 覆盖）
D_DATA_DIR = (os.environ.get("STOCK_ANALYZER_DATA_DIR") or r"D:\StockAnalyzer").strip() or r"D:\StockAnalyzer"
D_DB_DIR = os.path.join(D_DATA_DIR, "Database")
D_OUTPUT_DIR = os.path.join(D_DATA_DIR, "Output")
D_EXPORT_DIR = os.path.join(D_DATA_DIR, "Export")
D_IMAGES_DIR = os.path.join(D_DATA_DIR, "ConsultationImages")  # 咨询图片目录
# SQLite 内部临时文件（排序、索引等）默认用系统 Temp；C 盘满时易误报 database or disk is full
D_SQLITE_TMP = os.path.join(D_DATA_DIR, "temp")
MANAGED_STOCKS_FILE = os.path.join(D_DATA_DIR, "managed_stocks.json")

# 确保目录存在
for dir_path in [D_DATA_DIR, D_DB_DIR, D_OUTPUT_DIR, D_EXPORT_DIR, D_IMAGES_DIR, D_SQLITE_TMP]:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception as e:
        print(f"创建目录失败 {dir_path}: {e}")

# 本项目 JSON 配置目录（相对 stockyidong.py，不再依赖仓库根目录 cwd）
_APP_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_CONFIG_DIR = os.path.join(_APP_SRC_DIR, "config")
try:
    os.makedirs(_APP_CONFIG_DIR, exist_ok=True)
except OSError:
    pass

# 数据库路径（含咨询表 news_info）。优先级：
# 1) 环境变量 STOCK_ANALYSIS_DB 或 STOCK_ANALYSIS_DB_PATH（任意路径的旧库，无需拷贝）
# 2) 项目文件夹 stockyidong_project/data/stock_analysis.db 若已存在（把旧 db 拷到此即可，无需改代码）
# 3) 默认 D:\StockAnalyzer\Database\stock_analysis.db
_STOCKYIDONG_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_PROJECT_LOCAL_DB = os.path.join(_STOCKYIDONG_PROJECT_ROOT, "data", "stock_analysis.db")
_db_override = (
    (os.environ.get("STOCK_ANALYSIS_DB") or os.environ.get("STOCK_ANALYSIS_DB_PATH") or "").strip().strip('"')
)
if _db_override:
    DB_PATH = os.path.normpath(os.path.expanduser(_db_override))
elif os.path.isfile(_PROJECT_LOCAL_DB):
    DB_PATH = os.path.normpath(_PROJECT_LOCAL_DB)
else:
    DB_PATH = os.path.join(D_DB_DIR, "stock_analysis.db")


def find_script_path_in_monorepo(script_name, tried_paths):
    """在 monorepo 中查找脚本：自本文件目录逐级向上，在含 *_project 子目录的层级搜索根目录与各 *_project/src。"""
    alternate_names = []
    if script_name == "jiuyan_gongshe_crawler.py":
        alternate_names.append("jiuyangongshe_crawler.py")
    names_to_try = [script_name] + [n for n in alternate_names if n != script_name]

    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        try:
            sub = os.listdir(d)
        except OSError:
            sub = []
        has_bundle_projects = any(
            name.endswith("_project") and os.path.isdir(os.path.join(d, name))
            for name in sub
        )
        if has_bundle_projects:
            for sn in names_to_try:
                root_candidate = os.path.join(d, sn)
                tried_paths.append(root_candidate)
                if os.path.isfile(root_candidate):
                    return root_candidate
                for entry in sorted(sub):
                    if not entry.endswith("_project"):
                        continue
                    p = os.path.join(d, entry, "src", sn)
                    tried_paths.append(p)
                    if os.path.isfile(p):
                        return p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _load_tushare_token_from_local_file():
    """从本地文件读取 Tushare token（不写死在源码里）。
    查找顺序：环境变量 TUSHARE_TOKEN_FILE 指向的文件 -> 数据目录 tushare_local.json -> 项目 config/tushare_local.json
    内容可为 JSON（{"token":"..."}）或单行纯文本。"""
    candidates = []
    env_path = (os.environ.get("TUSHARE_TOKEN_FILE") or "").strip()
    if env_path:
        candidates.append(os.path.normpath(os.path.expanduser(env_path)))
    candidates.append(os.path.join(D_DATA_DIR, "tushare_local.json"))
    candidates.append(os.path.join(_APP_CONFIG_DIR, "tushare_local.json"))
    for path in candidates:
        if not path or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if not raw:
                continue
            if raw.startswith("{"):
                data = json.loads(raw)
                tok = (data.get("token") or data.get("TUSHARE_TOKEN") or "").strip()
                if tok:
                    return tok
            else:
                line = raw.splitlines()[0].strip()
                if line and not line.startswith("#"):
                    return line
        except Exception:
            continue
    return ""


def _akshare_fund_flow_market(code6: str) -> str:
    """ak.stock_individual_fund_flow(stock, market) 的 market：sh / sz / bj"""
    c = (code6 or "").strip()
    if len(c) >= 6:
        c = c[:6]
    if not c.isdigit():
        return "sh"
    if c.startswith(("5", "6", "9")):
        return "sh"
    if c.startswith(("4", "8")):
        return "bj"
    return "sz"


TS_DEFAULT_ACCOUNT = "18939863051"
# 优先级：环境变量 TUSHARE_TOKEN > 本地 tushare_local.json（见上）；程序内「登录」保存的 token 在 ai_config.json，由 self.ts_token 优先使用
TS_DEFAULT_TOKEN = (os.environ.get("TUSHARE_TOKEN") or "").strip() or _load_tushare_token_from_local_file()
MARKET_NAV_CONFIG_FILE = os.path.join(_APP_CONFIG_DIR, "market_nav_config.json")
# 打包后使用固定路径，与“原程序”一致：优先 D:\StockAnalyzer，其次 exe 同目录
def _resolve_market_nav_config_path():
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        path_in_data = os.path.join(D_DATA_DIR, "market_nav_config.json")
        path_exe = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "market_nav_config.json")
        if os.path.exists(path_in_data):
            return path_in_data
        return path_exe
    return MARKET_NAV_CONFIG_FILE

CRAWLER_CONFIG_FILE = os.path.join(_APP_CONFIG_DIR, "crawler_config.json")

def _resolve_crawler_config_path():
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        path_in_data = os.path.join(D_DATA_DIR, "crawler_config.json")
        path_exe = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "crawler_config.json")
        if os.path.exists(path_in_data):
            return path_in_data
        return path_exe
    return CRAWLER_CONFIG_FILE
EXCEL_FILES_CONFIG_FILE = os.path.join(D_DATA_DIR, "excel_files_config.json")
DEFAULT_MARKET_NAV_CONFIG = {
    "indices": [
        {"name": "财联社情绪指数", "desc": "实时跟踪A股情绪温度", "url": "https://www.cls.cn/subject/1079"},
        {"name": "富时中国A50期指", "desc": "离岸A股方向，美股时段参考", "url": "https://finance.sina.com.cn/money/future/qhscfx/ftse50.shtml"},
        {"name": "美股主要股指", "desc": "全球风险偏好风向", "url": "https://finance.sina.com.cn/stock/usstock/sector.shtml"},
        {"name": "流动性指标(Shibor)", "desc": "短端利率，观察资金松紧", "url": "https://data.eastmoney.com/shibor/shibor_list.html"},
        {"name": "CPI/PPI数据", "desc": "通胀水平，影响政策节奏", "url": "https://data.eastmoney.com/cjsj/cpi.html"},
        {"name": "国债收益率曲线", "desc": "无风险利率，衡量估值压力", "url": "https://data.eastmoney.com/cjsj/zgyz_list.html"},
        {"name": "中国证监会官网", "desc": "政策发布、非法荐股警示、合法机构查询入口", "url": "http://www.csrc.gov.cn"},
        {"name": "巨潮资讯网", "desc": "证监会指定信息披露平台，上市公司公告/年报权威来源", "url": "http://www.cninfo.com.cn"},
        {"name": "中证指数有限公司", "desc": "指数编制机构，查询沪深300等成分股及估值", "url": "http://www.csindex.com.cn"}
    ],
    "portals": [
        {"name": "Tushare Pro", "desc": "数据接口开放平台，量化回测必备", "url": "https://tushare.pro/"},
        {"name": "JoinQuant 聚宽", "desc": "策略研究与实盘撮合", "url": "https://www.joinquant.com/"},
        {"name": "米筐 RiceQuant", "desc": "量化策略社区+云回测", "url": "https://www.ricequant.com/"},
        {"name": "BigQuant", "desc": "机器学习因子研究平台", "url": "https://bigquant.com/"},
        {"name": "东方财富网", "desc": "行情数据+社区+基金销售，主力持仓查询工具", "url": "https://www.eastmoney.com/"},
        {"name": "同花顺财经", "desc": "实时行情、智能选股、两融数据跟踪", "url": "https://www.10jqka.com.cn/"},
        {"name": "新浪财经", "desc": "全球市场覆盖，外汇/期货实时行情", "url": "https://finance.sina.com.cn/"},
        {"name": "雪球", "desc": "投资者社交平台，大V实盘分享", "url": "https://xueqiu.com/"},
        {"name": "选股宝", "desc": "热点题材挖掘，龙虎榜追踪", "url": "https://xuangubao.cn/"},
        {"name": "萝卜投研", "desc": "免费研报平台，行业数据可视化", "url": "https://robo.datayes.com/"},
        {"name": "财联社", "desc": "24小时电报快讯，政策/突发事件预警", "url": "https://www.cls.cn/"},
        {"name": "TradingView", "desc": "国际级K线分析工具，多市场技术指标", "url": "https://www.tradingview.com/"},
        {"name": "Wind资讯", "desc": "机构级资讯与数据终端", "url": "https://www.wind.com.cn/"},
        {"name": "中金在线", "desc": "综合财经门户，期货外汇全覆盖", "url": "https://www.cnfol.com/"}
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
        {"name": "MACD俱乐部", "desc": "技术指标讨论，公式编写教学", "url": "http://bbs.macd.cn/"},
        {"name": "360导航-财经网址", "desc": "聚合东方财富/和讯等头部入口", "url": "https://hao.360.com/sub/caijing_website_nav.html"},
        {"name": "123网址之家-财经导航", "desc": "覆盖期货/外汇/股票社区链接", "url": "https://www.1234wu.com/wz/90_1.html"}
    ],
    "dv_accounts": [
        {"name": "饭统戴老板", "desc": "长篇深度商业故事，洞察公司与经济史", "url": "https://weixin.sogou.com/weixin?type=1&query=%E9%A5%AD%E7%BB%9F%E6%88%B4%E8%80%81%E6%9D%BF"},
        {"name": "三折人生", "desc": "金融科普漫画，财经小白入门", "url": "https://weixin.sogou.com/weixin?type=1&query=%E4%B8%89%E6%8A%98%E4%BA%BA%E7%94%9F"},
        {"name": "券商中国", "desc": "证券时报旗下官媒，热点政策速递", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%88%B8%E5%95%86%E4%B8%AD%E5%9B%BD"},
        {"name": "咩咩说", "desc": "券商研究视角，宏观与行业思考", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%92%A9%E5%92%A9%E8%AF%B4"},
        {"name": "月风投资笔记", "desc": "私募经理吴悦风，宏观与个股解析", "url": "https://weixin.sogou.com/weixin?type=1&query=%E6%9C%88%E9%A3%8E%E6%8A%95%E8%B5%84%E7%AC%94%E8%AE%B0"},
        {"name": "英为财情", "desc": "全球行情+工具，美股/大宗商品深度", "url": "http://weixin.qq.com/r/nzhpcYvEHtZhrc8S922N"},
        {"name": "李迅雷金融与投资", "desc": "中泰证券首席，宏观策略观点", "url": "https://weixin.sogou.com/weixin?type=1&query=%E6%9D%8E%E8%BF%85%E9%9B%B7"},
        {"name": "定投十年赚十倍", "desc": "银行螺丝钉基金定投与估值表", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%AE%9A%E6%8A%95%E5%8D%81%E5%B9%B4%E8%B5%9A%E5%8D%81%E5%80%8D"},
        {"name": "图解金融", "desc": "图文并茂讲解金融知识", "url": "https://weixin.sogou.com/weixin?type=1&query=%E5%9B%BE%E8%A7%A3%E9%87%91%E8%9E%8D"},
        {"name": "金融街老裘", "desc": "财务研究与行业分析，偏个股基本面", "url": "https://weixin.sogou.com/weixin?type=1&query=%E9%87%91%E8%9E%8D%E8%A1%97%E8%80%81%E8%A3%98"}
    ],
    "ai_search_questions": []
}

# 全局设置matplotlib中文字体，避免字体警告
try:
    # 使用Windows系统常见的中文字体，避免使用不存在的字体
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
    print("警告: openpyxl未安装，Excel导出功能可能不可用")
    openpyxl = None

# OCR功能已完全移除

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    print("❌ 警告: python-docx未安装，Word文档读取功能不可用")
    DOCX_AVAILABLE = False

# 全局变量
STOCK_NAMES_SET = None
STOCK_CODES_DICT = None
STOCK_NAME_TO_CODE = None
ETF_CACHE_REFRESHED = False
# 并发调用 load_stock_names() 时串行化，避免重复联网与全局字典竞态
STOCK_NAMES_LOAD_LOCK = threading.Lock()

# ==================== 数据库管理 ====================
def init_database():
    """初始化股票数据库"""
    db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建股票数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL,
            change_pct REAL,
            volume REAL,
            turnover REAL,
            market_cap REAL,
            pe_ratio REAL,
            sector TEXT,
            theme TEXT,
            analysis_result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, date)
        )
    ''')
    
    # 创建爬取文章表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawled_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            content TEXT,
            url TEXT,
            publish_time TEXT,
            views INTEGER,
            likes INTEGER,
            replies INTEGER,
            crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建股票逻辑表（用于保存股票名、逻辑、日期、来源）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_logic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_name TEXT NOT NULL,
            logic TEXT,
            date TEXT NOT NULL,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建资讯表（用于保存标签页名、内容、时间）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tab_name TEXT NOT NULL,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建评注表（用于保存资讯的评注）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_id INTEGER NOT NULL,
            comment_text TEXT NOT NULL,
            author TEXT,
            color TEXT,
            font_family TEXT,
            font_size INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (news_id) REFERENCES news_info(id) ON DELETE CASCADE
        )
    ''')
    
    # 创建凯利公式记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kelly_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_name TEXT NOT NULL,
            calc_time TEXT NOT NULL,
            odds REAL NOT NULL,
            win_prob REAL NOT NULL,
            kelly_ratio REAL NOT NULL,
            suggestion TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建交易体系配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trading_system_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            stock_type TEXT,
            sector TEXT,
            strategy TEXT,
            market_status TEXT,
            peripheral_sentiment REAL,
            position REAL,
            stop_loss REAL,
            take_profit REAL,
            target_price REAL,
            config_advice TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建龙虎榜记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lhb_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            ts_code TEXT NOT NULL,
            name TEXT,
            close REAL,
            pct_change REAL,
            turnover_rate REAL,
            amount REAL,
            l_sell REAL,
            l_buy REAL,
            l_amount REAL,
            net_amount REAL,
            net_rate REAL,
            amount_rate REAL,
            float_values REAL,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trade_date, ts_code, reason)
        )
    ''')
    
    # 创建同花顺实时数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ths_realtime_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            current_price REAL,
            change_pct REAL,
            circulation_market_value REAL,
            volume_ratio REAL,
            four_min_change_rate REAL,
            main_net_amount REAL,
            net_amount_ratio REAL,
            turnover_rate REAL,
            pe_ratio REAL,
            amplitude REAL,
            good_news TEXT,
            limit_up_count INTEGER,
            save_date TEXT NOT NULL,
            save_time TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引以提高查询效率
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ths_stock_code ON ths_realtime_data(stock_code)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ths_save_date ON ths_realtime_data(save_date)
    ''')

    # 系统研判缓存：选股池/情绪快照/实时新闻等汇总全文，供 3 小时内复用
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS judgment_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            raw_context TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_judgment_cache_created ON judgment_cache(created_at)
    ''')
    
    conn.commit()
    conn.close()
    return db_path

# 研判表缓存有效期（秒），默认 3 小时
JUDGMENT_CACHE_TTL_SECONDS = 3 * 3600


def _ensure_judgment_cache_table():
    """确保 judgment_cache 表存在（升级后未重启程序时也可写入）。"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS judgment_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw_context TEXT NOT NULL
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_judgment_cache_created ON judgment_cache(created_at)"
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"确保研判表存在失败: {e}")


def save_judgment_cache_snapshot(raw_context: str):
    """将系统研判原始汇总写入 judgment_cache（研判表）。"""
    if not raw_context or not str(raw_context).strip():
        return
    _ensure_judgment_cache_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO judgment_cache (created_at, raw_context) VALUES (?, ?)",
            (ts, raw_context),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"保存研判表失败: {e}")


def load_fresh_judgment_cache(max_age_seconds=None):
    """读取研判表最新一条；若在有效期内则返回 (raw_context, created_at)，否则 (None, None)。"""
    if max_age_seconds is None:
        max_age_seconds = JUDGMENT_CACHE_TTL_SECONDS
    _ensure_judgment_cache_table()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT created_at, raw_context FROM judgment_cache ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None, None
        created_at, raw = row[0], row[1]
        dt = datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - dt).total_seconds() > float(max_age_seconds):
            return None, None
        return raw, created_at
    except Exception as e:
        print(f"读取研判表失败: {e}")
        return None, None


def has_lhb_records(trade_date):
    """检查指定日期的龙虎榜数据是否已保存"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(1) FROM lhb_records WHERE trade_date = ?", (trade_date,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"检查龙虎榜数据失败: {e}")
        return False

def save_lhb_records(records):
    """批量保存龙虎榜数据"""
    if not records:
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        insert_sql = '''
            INSERT OR IGNORE INTO lhb_records (
                trade_date, ts_code, name, close, pct_change, turnover_rate,
                amount, l_sell, l_buy, l_amount, net_amount, net_rate,
                amount_rate, float_values, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        prepared = []
        for row in records:
            prepared.append((
                row.get('trade_date'),
                row.get('ts_code'),
                row.get('name'),
                row.get('close'),
                row.get('pct_change'),
                row.get('turnover_rate'),
                row.get('amount'),
                row.get('l_sell'),
                row.get('l_buy'),
                row.get('l_amount'),
                row.get('net_amount'),
                row.get('net_rate'),
                row.get('amount_rate'),
                row.get('float_values'),
                row.get('reason')
            ))
        
        cursor.executemany(insert_sql, prepared)
        inserted = cursor.rowcount
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        print(f"保存龙虎榜记录失败: {e}")
        return 0

def save_stock_to_db(stock_code, stock_name, date, price=None, change_pct=None, 
                     volume=None, turnover=None, market_cap=None, pe_ratio=None,
                     sector=None, theme=None, analysis_result=None):
    """保存股票数据到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO stock_data 
            (stock_code, stock_name, date, price, change_pct, volume, turnover, 
             market_cap, pe_ratio, sector, theme, analysis_result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (stock_code, stock_name, date, price, change_pct, volume, turnover,
              market_cap, pe_ratio, sector, theme, analysis_result))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存股票数据到数据库失败: {e}")
        return False

def save_article_to_db(source, title, author=None, content=None, url=None,
                       publish_time=None, views=0, likes=0, replies=0):
    """保存爬取的文章到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO crawled_articles 
            (source, title, author, content, url, publish_time, views, likes, replies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (source, title, author, content, url, publish_time, views, likes, replies))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存文章到数据库失败: {e}")
        return False

def save_news_info_to_db(tab_name, content):
    """保存资讯到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO news_info (tab_name, content, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (tab_name, content, current_time, current_time))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存资讯到数据库失败: {e}")
        return False


def get_news_stocks_by_date_and_frequency(ndays=8, meta=None):
    """从 news_info 按日期分组，每日期合并 content 提取股票并按出现频次降序，返回最近 ndays 天的数据。
    返回: [{"date_ymd": "YYYY-MM-DD", "date_mmdd": "MMDD", "stocks": [(name, code), ...]}, ...]，最多 ndays 项。

    若 meta 传入 dict，会写入诊断字段（reason、error、news_row_count 等），便于界面提示。"""
    global STOCK_CODES_DICT
    if meta is not None:
        meta.clear()
        meta["ndays"] = ndays
    try:
        load_stock_names()
    except Exception:
        pass
    if STOCK_CODES_DICT is None:
        if meta is not None:
            meta["reason"] = "no_stock_dict"
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"从资讯表读取失败: {e}")
        print(f"  数据库: {DB_PATH}")
        print(
            "  若含 disk full：请保证 D: 上数据目录有足够空间；本程序启动时已尽量将 SQLITE_TMPDIR/TEMP 指到 <数据目录>\\temp。"
            " 若仍报错请彻底退出后重开，或手动设置 SQLITE_TMPDIR 后再启动。"
        )
        if meta is not None:
            meta["reason"] = "db_error"
            meta["error"] = str(e)
        return []
    if meta is not None:
        meta["news_row_count"] = len(rows)
    if not rows:
        if meta is not None:
            meta["reason"] = "no_rows"
        return []
    # 按日期分组 (created_at 格式 "YYYY-MM-DD HH:MM:SS")
    by_date = {}
    for row in rows:
        rid, tab_name, content, created_at = row
        if not created_at:
            continue
        date_ymd = created_at[:10] if len(created_at) >= 10 else created_at
        if date_ymd not in by_date:
            by_date[date_ymd] = []
        if content:
            by_date[date_ymd].append(content)
    # 取最近 ndays 个日期（按日期降序）
    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    if not sorted_dates:
        if meta is not None:
            meta["reason"] = "no_valid_dates"
            meta["hint"] = "news_info 有记录但 created_at 为空或格式异常，无法按日归类。"
        return []
    result = []
    total_parsed_codes = 0
    for date_ymd in sorted_dates:
        merged = " ".join(by_date[date_ymd])
        codes = re.findall(r'\d{6}', merged)
        valid = [c for c in codes if c in STOCK_CODES_DICT]
        counter = Counter(valid)
        most_common = counter.most_common(80)
        stocks = [(STOCK_CODES_DICT[code], code) for code, _ in most_common]
        total_parsed_codes += len(stocks)
        date_mmdd = date_ymd[5:7] + date_ymd[8:10]  # MMDD
        result.append({"date_ymd": date_ymd, "date_mmdd": date_mmdd, "stocks": stocks})
    if meta is not None:
        meta["days_with_news"] = len(result)
        meta["total_stock_slots"] = total_parsed_codes
        if total_parsed_codes == 0:
            meta["reason"] = "no_codes_in_news"
            meta["hint"] = (
                "资讯正文里没有出现可识别的 A 股六位代码（或代码不在本地股票字典中）。"
                "请先确认已加载股票列表，且资讯内容含 600519 这类代码。"
            )
    return result


def get_news_stocks_merged_recent_days(ndays=5, meta=None):
    """从 news_info 取最近 ndays 个「有资讯的日期」，合并这些日期的全部正文，按六位代码出现频次降序，返回 [(name, code), ...] 最多 80 条。"""
    global STOCK_CODES_DICT
    if meta is not None:
        meta.clear()
        meta["ndays"] = ndays
    try:
        load_stock_names()
    except Exception:
        pass
    if STOCK_CODES_DICT is None:
        if meta is not None:
            meta["reason"] = "no_stock_dict"
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, tab_name, content, created_at FROM news_info ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"从资讯表读取失败: {e}")
        if meta is not None:
            meta["reason"] = "db_error"
            meta["error"] = str(e)
        return []
    if meta is not None:
        meta["news_row_count"] = len(rows)
    if not rows:
        if meta is not None:
            meta["reason"] = "no_rows"
        return []
    by_date = {}
    for row in rows:
        rid, tab_name, content, created_at = row
        if not created_at:
            continue
        date_ymd = created_at[:10] if len(created_at) >= 10 else created_at
        if date_ymd not in by_date:
            by_date[date_ymd] = []
        if content:
            by_date[date_ymd].append(content)
    sorted_dates = sorted(by_date.keys(), reverse=True)[:ndays]
    if not sorted_dates:
        if meta is not None:
            meta["reason"] = "no_valid_dates"
            meta["hint"] = "news_info 有记录但 created_at 为空或格式异常，无法按日归类。"
        return []
    merged = " ".join(piece for d in sorted_dates for piece in by_date[d])
    codes = re.findall(r"\d{6}", merged)
    valid = [c for c in codes if c in STOCK_CODES_DICT]
    counter = Counter(valid)
    most_common = counter.most_common(80)
    stocks = [(STOCK_CODES_DICT[code], code) for code, _ in most_common]
    if meta is not None:
        meta["days_merged"] = len(sorted_dates)
        meta["merged_dates_ymd"] = sorted_dates
        meta["total_stock_slots"] = len(stocks)
        if not stocks:
            meta["reason"] = "no_codes_in_news"
            meta["hint"] = (
                "资讯正文里没有出现可识别的 A 股六位代码（或代码不在本地股票字典中）。"
                "请先确认已加载股票列表，且资讯内容含 600519 这类代码。"
            )
    return stocks


def save_kelly_record_to_db(stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes):
    """保存凯利公式计算结果到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO kelly_records
            (stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (stock_name, calc_time, odds, win_prob, kelly_ratio, suggestion, notes))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存凯利公式记录失败: {e}")
        return False

def save_stock_logic_to_db(stock_name, logic, date, source=None):
    """保存股票逻辑到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO stock_logic 
            (stock_name, logic, date, source)
            VALUES (?, ?, ?, ?)
        ''', (stock_name, logic, date, source))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存股票逻辑到数据库失败: {e}")
        return False

def get_stock_logic_from_db(start_date=None, end_date=None, stock_name=None, logic_content=None):
    """从数据库获取股票逻辑"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = "SELECT * FROM stock_logic WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        if stock_name:
            query += " AND stock_name = ?"
            params.append(stock_name)
        
        if logic_content:
            query += " AND logic LIKE ?"
            params.append(f'%{logic_content}%')
        
    except Exception:
        pass

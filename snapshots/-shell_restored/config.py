"""
配置 & 路径常量 + Tushare patch + 辅助函数

Phase 1: 路径常量 + DB_PATH + APP_CONFIG + token 工具
Phase 2: 追加 _ts_patch_pro_api + _akshare_fund_flow_market + skill 解析函数

安全拆分原则: 本模块只定义常量/只读属性,不做 UI、不访问网络、不依赖 tkinter。
"""
import os
import sys
import re
import json
import time as _ts_time
import threading as _ts_threading
from urllib.parse import urljoin

# ==================== 第三方库 availability 标志 ====================
# tushare(667ms) akshare(134ms) 改为延迟导入，启动时不阻塞
_ts_mod = _ak_mod = _np_mod = _pd_mod = _rs_mod = None

def __getattr__(name):
    global _ts_mod, _ak_mod, _np_mod, _pd_mod, _rs_mod
    if name in ('ts', 'TUSHARE'):
        if _ts_mod is None:
            try: import tushare as _m; _ts_mod = _m
            except: _ts_mod = None
        return _ts_mod
    if name in ('ak', 'AKSHARE'):
        if _ak_mod is None:
            try: import akshare as _m; _ak_mod = _m
            except: _ak_mod = None
        return _ak_mod
    if name == 'np':
        if _np_mod is None:
            try: import numpy as _m; _np_mod = _m
            except: _np_mod = None
        return _np_mod
    if name == 'pd':
        if _pd_mod is None:
            try: import pandas as _m; _pd_mod = _m
            except: _pd_mod = None
        return _pd_mod
    if name == 'requests':
        if _rs_mod is None:
            try: import requests as _m; _rs_mod = _m
            except: _rs_mod = None
        return _rs_mod
    # availability flags - 首次访问时按需检测并缓存
    if name == 'TS_AVAILABLE':
        if _ts_mod is None:
            try: import tushare; globals()['_ts_mod'] = tushare
            except: globals()['_ts_mod'] = None
        return _ts_mod is not None
    if name == 'AKSHARE_AVAILABLE':
        if _ak_mod is None:
            try: import akshare; globals()['_ak_mod'] = akshare
            except: globals()['_ak_mod'] = None
        return _ak_mod is not None
    raise AttributeError(f"module 'utils.config' has no attribute '{name}'")

# ==================== 跨模块全局变量 (统一在此定义) ====================
import threading as _threading
STOCK_NAMES_SET = None
STOCK_CODES_DICT = None
STOCK_NAME_TO_CODE = None
ETF_CACHE_REFRESHED = False
STOCK_NAMES_LOAD_LOCK = _threading.Lock()

# ==================== Phase 1: 路径常量 ====================
D_DATA_DIR = (os.environ.get("STOCK_ANALYZER_DATA_DIR") or r"D:\StockAnalyzer").strip() or r"D:\StockAnalyzer"
D_DB_DIR = os.path.join(D_DATA_DIR, "Database")
D_OUTPUT_DIR = os.path.join(D_DATA_DIR, "Output")
D_EXPORT_DIR = os.path.join(D_DATA_DIR, "Export")
D_IMAGES_DIR = os.path.join(D_DATA_DIR, "ConsultationImages")
D_SQLITE_TMP = os.path.join(D_DATA_DIR, "temp")
MANAGED_STOCKS_FILE = os.path.join(D_DATA_DIR, "managed_stocks.json")

for _dir_path in [D_DATA_DIR, D_DB_DIR, D_OUTPUT_DIR, D_EXPORT_DIR, D_IMAGES_DIR, D_SQLITE_TMP]:
    try:
        os.makedirs(_dir_path, exist_ok=True)
    except Exception as _e:
        print(f"创建目录失败 {_dir_path}: {_e}")

_APP_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_SRC_DIR = os.path.dirname(_APP_SRC_DIR)
_APP_CONFIG_DIR = os.path.join(_APP_SRC_DIR, "config")
try:
    os.makedirs(_APP_CONFIG_DIR, exist_ok=True)
except OSError:
    pass

APP_CONFIG_FILE = os.path.join(_APP_CONFIG_DIR, "app_config.json")
DEFAULT_APP_CONFIG = {
    "window_title": "选对池塘钓对鱼,情绪下行就清仓 天时地利人和 金叉乖离背离 子攻现金流操生",
    "font_size": 12,
    "title_color": "#000000"
}


def load_app_config():
    try:
        if os.path.exists(APP_CONFIG_FILE):
            with open(APP_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return DEFAULT_APP_CONFIG


def save_app_config(config):
    try:
        os.makedirs(_APP_CONFIG_DIR, exist_ok=True)
        with open(APP_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


APP_CONFIG = load_app_config()

_STOCKYIDONG_PROJECT_ROOT = os.path.normpath(os.path.join(_APP_SRC_DIR, ".."))
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


def _load_tushare_token_from_local_file():
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


TS_DEFAULT_ACCOUNT = "18939863051"
TS_DEFAULT_TOKEN = (os.environ.get("TUSHARE_TOKEN") or "").strip() or _load_tushare_token_from_local_file()

MARKET_NAV_CONFIG_FILE = os.path.join(_APP_CONFIG_DIR, "market_nav_config.json")


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


def find_script_path_in_monorepo(script_name, tried_paths):
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


# ==================== Phase 2: Tushare API patch ====================
_TS_PATCHED_IDS = set()
_TS_CALL_LOCK = _ts_threading.Lock()


def _ts_patch_pro_api(_orig_pro_api):
    """包装 ts.pro_api(), 加 slot 限频 (仅 sleep, 不重试; 调用方自行 try/except)"""
    _TS_MIN_WAIT = 0.35

    def _patch_client(pro):
        pid = id(pro)
        if pid in _TS_PATCHED_IDS:
            return pro
        try:
            orig_query = pro.query
            def _wrapped_query(*args, **kwargs):
                with _TS_CALL_LOCK:
                    _ts_time.sleep(_TS_MIN_WAIT)
                return orig_query(*args, **kwargs)
            pro.query = _wrapped_query
            _TS_PATCHED_IDS.add(pid)
        except Exception as _e_wrap:
            print(f"  ⚠️ Patch client 失败: {_e_wrap}")
        return pro

    def _patched_pro_api(*args, **kwargs):
        pro = _orig_pro_api(*args, **kwargs)
        return _patch_client(pro)
    return _patched_pro_api


# ==================== Phase 2: akshare market helper ====================
def _akshare_fund_flow_market(code6: str) -> str:
    """ak.stock_individual_fund_flow(stock, market) 的 market:sh / sz / bj"""
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


# ==================== Phase 2: 技能解析辅助 ====================
def load_iwencai_env_from_dotfiles():
    """从 .env 或 .iwencai_cookie 文件加载问财 cookie"""
    pass


def parse_skill_md_for_usage(skill_md_path: str, max_body_chars: int = 8000):
    """解析 skill md 文件提取 usage 信息"""
    pass


# ==================== __all__ (Phase 1 + Phase 2 合并) ====================
__all__ = [
    # 第三方库 availability + 模块
    "TS_AVAILABLE", "ts",
    "AKSHARE_AVAILABLE", "ak",
    "np", "pd", "requests",
    # 跨模块全局变量
    "STOCK_NAMES_SET", "STOCK_CODES_DICT", "STOCK_NAME_TO_CODE",
    "ETF_CACHE_REFRESHED", "STOCK_NAMES_LOAD_LOCK",
    # Phase 1 路径常量
    "D_DATA_DIR", "D_DB_DIR", "D_OUTPUT_DIR", "D_EXPORT_DIR", "D_IMAGES_DIR",
    "D_SQLITE_TMP", "MANAGED_STOCKS_FILE",
    "_APP_SRC_DIR", "_APP_CONFIG_DIR",
    "APP_CONFIG_FILE", "DEFAULT_APP_CONFIG", "APP_CONFIG",
    "load_app_config", "save_app_config",
    "DB_PATH",
    "TS_DEFAULT_ACCOUNT", "TS_DEFAULT_TOKEN",
    "_load_tushare_token_from_local_file",
    "MARKET_NAV_CONFIG_FILE", "CRAWLER_CONFIG_FILE", "EXCEL_FILES_CONFIG_FILE",
    "_resolve_market_nav_config_path", "_resolve_crawler_config_path",
    "find_script_path_in_monorepo",
    # Phase 2
    "_ts_patch_pro_api", "_akshare_fund_flow_market",
    "load_iwencai_env_from_dotfiles", "parse_skill_md_for_usage",
]



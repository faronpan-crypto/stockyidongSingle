"""
同花顺 iFinD MCP 简化调用客户端
- 无 session 模式 (新版 MCP endpoint 不需要 Mcp-Session-Id)
- 统一工具集: security_highfreq_quotes / search_trending_news / search_news / search_notice / get_security_indicators / fetch_edb / search_edb / search_securities / get_stock_summary
- 返回格式: {"ok": bool, "data": dict|None, "error": str|None}
"""
import json
import os
import warnings
from pathlib import Path

import requests

# ── 配置: 优先环境变量, 其次 mcp_config.json ──
_PLUGIN_DIR = Path.home() / ".trae-cn" / "plugins" / "trae-remote-official" / "ifind" / "1.5.0" / "skills" / "ifind-finance-data"
_CONFIG_PATH = _PLUGIN_DIR / "mcp_config.json"

try:
    _CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
except Exception:
    _CONFIG = {}

AUTH_TOKEN = os.getenv("IFIND_AUTH_TOKEN") or _CONFIG.get("IFIND_AUTH_TOKEN", "")
SERVER_URL = "https://api-mcp.51ifind.com:8643/ds-mcp-servers/hexin-ifind-financial-mcp"

warnings.filterwarnings("ignore", category=Warning)


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {AUTH_TOKEN}",
    }


def mcp_call(server_type: str, tool_name: str, params: dict, timeout: int = 60) -> dict:
    """发起一次 MCP tools/call 请求 (无 session)"""
    if not AUTH_TOKEN:
        return {"ok": False, "error": "缺少 IFIND_AUTH_TOKEN, 请在 Trae 插件里授权 iFinD"}

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": params},
    }
    try:
        resp = requests.post(SERVER_URL, json=payload, headers=_headers(), verify=False, timeout=timeout)
        if resp.status_code != 200:
            _body = resp.text[:300] if resp.text else ""
            if resp.status_code == 429:
                return {"ok": False, "error": f"iFinD 限流 (429), 请稍后重试"}
            return {"ok": False, "error": f"HTTP {resp.status_code}: {_body}"}
        if not resp.text.strip():
            return {"ok": False, "error": "空响应"}
        j = resp.json()
    except Exception as e:
        return {"ok": False, "error": f"请求异常: {e}"}

    # 解包: 新版 MCP 返回 result.content[].text 是 JSON 字符串
    if "result" in j:
        for c in j["result"].get("content", []):
            if c.get("type") == "text":
                try:
                    inner = json.loads(c["text"])
                    return {"ok": inner.get("code") == 1, "data": inner, "error": inner.get("msg") if inner.get("code") != 1 else None}
                except Exception:
                    return {"ok": True, "data": c["text"], "error": None}
    if "error" in j:
        return {"ok": False, "error": str(j["error"])}
    return {"ok": True, "data": j, "error": None}


# ── 常用高层封装 ──

def index_realtime(symbols: str = "000001.SH,399001.SZ,399006.SZ,000688.SH") -> dict:
    """大盘指数实时行情 (含涨跌家数/涨停跌停)"""
    return mcp_call("index", "security_highfreq_quotes", {
        "market": "指数",
        "symbols": symbols,
        "indicators": "最新价,涨跌幅,成交额,上涨家数,下跌家数,涨停家数,跌停家数",
        "data_mode": "real_time",
    })


def stock_realtime(symbols: str, indicators: str = "最新价,涨跌幅,成交额,换手率,市盈率TTM,总市值") -> dict:
    """A股个股实时行情"""
    return mcp_call("stock", "security_highfreq_quotes", {
        "market": "A股",
        "symbols": symbols,
        "indicators": indicators,
        "data_mode": "real_time",
    })


def etf_realtime(symbols: str = "510300.SH,159915.SZ,510500.SH,588000.SH,513100.SH,513520.SH") -> dict:
    """热门 ETF 实时行情"""
    return mcp_call("stock", "security_highfreq_quotes", {
        "market": "基金",
        "symbols": symbols,
        "indicators": "最新价,涨跌幅,成交额,折价",
        "data_mode": "real_time",
    })


def trending_news(time_scope: str = "24小时", size: int = 10) -> dict:
    """热点事件资讯"""
    return mcp_call("news", "search_trending_news", {
        "time_scope": time_scope,
        "sensitive": "全部",
        "size": size,
    })


def search_news(query: str, size: int = 10) -> dict:
    """新闻语义检索"""
    return mcp_call("news", "search_news", {
        "query": query,
        "time_start": "2026-01-01",
        "time_end": "2026-12-31",
        "size": size,
    })


def sector_today(query: str = "今日申万一级行业板块的名称、涨跌幅、成交额排名") -> dict:
    """板块行情 (market='板块')"""
    return mcp_call("index", "get_security_indicators", {
        "market": "板块",
        "query": query,
    })


def parse_tables(raw_data: dict):
    """
    从 iFinD 返回 data.tables 里解包出 (表头list, 数据行list[list])
    失败返回 ([], [])
    """
    try:
        tables = raw_data.get("data", {}).get("tables", [])
        if len(tables) < 2:
            return ([], [])
        return (tables[0], tables[1:])
    except Exception:
        return ([], [])


# ── 通用常量 ──
INDEX_SYMBOLS_DEFAULT = "000001.SH,399001.SZ,399006.SZ,000688.SH"
ETF_SYMBOLS_DEFAULT = "510300.SH,159915.SZ,510500.SH,588000.SH,513100.SH,513520.SH"
TRENDING_SIZE_DEFAULT = 10

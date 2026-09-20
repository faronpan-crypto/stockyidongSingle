"""格式化/转换/解析/编码"""
import os, sys, re, json, time, threading, traceback, hashlib, urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
try:
    import numpy as np
except ImportError: np = None
try:
    import pandas as pd
except ImportError: pd = None
try:
    import akshare as ak
except ImportError: ak = None
try:
    import tushare as ts
except ImportError: ts = None
try:
    import requests
except ImportError: requests = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

import re
import json
import os
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class FormatMixin:
    """格式化/转换/解析/编码"""

    def _parse_nuxt_from_html_safe(self, html_content: str):
        """解析选股通等站点注入的 window.__NUXT__(与 src/parse_nuxt.py 同源)。"""
        try:
            from parse_nuxt import parse_nuxt_from_text
            return parse_nuxt_from_text(html_content)
        except Exception:
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "parse_nuxt.py")
            if not os.path.isfile(path):
                raise
            spec = importlib.util.spec_from_file_location("_stockyidong_parse_nuxt", path)
            if not spec or not spec.loader:
                raise
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.parse_nuxt_from_text(html_content)

    def _parse_number(self, numbers, index):
        """解析数字,如果索引超出范围返回None"""
        try:
            if index < len(numbers):
                value = float(numbers[index])
                # 过滤明显不合理的大数字(可能是日期或时间)
                if abs(value) < 1e10:
                    return value
            return None
        except:
            return None

    def _parse_integer(self, numbers, index):
        """解析整数,如果索引超出范围返回None"""
        try:
            if index < len(numbers):
                value = int(float(numbers[index]))
                if abs(value) < 1e6:
                    return value
            return None
        except:
            return None

    def _normalize_stock_code_6(self, code) -> str:
        """提取 A 股 6 位代码(兼容 600000、600000.SH 等)。"""
        import re
        s = re.sub(r"\D", "", str(code or ""))
        if len(s) >= 6:
            return s[-6:]
        if s:
            return s.zfill(6)[:6]
        return ""

    def _parse_delivery_data(self, delivery_data):
        """解析交割单数据,提取交易记录"""
        transactions = []
        lines = delivery_data.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 尝试匹配同花顺交割单格式
            # 常见格式:日期、股票代码、股票名称、买卖、数量、价格、金额等
            transaction = {}
            # 尝试提取股票代码(6位数字)
            import re
            code_match = re.search(r'(\d{6})', line)
            if code_match:
                transaction['code'] = code_match.group(1)
            # 尝试提取股票名称(中文字符)
            name_match = re.search(r'([\u4e00-\u9fa5]+)', line)
            if name_match:
                transaction['name'] = name_match.group(1)
            # 尝试提取买卖方向
            if '买' in line or '买入' in line or 'B' in line.upper():
                transaction['direction'] = '买入'
            elif '卖' in line or '卖出' in line or 'S' in line.upper():
                transaction['direction'] = '卖出'
            # 尝试提取价格(数字.数字格式)
            price_match = re.search(r'(\d+\.\d+)', line)
            if price_match:
                try:
                    transaction['price'] = float(price_match.group(1))
                except:
                    pass
            # 尝试提取数量(整数)
            qty_match = re.search(r'(\d+)\s*股', line)
            if not qty_match:
                qty_match = re.search(r'(\d{3,})', line)  # 至少3位数字可能是数量
            if qty_match:
                try:
                    transaction['quantity'] = int(qty_match.group(1))
                except:
                    pass
            # 尝试提取日期
            date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', line)
            if date_match:
                transaction['date'] = date_match.group(1)
            # 如果解析到有效信息,添加到列表
            if transaction:
                transactions.append(transaction)
        return transactions

    def _parse_market_nav_import_data(self, raw_text):
        """解析外部导航数据,返回规范化字典"""
        if not raw_text:
            return {}
        raw_text = raw_text.strip()
        if not raw_text:
            return {}
        # 1. 尝试 JSON
        try:
            data = json.loads(raw_text)
            normalized = self._normalize_market_nav_data(data)
            if normalized:
                return normalized
        except Exception:
            pass
        # 2. 逐行解析
        return self._parse_market_nav_lines(raw_text)

    def _normalize_market_nav_data(self, data):
        """将外部数据归一化为配置结构"""
        result = {"indices": [], "portals": [], "hot_sources": [], "dv_accounts": []}
        def normalize_entry(item, require_desc=False):
            if not isinstance(item, dict):
                return None
            name = item.get("name") or item.get("title")
            url = item.get("url") or item.get("link")
            if not name or not url:
                return None
            entry = {"name": name.strip(), "url": url.strip()}
            desc_val = item.get("desc") or item.get("description") or item.get("summary") or ""
            if require_desc or desc_val:
                entry["desc"] = desc_val.strip()
            return entry
        def append_items(key, items, require_desc=False):
            if not isinstance(items, list):
                return
            for item in items:
                entry = normalize_entry(item, require_desc=require_desc)
                if entry:
                    # 设置排序字段
                    entry["sort_order"] = len(result[key]) + 1
                    result[key].append(entry)
        if isinstance(data, dict):
            append_items("indices", data.get("indices") or data.get("index") or data.get("macro"), require_desc=True)
            append_items("portals", data.get("portals") or data.get("platforms") or data.get("sites"))
            append_items("hot_sources", data.get("hot_sources") or data.get("hot") or data.get("hotlists"))
            append_items("dv_accounts", data.get("dv_accounts") or data.get("dv") or data.get("kens"), require_desc=True)
            return result
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                key = self._map_market_nav_category(item.get("type") or item.get("category"))
                if not key:
                    continue
                entry = normalize_entry(item, require_desc=(key == "indices"))
                if entry:
                    result[key].append(entry)
            return result
        return result

    def _parse_market_nav_lines(self, raw_text):
        """解析文本格式的导航数据"""
        result = {"indices": [], "portals": [], "hot_sources": [], "dv_accounts": []}
        lines = raw_text.splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("{") and line.endswith("}"):
                try:
                    item = json.loads(line)
                    key = self._map_market_nav_category(item.get("type") or item.get("category"))
                    if not key:
                        continue
                    entry = {
                        "name": item.get("name") or item.get("title"),
                        "url": item.get("url") or item.get("link"),
                        "desc": item.get("desc") or item.get("description") or ""
                    }
                    if entry["name"] and entry["url"]:
                        if not entry["desc"]:
                            entry.pop("desc")
                        # 设置排序字段
                        entry["sort_order"] = len(result[key]) + 1
                        result[key].append(entry)
                    continue
                except Exception:
                    pass
            parts = [p.strip() for p in re.split(r"[|,,]", line) if p.strip()]
            if len(parts) < 3:
                continue
            key = self._map_market_nav_category(parts[0])
            if not key:
                continue
            name = parts[1]
            url = parts[2]
            desc = parts[3] if len(parts) > 3 else ""
            if not name or not url:
                continue
            entry = {"name": name, "url": url}
            if desc:
                entry["desc"] = desc
            # 设置排序字段
            entry["sort_order"] = len(result[key]) + 1
            result[key].append(entry)
        return result

    def _format_ts_code(self, stock_code: str) -> str:
        """将普通股票代码转换为Tushare格式"""
        if not stock_code:
            return ""
        stock_code = stock_code.strip()
        if stock_code.startswith(("5", "6", "9")):
            suffix = "SH"
        else:
            suffix = "SZ"
        return f"{stock_code}.{suffix}"

    def _format_skillhub_result_display(self, raw: str) -> str:
        """将问财 API / 技能 CLI 返回的 JSON 整理为「概要 + 表格」便于直接阅读(不附带接口调试 JSON)。"""
        import json
        import re as _re
        # 问财 OpenAPI 常见调试字段:对用户阅读无帮助,且含英文字段名/SQL/列定义
        _wencai_meta_keys = frozenset(
            {
                "code",
                "message",
                "datas",
                "success",
                "error",
                "query",
                "count",
                "QTime",
                "qtime",
                "q_time",
                "model_sql",
                "data_sql",
                "columns",
                "column",
                "expand_index",
                "is_cache",
                "page",
                "limit",
                "source",
                "trace_id",
                "request_id",
                "tid",
                "token",
            }
        )
        raw = (raw or "").strip()
        if not raw:
            return "(无输出)"
        if raw.startswith(("未设置 IWENCAI_API_KEY", "请输入", "请求失败")):
            return raw
        if raw.startswith("HTTP "):
            return raw
        obj = None
        try:
            obj = json.loads(raw)
        except Exception:
            m = _re.search(r"\{[\s\S]*\}\s*$", raw.strip())
            if m:
                try:
                    obj = json.loads(m.group(0))
                except Exception:
                    pass
        if obj is None:
            return raw
        lines = []
        if isinstance(obj, dict):
            if obj.get("success") is False:
                return "【执行失败】\n" + str(obj.get("error", obj))
            code, msg = obj.get("code"), obj.get("message")
            if code is not None or (msg and str(msg).lower() not in ("", "none")):
                lines.append("──────── 概要 ────────")
                if code is not None:
                    lines.append(f"状态码:{code}")
                if msg is not None:
                    lines.append(f"说明:{msg}")
                lines.append("")
            datas = obj.get("datas")
            datas_has_rows = isinstance(datas, list) and len(datas) > 0
            if datas_has_rows:
                lines.append(f"──────── 数据表(共 {len(datas)} 条,至多展示 500 条)────────")
                try:
                    slice_rows = datas[:500]
                    if all(isinstance(x, dict) for x in slice_rows):
                        df = pd.DataFrame(slice_rows)
                        lines.append(df.to_string(index=False))
                    else:
                        lines.append(json.dumps(slice_rows, ensure_ascii=False, indent=2))
                except Exception:
                    lines.append(json.dumps(datas[:100], ensure_ascii=False, indent=2))
                lines.append("")
            elif isinstance(datas, list):
                lines.append("──────── 数据 ────────\n(暂无数据行)\n")
            skip = {"code", "message", "datas", "success", "error", "query", "count"}
            rest = {k: v for k, v in obj.items() if k not in skip}
            rest_user = {k: v for k, v in rest.items() if k not in _wencai_meta_keys}
            # 已有可读表格时不再追加「其它字段」里的 SQL/columns 等,避免满屏英文调试信息
            if rest_user and not datas_has_rows:
                lines.append("──────── 补充信息 ────────")
                lines.append(json.dumps(rest_user, ensure_ascii=False, indent=2))
        elif isinstance(obj, list):
            lines.append("──────── JSON 数组 ────────")
            try:
                if obj and all(isinstance(x, dict) for x in obj[:500]):
                    lines.append(pd.DataFrame(obj[:500]).to_string(index=False))
                else:
                    lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
            except Exception:
                lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
        out = "\n".join(lines).strip()
        if not out:
            return json.dumps(obj, ensure_ascii=False, indent=2)
        return out

    def _format_dashboard_report(self, data):
        """格式化仪表盘 JSON → 报告"""
        risk = data.get("risk", {})
        score = risk.get("risk_score", 0)
        level = risk.get("level", "--")
        action = risk.get("action", "")
        dims = risk.get("dims", {})
        lines = []
        lines.append("═" * 55)
        lines.append(f"🚦 大盘风险仪表盘报告  总分 {score}/100  [{level}]")
        lines.append("═" * 55)
        lines.append(f"⏰ {data.get('time','?')}")
        lines.append(f"📌 {action}")
        lines.append("")
        # 分维度详解
        dim_weights = {"估值": 40, "杠杆": 25, "量能": 20, "利率": 15}
        for name, info in dims.items():
            max_s = dim_weights.get(name, info.get("max", 0))
            sc = info.get("score", 0)
            lines.append(f"  【{name}】{sc}/{max_s}  {info.get('desc','')}")
        lines.append("")
        lines.append("═" * 55)
        lines.append("📖 方法论（四层递进）")
        lines.append("═" * 55)
        # 动态生成建议
        if score >= 65:
            lines.append("\n⚠️  逃顶信号！多维度共振见顶区域\n")
            lines.append("  操作: 降低杠杆，落袋为安，减仓到 50% 以下")
            lines.append("  观察: 等缩量回调 + 情绪冷却 再考虑接回")
        elif score <= 25:
            lines.append("\n✅  抄底区域！估值+情绪低位共振\n")
            lines.append("  操作: 可分批建仓，不要等绝对底")
            lines.append("  观察: 政策信号（降准降息/国家队进场）")
        else:
            lines.append("\n⚖️  正常区间，结构性机会为主\n")
            lines.append("  操作: 保持仓位，板块轮动")
            lines.append("  观察: 哪一个维度先突破（见顶信号通常先量能后估值）")
        # 与早盘S-T指导的衔接
        lines.append("")
        lines.append("━" * 55)
        lines.append("🔗 与早盘S-T指导的衔接")
        lines.append("━" * 55)
        lines.append("  战术层: 早盘S-T指导 → 日内做T方向")
        lines.append("  战略层: 大盘风险仪表盘 → 周度逃顶/抄底方向（本报告）")
        lines.append("  情绪层: 情绪周期 skill → 5 阶段判断")
        return "\n".join(lines)


__all__ = ["FormatMixin"]

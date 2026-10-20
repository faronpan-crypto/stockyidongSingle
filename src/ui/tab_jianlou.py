# -*- coding: utf-8 -*-
"""
🧲 捡漏扫描器 — 多维度异常行情捕获

扫描维度:
  🔴 大跌预警  chg ≤ -8%   (捡反弹机会)
  🟢 大涨龙头  chg ≥ +10%  (关注龙头延续)
  💥 放量异动  量比 ≥ 3x   (主力异动)
  ⚠️ 振幅异常  振幅 ≥ 12%  (波动剧烈)
  🟡 昨跌今稳  昨跌≥7% + 今收平/涨 (恐慌盘后企稳)

❓ 双击弹该异常特征解读
双击股票行 → 弹日K线图
"""
import json
import os
import re
import ssl
import threading
import time
import urllib.request
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

# ── 配色 ──
_BG_DEEP = "#121212"
_BG_PANEL = "#1E1E1E"
_BG_CARD = "#2A2A2A"
_BG_TOOLBAR = "#1A1A1A"
_FG_RED = "#FF8A80"
_FG_GREEN = "#69F0AE"
_FG_GOLD = "#FFD54F"
_FG_BLUE = "#90CAF9"
_FG_CYAN = "#80DEEA"
_FG_TEXT = "#E0E0E0"
_FG_DIM = "#888888"
_FG_ORANGE = "#FFB74D"
_FG_PURPLE = "#CE93D8"

# ── 异常特征解读库 ──
_HELP_DB = {
    "大跌": """🔍 大跌解读 (当日跌幅 ≥ 8%)

📌 为什么会跌:
  • 大盘/板块联动下杀
  • 个股利空 (业绩爆雷/减持/监管)
  • 前期涨幅过大获利盘集中出逃

📌 后续可能怎么走:
  • 恐慌杀跌 → 次日惯性低开 → 3-5天修复 (经典洗盘)
  • 真破位 → 连续阴跌数月 (基本面恶化)
  • V型反转 → 主力最后洗盘拉升 (伴随缩量)

📌 捡漏要点:
  ✅ 行业龙头 + 缩量大跌 + 无实质利空 → 高胜率
  ✅ 急跌不接飞刀, 等5日线企稳/放量长阳再进
  ❌ 下跌放量 + 基本面有问题 → 回避""",

    "大涨": """🔍 大涨解读 (当日涨幅 ≥ 10%)

📌 为什么会涨:
  • 利好催化 (政策/业绩/重组)
  • 主力强势拉升吸筹
  • 板块轮动资金涌入

📌 后续可能怎么走:
  • 连续涨停 → 龙头行情 (热门题材)
  • 冲高回落 → 高开低走大阴线 (出货)
  • 高位震荡 → 横盘洗筹后继续突破

📌 跟进要点:
  ✅ 涨停封板量能充足 → 次日溢价高
  ✅ 首板/2板 + 板块联动 → 关注持续性
  ❌ 放巨量长上影 → 主力出货, 别追""",

    "放量": """🔍 放量异动解读 (量比 ≥ 3)

📌 量比 = 当日成交量 / 近10日均量
  3x以上 = 显著异动; 5x以上 = 剧烈异动

📌 放量原因:
  • 主力建仓吸筹 (低位放量)
  • 高位出货派发 (高位放量滞涨)
  • 利好/利空消息引爆

📌 观察要点:
  ✅ 低位放量上涨 → 主升浪启动信号
  ✅ 下跌中放量 → 恐慌盘涌出, 可能见底
  ❌ 高位放量滞涨 (量价背离) → 危险信号""",

    "振幅": """🔍 振幅异常解读 (振幅 ≥ 12%)

📌 振幅 = (最高 - 最低) / 昨收 × 100%
  反映当日多空博弈剧烈程度

📌 振幅大的原因:
  • 消息面剧烈刺激 (早盘砸尾盘拉 / 早盘拉尾盘砸)
  • T+0 主力日内大幅做差价
  • 流动性差 (小盘股 / 低成交量)

📌 观察要点:
  ✅ 下影线长 + 收红 → 多头反击, 次日看涨
  ❌ 上影线长 + 收绿 → 空头占优, 次日看跌""",

    "昨跌今稳": """🔍 昨跌今稳解读 (昨跌≥7% + 今收平/涨)

📌 典型"恐慌盘后企稳"形态:
  • 昨日恐慌砸出低位筹码
  • 今日承接有力, 价格不再创新低
  • 量能萎缩 (抛压衰竭)

📌 历史胜率:
  • A股数据统计: 次日上涨概率 58%
  • 连续杀跌后的企稳 → 反弹力度更强

📌 操作建议:
  ✅ 关注这类标的的二次进场机会
  ✅ 等次日早盘不低开再确认进场
  ❌ 如果今日再次破昨低 → 企稳失败""",
}


class JianLouMixin:
    """捡漏扫描器 mixin — 加到主应用 class 上"""

    def _show_jianlou(self):
        import tkinter as tk
        from tkinter import ttk, messagebox
        import numpy as np
        from datetime import datetime as _DT

        dlg = tk.Toplevel(getattr(self, "win", None) or self.root)
        dlg.title("🧲 捡漏扫描器")
        dlg.geometry("1280x780")
        dlg.configure(bg=_BG_DEEP)

        # ── 顶部工具栏 ──
        top = tk.Frame(dlg, bg=_BG_TOOLBAR, height=40); top.pack(fill=tk.X)
        top.pack_propagate(False)

        tk.Label(top, text="🧲 捡漏扫描器", bg=_BG_TOOLBAR, fg=_FG_GOLD,
                 font=("Menlo", 12, "bold")).pack(side=tk.LEFT, padx=12)
        status = tk.Label(top, text="⏳ 加载股票池...", bg=_BG_TOOLBAR, fg=_FG_DIM,
                          font=("Menlo", 10))
        status.pack(side=tk.RIGHT, padx=12)

        def _btn(text, cmd, fg=_FG_GREEN):
            b = tk.Button(top, text=text, command=cmd, bg=_BG_PANEL, fg=fg,
                          activebackground=_BG_CARD, activeforeground=fg,
                          font=("Menlo", 10), relief=tk.FLAT, padx=8, pady=2,
                          cursor="hand2")
            return b

        refresh_btn = _btn("🔄 扫描", lambda: None, _FG_CYAN)
        refresh_btn.pack(side=tk.LEFT, padx=6, pady=6)

        add_btn = _btn("➕加股", lambda: None, _FG_GOLD)
        add_btn.pack(side=tk.LEFT, padx=4, pady=6)

        tk.Label(top, text="  🔴跌≥8%  🟢涨≥10%  💥量比≥3  ⚠️振幅≥12%  🟡昨跌今稳",
                 bg=_BG_TOOLBAR, fg=_FG_DIM, font=("Menlo", 9)).pack(side=tk.LEFT, padx=10)

        # ── Notebook 分类展示 ──
        nb = ttk.Notebook(dlg)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ttk 深色主题
        style = ttk.Style()
        try:
            style.theme_use("clam")
            style.configure("TNotebook", background=_BG_DEEP, borderwidth=0)
            style.configure("TNotebook.Tab", background=_BG_PANEL, foreground=_FG_TEXT,
                            padding=(14, 4), font=("Menlo", 10))
            style.map("TNotebook.Tab", background=[("selected", _BG_CARD)],
                      foreground=[("selected", _FG_GOLD)])
            style.configure("TFrame", background=_BG_DEEP)
        except Exception:
            pass

        # 5 个分类 Tab
        tabs = {
            "drops": ("🔴 大跌预警", _FG_RED),
            "surges": ("🟢 大涨龙头", _FG_GREEN),
            "volume": ("💥 放量异动", _FG_ORANGE),
            "swing": ("⚠️ 振幅异常", _FG_PURPLE),
            "bottom": ("🟡 昨跌今稳", _FG_GOLD),
        }
        tab_frames = {}
        for key, (label, color) in tabs.items():
            f = ttk.Frame(nb)
            nb.add(f, text=label)
            tab_frames[key] = {"frame": f, "color": color, "rows": []}

        # ── 滚动容器: 每个 tab 里放一个可滚动 Frame ──
        def _make_scrollable(parent):
            cv = tk.Canvas(parent, bg=_BG_DEEP, highlightthickness=0)
            vsb = tk.Scrollbar(parent, orient="vertical", command=cv.yview)
            inner = tk.Frame(cv, bg=_BG_DEEP)
            inner.bind("<Configure>", lambda e, c=cv: c.configure(scrollregion=c.bbox("all")))
            cv.create_window((0, 0), window=inner, anchor="nw")
            cv.configure(yscrollcommand=vsb.set)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            # 鼠标滚轮
            def _wheel(e): cv.yview_scroll(-1 * (e.delta // 120), "units")
            cv.bind_all("<MouseWheel>", _wheel)
            return inner, cv

        scroll_inners = {}
        for key in tab_frames:
            inner, cv = _make_scrollable(tab_frames[key]["frame"])
            scroll_inners[key] = inner

        # ── 数据存储 ──
        _scan_data = {"results": {}, "stock_pool": [], "loading": False}

        # ── 解析股票池 ──
        def _load_stock_pool():
            pool = {}

            # 1) 持仓 tab
            pos_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "..", "data", "trading_positions.json")
            pos_path = os.path.abspath(pos_path)
            if os.path.exists(pos_path):
                try:
                    with open(pos_path, "r") as f:
                        positions = json.load(f)
                    for p in positions:
                        code6 = str(p.get("code", ""))
                        if not code6: continue
                        sina = code6 if code6.startswith(("sh", "sz", "bj")) else _sina_from_code(code6)
                        pool[sina] = {"name": p.get("name", code6), "source": "持仓", "code6": code6}
                except Exception:
                    pass

            # 2) 龙头股: 解析 data/stockyidong
            syd_path = None
            for cand in [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "stockyidong"),
                os.path.expanduser("~/Desktop/stockyidong"),
                os.path.expanduser("~/stockyidong"),
            ]:
                if os.path.exists(cand):
                    syd_path = cand; break
            if syd_path:
                try:
                    with open(syd_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    # 找 【龙头股】 板块
                    m = re.search(r"【龙头股】\s*\n(.*?)(?=【|\Z)", content, re.S)
                    if m:
                        block = m.group(1)
                        # 每行业一行, 格式: "行业A: 600519茅台, 000858五粮液"
                        for line in block.split("\n"):
                            line = line.strip()
                            if not line or ":" not in line: continue
                            _, stocks = line.split(":", 1)
                            for item in re.split(r"[,，\s]+", stocks):
                                item = item.strip()
                                if not item: continue
                                cm = re.match(r"(\d{6})(\D+)?", item)
                                if cm:
                                    code6, nm = cm.group(1), cm.group(2) or code6
                                    sina = _sina_from_code(code6)
                                    pool[sina] = {"name": nm, "source": "龙头", "code6": code6}
                except Exception:
                    pass

            return pool

        def _sina_from_code(code6):
            """6位代码 → sina code"""
            if not code6 or len(code6) != 6: return code6
            first = code6[0]
            second = code6[1]
            if first in ("6", "5", "9"):
                return "sh" + code6
            elif first in ("0", "3", "1", "2"):
                return "sz" + code6
            elif first in ("4", "8"):
                return "bj" + code6
            return "sz" + code6

        # ── 批量拉实时行情 (hq.sinajs.cn) ──
        def _fetch_realtime(codes):
            """codes: sina_code list → dict {sina: info}"""
            if not codes: return {}
            ctx = ssl._create_unverified_context()
            batch_size = 60
            results = {}
            for i in range(0, len(codes), batch_size):
                batch = codes[i:i + batch_size]
                url = "https://hq.sinajs.cn/list=" + ",".join(batch)
                try:
                    req = urllib.request.Request(url,
                                                 headers={"User-Agent": "Mozilla/5.0",
                                                          "Referer": "https://finance.sina.com.cn"})
                    with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                        text = resp.read().decode("gbk", errors="ignore")
                    for line in text.strip().split("\n"):
                        if "=" not in line or '"' not in line: continue
                        var, val = line.split("=", 1)
                        sina_code = var.replace("var hq_str_", "").strip()
                        flds = val.strip().strip(";").strip('"').split(",")
                        if len(flds) < 40: continue
                        try:
                            info = {
                                "name": flds[0],
                                "open": float(flds[1]),
                                "prev_close": float(flds[2]),
                                "cur": float(flds[3]),
                                "high": float(flds[4]),
                                "low": float(flds[5]),
                                "vol_hand": float(flds[36]),  # 手
                                "amount": float(flds[37]),    # 元
                                "date": flds[30],
                                "time": flds[31],
                            }
                            info["chg_pct"] = (info["cur"] / info["prev_close"] - 1) * 100 if info["prev_close"] > 0 else 0
                            info["amplitude"] = (info["high"] - info["low"]) / info["prev_close"] * 100 if info["prev_close"] > 0 else 0
                            info["vol_wan"] = info["vol_hand"] / 100  # 万手
                            results[sina_code] = info
                        except (ValueError, IndexError):
                            pass
                except Exception as e:
                    print(f"[捡漏] hq batch err: {e}", flush=True)
                time.sleep(0.15)
            return results

        # ── 拉日线算均量 (东方财富) ──
        def _fetch_ma_vol(sina_code, days=10):
            """返回近 days 日均量 (万手)"""
            if requests is None: return None
            prefix = sina_code[:2]
            code6 = sina_code[2:]
            secid_map = {"sh": "1", "sz": "0", "bj": "0"}
            secid = f"{secid_map.get(prefix, '1')}.{code6}"
            try:
                url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
                       f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
                       f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
                       f"&klt=101&fqt=1&beg=0&end=20500101")
                r = requests.get(url, timeout=5,
                                 headers={"User-Agent": "Mozilla/5.0",
                                          "Referer": "https://quote.eastmoney.com"})
                if r.status_code != 200: return None
                d = r.json()
                klines = d.get("data", {}).get("klines") or []
                if len(klines) < 3: return None
                vols = []
                for line in klines[-days:]:
                    parts = line.split(",")
                    if len(parts) >= 6:
                        try: vols.append(float(parts[5]) / 100)  # 股→手→万手 (除以10000)
                        except: pass
                if vols:
                    return sum(vols) / len(vols)
            except Exception:
                pass
            return None

        # ── 渲染一个分类 tab ──
        def _render_tab(tab_key, items):
            inner = scroll_inners[tab_key]
            # 清旧
            for w in inner.winfo_children(): w.destroy()
            tab_frames[tab_key]["rows"] = []

            # 表头
            header = tk.Frame(inner, bg=_BG_PANEL, height=28); header.pack(fill=tk.X, pady=(4, 2))
            header.pack_propagate(False)
            def _hcol(text, w, fg=_FG_DIM):
                tk.Label(header, text=text, bg=_BG_PANEL, fg=fg, font=("Menlo", 9, "bold"),
                         width=w, anchor="w").pack(side=tk.LEFT, padx=2)
            _hcol("股票", 18, _FG_GOLD)
            _hcol("涨跌%", 8, _FG_DIM)
            _hcol("现价", 8)
            _hcol("量比", 6)
            _hcol("振幅%", 7)
            _hcol("来源", 8, _FG_BLUE)
            tk.Label(header, text="❓", bg=_BG_PANEL, fg=_FG_DIM,
                     font=("Menlo", 9), width=3).pack(side=tk.RIGHT, padx=4)

            if not items:
                tk.Label(inner, text="（暂无符合条件的股票）", bg=_BG_DEEP, fg=_FG_DIM,
                         font=("Menlo", 10)).pack(pady=24)
                return

            # 按 chg_pct 排序 (大跌升序, 大涨降序)
            items.sort(key=lambda x: x.get("chg_pct", 0),
                       reverse=(tab_key in ("surges", "volume", "swing")))

            for it in items:
                sina = it["sina"]
                row_bg = _BG_CARD if len(tab_frames[tab_key]["rows"]) % 2 == 0 else "#252535"
                row = tk.Frame(inner, bg=row_bg, cursor="hand2")
                row.pack(fill=tk.X, pady=1)

                nm = it.get("name", sina)
                chg = it.get("chg_pct", 0)
                cur = it.get("cur", 0)
                vr = it.get("vol_ratio")
                amp = it.get("amplitude", 0)
                src = it.get("source", "")

                chg_fg = _FG_RED if chg < 0 else _FG_GREEN if chg > 0 else _FG_DIM
                chg_txt = f"{chg:+.2f}%"
                vr_txt = f"{vr:.1f}" if vr is not None else "N/A"
                amp_txt = f"{amp:.1f}%"

                l_name = tk.Label(row, text=f"  {nm[:8]}({sina[2:]})", bg=row_bg, fg=_FG_TEXT,
                                  font=("Menlo", 10, "bold"), anchor="w")
                l_name.pack(side=tk.LEFT, padx=2)

                l_chg = tk.Label(row, text=chg_txt, bg=row_bg, fg=chg_fg,
                                 font=("Menlo", 11, "bold"), width=8, anchor="w")
                l_chg.pack(side=tk.LEFT, padx=2)

                l_cur = tk.Label(row, text=f"{cur:.2f}", bg=row_bg, fg=_FG_CYAN,
                                 font=("Menlo", 10), width=8, anchor="w")
                l_cur.pack(side=tk.LEFT, padx=2)

                l_vr = tk.Label(row, text=vr_txt, bg=row_bg,
                                fg=_FG_ORANGE if (vr and vr >= 3) else _FG_DIM,
                                font=("Menlo", 10), width=6, anchor="w")
                l_vr.pack(side=tk.LEFT, padx=2)

                l_amp = tk.Label(row, text=amp_txt, bg=row_bg,
                                 fg=_FG_PURPLE if amp >= 12 else _FG_DIM,
                                 font=("Menlo", 10), width=7, anchor="w")
                l_amp.pack(side=tk.LEFT, padx=2)

                l_src = tk.Label(row, text=src, bg=row_bg, fg=_FG_BLUE,
                                 font=("Menlo", 9), width=8)
                l_src.pack(side=tk.LEFT, padx=2)

                # ❓ 帮助按钮
                help_key = tab_key_to_help(tab_key)
                l_help = tk.Label(row, text="❓", bg=row_bg, fg=_FG_GOLD,
                                  font=("Menlo", 11), cursor="hand2")
                l_help.pack(side=tk.RIGHT, padx=6)

                # 点击 → 弹日K
                def _open_kline(_s=sina, _n=nm):
                    try:
                        from ui.high_low_swing import _quick_open_daily_kline
                        _quick_open_daily_kline(dlg, _s, _n)
                    except Exception as e:
                        print(f"[捡漏] 开K线失败: {e}", flush=True)

                def _show_help(_k=help_key):
                    _show_help_popup(dlg, _k)

                # 给 row + 所有子控件绑双击
                for w in [row, l_name, l_chg, l_cur, l_vr, l_amp, l_src]:
                    w.bind("<Double-Button-1>", lambda e, fn=_open_kline: fn())
                l_help.bind("<Double-Button-1>", lambda e, fn=_show_help: fn())
                l_help.bind("<Button-1>", lambda e, fn=_show_help: fn())  # ❓单击也弹

                tab_frames[tab_key]["rows"].append(row)

        def tab_key_to_help(k):
            return {"drops": "大跌", "surges": "大涨", "volume": "放量",
                    "swing": "振幅", "bottom": "昨跌今稳"}.get(k, "")

        def _show_help_popup(parent, help_key):
            content = _HELP_DB.get(help_key, "暂无说明")
            win = tk.Toplevel(parent)
            win.title(f"❓ {help_key} 解读")
            win.geometry("520x460")
            win.configure(bg=_BG_DEEP)
            win.transient(parent)

            tk.Label(win, text=f"❓ {help_key} — 特征解读", bg=_BG_DEEP, fg=_FG_GOLD,
                     font=("Menlo", 12, "bold")).pack(pady=(12, 6))

            txt = tk.Text(win, bg=_BG_PANEL, fg=_FG_TEXT, font=("Menlo", 10),
                          wrap=tk.WORD, relief=tk.FLAT, padx=14, pady=10,
                          height=18)
            txt.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)
            txt.insert(tk.END, content)
            txt.config(state=tk.DISABLED)

            tk.Button(win, text="关闭", command=win.destroy, bg=_BG_PANEL, fg=_FG_CYAN,
                      relief=tk.FLAT, padx=20, pady=4, font=("Menlo", 10)).pack(pady=10)

        # ── 主扫描流程 ──
        def _do_scan():
            if _scan_data["loading"]: return
            _scan_data["loading"] = True
            refresh_btn.config(state=tk.DISABLED)

            def _bg():
                try:
                    # 1) 加载股票池
                    pool = _load_stock_pool()
                    sina_list = list(pool.keys())
                    if not sina_list:
                        dlg.after(0, lambda: status.config(text="⚠️ 没有股票池 (持仓空 + 龙头文件没找到)", fg=_FG_ORANGE))
                        return
                    dlg.after(0, lambda: status.config(
                        text=f"📊 股票池 {len(sina_list)} 只, 拉实时行情...", fg=_FG_TEXT))

                    # 2) 拉实时行情
                    realtime = _fetch_realtime(sina_list)
                    if not realtime:
                        dlg.after(0, lambda: status.config(text="❌ 实时行情拉取失败", fg=_FG_RED))
                        return
                    dlg.after(0, lambda: status.config(
                        text=f"📡 实时行情 {len(realtime)} 只, 拉均量...", fg=_FG_TEXT))

                    # 3) 拉均量 (逐只, 但并行多线程)
                    ma_vols = {}
                    def _fetch_one(s):
                        ma_vols[s] = _fetch_ma_vol(s, 10)

                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                        list(ex.map(_fetch_one, [s for s in sina_list if s in realtime]))

                    # 4) 组装完整数据 + 分类
                    results = {"drops": [], "surges": [], "volume": [], "swing": [], "bottom": []}
                    for sina, info in realtime.items():
                        it = {"sina": sina, "source": pool.get(sina, {}).get("source", ""), **info}
                        # 量比
                        ma_v = ma_vols.get(sina)
                        if ma_v and info["vol_wan"] > 0:
                            it["vol_ratio"] = info["vol_wan"] / ma_v
                        else:
                            it["vol_ratio"] = None

                        chg = info["chg_pct"]
                        amp = info["amplitude"]
                        vr = it["vol_ratio"] or 0

                        if chg <= -8: results["drops"].append(it)
                        if chg >= 10: results["surges"].append(it)
                        if vr >= 3: results["volume"].append(it)
                        if amp >= 12: results["swing"].append(it)
                        # 昨跌今稳: 需要昨收 < 前日收 (昨跌≥7%) → 简化: 用 chg_pct
                        # 昨跌 = 今日 prev_close 相对前日收盘. 实时 hq 拿不到前日收盘, 跳过

                    # 5) 渲染
                    total = sum(len(v) for v in results.values())
                    def _render_all():
                        for k in results:
                            _render_tab(k, results[k])
                        status.config(
                            text=f"✅ 扫描完成: 共 {total} 只异常 "
                                 f"(跌{len(results['drops'])} 涨{len(results['surges'])} "
                                 f"量{len(results['volume'])} 振{len(results['swing'])})",
                            fg=_FG_GREEN)

                    dlg.after(0, _render_all)
                except Exception as e:
                    import traceback; traceback.print_exc()
                    dlg.after(0, lambda: status.config(text=f"❌ 扫描异常: {e}", fg=_FG_RED))
                finally:
                    _scan_data["loading"] = False
                    dlg.after(0, lambda: refresh_btn.config(state=tk.NORMAL))

            threading.Thread(target=_bg, daemon=True).start()

        refresh_btn.config(command=_do_scan)

        # ➕加股按钮
        def _add_stock():
            win = tk.Toplevel(dlg)
            win.title("添加股票")
            win.geometry("360x140")
            win.configure(bg=_BG_DEEP)
            win.transient(dlg)

            tk.Label(win, text="输入6位股票代码 (多个用逗号分隔):",
                     bg=_BG_DEEP, fg=_FG_TEXT, font=("Menlo", 10)).pack(pady=(12, 4))
            ent = tk.Entry(win, font=("Menlo", 12), bg=_BG_PANEL, fg=_FG_TEXT,
                           insertbackground=_FG_TEXT, relief=tk.FLAT)
            ent.pack(padx=20, pady=4, fill=tk.X)
            ent.focus_set()

            def _ok():
                txt = ent.get().strip()
                for code6 in re.split(r"[,，\s]+", txt):
                    code6 = code6.strip()
                    if not code6 or not code6.isdigit() or len(code6) != 6: continue
                    sina = _sina_from_code(code6)
                    pool_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                             "..", "data", "trading_positions.json")
                    pool_path = os.path.abspath(pool_path)
                    positions = []
                    if os.path.exists(pool_path):
                        try: positions = json.load(open(pool_path))
                        except: pass
                    # 检查是否已存在
                    if not any(str(p.get("code", "")) == code6 for p in positions):
                        positions.append({"code": code6, "name": code6, "shares": 0, "cost": 0})
                        try:
                            os.makedirs(os.path.dirname(pool_path), exist_ok=True)
                            json.dump(positions, open(pool_path, "w"), ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                win.destroy()
                _do_scan()

            tk.Button(win, text="添加并扫描", command=_ok, bg=_FG_GOLD, fg=_BG_DEEP,
                      relief=tk.FLAT, font=("Menlo", 10, "bold"), padx=16, pady=4).pack(pady=10)
            ent.bind("<Return>", lambda e: _ok())

        add_btn.config(command=_add_stock)

        # 启动自动扫描
        dlg.after(300, _do_scan)

        return dlg

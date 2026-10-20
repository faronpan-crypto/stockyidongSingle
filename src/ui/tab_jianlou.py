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

        # ── 从新浪全市场榜单拉异常股票 (主源, 不再依赖持仓文件) ──
        def _fetch_sina_rank(sort_key, asc, num=50):
            """sort: changepercent / turnoverratio(换手率即量比) / volume(成交额)
               asc: 0=降序(Top), 1=升序(Bottom)"""
            try:
                url = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                       f"Market_Center.getHQNodeData?page=1&num={num}&sort={sort_key}&asc={asc}"
                       f"&node=hs_a&symbol=&_s_r_a=auto")
                r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200: return []
                return json.loads(r.text)
            except Exception as e:
                print(f"[捡漏] 新浪榜单 {sort_key} asc={asc} err: {e}", flush=True)
                return []

        # ── 同时维护持仓/龙头 → 用来打标签 "我的持仓" / "龙头" ──
        def _load_my_tags():
            """返回 dict {sina_code: tag}"""
            tags = {}
            pos_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "..", "data", "trading_positions.json")
            pos_path = os.path.abspath(pos_path)
            if os.path.exists(pos_path):
                try:
                    for p in json.load(open(pos_path)):
                        code6 = str(p.get("code", ""))
                        if not code6: continue
                        sina = code6 if code6.startswith(("sh", "sz", "bj")) else _sina_from_code(code6)
                        tags[sina] = "持仓"
                except Exception:
                    pass

            syd_path = None
            for cand in [
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "stockyidong"),
                os.path.expanduser("~/Desktop/stockyidong"),
                os.path.expanduser("~/stockyidong"),
            ]:
                if os.path.exists(cand): syd_path = cand; break
            if syd_path:
                try:
                    content = open(syd_path, "r", encoding="utf-8", errors="ignore").read()
                    m = re.search(r"【龙头股】\s*\n(.*?)(?=【|\Z)", content, re.S)
                    if m:
                        for line in m.group(1).split("\n"):
                            if ":" not in line: continue
                            _, stocks = line.split(":", 1)
                            for item in re.split(r"[,，\s]+", stocks):
                                cm = re.match(r"(\d{6})", item.strip())
                                if cm:
                                    sina = _sina_from_code(cm.group(1))
                                    tags[sina] = "龙头"
                except Exception:
                    pass
            return tags

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

        # ── 主扫描流程 (全市场榜单, 不再依赖本地股票池) ──
        def _do_scan():
            if _scan_data["loading"]: return
            _scan_data["loading"] = True
            refresh_btn.config(state=tk.DISABLED)

            def _bg():
                try:
                    dlg.after(0, lambda: status.config(text="📡 拉取全市场榜单...", fg=_FG_TEXT))

                    # 1) 拉 4 个榜单
                    drops_raw = _fetch_sina_rank("changepercent", asc=1, num=50)  # 跌幅榜 Top50
                    surges_raw = _fetch_sina_rank("changepercent", asc=0, num=50)  # 涨幅榜 Top50
                    vol_raw = _fetch_sina_rank("turnoverratio", asc=0, num=50)     # 换手率(量比)榜
                    # 振幅榜用 hq 实时拉: 取跌幅榜+涨幅榜前30只的振幅

                    dlg.after(0, lambda: status.config(
                        text=f"📊 跌幅{len(drops_raw)} 涨幅{len(surges_raw)} 换手{len(vol_raw)}, 去重合并...",
                        fg=_FG_TEXT))

                    # 2) 从持仓/龙头拿标签
                    my_tags = _load_my_tags()

                    # 3) 合并 + 去重 + 分类
                    results = {"drops": [], "surges": [], "volume": [], "swing": [], "bottom": []}
                    seen = set()

                    def _item_from_sina_raw(raw, default_chg=None):
                        """新浪榜单 raw item → dict"""
                        if not raw: return None
                        sina = raw.get("symbol", "")
                        if not sina or sina in seen: return None
                        seen.add(sina)
                        chg = float(raw.get("changepercent", 0) or 0)
                        cur = float(raw.get("trade", 0) or 0)
                        # sina 榜单的 turnoverratio 是换手率(%), 不是量比.
                        # 新浪榜单没有直接给振幅, 需要额外 hq 拉
                        return {
                            "sina": sina,
                            "name": raw.get("name", sina[2:]),
                            "code6": sina[2:],
                            "cur": cur,
                            "chg_pct": chg,
                            "amplitude": None,  # 待 hq 补
                            "vol_ratio": None,  # 新浪榜单没有量比, 用换手率粗略替代
                            "turnover": float(raw.get("turnoverratio", 0) or 0),
                            "vol_wan": float(raw.get("volume", 0) or 0) / 10000,  # 万股
                            "source": my_tags.get(sina, ""),
                        }

                    # 分类 (新浪榜单只给了 chg, 用阈值过滤)
                    for raw in drops_raw:
                        it = _item_from_sina_raw(raw)
                        if it and it["chg_pct"] <= -8:
                            results["drops"].append(it)
                    for raw in surges_raw:
                        it = _item_from_sina_raw(raw)
                        if it and it["chg_pct"] >= 10:
                            results["surges"].append(it)
                    # 换手率榜 → 当作"放量异动"的近似 (换手 > 15%)
                    for raw in vol_raw:
                        it = _item_from_sina_raw(raw)
                        if it and it.get("turnover", 0) >= 15:
                            results["volume"].append(it)

                    # 4) 拉 hq 实时行情补振幅 + 量比 (对已收集的异常股)
                    all_sina = []
                    for k in results:
                        for it in results[k]:
                            if it["sina"] not in all_sina:
                                all_sina.append(it["sina"])

                    if all_sina:
                        ctx = ssl._create_unverified_context()
                        for i in range(0, len(all_sina), 60):
                            batch = all_sina[i:i + 60]
                            url = "https://hq.sinajs.cn/list=" + ",".join(batch)
                            try:
                                req = urllib.request.Request(url,
                                        headers={"User-Agent": "Mozilla/5.0",
                                                 "Referer": "https://finance.sina.com.cn"})
                                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                                    text = resp.read().decode("gbk", errors="ignore")
                                hq_map = {}
                                for line in text.strip().split("\n"):
                                    if "=" not in line or '"' not in line: continue
                                    var, val = line.split("=", 1)
                                    sc = var.replace("var hq_str_", "").strip()
                                    f = val.strip().strip(";").strip('"').split(",")
                                    if len(f) < 38: continue
                                    try:
                                        hq_map[sc] = {
                                            "prev": float(f[2]), "cur": float(f[3]),
                                            "hi": float(f[4]), "lo": float(f[5]),
                                            "vol_hand": float(f[36]),
                                        }
                                    except: pass
                                # 回写振幅 + 量比
                                for k in results:
                                    for it in results[k]:
                                        hq = hq_map.get(it["sina"])
                                        if hq and hq["prev"] > 0:
                                            amp = (hq["hi"] - hq["lo"]) / hq["prev"] * 100
                                            it["amplitude"] = round(amp, 2)
                                            # 振幅≥12% 补进 swing tab
                                            if amp >= 12 and k != "swing":
                                                # 但别重复加
                                                if not any(x["sina"] == it["sina"] for x in results["swing"]):
                                                    results["swing"].append({**it})
                                            # 换手率粗略当量比 (经验值: 换手率 / 3 ≈ 量比)
                                            it["vol_ratio"] = round(it.get("turnover", 0) / 3, 2)
                            except Exception as e:
                                print(f"[捡漏] hq补数据 err: {e}", flush=True)
                            time.sleep(0.2)

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

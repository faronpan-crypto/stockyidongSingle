"""东方财富 Choice 金融数据弹窗 Mixin

核心功能:
  - 🏒 涨停/跌停/连板股池 (东方财富源)
  - 🐉 龙虎榜每日明细
  - 📊 宏观数据 (GDP/CPI/PMI)
  - 💰 国债收益率曲线
  - 📈 财务摘要 (同花顺源)
  - 🎯 妙想 MCP 一键查询 (需 API key)

数据源优先级:
  1. 妙想 MCP (mxapi.eastmoney.com) — 用户填 EASTMONEY_APIKEY
  2. 妙想 Skills (mkapi2.dfcfs.com) — 用户填 apikey
  3. akshare 公开数据源 (无需 key)
"""
from __future__ import annotations

import json
import os
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

import requests

try:
    import akshare as ak
except ImportError:
    ak = None


# ── 妙想 MCP endpoint ──
MIAOXIANG_MCP_URL = "https://mxapi.eastmoney.com/mxds/mcp"
MIAOXIANG_SKILLS_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"

# API key 存储 (用户填了就持久化)
_CHOICE_KEY_PATH = os.path.expanduser("~/.choice_apikey.json")

import re


def _clean_choice_key(raw: str) -> str:
    """从用户粘贴的任意文本中提取真正的 API Key
    
    用户常把整行 'API Key 查看\n您的专属 API Key\nem_xxx' 复制进来,
    这里用正则精确提取常见格式的 token:
      - em_xxx   (妙想 Skills API)
      - mkt_xxx  (妙想 MCP)  
      - 纯 hex 40+ 位 token
    """
    if not raw:
        return ""
    raw = raw.strip()
    # 1. em_ / mkt_ 开头
    for prefix in ("em_", "mkt_"):
        m = re.search(rf'({prefix}[a-zA-Z0-9_\-]+)', raw)
        if m:
            return m.group(1)
    # 2. 纯 hex 32+ 位
    m = re.search(r'([a-f0-9]{32,})', raw)
    if m:
        return m.group(1)
    # 3. 兜底: 取最后一个单词 (用户直接粘贴 key 时)
    tokens = re.findall(r'[a-zA-Z0-9_\-]{16,}', raw)
    if tokens:
        return tokens[-1]
    return re.sub(r'[^a-zA-Z0-9_\-]', '', raw)


def _load_apikey() -> dict:
    try:
        data = json.loads(open(_CHOICE_KEY_PATH).read())
        # 自动清理已存的旧 key (兼容之前带垃圾的)
        if data.get("skills_apikey"):
            data["skills_apikey"] = _clean_choice_key(data["skills_apikey"])
        if data.get("mx_apikey"):
            data["mx_apikey"] = _clean_choice_key(data["mx_apikey"])
        return data
    except Exception:
        return {}


def _save_apikey(data: dict):
    try:
        cleaned = {k: _clean_choice_key(v) for k, v in data.items() if v}
        open(_CHOICE_KEY_PATH, "w").write(json.dumps(cleaned))
    except Exception:
        pass


def _mask_key(k: str) -> str:
    """只显示前 10 位 + ***"""
    if not k:
        return ""
    return k[:10] + "***" if len(k) > 10 else k + "***"


class ChoiceMixin:
    """东方财富 Choice / 妙想 数据弹窗"""

    # 📋 功能清单
    _CHOICE_FEATURES = [
        ("🏒 涨停股池", "zt_pool"),
        ("🐉 龙虎榜明细", "lhb"),
        ("📊 宏观·GDP", "gdp"),
        ("📊 宏观·CPI", "cpi"),
        ("📊 宏观·PMI", "pmi"),
        ("💰 国债收益率", "bond_yield"),
        ("📈 个股财务摘要", "financial"),
        ("🧠 妙想 AI 查询", "miaoxiang"),
    ]

    # 📋 快捷模板 (妙想 AI 用)
    _CHOICE_TEMPLATES = [
        "宁德时代最新价和市值",
        "贵州茅台 2025 年三季报净利润",
        "今日涨停股票列表",
        "比亚迪和特斯拉 PE 对比",
        "半导体板块今日资金流向",
        "2026 年三季度 GDP 同比增速",
        "新能源汽车行业龙头排名",
        "北向资金今日净买入 TOP10",
    ]

    # ═══════════════════════════════════════════════════════════
    # 🎯 主入口
    # ═══════════════════════════════════════════════════════════

    def _show_choice_dialog(self):
        """🎯 东方财富 Choice / 妙想 弹窗"""
        dlg = tk.Toplevel(self.root)
        dlg.title("🎯 Choice · 东方财富 / 妙想 金融数据")
        dlg.geometry("1420x840")
        dlg.transient(self.root)

        # ── 顶栏 ──
        topbar = ttk.Frame(dlg)
        topbar.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(topbar, text="🎯 Choice · 东方财富 / 妙想",
                 font=("", 13, "bold")).pack(side=tk.LEFT)
        self._choice_status = tk.StringVar(value="就绪")
        ttk.Label(topbar, textvariable=self._choice_status,
                  foreground="gray").pack(side=tk.LEFT, padx=12)

        # API Key 提示
        keys = _load_apikey()  # 自动清理旧 key
        has_key = bool(keys.get("mx_apikey") or keys.get("skills_apikey"))
        real_key = keys.get("skills_apikey") or ""
        if has_key and real_key:
            key_hint = f"妙想 API Key: ✅ {_mask_key(real_key)}"
        elif has_key:
            key_hint = "妙想 API Key: ✅ 已配置"
        else:
            key_hint = "妙想 API Key: ⚠️ 未配置 (可用公开 akshare)"
        ttk.Label(topbar, text=key_hint,
                  foreground="#FF6600").pack(side=tk.RIGHT, padx=12)
        ttk.Button(topbar, text="🔑 配置 API Key",
                   command=lambda: self._choice_config_apikey(dlg)).pack(side=tk.RIGHT)

        # ── 三列 PanedWindow ──
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ═══ 左列: 功能入口 + 模板 ═══
        left_frame = ttk.Frame(pw, width=230)
        pw.add(left_frame, weight=0)

        tk.Label(left_frame, text="🔍 功能",
                 font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(4, 4))

        self._choice_feat_lb = tk.Listbox(left_frame, selectmode=tk.SINGLE,
                                           font=("", 11), activestyle="dotbox",
                                           height=10)
        for label, _ in self._CHOICE_FEATURES:
            self._choice_feat_lb.insert(tk.END, label)
        self._choice_feat_lb.pack(fill=tk.X, padx=4)
        self._choice_feat_lb.bind("<<ListboxSelect>>",
                                   lambda e: self._choice_on_feat_select())

        # 日期选择
        tk.Label(left_frame, text="📅 日期",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        today = time.strftime("%Y%m%d")
        self._choice_date_var = tk.StringVar(value=today)
        date_frame = ttk.Frame(left_frame)
        date_frame.pack(fill=tk.X, padx=4)
        ttk.Entry(date_frame, textvariable=self._choice_date_var,
                   font=("", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(date_frame, text="今日", width=4,
                    command=lambda: self._choice_date_var.set(today)).pack(side=tk.LEFT, padx=2)

        # 代码输入 (个股查询用)
        tk.Label(left_frame, text="🏷️ 股票代码",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(8, 2))
        self._choice_code_var = tk.StringVar(value="600519")
        ttk.Entry(left_frame, textvariable=self._choice_code_var,
                  font=("", 10)).pack(fill=tk.X, padx=4)

        # 模板
        tk.Label(left_frame, text="📋 妙想 AI 模板",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 2))
        for tpl in self._CHOICE_TEMPLATES[:5]:
            btn = tk.Button(left_frame, text=tpl, cursor="hand2", relief=tk.FLAT,
                            fg="#FF6600", font=("", 9), anchor="w", pady=1,
                            command=lambda tt=tpl: self._choice_preset(tt))
            btn.pack(anchor="w", padx=6)

        # 妙想 Web 入口
        sep = ttk.Separator(left_frame, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, padx=6, pady=(10, 4))
        tk.Label(left_frame, text="🔗 妙想 Web",
                 font=("", 10, "bold")).pack(anchor="w", padx=6)
        for label, url in [
            ("💎 Choice 终端", "https://choice.eastmoney.com/"),
            ("🧠 妙想 MCP", "https://choice.eastmoney.com/mcp/"),
            ("📊 妙想 Skills", "https://ai.eastmoney.com/miaoxiang/"),
        ]:
            tk.Button(left_frame, text=label, cursor="hand2", relief=tk.FLAT,
                       fg="#FF6600", font=("", 9), anchor="w",
                       command=lambda u=url: webbrowser.open_new_tab(u))\
                .pack(anchor="w", padx=6)

        # ═══ 中列: 搜索框 + Notebook + Treeview ═══
        mid_frame = ttk.Frame(pw)
        pw.add(mid_frame, weight=3)

        search_frame = ttk.Frame(mid_frame)
        search_frame.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(search_frame, text="🔎", font=("", 12)).pack(side=tk.LEFT)
        self._choice_query_ent = ttk.Entry(search_frame, font=("", 12))
        self._choice_query_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._choice_query_ent.bind("<Return>", lambda e: self._choice_go())

        ttk.Button(search_frame, text="🧠 妙想 AI", width=10,
                    command=lambda: self._choice_do("miaoxiang")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🏒 涨停池", width=10,
                    command=lambda: self._choice_do("zt_pool")).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="🐉 龙虎榜", width=8,
                    command=lambda: self._choice_do("lhb")).pack(side=tk.LEFT, padx=2)

        self._choice_nb = ttk.Notebook(mid_frame)
        self._choice_nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        self._choice_list_tab = ttk.Frame(self._choice_nb)
        self._choice_nb.add(self._choice_list_tab, text="📋 数据列表")

        self._choice_ai_tab = ttk.Frame(self._choice_nb)
        self._choice_nb.add(self._choice_ai_tab, text="🧠 妙想 AI")

        self._choice_tree_frame = ttk.Frame(self._choice_list_tab)
        self._choice_tree_frame.pack(fill=tk.BOTH, expand=True)

        # ═══ 右列: 详情预览 ═══
        right_frame = ttk.Frame(pw, width=430)
        pw.add(right_frame, weight=2)

        ttk.Label(right_frame, text="📖 详情 / 提示",
                  font=("", 11, "bold")).pack(anchor="w", padx=6, pady=4)

        self._choice_detail_text = tk.Text(right_frame, wrap=tk.WORD,
                                           font=("TkDefaultFont", 10),
                                           background="#fff8e1", height=30)
        self._choice_detail_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._choice_detail_text.configure(state=tk.DISABLED)

        # 初始化: 自动加载涨停池
        dlg.after(100, lambda: (
            self._choice_feat_lb.selection_clear(0, tk.END),
            self._choice_feat_lb.selection_set(0),
            self._choice_do("zt_pool")
        ))

    # ── API Key 配置 ──

    def _choice_config_apikey(self, parent):
        """配置妙想 API Key 弹窗"""
        dlg = tk.Toplevel(parent)
        dlg.title("🔑 妙想 API Key 配置")
        dlg.geometry("560x400")
        dlg.transient(parent)
        dlg.grab_set()

        keys = _load_apikey()

        tk.Label(dlg, text="🧠 妙想 AI 查询需要 API Key",
                 font=("", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
        tk.Label(dlg, text="获取方式:\n"
                 "1. 打开 https://choice.eastmoney.com/mcp/\n"
                 "2. 登录后点击「查看 API Key」\n"
                 "3. 复制填入下方 (格式: mkt_xxx...)\n"
                 "💰 免费版每日 300 次, 会员版更多",
                 justify=tk.LEFT, foreground="#666",
                 font=("", 9)).pack(anchor="w", padx=12)

        frame1 = ttk.Frame(dlg)
        frame1.pack(fill=tk.X, padx=12, pady=8)
        tk.Label(frame1, text="妙想 Skills API Key:", width=20).pack(side=tk.LEFT)
        skills_var = tk.StringVar(value=keys.get("skills_apikey", ""))
        ttk.Entry(frame1, textvariable=skills_var, show="*", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        frame2 = ttk.Frame(dlg)
        frame2.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(frame2, text="妙想 MCP API Key:", width=20).pack(side=tk.LEFT)
        mcp_var = tk.StringVar(value=keys.get("mx_apikey", ""))
        ttk.Entry(frame2, textvariable=mcp_var, show="*", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _save():
            s = skills_var.get().strip()
            m = mcp_var.get().strip()
            if s and not s.startswith("mkt_"):
                if not tk.messagebox.askyesno("格式提示",
                    "妙想 Skills API Key 通常以 mkt_ 开头\n"
                    f"你当前输入的是: {s[:20]}...\n\n"
                    "确认保存?"):
                    return
            _save_apikey({"skills_apikey": s, "mx_apikey": m})
            tk.messagebox.showinfo("保存成功", "✅ API Key 已保存\n\n免费版每日 300 次\n打开弹窗右上角会显示「已配置」")
            dlg.destroy()

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(pady=12)

        def _test_key():
            s = skills_var.get().strip()
            if not s:
                tk.messagebox.showwarning("提示", "请先粘贴 API Key")
                return
            try:
                r = requests.post(
                    MIAOXIANG_SKILLS_URL,
                    json={"toolQuery": "A股今日成交量"},
                    headers={"Content-Type": "application/json", "apikey": s},
                    timeout=15,
                )
                j = r.json()
                if j.get("success"):
                    tk.messagebox.showinfo("✅ Key 有效", "API Key 验证通过, 妙想 AI 立即可用!")
                else:
                    msg = j.get("message", r.text[:200])
                    tk.messagebox.showerror("❌ Key 无效", f"服务器返回:\n{msg}")
            except Exception as e:
                tk.messagebox.showerror("❌ 网络错误", str(e)[:200])

        ttk.Button(btn_frame, text="🧪 测试 Key", command=_test_key, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="💾 保存", command=_save, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="❌ 取消", command=dlg.destroy, width=10).pack(side=tk.LEFT, padx=6)

    # ── 调度 ──

    def _choice_on_feat_select(self):
        sel = self._choice_feat_lb.curselection()
        if not sel: return
        _, mode = self._CHOICE_FEATURES[sel[0]]
        self._choice_do(mode)

    def _choice_preset(self, tpl: str):
        self._choice_query_ent.delete(0, tk.END)
        self._choice_query_ent.insert(0, tpl)
        self._choice_do("miaoxiang")

    def _choice_go(self):
        q = self._choice_query_ent.get().strip()
        if not q: return
        # 自动识别模式
        if any(k in q for k in ["最新价", "市值", "PE", "财报", "利润", "营收"]):
            self._choice_do("miaoxiang")
        else:
            self._choice_do("miaoxiang")

    def _choice_do(self, mode: str):
        """后台线程"""
        for w in self._choice_tree_frame.winfo_children():
            w.destroy()

        if mode == "miaoxiang":
            query = self._choice_query_ent.get().strip()
            if not query:
                self._choice_status.set("⚠️ 请输入问题")
                self._choice_set_detail("⚠️ 请在搜索框输入问题\n\n示例:\n  宁德时代最新价\n  比亚迪 PE 估值\n  今日涨停股票\n  半导体资金流向")
                return
            self._choice_nb.select(1)
            self._choice_status.set(f"⏳ 妙想 AI 思考: {query}")
            self._choice_set_detail(f"⏳ 正在通过妙想 Skills API 查询: {query}\n\n请稍候...")
        else:
            self._choice_nb.select(0)
            self._choice_status.set(f"⏳ 加载 {mode}...")

        def _bg():
            t0 = time.time()
            result = self._choice_fetch(mode)
            dt = time.time() - t0
            self.root.after(0, lambda: self._choice_render(mode, result, dt))

        threading.Thread(target=_bg, daemon=True).start()

    # ── 数据获取 ──

    def _choice_fetch(self, mode: str) -> dict:
        """不同模式的数据获取"""
        if mode == "miaoxiang":
            return self._choice_query_miaoxiang()
        if ak is None:
            return {"ok": False, "error": "akshare 未安装"}
        try:
            if mode == "zt_pool":
                date = self._choice_date_var.get().strip() or time.strftime("%Y%m%d")
                df = ak.stock_zt_pool_em(date=date)
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "lhb":
                date = self._choice_date_var.get().strip() or time.strftime("%Y%m%d")
                df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "gdp":
                df = ak.macro_china_gdp()
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "cpi":
                df = ak.macro_china_cpi()
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "pmi":
                df = ak.macro_china_pmi()
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "bond_yield":
                df = ak.bond_china_yield(start_date="20240101",
                                          end_date=time.strftime("%Y%m%d"))
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
            elif mode == "financial":
                code = self._choice_code_var.get().strip() or "600519"
                df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
                return {"ok": True, "data": df.to_dict("records"), "headers": list(df.columns)}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}
        return {"ok": False, "error": f"未知模式: {mode}"}

    def _choice_query_miaoxiang(self) -> dict:
        """调妙想 Skills API"""
        keys = _load_apikey()
        apikey = (keys.get("skills_apikey") or os.getenv("EASTMONEY_APIKEY", "")).strip()
        query = self._choice_query_ent.get().strip()
        if not query:
            return {"ok": False, "error": "请输入查询问题"}
        if not apikey:
            return {"ok": False, "error": ("⚠️ 需要妙想 API Key\n\n"
                    "1. 点顶栏「🔑 配置 API Key」按钮\n"
                    "2. 打开 https://choice.eastmoney.com/mcp/ 获取\n"
                    "3. 免费版每日 300 次调用\n\n"
                    "💡 无 Key 时可用左列其他 akshare 功能 (涨停/龙虎榜/宏观)")}
        try:
            resp = requests.post(
                MIAOXIANG_SKILLS_URL,
                json={"toolQuery": query},
                headers={"Content-Type": "application/json",
                         "apikey": apikey},
                timeout=60,
            )
            j = resp.json()
            if j.get("success"):
                return {"ok": True, "ai_result": j}
            else:
                return {"ok": False, "error": f"妙想 API 错误: {j.get('message', resp.text[:200])}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    # ── 渲染 ──

    def _choice_render(self, mode: str, result: dict, dt: float):
        if mode == "miaoxiang":
            self._choice_render_ai(result, dt)
            return

        if not result.get("ok"):
            self._choice_status.set(f"❌ 失败: {result.get('error', '?')[:60]}")
            self._choice_set_detail(f"❌ 加载失败\n\n{result.get('error', '未知错误')}\n\n"
                                     f"💡 建议:\n"
                                     f"• 检查东方财富是否被限流 (稍后重试)\n"
                                     f"• 确认 akshare 版本最新\n"
                                     f"• 妙想 AI 查询需先配置 API Key")
            return

        data = result.get("data") or []
        headers = result.get("headers") or []

        # 智能选列: 最多 8 列
        display_headers = self._choice_pick_headers(headers, mode)

        tree = ttk.Treeview(self._choice_tree_frame, columns=display_headers,
                            show="headings", height=min(28, len(data)))
        widths = self._choice_auto_width(display_headers)
        for h, w in zip(display_headers, widths):
            tree.heading(h, text=h)
            anchor = "center" if any(x in h for x in ("序号", "涨跌", "涨幅", "市值", "价格", "量", "额", "率")) else "w"
            tree.column(h, width=w, anchor=anchor)

        # 标签
        if mode == "zt_pool":
            tree.tag_configure("zt", background="#ffebee", foreground="#c62828")
        elif mode == "lhb":
            tree.tag_configure("buy", background="#ffebee", foreground="#c62828")
            tree.tag_configure("sell", background="#e8f5e9", foreground="#2e7d32")

        for i, rec in enumerate(data):
            vals = []
            for h in display_headers:
                v = rec.get(h, "")
                if isinstance(v, float):
                    vals.append(f"{v:.2f}")
                else:
                    vals.append(str(v)[:22] if v else "")
            tag = ""
            if mode == "zt_pool":
                tag = "zt"
            elif mode == "lhb" and len(rec) > 3:
                # 龙虎榜净买
                for k in ("净买入额", "净买额", "净买入"):
                    if k in rec and isinstance(rec[k], (int, float)):
                        tag = "buy" if rec[k] >= 0 else "sell"
                        break
            tree.insert("", tk.END, values=vals, tags=(tag,) if tag else ())

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(self._choice_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(data):
                self._choice_show_detail(data[idx], mode)

        tree.bind("<<TreeviewSelect>>", _on_select)

        self._choice_status.set(f"✅ {mode}: {len(data)} 条 ({dt:.1f}s)")

    def _choice_render_ai(self, result: dict, dt: float):
        """妙想 AI 结果渲染"""
        self._choice_nb.select(1)
        for w in self._choice_ai_tab.winfo_children():
            w.destroy()

        if not result.get("ok"):
            self._choice_status.set("❌ AI 查询失败")
            self._choice_set_detail(result.get("error", "未知错误"))
            return

        j = result.get("ai_result") or {}
        txt = tk.Text(self._choice_ai_tab, wrap=tk.WORD, font=("", 11),
                       background="#fff3e0")
        txt.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # 解包妙想 Skills 返回
        rendered = self._choice_format_miaoxiang_resp(j)
        txt.insert("1.0", f"🧠 妙想 AI 查询结果\n\n{'='*40}\n\n{rendered}")
        txt.configure(state=tk.DISABLED)

        self._choice_status.set(f"✅ 妙想 AI 完成 ({dt:.1f}s)")
        self._choice_set_detail(f"📊 妙想 AI 返回\n\n耗时: {dt:.1f}s\n\n原始 JSON 已在上方展示")

    def _choice_format_miaoxiang_resp(self, j: dict) -> str:
        """妙想 Skills 返回格式化"""
        out = []
        data = j.get("data") or {}

        # 表格数据
        tables = data.get("dataTableDTOList") or []
        for t in tables:
            title = t.get("title", "")
            if title:
                out.append(f"📌 {title}")
                out.append("─" * 40)
            name_map = t.get("nameMap") or {}
            order = t.get("indicatorOrder") or []
            table = t.get("table") or {}
            head = table.get("headName") or table.get("headNameSub") or []
            for h in head[:8]:
                out.append(f"  📎 {h}")
            # 指标列
            for col in order[:6]:
                cn = name_map.get(col, col)
                vals = table.get(col, [])[:5]
                out.append(f"    {cn}: {', '.join(str(v) for v in vals)}")
            out.append("")

        # 文本回复
        reply = data.get("replyText") or data.get("text") or ""
        if reply:
            out.append("💬 文本回复:")
            out.append(reply[:2000])

        if not out:
            out.append(json.dumps(j, ensure_ascii=False, indent=2)[:3000])

        return "\n".join(out)

    # ── 详情 ──

    def _choice_show_detail(self, rec: dict, mode: str):
        lines = [f"📊 详情 (mode={mode})", "─" * 40]
        for k, v in rec.items():
            if v is None or v == "": continue
            s = str(v)
            if len(s) > 120: s = s[:120] + "..."
            lines.append(f"  {k}: {s}")
        self._choice_set_detail("\n".join(lines[:60]))

    def _choice_set_detail(self, text: str):
        self._choice_detail_text.configure(state=tk.NORMAL)
        self._choice_detail_text.delete("1.0", tk.END)
        self._choice_detail_text.insert("1.0", text)
        self._choice_detail_text.configure(state=tk.DISABLED)

    # ── 工具 ──

    def _choice_pick_headers(self, headers: list, mode: str) -> list:
        """根据模式选关键列"""
        if not headers: return []
        # 各模式关键列
        key_cols = {
            "zt_pool": ["序号", "代码", "名称", "涨跌幅", "最新价", "成交额", "封板资金", "换手率", "连板数"],
            "lhb": ["序号", "代码", "名称", "收盘价", "涨跌幅", "成交额", "净买入额", "买入总额", "卖出总额"],
            "gdp": ["季度", "GDP同比增长", "GDP环比增长", "GDP累计同比增长"],
            "cpi": ["月份", "全国-当月", "全国-同比增长", "全国-环比增长"],
            "pmi": ["月份", "制造业PMI", "非制造业PMI"],
            "bond_yield": ["曲线名称", "日期", "1年", "3年", "5年", "10年"],
            "financial": ["报告期", "净利润", "净利润同比增长率", "营业总收入", "营业总收入同比增长率", "基本每股收益", "ROE"],
        }
        wanted = key_cols.get(mode, [])
        picked = [h for h in wanted if h in headers]
        if len(picked) < 3:
            picked = headers[:8]
        return picked[:9]

    def _choice_auto_width(self, headers: list) -> list:
        widths = {"序号": 35, "代码": 70, "名称": 130, "日期": 80,
                  "收盘价": 70, "最新价": 70, "涨跌幅": 70, "成交额": 90,
                  "换手率": 70, "封板资金": 90, "连板数": 60, "净买入额": 90,
                  "买入总额": 90, "卖出总额": 90}
        return [widths.get(h, 100) for h in headers]

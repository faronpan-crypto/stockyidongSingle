"""📋 操盘面板 — 本地持仓管理 + 实时行情 + 模拟交易

⚠️ 所有交易都是本地模拟, 不会真实下单!
真实交易需要券商 API 或同花顺 easytrader (仅 Windows).
"""
import os, json, time, threading, traceback, urllib.request, ssl
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

POS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trading_positions.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trading_log.json")

_EM_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}


def _load_positions():
    try:
        if os.path.exists(POS_FILE):
            with open(POS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[📋操盘] 读取持仓失败: {e}")
    return []


def _save_positions(positions):
    os.makedirs(os.path.dirname(POS_FILE), exist_ok=True)
    with open(POS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def _load_log():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return []


def _save_log(log):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _batch_fetch_quotes(codes):
    """批量拉新浪实时行情. codes: ['sh600519', 'sz300750', ...]
    返回 {code: {'name': str, 'cur': float, 'pct': float, 'date': str}}"""
    if not codes:
        return {}
    ctx = ssl._create_unverified_context()
    result = {}
    for bi in range(0, len(codes), 40):
        batch = codes[bi:bi + 40]
        try:
            url = f"https://hq.sinajs.cn/list={','.join(batch)}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=_EM_HDR),
                                        timeout=8, context=ctx) as resp:
                text = resp.read().decode("gbk", errors="ignore")
            for line in text.strip().split("\n"):
                if "=" not in line:
                    continue
                code = line.split("=")[0].replace("var hq_str_", "")
                f = line.split('"')[1].split(",")
                if len(f) < 32:
                    continue
                try:
                    cur = float(f[3])
                    prev = float(f[2])
                    pct = round((cur - prev) / prev * 100, 2) if prev > 0 else 0
                    result[code] = {"name": f[0][:8], "cur": cur, "pct": pct, "date": f[30]}
                except:
                    pass
        except Exception as e:
            print(f"[📋操盘] 行情拉取失败 batch {bi}: {e}")
        time.sleep(0.02)
    return result


def _to_sina_code(code6):
    """6位数字 → sh600519 / sz300750 / sh688xxx 等"""
    code6 = str(code6).strip()
    if not code6.isdigit() or len(code6) != 6:
        return None
    if code6.startswith(("6", "5")):
        return f"sh{code6}"
    if code6.startswith(("0", "3")):
        return f"sz{code6}"
    if code6.startswith(("4", "8")):
        return f"bj{code6}"
    return f"sz{code6}"


class CaochuanMixin:
    """📋操盘面板"""

    def _show_caochuan_panel(self):
        win = tk.Toplevel(self.root)
        win.title("📋 操盘面板 (模拟)")
        win.geometry("1100x660")
        win.attributes("-topmost", True)

        # === 顶部风险提示 ===
        risk = tk.Label(win, text="⚠️ 模拟交易 — 不会真实下单",
                        bg="#fff3cd", fg="#856404", font=("TkDefaultFont", 9))
        risk.pack(fill=tk.X, padx=8, pady=(4, 2))

        # === 工具栏 (拆两行避免挤压) ===
        tb1 = ttk.Frame(win)
        tb1.pack(fill=tk.X, padx=8, pady=1)
        ttk.Button(tb1, text="➕加", width=5, command=lambda: self._cc_add_position(tree, quote_map, _log_view)).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb1, text="🗑️删", width=5, command=lambda: self._cc_delete_selected(tree, _log_view)).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb1, text="✏️改", width=5, command=lambda: self._cc_edit_qty(tree, quote_map, _log_view)).pack(side=tk.LEFT, padx=1)
        ttk.Separator(tb1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(tb1, text="全部卖", width=6, command=lambda: self._cc_bulk_sell(tree, quote_map, _log_view, "全部")).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb1, text="盈利卖", width=6, command=lambda: self._cc_bulk_sell(tree, quote_map, _log_view, "盈利")).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb1, text="亏损卖", width=6, command=lambda: self._cc_bulk_sell(tree, quote_map, _log_view, "亏损")).pack(side=tk.LEFT, padx=1)
        ttk.Separator(tb1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        ttk.Button(tb1, text="🔄刷", width=4, command=lambda: self._cc_refresh_quotes(tree, quote_map)).pack(side=tk.LEFT, padx=1)
        ttk.Button(tb1, text="💾存", width=4, command=lambda: (_save_positions(_cc_positions), messagebox.showinfo("保存", "已保存持仓", parent=win))).pack(side=tk.LEFT, padx=1)
        ttk.Separator(tb1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        # 百分比买卖放第一行最右
        self._cc_pct_var = tk.StringVar(value="50")
        ttk.Label(tb1, text="%:").pack(side=tk.RIGHT, padx=(0, 1))
        ttk.Button(tb1, text="卖出%", width=6, command=lambda: self._cc_pct_trade(tree, quote_map, _log_view, "sell")).pack(side=tk.RIGHT, padx=1)
        ttk.Button(tb1, text="买入%", width=6, command=lambda: self._cc_pct_trade(tree, quote_map, _log_view, "buy")).pack(side=tk.RIGHT, padx=1)
        ttk.Entry(tb1, textvariable=self._cc_pct_var, width=4).pack(side=tk.RIGHT, padx=1)

        # === 账户概览 ===
        summary = tk.LabelFrame(win, text="账户概览", padding=2)
        summary.pack(fill=tk.X, padx=8, pady=2)
        self._cc_total_var = tk.StringVar(value="市值: 0")
        self._cc_pnl_var = tk.StringVar(value="总盈亏: 0")
        self._cc_pnl_pct_var = tk.StringVar(value="盈亏比: 0%")
        self._cc_count_var = tk.StringVar(value="持仓: 0")
        ttk.Label(summary, textvariable=self._cc_total_var, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, padx=8)
        ttk.Label(summary, textvariable=self._cc_pnl_var, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=1, padx=8)
        ttk.Label(summary, textvariable=self._cc_pnl_pct_var, font=("TkDefaultFont", 9, "bold")).grid(row=0, column=2, padx=8)
        ttk.Label(summary, textvariable=self._cc_count_var, font=("TkDefaultFont", 9)).grid(row=0, column=3, padx=8)

        # === 主区域: 持仓表格 + 交易日志 ===
        main = ttk.Panedwindow(win, orient=tk.VERTICAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=3)

        # 持仓表格 (列宽更紧凑)
        pos_frame = ttk.Frame(main)
        cols = ("code", "name", "qty", "cost", "cur", "mv", "pnl", "pnl%", "today%", "date")
        tree = ttk.Treeview(pos_frame, columns=cols, show="headings", selectmode="extended", height=12)
        for c, t, w in [
            ("code", "代码", 70), ("name", "名称", 70),
            ("qty", "持仓", 55), ("cost", "成本", 60),
            ("cur", "现价", 60), ("mv", "市值", 75),
            ("pnl", "盈亏", 80), ("pnl%", "盈亏%", 65),
            ("today%", "今日%", 60), ("date", "数据日", 75),
        ]:
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor=tk.CENTER, stretch=False)
        vsb = ttk.Scrollbar(pos_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 日志
        log_frame = ttk.LabelFrame(main, text="交易日志", padding=2)
        _log_view = tk.Text(log_frame, height=6, font=("Menlo", 9))
        _log_view.pack(fill=tk.BOTH, expand=True)
        _log_view.insert("end", "🟢 操盘面板已启动\n")
        for rec in _load_log()[-20:]:
            _log_view.insert("end", rec + "\n")
        _log_view.see("end")

        main.add(pos_frame, weight=3)
        main.add(log_frame, weight=1)

        # === 状态 ===
        self._cc_positions = _load_positions()  # [{code6, sina, name, qty, cost, buy_date}]
        quote_map = {}  # {sina_code: {name, cur, pct, date}}

        # === 刷新函数 ===
        def _render():
            tree.delete(*tree.get_children())
            total_mv = 0
            total_pnl = 0
            for pos in self._cc_positions:
                sina = pos.get("sina") or _to_sina_code(pos["code6"])
                q = quote_map.get(sina, {})
                cur = q.get("cur", 0) or pos.get("last_cur", 0)
                name = q.get("name") or pos.get("name", "?")
                pos["sina"] = sina
                pos["name"] = name
                if cur > 0:
                    pos["last_cur"] = cur
                qty = pos["qty"]
                cost = pos["cost"]
                mv = cur * qty if cur > 0 else 0
                pnl = (cur - cost) * qty if cur > 0 else 0
                pnl_pct = (cur - cost) / cost * 100 if cost > 0 and cur > 0 else 0
                total_mv += mv
                total_pnl += pnl
                pct_today = q.get("pct", 0)
                date = q.get("date", "-")
                tags = ()
                if pnl > 0:
                    tags = ("profit",)
                elif pnl < 0:
                    tags = ("loss",)
                tree.insert("", "end", iid=pos["code6"], values=(
                    pos["code6"], name, f"{qty}", f"{cost:.2f}",
                    f"{cur:.2f}" if cur > 0 else "-", f"{mv:.0f}" if mv else "-",
                    f"{pnl:+.0f}" if cur > 0 else "-", f"{pnl_pct:+.2f}%" if cur > 0 else "-",
                    f"{pct_today:+.2f}%" if pct_today else "-", date,
                ), tags=tags)
            tree.tag_configure("profit", foreground="#d32f2f")
            tree.tag_configure("loss", foreground="#388e3c")

            self._cc_total_var.set(f"持仓市值: {total_mv:,.0f}")
            self._cc_pnl_var.set(f"总盈亏: {total_pnl:+,.0f}")
            total_cost = sum(p["qty"] * p["cost"] for p in self._cc_positions)
            pct_str = f"{total_pnl / total_cost * 100:+.2f}%" if total_cost > 0 else "0%"
            self._cc_pnl_pct_var.set(f"盈亏比: {pct_str}")
            self._cc_count_var.set(f"持仓数量: {len(self._cc_positions)}")

        def _bg_refresh():
            codes = [p.get("sina") or _to_sina_code(p["code6"]) for p in self._cc_positions]
            codes = [c for c in codes if c]
            if not codes:
                self.root.after(0, _render)
                return
            new_q = _batch_fetch_quotes(codes)
            quote_map.update(new_q)
            self.root.after(0, _render)

        # 初始化 + 后台拉行情
        _render()
        threading.Thread(target=_bg_refresh, daemon=True).start()

        # 定时刷新 (盘中每15秒, 其他每60秒)
        def _schedule():
            try:
                threading.Thread(target=_bg_refresh, daemon=True).start()
            except:
                pass
            win.after(15000, _schedule)
        win.after(2000, _schedule)

        # 关闭时保存
        def _on_close():
            _save_positions(self._cc_positions)
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", _on_close)

        self._cc_tree = tree
        self._cc_quote_map = quote_map
        self._cc_log_view = _log_view
        self._cc_render = _render
        self._cc_bg_refresh = _bg_refresh

    # ============ 操作方法 ============

    def _cc_log(self, text):
        try:
            self._cc_log_view.insert("end", text + "\n")
            self._cc_log_view.see("end")
            # 持久化
            log = _load_log()
            log.append(text)
            if len(log) > 200:
                log = log[-200:]
            _save_log(log)
        except:
            pass

    def _cc_add_position(self, tree, quote_map, log_view):
        code6 = simpledialog.askstring("加持仓", "输入6位股票代码:", parent=self._cc_tree.winfo_toplevel())
        if not code6 or not code6.isdigit() or len(code6) != 6:
            return
        qty = simpledialog.askinteger("加持仓", f"买入股数 (必须100整数):", parent=self._cc_tree.winfo_toplevel(), minvalue=100)
        if not qty:
            return
        cost = simpledialog.askfloat("加持仓", f"成本价:", parent=self._cc_tree.winfo_toplevel())
        if not cost or cost <= 0:
            return
        # 同名则累加
        for p in self._cc_positions:
            if p["code6"] == code6:
                total_qty = p["qty"] + qty
                p["cost"] = round((p["cost"] * p["qty"] + cost * qty) / total_qty, 3)
                p["qty"] = total_qty
                self._cc_log(f"🟰 加仓 {code6} {qty}股 @ {cost:.2f}, 合计{total_qty}股, 平均成本{p['cost']:.2f}")
                break
        else:
            sina = _to_sina_code(code6)
            self._cc_positions.append({
                "code6": code6, "sina": sina, "name": "",
                "qty": qty, "cost": cost, "buy_date": time.strftime("%Y-%m-%d %H:%M"),
            })
            self._cc_log(f"🟢 新买入 {code6} {qty}股 @ {cost:.2f}")
        _save_positions(self._cc_positions)
        self._cc_bg_refresh()

    def _cc_delete_selected(self, tree, quote_map, log_view):
        sel = tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("确认", f"删除选中 {len(sel)} 条持仓?", parent=self._cc_tree.winfo_toplevel()):
            return
        for code6 in sel:
            self._cc_positions = [p for p in self._cc_positions if p["code6"] != code6]
            self._cc_log(f"🗑️ 删除持仓 {code6}")
        _save_positions(self._cc_positions)
        self._cc_bg_refresh()

    def _cc_edit_qty(self, tree, quote_map, log_view):
        sel = tree.selection()
        if len(sel) != 1:
            messagebox.showinfo("提示", "请选中1条持仓", parent=self._cc_tree.winfo_toplevel())
            return
        pos = next((p for p in self._cc_positions if p["code6"] == sel[0]), None)
        if not pos:
            return
        new_qty = simpledialog.askinteger("改数量", f"{pos['code6']} 当前 {pos['qty']}股, 新数量:",
                                          parent=self._cc_tree.winfo_toplevel(), initialvalue=pos["qty"], minvalue=0)
        if new_qty is None:
            return
        if new_qty == 0:
            self._cc_positions = [p for p in self._cc_positions if p["code6"] != pos["code6"]]
            self._cc_log(f"🗑️ 清仓 {pos['code6']}")
        else:
            pos["qty"] = new_qty
            self._cc_log(f"✏️ {pos['code6']} 数量→{new_qty}")
        _save_positions(self._cc_positions)
        self._cc_bg_refresh()

    def _cc_bulk_sell(self, tree, quote_map, log_view, mode):
        """批量卖出: 全部/盈利/亏损"""
        if not self._cc_positions:
            return
        targets = []
        for p in self._cc_positions:
            q = quote_map.get(p.get("sina") or _to_sina_code(p["code6"]), {})
            cur = q.get("cur", 0) or p.get("last_cur", 0)
            if cur <= 0:
                continue
            pnl_pct = (cur - p["cost"]) / p["cost"] * 100
            if mode == "全部":
                targets.append((p, cur, pnl_pct))
            elif mode == "盈利" and pnl_pct > 0:
                targets.append((p, cur, pnl_pct))
            elif mode == "亏损" and pnl_pct < 0:
                targets.append((p, cur, pnl_pct))
        if not targets:
            messagebox.showinfo("提示", f"没有符合「{mode}」条件的持仓", parent=self._cc_tree.winfo_toplevel())
            return
        total_pnl = sum((cur - p["cost"]) * p["qty"] for p, cur, _ in targets)
        if not messagebox.askyesno("确认",
                                    f"批量卖出「{mode}」{len(targets)}只, 预估盈亏 {total_pnl:+,.0f} 元\n" +
                                    "\n".join(f"  {p['code6']} {p.get('name','?')} {p['qty']}股 @{cur:.2f} ({pct:+.1f}%)"
                                              for p, cur, pct in targets),
                                    parent=self._cc_tree.winfo_toplevel()):
            return
        codes_sold = {p["code6"] for p, _, _ in targets}
        self._cc_positions = [p for p in self._cc_positions if p["code6"] not in codes_sold]
        self._cc_log(f"🔴 批量卖出「{mode}」{len(targets)}只, 总盈亏 {total_pnl:+,.0f}元")
        _save_positions(self._cc_positions)
        self._cc_bg_refresh()

    def _cc_pct_trade(self, tree, quote_map, log_view, direction):
        """对选中持仓按百分比买/卖"""
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请选中1条或多条持仓", parent=self._cc_tree.winfo_toplevel())
            return
        try:
            pct = float(self._cc_pct_var.get())
        except:
            messagebox.showerror("错误", "请输入有效百分比", parent=self._cc_tree.winfo_toplevel())
            return
        if pct <= 0 or pct > 100:
            messagebox.showerror("错误", "百分比需在 0~100 之间", parent=self._cc_tree.winfo_toplevel())
            return
        for code6 in sel:
            pos = next((p for p in self._cc_positions if p["code6"] == code6), None)
            if not pos:
                continue
            sina = pos.get("sina") or _to_sina_code(pos["code6"])
            q = quote_map.get(sina, {})
            cur = q.get("cur", 0) or pos.get("last_cur", 0)
            if cur <= 0 and direction == "buy":
                # 买入时现价未知, 用成本价
                cur = pos["cost"]
            if cur <= 0:
                continue
            delta_qty = int(pos["qty"] * pct / 100 / 100) * 100  # 100整数
            if delta_qty <= 0:
                delta_qty = 100
            if direction == "sell":
                delta_qty = min(delta_qty, pos["qty"])
                if delta_qty < 100:
                    delta_qty = 100
                    if delta_qty > pos["qty"]:
                        delta_qty = pos["qty"]
                pos["qty"] -= delta_qty
                self._cc_log(f"🔴 卖出 {pos['code6']} {delta_qty}股 @{cur:.2f} ({pct:.0f}%), 剩余 {pos['qty']}股, 盈亏 {(cur - pos['cost']) * delta_qty:+,.0f}")
                if pos["qty"] <= 0:
                    self._cc_positions.remove(pos)
                    self._cc_log(f"🗑️ 清仓 {pos['code6']}")
            else:  # buy
                new_total = pos["qty"] + delta_qty
                pos["cost"] = round((pos["cost"] * pos["qty"] + cur * delta_qty) / new_total, 3)
                pos["qty"] = new_total
                self._cc_log(f"🟢 买入 {pos['code6']} {delta_qty}股 @{cur:.2f} ({pct:.0f}%), 合计 {new_total}股, 成本 {pos['cost']:.2f}")
        _save_positions(self._cc_positions)
        self._cc_bg_refresh()

    def _cc_refresh_quotes(self, tree, quote_map):
        threading.Thread(target=self._cc_bg_refresh, daemon=True).start()
        self._cc_log("🔄 手动刷新行情")


__all__ = ["CaochuanMixin"]

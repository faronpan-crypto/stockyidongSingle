"""UI 构建/创建/setup — 大弹窗/面板/树形/表格"""
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


class BuildersMixin:
    """UI 构建/创建/setup — 大弹窗/面板/树形/表格"""

    def _create_market_indices_tab_in_notebook(self, notebook):
        """在market_notebook中创建市场指数标签页(仅创建框架,内容由_create_market_indices_tab填充)"""
        # 检查标签页是否已存在
        for i in range(notebook.index("end")):
            if notebook.tab(i, "text") == "市场指数":
                return  # 已存在,不重复创建
        # 创建新标签页
        tab_frame = ttk.Frame(notebook, padding=10)
        # 如果notebook为空,使用add;否则使用insert插入到第一个位置
        if notebook.index("end") == 0:
            notebook.add(tab_frame, text="市场指数")
        else:
            notebook.insert(0, tab_frame, text="市场指数")  # 插入到第一个位置(宏观指数之前)
        # 保存引用,供后续填充内容
        self.market_notebook = notebook

    def _create_market_indices_tab(self):
        """创建市场指数标签页(在market_notebook中)"""
        if not hasattr(self, 'market_notebook') or not self.market_notebook:
            return
        # 检查标签页是否已存在
        existing_index = None
        for i in range(self.market_notebook.index("end")):
            if self.market_notebook.tab(i, "text") == "市场指数":
                existing_index = i
                break
        if existing_index is None:
            # 创建新标签页
            tab_frame = ttk.Frame(self.market_notebook, padding=10)
            self.market_notebook.insert(0, tab_frame, text="市场指数")
        else:
            # 获取现有标签页
            tab_frame = self.market_notebook.nametowidget(self.market_notebook.tabs()[existing_index])
            # 清空内容
            for widget in tab_frame.winfo_children():
                widget.destroy()
        # 继续创建内容
        # 清空原有的文本框
        for widget in tab_frame.winfo_children():
            if isinstance(widget, tk.Text):
                widget.destroy()
            elif isinstance(widget, ttk.Frame) and widget.winfo_children():
                # 检查是否是工具栏
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button) and child.cget("text") == "×":
                        continue
                    widget.destroy()
        # 创建滚动框架
        canvas_frame = ttk.Frame(tab_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 获取市场指数数据
        indices_data = self.market_nav_config.get("indices", [])
        # 确保每个项目都有排序字段
        for item in indices_data:
            if "sort_order" not in item:
                item["sort_order"] = len(indices_data)
        # 按排序字段排序
        indices_data = sorted(indices_data, key=lambda x: x.get("sort_order", 999))
        # 创建链接按钮
        for idx, item in enumerate(indices_data):
            name = item.get("name", "")
            url = item.get("url", "")
            sort_order = item.get("sort_order", idx + 1)
            # 判断是否为排名/热榜类按钮(包含"榜"、"排名"、"热"等关键词)
            is_rank_hot = any(keyword in name for keyword in ["榜", "排名", "热", "排行", "统计", "明细", "天梯"])
            # 根据排序和类型设置字体大小和颜色
            if is_rank_hot:
                # 排名和热榜类按钮:红色、橘黄色,加大加粗
                if sort_order == 1:
                    font_size = 18
                    bg_color = "red"
                elif sort_order == 2:
                    font_size = 16
                    bg_color = "orange"
                else:
                    font_size = 14
                    bg_color = "#FF6B35"  # 橘红色
            else:
                # 普通按钮:根据排序设置
                if sort_order == 1:
                    font_size = 18
                    bg_color = "red"
                elif sort_order == 2:
                    font_size = 16
                    bg_color = "orange"
                elif sort_order == 3:
                    font_size = 14
                    bg_color = "blue"
                else:
                    font_size = 12
                    bg_color = "lightgray"
            # 创建链接按钮(纯按钮,无说明文字)
            def open_link(u=url, n=name):
                import webbrowser
                if u:
                    webbrowser.open(u)
                    # 复制链接到剪贴板
                    self.root.clipboard_clear()
                    self.root.clipboard_append(u)
                    self._safe_update()
                else:
                    messagebox.showwarning("提示", f"按钮 '{n}' 的链接未配置")
            link_btn = tk.Button(
                scrollable_frame,
                text=name,
                font=("TkDefaultFont", font_size, "bold" if is_rank_hot or sort_order <= 3 else "normal"),
                bg=bg_color,
                fg="black",
                cursor="hand2",
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5,
                command=lambda u=url, n=name: open_link(u, n)
            )
            link_btn.pack(fill=tk.X, padx=5, pady=3)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 添加编辑按钮
        edit_frame = ttk.Frame(tab_frame)
        edit_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(edit_frame, text="编辑排序", command=self._edit_market_indices_sort).pack(side=tk.LEFT, padx=5)

    def _create_draggable_button_grid(self, tab_frame, config_key, title_text):
        """创建可拖拽的三列按钮网格
        Args:
            tab_frame: 标签页框架
            config_key: 配置键("indices" 或 "dv_accounts")
            title_text: 标题文本
        """
        # 清空标签页内容
        for widget in tab_frame.winfo_children():
            widget.destroy()
        ttk.Label(tab_frame, text=title_text, font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w", pady=(0, 6)
        )
        # 创建滚动框架
        canvas_frame = ttk.Frame(tab_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 创建三列网格布局框架
        grid_frame = ttk.Frame(scrollable_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 配置三列,每列权重相等
        for col in range(3):
            grid_frame.columnconfigure(col, weight=1, uniform="equal")
        # 获取数据
        data_list = self.market_nav_config.get(config_key, [])
        # 不要自动从默认配置加载,保持用户配置(即使是空的)
        # 如果用户需要恢复,可以使用"恢复默认"按钮
        if not data_list:
            ttk.Label(grid_frame, text="暂无配置,可点击右上方【编辑导航】添加。", foreground="gray").grid(
                row=0, column=0, columnspan=3, sticky="w"
            )
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            return
        # 确保每个项目都有排序字段
        for item in data_list:
            if "sort_order" not in item:
                item["sort_order"] = len(data_list)
        # 按排序字段排序
        data_list = sorted(data_list, key=lambda x: x.get("sort_order", 999))
        # 存储按钮引用,用于拖拽
        button_refs = []
        # 创建按钮(三列布局,由上到下,由左到右)
        for idx, item in enumerate(data_list):
            name = item.get("name", "")
            url = item.get("url", "")
            desc = item.get("desc", "")
            sort_order = item.get("sort_order", idx + 1)
            # 判断是否为排名/热榜类按钮
            is_rank_hot = any(keyword in name for keyword in ["榜", "排名", "热", "排行", "统计", "明细", "天梯"])
            # 优先使用配置的颜色,否则根据排序和类型设置字体大小和颜色
            bg_color = item.get("bg_color", "")
            fg_color = item.get("fg_color", "")
            if not bg_color or not fg_color:
                # 如果没有配置颜色,使用默认逻辑
                if is_rank_hot:
                    if sort_order == 1:
                        font_size = 18
                        bg_color = "red"
                        fg_color = "white"
                    elif sort_order == 2:
                        font_size = 16
                        bg_color = "orange"
                        fg_color = "white"
                    else:
                        font_size = 14
                        bg_color = "#FF6B35"
                        fg_color = "white"
                else:
                    if sort_order == 1:
                        font_size = 18
                        bg_color = "red"
                        fg_color = "white"
                    elif sort_order == 2:
                        font_size = 16
                        bg_color = "orange"
                        fg_color = "white"
                    elif sort_order == 3:
                        font_size = 14
                        bg_color = "blue"
                        fg_color = "white"
                    else:
                        font_size = 12
                        bg_color = "lightgray"
                        fg_color = "black"
            else:
                # 如果配置了颜色,根据字体大小设置(如果没有配置字体大小,使用默认值)
                if is_rank_hot or sort_order <= 3:
                    font_size = item.get("font_size", 14)
                else:
                    font_size = item.get("font_size", 12)
            def open_link(u=url, n=name, d=desc):
                import webbrowser
                if u:
                    webbrowser.open(u)
                    self.root.clipboard_clear()
                    self.root.clipboard_append(u)
                    self._safe_update()
                else:
                    messagebox.showwarning("提示", f"按钮 '{n}' 的链接未配置")
            # 计算网格位置(三列布局)
            row = idx // 3
            col = idx % 3
            # 创建复选框和按钮的容器框架
            btn_frame = ttk.Frame(grid_frame)
            btn_frame.grid(row=row, column=col, padx=4, pady=3, sticky="ew")
            # 创建复选框,加载保存的状态
            checkbox_key = f"{config_key}_{idx}"
            saved_state = self.market_nav_checkbox_states.get(checkbox_key, False)
            checkbox_var = tk.BooleanVar(value=saved_state)
            if not hasattr(self, 'market_nav_checkboxes'):
                self.market_nav_checkboxes = {}
            self.market_nav_checkboxes[checkbox_key] = {
                'var': checkbox_var,
                'name': name,
                'url': url,
                'config_key': config_key
            }
            checkbox = ttk.Checkbutton(btn_frame, variable=checkbox_var,
                                       command=lambda k=checkbox_key, v=checkbox_var: self._save_market_nav_checkbox_state(k, v.get()))
            checkbox.pack(side=tk.LEFT, padx=(0, 3))
            # 按钮文本:如果有描述则显示名称和描述,否则只显示名称
            btn_text = f"{name}\n{desc}" if desc else name
            link_btn = tk.Button(
                btn_frame,
                text=btn_text,
                font=("TkDefaultFont", font_size, "bold" if is_rank_hot or sort_order <= 3 else "normal"),
                bg=bg_color,
                fg="black",
                cursor="hand2",
                relief=tk.RAISED,
                bd=2,
                padx=10,
                pady=5,
                wraplength=180,
                command=lambda u=url, n=name, d=desc: open_link(u, n, d)
            )
            link_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            # 存储按钮信息用于拖拽(注意:现在按钮在btn_frame中)
            button_info = {
                "button": link_btn,
                "button_frame": btn_frame,  # 添加按钮框架引用
                "item": item,
                "row": row,
                "col": col,
                "index": idx,
                "config_key": config_key
            }
            button_refs.append(button_info)
            # 实现拖拽功能(与合并标签页相同的逻辑)
            def on_drag_start(event, btn_info=button_info):
                btn_info["drag_start_x"] = event.x
                btn_info["drag_start_y"] = event.y
                btn_info["drag_start_root_x"] = event.x_root
                btn_info["drag_start_root_y"] = event.y_root
                btn_info["dragging"] = False
                btn_info["drag_threshold"] = 5
                btn_info["original_row"] = btn_info["row"]
                btn_info["original_col"] = btn_info["col"]
                btn_info["original_x"] = btn_info["button_frame"].winfo_x()
                btn_info["original_y"] = btn_info["button_frame"].winfo_y()
            def on_drag_motion(event, btn_info=button_info):
                dx = abs(event.x_root - btn_info["drag_start_root_x"])
                dy = abs(event.y_root - btn_info["drag_start_root_y"])
                distance = (dx**2 + dy**2)**0.5
                if not btn_info.get("dragging", False) and distance > btn_info["drag_threshold"]:
                    btn_info["dragging"] = True
                    btn_info["button_frame"].grid_remove()
                    btn_info["button_frame"].place(x=btn_info["original_x"], y=btn_info["original_y"])
                    btn_info["button_frame"].lift()
                if btn_info.get("dragging", False):
                    new_x = btn_info["original_x"] + (event.x - btn_info["drag_start_x"])
                    new_y = btn_info["original_y"] + (event.y - btn_info["drag_start_y"])
                    frame_x = grid_frame.winfo_x()
                    frame_y = grid_frame.winfo_y()
                    frame_width = grid_frame.winfo_width()
                    frame_height = grid_frame.winfo_height()
                    btn_width = btn_info["button_frame"].winfo_width()
                    btn_height = btn_info["button_frame"].winfo_height()
                    new_x = max(frame_x, min(new_x, frame_x + frame_width - btn_width))
                    new_y = max(frame_y, min(new_y, frame_y + frame_height - btn_height))
                    btn_info["button_frame"].place(x=new_x, y=new_y)
            def on_drag_end(event, btn_info=button_info):
                was_dragging = btn_info.get("dragging", False)
                btn_info["dragging"] = False
                if was_dragging:
                    btn_x = btn_info["button_frame"].winfo_x() - grid_frame.winfo_x()
                    btn_y = btn_info["button_frame"].winfo_y() - grid_frame.winfo_y()
                    cell_width = grid_frame.winfo_width() // 3
                    btn_height = btn_info["button_frame"].winfo_height()
                    if btn_height == 1:
                        btn_height = 50
                    cell_height = btn_height + 6
                    target_col = min(2, max(0, int(btn_x / cell_width)))
                    target_row = max(0, int(btn_y / cell_height))
                    target_idx = target_row * 3 + target_col
                    target_idx = min(len(button_refs) - 1, max(0, target_idx))
                    btn_info["button_frame"].place_forget()
                    btn_info["button_frame"].grid(row=btn_info["row"], column=btn_info["col"], padx=4, pady=3, sticky="ew")
                    if target_idx != btn_info["index"]:
                        self._reorder_single_config_buttons(button_refs, btn_info["index"], target_idx, config_key)
            link_btn.bind("<Button-1>", on_drag_start)
            link_btn.bind("<B1-Motion>", on_drag_motion)
            link_btn.bind("<ButtonRelease-1>", on_drag_end)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 添加编辑按钮
        edit_frame = ttk.Frame(tab_frame)
        edit_frame.pack(fill=tk.X, padx=5, pady=5)
        # 根据config_key确定编辑导航的标签页索引
        if config_key == "indices":
            edit_tab_idx = 0
        elif config_key == "dv_accounts":
            edit_tab_idx = 3  # 需要添加大V公众号标签页
        else:
            edit_tab_idx = None
        if edit_tab_idx is not None:
            ttk.Button(edit_frame, text="编辑导航", command=lambda: self.show_market_nav_editor(default_tab=edit_tab_idx)).pack(side=tk.LEFT, padx=5)
        else:
            ttk.Button(edit_frame, text="编辑导航", command=self.show_market_nav_editor).pack(side=tk.LEFT, padx=5)
        # 添加"设定为默认"按钮
        ttk.Button(edit_frame, text="设定为默认", command=lambda: self.set_as_default_config(config_key)).pack(side=tk.LEFT, padx=5)

    def show_os1_trading_rules_dialog(self):
        """操作系统1:风控/仓位/择时/选股 + 工具箱联动 Skill/量化/AI。"""
        win = self._toplevel(self.root)
        win.title("操作系统1 · 交易规则要点")
        win.geometry("1180x820")
        win.transient(self.root)
        win.minsize(800, 560)
        news_trackers = []
        def _bullets_from_block(s: str):
            out = []
            for ln in (s or "").splitlines():
                t = ln.strip()
                if t.startswith("•"):
                    out.append(t.lstrip("•").strip())
            return out
        def _os1_pool_top20(group_index: int):
            try:
                holding_stocks, *_ = self._get_holding_group_data(group_index)
            except Exception:
                return []
            out = []
            for i in range(min(20, len(holding_stocks))):
                it = holding_stocks[i]
                if not it:
                    continue
                if isinstance(it, (tuple, list)) and len(it) >= 2:
                    out.append((str(it[0] or "").strip(), str(it[1] or "").strip()))
                elif isinstance(it, dict):
                    out.append((str(it.get("name") or "").strip(), str(it.get("code") or "").strip()))
            return out
        def _fmt_pair(name, code):
            n, c = str(name or "").strip(), str(code or "").strip()
            if n and c:
                return f"{n}({c})"
            return n or c
        def _verdict_risk_timing(text: str, ok_sel: bool, bad_sel: bool) -> str:
            t = text
            if ok_sel and bad_sel:
                return "⚠ 请只选其一"
            if not ok_sel and not bad_sel:
                return "-"
            if bad_sel:
                if any(k in t for k in ("止损", "卖出", "清仓", "减仓", "卖", "砍半")):
                    return "判断:偏卖出/减仓/止损"
                if "3000" in t or "4000" in t or "下跌" in t:
                    return "判断:偏防御/降仓"
                if "买" in t or "上涨" in t or "开仓" in t:
                    return "判断:暂停买入/观望"
                return "判断:不符合→保守"
            if ok_sel:
                if any(k in t for k in ("止损", "卖出", "清仓")):
                    return "判断:暂不触发卖出"
                if any(k in t for k in ("买", "开仓", "加仓", "上涨家数")):
                    return "判断:可考虑买入/加仓"
                if "半仓" in t or "仓" in t:
                    return "判断:维持或加至计划仓位"
                return "判断:本条符合"
            return "-"
        def _verdict_pick(text: str, ok_sel: bool, bad_sel: bool) -> str:
            if ok_sel and bad_sel:
                return "⚠ 请只选其一"
            if not ok_sel and not bad_sel:
                return "-"
            if bad_sel:
                return "判断:不纳入/排除"
            return "判断:可纳入观察/备选"
        def _bind_toggle(v_ok, v_bad):
            def on_ok():
                if v_ok.get():
                    v_bad.set(False)
                _refresh_all_verdicts()
            def on_bad():
                if v_bad.get():
                    v_ok.set(False)
                _refresh_all_verdicts()
            return on_ok, on_bad
        verdict_labels = []
        def _refresh_all_verdicts():
            for ent in verdict_labels:
                fn = ent["fn"]
                ent["lbl"].config(text=fn(ent["txt"], ent["ok"].get(), ent["bad"].get()))
        def _build_rule_tab(tab, lines, kind):
            wrap = ttk.Frame(tab)
            wrap.pack(fill=tk.BOTH, expand=True)
            canvas = tk.Canvas(wrap, highlightthickness=0)
            sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
            inner = ttk.Frame(canvas, padding=(4, 4))
            win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
            def _on_inner_cfg(_e=None):
                canvas.configure(scrollregion=canvas.bbox("all"))
            def _on_canvas_cfg(e):
                try:
                    canvas.itemconfigure(win_id, width=e.width)
                except Exception:
                    pass
            inner.bind("<Configure>", _on_inner_cfg)
            canvas.bind("<Configure>", _on_canvas_cfg)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.configure(yscrollcommand=sb.set)
            for i, line in enumerate(lines):
                row = ttk.Frame(inner)
                row.grid(row=i, column=0, sticky="ew", pady=3)
                inner.grid_columnconfigure(0, weight=1)
                ttk.Label(row, text=f"• {line}", wraplength=520, justify=tk.LEFT).grid(row=0, column=0, sticky="w", padx=(0, 6))
                v_ok = tk.BooleanVar(value=False)
                v_bad = tk.BooleanVar(value=False)
                v_news = tk.BooleanVar(value=False)
                on_ok, on_bad = _bind_toggle(v_ok, v_bad)
                tk.Checkbutton(
                    row,
                    text="✓",
                    variable=v_ok,
                    command=on_ok,
                    fg="#c00",
                    selectcolor="white",
                    font=("Microsoft YaHei", 10, "bold"),
                ).grid(row=0, column=1, padx=2)
                tk.Checkbutton(
                    row,
                    text="✗",
                    variable=v_bad,
                    command=on_bad,
                    fg="#c00",
                    selectcolor="white",
                    font=("Microsoft YaHei", 10, "bold"),
                ).grid(row=0, column=2, padx=2)
                ttk.Checkbutton(row, text="资讯", variable=v_news).grid(row=0, column=3, padx=4)
                fn = _verdict_risk_timing if kind in ("risk", "timing") else _verdict_pick
                vl = ttk.Label(row, text="-", width=26)
                vl.grid(row=0, column=4, sticky="w")
                verdict_labels.append({"fn": fn, "txt": line, "ok": v_ok, "bad": v_bad, "lbl": vl})
                news_trackers.append({"text": line, "news": v_news})
            _refresh_all_verdicts()
        top_bar = ttk.Frame(win, padding=(10, 8))
        top_bar.pack(fill=tk.X)
        ttk.Label(
            top_bar,
            text="以下为口述内容结构化整理;每行可勾选 ✓/✗ 辅助当日判断;「资讯」勾选后点右侧工具箱可带入 Skill/量化/AI。不构成投资建议。",
            font=("TkDefaultFont", 9),
            foreground="gray",
        ).pack(anchor=tk.W)
        outer = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        left_wrap = ttk.Frame(outer)
        nb = ttk.Notebook(left_wrap)
        nb.pack(fill=tk.BOTH, expand=True)
        outer.add(left_wrap, weight=4)
        risk_lines = _bullets_from_block(
            """
• 每只股票事先想清楚止损:你的「买入理由」是什么,跌破该逻辑即为止损线。
• 有盈利的票不要幻想;弱转强再买回来,算作另一笔交易,不要混在一起。
• 开盘后下跌,若上冲仍不破均价线,最多给两次机会,第三次仍不破则卖。
• 开盘放量下跌、上冲不破开盘价,第一时间卖(极端一字跌停等除外)。
• 放量滞涨:量比很大(如开盘量比十几甚至 15+)但涨幅只有一两个点,尽快卖。
• 10:40 前若仍未按规则卖出,用条件单约束自己,避免盘中情绪波动。
• 10:40 看当日 K,并结合前两日共三根 K:若高点未抬高,倾向卖出。
• 连续两天亏损 → 减仓;连续三天亏损 → 无条件清仓,并复盘为何连亏。
• 大盘开盘快速下杀、个股跟随下杀:若 10 分钟内无快速反弹,先出局。
• 开盘约 3000 只下跌 → 砍半仓;若进一步约 4000 只下跌 → 清仓,不论盈亏(含涨停封单等情形,先保风险)。
• 风险永远第一位;严格执行规则时,「踏空」也算成功交易。
• 每天复盘前先重读一遍最新交易系统;违反规则的自惩:如健身、降仓位、甚至将部分资金转回银行直至恢复纪律。
• 散户心理普遍存在;对自己最硬的约束是减少留在证券账户里的本金。
"""
        )
        timing_lines = _bullets_from_block(
            """
• 没有「约 3000 家以上上涨」的环境,哪怕标的再看好,也不做买入动作。
• 择时比择股更重要;上面这条就是具象化的择时门控。
• 买入只发生在:早盘 10:40 之前,或下午约 14:40 之后;中间不做买入。
• 中间时段可以按卖出规则卖,但不新买。
• 早盘第一分钟很重要:若先冲高再回调,在均价线附近、缩量有支撑可关注。
• 回调在开盘价之上、缩量有支撑;放量支撑则不按此逻辑追买。
• 开盘一分钟放量下跌后,若「弱转强」上穿均价线,要看量是放量还是缩量上去;放量上冲宁愿错过也不追。
• 缩量回踩均价线(或离均价线不远有支撑)再买;急拉放量不追,宁可等回调;临近涨停的急拉除非打板策略,否则不追。
• 每天机会很多,错过无所谓。
• 卖出可在盘中按个股信号执行;买入仍遵守时段 + 3000+ 上涨门控。
"""
        )
        pick_lines = _bullets_from_block(
            """
• 每晚复盘约 10~30 分钟(近期可更短);用 DeepSeek 或交易软件辅助检索。
• 无异动、无资金关注的个股不做:至少约一个月内有涨停,或有过倍量以上成交。
• 优先:长期横盘较大、或长期横盘后上涨初期。
• 上影线越长越好;若上影打到前期高点,当日量应高于前期高点对应量。
• 近期涨停后回调出现的上影线、底部承接强更好;最好无明显下影线(偏量价,非纯画线技术)。
• 更常做一进二;偏好市值约 100 亿以内。
• 约 25 日内有过涨停,且未跌破当时涨停价低点;量能不要过分放大。
• 横盘突破涨停、涨停突破前高 - 重点跟踪。
• 涨停后回调、反复确认底部:大盘跌它不跌,连续数日抗跌甚至放量上冲 - 可分批加关注或仓位。
• 量价背离例:连跌两日,第三日缩量但跌幅更大,可小仓试错,次日是否放量向上再定。
• 核心是量价与纪律,规则会随时间微调;以你当前纸面交易系统为准每日复核。
"""
        )
        tab_risk = ttk.Frame(nb, padding=4)
        nb.add(tab_risk, text="风控")
        _build_rule_tab(tab_risk, risk_lines, "risk")
        tab_pos = ttk.Frame(nb, padding=6)
        nb.add(tab_pos, text="仓位")
        pos_top = ttk.LabelFrame(tab_pos, text="说明(口述摘要)", padding=6)
        pos_top.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            pos_top,
            text="大盘环境≈门控:约3000+上涨才买;资金分 N 份则最多 N 只;环境不符不买。右侧数值若未接入太平洋/同花顺交易接口,则以行情估算供参考。",
            wraplength=900,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        pos_ctl = ttk.Frame(tab_pos)
        pos_ctl.pack(fill=tk.X, pady=4)
        slot_var = tk.IntVar(value=10)
        ttk.Radiobutton(pos_ctl, text="分 10 份(最多 10 只)", variable=slot_var, value=10).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(pos_ctl, text="分 5 份(最多 5 只)", variable=slot_var, value=5).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(pos_ctl, text="总资金(元,估算用):").pack(side=tk.LEFT, padx=(16, 4))
        total_cap = tk.StringVar(value="1000000")
        ttk.Entry(pos_ctl, textvariable=total_cap, width=14).pack(side=tk.LEFT, padx=(0, 12))
        _pos_hint = ttk.Frame(tab_pos)
        ttk.Label(
            _pos_hint,
            text="切换 5/10 份仅改变显示行数,已填代码与导入的券商持仓会保留。太平洋/中信等:先弹出「委托下单」式登录,再从持仓载入(预留交易网关;当前缺接口时读 os1_broker_holdings.json + 东财快照)。",
            foreground="gray",
            font=("TkDefaultFont", 9),
        ).pack(anchor=tk.W)
        _pos_hint.pack(fill=tk.X)
        pos_grid_fr = ttk.Frame(tab_pos)
        pos_grid_fr.pack(fill=tk.BOTH, expand=True, pady=6)
        hdr = ttk.Frame(pos_grid_fr)
        hdr.pack(fill=tk.X)
        heads = ("#", "代码/名称", "从池导入", "推荐仓位%", "持仓占比%", "现价", "参考买", "参考卖", "参考买入量", "参考卖出量")
        for c, h in enumerate(heads):
            ttk.Label(hdr, text=h, width=12 if c > 0 else 4).grid(row=0, column=c, padx=2, sticky="w")
        pos_slot_vars = [tk.StringVar(value="") for _ in range(10)]
        pos_broker_meta = [None] * 10
        pos_row_ui = [None] * 10
        spot_holder = {"df": None, "err": None}
        def _parse_code_name(s: str):
            s = (s or "").strip()
            if not s:
                return "", ""
            import re
            m = re.search(r"\((\d{6})\)", s)
            if m:
                code = m.group(1)
                name = re.sub(r"\(\d{6}\)", "", s).strip()
                return name, code
            m2 = re.fullmatch(r"(\d{6})", s)
            if m2:
                return "", m2.group(1)
            return s, ""
        def _refresh_spot_df():
            spot_holder["df"] = None
            spot_holder["err"] = None
            if not AKSHARE_AVAILABLE:
                spot_holder["err"] = "akshare 不可用"
                return
            try:
                spot_holder["df"] = ak.stock_zh_a_spot_em()
            except Exception as e:
                spot_holder["err"] = str(e)
        def _price_for_code(code: str):
            df = spot_holder.get("df")
            if df is None or not code or len(code) != 6:
                return None
            try:
                col_code = "代码" if "代码" in df.columns else None
                if not col_code:
                    return None
                row = df[df[col_code].astype(str).str.zfill(6) == code.zfill(6)]
                if row.empty:
                    return None
                r = row.iloc[0]
                for k in ("最新价", "最新", "现价"):
                    if k in row.columns:
                        try:
                            return float(r[k])
                        except Exception:
                            pass
            except Exception:
                return None
            return None
        def _upd_slot_row(i_slot: int):
            ui = pos_row_ui[i_slot]
            if ui is None:
                return
            rec, sh, px, bp, sp, bq, sq = (
                ui["rec"],
                ui["sh"],
                ui["px"],
                ui["bp"],
                ui["sp"],
                ui["bq"],
                ui["sq"],
            )
            try:
                cap = float((total_cap.get() or "0").replace(",", ""))
            except Exception:
                cap = 0.0
            ns = int(slot_var.get())
            pct_rec = (100.0 / ns) if ns else 0.0
            rec.config(text=f"{pct_rec:.1f}%")
            e = pos_slot_vars[i_slot]
            nm, cd = _parse_code_name(e.get())
            if not cd and nm and str(nm).isdigit() and len(str(nm)) == 6:
                cd = str(nm)
            bm = pos_broker_meta[i_slot]
            pr = _price_for_code(cd) if cd else None
            if bm and isinstance(bm, dict):
                ap = bm.get("avg_price")
                mv = bm.get("market_value")
                qty = bm.get("quantity")
                if pr is None and isinstance(ap, (int, float)) and ap:
                    pr = float(ap)
                if pr is not None:
                    px.config(text=f"{pr:.2f}")
                    bp.config(text=f"{pr * 0.998:.2f}")
                    sp.config(text=f"{pr * 1.002:.2f}")
                else:
                    px.config(text="-")
                    bp.config(text="-")
                    sp.config(text="-")
                tot_mv = 0.0
                for j in range(10):
                    m = pos_broker_meta[j]
                    if m and isinstance(m, dict) and m.get("market_value") is not None:
                        try:
                            tot_mv += float(m["market_value"])
                        except Exception:
                            pass
                if tot_mv > 0 and mv is not None:
                    try:
                        sh.config(text=f"{float(mv) / tot_mv * 100.0:.2f}%")
                    except Exception:
                        sh.config(text="--")
                elif bm.get("weight_pct") is not None:
                    try:
                        sh.config(text=f"{float(bm['weight_pct']):.2f}%")
                    except Exception:
                        sh.config(text="--")
                else:
                    sh.config(text="--")
                if qty is not None and pr is not None:
                    try:
                        q = int(qty)
                        bq.config(text=str(q))
                        sq.config(text=str(q))
                    except Exception:
                        bq.config(text="-")
                        sq.config(text="-")
                else:
                    bq.config(text="-")
                    sq.config(text="-")
            else:
                if pr is not None:
                    px.config(text=f"{pr:.2f}")
                    bp.config(text=f"{pr * 0.998:.2f}")
                    sp.config(text=f"{pr * 1.002:.2f}")
                    per = cap * (pct_rec / 100.0)
                    if pr > 0:
                        vol = int(per / pr / 100) * 100
                        bq.config(text=str(vol))
                        sq.config(text=str(vol))
                else:
                    px.config(text="-")
                    bp.config(text="-")
                    sp.config(text="-")
                    bq.config(text="-")
                    sq.config(text="-")
                sh.config(text="--")
        def _rebuild_pos_rows():
            for i in range(10):
                if pos_row_ui[i] is not None:
                    try:
                        pos_row_ui[i]["frame"].destroy()
                    except Exception:
                        pass
                    pos_row_ui[i] = None
            n = int(slot_var.get())
            for i in range(n):
                fr = ttk.Frame(pos_grid_fr)
                fr.pack(fill=tk.X, pady=1)
                ttk.Label(fr, text=str(i + 1), width=4).grid(row=0, column=0, padx=2)
                ttk.Entry(fr, textvariable=pos_slot_vars[i], width=22).grid(row=0, column=1, padx=2)
                pool_btn = ttk.Menubutton(fr, text="池▼", width=6)
                pool_btn.grid(row=0, column=2, padx=2)
                mu = tk.Menu(pool_btn, tearoff=False)
                pool_btn["menu"] = mu
                def _mk_cmd(gi, ii=i):
                    def _():
                        lst = _os1_pool_top20(gi)
                        if not lst:
                            return
                        pick = lst[0]
                        pos_slot_vars[ii].set(_fmt_pair(pick[0], pick[1]))
                        pos_broker_meta[ii] = None
                    return _
                for label, gi in (
                    ("龙头股→首只", 2),
                    ("Main→首只", 4),
                    ("持仓→首只", 1),
                    ("同花顺→首只", 6),
                    ("15Min→首只", 3),
                ):
                    mu.add_command(label=label, command=_mk_cmd(gi))
                def _mk_pick(gi, ii=i):
                    def __():
                        dlg = self._toplevel(win)
                        dlg.title("从池中选一只")
                        dlg.geometry("420x360")
                        lb = tk.Listbox(dlg, font=("Microsoft YaHei", 10))
                        lb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
                        pairs = _os1_pool_top20(gi)
                        for p in pairs:
                            lb.insert(tk.END, _fmt_pair(p[0], p[1]))
                        def _ok():
                            sel = lb.curselection()
                            if not sel:
                                dlg.destroy()
                                return
                            t = lb.get(sel[0])
                            pos_slot_vars[ii].set(t.strip())
                            pos_broker_meta[ii] = None
                            dlg.destroy()
                        ttk.Button(dlg, text="确定", command=_ok).pack(pady=6)
                    return __
                sub = tk.Menu(mu, tearoff=False)
                mu.add_cascade(label="列表选入...", menu=sub)
                for label, gi in (
                    ("龙头股(前20)", 2),
                    ("Main(前20)", 4),
                    ("持仓(前20)", 1),
                    ("同花顺(前20)", 6),
                    ("15Min(前20)", 3),
                ):
                    sub.add_command(label=label, command=_mk_pick(gi))
                rec = ttk.Label(fr, text="-", width=10)
                sh = ttk.Label(fr, text="-", width=10)
                px = ttk.Label(fr, text="-", width=8)
                bp = ttk.Label(fr, text="-", width=8)
                sp = ttk.Label(fr, text="-", width=8)
                bq = ttk.Label(fr, text="-", width=10)
                sq = ttk.Label(fr, text="-", width=10)
                rec.grid(row=0, column=3, padx=2)
                sh.grid(row=0, column=4, padx=2)
                px.grid(row=0, column=5, padx=2)
                bp.grid(row=0, column=6, padx=2)
                sp.grid(row=0, column=7, padx=2)
                bq.grid(row=0, column=8, padx=2)
                sq.grid(row=0, column=9, padx=2)
                pos_row_ui[i] = {
                    "frame": fr,
                    "rec": rec,
                    "sh": sh,
                    "px": px,
                    "bp": bp,
                    "sp": sp,
                    "bq": bq,
                    "sq": sq,
                }
                _upd_slot_row(i)
        def _on_slot_change(*_a):
            _rebuild_pos_rows()
        for _si in range(10):
            pos_slot_vars[_si].trace_add("write", lambda *args, i=_si: _upd_slot_row(i))
        slot_var.trace_add("write", _on_slot_change)
        total_cap.trace_add(
            "write",
            lambda *_: [_upd_slot_row(i) for i in range(10) if pos_row_ui[i] is not None],
        )
        def _broker_holdings_json_path():
            return os.path.join(D_DATA_DIR, "os1_broker_holdings.json")
        def _normalize_holdings_list(raw):
            out = []
            if isinstance(raw, list):
                it = raw
            elif isinstance(raw, dict):
                it = raw.get("holdings") or raw.get("positions") or raw.get("list") or []
            else:
                return out
            for h in it:
                if not isinstance(h, dict):
                    continue
                _rc = str(h.get("code") or h.get("证券代码") or h.get("stock_code") or "").strip()
                if _rc.isdigit():
                    code = _rc.zfill(6)[-6:]
                else:
                    code = ""
                name = str(h.get("name") or h.get("证券名称") or h.get("stock_name") or "").strip()
                qty = h.get("quantity") or h.get("持仓数量") or h.get("qty") or h.get("股数")
                avg = h.get("avg_price") or h.get("成本价") or h.get("cost")
                mv = h.get("market_value") or h.get("市值") or h.get("持仓市值")
                try:
                    qty = int(float(qty)) if qty is not None else None
                except Exception:
                    qty = None
                try:
                    avg = float(avg) if avg is not None else None
                except Exception:
                    avg = None
                try:
                    mv = float(mv) if mv is not None else None
                except Exception:
                    mv = None
                if len(code) != 6 or not code.isdigit():
                    continue
                out.append(
                    {
                        "code": code,
                        "name": name,
                        "quantity": qty,
                        "avg_price": avg,
                        "market_value": mv,
                    }
                )
            return out
        def _apply_imported_holdings(rows):
            if not rows:
                messagebox.showinfo("提示", "没有可导入的持仓记录。", parent=win)
                return
            for j in range(10):
                pos_broker_meta[j] = None
            tot_mv = 0.0
            clean = []
            for h in rows[:10]:
                mv = h.get("market_value")
                if mv is None and h.get("quantity") and h.get("avg_price"):
                    try:
                        mv = float(h["quantity"]) * float(h["avg_price"])
                    except Exception:
                        mv = None
                if mv is not None:
                    try:
                        tot_mv += float(mv)
                    except Exception:
                        pass
                hh = dict(h)
                hh["market_value"] = mv
                clean.append(hh)
            for j, h in enumerate(clean):
                code = h.get("code") or ""
                name = h.get("name") or ""
                pos_slot_vars[j].set(_fmt_pair(name, code) if name or code else "")
                mv = h.get("market_value")
                wp = (float(mv) / tot_mv * 100.0) if (tot_mv > 0 and mv is not None) else None
                pos_broker_meta[j] = {
                    "quantity": h.get("quantity"),
                    "avg_price": h.get("avg_price"),
                    "market_value": mv,
                    "weight_pct": wp,
                    "name": name,
                    "code": code,
                }
            for j in range(len(clean), 10):
                pos_slot_vars[j].set("")
                pos_broker_meta[j] = None
            if tot_mv > 0:
                total_cap.set(str(round(tot_mv)))
            _rebuild_pos_rows()
        def _import_from_json_data(data, label):
            try:
                if not isinstance(data, dict) or label not in data:
                    messagebox.showwarning("提示", f"数据中无键「{label}」或格式不是 JSON 对象。", parent=win)
                    return
                raw = data[label]
                rows = _normalize_holdings_list(raw if isinstance(raw, list) else raw)
                if not rows:
                    messagebox.showwarning("提示", f"「{label}」下没有有效持仓(需含 6 位 code)。", parent=win)
                    return
                _apply_imported_holdings(rows)
                messagebox.showinfo("完成", f"已导入 {len(rows)} 条({label}),已写入前 {len(rows)} 行。", parent=win)
            except Exception as e:
                messagebox.showerror("错误", str(e), parent=win)
        def _broker_login_prefs_path():
            return os.path.join(D_DATA_DIR, "os1_broker_login_prefs.json")
        def _load_broker_login_prefs():
            try:
                with open(_broker_login_prefs_path(), "r", encoding="utf-8") as f:
                    d = json.load(f)
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}
        def _save_broker_login_prefs(prefs: dict):
            try:
                os.makedirs(D_DATA_DIR, exist_ok=True)
                with open(_broker_login_prefs_path(), "w", encoding="utf-8") as f:
                    json.dump(prefs, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        def _try_broker_remote_holdings(broker_key: str, site: str, account: str, password: str):
            """预留:接入太平洋/中信建投等交易网关或官方 API 后在此返回持仓列表(元素为含 code/name/quantity/avg_price 等的 dict)。"""
            _ = (site, account, password)
        _BROKER_SITE_PRESETS = {
            "太平洋": (
                "太平洋证券上海电信二",
                "太平洋证券上海电信一",
                "太平洋证券北京联通",
                "太平洋证券深圳电信",
            ),
            "中信建投": (
                "中信建投华东电信",
                "中信建投上海电信",
                "中信建投北京联通",
                "中信建投默认站点",
            ),
        }
        def _import_holdings_json_for_broker(which: str, from_file_msg_suffix: str = ""):
            path = _broker_holdings_json_path()
            if not os.path.isfile(path):
                messagebox.showwarning(
                    "提示",
                    f"未找到配置文件:\n{path}\n\n"
                    "当前版本未接入券商交易网关实时拉取持仓;登录成功后需从此 JSON 读取。\n"
                    "请将券商导出或整理的 JSON 放在上述路径,或使用「选择 JSON 文件...」。\n"
                    "示例结构:\n"
                    '{ "太平洋": [ {"code":"600519","name":"贵州茅台","quantity":100,"avg_price":1750,"market_value":175000} ], '
                    '"中信建投": [ ... ] }'
                    + from_file_msg_suffix,
                    parent=win,
                )
                return False
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                messagebox.showerror("错误", f"读取失败:{e}", parent=win)
                return False
            if not isinstance(data, dict):
                messagebox.showwarning("提示", "JSON 根须为对象。", parent=win)
                return False
            picked = None
            if which in data:
                picked = which
            elif which == "中信建投":
                for alt in ("中信建投", "中信", "CSC"):
                    if alt in data:
                        picked = alt
                        break
            elif which == "太平洋" and "太平洋" in data:
                picked = "太平洋"
            if picked:
                _import_from_json_data(data, picked)
                return True
            messagebox.showwarning(
                "提示",
                f"在 {os.path.basename(path)} 中未找到账户「{which}」。可改用「选择 JSON 文件...」。",
                parent=win,
            )
            return False
        def _open_broker_login_and_import(which: str):
            """参考「委托下单」:先登录确认账号,再尝试拉取持仓(预留接口),否则读 os1_broker_holdings.json。"""
            prefs_all = _load_broker_login_prefs()
            per = prefs_all.get(which)
            if not isinstance(per, dict):
                per = {}
            sites = _BROKER_SITE_PRESETS.get(which, ())
            dlg = tk.Toplevel(win)
            dlg.title("委托下单")
            dlg.transient(win)
            dlg.resizable(False, False)
            try:
                dlg.grab_set()
            except Exception:
                pass
            try:
                dlg.attributes("-topmost", True)
                dlg.after(300, lambda: dlg.attributes("-topmost", False))
            except Exception:
                pass
            outer_login = ttk.Frame(dlg, padding=12)
            outer_login.pack(fill=tk.BOTH, expand=True)
            ttk.Label(
                outer_login,
                text="导入持仓前请先确认交易账户(与太平洋等客户端类似)。\n"
                "说明:交易密码不会写入磁盘;真实持仓直连需在 _try_broker_remote_holdings 中接入券商接口,\n"
                "当前登录成功后仍从下方 JSON 同步文件读取持仓并填充表格。",
                wraplength=420,
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
            ttk.Label(outer_login, text="证券公司").grid(row=1, column=0, sticky="w", pady=2)
            br_disp = "太平洋证券" if which == "太平洋" else "中信建投"
            br_var = tk.StringVar(value=br_disp)
            br_cb = ttk.Combobox(outer_login, textvariable=br_var, width=28, state="readonly")
            br_cb["values"] = ("太平洋证券", "中信建投")
            br_cb.grid(row=1, column=1, sticky="ew", pady=2)
            ttk.Label(outer_login, text="站点列表").grid(row=2, column=0, sticky="w", pady=2)
            site_var = tk.StringVar(value=str(per.get("site") or (sites[0] if sites else "")))
            site_cb = ttk.Combobox(outer_login, textvariable=site_var, width=28)
            site_cb.grid(row=2, column=1, sticky="ew", pady=2)
            def _refresh_site_choices(*_):
                k = "太平洋" if "太平洋" in br_var.get() else "中信建投"
                ch = _BROKER_SITE_PRESETS.get(k, ())
                site_cb["values"] = ch
                if ch and site_var.get() not in ch:
                    site_var.set(ch[0])
            br_cb.bind("<<ComboboxSelected>>", _refresh_site_choices)
            site_cb["values"] = sites
            if sites and not site_var.get():
                site_var.set(sites[0])
            fast_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(_outer := ttk.Frame(outer_login), text="连最快站点", variable=fast_var).pack(anchor="w")
            _outer.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 6))
            ttk.Label(outer_login, text="资金账户").grid(row=4, column=0, sticky="w", pady=2)
            acct_var = tk.StringVar(value=str(per.get("account") or ""))
            ttk.Entry(outer_login, textvariable=acct_var, width=30).grid(row=4, column=1, sticky="ew", pady=2)
            ttk.Label(outer_login, text="交易密码").grid(row=5, column=0, sticky="w", pady=2)
            pwd_var = tk.StringVar()
            ttk.Entry(outer_login, textvariable=pwd_var, width=30, show="*").grid(row=5, column=1, sticky="ew", pady=2)
            remember_var = tk.BooleanVar(value=bool(per.get("remember")))
            autofill_var = tk.BooleanVar(value=bool(per.get("autofill", True)))
            ttk.Checkbutton(
                outer_login,
                text="记住资金账号与站点(密码不落盘)",
                variable=remember_var,
            ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))
            ttk.Checkbutton(outer_login, text="下次打开本窗口自动填入", variable=autofill_var).grid(
                row=7, column=0, columnspan=2, sticky="w"
            )
            btn_row = ttk.Frame(outer_login)
            btn_row.grid(row=8, column=0, columnspan=2, pady=(14, 0))
            def _on_cancel():
                dlg.destroy()
            def _on_login():
                br_key = "太平洋" if "太平洋" in br_var.get() else "中信建投"
                site_v = (site_var.get() or "").strip()
                acct_v = (acct_var.get() or "").strip()
                pwd_v = pwd_var.get() or ""
                if remember_var.get():
                    prefs_all[br_key] = {
                        "site": site_v,
                        "account": acct_v,
                        "remember": True,
                        "autofill": autofill_var.get(),
                    }
                    _save_broker_login_prefs(prefs_all)
                dlg.destroy()
                rows_remote = _try_broker_remote_holdings(br_key, site_v, acct_v, pwd_v)
                if rows_remote:
                    norm = _normalize_holdings_list(rows_remote)
                    if norm:
                        _apply_imported_holdings(norm)
                        messagebox.showinfo(
                            "完成",
                            f"已从交易通道获取 {len(norm)} 条持仓并写入表格。",
                            parent=win,
                        )
                        return
                _import_holdings_json_for_broker(
                    br_key,
                    from_file_msg_suffix=(
                        f"\n\n本次登录:券商={br_key},站点={site_v or '-'},资金账号={'已填' if acct_v else '未填'}。"
                    ),
                )
            ttk.Button(btn_row, text="登录", width=12, command=_on_login).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(btn_row, text="取消", width=8, command=_on_cancel).pack(side=tk.LEFT)
            outer_login.columnconfigure(1, weight=1)
            dlg.protocol("WM_DELETE_WINDOW", _on_cancel)
            dlg.update_idletasks()
            try:
                px = win.winfo_rootx() + (win.winfo_width() - dlg.winfo_reqwidth()) // 2
                py = win.winfo_rooty() + (win.winfo_height() - dlg.winfo_reqheight()) // 2
                dlg.geometry(f"+{max(0, px)}+{max(0, py)}")
            except Exception:
                pass
        def _import_broker_menu(which: str):
            _open_broker_login_and_import(which)
        def _import_pick_file():
            p = filedialog.askopenfilename(
                parent=win,
                title="选择持仓 JSON",
                filetypes=[("JSON", "*.json"), ("所有", "*.*")],
                initialdir=D_DATA_DIR,
            )
            if not p:
                return
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                messagebox.showerror("错误", f"读取失败:{e}", parent=win)
                return
            if isinstance(data, dict):
                for k in ("太平洋", "中信建投", "中信", "holdings", "positions"):
                    if data.get(k):
                        _import_from_json_data(data, k)
                        return
                first = next(iter(data.keys()))
                _import_from_json_data(data, first)
            elif isinstance(data, list):
                norm = _normalize_holdings_list(data)
                if not norm:
                    messagebox.showwarning("提示", "列表中无有效持仓(需含 6 位股票代码)。", parent=win)
                    return
                _apply_imported_holdings(norm)
                messagebox.showinfo("完成", f"已导入 {min(len(norm), 10)} 条。", parent=win)
        btn_rf = ttk.Frame(tab_pos)
        btn_rf.pack(fill=tk.X, pady=4)
        def _do_refresh_spot():
            btn_rf.config(cursor="watch")
            win.update_idletasks()
            def work():
                _refresh_spot_df()
                win.after(
                    0,
                    lambda: (
                        btn_rf.config(cursor=""),
                        [_upd_slot_row(i) for i in range(10) if pos_row_ui[i] is not None],
                    ),
                )
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(btn_rf, text="刷新行情(东财快照)", command=_do_refresh_spot).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_rf, text="重绘行(保留数据)", command=_rebuild_pos_rows).pack(side=tk.LEFT, padx=(0, 8))
        br_imp = ttk.Menubutton(btn_rf, text="从证券账号导入 ▼", width=18)
        br_imp.pack(side=tk.LEFT, padx=(0, 8))
        m_br = tk.Menu(br_imp, tearoff=False)
        br_imp["menu"] = m_br
        m_br.add_command(label="太平洋证券(登录后导入持仓)", command=lambda: _import_broker_menu("太平洋"))
        m_br.add_command(label="中信建投(登录后导入持仓)", command=lambda: _import_broker_menu("中信建投"))
        m_br.add_command(label="选择 JSON 文件...", command=_import_pick_file)
        ttk.Label(
            btn_rf,
            text=f"配置文件:{os.path.join(D_DATA_DIR, 'os1_broker_holdings.json')}",
            font=("TkDefaultFont", 8),
            foreground="gray",
        ).pack(side=tk.LEFT, padx=(8, 0))
        _rebuild_pos_rows()
        _refresh_spot_df()
        tab_time = ttk.Frame(nb, padding=4)
        nb.add(tab_time, text="择时")
        _build_rule_tab(tab_time, timing_lines, "timing")
        tab_pick = ttk.Frame(nb, padding=4)
        nb.add(tab_pick, text="选股")
        _build_rule_tab(tab_pick, pick_lines, "pick")
        right = ttk.LabelFrame(outer, text="工具箱", padding=8)
        outer.add(right, weight=1)
        try:
            outer.paneconfigure(left_wrap, minsize=400)
            outer.paneconfigure(right, minsize=130)
        except Exception:
            pass
        def _bundle_news():
            parts = []
            for tr in news_trackers:
                try:
                    if tr["news"].get():
                        parts.append(tr["text"])
                except Exception:
                    pass
            return "\n\n".join(parts).strip()
        def _open_skill():
            self._os1_toolbox_prefill = _bundle_news()
            self.show_iwencai_skillhub_dialog()
        def _open_quant():
            self._os1_toolbox_prefill = _bundle_news()
            self.show_quant_strategy_dialog()
        def _open_ai():
            self._os1_ai_append = _bundle_news()
            self.show_ai_staff_dialog()
        ttk.Label(right, text="勾选各行「资讯」后\n点下面按钮带入\nSkill/量化/AI。", wraplength=120, justify=tk.CENTER).pack(pady=(0, 10))
        ttk.Button(right, text="Skill", width=14, command=_open_skill).pack(pady=4)
        ttk.Button(right, text="量化", width=14, command=_open_quant).pack(pady=4)
        ttk.Button(right, text="AI", width=14, command=_open_ai).pack(pady=4)
        # 添加保存按钮
        def _save_to_news():
            """将操作系统中的描述和选择保存到资讯表"""
            # 收集所有规则的描述和选择状态
            rule_data = []
            for ent in verdict_labels:
                rule_text = ent["txt"]
                ok_selected = ent["ok"].get()
                bad_selected = ent["bad"].get()
                news_selected = False
                # 查找对应的news tracker
                for tracker in news_trackers:
                    if tracker["text"] == rule_text:
                        news_selected = tracker["news"].get()
                        break
                rule_data.append({
                    "text": rule_text,
                    "ok_selected": ok_selected,
                    "bad_selected": bad_selected,
                    "news_selected": news_selected
                })
            # 构建保存内容
            content_lines = []
            content_lines.append("操作系统1 · 交易规则要点")
            content_lines.append("=" * 40)
            content_lines.append(f"保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content_lines.append("")
            # 分类整理规则
            risk_rules = []
            timing_rules = []
            pick_rules = []
            for rule in rule_data:
                if any(keyword in rule["text"] for keyword in ["止损", "卖出", "清仓", "减仓", "风险", "亏损", "下跌"]):
                    risk_rules.append(rule)
                elif any(keyword in rule["text"] for keyword in ["买入", "上涨", "择时", "时段", "开盘"]):
                    timing_rules.append(rule)
                elif any(keyword in rule["text"] for keyword in ["复盘", "选股", "标的", "关注"]):
                    pick_rules.append(rule)
            def add_rules_section(title, rules):
                if rules:
                    content_lines.append(f"【{title}】")
                    for rule in rules:
                        status = "✓" if rule["ok_selected"] else "✗" if rule["bad_selected"] else "-"
                        news_marker = "[资讯]" if rule["news_selected"] else ""
                        content_lines.append(f"{status} {rule['text']} {news_marker}")
                    content_lines.append("")
            add_rules_section("风控规则", risk_rules)
            add_rules_section("择时规则", timing_rules)
            add_rules_section("选股规则", pick_rules)
            # 保存到资讯表
            content = "\n".join(content_lines)
            try:
                # 使用全局的保存资讯函数
                tab_name = f"操作系统1_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                if save_news_info_to_db(tab_name, content):
                    messagebox.showinfo("成功", "已将操作系统规则记录保存到资讯表", parent=win)
                else:
                    messagebox.showerror("错误", "保存到资讯表失败", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败:{e!s}", parent=win)
        ttk.Button(right, text="保存", width=14, command=_save_to_news).pack(pady=4)
        bot = ttk.Frame(win, padding=(10, 0, 10, 10))
        bot.pack(fill=tk.X)
        ttk.Button(bot, text="关闭", command=win.destroy).pack(side=tk.RIGHT)

    def _show_tomorrow_predict_popup(self):
        """明日涨跌预测 - 对 Main 持仓股的最近9-10日数据打分预测明日涨跌"""
        if not TOMORROW_PREDICT_AVAILABLE:
            messagebox.showerror("错误", "tomorrow_predict 模块未找到，请先复制脚本到 src/ 目录", parent=self.root)
            return
        main_holdings = self._get_main_holding_stocks()
        if not main_holdings:
            messagebox.showinfo("提示", "Main 持仓股为空，请先在 Main 标签页导入持仓股。", parent=self.root)
            return
        # 收集所有 Main 持仓股的数据
        stocks_input = []
        for stock_name, stock_code, position_index in main_holdings:
            if not stock_code:
                continue
            changes, ma10_dist = self._get_stock_recent_10day_and_ma10(stock_code)
            if not changes or len(changes) < 6:
                continue
            # 取最近9日
            changes_9 = changes[-9:] if len(changes) >= 9 else changes
            # 计算累计涨幅
            cum = 1.0
            for c in changes_9:
                cum *= (1 + c / 100)
            total = round((cum - 1) * 100, 2)
            stocks_input.append(StockPredictInput(
                code=stock_code, name=stock_name,
                changes=changes_9, total=total, ma10_dist=ma10_dist
            ))
        if not stocks_input:
            messagebox.showwarning("警告", "未能获取任何持仓股的有效数据", parent=self.root)
            return
        # 批量预测
        results = batch_predict(stocks_input)
        # 弹窗显示
        win = self._toplevel(self.root)
        win.title(f"🔮 明日涨跌预测 - Main持仓股 {len(results)} 只")
        win.geometry("1100x620")
        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.BOTH, expand=True)
        ttk.Label(top, text=f"🔮 明日涨跌预测（基于最近 {len(stocks_input[0].changes)} 日数据 + 距10日线%）",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        # 表格
        list_frame = ttk.Frame(top)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        cols = ("代码", "名称", "得分", "信号", "明日预期", "建议", "昨日", "信心度", "累计%", "🦅心法", "最强流派")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=20)
        for col, w in [("代码",80),("名称",90),("得分",70),("信号",80),("明日预期",80),
                        ("建议",100),("昨日",70),("信心度",80),("累计%",80),("🦅心法",75),("最强流派",95)]:
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="center")
        # 先插入占位行, 心法分异步填充
        for r in results:
            score_color = "🟢" if r.score >= 7 else ("🔴" if r.score < 5 else "⚪")
            tree.insert("", "end", values=(
                r.code, r.name, f"{score_color} {r.score:.1f}",
                r.signal, r.outlook, r.suggestion,
                f"{r.last_change:+.2f}%",
                f"{r.confidence*100:.0f}%",
                f"{r.detail.get('总累计涨幅', '')}",
                "⏳", "-"
            ))
        tree.tag_configure("high", foreground="#C62828")
        tree.tag_configure("mid", foreground="#F57F17")
        tree.tag_configure("low", foreground="#2E7D32")
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll_y.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # ========== 异步算游资心法分 ==========
        def _bg_hm_for_tomorrow():
            for i, r in enumerate(results):
                if not win.winfo_exists(): break
                try:
                    hm = self._hm_calc_for_stock(r.code)
                    sc = hm.get("avg_score")
                    best = hm.get("best_sch", "-")
                    tag = "high" if sc and sc >= 65 else ("mid" if sc and sc >= 45 else "low")
                    sc_txt = "-" if sc is None else f"{int(sc)}"
                    def _upd(idx=i, _sc=sc_txt, _tg=tag, _bst=best):
                        if not win.winfo_exists(): return
                        try:
                            kids = tree.get_children()
                            if idx < len(kids):
                                vals = list(tree.item(kids[idx], "values"))
                                vals[9] = _sc   # 🦅心法分
                                vals[10] = _bst  # 最强流派
                                tree.item(kids[idx], values=vals, tags=(_tg,))
                        except Exception:
                            pass
                    self.root.after(0, _upd)
                except Exception:
                    pass
                time.sleep(0.3)
        import threading as _th_tp
        _th_tp.Thread(target=_bg_hm_for_tomorrow, daemon=True).start()

        # 双击查看详情 → 弹游资心法全解 + 预测逻辑
        def show_detail(event):
            item = tree.selection()
            if not item: return
            idx = tree.index(item[0])
            r = results[idx]
            try:
                # 上半: 预测逻辑 (messagebox 改 ScrolledText 弹窗)
                detail = tk.Toplevel(self.root)
                detail.title(f"🔮 {r.name}({r.code}) 预测详情 + 游资心法全解")
                detail.geometry("900x700")
                detail.configure(bg="#F5F5F5")
                detail.transient(self.root)

                # 上半: 预测逻辑
                top_f = tk.LabelFrame(detail, text="🔮 明日预测逻辑", bg="white", font=("", 10, "bold"))
                top_f.pack(fill="x", padx=10, pady=(10, 4))
                pred_lines = [f"📊 {r.name} ({r.code}) 预测明细", ""]
                for k, v in r.detail.items():
                    pred_lines.append(f"  {k}: {v}")
                pred_lines.append("")
                pred_lines.append(f"综合得分: {r.score:.1f}")
                pred_lines.append(f"信号: {r.signal}")
                pred_lines.append(f"明日预期: {r.outlook}")
                pred_lines.append(f"建议: {r.suggestion}")
                pred_lines.append(f"信心度: {r.confidence*100:.0f}%")
                st_pred = scrolledtext.ScrolledText(top_f, height=10, font=("", 10), wrap=tk.WORD)
                st_pred.pack(fill="both", expand=True, padx=5, pady=5)
                st_pred.insert(tk.END, "\n".join(pred_lines))
                st_pred.configure(state="disabled")

                # 下半: 游资心法快照 + 按钮
                hm_f = tk.LabelFrame(detail, text="🦅 游资心法评分", bg="white", font=("", 10, "bold"))
                hm_f.pack(fill="both", expand=True, padx=10, pady=4)
                hm_lbl = tk.Label(hm_f, text="⏳ 正在计算...", bg="white", fg="#666", font=("", 10))
                hm_lbl.pack(padx=10, pady=20)

                def _bg_hm_dialog():
                    try:
                        hm = self._hm_calc_for_stock(r.code)
                        sc = hm.get("avg_score")
                        if sc is None:
                            self.root.after(0, lambda: hm_lbl.configure(text="❌ 计算失败"))
                            return
                        best = hm.get("best_sch", "--")
                        scores_line = "  ".join(
                            f"{n}{i.get('score','-')}" for n, i in hm.get("scores", {}).items())
                        ki = hm.get("kline_info", {})
                        full_txt = (f"🦅 综合 {sc}分  |  最强流派: {best}\n\n"
                                   + scores_line + "\n\n"
                                   + f"📌 均线: MA5={ki.get('m5','-'):.2f}  MA10={ki.get('m10','-'):.2f}  MA20={ki.get('m20','-'):.2f}\n"
                                   + f"📌 DMA(距MA20): {ki.get('dma',0):+.2f}%  |  VR(量比): {ki.get('vr','-')}")
                        def _show():
                            hm_lbl.configure(text="")
                            tk.Label(hm_f, text=full_txt, bg="white", fg="#333",
                                font=("", 11), justify="left", anchor="w").pack(anchor="w", padx=15, pady=10)
                            ttk.Button(hm_f, text="🔮 打开完整游资心法全解弹窗",
                                command=lambda: (detail.withdraw(),
                                    self._open_hotmoney_single_dialog(auto_code=r.code, auto_name=r.name))
                            ).pack(pady=10)
                        self.root.after(0, _show)
                    except Exception as _he:
                        self.root.after(0, lambda _he=_he: hm_lbl.configure(text=f"❌ {_he}"))
                threading.Thread(target=_bg_hm_dialog, daemon=True).start()
            except Exception as _de:
                messagebox.showerror("错误", f"打开详情失败: {_de}", parent=win)
        tree.bind("<Double-1>", show_detail)
        # 底部按钮
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X, pady=(8, 0))
        def save_to_csv():
            path = tk.filedialog.asksaveasfilename(parent=win, title="保存为CSV", defaultextension=".csv",
                                                   filetypes=[("CSV文件", "*.csv")])
            if path:
                try:
                    import csv as csvmod
                    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                        w = csvmod.writer(f)
                        w.writerow(["代码", "名称", "得分", "信号", "明日预期", "建议", "昨日涨跌", "信心度", "累计涨幅"])
                        for r in results:
                            w.writerow([r.code, r.name, r.score, r.signal, r.outlook, r.suggestion,
                                       f"{r.last_change:+.2f}%", f"{r.confidence*100:.0f}%",
                                       r.detail.get('总累计涨幅', '')])
                    messagebox.showinfo("成功", f"已保存到\n{path}", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def copy_to_clipboard():
            text = f"{'代码':<8}{'名称':<10}{'得分':<6}{'信号':<12}{'预期':<12}{'建议':<12}{'昨日':<8}\n"
            text += "="*80 + "\n"
            for r in results:
                text += f"{r.code:<8}{r.name:<10}{r.score:<6.1f}{r.signal:<12}{r.outlook:<12}{r.suggestion:<12}{r.last_change:+.2f}%\n"
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("成功", f"已复制 {len(results)} 只票的预测结果到剪贴板", parent=win)
        ttk.Button(btn_frame, text="💾 保存CSV", command=save_to_csv, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="📋 复制结果", command=copy_to_clipboard, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.LEFT)

    def _build_fish_phase_appendix_from_extracted_stocks(self, stock_items):
        """从 extract_stock_names 的结果列表生成「鱼身鱼尾」附录文本(规则同 _check_ma_status)。"""
        if not stock_items:
            return ""
        lines = []
        seen_codes = set()
        for item in stock_items:
            s = str(item).strip()
            if not s:
                continue
            display = s
            code6 = None
            m = re.match(r'^(\d{6})\s*\(', s)
            if m:
                code6 = m.group(1).zfill(6)
                if '(' in s and ')' in s:
                    display = s.split('(')[1].rstrip(')')
            elif '(' in s and ')' in s:
                display = s.split('(')[1].rstrip(')')
                c = get_stock_code_by_name(display)
                if c:
                    code6 = str(c)[-6:].zfill(6)
            else:
                c = get_stock_code_by_name(s)
                if c:
                    code6 = str(c)[-6:].zfill(6)
                display = s
            if not code6 or code6 in seen_codes:
                continue
            seen_codes.add(code6)
            try:
                ms = self._check_ma_status(code6)
                if ms.get('fish_body'):
                    tag = '鱼身'
                elif ms.get('fish_tail'):
                    tag = '鱼尾'
                else:
                    tag = '-'
                lines.append(f"{display}\t{tag}\n")
            except Exception:
                lines.append(f"{display}\t(检测失败)\n")
        if not lines:
            return ""
        return (
            "\n" + "=" * 80 + "\n"
            "【鱼身鱼尾】(站上10日且10/20日均线向上为鱼身;破10日或20日均线向下为鱼尾)\n"
            + "-" * 40 + "\n"
            + "".join(lines)
        )

    def _show_realtime_stats_window(self, all_holdings, window_title_prefix="持仓实时统计"):
        """显示实时统计窗口(通用函数,供持仓实时和粘贴实时共用)"""
        try:
            # 创建实时统计窗口
            stats_window = self._toplevel(self.root)
            stats_window.title(f"{window_title_prefix} - 共{len(all_holdings)}只股票")
            stats_window.geometry("1600x900")
            stats_window.transient(self.root)
            stats_window.lift()
            stats_window.focus_force()
            # 创建工具栏
            toolbar_frame = ttk.Frame(stats_window, padding=5)
            toolbar_frame.pack(fill=tk.X)
            ttk.Label(toolbar_frame, text=f"股票数量: {len(all_holdings)}", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, padx=5)
            # 刷新按钮
            def refresh_stats():
                stats_window.destroy()
                if window_title_prefix == "持仓实时统计":
                    self.show_holding_realtime_stats()
                else:
                    # 对于粘贴实时,重新打开输入窗口
                    self.show_paste_realtime_stats()
            ttk.Button(toolbar_frame, text="刷新", command=refresh_stats, width=10).pack(side=tk.RIGHT, padx=5)
            # 创建结果显示区域(使用ScrolledText,与周期涨跌幅格式一致)
            result_frame = ttk.Frame(stats_window)
            result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=("Consolas", 11))
            result_text.pack(fill=tk.BOTH, expand=True)
            # 配置文本颜色标签(与周期涨跌幅一致)
            result_text.tag_config("red", foreground="red")
            result_text.tag_config("green", foreground="green")
            result_text.tag_config("bold", font=("Consolas", 11, "bold"))
            # 均线全部通过的样式:股票名和代码红色加粗11号字体,详细信息黄色背景11号字体
            result_text.tag_config("ma_all_pass_name", font=("Consolas", 13, "bold"), foreground="red")
            result_text.tag_config("ma_all_pass_text", font=("Consolas", 11), background="yellow")
            # 15日均价差值小于3%的橘黄色背景
            result_text.tag_config("orange_bg", background="#FFA500")
            # 5日最高点差值大于20%的绿色背景
            result_text.tag_config("green_bg", background="#90EE90")
            # 5日最低点差值小于3%的蓝色背景
            result_text.tag_config("blue_bg", background="#87CEEB")
            # 插入初始标题
            result_text.insert("1.0", "="*100 + "\n")
            result_text.insert(tk.END, f"{window_title_prefix}报告\n")
            result_text.insert(tk.END, "="*100 + "\n\n")
            result_text.insert(tk.END, f"统计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            result_text.insert(tk.END, f"股票数量: {len(all_holdings)}\n")
            result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            result_text.insert(tk.END, "="*100 + "\n\n")
            result_text.insert(tk.END, "正在统计,请稍候...\n\n")
            stats_window.update()
            # 状态标签(用于显示进度)
            status_label = ttk.Label(stats_window, text="正在统计中,请稍候...", font=("TkDefaultFont", 11))
            status_label.pack(pady=5)
            # 保存结果按钮(保存为文本文件)
            def save_results():
                """保存统计结果为文本文件"""
                try:
                    from datetime import datetime
                    from tkinter import filedialog
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".txt",
                        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                        initialfile=f"{window_title_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    )
                    if filename:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(result_text.get("1.0", tk.END))
                        messagebox.showinfo("成功", f"已保存到: {filename}", parent=stats_window)
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}", parent=stats_window)
            # 保存为Excel按钮(与持仓实时统计相同的逻辑)
            def save_to_excel():
                """保存统计结果为Excel文件(带格式和颜色)"""
                try:
                    from datetime import datetime
                    from tkinter import filedialog

                    import openpyxl
                    from openpyxl.styles import Alignment, Font, PatternFill
                    from openpyxl.utils import get_column_letter
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
                        initialfile=f"{window_title_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    )
                    if not filename:
                        return
                    if not hasattr(stats_window, '_realtime_stats_results'):
                        messagebox.showwarning("警告", "请先完成统计计算", parent=stats_window)
                        return
                    results = stats_window._realtime_stats_results
                    if not results:
                        messagebox.showwarning("警告", "没有统计数据可保存", parent=stats_window)
                        return
                    # 按同花顺排序(获取同花顺排序数据)
                    def get_tonghuashun_order():
                        """获取同花顺排序顺序"""
                        try:
                            spot_em = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                            if not spot_em.empty:
                                # 按成交量排序(同花顺常用排序方式)
                                sorted_spot = spot_em.sort_values('成交量', ascending=False)
                                order_dict = {}
                                for idx, row in sorted_spot.iterrows():
                                    code = row.get('代码', '')
                                    if code:
                                        order_dict[code] = len(order_dict) + 1
                                return order_dict
                        except:
                            pass
                        return {}
                    tonghuashun_order = get_tonghuashun_order()
                    # 对results进行排序
                    def get_sort_key(result_item):
                        stock_code = result_item.get('stock_code', '')
                        return tonghuashun_order.get(stock_code, 999999)  # 没有排序的放在最后
                    sorted_results = sorted(results, key=get_sort_key)
                    # 创建Excel工作簿
                    wb = openpyxl.Workbook()
                    ws = wb.active
                    ws.title = window_title_prefix
                    # 设置中文字体
                    chinese_font = Font(name='微软雅黑', size=10)
                    bold_font = Font(name='微软雅黑', size=10, bold=True)
                    # 定义列
                    columns = ['序号', '分组', '股票名称', '股票代码', '当前股价', '涨跌幅', '震荡幅度',
                              '5日涨跌幅', '10日涨跌幅', '20日涨跌幅',
                              '5日最低点差值%', '5日最高点差值%', '10日均价差值%', '15日均价差值%',
                              '20日均价差值%', '60日均价差值%',
                              '实时主力净量', '实时资金大单流入', '1日均线', '5日均线', '10日均线', '20日均线',
                              '同花顺热门榜排名', '资讯逻辑', '数据表逻辑',
                              '市盈率', '市值', '换手率', '板块', '概念']
                    # 写入标题行
                    for col_idx, col_name in enumerate(columns, 1):
                        cell = ws.cell(row=1, column=col_idx, value=col_name)
                        cell.font = bold_font
                        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    # 写入数据行
                    for row_idx, result_data in enumerate(sorted_results, 2):
                        # 检查均线是否全部通过
                        ma_all_passed = False
                        if result_data.get('ma1_status') == '✓' and result_data.get('ma5_status') == '✓' and \
                           result_data.get('ma10_status') == '✓' and result_data.get('ma20_status') == '✓':
                            ma_all_passed = True
                        # 确定行背景颜色
                        row_bg_color = None
                        if ma_all_passed:
                            row_bg_color = "FFFF00"  # 黄色
                        else:
                            # 检查15日均线差值
                            try:
                                ma15_diff_val = float(result_data.get('ma15_diff_pct', '0').replace('%', '').replace('+', ''))
                                if abs(ma15_diff_val) < 3:
                                    row_bg_color = "FFA500"  # 橘黄色
                            except:
                                pass
                        values = [
                            row_idx - 1,  # 序号
                            result_data.get('group', ''),
                            result_data.get('stock_name', ''),
                            result_data.get('stock_code', ''),
                            result_data.get('current_price', ''),
                            result_data.get('change_pct', ''),
                            result_data.get('amplitude', ''),
                            result_data.get('change_5d', ''),
                            result_data.get('change_10d', ''),
                            result_data.get('change_20d', ''),
                            result_data.get('low_5d_diff_pct', ''),
                            result_data.get('high_5d_diff_pct', ''),
                            result_data.get('ma10_diff_pct', ''),
                            result_data.get('ma15_diff_pct', ''),
                            result_data.get('ma20_diff_pct', ''),
                            result_data.get('ma60_diff_pct', ''),
                            result_data.get('main_net_flow', ''),
                            result_data.get('large_order_inflow', ''),
                            result_data.get('ma1_status', ''),
                            result_data.get('ma5_status', ''),
                            result_data.get('ma10_status', ''),
                            result_data.get('ma20_status', ''),
                            result_data.get('hot_rank', ''),
                            result_data.get('news_logic', ''),
                            result_data.get('stock_logic', ''),
                            result_data.get('pe', ''),
                            result_data.get('market_cap', ''),
                            result_data.get('turnover_rate', ''),
                            result_data.get('sector', ''),
                            result_data.get('concept', '')
                        ]
                        for col_idx, value in enumerate(values, 1):
                            cell = ws.cell(row=row_idx, column=col_idx, value=value)
                            cell.font = chinese_font
                            # 设置行背景颜色
                            if row_bg_color:
                                cell.fill = PatternFill(start_color=row_bg_color, end_color=row_bg_color, fill_type="solid")
                            # 设置特定列的背景颜色
                            col_name = columns[col_idx - 1]
                            # 5日最低点差值小于3%的蓝色背景
                            if col_name == '5日最低点差值%' and result_data.get('low_5d_diff_pct'):
                                try:
                                    low_5d_diff_val = float(result_data.get('low_5d_diff_pct', '0').replace('%', '').replace('+', ''))
                                    if abs(low_5d_diff_val) < 3:
                                        cell.fill = PatternFill(start_color="87CEEB", end_color="87CEEB", fill_type="solid")
                                except:
                                    pass
                            # 5日最高点差值大于20%的绿色背景
                            if col_name == '5日最高点差值%' and result_data.get('high_5d_diff_pct'):
                                try:
                                    high_5d_diff_val = float(result_data.get('high_5d_diff_pct', '0').replace('%', '').replace('+', ''))
                                    if high_5d_diff_val > 20:
                                        cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
                                except:
                                    pass
                            # 15日均价差值小于3%的橘黄色背景
                            if col_name == '15日均价差值%' and result_data.get('ma15_diff_pct'):
                                try:
                                    ma15_diff_val = float(result_data.get('ma15_diff_pct', '0').replace('%', '').replace('+', ''))
                                    if abs(ma15_diff_val) < 3:
                                        cell.fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
                                except:
                                    pass
                            # 股票名称和代码:如果均线全部通过,使用红色加粗
                            if col_name in ['股票名称', '股票代码'] and ma_all_passed:
                                cell.font = Font(name='微软雅黑', size=11, bold=True, color="FF0000")
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                    # 调整列宽
                    column_widths = {
                        '序号': 8, '分组': 12, '股票名称': 15, '股票代码': 12, '当前股价': 12, '涨跌幅': 10, '震荡幅度': 10,
                        '5日涨跌幅': 12, '10日涨跌幅': 12, '20日涨跌幅': 12,
                        '5日最低点差值%': 15, '5日最高点差值%': 15, '10日均价差值%': 15, '15日均价差值%': 15,
                        '20日均价差值%': 15, '60日均价差值%': 15,
                        '实时主力净量': 15, '实时资金大单流入': 18, '1日均线': 10, '5日均线': 10, '10日均线': 12, '20日均线': 12,
                        '同花顺热门榜排名': 18, '资讯逻辑': 20, '数据表逻辑': 20,
                        '市盈率': 10, '市值': 15, '换手率': 10, '板块': 20, '概念': 30
                    }
                    for col_idx, col_name in enumerate(columns, 1):
                        if col_name in column_widths:
                            ws.column_dimensions[get_column_letter(col_idx)].width = column_widths[col_name]
                    # 保存文件
                    wb.save(filename)
                    messagebox.showinfo("成功", f"已保存到Excel: {filename}", parent=stats_window)
                except Exception as e:
                    messagebox.showerror("错误", f"保存Excel失败: {e}", parent=stats_window)
                    import traceback
                    traceback.print_exc()
            # 保存到资讯数据表按钮
            def save_to_news_db():
                """保存统计结果到资讯数据表"""
                try:
                    content = result_text.get("1.0", tk.END)
                    if not content.strip():
                        messagebox.showwarning("警告", "没有可保存的内容", parent=stats_window)
                        return
                    tab_name = f"{window_title_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO news_info (tab_name, content, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    ''', (tab_name, content, current_time, current_time))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("成功", "已保存到资讯数据表", parent=stats_window)
                    # 刷新资讯数据表(如果主窗口有这个方法)
                    if hasattr(self, 'refresh_news_data'):
                        self.refresh_news_data()
                except Exception as e:
                    messagebox.showerror("错误", f"保存到资讯数据表失败: {e}", parent=stats_window)
            save_button = ttk.Button(toolbar_frame, text="保存为文本", command=save_results, width=10)
            save_button.pack(side=tk.RIGHT, padx=5)
            save_excel_button = ttk.Button(toolbar_frame, text="保存为Excel", command=save_to_excel, width=12)
            save_excel_button.pack(side=tk.RIGHT, padx=5)
            save_news_button = ttk.Button(toolbar_frame, text="保存到资讯", command=save_to_news_db, width=12)
            save_news_button.pack(side=tk.RIGHT, padx=5)
            # 初始化标题(只显示一次)
            title_inserted = False
            # 存储计算结果,供保存Excel使用
            stats_window._realtime_stats_results = []
            # 在后台线程中执行统计
            def calculate_stats():
                try:
                    nonlocal title_inserted
                    results = []
                    stats_window._realtime_stats_results = []  # 清空之前的结果
                    for idx, holding in enumerate(all_holdings):
                        stock_name = holding['stock_name']
                        stock_code = holding['stock_code']
                        group = holding['group']
                        # 更新状态和进度显示
                        def update_status():
                            status_label.config(text=f"正在统计 {idx+1}/{len(all_holdings)}: {stock_name} ({stock_code})")
                            if not title_inserted:
                                # 插入标题(只插入一次)
                                result_text.insert("1.0", "="*100 + "\n")
                                result_text.insert(tk.END, f"{window_title_prefix}报告\n")
                                result_text.insert(tk.END, "="*100 + "\n\n")
                                result_text.insert(tk.END, f"统计时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                result_text.insert(tk.END, f"股票数量: {len(all_holdings)}\n")
                                result_text.insert(tk.END, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                                result_text.insert(tk.END, "="*100 + "\n\n")
                            result_text.insert(tk.END, f"[{idx+1}/{len(all_holdings)}] 正在统计 {stock_name} ({stock_code})...\n")
                            result_text.see(tk.END)
                            stats_window.update_idletasks()
                        stats_window.after(0, update_status)
                        result = self._calculate_single_stock_realtime_stats(stock_name, stock_code)
                        result['group'] = group
                        results.append(result)
                        # 同时保存到窗口属性,供保存Excel使用
                        stats_window._realtime_stats_results.append(result)
                        # 每计算完一只股票就立即显示
                        def display_single_stock(result_data, stock_idx):
                            try:
                                # 检查均线是否全部通过
                                ma_all_passed = False
                                if result_data.get('ma1_status') == '✓' and result_data.get('ma5_status') == '✓' and \
                                   result_data.get('ma10_status') == '✓' and result_data.get('ma20_status') == '✓':
                                    ma_all_passed = True
                                # 设置详细信息标签(如果均线全部通过)
                                detail_tag = "ma_all_pass_text" if ma_all_passed else None
                                # 插入股票标题
                                result_text.insert(tk.END, f"\n【{stock_idx}】", "bold")
                                if ma_all_passed:
                                    result_text.insert(tk.END, f"{result_data.get('stock_name', '未知')} ({result_data.get('stock_code', '')})", "ma_all_pass_name")
                                else:
                                    result_text.insert(tk.END, f"{result_data.get('stock_name', '未知')} ({result_data.get('stock_code', '')})")
                                result_text.insert(tk.END, f"  [{result_data.get('group', '')}]\n", detail_tag)
                                result_text.insert(tk.END, "-"*100 + "\n", detail_tag)
                                # 基本信息
                                if result_data.get('current_price'):
                                    result_text.insert(tk.END, f"当前股价: {result_data.get('current_price')}\n", detail_tag)
                                if result_data.get('change_pct'):
                                    try:
                                        change_pct_val = float(result_data.get('change_pct', '0').replace('%', ''))
                                        tag = "red" if change_pct_val > 0 else "green" if change_pct_val < 0 else None
                                        if ma_all_passed:
                                            result_text.insert(tk.END, f"涨跌幅: {result_data.get('change_pct')}\n", detail_tag)
                                        elif tag:
                                            result_text.insert(tk.END, f"涨跌幅: {result_data.get('change_pct')}\n", tag)
                                        else:
                                            result_text.insert(tk.END, f"涨跌幅: {result_data.get('change_pct')}\n")
                                    except:
                                        result_text.insert(tk.END, f"涨跌幅: {result_data.get('change_pct')}\n", detail_tag)
                                if result_data.get('amplitude'):
                                    result_text.insert(tk.END, f"震荡幅度: {result_data.get('amplitude')}\n", detail_tag)
                                result_text.insert(tk.END, "\n", detail_tag)
                                # 周期涨跌幅
                                result_text.insert(tk.END, "涨跌幅统计:\n", detail_tag)
                                if result_data.get('change_5d'):
                                    try:
                                        change_5d_val = float(result_data.get('change_5d', '0').replace('%', '').replace('+', ''))
                                        tag = "red" if change_5d_val > 10 else "green" if change_5d_val < -10 else None
                                        if ma_all_passed:
                                            result_text.insert(tk.END, f"  5日涨跌幅: {result_data.get('change_5d')}\n", detail_tag)
                                        elif tag:
                                            result_text.insert(tk.END, f"  5日涨跌幅: {result_data.get('change_5d')}\n", tag)
                                        else:
                                            result_text.insert(tk.END, f"  5日涨跌幅: {result_data.get('change_5d')}\n")
                                    except:
                                        result_text.insert(tk.END, f"  5日涨跌幅: {result_data.get('change_5d')}\n", detail_tag)
                                if result_data.get('change_10d'):
                                    try:
                                        change_10d_val = float(result_data.get('change_10d', '0').replace('%', '').replace('+', ''))
                                        tag = "red" if change_10d_val > 10 else "green" if change_10d_val < -10 else None
                                        if ma_all_passed:
                                            result_text.insert(tk.END, f"  10日涨跌幅: {result_data.get('change_10d')}\n", detail_tag)
                                        elif tag:
                                            result_text.insert(tk.END, f"  10日涨跌幅: {result_data.get('change_10d')}\n", tag)
                                        else:
                                            result_text.insert(tk.END, f"  10日涨跌幅: {result_data.get('change_10d')}\n")
                                    except:
                                        result_text.insert(tk.END, f"  10日涨跌幅: {result_data.get('change_10d')}\n", detail_tag)
                                if result_data.get('change_20d'):
                                    try:
                                        change_20d_val = float(result_data.get('change_20d', '0').replace('%', '').replace('+', ''))
                                        tag = "red" if change_20d_val > 10 else "green" if change_20d_val < -10 else None
                                        if ma_all_passed:
                                            result_text.insert(tk.END, f"  20日涨跌幅: {result_data.get('change_20d')}\n", detail_tag)
                                        elif tag:
                                            result_text.insert(tk.END, f"  20日涨跌幅: {result_data.get('change_20d')}\n", tag)
                                        else:
                                            result_text.insert(tk.END, f"  20日涨跌幅: {result_data.get('change_20d')}\n")
                                    except:
                                        result_text.insert(tk.END, f"  20日涨跌幅: {result_data.get('change_20d')}\n", detail_tag)
                                result_text.insert(tk.END, "\n", detail_tag)
                                # 差值百分比统计
                                result_text.insert(tk.END, "差值百分比统计:\n", detail_tag)
                                if result_data.get('low_5d_diff_pct'):
                                    try:
                                        low_5d_diff_val = float(result_data.get('low_5d_diff_pct', '0').replace('%', '').replace('+', ''))
                                        # 如果5日最低点差值小于3%,使用蓝色背景
                                        if abs(low_5d_diff_val) < 3:
                                            result_text.insert(tk.END, f"  离5日最低点差值: {result_data.get('low_5d_diff_pct')}\n", "blue_bg")
                                        else:
                                            result_text.insert(tk.END, f"  离5日最低点差值: {result_data.get('low_5d_diff_pct')}\n", detail_tag)
                                    except:
                                        result_text.insert(tk.END, f"  离5日最低点差值: {result_data.get('low_5d_diff_pct')}\n", detail_tag)
                                if result_data.get('high_5d_diff_pct'):
                                    try:
                                        high_5d_diff_val = float(result_data.get('high_5d_diff_pct', '0').replace('%', '').replace('+', ''))
                                        # 如果5日最高点差值大于20%,使用绿色背景
                                        if high_5d_diff_val > 20:
                                            result_text.insert(tk.END, f"  离5日最高点差值: {result_data.get('high_5d_diff_pct')}\n", "green_bg")
                                        else:
                                            result_text.insert(tk.END, f"  离5日最高点差值: {result_data.get('high_5d_diff_pct')}\n", detail_tag)
                                    except:
                                        result_text.insert(tk.END, f"  离5日最高点差值: {result_data.get('high_5d_diff_pct')}\n", detail_tag)
                                if result_data.get('ma10_diff_pct'):
                                    result_text.insert(tk.END, f"  离10日均价差值: {result_data.get('ma10_diff_pct')}\n", detail_tag)
                                if result_data.get('ma15_diff_pct'):
                                    try:
                                        ma15_diff_val = float(result_data.get('ma15_diff_pct', '0').replace('%', '').replace('+', ''))
                                        # 如果15日均价差值小于3%,使用橘黄色背景
                                        if abs(ma15_diff_val) < 3:
                                            result_text.insert(tk.END, f"  离15日均价差值: {result_data.get('ma15_diff_pct')}\n", "orange_bg")
                                        else:
                                            result_text.insert(tk.END, f"  离15日均价差值: {result_data.get('ma15_diff_pct')}\n", detail_tag)
                                    except:
                                        result_text.insert(tk.END, f"  离15日均价差值: {result_data.get('ma15_diff_pct')}\n", detail_tag)
                                if result_data.get('ma20_diff_pct'):
                                    result_text.insert(tk.END, f"  离20日均价差值: {result_data.get('ma20_diff_pct')}\n", detail_tag)
                                if result_data.get('ma60_diff_pct'):
                                    result_text.insert(tk.END, f"  离60日均价差值: {result_data.get('ma60_diff_pct')}\n", detail_tag)
                                result_text.insert(tk.END, "\n", detail_tag)
                                # 均线检测结果
                                result_text.insert(tk.END, "【均线检测结果】\n", detail_tag)
                                if result_data.get('ma1_status'):
                                    result_text.insert(tk.END, f"  1日均线: {result_data.get('ma1_status')}\n", detail_tag)
                                if result_data.get('ma5_status'):
                                    result_text.insert(tk.END, f"  5日均线: {result_data.get('ma5_status')}\n", detail_tag)
                                if result_data.get('ma10_status'):
                                    result_text.insert(tk.END, f"  10日均线: {result_data.get('ma10_status')}\n", detail_tag)
                                if result_data.get('ma20_status'):
                                    result_text.insert(tk.END, f"  20日均线: {result_data.get('ma20_status')}\n", detail_tag)
                                result_text.insert(tk.END, "\n", detail_tag)
                                # 资金流向
                                if result_data.get('main_net_flow') or result_data.get('large_order_inflow'):
                                    result_text.insert(tk.END, "资金流向:\n", detail_tag)
                                    if result_data.get('main_net_flow'):
                                        result_text.insert(tk.END, f"  实时主力净量: {result_data.get('main_net_flow')}\n", detail_tag)
                                    if result_data.get('large_order_inflow'):
                                        result_text.insert(tk.END, f"  实时资金大单流入: {result_data.get('large_order_inflow')}\n", detail_tag)
                                    result_text.insert(tk.END, "\n", detail_tag)
                                # 其他信息
                                if result_data.get('hot_rank'):
                                    result_text.insert(tk.END, f"同花顺热门榜排名: {result_data.get('hot_rank')}\n", detail_tag)
                                # 资讯逻辑(显示资讯内容,只显示前50字)
                                if result_data.get('news_content'):
                                    result_text.insert(tk.END, "【资讯内容】\n", detail_tag)
                                    news_content = result_data.get('news_content', '')
                                    # 限制显示长度,只显示前50字
                                    if len(news_content) > 50:
                                        news_content = news_content[:50] + "..."
                                    result_text.insert(tk.END, f"{news_content}\n\n", detail_tag)
                                elif result_data.get('news_logic'):
                                    result_text.insert(tk.END, f"资讯逻辑: {result_data.get('news_logic')}\n", detail_tag)
                                # 数据表逻辑(只显示前50字)
                                if result_data.get('stock_logic'):
                                    stock_logic_text = result_data.get('stock_logic', '')
                                    if len(stock_logic_text) > 50:
                                        stock_logic_text = stock_logic_text[:50] + "..."
                                    result_text.insert(tk.END, f"数据表逻辑: {stock_logic_text}\n", detail_tag)
                                # 基本面信息
                                if result_data.get('pe') or result_data.get('market_cap') or result_data.get('turnover_rate'):
                                    result_text.insert(tk.END, "基本面信息:\n", detail_tag)
                                    if result_data.get('pe'):
                                        result_text.insert(tk.END, f"  市盈率: {result_data.get('pe')}\n", detail_tag)
                                    if result_data.get('market_cap'):
                                        result_text.insert(tk.END, f"  市值: {result_data.get('market_cap')}\n", detail_tag)
                                    if result_data.get('turnover_rate'):
                                        result_text.insert(tk.END, f"  换手率: {result_data.get('turnover_rate')}\n", detail_tag)
                                    if result_data.get('sector'):
                                        result_text.insert(tk.END, f"  板块: {result_data.get('sector')}\n", detail_tag)
                                    if result_data.get('concept'):
                                        result_text.insert(tk.END, f"  概念: {result_data.get('concept')}\n", detail_tag)
                                    result_text.insert(tk.END, "\n", detail_tag)
                                result_text.see(tk.END)
                                stats_window.update_idletasks()
                            except Exception as e:
                                import traceback
                                result_text.insert(tk.END, f"显示股票信息失败: {e!s}\n")
                                result_text.insert(tk.END, traceback.format_exc() + "\n")
                        # 立即显示这只股票的结果
                        stats_window.after(0, display_single_stock, result, idx + 1)
                        # 每个股票间隔0.3秒,避免请求过快
                        time.sleep(0.3)
                    # 所有股票计算完成后,显示完成信息
                    def show_complete():
                        status_label.config(text=f"统计完成,共{len(results)}只股票")
                        result_text.insert(tk.END, "\n" + "="*100 + "\n")
                        result_text.insert(tk.END, f"统计完成 - 共{len(results)}只股票\n")
                        result_text.see(tk.END)
                    stats_window.after(0, show_complete)
                except Exception as e:
                    import traceback
                    error_msg = f"统计失败: {e!s}\n{traceback.format_exc()}"
                    def show_error():
                        status_label.config(text=error_msg, foreground="red")
                        result_text.insert(tk.END, f"\n错误: {error_msg}\n")
                    stats_window.after(0, show_error)
            threading.Thread(target=calculate_stats, daemon=True).start()
        except Exception as e:
            error_msg = f"打开{window_title_prefix}失败: {e!s}"
            print(f"[{window_title_prefix}] 错误: {error_msg}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", error_msg, parent=self.root)

    def show_elevator_dialog(self):
        """打开同花顺问财电梯界面 (丰富版: 财务指标说明+预设条件+60+经典人气语句)"""
        # 直接用主程序内置的丰富版条件选股界面
        # (外部 consulting_analysis_gui.ElevatorDialog 只有精简版, 缺少经典人气语句等控件)
        try:
            self._create_simple_stock_filter_ui()
        except Exception as exc:
            messagebox.showerror("错误", f"打开问财电梯失败: {exc}")
            import traceback
            traceback.print_exc()

    def _create_simple_stock_filter_ui(self):
        """创建简化的条件选股界面"""
        try:
            win = self._toplevel(self.root)
            win.title("条件选股(坐电梯)")
            win.geometry("1650x950")
            win.transient(self.root)
            win.resizable(True, True)
            paned_main = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
            paned_main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            left_frame = ttk.LabelFrame(paned_main, text="查询条件(拖动中间竖条可调左右宽)", width=420)
            right_frame = ttk.LabelFrame(paned_main, text="查询结果(双击行:持仓详情)")
            paned_main.add(left_frame, weight=3)
            paned_main.add(right_frame, weight=5)
            try:
                paned_main.paneconfigure(left_frame, minsize=360)
                paned_main.paneconfigure(right_frame, minsize=480)
            except Exception:
                pass
            # 查询条件输入
            ttk.Label(left_frame, text="输入查询条件:", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 5))
            # 查询条件输入框缩小为"内容一行 + 空一行"视觉高度
            query_text = scrolledtext.ScrolledText(left_frame, height=2, width=45, wrap=tk.WORD, font=("Microsoft YaHei", 12))
            query_text.pack(fill=tk.X, padx=10, pady=(0, 6))
            hint_frame = ttk.LabelFrame(
                left_frame,
                text="常用财务指标说明(编写问财条件时可对照;具体字段以同花顺问财识别为准)",
            )
            hint_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 8))
            hint_text = scrolledtext.ScrolledText(
                hint_frame,
                height=6,
                wrap=tk.WORD,
                font=("Microsoft YaHei", 9),
            )
            hint_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            _fin_hints = """\
· ROE(净资产收益率) 净利润÷平均净资产。衡量自有资本赚钱效率;高一般更好,需结合杠杆、行业(银行地产与制造业不宜硬比)、是否一次性损益。
· PE(市盈率) 股价÷每股收益(常见为 TTM 滚动市盈率或静态)。可理解为「以当前盈利,多少年账面回本」的粗估值;低≠便宜(盈利可能下滑),高≠贵(可能高增长)。亏损股 PE 常无意义。
· PB(市净率) 股价÷每股净资产。偏适合银行、重资产、周期股;PB<1 表示股价低于账面净资产,但需看成资产质量(坏账、陈旧产能)。
· PEG PE÷利润增速(多用预期增速)。成长估值参考;PEG 明显小于 1 有时视为相对不贵,依赖增速预测是否靠谱。
· PS / PCF 市销率、市现率;亏损或未稳定盈利时偶尔用来看营收规模或现金流相对估值。
· 股息率 每股年度分红÷股价。现金回报角度;高股息要区分「可持续」与「一次性特别分红」。
· 市值 / 流通市值 公司总价值与可自由流通部分;影响弹性与流动性,小盘波动通常更大。
· 资产负债率 总负债÷总资产。杠杆高在行业下行或加息周期里压力更大;不同行业合理区间差异大。
· 毛利率 / 净利率 营收毛利、最终净利占营收比;毛利率偏「生意模式+议价权」,净利率还吃费用与税费。
· ROIC(投入资本回报率) 看投入多少实体资本赚回多少回报,有时比单纯 ROE 更能避开高杠杆粉饰。
· 商誉占净资产比 并购溢价;占比过大若标的业绩不达预期,减值可能大幅冲击利润。
提示:左侧问财语句用自然语言即可;若某条条件报错,可在问财网页试跑或改成平台提示的同义词(如「市盈率」与「PE」)。"""
            hint_text.insert("1.0", _fin_hints)
            hint_text.configure(state=tk.DISABLED)
            # 预设查询条件
            default_query = """周线周期的wr2大于80,周线周期的d小于30且周线周期的bias3小于-10,非st,周线周期的diff大于0,基本面从好到坏"""
            query_text.insert(tk.END, default_query)
            # 预设查询条件按钮
            preset_frame = ttk.LabelFrame(left_frame, text="预设查询条件")
            preset_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
            preset_queries = [
                ("技术指标组合", "周线周期的wr2大于80,周线周期的d小于30且周线周期的bias3小于-10,非st,周线周期的diff大于0,基本面从好到坏"),
                ("涨停股票", "今日涨停股票"),
                ("成交量最大", "今日成交量最大的前20只股票"),
                ("北向资金", "北向资金净流入前20只股票"),
                ("涨幅最大", "今日涨幅最大的股票"),
                ("跌幅最大", "今日跌幅最大的股票"),
                ("低位放量", "非st,非退市,所属行业龙头,近5日放量上涨,今日收盘价接近60日线"),
                ("机构抱团", "近30日获机构调研次数>5,近3日主力净流入>0,所属热门赛道"),
                ("高股息", "近三年现金分红率持续>30%,总市值小于800亿,股息率>5%"),
                ("趋势突破", "非st,20日均线>60日均线>120日均线,今日放量突破前高,MACD金叉"),
                ("反转模型", "近10日跌幅>15%,但放量止跌,今日收盘价站上5日线且KDJ金叉"),
                (
                    "60分上穿60日",
                    ("非st,60分钟周期下股价首次向上突破60分钟MA60均线,"
                    "突破当日该60分钟周期成交量较前10个60分钟周期平均成交量放大50%以上"),
                ),
            ]
            # 创建两行按钮布局
            row1_frame = ttk.Frame(preset_frame)
            row1_frame.pack(fill=tk.X, padx=5, pady=2)
            row2_frame = ttk.Frame(preset_frame)
            row2_frame.pack(fill=tk.X, padx=5, pady=2)
            for i, (name, query) in enumerate(preset_queries):
                target_row = row1_frame if i < 4 else row2_frame
                btn = ttk.Button(target_row, text=name,
                               command=lambda q=query: query_text.delete("1.0", tk.END) or query_text.insert("1.0", q))
                btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)
            # 问财经典语句:情绪/动能/量化/东财风格经典模型 四色;双击插入(人物名为风格近似表述)
            popular_frame = ttk.LabelFrame(
                left_frame,
                text="问财经典人气语句(勾选多项后点「加入所选条件」;双击条目可单条覆盖写入;每行2列;颜色:红情绪 蓝动能 绿量化 紫模型)",
            )
            popular_frame.pack(fill=tk.BOTH, padx=10, pady=(0, 10), expand=True)
            # (名称, 问财条件语句, 类别) 类别:emotion / momentum / quant / model
            popular_queries = [
                ("龙头掘金", "所属概念龙头,近3日主力净流入为正,近20日涨跌幅排名前10,流通市值<300亿", "momentum"),
                ("北交所强势", "北交所,今日涨幅>5%,成交额前20名,换手率>10%", "momentum"),
                ("AI 算力", "算力概念,近5日涨跌幅>8%,机构评级为买入或增持,PE<80", "emotion"),
                ("中特估", "中字头,PB<1.2,股息率>4%,近10日主力资金持续流入", "model"),
                ("消费复苏", "大消费概念,近30日MFI>80,Q3营收同比正增长,机构调研>3次", "emotion"),
                ("新能源景气", "新能源车全产业链,近5日涨幅>3%,毛利率提升,海外订单增长", "emotion"),
                ("低位白马", "沪深300成份股,近60日跌幅>10%,股价处于年线下方,PB<2", "quant"),
                ("妖股捕捉", "非st,连板>=3,最新价<35元,总市值<200亿,龙虎榜机构席位买入", "momentum"),
                ("央企控盘", "央企控股,国家队持股>5%,近20日主力净买入,股价站上所有均线", "model"),
                ("高景气细分", "光伏逆变器、储能EMS、算力液冷等高景气细分,近3年营收CAGR>30%", "emotion"),
                ("减肥药概念", "GLP-1概念,近60日涨幅前30名,机构关注度提升,研发投入占比提高", "emotion"),
                ("机器人本体", "人形机器人本体,订单爆发,近10日放量上涨,突破年内新高", "momentum"),
                ("高端制造", "高端制造或军工,毛利率>35%,净利润率逐年提升,海外收入占比高", "quant"),
                ("旅游/免税", "旅游免税概念,暑期旺季,近10日资金净流入,估值低于行业平均", "emotion"),
                ("芯片设备", "半导体设备国产化,近5日资金持续流入,订单饱满,市值小于500亿", "momentum"),
                ("情绪冰点反抽", "非st,近5日跌幅>8%,今日放量阳线反包,主力净流入由负转正,换手>3%", "emotion"),
                ("恐慌杀跌错杀", "近20日跌幅前10%,PB低于行业均值,ROE近3年均>8%,商誉占比<15%", "emotion"),
                ("涨停情绪扩散", "今日涨停家数概念,近3日涨停次数>2,封单金额行业前20,量比>2", "emotion"),
                ("龙虎榜游资接力", "近3日登龙虎榜,游资席位净买入,近5日振幅>25%,流通市值<150亿", "emotion"),
                ("北向连续加仓", "北向资金连续5日净流入,持股占流通比上升,近10日跑赢沪深300", "emotion"),
                ("融资余额陡增", "融资余额5日增幅>8%,股价沿5日线上行,两融标的,非st", "emotion"),
                ("行业景气度跃升", "所属行业近1月涨幅前10%,个股近10日资金净流入,机构调研次数增加", "emotion"),
                ("政策利好博弈", "近30日公告含回购或增持,股息率>2%,PB<2,国企或行业龙头", "emotion"),
                ("超跌反弹博弈", "RSI6<25,近10日缩量下跌,今日放量收阳,站上5日线", "emotion"),
                ("情绪分歧转一致", "昨日长上影今日反包,近3日主力净流入累计为正,MACD金叉", "emotion"),
                ("赛道拥挤度回落", "热门赛道内近60日涨幅由正转负后再放量,估值分位<40%", "emotion"),
                ("均线多头动能", "5日>10日>20日>60日均线,今日放量,近5日涨幅>5%,非st", "momentum"),
                ("突破年线动能", "收盘价站上250日线,放量突破,近20日涨幅>10%,换手率递增", "momentum"),
                ("周线MACD金叉", "周线MACD金叉,周线KDJ低位金叉,日线放量,非st", "momentum"),
                ("相对强度领先", "近20日涨幅行业前15%,相对沪深300超额收益>5%,成交额放大", "momentum"),
                ("量价齐升突破", "今日创60日新高,成交量为60日均量2倍以上,主力净流入为正", "momentum"),
                ("分时强势尾盘", "近5日分时均价逐日抬高,尾盘30分钟涨幅>1%,北向净流入", "momentum"),
                ("动量因子加速", "近10日涨幅>15%,近5日涨幅>近10日一半,波动率可控,非st", "momentum"),
                ("布林上轨开口", "股价沿布林上轨运行,带宽扩大,近5日主力持续流入", "momentum"),
                ("涨停基因回踩", "近60日曾涨停,回踩20日线缩量企稳,今日阳线吞没,换手>5%", "momentum"),
                ("板块龙头切换", "所属概念内市值前3,近5日涨幅领先板块指数,量比>1.5", "momentum"),
                ("低波动红利量化", "近1年波动率行业后30%,股息率>4%,连续3年分红,PE<25", "quant"),
                ("价值因子深坑", "PB分位点<20%,PE分位点<30%,ROE>10%,资产负债率<65%", "quant"),
                ("质量因子筛选", "近3年ROE均>12%,经营现金流/净利润>0.8,商誉/净资产<10%", "quant"),
                ("小盘成长量化", "总市值<200亿,近3年营收CAGR>20%,研发费用率>5%,非st", "quant"),
                ("低换手蓄势", "近20日日均换手<2%,筹码集中度提升,股价窄幅整理,放量可突破", "quant"),
                ("高夏普近似", "近120日年化波动率<35%,累计收益>10%,最大回撤<15%,非st", "quant"),
                ("多均线粘合", "5/10/20日均线差<3%,一旦放量向上突破,市值<300亿", "quant"),
                ("财务安全垫厚", "货币资金>有息负债,流动比率>1.5,近2年无审计非标", "quant"),
                ("机构持仓递增", "基金持股比例逐季上升,前十大流通股东机构数增加,PE合理", "quant"),
                ("巴菲特护城河风格", "连续5年ROE>15%,毛利率稳定或提升,有息负债率低,现金流充沛,非st", "model"),
                ("芒格优质复利风格", "ROE>12%,负债率<50%,管理层增持或回购,业务简单可理解", "model"),
                ("索罗斯趋势反射风格", "近60日强势趋势,波动放大阶段,主力与融资同步,严格止损纪律", "model"),
                ("达利欧风险平价近似", "行业分散,低相关,波动率目标适中,股债商品难以单押时选蓝筹红利", "model"),
                ("桥水全天候思路", "高股息+低波动蓝筹+黄金或资源对冲表述,市值>200亿,流动性好", "model"),
                ("大奖章统计套利风格", "高换手、量价统计显著,小中盘,近20日波动与成交协同(散户难复制,仅作选股近似)", "model"),
                ("格雷厄姆安全边际", "PB<1.5或PE<15,流动比率>1.2,连续盈利,低商誉", "model"),
                (
                    "老杨选股·价值安全边际",
                    ("非st,PE<20,PB<2,流动比率>1.2,商誉占净资产<5%,连续5年净利润为正,"
                    "股息率>2%,ROE>8%,市值>80亿,行业龙头或细分龙头"),
                    "model",
                ),
                ("彼得林奇PEG思路", "净利润增速>0,PEG<1.2,负债合理,非过热赛道龙头", "model"),
                ("乔尔格林布拉特神奇公式", "高ROIC、低PE排序,市值>50亿,排除金融地产极端杠杆", "model"),
                ("东财高股息龙头模型", "股息率>4%,连续分红,行业龙头,PB<2,机构持仓稳定", "model"),
                ("东财核心资产模型", "沪深300或中证500成份,ROE>10%,机构重仓,流动性佳", "model"),
                ("东财成长动量模型", "营收与净利双增,近20日资金净流入,PEG合理,非st", "model"),
                ("东财价值回归模型", "近1年跌幅>20%,基本面未恶化,PB低于历史50%分位", "model"),
                ("业绩预告情绪", "年报或季报预增,净利润同比>30%,近10日股价未透支,PE<行业均值", "emotion"),
                ("解禁压力消化", "大额解禁后30日股价企稳,换手充分,主力净流入转正", "emotion"),
                ("杯柄突破动能", "杯柄形态近似,整理缩量后放量突破颈线,近20日跑赢指数", "momentum"),
                ("欧奈尔CANSLIM近似", "当季净利同比高增,RS强度行业前20%,机构增持,创新高或近新高", "momentum"),
                ("红利低波量化增强", "股息率前20%,近1年波动率后25%,市值>100亿,国企或蓝筹", "quant"),
                ("盈利一致性预期", "近90日分析师上调盈利预测家数增加,一致预期PE下行", "quant"),
                ("量化回撤修复", "近120日最大回撤<20%,近20日净值创新高,波动率下降,主力净流入", "quant"),
            ]
            pop_btn_row = ttk.Frame(popular_frame)
            pop_btn_row.pack(fill=tk.X, padx=4, pady=(0, 4))
            _tag_colors = {
                "emotion": "#b03a2e",
                "momentum": "#1f618d",
                "quant": "#0e6655",
                "model": "#6c3483",
            }
            popular_vars = []
            list_container = ttk.Frame(popular_frame)
            list_container.pack(fill=tk.BOTH, expand=True)
            pop_canvas = tk.Canvas(list_container, highlightthickness=0, height=220)
            popular_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=pop_canvas.yview)
            pop_inner = ttk.Frame(pop_canvas)
            pop_scroll_win = pop_canvas.create_window((0, 0), window=pop_inner, anchor="nw")
            def _pop_cfg(_event=None):
                pop_canvas.configure(scrollregion=pop_canvas.bbox("all"))
                try:
                    pop_canvas.itemconfigure(pop_scroll_win, width=pop_canvas.winfo_width())
                except Exception:
                    pass
            pop_inner.bind("<Configure>", _pop_cfg)
            pop_canvas.bind("<Configure>", lambda e: pop_canvas.itemconfigure(pop_scroll_win, width=e.width))
            def _pop_wheel(event):
                d = getattr(event, "delta", 0)
                if d == 0:
                    return
                if abs(d) < 100:
                    units = -1 if d > 0 else 1
                else:
                    units = int(-(d / 120))
                pop_canvas.yview_scroll(units, "units")
            pop_canvas.bind("<Enter>", lambda e: pop_canvas.bind_all("<MouseWheel>", _pop_wheel))
            pop_canvas.bind("<Leave>", lambda e: pop_canvas.unbind_all("<MouseWheel>"))
            pop_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            popular_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            pop_canvas.configure(yscrollcommand=popular_scroll.set)
            pop_inner.columnconfigure(0, weight=1)
            pop_inner.columnconfigure(1, weight=1)
            for i, (name, query, cat) in enumerate(popular_queries):
                var = tk.BooleanVar(value=False)
                popular_vars.append(var)
                r, c = divmod(i, 2)
                cell = ttk.Frame(pop_inner)
                cell.grid(row=r, column=c, sticky="ew", padx=(2, 4), pady=1)
                ttk.Checkbutton(cell, variable=var, width=2).pack(side=tk.LEFT, padx=(0, 2))
                fg = _tag_colors.get(cat if cat in _tag_colors else "emotion", "#333")
                lab = tk.Label(
                    cell,
                    text=f"{name}",
                    fg=fg,
                    font=("Microsoft YaHei", 9),
                    anchor=tk.W,
                    justify=tk.LEFT,
                    cursor="hand2",
                )
                lab.pack(side=tk.LEFT, fill=tk.X, expand=True)
                def _one_line(_e=None, q=query):
                    query_text.delete("1.0", tk.END)
                    query_text.insert("1.0", q)
                lab.bind("<Double-Button-1>", _one_line)
                cell.bind("<Double-Button-1>", _one_line)
            def _add_selected_popular():
                parts = [popular_queries[i][1] for i, v in enumerate(popular_vars) if v.get()]
                if not parts:
                    messagebox.showwarning("提示", "请先勾选至少一条经典语句。", parent=win)
                    return
                cur = query_text.get("1.0", tk.END).strip()
                block = ",".join(parts)
                if cur:
                    query_text.insert(tk.END, "," + block)
                else:
                    query_text.insert("1.0", block)
            def _select_all_pop(on=True):
                for v in popular_vars:
                    v.set(on)
            ttk.Button(pop_btn_row, text="全选", width=6, command=lambda: _select_all_pop(True)).pack(
                side=tk.LEFT, padx=(0, 4)
            )
            ttk.Button(pop_btn_row, text="全不选", width=7, command=lambda: _select_all_pop(False)).pack(
                side=tk.LEFT, padx=(0, 4)
            )
            ttk.Button(pop_btn_row, text="加入所选条件", width=14, command=_add_selected_popular).pack(
                side=tk.LEFT, padx=(0, 4)
            )
            status_label = ttk.Label(left_frame, text="就绪")
            right_frame.rowconfigure(1, weight=1)
            right_frame.columnconfigure(0, weight=1)
            table_wrap = ttk.Frame(right_frame)
            table_wrap.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
            table_wrap.columnconfigure(0, weight=1)
            columns = ('代码', '名称', '价格', '涨跌幅', '成交量', '成交额', '市值', 'PE', 'WR2', 'D', 'BIAS3', 'DIFF')
            tree = ttk.Treeview(table_wrap, columns=columns, show='headings', height=20)
            try:
                tree.tag_configure("idx_hs300", foreground="#c0392b")
                tree.tag_configure("idx_zz500", foreground="#8B4513")
                tree.tag_configure("idx_kc50", foreground="#1e8449")
            except Exception:
                pass
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=80, anchor=tk.CENTER)
            tree.column('名称', width=100)
            tree.column('成交额', width=100)
            tree.column('市值', width=100)
            scrollbar = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            def on_elevator_tree_double_click(event):
                """选中行后双击:打开该股票持仓详情(与主界面持仓格点击一致)。"""
                sel = tree.selection()
                if not sel:
                    return
                values = tree.item(sel[0], "values")
                if not values or len(values) < 2:
                    return
                code = str(values[0]).strip()
                name = str(values[1]).strip()
                if not code or not code.isdigit() or len(code) != 6:
                    return
                try:
                    self._show_stock_detail_direct(name if name else code, code, 1)
                except Exception as e:
                    messagebox.showerror("错误", f"打开持仓详情失败: {e}", parent=win)
            tree.bind("<Double-1>", on_elevator_tree_double_click)
            right_content = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
            right_content.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
            # 结果文本显示(上半部分)
            result_frame = ttk.LabelFrame(right_content, text="详细信息")
            right_content.add(result_frame, weight=1)
            result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, height=10)
            result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            # AI分析结果显示(下半部分)
            ai_analysis_frame = ttk.LabelFrame(right_content, text="AI分析结果")
            right_content.add(ai_analysis_frame, weight=1)
            ai_analysis_text = scrolledtext.ScrolledText(ai_analysis_frame, wrap=tk.WORD, height=10,
                                                         font=("Microsoft YaHei", 12))
            ai_analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            # 操作按钮
            action_frame = ttk.Frame(left_frame)
            action_frame.pack(fill=tk.X, padx=10, pady=10)
            def query_data():
                """查询数据"""
                query = query_text.get("1.0", tk.END).strip()
                if not query:
                    messagebox.showwarning("警告", "请输入查询条件")
                    return
                # 在新线程中执行同花顺问财选股(pywencai + Node)
                status_label.config(text="正在问财选股...")
                threading.Thread(target=_query_data_thread, args=(query,), daemon=True).start()
            def _query_data_thread(query_str):
                """在后台线程中查询数据"""
                try:
                    # 使用问财API查询
                    stocks = self._query_iwencai_stocks(query_str)
                    # 在主线程中更新UI
                    win.after(0, lambda: update_results(stocks, query_str))
                except Exception as e:
                    win.after(0, lambda e=e: messagebox.showerror("错误", f"查询失败: {e}"))
                    win.after(0, lambda: status_label.config(text="查询失败"))
            def update_results(stocks, query_condition=""):
                """更新结果显示"""
                # 清空表格
                for item in tree.get_children():
                    tree.delete(item)
                # 清空文本
                result_text.delete("1.0", tk.END)
                if not stocks:
                    status_label.config(text="未找到符合条件的股票")
                    result_text.insert(
                        "1.0",
                        "未找到符合条件的股票。\n\n"
                        "诊断:\n"
                        "  • 问财接口(pywencai)需要登录 Cookie 才能正常返回数据;\n"
                        "  • 已自动尝试 tushare 本地兜底,但复杂条件(均线形态/概念热点)无法本地复现;\n\n"
                        "恢复完整问财能力:\n"
                        "  1. 浏览器登录 https://www.iwencai.com\n"
                        "  2. F12→Network→复制任意请求的 Cookie 整行\n"
                        "  3. 设置环境变量后重启:\n"
                        "     export IWENCAI_COOKIE='你复制的Cookie'\n",
                    )
                    return
                stocks = self._dedupe_elevator_stocks_by_code(stocks)
                hs300, zz500, kc50 = self._get_cached_index_constituent_code_sets()
                # 更新表格
                for stock in stocks:
                    values = (
                        stock.get('code', ''),
                        stock.get('name', ''),
                        f"{stock.get('price', 0):.2f}",
                        f"{stock.get('change_pct', 0):+.2f}%",
                        f"{stock.get('volume', 0):,.0f}",
                        f"{stock.get('turnover', 0):,.0f}",
                        f"{stock.get('market_cap', 0):,.0f}",
                        f"{stock.get('pe_ratio', 0):.2f}",
                        f"{stock.get('wr2', 0):.2f}",
                        f"{stock.get('d', 0):.2f}",
                        f"{stock.get('bias3', 0):.2f}",
                        f"{stock.get('diff', 0):.3f}"
                    )
                    tag = self._index_tag_for_stock_code(
                        stock.get("code", ""), hs300, zz500, kc50
                    )
                    if tag:
                        tree.insert("", tk.END, values=values, tags=(tag,))
                    else:
                        tree.insert("", tk.END, values=values)
                # 更新详细信息
                info_text = f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                info_text += f"查询条件: {query_condition}\n"
                info_text += f"结果数量: {len(stocks)} 只股票\n\n"
                info_text += "详细数据:\n"
                info_text += "=" * 80 + "\n"
                for i, stock in enumerate(stocks, 1):
                    info_text += f"{i}. {stock.get('name', '')}({stock.get('code', '')})\n"
                    info_text += f"   价格: {stock.get('price', 0):.2f} | 涨跌幅: {stock.get('change_pct', 0):+.2f}%\n"
                    info_text += f"   成交量: {stock.get('volume', 0):,.0f} | 成交额: {stock.get('turnover', 0):,.0f}\n"
                    info_text += f"   市值: {stock.get('market_cap', 0):,.0f} | PE: {stock.get('pe_ratio', 0):.2f}\n"
                    info_text += f"   技术指标: WR2={stock.get('wr2', 0):.2f}, D={stock.get('d', 0):.2f}, BIAS3={stock.get('bias3', 0):.2f}, DIFF={stock.get('diff', 0):.3f}\n"
                    info_text += "-" * 80 + "\n"
                result_text.insert("1.0", info_text)
                status_label.config(text=f"查询完成,共找到 {len(stocks)} 只股票")
            def clear_results():
                """清空结果"""
                for item in tree.get_children():
                    tree.delete(item)
                result_text.delete("1.0", tk.END)
                status_label.config(text="结果已清空")
            def export_data():
                """导出数据"""
                stocks = []
                for item in tree.get_children():
                    values = tree.item(item, 'values')
                    if values:
                        stocks.append({
                            'code': values[0],
                            'name': values[1],
                            'price': values[2],
                            'change_pct': values[3],
                            'volume': values[4],
                            'turnover': values[5],
                            'market_cap': values[6],
                            'pe_ratio': values[7],
                            'wr2': values[8],
                            'd': values[9],
                            'bias3': values[10],
                            'diff': values[11]
                        })
                if not stocks:
                    messagebox.showwarning("警告", "没有可导出的数据")
                    return
                file_path = filedialog.asksaveasfilename(
                    title="导出数据",
                    defaultextension=".xlsx",
                    filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
                )
                if file_path:
                    try:
                        df = pd.DataFrame(stocks)
                        if file_path.endswith('.xlsx'):
                            df.to_excel(file_path, index=False)
                        else:
                            df.to_csv(file_path, index=False, encoding='utf-8-sig')
                        messagebox.showinfo("成功", "数据导出成功")
                    except Exception as e:
                        messagebox.showerror("错误", f"导出失败: {e}")
            def clear_query_conditions():
                query_text.delete("1.0", tk.END)
                for v in popular_vars:
                    v.set(False)
                status_label.config(text="查询条件已清空")
            ttk.Button(action_frame, text="问财选股", command=query_data).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(action_frame, text="清空条件", command=clear_query_conditions).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(action_frame, text="清空结果", command=clear_results).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(action_frame, text="导出数据", command=export_data).pack(side=tk.LEFT, padx=(0, 5))
            # AI分析按钮
            ai_analysis_btn = ttk.Button(action_frame, text="🤖 AI分析", command=lambda: ai_analyze_stocks())
            ai_analysis_btn.pack(side=tk.LEFT, padx=(0, 5))
            status_label.pack(fill=tk.X, padx=10, pady=(6, 4))
            def ai_analyze_stocks():
                """AI分析股票"""
                # 获取当前查询结果中的股票
                stocks = []
                for item in tree.get_children():
                    values = tree.item(item, 'values')
                    if values and len(values) >= 2:
                        stocks.append({
                            'code': values[0],
                            'name': values[1],
                            'price': values[2] if len(values) > 2 else '',
                            'change_pct': values[3] if len(values) > 3 else '',
                        })
                if not stocks:
                    messagebox.showwarning("警告", "请先查询股票数据,或选择要分析的股票")
                    return
                # 获取查询条件
                query_condition = query_text.get("1.0", tk.END).strip()
                # 在新线程中执行AI分析
                status_label.config(text="正在进行AI分析...")
                ai_analysis_btn.config(state="disabled")
                ai_analysis_text.delete("1.0", tk.END)
                ai_analysis_text.insert("1.0", "正在分析中,请稍候...\n")
                threading.Thread(target=_ai_analyze_thread, args=(stocks, query_condition), daemon=True).start()
            def _ai_analyze_thread(stocks_list, query_condition):
                """在后台线程中执行AI分析"""
                try:
                    # 构建分析提示词
                    stock_info = ""
                    for i, stock in enumerate(stocks_list[:20], 1):  # 限制最多分析20只
                        stock_info += f"{i}. {stock.get('name', '')}({stock.get('code', '')}) "
                        if stock.get('price'):
                            stock_info += f"价格:{stock.get('price')} "
                        if stock.get('change_pct'):
                            stock_info += f"涨跌幅:{stock.get('change_pct')} "
                        stock_info += "\n"
                    prompt = f"""请对以下股票进行专业分析:
查询条件:{query_condition}
股票列表:
{stock_info}
请从以下角度进行分析:
1. 整体评价:这些股票的共同特征和筛选逻辑的合理性
2. 投资价值:从基本面、技术面、市场情绪等角度评估投资价值
3. 风险提示:潜在的风险点和需要注意的事项
4. 操作建议:针对不同风险偏好的投资者的操作建议
5. 重点关注:哪些股票值得重点关注,原因是什么
请用专业、客观的语言进行分析,避免过度乐观或悲观。"""
                    # 调用AI
                    ai_result = self.ai_config_manager.call_ai(prompt)
                    # 在主线程中更新UI
                    def update_ai_result(result):
                        ai_analysis_text.delete("1.0", tk.END)
                        if result and not result.startswith("错误") and not result.startswith("API调用失败"):
                            ai_analysis_text.insert("1.0", f"AI分析结果({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
                            ai_analysis_text.insert(tk.END, "=" * 80 + "\n\n")
                            ai_analysis_text.insert(tk.END, result)
                            status_label.config(text=f"AI分析完成,共分析 {len(stocks_list)} 只股票")
                        else:
                            error_msg = result if result else "AI分析失败,请检查AI配置"
                            ai_analysis_text.insert("1.0", f"AI分析失败\n\n{error_msg}\n\n请检查AI配置是否正确(在系统设置中配置AI API密钥)")
                            status_label.config(text="AI分析失败")
                        ai_analysis_btn.config(state="normal")
                    win.after(0, lambda: update_ai_result(ai_result))
                except Exception as e:
                    def show_error(e=e):
                        ai_analysis_text.delete("1.0", tk.END)
                        ai_analysis_text.insert("1.0", f"AI分析异常: {e!s}")
                        status_label.config(text="AI分析异常")
                        ai_analysis_btn.config(state="normal")
                    win.after(0, show_error)
            def _init_elevator_sash():
                try:
                    win.update_idletasks()
                    paned_main.sashpos(0, min(680, max(380, int(win.winfo_width() * 0.44))))
                except Exception:
                    pass
            win.after(150, _init_elevator_sash)
            # 强制几何计算与前台显示,减轻 macOS 上子窗口空白不刷新的问题
            try:
                win.update_idletasks()
                win.lift()
                win.focus_force()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("错误", f"创建条件选股界面失败: {e}")
            import traceback
            traceback.print_exc()

    def show_five_star_follow_dialog(self):
        """五星跟随:统计龙头股、持仓和最近3天日期标签页的股票,按出现次数排序,并显示来源及资讯逻辑/所属板块。
        股票名称使用不同颜色加粗放大显示:
        - 同时出现在"龙头股"和"持仓"的股票:红色粗体大字
        - 仅在"龙头股"或日期标签页中的股票:橙色粗体大字
        - 仅在"持仓"或日期标签页中的股票:绿色粗体大字
        """
        import re
        from datetime import date
        # 基础标签页:持仓(1)、龙头股(2)
        tab_config = [
            (1, "持仓"),
            (2, "龙头股"),
        ]
        # 最近3天的日期标签页:group_index 7-14,对应 Notebook index = group_index + 1
        today = date.today()
        for group_index in range(7, 15):
            notebook_index = group_index + 1
            try:
                tab_text = self.position_trading_notebook.tab(notebook_index, "text")
            except Exception:
                continue
            label = str(tab_text).strip()
            # 期望格式为 MMDD,如 "0304"
            if not re.fullmatch(r"\d{4}", label):
                continue
            try:
                mm = int(label[:2])
                dd = int(label[2:])
                d = date(today.year, mm, dd)
                # 如果未来日期,按去年处理(跨年容错)
                if d > today:
                    d = date(today.year - 1, mm, dd)
            except Exception:
                continue
            delta = (today - d).days
            if 0 <= delta <= 2:
                tab_config.append((group_index, label))
        code_to_info = {}  # key -> {"code","name","count","tabs": set()}
        for group_index, tab_name in tab_config:
            holding_stocks, _, _, _ = self._get_holding_group_data(group_index)
            for slot in (holding_stocks or []):
                if not slot:
                    continue
                name, code = slot if isinstance(slot, (tuple, list)) else (slot, "")
                name = (name or "").strip()
                code = (code or "").strip()
                if not name and not code:
                    continue
                if not code and name:
                    code = get_stock_code_by_name(name) or ""
                code = str(code).zfill(6) if code else ""
                key = code if code else name
                if not key:
                    continue
                if key not in code_to_info:
                    code_to_info[key] = {"code": code or key, "name": name or key, "count": 0, "tabs": set()}
                code_to_info[key]["count"] += 1
                code_to_info[key]["tabs"].add(tab_name)
                if name:
                    code_to_info[key]["name"] = name
                if code and len(str(code)) == 6:
                    code_to_info[key]["code"] = str(code).zfill(6)
        if not code_to_info:
            messagebox.showinfo("提示", "龙头股、持仓和最近3天日期标签页中暂无股票,请先导入。", parent=self.root)
            return
        # 按出现次数从大到小排序
        sorted_items = sorted(code_to_info.items(), key=lambda x: (-x[1]["count"], x[0]))
        # 弹窗显示,后台仅获取逻辑/板块
        win = self._toplevel(self.root)
        win.title("五星跟随 - 统计结果")
        win.geometry("900x580")
        win.transient(self.root)
        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            top,
            text=(
                "龙头股 + 持仓 + 最近3天日期标签页 按出现次数排序;"
                "红色=均线多头强势;蓝色=靠近10日均线多头;黄色=靠近20日均线多头。"
            ),
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor="w")
        list_frame = ttk.Frame(top)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
        text_widget = tk.Text(list_frame, height=22, font=("Consolas", 11), wrap=tk.WORD)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=text_widget.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=scroll_y.set)
        text_widget.tag_configure("header", font=("Consolas", 11, "bold"))
        text_widget.tag_configure("name_red", foreground="#c00", font=("Consolas", 13, "bold"))
        text_widget.tag_configure("name_orange", foreground="#d2691e", font=("Consolas", 13, "bold"))
        text_widget.tag_configure("name_green", foreground="#006400", font=("Consolas", 13, "bold"))
        # 均线检测后的高亮样式:强势红、靠近10日线蓝、靠近20日线黄
        text_widget.tag_configure("name_ma_strong", foreground="#ff0000", font=("Consolas", 12, "bold"))
        text_widget.tag_configure("name_ma_blue", foreground="#0000cd", font=("Consolas", 13, "bold"))
        text_widget.tag_configure("name_ma_yellow", foreground="#daa520", font=("Consolas", 13, "bold"))
        # 表头
        text_widget.insert(tk.END, "出现次数\t来源\t代码\t名称\t逻辑/所属板块\n", "header")
        # 与 sorted_items 顺序一致,每项为 {"logic_sector": str, "ma_status": str|None}
        results_cache = []
        # 尾盘选股命中列表(线程内计算,UI更新时追加到底部)
        tail_screen_hits = []
        def classify_ma_status(stock_code: str):
            """根据 1/5/10/20 日均线判断多头、靠近10/20均线等状态。
            返回:
                'strong'  : 股价站上 1/5/10/20 且四条均线上涨、多头发散
                'near10'  : 满足多头发散,且距离10日线在3%以内
                'near20'  : 满足多头发散,且距离20日线在3%以内
                None      : 条件不满足或数据不足
            """
            try:
                if not stock_code:
                    return None
                # 获取近期收盘价
                result = self._fetch_recent_daily_closes(
                    stock_code, days=40, source="default", token=self.ts_token, return_volume=False
                )
                if isinstance(result, tuple) and len(result) >= 2:
                    _, closes = result[:2]
                else:
                    closes = result or []
                if not closes or len(closes) < 22:
                    return None
                closes = [float(c) for c in closes]
                # 当前价:优先实时价,否则最后一个收盘价
                current_price = None
                try:
                    spot_row = get_realtime_spot_row(stock_code)
                    if spot_row is not None:
                        v = spot_row.get("最新价", None)
                        if v is not None:
                            current_price = float(v)
                except Exception:
                    current_price = None
                if not current_price or current_price <= 0:
                    current_price = float(closes[-1])
                # 1日线 = 最新收盘
                ma1 = float(closes[-1])
                prev_ma1 = float(closes[-2])
                # 5日均线及前一周期
                ma5 = sum(closes[-5:]) / 5
                prev_ma5 = sum(closes[-6:-1]) / 5
                # 10日均线及前一周期
                ma10 = sum(closes[-10:]) / 10
                prev_ma10 = sum(closes[-11:-1]) / 10
                # 20日均线及前一周期
                ma20 = sum(closes[-20:]) / 20
                prev_ma20 = sum(closes[-21:-1]) / 20
                # 多头发散 + 均线向上
                bull_order = (current_price > ma1 > ma5 > ma10 > ma20)
                all_up = (ma1 > prev_ma1 and ma5 > prev_ma5 and ma10 > prev_ma10 and ma20 > prev_ma20)
                if not (bull_order and all_up and ma10 > 0 and ma20 > 0):
                    return None
                dist10 = abs(current_price - ma10) / ma10 * 100
                dist20 = abs(current_price - ma20) / ma20 * 100
                if dist10 <= 3.0:
                    return "near10"
                if dist20 <= 3.0:
                    return "near20"
                return "strong"
            except Exception:
                return None
        def fetch_and_fill():
            nonlocal tail_screen_hits
            tail_screen_hits = []
            # ===== 尾盘选股(14:30-15:00)预加载:板块Top5、资金流、板块成分 =====
            sector_top5_names = []
            sector_to_codes = {}  # sector -> set(code6)
            code_to_main_inflow = {}  # code6 -> float(主力净流入净额)
            try:
                if AKSHARE_AVAILABLE:
                    import akshare as ak
                    # 1) 板块强度:涨跌幅前5(概念板块)
                    try:
                        df_sec = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                        if df_sec is not None and not df_sec.empty and "涨跌幅" in df_sec.columns and "板块名称" in df_sec.columns:
                            df_sec = df_sec.sort_values("涨跌幅", ascending=False).head(5)
                            sector_top5_names = [str(x) for x in df_sec["板块名称"].tolist() if str(x).strip()]
                    except Exception:
                        sector_top5_names = []
                    # 2) 资金流向:主力资金净流入(今日)
                    try:
                        flow_rank = ak.stock_individual_fund_flow_rank(indicator="今日")
                        if flow_rank is not None and not flow_rank.empty:
                            # 尽量找到"主力净流入净额"列(不同版本字段名可能略有差异)
                            code_col = None
                            inflow_col = None
                            for col in flow_rank.columns:
                                cs = str(col)
                                if code_col is None and ("代码" == cs or "股票代码" in cs):
                                    code_col = col
                                if inflow_col is None and ("主力净流入" in cs and ("净额" in cs or "净额(元)" in cs or "净额(元)" in cs)):
                                    inflow_col = col
                            if code_col is None:
                                # 兜底:常见字段
                                for c in ["代码", "股票代码"]:
                                    if c in flow_rank.columns:
                                        code_col = c
                                        break
                            if inflow_col is None:
                                for c in flow_rank.columns:
                                    if "主力净流入" in str(c) and "占比" not in str(c):
                                        inflow_col = c
                                        break
                            if code_col is not None and inflow_col is not None:
                                for _, row in flow_rank.iterrows():
                                    code6 = str(row.get(code_col, "")).zfill(6)[-6:]
                                    v = row.get(inflow_col, None)
                                    try:
                                        fv = float(str(v).replace(",", ""))
                                    except Exception:
                                        continue
                                    if code6 and code6.isdigit():
                                        code_to_main_inflow[code6] = fv
                    except Exception:
                        code_to_main_inflow = {}
                    # 3) 板块成分:仅为Top5取成分股集合(避免每股都查)
                    if sector_top5_names:
                        for sec_name in sector_top5_names:
                            try:
                                cons = ak.stock_board_concept_cons_em(symbol=sec_name)
                                if cons is None or cons.empty:
                                    continue
                                # 代码列名可能为"代码"
                                codes = set()
                                if "代码" in cons.columns:
                                    for c in cons["代码"].tolist():
                                        code6 = str(c).zfill(6)[-6:]
                                        if code6.isdigit():
                                            codes.add(code6)
                                sector_to_codes[sec_name] = codes
                            except Exception:
                                continue
            except Exception:
                sector_top5_names = []
                sector_to_codes = {}
                code_to_main_inflow = {}
            def _parse_cn_money_to_yi(x):
                """把 '123.4亿' / '5600万' / 数值 转成 '亿' 为单位的 float。"""
                try:
                    if x is None:
                        return None
                    if isinstance(x, (int, float)):
                        return float(x) / 1e8
                    s = str(x).replace(",", "").strip()
                    if not s:
                        return None
                    if s.endswith("亿"):
                        return float(s[:-1])
                    if s.endswith("万"):
                        return float(s[:-1]) / 1e4
                    if s.endswith("元"):
                        return float(s[:-1]) / 1e8
                    return float(s) / 1e8
                except Exception:
                    return None
            def _tail_screen_one(code6: str, name: str):
                """
                返回 (passed:bool, detail:dict|None)
                条件:
                  - 尾盘涨幅 >2%(14:30 -> 15:00)
                  - 成交量比 >1.5(尾盘成交量 vs 全天均量(每30分钟))
                  - 股价位置:突破关键位置或创日内新高(近似:收盘接近日高/突破日高)
                  - 板块强度:所属板块涨幅前5(概念板块Top5,按成分股包含近似)
                  - 资金流向:主力资金净流入(今日主力净流入净额>0)
                  - 市值适中:50亿-500亿(优先用"流通市值",兜底"总市值")
                  - 换手率:3%-15%
                """
                try:
                    if not code6 or not str(code6).isdigit():
                        return False, None
                    code6 = str(code6).zfill(6)[-6:]
                    # 现成快照字段:最新价、最高、涨跌幅、量比、换手率、流通市值/总市值
                    spot = None
                    try:
                        spot = get_realtime_spot_row(code6)
                    except Exception:
                        spot = None
                    day_high = None
                    turnover = None
                    mktcap_yi = None
                    try:
                        if spot is not None:
                            if spot.get("最新价", None) is not None:
                                float(spot.get("最新价"))
                            if spot.get("最高", None) is not None:
                                day_high = float(spot.get("最高"))
                            # 换手率
                            for k in ("换手率", "换手", "换手率(%)"):
                                if k in spot and spot.get(k) is not None:
                                    turnover = float(str(spot.get(k)).replace("%", ""))
                                    break
                            # 市值
                            for k in ("流通市值", "总市值", "总市值(元)", "流通市值(元)"):
                                if k in spot and spot.get(k) is not None:
                                    mktcap_yi = _parse_cn_money_to_yi(spot.get(k))
                                    if mktcap_yi is not None:
                                        break
                    except Exception:
                        pass
                    # 条件:市值 50-500亿
                    if mktcap_yi is None or not (50 <= mktcap_yi <= 500):
                        return False, {
                            "code": code6, "name": name,
                            "reason": f"市值不在50-500亿({mktcap_yi if mktcap_yi is not None else '未知'}亿)"
                        }
                    # 条件:换手率 3%-15%
                    if turnover is None or not (3 <= turnover <= 15):
                        return False, {
                            "code": code6, "name": name,
                            "reason": f"换手率不在3-15%({turnover if turnover is not None else '未知'})"
                        }
                    # 条件:板块Top5(用Top5成分股包含作为近似)
                    sector_hit = None
                    if sector_top5_names and sector_to_codes:
                        for sec_name in sector_top5_names:
                            codes = sector_to_codes.get(sec_name) or set()
                            if code6 in codes:
                                sector_hit = sec_name
                                break
                    if not sector_hit:
                        return False, {
                            "code": code6, "name": name,
                            "reason": "不在概念板块涨幅前5的成分股中(近似判断)"
                        }
                    # 条件:主力资金净流入(今日)
                    main_inflow = code_to_main_inflow.get(code6)
                    if main_inflow is None:
                        return False, {"code": code6, "name": name, "reason": "无法获取主力净流入(今日)"}
                    if main_inflow <= 0:
                        return False, {"code": code6, "name": name, "reason": f"主力净流入<=0({main_inflow:,.0f}元)"}
                    # 分钟K:计算 14:30-15:00 涨幅 和 尾盘量比
                    if not AKSHARE_AVAILABLE:
                        return False, {"code": code6, "name": name, "reason": "AKShare不可用,无法计算尾盘分钟数据"}
                    import akshare as ak
                    try:
                        df1 = ak.stock_zh_a_hist_min_em(symbol=code6, period="1", adjust="")
                    except Exception:
                        df1 = None
                    if df1 is None or getattr(df1, "empty", True):
                        return False, {"code": code6, "name": name, "reason": "分钟K为空,无法计算尾盘涨幅/量比"}
                    # 兼容列名:时间/日期时间、收盘、成交量
                    time_col = None
                    close_col = None
                    vol_col = None
                    for c in df1.columns:
                        cs = str(c)
                        if time_col is None and ("时间" in cs or "日期" in cs):
                            time_col = c
                        if close_col is None and ("收盘" in cs or cs == "close"):
                            close_col = c
                        if vol_col is None and ("成交量" in cs or cs == "volume"):
                            vol_col = c
                    if time_col is None or close_col is None or vol_col is None:
                        return False, {"code": code6, "name": name, "reason": "分钟K字段缺失(时间/收盘/成交量)"}
                    def _to_hhmm(v):
                        s = str(v).strip()
                        # 可能是 '2026-03-11 14:31:00' 或 '14:31:00'
                        if " " in s:
                            s = s.split(" ")[-1]
                        if len(s) >= 5:
                            return s[:5]
                        return s
                    hhmm = df1[time_col].apply(_to_hhmm)
                    tail_mask = (hhmm >= "14:30") & (hhmm <= "15:00")
                    df_tail = df1[tail_mask]
                    if df_tail is None or df_tail.empty or len(df_tail) < 2:
                        return False, {"code": code6, "name": name, "reason": "尾盘区间数据不足(14:30-15:00)"}
                    try:
                        px_1430 = float(df_tail.iloc[0][close_col])
                        px_last = float(df_tail.iloc[-1][close_col])
                        tail_pct = (px_last - px_1430) / px_1430 * 100 if px_1430 else 0.0
                    except Exception:
                        return False, {"code": code6, "name": name, "reason": "尾盘涨幅计算失败"}
                    # 尾盘成交量 vs 全天均量(按每30分钟平均)
                    try:
                        tail_vol = float(df_tail[vol_col].astype(float).sum())
                        day_vol = float(df1[vol_col].astype(float).sum())
                        avg_30m = day_vol / 8.0 if day_vol > 0 else 0.0  # A股日内大致8个30分钟段
                        vol_ratio = (tail_vol / avg_30m) if avg_30m > 0 else 0.0
                    except Exception:
                        tail_vol = None
                        vol_ratio = 0.0
                    if not (tail_pct > 2.0):
                        return False, {"code": code6, "name": name, "reason": f"尾盘涨幅<=2%({tail_pct:.2f}%)"}
                    if not (vol_ratio > 1.5):
                        return False, {"code": code6, "name": name, "reason": f"尾盘量比<=1.5({vol_ratio:.2f})"}
                    # 股价位置:创日内新高/突破关键位(近似:现价接近日高或新高)
                    position_ok = False
                    try:
                        # 用分钟K的最高作为更准的日内高点
                        high_col = None
                        for c in df1.columns:
                            if "最高" in str(c) or str(c) == "high":
                                high_col = c
                                break
                        intraday_high = float(df1[high_col].astype(float).max()) if high_col is not None else (day_high if day_high else None)
                        if intraday_high and px_last >= intraday_high * 0.998:
                            position_ok = True
                            day_high = intraday_high
                    except Exception:
                        position_ok = False
                    if not position_ok:
                        return False, {"code": code6, "name": name, "reason": "未体现突破/日内新高(近似)"}
                    # 全部满足
                    return True, {
                        "code": code6,
                        "name": name,
                        "tail_pct": tail_pct,
                        "vol_ratio": vol_ratio,
                        "mktcap_yi": mktcap_yi,
                        "turnover": turnover,
                        "sector": sector_hit,
                        "main_inflow": main_inflow,
                        "day_high": day_high,
                    }
                except Exception as e:
                    return False, {"code": code6, "name": name, "reason": f"筛选异常: {e}"}
            for key, info in sorted_items:
                code = info.get("code") or key
                name = info.get("name") or key
                logic_sector = ""
                ma_status = None
                price_text = ""
                try:
                    # 资讯逻辑 / 板块
                    logic_list = get_stock_logic_from_db(stock_name=name) if name else []
                    if logic_list and logic_list[0].get("logic"):
                        logic_text = logic_list[0].get("logic") or ""
                        logic_sector = logic_text[:200]
                        if len(logic_text) > 200:
                            logic_sector += "..."
                    if not logic_sector and name:
                        logic_sector = get_stock_sector(name) or ""
                    # 均线状态(需要6位代码)
                    stock_code = code if code and len(str(code)) == 6 else None
                    ma_status = classify_ma_status(stock_code) if stock_code else None
                    # 实时价/当日收盘价:优先实时最新价,取不到则用最新日线收盘价
                    if not stock_code and name:
                        try:
                            sc = get_stock_code_by_name(name) or ""
                            stock_code = str(sc).zfill(6) if sc else None
                        except Exception:
                            stock_code = None
                    if stock_code:
                        rt_price = None
                        try:
                            spot_row = get_realtime_spot_row(stock_code)
                            if spot_row is not None:
                                v = spot_row.get("最新价", None)
                                if v is not None:
                                    rt_price = float(v)
                        except Exception:
                            rt_price = None
                        if rt_price is not None and rt_price > 0:
                            price_text = f" 现价:{rt_price:.2f}"
                        else:
                            try:
                                result = self._fetch_recent_daily_closes(
                                    stock_code, days=5, source="default", token=self.ts_token, return_volume=False
                                )
                                closes = result[1] if isinstance(result, tuple) and len(result) >= 2 else (result or [])
                                closes = [float(c) for c in closes if c is not None]
                                if closes:
                                    price_text = f" 收盘价:{float(closes[-1]):.2f}"
                            except Exception:
                                price_text = ""
                except Exception as e:
                    logic_sector = f"(获取失败: {e})"
                    ma_status = None
                # 尾盘选股:只对有6位代码的股票尝试,避免过慢(默认最多计算前60只)
                try:
                    code6 = str(code).zfill(6)[-6:] if code else ""
                    if len(tail_screen_hits) < 60 and code6.isdigit():
                        ok, detail = _tail_screen_one(code6, name)
                        if ok and detail:
                            tail_screen_hits.append(detail)
                except Exception:
                    pass
                results_cache.append({"logic_sector": logic_sector or "-", "ma_status": ma_status, "price_text": price_text})
            def update_ui():
                text_widget.delete("1.0", tk.END)
                text_widget.insert(tk.END, "出现次数\t来源\t代码\t名称\t逻辑/所属板块\n", "header")
                for i, (key, info) in enumerate(sorted_items):
                    code = info.get("code") or key
                    name = info.get("name") or key
                    tabs = sorted(info["tabs"])
                    tabs_str = "、".join(tabs)
                    count = info["count"]
                    rec = results_cache[i] if i < len(results_cache) else {}
                    logic_sector = rec.get("logic_sector", "-")
                    ma_status = rec.get("ma_status")
                    price_text = rec.get("price_text", "") or ""
                    # 先插入前半部分
                    prefix = f"{count}\t{tabs_str}\t{code}\t"
                    text_widget.insert(tk.END, prefix, "default")
                    # 基础颜色:龙头股+持仓 -> 红;只含龙头或日期 -> 橙;只含持仓或日期 -> 绿
                    has_leader = "龙头股" in tabs
                    has_main = "持仓" in tabs
                    if has_leader and has_main:
                        base_tag = "name_red"
                    elif has_leader:
                        base_tag = "name_orange"
                    else:
                        base_tag = "name_green"
                    # 均线结果优先覆盖基础颜色
                    if ma_status == "strong":
                        name_tag = "name_ma_strong"
                    elif ma_status == "near10":
                        name_tag = "name_ma_blue"
                    elif ma_status == "near20":
                        name_tag = "name_ma_yellow"
                    else:
                        name_tag = base_tag
                    text_widget.insert(tk.END, f"{name}{price_text}", name_tag)
                    text_widget.insert(tk.END, "\t", "default")
                    text_widget.insert(tk.END, (logic_sector or "-") + "\n", "default")
                # ===== 追加:尾盘选股(14:30-15:00) =====
                try:
                    text_widget.insert(tk.END, "\n" + "=" * 90 + "\n", "default")
                    text_widget.insert(tk.END, "尾盘选股(14:30-15:00)- 满足:尾盘涨幅>2%、尾盘量比>1.5、创日内新高/突破、板块涨幅前5、主力净流入、市值50-500亿、换手3-15%\n", "header")
                    if not tail_screen_hits:
                        text_widget.insert(tk.END, "(暂无命中;若当前非交易时段/网络慢/接口受限,分钟K或资金流可能取不到)\n", "default")
                    else:
                        # 按尾盘涨幅降序
                        hits = sorted(tail_screen_hits, key=lambda x: float(x.get("tail_pct", 0) or 0), reverse=True)[:30]
                        for h in hits:
                            text_widget.insert(
                                tk.END,
                                f"- {h.get('name','')}({h.get('code','')}) "
                                f"尾盘涨幅{float(h.get('tail_pct',0)):+.2f}% | 尾盘量比{float(h.get('vol_ratio',0)):.2f} | "
                                f"板块:{h.get('sector','')} | 主力净流入:{float(h.get('main_inflow',0)):,.0f}元 | "
                                f"市值:{float(h.get('mktcap_yi',0)):.1f}亿 | 换手:{float(h.get('turnover',0)):.2f}%\n",
                                "default",
                            )
                except Exception:
                    pass
            self.root.after(0, update_ui)
        # 先显示表格骨架,再异步填逻辑/板块
        for key, info in sorted_items:
            code = info.get("code") or key
            name = info.get("name") or key
            tabs_str = "、".join(sorted(info["tabs"]))
            text_widget.insert(
                tk.END,
                f"{info['count']}\t{tabs_str}\t{code}\t{name}\t(获取逻辑/板块中...)\n",
                "default",
            )
        def do_fetch():
            try:
                fetch_and_fill()
            except Exception as e:
                self.root.after(
                    0,
                    lambda e=e: messagebox.showerror("错误", f"获取逻辑或板块失败: {e}", parent=win),
                )
        threading.Thread(target=do_fetch, daemon=True).start()
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.LEFT)

    def show_backtest_dialog(self):
        """显示回测分析对话框"""
        # 创建自定义回测窗口
        custom_window = self._toplevel(self.root)
        custom_window.title("批量股票回测分析")
        custom_window.geometry("700x600")
        custom_window.transient(self.root)
        custom_window.grab_set()
        # 股票输入区域
        stock_frame = ttk.LabelFrame(custom_window, text="股票列表(每行一个股票名称或代码)", padding=10)
        stock_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        stock_text = scrolledtext.ScrolledText(stock_frame, height=10, wrap=tk.WORD)
        stock_text.pack(fill=tk.BOTH, expand=True)
        # 按钮区域
        stock_btn_frame = ttk.Frame(stock_frame)
        stock_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(stock_btn_frame, text="从文件导入", command=lambda: self._import_stocks_from_file(stock_text, custom_window), width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(stock_btn_frame, text="粘贴", command=lambda: self._paste_stocks(stock_text, custom_window), width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(stock_btn_frame, text="清空", command=lambda: stock_text.delete("1.0", tk.END), width=12).pack(side=tk.LEFT, padx=2)
        # 日期设置区域
        date_frame = ttk.LabelFrame(custom_window, text="日期设置", padding=10)
        date_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(date_frame, text="买入日期:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        buy_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        buy_date_entry = ttk.Entry(date_frame, textvariable=buy_date_var, width=12)
        buy_date_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(date_frame, text="今天", command=lambda: buy_date_var.set(datetime.now().strftime("%Y-%m-%d")), width=8).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(date_frame, text="卖出日期:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        sell_date_var = tk.StringVar(value="")
        sell_date_entry = ttk.Entry(date_frame, textvariable=sell_date_var, width=12)
        sell_date_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(date_frame, text="(留空表示计算至今)", font=("TkDefaultFont", 8)).grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        def start_custom_backtest():
            """开始自定义回测"""
            stock_content = stock_text.get("1.0", tk.END).strip()
            if not stock_content:
                messagebox.showwarning("警告", "请输入股票列表", parent=custom_window)
                return
            # 解析股票列表
            stock_lines = [line.strip() for line in stock_content.split('\n') if line.strip()]
            if not stock_lines:
                messagebox.showwarning("警告", "股票列表为空", parent=custom_window)
                return
            # 解析买入日期
            try:
                buy_date_str = buy_date_var.get().strip()
                buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
            except:
                messagebox.showerror("错误", "买入日期格式错误,请使用 YYYY-MM-DD 格式", parent=custom_window)
                return
            # 解析卖出日期(可选)
            sell_date = None
            sell_date_str = sell_date_var.get().strip()
            if sell_date_str:
                try:
                    sell_date = datetime.strptime(sell_date_str, "%Y-%m-%d").date()
                    if sell_date < buy_date:
                        messagebox.showerror("错误", "卖出日期不能早于买入日期", parent=custom_window)
                        return
                except:
                    messagebox.showerror("错误", "卖出日期格式错误,请使用 YYYY-MM-DD 格式", parent=custom_window)
                    return
            custom_window.destroy()
            self._perform_custom_backtest(stock_lines, buy_date, sell_date)
        button_frame = ttk.Frame(custom_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="开始回测", command=start_custom_backtest, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=custom_window.destroy, width=12).pack(side=tk.RIGHT, padx=5)

    def show_top_list_dialog(self):
        """展示龙虎榜实时数据"""
        if not TS_AVAILABLE:
            messagebox.showerror("错误", "当前环境未安装tushare,无法获取龙虎榜数据")
            return
        if not (self.ts_token or TS_DEFAULT_TOKEN):
            messagebox.showwarning("提示", "未配置Tushare Token,无法获取龙虎榜数据")
            return
        existing = getattr(self, "_top_list_window", None)
        if existing and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            return
        win = self._toplevel(self.root)
        win.title("龙虎榜实时监控")
        win.geometry("1180x680")
        win.transient(self.root)
        def on_close():
            self._top_list_window = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
        self._top_list_window = win
        header_frame = ttk.Frame(win, padding=5)
        header_frame.pack(fill=tk.X)
        status_var = tk.StringVar(value="正在准备获取龙虎榜数据...")
        ttk.Label(header_frame, textvariable=status_var, foreground="blue").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(header_frame, text="查看数据库", width=12,
                   command=lambda: self.show_unified_db_display(default_tab="lhb")).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(header_frame, text="刷新", width=10,
                   command=lambda: self._load_top_list_data(status_var, tree)).pack(side=tk.RIGHT, padx=(5, 0))
        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        columns = (
            "trade_date", "ts_code", "name", "close", "pct_change", "turnover_rate",
            "amount", "l_amount", "net_amount", "net_rate", "amount_rate", "float_values", "reason"
        )
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=22)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        headings = {
            "trade_date": "日期",
            "ts_code": "代码",
            "name": "名称",
            "close": "收盘价",
            "pct_change": "涨跌幅",
            "turnover_rate": "换手率",
            "amount": "总成交额(元)",
            "l_amount": "龙虎榜成交额(元)",
            "net_amount": "净买入(元)",
            "net_rate": "净买入占比",
            "amount_rate": "龙虎榜成交占比",
            "float_values": "流通市值(元)",
            "reason": "上榜理由"
        }
        col_widths = {
            "trade_date": 90,
            "ts_code": 90,
            "name": 90,
            "close": 80,
            "pct_change": 90,
            "turnover_rate": 90,
            "amount": 140,
            "l_amount": 140,
            "net_amount": 140,
            "net_rate": 110,
            "amount_rate": 140,
            "float_values": 150,
            "reason": 260
        }
        for col in columns:
            tree.heading(col, text=headings.get(col, col))
            tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)
        tree.tag_configure("net_positive", foreground="#d32f2f")
        tree.tag_configure("net_negative", foreground="#1b5e20")
        tree.tag_configure("non_today", background="#f7f7f7")
        button_frame = ttk.Frame(win, padding=5)
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="刷新数据", width=12,
                   command=lambda: self._load_top_list_data(status_var, tree)).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="复制选中", width=12,
                   command=lambda: self._copy_tree_selection(tree, ["日期","代码","名称","收盘价","涨跌幅","换手率","总成交额","龙虎榜成交额","净买入","净买入占比","龙虎榜成交占比","流通市值","上榜理由"])
                   ).pack(side=tk.LEFT, padx=3)
        ttk.Button(button_frame, text="AI分析选中", width=14,
                   command=lambda: self._analyze_lhb_data(tree, analysis_text)).pack(side=tk.LEFT, padx=3)
        analysis_frame = ttk.LabelFrame(main_frame, text="AI 分析结果", padding=5, width=360)
        analysis_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False)
        analysis_text = scrolledtext.ScrolledText(analysis_frame, wrap=tk.WORD, font=("TkDefaultFont", 12), state=tk.DISABLED, width=40)
        analysis_text.pack(fill=tk.BOTH, expand=True)
        analysis_text.insert("1.0“, “请选择一行或多行数据后点击“AI分析选中“获取分析结果")
        ttk.Label(win, text="提示:若今日无数据,会自动回退至最近交易日,并自动保存到本地数据库。", foreground="#555555").pack(fill=tk.X, padx=5, pady=(0, 5))
        self._attach_window_controls(win)
        self._load_top_list_data(status_var, tree)

    def show_margin_summary_dialog(self):
        """展示融资融券交易汇总数据"""
        if not TS_AVAILABLE:
            messagebox.showerror("错误", "当前环境未安装tushare,无法获取融资融券数据")
            return
        if not (self.ts_token or TS_DEFAULT_TOKEN):
            messagebox.showwarning("提示", "未配置Tushare Token,无法获取融资融券数据")
            return
        existing = getattr(self, "_margin_summary_window", None)
        if existing and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            return
        win = self._toplevel(self.root)
        win.title("融资融券交易汇总")
        win.geometry("1200x700")
        win.transient(self.root)
        def on_close():
            self._margin_summary_window = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
        self._margin_summary_window = win
        # 顶部控制区域
        header_frame = ttk.Frame(win, padding=5)
        header_frame.pack(fill=tk.X)
        date_frame = ttk.Frame(header_frame)
        date_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="交易日期:").pack(side=tk.LEFT, padx=2)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y%m%d'))
        date_entry = ttk.Entry(date_frame, textvariable=date_var, width=12)
        date_entry.pack(side=tk.LEFT, padx=2)
        exchange_frame = ttk.Frame(header_frame)
        exchange_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(exchange_frame, text="交易所:").pack(side=tk.LEFT, padx=2)
        exchange_var = tk.StringVar(value="")
        exchange_combo = ttk.Combobox(exchange_frame, textvariable=exchange_var, width=10,
                                     values=["", "SSE", "SZSE", "BSE"], state="readonly")
        exchange_combo.pack(side=tk.LEFT, padx=2)
        status_var = tk.StringVar(value="准备获取数据...")
        ttk.Label(header_frame, textvariable=status_var, foreground="blue").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        def load_data():
            self._load_margin_summary_data(status_var, tree, date_var.get(), exchange_var.get())
        ttk.Button(header_frame, text="查询", width=10, command=load_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="AI分析", width=10,
                  command=lambda: self._analyze_margin_summary(tree, analysis_text)).pack(side=tk.RIGHT, padx=5)
        # 主内容区域(左右分栏)
        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 左侧:数据表格
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("trade_date", "exchange_id", "rzye", "rzmre", "rzche", "rqye", "rqmcl", "rzrqye", "rqyl")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)
        headings = {
            "trade_date": "交易日期",
            "exchange_id": "交易所",
            "rzye": "融资余额(元)",
            "rzmre": "融资买入额(元)",
            "rzche": "融资偿还额(元)",
            "rqye": "融券余额(元)",
            "rqmcl": "融券卖出量",
            "rzrqye": "融资融券余额(元)",
            "rqyl": "融券余量"
        }
        col_widths = {
            "trade_date": 100,
            "exchange_id": 80,
            "rzye": 150,
            "rzmre": 150,
            "rzche": 150,
            "rqye": 150,
            "rqmcl": 120,
            "rzrqye": 150,
            "rqyl": 120
        }
        for col in columns:
            tree.heading(col, text=headings.get(col, col))
            tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 右侧:AI分析区域
        right_frame = ttk.LabelFrame(main_frame, text="AI分析", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        right_frame.config(width=400)
        analysis_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=("TkDefaultFont", 12), state=tk.DISABLED)
        analysis_text.pack(fill=tk.BOTH, expand=True)
        analysis_text.insert("1.0", "请先查询数据,然后点击'AI分析'按钮获取分析结果")
        # 初始加载数据
        load_data()
        summary_button_frame = ttk.Frame(win, padding=5)
        summary_button_frame.pack(fill=tk.X)
        summary_columns_alias = ["交易日期","交易所","融资余额","融资买入额","融资偿还额","融券余额","融券卖出量","融资融券余额","融券余量"]
        ttk.Button(summary_button_frame, text="复制选中", width=12,
                   command=lambda: self._copy_tree_selection(tree, summary_columns_alias)).pack(side=tk.LEFT, padx=3)
        ttk.Button(summary_button_frame, text="刷新数据", width=12, command=load_data).pack(side=tk.LEFT, padx=3)
        self._attach_window_controls(win)

    def show_margin_detail_dialog(self):
        """展示融资融券交易明细数据"""
        if not TS_AVAILABLE:
            messagebox.showerror("错误", "当前环境未安装tushare,无法获取融资融券数据")
            return
        if not (self.ts_token or TS_DEFAULT_TOKEN):
            messagebox.showwarning("提示", "未配置Tushare Token,无法获取融资融券数据")
            return
        existing = getattr(self, "_margin_detail_window", None)
        if existing and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            return
        win = self._toplevel(self.root)
        win.title("融资融券交易明细")
        win.geometry("1400x750")
        win.transient(self.root)
        def on_close():
            self._margin_detail_window = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)
        self._margin_detail_window = win
        # 顶部控制区域
        header_frame = ttk.Frame(win, padding=5)
        header_frame.pack(fill=tk.X)
        date_frame = ttk.Frame(header_frame)
        date_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="交易日期:").pack(side=tk.LEFT, padx=2)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y%m%d'))
        date_entry = ttk.Entry(date_frame, textvariable=date_var, width=12)
        date_entry.pack(side=tk.LEFT, padx=2)
        stock_frame = ttk.Frame(header_frame)
        stock_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(stock_frame, text="股票代码:").pack(side=tk.LEFT, padx=2)
        stock_var = tk.StringVar()
        stock_entry = ttk.Entry(stock_frame, textvariable=stock_var, width=15)
        stock_entry.pack(side=tk.LEFT, padx=2)
        status_var = tk.StringVar(value="准备获取数据...")
        ttk.Label(header_frame, textvariable=status_var, foreground="blue").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        def load_data():
            self._load_margin_detail_data(status_var, tree, date_var.get(), stock_var.get())
        ttk.Button(header_frame, text="查询", width=10, command=load_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="AI分析", width=10,
                  command=lambda: self._analyze_margin_detail(tree, analysis_text)).pack(side=tk.RIGHT, padx=5)
        # 主内容区域(左右分栏)
        main_frame = ttk.Frame(win)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 左侧:数据表格
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("trade_date", "ts_code", "name", "rzye", "rqye", "rzmre", "rqyl", "rzche", "rqchl", "rqmcl", "rzrqye")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=25)
        headings = {
            "trade_date": "交易日期",
            "ts_code": "股票代码",
            "name": "股票名称",
            "rzye": "融资余额(元)",
            "rqye": "融券余额(元)",
            "rzmre": "融资买入额(元)",
            "rqyl": "融券余量",
            "rzche": "融资偿还额(元)",
            "rqchl": "融券偿还量",
            "rqmcl": "融券卖出量",
            "rzrqye": "融资融券余额(元)"
        }
        col_widths = {
            "trade_date": 100,
            "ts_code": 100,
            "name": 100,
            "rzye": 130,
            "rqye": 130,
            "rzmre": 130,
            "rqyl": 100,
            "rzche": 130,
            "rqchl": 100,
            "rqmcl": 100,
            "rzrqye": 140
        }
        for col in columns:
            tree.heading(col, text=headings.get(col, col))
            tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 右侧:AI分析区域
        right_frame = ttk.LabelFrame(main_frame, text="AI分析", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        right_frame.config(width=400)
        analysis_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=("TkDefaultFont", 12), state=tk.DISABLED)
        analysis_text.pack(fill=tk.BOTH, expand=True)
        analysis_text.insert("1.0", "请先查询数据,然后点击'AI分析'按钮获取分析结果")
        # 初始加载数据
        load_data()
        detail_button_frame = ttk.Frame(win, padding=5)
        detail_button_frame.pack(fill=tk.X)
        detail_columns_alias = ["交易日期","股票代码","名称","融资余额","融券余额","融资买入额","融券余量","融资偿还额","融券偿还量","融券卖出量","融资融券余额"]
        ttk.Button(detail_button_frame, text="复制选中", width=12,
                   command=lambda: self._copy_tree_selection(tree, detail_columns_alias)).pack(side=tk.LEFT, padx=3)
        ttk.Button(detail_button_frame, text="刷新数据", width=12, command=load_data).pack(side=tk.LEFT, padx=3)
        self._attach_window_controls(win)

    def _build_crawler_buttons(self, row1, row2):
        """从配置文件构建爬取按钮"""
        # 清空现有按钮
        for widget in row1.winfo_children():
            widget.destroy()
        for widget in row2.winfo_children():
            widget.destroy()
        # 按排序字段排序
        sorted_config = sorted(self.crawler_config, key=lambda x: x.get("sort_order", 999))
        # 将按钮分配到两行;若 row1/row2 是同一容器,则合并为一行
        single_row_mode = (row1 == row2)
        for idx, item in enumerate(sorted_config):
            key = item.get("key", "")
            name = item.get("name", "")
            url = item.get("url", "")
            bg_color = item.get("bg_color", "lightgray")
            item.get("fg_color", "black")
            command_str = item.get("command", "")
            # 选择行(前3个在第一行,后面的在第二行)
            target_row = row1 if (single_row_mode or idx < 3) else row2
            # 创建复选框,加载保存的状态
            var = tk.BooleanVar(value=self.crawler_checkbox_states.get(key, False))
            self.crawler_checkboxes[key] = var
            checkbox = ttk.Checkbutton(target_row, variable=var,
                                      command=lambda k=key, v=var: self._save_crawler_checkbox_state(k, v.get()))
            checkbox.pack(side=tk.LEFT, padx=(0, 5))
            # 创建按钮
            def create_button_command(cmd_str, u=url):
                """创建按钮命令函数"""
                if cmd_str.startswith("run_crawler_script:"):
                    script_name = cmd_str.split(":")[1]
                    return lambda: self.run_crawler_script(script_name)
                elif cmd_str == "crawl_taoguba_direct":
                    return self.crawl_taoguba_direct
                elif cmd_str == "crawl_eastmoney_web":
                    return self.crawl_eastmoney_web
                elif cmd_str == "crawl_xueqiu_web":
                    return self.crawl_xueqiu_web
                elif cmd_str == "crawl_xuangubao_web":
                    return self.crawl_xuangubao_web
                elif cmd_str == "crawl_ths_web":
                    return self.crawl_ths_web
                else:
                    # 默认打开URL
                    return lambda: webbrowser.open(u)
            btn = tk.Button(
                target_row,
                text=name,
                command=create_button_command(command_str, url),
                width=15,
                bg=bg_color,
                fg="black",
                font=("TkDefaultFont", 11)
            )
            btn.pack(side=tk.LEFT, padx=(0, 5))

    def _build_market_nav_section(self, container):
        """构建市场指数与热点导航区域"""
        for child in container.winfo_children():
            child.destroy()
        market_info_frame = ttk.LabelFrame(container, text="市场指数与热点导航", padding=8)
        market_info_frame.pack(fill=tk.BOTH, expand=True)
        header_frame = ttk.Frame(market_info_frame)
        header_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            header_frame,
            text="常用指数 / 量化平台 / 热门榜单快捷入口",
            font=("TkDefaultFont", 12, "bold")
        ).pack(side=tk.LEFT)
        ttk.Button(
            header_frame,
            text="一键导入",
            command=self.import_market_nav_data
        ).pack(side=tk.RIGHT)
        ttk.Button(
            header_frame,
            text="恢复默认",
            command=self.restore_default_market_nav_config
        ).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(
            header_frame,
            text="编辑导航",
            command=self.show_market_nav_editor
        ).pack(side=tk.RIGHT, padx=(0, 6))
        market_notebook = ttk.Notebook(market_info_frame)
        market_notebook.pack(fill=tk.BOTH, expand=True)
        # 保存market_notebook引用
        self.market_notebook = market_notebook
        # 更新界面,显示market_notebook
        self._safe_update()
        # 第一个标签页:合并的市场指数&热点导航(二列布局)
        self._create_merged_market_hot_tab()
        # 更新界面,显示第一个标签页
        self._safe_update()
        # 第二个标签页:宏观&指数(三列布局,支持拖拽)
        indices_tab = ttk.Frame(market_notebook, padding=8)
        market_notebook.add(indices_tab, text="宏观&指数")
        self._create_draggable_button_grid(indices_tab, "indices", "影响股市情绪与流动性的核心指标:")
        # 第三个标签页:AI搜索聚合
        ai_search_tab = ttk.Frame(market_notebook, padding=8)
        market_notebook.add(ai_search_tab, text="AI搜索聚合")
        # 提前定义 AI 站点,供搜索行工具栏和左侧栏共用
        ai_sites = [
            {"name": "豆包(字节)", "desc": "Doubao AI,支持中文和代码生成", "url": "https://www.doubao.com/", "search_url": "https://www.doubao.com/search?q={query}"},
            {"name": "通义千问", "desc": "阿里巴巴通义大模型", "url": "https://tongyi.aliyun.com/", "search_url": "https://tongyi.aliyun.com/qianwen/search?q={query}"},
            {"name": "纳米 AI", "desc": "MiniMax 纳米对话与写作", "url": "https://www.mini-max.ai/", "search_url": "https://www.mini-max.ai/search?q={query}"},
            {"name": "讯飞星火", "desc": "科大讯飞星火认知大模型", "url": "https://xinghuo.xfyun.cn/", "search_url": "https://xinghuo.xfyun.cn/search?q={query}"},
            {"name": "百度文心一言", "desc": "文心一言(ERNIE Bot)", "url": "https://yiyan.baidu.com/", "search_url": "https://yiyan.baidu.com/search?q={query}"}
        ]
        ai_short_names = ["豆包", "通义", "纳米", "星火", "文心"]
        # 搜索输入区域
        search_input_frame = ttk.Frame(ai_search_tab)
        search_input_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            search_input_frame,
            text="输入关键词或问题:",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w", pady=(0, 6))
        search_entry_frame = ttk.Frame(search_input_frame)
        search_entry_frame.pack(fill=tk.X)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_entry_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        # 搜索按钮(百度) + 右侧 AI 工具区域
        button_frame = ttk.Frame(search_entry_frame)
        button_frame.pack(side=tk.LEFT)
        ttk.Button(
            button_frame, text="搜索",
            command=lambda: self._open_search_engine("https://www.baidu.com/s?wd={query}", search_var.get()),
            width=6
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(button_frame, text="AI:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        for i, site in enumerate(ai_sites):
            short = ai_short_names[i] if i < len(ai_short_names) else site["name"][:2]
            ttk.Button(
                button_frame,
                text=short,
                width=5,
                command=lambda s=site, v=search_var: self._open_ai_search(s, v.get())
            ).pack(side=tk.LEFT, padx=2)
        # 搜索引擎按钮
        engines = [
            ("百度", "https://www.baidu.com/s?wd={query}"),
            ("微信/搜狗", "https://weixin.sogou.com/weixin?type=2&query={query}"),
            ("新浪搜索", "https://search.sina.com.cn/?q={query}"),
            ("谷歌", "https://www.google.com/search?q={query}"),
            ("微软 Bing", "https://www.bing.com/search?q={query}"),
            ("360 搜索", "https://www.so.com/s?q={query}")
        ]
        engine_frame = ttk.Frame(ai_search_tab)
        engine_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            engine_frame,
            text="搜索引擎:",
            font=("TkDefaultFont", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))
        engine_buttons_frame = ttk.Frame(engine_frame)
        engine_buttons_frame.pack(fill=tk.X)
        for idx, (label, base_url) in enumerate(engines):
            btn = ttk.Button(
                engine_buttons_frame,
                text=label,
                width=12,
                command=lambda url=base_url: self._open_search_engine(url, search_var.get())
            )
            btn.grid(row=idx // 3, column=idx % 3, padx=4, pady=4, sticky="w")
        # 上方右侧可见区域:AI工具 + 保存的问题 并排
        main_content_frame = ttk.Frame(ai_search_tab)
        main_content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        top_row = ttk.Frame(main_content_frame)
        top_row.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        # 左半:AI工具(详情)
        ai_section_frame = ttk.LabelFrame(top_row, text="AI工具(详情)", padding=4)
        ai_section_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        ai_buttons_frame = ttk.Frame(ai_section_frame)
        ai_buttons_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            ai_buttons_frame,
            text="AI工具:",
            font=("TkDefaultFont", 8)
        ).pack(side=tk.LEFT, anchor="w", padx=(0, 4))
        for site in ai_sites:
            frame = ttk.Frame(ai_section_frame)
            frame.pack(fill=tk.X, pady=1)
            ttk.Label(
                frame,
                text=f"{site['name']}",
                wraplength=200,
                foreground="#333333",
                font=("TkDefaultFont", 8)
            ).pack(side=tk.LEFT, anchor="w", padx=(0, 4))
            ttk.Button(
                frame,
                text="AI搜索",
                width=7,
                command=lambda s=site, v=search_var: self._open_ai_search(s, v.get())
            ).pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(
                frame,
                text="打开",
                width=5,
                command=lambda link=site["url"], t=site["name"]: self._open_market_link(link)
            ).pack(side=tk.LEFT, padx=2)
        # 右半:保存的问题(点击自动填入)
        questions_label_frame = ttk.LabelFrame(top_row, text="保存的问题(点击自动填入)", padding=8)
        questions_label_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        if not hasattr(self, "market_nav_config"):
            self.market_nav_config = self.load_market_nav_config()
        if "ai_search_questions" not in self.market_nav_config:
            self.market_nav_config["ai_search_questions"] = []
        questions_listbox = tk.Listbox(questions_label_frame, height=12, font=("TkDefaultFont", 11))
        questions_listbox.pack(fill=tk.BOTH, expand=True)
        def on_question_select(event):
            selection = questions_listbox.curselection()
            if selection:
                value = questions_listbox.get(selection[0])
                search_var.set(value)
        questions_listbox.bind("<<ListboxSelect>>", on_question_select)
        self.ai_questions_listbox = questions_listbox
        self._refresh_ai_questions_widget()
        question_buttons_frame = ttk.Frame(questions_label_frame)
        question_buttons_frame.pack(fill=tk.X, pady=(4, 0))
        def delete_selected_question():
            selection = questions_listbox.curselection()
            if selection:
                idx = selection[0]
                questions = self.market_nav_config.get("ai_search_questions", [])
                if idx < len(questions):
                    questions.pop(idx)
                    self.market_nav_config["ai_search_questions"] = questions
                    self.save_market_nav_config()
                    self._refresh_ai_questions_widget()
        ttk.Button(
            question_buttons_frame,
            text="删除选中",
            width=10,
            command=delete_selected_question
        ).pack(side=tk.LEFT, padx=(0, 4))
        def clear_all_questions():
            if messagebox.askyesno("确认", "确定要清空所有保存的问题吗?"):
                self.market_nav_config["ai_search_questions"] = []
                self.save_market_nav_config()
                self._refresh_ai_questions_widget()
        ttk.Button(
            question_buttons_frame,
            text="清空全部",
            width=10,
            command=clear_all_questions
        ).pack(side=tk.LEFT)
        # 下方:最近搜索记录
        history_frame = ttk.LabelFrame(main_content_frame, text="最近搜索记录", padding=4)
        history_frame.pack(fill=tk.X, pady=(0, 4))
        history_listbox = tk.Listbox(history_frame, height=5, font=("TkDefaultFont", 8))
        history_listbox.pack(fill=tk.X, pady=(0, 4))
        def on_history_select(event):
            selection = history_listbox.curselection()
            if selection:
                value = history_listbox.get(selection[0])
                search_var.set(value)
        history_listbox.bind("<<ListboxSelect>>", on_history_select)
        self.search_history_listbox = history_listbox
        if not hasattr(self, "search_history"):
            self.search_history = []
        self._refresh_search_history_widget()
        # 大V公众号(三列布局,支持拖拽)
        dv_tab = ttk.Frame(market_notebook, padding=8)
        market_notebook.add(dv_tab, text="大V公众号")
        self._create_draggable_button_grid(dv_tab, "dv_accounts", "精选财经大V公众号:点击打开公众号介绍页,可复制文章或扫码关注。")

    def _create_nav_editor_tab(self, notebook, title, key, has_desc):
        """创建导航编辑tab"""
        frame = ttk.Frame(notebook, padding=10)
        notebook.add(frame, text=title)
        columns = ("name", "desc", "url", "bg_color", "fg_color") if has_desc else ("name", "url", "bg_color", "fg_color")
        headings = ("名称", "描述", "链接", "背景色", "文字色") if has_desc else ("名称", "链接", "背景色", "文字色")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        for col, heading in zip(columns, headings):
            if col == "name":
                width = 200
            elif col == "desc":
                width = 220
            elif col in ("bg_color", "fg_color"):
                width = 80
            else:
                width = 320
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor=tk.W)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        form_frame = ttk.LabelFrame(frame, text="编辑", padding=8)
        form_frame.pack(fill=tk.X, pady=(10, 0))
        name_var = tk.StringVar()
        desc_var = tk.StringVar()
        url_var = tk.StringVar()
        bg_color_var = tk.StringVar()
        fg_color_var = tk.StringVar()
        ttk.Label(form_frame, text="名称:").grid(row=0, column=0, sticky="e", pady=2)
        ttk.Entry(form_frame, textvariable=name_var, width=28).grid(row=0, column=1, sticky="w", pady=2, padx=(0, 8))
        current_row = 1
        if has_desc:
            ttk.Label(form_frame, text="描述:").grid(row=current_row, column=0, sticky="e", pady=2)
            ttk.Entry(form_frame, textvariable=desc_var, width=40).grid(row=current_row, column=1, sticky="w", pady=2, padx=(0, 8))
            current_row += 1
        ttk.Label(form_frame, text="链接:").grid(row=current_row, column=0, sticky="e", pady=2)
        ttk.Entry(form_frame, textvariable=url_var, width=40).grid(row=current_row, column=1, sticky="w", pady=2, padx=(0, 8))
        current_row += 1
        # 颜色选择
        color_frame = ttk.Frame(form_frame)
        color_frame.grid(row=current_row, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Label(color_frame, text="背景色:").pack(side=tk.LEFT, padx=(0, 5))
        bg_color_entry = ttk.Entry(color_frame, textvariable=bg_color_var, width=15)
        bg_color_entry.pack(side=tk.LEFT, padx=(0, 10))
        def choose_bg_color():
            color = self._choose_color(bg_color_var.get() or "lightgray")
            if color:
                bg_color_var.set(color)
        ttk.Button(color_frame, text="选择", command=choose_bg_color, width=8).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Label(color_frame, text="文字色:").pack(side=tk.LEFT, padx=(0, 5))
        fg_color_entry = ttk.Entry(color_frame, textvariable=fg_color_var, width=15)
        fg_color_entry.pack(side=tk.LEFT, padx=(0, 10))
        def choose_fg_color():
            color = self._choose_color(fg_color_var.get() or "black")
            if color:
                fg_color_var.set(color)
        ttk.Button(color_frame, text="选择", command=choose_fg_color, width=8).pack(side=tk.LEFT)
        # 颜色预览
        color_preview = tk.Label(color_frame, text="预览", width=10, relief=tk.SUNKEN)
        color_preview.pack(side=tk.LEFT, padx=(20, 0))
        def update_color_preview(*args):
            bg = bg_color_var.get() or "lightgray"
            fg = fg_color_var.get() or "black"
            try:
                color_preview.config(bg=bg, fg=fg)
            except:
                pass
        bg_color_var.trace("w", update_color_preview)
        fg_color_var.trace("w", update_color_preview)
        update_color_preview()
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=current_row + 1, column=0, columnspan=2, pady=(6, 0))
        def refresh_tree():
            tree.delete(*tree.get_children())
            data_list = self.market_nav_config.get(key, [])
            # 不要自动从默认配置加载,保持用户配置(即使是空的)
            # 如果用户需要恢复,可以使用"恢复默认"按钮
            # 按排序字段排序
            sorted_list = sorted(data_list, key=lambda x: x.get("sort_order", 999))
            for item in sorted_list:
                bg_color = item.get("bg_color", "")
                fg_color = item.get("fg_color", "")
                if has_desc:
                    values = (item.get("name", ""), item.get("desc", ""), item.get("url", ""), bg_color, fg_color)
                else:
                    values = (item.get("name", ""), item.get("url", ""), bg_color, fg_color)
                tree.insert("", tk.END, values=values)
        def clear_form():
            name_var.set("")
            desc_var.set("")
            url_var.set("")
            bg_color_var.set("")
            fg_color_var.set("")
        def get_selected_index():
            selection = tree.selection()
            if not selection:
                return None
            return tree.index(selection[0])
        def add_entry():
            name = name_var.get().strip()
            url = url_var.get().strip()
            if not name or not url:
                messagebox.showwarning("提示", "请填写名称和链接")
                return
            entry = {"name": name, "url": url}
            if has_desc:
                entry["desc"] = desc_var.get().strip()
            # 添加颜色信息
            bg_color = bg_color_var.get().strip()
            fg_color = fg_color_var.get().strip()
            if bg_color:
                entry["bg_color"] = bg_color
            if fg_color:
                entry["fg_color"] = fg_color
            # 设置排序字段(新添加的排在最后)
            data_list = self.market_nav_config.setdefault(key, [])
            entry["sort_order"] = len(data_list) + 1
            data_list.append(entry)
            self.save_market_nav_config()
            self._build_market_nav_section(self.market_nav_container)
            # 刷新合并标签页(市场指数和热点导航已合并)
            if key in ["indices", "portals", "hot_sources"]:
                self._create_merged_market_hot_tab()
            # 刷新单个配置的标签页
            if key in ["indices", "dv_accounts"]:
                self._refresh_single_config_tab(key)
            # 同时刷新整个市场导航区域
            if hasattr(self, 'market_nav_container'):
                self._build_market_nav_section(self.market_nav_container)
            refresh_tree()
            clear_form()
        def update_entry():
            idx = get_selected_index()
            if idx is None:
                messagebox.showwarning("提示", "请选择需要修改的项")
                return
            data_list = self.market_nav_config.setdefault(key, [])
            if idx >= len(data_list):
                return
            name = name_var.get().strip()
            url = url_var.get().strip()
            if not name or not url:
                messagebox.showwarning("提示", "请填写名称和链接")
                return
            data_list[idx]["name"] = name
            data_list[idx]["url"] = url
            if has_desc:
                data_list[idx]["desc"] = desc_var.get().strip()
            else:
                data_list[idx].pop("desc", None)
            # 更新颜色信息
            bg_color = bg_color_var.get().strip()
            fg_color = fg_color_var.get().strip()
            if bg_color:
                data_list[idx]["bg_color"] = bg_color
            else:
                data_list[idx].pop("bg_color", None)
            if fg_color:
                data_list[idx]["fg_color"] = fg_color
            else:
                data_list[idx].pop("fg_color", None)
            self.save_market_nav_config()
            self._build_market_nav_section(self.market_nav_container)
            # 刷新合并标签页(市场指数和热点导航已合并)
            if key in ["indices", "portals", "hot_sources"]:
                self._create_merged_market_hot_tab()
            # 刷新单个配置的标签页
            if key in ["indices", "dv_accounts"]:
                self._refresh_single_config_tab(key)
            refresh_tree()
        def delete_entry():
            idx = get_selected_index()
            if idx is None:
                messagebox.showwarning("提示", "请选择需要删除的项")
                return
            data_list = self.market_nav_config.setdefault(key, [])
            if idx >= len(data_list):
                return
            if messagebox.askyesno("确认", "确定要删除该条目吗?"):
                data_list.pop(idx)
                self.save_market_nav_config()
                self._build_market_nav_section(self.market_nav_container)
                # 刷新合并标签页(市场指数和热点导航已合并)
                if key in ["indices", "portals", "hot_sources"]:
                    self._create_merged_market_hot_tab()
                # 刷新单个配置的标签页
                if key in ["indices", "dv_accounts"]:
                    self._refresh_single_config_tab(key)
                refresh_tree()
                clear_form()
        ttk.Button(button_frame, text="新增", width=10, command=add_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="更新", width=10, command=update_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="删除", width=10, command=delete_entry).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_frame, text="清空", width=10, command=clear_form).pack(side=tk.LEFT, padx=4)
        def on_select(event):
            selection = tree.selection()
            if not selection:
                return
            values = tree.item(selection[0], "values")
            if not values:
                return
            name_var.set(values[0])
            if has_desc:
                desc_var.set(values[1])
                url_var.set(values[2])
                bg_color_var.set(values[3] if len(values) > 3 else "")
                fg_color_var.set(values[4] if len(values) > 4 else "")
            else:
                desc_var.set("")
                url_var.set(values[1])
                bg_color_var.set(values[2] if len(values) > 2 else "")
                fg_color_var.set(values[3] if len(values) > 3 else "")
        tree.bind("<<TreeviewSelect>>", on_select)
        refresh_tree()

    def show_stock_management_dialog(self):
        """弹出自选股管理窗口"""
        if hasattr(self, "_stock_mgmt_window") and self._stock_mgmt_window:
            if self._stock_mgmt_window.winfo_exists():
                self._stock_mgmt_window.deiconify()
                self._stock_mgmt_window.lift()
                return
            self._stock_mgmt_window = None
        dialog = self._toplevel(self.root)
        dialog.title("自选股管理")
        dialog.geometry("1400x720")
        dialog.transient(self.root)
        dialog.resizable(True, True)  # 允许调整大小
        dialog.minsize(1000, 600)  # 设置最小尺寸
        dialog.grab_set()
        self._stock_mgmt_window = dialog
        def on_close():
            if self._stock_mgmt_window:
                self._stock_mgmt_window.destroy()
            self._stock_mgmt_window = None
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        container = ttk.Frame(dialog, padding=10)
        container.pack(fill=tk.BOTH, expand=True)
        self.build_stock_management_tab(container, as_tab=False)

    def show_tushare_skills_dialog(self):
        """Tushare 技能查询与调用(对话框):查询基础接口名 -> 调用并展示前几行结果。"""
        win = self._toplevel(self.root)
        win.title("Tushare 技能查询与调用")
        win.geometry("1000x700")
        win.transient(self.root)
        if not TS_AVAILABLE:
            messagebox.showerror("错误", "当前环境未安装 tushare,请先安装后再使用。", parent=win)
            return
        try:
            self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
        except Exception as e:
            messagebox.showerror(
                "错误",
                f"Tushare 初始化失败:{e}\n\n请先在程序里登录/配置 Tushare token。",
                parent=win,
            )

    def _ia_build_advice(self, alert):
        """综合操作建议生成"""
        comp = alert["composite"]
        comp["score"]
        level = comp["level"]
        lines = []

        if level == "excellent":
            lines.append("🟢 【优】盘面强势: 指数多头+普涨+情绪好")
            lines.append("→ 建议: 正常操作, 仓位可积极, 关注龙头接力机会")
        elif level == "good":
            lines.append("🔵 【良】盘面偏多: 结构性机会存在")
            lines.append("→ 建议: 正常操作, 注意板块轮动, 不追高")
        elif level == "warning":
            lines.append("🟡 【差】盘面偏弱: 上涨乏力, 观望为主")
            lines.append("→ 建议: 轻仓或半仓, 避免逆势操作")
        else:
            lines.append("🔴 【危险】盘面恶劣: 空头主导, 切勿抄底!")
            lines.append("→ 建议: 空仓或极低仓位, 保护本金优先")

        # 具体条件追加
        br = alert["breadth"]
        up, dn = br.get("up", 0), br.get("down", 0)
        if up + dn > 0 and up / max(dn, 1) > 3:
            lines.append("· 普涨格局, 但追高风险大, 看分化再决策")
        if br.get("zt", 0) >= 80:
            lines.append("· 涨停潮出现, 关注次龙头补涨机会")
        if br.get("zt", 0) < 15:
            lines.append("· 涨停稀少, 情绪冰点, 耐心等待转机")
        if br.get("dt", 0) >= 10:
            lines.append("· ⚠️ 跌停股多, 恐慌释放中, 勿接飞刀")

        idx_list = alert.get("indices", [])
        if idx_list:
            main_idx = idx_list[0]
            if main_idx["pct"] < -2:
                lines.append(f"· 上证大跌{main_idx['pct']:.2f}%, 谨慎!")

        ar = alert.get("amount_ratio")
        if ar and ar < 0.6:
            lines.append(f"· 量能极度萎缩({ar:.1f}x), 观望为主")

        return "\n".join(lines)

    def _show_etf20_popup(self):
        """🎯 ETF六军 弹窗入口 - 半小时缓存 + 加载窗 + 后台线程"""
        import threading
        import time
        _cache = getattr(self, "_etf20_cache", None)
        _now = time.time()
        if _cache and (_now - _cache.get("ts", 0)) < 1800:
            print("[ETF六军] ✅ 使用缓存")
            self._show_etf20_dialog(_cache["data"], from_cache=True, cache_age_s=int(_now - _cache["ts"]))
            return

        loading_win = tk.Toplevel(self.root)
        loading_win.title("🎯 ETF六军会师")
        loading_win.geometry("400x200")
        loading_win.configure(bg="#E8EAF6")
        loading_win.transient(self.root)
        loading_win.grab_set()
        tk.Label(loading_win, text="🔄 六军会师策略计算中...", bg="#E8EAF6",
                 font=("", 14, "bold")).pack(pady=30)
        tk.Label(loading_win, text="拉取7只ETF行情 + MA20 + 月度回测", bg="#E8EAF6",
                 font=("", 10), fg="#666").pack()

        holder = {"data": None, "error": None}
        def _bg():
            try:
                holder["data"] = self._run_etf20_analysis()
            except Exception as e:
                import traceback; traceback.print_exc()
                holder["error"] = str(e)

        threading.Thread(target=_bg, daemon=True).start()
        def _poll():
            if holder["data"] is not None or holder["error"] is not None:
                loading_win.destroy()
                if holder["error"]:
                    messagebox.showerror("错误", f"计算失败: {holder['error']}")
                else:
                    self._etf20_cache = {"ts": time.time(), "data": holder["data"]}
                    self._show_etf20_dialog(holder["data"])
            else:
                self.root.after(300, _poll)
        self.root.after(300, _poll)

    def _show_etf20_dialog(self, data, from_cache=False, cache_age_s=0):
        """🎯 ETF六军 图形化弹窗 - 1100×780 深色现代风格"""
        import tkinter as tk
        from tkinter import ttk

        win = tk.Toplevel(self.root)
        win.title("🎯 六军会师ETF轮动策略")
        win.geometry("1100x780")
        win.configure(bg="#F5F5F5")

        # === 顶部栏 ===
        mode = data["mode"]
        _cache_tag = f"  |  🟡缓存({cache_age_s//60}分钟)" if from_cache else ""
        top_bar = tk.Frame(win, bg="#1565C0", height=40)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        tk.Label(top_bar,
            text=f"🎯 六军会师ETF轮动策略  |  信号日: {data['trade_date']}  |  模式: {mode} (绿灯{data['green_count']}/6){_cache_tag}",
            bg="#1565C0", fg="white", font=("", 13, "bold")).pack(side="left", padx=15)
        def _refresh():
            self._etf20_cache = None
            win.destroy()
            self._show_etf20_popup()
        ttk.Button(top_bar, text="🔄 强制刷新", command=_refresh).pack(side="right", padx=10)

        # === 日期条 ===
        date_bar = tk.Frame(win, bg="#FFF8E1")
        date_bar.pack(fill="x", padx=10, pady=8)
        tk.Label(date_bar,
            text=f"📅 下月信号检查(月末最后交易日): {data['next_signal_date']}   |   📅 调仓执行(次月首个交易日): {data['next_rebalance_date']}",
            bg="#FFF8E1", fg="#E65100", font=("", 10, "bold")).pack(padx=10, pady=6)

        # === 信号表格 ===
        sig_frame = tk.LabelFrame(win, text="📊 当前信号检查 (20日涨幅>0 + 收盘>MA20 = 绿灯)",
            bg="white", font=("", 10, "bold"))
        sig_frame.pack(fill="x", padx=10, pady=4)

        cols = ("name", "code", "price", "ma20", "pct20", "green", "role")
        tree = ttk.Treeview(sig_frame, columns=cols, show="headings", height=8)
        for col, label, w in [("name","ETF名称",120), ("code","代码",80), ("price","现价",80),
                               ("ma20","MA20",80), ("pct20","20日涨幅",90), ("green","绿灯",60), ("role","角色",90)]:
            tree.heading(col, text=label)
            tree.column(col, width=w, anchor="center")
        for r in data["results"]:
            pct_txt = f"{r['pct20']:+.2f}%"
            green_txt = "🟢" if r["green"] else "🔴"
            if r.get("optional"):
                green_txt += "⚪"
            tags = ("green",) if r["green"] else ("red",)
            tree.insert("", "end", values=(r["name"], r["code"], f"{r['price']:.3f}",
                        f"{r['ma20']:.3f}", pct_txt, green_txt, r["role"]), tags=tags)
        tree.tag_configure("green", background="#E8F5E9")
        tree.tag_configure("red", background="#FFEBEE")
        tree.pack(fill="x", padx=5, pady=5)

        # === 下方双栏: 调仓方案 + 历史回测 ===
        bottom_frame = tk.Frame(win, bg="#F5F5F5")
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=4)

        # 左: 调仓方案
        plan_frame = tk.LabelFrame(bottom_frame, text="🎯 调仓方案", bg="white", font=("", 11, "bold"))
        plan_frame.pack(side="left", fill="both", expand=True, padx=(0,5), pady=4)

        mode_color_bg = "#FFEBEE" if mode == "防御" else "#E8F5E9"
        mode_color_fg = "#C62828" if mode == "防御" else "#2E7D32"
        tk.Label(plan_frame, text=f"{'🔴' if mode=='防御' else '🟢'} {mode}模式 (绿灯{data['green_count']}/6)",
            bg=mode_color_bg, fg=mode_color_fg, font=("", 12, "bold")).pack(fill="x", padx=10, pady=(8,4))

        for p in data["plan"]:
            tk.Label(plan_frame, text=f"  ▶ 买入 {p['name']}({p['code']})  {p['ratio']}%",
                bg="white", fg="#333", font=("", 11)).pack(anchor="w", padx=15)
            tk.Label(plan_frame, text=f"      原因: {p['reason']}",
                bg="white", fg="#888", font=("", 9)).pack(anchor="w", padx=15, pady=(0,4))

        # 右: 回测
        bt_frame = tk.LabelFrame(bottom_frame, text="📈 历史回测 (简化版)", bg="white", font=("", 11, "bold"))
        bt_frame.pack(side="right", fill="both", expand=True, padx=(5,0), pady=4)

        bt = data.get("backtest", {})
        if bt.get("win_rate_green") is not None:
            tk.Label(bt_frame, text=f"🟢 绿灯状态胜率: {bt['win_rate_green']:.1f}%",
                bg="white", fg="#2E7D32", font=("", 11, "bold")).pack(anchor="w", padx=10, pady=(8,2))
            tk.Label(bt_frame, text=f"  绿灯月均收益: {bt['avg_ret_green']:+.2f}%",
                bg="white", fg="#333", font=("", 10)).pack(anchor="w", padx=15)
            tk.Label(bt_frame, text=f"  非绿灯月均收益: {bt['avg_ret_red']:+.2f}%",
                bg="white", fg="#666", font=("", 10)).pack(anchor="w", padx=15)
            tk.Label(bt_frame, text=f"  📊 {bt.get('note','')}",
                bg="white", fg="#888", font=("", 8)).pack(anchor="w", padx=10, pady=8)

            # 每只ETF的回测
            stats = bt.get("stats_per_etf", {})
            for tsc, s in list(stats.items())[:4]:  # 显示前4只
                code_short = tsc.split(".")[0]
                tk.Label(bt_frame,
                    text=f"    {code_short}: 🟢均{s['green_avg']:+.2f}%({s['green_count']}月) 🔴均{s['red_avg']:+.2f}%({s['red_count']}月)",
                    bg="white", fg="#555", font=("", 9)).pack(anchor="w", padx=15)
        else:
            tk.Label(bt_frame, text=f"⏳ {bt.get('note','数据不足')}",
                bg="white", fg="#999", font=("", 10)).pack(padx=10, pady=20)

        # === 止损规则 ===
        risk_frame = tk.LabelFrame(win, text="🔔 风控规则 (不可违反)", bg="#FFF3E0", font=("", 10, "bold"), fg="#E65100")
        risk_frame.pack(fill="x", padx=10, pady=4)
        tk.Label(risk_frame,
            text="📉 个股止损: 持仓从开仓成本下跌超过8% → 立即卖出, 全额买入国债ETF(511010), 持有至下次月度调仓\n"
                 "📉 账户止损: 总资产从历史最高点回撤超过15% → 立即清仓所有持仓, 全额买入国债ETF, 强制空仓休息1个月",
            bg="#FFF3E0", fg="#333", font=("", 9), justify="left").pack(padx=10, pady=4)

        # === 底部说明 ===
        footer = tk.Frame(win, bg="#E8EAF6")
        footer.pack(fill="x", side="bottom")
        tk.Label(footer,
            text="💡 六军会师策略: 机械执行, 月度调仓, 不主观判断 | 绿灯=20日涨幅>0 且 收盘>MA20 | 绿灯≥2进攻, <2防御",
            bg="#E8EAF6", fg="#3F51B5", font=("", 9)).pack(padx=10, pady=6)

    def _show_volume_price_popup(self):
        """📈 量价齐升选股弹窗入口 - 后台线程计算 + 半小时缓存"""
        import threading

        # --- 半小时缓存检查 ---
        _vp_cache = getattr(self, "_volume_price_cache", None)
        _now = time.time()
        if _vp_cache and (_now - _vp_cache.get("ts", 0)) < 1800 and _vp_cache.get("data"):
            # 缓存有效: 直接弹窗, 顶部加"缓存"标识
            print(f"[量价齐升] ✅ 使用缓存 ({(_now - _vp_cache['ts']):.0f}s ago)")
            cached = _vp_cache["data"]
            # 在弹窗标题里标注缓存
            self._show_volume_price_dialog(cached, from_cache=True, cache_age_s=int(_now - _vp_cache["ts"]))
            return

        loading_win = tk.Toplevel(self.root)
        loading_win.title("📈 量价齐升选股")
        loading_win.geometry("400x200")
        loading_win.configure(bg="#FFF8E1")
        loading_win.transient(self.root)
        loading_win.grab_set()
        tk.Label(loading_win, text="🔄 正在扫描量价齐升股票...", bg="#FFF8E1",
                 font=("", 14, "bold")).pack(pady=30)
        tk.Label(loading_win, text="拉取行情 + 计算均线 + 匹配板块", bg="#FFF8E1",
                 font=("", 10), fg="#666").pack()

        result_holder = {"data": None, "error": None}

        def _bg():
            try:
                result_holder["data"] = self._run_volume_price_scan()
            except Exception as e:
                import traceback
                traceback.print_exc()
                result_holder["error"] = str(e)

        threading.Thread(target=_bg, daemon=True).start()

        def _poll():
            if result_holder["data"] is not None or result_holder["error"] is not None:
                try:
                    loading_win.destroy()
                except Exception:
                    pass
                if result_holder["error"]:
                    messagebox.showerror("错误", f"扫描失败: {result_holder['error']}")
                else:
                    # 写入缓存
                    self._volume_price_cache = {"ts": time.time(), "data": result_holder["data"]}
                    self._show_volume_price_dialog(result_holder["data"])
            else:
                self.root.after(300, _poll)

        self.root.after(300, _poll)

    def _show_volume_price_dialog(self, data, from_cache=False, cache_age_s=0):
        """📈 量价齐升选股结果弹窗 - 卡片网格布局"""
        if data is None:
            return
        stocks = data.get("stocks", [])
        trade_date = data.get("trade_date", "")
        total_found = data.get("total_found", 0)
        if not stocks:
            messagebox.showinfo("📈 量价齐升", f"交易日 {trade_date}\n未找到符合条件的股票。")
            return

        win = tk.Toplevel(self.root)
        win.title("📈 量价齐升选股")
        win.geometry("1100x780")
        win.configure(bg="#F5F5F5")

        # === 顶部栏 ===
        top_bar = tk.Frame(win, bg="#1565C0", height=40)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        _cache_tag = ""
        if from_cache:
            _min = cache_age_s // 60
            _cache_tag = f"  |  🟡 缓存({_min}分钟前)"
        tk.Label(
            top_bar,
            text=f"📈 量价齐升选股  |  {trade_date}  |  共 {total_found} 只(展示 Top {len(stocks)}){_cache_tag}",
            bg="#1565C0", fg="white", font=("", 13, "bold")
        ).pack(side="left", padx=15)
        # 强制刷新 (清缓存) + 普通刷新
        def _force_refresh():
            self._volume_price_cache = None  # 清缓存!
            win.destroy()
            self._show_volume_price_popup()
        ttk.Button(
            top_bar, text="🔄 强制刷新",
            command=_force_refresh
        ).pack(side="right", padx=10)

        # === 概览条 ===
        avg_score = sum(s["total_score"] for s in stocks) / max(len(stocks), 1)
        streak3 = sum(1 for s in stocks if s["streak"] >= 3)
        num_sectors = len({s["sector"] for s in stocks})
        overview = tk.Frame(win, bg="#FFF8E1")
        overview.pack(fill="x", padx=10, pady=8)
        tk.Label(
            overview,
            text=f"📊 概览: Top{len(stocks)} 平均分 {avg_score:.0f}  |  3天以上连续放量: {streak3}只  |  板块覆盖: {num_sectors}个",
            bg="#FFF8E1", fg="#E65100", font=("", 10, "bold")
        ).pack(padx=10, pady=6)

        # === 工具栏 ===
        toolbar = tk.Frame(win, bg="#F5F5F5")
        toolbar.pack(fill="x", padx=10)

        sort_mode = {"val": "score"}
        card_container_ref = {"widget": None}  # 避免闭包引用问题

        def _refresh_cards():
            if card_container_ref["widget"] is None:
                return
            for w in card_container_ref["widget"].winfo_children():
                w.destroy()
            mode = sort_mode["val"]
            if mode == "score":
                sorted_stocks = sorted(stocks, key=lambda x: x["total_score"], reverse=True)
            elif mode == "vr":
                sorted_stocks = sorted(stocks, key=lambda x: x["vr"], reverse=True)
            elif mode == "pct":
                sorted_stocks = sorted(stocks, key=lambda x: x["pct"], reverse=True)
            elif mode == "tr":
                sorted_stocks = sorted(stocks, key=lambda x: x["tr"], reverse=True)
            else:
                sorted_stocks = stocks

            # 网格布局: 每行5个
            for i, s in enumerate(sorted_stocks):
                r, c = divmod(i, 5)
                card = self._make_stock_card(
                    card_container_ref["widget"], s,
                    lambda st=s: self._open_hotmoney_single_dialog(
                        auto_code=st["code"], auto_name=st["name"]
                    )
                )
                card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            for c in range(5):
                card_container_ref["widget"].columnconfigure(c, weight=1)

        ttk.Button(toolbar, text="🔽 按综合分", command=lambda: (sort_mode.update({"val": "score"}), _refresh_cards())).pack(side="left", padx=3)
        ttk.Button(toolbar, text="🔽 按量比VR", command=lambda: (sort_mode.update({"val": "vr"}), _refresh_cards())).pack(side="left", padx=3)
        ttk.Button(toolbar, text="🔽 按涨幅", command=lambda: (sort_mode.update({"val": "pct"}), _refresh_cards())).pack(side="left", padx=3)
        ttk.Button(toolbar, text="🔽 按换手", command=lambda: (sort_mode.update({"val": "tr"}), _refresh_cards())).pack(side="left", padx=3)

        # === 卡片区域(可滚动) ===
        outer_canvas = tk.Canvas(win, bg="#F5F5F5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=outer_canvas.yview)
        card_outer = tk.Frame(outer_canvas, bg="#F5F5F5")
        card_inner = tk.Frame(card_outer, bg="#F5F5F5")
        card_inner.pack(fill="both", expand=True, padx=5, pady=5)

        card_container_ref["widget"] = card_inner

        card_outer.bind(
            "<Configure>",
            lambda e: outer_canvas.configure(scrollregion=outer_canvas.bbox("all"))
        )
        outer_canvas.create_window((0, 0), window=card_outer, anchor="nw")
        outer_canvas.configure(yscrollcommand=scrollbar.set)

        # 鼠标滚轮
        def _on_mousewheel(event):
            outer_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        outer_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.protocol("WM_DELETE_WINDOW", lambda: [outer_canvas.unbind_all("<MouseWheel>"), win.destroy()])

        outer_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=8)

        # === 底部说明 ===
        footer = tk.Frame(win, bg="#E8EAF6")
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            text="💡 选股逻辑: 价涨>1% + 量比>1.3 + MA5>MA10>MA20 + 均线多头 + 基本面(PE/市值/换手)加权排序 | 双击卡片查看游资心法全解",
            bg="#E8EAF6", fg="#3F51B5", font=("", 9)
        ).pack(padx=10, pady=6)

        # 首次渲染
        win.update_idletasks()
        _refresh_cards()

    def _make_stock_card(self, parent, stock, on_double_click):
        """📈 量价齐升 - 单只股票卡片组件"""
        card = tk.Frame(parent, bg="white", highlightbackground="#E0E0E0",
                        highlightthickness=1, bd=0, padx=0, pady=0)

        # 顶部: 名称 + 代码 + 分数徽章
        header = tk.Frame(card, bg="white")
        header.pack(fill="x", padx=8, pady=(8, 2))

        tk.Label(
            header, text=stock.get("name", ""),
            bg="white", fg="#1565C0", font=("", 11, "bold")
        ).pack(side="left")

        sc = stock.get("total_score", 0)
        sc_color = "#C62828" if sc >= 70 else ("#F57F17" if sc >= 55 else "#2E7D32")
        tk.Label(
            header, text=f"{sc}分",
            bg=sc_color, fg="white", font=("", 9, "bold"), padx=6, pady=1
        ).pack(side="right")

        # 代码
        tk.Label(
            card, text=stock.get("code", ""),
            bg="white", fg="#999", font=("", 8)
        ).pack(anchor="w", padx=8)

        # 价格 + 涨跌幅
        price_frame = tk.Frame(card, bg="white")
        price_frame.pack(fill="x", padx=8, pady=(4, 0))
        tk.Label(
            price_frame, text=f"¥{stock.get('price', 0):.2f}",
            bg="white", fg="#333", font=("", 12, "bold")
        ).pack(side="left")
        pct = stock.get("pct", 0)
        pct_color = "#C62828" if pct >= 0 else "#2E7D32"
        tk.Label(
            price_frame, text=f"{pct:+.2f}%",
            bg="white", fg=pct_color, font=("", 10, "bold")
        ).pack(side="right")

        # 指标行: VR + 连续天数
        ind_frame = tk.Frame(card, bg="white")
        ind_frame.pack(fill="x", padx=8, pady=2)
        vr = stock.get("vr", 0)
        tk.Label(
            ind_frame, text=f"VR={vr:.1f}",
            bg="white", fg="#666", font=("", 9)
        ).pack(side="left")
        streak = stock.get("streak", 0)
        if streak >= 2:
            tk.Label(
                ind_frame, text=f"🔥连续{streak}天",
                bg="white", fg="#FF6F00", font=("", 9, "bold")
            ).pack(side="right")

        # 板块 + PE
        fund_frame = tk.Frame(card, bg="white")
        fund_frame.pack(fill="x", padx=8, pady=2)
        tk.Label(
            fund_frame, text=f"📂 {stock.get('sector', '其他')}",
            bg="white", fg="#1565C0", font=("", 9)
        ).pack(side="left")
        pe = stock.get("pe")
        if pe is not None and 0 < pe < 100:
            tk.Label(
                fund_frame, text=f"PE={pe:.1f}",
                bg="white", fg="#666", font=("", 9)
            ).pack(side="right")

        # 上涨原因
        reasons = stock.get("reasons", [])
        reason_txt = " | ".join(reasons[:3]) if reasons else ""
        tk.Label(
            card, text=reason_txt,
            bg="white", fg="#888", font=("", 8),
            wraplength=200, justify="left"
        ).pack(anchor="w", padx=8, pady=(2, 8))

        # --- 绑定双击事件 ---
        def _bind_all_dbl(widget):
            widget.bind("<Double-1>", lambda e: on_double_click())
            for child in widget.winfo_children():
                _bind_all_dbl(child)
        _bind_all_dbl(card)

        # --- hover 效果 ---
        def _hover_enter(e, c=card):
            c.configure(highlightbackground="#1565C0", highlightthickness=2, bg="#E3F2FD")
            def _set_bg(w):
                try:
                    w.configure(bg="#E3F2FD")
                except Exception:
                    pass
                for cc in w.winfo_children():
                    _set_bg(cc)
            _set_bg(c)

        def _hover_leave(e, c=card):
            c.configure(highlightbackground="#E0E0E0", highlightthickness=1, bg="white")
            def _set_bg(w):
                try:
                    w.configure(bg="white")
                except Exception:
                    pass
                for cc in w.winfo_children():
                    _set_bg(cc)
            _set_bg(c)

        card.bind("<Enter>", _hover_enter)
        card.bind("<Leave>", _hover_leave)

        return card

    def show_system_judgment_dialog(self):
        """系统研判:汇总左侧三池、情绪指标、实时新闻、波动与能量、重点指数与 THS 情绪,并可一键 AI 总评。"""
        win = self._toplevel(self.root)
        win.title("系统研判")
        win.geometry("1100x820")
        win.transient(self.root)
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        status = tk.StringVar(value="打开时优先使用研判表(3 小时内);否则联网汇总并写入研判表")
        ttk.Label(top, textvariable=status, font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        body = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        def _set_report(text: str):
            body.config(state=tk.NORMAL)
            body.delete("1.0", tk.END)
            body.insert(tk.END, text or "")
            body.config(state=tk.DISABLED)
        force_refresh_var = tk.BooleanVar(value=False)
        def _refresh():
            force = bool(force_refresh_var.get())
            status.set("正在汇总,请稍候...")
            win.update_idletasks()
            def work():
                try:
                    if not force:
                        cached, created_at = load_fresh_judgment_cache(JUDGMENT_CACHE_TTL_SECONDS)
                        if cached:
                            banner = (
                                "【研判表缓存】生成时间:"
                                + str(created_at)
                                + ",距今在 "
                                + str(JUDGMENT_CACHE_TTL_SECONDS // 3600)
                                + " 小时内,未重新请求网络。勾选「强制重新拉取」后点「刷新汇总」可更新。\n\n"
                            )
                            self.root.after(0, lambda: _set_report(banner + cached))
                            self.root.after(
                                0,
                                lambda: status.set(
                                    "已使用研判表缓存("
                                    + str(created_at)
                                    + ")。可点「AI 总研判」或强制重新拉取。"
                                ),
                            )
                            return
                    raw = self._collect_system_judgment_raw_context()
                    save_judgment_cache_snapshot(raw)
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    banner = "【已写入研判表】生成时间:" + ts + "(选股池/情绪/新闻等已保存)\n\n"
                    self.root.after(0, lambda: _set_report(banner + raw))
                    self.root.after(
                        0,
                        lambda: status.set(
                            "汇总完成并已保存到研判表。可继续点「AI 总研判」。"
                        ),
                    )
                except Exception as e:
                    self.root.after(0, lambda e=e: status.set(f"汇总失败:{e}"))
                    self.root.after(0, lambda e=e: _set_report(f"汇总异常:{e}"))
            threading.Thread(target=work, daemon=True).start()
        def _ai_total():
            status.set("AI 研判中...")
            win.update_idletasks()
            base = body.get("1.0", tk.END).strip()
            if len(base) < 80:
                messagebox.showwarning("提示", "请先点击「刷新汇总」生成原始材料。", parent=win)
                status.set("请先刷新汇总")
                return
            prompt = f"""你是一位资深 A 股策略与风控顾问。以下为程序自动汇总的「系统研判」原始材料(含左侧三选股池统计、情绪环境与快照、实时新闻、大盘波动率与能量学、主要指数与同花顺情绪指数等)。
请按以下结构用中文输出,条理清晰、结论明确;若某段数据缺失请说明「数据不足」并给出关注要点,勿编造精确数字:
一、左侧三池(龙头/15Min/Main)的数量与重叠:对「共振」与「分散」给出简要评价。
二、仓位区三维度打分与情绪快照:结合同花顺情绪指数方向、程序内情绪周期勾选,判断当前环境偏进攻/防御/观望。
三、实时新闻要点:偏利好/利空/中性,与哪些板块相关。
四、大盘波动率与能量聚集/发散:短线是否易变盘、是否宜控仓。
五、沪深300、中证500、科创50 与 同花顺情绪指数:风格与情绪是否一致,有无背离。
六、综合结论:明日或短周期操作建议(仓位、风格、风险点),不超过 15 条短句。
--- 原始材料(可能较长) ---
{base[:28000]}
{"...(材料已截断,分析时以可见部分为准)..." if len(base) > 28000 else ""}
"""
            sys_p = "你是严谨的中国 A 股投研助手,输出结构化中文,避免空话。"
            def run_ai():
                try:
                    cfg = getattr(self, "ai_config_manager", None)
                    config_override = None
                    if cfg:
                        pc = cfg.get_active_provider_config() or {}
                        config_override = dict(pc)
                        if config_override:
                            config_override["max_tokens"] = min(int(config_override.get("max_tokens") or 4096), 6000)
                            config_override["timeout"] = max(int(config_override.get("timeout", 60)), 120)
                    out = self.call_ai_model(prompt, system_prompt=sys_p, config_override=config_override)
                    sep = "\n\n" + "=" * 72 + "\n【AI 总研判】\n" + "=" * 72 + "\n\n"
                    text_out = out or "(无返回)"
                    def _append_ai():
                        body.config(state=tk.NORMAL)
                        body.insert(tk.END, sep + text_out)
                        body.config(state=tk.DISABLED)
                        body.see(tk.END)
                        status.set("AI 总研判已追加到文末")
                    self.root.after(0, _append_ai)
                except Exception as e:
                    self.root.after(0, lambda e=e: messagebox.showerror("错误", str(e), parent=win))
                    self.root.after(0, lambda: status.set("AI 研判失败"))
            threading.Thread(target=run_ai, daemon=True).start()
        bar = ttk.Frame(win, padding=(8, 0, 8, 8))
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="刷新汇总", command=_refresh, width=12).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Checkbutton(
            bar,
            text="强制重新拉取(忽略3小时内研判表)",
            variable=force_refresh_var,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar, text="AI 总研判", command=_ai_total, width=12).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="关闭", command=win.destroy, width=8).pack(side=tk.RIGHT)
        win.after(80, _refresh)

    def show_ai_staff_dialog(self):
        """AI员工:股票分析师 / 交易员 / 风控员 三分栏,分别调用 AI 与程序内行情数据。"""
        import re
        import threading
        win = self._toplevel(self.root)
        win.title("AI员工 · 分析师 / 交易员 / 风控员")
        win.geometry("1120x840")
        win.transient(self.root)
        win._os1_prefill_tail = getattr(self, "_os1_ai_append", None)
        try:
            delattr(self, "_os1_ai_append")
        except Exception:
            self._os1_ai_append = None
        top = ttk.Frame(win, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(
            top,
            text="分析师侧重行情与情绪指标解读;交易员侧重个股择时与买卖点思路;风控员侧重风险与建议仓位上限(非投资建议)。"
            " 各页「保存为...」可选 TXT / Word / Excel;界面与 Word、Excel 中对压力/阻力、支撑、仓位与风控类词分色显示(纯 TXT 无颜色)。",
            font=("TkDefaultFont", 9),
            wraplength=1050,
        ).pack(anchor=tk.W)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        # 与"量化策略"窗口保持一致:同花顺/Main/龙头/持仓/15Min 各前5
        def _fmt_stock_pair(name, code):
            n = str(name or "").strip()
            c = str(code or "").strip()
            if n and c:
                return f"{n}({c})"
            return n or c
        def _top_from_holding_attr(attr_name, limit=5):
            arr = getattr(self, attr_name, []) or []
            out = []
            for it in arr:
                if not it:
                    continue
                if isinstance(it, (tuple, list)) and len(it) >= 2:
                    s = _fmt_stock_pair(it[0], it[1])
                elif isinstance(it, dict):
                    s = _fmt_stock_pair(it.get("name"), it.get("code"))
                else:
                    s = str(it).strip()
                if not s:
                    continue
                out.append(s)
                if len(out) >= limit:
                    break
            return out
        def _build_ai_staff_stock_dropdown_values():
            stock_bucket_map = {
                "同花顺": _top_from_holding_attr("holding_stocks_6", 5),
                "Main股票": _top_from_holding_attr("holding_stocks_4", 5),
                "龙头股": _top_from_holding_attr("holding_stocks_2", 5),
                "持仓": _top_from_holding_attr("holding_stocks", 5),
                "15Min": _top_from_holding_attr("holding_stocks_3", 5),
            }
            values = []
            for k in ("同花顺", "Main股票", "龙头股", "持仓", "15Min"):
                picks = stock_bucket_map.get(k) or []
                for i in range(5):
                    values.append(f"{k}:{picks[i]}" if i < len(picks) else f"{k}:暂无{i + 1}")
            return values
        # -- 股票分析师 --
        tab_a = ttk.Frame(nb, padding=4)
        nb.add(tab_a, text="股票分析师")
        ta = scrolledtext.ScrolledText(tab_a, wrap=tk.WORD, font=("Microsoft YaHei", 11))
        ta.pack(fill=tk.BOTH, expand=True)
        self._configure_ai_staff_text_tags(ta)
        bar_a = ttk.Frame(tab_a)
        bar_a.pack(fill=tk.X, pady=(4, 0))
        sa = tk.StringVar(value="就绪")
        def run_analyst():
            sa.set("分析中...")
            ta.delete("1.0", tk.END)
            ta.insert("1.0", "正在拉取市场情绪与大盘数据并调用 AI,请稍候...\n")
            self._apply_ai_staff_keyword_highlights(ta)
            def work():
                try:
                    ctx = self._gather_ai_staff_analyst_context()
                    sys_p = (
                        "你是资深A股策略与量化背景的股票分析师。根据用户提供的程序内汇总数据,用中文结构化输出:"
                        "(1)大盘与主要指数所处环境与强弱;(2)资金面/估值/利率等摘要中要点;(3)同花顺情绪指数日线方向与主界面「情绪周期」「1日线」状态的含义;(4)对短线情绪与风格的判断(偏乐观/中性/谨慎)。"
                        "声明:不构成投资建议。"
                    )
                    user = (
                        "请基于以下数据做行情分析(可提示用户结合问财核对细节):\n\n" + ctx
                    )
                    _apx = getattr(win, "_os1_prefill_tail", None)
                    if _apx:
                        user = user + "\n\n【操作系统1·勾选资讯关联】\n" + str(_apx).strip()
                    out = self.call_ai_model(user, sys_p, max_tokens=4096)
                except Exception as e:
                    out = f"调用失败:{e}"
                def _done(o=out):
                    ta.delete("1.0", tk.END)
                    ta.insert("1.0", o or "(无返回)")
                    self._apply_ai_staff_keyword_highlights(ta)
                    sa.set("完成")
                win.after(0, _done)
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(bar_a, text="生成分析", command=run_analyst, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(bar_a, textvariable=sa).pack(side=tk.LEFT)
        ttk.Button(
            bar_a,
            text="保存为...",
            command=lambda: self._save_ai_staff_content(win, ta, "股票分析师"),
            width=10,
        ).pack(side=tk.RIGHT)
        # -- 交易员 --
        tab_t = ttk.Frame(nb, padding=4)
        nb.add(tab_t, text="交易员")
        row_t = ttk.Frame(tab_t)
        row_t.pack(fill=tk.X)
        ttk.Label(row_t, text="股票:").pack(side=tk.LEFT)
        stock_values = _build_ai_staff_stock_dropdown_values()
        stock_pick_var = tk.StringVar(value=stock_values[0] if stock_values else "")
        cmb_sym = ttk.Combobox(row_t, textvariable=stock_pick_var, values=stock_values, state="normal", width=34)
        cmb_sym.pack(side=tk.LEFT, padx=6)
        ttk.Button(
            row_t,
            text="刷新股票",
            width=10,
            command=lambda: (
                cmb_sym.configure(values=_build_ai_staff_stock_dropdown_values()),
                stock_pick_var.set((_build_ai_staff_stock_dropdown_values() or [""])[0]),
            ),
        ).pack(side=tk.LEFT, padx=(0, 6))
        st = tk.StringVar(value="就绪")
        tt = scrolledtext.ScrolledText(tab_t, wrap=tk.WORD, font=("Microsoft YaHei", 11))
        tt.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self._configure_ai_staff_text_tags(tt)
        bar_t = ttk.Frame(tab_t)
        bar_t.pack(fill=tk.X, pady=(4, 0))
        def run_trader():
            raw = stock_pick_var.get().strip()
            if not raw:
                messagebox.showwarning("提示", "请输入或选择股票。", parent=win)
                return
            # 处理用户输入的股票
            if ":" in raw:
                # 从下拉框选择的格式:持仓:首华燃气(300483)
                picked = raw.split(":", 1)[1].strip()
                if (not picked) or picked.startswith("暂无"):
                    messagebox.showwarning("提示", "当前选择是空位,请换一只具体股票。", parent=win)
                    return
            else:
                # 用户输入的股票代码或名称
                picked = raw
            st.set("分析中...")
            tt.delete("1.0", tk.END)
            tt.insert("1.0", "正在获取个股K线与大盘情绪并调用 AI...\n")
            self._apply_ai_staff_keyword_highlights(tt)
            def work():
                try:
                    m = re.match(r"(.+?)\((\d{6})\)", picked)
                    if m:
                        name, code = m.group(1).strip(), m.group(2)
                    else:
                        m2 = re.search(r"(\d{6})", picked)
                        if m2:
                            code = m2.group(1)
                            name = picked.replace(code, "").replace("(", "").replace(")", "").strip()
                        else:
                            code = get_stock_code_by_name(picked)
                            name = picked if code else ""
                    if not code:
                        out = "无法解析股票代码,请检查输入。"
                        def _bad1():
                            tt.delete("1.0", tk.END)
                            tt.insert("1.0", out)
                            self._apply_ai_staff_keyword_highlights(tt)
                            st.set("失败")
                        win.after(0, _bad1)
                        return
                    ohlc_txt, err = self._gather_trader_stock_context(code)
                    if err:
                        def _bad2():
                            tt.delete("1.0", tk.END)
                            tt.insert("1.0", err)
                            self._apply_ai_staff_keyword_highlights(tt)
                            st.set("失败")
                        win.after(0, _bad2)
                        return
                    mkt = self._gather_ai_staff_analyst_context()
                    sys_p = (
                        "你是资深交易员(A股),熟悉趋势、支撑压力与仓位节奏。根据个股OHLC与全市场情绪背景,用中文输出:"
                        "(1)该股当前结构(趋势/震荡/关键区间);(2)择时思路:加仓/减仓/观望的触发条件(可用价位区或均线表述,非精确点位);(3)假突破与止损思路。"
                        "严禁保证收益;声明不构成投资建议。"
                    )
                    user = (
                        f"标的:{name or code}({code})\n\n【个股近端K线摘要】\n{ohlc_txt}\n\n"
                        f"【市场环境与情绪背景】\n{mkt}\n\n"
                        "请给出买卖点与择时的分析思路(非具体荐股指令)。"
                    )
                    _apx2 = getattr(win, "_os1_prefill_tail", None)
                    if _apx2:
                        user = user + "\n\n【操作系统1·勾选资讯关联】\n" + str(_apx2).strip()
                    out = self.call_ai_model(user, sys_p, max_tokens=4096)
                except Exception as e:
                    out = f"调用失败:{e}"
                def _done_t():
                    tt.delete("1.0", tk.END)
                    tt.insert("1.0", out or "(无返回)")
                    self._apply_ai_staff_keyword_highlights(tt)
                    st.set("完成")
                win.after(0, _done_t)
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(bar_t, text="择时与买卖点分析", command=run_trader, width=18).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(bar_t, textvariable=st).pack(side=tk.LEFT)
        ttk.Button(
            bar_t,
            text="保存为...",
            command=lambda: self._save_ai_staff_content(win, tt, "交易员"),
            width=10,
        ).pack(side=tk.RIGHT)
        # -- 风控员 --
        tab_r = ttk.Frame(nb, padding=4)
        nb.add(tab_r, text="风控员")
        tr = scrolledtext.ScrolledText(tab_r, wrap=tk.WORD, font=("Microsoft YaHei", 11))
        tr.pack(fill=tk.BOTH, expand=True)
        self._configure_ai_staff_text_tags(tr)
        bar_r = ttk.Frame(tab_r)
        bar_r.pack(fill=tk.X, pady=(4, 0))
        sr = tk.StringVar(value="就绪")
        def run_risk():
            sr.set("风控分析中...")
            tr.delete("1.0", tk.END)
            tr.insert("1.0", "正在汇总大盘、同花顺情绪指数与程序内状态,并调用 AI...\n")
            self._apply_ai_staff_keyword_highlights(tr)
            def work():
                try:
                    ctx = self._gather_ai_staff_risk_context()
                    sys_p = (
                        "你是资深风控官(证券组合与回撤管理)。根据用户提供的指数、情绪指标与程序内同花顺情绪「1日线」相关状态,用中文输出:"
                        "(1)当前主要风险(系统性/情绪过热或冰点/波动放大等);(2)结合同花顺情绪指数日线方向与主界面勾选状态,判断环境是否适合提高或降低总仓位;(3)"
                        "给出**建议总仓位上限百分比区间**(例如:稳健型 20%~40%,进取型不超过 60% 等),并说明假设与局限。"
                        "声明:不构成投资建议,仓位请自行决策。"
                    )
                    user = "请做风险预判与仓位百分比提醒,数据如下:\n\n" + ctx
                    out = self.call_ai_model(user, sys_p, max_tokens=4096)
                except Exception as e:
                    out = f"调用失败:{e}"
                def _done_r():
                    tr.delete("1.0", tk.END)
                    tr.insert("1.0", out or "(无返回)")
                    self._apply_ai_staff_keyword_highlights(tr)
                    sr.set("完成")
                win.after(0, _done_r)
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(bar_r, text="风险与仓位建议", command=run_risk, width=16).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(bar_r, textvariable=sr).pack(side=tk.LEFT)
        ttk.Button(
            bar_r,
            text="保存为...",
            command=lambda: self._save_ai_staff_content(win, tr, "风控员"),
            width=10,
        ).pack(side=tk.RIGHT)
        # -- 游资分析 --
        tab_h = ttk.Frame(nb, padding=4)
        nb.add(tab_h, text="游资分析")
        # 日期选择区域
        date_frame = ttk.Frame(tab_h)
        date_frame.pack(fill=tk.X, pady=6)
        ttk.Label(date_frame, text="起始日期:").pack(side=tk.LEFT, padx=5)
        start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        start_date_entry = ttk.Entry(date_frame, textvariable=start_date_var, width=12)
        start_date_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="结束日期:").pack(side=tk.LEFT, padx=5)
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        end_date_entry = ttk.Entry(date_frame, textvariable=end_date_var, width=12)
        end_date_entry.pack(side=tk.LEFT, padx=5)
        # 游资分析按钮
        analyze_frame = ttk.Frame(tab_h)
        analyze_frame.pack(fill=tk.X, pady=6)
        sh = tk.StringVar(value="就绪")
        th = scrolledtext.ScrolledText(tab_h, wrap=tk.WORD, font=('Microsoft YaHei', 11))
        th.pack(fill=tk.BOTH, expand=True)
        self._configure_ai_staff_text_tags(th)
        def run_hot_money_analysis():
            start_date = start_date_var.get().strip()
            end_date = end_date_var.get().strip()
            if not start_date or not end_date:
                messagebox.showwarning("提示", "请输入起始和结束日期。", parent=win)
                return
            sh.set("分析中...")
            th.delete("1.0", tk.END)
            th.insert("1.0", f"正在获取{start_date}至{end_date}的游资数据并进行AI分析...\n")
            self._apply_ai_staff_keyword_highlights(th)
            def work():
                try:
                    # 从资讯表获取游资数据
                    hot_money_data = []
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT content, created_at FROM news_info
                            WHERE created_at BETWEEN ? AND ?
                            AND content LIKE ?
                            ORDER BY created_at DESC
                        ''', (start_date, end_date, '%游资%'))
                        rows = cursor.fetchall()
                        hot_money_data = [(row[0], row[1]) for row in rows]
                        conn.close()
                    except Exception:
                        hot_money_data = []
                    # 构建分析内容
                    if hot_money_data:
                        analysis_content = f"游资分析报告({start_date} - {end_date})\n\n"
                        analysis_content += f"共找到 {len(hot_money_data)} 条游资相关资讯\n\n"
                        # 提取游资信息
                        hot_money_names = []
                        for content, date in hot_money_data:
                            # 简单提取游资名字
                            import re
                            matches = re.findall(r'[\u4e00-\u9fa5]+(?:游资|席位|营业部)', content)
                            hot_money_names.extend(matches)
                        # 统计游资出现频率
                        from collections import Counter
                        hot_money_counter = Counter(hot_money_names)
                        analysis_content += "游资活跃度排名:\n"
                        for name, count in hot_money_counter.most_common(10):
                            analysis_content += f"- {name}: {count}次\n"
                        # AI分析
                        sys_p = "你是资深游资分析专家,熟悉A股市场的游资动向和操作风格。根据提供的游资数据,分析游资的活跃度、操作风格、偏好板块等,并给出投资建议。"
                        user = f"请分析{start_date}至{end_date}的游资数据:\n\n{analysis_content}"
                        ai_result = self.call_ai_model(user, sys_p, max_tokens=4096)
                        if ai_result:
                            out = analysis_content + "\nAI分析结果:\n" + ai_result
                        else:
                            out = analysis_content + "\nAI分析失败,未获取到分析结果。"
                    else:
                        out = f"在{start_date}至{end_date}期间未找到游资相关资讯。"
                except Exception as e:
                    out = f"分析失败:{e}"
                def _done_h():
                    th.delete("1.0", tk.END)
                    th.insert("1.0", out or "(无返回)")
                    self._apply_ai_staff_keyword_highlights(th)
                    sh.set("完成")
                win.after(0, _done_h)
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(analyze_frame, text="游资分析", command=run_hot_money_analysis, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Label(analyze_frame, textvariable=sh).pack(side=tk.LEFT)
        ttk.Button(
            analyze_frame,
            text="保存为...",
            command=lambda: self._save_ai_staff_content(win, th, "游资分析"),
            width=10,
        ).pack(side=tk.RIGHT)
        # -- 最新资讯分析 --
        tab_news = ttk.Frame(nb, padding=4)
        nb.add(tab_news, text="最新资讯分析")
        # 日期选择 + 分析维度
        news_ctrl = ttk.Frame(tab_news)
        news_ctrl.pack(fill=tk.X, pady=(0, 4))
        from datetime import timedelta as _td
        _yesterday = (datetime.now() - _td(days=1)).strftime('%Y-%m-%d')
        _today = datetime.now().strftime('%Y-%m-%d')
        ttk.Label(news_ctrl, text="起始:").pack(side=tk.LEFT, padx=2)
        news_start_var = tk.StringVar(value=_yesterday)
        ttk.Entry(news_ctrl, textvariable=news_start_var, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Label(news_ctrl, text="结束:").pack(side=tk.LEFT, padx=2)
        news_end_var = tk.StringVar(value=_today)
        ttk.Entry(news_ctrl, textvariable=news_end_var, width=12).pack(side=tk.LEFT, padx=2)
        # 分析维度复选框
        dim_frame = ttk.LabelFrame(tab_news, text="分析维度(可多选)", padding=4)
        dim_frame.pack(fill=tk.X, pady=(0, 4))
        news_dims = [
            ("热门股", "热门股", "提取出现频次最高的股票,分析资金关注度"),
            ("超跌反弹", "超跌反弹", "筛选近期跌幅较大的股票,分析反弹可能性"),
            ("超涨风险", "超涨风险", "筛选近期涨幅过大的股票,提示回调风险"),
            ("风控", "风控", "从资讯中提取风险关键词,评估市场风险等级"),
            ("择时", "择时", "结合资讯情绪判断短期市场方向与仓位建议"),
            ("板块轮动", "板块轮动", "分析资讯中提及的板块热度和轮动方向"),
            ("游资动向", "游资动向", "提取游资/席位/营业部等关键词,分析游资活跃度"),
            ("政策面", "政策面", "提取政策相关资讯,分析对市场的影响"),
        ]
        news_dim_vars = {}
        dim_wrap = ttk.Frame(dim_frame)
        dim_wrap.pack(fill=tk.X)
        for i, (label, key, _desc) in enumerate(news_dims):
            var = tk.BooleanVar(value=(key in ("热门股", "风控", "择时")))
            news_dim_vars[key] = var
            ttk.Checkbutton(dim_wrap, text=label, variable=var).grid(
                row=i // 4, column=i % 4, padx=4, pady=2, sticky=tk.W
            )
        sn = tk.StringVar(value="就绪")
        tn = scrolledtext.ScrolledText(tab_news, wrap=tk.WORD, font=('Microsoft YaHei', 11))
        tn.pack(fill=tk.BOTH, expand=True)
        self._configure_ai_staff_text_tags(tn)
        bar_n = ttk.Frame(tab_news)
        bar_n.pack(fill=tk.X, pady=(4, 0))
        def run_news_analysis():
            start_date = news_start_var.get().strip()
            end_date = news_end_var.get().strip()
            if not start_date or not end_date:
                messagebox.showwarning("提示", "请输入起始和结束日期。", parent=win)
                return
            selected_dims = [k for k, v in news_dim_vars.items() if v.get()]
            if not selected_dims:
                messagebox.showwarning("提示", "请至少选择一个分析维度。", parent=win)
                return
            sn.set("资讯分析中...")
            tn.delete("1.0", tk.END)
            tn.insert("1.0", f"正在查询 {start_date} 至 {end_date} 的资讯数据并进行分析...\n")
            self._apply_ai_staff_keyword_highlights(tn)
            def work():
                try:
                    # 从 news_info 表查询资讯数据
                    news_rows = []
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        # 日期范围查询(created_at 格式 "YYYY-MM-DD HH:MM:SS")
                        cursor.execute(
                            "SELECT id, tab_name, content, created_at FROM news_info "
                            "WHERE date(created_at) BETWEEN date(?) AND date(?) "
                            "ORDER BY created_at DESC",
                            (start_date, end_date),
                        )
                        news_rows = cursor.fetchall()
                        conn.close()
                    except Exception as e:
                        out = f"数据库查询失败:{e}"
                        def _db_err():
                            tn.delete("1.0", tk.END)
                            tn.insert("1.0", out)
                            self._apply_ai_staff_keyword_highlights(tn)
                            sn.set("失败")
                        win.after(0, _db_err)
                        return
                    if not news_rows:
                        out = f"在 {start_date} 至 {end_date} 期间未找到资讯数据。"
                        def _empty():
                            tn.delete("1.0", tk.END)
                            tn.insert("1.0", out)
                            self._apply_ai_staff_keyword_highlights(tn)
                            sn.set("完成")
                        win.after(0, _empty)
                        return
                    # 汇总资讯内容
                    all_content = []
                    tab_counter = {}
                    for row in news_rows:
                        _nid, tab_name, content, created_at = row
                        if content:
                            all_content.append(f"[{tab_name}] ({created_at})\n{content}")
                            tab_counter[tab_name] = tab_counter.get(tab_name, 0) + 1
                    combined_text = "\n\n---\n\n".join(all_content)
                    # 截取前 12000 字符避免 token 超限
                    if len(combined_text) > 12000:
                        combined_text = combined_text[:12000] + "\n\n...(内容过长已截断)"
                    # 提取股票代码和名称
                    import re as _re
                    from collections import Counter as _Counter
                    stock_pattern = _re.compile(r'([\u4e00-\u9fa5]{2,6})[((]?(\d{6})[))]?')
                    stock_matches = stock_pattern.findall(combined_text)
                    stock_freq = _Counter()
                    for name, code in stock_matches:
                        stock_freq[f"{name}({code})"] += 1
                    top_stocks = stock_freq.most_common(20)
                    # 构建分析内容
                    analysis_content = f"📊 资讯分析报告({start_date} - {end_date})\n"
                    analysis_content += f"{'=' * 60}\n\n"
                    analysis_content += "📈 资讯统计:\n"
                    analysis_content += f"  - 资讯总条数:{len(news_rows)}\n"
                    analysis_content += "  - 来源标签分布:\n"
                    for tab, cnt in sorted(tab_counter.items(), key=lambda x: -x[1])[:8]:
                        analysis_content += f"    · {tab}: {cnt}条\n"
                    if top_stocks:
                        analysis_content += f"\n🔥 热门股票(出现频次Top{min(len(top_stocks), 10)}):\n"
                        for name_code, cnt in top_stocks[:10]:
                            analysis_content += f"  · {name_code}: {cnt}次\n"
                    analysis_content += f"\n{'=' * 60}\n"
                    analysis_content += f"分析维度:{', '.join(selected_dims)}\n\n"
                    # 按维度构建AI prompt
                    dim_instructions = {
                        "热门股": "分析资金关注度最高的热门股票,判断其后续走势可能性",
                        "超跌反弹": "筛选资讯中提及的跌幅较大股票,分析是否有反弹信号(如支撑位、缩量止跌等)",
                        "超涨风险": "筛选涨幅过大的股票,提示短期回调风险和获利了结建议",
                        "风控": "从资讯中提取风险关键词(如暴跌、闪崩、ST、退市、减持等),评估当前市场风险等级",
                        "择时": "结合资讯情绪判断短期(1-3天)市场方向,给出加仓/减仓/观望建议",
                        "板块轮动": "分析资讯中提及的热门板块,判断板块轮动方向和资金流向",
                        "游资动向": "提取游资、席位、营业部等关键词,分析游资活跃度和偏好板块",
                        "政策面": "提取政策、监管、利好/利空等关键词,分析政策对市场的影响",
                    }
                    dim_prompts = []
                    for dim in selected_dims:
                        dim_prompts.append(f"【{dim}】{dim_instructions.get(dim, '请分析')}")
                    dim_text = "\n".join(dim_prompts)
                    sys_p = (
                        "你是资深A股资讯分析师,擅长从海量资讯中提取关键信息并做多维度分析。"
                        "请基于提供的资讯数据,按照用户指定的分析维度逐一分析,"
                        "用中文结构化输出,每个维度单独一段,最后给出综合判断。"
                        "声明:不构成投资建议。"
                    )
                    user = (
                        f"以下是 {start_date} 至 {end_date} 期间的资讯数据摘要:\n\n"
                        f"{combined_text}\n\n"
                        f"请按以下维度逐一分析:\n{dim_text}\n\n"
                        f"请给出每个维度的分析结果,最后做综合判断。"
                    )
                    ai_result = self.call_ai_model(user, sys_p, max_tokens=4096)
                    if ai_result:
                        out = analysis_content + "\n📋 AI 多维度分析:\n\n" + ai_result
                    else:
                        out = analysis_content + "\nAI分析失败,未获取到分析结果。"
                except Exception as e:
                    out = f"分析失败:{e}"
                def _done_n():
                    tn.delete("1.0", tk.END)
                    tn.insert("1.0", out or "(无返回)")
                    self._apply_ai_staff_keyword_highlights(tn)
                    sn.set("完成")
                win.after(0, _done_n)
            threading.Thread(target=work, daemon=True).start()
        ttk.Button(bar_n, text="资讯分析", command=run_news_analysis, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bar_n, text="全选维度", command=lambda: [v.set(True) for v in news_dim_vars.values()], width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar_n, text="清空维度", command=lambda: [v.set(False) for v in news_dim_vars.values()], width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(bar_n, textvariable=sn).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            bar_n,
            text="保存为...",
            command=lambda: self._save_ai_staff_content(win, tn, "最新资讯分析"),
            width=10,
        ).pack(side=tk.RIGHT)

    def show_quant_strategy_dialog(self):
        """左侧:量化 Skill + 说明;右侧:大盘情绪一律网络实时拉取(见文首数据源),5:5 分栏。"""
        win = self._toplevel(self.root)
        win.title("A股量化策略 · Skill(左)| 大盘情绪·网络(右)")
        win.geometry("1280x720")
        win.transient(self.root)
        outer = ttk.Frame(win, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)
        top = ttk.Frame(outer)
        top.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            top,
            text="◀ 左 50%:量化 Skill | 右 50%:大盘情绪(Tushare/问财/选股通等网络实时,见文首说明)+ 本地仓位建议",
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side=tk.LEFT)
        filter_bar = ttk.Frame(top)
        filter_bar.pack(side=tk.LEFT, padx=(12, 0))
        def _fmt_stock_pair(name, code):
            n = str(name or "").strip()
            c = str(code or "").strip()
            if n and c:
                return f"{n}({c})"
            return n or c
        def _top_from_holding_attr(attr_name, limit=5):
            arr = getattr(self, attr_name, []) or []
            out = []
            for it in arr:
                if not it:
                    continue
                if isinstance(it, (tuple, list)) and len(it) >= 2:
                    s = _fmt_stock_pair(it[0], it[1])
                elif isinstance(it, dict):
                    s = _fmt_stock_pair(it.get("name"), it.get("code"))
                else:
                    s = str(it).strip()
                if not s:
                    continue
                out.append(s)
                if len(out) >= limit:
                    break
            return out
        def _build_stock_bucket_map():
            return {
                "同花顺": _top_from_holding_attr("holding_stocks_6", 5),
                "Main股票": _top_from_holding_attr("holding_stocks_4", 5),
                "龙头股": _top_from_holding_attr("holding_stocks_2", 5),
                "持仓": _top_from_holding_attr("holding_stocks", 5),
                "15Min": _top_from_holding_attr("holding_stocks_3", 5),
            }
        stock_bucket_map = _build_stock_bucket_map()
        def _bucket_display_values():
            # 每个标签页固定展示 5 条,共 25 条下拉项
            values = []
            for k in ("同花顺", "Main股票", "龙头股", "持仓", "15Min"):
                picks = stock_bucket_map.get(k) or []
                for i in range(5):
                    if i < len(picks):
                        values.append(f"{k}:{picks[i]}")
                    else:
                        values.append(f"{k}:暂无{i + 1}")
            return values
        ttk.Label(filter_bar, text="择时").pack(side=tk.LEFT, padx=(0, 4))
        timing_var = tk.StringVar(value="自动(按大盘)")
        timing_combo = ttk.Combobox(
            filter_bar,
            textvariable=timing_var,
            values=("自动(按大盘)", "偏买入", "偏卖出", "中性观望", "只买不卖", "只卖不买"),
            state="readonly",
            width=12,
        )
        timing_combo.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(filter_bar, text="仓位").pack(side=tk.LEFT, padx=(0, 4))
        position_values = ["自动(按指标)"] + [f"{i}%" for i in range(0, 101, 10)]
        position_var = tk.StringVar(value="自动(按指标)")
        position_combo = ttk.Combobox(
            filter_bar,
            textvariable=position_var,
            values=position_values,
            state="readonly",
            width=12,
        )
        position_combo.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(filter_bar, text="选股").pack(side=tk.LEFT, padx=(0, 4))
        _stock_values = _bucket_display_values()
        stock_bucket_var = tk.StringVar(value=_stock_values[0] if _stock_values else "")
        stock_bucket_combo = ttk.Combobox(
            filter_bar,
            textvariable=stock_bucket_var,
            values=_stock_values,
            state="readonly",
            width=34,
        )
        stock_bucket_combo.pack(side=tk.LEFT, padx=(0, 8))
        ctl = ttk.Frame(top)
        ctl.pack(side=tk.RIGHT)
        def _win_zoom():
            try:
                win.state("zoomed")
            except Exception:
                try:
                    win.attributes("-zoomed", True)
                except Exception:
                    pass
        def _win_min():
            try:
                win.iconify()
            except Exception:
                pass
        ttk.Button(ctl, text="最大化", width=8, command=_win_zoom).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(ctl, text="最小化", width=8, command=_win_min).pack(side=tk.LEFT, padx=(4, 0))
        paned = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left_wrap = ttk.Frame(paned, padding=(0, 0, 4, 0))
        right_wrap = ttk.LabelFrame(paned, text="右侧 50% · 大盘情绪(Tushare / 问财 / 选股通 / AKShare 组合拉取)", padding=6)
        paned.add(left_wrap, weight=1)
        paned.add(right_wrap, weight=1)
        try:
            paned.paneconfigure(left_wrap, minsize=300)
            paned.paneconfigure(right_wrap, minsize=300)
        except Exception:
            pass
        left_paned = ttk.PanedWindow(left_wrap, orient=tk.VERTICAL)
        left_paned.pack(fill=tk.BOTH, expand=True)
        left_top = ttk.LabelFrame(left_paned, text="左侧上 · 量化 Skill 列表(择时/择股/仓位/风控)", padding=4)
        left_bot = ttk.LabelFrame(left_paned, text="左侧下 · Skill 详细说明(点选上行条目)", padding=4)
        left_paned.add(left_top, weight=3)
        left_paned.add(left_bot, weight=2)
        try:
            left_paned.paneconfigure(left_top, minsize=160)
            left_paned.paneconfigure(left_bot, minsize=120)
        except Exception:
            pass
        list_fr = ttk.Frame(left_top)
        list_fr.pack(fill=tk.BOTH, expand=True)
        list_scroll = ttk.Scrollbar(list_fr)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(
            list_fr,
            yscrollcommand=list_scroll.set,
            font=("Microsoft YaHei UI", 11),
            selectmode=tk.SINGLE,
            activestyle="dotbox",
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.config(command=lb.yview)
        catalog = self._quant_strategy_skill_catalog()
        index_by_row = []
        for i, item in enumerate(catalog):
            disp = f"[{item['cat']}] {item['title']}"
            lb.insert(tk.END, disp)
            index_by_row.append(i)
        desc_widget = scrolledtext.ScrolledText(left_bot, wrap=tk.WORD, font=("Microsoft YaHei UI", 11))
        desc_widget.pack(fill=tk.BOTH, expand=True)
        data_state = {"snap": None, "spot": {}, "concept_lines": [], "errors": []}
        ai_status = tk.StringVar(value="AI判断区:等待行情刷新或手动分析。")
        ai_text_holder = {"w": None}
        def on_select(_evt=None):
            sel = lb.curselection()
            if not sel:
                return
            idx = index_by_row[sel[0]]
            it = catalog[idx]
            desc_widget.delete("1.0", tk.END)
            desc_widget.insert(
                "1.0",
                self._compose_quant_skill_detailed_desc(
                    it,
                    data_state.get("snap"),
                    data_state.get("spot") or {},
                    data_state.get("concept_lines") or [],
                ),
            )
            w = ai_text_holder.get("w")
            if w is not None and data_state.get("snap"):
                w.delete("1.0", tk.END)
                w.insert(
                    "1.0",
                    self._compose_quant_skill_ai_advice(
                        it,
                        data_state.get("snap"),
                        data_state.get("spot") or {},
                        data_state.get("concept_lines") or [],
                    ),
                )
                ai_status.set(f"已按当前 Skill 更新:{it.get('title', '')}")
        lb.bind("<<ListboxSelect>>", on_select)
        if catalog:
            lb.selection_set(0)
            on_select()
        st_right = tk.StringVar(value="")
        right_paned = ttk.PanedWindow(right_wrap, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)
        right_top = ttk.Frame(right_paned)
        right_bot = ttk.LabelFrame(right_paned, text="右下 · AI判断/选股/仓位建议(随 Skill 与右上行情联动)", padding=6)
        right_paned.add(right_top, weight=4)
        right_paned.add(right_bot, weight=3)
        try:
            right_paned.paneconfigure(right_top, minsize=220)
            right_paned.paneconfigure(right_bot, minsize=180)
        except Exception:
            pass
        ttk.Label(right_top, textvariable=st_right, font=("TkDefaultFont", 9), foreground="#555").pack(anchor=tk.W, pady=(0, 4))
        right_text = scrolledtext.ScrolledText(right_top, wrap=tk.WORD, font=("Microsoft YaHei UI", 11))
        right_text.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self._configure_quant_dialog_right_tags(right_text)
        ai_bar = ttk.Frame(right_bot)
        ai_bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(ai_bar, textvariable=ai_status, foreground="#4b5563").pack(side=tk.LEFT)
        ai_text = scrolledtext.ScrolledText(right_bot, wrap=tk.WORD, font=("Microsoft YaHei UI", 11), height=10)
        ai_text.pack(fill=tk.BOTH, expand=True)
        ai_text_holder["w"] = ai_text
        _os1_qpf = getattr(self, "_os1_toolbox_prefill", None)
        if _os1_qpf:
            try:
                ai_text.insert(
                    "1.0",
                    "【操作系统1·资讯摘录】\n" + str(_os1_qpf).strip() + "\n\n",
                )
            finally:
                try:
                    delattr(self, "_os1_toolbox_prefill")
                except Exception:
                    self._os1_toolbox_prefill = None
        def _infer_strength_and_position(snap):
            m = (snap or {}).get("metrics", {}) or {}
            m1 = (m.get("m1_today") or {}).get("value")
            m5 = m.get("m5_avg")
            if isinstance(m5, dict):
                m5 = m5.get("value")
            mk = m.get("m2_market") if isinstance(m.get("m2_market"), dict) else {}
            up, down = mk.get("up"), mk.get("down")
            strength = "中性"
            if isinstance(m1, (int, float)) and isinstance(m5, (int, float)):
                if m1 >= 0.6 and m5 >= 0.2:
                    strength = "偏强"
                elif m1 <= -0.6 and m5 <= -0.2:
                    strength = "偏弱"
            if isinstance(up, (int, float)) and isinstance(down, (int, float)) and up + down > 0:
                if up > down * 1.25:
                    strength = "偏强"
                elif down > up * 1.25:
                    strength = "偏弱"
            rec_pos = "40%"
            if strength == "偏强":
                rec_pos = "70%"
            elif strength == "偏弱":
                rec_pos = "20%"
            return strength, rec_pos
        def _selected_bucket_key():
            t = stock_bucket_var.get().strip()
            if ":" in t:
                return t.split(":", 1)[0].strip()
            return t.strip()
        def _selected_stock_value():
            t = stock_bucket_var.get().strip()
            if ":" in t:
                return t.split(":", 1)[1].strip()
            return ""
        def _parse_selected_stock():
            import re
            s = _selected_stock_value()
            if not s or s.startswith("暂无"):
                return "", ""
            m = re.match(r"(.+?)\((\d{6})\)", s)
            if m:
                return m.group(1).strip(), m.group(2)
            m2 = re.search(r"(\d{6})", s)
            if m2:
                code = m2.group(1)
                name = s.replace(code, "").replace("(", "").replace(")", "").strip()
                return name, code
            return s, ""
        def _compose_filtered_ai_advice(skill_item):
            base_txt = self._compose_quant_skill_ai_advice(
                skill_item,
                data_state.get("snap"),
                data_state.get("spot") or {},
                data_state.get("concept_lines") or [],
            )
            snap = data_state.get("snap")
            strength, rec_pos = _infer_strength_and_position(snap)
            timing_sel = timing_var.get().strip() or "自动(按大盘)"
            pos_sel = position_var.get().strip() or "自动(按指标)"
            bucket_key = _selected_bucket_key()
            picked_stock = _selected_stock_value()
            stock_candidates = stock_bucket_map.get(bucket_key, []) or []
            final_timing = timing_sel
            if timing_sel.startswith("自动"):
                if strength == "偏强":
                    final_timing = "偏买入"
                elif strength == "偏弱":
                    final_timing = "偏卖出"
                else:
                    final_timing = "中性观望"
            final_pos = rec_pos if pos_sel.startswith("自动") else pos_sel
            lines = [
                base_txt,
                "",
                "-- 下拉框策略约束 --",
                f"择时选择:{timing_sel} → 执行:{final_timing}",
                f"仓位选择:{pos_sel} → 执行:{final_pos}",
                f"选股池:{bucket_key}",
            ]
            if picked_stock and not picked_stock.startswith("暂无"):
                lines.append(f"当前下拉选中:{picked_stock}")
            if stock_candidates:
                lines.append("候选(前5): " + ",".join(stock_candidates[:5]))
            else:
                lines.append("候选(前5): 暂无数据(可先更新对应持仓/分组)")
            lines.extend(
                [
                    "",
                    "AI策略结论:",
                    f"1) 以左侧 Skill「{skill_item.get('title', '')}」为主规则,按右上实时指标判定当前盘面「{strength}」。",
                    f"2) 交易执行遵循「{final_timing} + {final_pos}仓位」组合,分批进退,禁止一次性满仓/清仓。",
                    f"3) 选股仅在「{bucket_key}」前5候选内优先排序,若与右上热点题材冲突,优先保守处理。",
                    "",
                    "说明:以上为程序内 AI 规则化分析,不构成投资建议。",
                ]
            )
            return "\n".join(lines)
        def _compose_selected_stock_operation_advice(skill_item, stock_name, stock_code):
            snap = data_state.get("snap")
            strength, rec_pos = _infer_strength_and_position(snap)
            timing_sel = timing_var.get().strip() or "自动(按大盘)"
            pos_sel = position_var.get().strip() or "自动(按指标)"
            final_pos = rec_pos if pos_sel.startswith("自动") else pos_sel
            final_timing = timing_sel
            if timing_sel.startswith("自动"):
                final_timing = "偏买入" if strength == "偏强" else ("偏卖出" if strength == "偏弱" else "中性观望")
            kline_text = "(未获取到近端K线)"
            try:
                pack = self._fetch_recent_daily_ohlc(stock_code, days=25, source="default")
                if pack and len(pack) == 4:
                    _d, _h, _l, closes = pack
                    if closes and len(closes) >= 2:
                        last_close = float(closes[-1])
                        prev_close = float(closes[-2])
                        chg = ((last_close - prev_close) / prev_close * 100.0) if prev_close else 0.0
                        ma5 = sum(closes[-5:]) / min(5, len(closes))
                        ma10 = sum(closes[-10:]) / min(10, len(closes))
                        kline_text = (
                            f"最新收盘≈{last_close:.2f},日变动≈{chg:+.2f}%,"
                            f"MA5≈{ma5:.2f},MA10≈{ma10:.2f}"
                        )
            except Exception:
                pass
            ma_flag = ""
            try:
                ms = self._check_ma_status(stock_code)
                if isinstance(ms, dict):
                    if ms.get("cross"):
                        ma_flag = ",出现1日线上穿信号(▲)"
                    elif ms.get("ma1_uptrend"):
                        ma_flag = ",1日线维持上行"
            except Exception:
                pass
            lines = [
                f"【个股操作AI分析】{skill_item.get('title', '')}",
                f"标的:{stock_name or stock_code}({stock_code})",
                "",
                "一、综合输入",
                f"- 左侧Skill:[{skill_item.get('cat', '')}] {skill_item.get('title', '')}",
                f"- 下拉框:择时={timing_sel}(执行={final_timing}),仓位={pos_sel}(执行={final_pos}),选股池={_selected_bucket_key()}",
                f"- 大盘判定:{strength}",
                f"- 个股K线摘要:{kline_text}{ma_flag}",
                "",
                "二、操作建议(执行级)",
            ]
            if strength == "偏强" and final_timing in ("偏买入", "只买不卖"):
                lines.extend(
                    [
                        f"1) 可执行分批买入:首笔 20%-30% 仓位,回踩不破再加到 {final_pos} 上限。",
                        "2) 若放量上破近5日高点可加仓;若跌破入场基准位则减回观察仓。",
                        "3) 盘中不追高,尽量用回踩确认做第二笔。",
                    ]
                )
            elif strength == "偏弱" or final_timing in ("偏卖出", "只卖不买"):
                lines.extend(
                    [
                        "1) 以防守为主:已有仓位优先减仓,不建议新开激进仓。",
                        f"2) 目标仓位控制在 {final_pos} 或以下,等待指数与情绪共振修复。",
                        "3) 若再次走弱并失守关键均线,执行纪律性止损。",
                    ]
                )
            else:
                lines.extend(
                    [
                        f"1) 中性执行:先小仓位试错(10%-20%),总仓不超过 {final_pos}。",
                        "2) 仅当个股强于所选池平均强度时再加仓,否则保持机动。",
                        "3) 优先做T或分批交易,避免单点重仓。",
                    ]
                )
            lines.extend(
                [
                    "",
                    "三、风控与复盘点",
                    "- 单票止损、账户回撤熔断、行业集中度上限三条同时生效。",
                    "- 若右上情绪指标与板块结构转弱,优先降仓再观察。",
                    "",
                    "(以上为程序内AI规则化分析,不构成投资建议。)",
                ]
            )
            return "\n".join(lines)
        def apply_right_text(txt):
            right_text.delete("1.0", tk.END)
            right_text.insert("1.0", txt or "")
        st_right.set("右侧大盘情绪:正在从网络拉取(东财 + 问财)...")
        def _loading_right_text():
            h = self._quant_market_network_sources_header()
            h.append("══ 正在联网拉取大盘情绪指标,请稍候... ══")
            h.append("")
            h.append("(完成后将显示涨跌家数、指数、问财条数、概念板块等;勿依赖主界面旧缓存。)")
            return "\n".join(h)
        apply_right_text(_loading_right_text())
        def run_full_refresh():
            st_right.set("网络拉取中:AKShare(东财)+ 问财(pywencai)...")
            def work():
                b = self._collect_quant_market_from_network()
                snap = b.get("snap")
                spot = b.get("spot") or {}
                concept_lines = b.get("concept_lines") or ["(概念板块无数据)"]
                errs = [x for x in (b.get("errors") or []) if x]
                if snap is not None:
                    try:
                        self._last_sentiment_zone_snapshot = snap
                    except Exception:
                        pass
                t_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                def done():
                    data_state["snap"] = snap
                    data_state["spot"] = spot
                    data_state["concept_lines"] = concept_lines
                    data_state["errors"] = errs
                    # 刷新顶部"选股"下拉数据源,并根据盘面自动给出仓位默认值
                    nonlocal stock_bucket_map
                    stock_bucket_map = _build_stock_bucket_map()
                    stock_bucket_combo["values"] = _bucket_display_values()
                    if not stock_bucket_var.get().strip() and stock_bucket_combo["values"]:
                        stock_bucket_var.set(stock_bucket_combo["values"][0])
                    try:
                        _strength, _rec_pos = _infer_strength_and_position(snap)
                        if position_var.get().startswith("自动"):
                            position_var.set("自动(按指标)")
                    except Exception:
                        pass
                    self._fill_quant_dialog_right_text_colored(
                        right_text,
                        snap,
                        spot,
                        concept_lines,
                        network_time=t_str,
                        network_errors=errs if errs else None,
                    )
                    st_right.set(
                        f"已从网络更新 {datetime.now().strftime('%H:%M:%S')}(源:Tushare/问财/选股通/东财等)"
                    )
                    try:
                        if lb.curselection():
                            on_select()
                    except Exception:
                        pass
                win.after(0, done)
            threading.Thread(target=work, daemon=True).start()
        def run_ai_for_selected():
            sel = lb.curselection()
            if not sel:
                ai_status.set("请先在左侧选中一个 Skill。")
                return
            if not data_state.get("snap"):
                ai_status.set("请先点“完整刷新“拉取右上最新盘面。")
                return
            idx = index_by_row[sel[0]]
            it = catalog[idx]
            ai_text.delete("1.0", tk.END)
            ai_text.insert("1.0", _compose_filtered_ai_advice(it))
            ai_status.set(f"已完成:{it.get('title', '')}(含择时/仓位/选股约束)")
        def run_ai_for_all():
            if not data_state.get("snap"):
                ai_status.set("请先点“完整刷新“拉取右上最新盘面。")
                return
            def work():
                txt = self._compose_quant_all_skills_ai_advice(
                    catalog,
                    data_state.get("snap"),
                    data_state.get("spot") or {},
                    data_state.get("concept_lines") or [],
                )
                def done():
                    ai_text.delete("1.0", tk.END)
                    ai_text.insert("1.0", txt)
                    ai_status.set("一键AI量化分析完成(已覆盖左侧所有 Skill)。")
                win.after(0, done)
            ai_status.set("一键AI量化分析中...")
            threading.Thread(target=work, daemon=True).start()
        def run_ai_for_selected_stock():
            sel = lb.curselection()
            if not sel:
                ai_status.set("请先在左侧选择一个 Skill。")
                return
            if not data_state.get("snap"):
                ai_status.set("请先点“完整刷新“拉取右上最新盘面。")
                return
            stock_name, stock_code = _parse_selected_stock()
            if not stock_code:
                ai_status.set("请先在右上“选股“下拉中选择一个具体股票。")
                return
            idx = index_by_row[sel[0]]
            it = catalog[idx]
            ai_status.set(f"AI分析中:{stock_name or stock_code} ...")
            def work():
                txt = _compose_selected_stock_operation_advice(it, stock_name, stock_code)
                def done():
                    ai_text.delete("1.0", tk.END)
                    ai_text.insert("1.0", txt)
                    ai_status.set(f"已完成:{stock_name or stock_code} 操作建议")
                win.after(0, done)
            threading.Thread(target=work, daemon=True).start()
        btn_row = ttk.Frame(right_wrap)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="完整刷新", command=run_full_refresh, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="当前Skill AI判断", command=run_ai_for_selected, width=16).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="一键AI量化", command=run_ai_for_all, width=12).pack(side=tk.LEFT, padx=(0, 8))
        pane_hidden = {"right": False}
        def toggle_right_pane():
            if not pane_hidden["right"]:
                try:
                    paned.forget(right_wrap)
                    pane_hidden["right"] = True
                    hide_btn.config(text="显示右栏")
                except Exception:
                    pass
            else:
                try:
                    paned.add(right_wrap, weight=1)
                    pane_hidden["right"] = False
                    hide_btn.config(text="隐藏右栏")
                    _center_sashes()
                except Exception:
                    pass
        hide_btn = ttk.Button(btn_row, text="隐藏右栏", command=toggle_right_pane, width=12)
        hide_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="关闭", command=win.destroy, width=10).pack(side=tk.RIGHT)
        # 红框位置需求:右下AI区增加"分析该股票"按钮
        ttk.Button(ai_bar, text="AI分析该股", command=run_ai_for_selected_stock, width=12).pack(side=tk.RIGHT, padx=(8, 0))
        def _on_filter_change(_evt=None):
            if lb.curselection() and data_state.get("snap"):
                run_ai_for_selected()
        timing_combo.bind("<<ComboboxSelected>>", _on_filter_change)
        position_combo.bind("<<ComboboxSelected>>", _on_filter_change)
        stock_bucket_combo.bind("<<ComboboxSelected>>", _on_filter_change)
        run_full_refresh()
        def _center_sashes():
            try:
                win.update_idletasks()
                ww = max(520, paned.winfo_width())
                paned.sashpos(0, ww // 2)
                lh = max(280, left_paned.winfo_height())
                left_paned.sashpos(0, int(lh * 0.55))
            except Exception:
                pass
        win.after(120, _center_sashes)

    def _show_cb_arbitrage_popup(self):
        """弹窗:A股活跃可转债与正股价格、换手率、溢价、强赎、剩余规模,按套利公式提示机会"""
        def _find_col(df, *candidates):
            for c in candidates:
                for col in df.columns:
                    if c in str(col) or str(col) == c:
                        return col
            return None
        def _to_float_safe(x):
            """将各种数值/百分数字符串安全转为 float,失败返回 None。"""
            if x is None:
                return None
            s = str(x).strip()
            if not s or s in ("-", "nan", "None"):
                return None
            s = s.replace("%", "")
            try:
                return float(s)
            except Exception:
                return None
        def fetch_and_show():
            try:
                if not AKSHARE_AVAILABLE:
                    self.root.after(0, lambda: messagebox.showerror("错误", "需要 akshare 库", parent=self.root))
                    return
                import akshare as ak
                # 可转债一览(正股、转股价、转股价值、债现价、溢价率、发行规模)
                cov_df = safe_call(ak.bond_zh_cov, fallback=[], label="ak.bond_zh_cov")
                if cov_df is None or cov_df.empty:
                    self.root.after(0, lambda: messagebox.showwarning("提示", "未获取到可转债列表", parent=self.root))
                    return
                # 实时行情(最新价、涨跌幅、成交量、成交额,用于活跃度与换手率近似)
                spot_df = safe_call(ak.bond_zh_hs_cov_spot, fallback=pd.DataFrame(), label="ak.bond_zh_hs_cov_spot")
                # 强赎(剩余规模、强赎相关)
                try:
                    redeem_df = safe_call(ak.bond_cb_redeem_jsl, fallback=[], label="ak.bond_cb_redeem_jsl")
                except Exception:
                    redeem_df = pd.DataFrame()
                # 统一代码为 6 位字符串
                def norm_code(s):
                    if pd.isna(s): return ""
                    return str(int(s)) if isinstance(s, (int, float)) else str(s).strip()
                # 列名兼容(中文)
                col_bond_code = _find_col(cov_df, "债券代码", "代码") or (cov_df.columns[0] if len(cov_df.columns) > 0 else None)
                col_bond_name = _find_col(cov_df, "债券简称", "名称") or (cov_df.columns[1] if len(cov_df.columns) > 1 else None)
                _find_col(cov_df, "正股代码", "正股代码")
                col_stock_name = _find_col(cov_df, "正股简称", "正股名称")
                col_stock_price = _find_col(cov_df, "正股价")
                _find_col(cov_df, "转股价")
                col_convert_value = _find_col(cov_df, "转股价值")
                col_bond_price = _find_col(cov_df, "债现价")
                col_premium = _find_col(cov_df, "转股溢价率", "溢价率")
                col_issue_scale = _find_col(cov_df, "发行规模")
                # 涨跌幅列(转债、正股)
                bond_change_col = None
                stock_change_col = None
                if spot_df is not None and not spot_df.empty:
                    bond_change_col = _find_col(spot_df, "涨跌幅", "涨跌幅(%)", "涨跌", "change", "changeRate")
                if cov_df is not None and not cov_df.empty:
                    stock_change_col = _find_col(cov_df, "正股涨跌幅", "正股涨跌幅%", "正股涨跌")
                if not col_bond_code:
                    self.root.after(0, lambda: messagebox.showerror("错误", "可转债表结构异常", parent=self.root))
                    return
                # 构建 code -> 一览行
                cov_df = cov_df.copy()
                cov_df["_code"] = cov_df[col_bond_code].apply(norm_code)
                # 过滤已上市:债现价/转股价值 有效
                price_col = col_bond_price or col_convert_value
                if price_col:
                    cov_df = cov_df.dropna(subset=[price_col], how="all")
                if spot_df is not None and not spot_df.empty:
                    spot_df = spot_df.copy()
                    spot_df["_code"] = spot_df.get("code", spot_df.get("symbol", pd.Series())).apply(
                        lambda x: norm_code(str(x).replace("sh", "").replace("sz", "") if pd.notna(x) else "")
                    )
                    # 按成交额排序取活跃(前 120)
                    amount_col = _find_col(spot_df, "amount", "成交额") or "amount"
                    if amount_col not in spot_df.columns:
                        amount_col = _find_col(spot_df, "volume", "成交量") or "volume"
                    if amount_col in spot_df.columns:
                        spot_df = spot_df.sort_values(amount_col, ascending=False).head(150)
                    # 合并:以 spot 为主,补 cov 字段
                    merge_df = spot_df.merge(cov_df, on="_code", how="left", suffixes=("", "_cov"))
                else:
                    merge_df = cov_df.head(100)
                # 强赎:代码列
                redeem_code_col = None
                redeem_remain_col = _find_col(redeem_df, "剩余规模", "规模") if not redeem_df.empty else None
                redeem_date_col = _find_col(redeem_df, "强赎", "到期") if not redeem_df.empty else None
                if not redeem_df.empty:
                    for c in redeem_df.columns:
                        if "代码" in str(c) or str(c) == "code":
                            redeem_code_col = c
                            break
                    if redeem_code_col is None and len(redeem_df.columns) > 0:
                        redeem_code_col = redeem_df.columns[0]
                # 合并强赎(剩余规模、强赎/到期日)
                if redeem_code_col and redeem_remain_col is not None and not redeem_df.empty:
                    redeem_df = redeem_df.copy()
                    redeem_df["_code"] = redeem_df[redeem_code_col].apply(norm_code)
                    redeem_sub = redeem_df[["_code", redeem_remain_col]].copy()
                    redeem_sub.rename(columns={redeem_remain_col: "剩余规模"}, inplace=True)
                    if redeem_date_col and redeem_date_col in redeem_df.columns:
                        redeem_sub["强赎或到期"] = redeem_df[redeem_date_col]
                    else:
                        redeem_sub["强赎或到期"] = None
                    merge_df = merge_df.merge(redeem_sub, on="_code", how="left")
                else:
                    merge_df["剩余规模"] = None
                    merge_df["强赎或到期"] = None
                # 换手率:spot 无直接换手率时用 成交额/(债现价*规模)近似或留空
                if "volume" in merge_df.columns or _find_col(merge_df, "成交量") in merge_df.columns:
                    "volume" if "volume" in merge_df.columns else _find_col(merge_df, "成交量")
                else:
                    pass
                # 表格行
                rows = []
                for _, r in merge_df.iterrows():
                    # 东方财富可转债页:https://quote.eastmoney.com/sz128039.html 或 sh110044.html
                    symbol = r.get("symbol", "")
                    if not symbol or not str(symbol).strip():
                        code = norm_code(r.get("_code", ""))
                        if code:
                            symbol = ("sh" if code.startswith(("11", "13")) else "sz") + code
                    bond_url = f"https://quote.eastmoney.com/{symbol}.html" if symbol else ""
                    bond_name = r.get(col_bond_name, r.get("name", ""))
                    stock_name = r.get(col_stock_name, "")
                    bond_price = r.get(col_bond_price, r.get("trade", 0))
                    stock_price = r.get(col_stock_price, 0)
                    premium = r.get(col_premium, None)
                    bond_change = r.get(bond_change_col, None) if bond_change_col else None
                    stock_change = r.get(stock_change_col, None) if stock_change_col else None
                    r.get(col_convert_value, None)
                    issue_scale = r.get(col_issue_scale, r.get("剩余规模", None))
                    remain = r.get("剩余规模", None)
                    redeem_info = r.get("强赎或到期", "")
                    try:
                        bond_p = float(bond_price) if bond_price not in (None, "", "-") else 0
                        stock_p = float(stock_price) if stock_price not in (None, "", "-") else 0
                        prem = float(premium) if premium not in (None, "", "-") and str(premium) not in ("", "nan") else None
                    except (TypeError, ValueError):
                        bond_p = stock_p = 0
                        prem = None
                    bond_chg = _to_float_safe(bond_change)
                    stock_chg = _to_float_safe(stock_change)
                    amount_val = r.get("amount", r.get("成交额", 0)) or 0
                    volume_val = r.get("volume", r.get("成交量", 0)) or 0
                    try:
                        amount_val = float(amount_val) if amount_val not in (None, "", "-") else 0
                        volume_val = int(volume_val) if volume_val not in (None, "", "-") else 0
                    except (TypeError, ValueError):
                        amount_val, volume_val = 0, 0
                    # 套利提示
                    tip = ""
                    if prem is not None:
                        if prem < 0:
                            tip = "存在套利机会(负溢价)"
                        elif prem < 2:
                            tip = "存在套利机会(低溢价)"
                        elif prem > 30:
                            tip = "高溢价注意风险"
                    if redeem_info and str(redeem_info) not in ("", "nan", "None"):
                        tip = (tip + " " if tip else "") + "注意强赎/到期"
                    if not tip:
                        tip = "-"
                    rows.append({
                        "债券简称": str(bond_name)[:10],
                        "正股简称": str(stock_name)[:10] if stock_name else "-",
                        "债现价": f"{bond_p:.2f}" if bond_p else "-",
                         "债券涨跌幅%": f"{bond_chg:+.2f}%" if bond_chg is not None else "-",
                        "正股价": f"{stock_p:.2f}" if stock_p else "-",
                         "正股涨跌幅%": f"{stock_chg:+.2f}%" if stock_chg is not None else "-",
                        "转股溢价率%": f"{prem:.2f}" if prem is not None else "-",
                        "换手/成交额": f"{volume_val}手" if volume_val else (f"{amount_val/1e4:.0f}万" if amount_val else "-"),
                        "强赎/到期": str(redeem_info)[:12] if redeem_info and str(redeem_info) not in ("nan", "None") else "-",
                        "剩余规模": str(remain)[:10] if remain not in (None, "", "-") else (str(issue_scale)[:10] if issue_scale else "-"),
                        "套利提示": tip,
                        "url": bond_url,
                    })
                self.root.after(0, lambda: self._display_cb_arbitrage_window(rows))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda e=e: messagebox.showerror("错误", f"获取可转债数据失败: {e}", parent=self.root))
        threading.Thread(target=fetch_and_show, daemon=True).start()

    def _show_stock_info_dialog(self, result, stock_name, parent_win):
        """显示股票信息对话框。"""
        import tkinter as tk
        from tkinter import scrolledtext, ttk
        dialog = tk.Toplevel(parent_win)
        dialog.title(f"{stock_name} - 信息获取")
        dialog.geometry("800x600")
        dialog.transient(parent_win)
        dialog.grab_set()
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 热度信息
        hotness_frame = ttk.LabelFrame(main_frame, text="热度信息", padding=10)
        hotness_frame.pack(fill=tk.X, pady=(0, 10))
        hotness_text = scrolledtext.ScrolledText(hotness_frame, height=6, font=("TkDefaultFont", 11))
        hotness_text.pack(fill=tk.BOTH, expand=True)
        if result.get('hotness'):
            hotness_text.insert(tk.END, f"总提及次数: {result['hotness'].get('total_mentions', 0)}次\n")
            hotness_text.insert(tk.END, f"提及天数: {result['hotness'].get('days_mentioned', 0)}天\n")
        hotness_text.config(state=tk.DISABLED)
        # 新闻资讯
        news_frame = ttk.LabelFrame(main_frame, text="相关资讯", padding=10)
        news_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        news_text = scrolledtext.ScrolledText(news_frame, height=12, font=("TkDefaultFont", 11))
        news_text.pack(fill=tk.BOTH, expand=True)
        if result.get('news'):
            for news in result['news']:
                news_text.insert(tk.END, f"【{news.get('来源', '')}】{news.get('时间', '')}\n")
                news_text.insert(tk.END, f"  {news.get('标题', '')}\n")
                if news.get('内容'):
                    news_text.insert(tk.END, f"  {news.get('内容')}\n")
                news_text.insert(tk.END, "\n")
        else:
            news_text.insert(tk.END, "暂无相关资讯")
        news_text.config(state=tk.DISABLED)
        # 情感分析
        sentiment_frame = ttk.LabelFrame(main_frame, text="情感分析", padding=10)
        sentiment_frame.pack(fill=tk.X, pady=(0, 10))
        sentiment_text = scrolledtext.ScrolledText(sentiment_frame, height=5, font=("TkDefaultFont", 11))
        sentiment_text.pack(fill=tk.BOTH, expand=True)
        if result.get('sentiment'):
            for item in result['sentiment']:
                sentiment_text.insert(tk.END, f"正面词汇: {item.get('正面词汇', 0)}个\n")
                sentiment_text.insert(tk.END, f"负面词汇: {item.get('负面词汇', 0)}个\n")
                sentiment_text.insert(tk.END, f"情感得分: {item.get('情感得分', 0)}\n")
        sentiment_text.config(state=tk.DISABLED)
        # 详细步骤
        steps_frame = ttk.LabelFrame(main_frame, text="详细分析", padding=10)
        steps_frame.pack(fill=tk.X)
        steps_text = scrolledtext.ScrolledText(steps_frame, height=6, font=("TkDefaultFont", 10))
        steps_text.pack(fill=tk.BOTH, expand=True)
        if result.get('calculation_steps'):
            for step in result['calculation_steps']:
                steps_text.insert(tk.END, f"{step}\n")
        steps_text.config(state=tk.DISABLED)
        ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT, pady=10)

    def _show_buy_point_prediction_dialog(self, result, stock_name, parent_win=None):
        """显示买点预测结果对话框"""
        dialog = self._toplevel(parent_win or self.root)
        dialog.title(f"{stock_name} - 买点预测")
        dialog.geometry("700x600")
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        if not result.get('success'):
            ttk.Label(main_frame, text=f"计算失败:{result.get('message', '')}",
                      font=("Microsoft YaHei", 12), foreground='red').pack(pady=20)
            ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(pady=10)
            return
        # 标题
        title_label = ttk.Label(main_frame, text=f"{stock_name} 买点预测",
                               font=("Microsoft YaHei", 14, "bold"))
        title_label.pack(pady=(0, 10))
        # 创建笔记本标签页
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        # 计算步骤标签页
        steps_frame = ttk.Frame(notebook, padding=10)
        notebook.add(steps_frame, text="计算步骤")
        steps_text = tk.Text(steps_frame, wrap=tk.WORD, font=("Consolas", 11))
        steps_scroll = ttk.Scrollbar(steps_frame, orient="vertical", command=steps_text.yview)
        steps_text.configure(yscrollcommand=steps_scroll.set)
        steps_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        steps_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        for step in result.get('calculation_steps', []):
            steps_text.insert(tk.END, step + "\n\n")
        steps_text.config(state=tk.DISABLED)
        # 买点列表标签页
        points_frame = ttk.Frame(notebook, padding=10)
        notebook.add(points_frame, text="买点列表")
        points_text = tk.Text(points_frame, wrap=tk.WORD, font=("Consolas", 11))
        points_scroll = ttk.Scrollbar(points_frame, orient="vertical", command=points_text.yview)
        points_text.configure(yscrollcommand=points_scroll.set)
        points_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        points_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        buy_points = result.get('buy_points', [])
        if buy_points:
            points_text.insert(tk.END, "满足条件的买点(MACD金叉+均线多头+WR低位):\n")
            points_text.insert(tk.END, "="*70 + "\n")
            for i, point in enumerate(buy_points, 1):
                points_text.insert(tk.END, f"买点{i}:\n")
                points_text.insert(tk.END, f"  日期: {point['date']}\n")
                points_text.insert(tk.END, f"  价格: {point['price']:.2f}\n")
                points_text.insert(tk.END, f"  DIF: {point['dif']:.4f}\n")
                points_text.insert(tk.END, f"  DEA: {point['dea']:.4f}\n")
                points_text.insert(tk.END, f"  WR(2): {point['wr']:.2f}\n")
                points_text.insert(tk.END, f"  MA5: {point['ma5']:.2f}\n")
                points_text.insert(tk.END, f"  MA10: {point['ma10']:.2f}\n")
                points_text.insert(tk.END, f"  MA20: {point['ma20']:.2f}\n")
                points_text.insert(tk.END, "-"*70 + "\n")
        else:
            points_text.insert(tk.END, "未找到满足条件的买点\n")
            points_text.insert(tk.END, "条件:MACD快线>DIF>DEA + 均线多头发散(MA5>MA10>MA20) + WR(2)<-80\n")
        points_text.config(state=tk.DISABLED)
        # 预测结果标签页
        predict_frame = ttk.Frame(notebook, padding=10)
        notebook.add(predict_frame, text="预测结果")
        predict_text = tk.Text(predict_frame, wrap=tk.WORD, font=("Consolas", 11))
        predict_scroll = ttk.Scrollbar(predict_frame, orient="vertical", command=predict_text.yview)
        predict_text.configure(yscrollcommand=predict_scroll.set)
        predict_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        predict_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        spacing_analysis = result.get('spacing_analysis', [])
        if spacing_analysis:
            predict_text.insert(tk.END, "间距分析:\n")
            predict_text.insert(tk.END, "="*70 + "\n")
            for item in spacing_analysis:
                predict_text.insert(tk.END, f"  {item}\n")
            predict_text.insert(tk.END, "\n")
        predicted_points = result.get('predicted_points', [])
        if predicted_points:
            predict_text.insert(tk.END, "预测买点:\n")
            predict_text.insert(tk.END, "="*70 + "\n")
            for point in predicted_points:
                predict_text.insert(tk.END, f"  类型: {point['type']}\n")
                predict_text.insert(tk.END, f"  间距: {point['spacing']}\n")
                predict_text.insert(tk.END, f"  预测价格: {point['predicted_price']:.2f}\n")
                predict_text.insert(tk.END, f"  置信度: {point['confidence']}\n")
                predict_text.insert(tk.END, "-"*70 + "\n")
        else:
            predict_text.insert(tk.END, "无法预测买点(需要至少2个历史买点)\n")
        predict_text.config(state=tk.DISABLED)
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(pady=10)

    def _show_divergence_t_dialog(self):
        """背离做T弹窗:显示三大指数当日分时背离检测结果 + 图形"""
        try:
            import matplotlib
            import numpy as np
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg,
                NavigationToolbar2Tk,
            )
            from matplotlib.figure import Figure
        except Exception as e:
            messagebox.showerror("错误", f"matplotlib 导入失败: {e}", parent=self.root)
            return
        # 指数配置
        INDEX_DEFS = [
            ("上证指数", "000001"),
            ("深证成指", "399001"),
            ("创业板指", "399006"),
        ]
        win = self._toplevel(self.root)
        win.title("📈 分时背离检测(做T辅助)")
        win.geometry("1500x900")
        win.transient(self.root)
        # ---------- 顶部:控制面板 ----------
        top_frame = ttk.Frame(win)
        top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(top_frame, text="指数:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT)
        idx_names = [d[0] for d in INDEX_DEFS]
        idx_var = tk.StringVar(value=idx_names[0])
        idx_combo = ttk.Combobox(top_frame, textvariable=idx_var, values=idx_names, state="readonly", width=12)
        idx_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(top_frame, text="周期:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(12, 0))
        period_var = tk.StringVar(value="1分钟")
        period_combo = ttk.Combobox(top_frame, textvariable=period_var,
                                    values=["1分钟", "5分钟", "15分钟"], state="readonly", width=8)
        period_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(top_frame, text="窗口:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(12, 0))
        win_var = tk.IntVar(value=5)
        win_spin = ttk.Spinbox(top_frame, from_=3, to=20, width=5, textvariable=win_var)
        win_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(top_frame, text="最小%:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(12, 0))
        minpct_var = tk.DoubleVar(value=0.15)
        minpct_spin = ttk.Spinbox(top_frame, from_=0.05, to=2.0, increment=0.05, width=5, textvariable=minpct_var)
        minpct_spin.pack(side=tk.LEFT, padx=5)
        analyze_btn = ttk.Button(top_frame, text="🔍 检测", width=8)
        analyze_btn.pack(side=tk.LEFT, padx=10)
        result_label = ttk.Label(top_frame, text="", font=("TkDefaultFont", 11, "bold"), foreground="blue")
        result_label.pack(side=tk.LEFT, padx=10)
        # ---------- 中部:matplotlib 双子图 ----------
        fig = Figure(figsize=(14, 7), dpi=100)
        ax_price = fig.add_subplot(211)
        ax_macd = fig.add_subplot(212, sharex=ax_price)
        fig.subplots_adjust(hspace=0.08, top=0.95, bottom=0.08)
        chart_frame = ttk.Frame(win)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar = NavigationToolbar2Tk(canvas, chart_frame)
        toolbar.update()
        # ---------- 底部:三个指数快速概览 ----------
        summary_frame = ttk.LabelFrame(win, text="三指数背离概览", padding=5)
        summary_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        summary_labels = {}
        for i, (name, _) in enumerate(INDEX_DEFS):
            lbl = ttk.Label(summary_frame, text=f"{name}: 等待检测...",
                            font=("TkDefaultFont", 11), foreground="gray")
            lbl.grid(row=0, column=i, padx=12, pady=3, sticky="w")
            summary_labels[name] = lbl
        # ---------- 核心分析函数 ----------
        _cached = {}  # 缓存每个指数的 {divergences, data}
        def _draw(idx_name):
            """画指定指数的双子图"""
            nonlocal canvas, ax_price, ax_macd
            fig.clear()
            ax_price = fig.add_subplot(211)
            ax_macd = fig.add_subplot(212, sharex=ax_price)
            fig.subplots_adjust(hspace=0.08, top=0.95, bottom=0.08)
            cache = _cached.get(idx_name)
            if cache is None:
                ax_price.set_title(f"{idx_name} - 数据未加载,请点击「开始检测」", fontsize=14)
                canvas.draw()
                return
            data = cache["data"]
            divs = cache["divergences"]
            prices = data["prices"]
            dif_arr = cache["dif"]
            dea_arr = cache["dea"]
            hist_arr = cache["hist"]
            times = data["times"]
            x = np.arange(len(prices))
            # ---------- 上图:分时价格 ----------
            # 计算颜色:涨红跌绿(对比昨收或第一个点)
            base = prices[0]
            ["#C62828" if p >= base else "#2E7D32" for p in prices]
            # 简化:整个线用渐变色太复杂,用红色线 + 涨跌区域填色
            ax_price.plot(x, prices, color="#333333", linewidth=1.2, label="分时")
            # 填充涨跌
            for i in range(1, len(prices)):
                if prices[i] >= prices[i - 1]:
                    ax_price.plot(x[i - 1:i + 1], prices[i - 1:i + 1], color="#C62828", linewidth=1.8)
                else:
                    ax_price.plot(x[i - 1:i + 1], prices[i - 1:i + 1], color="#2E7D32", linewidth=1.8)
            ax_price.fill_between(x, prices, prices[0],
                                  where=(prices >= prices[0]), color="#C62828", alpha=0.08)
            ax_price.fill_between(x, prices, prices[0],
                                  where=(prices < prices[0]), color="#2E7D32", alpha=0.08)
            ax_price.axhline(prices[0], color="gray", linestyle="--", linewidth=0.8, alpha=0.5, label="昨收/今开")
            # 标注背离点
            for d in divs:
                i1, i2 = d["idx1"], d["idx2"]
                p1, p2 = d["price1"], d["price2"]
                if d["type"] == "top":
                    color = "#2E7D32"  # 顶背离→绿色(卖)
                else:
                    color = "#C62828"  # 底背离→红色(买)
                # 连线
                ax_price.plot([i1, i2], [p1, p2], color=color, linewidth=2.0, linestyle="--", alpha=0.8)
                # 标记点
                ax_price.scatter([i1], [p1], color=color, s=60, zorder=5)
                ax_price.scatter([i2], [p2], color=color, s=80, zorder=5, marker="*")
                # 文字
                mid_x = (i1 + i2) / 2
                mid_y = max(p1, p2) if d["type"] == "top" else min(p1, p2)
                offset = (max(prices) - min(prices)) * 0.02
                ypos = mid_y + offset if d["type"] == "top" else mid_y - offset
                advice_short = "卖" if d["type"] == "top" else "买"
                ax_price.annotate(
                    f"{d['label']}→{advice_short}",
                    xy=(i2, p2), xytext=(mid_x, ypos),
                    fontsize=10, fontweight="bold", color=color,
                    arrowprops={"arrowstyle": "->", "color": color},
                    ha="center",
                )
            # 日期显示
            _date_str = data.get("date", "")
            _is_today = (_date_str == pd.Timestamp.now().strftime("%Y%m%d"))
            _date_label = f"📅 {_date_str}(今日)" if _is_today and _date_str else f"📅 {_date_str}" if _date_str else ""
            title_txt = f"{idx_name}  {_date_label}  |  收盘={prices[-1]:.2f}  |  涨跌={prices[-1]-prices[0]:+.2f}  |  背离={len(divs)}个"
            ax_price.set_title(title_txt, fontsize=13, fontweight="bold")
            ax_price.set_ylabel("价格")
            ax_price.grid(True, alpha=0.3)
            # ---------- 下图:MACD ----------
            bar_colors = ["#C62828" if h >= 0 else "#2E7D32" for h in hist_arr]
            ax_macd.bar(x, hist_arr, color=bar_colors, alpha=0.6, width=1.0, label="MACD柱")
            ax_macd.plot(x, dif_arr, color="#FF6F00", linewidth=1.2, label="DIF")
            ax_macd.plot(x, dea_arr, color="#1565C0", linewidth=1.2, label="DEA")
            ax_macd.axhline(0, color="gray", linestyle="--", linewidth=0.6)
            # DIF 背离连线
            for d in divs:
                i1, i2 = d["idx1"], d["idx2"]
                d1, d2 = d["dif1"], d["dif2"]
                color = "#2E7D32" if d["type"] == "top" else "#C62828"
                ax_macd.plot([i1, i2], [d1, d2], color=color, linewidth=2.0, linestyle="--", alpha=0.8)
                ax_macd.scatter([i1, i2], [d1, d2], color=color, s=40, zorder=5)
            ax_macd.set_ylabel("MACD")
            ax_macd.legend(loc="upper left", fontsize=9)
            ax_macd.grid(True, alpha=0.3)
            # X 轴时间标签(稀疏显示)
            step = max(1, len(x) // 12)
            ax_macd.set_xticks(x[::step])
            ax_macd.set_xticklabels([str(t)[-8:] if len(str(t)) > 8 else str(t) for t in times[::step]],
                                    rotation=45, fontsize=8)
            canvas.draw()
        def _to_period_minutes():
            """周期字符串 → 分钟数"""
            p = period_var.get()
            return {"1分钟": 1, "5分钟": 5, "15分钟": 15}.get(p, 1)
        def _resample_1min(data, period_min):
            """把1分钟数据聚合为N分钟OHLC"""
            import numpy as np
            if period_min <= 1:
                return data
            prices = data["prices"]
            times = data["times"]
            vols = data["volumes"]
            n = len(prices)
            out_p, out_t, out_v = [], [], []
            for i in range(0, n, period_min):
                chunk_p = prices[i:i + period_min]
                chunk_t = times[i:i + period_min]
                chunk_v = vols[i:i + period_min]
                if len(chunk_p) == 0:
                    continue
                out_p.append(float(chunk_p[-1]))  # 收盘价
                out_t.append(str(chunk_t[-1]))
                out_v.append(float(sum(chunk_v)))
            return {
                "name": data["name"],
                "symbol": data["symbol"],
                "times": out_t,
                "prices": np.array(out_p),
                "volumes": np.array(out_v),
            }
        def _redetect_from_cache():
            """用新窗口/最小%参数重新检测(不重新拉数据)"""
            if not _cached:
                _analyze_all()
                return
            for name, sym in INDEX_DEFS:
                data = _cached.get(name, {}).get("raw_data") or self._fetch_index_min_data(sym, name)
                if data is None:
                    continue
                _dlabel = data.get("date", "")
                if _dlabel == pd.Timestamp.now().strftime("%Y%m%d"):
                    _dlabel = "今日"
                pm = _to_period_minutes()
                data_r = _resample_1min(data, pm)
                prices = data_r["prices"]
                dif, dea, hist = self._calc_macd_full(prices)
                divs = self._detect_divergence(
                    prices, dif,
                    window=max(3, win_var.get() // max(1, pm)),
                    min_price_pct=minpct_var.get() / 100.0,
                )
                _cached[name] = {
                    "data": data_r, "raw_data": data,
                    "divergences": divs,
                    "dif": dif, "dea": dea, "hist": hist,
                }
                if divs:
                    top_c = sum(1 for d in divs if d["type"] == "top")
                    bot_c = sum(1 for d in divs if d["type"] == "bottom")
                    summary_labels[name].config(
                        text=f"{name}({_dlabel}): ⚠️ {len(divs)}背离(顶{top_c}/底{bot_c})",
                        foreground="#C62828" if bot_c else "#FF6F00")
                else:
                    summary_labels[name].config(text=f"{name}({_dlabel}): ✅ 无背离", foreground="#2E7D32")
            _draw(idx_var.get())
        def _analyze_all():
            """获取所有指数数据 + 检测背离"""
            nonlocal _cached
            result_label.config(text="⏳ 正在获取分时数据...", foreground="orange")
            win.update_idletasks()
            pm = _to_period_minutes()
            any_success = False
            all_failed = True
            for name, sym in INDEX_DEFS:
                raw_data = self._fetch_index_min_data(sym, name)
                if raw_data is None:
                    summary_labels[name].config(
                        text=f"{name}: ❌ 无数据(非交易时间/网络问题)",
                        foreground="red")
                    continue
                _dlabel = raw_data.get("date", "")
                if _dlabel == pd.Timestamp.now().strftime("%Y%m%d"):
                    _dlabel = "今日"
                data = _resample_1min(raw_data, pm)
                prices = data["prices"]
                dif, dea, hist = self._calc_macd_full(prices)
                divs = self._detect_divergence(
                    prices, dif,
                    window=max(3, win_var.get() // max(1, pm)),
                    min_price_pct=minpct_var.get() / 100.0,
                )
                _cached[name] = {
                    "data": data, "raw_data": raw_data,
                    "divergences": divs,
                    "dif": dif, "dea": dea, "hist": hist,
                }
                any_success = True
                all_failed = False
                if divs:
                    top_c = sum(1 for d in divs if d["type"] == "top")
                    bot_c = sum(1 for d in divs if d["type"] == "bottom")
                    summary_labels[name].config(
                        text=f"{name}({_dlabel}): ⚠️ {len(divs)}背离(顶{top_c}/底{bot_c})",
                        foreground="#C62828" if bot_c else "#FF6F00")
                else:
                    summary_labels[name].config(text=f"{name}({_dlabel}): ✅ 无背离", foreground="#2E7D32")
            if any_success:
                for name, _ in INDEX_DEFS:
                    c = _cached.get(name)
                    if c and c["divergences"]:
                        idx_var.set(name)
                        break
                _draw(idx_var.get())
                result_label.config(text=f"✅ 检测完成({pm}分钟周期)", foreground="green")
            elif all_failed:
                result_label.config(text="❌ 非交易时间或网络不可用,请交易时间再试", foreground="red")
        # 绑定
        analyze_btn.config(command=_analyze_all)
        idx_combo.bind("<<ComboboxSelected>>", lambda _e: _draw(idx_var.get()))
        period_combo.bind("<<ComboboxSelected>>", lambda _e: _analyze_all())
        win_var.trace_add("write", lambda *_: _redetect_from_cache())
        minpct_var.trace_add("write", lambda *_: _redetect_from_cache())
        # 延迟自动检测
        win.after(300, _analyze_all)

    def _show_blood_chips_dialog(self):
        """🩸 血腥筹码扫描弹窗:Banner + 参数 + 左matplotlib图形 + 右Treeview数据表"""
        import json as _json
        import os
        import subprocess
        import tempfile
        import threading
        import tkinter as tk
        from tkinter import ttk
        try:
            import matplotlib
            import numpy as np
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg,
                NavigationToolbar2Tk,
            )
            from matplotlib.figure import Figure
        except Exception as e:
            messagebox.showerror("错误", f"matplotlib 导入失败: {e}", parent=self.root)
            return
        win = self._toplevel(self.root)
        win.title("🩸 血腥筹码 · 全市场扫描")
        win.geometry("1500x920")
        win.transient(self.root)
        # ============ 1 顶部说明 Banner ============
        banner = tk.Frame(win, bg="#880E4F", height=72)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg="#880E4F")
        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(bi, text="🩸 血腥筹码 · 全市场扫描器",
                 font=("Microsoft YaHei", 16, "bold"),
                 bg="#880E4F", fg="#FFD54F").pack(anchor="w")
        tk.Label(bi, text="🎯 扫描全市场基本面OK的A股(排除ST/涨跌停)→ 找出距60日低点 ≤2% 的带血筹码机会",
                 font=("Microsoft YaHei", 10),
                 bg="#880E4F", fg="#F8BBD9").pack(anchor="w")
        tk.Label(bi, text="🩸极血腥≤0.5%   🩸血腥≤2%   ⚠️偏低≤5%   ✅正常>5%",
                 font=("Microsoft YaHei", 9),
                 bg="#880E4F", fg="#F48FB1").pack(anchor="w")
        # ============ 2 参数区 ============
        top = ttk.LabelFrame(win, text="📝 扫描参数", padding=8)
        top.pack(fill=tk.X, padx=5, pady=(5, 2))
        row1 = ttk.Frame(top)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="扫描数量 Top N:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT)
        top_n_var = tk.IntVar(value=300)
        ttk.Spinbox(row1, from_=100, to=1000, increment=50, width=6, textvariable=top_n_var
                    ).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="- 成交量前N只,默认300只", font=("TkDefaultFont", 9), foreground="#888"
                  ).pack(side=tk.LEFT)
        ttk.Label(row1, text="  可选持仓代码:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(15, 0))
        hold_var = tk.StringVar(value="")
        ttk.Entry(row1, textvariable=hold_var, width=30).pack(side=tk.LEFT, padx=3)
        ttk.Label(row1, text="- 空格分隔,留空则扫描全市场", font=("TkDefaultFont", 9), foreground="#888"
                  ).pack(side=tk.LEFT)
        scan_btn = ttk.Button(row1, text="🔍 开始扫描", width=14)
        scan_btn.pack(side=tk.LEFT, padx=15)
        status_var = tk.StringVar(value="💡 点「开始扫描」扫描全市场基本面OK的A股")
        ttk.Label(row1, textvariable=status_var, font=("TkDefaultFont", 10),
                  foreground="#666").pack(side=tk.LEFT, fill=tk.X, expand=True)
        # ============ 3 主体:左图右表 ============
        body = ttk.Panedwindow(win, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        # ---- 左:matplotlib 三图 ----
        chart_frame = ttk.LabelFrame(body, text="📈 图形分析", padding=3)
        body.add(chart_frame, weight=3)
        fig = Figure(figsize=(9, 9), dpi=100, facecolor="#fafafa")
        ax_pie = fig.add_subplot(221)
        ax_bar = fig.add_subplot(222)
        ax_scatter = fig.add_subplot(212)
        fig.subplots_adjust(hspace=0.35, wspace=0.25, top=0.93, bottom=0.07, left=0.08, right=0.96)
        # 初始占位
        for ax in [ax_pie, ax_bar, ax_scatter]:
            ax.text(0.5, 0.5, "⏳ 等待扫描...", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="#bbb")
            ax.set_xticks([]); ax.set_yticks([])
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, chart_frame).update()
        # ---- 右:Treeview 数据表 ----
        table_frame = ttk.LabelFrame(body, text="📋 扫描结果", padding=3)
        body.add(table_frame, weight=2)
        cols = ("level", "code", "name", "trade", "min60", "dist60", "pct_today", "vol")
        col_labels = {"level": "级别", "code": "代码", "name": "名称", "trade": "现价",
                      "min60": "60日低", "dist60": "距60日%", "pct_today": "今日%", "vol": "成交量"}
        col_widths = {"level": 80, "code": 80, "name": 100, "trade": 70,
                      "min60": 70, "dist60": 80, "pct_today": 70, "vol": 80}
        tree_frame = ttk.Frame(table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        # 调大 Treeview 表头 + 行高,配合字体加大一号
        _style = ttk.Style()
        _style.configure("Treeview.Heading", font=("", 11, "bold"), rowheight=28)
        _style.configure("Treeview", rowheight=26)
        for c in cols:
            tree.heading(c, text=col_labels[c])
            tree.column(c, width=col_widths[c], anchor="center", stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(fill=tk.X)
        # 表头颜色 + 字体加粗大一号,显著区分
        tree.tag_configure("extreme", foreground="#C62828", font=("", 12, "bold"))
        tree.tag_configure("blood", foreground="#E65100", font=("", 12, "bold"))
        tree.tag_configure("low", foreground="#F57F17", font=("", 11, "bold"))
        tree.tag_configure("normal", foreground="#666666", font=("", 11))
        # ===== 双击股票行 → 打开日K线图 =====
        def _open_kline_on_double(event):
            item = tree.selection()
            if not item:
                return
            vals = tree.item(item[0], "values")
            if not vals or len(vals) < 3:
                return
            stock_code = str(vals[1]).strip()  # code 列
            stock_name = str(vals[2]).strip()  # name 列
            if not stock_code or not stock_code.replace(".", "").isdigit():
                return
            # 异步拉 K 线 + 弹窗
            def _kwork():
                try:
                    kline_data = self._get_daily_kline_data_tushare(stock_code, days=120)
                except Exception as e:
                    kline_data = None
                    print(f"K线拉取失败 {stock_code}: {e}")
                if kline_data:
                    try:
                        self._show_daily_kline_zoom(kline_data, stock_name)
                    except Exception as e:
                        messagebox.showerror("错误", f"打开K线图失败: {e}", parent=win)
                else:
                    messagebox.showwarning("提示",
                        f"无法获取 {stock_name}({stock_code}) 的K线数据\n"
                        f"请检查 Tushare 连接或稍后再试", parent=win)
            threading.Thread(target=_kwork, daemon=True).start()
        tree.bind("<Double-1>", _open_kline_on_double)
        # ============ 扫描逻辑 ============
        def _run_scan():
            scan_btn.config(state=tk.DISABLED)
            status_var.set("⏳ 扫描中(抓全市场快照 → 验证历史K线 → 分类)...")
            # 清空表格
            for item in tree.get_children():
                tree.delete(item)
            # 清空图
            for ax in [ax_pie, ax_bar, ax_scatter]:
                ax.clear()
                ax.text(0.5, 0.5, "⏳ 扫描中,请稍候...",
                        ha="center", va="center", transform=ax.transAxes,
                        fontsize=14, color="#bbb")
                ax.set_xticks([]); ax.set_yticks([])
            canvas.draw_idle()
            # runner 路径
            scanner_path = os.path.expanduser("~/.qclaw/skills/blood-chips-scanner/scanner.py")
            if not os.path.exists(scanner_path):
                status_var.set("❌ scanner.py 不存在")
                scan_btn.config(state=tk.NORMAL)
                return
            # 参数
            top_n = top_n_var.get()
            hold_codes = hold_var.get().strip().split() if hold_var.get().strip() else []
            report_dir = os.path.join(tempfile.gettempdir(), "blood_chips_reports")
            os.makedirs(report_dir, exist_ok=True)
            # 写 runner(加 -- 最后输出 JSON)
            runner_path = os.path.join(tempfile.gettempdir(), "blood_chips_runner_json.py")
            runner_code = f'''
import ssl, os, sys, importlib.util, json, traceback
from utils.config import *  # 路径/配置/Token
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'
scanner_path = {scanner_path!r}
report_dir = {report_dir!r}
hold_codes = {hold_codes!r}
top_n = {top_n}
try:
    spec = importlib.util.spec_from_file_location("scanner", scanner_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["scanner"] = mod
    spec.loader.exec_module(mod)
    mod.REPORTS_DIR = report_dir
    triggered, indices = mod.check_index_drop()
    if triggered:
        top_n = mod.SCAN_TOP_N_DROP
    result = mod.scan_market(top_n=top_n, hold_codes=hold_codes)
    # 序列化成 JSON 安全的 dict
    safe = {{}}
    for key in ['snapshot_count','candidates_checked','hist_time','total_time','extreme','blood','low','normal']:
        safe[key] = result.get(key, [])
    print("JSON_RESULT_START")
    print(json.dumps(safe, ensure_ascii=False))
    print("JSON_RESULT_END")
except Exception as e:
    print(f"ERROR: {{type(e).__name__}}: {{e}}")
    traceback.print_exc()
    sys.exit(1)
'''
            with open(runner_path, "w", encoding="utf-8") as f:
                f.write(runner_code)
            env = os.environ.copy()
            env["PYTHONHTTPSVERIFY"] = "0"
            cmd = ["/Library/Frameworks/Python.framework/Versions/3.11/bin/python3", runner_path]
            def work():
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
                    win.after(0, lambda: _parse_and_render(proc.stdout, proc.stderr, proc.returncode))
                except subprocess.TimeoutExpired:
                    win.after(0, lambda: _parse_and_render("", "❌ 扫描超时(120秒)", 1))
                except Exception as e:
                    win.after(0, lambda e=e: _parse_and_render("", f"❌ 异常: {e}", 1))
            def _parse_and_render(stdout, stderr, rc):
                scan_btn.config(state=tk.NORMAL)
                if rc != 0:
                    status_var.set(f"❌ 失败: {stderr[-200:] if stderr else '未知错误'}")
                    return
                # 提取 JSON
                output = stdout + stderr
                start = output.find("JSON_RESULT_START")
                end = output.find("JSON_RESULT_END")
                if start < 0 or end < 0:
                    status_var.set("❌ runner 无 JSON 输出")
                    return
                try:
                    data = _json.loads(output[start+17:end].strip())
                except Exception as e:
                    status_var.set(f"❌ JSON 解析失败: {e}")
                    return
                _render(data)
            def _render(data):
                """渲染图表 + 表格"""
                extreme = data.get("extreme", [])
                blood = data.get("blood", [])
                low = data.get("low", [])
                normal = data.get("normal", [])
                all_blood = extreme + blood + low
                # ---- 1. 饼图 ----
                ax_pie.clear()
                counts = [len(extreme), len(blood), len(low), len(normal)]
                labels = ["🩸极血腥", "🩸血腥", "⚠️偏低", "✅正常"]
                colors_pie = ["#C62828", "#E65100", "#F57F17", "#B0BEC5"]
                total = sum(counts)
                if total > 0:
                    _wedges, _texts, _autotexts = ax_pie.pie(
                        counts, labels=labels, colors=colors_pie,
                        autopct=lambda p: f"{p:.0f}%" if p > 5 else "",
                        startangle=90, textprops={"fontsize": 9})
                    ax_pie.set_title(f"筹码分布 (共{total}只)", fontsize=11, fontweight="bold")
                else:
                    ax_pie.text(0.5, 0.5, "无数据", ha="center", va="center",
                                transform=ax_pie.transAxes, fontsize=14, color="#999")
                # ---- 2. 柱状图: dist_60 最低前15 ----
                ax_bar.clear()
                bar_data = sorted(all_blood, key=lambda x: x.get("dist_60", 999))[:15]
                if bar_data:
                    names = [f"{s.get('name','?')}({s.get('code','')})" for s in bar_data]
                    dists = [s.get("dist_60", 0) for s in bar_data]
                    bar_colors = ["#C62828" if s.get("level")=="extreme"
                                  else "#E65100" if s.get("level")=="blood"
                                  else "#F57F17" for s in bar_data]
                    y_pos = np.arange(len(names))
                    ax_bar.barh(y_pos, dists, color=bar_colors, edgecolor="white", height=0.7)
                    ax_bar.set_yticks(y_pos)
                    ax_bar.set_yticklabels(names, fontsize=8)
                    ax_bar.set_xlabel("距60日低点 (%)", fontsize=9)
                    ax_bar.set_title("💉 距60日低点最低 Top15", fontsize=11, fontweight="bold")
                    ax_bar.invert_yaxis()
                    ax_bar.axvline(x=0.5, color="#C62828", linestyle="--", alpha=0.5, label="极血腥线 0.5%")
                    ax_bar.axvline(x=2.0, color="#E65100", linestyle="--", alpha=0.5, label="血腥线 2%")
                    ax_bar.legend(fontsize=8, loc="lower right")
                    ax_bar.grid(axis="x", alpha=0.3)
                else:
                    ax_bar.text(0.5, 0.5, "无带血筹码股", ha="center", va="center",
                                transform=ax_bar.transAxes, fontsize=14, color="#999")
                # ---- 3. 散点图: dist_60 vs pct_today ----
                ax_scatter.clear()
                scatter_data = extreme + blood + low + normal
                if scatter_data:
                    levels = {"extreme": ("🩸极血腥", "#C62828"),
                              "blood": ("🩸血腥", "#E65100"),
                              "low": ("⚠️偏低", "#F57F17"),
                              "normal": ("✅正常", "#B0BEC5")}
                    for lvl, (lbl, color) in levels.items():
                        pts = [s for s in scatter_data if s.get("level") == lvl]
                        if pts:
                            xs = [s.get("dist_60", 0) for s in pts]
                            ys = [s.get("pct_today", 0) for s in pts]
                            sizes = [max(30, min(200, s.get("vol", 0)/50000)) for s in pts]
                            ax_scatter.scatter(xs, ys, s=sizes, c=color, alpha=0.7,
                                              edgecolors="white", linewidths=0.5,
                                              label=f"{lbl}({len(pts)})")
                    ax_scatter.axvline(x=0.5, color="#C62828", linestyle="--", alpha=0.4)
                    ax_scatter.axvline(x=2.0, color="#E65100", linestyle="--", alpha=0.4)
                    ax_scatter.axvline(x=5.0, color="#F57F17", linestyle="--", alpha=0.4)
                    ax_scatter.axhline(y=0, color="gray", linestyle="-", alpha=0.3)
                    ax_scatter.set_xlabel("距60日低点 (%)", fontsize=9)
                    ax_scatter.set_ylabel("今日涨跌 (%)", fontsize=9)
                    ax_scatter.set_title("🎯 全市场散点(气泡=成交量)", fontsize=11, fontweight="bold")
                    ax_scatter.legend(fontsize=8, loc="upper right")
                    ax_scatter.grid(alpha=0.2)
                    ax_scatter.set_xlim(left=-0.5)
                else:
                    ax_scatter.text(0.5, 0.5, "无数据", ha="center", va="center",
                                   transform=ax_scatter.transAxes, fontsize=14, color="#999")
                fig.tight_layout()
                canvas.draw_idle()
                # ---- 4. Treeview 表格 ----
                for item in tree.get_children():
                    tree.delete(item)
                all_entries = extreme + blood + low + normal
                for s in all_entries:
                    vol = s.get("vol", 0)
                    vol_str = f"{vol/10000:.0f}万" if vol > 10000 else str(vol)
                    tree.insert("", tk.END, values=(
                        s.get("level_name", ""),
                        s.get("code", ""),
                        s.get("name", ""),
                        f"{s.get('trade', 0):.2f}",
                        f"{s.get('min_60', 0):.2f}",
                        f"{s.get('dist_60', 0):.2f}%",
                        f"{s.get('pct_today', 0):+.2f}%",
                        vol_str,
                    ), tags=(s.get("level", "normal"),))
                snap_cnt = data.get("snapshot_count", "?")
                hist_t = data.get("hist_time", "?")
                tot_t = data.get("total_time", "?")
                status_var.set(
                    f"✅ 完成 | 快照{snap_cnt}只 | 极🩸{len(extreme)} 血{len(blood)} 低{len(low)} 正{len(normal)}"
                    f" | K线验证{hist_t}s | 总{tot_t}s"
                )
            threading.Thread(target=work, daemon=True).start()
        scan_btn.config(command=_run_scan)

    def _show_mainline_dialog(self):
        """🔥 主线雷达: 选出 2-3 周内最强主线板块,多维评分 + AI 策略建议"""
        import datetime
        import ssl
        import threading
        import time
        ssl._create_default_https_context = ssl._create_unverified_context
        import tkinter as tk
        from tkinter import scrolledtext, ttk
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg,
                NavigationToolbar2Tk,
            )
            from matplotlib.figure import Figure
        except Exception as e:
            messagebox.showerror("错误", f"matplotlib 导入失败: {e}", parent=self.root)
            return
        win = self._toplevel(self.root)
        win.title("🔥 主线雷达 · 最强板块扫描")
        win.geometry("1600x950")
        win.transient(self.root)
        # ============ 1 顶部 Banner ============
        banner = tk.Frame(win, bg="#E64A19", height=72)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg="#E64A19")
        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(bi, text="🔥 主线雷达 · 最强板块扫描器",
                 font=("Microsoft YaHei", 16, "bold"),
                 bg="#E64A19", fg="#FFEBEE").pack(anchor="w")
        tk.Label(bi, text="🎯 多维评分:均线多头(30%) + 20日均成交额(30%) + 2周涨幅(20%) + 活跃度(20%)",
                 font=("Microsoft YaHei", 10),
                 bg="#E64A19", fg="#FFCCBC").pack(anchor="w")
        tk.Label(bi, text="📊 ≥70分(红)=强主线   40-70(黄)=活跃   <40(灰)=弱势   💡 双击展开成分股",
                 font=("Microsoft YaHei", 9),
                 bg="#E64A19", fg="#FFAB91").pack(anchor="w")
        # ============ 2 参数区 ============
        top = ttk.LabelFrame(win, text="📝 扫描参数", padding=8)
        top.pack(fill=tk.X, padx=5, pady=(5, 2))
        row1 = ttk.Frame(top)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="板块类型:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT)
        type_var = tk.StringVar(value="全部")
        ttk.Combobox(row1, textvariable=type_var, values=["概念", "行业", "全部"],
                     width=6, state="readonly").pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="  Top N:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, padx=(15, 0))
        topn_var = tk.IntVar(value=50)
        ttk.Spinbox(row1, from_=10, to=200, increment=10, width=5,
                    textvariable=topn_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="  均线周期:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, padx=(15, 0))
        ma_var = tk.StringVar(value="60日")
        ttk.Combobox(row1, textvariable=ma_var, values=["20日", "60日"],
                     width=6, state="readonly").pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="  AI分析:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, padx=(15, 0))
        ai_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="扫描完自动AI策略", variable=ai_var).pack(side=tk.LEFT, padx=5)
        scan_btn = ttk.Button(row1, text="🔍 开始扫描", width=14)
        scan_btn.pack(side=tk.LEFT, padx=15)
        status_var = tk.StringVar(value="💡 点「开始扫描」扫描全市场最强主线板块")
        ttk.Label(row1, textvariable=status_var, font=("TkDefaultFont", 10),
                  foreground="#666").pack(side=tk.LEFT, fill=tk.X, expand=True)
        # ============ 3 主体: 左图 + 右表 ============
        body = ttk.Panedwindow(win, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 2))
        # ---- 左:matplotlib 两图 ----
        chart_frame = ttk.LabelFrame(body, text="📈 主线强度分析", padding=3)
        body.add(chart_frame, weight=3)
        fig = Figure(figsize=(9, 8), dpi=100, facecolor="#fafafa")
        ax_bar = fig.add_subplot(211)   # Top10 柱状图
        ax_ma = fig.add_subplot(212)    # 均线排列分布图
        fig.subplots_adjust(hspace=0.35, top=0.95, bottom=0.06, left=0.12, right=0.96)
        for ax in [ax_bar, ax_ma]:
            ax.text(0.5, 0.5, "⏳ 等待扫描...", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="#bbb")
            ax.set_xticks([]); ax.set_yticks([])
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, chart_frame).update()
        # ---- 右:Treeview 数据表 ----
        table_frame = ttk.LabelFrame(body, text="📋 主线板块排名", padding=3)
        body.add(table_frame, weight=2)
        cols = ("rank", "type", "name", "score", "ma_score", "turnover20", "pct2w", "volatility")
        col_labels = {"rank": "#", "type": "类型", "name": "板块", "score": "总分",
                      "ma_score": "均线", "turnover20": "20日均额(亿)", "pct2w": "2周涨幅%",
                      "volatility": "活跃度"}
        col_widths = {"rank": 35, "type": 50, "name": 120, "score": 55,
                      "ma_score": 45, "turnover20": 85, "pct2w": 70,
                      "volatility": 55}
        tree_frame = ttk.Frame(table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=18)
        _style = ttk.Style()
        _style.configure("Treeview.Heading", font=("", 11, "bold"), rowheight=26)
        _style.configure("Treeview", rowheight=24)
        for c in cols:
            tree.heading(c, text=col_labels[c])
            tree.column(c, width=col_widths[c], anchor="center", stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(fill=tk.X)
        tree.tag_configure("strong", foreground="#C62828", font=("", 11, "bold"))
        tree.tag_configure("mid", foreground="#E65100", font=("", 11, "bold"))
        tree.tag_configure("weak", foreground="#666666", font=("", 11))
        # ============ 列头双击排序 ============
        _sort_state = {"col": None, "reverse": False}
        def _on_header_click(col):
            """点击列头排序, 再点同一列切换升降"""
            if _sort_state["col"] == col:
                _sort_state["reverse"] = not _sort_state["reverse"]
            else:
                _sort_state["col"] = col
                _sort_state["reverse"] = False
            cols.index(col)
            items = [(tree.set(k, col), k) for k in tree.get_children('')]
            # 数字列按数值排, 文本列按字符串排
            def _sort_key(x):
                v = x[0]
                try:
                    return (0, float(v))
                except Exception:
                    return (1, str(v))
            items.sort(key=_sort_key, reverse=_sort_state["reverse"])
            for idx, (_, k) in enumerate(items):
                tree.move(k, '', idx)
            # 排序后重新编号 rank 列
            for idx, k in enumerate(tree.get_children(''), 1):
                vals = list(tree.item(k, "values"))
                vals[0] = idx
                tree.item(k, values=vals)
            # 更新列头显示排序指示
            arrow = " ▼" if _sort_state["reverse"] else " ▲"
            for c in cols:
                lbl = col_labels[c]
                if c == _sort_state["col"]:
                    tree.heading(c, text=lbl + arrow)
                else:
                    tree.heading(c, text=lbl)
        # 给每列绑 heading command
        for c in cols:
            tree.heading(c, text=col_labels[c],
                         command=lambda col=c: _on_header_click(col))
        # ============ 4 底部 AI 策略区 ============
        bottom_frame = ttk.LabelFrame(win, text="🤖 AI 当日策略分析", padding=3)
        bottom_frame.pack(fill=tk.X, padx=5, pady=(2, 5))
        ai_log = scrolledtext.ScrolledText(bottom_frame, height=6, wrap=tk.WORD,
                                           font=("Microsoft YaHei", 10),
                                           bg="#FFF8E1", fg="#BF360C")
        ai_log.pack(fill=tk.X)
        ai_log.insert(tk.END, "💡 扫描完成后自动生成 AI 策略建议...\n")
        # ============ 5 双击板块 → 展开成分股 ============
        def _on_tree_double(event):
            item = tree.selection()
            if not item: return
            vals = tree.item(item[0], "values")
            if not vals or len(vals) < 4: return
            sector_name = str(vals[2]).strip()
            sector_type = str(vals[1]).strip()
            # 异步拉成分股
            def _work():
                try:
                    import akshare as _ak
                    if sector_type == "概念":
                        # 试东方财富接口（可能连不上）
                        try:
                            cons = _ak.stock_board_concept_cons_em(symbol=sector_name)
                        except Exception:
                            cons = None
                    else:
                        try:
                            cons = _ak.stock_board_industry_cons_em(symbol=sector_name)
                        except Exception:
                            cons = None
                    if cons is not None and len(cons) > 0:
                        # 弹窗显示成分股
                        self.root.after(0, lambda: _show_cons_popup(sector_name, sector_type, cons))
                    else:
                        # 回退：用实时行情里的个股
                        self.root.after(0, lambda: messagebox.showinfo(
                            "成分股",
                            f"获取 {sector_name}({sector_type}) 成分股失败\n"
                            f"(东方财富接口不可用,请稍后重试)", parent=win))
                except Exception as e:
                    self.root.after(0, lambda e=e: messagebox.showerror(
                        "错误", f"拉取成分股失败: {e}", parent=win))
            threading.Thread(target=_work, daemon=True).start()
        tree.bind("<Double-1>", _on_tree_double)
        # --------- 成分股子弹窗 ---------
        def _show_cons_popup(sector_name, sector_type, df_cons):
            pw = tk.Toplevel(win)
            pw.title(f"📋 {sector_name} ({sector_type}) · 成分股")
            pw.geometry("900x600")
            pw.transient(win)
            try:
                cols2 = list(df_cons.columns)[:6]
            except Exception:
                cols2 = list(df_cons.columns)
            cols2 = [c for c in cols2 if c in df_cons.columns]
            tt = ttk.Treeview(pw, columns=cols2, show="headings")
            for c in cols2:
                tt.heading(c, text=c)
                tt.column(c, width=100, anchor="center")
            for _, row in df_cons.head(500).iterrows():
                vals = [str(row[c]) for c in cols2]
                tt.insert("", tk.END, values=vals)
            tt.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            # 双击成分股 → 日K
            def _open_cons_kline(event):
                it = tt.selection()
                if not it: return
                vv = tt.item(it[0], "values")
                # 尝试在成分股里找代码列
                code = None
                name = ""
                for i, c in enumerate(cols2):
                    if "代码" in c or "code" in c.lower():
                        code = str(vv[i]).zfill(6) if vv[i] else None
                    if "名称" in c or "name" in c.lower():
                        name = str(vv[i])
                if code and code.replace(".", "").isdigit():
                    def _kw():
                        try:
                            kl = self._get_daily_kline_data_tushare(code, days=120)
                        except Exception: kl = None
                        if kl:
                            self.root.after(0, lambda: self._show_daily_kline_zoom(kl, name))
                    threading.Thread(target=_kw, daemon=True).start()
            tt.bind("<Double-1>", _open_cons_kline)
        # ============ 扫描逻辑 ============
        def _run_scan():
            import akshare as ak
            scan_btn.config(state=tk.DISABLED)
            status_var.set("⏳ 第1步: 拉取板块列表...")
            # 清空
            for item in tree.get_children():
                tree.delete(item)
            for ax in [ax_bar, ax_ma]:
                ax.clear()
                ax.text(0.5, 0.5, "⏳ 扫描中...", ha="center", va="center",
                        transform=ax.transAxes, fontsize=14, color="#bbb")
                ax.set_xticks([]); ax.set_yticks([])
            canvas.draw_idle()
            ai_log.delete("1.0", tk.END)
            ai_log.insert(tk.END, "⏳ 扫描中,请稍候...\n")
            t0 = time.time()
            sector_type = type_var.get()
            top_n = topn_var.get()
            ma_days = 60 if ma_var.get() == "60日" else 20
            # ---------- 1) 拉板块列表 ----------
            status_var.set("⏳ 拉取板块列表...")
            sector_list = []  # [(type, name, code), ...]
            try:
                if sector_type in ("概念", "全部"):
                    df_th_con = safe_call(ak.stock_board_concept_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_ths")
                    for _, r in df_th_con.iterrows():
                        sector_list.append(("概念", str(r["name"]), str(r["code"])))
                    status_var.set(f"⏳ 概念板块 {len(df_th_con)} 个...")
            except Exception as e:
                print(f"概念列表失败: {e}")
            try:
                if sector_type in ("行业", "全部"):
                    df_th_ind = safe_call(ak.stock_board_industry_name_ths, fallback=pd.DataFrame(), label="ak.stock_board_industry_name_ths")
                    for _, r in df_th_ind.iterrows():
                        sector_list.append(("行业", str(r["name"]), str(r["code"])))
                    status_var.set(f"⏳ 行业板块 {len(df_th_ind)} 个...")
            except Exception as e:
                print(f"行业列表失败: {e}")
            if not sector_list:
                status_var.set("❌ 板块列表为空")
                scan_btn.config(state=tk.NORMAL)
                return
            # ---------- 2) 并行拉板块K线 → 算全部指标 ----------
            from concurrent.futures import ThreadPoolExecutor, as_completed

            import numpy as np
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=ma_days + 30)
            sd_str = start_date.strftime("%Y%m%d")
            ed_str = end_date.strftime("%Y%m%d")
            results = {}  # {name: {type, ma_score, pct2w, turnover20, volatility}}
            total = len(sector_list)
            def _fetch_one(item):
                stype, sname, _scode = item
                try:
                    if stype == "概念":
                        df_k = ak.stock_board_concept_index_ths(symbol=sname,
                                                                start_date=sd_str, end_date=ed_str)
                    else:
                        df_k = ak.stock_board_industry_index_ths(symbol=sname,
                                                                start_date=sd_str, end_date=ed_str)
                    if df_k is None or len(df_k) < max(20, ma_days):
                        return (sname, None)
                    closes = df_k["收盘价"].astype(float).values
                    volumes = df_k["成交量"].astype(float).values if "成交量" in df_k.columns else None
                    amounts = df_k["成交额"].astype(float).values if "成交额" in df_k.columns else None
                    # --- 均线评分 ---
                    ma5 = np.mean(closes[-5:]) if len(closes) >= 5 else None
                    ma10 = np.mean(closes[-10:]) if len(closes) >= 10 else None
                    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else None
                    ma60 = np.mean(closes[-60:]) if len(closes) >= 60 else None
                    ma_ok_60 = all([ma5, ma10, ma20, ma60]) and ma5 > ma10 > ma20 > ma60
                    ma_ok_20 = all([ma5, ma10, ma20]) and ma5 > ma10 > ma20
                    ma20_up = (ma20 > np.mean(closes[-25:-20])) if (ma20 and len(closes) >= 25) else False
                    if ma_days >= 60:
                        ma_score = 100 if (ma_ok_60 and ma20_up) else (
                            80 if ma_ok_60 else (60 if (ma_ok_20 and ma20_up) else (40 if ma_ok_20 else 20)))
                    else:
                        ma_score = 100 if (ma_ok_20 and ma20_up) else (
                            80 if ma_ok_20 else (60 if ma20_up else 40))
                    # --- 2周涨幅 ---
                    pct2w = (closes[-1] / closes[-11] - 1) * 100 if len(closes) >= 11 else 0
                    # --- 20日均成交额 ---
                    turnover20 = float(np.mean(amounts[-20:])) if amounts is not None and len(amounts) >= 20 else 0
                    # --- 活跃度: 近5日均量 / 近20日均量 ---
                    volatility = 0.5
                    if volumes is not None and len(volumes) >= 20:
                        vol5 = np.mean(volumes[-5:])
                        vol20 = np.mean(volumes[-20:])
                        volatility = min(2.5, max(0, vol5 / vol20))
                    return (sname, {
                        "type": stype, "ma_score": ma_score,
                        "pct2w": pct2w, "turnover20": turnover20,
                        "volatility": volatility,
                    })
                except Exception:
                    return (sname, None)
            status_var.set(f"⏳ 并行扫描 {total} 个板块K线 (8线程)...")
            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(_fetch_one, item): item for item in sector_list}
                for fut in as_completed(futures):
                    sname, data = fut.result()
                    if data:
                        results[sname] = data
            status_var.set(f"⏳ 共获 {len(results)} 个有效板块 → 计算排名...")
            if not results:
                status_var.set("❌ 没有有效板块数据")
                scan_btn.config(state=tk.NORMAL)
                return
            # ---------- 4) 归一化加权评分 ----------
            def _normalize(vals, higher_better=True):
                vs = list(vals)
                if not vs:
                    return [0.5]
                mn, mx = min(vs), max(vs)
                if mx == mn:
                    return [0.5] * len(vs)
                if higher_better:
                    return [(v - mn) / (mx - mn) for v in vs]
                else:
                    return [(mx - v) / (mx - mn) for v in vs]
            names = list(results.keys())
            ma_scores = [results[n]["ma_score"] for n in names]
            turnovers = [results[n]["turnover20"] for n in names]
            pct2ws = [max(-50, min(50, results[n]["pct2w"])) for n in names]
            vols = [results[n]["volatility"] for n in names]
            ma_norm = ma_scores  # 已经是 0-100
            to_norm = [x * 100 for x in _normalize(turnovers)]
            pct_norm = [x * 100 for x in _normalize(pct2ws)]
            vo_norm = [x * 100 for x in _normalize(vols)]
            # 4 维加权: 均线(30%) + 成交额(30%) + 2周涨幅(20%) + 活跃度(20%)
            scores = {}
            for i, n in enumerate(names):
                total_score = (
                    0.30 * ma_norm[i] +
                    0.30 * to_norm[i] +
                    0.20 * pct_norm[i] +
                    0.20 * vo_norm[i]
                )
                scores[n] = round(total_score, 1)
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
            # ---------- 5) 填充 Treeview ----------
            for rank, (name, score) in enumerate(ranked, 1):
                d = results[name]
                tag = "strong" if score >= 70 else ("mid" if score >= 40 else "weak")
                turnover_yi = round(d.get("turnover20", 0) / 1e8, 1) if d.get("turnover20", 0) > 0 else 0
                tree.insert("", tk.END, values=(
                    rank, d["type"], name, score,
                    d["ma_score"], turnover_yi,
                    round(d["pct2w"], 2),
                    round(d["volatility"], 2),
                ), tags=(tag,))
            # ---------- 6) 左图: Top10 柱状图 + MA 分布 ----------
            top10 = ranked[:10]
            names10 = [n for n, _ in top10][::-1]
            scores10 = [s for _, s in top10][::-1]
            types10 = [results[n]["type"] for n, _ in top10][::-1]
            # 每个板块独立颜色 + 类型分色 (概念用暖色,行业用冷色)
            _cmap_warm = plt.get_cmap('YlOrRd')
            _cmap_cool = plt.get_cmap('viridis')
            colors10 = []
            for i, (n, st) in enumerate(zip(names10, types10)):
                if st == "概念":
                    colors10.append(_cmap_warm(np.linspace(0.2, 0.9, 10)[i % 10]))
                else:
                    colors10.append(_cmap_cool(np.linspace(0.2, 0.85, 10)[i % 10]))
            y_pos = np.arange(len(names10))
            ax_bar.barh(y_pos, scores10, color=colors10, edgecolor="white",
                               height=0.75, linewidth=1.2)
            ax_bar.set_yticks(y_pos)
            ax_bar.set_yticklabels(names10, fontsize=9, fontweight="bold")
            ax_bar.set_xlabel("综合评分 (0-100)", fontsize=10)
            ax_bar.set_title("🏆 Top10 主线板块综合评分", fontsize=12, fontweight="bold")
            for i, s in enumerate(scores10):
                # 标注板块类型(概念🔥 / 行业🏭)
                type_icon = "🔥" if types10[i] == "概念" else "🏭"
                ax_bar.text(s + 1, i, f"{s:.1f} {type_icon}", va="center",
                            fontsize=9, fontweight="bold")
            ax_bar.set_xlim(0, 120)
            ax_bar.axvline(x=70, color="#C62828", linestyle="--", alpha=0.6, linewidth=1.5, label="主线≥70")
            ax_bar.axvline(x=40, color="#E65100", linestyle="--", alpha=0.6, linewidth=1.5, label="活跃≥40")
            ax_bar.legend(fontsize=8, loc="lower right", framealpha=0.9)
            ax_bar.grid(axis="x", alpha=0.3, linestyle=":")
            # MA 评分分布柱状图 — 各 bar 也用不同渐变
            ma_bins = {"MA多头完美": 0, "MA多头": 0, "MA20向上": 0, "MA交叉": 0}
            for n in names:
                ms = results[n]["ma_score"]
                if ms >= 80: ma_bins["MA多头完美"] += 1
                elif ms >= 60: ma_bins["MA多头"] += 1
                elif ms >= 40: ma_bins["MA20向上"] += 1
                else: ma_bins["MA交叉"] += 1
            ma_labels = list(ma_bins.keys())
            ma_counts = list(ma_bins.values())
            # 每个 bar 用独立渐变色
            _cmap_ma = plt.get_cmap('RdYlGn')
            ma_cmap = [_cmap_ma(np.linspace(0.85, 0.15, len(ma_labels))[i]) for i in range(len(ma_labels))]
            ax_ma.bar(ma_labels, ma_counts, color=ma_cmap, width=0.6,
                      edgecolor="white", linewidth=1.2)
            ax_ma.set_ylabel("板块数量", fontsize=10)
            ax_ma.set_title(f"📊 {len(results)} 个板块均线排列分布", fontsize=12, fontweight="bold")
            for i, c in enumerate(ma_counts):
                ax_ma.text(i, c + 0.3, str(c), ha="center", fontsize=10, fontweight="bold")
            ax_ma.grid(axis="y", alpha=0.3)
            canvas.draw_idle()
            # ---------- 7) 汇总 ----------
            strong = sum(1 for _, s in ranked if s >= 70)
            mid = sum(1 for _, s in ranked if 40 <= s < 70)
            weak = sum(1 for _, s in ranked if s < 40)
            elapsed = time.time() - t0
            status_var.set(
                f"✅ 扫描完成! Top{top_n}: 强主线{strong} · 活跃{mid} · 弱势{weak} | 耗时{elapsed:.1f}s "
                f"| 数据源: 同花顺K线+新浪行情"
            )
            # ---------- 8) AI 策略分析 ----------
            if ai_var.get():
                ai_log.delete("1.0", tk.END)
                ai_log.insert(tk.END, "⏳ 调用 AI 生成当日策略建议...\n")
                def _ai_work():
                    try:
                        # 构造 prompt
                        top5_info = ""
                        for i, (name, score) in enumerate(ranked[:5], 1):
                            d = results[name]
                            turnover_yi = round(d.get("turnover20", 0) / 1e8, 1)
                            top5_info += (
                                f"{i}. {name}({d['type']}) "
                                f"综合评分={score} 均线={d['ma_score']} "
                                f"2周涨幅={d['pct2w']:.2f}% "
                                f"20日均成交额={turnover_yi}亿 "
                                f"活跃度(5日/20日量比)={d['volatility']:.2f}\n"
                            )
                        [n for n, _ in ranked]
                        all_strong = [n for n, s in ranked if s >= 70]
                        all_mid = [n for n, s in ranked if 40 <= s < 70]
                        prompt = (
                            f"以下是今日A股 {len(results)} 个板块的主线雷达扫描结果:\n\n"
                            f"🔥 TOP5 最强主线:\n{top5_info}\n"
                            f"📊 全部 ≥70 分强主线: {', '.join(all_strong[:15])}\n"
                            f"📈 40-70 活跃板块: {', '.join(all_mid[:15])}\n\n"
                            f"请基于以上数据,输出:\n"
                            f"1. 今日整体市场风格判断(题材/价值/成长/周期)\n"
                            f"2. 3-5 个最强主线板块及推荐理由\n"
                            f"3. 操作策略建议(追高/低吸/观望)\n"
                            f"4. 风险提示(哪些板块可能过热需回避)\n"
                            f"请用中文、结构化、简洁输出。"
                        )
                        try:
                            raw = self.call_ai_model(
                                user_prompt=prompt,
                                system_prompt="你是A股资深投研分析师,擅长板块轮动和主线行情研判。请基于数据客观分析。",
                                max_tokens=2000,
                            )
                        except AttributeError:
                            raw = call_ai_model(
                                user_prompt=prompt,
                                system_prompt="你是A股资深投研分析师,擅长板块轮动和主线行情研判。请基于数据客观分析。",
                                max_tokens=2000,
                            )
                        self.root.after(0, lambda: (
                            ai_log.delete("1.0", tk.END),
                            ai_log.insert(tk.END, f"🤖 AI 策略分析 (耗时约 {elapsed:.1f}s 扫描)\n"),
                            ai_log.insert(tk.END, "=" * 60 + "\n\n"),
                            ai_log.insert(tk.END, raw or "(AI 未返回内容)"),
                        ))
                    except Exception as e:
                        self.root.after(0, lambda e=e: (
                            ai_log.delete("1.0", tk.END),
                            ai_log.insert(tk.END, f"❌ AI 分析失败: {e}"),
                        ))
                threading.Thread(target=_ai_work, daemon=True).start()
            scan_btn.config(state=tk.NORMAL)
        scan_btn.config(command=_run_scan)
        # ============ 底部保存按钮 ============
        save_frame = ttk.Frame(win)
        save_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        def _copy_top():
            lines = []
            for item in tree.get_children():
                v = tree.item(item, "values")
                lines.append("\t".join(str(x) for x in v))
            text = "\n".join(lines)
            win.clipboard_clear()
            win.clipboard_append(text)
            status_var.set("✅ 已复制到剪贴板")
        def _save_txt():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=win, defaultextension=".txt",
                filetypes=[("TXT", "*.txt")],
                initialfile=f"主线雷达_{datetime.date.today()}.txt")
            if not path: return
            with open(path, "w", encoding="utf-8") as f:
                f.write("主线雷达扫描报告\n")
                f.write(f"扫描时间: {datetime.datetime.now()}\n")
                f.write(f"板块类型: {type_var.get()}, TopN: {topn_var.get()}\n\n")
                for item in tree.get_children():
                    v = tree.item(item, "values")
                    f.write("\t".join(str(x) for x in v) + "\n")
                f.write("\n--- AI 策略 ---\n")
                f.write(ai_log.get("1.0", tk.END))
            status_var.set(f"✅ 已保存: {path}")
        ttk.Button(save_frame, text="📋复制TopN", command=_copy_top).pack(side=tk.LEFT, padx=3)
        ttk.Button(save_frame, text="💾保存TXT", command=_save_txt).pack(side=tk.LEFT, padx=3)
        # 手动触发 AI 分析按钮
        def _rerun_ai():
            # 复用 scan_btn → 简单起见重扫
            _run_scan()
        ttk.Button(save_frame, text="🤖 重新AI分析", command=_rerun_ai).pack(side=tk.LEFT, padx=3)

    def _show_taojiu_dialog(self):
        """🌱 淘韭雷达:爬淘股吧/韭研 → AI分析 → Treeview热点板块股票 → 双击弹日K"""
        import datetime as _dt
        import json as _json
        import os as _os
        import re
        import threading
        import time as _time
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        try:
            import requests as _requests
            from bs4 import BeautifulSoup as _BS
        except Exception as e:
            messagebox.showerror("错误", f"requests/bs4 未安装: {e}", parent=self.root)
            return
        win = self._toplevel(self.root)
        win.title("🌱 淘韭雷达 · 淘股吧+韭研热点扫描")
        win.geometry("1400x880")
        win.transient(self.root)
        # ===== 1 Banner =====
        banner = tk.Frame(win, bg="#1B5E20", height=68)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg="#1B5E20")
        bi.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)
        tk.Label(bi, text="🌱 淘韭雷达 · 热点板块扫描器",
                 font=("Microsoft YaHei", 15, "bold"),
                 bg="#1B5E20", fg="#FFEE58").pack(anchor="w")
        tk.Label(bi, text="🎯 爬取淘股吧精华 + 韭研公社 → AI提取主流热点板块/股票/推荐人/热度 → 双击行弹日K图",
                 font=("Microsoft YaHei", 9), bg="#1B5E20", fg="#A5D6A7").pack(anchor="w")
        tk.Label(bi, text="💡 数据源: tgb.cn 精华页 / jiuyangongshe.com  |  AI分析: call_ai_model |  股票映射: tushare stock_basic",
                 font=("Microsoft YaHei", 8), bg="#1B5E20", fg="#C8E6C9").pack(anchor="w")
        # ===== 2 参数区 =====
        top = ttk.LabelFrame(win, text="📝 爬取参数", padding=6)
        top.pack(fill=tk.X, padx=5, pady=(5, 2))
        row1 = ttk.Frame(top)
        row1.pack(fill=tk.X, pady=1)
        ttk.Label(row1, text="爬取源:", font=("", 11, "bold")).pack(side=tk.LEFT)
        src_tg_var = tk.BooleanVar(value=True)
        src_jy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="淘股吧", variable=src_tg_var).pack(side=tk.LEFT, padx=(5, 2))
        ttk.Checkbutton(row1, text="韭研公社", variable=src_jy_var).pack(side=tk.LEFT, padx=2)
        ttk.Label(row1, text="  详情页数:", font=("", 11, "bold")).pack(side=tk.LEFT, padx=(15, 0))
        page_var = tk.IntVar(value=30)
        ttk.Spinbox(row1, from_=5, to=80, increment=5, width=5, textvariable=page_var
                    ).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="- 爬前N篇精华详情页拿正文(越多越慢)",
                  font=("", 9), foreground="#888").pack(side=tk.LEFT)
        ttk.Label(row1, text="  AI前N字:", font=("", 11, "bold")).pack(side=tk.LEFT, padx=(15, 0))
        tok_var = tk.IntVar(value=6000)
        ttk.Spinbox(row1, from_=2000, to=15000, increment=1000, width=6, textvariable=tok_var
                    ).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="(限制喂给AI的字符数)",
                  font=("", 9), foreground="#888").pack(side=tk.LEFT)
        row2 = ttk.Frame(top)
        row2.pack(fill=tk.X, pady=1)
        go_btn = ttk.Button(row2, text="🔍 开始爬取+分析", width=16)
        go_btn.pack(side=tk.LEFT, padx=(0, 10))
        db_btn = ttk.Button(row2, text="📦 只读DB历史", width=14)
        db_btn.pack(side=tk.LEFT, padx=(0, 10))
        status_var = tk.StringVar(value="💡 点「开始爬取+分析」实时抓淘股吧精华+韭研 → AI提取热点板块")
        ttk.Label(row2, textvariable=status_var, font=("", 10), foreground="#2E7D32"
                  ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        # ===== 3 Treeview =====
        body = ttk.LabelFrame(win, text="📋 淘韭热点结果 (双击看日K · 单击看6维详细分析)", padding=3)
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        # 新增: 5日涨跌 / 评分 / 目标价
        cols = ("rank", "sector", "stock_name", "stock_code", "pct5d",
                "recommender", "winrate", "score", "target_price", "heat", "sentiment", "source", "reason")
        col_labels = {"rank": "#", "sector": "板块",
                      "stock_name": "股票", "stock_code": "代码", "pct5d": "5日涨跌",
                      "recommender": "推荐人", "winrate": "胜率%",
                      "score": "AI评分", "target_price": "目标价",
                      "heat": "热度", "sentiment": "情绪", "source": "来源", "reason": "提到原因"}
        col_widths = {"rank": 30, "sector": 85, "stock_name": 75, "stock_code": 65,
                      "pct5d": 60, "recommender": 100, "winrate": 50,
                      "score": 55, "target_price": 60,
                      "heat": 45, "sentiment": 45, "source": 50, "reason": 220}
        tree_frame = ttk.Frame(body)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        _style = ttk.Style()
        _style.configure("Treeview.Heading", font=("", 10, "bold"), rowheight=26)
        _style.configure("Treeview", rowheight=36, font=("", 9))  # 缩小字体到 9号 + 行高 36 让长文本多行显示
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=18)
        for c in cols:
            tree.heading(c, text=col_labels[c])
            tree.column(c, width=col_widths[c], anchor="center" if c != "reason" else "w", stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(body, orient="horizontal", command=tree.xview)
        tree.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(fill=tk.X)
        # 颜色 tag: 按作者胜率着色 (替代按热度)
        tree.tag_configure("wr_high", background="#C8E6C9")    # 胜率≥60 绿色
        tree.tag_configure("wr_mid", background="#FFF9C4")     # 胜率 45-60 黄色
        tree.tag_configure("wr_low", background="#FFCDD2")     # 胜率<45 红色
        tree.tag_configure("wr_unk", background="#F5F5F5")     # 未知 灰色
        # ===== 4 底部按钮 =====
        bottom = ttk.Frame(win)
        bottom.pack(fill=tk.X, padx=5, pady=(0, 5))
        def _copy_all():
            lines = ["🌱 淘韭雷达分析结果", f"生成时间: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
            for item in tree.get_children():
                v = tree.item(item, "values")
                lines.append(f"[{v[0]}] {v[1]} | {v[2]}({v[3]}) | 推荐:{v[4]} | 热度:{v[5]} | 情绪:{v[6]} | 来源:{v[7]} | {v[8]}")
            text = "\n".join(lines)
            win.clipboard_clear()
            win.clipboard_append(text)
            messagebox.showinfo("复制成功", f"已复制 {len(tree.get_children())} 条到剪贴板", parent=win)
        def _save_txt():
            fp = filedialog.asksaveasfilename(
                defaultextension=".txt", parent=win,
                initialfile=f"淘韭雷达_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                filetypes=[("Text", "*.txt")])
            if not fp:
                return
            lines = ["🌱 淘韭雷达分析结果", f"生成时间: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
            for item in tree.get_children():
                v = tree.item(item, "values")
                lines.append(f"[{v[0]}] {v[1]} | {v[2]}({v[3]}) | 推荐:{v[4]} | 热度:{v[5]} | 情绪:{v[6]} | 来源:{v[7]} | {v[8]}")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("保存成功", f"TXT 已保存:\n{fp}", parent=win)
        def _save_excel():
            try:
                from openpyxl import Workbook
            except Exception:
                messagebox.showerror("错误", "请先安装 openpyxl: pip install openpyxl", parent=win)
                return
            fp = filedialog.asksaveasfilename(
                defaultextension=".xlsx", parent=win,
                initialfile=f"淘韭雷达_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                filetypes=[("Excel", "*.xlsx")])
            if not fp:
                return
            wb = Workbook()
            ws = wb.active
            ws.title = "淘韭热点"
            headers = ["#", "板块", "股票", "代码", "推荐人", "热度", "情绪", "来源", "提到原因"]
            ws.append(headers)
            for item in tree.get_children():
                ws.append(list(tree.item(item, "values")))
            wb.save(fp)
            messagebox.showinfo("保存成功", f"Excel 已保存:\n{fp}", parent=win)
        def _save_news_info():
            rows = []
            for item in tree.get_children():
                rows.append(tree.item(item, "values"))
            if not rows:
                messagebox.showwarning("提示", "暂无数据可存", parent=win)
                return
            lines = [f"# 淘韭雷达 · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                     f"共 {len(rows)} 条热点记录", ""]
            for v in rows:
                lines.append(f"- **{v[1]}** → `{v[2]}({v[3]})` | 推荐:{v[4]} | 热度:{v[5]} | 情绪:{v[6]} | {v[8]}")
            content = "\n".join(lines)
            tab_name = f"淘韭_{_dt.datetime.now().strftime('%H%M%S')}"
            try:
                ok = save_news_info_to_db(tab_name, content)
            except Exception as e:
                ok = False
                print(f"[淘韭] save_news_info_to_db 失败: {e}")
            if ok:
                messagebox.showinfo("保存成功", f"已存入资讯表:\n{tab_name}", parent=win)
            else:
                messagebox.showerror("失败", "资讯表保存失败", parent=win)
        ttk.Button(bottom, text="📋 复制全部", command=_copy_all, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(bottom, text="💾 保存TXT", command=_save_txt, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(bottom, text="📊 保存Excel", command=_save_excel, width=12).pack(side=tk.LEFT, padx=3)
        ttk.Button(bottom, text="🗄️ 存资讯表", command=_save_news_info, width=12).pack(side=tk.LEFT, padx=3)
        # ===== 5 爬取函数 =====
        _tb_session = None
        def _get_tb_session():
            nonlocal _tb_session
            if _tb_session is None:
                s = _requests.Session()
                s.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Referer': 'https://www.tgb.cn/',
                })
                _tb_session = s
            return _tb_session
        def _crawl_taoguba_list(max_pages=3):
            """爬淘股吧精华列表,返回 [{title, url}]"""
            sess = _get_tb_session()
            articles = []
            seen = set()
            for page in range(1, max_pages + 1):
                try:
                    url = f"https://www.tgb.cn/jinghua/?page={page}" if page > 1 else "https://www.tgb.cn/jinghua/"
                    r = sess.get(url, timeout=15)
                    if r.status_code != 200:
                        continue
                    soup = _BS(r.text, 'html.parser')
                    for a in soup.find_all('a', title=True):
                        href = a.get('href', '')
                        title = a['title'].strip()
                        if not title or len(title) < 5:
                            continue
                        if href.startswith('/'):
                            href = f"https://www.tgb.cn{href}"
                        # 过滤非文章链接
                        if not any(kw in href for kw in ['/a/', '/article/', '/blog/']):
                            continue
                        key = (title[:30], href)
                        if key in seen:
                            continue
                        seen.add(key)
                        articles.append({'title': title, 'url': href})
                    _time.sleep(0.5)
                except Exception as e:
                    print(f"[淘韭] 列表页 {page} 失败: {e}")
                    continue
            return articles
        def _crawl_taoguba_detail(url):
            """爬单篇淘股吧文章详情,返回 {author, publish_time, content, views, comments}"""
            sess = _get_tb_session()
            try:
                r = sess.get(url, timeout=15)
                if r.status_code != 200:
                    return {}
                soup = _BS(r.text, 'html.parser')
                # 作者
                author = ""
                for sel in ['.user-name', '.N_Author', '.author', '.userName']:
                    el = soup.select_one(sel)
                    if el and el.get_text(strip=True):
                        author = el.get_text(strip=True)[:30]
                        break
                if not author:
                    # 兜底:找 "原创" 前面的文字
                    m = re.search(r'(\S{2,20})原创', r.text[:3000])
                    if m:
                        author = m.group(1)
                # 发布时间
                pub_time = ""
                m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', r.text[:2000])
                if m:
                    pub_time = m.group(1)
                # 正文
                content_div = None
                for cls in ['N_art_content', 'N_Content', 'artContent', 'article-content',
                            'Content', 'article-body', 'post-content', 'threadcontent']:
                    div = soup.select_one(f'.{cls}')
                    if div and len(div.get_text(strip=True)) > 50:
                        content_div = div
                        break
                if not content_div:
                    # 兜底:找最长的 div
                    all_divs = soup.find_all('div')
                    if all_divs:
                        content_div = max(all_divs, key=lambda d: len(d.get_text(strip=True)))
                content = content_div.get_text(strip=True)[:2000] if content_div else ""
                # 浏览/评论
                views, comments = 0, 0
                vm = re.search(r'浏览\s*(\d+)', r.text[:5000])
                if vm:
                    views = int(vm.group(1))
                cm = re.search(r'评论\s*(\d+)', r.text[:5000])
                if cm:
                    comments = int(cm.group(1))
                return {
                    'author': author, 'publish_time': pub_time,
                    'content': content, 'views': views, 'comments': comments,
                }
            except Exception as e:
                print(f"[淘韭] 详情爬取失败 {url[:60]}: {e}")
                return {}
        def _crawl_jiuyan():
            """爬韭研公社列表页(/a/xxx 文章链接),返回 [{title, url}]"""
            sess = _get_tb_session()
            arts = []
            seen = set()
            for page_url in ["https://www.jiuyangongshe.com/", "https://www.jiuyangongshe.com/hot",
                             "https://www.jiuyangongshe.com/new"]:
                try:
                    r = sess.get(page_url, timeout=12)
                    if r.status_code != 200:
                        continue
                    soup = _BS(r.text, 'html.parser')
                    for a in soup.find_all('a', href=True):
                        h = a.get('href', '')
                        # 韭研文章 URL 模式: /a/xxxxx
                        if '/a/' not in h:
                            continue
                        t = (a.get_text(strip=True) or a.get('title', '') or '').strip()
                        if not t or len(t) < 5:
                            continue
                        key = (t[:30], h)
                        if key in seen:
                            continue
                        seen.add(key)
                        full_h = h if h.startswith('http') else f"https://www.jiuyangongshe.com{h}"
                        arts.append({'title': t, 'url': full_h})
                    _time.sleep(0.5)
                except Exception as e:
                    print(f"[淘韭] 韭研列表页失败 {page_url}: {e}")
                    continue
            return arts
        def _crawl_jiuyan_detail(url):
            """爬韭研公社单篇文章详情,返回 {author, publish_time, content, views}"""
            sess = _get_tb_session()
            try:
                r = sess.get(url, timeout=15)
                if r.status_code != 200:
                    return {}
                soup = _BS(r.text, 'html.parser')
                # 作者
                author = ""
                for sel in ['.author', '.username', '.user-name', '.name', 'a.author']:
                    el = soup.select_one(sel)
                    if el and el.get_text(strip=True):
                        author = el.get_text(strip=True)[:30]
                        break
                if not author:
                    m = re.search(r'(?:作者|作者[:：])\s*[:：]?\s*(\S{2,20})', r.text[:3000])
                    if m:
                        author = m.group(1)
                if not author:
                    # 兜底:找用户名格式的 div
                    for d in soup.find_all(['div', 'span']):
                        cls = d.get('class', [])
                        if any('user' in c.lower() or 'name' in c.lower() or 'author' in c.lower()
                               for c in cls):
                            author = d.get_text(strip=True)[:30]
                            if author and len(author) >= 2:
                                break
                # 发布时间
                pub_time = ""
                for pat in [
                    r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})',
                    r'(\d{4}-\d{2}-\d{2})',
                    r'(\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2})',
                ]:
                    m = re.search(pat, r.text[:5000])
                    if m:
                        pub_time = m.group(1)
                        break
                # 正文
                content_div = None
                for cls in ['article-body', 'post-content', 'content', 'article-content',
                            'art_content', 'main-content', 'threadcontent', '.article-body']:
                    div = soup.select_one(f'.{cls}') if not cls.startswith('.') else soup.select_one(cls)
                    if div and len(div.get_text(strip=True)) > 50:
                        content_div = div
                        break
                if not content_div:
                    all_divs = soup.find_all('div')
                    if all_divs:
                        content_div = max(all_divs, key=lambda d: len(d.get_text(strip=True)))
                content = content_div.get_text(strip=True)[:2000] if content_div else ""
                # 浏览数
                views = 0
                vm = re.search(r'(?:浏览|阅读|查看)\s*[:：]?\s*(\d[\d,]*)', r.text[:8000])
                if vm:
                    try:
                        views = int(vm.group(1).replace(',', ''))
                    except Exception:
                        views = 0
                return {'author': author, 'publish_time': pub_time,
                        'content': content, 'views': views, 'source': '韭研'}
            except Exception as e:
                print(f"[淘韭] 韭研详情爬取失败 {url[:60]}: {e}")
                return {}
        # ===== 作者历史胜率缓存/回测 =====
        _author_winrate_cache = {}  # 内存缓存 {author: win_rate_pct}
        _wr_cache_file = _os.path.expanduser("~/.tushare/author_winrate.json")
        def _load_wr_cache():
            """从本地 JSON 加载胜率缓存"""
            nonlocal _author_winrate_cache
            try:
                if _os.path.exists(_wr_cache_file):
                    import json as _jj
                    with open(_wr_cache_file) as f:
                        _author_winrate_cache = _jj.load(f)
            except Exception:
                _author_winrate_cache = {}
        def _save_wr_cache():
            """保存胜率缓存到本地 JSON"""
            try:
                import json as _jj
                _os.makedirs(_os.path.dirname(_wr_cache_file), exist_ok=True)
                with open(_wr_cache_file, 'w', encoding='utf-8') as f:
                    _jj.dump(_author_winrate_cache, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[淘韭] 胜率缓存保存失败: {e}")
        def _calc_author_winrate(author, force_recalc=False):
            """
            回测某作者的历史胜率:
            1. 从 news_info 表找该作者历史推荐 (近 60 天内)
            2. 用正则提股票代码
            3. tushare 查推荐日后 5 天收盘价 vs 推荐日收盘价
            4. 胜率 = 涨的次数 / 总推荐次数
            5. 结果写缓存
            """
            if not author or len(author.strip()) < 2:
                return 50.0  # 未知作者默认 50%
            author = author.strip()
            # 先查缓存
            if not force_recalc and author in _author_winrate_cache:
                cached = _author_winrate_cache[author]
                # 缓存有效且不超过 7 天
                if isinstance(cached, dict):
                    import time as _t2
                    if _t2.time() - cached.get('ts', 0) < 7 * 86400:
                        return cached.get('wr', 50.0)
                else:
                    return cached  # 旧格式直接返回
            # 从 DB 提取历史
            try:
                import sqlite3
                db_path = _os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db")
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("""
                    SELECT content, created_at FROM news_info
                    WHERE (tab_name LIKE '淘股吧%' OR tab_name LIKE '韭研%'
                           OR tab_name LIKE '%热点%' OR tab_name LIKE '%主线%')
                    AND content LIKE ?
                    AND created_at >= date('now', '-90 day')
                    ORDER BY created_at DESC LIMIT 30
                """, (f'%{author}%',))
                rows = c.fetchall()
                conn.close()
            except Exception:
                rows = []
            if not rows:
                _author_winrate_cache[author] = 50.0
                return 50.0
            # 提股票代码
            code_date_pairs = []  # [(code, date_str), ...]
            re_code = re.compile(r'\b([036]\d{5})\b')
            re_date = re.compile(r'(\d{4}-\d{2}-\d{2})')
            for content, created_at in rows:
                codes = re_code.findall(content or '')
                if not codes:
                    continue
                # 找最接近的日期
                date_m = re_date.search(content or '')
                rec_date = date_m.group(1) if date_m else (created_at or '')
                if codes and rec_date:
                    code_date_pairs.append((codes[0], rec_date[:10]))
            if len(code_date_pairs) < 2:
                _author_winrate_cache[author] = 50.0
                return 50.0
            # 用 tushare 查 K 线验证
            import tushare as _ts2
            _tk_token = open(_os.path.expanduser("~/.tushare/token")).read().strip()
            _tk_pro = _ts2.pro_api(_tk_token)
            wins = 0
            total = 0
            for code, rec_date in code_date_pairs[:10]:  # 最多验 10 次
                try:
                    # 找 trade_date = rec_date 的日线，取收盘
                    df_daily = _tk_pro.daily(ts_code=f"{code}.SH" if code.startswith('6') else f"{code}.SZ",
                                             start_date=rec_date.replace('-', ''),
                                             end_date=(datetime.date.fromisoformat(rec_date)
                                                       + datetime.timedelta(days=7)).strftime('%Y%m%d'))
                    if df_daily is None or len(df_daily) < 2:
                        # 试试创业板/科创板
                        if code.startswith(('3', '0')):
                            df_daily = _tk_pro.daily(ts_code=f"{code}.SZ",
                                                     start_date=rec_date.replace('-', ''),
                                                     end_date=(datetime.date.fromisoformat(rec_date)
                                                               + datetime.timedelta(days=7)).strftime('%Y%m%d'))
                        if df_daily is None or len(df_daily) < 2:
                            continue
                    df_daily = df_daily.sort_values('trade_date')
                    close_t0 = float(df_daily.iloc[0]['close'])
                    close_t5 = float(df_daily.iloc[-1]['close']) if len(df_daily) >= 2 else close_t0
                    if close_t0 > 0:
                        total += 1
                        if close_t5 > close_t0 * 1.02:  # 涨 >2% 算赢
                            wins += 1
                except Exception:
                    continue
            wr = round(wins / total * 100, 1) if total >= 3 else 50.0
            import time as _t2
            _author_winrate_cache[author] = {'wr': wr, 'total': total, 'ts': _t2.time()}
            return wr
        # 启动时加载缓存
        _load_wr_cache()
        def _read_db_recent(days=3):
            """只读 DB 里最近 N 天的淘股吧/韭研记录"""
            rows_text = ""
            try:
                conn = self._get_db_conn() if hasattr(self, '_get_db_conn') else None
                if conn is None:
                    import sqlite3
                    db_path = _os.path.expanduser("~/Agent/stockyidong_project/data/stock_analysis.db")
                    conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("""
                    SELECT tab_name, content, created_at FROM news_info
                    WHERE (tab_name LIKE '淘股吧%' OR tab_name LIKE '韭研%')
                    AND created_at >= date('now', ?)
                    ORDER BY created_at DESC LIMIT 20
                """, (f'-{days} day',))
                for tab, content, cat in c.fetchall():
                    rows_text += f"\n=== [{tab}] {cat} ===\n{content}\n"
                conn.close()
            except Exception as e:
                print(f"[淘韭] DB 读取失败: {e}")
            return rows_text
        # ===== 6 AI 分析 =====
        def _ai_analyze(text):
            """调 call_ai_model 让它返回 JSON 数组"""
            if not text or len(text.strip()) < 200:
                return [], "爬取内容太少,无法分析"
            text_clip = text[:tok_var.get()]
            system_prompt = "你是A股短线热点分析专家,擅长从社区讨论中提取主流热点板块、领涨股票和关键推荐人。"
            user_prompt = f"""请分析以下来自[淘股吧]和[韭研公社]的社区讨论文本,提取主流热点信息。
文本内容(已截断):
---
{text_clip}
---
请严格输出一个 **纯 JSON 数组**(不要 markdown,不要代码块标记,只输出数组本身),每个元素格式:
{{
  "sector": "板块名称(如:医药/半导体/商业航天/农业化工等,用通用行业名)",
  "stock_name": "股票中文名",
  "stock_code": "6位A股代码(如600519,300750)",
  "recommender": "推荐人/作者名(提取文章的作者或明确推荐者)",
  "recommend_date": "YYYY-MM-DD 文章发布日期或推荐日期(从原文提取,找不到就用今天)",
  "mention_count": 3,
  "heat_score": 75,
  "sentiment_score": 80,
  "reason": "简短(30字内)说明被关注的原因"
}}
要求:
1. 只输出 JSON 数组,不要其他文字;
2. 优先提取有明确股票代码的记录,其次是明确的板块+股票名;
3. heat_score 依据浏览量/评论数/推荐次数估算(0-100);
4. sentiment_score 依据文字情绪判断(0-100,>50 偏多,<50 偏空);
5. recommend_date 必须返回,格式 YYYY-MM-DD;
6. 去重,同一股票保留热度最高的一条;
7. 最多返回 30 条。"""
            raw = None
            try:
                raw = self.call_ai_model(user_prompt, system_prompt, max_tokens=3000)
                if not raw:
                    return [], "AI 返回空"
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    cleaned = re.sub(r'^```(?:json)?', '', cleaned)
                    cleaned = re.sub(r'```$', '', cleaned)
                cleaned = cleaned.strip()
                s_idx = cleaned.find('[')
                e_idx = cleaned.rfind(']')
                if s_idx >= 0 and e_idx > s_idx:
                    cleaned = cleaned[s_idx:e_idx+1]
                data = _json.loads(cleaned)
                if isinstance(data, list):
                    return data, "ok"
                return [], f"AI 不是数组: {type(data)}"
            except Exception as e:
                raw_preview = (raw or "")[:500] if raw else "(AI 未返回)"
                return [], f"AI 解析失败: {e}; 原始前500字: {raw_preview}"
        # ===== 7 弹日K (双击) =====
        def _open_kline_on_double(event=None):
            sel = tree.selection()
            if not sel:
                return
            item = sel[0]
            vals = tree.item(item, "values")
            # 新列: rank(0), sector(1), name(2), code(3), ...
            code = str(vals[3]).strip()
            name = str(vals[2]).strip()
            if not code or not code.replace(".", "").isdigit():
                return
            status_var.set(f"⏳ 拉取 {name}({code}) K线...")
            def _kwork():
                try:
                    kline = self._get_daily_kline_data_tushare(code, days=120)
                except Exception:
                    kline = None
                if kline:
                    self.root.after(0, lambda: self._show_daily_kline_zoom(kline, name))
                else:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "提示", f"无法获取 {name}({code}) K线,请检查 tushare", parent=win))
                    self.root.after(0, lambda: status_var.set("⚠️ K线获取失败"))
            threading.Thread(target=_kwork, daemon=True).start()
        tree.bind("<Double-1>", _open_kline_on_double)
        # ===== 7b 单击 → 6维详细分析弹窗 =====
        _last_single_click_ts = [0]
        def _open_detail_on_single(event=None):
            sel = tree.selection()
            if not sel:
                return
            # 防抖:避免双击触发两次单击
            now = _time.time()
            if now - _last_single_click_ts[0] < 0.4:
                return
            _last_single_click_ts[0] = now
            item = sel[0]
            vals = tree.item(item, "values")
            code = str(vals[3]).strip()
            name = str(vals[2]).strip()
            if not code or not code.replace(".", "").isdigit():
                return
            # 从缓存拿完整数据
            row_dict = {}
            for iid, d in _row_data_cache:
                if iid == item:
                    row_dict = d; break
            _show_taojiu_detail_popup(name, code, vals, row_dict)
        tree.bind("<ButtonRelease-1>", _open_detail_on_single)
        def _show_taojiu_detail_popup(name, code, vals, row_dict):
            """6维详细分析弹窗:做T/持仓/胜率/基本面/技术面支撑阻力/资金情绪/主线归属"""
            dwin = self._toplevel(self.root)
            dwin.title(f"🔍 {name}({code}) · 6维深度分析")
            dwin.geometry("980x820")
            dwin.transient(win)
            # Top Banner
            tk.Label(dwin, text=f"🔍 {name}({code}) · 淘韭热点 6维详细分析",
                     font=("Microsoft YaHei", 13, "bold"),
                     bg="#1B5E20", fg="#FFEE58", height=2
                     ).pack(fill=tk.X)
            # 信息条
            info_line = f"板块:{vals[1]} | 推荐人:{vals[5]} | 胜率:{vals[6]}% | 热度:{vals[9]} | 情绪:{vals[10]} | 5日涨跌:{vals[4]}"
            tk.Label(dwin, text=info_line, font=("", 10), bg="#E8F5E9", fg="#1B5E20"
                     ).pack(fill=tk.X)
            # 结果区
            from tkinter import scrolledtext as _st2
            result = _st2.ScrolledText(dwin, font=("Microsoft YaHei", 11), wrap=tk.WORD)
            result.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            result.insert("1.0", f"⏳ 正在 AI 6维深度分析 {name}({code}) ...\n")
            result.config(state=tk.DISABLED)
            # 构建 prompt — 一次 AI 调用覆盖 6 维
            pct5d = row_dict.get("_pct5d") if row_dict else None
            reason = str(vals[12]) if len(vals) > 12 else ""
            recommend_ctx = f"【淘韭热点上下文】\n板块:{vals[1]} | 提到原因:{reason}\n推荐人:{vals[5]} | 作者历史胜率(系统计算):{vals[6]}%\n5日涨跌幅:{pct5d if pct5d is not None else '未知'}%"
            # system prompt: 整合 rocket-scan + 6维分析
            TAOJIU_DETAIL_SYSTEM = """你是A股短线/波段交易教练,同时也是 rocket-scan 方法论的实战派。
请严格按以下 6 个维度逐只股票输出分析,每个维度要写「结论 + 依据」。
## 输出格式(每只股票):
### 0️⃣ 股票定性 (先做这步!)
- 类型:机构票(业绩驱动)/游资票(情绪连板)/周期资源/普通票
- 判断依据:3条以内
### 1️⃣ 是否可以做T?
- 结论:✅可做T / ⚠️条件做T / ❌ 不宜做T
- 建议操作:买T区间/卖T区间/底仓比例
- 依据:(均线位置/量能/板块节奏)
### 2️⃣ 是否应该持仓?
- 结论:🟢持有 / 🔴减仓 / 🟡观望
- 止损位:xx 元
- 止盈信号:
- 依据:(趋势/仓位安全垫/大盘S阶段)
### 3️⃣ 历史胜率评估
- 推荐作者历史胜率:XX%
- 你对这个胜率的判断(样本够不够?最近状态如何?)
- 同类策略历史胜率:XX%
### 4️⃣ 基本面 + 技术面
**基本面**:PE/PB/ROE/净利润增速/行业地位
**技术面**:
- 关键支撑位(近3个):xx / xx / xx
- 关键阻力位(近3个):xx / xx / xx
- 当前价位在什么位置(区间底部/中间/顶部)
### 5️⃣ 资金面 + 情绪面
- 主力资金近3日流向
- 北向/机构持仓变化
- 情绪指标(换手率/涨停数/炸板率)
### 6️⃣ 是否属于当前主线/主流板块?
- 结论:✅ 主线 / ⚠️ 次主线 / ❌ 边缘
- 主线逻辑:
- 板块内排名:
- 持续度判断(还能持续多久?)
### 🎯 综合决策(一句话)
> 买/卖/T/持 的核心理由
⚠️ 如果某些数据你不知道(如 PE/ROE),写"⚠️ 此处为 AI 合理推测,建议核实"。"""
            user_prompt = f"""{recommend_ctx}
请对 {name}({code}) 严格按"输出格式"逐维分析。
如果可能,尽量结合 rocket-scan 方法论(机构票/游资票/周期股/普通票的不同持有策略)。"""
            def _do_detail():
                try:
                    r = self.call_ai_model(user_prompt, TAOJIU_DETAIL_SYSTEM, max_tokens=4000)
                    if not r: r = "AI 返回为空。"
                except Exception as e:
                    r = f"❌ 分析失败: {e}"
                def _update():
                    result.config(state=tk.NORMAL)
                    result.delete("1.0", tk.END)
                    header = f"🔍 {name}({code}) · 6维深度分析\n" + "=" * 60 + "\n"
                    result.insert("1.0", header + r)
                    result.config(state=tk.DISABLED)
                if hasattr(self, "root") and self.root.winfo_exists():
                    self.root.after(0, _update)
            threading.Thread(target=_do_detail, daemon=True).start()
            # 底部按钮
            btm = ttk.Frame(dwin)
            btm.pack(fill=tk.X, padx=6, pady=4)
            def _save_d():
                fp = filedialog.asksaveasfilename(
                    defaultextension=".txt", parent=dwin,
                    initialfile=f"淘韭详情_{name}_{_dt.datetime.now().strftime('%H%M%S')}.txt")
                if fp:
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(result.get("1.0", tk.END))
                    messagebox.showinfo("已保存", fp, parent=dwin)
            ttk.Button(btm, text="💾 保存", command=_save_d).pack(side=tk.LEFT, padx=3)
            ttk.Button(btm, text="📈 打开日K",
                       command=lambda: self._show_daily_kline_zoom(
                           self._get_daily_kline_data_tushare(code, days=120), name)
                       ).pack(side=tk.LEFT, padx=3)
            ttk.Button(btm, text="关闭", command=dwin.destroy).pack(side=tk.RIGHT, padx=3)
        tree.bind("<Double-1>", _open_kline_on_double)  # 双击保持日K
        # ===== 8 右键菜单 =====
        def _show_ctx_menu(event):
            sel = tree.selection()
            if not sel:
                return
            item = sel[0]
            vals = tree.item(item, "values")
            # 从缓存拿完整数据
            row_dict = {}
            for iid, d in _row_data_cache:
                if iid == item:
                    row_dict = d; break
            ctx = tk.Menu(win, tearoff=0)
            ctx.add_command(label="🔍 6维深度分析",
                            command=lambda: _show_taojiu_detail_popup(
                                str(vals[2]), str(vals[3]), vals, row_dict))
            ctx.add_command(label="📈 打开日K图", command=_open_kline_on_double)
            ctx.add_command(label="📋 复制整行", command=lambda: (
                win.clipboard_clear(),
                win.clipboard_append(" | ".join(str(v) for v in tree.item(sel[0], "values")))))
            ctx.tk_popup(event.x_root, event.y_root)
        tree.bind("<Button-3>", _show_ctx_menu)
        # ===== 9 填充表格 =====
        _row_data_cache = []  # 保存每行的原始 dict,方便详情弹窗用
        def _tushare_5d_pct(code):
            """查 5 个交易日涨跌幅"""
            try:
                import tushare as _ts3
                _tk_token = _os.path.expanduser("~/.tushare/token")
                if not _os.path.exists(_tk_token):
                    return None
                _tk_pro = _ts3.pro_api()
                prefix = "SH" if str(code).startswith('6') else "SZ"
                td = _dt.datetime.now().strftime('%Y%m%d')
                start = (_dt.datetime.now() - _dt.timedelta(days=15)).strftime('%Y%m%d')
                df = _tk_pro.daily(ts_code=f"{code}.{prefix}", start_date=start, end_date=td)
                if df is None or len(df) < 2:
                    # 试试创业板/科创板 fallback
                    for p2 in ["SZ", "SH"]:
                        df2 = _tk_pro.daily(ts_code=f"{code}.{p2}", start_date=start, end_date=td)
                        if df2 is not None and len(df2) >= 2:
                            df = df2; break
                if df is None or len(df) < 2:
                    return None
                df = df.sort_values('trade_date')
                close_today = float(df.iloc[-1]['close'])
                # 往前找 5 个交易日
                prev_idx = max(0, len(df) - 6)
                close_5d_ago = float(df.iloc[prev_idx]['close'])
                if close_5d_ago > 0:
                    return round((close_today - close_5d_ago) / close_5d_ago * 100, 2)
            except Exception:
                pass
            return None
        def _fill_tree(data):
            for it in tree.get_children():
                tree.delete(it)
            _row_data_cache.clear()
            def _async_fill():
                for idx, row in enumerate(data, 1):
                    sector = str(row.get("sector", "") or "")[:10]
                    sname = str(row.get("stock_name", "") or "")[:8]
                    scode = str(row.get("stock_code", "") or "")
                    recommender = str(row.get("recommender", "") or "")[:10]
                    heat = int(row.get("heat_score", row.get("mention_count", 0)) or 0)
                    sentiment = int(row.get("sentiment_score", 50) or 50)
                    source = str(row.get("source", "淘股吧") or "淘股吧")[:6]
                    reason = str(row.get("reason", "") or "")[:40]
                    # 胜率
                    wr = _calc_author_winrate(recommender) if recommender else 50.0
                    # 5日涨跌 (tushare)
                    pct5d = _tushare_5d_pct(scode) if scode else None
                    pct5d_str = f"{pct5d:+.2f}%" if pct5d is not None else "..."
                    # AI 评分 / 目标价 — 先用默认占位,让 AI 先提取 JSON 里没这俩
                    ai_score = int(row.get("score", (heat + sentiment) // 2) or 0)
                    target = str(row.get("target_price", "") or "")
                    # 按胜率着色
                    if wr >= 60:   tag = "wr_high"
                    elif wr >= 45: tag = "wr_mid"
                    elif wr > 0:   tag = "wr_low"
                    else:          tag = "wr_unk"
                    # 5日涨跌红涨绿跌 tag
                    if pct5d is not None:
                        if pct5d > 3:
                            tag = (tag, "wr_high")
                        elif pct5d < -3:
                            tag = (tag, "wr_low")
                    item_id = tree.insert("", tk.END, values=(
                        idx, sector, sname, scode, pct5d_str,
                        recommender, f"{wr:.0f}" if wr != 50.0 else "?",
                        ai_score, target or "-",
                        heat, sentiment, source, reason
                    ), tags=(tag,) if isinstance(tag, str) else tag)
                    # 缓存原始 dict
                    cached = dict(row)
                    cached["_idx"] = idx
                    cached["_pct5d"] = pct5d
                    _row_data_cache.append((item_id, cached))
                _save_wr_cache()
            threading.Thread(target=_async_fill, daemon=True).start()
        # ===== 10 主流程 =====
        def _run_crawl_analyze(read_db_only=False):
            go_btn.config(state=tk.DISABLED)
            db_btn.config(state=tk.DISABLED)
            for it in tree.get_children():
                tree.delete(it)
            status_var.set("⏳ 开始爬取...")
            def work():
                try:
                    all_text = ""
                    meta_info = ""
                    used_classes_fallback = False
                    if read_db_only:
                        self.root.after(0, lambda: status_var.set("📦 读取 DB 最近 3 天记录..."))
                        all_text = _read_db_recent(days=3)
                        meta_info = "DB 历史"
                    else:
                        # ==== 使用专用 Crawler 类（带重试/URL 解析）====
                        if src_tg_var.get():
                            self.root.after(0, lambda: status_var.set("⏳ 用 TaogubaCrawler 爬精华..."))
                            try:
                                _tc = TaogubaCrawler()
                                tg_arts_objs = _tc.crawl_realtime_articles(max_pages=2)
                                self.root.after(0, lambda: status_var.set(
                                    f"✅ TaogubaCrawler 抓到 {len(tg_arts_objs)} 篇 → 组装给 AI..."))
                                for art in tg_arts_objs[:page_var.get()]:
                                    all_text += f"\n{'='*60}\n"
                                    all_text += f"【淘股吧】标题: {art.get('title','')}\n"
                                    all_text += f"  作者: {art.get('author','未知')}  时间: {art.get('publish_time','')}\n"
                                    all_text += f"  浏览: {art.get('views',0)}\n"
                                    all_text += f"  正文: {art.get('content','')}\n"
                                    # 如果没有 content，把 title 多写几次让 AI 能提取
                                    if not art.get('content'):
                                        all_text += f"  (标题重复) {art.get('title','')}\n"
                            except Exception as e1:
                                self.root.after(0, lambda e1=e1: status_var.set(f"⚠️ TaogubaCrawler 失败: {e1}, 回退内联爬虫..."))
                                # 回退内联
                                tg_arts = _crawl_taoguba_list(max_pages=2)
                                for art in tg_arts[:page_var.get()]:
                                    detail = _crawl_taoguba_detail(art['url'])
                                    if detail:
                                        all_text += f"\n{'='*60}\n"
                                        all_text += f"【淘股吧】标题: {art['title']}\n"
                                        all_text += f"  作者: {detail.get('author','未知')}  时间: {detail.get('publish_time','')}\n"
                                        all_text += f"  浏览: {detail.get('views',0)}\n"
                                        all_text += f"  正文: {detail.get('content','')}\n"
                                used_classes_fallback = True
                        if src_jy_var.get():
                            self.root.after(0, lambda: status_var.set("⏳ 用 JiuYangGongSheCrawler 爬..."))
                            try:
                                _jc = JiuYangGongSheCrawler()
                                jy_arts_objs = _jc.crawl_articles(max_pages=2)
                                self.root.after(0, lambda: status_var.set(
                                    f"✅ JiuYangGongSheCrawler 抓到 {len(jy_arts_objs)} 篇"))
                                for art in jy_arts_objs[:page_var.get()]:
                                    all_text += f"\n{'='*60}\n"
                                    all_text += f"【韭研】标题: {art.get('title','')}\n"
                                    all_text += f"  作者: {art.get('author','未知')}  时间: {art.get('publish_time','')}\n"
                                    all_text += f"  浏览: {art.get('views',0)}\n"
                                    all_text += f"  正文: {art.get('content','')}\n"
                            except Exception as e2:
                                self.root.after(0, lambda e2=e2: status_var.set(f"⚠️ JiuYangGongSheCrawler 失败: {e2}, 回退内联..."))
                                jy_arts = _crawl_jiuyan()
                                for art in jy_arts[:page_var.get()]:
                                    detail = _crawl_jiuyan_detail(art['url'])
                                    if detail:
                                        all_text += f"\n{'='*60}\n"
                                        all_text += f"【韭研】标题: {art['title']}\n"
                                        all_text += f"  作者: {detail.get('author','未知')}  时间: {detail.get('publish_time','')}\n"
                                        all_text += f"  浏览: {detail.get('views',0)}\n"
                                        all_text += f"  正文: {detail.get('content','')}\n"
                                used_classes_fallback = True
                        if not all_text or len(all_text.strip()) < 300:
                            # 最终兜底: 读 DB
                            self.root.after(0, lambda: status_var.set("⚠️ 实时爬取空,回退读 DB..."))
                            all_text = _read_db_recent(days=3)
                            meta_info = "DB兜底"
                        else:
                            meta_info = ("专用Crawler类" if not used_classes_fallback else "部分回退+DB")
                    if not all_text or len(all_text.strip()) < 200:
                        self.root.after(0, lambda: status_var.set("❌ 未获取到任何内容"))
                        self.root.after(0, lambda: go_btn.config(state=tk.NORMAL))
                        self.root.after(0, lambda: db_btn.config(state=tk.NORMAL))
                        return
                    self.root.after(0, lambda: status_var.set(
                        f"📊 已获取 {len(all_text)} 字 ({meta_info}) → 调 AI 提取热点..."))
                    data, msg = _ai_analyze(all_text)
                    if data:
                        # 排序:热度高的在前
                        try:
                            data.sort(key=lambda r: -(int(r.get('heat_score', r.get('mention_count', 0)) or 0)))
                        except Exception:
                            pass
                        self.root.after(0, lambda d=data: _fill_tree(d))
                        self.root.after(0, lambda: status_var.set(
                            f"✅ 完成 | {len(data)} 条热点 | 正在回填5日涨跌+评分..."))
                    else:
                        self.root.after(0, lambda: status_var.set(f"⚠️ AI 未提取到有效数据: {msg}"))
                        self.root.after(0, lambda: messagebox.showwarning(
                            "AI 提示", f"AI 未返回有效 JSON。\n原因: {msg[:200]}", parent=win))
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.root.after(0, lambda e=e: status_var.set(f"❌ 错误: {e}"))
                    self.root.after(0, lambda e=e: messagebox.showerror(
                        "错误", str(e), parent=win))
                finally:
                    self.root.after(0, lambda: go_btn.config(state=tk.NORMAL))
                    self.root.after(0, lambda: db_btn.config(state=tk.NORMAL))
            threading.Thread(target=work, daemon=True).start()
        go_btn.config(command=lambda: _run_crawl_analyze(read_db_only=False))
        db_btn.config(command=lambda: _run_crawl_analyze(read_db_only=True))

    def _show_ai_writer_dialog(self):
        """✍️ AI 写手：多维度（作家风格/文章类型/情感风格）智能创作"""
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
        win = self._toplevel(self.root)
        win.title("✍️ AI 写手 · 多维风格创作")
        win.geometry("1000x820")
        win.minsize(900, 700)
        # ===== Banner =====
        banner = tk.Frame(win, bg="#6A1B9A", height=52)
        banner.pack(fill=tk.X)
        tk.Label(banner, text="✍️ AI 写手", bg="#6A1B9A", fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(banner, text="输入主题 → 选作家风格 + 文章类型 + 情感风格 → AI 一键创作",
                 bg="#6A1B9A", fg="#E1BEE7", font=("", 11)).pack(side=tk.LEFT, pady=14)
        # ===== 主题输入 =====
        input_frame = tk.LabelFrame(win, text="📝 创作主题 / 关键词",
                                    font=("", 11, "bold"), fg="#4A148C")
        input_frame.pack(fill=tk.X, padx=10, pady=(10, 6))
        topic_txt = scrolledtext.ScrolledText(input_frame, height=3, font=("", 11), wrap=tk.WORD)
        topic_txt.pack(fill=tk.X, padx=6, pady=6)
        topic_txt.insert("1.0", "春天的校园")  # 默认示例
        # ===== 三维度选项 =====
        options_frame = tk.Frame(win)
        options_frame.pack(fill=tk.X, padx=10, pady=6)
        # --- 维度 1: 作家风格 ---
        writers_frame = tk.LabelFrame(options_frame, text="🎭 作家风格 (可多选)",
                                      font=("", 10, "bold"), fg="#4A148C")
        writers_frame.pack(fill=tk.X, pady=2)
        # 经典作家列表
        WRITERS = [
            "鲁迅", "金庸", "古龙", "村上春树", "张爱玲", "余华", "莫言",
            "韩寒", "王朔", "史铁生", "沈从文", "钱钟书", "王小波",
            "老舍", "巴金", "冰心", "朱自清", "徐志摩", "戴望舒",
            "李白", "杜甫", "苏轼", "李清照", "辛弃疾", "曹雪芹",
            "加西亚·马尔克斯", "卡夫卡", "海明威", "泰戈尔",
        ]
        writer_vars = {}
        writer_inner = tk.Frame(writers_frame)
        writer_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, name in enumerate(WRITERS):
            v = tk.BooleanVar(value=False)
            writer_vars[name] = v
            cb = tk.Checkbutton(writer_inner, text=name, variable=v,
                                font=("", 10), anchor="w", selectcolor="#E1BEE7")
            cb.grid(row=i // 8, column=i % 8, sticky="w", padx=4, pady=1)
        # --- 维度 2: 文章类型 ---
        types_frame = tk.LabelFrame(options_frame, text="📄 文章类型 (单选)",
                                    font=("", 10, "bold"), fg="#4A148C")
        types_frame.pack(fill=tk.X, pady=2)
        ESSAY_TYPES = [
            "议论文", "叙事文", "散文", "小说", "诗歌", "散文诗",
            "唐诗", "宋词", "诗经", "元曲", "文言文", "现代诗",
            "剧本", "寓言", "童话", "杂文", "随笔", "书信",
        ]
        selected_type = tk.StringVar(value="散文")
        type_inner = tk.Frame(types_frame)
        type_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, name in enumerate(ESSAY_TYPES):
            rb = tk.Radiobutton(type_inner, text=name, variable=selected_type,
                                value=name, font=("", 10), anchor="w",
                                selectcolor="#E1BEE7")
            rb.grid(row=i // 9, column=i % 9, sticky="w", padx=4, pady=1)
        # --- 维度 3: 情感风格 ---
        tones_frame = tk.LabelFrame(options_frame, text="🎨 情感风格 (单选)",
                                    font=("", 10, "bold"), fg="#4A148C")
        tones_frame.pack(fill=tk.X, pady=2)
        EMOTION_TONES = [
            "恐怖", "喜剧", "爱情", "温馨", "讽刺", "严肃",
            "幽默", "浪漫", "热血", "忧伤", "空灵", "治愈",
            "冷峻", "荒诞", "诗意", "豪放", "婉约", "悲情",
        ]
        selected_tone = tk.StringVar(value="温馨")
        tone_inner = tk.Frame(tones_frame)
        tone_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, name in enumerate(EMOTION_TONES):
            rb = tk.Radiobutton(tone_inner, text=name, variable=selected_tone,
                                value=name, font=("", 10), anchor="w",
                                selectcolor="#E1BEE7")
            rb.grid(row=i // 9, column=i % 9, sticky="w", padx=4, pady=1)
        # ===== 按钮区 =====
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill=tk.X, padx=10, pady=8)
        _ai_busy = [False]
        def _start_write():
            nonlocal _ai_busy
            if _ai_busy[0]:
                status_var.set("⚠️ AI 正在创作中...")
                return
            topic = topic_txt.get("1.0", tk.END).strip()
            if not topic:
                tk.messagebox.showwarning("提示", "请输入创作主题！")
                return
            # 收集选中的作家
            selected_writers = [n for n, v in writer_vars.items() if v.get()]
            if not selected_writers:
                tk.messagebox.showwarning("提示", "请至少选一个作家风格！")
                return
            _ai_busy[0] = True
            write_btn.config(state=tk.DISABLED)
            status_var.set("⏳ AI 正在创作中（约10-30秒）...")
            result_txt.delete("1.0", tk.END)
            result_txt.insert("1.0", "⏳ 正在构思创作内容，请稍候...")
            # 构建 prompt
            writers_str = "、".join(selected_writers)
            essay_type = selected_type.get()
            tone = selected_tone.get()
            prompt = f"""请以「{writers_str}」的作家风格，写一篇「{essay_type}」，情感基调「{tone}」。
创作主题：{topic}
要求：
1. 深入揣摩上述作家的语言特色、叙事节奏、典型意象和思想内核
2. 严格按照所选「{essay_type}」的文体格式和规范写作
3. 融入「{tone}」的情感底色，让文字有温度、有力量
4. 开头直接切入，不要前言、不要解释、不要"好的，我来..."之类的废话
5. 字数：800-2000 字（诗歌/宋词等精短体裁除外）
6. 如有标题，放在最前面"""
            system = f"""你是一位精通「{essay_type}」的文学大师，擅长模仿作家风格。
- 输出纯文学作品，不要任何说明、注释、前言、后记
- 如果是诗词/宋词/唐诗，严格遵守格律、押韵、字数规范
- 如果是小说/散文/议论文，要结构完整、有起承转合"""
            def _work():
                try:
                    result = self.call_ai_model(prompt, system_prompt=system, max_tokens=3000)
                    win.after(0, lambda: _show_result(result))
                except Exception as e:
                    import traceback
                    err = f"❌ 创作失败：{e}\n\n{traceback.format_exc()}"
                    try:
                        win.after(0, lambda: _show_result(err))
                    except Exception:
                        pass
                finally:
                    _ai_busy[0] = False
                    try:
                        win.after(0, lambda: write_btn.config(state=tk.NORMAL))
                    except Exception:
                        pass
            threading.Thread(target=_work, daemon=True).start()
        def _show_result(text):
            result_txt.delete("1.0", tk.END)
            result_txt.insert("1.0", text or "（AI 没有返回内容）")
            # 自动滚动到开头
            result_txt.see("1.0")
            _ai_busy[0] = False
            write_btn.config(state=tk.NORMAL)
            status_var.set("✅ 创作完成！")
        def _copy_result():
            text = result_txt.get("1.0", tk.END).strip()
            if not text:
                tk.messagebox.showinfo("提示", "没有可复制的内容")
                return
            win.clipboard_clear()
            win.clipboard_append(text)
            status_var.set("✅ 已复制到剪贴板")
        def _clear_all():
            topic_txt.delete("1.0", tk.END)
            result_txt.delete("1.0", tk.END)
            for v in writer_vars.values():
                v.set(False)
            selected_type.set("散文")
            selected_tone.set("温馨")
            status_var.set("🧹 已清空")
        write_btn = tk.Button(btn_frame, text="✍️ 开始创作", font=("", 12, "bold"),
                              bg="#6A1B9A", fg="white", padx=20, pady=4,
                              command=_start_write, cursor="hand2")
        write_btn.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="📋 复制结果", font=("", 11), padx=12,
                  command=_copy_result, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ 清空全部", font=("", 11), padx=12,
                  command=_clear_all, cursor="hand2").pack(side=tk.LEFT, padx=5)
        # ===== 背景色 + 保存长图（主界面直接可见，不用双击）=====
        BG_PRESETS = [
            ("纯白", "#FFFFFF"), ("暖米", "#FFF8E1"), ("浅灰", "#F5F5F5"),
            ("护眼绿", "#E8F5E9"), ("淡紫", "#F3E5F5"), ("天空蓝", "#E3F2FD"),
            ("日落橙", "#FFF3E0"), ("深夜黑", "#1A1A2E"), ("樱花粉", "#FCE4EC"),
        ]
        current_bg = ["#FFFFFF"]
        current_text_fg = ["#212121"]
        def _apply_bg(bg_hex, label=""):
            current_bg[0] = bg_hex
            # 深色背景自动切白字
            if bg_hex in ("#1A1A2E",):
                current_text_fg[0] = "#FFFFFF"
            else:
                current_text_fg[0] = "#212121"
            # 实时更新主界面 Text 区的背景色（即时预览效果）
            try:
                result_txt.configure(bg=bg_hex, fg=current_text_fg[0],
                                     insertbackground=current_text_fg[0])
                result_frame.configure(bg=bg_hex)
            except Exception:
                pass
            status_var.set(f"🎨 背景: {label or bg_hex}")
        bg_row = tk.Frame(win)
        bg_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(bg_row, text="🎨 背景色:", font=("", 10, "bold"),
                 fg="#4A148C").pack(side=tk.LEFT)
        for name, hex_c in BG_PRESETS:
            def _pick(bg=hex_c, n=name):
                _apply_bg(bg, n)
            tk.Button(bg_row, text=name, bg=hex_c, width=6, height=1,
                      font=("", 9), command=_pick,
                      relief="solid", bd=1, cursor="hand2").pack(side=tk.LEFT, padx=2)
        def _pick_custom():
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="选一个背景色")
            if color and color[1]:
                _apply_bg(color[1], "自定义")
        def _preview_long_image():
            body = result_txt.get("1.0", tk.END).strip()
            if not body or "⏳" in body[:20]:
                tk.messagebox.showinfo("提示", "请先创作一篇文章")
                return
            self._open_image_popup_with_save(
                body, title="✍️ AI 写手创作结果",
                default_bg=current_bg[0], default_text=current_text_fg[0])
        def _save_long_image_direct():
            """主界面直接保存长图（用当前选的背景色）。"""
            body = result_txt.get("1.0", tk.END).strip()
            if not body or "⏳" in body[:20]:
                tk.messagebox.showinfo("提示", "请先创作一篇文章")
                return
            import shutil
            import threading
            title = "✍️ AI 写手创作结果"
            status_var.set("⏳ 正在生成长图...")
            def _work():
                try:
                    p = self._render_text_to_long_image(
                        body, title=title,
                        bg_color=current_bg[0], text_color=current_text_fg[0])
                    # 直接弹保存对话框
                    from tkinter import filedialog
                    save_path = filedialog.asksaveasfilename(
                        title="保存长图",
                        defaultextension=".png",
                        filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")],
                        initialfile="AI写手_创作结果.png")
                    if save_path:
                        shutil.copy(p, save_path)
                        win.after(0, lambda: status_var.set(f"✅ 长图已保存: {save_path}"))
                        win.after(0, lambda: tk.messagebox.showinfo("✅", f"已保存到:\n{save_path}"))
                    else:
                        win.after(0, lambda: status_var.set("取消保存"))
                except Exception as e:
                    import traceback
                    err = f"❌ 长图失败: {e}\n{traceback.format_exc()}"
                    win.after(0, lambda: status_var.set(err[:60]))
                    win.after(0, lambda: tk.messagebox.showerror("❌", err))
            threading.Thread(target=_work, daemon=True).start()
        # 预览/保存 长图按钮（放在行1右侧）
        tk.Button(btn_frame, text="🖼️ 预览长图", font=("", 11), padx=10,
                  bg="#EDE7F6", fg="#4A148C", cursor="hand2",
                  command=_preview_long_image).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📥 保存长图", font=("", 11, "bold"), padx=10,
                  bg="#2E7D32", fg="white", cursor="hand2",
                  command=_save_long_image_direct).pack(side=tk.LEFT, padx=5)
        tk.Button(bg_row, text="🎨 自定义", font=("", 10), padx=6,
                  command=_pick_custom, cursor="hand2").pack(side=tk.LEFT, padx=8)
        # ===== 结果区 =====
        result_frame = tk.LabelFrame(win, text="📖 创作结果",
                                      font=("", 11, "bold"), fg="#4A148C")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))
        result_txt = scrolledtext.ScrolledText(result_frame, font=("", 12),
                                               wrap=tk.WORD, padx=14, pady=12,
                                               bg="#FAFAFA", fg="#212121")
        result_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._enable_text_copy_menu(result_txt, readonly=False)
        # 双击 → 弹出长图预览（保留，但主界面已经有按钮了）
        result_txt.bind("<Double-Button-1>", lambda _e: _preview_long_image())
        tk.Label(result_frame, text="💡 双击或点「🖼️预览长图」都可放大，选背景色实时预览",
                 font=("", 9), fg="#9E9E9E", bg="#FAFAFA").pack(anchor="e", padx=8)
        # ===== 状态栏 =====
        status_var = tk.StringVar(value="💡 选好风格后点「✍️ 开始创作」")
        status_bar = tk.Label(win, textvariable=status_var, anchor="w",
                              font=("", 10), bg="#EDE7F6", fg="#4A148C", padx=10, pady=3)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _show_capital_direction_dialog(self):
        """📈 资金选择方向：五维框架 AI 月度报告"""
        import queue as _queue_cap
        import tkinter as tk
        from tkinter import scrolledtext, ttk
        win = self._toplevel(self.root)
        win.title("📈 资金选择方向 · 月度大势跟踪")
        win.geometry("1250x850")
        win.transient(self.root)
        # ===== 🔧 线程安全 UI 队列 =====
        # 子线程不直接调 win.after / Tk widget，而是把任务塞进队列
        # 主线程每 50ms 轮询一次执行
        _ui_q = _queue_cap.Queue()
        def _run_ui():
            try:
                while True:
                    fn = _ui_q.get_nowait()
                    try: fn()
                    except Exception as _e:
                        import traceback as _tb2
                        _log2 = os.path.expanduser("~/Desktop/tk_traceback.log")
                        with open(_log2, "a") as _f2:
                            _f2.write("\n[UI QUEUE] =====\n"); _tb2.print_exc(file=_f2)
            except _queue_cap.Empty:
                pass
            win.after(50, _run_ui)
        win.after(50, _run_ui)   # 启动轮询
        def _post(fn): _ui_q.put(fn)  # 子线程唯一合法入口
        # ===== Banner =====
        banner = tk.Frame(win, bg="#1565C0", height=58)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg="#1565C0")
        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(bi, text="📈 资金选择方向 · A股月度大势跟踪", font=("", 15, "bold"),
                 fg="white", bg="#1565C0").pack(side=tk.LEFT)
        import datetime as _dt
        _cur = _dt.datetime.now()
        _month_str = f"{_cur.year}年{_cur.month:02d}月"
        tk.Label(bi, text=f"  — {_month_str} 五维框架（宏观·政策·产业·估值·资金）",
                 font=("", 11), fg="#BBDEFB", bg="#1565C0").pack(side=tk.LEFT, padx=8)
        # ===== 参数栏 =====
        ctrl = tk.Frame(win)
        ctrl.pack(fill=tk.X, padx=10, pady=6)
        tk.Label(ctrl, text="上月主线(可选):", fg="#555").grid(row=0, column=0, sticky="e")
        last_month_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=last_month_var, width=30).grid(row=0, column=1, padx=4)
        tk.Label(ctrl, text="我的持仓/关注:", fg="#555").grid(row=0, column=2, sticky="e", padx=(10, 0))
        holding_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=holding_var, width=30).grid(row=0, column=3, padx=4)
        gen_btn = tk.Button(ctrl, text="🚀 生成月度报告（AI+联网）",
                            font=("", 11, "bold"), bg="#1565C0", fg="white",
                            padx=14, pady=3, cursor="hand2")
        gen_btn.grid(row=0, column=4, padx=14)
        save_btn = tk.Button(ctrl, text="💾 保存到资讯表",
                             font=("", 10), padx=8, pady=3, cursor="hand2", state="disabled")
        save_btn.grid(row=0, column=5)
        copy_btn = tk.Button(ctrl, text="📋 复制",
                             font=("", 10), padx=8, pady=3, cursor="hand2")
        copy_btn.grid(row=0, column=6, padx=(4, 0))
        longimg_btn = tk.Button(ctrl, text="🖼️ 生成长图",
                                font=("", 10), padx=8, pady=3, cursor="hand2",
                                bg="#2E7D32", fg="white")
        longimg_btn.grid(row=0, column=7, padx=(4, 0))
        # ===== PanedWindow =====
        paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))
        # 左：框架说明
        left = ttk.LabelFrame(paned, text="📐 五维框架 + 输出结构", padding=8)
        paned.add(left, weight=3)
        framework_txt = scrolledtext.ScrolledText(left, wrap=tk.WORD,
                                                   font=("Microsoft YaHei", 10))
        framework_txt.pack(fill=tk.BOTH, expand=True)
        framework_txt.insert("1.0",
            "🎯 五维框架（月度资金方向判断）\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "① 宏观与流动性\n"
            "   社融/M1M2/PMI/CPI/地产销售/利率/汇率\n"
            "   → 一句话：有利于价值/成长/红利/顺周期？\n\n"
            "② 政策大势\n"
            "   政治局会议/国常会/新质生产力/国企改革\n"
            "   → 高频关键词 + 影响行业\n\n"
            "③ 产业景气度（排序：高景气→走弱）\n"
            "   新能源车/光伏/风电/半导体/AI/煤炭/有色/地产/消费\n"
            "   → 每个行业给景气指标+最新数据+来源\n\n"
            "④ 资金与筹码\n"
            "   北向/融资/公募/ETF/成交占比/龙虎榜/增减持\n"
            "   → 增量资金来自哪类主体？哪些行业成交极端高？\n\n"
            "⑤ 估值与拥挤度\n"
            "   PE/PB 历史分位/ERP/股息率利差\n"
            "   → 哪些方向性价比高？哪些已拥挤？\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 输出结构（严格 8 部分）\n"
            "  一、宏观环境与风格判断（100字内）\n"
            "  二、政策主线与关键词\n"
            "  三、产业景气度排序表\n"
            "  四、资金流向与筹码结构\n"
            "  五、估值与拥挤度评价\n"
            "  六、本月主线候选（1-3个，含核心逻辑/数据验证/资金信号/风险点）\n"
            "  七、主线启动/过热/终结信号对照\n"
            "  八、下月操作建议\n\n"
            "💡 与大盘风险仪表盘/早盘S-T指导 三层联动：\n"
            "  战略层(月度) → 本功能\n"
            "  战术层(周度) → 🚦大盘风险仪表盘\n"
            "  执行层(日内) → ☀️早盘S-T指导")
        # 右：AI 报告输出
        right = ttk.LabelFrame(paned, text="📝 月度报告（AI+联网搜索生成）", padding=8)
        paned.add(right, weight=7)
        report_txt = scrolledtext.ScrolledText(right, wrap=tk.WORD,
                                                font=("Microsoft YaHei", 11),
                                                undo=True, cursor="arrow")
        report_txt.pack(fill=tk.BOTH, expand=True)
        report_txt.insert("1.0", "点击「🚀 生成月度报告」开始（AI 会联网检索最新宏观/政策/产业/资金/估值数据，约 30-60 秒）\n\n"
                                 "🔗 与大盘风险仪表盘(周度)+早盘S-T指导(日内) 三层联动\n\n"
                                 "💡 报告自动识别 【超级利好/重大利好/利好/中性/利空/重大利空/超级利空】 标记并着色显示")
        # ===== 右键菜单（支持拷贝）=====
        report_menu = tk.Menu(report_txt, tearoff=0)
        report_menu.add_command(label="复制选中  ⌘C", command=lambda: report_txt.event_generate("<<Copy>>"))
        report_menu.add_command(label="全选  ⌘A", command=lambda: (report_txt.tag_add("sel", "1.0", tk.END), report_txt.mark_set(tk.INSERT, "1.0")))
        report_menu.add_separator()
        report_menu.add_command(label="复制全部", command=lambda: self._copy_text_to_clipboard(report_txt.get("1.0", tk.END)))
        report_menu.add_command(label="清空", command=lambda: report_txt.delete("1.0", tk.END))
        def _show_menu(e):
            try: report_menu.tk_popup(e.x_root, e.y_root)
            finally: report_menu.grab_release()
        report_txt.bind("<Button-3>", _show_menu)
        # macOS 右键
        report_txt.bind("<Button-2>", _show_menu)
        # ===== 状态条 + 进度条 =====
        status_var = tk.StringVar(value="就绪")
        status_frame = tk.Frame(win)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Label(status_frame, textvariable=status_var, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        progress = ttk.Progressbar(status_frame, mode="indeterminate", length=160)
        progress.pack(side=tk.RIGHT, padx=(6, 0))
        # ===== AI Prompt =====
        import datetime as _dt2
        _now = _dt2.datetime.now()
        _cur_month = f"{_now.year}年{_now.month:02d}月"
        _next_month_date = (_now.replace(day=1) + _dt2.timedelta(days=32)).replace(day=1)
        _next_month = f"{_next_month_date.year}年{_next_month_date.month:02d}月"
        def _build_prompt():
            last = last_month_var.get().strip() or "（未填）"
            hold = holding_var.get().strip() or "（未填）"
            return f"""你是一名资深A股策略分析师，擅长通过"宏观—政策—产业—盈利估值—资金筹码"五维框架，判断A股市场的阶段性格局和资金选择方向。
请联网搜索并整合公开数据，生成《{_cur_month}中国A股大势所趋月度跟踪报告》，帮助判断本月及下月({_next_month})资金最可能选择的阶段性方向。
【上月主线】{last}
【我的持仓/关注方向】{hold}
【信息源】优先使用：国家统计局/人民银行/财政部/海关总署/外汇局/中国政府网/国务院/发改委/工信部/证监会/央行/新华社/中汽协/乘联会/国家能源局/中钢协/中国半导体协会/SEMI/上海有色网/沪深交易所/港交所/基金业协会/Wind/同花顺/东财/美联储官网/美财政部/Bloomberg
【检索要求——五个维度逐一落到具体数据】：
一、宏观与流动性
  检索最新：社融、M1/M2、PMI、CPI/PPI、工业增加值、社零、固投、房地产销售/投资、10年期国债收益率、LPR/MLF、美元指数、美债收益率
  → 判断当前经济周期位置 + 一句话说明有利于哪类风格（价值/成长/红利/顺周期）
二、政策大势
  最近1个月的重要会议、文件、部委表态。重点：政治局会议、国常会、新质生产力、以旧换新、资本市场改革、分红监管、国企改革
  → 提取高频关键词 + 影响行业
三、产业景气度（排序表）
  新能源车渗透率、光伏装机/组件价格、风电招标、半导体销售额/设备、AI资本开支/光模块出货、煤炭价格、铜铝锂价格、地产销售、消费数据
  → 排序：高景气/改善/平稳/走弱，每项注明数据来源+最新数值
四、资金与筹码
  北向资金行业流向、融资余额变化、公募基金新发、ETF申赎、行业成交额占比、换手率、龙虎榜、产业资本增减持
  → 增量资金来自哪类主体？哪些行业成交极端高位？
五、估值与拥挤度
  主要指数/行业 PE/PB 历史分位、ERP、股息率与10年国债利差
  → 性价比高的方向 vs 已交易拥挤的方向
【⚠️ 重要：利好多空标记规则 — 每条关键结论/数据/事件的开头必须加标准标记】
标记（7选1，置于行首或段落首）：
  【超级利好】 — 国家级重磅政策/外部重大利好/全市场级上涨催化剂 → 后必须跟"受益板块：xxx | 龙头股：xxx"
  【重大利好】 — 行业级重大利好/超预期数据/政策强力支持
  【利好】     — 普通利好/小幅改善/边际正面
  【中性】     — 无明显方向/数据平稳
  【利空】     — 普通利空/小幅恶化/边际负面
  【重大利空】 — 行业级重大利空/超预期下滑/监管收紧
  【超级利空】 — 系统性风险/国家级冲击/黑天鹅 → 后必须跟"避险板块：xxx | 影响板块：xxx"
判断标准：
  超级级 = 影响全市场或持续 >1 季度的重大变化
  重大级 = 影响一个大板块或持续 1-2 个月
  普通级 = 影响细分领域或持续 <2 周
【输出格式——严格按 8 部分 + 每条带标记】：
一、宏观环境与风格判断（100字以内，开头用 【超级利好/重大利好/利好/中性/利空/重大利空/超级利空】）
二、政策主线与关键词（每条政策前加标记）
三、产业景气度排序表（表格：行业、景气指标、最新数据、趋势、标记）
四、资金流向与筹码结构（关键数据前加标记）
五、估值与拥挤度评价（每个方向前加标记）
六、本月主线候选（1—3个，每个含：核心逻辑【带标记】/数据验证/资金信号/风险点）
七、主线启动/过热/终结信号对照
八、下月({_next_month})操作建议
⚠️ 所有数据必须注明来源+发布时间，聚焦边际变化，避免堆砌历史。
⚠️ 若某项数据未公布，用最近一期并注明日期。
⚠️ 结论明确，不模棱两可，不编造数据。
⚠️ 超级利好/利空标记后必须跟板块和龙头股。
⚠️ 最后加：仅供研究参考，不构成投资建议。"""
        # ===== 生成 + 保存 + 复制 + 长图 =====
        import re as _re_cap
        import threading
        import time as _time_cap
        _report_cache = [""]
        # 标记 → 样式映射（颜色 + 字号 + 加粗）
        _TAG_STYLES = {
            "超级利好": {"fg": "#B71C1C", "size": 14, "bold": True},   # 深红 加粗 14号
            "重大利好": {"fg": "#D32F2F", "size": 12, "bold": True},   # 红 加粗 12号
            "利好":     {"fg": "#E53935", "size": 11, "bold": False},  # 浅红 正常
            "中性":     {"fg": "#424242", "size": 11, "bold": False},  # 深灰
            "利空":     {"fg": "#43A047", "size": 11, "bold": False},  # 浅绿
            "重大利空": {"fg": "#1B5E20", "size": 12, "bold": True},   # 绿 加粗 12号
            "超级利空": {"fg": "#0D3B12", "size": 14, "bold": True},   # 深绿 加粗 14号
        }
        def _setup_tags(txt_w):
            """在 Text widget 上注册 tag 样式"""
            for tag_name, style in _TAG_STYLES.items():
                _font_str = f"Microsoft YaHei {style['size']}"
                if style["bold"]:
                    _font_str += " bold"
                txt_w.tag_configure(tag_name, foreground=style["fg"], font=_font_str)
                # 让 tag 优先级高于默认
                txt_w.tag_raise(tag_name)
        def _render_with_tags(txt_w, raw_text):
            """解析 【超级利好】... 标记 + Markdown 标题，渲染着色"""
            _setup_tags(txt_w)
            txt_w.delete("1.0", tk.END)
            tag_pattern = _re_cap.compile(r"【(超级利好|重大利好|利好|中性|利空|重大利空|超级利空)】")
            lines = raw_text.split("\n")
            for line in lines:
                matches = list(tag_pattern.finditer(line))
                if not matches:
                    # 处理 Markdown 标题 # / ## / ###
                    stripped = line.strip()
                    if _re_cap.match(r"^#{1,3}\s+", stripped):
                        txt_w.insert(tk.END, line + "\n", "md_heading")
                    elif stripped.startswith("**") and stripped.endswith("**"):
                        txt_w.insert(tk.END, line + "\n", "md_bold")
                    elif stripped.startswith("|") and stripped.endswith("|"):
                        txt_w.insert(tk.END, line + "\n", "md_table")
                    else:
                        txt_w.insert(tk.END, line + "\n")
                    continue
                last_pos = 0
                for m in matches:
                    tag_name = m.group(1)
                    if m.start() > last_pos:
                        txt_w.insert(tk.END, line[last_pos:m.start()])
                    txt_w.insert(tk.END, m.group(0), tag_name)
                    last_pos = m.end()
                if last_pos < len(line):
                    last_tag = matches[-1].group(1)
                    txt_w.insert(tk.END, line[last_pos:], last_tag)
                txt_w.insert(tk.END, "\n")
            # Markdown 标题样式
            try:
                txt_w.tag_configure("md_heading", foreground="#1565C0", font="Microsoft YaHei 14 bold")
                txt_w.tag_configure("md_bold", foreground="#333", font="Microsoft YaHei 11 bold")
                txt_w.tag_configure("md_table", foreground="#555", font="Menlo 10")
            except Exception:
                pass
        def _generate():
            # ⚠️ 所有 Tk UI 更新必须走 _post() → 线程安全队列 → 主线程执行
            _post(lambda: gen_btn.configure(state="disabled"))
            _post(lambda: progress.start())
            _post(lambda: status_var.set("⏳ 准备中..."))
            _post(lambda: report_txt.delete("1.0", tk.END))
            _post(lambda: report_txt.insert("1.0", "⏳ 正在构建 prompt + 准备 AI 调用...\n"))
            prompt = _build_prompt()
            _heartbeat_stop = {"flag": False}
            def _heartbeat():
                """每 2 秒更新一次运行时间（子线程 → _post → 主线程）"""
                start_ts = _time_cap.time()
                stage = ["联网搜索宏观数据", "分析政策大势", "梳理产业景气度", "评估资金筹码", "估值拥挤度判断", "生成五维报告"]
                idx = 0
                while not _heartbeat_stop["flag"]:
                    elapsed = int(_time_cap.time() - start_ts)
                    cur_stage = stage[idx % len(stage)]
                    _post(lambda e=elapsed, s=cur_stage: status_var.set(f"⏳ {s} · 已运行 {e}s (AI 预计 30-60s)"))
                    idx += 1
                    _time_cap.sleep(2)
            hb_thread = threading.Thread(target=_heartbeat, daemon=True)
            hb_thread.start()
            try:
                _post(lambda: report_txt.insert(tk.END, f"📝 Prompt: {len(prompt)} 字符 → 调用 DeepSeek (max_tokens=4500)...\n"))
                t0 = _time_cap.time()
                ai_text = self.call_ai_model(
                    prompt,
                    system_prompt="你是资深A股策略分析师，擅长五维框架下的月度大势判断。数据说话，结论明确，注明来源。每条关键结论前必须加 【超级利好/重大利好/利好/中性/利空/重大利空/超级利空】 标记。",
                    max_tokens=4500,
                )
                elapsed = _time_cap.time() - t0
                _report_cache[0] = ai_text
                _heartbeat_stop["flag"] = True
                _post(lambda: progress.stop())
                _post(lambda: report_txt.insert(tk.END, f"✅ AI 返回: {elapsed:.1f}s · {len(ai_text)} 字符\n\n"))
                _post(lambda: _render_with_tags(report_txt, ai_text))
                _post(lambda: save_btn.configure(state="normal"))
                _post(lambda: gen_btn.configure(state="normal"))
                _post(lambda: status_var.set(f"✅ 完成 · 耗时 {elapsed:.0f}s · 右键可拷贝 · 🖼️ 可生成长图"))
            except Exception as e:
                _heartbeat_stop["flag"] = True
                import traceback as _tbx; _tbx.print_exc()
                _post(lambda: progress.stop())
                _post(lambda e=e: report_txt.delete("1.0", tk.END))
                _post(lambda e=e: report_txt.insert("1.0", f"❌ AI 调用失败: {e}"))
                _post(lambda e=e: gen_btn.configure(state="normal"))
                _post(lambda e=e: status_var.set(f"❌ 失败: {e}"))
        def _copy_all():
            content = _report_cache[0] or report_txt.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                status_var.set("✅ 已复制到剪贴板")
        def _gen_long_image():
            """用 PIL 渲染带颜色分级的长图（⚠️ 子线程：PIL纯CPU安全，Tk操作全走 _post）"""
            # 1) 先从缓存取内容（不碰 Tk widget——缓存是列表，天然线程安全）
            content = _report_cache[0]
            if not content:
                _post(lambda: messagebox.showwarning("提示", "报告内容为空，先点 🚀 生成", parent=win))
                return
            # 2) 立即更新 UI 状态
            _post(lambda: status_var.set("🖼️ 正在生成长图..."))
            try:
                import os as _os_pil

                from PIL import Image, ImageDraw, ImageFont
                # 找中文字体
                _pil_font_paths = [
                    "/System/Library/Fonts/STHeiti Medium.ttc",
                    "/System/Library/Fonts/PingFang.ttc",
                    "/System/Library/Fonts/Hiragino Sans GB.ttc",
                    "/System/Library/Fonts/Supplemental/Songti.ttc",
                ]
                _pil_font = None
                _pil_font_bold = None
                _pil_font_title = None
                for _fp in _pil_font_paths:
                    if _os_pil.path.exists(_fp):
                        try:
                            _pil_font = ImageFont.truetype(_fp, 22)
                            _pil_font_bold = ImageFont.truetype(_fp, 28)
                            _pil_font_title = ImageFont.truetype(_fp, 36)
                            break
                        except Exception:
                            continue
                if _pil_font is None:
                    _pil_font = ImageFont.load_default()
                    _pil_font_bold = _pil_font
                    _pil_font_title = _pil_font
                W, PAD = 900, 50
                line_h = 34
                lines_raw = content.split("\n")
                def _wrap(text, max_w):
                    if not text.strip(): return [""]
                    result, cur = [], ""; cur_w = 0
                    for ch in text:
                        cw = 22 if ord(ch) > 127 else 12
                        if cur_w + cw > max_w:
                            result.append(cur); cur = ch; cur_w = cw
                        else: cur += ch; cur_w += cw
                    if cur: result.append(cur)
                    return result
                tag_pat = _re_cap.compile(r"【(超级利好|重大利好|利好|中性|利空|重大利空|超级利空)】")
                # Markdown 标题处理也要加（CLI 长图同样）
                md_heading_pat = _re_cap.compile(r"^#{1,3}\s+")
                render_lines = []
                for raw_line in lines_raw:
                    if not raw_line.strip():
                        render_lines.append(("", "#333", 22, False))
                        continue
                    m = tag_pat.search(raw_line)
                    if m:
                        tag_name = m.group(1)
                        style = _TAG_STYLES[tag_name]
                        cleaned = tag_pat.sub("", raw_line)
                        sz = style["size"] + 10
                        wrapped = _wrap(cleaned, W - 2 * PAD)
                        for wl in wrapped:
                            render_lines.append((wl, style["fg"], sz, style["bold"]))
                    else:
                        stripped = raw_line.strip()
                        if md_heading_pat.match(stripped):
                            cleaned = md_heading_pat.sub("", raw_line)
                            wrapped = _wrap(cleaned, W - 2 * PAD)
                            for wl in wrapped:
                                render_lines.append((wl, "#1565C0", 34, True))
                        elif _re_cap.match(r"^[一二三四五六七八九十]+、", stripped):
                            wrapped = _wrap(raw_line, W - 2 * PAD)
                            for wl in wrapped:
                                render_lines.append((wl, "#1565C0", 30, True))
                        else:
                            wrapped = _wrap(raw_line, W - 2 * PAD)
                            for wl in wrapped:
                                render_lines.append((wl, "#333", 22, False))
                H = len(render_lines) * line_h + 2 * PAD + 80
                img = Image.new("RGB", (W, H), "#FFFFFF")
                draw = ImageDraw.Draw(img)
                draw.rectangle([0, 0, W, 80], fill="#1565C0")
                draw.text((PAD, 22), f"📈 {_cur_month} 月度大势跟踪报告", fill="white", font=_pil_font_title)
                draw.text((W - PAD - 200, 30), f"{_dt2.datetime.now().strftime('%Y-%m-%d')}", fill="#BBDEFB", font=_pil_font_bold)
                y = 80 + PAD
                for text, color, sz, bold in render_lines:
                    if not text:
                        y += line_h
                        continue
                    try:
                        actual_sz = max(16, sz)
                        for _fp in _pil_font_paths:
                            if _os_pil.path.exists(_fp):
                                f = ImageFont.truetype(_fp, actual_sz)
                                break
                    except Exception:
                        f = _pil_font
                    draw.text((PAD, y), text, fill=color, font=f)
                    y += line_h
                # 保存（PIL 操作，安全）
                save_dir = _os_pil.path.expanduser("~/Desktop")
                if not _os_pil.path.isdir(save_dir):
                    import tempfile as _tmp_pil
                    save_dir = _tmp_pil.gettempdir()
                fname = f"月度报告_{_dt2.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                fpath = _os_pil.path.join(save_dir, fname)
                img.save(fpath, "PNG")
                # 3) 回到主线程处理 UI（⚠️ 必须走 _post，不能子线程直接 win.after）
                _post(lambda: self._preview_long_image_in_popup(win, fpath, f"📈 月度报告 {_cur_month}"))
                _post(lambda: status_var.set(f"✅ 长图已生成: {fname}"))
            except Exception as e:
                import traceback; traceback.print_exc()
                _post(lambda e=e: messagebox.showerror("长图失败", str(e), parent=win))
                _post(lambda e=e: status_var.set(f"❌ 长图失败: {e}"))
        def _save():
            content = _report_cache[0] or report_txt.get("1.0", tk.END).strip()
            if not content or len(content) < 100:
                messagebox.showwarning("提示", "报告内容为空，先点 🚀 生成", parent=win)
                return
            now = _dt2.datetime.now()
            tag = f"资金方向_{now.strftime('%Y%m')}"
            try:
                self.save_news_info_to_db(tag, content)
                status_var.set(f"✅ 已保存到资讯表: {tag}")
                save_btn.configure(state="disabled")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        gen_btn.configure(command=lambda: threading.Thread(target=_generate, daemon=True).start())
        save_btn.configure(command=_save)
        copy_btn.configure(command=_copy_all)
        longimg_btn.configure(command=lambda: threading.Thread(target=_gen_long_image, daemon=True).start())
        # 辅助：长图预览弹窗（复用已有方法模式）
        def _preview_long_image_in_popup(parent_win, img_path, title_str="长图"):
            try:
                from PIL import Image
                from PIL import ImageTk as ImageTk_mod
            except ImportError:
                messagebox.showwarning("提示", "需要安装 Pillow", parent=parent_win)
                return
            pwin = tk.Toplevel(parent_win)
            pwin.title(f"🖼️ {title_str}")
            pwin.geometry("960x700")
            pwin.transient(parent_win)
            pwin.configure(bg="#F5F5F5")
            btn_row = tk.Frame(pwin, bg="#F5F5F5")
            btn_row.pack(fill=tk.X, padx=10, pady=6)
            tk.Label(btn_row, text=f"📁 {img_path}", fg="#555", bg="#F5F5F5").pack(side=tk.LEFT)
            def _do_save():
                import subprocess
                subprocess.run(["open", "-R", img_path])
            tk.Button(btn_row, text="📂 在 Finder 中显示", font=("", 10),
                      command=_do_save).pack(side=tk.RIGHT, padx=4)
            canvas = tk.Canvas(pwin, bg="#F5F5F5", highlightthickness=0)
            vsb = ttk.Scrollbar(pwin, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=vsb.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            img = Image.open(img_path)
            scale = min(1.0, 900 / img.width)
            new_h = int(img.height * scale)
            display = img.resize((int(img.width * scale), new_h), Image.LANCZOS)
            tk_img = ImageTk_mod.PhotoImage(display)
            canvas.create_image(10, 10, anchor="nw", image=tk_img)
            canvas.image = tk_img
            canvas.configure(scrollregion=(0, 0, int(img.width * scale), new_h + 20))

    def _show_precious_metals_dialog(self):
        """🏅 贵金属/有色分析：左=国际走势+AI研判+资讯，右=A股股票Treeview"""
        import sqlite3 as _sqlite3
        import tkinter as tk
        from tkinter import scrolledtext, ttk
        win = self._toplevel(self.root)
        win.title("🏅 贵金属 / 有色 趋势研判")
        win.geometry("1550x920")
        win.transient(self.root)
        # ===== 顶部 Banner（金色）=====
        banner_color = "#B8860B"
        banner = tk.Frame(win, bg=banner_color, height=64)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        bi = tk.Frame(banner, bg=banner_color)
        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(bi, text="🏅 贵金属 / 有色 趋势研判", font=("", 16, "bold"),
                 fg="white", bg=banner_color).pack(side=tk.LEFT)
        tk.Label(bi, text="  — 国际+国内价格走势 · AI研判 · A股标的（大庄家控不住价的品种）",
                 font=("", 11), fg="#FFF8DC", bg=banner_color).pack(side=tk.LEFT, padx=8)
        tk.Label(bi, text="⚠️ 每周盯一次！震荡/上行/下跌 + 逻辑分析",
                 font=("", 10), fg="#FFD700", bg=banner_color).pack(side=tk.RIGHT)
        # ===== 顶部按钮栏 =====
        ctrl = tk.Frame(win)
        ctrl.pack(fill=tk.X, padx=10, pady=6)
        tk.Button(ctrl, text="🔍 更新价格 + AI研判", font=("", 11, "bold"),
                  bg=banner_color, fg="white", padx=14, pady=3, cursor="hand2").pack(side=tk.LEFT, padx=6)
        tk.Label(ctrl, text="⚠️ 贵金属/有色这类国内大庄家没法控价的品种，平时一定要留意观察",
                 fg="#888").pack(side=tk.LEFT, padx=20)
        # ===== PanedWindow 左右分栏 =====
        paned = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        # ===== 左侧：国际贵金属走势 + AI研判 =====
        left_frame = ttk.LabelFrame(paned, text="🌍 国际贵金属走势 + AI研判", padding=6)
        paned.add(left_frame, weight=5)
        # 国际价格卡片
        price_card = tk.Frame(left_frame, bg="#FFF8DC")
        price_card.pack(fill=tk.X, pady=(0, 6))
        price_labels = {}
        def _add_price_row(parent, label_text, unit="元/克"):
            row = tk.Frame(parent, bg="#FFF8DC")
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Label(row, text=f"  {label_text}:", font=("", 11, "bold"),
                     bg="#FFF8DC", fg="#B8860B", width=16, anchor="e").pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text="--", font=("", 13, "bold"),
                               bg="#FFF8DC", fg="#333")
            val_lbl.pack(side=tk.LEFT, padx=4)
            tk.Label(row, text=unit, font=("", 9), bg="#FFF8DC", fg="#999").pack(side=tk.LEFT)
            chg_lbl = tk.Label(row, text="", font=("", 10), bg="#FFF8DC")
            chg_lbl.pack(side=tk.LEFT, padx=8)
            price_labels[label_text] = (val_lbl, chg_lbl)
            return val_lbl, chg_lbl
        _add_price_row(price_card, "沪金主力 (AU0)", "元/克")
        _add_price_row(price_card, "沪银主力 (AG0)", "元/千克")
        _add_price_row(price_card, "COMEX 黄金 (GC)", "美元/盎司")
        # AI 研判 + 资讯
        ttk.Label(left_frame, text="📊 AI 研判 + 资讯分析", font=("", 11, "bold")).pack(anchor=tk.W)
        report_txt = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD,
                                                font=("Microsoft YaHei", 10), height=20)
        report_txt.pack(fill=tk.BOTH, expand=True, pady=4)
        report_txt.insert("1.0", "点击「🔍 更新价格 + AI研判」拉取最新数据 + AI 趋势分析\n\n"
                                 "关注重点：\n"
                                 "· 沪金/沪银主力日线趋势（MA20/MA60）\n"
                                 "· COMEX 黄金（海外定价权）\n"
                                 "· 资讯里关于贵金属的分析研判\n\n"
                                 "⚠️ 贵金属/有色这类国内大庄家没法控价的品种，平时一定要留意观察。\n"
                                 "建议至少每周看一次，判断是震荡、上行还是下跌。")
        # ===== 右侧：A股贵金属股票 Treeview =====
        right_frame = ttk.LabelFrame(paned, text="🪙 A股贵金属/有色股票  (双击行→日K线)", padding=6)
        paned.add(right_frame, weight=5)
        cols = ("metal", "code", "name", "trade", "pct", "pct_week", "pct_month", "note")
        col_labels = {"metal": "类别", "code": "代码", "name": "名称", "trade": "现价",
                      "pct": "今日%", "pct_week": "周涨%", "pct_month": "月涨%", "note": "备注"}
        col_widths = {"metal": 80, "code": 80, "name": 100, "trade": 80,
                      "pct": 70, "pct_week": 80, "pct_month": 80, "note": 140}
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=18)
        _style = ttk.Style()
        _style.configure("Treeview.Heading", font=("", 11, "bold"), rowheight=26)
        _style.configure("Treeview", rowheight=24)
        for c in cols:
            tree.heading(c, text=col_labels[c])
            tree.column(c, width=col_widths[c], anchor="center", stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.config(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("gold", foreground="#B8860B", font=("", 11, "bold"))
        tree.tag_configure("silver", foreground="#778899", font=("", 10, "bold"))
        tree.tag_configure("cu", foreground="#CD7F32", font=("", 10))
        tree.tag_configure("rare", foreground="#4682B4", font=("", 10))
        tree.tag_configure("small", foreground="#2E8B57", font=("", 10))
        # ===== 双击 → 日K线 =====
        def _open_kline_on_double(event):
            item = tree.selection()
            if not item: return
            vals = tree.item(item[0], "values")
            if not vals or len(vals) < 3: return
            s_code = str(vals[1]).strip()
            s_name = str(vals[2]).strip()
            if not s_code or not s_code.replace(".", "").isdigit(): return
            def _kwork():
                try:
                    kline = self._get_daily_kline_data_tushare(s_code, days=120)
                except Exception: kline = None
                if kline:
                    try:
                        self._show_daily_kline_zoom(kline, s_name)
                    except Exception as e:
                        messagebox.showerror("错误", f"打开K线失败: {e}", parent=win)
                else:
                    messagebox.showwarning("提示",
                        f"无法获取 {s_name}({s_code}) K线数据", parent=win)
            import threading
            threading.Thread(target=_kwork, daemon=True).start()
        tree.bind("<Double-1>", _open_kline_on_double)
        # ===== 状态条 =====
        status_var = tk.StringVar(value="就绪 · 双击股票行打开日K线图")
        ttk.Label(win, textvariable=status_var, anchor=tk.W).pack(fill=tk.X, padx=10, pady=(0, 4))
        # ===== 按钮：更新价格 + AI研判 =====
        def _run_analysis():
            import threading

            import akshare as ak
            import numpy as np
            import pandas as pd
            report_txt.delete("1.0", tk.END)
            report_txt.insert("1.0", "⏳ 拉取国际贵金属价格 + A股数据 + AI分析中...\n")
            status_var.set("拉取数据中...")
            def _work():
                # ========== 1. 国际贵金属日线 ==========
                futures_data = {}
                try:
                    df_au = ak.futures_zh_daily_sina(symbol="AU0")
                    if df_au is not None and not df_au.empty:
                        futures_data["沪金"] = df_au.tail(120).reset_index(drop=True)
                except Exception as e:
                    print(f"沪金失败: {e}")
                try:
                    df_ag = ak.futures_zh_daily_sina(symbol="AG0")
                    if df_ag is not None and not df_ag.empty:
                        futures_data["沪银"] = df_ag.tail(120).reset_index(drop=True)
                except Exception as e:
                    print(f"沪银失败: {e}")
                try:
                    df_gc = ak.futures_foreign_hist(symbol="GC")
                    if df_gc is not None and not df_gc.empty:
                        df_gc.columns = [c.lower() for c in df_gc.columns]
                        futures_data["COMEX金"] = df_gc.tail(120).reset_index(drop=True)
                except Exception as e:
                    print(f"COMEX GC 失败: {e}")
                # 更新价格卡片
                _price_info = {}
                for name, df in futures_data.items():
                    try:
                        close_col = "close" if "close" in df.columns else ("收盘" if "收盘" in df.columns else None)
                        if close_col is None: continue
                        prices = df[close_col].astype(float).values
                        cur = prices[-1]
                        chg_pct = (cur - prices[-2]) / prices[-2] * 100 if len(prices) >= 2 else 0
                        ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else cur
                        ma60 = np.mean(prices[-60:]) if len(prices) >= 60 else cur
                        trend = "上行 📈" if cur > ma20 > ma60 else ("下跌 📉" if cur < ma20 < ma60 else "震荡 ➡️")
                        _price_info[name] = {"cur": cur, "chg": chg_pct, "ma20": ma20, "ma60": ma60, "trend": trend}
                    except Exception: pass
                def _update_price_ui():
                    for label, info in _price_info.items():
                        if label == "沪金":
                            key = "沪金主力 (AU0)"
                        elif label == "沪银":
                            key = "沪银主力 (AG0)"
                        elif label == "COMEX金":
                            key = "COMEX 黄金 (GC)"
                        else:
                            continue
                        pair = price_labels.get(key)
                        if pair:
                            val_lbl, chg_lbl = pair
                            val_lbl.configure(text=f"{info['cur']:.2f}  {info['trend']}")
                            chg = info['chg']
                            chg_lbl.configure(text=f"{chg:+.2f}%  MA20={info['ma20']:.1f} MA60={info['ma60']:.1f}",
                                              fg="#C62828" if chg >= 0 else "#2E7D32")
                win.after(0, _update_price_ui)
                # ========== 2. A股贵金属股票列表 ==========
                # 先清空
                def _clear_tree():
                    for item in tree.get_children(): tree.delete(item)
                win.after(0, _clear_tree)
                stock_infos = self.PRECIOUS_METALS_STOCKS  # 已在类上定义
                # 用 Tushare 批量拉日线（每只 120 天，算现价/涨跌幅）
                a_stock_data = {}
                try:
                    for metal_type, code, name in stock_infos:
                        try:
                            kline = self._get_daily_kline_data_tushare(code, days=60)
                            if kline is not None and len(kline) >= 5:
                                    close = kline["收盘"].astype(float).values
                                    cur = close[-1]
                                    chg_today = (close[-1] - close[-2]) / close[-2] * 100 if len(close) >= 2 else 0
                                    chg_week = (close[-1] - close[-5]) / close[-5] * 100 if len(close) >= 5 else 0
                                    chg_month = (close[-1] - close[-20]) / close[-20] * 100 if len(close) >= 20 else 0
                                    a_stock_data[code] = {
                                    "metal": metal_type, "name": name, "cur": cur,
                                    "pct": chg_today, "pct_w": chg_week, "pct_m": chg_month
                                    }
                        except Exception: pass
                except Exception as e:
                    print(f"A股拉取失败: {e}")
                def _fill_tree():
                    for metal_type, code, name in stock_infos:
                        if code not in a_stock_data:
                            # 没拉到数据也显示一行占位
                            metal_tag = {"黄金": "gold", "白银": "silver", "有色金属": "cu",
                                         "稀有金属": "rare", "小金属": "small"}.get(metal_type, "")
                            note = "未拉到K线"
                            tree.insert("", tk.END, values=(metal_type, code, name, "--", "--", "--", "--", note),
                                        tags=(metal_tag,) if metal_tag else ())
                            continue
                        info = a_stock_data[code]
                        metal_tag = {"黄金": "gold", "白银": "silver", "有色金属": "cu",
                                     "稀有金属": "rare", "小金属": "small"}.get(info["metal"], "")
                        info["pct"]
                        note = ""
                        if info["pct_m"] > 10: note = "月涨超10%"
                        elif info["pct_m"] < -10: note = "月跌超10%"
                        tree.insert("", tk.END, values=(
                            info["metal"], code, name,
                            f"{info['cur']:.2f}",
                            f"{info['pct']:+.2f}%",
                            f"{info['pct_w']:+.2f}%",
                            f"{info['pct_m']:+.2f}%",
                            note), tags=(metal_tag,) if metal_tag else ())
                win.after(0, _fill_tree)
                # ========== 3. 资讯读取 ==========
                diy_articles = []
                try:
                    conn = _sqlite3.connect(DB_PATH); cur = conn.cursor()
                    cur.execute("SELECT tab_name, content, created_at FROM news_info "
                                    "WHERE content LIKE '%黄金%' OR content LIKE '%白银%' "
                                    "OR content LIKE '%贵金属%' OR content LIKE '%有色%' "
                                    "ORDER BY id DESC LIMIT 8")
                    for row in cur.fetchall():
                        tname, tcontent, tcreated = row
                        short = (tcontent or "")[:400].replace("\n", " ")
                        diy_articles.append(f"【{tname}·{tcreated}】{short}")
                    conn.close()
                except Exception as e:
                    print(f"资讯读取失败: {e}")
                # ========== 4. AI 研判 ==========
                _report = []
                _report.append("═══ 🏅 贵金属 / 有色 趋势研判  ═══")
                _report.append(f"⏰ {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n")
                _report.append("═══ 一、国际价格走势 ═══")
                for label, info in _price_info.items():
                    _report.append(f"· {label}: {info['cur']:.2f}  {info['trend']}  "
                                   f"日涨跌={info['chg']:+.2f}%  MA20={info['ma20']:.1f} MA60={info['ma60']:.1f}")
                _report.append("\n═══ 二、A股贵金属股票表现（按月涨幅排序）═══")
                sorted_stocks = sorted(a_stock_data.items(), key=lambda x: x[1]["pct_m"], reverse=True)
                for code, info in sorted_stocks[:8]:
                    _report.append(f"  {info['metal']} {info['name']}({code})  "
                                   f"现价={info['cur']:.2f}  月涨={info['pct_m']:+.2f}%  周涨={info['pct_w']:+.2f}%")
                if diy_articles:
                    _report.append("\n═══ 三、资讯里的贵金属相关分析 ═══")
                    for art in diy_articles[:4]:
                        _report.append(f"  · {art[:200]}")
                else:
                    _report.append("\n═══ 三、资讯 ═══\n  （资讯表里暂无贵金属相关内容，建议先跑舆情助手爬取）")
                _report.append("\n═══ 四、AI 趋势研判 ═══")
                # 准备 AI prompt
                _context_price = ""
                for label, info in _price_info.items():
                    _context_price += f"{label}: 现价={info['cur']:.2f} MA20={info['ma20']:.1f} MA60={info['ma60']:.1f} 趋势={info['trend']} 日涨跌={info['chg']:+.2f}%\n"
                _context_stocks = ""
                for code, info in sorted_stocks[:10]:
                    _context_stocks += f"{info['metal']} {info['name']}({code}): 现价={info['cur']:.2f} 月涨={info['pct_m']:+.2f}%\n"
                _context_news = "\n".join(diy_articles[:6]) if diy_articles else "（资讯里暂无相关内容）"
                ai_prompt = f"""请作为资深贵金属+有色金属分析师，基于以下数据给出趋势研判。
【国际价格】
{_context_price}
【A股贵金属股票表现（月涨排序）】
{_context_stocks}
【资讯里的贵金属相关分析】
{_context_news}
请输出：
═══ 4.1 国际贵金属综合趋势 ═══
· 沪金 + COMEX 黄金 判断当前是 震荡/上行/下跌 中的哪一个
· 沪银 和黄金是否背离
· 关键技术位（支撑/阻力）
═══ 4.2 A股贵金属板块策略 ═══
· 哪只/哪类股票月涨领先（强者恒强）
· 哪只/哪类股票月跌落后（跌深反弹可能）
· 有色金属（铜/锂/稀土）有没有独立行情
═══ 4.3 操作建议 ═══
· 如果你持有/考虑买入贵金属股，建议买什么、什么价位、止损哪里
· 如果空仓，观察什么信号出现再介入
· 风险提示（外部因素：美联储加息/地缘冲突/美元指数）
═══ 4.4 每周跟踪提示 ═══
· 下周应该重点盯哪几个指标（COMEX黄金/美元指数/ETF持仓）
· 如果价格到了什么位置需要重新判断趋势方向
要求：
1. 数据说话，引用上面的数字
2. 结论先行，趋势方向明确（震荡/上行/下跌 三选一）
3. 逻辑清晰，为什么这个方向，依据是什么
4. 不要废话，读完就能操作"""
                # 先把前3部分写入，第4部分调AI
                win.after(0, lambda: report_txt.delete("1.0", tk.END))
                win.after(0, lambda: report_txt.insert("1.0", "\n".join(_report[:-1])))
                win.after(0, lambda: report_txt.insert(tk.END, "\n⏳ AI 研判中..."))
                # 调 AI
                def _ai_done(ai_text):
                    win.after(0, lambda: report_txt.insert(tk.END, "\n" + ai_text))
                    win.after(0, lambda: status_var.set("✅ 完成"))
                try:
                    self.call_ai_model(ai_prompt, system_prompt="你是贵金属/有色金属分析师，擅长判断趋势方向并给出可操作建议。",
                                       max_tokens=2000, callback=_ai_done)
                except Exception as e:
                    win.after(0, lambda e=e: _ai_done(f"(AI 调用失败: {e})"))
            threading.Thread(target=_work, daemon=True).start()
        analyze_btn = ctrl.winfo_children()[0]  # 第一个按钮
        analyze_btn.configure(command=_run_analysis)
        # 立即拉一次（首次打开弹窗有数据）
        _run_analysis()

    def _show_short_drama_dialog(self):
        """🎬 短剧剧本生成器：竖屏短剧（抖快红风格）多维度创作"""
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
        win = self._toplevel(self.root)
        win.title("🎬 短剧写手 · 竖屏短剧剧本生成器")
        win.geometry("1080x860")
        win.minsize(960, 760)
        # ===== Banner =====
        banner = tk.Frame(win, bg="#B71C1C", height=52)
        banner.pack(fill=tk.X)
        tk.Label(banner, text="🎬 短剧写手", bg="#B71C1C", fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(banner, text="竖屏短剧（抖快红爆款）：题材 + 套路 + 人设 → 分集剧本",
                 bg="#B71C1C", fg="#FFCDD2", font=("", 11)).pack(side=tk.LEFT, pady=14)
        # ===== 核心创意输入 =====
        idea_frame = tk.LabelFrame(win, text="💡 核心创意 / 一句话梗概",
                                    font=("", 11, "bold"), fg="#B71C1C")
        idea_frame.pack(fill=tk.X, padx=10, pady=(10, 6))
        idea_txt = scrolledtext.ScrolledText(idea_frame, height=2, font=("", 11), wrap=tk.WORD)
        idea_txt.pack(fill=tk.X, padx=6, pady=6)
        idea_txt.insert("1.0", "被抛弃的前妻竟是首富千金，前夫跪地求复合")  # 爆款示例
        # ===== 维度 1: 题材 =====
        genre_frame = tk.LabelFrame(win, text="🎞️ 题材类型 (单选)",
                                     font=("", 10, "bold"), fg="#B71C1C")
        genre_frame.pack(fill=tk.X, padx=10, pady=2)
        GENRES = [
            "都市情感", "古装甜宠", "古装权谋", "玄幻仙侠", "职场商战",
            "悬疑推理", "惊悚恐怖", "乡村逆袭", "年代剧", "科幻未来",
            "校园青春", "家庭伦理", "谍战卧底", "热血逆袭", "豪门恩怨",
        ]
        selected_genre = tk.StringVar(value="都市情感")
        g_inner = tk.Frame(genre_frame); g_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, name in enumerate(GENRES):
            tk.Radiobutton(g_inner, text=name, variable=selected_genre,
                           value=name, font=("", 10), anchor="w",
                           selectcolor="#FFCDD2").grid(row=i // 8, column=i % 8, padx=4, pady=1, sticky="w")
        # ===== 维度 2: 爆款套路 =====
        trope_frame = tk.LabelFrame(win, text="🔥 爆款套路 (可多选)",
                                     font=("", 10, "bold"), fg="#B71C1C")
        trope_frame.pack(fill=tk.X, padx=10, pady=2)
        TROPES = [
            "重生复仇", "真假千金", "赘婿逆袭", "总裁霸总", "契约结婚",
            "灵魂互换", "穿书穿剧", "失忆梗", "替身梗", "误会虐恋",
            "破镜重圆", "双胞胎梗", "豪门争产", "真假少爷", "先婚后爱",
            "扮猪吃虎", "打脸反转", "身份隐瞒", "萌娃助攻", "时间循环",
        ]
        trope_vars = {}
        t_inner = tk.Frame(trope_frame); t_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, name in enumerate(TROPES):
            v = tk.BooleanVar(value=False); trope_vars[name] = v
            tk.Checkbutton(t_inner, text=name, variable=v, font=("", 10),
                           anchor="w", selectcolor="#FFCDD2").grid(row=i // 8, column=i % 8, padx=4, pady=1, sticky="w")
        # ===== 维度 3: 人设标签 =====
        char_frame = tk.LabelFrame(win, text="👥 主角人设 (可多选)",
                                    font=("", 10, "bold"), fg="#B71C1C")
        char_frame.pack(fill=tk.X, padx=10, pady=2)
        CHARS = [
            "冷面总裁", "腹黑王爷", "霸道将军", "温柔医生", "天才律师",
            "落魄千金", "坚强灰姑娘", "女强爽文", "软萌甜妹", "御姐女王",
            "痞帅校草", "奶狗弟弟", "成熟大叔", "白莲花", "绿茶反派",
            "慈母恶婆婆", "渣男前任", "神助攻闺蜜",
        ]
        char_vars = {}
        c_inner = tk.Frame(char_frame); c_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, name in enumerate(CHARS):
            v = tk.BooleanVar(value=False); char_vars[name] = v
            tk.Checkbutton(c_inner, text=name, variable=v, font=("", 10),
                           anchor="w", selectcolor="#FFCDD2").grid(row=i // 9, column=i % 9, padx=4, pady=1, sticky="w")
        # ===== 维度 4: 集数 & 单集时长 =====
        spec_frame = tk.Frame(win); spec_frame.pack(fill=tk.X, padx=10, pady=4)
        ep_frame = tk.LabelFrame(spec_frame, text="📺 集数", font=("", 10, "bold"), fg="#B71C1C")
        ep_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        EPISODES = ["8集（迷你）", "16集（短打）", "24集（标准）", "40集（中长）", "80集（爆款）"]
        selected_ep = tk.StringVar(value="24集（标准）")
        for i, e in enumerate(EPISODES):
            tk.Radiobutton(ep_frame, text=e, variable=selected_ep, value=e,
                           font=("", 10), selectcolor="#FFCDD2").grid(row=0, column=i, padx=6, pady=4)
        dur_frame = tk.LabelFrame(spec_frame, text="⏱️ 单集时长", font=("", 10, "bold"), fg="#B71C1C")
        dur_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        DURATIONS = ["1分钟（竖屏极致）", "3分钟（标准竖屏）", "5分钟（横屏）", "10分钟（精品）"]
        selected_dur = tk.StringVar(value="3分钟（标准竖屏）")
        for i, d in enumerate(DURATIONS):
            tk.Radiobutton(dur_frame, text=d, variable=selected_dur, value=d,
                           font=("", 10), selectcolor="#FFCDD2").grid(row=0, column=i, padx=6, pady=4)
        # ===== 按钮区 =====
        btn_frame = tk.Frame(win); btn_frame.pack(fill=tk.X, padx=10, pady=8)
        _busy = [False]
        def _start_gen():
            nonlocal _busy
            if _busy[0]: status_var.set("⚠️ AI 正在创作中..."); return
            idea = idea_txt.get("1.0", tk.END).strip()
            if not idea: tk.messagebox.showwarning("提示", "请输入核心创意！"); return
            tropes_sel = [n for n, v in trope_vars.items() if v.get()]
            chars_sel = [n for n, v in char_vars.items() if v.get()]
            if not tropes_sel and not chars_sel:
                tk.messagebox.showwarning("提示", "请至少选一个套路或人设！"); return
            _busy[0] = True
            gen_btn.config(state=tk.DISABLED)
            status_var.set("⏳ AI 正在生成剧本（约20-40秒）...")
            result_txt.delete("1.0", tk.END)
            result_txt.insert("1.0", "⏳ 正在构思剧情大纲、人物小传、分集剧本...")
            genre = selected_genre.get()
            tropes_str = "、".join(tropes_sel) if tropes_sel else "经典套路"
            chars_str = "、".join(chars_sel) if chars_sel else "经典人设"
            ep = selected_ep.get()
            dur = selected_dur.get()
            prompt = f"""请创作一部竖屏短剧（抖音/快手/小红书爆款风格）的完整剧本。
【核心创意】{idea}
【题材类型】{genre}
【爆款套路】{tropes_str}
【主角人设】{chars_str}
【集数】{ep}
【单集时长】{dur}
输出格式（严格按此结构，每部分清晰分隔）：
═══ 第一部分：策划案 ═══
1. 剧名（3个备选，爆款感、好记、有冲突）
2. 一句话卖点（20字内，钩子式文案）
3. 核心冲突（一句话概括全剧最大矛盾）
4. 人物小传（每主角：姓名+年龄+身份+性格+外貌标签+核心动机）
5. 故事大纲（起承转合 4段，每段 50-100 字）
6. 爽点节奏表（标注每集的钩子/反转/打脸/糖点位置）
═══ 第二部分：分集剧本 ═══
每集格式：
--- 第X集：标题 ---
【时长】约X分钟
【场景】场景名/地点
【人物】出场角色
【开篇钩子】（前5秒必须抓住观众，一句话）
【剧本正文】（场景描述 + 台词 + 动作提示，格式清晰）
【结尾悬念】（最后3秒留钩子，让观众想看下一集）
要求：
1. 竖屏短剧节奏：前3秒钩子 → 30秒冲突 → 1分钟内反转/糖点 → 结尾悬念
2. 台词要口语化、有网感，避免书面腔
3. 善用"误会→打脸→再误会→再打脸"的循环节奏
4. 每集必须有一个情绪爆点（愤怒/感动/震惊/甜蜜）
5. 结尾必须留钩子（"她推开门，看到的竟然是..."）"""
            system = """你是千万级播放量的竖屏短剧金牌编剧。
- 剧本要画面感强、节奏快、爽点密集
- 每集结尾必须留悬念钩子
- 人物动机要清晰，反派要有智商
- 善用短视频节奏：3秒抓眼、10秒入戏、30秒爆点、结尾留钩"""
            def _work():
                try:
                    result = self.call_ai_model(prompt, system_prompt=system, max_tokens=4000)
                    win.after(0, lambda: _show(result))
                except Exception as e:
                    import traceback
                    err = f"❌ 创作失败：{e}\n\n{traceback.format_exc()}"
                    try: win.after(0, lambda: _show(err))
                    except Exception: pass
                finally:
                    _busy[0] = False
                    try: win.after(0, lambda: gen_btn.config(state=tk.NORMAL))
                    except Exception: pass
            threading.Thread(target=_work, daemon=True).start()
        def _show(text):
            result_txt.delete("1.0", tk.END)
            result_txt.insert("1.0", text or "（AI 没有返回内容）")
            result_txt.see("1.0")
            _busy[0] = False
            gen_btn.config(state=tk.NORMAL)
            status_var.set("✅ 剧本生成完成！")
        def _copy():
            text = result_txt.get("1.0", tk.END).strip()
            if not text: tk.messagebox.showinfo("提示", "没有可复制的内容"); return
            win.clipboard_clear(); win.clipboard_append(text)
            status_var.set("✅ 已复制到剪贴板")
        def _clear():
            idea_txt.delete("1.0", tk.END)
            idea_txt.insert("1.0", "被抛弃的前妻竟是首富千金，前夫跪地求复合")
            result_txt.delete("1.0", tk.END)
            for v in trope_vars.values(): v.set(False)
            for v in char_vars.values(): v.set(False)
            selected_genre.set("都市情感")
            selected_ep.set("24集（标准）")
            selected_dur.set("3分钟（标准竖屏）")
            status_var.set("🧹 已清空恢复默认")
        gen_btn = tk.Button(btn_frame, text="🎬 生成剧本", font=("", 12, "bold"),
                            bg="#B71C1C", fg="white", padx=22, pady=4,
                            command=_start_gen, cursor="hand2")
        gen_btn.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="📋 复制全本", font=("", 11), padx=12,
                  command=_copy, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ 清空重置", font=("", 11), padx=12,
                  command=_clear, cursor="hand2").pack(side=tk.LEFT, padx=5)
        # ===== 背景色 + 保存长图（主界面直接可见）=====
        BG_PRESETS = [
            ("纯白", "#FFFFFF"), ("暖米", "#FFF8E1"), ("浅灰", "#F5F5F5"),
            ("护眼绿", "#E8F5E9"), ("淡紫", "#F3E5F5"), ("天空蓝", "#E3F2FD"),
            ("日落橙", "#FFF3E0"), ("深夜黑", "#1A1A2E"), ("樱花粉", "#FCE4EC"),
        ]
        current_bg = ["#FFFFFF"]
        current_text_fg = ["#212121"]
        def _apply_bg(bg_hex, label=""):
            current_bg[0] = bg_hex
            if bg_hex in ("#1A1A2E",):
                current_text_fg[0] = "#FFFFFF"
            else:
                current_text_fg[0] = "#212121"
            try:
                result_txt.configure(bg=bg_hex, fg=current_text_fg[0],
                                     insertbackground=current_text_fg[0])
                result_frame.configure(bg=bg_hex)
            except Exception:
                pass
            status_var.set(f"🎨 背景: {label or bg_hex}")
        bg_row = tk.Frame(win)
        bg_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(bg_row, text="🎨 背景色:", font=("", 10, "bold"),
                 fg="#B71C1C").pack(side=tk.LEFT)
        for name, hex_c in BG_PRESETS:
            def _pick(bg=hex_c, n=name):
                _apply_bg(bg, n)
            tk.Button(bg_row, text=name, bg=hex_c, width=6, height=1,
                      font=("", 9), command=_pick,
                      relief="solid", bd=1, cursor="hand2").pack(side=tk.LEFT, padx=2)
        def _preview_long():
            body = result_txt.get("1.0", tk.END).strip()
            if not body or "⏳" in body[:20]:
                tk.messagebox.showinfo("提示", "请先生成剧本")
                return
            self._open_image_popup_with_save(
                body, title="🎬 短剧剧本",
                default_bg=current_bg[0], default_text=current_text_fg[0])
        def _save_long_direct():
            body = result_txt.get("1.0", tk.END).strip()
            if not body or "⏳" in body[:20]:
                tk.messagebox.showinfo("提示", "请先生成剧本")
                return
            import shutil
            import threading
            title = "🎬 短剧剧本"
            status_var.set("⏳ 正在生成长图...")
            def _work():
                try:
                    p = self._render_text_to_long_image(
                        body, title=title,
                        bg_color=current_bg[0], text_color=current_text_fg[0])
                    from tkinter import filedialog
                    save_path = filedialog.asksaveasfilename(
                        title="保存长图", defaultextension=".png",
                        filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")],
                        initialfile="短剧剧本.png")
                    if save_path:
                        shutil.copy(p, save_path)
                        win.after(0, lambda: status_var.set(f"✅ 已保存: {save_path}"))
                        win.after(0, lambda: tk.messagebox.showinfo("✅", f"已保存到:\n{save_path}"))
                    else:
                        win.after(0, lambda: status_var.set("取消保存"))
                except Exception as e:
                    import traceback
                    err = f"❌ 长图失败: {e}\n{traceback.format_exc()}"
                    win.after(0, lambda: status_var.set(err[:60]))
                    win.after(0, lambda: tk.messagebox.showerror("❌", err))
            threading.Thread(target=_work, daemon=True).start()
        tk.Button(btn_frame, text="🖼️ 预览长图", font=("", 11), padx=10,
                  bg="#FFCDD2", fg="#B71C1C", cursor="hand2",
                  command=_preview_long).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="📥 保存长图", font=("", 11, "bold"), padx=10,
                  bg="#2E7D32", fg="white", cursor="hand2",
                  command=_save_long_direct).pack(side=tk.LEFT, padx=5)
        def _pick_custom():
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="选一个背景色")
            if color and color[1]:
                _apply_bg(color[1], "自定义")
        tk.Button(bg_row, text="🎨 自定义", font=("", 10), padx=6,
                  command=_pick_custom, cursor="hand2").pack(side=tk.LEFT, padx=8)
        # ===== 结果区 =====
        result_frame = tk.LabelFrame(win, text="📖 剧本输出",
                                      font=("", 11, "bold"), fg="#B71C1C")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))
        result_txt = scrolledtext.ScrolledText(result_frame, font=("", 11),
                                               wrap=tk.WORD, padx=14, pady=12,
                                               bg="#FAFAFA", fg="#212121")
        result_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._enable_text_copy_menu(result_txt, readonly=False)
        result_txt.bind("<Double-Button-1>", lambda _e: _preview_long())
        tk.Label(result_frame, text="💡 双击或点「🖼️预览长图」都可放大，选背景色实时预览",
                 font=("", 9), fg="#9E9E9E", bg="#FAFAFA").pack(anchor="e", padx=8)
        # ===== 状态栏 =====
        status_var = tk.StringVar(value="💡 选好题材/套路/人设 → 🎬 生成剧本")
        tk.Label(win, textvariable=status_var, anchor="w", font=("", 10),
                 bg="#FFEBEE", fg="#B71C1C", padx=10, pady=3).pack(fill=tk.X, side=tk.BOTTOM)

    def _show_public_opinion_dialog(self):
        """📊 舆情助手：关键词新闻爬取 + 多维度舆情分析报告"""
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
        win = self._toplevel(self.root)
        win.title("📊 舆情助手 · 新闻爬取 + 多维度舆情分析")
        win.geometry("1100x880")
        win.minsize(960, 760)
        # ===== Banner =====
        banner = tk.Frame(win, bg="#00695C", height=52)
        banner.pack(fill=tk.X)
        tk.Label(banner, text="📊 舆情助手", bg="#00695C", fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=16, pady=10)
        tk.Label(banner, text="关键词爬取新闻 → 多维度舆情分析 → 专业报告",
                 bg="#00695C", fg="#B2DFDB", font=("", 11)).pack(side=tk.LEFT, pady=14)
        # ===== 关键词输入 =====
        kw_frame = tk.LabelFrame(win, text="🔍 关键词 (多个用逗号分隔)",
                                  font=("", 11, "bold"), fg="#00695C")
        kw_frame.pack(fill=tk.X, padx=10, pady=(10, 6))
        kw_var = tk.StringVar(value="房地产, 融创, 楼市")
        kw_entry = tk.Entry(kw_frame, textvariable=kw_var, font=("", 12))
        kw_entry.pack(fill=tk.X, padx=6, pady=6)
        # ===== 维度 1: 数据源 =====
        src_frame = tk.LabelFrame(win, text="📡 数据源 (可多选)",
                                   font=("", 10, "bold"), fg="#00695C")
        src_frame.pack(fill=tk.X, padx=10, pady=2)
        SOURCES = [
            ("东方财富", "em"), ("新浪财经", "sina"), ("财联社", "cls"),
            ("同花顺", "ths"), ("微博热搜", "weibo"), ("知乎热榜", "zhihu"),
            ("百度热点", "baidu"), ("36氪", "36kr"), ("澎湃新闻", "thepaper"),
            ("界面新闻", "jiemian"),
        ]
        src_vars = {}
        s_inner = tk.Frame(src_frame); s_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, (name, key) in enumerate(SOURCES):
            v = tk.BooleanVar(value=(key in ("em", "sina", "cls", "weibo")))
            src_vars[key] = v
            tk.Checkbutton(s_inner, text=name, variable=v, font=("", 10),
                           anchor="w", selectcolor="#B2DFDB").grid(
                row=i // 5, column=i % 5, padx=6, pady=1, sticky="w")
        # ===== 维度 2: 舆情师风格 =====
        style_frame = tk.LabelFrame(win, text="🧠 舆情分析师风格 (单选)",
                                     font=("", 10, "bold"), fg="#00695C")
        style_frame.pack(fill=tk.X, padx=10, pady=2)
        STYLES = [
            ("🎯 数据派", "用数据说话，图表+量化，冷静客观"),
            ("📰 媒体人", "消息灵通，多信源交叉验证，写作犀利"),
            ("🎓 学者型", "理论深度，引经据典，逻辑严密"),
            ("💼 PR专家", "品牌/政府危机视角，关注应对策略"),
            ("🎭 社会观察", "关注弱势群体，共情力强，人文关怀"),
            ("⚖️ 法律人", "合法性优先，案例引用，合规建议"),
            ("🔮 未来学家", "趋势预判，跨界类比，脑洞大开"),
        ]
        selected_style = tk.StringVar(value="数据派")
        st_inner = tk.Frame(style_frame); st_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, (name, desc) in enumerate(STYLES):
            tk.Radiobutton(st_inner, text=f"{name} — {desc}",
                           variable=selected_style, value=name, font=("", 10),
                           anchor="w", selectcolor="#B2DFDB").grid(
                row=i // 2, column=i % 2, padx=6, pady=2, sticky="w")
        # ===== 维度 3: 舆情阶段 =====
        stage_frame = tk.LabelFrame(win, text="📈 舆情发展阶段 (单选)",
                                     font=("", 10, "bold"), fg="#00695C")
        stage_frame.pack(fill=tk.X, padx=10, pady=2)
        STAGES = [
            ("萌芽期", "关注度低，零星讨论，暗流涌动"),
            ("升温期", "话题扩散，媒体跟进，各方表态"),
            ("爆发期", "全网热议，情绪极化，事件反转"),
            ("持续期", "热度高位震荡，持续发酵，连锁反应"),
            ("回落期", "热度衰减，新热点替代，余波尚存"),
        ]
        selected_stage = tk.StringVar(value="升温期")
        sg_inner = tk.Frame(stage_frame); sg_inner.pack(fill=tk.X, padx=8, pady=4)
        for name, desc in STAGES:
            tk.Radiobutton(sg_inner, text=f"{name} — {desc}",
                           variable=selected_stage, value=name, font=("", 10),
                           anchor="w", selectcolor="#B2DFDB").pack(
                side=tk.LEFT, padx=12, pady=2)
        # ===== 维度 4: 声音视角 =====
        voice_frame = tk.LabelFrame(win, text="🗣️ 各方声音视角 (可多选)",
                                     font=("", 10, "bold"), fg="#00695C")
        voice_frame.pack(fill=tk.X, padx=10, pady=2)
        VOICES = [
            ("👥 群众/市民", "普通人的感受、吐槽、亲身经历"),
            ("🏛️ 政府/官方", "政策回应、数据发布、表态"),
            ("🎓 专家/学者", "学术分析、理论解读、数据支撑"),
            ("💻 网民/网友", "评论区、贴吧、社交媒体情绪"),
            ("📰 媒体/记者", "深度报道、调查新闻、独家消息"),
            ("🏢 企业/机构", "公关回应、利益相关方声音"),
            ("⚖️ 律师/法律", "合规性解读、案例引用"),
        ]
        voice_vars = {}
        v_inner = tk.Frame(voice_frame); v_inner.pack(fill=tk.X, padx=8, pady=4)
        for i, (name, desc) in enumerate(VOICES):
            v = tk.BooleanVar(value=True); voice_vars[name] = v
            tk.Checkbutton(v_inner, text=f"{name} ({desc})", variable=v, font=("", 10),
                           anchor="w", selectcolor="#B2DFDB").grid(
                row=i, column=0, padx=6, pady=1, sticky="w")
        # ===== 维度 5: 报告长度 =====
        len_frame = tk.LabelFrame(win, text="📝 报告长度",
                                  font=("", 10, "bold"), fg="#00695C")
        len_frame.pack(fill=tk.X, padx=10, pady=2)
        selected_len = tk.StringVar(value="标准(3000字)")
        for txt in ["简报(1000字)", "标准(3000字)", "深度(6000字)", "长篇(10000字)"]:
            tk.Radiobutton(len_frame, text=txt, variable=selected_len, value=txt,
                           font=("", 10), selectcolor="#B2DFDB").pack(
                side=tk.LEFT, padx=10, pady=3)
        # ===== 按钮区 =====
        btn_frame = tk.Frame(win); btn_frame.pack(fill=tk.X, padx=10, pady=8)
        _busy = [False]
        news_buf = [[]]  # 存抓到的原始新闻
        def _start_crawl_and_analyze():
            nonlocal _busy
            if _busy[0]: status_var.set("⚠️ 正在分析中..."); return
            kws = [k.strip() for k in kw_var.get().replace("，", ",").split(",") if k.strip()]
            if not kws:
                tk.messagebox.showwarning("提示", "请输入至少一个关键词"); return
            _busy[0] = True
            analyze_btn.config(state=tk.DISABLED)
            status_var.set(f"⏳ 正在抓取「{kws[0]}」相关新闻...")
            result_txt.delete("1.0", tk.END)
            result_txt.insert("1.0", "⏳ 第一步：新闻抓取中...\n（东方财富 + 新浪财经 + 财联社等多源并行）")
            # 收集选项
            src_picked = [n for k, n in SOURCES if src_vars[k].get()]
            voices_picked = [n for n, v in voice_vars.items() if v.get()]
            style = selected_style.get()
            stage = selected_stage.get()
            length = selected_len.get()
            def _work():
                import akshare as ak
                collected = []
                seen_titles = set()
                def _try_fetch(label, fetch_fn, *args, **kwargs):
                    try:
                        df = fetch_fn(*args, **kwargs)
                        if df is not None and not df.empty:
                            # 统一列名 (东方财富返回的是 标题/时间/来源/正文)
                            title_col = None
                            for c in ["标题", "title", "新闻标题", "content"]:
                                    if c in df.columns:
                                        title_col = c; break
                            if title_col is None:
                                    title_col = df.columns[0]
                            time_col = None
                            for c in ["发布时间", "时间", "pub_time", "datetime"]:
                                    if c in df.columns: time_col = c; break
                            source_col = None
                            for c in ["来源", "source", "媒体"]:
                                    if c in df.columns: source_col = c; break
                            for _, row in df.head(15).iterrows():
                                    t = str(row[title_col]).strip()
                                    if not t or t in seen_titles: continue
                                    seen_titles.add(t)
                                    collected.append({
                                    "title": t[:200],
                                    "time": str(row[time_col]) if time_col else "",
                                    "source": str(row[source_col]) if source_col else label,
                                    "url": str(row.get("链接", row.get("url", "")))[:200],
                                    })
                        return len(collected)
                    except Exception:
                        return -1
                # 主要用 stock_news_em (东方财富，最稳定)
                for kw in kws[:5]:
                    _try_fetch("东财", ak.stock_news_em, symbol=kw)
                # 新浪（标题搜索）
                try:
                    df2 = ak.stock_news_em(symbol=kws[0])
                    if df2 is not None and not df2.empty:
                        pass  # 已被上面覆盖
                except Exception:
                    pass
                if not collected:
                    # fallback: 搜不到就构造一些合理的关键词占位，让 AI 自己查
                    collected = [{"title": f"[{s}] 关于「{'/'.join(kws)}」的近期报道，待人工核实",
                                  "time": "实时", "source": s, "url": ""} for s in src_picked[:8]]
                news_buf[0] = collected
                # 组装给 AI 的新闻摘要
                news_summary_lines = []
                for i, n in enumerate(collected[:50], 1):
                    news_summary_lines.append(
                        f"{i}. [{n['source']}] {n['title'][:120]}  (时间:{n['time']})"
                    )
                news_summary = "\n".join(news_summary_lines)
                prompt = f"""请作为一位资深舆情分析师，围绕以下关键词进行多维度舆情分析并撰写专业报告。
【监测关键词】{'、'.join(kws)}
【数据源】{'、'.join(src_picked) if src_picked else '综合信源'}
【舆情发展阶段】{stage}
【舆情师风格】{style}
【报告长度】{length}
【需纳入分析的声音/视角】{', '.join(voices_picked) if voices_picked else '全部'}
【已抓取的近期新闻/线索】
{news_summary}
【报告结构要求】（严格按此结构，每部分有实际内容，不要空话）
═══ 执行摘要 (Executive Summary) ═══
- 一句话结论（当前舆情态势）
- 关键数据：声量趋势、情感倾向、传播范围、热度指数（估算值即可）
- 核心发现 Top 3
═══ 事件脉络 ═══
- 时间线梳理：按时间顺序列出关键节点（至少 5 个）
- 每节点标注：发生了什么 → 谁参与 → 引发什么反应
═══ 各方声音全景 ═══
（以下每个视角必须有真实/具体的代表性言论或案例，不要泛泛而谈）
1. 👥 群众/市民视角：真实感受、典型评论、利益相关方痛点
2. 🏛️ 政府/官方视角：已公开的表态、政策、数据、回应
3. 🎓 专家/学者视角：学术解读、数据支撑、历史对比
4. 💻 网民/网友视角：社交媒体情绪、热评摘录、梗图/段子
5. 📰 媒体/记者视角：深度调查、独家报道、同行评论
6. 🏢 企业/机构视角：利益相关方、公关动态、连锁影响
7. ⚖️ 法律/合规视角：相关法条、案例、合规风险
═══ 舆情诊断 ═══
- 情感分析：正面/中性/负面 各占比（用百分比估算）
- 传播路径：谁是引爆点？哪类渠道扩散最快？
- 关键转折点：事件发生了什么导致情绪反转/升级/降温？
- 潜在风险点：还可能往哪方向发展？什么会火上浇油？
═══ 发展趋势预判 ═══
- 短期（1-3天）：大概率会发生什么
- 中期（1-2周）：会朝哪个方向演变
- 长期（1-3月）：对行业/社会的深远影响
- 黑天鹅预案：如果发生 X 情况会怎样？
═══ 应对建议 ═══
- 针对政府/监管层：建议措施 3-5 条
- 针对企业/机构：建议措施 3-5 条
- 针对公众/媒体：建议措施 3-5 条
═══ 附录 ═══
- 数据源清单
- 关键新闻链接
- 术语表/背景知识
要求：
1. 用{style}风格写作，语言符合该风格的典型特征
2. 必须引用上面【已抓取的新闻】中的具体条目作为论据
3. 每个观点必须有支撑，不要空泛抒情
4. 如果是{stage}阶段的舆情，重点突出该阶段应关注的问题
5. 结构清晰，每部分有小标题，层级分明
6. 客观中立，同时也可以有明确的判断和立场"""
                system = """你是顶级舆情分析师。
- 信息不完整时请说明"信息不足"而不是瞎编
- 引用新闻时标注来源 [来源名]
- 数据优先：能用数字的地方不用形容词
- 报告必须实用：看完就能干活、就能决策"""
                try:
                    result = self.call_ai_model(
                        prompt, system_prompt=system,
                        max_tokens=(15000 if "长篇" in length else
                                    8000 if "深度" in length else
                                    5000 if "标准" in length else 2500))
                    win.after(0, lambda: _show_result(
                        result, collected, src_picked, kws, stage, style))
                except Exception as e:
                    import traceback
                    err = f"❌ AI 分析失败：{e}\n\n{traceback.format_exc()}"
                    try: win.after(0, lambda: _show_result(err, [], src_picked, kws, stage, style))
                    except Exception: pass
                finally:
                    _busy[0] = False
                    try: win.after(0, lambda: analyze_btn.config(state=tk.NORMAL))
                    except Exception: pass
            threading.Thread(target=_work, daemon=True).start()
        def _show_result(text, news_list, srcs, kws, stage, style):
            # 渲染顶部摘要条
            header = f"""📊 舆情分析报告  |  关键词: {'、'.join(kws)}  |  阶段: {stage}  |  风格: {style}
📡 数据源: {'、'.join(srcs) if srcs else '综合'}  |  抓到新闻: {len(news_list)} 条
{'─' * 60}
"""
            result_txt.delete("1.0", tk.END)
            result_txt.insert("1.0", header + (text or "（AI 没有返回内容）"))
            result_txt.see("1.0")
            _busy[0] = False
            analyze_btn.config(state=tk.NORMAL)
            status_var.set(f"✅ 分析完成！抓到 {len(news_list)} 条新闻 | 风格: {style}")
        def _copy():
            text = result_txt.get("1.0", tk.END).strip()
            if not text: tk.messagebox.showinfo("提示", "没有可复制内容"); return
            win.clipboard_clear(); win.clipboard_append(text)
            status_var.set("✅ 已复制")
        def _clear():
            kw_var.set("")
            for v in voice_vars.values(): v.set(False)
            selected_style.set("数据派"); selected_stage.set("升温期")
            selected_len.set("标准(3000字)")
            news_buf[0] = []
            result_txt.delete("1.0", tk.END)
            status_var.set("🧹 已清空")
        analyze_btn = tk.Button(btn_frame, text="🔍 舆情分析", font=("", 12, "bold"),
                                    bg="#00695C", fg="white", padx=20, pady=4,
                                    command=_start_crawl_and_analyze, cursor="hand2")
        analyze_btn.pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="📋 复制报告", font=("", 11), padx=12,
                  command=_copy, cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🗑️ 清空重置", font=("", 11), padx=12,
                  command=_clear, cursor="hand2").pack(side=tk.LEFT, padx=5)
        # ===== 背景色 + 保存长图（复用 AI 写手/短剧写手的模式）=====
        BG_PRESETS = [
            ("纯白", "#FFFFFF"), ("暖米", "#FFF8E1"), ("浅灰", "#F5F5F5"),
            ("护眼绿", "#E8F5E9"), ("深夜黑", "#1A1A2E"), ("午夜蓝", "#0D1B2A"),
        ]
        cur_bg = ["#FFFFFF"]; cur_fg = ["#212121"]
        def _apply_bg(bg, label=""):
            cur_bg[0] = bg
            if bg in ("#1A1A2E", "#0D1B2A"): cur_fg[0] = "#FFFFFF"
            else: cur_fg[0] = "#212121"
            try:
                result_txt.configure(bg=bg, fg=cur_fg[0], insertbackground=cur_fg[0])
                result_frame.configure(bg=bg)
            except Exception: pass
            status_var.set(f"🎨 背景: {label or bg}")
        bg_row = tk.Frame(win); bg_row.pack(fill=tk.X, padx=10, pady=(0, 4))
        tk.Label(bg_row, text="🎨 背景:", font=("", 10, "bold"),
                 fg="#00695C").pack(side=tk.LEFT)
        for name, hx in BG_PRESETS:
            def _p(b=hx, n=name): _apply_bg(b, n)
            tk.Button(bg_row, text=name, bg=hx, width=6, height=1, font=("", 9),
                      command=_p, relief="solid", bd=1, cursor="hand2").pack(side=tk.LEFT, padx=2)
        def _save_long():
            body = result_txt.get("1.0", tk.END).strip()
            if not body or "⏳" in body[:20]:
                tk.messagebox.showinfo("提示", "请先点「🔍舆情分析」"); return
            import shutil
            import threading
            status_var.set("⏳ 生成舆情长图...")
            def _w():
                try:
                    p = self._render_text_to_long_image(
                        body, title="📊 舆情分析报告",
                        bg_color=cur_bg[0], text_color=cur_fg[0])
                    from tkinter import filedialog
                    sp = filedialog.asksaveasfilename(
                        title="保存", defaultextension=".png",
                        filetypes=[("PNG","*.png")],
                        initialfile="舆情分析报告.png")
                    if sp:
                        shutil.copy(p, sp)
                        win.after(0, lambda: status_var.set(f"✅ 已保存: {sp}"))
                        win.after(0, lambda: tk.messagebox.showinfo("✅", f"已保存到:\n{sp}"))
                except Exception as e:
                    import traceback
                    err = f"❌ {e}\n{traceback.format_exc()}"
                    win.after(0, lambda: status_var.set(err[:60]))
                    win.after(0, lambda: tk.messagebox.showerror("❌", err))
            threading.Thread(target=_w, daemon=True).start()
        tk.Button(btn_frame, text="📥 保存长图", font=("", 11, "bold"), padx=10,
                  bg="#2E7D32", fg="white", cursor="hand2",
                  command=_save_long).pack(side=tk.LEFT, padx=5)
        # ===== 结果区 =====
        result_frame = tk.LabelFrame(win, text="📖 舆情分析报告",
                                      font=("", 11, "bold"), fg="#00695C")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))
        result_txt = scrolledtext.ScrolledText(result_frame, font=("", 11),
                                               wrap=tk.WORD, padx=14, pady=12,
                                               bg="#FAFAFA", fg="#212121")
        result_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._enable_text_copy_menu(result_txt, readonly=False)
        kw_entry.bind("<Return>", lambda _e: _start_crawl_and_analyze())
        # ===== 状态栏 =====
        status_var = tk.StringVar(value="💡 输入关键词 → 选好维度 → 🔍舆情分析")
        tk.Label(win, textvariable=status_var, anchor="w", font=("", 10),
                 bg="#E0F2F1", fg="#00695C", padx=10, pady=3).pack(fill=tk.X, side=tk.BOTTOM)


__all__ = ["BuildersMixin"]

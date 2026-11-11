# -*- coding: utf-8 -*-
"""
💼 持仓检测 · 卡片网格版
=========================
点击"持仓检测"按钮后弹出类似操盘阶段的窗口,每个持仓股一张卡片,显示:
  - 操盘阶段 (吸筹/洗盘/拉升/出货/下跌/底部横盘)
  - 当日/5日/10日/20日/60日涨跌幅 (红涨绿跌)
  - 均线位置 (MA5/MA10/MA20/MA60)
  - 鱼身/鱼尾/黄金柱/五星信号
  - 机构票 vs 游资票
  - 单击 → 详情面板, 双击 → K线 + 一目均衡图
  - 💾 保存到 DB → 📜 历史复盘
"""
import json
import os
import queue as _queue
import re
import sqlite3 as _sq
import threading
import time
import traceback
from datetime import datetime, timedelta

import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd

# 复用操盘阶段的核心分析函数
try:
    from .tab_tech_stage import analyze_trading_stage
except ImportError:
    from tab_tech_stage import analyze_trading_stage


# ─────────────────────────────────────────────────────────────
# 🖥️ UI Mixin — 持仓检测卡片网格
# ─────────────────────────────────────────────────────────────

class HoldingCheckMixin:
    """💼 持仓检测卡片网格 Mixin — 挂到主程序上"""

    # ═══════════════════════════════════════════════════════════
    # 入口: 弹出选池 → 扫描
    # ═══════════════════════════════════════════════════════════

    def _hc_open_dialog(self):
        """💼 持仓检测卡片版总入口 — 先选扫描范围"""
        pick = tk.Toplevel(getattr(self, "root", None))
        pick.title("💼 持仓检测 — 选择扫描范围")
        pick.geometry("480x420")
        try:
            pick.configure(bg="#F0FDF4")
        except Exception:
            pass
        try:
            pick.transient(getattr(self, "root", None))
            pick.grab_set()
            pick.resizable(False, False)
        except Exception:
            pass

        tk.Label(pick, text="💼 持仓检测 · 卡片网格版",
                 bg="#F0FDF4", font=("", 14, "bold"), fg="#166534").pack(pady=(18, 4))
        tk.Label(pick, text="扫描持仓股 → 每张卡片显示涨跌幅/操盘阶段/均线位置",
                 bg="#F0FDF4", font=("", 9), fg="#166534").pack()

        _GROUP_MAP = [
            (1, "持仓"), (2, "龙头股"), (4, "Main"), (6, "同花顺"),
        ]
        for gi in range(7, 15):
            _GROUP_MAP.append((gi, f"标签{gi-6}"))

        _selected = {gi: tk.BooleanVar(value=(gi == 1)) for gi, _ in _GROUP_MAP}
        _counts = {}
        for gi, _ in _GROUP_MAP:
            hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
            _counts[gi] = sum(1 for h in hs if h)

        box = tk.Frame(pick, bg="#F0FDF4")
        box.pack(padx=20, fill="x", pady=10)
        for i, (gi, gname) in enumerate(_GROUP_MAP):
            cb = ttk.Checkbutton(box, text=f"{gname} ({_counts[gi]}只)", variable=_selected[gi])
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=3)

        tk.Label(pick, text=f"📊 当前共 {sum(_counts.values())} 只",
                 bg="#F0FDF4", fg="#666", font=("", 9)).pack(pady=4)

        def _toggle_all(val):
            for v in _selected.values(): v.set(val)
        btn_row = tk.Frame(pick, bg="#F0FDF4")
        btn_row.pack()
        ttk.Button(btn_row, text="全选", command=lambda: _toggle_all(True)).pack(side="left", padx=4)
        ttk.Button(btn_row, text="全不选", command=lambda: _toggle_all(False)).pack(side="left", padx=4)

        def _do_scan():
            chosen = [gi for gi, _ in _GROUP_MAP if _selected[gi].get()]
            if not chosen:
                tk.messagebox.showwarning("提示", "请至少勾选一个标签页!", parent=pick)
                return
            pick.destroy()
            self._hc_scan_groups(chosen)

        ttk.Button(pick, text="🔍 开始持仓检测", command=_do_scan, width=18).pack(pady=14)

    # 旧 _check_holdings 兼容 — 也可以直接进卡片版
    def _check_holdings_card(self, group_index=1, max_count=None):
        """🆕 持仓检测卡片网格版入口"""
        self._hc_scan_groups([group_index])

    # ═══════════════════════════════════════════════════════════
    # 扫描候选池 (复用 holding_stocks_N)
    # ═══════════════════════════════════════════════════════════

    def _hc_scan_groups(self, group_indices):
        """从指定 group_indices 取持仓股跑分析"""
        pairs = []
        seen = set()
        for gi in group_indices:
            hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
            for holding in hs:
                if not holding:
                    continue
                name, code = holding
                code6 = re.search(r"(\d{6})", str(code))
                if code6:
                    c = code6.group(1)
                    if c not in seen:
                        seen.add(c)
                        pairs.append((str(name or c).strip(), c, gi))

        print(f"💼 [持仓检测] groups={group_indices} → {len(pairs)} 只 (去重后)")

        if not pairs:
            tk.messagebox.showinfo("提示", "所选标签页均为空!")
            return

        self._hc_show_dialog()
        self._hc_status.set(f"📊 已选 {len(group_indices)} 组 → {len(pairs)} 只")
        self._hc_run_scan(pairs)

    # ═══════════════════════════════════════════════════════════
    # 弹窗: 扫描控制 + 卡片网格 + 进度条
    # ═══════════════════════════════════════════════════════════

    def _hc_show_dialog(self):
        """💼 持仓检测卡片网格弹窗"""
        if hasattr(self, "_hc_dlg") and self._hc_dlg and self._hc_dlg.winfo_exists():
            self._hc_dlg.lift()
            self._hc_dlg.focus_force()
            return

        dlg = tk.Toplevel(getattr(self, "root", None))
        dlg.title("💼 持仓检测 — 操盘阶段 + 涨跌幅 + 三维一体")
        dlg.geometry("1280x780")
        dlg.transient(getattr(self, "root", None))

        self._hc_dlg = dlg
        self._hc_kill_flag = False
        self._hc_all_results = {}   # code → result dict
        self._hc_cards = {}         # code → (card_frame, result)
        self._hc_queue = _queue.Queue()

        # 顶栏
        top = tk.Frame(dlg, bg="#F8FAFC", height=50)
        top.pack(fill=tk.X)
        tk.Label(top, text="💼 持仓检测", font=("", 14, "bold"),
                 bg="#F8FAFC").pack(side=tk.LEFT, padx=12, pady=8)

        self._hc_status = tk.StringVar(value="⏳ 准备中...")
        tk.Label(top, textvariable=self._hc_status,
                 foreground="blue", bg="#F8FAFC").pack(side=tk.LEFT, padx=12)

        # 控制面板
        ctrl = tk.LabelFrame(dlg, text="🎛️ 扫描控制", padx=6, pady=6)
        ctrl.pack(fill=tk.X, padx=8, pady=4)

        btn1_row = tk.Frame(ctrl)
        btn1_row.pack(fill=tk.X, pady=(2, 4))
        self._hc_kill_btn = ttk.Button(btn1_row, text="⏹ 停止",
                                       command=lambda: setattr(self, "_hc_kill_flag", True),
                                       state=tk.DISABLED)
        self._hc_kill_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="💾 保存结果",
                   command=self._hc_save_to_db).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="🖼 存图片",
                   command=self._hc_save_as_image).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="📜 历史回看",
                   command=self._hc_open_history).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn1_row, text="🔄 重扫全部",
                   command=lambda: self._hc_rescan_all()).pack(side=tk.LEFT, padx=4)

        # 进度条 + 统计
        prog_row = tk.Frame(ctrl)
        prog_row.pack(fill=tk.X, pady=(0, 4))
        self._hc_progress = ttk.Progressbar(prog_row, mode="determinate", length=300)
        self._hc_progress.pack(side=tk.LEFT, padx=(0, 8))
        self._hc_step_label = tk.Label(prog_row, text="就绪", fg="#666")
        self._hc_step_label.pack(side=tk.LEFT)

        # Notebook: 实时扫描 + 历史回看
        nb = ttk.Notebook(dlg)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Tab 1: 实时扫描
        tab_realtime = ttk.Frame(nb)
        nb.add(tab_realtime, text="实时扫描")

        # 卡片网格
        outer = tk.Frame(tab_realtime)
        outer.pack(fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(outer)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._hc_canvas = tk.Canvas(outer, bg="#F8FAFC", highlightthickness=0,
                                    yscrollcommand=sb.set)
        self._hc_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.configure(command=self._hc_canvas.yview)

        self._hc_card_frame = tk.Frame(self._hc_canvas, bg="#F8FAFC")
        self._hc_canvas.create_window((0, 0), window=self._hc_card_frame, anchor="nw")
        self._hc_card_frame.bind("<Configure>",
                                 lambda e: self._hc_canvas.configure(scrollregion=self._hc_canvas.bbox("all")))

        # Tab 2: 历史回看
        tab_history = ttk.Frame(nb)
        nb.add(tab_history, text="📜 历史回看")

        self._hc_history_listbox = tk.Listbox(tab_history)
        self._hc_history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._hc_history_listbox.bind("<<ListboxSelect>>", lambda e: self._hc_load_history())
        self._hc_history_refresh_btn = ttk.Button(tab_history, text="🔄 刷新",
                                                  command=self._hc_refresh_history)
        self._hc_history_refresh_btn.pack(side=tk.RIGHT, padx=8, pady=8)

        # 初始化数据库
        self._hc_db_init()
        self._hc_refresh_history_list()

    # ═══════════════════════════════════════════════════════════
    # 后台扫描线程
    # ═══════════════════════════════════════════════════════════

    def _hc_run_scan(self, pairs):
        """后台线程: 逐只跑 AKShare + analyze_trading_stage"""
        import akshare as ak

        N = len(pairs)
        self._hc_kill_flag = False
        self._hc_kill_btn.configure(state=tk.NORMAL)
        self._hc_progress.configure(maximum=N, value=0)

        def _worker(q):
            for i, (name, code, gidx) in enumerate(pairs):
                if self._hc_kill_flag:
                    q.put(("killed", i, N))
                    return
                q.put(("log", f"🔍 [{i+1}/{N}] {name}({code})..."))

                df = fund_df = None
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=code, period="daily",
                        start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"),
                        adjust="qfq"
                    )
                except Exception:
                    pass
                try:
                    fund_df = ak.stock_fund_stock_holder(symbol=code)
                except Exception:
                    pass

                analyze = None
                price = 0.0
                err = None
                if df is not None and len(df) >= 60:
                    try:
                        analyze = analyze_trading_stage(df, fund_df)
                        price = float(df.iloc[-1]["收盘"])
                    except Exception as e:
                        err = f"分析异常: {e}"
                else:
                    err = f"K线不足 ({len(df) if df is not None else 0}行)"

                q.put(("result", {
                    "name": name, "code": code, "group": gidx,
                    "price": price, "analyze": analyze, "error": err,
                    "index": i, "total": N,
                }))

            q.put(("done", N, N))

        threading.Thread(target=_worker, args=(self._hc_queue,), daemon=True).start()
        self._hc_poll_queue(self._hc_queue, N)

    def _hc_poll_queue(self, q, N):
        """主线程轮询 Queue"""
        try:
            while True:
                msg = q.get_nowait()
                kind = msg[0]

                if kind == "log":
                    self._hc_status.set(msg[1])

                elif kind == "result":
                    r = msg[1]
                    self._hc_all_results[r["code"]] = r
                    self._hc_render_one_card(r)
                    self._hc_step_label.configure(text=f"[{r['index']+1}/{N}] 已完成")

                elif kind == "killed":
                    step_val, tot = msg[1], msg[2]
                    self._hc_progress.configure(value=step_val)
                    self._hc_step_label.configure(text=f"[⏹] 用户停止 {step_val}/{tot}")
                    self._hc_kill_btn.configure(state=tk.DISABLED)
                    return

                elif kind == "done":
                    self._hc_progress.configure(value=N)
                    self._hc_step_label.configure(text=f"[100%] 扫描完成 {N}/{N}")
                    self._hc_status.set(f"✅ 全部完成 — {len(self._hc_all_results)}/{N} 只")
                    self._hc_kill_btn.configure(state=tk.DISABLED)
                    return

        except _queue.Empty:
            pass
        except Exception as e:
            print(f"[持仓检测] poll_queue 异常: {e}")

        if self._hc_dlg and self._hc_dlg.winfo_exists():
            self._hc_dlg.after(80, lambda: self._hc_poll_queue(q, N))

    # ═══════════════════════════════════════════════════════════
    # 卡片渲染
    # ═══════════════════════════════════════════════════════════

    def _hc_render_one_card(self, r):
        """渲染一张持仓检测卡片"""
        try:
            name, code = r["name"], r["code"]
            a = r.get("analyze")
            err = r.get("error")

            # 已有则删旧的
            if code in self._hc_cards:
                old, _ = self._hc_cards[code]
                try:
                    old.destroy()
                except Exception:
                    pass
                del self._hc_cards[code]

            cols = max(3, min(5, (self._hc_canvas.winfo_width() or 1000) // 240))
            cell_w, cell_h = 220, 220

            existing = list(self._hc_cards.values())
            idx = len(existing)
            row, col = divmod(idx, cols)

            _FALLBACK = {
                "吸筹": ("#FFF9E6", "#D4A017"), "洗盘": ("#E6F3FF", "#3B82F6"),
                "拉升": ("#E6FFE6", "#22C55E"), "出货": ("#FFE6E6", "#EF4444"),
                "下跌": ("#F5F5F5", "#6B7280"), "底部横盘": ("#FAF5FF", "#8B5CF6"),
            }
            if a is None:
                bg, tag_color, stage = "#FEE2E2", "#991B1B", "❌失败"
            else:
                stage = a.get("stage", "?")
                bg, tag_color = a.get("background_color", _FALLBACK.get(stage, ("#FFFFFF", "#333")))
                tag_color = a.get("tag_color", tag_color)

            card = tk.Frame(self._hc_card_frame, bg=bg, width=cell_w, height=cell_h,
                            highlightbackground=tag_color, highlightthickness=2,
                            cursor="hand2")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            card.pack_propagate(False)

            # 右上角标签
            top_right = tk.Frame(card, bg=tag_color)
            top_right.place(relx=0.98, rely=0, anchor="ne", y=4, x=-4)
            tk.Label(top_right, text=stage, bg=tag_color, fg="white",
                     font=("", 9, "bold"), padx=6, pady=1).pack(side=tk.LEFT)

            # 名称 + 代码
            tk.Label(card, text=name, bg=bg, font=("", 12, "bold"),
                     anchor="w").pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=code, bg=bg, font=("", 9), fg="#666",
                     anchor="w").pack(anchor="w", padx=8)

            if a is not None:
                # 机构/游资
                inst = a.get("institution_vs_hot_money", "")
                inst_color = "#1E40AF" if "机构" in inst else "#DC2626" if "游资" in inst else "#6B7280"
                tk.Label(card, text=f"🏛 {inst}({a.get('institution_score', 0)})",
                         bg=bg, fg=inst_color, font=("", 9, "bold"),
                         anchor="w").pack(anchor="w", padx=8, pady=(2, 0))

                # 价格 + MA
                d = a.get("detail", {})
                tk.Label(card, text=f"¥{d.get('close','?')}  MA5={d.get('ma5','?')}  MA20={d.get('ma20','?')}",
                         bg=bg, font=("", 9), fg="#333",
                         anchor="w").pack(anchor="w", padx=8)

                # 涨跌幅工具函数 (闭包内)
                def _pct_color(val):
                    try:
                        v = float(val)
                        if v > 0: return "#DC2626"
                        if v < 0: return "#16A34A"
                        return "#666666"
                    except Exception:
                        return "#666666"

                def _fmt(val, n=2):
                    if val is None: return "--"
                    try:
                        return f"{float(val):+.{n}f}%"
                    except Exception:
                        return "--"

                # 当日 + 5日
                r1, r5 = a.get("ret1_pct"), a.get("ret5_pct")
                row_r1 = tk.Frame(card, bg=bg)
                row_r1.pack(anchor="w", padx=8)
                tk.Label(row_r1, text="当日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r1, text=_fmt(r1), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r1)).pack(side=tk.LEFT, padx=(0, 10))
                tk.Label(row_r1, text="5日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r1, text=_fmt(r5), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r5)).pack(side=tk.LEFT)

                # 10日 + 20日 + 📍位置
                r10, r20 = a.get("ret10_pct"), a.get("ret20_pct")
                row_r2 = tk.Frame(card, bg=bg)
                row_r2.pack(anchor="w", padx=8)
                tk.Label(row_r2, text="10日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r2, text=_fmt(r10), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r10)).pack(side=tk.LEFT, padx=(0, 10))
                tk.Label(row_r2, text="20日:", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r2, text=_fmt(r20, 1), bg=bg, font=("", 9, "bold"),
                         fg=_pct_color(r20)).pack(side=tk.LEFT, padx=(0, 10))
                tk.Label(row_r2, text="📍", bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)
                tk.Label(row_r2, text=f"{a.get('pos_range_pct','?')}%",
                         bg=bg, font=("", 9), fg="#333").pack(side=tk.LEFT)

            else:
                tk.Label(card, text=f"❌ {err or '分析失败'}", bg=bg, font=("", 9),
                         fg="#991B1B", anchor="w").pack(anchor="w", padx=8, pady=(6, 0))

            # 绑定事件: 单击详情, 双击 K 线
            click_timer = {"id": None}
            def _on_click(e, _r=r):
                if click_timer["id"]:
                    self._hc_dlg.after_cancel(click_timer["id"])
                    click_timer["id"] = None
                click_timer["id"] = self._hc_dlg.after(260, lambda: self._hc_show_detail(_r))

            def _on_dblclick(e, _r=r):
                if click_timer["id"]:
                    self._hc_dlg.after_cancel(click_timer["id"])
                    click_timer["id"] = None
                self._hc_open_kline(_r)

            for w in [card] + [c for c in card.winfo_children()]:
                w.bind("<Button-1>", _on_click)
                w.bind("<Double-Button-1>", _on_dblclick)

            self._hc_cards[code] = (card, r)

        except Exception as e:
            print(f"[持仓检测] render_card 异常: {e}")
            traceback.print_exc()

    # ═══════════════════════════════════════════════════════════
    # 单击 → 详情面板
    # ═══════════════════════════════════════════════════════════

    def _hc_show_detail(self, r):
        """单击 → 详情面板 (阶段/均线/信号/原因)"""
        a = r.get("analyze")
        if not a:
            return
        dlg = tk.Toplevel(self._hc_dlg)
        dlg.title(f"📋 {r['name']}({r['code']}) — 详情")
        dlg.geometry("520x560")
        dlg.transient(self._hc_dlg)
        try:
            dlg.grab_set()
        except Exception:
            pass

        bg = a.get("background_color", "#FFFFFF")
        fg = a.get("tag_color", "#333333")

        tk.Label(dlg, text=f"{r['name']} ({r['code']})", font=("", 14, "bold")).pack(pady=(10, 4))
        tk.Label(dlg, text=f"💰 价格: ¥{r.get('price', '?')}   📊 阶段: {a.get('stage')}   得分: {a.get('stage_score')}",
                 font=("", 10)).pack(pady=2)

        text = tk.Text(dlg, wrap="word", font=("", 10), padx=12, pady=8)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        d = a.get("detail", {})
        lines = [
            f"【基本信息】",
            f"  收盘: {d.get('close')}  MA5: {d.get('ma5')}  MA10: {d.get('ma10')}  MA20: {d.get('ma20')}  MA60: {d.get('ma60')}",
            f"  60日高/低: {d.get('high60')} / {d.get('low60')}  位置: {a.get('pos_range_pct')}%",
            f"",
            f"【涨跌幅】",
            f"  当日: {a.get('ret1_pct', '--')}%  5日: {a.get('ret5_pct', '--')}%  10日: {a.get('ret10_pct', '--')}%",
            f"  20日: {a.get('ret20_pct', '--')}%  60日: {a.get('ret60_pct', '--')}%",
            f"",
            f"【均线状态】",
            f"  排列: {a.get('ma_status', {}).get('排列', '--')}  趋势: {a.get('trend')}",
            f"",
            f"【量能】",
            f"  状态: {a.get('volume_status', {}).get('state', '--')}  量比: {a.get('volume_status', {}).get('vratio', '--')}",
            f"",
            f"【机构/游资】",
            f"  属性: {a.get('institution_vs_hot_money')}  机构分: {a.get('institution_score')}  游资分: {a.get('hot_money_score')}",
            f"",
            f"【K线形态】{a.get('kline_pattern', '--')}",
            f"",
            f"【关键信号】",
        ]
        for sig in a.get("signals", []):
            lines.append(f"  • {sig}")

        text.insert("1.0", "\n".join(lines))
        text.configure(state=tk.DISABLED)

        btn_bar = tk.Frame(dlg)
        btn_bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_bar, text="📈 K线图+一目均衡",
                   command=lambda: self._hc_open_kline(r)).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_bar, text="🔄 重跑",
                   command=lambda: self._hc_rescan_one(r['code'])).pack(side=tk.LEFT)

    # ═══════════════════════════════════════════════════════════
    # 双击 → K线 + 一目均衡图
    # ═══════════════════════════════════════════════════════════

    def _hc_open_kline(self, r):
        """双击 → 开 K 线图 (复用主程序的K线方法)"""
        code = r["code"]
        name = r["name"]
        import re as _re
        m = _re.search(r"(\d{6})", str(code))
        if not m:
            tk.messagebox.showerror("❌", f"无效代码: {code}")
            return
        c6 = m.group(1)
        # 优先复用主程序已有的 K 线打开方法
        for attr in ("_open_kline_with_ichimoku", "_open_daily_kline", "_show_kline_chart",
                     "_open_kline_chart", "open_kline_dialog"):
            if hasattr(self, attr):
                try:
                    getattr(self, attr)(c6, name)
                    return
                except Exception as e:
                    print(f"[持仓检测] 尝试 {attr} 失败: {e}")
        # 最终兜底: 简单提示
        tk.messagebox.showinfo("K线", f"请在主界面双击 {name}({c6}) 查看 K 线图")

    # ═══════════════════════════════════════════════════════════
    # 💾 数据库 + 📜 历史复盘
    # ═══════════════════════════════════════════════════════════

    def _hc_db_path(self):
        p = os.path.join(os.getcwd(), "data", "stock_analysis.db")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def _hc_db_init(self):
        conn = _sq.connect(self._hc_db_path())
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holding_check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                scope TEXT,
                stock_count INTEGER,
                json_data TEXT,
                note TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _hc_save_to_db(self):
        """💾 保存当前持仓检测结果"""
        if not self._hc_all_results:
            self._hc_status.set("⚠️ 没有结果可保存")
            return
        try:
            self._hc_db_init()
            conn = _sq.connect(self._hc_db_path())
            slim = []
            for code, r in self._hc_all_results.items():
                a = r.get("analyze")
                if not a:
                    continue
                slim.append({
                    "code": code, "name": r["name"],
                    "price": r.get("price"),
                    "stage": a.get("stage"),
                    "stage_score": a.get("stage_score"),
                    "ret1_pct": a.get("ret1_pct"),
                    "ret5_pct": a.get("ret5_pct"),
                    "ret10_pct": a.get("ret10_pct"),
                    "ret20_pct": a.get("ret20_pct"),
                    "ret60_pct": a.get("ret60_pct"),
                    "pos_range_pct": a.get("pos_range_pct"),
                    "institution_vs_hot_money": a.get("institution_vs_hot_money"),
                    "trend": a.get("trend"),
                    "ma_arrange": a.get("ma_status", {}).get("排列"),
                    "signals": a.get("signals", []),
                })
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO holding_check_history (ts, scope, stock_count, json_data, note) VALUES (?,?,?,?,?)",
                (ts, "持仓检测", len(slim), json.dumps(slim, ensure_ascii=False), "")
            )
            conn.commit()
            new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            self._hc_status.set(f"✅ 已保存到 DB #{new_id} ({len(slim)}只)")
            self._hc_refresh_history_list()
        except Exception as e:
            self._hc_status.set(f"❌ 保存失败: {e}")
            traceback.print_exc()

    def _hc_list_history(self):
        conn = _sq.connect(self._hc_db_path())
        rows = conn.execute(
            "SELECT id, ts, scope, stock_count FROM holding_check_history ORDER BY id DESC"
        ).fetchall()
        conn.close()
        return rows

    def _hc_refresh_history_list(self):
        """刷新历史回看列表 Tab"""
        try:
            rows = self._hc_list_history()
            if not hasattr(self, "_hc_history_listbox"):
                return
            self._hc_history_listbox.delete(0, tk.END)
            for rid, ts, scope, cnt in rows:
                self._hc_history_listbox.insert(tk.END, f"#{rid}  {ts}  {scope}  {cnt}只")
        except Exception:
            pass

    def _hc_open_history(self):
        """切到历史回看 Tab"""
        try:
            nb = self._hc_dlg.nametowidget(self._hc_dlg.winfo_children()[0])
        except Exception:
            return
        for i in range(nb.index("end")):
            if nb.tab(i, "text").startswith("📜"):
                nb.select(i)
                self._hc_refresh_history_list()
                return

    def _hc_load_history(self):
        """选中历史记录 → 恢复卡片"""
        sel = self._hc_history_listbox.curselection()
        if not sel:
            return
        text = self._hc_history_listbox.get(sel[0])
        m = re.match(r"#(\d+)", text)
        if not m:
            return
        row_id = int(m.group(1))
        try:
            conn = _sq.connect(self._hc_db_path())
            row = conn.execute("SELECT json_data FROM holding_check_history WHERE id=?", (row_id,)).fetchone()
            conn.close()
            if not row:
                return
            data = json.loads(row[0])
            # 清空现有卡片
            for w in self._hc_card_frame.winfo_children():
                w.destroy()
            self._hc_cards.clear()
            self._hc_all_results.clear()
            # 恢复
            for item in data:
                self._hc_all_results[item["code"]] = {
                    "name": item["name"], "code": item["code"],
                    "price": item.get("price", 0), "analyze": item,
                }
                self._hc_render_one_card(self._hc_all_results[item["code"]])
            self._hc_status.set(f"📜 已加载 #{row_id} ({len(data)}只)")
        except Exception as e:
            self._hc_status.set(f"❌ 加载失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # 辅助: 存图 / 存文 / 重扫
    # ═══════════════════════════════════════════════════════════

    def _hc_save_as_image(self):
        """存图片 (Canvas screenshot)"""
        try:
            self._hc_canvas.postscript(file="holding_check.ps", colormode="color")
            self._hc_status.set("📸 已存为 holding_check.ps")
        except Exception as e:
            self._hc_status.set(f"❌ 存图失败: {e}")

    def _hc_save_as_text(self):
        """存文字 (CSV)"""
        if not self._hc_all_results:
            self._hc_status.set("⚠️ 无结果")
            return
        import csv
        path = f"holding_check_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["代码", "名称", "阶段", "得分", "当日%", "5日%", "10日%", "20日%", "60日%",
                            "位置%", "排列", "趋势", "属性"])
                for code, r in self._hc_all_results.items():
                    a = r.get("analyze") or {}
                    w.writerow([
                        code, r.get("name", ""), a.get("stage", ""), a.get("stage_score", ""),
                        a.get("ret1_pct", ""), a.get("ret5_pct", ""), a.get("ret10_pct", ""),
                        a.get("ret20_pct", ""), a.get("ret60_pct", ""),
                        a.get("pos_range_pct", ""),
                        a.get("ma_status", {}).get("排列", ""), a.get("trend", ""),
                        a.get("institution_vs_hot_money", ""),
                    ])
            self._hc_status.set(f"📄 已存 CSV: {path}")
        except Exception as e:
            self._hc_status.set(f"❌ 存文失败: {e}")

    def _hc_rescan_all(self):
        """重扫全部 (复用现有 pairs)"""
        pairs = []
        seen = set()
        for code, r in self._hc_all_results.items():
            if code not in seen:
                seen.add(code)
                pairs.append((r["name"], code, r.get("group", 1)))
        if pairs:
            # 清空卡片
            for w in self._hc_card_frame.winfo_children():
                w.destroy()
            self._hc_cards.clear()
            self._hc_all_results.clear()
            self._hc_run_scan(pairs)

    def _hc_rescan_one(self, code):
        """重扫单只"""
        existing = self._hc_all_results.get(code)
        if not existing:
            return
        self._hc_status.set(f"🔄 重扫 {existing['name']}({code})...")
        import akshare as ak

        def _worker():
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code, period="daily",
                    start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"), adjust="qfq"
                )
                fund_df = None
                try:
                    fund_df = ak.stock_fund_stock_holder(symbol=code)
                except Exception:
                    pass
                a = analyze_trading_stage(df, fund_df) if df is not None and len(df) >= 60 else None
                price = float(df.iloc[-1]["收盘"]) if df is not None and len(df) >= 60 else 0
                result = {"name": existing["name"], "code": code, "price": price,
                          "analyze": a, "error": None, "group": existing.get("group", 1)}
                self._hc_dlg.after(0, lambda: self._hc_render_one_card(result))
                self._hc_dlg.after(0, lambda: self._hc_status.set(f"✅ {existing['name']} 重扫完成"))
            except Exception as e:
                self._hc_dlg.after(0, lambda: self._hc_status.set(f"❌ 重扫失败: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

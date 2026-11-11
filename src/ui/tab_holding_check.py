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

import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk

# 顶部 try-import: 让 import 失败能被捕获并上报
try:
    import akshare as _ak_module
    _HC_AK_OK = True
except Exception as _e:
    _HC_AK_OK = False
    _HC_AK_ERR = str(_e)
    print(f"⚠️ [持仓检测] akshare 导入失败: {_e}")

# 导入 analyze_trading_stage
try:
    from .tab_tech_stage import analyze_trading_stage as _HC_analyze
    _HC_ANALYZE_OK = True
except ImportError:
    try:
        from tab_tech_stage import analyze_trading_stage as _HC_analyze
        _HC_ANALYZE_OK = True
    except Exception as _e:
        _HC_ANALYZE_OK = False
        print(f"⚠️ [持仓检测] analyze_trading_stage 导入失败: {_e}")


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

        def _get_holding_list(gi):
            """gi=1 叫 holding_stocks (无后缀), 其他叫 holding_stocks_{gi}"""
            name = "holding_stocks" if gi == 1 else f"holding_stocks_{gi}"
            return getattr(self, name, [None] * 80)

        _selected = {gi: tk.BooleanVar(value=(gi == 1)) for gi, _ in _GROUP_MAP}
        _counts = {}
        for gi, _ in _GROUP_MAP:
            hs = _get_holding_list(gi)
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
        def _get_holding_list(gi):
            name = "holding_stocks" if gi == 1 else f"holding_stocks_{gi}"
            return getattr(self, name, [None] * 80)

        pairs = []
        seen = set()
        debug_counts = {}
        for gi in group_indices:
            hs = _get_holding_list(gi)
            _cnt = 0
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
                        _cnt += 1
            debug_counts[gi] = _cnt

        # 🎯 调试输出 —— 帮用户排查
        print(f"\n{'='*60}")
        print(f"[💼持仓检测] _hc_scan_groups 调试")
        print(f"  选择组: {group_indices}")
        for gi, cnt in debug_counts.items():
            name_attr = "holding_stocks" if gi == 1 else f"holding_stocks_{gi}"
            print(f"  gi={gi} → getattr({name_attr}) → {cnt} 只")
        print(f"  最终 pairs: {len(pairs)} 只")
        for name, c, gi in pairs[:5]:
            print(f"    [{gi}] {name}({c})")
        if len(pairs) > 5:
            print(f"    ... 还有 {len(pairs)-5} 只")
        print(f"{'='*60}\n")

        print(f"💼 [持仓检测] groups={group_indices} → {len(pairs)} 只 (去重后)")

        if not pairs:
            tk.messagebox.showinfo("提示", "所选标签页均为空!")
            return

        # 🛡 启动前自检 —— 防止弹窗空白
        errs = []
        if not _HC_AK_OK:
            errs.append(f"akshare 导入失败: {_HC_AK_ERR}")
        if not _HC_ANALYZE_OK:
            errs.append("analyze_trading_stage 导入失败")
        if errs:
            tk.messagebox.showerror("❌ 依赖缺失",
                                   "持仓检测无法启动:\n\n" + "\n".join(errs))
            return

        print(f"\n{'='*60}")
        print(f"[💼持仓检测] ✅ 自检通过: akshare + analyze_trading_stage 就绪")
        print(f"{'='*60}\n")

        try:
            self._hc_show_dialog()
        except Exception as _e:
            tk.messagebox.showerror("❌ 弹窗创建失败", traceback.format_exc())
            return

        try:
            self._hc_status.set(f"📊 已选 {len(group_indices)} 组 → {len(pairs)} 只")
            self._hc_run_scan(pairs)
        except Exception as _e:
            tk.messagebox.showerror("❌ 扫描启动失败", traceback.format_exc())
            traceback.print_exc()

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
        import akshare as ak  # 局部 import 备用

        N = len(pairs)
        try:
            self._hc_kill_flag = False
            self._hc_kill_btn.configure(state=tk.NORMAL)
            self._hc_progress.configure(maximum=N, value=0)
            self._hc_status.set(f"🔄 正在初始化 {N} 只...")
        except Exception as e:
            print(f"❌ [持仓检测] 初始化 UI 控件失败: {e}")

        print(f"\n[💼持仓检测] _hc_run_scan 启动, N={N}")

        # worker 线程
        def _worker(q):
            print(f"[💼持仓检测] 🧵 worker 线程启动! pairs[0]={pairs[0] if pairs else 'EMPTY'}")
            try:
                q.put(("log", f"🚀 worker 线程已启动, 准备扫描 {N} 只..."))
            except Exception:
                pass

            for i, (name, code, gidx) in enumerate(pairs):
                try:
                    if self._hc_kill_flag:
                        q.put(("killed", i, N))
                        print(f"[💼持仓检测] worker 被用户停止 @ {i}")
                        return

                    q.put(("log", f"🔍 [{i+1}/{N}] {name}({code})..."))

                    df = fund_df = None
                    try:
                        df = _ak_module.stock_zh_a_hist(
                            symbol=code, period="daily",
                            start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                            end_date=datetime.now().strftime("%Y%m%d"),
                            adjust="qfq"
                        )
                        print(f"[💼持仓检测] [{i+1}/{N}] {name} akshare 返回 {len(df) if df is not None else 0} 行")
                    except Exception as e:
                        print(f"[💼持仓检测] [{i+1}/{N}] {name} akshare 失败: {e}")
                        traceback.print_exc()

                    try:
                        fund_df = _ak_module.stock_fund_stock_holder(symbol=code)
                    except Exception:
                        pass

                    analyze = None
                    price = 0.0
                    err = None
                    if df is not None and len(df) >= 60:
                        try:
                            analyze = _HC_analyze(df, fund_df)
                            price = float(df.iloc[-1]["收盘"])
                            print(f"[💼持仓检测] [{i+1}/{N}] {name} analyze ✅ stage={analyze.get('stage')}")
                        except Exception as e:
                            err = f"分析异常: {e}"
                            print(f"[💼持仓检测] [{i+1}/{N}] {name} analyze ❌: {e}")
                            traceback.print_exc()
                    else:
                        err = f"K线不足 ({len(df) if df is not None else 0}行)"
                        print(f"[💼持仓检测] [{i+1}/{N}] {name} K线不足: {err}")

                    _df_tail = None
                    if df is not None and len(df) >= 60:
                        try:
                            dft = df.tail(200).reset_index(drop=True)
                            _df_tail = [
                                {"date": str(r.get("日期", "")), "open": float(r.get("开盘", 0)),
                                 "high": float(r.get("最高", 0)), "low": float(r.get("最低", 0)),
                                 "close": float(r.get("收盘", 0)), "vol": float(r.get("成交量", 0))}
                                for _, r in dft.iterrows()
                            ]
                        except Exception:
                            _df_tail = None

                    q.put(("result", {
                        "name": name, "code": code, "group": gidx,
                        "price": price, "analyze": analyze, "error": err,
                        "index": i, "total": N, "df_tail": _df_tail,
                    }))

                except Exception as loop_err:
                    # 单只股票出问题不影响整体
                    print(f"[💼持仓检测] [{i+1}/{N}] {name} 循环异常: {loop_err}")
                    traceback.print_exc()
                    q.put(("result", {
                        "name": name, "code": code, "group": gidx,
                        "price": 0, "analyze": None, "error": str(loop_err),
                        "index": i, "total": N, "df_tail": None,
                    }))

            print(f"[💼持仓检测] worker 循环结束, 发送 done 消息")
            try:
                q.put(("done", N, N))
            except Exception:
                pass

        # 启动线程 —— 这行也包 try-except
        try:
            t = threading.Thread(target=_worker, args=(self._hc_queue,), daemon=True)
            t.start()
            print(f"[💼持仓检测] ✅ worker 线程已创建 (pid={t.ident})")
        except Exception as e:
            print(f"❌ [持仓检测] 线程创建失败: {e}")
            tk.messagebox.showerror("❌ 线程创建失败", traceback.format_exc())
            return

        # 立即调 poll_queue —— 也包 try-except
        try:
            self._hc_poll_queue(self._hc_queue, N)
        except Exception as e:
            print(f"❌ [持仓检测] poll_queue 启动失败: {e}")
            traceback.print_exc()

    def _hc_poll_queue(self, q, N):
        """主线程轮询 Queue + 更新进度条"""
        try:
            # 用 try-while 一次性把 Queue 里所有可用消息都取走
            got_any = False
            while True:
                try:
                    msg = q.get_nowait()
                    got_any = True
                except _queue.Empty:
                    break

                kind = msg[0]

                if kind == "log":
                    try:
                        self._hc_status.set(msg[1])
                    except Exception:
                        pass

                elif kind == "result":
                    r = msg[1]
                    self._hc_all_results[r["code"]] = r
                    done = r["index"] + 1
                    try:
                        self._hc_render_one_card(r)
                        self._hc_progress.configure(value=done)
                        self._hc_step_label.configure(text=f"[{done}/{N}] 已完成")
                        self._hc_status.set(f"✅ {r['name']}({r['code']}) — {done}/{N} ({100*done//N}%)")
                    except Exception as e:
                        print(f"[💼持仓检测] render/UI 更新失败: {e}")
                        traceback.print_exc()
                    print(f"[💼持仓检测] poll result: [{done}/{N}] {r['name']} stage={r.get('analyze',{}).get('stage') if r.get('analyze') else r.get('error')}")

                elif kind == "killed":
                    try:
                        step_val, tot = msg[1], msg[2]
                        self._hc_progress.configure(value=step_val)
                        self._hc_step_label.configure(text=f"[⏹] 用户停止 {step_val}/{tot}")
                        self._hc_kill_btn.configure(state=tk.DISABLED)
                    except Exception:
                        pass
                    return

                elif kind == "done":
                    try:
                        self._hc_progress.configure(value=N)
                        self._hc_step_label.configure(text=f"[100%] 扫描完成 {N}/{N}")
                        self._hc_status.set(f"✅ 全部完成 — {len(self._hc_all_results)}/{N} 只")
                        self._hc_kill_btn.configure(state=tk.DISABLED)
                    except Exception:
                        pass
                    print(f"[💼持仓检测] ✅ poll done: {len(self._hc_all_results)}/{N}")
                    return

            # 队列暂时空了 → 80ms 后再 poll
            if self._hc_dlg and self._hc_dlg.winfo_exists():
                self._hc_dlg.after(80, lambda: self._hc_poll_queue(q, N))
            else:
                print(f"[💼持仓检测] poll_queue 停止 (dlg 已关闭)")

        except Exception as e:
            print(f"❌ [持仓检测] poll_queue 异常: {e}")
            traceback.print_exc()
            # 即使异常也不放弃, 继续调度
            try:
                if self._hc_dlg and self._hc_dlg.winfo_exists():
                    self._hc_dlg.after(200, lambda: self._hc_poll_queue(q, N))
            except Exception:
                pass

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
            cell_w, cell_h = 220, 260

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

            # ── 底部操作按钮行 ──
            btn_bar = tk.Frame(card, bg=bg)
            btn_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=4)
            # 🔍一键诊断
            _b1 = tk.Button(btn_bar, text="🔍诊断", command=lambda _r=r: self._hc_diagnose_dialog(_r),
                            relief=tk.FLAT, bg="#DBEAFE", fg="#1E40AF",
                            font=("", 8, "bold"), padx=6, pady=1, cursor="hand2")
            _b1.pack(side=tk.LEFT, padx=2)
            # 📈K线
            _b2 = tk.Button(btn_bar, text="📈K线", command=lambda _r=r: self._hc_open_kline(_r),
                            relief=tk.FLAT, bg="#DCFCE7", fg="#166534",
                            font=("", 8, "bold"), padx=6, pady=1, cursor="hand2")
            _b2.pack(side=tk.LEFT, padx=2)
            # ↻ 重扫
            _b3 = tk.Button(btn_bar, text="↻", command=lambda _r=r: self._hc_rescan_one(_r["code"]),
                            relief=tk.FLAT, bg="#F3F4F6", fg="#6B7280",
                            font=("", 9), padx=4, pady=1, cursor="hand2")
            _b3.pack(side=tk.RIGHT, padx=2)

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

    # ═══════════════════════════════════════════════════════════
    # 🔍 一键诊断 —— 完整面板 (阶段/均线/信号 + K线图 + 一目均衡)
    # ═══════════════════════════════════════════════════════════

    def _hc_diagnose_dialog(self, r):
        """🔍 一键诊断: 左侧详情 + 右侧嵌入式 K 线 + 一目均衡表"""
        a = r.get("analyze")
        if not a:
            tk.messagebox.showwarning("提示", "该股票分析数据不可用")
            return

        dlg = tk.Toplevel(self._hc_dlg)
        dlg.title(f"🔍一键诊断 — {r['name']}({r['code']})")
        dlg.geometry("1180x780")
        try:
            dlg.transient(self._hc_dlg)
            dlg.grab_set()
        except Exception:
            pass

        # ═══ 顶部标题栏 ═══
        header_bg = a.get("tag_color", "#1E40AF")
        header = tk.Frame(dlg, bg=header_bg, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"🔍 {r['name']} ({r['code']})",
                 bg=header_bg, fg="white",
                 font=("", 16, "bold")).pack(side=tk.LEFT, padx=14, pady=10)
        tk.Label(header, text=f"🎯 阶段: {a.get('stage','--')}  "
                              f"得分: {a.get('stage_score','--')}  "
                              f"💰 ¥{r.get('price','--')}",
                 bg=header_bg, fg="white",
                 font=("", 11)).pack(side=tk.LEFT, padx=14)

        # ═══ 主体 PanedWindow 左右分割 ═══
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── 左栏: 详情面板 ──
        left = tk.Frame(pw, bg="#F8FAFC")
        pw.add(left, weight=1)
        self._hc_diagnose_left(left, r, a)

        # ── 右栏: K线 + 一目均衡 ──
        right = tk.Frame(pw, bg="#FFFFFF")
        pw.add(right, weight=3)

        # 先放一个 Loading 提示, 后台画好再替换
        loading = tk.Label(right, text="📊 正在加载 K 线图 + 一目均衡表...",
                           font=("", 11), fg="#666", bg="#FFFFFF")
        loading.pack(expand=True)

        # 后台线程: 准备 df 并画图
        df_tail = r.get("df_tail")
        threading.Thread(
            target=self._hc_diagnose_draw_chart,
            args=(right, r, df_tail, loading),
            daemon=True,
        ).start()

        # ═══ 底部操作栏 ═══
        bot = tk.Frame(dlg, bg="#F1F5F9", height=44)
        bot.pack(fill=tk.X, side=tk.BOTTOM)
        bot.pack_propagate(False)
        ttk.Button(bot, text="📈 独立 K 线窗口",
                   command=lambda: self._hc_open_kline(r)).pack(side=tk.LEFT, padx=10, pady=8)
        ttk.Button(bot, text="🔄 重扫此股",
                   command=lambda: self._hc_rescan_one(r["code"])).pack(side=tk.LEFT, padx=10, pady=8)
        ttk.Button(bot, text="💾 保存本次到 DB",
                   command=self._hc_save_to_db).pack(side=tk.LEFT, padx=10, pady=8)
        ttk.Button(bot, text="关闭",
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=10, pady=8)

    # ── 左栏: 详情 ──

    def _hc_diagnose_left(self, parent, r, a):
        """左栏: 阶段/均线/信号/涨跌幅汇总"""
        # 滚动容器
        outer = tk.Frame(parent, bg="#F8FAFC")
        outer.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(outer)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(outer, bg="#F8FAFC", highlightthickness=0,
                           yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.configure(command=canvas.yview)
        body = tk.Frame(canvas, bg="#F8FAFC")
        canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _section(title, color="#1E40AF"):
            """小工具: 画一个区块标题"""
            f = tk.Frame(body, bg="#F8FAFC")
            f.pack(fill=tk.X, padx=8, pady=(8, 2))
            tk.Label(f, text=f"▌ {title}", bg="#F8FAFC", fg=color,
                     font=("", 11, "bold")).pack(side=tk.LEFT)
            tk.Frame(body, bg="#CBD5E1", height=1).pack(fill=tk.X, padx=8)
            return f

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

        bg_body = "#FFFFFF"

        # ① 阶段
        _section("🎯 操盘阶段", "#DC2626")
        f1 = tk.Frame(body, bg=bg_body, relief=tk.FLAT)
        f1.pack(fill=tk.X, padx=8, pady=4)
        for i, (k, v) in enumerate([
            ("阶段", a.get("stage", "--")),
            ("得分", str(a.get("stage_score", "--"))),
            ("趋势", a.get("trend", "--")),
        ]):
            tk.Label(f1, text=f"{k}:", bg=bg_body, fg="#64748B",
                     font=("", 9)).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            tk.Label(f1, text=str(v), bg=bg_body, fg="#0F172A",
                     font=("", 10, "bold")).grid(row=i, column=1, sticky="w", padx=4, pady=2)

        # ② 涨跌幅
        _section("📊 涨跌幅", "#16A34A")
        f2 = tk.Frame(body, bg=bg_body)
        f2.pack(fill=tk.X, padx=8, pady=4)
        pct_rows = [
            ("当日", a.get("ret1_pct", None)),
            ("5日", a.get("ret5_pct", None)),
            ("10日", a.get("ret10_pct", None)),
            ("20日", a.get("ret20_pct", None)),
            ("60日", a.get("ret60_pct", None)),
        ]
        for i, (lbl, val) in enumerate(pct_rows):
            tk.Label(f2, text=f"{lbl}:", bg=bg_body, fg="#64748B",
                     font=("", 9)).grid(row=i // 2, column=(i % 2) * 2,
                                        sticky="w", padx=(8, 2), pady=2)
            tk.Label(f2, text=_fmt(val), bg=bg_body, fg=_pct_color(val),
                     font=("", 10, "bold")).grid(row=i // 2, column=(i % 2) * 2 + 1,
                                                sticky="w", padx=(0, 12), pady=2)

        # ③ 均线
        _section("📈 均线", "#3B82F6")
        d = a.get("detail", {})
        f3 = tk.Frame(body, bg=bg_body)
        f3.pack(fill=tk.X, padx=8, pady=4)
        ma_labels = [("收盘", "close"), ("MA5", "ma5"), ("MA10", "ma10"),
                     ("MA20", "ma20"), ("MA60", "ma60"), ("60日高", "high60"),
                     ("60日低", "low60")]
        for i, (lbl, key) in enumerate(ma_labels):
            tk.Label(f3, text=f"{lbl}:", bg=bg_body, fg="#64748B",
                     font=("", 9)).grid(row=i // 2, column=(i % 2) * 2,
                                        sticky="w", padx=(8, 2), pady=2)
            tk.Label(f3, text=str(d.get(key, "--")), bg=bg_body, fg="#0F172A",
                     font=("", 9, "bold")).grid(row=i // 2, column=(i % 2) * 2 + 1,
                                                sticky="w", padx=(0, 12), pady=2)
        ms = a.get("ma_status", {})
        tk.Label(f3, text=f"排列: {ms.get('排列','--')}", bg=bg_body,
                 fg="#0F172A", font=("", 9)).grid(row=4, column=0, columnspan=4,
                                                  sticky="w", padx=8, pady=(4, 2))
        tk.Label(f3, text=f"📍 60日位置: {a.get('pos_range_pct','--')}%",
                 bg=bg_body, fg="#0F172A", font=("", 9)).grid(row=5, column=0, columnspan=4,
                                                              sticky="w", padx=8, pady=(0, 4))

        # ④ 量能
        _section("📉 量能", "#F59E0B")
        f4 = tk.Frame(body, bg=bg_body)
        f4.pack(fill=tk.X, padx=8, pady=4)
        vs = a.get("volume_status", {})
        for i, (k, v) in enumerate([
            ("状态", vs.get("state", "--")),
            ("量比", str(vs.get("vratio", "--"))),
            ("位置", str(vs.get("pos", "--"))),
        ]):
            tk.Label(f4, text=f"{k}:", bg=bg_body, fg="#64748B",
                     font=("", 9)).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            tk.Label(f4, text=str(v), bg=bg_body, fg="#0F172A",
                     font=("", 10, "bold")).grid(row=i, column=1, sticky="w", padx=4, pady=2)

        # ⑤ 机构/游资
        _section("🏛 机构 vs 游资", "#1E40AF")
        f5 = tk.Frame(body, bg=bg_body)
        f5.pack(fill=tk.X, padx=8, pady=4)
        inst_type = a.get("institution_vs_hot_money", "--")
        inst_color = "#1E40AF" if "机构" in inst_type else "#DC2626" if "游资" in inst_type else "#6B7280"
        tk.Label(f5, text=f"属性: {inst_type}", bg=bg_body, fg=inst_color,
                 font=("", 10, "bold")).grid(row=0, column=0, columnspan=4,
                                              sticky="w", padx=8, pady=(2, 4))
        for i, (lbl, key) in enumerate([
            ("机构分", "institution_score"),
            ("游资分", "hot_money_score"),
        ]):
            tk.Label(f5, text=f"{lbl}:", bg=bg_body, fg="#64748B",
                     font=("", 9)).grid(row=1 + i, column=0, sticky="w", padx=8, pady=2)
            tk.Label(f5, text=str(a.get(key, "--")), bg=bg_body, fg="#0F172A",
                     font=("", 10, "bold")).grid(row=1 + i, column=1, sticky="w", padx=4, pady=2)

        # ⑥ 关键信号
        _section("🚦 关键信号", "#EF4444")
        f6 = tk.Frame(body, bg=bg_body)
        f6.pack(fill=tk.X, padx=8, pady=4)
        sigs = a.get("signals", [])
        if sigs:
            for i, sig in enumerate(sigs):
                tk.Label(f6, text=f"• {sig}", bg=bg_body, fg="#374151",
                         font=("", 9), anchor="w", wraplength=320,
                         justify=tk.LEFT).pack(anchor="w", padx=8, pady=1)
        else:
            tk.Label(f6, text="(暂无)", bg=bg_body, fg="#9CA3AF",
                     font=("", 9)).pack(anchor="w", padx=8, pady=4)

        # ⑦ K线形态
        _section("🕯 K线形态", "#8B5CF6")
        tk.Label(body, text=f"  {a.get('kline_pattern', '--')}",
                 bg=bg_body, fg="#374151", font=("", 9), wraplength=340,
                 justify=tk.LEFT).pack(anchor="w", padx=8, pady=(2, 8))

    # ── 右栏: K 线 + 一目均衡 (matplotlib) ──

    def _hc_diagnose_draw_chart(self, parent, r, df_tail, loading_label):
        """后台: 准备 df → 画 K 线 + MA + 一目均衡表 → FigureCanvasTkAgg"""
        try:
            import matplotlib
            matplotlib.use("TkAgg", force=False)
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.patches import FancyBboxPatch
            import matplotlib.dates as mdates
            from datetime import datetime as _dt

            plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC",
                                                "Heiti SC", "STHeiti", "SimHei", "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False

            # 若无缓存 df_tail, 现场取一次
            if not df_tail:
                import akshare as ak
                code = r["code"]
                df = ak.stock_zh_a_hist(
                    symbol=code, period="daily", adjust="qfq",
                    start_date=(_dt.now() - _dt.timedelta(days=500)).strftime("%Y%m%d"),
                    end_date=_dt.now().strftime("%Y%m%d"),
                )
                dft = df.tail(200).reset_index(drop=True)
                df_tail = [
                    {
                        "date": str(row.get("日期", "")),
                        "open": float(row.get("开盘", 0)),
                        "high": float(row.get("最高", 0)),
                        "low": float(row.get("最低", 0)),
                        "close": float(row.get("收盘", 0)),
                        "vol": float(row.get("成交量", 0)),
                    }
                    for _, row in dft.iterrows()
                ]

            # 转 numpy 方便画图
            closes = np.array([x["close"] for x in df_tail], dtype=float)
            opens = np.array([x["open"] for x in df_tail], dtype=float)
            highs = np.array([x["high"] for x in df_tail], dtype=float)
            lows = np.array([x["low"] for x in df_tail], dtype=float)
            vols = np.array([x["vol"] for x in df_tail], dtype=float)
            dates_raw = [x["date"] for x in df_tail]
            n = len(closes)

            # ── 计算均线 ──
            def _ma(arr, w):
                out = np.full_like(arr, np.nan)
                if len(arr) >= w:
                    out[w - 1:] = np.convolve(arr, np.ones(w) / w, mode="valid")
                return out

            ma5 = _ma(closes, 5)
            ma10 = _ma(closes, 10)
            ma20 = _ma(closes, 20)
            ma60 = _ma(closes, 60)

            # ── 一目均衡表 ──
            def _ichimoku(highs, lows, closes):
                # 转换线 (9日)
                tl = 9
                turn = np.full(n, np.nan)
                for i in range(tl - 1, n):
                    turn[i] = (np.max(highs[i - tl + 1:i + 1]) +
                               np.min(lows[i - tl + 1:i + 1])) / 2
                # 基准线 (26日)
                bl = 26
                base = np.full(n, np.nan)
                for i in range(bl - 1, n):
                    base[i] = (np.max(highs[i - bl + 1:i + 1]) +
                               np.min(lows[i - bl + 1:i + 1])) / 2
                # 先行带 A/B (各前移 26 天)
                span_a = np.full(n, np.nan)
                span_b = np.full(n, np.nan)
                shift = 26
                for i in range(n):
                    if i + shift < n:
                        if not np.isnan(turn[i]) and not np.isnan(base[i]):
                            span_a[i + shift] = (turn[i] + base[i]) / 2
                    if i + shift < n and i >= 51:
                        span_b[i + shift] = (np.max(highs[i - 51:i + 1]) +
                                             np.min(lows[i - 51:i + 1])) / 2
                # 延迟带 (收盘价后移 26)
                lag = np.full(n, np.nan)
                for i in range(n - shift):
                    lag[i + shift] = closes[i]
                return turn, base, span_a, span_b, lag

            turn, base, span_a, span_b, lag = _ichimoku(highs, lows, closes)

            # ── 画图 ──
            fig = plt.figure(figsize=(10, 7.5), dpi=100, facecolor="#FFFFFF")
            ax = fig.add_axes([0.08, 0.18, 0.88, 0.78])
            ax.set_facecolor("#FAFAFA")

            x = np.arange(n)

            # K 线 (简化: 用竖线 + 小矩形, 红涨绿跌)
            body_w = 0.6
            for i in range(n):
                c, o, h, lo = closes[i], opens[i], highs[i], lows[i]
                up = c >= o
                color = "#DC2626" if up else "#16A34A"
                ax.plot([x[i], x[i]], [lo, h], color=color, lw=0.7, zorder=2)
                body_lo = min(c, o)
                body_hi = max(c, o)
                rect = plt.Rectangle((x[i] - body_w / 2, body_lo), body_w,
                                     max(body_hi - body_lo, 0.001),
                                     facecolor=color, edgecolor=color, zorder=3)
                ax.add_patch(rect)

            # MA
            ax.plot(x, ma5, color="#F59E0B", lw=1.2, label="MA5", zorder=4)
            ax.plot(x, ma10, color="#3B82F6", lw=1.2, label="MA10", zorder=4)
            ax.plot(x, ma20, color="#8B5CF6", lw=1.2, label="MA20", zorder=4)
            ax.plot(x, ma60, color="#6B7280", lw=1.3, label="MA60", zorder=4)

            # 一目均衡表
            ax.plot(x, turn, color="#EC4899", lw=1.0, label="转换线", zorder=5)
            ax.plot(x, base, color="#06B6D4", lw=1.0, label="基准线", zorder=5)
            ax.plot(x, lag, color="#A855F7", lw=1.0, ls="--", label="延迟线", zorder=5)
            # 先行带 A/B 填充
            ax.fill_between(x, span_a, span_b,
                            where=(~np.isnan(span_a)) & (~np.isnan(span_b)),
                            color="#3B82F6", alpha=0.15, label="先行带A")
            ax.fill_between(x, span_a, span_b,
                            where=(~np.isnan(span_a)) & (~np.isnan(span_b)) & (span_a < span_b),
                            color="#16A34A", alpha=0.12, label="先行带B")

            # 样式
            ax.set_title(f"{r['name']}({r['code']})  K线 + 一目均衡表",
                         fontsize=12, pad=8, color="#0F172A")
            ax.grid(True, alpha=0.3, linestyle="--")
            ax.legend(loc="upper left", fontsize=8, ncol=4, framealpha=0.9)
            # X 轴标签: 每 20 天显示一次
            step = max(1, n // 8)
            ticks = list(range(0, n, step)) + [n - 1]
            ax.set_xticks(ticks)
            ax.set_xticklabels([dates_raw[i][-5:] for i in ticks], rotation=30, fontsize=8)

            # 成交量副图
            ax2 = fig.add_axes([0.08, 0.06, 0.88, 0.10], sharex=ax)
            for i in range(n):
                up = closes[i] >= opens[i]
                c = "#DC2626" if up else "#16A34A"
                ax2.bar(x[i], vols[i], width=0.7, color=c)
            ax2.set_ylabel("量", fontsize=8)
            ax2.tick_params(axis="x", labelsize=7)
            ax2.grid(True, alpha=0.2)

            # 嵌到 Tk
            canvas = FigureCanvasTkAgg(fig, master=parent)

            def _on_ready():
                try:
                    loading_label.destroy()
                except Exception:
                    pass
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                canvas.draw()

            # 调度回主线程
            try:
                parent.winfo_toplevel().after(0, _on_ready)
            except Exception:
                _on_ready()

        except Exception as e:
            import traceback
            traceback.print_exc()
            def _fail():
                try:
                    loading_label.configure(text=f"❌ K线图加载失败: {e}", fg="#DC2626")
                except Exception:
                    pass
            try:
                parent.winfo_toplevel().after(0, _fail)
            except Exception:
                _fail()

"""
仓位/持仓 Mixin — CangweiMixin

迁移自 stockyidong mac003.py: 52 方法 / ~7673 行
涵盖: 持仓监控、仓位管理、凯利记录、盈亏计算、持仓详情、组合仪表盘
"""
import os, sys, re, json, time, threading, traceback, sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

try:
    import numpy as np
except ImportError: np = None
try:
    import pandas as pd
except ImportError: pd = None

from utils.config import DB_PATH, _APP_CONFIG_DIR
from utils.network import safe_call
from data.snapshot import *
from logic.crawlers import *  # TaogubaCrawler
from logic.spot import *
from data.db import init_database, save_kelly_record_to_db
from logic.stock_names import *  # get_stock_name_by_code 等
try:
    import akshare as ak
except ImportError: ak = None
try:
    import tushare as ts
except ImportError: ts = None

from datetime import datetime, timedelta
import re
import json
import os
import sys
import time
import threading
import traceback
import sqlite3

class CangweiMixin:
    """仓位管理 + 持仓监控相关方法"""


    def _show_self_holding_monitor_popup(self):
        """自持股监测:监测对象为 Main 持仓股,展示逻辑与热门股非去重里的同花顺股票一致(近10日涨跌幅、距10日线%、颜色规则)。"""
        main_holdings = self._get_main_holding_stocks()
        if not main_holdings:
            messagebox.showinfo("提示", "Main 持仓股为空,请先在 Main 标签页导入持仓股。", parent=self.root)
            return
        day_headers = [f"近{i}日" for i in range(1, 11)]
        ma10_col = "距10日线%"
        stocks = []
        for stock_name, stock_code, position_index in main_holdings:
            s = {'code': stock_code, 'name': stock_name, '逻辑': ''}
            for k in range(1, 11):
                s[f'近{k}日'] = ''
            s[ma10_col] = ''
            if stock_code:
                changes, ma10_dist = self._get_stock_recent_10day_and_ma10(stock_code)
                if changes and len(changes) >= 10:
                    for k in range(1, 11):
                        s[f'近{k}日'] = changes[10 - k]
                if ma10_dist is not None:
                    s[ma10_col] = ma10_dist
            stocks.append(s)
        win = self._safe_toplevel(self.root)
        win.title("自持股监测 - Main持仓股 🦅心法评分")
        win.geometry("1100x620")
        win.transient(self.root)
        top = ttk.Frame(win, padding=10)
        top.pack(fill=tk.BOTH, expand=True)
        ttk.Label(top, text=f"Main 持仓股 {len(stocks)} 只 | 涨幅红/跌幅蓝 | 近10日 | 距10日线 | 🦅游资心法 (双击行看全解)",
            font=("", 11, "bold")).pack(anchor="w")
        ttk.Label(top, text="🦅心法分: ≥65红(强) 45-64橙(中) <45绿(弱) | 异步0.3s/只逐行填充", foreground="gray").pack(anchor="w", pady=(0, 4))

        list_frame = ttk.Frame(top)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 4))

        # Treeview
        cols = ("code", "name", "logic") + tuple(f"d{i}" for i in range(1, 11)) + ("ma10", "hm_score", "best_sch")
        col_labels = ["代码", "名称", "逻辑/概念"] + [f"近{i}日" for i in range(1, 11)] + ["距10日线%", "🦅心法", "最强流派"]
        col_widths = [80, 90, 90] + [60] * 10 + [85, 75, 95]
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=18)
        for c, lbl, w in zip(cols, col_labels, col_widths):
            tree.heading(c, text=lbl)
            tree.column(c, width=w, anchor="center")
        for s in stocks:
            row_vals = (s.get('code',''), s.get('name',''), s.get('逻辑',''))
            row_vals += tuple(str(s.get(f'近{i}日','')) for i in range(1, 11))
            row_vals += (str(s.get(ma10_col,'')), "⏳", "-")
            tree.insert("", "end", values=row_vals, tags=("mid",))
        tree.tag_configure("high", foreground="#C62828")
        tree.tag_configure("mid", foreground="#F57F17")
        tree.tag_configure("low", foreground="#2E7D32")
        tree.tag_configure("red", foreground="#C62828")
        tree.tag_configure("green", foreground="#2E7D32")
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # ========== 异步算游资心法分 ==========
        import threading as _th_shm
        def _bg_hm():
            for i, s in enumerate(stocks):
                if not win.winfo_exists(): break
                try:
                    hm = self._hm_calc_for_stock(s.get('code',''))
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
                                vals[13] = _sc
                                vals[14] = _bst
                                tree.item(kids[idx], values=vals, tags=(_tg,))
                        except Exception:
                            pass
                    self.root.after(0, _upd)
                except Exception:
                    pass
                time.sleep(0.3)
        _th_shm.Thread(target=_bg_hm, daemon=True).start()

        # ========== 双击行 → 预测逻辑 + 游资心法全解 + 10日涨跌 + MA10 ==========
        def _on_double(evt):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            s = stocks[idx]
            code6 = str(s.get('code',''))
            name = str(s.get('name',''))
            if not code6 or not code6.isdigit(): return
            try:
                detail = tk.Toplevel(self.root)
                detail.title(f"🦅🔮 {name}({code6}) 自持股监测 + 预测逻辑 + 心法全解")
                detail.geometry("920x880")
                detail.configure(bg="#F5F5F5")
                detail.transient(self.root)
                # --- 区域1: 自持股监测数据 ---
                top_f = tk.LabelFrame(detail, text="📊 自持股监测数据 (近10日涨跌 + 距MA10)", bg="white", font=("", 10, "bold"))
                top_f.pack(fill="x", padx=10, pady=(10, 4))
                det_lines = [f"📊 {name} ({code6}) 自持股监测", ""]
                det_lines.append("  近10日涨跌幅:")
                for i in range(1, 11):
                    v = s.get(f'近{i}日', '')
                    det_lines.append(f"    近{i}日: {v}")
                det_lines.append("")
                det_lines.append(f"  距MA10: {s.get(ma10_col, '')}%")
                st_d = scrolledtext.ScrolledText(top_f, height=7, font=("", 10), wrap=tk.WORD)
                st_d.pack(fill="both", expand=True, padx=5, pady=5)
                st_d.insert(tk.END, "\n".join(det_lines))
                st_d.configure(state="disabled")

                # --- 区域2: 🔮 预测逻辑 ---
                pred_f = tk.LabelFrame(detail, text="🔮 明日预测逻辑 (基于近9日走势 + 距MA10)", bg="white", font=("", 10, "bold"))
                pred_f.pack(fill="x", padx=10, pady=4)
                pred_lbl = tk.Label(pred_f, text="⏳ 正在计算预测...", bg="white", fg="#666", font=("", 10))
                pred_lbl.pack(padx=10, pady=15)
                def _bg_pred():
                    try:
                        pred_txt = ""
                        if TOMORROW_PREDICT_AVAILABLE:
                            changes, ma10_dist = self._get_stock_recent_10day_and_ma10(code6)
                            if changes and len(changes) >= 6:
                                changes_9 = changes[-9:] if len(changes) >= 9 else changes
                                cum = 1.0
                                for c in changes_9:
                                    cum *= (1 + c / 100)
                                total = round((cum - 1) * 100, 2)
                                inp = StockPredictInput(code=code6, name=name, changes=changes_9, total=total, ma10_dist=ma10_dist)
                                result = predict_tomorrow(inp)
                                lines = [f"🔮 {name} ({code6}) 明日预测", ""]
                                lines.append(f"  📌 综合得分: {result.score:.1f}  |  信号: {result.signal}")
                                lines.append(f"  📌 明日预期: {result.outlook}")
                                lines.append(f"  📌 操作建议: {result.suggestion}")
                                lines.append(f"  📌 信心度: {result.confidence*100:.0f}%")
                                lines.append("")
                                lines.append("  📋 各维度打分明细:")
                                for k, v in result.detail.items():
                                    if isinstance(v, tuple):
                                        lines.append(f"    {k}: {v[0]}分 → {v[1]}")
                                    else:
                                        lines.append(f"    {k}: {v}")
                                pred_txt = "\n".join(lines)
                            else:
                                pred_txt = "⚠️ 涨跌数据不足，无法预测（需至少6日）"
                        else:
                            pred_txt = "⚠️ tomorrow_predict 模块未加载，预测功能不可用"
                        def _show_pred():
                            pred_lbl.configure(text="")
                            st_p = scrolledtext.ScrolledText(pred_f, height=10, font=("", 10), wrap=tk.WORD, bg="#FFFDE7")
                            st_p.pack(fill="both", expand=True, padx=5, pady=5)
                            st_p.insert(tk.END, pred_txt)
                            st_p.configure(state="disabled")
                        self.root.after(0, _show_pred)
                    except Exception as _pe:
                        self.root.after(0, lambda _pe=_pe: pred_lbl.configure(text=f"❌ 预测计算失败: {_pe}"))
                threading.Thread(target=_bg_pred, daemon=True).start()

                # --- 区域3: 🦅 游资心法快照 ---
                hm_f = tk.LabelFrame(detail, text="🦅 游资心法评分", bg="white", font=("", 10, "bold"))
                hm_f.pack(fill="both", expand=True, padx=10, pady=4)
                hm_lbl = tk.Label(hm_f, text="⏳ 正在计算心法评分...", bg="white", fg="#666", font=("", 10))
                hm_lbl.pack(padx=10, pady=15)
                def _bg_hm_d():
                    try:
                        hm = self._hm_calc_for_stock(code6)
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
                            ttk.Button(hm_f, text="🦅🔮 打开完整游资心法全解 + K线图弹窗",
                                command=lambda: (detail.withdraw(),
                                    self._open_hotmoney_single_dialog(auto_code=code6, auto_name=name))
                            ).pack(pady=10)
                        self.root.after(0, _show)
                    except Exception as _he:
                        self.root.after(0, lambda _he=_he: hm_lbl.configure(text=f"❌ {_he}"))
                threading.Thread(target=_bg_hm_d, daemon=True).start()
            except Exception as _de:
                messagebox.showerror("错误", f"打开详情失败: {_de}", parent=win)
        tree.bind("<Double-1>", _on_double)
        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X)
        def get_full_text():
            lines = ["===== 自持股监测(Main持仓股 + 🦅心法) =====",
                     "代码\t名称\t逻辑/概念标签\t" + "\t".join(day_headers) + "\t" + ma10_col + "\t🦅心法\t最强流派"]
            for i, s in enumerate(stocks):
                kids = tree.get_children()
                row_hm = "-"; row_best = "-"
                if i < len(kids):
                    vals = tree.item(kids[i], "values")
                    row_hm = str(vals[13]) if len(vals) > 13 else "-"
                    row_best = str(vals[14]) if len(vals) > 14 else "-"
                day_cols = "\t".join(str(s.get(f'近{j}日', '')) for j in range(1, 11))
                lines.append(f"{s.get('code','')}\t{s.get('name','')}\t{s.get('逻辑','')}\t{day_cols}\t{s.get(ma10_col,'')}\t{row_hm}\t{row_best}")
            return "\n".join(lines)
        def save_to_txt():
            path = tk.filedialog.asksaveasfilename(parent=win, title="保存为文本文件", defaultextension=".txt", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
            if path:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(get_full_text())
                    messagebox.showinfo("成功", f"已保存到\n{path}", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def save_to_excel():
            path = tk.filedialog.asksaveasfilename(parent=win, title="保存为 Excel", defaultextension=".xlsx", filetypes=[("Excel 文件", "*.xlsx"), ("所有文件", "*.*")])
            if path:
                try:
                    # 从 tree 读取心法分列值
                    rows_data = []
                    for i, s in enumerate(stocks):
                        row = dict(s)
                        row['🦅心法'] = '-'
                        row['最强流派'] = '-'
                        kids = tree.get_children()
                        if i < len(kids):
                            vals = tree.item(kids[i], "values")
                            if len(vals) > 13:
                                row['🦅心法'] = str(vals[13])
                            if len(vals) > 14:
                                row['最强流派'] = str(vals[14])
                        rows_data.append(row)
                    df = pd.DataFrame(rows_data)
                    if 'code' in df.columns:
                        df = df.rename(columns={'code': '代码', 'name': '名称', '逻辑': '逻辑/概念'})
                    col_order = ['代码', '名称', '逻辑/概念'] + [f'近{i}日' for i in range(1, 11)] + [ma10_col, '🦅心法', '最强流派']
                    df = df.reindex(columns=[c for c in col_order if c in df.columns])
                    df.to_excel(path, index=False)
                    messagebox.showinfo("成功", f"已保存到\n{path}", parent=win)
                except Exception as e:
                    messagebox.showerror("错误", f"保存失败: {e}", parent=win)
        def open_full_view():
            """全窗口浏览 — 在独立大窗口中显示完整文本"""
            content = get_full_text()
            self.open_full_window_viewer_from_content(content, "自持股监测")
        ttk.Button(btn_frame, text="保存为 TXT", command=save_to_txt, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="保存为 Excel", command=save_to_excel, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="全窗口浏览", command=open_full_view, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.LEFT)


    def show_holding_realtime_stats(self):
        """显示所有持仓股的实时统计"""
        try:
            print("[持仓实时统计] 开始收集持仓股...")
            # 收集所有标签的所有持仓股
            all_holdings = []
            group_names = ["自持股", "龙头股", "15Min", "Main", "持仓历史股"]
            for group_index in range(1, 6):
                try:
                    holding_stocks, _, _, _ = self._get_holding_group_data(group_index)
                    group_name = group_names[group_index - 1] if group_index <= len(group_names) else f"持仓组{group_index}"
                    count = 0
                    for stock in holding_stocks:
                        if stock and stock[0] and stock[1]:  # stock[0]是股票名,stock[1]是股票代码
                            all_holdings.append({
                                'stock_name': str(stock[0]).strip(),
                                'stock_code': str(stock[1]).strip(),
                                'group': group_name
                            })
                            count += 1
                    print(f"[持仓实时统计] {group_name}: 找到{count}只股票")
                except Exception as e:
                    print(f"[持仓实时统计] 获取持仓组{group_index}失败: {e}")
                    import traceback
                    traceback.print_exc()
            print(f"[持仓实时统计] 总共收集到{len(all_holdings)}只股票")
            if not all_holdings:
                messagebox.showinfo("提示", "当前没有持仓股,请先添加持仓股", parent=self.root)
                return
            # 调用通用显示函数
            self._show_realtime_stats_window(all_holdings, "持仓实时统计")
            # 检查买入信号并更新标签
            try:
                self._check_buy_signal()
            except Exception as e:
                print(f"检查买入信号失败: {e}")
        except Exception as e:
            error_msg = f"打开持仓实时统计失败: {e!s}"
            print(f"[持仓实时统计] 错误: {error_msg}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", error_msg, parent=self.root)


    def _trigger_new_position_dialog(self, position_type, stock_name, parent=None, reason=None):
        if not stock_name:
            messagebox.showwarning("警告", "请选择股票", parent=parent or self.root)
            return
        self.pending_waiting_reason = reason
        position_button_map = {
            "绩优股": "new_position_button",
            "朋友": "new_position_button2",
            "强势股": "new_position_button3",
            "妖股": "new_position_button4",
            "均值回归": "new_position_button5",
        }
        button_attr = position_button_map.get(position_type, "new_position_button")
        button = getattr(self, button_attr, None)
        if not button:
            messagebox.showerror("错误", "未找到开新仓按钮,请先进入主界面", parent=parent or self.root)
            return
        button.invoke()
        def fill_stock_name():
            try:
                for widget in self.root.winfo_children():
                    if isinstance(widget, tk.Toplevel):
                        title = widget.title()
                        if position_type in title and "新仓" in title:
                            def find_stock_combo(parent_widget):
                                for child in parent_widget.winfo_children():
                                    if isinstance(child, ttk.Combobox):
                                        for sibling in child.master.winfo_children():
                                            if isinstance(sibling, ttk.Label) and "股票名称" in sibling.cget("text"):
                                                return child
                                    result = find_stock_combo(child)
                                    if result:
                                        return result
                                return None
                            stock_combo = find_stock_combo(widget)
                            if stock_combo:
                                stock_combo.set(stock_name)
                            break
            except Exception as e:
                print(f"填入股票名称失败: {e}")
        self.root.after(300, fill_stock_name)


    def _open_waiting_new_position(self, section_key):
        section = getattr(self, "waiting_section_vars", {}).get(section_key)
        if not section:
            return
        stock_name = section["stock_var"].get().strip()
        if not stock_name:
            messagebox.showwarning("提示", "请选择自选股后再开新仓", parent=self.root)
            return
        position_type = section["type_var"].get() or "绩优股"
        reason = None
        if hasattr(self, "waiting_reason_map"):
            reason = self.waiting_reason_map.get(section_key)
        self._trigger_new_position_dialog(position_type, stock_name, reason=reason)


    def _collect_holding_pool_stats(self):
        """左侧标签池:龙头股(2)≈情绪/龙头、15Min(3)≈技术面、Main(4)≈基本面/资讯;统计数量与代码重叠。"""
        out = {"labels": ("龙头股(情绪/龙头池)", "15Min(技术面池)", "Main(基本面/资讯池)"), "groups": (2, 3, 4)}
        def _codes_for(gi):
            hs, _, _, _ = self._get_holding_group_data(gi)
            codes = []
            for item in hs or []:
                if not item or not item[0]:
                    continue
                c = (item[1] or "").strip()
                if not c:
                    c = get_stock_code_by_name(item[0]) or ""
                c = c.zfill(6) if len(str(c)) <= 6 and str(c).isdigit() else ""
                if c:
                    codes.append(c)
            return codes
        c2, c3, c4 = _codes_for(2), _codes_for(3), _codes_for(4)
        s2, s3, s4 = set(c2), set(c3), set(c4)
        out["counts"] = (len(c2), len(c3), len(c4))
        out["triple_overlap_n"] = len(s2 & s3 & s4)
        out["pair_23"] = len(s2 & s3)
        out["pair_24"] = len(s2 & s4)
        out["pair_34"] = len(s3 & s4)
        out["fill_rates"] = tuple(round(n / 80.0, 4) for n in out["counts"])
        return out


    def _holding_red_star_signal_5d_low_ma1(self, stock_code, low_pct_threshold=3.0):
        """信号/持仓:现价在近5日低位附近,且站上1日线(现价≥昨收;不要求昨收相对前收向上)。
        近低:相对近5日最低价的最低价、或近5日收盘的最低价,二者任一在阈值内即算。"""
        try:
            code = str(stock_code).zfill(6)
            ohlc = self._fetch_recent_daily_ohlc(code, days=30)
            if not ohlc or len(ohlc) != 4:
                return False
            _dates, _highs, lows, closes = ohlc
            if len(closes) < 5 or len(lows) < 5:
                return False
            closes_f = [float(x) for x in closes]
            lows_f = [float(x) for x in lows]
            latest_price = self._resolve_latest_price_for_ma(code, closes_f)
            if latest_price is None or latest_price <= 0:
                return False
            lows_5 = list(lows_f[-5:])
            try:
                spot = self._get_realtime_spot_row_for_holding(code)
                if spot and spot.get('最低') is not None:
                    ld = float(spot['最低'])
                    lows_5[-1] = min(ld, lows_5[-1])
            except Exception:
                pass
            min5_low = min(lows_5)
            min5_close = min(closes_f[-5:])
            thr = float(low_pct_threshold)
            near_low = False
            if min5_low > 0:
                near_low = near_low or ((latest_price - min5_low) / min5_low * 100.0 <= thr)
            if min5_close > 0:
                near_low = near_low or ((latest_price - min5_close) / min5_close * 100.0 <= thr)
            if len(closes_f) < 2:
                return False
            ref_price = float(closes_f[-2])
            ma1_ok = latest_price >= ref_price
            return bool(near_low and ma1_ok)
        except Exception:
            return False


    def _get_realtime_spot_row_for_holding(self, stock_code, cache_duration=30):
        """获取持仓预警用实时行情行,与一键分析同源:优先 Tushare(实时价+今日日K),失败则 AKShare 全市场快照。
        返回与 get_realtime_spot_row 兼容的 dict:含 最新价、最高、最低、昨收、涨跌幅 等。"""
        if not stock_code:
            return None
        try:
            if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                import tushare as ts
                ts_token = self.ts_token or TS_DEFAULT_TOKEN
                os.environ["TUSHARE_TOKEN"] = ts_token
                ts_code = self._format_ts_code(stock_code)
                price = None
                try:
                    df = ts.realtime_quote(ts_code=ts_code, src='dc')
                    if df is not None and not df.empty and 'price' in df.columns:
                        price = float(df.iloc[0]['price'])
                except Exception:
                    pass
                if price is None:
                    today = datetime.now().strftime('%Y%m%d')
                    pro = ts.pro_api()
                    df_d = pro.daily(ts_code=ts_code, trade_date=today)
                    if df_d is not None and not df_d.empty and 'close' in df_d.columns:
                        price = float(df_d.iloc[0]['close'])
                if price and 0.01 < price < 10000:
                    result = self._fetch_recent_daily_closes(stock_code, days=3, source="default", token=self.ts_token, return_volume=False)
                    if isinstance(result, tuple) and len(result) >= 2:
                        _, closes = result[0], result[1]
                        prev_close = float(closes[-2]) if len(closes) >= 2 else price
                    else:
                        prev_close = price
                    pct = ((price - prev_close) / prev_close * 100) if prev_close and prev_close != 0 else 0
                    # Tushare 实时/今日日K 无当日最高最低时,用当前价充当作保守值,振幅由后续 akshare 或历史累积
                    return {
                        '最新价': price, '最高': price, '最低': price,
                        '昨收': prev_close, '涨跌幅': round(pct, 2)
                    }
        except Exception as e:
            print(f"Tushare实时行情失败 {stock_code},改用AKShare: {e}")
        try:
            return get_realtime_spot_row(stock_code, cache_duration=cache_duration)
        except Exception as e:
            print(f"获取实时行情失败 {stock_code}: {e}")
            return None


    def _get_holding_daily_change_pct_tushare(self, stock_code):
        """持仓检测专用:优先用 Tushare 最近两日收盘计算涨跌幅,失败返回 None。"""
        if not stock_code or not TS_AVAILABLE:
            return None
        ts_token = (self.ts_token or TS_DEFAULT_TOKEN or "").strip()
        if not ts_token:
            return None
        try:
            import tushare as ts
            code6 = _normalize_a_share_code6(stock_code)
            if not code6:
                return None
            ts_code = _format_ts_code_for_spot(code6)
            if not ts_code:
                return None
            os.environ["TUSHARE_TOKEN"] = ts_token
            pro = ts.pro_api()
            dfd = pro.daily(ts_code=ts_code, limit=2)
            if dfd is None or dfd.empty or len(dfd) < 2:
                return None
            dfd = dfd.sort_values("trade_date", ascending=True)
            prev_close = float(dfd.iloc[-2]["close"])
            last_close = float(dfd.iloc[-1]["close"])
            if prev_close == 0:
                return None
            return round((last_close - prev_close) / prev_close * 100, 2)
        except Exception:
            return None


    def _get_holding_group_data(self, group_index):
        """获取指定持仓组的数据结构
        Args:
            group_index: 持仓组索引(1-5)
        Returns:
            tuple: (holding_stocks, holding_labels, holding_kelly_results, holding_low_diff_results)
        """
        if group_index == 1:
            return self.holding_stocks, self.holding_labels, self.holding_kelly_results, self.holding_low_diff_results
        else:
            holding_stocks = getattr(self, f'holding_stocks_{group_index}')
            holding_labels = getattr(self, f'holding_labels_{group_index}')
            holding_kelly_results = getattr(self, f'holding_kelly_results_{group_index}')
            holding_low_diff_results = getattr(self, f'holding_low_diff_results_{group_index}')
            return holding_stocks, holding_labels, holding_kelly_results, holding_low_diff_results


    def _export_all_holdings(self):
        """导出所有持仓标签页的股票到TXT文件
        导出规则:
        - 每个持仓标签页导出前20个股票
        - 包含日期时间
        - 保存到 Export 目录
        - 格式:单纯股票名字列表
        """
        try:
            import subprocess
            from tkinter import messagebox
            # 确保导出目录存在
            os.makedirs(D_EXPORT_DIR, exist_ok=True)
            # 生成文件名(包含日期时间)
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"持仓导出_{current_time}.txt"
            filepath = os.path.join(D_EXPORT_DIR, filename)
            # 收集所有持仓标签页的股票
            all_stocks = []
            # 遍历所有持仓组(1-14)
            for group_index in range(1, 15):
                holding_stocks, _, _, _ = self._get_holding_group_data(group_index)
                # 只取前20个股票
                for i, stock in enumerate(holding_stocks[:20]):
                    if stock and stock[0]:  # stock 是 (stock_name, stock_code) 元组
                        stock_name = stock[0]
                        stock_code = stock[1] if len(stock) > 1 else ""
                        # 只导出有效的股票代码(6位数字)
                        if stock_code and stock_code.isdigit() and len(stock_code) == 6:
                            all_stocks.append({
                                'code': stock_code,
                                'name': stock_name,
                                'group': group_index
                            })
            # 如果没有股票,提示用户
            if not all_stocks:
                messagebox.showinfo("提示", "当前没有持仓股票可导出")
                return
            # 写入文件(只保存股票名字列表)
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入股票名称,每行一个
                for stock in all_stocks:
                    f.write(f"{stock['name']}\n")
            # 显示成功消息
            messagebox.showinfo("导出成功",
                           f"已成功导出 {len(all_stocks)} 只股票到:\n{filepath}\n\n"
                           f"文件已自动打开,方便拷贝导入到同花顺自选股")
            # 自动打开文件
            try:
                print(f"尝试打开文件: {filepath}")
                print(f"操作系统类型: {os.name}")
                if os.name == 'darwin':  # macOS
                    print("使用 open 命令")
                    result = subprocess.run(['open', filepath], capture_output=True, text=True)
                    print(f"命令执行结果: {result.returncode}")
                    if result.stderr:
                        print(f"错误信息: {result.stderr}")
                elif os.name == 'nt':  # Windows
                    print("使用 start 命令")
                    result = subprocess.run(['start', filepath], shell=True, capture_output=True, text=True)
                    print(f"命令执行结果: {result.returncode}")
                    if result.stderr:
                        print(f"错误信息: {result.stderr}")
                elif os.name == 'posix':  # Linux
                    print("使用 xdg-open 命令")
                    result = subprocess.run(['xdg-open', filepath], capture_output=True, text=True)
                    print(f"命令执行结果: {result.returncode}")
                    if result.stderr:
                        print(f"错误信息: {result.stderr}")
            except Exception as open_err:
                # 打开文件失败不影响导出结果
                print(f"打开文件失败: {open_err!s}")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("导出失败", f"导出持仓失败:{e!s}")


    def _refresh_holding_tabs_from_news(self, run_hold_checks=False):
        """从资讯表按日期+频次刷新持仓7-14(原持仓1-持仓8):取最近8天资讯,每页为该日股票按频次排序,标签名改为MMDD。"""
        news_meta = {}
        days_data = get_news_stocks_by_date_and_frequency(ndays=8, meta=news_meta)
        if not days_data:
            reason = news_meta.get("reason")
            if reason == "db_error":
                msg = (
                    f"读取资讯表失败:{news_meta.get('error', '')}\n\n"
                    f"数据库:{DB_PATH}\n\n"
                    "若提示 database or disk is full:\n"
                    "1)清理 C: 与 D: 剩余空间;\n"
                    "2)彻底退出本程序后重新打开(启动时会把临时目录指到 D:\\StockAnalyzer\\temp,若设了 STOCK_ANALYZER_DATA_DIR 则为该目录下 temp);\n"
                    "3)仍失败时可在启动前手动设置环境变量 SQLITE_TMPDIR 到空间足够的文件夹。"
                )
            elif reason == "no_stock_dict":
                msg = "未能加载「股票代码-名称」对照表,无法从资讯正文识别六位代码。请检查网络或本地缓存后重试。"
            elif reason == "no_rows":
                msg = (
                    "资讯表(news_info)里目前没有记录。\n\n"
                    "请先使用「一键资讯」「批量爬取资讯」或各爬虫将内容保存进股票资讯表,再点「从资讯刷新」。"
                )
            elif reason == "no_valid_dates":
                msg = news_meta.get("hint") or "资讯记录无法按日期归类(created_at 异常)。"
            else:
                msg = "资讯表中暂无有效数据。请先爬取并保存资讯到股票资讯表(news_info)。"
            try:
                messagebox.showinfo("提示", msg, parent=self.root)
            except Exception:
                pass
            return
        if news_meta.get("reason") == "no_codes_in_news" or news_meta.get("total_stock_slots", -1) == 0:
            try:
                messagebox.showwarning(
                    "提示",
                    (news_meta.get("hint") or "资讯里没有解析出有效 A 股代码。")
                    + "\n\n仍会尝试按日期更新「持仓1~8」标签名,但中间股票格子可能为空。",
                    parent=self.root,
                )
            except Exception:
                pass
        for i, day_info in enumerate(days_data):
            group_index = 7 + i
            stocks = day_info.get("stocks", [])
            date_mmdd = day_info.get("date_mmdd", f"持仓{i+1}")
            holding_stocks = getattr(self, f'holding_stocks_{group_index}')
            for j in range(80):
                holding_stocks[j] = stocks[j] if j < len(stocks) else None
            notebook_index = group_index + 1
            try:
                self.position_trading_notebook.tab(notebook_index, text=date_mmdd)
            except Exception:
                pass
            for j in range(20):
                self._update_holding_label(j, check_conditions=False, group_index=group_index, fetch_daily_change=False)
        try:
            saved = self.ai_config_manager.config.get("holding_tab_names", {})
            for i, day_info in enumerate(days_data):
                saved[str(7 + i)] = day_info.get("date_mmdd", f"持仓{i+1}")
            self.ai_config_manager.config["holding_tab_names"] = saved
            self.ai_config_manager.save_config()
        except Exception:
            pass
        if run_hold_checks:
            try:
                self._run_holding_checks_for_news_tabs(include_main=True, include_date_tabs=True)
            except Exception as e:
                print(f"资讯刷新后触发持仓检测失败: {e}")


    def _run_holding_checks_for_news_tabs(self, include_main=True, include_date_tabs=True):
        """资讯刷新后:对当期及其他日期标签页批量触发「持仓检测」按钮同源逻辑。"""
        targets = []
        if include_main:
            targets.append(4)
        if include_date_tabs:
            targets.extend(range(7, 15))
        valid_targets = []
        for g in targets:
            try:
                holding_stocks, _, _, _ = self._get_holding_group_data(g)
            except Exception:
                continue
            if any(holding_stocks):
                valid_targets.append(g)
        if not valid_targets:
            return
        names = [self._signal_tab_label_for_group(g) for g in valid_targets]
        try:
            messagebox.showinfo(
                "资讯刷新",
                "已开始批量执行持仓检测:\n" + "、".join(names),
                parent=self.root,
            )
        except Exception:
            pass
        # 逐个错峰触发,避免同一时刻并发过高
        delay_ms = 0
        for g in valid_targets:
            def _kick(group_idx=g):
                try:
                    self._check_holdings(group_index=group_idx, max_count=80)
                except Exception as _e:
                    print(f"触发持仓检测失败(group={group_idx}): {_e}")
            self.root.after(delay_ms, _kick)
            delay_ms += 1200


    def _create_holding_tab(self, notebook, tab_name, group_index):
        """创建持仓标签页的辅助函数
        Args:
            notebook: 要添加标签页的Notebook控件
            tab_name: 标签页名称
            group_index: 持仓组索引(1-5)
        """
        holding_tab = ttk.Frame(notebook, padding=2)
        # 设置持仓标签页按钮宽度
        tab_text = tab_name + "                    " if group_index == 1 else tab_name
        notebook.add(holding_tab, text=tab_text)
        # 获取对应组的数据结构
        _holding_stocks, holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
        # 自持仓管理:不要 expand 占满整页,否则股票网格下会出现大块空白,挤占下方 Notebook 外区域
        holding_frame = ttk.LabelFrame(holding_tab, text=f"自持仓管理({tab_name})", padding=2)
        holding_frame.pack(fill=tk.X, expand=False, anchor=tk.N)
        # 持仓股管理按钮行(小字号+紧凑 padding,避免一行挤不下)
        holding_control_frame = ttk.Frame(holding_frame)
        holding_control_frame.pack(fill=tk.X, pady=(0, 2))
        _hb_style = "HoldingToolbar.TButton"
        # 所有持仓组(1-14)都支持80个股票,添加弹出框按钮
        ttk.Button(
            holding_control_frame,
            text="打开管理界面",
            style=_hb_style,
            command=lambda: self._open_history_holdings_window(group_index),
            width=10,
        ).pack(side=tk.LEFT, padx=(0, 3))
        # 所有持仓组都支持80个股票
        max_count = 80
        ttk.Button(
            holding_control_frame,
            text="导入持仓",
            style=_hb_style,
            command=lambda: self._import_holdings(group_index, max_count=max_count),
            width=9,
        ).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(
            holding_control_frame,
            text="持仓股管理",
            style=_hb_style,
            command=lambda: self._manage_holdings(group_index, max_count=max_count),
            width=10,
        ).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(
            holding_control_frame,
            text="持仓检测",
            style=_hb_style,
            command=lambda: self._check_holdings(group_index, max_count=max_count),
            width=9,
        ).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(holding_control_frame, text="持仓计算", style=_hb_style, command=self._open_holding_calculator, width=9).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(holding_control_frame, text="持仓导出", style=_hb_style, command=lambda: self._export_all_holdings(), width=9).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(holding_control_frame, text="设置", style=_hb_style, command=self._open_settings_dialog, width=6).pack(side=tk.LEFT, padx=(0, 3))
        if group_index == 2:
            ttk.Button(
                holding_control_frame,
                text="资讯股",
                style=_hb_style,
                command=lambda: self._refresh_leader_from_news(silent=False),
                width=8,
            ).pack(side=tk.LEFT, padx=(0, 3))
        else:
            ttk.Button(
                holding_control_frame,
                text="5日最低点",
                style=_hb_style,
                command=lambda: self._calculate_5day_low_diff(group_index, max_count=max_count),
                width=10,
            ).pack(side=tk.LEFT, padx=(0, 3))
        # 同花顺标签页(group_index=6)添加爬取同花顺热榜的按钮
        if group_index == 6:
            ttk.Button(
                holding_control_frame,
                text="爬取同花顺热榜",
                style=_hb_style,
                command=self._crawl_ths_hot_stocks,
                width=12,
            ).pack(side=tk.LEFT, padx=(0, 3))
        # 龙头股标签页(group_index=2):坐电梯同源问财指标下拉 + 问财分次查询 + 本地均线标记
        if group_index == 2:
            wrow = ttk.Frame(holding_control_frame)
            wrow.pack(side=tk.LEFT, padx=(0, 3))
            ttk.Label(wrow, text="问财指标").pack(side=tk.LEFT, padx=(0, 2))
            self._leader_wencai_indicator_placeholder = "(选后查询显示)"
            _wvals = [self._leader_wencai_indicator_placeholder] + self._load_elevator_wencai_conditions()
            self._leader_wencai_indicator_var = tk.StringVar(value=self._leader_wencai_indicator_placeholder)
            wcombo = ttk.Combobox(
                wrow,
                textvariable=self._leader_wencai_indicator_var,
                values=_wvals,
                state="readonly",
                width=20,
            )
            wcombo.pack(side=tk.LEFT, padx=(0, 2))
            def _on_leader_wencai_pick(_evt=None):
                sel = self._leader_wencai_indicator_var.get()
                if not sel or sel == self._leader_wencai_indicator_placeholder:
                    return
                self._start_wencai_indicator_query_for_leader_tab(sel)
            wcombo.bind("<<ComboboxSelected>>", _on_leader_wencai_pick)
            ttk.Button(
                holding_control_frame,
                text="问财+均线龙头",
                style=_hb_style,
                command=self._import_leader_stocks_from_wencai_ma,
                width=12,
            ).pack(side=tk.LEFT, padx=(0, 3))
        # 15Min标签页(group_index=3)添加爬取问财15分钟策略股票的按钮
        if group_index == 3:
            ttk.Button(
                holding_control_frame,
                text="爬取问财15Min",
                style=_hb_style,
                command=self._crawl_iwencai_15min_stocks,
                width=12,
            ).pack(side=tk.LEFT, padx=(0, 3))
        # Main(group_index=4):资讯表最近5日合并,按正文内股票代码出现频次排序
        if group_index == 4:
            ttk.Button(
                holding_control_frame,
                text="从资讯刷新",
                style=_hb_style,
                command=lambda: self._refresh_main_from_news(silent=False, run_hold_checks=True),
                width=10,
            ).pack(side=tk.LEFT, padx=(0, 3))
        # 持仓7-14(原持仓1-8):从资讯表按日期+频次刷新,标签名改为MMDD
        if 7 <= group_index <= 14 and group_index == 7:
            ttk.Button(
                holding_control_frame,
                text="从资讯刷新",
                style=_hb_style,
                command=lambda: self._refresh_holding_tabs_from_news(run_hold_checks=True),
                width=10,
            ).pack(side=tk.LEFT, padx=(0, 3))
        # 持仓股显示区域(不占满垂直剩余空间,避免行被强行拉高顶掉下方板块/导航)
        holding_stocks_frame = ttk.Frame(holding_frame)
        holding_stocks_frame.pack(fill=tk.X, expand=False)
        # 所有组在标签页都显示20个(持仓2、3、4、5支持80个,但标签页只显示20个)
        display_count = 20
        rows = 5  # 5行
        cols = 4  # 每行4个
        # 创建持仓股显示按钮:行不 expand,高度随字体与 padding,避免「按钮巨高」
        for row in range(rows):
            row_frame = ttk.Frame(holding_stocks_frame)
            row_frame.pack(fill=tk.X, expand=False, pady=1)
            for col in range(cols):
                i = row * cols + col
                if i >= display_count:
                    break
                stock_frame = ttk.Frame(row_frame)
                stock_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                # 按钮(点击弹出详情)
                label = tk.Label(stock_frame, text=f"{i+1}",
                               font=("TkDefaultFont", 13),
                               bg="lightgray",
                               relief=tk.RAISED,
                               padx=4, pady=2,
                               cursor="hand2")
                label.pack(fill=tk.X, expand=False)
                # 绑定点击事件,打开详情弹出框
                def make_click_handler(idx=i, gidx=group_index):
                    def on_click(event):
                        self._show_holding_detail(idx, gidx)
                    return on_click
                label.bind("<Button-1>", make_click_handler())
                holding_labels.append(label)
        # 仅持仓1-8(group_index 7-14)在股票列表最下方显示"各导入的2个板块"名(点击交易-查看时更新)
        if 7 <= group_index <= 14:
            sector_bottom_frame = ttk.Frame(holding_frame)
            sector_bottom_frame.pack(fill=tk.X, pady=(2, 0))
            sector_label = ttk.Label(sector_bottom_frame, text="板块: -", font=("TkDefaultFont", 11), foreground="gray")
            sector_label.pack(anchor=tk.W)
            setattr(self, f'holding_tab_sector_label_{group_index}', sector_label)
        # 从配置文件加载持仓股(所有组都支持80个,但标签页只显示前20个)
        # 持仓1-8(group_index 7-14)暂时不自动加载,等待用户点击"板块情绪监测-查看"按钮时再加载
        if group_index < 7:
            self._load_holdings_from_config(group_index, display_only=True)


    def _import_holdings(self, group_index=1, max_count=20, popup_window=None):
        """导入持仓股(从历史持仓股或自选股数据表或直接输入)
        Args:
            group_index: 持仓组索引
            max_count: 最大持仓数量(默认20,持仓历史股弹出框为80)
            popup_window: 弹出窗口引用(用于更新显示)
        """
        import_window = self._safe_toplevel(self.root)
        import_window.title("导入持仓股")
        import_window.geometry("600x550")
        # 持仓位置选择(在窗口顶部)
        position_frame = ttk.Frame(import_window)
        position_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        ttk.Label(position_frame, text="选择持仓位置:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(0, 5))
        position_var = tk.StringVar(value="1")
        # 根据max_count确定可选择的持仓位置数量
        max_positions = max_count if max_count else 20
        position_combo = ttk.Combobox(position_frame, textvariable=position_var,
                                      values=[f"{i+1}" for i in range(max_positions)],
                                      state="readonly", width=10)
        position_combo.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(position_frame, text="(选择要修改的持仓位置)", font=("TkDefaultFont", 8),
                 foreground="gray").pack(side=tk.LEFT)
        # 创建标签页
        notebook = ttk.Notebook(import_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # 持仓输入标签页(默认标签页)
        input_tab = ttk.Frame(notebook)
        notebook.add(input_tab, text="持仓输入")
        # 输入说明
        ttk.Label(input_tab, text="请输入股票名称或代码(每行一个):",
                 font=("TkDefaultFont", 11)).pack(anchor=tk.W, padx=5, pady=(5, 2))
        # 输入框
        input_text = scrolledtext.ScrolledText(input_tab, height=15, wrap=tk.WORD)
        input_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 历史持仓股标签页
        history_tab = ttk.Frame(notebook)
        notebook.add(history_tab, text="历史持仓股")
        history_listbox = tk.Listbox(history_tab, height=15)
        history_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 从配置文件加载历史持仓股(与持仓股管理的历史持仓股一致)
        def load_history_holdings():
            try:
                history_listbox.delete(0, tk.END)
                history_holdings = self.ai_config_manager.config.get("history_holdings", [])
                for item in history_holdings:
                    stock_name = item.get("stock_name", "").strip()
                    stock_code = item.get("stock_code", "").strip()
                    if stock_name or stock_code:
                        if stock_code:
                            history_listbox.insert(tk.END, f"{stock_name} ({stock_code})")
                        else:
                            history_listbox.insert(tk.END, stock_name)
            except Exception as e:
                print(f"加载历史持仓股失败: {e}")
        # 初始加载
        load_history_holdings()
        ttk.Button(history_tab, text="刷新", command=load_history_holdings).pack(pady=5)
        # 自选股数据表标签页
        db_tab = ttk.Frame(notebook)
        notebook.add(db_tab, text="自选股数据表")
        db_listbox = tk.Listbox(db_tab, height=15)
        db_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 从自选股数据表加载
        def load_db_stocks():
            try:
                db_listbox.delete(0, tk.END)
                # 从stock_logic表获取股票数据
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    cursor.execute('SELECT DISTINCT stock_name FROM stock_logic ORDER BY created_at DESC LIMIT 100')
                    db_stocks = cursor.fetchall()
                    for (stock_name,) in db_stocks:
                        stock_code = get_stock_code_by_name(stock_name)
                        if stock_code:
                            db_listbox.insert(tk.END, f"{stock_name} ({stock_code})")
                        else:
                            db_listbox.insert(tk.END, stock_name)
                except Exception as e:
                    print(f"从stock_logic表获取数据失败: {e}")
                conn.close()
            except Exception as e:
                messagebox.showerror("错误", f"加载自选股数据表失败: {e}", parent=import_window)
        # 初始加载
        load_db_stocks()
        ttk.Button(db_tab, text="刷新", command=load_db_stocks).pack(pady=5)
        # 股票数据表标签页
        stock_data_tab = ttk.Frame(notebook)
        notebook.add(stock_data_tab, text="股票数据表")
        stock_data_listbox = tk.Listbox(stock_data_tab, height=15)
        stock_data_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 从股票数据表加载
        def load_stock_data_stocks():
            try:
                stock_data_listbox.delete(0, tk.END)
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    # 从stock_data表获取最近100条不同股票的记录
                    cursor.execute('''
                        SELECT DISTINCT stock_name, stock_code
                        FROM stock_data
                        ORDER BY created_at DESC
                        LIMIT 100
                    ''')
                    stock_data_records = cursor.fetchall()
                    for stock_name, stock_code in stock_data_records:
                        if stock_name and stock_code:
                            stock_data_listbox.insert(tk.END, f"{stock_name} ({stock_code})")
                        elif stock_name:
                            stock_code = get_stock_code_by_name(stock_name)
                            if stock_code:
                                stock_data_listbox.insert(tk.END, f"{stock_name} ({stock_code})")
                            else:
                                stock_data_listbox.insert(tk.END, stock_name)
                        elif stock_code:
                            stock_data_listbox.insert(tk.END, stock_code)
                except Exception as e:
                    print(f"从stock_data表获取数据失败: {e}")
                conn.close()
            except Exception as e:
                messagebox.showerror("错误", f"加载股票数据表失败: {e}", parent=import_window)
        # 初始加载
        load_stock_data_stocks()
        ttk.Button(stock_data_tab, text="刷新", command=load_stock_data_stocks).pack(pady=5)
        # 龙虎榜数据表标签页
        lhb_tab = ttk.Frame(notebook)
        notebook.add(lhb_tab, text="龙虎榜数据表")
        lhb_listbox = tk.Listbox(lhb_tab, height=15)
        lhb_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 从龙虎榜数据表加载
        def load_lhb_stocks():
            try:
                lhb_listbox.delete(0, tk.END)
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    # 从lhb_records表获取最近100条不同股票的记录
                    # ts_code格式可能是"000001.SZ",需要转换为"000001"
                    cursor.execute('''
                        SELECT DISTINCT name, ts_code
                        FROM lhb_records
                        WHERE name IS NOT NULL AND name != ''
                        ORDER BY created_at DESC
                        LIMIT 100
                    ''')
                    lhb_records = cursor.fetchall()
                    for name, ts_code in lhb_records:
                        # 将ts_code从"000001.SZ"格式转换为"000001"
                        stock_code = ts_code.split('.')[0] if ts_code else None
                        if name and stock_code:
                            lhb_listbox.insert(tk.END, f"{name} ({stock_code})")
                        elif name:
                            lhb_listbox.insert(tk.END, name)
                        elif stock_code:
                            lhb_listbox.insert(tk.END, stock_code)
                except Exception as e:
                    print(f"从lhb_records表获取数据失败: {e}")
                conn.close()
            except Exception as e:
                messagebox.showerror("错误", f"加载龙虎榜数据表失败: {e}", parent=import_window)
        # 初始加载
        load_lhb_stocks()
        ttk.Button(lhb_tab, text="刷新", command=load_lhb_stocks).pack(pady=5)
        # 选择按钮
        def select_stocks():
            """选择股票并填充到持仓股"""
            # 获取选定的持仓位置索引(0-19)
            position_text = position_var.get()
            # 兼容旧格式"持仓1"和新格式"1"
            position_text = position_text.replace("持仓", "")
            position_index = int(position_text) - 1
            current_tab = notebook.index(notebook.select())
            stocks_to_import = []
            if current_tab == 0:  # 持仓输入标签页
                # 从输入框读取
                input_content = input_text.get("1.0", tk.END).strip()
                if not input_content:
                    messagebox.showwarning("警告", "请输入股票名称或代码", parent=import_window)
                    return
                # 解析输入(每行一个)
                lines = [line.strip() for line in input_content.split('\n') if line.strip()]
                for line in lines:
                    # 解析股票名称和代码
                    stock_name = None
                    stock_code = None
                    # 检查是否是股票代码(6位数字)
                    if line.isdigit() and len(line) == 6:
                        stock_code = line
                        stock_name = None  # 稍后通过代码获取名称
                    elif "(" in line and ")" in line:
                        # 格式:名称(代码) 或 代码(名称)
                        parts = line.split("(")
                        if len(parts) == 2:
                            part1 = parts[0].strip()
                            part2 = parts[1].replace(")", "").strip()
                            if part2.isdigit() and len(part2) == 6:
                                # 名称(代码)
                                stock_name = part1
                                stock_code = part2
                            else:
                                # 代码(名称)
                                stock_code = part1
                                stock_name = part2
                    else:
                        # 可能是股票名称或代码
                        if line.isdigit() and len(line) == 6:
                            stock_code = line
                        else:
                            stock_name = line
                    stocks_to_import.append((stock_name, stock_code))
            elif current_tab == 1:  # 历史持仓股
                selected_indices = history_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("警告", "请先选择股票", parent=import_window)
                    return
                stocks_list = history_listbox
                for idx in selected_indices:
                    stock_text = stocks_list.get(idx)
                    # 解析股票名称和代码
                    if "(" in stock_text and ")" in stock_text:
                        stock_name = stock_text.split("(")[0].strip()
                        stock_code = stock_text.split("(")[1].replace(")", "").strip()
                    else:
                        stock_name = stock_text.strip()
                        stock_code = None
                    stocks_to_import.append((stock_name, stock_code))
            elif current_tab == 2:  # 自选股数据表
                selected_indices = db_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("警告", "请先选择股票", parent=import_window)
                    return
                stocks_list = db_listbox
                for idx in selected_indices:
                    stock_text = stocks_list.get(idx)
                    # 解析股票名称和代码
                    if "(" in stock_text and ")" in stock_text:
                        stock_name = stock_text.split("(")[0].strip()
                        stock_code = stock_text.split("(")[1].replace(")", "").strip()
                    else:
                        stock_name = stock_text.strip()
                        stock_code = None
                    stocks_to_import.append((stock_name, stock_code))
            elif current_tab == 3:  # 股票数据表
                selected_indices = stock_data_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("警告", "请先选择股票", parent=import_window)
                    return
                stocks_list = stock_data_listbox
                for idx in selected_indices:
                    stock_text = stocks_list.get(idx)
                    # 解析股票名称和代码
                    if "(" in stock_text and ")" in stock_text:
                        stock_name = stock_text.split("(")[0].strip()
                        stock_code = stock_text.split("(")[1].replace(")", "").strip()
                    else:
                        stock_name = stock_text.strip()
                        stock_code = None
                    stocks_to_import.append((stock_name, stock_code))
            elif current_tab == 4:  # 龙虎榜数据表
                selected_indices = lhb_listbox.curselection()
                if not selected_indices:
                    messagebox.showwarning("警告", "请先选择股票", parent=import_window)
                    return
                stocks_list = lhb_listbox
                for idx in selected_indices:
                    stock_text = stocks_list.get(idx)
                    # 解析股票名称和代码
                    if "(" in stock_text and ")" in stock_text:
                        stock_name = stock_text.split("(")[0].strip()
                        stock_code = stock_text.split("(")[1].replace(")", "").strip()
                    else:
                        stock_name = stock_text.strip()
                        stock_code = None
                    stocks_to_import.append((stock_name, stock_code))
            if not stocks_to_import:
                messagebox.showwarning("警告", "没有可导入的股票", parent=import_window)
                return
            # 获取对应组的数据结构
            holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
            # 填充到选定的持仓位置(从选定位置开始,最多max_count个)
            imported_count = 0
            for i, (stock_name, stock_code) in enumerate(stocks_to_import):
                if position_index + i >= max_count:
                    break
                # 如果没有股票代码,尝试通过名称获取
                if not stock_code and stock_name:
                    stock_code = get_stock_code_by_name(stock_name)
                # 如果没有股票名称,尝试通过代码获取
                if not stock_name and stock_code:
                    try:
                        import akshare as ak
                        stock_info = ak.stock_individual_info_em(symbol=stock_code)
                        if stock_info is not None and not stock_info.empty:
                            for _, row in stock_info.iterrows():
                                if row.get('item', '') == '股票简称' or row.get('item', '') == '股票名称':
                                    stock_name = row.get('value', '')
                                    break
                    except:
                        pass
                # 确保至少有一个值
                if stock_name or stock_code:
                    holding_stocks[position_index + i] = (stock_name if stock_name else '', stock_code if stock_code else '')
                else:
                    holding_stocks[position_index + i] = None
                # 立即更新显示(不执行检测)
                self._update_holding_label(position_index + i, check_conditions=False, group_index=group_index)
                # 强制刷新界面
                self._safe_update_idletasks()
                imported_count += 1
            # 强制更新所有持仓标签显示(不执行检测)
            for j in range(max_count):
                if j < len(holding_stocks):
                    self._update_holding_label(j, check_conditions=False, group_index=group_index)
                self._safe_update_idletasks()
            # 如果是在弹出窗口中,更新弹出窗口显示
            if popup_window and hasattr(popup_window, '_update_display'):
                popup_window._update_display()
            # 保存持仓股到配置文件
            self._save_holdings_to_config(group_index)
            import_window.destroy()
            messagebox.showinfo("成功", f"已导入 {imported_count} 个持仓股到{position_text}并保存,正在检测...", parent=self.root)
            # 导入后自动触发一次检测
            self._check_holdings(group_index, max_count=max_count)
        button_frame = ttk.Frame(import_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(button_frame, text="确定", command=select_stocks, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=import_window.destroy, width=10).pack(side=tk.LEFT, padx=5)


    def _manage_holdings(self, group_index=1, max_count=20, popup_window=None):
        """持仓股管理(编辑当前持仓股)"""
        # 获取对应组的数据结构
        holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
        manage_window = self._safe_toplevel(self.root)
        manage_window.title(f"持仓股管理(持仓组{group_index})")
        manage_window.geometry("600x600")
        # 说明标签
        ttk.Label(manage_window, text="编辑当前持仓股(每行一个,格式:股票名称 或 股票名称(代码) 或 代码)",
                 font=("TkDefaultFont", 11), wraplength=550).pack(anchor=tk.W, padx=10, pady=(10, 5))
        # 创建滚动框架
        canvas = tk.Canvas(manage_window)
        scrollbar = ttk.Scrollbar(manage_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")
        # 根据max_count创建输入框,每个对应一个持仓位置
        input_frames = []
        input_vars = []
        for i in range(max_count):
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, padx=10, pady=2)
            # 标签
            label = ttk.Label(frame, text=f"{i+1}:", width=8)
            label.pack(side=tk.LEFT, padx=(0, 5))
            # 输入框
            var = tk.StringVar()
            # 显示当前持仓股
            if i < len(holding_stocks) and holding_stocks[i]:
                stock_name, stock_code = holding_stocks[i]
                if stock_code:
                    var.set(f"{stock_name}({stock_code})")
                else:
                    var.set(stock_name if stock_name else "")
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            input_frames.append(frame)
            input_vars.append(var)
        # 打包canvas和scrollbar(在创建完所有输入框后)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")
        # 历史持仓股选择区域
        history_frame = ttk.LabelFrame(manage_window, text="历史持仓股(点击选择)", padding=5)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # 历史持仓股列表(使用Treeview显示)
        history_tree_frame = ttk.Frame(history_frame)
        history_tree_frame.pack(fill=tk.BOTH, expand=True)
        history_tree = ttk.Treeview(history_tree_frame, columns=("name", "code", "date"), show="headings", height=6)
        history_tree.heading("name", text="股票名称")
        history_tree.heading("code", text="股票代码")
        history_tree.heading("date", text="替换时间")
        history_tree.column("name", width=150)
        history_tree.column("code", width=100)
        history_tree.column("date", width=150)
        history_scrollbar = ttk.Scrollbar(history_tree_frame, orient="vertical", command=history_tree.yview)
        history_tree.configure(yscrollcommand=history_scrollbar.set)
        history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 加载历史持仓股
        def load_history_holdings():
            history_tree.delete(*history_tree.get_children())
            try:
                history_holdings = self.ai_config_manager.config.get("history_holdings", [])
                for item in history_holdings:
                    stock_name = item.get("stock_name", "").strip()
                    stock_code = item.get("stock_code", "").strip()
                    replaced_date = item.get("replaced_date", "").strip()
                    if stock_name or stock_code:
                        display_name = stock_name if stock_name else stock_code
                        history_tree.insert("", "end", values=(display_name, stock_code, replaced_date))
            except Exception as e:
                print(f"加载历史持仓股失败: {e}")
        load_history_holdings()
        # 历史持仓股选择按钮
        history_button_frame = ttk.Frame(history_frame)
        history_button_frame.pack(fill=tk.X, pady=(5, 0))
        def select_from_history():
            """从历史持仓股中选择并填充到当前选中的输入框"""
            selection = history_tree.selection()
            if not selection:
                messagebox.showwarning("提示", "请先选择历史持仓股", parent=manage_window)
                return
            # 获取选中的历史持仓股
            item = history_tree.item(selection[0])
            values = item['values']
            if len(values) >= 2:
                stock_name = values[0]
                stock_code = values[1]
                # 查找第一个空的输入框,或者让用户选择位置
                empty_index = None
                for i in range(max_count):
                    if i < len(input_vars) and not input_vars[i].get().strip():
                        empty_index = i
                        break
                if empty_index is not None:
                    # 自动填充到第一个空位置
                    if stock_code:
                        if stock_name and stock_name != stock_code:
                            input_vars[empty_index].set(f"{stock_name}({stock_code})")
                        else:
                            input_vars[empty_index].set(stock_code)
                    else:
                        input_vars[empty_index].set(stock_name)
                    messagebox.showinfo("成功", f"已填充到{empty_index+1}", parent=manage_window)
                else:
                    # 所有位置都有内容,让用户选择位置
                    position_window = self._toplevel(manage_window)
                    position_window.title("选择持仓位置")
                    position_window.geometry("300x400")
                    ttk.Label(position_window, text="请选择要填充的持仓位置:",
                             font=("TkDefaultFont", 12)).pack(pady=10)
                    position_var = tk.IntVar(value=0)
                    for i in range(max_count):
                        if i < len(input_vars):
                            current_text = input_vars[i].get().strip()
                            display_text = f"{i+1}: {current_text if current_text else '空'}"
                            ttk.Radiobutton(position_window, text=display_text, variable=position_var,
                                           value=i).pack(anchor=tk.W, padx=20, pady=2)
                    def confirm_position():
                        selected_index = position_var.get()
                        if stock_code:
                            if stock_name and stock_name != stock_code:
                                input_vars[selected_index].set(f"{stock_name}({stock_code})")
                            else:
                                input_vars[selected_index].set(stock_code)
                        else:
                            input_vars[selected_index].set(stock_name)
                        position_window.destroy()
                        messagebox.showinfo("成功", f"已填充到{selected_index+1}", parent=manage_window)
                    ttk.Button(position_window, text="确定", command=confirm_position).pack(pady=10)
        ttk.Button(history_button_frame, text="选择填充", command=select_from_history, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(history_button_frame, text="刷新列表", command=load_history_holdings, width=12).pack(side=tk.LEFT, padx=5)
        # 按钮区域
        button_frame = ttk.Frame(manage_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        def save_holdings():
            """保存持仓股"""
            for i in range(max_count):
                if i >= len(input_vars):
                    break
                input_text = input_vars[i].get().strip()
                if not input_text:
                    # 清空该持仓位置
                    holding_stocks[i] = None
                    self._update_holding_label(i, check_conditions=False, group_index=group_index)
                    continue
                # 解析输入
                stock_name = None
                stock_code = None
                # 检查是否是股票代码(6位数字)
                if input_text.isdigit() and len(input_text) == 6:
                    stock_code = input_text
                    stock_name = None  # 稍后通过代码获取名称
                elif "(" in input_text and ")" in input_text:
                    # 格式:名称(代码) 或 代码(名称)
                    parts = input_text.split("(")
                    if len(parts) == 2:
                        part1 = parts[0].strip()
                        part2 = parts[1].replace(")", "").strip()
                        if part2.isdigit() and len(part2) == 6:
                            # 名称(代码)
                            stock_name = part1
                            stock_code = part2
                        else:
                            # 代码(名称)
                            stock_code = part1
                            stock_name = part2
                else:
                    # 可能是股票名称或代码
                    if input_text.isdigit() and len(input_text) == 6:
                        stock_code = input_text
                    else:
                        stock_name = input_text
                # 如果没有股票代码,尝试通过名称获取
                if not stock_code and stock_name:
                    stock_code = get_stock_code_by_name(stock_name)
                # 如果没有股票名称,尝试通过代码获取
                if not stock_name and stock_code:
                    # 可以通过akshare获取股票名称
                    try:
                        import akshare as ak
                        stock_info = ak.stock_individual_info_em(symbol=stock_code)
                        if stock_info is not None and not stock_info.empty:
                            # 尝试从信息中获取名称
                            for _, row in stock_info.iterrows():
                                if row.get('item', '') == '股票简称' or row.get('item', '') == '股票名称':
                                    stock_name = row.get('value', '')
                                    break
                    except:
                        pass
                # 确保至少有一个值
                if stock_name or stock_code:
                    holding_stocks[i] = (stock_name if stock_name else '', stock_code if stock_code else '')
                else:
                    holding_stocks[i] = None
                # 立即更新显示(不执行检测)
                self._update_holding_label(i, check_conditions=False, group_index=group_index)
                # 强制刷新界面
                self._safe_update_idletasks()
            # 强制更新所有持仓标签显示(不执行检测)
            for j in range(max_count):
                if j < len(holding_stocks):
                    self._update_holding_label(j, check_conditions=False, group_index=group_index)
                self._safe_update_idletasks()
            # 如果是在弹出窗口中,更新弹出窗口显示
            if popup_window and hasattr(popup_window, '_update_display'):
                popup_window._update_display()
            # 保存持仓股到配置文件
            self._save_holdings_to_config(group_index)
            manage_window.destroy()
            messagebox.showinfo("成功", "持仓股已更新并保存,正在检测...", parent=self.root)
            # 更新后自动触发一次检测
            self._check_holdings(group_index, max_count=max_count)
        ttk.Button(button_frame, text="保存", command=save_holdings, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=manage_window.destroy, width=10).pack(side=tk.LEFT, padx=5)


    def _save_holdings_to_config(self, group_index=1):
        """保存持仓股到配置文件,并将替换掉的持仓股保存到历史持仓股"""
        try:
            # 获取对应组的数据结构
            holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
            # 配置文件键名根据组索引不同
            config_key = f"holding_stocks_{group_index}" if group_index > 1 else "holding_stocks"
            # 获取之前的持仓股数据(用于比较)
            old_holdings_data = self.ai_config_manager.config.get(config_key, [])
            old_holdings_dict = {}
            # 所有持仓组都支持80个股票
            max_index = 80
            for item in old_holdings_data:
                index = item.get("index", -1)
                if 0 <= index < max_index:
                    stock_name = item.get("stock_name", "").strip()
                    stock_code = item.get("stock_code", "").strip()
                    if stock_name or stock_code:
                        old_holdings_dict[index] = (stock_name, stock_code)
            # 准备新的持仓股数据(保存所有80个)
            holdings_data = []
            replaced_holdings = []  # 被替换的持仓股
            # 保存所有持仓股(所有组都支持80个)
            save_count = 80
            for i in range(save_count):
                if i < len(holding_stocks):
                    holding = holding_stocks[i]
                else:
                    holding = None
                if holding and (holding[0] or holding[1]):  # 如果有股票名称或代码
                    stock_name, stock_code = holding
                    holdings_data.append({
                        "index": i,
                        "stock_name": stock_name if stock_name else "",
                        "stock_code": stock_code if stock_code else ""
                    })
                    # 检查是否替换了之前的持仓股
                    if i in old_holdings_dict:
                        old_holding = old_holdings_dict[i]
                        if old_holding[0] != stock_name or old_holding[1] != stock_code:
                            # 被替换了,保存到历史持仓股
                            replaced_holdings.append({
                                "stock_name": old_holding[0],
                                "stock_code": old_holding[1],
                                "replaced_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            })
                else:
                    holdings_data.append({
                        "index": i,
                        "stock_name": "",
                        "stock_code": ""
                    })
                    # 如果之前有持仓股,现在被清空了,也保存到历史持仓股
                    if i in old_holdings_dict:
                        old_holding = old_holdings_dict[i]
                        replaced_holdings.append({
                            "stock_name": old_holding[0],
                            "stock_code": old_holding[1],
                            "replaced_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
            # 保存当前持仓股到配置文件
            self.ai_config_manager.config[config_key] = holdings_data
            # 保存历史持仓股(去重,避免重复添加)
            history_holdings = self.ai_config_manager.config.get("history_holdings", [])
            history_dict = {}  # 用于去重,key为 stock_code
            # 将现有历史持仓股加入字典
            for item in history_holdings:
                code = item.get("stock_code", "").strip()
                if code:
                    history_dict[code] = item
            # 添加新的历史持仓股(去重)
            for item in replaced_holdings:
                code = item.get("stock_code", "").strip()
                if code and code not in history_dict:
                    history_dict[code] = item
            # 转换回列表
            history_holdings = list(history_dict.values())
            # 按替换时间倒序排列(最新的在前)
            history_holdings.sort(key=lambda x: x.get("replaced_date", ""), reverse=True)
            # 限制历史持仓股数量(最多保留100个)
            if len(history_holdings) > 100:
                history_holdings = history_holdings[:100]
            self.ai_config_manager.config["history_holdings"] = history_holdings
            self.ai_config_manager.save_config()
        except Exception as e:
            print(f"保存持仓股到配置文件失败: {e}")


    def _load_holdings_from_config(self, group_index=1, display_only=False):
        """从配置文件加载持仓股(不执行检测,检测由首次加载时的_check_holdings执行)
        Args:
            group_index: 持仓组索引
            display_only: 如果为True,只加载前20个到标签页显示(用于持仓历史股)
        """
        try:
            # 获取对应组的数据结构
            holding_stocks, holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
            # 配置文件键名根据组索引不同
            config_key = f"holding_stocks_{group_index}" if group_index > 1 else "holding_stocks"
            holdings_data = self.ai_config_manager.config.get(config_key, [])
            if holdings_data:
                # 所有持仓组都支持80个股票
                max_index = 80
                # 如果是display_only模式,只加载前20个到标签页显示;否则加载所有80个
                for item in holdings_data:
                    index = item.get("index", -1)
                    if 0 <= index < max_index:  # 始终加载所有80个到内存
                        stock_name = item.get("stock_name", "").strip()
                        stock_code = item.get("stock_code", "").strip()
                        if stock_name or stock_code:
                            holding_stocks[index] = (stock_name, stock_code)
                        else:
                            holding_stocks[index] = None
                # 更新所有持仓标签显示(不执行检测,只更新显示)
                # 标签页只显示前20个
                update_count = min(20, len(holding_labels)) if display_only else 80
                for i in range(update_count):
                    if i < len(holding_labels):
                        self._update_holding_label(i, check_conditions=False, group_index=group_index, fetch_daily_change=False)
        except Exception as e:
            print(f"从配置文件加载持仓股失败: {e}")


    def _update_holding_label(self, index, check_conditions=False, group_index=1, daily_change_pct=None, fetch_daily_change=True):
        """
        更新持仓股标签显示
        Args:
            index: 持仓股索引
            check_conditions: 是否执行检测,默认False(只在首次加载和手动检测时设为True)
            group_index: 持仓组索引(1-5),默认1
            daily_change_pct: 当日涨跌幅(持仓检测时传入),显示在按钮右侧
            fetch_daily_change: 是否联网拉取当日涨跌幅;批量初始化时应为 False,否则会阻塞界面数百次请求
        """
        # 获取对应组的数据结构
        holding_stocks, holding_labels, holding_kelly_results, holding_low_diff_results = self._get_holding_group_data(group_index)
        if index < len(holding_labels):
            label = holding_labels[index]
            # 检查持仓股是否存在且不为None
            if (index < len(holding_stocks) and
                holding_stocks[index] is not None and
                holding_stocks[index]):
                stock_name, stock_code = holding_stocks[index]
                change_pct_val = None  # 用于持仓7-14无凯利结果时按涨跌幅着色
                # 构建显示文本 - 显示股票名和仓位,去除"持仓"字样
                if stock_name:
                    # 去除股票名中的"持仓"字样
                    display_text = stock_name.replace("持仓", "").strip()
                    if stock_code:
                        display_text += f" ({stock_code})"
                elif stock_code:
                    display_text = stock_code
                else:
                    display_text = f"{index+1}"
                # 日K 昨未站上1日线、今收站上 → ▲(与「信号」同源,紧接在名称/代码后)
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    if holding_kelly_results[index].get('ma1_close_tri'):
                        display_text += " ▲"
                # 添加支撑阻力标记
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    kelly_result = holding_kelly_results[index]
                    if kelly_result.get('near_support_buy'):
                        display_text += " [撑]"
                    if kelly_result.get('near_resistance_sell'):
                        display_text += " [阻]"
                    if kelly_result.get('new_high'):
                        display_text += " [新高]"
                # 添加凯利公式百分比(「信号」轻量检测不写凯利,不显示 0%)
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    kelly_result = holding_kelly_results[index]
                    if not kelly_result.get('signal_lightweight'):
                        kelly_percent = kelly_result['ratio'] * 100
                        display_text += f" [{kelly_percent:.1f}%]"
                # 游资心法得分 (异步缓存)
                _hm_key = stock_code
                _hm_cache = getattr(self, '_hm_scores_cache', {})
                _hm_score = _hm_cache.get(_hm_key)
                if _hm_score is not None and isinstance(_hm_score, (int, float)):
                    display_text += f" 🦅{int(_hm_score)}"
                elif _hm_key and _hm_key.isdigit() and len(_hm_key) == 6:
                    # cache miss → 后台线程算, 算完后刷新按钮
                    import threading as _th_hm
                    def _hm_bg(_code, _idx, _gi):
                        try:
                            self._hm_calc_for_stock(_code)
                            self.root.after(0, lambda: self._update_holding_label(_idx, group_index=_gi, fetch_daily_change=False))
                        except Exception:
                            pass
                    _th_hm.Thread(target=_hm_bg, args=(_hm_key, index, group_index), daemon=True).start()
                # 当日涨跌幅:优先使用持仓检测传入的值,否则实时拉取
                change_pct_text = ""
                current_price = None
                amplitude_pct = None
                if daily_change_pct is not None:
                    change_pct_val = float(daily_change_pct)
                    if change_pct_val > 0 or change_pct_val < 0:
                        change_pct_text = f" [{change_pct_val:.1f}%]"
                    else:
                        change_pct_text = " [0.0%]"
                        change_pct_val = 0.0
                elif stock_code and fetch_daily_change:
                    try:
                        # 优先用 Tushare 最近两日收盘计算涨跌幅;取不到再回退实时行情
                        change_pct = self._get_holding_daily_change_pct_tushare(stock_code)
                        spot_row = None
                        if change_pct is None:
                            spot_row = self._get_realtime_spot_row_for_holding(stock_code, cache_duration=60)
                            if spot_row is not None:
                                change_pct = spot_row.get('涨跌幅')
                        if change_pct is not None:
                            change_pct_val = float(change_pct)
                            if change_pct_val > 0 or change_pct_val < 0:
                                change_pct_text = f" [{change_pct_val:.1f}%]"
                            else:
                                change_pct_text = " [0.0%]"
                                change_pct_val = 0.0
                        # 获取当前价格和振幅
                        if spot_row is None:
                            spot_row = self._get_realtime_spot_row_for_holding(stock_code, cache_duration=60)
                        if spot_row is not None:
                            current_price = spot_row.get('最新价')
                            high = spot_row.get('最高')
                            low = spot_row.get('最低')
                            if current_price is not None:
                                current_price = float(current_price)
                            if high is not None and low is not None:
                                high = float(high)
                                low = float(low)
                                if low > 0:
                                    amplitude_pct = (high - low) / low * 100
                    except Exception:
                        pass
                # 添加当前价格、涨跌幅、振幅到按钮右侧
                price_amp_text = ""
                if current_price is not None:
                    price_amp_text = f" {current_price:.2f}"
                if change_pct_text:
                    price_amp_text += change_pct_text
                if amplitude_pct is not None:
                    price_amp_text += f" 振{amplitude_pct:.1f}%"
                if price_amp_text:
                    display_text += price_amp_text
                # 添加5日最低点差%(第二行)
                low_diff_line = ""
                low_diff_pct = None
                if index < len(holding_low_diff_results) and holding_low_diff_results[index]:
                    low_diff_result = holding_low_diff_results[index]
                    low_diff_pct = low_diff_result.get('low_diff_pct', 0)
                    low_diff_line = f"\n差%: {low_diff_pct:+.2f}%"
                # 如果有第二行,添加到显示文本
                if low_diff_line:
                    display_text += low_diff_line
                # 鱼身/鱼尾(持仓检测写入 ma_status 后显示在按钮上);五星:5日低+1日线满足
                fish_suffix = ""
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    _kr_f = holding_kelly_results[index]
                    _rs = bool(_kr_f.get('red_star_signal'))
                    _ms = _kr_f.get('ma_status') or {}
                    if _ms.get('fish_body'):
                        fish_suffix = "\n鱼身" + (" ★" if _rs else "")
                    elif _ms.get('fish_tail'):
                        fish_suffix = "\n鱼尾" + (" ★" if _rs else "")
                    elif _rs:
                        fish_suffix = "\n★"
                if fish_suffix:
                    display_text += fish_suffix
                golden_suffix = ""
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    if holding_kelly_results[index].get('is_golden_stock'):
                        golden_suffix = "\n黄金股"
                if golden_suffix:
                    display_text += golden_suffix
                sr_suffix = ""
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    _kr = holding_kelly_results[index]
                    if _kr.get('near_support_buy'):
                        sr_suffix += "\n买入"
                    if _kr.get('near_resistance_sell'):
                        sr_suffix += "\n卖出"
                if sr_suffix:
                    display_text += sr_suffix
                # 尝试设置文本,如果文本太长则减小字体
                # 先使用默认字体
                label.config(text=display_text, font=("TkDefaultFont", 13))
                # 如果差%小于3%,用红色显示(设置整个标签的前景色)
                if low_diff_pct is not None and low_diff_pct < 3.0:
                    # 保存当前背景色,只改变前景色
                    current_bg = label.cget('bg')
                    label.config(fg="red", bg=current_bg)
                else:
                    # 恢复默认颜色(根据检测结果设置,这里先不设置,由后续的样式更新函数处理)
                    pass
                label.update_idletasks()
                # 检查文本是否超出按钮宽度,如果超出则减小字体
                try:
                    # 获取按钮实际宽度
                    button_width = label.winfo_width()
                    if button_width > 1:
                        # 使用字体度量来估算文本宽度(只计算第一行)
                        from tkinter import font as tkfont
                        default_font = tkfont.Font(family="TkDefaultFont", size=13)
                        first_line = display_text.split('\n')[0] if '\n' in display_text else display_text
                        text_width = default_font.measure(first_line)
                        # 如果文本宽度超过按钮宽度的90%,减小字体
                        if text_width > button_width * 0.9:
                            # 尝试不同的字体大小
                            for font_size in [12, 11, 10, 9]:
                                test_font = tkfont.Font(family="TkDefaultFont", size=font_size)
                                text_width = test_font.measure(first_line)
                                if text_width <= button_width * 0.9:
                                    label.config(font=("TkDefaultFont", font_size))
                                    break
                except:
                    # 如果获取宽度失败,使用默认字体
                    label.config(font=("TkDefaultFont", 13))
            else:
                label.config(text=f"{index+1}", bg="lightgray", fg="black")
            # 只有在明确要求检测时才执行检测(首次加载和手动检测按钮)
            if check_conditions and (index < len(holding_stocks) and
                holding_stocks[index] is not None and
                holding_stocks[index]):
                # 获取大盘情绪指数
                market_score = self._get_market_sentiment_score()
                stock_name, stock_code = holding_stocks[index]
                try:
                    can_open = self._check_holding_conditions(stock_name, stock_code)
                    self._update_holding_label_style(label, can_open, market_score, index, group_index)
                    # 黄金股:金底;否则鱼身红底 / 鱼尾绿底(覆盖均线格线样式)
                    if index < len(holding_kelly_results) and holding_kelly_results[index]:
                        _kr = holding_kelly_results[index]
                        _ms = _kr.get('ma_status') or {}
                        try:
                            if hasattr(label, '_stripe_canvas'):
                                label._stripe_canvas.destroy()
                                del label._stripe_canvas
                        except Exception:
                            pass
                        if _kr.get('is_golden_stock'):
                            label.config(highlightthickness=0, bg='#DAA520', fg='#1a1a1a')
                        elif _ms.get('fish_body'):
                            label.config(highlightthickness=0, bg='#c62828', fg='white')
                        elif _ms.get('fish_tail'):
                            label.config(highlightthickness=0, bg='#2e7d32', fg='white')
                        if _kr.get('red_star_signal') or _kr.get('ma1_close_tri'):
                            label.config(highlightthickness=2, highlightbackground='red', highlightcolor='red')
                except Exception:
                    # 如果检测失败,使用默认样式
                    label.config(bg="lightgray", fg="black")
            elif not check_conditions and (index < len(holding_stocks) and
                holding_stocks[index] is not None and
                holding_stocks[index]):
                # 不检测时,只使用已有的凯利结果来更新样式(如果有)
                if index < len(holding_kelly_results) and holding_kelly_results[index]:
                    # 使用已有的检测结果更新样式
                    kelly_result = holding_kelly_results[index]
                    ma_status = kelly_result.get('ma_status', {})
                    # 判断是否满足开新仓条件(所有均线都满足)
                    can_open = all(ma_status.get(ma_key, False) for ma_key in ['ma1', 'ma5', 'ma10', 'ma20'])
                    market_score = self._get_market_sentiment_score()
                    self._update_holding_label_style(label, can_open, market_score, index, group_index)
                    _ms = kelly_result.get('ma_status') or {}
                    if (kelly_result.get('is_golden_stock') or _ms.get('fish_body') or _ms.get('fish_tail')
                            or kelly_result.get('red_star_signal') or kelly_result.get('ma1_close_tri')):
                        try:
                            if hasattr(label, '_stripe_canvas'):
                                label._stripe_canvas.destroy()
                                del label._stripe_canvas
                        except Exception:
                            pass
                        if kelly_result.get('is_golden_stock'):
                            label.config(highlightthickness=0, bg='#DAA520', fg='#1a1a1a')
                        elif _ms.get('fish_body'):
                            label.config(highlightthickness=0, bg='#c62828', fg='white')
                        elif _ms.get('fish_tail'):
                            label.config(highlightthickness=0, bg='#2e7d32', fg='white')
                        if kelly_result.get('red_star_signal') or kelly_result.get('ma1_close_tri'):
                            label.config(highlightthickness=2, highlightbackground='red', highlightcolor='red')
                else:
                    # 没有检测结果时:持仓7-14(资讯日期标签页)按实时涨跌幅着色,其余用默认样式
                    if 7 <= group_index <= 14 and change_pct_val is not None:
                        if change_pct_val > 0:
                            label.config(fg="red", bg="white")
                        elif change_pct_val < 0:
                            label.config(fg="green", bg="white")
                        else:
                            label.config(fg="black", bg="white")
                    else:
                        label.config(bg="lightgray", fg="black")
            # 强制更新显示
            label.update_idletasks()


    def _update_holding_label_style(self, label, can_open, market_score, index=None, group_index=1):
        """更新持仓标签的样式(颜色和边框)"""
        # 检查label是否仍然有效
        try:
            # 尝试访问label的winfo_exists方法,如果label已被销毁会抛出异常
            if not hasattr(label, 'winfo_exists') or not label.winfo_exists():
                return
        except:
            return
        # 获取对应组的数据结构
        _holding_stocks, _holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
        # 设置字体颜色:均线检测通过(可开新仓)显示红色,否则绿色
        # 如果价格距离10日均线在3%以内,显示黄色
        try:
            # 检查是否距离10日均线在3%以内
            near_ma10 = False
            if index is not None and index < len(holding_kelly_results) and holding_kelly_results[index]:
                kelly_result = holding_kelly_results[index]
                ma_status = kelly_result.get('ma_status', {})
                near_ma10 = ma_status.get('near_ma10', False)
            # 检查支撑阻力和创新高标记
            has_support = False
            has_resistance = False
            has_new_high = False
            if index is not None and index < len(holding_kelly_results) and holding_kelly_results[index]:
                kelly_result = holding_kelly_results[index]
                has_support = kelly_result.get('near_support_buy', False)
                has_resistance = kelly_result.get('near_resistance_sell', False)
                has_new_high = kelly_result.get('new_high', False)
            # 设置颜色优先级:新高 > 支撑 > 阻力 > 均线状态
            if has_new_high:
                # 创新高:红色
                label.config(fg="red", bg="white")
            elif has_support:
                # 靠近支撑:红色
                label.config(fg="red", bg="white")
            elif has_resistance:
                # 靠近阻力:绿色
                label.config(fg="green", bg="white")
            elif near_ma10:
                # 距离10日均线在3%以内,显示黄色
                label.config(fg="orange", bg="white")
            elif can_open:
                label.config(fg="red", bg="white")
            else:
                label.config(fg="green", bg="white")
        except:
            return
        # 文本框已移除,点击按钮弹出详情界面查看
        # 添加网格线:大盘情绪不好(<30)用绿色网格,否则用黄色网格
        # 移除旧的网格Canvas
        if hasattr(label, '_grid_canvas'):
            try:
                label._grid_canvas.destroy()
            except:
                pass
            # 使用highlightthickness创建粗绿色边框
            try:
                label.config(highlightthickness=4, highlightbackground="green", highlightcolor="green")
            except:
                pass
            # 创建斜纹效果(使用Canvas在父容器上绘制)
            try:
                # 检查是否已有斜纹Canvas
                if hasattr(label, '_stripe_canvas'):
                    try:
                        label._stripe_canvas.destroy()
                    except:
                        pass
                # 获取标签的父容器和位置
                try:
                    parent = label.master
                    if parent:
                        label.update_idletasks()
                        # 再次检查label是否仍然有效
                        if not label.winfo_exists():
                            return
                        x = label.winfo_x()
                        y = label.winfo_y()
                        width = label.winfo_width()
                        height = label.winfo_height()
                        if width > 1 and height > 1:
                            # 再次检查label是否仍然有效
                            if not label.winfo_exists():
                                return
                            # 创建Canvas用于绘制斜纹(覆盖在标签区域)
                            stripe_canvas = tk.Canvas(parent, width=width, height=height,
                                                     highlightthickness=0, bg="", bd=0)
                            stripe_canvas.place(x=x, y=y)
                            label._stripe_canvas = stripe_canvas
                            # 绘制绿色斜纹(对角线)
                            stripe_width = 2
                            stripe_spacing = 8
                            for i in range(-height, width + height, stripe_spacing):
                                stripe_canvas.create_line(i, 0, i + height, height,
                                                         fill="darkgreen", width=stripe_width)
                except:
                    return
            except Exception as e:
                print(f"绘制斜纹边框失败: {e}")
        else:
            # 移除斜纹边框
            try:
                if label.winfo_exists():
                    label.config(highlightthickness=0)
                    if hasattr(label, '_stripe_canvas'):
                        try:
                            label._stripe_canvas.destroy()
                            del label._stripe_canvas
                        except:
                            pass
            except:
                pass


    def _open_history_holdings_window(self, group_index=5):
        """打开持仓管理窗口(80个股票)
        Args:
            group_index: 持仓组索引(1=持仓, 2=龙头股, 3=15Min, 4=Main, 5=持仓历史股, 6=同花顺, 7-14=持仓1-8)
        """
        try:
            # 获取对应组的数据结构
            _holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
            # 根据group_index确定窗口标题
            title_map = {
                1: "持仓管理(80个股票)",
                2: "龙头股管理(80个股票)",
                3: "15Min管理(80个股票)",
                4: "Main管理(80个股票)",
                5: "持仓历史股管理(80个股票)",
                6: "同花顺管理(80个股票)",
                7: "持仓1管理(80个股票)",
                8: "持仓2管理(80个股票)",
                9: "持仓3管理(80个股票)",
                10: "持仓4管理(80个股票)",
                11: "持仓5管理(80个股票)",
                12: "持仓6管理(80个股票)",
                13: "持仓7管理(80个股票)",
                14: "持仓8管理(80个股票)"
            }
            window_title = title_map.get(group_index, f"持仓{group_index}管理(80个股票)")
            # 创建弹出窗口
            popup_window = self._safe_toplevel(self.root)
            popup_window.title(window_title)
            popup_window.geometry("1600x900")
            # 主框架
            main_frame = ttk.Frame(popup_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 控制按钮区域
            control_frame = ttk.Frame(main_frame)
            control_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Button(control_frame, text="导入持仓", command=lambda: self._import_holdings(group_index, max_count=80, popup_window=popup_window), width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(control_frame, text="持仓股管理", command=lambda: self._manage_holdings(group_index, max_count=80, popup_window=popup_window), width=12).pack(side=tk.LEFT, padx=(0, 5))
            def check_holdings_with_update():
                """检测持仓股并更新弹出窗口显示(执行均线检测和凯利公式计算)"""
                # 开始检测前先更新一次显示
                update_display()
                # 开始检测
                self._check_holdings(group_index, max_count=80)
                # 检测完成后更新显示(延迟更长时间,确保所有检测完成)
                # 80个股票,每个间隔1秒,需要至少80秒
                # 先延迟5秒更新一次,然后每隔10秒更新一次,直到检测完成(最多等待120秒)
                update_count = [0]  # 使用列表以便在嵌套函数中修改
                max_updates = 12  # 最多更新12次(120秒)
                def update_after_delay():
                    if update_count[0] < max_updates:
                        update_display()
                        update_count[0] += 1
                        popup_window.after(10000, update_after_delay)  # 每10秒更新一次
                popup_window.after(5000, update_after_delay)  # 首次延迟5秒更新
            ttk.Button(control_frame, text="持仓检测", command=check_holdings_with_update, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(control_frame, text="凯利设定", command=self._show_kelly_config, width=12).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(control_frame, text="持仓计算", command=self._open_holding_calculator, width=12).pack(side=tk.LEFT, padx=(0, 5))
            def calculate_5day_low_diff_with_update():
                """计算5日最低点差%并更新弹出窗口显示"""
                # 开始计算前先更新一次显示
                update_display()
                # 开始计算
                self._calculate_5day_low_diff(group_index, max_count=80)
                # 计算完成后更新显示(延迟更长时间,确保所有计算完成)
                # 80个股票,每个间隔0.5秒,需要至少40秒
                # 先延迟5秒更新一次,然后每隔5秒更新一次,直到计算完成(最多等待60秒)
                update_count = [0]  # 使用列表以便在嵌套函数中修改
                max_updates = 12  # 最多更新12次(60秒)
                def update_after_delay():
                    if update_count[0] < max_updates:
                        update_display()
                        update_count[0] += 1
                        popup_window.after(5000, update_after_delay)  # 每5秒更新一次
                popup_window.after(5000, update_after_delay)  # 首次延迟5秒更新
            ttk.Button(control_frame, text="5日最低点", command=calculate_5day_low_diff_with_update, width=12).pack(side=tk.LEFT, padx=(0, 5))
            # 创建滚动框架显示80个股票
            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            # 确保scrollable_frame填满canvas的宽度
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            def on_canvas_configure(event):
                canvas_width = event.width
                canvas.itemconfig(canvas_window, width=canvas_width)
            canvas.bind('<Configure>', on_canvas_configure)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 创建80个持仓股显示按钮,每行5个,共16行
            popup_labels = []
            for row in range(16):  # 16行
                row_frame = ttk.Frame(scrollable_frame)
                row_frame.pack(fill=tk.BOTH, expand=True, pady=2)  # 与主界面持仓股按钮行间距一致
                for col in range(5):  # 每行5个
                    i = row * 5 + col
                    stock_frame = ttk.Frame(row_frame)
                    stock_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)  # 减少padx
                    # 按钮(点击弹出详情)
                    label = tk.Label(stock_frame, text=f"{i+1}",
                                   font=("TkDefaultFont", 11),
                                   bg="lightgray",
                                   relief=tk.RAISED,
                                   padx=5, pady=8,  # 与主界面持仓股按钮高度一致
                                   cursor="hand2")
                    label.pack(fill=tk.BOTH, expand=True)
                    # 绑定点击事件,打开详情弹出框
                    def make_click_handler(idx=i, gidx=group_index):
                        def on_click(event):
                            self._show_holding_detail(idx, gidx)
                        return on_click
                    label.bind("<Button-1>", make_click_handler())
                    popup_labels.append(label)
            # 更新显示(从配置加载所有80个股票)
            def update_display():
                # 重新获取最新的数据结构(确保获取最新数据)
                current_stocks, _current_labels, current_kelly_results, current_low_diff_results = self._get_holding_group_data(group_index)
                # 获取大盘情绪指数
                self._get_market_sentiment_score()
                for i in range(80):
                    if i < len(popup_labels):
                        if i < len(current_stocks) and current_stocks[i]:
                            stock_name, stock_code = current_stocks[i]
                            display_text = stock_name.replace("持仓", "").strip()
                            # 添加凯利公式百分比(如果有检测结果)
                            if i < len(current_kelly_results) and current_kelly_results[i]:
                                kelly_result = current_kelly_results[i]
                                kelly_percent = kelly_result.get('ratio', 0) * 100
                                display_text += f" [{kelly_percent:.1f}%]"
                            # 获取实时涨跌幅
                            change_pct_text = ""
                            if stock_code:
                                try:
                                    spot_row = get_realtime_spot_row(stock_code, cache_duration=60)
                                    if spot_row is not None:
                                        change_pct = spot_row.get('涨跌幅')
                                        if change_pct is not None:
                                            change_pct_val = float(change_pct)
                                            # 格式化涨跌幅,正数显示+号,负数显示-号
                                            if change_pct_val > 0:
                                                change_pct_text = f" +{change_pct_val:.2f}%"
                                            elif change_pct_val < 0:
                                                change_pct_text = f" {change_pct_val:.2f}%"
                                            else:
                                                change_pct_text = " 0.00%"
                                except Exception:
                                    # 获取失败时忽略,不显示涨跌幅
                                    pass
                            # 添加涨跌幅到文本最右边
                            if change_pct_text:
                                display_text += change_pct_text
                            # 添加5日最低点差%(第二行)
                            low_diff_line = ""
                            low_diff_pct = None
                            if i < len(current_low_diff_results) and current_low_diff_results[i]:
                                low_diff_result = current_low_diff_results[i]
                                low_diff_pct = low_diff_result.get('low_diff_pct', 0)
                                low_diff_line = f"\n差%: {low_diff_pct:+.2f}%"
                            # 如果有第二行,添加到显示文本
                            if low_diff_line:
                                display_text += low_diff_line
                            # 根据检测结果设置颜色
                            can_open = False
                            near_ma10 = False
                            if i < len(current_kelly_results) and current_kelly_results[i]:
                                kelly_result = current_kelly_results[i]
                                ma_status = kelly_result.get('ma_status', {})
                                # 判断是否满足开新仓条件(所有均线都满足)
                                can_open = all(ma_status.get(ma_key, False) for ma_key in ['ma1', 'ma5', 'ma10', 'ma20'])
                                near_ma10 = ma_status.get('near_ma10', False)
                            # 设置文本和颜色
                            popup_labels[i].config(text=display_text, font=("TkDefaultFont", 11), bg="white")
                            # 如果差%小于3%,用红色显示(优先级最高)
                            if low_diff_pct is not None and low_diff_pct < 3.0:
                                popup_labels[i].config(fg="red")
                            # 否则根据检测结果设置颜色(与主界面一致)
                            elif near_ma10:
                                popup_labels[i].config(fg="orange")
                            elif can_open:
                                popup_labels[i].config(fg="red")
                            else:
                                popup_labels[i].config(fg="green")
                            popup_labels[i].update_idletasks()
                            # 检查文本是否超出按钮宽度,如果超出则减小字体
                            try:
                                button_width = popup_labels[i].winfo_width()
                                if button_width > 1:
                                    from tkinter import font as tkfont
                                    default_font = tkfont.Font(family="TkDefaultFont", size=9)
                                    text_width = default_font.measure(display_text)
                                    if text_width > button_width * 0.9:
                                        for font_size in [8, 7, 6, 5]:
                                            test_font = tkfont.Font(family="TkDefaultFont", size=font_size)
                                            text_width = test_font.measure(display_text)
                                            if text_width <= button_width * 0.9:
                                                popup_labels[i].config(font=("TkDefaultFont", font_size))
                                                break
                            except:
                                pass
                        else:
                            popup_labels[i].config(text=f"{i+1}", bg="lightgray", fg="black")
            # 从配置文件加载所有80个股票(确保加载所有80个,不只是前12个)
            self._load_holdings_from_config(group_index, display_only=False)
            # 初始更新显示
            update_display()
            # 保存弹出窗口引用,以便后续更新
            popup_window._update_display = update_display
            popup_window._popup_labels = popup_labels
            popup_window._group_index = group_index  # 保存group_index以便后续使用
            # 将弹出窗口引用保存到类中,以便检测完成后更新
            if not hasattr(self, '_history_holdings_popup_windows'):
                self._history_holdings_popup_windows = []
            if popup_window not in self._history_holdings_popup_windows:
                self._history_holdings_popup_windows.append(popup_window)
            # 窗口关闭时移除引用
            def on_close():
                if hasattr(self, '_history_holdings_popup_windows'):
                    if popup_window in self._history_holdings_popup_windows:
                        self._history_holdings_popup_windows.remove(popup_window)
                popup_window.destroy()
            popup_window.protocol("WM_DELETE_WINDOW", on_close)
        except Exception as e:
            import traceback
            error_msg = f"打开持仓历史股管理窗口失败: {e}\n{traceback.format_exc()}"
            print(error_msg)
            messagebox.showerror("错误", f"打开持仓历史股管理窗口失败: {e}", parent=self.root)


    def _check_holdings(self, group_index=1, max_count=None):
        """检测持仓股:三维一体(均线/凯利/资金)+ 黄金/压力支撑/五星,以及与「信号」同源的日K收盘1日上穿 ▲。"""
        # 获取对应组的数据结构
        holding_stocks, holding_labels, holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
        if not any(holding_stocks):
            messagebox.showwarning("警告", "请先导入持仓股", parent=self.root)
            return
        # 获取大盘情绪指数
        market_score = self._get_market_sentiment_score()
        # 在新线程中执行检测
        def check_thread():
            for i, holding in enumerate(holding_stocks):
                if holding:
                    stock_name, stock_code = holding
                    daily_change_pct = None
                    try:
                        # 同时获取当日涨跌幅,供按钮右侧显示(优先 Tushare 最近两日收盘计算)
                        try:
                            daily_change_pct = self._get_holding_daily_change_pct_tushare(stock_code)
                            if daily_change_pct is None:
                                spot = self._get_realtime_spot_row_for_holding(stock_code)
                                if spot and spot.get('涨跌幅') is not None:
                                    daily_change_pct = float(spot.get('涨跌幅'))
                        except Exception:
                            pass
                        # 使用三维一体检测(技术仓位资金检测)
                        detection_result = self._three_dimensional_detection(stock_name, stock_code)
                        if detection_result['success']:
                            can_open = detection_result['technical']['can_open']
                            ma_status = detection_result['technical']['ma_status']
                            kelly_result = detection_result['position']
                            is_golden = False
                            try:
                                is_golden = bool(self._check_golden_stock_recent_20d(stock_code, stock_name or ''))
                            except Exception:
                                pass
                            near_buy, near_sell = False, False
                            try:
                                near_buy, near_sell = self._holding_sr_buy_sell_from_daily_kline(stock_code)
                            except Exception:
                                pass
                            red_star = False
                            try:
                                red_star = bool(self._holding_red_star_signal_5d_low_ma1(stock_code))
                            except Exception:
                                pass
                            ma1_tri = False
                            try:
                                ma1_tri = bool(self._signal_ma1_close_crossed_up_last_bar(stock_code))
                            except Exception:
                                pass
                            # 检查是否创新高
                            new_high = False
                            try:
                                new_high = bool(self._check_new_high(stock_code))
                            except Exception:
                                pass
                            # 存储凯利公式结果
                            holding_kelly_results[i] = {
                                'ratio': kelly_result['kelly_ratio'],
                                'b': kelly_result['b'],
                                'p': kelly_result['p'],
                                'ma_status': ma_status.copy(),
                                'is_golden_stock': is_golden,
                                'near_support_buy': near_buy,
                                'near_resistance_sell': near_sell,
                                'red_star_signal': red_star,
                                'ma1_close_tri': ma1_tri,
                                'new_high': new_high,
                            }
                            # 在主线程中更新UI(传入当日涨跌幅,显示在按钮右侧)
                            def update_ui(idx=i, result=can_open, name=stock_name, code=stock_code, score=market_score, gidx=group_index, pct=daily_change_pct):
                                if idx < len(holding_labels):
                                    self._update_holding_label(idx, check_conditions=True, group_index=gidx, daily_change_pct=pct)
                                # 更新所有打开的弹出窗口
                                if hasattr(self, '_history_holdings_popup_windows'):
                                    for popup in self._history_holdings_popup_windows:
                                        if popup.winfo_exists() and hasattr(popup, '_update_display'):
                                            try:
                                                popup._update_display()
                                            except:
                                                pass
                            self.root.after(0, update_ui)
                        else:
                            # 检测失败也更新按钮文字(含当日涨跌幅)
                            def update_ui_fail(idx=i, gidx=group_index, pct=daily_change_pct):
                                if idx < len(holding_labels):
                                    self._update_holding_label(idx, check_conditions=False, group_index=gidx, daily_change_pct=pct)
                            self.root.after(0, update_ui_fail)
                            print(f"三维一体检测失败: {detection_result.get('error', '未知错误')}")
                        # 每个股票检测间隔1秒,避免请求过快
                        time.sleep(1)
                    except Exception as e:
                        print(f"检测持仓股 {stock_name} 失败: {e}")
            # 检测完成后,再次更新所有弹出窗口
            def final_update():
                if hasattr(self, '_history_holdings_popup_windows'):
                    for popup in self._history_holdings_popup_windows:
                        if popup.winfo_exists() and hasattr(popup, '_update_display'):
                            try:
                                popup._update_display()
                            except:
                                pass
            self.root.after(1000, final_update)  # 延迟1秒后更新,确保所有检测完成
        thread = threading.Thread(target=check_thread, daemon=True)
        thread.start()


    def _detect_and_store_one_holding_slot(self, group_index, slot_index):
        """「信号」全表检测:逐格只做均线鱼身/鱼尾(_check_ma_status)、五星、日K收盘1日上穿(▲);不拉三维/大单/侧栏/10日等统计。
        返回 (log_line, daily_change_pct 或 None, meta_dict);无股票则 (None, None, None)。
        meta_dict 含 fish_body, fish_tail, red_star, ma1_tri, sidebar(空)。"""
        meta = {
            "fish_body": False, "fish_tail": False, "red_star": False,
            "ma1_tri": False, "buy": False, "sell": False, "sidebar": "",
            "skipped_ma20": False,
        }
        holding_stocks, _holding_labels, holding_kelly_results, _ = self._get_holding_group_data(group_index)
        if slot_index >= len(holding_stocks) or not holding_stocks[slot_index]:
            return None, None, None
        stock_name, stock_code = holding_stocks[slot_index]
        daily_change_pct = None
        try:
            spot = self._get_realtime_spot_row_for_holding(stock_code)
            if spot and spot.get('涨跌幅') is not None:
                daily_change_pct = float(spot.get('涨跌幅'))
        except Exception:
            pass
        tab_label = self._signal_tab_label_for_group(group_index)
        err_msg = None
        tags_joined = ''
        try:
            ma_status = self._check_ma_status(stock_code)
            red_star = False
            try:
                red_star = bool(self._holding_red_star_signal_5d_low_ma1(stock_code))
            except Exception:
                pass
            ma1_tri = False
            try:
                ma1_tri = bool(self._signal_ma1_close_crossed_up_last_bar(stock_code))
            except Exception:
                pass
            # ✅ 凯利公式实时计算（之前硬编码 0.0）
            _kb, _kp = self._calculate_kelly_params(ma_status)
            holding_kelly_results[slot_index] = {
                'ratio': self._calculate_kelly_ratio(_kb, _kp),
                'b': _kb,
                'p': _kp,
                'ma_status': ma_status.copy() if isinstance(ma_status, dict) else dict(ma_status or {}),
                'is_golden_stock': False,
                'near_support_buy': False,
                'near_resistance_sell': False,
                'red_star_signal': red_star,
                'ma1_close_tri': ma1_tri,
                'signal_lightweight': True,
            }
            parts = []
            if ma_status.get('fish_body'):
                parts.append('鱼身')
            elif ma_status.get('fish_tail'):
                parts.append('鱼尾')
            if red_star:
                parts.append('★')
            if ma1_tri:
                parts.append('▲')
            tags_joined = ' '.join(parts) if parts else ''
            meta["fish_body"] = bool(ma_status.get("fish_body"))
            meta["fish_tail"] = bool(ma_status.get("fish_tail"))
            meta["red_star"] = bool(red_star)
            meta["ma1_tri"] = bool(ma1_tri)
        except Exception as e:
            err_msg = str(e)
        meta["sidebar"] = ""
        # ✅ 计算凯利百分比（之前硬编码）
        try:
            _kb2, _kp2 = self._calculate_kelly_params(ma_status) if ma_status else (1.0, 0.5)
            _kelly_ratio = self._calculate_kelly_ratio(_kb2, _kp2)
        except Exception:
            _kb2, _kp2, _kelly_ratio = 1.0, 0.5, 0.0
        meta["kelly_ratio"] = _kelly_ratio
        meta["kelly_b"] = _kb2
        meta["kelly_p"] = _kp2
        meta["kelly_pct"] = round(_kelly_ratio * 100, 1)
        if err_msg:
            line = f"[{tab_label}] #{slot_index + 1} {stock_name} ({stock_code}) ✗ {err_msg}"
        else:
            _k = f"🎯{_kelly_ratio*100:.0f}%" if _kelly_ratio > 0 else ""
            line = f"[{tab_label}] #{slot_index + 1} {stock_name} ({stock_code}) → {tags_joined or '-'} {_k}"
        return line, daily_change_pct, meta


    def show_signal_all_holdings_detection(self):
        """信号:标签页 1~14 有仓位的格子逐只检测;鱼身鱼尾、五星、1日收盘上穿▲;无20日线门槛/无三维大单/无10日统计与侧栏逻辑。"""
        tasks = []
        for g in range(1, 15):
            holding_stocks, _, _, _ = self._get_holding_group_data(g)
            for i in range(len(holding_stocks)):
                if holding_stocks[i]:
                    tasks.append((g, i))
        if not tasks:
            messagebox.showinfo("提示", "当前所有标签页均无持仓股票。", parent=self.root)
            return
        old = getattr(self, "_signal_all_holdings_win", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.destroy()
            except Exception:
                pass
        win = self._safe_toplevel(self.root)
        self._signal_all_holdings_win = win
        win.title("信号 - 全标签页持仓检测")
        win.geometry("1180x620")
        win.minsize(860, 420)
        win.transient(self.root)
        win._signal_is_max = False
        win._signal_saved_geom = "1180x620+80+60"
        def _signal_win_maximize():
            try:
                if not win.winfo_exists():
                    return
                if getattr(win, "_signal_is_max", False):
                    win.state("normal")
                    win.geometry(win._signal_saved_geom)
                    win._signal_is_max = False
                else:
                    win._signal_saved_geom = win.geometry()
                    if sys.platform == "win32":
                        win.state("zoomed")
                    else:
                        try:
                            win.attributes("-zoomed", True)
                        except Exception:
                            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
                            win.geometry(f"{sw}x{sh}+0+0")
                    win._signal_is_max = True
            except Exception:
                pass
        def _signal_win_minimize():
            try:
                if win.winfo_exists():
                    win.iconify()
            except Exception:
                pass
        def _signal_win_hide():
            try:
                if win.winfo_exists():
                    win.withdraw()
            except Exception:
                pass
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        top_row = ttk.Frame(top)
        top_row.pack(fill=tk.X)
        status_var = tk.StringVar(value=f"准备检测... 共 {len(tasks)} 只股票")
        ttk.Label(top_row, textvariable=status_var, font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, anchor=tk.W)
        title_btns = ttk.Frame(top_row)
        title_btns.pack(side=tk.RIGHT)
        ttk.Button(title_btns, text="最大化", width=7, command=_signal_win_maximize).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(title_btns, text="最小化", width=7, command=_signal_win_minimize).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(title_btns, text="隐藏", width=7, command=_signal_win_hide).pack(side=tk.LEFT)
        prog = ttk.Progressbar(top, mode="determinate", maximum=max(1, len(tasks)), length=760)
        prog.pack(fill=tk.X, pady=(6, 0))
        prog["value"] = 0
        eta_var = tk.StringVar(value="排队中:首只股票开始后会显示耗时与预计剩余...")
        ttk.Label(top, textvariable=eta_var, foreground="#444", font=("TkDefaultFont", 11)).pack(
            anchor=tk.W, pady=(2, 0)
        )
        pct_var = tk.StringVar(value="0%")
        ttk.Label(top, textvariable=pct_var, foreground="#1565c0", font=("TkDefaultFont", 11, "bold")).pack(
            anchor=tk.E, pady=(0, 2)
        )
        mid = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        log = scrolledtext.ScrolledText(mid, wrap=tk.WORD, width=72, font=("Consolas", 12))
        side = scrolledtext.ScrolledText(mid, wrap=tk.WORD, width=38, font=("TkDefaultFont", 11))
        mid.add(log, weight=3)
        mid.add(side, weight=2)
        # ✅ 双击 log 行弹日K图
        def _on_log_double_click(event):
            import re as _re_k
            import threading as _th_k
            # 获取点击位置的行号
            try:
                _line_idx = log.index(f"@{event.x},{event.y}").split(".")[0]
                _line_text = log.get(f"{_line_idx}.0", f"{_line_idx}.end")
            except Exception:
                return
            # 正则提 6 位股票代码
            _m = _re_k.search(r'\(([036]\d{5})\)', _line_text) or _re_k.search(r'\b([036]\d{5})\b', _line_text)
            if not _m:
                return
            _code = _m.group(1)
            # 提股票名（括号前的文字）
            _nm = ""
            _mn = _re_k.search(r'#\d+\s+([^\s(]+)\s*\(', _line_text)
            if _mn: _nm = _mn.group(1)
            if not _nm: _nm = _code
            def _kwork():
                try:
                    _kline = self._get_daily_kline_data_tushare(_code, days=120)
                except Exception:
                    _kline = None
                if _kline:
                    self.root.after(0, lambda: self._show_daily_kline_zoom(_kline, _nm))
                else:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "提示", f"无法获取 {_nm}({_code}) K线", parent=win))
            _th_k.Thread(target=_kwork, daemon=True).start()
        log.bind("<Double-1>", _on_log_double_click)
        # ===== 🔧 所有检测结果缓存（供扩展数据 + 保存功能使用）=====
        # 格式: [(tab_label, slot, stock_name, stock_code, line, daily_pct, meta_dict), ...]
        _signal_results_cache = []
        # ===== 按钮栏 =====
        bot = ttk.Frame(win, padding=8)
        bot.pack(fill=tk.X)
        # --- 右键菜单（log + side 都可用）---
        def _build_right_menu(txt_w):
            menu = tk.Menu(txt_w, tearoff=0)
            def _copy():
                try: txt_w.event_generate("<<Copy>>")
                except Exception:
                    sel = txt_w.get(tk.SEL_FIRST, tk.SEL_LAST)
                    if sel: self.root.clipboard_append(sel)
            def _select_all(): txt_w.tag_add(tk.SEL, "1.0", tk.END)
            def _copy_all():
                self.root.clipboard_append(txt_w.get("1.0", tk.END).strip())
            menu.add_command(label="拷贝选中 (⌘C)", command=_copy)
            menu.add_command(label="全选 (⌘A)", command=_select_all)
            menu.add_command(label="复制全部", command=_copy_all)
            menu.add_separator()
            menu.add_command(label="清空", command=lambda: txt_w.delete("1.0", tk.END))
            def _popup(event):
                menu.tk_popup(event.x_root, event.y_root)
            txt_w.bind("<Button-3>", _popup)
            try: txt_w.bind("<Control-c>", lambda e: (txt_w.event_generate("<<Copy>>"), "break"))
            except Exception: pass
            try: txt_w.bind("<Control-a>", lambda e: (_select_all(), "break"))
            except Exception: pass
        _build_right_menu(log)
        _build_right_menu(side)
        # --- 保存功能 ---
        def _save_txt():
            from tkinter import filedialog as fd
            content = log.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("提示", "日志为空，先点「信号」检测", parent=win)
                return
            path = fd.asksaveasfilename(parent=win, defaultextension=".txt",
                                       initialfile=f"信号检测_{time.strftime('%Y%m%d_%H%M%S')}.txt")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("保存成功", f"已保存到:\n{path}", parent=win)
        def _save_excel():
            from tkinter import filedialog as fd
            if not _signal_results_cache:
                messagebox.showwarning("提示", "还没有检测结果", parent=win)
                return
            path = fd.asksaveasfilename(parent=win, defaultextension=".xlsx",
                                       initialfile=f"信号检测_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")
            if not path: return
            try:
                import pandas as pd
                rows = []
                for rec in _signal_results_cache:
                    tab, slot, nm, co, line, pct, meta = rec
                    rows.append({
                        "标签页": tab, "位置": slot + 1, "名称": nm, "代码": co,
                        "日线信号": line.split("→")[-1].strip() if "→" in line else "",
                        "当日涨跌%": f"{pct:+.2f}" if pct is not None else "",
                        "鱼身": meta.get("fish_body", False),
                        "鱼尾": meta.get("fish_tail", False),
                        "红星★": meta.get("red_star", False),
                        "▲上穿": meta.get("ma1_tri", False),
                    })
                df = pd.DataFrame(rows)
                with pd.ExcelWriter(path, engine="openpyxl") as w:
                    df.to_excel(w, index=False, sheet_name="信号检测")
                messagebox.showinfo("保存成功", f"已保存 {len(df)} 只到:\n{path}", parent=win)
            except Exception as e:
                messagebox.showerror("Excel失败", str(e), parent=win)
        def _save_to_news():
            content = log.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("提示", "日志为空", parent=win)
                return
            tab_name = "信号检测"
            from datetime import datetime as _dt_n
            title = f"信号检测_{_dt_n.now().strftime('%Y-%m-%d %H:%M')}"
            try:
                self.save_news_info_to_db(tab_name, f"## {title}\n\n{content}")
                messagebox.showinfo("成功", f"已保存到资讯表 [{tab_name}]", parent=win)
            except Exception as e:
                messagebox.showerror("保存失败", str(e), parent=win)
        def _copy_all_log():
            content = log.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_append(content)
                status_var.set("✅ 已复制全部到剪贴板")
        # --- 扩展数据：板块 + 资金流 + 基本面 ---
        def _enrich_data():
            """异步加载扩展数据（板块名、大单净额、基本面打分），填充 side + 日志"""
            if not _signal_results_cache:
                messagebox.showwarning("提示", "还没有检测结果", parent=win)
                return
            n = len(_signal_results_cache)
            status_var.set(f"正在加载扩展数据 · 共 {n} 只...")
            prog["value"] = 0
            win.update_idletasks()
            def _worker():
                # 1) 一次性拉 stock_basic（0.2s, 5551 只）
                try:
                    import tushare as _ts_en
                    _tk = open(os.path.expanduser("~/.tushare/token")).read().strip()
                    _pro = _ts_en.pro_api(_tk)
                    sb = _pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry,area")
                    # 构建 {code: industry} 映射
                    _ind_map = {}
                    for _, r in sb.iterrows():
                        short_code = r["ts_code"].split(".")[0]
                        _ind_map[short_code] = r["industry"] or ""
                except Exception as e:
                    _ind_map = {}
                    print(f"[扩展数据] stock_basic 失败: {e}")
                # 2) 腾讯批量拉大单净额（每批 20 只）
                def _batch_tencent(codes_list):
                    """codes_list: ['600519', '000001', ...] → {code: big_net_wan}"""
                    import requests as _rq
                    h = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com/"}
                    # 代码转腾讯格式
                    tq_codes = []
                    for c in codes_list:
                        if c.startswith(("6", "9")):
                            tq_codes.append(f"sh{c}")
                        else:
                            tq_codes.append(f"sz{c}")
                    tq_str = ",".join(tq_codes)
                    try:
                        r = _rq.get(f"https://qt.gtimg.cn/q={tq_str}", headers=h, timeout=15)
                        result = {}
                        for part in r.text.strip().split(";"):
                            if "=" not in part: continue
                            _, data = part.split("=", 1)
                            items = data.strip('"').split("~")
                            if len(items) > 48:
                                code = items[2]
                                try: big_net = float(items[47])
                                except: big_net = None
                                result[code] = big_net
                        return result
                    except Exception as e:
                        print(f"[扩展数据] 腾讯批量失败: {e}")
                        return {}
                all_codes = list({rec[3] for rec in _signal_results_cache})
                batch_size = 20
                big_net_map = {}
                for i in range(0, len(all_codes), batch_size):
                    batch = all_codes[i:i + batch_size]
                    big_net_map.update(_batch_tencent(batch))
                    time.sleep(0.15)  # 防限流
                # 3) 基本面打分（PE/PB/ROE 简单规则，tushare daily_basic）
                #    先拿最近有数据的交易日
                try:
                    import tushare as _ts2
                    _pro2 = _ts2.pro_api(_tk)
                    # 先试最近的交易日
                    _fund_map = {}
                    for d in ["20260829", "20260828", "20260827", "20260826", "20260825"]:
                        try:
                            db = _pro2.daily_basic(ts_code="", trade_date=d, fields="ts_code,pe,pb,roe,total_mv")
                            if len(db) > 100:
                                for _, r in db.iterrows():
                                    sc = r["ts_code"].split(".")[0]
                                    pe = r.get("pe"); pb = r.get("pb"); roe = r.get("roe")
                                    if pe is not None or pb is not None:
                                        _fund_map[sc] = {"pe": pe, "pb": pb, "roe": roe}
                                break
                        except Exception: continue
                except Exception as e:
                    _fund_map = {}
                    print(f"[扩展数据] daily_basic 失败: {e}")
                # 4) 回填到 meta + 构建 side 文本
                for rec in _signal_results_cache:
                    _tab, _slot, _nm, co, _line, _pct, meta = rec
                    meta["industry"] = _ind_map.get(co, "")
                    meta["big_net_wan"] = big_net_map.get(co)
                    meta["fund"] = _fund_map.get(co)
                    # 基本面打分（PE/PB/ROE 简单逻辑）
                    score_parts = []
                    fund = meta["fund"] or {}
                    pe = fund.get("pe"); pb = fund.get("pb"); roe = fund.get("roe")
                    if pe is not None and isinstance(pe, (int, float)) and pe > 0 and pe < 200:
                        if pe < 15: score_parts.append(f"PE{pe:.0f}低估")
                        elif pe < 30: score_parts.append(f"PE{pe:.0f}合理")
                        else: score_parts.append(f"PE{pe:.0f}偏高")
                    if pb is not None and isinstance(pb, (int, float)) and pb > 0 and pb < 50:
                        if pb < 1.5: score_parts.append(f"PB{pb:.1f}低估")
                        elif pb < 3: score_parts.append(f"PB{pb:.1f}合理")
                        else: score_parts.append(f"PB{pb:.1f}偏高")
                    if roe is not None and isinstance(roe, (int, float)) and roe > -50 and roe < 100:
                        if roe > 15: score_parts.append(f"ROE{roe:.1f}%优秀")
                        elif roe > 8: score_parts.append(f"ROE{roe:.1f}%良好")
                        elif roe < 0: score_parts.append(f"ROE{roe:.1f}%亏损")
                    meta["fund_score"] = " / ".join(score_parts) if score_parts else "暂无数据"
                # 5) 更新 UI（主线程）
                def _update_ui():
                    side.insert(tk.END, "\n" + "=" * 40 + "\n")
                    side.insert(tk.END, "📊 扩展数据（板块 / 资金 / 基本面）\n\n")
                    for rec in _signal_results_cache:
                        _tab, _slot, nm, co, _line, _pct, meta = rec
                        ind = meta.get("industry", "")
                        bn = meta.get("big_net_wan")
                        fs = meta.get("fund_score", "")
                        bn_str = f"{bn:+.0f}万" if bn is not None else "?"
                        side.insert(tk.END, f"[{nm}({co})]\n")
                        side.insert(tk.END, f"  板块: {ind or '?'}\n")
                        side.insert(tk.END, f"  大单净额: {bn_str}\n", ("flow_up" if (bn and bn > 0) else ("flow_dn" if (bn and bn < 0) else "")))
                        side.insert(tk.END, f"  基本面: {fs}\n\n")
                    side.tag_configure("flow_up", foreground="#C62828")
                    side.tag_configure("flow_dn", foreground="#2E7D32")
                    status_var.set(f"✅ 扩展数据已加载 · 共 {len(_signal_results_cache)} 只")
                self.root.after(0, _update_ui)
            threading.Thread(target=_worker, daemon=True).start()
        # --- 按钮 ---
        btn_frame = ttk.Frame(bot)
        btn_frame.pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="📋 复制全部", width=10, command=_copy_all_log).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="💾 保存TXT", width=10, command=_save_txt).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="📊 保存Excel", width=12, command=_save_excel).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="📰 存资讯表", width=12, command=_save_to_news).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_frame, text="📊 加载扩展数据（板块/资金/基本面）", width=28, command=_enrich_data).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bot, text="关闭窗口(检测在后台继续直至全部完成)", command=win.destroy).pack(side=tk.RIGHT)
        def append_and_progress(cur, total, text_line, gidx, idx, pct, side_text):
            try:
                if win.winfo_exists():
                    log.tag_configure('redstar', foreground='red')
                    log.tag_configure('redtri', foreground='red')
                    if ('★' in text_line) or ('▲' in text_line):
                        for ch in text_line:
                            if ch == '★':
                                log.insert(tk.END, ch, ('redstar',))
                            elif ch == '▲':
                                log.insert(tk.END, ch, ('redtri',))
                            else:
                                log.insert(tk.END, ch)
                        log.insert(tk.END, "\n")
                    else:
                        log.insert(tk.END, text_line + "\n")
                    log.see(tk.END)
                    if side_text:
                        side.insert(tk.END, side_text)
                        side.see(tk.END)
                    prog['maximum'] = max(1, total)
                    prog['value'] = cur
                    pct_var.set(f"已完成 {cur}/{total}  ·  {100.0 * cur / total:.1f}%")
                    status_var.set(f"已完成 {cur}/{total} · 组{gidx} 位{idx + 1}(刚写入日志)")
                    win.update_idletasks()
            except Exception:
                pass
            try:
                self._update_holding_label(idx, check_conditions=True, group_index=gidx, daily_change_pct=pct)
            except Exception:
                pass
            if hasattr(self, '_history_holdings_popup_windows'):
                for popup in self._history_holdings_popup_windows:
                    if popup.winfo_exists() and hasattr(popup, '_update_display'):
                        try:
                            popup._update_display()
                        except Exception:
                            pass
        def worker():
            total = len(tasks)
            t0 = time.monotonic()
            tallies = {
                "fish_body": 0,
                "fish_tail": 0,
                "red_star": 0,
                "ma1_tri": 0,
                "skipped_tail": 0,      # ✅ 跳过:鱼尾
                "skipped_noedge": 0,   # ✅ 跳过:凯利<=0
            }
            # ✅ 提前一次性拉基本面数据(不浪费并行时间,先花 ~0.5s 把 industry/fund/big_net 全部拿到)
            _pre_start = time.monotonic()
            _ind_map, _fund_map, _big_net_map = {}, {}, {}
            _fund_score_map = {}
            try:
                import tushare as _ts_pre
                _tk_pre = open(os.path.expanduser("~/.tushare/token")).read().strip()
                _pro_pre = _ts_pre.pro_api(_tk_pre)
                # stock_basic → {code: industry}
                sb = _pro_pre.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry,area")
                for _, r in sb.iterrows():
                    _ind_map[r["ts_code"].split(".")[0]] = r.get("industry") or ""
                # daily_basic → {code: {pe,pb,roe}}  (全市场一次性)
                for d in ["20260829", "20260828", "20260827", "20260826", "20260825"]:
                    try:
                        db = _pro_pre.daily_basic(ts_code="", trade_date=d, fields="ts_code,pe,pb,roe,total_mv")
                        if len(db) > 100:
                            for _, r in db.iterrows():
                                sc = r["ts_code"].split(".")[0]
                                _fund_map[sc] = {"pe": r.get("pe"), "pb": r.get("pb"), "roe": r.get("roe")}
                            break
                    except Exception:
                        continue
                # 基本面打分预计算
                for sc, fund in _fund_map.items():
                    pe = fund.get("pe"); pb = fund.get("pb"); roe = fund.get("roe")
                    parts = []
                    if pe is not None and isinstance(pe, (int, float)) and 0 < pe < 200:
                        if pe < 15: parts.append(f"PE{pe:.0f}低")
                        elif pe < 30: parts.append(f"PE{pe:.0f}合")
                        else: parts.append(f"PE{pe:.0f}高")
                    if pb is not None and isinstance(pb, (int, float)) and 0 < pb < 50:
                        if pb < 1.5: parts.append(f"PB{pb:.1f}低")
                        elif pb < 3: parts.append(f"PB{pb:.1f}合")
                        else: parts.append(f"PB{pb:.1f}高")
                    if roe is not None and isinstance(roe, (int, float)) and -50 < roe < 100:
                        if roe > 15: parts.append(f"ROE{roe:.0f}%优")
                        elif roe > 8: parts.append(f"ROE{roe:.0f}%良")
                        elif roe < 0: parts.append(f"ROE{roe:.0f}%亏")
                    _fund_score_map[sc] = "·".join(parts) if parts else ""
            except Exception as e:
                print(f"[信号-预加载] 基本面失败: {e}")
            # 腾讯批量拉大单净额
            try:
                import requests as _rq_pre
                _h_pre = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.qq.com/"}
                _all_codes_pre = list(dict.fromkeys(
                    (self._get_holding_group_data(g)[0][i][1] if self._get_holding_group_data(g)[0][i] else "")
                    for g, i in tasks
                ))
                _all_codes_pre = [c for c in _all_codes_pre if c]
                for _bi in range(0, len(_all_codes_pre), 20):
                    batch = _all_codes_pre[_bi:_bi + 20]
                    tq = ",".join(f"sh{c}" if c.startswith(("6", "9")) else f"sz{c}" for c in batch)
                    try:
                        _rr = _rq_pre.get(f"https://qt.gtimg.cn/q={tq}", headers=_h_pre, timeout=15)
                        for part in _rr.text.strip().split(";"):
                            if "=" not in part: continue
                            _, _dd = part.split("=", 1)
                            _items = _dd.strip('"').split("~")
                            if len(_items) > 48:
                                _cc = _items[2]
                                try: _big_net_map[_cc] = float(_items[47])
                                except: pass
                    except Exception:
                        pass
                    time.sleep(0.12)
            except Exception as e:
                print(f"[信号-预加载] 大单净额失败: {e}")
            print(f"[信号-预加载] 基本面 + 大单净额耗时 {time.monotonic()-_pre_start:.1f}s "
                  f"(industry:{len(_ind_map)}, fund:{len(_fund_map)}, big_net:{len(_big_net_map)})")
            status_var.set(
                f"⏳ 预加载完成·板块{len(_ind_map)} 基本面{len(_fund_map)} 大单净额{len(_big_net_map)} → 开始并行检测..."
            )
            def ui_pulse_start(c, t, g, i, nm, co):
                """主线程:在后台开始处理第 c 只之前就刷新进度条与说明(避免长时间无响应)。"""
                try:
                    if not win.winfo_exists():
                        return
                    prog["maximum"] = max(1, t)
                    prog["value"] = max(0, c - 1)
                    done = max(0, c - 1)
                    if t > 0:
                        pct_var.set(
                            f"进行中 {c}/{t}  ·  条形进度约 {100.0 * done / t:.1f}%(当前这只完成后会前进)"
                        )
                    elapsed = time.monotonic() - t0
                    if c <= 1:
                        eta_var.set(
                            f"已开始第 1 只(均线鱼身鱼尾/五星/1日收盘上穿等,界面未卡死)· 已等待 {elapsed:.0f}s"
                        )
                    elif done > 0:
                        per = elapsed / done
                        rem = per * (t - done)
                        eta_var.set(
                            f"已用 {elapsed / 60:.1f} 分 · 粗估剩余 {max(0.0, rem) / 60:.1f} 分"
                            f"(按最近均速 {per:.1f}s/只,仅供参考)"
                        )
                    else:
                        eta_var.set(f"已用 {elapsed:.0f}s ...")
                    status_var.set(
                        f"正在检测 {c}/{t} · {nm} ({co}) · 组{g} 位{i + 1}"
                    )
                    win.update_idletasks()
                except Exception:
                    pass
            import concurrent.futures as _cf_cap
            _MAX_WORKERS = 12  # 并行 12 线程
            completed_count = [0]
            def _process_one(cur, gidx, idx):
                """单只检测（由线程池调度，纯计算 + 网络请求，不碰 Tk）"""
                try:
                    hs, _, _, _ = self._get_holding_group_data(gidx)
                    _hold = hs[idx] if idx < len(hs) else None
                    _nm, _co = _hold if _hold else ("?", "")
                except Exception:
                    _nm, _co = ("?", "")
                # 实时推送"正在检测 XXX"（子线程 → root.after，root.after 线程安全）
                self.root.after(
                    0,
                    lambda c=cur, t=total, g=gidx, i=idx, n=_nm, co=_co: ui_pulse_start(c, t, g, i, n, co),
                )
                try:
                    line, pct, meta = self._detect_and_store_one_holding_slot(gidx, idx)
                except Exception as e:
                    line, pct, meta = f"[{self._signal_tab_label_for_group(gidx)}] #{idx+1} ? ({_co}) ✗ {e}", None, None
                # ========== ✅ 跳过逻辑 ==========
                # 只有同时满足以下 3 个条件才跳过:
                #   1) 鱼尾(中期弱势)  2) 无★(无短期超跌反弹)  3) 无▲(无短期趋势反转)  4) 凯利<=0(无正向期望值)
                # 只要有任何一个正面信号就保留 ★ / ▲ / kelly>0
                _skip_reason = ""
                if meta:
                    _no_positive = (
                        meta.get("fish_tail")
                        and not meta.get("red_star")
                        and not meta.get("ma1_tri")
                        and meta.get("kelly_ratio", 0) <= 0
                    )
                    if _no_positive:
                        _skip_reason = "鱼尾+无★▲+凯利<=0"
                        tallies["skipped_tail"] += 1
                if _skip_reason:
                    # 跳过的股票仍然递增 completed_count，仍然更新进度条，只是不输出 log、不入 cache
                    completed_count[0] += 1
                    self.root.after(0, lambda c=completed_count[0], t=total, n=_nm, r=_skip_reason: (
                        pct_var.set(f"已完成 {c}/{t}  ·  跳过{n}({r})"),
                        status_var.set(f"跳过 {n} — {r}"),
                        prog.configure(value=c),
                        win.update_idletasks(),
                    ))
                    return
                # ========== 累加统计 ==========
                if line and meta:
                    if meta.get("fish_body"): tallies["fish_body"] += 1
                    if meta.get("fish_tail"): tallies["fish_tail"] += 1
                    if meta.get("red_star"): tallies["red_star"] += 1
                    if meta.get("ma1_tri"): tallies["ma1_tri"] += 1
                # ========== ✅ 拼基本面信息到 log 行 ==========
                _ind = _ind_map.get(_co, "")
                _fs = _fund_score_map.get(_co, "")
                _bn = _big_net_map.get(_co)
                _bn_str = f"{_bn:+.0f}万" if _bn is not None else "?"
                _pct_str = f"{pct:+.2f}%" if pct is not None else ""
                _extra_parts = []
                if _ind: _extra_parts.append(f"📦{_ind}")
                if _fs: _extra_parts.append(f"📊{_fs}")
                _extra_parts.append(f"💸{_bn_str}")
                if _pct_str: _extra_parts.append(f"📈{_pct_str}")
                _extra = " | " + "  ".join(_extra_parts) if _extra_parts else ""
                if line:
                    line = line + _extra
                # 缓存（list.append 线程安全）
                sd = meta.get("sidebar") or ""
                _signal_results_cache.append((
                    self._signal_tab_label_for_group(gidx), idx, _nm, _co,
                    line, pct, meta
                ))
                # 推送 UI 更新
                completed_count[0] += 1
                self.root.after(
                    0,
                    lambda c=completed_count[0], t=total, ln=line or "", g=gidx, i=idx, p=pct, s=sd: append_and_progress(c, t, ln, g, i, p, s),
                )
            # ===== 并行执行 =====
            _parallel_start = time.monotonic()
            with _cf_cap.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
                futures = {}
                for cur, (gidx, idx) in enumerate(tasks, start=1):
                    fut = executor.submit(_process_one, cur, gidx, idx)
                    futures[fut] = (cur, gidx, idx)
                # 等待全部完成
                for fut in _cf_cap.as_completed(futures):
                    try: fut.result()  # 捕获可能的异常
                    except Exception as e:
                        cur_err, _g_err, _i_err = futures[fut]
                        print(f"[并行检测] 任务 #{cur_err} 异常: {e}")
            print(f"[信号检测] {len(tasks)} 只 · {_MAX_WORKERS}线程 · 并行耗时 {time.monotonic()-_parallel_start:.1f}s")
            def finish():
                try:
                    if win.winfo_exists():
                        elapsed_all = time.monotonic() - t0
                        status_var.set(f"全部完成 · 共 {total} 只 · 用时 {elapsed_all / 60:.1f} 分钟")
                        prog['maximum'] = max(1, total)
                        prog['value'] = total
                        pct_var.set(f"100%  ·  {total}/{total}")
                        eta_var.set(f"总用时 {elapsed_all / 60:.1f} 分(约 {elapsed_all / max(1, total):.1f} 秒/只)")
                        try:
                            log.tag_configure("summary", font=("Consolas", 12, "bold"))
                        except Exception:
                            pass
                        def pct_ok(x):
                            return (100.0 * x / total) if total else 0.0
                        log.insert(tk.END, "\n══════════ 汇总 ══════════\n", "summary")
                        _keep = total - tallies["skipped_tail"]
                        log.insert(
                            tk.END,
                            f"检测样本:{total} 只 · 保留:{_keep} 只 · 跳过:{tallies['skipped_tail']}只\n"
                            f"  (跳过=鱼尾 + 无★ + 无▲ + 凯利<=0, 只要有任何一个正面信号都保留)\n"
                            f"鱼身:{tallies['fish_body']}({pct_ok(tallies['fish_body']):.1f}%)  "
                            f"鱼尾:{tallies['fish_tail']}  "
                            f"红星★:{tallies['red_star']}({pct_ok(tallies['red_star']):.1f}%)  "
                            f"三角▲:{tallies['ma1_tri']}({pct_ok(tallies['ma1_tri']):.1f}%)\n"
                            f"💡 双击任意行可打开该股票日K图\n",
                            "summary",
                        )
                        log.see(tk.END)
                except Exception:
                    pass
            self.root.after(0, finish)
            def popups_final():
                if hasattr(self, '_history_holdings_popup_windows'):
                    for popup in self._history_holdings_popup_windows:
                        if popup.winfo_exists() and hasattr(popup, '_update_display'):
                            try:
                                popup._update_display()
                            except Exception:
                                pass
            self.root.after(500, popups_final)
        log.insert(tk.END, f"开始全标签页「信号」检测,共 {len(tasks)} 只;每项约 1 秒。\n")
        log.insert(tk.END,
            "═══════════════ 信号图例 ═══════════════\n",
        )
        log.insert(tk.END,
            "🐟 鱼身: 股价站上10日线 + 10日线、20日线都向上 → 主升持有期\n"
            "💀 鱼尾: 跌破10日线 或 20日线向下 → 弱势离场信号(自动跳过)\n"
            "⭐ 红星★: 现价在近5日低位≤3%附近 + 站上1日线(≥昨收) → 短期超跌反弹\n"
            "🔺 三角▲: 昨收未站上1日线(昨收<前收) + 今收站上1日线(今收≥昨收) → 短期趋势反转\n"
            "🎯 凯利: f*=(bp-q)/b 仓位比例,≤0 表示无正向期望值(自动跳过)\n"
            "📦板块  📊PE/PB/ROE基本面  💸大单净额(万)  📈当日涨跌%\n"
            "💡 双击任意行可打开该股票日K图\n",
        )
        log.insert(tk.END,
            "═══════════════════════════════════════\n\n",
        )
        threading.Thread(target=worker, daemon=True).start()


    def _get_all_holding_stocks(self):
        """获取所有持仓股列表(包括所有持仓组1-14)
        按优先级顺序:15Min -> 持仓 -> 龙头股 -> Main -> 持仓历史股 -> 同花顺 -> 持仓1-8
        Returns:
            list: [(stock_name, stock_code, group_index, position_index), ...]
        """
        all_holdings = []
        # 按优先级顺序添加:3(15Min) -> 1(持仓) -> 2(龙头股) -> 4(Main) -> 5(持仓历史股) -> 6(同花顺) -> 7-14(持仓1-8)
        priority_order = [3, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
        for group_idx in priority_order:
            if group_idx == 1:
                # 持仓1(80个)
                for i, holding in enumerate(self.holding_stocks):
                    if holding:
                        stock_name, stock_code = holding
                        all_holdings.append((stock_name, stock_code, 1, i))
            else:
                # 持仓2-14(各80个)
                holding_stocks = getattr(self, f'holding_stocks_{group_idx}', [None] * 80)
                for i, holding in enumerate(holding_stocks):
                    if holding:
                        stock_name, stock_code = holding
                        all_holdings.append((stock_name, stock_code, group_idx, i))
        return all_holdings


    def _get_main_holding_stocks(self):
        """获取Main标签页(group_index=4)的持仓股列表
        Returns:
            list: [(stock_name, stock_code, position_index), ...]
        """
        main_holdings = []
        # 获取Main标签页的持仓股(group_index=4)
        holding_stocks_4 = getattr(self, 'holding_stocks_4', [None] * 80)
        for i, holding in enumerate(holding_stocks_4):
            if holding:
                stock_name, stock_code = holding
                main_holdings.append((stock_name, stock_code, i))
        return main_holdings


    def _get_monitor_holding_stocks(self):
        """获取日K线监测对象股:龙头股(2)、Main(4)、持仓历史股(5)、同花顺(6)、标签1-8(7-14),不去重,带组名。
        Returns:
            list: [(stock_name, stock_code, group_name, position_index), ...]
        """
        monitor_group_names = {
            2: "龙头股",
            4: "Main",
            5: "持仓历史股",
            6: "同花顺",
        }
        holding_tab_names = getattr(self.ai_config_manager, 'config', {}).get("holding_tab_names", {}) or {}
        result = []
        for group_index in [2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
            group_name = monitor_group_names.get(group_index) or holding_tab_names.get(str(group_index), f"标签{group_index-6}")
            holding_stocks = getattr(self, f'holding_stocks_{group_index}', [None] * 80)
            for i, holding in enumerate(holding_stocks):
                if not holding:
                    continue
                stock_name, stock_code = holding
                if (stock_name or '').strip() or (stock_code or '').strip():
                    result.append((str(stock_name or '').strip(), str(stock_code or '').strip(), group_name, i))
        return result


    def _get_self_holding_monitor_stocks(self):
        """获取自持股监测对象股:龙头股(2)+Main(4)+同花顺(6)+标签1-8(7-14),按代码去重。
        Returns:
            list: [(stock_name, stock_code, position_index), ...]  position_index 为顺序号
        """
        seen_codes = set()
        result = []
        idx = 0
        group_indices = [2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14]  # 龙头股、Main、同花顺、标签1-8
        for group_index in group_indices:
            holding_stocks = getattr(self, f'holding_stocks_{group_index}', [None] * 80)
            for holding in holding_stocks:
                if not holding:
                    continue
                stock_name, stock_code = holding
                code = (stock_code or '').strip()
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)
                result.append((stock_name or '', stock_code, idx))
                idx += 1
        return result


    def _update_holding_price_history(self, stock_code, price, high=None, low=None):
        """更新持仓股价格历史记录
        Args:
            stock_code: 股票代码
            price: 当前价格
            high: 最高价(可选)
            low: 最低价(可选)
        """
        import time
        current_time = time.time()
        if stock_code not in self.holding_price_history:
            self.holding_price_history[stock_code] = []
        # 添加当前价格记录
        self.holding_price_history[stock_code].append({
            'timestamp': current_time,
            'price': price,
            'high': high if high else price,
            'low': low if low else price
        })
        # 只保留1小时内的数据(3600秒)
        one_hour_ago = current_time - 3600
        self.holding_price_history[stock_code] = [
            record for record in self.holding_price_history[stock_code]
            if record['timestamp'] >= one_hour_ago
        ]


    def _calculate_holding_amplitude(self, stock_code):
        """计算持仓股1小时内的振幅
        Args:
            stock_code: 股票代码
        Returns:
            float: 振幅百分比,如果数据不足返回None
        """
        if stock_code not in self.holding_price_history:
            return None
        history = self.holding_price_history[stock_code]
        if len(history) < 2:
            return None
        # 计算1小时内的最高价和最低价
        prices = [record['price'] for record in history]
        highs = [record['high'] for record in history]
        lows = [record['low'] for record in history]
        max_price = max(max(highs), max(prices))
        min_price = min(min(lows), min(prices))
        if min_price <= 0:
            return None
        # 计算振幅 = (最高价 - 最低价) / 最低价 * 100
        amplitude = (max_price - min_price) / min_price * 100
        return amplitude


    def _show_should_hold_dialog(self):
        """💼 是否持有:持股列表选择 + 手动输入 → AI 按机构票/游资票/周期股框架分析 → 输出持有/卖出建议及逻辑"""
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
        win = self._safe_toplevel(self.root)
        win.title("💼 是否持有 · 智能分析器")
        win.geometry("1400x880")
        win.transient(self.root)
        # ============ Skill 系统提示词(整合 rocket-scan 完整方法论) ============
        SHOULD_HOLD_SYSTEM_PROMPT = """你是一位拥有30年A股实战经验的资深基金经理，专精持仓决策。你已经通过真实交易案例（迈为股份、商洛电子、诺德股份、白银有色）归纳出了完整的「三维共振+四类定性」框架：
═══════════════════════════════════════
【核心认知】买入即大涨/持有不动的本质
═══════════════════════════════════════
> 在"价值+趋势+情绪"三重共振的临界点入场，享受资金合力推动的戴维斯双击/主升浪。
三维共振模型：
  维度1：基本面（Why）→ 价值重估逻辑（业绩/政策/事件驱动）
  维度2：技术面（When）→ 起爆点信号（缩量整理结束、突破关键位置）
  维度3：情绪面（Who）→ 资金性质判断（机构主导 or 游资接力）
═══════════════════════════════════════
【四类股票定性】（先判断类型，再套用对应框架！）
═══════════════════════════════════════
🔵 【机构票】—— 业绩驱动，慢牛趋势
┌──────────┬──────────────────────────────────────────┐
│ 识别特征  │ 前十大股东有公募/保险/北向；ROE连续3年>12%；  │
│          │ 研报密集覆盖；净利润同比增速持续>30%；       │
│          │ 均线多头排列；趋势流畅，回调有序不跌停       │
├──────────┼──────────────────────────────────────────┤
│ 持有原则  │ 业绩驱动趋势，趋势不破不卖                  │
│          │ 止损放至-15%，20日线有效跌破才卖              │
│          │ 机构不止盈，长期持有享受泡沫                 │
│          │ 缩量回调是买点，高位放量滞涨是卖点            │
├──────────┼──────────────────────────────────────────┤
│ 教训案例  │ 迈为股份：90元-7%止损踏空400%！              │
│          │ 本质：把机构票当短线炒了，止损太紧被洗出去    │
│          │ 正确：HJT赛道景气+业绩未破→应忍受-15%波动    │
└──────────┴──────────────────────────────────────────┘
🟠 【游资票】—— 情绪驱动，连板博弈
┌──────────┬──────────────────────────────────────────┐
│ 识别特征  │ 连续涨停/连板；日换手>15%；                 │
│          │ 龙虎榜有知名游资（赵老哥/章盟主等）；         │
│          │ 无业绩支撑（PE极高或亏损）；涨跌凌厉         │
├──────────┼──────────────────────────────────────────┤
│ 持有原则  │ 情绪决定高度，连板不猜顶                    │
│          │ 情绪高潮前持有，高潮时全身而退                │
│          │ 止损用5日线移动止盈                          │
│          │ 高位炸板是离场信号，跌停是终极信号            │
├──────────┼──────────────────────────────────────────┤
│ 教训案例  │ 商洛电子：21元卖踏空162%！                  │
│          │ 本质：游资票情绪加速期，涨30%先落袋为安       │
│          │ 正确：设定目标价（至少1倍空间），情绪高潮才卖  │
└──────────┴──────────────────────────────────────────┘
🟡 【周期/资源股】—— 商品驱动，低位反转
┌──────────┬──────────────────────────────────────────┐
│ 识别特征  │ 有色/煤炭/化工/新能源材料；                 │
│          │ 业绩随商品价格剧烈波动；                     │
│          │ 长期低位横盘后突然放量启动                    │
├──────────┼──────────────────────────────────────────┤
│ 持有原则  │ 商品牛市不要猜顶；逻辑未破坏就拿着           │
│          │ 业绩从亏转盈/大幅增长时，坚定持有             │
│          │ 止损可以宽，因为周期反转往往是数倍行情        │
├──────────┼──────────────────────────────────────────┤
│ 教训案例  │ 诺德股份：3-4元没买→涨到11元(+200%)         │
│          │ 白银有色：3-4元卖→涨到15元(+300%)           │
│          │ 本质：周期股底部反转时，逻辑没破坏就不要卖    │
└──────────┴──────────────────────────────────────────┘
⚪ 【普通票】—— 无明显定性属性
  持有原则：20日线以上持有，跌破减仓；结合大盘红绿灯操作
═══════════════════════════════════════
【止损纪律对照表】（铁律！严格按类型执行）
═══════════════════════════════════════
┌──────────┬────────────┬──────────────┬──────────┐
│ 股票类型  │ 买入即大跌  │ 趋势破位止损  │ 最大容忍 │
├──────────┼────────────┼──────────────┼──────────┤
│ 机构票    │ -7%关注    │ 跌破20日线    │ -15%     │
│ 游资票    │ -10%止损   │ 跌破5日线     │ -15%     │
│ 强势追板  │ -5%止损    │ 跌破分时均价线│ -8%      │
│ 周期/资源 │ 宽止损     │ 逻辑破坏才卖  │ -20%     │
└──────────┴────────────┴──────────────┴──────────┘
═══════════════════════════════════════
【卖出决策4种情况】（满足任意1条可考虑卖）
═══════════════════════════════════════
1. 🔴 **逻辑破坏**：买入理由消失（业绩爆雷/赛道逆转/题材退潮），立即卖出不拖
2. 🔴 **技术破位**：跌破关键均线（机构20日线/游资5日线），及时止损
3. 🟡 **情绪高潮**：连续涨停加速末期/换手率>25%/同题材大面积炸板，分批止盈
4. 🟡 **目标到达**：达到预设目标价（机构30-50%/游资1倍/周期商品见顶），兑现利润
═══════════════════════════════════════
【输出格式要求】（每只股票严格按以下 7 个维度 + 1 个决策输出）
═══════════════════════════════════════
## 💼 [股票名称](代码) 是否持有
### 0️⃣ 股票定性（先做这步！）
- **类型**: 机构票(业绩驱动) / 游资票(情绪连板) / 周期资源 / 普通票
- **判断依据**: (3条以内)
### 1️⃣ 是否可以做T？
- **结论**: ✅可做T / ⚠️条件做T / ❌ 不宜做T
- **建议操作**: 买T区间 / 卖T区间 / 底仓保持
- **依据**: (均线位置 / 量能 / 板块节奏)
### 2️⃣ 是否应该持仓？
- **结论**: 🟢持有 / 🔴减仓 / 🟡观望
- **止损位**: xx 元（按股票类型对照止损纪律表）
- **止盈信号**: (如"5日线跌破"/"商品期货见顶"/"高位放量滞涨")
- **依据**: (趋势 / 成本安全垫 / 大盘S阶段)
### 3️⃣ 历史胜率评估
- **你的历史同类策略胜率**: XX%（如有）
- **当前持有时点的胜率概率**: XX%
- **胜率判断**: (样本够不够？类似形态最近有没有赚钱？)
### 4️⃣ 基本面 + 技术面
**基本面**: PE / PB / ROE / 净利润增速 / 行业地位 / 业绩逻辑
**技术面**:
- **关键支撑位**(近3个): xx / xx / xx
- **关键阻力位**(近3个): xx / xx / xx
- **当前价位位置**: (区间底部 / 中间 / 顶部)
### 5️⃣ 资金面 + 情绪面
- 主力资金近3日流向
- 北向/机构持仓变化
- 情绪指标(换手率 / 涨停数 / 炸板率)
### 6️⃣ 是否属于当前主线/主流板块？
- **结论**: ✅ 主线 / ⚠️ 次主线 / ❌ 边缘
- **主线逻辑**:
- **板块内排名**:
- **持续度判断**: (还能持续多久？)
### 🎯 综合决策（一句话）
> (买/卖/T/持 的核心理由 —— 必须说清楚为什么！)
---
最后给出**优先级排序**（最建议减仓 → 最建议持有）。
⚠️ 如果某些数据你不知道（如 PE/ROE/真实资金流向），写"⚠️ 此处为 AI 合理推测，建议核实"。"""
        def _build_should_hold_prompt(stocks_info, extra_context=""):
            """构建 AI prompt (含 tushare 实时数据)"""
            stock_blocks = []
            for s in stocks_info:
                live = s.get("live", {})
                ts_code = s.get("ts_code", "")
                # 把 live 数据拼成结构化文本
                live_lines = []
                if live:
                    live_lines.append("📡 **tushare 实时数据**:")
                    live_lines.append(f"  - 数据日期: {live.get('latest_date', 'N/A')} (ts_code={ts_code})")
                    if "latest_price" in live:
                        live_lines.append(f"  - 📈 最新价: {live['latest_price']} 元  涨跌: {live.get('change_pct', '?')}%")
                    if "ma5" in live:
                        live_lines.append(f"  - 📊 均线: MA5={live['ma5']} / MA10={live.get('ma10','?')} / MA20={live.get('ma20','?')} / MA60={live.get('ma60','?')}")
                    if "high_20d" in live:
                        live_lines.append(f"  - 🔺 20日高/低: {live['high_20d']} / {live['low_20d']}  量比: {live.get('vol_ratio', '?')}")
                    if "pe_ttm" in live:
                        live_lines.append(f"  - 💹 估值: PE_TTM={live['pe_ttm']}  PB={live.get('pb','?')}  总市值={live.get('total_mv','?')}")
                    if "turnover" in live:
                        live_lines.append(f"  - 🔄 换手率: {live['turnover']}%")
                    if "main_net_latest" in live:
                        live_lines.append(f"  - 💰 主力净额: 今日 {live['main_net_latest']}亿  近3日 {live.get('main_net_3d','?')}亿")
                    if "north_net_latest" in live:
                        live_lines.append(f"  - 🌐 北向净额: 今日 {live['north_net_latest']}万  近3日 {live.get('north_net_3d','?')}万")
                    if live.get("_error"):
                        live_lines.append(f"  - ⚠️ 部分数据拉取失败: {live['_error']}")
                block = f"""
### 股票: {s.get('name','?')}({s.get('code','?')})
- 用户持有成本: {s.get('cost','未知')} 元
- 用户盈亏: {s.get('pnl_pct','未知')}%
- 用户买入理由/逻辑: {s.get('buy_reason','未提供')}
- 用户历史教训(如有): {s.get('lesson','未提供')}
{chr(10).join(live_lines) if live_lines else '- ⚠️ 实时数据未拉取, AI 可能使用过时训练数据'}
"""
                stock_blocks.append(block)
            prompt = f"""请对以下持仓股票逐一进行"是否持有"分析：
{''.join(stock_blocks)}
{f'额外背景信息：{extra_context}' if extra_context else ''}
---
请严格按以下 6 维度 + 综合决策 输出（与 system prompt 格式完全一致）：
## 💼 [股票名称](代码) 是否持有
### 0️⃣ 股票定性
- **类型**: 机构票 / 游资票 / 周期资源 / 普通票
- **判断依据**: (3条以内)
### 1️⃣ 是否可以做T？
- **结论**: ✅/⚠️/❌ + 买T卖T区间 + 均线量能依据
### 2️⃣ 是否应该持仓？
- **结论**: 🟢持有 / 🔴减仓 / 🟡观望
- **止损位**: xx 元
- **止盈信号**: (破5日线/20日线/商品见顶/高位滞涨)
- **依据**: (趋势/成本安全垫/大盘S阶段)
### 3️⃣ 历史胜率评估
- 你的历史同类策略胜率 / 当前持有时点胜率概率
### 4️⃣ 基本面 + 技术面
**基本面**: PE / PB / ROE / 净利润增速 / 行业地位
**技术面**: 支撑位 / 阻力位(近3个) / 当前位置
### 5️⃣ 资金面 + 情绪面
- 主力流向 / 北向持仓 / 换手率 / 炸板率
### 6️⃣ 主线/主流板块归属
- ✅主线 / ⚠️次主线 / ❌边缘 + 持续度判断
### 🎯 综合决策（一句话）
> 核心理由（必须说清楚为什么！）
---
最后给出优先级排序（最建议减仓 → 最建议持有）。
"""
            return prompt
        # ============ 📡 tushare 实时数据注入器 ============
        def _enrich_with_live_data(stocks_info, progress_cb=None):
            """对每只股票拉取 tushare 最新数据, 合并到 stocks_info"""
            import tushare as _ts
            _pro = _ts.pro_api()
            today = datetime.now().strftime("%Y%m%d")
            # 交易日回退
            try:
                _cal = _pro.trade_cal(exchange="SSE", start_date="20260101", end_date=today, is_open="1")
                if len(_cal):
                    _latest_td = _cal["cal_date"].max()
                else:
                    _latest_td = today
            except Exception:
                _latest_td = today
            enriched = []
            for s in stocks_info:
                code = s.get("code", "")
                # 把用户输入的代码规范化为 tushare ts_code
                ts_code = code
                if code and "." not in code:
                    if code.startswith(("6", "5")):
                        ts_code = f"{code}.SH"
                    elif code.startswith(("0", "3")):
                        ts_code = f"{code}.SZ"
                    elif code.startswith("8"):
                        ts_code = f"{code}.BJ"
                live = {}
                try:
                    # 1. 日线行情 (近60日)
                    df_k = _pro.daily(ts_code=ts_code, start_date="20260101", end_date=_latest_td)
                    if df_k is not None and len(df_k) > 0:
                        df_k = df_k.sort_values("trade_date")
                        last = df_k.iloc[-1]
                        live["latest_price"] = round(float(last["close"]), 2)
                        live["latest_date"] = str(last["trade_date"])
                        live["change_pct"] = round(float(last["pct_chg"]), 2)
                        # 均线
                        closes = df_k["close"].astype(float).tolist()
                        if len(closes) >= 5:
                            live["ma5"] = round(sum(closes[-5:]) / 5, 2)
                        if len(closes) >= 10:
                            live["ma10"] = round(sum(closes[-10:]) / 10, 2)
                        if len(closes) >= 20:
                            live["ma20"] = round(sum(closes[-20:]) / 20, 2)
                        if len(closes) >= 60:
                            live["ma60"] = round(sum(closes[-60:]) / 60, 2)
                        # 近20日高低点 → 支撑/阻力
                        recent_20 = closes[-20:] if len(closes) >= 20 else closes
                        live["high_20d"] = round(max(recent_20), 2)
                        live["low_20d"] = round(min(recent_20), 2)
                        live["vol_ratio"] = round(float(last["vol"]) / (sum(df_k["vol"].astype(float).tolist()[-20:]) / 20), 2) if len(df_k) >= 20 else 1.0
                    # 2. 基本面 (daily_basic)
                    df_b = _pro.daily_basic(ts_code=ts_code, trade_date=_latest_td,
                                             fields="ts_code,trade_date,pe_ttm,pb,total_mv,circ_mv,turnover_rate,volume_ratio")
                    if df_b is not None and len(df_b) > 0:
                        b = df_b.iloc[0]
                        live["pe_ttm"] = round(float(b["pe_ttm"]), 2) if b["pe_ttm"] and str(b["pe_ttm"]) not in ("nan", "None", "") else "N/A"
                        live["pb"] = round(float(b["pb"]), 2) if b["pb"] and str(b["pb"]) not in ("nan", "None", "") else "N/A"
                        live["total_mv"] = f"{float(b['total_mv'])/10000:.1f}亿" if b["total_mv"] else "N/A"
                        live["turnover"] = round(float(b["turnover_rate"]), 2) if b["turnover_rate"] else "N/A"
                        live["vol_ratio_basic"] = round(float(b["volume_ratio"]), 2) if b["volume_ratio"] else "N/A"
                    # 3. 资金流向 (moneyflow, 近3日)
                    df_m = _pro.moneyflow(ts_code=ts_code, start_date="20260825", end_date=_latest_td)
                    if df_m is not None and len(df_m) > 0:
                        df_m = df_m.sort_values("trade_date")
                        # 主力净额 = buy_sm_amount - sell_sm_amount (这里直接用 net_mf_amount 或算)
                        try:
                            # tushare moneyflow 主力 = 大单+超大单净额
                            df_m["main_net"] = (
                                df_m["buy_elg_amount"].astype(float) + df_m["buy_lg_amount"].astype(float)
                                - df_m["sell_elg_amount"].astype(float) - df_m["sell_lg_amount"].astype(float)
                            )
                            last_3 = df_m.tail(3)
                            live["main_net_3d"] = round(float(last_3["main_net"].sum()) / 10000, 2)  # 转亿
                            live["main_net_latest"] = round(float(df_m.iloc[-1]["main_net"]) / 10000, 2)
                        except Exception:
                            pass
                    # 4. 北向持仓 (hsgt_top10, 如果是沪深股)
                    if ts_code.endswith((".SH", ".SZ")):
                        try:
                            df_h = _pro.hsgt_top10(ts_code=ts_code, start_date="20260825", end_date=_latest_td)
                            if df_h is not None and len(df_h) > 0:
                                df_h = df_h.sort_values("trade_date")
                                live["north_net_latest"] = round(float(df_h.iloc[-1]["net_amount"]), 2)
                                live["north_net_3d"] = round(float(df_h.tail(3)["net_amount"].sum()), 2)
                        except Exception:
                            pass
                except Exception as e:
                    live["_error"] = str(e)
                merged = {**s, "live": live, "ts_code": ts_code}
                enriched.append(merged)
                if progress_cb:
                    progress_cb(len(enriched), len(stocks_info))
            return enriched
        # ============ UI ============
        # 顶部 Banner
        banner = tk.Frame(win, bg="#1565C0", height=70)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        tk.Label(banner, text="💼 是否持有 · 智能分析器", font=("Microsoft YaHei", 16, "bold"),
                 bg="#1565C0", fg="#FFFFFF").pack(anchor="w", padx=14, pady=(10, 0))
        tk.Label(banner, text="机构票·游资票·周期资源股 三分类框架 → 每只股票输出持有/卖出/观望建议及核心逻辑",
                 font=("Microsoft YaHei", 10), bg="#1565C0", fg="#BBDEFB").pack(anchor="w", padx=14)
        # 主体:左(选择区) + 右(结果)
        body = ttk.PanedWindow(win, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # --- 左侧:股票选择区 ---
        left_frame = ttk.Frame(body)
        body.add(left_frame, weight=2)
        # 手动输入
        input_frame = ttk.LabelFrame(left_frame, text="📝 手动添加", padding=6)
        input_frame.pack(fill=tk.X, padx=3, pady=(0, 4))
        row_input = ttk.Frame(input_frame)
        row_input.pack(fill=tk.X)
        ttk.Label(row_input, text="代码/名称:", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
        code_var = tk.StringVar()
        ttk.Entry(row_input, textvariable=code_var, width=14).pack(side=tk.LEFT, padx=4)
        ttk.Label(row_input, text="成本:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        cost_var = tk.StringVar()
        ttk.Entry(row_input, textvariable=cost_var, width=7).pack(side=tk.LEFT, padx=4)
        ttk.Label(row_input, text="盈亏%:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        pnl_var = tk.StringVar()
        ttk.Entry(row_input, textvariable=pnl_var, width=7).pack(side=tk.LEFT, padx=4)
        add_btn = ttk.Button(row_input, text="➕ 添加")
        add_btn.pack(side=tk.LEFT, padx=8)
        # 常用快捷
        ttk.Label(input_frame, text="快捷:").pack(anchor="w", pady=(4, 0))
        quick_row = ttk.Frame(input_frame)
        quick_row.pack(fill=tk.X, pady=(2, 0))
        for qc, qn in [("600519", "茅台"), ("002594", "比亚迪"), ("300750", "宁德"), ("601318", "平安"), ("601899", "紫金"), ("000858", "五粮")]:
            ttk.Button(quick_row, text=qn, width=5,
                       command=lambda c=qc: (code_var.set(c), cost_var.set(""), pnl_var.set(""))).pack(side=tk.LEFT, padx=2)
        # 持股列表(多选)
        list_frame = ttk.LabelFrame(left_frame, text="📋 持股列表(点击选中/取消,也可全选)", padding=4)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 4))
        # 搜索栏
        search_row = ttk.Frame(list_frame)
        search_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(search_row, text="筛选:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        filter_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=filter_var, width=10).pack(side=tk.LEFT, padx=3)
        # 持股 Listbox (多选)
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        holding_lb = tk.Listbox(listbox_frame, selectmode=tk.EXTENDED, font=("TkDefaultFont", 10),
                                activestyle="none", exportselection=False, height=15)
        holding_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_hold = ttk.Scrollbar(listbox_frame, command=holding_lb.yview)
        sb_hold.pack(side=tk.RIGHT, fill=tk.Y)
        holding_lb.config(yscrollcommand=sb_hold.set)
        def _populate_holdings(filter_text=""):
            """填充持股列表(自持股 group_idx=1 + Main group_idx=4)"""
            holding_lb.delete(0, tk.END)
            filter_text = (filter_text or "").strip().lower()
            all_items = []
            def _add_group(group_idx, group_label):
                hs = getattr(self, f'holding_stocks_{group_idx}', None)
                if group_idx == 1:
                    hs = self.holding_stocks
                if not hs:
                    return
                for h in hs:
                    if h:
                        n, c = h
                        n, c = str(n or ""), str(c or "")
                        if filter_text and filter_text not in (n + c).lower():
                            continue
                        all_items.append((group_label, n, c))
            _add_group(1, "自持股")
            _add_group(4, "Main持仓")
            seen = set()
            for gl, n, c in all_items:
                key = (n, c)
                if key in seen or not c:
                    continue
                seen.add(key)
                holding_lb.insert(tk.END, f"[{gl}] {n}({c})")
        _populate_holdings()
        filter_var.trace_add("write", lambda *a: _populate_holdings(filter_var.get()))
        # 全选/取消
        sel_row = ttk.Frame(list_frame)
        sel_row.pack(fill=tk.X, pady=(3, 0))
        ttk.Button(sel_row, text="全选", command=lambda: holding_lb.select_set(0, tk.END)).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel_row, text="取消全选", command=lambda: holding_lb.select_clear(0, tk.END)).pack(side=tk.LEFT, padx=2)
        ttk.Label(sel_row, textvariable=tk.StringVar(value="")).pack(side=tk.LEFT)
        # 额外上下文(可选)
        ctx_frame = ttk.LabelFrame(left_frame, text="💡 额外背景(可选)", padding=4)
        ctx_frame.pack(fill=tk.X, padx=3, pady=(0, 4))
        ctx_text = scrolledtext.ScrolledText(ctx_frame, height=3, font=("TkDefaultFont", 10))
        ctx_text.pack(fill=tk.X)
        ctx_text.insert("1.0", "")
        # 操作按钮
        action_row = ttk.Frame(left_frame)
        action_row.pack(fill=tk.X, padx=3, pady=4)
        status_var = tk.StringVar(value="💡 选中持股列表中的股票,或手动添加 → 点「🔍 开始分析」")
        ttk.Label(action_row, textvariable=status_var, font=("TkDefaultFont", 10),
                  foreground="#1565C0").pack(side=tk.LEFT, fill=tk.X, expand=True)
        analyze_btn = ttk.Button(action_row, text="🔍 开始分析", width=14)
        analyze_btn.pack(side=tk.RIGHT)
        # --- 右侧:结果区 ---
        right_frame = ttk.Frame(body)
        body.add(right_frame, weight=3)
        result_header = ttk.Frame(right_frame)
        result_header.pack(fill=tk.X, padx=3, pady=(0, 2))
        ttk.Label(result_header, text="📊 分析结果", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT)
        result_text = scrolledtext.ScrolledText(right_frame, font=("Microsoft YaHei", 11), wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 3))
        # ============ 🎨 注册彩色 tag 体系 ============
        # A股传统配色：红涨绿跌
        result_text.tag_config("header_blue",  foreground="#1565C0", font=("Microsoft YaHei", 13, "bold"))
        result_text.tag_config("dim_line",     foreground="#BDBDBD")
        result_text.tag_config("meta_info",    foreground="#546E7A", font=("Microsoft YaHei", 9))
        result_text.tag_config("tip_hint",     foreground="#7B1FA2", font=("Microsoft YaHei", 10))
        result_text.tag_config("dim_title",    foreground="#616161", font=("Microsoft YaHei", 11, "bold"))  # 维度标题 0️⃣1️⃣2️⃣
        result_text.tag_config("sec_title",    foreground="#1565C0", font=("Microsoft YaHei", 11, "bold"))  # ## 大标题
        result_text.tag_config("item_label",   foreground="#37474F", font=("Microsoft YaHei", 11, "bold"))  # - **标签**: 值
        # 情绪色
        result_text.tag_config("pos",          foreground="#C62828")   # 红: 正面(持有/买入/主线/支撑/涨)
        result_text.tag_config("pos_bold",     foreground="#C62828", font=("Microsoft YaHei", 11, "bold"))
        result_text.tag_config("neg",          foreground="#2E7D32")   # 绿: 负面(卖出/减仓/止损/破位/跌)
        result_text.tag_config("neg_bold",     foreground="#2E7D32", font=("Microsoft YaHei", 11, "bold"))
        result_text.tag_config("warn",         foreground="#E65100", background="#FFF3E0")  # 橙底: 条件/警告
        result_text.tag_config("neutral",      foreground="#F57C00")   # 橙: 观望/次主线
        result_text.tag_config("quote",        foreground="#455A64", font=("Microsoft YaHei", 10, "italic"))  # 灰色斜体引用
        result_text.tag_config("section_sep",  foreground="#90A4AE")  # ── 分隔线浅灰
        def _render_colored_result(text_widget, full_text):
            """把 AI 分析结果按结构 + 情绪面打上彩色 tag"""
            text_widget.config(state=tk.NORMAL)
            text_widget.delete("1.0", tk.END)
            # 情绪关键词 → tag 映射
            POS_KEYWORDS = ["持有", "买入", "做多", "主线", "核心逻辑", "支撑", "涨", "上涨", "强势", "多头",
                            "突破", "起爆", "✅", "🟢", "🟠", "可做T", "做T", "乐观", "看好", "机会", "买点",
                            "红", "积极", "盈利", "胜率高", "高胜率", "推荐", "值得"]
            NEG_KEYWORDS = ["卖出", "减仓", "止损", "破位", "边缘", "跌", "下跌", "弱势", "空头", "看跌",
                            "⚠️", "❌", "🔴", "不宜", "观望", "恐慌", "退潮", "不做", "回避", "减磅",
                            "绿", "消极", "亏损", "胜率低", "爆雷", "谨慎"]
            WARN_KEYWORDS = ["条件", "可能", "注意", "⚠️", "如果", "或", "视情况", "小心", "防", "控制仓位"]
            def _colorize_inline(line):
                """对单行做局部关键词染色, 返回 [(text, tag), ...] 列表"""
                # 先用正则把可能包含关键词的片段挖出来, 逐段判断
                # 简化版: 直接按词匹配 + 优先级 neg > pos
                segments = []
                remaining = line
                # 先按 emoji 切分(因为 emoji 是最明确的信号)
                # 分段: 遇到关键词就切
                kw_all = []
                for kw in POS_KEYWORDS:
                    kw_all.append((kw, "pos"))
                for kw in NEG_KEYWORDS:
                    kw_all.append((kw, "neg"))
                for kw in WARN_KEYWORDS:
                    kw_all.append((kw, "warn"))
                # 找最早出现的关键词, 递归切片
                while remaining:
                    earliest = None; earliest_tag = None; earliest_idx = 99999
                    for kw, tag in kw_all:
                        idx = remaining.find(kw)
                        if 0 <= idx < earliest_idx:
                            earliest_idx = idx; earliest = kw; earliest_tag = tag
                    if earliest is None:
                        segments.append((remaining, "")); break
                    # 前面的纯文本
                    if earliest_idx > 0:
                        segments.append((remaining[:earliest_idx], ""))
                    # 关键词本身
                    segments.append((earliest, earliest_tag))
                    # 跳过这个关键词继续
                    remaining = remaining[earliest_idx + len(earliest):]
                    # 跳过空白
                    if remaining.startswith(" "):
                        segments.append((" ", ""))
                        remaining = remaining[1:]
                return segments if segments else [(line, "")]
            lines = full_text.split("\n")
            for raw_line in lines:
                line = raw_line  # 保留原始, 避免 strip 丢空白
                stripped = line.strip()
                # ── 大标题/区块头 ──
                if stripped.startswith("## "):
                    text_widget.insert(tk.END, line + "\n", "header_blue")
                    continue
                if stripped.startswith("### "):
                    text_widget.insert(tk.END, line + "\n", "sec_title")
                    continue
                # 维度标题（0️⃣~6️⃣ / 🎯）
                if stripped and stripped[0] in "0123456🎯🔑📋📍🧩⚠️🤔🔑✅❌🟢🔴🟡":
                    if any(c in stripped for c in ["0️⃣","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","🎯"]):
                        text_widget.insert(tk.END, line + "\n", "dim_title")
                        continue
                # ── 分隔线 ──
                if all(c in "━─═│" for c in stripped) and len(stripped) > 4:
                    text_widget.insert(tk.END, line + "\n", "section_sep")
                    continue
                if stripped.startswith(("━━━━━━", "──────")):
                    text_widget.insert(tk.END, line + "\n", "section_sep")
                    continue
                # ── Blockquote ──
                if stripped.startswith(">"):
                    text_widget.insert(tk.END, line + "\n", "quote")
                    continue
                # ── Meta 信息行 ──
                if stripped.startswith(("分析股票", "时间:", "生成时间")):
                    text_widget.insert(tk.END, line + "\n", "meta_info")
                    continue
                # ── 标题里带 emoji 的 banner ──
                if "💡" in stripped and ("点" in stripped or "提示" in stripped or "想看" in stripped):
                    text_widget.insert(tk.END, line + "\n", "tip_hint")
                    continue
                # ── 普通行: 逐段局部染色 ──
                # 标签行 "- **xxx**: yyy" —— label 加粗, value 情绪染色
                m = re.match(r'^(\s*[-*]\s*\*\*[^*]+\*\*\s*[:：]\s*)(.*)$', line)
                if m:
                    label_part, value_part = m.group(1), m.group(2)
                    text_widget.insert(tk.END, label_part, "item_label")
                    for seg_text, seg_tag in _colorize_inline(value_part):
                        text_widget.insert(tk.END, seg_text, seg_tag if seg_tag else "")
                    text_widget.insert(tk.END, "\n")
                    continue
                # 其他普通行 → 局部染色
                if not stripped:
                    text_widget.insert(tk.END, "\n")  # 空行
                else:
                    for seg_text, seg_tag in _colorize_inline(line):
                        text_widget.insert(tk.END, seg_text, seg_tag if seg_tag else "")
                    text_widget.insert(tk.END, "\n")
            text_widget.config(state=tk.DISABLED)
        # 初始化彩色 banner（用渲染器）
        _init_banner = """## 💼 是否持有 · 智能分析器 (rocket-scan 方法论版)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔰 股票定性框架（三维共振模型）:
  维度1 基本面(Why) → 业绩/政策/事件驱动
  维度2 技术面(When) → 起爆点/均线/量能
  维度3 情绪面(Who) → 机构or游资or周期
📋 四类定性口诀:
  🔵 机构票 → 业绩驱动趋势,趋势不破不卖,止损-15%
  🟠 游资票 → 情绪决定高度,连板不猜顶,止损-10%
  🟡 周期/资源 → 商品牛市不要猜顶,逻辑未破坏就拿着
  ⚪ 普通票 → 20日线以上持有,跌破减仓
📚 方法论: rocket-scan (迈为-商洛-诺德-白银有色 案例归纳)
💡 点下方「🔍 开始分析」 → 自动输出 6 维彩色分析报告
⏳ AI 分析需 10-30 秒/股,请稍候..."""
        _render_colored_result(result_text, _init_banner)
        result_text.config(state=tk.DISABLED)
        # ============ 添加按钮回调 ============
        def _on_add_manual():
            c = code_var.get().strip()
            if not c:
                return
            # 查名称
            n = ""
            try:
                import tushare as _ts
                _pro = _ts.pro_api()
                _tsc = c + (".SH" if c.startswith("6") else ".SZ" if c.startswith(("0", "3")) else ".BJ")
                _sb = _pro.stock_basic(ts_code=_tsc, fields="name")
                if _sb is not None and len(_sb) > 0:
                    n = str(_sb.iloc[0]["name"])
            except Exception:
                pass
            display = f"[手动] {n}({c})" if n else f"[手动] ({c})"
            holding_lb.insert(tk.END, display)
            code_var.set("")
            cost_var.set("")
            pnl_var.set("")
        add_btn.config(command=_on_add_manual)
        # ============ 分析回调 ============
        def _collect_selected():
            """收集选中的股票信息"""
            sel = holding_lb.curselection()
            if not sel:
                return None, "请先选择股票(左侧列表点击选择,或手动添加)"
            stocks_info = []
            for idx in sel:
                item = holding_lb.get(idx)
                # 解析 [来源] 名称(代码)
                import re as _re
                m = _re.match(r"\[([^\]]+)\]\s*(.+?)\s*\((\d+)\)", item)
                if m:
                    source, name, code = m.group(1), m.group(2), m.group(3)
                else:
                    name, code = item, ""
                    source = "手动"
                stocks_info.append({
                    "name": name, "code": code,
                    "cost": cost_var.get().strip() or "未提供",
                    "pnl_pct": pnl_var.get().strip() or "未提供",
                    "buy_reason": "", "lesson": "",
                    "source": source,
                })
            return stocks_info, None
        # ============ 🧠 分析逻辑按钮(展示详细推理过程) ============
        _last_stocks = [None]  # 闭包保存上次分析的股票列表
        _last_ai_raw = [""]    # 闭包保存上次 AI 原始输出
        # 推理专用系统提示词(让 AI 把思考过程一步步写出来)
        REASONING_SYSTEM_PROMPT = """你是一位资深的交易教练，正在拆解 AI 持仓决策的完整思考过程。
请把以下"AI 给出的持有/卖出结论"背后的推理链、数据判断、类型定性依据一步步展开。
要求：
1. 先对每只股票判断【机构/游资/周期/普通】，写清楚"为什么是这个类型"的判断依据
2. 再一步步展示 AI 的思考过程（"首先检查了什么 → 发现了什么 → 因此判定..."）
3. 把 AI 可能用到但没说出来的隐含假设也写出来（如"假设该股 ROE 是多少"）
4. 指出决策中最关键的 1-2 个转折点（如果去掉这个条件，结论会不会变？）
5. 如果条件不足（如没提供 ROE 数据），标注"⚠️ 此处为 AI 合理推测，建议核实"
输出格式：
- 📍 定性推理：[类型判断] → [3-5 条依据]
- 🧩 完整推理链：[步骤1 → 步骤2 → 步骤3 → 结论]
- ⚠️ 隐含假设：[未明确给出但 AI 默认了的前提]
- 🔑 关键决策点：[最核心的 1-2 个因素，去掉它结论可能反转]
- 🤔 不确定性：[哪些地方数据不足，需要用户补充核实]"""
        def _on_show_reasoning():
            """展示上次分析的详细推理过程"""
            if not _last_stocks[0]:
                messagebox.showinfo("提示", "请先点「🔍 开始分析」生成结果，再看推理过程", parent=win)
                return
            ctx = ctx_text.get("1.0", tk.END).strip()
            stocks = _last_stocks[0]
            prev_result = _last_ai_raw[0]
            # 构造推理请求 prompt
            reasoning_prompt = f"""请对以下 {len(stocks)} 只股票的"是否持有"分析，展开详细的推理过程：
【原始分析输入 — 股票信息】
"""
            for i, s in enumerate(stocks, 1):
                reasoning_prompt += f"{i}. {s.get('name','?')}({s.get('code','?')}) | 成本:{s.get('cost','?')} | 盈亏:{s.get('pnl_pct','?')}%\n"
            reasoning_prompt += f"""
【上次 AI 给出的结论】
{prev_result[:3000] if prev_result else '(无)'}
{f'【用户额外背景】{ctx}' if ctx else ''}
---
请严格按"输出格式"每只股票分别展开完整推理链。"""
            # UI 更新
            analyze_btn.config(state=tk.DISABLED)
            status_var.set("🧠 正在展开推理链，请稍候...")
            result_text.config(state=tk.NORMAL)
            result_text.delete("1.0", tk.END)
            result_text.insert("1.0", f"🧠 正在展开 {len(stocks)} 只股票的推理过程...\n\n")
            result_text.config(state=tk.DISABLED)
            def _do_reason():
                try:
                    reasoning = self.call_ai_model(reasoning_prompt, REASONING_SYSTEM_PROMPT, max_tokens=4000)
                    if not reasoning:
                        reasoning = "AI 推理返回为空。"
                except Exception as e:
                    reasoning = f"❌ 推理失败: {e}"
                def _update():
                    result_text.config(state=tk.NORMAL)
                    result_text.delete("1.0", tk.END)
                    header = f"## 🧠 详细推理过程\n{'━' * 50}\n"
                    meta = f"分析股票: {len(stocks)} 只  |  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  数据源: 上次分析\n" + "-" * 50 + "\n\n"
                    _render_colored_result(result_text, header + meta + reasoning)
                    result_text.see("1.0")
                    result_text.config(state=tk.DISABLED)
                    analyze_btn.config(state=tk.NORMAL)
                    status_var.set("✅ 推理展开完成,可切换查看结论 vs 推理")
                if hasattr(self, "root") and self.root.winfo_exists():
                    self.root.after(0, _update)
            threading.Thread(target=_do_reason, daemon=True).start()
        # 构建"分析逻辑"按钮 —— 放在 analyze_btn 旁边
        reason_btn = ttk.Button(action_row, text="🧠 分析逻辑", width=12, command=_on_show_reasoning)
        reason_btn.pack(side=tk.RIGHT, padx=(0, 5))
        # 在分析完成时保存状态
        def _on_analyze_with_save():
            nonlocal _last_stocks, _last_ai_raw
            stocks_info, err = _collect_selected()
            if err:
                messagebox.showwarning("提示", err, parent=win)
                return
            ctx = ctx_text.get("1.0", tk.END).strip()
            _last_stocks[0] = stocks_info  # 保存引用
            analyze_btn.config(state=tk.DISABLED)
            status_var.set(f"⏳ 正在拉取 {len(stocks_info)} 只股票实时行情...")
            reason_btn.config(state=tk.DISABLED)
            result_text.config(state=tk.NORMAL)
            result_text.delete("1.0", tk.END)
            result_text.insert("1.0", f"📡 正在拉取 {len(stocks_info)} 只股票实时数据 (tushare)...\n\n")
            result_text.config(state=tk.DISABLED)
            # ============ 拉取 tushare 实时数据 ============
            try:
                stocks_info = _enrich_with_live_data(stocks_info)
                result_text.config(state=tk.NORMAL)
                result_text.insert(tk.END, "✅ 实时数据拉取完成,开始 AI 分析...\n\n")
                result_text.config(state=tk.DISABLED)
            except Exception as _e:
                result_text.config(state=tk.NORMAL)
                result_text.insert(tk.END, f"⚠️ 实时数据拉取失败: {_e}\n   AI 将使用训练数据(可能过时)\n\n")
                result_text.config(state=tk.DISABLED)
            status_var.set(f"⏳ 正在 AI 分析 {len(stocks_info)} 只股票...")
            _last_stocks[0] = stocks_info  # 保存 enriched 引用
            prompt = _build_should_hold_prompt(stocks_info, ctx)
            def _do_ai():
                try:
                    ai_result = self.call_ai_model(prompt, SHOULD_HOLD_SYSTEM_PROMPT, max_tokens=4000)
                    if not ai_result:
                        ai_result = "AI 返回为空,请稍后重试。"
                except Exception as e:
                    ai_result = f"❌ AI 分析失败: {e}"
                def _update():
                    _last_ai_raw[0] = ai_result  # 保存 AI 原始输出
                    result_text.config(state=tk.NORMAL)
                    result_text.delete("1.0", tk.END)
                    # 拼成 markdown 格式给彩色渲染器
                    header = f"## 💼 是否持有 · 分析结果\n{'━' * 50}\n"
                    meta = f"分析股票: {len(stocks_info)} 只  |  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "-" * 50 + "\n\n"
                    tip = "💡 想看 AI 是怎么一步步得出这个结论的？点上方「🧠 分析逻辑」按钮\n\n"
                    _render_colored_result(result_text, header + meta + tip + ai_result)
                    result_text.see("1.0")
                    result_text.config(state=tk.DISABLED)
                    analyze_btn.config(state=tk.NORMAL)
                    reason_btn.config(state=tk.NORMAL)
                    status_var.set("✅ 分析完成,可点「🧠 分析逻辑」查看推理过程")
                if hasattr(self, "root") and self.root.winfo_exists():
                    self.root.after(0, _update)
            threading.Thread(target=_do_ai, daemon=True).start()
        analyze_btn.config(command=_on_analyze_with_save)
        win.lift()
        win.focus_force()
        try:
            win.grab_set()
        except Exception:
            pass


    def _show_chip_cost_popup(self):
        """弹窗:对资讯表和股票表及持仓中能统计到的股票,计算股价与10日线、20日线的百分比距离,按距离%排序,红到绿渐显。"""
        def fetch_and_show():
            try:
                # 1) 资讯表:最近30天资讯中出现的股票
                stocks_by_code = {}
                try:
                    days_data = get_news_stocks_by_date_and_frequency(ndays=30)
                    for day_info in days_data:
                        for name, code in day_info.get("stocks", []):
                            if code and code not in stocks_by_code:
                                stocks_by_code[code] = name
                except Exception as e:
                    print(f"从资讯表取股票失败: {e}")
                # 2) 股票表 stock_data
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute("SELECT DISTINCT stock_code, stock_name FROM stock_data WHERE stock_code IS NOT NULL AND stock_code != ''")
                    for code, name in cur.fetchall():
                        if code and code not in stocks_by_code:
                            stocks_by_code[code] = (name or "").strip() or code
                    conn.close()
                except Exception as e:
                    print(f"从股票表取股票失败: {e}")
                # 3) 持仓 1-14
                for name, code, _, _ in self._get_all_holding_stocks():
                    if code and code not in stocks_by_code:
                        stocks_by_code[code] = (name or "").strip() or code
                if not stocks_by_code:
                    self.root.after(0, lambda: messagebox.showinfo("提示", "资讯表、股票表和持仓中暂无统计到的股票,请先添加数据。", parent=self.root))
                    return
                rows = []
                for code, name in list(stocks_by_code.items()):
                    try:
                        spot = self._get_realtime_spot_row_for_holding(code)
                        price = None
                        if spot:
                            price = spot.get("最新价")
                        if price is None:
                            continue
                        try:
                            price = float(price)
                        except (TypeError, ValueError):
                            continue
                        if price <= 0:
                            continue
                        result = self._fetch_recent_daily_closes(code, days=25, source="default", token=self.ts_token, return_volume=False)
                        if not isinstance(result, tuple) or len(result) < 2:
                            continue
                        _, closes = result[0], result[1]
                        closes = [float(x) for x in closes if x is not None]
                        if len(closes) < 10:
                            continue
                        ma10 = sum(closes[-10:]) / 10
                        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
                        dist_ma10_pct = (price - ma10) / ma10 * 100 if ma10 and ma10 > 0 else 0
                        dist_ma20_pct = (price - ma20) / ma20 * 100 if ma20 and ma20 > 0 else None
                        # 排序用:优先20日线距离,否则用10日线
                        sort_pct = dist_ma20_pct if dist_ma20_pct is not None else dist_ma10_pct
                        rows.append({
                            "stock_name": name or code,
                            "stock_code": code,
                            "price": price,
                            "ma10": round(ma10, 2),
                            "ma20": round(ma20, 2) if ma20 is not None else None,
                            "dist_ma10_pct": round(dist_ma10_pct, 2),
                            "dist_ma20_pct": round(dist_ma20_pct, 2) if dist_ma20_pct is not None else None,
                            "sort_pct": sort_pct,
                        })
                    except Exception:
                        continue
                rows.sort(key=lambda x: x["sort_pct"], reverse=True)
                self.root.after(0, lambda r=rows: self._display_chip_cost_window(r))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda e=e: messagebox.showerror("错误", f"均线距离统计失败: {e}", parent=self.root))
        threading.Thread(target=fetch_and_show, daemon=True).start()


    def _display_chip_cost_window(self, rows):
        """在主线程中显示股价与10日线、20日线距离弹窗,按距离%红到绿渐显。"""
        win = self._safe_toplevel(self.root)
        win.title("筹码成本 - 股价与10日线、20日线距离%")
        win.geometry("1000x600")
        win.transient(self.root)
        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main, text="股价高于均线为红色、低于为绿色;显示与10日线、20日线的百分比距离,按距离排序(红→绿)", font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 5))
        # 按钮区域:支持保存结果到资讯表
        button_frame = ttk.Frame(main)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        cols = ("股票名称", "股票代码", "股价", "10日线", "20日线", "与10日线距离%", "与20日线距离%")
        tree = ttk.Treeview(main, columns=cols, show="headings", height=22)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=100 if c in ("股票名称", "股票代码") else 88)
        vsb = ttk.Scrollbar(main, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.tag_configure("chip_red4", background="#ffcdd2")
        tree.tag_configure("chip_red3", background="#ef9a9a")
        tree.tag_configure("chip_red2", background="#e57373")
        tree.tag_configure("chip_red1", background="#f44336")
        tree.tag_configure("chip_green1", background="#c8e6c9")
        tree.tag_configure("chip_green2", background="#a5d6a7")
        tree.tag_configure("chip_green3", background="#81c784")
        tree.tag_configure("chip_green4", background="#4caf50")
        for r in rows:
            ma20_str = f"{r.get('ma20', 0):.2f}" if r.get("ma20") is not None else "-"
            dist_ma20_str = f"{r.get('dist_ma20_pct', 0):+.2f}%" if r.get("dist_ma20_pct") is not None else "-"
            vals = (
                str(r.get("stock_name", ""))[:10],
                r.get("stock_code", ""),
                f"{r.get('price', 0):.2f}",
                f"{r.get('ma10', 0):.2f}",
                ma20_str,
                f"{r.get('dist_ma10_pct', 0):+.2f}%",
                dist_ma20_str,
            )
            iid = tree.insert("", tk.END, values=vals)
            pct = r.get("sort_pct", 0)
            if pct >= 10:
                tree.item(iid, tags=("chip_red4",))
            elif pct >= 5:
                tree.item(iid, tags=("chip_red3",))
            elif pct >= 0:
                tree.item(iid, tags=("chip_red2",) if pct >= 1 else ("chip_red1",))
            elif pct >= -5:
                tree.item(iid, tags=("chip_green1",))
            elif pct >= -10:
                tree.item(iid, tags=("chip_green2",))
            elif pct >= -20:
                tree.item(iid, tags=("chip_green3",))
            else:
                tree.item(iid, tags=("chip_green4",))
        def save_to_news():
            """将当前筹码成本结果保存到资讯表,便于后续AI综合分析。"""
            try:
                if not rows:
                    messagebox.showinfo("提示", "当前没有可保存的数据。", parent=win)
                    return
                lines = []
                lines.append("筹码成本统计:股价与10日线、20日线的百分比距离(红=高于均线,绿=低于均线,按距离排序)。")
                for r in rows[:200]:
                    name = str(r.get("stock_name", ""))[:20]
                    code = str(r.get("stock_code", ""))
                    try:
                        price = float(r.get("price", 0) or 0)
                    except Exception:
                        price = 0.0
                    ma10 = r.get("ma10", 0) or 0
                    ma20 = r.get("ma20", None)
                    d10 = r.get("dist_ma10_pct", 0) or 0
                    d20 = r.get("dist_ma20_pct", None)
                    line = f"{name}({code}) 现价:{price:.2f} 10日线:{ma10:.2f}"
                    if ma20 is not None:
                        try:
                            line += f" 20日线:{float(ma20):.2f}"
                        except Exception:
                            line += f" 20日线:{ma20}"
                    line += f" 与10日线距离:{d10:+.2f}%"
                    if d20 is not None:
                        try:
                            line += f" 与20日线距离:{float(d20):+,.2f}%"
                        except Exception:
                            line += f" 与20日线距离:{d20}"
                    lines.append(line)
                content = "\n".join(lines)
                tab_name = "筹码成本_10日20日线距离"
                if save_news_info_to_db(tab_name, content):
                    messagebox.showinfo("成功", "已将筹码成本结果保存到资讯表,用于后续AI综合分析。", parent=win)
                else:
                    messagebox.showerror("错误", "保存到资讯表失败。", parent=win)
            except Exception as e:
                messagebox.showerror("错误", f"保存到资讯表失败: {e}", parent=win)
        ttk.Button(button_frame, text="保存到资讯表", command=save_to_news, width=16).pack(side=tk.LEFT, padx=(0, 5))
        win.lift()
        win.focus_force()


    def _on_holding_stock_monitor_toggle(self):
        """Main持仓股监测开关切换"""
        self.holding_stock_monitor_enabled = self.holding_stock_monitor_var.get()
        if self.holding_stock_monitor_enabled:
            print("[Main持仓股监测] 已开启")
            self._start_holding_stock_monitor()
            self._show_holding_stock_monitor()
        else:
            print("[Main持仓股监测] 已关闭")
            self._stop_holding_stock_monitor()


    def _update_holdings_1_to_8(self):
        """更新持仓1-8(group_index 7-14)的股票数据
        仅在点击"板块情绪监测-查看"按钮时调用
        """
        try:
            print("[持仓1-8更新] 开始更新持仓1-8的股票数据...")
            for group_index in range(7, 15):
                # 从配置文件加载持仓股
                self._load_holdings_from_config(group_index, display_only=True)
                # 更新显示(只更新前20个标签)
                holding_labels = getattr(self, f'holding_labels_{group_index}', [])
                for i in range(min(20, len(holding_labels))):
                    try:
                        self._update_holding_label(i, check_conditions=False, group_index=group_index)
                    except Exception as e:
                        print(f"更新持仓{group_index-6}标签{i}失败: {e}")
            print("[持仓1-8更新] 持仓1-8股票数据已更新")
        except Exception as e:
            print(f"[持仓1-8更新] 更新失败: {e}")


    def _update_holding_tabs_sector_labels(self):
        """更新持仓1-8标签页底部的板块名:各显示2个(从 top16_sector_names 按顺序分配)"""
        for group_index in range(7, 15):
            label = getattr(self, f'holding_tab_sector_label_{group_index}', None)
            if label is None:
                continue
            idx = (group_index - 7) * 2
            if self.top16_sector_names and idx + 1 < len(self.top16_sector_names):
                two = self.top16_sector_names[idx:idx+2]
                label.config(text="板块: " + ", ".join(two))
            elif self.top16_sector_names and idx < len(self.top16_sector_names):
                label.config(text="板块: " + self.top16_sector_names[idx])
            else:
                label.config(text="板块: -")


    def _start_holding_stock_monitor(self):
        """启动持仓股监测"""
        if self.holding_stock_monitor_running:
            return
        self.holding_stock_monitor_running = True
        def monitor_loop():
            while self.holding_stock_monitor_running:
                try:
                    if self.holding_stock_monitor_enabled:
                        self._update_holding_stock_monitor()
                except Exception as e:
                    print(f"Main持仓股监测错误: {e}")
                # 等待5分钟(300秒)
                for _ in range(300):
                    if not self.holding_stock_monitor_running:
                        break
                    time.sleep(1)
        self.holding_stock_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.holding_stock_monitor_thread.start()
        print("[Main持仓股监测] 监测已启动,每5分钟刷新一次")


    def _stop_holding_stock_monitor(self):
        """停止持仓股监测"""
        self.holding_stock_monitor_running = False
        print("[Main持仓股监测] 监测已停止")


    def _show_holding_stock_monitor(self):
        """显示Main持仓股监测窗口(显示Main标签页持仓股的日K线图,数据来自Tushare)"""
        # 如果窗口已存在,则显示并刷新
        if self.holding_stock_monitor_window is not None:
            try:
                self.holding_stock_monitor_window.deiconify()
                self.holding_stock_monitor_window.lift()
                self._update_holding_stock_monitor()
                return
            except:
                # 窗口已销毁,重新创建
                self.holding_stock_monitor_window = None
        # 创建新窗口
        monitor_window = self._safe_toplevel(self.root)
        monitor_window.title("持仓股日K线监测 - 龙头股/Main/持仓历史股/同花顺/标签1-8")
        monitor_window.geometry("1600x1000")
        self.holding_stock_monitor_window = monitor_window
        # 主框架
        main_frame = ttk.Frame(monitor_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题和刷新按钮
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        title_text = "持仓股日K线监测(龙头股/Main/持仓历史股/同花顺/标签1-8)\n筛选:5/10/20日多头发散且股价>10日线 | 每5分钟刷新 | 数据Tushare"
        ttk.Label(header_frame, text=title_text, font=("TkDefaultFont", 12, "bold"), justify=tk.LEFT).pack(side=tk.LEFT, anchor=tk.W)
        # 报警信息区:低于1日线、靠近5日线、靠近10日线、靠近20日线
        alert_frame = ttk.Frame(header_frame)
        alert_frame.pack(side=tk.LEFT, padx=(20, 0), fill=tk.X, expand=True)
        self.main_monitor_alert_label = ttk.Label(alert_frame, text="", font=("TkDefaultFont", 11), foreground="red")
        self.main_monitor_alert_label.pack(anchor=tk.W)
        self.main_monitor_near_ma5_label = ttk.Label(alert_frame, text="", font=("TkDefaultFont", 11), foreground="orange")
        self.main_monitor_near_ma5_label.pack(anchor=tk.W)
        self.main_monitor_near_ma10_label = ttk.Label(alert_frame, text="", font=("TkDefaultFont", 11), foreground="blue")
        self.main_monitor_near_ma10_label.pack(anchor=tk.W)
        self.main_monitor_near_ma20_label = ttk.Label(alert_frame, text="", font=("TkDefaultFont", 11), foreground="purple")
        self.main_monitor_near_ma20_label.pack(anchor=tk.W)
        refresh_btn = ttk.Button(header_frame, text="立即刷新",
                                command=lambda: self._update_holding_stock_monitor())
        refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))
        # 滚动框架(容纳所有持仓股的K线图:3列)
        canvas = tk.Canvas(main_frame, bg="white")
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 配置网格布局:3列
        cols = 3
        for i in range(cols):
            scrollable_frame.columnconfigure(i, weight=1, uniform="chart")
        # 存储图表组件
        chart_widgets = []
        def create_chart_frame(row, col, stock_name, stock_code, group_name, position_index):
            """创建单个持仓股K线图框架"""
            chart_frame = ttk.LabelFrame(scrollable_frame,
                                        text=f"{group_name}-{position_index+1}: {stock_name} ({stock_code})",
                                        padding=5)
            chart_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                from matplotlib.figure import Figure
                fig = Figure(figsize=(5, 3), dpi=80)
                ax = fig.add_subplot(111)
                canvas_widget = FigureCanvasTkAgg(fig, chart_frame)
                canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                # 显示加载中
                ax.text(0.5, 0.5, "加载中...", ha='center', va='center',
                       transform=ax.transAxes, fontsize=10)
                canvas_widget.draw()
                chart_widgets.append({
                    'stock_name': stock_name,
                    'stock_code': stock_code,
                    'group_name': group_name,
                    'position_index': position_index,
                    'fig': fig,
                    'ax': ax,
                    'canvas': canvas_widget,
                    'frame': chart_frame
                })
            except ImportError:
                error_label = tk.Label(chart_frame, text="matplotlib未安装",
                                     font=("TkDefaultFont", 11), fg="red")
                error_label.pack(fill=tk.BOTH, expand=True)
        # 获取龙头股、Main、持仓历史股、同花顺、标签1-8的持仓股,按股票代码去重(每个代码只保留一个)
        monitor_holdings_raw = self._get_monitor_holding_stocks()
        seen_codes = set()
        monitor_holdings = []
        for (stock_name, stock_code, group_name, position_index) in monitor_holdings_raw:
            if not stock_code or stock_code in seen_codes:
                continue
            seen_codes.add(stock_code)
            monitor_holdings.append((stock_name, stock_code, group_name, position_index))
        # 创建持仓股K线图框架(3列)
        for idx, (stock_name, stock_code, group_name, position_index) in enumerate(monitor_holdings):
            if not stock_code:
                continue
            row = idx // cols
            col = idx % cols
            create_chart_frame(row, col, stock_name, stock_code, group_name, position_index)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 存储图表组件到窗口对象
        monitor_window.chart_widgets = chart_widgets
        # 初始加载数据
        self._update_holding_stock_monitor()
        # 窗口关闭事件
        def on_closing():
            self.holding_stock_monitor_window = None
            monitor_window.destroy()
        monitor_window.protocol("WM_DELETE_WINDOW", on_closing)


    def _update_holding_stock_monitor(self):
        """更新持仓股监测窗口的K线图(带排序)"""
        if self.holding_stock_monitor_window is None:
            return
        try:
            chart_widgets = getattr(self.holding_stock_monitor_window, 'chart_widgets', [])
            if not chart_widgets:
                return
            # 存储每个图表的排序键和图表信息
            chart_data_with_sort = []
            # 存储低于1日线、靠近5/10/20日线的股票(用于报警显示)
            below_ma1_stocks = []
            near_ma5_stocks = []
            near_ma10_stocks = []
            near_ma20_stocks = []
            def _fmt_date(s):
                if not s or len(s) != 8:
                    return str(s)
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            def update_chart(chart_info):
                """更新单个图表并计算排序键(日K线,数据来自Tushare)"""
                try:
                    stock_name = chart_info['stock_name']
                    stock_code = chart_info['stock_code']
                    ax = chart_info['ax']
                    fig = chart_info['fig']
                    canvas = chart_info['canvas']
                    # 清空图表
                    ax.clear()
                    try:
                        # 获取日K线数据(Tushare)
                        kline_data = self._get_daily_kline_data_tushare(str(stock_code).zfill(6), days=60)
                        if kline_data is None:
                            # 无数据视为不符合条件,不显示任何内容(不绘制提示)
                            return
                        data = kline_data['data']
                        ma_values = kline_data['ma_values']
                        trade_dates = kline_data.get('trade_dates') or []
                        closes = data['收盘'].values
                        opens = data['开盘'].values
                        highs = data['最高'].values
                        lows = data['最低'].values
                        n = len(closes)
                        dates = list(range(n))
                        current_price = float(closes[-1]) if n else 0
                        # 排序键:日K下 1日线=昨日收盘,5日线=5日均,10日线=10日均
                        sort_key = (3, 0)
                        above_ma1 = False
                        ma1_cross_k_count = 0
                        ref_ma1 = float(closes[-2]) if n >= 2 else (float(closes[-1]) if n else 0)
                        if n >= 2 and current_price > ref_ma1:
                            above_ma1 = True
                            sort_key = (0, -current_price)
                            ma1_cross_k_count = 1
                        else:
                            if n >= 2:
                                below_ma1_stocks.append(stock_name)
                        ma5 = float(sum(closes[-5:]) / 5) if n >= 5 else None
                        ma10 = float(sum(closes[-10:]) / 10) if n >= 10 else None
                        ma20 = float(sum(closes[-20:]) / 20) if n >= 20 else None
                        if not above_ma1 and ma5 is not None:
                            if current_price > ma5:
                                sort_key = (1, -current_price)
                        if ma10 is not None and current_price > ma10:
                            sort_key = (2, -current_price)
                        # 筛选:5/10/20日多头发散(MA5>MA10>MA20)且股价>10日线
                        pass_filter = (
                            n >= 20 and ma5 is not None and ma10 is not None and ma20 is not None
                            and ma5 > ma10 > ma20
                            and current_price > ma10
                        )
                        if not pass_filter:
                            return  # 不符合条件直接不显示,不绘制任何内容
                        # 靠近5/10/20日线检测(距离≤3%)
                        if ma5 is not None and ma5 > 0:
                            dist5 = abs(current_price - ma5) / ma5 * 100
                            if dist5 <= 3.0:
                                near_ma5_stocks.append(stock_name)
                        if ma10 is not None and ma10 > 0:
                            dist10 = abs(current_price - ma10) / ma10 * 100
                            if dist10 <= 3.0:
                                near_ma10_stocks.append(stock_name)
                        if ma20 is not None and ma20 > 0:
                            dist20 = abs(current_price - ma20) / ma20 * 100
                            if dist20 <= 3.0:
                                near_ma20_stocks.append(stock_name)
                        chart_data_with_sort.append((sort_key, chart_info))
                        # 绘制日K蜡烛图
                        for i in range(n):
                            color = 'red' if closes[i] >= opens[i] else 'green'
                            body_bottom = min(float(opens[i]), float(closes[i]))
                            body_top = max(float(opens[i]), float(closes[i]))
                            ax.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)
                            ax.plot([i, i], [float(lows[i]), body_bottom], color=color, linewidth=1)
                            ax.plot([i, i], [body_top, float(highs[i])], color=color, linewidth=1)
                        ax.plot(dates, closes, color='black', linewidth=0.5, label='收盘', alpha=0.5, linestyle='--')
                        # 绘制均线
                        period_map = {'ma1': 1, 'ma5': 5, 'ma10': 10, 'ma20': 20}
                        ma_colors = {'ma1': '#FF0000', 'ma5': '#00FF00', 'ma10': '#0000FF', 'ma20': '#FF00FF'}
                        ma_labels = {'ma1': 'MA1', 'ma5': 'MA5', 'ma10': 'MA10', 'ma20': 'MA20'}
                        for ma_name in ['ma1', 'ma5', 'ma10', 'ma20']:
                            if ma_name not in ma_values or len(ma_values[ma_name]) == 0:
                                continue
                            ma_data = ma_values[ma_name]
                            period = period_map[ma_name]
                            start_idx = min(period - 1, n - 1)
                            ma_indices = list(range(start_idx, start_idx + len(ma_data)))
                            min_len = min(len(ma_indices), len(ma_data))
                            if min_len > 0:
                                ax.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],
                                       linewidth=0.8, label=ma_labels[ma_name], alpha=0.8)
                        title_text = f"{stock_name} ({stock_code})"
                        if above_ma1 and ma1_cross_k_count > 0:
                            title_text += " [穿上1日线第1根]"
                        elif above_ma1:
                            title_text += " [在1日线上]"
                        ax.set_title(title_text, fontsize=8, fontweight='bold')
                        ax.set_xlabel('日期', fontsize=6)
                        ax.set_ylabel('价格', fontsize=6)
                        ax.legend(loc='upper left', fontsize=5)
                        ax.grid(True, alpha=0.3)
                        step = max(1, len(trade_dates) // 8)
                        ax.set_xticks(dates[::step])
                        ax.set_xticklabels([_fmt_date(trade_dates[i]) if i < len(trade_dates) else str(i) for i in dates[::step]], rotation=45, ha='right', fontsize=5)
                        fig.tight_layout()
                        canvas.draw()
                    except Exception as e:
                        print(f"获取 {stock_code} 日K线失败: {e}")
                        ax.text(0.5, 0.5, f"加载失败:\n{str(e)[:30]}", ha='center', va='center',
                               transform=ax.transAxes, fontsize=8, wrap=True)
                        canvas.draw()
                except Exception as e:
                    print(f"更新持仓股 {chart_info.get('stock_name', '未知')} K线图失败: {e}")
                    try:
                        ax = chart_info.get('ax')
                        canvas = chart_info.get('canvas')
                        if ax and canvas:
                            ax.clear()
                            ax.text(0.5, 0.5, f"加载失败:\n{str(e)[:30]}", ha='center', va='center',
                                   transform=ax.transAxes, fontsize=8, wrap=True)
                            canvas.draw()
                    except:
                        pass
            # 在后台线程中更新所有图表并排序
            def update_all_charts():
                for chart_info in chart_widgets:
                    update_chart(chart_info)
                # 等待所有图表更新完成
                import time
                time.sleep(2)
                # 对图表进行排序
                chart_data_with_sort.sort(key=lambda x: x[0])
                # 按股票代码去重,每个代码只保留一个(保留排序后第一个即最优)
                seen_codes = set()
                chart_data_with_sort_dedup = []
                for item in chart_data_with_sort:
                    code = item[1].get('stock_code', '')
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        chart_data_with_sort_dedup.append(item)
                chart_data_with_sort = chart_data_with_sort_dedup
                # 更新报警标签(低于1日线的股票)
                def update_alert_label():
                    try:
                        if hasattr(self, 'main_monitor_alert_label') and self.main_monitor_alert_label:
                            if below_ma1_stocks:
                                alert_text = f"⚠ 低于1日线: {', '.join(below_ma1_stocks)}"
                                self.main_monitor_alert_label.config(text=alert_text, foreground="red")
                                print(f"[Main持仓股监测] 报警: 以下股票低于1日线: {', '.join(below_ma1_stocks)}")
                                # 弹窗预警(只对新增的低于1日线的股票弹窗,避免重复)
                                new_alert_stocks = []
                                for stock in below_ma1_stocks:
                                    # 使用股票名和当前日期作为key,每天最多报警一次
                                    import datetime
                                    today = datetime.date.today().strftime("%Y%m%d")
                                    alert_key = f"{stock}_{today}"
                                    if alert_key not in self.main_below_ma1_alerted:
                                        new_alert_stocks.append(stock)
                                        self.main_below_ma1_alerted.add(alert_key)
                                # 清理过期的报警记录(保留当天的)
                                today = datetime.date.today().strftime("%Y%m%d")
                                self.main_below_ma1_alerted = {
                                    key for key in self.main_below_ma1_alerted
                                    if key.endswith(f"_{today}")
                                }
                                # 如果有新增的低于1日线的股票,弹窗预警
                                if new_alert_stocks:
                                    alert_msg = "【Main持仓股预警】\n\n以下股票低于1日线,请注意风险:\n\n"
                                    alert_msg += "\n".join([f"• {stock}" for stock in new_alert_stocks])
                                    alert_msg += "\n\n建议及时关注并考虑止损操作!"
                                    # 使用非阻塞方式显示消息框
                                    def show_alert():
                                        try:
                                            from tkinter import messagebox
                                            messagebox.showwarning("Main持仓股预警", alert_msg)
                                        except Exception as e:
                                            print(f"弹窗预警失败: {e}")
                                    # 延迟100ms显示,避免阻塞主线程
                                    self.root.after(100, show_alert)
                            else:
                                self.main_monitor_alert_label.config(text="✓ 所有股票均在1日线上", foreground="green")
                                # 清空已报警记录(当所有股票都回到1日线上时)
                                # 注意:不清空,保留当天的记录,避免反复弹窗
                            # 靠近5/10/20日线标签
                            if hasattr(self, 'main_monitor_near_ma5_label') and self.main_monitor_near_ma5_label:
                                self.main_monitor_near_ma5_label.config(
                                    text=f"靠近5日线: {', '.join(near_ma5_stocks)}" if near_ma5_stocks else "靠近5日线: 无")
                            if hasattr(self, 'main_monitor_near_ma10_label') and self.main_monitor_near_ma10_label:
                                self.main_monitor_near_ma10_label.config(
                                    text=f"靠近10日线: {', '.join(near_ma10_stocks)}" if near_ma10_stocks else "靠近10日线: 无")
                            if hasattr(self, 'main_monitor_near_ma20_label') and self.main_monitor_near_ma20_label:
                                self.main_monitor_near_ma20_label.config(
                                    text=f"靠近20日线: {', '.join(near_ma20_stocks)}" if near_ma20_stocks else "靠近20日线: 无")
                    except Exception as e:
                        print(f"更新报警标签失败: {e}")
                # 在主线程中更新标签
                try:
                    self.root.after(0, update_alert_label)
                except:
                    pass
                # 重新排列图表位置
                cols = 3
                try:
                    # 获取scrollable_frame
                    scrollable_frame = None
                    for widget in self.holding_stock_monitor_window.winfo_children():
                        if isinstance(widget, ttk.Frame):
                            for child in widget.winfo_children():
                                if isinstance(child, tk.Canvas):
                                    canvas_widget = child
                                    for canvas_child in canvas_widget.winfo_children():
                                        if isinstance(canvas_child, ttk.Frame):
                                            scrollable_frame = canvas_child
                                            break
                                    break
                    if scrollable_frame:
                        # 隐藏不符合筛选条件的图表
                        passed_infos = {id(cinfo) for (_, cinfo) in chart_data_with_sort}
                        for chart_info in chart_widgets:
                            try:
                                frame = chart_info.get('frame')
                                if frame and id(chart_info) not in passed_infos:
                                    frame.grid_remove()
                            except Exception:
                                pass
                        # 重新排列符合条件的图表(使用 frame 引用)
                        for idx, (sort_key, chart_info) in enumerate(chart_data_with_sort):
                            try:
                                chart_frame = chart_info.get('frame')
                                if not chart_frame:
                                    for widget in scrollable_frame.winfo_children():
                                        if isinstance(widget, ttk.LabelFrame):
                                            if chart_info.get('stock_code', '') in widget.cget('text'):
                                                chart_frame = widget
                                                break
                                if chart_frame:
                                    row = idx // cols
                                    col = idx % cols
                                    chart_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                            except Exception:
                                pass
                except:
                    pass
            # 使用线程更新,避免阻塞UI
            threading.Thread(target=update_all_charts, daemon=True).start()
        except Exception as e:
            print(f"更新Main持仓股监测失败: {e}")
            import traceback
            traceback.print_exc()


    def _start_holding_amplitude_monitor(self):
        """启动持仓股振幅监控"""
        if self.holding_amplitude_monitor_running:
            return
        self.holding_amplitude_monitor_running = True
        # 启动时从界面同步一次开关状态,避免界面已勾选但内部未同步导致"开了没动静"
        try:
            if getattr(self, 'amplitude_alert_var', None) is not None:
                self.amplitude_alert_enabled = bool(self.amplitude_alert_var.get())
            if getattr(self, 'ma_alert_var', None) is not None:
                self.ma_alert_enabled = bool(self.ma_alert_var.get())
            if getattr(self, 'break_ma1_alert_var', None) is not None:
                self.break_ma1_alert_enabled = bool(self.break_ma1_alert_var.get())
            if getattr(self, 'break_ma5_alert_var', None) is not None:
                self.break_ma5_alert_enabled = bool(self.break_ma5_alert_var.get())
            if getattr(self, 'break_ma20_alert_var', None) is not None:
                self.break_ma20_alert_enabled = bool(self.break_ma20_alert_var.get())
        except Exception:
            pass
        def monitor_loop():
            while self.holding_amplitude_monitor_running:
                try:
                    # 使用主线程已同步的内部标志,避免在后台线程读取 Tk 变量(Tkinter 非线程安全会导致开关一直不执行)
                    amp_on = getattr(self, 'amplitude_alert_enabled', False)
                    ma_on = getattr(self, 'ma_alert_enabled', False)
                    break_ma_on = (getattr(self, 'break_ma1_alert_enabled', False) or
                                   getattr(self, 'break_ma5_alert_enabled', False) or
                                   getattr(self, 'break_ma20_alert_enabled', False))
                    if amp_on:
                        self._check_holding_amplitude_alerts()
                    if ma_on:
                        self._check_holding_ma_alerts()
                    if break_ma_on:
                        self._check_holding_break_ma_alerts()
                except Exception as e:
                    print(f"持仓股监控错误: {e}")
                # 等待检查间隔
                time.sleep(self.holding_amplitude_check_interval)
        self.holding_amplitude_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.holding_amplitude_monitor_thread.start()
        print("[持仓监控] 持仓股监控已启动")


    def _stop_holding_amplitude_monitor(self):
        """停止持仓股振幅监控"""
        self.holding_amplitude_monitor_running = False
        print("[持仓监控] 持仓股振幅监控已停止")


    def _check_holding_conditions(self, stock_name, stock_code):
        """检测持仓股是否满足开新仓条件(仅检查1日、5日、10日、20日均线)"""
        try:
            # 获取股票代码
            if not stock_code:
                stock_code = get_stock_code_by_name(stock_name)
            if not stock_code:
                return False
            # 注意:持仓检测仅检查均线状态,不检查大盘分数、外围情绪分数、15分钟/60分钟多头排列
            # 检测均线状态(1日、5日、10日、20日)
            # 获取最近收盘价数据
            result = self._fetch_recent_daily_closes(stock_code, days=45, source="default", token=self.ts_token, return_volume=False)
            if isinstance(result, tuple) and len(result) >= 2:
                dates, closes = result[:2]
            else:
                _dates, closes = result, []
            if not closes or len(closes) < 20:
                return False
            # 优先获取实时价格或当日价格
            realtime_price = None
            try:
                # 尝试使用tushare获取实时价格
                if TS_AVAILABLE and (self.ts_token or TS_DEFAULT_TOKEN):
                    try:
                        import tushare as ts
                        ts_token = self.ts_token or TS_DEFAULT_TOKEN
                        os.environ["TUSHARE_TOKEN"] = ts_token
                        ts_code = self._format_ts_code(stock_code)
                        # 先尝试实时行情
                        try:
                            df = ts.realtime_quote(ts_code=ts_code, src='dc')
                            if df is not None and not df.empty and 'price' in df.columns:
                                realtime_price = float(df.iloc[0]['price'])
                                if realtime_price > 0.01 and realtime_price < 10000:
                                    print(f"[持仓条件检测-实时] {stock_code} 实时价格: {realtime_price}")
                        except:
                            pass  # 跳过 daily fallback
                    except Exception as e:
                        print(f"获取实时价格失败 {stock_code}: {e}")
            except:
                pass
            # 如果获取到实时价格,使用实时价格;否则使用历史收盘价
            if realtime_price and realtime_price > 0:
                latest_price = realtime_price
            else:
                latest_price = float(closes[-1])
            # 检测1日线(不判断是否上升,只判断是否站上)
            if len(closes) >= 3:
                ref_price = float(closes[-2])
                float(closes[-3])
                ma1_crossed = latest_price >= ref_price
                # 1日线只判断是否站上,不考虑是否上升
                if not ma1_crossed:
                    return False
            else:
                return False
            # 检测5日线
            if len(closes) >= 7:
                ma5_values = [float(closes[i]) for i in range(len(closes)-5, len(closes))]
                ref_ma5 = sum(ma5_values) / len(ma5_values)
                prev_ma5_values = [float(closes[i]) for i in range(len(closes)-10, len(closes)-5)]
                prev_ma5 = sum(prev_ma5_values) / len(prev_ma5_values) if len(prev_ma5_values) >= 5 else ref_ma5
                ma5_crossed = latest_price >= ref_ma5
                ma5_uptrend = ref_ma5 >= prev_ma5
                if not (ma5_crossed and ma5_uptrend):
                    return False
            else:
                return False
            # 检测10日线
            if len(closes) >= 12:
                ma10_values = [float(closes[i]) for i in range(len(closes)-10, len(closes))]
                ref_ma10 = sum(ma10_values) / len(ma10_values)
                prev_ma10_values = [float(closes[i]) for i in range(len(closes)-20, len(closes)-10)]
                prev_ma10 = sum(prev_ma10_values) / len(prev_ma10_values) if len(prev_ma10_values) >= 10 else ref_ma10
                ma10_crossed = latest_price >= ref_ma10
                ma10_uptrend = ref_ma10 >= prev_ma10
                if not (ma10_crossed and ma10_uptrend):
                    return False
            else:
                return False
            # 检测20日线
            if len(closes) >= 22:
                ma20_values = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
                ref_ma20 = sum(ma20_values) / len(ma20_values)
                prev_ma20_values = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
                prev_ma20 = sum(prev_ma20_values) / len(prev_ma20_values) if len(prev_ma20_values) >= 20 else ref_ma20
                ma20_crossed = latest_price >= ref_ma20
                ma20_uptrend = ref_ma20 >= prev_ma20
                if not (ma20_crossed and ma20_uptrend):
                    return False
            else:
                return False
            # 所有均线条件都满足
            return True
        except Exception as e:
            print(f"检测持仓股条件失败: {e}")
            return False


    def _start_holding_auto_check(self):
        """启动持仓股自动检测(每15分钟)"""
        if self.holding_check_running:
            return
        self.holding_check_running = True
        def auto_check_loop():
            while self.holding_check_running:
                try:
                    # 获取大盘情绪指数
                    market_score = self._get_market_sentiment_score()
                    # 检测所有持仓股(静默模式,不显示消息框)
                    if any(self.holding_stocks):
                        for i, holding in enumerate(self.holding_stocks):
                            if holding:
                                stock_name, stock_code = holding
                                try:
                                    # 使用三维一体检测
                                    detection_result = self._three_dimensional_detection(stock_name, stock_code)
                                    if detection_result['success']:
                                        can_open = detection_result['technical']['can_open']
                                        ma_status = detection_result['technical']['ma_status']
                                        kelly_result = detection_result['position']
                                        is_golden = False
                                        try:
                                            is_golden = bool(self._check_golden_stock_recent_20d(stock_code, stock_name or ''))
                                        except Exception:
                                            pass
                                        near_buy, near_sell = False, False
                                        try:
                                            near_buy, near_sell = self._holding_sr_buy_sell_from_daily_kline(stock_code)
                                        except Exception:
                                            pass
                                        red_star = False
                                        try:
                                            red_star = bool(self._holding_red_star_signal_5d_low_ma1(stock_code))
                                        except Exception:
                                            pass
                                        # 存储凯利公式结果
                                        self.holding_kelly_results[i] = {
                                            'ratio': kelly_result['kelly_ratio'],
                                            'b': kelly_result['b'],
                                            'p': kelly_result['p'],
                                            'ma_status': ma_status.copy(),
                                            'is_golden_stock': is_golden,
                                            'near_support_buy': near_buy,
                                            'near_resistance_sell': near_sell,
                                            'red_star_signal': red_star,
                                        }
                                        def update_ui(idx=i, result=can_open, score=market_score):
                                            if idx < len(self.holding_labels):
                                                # 自动检测循环已禁用,这里不会被执行
                                                self._update_holding_label(idx, check_conditions=False)
                                        self.root.after(0, update_ui)
                                    else:
                                        print(f"三维一体检测失败: {detection_result.get('error', '未知错误')}")
                                    time.sleep(1)  # 每个股票检测间隔1秒
                                except Exception as e:
                                    print(f"自动检测持仓股 {stock_name} 失败: {e}")
                    # 等待15分钟(900秒)
                    for _ in range(900):
                        if not self.holding_check_running:
                            break
                        time.sleep(1)
                except Exception as e:
                    print(f"自动检测持仓股失败: {e}")
                    time.sleep(60)  # 出错后等待1分钟再继续
        self.holding_check_thread = threading.Thread(target=auto_check_loop, daemon=True)
        self.holding_check_thread.start()


    def _stop_holding_auto_check(self):
        """停止持仓股自动检测"""
        self.holding_check_running = False


    def _show_holding_analysis_in_right_panel(self, index, group_index=1):
        """在右侧面板显示持仓股的均线检测结果和K线图"""
        # 获取对应组的数据结构
        holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
        if index >= len(holding_stocks) or not holding_stocks[index]:
            # 清空右侧面板显示
            for widget in self.holding_analysis_container.winfo_children():
                widget.destroy()
            ttk.Label(self.holding_analysis_container,
                     text="该持仓位置未设置股票",
                     font=("TkDefaultFont", 12),
                     foreground="gray").pack(expand=True)
            return
        stock_name, stock_code = holding_stocks[index]
        if not stock_code:
            stock_code = get_stock_code_by_name(stock_name)
        if not stock_code:
            # 清空右侧面板显示
            for widget in self.holding_analysis_container.winfo_children():
                widget.destroy()
            ttk.Label(self.holding_analysis_container,
                     text=f"无法获取股票代码: {stock_name}",
                     font=("TkDefaultFont", 12),
                     foreground="red").pack(expand=True)
            return
        # 清空右侧面板
        for widget in self.holding_analysis_container.winfo_children():
            widget.destroy()
        # 显示加载中
        loading_label = ttk.Label(self.holding_analysis_container,
                                 text="正在加载均线检测结果和K线图...",
                                 font=("TkDefaultFont", 12))
        loading_label.pack(expand=True)
        self._safe_update()
        # 在后台线程中加载数据
        def load_analysis_data():
            try:
                # 1. 检测均线(1日、5日、10日、20日)
                ma_results = self._check_moving_averages_for_holding(stock_code, stock_name)
                # 2. 获取日K线数据(Tushare)
                kline_data = self._get_daily_kline_data_tushare(stock_code, days=60)
                # 在主线程中更新UI
                def update_ui():
                    # 清空加载提示
                    loading_label.destroy()
                    # 创建滚动框架
                    scroll_frame = ttk.Frame(self.holding_analysis_container)
                    scroll_frame.pack(fill=tk.BOTH, expand=True)
                    # 创建Canvas和滚动条
                    canvas = tk.Canvas(scroll_frame, bg="white")
                    scrollbar = ttk.Scrollbar(scroll_frame, orient=tk.VERTICAL, command=canvas.yview)
                    inner_frame = ttk.Frame(canvas)
                    inner_frame.bind(
                        "<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                    )
                    canvas.create_window((0, 0), window=inner_frame, anchor="nw")
                    canvas.configure(yscrollcommand=scrollbar.set)
                    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    # 显示股票名称
                    title_frame = ttk.Frame(inner_frame)
                    title_frame.pack(fill=tk.X, padx=10, pady=10)
                    ttk.Label(title_frame, text=f"{stock_name} ({stock_code})",
                             font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)
                    # 显示均线检测结果
                    ma_frame = ttk.LabelFrame(inner_frame, text="均线检测结果", padding=10)
                    ma_frame.pack(fill=tk.X, padx=10, pady=5)
                    ma_periods = [('ma1', '1日'), ('ma5', '5日'), ('ma10', '10日'), ('ma20', '20日')]
                    ma_row = ttk.Frame(ma_frame)
                    ma_row.pack(fill=tk.X)
                    for ma_key, ma_name in ma_periods:
                        passed = ma_results.get(ma_key, False)
                        color = "red" if passed else "green"
                        status_text = "通过" if passed else "未通过"
                        ma_label_frame = ttk.Frame(ma_row)
                        ma_label_frame.pack(side=tk.LEFT, padx=10)
                        ttk.Label(ma_label_frame, text=f"{ma_name}线:", font=("TkDefaultFont", 12)).pack()
                        status_label = tk.Label(ma_label_frame, text=status_text,
                                               font=("TkDefaultFont", 12, "bold"),
                                               bg=color, fg="white", padx=10, pady=5)
                        status_label.pack(pady=5)
                    # 显示日K线图(Tushare)
                    if kline_data:
                        kline_frame = ttk.LabelFrame(inner_frame, text="日K线图(Tushare)", padding=10)
                        kline_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                        # 绘制日K线图
                        self._draw_daily_kline_chart(kline_frame, kline_data, stock_name)
                    else:
                        error_label = ttk.Label(inner_frame,
                                               text="无法获取日K线数据(请检查Tushare配置)",
                                               font=("TkDefaultFont", 12),
                                               foreground="red")
                        error_label.pack(padx=10, pady=10)
                self.root.after(0, update_ui)
            except Exception as e:
                def show_error(e=e):
                    loading_label.destroy()
                    error_label = ttk.Label(self.holding_analysis_container,
                                           text=f"加载失败: {e}",
                                           font=("TkDefaultFont", 12),
                                           foreground="red")
                    error_label.pack(expand=True)
                self.root.after(0, show_error)
                import traceback
                traceback.print_exc()
        threading.Thread(target=load_analysis_data, daemon=True).start()


    def _check_moving_averages_for_holding(self, stock_code, stock_name):
        """检测持仓股的均线(1日、5日、10日、20日)"""
        try:
            # 获取历史数据(至少需要20日)
            hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq", start_date="")
            if hist_data.empty or len(hist_data) < 20:
                return {'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False}
            # 取最近20日数据
            recent_data = hist_data.tail(20)
            close_prices = recent_data['收盘'].values
            current_price = close_prices[-1]
            # 计算均线
            ma1 = close_prices[-1]  # 1日均线就是当前价格
            ma5 = sum(close_prices[-5:]) / 5 if len(close_prices) >= 5 else current_price
            ma10 = sum(close_prices[-10:]) / 10 if len(close_prices) >= 10 else current_price
            ma20 = sum(close_prices[-20:]) / 20 if len(close_prices) >= 20 else current_price
            # 检测:当前价格是否在均线之上(通过=红色,未通过=绿色)
            return {
                'ma1': current_price >= ma1,  # 1日均线总是通过
                'ma5': current_price >= ma5,
                'ma10': current_price >= ma10,
                'ma20': current_price >= ma20
            }
        except Exception as e:
            print(f"检测均线失败 {stock_code}: {e}")
            return {'ma1': False, 'ma5': False, 'ma10': False, 'ma20': False}


    def _holding_sr_buy_sell_from_daily_kline(self, stock_code, threshold_pct=2.0):
        """持仓检测:当日收盘与支撑/压力线价差绝对值≤threshold_pct% → 买入/卖出标记。"""
        near_buy, near_sell = False, False
        try:
            kd = self._get_daily_kline_data_tushare(str(stock_code).zfill(6), days=60)
            if not kd:
                return near_buy, near_sell
            sr = self._compute_daily_support_resistance_line_prices(kd)
            close = sr.get('close')
            if close is None or close <= 0:
                return near_buy, near_sell
            sp = sr.get('support_price')
            if sp is not None and sp > 0:
                if abs(close - sp) / sp * 100.0 <= threshold_pct:
                    near_buy = True
            rp = sr.get('resistance_price')
            if rp is not None and rp > 0:
                if abs(close - rp) / rp * 100.0 <= threshold_pct:
                    near_sell = True
        except Exception:
            pass
        return near_buy, near_sell


    def _show_holding_detail(self, index, group_index=1):
        """显示持仓股详情弹出框"""
        # 获取对应组的数据结构
        holding_stocks, _holding_labels, _holding_kelly_results, _holding_low_diff_results = self._get_holding_group_data(group_index)
        if index >= len(holding_stocks) or not holding_stocks[index]:
            messagebox.showinfo("提示", "该持仓位置未设置股票", parent=self.root)
            return
        stock_name, stock_code = holding_stocks[index]
        if not stock_code:
            stock_code = get_stock_code_by_name(stock_name)
        if not stock_code:
            messagebox.showwarning("警告", f"无法获取股票代码: {stock_name}", parent=self.root)
            return
        # 创建弹出窗口
        detail_window = self._safe_toplevel(self.root)
        detail_window.title(f"持仓详情 - {stock_name} ({stock_code})")
        detail_window.geometry("1000x900")
        # 获取股票数据表的逻辑(在最初位置显示)
        stock_logic_text = ""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # 查询该股票在stock_logic表中的最新逻辑
            cursor.execute('''
                SELECT logic FROM stock_logic
                WHERE stock_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (stock_name,))
            row = cursor.fetchone()
            if row and row[0]:
                stock_logic_text = row[0]
            conn.close()
        except Exception as e:
            print(f"获取股票数据表逻辑失败: {e}")
        # 创建上下分割的PanedWindow
        main_paned = ttk.PanedWindow(detail_window, orient=tk.VERTICAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 上半部分:逻辑文本和均线检测结果
        top_frame = ttk.Frame(main_paned)
        main_paned.add(top_frame, weight=1)
        # 顶部按钮区域
        button_frame = ttk.Frame(top_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        # 保存当前索引和持仓股列表到窗口对象,用于切换
        detail_window._current_index = index
        detail_window._holding_stocks = holding_stocks
        detail_window._group_index = group_index
        # 左右箭头按钮(用于切换前后持仓股)
        def switch_stock(direction):
            """切换股票(direction: -1为上一个,1为下一个),自动跳过空的持仓位置"""
            current_idx = detail_window._current_index
            stocks = detail_window._holding_stocks
            group_idx = detail_window._group_index
            # 查找下一个有效的持仓位置
            new_index = current_idx + direction
            # 向前查找(direction < 0)或向后查找(direction > 0)
            while True:
                # 检查边界
                if new_index < 0:
                    messagebox.showinfo("提示", "已经是第一个持仓股", parent=detail_window)
                    return
                if new_index >= len(stocks):
                    messagebox.showinfo("提示", "已经是最后一个持仓股", parent=detail_window)
                    return
                # 检查该位置是否有股票
                if stocks[new_index] and stocks[new_index][0]:  # 有股票名称
                    break
                # 继续查找下一个位置
                new_index += direction
            # 更新索引
            detail_window._current_index = new_index
            # 关闭当前窗口并打开新的详情窗口
            detail_window.destroy()
            self._show_holding_detail(new_index, group_idx)
        # 左箭头按钮(上一个)
        prev_button = ttk.Button(button_frame, text="◀ 上一个", command=lambda: switch_stock(-1), width=12)
        prev_button.pack(side=tk.LEFT, padx=5)
        # 右箭头按钮(下一个)
        next_button = ttk.Button(button_frame, text="下一个 ▶", command=lambda: switch_stock(1), width=12)
        next_button.pack(side=tk.LEFT, padx=5)
        # 分隔符
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        # 股票输入框和确认按钮
        ttk.Label(button_frame, text="股票:", font=("TkDefaultFont", 11)).pack(side=tk.LEFT, padx=(5, 2))
        stock_input_var = tk.StringVar()
        stock_input_entry = ttk.Entry(button_frame, textvariable=stock_input_var, width=15)
        stock_input_entry.pack(side=tk.LEFT, padx=2)
        def analyze_input_stock():
            """分析输入的股票"""
            input_text = stock_input_var.get().strip()
            if not input_text:
                messagebox.showwarning("警告", "请输入股票代码或名称", parent=detail_window)
                return
            # 判断输入的是代码还是名称
            input_code = None
            input_name = None
            # 如果是纯数字,可能是代码
            if input_text.isdigit():
                input_code = input_text
                # 尝试获取股票名称
                try:
                    import akshare as ak
                    stock_info = safe_call(ak.stock_info_a_code_name, fallback=pd.DataFrame(), label="ak.stock_info_a_code_name")
                    stock_row = stock_info[stock_info['code'] == input_code]
                    if not stock_row.empty:
                        input_name = stock_row.iloc[0]['name']
                    else:
                        # 尝试ETF
                        etf_info = safe_call(ak.fund_etf_spot_em, fallback=pd.DataFrame(), label="ak.fund_etf_spot_em")
                        if not etf_info.empty:
                            etf_row = etf_info[etf_info['代码'] == input_code]
                            if not etf_row.empty:
                                input_name = etf_row.iloc[0]['名称']
                except:
                    pass
            else:
                # 输入的是名称,尝试获取代码
                input_name = input_text
                input_code = get_stock_code_by_name(input_text)
            # 验证股票信息
            if not input_code:
                messagebox.showerror("错误", f"无法找到股票: {input_text}\n请检查股票代码或名称是否正确", parent=detail_window)
                return
            if not input_name:
                # 如果还没有名称,尝试通过代码获取
                try:
                    import akshare as ak
                    stock_info = safe_call(ak.stock_info_a_code_name, fallback=pd.DataFrame(), label="ak.stock_info_a_code_name")
                    stock_row = stock_info[stock_info['code'] == input_code]
                    if not stock_row.empty:
                        input_name = stock_row.iloc[0]['name']
                    else:
                        etf_info = safe_call(ak.fund_etf_spot_em, fallback=pd.DataFrame(), label="ak.fund_etf_spot_em")
                        if not etf_info.empty:
                            etf_row = etf_info[etf_info['代码'] == input_code]
                            if not etf_row.empty:
                                input_name = etf_row.iloc[0]['名称']
                except:
                    input_name = input_code  # 如果获取失败,使用代码作为名称
            # 关闭当前窗口并打开新股票的详情窗口
            # 创建一个临时的持仓股列表,只包含这一个股票
            # 关闭当前窗口
            detail_window.destroy()
            # 创建一个新的详情窗口(使用临时数据)
            # 临时修改_get_holding_group_data的返回值,或者直接调用显示函数
            # 由于_show_holding_detail依赖于_get_holding_group_data,我们需要创建一个辅助函数
            self._show_stock_detail_direct(input_name, input_code, group_index)
        # 确认按钮
        confirm_button = ttk.Button(button_frame, text="确认分析", command=analyze_input_stock, width=10)
        confirm_button.pack(side=tk.LEFT, padx=5)
        # 绑定回车键
        stock_input_entry.bind("<Return>", lambda e: analyze_input_stock())
        # 分隔符
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        # 构建股票链接
        def build_stock_urls(code):
            """构建新浪和东方财富的股票链接"""
            urls = {}
            if code:
                # 新浪财经链接
                if code.startswith('6'):
                    urls['新浪'] = f"https://finance.sina.com.cn/realstock/company/sh{code}/nc.shtml"
                else:
                    urls['新浪'] = f"https://finance.sina.com.cn/realstock/company/sz{code}/nc.shtml"
                # 东方财富链接
                if code.startswith('6'):
                    urls['东方财富'] = f"https://quote.eastmoney.com/sh{code}.html"
                else:
                    urls['东方财富'] = f"https://quote.eastmoney.com/sz{code}.html"
            return urls
        stock_urls = build_stock_urls(stock_code)
        def open_url(url_name):
            """打开股票链接"""
            import webbrowser
            url = stock_urls.get(url_name)
            if url:
                webbrowser.open(url)
        # 链接按钮
        if stock_urls.get('新浪'):
            ttk.Button(button_frame, text="新浪", command=lambda: open_url('新浪'), width=10).pack(side=tk.LEFT, padx=5)
        if stock_urls.get('东方财富'):
            ttk.Button(button_frame, text="东方财富", command=lambda: open_url('东方财富'), width=12).pack(side=tk.LEFT, padx=5)
        # 大单按钮
        def load_big_order_data():
            """加载大单和股票详情"""
            detail_text.config(state=tk.NORMAL)
            detail_text.insert(tk.END, "\n【正在获取大单和股票详情...】\n")
            detail_text.see(tk.END)
            detail_text.config(state=tk.DISABLED)
            detail_window.update()
            try:
                # 获取大单净流入数据
                order_data = self._get_large_order_net_inflow_with_accumulation(stock_code, days=20)
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, "\n【大单净流入数据】\n")
                if order_data['daily']:
                    detail_text.insert(tk.END, "最近5日大单净流入:\n")
                    for item in order_data['daily']:
                        net_inflow = item['net_inflow']
                        color_tag = "red_normal" if net_inflow > 0 else "green_normal"
                        detail_text.insert(tk.END, f"  {item['date']}: {net_inflow:+,.2f} 万元\n", color_tag)
                    detail_text.insert(tk.END, "\n")
                if order_data['accumulation']:
                    detail_text.insert(tk.END, "累计大单净流入:\n")
                    for period, value in order_data['accumulation'].items():
                        color_tag = "red_normal" if value > 0 else "green_normal"
                        detail_text.insert(tk.END, f"  {period}累计: {value:+,.2f} 万元\n", color_tag)
                    detail_text.insert(tk.END, "\n")
                # 获取股票基本信息
                try:
                    import akshare as ak
                    stock_info = ak.stock_individual_info_em(symbol=stock_code)
                    if stock_info is not None and not stock_info.empty:
                        detail_text.insert(tk.END, "【股票基本信息】\n")
                        for _, row in stock_info.iterrows():
                            item = row.get('item', '')
                            value = row.get('value', '')
                            if item and value:
                                detail_text.insert(tk.END, f"{item}: {value}\n")
                        detail_text.insert(tk.END, "\n")
                except Exception as e:
                    detail_text.insert(tk.END, f"获取股票基本信息失败: {e}\n\n")
                detail_text.config(state=tk.DISABLED)
                detail_text.see(tk.END)
            except Exception as e:
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, f"获取大单数据失败: {e}\n\n")
                detail_text.config(state=tk.DISABLED)
        ttk.Button(button_frame, text="大单", command=load_big_order_data, width=10).pack(side=tk.LEFT, padx=5)
        def open_hotmoney_heart():
            """🦅 打开该股票的心法全解弹窗"""
            try:
                detail_window.withdraw()  # 先隐藏详情窗
                self._open_hotmoney_single_dialog(auto_code=stock_code, auto_name=stock_name)
            except Exception as e:
                detail_window.deiconify()
                import tkinter.messagebox as _mb
                _mb.showerror("错误", f"打开心法全解失败: {e}", parent=self.root)
        ttk.Button(button_frame, text="🦅 心法全解", command=open_hotmoney_heart, width=12).pack(side=tk.LEFT, padx=5)
        def save_to_news():
            """保存为资讯"""
            try:
                content = "【持仓股详情】\n"
                content += f"股票名称: {stock_name}\n"
                content += f"股票代码: {stock_code}\n\n"
                # 获取基本信息
                try:
                    import akshare as ak
                    stock_info = ak.stock_individual_info_em(symbol=stock_code)
                    if stock_info is not None and not stock_info.empty:
                        content += "【基本信息】\n"
                        for _, row in stock_info.iterrows():
                            item = row.get('item', '')
                            value = row.get('value', '')
                            if item and value:
                                content += f"{item}: {value}\n"
                        content += "\n"
                except:
                    pass
                # 获取大单净流入数据
                order_data = self._get_large_order_net_inflow_with_accumulation(stock_code, days=20)
                if order_data['daily']:
                    content += "【最近5日大单净流入】\n"
                    for item in order_data['daily']:
                        content += f"{item['date']}: {item['net_inflow']:,.2f} 万元\n"
                    content += "\n"
                if order_data['accumulation']:
                    content += "【累计大单净流入】\n"
                    for period, value in order_data['accumulation'].items():
                        content += f"{period}累计: {value:,.2f} 万元\n"
                    content += "\n"
                # 获取涨跌幅数据
                price_changes = self._get_stock_price_changes(stock_code, days=20)
                if price_changes:
                    content += "【最近5日涨跌幅】\n"
                    for item in price_changes[:5]:
                        content += f"{item['date']}: {item['change_pct']:+.2f}%\n"
                    content += "\n"
                    # 计算累计涨跌幅
                    if len(price_changes) >= 3:
                        acc_3d = sum([p['change_pct'] for p in price_changes[:3]])
                        content += f"3日累计涨跌幅: {acc_3d:+.2f}%\n"
                    if len(price_changes) >= 5:
                        acc_5d = sum([p['change_pct'] for p in price_changes[:5]])
                        content += f"5日累计涨跌幅: {acc_5d:+.2f}%\n"
                    if len(price_changes) >= 10:
                        acc_10d = sum([p['change_pct'] for p in price_changes[:10]])
                        content += f"10日累计涨跌幅: {acc_10d:+.2f}%\n"
                    if len(price_changes) >= 20:
                        acc_20d = sum([p['change_pct'] for p in price_changes[:20]])
                        content += f"20日累计涨跌幅: {acc_20d:+.2f}%\n"
                # 保存到资讯
                tab_name = f"持仓详情_{stock_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                tab_id = self.create_text_tab(tab_name)
                text_widget = self.text_widgets[tab_id]['widget']
                text_widget.insert("1.0", content)
                # 保存到数据库
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO news_info (tab_name, content, created_at)
                        VALUES (?, ?, ?)
                    ''', (tab_name, content, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"保存到数据库失败: {e}")
                messagebox.showinfo("成功", "已保存为资讯", parent=detail_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=detail_window)
        def open_stock_data_table():
            """打开股票数据表,并自动填充股票名称"""
            try:
                # 打开数据表窗口
                db_window = self.show_unified_db_display(default_tab="stock_logic")
                # 延迟执行,确保窗口已创建
                def fill_stock_name():
                    try:
                        # 如果窗口有stock_name_var属性,直接设置
                        if hasattr(db_window, '_stock_name_var'):
                            db_window._stock_name_var.set(stock_name)
                    except Exception as e:
                        print(f"自动填充股票名称失败: {e}")
                # 延迟200ms执行,确保窗口已完全创建
                detail_window.after(200, fill_stock_name)
            except Exception as e:
                messagebox.showerror("错误", f"打开数据表失败: {e}", parent=detail_window)
        ttk.Button(button_frame, text="保存为资讯", command=save_to_news, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="打开股票数据表", command=open_stock_data_table, width=15).pack(side=tk.LEFT, padx=5)
        # 🦅 游资心法快速分析 (双击 → 心法全解弹窗)
        hm_frame = tk.LabelFrame(detail_window, text="🦅 游资心法快照 (双击看全解)", bg="#FAFAFA", font=("", 10, "bold"), fg="#1565C0")
        hm_frame.pack(fill=tk.X, padx=10, pady=4)
        def _hm_open_detail(_evt=None):
            try:
                detail_window.withdraw()
                self._open_hotmoney_single_dialog(auto_code=stock_code, auto_name=stock_name)
            except Exception as _he:
                messagebox.showerror("错误", f"打开游资心法全解失败: {_he}", parent=detail_window)
        hm_frame.bind("<Double-1>", _hm_open_detail)
        try:
            hm_data = self._hm_calc_for_stock(stock_code)
            hm_score = hm_data.get("avg_score")
            if hm_score is not None:
                best = hm_data.get("best_sch", "--")
                score_lines = []
                for hm_name, hm_info in hm_data.get("scores", {}).items():
                    sc = hm_info.get("score", 0)
                    score_lines.append(f"{hm_name}{sc}")
                hm_txt = (f"🦅 综合 {hm_score}分  |  最强流派: {best}\n"
                          + "  ".join(score_lines))
                hm_lbl = tk.Label(hm_frame, text=hm_txt, bg="#FAFAFA", fg="#1565C0",
                                  font=("", 9), anchor="w", justify=tk.LEFT, cursor="hand2")
                hm_lbl.pack(anchor="w", padx=8, pady=6)
                hm_lbl.bind("<Double-1>", _hm_open_detail)
            else:
                hm_lbl2 = tk.Label(hm_frame, text="⏳ 计算中... (双击看全解)", bg="#FAFAFA", fg="#666",
                         font=("", 9), cursor="hand2")
                hm_lbl2.pack(padx=8, pady=6)
                hm_lbl2.bind("<Double-1>", _hm_open_detail)
        except Exception as _hm_err:
            hm_lbl3 = tk.Label(hm_frame, text=f"计算失败: {_hm_err} (双击看全解)", bg="#FAFAFA", fg="#1565C0",
                     font=("", 9), cursor="hand2")
            hm_lbl3.pack(padx=8, pady=6)
            hm_lbl3.bind("<Double-1>", _hm_open_detail)
        # 创建滚动文本框显示详情(使用Text以便支持颜色和字体粗细)
        text_frame = ttk.Frame(top_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        detail_text = tk.Text(text_frame, wrap=tk.WORD, font=("TkDefaultFont", 12))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=detail_text.yview)
        detail_text.configure(yscrollcommand=scrollbar.set)
        detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 配置文本标签(用于颜色和字体粗细)
        detail_text.tag_configure("red_normal", foreground="red", font=("TkDefaultFont", 12))
        detail_text.tag_configure("red_bold", foreground="red", font=("TkDefaultFont", 12, "bold"))
        detail_text.tag_configure("red_bold_large", foreground="red", font=("TkDefaultFont", 12, "bold"))
        detail_text.tag_configure("green_normal", foreground="green", font=("TkDefaultFont", 12))
        detail_text.tag_configure("green_bold", foreground="green", font=("TkDefaultFont", 12, "bold"))
        detail_text.tag_configure("green_bold_large", foreground="green", font=("TkDefaultFont", 12, "bold"))
        detail_text.tag_configure("yellow_bold", foreground="orange", font=("TkDefaultFont", 12, "bold"))  # 黄色标签用于10日均线距离提示
        detail_text.tag_configure("energy_title", foreground="#5e35b1", font=("TkDefaultFont", 13, "bold"))
        detail_text.tag_configure("energy_header", foreground="#424242", font=("TkDefaultFont", 12, "bold"))
        energy_tag_cache = set()
        energy_palettes = {
            "positive": ["#ef9a9a", "#e57373", "#ef5350", "#e53935", "#c62828"],  # 红色(浅->深)
            "neutral": ["#222222", "#1f1f1f", "#1b1b1b", "#171717", "#111111"],   # 黑色(浅->深)
            "negative": ["#a5d6a7", "#81c784", "#66bb6a", "#43a047", "#2e7d32"],  # 绿色(浅->深)
        }
        def _energy_line_tone_and_strength(line_text):
            """根据量能说明文案给出情绪方向(正/中/负)和强度[0,1]。"""
            s = (line_text or "").strip()
            if not s:
                return "neutral", 0.0
            # 方向判断:按关键词做规则映射(用户要求:正面红、中性黄、负面绿)
            pos_keys = ("聚集", "蓄势", "多头", "上行", "上移", "上涨", "进攻", "回补", "更强")
            neg_keys = ("发散", "释放", "空头", "下行", "下移", "下跌", "打压", "回调", "更弱")
            if any(k in s for k in pos_keys):
                tone = "positive"
            elif any(k in s for k in neg_keys):
                tone = "negative"
            else:
                tone = "neutral"
            # 强度估算:优先读"比值",其次读百分比,最后用默认中等强度
            strength = 0.35
            m_ratio = re.search(r"比\s*([0-9]+(?:\.[0-9]+)?)", s)
            if m_ratio:
                ratio = float(m_ratio.group(1))
                strength = min(1.0, abs(ratio - 1.0) / 0.35)
            else:
                pcts = [abs(float(x)) for x in re.findall(r"([+-]?\d+(?:\.\d+)?)\s*%", s)]
                if pcts:
                    strength = min(1.0, max(pcts) / 6.0)
            return tone, max(0.0, min(1.0, strength))
        def _insert_energy_block_with_style(block_text):
            """将能量学分析按行插入并着色:正红/中黄/负绿,强度映射颜色深浅与字号。"""
            for raw_line in (block_text or "").splitlines(True):
                line = raw_line.rstrip("\n")
                stripped = line.strip()
                if not stripped:
                    detail_text.insert(tk.END, raw_line)
                    continue
                if stripped.startswith("【能量学分析"):
                    detail_text.insert(tk.END, raw_line, "energy_title")
                    continue
                if stripped.startswith("如何读下面五条指标:"):
                    detail_text.insert(tk.END, raw_line, "energy_header")
                    continue
                is_explain_line = (
                    stripped.startswith(("· ", "→", "1", "2", "3", "4", "5")) or "解读:" in stripped
                )
                if not is_explain_line:
                    detail_text.insert(tk.END, raw_line)
                    continue
                tone, strength = _energy_line_tone_and_strength(stripped)
                level = round(strength * 4)  # 0..4
                color = energy_palettes[tone][level]
                size = 12 + level               # 12..16
                weight = "bold" if level >= 2 else "normal"
                tag_name = f"energy_{tone}_{level}_{weight}"
                if tag_name not in energy_tag_cache:
                    detail_text.tag_configure(tag_name, foreground=color, font=("TkDefaultFont", size, weight))
                    energy_tag_cache.add(tag_name)
                detail_text.insert(tk.END, raw_line, tag_name)
        # AI分析按钮(需要在detail_text定义之后)
        def run_ai_analysis():
            """运行AI分析"""
            # 在文本末尾显示"正在分析..."
            detail_text.config(state=tk.NORMAL)
            ai_start_pos = detail_text.index(tk.END)
            detail_text.insert(tk.END, "\n" + "="*80 + "\n")
            detail_text.insert(tk.END, "【AI分析】\n")
            detail_text.insert(tk.END, "="*80 + "\n")
            detail_text.insert(tk.END, "正在分析中,请稍候...\n")
            detail_text.see(tk.END)
            detail_text.config(state=tk.DISABLED)
            detail_window.update()
            # 在后台线程中运行AI分析
            def analyze_in_background():
                try:
                    # 获取股票基本信息
                    stock_info_text = ""
                    try:
                        import akshare as ak
                        stock_info = ak.stock_individual_info_em(symbol=stock_code)
                        if stock_info is not None and not stock_info.empty:
                            stock_info_text = "\n股票基本信息:\n"
                            for _, row in stock_info.iterrows():
                                item = row.get('item', '')
                                value = row.get('value', '')
                                if item and value:
                                    stock_info_text += f"{item}: {value}\n"
                    except Exception as e:
                        stock_info_text = f"获取基本信息失败: {e}\n"
                    # 获取均线检测结果
                    ma_info = ""
                    if detection_result:
                        ma_info = "\n均线检测结果:\n"
                        if 'ma1' in detection_result:
                            ma1 = detection_result['ma1']
                            ma_info += f"1日线: {'已站上' if ma1['crossed'] else '未站上'}, {'上升' if ma1['uptrend'] else '未上升'}, 当前价: {detection_result['current_price']:.2f}, 参考1日线: {ma1['ref']:.2f}\n"
                        if 'ma5' in detection_result:
                            ma5 = detection_result['ma5']
                            ma_info += f"5日线: {'已站上' if ma5['crossed'] else '未站上'}, {'上升' if ma5['uptrend'] else '未上升'}, 参考5日线: {ma5['ref']:.2f}\n"
                        if 'ma10' in detection_result:
                            ma10 = detection_result['ma10']
                            ma_info += f"10日线: {'已站上' if ma10['crossed'] else '未站上'}, {'上升' if ma10['uptrend'] else '未上升'}, 参考10日线: {ma10['ref']:.2f}\n"
                        if 'ma20' in detection_result:
                            ma20 = detection_result['ma20']
                            ma_info += f"20日线: {'已站上' if ma20['crossed'] else '未站上'}, {'上升' if ma20['uptrend'] else '未上升'}, 参考20日线: {ma20['ref']:.2f}\n"
                    # 构建AI分析提示词
                    prompt = f"""请作为专业的证券分析师,对以下股票进行全面的多维度分析:
股票名称:{stock_name}
股票代码:{stock_code}
{stock_info_text}
{ma_info}
股票逻辑信息:
{stock_logic_text if stock_logic_text else '暂无逻辑信息'}
请从以下几个维度进行专业分析:
1. **基本面分析**:
   - 公司主营业务和行业地位
   - 财务状况(盈利能力、偿债能力、运营能力)
   - 估值水平(PE、PB等)
   - 行业对比和竞争优势
2. **技术面分析**:
   - 当前技术形态和趋势
   - 均线系统分析
   - 支撑位和阻力位
   - 技术指标信号
3. **财务面分析**:
   - 营收和利润增长情况
   - 现金流状况
   - 资产负债结构
   - 财务健康度评估
4. **概念分析**:
   - 所属概念板块
   - 概念热度
   - 政策支持情况
   - 市场关注度
5. **成长性分析**:
   - 业绩增长潜力
   - 行业成长空间
   - 公司发展规划
   - 未来增长驱动因素
6. **板块分析**:
   - 所属行业板块
   - 板块轮动情况
   - 板块内地位
   - 板块发展趋势
请提供专业的、结构化的分析报告,包括每个维度的详细分析和综合评价。"""
                    # 系统提示词
                    system_prompt = "你是一位资深的证券分析师,具有丰富的股票分析经验。请从基本面、技术面、财务面、概念、成长性、板块等多个维度对股票进行专业分析,提供客观、深入、有价值的分析报告。"
                    # 调用AI模型
                    ai_result = self.call_ai_model(prompt, system_prompt)
                    if not ai_result:
                        ai_result = "AI分析失败:未获取到分析结果"
                    # 在主线程中更新UI
                    def update_ui():
                        detail_text.config(state=tk.NORMAL)
                        # 删除"正在分析中"文本
                        detail_text.delete(ai_start_pos, tk.END)
                        # 插入AI分析结果
                        detail_text.insert(tk.END, "\n" + "="*80 + "\n")
                        detail_text.insert(tk.END, "【AI分析】\n")
                        detail_text.insert(tk.END, "="*80 + "\n")
                        detail_text.insert(tk.END, ai_result + "\n")
                        detail_text.see(tk.END)
                        detail_text.config(state=tk.DISABLED)
                    detail_window.after(0, update_ui)
                except Exception as e:
                    def show_error(e=e):
                        detail_text.config(state=tk.NORMAL)
                        detail_text.delete(ai_start_pos, tk.END)
                        detail_text.insert(tk.END, "\n" + "="*80 + "\n")
                        detail_text.insert(tk.END, "【AI分析】\n")
                        detail_text.insert(tk.END, "="*80 + "\n")
                        detail_text.insert(tk.END, f"AI分析失败:{e}\n")
                        detail_text.see(tk.END)
                        detail_text.config(state=tk.DISABLED)
                    detail_window.after(0, show_error)
                    import traceback
                    traceback.print_exc()
            threading.Thread(target=analyze_in_background, daemon=True).start()
        ttk.Button(button_frame, text="🤖 AI分析", command=run_ai_analysis, width=12).pack(side=tk.LEFT, padx=5)
        # 股票描述按钮
        def load_stock_description():
            """加载股票描述信息"""
            detail_text.config(state=tk.NORMAL)
            detail_text.insert(tk.END, "\n【正在获取股票描述...】\n")
            detail_text.see(tk.END)
            detail_text.config(state=tk.DISABLED)
            detail_window.update()
            try:
                # 构建股票描述
                description = f"### {stock_name} ({stock_code})\n\n"
                # 1. 核心业务
                description += "1. **核心业务**:"
                try:
                    # 尝试从多个数据源获取
                    core_business = None
                    # 尝试1: AKShare
                    try:
                        import akshare as ak
                        stock_info = ak.stock_individual_info_em(symbol=stock_code)
                        if stock_info is not None and not stock_info.empty:
                            for _, row in stock_info.iterrows():
                                item = row.get('item', '')
                                value = row.get('value', '')
                                if '主营业务' in item or '经营范围' in item:
                                    core_business = value
                                    break
                    except Exception:
                        pass
                    # 尝试2: 新浪财经
                    if not core_business:
                        try:
                            import re

                            import requests
                            url = f"https://finance.sina.com.cn/realstock/company/{'sh' if stock_code.startswith('6') else 'sz'}{stock_code}/nc.shtml"
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            response = requests.get(url, headers=headers, timeout=5)
                            if response.status_code == 200:
                                # 简单解析主营业务
                                match = re.search(r'主营业务:([^<]+)', response.text)
                                if match:
                                    core_business = match.group(1).strip()
                        except Exception:
                            pass
                    # 尝试3: 东方财富
                    if not core_business:
                        try:
                            import re

                            import requests
                            url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/Index?type=web&code={stock_code}"
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            response = requests.get(url, headers=headers, timeout=5)
                            if response.status_code == 200:
                                # 简单解析主营业务
                                match = re.search(r'公司简介.*?<p>(.*?)</p>', response.text, re.DOTALL)
                                if match:
                                    core_business = match.group(1).strip()
                        except Exception:
                            pass
                    if core_business:
                        description += f"{core_business}\n"
                    else:
                        description += "暂无数据\n"
                except Exception as e:
                    description += f"获取失败: {e}\n"
                # 2. 财务概况
                description += "\n2. **财务概况**:\n"
                try:
                    # 尝试从多个数据源获取
                    finance_data = None
                    # 尝试1: AKShare
                    try:
                        import akshare as ak
                        finance_data = ak.stock_financial_analysis_indicator(symbol=stock_code)
                    except Exception:
                        pass
                    if finance_data is not None and not finance_data.empty:
                        # 获取最新季度数据
                        latest_data = finance_data.iloc[0]
                        description += f"- 营收: {latest_data.get('营业总收入', '暂无')}\n"
                        description += f"- 净利润: {latest_data.get('净利润', '暂无')}\n"
                        description += f"- 资产负债率: {latest_data.get('资产负债率', '暂无')}\n"
                        description += f"- 净资产收益率: {latest_data.get('净资产收益率', '暂无')}\n"
                    else:
                        description += "- 暂无数据\n"
                except Exception as e:
                    description += f"- 获取失败: {e}\n"
                # 3. 市场特征
                description += "\n3. **市场特征**:\n"
                try:
                    # 尝试从多个数据源获取
                    industry = None
                    total_share = None
                    float_share = None
                    # 尝试1: AKShare
                    try:
                        import akshare as ak
                        stock_info = ak.stock_individual_info_em(symbol=stock_code)
                        if stock_info is not None and not stock_info.empty:
                            for _, row in stock_info.iterrows():
                                item = row.get('item', '')
                                value = row.get('value', '')
                                if '所属行业' in item:
                                    industry = value
                                elif '总股本' in item:
                                    total_share = value
                                elif '流通股本' in item:
                                    float_share = value
                    except Exception:
                        pass
                    if industry:
                        description += f"- 所属行业: {industry}\n"
                    if total_share:
                        description += f"- 总股本: {total_share}\n"
                    if float_share:
                        description += f"- 流通股本: {float_share}\n"
                    # 获取近期涨跌幅
                    try:
                        price_changes = self._get_stock_price_changes(stock_code, days=30)
                        if price_changes:
                            recent_change = price_changes[0]['change_pct']
                            description += f"- 近期涨跌幅: {recent_change:+.2f}%\n"
                    except Exception:
                        pass
                except Exception as e:
                    description += f"- 获取失败: {e}\n"
                # 4. 最新动态
                description += "\n4. **最新动态**:\n"
                try:
                    # 尝试从多个数据源获取
                    news_list = []
                    # 尝试1: AKShare
                    try:
                        import akshare as ak
                        news_data = ak.stock_news_em(symbol=stock_code)
                        if news_data is not None and not news_data.empty:
                            for _, row in news_data.head(5).iterrows():
                                title = row.get('title', '')
                                time = row.get('time', '')
                                news_list.append(f"- {time}: {title}")
                    except Exception:
                        pass
                    # 尝试2: 新浪财经
                    if not news_list:
                        try:
                            import re

                            import requests
                            url = f"https://finance.sina.com.cn/realstock/company/{'sh' if stock_code.startswith('6') else 'sz'}{stock_code}/nc.shtml"
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            response = requests.get(url, headers=headers, timeout=5)
                            if response.status_code == 200:
                                # 简单解析新闻
                                matches = re.findall(r'<a href=.*?>(.*?)</a>.*?\((\d{4}-\d{2}-\d{2})\)', response.text)
                                for title, date in matches[:5]:
                                    news_list.append(f"- {date}: {title.strip()}")
                        except Exception:
                            pass
                    if news_list:
                        description += "\n".join(news_list) + "\n"
                    else:
                        description += "- 暂无数据\n"
                except Exception as e:
                    description += f"- 获取失败: {e}\n"
                # 显示股票描述
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, "\n" + "="*80 + "\n")
                detail_text.insert(tk.END, "【股票描述】\n")
                detail_text.insert(tk.END, "="*80 + "\n")
                detail_text.insert(tk.END, description + "\n")
                detail_text.see(tk.END)
                detail_text.config(state=tk.DISABLED)
            except Exception as e:
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, f"\n【股票描述】\n获取失败: {e}\n\n")
                detail_text.config(state=tk.DISABLED)
        ttk.Button(button_frame, text="股票描述", command=load_stock_description, width=12).pack(side=tk.LEFT, padx=5)
        # 游资分析按钮
        def load_hot_money_analysis():
            """加载游资分析信息"""
            detail_text.config(state=tk.NORMAL)
            detail_text.insert(tk.END, "\n【正在获取游资分析...】\n")
            detail_text.see(tk.END)
            detail_text.config(state=tk.DISABLED)
            detail_window.update()
            try:
                # 1. 从配置表获取游资名单
                hot_money_list = []
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS hot_money_info (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE,
                            source TEXT,
                            updated_at TEXT
                        )
                    ''')
                    cursor.execute('SELECT name FROM hot_money_info')
                    rows = cursor.fetchall()
                    hot_money_list = [row[0] for row in rows]
                    conn.close()
                except Exception as e:
                    print(f"从配置表获取游资名单失败: {e}")
                # 2. 如果游资名单为空,从多个网站获取
                if not hot_money_list:
                    hot_money_list = []
                    # 从淘股吧获取
                    try:
                        import re

                        import requests
                        url = "https://www.taoguba.com.cn/Article/3457880/1"
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            # 简单解析游资名字
                            matches = re.findall(r'[\u4e00-\u9fa5]+(?:游资|席位|营业部)', response.text)
                            hot_money_list.extend([match for match in matches if match not in hot_money_list])
                    except Exception:
                        pass
                    # 从东方财富获取
                    try:
                        import re

                        import requests
                        url = "https://data.eastmoney.com/stock/tradedetail.html"
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            # 简单解析游资名字
                            matches = re.findall(r'[\u4e00-\u9fa5]+(?:营业部|席位)', response.text)
                            hot_money_list.extend([match for match in matches if match not in hot_money_list])
                    except Exception:
                        pass
                    # 从同花顺获取
                    try:
                        import re

                        import requests
                        url = "http://data.10jqka.com.cn/market/longhu/list/"
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            # 简单解析游资名字
                            matches = re.findall(r'[\u4e00-\u9fa5]+(?:营业部|席位)', response.text)
                            hot_money_list.extend([match for match in matches if match not in hot_money_list])
                    except Exception:
                        pass
                    # 从搜索引擎获取
                    try:
                        import re

                        import requests
                        url = "https://www.baidu.com/s?wd=游资席位名单"
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            # 简单解析游资名字
                            matches = re.findall(r'[\u4e00-\u9fa5]+(?:游资|席位|营业部)', response.text)
                            hot_money_list.extend([match for match in matches if match not in hot_money_list])
                    except Exception:
                        pass
                    # 保存游资名单到配置表
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        for name in hot_money_list:
                            try:
                                cursor.execute('''
                                    INSERT OR IGNORE INTO hot_money_info (name, source, updated_at)
                                    VALUES (?, ?, ?)
                                ''', (name, 'multiple_sources', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                            except Exception:
                                pass
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        print(f"保存游资名单失败: {e}")
                # 3. 构建游资分析
                analysis = f"### 游资分析 ({stock_name} - {stock_code})\n\n"
                # 游资名单
                analysis += "1. **游资名单**:\n"
                if hot_money_list:
                    analysis += "\n".join([f"- {name}" for name in hot_money_list[:20]]) + "\n"
                else:
                    analysis += "- 暂无数据\n"
                # 游资活跃度分析
                analysis += "\n2. **游资活跃度分析**:\n"
                try:
                    # 这里可以添加游资活跃度分析逻辑
                    # 例如,分析近期该股票的龙虎榜数据,查看游资进出情况
                    analysis += "- 暂无数据\n"
                except Exception as e:
                    analysis += f"- 获取失败: {e}\n"
                # 游资偏好分析
                analysis += "\n3. **游资偏好分析**:\n"
                try:
                    # 这里可以添加游资偏好分析逻辑
                    # 例如,分析游资在该股票上的历史操作记录
                    analysis += "- 暂无数据\n"
                except Exception as e:
                    analysis += f"- 获取失败: {e}\n"
                # 显示游资分析
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, "\n" + "="*80 + "\n")
                detail_text.insert(tk.END, "【游资分析】\n")
                detail_text.insert(tk.END, "="*80 + "\n")
                detail_text.insert(tk.END, analysis + "\n")
                detail_text.see(tk.END)
                detail_text.config(state=tk.DISABLED)
            except Exception as e:
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, f"\n【游资分析】\n获取失败: {e}\n\n")
                detail_text.config(state=tk.DISABLED)
        ttk.Button(button_frame, text="游资分析", command=load_hot_money_analysis, width=12).pack(side=tk.LEFT, padx=5)
        # 保存为资讯按钮
        def save_to_news_single():
            """保存当前分析内容为资讯"""
            try:
                # 获取当前文本内容
                current_content = detail_text.get("1.0", tk.END)
                # 构建资讯内容
                content = "【持仓股分析】\n"
                content += f"股票名称: {stock_name}\n"
                content += f"股票代码: {stock_code}\n\n"
                content += current_content
                # 保存到资讯
                tab_name = f"持仓分析_{stock_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                tab_id = self.create_text_tab(tab_name)
                text_widget = self.text_widgets[tab_id]['widget']
                text_widget.insert("1.0", content)
                # 保存到数据库
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO news_info (tab_name, content, created_at)
                        VALUES (?, ?, ?)
                    ''', (tab_name, content, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"保存到数据库失败: {e}")
                messagebox.showinfo("成功", "已保存为资讯", parent=detail_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=detail_window)
        # 一键保存按钮
        def save_all_analysis():
            """一键保存所有分析内容到资讯表"""
            try:
                # 构建完整分析内容
                content = "【持仓股综合分析】\n"
                content += f"股票名称: {stock_name}\n"
                content += f"股票代码: {stock_code}\n\n"
                # 1. 基本信息
                content += "="*80 + "\n"
                content += "【基本信息】\n"
                content += "="*80 + "\n"
                content += f"股票名称: {stock_name}\n"
                content += f"股票代码: {stock_code}\n"
                content += "股票链接: "
                if stock_urls.get('新浪'):
                    content += "新浪 | "
                if stock_urls.get('东方财富'):
                    content += "东方财富"
                content += "\n\n"
                # 2. 股票数据表逻辑
                if stock_logic_text:
                    content += "="*80 + "\n"
                    content += "【股票数据表逻辑】\n"
                    content += "="*80 + "\n"
                    content += stock_logic_text + "\n"
                    content += "="*80 + "\n\n"
                # 3. 均线检测结果
                try:
                    detection_result = get_detailed_ma_detection()
                    if detection_result:
                        content += "="*80 + "\n"
                        content += "【均线检测结果】\n"
                        content += "="*80 + "\n"
                        if 'ma1' in detection_result:
                            ma1 = detection_result['ma1']
                            cross_text = "已站上" if ma1['crossed'] else "未站上"
                            content += f"1日线: {cross_text}1日线\n"
                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考1日线: {ma1['ref']:.2f} / 前值: {ma1['prev']:.2f}\n\n"
                        if 'ma5' in detection_result:
                            ma5 = detection_result['ma5']
                            cross_text = "已站上" if ma5['crossed'] else "未站上"
                            trend_text = "上升" if ma5['uptrend'] else "未上升"
                            content += f"5日线: {cross_text}5日线,5日线{trend_text}\n"
                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考5日线: {ma5['ref']:.2f} / 前值: {ma5['prev']:.2f}\n\n"
                        if 'ma10' in detection_result:
                            ma10 = detection_result['ma10']
                            cross_text = "已站上" if ma10['crossed'] else "未站上"
                            trend_text = "上升" if ma10['uptrend'] else "未上升"
                            content += f"10日线: {cross_text}10日线,10日线{trend_text}\n"
                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考10日线: {ma10['ref']:.2f} / 前值: {ma10['prev']:.2f}\n"
                            if ma10['ref'] > 0:
                                distance_pct = abs((detection_result['current_price'] - ma10['ref']) / ma10['ref']) * 100
                                content += f"  价格距离10日均线: {distance_pct:.2f}%\n"
                            content += "\n"
                        if 'ma20' in detection_result:
                            ma20 = detection_result['ma20']
                            cross_text = "已站上" if ma20['crossed'] else "未站上"
                            trend_text = "上升" if ma20['uptrend'] else "未上升"
                            content += f"20日线: {cross_text}20日线,20日线{trend_text}\n"
                            content += f"  当前价: {detection_result['current_price']:.2f} / 参考20日线: {ma20['ref']:.2f} / 前值: {ma20['prev']:.2f}\n\n"
                except Exception:
                    pass
                # 4. 最近5天涨跌幅
                try:
                    price_changes = self._get_stock_price_changes(stock_code, days=5)
                    if price_changes:
                        content += "="*80 + "\n"
                        content += "【最近5天涨跌幅】\n"
                        content += "="*80 + "\n"
                        for item in price_changes[:5]:
                            content += f"{item['date']}: {item['change_pct']:+.2f}%\n"
                        content += "\n"
                except Exception:
                    pass
                # 5. 股票描述
                # 这里可以添加股票描述内容
                # 6. 游资分析
                # 这里可以添加游资分析内容
                # 保存到资讯
                tab_name = f"持仓综合分析_{stock_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                tab_id = self.create_text_tab(tab_name)
                text_widget = self.text_widgets[tab_id]['widget']
                text_widget.insert("1.0", content)
                # 保存到数据库
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO news_info (tab_name, content, created_at)
                        VALUES (?, ?, ?)
                    ''', (tab_name, content, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"保存到数据库失败: {e}")
                messagebox.showinfo("成功", "已一键保存所有分析内容为资讯", parent=detail_window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=detail_window)
        ttk.Button(button_frame, text="保存为资讯", command=save_to_news_single, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="一键保存", command=save_all_analysis, width=12).pack(side=tk.LEFT, padx=5)
        # 显示基本信息
        content = "【股票信息】\n"
        content += f"股票名称: {stock_name}\n"
        content += f"股票代码: {stock_code}\n"
        content += "股票链接: "
        if stock_urls.get('新浪'):
            content += "新浪 | "
        if stock_urls.get('东方财富'):
            content += "东方财富"
        content += "\n\n"
        # 在最初位置显示股票数据表的逻辑
        if stock_logic_text:
            content += "="*80 + "\n"
            content += "【股票数据表逻辑】\n"
            content += "="*80 + "\n"
            content += stock_logic_text + "\n"
            content += "="*80 + "\n\n"
        # 显示均线检测结果(获取详细检测信息,在逻辑文本之后显示)
        def get_detailed_ma_detection():
            """获取详细的均线检测结果"""
            try:
                # 使用默认数据源进行检测(优先Tushare,失败则AKShare)
                result = self._fetch_recent_daily_closes(
                    stock_code, days=45, source="default", token=self.ts_token, return_volume=False
                )
                if isinstance(result, tuple) and len(result) >= 2:
                    dates, closes = result[:2]
                else:
                    dates, closes = result, []
                if not closes or len(closes) < 3:
                    return None
                latest_price = float(closes[-1])
                # 检测结果字典
                detection_result = {
                    'stock_code': stock_code,
                    'current_price': latest_price,
                    'dates': dates,
                    'closes': closes,
                }
                # 1日线检测
                if len(closes) >= 3:
                    ref_price = float(closes[-2])
                    prev_price = float(closes[-3])
                    crossed = latest_price >= ref_price
                    uptrend = ref_price >= prev_price
                    detection_result['ma1'] = {
                        'ref': ref_price,
                        'prev': prev_price,
                        'crossed': crossed,
                        'uptrend': uptrend
                    }
                # 5日线检测
                if len(closes) >= 7:
                    ma5_values = [float(closes[i]) for i in range(len(closes)-5, len(closes))]
                    ref_ma5 = sum(ma5_values) / len(ma5_values)
                    prev_ma5_values = [float(closes[i]) for i in range(len(closes)-10, len(closes)-5)]
                    prev_ma5 = sum(prev_ma5_values) / len(prev_ma5_values) if len(prev_ma5_values) >= 5 else ref_ma5
                    crossed = latest_price >= ref_ma5
                    uptrend = ref_ma5 >= prev_ma5
                    detection_result['ma5'] = {
                        'ref': ref_ma5,
                        'prev': prev_ma5,
                        'crossed': crossed,
                        'uptrend': uptrend
                    }
                # 10日线检测
                if len(closes) >= 12:
                    ma10_values = [float(closes[i]) for i in range(len(closes)-10, len(closes))]
                    ref_ma10 = sum(ma10_values) / len(ma10_values)
                    prev_ma10_values = [float(closes[i]) for i in range(len(closes)-20, len(closes)-10)]
                    prev_ma10 = sum(prev_ma10_values) / len(prev_ma10_values) if len(prev_ma10_values) >= 10 else ref_ma10
                    crossed = latest_price >= ref_ma10
                    uptrend = ref_ma10 >= prev_ma10
                    detection_result['ma10'] = {
                        'ref': ref_ma10,
                        'prev': prev_ma10,
                        'crossed': crossed,
                        'uptrend': uptrend
                    }
                # 20日线检测
                if len(closes) >= 22:
                    ma20_values = [float(closes[i]) for i in range(len(closes)-20, len(closes))]
                    ref_ma20 = sum(ma20_values) / len(ma20_values)
                    prev_ma20_values = [float(closes[i]) for i in range(len(closes)-40, len(closes)-20)]
                    prev_ma20 = sum(prev_ma20_values) / len(prev_ma20_values) if len(prev_ma20_values) >= 20 else ref_ma20
                    crossed = latest_price >= ref_ma20
                    uptrend = ref_ma20 >= prev_ma20
                    detection_result['ma20'] = {
                        'ref': ref_ma20,
                        'prev': prev_ma20,
                        'crossed': crossed,
                        'uptrend': uptrend
                    }
                return detection_result
            except Exception as e:
                print(f"均线检测失败: {e}")
                return None
        try:
            detection_result = get_detailed_ma_detection()
            market_score = self._get_market_sentiment_score()
            # 判断是否满足开新仓条件(所有均线都满足)
            # 注意:1日线只判断是否站上,不判断是否上升
            if detection_result:
                for ma_key in ['ma1', 'ma5', 'ma10', 'ma20']:
                    if ma_key in detection_result:
                        ma = detection_result[ma_key]
                        # 1日线只判断是否站上,不考虑是否上升
                        if ma_key == 'ma1':
                            if not ma['crossed']:
                                break
                        else:
                            # 其他均线需要同时满足站上且上升
                            if not (ma['crossed'] and ma['uptrend']):
                                break
            # 使用三维一体检测获取完整结果(技术仓位资金检测)
            three_d_result = self._three_dimensional_detection(stock_name, stock_code)
            if three_d_result and three_d_result['success']:
                tech_result = three_d_result['technical']
                position_result = three_d_result['position']
                # 技术维度(均线检测)- 这部分保留在原有位置
                content += "【均线检测详细和结果】\n"
                content += "=" * 50 + "\n"
                content += f"检测结果: {'满足开新仓条件' if tech_result['can_open'] else '不满足开新仓条件'}\n"
                content += f"大盘情绪指数: {market_score}\n"
                if detection_result:
                    content += f"当前价格: {detection_result['current_price']:.2f}\n"
                content += "\n"
                ma_list = []
                ma_status_detail = tech_result['ma_status']
                if ma_status_detail.get('ma1', False):
                    ma_list.append("1日")
                if ma_status_detail.get('ma5', False):
                    ma_list.append("5日")
                if ma_status_detail.get('ma10', False):
                    ma_list.append("10日")
                if ma_status_detail.get('ma20', False):
                    ma_list.append("20日")
                content += f"站上均线: {', '.join(ma_list) if ma_list else '无'}\n"
                if ma_status_detail.get('below_ma20', False):
                    content += "⚠ 股价低于20日线\n"
                content += "\n"
            # 显示详细的均线检测信息(在逻辑文本之后,每条均线单独显示)(在逻辑文本之后)
            if detection_result:
                content += "="*80 + "\n"
                content += "【均线检测结果】\n"
                content += "="*80 + "\n"
                # 1日线(不判断是否上升,只判断是否站上)
                if 'ma1' in detection_result:
                    ma1 = detection_result['ma1']
                    cross_text = "已站上" if ma1['crossed'] else "未站上"
                    status_color = "✓" if ma1['crossed'] else "✗"
                    content += f"{status_color} 1日线: {cross_text}1日线\n"
                    content += f"  当前价: {detection_result['current_price']:.2f} / 参考1日线: {ma1['ref']:.2f} / 前值: {ma1['prev']:.2f}\n\n"
                # 5日线
                if 'ma5' in detection_result:
                    ma5 = detection_result['ma5']
                    cross_text = "已站上" if ma5['crossed'] else "未站上"
                    trend_text = "上升" if ma5['uptrend'] else "未上升"
                    status_color = "✓" if (ma5['crossed'] and ma5['uptrend']) else "✗"
                    content += f"{status_color} 5日线: {cross_text}5日线,5日线{trend_text}\n"
                    content += f"  当前价: {detection_result['current_price']:.2f} / 参考5日线: {ma5['ref']:.2f} / 前值: {ma5['prev']:.2f}\n\n"
                # 10日线
                if 'ma10' in detection_result:
                    ma10 = detection_result['ma10']
                    cross_text = "已站上" if ma10['crossed'] else "未站上"
                    trend_text = "上升" if ma10['uptrend'] else "未上升"
                    status_color = "✓" if (ma10['crossed'] and ma10['uptrend']) else "✗"
                    content += f"{status_color} 10日线: {cross_text}10日线,10日线{trend_text}\n"
                    content += f"  当前价: {detection_result['current_price']:.2f} / 参考10日线: {ma10['ref']:.2f} / 前值: {ma10['prev']:.2f}\n"
                    # 计算并显示10日均线距离
                    if ma10['ref'] > 0:
                        distance_pct = abs((detection_result['current_price'] - ma10['ref']) / ma10['ref']) * 100
                        content += f"  价格距离10日均线: {distance_pct:.2f}%\n"
                    content += "\n"
                # 20日线
                if 'ma20' in detection_result:
                    ma20 = detection_result['ma20']
                    cross_text = "已站上" if ma20['crossed'] else "未站上"
                    trend_text = "上升" if ma20['uptrend'] else "未上升"
                    status_color = "✓" if (ma20['crossed'] and ma20['uptrend']) else "✗"
                    content += f"{status_color} 20日线: {cross_text}20日线,20日线{trend_text}\n"
                    content += f"  当前价: {detection_result['current_price']:.2f} / 参考20日线: {ma20['ref']:.2f} / 前值: {ma20['prev']:.2f}\n\n"
                # 仓位维度(凯利公式)
                content += "【凯利公式计算详细和结果】\n"
                content += "=" * 50 + "\n"
                content += f"凯利百分比: {position_result['kelly_percent']:.2f}%\n"
                content += f"盈亏比(b): {position_result['b']:.2f}\n"
                content += f"胜率(p): {position_result['p']:.2f}\n"
                content += "\n"
                content += "【凯利公式计算逻辑】\n"
                content += "公式: f = (bp - q) / b,其中 q = 1 - p\n"
                content += f"计算: f = ({position_result['b']:.2f} × {position_result['p']:.2f} - {1 - position_result['p']:.2f}) / {position_result['b']:.2f}\n"
                content += f"结果: f = {position_result['kelly_ratio']:.4f} = {position_result['kelly_percent']:.2f}%\n"
                content += "\n"
        except Exception as e:
            content += f"【均线检测】\n检测失败: {e}\n\n"
        # 显示内容
        detail_text.insert(tk.END, content)
        detail_text.config(state=tk.DISABLED)
        detail_window.update()
        # 获取并显示最近5天的涨跌幅
        try:
            price_changes = self._get_stock_price_changes(stock_code, days=5)
            if price_changes:
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, "【最近5天涨跌幅】\n")
                detail_text.insert(tk.END, "=" * 50 + "\n")
                for item in price_changes[:5]:
                    change_pct = item['change_pct']
                    date = item['date']
                    # 根据正负值设置颜色
                    if change_pct > 0:
                        detail_text.insert(tk.END, f"{date}: {change_pct:+.2f}%\n", "red_normal")
                    elif change_pct < 0:
                        detail_text.insert(tk.END, f"{date}: {change_pct:+.2f}%\n", "green_normal")
                    else:
                        detail_text.insert(tk.END, f"{date}: {change_pct:+.2f}%\n")
                detail_text.insert(tk.END, "\n")
                detail_text.config(state=tk.DISABLED)
            else:
                detail_text.config(state=tk.NORMAL)
                detail_text.insert(tk.END, "【最近5天涨跌幅】\n暂无数据\n\n")
                detail_text.config(state=tk.DISABLED)
        except Exception as e:
            detail_text.config(state=tk.NORMAL)
            detail_text.insert(tk.END, f"【最近5天涨跌幅】\n获取失败: {e}\n\n")
            detail_text.config(state=tk.DISABLED)
        def _load_energy_analysis_async():
            """后台拉取 OHLC 并追加能量学分析,避免阻塞界面。"""
            def work():
                try:
                    block = self._compute_energy_analysis_report_text(stock_code, days=60)
                except Exception as ex:
                    block = f"【能量学分析】\n计算失败:{ex}\n"
                block = block.rstrip() + "\n\n"
                def ui():
                    try:
                        detail_text.config(state=tk.NORMAL)
                        _insert_energy_block_with_style(block)
                        detail_text.see(tk.END)
                        detail_text.config(state=tk.DISABLED)
                    except Exception:
                        pass
                detail_window.after(0, ui)
            threading.Thread(target=work, daemon=True).start()
        # 下半部分:日K线图(数据来自Tushare)
        bottom_frame = ttk.LabelFrame(main_paned, text="日K线图(Tushare)", padding=10)
        main_paned.add(bottom_frame, weight=1)
        # 显示加载中
        kline_loading_label = ttk.Label(bottom_frame,
                                       text="正在加载日K线图...",
                                       font=("TkDefaultFont", 12))
        kline_loading_label.pack(expand=True)
        detail_window.update()
        # 在后台线程中加载日K线数据(Tushare)
        def load_kline_data():
            try:
                kline_data = self._get_daily_kline_data_tushare(stock_code, days=60)
                def update_kline_ui():
                    kline_loading_label.destroy()
                    if kline_data:
                        self._draw_daily_kline_chart(bottom_frame, kline_data, stock_name)
                        # 添加量化分析按钮
                        analysis_button_frame = ttk.Frame(bottom_frame)
                        analysis_button_frame.pack(fill=tk.X, padx=10, pady=5)
                        def calculate_kelly():
                            try:
                                result = self._calculate_kelly_position(kline_data, stock_name)
                                self._show_kelly_result_dialog(result, stock_name, detail_window)
                            except Exception as e:
                                messagebox.showerror("错误", f"凯利计算失败: {e}", parent=detail_window)
                        ttk.Button(analysis_button_frame, text="凯利计算", command=calculate_kelly, width=12).pack(side=tk.LEFT, padx=5)
                        def calculate_sharpe():
                            try:
                                result = self._calculate_sharpe_ratio(kline_data, stock_name)
                                self._show_analysis_result_dialog(result, stock_name, "夏普比率分析", detail_window)
                            except Exception as e:
                                messagebox.showerror("错误", f"夏普比率计算失败: {e}", parent=detail_window)
                        ttk.Button(analysis_button_frame, text="夏普比率", command=calculate_sharpe, width=12).pack(side=tk.LEFT, padx=5)
                        def calculate_mean_reversion():
                            try:
                                result = self._calculate_mean_reversion(kline_data, stock_name)
                                self._show_analysis_result_dialog(result, stock_name, "均值回归分析", detail_window)
                            except Exception as e:
                                messagebox.showerror("错误", f"均值回归计算失败: {e}", parent=detail_window)
                        ttk.Button(analysis_button_frame, text="均值回归", command=calculate_mean_reversion, width=12).pack(side=tk.LEFT, padx=5)
                    else:
                        error_label = ttk.Label(bottom_frame,
                                               text="无法获取日K线数据(请检查Tushare配置)",
                                               font=("TkDefaultFont", 12),
                                               foreground="red")
                        error_label.pack(expand=True)
                detail_window.after(0, update_kline_ui)
            except Exception as e:
                def show_error(e=e):
                    kline_loading_label.destroy()
                    error_label = ttk.Label(bottom_frame,
                                           text=f"加载日K线图失败: {e}",
                                           font=("TkDefaultFont", 12),
                                           foreground="red")
                    error_label.pack(expand=True)
                detail_window.after(0, show_error)
                import traceback
                traceback.print_exc()
        threading.Thread(target=load_kline_data, daemon=True).start()


    def _open_holding_calculator(self):
        """打开持仓计算独立程序"""
        try:
            import os
            import subprocess
            import sys
            # 获取当前脚本所在目录
            os.path.dirname(os.path.abspath(__file__))
            # 支持打包后的环境查找脚本文件
            script_name = "stockchichang.py"
            calculator_path = None
            # 1. 尝试使用 PyInstaller 打包后的路径(sys._MEIPASS)
            if hasattr(sys, '_MEIPASS'):
                meipass_path = os.path.join(sys._MEIPASS, script_name)
                if os.path.exists(meipass_path):
                    calculator_path = meipass_path
            # 2. 尝试可执行文件所在目录的 _internal 子目录
            if not calculator_path and hasattr(sys, 'frozen'):
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                internal_path = os.path.join(exe_dir, '_internal', script_name)
                if os.path.exists(internal_path):
                    calculator_path = internal_path
            # 3. 尝试与主程序同目录
            if not calculator_path:
                same_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
                if os.path.exists(same_dir_path):
                    calculator_path = same_dir_path
            # 4. 尝试当前工作目录
            if not calculator_path:
                cwd_path = os.path.join(os.getcwd(), script_name)
                if os.path.exists(cwd_path):
                    calculator_path = cwd_path
            # 如果文件存在,运行持仓计算器
            if calculator_path and os.path.exists(calculator_path):
                is_frozen = hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS')
                if is_frozen:
                    # 打包后的环境:直接导入并执行模块
                    try:
                        import importlib.util
                        module_name = os.path.splitext(script_name)[0]
                        spec = importlib.util.spec_from_file_location(module_name, calculator_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            # 在新线程中执行
                            def run_calculator():
                                try:
                                    spec.loader.exec_module(module)
                                except Exception as e:
                                    messagebox.showerror("错误", f"执行持仓计算程序失败: {e}", parent=self.root)
                            threading.Thread(target=run_calculator, daemon=True).start()
                        else:
                            messagebox.showerror("错误", f"无法加载持仓计算模块: {script_name}", parent=self.root)
                    except Exception as e:
                        messagebox.showerror("错误", f"启动持仓计算程序失败: {e}", parent=self.root)
                else:
                    # 开发环境:使用 subprocess
                    subprocess.Popen(
                        [sys.executable, calculator_path],
                        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0,
                        encoding='utf-8',
                        errors='replace'
                    )
            else:
                error_msg = f"未找到持仓计算程序:{script_name}\n\n"
                if hasattr(sys, '_MEIPASS'):
                    error_msg += f"已尝试路径:\n1. {os.path.join(sys._MEIPASS, script_name)}\n"
                if hasattr(sys, 'frozen'):
                    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                    error_msg += f"2. {os.path.join(exe_dir, '_internal', script_name)}\n"
                error_msg += f"3. {os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)}\n"
                error_msg += f"4. {os.path.join(os.getcwd(), script_name)}\n"
                messagebox.showerror("错误", error_msg, parent=self.root)
        except Exception as e:
            messagebox.showerror("错误", f"打开持仓计算程序失败:{e}", parent=self.root)


    def _calculate_position_advice(self, market_ctx, buy_signals, sell_signals, risk_pass, dj_score, p_phase):
        """结合大盘+个股信号给出仓位/买卖建议
        返回: {'action': str, 'position_pct': int, 'reasoning': str}
        """
        market_cap = market_ctx.get("position_cap", 50)
        market_sentiment = market_ctx.get("sentiment", "未知")
        # 基础仓位:根据个股买卖信号
        if buy_signals >= 3:
            base_pos = 70
            base_action = "买入"
        elif buy_signals >= 2:
            base_pos = 40
            base_action = "轻仓买入"
        elif buy_signals >= 1:
            base_pos = 20
            base_action = "试探性买入"
        elif sell_signals >= 3:
            base_pos = 0
            base_action = "卖出/清仓"
        elif sell_signals >= 2:
            base_pos = 10
            base_action = "减仓"
        else:
            base_pos = 30
            base_action = "持有/观望"
        # 风控未通过 → 强制不买入
        if not risk_pass:
            base_pos = 0
            base_action = "风控未通过,不操作"
        # P3狂热期 → 降低仓位
        if p_phase == "P3":
            base_pos = min(base_pos, 15)
            base_action = base_action.replace("买入", "减仓" if "买入" in base_action else base_action)
        # P0衰退期 → 不加仓
        elif p_phase == "P0":
            base_pos = min(base_pos, 20)
        # 段基评分修正
        if dj_score >= 80:
            base_pos = min(int(base_pos * 1.1), 90)
        elif dj_score < 50:
            base_pos = int(base_pos * 0.7)
        # 大盘仓位上限约束:个股仓位不得超过大盘允许的上限
        final_pos = min(base_pos, market_cap)
        # 构建推理过程
        reasoning_parts = []
        reasoning_parts.append(f"大盘情绪{market_sentiment}→仓位上限{market_cap}%")
        reasoning_parts.append(f"个股买入信号{buy_signals}/卖出{sell_signals}→基础仓位{base_pos}%")
        if not risk_pass:
            reasoning_parts.append("风控未通过→强制仓位0%")
        if p_phase == "P3":
            reasoning_parts.append("P3狂热期→仓位上限15%")
        elif p_phase == "P0":
            reasoning_parts.append("P0衰退期→不加仓")
        if dj_score >= 80:
            reasoning_parts.append(f"段基{dj_score}分(优秀)→仓位上浮10%")
        elif dj_score < 50:
            reasoning_parts.append(f"段基{dj_score}分(偏低)→仓位下调30%")
        reasoning_parts.append(f"大盘上限{market_cap}% vs 个股{base_pos}%→取较小值={final_pos}%")
        return {
            "action": base_action,
            "position_pct": final_pos,
            "reasoning": " → ".join(reasoning_parts),
        }


    def _show_add_position_dialog(self):
        """💰 是否加仓:输入股票 → K线技术图 + AI 加仓分析(凯利公式/正金字塔/本金铁律)"""
        import threading
        import tkinter as tk
        from tkinter import scrolledtext
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
        win = self._safe_toplevel(self.root)
        win.title("💰 是否加仓 · 分析器")
        win.geometry("1400x920")
        win.transient(self.root)
        # ============ 1 顶部说明 Banner ============
        banner = tk.Frame(win, bg="#2E7D32", height=80)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)
        banner_inner = tk.Frame(banner, bg="#2E7D32")
        banner_inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        tk.Label(banner_inner, text="💰 是否加仓 · 智能分析器",
                 font=("Microsoft YaHei", 17, "bold"),
                 bg="#2E7D32", fg="#FFFFFF").pack(anchor="w")
        desc = (
            "🎯 输入股票代码 → 自动计算 MA/RSI/MACD/布林带 → 规则引擎评分"
            " + AI 智能建议(凯利公式 · 正金字塔 · 本金铁律)"
        )
        tk.Label(banner_inner, text=desc,
                 font=("Microsoft YaHei", 11),
                 bg="#2E7D32", fg="#E8F5E9").pack(anchor="w")
        hint = "🟢 建议加仓 (≥+6)   ⚪ 中性观望 (-2~+5)   🔴 建议不加 (≤-2)"
        tk.Label(banner_inner, text=hint,
                 font=("Microsoft YaHei", 10, "bold"),
                 bg="#2E7D32", fg="#FFD54F").pack(anchor="w")
        # ============ 2 输入栏 ============
        top = ttk.LabelFrame(win, text="📝 输入参数", padding=8)
        top.pack(fill=tk.X, padx=5, pady=(5, 2))
        # 第1行:主要参数
        row1 = ttk.Frame(top)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="股票代码/名称:", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT)
        code_var = tk.StringVar()
        code_entry = ttk.Entry(row1, textvariable=code_var, width=18, font=("TkDefaultFont", 11))
        code_entry.pack(side=tk.LEFT, padx=5)
        code_entry.focus_set()
        # 快捷按钮
        for quick_code, quick_name in [("600519", "茅台"), ("000858", "五粮液"),
                                       ("300750", "宁德时代"), ("002594", "比亚迪"),
                                       ("601318", "平安")]:
            ttk.Button(row1, text=f"{quick_name}", width=6,
                       command=lambda c=quick_code: (code_var.set(c), _on_analyze())
                       ).pack(side=tk.LEFT, padx=2)
        analyze_btn = ttk.Button(row1, text="🔍 执行分析", width=12)
        analyze_btn.pack(side=tk.LEFT, padx=15)
        status_var = tk.StringVar(value="💡 输入股票代码,或点上方快捷按钮")
        ttk.Label(row1, textvariable=status_var, font=("TkDefaultFont", 10),
                  foreground="#666").pack(side=tk.LEFT, fill=tk.X, expand=True)
        # 第2行:可选参数
        row2 = ttk.Frame(top)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="(可选)持仓成本:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        cost_var = tk.StringVar(value="")
        ttk.Entry(row2, textvariable=cost_var, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Label(row2, text="  - 输入后在K线上画橙色成本线", font=("TkDefaultFont", 9), foreground="#888").pack(side=tk.LEFT)
        ttk.Label(row2, text="   当前仓位%:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        pos_var = tk.StringVar(value="5")
        ttk.Entry(row2, textvariable=pos_var, width=5).pack(side=tk.LEFT, padx=3)
        ttk.Label(row2, text="  - 用于检查本金铁律(单股≤15%)", font=("TkDefaultFont", 9), foreground="#888").pack(side=tk.LEFT)
        ttk.Label(row2, text="   历史天数:", font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        days_var = tk.IntVar(value=250)
        ttk.Spinbox(row2, from_=60, to=500, increment=10, width=5, textvariable=days_var).pack(side=tk.LEFT, padx=3)
        ttk.Label(row2, text="  - 默认250天≈1年", font=("TkDefaultFont", 9), foreground="#888").pack(side=tk.LEFT)
        # ============ 3 主体:左图右文 ============
        body = ttk.Panedwindow(win, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))
        # ---- 左:matplotlib 四图 ----
        chart_frame = ttk.LabelFrame(body, text="📈 技术分析图表", padding=3)
        body.add(chart_frame, weight=3)
        fig = Figure(figsize=(8, 9), dpi=100, facecolor="#f5f5f5")
        ax_price = fig.add_subplot(411)
        ax_vol = fig.add_subplot(412, sharex=ax_price)
        ax_macd = fig.add_subplot(413, sharex=ax_price)
        ax_rsi = fig.add_subplot(414, sharex=ax_price)
        fig.subplots_adjust(hspace=0.08, top=0.96, bottom=0.05)
        # 初始占位提示
        for ax in [ax_price, ax_vol, ax_macd, ax_rsi]:
            ax.text(0.5, 0.5, "⏳ 等待分析...\n输入股票代码后点「执行分析」",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=12, color="#999")
            ax.set_xticks([]); ax.set_yticks([])
            ax.spines[["top", "right", "bottom", "left"]].set_visible(False)
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, chart_frame).update()
        # ---- 右:AI 分析报告 ----
        report_frame = ttk.Frame(body)
        body.add(report_frame, weight=2)
        report_hdr = ttk.LabelFrame(report_frame, text="📋 加仓分析报告", padding=3)
        report_hdr.pack(fill=tk.BOTH, expand=True)
        report_txt = scrolledtext.ScrolledText(
            report_hdr, wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg="#1e1e1e", fg="#d4d4d4", padx=8, pady=8)
        report_txt.pack(fill=tk.BOTH, expand=True)
        # 初始占位提示
        report_txt.insert("1.0", """
╔══════════════════════════════════════════════╗
║                                              ║
║   📖  使用说明                                ║
║                                              ║
║   1️⃣  在左上方输入股票代码(如 600519)        ║
║      或直接输入股票名称                         ║
║                                              ║
║   2️⃣  可选:填写持仓成本价(在K线上显示)       ║
║              和当前仓位百分比                   ║
║                                              ║
║   3️⃣  点击 🔍执行分析 或 按 回车键              ║
║                                              ║
║   4️⃣  查看结果:                               ║
║      📊 左图 = K线+均线+布林+MACD+RSI           ║
║      📋 右文 = 规则引擎评分 + AI详细报告         ║
║                                              ║
║   🎯 规则引擎评分:                             ║
║      ≥ +6  → 🟢 建议加仓                        ║
║      -2~+5 → ⚪ 中性观望                        ║
║      ≤ -2  → 🔴 建议不加                        ║
║                                              ║
║   ⚠️  所有分析仅供参考,不构成投资建议            ║
║                                              ║
╚══════════════════════════════════════════════╝
""".strip())
        report_txt.config(state=tk.NORMAL)
        self._enable_text_copy_menu(report_txt, readonly=True)
        def _fetch_daily(code, days=250):
            """拉取A股历史日线 - 三级降级:东财 → 腾讯 → 新浪"""
            import akshare as ak
            import pandas as pd
            end = pd.Timestamp.now().strftime("%Y%m%d")
            start = (pd.Timestamp.now() - pd.Timedelta(days=int(days) + 30)).strftime("%Y%m%d")
            def _try_em():
                """1 东方财富源(交易时段首选)"""
                for sym in [code, code + ".SH", code + ".SZ"]:
                    try:
                        df = ak.stock_zh_a_hist(
                            symbol=sym, period="daily",
                            start_date=start, end_date=end, adjust="qfq")
                        if df is not None and len(df) >= 60:
                            return df.tail(int(days))
                    except Exception:
                        continue
                return None
            def _try_tx():
                """2 腾讯源(非交易时段兜底)"""
                # 沪市60开头 → sh, 深市00/30开头 → sz
                prefix = "sh" if code.startswith("6") else "sz"
                for sym in [prefix + code, code]:
                    try:
                        df = ak.stock_zh_a_hist_tx(
                            symbol=sym, start_date=start,
                            end_date=end, adjust="qfq")
                        if df is not None and len(df) >= 60:
                            # 列名映射: date/open/close/high/low/amount → 东财格式
                            df = df.rename(columns={
                                "date": "日期", "open": "开盘",
                                "close": "收盘", "high": "最高",
                                "low": "最低", "amount": "成交额",
                            })
                            # 腾讯源缺成交量列 - 用 amount/close 近似估算(单位不重要,比例一致就行)
                            df["成交量"] = df["成交额"] / df["收盘"]
                            df["日期"] = pd.to_datetime(df["日期"])
                            return df[["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]].tail(int(days))
                    except Exception:
                        continue
                return None
            def _try_sina():
                """3 新浪源(终极兜底)"""
                prefix = "sh" if code.startswith("6") else "sz"
                for sym in [prefix + code, code]:
                    try:
                        df = ak.stock_zh_a_daily(
                            symbol=sym, start_date=start,
                            end_date=end, adjust="qfq")
                        if df is not None and len(df) >= 60:
                            # 新浪列: date/open/high/low/close/volume/amount...
                            df = df.rename(columns={
                                "date": "日期", "open": "开盘",
                                "close": "收盘", "high": "最高",
                                "low": "最低", "volume": "成交量",
                                "amount": "成交额",
                            })
                            if "成交量" not in df.columns and "成交额" in df.columns:
                                df["成交量"] = df["成交额"] / df["收盘"]
                            df["日期"] = pd.to_datetime(df["日期"])
                            cols = [c for c in ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"] if c in df.columns]
                            return df[cols].tail(int(days))
                    except Exception:
                        continue
                return None
            df = _try_em()
            if df is None:
                df = _try_tx()
            if df is None:
                df = _try_sina()
            return df
        def _parse_code(raw):
            """解析输入 → (code, name)"""
            raw = raw.strip()
            if not raw:
                return None, None
            # 全局字典:STOCK_CODES_DICT[code] = name, STOCK_NAME_TO_CODE[name] = code
            # 先尝试:6位数字 → 当代码查字典
            if raw.isdigit() and len(raw) == 6:
                return raw, STOCK_CODES_DICT.get(raw, raw)
            # 输入是股票名称 → 反查代码
            if raw in STOCK_NAME_TO_CODE:
                return STOCK_NAME_TO_CODE[raw], raw
            # 输入是代码但可能带前缀/后缀 → 提取6位数字
            import re as _re
            m = _re.search(r"(\d{6})", raw)
            if m:
                code6 = m.group(1)
                return code6, STOCK_CODES_DICT.get(code6, code6)
            return None, None
        def _draw_chart(df, stock_name, cost=None):
            """画四图K线"""
            nonlocal canvas, ax_price, ax_vol, ax_macd, ax_rsi, fig
            fig.clear()
            ax_price = fig.add_subplot(411)
            ax_vol = fig.add_subplot(412, sharex=ax_price)
            ax_macd = fig.add_subplot(413, sharex=ax_price)
            ax_rsi = fig.add_subplot(414, sharex=ax_price)
            fig.subplots_adjust(hspace=0.06, top=0.96, bottom=0.06)
            closes = df["收盘"].astype(float).values
            highs = df["最高"].astype(float).values
            lows = df["最低"].astype(float).values
            df["开盘"].astype(float).values
            volumes = df["成交量"].astype(float).values
            dates = df["日期"].astype(str).values
            x = np.arange(len(closes))
            # 均线
            ma5 = self._calc_ma(closes, 5)
            ma10 = self._calc_ma(closes, 10)
            ma20 = self._calc_ma(closes, 20)
            ma60 = self._calc_ma(closes, 60)
            boll_mid, boll_up, boll_low = self._calc_bollinger(closes, 20, 2)
            dif, dea, hist = self._calc_macd_full(closes)
            rsi = self._calc_rsi(closes, 14)
            # ---- 上图:K线 + 均线 + 布林 ----
            ax_price.plot(x, closes, color="#333", linewidth=1)
            ax_price.plot(x, ma5, color="#E53935", linewidth=0.9, label="MA5")
            ax_price.plot(x, ma10, color="#1E88E5", linewidth=0.9, label="MA10")
            ax_price.plot(x, ma20, color="#43A047", linewidth=0.9, label="MA20")
            ax_price.plot(x, ma60, color="#FB8C00", linewidth=0.9, label="MA60")
            ax_price.plot(x, boll_up, color="#9E9E9E", linewidth=0.6, linestyle="--")
            ax_price.plot(x, boll_low, color="#9E9E9E", linewidth=0.6, linestyle="--")
            ax_price.fill_between(x, boll_up, boll_low, alpha=0.05, color="#9E9E9E")
            # 持仓成本线
            if cost:
                try:
                    c = float(cost)
                    ax_price.axhline(c, color="#FF6F00", linestyle=":", linewidth=1.2,
                                     label=f"成本 {c:.2f}")
                except Exception:
                    pass
            # 支撑阻力
            try:
                levels = self._compute_daily_support_resistance_line_prices(df)
                for lvl in (levels or []):
                    ax_price.axhline(float(lvl), color="#7B1FA2", linestyle=":", linewidth=0.5, alpha=0.6)
            except Exception:
                pass
            last = closes[-1]
            chg = closes[-1] - closes[-2] if len(closes) > 1 else 0
            ax_price.set_title(f"{stock_name}  |  现价={last:.2f}  |  昨收={closes[-2]:.2f}  |  {chg:+.2f}",
                               fontsize=12, fontweight="bold")
            ax_price.legend(loc="upper left", fontsize=8, ncol=4)
            ax_price.grid(True, alpha=0.2)
            ax_price.set_ylabel("价格")
            # ---- 量能 ----
            vol_colors = ["#C62828" if closes[i] >= closes[i - 1] else "#2E7D32"
                          for i in range(1, len(closes))]
            ax_vol.bar(x[1:], volumes[1:], color=vol_colors, width=0.8)
            ax_vol.grid(True, alpha=0.2)
            ax_vol.set_ylabel("量")
            # ---- MACD ----
            bar_colors = ["#C62828" if h >= 0 else "#2E7D32" for h in hist]
            ax_macd.bar(x, hist, color=bar_colors, width=0.8, alpha=0.6)
            ax_macd.plot(x, dif, color="#FF6F00", linewidth=0.9, label="DIF")
            ax_macd.plot(x, dea, color="#1565C0", linewidth=0.9, label="DEA")
            ax_macd.axhline(0, color="gray", linestyle="--", linewidth=0.6)
            ax_macd.legend(loc="upper left", fontsize=8)
            ax_macd.grid(True, alpha=0.2)
            ax_macd.set_ylabel("MACD")
            # ---- RSI ----
            ax_rsi.plot(x, rsi, color="#7B1FA2", linewidth=1.1)
            ax_rsi.axhline(70, color="#C62828", linestyle="--", linewidth=0.6, label="70超买")
            ax_rsi.axhline(30, color="#2E7D32", linestyle="--", linewidth=0.6, label="30超卖")
            ax_rsi.fill_between(x, 70, 100, alpha=0.08, color="#C62828")
            ax_rsi.fill_between(x, 0, 30, alpha=0.08, color="#2E7D32")
            ax_rsi.legend(loc="upper left", fontsize=8)
            ax_rsi.set_ylim(0, 100)
            ax_rsi.grid(True, alpha=0.2)
            ax_rsi.set_ylabel("RSI")
            # X轴时间标签
            step = max(1, len(x) // 15)
            ax_rsi.set_xticks(x[::step])
            ax_rsi.set_xticklabels([d[:10] for d in dates[::step]], rotation=45, fontsize=7)
            canvas.draw()
            # 返回技术指标快照(用于 AI prompt)
            return {
                "last_price": float(closes[-1]),
                "ma5": float(ma5[-1]) if not np.isnan(ma5[-1]) else None,
                "ma10": float(ma10[-1]) if not np.isnan(ma10[-1]) else None,
                "ma20": float(ma20[-1]) if not np.isnan(ma20[-1]) else None,
                "ma60": float(ma60[-1]) if not np.isnan(ma60[-1]) else None,
                "boll_upper": float(boll_up[-1]) if not np.isnan(boll_up[-1]) else None,
                "boll_mid": float(boll_mid[-1]) if not np.isnan(boll_mid[-1]) else None,
                "boll_lower": float(boll_low[-1]) if not np.isnan(boll_low[-1]) else None,
                "rsi": float(rsi[-1]) if not np.isnan(rsi[-1]) else None,
                "macd_dif": float(dif[-1]),
                "macd_dea": float(dea[-1]),
                "macd_hist": float(hist[-1]),
                "high_60": float(np.max(highs[-60:])),
                "low_60": float(np.min(lows[-60:])),
                "vol_last": float(volumes[-1]),
                "vol_avg_20": float(np.mean(volumes[-20:])),
                "chg_5d": float((closes[-1] / closes[-5] - 1) * 100) if len(closes) > 5 else 0,
                "chg_20d": float((closes[-1] / closes[-20] - 1) * 100) if len(closes) > 20 else 0,
                "chg_60d": float((closes[-1] / closes[-60] - 1) * 100) if len(closes) > 60 else 0,
            }
        def _build_add_position_prompt(stock_code, stock_name, df, tech_snap, cost, current_pos):
            """按 SKILL.md 框架构建 AI prompt"""
            import json
            # 最近K线摘要
            tail = df.tail(10)[["日期", "开盘", "最高", "最低", "收盘", "成交量"]].to_dict("records")
            kline_json = json.dumps(tail, ensure_ascii=False, indent=2)
            tech_json = json.dumps(tech_snap, ensure_ascii=False, indent=2)
            return f"""你是专业的A股加仓分析顾问。请严格按照以下 SKILL.md 框架输出分析报告。
## 股票
名称: {stock_name}
代码: {stock_code}
持仓成本: {cost or '(未输入)'}
当前仓位: {current_pos or '5'}%
## 技术指标快照
```json
{tech_json}
```
## 近10日K线
```json
{kline_json}
```
## 请按以下框架输出
⚠️ 前置警示(财富转移 + 本金铁律)
  - 先讲清楚 2014-2015 A股牛熊散户亏2500亿的真相
  - 明确本金防御三条铁律(单股≤15%、利润隔离、禁止亏损加仓)
📌 核心结论(趋势判断 + 加仓建议 + 逻辑)
  - 一句话说清楚能不能加仓、加多少
💹 当前行情(价/量/均线多空排列)
📊 技术位(3级支撑 + 2级阻力 + RSI/MACD/布林解读)
📐 凯利仓位(估算胜率/盈亏比 → 半凯利推荐百分比)
🎯 加仓方案A(稳健分批)+ 方案B(激进),每批必带止损价
💰 本金防御检查(三条合规确认)
⚠️ 风险提示
💡 操作纪律
要求:
1. 具体数字要精确(如"第一支撑位 28.50"而不是"支撑位在28块左右")
2. 止损位必须有价格,不能模糊
3. 凯利公式里的胜率/盈亏比必须根据近60日数据估算
4. 不要输出 markdown 表格,用列表和编号即可
"""
        _ai_busy = [False]
        def _on_analyze():
            try:
                if _ai_busy[0]:
                    status_var.set("⚠️ AI 分析正在进行中,请稍候...")
                    return
                raw = code_var.get().strip()
                code, name = _parse_code(raw)
                if not code:
                    messagebox.showwarning("提示", "请输入有效的 6 位股票代码\n支持数字代码(如600519)", parent=win)
                    return
                _ai_busy[0] = True
                analyze_btn.config(state=tk.DISABLED)
                status_var.set(f"⏳ 拉取 {name}({code}) 日线数据...")
                report_txt.delete("1.0", tk.END)
                report_txt.insert(tk.END, "⏳ 数据加载中,请稍候...\n")
                cost = cost_var.get().strip() or None
                pos = pos_var.get().strip() or "5"
                def work():
                    try:
                        df = _fetch_daily(code, days_var.get())
                        if df is None or len(df) < 60:
                            win.after(0, lambda: _show_err(f"❌ 数据获取失败:{name}({code})\n可能原因:1 代码错误 2 非交易时段东方财富接口被掐断 3 网络不通\n\n请稍后重试,或检查网络连接"))
                            return
                        win.after(0, lambda: status_var.set(f"✅ {name}({code}) 日线 {len(df)} 条 - 计算技术指标..."))
                        tech = _draw_chart(df, name, cost)
                        win.after(0, lambda: status_var.set("⏳ AI 分析中(约10-30秒)..."))
                        prompt = _build_add_position_prompt(code, name, df, tech, cost, pos)
                        _system = (
                            "你是专业的A股加仓分析顾问,严格按 SKILL.md 框架输出。"
                            "结论先行,数字精确,止损有价格,仓位有凯利依据。"
                        )
                        result = self.call_ai_model(prompt, _system, max_tokens=4096)
                        win.after(0, lambda: _show_result(result, tech, name))
                    except Exception as e:
                        import traceback
                        win.after(0, lambda e=e: _show_err(f"❌ 后台线程异常\n{e}\n\n{traceback.format_exc()}"))
                def _show_err(msg):
                    report_txt.delete("1.0", tk.END)
                    report_txt.insert("1.0", msg)
                    _ai_busy[0] = False
                    analyze_btn.config(state=tk.NORMAL)
                    status_var.set("❌ 失败")
                def _rule_engine(tech):
                    """
                    规则引擎:纯代码判断「能不能加仓」- 不依赖 AI。
                    返回 (verdict, score, max_score, reasons, warnings)
                      verdict: 'YES'/'NO'/'NEUTRAL'
                      score/max_score: 加分制
                      reasons: 做多理由列表
                      warnings: 减分/警告列表
                    """
                    score = 0
                    reasons = []
                    warnings = []
                    L = tech["last_price"]
                    ma5, ma10, ma20, _ma60 = tech["ma5"], tech["ma10"], tech["ma20"], tech["ma60"]
                    rsi = tech["rsi"]
                    dif, dea, hist = tech["macd_dif"], tech["macd_dea"], tech["macd_hist"]
                    boll_low, boll_mid, boll_up = tech["boll_lower"], tech["boll_mid"], tech["boll_upper"]
                    high60, low60 = tech["high_60"], tech["low_60"]
                    # ---- 1. 均线排列(±3)----
                    if ma5 and ma10 and ma20:
                        if ma5 > ma10 > ma20:       # 多头排列
                            score += 3; reasons.append("MA5>MA10>MA20 多头排列(+3)")
                        elif ma5 < ma10 < ma20:     # 空头排列
                            score -= 3; warnings.append("MA5<MA10<MA20 空头排列(-3)")
                        else:
                            reasons.append("均线纠缠(0)")
                    # ---- 2. RSI 位置(±2)----
                    if rsi is not None:
                        if rsi < 30:
                            score += 2; reasons.append(f"RSI={rsi:.0f} 超卖区,加仓好时机(+2)")
                        elif rsi < 45:
                            score += 1; reasons.append(f"RSI={rsi:.0f} 偏低,有上行空间(+1)")
                        elif rsi > 70:
                            score -= 2; warnings.append(f"RSI={rsi:.0f} 超买区,追高风险(-2)")
                        elif rsi > 55:
                            score -= 1; warnings.append(f"RSI={rsi:.0f} 偏高,谨慎(-1)")
                    # ---- 3. MACD 状态(±2)----
                    if dif is not None and dea is not None:
                        if dif > dea and hist > 0:
                            score += 2; reasons.append("MACD金叉 柱正(+2)")
                        elif dif > dea and hist < 0:
                            score += 1; reasons.append("MACD底背离 柱缩(+1)")
                        elif dif < dea and hist < 0:
                            score -= 2; warnings.append("MACD死叉 柱负(-2)")
                        elif dif < dea and hist > 0:
                            score -= 1; warnings.append("MACD顶背离(-1)")
                    # ---- 4. 布林位置(±2)----
                    if boll_low and boll_up and boll_mid:
                        boll_range = boll_up - boll_low
                        if boll_range > 0:
                            bpos = (L - boll_low) / boll_range
                            if bpos < 0.1:
                                score += 2; reasons.append("触及布林下轨(+2)")
                            elif bpos < 0.3:
                                score += 1; reasons.append("布林偏低(+1)")
                            elif bpos > 0.9:
                                score -= 2; warnings.append("触及布林上轨,追高风险(-2)")
                            elif bpos > 0.7:
                                score -= 1; warnings.append("布林偏高(-1)")
                    # ---- 5. 距60日位置(±2)----
                    if high60 and low60 and high60 > low60:
                        zpos = (L - low60) / (high60 - low60)
                        if zpos < 0.2:
                            score += 2; reasons.append(f"距60日低点{zpos*100:.0f}%,超跌(+2)")
                        elif zpos < 0.4:
                            score += 1; reasons.append("60日位置偏低(+1)")
                        elif zpos > 0.85:
                            score -= 2; warnings.append(f"距60日高点仅{(1-zpos)*100:.0f}%,高位(-2)")
                        elif zpos > 0.7:
                            score -= 1; warnings.append("60日位置偏高(-1)")
                    # ---- 6. 量比(±1)----
                    vol_ratio = tech["vol_last"] / tech["vol_avg_20"] if tech["vol_avg_20"] > 0 else 1.0
                    if vol_ratio < 0.7:
                        score += 1; reasons.append("缩量调整后可能放量(+1)")
                    elif vol_ratio > 2.0:
                        score -= 1; warnings.append("爆量上涨后可能回调(-1)")
                    max_score = 12
                    if score >= 6:
                        verdict = "YES"
                    elif score <= -2:
                        verdict = "NO"
                    else:
                        verdict = "NEUTRAL"
                    return verdict, score, max_score, reasons, warnings
                def _show_result(result, tech, name):
                    try:
                        report_txt.delete("1.0", tk.END)
                        # === 1 规则引擎结论 ===
                        verdict, score, max_s, reasons, warnings = _rule_engine(tech)
                        verdict_map = {
                            "YES": ("✅ 建议加仓", "#C62828", "👍 综合技术面支持加仓"),
                            "NO": ("❌ 建议观望/不加", "#2E7D32", "⚠️ 技术面不支持加仓,等回调或趋势确认"),
                            "NEUTRAL": ("⚖️ 中性,可轻仓试探", "#FF6F00", "🤔 多空因素交织,建议不超过5%轻仓"),
                        }
                        v_text, _v_color, v_desc = verdict_map[verdict]
                        verdict_block = f"""
{'═'*60}
  {v_text}  |  规则引擎评分: {score:+d} / {max_s}
  {v_desc}
{'═'*60}
📈 做多理由:
"""
                        for r in reasons:
                            verdict_block += f"  ✅ {r}\n"
                        if not reasons:
                            verdict_block += "  (无明显做多信号)\n"
                        verdict_block += "\n⚠️ 警告/减分:\n"
                        for w in warnings:
                            verdict_block += f"  ❌ {w}\n"
                        if not warnings:
                            verdict_block += "  (无明显警告)\n"
                        verdict_block += "\n"
                        # === 2 技术快照 ===
                        def _fmt(v, fmt=".2f"):
                            if v is None: return "N/A"
                            return f"{v:{fmt}}"
                        vol_ratio_str = f"{tech['vol_last']/tech['vol_avg_20']:.2f}" if tech['vol_avg_20']>0 else "N/A"
                        snap = f"""📊 {name} 技术快照
  现价: {tech['last_price']:.2f}  |  5日: {tech['chg_5d']:+.2f}%  |  20日: {tech['chg_20d']:+.2f}%  |  60日: {tech['chg_60d']:+.2f}%
  MA5={_fmt(tech['ma5'])}  MA10={_fmt(tech['ma10'])}  MA20={_fmt(tech['ma20'])}  MA60={_fmt(tech['ma60'])}
  布林: {_fmt(tech['boll_lower'])} ~ {_fmt(tech['boll_mid'])} ~ {_fmt(tech['boll_upper'])}
  RSI(14)={_fmt(tech['rsi'],'.1f')}  |  MACD DIF={_fmt(tech['macd_dif'],'.3f')} DEA={_fmt(tech['macd_dea'],'.3f')} 柱={_fmt(tech['macd_hist'],'.3f')}
  60日高={tech['high_60']:.2f}  60日低={tech['low_60']:.2f}  |  量比={vol_ratio_str}
"""
                        # === 3 AI 详细分析 ===
                        report_txt.insert("1.0", verdict_block + "\n" + snap + "\n" + (result or "AI 未返回结果"))
                        _ai_busy[0] = False
                        analyze_btn.config(state=tk.NORMAL)
                        status_var.set(f"✅ {v_text} - 仅供参考,不构成投资建议")
                    except Exception as e:
                        import traceback
                        _show_err(f"❌ 结果渲染异常\n{e}\n\n{traceback.format_exc()}")
                threading.Thread(target=work, daemon=True).start()
            except Exception as e:
                import traceback
                err = f"❌ 【界面层异常】\n{e}\n\n{traceback.format_exc()}"
                # 调试:写到文件
                try:
                    with open("/tmp/addpos_error.log", "w") as _f:
                        _f.write(err)
                except Exception:
                    pass
                try:
                    report_txt.delete("1.0", tk.END)
                    report_txt.insert("1.0", err)
                except Exception:
                    pass
                try:
                    status_var.set("❌ 界面异常")
                    _ai_busy[0] = False
                    analyze_btn.config(state=tk.NORMAL)
                except Exception:
                    pass
        analyze_btn.config(command=_on_analyze)
        code_entry.bind("<Return>", lambda _e: _on_analyze())


    def _show_portfolio_dashboard(self):
        """📊 持股风险仪表盘: 从GUI4个持仓标签页拿股 → 左下列表 + 右侧AI总体分析"""
        import threading
        import tkinter as tk
        from datetime import datetime
        from tkinter import scrolledtext

        import tushare as _ts_pro
        # ===== 1. 定义所有可选的持仓标签页 (group 索引 + 名称 + 默认勾选) =====
        ALL_GROUPS = [
            (1,  "自持股",       True),
            (2,  "龙头股",       True),
            (4,  "Main",         True),
            (6,  "同花顺",       True),
            (5,  "持仓历史股",   False),
            (3,  "15Min",        False),
            (7,  "标签1",        False),
            (8,  "标签2",        False),
            (9,  "标签3",        False),
            (10, "标签4",        False),
            (11, "标签5",        False),
            (12, "标签6",        False),
            (13, "标签7",        False),
            (14, "标签8",        False),
        ]
        def _count_group_stocks(gi):
            """统计某个 group 里非 None 的股票数"""
            if gi == 1:
                hs = getattr(self, "holding_stocks", [None] * 80)
            else:
                hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
            return sum(1 for h in hs if h)
        def _get_holdings_by_groups(selected_gis):
            """按选中的 group 拿持仓, 按代码去重"""
            seen = set(); result = []
            groups_label = {gi: name for gi, name, _ in ALL_GROUPS}
            for gi in selected_gis:
                if gi == 1:
                    hs = getattr(self, "holding_stocks", [None] * 80)
                else:
                    hs = getattr(self, f"holding_stocks_{gi}", [None] * 80)
                for h in hs:
                    if not h: continue
                    try:
                        name, code = h[0], str(h[1])
                    except: continue
                    if not name or not code: continue
                    key = code.strip()
                    if key in seen: continue
                    seen.add(key)
                    result.append({"name": name.strip(), "code": key, "group": groups_label.get(gi, f"group{gi}")})
            return result
        # ===== 2. 窗口 =====
        win = tk.Toplevel()
        win.title("📊 持股风险仪表盘")
        win.geometry("1320x880")
        win.lift(); win.focus_force()
        banner = tk.Frame(win, bg="#4A148C", height=58); banner.pack(fill=tk.X); banner.pack_propagate(False)
        tk.Label(banner, text="📊 持股风险仪表盘", font=("", 16, "bold"),
                 fg="white", bg="#4A148C").pack(side=tk.LEFT, padx=16, pady=12)
        count_var = tk.StringVar(value="📦 未扫描")
        tk.Label(banner, textvariable=count_var, font=("", 13),
                 fg="#E1BEE7", bg="#4A148C").pack(side=tk.LEFT, padx=8)
        tk.Label(banner, text=f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                 fg="#CE93D8", bg="#4A148C", font=("", 11)).pack(side=tk.RIGHT, padx=14, pady=12)
        # ===== 控制栏: Checkbox 选择标签页 =====
        ctrl = tk.Frame(win, bg="#F3E5F5"); ctrl.pack(fill=tk.X, padx=10, pady=(6, 4))
        # 闭包缓存 —— 数据拉取完存这里, AI 按钮复用
        _cached_results = [None]  # list 闭包可变
        _cached_latest_td = [None]
        # ===== 公共渲染函数 (排序 + worker 都能调) =====
        def _render_text_public(results_rs):
            tree.config(state=tk.NORMAL); tree.delete("1.0", tk.END)
            tree._line_data = {}
            row_tags_map = {"red_bg":"rh","yellow_bg":"yh","green_bg":"gh","gray_bg":"bh"}
            line_count = 0
            for r in results_rs:
                t = r["tag"]; vals = r["values"]; data = r["data"]
                bg = row_tags_map.get(t, "bh")
                tree._line_data[line_count] = data
                def _w(text, *tags):
                    tree.insert(tk.END, str(text), (bg,) + tags)
                _w(f"{vals[0]:<3}")
                _w(f"{vals[1]:<12}", "stk")
                _w(f"{vals[2]:<11}")
                _w(f"{vals[3]:<7}")
                try:
                    dev_val = float(data.get("dev_ma20", 0) or 0)
                except: dev_val = 0
                price_tag = "rn" if dev_val < -3 else "gn" if dev_val > 3 else bg
                _w(f"{vals[4]:>7}", price_tag)
                _w(f"{vals[5]:>7}")
                _w(f"{vals[6]:>7}")
                _w(f"{vals[7]:>7}")
                _w(f"{vals[8]:>7}")
                dd_tag = "rn" if str(vals[9]).startswith("-") else "gn" if vals[9] != "N/A" else bg
                _w(f"{vals[9]:>8}", dd_tag)
                _w(f"{vals[10]:>6}")
                dev_tag = "rn" if str(vals[11]).startswith("-") else "gn" if vals[11] != "N/A" else bg
                _w(f"{vals[11]:>8}", dev_tag)
                _w(f"{vals[12]:>7}")
                _w(f"{vals[13]:>7}")
                try: sc = int(vals[14])
                except: sc = 50
                sc_tag = "rn" if sc < 40 else "yn" if sc < 65 else "gn"
                _w(f"{vals[14]:>4}", sc_tag); _w(" ")
                tag_text = "减仓" if sc < 40 else "观望" if sc < 65 else "持有"
                _w(tag_text + " ", sc_tag)
                tree.insert(tk.END, "\n", (bg,))
                line_count += 1
                tree.config(state=tk.DISABLED)
        # 扫描按钮 (最右)
        scan_btn = tk.Button(ctrl, text="🔍 拉取数据 + 计算红绿灯", font=("", 11, "bold"),
                             bg="#4A148C", fg="white", padx=14, relief=tk.FLAT,
                             cursor="hand2")
        scan_btn.pack(side=tk.RIGHT, padx=4, pady=6)
        # AI 总体分析按钮 (扫描后才启用)
        ai_btn = tk.Button(ctrl, text="🤖 AI 总体分析", font=("", 11, "bold"),
                           bg="#FF6F00", fg="white", padx=14, relief=tk.FLAT,
                           state=tk.DISABLED, cursor="hand2")
        ai_btn.pack(side=tk.RIGHT, padx=4, pady=6)
        # 全选/全不选
        def _select_all(v):
            for _, _, _ in ALL_GROUPS:
                pass  # 下面的 var 是闭包的
        # 先占位, 等 vars 创建后再绑定
        # Checkbox 区域 (水平排列, 自动换行)
        cb_canvas = tk.Canvas(ctrl, bg="#F3E5F5", highlightthickness=0, height=56)
        cb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)
        cb_inner = tk.Frame(cb_canvas, bg="#F3E5F5")
        cb_canvas.create_window((0, 0), window=cb_inner, anchor="nw")
        group_vars = {}  # gi -> BooleanVar
        for idx, (gi, gname, default_on) in enumerate(ALL_GROUPS):
            count = _count_group_stocks(gi)
            var = tk.BooleanVar(value=default_on)
            group_vars[gi] = var
            # 每行 7 个
            row = idx // 7
            col = idx % 7
            cb = tk.Checkbutton(cb_inner, text=f"{gname}({count})",
                                    variable=var, bg="#F3E5F5", fg="#4A148C",
                                    font=("", 10, "bold" if default_on else ""),
                                    activebackground="#F3E5F5", selectcolor="white",
                                    onvalue=True, offvalue=False)
            cb.grid(row=row, column=col, padx=6, pady=2, sticky="w")
        # 全选 / 反选按钮
        btns = tk.Frame(ctrl, bg="#F3E5F5"); btns.pack(side=tk.LEFT, padx=4, pady=6)
        def _on_all():
            for v in group_vars.values(): v.set(True)
        def _on_none():
            for v in group_vars.values(): v.set(False)
        def _on_core():
            for gi, v in group_vars.items():
                v.set(gi in (1, 2, 4, 6))  # 只勾核心 4 组
        tk.Button(btns, text="全选", command=_on_all, font=("", 9),
                  bg="#EDE7F6", relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="全不选", command=_on_none, font=("", 9),
                  bg="#EDE7F6", relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=2)
        tk.Button(btns, text="只选核心4组", command=_on_core, font=("", 9, "bold"),
                  bg="#7B1FA2", fg="white", relief=tk.FLAT, padx=6).pack(side=tk.LEFT, padx=2)
        status_var = tk.StringVar(value="勾选上方标签页 → 点「🔍 拉取数据」开始扫描 (默认只扫 4 个核心标签页)")
        tk.Label(ctrl, textvariable=status_var, fg="#666", bg="#F3E5F5",
                 font=("", 10)).pack(side=tk.LEFT, padx=10)
        main = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashwidth=4)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        # ===== 左侧: 纯文本结果区 =====
        left = tk.Frame(main, bg="white"); main.add(left, width=950)
        tk.Label(left, text="📈 持仓价格全景 (双击行→6维+K线)", bg="white", fg="#333",
                 font=("", 12, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        # 表头 (可点击排序)
        _hdr = tk.Frame(left, bg="#4A148C"); _hdr.pack(fill=tk.X, padx=8, pady=(0, 2))
        _hcols = ["灯","股票","代码","分组","现价","5日前","10日前","20日前","3月高","距3月高","量比","偏MA20","支撑","阻力","评分","瑞鹤仙","利弗莫尔"]
        _hwids = [3,10,10,7,8,7,7,7,8,9,6,9,7,7,6,10,12]
        _col_idx = {c: i for i, c in enumerate(_hcols)}
        _sort_state = {"col": None, "reverse": False}
        def _try_float(v):
            try: return float(str(v).replace("%","").replace("+","-"))
            except: return None
        def _sort_by(col_name):
            results = _cached_results[0]
            if not results: return
            idx = _col_idx.get(col_name, -1)
            if idx < 0: return
            # 翻转排序方向
            if _sort_state["col"] == col_name: _sort_state["reverse"] = not _sort_state["reverse"]
            else: _sort_state["col"] = col_name; _sort_state["reverse"] = False
            def _key(r):
                v = r["values"][idx]
                f = _try_float(v)
                return (0, f if f is not None else 999999)
            sorted_r = sorted(results, key=_key, reverse=_sort_state["reverse"])
            _render_text_public(sorted_r)
        _MonoFont = ("Menlo", 9)
        def _mk_hdr_label(text, w):
            lbl = tk.Label(_hdr, text=text.ljust(w), width=w, bg="#4A148C", fg="white",
                          font=_MonoFont, cursor="hand2", anchor="w")
            lbl.bind("<Button-1>", lambda e, t=text: _sort_by(t))
            lbl.pack(side=tk.LEFT, padx=1)
            return lbl
        for _c, _w in zip(_hcols, _hwids):
            _mk_hdr_label(_c, _w)
        # 纯文本框
        tree = scrolledtext.ScrolledText(left, font=("Menlo",10), bg="#FAFAFA", wrap=tk.NONE, height=24, cursor="hand2")
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0,2))
        tree.tag_configure("rh", background="#FFEBEE")
        tree.tag_configure("yh", background="#FFFDE7")
        tree.tag_configure("gh", background="#E8F5E9")
        tree.tag_configure("bh", background="#F5F5F5")
        tree.tag_configure("rn", foreground="#C62828", font=("Menlo",10,"bold"))
        tree.tag_configure("gn", foreground="#2E7D32", font=("Menlo",10,"bold"))
        tree.tag_configure("yn", foreground="#F57F17", font=("Menlo",10,"bold"))
        tree.tag_configure("stk", foreground="#1A237E", font=("Menlo",10,"bold"))
        tree.tag_configure("bn", foreground="#666")
        tree.insert(tk.END, "⏳ 等待扫描...", "bn")
        tree.config(state=tk.DISABLED)
        # 行号→data 映射
        tree._line_data = {}
        summary = tk.Frame(left, bg="#EDE7F6"); summary.pack(fill=tk.X, padx=8, pady=(0, 6))
        stats_var = tk.StringVar(value="点「🔍 拉取数据 + 计算风险」开始扫描...")
        tk.Label(summary, textvariable=stats_var, bg="#EDE7F6", fg="#4527A0",
                 font=("", 11, "bold")).pack(padx=10, pady=6)
        # ===== 右侧: AI =====
        right = tk.Frame(main, bg="white"); main.add(right)
        tk.Label(right, text="🤖 AI 总体持仓策略分析", bg="white", fg="#333",
                 font=("", 12, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
        ai_txt = scrolledtext.ScrolledText(right, font=("", 11), wrap=tk.WORD,
                                            bg="#FAFAFA", height=28)
        ai_txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        ai_txt.tag_configure("h",  foreground="#4A148C", font=("", 12, "bold"))
        ai_txt.tag_configure("rg", foreground="#C62828", background="#FFEBEE")
        ai_txt.tag_configure("yg", foreground="#F57F17", background="#FFFDE7")
        ai_txt.tag_configure("gg", foreground="#2E7D32", background="#E8F5E9")
        ai_txt.insert(tk.END, "⏳ 等待扫描...\n\n扫描完成后 AI 会在此给出整体持仓策略建议。", "h")
        ai_txt.config(state=tk.DISABLED)
        def _render_ai(text):
            ai_txt.config(state=tk.NORMAL); ai_txt.delete("1.0", tk.END)
            for line in (text or "(AI未返回)").split("\n"):
                if any(kw in line for kw in ["持有", "安全", "加仓", "低吸", "积极", "多头", "绿灯", "健康"]):
                    ai_txt.insert(tk.END, line + "\n", "gg")
                elif any(kw in line for kw in ["减仓", "危险", "清仓", "避险", "破位", "空头", "红灯", "止损", "警惕"]):
                    ai_txt.insert(tk.END, line + "\n", "rg")
                elif any(kw in line for kw in ["黄灯", "控制", "观望", "震荡", "谨慎"]):
                    ai_txt.insert(tk.END, line + "\n", "yg")
                else:
                    ai_txt.insert(tk.END, line + "\n")
            ai_txt.config(state=tk.DISABLED)
        # ===== 3. 扫描 =====
        def _scan_all():
            import sys as _sys_btn
            print("🔘 按钮被点击了!", file=_sys_btn.stderr, flush=True)
            # 1. 从 checkbox 拿选中的 group
            selected_gis = [gi for gi, var in group_vars.items() if var.get()]
            if not selected_gis:
                tk.messagebox.showinfo("提示", "请先勾选至少 1 个持仓标签页！\n\n建议勾选：自持股 + 龙头股 + Main + 同花顺")
                return
            # 2. 取持仓
            all_holdings = _get_holdings_by_groups(selected_gis)
            if not all_holdings:
                tk.messagebox.showwarning("提示", f"勾选的 {len(selected_gis)} 个标签页里没有任何股票！\n\n请先在 GUI 标签页中添加股票。")
                return
            count_var.set(f"📦 {len(all_holdings)} 只持仓 (来自 {len(selected_gis)} 个标签页)")
            scan_btn.config(state=tk.DISABLED, text="⏳ 拉取中...")
            tree.config(state=tk.NORMAL); tree.delete("1.0", tk.END)
            tree.insert(tk.END, "⏳ 拉取中...", "bn"); tree.config(state=tk.DISABLED)
            tree._line_data = {}
            status_var.set(f"⏳ 已选 {len(selected_gis)} 个标签页, {len(all_holdings)} 只股票, 正在拉 tushare...")
            def worker():
                import traceback as _tb
                try:
                    _worker_inner()
                except Exception as e:
                    print(f"  ❌ WORKER FATAL: {e}\n{_tb.format_exc()}", flush=True)
                    win.after(0, lambda e=e: status_var.set(f"❌ 扫描异常: {e}"))
                    win.after(0, lambda: scan_btn.config(state=tk.NORMAL, text="🔍 重新拉取"))
            def _worker_inner():
                import sys as _sys
                def _log(msg):
                    print(msg, file=_sys.stderr, flush=True)
                import concurrent.futures as _cf
                _log(f"🚀 WORKER START: all_holdings={len(all_holdings)}"); _pro = _ts_pro.pro_api()
                today = datetime.now().strftime("%Y%m%d")
                t0 = time.time()
                try:
                    _cal = _pro.trade_cal(exchange="SSE", start_date="20260101",
                                          end_date=today, is_open="1")
                    _latest = _cal["cal_date"].max() if len(_cal) else today
                except: _latest = today
                # 交易日回退 5/10/20
                try:
                    cal_all = _pro.trade_cal(exchange="SSE", start_date="20250601",
                                             end_date=_latest, is_open="1")
                    trade_days = sorted(cal_all["cal_date"].tolist()) if len(cal_all) else [_latest]
                    idx = trade_days.index(_latest) if _latest in trade_days else len(trade_days) - 1
                    td_5 = trade_days[max(0, idx - 5)]
                    td_10 = trade_days[max(0, idx - 10)]
                    td_20 = trade_days[max(0, idx - 20)]
                except Exception:
                    td_5 = td_10 = td_20 = _latest
                # ===== 优化1: 全市场批量当日数据 (2 次 API, 不管 30 只还是 5547 只) =====
                win.after(0, lambda: status_var.set("⏳ 拉全市场当日数据 (2 次 API)..."))
                try:
                    t1 = time.time()
                    df_today = _pro.daily(trade_date=_latest)
                    _log(f"  📊 批量 daily ({len(df_today)}只): {time.time()-t1:.2f}s")
                except Exception: df_today = None
                try:
                    df_basic_today = _pro.daily_basic(trade_date=_latest,
                                                      fields="ts_code,pe_ttm,pb,total_mv,turnover_rate")
                    _log(f"  📊 批量 daily_basic ({len(df_basic_today)}只): {time.time()-t1:.2f}s")
                except Exception: df_basic_today = None
                # 转成 dict 加速查询
                today_map = {}
                if df_today is not None and len(df_today):
                    for _, row in df_today.iterrows():
                        today_map[row["ts_code"]] = row
                basic_map = {}
                if df_basic_today is not None and len(df_basic_today):
                    for _, row in df_basic_today.iterrows():
                        basic_map[row["ts_code"]] = row
                # ===== 优化2: 历史 K 线并发拉取 (5 workers) =====
                import re as _re_ts
                def _to_ts_code(code):
                    if not code: return ""
                    code = str(code).strip().upper()
                    # 先处理 "600519.SH" / "600519.SZ" 这种 — 直接合法
                    if _re_ts.match(r"^\d{6}\.(SH|SZ|BJ)$", code): return code
                    # 提取纯 6 位数字 (不管周围有什么垃圾 "42. 300483" → 300483)
                    m = _re_ts.search(r"(\d{6})", code)
                    if not m: return code  # 没有 6 位数字, 原样
                    pure6 = m.group(1)
                    # 已带前缀 SH600519 → 提取纯数字后再判断
                    if pure6.startswith(("43","83","87","92")): return pure6 + ".BJ"
                    if pure6.startswith(("6","5","9")): return pure6 + ".SH"
                    if pure6.startswith(("0","3","2")): return pure6 + ".SZ"
                    return pure6 + ".SH"
                all_ts_codes = []
                code_mapping = {}
                for h in all_holdings:
                    ts_code = _to_ts_code(h["code"])
                    all_ts_codes.append(ts_code)
                    code_mapping[ts_code] = h
                _log(f"📋 ts_code 转换: {len(all_ts_codes)} 只, 前5: {all_ts_codes[:5]}")
                win.after(0, lambda: status_var.set(
                    f"⏳ 并发拉 {len(all_ts_codes)} 只历史 K 线 (5 workers)..."))
                def _fetch_history(ts_c):
                    try:
                        return ts_c, _pro.daily(ts_code=ts_c, start_date="20250601", end_date=_latest)
                    except:
                        return ts_c, None
                t2 = time.time()
                hist_map = {}
                with _cf.ThreadPoolExecutor(max_workers=5) as pool:
                    for ts_c, df in pool.map(_fetch_history, all_ts_codes):
                        hist_map[ts_c] = df
                _log(f"  📊 {len(all_ts_codes)} 只并发历史K线: {time.time()-t2:.2f}s")
                # ===== 计算 =====
                results = []; rc = yc = gc = 0
                n = len(all_holdings)
                _log(f"  📈 DEBUG: 开始计算, n={n}, all_ts_codes={len(all_ts_codes)}")
                for i, ts_code in enumerate(all_ts_codes):
                    try:
                        h = code_mapping[ts_code]
                        code = h["code"]
                        df_k = hist_map.get(ts_code)
                        row_t = today_map.get(ts_code)
                        row_b = basic_map.get(ts_code)
                        if i < 3 or df_k is None:
                            _log(f"  📈 DEBUG[{i}]: {ts_code} h={h['name']} df_k={'有' if df_k is not None and len(df_k) else '空'} row_t={'有' if row_t is not None else '无'}")
                        price_now = p5 = p10 = p20 = p3m_high = "-"
                        pct_3m = vr = dma = supp = resi = "N/A"
                        score = 50; light = "⚫"
                        if df_k is not None and len(df_k) > 0:
                            df_k = df_k.sort_values("trade_date")
                            closes = df_k["close"].astype(float).tolist()
                            vols = df_k["vol"].astype(float).tolist()
                            price_now = round(closes[-1], 2)
                            # 用历史 daily 的 trade_date 列直接找, 不用再 sub
                            dates_list = df_k["trade_date"].tolist()
                            def _fp_fast(td):
                                for k in range(len(dates_list)-1, -1, -1):
                                        if dates_list[k] <= td:
                                            return round(closes[k], 2)
                                return None
                            p5 = _fp_fast(td_5); p10 = _fp_fast(td_10); p20 = _fp_fast(td_20)
                            p3m_high = round(max(closes[-60:]), 2) if len(closes) >= 60 else round(max(closes), 2)
                            if p3m_high:
                                pct_3m = f"{(price_now - p3m_high) / p3m_high * 100:+.2f}%"
                            vol_t = vols[-1]
                            vol_a = sum(vols[-20:]) / 20 if len(vols) >= 20 else vol_t
                            vr = round(vol_t / vol_a, 2) if vol_a > 0 else 1
                            ma5 = sum(closes[-5:])/5 if len(closes)>=5 else price_now
                            ma10 = sum(closes[-10:])/10 if len(closes)>=10 else price_now
                            ma20 = sum(closes[-20:])/20 if len(closes)>=20 else price_now
                            dma = round((price_now - ma20) / ma20 * 100, 2)
                            last20 = closes[-20:] if len(closes) >= 20 else closes
                            supp = round(min(last20), 2); resi = round(max(last20), 2)
                            # 6维打分
                            score = 50
                            if vr > 2: score -= 8
                            elif 0.6 <= vr <= 1.3: score += 6
                            if abs(dma) < 3: score += 6
                            elif abs(dma) > 12: score -= 8
                            dd = (price_now - p3m_high) / p3m_high * 100 if p3m_high else 0
                            if dd > -5: score += 4
                            elif dd < -15: score -= 8
                            if ma5 > ma10 > ma20: score += 12
                            elif ma5 < ma10 < ma20: score -= 16
                            if row_b is not None:
                                try:
                                        pe_v = float(row_b.get("pe_ttm") or 0)
                                        if 0 < pe_v < 40: score += 6
                                        elif pe_v > 100: score -= 8
                                except: pass
                            score = max(0, min(100, score))
                            light = "🟢" if score >= 65 else ("🟡" if score >= 40 else "🔴")
                            # ===== 瑞鹤仙心法打分 =====
                            # 核心: 只做强势 + 均线多头 + 量能活跃 + 不追高
                            rhx = 50
                            if ma5 > ma10 > ma20: rhx += 25        # 均线多头 +25 (只做强势)
                            elif ma5 < ma10 < ma20: rhx -= 25     # 均线空头 -25 (回避)
                            if 1.0 <= vr <= 2.0: rhx += 15         # 量能活跃 +15
                            elif vr < 0.6: rhx -= 10               # 缩量 -10 (不活跃)
                            elif vr > 3.0: rhx -= 15               # 天量 -15 (滞涨风险)
                            if dma > 10: rhx -= 20                 # 偏离MA20>10% -20 (追高)
                            elif dma > 5: rhx -= 8                 # 偏离>5% -8 (偏高)
                            elif -3 <= dma <= 3: rhx += 8           # 合理位置 +8
                            if dd > -5: rhx += 10                  # 接近新高 +10 (强势)
                            elif dd < -20: rhx -= 15               # 深套 -15 (回避)
                            if dd > 5: rhx -= 15                   # 暴涨后 -15 (不追涨)
                            rhx = max(0, min(100, rhx))
                            # 瑞鹤仙标签
                            if rhx >= 70: rhx_tag = "✅强势可做"
                            elif rhx >= 50: rhx_tag = "⚠️观察等待"
                            else: rhx_tag = "❌坚决回避"
                            # ===== 利弗莫尔四支柱 =====
                            # 支柱1: 最小阻力线 (classify_trend 内联)
                            _n = len(closes)
                            if _n >= 20:
                                _net20 = closes[-1] / closes[-20] - 1
                                _x = list(range(20))
                                _slope = np.polyfit(_x, closes[-20:], 1)[0]
                                _slope_pct = _slope / closes[-1] * 20
                                _ma20_lm = sum(closes[-20:]) / 20
                                _abs_net = abs(_net20)
                                if _abs_net < 0.05 and vr > 0:
                                        _trend_label = "横盘"
                                elif _net20 > 0.08 and closes[-1] > _ma20_lm and _slope_pct > 0:
                                        _trend_label = "强上升趋势"
                                elif _net20 < -0.08 and closes[-1] < _ma20_lm and _slope_pct < 0:
                                        _trend_label = "强下降趋势"
                                elif _net20 > 0:
                                        _trend_label = "震荡偏多"
                                else:
                                        _trend_label = "震荡偏空"
                            else:
                                _trend_label = "数据不足"
                            _TREND_DIR_LM = {"强上升趋势":"上升","震荡偏多":"上升","横盘":"震荡","震荡偏空":"下降","强下降趋势":"下降"}
                            _trend_dir = _TREND_DIR_LM.get(_trend_label, "震荡")
                            # 支柱2: 关键点识别
                            _last_vol = vols[-1]
                            _vol_avg5 = sum(vols[-6:-1]) / 5 if len(vols) >= 6 else (_last_vol if _last_vol > 0 else 1)
                            _vol_exp = (_last_vol / _vol_avg5 > 1.2) if _vol_avg5 > 0 else False
                            _ma10_lm = sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1]
                            _win30 = closes[-30:] if len(closes) >= 30 else closes
                            if df_k is not None and len(df_k) >= 30 and "high" in df_k.columns:
                                _hi30 = float(df_k["high"].iloc[-30:].max()) if len(df_k) >= 30 else float(df_k["high"].max())
                                _lo30 = float(df_k["low"].iloc[-30:].min()) if len(df_k) >= 30 else float(df_k["low"].min())
                            else:
                                _hi30 = max(_win30); _lo30 = min(_win30)
                            _rng30 = (_hi30 - _lo30) / _lo30 if _lo30 else 0
                            _consolidated = _rng30 < 0.15
                            # 简单 pivot high: 近5个高点的最大值
                            if df_k is not None and len(df_k) >= 10 and "high" in df_k.columns:
                                _ph5 = float(df_k["high"].iloc[-10:].max())
                                _pl5 = float(df_k["low"].iloc[-10:].min())
                            else:
                                _ph5 = _hi30; _pl5 = _lo30
                            _reversal_kp = _consolidated and closes[-1] >= _hi30 and _vol_exp
                            _pullback_ma10 = min(closes[-7:-1]) <= _ma10_lm if len(closes) >= 7 else False
                            _continuation_kp = (_trend_dir == "上升") and _pullback_ma10 and closes[-1] > _ma10_lm and _vol_exp
                            _breakout_now = closes[-1] > _ph5 and _vol_exp
                            _prev_broke = (len(closes) >= 2) and (closes[-2] > _ph5)
                            _danger = _prev_broke and (closes[-1] < _ph5)
                            # 支柱3+4: 综合判定 + 输出
                            if _trend_dir == "下降":
                                _lm_tag = "🔻下降通道 无买点"
                                _lm_color = "rn"
                            elif _trend_dir == "震荡":
                                if _consolidated and closes[-1] >= _hi30 and _vol_exp:
                                        _lm_tag = "⏳盘整+放量待突破"
                                        _lm_color = "yn"
                                else:
                                        _lm_tag = "➡️震荡观望"
                                        _lm_color = "yn"
                            elif _danger:
                                _lm_tag = "🚫假突破 撤买点"
                                _lm_color = "rn"
                            elif _reversal_kp:
                                _lm_tag = "✅反转关键点"
                                _lm_color = "gn"
                            elif _continuation_kp:
                                _lm_tag = "✅持续关键点"
                                _lm_color = "gn"
                            elif _breakout_now:
                                _lm_tag = "⏳突破中 等回踩"
                                _lm_color = "yn"
                            elif _trend_dir == "上升":
                                _lm_tag = "🔺上升 等关键点"
                                _lm_color = "gn"
                            else:
                                _lm_tag = "⏸️数据不足"
                                _lm_color = "bn"
                            # 利弗莫尔止损位 + 最大风险%
                            _hard_sl = closes[-1] * 0.90
                            _struct_sl = _pl5 * 0.985
                            _eff_sl = max(_hard_sl, _struct_sl)  # 取更紧者
                            _lm_sl_pct = round((closes[-1] - _eff_sl) / closes[-1] * 100, 1)
                            _lm_sl_str = f"止损{_eff_sl:.2f}({_lm_sl_pct}%)"
                        else:
                            rhx = 50; rhx_tag = "⏸️无数据"; ma5 = ma10 = ma20 = 0
                            _eff_sl = 0
                            _trend_dir = "震荡"; _lm_tag = "⏸️无数据"; _lm_color = "bn"; _lm_sl_str = ""
                        if score >= 65: tag = "green_bg"; gc += 1
                        elif score >= 40: tag = "yellow_bg"; yc += 1
                        else: tag = "red_bg"; rc += 1
                        results.append({
                            "values": (light, h["name"], code, h["group"],
                                       f"{price_now}", f"{p5}", f"{p10}", f"{p20}",
                                       f"{p3m_high}", f"{pct_3m}",
                                       f"{vr}", f"{dma:+.2f}%" if dma != "N/A" else "N/A",
                                       f"{supp}", f"{resi}", f"{score}",
                                       f"{rhx_tag}", f"{_lm_tag}"),
                            "tag": tag,
                            "data": {"name": h["name"], "code": code, "ts_code": ts_code,
                                     "price": price_now, "score": score, "supp": supp, "resi": resi,
                                     "vol_ratio": vr, "dev_ma20": dma,
                                     "ma5": ma5 if df_k is not None and len(df_k) else 0,
                                     "ma10": ma10 if df_k is not None and len(df_k) else 0,
                                     "ma20": ma20 if df_k is not None and len(df_k) else 0,
                                     "rhx_score": rhx, "rhx_tag": rhx_tag,
                                     "lm_trend_dir": _trend_dir, "lm_tag": _lm_tag,
                                     "lm_sl_str": _lm_sl_str, "lm_eff_sl": _eff_sl if df_k is not None and len(df_k) else 0}
                    })
                    except Exception as _e2:
                        import traceback as _tb_inner
                        _log(f"  ⚠️ [{i}] {ts_code} 计算异常: {_e2}")
                        _tb_inner.print_exc()
                        continue
                _log(f"📈 results: len={len(results)} rc={rc} yc={yc} gc={gc}, df_k有数据={sum(1 for r in results if r['data'].get('price') != '-')}")
                # 一次性写 ScrolledText (最可靠)
                def _render_text():
                    try:
                        tree.config(state=tk.NORMAL); tree.delete("1.0", tk.END)
                        tree._line_data = {}
                        row_tags_map = {"red_bg":"rh","yellow_bg":"yh","green_bg":"gh","gray_bg":"bh"}
                        line_count = 0
                        for r in results:
                            t = r["tag"]; vals = r["values"]; data = r["data"]
                            bg = row_tags_map.get(t, "bh")
                            # 存 data: 从 1 开始
                            tree._line_data[line_count] = data
                            def _w(text, *tags):
                                    tree.insert(tk.END, str(text), (bg,) + tags)
                            _w(f"{vals[0]:<2}")        # 灯
                            _w(f"{vals[1]:<10}", "stk")  # 股票
                            _w(f"{vals[2]:<10}")        # 代码
                            _w(f"{vals[3]:<7}")         # 分组
                            # 现价 - 按涨跌着色
                            try:
                                    dev_val = float(data.get("dev_ma20", 0) or 0)
                                    pct_val = vals[9]
                                    float(str(pct_val).replace("%","").replace("+","")) if pct_val and pct_val != "N/A" else 0
                            except:
                                    dev_val = 0
                            price_tag = "rn" if dev_val < -3 else "gn" if dev_val > 3 else bg
                            _w(f"{vals[4]:>7}", price_tag)
                            _w(f"{vals[5]:>7}")
                            _w(f"{vals[6]:>7}")
                            _w(f"{vals[7]:>7}")
                            _w(f"{vals[8]:>7}")
                            dd_tag = "rn" if str(vals[9]).startswith("-") else "gn" if vals[9] != "N/A" else bg
                            _w(f"{vals[9]:>8}", dd_tag)
                            _w(f"{vals[10]:>6}")
                            dev_tag = "rn" if str(vals[11]).startswith("-") else "gn" if vals[11] != "N/A" else bg
                            _w(f"{vals[11]:>8}", dev_tag)
                            _w(f"{vals[12]:>7}")
                            _w(f"{vals[13]:>7}")
                            # 评分 + 语义标签
                            try: sc = int(vals[14])
                            except: sc = 50
                            sc_tag = "rn" if sc < 40 else "yn" if sc < 65 else "gn"
                            _w(f"{vals[14]:>4}", sc_tag); _w(" ")
                            tag_text = "减仓" if sc < 40 else "观望" if sc < 65 else "持有"
                            _w(tag_text + " ", sc_tag)
                            # 瑞鹤仙
                            rhx_v = vals[15] if len(vals) > 15 else ""
                            if rhx_v.startswith("✅"): rhx_col = "gn"
                            elif rhx_v.startswith("⚠️"): rhx_col = "yn"
                            else: rhx_col = "rn"
                            _w(f"{rhx_v:>10}", rhx_col)
                            # 利弗莫尔
                            lm_v = vals[16] if len(vals) > 16 else ""
                            if lm_v.startswith(("✅", "🔺")): lm_col = "gn"
                            elif lm_v.startswith(("⚠️", "⏳", "➡️")): lm_col = "yn"
                            elif lm_v.startswith(("🔻", "🚫")): lm_col = "rn"
                            else: lm_col = "bn"
                            _w(f"{lm_v:>12}", lm_col)
                            tree.insert(tk.END, "\n", (bg,))
                            line_count += 1
                            tree.config(state=tk.DISABLED)
                        _log(f"🖥️ 文本渲染成功: {line_count} 行")
                    except Exception as e:
                        _log(f"🖥️ 文本渲染失败: {e}")
                        import traceback; traceback.print_exc()
                win.after(0, _render_text)
                avg_pct = _avg_drawdown(results)
                win.after(0, lambda: stats_var.set(
                    f"🟢{gc} 🟡{yc} 🔴{rc}  |  绿灯率 {gc/n*100:.0f}%  |  距3月高 均值 {avg_pct}"))
                # ===== 拆分为两步: 数据缓存好, AI 按钮按需点 =====
                _cached_results[0] = results
                _cached_latest_td[0] = _latest
                win.after(0, lambda: status_var.set(
                    f"✅ 数据就绪 ({len(results)}只, 拉取 {time.time()-t0:.1f}秒)  |  点右侧 🤖 AI 总体分析"))
                win.after(0, lambda: scan_btn.config(state=tk.NORMAL, text="🔍 重新拉取"))
                win.after(0, lambda: ai_btn.config(state=tk.NORMAL, text="🤖 AI 总体分析"))
                win.after(0, lambda: _render_ai(
                    f"⏰ 数据已就绪 ({len(results)}只, {time.time()-t0:.1f}秒)\n\n"
                    f"📊 红绿灯分布: 🟢{gc} 🟡{yc} 🔴{rc}  |  绿灯率 {gc/n*100:.0f}%\n\n"
                    f"💡 想看 AI 对这 {len(results)} 只持仓做总体策略建议?\n"
                    f"   点上方「🤖 AI 总体分析」按钮 (可能需要 5-15 秒)"))
            threading.Thread(target=worker, daemon=True).start()
        def _avg_drawdown(results):
            vals = []
            for r in results:
                try:
                    p = float(r["values"][9].replace("%", ""))
                    vals.append(p)
                except: pass
            if not vals: return "N/A"
            return f"{sum(vals)/len(vals):+.2f}%"
        def _build_ai_prompt(results, td):
            g = [r for r in results if r["data"]["score"] >= 65]
            y = [r for r in results if 40 <= r["data"]["score"] < 65]
            r = [r for r in results if r["data"]["score"] < 40]
            n = len(results)
            lines = [f"## 持仓红绿灯 ({n}只, 数据日期 {td})",
                     f"- 🟢 绿灯安全 {len(g)}只: {', '.join(r['values'][1] for r in g[:12])}",
                     f"- 🟡 黄灯警惕 {len(y)}只: {', '.join(r['values'][1] for r in y[:12])}",
                     f"- 🔴 红灯危险 {len(r)}只: {', '.join(r['values'][1] for r in r[:12])}", "",
                     "## 详细数据 (现价 | 距3月高 | 量比 | 偏离MA20 | 支撑/阻力 | 评分)"]
            for rv in results:
                v = rv["values"]
                lines.append(f"{v[1]}({v[2]}): {v[4]} | {v[9]} | {v[10]} | {v[11]} | {v[12]}/{v[13]} | {v[14]}")
            return ("请对我的持仓组合做整体风险评估。\n\n" + "\n".join(lines) +
                    "\n\n输出: 1.整体健康度+一句话 2.结构性风险 3.红灯减仓建议(按优先级) "
                    "4.黄灯操作建议 5.绿灯持有策略 6.板块再平衡 🎯 一句话操作总结")
        scan_btn.config(command=_scan_all)
        # ===== 独立的 AI 总体分析 =====
        def _run_ai_overall():
            results = _cached_results[0]
            if not results:
                tk.messagebox.showinfo("提示", "请先点「🔍 拉取数据 + 计算红绿灯」获取持仓数据！")
                return
            ai_btn.config(state=tk.DISABLED, text="⏳ AI 分析中...")
            scan_btn.config(state=tk.DISABLED)
            win.after(0, lambda: status_var.set(f"⏳ AI 正在分析 {len(results)} 只持仓 (可能 5-15秒)..."))
            win.after(0, lambda: _render_ai(
                f"⏳ AI 正在分析 {len(results)} 只持仓...\n\n(请稍候, 大模型正在生成总体策略建议)"))
            def ai_worker():
                t0 = time.time()
                prompt = _build_ai_prompt(results, _cached_latest_td[0] or "")
                try:
                    res = self.call_ai_model(prompt,
                        system_prompt="你是A股持仓风险分析师,擅长从多只持仓股的价格结构和均线形态综合判断整体风险。参考 rocket-scan 三维共振模型。",
                        max_tokens=2500)
                except Exception as e:
                    res = f"❌ AI 失败: {e}"
                win.after(0, lambda: _render_ai(res + f"\n\n⏱️ AI 耗时 {time.time()-t0:.1f}秒"))
                win.after(0, lambda: ai_btn.config(state=tk.NORMAL, text="🤖 AI 重新分析"))
                win.after(0, lambda: scan_btn.config(state=tk.NORMAL))
                win.after(0, lambda: status_var.set("✅ AI 分析完成"))
            threading.Thread(target=ai_worker, daemon=True).start()
        ai_btn.config(command=_run_ai_overall)
        # ===== 4. 双击 → 轻量日K线窗口 + 6维按钮 =====
        def _open_kline_fast(data):
            if not data: return
            # data 里必须有 ts_code
            ts_c = data.get("ts_code", "")
            name = data.get("name", "?")
            code = data.get("code", "?")
            if not ts_c:
                tk.messagebox.showwarning("提示", f"{name}({code}) 无有效 tushare 代码", parent=win)
                return
            kw = tk.Toplevel()
            light = "🔴" if data.get("score", 50) < 40 else ("🟡" if data.get("score", 50) < 65 else "🟢")
            kw.title(f"📈 {name}({code}) · 日K线 {light}")
            kw.geometry("900x640"); kw.lift(); kw.focus_force()
            # 顶部信息栏 + 按钮
            top = tk.Frame(kw, bg="#EDE7F6", height=32); top.pack(fill=tk.X, side=tk.TOP)
            top.pack_propagate(False)
            sc = data.get("score", 50)
            tk.Label(top, text=f"{name}({code})  现价 {data.get('price','-')}  评分 {sc}/100 {light}  支撑 {data.get('supp','-')}  阻力 {data.get('resi','-')}",
                     bg="#EDE7F6", fg="#4527A0", font=("", 11, "bold")).pack(side=tk.LEFT, padx=12, pady=4)
            kline_fig_container = [None]  # 闭包引用
            # --- 6维分析按钮 ---
            def _open_6dim():
                self._SingleAnalysis(self, data).show()
            tk.Button(top, text="📊 6维打分分析", command=_open_6dim,
                      bg="#7B1FA2", fg="white", font=("",9,"bold"),
                      relief=tk.FLAT, padx=10, pady=2, cursor="hand2").pack(side=tk.RIGHT, padx=10, pady=4)
            # K线容器
            kline_host = tk.Frame(kw, bg="white"); kline_host.pack(fill=tk.BOTH, expand=True)
            loading = tk.Label(kline_host, text="⏳ 拉取日K线...", bg="white", font=("",11))
            loading.pack(expand=True)
            # 后台线程拉数据
            import threading as _th
            def _fetch_and_draw():
                try:
                    import tushare as _ts
                    from datetime import datetime as _dt
                    import matplotlib; matplotlib.use("TkAgg")
                    import numpy as np
                    import pandas as pd
                    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                    from matplotlib.figure import Figure
                    from matplotlib.patches import Rectangle
                    df_k = _ts.pro_api().daily(ts_code=ts_c, start_date="20250901",
                                              end_date=_dt.now().strftime("%Y%m%d"))
                    if df_k is None or len(df_k) == 0:
                        kw.after(0, lambda: loading.config(text="❌ 无K线数据"))
                        return
                    df_k = df_k.sort_values("trade_date").reset_index(drop=True)
                    # 最近 120 天 (约 6 个月)
                    df_k = df_k.tail(120).reset_index(drop=True)
                    dates = pd.to_datetime(df_k["trade_date"], format="%Y%m%d")
                    opens = df_k["open"].astype(float).values
                    highs = df_k["high"].astype(float).values
                    lows = df_k["low"].astype(float).values
                    closes = df_k["close"].astype(float).values
                    # 计算均线
                    ma5 = pd.Series(closes).rolling(5).mean().values
                    ma10 = pd.Series(closes).rolling(10).mean().values
                    ma20 = pd.Series(closes).rolling(20).mean().values
                    def _do_draw():
                        loading.destroy()
                        fig = Figure(figsize=(11, 6), dpi=90, facecolor="#FAFAFA")
                        ax = fig.add_subplot(111, facecolor="#FAFAFA")
                        n = len(closes)
                        x = np.arange(n)
                        # 画 K 线 (蜡烛)
                        for i in range(n):
                            color = "#C62828" if closes[i] >= opens[i] else "#2E7D32"
                            # 影线
                            ax.plot([x[i], x[i]], [lows[i], highs[i]], color=color, lw=0.8)
                            # 实体
                            body_lo = min(opens[i], closes[i])
                            body_hi = max(opens[i], closes[i])
                            body = Rectangle((x[i] - 0.35, body_lo), 0.7, body_hi - body_lo,
                                             facecolor=color, edgecolor=color)
                            ax.add_patch(body)
                        # 均线
                        ax.plot(x, ma5, color="#FF9800", lw=1.2, label="MA5", alpha=0.85)
                        ax.plot(x, ma10, color="#2196F3", lw=1.2, label="MA10", alpha=0.85)
                        ax.plot(x, ma20, color="#9C27B0", lw=1.3, label="MA20", alpha=0.9)
                        # 支撑/阻力线
                        supp = data.get("supp")
                        resi = data.get("resi")
                        if supp and supp not in ("N/A", "-", None):
                            try:
                                    ax.axhline(y=float(supp), color="#4CAF50", ls="--", lw=0.9, label=f"支撑 {supp}")
                            except: pass
                        if resi and resi not in ("N/A", "-", None):
                            try:
                                    ax.axhline(y=float(resi), color="#F44336", ls="--", lw=0.9, label=f"阻力 {resi}")
                            except: pass
                        # x 轴格式
                        step = max(1, n // 12)
                        tick_pos = x[::step]
                        tick_labels = dates.iloc[::step].dt.strftime("%m-%d")
                        ax.set_xticks(tick_pos)
                        ax.set_xticklabels(tick_labels, rotation=30, fontsize=8)
                        ax.set_title(f"{name}({code})  日K线 · 近{n}日", fontsize=11, fontweight="bold")
                        ax.legend(loc="upper left", fontsize=8, framealpha=0.7)
                        ax.grid(True, alpha=0.3, color="#DDD")
                        ax.margins(x=0.02)
                        fig.tight_layout()
                        canvas = FigureCanvasTkAgg(fig, master=kline_host)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        kline_fig_container[0] = canvas
                    kw.after(0, _do_draw)
                except Exception as e:
                    kw.after(0, lambda e=e: loading.config(text=f"❌ 拉K线失败: {e}"))
                    import traceback; traceback.print_exc()
            _th.Thread(target=_fetch_and_draw, daemon=True).start()
        def _open_single(data):
            """完整 6维+AI+K线 弹窗"""
            if not data: return
            self._SingleAnalysis(self, data).show()
        def _get_data_at_click(event):
            """从点击位置取该行的 data"""
            line = int(tree.index(f"@{event.x},{event.y}").split(".")[0]) - 1
            return tree._line_data.get(line)
        tree.bind("<Double-1>", lambda e: _open_kline_fast(_get_data_at_click(e)))
        # 右键
        _last_right_data = [None]
        def _on_right(e):
            _last_right_data[0] = _get_data_at_click(e)
            rc.tk_popup(e.x_root, e.y_root)
        rc = tk.Menu(win, tearoff=0)
        rc.add_command(label="📈 打开日K线 (双击)",
                       command=lambda: _open_kline_fast(_last_right_data[0]))
        rc.add_command(label="🔍 完整6维分析 + AI",
                       command=lambda: _open_single(_last_right_data[0]))
        tree.bind("<Button-3>", _on_right)



__all__ = ["CangweiMixin"]

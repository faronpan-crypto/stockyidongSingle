"""
大盘分析 Mixin — DapanMixin

迁移自 stockyidong mac003.py: 81 方法 / ~8697 行
涵盖: 大盘 Tab 刷新/快照/趋势, 情绪周期三维度, 涨跌停广度, 同花顺情绪, 生命周期扫描
"""
import os, sys, re, json, time, sqlite3, threading, traceback, base64, io, hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
from datetime import datetime, timedelta
from urllib.parse import urljoin

try:
    import numpy as np
except ImportError:
    np = None
try:
    import pandas as pd
except ImportError:
    pd = None
try:
    import akshare as ak
except ImportError:
    ak = None
try:
    import tushare as ts
except ImportError:
    ts = None
try:
    import requests
except ImportError:
    requests = None
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from utils.config import *
from utils.network import safe_call
from data.db import init_database, save_judgment_cache_snapshot, load_fresh_judgment_cache, save_stock_to_db, save_kelly_record_to_db
from data.snapshot import *
from logic.crawlers import *
from logic.spot import *  # _should_skip_akshare
from logic.dapan_fetcher import *

class DapanMixin:
    """大盘分析 + 情绪周期相关方法"""


    def _apply_ths_sentiment_trend_to_checkboxes(self, trend):
        """将 上行/震荡/下行 映射到开新仓流程中的两个勾选框。"""
        try:
            if trend == "上行":
                self.sentiment_index_ma1_uptrend_var.set(True)
                self.sentiment_index_ma1_above_var.set(True)
            elif trend == "下行":
                self.sentiment_index_ma1_uptrend_var.set(False)
                self.sentiment_index_ma1_above_var.set(False)
            else:
                # 震荡:未明确向上,但仍可能在 1 日线上 → 不满足「双勾选」开新仓条件
                self.sentiment_index_ma1_uptrend_var.set(False)
                self.sentiment_index_ma1_above_var.set(True)
            self._update_sentiment_index_check_coord()
        except Exception:
            pass


    def _update_sentiment_index_check_coord(self):
        """两个手动勾选框与「已确认」汇总状态同步。"""
        try:
            if self.sentiment_index_ma1_uptrend_var.get() and self.sentiment_index_ma1_above_var.get():
                self.sentiment_index_check_var.set(True)
            else:
                self.sentiment_index_check_var.set(False)
        except Exception:
            pass


    def _save_ths_sentiment_trend(self, trend):
        if trend not in ("上行", "震荡", "下行"):
            return
        self.ths_sentiment_trend_var.set(trend)
        self.ai_config_manager.config["ths_sentiment_trend"] = trend
        try:
            self.ai_config_manager.save_config()
        except Exception:
            pass
        self._apply_ths_sentiment_trend_to_checkboxes(trend)


    def _show_ths_sentiment_reminder_dialog(self):
        top = self._safe_toplevel(self.root)
        top.title("同花顺情绪指数")
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception:
            pass
        # 登记到提醒弹窗列表,关闭时(确定/稍后/×)移除引用以释放配额
        try:
            self._ths_reminder_windows.append(top)
            def _on_destroy(event, ref=top):
                if event.widget is not ref:
                    return
                try:
                    self._ths_reminder_windows.remove(ref)
                except ValueError:
                    pass
            top.bind("<Destroy>", _on_destroy)
        except Exception:
            pass
        top.geometry("440x210")
        f = ttk.Frame(top, padding=16)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            f,
            text="请选择当前同花顺情绪指数的大致方向(将与「交易」开新仓流程中的「1日线往上」「在1日线上」勾选框联动):",
            wraplength=400,
        ).pack(anchor=tk.W)
        var = tk.StringVar(value=self.ths_sentiment_trend_var.get())
        rb = ttk.Frame(f)
        rb.pack(anchor=tk.W, pady=(14, 10))
        for t in ("上行", "震荡", "下行"):
            ttk.Radiobutton(rb, text=t, variable=var, value=t).pack(side=tk.LEFT, padx=(0, 18))
        def on_ok():
            self._save_ths_sentiment_trend(var.get())
            top.destroy()
        bf = ttk.Frame(f)
        bf.pack(anchor=tk.E, pady=(6, 0))
        ttk.Button(bf, text="确定", command=on_ok, width=10).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(bf, text="稍后", command=top.destroy, width=10).pack(side=tk.RIGHT)
        top.protocol("WM_DELETE_WINDOW", top.destroy)
        try:
            top.lift()
            top.attributes("-topmost", True)
            top.after(300, lambda: top.attributes("-topmost", False))
            top.focus_force()
        except Exception:
            pass


    def update_sentiment_indicator(self, sentiment):
        """更新右下角情绪指标(文本颜色 + 红黄绿灯)"""
        try:
            if not hasattr(self, 'sentiment_canvas') or not hasattr(self, 'sentiment_value_label'):
                return
            if not self.sentiment_canvas.winfo_exists() or not self.sentiment_value_label.winfo_exists():
                return
            # 文本映射与颜色
            sentiment_text = str(sentiment or "中性")
            sentiment_map = {
                "积极": ("积极", "red"),
                "偏积极": ("偏积极", "red"),
                "消极": ("消极", "green"),
                "偏消极": ("偏消极", "green"),
                "中性": ("中性", "orange"),
            }
            display_text, color = sentiment_map.get(sentiment_text, ("中性", "orange"))
            self.sentiment_value_label.configure(text=display_text, foreground=color)
            # 画红黄绿灯
            self.sentiment_canvas.delete("all")
            # 背板
            self.sentiment_canvas.create_rectangle(5, 5, 55, 79, outline="#b0b0b0", width=1)
            # 判断哪个灯亮
            active = "yellow"
            if color == "red":
                active = "red"
            elif color == "green":
                active = "green"
            else:
                active = "yellow"
            # 颜色定义
            on_colors = {"red": "#ff4040", "yellow": "#ffbf00", "green": "#4cd964"}
            off_color = "#d0d0d0"
            # 逐个绘制
            for name, (cx, cy, r) in self._sentiment_lights.items():
                fill = on_colors[name] if name == active else off_color
                self.sentiment_canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline="#888888")
        except Exception as _:
            # 静默失败,避免影响主流程
            pass


    def _removed_start_etf_comprehensive_monitoring(self):
        """启动ETF全面监控"""
        try:
            # 创建ETF监控窗口
            etf_window = self._safe_toplevel(self.root)
            etf_window.title("🚀 ETF全面监控")
            etf_window.geometry("1200x800")
            etf_window.configure(bg='white')
            # 创建滚动框架
            canvas = tk.Canvas(etf_window, bg='white')
            scrollbar = ttk.Scrollbar(etf_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 标题
            title_frame = ttk.Frame(scrollable_frame)
            title_frame.pack(fill=tk.X, pady=10)
            ttk.Label(title_frame, text="🚀 ETF全面监控",
                     font=("Arial", 16, "bold")).pack()
            # 控制按钮
            control_frame = ttk.Frame(scrollable_frame)
            control_frame.pack(fill=tk.X, pady=10)
            ttk.Button(control_frame, text="🔄 刷新数据",
                      command=lambda: self.load_etf_data(scrollable_frame)).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(control_frame, text="📊 统计分析",
                      command=lambda: self.show_etf_statistics()).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(control_frame, text="💾 导出数据",
                      command=lambda: self.export_etf_data()).pack(side=tk.LEFT)
            # 加载ETF数据
            self.load_etf_data(scrollable_frame)
            # 布局
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
        except Exception as e:
            print(f"启动ETF监控失败: {e}")


    def _removed_load_etf_data(self, parent_frame):
        """加载ETF数据"""
        try:
            # 清除现有数据
            for widget in parent_frame.winfo_children():
                if isinstance(widget, ttk.LabelFrame) and "ETF数据" in widget.cget("text"):
                    widget.destroy()
            # 显示加载状态
            loading_label = ttk.Label(parent_frame, text="🔄 正在加载ETF数据...",
                                    font=("Arial", 12), foreground="blue")
            loading_label.pack(pady=20)
            parent_frame.update()
            # 获取ETF数据
            etf_data = []  # ETF数据获取功能已移除
            # 移除加载标签
            loading_label.destroy()
            if not etf_data:
                error_label = ttk.Label(parent_frame, text="❌ 获取ETF数据失败",
                                      font=("Arial", 12), foreground="red")
                error_label.pack(pady=20)
                return
            # 创建ETF数据显示区域
            etf_frame = ttk.LabelFrame(parent_frame, text=f"📊 ETF实时数据 (共{len(etf_data)}个)", padding=10)
            etf_frame.pack(fill=tk.X, pady=10)
            # 统计信息
            up_count = len([etf for etf in etf_data if etf.get('涨跌幅', 0) > 0])
            down_count = len([etf for etf in etf_data if etf.get('涨跌幅', 0) < 0])
            flat_count = len(etf_data) - up_count - down_count
            stats_frame = ttk.Frame(etf_frame)
            stats_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(stats_frame, text=f"总计: {len(etf_data)}个", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 20))
            ttk.Label(stats_frame, text=f"上涨: {up_count}个", font=("Arial", 10), foreground="red").pack(side=tk.LEFT, padx=(0, 20))
            ttk.Label(stats_frame, text=f"下跌: {down_count}个", font=("Arial", 10), foreground="green").pack(side=tk.LEFT, padx=(0, 20))
            ttk.Label(stats_frame, text=f"平盘: {flat_count}个", font=("Arial", 10), foreground="gray").pack(side=tk.LEFT)
            # 表头
            header_frame = ttk.Frame(etf_frame)
            header_frame.pack(fill=tk.X, pady=(0, 5))
            headers = ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "换手率", "市盈率"]
            widths = [8, 15, 8, 8, 8, 10, 10, 8, 8]
            for header, width in zip(headers, widths):
                ttk.Label(header_frame, text=header, font=("Arial", 10, "bold"), width=width).pack(side=tk.LEFT)
            # 分隔线
            separator = ttk.Separator(etf_frame, orient='horizontal')
            separator.pack(fill=tk.X, pady=2)
            # ETF数据
            for etf in etf_data:
                row_frame = ttk.Frame(etf_frame)
                row_frame.pack(fill=tk.X, pady=1)
                code = etf.get('代码', '')
                name = etf.get('名称', '')
                price = etf.get('最新价', 0)
                change_pct = etf.get('涨跌幅', 0)
                change_amt = etf.get('涨跌额', 0)
                volume = etf.get('成交量', 0)
                amount = etf.get('成交额', 0)
                turnover = etf.get('换手率', 0)
                pe = etf.get('市盈率', 0)
                # 涨跌幅颜色
                change_color = "red" if change_pct > 0 else "green" if change_pct < 0 else "black"
                data_items = [
                    (code, 8, "black"),
                    (name, 15, "black"),
                    (f"{price:.2f}", 8, "black"),
                    (f"{change_pct:+.2f}%", 8, change_color),
                    (f"{change_amt:+.2f}", 8, change_color),
                    (f"{volume/10000:.1f}万", 10, "black"),
                    (f"{amount/100000000:.1f}亿", 10, "black"),
                    (f"{turnover:.2f}%", 8, "black"),
                    (f"{pe:.2f}", 8, "black")
                ]
                for text, width, color in data_items:
                    ttk.Label(row_frame, text=text, width=width, foreground=color).pack(side=tk.LEFT)
            # 更新时间
            update_time = ttk.Label(parent_frame, text=f"📅 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                  font=("Arial", 10), foreground="gray")
            update_time.pack(pady=(10, 0))
        except Exception as e:
            print(f"加载ETF数据失败: {e}")


    def _removed_show_etf_statistics(self):
        """显示ETF统计分析"""
        try:
            etf_data = []  # ETF数据获取功能已移除
            if not etf_data:
                print("没有ETF数据可分析")
                return
            # 创建统计窗口
            stats_window = self._safe_toplevel(self.root)
            stats_window.title("📊 ETF统计分析")
            stats_window.geometry("800x600")
            # 统计计算
            up_etfs = [etf for etf in etf_data if etf.get('涨跌幅', 0) > 0]
            down_etfs = [etf for etf in etf_data if etf.get('涨跌幅', 0) < 0]
            avg_change = sum(etf.get('涨跌幅', 0) for etf in etf_data) / len(etf_data)
            max_gain = max(etf.get('涨跌幅', 0) for etf in etf_data)
            max_loss = min(etf.get('涨跌幅', 0) for etf in etf_data)
            # 显示统计结果
            ttk.Label(stats_window, text="📊 ETF统计分析", font=("Arial", 16, "bold")).pack(pady=10)
            stats_text = f"""
📈 总体统计:
• 总ETF数量: {len(etf_data)}个
• 上涨ETF: {len(up_etfs)}个 ({len(up_etfs)/len(etf_data)*100:.1f}%)
• 下跌ETF: {len(down_etfs)}个 ({len(down_etfs)/len(etf_data)*100:.1f}%)
• 平均涨跌幅: {avg_change:.2f}%
📊 涨跌统计:
• 最大涨幅: {max_gain:.2f}%
• 最大跌幅: {max_loss:.2f}%
🔥 涨幅榜前5:
"""
            # 涨幅榜
            top_gainers = sorted(etf_data, key=lambda x: x.get('涨跌幅', 0), reverse=True)[:5]
            for i, etf in enumerate(top_gainers, 1):
                stats_text += f"{i}. {etf.get('名称', '')} ({etf.get('代码', '')}): {etf.get('涨跌幅', 0):+.2f}%\n"
            stats_text += "\n📉 跌幅榜前5:\n"
            # 跌幅榜
            top_losers = sorted(etf_data, key=lambda x: x.get('涨跌幅', 0))[:5]
            for i, etf in enumerate(top_losers, 1):
                stats_text += f"{i}. {etf.get('名称', '')} ({etf.get('代码', '')}): {etf.get('涨跌幅', 0):+.2f}%\n"
            # 显示统计文本
            text_widget = tk.Text(stats_window, wrap=tk.WORD, font=("Arial", 11))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert(tk.END, stats_text)
            text_widget.config(state=tk.DISABLED)
        except Exception as e:
            print(f"显示ETF统计失败: {e}")


    def _removed_export_etf_data(self):
        """导出ETF数据"""
        try:
            etf_data = []  # ETF数据获取功能已移除
            if not etf_data:
                print("没有ETF数据可导出")
                return
            # 保存为CSV文件
            filename = f"etf_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            import pandas as pd
            df = pd.DataFrame(etf_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"ETF数据已导出到: {filename}")
        except Exception as e:
            print(f"导出ETF数据失败: {e}")


    def _get_crash_alert_snapshot(self):
        """计算最近20交易日三指数平均跌幅;当平均跌幅 <= -15% 触发暴跌提示。"""
        crash_index_defs = [
            ("上证300", "sh000300", "000300.SH"),
            ("中证500", "sh000905", "000905.SH"),
            ("科创30(用科创50近似)", "sh000688", "000688.SH"),
        ]
        extra_index_defs = [
            ("上证指数(000001)", "sh000001", "000001.SH"),
            ("中证指数(用中证1000近似)", "sh000852", "000852.SH"),
            ("创业板指(399006)", "sz399006", "399006.SZ"),
        ]
        all_index_defs = crash_index_defs + extra_index_defs
        out = {"indices": {}, "extra_indices": {}, "avg_drop_pct": None, "is_crash": False, "source": "未获取"}
        crash_vals = []
        all_values = {}
        # 1) 优先 AKShare
        try:
            if AKSHARE_AVAILABLE:
                for name, ak_symbol, _ in all_index_defs:
                    df = ak.stock_zh_index_daily(symbol=ak_symbol)
                    if df is None or len(df) < 21:
                        continue
                    close_col = "close" if "close" in df.columns else ("收盘" if "收盘" in df.columns else None)
                    if close_col is None:
                        continue
                    s = pd.to_numeric(df[close_col], errors="coerce").dropna().values
                    if len(s) < 21:
                        continue
                    pct = (float(s[-1]) / float(s[-21]) - 1.0) * 100.0
                    all_values[name] = pct
                if all_values:
                    out["source"] = "AKShare"
        except Exception as e:
            print(f"[暴跌提示] AKShare 计算失败: {e}")
        # 2) 回退 Tushare
        if not all_values:
            try:
                if TS_AVAILABLE and (getattr(self, "ts_token", None) or TS_DEFAULT_TOKEN):
                    self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
                    end_date = datetime.now().strftime("%Y%m%d")
                    for name, _, ts_code in all_index_defs:
                        df = self.ts_client.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                        if df is None or df.empty or "trade_date" not in df.columns:
                            continue
                        df = df.sort_values("trade_date")
                        close_col = "close" if "close" in df.columns else None
                        if close_col is None:
                            continue
                        s = pd.to_numeric(df[close_col], errors="coerce").dropna().values
                        if len(s) < 21:
                            continue
                        pct = (float(s[-1]) / float(s[-21]) - 1.0) * 100.0
                        all_values[name] = pct
                    if all_values:
                        out["source"] = "Tushare"
            except Exception as e:
                print(f"[暴跌提示] Tushare 回退失败: {e}")
        for name, _, _ in crash_index_defs:
            if name in all_values:
                out["indices"][name] = all_values[name]
                crash_vals.append(all_values[name])
        for name, _, _ in extra_index_defs:
            if name in all_values:
                out["extra_indices"][name] = all_values[name]
        if crash_vals:
            avg = float(sum(crash_vals) / len(crash_vals))
            out["avg_drop_pct"] = avg
            out["is_crash"] = avg <= -15.0
        return out


    def _save_crash_alert_snapshot_to_news(self):
        """将当前暴跌快照记录到资讯表。"""
        info = self._get_crash_alert_snapshot()
        avg = info.get("avg_drop_pct")
        lines = [
            "暴跌提示快照",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"数据源: {info.get('source', '未获取')}",
        ]
        for k, v in info.get("indices", {}).items():
            lines.append(f"{k}: {v:+.2f}%")
        for k, v in info.get("extra_indices", {}).items():
            lines.append(f"{k}: {v:+.2f}%")
        lines.append(f"平均跌幅(20交易日): {'未获取' if avg is None else f'{avg:+.2f}%'}")
        lines.append(f"是否触发暴跌提示: {'是' if info.get('is_crash') else '否'}")
        content = "\n".join(lines)
        tab_name = f"暴跌提示_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ok = save_news_info_to_db(tab_name, content)
        if ok:
            messagebox.showinfo("成功", f"已保存到资讯表:{tab_name}", parent=self.root)
        else:
            messagebox.showerror("错误", "保存暴跌快照失败", parent=self.root)


    def _prediction_fetch_ths_sentiment_daily(self):
        """拉取同花顺情绪指数概念日线,判断最新一日相对前一日的方向(1日线向上/向下)。"""
        from datetime import datetime, timedelta
        try:
            import akshare as ak
        except Exception:
            return None, "当前环境未安装 akshare,无法自动拉取同花顺情绪指数日线。"
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=55)).strftime("%Y%m%d")
        for sym in ("同花顺情绪指数", "883404"):
            try:
                df = ak.stock_board_concept_hist_em(
                    symbol=sym, period="daily", start_date=start, end_date=end
                )
                if df is None or len(df) < 2:
                    continue
                dcol = df.columns[0]
                close_col = None
                for c in df.columns:
                    if "收盘" in str(c):
                        close_col = c
                        break
                if close_col is None:
                    num_cols = [c for c in df.columns if str(df[c].dtype).startswith(("float", "int"))]
                    close_col = num_cols[-1] if num_cols else df.columns[-1]
                c0 = float(df.iloc[-2][close_col])
                c1 = float(df.iloc[-1][close_col])
                d0 = str(df.iloc[-2][dcol])
                d1 = str(df.iloc[-1][dcol])
                if c1 > c0:
                    direction = "向上 ↑(最新交易日收盘高于前一交易日,1日线方向视为向上)"
                    ma1_up = True
                elif c1 < c0:
                    direction = "向下 ↓(最新交易日收盘低于前一交易日)"
                    ma1_up = False
                else:
                    direction = "走平(两日收盘相同)"
                    ma1_up = False
                txt = (
                    f"同花顺情绪指数(东方财富概念板块「{sym}」日线)\n"
                    f"  {d0} 收盘: {c0:.4f}\n"
                    f"  {d1} 收盘: {c1:.4f}\n"
                    f"  1日线方向(相对前一交易日): {direction}"
                )
                return txt, ma1_up
            except Exception:
                continue
        return None, "未能拉取同花顺情绪指数日线(网络异常或接口变更)。可在同花顺/东财查看概念「同花顺情绪指数」883404。"


    def _collect_realtime_world_us_snapshot_bundle(self):
        """返回 (快讯以上正文, 快讯行列表[{line,url}], 快讯以下正文)。链接仅存在 url 字段,不写入 line。"""
        if not AKSHARE_AVAILABLE:
            return ("当前环境未安装 AKShare,请 pip install akshare 后重试。\n", [], "")
        import akshare as ak
        lines = []
        lines.append(
            "【隔夜外围 · 美股收盘 · 中概 · 快讯】"
            + datetime.now().strftime(" %Y-%m-%d %H:%M:%S")
        )
        lines.append(
            "说明:标普/道指/纳指为新浪指数日线(上一交易日收盘涨跌);东财「知名美股」有延迟;"
            "中概股从各分类列表中按名称关键词筛选;快讯含东财聚合的国内外主流来源、财新周刊流与市场关键词检索。"
            "「利好板块与龙头」需结合 A 股盘面,下方给问财示例与 Skill 入口。"
        )
        lines.append("")
        def _block(title: str, body: str):
            lines.append(f"══ {title} ══")
            lines.append(body if (body or "").strip() else "(无)")
            lines.append("")
        # -- 美股三大指数(新浪日线)--
        idx_lines = []
        for sym, cn in [
            (".INX", "标普500"),
            (".DJI", "道琼斯"),
            (".IXIC", "纳斯达克综合"),
        ]:
            try:
                df = ak.index_us_stock_sina(symbol=sym)
                if df is None or len(df) < 2:
                    idx_lines.append(f"  • {cn}:数据不足")
                    continue
                prev_r, last_r = df.iloc[-2], df.iloc[-1]
                c0 = float(prev_r["close"])
                c1 = float(last_r["close"])
                pct = (c1 - c0) / c0 * 100.0 if c0 else 0.0
                d = str(last_r.get("date", ""))
                idx_lines.append(f"  • {cn}  {d}  收 {c1:.2f}  较前一日 {pct:+.2f}%")
            except Exception as e:
                idx_lines.append(f"  • {cn}:{e}")
        _block("美股主要指数(隔夜收盘涨跌)", "\n".join(idx_lines))
        # -- 美股知名分类(东财)涨跌与领涨领跌 --
        cats = [
            ("科技类", "科技"),
            ("金融类", "金融"),
            ("医药食品类", "医药消费"),
            ("媒体类", "媒体"),
            ("汽车能源类", "汽车能源"),
            ("制造零售类", "制造零售"),
        ]
        cat_buf = []
        for sym_cn, short in cats:
            try:
                df = ak.stock_us_famous_spot_em(symbol=sym_cn)
                if df is None or df.empty:
                    cat_buf.append(f"【{short}】(空表)")
                    continue
                p = pd.to_numeric(df["涨跌幅"], errors="coerce")
                df2 = df.assign(_p=p).dropna(subset=["_p"])
                if df2.empty:
                    cat_buf.append(f"【{short}】无数值")
                    continue
                mean_p = float(df2["_p"].mean())
                top2 = df2.nlargest(2, "_p")
                bot2 = df2.nsmallest(2, "_p")
                t0 = f"{top2.iloc[0]['名称']} {float(top2.iloc[0]['_p']):+.2f}%"
                b0 = f"{bot2.iloc[0]['名称']} {float(bot2.iloc[0]['_p']):+.2f}%"
                cat_buf.append(f"【{short}】平均 {mean_p:+.2f}%  领涨 {t0}  领跌 {b0}")
            except Exception as e:
                cat_buf.append(f"【{short}】{e}")
        _block("美股板块/分类涨跌(东财知名美股六大类)", "\n".join(cat_buf))
        # -- 中概代表:合并分类去重后按名称关键词筛选 --
        zg_kw = (
            "阿里|京东|拼多|百度|网易|哔哩|蔚来|理想|小鹏|携程|新东方|爱奇艺|贝壳|富途|"
            "唯品|叮咚|腾讯音乐|金山云|华住|中通|再鼎|新氧|好未来|高途|叮咚|名创"
        )
        zg_buf = []
        try:
            merged = []
            for sym_cn, _ in cats:
                try:
                    df = ak.stock_us_famous_spot_em(symbol=sym_cn)
                    if df is not None and not df.empty:
                        merged.append(df)
                except Exception:
                    continue
            if not merged:
                zg_buf.append("(各分类均未取到表)")
            else:
                all_df = pd.concat(merged, ignore_index=True)
                name_col = "名称" if "名称" in all_df.columns else all_df.columns[0]
                all_df = all_df.drop_duplicates(subset=[name_col])
                m = all_df[name_col].astype(str).str.contains(zg_kw, regex=True, na=False)
                zg = all_df.loc[m].copy()
                zg["_p"] = pd.to_numeric(zg.get("涨跌幅"), errors="coerce")
                zg = zg.sort_values("_p", ascending=False, na_position="last")
                show_cols = [c for c in ["名称", "涨跌幅", "最新价", "代码"] if c in zg.columns]
                if show_cols and not zg.empty:
                    zg_buf.append(zg[show_cols].head(22).to_string(index=False))
                else:
                    zg_buf.append("(未匹配到中概关键词,可改东财美股页面核对名称)")
        except Exception as e:
            zg_buf.append(str(e))
        _block("中概代表股(名称关键词筛选 · 仅供参考)", "\n".join(zg_buf))
        # -- 快讯:国内外主流(东财关键词)+ 财新 + 市场关键词;URL 由弹窗 tag 绑定 --
        news_items = []
        seen_urls = set()
        mainstream_domestic = ["新华社", "人民日报", "经济日报", "央视新闻", "中国证券报"]
        mainstream_global = ["路透", "彭博", "华尔街", "华尔街日报", "英国金融时报"]
        for kw in mainstream_domestic:
            self._append_stock_news_em_rows(
                ak, news_items, seen_urls, kw, f"国内·{kw}", max_rows=2
            )
        for kw in mainstream_global:
            self._append_stock_news_em_rows(
                ak, news_items, seen_urls, kw, f"国际·{kw}", max_rows=2
            )
        if news_items:
            news_items.append({"line": "══ 财新 / 市场关键词快讯 ══", "url": None})
        try:
            cx = safe_call(ak.stock_news_main_cx, fallback=[], label="ak.stock_news_main_cx")
            if cx is not None and not cx.empty:
                n = min(18, len(cx))
                for i in range(n):
                    row = cx.iloc[i]
                    summ = str(row.get("summary", row.get("tag", "")))[:200]
                    uu = self._normalize_news_item_url(row.get("url"))
                    if not uu:
                        uu = self._url_from_series_any_cell(row)
                    if uu and uu in seen_urls:
                        continue
                    if uu:
                        seen_urls.add(uu)
                    news_items.append({"line": f"  · [财新] {summ}", "url": uu})
        except Exception as e:
            news_items.append({"line": f"财新流:{e}", "url": None})
        keywords = ["美股", "美联储", "英伟达", "纳斯达克", "加息", "关税", "原油"]
        for kw in keywords[:5]:
            self._append_stock_news_em_rows(
                ak, news_items, seen_urls, kw, kw, max_rows=3
            )
        head = (
            "\n".join(lines)
            + "\n══ 实时/隔夜相关快讯(摘要 · 点击蓝色行打开原文,链接不单独显示)══\n"
        )
        if not news_items:
            news_items = [{"line": "(无)", "url": None}]
        tail_lines = []
        def _block_tail(title: str, body: str):
            tail_lines.append(f"══ {title} ══")
            tail_lines.append(body if (body or "").strip() else "(无)")
            tail_lines.append("")
        hot_buf = []
        try:
            hr = safe_call(ak.stock_hot_rank_em, fallback=pd.DataFrame(), label="ak.stock_hot_rank_em")
            if hr is not None and not hr.empty:
                cols = [c for c in hr.columns if str(c) in ("代码", "股票代码", "股票名称", "涨跌幅", "最新价")]
                if not cols:
                    cols = list(hr.columns)[:6]
                hot_buf.append(hr[cols].head(15).to_string(index=False))
        except Exception as e:
            hot_buf.append(f"东财热榜未取到(可忽略):{e}")
        _block_tail("A 股人气榜参考(同日情绪,非隔夜因果)", "\n".join(hot_buf))
        tail_lines.append("══ 利好哪些 A 股板块与龙头(怎么用问财 / Skill)══")
        tail_lines.append(
            "程序无法自动断言「新闻→板块→龙头」因果,请用左侧「Skill」或下方问财链接,"
            "结合上方美股分类强弱自行检索:"
        )
        tail_lines.append("  · 美股科技强 → 可搜:半导体、消费电子、人工智能、通信设备 概念 今日涨幅 龙头")
        tail_lines.append("  · 美股金融强 → 银行、保险、券商")
        tail_lines.append("  · 汽车能源强 → 新能源车、锂电池、光伏、煤炭石油")
        tail_lines.append("  · 医药消费强 → 创新药、CRO、白酒、食品饮料")
        tail_lines.append("")
        tail_lines.append("问财示例(复制到 Skill 通用问财):")
        tail_lines.append("  「今日主力资金净流入前10的行业板块,每个板块列出涨幅第一的非ST股票」")
        tail_lines.append("  「半导体概念,今日涨跌幅排名,前8名,非ST」")
        tail_lines.append("  「中概股相关A股概念,今日涨幅排名」")
        tail_lines.append("")
        tail = "\n".join(tail_lines)
        return head, news_items, tail


    def _collect_realtime_world_us_snapshot(self) -> str:
        """纯文本版(快讯行为纯文字,无隐藏链接),供需要整段字符串的场景。"""
        h, items, t = self._collect_realtime_world_us_snapshot_bundle()
        mid = "\n".join(x.get("line", "") for x in items) + "\n\n"
        return h + mid + t


    def _plot_sentiment_chart_on_ax(self, ax, spec):
        """在单个 axes 上画一类情绪指标(spec: kind/title/df)。"""
        kind = spec.get("kind")
        df = spec.get("df")
        title = spec.get("title", "")
        ax.set_title(title, fontsize=9)
        if df is None or getattr(df, "empty", True):
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", transform=ax.transAxes, fontsize=9)
            ax.set_axis_off()
            return
        try:
            if kind == "breadth":
                # AKShare stock_market_activity_legu 多为长表:item / value(「上涨」等在单元格)
                if "item" in df.columns and "value" in df.columns:
                    items = df["item"].astype(str)
                    mask = items.str.contains(
                        "上涨|下跌|平盘|停牌|涨停|跌停|真实涨停|持平", regex=True, na=False
                    )
                    sub_df = df.loc[mask] if mask.any() else df.head(12)
                    labels = sub_df["item"].astype(str).tolist()
                    vals_l = pd.to_numeric(sub_df["value"], errors="coerce").fillna(0.0).tolist()
                    colors = []
                    for lab in labels:
                        if "涨" in lab and "跌" not in lab:
                            colors.append("#e74c3c")
                        elif "跌" in lab:
                            colors.append("#2ecc71")
                        else:
                            colors.append("#95a5a6")
                    if labels:
                        ax.bar(range(len(labels)), vals_l, color=colors)
                        ax.set_xticks(range(len(labels)))
                        ax.set_xticklabels(labels, rotation=22, fontsize=7)
                        ax.set_ylabel("数值", fontsize=8)
                    else:
                        ax.text(0.5, 0.5, "无可用行", ha="center", va="center", transform=ax.transAxes)
                        ax.set_axis_off()
                    return
                row = df.iloc[-1]
                labels, vals, colors = [], [], []
                for c in df.columns:
                    cs = str(c)
                    if not any(k in cs for k in ("上涨", "下跌", "平盘", "停牌", "持平")):
                        continue
                    v = pd.to_numeric(row[c], errors="coerce")
                    if pd.isna(v):
                        continue
                    short = cs.replace("家数", "").replace("股票", "").strip()[:10]
                    labels.append(short)
                    vals.append(float(v))
                    if "涨" in short and "跌" not in short:
                        colors.append("#e74c3c")
                    elif "跌" in short:
                        colors.append("#2ecc71")
                    else:
                        colors.append("#95a5a6")
                if labels:
                    ax.bar(range(len(labels)), vals, color=colors or "#3498db")
                    ax.set_xticks(range(len(labels)))
                    ax.set_xticklabels(labels, rotation=18, fontsize=7)
                    ax.set_ylabel("家数", fontsize=8)
                else:
                    ax.text(0.5, 0.5, "列结构未识别", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
                return
            if kind == "north":
                date_c = None
                for c in df.columns:
                    if "日期" in str(c) or "时间" in str(c):
                        date_c = c
                        break
                if date_c is None:
                    date_c = df.columns[0]
                val_c = None
                for c in df.columns:
                    if c == date_c:
                        continue
                    sc = str(c)
                    if any(k in sc for k in ("净流", "净买", "流入", "成交净", "净流入")):
                        val_c = c
                        break
                if val_c is None:
                    for c in df.columns[1:]:
                        s = pd.to_numeric(df[c], errors="coerce")
                        if s.notna().sum() > len(df) * 0.5:
                            val_c = c
                            break
                if val_c:
                    y = pd.to_numeric(df[val_c], errors="coerce")
                    ax.plot(range(len(y)), y.values, color="#2980b9", marker="o", markersize=2, linewidth=1.1)
                    ax.axhline(0, color="gray", linewidth=0.4, linestyle="--")
                    step = max(1, len(df) // 5)
                    ticks = list(range(0, len(df), step))
                    ax.set_xticks(ticks)
                    xlabels = [str(df[date_c].iloc[j])[:10] for j in ticks]
                    ax.set_xticklabels(xlabels, rotation=22, fontsize=6)
                    ylab = str(val_c)[:12] + ("..." if len(str(val_c)) > 12 else "")
                    ax.set_ylabel(ylab, fontsize=7)
                else:
                    ax.text(0.5, 0.5, "无数值列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
            elif kind == "index_barh":
                name_c = "名称" if "名称" in df.columns else df.columns[0]
                pct_c = None
                for c in df.columns:
                    sc = str(c)
                    if "涨跌幅" in sc or "涨跌额" == sc:
                        pct_c = c
                        break
                if pct_c is None:
                    for c in df.columns:
                        sc = str(c)
                        if "涨跌" in sc and "家" not in sc:
                            pct_c = c
                            break
                if pct_c:
                    names = df[name_c].astype(str).tolist()
                    pcts = pd.to_numeric(df[pct_c], errors="coerce").fillna(0.0).tolist()
                    y_pos = np.arange(len(names))
                    bar_colors = ["#e74c3c" if p >= 0 else "#3498db" for p in pcts]
                    ax.barh(y_pos, pcts, color=bar_colors, height=0.55)
                    ax.set_yticks(y_pos)
                    ax.set_yticklabels(names, fontsize=7)
                    ax.axvline(0, color="gray", linewidth=0.5)
                    ax.set_xlabel("涨跌幅 %", fontsize=7)
                else:
                    ax.text(0.5, 0.5, "无涨跌幅列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
            elif kind == "bond_lines":
                date_c = "日期" if "日期" in df.columns else df.columns[0]
                series_cols = []
                for c in df.columns:
                    if c == date_c:
                        continue
                    sc = str(c)
                    if ("10" in sc or "十" in sc) and any(
                        k in sc for k in ("债", "收益", "国债", "美债", "美国", "中国")
                    ):
                        series_cols.append(c)
                if len(series_cols) < 2:
                    series_cols = [c for c in df.columns if c != date_c][:4]
                for c in series_cols[:4]:
                    y = pd.to_numeric(df[c], errors="coerce")
                    ax.plot(range(len(df)), y, label=str(c)[:16], linewidth=1)
                ax.legend(fontsize=5, loc="best")
                ax.set_ylabel("%", fontsize=7)
                step = max(1, len(df) // 4)
                ticks = list(range(0, len(df), step))
                ax.set_xticks(ticks)
                ax.set_xticklabels([str(df[date_c].iloc[j])[:10] for j in ticks], rotation=16, fontsize=6)
            elif kind in ("pizza_line", "us_equity_line"):
                date_c = (
                    "日期"
                    if "日期" in df.columns
                    else ("date" if "date" in df.columns else df.columns[0])
                )
                val_c = None
                for c in ("收盘", "close"):
                    if c in df.columns:
                        val_c = c
                        break
                if val_c is None:
                    for c in df.columns:
                        if c != date_c:
                            val_c = c
                            break
                if val_c:
                    y = pd.to_numeric(df[val_c], errors="coerce")
                    ax.plot(range(len(df)), y.values, color="#e67e22", linewidth=1.2)
                    step = max(1, len(df) // 4)
                    ticks = list(range(0, len(df), step))
                    ax.set_xticks(ticks)
                    ax.set_xticklabels(
                        [str(df[date_c].iloc[j])[:10] for j in ticks], rotation=18, fontsize=6
                    )
                    ax.set_ylabel("美元", fontsize=7)
                else:
                    ax.text(0.5, 0.5, "无收盘价列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
            elif kind == "us10y_line":
                date_c = "日期" if "日期" in df.columns else df.columns[0]
                col = None
                for c in df.columns:
                    if c == date_c:
                        continue
                    sc = str(c)
                    if "美国" in sc and "10" in sc and "债" in sc:
                        col = c
                        break
                if col is None:
                    for c in df.columns:
                        if c != date_c:
                            col = c
                            break
                if col:
                    y = pd.to_numeric(df[col], errors="coerce")
                    ax.plot(range(len(df)), y.values, color="#1a5276", linewidth=1.3)
                    ax.set_ylabel("%", fontsize=7)
                    step = max(1, len(df) // 4)
                    ticks = list(range(0, len(df), step))
                    ax.set_xticks(ticks)
                    ax.set_xticklabels(
                        [str(df[date_c].iloc[j])[:10] for j in ticks], rotation=16, fontsize=6
                    )
                else:
                    ax.text(0.5, 0.5, "无美债10年列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
            elif kind == "polymarket_barh":
                name_c = "问题" if "问题" in df.columns else df.columns[0]
                val_c = "Yes概率%" if "Yes概率%" in df.columns else None
                if val_c is None:
                    for c in df.columns:
                        if c != name_c:
                            val_c = c
                            break
                if val_c:
                    names = df[name_c].astype(str).tolist()
                    pcts = pd.to_numeric(df[val_c], errors="coerce").fillna(0.0).tolist()
                    y_pos = np.arange(len(names))
                    ax.barh(y_pos, pcts, color="#8e44ad", height=0.5)
                    ax.set_yticks(y_pos)
                    ax.set_yticklabels(names, fontsize=6)
                    ax.set_xlabel(str(val_c)[:16], fontsize=7)
                    ax.set_xlim(0, max(100.0, max(pcts) * 1.08 if pcts else 100.0))
                else:
                    ax.text(0.5, 0.5, "无数值列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
            elif kind == "date_multi_line":
                date_c = spec.get("date_col")
                if not date_c or date_c not in df.columns:
                    date_c = df.columns[0]
                val_cols = [c for c in (spec.get("value_cols") or []) if c in df.columns]
                if not val_cols:
                    ax.text(0.5, 0.5, "无数值列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
                else:
                    colors = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad"]
                    for i, c in enumerate(val_cols[:4]):
                        y = pd.to_numeric(df[c], errors="coerce")
                        ax.plot(
                            range(len(df)),
                            y.values,
                            label=str(c)[:14],
                            color=colors[i % len(colors)],
                            linewidth=1.0,
                        )
                    ax.legend(fontsize=5, loc="best")
                    step = max(1, len(df) // 4)
                    ticks = list(range(0, len(df), step))
                    ax.set_xticks(ticks)
                    ax.set_xticklabels(
                        [str(df[date_c].iloc[j])[:12] for j in ticks], rotation=16, fontsize=6
                    )
                    ylab = spec.get("ylabel") or ""
                    if ylab:
                        ax.set_ylabel(ylab, fontsize=7)
            elif kind == "month_line":
                mc = spec.get("month_col")
                vc = spec.get("value_col")
                if (
                    not mc
                    or not vc
                    or mc not in df.columns
                    or vc not in df.columns
                ):
                    ax.text(0.5, 0.5, "列配置缺失", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
                else:
                    y = pd.to_numeric(df[vc], errors="coerce")
                    x = np.arange(len(df))
                    ax.plot(x, y.values, color="#16a085", linewidth=1.1, marker="o", markersize=2)
                    ax.set_xticks(x)
                    ax.set_xticklabels(df[mc].astype(str).tolist(), rotation=24, fontsize=5)
                    ax.set_ylabel(str(vc)[:18], fontsize=7)
            elif kind == "date_value_line":
                date_c = spec.get("date_col")
                if not date_c or date_c not in df.columns:
                    date_c = "日期" if "日期" in df.columns else df.columns[0]
                val_c = spec.get("value_col")
                if not val_c or val_c not in df.columns:
                    ax.text(0.5, 0.5, "无数值列", ha="center", va="center", transform=ax.transAxes)
                    ax.set_axis_off()
                else:
                    y = pd.to_numeric(df[val_c], errors="coerce")
                    ax.plot(range(len(df)), y.values, color="#d35400", linewidth=1.1)
                    step = max(1, len(df) // 4)
                    ticks = list(range(0, len(df), step))
                    ax.set_xticks(ticks)
                    ax.set_xticklabels(
                        [str(df[date_c].iloc[j])[:12] for j in ticks], rotation=16, fontsize=6
                    )
                    ax.set_ylabel(str(val_c)[:14], fontsize=7)
            else:
                ax.text(0.5, 0.5, "未知图类型", ha="center", va="center", transform=ax.transAxes)
                ax.set_axis_off()
        except Exception as ex:
            ax.text(0.5, 0.5, str(ex)[:100], ha="center", va="center", transform=ax.transAxes, fontsize=7)
            ax.set_axis_off()


    def _fetch_polymarket_hot_markets_snapshot(self, n=8):
        """Polymarket Gamma API:未关闭市场中取成交量居前若干条,解析 Yes 报价(0-100%)。"""
        import json
        try:
            r = requests.get(
                "https://gamma-api.polymarket.com/markets",
                params={"limit": "120", "closed": "false", "active": "true"},
                timeout=12,
            )
            if r.status_code != 200:
                return f"(HTTP {r.status_code})", None
            data = r.json()
            if not isinstance(data, list):
                return "(返回非列表)", None
            rows = []
            for m in data:
                try:
                    if m.get("closed") is True:
                        continue
                    q = (m.get("question") or "").strip()
                    if not q:
                        continue
                    raw = m.get("outcomePrices") or "[]"
                    if isinstance(raw, str):
                        prices = json.loads(raw)
                    else:
                        prices = raw
                    if not prices:
                        continue
                    yes = float(prices[0]) * 100.0
                    vol = float(m.get("volumeNum") or m.get("volume") or 0)
                    rows.append((vol, q[:52], yes))
                except Exception:
                    continue
            rows.sort(key=lambda x: x[0], reverse=True)
            picked = rows[: max(4, min(n, 12))]
            if not picked:
                return "(无可用未结市场)", None
            df = pd.DataFrame(
                [{"问题": x[1], "Yes概率%": round(x[2], 2)} for x in picked]
            )
            txt = df.to_string(index=False)
            return txt, df
        except Exception as e:
            return f"(Polymarket 获取失败:{e})", None


    def _apply_market_sentiment_charts(self, fig, charts, scale=1.0):
        """按列表顺序绘制多格子图(默认 6 列),与左侧文本同源;缺数据子图显示「暂无数据」。
        scale:相对基础尺寸的放大系数,用于弹窗内「放大/缩小图示」。"""
        try:
            scale = float(scale)
        except Exception:
            scale = 1.0
        scale = max(0.65, min(2.2, scale))
        fig.clear()
        specs = [dict(c) for c in (charts or []) if isinstance(c, dict)]
        n = len(specs)
        if n == 0:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "暂无图表数据", ha="center", va="center", transform=ax.transAxes, fontsize=10)
            ax.set_axis_off()
            fig.set_size_inches(14.0 * scale, 7.5 * scale)
            fig.tight_layout(rect=[0, 0.02, 1, 0.96])
            return
        ncols = 6
        nrows = int(np.ceil(n / ncols))
        base_w, base_h = 15.0, max(7.2, nrows * 2.65)
        fig.set_size_inches(base_w * scale, base_h * scale)
        axs = fig.subplots(nrows, ncols, squeeze=False)
        total = nrows * ncols
        for idx in range(total):
            r, c = divmod(idx, ncols)
            ax = axs[r][c]
            if idx < n:
                self._plot_sentiment_chart_on_ax(ax, specs[idx])
                try:
                    ax._sentiment_chart_spec = specs[idx]
                except Exception:
                    pass
            else:
                ax.axis("off")
        fig.tight_layout(rect=[0, 0.02, 1, 0.97])


    def _get_market_sentiment_chart_help(self, spec):
        """市场情绪子图说明与外部参考链接(双击弹窗用);必要时标记需网络摘要补充。"""
        if not isinstance(spec, dict):
            spec = {}
        kind = str(spec.get("kind") or "")
        title = str(spec.get("title") or "指标").strip()
        needs_web = False
        web_query = None
        base_links = [
            ("东方财富", "https://www.eastmoney.com/"),
            ("国家统计局", "https://www.stats.gov.cn/"),
        ]
        body = (
            "图示数据与左侧「指标快照」同源,由 AKShare 等公开接口拉取;"
            "横轴多为时间序号或类别序号,纵轴为接口字段含义;仅供参考,不构成投资建议。"
        )
        links = list(base_links)
        def _add(*pairs):
            for lab, url in pairs:
                if (lab, url) not in links:
                    links.append((lab, url))
        US_EQ = {
            "SPY": (
                ("标普500 ETF(SPY):追踪标普 500 指数,常作美股大盘风险偏好的代理;"
                "与 A 股存在交易时段与制度差异,仅作全球权益情绪参照。"),
                (("雅虎财经 SPY", "https://finance.yahoo.com/quote/SPY"),),
            ),
            "QQQ": (
                "纳指100 ETF(QQQ):偏重科技成长,波动常高于标普;可观察全球成长股情绪外溢。",
                (("雅虎财经 QQQ", "https://finance.yahoo.com/quote/QQQ"),),
            ),
            "IWM": (
                "罗素2000 ETF(IWM):小盘风格代理,对利率与信用环境较敏感。",
                (("雅虎财经 IWM", "https://finance.yahoo.com/quote/IWM"),),
            ),
            "GLD": (
                "SPDR 黄金 ETF(GLD):黄金现货代理,常与避险、实际利率预期相关。",
                (("雅虎财经 GLD", "https://finance.yahoo.com/quote/GLD"),),
            ),
            "USO": (
                "原油 ETF(USO):油价波动代理,与全球通胀预期、地缘风险相关。",
                (("雅虎财经 USO", "https://finance.yahoo.com/quote/USO"),),
            ),
            "DBC": (
                "Invesco 商品指数 ETF(DBC):能源+农产品+金属等一篮子商品代理,可作康波长波中商品位置的实务参照(与单一品种周期不同)。",
                (("雅虎财经 DBC", "https://finance.yahoo.com/quote/DBC"),),
            ),
            "CPER": (
                "美国铜 ETF(CPER):铜价/工业金属代理,周期研究中常作全球制造业与资本开支情绪的同步指标之一。",
                (("雅虎财经 CPER", "https://finance.yahoo.com/quote/CPER"),),
            ),
            "UUP": (
                "美元指数 ETF(UUP):美元强弱代理,影响跨境资金与大宗商品报价。",
                (("雅虎财经 UUP", "https://finance.yahoo.com/quote/UUP"),),
            ),
            "VXX": (
                "短期波动率期货(VXX):恐慌情绪代理,与权益风险溢价相关,长期持有损耗大。",
                (("雅虎财经 VXX", "https://finance.yahoo.com/quote/VXX"),),
            ),
            "ITB": (
                "美股住宅建筑 ETF(ITB):美房建/住宅相关板块代理,可作全球地产链情绪参照。",
                (("雅虎财经 ITB", "https://finance.yahoo.com/quote/ITB"),),
            ),
        }
        if kind == "breadth":
            body = (
                "市场宽度:涨跌家数、涨跌停家数等反映全市场多空结构与情绪极端程度;"
                "上涨家数占优时常对应风险偏好偏高。"
            )
            _add(("同花顺行情", "https://www.10jqka.com.cn/"))
        elif kind == "north":
            body = "北向资金:沪深港通净流入反映外资对 A 股短期配置意愿;需结合汇率与外围市场解读。"
            _add(("港交所沪深港通", "https://www.hkex.com.hk/Mutual-Market/Stock-Connect?sc_lang=zh-HK"))
        elif kind == "index_barh":
            body = "主要指数涨跌幅:观察大盘与风格指数当日强弱;筛选失败时可能为网络或接口限制。"
            _add(("东方财富指数行情", "https://quote.eastmoney.com/center/hszs.html"))
        elif kind == "bond_lines":
            body = "中美国债收益率:利差与期限结构影响股债性价比与跨境资金成本;曲线变动常领先或同步于宏观预期。"
            _add(("东方财富国债数据", "https://data.eastmoney.com/cjsj/zgyz_list.html"))
        elif kind == "pizza_line":
            body = (
                "五角大楼披萨指数:坊间非官方谈资(披萨订单/加班等民间说法);"
                "此处用美股 Papa John's(PZZA)日线收盘作非官方代理,与真实军方统计无关,勿过度解读。"
            )
            _add(("雅虎财经 PZZA", "https://finance.yahoo.com/quote/PZZA/"))
        elif kind == "us_equity_line":
            sym = title.strip().upper()
            for sep in ("(", "("):
                if sep in sym:
                    sym = sym.split(sep)[0].strip()
            if sym in US_EQ:
                body, extra = US_EQ[sym]
                _add(*extra)
            else:
                body = (
                    f"美股日线「{title}」:图示为 AKShare 拉取的收盘价走势,常见为 ETF 或个股代理;"
                    "与 A 股交易制度、时段不同,仅作全球情绪与资产联动参照。"
                )
                ysym = sym[:12] if sym.isalnum() else "SPY"
                _add(("雅虎财经", f"https://finance.yahoo.com/quote/{ysym}"))
                needs_web = True
                web_query = f"{title} ETF 或 股票 含义"
        elif kind == "us10y_line":
            body = "美国 10 年期国债收益率:全球资产定价锚之一;上行常压制成长股估值,影响美元与新兴市场资金流动。"
            _add(("FRED 美债", "https://fred.stlouisfed.org/series/DGS10"))
        elif kind == "polymarket_barh":
            body = "Polymarket:去中心化预测市场,Yes% 为市场隐含概率;流动性与样本偏差大,勿作单一依据。"
            _add(("Polymarket", "https://polymarket.com/"))
        elif kind == "date_multi_line":
            body = "多序列折线:多为利率或多期限报价;请看纵轴单位(常见为 %)。"
            needs_web = True
            web_query = f"{title} 指标 含义"
            if "LPR" in title:
                body = "LPR:贷款市场报价利率,影响企业与房贷融资成本;与 MLF、政策利率预期相关。"
                _add(("央行 LPR 说明", "http://www.pbc.gov.cn/"))
                needs_web = False
                web_query = None
        elif kind == "month_line":
            body = "月度指标折线:横轴为统计期标签;注意发布滞后与口径修订。"
            needs_web = True
            web_query = f"{title} 经济指标 含义"
            if "固定资产投资" in title or "朱格拉" in title:
                body = (
                    "固定资产投资同比增速:实务中常作为朱格拉周期(资本开支/设备更新,约 8-10 年量级)的代理之一;"
                    "需结合制造业投资、技改与政策口径,不宜单独择时。"
                )
                _add(("国家统计局", "https://www.stats.gov.cn/"))
                needs_web = False
                web_query = None
            elif "企业景气" in title:
                body = "企业景气指数(季度):反映企业家对宏观经济与企业经营状况的判断,可作实体预期与库存/资本开支周期的辅助参照。"
                _add(("国家统计局", "https://www.stats.gov.cn/"))
                needs_web = False
                web_query = None
            elif "全社会用电" in title or "用电同比" in title:
                body = "全社会用电量同比:经济活动的实物侧热度代理之一,常用于对照 GDP/工业增速;注意季节性与气温因素。"
                _add(("国家能源局", "https://www.nea.gov.cn/"))
                needs_web = False
                web_query = None
        elif kind == "date_value_line":
            body = "按日期排列的指标今值/数量级序列;注意单位(点、%、亿元等)。"
            needs_web = True
            web_query = f"{title} 指标 含义"
            if "规上工业" in title or "工业增加值" in title:
                body = (
                    "规模以上工业增加值同比增速:反映工业生产实物量侧景气,可作基钦库存周期与朱格拉资本开支周期的实体对照;"
                    "发布节奏与口径以国家统计局为准。"
                )
                _add(("国家统计局", "https://www.stats.gov.cn/"))
                needs_web = False
                web_query = None
        t = title.upper()
        if "SPY" in t or "QQQ" in t or "IWM" in t or "GLD" in t or "USO" in t or "UUP" in t or "VXX" in t or "ITB" in t or "DBC" in t or "CPER" in t:
            if kind != "us_equity_line" and kind != "pizza_line":
                body += " 美股 ETF:跟踪标的或波动率代理,与 A 股交易时差与制度不同,仅作全球风险偏好参照。"
                _add(("雅虎财经 ETF", "https://finance.yahoo.com/"))
        if "CPI" in title or "PPI" in title or "PMI" in title or "M2" in title or "GDP" in title or "非农" in title:
            _add(("美国劳工统计局", "https://www.bls.gov/"))
        if "BDI" in title or "波罗的海" in title:
            body = "BDI:干散货运价指数,反映大宗商品海运需求与全球贸易热度。"
            _add(("波罗的海交易所", "https://www.balticexchange.com/en/index.html"))
            needs_web = False
        if "京沪" in title or "二手" in title or "国房" in title:
            _add(("国家统计局房地产", "https://www.stats.gov.cn/tjsj/zxfb/"))
        if "新屋" in title or "NAHB" in title or "FHFA" in title or "成屋" in title:
            _add(("美国人口普查局-新屋开工", "https://www.census.gov/construction/nrc/index.html"))
        if needs_web and not web_query:
            web_query = f"{title} 金融 指标 解释"
        return {
            "title": title,
            "body": body,
            "links": links[:12],
            "needs_web": needs_web,
            "web_query": web_query,
        }


    def _show_market_sentiment_chart_popup(self, parent, spec):
        """双击子图:大图 + 文字说明 + 可点击参考链接。"""
        import webbrowser
        if not isinstance(spec, dict):
            return
        info = self._get_market_sentiment_chart_help(spec)
        top = self._toplevel(parent)
        top.title("指标说明 · " + (info.get("title") or "")[:56])
        top.geometry("920x760")
        top.transient(parent)
        pan = ttk.PanedWindow(top, orient=tk.VERTICAL)
        pan.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        fig_fr = ttk.Frame(pan)
        txt_fr = ttk.Frame(pan)
        pan.add(fig_fr, weight=5)
        pan.add(txt_fr, weight=3)
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            pfig = Figure(figsize=(10.0, 5.2), dpi=100)
            pax = pfig.add_subplot(111)
            self._plot_sentiment_chart_on_ax(pax, spec)
            pfig.tight_layout()
            pcanvas = FigureCanvasTkAgg(pfig, master=fig_fr)
            pcanvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            pcanvas.draw()
        except Exception as ex:
            ttk.Label(fig_fr, text=f"绘图失败:{ex}", wraplength=600).pack(expand=True, padx=8)
        inner = ttk.Frame(txt_fr)
        inner.pack(fill=tk.BOTH, expand=True)
        ttk.Label(inner, text=info.get("title", ""), font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W, padx=4, pady=(0, 4))
        st = scrolledtext.ScrolledText(inner, wrap=tk.WORD, font=("Microsoft YaHei", 11), height=8)
        st.insert(tk.END, info.get("body", ""))
        st.config(state=tk.DISABLED)
        st.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        wq = info.get("web_query")
        if info.get("needs_web") and wq:
            def _web_enrich():
                sn = self._fetch_ddg_abstract(wq)
                if not sn:
                    return
                def _apply_snippet():
                    st.config(state=tk.NORMAL)
                    st.insert(tk.END, "\n\n【检索摘要(DuckDuckGo)】\n" + sn)
                    st.config(state=tk.DISABLED)
                top.after(0, _apply_snippet)
            threading.Thread(target=_web_enrich, daemon=True).start()
        lf = ttk.LabelFrame(inner, text="参考链接(单击用系统浏览器打开)")
        lf.pack(fill=tk.X)
        for lab, url in info.get("links") or []:
            row = ttk.Frame(lf)
            row.pack(fill=tk.X, padx=6, pady=2)
            lb = tk.Label(
                row,
                text=f"{lab}  →  {url}",
                fg="#1565c0",
                cursor="hand2",
                font=("Microsoft YaHei", 9),
                justify=tk.LEFT,
                wraplength=860,
            )
            lb.pack(anchor=tk.W)
            def _open(u=url):
                try:
                    webbrowser.open(u)
                except Exception:
                    messagebox.showerror("提示", f"无法打开链接:{u}", parent=top)
            lb.bind("<Button-1>", lambda e, u=url: _open(u))
        ttk.Button(inner, text="关闭", command=top.destroy).pack(pady=8)
        def _lift_popup():
            try:
                top.update_idletasks()
                top.lift()
                top.focus_force()
            except Exception:
                pass
        top.after(80, _lift_popup)


    def _collect_market_sentiment_snapshot_bundle(self):
        """汇总指标快照文本,并收集右侧图表用 DataFrame(与文本同源一次拉取)。"""
        if not AKSHARE_AVAILABLE:
            return (
                "当前环境未安装 AKShare,无法拉取指标。\n请 pip install akshare 后重试。",
                [],
            )
        lines = []
        lines.append(
            "【A 股市场情绪 · 指标快照】"
            + datetime.now().strftime(" %Y-%m-%d %H:%M:%S")
        )
        lines.append(
            "说明:数据来自 AKShare 对接的公开数据源(如东方财富、雅虎财经美股日线等),用于观察资金、估值、利率、"
            "银行间与离岸拆借(SHIBOR/HIBOR/SIBOR 等)、汇率与主力动向;"
            "另含五角大楼披萨指数(PZZA 非官方代理)、美国10年期国债、Polymarket 预测市场节选,"
            "并扩展美股大盘/商品/汇率 ETF、中美宏观、全球地产与航运/贵金属等;"
            "另含周金涛框架常用实务序列:固定资产投资同比(朱格拉代理)、规上工业增加值、企业景气指数、全社会用电量同比、DBC 商品 ETF、CPER 铜 ETF 等。"
            "仅供参考,不构成投资建议。右侧多格图示与左侧为同一批数据。"
        )
        lines.append("")
        def _block(title: str, body: str):
            lines.append(f"══ {title} ══")
            lines.append(body if body.strip() else "(无)")
            lines.append("")
        def _safe_df(name: str, fn, max_rows: int = 14, **kwargs):
            try:
                df = fn(**kwargs) if kwargs else fn()
                if df is None or getattr(df, "empty", True):
                    return f"({name}:返回空表)", None
                tail = df.tail(max_rows)
                return tail.to_string(index=False), tail.copy()
            except Exception as e:
                return f"({name} 获取失败:{e})", None
        t_act, df_act = _safe_df("涨跌家数", lambda: ak.stock_market_activity_legu(), max_rows=8)
        _block("市场宽度(涨跌家数等)", t_act)
        _block(
            "沪深港通资金汇总(最新交易日)",
            _safe_df("港通汇总", lambda: ak.stock_hsgt_fund_flow_summary_em(), max_rows=8)[0],
        )
        t_north, df_north = _safe_df(
            "北向历史", lambda: ak.stock_hsgt_hist_em(symbol="北向资金"), max_rows=18
        )
        _block("北向资金 · 历史(近日)", t_north)
        _block(
            "SHIBOR(上海银行间同业拆放利率,全期限表)",
            _safe_df("SHIBOR", lambda: ak.macro_china_shibor_all(), max_rows=10)[0],
        )
        def _interbank_offshore():
            """东方财富同业拆借:含香港 HIBOR、新加坡 SIBOR、伦敦 Libor 等;单路失败不影响其它。"""
            chunks = []
            combos = [
                ("上海银行间 · Shibor 人民币 · 隔夜", "上海银行同业拆借市场", "Shibor人民币", "隔夜"),
                ("香港 · Hibor 港币 · 隔夜", "香港银行同业拆借市场", "Hibor港币", "隔夜"),
                ("新加坡 · Sibor 美元 · 隔夜", "新加坡银行同业拆借市场", "Sibor美元", "隔夜"),
                ("新加坡 · Sibor 星元 · 隔夜", "新加坡银行同业拆借市场", "Sibor星元", "隔夜"),
                ("伦敦 · Libor 美元 · 隔夜", "伦敦银行同业拆借市场", "Libor美元", "隔夜"),
            ]
            for title, market, symbol, ind in combos:
                try:
                    df = ak.rate_interbank(market=market, symbol=symbol, indicator=ind)
                    if df is None or getattr(df, "empty", True):
                        chunks.append(f"【{title}】(暂无数据)\n")
                        continue
                    chunks.append(f"【{title}】\n{df.tail(8).to_string(index=False)}\n")
                except Exception as e:
                    chunks.append(f"【{title}】(接口异常或未开放:{e})\n")
            return "\n".join(chunks).strip()
        _block("离岸/国际同业拆借(HIBOR · SIBOR · Libor 等)", _interbank_offshore())
        _block(
            "主力资金流向 · 全市场(大单/主力统计,东财)",
            _safe_df("主力流向", lambda: ak.stock_main_fund_flow(symbol="全部股票"), max_rows=18)[0],
        )
        def _fx_mid():
            try:
                df = safe_call(ak.currency_boc_safe, fallback=[], label="ak.currency_boc_safe")
                if df is None or df.empty:
                    return "(无数据)"
                df = df.tail(10)
                prefer = ["日期", "美元", "欧元", "日元", "港币", "英镑", "新加坡元"]
                use = [c for c in prefer if c in df.columns]
                if len(use) < 2:
                    use = [df.columns[0]] + list(df.columns[1:9])
                return df[use].to_string(index=False)
            except Exception as e:
                return f"(人民币汇率中间价获取失败:{e})"
        _block("人民币汇率中间价(节选,影响外资与跨境资金成本)", _fx_mid())
        _block(
            "A 股指数市盈率(上证 / 深证,历史)",
            _safe_df("上证PE", lambda: ak.stock_market_pe_lg(symbol="上证"), max_rows=8)[0]
            + "\n\n"
            + _safe_df("深证PE", lambda: ak.stock_market_pe_lg(symbol="深证"), max_rows=8)[0],
        )
        def _bond():
            try:
                df_full = safe_call(ak.bond_zh_us_rate, fallback=[], label="ak.bond_zh_us_rate")
                if df_full is None or df_full.empty:
                    return "(无数据)", None, None
                df_text = df_full.tail(10)
                prefer = [
                    "日期",
                    "中国国债收益率2年",
                    "中国国债收益率5年",
                    "中国国债收益率10年",
                    "美国国债收益率2年",
                    "美国国债收益率10年",
                    "美国国债收益率10年-2年",
                ]
                use = [c for c in prefer if c in df_text.columns]
                if not use:
                    use = list(df_text.columns)[:10]
                df_chart = df_full.tail(40)[use].copy() if use else df_full.tail(40).copy()
                df_us10 = None
                if "日期" in df_full.columns and "美国国债收益率10年" in df_full.columns:
                    df_us10 = df_full[["日期", "美国国债收益率10年"]].tail(60).copy()
                return df_text[use].to_string(index=False), df_chart, df_us10
            except Exception as e:
                return f"(获取失败:{e})", None, None
        def _idx():
            try:
                df = safe_call(ak.stock_zh_index_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_index_spot_em")
                if df is None or df.empty:
                    return "(无数据)", None
                name_col = "名称" if "名称" in df.columns else df.columns[1]
                sub = df[
                    df[name_col].astype(str).str.contains(
                        "上证指数|深证成指|创业板指|沪深300|科创50",
                        regex=True,
                        na=False,
                    )
                ]
                if sub.empty:
                    keep0 = [
                        c
                        for c in ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额"]
                        if c in df.columns
                    ]
                    chart_fallback = None
                    if keep0:
                        cand = df[keep0].head(15).copy()
                        if any("涨跌幅" in str(c) or "涨跌" in str(c) for c in cand.columns):
                            chart_fallback = cand
                    return df.head(15).to_string(index=False), chart_fallback
                keep = [c for c in ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额"] if c in sub.columns]
                sub2 = sub[keep].head(20).copy()
                return sub2.to_string(index=False), sub2
            except Exception as e:
                return f"(主要指数行情获取失败,可能为网络限制:{e})", None
        bond_txt, df_bond, df_us10y = _bond()
        _block("中美国债收益率(近日)", bond_txt)
        idx_txt, df_idx = _idx()
        _block("主要指数即时行情(筛选)", idx_txt)
        def _pizza_proxy():
            try:
                dfp = ak.stock_us_daily(symbol="PZZA", adjust="qfq")
                if dfp is None or dfp.empty:
                    return "(无数据)", None
                dfp = dfp.tail(80).copy()
                dfp["日期"] = dfp["date"].astype(str)
                dfp["收盘"] = pd.to_numeric(dfp["close"], errors="coerce")
                chart_df = dfp[["日期", "收盘"]].copy()
                note = (
                    "说明:坊间「五角大楼披萨指数」指五角大楼周边披萨外送/深夜订单与岗位加班的民间说法,"
                    "无统一官方日线;此处用 Papa John's(NASDAQ:PZZA)收盘作非官方代理,仅作情绪参照,不代表军方或官方统计。"
                )
                return note + "\n" + dfp.tail(6).to_string(index=False), chart_df
            except Exception as e:
                return f"(PZZA 获取失败:{e})", None
        pizza_txt, df_pizza = _pizza_proxy()
        _block("五角大楼披萨指数(非官方代理:PZZA)", pizza_txt)
        poly_txt, df_poly = self._fetch_polymarket_hot_markets_snapshot(8)
        _block("Polymarket(预测市场 · Yes 报价节选)", poly_txt)
        def _fetch_us_daily(symbol: str, label: str, adjust: str = "qfq"):
            try:
                dfp = ak.stock_us_daily(symbol=symbol, adjust=adjust)
                if dfp is None or dfp.empty:
                    return f"({label}:无数据)", None
                dfp = dfp.tail(120).copy()
                dfp["日期"] = dfp["date"].astype(str)
                dfp["收盘"] = pd.to_numeric(dfp["close"], errors="coerce")
                chart_df = dfp[["日期", "收盘"]].copy()
                note = (
                    f"说明:{label},来源 AKShare 美股日线({symbol},adjust={adjust!r}),"
                    "与东方财富/同花顺等终端中同类 ETF 走势可作对照。"
                )
                return note + "\n" + dfp.tail(6).to_string(index=False), chart_df
            except Exception as e:
                return f"({label} 获取失败:{e})", None
        ext_charts = []
        _block(
            "扩展指标(美股 ETF / 中美宏观 / 汇率等)",
            "以下各段与右侧扩展子图一一对应;数据以 AKShare 公开接口为准,若网络不稳可能暂缺。",
        )
        for sym, blk_title, adj in [
            ("SPY", "美股·标普500 ETF(SPY,大盘代理)", "qfq"),
            ("QQQ", "美股·纳指100 ETF(QQQ)", "qfq"),
            ("IWM", "美股·罗素2000 ETF(IWM,小盘)", "qfq"),
            ("GLD", "美股·黄金 ETF(GLD)", ""),
            ("USO", "美股·原油 ETF(USO)", "qfq"),
            ("UUP", "美股·美元指数 ETF(UUP,美元强弱代理)", "qfq"),
            ("VXX", "美股·波动率短期期货(VXX,恐慌情绪代理)", ""),
        ]:
            # GLD/VXX 等需 adjust="",不可因空串为假而回退到 qfq
            adjust_param = "" if adj == "" else (adj or "qfq")
            t_us, cdf_us = _fetch_us_daily(sym, blk_title.split("(")[0], adjust_param)
            _block(blk_title, t_us)
            ext_charts.append({"kind": "us_equity_line", "title": sym, "df": cdf_us})
        try:
            df_lpr = ak.macro_china_lpr().tail(50)
            _block(
                "中国·LPR(贷款市场报价利率)",
                df_lpr.tail(10).to_string(index=False) if not df_lpr.empty else "(无)",
            )
            ext_charts.append(
                {
                    "kind": "date_multi_line",
                    "title": "LPR 1Y/5Y",
                    "df": df_lpr.copy() if not df_lpr.empty else None,
                    "date_col": "TRADE_DATE",
                    "value_cols": ["LPR1Y", "LPR5Y"],
                    "ylabel": "%",
                }
            )
        except Exception as e:
            _block("中国·LPR(贷款市场报价利率)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_multi_line",
                    "title": "LPR 1Y/5Y",
                    "df": None,
                    "date_col": "TRADE_DATE",
                    "value_cols": ["LPR1Y", "LPR5Y"],
                    "ylabel": "%",
                }
            )
        try:
            df_cpi_cn = ak.macro_china_cpi().head(48).iloc[::-1].reset_index(drop=True)
            _block("中国·CPI 同比(节选)", df_cpi_cn.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "中国CPI同比%",
                    "df": df_cpi_cn,
                    "month_col": "月份",
                    "value_col": "全国-同比增长",
                }
            )
        except Exception as e:
            _block("中国·CPI 同比(节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "中国CPI同比%",
                    "df": None,
                    "month_col": "月份",
                    "value_col": "全国-同比增长",
                }
            )
        try:
            df_pmi = ak.macro_china_pmi().head(48).iloc[::-1].reset_index(drop=True)
            _block("中国·制造业 PMI(节选)", df_pmi.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "制造业PMI",
                    "df": df_pmi,
                    "month_col": "月份",
                    "value_col": "制造业-指数",
                }
            )
        except Exception as e:
            _block("中国·制造业 PMI(节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "制造业PMI",
                    "df": None,
                    "month_col": "月份",
                    "value_col": "制造业-指数",
                }
            )
        try:
            df_m2 = (
                ak.macro_china_m2_yearly()
                .dropna(subset=["今值"], how="all")
                .tail(50)
            )
            _block("中国·M2 货币供应年率(今值节选)", df_m2.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "中国M2年率",
                    "df": df_m2,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("中国·M2 货币供应年率(今值节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "中国M2年率",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_gdp = ak.macro_china_gdp().head(20).iloc[::-1].reset_index(drop=True)
            _block("中国·GDP 同比(分季,节选)", df_gdp.tail(8).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "GDP同比%",
                    "df": df_gdp,
                    "month_col": "季度",
                    "value_col": "国内生产总值-同比增长",
                }
            )
        except Exception as e:
            _block("中国·GDP 同比(分季,节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "GDP同比%",
                    "df": None,
                    "month_col": "季度",
                    "value_col": "国内生产总值-同比增长",
                }
            )
        try:
            df_usd = ak.currency_boc_safe().tail(55)
            _block("人民币·对美元中间价(节选)", df_usd.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "USD/CNY中间价",
                    "df": df_usd,
                    "date_col": "日期",
                    "value_col": "美元",
                }
            )
        except Exception as e:
            _block("人民币·对美元中间价(节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "USD/CNY中间价",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "美元",
                }
            )
        try:
            df_ppi = ak.macro_china_ppi().head(40).iloc[::-1].reset_index(drop=True)
            _block("中国·PPI 同比(节选)", df_ppi.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "中国PPI同比%",
                    "df": df_ppi,
                    "month_col": "月份",
                    "value_col": "当月同比增长",
                }
            )
        except Exception as e:
            _block("中国·PPI 同比(节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "中国PPI同比%",
                    "df": None,
                    "month_col": "月份",
                    "value_col": "当月同比增长",
                }
            )
        try:
            df_rrr = ak.macro_china_reserve_requirement_ratio().head(22).iloc[::-1].reset_index(drop=True)
            _block("中国·存款准备金率(大型机构,节选)", df_rrr.tail(8).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "存准率%",
                    "df": df_rrr,
                    "month_col": "生效时间",
                    "value_col": "大型金融机构-调整后",
                }
            )
        except Exception as e:
            _block("中国·存款准备金率(大型机构,节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "存准率%",
                    "df": None,
                    "month_col": "生效时间",
                    "value_col": "大型金融机构-调整后",
                }
            )
        try:
            df_tr = ak.macro_china_trade_balance().dropna(subset=["今值"], how="all").tail(45)
            _block("中国·贸易帐(今值节选,宏观日历口径)", df_tr.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "贸易帐今值",
                    "df": df_tr,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("中国·贸易帐(今值节选,宏观日历口径)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "贸易帐今值",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_sh = ak.macro_china_shibor_all().tail(55)
            _block("中国·SHIBOR 隔夜定价(近日)", df_sh.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_multi_line",
                    "title": "SHIBOR O/N",
                    "df": df_sh,
                    "date_col": "日期",
                    "value_cols": ["O/N-定价"],
                    "ylabel": "%",
                }
            )
        except Exception as e:
            _block("中国·SHIBOR 隔夜定价(近日)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_multi_line",
                    "title": "SHIBOR O/N",
                    "df": None,
                    "date_col": "日期",
                    "value_cols": ["O/N-定价"],
                    "ylabel": "%",
                }
            )
        try:
            df_fxg = ak.macro_china_foreign_exchange_gold().head(36).iloc[::-1].reset_index(drop=True)
            _block("中国·国家外汇储备(节选)", df_fxg.tail(8).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "外汇储备",
                    "df": df_fxg,
                    "month_col": "统计时间",
                    "value_col": "国家外汇储备",
                }
            )
        except Exception as e:
            _block("中国·国家外汇储备(节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "外汇储备",
                    "df": None,
                    "month_col": "统计时间",
                    "value_col": "国家外汇储备",
                }
            )
        try:
            df_ucpi = ak.macro_usa_cpi_monthly().dropna(subset=["今值"], how="all").tail(45)
            _block("美国·CPI 月率今值(节选)", df_ucpi.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国CPI今值",
                    "df": df_ucpi,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("美国·CPI 月率今值(节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国CPI今值",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_nfp = ak.macro_usa_non_farm().dropna(subset=["今值"], how="all").tail(45)
            _block("美国·非农就业人数变动(今值节选)", df_nfp.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国非农今值",
                    "df": df_nfp,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("美国·非农就业人数变动(今值节选)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国非农今值",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        _block(
            "周金涛周期论 · 核心实务指标(康波·朱格拉·基钦·实体侧)",
            "说明:涛动周期论将长波(康波:资源与价格体系)、资本开支周期(朱格拉)、库存短周期(基钦)、建筑周期(库兹涅茨)对照观察。"
            "下列为 AKShare 可拉取的公开序列:固定资产投资同比(朱格拉常用代理)、规模以上工业增加值年率(实体生产)、企业景气指数(季度预期)、"
            "全社会用电量同比(经济热度);DBC(商品指数 ETF)、CPER(铜 ETF)作全球商品与工业金属侧参照。口径与滞后以发布机构为准,不构成投资建议。",
        )
        try:
            df_gdz = ak.macro_china_gdzctz().head(80).iloc[::-1].reset_index(drop=True)
            _block(
                "中国·固定资产投资完成额·当月同比(朱格拉周期常用代理,节选)",
                df_gdz.tail(10).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "固定资产投资同比%",
                    "df": df_gdz,
                    "month_col": "月份",
                    "value_col": "同比增长",
                }
            )
        except Exception as e:
            _block("中国·固定资产投资完成额·当月同比", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "固定资产投资同比%",
                    "df": None,
                    "month_col": "月份",
                    "value_col": "同比增长",
                }
            )
        try:
            df_ipv = ak.macro_china_industrial_production_yoy().dropna(subset=["今值"], how="all").tail(80)
            _block(
                "中国·规模以上工业增加值年率(实体生产侧,基钦/朱格拉对照,节选)",
                df_ipv.tail(10).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "规上工业增加值年率",
                    "df": df_ipv,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("中国·规模以上工业增加值年率", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "规上工业增加值年率",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_eb = ak.macro_china_enterprise_boom_index().head(32).iloc[::-1].reset_index(drop=True)
            _block("中国·企业景气指数(季度,企业家预期侧,节选)", df_eb.tail(8).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "企业景气指数",
                    "df": df_eb,
                    "month_col": "季度",
                    "value_col": "企业景气指数-指数",
                }
            )
        except Exception as e:
            _block("中国·企业景气指数(季度)", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "企业景气指数",
                    "df": None,
                    "month_col": "季度",
                    "value_col": "企业景气指数-指数",
                }
            )
        try:
            df_el = ak.macro_china_society_electricity().tail(48).copy()
            _block(
                "中国·全社会用电量同比(经济热度实物侧参照,节选)",
                df_el.tail(10).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "全社会用电同比%",
                    "df": df_el,
                    "month_col": "统计时间",
                    "value_col": "全社会用电量同比",
                }
            )
        except Exception as e:
            _block("中国·全社会用电量同比", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "全社会用电同比%",
                    "df": None,
                    "month_col": "统计时间",
                    "value_col": "全社会用电量同比",
                }
            )
        t_dbc, df_dbc = _fetch_us_daily("DBC", "美股·商品指数 ETF(DBC,康波商品篮子代理)", "qfq")
        _block("美股·商品指数 ETF(DBC,全球商品综合代理)", t_dbc)
        ext_charts.append({"kind": "us_equity_line", "title": "DBC", "df": df_dbc})
        t_cper, df_cper = _fetch_us_daily("CPER", "美股·铜 ETF(CPER,工业金属/资本开支情绪代理)", "qfq")
        _block("美股·铜 ETF(CPER,工业金属周期参照)", t_cper)
        ext_charts.append({"kind": "us_equity_line", "title": "CPER", "df": df_cper})
        _block(
            "全球地产与周金涛框架参照(库兹涅茨/朱格拉/库存·商品)",
            "说明:周金涛「涛动周期论」中常对照地产链、利率、美元、商品与航运等;库兹涅茨周期多与建筑业/房地产相关;"
            "BDI(波罗的海干散货)作全球贸易热度参照;以下为 AKShare 可拉取的公开序列节选,城市覆盖以接口为准(京沪为统计局 70 城指数中的代表)。",
        )
        try:
            dfh = safe_call(ak.macro_china_new_house_price, fallback=[], label="ak.macro_china_new_house_price")
            dfh = dfh[dfh["城市"].isin(["北京", "上海"])].copy()
            pv = dfh.pivot_table(
                index="日期", columns="城市", values="二手住宅价格指数-同比", aggfunc="first"
            )
            pv = pv.sort_index().tail(72).reset_index()
            pv["日期"] = pv["日期"].astype(str)
            cols = [c for c in ("北京", "上海") if c in pv.columns]
            _block(
                "中国·京沪 二手住宅价格指数·同比(统计局 70 城口径,节选)",
                "数据源字段若仅含京沪则与下图一致;同比为指数点,非涨跌幅%。\n"
                + pv.tail(10).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "date_multi_line",
                    "title": "京沪二手同比",
                    "df": pv.copy() if cols else None,
                    "date_col": "日期",
                    "value_cols": cols,
                    "ylabel": "指数",
                }
            )
        except Exception as e:
            _block("中国·京沪 二手住宅价格指数·同比", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_multi_line",
                    "title": "京沪二手同比",
                    "df": None,
                    "date_col": "日期",
                    "value_cols": ["北京", "上海"],
                    "ylabel": "指数",
                }
            )
        try:
            df_cnre = ak.macro_china_real_estate().tail(96).copy()
            df_cnre["日期"] = df_cnre["日期"].astype(str)
            _block(
                "中国·全国房地产开发景气指数(国房景气指数,节选)",
                df_cnre.tail(10).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "国房景气指数",
                    "df": df_cnre,
                    "date_col": "日期",
                    "value_col": "最新值",
                }
            )
        except Exception as e:
            _block("中国·全国房地产开发景气指数", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "国房景气指数",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "最新值",
                }
            )
        try:
            df_hs = (
                ak.macro_usa_house_starts()
                .dropna(subset=["今值"], how="all")
                .tail(48)
            )
            _block("美国·新屋开工总数年化(节选,库兹涅茨/地产链参照)", df_hs.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国新屋开工",
                    "df": df_hs,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("美国·新屋开工总数年化", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国新屋开工",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_fhfa = ak.macro_usa_house_price_index().dropna(subset=["今值"], how="all").tail(48)
            _block("美国·FHFA 房价指数月率(节选)", df_fhfa.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国FHFA房价月率",
                    "df": df_fhfa,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("美国·FHFA 房价指数月率", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国FHFA房价月率",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_nahb = ak.macro_usa_nahb_house_market_index().dropna(subset=["今值"], how="all").tail(48)
            _block("美国·NAHB 房产市场指数(节选)", df_nahb.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国NAHB指数",
                    "df": df_nahb,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("美国·NAHB 房产市场指数", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国NAHB指数",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_can = ak.macro_canada_new_house_rate().iloc[:40].iloc[::-1].copy()
            df_can["v"] = pd.to_numeric(df_can["现值"], errors="coerce")
            _block("加拿大·新屋价格指数月率(节选)", df_can.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "加拿大新屋价格",
                    "df": df_can,
                    "month_col": "时间",
                    "value_col": "v",
                }
            )
        except Exception as e:
            _block("加拿大·新屋价格指数月率", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "加拿大新屋价格",
                    "df": None,
                    "month_col": "时间",
                    "value_col": "v",
                }
            )
        try:
            df_pend = ak.macro_usa_pending_home_sales().dropna(subset=["今值"], how="all").tail(48)
            _block("美国·成屋签约销售指数月率(节选)", df_pend.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国成屋签约月率",
                    "df": df_pend,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        except Exception as e:
            _block("美国·成屋签约销售指数月率", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "美国成屋签约月率",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "今值",
                }
            )
        try:
            df_phs = ak.macro_usa_phs().head(40).iloc[::-1].copy()
            df_phs["y"] = pd.to_numeric(df_phs["现值"], errors="coerce").fillna(
                pd.to_numeric(df_phs["前值"], errors="coerce")
            )
            _block("美国·成屋销售年化总数月率(节选,PHS 相关序列)", df_phs.tail(10).to_string(index=False))
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "美国成屋销售月率",
                    "df": df_phs,
                    "month_col": "时间",
                    "value_col": "y",
                }
            )
        except Exception as e:
            _block("美国·成屋销售年化总数月率", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "month_line",
                    "title": "美国成屋销售月率",
                    "df": None,
                    "month_col": "时间",
                    "value_col": "y",
                }
            )
        try:
            df_bdi = ak.macro_shipping_bdi().tail(200).copy()
            df_bdi["日期"] = df_bdi["日期"].astype(str)
            _block(
                "全球·波罗的海干散货指数 BDI(航运/贸易热度,周金涛框架中常作实体需求侧参照)",
                df_bdi.tail(10).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "BDI",
                    "df": df_bdi,
                    "date_col": "日期",
                    "value_col": "最新值",
                }
            )
        except Exception as e:
            _block("全球·BDI 波罗的海干散货指数", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "BDI",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "最新值",
                }
            )
        try:
            df_gold = ak.macro_cons_gold().tail(120).copy()
            df_gold["日期"] = df_gold["日期"].astype(str)
            _block(
                "全球·COMEX 黄金库存·总价值(商品侧参照,美林时钟/康波中的贵金属维度)",
                df_gold.tail(8).to_string(index=False),
            )
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "COMEX黄金总价值",
                    "df": df_gold,
                    "date_col": "日期",
                    "value_col": "总价值",
                }
            )
        except Exception as e:
            _block("全球·COMEX 黄金库存总价值", f"(获取失败:{e})")
            ext_charts.append(
                {
                    "kind": "date_value_line",
                    "title": "COMEX黄金总价值",
                    "df": None,
                    "date_col": "日期",
                    "value_col": "总价值",
                }
            )
        t_itb, df_itb = _fetch_us_daily("ITB", "美股·地产建筑 ETF(ITB,美房建板块代理)", "qfq")
        _block("美股·地产建筑 ETF(ITB,全球地产链情绪代理)", t_itb)
        ext_charts.append({"kind": "us_equity_line", "title": "ITB", "df": df_itb})
        # 多格图示(与左侧文字同源);缺表时对应格显示「暂无数据」
        charts = [
            {"kind": "breadth", "title": "涨跌家数", "df": df_act},
            {"kind": "north", "title": "北向资金(近日)", "df": df_north},
            {"kind": "index_barh", "title": "主要指数涨跌幅", "df": df_idx},
            {"kind": "bond_lines", "title": "中美国债收益率", "df": df_bond},
            {"kind": "pizza_line", "title": "五角大楼披萨指数(代理:PZZA)", "df": df_pizza},
            {"kind": "us10y_line", "title": "美国10年期国债收益率", "df": df_us10y},
            {"kind": "polymarket_barh", "title": "Polymarket 热门 Yes%", "df": df_poly},
        ] + ext_charts
        def _margin():
            try:
                df = safe_call(ak.stock_margin_sse, fallback=[], label="ak.stock_margin_sse")
                if df is None or df.empty:
                    return "(无数据)"
                tail = df.tail(3)
                note = ""
                if len(df) > 0:
                    last_d = str(tail.iloc[-1].get("信用交易日期", ""))
                    if last_d and last_d < "20200101":
                        note = "\n提示:上交所融资融券接口返回日期较旧,请以交易所官网为准。"
                return tail.to_string(index=False) + note
            except Exception as e:
                return f"(融资融券(沪)获取失败:{e})"
        _block("融资融券余额 · 上交所(最近若干条,日期以数据源为准)", _margin())
        lines.append("══ 参考链接(浏览器打开)══")
        lines.append("东方财富国债:data.eastmoney.com/cjsj/zgyz_list.html")
        lines.append("国家统计局 / 宏观数据:可在 stats.gov.cn 对照 CPI、GDP 等发布口径")
        lines.append("Polymarket:https://polymarket.com/")
        lines.append("同花顺情绪相关:可在行情软件查看情绪指数、涨跌比等")
        lines.append("")
        return "\n".join(lines), charts


    def _open_crash_rally_calendar(self):
        """🗓️ 暴涨暴跌日历 — 调出 crash_rally_calendar.py"""
        try:
            import sys as _sys_cr
            # 确保 src 在 path 里 (mac003 从 src/ 跑, mac.py 也在 src/)
            _src_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else ""
            if _src_dir and _src_dir not in _sys_cr.path:
                _sys_cr.path.insert(0, _src_dir)
            # 也加上父目录 (crash_rally_calendar.py 和 ui/ 同级, 在 src/)
            _parent = os.path.dirname(_src_dir) if _src_dir else ""
            if _parent and _parent not in _sys_cr.path:
                _sys_cr.path.insert(0, _parent)
            from crash_rally_calendar import open_crash_rally_calendar
            open_crash_rally_calendar(getattr(self, "root", None))
        except Exception as _e_cr:
            print(f"[大盘] 🗓️ 暴涨暴跌日历启动失败: {_e_cr}", flush=True)
            try:
                import tkinter.messagebox as _mb
                _mb.showerror("🗓️ 暴涨暴跌日历启动失败",
                              f"{_e_cr}\n\n请确认 crash_rally_calendar.py 在 src/ 目录下")
            except Exception:
                pass


    def _bg_load_dapan(self):
        """大盘分析Tab后台加载: 红绿灯+四维度+情绪周期+板块
        ⚠️ 线程安全: 后台线程只放数据到 _dapan_pending, 主线程用 root.after 轮询"""
        import threading as _th
        # 停止信号 + 进度回调
        self._dapan_stop_event = _th.Event()
        _stop = self._dapan_stop_event
        def _step(name):
            """每步开始前调, 更新状态 + 检查停止信号"""
            if _stop.is_set():
                print(f"[大盘] ⏹️ 用户停止 (在: {name})", flush=True)
                return False
            self.root.after(0, lambda n=name: setattr(
                self, '_dapan_alert_var', None) or (  # 不直接设 StringVar, 用下面的
                    self._dapan_alert_var.set(f"⏳ {n}...")) if hasattr(self, '_dapan_alert_var') else None)
            return True
        self._dapan_pending = None
        if not hasattr(self, "_dapan_polling"):
            self._dapan_polling = True
            def _poll():
                if self._dapan_pending is not None:
                    data = self._dapan_pending
                    self._dapan_pending = None
                    self._dapan_update_ui(data)
                self.root.after(300, _poll)
            self.root.after(500, _poll)
        # 启用 ⏹️ 停止按钮
        self.root.after(0, lambda: self._dapan_stop_btn.config(state="normal", bg="#E53935"))
        def _run():
            try:
                import json as _js
                import os as _os
                import subprocess as _sp
                import time as _t_dp

                if not _step("初始化 tushare"): return
                import akshare as ak
                print("[大盘分析] ⏳ 开始加载...", flush=True)
                dapan_data = {"dims": {}, "hld": {}, "emo": {}, "sectors": {}}

                # ---- 先初始化 tushare + 最近交易日 (akshare 挂时用兜底) ----
                _ts_pro_dapan = None
                _trade_date_dapan = None
                _use_tushare_fallback = False
                try:
                    from datetime import date as _dt_date
                    from datetime import timedelta as _dt_td

                    import tushare as _ts_dp
                    _tk = (_os.environ.get("TUSHARE_TOKEN") or getattr(self, "ts_token", "") or TS_DEFAULT_TOKEN or "").strip()
                    if _tk:
                        _ts_dp.set_token(_tk)
                        _ts_pro_dapan = _ts_dp.pro_api()
                        _cal2 = _ts_pro_dapan.trade_cal(exchange="SSE",
                            start_date=(_dt_date.today()-_dt_td(days=10)).strftime("%Y%m%d"),
                            end_date=_dt_date.today().strftime("%Y%m%d"), is_open="1")
                        if _cal2 is not None and len(_cal2) > 0:
                            _trade_date_dapan = str(_cal2["cal_date"].iloc[0])
                        else:
                            _trade_date_dapan = _dt_date.today().strftime("%Y%m%d")
                        print(f"[大盘] tushare兜底就绪 trade_date={_trade_date_dapan}")
                except Exception as _e_init:
                    import traceback as _tb
                    print(f"[大盘] tushare兜底初始化fail: {_e_init}")
                    _tb.print_exc()

                # --- 1. 涨跌停广度 (核心! 1次尝试 + tushare兜底, 东财限流时不白等) ---
                if not _step("拉涨跌停广度"): return
                spot = None
                try:
                    spot = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                except Exception as e:
                    print(f"[大盘] spot akshare fail → 直接兜底: {str(e)[:40]}")
                total = up = dn = flat = zt = dt = breadth_score = None
                if spot is not None and len(spot) > 0:
                    total = len(spot)
                    up = len(spot[spot["涨跌幅"] > 0])
                    dn = len(spot[spot["涨跌幅"] < 0])
                    flat = total - up - dn
                    zt = len(spot[spot["涨跌幅"] >= 9.5])
                    dt = len(spot[spot["涨跌幅"] <= -9.5])
                elif _ts_pro_dapan and _trade_date_dapan:
                    print("[大盘] akshare spot挂 → tushare daily兜底")
                    _use_tushare_fallback = True
                    try:
                        _tdf = _ts_pro_dapan.daily(trade_date=_trade_date_dapan)
                        if _tdf is not None and len(_tdf) > 0:
                            total = len(_tdf)
                            up = int((_tdf["pct_chg"] > 0).sum())
                            dn = int((_tdf["pct_chg"] < 0).sum())
                            flat = total - up - dn
                            zt = int((_tdf["pct_chg"] >= 9.5).sum())
                            dt = int((_tdf["pct_chg"] <= -9.5).sum())
                    except Exception as _e2:
                        print(f"[大盘] tushare breadth兜底fail: {_e2}")

                if total is not None and total > 0:
                    breadth_score = 100 if up > dn * 2 else (70 if up > dn else (40 if up > dn * 0.7 else 15))
                    breadth_lvl = "green" if breadth_score >= 60 else ("yellow" if breadth_score >= 35 else "red")
                    dapan_data["dims"]["breadth"] = (breadth_lvl, f"涨{up}/跌{dn}/平{flat}  涨停{zt}/跌停{dt}")
                    dapan_data["hld"]["breadth_score"] = breadth_score
                else:
                    dapan_data["dims"]["breadth"] = ("gray", "spot接口超时")
                    dapan_data["hld"]["breadth_score"] = 50

                # --- 2. 北向资金 (沪股通+深股通 + tushare兜底) ---
                if not _step("拉北向资金"): return
                north_ok = False
                try:
                    import pandas as _pd_dp
                    hgt = ak.stock_hsgt_hist_em(symbol="沪股通")
                    sgt = ak.stock_hsgt_hist_em(symbol="深股通")
                    nv_h = 0
                    for _i in range(len(hgt)-1, max(len(hgt)-5, 0), -1):
                        v = hgt.iloc[_i].get("当日成交净买额")
                        if v is not None and not _pd_dp.isna(v):
                            nv_h = float(v); break
                    nv_s = 0
                    for _i in range(len(sgt)-1, max(len(sgt)-5, 0), -1):
                        v = sgt.iloc[_i].get("当日成交净买额")
                        if v is not None and not _pd_dp.isna(v):
                            nv_s = float(v); break
                    nv_yi = (nv_h + nv_s) / 1e8
                    north_score = min(100, max(0, int(50 + nv_yi * 2)))
                    north_lvl = "green" if nv_yi > 10 else ("yellow" if nv_yi > -5 else "red")
                    dapan_data["dims"]["north"] = (north_lvl, f"{nv_yi:+.1f}亿")
                    dapan_data["hld"]["north_score"] = north_score
                    north_ok = True
                except Exception as e:
                    print(f"[大盘] north akshare fail: {e}")
                if not north_ok and _ts_pro_dapan and _trade_date_dapan:
                    try:
                        # tushare 北向: 用 daily_basic 的 主力净流入 作代理 (或用 moneyflow 接口)
                        _try_north = _ts_pro_dapan.moneyflow_hsgt(start_date=_trade_date_dapan, end_date=_trade_date_dapan)
                        if _try_north is None or len(_try_north) == 0:
                            # 兜底: 全市场 daily_basic 的 amount 涨幅作代理
                            _db_df = _ts_pro_dapan.daily_basic(trade_date=_trade_date_dapan,
                                fields="ts_code,turnover_rate,circ_mv,total_mv")
                            _am = _ts_pro_dapan.daily(trade_date=_trade_date_dapan)
                            if _am is not None and len(_am) > 0:
                                _total_amt = float(_am["amount"].sum()) / 1e5  # 千元→亿 (daily amount 是千元)
                                # 用成交额作为北向资金的代理指标（北向好=A股成交量活跃）
                                nv_yi = _total_amt / 100  # 简化: 总成交额高=北向积极
                                north_score = min(100, max(0, int(50 + nv_yi * 0.3)))
                                north_lvl = "green" if nv_yi > 30 else ("yellow" if nv_yi > 0 else "red")
                                dapan_data["dims"]["north"] = (north_lvl, f"成交额代理 {_total_amt:.0f}亿")
                                dapan_data["hld"]["north_score"] = north_score
                            else:
                                dapan_data["dims"]["north"] = ("gray", "获取失败")
                                dapan_data["hld"]["north_score"] = 50
                        else:
                            # moneyflow_hsgt 有数据
                            nv_yi = float(_try_north["ggt_ss"].iloc[-1] + _try_north["ggt_sz"].iloc[-1]) / 1e8
                            north_score = min(100, max(0, int(50 + nv_yi * 2)))
                            north_lvl = "green" if nv_yi > 10 else ("yellow" if nv_yi > -5 else "red")
                            dapan_data["dims"]["north"] = (north_lvl, f"{nv_yi:+.1f}亿")
                            dapan_data["hld"]["north_score"] = north_score
                        print("[大盘] ✅ north tushare兜底")
                    except Exception as _e3:
                        print(f"[大盘] north tushare兜底fail: {_e3}")
                        dapan_data["dims"]["north"] = ("gray", "获取失败")
                        dapan_data["hld"]["north_score"] = 50
                elif not north_ok:
                    dapan_data["dims"]["north"] = ("gray", "获取失败")
                    dapan_data["hld"]["north_score"] = 50

                # --- 3. 融资融券 (+ tushare兜底) ---
                if not _step("拉融资融券"): return
                margin_ok = False
                try:
                    margin_sh = safe_call(ak.macro_china_market_margin_sh, fallback=[], label="ak.macro_china_market_margin_sh")
                    margin_sz = safe_call(ak.macro_china_market_margin_sz, fallback=[], label="ak.macro_china_market_margin_sz")
                    col_sh = [c for c in margin_sh.columns if '融资' in c or '余额' in c][-1]
                    col_sz = [c for c in margin_sz.columns if '融资' in c or '余额' in c][-1]
                    sh_latest = float(margin_sh[col_sh].iloc[-1])
                    sz_latest = float(margin_sz[col_sz].iloc[-1])
                    sh_prev = float(margin_sh[col_sh].iloc[-2]) if len(margin_sh) >= 2 else sh_latest
                    sz_prev = float(margin_sz[col_sz].iloc[-2]) if len(margin_sz) >= 2 else sz_latest
                    margin_chg = ((sh_latest+sz_latest) - (sh_prev+sz_prev)) / (sh_prev+sz_prev) * 100
                    margin_score = min(100, max(0, int(50 + margin_chg * 5)))
                    margin_lvl = "green" if margin_chg > 0.5 else ("yellow" if margin_chg > -1 else "red")
                    dapan_data["dims"]["margin"] = (margin_lvl, f"{margin_chg:+.2f}%")
                    dapan_data["hld"]["margin_score"] = margin_score
                    margin_ok = True
                except Exception as e:
                    print(f"[大盘] margin akshare fail: {e}")
                if not margin_ok and _ts_pro_dapan and _trade_date_dapan:
                    try:
                        _md = _ts_pro_dapan.margin_detail(trade_date=_trade_date_dapan)
                        if _md is not None and len(_md) > 0 and "rzye" in _md.columns:
                            _total_rz = float(_md["rzye"].sum())
                            # 用指数涨跌幅做融资融券变化代理
                            _idx_ret = _ts_pro_dapan.index_daily(ts_code="000001.SH", trade_date=_trade_date_dapan)
                            if _idx_ret is not None and len(_idx_ret) > 0:
                                _pct = float(_idx_ret["pct_chg"].iloc[0])
                                margin_score = min(100, max(0, int(50 + _pct * 10)))
                                margin_lvl = "green" if _pct > 0.5 else ("yellow" if _pct > -0.5 else "red")
                                dapan_data["dims"]["margin"] = (margin_lvl, f"指数代理 {_pct:+.2f}%")
                                dapan_data["hld"]["margin_score"] = margin_score
                                print("[大盘] ✅ margin tushare兜底")
                            else:
                                dapan_data["dims"]["margin"] = ("gray", "获取失败")
                                dapan_data["hld"]["margin_score"] = 50
                        else:
                            dapan_data["dims"]["margin"] = ("gray", "获取失败")
                            dapan_data["hld"]["margin_score"] = 50
                    except Exception as _e4:
                        print(f"[大盘] margin tushare兜底fail: {_e4}")
                        dapan_data["dims"]["margin"] = ("gray", "获取失败")
                        dapan_data["hld"]["margin_score"] = 50
                elif not margin_ok:
                    dapan_data["dims"]["margin"] = ("gray", "获取失败")
                    dapan_data["hld"]["margin_score"] = 50

                # --- 4. 换手率/成交额 (+ tushare兜底) ---
                if not _step("拉换手率"): return
                turn_ok = False
                try:
                    sh2 = ak.stock_zh_index_daily_em(symbol="sh000001")
                    turnover = float(sh2["amount"].iloc[-1]) if "amount" in sh2.columns else 0
                    turnover_pct = min(100, max(0, int(turnover / 5e10 * 100)))
                    turn_lvl = "green" if turnover > 5e10 else ("yellow" if turnover > 3e10 else "red")
                    dapan_data["dims"]["turnover"] = (turn_lvl, f"{turnover/1e8:.0f}亿")
                    dapan_data["hld"]["turnover_score"] = turnover_pct
                    turn_ok = True
                except Exception as e:
                    print(f"[大盘] turnover akshare fail: {e}")
                if not turn_ok and _ts_pro_dapan and _trade_date_dapan:
                    try:
                        _idx = _ts_pro_dapan.index_daily(ts_code="000001.SH", trade_date=_trade_date_dapan)
                        if _idx is not None and len(_idx) > 0:
                            turnover = float(_idx["amount"].iloc[0]) * 1e4  # tushare amount 是千元→元
                            turnover_pct = min(100, max(0, int(turnover / 5e10 * 100)))
                            turn_lvl = "green" if turnover > 5e10 else ("yellow" if turnover > 3e10 else "red")
                            dapan_data["dims"]["turnover"] = (turn_lvl, f"{turnover/1e8:.0f}亿")
                            dapan_data["hld"]["turnover_score"] = turnover_pct
                            print("[大盘] ✅ turnover tushare兜底")
                        else:
                            dapan_data["dims"]["turnover"] = ("gray", "获取失败")
                            dapan_data["hld"]["turnover_score"] = 50
                    except Exception as _e5:
                        print(f"[大盘] turnover tushare兜底fail: {_e5}")
                        dapan_data["dims"]["turnover"] = ("gray", "获取失败")
                        dapan_data["hld"]["turnover_score"] = 50
                elif not turn_ok:
                    dapan_data["dims"]["turnover"] = ("gray", "获取失败")
                    dapan_data["hld"]["turnover_score"] = 50

                # --- 综合评分 ---
                scores = [v for k, v in dapan_data["hld"].items() if k.endswith("_score")]
                avg = sum(scores) / len(scores) if scores else 50
                if avg >= 65: hld_col, hld_lvl = "green", "🟢 可以开新仓"
                elif avg >= 40: hld_col, hld_lvl = "yellow", "🟡 谨慎操作"
                else: hld_col, hld_lvl = "red", "🔴 禁止开新仓"
                dapan_data["hld"]["avg"] = avg
                dapan_data["hld"]["col"] = hld_col
                dapan_data["hld"]["lvl"] = hld_lvl

                # --- 情绪引擎 (+ tushare 数据兜底校验) ---
                if not _step("计算情绪引擎"): return
                emo_stage = "震荡"
                skill_py = _os.path.expanduser("~/.qclaw/workspace-ek2hwmmwwhxi3mz3/skills/情绪周期流/scripts/情绪周期流_engine.py")
                emo_engine_data = None
                if _os.path.exists(skill_py):
                    try:
                        r = _sp.run(["/Library/Frameworks/Python.framework/Versions/3.11/bin/python3", skill_py, "--market", "--json"],
                                    capture_output=True, text=True, timeout=15)
                        if r.returncode == 0 and r.stdout.strip():
                            emo_engine_data = _js.loads(r.stdout.strip())
                            emo_stage = emo_engine_data.get("emotion_stage", emo_engine_data.get("stage", "震荡"))
                            # 校验: 引擎的新浪数据源可能挂了 → 用 tushare 算的真实数据覆盖
                            _engine_zt = emo_engine_data.get("limit_up_count", 0)
                            _engine_up_ratio = emo_engine_data.get("breadth_up_ratio", 0.5)
                            _tushare_zt = zt if 'zt' in dir() and zt else 0
                            _tushare_up = up if 'up' in dir() and up else 0
                            _tushare_dn = dn if 'dn' in dir() and dn else 0
                            # 如果引擎返回的涨停 < 10 但 tushare 有真实数据 → 引擎脏了, 用 tushare 重算
                            if _engine_zt < 10 and _tushare_zt > 10:
                                print(f"[大盘] ⚠️ 情绪引擎新浪数据源挂了 (engine_zt={_engine_zt}, tushare_zt={_tushare_zt}), 用 tushare 重算情绪")
                                _total_t = (_tushare_up or 0) + (_tushare_dn or 0)
                                _up_ratio = _tushare_up / _total_t if _total_t > 0 else 0.5
                                if _tushare_zt >= 80 and _up_ratio >= 0.7: emo_stage = "高潮"
                                elif _tushare_zt >= 40 and _up_ratio >= 0.55: emo_stage = "发酵"
                                elif _tushare_zt >= 15 and _up_ratio >= 0.5: emo_stage = "启动"
                                elif _tushare_zt < 10 and _up_ratio < 0.4: emo_stage = "冰点"
                                elif _up_ratio < 0.45: emo_stage = "退潮"
                                else: emo_stage = "震荡"
                                print(f"[大盘] ✅ tushare 情绪重算 stage={emo_stage} zt={_tushare_zt} up_ratio={_up_ratio:.2f}")
                    except Exception as e:
                        print(f"[大盘] emo engine fail: {e}")
                dapan_data["emo"]["stage"] = emo_stage
                dapan_data["emo"]["up"] = up if 'up' in dir() else 0
                dapan_data["emo"]["dn"] = dn if 'dn' in dir() else 0
                dapan_data["emo"]["zt"] = zt if 'zt' in dir() else 0
                dapan_data["emo"]["dt"] = dt if 'dt' in dir() else 0

                # --- 热门/冷门板块 (多源 fallback, 热门12+冷门9) ---
                # 🔥 快速路径: 同花顺优先 (0.4s), 东财限流要 10s+ 超时
                hot8 = cold8 = None
                # 源1: 同花顺 行业板块
                try:
                    ind = safe_call(ak.stock_board_industry_summary_ths, fallback=pd.DataFrame(), label="ak.stock_board_industry_summary_ths")
                    if ind is not None and len(ind) > 0 and "涨跌幅" in ind.columns:
                        ind_sorted = ind.sort_values(by="涨跌幅", ascending=False)
                        hot8 = []
                        for _, row in ind_sorted.head(12).iterrows():
                            hot8.append((str(row.get("板块", "")), row.get("涨跌幅", 0),
                                         f"净流入{row.get('净流入',0)}亿 领涨{row.get('领涨股','')}"))
                        cold8 = []
                        for _, row in ind_sorted.tail(9).iterrows():
                            cold8.append((str(row.get("板块", "")), row.get("涨跌幅", 0),
                                          f"净流入{row.get('净流入',0)}亿 领涨{row.get('领涨股','')}"))
                        print(f"[大盘] ✅ 板块源=同花顺行业 {len(ind)}行")
                except Exception as ths_e:
                    print(f"[大盘] 同花顺行业fail → 兜底东财: {str(ths_e)[:40]}")
                # 源2 fallback: 东方财富 概念板块
                if hot8 is None:
                    try:
                        cons = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                        if cons is not None and len(cons) > 0 and "涨跌幅" in cons.columns:
                            cs = cons.sort_values(by="涨跌幅", ascending=False)
                            hot8 = [(str(row.get("板块名称", "")), row.get("涨跌幅", 0))
                                    for _, row in cs.head(12).iterrows()]
                            cold8 = [(str(row.get("板块名称", "")), row.get("涨跌幅", 0))
                                     for _, row in cs.tail(9).iterrows()]
                            print("[大盘] ✅ 板块源=东财概念")
                    except Exception as e:
                        print(f"[大盘] 东财概念fail (跳过): {str(e)[:40]}")
                # 源3 fallback: tushare 申万行业分类 + 指数日线
                if hot8 is None:
                    try:
                        import tushare as _ts_dp
                        _pro_dp = _ts_dp.pro_api()
                        today = _dt_dp.now().strftime("%Y%m%d") if '_dt_dp' in dir() else time.strftime("%Y%m%d")
                        idx_list = _pro_dp.index_classify(level="L2", src="SW2021")
                        if idx_list is not None and len(idx_list) > 0:
                            # 取最近交易日行情
                            from datetime import datetime as _dt2
                            _dl = _pro_dp.trade_cal(exchange="SSE", start_date=today, end_date=today, is_open="1")
                            _td = today
                            if _dl is None or len(_dl) == 0:
                                _dl2 = _pro_dp.trade_cal(exchange="SSE", start_date="20260801",
                                                         end_date=today, is_open="1")
                                if _dl2 is not None and len(_dl2) > 0:
                                    _td = max(_dl2["cal_date"].tolist())
                            # 批量拉行业指数日线
                            idx_codes = idx_list["index_code"].tolist()[:30]
                            idx_dfs = []
                            for _ic in idx_codes[:10]:
                                try:
                                    _idf = _pro_dp.index_daily(ts_code=_ic, trade_date=_td)
                                    if _idf is not None and len(_idf) > 0:
                                        _r = _idf.iloc[0]
                                        _nm_row = idx_list[idx_list["index_code"]==_ic]
                                        _nm = _nm_row["industry_name"].values[0] if len(_nm_row) else _ic
                                        idx_dfs.append((_nm, float(_r.get("pct_chg", 0))))
                                except Exception: pass
                            idx_dfs.sort(key=lambda x: x[1], reverse=True)
                            hot8 = [(n, c) for n, c in idx_dfs[:8]]
                            cold8 = [(n, c) for n, c in idx_dfs[-8:]]
                            print(f"[大盘] ✅ 板块源=tushare申万 {len(idx_dfs)}行")
                    except Exception as e:
                        print(f"[大盘] tushare板块fail: {e}")
                if hot8:
                    dapan_data["sectors"]["hot"] = hot8
                    dapan_data["sectors"]["cold"] = cold8

                # ======== 5. 最近20日趋势 (上证涨跌幅 + 情绪分) ========
                print(f"[大盘] 👉 进入 trend10 代码块...", flush=True)
                if not _step("拉20日趋势"): return
                # 策略: akshare 新浪指数优先 (稳定), tushare 兜底 (可能被熔断 hang 住)
                trend10 = []
                _tushare_map = {}

                # Step 1: akshare 拉上证日线 (当前机器最稳)
                try:
                    from ui._akshare_fetcher import fetch_index_daily as _fi
                    _idx_df = _fi(symbol="sh000001", days=25)
                    if _idx_df is not None and len(_idx_df) > 0:
                        for _ir in _idx_df.itertuples(index=False):
                            _pct3 = float(getattr(_ir, "pct_chg", 0) or 0)
                            _close3 = float(_ir.close)
                            # akshare 指数接口没有 turnover_rate / amount, 用 0 代替
                            _vol3 = 0; _tr3 = 0
                            # 自算 emo score (与原 tushare 逻辑一致)
                            _base3 = 50
                            if _pct3 > 1: _base3 += 20
                            elif _pct3 > 0: _base3 += 8
                            elif _pct3 < -1: _base3 -= 20
                            elif _pct3 < 0: _base3 -= 8
                            if _vol3 > 5000: _base3 += 10
                            elif _vol3 < 3000: _base3 -= 5
                            if _tr3 > 2: _base3 += 8
                            elif _tr3 < 0.5: _base3 -= 5
                            _emo_s3 = max(10, min(95, _base3))
                            if hasattr(_ir.date, "strftime"):
                                _full_k = _ir.date.strftime("%Y-%m-%d")
                            else:
                                _full_k = str(_ir.date)[:10]
                            _tushare_map[_full_k] = {
                                "full_date": _full_k,
                                "date": _full_k[5:7]+"/"+_full_k[8:10],
                                "pct": _pct3,
                                "emo": _emo_s3,
                                "zt": 0,
                                "close": _close3,
                            }
                        print(f"[大盘] ✅ akshare trend10 拉到: {len(_tushare_map)}天, 最新={max(_tushare_map.keys())}")
                except Exception as _e_ak_primary:
                    print(f"[大盘] akshare trend10 优先fail: {_e_ak_primary}, 尝试 tushare...")

                # Step 2: 如果 akshare 没拉到, 尝试 tushare (有 hang 风险, 用 except 兜底)
                if not _tushare_map:
                    try:
                        import tushare as _ts_trend2
                        from datetime import date as _dt_date_t2
                        _today_yyyymmdd = _dt_date_t2.today().strftime("%Y%m%d")
                        _pro2 = _ts_trend2.pro_api()
                        _cal2 = _pro2.trade_cal(exchange="SSE", start_date="20250101",
                                                end_date=_today_yyyymmdd, is_open="1")
                        _td_list2 = sorted(_cal2["cal_date"].tolist())[-22:] if _cal2 is not None else []
                        _t10_2 = _td_list2[-20:] if len(_td_list2) >= 20 else _td_list2
                        for _td2 in _t10_2:
                            try:
                                _df2 = _pro2.index_daily(ts_code="000001.SH", trade_date=_td2)
                                if _df2 is None or len(_df2) == 0: continue
                                _r2 = _df2.iloc[0]
                                _pct3 = float(_r2.get("pct_chg", 0) or 0)
                                _vol3 = float(_r2.get("amount", 0) or 0) / 1e5
                                _tr3 = float(_r2.get("turnover_rate", 0) or 0)
                                _close3 = float(_r2.get("close", 0) or 0)
                                _base3 = 50
                                if _pct3 > 1: _base3 += 20
                                elif _pct3 > 0: _base3 += 8
                                elif _pct3 < -1: _base3 -= 20
                                elif _pct3 < 0: _base3 -= 8
                                if _vol3 > 5000: _base3 += 10
                                elif _vol3 < 3000: _base3 -= 5
                                if _tr3 > 2: _base3 += 8
                                elif _tr3 < 0.5: _base3 -= 5
                                _emo_s3 = max(10, min(95, _base3))
                                _full_k = _td2[:4]+"-"+_td2[4:6]+"-"+_td2[6:8]
                                _tushare_map[_full_k] = {
                                    "full_date": _full_k,
                                    "date": _td2[4:6]+"/"+_td2[6:8],
                                    "pct": _pct3,
                                    "emo": _emo_s3,
                                    "zt": 0,
                                    "close": _close3,
                                }
                            except Exception: continue
                        print(f"[大盘] tushare trend10 拉到: {len(_tushare_map)}天, 最新={max(_tushare_map.keys()) if _tushare_map else '无'}")
                    except Exception as _e_ts:
                        print(f"[大盘] tushare trend10 fail: {_e_ts}")

                # ==== 两个都挂了 → 兜底: 纯 akshare 直连 ====
                if not _tushare_map:
                    try:
                        from ui._akshare_fetcher import fetch_index_daily as _fi
                        _idx_df = _fi(symbol="sh000001", days=25)
                        if _idx_df is not None and len(_idx_df) > 0:
                            for _ir in _idx_df.itertuples(index=False):
                                _pct3 = float(getattr(_ir, "pct_chg", 0) or 0)
                                _close3 = float(_ir.close)
                                # akshare 指数接口没有 turnover_rate / amount, 用 0 代替
                                _vol3 = 0; _tr3 = 0
                                # 自算 emo score (与 tushare 逻辑一致)
                                _base3 = 50
                                if _pct3 > 1: _base3 += 20
                                elif _pct3 > 0: _base3 += 8
                                elif _pct3 < -1: _base3 -= 20
                                elif _pct3 < 0: _base3 -= 8
                                if _vol3 > 5000: _base3 += 10
                                elif _vol3 < 3000: _base3 -= 5
                                if _tr3 > 2: _base3 += 8
                                elif _tr3 < 0.5: _base3 -= 5
                                _emo_s3 = max(10, min(95, _base3))
                                if hasattr(_ir.date, "strftime"):
                                    _full_k = _ir.date.strftime("%Y-%m-%d")
                                else:
                                    _full_k = str(_ir.date)[:10]
                                _tushare_map[_full_k] = {
                                    "full_date": _full_k,
                                    "date": _full_k[5:7]+"/"+_full_k[8:10],
                                    "pct": _pct3,
                                    "emo": _emo_s3,
                                    "zt": 0,
                                    "close": _close3,
                                }
                            print(f"[大盘] ✅ akshare trend10 兜底拉到: {len(_tushare_map)}天, 最新={max(_tushare_map.keys())}")
                    except Exception as _e_ak:
                        print(f"[大盘] akshare trend10 兜底也挂: {_e_ak}")
                        _tushare_map = {}

                # Step 2: 读 market_sentiment_data.json (可能过时, 但 sentiment_score 更准)
                _emo_json = _os.path.expanduser("~/.qclaw/workspace-agent-85985980/market_sentiment_data.json")
                _json_map = {}
                try:
                    if _os.path.exists(_emo_json):
                        with open(_emo_json) as _fj:
                            _sd = _js.load(_fj)
                        _dl = _sd.get("data", [])
                        for _d in _dl:
                            _dt2 = str(_d.get("date", ""))
                            if len(_dt2) == 8:
                                _full2 = _dt2[:4]+"-"+_dt2[4:6]+"-"+_dt2[6:8]
                            else:
                                _full2 = _dt2
                            _json_map[_full2] = float(_d.get("sentiment_score", 50) or 50)
                        print(f"[大盘] JSON 有 sentiment_score: {len(_json_map)}天, 最新={max(_json_map.keys()) if _json_map else '无'}")
                except Exception as _e_j:
                    print(f"[大盘] JSON trend10 fail: {_e_j}")

                # Step 3: 合并 — tushare 做底 (日期永远新鲜), JSON sentiment_score 覆盖
                if _tushare_map:
                    for _k, _rec in _tushare_map.items():
                        if _k in _json_map:
                            _rec["emo"] = _json_map[_k]  # JSON 情绪分更准则覆盖
                        trend10.append(_rec)
                    trend10.sort(key=lambda x: x["full_date"])
                    print(f"[大盘] ✅ 10日趋势: {len(trend10)}天, 最新={trend10[-1]['full_date']}")
                else:
                    # tushare 也挂了 → 退回到纯 JSON (可能过时)
                    try:
                        if _os.path.exists(_emo_json):
                            with open(_emo_json) as _fj:
                                _sd = _js.load(_fj)
                            _dl = _sd.get("data", [])
                            for _d in _dl[-10:]:
                                _dt2 = str(_d.get("date", ""))
                                if len(_dt2) == 8:
                                    _full2 = _dt2[:4]+"-"+_dt2[4:6]+"-"+_dt2[6:8]
                                else:
                                    _full2 = _dt2
                                trend10.append({
                                    "full_date": _full2,
                                    "date": _dt2[4:6]+"/"+_dt2[6:8],
                                    "pct": float(_d.get("sh_chg", 0) or 0),
                                    "emo": float(_d.get("sentiment_score", 50) or 50),
                                    "zt": int(_d.get("zt_count", 0) or 0),
                                    "close": _d.get("index_close", 0),
                                })
                            print(f"[大盘] ⚠️ tushare挂了, 纯JSON fallback: {len(trend10)}天 (可能过时)")
                    except Exception as _e_last:
                        print(f"[大盘] ❌ trend10 全部数据源挂了: {_e_last}")
                dapan_data["trend10"] = trend10

                # 5.6 把 breadth 实时数据 (up/dn/zt/dt) 合并进 trend10 最新一天
                if trend10 and 'up' in dir() and up is not None:
                    _td_full = _trade_date_dapan[:4]+"-"+_trade_date_dapan[4:6]+"-"+_trade_date_dapan[6:8] if _trade_date_dapan else None
                    for _tr in trend10:
                        if _td_full and _tr.get("full_date") == _td_full:
                            _tr["up"] = up; _tr["dn"] = dn; _tr["zt"] = zt; _tr["dt"] = dt
                            break
                    else:
                        # 没匹配上就填最新一天
                        trend10[-1]["up"] = up; trend10[-1]["dn"] = dn
                        trend10[-1]["zt"] = zt; trend10[-1]["dt"] = dt
                    print(f"[大盘] ✅ breadth 已合并: up={up} dn={dn} zt={zt} dt={dt}")

                # 5.5 后台直接同步 trend10 → emo_hist (后台线程, 不依赖 UI)
                try:
                    import json as _js_as, os as _os_as
                    _asp = _os_as.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_emo_history.json")
                    if trend10:
                        if _os_as.path.exists(_asp):
                            with open(_asp) as _af: _hr = _js_as.load(_af)
                            if isinstance(_hr, list):
                                _h2 = {}
                                for _x in _hr: _h2[_x.get("date","")] = _x
                                _hr = _h2
                        else:
                            _hr = {}
                        _achg = False
                        for _d in trend10:
                            _k = _d.get("full_date"); _es = float(_d.get("emo",50) or 50); _pc = float(_d.get("pct",0) or 0)
                            if _es >= 70: _ast = "高潮"
                            elif _es >= 60: _ast = "发酵"
                            elif _es >= 50: _ast = "启动"
                            elif _es >= 40: _ast = "震荡"
                            elif _es >= 30: _ast = "分歧"
                            else: _ast = "退潮"
                            if _k in _hr:
                                _r = _hr[_k]; _r["emo_score"] = _es; _r["pct"] = _pc
                                if not _r.get("stage") or _r.get("stage","").strip() in ("震荡",""): _r["stage"] = _ast
                                # breadth 数据: 有就更新, 没有就保留原值
                                if _d.get("up") is not None: _r["up"] = _d.get("up")
                                if _d.get("dn") is not None: _r["dn"] = _d.get("dn")
                                if _d.get("zt"): _r["zt"] = _d.get("zt")
                                if _d.get("dt") is not None: _r["dt"] = _d.get("dt")
                                _achg = True
                            else:
                                _hr[_k] = {"date":_k,"pnl":"","ths":"","stage":_ast,
                                           "emo_score":_es,"pct":_pc,"close":_d.get("close",0),
                                           "zt":_d.get("zt",0),"up":_d.get("up"),"dn":_d.get("dn"),"dt":_d.get("dt")}
                                _achg = True
                        if _achg:
                            with open(_asp, "w") as _af: _js_as.dump(_hr, _af, ensure_ascii=False, indent=2)
                            print(f"[大盘] ✅ emo_hist 已同步 {len(_hr)}天 → {_asp}", flush=True)
                            # 后台线程: 自动 push 到 Gist
                            try:
                                import threading as _th_as2
                                def _bg_gist():
                                    try:
                                        _cfg = self._get_emo_sync_config()
                                        if _cfg.get("gist_token") and _cfg.get("gist_id"):
                                            _r2 = self._emo_gist_push(_hr)
                                            print(f"[大盘] ☁️ Gist push: {_r2.get('msg','')}", flush=True)
                                    except Exception as _gx:
                                        print(f"[大盘] Gist push skip: {_gx}")
                                _th_as2.Thread(target=_bg_gist, daemon=True).start()
                            except: pass
                        else:
                            print(f"[大盘] emo_hist 无变化 ({len(_hr)}天)", flush=True)
                except Exception as _e_as:
                    print(f"[大盘] emo_hist 后台同步fail: {_e_as}", flush=True)

                # ======== 核心数据就绪 → 先存 snapshot + 写 pending (不等盘中警告) ========
                print(f"[大盘分析] ✅ 核心数据就绪 score={avg:.0f} emo={emo_stage}", flush=True)
                try:
                    self._save_dapan_snapshot(dapan_data)
                    print(f"[大盘] ✅ snapshot 已保存 trend10={len(dapan_data.get('trend10',[]))}天")
                except Exception as _e_ss_bg:
                    print(f"[大盘] snapshot 保存fail: {_e_ss_bg}")
                self._dapan_pending = dapan_data  # 立即让主线程更新 UI

                # ======== 盘中警告数据 (失败不影响主流程) ========
                if not _step("拉盘中警告"): return
                try:
                    print("[大盘] ⏳ 盘中警告拉取...", flush=True)
                    alert = self._fetch_intraday_alert_data()
                    dapan_data["alert"] = alert
                    _cs = alert.get("composite", {}) if isinstance(alert, dict) else {}
                    print(f"[大盘] ✅ 盘中警告 score={_cs.get('score','?')} "
                          f"level={_cs.get('level_cn','?')}", flush=True)
                except Exception as ea:
                    print(f"[大盘] ❌ 盘中警告fail: {ea}", flush=True)
                    dapan_data["alert"] = None

                # ======== 盘中警告完成后二次更新 UI (刷新 alert 字段) ========
                print(f"[大盘分析] ✅ 完整数据就绪 score={avg:.0f} emo={emo_stage}", flush=True)
                self._dapan_pending = dapan_data  # 二次刷新 (带 alert)

            except Exception as e:
                import traceback; traceback.print_exc()
                print(f"[大盘分析] ❌ 总体异常: {e}", flush=True)
            finally:
                # 禁用 ⏹️ 停止按钮, 不管成功/失败/停止
                try:
                    self.root.after(0, lambda: self._dapan_stop_btn.config(state="disabled", bg="#555"))
                except Exception:
                    pass
        _th.Thread(target=_run, daemon=True).start()


    def _dapan_update_ui(self, data):
        """主线程UI更新: 把后台线程拉到的数据渲染到控件上"""
        # 缓存完整数据, Canvas <Configure> 事件触发重绘时用
        self._dapan_full_data = data
        try:
            hld = data.get("hld", {})
            dims = data.get("dims", {})
            emo = data.get("emo", {})
            sec = data.get("sectors", {})

            # 1. 红绿灯
            hld_col = hld.get("col", "gray")
            self._dapan_hld_canvas.delete("all")
            self._dapan_hld_canvas.create_oval(3, 3, 25, 25,
                fill=self._dapan_hld_col.get(hld_col, "#BDBDBD"),
                outline="#424242", width=2)
            self._dapan_score_var.set(f"{hld.get('avg', 0):.0f}")
            self._dapan_level_var.set(hld.get("lvl", "--"))

            # 2. 水温计 (推荐仓位%)
            try:
                # 评分 → 仓位%
                score = hld.get("avg", 50)
                if score is None or (isinstance(score, float) and (score != score)):  # NaN check
                    score = 50
                score = float(score) if not isinstance(score, (int, float)) else score
                # 情绪修正
                emo_s = emo.get("stage", "震荡")
                emo_pos = {"冰点": 0, "启动": 15, "发酵": 30, "高潮": 50,
                           "分歧": 15, "退潮": 0}.get(emo_s, 15)
                # 综合仓位
                base_pos = min(100, max(0, int(score)))
                rec_pct = int(base_pos * 0.5 + emo_pos * 0.5)
                # 冰点/退潮强制0%
                if emo_s in ("冰点", "退潮"): rec_pct = min(rec_pct, 10)
                # 画水温计
                tc = self._dapan_term_canvas
                tc.delete("all")
                # 外壳
                tc.create_rectangle(8, 4, 14, 50, fill="#37474F", outline="#78909C", width=1)
                tc.create_oval(6, 48, 16, 58, fill="#37474F", outline="#78909C", width=1)
                # 填充
                fill_h = int(rec_pct / 100 * 42)  # 4~48
                fill_y = 4 + (42 - fill_h)
                if rec_pct > 50: fc = "#C62828"
                elif rec_pct > 25: fc = "#F57F17"
                elif rec_pct > 0: fc = "#FFB74D"
                else: fc = "#2E7D32"
                tc.create_rectangle(10, fill_y, 12, 48, fill=fc, outline="")
                tc.create_oval(8, 50, 14, 56, fill=fc, outline="")
                self._dapan_term_pct_var.set(f"{rec_pct}%")
                self._dapan_term_pct_var.set(f"{rec_pct}%")
            except Exception as e: print(f"[大盘] term fail: {e}")

            # 3. 四维度 (UI 已移除, 跳过)
            if hasattr(self, '_dapan_dims') and self._dapan_dims:
                for key, (lv, txt) in dims.items():
                    d = self._dapan_dims.get(key)
                    if not d: continue
                    try:
                        d["lc"].delete("all")
                        d["lc"].create_oval(1, 1, 13, 13,
                            fill=self._dapan_hld_col.get(lv, "#BDBDBD"),
                            outline="#424242", width=1)
                        d["sv"].set(txt)
                    except Exception: pass

            # 4. 情绪周期大字明确显示 + 情绪条高亮
            emo_stage = emo.get("stage", "震荡")
            emoji_map = {"冰点": "❄️", "启动": "🌱", "发酵": "🔥",
                         "高潮": "💥", "分歧": "⚡", "退潮": "📉"}
            self._dapan_emo_var.set(f"{emoji_map.get(emo_stage,'📊')} {emo_stage}")
            self._dapan_updn_var.set(f"涨{emo.get('up',0)}/跌{emo.get('dn',0)}  ZT{emo.get('zt',0)} DT{emo.get('dt',0)}")

            # 盘中警告小条渲染
            alert = data.get("alert")
            if alert:
                comp = alert.get("composite", {})
                score = comp.get("score", 0)
                level_cn = comp.get("level_cn", "--")
                signal = comp.get("signal", "⏳")
                level = comp.get("level", "warning")
                # 关键指数一行摘要
                idx_parts = []
                for it in alert.get("indices", [])[:3]:
                    pct = it["pct"]
                    idx_parts.append(f"{it['name'][:2]}{pct:+.2f}%")
                idx_str = " ".join(idx_parts) if idx_parts else "无指数数据"
                br = alert.get("breadth", {})
                br_str = f"涨{br.get('up',0)}/跌{br.get('down',0)}"
                text = f"{signal}{level_cn} {score}分  {idx_str}  {br_str}"
                if getattr(self, "_dapan_alert_var", None) is not None:
                    self._dapan_alert_var.set(text)
                # 根据等级变色
                fg_map = {"excellent": "#4CAF50", "good": "#42A5F5",
                          "warning": "#FFD54F", "danger": "#EF5350"}
                if getattr(self, "_dapan_alert_lbl", None) is not None:
                    self._dapan_alert_lbl.config(fg=fg_map.get(level, "#E0E0E0"))
            else:
                if getattr(self, "_dapan_alert_var", None) is not None:
                    self._dapan_alert_var.set("⏳ 非交易时段或拉取失败")
                if getattr(self, "_dapan_alert_lbl", None) is not None:
                    self._dapan_alert_lbl.config(fg="#9E9E9E")
            # 情绪条: 当前位置金色边框+加粗文字
            try:
                bar = self._dapan_emo_strip_canvas
                bar.delete("all")
                stages = [("冰点", "#2E7D32"), ("启动", "#F57F17"),
                          ("发酵", "#FF6F00"), ("高潮", "#C62828"),
                          ("分歧", "#6A1B9A"), ("退潮", "#455A64"),
                          ("冰点", "#2E7D32")]
                sw = 90
                for si, (sname, scolor) in enumerate(stages):
                    x1 = si * sw + 2; x2 = x1 + sw - 2
                    cur = (sname == emo_stage)
                    bar.create_rectangle(x1, 2, x2, 24, fill=scolor,
                                         outline="#FFD700" if cur else "#555",
                                         width=3 if cur else 1)
                    if cur:
                        bar.create_text((x1+x2)/2, 13, text=f"▶{sname}◀",
                                        fill="#FFD700", font=("", 9, "bold"))
                    else:
                        bar.create_text((x1+x2)/2, 13, text=sname,
                                        fill="#E0E0E0", font=("", 8))
            except Exception as e: print(f"[大盘] emo strip fail: {e}")

            # 5. 热门/冷门板块网格卡片 (可双击打开成分股)
            def _render_grid(parent_frame, data, is_hot, cols):
                """在 parent_frame 里渲染 cols 列的网格卡片, 绑定双击打开成分股"""
                for w in parent_frame.winfo_children():
                    w.destroy()
                if not data:
                    tk.Label(parent_frame, text="⏳ 暂无数据", bg="#FAFAFA",
                             fg="#999").pack(padx=10, pady=20)
                    return
                def _bind_dblclick(widgets, _nm):
                    """给一组widget全绑双击事件"""
                    for w in widgets:
                        try:
                            w.bind("<Double-Button-1>", lambda e, n=_nm: self._open_sector_detail(n))
                            w.bind("<Enter>", lambda e, c=widgets: [x.config(cursor="hand2") for x in c])
                            w.bind("<Leave>", lambda e, c=widgets: [x.config(cursor="") for x in c])
                        except Exception: pass
                for idx, item in enumerate(data):
                    r, c = divmod(idx, cols)
                    bg = "#FFEBEE" if is_hot else "#E8F5E9"
                    fg = "#C62828" if is_hot else "#2E7D32"
                    # 卡片
                    card = tk.Frame(parent_frame, bg=bg, highlightbackground=fg,
                                    highlightthickness=1, padx=4, pady=2)
                    card.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
                    parent_frame.columnconfigure(c, weight=1)
                    nm = item[0]; chg = item[1]
                    top_row = tk.Frame(card, bg=bg); top_row.pack(fill=tk.X)
                    nm_lbl = tk.Label(top_row, text=f"{idx+1}. {nm}", bg=bg, fg="#212121",
                                      font=("", 8, "bold"), anchor="w")
                    nm_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    chg_fg = "#C62828" if chg >= 0 else "#2E7D32"
                    chg_lbl = tk.Label(top_row, text=f"{chg:+.2f}%", bg=bg, fg=chg_fg,
                                       font=("", 9, "bold"))
                    chg_lbl.pack(side=tk.RIGHT)
                    widgets = [card, top_row, nm_lbl, chg_lbl]
                    if len(item) >= 3 and item[2]:
                        det_lbl = tk.Label(card, text=str(item[2])[:28], bg=bg, fg="#757575",
                                           font=("", 7), anchor="w")
                        det_lbl.pack(fill=tk.X); widgets.append(det_lbl)
                    _bind_dblclick(widgets, nm)

            if hasattr(self, '_dapan_hot_inner'):
                _render_grid(self._dapan_hot_inner, sec.get("hot", []), True, 3)
            if hasattr(self, '_dapan_cold_inner'):
                _render_grid(self._dapan_cold_inner, sec.get("cold", []), False, 3)

            # 6. 近 N 日趋势 Canvas
            trend10 = data.get("trend10", [])
            self._dapan_trend_data = trend10  # 缓存, Canvas resize 时自动重绘
            try:
                tc = self._dapan_trend_canvas
                tc.delete("all")
                cw = tc.winfo_width()
                # 还没布局完 (winfo_width 返回 1), 先跳过, 等 <Configure> 事件重绘
                if cw < 100 and trend10:
                    tc.create_text(400, 80, text="⏳ 等待布局...", fill="#90A4AE", font=("", 10))
                    return
                cw = cw or 900
                # 颜色映射: 情绪分→颜色
                def _emo_col(s):
                    if s >= 70: return "#C62828"
                    if s >= 60: return "#FF6F00"
                    if s >= 50: return "#F57F17"
                    if s >= 40: return "#FFD54F"
                    if s >= 30: return "#9E9E9E"
                    return "#2E7D32"
                if not trend10:
                    tc.create_text(400, 80, text="⏳ 暂无10日趋势数据",
                                   fill="#90A4AE", font=("", 10))
                else:
                    # cw 已在外层算好
                    ch = 160
                    pad_l, pad_r, pad_t = 8, 8, 4
                    plot_w = cw - pad_l - pad_r
                    n = len(trend10)
                    col_w = plot_w / n

                    # ======== 第1行: 标题 + 图例 ========
                    tc.create_text(cw/2, 8, text=f"📈 近{n}日上证涨跌 + 情绪分趋势",
                                   fill="#1A237E", font=("", 9, "bold"))
                    tc.create_text(pad_l+4, 18, text="●情绪分", fill="#FF6F00",
                                   font=("", 8), anchor="w")
                    tc.create_text(pad_l+60, 18, text="▌上证涨跌", fill="#C62828",
                                   font=("", 8), anchor="w")

                    # ======== 每天一列 ========
                    col_x = [pad_l + i * col_w for i in range(n)]
                    # 过滤 NaN pct 值
                    _valid_pcts = [d["pct"] for d in trend10 if d.get("pct") is not None and d["pct"] == d["pct"]]
                    max_abs = max(abs(p) for p in _valid_pcts) if _valid_pcts else 1
                    if max_abs == 0: max_abs = 1

                    # 各区域 Y 坐标
                    Y_LABEL_TOP = 24    # 日期标签
                    Y_LABEL_BTM = 40
                    Y_HEAT_TOP  = 44    # 热力方块
                    Y_HEAT_BTM  = 58
                    Y_SCORE_TOP = 62    # 情绪分数字
                    Y_SCORE_BTM = 74
                    Y_CHART_TOP = 78    # 涨跌柱 + 折线区域
                    Y_CHART_BTM = 140
                    mid_y = (Y_CHART_TOP + Y_CHART_BTM) / 2

                    for i, d in enumerate(trend10):
                        cx = col_x[i] + col_w / 2
                        cx_l = col_x[i] + 2  # 列左边界
                        cx_r = col_x[i] + col_w - 2  # 列右边界
                        chg = d["pct"]
                        # NaN 防护: 跳过无效数据
                        if chg is None or (isinstance(chg, float) and chg != chg):
                            chg = 0.0
                        emo_s = d["emo"]
                        if emo_s is None or (isinstance(emo_s, float) and emo_s != emo_s):
                            emo_s = 50.0
                        date_str = d["date"]
                        full_date = d.get("full_date", date_str)
                        is_today = (i == n-1)

                        # 背景卡片 (最后一天加金色边框)
                        card_bg = "#FFF8E1" if is_today else "#FFFFFF"
                        card_bd = "#FF6F00" if is_today else "#CFD8DC"
                        tc.create_rectangle(cx_l, Y_LABEL_TOP - 2, cx_r, 152,
                                            fill=card_bg, outline=card_bd, width=1 if is_today else 1)

                        # ① 日期标签
                        date_fg = "#B71C1C" if is_today else "#455A64"
                        date_font = ("", 9, "bold") if is_today else ("", 8)
                        tc.create_text(cx, (Y_LABEL_TOP+Y_LABEL_BTM)/2,
                                       text=date_str, fill=date_fg, font=date_font)
                        if is_today:
                            tc.create_text(cx, Y_LABEL_TOP - 2, text="★",
                                           fill="#FF6F00", font=("", 9, "bold"), anchor="s")

                        # ② 热力方块
                        heat_col = _emo_col(emo_s)
                        tc.create_rectangle(cx_l + 6, Y_HEAT_TOP, cx_r - 6, Y_HEAT_BTM,
                                            fill=heat_col, outline="white", width=1)

                        # ③ 情绪分数字 (热力方块里面)
                        tc.create_text(cx, (Y_HEAT_TOP+Y_HEAT_BTM)/2,
                                       text=f"{emo_s:.0f}", fill="white",
                                       font=("", 9, "bold"))

                        # ④ 情绪分折线圆点 (在 CHART_TOP 线上方)
                        emo_y = Y_CHART_TOP - 4 - (emo_s / 100 * 10)  # emo 越高越往上
                        tc.create_oval(cx-3, emo_y-3, cx+3, emo_y+3,
                                       fill=heat_col, outline="white", width=1)

                        # ⑤ 涨跌幅柱子 (NaN 已在上面兜底为 0.0)
                        try:
                            bh = int(abs(chg) / max_abs * ((Y_CHART_BTM - Y_CHART_TOP)/2 - 2))
                        except (ValueError, ZeroDivisionError):
                            bh = 0
                        if chg >= 0:
                            tc.create_rectangle(cx-5, mid_y - bh, cx+5, mid_y,
                                                fill="#C62828", outline="#C62828")
                        elif chg < 0:
                            tc.create_rectangle(cx-5, mid_y, cx+5, mid_y + bh,
                                                fill="#2E7D32", outline="#2E7D32")

                        # ⑥ 涨跌%标注
                        tcol = "#C62828" if chg >= 0 else "#2E7D32"
                        tc.create_text(cx, mid_y - bh - 3 if chg >= 0 else mid_y + bh + 3,
                                       text=f"{chg:+.1f}", fill=tcol,
                                       font=("", 8, "bold"),
                                       anchor="s" if chg >= 0 else "n")

                        # 保存坐标给折线用
                        d["_cx"] = cx
                        d["_emo_y"] = emo_y

                    # ======== 画情绪分折线 (连圆点) ========
                    pts = [(d["_cx"], d["_emo_y"]) for d in trend10]
                    if len(pts) >= 2:
                        flat = [coord for p in pts for coord in p]
                        tc.create_line(*flat, fill="#FF6F00", width=2, smooth=True)

                    # ======== 中间零线 ========
                    tc.create_line(pad_l, mid_y, pad_l + plot_w, mid_y,
                                   fill="#B0BEC5", width=1, dash=(2, 2))

                    # (tooltip 已移除 - 精要数据直接显示在情绪周期日历格子里)
            except Exception as e: print(f"[大盘] trend10 Canvas fail: {e}")

            # 注意: emo_hist 同步已移到后台数据收集线程 (trend10 赋值后立即执行)
            # 这里不再重复做, 避免 UI 更新时再跑一遍

            # ✅ 保存大盘 snapshot 到本地 (启动时秒出旧数据)
            try:
                self._save_dapan_snapshot(data)
            except Exception as _e_ss:
                pass  # snapshot 保存失败不影响 UI

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[大盘分析] ❌ UI更新异常: {e}", flush=True)


    def _dapan_snapshot_path(self):
        return os.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_dapan_snapshot.json")


    def _save_dapan_snapshot(self, data):
        """保存大盘数据 snapshot 到本地 JSON (供启动时秒出旧数据)"""
        import json as _js
        path = self._dapan_snapshot_path()
        # 清理不能序列化的字段 (带 _ 前缀的临时字段)
        clean = {}
        for k, v in data.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            clean[k] = v
        clean["_saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "w") as f:
            _js.dump(clean, f, ensure_ascii=False, indent=2, default=str)


    def _try_load_dapan_snapshot(self):
        """启动时尝试读大盘 snapshot 秒出旧数据, 失败则放弃"""
        import json as _js
        import os as _os
        path = self._dapan_snapshot_path()
        if not _os.path.exists(path):
            print("[大盘] 📂 无 snapshot, 显示占位符", flush=True)
            # 没有 snapshot 时, 至少从 emo_history 渲染 10 日趋势
            self._render_trend_from_emo_history()
            return False
        try:
            with open(path) as f:
                data = _js.load(f)
            saved_at = data.get("_saved_at", "?")
            print(f"[大盘] 📂 读 snapshot 成功 (保存于 {saved_at}), 秒出", flush=True)
            # snapshot 里 emo/hld 可能为空 (旧版本没写入), 从 trend10 推导
            if data and not data.get("emo") and data.get("trend10"):
                _lt = data["trend10"][-1]
                _e2 = float(_lt.get("emo", 50))
                _sc = max(0, min(100, int(_e2)))
                _st2 = "高潮" if _e2 >= 70 else ("发酵" if _e2 >= 55 else ("启动" if _e2 >= 45 else ("震荡" if _e2 >= 35 else ("分歧" if _e2 >= 25 else "退潮"))))
                data["emo"] = {"stage": _st2, "up": 0, "dn": 0, "zt": 0, "dt": 0, "score": _sc}
                data["hld"] = {"avg": _sc, "lvl": "green" if _sc >= 60 else ("yellow" if _sc >= 35 else "red"),
                               "breadth_score": _sc, "north_score": 50}
                data["dims"] = {"breadth": ("gray", "-"), "north": ("gray", "-"),
                                "moneyflow": ("gray", "-"), "turnover": ("gray", "-")}
                print(f"[大盘] snapshot emo 已从 trend10 推导: stage={_st2}, emo={_sc}", flush=True)
            self._dapan_update_ui(data)
            return True
        except Exception as e:
            print(f"[大盘] snapshot 读取失败: {e}, 尝试 emo_history", flush=True)
            self._render_trend_from_emo_history()
            return False


    def _redraw_trend_if_width_ok(self):
        """Canvas <Configure> 事件触发: 宽度够了就用缓存的完整数据重绘所有控件"""
        # --- Re-entry guard: 避免 Configure → 重绘 → 再触发 Configure 的无限循环 ---
        if getattr(self, '_dapan_redrawing', False):
            return
        tc = getattr(self, '_dapan_trend_canvas', None)
        data = getattr(self, '_dapan_full_data', None)
        if not tc or not data:
            return
        cw = tc.winfo_width()
        if cw < 100:
            return
        # --- 宽度防抖: 宽度没变不重绘 (pack/grid 会连续触发多次 Configure) ---
        if getattr(self, '_dapan_last_width', None) == cw:
            return
        self._dapan_last_width = cw
        self._dapan_redrawing = True
        try:
            self._dapan_update_ui(data)
        except Exception:
            pass
        finally:
            self._dapan_redrawing = False


    def _render_trend_from_emo_history(self):
        """从 emo_history.json 渲染全部天数趋势图"""
        import json as _js, os as _os
        path = os.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_emo_history.json")
        if not _os.path.exists(path):
            return
        try:
            with open(path) as f:
                hist = _js.load(f)
            if not isinstance(hist, dict) or not hist:
                return
            # 取全部天数 (按日期排序)
            sorted_dates = sorted(hist.keys())
            trend10 = []
            for d in sorted_dates:
                v = hist[d]
                trend10.append({
                    "full_date": d,
                    "date": d[5:10],
                    "pct": float(v.get("pct", 0) or 0),
                    "emo": float(v.get("emo_score", 50) or 50),
                    "zt": int(v.get("zt", 0) or 0),
                    "close": v.get("close", 0),
                })
            if trend10:
                last = trend10[-1]
                _es = float(last.get("emo", 50))
                # 优先从 JSON 里直接读 stage (人工校准过更准), 没有再从 emo_score 推导
                _raw = hist.get(last["full_date"], {})
                _stage_from_json = _raw.get("stage", "")
                if _stage_from_json and _stage_from_json not in ("-", ""):
                    _stage = _stage_from_json
                else:
                    _stage = "高潮" if _es >= 70 else ("发酵" if _es >= 55 else ("启动" if _es >= 45 else ("震荡" if _es >= 35 else ("分歧" if _es >= 25 else "退潮"))))
                _score = max(0, min(100, int(_es)))
                data = {
                    "trend10": trend10,
                    "emo": {"stage": _stage, "up": 0, "dn": 0, "zt": 0, "dt": 0, "score": _score},
                    "hld": {"avg": _score, "lvl": "green" if _score >= 60 else ("yellow" if _score >= 35 else "red"),
                            "breadth_score": _score, "north_score": 50},
                    "dims": {"breadth": ("gray", "-"), "north": ("gray", "-"),
                             "moneyflow": ("gray", "-"), "turnover": ("gray", "-")},
                    "sectors": {"hot": [], "cold": []}
                }
                self._dapan_update_ui(data)
                print(f"[大盘] 📂 从 emo_history 渲染全部 {len(trend10)} 天趋势 (stage={_stage}, emo={_score})", flush=True)
        except Exception as e:
            print(f"[大盘] emo_history 渲染失败: {e}", flush=True)


    def _run_lifecycle_scan(self, monitor_pool=None, progress_cb=None):
        """🧬 生命周期扫描: 对自持股监测股找筹码成本转折点 + 三分类打标 + 目标价
        monitor_pool: 可选外部候选池 [(name, code, gi), ...]，None 时用 _get_self_holding_monitor_stocks
        progress_cb: 可选回调 cb(idx, total, current_name, stage) 用于进度条
        Returns:
            dict: {"trade_date": str, "stocks": list[dict], "total_found": int, "error": str|None}
        """
        import datetime as _dt_mod
        import os as _os_env

        import tushare as _ts_mod

        def _cb(idx, total, name, stage):
            if progress_cb:
                try: progress_cb(idx, total, name, stage)
                except Exception: pass

        _token = (_os_env.environ.get("TUSHARE_TOKEN", "") or getattr(self, "ts_token", "") or TS_DEFAULT_TOKEN or "").strip()
        if not _token:
            return {"trade_date": "", "stocks": [], "total_found": 0, "error": "TUSHARE_TOKEN 未配置"}
        _ts_mod.set_token(_token)
        pro = _ts_mod.pro_api()

        # --- 1. 找最近交易日 ---
        today = _dt_mod.date.today()
        cal = pro.trade_cal(
            exchange="SSE",
            start_date=(today - _dt_mod.timedelta(days=10)).strftime("%Y%m%d"),
            end_date=today.strftime("%Y%m%d"),
            is_open="1"
        )
        trade_date = str(cal["cal_date"].iloc[0]) if cal is not None and len(cal) > 0 else today.strftime("%Y%m%d")

        # --- 2. 候选池: 外部传入 or 自持股监测股 ---
        if monitor_pool is None:
            monitor_stocks = self._get_self_holding_monitor_stocks()
        else:
            monitor_stocks = monitor_pool
        if not monitor_stocks:
            return {"trade_date": trade_date, "stocks": [], "total_found": 0, "error": "自持股监测池为空"}

        _cb(0, len(monitor_stocks), "-", "初始化数据...")

        # --- 3. 批量拉 stock_basic 排除 ST/退市/上市<1年 ---
        df_sb = pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,industry,list_date")
        today_dt = pd.Timestamp(today.strftime("%Y%m%d"))
        valid_sb = df_sb[
            (~df_sb["name"].fillna("").str.contains("ST|退", regex=True, na=False)) &
            (pd.to_datetime(df_sb["list_date"], errors="coerce") <= today_dt - pd.Timedelta(days=365))
        ].copy() if df_sb is not None else pd.DataFrame()

        # --- 3b. 【提速关键】一次性拉全市场 daily_basic 批量, 避免逐股 sleep ---
        time.sleep(0.3)
        _cb(0, len(monitor_stocks), "-", "批量拉取 daily_basic...")
        _db_all = None
        _db_map = {}
        try:
            _db_all = pro.daily_basic(trade_date=trade_date,
                fields="ts_code,turnover_rate,circ_mv,total_mv,pct_chg,close")
            if _db_all is not None and len(_db_all) > 0:
                _db_map = {row["ts_code"]: row for _, row in _db_all.iterrows()}
                print(f"[生命周期] ✅ 批量 daily_basic {len(_db_map)} 只")
        except Exception as _e_db:
            print(f"[生命周期] ⚠️ daily_basic 批量失败 {_e_db}, 降级逐股")

        # --- 4. 提前过滤掉 ST/上市不足 的 code, 节省循环内 dict 查找 ---
        _valid_tsc_set = set(valid_sb["ts_code"].tolist()) if len(valid_sb) > 0 else set()

        # --- 5. 逐股计算 ---
        results = []
        skip_count = {"ST/上市不足": 0, "K线不足": 0, "不满足过滤": 0}
        _total = len(monitor_stocks)

        for _idx, (s_name, s_code, _pos) in enumerate(monitor_stocks):
            try:
                # 【进度条】回调当前股票
                _cb(_idx + 1, _total, s_name, "检查 ST/上市时间")
                code6 = re.search(r"(\d{6})", s_code or "").group(1) if re.search(r"(\d{6})", s_code or "") else (s_code or "").strip()[:6]
                if not code6 or len(code6) != 6:
                    continue
                # 拼 ts_code
                if code6.startswith(("6", "9", "5")):
                    tsc = f"{code6}.SH"
                elif code6.startswith(("4", "8", "92")):
                    tsc = f"{code6}.BJ"
                else:
                    tsc = f"{code6}.SZ"

                # 查 ST / 上市不足 (用预拉的 set 快速查, 比 DataFrame filter 快 10x)
                if tsc not in _valid_tsc_set:
                    skip_count["ST/上市不足"] += 1
                    continue

                # 【提速】节流: 0.25s/只 (只在 daily 调用前 sleep)
                time.sleep(0.25)

                # 拉 2 年日K
                _cb(_idx + 1, _total, s_name, "拉取2年K线 + 算筹码成本")
                start = (today - _dt_mod.timedelta(days=730)).strftime("%Y%m%d")
                hist = pro.daily(ts_code=tsc, start_date=start, end_date=trade_date)
                if hist is None or len(hist) < 120:  # 至少半年数据
                    skip_count["K线不足"] += 1
                    continue
                hist = hist.sort_values("trade_date").reset_index(drop=True)
                cl = hist["close"].values.astype(float)
                vo = hist["vol"].values.astype(float)
                lo = hist["low"].values.astype(float)
                hist["high"].values.astype(float)
                dates = hist["trade_date"].values

                # 【提速关键】从预拉的 _db_map 直接查 daily_basic, 省掉 0.2s sleep + 逐股调用
                _db = None
                if tsc in _db_map:
                    # 批量拉成功 → 直接用 Series 转 DataFrame
                    _db_row = _db_map[tsc]
                    _db = pd.DataFrame([_db_row.to_dict()])
                else:
                    # 批量拉失败 → 降级逐股 (很少触发)
                    try:
                        time.sleep(0.2)
                        _db = pro.daily_basic(ts_code=tsc, trade_date=trade_date,
                            fields="ts_code,turnover_rate,circ_mv,total_mv,pct_chg,close")
                    except Exception:
                        _db = None

                # 计算 MA (去掉循环内冗余的 _ma 废弃函数)
                def _ma_correct(arr, w):
                    if len(arr) < w: return np.full(len(arr), np.nan)
                    out = np.full(len(arr), np.nan)
                    for i in range(w-1, len(arr)): out[i] = np.mean(arr[i-w+1:i+1])
                    return out
                ma20 = _ma_correct(cl, 20)
                ma60 = _ma_correct(cl, 60)

                # --- 阶段低点 L: 近 120 日最低 ---
                lookback_L = min(120, len(cl))
                L_val = float(np.min(lo[-lookback_L:]))
                int(np.argmin(lo[-lookback_L:])) + (len(lo) - lookback_L)

                # --- 筹码成本曲线 (换手衰减加权模型) ---
                # cost[t] = sum_{i<=t} close[i] * turn[i] * d^{t-i} / sum_{i<=t} turn[i] * d^{t-i}
                d = 0.87  # 日衰减系数
                N = len(cl)
                # 需要换手率, 如果 daily_basic 有就用, 否则用 vol 折算
                if _db is not None and len(_db) > 0 and "turnover_rate" in _db.columns:
                    float(_db["turnover_rate"].iloc[0]) if pd.notna(_db["turnover_rate"].iloc[0]) else 0.0
                    # 只有单日换手率, 不够做衰减模型 — 只能用成交量作权重
                # 用成交量 vol 作为权重代理 (无量纲)
                vol_norm = vo / (np.max(vo) + 1e-9)  # 归一化到 0~1

                # 用 numpy 向量化 cost 曲线
                cost_arr = np.full(N, np.nan)
                # 为避免 Python 循环太慢, 只在最后 180 天范围内精确算
                calc_start = max(20, N - 180)
                for t in range(calc_start, N):
                    # 权重: w[i] = vol[i] * d^(t-i), 对 i in [max(0,t-179), t]
                    i_lo = max(0, t - 179)
                    idx = np.arange(i_lo, t + 1)
                    decay = d ** (t - idx)  # [d^(t-i_lo), ..., d^0]
                    w = vol_norm[idx] * decay
                    c_weights = cl[idx] * w
                    cost_arr[t] = np.sum(c_weights) / (np.sum(w) + 1e-9)

                # --- 筹码转折点 T*: cost 曲线由降转升的最近拐点 ---
                # 计算 cost 斜率 (差分)
                cost_valid = cost_arr[calc_start:]  # 只看有值的部分
                slope = np.diff(cost_valid)
                # 斜率由负转正的位置 (排除前 5 个)
                pivot_indices = []
                min_idx = 5
                for k in range(min_idx, len(slope)):
                    # 连续 2 日斜率 >= 0, 且之前斜率 < 0
                    if slope[k] >= 0 and slope[k-1] >= 0:
                        # 找到前面最后一次 < 0
                        prev_neg = False
                        for j in range(max(0, k-10), k):
                            if slope[j] < 0:
                                prev_neg = True
                                break
                        if prev_neg:
                            pivot_indices.append(calc_start + k + 1)  # k 是 diff 下标, +1 对应 cost_arr 位置
                if not pivot_indices:
                    skip_count["不满足过滤"] += 1
                    continue
                t_star = pivot_indices[-1]  # 取最近一个
                P0 = float(cl[t_star])
                T_star_date = str(dates[t_star])

                # --- 过滤条件 ---
                # 1. 站上 MA20 >= 3 日
                last3 = cl[-3:]
                ma20_last3 = ma20[-3:]
                above_ma20 = all(last3 > ma20_last3) if not np.any(np.isnan(ma20_last3)) else False
                if not above_ma20:
                    skip_count["不满足过滤"] += 1
                    continue

                # 2. MA20 近 10 日斜率 ∈ [-3%, +10%] (放宽给游资/主力票的急拉形态)
                ma20_10 = ma20[-10:]
                if np.any(np.isnan(ma20_10)):
                    skip_count["不满足过滤"] += 1
                    continue
                ma20_slope_pct = (ma20_10[-1] - ma20_10[0]) / (ma20_10[0] + 1e-9) * 100
                ma20_flat = -3.0 <= ma20_slope_pct <= 10.0

                # 3. 距阶段低点 L 涨幅 < 50%
                L_gain_pct = (cl[-1] - L_val) / L_val * 100 if L_val > 0 else 0
                not_overheat = L_gain_pct < 50.0

                # 4. T* 距今 <= 60 交易日
                t_star_recency = (N - 1) - t_star <= 60

                # 5. 距 P0 涨幅不过高 (已涨 > 50% 不推荐追)
                p0_gain_pct = (cl[-1] - P0) / P0 * 100 if P0 > 0 else 0
                not_chase = p0_gain_pct < 50.0

                # 6. 日均成交额 > 3000万 (用 vol * close 代理)
                daily_turnover = float(np.mean(vo[-60:]) * cl[-1]) if len(cl) > 60 else 0
                liquid = daily_turnover > 3e7

                # 汇总过滤
                if not (ma20_flat and not_overheat and t_star_recency and not_chase and liquid):
                    skip_count["不满足过滤"] += 1
                    continue

                # --- 形态特征 (用于打标) ---
                circ_mv = 0.0
                if _db is not None and len(_db) > 0:
                    if "circ_mv" in _db.columns and pd.notna(_db["circ_mv"].iloc[0]):
                        circ_mv = float(_db["circ_mv"].iloc[0])  # 万元
                    if "total_mv" in _db.columns and pd.notna(_db["total_mv"].iloc[0]):
                        float(_db["total_mv"].iloc[0])

                # 近期换手中枢 (用 vol 代理, 归一化后看波动)
                vol_recent = vo[-60:]
                vol_volatility = float(np.std(vol_recent) / (np.mean(vol_recent) + 1e-9))
                vol_expansion = float(np.mean(vo[-5:]) / (np.mean(vo[-20:-5]) + 1e-9))

                # K 线节奏: 计算过去 60 日涨跌分布
                pct_changes = np.diff(cl[-60:]) / cl[-60:-1] * 100
                up_days = int(np.sum(pct_changes > 0))
                down_days = int(np.sum(pct_changes < 0))
                zt_days = int(np.sum(pct_changes >= 9.0))

                # 距 MA60 位置 (判断大趋势)
                if not np.isnan(ma60[-1]):
                    ma60_dist = (cl[-1] - ma60[-1]) / ma60[-1] * 100
                else:
                    ma60_dist = 0.0

                # --- 三分类打标 (启发式) ---
                score_inst = 0   # 机构票
                score_main = 0   # 主力票
                score_hot = 0    # 游资票

                # 市值维度 (circ_mv 万元)
                if circ_mv > 100e4:    # > 100 亿
                    score_inst += 35
                elif circ_mv > 50e4:  # 50~100 亿
                    score_inst += 15
                    score_main += 15
                elif circ_mv > 20e4:  # 20~50 亿
                    score_main += 30
                elif circ_mv > 10e4:  # 10~20 亿
                    score_main += 15
                    score_hot += 20
                else:                 # < 10 亿
                    score_hot += 35

                # K 线节奏 (慢涨 vs 急拉)
                if zt_days == 0 and vol_volatility < 0.8:  # 少涨停 + 量能稳定
                    score_inst += 25
                elif zt_days <= 2 and 0.5 < vol_volatility < 1.5:
                    score_main += 25
                elif zt_days >= 3 or vol_volatility > 1.2:  # 多涨停 or 量能剧烈
                    score_hot += 25

                # 均线位置 (距 MA60)
                if ma60_dist > 5:  # 已突破 MA60 并站稳
                    score_inst += 15
                elif ma60_dist > 0:
                    score_main += 10
                elif ma60_dist < -5:
                    score_hot += 10  # 还在 MA60 下方挣扎

                # 量能特征
                if 0.7 < vol_expansion < 1.3:  # 温和放量
                    score_inst += 10
                elif 1.3 <= vol_expansion < 2.0:
                    score_main += 10
                elif vol_expansion >= 2.0:
                    score_hot += 10

                # 涨跌分布
                if up_days > down_days + 10:  # 上涨天数显著多
                    score_inst += 10
                elif up_days > down_days:
                    score_main += 8
                # down_days 显著多则不加分

                scores_tag = [("机构票", score_inst), ("主力票", score_main), ("游资票", score_hot)]
                scores_tag.sort(key=lambda x: x[1], reverse=True)
                best_label, best_score = scores_tag[0]
                second_score = scores_tag[1][1]
                is_hybrid = (best_score - second_score) < 10

                if is_hybrid:
                    final_label = f"合力票·{best_label}"
                    mult_low, mult_high = 2.0, 3.0  # 合力票保守档
                elif best_label == "机构票":
                    mult_low, mult_high = 4.0, 6.0
                elif best_label == "主力票":
                    mult_low, mult_high = 2.0, 3.0
                else:
                    mult_low, mult_high = 1.5, 2.0

                # 置信度
                if best_score >= 50:
                    conf = "高"
                elif best_score >= 35:
                    conf = "中"
                else:
                    conf = "低"

                # 风险评级
                risk_stars = 1
                if p0_gain_pct > 30: risk_stars = 2
                if p0_gain_pct > 40: risk_stars = 3
                if circ_mv < 20e4: risk_stars += 1
                if best_label == "游资票": risk_stars += 1
                risk_stars = min(5, risk_stars)

                # --- 组装结果 ---
                results.append({
                    "code": code6,
                    "name": s_name or sb_row["name"].iloc[0] if len(sb_row) > 0 else "",
                    "price": float(cl[-1]),
                    "trade_date": trade_date,
                    # 生命周期核心数据
                    "L_val": L_val,
                    "L_gain_pct": round(L_gain_pct, 1),
                    "T_star_date": T_star_date,
                    "T_star_offset": int((N - 1) - t_star),  # 距今天数
                    "P0": round(P0, 3),
                    "p0_gain_pct": round(p0_gain_pct, 1),
                    # MA 状态
                    "ma20_slope_pct": round(ma20_slope_pct, 2),
                    "ma20_state": "上翘" if ma20_slope_pct > 1.0 else ("走平" if ma20_slope_pct >= -1.0 else "下行"),
                    "ma60_dist": round(ma60_dist, 1),
                    # 打标
                    "label": final_label,
                    "label_conf": conf,
                    "label_score": {"机构票": score_inst, "主力票": score_main, "游资票": score_hot},
                    # 目标价
                    "mult_low": mult_low,
                    "mult_high": mult_high,
                    "target_low": round(P0 * mult_low, 2),
                    "target_high": round(P0 * mult_high, 2),
                    # 风险
                    "risk_stars": risk_stars,
                    "circ_mv_yi": round(circ_mv / 10000, 1),  # 亿
                    # 形态特征
                    "zt_days_60": zt_days,
                    "vol_expansion": round(vol_expansion, 2),
                })
                print(f"[生命周期] ✅ {s_name}({code6}) T*={T_star_date} P0={P0:.2f} {final_label} {conf} 目标={mult_low}~{mult_high}x")

            except Exception as _e:
                print(f"[生命周期] ❌ {s_name}({s_code}) 计算失败: {_e}")
                skip_count["K线不足"] += 1
                continue

        print(f"[生命周期] 完成! 通过={len(results)}, 跳过={skip_count}")
        return {
            "trade_date": trade_date,
            "stocks": results,
            "total_found": len(results),
            "skip_count": skip_count,
            "error": None,
        }


    def _get_emo_sync_config():
        """读 GitHub Gist 同步配置"""
        import json as _jc, os as _jo
        _cf = _jo.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_sync_config.json")
        if _jo.path.exists(_cf):
            try: return _jc.load(open(_cf))
            except: return {}
        return {}


    def _set_emo_sync_config(self, cfg):
        import json as _jc, os as _jo
        _cf = _jo.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_sync_config.json")
        _jo.makedirs(_jo.path.dirname(_cf), exist_ok=True)
        _jc.dump(cfg, open(_cf, "w"), ensure_ascii=False, indent=2)


    def _emo_gist_push(self, hist_dict):
        """把 emo_hist 推送到 GitHub Gist"""
        import json as _ji_cfg, os as _jo_cfg
        _cf_cfg = _jo_cfg.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_sync_config.json")
        _cfg = {}
        if _jo_cfg.path.exists(_cf_cfg):
            try: _cfg = _ji_cfg.load(open(_cf_cfg))
            except: _cfg = {}
        cfg = _cfg
        token = cfg.get("gist_token", "")
        gist_id = cfg.get("gist_id", "")
        if not token or not gist_id:
            return {"ok": False, "msg": "未配置 Token+GistID"}
        try:
            import requests as _rq, json as _jc
            url = f"https://api.github.com/gists/{gist_id}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
            content = _jc.dumps(hist_dict, ensure_ascii=False, indent=2)
            # GET 当前 gist，拿到 etag 做更新
            r = _rq.get(url, headers=headers, timeout=8)
            if r.status_code == 200:
                old_files = r.json().get("files", {})
                payload = {"files": {}}
                for fname in old_files:
                    payload["files"][fname] = {"content": content}
                # 用 emo_hist.json 作为 filename
                fn = "emo_hist.json"
                payload = {"files": {fn: {"content": content}}}
                resp = _rq.patch(url, headers=headers, json=payload, timeout=8)
                if resp.status_code in (200, 204):
                    return {"ok": True, "msg": f"✅ Gist已同步 ({len(hist_dict)}天)"}
                else:
                    return {"ok": False, "msg": f"push fail HTTP {resp.status_code}: {resp.text[:100]}"}
            elif r.status_code == 404:
                # 创建新 gist
                payload = {"description": "stockyidong emo cycle history", "public": False,
                           "files": {"emo_hist.json": {"content": content}}}
                resp = _rq.post("https://api.github.com/gists", headers=headers, json=payload, timeout=8)
                if resp.status_code == 201:
                    new_id = resp.json().get("id","")
                    cfg["gist_id"] = new_id
                    import json as _ji_save, os as _jo_save
                    _cf_save = _jo_save.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_sync_config.json")
                    _jo_save.makedirs(_jo_save.path.dirname(_cf_save), exist_ok=True)
                    _ji_save.dump(cfg, open(_cf_save, "w"), ensure_ascii=False, indent=2)
                    return {"ok": True, "msg": f"✅ 新建Gist {new_id[:8]}..."}
                else:
                    return {"ok": False, "msg": f"create fail HTTP {resp.status_code}"}
            else:
                return {"ok": False, "msg": f"get gist fail HTTP {r.status_code}"}
        except Exception as e:
            return {"ok": False, "msg": f"push error: {e}"}


    def _emo_gist_pull(self, timeout=2):
        """从 GitHub Gist 拉取 emo_hist, 返回 dict (失败返回 None)"""
        import json as _ji_cfg, os as _jo_cfg
        _cf_cfg = _jo_cfg.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_sync_config.json")
        _cfg = {}
        if _jo_cfg.path.exists(_cf_cfg):
            try: _cfg = _ji_cfg.load(open(_cf_cfg))
            except: _cfg = {}
        cfg = _cfg
        token = cfg.get("gist_token", "")
        gist_id = cfg.get("gist_id", "")
        if not token or not gist_id: return None
        try:
            import requests as _rq
            url = f"https://api.github.com/gists/{gist_id}"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
            r = _rq.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                files = r.json().get("files", {})
                for fname, finfo in files.items():
                    if "emo" in fname.lower() or "hist" in fname.lower() or fname.endswith(".json"):
                        import json as _jc
                        content = finfo.get("content", "")
                        if content:
                            data = _jc.loads(content)
                            if isinstance(data, dict): return data
                            if isinstance(data, list):
                                nh = {}
                                for h in data: nh[h.get("date","")] = h
                                return nh
            return None
        except: return None


    def _merge_emo_hist(self, local, remote):
        """本地和远端合并, 取每个 date 下 emo_score 更大的 (认为更新鲜)"""
        merged = dict(local or {})
        remote = remote or {}
        for k, rv in remote.items():
            lv = merged.get(k, {})
            # 如果远端有 pnl/ths (更新的手填) 或者本地没有这个 key, 就用远端
            if not lv or (rv.get("pnl") and not lv.get("pnl")):
                merged[k] = rv
            elif rv.get("emo_score", 0) > lv.get("emo_score", 0):
                # emo_score 更高说明大盘刚同步了
                lv = dict(lv); lv.update({kk: vv for kk, vv in rv.items() if vv is not None})
                merged[k] = lv
            else:
                # 保留本地, 补充远端没有的字段
                for kk, vv in rv.items():
                    if vv is not None and not lv.get(kk):
                        lv[kk] = vv
                merged[k] = lv
        return merged


    def _build_emo_cycle_calendar(self, parent_frame, notebook=None):
        """🎭 在容器 frame 里直接渲染情绪周期三维度日历 (不弹窗, 嵌入 Notebook tab)。"""
        import json as _j, os as _os, datetime as _dt
        from datetime import datetime as _dt2, timedelta as _td

        EMO_HIST = _os.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_emo_history.json")

        # ---- 加载历史 ----
        hist_dict = {}
        if _os.path.exists(EMO_HIST):
            try:
                with open(EMO_HIST) as f:
                    raw = _j.load(f)
                if isinstance(raw, dict):
                    hist_dict = raw
                elif isinstance(raw, list):
                    for h in raw: hist_dict[h.get("date", "")] = h
            except: hist_dict = {}

        def _reload_hist():
            """从磁盘重新加载 + 后台异步 Gist pull (不阻塞 UI)"""
            nonlocal hist_dict
            if _os.path.exists(EMO_HIST):
                try:
                    with open(EMO_HIST) as f:
                        raw = _j.load(f)
                    if isinstance(raw, dict): hist_dict = raw
                    elif isinstance(raw, list):
                        nh = {}
                        for h in raw: nh[h.get("date","")] = h
                        hist_dict = nh
                except: pass
            # 后台异步 pull Gist, 不阻塞渲染
            import threading as _th_pull2
            def _bg_pull_sync():
                _remote = self._emo_gist_pull(timeout=2)
                if _remote:
                    hist_dict = self._merge_emo_hist(hist_dict, _remote)
                    print(f"[情绪周期] 📥 Gist pull {len(_remote)}天 → merge {len(hist_dict)}天", flush=True)
                    try: self.root.after(0, _render_month)
                    except: pass
            try: _th_pull2.Thread(target=_bg_pull_sync, daemon=True).start()
            except: pass

        def _save_hist_dict():
            with open(EMO_HIST, "w") as f:
                _j.dump(hist_dict, f, ensure_ascii=False, indent=2)
            # 自动 push 到 Gist
            import threading as _th
            def _bg_push():
                r = self._emo_gist_push(hist_dict)
                if r.get("ok"):
                    print(f"[情绪周期] {r['msg']}")
                else:
                    print(f"[情绪周期] sync skip: {r.get('msg','')}")
            try:
                _th.Thread(target=_bg_push, daemon=True).start()
            except: pass

        def _calc_consec_loss():
            cl = 0
            for h in reversed(sorted(hist_dict.values(), key=lambda x: x.get("date",""))):
                if h.get("pnl") == "亏钱": cl += 1
                else: break
            return cl

        # ---- 状态变量 ----
        # 默认月份
        dates_with_data = [_dt2.strptime(d, "%Y-%m-%d") for d in hist_dict.keys()
                           if isinstance(d, str) and len(d) == 10]
        # 默认定位到当前月 (而不是有数据的最早月)
        default_month = _dt2.now().replace(day=1)
        view_month = [default_month]
        is_rebuilding = [False]

        def _shift_month(delta):
            ym = view_month[0]
            new_m = ym.month + delta
            new_y = ym.year
            while new_m < 1: new_m += 12; new_y -= 1
            while new_m > 12: new_m -= 12; new_y += 1
            view_month[0] = _dt2(new_y, new_m, 1)
            _render_month()

        # grid_outer (延迟 pack, 等工具栏创建完再 pack)
        grid_outer = tk.Frame(parent_frame, bg="#1A1A2E")

        # ---- 紧凑工具栏 (统计+导航+图例 三合一, 最大化日历空间) ----
        cl = _calc_consec_loss()
        _up = sum(1 for v in hist_dict.values() if v.get("pnl") == "赚钱")
        _dn = sum(1 for v in hist_dict.values() if v.get("pnl") == "亏钱")
        _bad_stage = sum(1 for v in hist_dict.values() if v.get("stage") in ("冰点", "退潮"))
        stat_lbl_text = (f"📅{len(hist_dict)}天 💰{_up}📉{_dn} ⚠️{_bad_stage} 🔥{cl}天")

        toolbar_f = tk.Frame(parent_frame, bg="#1A1A2E")
        toolbar_f.pack(fill=tk.X, padx=4, pady=(2, 1))
        # 左: 导航按钮
        tk.Button(toolbar_f, text="◀", command=lambda: _shift_month(-1),
                  bg="#37474F", fg="white", font=("", 9, "bold"), padx=6, pady=1).pack(side=tk.LEFT, padx=(0,2))
        month_lbl = tk.Label(toolbar_f, text="", bg="#1A1A2E", fg="#FFD54F", font=("", 10, "bold"))
        month_lbl.pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar_f, text="▶", command=lambda: _shift_month(1),
                  bg="#37474F", fg="white", font=("", 9, "bold"), padx=6, pady=1).pack(side=tk.LEFT, padx=(2,4))
        # 中: 统计
        stat_lbl = tk.Label(toolbar_f, text=stat_lbl_text, bg="#1A1A2E", fg="#FFD54F", font=("", 9, "bold"))
        stat_lbl.pack(side=tk.LEFT, padx=4)
        # 图例 (紧凑色条)
        tk.Label(toolbar_f, text="", bg="#B71C1C", width=2, height=1).pack(side=tk.LEFT, padx=(6,0))
        tk.Label(toolbar_f, text="", bg="#1B5E20", width=2, height=1).pack(side=tk.LEFT, padx=1)
        tk.Label(toolbar_f, text="", bg="#E65100", width=2, height=1).pack(side=tk.LEFT, padx=1)
        # 右: 功能按钮
        tk.Button(toolbar_f, text="🔄", command=lambda: (_reload_hist(), _render_month()),
                  bg="#2E7D32", fg="white", font=("", 8, "bold"), padx=5, pady=1).pack(side=tk.RIGHT, padx=(2,0))
        tk.Button(toolbar_f, text="今天", command=lambda: (_reload_hist(), view_month.__setitem__(0,_dt2.now().replace(day=1)), _render_month()),
                  bg="#0D47A1", fg="white", font=("", 8, "bold"), padx=5, pady=1).pack(side=tk.RIGHT, padx=(2,0))
        tk.Button(toolbar_f, text="☁️", command=lambda: _open_sync_dialog(),
                  bg="#6A1B9A", fg="white", font=("", 8, "bold"), padx=5, pady=1).pack(side=tk.RIGHT, padx=(2,0))

        def _open_sync_dialog():
            """配置 GitHub Gist 同步的弹窗"""
            dlg = tk.Toplevel(self.root); dlg.title("☁️ 跨设备同步 (GitHub Gist)")
            dlg.geometry("480x400"); dlg.configure(bg="#263238"); dlg.transient(self.root)
            cfg = self._get_emo_sync_config()

            tk.Label(dlg, text="☁️ 跨设备同步情绪周期三维度数据", bg="#263238", fg="#FFD54F",
                     font=("", 13, "bold")).pack(pady=(14, 2))
            tk.Label(dlg, text="配置 GitHub Gist 后, 任何电脑保存自动 push, 打开自动 pull+合并",
                     bg="#263238", fg="#90A4AE", font=("", 9), wraplength=440).pack(pady=(0, 8))

            # 步骤说明
            tip_f = tk.Frame(dlg, bg="#37474F"); tip_f.pack(fill=tk.X, padx=16, pady=(0,6))
            tk.Label(tip_f,
                     text="① github.com/settings/tokens → Generate new token\n② Note随便写, Expiration选 No expiration\n③ 勾选 gist (只需这一项!)\n④ 复制 token 粘贴到下方 Token 框\n⑤ 填 GistID (首次创建后自动填入)",
                     bg="#37474F", fg="#B0BEC5", font=("", 8), justify="left", anchor="w").pack(padx=8, pady=6)

            f1 = tk.LabelFrame(dlg, text="GitHub Token", bg="#263238", fg="#81D4FA", font=("", 10, "bold"), padx=8, pady=6)
            f1.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(f1, text="ghp_xxxxxxxxxxxxxxxxxxxx", bg="#263238", fg="#B0BEC5", font=("", 8)).pack(anchor="w")
            token_var = tk.StringVar(value=cfg.get("gist_token", ""))
            tk.Entry(f1, textvariable=token_var, width=50, bg="#1A237E", fg="white",
                     insertbackground="white", show="*").pack(fill=tk.X, pady=3)

            f2 = tk.LabelFrame(dlg, text="Gist ID (留空→点击💾保存后自动创建)",
                               bg="#263238", fg="#FFAB91", font=("", 10, "bold"), padx=8, pady=6)
            f2.pack(fill=tk.X, padx=12, pady=4)
            tk.Label(f2, text="形如 abc123def456 (gist URL 里的那串)", bg="#263238",
                     fg="#B0BEC5", font=("", 8)).pack(anchor="w")
            gist_var = tk.StringVar(value=cfg.get("gist_id", ""))
            tk.Entry(f2, textvariable=gist_var, width=50, bg="#1A237E", fg="white",
                     insertbackground="white").pack(fill=tk.X, pady=3)

            status_lbl = tk.Label(dlg, text="", bg="#263238", fg="#FFD54F", font=("", 9))
            status_lbl.pack(pady=4)

            def _test_push():
                status_lbl.config(text="⏳ 测试推送中...", fg="#FFD54F")
                def _do():
                    _tmp_cfg = {"gist_token": token_var.get().strip(), "gist_id": gist_var.get().strip()}
                    if not _tmp_cfg["gist_token"]:
                        self.root.after(0, lambda: status_lbl.config(text="❌ Token为空", fg="#C62828"))
                        return
                    self._set_emo_sync_config(_tmp_cfg)
                    r = self._emo_gist_push(hist_dict)
                    if r.get("ok") and not gist_var.get().strip():
                        gist_var.set(self._get_emo_sync_config().get("gist_id",""))
                    self.root.after(0, lambda: status_lbl.config(text=r.get("msg",""),
                                                                  fg="#1B5E20" if r.get("ok") else "#C62828"))
                import threading; threading.Thread(target=_do, daemon=True).start()

            def _test_pull():
                status_lbl.config(text="⏳ 测试拉取中...", fg="#FFD54F")
                def _do():
                    _tmp_cfg = {"gist_token": token_var.get().strip(), "gist_id": gist_var.get().strip()}
                    self._set_emo_sync_config(_tmp_cfg)
                    r = self._emo_gist_pull()
                    if r is not None:
                        self.root.after(0, lambda: status_lbl.config(text=f"✅ 拉到 {len(r)} 天数据", fg="#1B5E20"))
                    else:
                        self.root.after(0, lambda: status_lbl.config(text="❌ 拉取失败 (Token/ID错或网络)", fg="#C62828"))
                import threading; threading.Thread(target=_do, daemon=True).start()

            def _save_cfg():
                cfg_new = {"gist_token": token_var.get().strip(), "gist_id": gist_var.get().strip()}
                self._set_emo_sync_config(cfg_new)
                _test_push()
                if gist_var.get().strip(): _test_pull()
                _render_month()
                dlg.destroy()

            bf = tk.Frame(dlg, bg="#263238"); bf.pack(pady=6)
            tk.Button(bf, text="💾保存并测试", command=_save_cfg, bg="#2E7D32", fg="white",
                      font=("", 10, "bold"), width=14).pack(side=tk.LEFT, padx=5)
            tk.Button(bf, text="测试拉取", command=_test_pull, bg="#0D47A1", fg="white",
                      font=("", 9), width=10).pack(side=tk.LEFT, padx=3)
            tk.Button(bf, text="取消", command=dlg.destroy, bg="#546E7A", fg="white",
                      font=("", 9), width=8).pack(side=tk.LEFT, padx=3)

        # grid_outer 在工具栏之后 pack (expand=True 填满剩余空间)
        grid_outer.pack(fill=tk.BOTH, expand=True, padx=4, pady=(1, 2))

        # ⚠️ grid_outer 内部 pack 顺序很重要: 先星期标题, 后日期网格 (expand=True)
        # 星期标题 (固定高度, 先 pack)
        wd_f = tk.Frame(grid_outer, bg="#1A1A2E"); wd_f.pack(fill=tk.X)
        for wi, wn in enumerate(["一","二","三","四","五","六","日"]):
            tk.Label(wd_f, text=wn, bg="#1A1A2E", fg="#90A4AE", font=("", 9)).grid(row=0, column=wi, sticky="nsew")
        for ci in range(7): wd_f.grid_columnconfigure(ci, weight=1)

        # 日期网格 (Canvas+Scrollbar 保底: 空间不够时可滚动查看所有行)
        _cal_canvas = tk.Canvas(grid_outer, bg="#1A1A2E", highlightthickness=0, bd=0)
        _cal_vsb = tk.Scrollbar(grid_outer, orient="vertical", command=_cal_canvas.yview,
                                bg="#37474F", troughcolor="#1A1A2E")
        _cal_canvas.configure(yscrollcommand=_cal_vsb.set)
        _cal_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        _cal_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        grid_f = tk.Frame(_cal_canvas, bg="#1A1A2E")
        _cal_window_id = _cal_canvas.create_window((0, 0), window=grid_f, anchor="nw")
        # 让 grid_f 宽度跟随 canvas, 高度够了自动隐藏 scrollbar
        def _on_gridf_config(e):
            _cal_canvas.configure(scrollregion=_cal_canvas.bbox("all"))
        grid_f.bind("<Configure>", _on_gridf_config)
        def _on_canvas_config(e):
            _cal_canvas.itemconfig(_cal_window_id, width=e.width)
        _cal_canvas.bind("<Configure>", _on_canvas_config)
        # 鼠标滚轮绑定 (只在鼠标进入日历区域时生效, 不干扰其他滚动控件)
        def _on_mousewheel(e):
            _cal_canvas.yview_scroll(int(-e.delta / 30), "units")
        def _bind_mousewheel(e):
            _cal_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(e):
            _cal_canvas.unbind_all("<MouseWheel>")
        _cal_canvas.bind("<Enter>", _bind_mousewheel)
        _cal_canvas.bind("<Leave>", _unbind_mousewheel)
        for ci in range(7): grid_f.grid_columnconfigure(ci, weight=1)

        # 底部预览
        detail_lbl = tk.Label(parent_frame, text="点击格子补录/修改, 鼠标悬停看三维度详情",
                              bg="#1A1A2E", fg="#90A4AE", font=("", 9), pady=4)
        detail_lbl.pack(fill=tk.X, padx=6)

        # ---- 编辑器弹窗 ----
        def _open_day_editor(date_str):
            edit_win = tk.Toplevel(self.root)
            edit_win.title(f"📝 {date_str}")
            edit_win.geometry("420x400")
            edit_win.configure(bg="#263238")
            edit_win.transient(self.root)

            rec = hist_dict.get(date_str, {})
            auto_text = getattr(self, "_dapan_emo_var", None)
            auto_text = auto_text.get() if auto_text else ""

            tk.Label(edit_win, text=f"📅 {date_str} 三维度记录", bg="#263238", fg="#FFD54F",
                     font=("", 13, "bold")).pack(pady=(14, 4))

            # 系统自动同步区
            sys_parts = []
            _e = rec.get("emo_score")
            _p = rec.get("pct")
            if _e is not None: sys_parts.append(f"📊情绪={_e:.0f}")
            if _p is not None: sys_parts.append(f"📈上证={_p:+.2f}%")
            if sys_parts:
                sf = tk.Frame(edit_win, bg="#37474F"); sf.pack(fill=tk.X, padx=12, pady=(0,4))
                tk.Label(sf, text="🔒 " + " | ".join(sys_parts), bg="#37474F", fg="#81D4FA",
                         font=("", 9)).pack(fill=tk.X, padx=8, pady=4)

            # 维度1: 阶段 — 清理掉可能的 emoji 前缀
            _stage_val = rec.get("stage", auto_text)
            # 去掉 emoji/图标前缀, 只留纯文字
            import re as _re_stage
            _stage_clean = _re_stage.sub(r'[^\u4e00-\u9fa5A-Za-z0-9 ]+', '', str(_stage_val or '')).strip()
            if not _stage_clean: _stage_clean = auto_text
            f1 = tk.LabelFrame(edit_win, text="①情绪阶段", bg="#263238", fg="#81D4FA",
                               font=("", 10, "bold"), padx=10, pady=4)
            f1.pack(fill=tk.X, padx=12, pady=3)
            stage_var = tk.StringVar(value=_stage_clean)
            tk.Entry(f1, textvariable=stage_var, width=40,
                     bg="#1A237E", fg="white", insertbackground="white").pack(fill=tk.X, pady=2)

            # 维度2: 同花顺
            f2 = tk.LabelFrame(edit_win, text="②同花顺情绪指数", bg="#263238", fg="#FFAB91",
                               font=("", 10, "bold"), padx=10, pady=4)
            f2.pack(fill=tk.X, padx=12, pady=3)
            ths_d = rec.get("ths", "向上")
            ths_var = tk.StringVar(value=f"{ths_d} (yes)" if ths_d=="向上" else f"{ths_d} (no)")
            tk.Radiobutton(f2, text="📈向上", variable=ths_var, value="向上 (yes)",
                           bg="#263238", fg="#E0E0E0", selectcolor="#263238").pack(anchor="w")
            tk.Radiobutton(f2, text="📉向下", variable=ths_var, value="向下 (no)",
                           bg="#263238", fg="#E0E0E0", selectcolor="#263238").pack(anchor="w")

            # 维度3: 盈亏
            f3 = tk.LabelFrame(edit_win, text="③账户盈亏", bg="#263238", fg="#A5D6A7",
                               font=("", 10, "bold"), padx=10, pady=4)
            f3.pack(fill=tk.X, padx=12, pady=3)
            pnl_d = rec.get("pnl", "赚钱")
            pnl_var = tk.StringVar(value=f"{pnl_d} (yes)" if pnl_d=="赚钱" else f"{pnl_d} (no)")
            tk.Radiobutton(f3, text="💰赚钱", variable=pnl_var, value="赚钱 (yes)",
                           bg="#263238", fg="#E0E0E0", selectcolor="#263238").pack(anchor="w")
            tk.Radiobutton(f3, text="💸亏钱", variable=pnl_var, value="亏钱 (no)",
                           bg="#263238", fg="#E0E0E0", selectcolor="#263238").pack(anchor="w")

            def _save():
                ths_v = "向下" if "向下" in ths_var.get() else "向上"
                pnl_v = "亏钱" if "亏钱" in pnl_var.get() else "赚钱"
                _old = hist_dict.get(date_str, {})
                hist_dict[date_str] = {
                    "date": date_str, "pnl": pnl_v, "ths": ths_v,
                    "stage": stage_var.get().strip(),
                    "emo_score": _old.get("emo_score"),
                    "pct": _old.get("pct"),
                    "close": _old.get("close"), "zt": _old.get("zt"),
                }
                _save_hist_dict()
                _refresh_stats()
                _render_month()
                edit_win.destroy()

            def _delete():
                if date_str in hist_dict:
                    del hist_dict[date_str]
                    _save_hist_dict()
                    _refresh_stats()
                    _render_month()
                edit_win.destroy()

            bf = tk.Frame(edit_win, bg="#263238"); bf.pack(pady=10)
            tk.Button(bf, text="💾保存", command=_save, bg="#2E7D32", fg="white",
                      font=("", 10, "bold"), width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(bf, text="🗑️删除", command=_delete, bg="#C62828", fg="white",
                      font=("", 10, "bold"), width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(bf, text="取消", command=edit_win.destroy, bg="#546E7A", fg="white",
                      font=("", 10), width=8).pack(side=tk.LEFT, padx=5)

        def _refresh_stats():
            cl = _calc_consec_loss()
            _up = sum(1 for v in hist_dict.values() if v.get("pnl") == "赚钱")
            _dn = sum(1 for v in hist_dict.values() if v.get("pnl") == "亏钱")
            _bad = sum(1 for v in hist_dict.values() if v.get("stage") in ("冰点","退潮"))
            stat_lbl.config(text=f"📅 {len(hist_dict)}天  |  💰{_up}  📉{_dn}  |  ⚠️冰点/退潮{_bad}  |  🔥连亏{cl}天")

        # ---- 渲染日历 ----
        def _render_month():
            _reload_hist()
            is_rebuilding[0] = True
            for w in grid_f.winfo_children(): w.destroy()
            ym = view_month[0]
            month_lbl.config(text=f"{ym.year} 年 {ym.month} 月")
            first = ym.replace(day=1)
            first_wd = first.weekday()
            if ym.month == 12:
                nx = ym.replace(year=ym.year+1, month=1, day=1)
            else:
                nx = ym.replace(month=ym.month+1, day=1)
            dim = (nx - _td(days=1)).day
            today_str = _dt2.now().strftime("%Y-%m-%d")

            row = 0; col = first_wd
            for d in range(1, dim + 1):
                ds = f"{ym.year:04d}-{ym.month:02d}-{d:02d}"
                is_today = (ds == today_str)
                rec = hist_dict.get(ds)

                # 背景色 (A股)
                if rec:
                    pnl = rec.get("pnl","")
                    ths = rec.get("ths","")
                    pct_v = rec.get("pct")
                    if pnl == "赚钱": bg = "#B71C1C"
                    elif pnl == "亏钱": bg = "#1B5E20"
                    elif pct_v is not None:
                        bg = "#B71C1C" if pct_v > 0 else ("#1B5E20" if pct_v < 0 else "#455A64")
                    else: bg = "#455A64"
                    bd = "#E65100" if ths == "向下" else None
                else:
                    bg = "#37474F"; bd = None

                cell = tk.Frame(grid_f, bg=bg, width=95, height=65,
                                highlightbackground=bd or "#1A1A2E",
                                highlightthickness=3 if bd else 1, cursor="hand2")
                cell.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                cell.grid_propagate(False)

                ths_v = rec.get("ths","") if rec else ""
                ths_icon = "📈" if ths_v=="向上" else ("📉" if ths_v=="向下" else "·")
                ths_fg = "#81D4FA" if ths_v else "#78909C"
                pnl_v = rec.get("pnl","") if rec else ""
                pnl_sym = "💰" if pnl_v=="赚钱" else ("💸" if pnl_v=="亏钱" else "·")
                stage_v = rec.get("stage","") if rec else ""
                stage_v = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9 ]+', '', str(stage_v or '')).strip()
                stage_fg = "#FFD54F" if stage_v in ("冰点","退潮") else "#FFFFFF"
                emo_s = rec.get("emo_score") if rec else None
                pct_v2 = rec.get("pct") if rec else None
                up_v = rec.get("up") if rec else None
                dn_v = rec.get("dn") if rec else None
                zt_v = rec.get("zt") if rec else None
                dt_v = rec.get("dt") if rec else None

                wl = []
                # 行1: 日期(左) + 同花顺(右)
                l1 = tk.Frame(cell, bg=bg); l1.pack(fill="x", pady=(2,0)); wl.append(l1)
                fg = "#FFD54F" if is_today else "white"
                n = tk.Label(l1, text=str(d), bg=bg, fg=fg,
                            font=("", 11, "bold" if is_today else "normal")); n.pack(side="left", padx=3); wl.append(n)
                t = tk.Label(l1, text=f"{ths_icon}", bg=bg, fg=ths_fg, font=("", 10)); t.pack(side="right", padx=3); wl.append(t)
                # 行2: 盈亏emoji (居中大号)
                p = tk.Label(cell, text=pnl_sym, bg=bg, fg="white", font=("", 14, "bold")); p.pack(pady=0); wl.append(p)
                # 行3: stage阶段文字 (居中)
                s = tk.Label(cell, text=stage_v or "·", bg=bg, fg=stage_fg, font=("", 10, "bold")); s.pack(pady=0); wl.append(s)
                # 行4: 优先显示涨跌广度, fallback emo+涨跌幅
                info_txt = ""; info_fg = "#B0BEC5"
                if up_v is not None and dn_v is not None:
                    # 有涨跌数据 → 显示广度
                    info_txt = f"↑{up_v} ↓{dn_v}"
                    if zt_v: info_txt += f" 🔥{zt_v}"
                    if dt_v: info_txt += f" ⚠️{dt_v}"
                    # 颜色: 涨多红/跌多绿/持平金
                    info_fg = "#FFCDD2" if up_v > dn_v else ("#C8E6C9" if up_v < dn_v else "#FFECB3")
                else:
                    # 无广度数据 → fallback emo分+涨跌幅
                    if emo_s is not None: info_txt += f"emo{emo_s:.0f}"
                    if pct_v2 is not None: info_txt += f" {pct_v2:+.1f}%"
                    if not info_txt: info_txt = "·"
                inf = tk.Label(cell, text=info_txt.strip(), bg=bg, fg=info_fg,
                               font=("", 9)); inf.pack(pady=0); wl.append(inf)
                wl.append(cell)

                def _bind_all(wlist, _ds=ds):
                    def _click(e):
                        print(f"[情绪日历] 👆 点击格子 ds={_ds}  hist_dict有={_ds in hist_dict}", flush=True)
                        if not is_rebuilding[0]: _open_day_editor(_ds)
                    def _ent(e):
                        _r = hist_dict.get(_ds, {})
                        _t = (f"📅 {_ds}  ①{_r.get('stage','未填') or '未填'}  "
                              f"②同花顺:{_r.get('ths','未填')}  ③盈亏:{_r.get('pnl','未填')}  "
                              f"📊emo={_r.get('emo_score','--')}  📈上证={_r.get('pct','--')}")
                        detail_lbl.config(text=_t, fg="#FFD54F")
                    def _lv(e):
                        detail_lbl.config(text="点击格子补录/修改, 鼠标悬停看三维度详情", fg="#90A4AE")
                    for w in wlist:
                        try:
                            w.bind("<Button-1>", _click)
                            w.bind("<Enter>", _ent)
                            w.bind("<Leave>", _lv)
                        except: pass
                _bind_all(wl)

                col += 1
                if col > 6: col = 0; row += 1

            for ci in range(7): grid_f.grid_columnconfigure(ci, weight=1)

            # 📊 复盘面板 (嵌在月历下方)
            try:
                pct_map_r, close_map_r = self._fetch_month_index_pct(ym)
                self._render_month_review(grid_f, ym, pct_map_r, close_map_r)
            except Exception as _rv_e:
                print(f"[情绪周期] 复盘面板 warn: {_rv_e}", flush=True)

            is_rebuilding[0] = False
            _refresh_stats()

        _render_month()


    def _show_emo_cycle_dialog(self):
        """🎭 情绪周期三维度输入 → 自动风控警告（系统红灯+同花顺+自己账户盈亏）+ 日历补录"""
        import json as _j_emo, os as _os_emo, datetime as _dt_emo
        from datetime import datetime as _dt2, timedelta as _td_emo
        EMO_HIST = _os_emo.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_emo_history.json")

        # ---- 自动获取维度1: 红绿灯 + 情绪阶段 ----
        auto_stage = getattr(self, "_dapan_emo_var", None)
        auto_text = auto_stage.get() if auto_stage else "⏳ 请先点 🗺️大盘分析 → 🔄刷新"
        BAD_STAGES = ("冰点", "退潮")
        is_bad_stage = any(s in auto_text for s in BAD_STAGES)

        # ---- 加载历史 (dict格式, 兼容旧list格式) ----
        hist_dict = {}
        if _os_emo.path.exists(EMO_HIST):
            try:
                with open(EMO_HIST) as f:
                    raw = _j_emo.load(f)
                if isinstance(raw, dict):
                    hist_dict = raw
                elif isinstance(raw, list):
                    # 旧格式 list → 转 dict
                    for h in raw:
                        hist_dict[h.get("date", "")] = h
            except: hist_dict = {}

        def _save_hist_dict():
            """持久化 hist_dict 到 JSON 文件 + 后台 push Gist"""
            with open(EMO_HIST, "w") as f:
                _j_emo.dump(hist_dict, f, ensure_ascii=False, indent=2)
            import threading as _th_s
            def _bg_push():
                r = self._emo_gist_push(hist_dict)
                if r.get("ok"): print(f"[情绪周期] {r['msg']}")
                else: print(f"[情绪周期] sync skip: {r.get('msg','')}")
            try: _th_s.Thread(target=_bg_push, daemon=True).start()
            except: pass

        def _sorted_list():
            """dict → list 按日期升序"""
            return sorted(hist_dict.values(), key=lambda x: x.get("date", ""))

        def _calc_consec_loss():
            """计算连续亏钱天数 (从最近日期往回数)"""
            cl = 0
            for h in reversed(_sorted_list()):
                if h.get("pnl") == "亏钱": cl += 1
                else: break
            return cl

        # ---- UI ----
        win = tk.Toplevel(self.root)
        win.title("🎭 情绪周期 · 三维度风控")
        win.geometry("580x560")
        win.configure(bg="#263238")

        tk.Label(win, text="🎭 情绪周期 · 三维度风控", bg="#263238", fg="#FFD54F",
                 font=("", 14, "bold")).pack(pady=(10, 2))
        tk.Label(win, text="情绪指数占 60-70% 决策力 · 不好就空仓, 好才加仓",
                 bg="#263238", fg="#90A4AE", font=("", 9)).pack(pady=(0, 6))

        # ---------- 维度1: 系统红绿灯 (自动) ----------
        f1 = tk.LabelFrame(win, text="① 系统红绿灯情绪 (自动获取)", bg="#263238", fg="#81D4FA",
                          font=("", 10, "bold"), padx=10, pady=6)
        f1.pack(fill=tk.X, padx=12, pady=3)
        tk.Label(f1, text=f"情绪阶段: 【{auto_text}】", bg="#263238", fg="white",
                 font=("", 11)).pack(anchor="w")
        tag1 = "⚠️ 该回乡下去躲一躲！" if is_bad_stage else "✅ 情绪健康"
        col1 = "#B71C1C" if is_bad_stage else "#1B5E20"
        tk.Label(f1, text=tag1, bg="#263238", fg=col1, font=("", 11, "bold")).pack(anchor="w", pady=(2, 0))

        # ---------- 维度2: 同花顺 (手工) ----------
        f2 = tk.LabelFrame(win, text="② 同花顺情绪指数 (手工输入)", bg="#263238", fg="#FFAB91",
                          font=("", 10, "bold"), padx=10, pady=6)
        f2.pack(fill=tk.X, padx=12, pady=3)
        tk.Label(f2, text="同花顺APP → 情绪指数 → 向上 or 向下?", bg="#263238",
                 fg="#B0BEC5", font=("", 9)).pack(anchor="w")
        ths_var = tk.StringVar(value="向上 (yes)")
        tk.Radiobutton(f2, text="📈 向上 (yes)", variable=ths_var, value="向上 (yes)",
                       bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")
        tk.Radiobutton(f2, text="📉 向下 (no)", variable=ths_var, value="向下 (no)",
                       bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")

        # ---------- 维度3: 今日盈亏 (手工) ----------
        f3 = tk.LabelFrame(win, text="③ 今天自己账户赚钱了吗? (连亏2天警告, 3天无条件清仓)",
                          bg="#263238", fg="#A5D6A7", font=("", 10, "bold"), padx=10, pady=6)
        f3.pack(fill=tk.X, padx=12, pady=3)
        tk.Label(f3, text="今天账户整体盈亏?", bg="#263238", fg="#B0BEC5", font=("", 9)).pack(anchor="w")
        pnl_var = tk.StringVar(value="赚钱 (yes)")
        tk.Radiobutton(f3, text="💰 赚钱 (yes)", variable=pnl_var, value="赚钱 (yes)",
                       bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")
        tk.Radiobutton(f3, text="📉 亏钱 (no)", variable=pnl_var, value="亏钱 (no)",
                       bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")

        today = _dt2.now().strftime("%Y-%m-%d")

        # 用 list 做可空 Holder, 解决闭包里 dir() 看不到外层变量的问题
        hist_text_ref = [None]

        def _refresh_stats():
            """刷新 f3 下方的统计标签和 hist_text 历史区"""
            nonlocal f3
            # 先移除旧的统计 Label 后重建
            for w in f3.winfo_children():
                try:
                    t = w.cget("text")
                except:
                    continue
                if isinstance(t, str) and t.startswith("📊"):
                    w.destroy()
            cl = _calc_consec_loss()
            tk.Label(f3, text=f"📊 历史记录 {len(hist_dict)} 天, 连续亏钱 {cl} 天",
                     bg="#263238", fg="#FFD54F", font=("", 10, "bold")).pack(anchor="w", pady=(6, 0))
            # 刷新最近7天历史
            ht = hist_text_ref[0]
            if ht is not None:
                ht.config(state="normal")
                ht.delete("1.0", "end")
                ht.insert("end", "日期\t\t同花顺\t盈亏\t\t情绪阶段\n")
                for h in _sorted_list()[-7:]:
                    line = f"{h.get('date','')}\t{h.get('ths','')}\t{'📉亏钱' if h.get('pnl')=='亏钱' else '💰赚钱'}\t{h.get('stage','')}\n"
                    ht.insert("end", line)
                ht.config(state="disabled")

        _refresh_stats()

        # ---------- 分析结果区 ----------
        result_lbl = tk.Label(win, text="", bg="#263238", justify="left",
                              font=("", 11, "bold"), wraplength=540)
        result_lbl.pack(fill=tk.X, padx=12, pady=6)

        def _analyze():
            ths_down = "向下" in ths_var.get()
            lost_today = "亏钱" in pnl_var.get()
            # 模拟今日若保存后的 hist_dict 来算连续亏
            tmp = dict(hist_dict)
            tmp[today] = {"date": today, "pnl": "亏钱" if lost_today else "赚钱",
                          "ths": "向下" if ths_down else "向上", "stage": auto_text}
            cl = 0
            for h in reversed(sorted(tmp.values(), key=lambda x: x.get("date", ""))):
                if h.get("pnl") == "亏钱": cl += 1
                else: break

            score = 0
            reasons = []
            if is_bad_stage:
                score += 1; reasons.append("❌ 系统情绪在 冰点/退潮")
            if ths_down:
                score += 1; reasons.append("❌ 同花顺情绪指数向下")
            if cl >= 2:
                score += 1; reasons.append(f"❌ 连续亏钱 {cl} 天")

            if score >= 3 or cl >= 3:
                msg = ("\n🚨🚨🚨 无条件清仓预警 🚨🚨🚨\n"
                       "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"   三维度同时触发! 必须清仓!\n\n"
                       f"   {chr(10).join(reasons)}\n\n"
                       "   情绪指数不好的时候,\n"
                       "   就干脆清仓空仓,\n"
                       "   能避掉 70% 的坑。\n\n"
                       "   —— 别再自己脑子有问题\n"
                       "      一下子亏十几个点了")
                result_lbl.config(text=msg, fg="#FF5252", bg="#B71C1C", padx=12, pady=12)
            elif cl >= 2:
                msg = ("\n⚠️⚠️ 亏损警告 ⚠️⚠️\n"
                       "━━━━━━━━━━━━━━━━━━━━\n"
                       f"   连续亏钱 {cl} 天!\n\n"
                       f"   {chr(10).join(reasons) if reasons else '   同花顺/红绿灯尚正常'}\n\n"
                       "   明天再亏一天 → 无条件清仓\n"
                       "   建议今天先减仓 50%")
                result_lbl.config(text=msg, fg="#FFD740", bg="#5D4037", padx=12, pady=12)
            elif score >= 2:
                msg = ("\n⚠️ 谨慎观望 ⚠️\n"
                       "━━━━━━━━━━━━━━━━━━━━\n"
                       f"   2个维度亮黄灯\n\n"
                       f"   {chr(10).join(reasons)}\n\n"
                       "   今天别开新仓\n"
                       "   持仓控制在 30% 以内")
                result_lbl.config(text=msg, fg="#FFB74D", bg="#4E342E", padx=12, pady=12)
            else:
                msg = ("\n✅ 情绪正常, 可以操作 ✅\n"
                       "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                       f"   {reasons[0] if reasons else '三维度均健康'}\n"
                       "   加仓看技术面, 不过度追高")
                result_lbl.config(text=msg, fg="#69F0AE", bg="#1B5E20", padx=12, pady=12)

        # ---------- 按钮区 ----------
        btn_f = tk.Frame(win, bg="#263238"); btn_f.pack(pady=4)
        tk.Button(btn_f, text="🔍 分析", command=_analyze,
                  bg="#FF6F00", fg="white", font=("", 10, "bold"), padx=10, pady=2).pack(side=tk.LEFT, padx=3)

        def _save_today():
            ths_down = "向下" in ths_var.get()
            lost_today = "亏钱" in pnl_var.get()
            hist_dict[today] = {"date": today, "pnl": "亏钱" if lost_today else "赚钱",
                                "ths": "向下" if ths_down else "向上", "stage": auto_text}
            _save_hist_dict()
            _refresh_stats()
            _analyze()

        tk.Button(btn_f, text="✅ 保存今日", command=_save_today,
                  bg="#1B5E20", fg="white", font=("", 10, "bold"), padx=10, pady=2).pack(side=tk.LEFT, padx=3)

        tk.Button(btn_f, text="📅 补录/修改历史", command=lambda: _open_calendar(),
                  bg="#6A1B9A", fg="white", font=("", 10, "bold"), padx=10, pady=2).pack(side=tk.LEFT, padx=3)

        # ---------- 最近7天历史 ----------
        tk.Label(win, text="📋 最近7天历史 (点击📅补录9月爆亏日方便复盘)", bg="#263238", fg="#81D4FA",
                 font=("", 9, "bold")).pack(anchor="w", padx=12, pady=(4, 0))
        hist_text = tk.Text(win, height=5, bg="#1A237E", fg="white", font=("", 9),
                            state="disabled", wrap="none")
        hist_text.pack(fill=tk.X, padx=12, pady=(2, 6))
        hist_text_ref[0] = hist_text  # 注册到 holder, 供 _refresh_stats 刷新
        hist_text.config(state="normal")
        hist_text.insert("end", "日期\t\t同花顺\t盈亏\t\t情绪阶段\n")
        for h in _sorted_list()[-7:]:
            line = f"{h.get('date','')}\t{h.get('ths','')}\t{'📉亏钱' if h.get('pnl')=='亏钱' else '💰赚钱'}\t{h.get('stage','')}\n"
            hist_text.insert("end", line)
        hist_text.config(state="disabled")

        # ==================== 📅 日历补录弹窗 ====================
        def _open_calendar():
            """月度日历, 点击日期可补录/修改/删除三维度数据"""
            cal_win = tk.Toplevel(self.root)
            cal_win.title("📅 情绪周期日历 · 补录历史")
            cal_win.geometry("800x620")
            cal_win.configure(bg="#1A1A2E")
            cal_win.transient(win)
            cal_win.minsize(760, 580)

            # 先算出数据范围, 确定默认展示月份
            dates_with_data = [_dt2.strptime(d, "%Y-%m-%d") for d in hist_dict.keys()
                               if isinstance(d, str) and len(d) == 10]
            if dates_with_data:
                dates_with_data.append(_dt2.now())
                first_date = min(dates_with_data)
                default_month = _dt2(first_date.year, first_date.month, 1)
            else:
                default_month = _dt2.now().replace(day=1)

            view_month = [default_month]  # list 用于闭包修改
            cells_ref = {}  # {(row,col): cell_frame}
            # 避免程序化刷新触发回调
            is_rebuilding = [False]

            # ---------- 紧凑工具栏 (导航+月份+统计+图例 一行搞定) ----------
            top_f = tk.Frame(cal_win, bg="#1A1A2E"); top_f.pack(fill=tk.X, pady=(8, 2), padx=10)
            tk.Button(top_f, text="◀", command=lambda: _shift_month(-1),
                      bg="#37474F", fg="white", font=("", 9, "bold"), padx=6, pady=1).pack(side=tk.LEFT, padx=(0,2))
            month_lbl = tk.Label(top_f, text="", bg="#1A1A2E", fg="#FFD54F", font=("", 11, "bold"))
            month_lbl.pack(side=tk.LEFT, padx=2)
            tk.Button(top_f, text="▶", command=lambda: _shift_month(1),
                      bg="#37474F", fg="white", font=("", 9, "bold"), padx=6, pady=1).pack(side=tk.LEFT, padx=(2,4))
            # 统计 + 紧凑图例
            _up = sum(1 for v in hist_dict.values() if v.get("pnl") == "赚钱")
            _dn = sum(1 for v in hist_dict.values() if v.get("pnl") == "亏钱")
            _bad = sum(1 for v in hist_dict.values() if v.get("stage") in ("冰点","退潮"))
            tk.Label(top_f, text=f"📅{len(hist_dict)}天 💰{_up}📉{_dn} ⚠️{_bad}", bg="#1A1A2E",
                     fg="#FFD54F", font=("", 9, "bold")).pack(side=tk.LEFT, padx=4)
            tk.Label(top_f, text="", bg="#B71C1C", width=2, height=1).pack(side=tk.LEFT, padx=(6,0))
            tk.Label(top_f, text="", bg="#2E7D32", width=2, height=1).pack(side=tk.LEFT, padx=1)
            tk.Label(top_f, text="", bg="#E65100", width=2, height=1).pack(side=tk.LEFT, padx=1)
            # 右侧功能按钮
            tk.Button(top_f, text="🔄", command=lambda: (_reload_hist(), _render_month()),
                      bg="#2E7D32", fg="white", font=("", 8, "bold"), padx=5, pady=1).pack(side=tk.RIGHT, padx=(2,0))
            tk.Button(top_f, text="今天", command=lambda: _jump_today(),
                      bg="#0D47A1", fg="white", font=("", 8, "bold"), padx=5, pady=1).pack(side=tk.RIGHT, padx=(2,0))

            def _reload_hist():
                """强制从磁盘重新加载 hist_dict + 后台异步 Gist pull"""
                nonlocal hist_dict
                if _os_emo.path.exists(EMO_HIST):
                    try:
                        with open(EMO_HIST) as f:
                            raw = _j_emo.load(f)
                        if isinstance(raw, dict):
                            hist_dict = raw
                        elif isinstance(raw, list):
                            nh = {}
                            for h in raw: nh[h.get("date","")] = h
                            hist_dict = nh
                    except: pass
                # 后台异步 Gist pull (不阻塞 UI)
                import threading as _th_diag
                def _bg():
                    try:
                        _remote = self._emo_gist_pull(timeout=2)
                        if _remote:
                            hist_dict = self._merge_emo_hist(hist_dict, _remote)
                            print(f"[日历] 📥 Gist pull {len(_remote)}天", flush=True)
                    except Exception as _gx:
                        print(f"[日历] Gist pull skip: {_gx}", flush=True)
                try: _th_diag.Thread(target=_bg, daemon=True).start()
                except: pass

            # 星期表头
            wdays_f = tk.Frame(cal_win, bg="#1A1A2E"); wdays_f.pack(fill=tk.X, padx=10)
            for i, w in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
                tk.Label(wdays_f, text=w, bg="#263238", fg="#81D4FA", font=("", 10, "bold"),
                         width=7, pady=3).grid(row=0, column=i, padx=1, pady=1)

            # 紧凑详情提示条 (悬停/点击时更新)
            detail_lbl = tk.Label(cal_win, text="点击日期格子补录/修改 · 鼠标悬停看详情",
                                  bg="#1A1A2E", fg="#90A4AE", font=("", 9))
            detail_lbl.pack(fill=tk.X, padx=10, pady=(0, 1))

            # 日期网格容器 (Canvas+Scrollbar 保底, 空间不够时可滚动)
            _cal_cv = tk.Canvas(cal_win, bg="#1A1A2E", highlightthickness=0, bd=0)
            _cal_vsb2 = tk.Scrollbar(cal_win, orient="vertical", command=_cal_cv.yview,
                                     bg="#37474F", troughcolor="#1A1A2E")
            _cal_cv.configure(yscrollcommand=_cal_vsb2.set)
            _cal_vsb2.pack(side=tk.RIGHT, fill=tk.Y)
            _cal_cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0), pady=(0,6))
            grid_f = tk.Frame(_cal_cv, bg="#1A1A2E")
            _cal_wid2 = _cal_cv.create_window((0, 0), window=grid_f, anchor="nw")
            grid_f.bind("<Configure>", lambda e: _cal_cv.configure(scrollregion=_cal_cv.bbox("all")))
            _cal_cv.bind("<Configure>", lambda e: _cal_cv.itemconfig(_cal_wid2, width=e.width))
            # 鼠标滚轮 (macOS)
            def _mw(e): _cal_cv.yview_scroll(int(-e.delta/30), "units")
            def _on(e): _cal_cv.bind_all("<MouseWheel>", _mw)
            def _off(e): _cal_cv.unbind_all("<MouseWheel>")
            _cal_cv.bind("<Enter>", _on); _cal_cv.bind("<Leave>", _off)

            # ---------- 渲染月历 ----------
            def _render_month():
                # 每次渲染前先从磁盘 reload (大盘后台可能刚同步完新数据)
                try:
                    _reload_hist()
                except Exception as _re_e:
                    print(f"[日历] reload 警告: {_re_e}", flush=True)
                is_rebuilding[0] = True
                for w in grid_f.winfo_children(): w.destroy()
                cells_ref.clear()

                try:
                    ym = view_month[0]
                    month_lbl.config(text=f"{ym.year} 年 {ym.month} 月")
                    first = ym.replace(day=1)
                    first_wd = first.weekday()
                    if ym.month == 12:
                        next_month = ym.replace(year=ym.year + 1, month=1, day=1)
                    else:
                        next_month = ym.replace(month=ym.month + 1, day=1)
                    days_in_month = (next_month - _td_emo(days=1)).day

                    today_str = _dt2.now().strftime("%Y-%m-%d")

                    row = 0; col = first_wd
                    for d in range(1, days_in_month + 1):
                        date_str = f"{ym.year:04d}-{ym.month:02d}-{d:02d}"
                        is_today = (date_str == today_str)
                        rec = hist_dict.get(date_str)

                        if rec:
                            pnl = rec.get("pnl", "")
                            ths = rec.get("ths", "")
                            pct_v = rec.get("pct")
                            if pnl == "赚钱": bg = "#B71C1C"
                            elif pnl == "亏钱": bg = "#2E7D32"
                            elif pct_v is not None:
                                if pct_v > 0: bg = "#B71C1C"
                                elif pct_v < 0: bg = "#2E7D32"
                                else: bg = "#455A64"
                            else: bg = "#455A64"
                            border_color = "#E65100" if ths == "向下" else None
                        else:
                            bg = "#37474F"; border_color = None

                        cell = tk.Frame(grid_f, bg=bg, width=95, height=65,
                                        highlightbackground=border_color or "#1A1A2E",
                                        highlightthickness=3 if border_color else 1,
                                        cursor="hand2")
                        cell.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                        cell.grid_propagate(False)

                        def _click_all(widget_list, _ds=date_str):
                            def _click(e):
                                print(f"[情绪日历-独立] 👆 点击格子 ds={_ds}", flush=True)
                                if not is_rebuilding[0]: _open_day_editor(_ds)
                            def _enter(e):
                                _r = hist_dict.get(_ds, {})
                                _ths_t = {"向上":"📈向上","向下":"📉向下"}.get(_r.get("ths",""),"未填")
                                _pnl_t = {"赚钱":"💰赚钱","亏钱":"💸亏钱"}.get(_r.get("pnl",""),"未填")
                                _stage_t = _r.get("stage","未填") or "未填"
                                _emo_t = f"{_r.get('emo_score','--')}" if _r.get("emo_score") is not None else "--"
                                _pct_t = f"{_r.get('pct',0):+.2f}%" if _r.get("pct") is not None else "--"
                                detail_lbl.config(text=(f"📅 {_ds}  ①{_stage_t}  ②同花顺:{_ths_t}  "
                                                        f"③盈亏:{_pnl_t}  📊emo={_emo_t}  📈上证={_pct_t}"),
                                                  fg="#FFD54F")
                            def _leave(e):
                                detail_lbl.config(text="点击日历上的日期进行补录/修改", fg="#90A4AE")
                            for w in widget_list:
                                try:
                                    w.bind("<Button-1>", _click)
                                    w.bind("<Enter>", _enter)
                                    w.bind("<Leave>", _leave)
                                except Exception:
                                    pass

                        ths_v = rec.get("ths", "") if rec else ""
                        ths_icon = "📈" if ths_v == "向上" else ("📉" if ths_v == "向下" else "·")
                        ths_fg = "#81D4FA" if ths_v else "#78909C"
                        pnl_v = rec.get("pnl", "") if rec else ""
                        pnl_sym = "💰" if pnl_v == "赚钱" else ("💸" if pnl_v == "亏钱" else "·")
                        stage_v = rec.get("stage", "") if rec else ""
                        stage_v = re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9 ]+', '', str(stage_v or '')).strip()
                        stage_fg = "#FFD54F" if stage_v in ("冰点", "退潮") else "#FFFFFF"
                        emo_s = rec.get("emo_score") if rec else None
                        pct_v2 = rec.get("pct") if rec else None

                        widget_list = []
                        # 行1: 日期(左) + 同花顺(右)
                        l1 = tk.Frame(cell, bg=bg); l1.pack(fill=tk.X, pady=(2,0))
                        widget_list.append(l1)
                        fg = "#FFD54F" if is_today else "white"
                        nlbl = tk.Label(l1, text=str(d), bg=bg, fg=fg,
                                        font=("", 11, "bold" if is_today else "normal"))
                        nlbl.pack(side=tk.LEFT, padx=3)
                        widget_list.append(nlbl)
                        t = tk.Label(l1, text=f"{ths_icon}", bg=bg, fg=ths_fg, font=("", 10))
                        t.pack(side=tk.RIGHT, padx=3)
                        widget_list.append(t)
                        # 行2: 盈亏emoji (居中大号)
                        p = tk.Label(cell, text=pnl_sym, bg=bg, fg="white", font=("", 14, "bold"))
                        p.pack(pady=0)
                        widget_list.append(p)
                        # 行3: stage阶段文字 (居中)
                        s = tk.Label(cell, text=stage_v or "·", bg=bg, fg=stage_fg, font=("", 10, "bold"))
                        s.pack(pady=0)
                        widget_list.append(s)
                        # 行4: emo分 + 涨跌幅 (居中)
                        info_txt = ""
                        if emo_s is not None: info_txt += f"emo{emo_s:.0f}"
                        if pct_v2 is not None: info_txt += f" {pct_v2:+.1f}%"
                        if not info_txt: info_txt = "·"
                        inf = tk.Label(cell, text=info_txt.strip(), bg=bg, fg="#B0BEC5", font=("", 9))
                        inf.pack(pady=0)
                        widget_list.append(inf)
                        widget_list.append(cell)
                        _click_all(widget_list, date_str)
                        cells_ref[(row, col)] = (cell, date_str)
                        col += 1
                        if col > 6: col = 0; row += 1

                    for ci in range(7): grid_f.grid_columnconfigure(ci, weight=1)
                    for ri in range(max(row + 1, 6)): grid_f.grid_rowconfigure(ri, weight=1)
                except Exception as _rr_e:
                    print(f"[日历] ❌ 渲染失败: {_rr_e}", flush=True)
                    import traceback as _tb_r; _tb_r.print_exc()

                is_rebuilding[0] = False
                print(f"[日历] ✅ 渲染完成, {len(hist_dict)}天数据, cells={len(cells_ref)}", flush=True)

            _render_month()

            # ---------- 月份导航 ----------
            def _shift_month(delta):
                ym = view_month[0]
                new_m = ym.month + delta
                new_y = ym.year
                while new_m < 1:
                    new_m += 12; new_y -= 1
                while new_m > 12:
                    new_m -= 12; new_y += 1
                view_month[0] = _dt2(new_y, new_m, 1)
                _render_month()

            def _jump_today():
                view_month[0] = _dt2.now().replace(day=1)
                _render_month()

            # ---------- 单日编辑弹窗 ----------
            def _open_day_editor(date_str):
                edit_win = tk.Toplevel(cal_win)
                edit_win.title(f"📝 补录 {date_str}")
                edit_win.geometry("420x380")
                edit_win.configure(bg="#263238")
                edit_win.transient(cal_win)
                edit_win.grab_set()

                rec = hist_dict.get(date_str, {})

                tk.Label(edit_win, text=f"📅 {date_str} 三维度记录", bg="#263238", fg="#FFD54F",
                         font=("", 13, "bold")).pack(pady=(14, 4))

                # ===== 只读系统数据区 (自动从大盘趋势同步) =====
                sys_info_parts = []
                _emo_s = rec.get("emo_score")
                _pct_v = rec.get("pct")
                _close_v = rec.get("close")
                _zt_v = rec.get("zt")
                if _emo_s is not None:
                    sys_info_parts.append(f"📊情绪分={_emo_s:.0f}")
                if _pct_v is not None:
                    sys_info_parts.append(f"📈上证={_pct_v:+.2f}%")
                if _zt_v is not None:
                    sys_info_parts.append(f"🔥ZT={_zt_v}")
                if _close_v:
                    sys_info_parts.append(f"📉收={_close_v}")
                if sys_info_parts:
                    sys_info = "  |  ".join(sys_info_parts)
                    sys_f = tk.Frame(edit_win, bg="#37474F")
                    sys_f.pack(fill=tk.X, padx=12, pady=(0, 4))
                    tk.Label(sys_f, text=f"🔒系统自动同步: {sys_info}",
                             bg="#37474F", fg="#81D4FA", font=("", 9),
                             padx=8, pady=4).pack(fill=tk.X)
                else:
                    tk.Label(edit_win, text="ℹ️ 该天暂无系统情绪数据 (加载大盘后自动补充)",
                             bg="#263238", fg="#78909C", font=("", 8)).pack(pady=(0, 4))

                # 维度1: 情绪阶段 (手填, 或用auto_text作为默认值)
                f1e = tk.LabelFrame(edit_win, text="① 情绪阶段 (系统自动获取或手填)",
                                    bg="#263238", fg="#81D4FA", font=("", 10, "bold"), padx=10, pady=4)
                f1e.pack(fill=tk.X, padx=12, pady=3)
                stage_var = tk.StringVar(value=rec.get("stage", auto_text))
                tk.Entry(f1e, textvariable=stage_var, width=40,
                         bg="#1A237E", fg="white", insertbackground="white").pack(fill=tk.X, pady=2)

                # 维度2: 同花顺
                f2e = tk.LabelFrame(edit_win, text="② 同花顺情绪指数",
                                    bg="#263238", fg="#FFAB91", font=("", 10, "bold"), padx=10, pady=4)
                f2e.pack(fill=tk.X, padx=12, pady=3)
                ths_default = rec.get("ths", "向上")
                ths_edit_var = tk.StringVar(value=f"{ths_default} (yes)" if ths_default == "向上" else f"{ths_default} (no)")
                tk.Radiobutton(f2e, text="📈 向上 (yes)", variable=ths_edit_var, value="向上 (yes)",
                               bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")
                tk.Radiobutton(f2e, text="📉 向下 (no)", variable=ths_edit_var, value="向下 (no)",
                               bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")

                # 维度3: 盈亏
                f3e = tk.LabelFrame(edit_win, text="③ 账户盈亏",
                                    bg="#263238", fg="#A5D6A7", font=("", 10, "bold"), padx=10, pady=4)
                f3e.pack(fill=tk.X, padx=12, pady=3)
                pnl_default = rec.get("pnl", "赚钱")
                pnl_edit_var = tk.StringVar(value=f"{pnl_default} (yes)" if pnl_default == "赚钱" else f"{pnl_default} (no)")
                tk.Radiobutton(f3e, text="💰 赚钱 (yes)", variable=pnl_edit_var, value="赚钱 (yes)",
                               bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")
                tk.Radiobutton(f3e, text="📉 亏钱 (no)", variable=pnl_edit_var, value="亏钱 (no)",
                               bg="#263238", fg="#E0E0E0", selectcolor="#263238", activebackground="#263238").pack(anchor="w")

                def _save_edit():
                    ths_v = "向下" if "向下" in ths_edit_var.get() else "向上"
                    pnl_v = "亏钱" if "亏钱" in pnl_edit_var.get() else "赚钱"
                    # 保留自动同步的字段 (emo_score/pct/close/zt)
                    _old = hist_dict.get(date_str, {})
                    hist_dict[date_str] = {
                        "date": date_str, "pnl": pnl_v, "ths": ths_v,
                        "stage": stage_var.get().strip(),
                        "emo_score": _old.get("emo_score"),  # 自动同步保留
                        "pct": _old.get("pct"),
                        "close": _old.get("close"),
                        "zt": _old.get("zt"),
                    }
                    _save_hist_dict()
                    _render_month()
                    _refresh_stats()
                    edit_win.destroy()

                def _delete_rec():
                    if date_str in hist_dict:
                        del hist_dict[date_str]
                        _save_hist_dict()
                        _render_month()
                        _refresh_stats()
                    edit_win.destroy()

                btn_f_edit = tk.Frame(edit_win, bg="#263238"); btn_f_edit.pack(pady=10)
                tk.Button(btn_f_edit, text="💾 保存", command=_save_edit,
                          bg="#1B5E20", fg="white", font=("", 10, "bold"), padx=14, pady=3).pack(side=tk.LEFT, padx=5)
                if rec:
                    tk.Button(btn_f_edit, text="🗑️ 删除该天记录", command=_delete_rec,
                              bg="#B71C1C", fg="white", font=("", 10, "bold"), padx=10, pady=3).pack(side=tk.LEFT, padx=5)
                tk.Button(btn_f_edit, text="取消", command=edit_win.destroy,
                          bg="#546E7A", fg="white", font=("", 10), padx=10, pady=3).pack(side=tk.LEFT, padx=5)


    def _show_lifecycle_popup(self):
        """🧬 生命周期: 先弹选股弹窗让用户勾选持股标签页 → 再扫描带进度条 → 卡片网格结果"""

        # --- 选股弹窗 ---
        pick = tk.Toplevel(self.root)
        pick.title("🧬 生命周期扫描 — 选择候选池")
        pick.geometry("480x420")
        pick.configure(bg="#FCE4EC")
        pick.transient(self.root)
        pick.grab_set()
        pick.resizable(False, False)

        tk.Label(pick, text="🧬 生命周期·筹码转折点扫描", bg="#FCE4EC",
                 font=("", 14, "bold"), fg="#AD1457").pack(pady=(18, 4))
        tk.Label(pick, text="勾选要扫描的持股标签页 (可多选)", bg="#FCE4EC",
                 font=("", 10), fg="#880E4F").pack(pady=(0, 12))

        # 分组定义: group_index → 显示名
        _GROUP_MAP = [
            (2, "龙头股"),
            (4, "Main"),
            (6, "同花顺"),
            (7, "标签1"),
            (8, "标签2"),
            (9, "标签3"),
            (10, "标签4"),
            (11, "标签5"),
            (12, "标签6"),
            (13, "标签7"),
            (14, "标签8"),
        ]
        # 默认全选
        _selected = {}
        for gi, gname in _GROUP_MAP:
            _selected[gi] = tk.BooleanVar(value=True)

        # 统计每组当前股票数
        _counts = {}
        for gi, _ in _GROUP_MAP:
            hs = getattr(self, f"holding_stocks_{gi}", [None]*80)
            cnt = sum(1 for h in hs if h)
            _counts[gi] = cnt

        box = tk.Frame(pick, bg="#FCE4EC")
        box.pack(padx=20, fill="x")
        _total_all = sum(_counts.values())
        for i, (gi, gname) in enumerate(_GROUP_MAP):
            row = i // 2; col = i % 2
            cb = ttk.Checkbutton(box, text=f"{gname} ({_counts[gi]}只)",
                                 variable=_selected[gi])
            cb.grid(row=row, column=col, sticky="w", padx=8, pady=3)

        info = tk.Label(pick, text=f"📊 当前自持股池共 {_total_all} 只(去重后)",
                        bg="#FCE4EC", fg="#666", font=("", 9))
        info.pack(pady=8)

        # 全选/全不选
        def _toggle_all(val):
            for v in _selected.values(): v.set(val)
        btn_row = tk.Frame(pick, bg="#FCE4EC")
        btn_row.pack()
        ttk.Button(btn_row, text="全选", command=lambda: _toggle_all(True)).pack(side="left", padx=4)
        ttk.Button(btn_row, text="全不选", command=lambda: _toggle_all(False)).pack(side="left", padx=4)

        # 执行按钮 (先禁用, 选完组才能点)
        def _do_scan():
            chosen = [gi for gi, _ in _GROUP_MAP if _selected[gi].get()]
            if not chosen:
                messagebox.showwarning("提示", "请至少勾选一个标签页!", parent=pick)
                return
            if len(chosen) > len(_GROUP_MAP):
                return

            # 关选股窗, 进入进度条扫描
            pick.destroy()
            self._lifecycle_scan_with_groups(chosen)

        ttk.Button(pick, text="🔍 开始扫描", command=_do_scan,
                   width=18).pack(pady=14)


    def _lifecycle_scan_with_groups(self, group_indices):
        """🧬 渐进式生命周期扫描: 先渲染全部候选卡 → 后台逐股填充"""
        import queue as _queue
        import threading
        import time

        # --- 缓存按 groups 算 hash ---
        _g_hash = ",".join(str(g) for g in sorted(group_indices))
        _cache = getattr(self, "_lifecycle_cache", None)
        _now = time.time()
        if _cache and _cache.get("groups") == _g_hash and (_now - _cache.get("ts", 0)) < 1800 and _cache.get("data"):
            print(f"[生命周期] ✅ 使用缓存 ({(_now - _cache['ts']):.0f}s ago)")
            self._show_lifecycle_dialog(_cache["data"], from_cache=True, cache_age_s=int(_now - _cache["ts"]))
            return

        # --- Step 1: 立即构建候选池并渲染灰色卡片 ---
        pool = self._build_lifecycle_candidate_pool(group_indices)
        if not pool:
            # 兜底: 弹手动输入框
            pool = self._lifecycle_manual_input()
            if not pool: return
        print(f"[生命周期] 📊 候选池 {len(pool)} 只, 立即渲染卡片...")

        # 渲染弹窗 (全灰色 loading 卡) — 候选池模式
        self._show_lifecycle_dialog(pool)

        # --- Step 2: 后台线程逐股计算 ---
        _q = _queue.Queue()
        holder = {"pro": None, "trade_date": None, "today": None,
                  "valid_tsc_set": None, "_db_map": None,
                  "skip_count": {"ST/上市不足": 0, "K线不足": 0, "不满足过滤": 0, "无转折点": 0, "格式无效": 0}, "scan_done": False}

        def _bg():
            import datetime as _dt_mod
            import os as _os_env

            import tushare as _ts_mod
            try:
                _token = (_os_env.environ.get("TUSHARE_TOKEN", "") or
                          getattr(self, "ts_token", "") or TS_DEFAULT_TOKEN or "").strip()
                if not _token:
                    _q.put(("error", "TUSHARE_TOKEN 未配置")); return
                _ts_mod.set_token(_token)
                pro = _ts_mod.pro_api()
                holder["pro"] = pro

                today = _dt_mod.date.today()
                holder["today"] = today
                cal = pro.trade_cal(exchange="SSE",
                    start_date=(today - _dt_mod.timedelta(days=10)).strftime("%Y%m%d"),
                    end_date=today.strftime("%Y%m%d"), is_open="1")
                trade_date = str(cal["cal_date"].iloc[0]) if cal is not None and len(cal) > 0 else today.strftime("%Y%m%d")
                holder["trade_date"] = trade_date

                import pandas as _pd
                df_sb = pro.stock_basic(exchange="", list_status="L",
                    fields="ts_code,name,industry,list_date")
                today_dt = _pd.Timestamp(today.strftime("%Y%m%d"))
                valid_sb = df_sb[
                    (~df_sb["name"].fillna("").str.contains("ST|退", regex=True, na=False)) &
                    (_pd.to_datetime(df_sb["list_date"], errors="coerce") <= today_dt - _pd.Timedelta(days=365))
                ].copy() if df_sb is not None else _pd.DataFrame()
                holder["valid_tsc_set"] = set(valid_sb["ts_code"].tolist()) if len(valid_sb) > 0 else set()

                time.sleep(0.3)
                try:
                    _db_all = pro.daily_basic(trade_date=trade_date,
                        fields="ts_code,turnover_rate,circ_mv,total_mv,pct_chg,close")
                    if _db_all is not None and len(_db_all) > 0:
                        holder["_db_map"] = {row["ts_code"]: row for _, row in _db_all.iterrows()}
                        print(f"[生命周期] ✅ 批量 daily_basic {len(holder['_db_map'])} 只")
                except Exception as _e:
                    print(f"[生命周期] ⚠️ daily_basic 批量失败 {_e}")

                _total = len(pool)
                for _idx, (s_name, s_code, _gi) in enumerate(pool):
                    try:
                        result, skip_reason = self._calc_lifecycle_for_stock(
                            s_name, s_code, pro, trade_date, today,
                            holder["valid_tsc_set"], holder.get("_db_map", {}), holder["skip_count"])
                        _q.put(("stock_done", s_code, s_name, result, skip_reason, trade_date, dict(holder["skip_count"])))
                    except Exception as _e2:
                        import traceback; traceback.print_exc()
                        _q.put(("stock_done", s_code, s_name, None, f"异常: {_e2}", trade_date, dict(holder["skip_count"])))

                holder["scan_done"] = True
                _q.put(("all_done",))
            except Exception as e:
                import traceback; traceback.print_exc()
                _q.put(("error", str(e)))

        threading.Thread(target=_bg, daemon=True).start()

        # --- Step 3: UI 轮询队列, 更新卡片 ---
        def _poll_ui():
            try:
                while True:
                    msg = _q.get_nowait()
                    if msg[0] == "stock_done":
                        _, code, name, result, skip_reason, td, sk = msg
                        self.root.after(0, lambda c=code, n=name, r=result, sr=skip_reason,
                                           t=td, s=sk: self._lc_update_card(c, n, r, sr, t, s))
                    elif msg[0] == "all_done":
                        self.root.after(0, lambda: self._lc_scan_finished(_g_hash, holder))
                        return
                    elif msg[0] == "error":
                        print(f"[生命周期] ❌ {msg[1]}"); return
            except _queue.Empty: pass
            self.root.after(100, _poll_ui)

        self.root.after(100, _poll_ui)


    def _run_lifecycle_scan_on_groups(self, group_indices, progress_cb=None):
        """🧬 扫描指定 groups 的生命周期 (抽出候选池构建逻辑)"""
        # --- 1. 构建候选池 (按指定 group_indices) ---
        seen = set(); monitor = []
        for gi in group_indices:
            hs = getattr(self, f"holding_stocks_{gi}", [None]*80)
            for h in hs:
                if not h: continue
                nm, cd = h
                cd = (cd or "").strip()
                if not cd or cd in seen: continue
                seen.add(cd)
                monitor.append((nm or "", cd, gi))
        if not monitor:
            return {"trade_date": "", "stocks": [], "total_found": 0,
                    "error": "所选标签页均为空股"}
        return self._run_lifecycle_scan(monitor_pool=monitor, progress_cb=progress_cb)


    def _build_lifecycle_candidate_pool(self, group_indices):
        """🧬 构建生命周期候选池 (从指定标签页取股票, 去重)
        Returns:
            list[(name, code, gi)]
        """
        seen = set(); monitor = []
        for gi in group_indices:
            hs = getattr(self, f"holding_stocks_{gi}", [None]*80)
            for h in hs:
                if not h: continue
                nm, cd = h
                cd = (cd or "").strip()
                if not cd or cd in seen: continue
                seen.add(cd)
                monitor.append((nm or "", cd, gi))
        return monitor


    def _lifecycle_manual_input(self):
        """🧬 兜底: 手动输入股票代码构建候选池
        支持格式:
          每⾏一个, 逗号或空格分隔 名称,代码
          或只要 6 位代码
        Returns:
            list[(name, code, 0)]  或 None (取消)
        """
        win = tk.Toplevel(self.root)
        win.title("🧬 手动输入股票代码")
        win.geometry("520x380")
        win.configure(bg="#FCE4EC")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        tk.Label(win, text="📝 自持股池为空, 请手动输入股票", bg="#FCE4EC",
                 font=("", 13, "bold"), fg="#AD1457").pack(pady=(16, 4))
        tk.Label(win, text="每行一个: 名称,代码 或 只要6位代码 (如: 平安银行,000001 或 000001)",
                 bg="#FCE4EC", font=("", 9), fg="#880E4F").pack(pady=(0, 10))

        txt = tk.Text(win, height=12, width=55, font=("", 11))
        txt.pack(padx=20, pady=6)
        txt.insert("1.0", "000001\n600519\n002594\n300750")

        result = {"pool": None}

        def _on_ok():
            raw = txt.get("1.0", tk.END).strip()
            if not raw:
                messagebox.showwarning("提示", "请输入股票代码!", parent=win)
                return
            pool = []; seen = set()
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith("#"): continue
                # 解析: 支持 "名称,代码" / "名称 代码" / 只要代码
                parts = re.split(r"[,，\s]+", line)
                parts = [p.strip() for p in parts if p.strip()]
                if not parts: continue
                # 找 6 位代码
                code6 = None; name = ""
                for p in parts:
                    m = re.search(r"(\d{6})", p)
                    if m:
                        code6 = m.group(1)
                    elif not code6:
                        name = p
                if not code6: continue
                if code6 in seen: continue
                seen.add(code6)
                pool.append((name or code6, code6, 0))
            if not pool:
                messagebox.showwarning("提示", "未解析到有效股票代码!", parent=win)
                return
            result["pool"] = pool
            win.destroy()

        btns = tk.Frame(win, bg="#FCE4EC"); btns.pack(pady=10)
        ttk.Button(btns, text="✅ 开始扫描", command=_on_ok, width=14).pack(side="left", padx=6)
        ttk.Button(btns, text="❌ 取消", command=win.destroy, width=14).pack(side="left", padx=6)

        self.root.wait_window(win)
        return result["pool"]


    def _calc_lifecycle_for_stock(self, s_name, s_code, pro, trade_date, today,
                                   valid_tsc_set, _db_map, skip_count):
        """🧬 单股生命周期计算 (独立方法, 可在后台线程逐只调用)
        Returns:
            (result_dict | None, skip_reason_str)
            result_dict 包含完整卡片数据; None 表示被过滤掉, skip_reason 说明原因
        """
        import datetime as _dt_m
        code6 = re.search(r"(\d{6})", s_code or "").group(1) if re.search(r"(\d{6})", s_code or "") else (s_code or "").strip()[:6]
        if not code6 or len(code6) != 6:
            skip_count["格式无效"] = skip_count.get("格式无效", 0) + 1
            return None, f"代码格式无效: {s_code}"

        if code6.startswith(("6", "9", "5")):
            tsc = f"{code6}.SH"
        elif code6.startswith(("4", "8", "92")):
            tsc = f"{code6}.BJ"
        else:
            tsc = f"{code6}.SZ"

        # ST/上市不足检查
        if valid_tsc_set and tsc not in valid_tsc_set:
            skip_count["ST/上市不足"] = skip_count.get("ST/上市不足", 0) + 1
            return None, "ST/上市不足1年"

        # 拉K线
        start = (today - _dt_m.timedelta(days=730)).strftime("%Y%m%d")
        import time as _time_m
        _time_m.sleep(0.25)
        try:
            hist = pro.daily(ts_code=tsc, start_date=start, end_date=trade_date)
        except Exception as _e:
            return None, f"K线拉取失败: {_e}"
        if hist is None or len(hist) < 120:
            skip_count["K线不足"] = skip_count.get("K线不足", 0) + 1
            return None, f"K线不足({len(hist) if hist is not None else 0}天<120)"

        hist = hist.sort_values("trade_date").reset_index(drop=True)
        cl = hist["close"].values.astype(float)
        vo = hist["vol"].values.astype(float)
        lo = hist["low"].values.astype(float)
        hist["high"].values.astype(float)
        dates = hist["trade_date"].values
        import numpy as _np_m

        # daily_basic
        _db = None
        if tsc in _db_map:
            import pandas as _pd_m
            _db_row = _db_map[tsc]
            _db = _pd_m.DataFrame([_db_row.to_dict()])

        # MA
        def _ma_correct(arr, w):
            if len(arr) < w: return _np_m.full(len(arr), _np_m.nan)
            out = _np_m.full(len(arr), _np_m.nan)
            for i in range(w-1, len(arr)): out[i] = _np_m.mean(arr[i-w+1:i+1])
            return out
        ma20 = _ma_correct(cl, 20)
        ma60 = _ma_correct(cl, 60)

        # 阶段低点 L
        lookback_L = min(120, len(cl))
        L_val = float(_np_m.min(lo[-lookback_L:]))
        L_gain_pct = round((cl[-1] - L_val) / L_val * 100, 1) if L_val > 0 else 0

        # 筹码成本曲线
        d = 0.87; N = len(cl)
        vol_norm = vo / (_np_m.max(vo) + 1e-9)
        cost_arr = _np_m.full(N, _np_m.nan)
        calc_start = max(20, N - 180)
        for t in range(calc_start, N):
            i_lo = max(0, t - 179)
            idx = _np_m.arange(i_lo, t + 1)
            decay = d ** (t - idx)
            w = vol_norm[idx] * decay
            c_weights = cl[idx] * w
            cost_arr[t] = _np_m.sum(c_weights) / (_np_m.sum(w) + 1e-9)

        # 筹码转折点 T*
        cost_valid = cost_arr[calc_start:]
        slope = _np_m.diff(cost_valid)
        pivot_indices = []
        for k in range(5, len(slope)):
            if slope[k] >= 0 and slope[k-1] >= 0:
                prev_neg = False
                for j in range(max(0, k-10), k):
                    if slope[j] < 0:
                        prev_neg = True; break
                if prev_neg:
                    pivot_indices.append(calc_start + k + 1)
        if not pivot_indices:
            skip_count["无转折点"] = skip_count.get("无转折点", 0) + 1
            return None, "无筹码转折点"
        t_star = pivot_indices[-1]
        P0 = round(float(cl[t_star]), 3)
        T_star_date = str(dates[t_star])

        # --- 6 层过滤 ---
        last3 = cl[-3:]
        ma20_last3 = ma20[-3:]
        above_ma20 = all(last3 > ma20_last3) if not _np_m.any(_np_m.isnan(ma20_last3)) else False
        if not above_ma20:
            skip_count["不满足过滤"] += 1
            return None, "MA20未站稳3日"

        ma20_10 = ma20[-10:]
        if _np_m.any(_np_m.isnan(ma20_10)):
            skip_count["不满足过滤"] += 1
            return None, "MA20数据不足"
        ma20_slope_pct = round((ma20_10[-1] - ma20_10[0]) / (ma20_10[0] + 1e-9) * 100, 2)
        ma20_flat = -3.0 <= ma20_slope_pct <= 10.0

        not_overheat = L_gain_pct < 50.0
        t_star_recency = (N - 1) - t_star <= 60
        p0_gain_pct = round((cl[-1] - P0) / P0 * 100, 1) if P0 > 0 else 0
        not_chase = p0_gain_pct < 50.0
        daily_turnover = float(_np_m.mean(vo[-60:]) * cl[-1]) if len(cl) > 60 else 0
        liquid = daily_turnover > 3e7

        if not (ma20_flat and not_overheat and t_star_recency and not_chase and liquid):
            reasons = []
            if not ma20_flat: reasons.append(f"MA20斜率{ma20_slope_pct:+.1f}%")
            if not not_overheat: reasons.append(f"距低点+{L_gain_pct:.0f}%")
            if not t_star_recency: reasons.append(f"T*距今{(N-1)-t_star}日>60")
            if not not_chase: reasons.append(f"距P0+{p0_gain_pct:.0f}%")
            if not liquid: reasons.append("成交额不足3kw")
            skip_count["不满足过滤"] += 1
            return None, " | ".join(reasons)

        # --- 形态特征 ---
        circ_mv = 0.0
        if _db is not None and len(_db) > 0:
            if "circ_mv" in _db.columns and _pd_m.notna(_db["circ_mv"].iloc[0]):
                circ_mv = float(_db["circ_mv"].iloc[0])
            if "total_mv" in _db.columns and _pd_m.notna(_db["total_mv"].iloc[0]):
                float(_db["total_mv"].iloc[0])

        vol_recent = vo[-60:]
        vol_volatility = float(_np_m.std(vol_recent) / (_np_m.mean(vol_recent) + 1e-9))
        vol_expansion = float(_np_m.mean(vo[-5:]) / (_np_m.mean(vo[-20:-5]) + 1e-9))

        pct_changes = _np_m.diff(cl[-60:]) / cl[-60:-1] * 100
        up_days = int(_np_m.sum(pct_changes > 0))
        down_days = int(_np_m.sum(pct_changes < 0))
        zt_days = int(_np_m.sum(pct_changes >= 9.0))

        if not _np_m.isnan(ma60[-1]):
            ma60_dist = round((cl[-1] - ma60[-1]) / ma60[-1] * 100, 1)
        else:
            ma60_dist = 0.0

        # --- 三分类打标 ---
        score_inst = score_main = score_hot = 0
        if circ_mv > 100e4: score_inst += 35
        elif circ_mv > 50e4: score_inst += 15; score_main += 15
        elif circ_mv > 20e4: score_main += 30
        elif circ_mv > 10e4: score_main += 15; score_hot += 20
        else: score_hot += 35

        if zt_days == 0 and vol_volatility < 0.8: score_inst += 25
        elif zt_days <= 2 and 0.5 < vol_volatility < 1.5: score_main += 25
        elif zt_days >= 3 or vol_volatility > 1.2: score_hot += 25

        if ma60_dist > 5: score_inst += 15
        elif ma60_dist > 0: score_main += 10
        elif ma60_dist < -5: score_hot += 10

        if 0.7 < vol_expansion < 1.3: score_inst += 10
        elif 1.3 <= vol_expansion < 2.0: score_main += 10
        elif vol_expansion >= 2.0: score_hot += 10

        if up_days > down_days + 10: score_inst += 10
        elif up_days > down_days: score_main += 8

        scores_tag = [("机构票", score_inst), ("主力票", score_main), ("游资票", score_hot)]
        scores_tag.sort(key=lambda x: x[1], reverse=True)
        best_label, best_score = scores_tag[0]
        second_score = scores_tag[1][1]
        is_hybrid = (best_score - second_score) < 10

        if is_hybrid:
            final_label = f"合力票·{best_label}"
            mult_low, mult_high = 2.0, 3.0
        elif best_label == "机构票":
            mult_low, mult_high = 4.0, 6.0
        elif best_label == "主力票":
            mult_low, mult_high = 2.0, 3.0
        else:
            mult_low, mult_high = 1.5, 2.0

        if best_score >= 50: conf = "高"
        elif best_score >= 35: conf = "中"
        else: conf = "低"

        risk_stars = 1
        if p0_gain_pct > 30: risk_stars = 2
        if p0_gain_pct > 40: risk_stars = 3
        if circ_mv < 20e4: risk_stars += 1
        if best_label == "游资票": risk_stars += 1
        risk_stars = min(5, risk_stars)

        result = {
            "code": code6,
            "name": s_name,
            "price": float(cl[-1]),
            "trade_date": trade_date,
            "L_val": L_val,
            "L_gain_pct": L_gain_pct,
            "T_star_date": T_star_date,
            "T_star_offset": int((N - 1) - t_star),
            "P0": P0,
            "p0_gain_pct": p0_gain_pct,
            "ma20_slope_pct": ma20_slope_pct,
            "ma20_state": "上翘" if ma20_slope_pct > 1.0 else ("走平" if ma20_slope_pct >= -1.0 else "下行"),
            "ma60_dist": ma60_dist,
            "label": final_label,
            "label_conf": conf,
            "label_score": {"机构票": score_inst, "主力票": score_main, "游资票": score_hot},
            "mult_low": mult_low,
            "mult_high": mult_high,
            "target_low": round(P0 * mult_low, 2),
            "target_high": round(P0 * mult_high, 2),
            "risk_stars": risk_stars,
        }
        return result, None


    def _show_lifecycle_dialog(self, data_or_pool, from_cache=False, cache_age_s=0):
        """🧬 生命周期卡片弹窗 - 自动判断模式:
           - 候选池模式: 传 [(name, code, gi), ...] → 渐进渲染
           - 结果模式: 传 dict 带 "stocks" key → 直接渲染 (兼容缓存/旧调用)
        """
        if data_or_pool is None: return

        # --- 自动判断模式 ---
        _is_pool = (isinstance(data_or_pool, list) and len(data_or_pool) > 0 and
                   all(isinstance(x, tuple) and len(x) == 3 for x in data_or_pool[:3]))

        if _is_pool:
            candidates = data_or_pool
            trade_date = ""
            skip_count = {}
            _hit_list = []; _skipped_list = []; _scan_done = {"flag": False}
        else:
            data = data_or_pool
            stocks = data.get("stocks", [])
            trade_date = data.get("trade_date", "")
            skip_count = data.get("skip_count", {})
            # 兼容旧缓存: 没有 _skipped_list 数据 → 用 skip_count 里的数量生成占位 skip 卡
            _skipped_list = data.get("_skipped_list", [])
            if not _skipped_list and skip_count:
                _skipped_list = [("_cache_skip_", "—", f"ST={skip_count.get('ST/上市不足',0)} K线={skip_count.get('K线不足',0)} 过滤={skip_count.get('不满足过滤',0)}")]
            _hit_list = stocks; _scan_done = {"flag": True}

        win = tk.Toplevel(self.root)
        win.title("🧬 生命周期·筹码转折点扫描")
        win.geometry("1280x820")
        win.configure(bg="#FAFAFA")

        top_bar = tk.Frame(win, bg="#AD1457", height=42)
        top_bar.pack(fill="x"); top_bar.pack_propagate(False)
        _cache_tag = ""
        if from_cache:
            _min = cache_age_s // 60
            _cache_tag = f"  |  🟡 缓存({_min}分钟前)"
        title_lbl = tk.Label(top_bar, text="", bg="#AD1457", fg="white", font=("", 13, "bold"))
        title_lbl.pack(side="left", padx=15)

        overview = tk.Frame(win, bg="#FFF3E0")
        overview.pack(fill="x", padx=10, pady=(6, 0))
        overview_lbl = tk.Label(overview, text="", bg="#FFF3E0", fg="#E65100", font=("", 10, "bold"))
        overview_lbl.pack(padx=10, pady=6)

        _THEME = {
            "inst":    {"bg": "#E8F5E9", "fg": "#1B5E20", "accent": "#388E3C", "label": "机构票"},
            "main":    {"bg": "#FFF3E0", "fg": "#E65100", "accent": "#F57C00", "label": "主力票"},
            "hot":     {"bg": "#FFEBEE", "fg": "#B71C1C", "accent": "#D32F2F", "label": "游资票"},
            "hybrid":  {"bg": "#E3F2FD", "fg": "#0D47A1", "accent": "#1976D2", "label": "合力票"},
            "loading": {"bg": "#F5F5F5", "fg": "#757575", "accent": "#BDBDBD", "label": "⏳扫描中"},
            "skip":    {"bg": "#ECEFF1", "fg": "#546E7A", "accent": "#90A4AE", "label": "未命中"},
        }

        def _theme_key(label):
            if "合力" in label: return "hybrid"
            if "机构" in label: return "inst"
            if "主力" in label: return "main"
            return "hot"

        canvas = tk.Canvas(win, bg="#FAFAFA", highlightthickness=0)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=6)
        sb.pack(side="right", fill="y", pady=6)
        grid_frame = tk.Frame(canvas, bg="#FAFAFA")
        _cv_win = canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: (canvas.itemconfig(_cv_win, width=e.width),
                                              canvas.configure(scrollregion=canvas.bbox("all"))))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta/120), "units"))

        COLS = 4; CARD_W = 290
        _card_refs = {}

        def _make_card(idx, name, code, theme_key):
            th = _THEME[theme_key]
            r, c = divmod(idx, COLS)
            card = tk.Frame(grid_frame, bg=th["bg"], width=CARD_W,
                            highlightbackground=th["accent"], highlightthickness=2)
            card.grid(row=r, column=c, padx=6, pady=6, sticky="n")
            card.grid_propagate(False)
            refs = {"frame": card, "lbls": {}}

            def _mk(parent, row_bg, row_fg, row_text):
                f = tk.Frame(parent, bg=row_bg); f.pack(fill="x", padx=8); return f

            hdr = tk.Frame(card, bg=th["bg"])
            hdr.pack(fill="x", padx=8, pady=(6, 2))
            refs["lbls"]["hdr_n"] = tk.Label(hdr, text=name, bg=th["bg"], fg=th["fg"], font=("",12,"bold"))
            refs["lbls"]["hdr_n"].pack(side="left")
            refs["lbls"]["hdr_c"] = tk.Label(hdr, text=f"[{code}]", bg=th["bg"], fg="#555", font=("",9))
            refs["lbls"]["hdr_c"].pack(side="left", padx=(2,4))
            refs["lbls"]["hdr_t"] = tk.Label(hdr, text=th["label"], bg=th["accent"], fg="white", font=("",9,"bold"), padx=6)
            refs["lbls"]["hdr_t"].pack(side="right")
            tk.Frame(card, bg=th["accent"], height=2).pack(fill="x", padx=8, pady=3)

            mid = tk.Frame(card, bg=th["bg"]); mid.pack(fill="x", padx=8)
            refs["lbls"]["m1"] = tk.Label(mid, text="", bg=th["bg"], fg="#333", font=("",11,"bold"))
            refs["lbls"]["m1"].pack(side="left")
            refs["lbls"]["m2"] = tk.Label(mid, text="", bg=th["bg"], fg="#555", font=("",9))
            refs["lbls"]["m2"].pack(side="right")

            r2 = tk.Frame(card, bg=th["bg"]); r2.pack(fill="x", padx=8, pady=(1,0))
            refs["lbls"]["r2l"] = tk.Label(r2, text="", bg=th["bg"], fg=th["fg"], font=("",9,"bold"))
            refs["lbls"]["r2l"].pack(side="left")
            refs["lbls"]["r2r"] = tk.Label(r2, text="", bg=th["bg"], fg="#333", font=("",9))
            refs["lbls"]["r2r"].pack(side="right")

            r3 = tk.Frame(card, bg=th["bg"]); r3.pack(fill="x", padx=8)
            refs["lbls"]["r3l"] = tk.Label(r3, text="", bg=th["bg"], fg="#666", font=("",9))
            refs["lbls"]["r3l"].pack(side="left")
            refs["lbls"]["r3r"] = tk.Label(r3, text="", bg=th["bg"], fg="#666", font=("",9))
            refs["lbls"]["r3r"].pack(side="right")

            r4 = tk.Frame(card, bg=th["bg"]); r4.pack(fill="x", padx=8, pady=(4,0))
            refs["lbls"]["tgt"] = tk.Label(r4, text="", bg=th["bg"], fg=th["fg"], font=("",10,"bold"))
            refs["lbls"]["tgt"].pack(side="left")

            r5 = tk.Frame(card, bg=th["bg"]); r5.pack(fill="x", padx=8, pady=(2,4))
            refs["lbls"]["risk"] = tk.Label(r5, text="", bg=th["bg"], fg="#555", font=("",9))
            refs["lbls"]["risk"].pack(side="left")
            refs["lbls"]["conf"] = tk.Label(r5, text="", bg=th["bg"], fg=th["accent"], font=("",9,"bold"))
            refs["lbls"]["conf"].pack(side="right")

            # 双击绑定 (非 loading/skip 卡才弹)
            def _bind(parent):
                for w in parent.winfo_children():
                    w.bind("<Double-1>", _on_dbl_inner)
                    _bind(w)
            def _on_dbl_inner(e):
                if code.startswith(("skip_", "loading_")): return
                try: self._open_hotmoney_single_dialog(auto_code=code, auto_name=name)
                except Exception: import traceback; traceback.print_exc()
            _bind(card)
            return refs

        def _paint_hit(refs, result):
            tk_key = _theme_key(result["label"])
            th = _THEME[tk_key]
            card = refs["frame"]
            card.configure(bg=th["bg"], highlightbackground=th["accent"])
            # 递归改背景色
            def _rec_bg(w):
                try: w.configure(bg=th["bg"])
                except Exception: pass
                for c in w.winfo_children(): _rec_bg(c)
            _rec_bg(card)
            refs["lbls"]["hdr_t"].configure(bg=th["accent"], text=th["label"])
            refs["lbls"]["m1"].configure(text=f"现价 {result['price']:.2f}")
            refs["lbls"]["m2"].configure(text=f"T*={result['T_star_date']}")
            refs["lbls"]["r2l"].configure(fg=th["fg"], text=f"P0={result['P0']:.2f}")
            refs["lbls"]["r2r"].configure(fg=("#C62828" if result['p0_gain_pct']>=0 else "#2E7D32"),
                text=f"距P0 {result['p0_gain_pct']}%")
            refs["lbls"]["r3l"].configure(text=f"MA20 {result['ma20_state']}")
            refs["lbls"]["r3r"].configure(text=f"距低点 +{result['L_gain_pct']}%")
            mult = f"{result['mult_low']}~{result['mult_high']}x"
            refs["lbls"]["tgt"].configure(fg=th["fg"],
                text=f"🎯 目标 {result['target_low']:.2f}~{result['target_high']:.2f} ({mult})")
            refs["lbls"]["risk"].configure(text=f"风险 {'⭐' * result['risk_stars']}")
            refs["lbls"]["conf"].configure(fg=th["accent"], text=f"置信 {result['label_conf']}")

        def _paint_skip(refs, name, code, reason):
            th = _THEME["skip"]
            card = refs["frame"]
            card.configure(bg=th["bg"], highlightbackground=th["accent"])
            def _rec_bg(w):
                try: w.configure(bg=th["bg"])
                except Exception: pass
                for c in w.winfo_children(): _rec_bg(c)
            _rec_bg(card)
            refs["lbls"]["hdr_t"].configure(bg=th["accent"], text="未命中")
            refs["lbls"]["m1"].configure(text=f"[{code}]")
            refs["lbls"]["m2"].configure(text="")
            refs["lbls"]["r2l"].configure(fg=th["fg"], text=(reason[:22] if reason else "条件未满足"))
            refs["lbls"]["r2r"].configure(text="")
            refs["lbls"]["r3l"].configure(text="")
            refs["lbls"]["r3r"].configure(text="")
            refs["lbls"]["tgt"].configure(fg=th["fg"], text="—")
            refs["lbls"]["risk"].configure(text="")
            refs["lbls"]["conf"].configure(fg=th["accent"], text="—")

        def _update_overview():
            nonlocal trade_date, skip_count
            _inst = sum(1 for s in _hit_list if "机构" in s["label"] and "合力" not in s["label"]) if _scan_done["flag"] else 0
            _main = sum(1 for s in _hit_list if "主力" in s["label"] and "合力" not in s["label"]) if _scan_done["flag"] else 0
            _hot = sum(1 for s in _hit_list if "游资" in s["label"] and "合力" not in s["label"]) if _scan_done["flag"] else 0
            _hy = sum(1 for s in _hit_list if "合力" in s["label"]) if _scan_done["flag"] else 0
            title_lbl.configure(
                text=f"🧬 生命周期·筹码转折点扫描  |  {trade_date}  |  命中 {len(_hit_list)}  跳过 {len(_skipped_list)}  总 {len(_hit_list)+len(_skipped_list)}{_cache_tag}")
            if _scan_done["flag"]:
                overview_lbl.configure(
                    text=f"📊 机构 {_inst}  主力 {_main}  游资 {_hot}  合力 {_hy}  |  "
                         f"ST={skip_count.get('ST/上市不足',0)} K线={skip_count.get('K线不足',0)} 过滤={skip_count.get('不满足过滤',0)}")
            else:
                overview_lbl.configure(text=f"📊 扫描中... 已处理 {len(_hit_list)+len(_skipped_list)} 只  |  命中 {len(_hit_list)}  跳过 {len(_skipped_list)}")

        # --- 初始渲染 ---
        if _is_pool:
            for idx, (name, code, gi) in enumerate(candidates):
                refs = _make_card(idx, name, code, "loading")
                _card_refs[code] = refs
            _update_overview()
        else:
            _sort_rank = {"机构票":0,"主力票":1,"合力票·机构票":2,"合力票·主力票":2,"合力票·游资票":2,"游资票":3}
            idx = 0
            for s in sorted(_hit_list, key=lambda x: _sort_rank.get(x["label"],4)):
                refs = _make_card(idx, s["name"], s["code"], _theme_key(s["label"]))
                _paint_hit(refs, s)
                _card_refs[s["code"]] = refs
                idx += 1
            # 也渲染 skip 卡
            for code, name, reason in _skipped_list:
                refs = _make_card(idx, name, code, "skip")
                _paint_skip(refs, name, code, reason or "")
                _card_refs[code] = refs
                idx += 1
            _update_overview()

        tk.Label(win, text="💡 双击命中卡片 → 打开该股票游资心法全解  |  机构票 4-6x  主力 2-3x  游资 1.5-2x",
            bg="#FAFAFA", fg="#7B1FA2", font=("",9)).pack(side="bottom", pady=6)

        # --- 暴露给后台的更新方法 ---
        def _on_stock_done(code, name, result, skip_reason, td, sk):
            nonlocal trade_date, skip_count
            if td: trade_date = td
            if sk: skip_count = sk
            refs = _card_refs.get(code)
            if not refs: return
            if result is not None: _hit_list.append(result); _paint_hit(refs, result)
            else: _skipped_list.append((code, name, skip_reason or "")); _paint_skip(refs, name, code, skip_reason or "")
            _update_overview()
        def _on_all_done(): _scan_done["flag"] = True; _update_overview()

        win._on_stock_done = _on_stock_done
        win._on_all_done = _on_all_done
        win._lc_hit_list = _hit_list       # 给缓存用
        win._lc_skipped_list = _skipped_list  # 给缓存用


    def _collect_market_sentiment_snapshot(self) -> str:
        """汇总与 A 股情绪环境相关的公开指标(AKShare/东财等),文本展示,供「情绪」窗口与 AI 解读。"""
        text, _charts = self._collect_market_sentiment_snapshot_bundle()
        return text


    def _gather_quant_emotion_context(self):
        """汇总与「仓位/情绪」相关的界面指标,供量化策略弹窗右侧展示。"""
        lines = []
        lines.append("══ 当前盘面与情绪相关指标(本窗口取值)══")
        lines.append("")
        def _g(varname, default="(无)"):
            v = getattr(self, varname, None)
            try:
                return v.get() if v is not None else default
            except Exception:
                return default
        lines.append(f"· 情绪周期(程序 1情绪周期): {_g('emotion_cycle_var')}")
        lines.append(f"· 同花顺三档(配置): {_g('ths_sentiment_trend_var')}")
        lines.append(
            f"· 同花顺情绪指数: 1日线往上={_g('sentiment_index_ma1_uptrend_var')}  "
            f"在1日线上={_g('sentiment_index_ma1_above_var')}  "
            f"已确认={_g('sentiment_index_check_var')}"
        )
        lines.append(f"· 三维打分(0-30 各): 基本面={_g('fundamental_var')}  技术面={_g('technical_var')}  情绪面={_g('sentiment_var')}")
        try:
            f, t, s = int(_g("fundamental_var", "0")), int(_g("technical_var", "0")), int(_g("sentiment_var", "0"))
            lines.append(f"· 三维总分: {f + t + s} / 90")
        except Exception:
            pass
        pv = getattr(self, "position_vars", None) or {}
        for key, label in (("emotion", "情绪天气"), ("v_judge", "大V"), ("yesterday", "昨日盘况")):
            vv = pv.get(key)
            try:
                lines.append(f"· {label}: {vv.get() if vv else '-'}")
            except Exception:
                lines.append(f"· {label}: -")
        lines.append(f"· 凯利相关·牌权: {_g('card_power_var')}  值搏率: {_g('value_risk_var')}")
        lines.append(f"· 主流板块: {_g('main_sector_var')}")
        lines.append(f"· 开新仓许可: {_g('new_position_var')}")
        lines.append(f"· 止损规则: {_g('stop_loss_var')}")
        try:
            lines.append(f"· 仓位演算结果: {pv.get('result').get()}")
        except Exception:
            pass
        try:
            lines.append(f"· 三维总分标签: {pv.get('total_score_var').get()}")
        except Exception:
            pass
        lines.append("")
        try:
            score = self._get_market_sentiment_score()
            lines.append(f"· 程序内大盘情绪分: {score}")
        except Exception:
            pass
        lines.append("")
        lines.append("(指标含义以软件内标签为准;量化组合为思路梳理,不构成投资建议。)")
        return "\n".join(lines)


    def _format_sentiment_zone_snapshot_lines(self, snap):
        """将情绪区间快照格式化为只读文本(与右上「情绪总览」同源字段)。"""
        if not snap or not isinstance(snap, dict):
            return ["(本次联网未得到情绪五问快照:请检查网络、Node/pywencai(问财),或点击「完整刷新」重试。)"]
        lines = []
        t = snap.get("time", "")
        m = snap.get("metrics", {}) or {}
        def _fv(key, sub="value"):
            o = m.get(key)
            if isinstance(o, (int, float)):
                return float(o) if sub == "value" else None
            if not isinstance(o, dict):
                return None
            v = o.get(sub)
            if isinstance(v, (int, float)):
                return v
            return None
        lines.append(f"更新时间: {t}")
        v1 = _fv("m1_today")
        v1y = _fv("m1_yday")
        lines.append(
            f"问1 同花顺情绪指数:当日 {v1:+.2f}% / 昨日 {v1y:+.2f}%"
            if isinstance(v1, (int, float)) and isinstance(v1y, (int, float))
            else f"问1 同花顺情绪指数:当日/昨日涨跌幅(问财/日线回退,见数值) {v1} {v1y}"
        )
        mk = m.get("m2_market") or {}
        lines.append(
            f"问2 全A涨跌家数:上涨 {mk.get('up')} 下跌 {mk.get('down')} 平盘 {mk.get('flat')} 总计 {mk.get('total')}({mk.get('source', '')})"
        )
        lines.append(f"问3 60分钟上穿60日线且放量:约 { _fv('m3', 'count') } 只(问财条数)")
        lines.append(f"问4 15分钟多均线发散:约 { _fv('m4', 'count') } 只(问财条数)")
        hs, zz, kc = _fv("m5_hs300"), _fv("m5_zz500"), _fv("m5_kc30")
        av = _fv("m5_avg")
        def _fmt_pct_slot(v):
            if isinstance(v, (int, float)):
                return f"{v:+.2f}%"
            return "未获取"
        lines.append(
            f"问5 沪深300 {_fmt_pct_slot(hs)} · 中证500 {_fmt_pct_slot(zz)} · 科创30(问财名) {_fmt_pct_slot(kc)} · 三指均值 {_fmt_pct_slot(av)}"
        )
        return lines


    def _quant_snapshot_good_bad_lines(self, snap):
        """根据右上情绪区间五问 + 涨跌家数,给出简短大盘好坏判别(规则化)。"""
        lines = ["══ 3 大盘好坏(仅依据右上情绪区间指标 + 涨跌比)══"]
        if not snap or not isinstance(snap, dict):
            lines.append("(无快照)")
            return lines
        m = snap.get("metrics") or {}
        mk = m.get("m2_market") or {}
        up, down = mk.get("up"), mk.get("down")
        tot = mk.get("total") or 0
        m1 = (m.get("m1_today") or {}).get("value")
        m5a = (m.get("m5_avg"))
        if isinstance(m5a, dict):
            m5a = m5a.get("value")
        verdict = []
        if isinstance(up, (int, float)) and isinstance(down, (int, float)) and (up + down) > 0:
            if up > down * 1.3:
                verdict.append("涨跌结构偏多(上涨家数明显多于下跌)。")
            elif down > up * 1.3:
                verdict.append("涨跌结构偏空(下跌家数明显多于上涨)。")
            else:
                verdict.append("涨跌家数接近,盘面结构中性。")
        if isinstance(m1, (int, float)):
            if m1 >= 0.8:
                verdict.append("同花顺情绪指数当日涨幅较大 → 短线情绪偏热。")
            elif m1 <= -0.8:
                verdict.append("同花顺情绪指数当日跌幅较大 → 短线情绪偏冷。")
            else:
                verdict.append("同花顺情绪指数当日波动温和。")
        if isinstance(m5a, (int, float)):
            if m5a >= 0.4:
                verdict.append("沪深300/中证500/科创30 均线性偏强。")
            elif m5a <= -0.4:
                verdict.append("上述宽基平均偏弱,注意回撤与仓位。")
        ratio_txt = ""
        if isinstance(up, (int, float)) and isinstance(down, (int, float)) and tot:
            ratio_txt = f"上涨/下跌:{int(up)}/{int(down)}(样本总计约 {int(tot)})。"
        lines.append(ratio_txt or "涨跌家数未获取。")
        lines.append("综合:" + (" ".join(verdict) if verdict else "指标不全,请点「完整刷新」重新联网拉取。"))
        lines.append("声明:以上为规则摘要,不构成投资建议。")
        return lines


    def _quant_dialog_insert_up_down_count(self, w, v, *, is_up):
        """上涨家数红、下跌家数绿(情绪好/坏与盘面习惯一致)。"""
        if v is None:
            w.insert(tk.END, "-", ("neutral",))
            return
        if not isinstance(v, (int, float)):
            w.insert(tk.END, str(v), ("neutral",))
            return
        w.insert(tk.END, str(int(v)), ("up_bold" if is_up else "down_bold",))


    def show_market_breadth_stats_dialog(self):
        """A股:全市场(约 5000+)涨跌家数 + 涨跌停;横向汇总;可最大化/最小化;导出 Word/Excel/Txt。"""
        import datetime as _dt
        win = self._safe_toplevel(self.root)
        win.title("行情统计 · A股涨跌与涨跌停")
        win.geometry("1100x640")
        win.minsize(640, 440)
        try:
            win.resizable(True, True)
        except Exception:
            pass
        def _win_max():
            try:
                if sys.platform == "win32":
                    win.state("zoomed")
                else:
                    win.attributes("-zoomed", True)
            except Exception:
                pass
        def _win_restore():
            try:
                win.state("normal")
            except Exception:
                pass
            try:
                win.attributes("-zoomed", False)
            except Exception:
                pass
        menubar = tk.Menu(win)
        win_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="窗口", menu=win_menu)
        win_menu.add_command(label="最小化(隐藏到任务栏)", command=lambda: win.iconify())
        win_menu.add_command(label="最大化", command=_win_max)
        win_menu.add_command(label="还原", command=_win_restore)
        try:
            win.config(menu=menubar)
        except Exception:
            pass
        today = _dt.date.today()
        start_var = tk.StringVar(value=(today - _dt.timedelta(days=30)).isoformat())
        end_var = tk.StringVar(value=today.isoformat())
        export_state = {
            "meta": {},
            "table": [],
            "breadth_daily": [],
            "force_em_note": "",
        }
        last_grid_cells = {"cells": []}
        grid_font_size_var = tk.IntVar(value=11)
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="起始日期").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=start_var, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="结束日期").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Entry(top, textvariable=end_var, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="(YYYY-MM-DD)", foreground="gray", font=("TkDefaultFont", 8)).pack(
            side=tk.LEFT, padx=(4, 0)
        )
        ttk.Label(top, text="网格字体").pack(side=tk.LEFT, padx=(10, 0))
        font_spin = tk.Spinbox(
            top,
            from_=8,
            to=20,
            width=4,
            textvariable=grid_font_size_var,
        )
        font_spin.pack(side=tk.LEFT, padx=(4, 0))
        refresh_btn = ttk.Button(top, text="刷新统计")
        refresh_btn.pack(side=tk.RIGHT, padx=(12, 4))
        stats_btn = ttk.Button(top, text="统计图")
        stats_btn.pack(side=tk.RIGHT, padx=(0, 4))
        hdr = ttk.LabelFrame(win, text="统计日汇总(横向)· 全 A 涨跌为东财快照样本", padding=10)
        hdr.pack(fill=tk.X, padx=8, pady=(0, 4))
        stat_summary_var = tk.StringVar(value="统计日:-")
        ttk.Label(hdr, textvariable=stat_summary_var, font=("Microsoft YaHei UI", 11)).pack(anchor=tk.W)
        summary_fr = ttk.Frame(hdr)
        summary_fr.pack(fill=tk.X, pady=8)
        sep_c = "gray"
        f_big = ("Microsoft YaHei UI", 17, "bold")
        f_lbl = ("Microsoft YaHei UI", 10)
        def _pack_sep():
            ttk.Label(summary_fr, text="  |  ", foreground=sep_c).pack(side=tk.LEFT, padx=2)
        ttk.Label(summary_fr, text="上涨", font=f_lbl).pack(side=tk.LEFT)
        up_disp = tk.Label(summary_fr, text="-", font=f_big, fg="gray")
        up_disp.pack(side=tk.LEFT, padx=(2, 0))
        _pack_sep()
        ttk.Label(summary_fr, text="下跌", font=f_lbl).pack(side=tk.LEFT)
        down_disp = tk.Label(summary_fr, text="-", font=f_big, fg="black")
        down_disp.pack(side=tk.LEFT, padx=(2, 0))
        _pack_sep()
        ttk.Label(summary_fr, text="涨停", font=f_lbl).pack(side=tk.LEFT)
        zt_disp = tk.Label(summary_fr, text="-", font=f_big, fg="#c0392b")
        zt_disp.pack(side=tk.LEFT, padx=(2, 0))
        _pack_sep()
        ttk.Label(summary_fr, text="跌停", font=f_lbl).pack(side=tk.LEFT)
        dt_disp = tk.Label(summary_fr, text="-", font=f_big, fg="#27ae60")
        dt_disp.pack(side=tk.LEFT, padx=(2, 0))
        _pack_sep()
        ttk.Label(summary_fr, text="样本", font=f_lbl).pack(side=tk.LEFT)
        n_disp = tk.Label(summary_fr, text="-", font=("Microsoft YaHei UI", 11), fg="gray")
        n_disp.pack(side=tk.LEFT, padx=(2, 0))
        note_var = tk.StringVar(
            value="全 A 涨跌:合并沪深/科创/创业/北交所东财快照或 A 股全表,按涨跌幅>0/<0 统计;涨跌停为统计日东财涨跌停池(口径不含部分 ST、科创板等)。"
        )
        ttk.Label(hdr, textvariable=note_var, foreground="gray", font=("TkDefaultFont", 9), wraplength=820).pack(
            anchor=tk.W, pady=(6, 0)
        )
        hist_outer = ttk.Frame(win)
        hist_outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        grid_fr = ttk.LabelFrame(
            hist_outer,
            text="区间内每日涨跌家数(横向每行 10 个交易日,新→旧;上涨>4000 红色、<1000 绿色)",
            padding=6,
        )
        grid_fr.pack(fill=tk.BOTH, expand=True)
        grid_canvas = tk.Canvas(grid_fr, highlightthickness=0, height=300)
        grid_scroll = ttk.Scrollbar(grid_fr, orient=tk.VERTICAL, command=grid_canvas.yview)
        grid_inner = ttk.Frame(grid_canvas)
        _grid_win_id = grid_canvas.create_window((0, 0), window=grid_inner, anchor=tk.NW)
        grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        grid_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        try:
            grid_canvas.configure(yscrollcommand=grid_scroll.set)
        except Exception:
            pass
        def _on_grid_inner_cfg(_evt=None):
            try:
                grid_canvas.configure(scrollregion=grid_canvas.bbox("all"))
            except Exception:
                pass
        def _on_grid_canvas_cfg(evt):
            try:
                grid_canvas.itemconfig(_grid_win_id, width=evt.width)
            except Exception:
                pass
            _on_grid_inner_cfg()
            try:
                if last_grid_cells.get("cells"):
                    _render_breadth_grid_rows(last_grid_cells.get("cells") or [])
            except Exception:
                pass
        grid_inner.bind("<Configure>", lambda _e: _on_grid_inner_cfg())
        grid_canvas.bind("<Configure>", _on_grid_canvas_cfg)
        try:
            grid_canvas.bind(
                "<MouseWheel>",
                lambda e: grid_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            )
        except Exception:
            pass
        lower_pw = ttk.PanedWindow(hist_outer, orient=tk.HORIZONTAL)
        lower_pw.pack(fill=tk.BOTH, expand=False, pady=(6, 0))
        hist_fr = ttk.LabelFrame(lower_pw, text="区间内交易日涨跌停(倒序,最多40条)", padding=6)
        day_fr = ttk.LabelFrame(lower_pw, text="选中日期 · 主流看盘数据与简析", padding=6)
        lower_pw.add(hist_fr, weight=1)
        lower_pw.add(day_fr, weight=1)
        try:
            lower_pw.paneconfigure(hist_fr, minsize=420)
            lower_pw.paneconfigure(day_fr, minsize=420)
        except Exception:
            pass
        cols = ("日期", "涨停", "跌停", "备注")
        tv = ttk.Treeview(hist_fr, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (110, 72, 72, 420)):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor=tk.CENTER if c != "备注" else tk.W)
        sy = ttk.Scrollbar(hist_fr, orient=tk.VERTICAL, command=tv.yview)
        tv.configure(yscrollcommand=sy.set)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        day_text = tk.Text(day_fr, wrap=tk.WORD, height=8, font=("Microsoft YaHei UI", 10))
        day_sy = ttk.Scrollbar(day_fr, orient=tk.VERTICAL, command=day_text.yview)
        day_text.configure(yscrollcommand=day_sy.set)
        day_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        day_sy.pack(side=tk.RIGHT, fill=tk.Y)
        err_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=err_var, foreground="red", font=("TkDefaultFont", 9), wraplength=820).pack(
            padx=8, pady=(0, 4), anchor=tk.W
        )
        bot = ttk.Frame(win, padding=8)
        bot.pack(fill=tk.X)
        ttk.Button(bot, text="导出 Excel...", command=lambda: _export("xlsx")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bot, text="导出 Word...", command=lambda: _export("docx")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bot, text="导出 Txt...", command=lambda: _export("txt")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bot, text="关闭", command=win.destroy).pack(side=tk.RIGHT)
        def _parse_d(s):
            x = (s or "").strip().replace("/", "-")
            a, b, c = x.split("-")
            return _dt.date(int(a), int(b), int(c))
        def _dedupe_spot_df(merged):
            if merged is None or getattr(merged, "empty", True):
                return merged
            code_col = None
            for cand in ("代码", "code", "股票代码"):
                if cand in merged.columns:
                    code_col = cand
                    break
            if not code_col:
                return merged
            ser = (
                merged[code_col]
                .astype(str)
                .str.replace(r"\D", "", regex=True)
                .str[-6:]
                .str.zfill(6)
            )
            m = merged.assign(_c6=ser)
            return m.drop_duplicates(subset=["_c6"], keep="first").drop(columns=["_c6"], errors="ignore")
        def _merge_a_spot(force_em: bool = False):
            if not AKSHARE_AVAILABLE:
                return None
            if _should_skip_akshare() and not force_em:
                return None
            parts = []
            for fn in (
                getattr(ak, "stock_sh_a_spot_em", None),
                getattr(ak, "stock_sz_a_spot_em", None),
                getattr(ak, "stock_kc_a_spot_em", None),
                getattr(ak, "stock_cy_a_spot_em", None),
                getattr(ak, "stock_bj_a_spot_em", None),
            ):
                if fn is None:
                    continue
                try:
                    df = fn()
                    if df is not None and not getattr(df, "empty", True):
                        parts.append(df)
                except Exception:
                    pass
            merged = None
            if parts:
                try:
                    merged = pd.concat(parts, ignore_index=True)
                    merged = _dedupe_spot_df(merged)
                except Exception:
                    merged = None
            if merged is None or len(merged) < 1200:
                try:
                    df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                    if df is not None and not getattr(df, "empty", True):
                        if merged is None or len(merged) < len(df):
                            merged = _dedupe_spot_df(df)
                except Exception:
                    pass
            return merged
        def _count_up_down(merged):
            if merged is None or getattr(merged, "empty", True):
                return None, None, None, 0
            col = None
            for cand in ("涨跌幅", "涨跌pct", "涨幅", "f3"):
                if cand in merged.columns:
                    col = cand
                    break
            n = len(merged)
            if not col:
                return None, None, None, n
            pct = pd.to_numeric(merged[col], errors="coerce")
            up_n = int((pct > 0).sum())
            down_n = int((pct < 0).sum())
            flat_n = int((pct == 0).sum())
            return up_n, down_n, flat_n, n
        def _apply_up_style(nv):
            if nv is None or nv == "":
                up_disp.config(text="-", fg="gray")
                return
            try:
                v = int(nv)
            except Exception:
                up_disp.config(text=str(nv), fg="gray")
                return
            up_disp.config(text=str(v))
            if v > 4000:
                up_disp.config(fg="red")
            elif v < 1000:
                up_disp.config(fg="green")
            else:
                up_disp.config(fg="black")
        def _breadth_db_path():
            return os.path.join(D_DATA_DIR, "market_breadth_daily.sqlite")
        def _breadth_cache_init():
            try:
                os.makedirs(D_DATA_DIR, exist_ok=True)
            except Exception:
                pass
            p = _breadth_db_path()
            con = sqlite3.connect(p)
            try:
                con.execute(
                    "CREATE TABLE IF NOT EXISTS daily ("
                    "trade_date TEXT PRIMARY KEY, "
                    "up_n INTEGER, down_n INTEGER, flat_n INTEGER, n_stk INTEGER, "
                    "updated_ts TEXT)"
                )
                con.commit()
            finally:
                con.close()
        def _breadth_cache_upsert(d: _dt.date, up_n, down_n, flat_n, n_stk):
            if d is None or up_n is None:
                return
            _breadth_cache_init()
            ts = _dt.datetime.now().isoformat(timespec="seconds")
            con = sqlite3.connect(_breadth_db_path())
            try:
                con.execute(
                    "INSERT OR REPLACE INTO daily(trade_date,up_n,down_n,flat_n,n_stk,updated_ts) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        d.isoformat(),
                        int(up_n),
                        int(down_n if down_n is not None else 0),
                        int(flat_n if flat_n is not None else 0),
                        int(n_stk if n_stk is not None else 0),
                        ts,
                    ),
                )
                con.commit()
            finally:
                con.close()
        def _breadth_cache_getmany(dates):
            if not dates:
                return {}
            _breadth_cache_init()
            con = sqlite3.connect(_breadth_db_path())
            try:
                cur = con.cursor()
                keys = [x.isoformat() for x in dates]
                cur.execute(
                    "SELECT trade_date, up_n, down_n, flat_n, n_stk FROM daily WHERE trade_date IN ({})".format(",".join("?" * len(keys))),
                    keys,
                )
                return {
                    r[0]: {"up_n": r[1], "down_n": r[2], "flat_n": r[3], "n_stk": r[4]}
                    for r in cur.fetchall()
                }
            finally:
                con.close()
        def _fetch_missing_breadth_with_tushare(dates):
            """用 Tushare 按交易日补齐全市场上涨/下跌/平盘家数。"""
            if not dates:
                return {}
            if not TS_AVAILABLE:
                return {}
            token = (getattr(self, "ts_token", None) or TS_DEFAULT_TOKEN or "").strip()
            if not token:
                return {}
            try:
                client = self._ensure_tushare_client(token)
            except Exception:
                return {}
            out = {}
            for td in dates:
                try:
                    ymd = td.strftime("%Y%m%d")
                    # trade_date 模式:返回该日全市场日线(需账号权限点数)
                    df = client.daily(
                        trade_date=ymd,
                        fields="ts_code,trade_date,pct_chg,pre_close,close",
                    )
                    if df is None or df.empty:
                        continue
                    pct = pd.to_numeric(df.get("pct_chg"), errors="coerce")
                    if pct is None or pct.empty:
                        pre_close = pd.to_numeric(df.get("pre_close"), errors="coerce")
                        close = pd.to_numeric(df.get("close"), errors="coerce")
                        pct = (close - pre_close) / pre_close * 100.0
                    up_n = int((pct > 0).sum())
                    down_n = int((pct < 0).sum())
                    flat_n = int((pct == 0).sum())
                    n_stk = int(pct.notna().sum())
                    if n_stk > 0:
                        out[td.isoformat()] = {
                            "up_n": up_n,
                            "down_n": down_n,
                            "flat_n": flat_n,
                            "n_stk": n_stk,
                        }
                        _breadth_cache_upsert(td, up_n, down_n, flat_n, n_stk)
                except Exception:
                    # 单日失败不影响其他日期
                    continue
            return out
        def _position_hint(upv):
            try:
                u = int(upv)
            except Exception:
                return "仓位建议:-"
            if u > 4000:
                return "仓位建议:80%(偏进攻)"
            if u > 3000:
                return "仓位建议:50%-80%(偏积极)"
            if u < 1000:
                return "仓位建议:20%(偏防守)"
            return "仓位建议:20%-50%(中性)"
        def _build_day_analysis(day_iso):
            br = export_state.get("breadth_daily") or []
            row_map = {str(x.get("日期", "")): x for x in br}
            tr = {str(x.get("日期", "")): x for x in (export_state.get("table") or [])}
            b = row_map.get(str(day_iso), {})
            t = tr.get(str(day_iso), {})
            up = b.get("上涨", "")
            dn = b.get("下跌", "")
            fp = b.get("平盘", "")
            tt = b.get("总计", "")
            zt = t.get("涨停", "")
            dt = t.get("跌停", "")
            try:
                u = int(up)
            except Exception:
                u = None
            try:
                d = int(dn)
            except Exception:
                d = None
            bias = "市场强弱:数据不足"
            if u is not None and d is not None:
                if u - d > 1200:
                    bias = "市场强弱:明显偏强(上涨显著多于下跌)"
                elif d - u > 1200:
                    bias = "市场强弱:明显偏弱(下跌显著多于上涨)"
                else:
                    bias = "市场强弱:震荡均衡(涨跌家数接近)"
            lines = [
                f"日期:{day_iso}",
                f"上涨:{up}   下跌:{dn}   平盘:{fp}   总计:{tt}",
                f"涨停:{zt}   跌停:{dt}",
                _position_hint(up if up != '' else None),
                bias,
                "看盘要点:",
                "1) 先看涨跌家数结构,再看涨停/跌停扩散。",
                "2) 若上涨>4000且涨停活跃,主线持续性通常更强。",
                "3) 若上涨<1000或跌停扩散,优先风控与仓位收缩。",
            ]
            return "\n".join(lines)
        def _show_day_analysis(day_iso):
            try:
                txt = _build_day_analysis(day_iso)
                day_text.config(state=tk.NORMAL)
                day_text.delete("1.0", tk.END)
                day_text.insert("1.0", txt)
                day_text.config(state=tk.DISABLED)
            except Exception:
                pass
        def _render_breadth_grid_rows(cells):
            try:
                fsz = int(grid_font_size_var.get())
            except Exception:
                fsz = 11
            fsz = max(8, min(20, fsz))
            f_top = ("Microsoft YaHei UI", fsz, "bold")
            f_bottom = ("Microsoft YaHei UI", max(8, fsz - 1), "bold")
            # 每行 3~4 天:宽屏 4,窄屏 3
            try:
                c_w = int(grid_canvas.winfo_width())
            except Exception:
                c_w = 0
            cols_per_row = 4 if c_w >= 980 else 3
            cols_per_row = max(3, min(4, cols_per_row))
            row_chunks = [cells[i : i + cols_per_row] for i in range(0, len(cells), cols_per_row)]
            for w in grid_inner.winfo_children():
                w.destroy()
            if not row_chunks:
                ttk.Label(grid_inner, text="(无交易日)").pack(anchor=tk.W)
                _on_grid_inner_cfg()
                return
            for row_cells in row_chunks:
                row_fr = ttk.Frame(grid_inner)
                row_fr.pack(fill=tk.X, pady=2)
                for cell in row_cells:
                    bf = ttk.Frame(row_fr, relief=tk.GROOVE, borderwidth=1)
                    try:
                        bf.configure(width=136, height=56)
                        bf.pack_propagate(False)
                    except Exception:
                        pass
                    bf.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2, pady=1)
                    td = cell["date"]
                    ds = td.strftime("%m-%d")
                    if cell.get("up") is None:
                        top_line = f"{ds}  仓位--"
                        bottom_line = "涨--  跌--  平--"
                        fg = "#555555"
                        bg = "#eeeeee"
                        hatch = False
                    else:
                        upv = int(cell["up"])
                        dv = int(cell["down"])
                        fv = int(cell["flat"])
                        if upv > 4000:
                            pos, bg, hatch = "80%", "#f5b7b1", False
                        elif upv > 3000:
                            pos, bg, hatch = "50%-80%", "#f8d7da", True
                        elif upv < 1000:
                            pos, bg, hatch = "20%", "#b7e1cd", False
                        else:
                            pos, bg, hatch = "20%-50%", "#e8eef5", False
                        top_line = f"{ds}  仓位{pos}"
                        bottom_line = f"涨{upv}  跌{dv}  平{fv}"
                        fg = "#8b0000" if upv > 3000 else ("#0b6b3a" if upv < 1000 else "#1f2937")
                    cv = tk.Canvas(bf, highlightthickness=0, bd=0)
                    cv.pack(fill=tk.BOTH, expand=True)
                    cv.update_idletasks()
                    w = max(128, int(cv.winfo_width() or 128))
                    h = max(50, int(cv.winfo_height() or 50))
                    cv.create_rectangle(0, 0, w, h, fill=bg, outline="")
                    if hatch:
                        step = 8
                        for x in range(-h, w + h, step):
                            cv.create_line(x, 0, x + h, h, fill="#e3a8ad", width=1)
                    cv.create_text(6, int(h * 0.34), anchor="w", text=top_line, fill=fg, font=f_top)
                    cv.create_text(6, int(h * 0.73), anchor="w", text=bottom_line, fill=fg, font=f_bottom)
            _on_grid_inner_cfg()
        def _on_tv_select(_evt=None):
            sel = tv.selection()
            if not sel:
                return
            vals = tv.item(sel[0], "values")
            if vals and len(vals) >= 1:
                _show_day_analysis(str(vals[0]))
        tv.bind("<<TreeviewSelect>>", _on_tv_select)
        def _export(kind: str):
            meta = export_state.get("meta") or {}
            rows = export_state.get("table") or []
            if not meta.get("统计日"):
                messagebox.showwarning("提示", "请先点击「刷新统计」再导出。", parent=win)
                return
            initial = os.path.join(D_DATA_DIR, f"行情统计_{meta.get('统计日', 'export')}")
            try:
                os.makedirs(D_DATA_DIR, exist_ok=True)
            except Exception:
                pass
            if kind == "txt":
                p = filedialog.asksaveasfilename(
                    parent=win,
                    defaultextension=".txt",
                    initialfile=os.path.basename(initial) + ".txt",
                    filetypes=[("文本", "*.txt"), ("所有", "*.*")],
                    initialdir=D_DATA_DIR,
                )
                if not p:
                    return
                lines = [
                    f"行情统计 导出 {_dt.datetime.now().isoformat(timespec='seconds')}",
                    f"区间: {meta.get('区间', '')}",
                    f"统计日: {meta.get('统计日', '')}",
                    f"上涨: {meta.get('上涨', '')}  下跌: {meta.get('下跌', '')}  平盘: {meta.get('平盘', '')}",
                    f"涨停: {meta.get('涨停', '')}  跌停: {meta.get('跌停', '')}",
                    f"样本股票数: {meta.get('样本股票数', '')}",
                    f"说明: {meta.get('说明', '')}",
                    "",
                    "日期\t涨停\t跌停\t备注",
                ]
                for r in rows:
                    lines.append(f"{r.get('日期','')}\t{r.get('涨停','')}\t{r.get('跌停','')}\t{r.get('备注','')}")
                br = export_state.get("breadth_daily") or []
                if br:
                    lines.append("")
                    lines.append("每日涨跌家数(新→旧,与网格顺序一致)")
                    lines.append("日期\t上涨\t下跌\t平盘\t总计")
                    for r in br:
                        lines.append(
                            f"{r.get('日期','')}\t{r.get('上涨','')}\t{r.get('下跌','')}\t{r.get('平盘','')}\t{r.get('总计', '')}"
                        )
                with open(p, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                messagebox.showinfo("完成", f"已保存:\n{p}", parent=win)
            elif kind == "xlsx":
                p = filedialog.asksaveasfilename(
                    parent=win,
                    defaultextension=".xlsx",
                    initialdir=D_DATA_DIR,
                    initialfile=os.path.basename(initial) + ".xlsx",
                    filetypes=[("Excel", "*.xlsx"), ("所有", "*.*")],
                )
                if not p:
                    return
                try:
                    summary = {k: [v] for k, v in meta.items()}
                    df_s = pd.DataFrame(summary)
                    df_t = pd.DataFrame(rows)
                    df_b = pd.DataFrame(export_state.get("breadth_daily") or [])
                    with pd.ExcelWriter(p, engine="openpyxl") as wr:
                        df_s.to_excel(wr, sheet_name="汇总", index=False)
                        if not df_b.empty:
                            df_b.to_excel(wr, sheet_name="每日涨跌", index=False)
                        df_t.to_excel(wr, sheet_name="涨跌停日历", index=False)
                        try:
                            from openpyxl.styles import Font
                            wb = wr.book
                            red_font = Font(color="FF0000")
                            green_font = Font(color="008000")
                            dark_green_font = Font(color="006400")
                            # 每日涨跌:上涨 >4000 红色,<1000 墨绿色
                            ws_b = wb["每日涨跌"] if "每日涨跌" in wb.sheetnames else None
                            if ws_b is not None:
                                header_map = {}
                                for c in range(1, ws_b.max_column + 1):
                                    name = ws_b.cell(row=1, column=c).value
                                    if name:
                                        header_map[str(name).strip()] = c
                                up_col = header_map.get("上涨")
                                if up_col:
                                    for r in range(2, ws_b.max_row + 1):
                                        cell = ws_b.cell(row=r, column=up_col)
                                        try:
                                            v = int(float(cell.value))
                                        except Exception:
                                            continue
                                        if v > 4000:
                                            cell.font = red_font
                                        elif v < 1000:
                                            cell.font = dark_green_font
                            # 涨跌停日历:涨停红色,跌停绿色
                            ws_t = wb["涨跌停日历"] if "涨跌停日历" in wb.sheetnames else None
                            if ws_t is not None:
                                header_map = {}
                                for c in range(1, ws_t.max_column + 1):
                                    name = ws_t.cell(row=1, column=c).value
                                    if name:
                                        header_map[str(name).strip()] = c
                                zt_col = header_map.get("涨停")
                                dt_col = header_map.get("跌停")
                                if zt_col:
                                    for r in range(2, ws_t.max_row + 1):
                                        cell = ws_t.cell(row=r, column=zt_col)
                                        if cell.value not in (None, "", "-", "?", "·"):
                                            cell.font = red_font
                                if dt_col:
                                    for r in range(2, ws_t.max_row + 1):
                                        cell = ws_t.cell(row=r, column=dt_col)
                                        if cell.value not in (None, "", "-", "?", "·"):
                                            cell.font = green_font
                        except Exception:
                            pass
                except Exception as e:
                    messagebox.showerror("错误", f"导出 Excel 失败(需安装 openpyxl):\n{e}", parent=win)
                    return
                messagebox.showinfo("完成", f"已保存:\n{p}", parent=win)
            elif kind == "docx":
                p = filedialog.asksaveasfilename(
                    parent=win,
                    defaultextension=".docx",
                    initialdir=D_DATA_DIR,
                    initialfile=os.path.basename(initial) + ".docx",
                    filetypes=[("Word", "*.docx"), ("所有", "*.*")],
                )
                if not p:
                    return
                try:
                    from docx import Document
                    doc = Document()
                    doc.add_heading("行情统计", level=1)
                    for k, v in meta.items():
                        doc.add_paragraph(f"{k}:{v}")
                    doc.add_paragraph("")
                    doc.add_heading("区间内涨跌停", level=2)
                    tbl = doc.add_table(rows=1 + len(rows), cols=4)
                    tbl.style = "Table Grid"
                    hdr_cells = tbl.rows[0].cells
                    hdr_cells[0].text = "日期"
                    hdr_cells[1].text = "涨停"
                    hdr_cells[2].text = "跌停"
                    hdr_cells[3].text = "备注"
                    for i, r in enumerate(rows):
                        row = tbl.rows[i + 1].cells
                        row[0].text = str(r.get("日期", ""))
                        row[1].text = str(r.get("涨停", ""))
                        row[2].text = str(r.get("跌停", ""))
                        row[3].text = str(r.get("备注", ""))
                    br = export_state.get("breadth_daily") or []
                    if br:
                        doc.add_heading("区间内每日涨跌家数", level=2)
                        tb2 = doc.add_table(rows=1 + len(br), cols=5)
                        tb2.style = "Table Grid"
                        h2 = tb2.rows[0].cells
                        h2[0].text = "日期"
                        h2[1].text = "上涨"
                        h2[2].text = "下跌"
                        h2[3].text = "平盘"
                        h2[4].text = "总计"
                        for i, r in enumerate(br):
                            row = tb2.rows[i + 1].cells
                            row[0].text = str(r.get("日期", ""))
                            row[1].text = str(r.get("上涨", ""))
                            row[2].text = str(r.get("下跌", ""))
                            row[3].text = str(r.get("平盘", ""))
                            row[4].text = str(r.get("总计", ""))
                    doc.save(p)
                except ImportError:
                    messagebox.showerror("错误", "未安装 python-docx,无法导出 Word。\npip install python-docx", parent=win)
                    return
                except Exception as e:
                    messagebox.showerror("错误", str(e), parent=win)
                    return
                messagebox.showinfo("完成", f"已保存:\n{p}", parent=win)
        def _show_breadth_stats_popup():
            br = export_state.get("breadth_daily") or []
            if not br:
                messagebox.showwarning("提示", "请先点击「刷新统计」生成周期数据。", parent=win)
                return
            series = []
            missing_n = 0
            for r in reversed(br):  # 旧 -> 新
                d = str(r.get("日期", "")).strip()
                try:
                    up = int(r.get("上涨"))
                    dn = int(r.get("下跌"))
                    fp = int(r.get("平盘"))
                    series.append((d, up, dn, fp))
                except Exception:
                    missing_n += 1
            if not series:
                messagebox.showwarning("提示", "当前周期暂无可统计的有效涨跌家数。", parent=win)
                return
            up_vals = [x[1] for x in series]
            dn_vals = [x[2] for x in series]
            fp_vals = [x[3] for x in series]
            dates = [x[0] for x in series]
            avg_up = round(sum(up_vals) / len(up_vals))
            avg_dn = round(sum(dn_vals) / len(dn_vals))
            avg_fp = round(sum(fp_vals) / len(fp_vals))
            max_up = max(series, key=lambda x: x[1])
            min_up = min(series, key=lambda x: x[1])
            pw = self._toplevel(win)
            pw.title("周期涨跌统计图")
            pw.geometry("1120x760")
            pw.minsize(860, 560)
            top2 = ttk.Frame(pw, padding=8)
            top2.pack(fill=tk.X)
            ttk.Label(top2, text="图形类型").pack(side=tk.LEFT)
            chart_var = tk.StringVar(value="折线图")
            chart_box = ttk.Combobox(
                top2,
                textvariable=chart_var,
                values=["折线图", "柱状图", "堆叠面积图", "分组柱状图"],
                state="readonly",
                width=14,
            )
            chart_box.pack(side=tk.LEFT, padx=6)
            stat_var = tk.StringVar(
                value=(
                    f"交易日: {len(br)}  有效: {len(series)}  缺失: {missing_n}   "
                    f"均值(涨/跌/平): {avg_up}/{avg_dn}/{avg_fp}   "
                    f"最大涨: {max_up[0]}={max_up[1]}   最小涨: {min_up[0]}={min_up[1]}"
                )
            )
            ttk.Label(top2, textvariable=stat_var, foreground="#333").pack(side=tk.LEFT, padx=(12, 0))
            chart_host = ttk.Frame(pw, padding=(8, 0, 8, 8))
            chart_host.pack(fill=tk.BOTH, expand=True)
            try:
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                from matplotlib.figure import Figure
            except Exception as e:
                ttk.Label(chart_host, text=f"未安装 matplotlib,无法绘图:{e}").pack(anchor=tk.W)
                ttk.Button(top2, text="关闭", command=pw.destroy).pack(side=tk.RIGHT)
                return
            fig = Figure(figsize=(10.5, 6.5), dpi=100)
            canvas = FigureCanvasTkAgg(fig, master=chart_host)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            def _draw_chart():
                kind = chart_var.get()
                fig.clear()
                ax = fig.add_subplot(111)
                x = list(range(len(dates)))
                if kind == "折线图":
                    ax.plot(x, up_vals, color="#c0392b", linewidth=1.8, label="上涨")
                    ax.plot(x, dn_vals, color="#1f4e79", linewidth=1.8, label="下跌")
                    ax.plot(x, fp_vals, color="#2e8b57", linewidth=1.5, label="平盘")
                elif kind == "柱状图":
                    colors = ["#c0392b" if v > 4000 else ("#1e8449" if v < 1000 else "#5d6d7e") for v in up_vals]
                    ax.bar(x, up_vals, color=colors, alpha=0.9, label="上涨")
                elif kind == "堆叠面积图":
                    ax.stackplot(x, up_vals, dn_vals, fp_vals, labels=["上涨", "下跌", "平盘"], alpha=0.75)
                else:
                    w = 0.28
                    ax.bar([i - w for i in x], up_vals, width=w, color="#c0392b", label="上涨")
                    ax.bar(x, dn_vals, width=w, color="#1f4e79", label="下跌")
                    ax.bar([i + w for i in x], fp_vals, width=w, color="#2e8b57", label="平盘")
                step = 1 if len(dates) <= 20 else (2 if len(dates) <= 60 else 5)
                xt = x[::step]
                xl = [dates[i][5:] if len(dates[i]) >= 10 else dates[i] for i in xt]
                ax.set_xticks(xt)
                ax.set_xticklabels(xl, rotation=45, ha="right")
                ax.set_ylabel("家数")
                ax.set_title("选定周期 A 股每日涨跌家数统计")
                ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
                ax.legend(loc="best")
                fig.tight_layout()
                canvas.draw()
            ttk.Button(top2, text="重绘", command=_draw_chart).pack(side=tk.RIGHT, padx=(0, 6))
            ttk.Button(top2, text="关闭", command=pw.destroy).pack(side=tk.RIGHT, padx=(0, 6))
            chart_box.bind("<<ComboboxSelected>>", lambda _e: _draw_chart())
            _draw_chart()
        def _do_refresh_sync():
            err_var.set("")
            export_state["force_em_note"] = ""
            if not AKSHARE_AVAILABLE:
                err_var.set("未安装或未启用 akshare,无法拉取东财数据。")
                return
            try:
                d0 = _parse_d(start_var.get())
                d1 = _parse_d(end_var.get())
            except Exception as e:
                err_var.set(f"日期格式错误(请使用 YYYY-MM-DD):{e}")
                return
            if d0 > d1:
                d0, d1 = d1, d0
            try:
                df_cal = safe_call(ak.tool_trade_date_hist_sina, fallback=pd.DataFrame(), label="ak.tool_trade_date_hist_sina")
                all_days = [x for x in df_cal["trade_date"].tolist() if isinstance(x, _dt.date)]
                market_latest = max([x for x in all_days if x <= today], default=None)
                in_range = [x for x in all_days if d0 <= x <= d1 and x <= today]
            except Exception as e:
                err_var.set(f"读取交易日历失败:{e}")
                return
            if not in_range:
                err_var.set("所选区间内没有交易日(或结束日期早于起始日期且均在今天之后)。")
                return
            stat_day = max(in_range)
            ymd = stat_day.strftime("%Y%m%d")
            stat_summary_var.set(f"统计日:{stat_day.isoformat()}  (区间 {d0.isoformat()}~{d1.isoformat()})")
            err_parts = []
            try:
                zt_df = ak.stock_zt_pool_em(date=ymd)
                zt_n = len(zt_df) if zt_df is not None and not getattr(zt_df, "empty", True) else 0
            except Exception as e:
                zt_n = None
                err_parts.append(f"涨停池:{e}")
            dt_n = None
            try:
                dt_df = ak.stock_zt_pool_dtgc_em(date=ymd)
                if dt_df is not None and not getattr(dt_df, "empty", True):
                    dt_n = len(dt_df)
                else:
                    dt_n = 0
            except Exception as e:
                dt_n = None
                err_parts.append(f"跌停池:{e}")
            merged = _merge_a_spot(force_em=False)
            force_note = ""
            if merged is None or _count_up_down(merged)[3] < 800:
                merged2 = _merge_a_spot(force_em=True)
                if merged2 is not None:
                    merged = merged2
                    if _should_skip_akshare():
                        force_note = "(已忽略 AKShare→Tushare 锁定,单独拉取东财全 A 快照用于涨跌统计)"
                        export_state["force_em_note"] = force_note
            up_n, down_n, flat_n, n_stk = _count_up_down(merged)
            if market_latest is not None and up_n is not None and down_n is not None and n_stk:
                try:
                    _breadth_cache_upsert(market_latest, up_n, down_n, flat_n, n_stk)
                except Exception:
                    pass
            zt_disp.config(text="-" if zt_n is None else str(zt_n))
            dt_disp.config(text="-" if dt_n is None else str(dt_n))
            _apply_up_style(up_n)
            down_disp.config(text="-" if down_n is None else str(down_n))
            n_disp.config(text="-" if not n_stk else f"{n_stk} 只")
            snap_hint = []
            if market_latest and stat_day != market_latest:
                snap_hint.append(
                    f"当前全 A 快照对应最新交易日 {market_latest.isoformat()} 附近行情,统计日为 {stat_day.isoformat()} 的涨跌停以上表为准。"
                )
            if force_note:
                snap_hint.append(force_note.strip("()"))
            _bn = os.path.basename(_breadth_db_path())
            _mls = market_latest.isoformat() if market_latest else "-"
            grid_note = (
                f" 每日涨跌网格(新→旧):优先读本地缓存 {_bn};"
                f"缺失日期自动尝试 Tushare 按交易日补齐;"
                f"最新交易日 {_mls} 仍以本次东财快照为主并写回缓存。"
            )
            note_var.set(
                "全 A 涨跌:东财行情快照合并去重后统计(力争覆盖 5000+);涨跌停为统计日专题池。"
                + grid_note
                + (" " + " ".join(snap_hint) if snap_hint else "")
            )
            if err_parts:
                err_var.set(";".join(err_parts))
            table_rows = []
            for iid in tv.get_children():
                tv.delete(iid)
            tail = sorted([x for x in in_range if x <= today], reverse=True)[:40]
            for td in tail:
                dty = td.strftime("%Y%m%d")
                zn = dn = "-"
                try:
                    zdf = ak.stock_zt_pool_em(date=dty)
                    zn = str(len(zdf)) if zdf is not None else "0"
                except Exception:
                    zn = "?"
                try:
                    ddf = ak.stock_zt_pool_dtgc_em(date=dty)
                    dn = str(len(ddf)) if ddf is not None and not getattr(ddf, "empty", True) else "0"
                except Exception:
                    dn = "·"
                remark = ""
                if td == stat_day:
                    remark = "区间最近交易日"
                if market_latest and td == market_latest:
                    remark = (remark + ";") if remark else ""
                    remark += "可与上方涨跌快照对照"
                tv.insert("", "end", values=(td.isoformat(), zn, dn, remark))
                table_rows.append({"日期": td.isoformat(), "涨停": zn, "跌停": dn, "备注": remark})
            cache_map = _breadth_cache_getmany(in_range)
            missing_days = [d for d in in_range if d.isoformat() not in cache_map]
            if missing_days:
                fetched_map = _fetch_missing_breadth_with_tushare(missing_days)
                if fetched_map:
                    cache_map.update(fetched_map)
            days_rev = sorted(in_range, reverse=True)
            cells = []
            breadth_rows = []
            for td in days_rev:
                up = down = flat = tot = None
                if market_latest and td == market_latest and up_n is not None and down_n is not None:
                    up, down, flat, tot = up_n, down_n, flat_n, n_stk
                else:
                    rec = cache_map.get(td.isoformat())
                    if rec and rec.get("up_n") is not None:
                        up, down, flat = rec["up_n"], rec["down_n"], rec["flat_n"]
                        tot = rec["n_stk"]
                        if tot is None and up is not None:
                            try:
                                tot = int(up) + int(down or 0) + int(flat or 0)
                            except Exception:
                                tot = None
                cells.append({"date": td, "up": up, "down": down, "flat": flat, "total": tot})
                breadth_rows.append(
                    {
                        "日期": td.isoformat(),
                        "上涨": "" if up is None else up,
                        "下跌": "" if down is None else down,
                        "平盘": "" if flat is None else flat,
                        "总计": "" if tot is None else tot,
                    }
                )
            export_state["breadth_daily"] = breadth_rows
            def _apply_breadth_grid():
                try:
                    last_grid_cells["cells"] = cells
                    _render_breadth_grid_rows(cells)
                except Exception:
                    pass
            win.after(0, _apply_breadth_grid)
            export_state["meta"] = {
                "统计日": stat_day.isoformat(),
                "区间": f"{d0.isoformat()}~{d1.isoformat()}",
                "上涨": "" if up_n is None else up_n,
                "下跌": "" if down_n is None else down_n,
                "平盘": "" if flat_n is None else flat_n,
                "涨停": "" if zt_n is None else zt_n,
                "跌停": "" if dt_n is None else dt_n,
                "样本股票数": n_stk,
                "说明": note_var.get(),
            }
            export_state["table"] = table_rows
            try:
                if table_rows:
                    _show_day_analysis(table_rows[0].get("日期", ""))
            except Exception:
                pass
        def _do_refresh():
            refresh_btn.config(state=tk.DISABLED)
            err_var.set("加载中...")
            def work():
                try:
                    _do_refresh_sync()
                except Exception as e:
                    err_var.set(str(e))
                finally:
                    win.after(0, lambda: refresh_btn.config(state=tk.NORMAL))
            threading.Thread(target=work, daemon=True).start()
        refresh_btn.config(command=_do_refresh)
        stats_btn.config(command=_show_breadth_stats_popup)
        try:
            font_spin.configure(
                command=lambda: _render_breadth_grid_rows(last_grid_cells.get("cells") or [])
            )
            font_spin.bind(
                "<KeyRelease>",
                lambda _e: _render_breadth_grid_rows(last_grid_cells.get("cells") or []),
            )
        except Exception:
            pass
        win.after(80, _do_refresh)


    def show_market_sentiment_dialog(self):
        """市场情绪:拉取资金/估值/债息/指数等多维指标,可选 AI 解读。"""
        win = self._safe_toplevel(self.root)
        win.title("市场情绪 · 指标快照")
        win.geometry("1360x920")
        win.transient(self.root)
        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        status_var = tk.StringVar(value="就绪")
        snapshot_holder = [""]
        last_charts_holder = [None]
        chart_scale = [1.18]
        hp_sash_saved = [None]
        chart_panel_max = [False]
        paned = ttk.PanedWindow(win, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        upper = ttk.LabelFrame(
            paned,
            text="指标快照(左侧文字 · 右侧多格图示;竖条调左右宽,右侧工具栏与图示区可上下拖动;双击单个子图可看大图、说明与参考链接;上下拖动调节与 AI 区比例)",
            padding=4,
        )
        lower = ttk.LabelFrame(paned, text="AI 情绪解读(基于上方快照)", padding=4)
        paned.add(upper, weight=4)
        paned.add(lower, weight=2)
        hp = ttk.PanedWindow(upper, orient=tk.HORIZONTAL)
        hp.pack(fill=tk.BOTH, expand=True)
        left_box = ttk.Frame(hp)
        right_outer = ttk.Frame(hp)
        hp.add(left_box, weight=5)
        hp.add(right_outer, weight=4)
        try:
            hp.paneconfigure(left_box, minsize=220)
            hp.paneconfigure(right_outer, minsize=320)
        except Exception:
            pass
        vp_right = ttk.PanedWindow(right_outer, orient=tk.VERTICAL)
        vp_right.pack(fill=tk.BOTH, expand=True)
        chart_tb = ttk.Frame(vp_right)
        right_box = ttk.Frame(vp_right)
        vp_right.add(chart_tb, weight=1)
        vp_right.add(right_box, weight=8)
        try:
            vp_right.paneconfigure(chart_tb, minsize=64)
            vp_right.paneconfigure(right_box, minsize=160)
        except Exception:
            pass
        ttk.Label(
            chart_tb,
            text="指标图示",
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 6))
        snap = scrolledtext.ScrolledText(left_box, wrap=tk.NONE, font=("Consolas", 10))
        snap.pack(fill=tk.BOTH, expand=True)
        fig = None
        canvas = None
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            fig = Figure(figsize=(8.0, 12.0), dpi=100)
            canvas = FigureCanvasTkAgg(fig, master=right_box)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            import time as _time
            _last_chart_click = [0.0, None]
            def _on_chart_press(event):
                ax = event.inaxes
                if ax is None:
                    return
                spec = getattr(ax, "_sentiment_chart_spec", None)
                if not isinstance(spec, dict) or not spec:
                    return
                t = _time.time()
                dbl = bool(getattr(event, "dblclick", False))
                if not dbl:
                    if _last_chart_click[1] is ax and (t - _last_chart_click[0]) < 0.45:
                        dbl = True
                    else:
                        _last_chart_click[0] = t
                        _last_chart_click[1] = ax
                if not dbl:
                    return
                _last_chart_click[0] = 0.0
                _last_chart_click[1] = None
                self._show_market_sentiment_chart_popup(win, spec)
            canvas.mpl_connect("button_press_event", _on_chart_press)
        except Exception as ex:
            ttk.Label(right_box, text=f"无法加载图示(需 matplotlib):{ex}", wraplength=280).pack(
                expand=True, padx=6, pady=12
            )
        def _draw_charts(items):
            last_charts_holder[0] = items
            if fig is None or canvas is None:
                return
            try:
                self._apply_market_sentiment_charts(fig, items or [], scale=chart_scale[0])
                canvas.draw()
            except Exception as e:
                fig.clear()
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, f"绘图异常:{e}", ha="center", va="center", transform=ax.transAxes, fontsize=9)
                ax.set_axis_off()
                canvas.draw()
        def _redraw_last_charts():
            items = last_charts_holder[0]
            if items is not None:
                _draw_charts(items)
        def _zoom_chart(delta):
            chart_scale[0] = max(0.7, min(2.2, chart_scale[0] + delta))
            _redraw_last_charts()
        max_btn = ttk.Button(chart_tb, text="图示最大化", width=11)
        def _toggle_chart_panel_max():
            try:
                if not chart_panel_max[0]:
                    hp_sash_saved[0] = hp.sashpos(0)
                    try:
                        hp.paneconfigure(left_box, minsize=0)
                    except Exception:
                        pass
                    hp.sashpos(0, 0)
                    chart_panel_max[0] = True
                    max_btn.config(text="图示还原")
                else:
                    try:
                        hp.paneconfigure(left_box, minsize=220)
                    except Exception:
                        pass
                    pos = hp_sash_saved[0]
                    if pos is None or pos < 12:
                        pos = max(300, int(win.winfo_width() * 0.4))
                    hp.sashpos(0, pos)
                    chart_panel_max[0] = False
                    max_btn.config(text="图示最大化")
                _redraw_last_charts()
            except Exception:
                pass
        max_btn.config(command=_toggle_chart_panel_max)
        max_btn.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(chart_tb, text="放大图示", width=9, command=lambda: _zoom_chart(0.14)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(chart_tb, text="缩小图示", width=9, command=lambda: _zoom_chart(-0.14)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(
            chart_tb,
            text="(左侧与图示间竖条调宽;工具栏与图示区间横条调上下;双击子图看大图与链接)",
            font=("TkDefaultFont", 8),
            foreground="#555",
        ).pack(side=tk.LEFT, padx=(8, 0))
        def _init_vertical_sash():
            try:
                win.update_idletasks()
                h = max(400, paned.winfo_height())
                paned.sashpos(0, int(h * 0.62))
            except Exception:
                pass
        def _init_right_vp_sash():
            try:
                win.update_idletasks()
                rh = max(120, right_outer.winfo_height())
                vp_right.sashpos(0, min(140, max(72, int(rh * 0.11))))
            except Exception:
                pass
        def _init_all_sashes():
            _init_vertical_sash()
            _init_right_vp_sash()
        win.after(120, _init_all_sashes)
        ai_out = scrolledtext.ScrolledText(lower, wrap=tk.WORD, font=("Microsoft YaHei", 12))
        ai_out.pack(fill=tk.BOTH, expand=True)
        def _refresh():
            status_var.set("正在拉取指标...")
            snap.delete("1.0", tk.END)
            snap.insert("1.0", "加载中,请稍候...")
            def work():
                try:
                    text, charts = self._collect_market_sentiment_snapshot_bundle()
                    snapshot_holder[0] = text
                    def done():
                        snap.delete("1.0", tk.END)
                        snap.insert("1.0", text)
                        _draw_charts(charts)
                        status_var.set("快照已更新 " + datetime.now().strftime("%H:%M:%S"))
                    win.after(0, done)
                except Exception as e:
                    def err(e=e):
                        snap.delete("1.0", tk.END)
                        snap.insert("1.0", f"汇总失败:{e}")
                        _draw_charts([])
                        status_var.set("失败")
                    win.after(0, err)
            threading.Thread(target=work, daemon=True).start()
        def _ai():
            body = snapshot_holder[0].strip() or snap.get("1.0", tk.END).strip()
            if not body or body.startswith("加载中"):
                messagebox.showwarning("提示", "请先点击「刷新快照」成功拉取指标后再分析。", parent=win)
                return
            ai_out.delete("1.0", tk.END)
            ai_out.insert("1.0", "AI 分析中,请稍候...\n")
            status_var.set("AI 分析中...")
            def run_ai():
                try:
                    sys_p = (
                        "你是资深 A 股市场策略分析师,熟悉资金面、估值、利率、汇率与境内外同业拆借利率。"
                        "根据用户给出的指标快照,用中文分条输出:"
                        "(1)整体情绪倾向:偏乐观/中性/偏谨慎及依据;"
                        "(2)大资金与主力动向、北向资金等要点;"
                        "(3)SHIBOR、SIBOR/HIBOR/Libor 等若出现,简述对跨境融资成本与风险偏好的含义;"
                        "(4)人民币汇率中间价节选对外资与流动性的可能影响;"
                        "(5)估值与指数位置简述;"
                        "(6)国债/美债与股债性价比的简要含义;"
                        "(7)若快照含「扩展指标」中的美股 ETF(如 SPY/QQQ/GLD/USO/VXX 等):简述其对全球风险偏好、"
                        "美元、商品与恐慌情绪的指示意义(均为代理,非 A 股直接标的);"
                        "(8)若含中美宏观(LPR、CPI、PMI、M2、非农等):择要点评对利率预期与外溢影响;"
                        "(9)若含全球地产与航运(京沪房价、美加地产指标、BDI、ITB 等):可对照库兹涅茨/库存/贸易热度作简述,避免机械套用「周金涛周期」结论;"
                        "(10)若快照含「五角大楼披萨指数(PZZA 代理)」:说明其为非官方情绪参照、勿过度解读;"
                        "(11)若含 Polymarket:简述预测概率作为风险偏好奇观指标的局限;"
                        "(12)短线风险提示。"
                        "声明:不构成投资建议。"
                    )
                    prompt = "以下为当前采集的市场指标快照,请分析:\n\n" + body
                    result = self.call_ai_model(prompt, sys_p)
                    win.after(
                        0,
                        lambda: (
                            ai_out.delete("1.0", tk.END),
                            ai_out.insert("1.0", result or "(无返回)"),
                            status_var.set("AI 解读完成"),
                        ),
                    )
                except Exception as e:
                    win.after(
                        0,
                        lambda e=e: (
                            ai_out.delete("1.0", tk.END),
                            ai_out.insert("1.0", f"AI 调用失败:{e}"),
                            status_var.set("AI 失败"),
                        ),
                    )
            threading.Thread(target=run_ai, daemon=True).start()
        ttk.Button(top, text="刷新快照", command=_refresh, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="AI 情绪解读", command=_ai, width=14).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(top, textvariable=status_var, font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
        _refresh()


    def _a_share_limit_up_threshold_pct(self, stock_code):
        """从日涨跌幅近似判断涨停:创业板/科创板约20%,其余主板约10%(略低于板幅以减少舍入误杀)。"""
        c = str(stock_code).strip().zfill(6)
        if not c.isdigit():
            return 9.85
        if c.startswith(('300', '301', '688', '689')):
            return 19.5
        # 北交所常见前缀,约30%
        if c.startswith(('8', '43', '83', '87', '92')):
            return 28.5
        return 9.85


    def _limit_up_pct_threshold(self, code6: str, stock_name: str = ""):
        """返回该股涨跌幅%达到时视为涨停的判定阈值(略低于板幅以容误差)。"""
        c = (code6 or "").strip()
        c6 = c[-6:].zfill(6) if c else ""
        name = (stock_name or "") or ""
        if name and re.match(r"^\*?ST", name):
            return 4.85
        if c6.startswith(("300", "301", "688")):
            return 19.5
        if c6.startswith(("8", "92")):
            return 29.0
        return 9.75


    def _get_market_sentiment_score(self):
        """获取大盘情绪指数(主界面总分)"""
        try:
            # 从主界面的total_score_var获取
            if hasattr(self, 'total_score_var'):
                score_text = self.total_score_var.get().replace("总分: ", "").strip()
                score = int(score_text) if score_text.isdigit() else 0
                return score
            return 0
        except:
            return 0


    def _get_market_limit_data(self):
        """获取A股涨跌板数据
        Returns:
            dict: 包含涨跌板数量、开板股票等信息
        """
        try:
            import akshare as ak
            market_data = {
                'up_count': 0,  # 涨停板数量
                'down_count': 0,  # 跌停板数量
                'up_opened': [],  # 涨停板开板股票列表
                'down_opened': [],  # 跌停板开板股票列表
                'up_limit_stocks': [],  # 所有涨停股票
                'down_limit_stocks': []  # 所有跌停股票
            }
            # 获取实时行情数据
            spot_data = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
            if spot_data.empty:
                return market_data
            # 筛选涨停板(涨跌幅 >= 9.8%,考虑ST股票)
            up_limit = spot_data[
                (spot_data['涨跌幅'] >= 9.8) |
                ((spot_data['涨跌幅'] >= 4.8) & (spot_data['名称'].str.contains('ST', na=False)))
            ]
            # 筛选跌停板(涨跌幅 <= -9.8%,考虑ST股票)
            down_limit = spot_data[
                (spot_data['涨跌幅'] <= -9.8) |
                ((spot_data['涨跌幅'] <= -4.8) & (spot_data['名称'].str.contains('ST', na=False)))
            ]
            market_data['up_count'] = len(up_limit)
            market_data['down_count'] = len(down_limit)
            # 获取涨停板股票列表
            if not up_limit.empty:
                for _, row in up_limit.iterrows():
                    stock_name = row.get('名称', '')
                    stock_code = row.get('代码', '')
                    change_pct = row.get('涨跌幅', 0)
                    market_data['up_limit_stocks'].append({
                        'name': stock_name,
                        'code': stock_code,
                        'change_pct': round(change_pct, 2)
                    })
            # 获取跌停板股票列表
            if not down_limit.empty:
                for _, row in down_limit.iterrows():
                    stock_name = row.get('名称', '')
                    stock_code = row.get('代码', '')
                    change_pct = row.get('涨跌幅', 0)
                    market_data['down_limit_stocks'].append({
                        'name': stock_name,
                        'code': stock_code,
                        'change_pct': round(change_pct, 2)
                    })
            # 判断开板(涨停板但当前价不等于最高价,或跌停板但当前价不等于最低价)
            for _, row in up_limit.iterrows():
                current_price = row.get('最新价', 0)
                high_price = row.get('最高', current_price)
                # 如果当前价低于最高价,说明开板了
                if current_price < high_price * 0.99:  # 允许0.01的误差
                    stock_name = row.get('名称', '')
                    stock_code = row.get('代码', '')
                    market_data['up_opened'].append({
                        'name': stock_name,
                        'code': stock_code,
                        'current_price': current_price,
                        'high_price': high_price
                    })
            for _, row in down_limit.iterrows():
                current_price = row.get('最新价', 0)
                low_price = row.get('最低', current_price)
                # 如果当前价高于最低价,说明开板了
                if current_price > low_price * 1.01:  # 允许0.01的误差
                    stock_name = row.get('名称', '')
                    stock_code = row.get('代码', '')
                    market_data['down_opened'].append({
                        'name': stock_name,
                        'code': stock_code,
                        'current_price': current_price,
                        'low_price': low_price
                    })
            return market_data
        except Exception as e:
            print(f"获取涨跌板数据失败: {e}")
            return {
                'up_count': 0,
                'down_count': 0,
                'up_opened': [],
                'down_opened': [],
                'up_limit_stocks': [],
                'down_limit_stocks': []
            }


    def _emotion_cycle_changed_for_lock(self):
        """情绪周期变更:若与上次不同则清除密码临时解锁;同步锁屏层。"""
        var = getattr(self, 'emotion_cycle_var', None)
        if not var:
            return
        cur = var.get()
        prev = getattr(self, '_emotion_lock_prev_cycle', None)
        if prev is not None and cur != prev:
            self._emotion_lock_suppressed = False
        self._emotion_lock_prev_cycle = cur
        self._sync_emotion_lock_overlay()


    def _sync_emotion_lock_overlay(self):
        """下行且未密码绕过时显示全屏锁,否则隐藏。"""
        try:
            var = getattr(self, 'emotion_cycle_var', None)
            if not var:
                self._emotion_lock_hide_overlay()
                return
            need_lock = (var.get() == "下行") and not getattr(self, '_emotion_lock_suppressed', False)
            if need_lock:
                self._emotion_lock_show_overlay()
            else:
                self._emotion_lock_hide_overlay()
        except Exception as e:
            print(f"情绪锁屏同步失败: {e}")


    def _emotion_lock_hide_overlay(self):
        ov = getattr(self, '_emotion_lock_overlay', None)
        if ov is not None:
            try:
                ov.place_forget()
            except Exception:
                pass


    def _emotion_lock_show_overlay(self):
        if getattr(self, '_emotion_lock_overlay', None) is None:
            self._emotion_lock_build_overlay()
        try:
            self._emotion_lock_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._emotion_lock_overlay.lift()
        except Exception:
            pass


    def _emotion_lock_build_overlay(self):
        ov = tk.Frame(self.root, bg='#6b2a2a', highlightthickness=0)
        inner = tk.Frame(ov, bg='#6b2a2a')
        inner.place(relx=0.5, rely=0.42, anchor='center')
        title = tk.Label(
            inner,
            text='情绪周期:下行(红灯闪烁)',
            fg='white', bg='#6b2a2a',
            font=('Microsoft YaHei', 18, 'bold'),
        )
        title.pack(pady=(0, 6))
        hint = tk.Label(
            inner,
            text='界面已锁定。\n点击本区域:输入解锁密码,或改为「上行 / 震荡」',
            fg='#ffe0e0', bg='#6b2a2a',
            font=('Microsoft YaHei', 12),
            justify='center',
        )
        hint.pack(pady=(0, 14))
        def click_any(_ev=None):
            self._emotion_lock_open_unlock_dialog()
        for w in (ov, inner, title, hint):
            w.bind('<Button-1>', click_any)
        bar = tk.Frame(inner, bg='#6b2a2a')
        bar.pack()
        tk.Button(
            bar, text='设置解锁密码',
            command=lambda: self._emotion_lock_open_password_dialog(self.root),
            font=('Microsoft YaHei', 10),
            bg='#8b4040', fg='white', activebackground='#a05050',
        ).pack(side=tk.LEFT, padx=6)
        self._emotion_lock_overlay = ov


    def _emotion_lock_open_password_dialog(self, parent=None):
        """设置/修改情绪下行解锁密码(存入 ai_config.json)"""
        win = self._toplevel(parent or self.root)
        win.title('情绪下行 - 解锁密码设置')
        win.geometry('420x200')
        win.transient(self.root)
        f = ttk.Frame(win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text='新密码:', font=('Microsoft YaHei', 10)).grid(row=0, column=0, sticky='w', pady=4)
        e1 = ttk.Entry(f, width=28, show='*')
        e1.grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Label(f, text='确认密码:', font=('Microsoft YaHei', 10)).grid(row=1, column=0, sticky='w', pady=4)
        e2 = ttk.Entry(f, width=28, show='*')
        e2.grid(row=1, column=1, sticky='ew', pady=4)
        ttk.Label(
            f,
            text='保存后,在「下行」锁屏界面可凭此密码暂时解锁。\n留空并保存则清除密码(仅能通过改为上行/震荡解锁)。',
            font=('Microsoft YaHei', 9),
        ).grid(row=2, column=0, columnspan=2, sticky='w', pady=10)
        f.columnconfigure(1, weight=1)
        def save_pwd():
            a, b = e1.get(), e2.get()
            if a != b:
                messagebox.showerror('错误', '两次密码不一致', parent=win)
                return
            self.ai_config_manager.config['emotion_down_lock_password'] = a.strip()
            self.ai_config_manager.save_config()
            messagebox.showinfo('成功', '解锁密码已保存', parent=win)
            win.destroy()
        bf = ttk.Frame(f)
        bf.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(bf, text='保存', command=save_pwd).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text='关闭', command=win.destroy).pack(side=tk.LEFT, padx=4)


    def _emotion_lock_open_unlock_dialog(self):
        dlg = self._safe_toplevel(self.root)
        dlg.title('解除情绪下行锁屏')
        dlg.geometry('440x260')
        dlg.transient(self.root)
        dlg.resizable(False, False)
        dlg.attributes('-topmost', True)
        frm = ttk.Frame(dlg, padding=14)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text='解锁方式(任选其一)', font=('Microsoft YaHei', 11, 'bold')).pack(anchor='w')
        ttk.Label(
            frm,
            text='方式一:将情绪周期改为非下行(关灯)',
            font=('Microsoft YaHei', 10),
        ).pack(anchor='w', pady=(10, 2))
        cy = ttk.Frame(frm)
        cy.pack(fill=tk.X, pady=4)
        ttk.Label(cy, text='情绪周期:').pack(side=tk.LEFT)
        unlock_cycle_var = tk.StringVar(
            value=self.emotion_cycle_var.get() if hasattr(self, 'emotion_cycle_var') else '下行'
        )
        unlock_combo = ttk.Combobox(
            cy, textvariable=unlock_cycle_var,
            values=['上行', '震荡', '下行'], state='readonly', width=10,
        )
        unlock_combo.pack(side=tk.LEFT, padx=6)
        ttk.Label(frm, text='方式二:输入已保存的解锁密码', font=('Microsoft YaHei', 10)).pack(anchor='w', pady=(12, 2))
        pe = ttk.Frame(frm)
        pe.pack(fill=tk.X, pady=4)
        ttk.Label(pe, text='密码:').pack(side=tk.LEFT)
        pwd_ent = ttk.Entry(pe, width=26, show='*')
        pwd_ent.pack(side=tk.LEFT, padx=6)
        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X, pady=16)
        def try_unlock():
            saved = self.ai_config_manager.config.get('emotion_down_lock_password', '') or ''
            new_cycle = unlock_cycle_var.get()
            if new_cycle in ('上行', '震荡'):
                if hasattr(self, 'emotion_cycle_var'):
                    self.emotion_cycle_var.set(new_cycle)
                dlg.destroy()
                return
            typed = pwd_ent.get().strip()
            if not typed:
                messagebox.showwarning(
                    '提示',
                    '当前仍为「下行」。请改为「上行」或「震荡」,或输入解锁密码。',
                    parent=dlg,
                )
                return
            if not saved:
                messagebox.showwarning(
                    '提示',
                    '尚未设置解锁密码。\n请改为「上行」或「震荡」,或先通过锁屏上的「设置解锁密码」保存密码。',
                    parent=dlg,
                )
                return
            if typed == saved:
                self._emotion_lock_suppressed = True
                self._emotion_lock_hide_overlay()
                dlg.destroy()
                messagebox.showinfo(
                    '已解锁',
                    '密码验证通过。界面已可操作。\n若再次切换情绪周期,将按新周期重新判断是否锁屏。',
                    parent=self.root,
                )
                return
            messagebox.showerror('错误', '密码错误', parent=dlg)
        ttk.Button(btn_row, text='解锁', command=try_unlock).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            btn_row, text='设置密码...',
            command=lambda: self._emotion_lock_open_password_dialog(dlg),
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text='取消', command=dlg.destroy).pack(side=tk.LEFT, padx=4)
        dlg.grab_set()
        dlg.focus_force()
        pwd_ent.focus_set()


    def _on_sector_sentiment_toggle(self):
        """持仓情绪监测开关切换"""
        self.sector_sentiment_monitor_enabled = self.sector_sentiment_var.get()
        if self.sector_sentiment_monitor_enabled:
            print("[持仓情绪监测] 已开启")
            self._start_sector_sentiment_monitor()
        else:
            print("[持仓情绪监测] 已关闭")
            self._stop_sector_sentiment_monitor()


    def _start_sector_sentiment_monitor(self):
        """启动持仓情绪监测"""
        if self.sector_sentiment_monitor_running:
            return
        self.sector_sentiment_monitor_running = True
        def monitor_loop():
            while self.sector_sentiment_monitor_running:
                try:
                    if self.sector_sentiment_monitor_enabled:
                        self._update_sector_sentiment_monitor()
                except Exception as e:
                    print(f"持仓情绪监测错误: {e}")
                # 等待5分钟(300秒)
                for _ in range(300):
                    if not self.sector_sentiment_monitor_running:
                        break
                    time.sleep(1)
        self.sector_sentiment_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.sector_sentiment_monitor_thread.start()
        print("[持仓情绪监测] 监测已启动,每5分钟刷新一次")


    def _stop_sector_sentiment_monitor(self):
        """停止持仓情绪监测"""
        self.sector_sentiment_monitor_running = False
        print("[持仓情绪监测] 监测已停止")


    def _show_sector_sentiment_monitor(self):
        """显示持仓情绪监测窗口(30个板块K线图)"""
        # 点击"查看"按钮时,更新持仓1-8(group_index 7-14)的股票数据
        self._update_holdings_1_to_8()
        # 获取同花顺涨幅最大前16板块,持仓1-8各在股票最下面显示2个板块名
        self._fetch_and_show_top16_sectors()
        # 如果窗口已存在,则显示并刷新
        if self.sector_sentiment_window is not None:
            try:
                self.sector_sentiment_window.deiconify()
                self.sector_sentiment_window.lift()
                self._update_sector_sentiment_monitor()
                return
            except:
                # 窗口已销毁,重新创建
                self.sector_sentiment_window = None
        # 创建新窗口
        monitor_window = self._safe_toplevel(self.root)
        monitor_window.title("持仓情绪监测 - 同花顺板块15分钟K线")
        monitor_window.geometry("1600x1000")
        self.sector_sentiment_window = monitor_window
        # 主框架
        main_frame = ttk.Frame(monitor_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 标题和刷新按钮
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        # 获取上次更新日期
        last_update = self.ai_config_manager.config.get("sector_index_last_update", "未知")
        ttk.Label(header_frame, text=f"同花顺板块15分钟K线监测(每5分钟自动刷新,板块更新: {last_update})",
                 font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
        refresh_btn = ttk.Button(header_frame, text="立即刷新",
                                command=lambda: self._update_sector_sentiment_monitor())
        refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))
        # 添加刷新板块列表按钮(获取当天最新强势板块)
        def refresh_sector_list():
            success, msg = self._refresh_sector_index_list()
            if success:
                messagebox.showinfo("成功", msg)
                # 关闭当前窗口,重新打开以显示新板块
                monitor_window.destroy()
                self._show_sector_sentiment_monitor()
            else:
                messagebox.showerror("错误", msg)
        refresh_sector_btn = ttk.Button(header_frame, text="刷新板块列表",
                                       command=refresh_sector_list)
        refresh_sector_btn.pack(side=tk.RIGHT, padx=(10, 0))
        # 添加自动导入龙头股按钮
        auto_import_btn = ttk.Button(header_frame, text="自动导入龙头股到持仓标签",
                                    command=lambda: self._auto_import_leader_stocks())
        auto_import_btn.pack(side=tk.RIGHT, padx=(10, 0))
        # 滚动框架(容纳30个K线图:3列x10行)
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
        def create_chart_frame(row, col, sector_name, sector_type="概念"):
            """创建单个板块K线图框架(包含K线图和龙头股列表)"""
            chart_frame = ttk.LabelFrame(scrollable_frame, text=sector_name, padding=5)
            chart_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            # 绑定双击事件,弹出详情窗口
            def on_double_click(event):
                self._show_sector_detail_popup(sector_name, sector_type)
            chart_frame.bind("<Double-Button-1>", on_double_click)
            # 也绑定到内容框架,确保双击任何地方都能触发
            content_frame = ttk.Frame(chart_frame)
            content_frame.pack(fill=tk.BOTH, expand=True)
            content_frame.bind("<Double-Button-1>", on_double_click)
            # 左侧:K线图
            kline_frame = ttk.Frame(content_frame)
            kline_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            # 右侧:龙头股列表
            leader_stocks_frame = ttk.LabelFrame(content_frame, text="龙头股", padding=3)
            leader_stocks_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(5, 0))
            # 创建龙头股列表(使用Text widget,支持滚动)
            leader_stocks_text = tk.Text(leader_stocks_frame, width=18, height=10,
                                        font=("TkDefaultFont", 7), wrap=tk.WORD)
            leader_stocks_scrollbar = ttk.Scrollbar(leader_stocks_frame, orient=tk.VERTICAL,
                                                   command=leader_stocks_text.yview)
            leader_stocks_text.configure(yscrollcommand=leader_stocks_scrollbar.set)
            leader_stocks_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            leader_stocks_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            leader_stocks_text.insert("1.0", "加载中...")
            leader_stocks_text.config(state=tk.DISABLED)  # 只读
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                from matplotlib.figure import Figure
                fig = Figure(figsize=(5, 3), dpi=80)
                ax = fig.add_subplot(111)
                canvas_widget = FigureCanvasTkAgg(fig, kline_frame)
                canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                # 显示加载中
                ax.text(0.5, 0.5, "加载中...", ha='center', va='center',
                       transform=ax.transAxes, fontsize=10)
                canvas_widget.draw()
                chart_widgets.append({
                    'sector_name': sector_name,
                    'sector_type': sector_type,
                    'fig': fig,
                    'ax': ax,
                    'canvas': canvas_widget,
                    'leader_stocks_text': leader_stocks_text  # 添加龙头股文本组件
                })
                # 为K线图组件也绑定双击事件
                canvas_widget.get_tk_widget().bind("<Double-Button-1>", on_double_click)
            except ImportError:
                error_label = tk.Label(kline_frame, text="matplotlib未安装",
                                     font=("TkDefaultFont", 11), fg="red")
                error_label.pack(fill=tk.BOTH, expand=True)
                # 为错误标签也绑定双击事件
                error_label.bind("<Double-Button-1>", on_double_click)
        # 获取板块列表(从下拉框中的板块指数列表)
        try:
            # 使用下拉框中的板块指数列表
            all_sectors = []
            for sector_name in self.sector_index_list:
                # 判断是概念板块还是行业板块
                sector_type = "概念"  # 默认
                try:
                    import akshare as ak
                    concept_df = safe_call(ak.stock_board_concept_name_em, fallback=pd.DataFrame(), label="ak.stock_board_concept_name_em")
                    if not concept_df.empty and sector_name in concept_df['板块名称'].tolist():
                        sector_type = "概念"
                    else:
                        industry_df = safe_call(ak.stock_board_industry_name_em, fallback=pd.DataFrame(), label="ak.stock_board_industry_name_em")
                        if not industry_df.empty and sector_name in industry_df['板块名称'].tolist():
                            sector_type = "行业"
                except:
                    pass
                all_sectors.append((sector_name, sector_type))
            # 创建K线图框架(3列,行数根据板块数量自动调整)
            for idx, (sector_name, sector_type) in enumerate(all_sectors):
                row = idx // cols
                col = idx % cols
                create_chart_frame(row, col, sector_name, sector_type)
        except Exception as e:
            print(f"获取板块列表失败: {e}")
            error_label = tk.Label(scrollable_frame, text=f"获取板块列表失败: {e}",
                                 font=("TkDefaultFont", 12), fg="red")
            error_label.grid(row=0, column=0, columnspan=3, padx=10, pady=10)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 存储图表组件到窗口对象
        monitor_window.chart_widgets = chart_widgets
        # 初始加载数据
        self._update_sector_sentiment_monitor()
        # 窗口关闭事件
        def on_closing():
            self.sector_sentiment_window = None
            monitor_window.destroy()
        monitor_window.protocol("WM_DELETE_WINDOW", on_closing)


    def _update_sector_sentiment_monitor(self):
        """更新持仓情绪监测窗口的K线图"""
        if self.sector_sentiment_window is None:
            return
        try:
            chart_widgets = getattr(self.sector_sentiment_window, 'chart_widgets', [])
            if not chart_widgets:
                return
            import akshare as ak
            import numpy as np
            import pandas as pd
            def update_chart(chart_info):
                """更新单个图表"""
                try:
                    sector_name = chart_info['sector_name']
                    sector_type = chart_info['sector_type']
                    ax = chart_info['ax']
                    fig = chart_info['fig']
                    canvas = chart_info['canvas']
                    # 清空图表
                    ax.clear()
                    # 获取板块15分钟K线数据
                    # 使用板块成分股的平均值
                    kline_data = None
                    leader_stocks_list = []  # 存储龙头股列表
                    try:
                        # 获取板块成分股(akshare已移除同花顺接口,使用东方财富接口,带重试机制)
                        stock_list = None
                        max_retries = 3
                        # 使用东方财富接口(同花顺 stock_board_concept_cons_ths/industry_cons_ths 已从akshare移除)
                        if stock_list is None or stock_list.empty:
                            for retry in range(max_retries):
                                try:
                                    time.sleep(0.5 * (retry + 1))  # 稍长延迟避免请求过快
                                    if sector_type == "概念":
                                        stock_list = ak.stock_board_concept_cons_em(symbol=sector_name)
                                    else:
                                        stock_list = ak.stock_board_industry_cons_em(symbol=sector_name)
                                    if stock_list is not None and not stock_list.empty:
                                        print(f"东方财富接口获取 {sector_name} 成功")
                                        break
                                except Exception as retry_e:
                                    print(f"东方财富接口获取 {sector_name} 失败(重试 {retry+1}/{max_retries}): {retry_e}")
                                    if retry == max_retries - 1:
                                        # 最后一轮失败后,尝试另一类型接口(板块名称可能在不同分类)
                                        try:
                                            time.sleep(0.5)
                                            if sector_type == "概念":
                                                stock_list = ak.stock_board_industry_cons_em(symbol=sector_name)
                                            else:
                                                stock_list = ak.stock_board_concept_cons_em(symbol=sector_name)
                                            if stock_list is not None and not stock_list.empty:
                                                print(f"东方财富备用接口获取 {sector_name} 成功")
                                        except Exception as fallback_e:
                                            print(f"东方财富备用接口获取 {sector_name} 失败: {fallback_e}")
                                    continue
                        if stock_list is not None and not stock_list.empty:
                            # 获取龙头股前10(按涨跌幅排序,取前10)
                            try:
                                # 获取名称和代码列
                                name_col = None
                                code_col = None
                                pct_col = None
                                for col in stock_list.columns:
                                    col_str = str(col).lower()
                                    if name_col is None and ('名称' in str(col) or 'name' in col_str):
                                        name_col = col
                                    if code_col is None and ('代码' in str(col) or 'code' in col_str):
                                        code_col = col
                                    if pct_col is None and ('涨跌幅' in str(col) or 'pct' in col_str or 'change' in col_str):
                                        pct_col = col
                                if name_col and code_col:
                                    # 按涨跌幅排序(如果有涨跌幅列)
                                    if pct_col:
                                        sorted_stocks = stock_list.sort_values(pct_col, ascending=False)
                                    else:
                                        sorted_stocks = stock_list
                                    # 取前10只股票
                                    for idx, (_, row) in enumerate(sorted_stocks.head(10).iterrows()):
                                        stock_name = str(row.get(name_col, '')).strip()
                                        stock_code = str(row.get(code_col, '')).strip()
                                        if stock_name and stock_code:
                                            pct_str = ""
                                            if pct_col:
                                                try:
                                                    pct_val = float(row.get(pct_col, 0))
                                                    pct_str = f" {pct_val:+.2f}%"
                                                except:
                                                    pass
                                            leader_stocks_list.append(f"{idx+1}. {stock_name}({stock_code}){pct_str}")
                            except Exception as e:
                                print(f"获取板块 {sector_name} 龙头股失败: {e}")
                                leader_stocks_list = ["获取失败"]
                        if stock_list is not None and not stock_list.empty:
                            # 获取成分股代码列
                            code_col = None
                            for col in ['代码', 'code', '股票代码']:
                                if col in stock_list.columns:
                                    code_col = col
                                    break
                            if code_col:
                                # 取前5只成分股的平均值
                                codes = stock_list[code_col].head(5).tolist()
                                all_closes = []
                                all_times = []
                                for code in codes:
                                    try:
                                        # 获取15分钟K线数据(带重试机制)
                                        stock_kline = None
                                        for kline_retry in range(2):
                                            try:
                                                time.sleep(0.3 * (kline_retry + 1))  # 延迟避免频繁请求
                                                stock_kline = ak.stock_zh_a_hist_min_em(symbol=str(code).zfill(6), period="15", adjust="")
                                                if stock_kline is not None and not stock_kline.empty:
                                                    break
                                            except Exception:
                                                if kline_retry == 1:
                                                    raise
                                                continue
                                        if stock_kline is not None and not stock_kline.empty:
                                            # 获取收盘价列和时间列
                                            close_col = None
                                            time_col = None
                                            for col in stock_kline.columns:
                                                col_str = str(col).lower()
                                                if close_col is None and ('收盘' in str(col) or 'close' in col_str):
                                                    close_col = col
                                                if time_col is None and ('时间' in str(col) or 'time' in col_str or 'date' in str(col)):
                                                    time_col = col
                                            if close_col:
                                                closes = stock_kline[close_col].astype(float).tolist()
                                                times = stock_kline[time_col].tolist() if time_col else range(len(closes))
                                                if len(closes) > 0:
                                                    all_closes.append(closes)
                                                    if not all_times:
                                                        all_times = times
                                    except Exception as e:
                                        print(f"获取 {code} 15分钟K线失败: {e}")
                                        continue
                                if all_closes:
                                    # 计算平均值
                                    max_len = max(len(c) for c in all_closes)
                                    avg_closes = []
                                    for i in range(max_len):
                                        values = [c[i] for c in all_closes if i < len(c)]
                                        if values:
                                            avg_closes.append(np.mean(values))
                                    if avg_closes:
                                        kline_data = pd.DataFrame({
                                            '时间': all_times[:len(avg_closes)],
                                            '收盘': avg_closes
                                        })
                    except Exception as e:
                        print(f"获取板块 {sector_name} 成分股数据失败: {e}")
                    # 绘制K线图
                    if kline_data is not None and not kline_data.empty:
                        # 获取收盘价和时间
                        close_col = None
                        time_col = None
                        for col in kline_data.columns:
                            col_str = str(col).lower()
                            if close_col is None and ('收盘' in str(col) or 'close' in col_str):
                                close_col = col
                            if time_col is None and ('时间' in str(col) or 'time' in col_str or 'date' in col_str):
                                time_col = col
                        if close_col:
                            closes = kline_data[close_col].astype(float).tolist()
                            times = kline_data[time_col].tolist() if time_col else range(len(closes))
                            # 计算均线(15分钟K线:1日=16根,5日=80根,10日=160根,20日=320根)
                            periods = {
                                'ma1': 16,   # 1日 = 16根15分钟K线
                                'ma5': 80,   # 5日 = 80根15分钟K线
                                'ma10': 160, # 10日 = 160根15分钟K线
                                'ma20': 320  # 20日 = 320根15分钟K线
                            }
                            ma1_values = []
                            ma5_values = []
                            ma10_values = []
                            ma20_values = []
                            for i in range(len(closes)):
                                # MA1
                                if i >= periods['ma1'] - 1:
                                    ma1_values.append(sum(closes[i-periods['ma1']+1:i+1]) / periods['ma1'])
                                else:
                                    ma1_values.append(None)
                                # MA5
                                if i >= periods['ma5'] - 1:
                                    ma5_values.append(sum(closes[i-periods['ma5']+1:i+1]) / periods['ma5'])
                                else:
                                    ma5_values.append(None)
                                # MA10
                                if i >= periods['ma10'] - 1:
                                    ma10_values.append(sum(closes[i-periods['ma10']+1:i+1]) / periods['ma10'])
                                else:
                                    ma10_values.append(None)
                                # MA20
                                if i >= periods['ma20'] - 1:
                                    ma20_values.append(sum(closes[i-periods['ma20']+1:i+1]) / periods['ma20'])
                                else:
                                    ma20_values.append(None)
                            # 绘制K线(简化为收盘价折线)
                            ax.plot(times, closes, 'b-', linewidth=1, label=sector_name, alpha=0.8)
                            # 绘制均线
                            if any(v is not None for v in ma1_values):
                                ma1_plot = [v if v is not None else closes[i] for i, v in enumerate(ma1_values)]
                                ax.plot(times, ma1_plot, 'r--', linewidth=0.8, label='MA1', alpha=0.6)
                            if any(v is not None for v in ma5_values):
                                ma5_plot = [v if v is not None else closes[i] for i, v in enumerate(ma5_values)]
                                ax.plot(times, ma5_plot, 'orange', linewidth=0.8, label='MA5', alpha=0.6)
                            if any(v is not None for v in ma10_values):
                                ma10_plot = [v if v is not None else closes[i] for i, v in enumerate(ma10_values)]
                                ax.plot(times, ma10_plot, 'green', linewidth=0.8, label='MA10', alpha=0.6)
                            if any(v is not None for v in ma20_values):
                                ma20_plot = [v if v is not None else closes[i] for i, v in enumerate(ma20_values)]
                                ax.plot(times, ma20_plot, 'purple', linewidth=0.8, label='MA20', alpha=0.6)
                            ax.set_title(sector_name, fontsize=8, fontweight='bold')
                            ax.set_xlabel('时间', fontsize=6)
                            ax.set_ylabel('价格', fontsize=6)
                            ax.legend(loc='upper left', fontsize=5)
                            ax.grid(True, alpha=0.3)
                            # 旋转日期标签
                            import matplotlib.pyplot as plt
                            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=5)
                            fig.tight_layout()
                            canvas.draw()
                            # 更新龙头股列表显示
                            try:
                                leader_stocks_text = chart_info.get('leader_stocks_text')
                                if leader_stocks_text:
                                    leader_stocks_text.config(state=tk.NORMAL)
                                    leader_stocks_text.delete("1.0", tk.END)
                                    if leader_stocks_list:
                                        leader_stocks_text.insert("1.0", "\n".join(leader_stocks_list))
                                    else:
                                        leader_stocks_text.insert("1.0", "暂无数据")
                                    leader_stocks_text.config(state=tk.DISABLED)
                            except Exception as e:
                                print(f"更新龙头股列表显示失败: {e}")
                        else:
                            ax.text(0.5, 0.5, "暂无数据", ha='center', va='center',
                                   transform=ax.transAxes, fontsize=10)
                            canvas.draw()
                            # 更新龙头股列表显示(即使没有K线数据)
                            try:
                                leader_stocks_text = chart_info.get('leader_stocks_text')
                                if leader_stocks_text:
                                    leader_stocks_text.config(state=tk.NORMAL)
                                    leader_stocks_text.delete("1.0", tk.END)
                                    if leader_stocks_list:
                                        leader_stocks_text.insert("1.0", "\n".join(leader_stocks_list))
                                    else:
                                        leader_stocks_text.insert("1.0", "暂无数据")
                                    leader_stocks_text.config(state=tk.DISABLED)
                            except Exception as e:
                                print(f"更新龙头股列表显示失败: {e}")
                    else:
                        ax.text(0.5, 0.5, "暂无数据\n点击刷新重试", ha='center', va='center',
                               transform=ax.transAxes, fontsize=9, color='gray')
                        canvas.draw()
                        # 更新龙头股列表显示(即使加载失败)
                        try:
                            leader_stocks_text = chart_info.get('leader_stocks_text')
                            if leader_stocks_text:
                                leader_stocks_text.config(state=tk.NORMAL)
                                leader_stocks_text.delete("1.0", tk.END)
                                if leader_stocks_list:
                                    leader_stocks_text.insert("1.0", "\n".join(leader_stocks_list))
                                else:
                                    leader_stocks_text.insert("1.0", "暂无数据")
                                leader_stocks_text.config(state=tk.DISABLED)
                        except Exception as e:
                            print(f"更新龙头股列表显示失败: {e}")
                except Exception as e:
                    error_msg = str(e)
                    print(f"更新板块 {chart_info.get('sector_name', '未知')} K线图失败: {e}")
                    try:
                        ax = chart_info.get('ax')
                        canvas = chart_info.get('canvas')
                        if ax and canvas:
                            ax.clear()
                            # 判断是否是网络问题
                            if 'Connection' in error_msg or 'Remote' in error_msg or 'timeout' in error_msg.lower():
                                ax.text(0.5, 0.5, "网络连接失败\n请稍后重试", ha='center', va='center',
                                       transform=ax.transAxes, fontsize=9, color='red')
                            else:
                                ax.text(0.5, 0.5, f"加载失败\n{error_msg[:25]}...", ha='center', va='center',
                                       transform=ax.transAxes, fontsize=8, color='red')
                            canvas.draw()
                    except:
                        pass
            # 在后台线程中更新所有图表
            def update_all_charts():
                for chart_info in chart_widgets:
                    update_chart(chart_info)
            # 使用线程更新,避免阻塞UI
            threading.Thread(target=update_all_charts, daemon=True).start()
        except Exception as e:
            print(f"更新持仓情绪监测失败: {e}")


    def _calculate_trend_tracking(self, kline_data, stock_name):
        """趋势跟踪分析。
        基于均线系统、价格突破、成交量等指标判断趋势方向和强度,
        预测未来一周的涨跌幅概率。
        核心逻辑:
        1. 均线多头/空头排列判断
        2. 价格突破关键均线的方向
        3. 成交量与价格的配合关系
        4. ATR波动率评估
        """
        result = {
            'success': False,
            'message': '',
            'analysis': [],
            'calculation_steps': [],
            'prediction': {
                'next_day': {'direction': 'neutral', 'probability': 50, 'expected_return': 0},
                'next_week': {'direction': 'neutral', 'probability': 50, 'expected_return': 0}
            },
            'trend_strength': 0
        }
        try:
            data = kline_data['data']
            ma_values = kline_data['ma_values']
            n = len(data)
            if n < 20:
                result['message'] = '数据不足,至少需要20条K线'
                return result
            closes = data['收盘'].values
            highs = data['最高'].values
            lows = data['最低'].values
            volumes = data['成交量'].values
            import numpy as np
            result['calculation_steps'].append("【步骤1:均线排列分析】")
            ma5 = np.array(ma_values.get('ma5', []))
            ma10 = np.array(ma_values.get('ma10', []))
            ma20 = np.array(ma_values.get('ma20', []))
            ma_trend_score = 0
            if len(ma5) >= 5 and len(ma10) >= 5 and len(ma20) >= 5:
                recent_ma5 = ma5[-5:]
                recent_ma10 = ma10[-5:]
                recent_ma20 = ma20[-5:]
                if recent_ma5[-1] > recent_ma10[-1] and recent_ma10[-1] > recent_ma20[-1]:
                    result['calculation_steps'].append("  ✓ 均线多头排列(MA5 > MA10 > MA20)")
                    ma_trend_score += 30
                    if recent_ma5[-1] > recent_ma5[-5] and recent_ma10[-1] > recent_ma10[-5]:
                        result['calculation_steps'].append("  ✓ 均线向上发散")
                        ma_trend_score += 10
                elif recent_ma5[-1] < recent_ma10[-1] and recent_ma10[-1] < recent_ma20[-1]:
                    result['calculation_steps'].append("  ✗ 均线空头排列(MA5 < MA10 < MA20)")
                    ma_trend_score -= 30
                else:
                    result['calculation_steps'].append("  ~ 均线缠绕(震荡趋势)")
                if len(ma20) >= 5:
                    recent_ma20 = ma20[-5:]
                    if closes[-1] > recent_ma20[-1]:
                        result['calculation_steps'].append("  ✓ 股价站在20日均线上方")
                        ma_trend_score += 15
                    else:
                        result['calculation_steps'].append("  ✗ 股价在20日均线下方")
                        ma_trend_score -= 10
            else:
                result['calculation_steps'].append("  ~ 均线数据不足")
            result['calculation_steps'].append("\n【步骤2:价格突破分析】")
            recent_high = max(closes[-20:])
            recent_low = min(closes[-20:])
            current_price = closes[-1]
            break_score = 0
            if current_price >= recent_high * 0.98:
                result['calculation_steps'].append("  ✓ 接近或突破近期高点")
                break_score += 20
                if volumes[-1] > np.mean(volumes[-20:]) * 1.3:
                    result['calculation_steps'].append("  ✓ 放量突破")
                    break_score += 10
            elif current_price <= recent_low * 1.02:
                result['calculation_steps'].append("  ✗ 接近或跌破近期低点")
                break_score -= 20
            result['calculation_steps'].append("\n【步骤3:成交量配合分析】")
            vol_score = 0
            recent_vol_mean = np.mean(volumes[-10:])
            vol_ratio = volumes[-1] / recent_vol_mean if recent_vol_mean > 0 else 1
            if vol_ratio > 1.5:
                result['calculation_steps'].append(f"  ✓ 放量(量比 {vol_ratio:.2f})")
                if closes[-1] > closes[-2]:
                    vol_score += 15
                    result['calculation_steps'].append("  ✓ 价涨量增")
                else:
                    vol_score -= 10
                    result['calculation_steps'].append("  ✗ 价跌量增(放量下跌)")
            elif vol_ratio < 0.7:
                result['calculation_steps'].append(f"  ~ 缩量(量比 {vol_ratio:.2f})")
                if closes[-1] > closes[-2]:
                    vol_score += 5
                    result['calculation_steps'].append("  ✓ 价涨量缩(惜售)")
                else:
                    vol_score -= 5
            result['calculation_steps'].append("\n【步骤4:ATR波动率分析】")
            volat_score = 0
            tr_list = []
            for i in range(1, n):
                high = highs[i]
                low = lows[i]
                prev_close = closes[i-1]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
            atr = np.mean(tr_list[-14:]) if len(tr_list) >= 14 else 0
            price_range = recent_high - recent_low
            volatility_ratio = atr / price_range if price_range > 0 else 0
            if volatility_ratio > 0.3:
                result['calculation_steps'].append("  ✓ 高波动率(趋势可能延续)")
                volat_score += 10
            elif volatility_ratio < 0.1:
                result['calculation_steps'].append("  ~ 低波动率(可能变盘)")
            total_score = ma_trend_score + break_score + vol_score + volat_score
            result['trend_strength'] = total_score
            result['calculation_steps'].append("\n【综合评分】")
            result['calculation_steps'].append(f"  均线趋势分:{ma_trend_score}")
            result['calculation_steps'].append(f"  突破分:{break_score}")
            result['calculation_steps'].append(f"  成交量分:{vol_score}")
            result['calculation_steps'].append(f"  波动率分:{volat_score}")
            result['calculation_steps'].append(f"  总分:{total_score}")
            if total_score > 30:
                result['prediction']['next_day']['direction'] = 'up'
                result['prediction']['next_day']['probability'] = min(70, 50 + total_score // 2)
                result['prediction']['next_day']['expected_return'] = total_score * 0.05
                result['prediction']['next_week']['direction'] = 'up'
                result['prediction']['next_week']['probability'] = min(65, 50 + total_score // 3)
                result['prediction']['next_week']['expected_return'] = total_score * 0.15
                result['analysis'].append("【趋势判断】强势上涨趋势")
                result['analysis'].append(f"【预测】明日上涨概率 {result['prediction']['next_day']['probability']}%")
                result['analysis'].append(f"【预测】下周上涨概率 {result['prediction']['next_week']['probability']}%")
                result['analysis'].append("【建议】持仓或逢低买入")
            elif total_score < -20:
                result['prediction']['next_day']['direction'] = 'down'
                result['prediction']['next_day']['probability'] = min(70, 50 - total_score // 2)
                result['prediction']['next_day']['expected_return'] = total_score * 0.05
                result['prediction']['next_week']['direction'] = 'down'
                result['prediction']['next_week']['probability'] = min(65, 50 - total_score // 3)
                result['prediction']['next_week']['expected_return'] = total_score * 0.15
                result['analysis'].append("【趋势判断】弱势下跌趋势")
                result['analysis'].append(f"【预测】明日下跌概率 {result['prediction']['next_day']['probability']}%")
                result['analysis'].append(f"【预测】下周下跌概率 {result['prediction']['next_week']['probability']}%")
                result['analysis'].append("【建议】减仓或观望")
            else:
                result['prediction']['next_day']['direction'] = 'neutral'
                result['prediction']['next_day']['probability'] = 50
                result['prediction']['next_week']['direction'] = 'neutral'
                result['prediction']['next_week']['probability'] = 50
                result['analysis'].append("【趋势判断】震荡整理趋势")
                result['analysis'].append("【预测】方向不明,震荡为主")
                result['analysis'].append("【建议】观望或高抛低吸")
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result


    def _get_ths_sentiment_index_daily(self, days=60):
        """获取同花顺情绪指数日线:优先 Tushare 指数接口,失败则用 AKShare 概念板块日K。"""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days + 20)).strftime("%Y%m%d")
        # 1) 尝试 Tushare 指数日线(同花顺情绪指数在部分数据源中为 883404.TI 或类似)
        if TS_AVAILABLE and (getattr(self, 'ts_token', None) or TS_DEFAULT_TOKEN):
            try:
                self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                for ts_code in ("883404.TI", "883404.SI", "399405.SZ"):
                    try:
                        df = self.ts_client.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                        if df is not None and not df.empty and len(df) >= 2:
                            df = df.sort_values("trade_date").tail(days).reset_index(drop=True)
                            data = pd.DataFrame({"收盘": df["close"].astype(float)})
                            return {
                                "data": data,
                                "trade_dates": list(df["trade_date"].astype(str)),
                                "source": "Tushare",
                            }
                    except Exception:
                        continue
            except Exception:
                pass
        # 2) 回退 AKShare:同花顺情绪指数概念板块日K
        for sym in ("同花顺情绪指数", "883404"):
            try:
                import akshare as ak
                df = ak.stock_board_concept_hist_em(
                    symbol=sym,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                )
                if df is not None and not df.empty and len(df) >= 2:
                    df = df.tail(days).reset_index(drop=True)
                    close_col = None
                    for c in df.columns:
                        if "收盘" in str(c):
                            close_col = c
                            break
                    if close_col is None:
                        num_cols = [c for c in df.columns if str(df[c].dtype).startswith(("float", "int"))]
                        close_col = num_cols[-1] if num_cols else df.columns[-1]
                    data = pd.DataFrame({"收盘": df[close_col].astype(float)})
                    date_col = df.columns[0]
                    trade_dates = [str(x)[:10].replace("-", "") for x in df[date_col]]
                    return {
                        "data": data,
                        "trade_dates": trade_dates,
                        "source": "AKShare",
                    }
            except Exception:
                continue
        return None


    def _build_sentiment_zone_tabs(self, parent):
        """右上区域:情绪区间标签页(所有指标集中在第1页,数据来源问财)。"""
        try:
            top_bar = ttk.Frame(parent)
            top_bar.pack(fill=tk.X, padx=4, pady=(2, 4))
            ttk.Label(top_bar, text="情绪区间指标(全部来自问财)", font=("TkDefaultFont", 10), foreground="#666666").pack(
                side=tk.LEFT, padx=(2, 8)
            )
            ttk.Button(top_bar, text="刷新", command=self._refresh_sentiment_zone_tabs_async, width=8).pack(side=tk.RIGHT)
            ttk.Button(top_bar, text="历史记录", command=self._show_sentiment_history_dialog, width=8).pack(side=tk.RIGHT, padx=(0, 4))
            self.sentiment_zone_status_var = tk.StringVar(value="准备就绪")
            ttk.Label(top_bar, textvariable=self.sentiment_zone_status_var, foreground="#666666").pack(side=tk.RIGHT, padx=(0, 8))
            notebook = ttk.Notebook(parent)
            notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
            self.sentiment_zone_notebook = notebook
            self.sentiment_zone_text_widgets = {}
            # ---- Tab 1: 🎯 情绪复盘 (先显示, 只渲染月复盘三栏, 不渲染完整日历) ----
            try:
                rev_tab = ttk.Frame(notebook)
                notebook.add(rev_tab, text="🎯 情绪复盘")
                # 滚动容器 (防止内容过长被截断)
                _rev_canvas = tk.Canvas(rev_tab, highlightthickness=0, borderwidth=0)
                _rev_scroll = ttk.Scrollbar(rev_tab, orient=tk.VERTICAL, command=_rev_canvas.yview)
                _rev_scroll.pack(side=tk.RIGHT, fill=tk.Y)
                _rev_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                _rev_canvas.configure(yscrollcommand=_rev_scroll.set)
                _rev_inner = ttk.Frame(_rev_canvas)
                _rev_win = _rev_canvas.create_window((0, 0), window=_rev_inner, anchor="nw")
                def _rev_on_config(e):
                    _rev_canvas.itemconfigure(_rev_win, width=e.width)
                    _rev_canvas.configure(scrollregion=_rev_canvas.bbox("all"))
                _rev_canvas.bind("<Configure>", _rev_on_config)
                _rev_inner.bind("<Configure>", lambda e: _rev_canvas.configure(scrollregion=_rev_canvas.bbox("all")))
                def _rev_wheel(e): _rev_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
                _rev_canvas.bind_all("<MouseWheel>", _rev_wheel)
                from datetime import datetime as _dt2
                _ym = _dt2.now()
                _pf, _cf = self._fetch_month_index_pct(_ym)
                self._render_month_review(_rev_inner, _ym, _pf, _cf)
                _rev_canvas.after(300, lambda: _rev_canvas.configure(scrollregion=_rev_canvas.bbox("all")))
            except Exception as _e_emo_tab:
                import traceback; traceback.print_exc()
                print(f"[情绪复盘] tab创建失败: {_e_emo_tab}", flush=True)
            # ---- Tab 2: 情绪总览 ----
            tab = ttk.Frame(notebook)
            notebook.add(tab, text="情绪总览")
            txt = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("Consolas", 11))
            txt.pack(fill=tk.BOTH, expand=True)
            txt.tag_configure("up_bold", foreground="#d32f2f", font=("Consolas", 11, "bold"))
            txt.tag_configure("down_bold", foreground="#2e7d32", font=("Consolas", 11, "bold"))
            txt.insert("1.0", "加载中...\n")
            txt.config(state=tk.DISABLED)
            self.sentiment_zone_text_widgets["overview"] = txt
            # ---- Tab 3: 📈 指数趋势 (上证/深成指/创业板 日K + 1/5/10/20/60均线) ----
            try:
                idx_tab = ttk.Frame(notebook)
                notebook.add(idx_tab, text="📈 指数趋势")
                self._build_index_trend_tab(idx_tab)
            except Exception as _e_idx:
                import traceback; traceback.print_exc()
                print(f"[指数趋势] tab创建失败: {_e_idx}", flush=True)
            self._refresh_sentiment_zone_tabs_async()
        except Exception as e:
            ttk.Label(parent, text=f"情绪区间标签页创建失败: {e}", foreground="red").pack(expand=True)


    def _build_emo_cycle_chart_tab(self, parent):
        """📈 情绪周期图: 从 emo_history.json 渲染情绪分折线 + 涨跌幅柱状图 + 热力条"""
        import json as _js, os as _os
        # 顶部标题栏
        header = tk.Frame(parent, bg="#1A237E")
        header.pack(fill=tk.X, padx=2, pady=(2, 0))
        tk.Label(header, text="📈 情绪周期三维度 · 情绪分趋势 + 涨跌幅 + 情绪阶段",
                 bg="#1A237E", fg="white", font=("", 11, "bold")).pack(side=tk.LEFT, padx=8, pady=4)
        # 刷新按钮
        def _refresh():
            try:
                self._render_emo_cycle_chart()
                self._emo_chart_status.set(f"✅ 已刷新  {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                self._emo_chart_status.set(f"❌ 刷新失败: {e}")
        tk.Button(header, text="🔄 刷新", command=_refresh,
                  bg="#FF6F00", fg="white", font=("", 9, "bold"),
                  padx=8, pady=1).pack(side=tk.RIGHT, padx=6, pady=3)
        self._emo_chart_status = tk.StringVar(value="⏳ 加载中...")
        tk.Label(header, textvariable=self._emo_chart_status,
                 bg="#1A237E", fg="#FFD54F", font=("", 9)).pack(side=tk.RIGHT, padx=8)

        # 趋势 Canvas (上, 较高)
        trend_frame = tk.Frame(parent, bg="#E8EAF6")
        trend_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=(2, 0))
        self._emo_chart_trend_canvas = tk.Canvas(trend_frame, bg="white",
                                                  highlightthickness=1, highlightbackground="#C5CAE9")
        self._emo_chart_trend_canvas.pack(fill=tk.BOTH, expand=True)

        # 阶段热力条 Canvas (下, 扁)
        heat_frame = tk.Frame(parent, bg="#E8EAF6")
        heat_frame.pack(fill=tk.X, padx=2, pady=(2, 2))
        self._emo_chart_heat_canvas = tk.Canvas(heat_frame, bg="#424242", height=40,
                                                 highlightthickness=1, highlightbackground="#555")
        self._emo_chart_heat_canvas.pack(fill=tk.X)

        # 宽度变化时自动重绘
        self._emo_chart_trend_canvas.bind("<Configure>", lambda e: self._render_emo_cycle_chart())
        self._emo_chart_heat_canvas.bind("<Configure>", lambda e: self._render_emo_cycle_chart())

        # 立即渲染
        self._render_emo_cycle_chart()


    def _render_emo_cycle_chart(self):
        """读取 emo_history.json 并渲染到情绪周期图 Canvas"""
        # --- Configure 防抖: 宽度没变不重绘 + re-entry guard ---
        if getattr(self, '_emo_chart_rendering', False):
            return
        tc = getattr(self, '_emo_chart_trend_canvas', None)
        hc = getattr(self, '_emo_chart_heat_canvas', None)
        if not tc or not hc:
            return
        _cw = tc.winfo_width()
        if _cw < 100:
            return
        if getattr(self, '_emo_chart_last_width', None) == _cw:
            return
        self._emo_chart_last_width = _cw
        self._emo_chart_rendering = True
        try:
            self._do_render_emo_cycle_chart()
        finally:
            self._emo_chart_rendering = False


    def _do_render_emo_cycle_chart(self):
        """实际渲染逻辑 (被 _render_emo_cycle_chart 防抖包裹)"""
        import json as _js, os as _os, re as _re
        try:
            path = os.path.expanduser("~/.qclaw/workspace-agent-85985980/stockyidong_emo_history.json")
            tc = getattr(self, '_emo_chart_trend_canvas', None)
            hc = getattr(self, '_emo_chart_heat_canvas', None)
            if not tc or not hc:
                return
            tc.delete("all"); hc.delete("all")

            if not os.path.exists(path):
                tc.create_text(300, 150, text="⏳ emo_history.json 不存在\n请先在「🎭情绪周期」弹窗录入数据",
                               fill="#90A4AE", font=("", 11), justify="center")
                hc.create_text(300, 20, text="暂无数据", fill="#90A4AE", font=("", 9))
                return

            with open(path) as f:
                hist = _js.load(f)
            if not isinstance(hist, dict) or not hist:
                tc.create_text(300, 150, text="⏳ emo_history 为空", fill="#90A4AE", font=("", 11))
                return

            # 按日期排序, 清理 stage 中的 emoji 前缀
            sorted_dates = sorted(hist.keys())
            data = []
            for d in sorted_dates:
                v = hist[d]
                stage_raw = str(v.get("stage", v.get("cycle", "")))
                stage = _re.sub(r'[^\u4e00-\u9fa5A-Za-z0-9 ]+', '', stage_raw).strip()
                if not stage:
                    # 从 emo_score 推断 stage
                    es = float(v.get("emo_score", 50) or 50)
                    if es >= 70: stage = "高潮"
                    elif es >= 55: stage = "发酵"
                    elif es >= 45: stage = "启动"
                    elif es >= 35: stage = "震荡"
                    elif es >= 25: stage = "分歧"
                    else: stage = "退潮"
                data.append({
                    "full_date": d,
                    "date": d[5:10],
                    "pct": float(v.get("pct", 0) or 0),
                    "emo": float(v.get("emo_score", 50) or 50),
                    "zt": int(v.get("zt", 0) or 0),
                    "close": v.get("close", 0),
                    "stage": stage,
                    "pnl": str(v.get("pnl", "")),
                    "ths": str(v.get("ths", "")),
                })

            n = len(data)
            cw = tc.winfo_width() or max(600, n * 60)
            ch = tc.winfo_height() or 300
            if cw < 100 or ch < 100:
                return  # 还没布局好,等下一次 Configure

            # ===== 趋势图 =====
            pad_l, pad_r, pad_t, pad_b = 45, 15, 30, 60
            plot_w = cw - pad_l - pad_r
            plot_h = ch - pad_t - pad_b - 14
            gap = plot_w / n
            bar_w = gap * 0.55

            def _emo_score_color(s):
                if s >= 70: return "#C62828"
                if s >= 60: return "#FF6F00"
                if s >= 50: return "#F57F17"
                if s >= 40: return "#FFD54F"
                if s >= 30: return "#9E9E9E"
                return "#2E7D32"

            def _stage_color(stg):
                _m = {"冰点": "#2E7D32", "启动": "#F57F17", "发酵": "#FF6F00",
                      "高潮": "#C62828", "分歧": "#6A1B9A", "退潮": "#455A64"}
                return _m.get(stg, "#78909C")

            # 标题
            tc.create_text(cw/2, 12,
                           text=f"📈 情绪周期趋势 · {n}天 ({data[0]['date']} ~ {data[-1]['date']})",
                           fill="#1A237E", font=("", 11, "bold"))
            tc.create_text(cw/2, 26, text="●情绪分(0-100折线)  ▌上证涨跌(红涨/绿跌柱)  ■情绪阶段(热力条)",
                           fill="#546E7A", font=("", 8))

            # 1) 涨跌柱状图 (下半区)
            emo_top_y = pad_t + 10
            emo_btm_y = pad_t + plot_h / 2 - 4
            bar_top_y = emo_btm_y + 4
            bar_btm_y = pad_t + plot_h
            mid_y = (bar_top_y + bar_btm_y) / 2
            max_abs = max((abs(d["pct"]) for d in data), default=1)
            if max_abs == 0: max_abs = 1

            # 零线
            tc.create_line(pad_l, mid_y, pad_l + plot_w, mid_y, fill="#B0BEC5", width=1)
            tc.create_text(pad_l - 4, mid_y, text="0", fill="#78909C", font=("", 8), anchor="e")

            for i, d in enumerate(data):
                cx = pad_l + i * gap + gap / 2
                x1 = cx - bar_w / 2
                x2 = cx + bar_w / 2
                chg = d["pct"]
                bh = int(abs(chg) / max_abs * ((bar_btm_y - bar_top_y) / 2 - 2))
                if chg >= 0:
                    tc.create_rectangle(x1, mid_y - bh, x2, mid_y,
                                        fill="#C62828", outline="#C62828")
                else:
                    tc.create_rectangle(x1, mid_y, x2, mid_y + bh,
                                        fill="#2E7D32", outline="#2E7D32")
                # 涨跌%文字
                fsize = 9 if i == n - 1 else 8
                tcol = "#C62828" if chg >= 0 else "#2E7D32"
                ty = mid_y - bh - 3 if chg >= 0 else mid_y + bh + 3
                tc.create_text(cx, ty, text=f"{chg:+.1f}%", fill=tcol,
                               font=("", fsize, "bold" if i == n - 1 else ""),
                               anchor="s" if chg >= 0 else "n")

            # 2) 情绪分折线 (上半区)
            emo_pts = []
            for i, d in enumerate(data):
                ex = pad_l + i * gap + gap / 2
                ey = emo_btm_y - (d["emo"] / 100 * (emo_btm_y - emo_top_y))
                emo_pts.append((ex, ey))
            if len(emo_pts) >= 2:
                flat = [coord for p in emo_pts for coord in p]
                tc.create_line(*flat, fill="#FF6F00", width=2, smooth=True)
                # 渐变圆点
                for i, (px, py) in enumerate(emo_pts):
                    col = _emo_score_color(data[i]["emo"])
                    tc.create_oval(px - 5, py - 5, px + 5, py + 5,
                                   fill=col, outline="white", width=1)
                    # 情绪分数值 (只标最后一个)
                    if i == n - 1:
                        tc.create_text(px + 8, py - 10, text=f"{data[i]['emo']:.0f}",
                                       fill="#FF6F00", font=("", 10, "bold"), anchor="w")

            # Y轴刻度
            tc.create_text(pad_l - 4, emo_top_y, text="100", fill="#78909C", font=("", 8), anchor="e")
            tc.create_text(pad_l - 4, emo_btm_y, text="0", fill="#78909C", font=("", 8), anchor="e")

            # X轴日期
            xlbl_y = bar_btm_y + 10
            for i, d in enumerate(data):
                cx = pad_l + i * gap + gap / 2
                # 每 2 天标一次, 最后一天必标
                if i % 2 == 0 or i == n - 1:
                    tc.create_text(cx, xlbl_y, text=d["date"],
                                   fill="#546E7A", font=("", 8))
                # 阶段文字 (最后一天标)
                if i == n - 1:
                    tc.create_text(cx, xlbl_y + 16, text=f"📊 {d['stage']}",
                                   fill=_stage_color(d["stage"]),
                                   font=("", 9, "bold"))

            # ===== 情绪阶段热力条 (独立 Canvas) =====
            hc.delete("all")
            hcw = hc.winfo_width() or cw
            hch = 40
            h_pad_l = pad_l
            h_pad_r = pad_r
            h_plot_w = hcw - h_pad_l - h_pad_r
            h_gap = h_plot_w / n
            sq_h = 22

            hc.create_text(hcw / 2, 8,
                           text="🔥 情绪阶段热力条  (红=高潮 橙=发酵 黄=启动 灰=震荡 紫=分歧 绿=退潮)",
                           fill="#E0E0E0", font=("", 8))
            for i, d in enumerate(data):
                sx = h_pad_l + i * h_gap + (h_gap - min(28, h_gap - 4)) / 2
                sq_w = min(28, h_gap - 4)
                col = _stage_color(d["stage"])
                hc.create_rectangle(sx, 14, sx + sq_w, 14 + sq_h,
                                     fill=col, outline="#222", width=1)
                # 阶段字
                hc.create_text(sx + sq_w / 2, 14 + sq_h / 2, text=d["stage"],
                               fill="white", font=("", 7, "bold"))
                # 最新标★
                if i == n - 1:
                    hc.create_text(sx + sq_w / 2, 14 - 2, text="★",
                                   fill="#FFD700", font=("", 9, "bold"))

            self._emo_chart_status.set(f"✅ {n}天数据  {data[0]['date']}~{data[-1]['date']}  当前:{data[-1]['stage']}")

        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[情绪周期图] 渲染失败: {e}", flush=True)
            if hasattr(self, '_emo_chart_status'):
                self._emo_chart_status.set(f"❌ 渲染失败: {e}")


    def _get_market_up_down_counts(self):
        """市场上涨/下跌家数:优先 AKShare 全A快照,失败回退 Tushare。"""
        try:
            if not AKSHARE_AVAILABLE:
                raise RuntimeError("AKShare unavailable")
            df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
            if df is None or df.empty:
                raise RuntimeError("AKShare returned empty")
            pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
            if pct_col is None:
                for c in df.columns:
                    if "涨跌幅" in str(c):
                        pct_col = c
                        break
            if pct_col is None:
                raise RuntimeError("AKShare pct column not found")
            p = pd.to_numeric(df[pct_col], errors="coerce")
            up = int((p > 0).sum())
            down = int((p < 0).sum())
            flat = int((p == 0).sum())
            total = int(p.notna().sum())
            return {"up": up, "down": down, "flat": flat, "total": total, "source": "AKShare"}
        except Exception:
            # 回退 Tushare:按最近可交易日全市场日线统计涨跌家数
            try:
                if not TS_AVAILABLE or not (getattr(self, "ts_token", None) or TS_DEFAULT_TOKEN):
                    return None
                self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
                for back in range(8):
                    td = (datetime.now() - timedelta(days=back)).strftime("%Y%m%d")
                    try:
                        df = self.ts_client.daily(trade_date=td)
                    except Exception:
                        continue
                    if df is None or df.empty:
                        continue
                    if "pct_chg" in df.columns:
                        p = pd.to_numeric(df["pct_chg"], errors="coerce")
                    elif "close" in df.columns and "pre_close" in df.columns:
                        c = pd.to_numeric(df["close"], errors="coerce")
                        pc = pd.to_numeric(df["pre_close"], errors="coerce")
                        p = (c / pc - 1.0) * 100.0
                    else:
                        continue
                    up = int((p > 0).sum())
                    down = int((p < 0).sum())
                    flat = int((p == 0).sum())
                    total = int(p.notna().sum())
                    return {"up": up, "down": down, "flat": flat, "total": total, "source": f"Tushare({td})"}
            except Exception:
                pass
            return None


    def _get_ths_sentiment_change_today_yday(self):
        """同花顺情绪指数:返回当日涨跌幅与昨日涨跌幅(优先 Tushare/AKShare,失败再问财)。"""
        # 1) 先用已有日线接口(已内置 Tushare/AKShare 回退)
        try:
            ths = self._get_ths_sentiment_index_daily(days=5)
            if ths and "data" in ths:
                closes = pd.to_numeric(ths["data"]["收盘"], errors="coerce").dropna().values
                if len(closes) >= 3:
                    today_pct = (float(closes[-1]) / float(closes[-2]) - 1.0) * 100.0
                    yday_pct = (float(closes[-2]) / float(closes[-3]) - 1.0) * 100.0
                    return {"today": today_pct, "yday": yday_pct, "source": ths.get("source", "Kline")}
        except Exception:
            pass
        # 2) 再回退问财
        try:
            m1_today = self._fetch_iwencai_metric("同花顺情绪指数883404 当日涨跌幅", value_hints=["涨跌幅", "当日"])
            m1_yday = self._fetch_iwencai_metric("同花顺情绪指数883404 昨日涨跌幅", value_hints=["涨跌幅", "昨日"])
            return {"today": m1_today.get("value"), "yday": m1_yday.get("value"), "source": "问财"}
        except Exception:
            return {"today": None, "yday": None, "source": "未获取"}


    def _enhance_sentiment_snapshot_with_tushare(self, snapshot):
        """问财/Ak 字段为空时,用 Tushare 指数日线与涨跌家数逻辑补齐情绪五问快照。"""
        if not snapshot or not isinstance(snapshot, dict):
            return
        m = snapshot.setdefault("metrics", {})
        tush_idx = self._get_major_index_pct_from_tushare()
        def _patch_m5(metric_key, cn_key, msg_note=None):
            sub = m.get(metric_key)
            if not isinstance(sub, dict):
                sub = {}
            if sub.get("value") is None and cn_key in tush_idx:
                m[metric_key] = {
                    "count": sub.get("count"),
                    "value": float(tush_idx[cn_key]),
                    "msg": msg_note or "Tushare·index_daily",
                }
        _patch_m5("m5_hs300", "沪深300")
        _patch_m5("m5_zz500", "中证500")
        if (m.get("m5_kc30") or {}).get("value") is None and "科创50" in tush_idx:
            o = m.get("m5_kc30") or {}
            m["m5_kc30"] = {
                "count": o.get("count"),
                "value": float(tush_idx["科创50"]),
                "msg": "Tushare·科创50(近似问财科创30)",
            }
        vals = []
        for k in ("m5_hs300", "m5_zz500", "m5_kc30"):
            v = (m.get(k) or {}).get("value")
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if vals:
            m["m5_avg"] = sum(vals) / len(vals)
        mk = m.get("m2_market")
        if not isinstance(mk, dict) or not mk.get("total"):
            m2 = self._get_market_up_down_counts()
            if m2:
                m["m2_market"] = m2


    def _save_sentiment_snapshot_to_history(self, snapshot):
        """保存情绪快照到历史记录。"""
        try:
            import json
            import sqlite3
            m = snapshot.get("metrics", {})
            mk = m.get("m2_market") or {}
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO sentiment_history
                (snapshot_time, snapshot_date, m1_today, m1_yday,
                 m2_up, m2_down, m2_flat, m2_total,
                 m3_count, m4_count, m5_hs300, m5_zz500, m5_kc30, m5_avg, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot.get("time", ""),
                datetime.now().strftime("%Y-%m-%d"),
                m.get("m1_today", {}).get("value"),
                m.get("m1_yday", {}).get("value"),
                mk.get("up"),
                mk.get("down"),
                mk.get("flat"),
                mk.get("total"),
                m.get("m3", {}).get("count"),
                m.get("m4", {}).get("count"),
                m.get("m5_hs300", {}).get("value"),
                m.get("m5_zz500", {}).get("value"),
                m.get("m5_kc30", {}).get("value"),
                m.get("m5_avg"),
                json.dumps(snapshot, ensure_ascii=False)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"保存情绪历史记录失败: {e}")


    def _get_sentiment_history(self, limit=15):
        """获取最近的情绪历史记录。"""
        try:
            import json
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute('''
                SELECT snapshot_time, snapshot_date, m1_today, m1_yday,
                       m2_up, m2_down, m2_flat, m2_total,
                       m3_count, m4_count, m5_hs300, m5_zz500, m5_kc30, m5_avg, raw_json
                FROM sentiment_history
                ORDER BY id DESC LIMIT ?
            ''', (limit,))
            rows = cur.fetchall()
            conn.close()
            history = []
            for row in rows:
                history.append({
                    "snapshot_time": row[0],
                    "snapshot_date": row[1],
                    "m1_today": row[2],
                    "m1_yday": row[3],
                    "m2_up": row[4],
                    "m2_down": row[5],
                    "m2_flat": row[6],
                    "m2_total": row[7],
                    "m3_count": row[8],
                    "m4_count": row[9],
                    "m5_hs300": row[10],
                    "m5_zz500": row[11],
                    "m5_kc30": row[12],
                    "m5_avg": row[13],
                    "raw_json": json.loads(row[14]) if row[14] else None
                })
            return history
        except Exception as e:
            print(f"获取情绪历史记录失败: {e}")
            return []


    def _show_sentiment_history_dialog(self):
        """打开情绪历史记录对话框。"""
        try:
            win = self._safe_toplevel(self.root)
            win.title("情绪历史记录")
            win.geometry("800x600")
            win.transient(self.root)
            notebook = ttk.Notebook(win)
            notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            # 文本视图
            txt_tab = ttk.Frame(notebook)
            notebook.add(txt_tab, text="详细记录")
            txt = scrolledtext.ScrolledText(txt_tab, wrap=tk.WORD, font=("Consolas", 11))
            txt.pack(fill=tk.BOTH, expand=True)
            txt.tag_configure("up_bold", foreground="#d32f2f", font=("Consolas", 11, "bold"))
            txt.tag_configure("down_bold", foreground="#2e7d32", font=("Consolas", 11, "bold"))
            def _fmt_pct(v):
                return f"{v:+.2f}%" if isinstance(v, (int, float)) else "未获取"
            def _ins_colored_value(w, v, pct=False):
                if not isinstance(v, (int, float)):
                    w.insert(tk.END, "未获取")
                    return
                s = f"{v:+.2f}%" if pct else (str(int(v)) if float(v).is_integer() else f"{v:.2f}")
                tag = "up_bold" if v >= 0 else "down_bold"
                w.insert(tk.END, s, tag)
            history = self._get_sentiment_history(limit=100)
            if history:
                txt.config(state=tk.NORMAL)
                txt.delete("1.0", tk.END)
                for idx, record in enumerate(history):
                    txt.insert(tk.END, "\n" + "="*70 + "\n")
                    txt.insert(tk.END, f"记录 #{idx+1} | {record['snapshot_time']}\n")
                    txt.insert(tk.END, "="*70 + "\n")
                    txt.insert(tk.END, "\n【问题1:同花顺情绪指数 当日涨跌幅、昨日涨跌幅?】\n")
                    txt.insert(tk.END, "  当日涨跌幅:")
                    _ins_colored_value(txt, record.get("m1_today"), pct=True)
                    txt.insert(tk.END, "\n")
                    txt.insert(tk.END, "  昨日涨跌幅:")
                    _ins_colored_value(txt, record.get("m1_yday"), pct=True)
                    txt.insert(tk.END, "\n")
                    if record.get("m2_up") is not None:
                        txt.insert(tk.END, "\n【问题2:当日股票涨跌个数各是多少个?】\n")
                        txt.insert(tk.END, "  上涨:")
                        _ins_colored_value(txt, record.get("m2_up"), pct=False)
                        txt.insert(tk.END, " 个\n")
                        txt.insert(tk.END, "  下跌:")
                        _ins_colored_value(txt, record.get("m2_down"), pct=False)
                        txt.insert(tk.END, " 个\n")
                        if record.get("m2_flat") is not None:
                            txt.insert(tk.END, f"  平盘:{int(record['m2_flat'])} 个\n")
                        if record.get("m2_total") is not None:
                            txt.insert(tk.END, f"  总计:{int(record['m2_total'])} 个\n")
                    if record.get("m3_count") is not None:
                        txt.insert(tk.END, "\n【问题3:股价上穿60分钟周期 60日均线 且放量?】\n")
                        txt.insert(tk.END, f"  答案:{record['m3_count']} 只\n")
                        # 显示股票列表(从raw_json中提取)
                        raw_json = record.get("raw_json", {})
                        m3_stocks = []
                        if isinstance(raw_json, dict):
                            metrics = raw_json.get("metrics", {})
                            m3 = metrics.get("m3", {})
                            m3_stocks = m3.get("stocks", [])
                        if m3_stocks:
                            txt.insert(tk.END, "  股票列表:")
                            for i, s in enumerate(m3_stocks[:30]):
                                name = s.get('name', '')
                                code = s.get('code', '')
                                # 去掉股票代码中的字母前缀(如SH、SZ)
                                import re
                                code_match = re.search(r'\d{6}', code)
                                clean_code = code_match.group() if code_match else code
                                if name and clean_code:
                                    stock_text = f"{name}({clean_code})"
                                elif name:
                                    stock_text = name
                                elif clean_code:
                                    stock_text = clean_code
                                else:
                                    continue
                                tag_name = f"stock_{i}_{record.get('snapshot_time', '')}"
                                txt.insert(tk.END, stock_text, tag_name)
                                txt.tag_configure(tag_name, foreground="#1565c0", underline=True)
                                txt.tag_bind(tag_name, "<Double-Button-1>",
                                          lambda e, n=name, c=clean_code: self._show_stock_detail_direct(n if n else c, c if c else n, 1))
                                if i < len(m3_stocks[:30]) - 1:
                                    txt.insert(tk.END, ", ")
                            if len(m3_stocks) > 30:
                                txt.insert(tk.END, f" ...(共{len(m3_stocks)}只)")
                            txt.insert(tk.END, "\n")
                    if record.get("m4_count") is not None:
                        txt.insert(tk.END, "\n【问题4:15分钟 5/10/20/60 向上发散?】\n")
                        txt.insert(tk.END, f"  答案:{record['m4_count']} 只\n")
                    if record.get("m5_hs300") is not None or record.get("m5_zz500") is not None or record.get("m5_kc30") is not None:
                        txt.insert(tk.END, "\n【问题5:沪深300/中证500/科创30 平均涨跌幅?】\n")
                        if record.get("m5_hs300") is not None:
                            txt.insert(tk.END, "  沪深300:")
                            _ins_colored_value(txt, record.get("m5_hs300"), pct=True)
                            txt.insert(tk.END, "\n")
                        if record.get("m5_zz500") is not None:
                            txt.insert(tk.END, "  中证500:")
                            _ins_colored_value(txt, record.get("m5_zz500"), pct=True)
                            txt.insert(tk.END, "\n")
                        if record.get("m5_kc30") is not None:
                            txt.insert(tk.END, "  科创30:")
                            _ins_colored_value(txt, record.get("m5_kc30"), pct=True)
                            txt.insert(tk.END, "\n")
                        if record.get("m5_avg") is not None:
                            txt.insert(tk.END, "  平均涨跌幅:")
                            _ins_colored_value(txt, record.get("m5_avg"), pct=True)
                            txt.insert(tk.END, "\n")
                txt.config(state=tk.DISABLED)
            else:
                txt.insert("1.0", "暂无历史记录\n")
                txt.config(state=tk.DISABLED)
            # 统计视图
            stat_tab = ttk.Frame(notebook)
            notebook.add(stat_tab, text="统计概览")
            stat_txt = scrolledtext.ScrolledText(stat_tab, wrap=tk.WORD, font=("Consolas", 11))
            stat_txt.pack(fill=tk.BOTH, expand=True)
            stat_txt.tag_configure("up_bold", foreground="#d32f2f", font=("Consolas", 11, "bold"))
            stat_txt.tag_configure("down_bold", foreground="#2e7d32", font=("Consolas", 11, "bold"))
            if history:
                stat_txt.config(state=tk.NORMAL)
                stat_txt.delete("1.0", tk.END)
                stat_txt.insert(tk.END, "情绪历史记录统计概览\n")
                stat_txt.insert(tk.END, "="*50 + "\n\n")
                stat_txt.insert(tk.END, f"总记录数:{len(history)} 条\n\n")
                m1_today_vals = [r['m1_today'] for r in history if isinstance(r['m1_today'], (int, float))]
                if m1_today_vals:
                    stat_txt.insert(tk.END, "【同花顺情绪指数当日涨跌幅】\n")
                    stat_txt.insert(tk.END, "  平均值:")
                    _ins_colored_value(stat_txt, sum(m1_today_vals)/len(m1_today_vals), pct=True)
                    stat_txt.insert(tk.END, "\n")
                    stat_txt.insert(tk.END, "  最大值:")
                    _ins_colored_value(stat_txt, max(m1_today_vals), pct=True)
                    stat_txt.insert(tk.END, "\n")
                    stat_txt.insert(tk.END, "  最小值:")
                    _ins_colored_value(stat_txt, min(m1_today_vals), pct=True)
                    stat_txt.insert(tk.END, "\n")
                    stat_txt.insert(tk.END, f"  上涨次数:{sum(1 for v in m1_today_vals if v > 0)} 次\n")
                    stat_txt.insert(tk.END, f"  下跌次数:{sum(1 for v in m1_today_vals if v < 0)} 次\n\n")
                m5_avg_vals = [r['m5_avg'] for r in history if isinstance(r['m5_avg'], (int, float))]
                if m5_avg_vals:
                    stat_txt.insert(tk.END, "【指数平均涨跌幅】\n")
                    stat_txt.insert(tk.END, "  平均值:")
                    _ins_colored_value(stat_txt, sum(m5_avg_vals)/len(m5_avg_vals), pct=True)
                    stat_txt.insert(tk.END, "\n")
                    stat_txt.insert(tk.END, "  最大值:")
                    _ins_colored_value(stat_txt, max(m5_avg_vals), pct=True)
                    stat_txt.insert(tk.END, "\n")
                    stat_txt.insert(tk.END, "  最小值:")
                    _ins_colored_value(stat_txt, min(m5_avg_vals), pct=True)
                    stat_txt.insert(tk.END, "\n")
                stat_txt.config(state=tk.DISABLED)
            else:
                stat_txt.insert("1.0", "暂无历史记录\n")
                stat_txt.config(state=tk.DISABLED)
        except Exception as e:
            print(f"打开情绪历史记录对话框失败: {e}")
            import traceback
            traceback.print_exc()


    def _collect_sentiment_zone_snapshot(self):
        """采集情绪区间页需要的全部指标(问财为主,Tushare 补缺)。"""
        snapshot = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        m1_pair = self._get_ths_sentiment_change_today_yday()
        # 涨跌家数使用全市场快照统计(更接近用户期望的5000+总数)
        m2_market = self._get_market_up_down_counts()
        m3 = self._fetch_iwencai_metric("股价上穿60分钟周期 60日均线 且放量")
        m4 = self._fetch_iwencai_metric("15分钟 5日线 10日线 20日线 60日线 向上发散")
        m5_hs300 = self._fetch_iwencai_metric("沪深300 涨跌幅", value_hints=["涨跌幅"])
        m5_zz500 = self._fetch_iwencai_metric("中证500 涨跌幅", value_hints=["涨跌幅"])
        m5_kc30 = self._fetch_iwencai_metric("科创30 涨跌幅", value_hints=["涨跌幅"])
        vals = [m5_hs300.get("value"), m5_zz500.get("value"), m5_kc30.get("value")]
        vals = [v for v in vals if isinstance(v, (int, float))]
        avg5 = float(sum(vals) / len(vals)) if vals else None
        snapshot["metrics"] = {
            "m1_today": {"value": m1_pair.get("today")},
            "m1_yday": {"value": m1_pair.get("yday")},
            "m2_market": m2_market,
            "m3": m3,
            "m4": m4,
            "m5_hs300": m5_hs300,
            "m5_zz500": m5_zz500,
            "m5_kc30": m5_kc30,
            "m5_avg": avg5,
        }
        self._enhance_sentiment_snapshot_with_tushare(snapshot)
        return snapshot


    def _render_sentiment_zone_snapshot(self, data):
        """把快照渲染到第一个页面(情绪总览)。"""
        if not hasattr(self, "sentiment_zone_text_widgets"):
            return
        t = data.get("time", "")
        m = data.get("metrics", {})
        w = self.sentiment_zone_text_widgets.get("overview")
        if w:
            w.config(state=tk.NORMAL)
            w.delete("1.0", tk.END)
            w.insert(tk.END, f"更新时间: {t}\n\n")
            def _fmt_pct(v):
                return f"{v:+.2f}%" if isinstance(v, (int, float)) else "未获取"
            def _fmt_num(v):
                if isinstance(v, (int, float)):
                    if float(v).is_integer():
                        return str(int(v))
                    return f"{v:.2f}"
                return "未获取"
            def _ins_colored_value(v, pct=False):
                if not isinstance(v, (int, float)):
                    w.insert(tk.END, "未获取")
                    return
                s = f"{v:+.2f}%" if pct else (str(int(v)) if float(v).is_integer() else f"{v:.2f}")
                tag = "up_bold" if v >= 0 else "down_bold"
                w.insert(tk.END, s, tag)
            # 结果统一放在"答案:"后同一行
            w.insert(tk.END, "问题1:同花顺情绪指数 当日涨跌幅、昨日涨跌幅? 答案:当日 ")
            _ins_colored_value(m.get("m1_today", {}).get("value"), pct=True)
            w.insert(tk.END, ",昨日 ")
            _ins_colored_value(m.get("m1_yday", {}).get("value"), pct=True)
            w.insert(tk.END, "\n")
            mk = m.get("m2_market") or {}
            up_n = mk.get("up")
            dn_n = mk.get("down")
            flat_n = mk.get("flat")
            tot_n = mk.get("total")
            w.insert(tk.END, "问题2:当日股票涨跌个数各是多少个? 答案:上涨 ")
            _ins_colored_value(up_n, pct=False)
            w.insert(tk.END, " 个,下跌 ")
            _ins_colored_value(dn_n, pct=False)
            w.insert(tk.END, " 个")
            if isinstance(flat_n, (int, float)):
                w.insert(tk.END, ",平盘 ")
                w.insert(tk.END, str(int(flat_n)))
                w.insert(tk.END, " 个")
            if isinstance(tot_n, (int, float)):
                w.insert(tk.END, ",总计 ")
                w.insert(tk.END, str(int(tot_n)))
                w.insert(tk.END, " 个")
            w.insert(tk.END, "\n")
            w.insert(tk.END, f"问题3:股价上穿60分钟周期 60日均线 且放量? 答案:{_fmt_num(m.get('m3', {}).get('count'))}\n")
            # 显示60分钟上穿放量的具体股票列表
            m3_stocks = m.get('m3', {}).get('stocks', [])
            if m3_stocks:
                w.insert(tk.END, "  股票列表:")
                for i, s in enumerate(m3_stocks[:30]):
                    name = s.get('name', '')
                    code = s.get('code', '')
                    # 去掉股票代码中的字母前缀(如SH、SZ)
                    import re
                    code_match = re.search(r'\d{6}', code)
                    clean_code = code_match.group() if code_match else code
                    if name and clean_code:
                        stock_text = f"{name}({clean_code})"
                    elif name:
                        stock_text = name
                    elif clean_code:
                        stock_text = clean_code
                    else:
                        continue
                    tag_name = f"stock_{i}"
                    w.insert(tk.END, stock_text, tag_name)
                    w.tag_configure(tag_name, foreground="#1565c0", underline=True)
                    w.tag_bind(tag_name, "<Double-Button-1>",
                              lambda e, n=name, c=clean_code: self._show_stock_detail_direct(n if n else c, c if c else n, 1))
                    if i < len(m3_stocks[:30]) - 1:
                        w.insert(tk.END, ", ")
                if len(m3_stocks) > 30:
                    w.insert(tk.END, f" ...(共{len(m3_stocks)}只)")
                w.insert(tk.END, "\n")
            w.insert(tk.END, f"问题4:15分钟 5/10/20/60 向上发散? 答案:{_fmt_num(m.get('m4', {}).get('count'))}\n")
            w.insert(tk.END, "问题5:沪深300/中证500/科创30 平均涨跌幅? 答案:沪深300 ")
            _ins_colored_value(m.get("m5_hs300", {}).get("value"), pct=True)
            w.insert(tk.END, ",中证500 ")
            _ins_colored_value(m.get("m5_zz500", {}).get("value"), pct=True)
            w.insert(tk.END, ",科创30 ")
            _ins_colored_value(m.get("m5_kc30", {}).get("value"), pct=True)
            w.insert(tk.END, ",平均 ")
            _ins_colored_value(m.get("m5_avg"), pct=True)
            w.insert(tk.END, "\n")
            # 历史记录(最近15条,由近及远)
            w.insert(tk.END, "\n" + "="*60 + "\n")
            w.insert(tk.END, "历史记录(最近15条)\n")
            w.insert(tk.END, "="*60 + "\n")
            history = self._get_sentiment_history(limit=15)
            if history:
                for idx, record in enumerate(history):
                    w.insert(tk.END, f"\n[{idx+1}] {record['snapshot_time']}\n")
                    w.insert(tk.END, "  情绪指数:当日 ")
                    _ins_colored_value(record.get("m1_today"), pct=True)
                    w.insert(tk.END, ",昨日 ")
                    _ins_colored_value(record.get("m1_yday"), pct=True)
                    w.insert(tk.END, "\n")
                    if record.get("m2_up") is not None:
                        w.insert(tk.END, f"  涨跌家数:上涨 {int(record['m2_up'])} 个,下跌 {int(record['m2_down'])} 个")
                        if record.get("m2_flat") is not None:
                            w.insert(tk.END, f",平盘 {int(record['m2_flat'])} 个")
                        w.insert(tk.END, "\n")
                    if record.get("m3_count") is not None:
                        w.insert(tk.END, f"  60分钟上穿放量:{record['m3_count']} 只\n")
                    if record.get("m4_count") is not None:
                        w.insert(tk.END, f"  15分钟均线发散:{record['m4_count']} 只\n")
                    if record.get("m5_avg") is not None:
                        w.insert(tk.END, "  指数平均涨跌幅:")
                        _ins_colored_value(record.get("m5_avg"), pct=True)
                        w.insert(tk.END, "\n")
            else:
                w.insert(tk.END, "  暂无历史记录\n")
            w.config(state=tk.DISABLED)


    def _refresh_sentiment_zone_tabs_async(self):
        """异步刷新情绪区间标签页。"""
        if not hasattr(self, "sentiment_zone_text_widgets"):
            return
        try:
            self.sentiment_zone_status_var.set("刷新中...")
        except Exception:
            pass
        def work():
            try:
                snap = self._collect_sentiment_zone_snapshot()
                def ui_ok():
                    self._last_sentiment_zone_snapshot = snap
                    self._save_sentiment_snapshot_to_history(snap)
                    self._render_sentiment_zone_snapshot(snap)
                    # 根据涨跌个数更新红绿灯状态
                    metrics = snap.get("metrics", {})
                    m2_market = metrics.get("m2_market", {})
                    up_count = m2_market.get("up")
                    if up_count is not None:
                        if up_count < 1600:
                            self.emotion_cycle_var.set("下行")
                        elif up_count <= 3500:
                            self.emotion_cycle_var.set("震荡")
                        else:
                            self.emotion_cycle_var.set("上行")
                    if hasattr(self, "sentiment_zone_status_var"):
                        self.sentiment_zone_status_var.set(f"已更新 {datetime.now().strftime('%H:%M:%S')}")
                self.root.after(0, ui_ok)
            except Exception as e:
                def ui_err(e=e):
                    if hasattr(self, "sentiment_zone_status_var"):
                        self.sentiment_zone_status_var.set("刷新失败")
                    for w in getattr(self, "sentiment_zone_text_widgets", {}).values():
                        w.config(state=tk.NORMAL)
                        w.delete("1.0", tk.END)
                        w.insert("1.0", f"刷新失败: {e}\n")
                        w.config(state=tk.DISABLED)
                self.root.after(0, ui_err)
        threading.Thread(target=work, daemon=True).start()


    def _draw_sentiment_index_chart(self, parent, index_data):
        """在同花顺情绪指数日线数据上绘制收盘价 + 1日均线(放在日K线图下方)。"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
            data = index_data["data"]
            trade_dates = index_data.get("trade_dates") or list(range(len(data)))
            source = index_data.get("source", "")
            closes = data["收盘"].values
            n = len(closes)
            dates = list(range(n))
            fig = Figure(figsize=(12, 3.5), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(dates, closes, color="gray", linewidth=0.8, label="收盘价", linestyle="--", alpha=0.8)
            ax.plot(dates, closes, color="#FF0000", linewidth=1.5, label="1日均线", alpha=0.9)
            ax.set_title(f"同花顺情绪指数 日线({source})", fontsize=11, fontweight="bold")
            ax.set_xlabel("日期", fontsize=9)
            ax.set_ylabel("指数", fontsize=9)
            ax.legend(loc="upper left", fontsize=8)
            ax.grid(True, alpha=0.3)
            step = max(1, len(trade_dates) // 12)
            ax.set_xticks(dates[::step])
            def _fmt(s):
                if not s or len(s) != 8:
                    return str(s)[:8]
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            ax.set_xticklabels(
                [_fmt(trade_dates[i]) if i < len(trade_dates) else str(i) for i in dates[::step]],
                rotation=45,
                ha="right",
            )
            canvas = FigureCanvasTkAgg(fig, parent)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            ttk.Label(parent, text=f"同花顺情绪指数图绘制失败: {e}", font=("TkDefaultFont", 12), foreground="red").pack(expand=True)



    def _load_crash_rally_events(self):

        """从 crash_rally_events 表读历史暴涨暴跌事件，填充暴跌 Tab 的下半 Treeview

        与 crash_rally_calendar.py 共用同一 SQLite 表，保证内容完全一致"""

        tree = getattr(self, "_crash_events_tree", None)

        if tree is None:

            return

        # 清空现有行

        for item in tree.get_children():

            tree.delete(item)

        label = getattr(self, "_crash_events_count_label", None)

        try:

            import sqlite3

            # 找 DB 路径: 优先 crash_rally_calendar.py 用的 ~/.qclaw/stock_analysis.db

            import os as _os

            qclaw_db = _os.path.join(_os.path.expanduser("~"), ".qclaw", "stock_analysis.db")

            db_path = qclaw_db

            # 如果 qclaw_db 不存在，尝试主程序自己的 db

            if not _os.path.exists(qclaw_db):

                alt_db = getattr(self, "db_path", None) or getattr(self, "DB_PATH", None)

                if alt_db and _os.path.exists(alt_db):

                    db_path = alt_db

                else:

                    if label:

                        label.config(text="⚠ 未找到事件库 DB")

                    return

            conn = sqlite3.connect(db_path)

            cur = conn.cursor()

            # 先确保表存在（幂等建表，同 crash_rally_calendar.py）

            cur.execute("""

                CREATE TABLE IF NOT EXISTS crash_rally_events (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    event_date TEXT, event_type TEXT, index_name TEXT,

                    index_pct REAL, magnitude TEXT, trigger TEXT,

                    trigger_detail TEXT, leading_signals TEXT,

                    signal_days_before INTEGER, recovery_days INTEGER,

                    max_recover_pct REAL, notes TEXT, source_urls TEXT,

                    related_stocks TEXT

                )

            """)

            cur.execute('CREATE INDEX IF NOT EXISTS idx_cr_date ON crash_rally_events(event_date)')

            cur.execute('CREATE INDEX IF NOT EXISTS idx_cr_type ON crash_rally_events(event_type)')

            # 读取

            cur.execute(

                "SELECT id,event_date,event_type,index_name,index_pct,magnitude,trigger "

                "FROM crash_rally_events ORDER BY event_date DESC")

            rows = cur.fetchall()

            conn.close()

            for r in rows:

                eid, date, etype, idx_name, pct, mag, trigger = r

                # 格式化涨跌幅

                pct_str = f"{pct:+.2f}%" if pct is not None else ""

                etype_cn = "暴跌" if etype == "crash" else ("暴涨" if etype == "rally" else str(etype or ""))

                tag = "crash" if etype == "crash" else ("rally" if etype == "rally" else "")

                # id 用字符串存，Treeview selection 返回字符串

                tree.insert("", tk.END, iid=str(eid),

                            values=(date or "", etype_cn, idx_name or "",

                                    pct_str, mag or "", trigger or ""),

                            tags=(tag,) if tag else ())

            if label:

                label.config(text=f"共 {len(rows)} 条 | 源: {db_path}")

        except Exception as e:

            if label:

                label.config(text=f"⚠ 读取事件库失败: {e}")

            print(f"[暴跌Tab] 加载事件库失败: {e}")

    def _open_crash_event_detail(self, event_id_str):

        """双击 Treeview 行 → 打开该暴涨暴跌事件的完整详情"""

        import sqlite3, os as _os

        try:

            eid = int(event_id_str)

        except (ValueError, TypeError):

            return

        qclaw_db = _os.path.join(_os.path.expanduser("~"), ".qclaw", "stock_analysis.db")

        db_path = qclaw_db

        if not _os.path.exists(qclaw_db):

            alt = getattr(self, "db_path", None) or getattr(self, "DB_PATH", None)

            if alt and _os.path.exists(alt):

                db_path = alt

        try:

            conn = sqlite3.connect(db_path)

            cur = conn.cursor()

            cur.execute(

                "SELECT * FROM crash_rally_events WHERE id=?", (eid,))

            row = cur.fetchone()

            cols = [d[0] for d in cur.description]

            conn.close()

            if not row:

                return

            info = dict(zip(cols, row))

            # 格式化显示文本

            lines = []

            lines.append("【暴涨暴跌事件详情】")

            lines.append("=" * 40)

            etype = info.get("event_type", "")

            etype_cn = "暴跌 🟢" if etype == "crash" else ("暴涨 🔴" if etype == "rally" else str(etype))

            lines.append(f"日期:   {info.get('event_date','')}")

            lines.append(f"类型:   {etype_cn}")

            lines.append(f"指数:   {info.get('index_name','')}")

            pct = info.get("index_pct")

            lines.append(f"涨跌幅: {pct:+.2f}%" if pct is not None else "涨跌幅: -")

            lines.append(f"幅度:   {info.get('magnitude','')}")

            lines.append(f"触发:   {info.get('trigger','')}")

            if info.get("trigger_detail"):

                lines.append(f"触发详情:\n  {info['trigger_detail']}")

            if info.get("leading_signals"):

                lines.append(f"提前信号: {info['leading_signals']}")

            sigdays = info.get("signal_days_before")

            if sigdays is not None and sigdays > 0:

                lines.append(f"信号提前: {sigdays} 天")

            recover = info.get("recovery_days")

            if recover is not None:

                if recover < 0:

                    lines.append("收复天数: 未收复")

                else:

                    lines.append(f"收复天数: {recover} 天")

            mr = info.get("max_recover_pct")

            if mr is not None:

                lines.append(f"最大反弹/续跌: {mr:+.2f}%")

            if info.get("notes"):

                lines.append(f"备注: {info['notes']}")

            if info.get("related_stocks"):

                lines.append(f"关联股票: {info['related_stocks']}")

            if info.get("source_urls"):

                urls = str(info["source_urls"]).split("|")

                lines.append("参考来源:")

                for u in urls:

                    u = u.strip()

                    if u:

                        lines.append(f"  {u}")

            content = "\n".join(lines)

            title = f"{etype_cn} {info.get('event_date','')} {info.get('index_name','')}"

            # 复用资讯详情弹窗的智能渲染

            self.open_full_window_viewer_from_content(content, title=title)

        except Exception as e:

            print(f"[暴跌Tab] 打开事件详情失败: {e}")

    def _calc_market_risk_indicators(self):

        """计算今日大盘危险/乐观信号 → (danger_list, opt_list, summary_text)

        每个 list 元素: (bool触发, 名称, 说明)"""

        import requests as _rv, json as _j, math as _math



        danger = []   # [(bool, name, detail)]

        opt = []



        closes = []; volumes = []; dates = []

        try:

            r = _rv.get(

                "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",

                params={"symbol": "sh000001", "scale": "240",

                        "ma": "no", "datalen": "120"},

                timeout=8, headers={"User-Agent": "Mozilla/5.0"})

            if r.status_code == 200 and r.text.strip():

                kl = _j.loads(r.text)

                # 🔧 关键修复: 按日期升序排序 (新浪本来就是旧→新, 这里保险)

                kl.sort(key=lambda x: x.get("day", ""))

                # 过滤掉 "未来" 数据 (盘中测试数据可能含当天未完成K线)

                from datetime import date as _dt_e

                today_str = _dt_e.today().isoformat()

                kl_clean = []

                for k in kl:

                    ds = k.get("day", "")

                    if ds and ds[:10] <= today_str:   # 只留 ≤ 今天的

                        volumes.append(float(k.get("volume", 0)))

                        dates.append(ds[:10])

                        kl_clean.append(k)

                        closes.append(float(k["close"]))

                # (不再单独缓存给快览面板, 已删除)

                pass

        except Exception as _e:

            print(f"[风险信号] 新浪日线拉失败: {_e}", flush=True)



        if len(closes) < 20:

            danger.append((True, "数据不足", f"仅 {len(closes)} 天日线, 信号仅供参考"))

            return danger, opt, "⚠️ 数据不足, 信号仅供参考"



        last = closes[-1]

        ma5 = sum(closes[-5:]) / 5

        ma10 = sum(closes[-10:]) / 10

        ma15 = sum(closes[-15:]) / 15

        ma20 = sum(closes[-20:]) / 20

        ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else None

        ma120 = sum(closes[-120:]) / 120 if len(closes) >= 120 else None



        # 涨跌幅序列

        pct_seq = []

        for i in range(1, len(closes)):

            pct_seq.append(round((closes[i] - closes[i-1]) / closes[i-1] * 100, 2))

        up_days = sum(1 for p in pct_seq[-20:] if p > 0)

        dn_days = sum(1 for p in pct_seq[-20:] if p < 0)

        flat_days = 20 - up_days - dn_days



        # 连跌天数

        max_consec_dn = 0; cur = 0

        for p in pct_seq[-20:]:

            if p < 0: cur += 1; max_consec_dn = max(max_consec_dn, cur)

            else: cur = 0

        # 连涨天数

        max_consec_up = 0; cur = 0

        for p in pct_seq[-20:]:

            if p > 0: cur += 1; max_consec_up = max(max_consec_up, cur)

            else: cur = 0



        # 量能 (近5日均量 vs 前15日均量)

        vol_ratio = 1.0

        if len(volumes) >= 20:

            vol_ratio = sum(volumes[-5:]) / sum(volumes[-20:-5]) if sum(volumes[-20:-5]) > 0 else 1.0



        # ======= 危险信号 =======

        # ① MA 空头排列 (MA5 < MA10 < MA15)

        bear_ma = (ma5 < ma10 < ma15)

        danger.append((bear_ma, "MA 空头排列 (MA5<MA10<MA15)",

                       f"MA5={ma5:.1f} MA10={ma10:.1f} MA15={ma15:.1f}"))



        # ② 上证跌破 MA60 (牛熊线)

        below_ma60 = (ma60 is not None and last < ma60)

        danger.append((below_ma60, "跌破 MA60 牛熊线",

                       f"当前={last:.1f} MA60={ma60:.1f} 偏离={(last-ma60)/ma60*100:+.2f}%"))



        # ③ 连续 3 天缩量 (量能比前一日 < 0.85)

        if len(volumes) >= 4:

            vol_shrink = (volumes[-1] < volumes[-2] * 0.85 and

                          volumes[-2] < volumes[-3] * 0.85 and

                          volumes[-3] < volumes[-4] * 0.85)

        else:

            vol_shrink = False

        danger.append((vol_shrink, "连续3天缩量",

                       f"vol_ratio={vol_ratio:.2f} (近5日均量/前15日均量)"))



        # ④ 近 10 日最大连跌 ≥ 4 天

        danger.append((max_consec_dn >= 4, "近10日连跌≥4天",

                       f"最长连跌 {max_consec_dn} 天"))



        # ⑤ 近 20 日下跌天数 ≥ 15 天

        danger.append((dn_days >= 15, "20日内下跌≥15天 (跌多涨少)",

                       f"涨{up_days}天 跌{dn_days}天 平{flat_days}天"))



        # ⑥ MA15 斜率向下 (近5天 MA15 持续下降)

        if len(closes) >= 20:

            ma15_now = ma15

            ma15_5d_ago = sum(closes[-20:-15]) / 5

            ma15_slope_down = ma15_now < ma15_5d_ago

        else:

            ma15_slope_down = False

        danger.append((ma15_slope_down, "MA15 向下发散",

                       f"MA15 现在={ma15:.1f} 5天前={ma15_5d_ago:.1f}"))



        # ======= 乐观信号 =======

        # ① MA 多头排列 (MA5 > MA10 > MA15 > MA20)

        bull_ma = (ma5 > ma10 > ma15 > ma20)

        opt.append((bull_ma, "MA 多头排列 (MA5>MA10>MA15>MA20)",

                    f"MA5={ma5:.1f} MA10={ma10:.1f} MA15={ma15:.1f}"))



        # ② 上证站稳 MA60

        opt.append((not below_ma60 and ma60 is not None, "站稳 MA60 牛熊线",

                    f"当前={last:.1f} MA60={ma60:.1f} 偏离={(last-ma60)/ma60*100:+.2f}%"))



        # ③ 量能放大 (vol_ratio > 1.3)

        opt.append((vol_ratio > 1.3, "放量上涨 (近5日均量>前15日均量×1.3)",

                    f"vol_ratio={vol_ratio:.2f}"))



        # ④ 近 10 日连涨 ≥ 4 天

        opt.append((max_consec_up >= 4, "近10日连涨≥4天",

                    f"最长连涨 {max_consec_up} 天"))



        # ⑤ 近 20 日上涨天数 ≥ 13 天

        opt.append((up_days >= 13, "20日内上涨≥13天 (涨多跌少)",

                    f"涨{up_days}天 跌{dn_days}天"))



        # ⑥ MA15 斜率向上

        opt.append((not ma15_slope_down and len(closes) >= 20, "MA15 向上发散",

                    f"MA15 现在={ma15:.1f} 5天前={ma15_5d_ago:.1f}"))



        # 综合

        d_count = sum(1 for t, _, _ in danger if t)

        o_count = sum(1 for t, _, _ in opt if t)



        if d_count >= 3 and o_count <= 1:

            summary = f"🚨 危险预警: {d_count} 个危险信号触发 → 建议减仓至 2-3 成"

        elif d_count >= 2 and o_count <= 2:

            summary = f"⚠️ 偏谨慎: {d_count}个危险 / {o_count}个乐观 → 控制仓位 3-5 成"

        elif o_count >= 3 and d_count <= 1:

            summary = f"🎯 积极信号: {o_count} 个乐观信号触发 → 可积极入场 5-8 成"

        elif o_count >= 2 and d_count <= 2:

            summary = f"😊 偏乐观: {o_count}个乐观 / {d_count}个危险 → 可试探 5-6 成"

        else:

            summary = f"⚖️ 中性: {d_count}个危险 / {o_count}个乐观 → 观望为主 3-5 成"



        return danger, opt, summary

    def _refresh_market_risk_panel(self):

        """刷新 大盘危险/乐观 信号面板"""

        try:

            danger, opt, summary = self._calc_market_risk_indicators()



            # 清旧

            for w in self._w_risk_frame.winfo_children(): w.destroy()

            for w in self._w_opt_frame.winfo_children(): w.destroy()



            def _render_list(parent, items, is_danger):

                for triggered, name, detail in items:

                    row = tk.Frame(parent, bg=parent["bg"])

                    row.pack(fill=tk.X, padx=6, pady=1)

                    icon = "🔴" if (is_danger and triggered) else (

                        "🟢" if (not is_danger and triggered) else "⚪")

                    fg = "#C62828" if (is_danger and triggered) else (

                        "#2E7D32" if (not is_danger and triggered) else "#78909C")

                    txt = f"{icon} {name}"

                    tk.Label(row, text=txt, bg=parent["bg"], fg=fg,

                             font=("", 9, "bold" if triggered else "normal"),

                             anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

                    tk.Label(parent, text=f"    {detail}", bg=parent["bg"], fg="#90A4AE",

                             font=("", 8), anchor="w").pack(fill=tk.X, padx=6)



            _render_list(self._w_risk_frame, danger, is_danger=True)

            _render_list(self._w_opt_frame, opt, is_danger=False)



            # 总评

            if summary.startswith("🚨"):

                fg = "#C62828"; bg = "#FFCDD2"

            elif summary.startswith("⚠️"):

                fg = "#E65100"; bg = "#FFE0B2"

            elif summary.startswith("🎯"):

                fg = "#1B5E20"; bg = "#C8E6C9"

            elif summary.startswith("😊"):

                fg = "#2E7D32"; bg = "#E8F5E9"

            else:

                fg = "#333"; bg = "#E0E0E0"

            self._w_risk_summary.config(text=summary, fg=fg, bg=bg)



        except Exception as _e:

            import traceback as _tb; _tb.print_exc()

            print(f"[风险面板] 刷新失败: {_e}", flush=True)



    # 等待仪表盘 · 手动判别按钮 (后台线程, 8秒超时)

    # ════════════════════════════════════════════════════════════════════════

    def _do_risk_check(self):

        """🎯 手动触发判别 - 后台线程拉数据, 8秒超时保护"""

        import threading as _th



        # UI: 按钮禁用 + 状态文字

        try:

            self._btn_risk_check.config(state=tk.DISABLED, text="⏳ 判别中...")

            self._lbl_risk_status.config(text="正在拉新浪日线... (8秒超时)", fg="#1565C0")

        except Exception:

            pass



        def _worker():

            import time as _tm

            t0 = _tm.time()

            try:

                # 1. 大盘危险/乐观信号 (新浪日线, timeout=8)

                danger, opt, summary = self._calc_market_risk_indicators()



                # 2. 情绪周期 + 暴跌温度计 (也走新浪日线, 已加 timeout=8)

                info = {}

                try:

                    info = self._get_crash_alert_snapshot() or {}

                except Exception:

                    pass

                mood_score = self._calc_mood_stage(info)

                avg_drop = self._calc_avg_drop(info)

                alpha_score, alpha_msg = self._calc_alpha_beta_opportunity()



                elapsed = round(_tm.time() - t0, 1)



                # 回到主线程刷新所有 UI

                def _update_ui():

                    try:

                        self._refresh_market_risk_panel()

                        # 三列图形

                        self._w_last_mood_score = mood_score

                        self._w_last_drop = avg_drop

                        self._w_last_alpha_score = alpha_score

                        self._draw_mood_canvas(mood_score)

                        self._draw_thermo_canvas(avg_drop)

                        self._draw_alpha_canvas(alpha_score, alpha_msg)

                        self._w_alpha_detail.config(text=alpha_msg)

                        # 综合决策

                        decision = self._calc_decision()

                        self._show_decision(decision)

                        # 按钮恢复

                        self._btn_risk_check.config(state=tk.NORMAL, text="🎯 判别今日乐观/悲观")

                        self._lbl_risk_status.config(

                            text=f"✅ 判别完成 ({elapsed}s) · {summary[:40]}",

                            fg="#2E7D32")

                    except Exception as _e_ui:

                        self._lbl_risk_status.config(text=f"❌ UI刷新失败: {_e_ui}", fg="#C62828")

                        self._btn_risk_check.config(state=tk.NORMAL)

                self.root.after(0, _update_ui)



            except Exception as _e:

                import traceback as _tb; _tb.print_exc()

                self.root.after(0, lambda: (

                    self._btn_risk_check.config(state=tk.NORMAL, text="🎯 判别今日乐观/悲观"),

                    self._lbl_risk_status.config(

                        text=f"❌ 判别失败: {str(_e)[:50]}", fg="#C62828")))



        _th.Thread(target=_worker, daemon=True).start()

    def _refresh_waiting_dashboard(self):

        """刷新等待 Tab 全部图形化组件（3 个 Canvas + 决策条）"""

        try:

            info = self._get_crash_alert_snapshot()

            self._w_dash_date_label.config(

                text=f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")



            # --- 1) 情绪周期位置 ---

            mood_score, mood_name = self._calc_mood_stage(info)

            self._w_last_mood_score = mood_score

            self._w_last_mood_name = mood_name

            self._draw_mood_canvas(mood_score, mood_name)

            self._w_mood_detail.config(

                text=f"当前情绪: {mood_name}\n"

                     f"三指数20日均跌: {info.get('avg_drop_pct', 0):+.2f}%\n"

                     f"数据源: {info.get('source', '-')}")



            # --- 2) 暴涨暴跌温度计 ---

            avg_drop = info.get('avg_drop_pct', 0) or 0

            self._w_last_avg_drop = avg_drop

            self._draw_thermo_canvas(avg_drop)

            idx_lines = " | ".join(

                f"{k}: {v:+.2f}%" for k, v in info.get('indices', {}).items()

            )

            self._w_crash_detail.config(

                text=f"20日三指数平均: {avg_drop:+.2f}%\n"

                     f"阈值线: -15% 触发暴跌提示\n"

                     f"{idx_lines}")



            # --- 3) α/β 反弹机会雷达 ---

            alpha_score, alpha_msg = self._calc_alpha_beta_opportunity()

            self._w_last_alpha_score = alpha_score

            self._draw_alpha_canvas(alpha_score, alpha_msg)

            self._w_alpha_detail.config(text=alpha_msg)



            # --- 4.5) 大盘危险/乐观信号 ---

            try:

                self._refresh_market_risk_panel()

            except Exception:

                pass



            # --- 5) 综合决策 ---

            verdict, sub, pct, rationale = self._calc_decision(

                mood_score, avg_drop, alpha_score, info)

            self._w_verdict_label.config(text=verdict)

            self._w_verdict_label.config(

                fg="#C62828" if verdict.startswith("🔥") else

                   "#2E7D32" if verdict.startswith("❄") else

                   "#1565C0" if verdict.startswith("🎯") else "#F57F17")

            self._w_verdict_sub.config(text=sub)

            self._w_action_bar["value"] = pct

            self._w_action_pct_label.config(text=f"{pct}%")

            self._w_rationale_text.config(state=tk.NORMAL)

            self._w_rationale_text.delete("1.0", tk.END)

            self._w_rationale_text.insert("1.0", rationale)

            self._w_rationale_text.config(state=tk.DISABLED)



        except Exception as e:

            print(f"[等待仪表盘] 刷新失败: {e}")

            import traceback

            traceback.print_exc()

    def _draw_mood_canvas(self, score, stage_name):

        """在 Canvas 上绘制情绪周期 5 段色带 + 指针 (自适应宽度)"""

        c = self._w_mood_canvas

        c.delete("all")

        W, H = self._canvas_size(c, w_min=200, h_min=80)



        # 色带区域 (居中, 上下留空间给标题和底部说明)

        pad_top = 30

        pad_bot = 25

        band_y0 = pad_top

        band_y1 = H - pad_bot



        segments = self._MOOD_STAGES

        seg_w = W / len(segments)

        for i, (_, name, color) in enumerate(segments):

            x0 = i * seg_w

            x1 = (i + 1) * seg_w

            c.create_rectangle(x0 + 2, band_y0, x1 - 2, band_y1,

                              fill=color, outline="", width=2)

            # 文字标签 (自动选字号)

            font_size = max(8, int(min(12, seg_w / 12)))

            c.create_text((x0 + x1) / 2, (band_y0 + band_y1) / 2, text=name,

                         fill="white", font=("Microsoft YaHei", font_size, "bold"))



        # 指针 (三角形, 指向当前分数)

        ptr_x = max(10, min(W - 10, score * W))

        ptr_h = 10

        c.create_polygon(ptr_x - 6, band_y0 - ptr_h + 2,

                        ptr_x + 6, band_y0 - ptr_h + 2,

                        ptr_x, band_y0,

                        fill="#333", outline="")

        # 当前百分比 (指针上方)

        c.create_text(ptr_x, band_y0 - ptr_h - 8, text=f"{score:.0%}",

                     font=("Microsoft YaHei", 10, "bold"), fill="#333")

        # 底部标题

        c.create_text(W / 2, H - 8,

                     text=f"当前位置: {stage_name}",

                     font=("Microsoft YaHei", 10), fill="#555")

    def _draw_thermo_canvas(self, avg_drop):

        """温度计: -25% 到 +10% (自适应宽度)"""

        c = self._w_thermo_canvas

        c.delete("all")

        W, H = self._canvas_size(c, w_min=150, h_min=100)



        # 让温度计居中 (竖在中央)

        mid_x = W / 2



        # 标尺参数

        min_v, max_v = -25, 10

        bar_w = max(24, min(44, W / 5))

        bar_x0 = mid_x - bar_w / 2

        bar_x1 = mid_x + bar_w / 2

        bar_top = 8

        bar_bot = H - 30

        bar_h = bar_bot - bar_top



        # 外壳

        c.create_rectangle(bar_x0 - 3, bar_top - 8, bar_x1 + 3, bar_bot + 8,

                          fill="#ECEFF1", outline="#90A4AE")



        # 分色区 (从顶到底: 暴涨红 → 正常黄 → 暴跌绿 → 极端暴跌深绿)

        zero_y = bar_bot - (0 - min_v) / (max_v - min_v) * bar_h

        crash_y = bar_bot - (-15 - min_v) / (max_v - min_v) * bar_h

        ext_crash_y = bar_bot - (-20 - min_v) / (max_v - min_v) * bar_h

        normal_y = bar_bot - (-5 - min_v) / (max_v - min_v) * bar_h



        # 自上而下: 暴涨区 (红) → 正常偏热 (浅红) → 正常 (黄) → 轻微跌 (浅黄) → 暴跌 (绿) → 极端 (深绿)

        c.create_rectangle(bar_x0, bar_top, bar_x1, zero_y,

                          fill="#EF5350", outline="")        # 0~+10% 红

        c.create_rectangle(bar_x0, normal_y, bar_x1, zero_y,

                          fill="#FFC107", outline="")        # -5~0% 黄

        c.create_rectangle(bar_x0, crash_y, bar_x1, normal_y,

                          fill="#FFD54F", outline="")        # -15~-5% 浅黄

        c.create_rectangle(bar_x0, ext_crash_y, bar_x1, crash_y,

                          fill="#66BB6A", outline="")        # -20~-15% 浅绿

        c.create_rectangle(bar_x0, bar_bot, bar_x1, ext_crash_y,

                          fill="#2E7D32", outline="")        # <-20% 深绿



        # 当前值标记 (红柱覆盖)

        val_clamp = max(min_v, min(max_v, avg_drop))

        val_y = bar_bot - (val_clamp - min_v) / (max_v - min_v) * bar_h

        if avg_drop <= 0:

            c.create_rectangle(bar_x0, val_y, bar_x1, zero_y,

                              fill="#C62828", outline="")

        else:

            c.create_rectangle(bar_x0, zero_y, bar_x1, val_y,

                              fill="#C62828", outline="")



        # 横线指针 + 数值标签 (左侧)

        marker_y = (val_y + bar_top) / 2

        # 从温度计左侧伸出一条线 + 数值

        left_label_x = bar_x0 - max(50, W / 4) + 10

        right_label_x = bar_x1 + max(20, W / 4) - 10

        c.create_line(bar_x0 - 8, marker_y, bar_x1 + 8, marker_y,

                     fill="#333", width=2)

        c.create_text(right_label_x, marker_y, text=f"{avg_drop:+.2f}%",

                     font=("Microsoft YaHei", 12, "bold"), fill="#C62828")



        # 阈值标注 (左侧竖排)

        for label, val in [("暴涨", +10), ("0%", 0), ("暴跌-15%", -15), ("极值-25%", -25)]:

            ly = bar_bot - (val - min_v) / (max_v - min_v) * bar_h

            c.create_line(bar_x0 - 5, ly, bar_x0, ly, fill="#666")

            c.create_text(bar_x0 - 10, ly, text=label, anchor="e",

                         font=("", 8), fill="#555")



    def _draw_alpha_canvas(self, opp_score, msg_prefix):

        """α/β 反弹机会圆环 (自适应宽度, 居中)"""

        c = self._w_alpha_canvas

        c.delete("all")

        W, H = self._canvas_size(c, w_min=150, h_min=100)



        # 圆环居中

        cx = W / 2

        cy = H / 2 - 5

        r = max(35, min(W, H) / 2 - 20)



        # 颜色映射

        if opp_score >= 60:

            arc_color = "#C62828"

        elif opp_score >= 35:

            arc_color = "#F57C00"

        else:

            arc_color = "#90A4AE"



        # 背景圆 (用 circle 模拟圆环)

        c.create_oval(cx - r, cy - r, cx + r, cy + r,

                     outline="#E0E0E0", width=min(14, r // 3))



        # 机会分圆弧

        angles = opp_score / 100 * 360

        if angles > 0:

            c.create_arc(cx - r, cy - r, cx + r, cy + r,

                        start=90, extent=-angles, style=tk.ARC,

                        outline=arc_color, width=min(14, r // 3))



        # 中心文字

        fs = max(14, min(28, r))

        c.create_text(cx, cy - 2, text=f"{opp_score}",

                     font=("Microsoft YaHei", fs, "bold"), fill=arc_color)

        c.create_text(cx, cy + fs / 2 + 4, text="反弹机会分",

                     font=("", 9), fill="#555")



        # 下方标尺 (紧贴圆环下方)

        bar_y = cy + r + 12

        if bar_y + 14 < H:

            bar_w = min(W - 20, max(80, 2 * r))

            bar_x0 = cx - bar_w / 2

            c.create_rectangle(bar_x0, bar_y, bar_x0 + bar_w, bar_y + 8,

                              fill="#E0E0E0", outline="")

            filled = bar_w * opp_score / 100

            c.create_rectangle(bar_x0, bar_y, bar_x0 + filled, bar_y + 8,

                              fill=arc_color, outline="")

            c.create_text(bar_x0, bar_y - 4, text="低", anchor="w",

                         font=("", 8), fill="#666")

            c.create_text(bar_x0 + bar_w, bar_y - 4, text="高", anchor="e",

                         font=("", 8), fill="#666")

    def _draw_alpha_canvas(self, opp_score, msg_prefix):

        """α/β 反弹机会雷达 — 圆环进度"""

        c = self._w_alpha_canvas

        c.delete("all")

        W = c.winfo_width() or 300

        H = 150

        c.config(width=W)



        # 中心

        cx, cy = W / 2, H / 2 - 10

        r_outer = 55

        r_inner = 40



        # 背景圆环

        c.create_oval(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,

                     outline="#E0E0E0", width=12)



        # 机会分圆环 (从 -90° 顺时针画)

        # opp_score 0~100 → 弧度

        import math

        angles = opp_score / 100 * 360

        # 颜色映射

        if opp_score >= 60:

            arc_color = "#C62828"  # 红 = 机会好

        elif opp_score >= 35:

            arc_color = "#F57C00"  # 橙

        else:

            arc_color = "#90A4AE"  # 灰 = 机会小



        # Tkinter arc 参数: extent 是度数, start=-90 表示 12 点方向

        if angles > 0:

            c.create_arc(cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer,

                        start=90, extent=-angles, style=tk.ARC,

                        outline=arc_color, width=12)



        # 中心文字

        c.create_text(cx, cy - 5, text=f"{opp_score}",

                     font=("Microsoft YaHei", 24, "bold"), fill=arc_color)

        c.create_text(cx, cy + 18, text="反弹机会分",

                     font=("", 9), fill="#555")



        # 下方标尺

        bar_y = H - 30

        c.create_rectangle(20, bar_y, W - 20, bar_y + 8, fill="#E0E0E0", outline="")

        filled = (W - 40) * opp_score / 100

        c.create_rectangle(20, bar_y, 20 + filled, bar_y + 8, fill=arc_color, outline="")

        c.create_text(20, bar_y - 5, text="低", anchor="w", font=("", 8), fill="#666")

        c.create_text(W - 20, bar_y - 5, text="高", anchor="e", font=("", 8), fill="#666")

    def _calc_decision(self, mood_score, avg_drop, alpha_score, info):

        """综合三因素 → 量化决策

        返回 (verdict_label, sub_text, pct_0_100, rationale_text)"""

        # 决策分数 (0=纯等待, 100=积极入场)

        # 情绪分高(乐观→狂热) → 入场意愿高

        # 暴跌深 → 入场意愿高 (左侧)

        # 历史反弹胜率高 → 入场意愿高

        drop_component = 0

        if avg_drop <= -15:

            drop_component = 35  # 暴跌区 → 加仓信号

        elif avg_drop <= -10:

            drop_component = 25

        elif avg_drop <= -5:

            drop_component = 15

        elif avg_drop <= 0:

            drop_component = 8

        else:

            drop_component = max(0, 5 - avg_drop)  # 正涨 → 等回调



        score = int(mood_score * 35 + drop_component + alpha_score * 0.3)

        score = max(5, min(95, score))



        if score >= 70:

            verdict = "🎯 可以积极入场"

            sub = f"建议仓位: 5-8 成 | 关注 β ETF 低位 + α ETF 反弹"

        elif score >= 50:

            verdict = "🎯 可以轻仓试探"

            sub = f"建议仓位: 2-5 成 | 优先 β ETF, 观察 α ETF 方向"

        elif score >= 30:

            verdict = "⏳ 适合等待"

            sub = f"建议仓位: 0-2 成 | 等情绪周期走到 绝望/复苏交界"

        else:

            verdict = "❄️ 观望为主"

            sub = f"建议仓位: 空仓或底仓 | 情绪极热/极冷都不宜追"



        # 构建理由

        reasons = [

            f"【情绪周期】当前 {mood_score:.0%} ({self._MOOD_STAGES[min(4, int(mood_score*5))][1]})",

            f"【20日三指数平均】{avg_drop:+.2f}% {'✅ 触发暴跌提示' if avg_drop <= -15 else '正常区间'}",

            f"【历史反弹胜率】α/β 机会分 {alpha_score}/100",

            f"【数据源】{info.get('source', '-')}",

        ]

        if avg_drop <= -15:

            reasons.append("💡 暴跌阈值已触发 — 左侧分批建仓 β ETF 胜率最高 (参考 2025年7月半导体ETF反弹)")

        if mood_score <= 0.30 and alpha_score >= 40:

            reasons.append("💡 情绪在恐慌/绝望区, 但历史反弹机会分高 — 经典恐慌贪婪反向操作区")

        if mood_score >= 0.75:

            reasons.append("⚠️ 情绪偏狂热, 追高风险大, 建议等回调再进")



        rationale = "\n".join(reasons)

        return verdict, sub, score, rationale




    def _calc_mood_stage(self, info):

        """计算当前情绪阶段 [0.0~1.0]"""

        avg_drop = info.get('avg_drop_pct')

        if avg_drop is None:

            # 无数据 → 默认中间 (复苏)

            return 0.45, "复苏(数据不足)"

        # 映射: -20% → 0.0 (恐慌), 0% → 0.5 (乐观起点), +10% → 1.0 (狂热)

        # 但暴跌后反弹规律: -15% 以下是买入区, -10% 开始复苏

        if avg_drop <= -20:

            return 0.05, "恐慌"

        elif avg_drop <= -15:

            return 0.15, "恐慌末期 (抄底区)"

        elif avg_drop <= -10:

            return 0.30, "绝望 → 复苏 (左侧机会)"

        elif avg_drop <= -5:

            return 0.45, "复苏"

        elif avg_drop <= 0:

            return 0.55, "乐观初期"

        elif avg_drop <= 5:

            return 0.70, "乐观"

        elif avg_drop <= 10:

            return 0.85, "狂热边缘"

        else:

            return 0.95, "狂热 (警惕)"

    def _calc_alpha_beta_opportunity(self):

        """基于 crash_rally_events 历史数据 + α/β 概念, 计算反弹机会分数 [0~100]"""

        import sqlite3, os as _os

        qclaw_db = _os.path.join(_os.path.expanduser("~"), ".qclaw", "stock_analysis.db")

        db_path = qclaw_db

        if not _os.path.exists(qclaw_db):

            alt = getattr(self, "db_path", None) or getattr(self, "DB_PATH", None)

            if alt and _os.path.exists(alt):

                db_path = alt

            else:

                return 30, "⚠ 无事件库,无法计算历史反弹胜率\n(请先打开 🗓️暴涨暴跌 日历 扫描历史事件)"

        try:

            conn = sqlite3.connect(db_path)

            cur = conn.cursor()

            # 统计暴跌事件反弹胜率

            cur.execute(

                "SELECT COUNT(*) FROM crash_rally_events "

                "WHERE event_type='crash' AND index_pct <= -5")

            total_crash = cur.fetchone()[0]

            cur.execute(

                "SELECT COUNT(*) FROM crash_rally_events "

                "WHERE event_type='crash' AND index_pct <= -5 "

                "AND max_recover_pct IS NOT NULL AND max_recover_pct > 0")

            with_recover = cur.fetchone()[0]

            cur.execute(

                "SELECT AVG(max_recover_pct) FROM crash_rally_events "

                "WHERE event_type='crash' AND index_pct <= -5 "

                "AND max_recover_pct IS NOT NULL AND max_recover_pct > 0")

            avg_recover = cur.fetchone()[0] or 0

            conn.close()



            # 机会分 = 反弹胜率 * 0.6 + 平均反弹幅度映射 * 0.4

            win_rate = with_recover / max(1, total_crash)

            # 平均反弹 0% → 0, 30% → 100

            recover_score = min(100, avg_recover / 30 * 100) if avg_recover > 0 else 0

            opp_score = int(win_rate * 60 + recover_score * 0.4)



            msg = (f"📊 历史暴跌事件: {total_crash} 次\n"

                   f"📈 反弹胜率: {win_rate:.0%}  ({with_recover}/{total_crash})\n"

                   f"💹 平均反弹幅度: {avg_recover:+.1f}%\n"

                   f"\n🎯 β ETF 低位机会: 指数暴跌后, 被动 β ETF(沪深300ETF/科创50ETF)\n"

                   f"   反弹胜率高于个股 (2025年7月半导体/科创ETF反弹经典案例)\n"

                   f"🎯 α ETF 机会: 行业 α ETF (如半导体/AI/创新药ETF)\n"

                   f"   暴跌后弹性更大, 但需配合情绪周期位置")

            return opp_score, msg

        except Exception as e:

            return 20, f"⚠ 计算历史反弹数据失败: {e}"




    def _update_waiting_combo_values(self):

        combos = getattr(self, "waiting_combo_widgets", None)

        if not combos:

            return

        options = getattr(self, "managed_stock_names", []) or []

        values = options[-100:]

        for combo in combos:

            current = combo.get()

            combo["values"] = values

            if current and current in values:

                combo.set(current)


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


    def _refresh_crash_alert_display(self):

        """刷新暴跌标签页显示 (实时快照 + 历史事件库)"""

        info = self._get_crash_alert_snapshot()

        txt = getattr(self, "crash_alert_text_widget", None)

        if txt is not None:

            try:

                txt.config(state=tk.NORMAL)

                txt.delete("1.0", tk.END)

                txt.insert(tk.END, "【暴跌判定规则】最近20交易日,上证300/中证500/科创30(科创50近似)平均跌幅 <= -15%\n\n")

                for k, v in info.get("indices", {}).items():

                    txt.insert(tk.END, f"{k}: {v:+.2f}%\n")

                extra = info.get("extra_indices", {})

                if extra:

                    txt.insert(tk.END, "\n【附加指数20天涨跌幅】\n")

                    for k, v in extra.items():

                        txt.insert(tk.END, f"{k}: {v:+.2f}%\n")

                avg = info.get("avg_drop_pct")

                if avg is None:

                    txt.insert(tk.END, "\n平均跌幅: 未获取(请检查数据源/网络)\n")

                    txt.insert(tk.END, f"数据源: {info.get('source', '未获取')}\n")

                else:

                    txt.insert(tk.END, f"\n平均跌幅: {avg:+.2f}%\n")

                    txt.insert(tk.END, f"数据源: {info.get('source', '未获取')}\n")

                    if info.get("is_crash"):

                        txt.insert(tk.END, "状态: 触发暴跌提示(记录暴跌转折时刻)\n")

                    else:

                        txt.insert(tk.END, "状态: 未触发暴跌提示\n")

                txt.config(state=tk.DISABLED)

            except Exception as e:

                print(f"[暴跌提示] 刷新快照失败: {e}")

        # 同时刷新下半部分历史事件库

        try:

            self._load_crash_rally_events()

        except Exception as e:

            print(f"[暴跌提示] 刷新事件库失败: {e}")



    # ════════════════════════════════════════════════════════════════════════

    # 等待 Tab —— 图形化决策仪表盘 (核心方法)

    # ════════════════════════════════════════════════════════════════════════

    # 情绪周期 5 阶段定义

    _MOOD_STAGES = [

        (0.00, "恐慌", "#2E7D32"),    # 绿色

        (0.20, "绝望", "#1565C0"),    # 深蓝

        (0.40, "复苏", "#F9A825"),    # 黄

        (0.60, "乐观", "#FB8C00"),    # 橙

        (0.80, "狂热", "#C62828"),    # 红

    ]



    # ════════════════════════════════════════════════════════════════════════

    # 等待仪表盘 · 大盘危险/乐观信号 (基于新浪上证指数日线)

    # ════════════════════════════════════════════════════════════════════════


    def _canvas_size(self, canvas, w_min=200, h_min=80):

        """从 Canvas 取实际宽高, 未布局完成时用 min 值"""

        try:

            w = max(w_min, canvas.winfo_width())

            h = max(h_min, canvas.winfo_height())

        except Exception:

            w, h = w_min, h_min

        return w, h


    def _open_alpha_beta_dialog(self):

        """📐 α/β 阿尔法贝塔 — 调出 alpha_beta_dialog.py"""

        try:

            import sys as _sys_ab, os as _os_ab

            _this_dir = _os_ab.path.dirname(_os_ab.path.abspath(__file__)) if "__file__" in dir() else ""

            if _this_dir and _this_dir not in _sys_ab.path:

                _sys_ab.path.insert(0, _this_dir)

            from alpha_beta_dialog import open_alpha_beta_dialog

            open_alpha_beta_dialog(getattr(self, "root", None))

        except Exception as _e_ab:

            print(f"[大盘] 📐 α/β 阿尔法贝塔启动失败: {_e_ab}", flush=True)

            try:

                import tkinter.messagebox as _mb

                _mb.showerror("📐 α/β 阿尔法贝塔启动失败",

                              f"{_e_ab}\n\n请确认 alpha_beta_dialog.py 在 src/ 目录下")

            except Exception:

                pass


    def _gather_ai_staff_risk_context(self):

        """风控员:强制使用联网实时大盘与情绪数据,并附风控补充。"""

        parts = []

        parts.append(self._gather_ai_staff_analyst_context())

        parts.append("\n【风控专用补充 · 指数近日收盘(上证)】\n")

        try:

            import akshare as ak

            df = ak.index_zh_a_hist(symbol="000001", period="daily")

            if df is not None and not df.empty:

                tail = df.tail(8)

                parts.append(tail.to_string(index=False))

            else:

                parts.append("(无)")

        except Exception as e:

            parts.append(f"(失败:{e})")

        return "\n".join(parts)


    def _draw_daily_kline_chart(self, parent, kline_data, stock_name, embed_zoom_handler=True):

        """绘制日K线图(Tushare),含均线与支撑/压力线;双击可弹出最大化查看。"""

        try:

            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(12, 6))

            canvas = FigureCanvasTkAgg(fig, parent)

            canvas.draw()

            w = canvas.get_tk_widget()

            w.pack(fill=tk.BOTH, expand=True)

            if embed_zoom_handler:

                w.bind("<Double-Button-1>", lambda e: self._show_daily_kline_zoom(kline_data, stock_name))

        except Exception as e:

            print(f"绘制日K线图失败: {e}")

            import traceback

            traceback.print_exc()

            error_label = ttk.Label(parent, text=f"绘制日K线图失败: {e}", font=("TkDefaultFont", 12), foreground="red")

            error_label.pack(expand=True)


    def _draw_15min_kline_chart(self, parent, kline_data, stock_name):

        """绘制15分钟K线图,包含1日、3日、5日、10日、20日均线"""

        try:

            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            from matplotlib.figure import Figure

            # 创建图表

            fig = Figure(figsize=(12, 6), dpi=100)

            ax = fig.add_subplot(111)

            data = kline_data['data']

            ma_values = kline_data['ma_values']

            # 准备K线数据

            dates = list(range(len(data)))  # 使用索引作为x轴

            if '开盘' in data.columns:

                opens = data['开盘'].values

                closes = data['收盘'].values

                highs = data['最高'].values

                lows = data['最低'].values

            else:

                # 如果列名不同,尝试使用位置索引

                opens = data.iloc[:, 1].values if len(data.columns) > 1 else data.iloc[:, 0].values

                closes = data.iloc[:, 2].values if len(data.columns) > 2 else data.iloc[:, 0].values

                highs = data.iloc[:, 3].values if len(data.columns) > 3 else data.iloc[:, 0].values

                lows = data.iloc[:, 4].values if len(data.columns) > 4 else data.iloc[:, 0].values

            # 绘制K线(使用蜡烛图样式)

            for i in range(len(dates)):

                color = 'red' if closes[i] >= opens[i] else 'green'

                # 绘制实体(开盘到收盘)

                body_bottom = min(opens[i], closes[i])

                body_top = max(opens[i], closes[i])

                ax.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)

                # 绘制上下影线

                ax.plot([i, i], [lows[i], body_bottom], color=color, linewidth=1)

                ax.plot([i, i], [body_top, highs[i]], color=color, linewidth=1)

            # 绘制收盘价折线(辅助线)

            ax.plot(dates, closes, color='black', linewidth=0.5, label='收盘价', alpha=0.5, linestyle='--')

            # 绘制均线(不同颜色)

            ma_colors = {

                'ma1': '#FF0000',   # 红色

                'ma3': '#FFA500',   # 橙色

                'ma5': '#00FF00',   # 绿色

                'ma10': '#0000FF',  # 蓝色

                'ma20': '#FF00FF'   # 紫色

            }

            ma_labels = {

                'ma1': '1日均线',

                'ma3': '3日均线',

                'ma5': '5日均线',

                'ma10': '10日均线',

                'ma20': '20日均线'

            }

            period_map = {

                'ma1': 16,

                'ma3': 48,

                'ma5': 80,

                'ma10': 160,

                'ma20': 320

            }

            for ma_name in ['ma1', 'ma3', 'ma5', 'ma10', 'ma20']:

                if ma_name in ma_values and len(ma_values[ma_name]) > 0:

                    ma_data = ma_values[ma_name]

                    # 对齐日期(均线数据从period-1开始)

                    period = period_map[ma_name]

                    start_idx = min(period-1, len(dates)-1)

                    # 创建对应的x轴索引

                    ma_indices = list(range(start_idx, start_idx + len(ma_data)))

                    # 确保数据长度一致

                    min_len = min(len(ma_indices), len(ma_data))

                    if min_len > 0:

                        ax.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],

                               linewidth=1.5, label=ma_labels[ma_name], alpha=0.8)

            ax.set_title(f"{stock_name} - 15分钟K线图(10日周期)", fontsize=12, fontweight='bold')

            ax.set_xlabel("K线序号", fontsize=10)

            ax.set_ylabel("价格", fontsize=10)

            ax.legend(loc='upper left', fontsize=8)

            ax.grid(True, alpha=0.3)

            # 设置x轴刻度(显示部分时间点)

            if len(dates) > 0:

                step = max(1, len(dates) // 10)  # 显示约10个刻度

                ax.set_xticks(dates[::step])

                ax.set_xticklabels([f"K{i+1}" for i in dates[::step]], rotation=45, ha='right')

            # 将图表嵌入到tkinter

            canvas = FigureCanvasTkAgg(fig, parent)

            canvas.draw()

            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        except Exception as e:

            print(f"绘制K线图失败: {e}")

            import traceback

            traceback.print_exc()

            error_label = ttk.Label(parent,

                                   text=f"绘制K线图失败: {e}",

                                   font=("TkDefaultFont", 12),

                                   foreground="red")

            error_label.pack(expand=True)


    def _risk_filter_stock(self, stock_code, stock_name="", kline_data=None, fundamental=None):

        """T5: 全局风控过滤器"""

        result = {"pass": True, "reasons": [], "warnings": []}

        try:

            close_price = None

            if kline_data and kline_data.get('data') is not None:

                df = kline_data['data']

                if len(df) > 0:

                    close_price = float(df['收盘'].values[-1])

            if close_price is not None and close_price < 20:

                result["pass"] = False

                result["reasons"].append(f"股价{close_price:.2f}元<20元,不满足硬标准")

            if kline_data and kline_data.get('data') is not None:

                df = kline_data['data']

                if len(df) >= 60:

                    closes = df['收盘'].values

                    pct_change = (closes[-1] / closes[-60] - 1) * 100

                    if pct_change > 100:

                        result["pass"] = False

                        result["reasons"].append(f"近60日涨幅{pct_change:.1f}%>100%,回避")

                    elif pct_change > 50:

                        result["warnings"].append(f"近60日涨幅{pct_change:.1f}%较高,注意风险")

            if kline_data and kline_data.get('data') is not None:

                p_phase = self._p_phase_classify(kline_data)

                if p_phase.get("phase") == "P3":

                    result["pass"] = False

                    result["reasons"].append("P3狂热期(出货区),不碰")

                elif p_phase.get("phase") == "P0":

                    result["warnings"].append("P0衰退期,需谨慎")

            if fundamental and isinstance(fundamental, dict):

                market_cap = fundamental.get("market_cap", 0)

                if market_cap and market_cap < 100e8:

                    result["warnings"].append(f"市值{market_cap/1e8:.0f}亿<100亿,偏小盘")

                revenue_growth = fundamental.get("revenue_growth", 0)

                if revenue_growth and revenue_growth < 15:

                    result["warnings"].append(f"营收增长{revenue_growth:.1f}%<15%")

        except Exception as e:

            result["warnings"].append(f"风控检查异常: {e}")

        return result


    def _show_market_risk_dashboard(self):

        """🚦 大盘风险仪表盘：估值+杠杆+量能+利率 四维度打分，输出逃顶/抄底信号"""

        import subprocess as _sp

        import tkinter as tk

        from tkinter import scrolledtext, ttk

        win = self._toplevel(self.root)

        win.title("🚦 大盘风险仪表盘 · 逃顶/抄底")

        win.geometry("1200x820")

        win.transient(self.root)

        # ===== 顶部 Banner（风险等级配色）=====

        banner = tk.Frame(win, bg="#2F4F4F", height=60)

        banner.pack(fill=tk.X)

        banner.pack_propagate(False)

        bi = tk.Frame(banner, bg="#2F4F4F")

        bi.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        tk.Label(bi, text="🚦 大盘风险仪表盘", font=("", 16, "bold"),

                 fg="white", bg="#2F4F4F").pack(side=tk.LEFT)

        risk_score_lbl = tk.Label(bi, text="--", font=("", 22, "bold"),

                                   fg="#FFD700", bg="#2F4F4F")

        risk_score_lbl.pack(side=tk.LEFT, padx=14)

        risk_level_lbl = tk.Label(bi, text="--", font=("", 14, "bold"),

                                   fg="white", bg="#2F4F4F")

        risk_level_lbl.pack(side=tk.LEFT)

        risk_action_lbl = tk.Label(bi, text="", font=("", 11),

                                    fg="#AAA", bg="#2F4F4F")

        risk_action_lbl.pack(side=tk.LEFT, padx=12)

        # ===== 控制栏 =====

        ctrl = tk.Frame(win)

        ctrl.pack(fill=tk.X, padx=10, pady=6)

        # 日期选择器

        import datetime as _dt3

        _today = _dt3.date.today().strftime("%Y-%m-%d")

        tk.Label(ctrl, text="📅 选择日期:", fg="#555").pack(side=tk.LEFT)

        date_var = tk.StringVar(value=_today)

        date_entry = tk.Entry(ctrl, textvariable=date_var, width=12, font=("", 11))

        date_entry.pack(side=tk.LEFT, padx=2)

        tk.Label(ctrl, text="(YYYY-MM-DD)", fg="#999", font=("", 9)).pack(side=tk.LEFT)

        trade_day_lbl = tk.Label(ctrl, text="", fg="#1565C0", font=("", 10))

        trade_day_lbl.pack(side=tk.LEFT, padx=6)

        # 快速跳转

        def _set_date(days_ago):

            d = _dt3.date.today() - _dt3.timedelta(days=days_ago)

            date_var.set(d.strftime("%Y-%m-%d"))

        tk.Button(ctrl, text="今天", command=lambda: _set_date(0), cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(ctrl, text="5天前", command=lambda: _set_date(5), cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(ctrl, text="1月前", command=lambda: _set_date(30), cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(ctrl, text="3月前", command=lambda: _set_date(90), cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Label(ctrl, text="  |  ", fg="#CCC").pack(side=tk.LEFT)

        run_btn = tk.Button(ctrl, text="🔍 拉取数据 + 计算风险",

                            font=("", 11, "bold"), bg="#2F4F4F", fg="white",

                            padx=12, pady=3, cursor="hand2")

        run_btn.pack(side=tk.LEFT, padx=4)

        tk.Label(ctrl, text="四维度共振打分：估值40% + 杠杆25% + 量能20% + 利率15%",

                 fg="#666").pack(side=tk.LEFT, padx=14)

        # ===== 主内容区 =====

        main_frame = ttk.Frame(win)

        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        # 左：4 维度条形图 + 原始数据卡片

        left = ttk.LabelFrame(main_frame, text="📊 四维度打分（共振越强越危险）", padding=8)

        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        dims_frame = tk.Frame(left, bg="white")

        dims_frame.pack(fill=tk.X, pady=(0, 10))

        # 动态创建维度条

        dim_widgets = {}  # name -> (canvas, score_lbl, desc_lbl)

        def _add_dim_row(parent, name, max_score, weight_color):

            row = tk.Frame(parent, bg="white")

            row.pack(fill=tk.X, pady=6)

            tk.Label(row, text=f"  {name}", font=("", 11, "bold"),

                     bg="white", width=8, anchor="w", fg="#333").pack(side=tk.LEFT)

            canvas = tk.Canvas(row, height=26, bg="#EEE", highlightthickness=0, width=400)

            canvas.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)

            score_lbl = tk.Label(row, text="0/0", font=("", 11, "bold"),

                                  bg="white", fg="#555", width=8, anchor="e")

            score_lbl.pack(side=tk.LEFT, padx=4)

            desc_lbl = tk.Label(row, text="", font=("", 10), bg="white", fg="#888", width=22, anchor="e")

            desc_lbl.pack(side=tk.LEFT)

            dim_widgets[name] = (canvas, score_lbl, desc_lbl, max_score)

            return canvas

        _add_dim_row(dims_frame, "估值", 40, "#1976D2")

        _add_dim_row(dims_frame, "杠杆", 25, "#FF9800")

        _add_dim_row(dims_frame, "量能", 20, "#4CAF50")

        _add_dim_row(dims_frame, "利率", 15, "#9C27B0")

        # 原始数据卡片

        raw_card = tk.Frame(left, bg="#F5F5DC")

        raw_card.pack(fill=tk.BOTH, expand=True)

        ttk.Label(raw_card, text="📋 原始数据", font=("", 11, "bold")).pack(anchor=tk.W, padx=8, pady=(6, 2))

        raw_txt = scrolledtext.ScrolledText(raw_card, wrap=tk.WORD, height=12,

                                             font=("Menlo", 10), bg="#FDFBF0")

        raw_txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # 右：报告 + 逃顶/抄底方法论

        right = ttk.LabelFrame(main_frame, text="📝 分析报告 + 逃顶/抄底方法论", padding=8)

        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        report_txt = scrolledtext.ScrolledText(right, wrap=tk.WORD,

                                                font=("Microsoft YaHei", 10))

        report_txt.pack(fill=tk.BOTH, expand=True)

        report_txt.insert("1.0",

            "🚦 大盘风险仪表盘 — 四维度共振打分\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            "维度          权重    数据源\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            "💎 估值层      40%    全市场PB 10年分位\n"

            "📈 杠杆层      25%    融资余额 1年分位\n"

            "💰 量能层      20%    两市成交额\n"

            "🏦 利率层      15%    10年国债收益率 5年分位\n"

            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "逃顶组合信号（单一易骗线，共振才行动）：\n"

            "  估值顶  = PE/PB 破历史 90% 分位 + 巴菲特指标>120%\n"

            "  资金顶  = 融资天量 + 新基爆款 + 散户开户暴增\n"

            "  技术顶  = 天量 + 顶背离 + 年线大乖离\n"

            "  政策顶  = 监管降温 + 官媒喊话\n\n"

            "抄底（顶部反向）：\n"

            "  估值底 = PE/PB 历史低位\n"

            "  政策底 = 国家队/降准/重要会议\n"

            "  市场底 = 缩量最后一跌 + 恐慌抛售\n"

            "  情绪底 = 基金冰点 + 销户潮 + 无人谈股\n\n"

            "💡 多维度共振才动手，单一信号容易假突破！\n\n"

            "点击「🔍 拉取最新数据」开始...")

        # ===== 状态条 =====

        status_var = tk.StringVar(value="就绪 · 每周五 16:30 自动跑（cron）")

        ttk.Label(win, textvariable=status_var, anchor=tk.W).pack(fill=tk.X, padx=10, pady=(0, 4))

        # ===== 填充维度条形图 =====

        def _draw_bar(canvas, pct, color="#E74C3C", label=""):

            canvas.delete("all")

            w = canvas.winfo_width() or 400

            h = 26

            canvas.create_rectangle(0, 0, w, h, fill="#F0F0F0", outline="")

            bw = int(w * min(pct, 1.0))

            if bw > 0:

                # 渐变效果：绿→黄→红

                if pct < 0.4: color = "#27AE60"

                elif pct < 0.7: color = "#F39C12"

                else: color = "#E74C3C"

                canvas.create_rectangle(0, 0, bw, h, fill=color, outline="")

            canvas.create_text(w // 2, h // 2, text=label, fill="white", font=("", 10, "bold"))

        def _update_risk_ui(data):

            risk = data.get("risk", {})

            score = risk.get("risk_score", 0)

            level = risk.get("level", "--")

            action = risk.get("action", "")

            # 颜色映射

            if score >= 82: bg, fg = "#8B0000", "#FFD700"       # 极度危险

            elif score >= 65: bg, fg = "#C62828", "white"       # 高风险

            elif score >= 45: bg, fg = "#E67E22", "white"       # 正常偏热

            elif score >= 25: bg, fg = "#27AE60", "white"       # 正常偏低

            else: bg, fg = "#1B5E20", "#FFD700"                 # 底部区域

            banner.configure(bg=bg); bi.configure(bg=bg)

            risk_score_lbl.configure(bg=bg, fg=fg, text=f"{score}")

            risk_level_lbl.configure(bg=bg, fg="white", text=f" [{level}]")

            risk_action_lbl.configure(bg=bg, fg="#FFD700", text=action)

            # 4 维度条形图

            dims = risk.get("dims", {})

            for name, info in dims.items():

                w = dim_widgets.get(name)

                if not w: continue

                canvas, score_lbl, desc_lbl, max_s = w

                sc = info.get("score", 0)

                pct = sc / max_s if max_s else 0

                _draw_bar(canvas, pct, label=f"{sc}/{max_s}  ({pct*100:.0f}%)")

                score_lbl.configure(text=f"{sc}/{max_s}")

                desc_lbl.configure(text=info.get("desc", ""))

            # 原始数据

            raw = data.get("data", {})

            lines = ["═══ 原始数据 ═══", ""]

            # 查询日/实际交易日

            qd = raw.get("query_date", "")

            ad = raw.get("actual_date", "")

            if qd and ad and qd != ad:

                lines.append(f"📅 查询日 {qd} → 实际交易日 {ad}（非交易日自动回退）")

            elif qd == ad:

                lines.append(f"📅 交易日 {qd}")

            lines.append("")

            pb = raw.get("pb", {})

            if pb:

                q_qtl = pb.get('pb_quantile_10y')

                q_str = f"{q_qtl*100:.1f}%" if q_qtl is not None else "N/A"

                lines.append("💎 PB/PE (10年分位):")

                lines.append(f"   上证 {pb.get('close','?')}  PB={pb.get('middlePB','?')}  分位={q_str}")

            margin = raw.get("margin", {})

            if margin:

                m_pct = margin.get('balance_pct_1y')

                m_str = f"{m_pct*100:.1f}%" if m_pct is not None else "N/A"

                lines.append("📈 融资余额:")

                lines.append(f"   沪深合计 {margin.get('balance_total_yi',0):.0f}亿  买入={margin.get('buy_yi',0):.0f}亿  1年分位={m_str}")

            turnover = raw.get("turnover", {})

            if turnover:

                lines.append("💰 两市成交:")

                if turnover.get('total_trillion') is not None:

                    lines.append(f"   沪 {turnover.get('sh_amount_yi',0):.0f}亿 + 深 {turnover.get('sz_amount_yi',0):.0f}亿 = 合计 {turnover.get('total_trillion',0):.2f}万亿")

                else:

                    lines.append(f"   {turnover.get('_note','历史缺失')}")

            bond = raw.get("bond", {})

            if bond:

                b_pct = bond.get('yield_pct_5y')

                b_str = f"{b_pct*100:.1f}%" if b_pct is not None else "N/A"

                lines.append("🏦 10年国债收益率:")

                lines.append(f"   {bond.get('yield_10y',0):.2f}%  5年分位={b_str}")

            lines.append("")

            lines.append(f"⏰ 更新时间: {data.get('time', '?')}")

            raw_txt.delete("1.0", tk.END)

            raw_txt.insert("1.0", "\n".join(lines))

            # 四指数涨跌统计表格

            idx_ret = data.get("index_returns", {})

            for row_id in idx_tv.get_children():

                idx_tv.delete(row_id)

            if idx_ret and "indices" in idx_ret:

                def _pct_fmt(v):

                    if v is None: return "—", ""

                    s = f"{v:+.2f}%"

                    tag = "up" if v > 0 else ("down" if v < 0 else "")

                    return s, tag

                for idx_name, info in idx_ret["indices"].items():

                    if "error" in info:

                        idx_tv.insert("", tk.END, values=(idx_name, "ERR", "—", "—", "—", "—"))

                        continue

                    bc = f"{info.get('base_close', 0):.2f}"

                    p5, t5 = _pct_fmt(info.get("5d", {}).get("pct"))

                    p10, t10 = _pct_fmt(info.get("10d", {}).get("pct"))

                    p20, t20 = _pct_fmt(info.get("20d", {}).get("pct"))

                    pnow, tnow = _pct_fmt(info.get("till_now", {}).get("pct"))

                    tags = (t5, t10, t20, tnow)

                    idx_tv.insert("", tk.END, values=(idx_name, bc, p5, p10, p20, pnow), tags=tags)

                idx_tv.tag_configure("up", foreground="#C62828")

                idx_tv.tag_configure("down", foreground="#2E7D32")

            else:

                for _ in range(4):

                    idx_tv.insert("", tk.END, values=("—", "—", "—", "—", "—", "—"))

            # 报告

            report_txt.delete("1.0", tk.END)

            report_txt.insert("1.0", self._format_dashboard_report(data))

        # ===== 四指数涨跌统计表格（嵌入原始数据卡片下方）=====

        idx_card = tk.Frame(left, bg="#E8F5E9")

        idx_card.pack(fill=tk.X, pady=(6, 0))

        tk.Label(idx_card, text="📈 后续涨跌统计（基准日 → +5/+10/+20 交易日 → 至今）",

                 font=("", 10, "bold"), bg="#E8F5E9", fg="#2E7D32").pack(anchor=tk.W, padx=8, pady=(4, 2))

        idx_cols = ("指数", "基准收盘", "+5日", "+10日", "+20日", "至今")

        idx_tv = ttk.Treeview(idx_card, columns=idx_cols, show="headings", height=5)

        for c, w in [("指数", 80), ("基准收盘", 80), ("+5日", 72), ("+10日", 72), ("+20日", 72), ("至今", 72)]:

            idx_tv.heading(c, text=c)

            idx_tv.column(c, width=w, anchor="center")

        idx_tv.pack(fill=tk.X, padx=8, pady=(0, 6))

        # 空行占位

        for _ in range(4):

            idx_tv.insert("", tk.END, values=("—", "—", "—", "—", "—", "—"))

        # ===== 跑 CLI =====

        import threading

        def _run():

            status_var.set("拉取数据中...")

            try:

                cmd = [sys.executable, self.SKILL_DASHBOARD_SCRIPT, "--json"]

                sel_date = date_var.get().strip()

                if sel_date and sel_date != _today:

                    cmd += ["--date", sel_date]

                proc = _sp.run(cmd, capture_output=True, text=True, timeout=90)

                out = proc.stdout.strip()

                i = out.find("{")

                if i < 0:

                    raise RuntimeError(f"无 JSON 输出: {out[:200]}")

                data = json.loads(out[i:])

                # 显示交易日回退提示

                qd = data.get("data", {}).get("query_date", "")

                ad = data.get("data", {}).get("actual_date", "")

                if qd and ad and qd != ad:

                    win.after(0, lambda: trade_day_lbl.configure(

                        text=f"📂 {qd} 为非交易日 → 回退到 {ad}", fg="#E65100"))

                else:

                    win.after(0, lambda: trade_day_lbl.configure(

                        text=f"📂 交易日 {ad}", fg="#1565C0"))

                win.after(0, lambda: _update_risk_ui(data))

                win.after(0, lambda: status_var.set("✅ 完成"))

            except Exception as e:

                win.after(0, lambda e=e: status_var.set(f"❌ 失败: {e}"))

                win.after(0, lambda e=e: report_txt.delete("1.0", tk.END))

                win.after(0, lambda e=e: report_txt.insert("1.0", f"❌ 拉取失败: {e}"))

        run_btn.configure(command=lambda: threading.Thread(target=_run, daemon=True).start())

        # 立即拉一次

        threading.Thread(target=_run, daemon=True).start()




    def _update_etf_col(self, loading_lbl, results, parent_frame):

        """后台 ETF 线程回来后, 销毁 loading 占位 + 渲染 TOP3/BOTTOM3/αβ对比"""

        try:

            # 先 destroy 旧 loading 和其他子组件

            for w in parent_frame.winfo_children():

                w.destroy()



            if not results:

                tk.Label(parent_frame,

                         text="⚠️ 暂无可显示的 ETF 月度数据\n(请检查网络或稍后刷新)",

                         bg="#0D1B2A", fg="#EF5350",

                         font=("", 10), anchor="w", justify=tk.LEFT).pack(fill=tk.X, pady=10)

                return



            results.sort(key=lambda x: x[2], reverse=True)

            top3 = results[:3]

            bot3 = results[-3:][::-1]



            tk.Label(parent_frame, text="🔥 TOP 3 (α机会):",

                     bg="#0D1B2A", fg="#EF5350",

                     font=("", 10, "bold")).pack(anchor="w")

            for en, et, p, d in top3:

                tk.Label(parent_frame,

                         text=f"  {'+' if p > 0 else ''}{p}%  [{et}] {en}  ({d}天)",

                         bg="#0D1B2A", fg="#FFCDD2",

                         font=("", 10), anchor="w").pack(fill=tk.X)



            tk.Label(parent_frame, text="❄️ BOTTOM 3 (错杀α):",

                     bg="#0D1B2A", fg="#66BB6A",

                     font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))

            for en, et, p, d in bot3:

                tk.Label(parent_frame,

                         text=f"  {'+' if p > 0 else ''}{p}%  [{et}] {en}  ({d}天)",

                         bg="#0D1B2A", fg="#C8E6C9",

                         font=("", 10), anchor="w").pack(fill=tk.X)



            # β vs α

            beta_pcts = [x[2] for x in results if x[1] == "β"]

            alpha_pcts = [x[2] for x in results if "α" in x[1]]

            if beta_pcts and alpha_pcts:

                b_avg = round(sum(beta_pcts)/len(beta_pcts), 2)

                a_avg = round(sum(alpha_pcts)/len(alpha_pcts), 2)

                tk.Label(parent_frame,

                         text=f"\n📊 β平均: {'+' if b_avg>0 else ''}{b_avg}%  |  "

                              f"α平均: {'+' if a_avg>0 else ''}{a_avg}%",

                         bg="#0D1B2A", fg="#FFD54F",

                         font=("", 9, "bold")).pack(anchor="w")

                if a_avg > b_avg + 2:

                    tip = "💡 α > β, 本月选股/行业弹性跑赢指数!"

                elif b_avg > a_avg + 2:

                    tip = "💡 β > α, 本月指数行情为主, 大盘ETF稳"

                else:

                    tip = "💡 α≈β, 板块轮动快, 分散配置"

                tk.Label(parent_frame, text=tip,

                         bg="#0D1B2A", fg="#FFD54F",

                         font=("", 9), anchor="w", wraplength=260,

                         justify=tk.LEFT).pack(fill=tk.X, pady=(2, 0))

        except Exception as e:

            print(f"[日历] _update_etf_col 异常 (可能窗口已关闭): {e}", flush=True)



    # ════════════════════════════════════════════════════════════════════════

    # 情绪日历 · 共用的大盘日线拉取 (新浪源)

    # ════════════════════════════════════════════════════════════════════════


    def _render_month_review(self, grid_f, ym, pct_map, close_map):

        """在月历下方追加一个复盘 Text 面板"""

        import sqlite3, os as _os, json as _j_rv

        from datetime import datetime as _dt3



        # 先 destroy 旧面板 (防止重复)

        for child in grid_f.winfo_children():

            if getattr(child, "_is_month_review", False):

                child.destroy()

        row_idx = max(6, (len(pct_map) > 0 and 6 or 6))

        # 根据已渲染的格子数算 row_idx

        row_idx = 6  # 6 行日历后追加



        rev_frame = tk.Frame(grid_f, bg="#0D1B2A")

        rev_frame._is_month_review = True

        rev_frame.grid(row=row_idx, column=0, columnspan=7, sticky="nsew",

                       padx=1, pady=(8, 4))

        rev_frame.grid_propagate(False)  # 允许控制高度



        # 标题栏

        title_f = tk.Frame(rev_frame, bg="#0D1B2A")

        title_f.pack(fill=tk.X, pady=(6, 0), padx=12)

        tk.Label(title_f, text=f"📊 {ym.year} 年 {ym.month} 月 · 大盘复盘",

                 bg="#0D1B2A", fg="#FFD54F",

                 font=("Microsoft YaHei", 13, "bold")).pack(side=tk.LEFT)

        tk.Label(title_f, text="← 本月发生了什么？重大涨跌原因？α/β机会在哪？",

                 bg="#0D1B2A", fg="#78909C", font=("", 9)).pack(side=tk.LEFT, padx=8)



        # 正文 (三栏: 大盘概况 | 重大涨跌 | α/β板块ETF)

        body_f = tk.Frame(rev_frame, bg="#0D1B2A")

        body_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)



        col_frames = [tk.Frame(body_f, bg="#0D1B2A") for _ in range(3)]

        for i, cf in enumerate(col_frames):

            cf.grid(row=0, column=i, sticky="nsew", padx=6, pady=4)

            body_f.grid_columnconfigure(i, weight=1)



        # ======================================================

        # 【列1】大盘概况

        # ======================================================

        lf1 = tk.Label(col_frames[0], text="📈 大盘概况",

                       bg="#0D1B2A", fg="#81D4FA",

                       font=("Microsoft YaHei", 11, "bold"))

        lf1.pack(anchor="w")

        tk.Frame(col_frames[0], bg="#1565C0", height=1).pack(fill=tk.X, pady=(2, 6))



        # 统计

        if pct_map:

            vals = list(pct_map.values())

            up = sum(1 for v in vals if v > 0)

            dn = sum(1 for v in vals if v < 0)

            flat = len(vals) - up - dn

            # 月涨跌幅 (第一根到最后一根)

            sorted_dates = sorted(pct_map.keys())

            first_close = close_map.get(sorted_dates[0], 0)

            last_close = close_map.get(sorted_dates[-1], 0)

            month_pct = round((last_close - first_close) / first_close * 100, 2) if first_close else 0

            # 最大涨跌日

            max_up_date, max_up_val = max(pct_map.items(), key=lambda x: x[1])

            max_dn_date, max_dn_val = min(pct_map.items(), key=lambda x: x[1])

            # 连涨连跌

            cur_streak = 0; max_streak_up = 0; max_streak_dn = 0

            for ds in sorted_dates:

                v = pct_map[ds]

                if v > 0:

                    cur_streak = cur_streak + 1 if cur_streak > 0 else 1

                    max_streak_up = max(max_streak_up, cur_streak)

                elif v < 0:

                    cur_streak = cur_streak - 1 if cur_streak < 0 else -1

                    max_streak_dn = min(max_streak_dn, cur_streak)

                else:

                    cur_streak = 0

        else:

            up = dn = flat = 0; month_pct = 0

            max_up_date = max_up_val = "-"

            max_dn_date = max_dn_val = "-"

            max_streak_up = max_streak_dn = 0



        lines_c1 = [

            f"📅 交易日: {up + dn + flat} 天",

            f"📈 涨: {up}天  📉 跌: {dn}天  ➖ 平: {flat}天",

            f"📊 月涨跌幅: {'+' if month_pct > 0 else ''}{month_pct}%",

            f"🔥 最大单日涨: {max_up_date}  +{max_up_val}%",

            f"❄️ 最大单日跌: {max_dn_date}  {max_dn_val}%",

            f"🔗 最长连涨: {max_streak_up}天  最长连跌: {abs(max_streak_dn)}天",

        ]

        for ln in lines_c1:

            fg = "#EF5350" if "最大单日涨" in ln or "月涨跌幅: +" in ln else (

                "#66BB6A" if "最大单日跌" in ln or "月涨跌幅: -" in ln else "#ECEFF1")

            tk.Label(col_frames[0], text=ln, bg="#0D1B2A", fg=fg,

                     font=("", 10), anchor="w", justify=tk.LEFT).pack(fill=tk.X)



        # ======================================================

        # 【列2】重大涨跌 + 关联 crash_rally_events

        # ======================================================

        lf2 = tk.Label(col_frames[1], text="⚠️ 重大涨跌 & 原因",

                       bg="#0D1B2A", fg="#FF8A65",

                       font=("Microsoft YaHei", 11, "bold"))

        lf2.pack(anchor="w")

        tk.Frame(col_frames[1], bg="#E64A19", height=1).pack(fill=tk.X, pady=(2, 6))



        # 查 crash_rally_events 当月数据

        qclaw_db = _os.path.join(_os.path.expanduser("~"), ".qclaw", "stock_analysis.db")

        crash_events = []

        try:

            if _os.path.exists(qclaw_db):

                conn = sqlite3.connect(qclaw_db)

                cur = conn.cursor()

                cur.execute(

                    "SELECT event_date, event_type, index_name, "

                    "index_pct, magnitude, trigger, trigger_detail "

                    "FROM crash_rally_events "

                    "WHERE event_date LIKE ? "

                    "ORDER BY ABS(index_pct) DESC LIMIT 10",

                    (f"{ym.year:04d}-{ym.month:02d}%",))

                crash_events = cur.fetchall()

                conn.close()

        except Exception as e:

            print(f"[日历] crash_rally 查失败: {e}", flush=True)



        if crash_events:

            for ev in crash_events[:6]:

                edate, etype, ename, epct, emag, etrig, edetail = ev[0], ev[1], ev[2], ev[3], ev[4], ev[5], ev[6]

                icon = "🟢暴跌" if etype == "crash" else "🔴暴涨"

                mag_icon = {"极端":"🚨","刹跌":"⚠️","大涨":"🔥","小涨":"📈","小跌":"📉"}.get(emag, "")

                pct_str = f"{epct:+.2f}%" if epct is not None else "--"

                tk.Label(col_frames[1],

                         text=f"{icon}{mag_icon} {edate[-5:]} {ename} {pct_str}",

                         bg="#0D1B2A", fg="#FFCDD2" if etype == "crash" else "#FFE0B2",

                         font=("", 9, "bold"), anchor="w").pack(fill=tk.X)

                reason = (etrig or edetail or "")[:50]

                if reason:

                    tk.Label(col_frames[1], text=f"  └ {reason}",

                             bg="#0D1B2A", fg="#90A4AE",

                             font=("", 8), anchor="w", wraplength=240,

                             justify=tk.LEFT).pack(fill=tk.X)

        else:

            tk.Label(col_frames[1],

                     text="💡 暂无历史事件记录\n"

                          "(打开 🗓️暴涨暴跌 日历 扫描后自动关联)",

                     bg="#0D1B2A", fg="#78909C",

                     font=("", 9), anchor="w", justify=tk.LEFT).pack(fill=tk.X, pady=4)



        # 自动推导涨跌原因 (通用财经大事件)

        _month_factors = {

            1: ("年末效应", "机构年终做账+跨年资金面变化, 历来震荡加剧"),

            2: ("春节效应", "节前缩量节后反弹, '肥正月瘦二月'"),

            3: ("两会行情", "政策预期+政府工作报告, 稳增长板块活跃"),

            4: ("年报密集披露", "业绩真空期结束, 高送转/一季报行情"),

            5: ("五穷六绝", "历史规律: 5月往往调整, 6月见底"),

            6: ("半年报+美联储议息", "成长股承压, 大盘风格占优"),

            7: ("中报行情", "半导体/科创/消费电子高弹性, 2025年7月经典反弹"),

            8: ("高温+洪涝", "新能源/抗旱/水利异动, 防御板块走强"),

            9: ("开学季+国庆前", "消费复苏预期, 节前缩量调整"),

            10: ("节后修复", "国庆后开门红概率大, 科技成长反弹"),

            11: ("年底吃饭行情", "机构排名战, 热点轮动快"),

            12: ("收官之战", "北向资金+中央经济工作会议, 布局来年"),

        }

        mname, mdesc = _month_factors.get(ym.month, ("",""))

        tk.Label(col_frames[1], text=f"\n📅 季节性: {mname}",

                 bg="#0D1B2A", fg="#B39DDB",

                 font=("", 9, "bold")).pack(anchor="w", pady=(6, 0))

        tk.Label(col_frames[1], text=f"  {mdesc}",

                 bg="#0D1B2A", fg="#90A4AE",

                 font=("", 8), anchor="w", wraplength=240, justify=tk.LEFT).pack(fill=tk.X)



        # ======================================================

        # 【列3】α/β 板块 & ETF 涨跌幅排行 (后台异步加载)

        # ======================================================

        lf3 = tk.Label(col_frames[2], text="🎯 α/β 板块 ETF 月度排行",

                       bg="#0D1B2A", fg="#A5D6A7",

                       font=("Microsoft YaHei", 11, "bold"))

        lf3.pack(anchor="w")

        tk.Frame(col_frames[2], bg="#43A047", height=1).pack(fill=tk.X, pady=(2, 6))



        # 内置 α/β ETF 清单

        _ETF_LIST = [

            ("沪深300ETF", "sh510300", "β"),

            ("科创50ETF",  "sh588000", "α+β"),

            ("中证500ETF", "sh510500", "β"),

            ("半导体ETF",  "sh512760", "α"),

            ("芯片ETF",    "sz159995", "α"),

            ("医药ETF",    "sh512010", "α"),

            ("新能源ETF",  "sh516160", "α"),

            ("红利ETF",    "sh510880", "β"),

            ("黄金ETF",    "sh518880", "α"),

            ("纳指ETF",    "sh513100", "β"),

        ]



        # ETF 月度涨跌幅 (timeout=1s, 全挂则放弃, 不阻塞启动)

        results = []

        import requests as _r_etf, json as _j_etf

        for ename, esym, etype in _ETF_LIST:

            try:

                r = _r_etf.get(

                    "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",

                    params={"symbol": esym, "scale": "240",

                            "ma": "no", "datalen": "120"},

                    timeout=1, headers={"User-Agent": "Mozilla/5.0"})

                if r.status_code == 200 and r.text.strip():

                    kl = _j_etf.loads(r.text)

                    month_kl = [k for k in kl if k.get("day","").startswith(

                        f"{ym.year:04d}-{ym.month:02d}")]

                    if len(month_kl) >= 2:

                        fc = float(month_kl[0]["close"])

                        lc = float(month_kl[-1]["close"])

                        pct = round((lc - fc) / fc * 100, 2)

                        results.append((ename, etype, pct, len(month_kl)))

            except Exception:

                pass



        if not results:

            tk.Label(col_frames[2],

                text="⚠️ 当月 ETF 日线拉取失败 (新浪源不可用)\n可稍后点 🔄 手动刷新",

                bg="#0D1B2A", fg="#78909C",

                font=("", 9), justify=tk.LEFT).pack(anchor="w", pady=4)

        else:

            results.sort(key=lambda x: x[2], reverse=True)

            top3 = results[:3]; bot3 = results[-3:]

            betas = [x[2] for x in results if x[1] == "β"]

            alphas = [x[2] for x in results if x[1] == "α"]

            beta_avg = round(sum(betas) / len(betas), 2) if betas else 0

            alpha_avg = round(sum(alphas) / len(alphas), 2) if alphas else 0



            tk.Label(col_frames[2], text="🔥 涨幅 TOP 3",

                     bg="#0D1B2A", fg="#FF6F00",

                     font=("", 9, "bold")).pack(anchor="w", pady=(4, 0))

            for en, et, pct, _ in top3:

                tk.Label(col_frames[2],

                    text=f"   {en} ({et})  {pct:+.2f}%",

                    bg="#0D1B2A", fg="#FFCDD2" if pct < 0 else "#FFECB3",

                    font=("", 9)).pack(anchor="w")



            tk.Label(col_frames[2], text="❄️ 跌幅 BOTTOM 3",

                     bg="#0D1B2A", fg="#2E7D32",

                     font=("", 9, "bold")).pack(anchor="w", pady=(6, 0))

            for en, et, pct, _ in bot3:

                tk.Label(col_frames[2],

                    text=f"   {en} ({et})  {pct:+.2f}%",

                    bg="#0D1B2A", fg="#C8E6C9" if pct > 0 else "#EF9A9A",

                    font=("", 9)).pack(anchor="w")



            tk.Label(col_frames[2], text=f"📊 β 平均 {beta_avg:+.2f}%  vs  α 平均 {alpha_avg:+.2f}%",

                     bg="#0D1B2A", fg="#81D4FA",

                     font=("", 9, "bold")).pack(anchor="w", pady=(8, 0))

            if alpha_avg > beta_avg + 1:

                tip = "💡 α ETF 弹性更大 (下跌后反弹/上涨时跑赢 β)"

            elif beta_avg > alpha_avg + 1:

                tip = "💡 β ETF 领涨 (大盘 β 行情, 被动指数更强)"

            else:

                tip = "💡 α/β 差距不大, 均衡配置"

            tk.Label(col_frames[2], text=tip, bg="#0D1B2A", fg="#B0BEC5",

                     font=("", 8), wraplength=220, justify=tk.LEFT).pack(anchor="w", pady=(2, 4))



        # 固定高度, 让滚动条能正确工作

        rev_frame.update_idletasks()

        h = rev_frame.winfo_reqheight()

        rev_frame.config(height=max(h, 280))

        print(f"[日历] 📊 复盘面板渲染完成 (height={h})", flush=True)




    def _fetch_month_index_pct(self, ym):

        """拉当月上证指数日线 (新浪源优先, 兜底 AKShare). 返回 (pct_map, close_map)"""

        import requests as _rv_em, json as _j_em, pandas as _pd_em

        from datetime import timedelta as _td_em

        pct_map = {}; close_map = {}

        try:

            r = _rv_em.get(

                "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",

                params={"symbol": "sh000001", "scale": "240",

                        "ma": "no", "datalen": "150"},

                timeout=10, headers={"User-Agent": "Mozilla/5.0"})

            if r.status_code == 200 and r.text.strip():

                kl = _j_em.loads(r.text)

                prev = None

                for k in kl:

                    ds = k.get("day", "")

                    if not ds: continue

                    c = float(k.get("close", 0))

                    close_map[ds] = c

                    if prev and prev > 0:

                        pct_map[ds] = round((c - prev) / prev * 100, 2)

                    prev = c

                # 只保留当月

                ym_str = f"{ym.year:04d}-{ym.month:02d}"

                pct_map = {k: v for k, v in pct_map.items() if k.startswith(ym_str)}

                close_map = {k: v for k, v in close_map.items() if k.startswith(ym_str)}

                print(f"[日历] 📈 新浪源拉到 {len(pct_map)} 天上证日线", flush=True)

        except Exception as _e:

            print(f"[日历] 新浪源失败, 尝试 AKShare: {_e}", flush=True)

            try:

                import akshare as _ak_em

                if ym.month == 12:

                    end_date = ym.replace(year=ym.year + 1, month=1, day=1) - _td_em(days=1)

                else:

                    end_date = ym.replace(month=ym.month + 1, day=1) - _td_em(days=1)

                df = _ak_em.index_zh_a_hist(

                    symbol="000001", period="daily",

                    start_date=ym.replace(day=1).strftime("%Y%m%d"),

                    end_date=end_date.strftime("%Y%m%d"))

                cc = "收盘" if "收盘" in df.columns else "close"

                dc = "日期" if "日期" in df.columns else "date"

                prev = None

                for d, c in zip(df[dc], df[cc].astype(float)):

                    ds = _pd_em.to_datetime(d).strftime("%Y-%m-%d")

                    close_map[ds] = float(c)

                    if prev and prev > 0:

                        pct_map[ds] = round((float(c) - prev) / prev * 100, 2)

                    prev = float(c)

                print(f"[日历] 📈 AKShare 兜底拉到 {len(pct_map)} 天", flush=True)

            except Exception as _e2:

                print(f"[日历] AKShare 也失败: {_e2}", flush=True)

        return pct_map, close_map




    def _fetch_index_daily(self, symbol="sh000001", days=180):
        """从新浪拉指数日K线, 返回 list[dict] (day, open, high, low, close, volume)"""
        import requests as _req, json as _j
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        try:
            r = _req.get(url, params={"symbol": symbol, "scale": 240, "ma": "no", "datalen": days}, timeout=8)
            if r.status_code != 200 or not r.text.strip():
                return []
            data = _j.loads(r.text)
            # 新浪返回字段: day, open, high, low, close, volume
            return sorted(data, key=lambda x: x.get("day", ""))
        except Exception as e:
            print(f"[指数趋势] 拉取 {symbol} 失败: {e}", flush=True)
            return []

    def _sina_to_kline_data(self, sina_list):
        """新浪 list[dict] → _show_daily_kline_zoom 期待的 {"data": DataFrame} 格式"""
        import pandas as _pd
        if not sina_list:
            return None
        rows = []
        for d in sina_list:
            rows.append({
                "日期": d.get("day", ""),
                "开盘": float(d.get("open", 0)),
                "收盘": float(d.get("close", 0)),
                "最高": float(d.get("high", 0)),
                "最低": float(d.get("low", 0)),
                "成交量": float(d.get("volume", 0)),
            })
        df = _pd.DataFrame(rows)
        return {"data": df}

    def _build_index_trend_tab(self, parent):
        """📈 指数趋势 Tab: 上证/深成指/创业板 日K线 + MA1/5/10/20/60 + 双击放大"""
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        INDEX_MAP = {
            # ---- A 股宽基指数 ----
            "上证指数": "sh000001", "深证成指": "sz399001", "创业板指": "sz399006",
            "科创50":   "sh000688", "沪深300":  "sh000300", "上证50":   "sh000016",
            "中证500":  "sh000905", "中证1000": "sh000852",
            # ---- 主题/行业 ETF ----
            "科创ETF":    "sh588000", "半导体ETF":  "sh512760", "黄金ETF":    "sh518880",
            "纳指ETF":    "sh513100", "日经ETF":    "sh513520", "证券ETF":    "sh512880",
            "医药ETF":    "sh512010", "新能源ETF":  "sh515030", "军工ETF":    "sh512660",
            "消费ETF":    "sz159928", "银行ETF":    "sh512800", "红利ETF":    "sh515180",
        }
        MA_PERIODS = [1, 5, 10, 20, 60]
        MA_COLORS = {1: "#FF6B6B", 5: "#4ECDC4", 10: "#FFE66D", 20: "#95E1D3", 60: "#C7CEEA"}

        # ---- 滚动容器 (高度翻倍 + 可拖动) ----
        _wrap = tk.Frame(parent, bg="#1E1E2E")
        _wrap.pack(fill=tk.BOTH, expand=True)
        _wrap_canvas = tk.Canvas(_wrap, highlightthickness=0, borderwidth=0, bg="#1E1E2E")
        _wrap_scroll = ttk.Scrollbar(_wrap, orient=tk.VERTICAL, command=_wrap_canvas.yview)
        _wrap_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        _wrap_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _wrap_canvas.configure(yscrollcommand=_wrap_scroll.set)
        _wrap_inner = tk.Frame(_wrap_canvas, bg="#1E1E2E")
        _wrap_win = _wrap_canvas.create_window((0, 0), window=_wrap_inner, anchor="nw")
        _wrap_inner.bind("<Configure>", lambda e: _wrap_canvas.configure(scrollregion=_wrap_canvas.bbox("all")))
        _wrap_canvas.bind("<Configure>", lambda e: _wrap_canvas.itemconfigure(_wrap_win, width=e.width))
        def _on_wheel(e): _wrap_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        _wrap_canvas.bind_all("<MouseWheel>", _on_wheel)

        # ---- 顶部工具栏 ----
        top = ttk.Frame(_wrap_inner)
        top.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(top, text="指数:").pack(side=tk.LEFT)
        _idx_var = tk.StringVar(value="上证指数")
        ttk.Combobox(top, textvariable=_idx_var, values=list(INDEX_MAP.keys()), state="readonly", width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="🔄 刷新", width=8, command=lambda: _redraw()).pack(side=tk.LEFT, padx=4)
        _days_var = tk.StringVar(value="180")
        ttk.Label(top, text=" 天数:").pack(side=tk.LEFT)
        ttk.Combobox(top, textvariable=_days_var, values=["60", "120", "180", "360"], state="readonly", width=6).pack(side=tk.LEFT, padx=4)
        tk.Label(top, text=" 双击图放大", fg="#FFD54F").pack(side=tk.LEFT, padx=10)
        _status = tk.Label(top, text="", fg="#888")
        _status.pack(side=tk.RIGHT, padx=8)

        # ---- Figure (高度翻倍 4.5 → 9) ----
        fig = plt.Figure(figsize=(8, 9), dpi=100, facecolor="#1E1E2E")
        _canvas = FigureCanvasTkAgg(fig, master=_wrap_inner)
        _canvas.get_tk_widget().pack(fill=tk.X, padx=4, pady=4)
        try:
            _tb = NavigationToolbar2Tk(_canvas, _wrap_inner, pack_toolbar=False)
            _tb.update()
        except Exception:
            pass

        def _ema(data, period):
            """EMA 计算 (长度严格 = len(data))"""
            if len(data) < period:
                return [None] * len(data)
            result = [None] * len(data)
            sma = sum(data[:period]) / period
            result[period - 1] = sma
            k = 2 / (period + 1)
            for i in range(period, len(data)):
                result[i] = data[i] * k + result[i - 1] * (1 - k)
            return result

        def _compute_macd(closes, fast=12, slow=26, signal=9):
            """返回 (dif, dea, macd_bar) 全 float (None→0.0, matplotlib可直接画)"""
            ema_fast = _ema(closes, fast)
            ema_slow = _ema(closes, slow)
            dif = [0.0 if (ema_fast[i] is None or ema_slow[i] is None) else float(ema_fast[i] - ema_slow[i])
                   for i in range(len(closes))]
            # DEA 基于非 None 部分算
            valid_start = next((i for i, v in enumerate(dif) if v != 0.0), len(dif))
            if valid_start < len(dif):
                _dea_series = _ema([v for v in dif[valid_start:]], signal)
                dea = [0.0] * valid_start + [0.0 if v is None else float(v) for v in _dea_series]
            else:
                dea = [0.0] * len(dif)
            macd_bar = [0.0 if dif[i] == 0.0 and i < valid_start else 2.0 * (dif[i] - dea[i])
                        for i in range(len(dif))]
            return dif, dea, macd_bar

        def _draw_axes(ax, ax2, ax3, closes, opens, highs, lows, volumes, days_list, x, show_macd=True):
            """画 K 线 + MA + 成交量 + (可选 MACD)"""
            bar_w = 0.6
            for i in range(len(closes)):
                color = "#EF5350" if closes[i] >= opens[i] else "#66BB6A"
                ax.plot([x[i], x[i]], [lows[i], highs[i]], color=color, linewidth=0.6)
                body_lo, body_hi = min(opens[i], closes[i]), max(opens[i], closes[i])
                ax.bar(x[i], body_hi - body_lo, bottom=body_lo, width=bar_w, color=color, edgecolor=color, linewidth=0.5)
            for ma_p in MA_PERIODS:
                if len(closes) < ma_p: continue
                ma_vals = [None if i + 1 < ma_p else sum(closes[i + 1 - ma_p:i + 1]) / ma_p for i in range(len(closes))]
                ax.plot(x, ma_vals, color=MA_COLORS[ma_p], linewidth=1.2, label=f"MA{ma_p}")
            ax.legend(loc="upper left", fontsize=7, facecolor="#1E1E2E", edgecolor="#444", labelcolor="#FFF", ncol=5)
            ax.set_title("日K (MA 1/5/10/20/60)", color="#FFF", fontsize=11)
            ax.tick_params(colors="#CCC", labelsize=8)
            for sp in ax.spines.values(): sp.set_color("#444")
            ax.grid(True, alpha=0.2, color="#666")
            step = max(1, len(x) // 10)
            ax.set_xticks(x[::step])
            ax.set_xticklabels([days_list[i][5:] for i in range(0, len(x), step)], rotation=30, fontsize=7)

            # 成交量
            ax2.bar(x, volumes, width=bar_w * 0.6, color="#546E7A", alpha=0.4)
            ax2.set_ylim(0, max(volumes) * 3 if volumes else 1)
            ax2.tick_params(colors="#888", labelsize=7)
            ax2.set_ylabel("量", color="#888", fontsize=8)
            ax2.grid(True, alpha=0.1, color="#666")

            # MACD
            if show_macd:
                dif, dea, macd_bar = _compute_macd(closes)
                macd_colors = ["#EF5350" if v >= 0 else "#66BB6A" for v in macd_bar]
                ax3.bar(x, macd_bar, width=bar_w * 0.6, color=macd_colors, alpha=0.7)
                ax3.plot(x, dif, color="#FFD54F", linewidth=1, label="DIF")
                ax3.plot(x, dea, color="#42A5F5", linewidth=1, label="DEA")
                ax3.axhline(0, color="#666", linewidth=0.5)
                ax3.set_ylabel("MACD", color="#888", fontsize=8)
                ax3.tick_params(colors="#888", labelsize=7)
                ax3.legend(loc="upper left", fontsize=7, facecolor="#1E1E2E", edgecolor="#444", labelcolor="#FFF", ncol=3)
                ax3.grid(True, alpha=0.1, color="#666")

        def _redraw():
            name = _idx_var.get(); symbol = INDEX_MAP.get(name, "sh000001")
            try: days = int(_days_var.get())
            except Exception: days = 180
            _status.config(text=f"拉取 {name} ({symbol})...", fg="#42A5F5"); _wrap.update_idletasks()
            data = self._fetch_index_daily(symbol, days)
            if not data: _status.config(text="❌ 拉取失败", fg="#EF5350"); return

            days_list = [d["day"] for d in data]
            closes = [float(d["close"]) for d in data]; opens = [float(d["open"]) for d in data]
            highs = [float(d["high"]) for d in data]; lows = [float(d["low"]) for d in data]
            volumes = [float(d.get("volume", 0)) for d in data]; x = list(range(len(closes)))

            fig.clear()
            gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.3)
            ax = fig.add_subplot(gs[0], facecolor="#1E1E2E")
            ax2 = fig.add_subplot(gs[1], facecolor="#1E1E2E", sharex=ax)
            ax3 = fig.add_subplot(gs[2], facecolor="#1E1E2E", sharex=ax)
            _draw_axes(ax, ax2, ax3, closes, opens, highs, lows, volumes, days_list, x, show_macd=True)
            fig.suptitle(f"{name} 日K线图 ({days_list[0]} ~ {days_list[-1]})", color="#FFF", fontsize=13, y=0.99)
            _canvas.draw_idle()

            last, prev = closes[-1], closes[-2] if len(closes) >= 2 else closes[-1]
            pct = (last - prev) / prev * 100 if prev else 0
            _status.config(text=f"✅ {name}  收盘:{last:.2f}  {'+' if pct > 0 else ''}{pct:.2f}%  ({days_list[-1]})",
                           fg="#EF5350" if pct >= 0 else "#66BB6A")

            # 存数据给双击放大用
            _last_data["name"] = name; _last_data["symbol"] = symbol
            _last_data["days"] = days; _last_data["data"] = data

        _last_data = {}

        def _show_large(e):
            """双击 → 自画的指数日K线大弹窗 (不复用持仓股 Dialog)"""
            symbol = _last_data.get("symbol")
            days = _last_data.get("days", 180)
            if not symbol: return
            self._show_index_kline_dialog(initial_symbol=symbol, initial_days=days)

        # 绑定双击
        _canvas.get_tk_widget().bind("<Double-Button-1>", _show_large)

        import threading as _th
        _th.Thread(target=_redraw, daemon=True).start()


    # 机构公私募知识体系 · 2026 版
    # ─────────────────────────────────────────────────────────────
    def _show_institution_dialog(self):
        """🏛️ 机构公私募完整体系图形化面板 (Tab 式)"""
        import tkinter as tk
        win = tk.Toplevel(self.root)
        win.title("🏛️ 机构 / 公募 / 私募 完整体系 (2026 版)")
        win.geometry("1280x820")
        win.configure(bg="#1E1E2E")
        try: win.state("zoomed")
        except Exception: pass

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        def _mk_scrollable_tab(nb_, tab_title):
            tab = ttk.Frame(nb_)
            nb_.add(tab, text=tab_title)
            cv = tk.Canvas(tab, highlightthickness=0, borderwidth=0, bg="#1E1E2E")
            sb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=cv.yview)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            cv.configure(yscrollcommand=sb.set, bg="#1E1E2E")
            inner = ttk.Frame(cv, padding=8)
            win_id = cv.create_window((0, 0), window=inner, anchor="nw")
            def _on_cv_cfg(e): cv.itemconfigure(win_id, width=e.width)
            def _on_in_cfg(e): cv.configure(scrollregion=cv.bbox("all"))
            cv.bind("<Configure>", _on_cv_cfg)
            inner.bind("<Configure>", _on_in_cfg)
            def _wheel(e): cv.yview_scroll(int(-1 * (e.delta / 120)), "units")
            cv.bind_all("<MouseWheel>", _wheel)
            return inner

        # ── Tab 1: 系统层 (工具链) ──
        t1 = _mk_scrollable_tab(nb, "🧰 系统层 · 工具链")
        _T = ttk.LabelFrame(t1, text="交易/执行", padding=8)
        _T.pack(fill=tk.X, pady=4)
        tools_trade = [
            ("恒生 O32 / O45", "公募/券商资管 OMS 三巨头, 机构主流订单管理系统", "https://www.hundsun.com"),
            ("金证 / 顶点", "券商资管备选 OMS, 部分私募也用", "https://www.kingdom.com.cn"),
            ("宽睿 / 华锐 ATP", "券商极速柜台, 量化交易通道", "https://www.huarui-tech.com"),
            ("迅投 QMT / MiniQMT", "本地跑 Python 自由, 源码不外泄, 需 24h 开机", "https://www.thinktrader.net"),
            ("恒生 PTrade", "券商云托管零代码模板, Python 沙箱受限, 无期权期货", "https://www.hundsun.com"),
        ]
        for name, desc, link in tools_trade:
            row = ttk.Frame(_T); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"🔹 {name}", font=("Helvetica", 11, "bold"), foreground="#42A5F5").pack(side=tk.LEFT)
            ttk.Label(row, text=f" — {desc}", foreground="#AAAAAA").pack(side=tk.LEFT, fill=tk.X, expand=True)
            if link:
                link_lbl = ttk.Label(row, text="🔗 官网", foreground="#64B5F6", cursor="hand2")
                link_lbl.pack(side=tk.RIGHT)
                def _open(url=link): webbrowser.open(url)
                link_lbl.bind("<Button-1>", lambda e, u=link: webbrowser.open(u))

        _T2 = ttk.LabelFrame(t1, text="投研 / 回测", padding=8)
        _T2.pack(fill=tk.X, pady=4)
        tools_research = [
            ("聚宽 JoinQuant", "国内顶级量化回测平台, 因子库丰富", "https://www.joinquant.com"),
            ("米筐 RiceQuant", "券商级回测, RQAlpha 引擎", "https://www.ricequant.com"),
            ("优矿 Uqer", "通联数据旗下, 因子挖掘友好", "https://uqer.datayes.com"),
            ("掘金 Quant", "本地/云双模式, C++ 撮合引擎", "https://www.myquant.cn"),
            ("BigQuant", "AI 量化选股平台", "https://www.bigquant.com"),
        ]
        for name, desc, link in tools_research:
            row = ttk.Frame(_T2); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"🔹 {name}", font=("Helvetica", 11, "bold"), foreground="#AB47BC").pack(side=tk.LEFT)
            ttk.Label(row, text=f" — {desc}", foreground="#AAAAAA").pack(side=tk.LEFT, fill=tk.X, expand=True)
            link_lbl = ttk.Label(row, text="🔗", foreground="#64B5F6", cursor="hand2")
            link_lbl.pack(side=tk.RIGHT)
            link_lbl.bind("<Button-1>", lambda e, u=link: webbrowser.open(u))

        _T3 = ttk.LabelFrame(t1, text="风控 / 归因 / 数据", padding=8)
        _T3.pack(fill=tk.X, pady=4)
        for name, desc, link in [
            ("MSCI Barra CNE6", "A 股标准 Barra 模型, 风格暴露 + 行业中性", "https://www.msci.com"),
            ("Axioma", "另一套风险模型 + 组合优化器", "https://www.axioma.com"),
            ("Brinson 归因", "业绩归因标准框架 (资产配置 + 个股选择)", "https://en.wikipedia.org/wiki/Brinson_model"),
            ("Wind / Choice / iFinD", "机构级数据终端三巨头", "https://www.wind.com.cn"),
            ("朝阳永续", "私募净值数据库", "https://www.chaoyangyongxu.com"),
        ]:
            row = ttk.Frame(_T3); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"🔸 {name}", font=("Helvetica", 11, "bold"), foreground="#FFA726").pack(side=tk.LEFT)
            ttk.Label(row, text=f" — {desc}", foreground="#AAAAAA").pack(side=tk.LEFT, fill=tk.X, expand=True)
            link_lbl = ttk.Label(row, text="🔗", foreground="#64B5F6", cursor="hand2"); link_lbl.pack(side=tk.RIGHT)
            link_lbl.bind("<Button-1>", lambda e, u=link: webbrowser.open(u))

        # ── Tab 2: 选股逻辑 ──
        t2 = _mk_scrollable_tab(nb, "🎯 选股逻辑 (三套操作系统)")
        systems = [
            ("🏛️ 公募主观", "产业趋势 > 公司质量 > 估值", "#FF7043",
             "2026 年框架已切换: 基金经理季报明确淡化短期景气, 押中长期产业逻辑.\n"
             "基本不择时, 所谓择时 = 行业/风格轮动.\n"
             "2026Q2 主动偏股基金仓位约 86%, 普通股票型中位数 91.25% (历史 84.85% 分位)."),
            ("💹 量化私募", "多因子打分 + 高度分散 + 赚定价偏差", "#42A5F5",
             "分支: 300/A500/500/1000/2000 指增、红利指增、量化选股(空气指增)、市场中性.\n"
             "风控本身就是业务 (Barra 风格约束 + 行业中性 + 流动性冲击).\n"
             "2026 年量化超额收缩至平均 3.11% (去年同期 14.17%) — 同质化 + 规模膨胀."),
            ("🔥 游资 / 量化游资", "题材 + 情绪 + 筹码 / 小市值 + 量价因子", "#EF5350",
             "传统游资: 流通市值 50~200 亿, 常态换手 15~40%, 有涨停基因.\n"
             "量化游资偏好: 流动性好的中小盘微盘, 量价因子有效, 盘口密集小单.\n"
             "2026 量化占市场成交 30~40%, 小盘题材票常超 50% — 游资越来越难做的根本原因."),
        ]
        for title, sub, color, body in systems:
            _F = tk.Frame(t2, bg=color, bd=0, highlightthickness=1, highlightbackground=color)
            _F.pack(fill=tk.X, pady=6)
            tk.Label(_F, text=f" {title} — {sub}", bg=color, fg="white",
                     font=("Helvetica", 13, "bold"), anchor="w").pack(fill=tk.X, padx=6, pady=4)
            tk.Label(_F, text=body, bg="#2A2A3E", fg="#ECEFF1", justify=tk.LEFT,
                     anchor="w", padx=10, pady=8, font=("Helvetica", 10)).pack(fill=tk.X)

        # ── Tab 3: 择时 / 风控 / 归因 ──
        t3 = _mk_scrollable_tab(nb, "⏱️ 择时 · 风控 · 归因")
        _TO = ttk.LabelFrame(t3, text="择时 (谁择时, 用什么)", padding=8)
        _TO.pack(fill=tk.X, pady=4)
        for txt in [
            ("公募", "基本不择时. 2026Q2 主动偏股仓位中位数 91.25%"),
            ("私募绝对收益", "估值分位 / 股债性价比 ERP / 趋势均线 / 成交量波动率 / 北向资金 / 两融 / 情绪指标(涨停/连板高度/换手)"),
            ("量化中性", "股指期货基差 — 基差就是对冲成本, 走阔就减仓"),
        ]:
            row = ttk.Frame(_TO); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"  {txt[0]}", font=("Helvetica", 11, "bold"), foreground="#42A5F5").pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(row, text=txt[1], foreground="#B0BEC5").pack(side=tk.LEFT, fill=tk.X, expand=True)

        _RK = ttk.LabelFrame(t3, text="合规硬约束 (2026 新规)", padding=8)
        _RK.pack(fill=tk.X, pady=4)
        _rules = [
            ("双十红线", "单只基金持单票 ≤ 净值 10%; 同一管理人旗下合计 ≤ 该股总股本 10%"),
            ("全组合上限", "同一管理人全部开放式基金持单票流通股 ≤ 15%, 全部组合 ≤ 30%"),
            ("举牌", "单票接近 5% 触发举牌 → 限售 6 个月, 公募普遍躲着走"),
            ("被动超限", "波动/赎回/合并导致超限 → 10 个交易日内可调整; ETF 指数化部分豁免"),
            ("2026 题材风格指引", "2026-12-01 施行: 主题基金必须建风格库(年度更新≤12次), 防风格漂移, 投研与合规必须独立"),
            ("2026Q2 实况", "971 只主动权益基金顶格配置(>9.5%) 创历史新高, 272 只破 10%, 最高 14.88%. 集中度已处警戒状态"),
        ]
        for name, desc in _rules:
            row = ttk.Frame(_RK); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"⚠ {name}", font=("Helvetica", 11, "bold"), foreground="#EF5350").pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(row, text=desc, foreground="#B0BEC5").pack(side=tk.LEFT, fill=tk.X, expand=True)

        _QR = ttk.LabelFrame(t3, text="量化风控流水线", padding=8)
        _QR.pack(fill=tk.X, pady=4)
        for txt in [
            "Barra 风格暴露约束 (beta/市值/动量/波动率/流动性)",
            "行业 / 市值中性",
            "个股集中度上限",
            "持仓 ≤ 个股日均成交额固定比例 (流动性冲击约束)",
            "回撤预警线 (日/周/月)",
            "因子拥挤度监控 (同因子同时拥挤 → 踩踏风险)",
            "压力测试 (极端行情下组合最大可能损失)",
        ]:
            ttk.Label(_QR, text=f"  ✅ {txt}", foreground="#81C784").pack(anchor="w")

        # ── Tab 4: 参考指数 ──
        t4 = _mk_scrollable_tab(nb, "📐 参考哪些指数")
        ref_groups = [
            ("业绩基准", ["沪深300", "中证A500", "中证500", "中证1000", "中证2000", "创业板指", "科创50", "中证红利", "万得全A"]),
            ("对冲工具", ["IF (沪深300)", "IC (中证500)", "IM (中证1000)", "股指期货", "期权 / 雪球"]),
            ("风格行业", ["Barra 风格因子 (beta/市值/动量/波动率/流动性)", "申万一级行业 (31 个)", "中信一级行业 (31 个)", "宽基成分股 (做成分股约束)"]),
        ]
        for title, items in ref_groups:
            _F = ttk.LabelFrame(t4, text=title, padding=8); _F.pack(fill=tk.X, pady=4)
            for it in items:
                ttk.Label(_F, text=f"  🔸 {it}", foreground="#B0BEC5").pack(anchor="w", pady=1)

        _Z = ttk.LabelFrame(t4, text="2026 指增实况 (截至 9 月)", padding=8); _Z.pack(fill=tk.X, pady=4)
        z_stats = [
            ("中证2000 指增", "+17.51%", "收益最强 / 回撤最深"),
            ("中证A500 指增", "+9.98%", "中等"),
            ("沪深300 指增", "+7.49%", "最稳"),
            ("中证1000 指增", "+6.66%", "中等"),
            ("量化选股 (空气指增)", "+3.75%", "弱于 2000"),
            ("中证500 指增", "+2.45%", "最弱"),
        ]
        for name, val, note in z_stats:
            row = ttk.Frame(_Z); row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"  {name}", font=("Helvetica", 11, "bold"), foreground="#E3F2FD").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(row, text=val, font=("Helvetica", 12, "bold"), foreground="#66BB6A").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(row, text=f"({note})", foreground="#90A4AE").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Tab 5: 机构现在持有什么 ──
        t5 = _mk_scrollable_tab(nb, "💰 机构重仓 (2026Q2)")
        _TOP = ttk.LabelFrame(t5, text="公募前十大重仓股 (硬科技首次彻底霸榜)", padding=8); _TOP.pack(fill=tk.X, pady=4)
        top10 = [
            ("1", "中际旭创", "1662.53 亿", "1816 只基金持有", "#EF5350"),
            ("2", "新易盛", "—", "光模块", "#EF5350"),
            ("3", "东山精密", "—", "PCB", "#EF5350"),
            ("4", "寒武纪", "—", "AI 芯片", "#EF5350"),
            ("5", "宁德时代", "—", "新能源", "#42A5F5"),
            ("6", "北方华创", "—", "半导体设备", "#EF5350"),
            ("7", "兆易创新", "—", "存储芯片", "#EF5350"),
            ("8", "源杰科技", "—", "光芯片", "#EF5350"),
            ("9", "中微公司", "—", "刻蚀设备", "#EF5350"),
            ("10", "三环集团", "—", "MLCC", "#EF5350"),
        ]
        for rank, name, val, detail, color in top10:
            row = ttk.Frame(_TOP); row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"#{rank}", bg=color, fg="white", width=3, font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Label(row, text=name, font=("Helvetica", 11, "bold")).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(row, text=val, foreground="#FFD54F").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(row, text=detail, foreground="#90A4AE").pack(side=tk.LEFT, fill=tk.X, expand=True)

        _SEC = ttk.LabelFrame(t5, text="行业权重变化", padding=8); _SEC.pack(fill=tk.X, pady=4)
        for txt in [
            "📈 电子 42.66% (单季加仓 +10.7~21.5 pct)",
            "📈 通信 16.93%",
            "📈 机械 6.07%",
            "📉 腾讯控股 / 贵州茅台 (退至第 30 位) / 阿里巴巴 / 紫金矿业 — 均被大幅减持",
            "💥 消费股近十年首次全部退出公募前十大重仓",
            "💥 双创配置比例首次超过主板 (56.35% vs 43.55%)",
        ]:
            ttk.Label(_SEC, text=f"  {txt}", foreground="#B0BEC5").pack(anchor="w", pady=1)

        # ── Tab 6: 从哪查 (渠道) ──
        t6 = _mk_scrollable_tab(nb, "🔍 信息渠道 + 时效")
        _CH = ttk.LabelFrame(t6, text="持仓数据来源", padding=8); _CH.pack(fill=tk.X, pady=4)
        channels = [
            ("巨潮资讯 / 交易所官网", "上市公司前十大 (流通) 股东", "季报 1 个月 / 半年报 2 个月 / 年报 4 个月内", "http://www.cninfo.com.cn"),
            ("基金季报/半年报/年报", "前十大重仓 (季报) / 全部持仓 (半年报年报)", "季度结束 15 个工作日内", None),
            ("沪深港通", "北向持股", "每季第五个交易日披露上季末", None),
            ("ETF 申赎清单 PCF", "每日成分与权重", "每日", None),
            ("龙虎榜", "机构专用席位买卖", "当日", None),
            ("大宗交易 / 两融 / 股东户数", "资金痕迹与筹码集中度", "日 / 周", None),
            ("Wind / Choice / iFinD / 天天基金", "机构持股汇总与变动", "整合加工", None),
            ("私募", "无强制持仓披露, 只能从个股十大股东间接看到", "—", None),
        ]
        for ch, content, timeliness, link in channels:
            row = ttk.Frame(_CH); row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=f"📍 {ch}", font=("Helvetica", 11, "bold"), foreground="#42A5F5").pack(side=tk.LEFT, anchor="w")
            ttk.Label(row, text=f"  {content}  | 时效: {timeliness}", foreground="#B0BEC5", wraplength=700).pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="w")
            if link:
                link_lbl = ttk.Label(row, text="🔗", foreground="#64B5F6", cursor="hand2")
                link_lbl.pack(side=tk.RIGHT)
                link_lbl.bind("<Button-1>", lambda e, u=link: webbrowser.open(u))

        tk.Label(t6, text="⚠ 核心提醒: 所有持仓数据滞后 1~3 个月, 只能看连续 2~3 期的趋势, 不能当实时操盘依据; 季报加仓也可能是高位接盘.",
                 bg="#3E2723", fg="#FFAB91", pady=10, padx=12, font=("Helvetica", 10, "bold")).pack(fill=tk.X, pady=10)

        # ── Tab 7: 识别谁在主导 + 实操含义 ──
        t7 = _mk_scrollable_tab(nb, "🎭 谁在主导 + 实操含义")
        _ID = ttk.LabelFrame(t7, text="识别资金类型 (盘口特征)", padding=8); _ID.pack(fill=tk.X, pady=4)
        for txt in [
            "直线脉冲 = 游资",
            "阶梯慢涨 = 机构",
            "锯齿毛刺 = 量化",
            "再叠加: 换手率 / 龙虎榜席位类型 / 单笔拆单特征",
        ]:
            ttk.Label(_ID, text=f"  {txt}", font=("Helvetica", 11), foreground="#B0BEC5").pack(anchor="w", pady=2)

        _DO = ttk.LabelFrame(t7, text="对你的实操含义", padding=8); _DO.pack(fill=tk.X, pady=4)
        for txt in [
            "跟公募只能用季度环比趋势, 而且当前是 K 型分化的极致抱团 — 拥挤度高, 脆弱性大, 必须留逆向余地.",
            "反向思维: 被无差别减仓的创新药 / 有色-黄金反而可能有修复机会 (光大投顾提示).",
            "判断个股先分清资金结构再定规则: 游资票用情绪周期, 机构票用均线趋势 (你的天地一刀斩就是纯机构控盘形态), 量化扎堆的票别去高频对拼.",
            "2026 量化超额收缩是行业性问题 (同质化 + 规模膨胀), 挑量化产品看风格约束纪律, 不看单月超额.",
        ]:
            tk.Label(_DO, text=f"💡 {txt}", bg="#1B5E20", fg="#A5D6A7", padx=10, pady=8,
                     wraplength=900, justify=tk.LEFT, font=("Helvetica", 10)).pack(fill=tk.X, pady=4)

        _FINAL = tk.Frame(t7, bg="#FF6F00", bd=0, highlightthickness=2, highlightbackground="#FFA726")
        _FINAL.pack(fill=tk.X, pady=16)
        tk.Label(_FINAL, text="📌 2026 量化已占全市场成交 30%~40% — 小盘题材票常超 50%\n这就是「游资越来越难做」的根本原因.",
                 bg="#FF6F00", fg="white", font=("Helvetica", 13, "bold"), justify=tk.CENTER, pady=14).pack()

    def _show_institution_holdings(self):
        """📊 机构重仓追踪 (实时数据不可得 — 显示数据滞后 + 查看链接)"""
        import webbrowser
        win = tk.Toplevel(self.root); win.title("📊 机构重仓追踪"); win.geometry("960x600")
        nb = ttk.Notebook(win); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        def _mk_tab(nb_, title):
            t = ttk.Frame(nb_); nb_.add(t, text=title)
            cv = tk.Canvas(t, highlightthickness=0, bg="#1E1E2E")
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb = ttk.Scrollbar(t, orient=tk.VERTICAL, command=cv.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
            cv.configure(yscrollcommand=sb.set, bg="#1E1E2E")
            inner = ttk.Frame(cv, padding=8)
            cv.create_window((0, 0), window=inner, anchor="nw")
            inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
            return inner

        t1 = _mk_tab(nb, "🔗 查持仓链接 (可点)")
        for name, url in [
            ("巨潮资讯 (基金季报)", "http://www.cninfo.com.cn/new/data/fundArchives"),
            ("东方财富 · 基金持仓", "https://fund.eastmoney.com/data/fundranking.html"),
            ("同花顺 · 机构持仓", "https://data.10jqka.com.cn/fund/"),
            ("沪深港通 · 北向持股", "https://data.eastmoney.com/hsgtcg/list.html"),
            ("龙虎榜 (机构专用)", "https://data.eastmoney.com/stock/tradedate.html"),
            ("Wind (需账号)", "https://www.wind.com.cn"),
        ]:
            f = ttk.Frame(t1); f.pack(fill=tk.X, pady=4)
            ttk.Label(f, text=name, font=("Helvetica", 11, "bold"), foreground="#42A5F5").pack(side=tk.LEFT)
            l = ttk.Label(f, text="🔗", foreground="#64B5F6", cursor="hand2")
            l.pack(side=tk.RIGHT)
            l.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    def _show_factor_catalog_dialog(self):
        """🎯 量化因子体系 下拉框"""
        import webbrowser
        win = tk.Toplevel(self.root); win.title("🎯 量化因子体系 + 归因 (Brinson)"); win.geometry("1000x680")
        cv = tk.Canvas(win, highlightthickness=0, bg="#1E1E2E"); cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(win, orient=tk.VERTICAL, command=cv.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.configure(yscrollcommand=sb.set, bg="#1E1E2E")
        inner = ttk.Frame(cv, padding=8)
        cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

        # 因子分类
        factor_groups = [
            ("📈 量价因子", ["动量 (1/3/6/12 月)", "波动率 / 偏度 / 峰度", "换手率", "流动性 (Amihud, Pastor-Stambaugh)", "反转 (短期 / 长期)", "尾盘效应", "日内偏度"]),
            ("💰 基本面因子", ["ROE / ROA / ROIC", "毛利率 / 净利率", "营收 / 利润增速", "估值 (PE/PB/PS/EV/EBITDA)", "现金流质量", "资产负债率", "股息率"]),
            ("🎨 Barra 风格因子 (CNE6)", ["beta", "市值 lncap", "动量 momentum", "波动率 volatility", "流动性 liquidity", "贝塔 beta", "质量 quality", "成长 growth", "价值 value", "杠杆 leverage", "行业中性"]),
            ("🌐 另类因子", ["舆情 / 新闻情绪", "供应链数据 (海关 / 物流)", "卫星 / POI 人流", "招聘数据 (猎聘)", "专利 / 研发投入", "高管增减持", "回购 / 分红历史"]),
            ("🔀 合成方法", ["多因子打分 (IC 加权 / IR 加权)", "机器学习 (XGBoost / LightGBM / Transformer)", "深度学习 (时序 Transformer)", "深度学习因子 → 线性合成"]),
        ]
        for title, items in factor_groups:
            _F = ttk.LabelFrame(inner, text=title, padding=8); _F.pack(fill=tk.X, pady=6)
            ttk.Label(_F, text="  点击展开/折叠", foreground="#666", font=("Helvetica", 9)).pack(anchor="ne")
            for it in items:
                ttk.Label(_F, text=f"  ✅ {it}", foreground="#81C784").pack(anchor="w", pady=1)

        # 归因 / 策略 / Demo
        parts = [
            ("📊 业绩归因框架", [
                "Brinson 归因: 资产配置贡献 + 行业选择贡献 + 个股选择贡献 + 交互项",
                "Brinson-Fachler 修正版 (基准行业权重 vs 实际)",
                "Carino 对数归因 (解决 Brinson 跨期可加性)",
                "因子归因: 总收益 = 无风险 + 风格暴露 × 风格收益 + 因子特异性收益",
                "Grinold-Kahn 投资组合管理定律",
            ]),
            ("🎯 指增策略 2026 实况", [
                "中证2000 指增: 年内超额 +17.51% (收益最强, 回撤最深)",
                "中证A500 指增: +9.98%",
                "沪深300 指增: +7.49% (最稳)",
                "中证1000 指增: +6.66%",
                "量化选股 (空气指增): +3.75%",
                "中证500 指增: +2.45% (最弱)",
                "上半年 1236 只指增平均超额仅 3.11% (去年同期 14.17%) — Beta 盛宴, Alpha 稀缺",
            ]),
            ("📚 参考书籍 / 链接", [
                ("主动投资组合管理 (Grinold & Kahn)", "https://www.amazon.com"),
                ("量化金融 (Rama Cont)", "https://www.amazon.com"),
                ("因子投资指南 (Robeco)", "https://www.robeco.com"),
                ("MSCI Barra CNE6 文档", "https://www.msci.com"),
                ("Axioma 风险模型", "https://www.axioma.com"),
                ("CFA Institute / Journal of Portfolio Management", "https://www.cfainstitute.org"),
            ]),
        ]
        for title, items in parts:
            _F = ttk.LabelFrame(inner, text=title, padding=8); _F.pack(fill=tk.X, pady=6)
            for it in items:
                if isinstance(it, tuple):
                    n, u = it
                    r = ttk.Frame(_F); r.pack(fill=tk.X, pady=2)
                    ttk.Label(r, text=f"  📖 {n}", foreground="#E3F2FD").pack(side=tk.LEFT, fill=tk.X, expand=True)
                    l = ttk.Label(r, text="🔗", foreground="#64B5F6", cursor="hand2"); l.pack(side=tk.RIGHT)
                    l.bind("<Button-1>", lambda e, uu=u: webbrowser.open(uu))
                else:
                    ttk.Label(_F, text=f"  📌 {it}", foreground="#B0BEC5").pack(anchor="w", pady=1)

    def _show_institution_knowledge_dialog(self):
        """📚 机构知识体系综合 Dialog (下拉框/折叠式)"""
        win = tk.Toplevel(self.root); win.title("📚 机构知识体系 (综合)"); win.geometry("1100x720")
        nb = ttk.Notebook(win); nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        def _mk(nb_, t):
            x = ttk.Frame(nb_); nb_.add(x, text=t); return x

        # ── Tab 1: 完整调研报告引用 ──
        t1 = _mk(nb, "📄 调研笔记 · 引用")
        tk.Label(t1, text="机构量化体系调研 (2026-09-26)", font=("Helvetica", 14, "bold"),
                 foreground="#42A5F5").pack(pady=(20, 6))
        full_text = """
先给结论: A 股有三套完全不同的操作系统 —— 公募主观 (产业趋势+抱团, 基本不择时)、
量化私募 (多因子+组合优化, 风控本身就是业务)、游资/量化游资 (情绪博弈+盘口).
混在一起谈必然失真. 而且 2026 年量化已占全市场成交 30%~40%, 小盘题材票里常超 50%,
这就是「游资越来越难做」的根本原因.

一、系统层: 工具链
  交易/执行: 恒生 O32/O45 / 金证 / 顶点 (OMS 三巨头)
              券商极速柜台: 宽睿 / 华锐 ATP
              迅投 QMT/MiniQMT (本地跑 Python 自由) vs 恒生 PTrade (云托管零代码)
  投研/回测: 聚宽 / 米筐 / 优矿 / 掘金 / BigQuant
  风控/归因: MSCI Barra CNE5/CNE6 + Axioma + Brinson
  数据: Wind / Choice / iFinD / 朝阳永续 + Level-2 + 另类数据

二、选股逻辑
  公募主观: 产业趋势 > 公司质量 > 估值
  量化私募: 多因子打分 / 300/A500/500/1000/2000 指增 / 红利指增 / 量化选股 / 市场中性
  游资 / 量化游资: 题材情绪筹码 / 小市值 + 流动性 + 量价因子

三、择时
  公募基本不择时 (Q2 仓位 86%, 股票型中位数 91.25%)
  私募绝对收益会择时 (估值分位 / ERP / 均线 / 北向 / 情绪)
  量化中性看股指期货基差 (对冲成本)

四、风控
  合规硬约束 (双十红线 + 举牌限售 + 2026 题材风格指引)
  量化风控 (Barra 风格约束 + 行业中性 + 流动性 + 压力测试)

五、参考哪些指数
  业绩基准: 沪深300 / A500 / 500 / 1000 / 2000 / 创业板指 / 科创50 / 红利 / 万得全A
  对冲工具: IF / IC / IM + 期权 / 雪球
  风格行业: Barra 因子 / 申万 / 中信

六、机构现在持有什么 (2026Q2)
  前十大硬科技霸榜: 中际旭创 / 新易盛 / 东山精密 / 寒武纪 / 宁德时代...
  电子 42.66%, 通信 16.93%; 双创 56.35% > 主板 43.55%
  消费股近十年首次全部退出公募前十大重仓

七、从哪查 (渠道 + 时效)
  巨潮 / 基金季报 / 沪深港通 / ETF PCF / 龙虎榜 / Wind / Choice
  ⚠ 所有持仓数据滞后 1~3 个月

八、游资 / 量化游资选哪些股票
  传统游资: 流通市值 50~200 亿, 常态换手 15~40%
  量化偏好: 流动性好的中小盘微盘, 量价因子有效
  2026 博弈: 量化总规模破 3 万亿, 纯打板游资最受伤
  识别: 直线脉冲=游资 / 阶梯慢涨=机构 / 锯齿毛刺=量化

对你的实操含义:
  跟公募只能看季度环比, 当前位置是 K 型分化极致抱团, 脆弱性大
  反向思维: 创新药 / 有色-黄金被无差别减仓反而可能有修复机会
  判断个股先分清资金结构再定规则
  挑量化产品看风格约束纪律, 不看单月超额
"""
        st = scrolledtext.ScrolledText(t1, wrap=tk.WORD, font=("Consolas", 10))
        st.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        st.insert("1.0", full_text.strip())
        st.config(state=tk.DISABLED)

        # ── Tab 2: 下拉框式快速查询 ──
        t2 = _mk(nb, "🔎 快速查询 (下拉框)")
        options = ttk.Combobox(t2, values=["择时指标", "量化风控指标", "2026 指增排名", "公募 2026Q2 行业权重", "Barra CNE6 因子列表", "信息渠道时效表"], width=30)
        options.pack(pady=10); options.current(0)
        result = scrolledtext.ScrolledText(t2, wrap=tk.WORD, font=("Consolas", 10))
        result.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        _answers = {
            "择时指标": "估值分位 / 股债性价比 ERP / 趋势均线 / 成交量波动率 / 北向资金 / 两融余额 / 情绪指标 (涨停家数/连板高度/换手)",
            "量化风控指标": "Barra 风格暴露 / 行业市值中性 / 个股集中度 / 流动性冲击约束 / 回撤预警线 / 因子拥挤度 / 压力测试",
            "2026 指增排名": "中证2000 +17.51% > A500 +9.98% > 300 +7.49% > 1000 +6.66% > 选股 +3.75% > 500 +2.45%",
            "公募 2026Q2 行业权重": "电子 42.66% (+10.7~21.5pct), 通信 16.93%, 机械 6.07%; 消费近十年首次退出前十大重仓",
            "Barra CNE6 因子列表": "beta / lncap (市值) / momentum (动量) / volatility (波动率) / liquidity (流动性) / quality (质量) / growth (成长) / value (价值) / leverage (杠杆)",
            "信息渠道时效表": "巨潮/交易所 季报1个月/半年报2个月/年报4个月 | 基金季报 季度结束15工作日 | 北向 每季第五个交易日披露上季末 | 私募 无强制披露",
        }
        def _on_sel(e):
            result.config(state=tk.NORMAL); result.delete("1.0", tk.END)
            result.insert("1.0", _answers.get(options.get(), ""))
            result.config(state=tk.DISABLED)
        options.bind("<<ComboboxSelected>>", _on_sel); _on_sel(None)


    # ── helpers ──
    def _open_safe(self, url):
        import webbrowser, tkinter.messagebox as _mb
        if not url: return
        if not url.startswith(("http://", "https://")): url = "https://" + url
        try:
            ok = webbrowser.open(url, new=2)
            if not ok: _mb.showwarning("链接打开失败", "浏览器无法打开: " + url)
        except Exception as e:
            _mb.showerror("链接打不开", str(url) + "\n" + str(e))

    def _collapsible_frame(self, parent, title):
        import tkinter as _tk
        outer = ttk.LabelFrame(parent, text="  ▼ " + title + "  ", padding=4)
        content = ttk.Frame(outer)
        content.pack(fill=_tk.X, pady=4)
        _st = {"c": False}
        def _toggle(e=None):
            if _st["c"]:
                content.pack(fill=_tk.X, pady=4); outer.configure(text="  ▼ " + title + "  ")
            else:
                content.pack_forget(); outer.configure(text="  ▶ " + title + "  (点击展开)")
            _st["c"] = not _st["c"]
        outer.bind("<Button-1>", _toggle)
        for child in outer.winfo_children(): child.bind("<Button-1>", _toggle)
        return outer, content

    def _show_institution_dialog(self):
        import tkinter as _tk
        win = _tk.Toplevel(self.root); win.title("🏛️ 机构 / 公募 / 私募 完整体系 (2026 版)")
        win.geometry("1300x850"); win.configure(bg="#1E1E2E")
        try: win.state("zoomed")
        except Exception: pass
        _FS = {"v": 14}
        c = _FS["v"]; cb = c + 1
        bar = ttk.Frame(win); bar.pack(fill=_tk.X, padx=8, pady=4)
        ttk.Label(bar, text="🔤 基础字号:", font=("Helvetica", 11)).pack(side=_tk.LEFT)
        def _fs_d(): _FS["v"] = max(8,_FS["v"]-1); _rf(); _fl.config(text=str(_FS["v"]))
        def _fs_u(): _FS["v"] = min(22,_FS["v"]+1); _rf(); _fl.config(text=str(_FS["v"]))
        ttk.Button(bar, text="−", width=3, command=_fs_d).pack(side=_tk.LEFT, padx=3)
        _fl = ttk.Label(bar, text=str(_FS["v"]), font=("Helvetica", 12, "bold")); _fl.pack(side=_tk.LEFT)
        ttk.Button(bar, text="+", width=3, command=_fs_u).pack(side=_tk.LEFT)
        ttk.Label(bar, text="  💡 LabelFrame 标题点一下可折叠/展开", foreground="#888").pack(side=_tk.LEFT, padx=20)

        nb = ttk.Notebook(win); nb.pack(fill=_tk.BOTH, expand=True, padx=6, pady=4)
        def _mk_tab(nb_, ttl):
            tab = ttk.Frame(nb_); nb_.add(tab, text=ttl)
            cv = _tk.Canvas(tab, highlightthickness=0, borderwidth=0, bg="#1E1E2E")
            sb = ttk.Scrollbar(tab, orient=_tk.VERTICAL, command=cv.yview); sb.pack(side=_tk.RIGHT, fill=_tk.Y)
            cv.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True); cv.configure(yscrollcommand=sb.set, bg="#1E1E2E")
            inner = ttk.Frame(cv, padding=8); cv.create_window((0,0), window=inner, anchor="nw")
            cv.bind("<Configure>", lambda e: cv.itemconfigure(1, width=e.width))
            inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
            cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-1*(e.delta/120)), "units"))
            return inner
        def _line(parent, n, d, u=None):
            r = ttk.Frame(parent); r.pack(fill=_tk.X, pady=2)
            ttk.Label(r, text="🔹 " + n, font=("Helvetica", cb, "bold"), foreground="#42A5F5").pack(side=_tk.LEFT)
            ttk.Label(r, text=" — " + d, foreground="#CCCCCC", font=("Helvetica", c)).pack(side=_tk.LEFT, fill=_tk.X, expand=True)
            if u:
                l = _tk.Label(r, text="🔗 打开", fg="#64B5F6", cursor="hand2", bg="#1E1E2E", font=("Helvetica", c))
                l.pack(side=_tk.RIGHT); l.bind("<Button-1>", lambda e, uu=u: self._open_safe(uu))
        def _rf():
            try:
                for w in win.winfo_children():
                    for ch in w.winfo_children():
                        try: cls = ch.__class__.__name__
                        except: continue
                        if cls in ("Label","LabelFrame"):
                            try: ch.configure(font=("Helvetica", _FS["v"] if cls=="Label" else _FS["v"]+1))
                            except: pass
                        elif cls == "Button":
                            try: ch.configure(font=("Helvetica", max(8,_FS["v"]-1)))
                            except: pass
            except: pass

        t1 = _mk_tab(nb, "🧰 系统层 · 工具链")
        F1, i1 = self._collapsible_frame(t1, "交易/执行"); F1.pack(fill=_tk.X, pady=4)
        for n,d,u in [("恒生 O32/O45","公募/券商资管 OMS 三巨头","www.hundsun.com"),("金证/顶点","券商资管备选 OMS","www.kingdom.com.cn"),("迅投 QMT/MiniQMT","本地跑 Python 自由","www.thinktrader.net")]: _line(i1, n, d, u)
        F2, i2 = self._collapsible_frame(t1, "投研 / 回测"); F2.pack(fill=_tk.X, pady=4)
        for n,d,u in [("聚宽 JoinQuant","国内顶级量化回测","www.joinquant.com"),("米筐 RiceQuant","RQAlpha 引擎","www.ricequant.com"),("优矿 Uqer","因子挖掘友好","uqer.datayes.com")]: _line(i2, n, d, u)
        F3, i3 = self._collapsible_frame(t1, "风控 / 归因 / 数据"); F3.pack(fill=_tk.X, pady=4)
        for n,d,u in [("MSCI Barra CNE6","A股标准 Barra 模型","www.msci.com"),("Brinson 归因","业绩归因框架","en.wikipedia.org/wiki/Brinson_model"),("Wind/Choice/iFinD","机构终端三巨头","www.wind.com.cn")]: _line(i3, n, d, u)

        t2 = _mk_tab(nb, "🎯 选股逻辑 (三套操作系统)")
        for title, sub, color, body in [
            ("🏛️ 公募主观","产业趋势 > 公司质量 > 估值","#FF7043","2026 框架切换: 基金经理季报淡化短期景气. 基本不择时.\n2026Q2 主动偏股仓位中位数 91.25%."),
            ("💹 量化私募","多因子打分 + 高度分散 + 赚定价偏差","#42A5F5","分支: 指增 / 红利指增 / 市场中性.\n2026 超额收缩至平均 3.11%."),
            ("🔥 游资 / 量化游资","题材 + 情绪 / 小市值 + 量价因子","#EF5350","传统游资: 流通市值 50~200 亿, 换手 15~40%.\n2026 量化占市场成交 30~40%, 小盘题材常超 50%."),
        ]:
            F = _tk.Frame(t2, bg=color); F.pack(fill=_tk.X, pady=6)
            _tk.Label(F, text=" " + title + " — " + sub, bg=color, fg="white", font=("Helvetica", cb+1, "bold"), anchor="w").pack(fill=_tk.X, padx=6, pady=4)
            _tk.Label(F, text=body, bg="#2A2A3E", fg="#ECEFF1", justify=_tk.LEFT, anchor="w", padx=10, pady=8, font=("Helvetica", c)).pack(fill=_tk.X)

        t3 = _mk_tab(nb, "⏱️ 择时 · 风控 · 归因")
        TO, i3a = self._collapsible_frame(t3, "择时 (谁择时)"); TO.pack(fill=_tk.X, pady=4)
        for n,d in [("公募","基本不择时"),("私募绝对收益","估值分位/ERP/均线/北向/情绪"),("量化中性","股指期货基差 = 对冲成本")]:
            r = ttk.Frame(i3a); r.pack(fill=_tk.X, pady=2)
            ttk.Label(r, text="  " + n, font=("Helvetica", cb, "bold"), foreground="#42A5F5").pack(side=_tk.LEFT, padx=(0,8))
            ttk.Label(r, text=d, font=("Helvetica", c), foreground="#CCCCCC").pack(side=_tk.LEFT, fill=_tk.X, expand=True)
        RK, i3b = self._collapsible_frame(t3, "合规硬约束 (2026 新规)"); RK.pack(fill=_tk.X, pady=4)
        for n,d in [("双十红线","单票 ≤ 净值 10%; 同管理人合计 ≤ 总股本 10%"),("举牌","接近 5% → 限售 6 个月"),("被动超限","10 交易日内可调整; ETF 豁免"),("2026 题材风格指引","2026-12-01 施行, 防风格漂移"),("2026Q2 实况","272 只破 10%, 最高 14.88%")]:
            r = ttk.Frame(i3b); r.pack(fill=_tk.X, pady=2)
            ttk.Label(r, text="⚠ " + n, font=("Helvetica", cb, "bold"), foreground="#EF5350").pack(side=_tk.LEFT, padx=(0,8))
            ttk.Label(r, text=d, font=("Helvetica", c), foreground="#CCCCCC").pack(side=_tk.LEFT, fill=_tk.X, expand=True)
        QR, i3c = self._collapsible_frame(t3, "量化风控流水线"); QR.pack(fill=_tk.X, pady=4)
        for t in ["Barra 风格暴露约束","行业/市值中性","个股集中度上限","流动性冲击约束","回撤预警线","因子拥挤度监控","压力测试"]:
            ttk.Label(i3c, text="  ✅ " + t, font=("Helvetica", c), foreground="#81C784").pack(anchor="w", pady=1)

        t4 = _mk_tab(nb, "📐 参考哪些指数")
        for title, items in [("业绩基准",["沪深300","中证A500","中证500","中证1000","中证2000","创业板指","科创50","中证红利","万得全A"]),("对冲工具",["IF/IC/IM 股指期货","期权 / 雪球"]),("风格行业",["Barra 风格因子","申万/中信一级行业"])]:
            F, fi = self._collapsible_frame(t4, title); F.pack(fill=_tk.X, pady=4)
            for it in items: ttk.Label(fi, text="  🔸 " + it, font=("Helvetica", c), foreground="#CCCCCC").pack(anchor="w", pady=1)
        Z, iz = self._collapsible_frame(t4, "2026 指增排名"); Z.pack(fill=_tk.X, pady=4)
        for n,v,no in [("中证2000","+17.51%","最强"),("A500","+9.98%","中"),("300","+7.49%","最稳"),("1000","+6.66%","中"),("选股","+3.75%","弱"),("500","+2.45%","最弱")]:
            r = ttk.Frame(iz); r.pack(fill=_tk.X, pady=2)
            ttk.Label(r, text="  " + n, font=("Helvetica", cb, "bold")).pack(side=_tk.LEFT, padx=(0,10))
            ttk.Label(r, text=v, font=("Helvetica", cb, "bold"), foreground="#66BB6A").pack(side=_tk.LEFT, padx=(0,10))
            ttk.Label(r, text="(" + no + ")", font=("Helvetica", c), foreground="#90A4AE").pack(side=_tk.LEFT, fill=_tk.X, expand=True)

        t5 = _mk_tab(nb, "💰 机构重仓 (2026Q2)")
        TOP, i5 = self._collapsible_frame(t5, "公募前十大 (硬科技霸榜)"); TOP.pack(fill=_tk.X, pady=4)
        for rk,name,val,dt,col in [("1","中际旭创","1662.53亿","1816只基金","#EF5350"),("2","新易盛","—","光模块","#EF5350"),("3","东山精密","—","PCB","#EF5350"),("4","寒武纪","—","AI芯片","#EF5350"),("5","宁德时代","—","新能源","#42A5F5"),("6","北方华创","—","半导体设备","#EF5350"),("7","兆易创新","—","存储芯片","#EF5350"),("8","源杰科技","—","光芯片","#EF5350"),("9","中微公司","—","刻蚀设备","#EF5350"),("10","三环集团","—","MLCC","#EF5350")]:
            r = ttk.Frame(i5); r.pack(fill=_tk.X, pady=1)
            _tk.Label(r, text="#" + rk, bg=col, fg="white", width=3, font=("Helvetica", c, "bold")).pack(side=_tk.LEFT, padx=(0,6))
            ttk.Label(r, text=name, font=("Helvetica", cb, "bold")).pack(side=_tk.LEFT, padx=(0,10))
            ttk.Label(r, text=val, font=("Helvetica", c), foreground="#FFD54F").pack(side=_tk.LEFT, padx=(0,10))
            ttk.Label(r, text=dt, font=("Helvetica", c), foreground="#90A4AE").pack(side=_tk.LEFT, fill=_tk.X, expand=True)
        SEC, i5b = self._collapsible_frame(t5, "行业变化"); SEC.pack(fill=_tk.X, pady=4)
        for t in ["📈 电子 42.66% (加仓 +10.7~21.5pct)","📈 通信 16.93%","📉 茅台退至第30位","💥 消费股首次退出前十大重仓","💥 双创 56.35% > 主板 43.55%"]:
            ttk.Label(i5b, text="  " + t, font=("Helvetica", c), foreground="#CCCCCC").pack(anchor="w", pady=1)

        t6 = _mk_tab(nb, "🔍 信息渠道 + 时效")
        CH, ich = self._collapsible_frame(t6, "持仓数据来源"); CH.pack(fill=_tk.X, pady=4)
        for n,co,tm,u in [("巨潮资讯","上市公司前十大股东","季报1个月内","www.cninfo.com.cn"),("基金季报","前十大重仓","季度结束15工作日",None),("沪深港通","北向持股","每季第五交易日披露上季末",None),("ETF 申赎清单","每日成分与权重","每日",None),("龙虎榜","机构专用席位","当日",None),("私募","无强制披露","—",None)]: _line(ich, n, co + " | " + tm, u)
        _tk.Label(t6, text="⚠ 所有持仓数据滞后 1~3 个月, 不能当实时操盘依据.", bg="#3E2723", fg="#FFAB91", pady=10, padx=12, font=("Helvetica", cb, "bold")).pack(fill=_tk.X, pady=10)

        t7 = _mk_tab(nb, "🎭 谁在主导 + 实操含义")
        ID, i7a = self._collapsible_frame(t7, "识别资金 (盘口特征)"); ID.pack(fill=_tk.X, pady=4)
        for t in ["直线脉冲 = 游资","阶梯慢涨 = 机构","锯齿毛刺 = 量化","叠加: 换手率 / 龙虎榜 / 拆单特征"]:
            ttk.Label(i7a, text="  " + t, font=("Helvetica", cb), foreground="#CCCCCC").pack(anchor="w", pady=2)
        DO, i7b = self._collapsible_frame(t7, "实操含义"); DO.pack(fill=_tk.X, pady=4)
        for t in ["跟公募只能看季度环比, K 型分化极致抱团, 脆弱性大","反向思维: 创新药/有色-黄金被减仓可能有修复机会","先分清资金结构再定规则","挑量化看风格约束纪律, 不看单月超额"]:
            _tk.Label(i7b, text="💡 " + t, bg="#1B5E20", fg="#A5D6A7", padx=10, pady=8, wraplength=950, justify=_tk.LEFT, font=("Helvetica", c)).pack(fill=_tk.X, pady=4)
        FIN = _tk.Frame(t7, bg="#FF6F00"); FIN.pack(fill=_tk.X, pady=16)
        _tk.Label(FIN, text="📌 2026 量化已占全市场成交 30~40%, 小盘题材常超 50%\n这就是游资越来越难做的根本原因.", bg="#FF6F00", fg="white", font=("Helvetica", cb+1, "bold"), justify=_tk.CENTER, pady=14).pack()
        win.after(100, _rf)

    def _show_institution_holdings(self):
        import tkinter as _tk
        win = _tk.Toplevel(self.root); win.title("📊 机构重仓追踪"); win.geometry("980x620"); win.configure(bg="#1E1E2E")
        _FS = {"v": 14}; c = _FS["v"]; cb = c + 1
        bar = ttk.Frame(win); bar.pack(fill=_tk.X, padx=8, pady=4)
        ttk.Label(bar, text="🔤 字号:", font=("Helvetica", 11)).pack(side=_tk.LEFT)
        ttk.Button(bar, text="−", width=3, command=lambda: (_FS.__setitem__("v",max(8,_FS["v"]-1)), _rf())).pack(side=_tk.LEFT, padx=3)
        ttk.Label(bar, text=str(_FS["v"]), font=("Helvetica", 12, "bold")).pack(side=_tk.LEFT)
        ttk.Button(bar, text="+", width=3, command=lambda: (_FS.__setitem__("v",min(22,_FS["v"]+1)), _rf())).pack(side=_tk.LEFT)
        cv = _tk.Canvas(win, highlightthickness=0, bg="#1E1E2E"); cv.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)
        sb = ttk.Scrollbar(win, orient=_tk.VERTICAL, command=cv.yview); sb.pack(side=_tk.RIGHT, fill=_tk.Y); cv.configure(yscrollcommand=sb.set)
        inner = ttk.Frame(cv, padding=8); cv.create_window((0,0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfigure(1, width=e.width))
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-1*(e.delta/120)), "units"))
        def _rf():
            for w in win.winfo_children():
                for ch in w.winfo_children():
                    try: cls = ch.__class__.__name__
                    except: continue
                    if cls in ("Label","LabelFrame"):
                        try: ch.configure(font=("Helvetica", _FS["v"] if cls=="Label" else _FS["v"]+1))
                        except: pass
        F, fi = self._collapsible_frame(inner, "🔗 查持仓链接"); F.pack(fill=_tk.X, pady=4)
        for n,u in [("巨潮资讯","www.cninfo.com.cn/new/data/fundArchives"),("东方财富·基金持仓","fund.eastmoney.com/data/fundranking.html"),("同花顺·机构持仓","data.10jqka.com.cn/fund/"),("沪深港通·北向","data.eastmoney.com/hsgtcg/list.html"),("龙虎榜","data.eastmoney.com/stock/tradedate.html"),("Wind","www.wind.com.cn")]:
            r = ttk.Frame(fi); r.pack(fill=_tk.X, pady=4)
            ttk.Label(r, text=n, font=("Helvetica", cb, "bold"), foreground="#42A5F5").pack(side=_tk.LEFT)
            l = _tk.Label(r, text="🔗 打开", fg="#64B5F6", cursor="hand2", bg="#1E1E2E", font=("Helvetica", c))
            l.pack(side=_tk.RIGHT); l.bind("<Button-1>", lambda e, uu=u: self._open_safe(uu))
        win.after(100, _rf)

    def _show_factor_catalog_dialog(self):
        import tkinter as _tk
        win = _tk.Toplevel(self.root); win.title("🎯 量化因子体系 + 归因"); win.geometry("1020x700"); win.configure(bg="#1E1E2E")
        _FS = {"v": 14}; c = _FS["v"]; cb = c + 1
        bar = ttk.Frame(win); bar.pack(fill=_tk.X, padx=8, pady=4)
        ttk.Label(bar, text="🔤 字号:", font=("Helvetica", 11)).pack(side=_tk.LEFT)
        ttk.Button(bar, text="−", width=3, command=lambda: (_FS.__setitem__("v",max(8,_FS["v"]-1)), _rf())).pack(side=_tk.LEFT, padx=3)
        ttk.Label(bar, text=str(_FS["v"]), font=("Helvetica", 12, "bold")).pack(side=_tk.LEFT)
        ttk.Button(bar, text="+", width=3, command=lambda: (_FS.__setitem__("v",min(22,_FS["v"]+1)), _rf())).pack(side=_tk.LEFT)
        cv = _tk.Canvas(win, highlightthickness=0, bg="#1E1E2E"); cv.pack(side=_tk.LEFT, fill=_tk.BOTH, expand=True)
        sb = ttk.Scrollbar(win, orient=_tk.VERTICAL, command=cv.yview); sb.pack(side=_tk.RIGHT, fill=_tk.Y); cv.configure(yscrollcommand=sb.set)
        inner = ttk.Frame(cv, padding=8); cv.create_window((0,0), window=inner, anchor="nw")
        cv.bind("<Configure>", lambda e: cv.itemconfigure(1, width=e.width))
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-1*(e.delta/120)), "units"))
        def _rf():
            for w in win.winfo_children():
                for ch in w.winfo_children():
                    try: cls = ch.__class__.__name__
                    except: continue
                    if cls in ("Label","LabelFrame"):
                        try: ch.configure(font=("Helvetica", _FS["v"] if cls=="Label" else _FS["v"]+1))
                        except: pass
        for title, items in [("📈 量价因子",["动量","波动率/偏度/峰度","换手率","流动性(Amihud)","反转","尾盘效应"]),("💰 基本面因子",["ROE/ROA/ROIC","毛利率/净利率","估值","现金流质量","股息率"]),("🎨 Barra CNE6",["beta","lncap(市值)","momentum","volatility","liquidity","quality","growth","value","leverage"]),("🌐 另类因子",["舆情/新闻情绪","供应链数据","POI 人流","招聘数据","专利/研发","高管增减持"]),("🔀 合成方法",["多因子打分(IC/IR 加权)","机器学习(XGBoost/LightGBM)","深度学习(Transformer)"])]:
            F, fi = self._collapsible_frame(inner, title); F.pack(fill=_tk.X, pady=6)
            for it in items: ttk.Label(fi, text="  ✅ " + it, font=("Helvetica", c), foreground="#81C784").pack(anchor="w", pady=1)
        for title, items in [("📊 业绩归因",[("Brinson","资产配置+行业+个股+交互项","en.wikipedia.org/wiki/Brinson_model"),("Carino","跨期可加",""),("因子归因","风格暴露×风格收益+特异性收益","")]),("🎯 2026 指增排名",[("中证2000","+17.51%","最强"),("A500","+9.98%","中"),("300","+7.49%","最稳"),("1000","+6.66%","中"),("选股","+3.75%","弱"),("500","+2.45%","最弱")]),("📚 参考",[("MSCI Barra","www.msci.com"),("Axioma","www.axioma.com")])]:
            F, fi = self._collapsible_frame(inner, title); F.pack(fill=_tk.X, pady=6)
            for e in items:
                if e[1].startswith("+") and not e[2]:
                    r = ttk.Frame(fi); r.pack(fill=_tk.X, pady=2)
                    ttk.Label(r, text="  " + e[0], font=("Helvetica", cb, "bold")).pack(side=_tk.LEFT, padx=(0,10))
                    ttk.Label(r, text=e[1], font=("Helvetica", cb, "bold"), foreground="#66BB6A").pack(side=_tk.LEFT, padx=(0,10))
                    ttk.Label(r, text="(" + e[2] + ")", font=("Helvetica", c), foreground="#90A4AE").pack(side=_tk.LEFT, fill=_tk.X, expand=True)
                elif not e[2]:
                    ttk.Label(fi, text="  📌 " + e[0] + ": " + e[1], font=("Helvetica", c), foreground="#CCCCCC").pack(anchor="w", pady=1)
                else:
                    n,u = e[0], e[1]
                    r = ttk.Frame(fi); r.pack(fill=_tk.X, pady=2)
                    ttk.Label(r, text="  📖 " + n, font=("Helvetica", c), foreground="#E3F2FD").pack(side=_tk.LEFT, fill=_tk.X, expand=True)
                    l = _tk.Label(r, text="🔗", fg="#64B5F6", cursor="hand2", bg="#1E1E2E", font=("Helvetica", c))
                    l.pack(side=_tk.RIGHT); l.bind("<Button-1>", lambda e, uu=u: self._open_safe(uu))
        win.after(100, _rf)

    def _show_institution_knowledge_dialog(self):
        import tkinter as _tk
        from tkinter import scrolledtext
        win = _tk.Toplevel(self.root); win.title("📚 机构知识体系 (综合)"); win.geometry("1120x720"); win.configure(bg="#1E1E2E")
        nb = ttk.Notebook(win); nb.pack(fill=_tk.BOTH, expand=True, padx=6, pady=6)
        t1 = ttk.Frame(nb); nb.add(t1, text="📄 调研笔记")
        _tk.Label(t1, text="机构量化体系调研 (2026-09-26)", font=("Helvetica", 16, "bold"), foreground="#42A5F5").pack(pady=(20,6))
        full = """结论: A 股三套操作系统 — 公募主观/量化私募/游资量化游资. 2026 量化占成交 30~40%, 小盘题材常超 50%.

一、系统层工具链 — 见 🧰 系统层 Tab
二、选股逻辑 — 见 🎯 选股逻辑 Tab
三、择时 — 公募不择时, 私募择时, 量化看中证基差
四、风控 — 双十红线 + Barra 风格约束
五、参考指数 — 沪深300/A500/500/1000/2000 + IF/IC/IM
六、机构重仓 — 2026Q2 硬科技霸榜, 茅台退至第30
七、信息渠道 — 巨潮/基金季报/沪深港通/龙虎榜
八、游资/量化游资 — 直线=游资, 阶梯=机构, 锯齿=量化

实操含义:
  - 跟公募只能看季度环比, 当前 K 型分化极致抱团
  - 反向思维: 创新药/有色-黄金被减仓可能有修复机会
  - 先分资金结构再定规则
  - 挑量化看风格约束纪律, 不看单月超额"""
        st = scrolledtext.ScrolledText(t1, wrap=_tk.WORD, font=("Helvetica", 13))
        st.pack(fill=_tk.BOTH, expand=True, padx=10, pady=10); st.insert("1.0", full.strip()); st.config(state=_tk.DISABLED)
        t2 = ttk.Frame(nb); nb.add(t2, text="🔎 快速查询")
        opts = ttk.Combobox(t2, values=["择时指标","风控指标","2026 指增排名","公募行业权重","Barra CNE6","信息渠道时效"], width=30, font=("Helvetica",13))
        opts.pack(pady=10); opts.current(0)
        res = scrolledtext.ScrolledText(t2, wrap=_tk.WORD, font=("Helvetica", 13))
        res.pack(fill=_tk.BOTH, expand=True, padx=10, pady=5)
        ans = {"择时指标":"估值分位/ERP/均线/北向/情绪","风控指标":"Barra风格/行业中性/流动性/回撤/因子拥挤","2026 指增排名":"2000 +17.51% > A500 +9.98% > 300 +7.49% > 1000 +6.66% > 选股 +3.75% > 500 +2.45%","公募行业权重":"电子42.66%,通信16.93%,双创56.35%>主板43.55%","Barra CNE6":"beta/lncap/momentum/volatility/liquidity/quality/growth/value/leverage","信息渠道时效":"巨潮:季报1月/半年报2月/年报4月 | 基金:15工作日 | 北向:每季第五交易日"}
        def _on(e): res.config(state=_tk.NORMAL); res.delete("1.0", _tk.END); res.insert("1.0", ans.get(opts.get(),"")); res.config(state=_tk.DISABLED)
        opts.bind("<<ComboboxSelected>>", _on); _on(None)



    def _show_index_kline_dialog(self, initial_symbol=None, initial_days=180):
        """📈 指数/ETF 日K线大弹窗 - 指标可选 MACD/KDJ/WR/BIAS/筹码"""
        import tkinter as tk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        import matplotlib.pyplot as plt
        from matplotlib import gridspec
        import numpy as np

        INDICES = [
            ("上证指数", "sh000001"), ("深证成指", "sz399001"), ("创业板指", "sz399006"), ("科创50", "sh000688"),
            ("沪深300", "sh000300"), ("中证A500", "sh000211"), ("中证500", "sh000905"),
            ("中证1000", "sh000852"), ("中证2000", "sh932000"), ("中证红利", "sh000922"),
            ("科创ETF(588000)", "sh588000"), ("半导体ETF(512760)", "sh512760"),
            ("黄金ETF(518880)", "sh518880"), ("纳指ETF(513100)", "sh513100"),
            ("日经ETF(513520)", "sh513520"), ("证券ETF(512880)", "sh512880"),
            ("医药ETF(512010)", "sh512010"), ("新能源ETF(515030)", "sh515030"),
            ("军工ETF(512660)", "sh512660"), ("银行ETF(512800)", "sh512800"),
        ]
        NAME2SYMBOL = {n: s for n, s in INDICES}
        SYMBOL2NAME = {s: n for n, s in INDICES}
        DAYS_OPTS = [60, 120, 180, 360]
        if initial_symbol and initial_symbol in SYMBOL2NAME: init_name = SYMBOL2NAME[initial_symbol]
        else: init_name = INDICES[0][0]

        win = tk.Toplevel(self.root); win.configure(bg="#1E1E2E")
        try: win.attributes("-topmost", True)
        except Exception: pass
        try: win.state("zoomed")
        except Exception: win.geometry("1300x900")

        # === 顶栏 ===
        top = ttk.Frame(win, padding=(6, 4)); top.pack(fill=tk.X)
        ttk.Label(top, text="📈 指数日K线", font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT, padx=(0, 14))
        name_var = tk.StringVar(value=init_name)
        sym_combo = ttk.Combobox(top, textvariable=name_var, values=[n for n, _ in INDICES], width=18, state="readonly")
        sym_combo.pack(side=tk.LEFT, padx=4)
        days_var = tk.IntVar(value=initial_days)
        ttk.Label(top, text="天数").pack(side=tk.LEFT, padx=(10, 2))
        days_combo = ttk.Combobox(top, textvariable=days_var, values=DAYS_OPTS, width=5, state="readonly")
        days_combo.pack(side=tk.LEFT, padx=4)
        refresh_btn = ttk.Button(top, text="🔄 刷新")
        refresh_btn.pack(side=tk.LEFT, padx=8)
        status_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=status_var, foreground="#90A4AE").pack(side=tk.LEFT, padx=10)

        # === 指标选择行 (只保留勾选) ===
        ind_row = ttk.Frame(win, padding=(6, 0)); ind_row.pack(fill=tk.X)
        ttk.Label(ind_row, text="📊 指标:").pack(side=tk.LEFT, padx=(0, 6))
        ind_vars = {
            'macd': tk.BooleanVar(value=True),
            'kdj':  tk.BooleanVar(value=True),
            'wr':   tk.BooleanVar(value=False),
            'bias': tk.BooleanVar(value=False),
            'chip': tk.BooleanVar(value=True),
        }
        ind_labels = [('macd', 'MACD'), ('kdj', 'KDJ'), ('wr', 'WR威廉'), ('bias', 'BIAS乖离'), ('chip', '筹码')]
        for k, label in ind_labels:
            ttk.Checkbutton(ind_row, text=label, variable=ind_vars[k]).pack(side=tk.LEFT, padx=3)

        # --- 指标详细信息字典 ---
        IND_INFO = {
            'macd': {
                'title': 'MACD 异同移动平均线',
                'stars': '⭐⭐⭐⭐⭐', 'star_text': '核心趋势指标',
                'formula': 'EMA12 - EMA26 = DIF(蓝线)\nDIF的EMA9 = DEA(红线)\n柱状 = 2 × (DIF - DEA)',
                'core_signals': [
                    '🟢 金叉(DIF上穿DEA) → 买入信号',
                    '🔴 死叉(DIF下穿DEA) → 卖出信号',
                    '🟢🟢 零轴上方金叉 → 强买入(主升浪)',
                    '🔴🔴 零轴下方死叉 → 强卖出(主跌浪)',
                    '⬆️ 红柱放大 → 多头动能加强',
                    '⬇️ 绿柱放大 → 空头动能加强',
                    '💔 顶背离(股价新高 MACD未新高) → 看跌反转',
                    '💔 底背离(股价新低 MACD未新低) → 看涨反转',
                ],
                'when_to_use': ['中长期趋势跟踪', '判断多空力量强弱', '发现背离反转信号'],
                'pitfalls': ['震荡市频繁金叉死叉=无效信号', '股价暴涨后MACD滞后钝化', '不能单独使用, 需配合K线形态'],
                'links': [
                    ('⭐⭐⭐ 百度百科 - 权威定义', 'https://baike.baidu.com/item/MACD指标'),
                    ('⭐⭐⭐ 雪球MACD实战教程', 'https://xueqiu.com/873953755/312548885'),
                    ('⭐⭐ 东方财富MACD详解', 'https://caifuhao.eastmoney.com/news/202005/1513540202710'),
                ],
            },
            'kdj': {
                'title': 'KDJ 随机指标 (9,3,3)',
                'stars': '⭐⭐⭐⭐', 'star_text': '超买超卖判断',
                'formula': 'RSV = (收盘-9日最低)/(9日最高-9日最低) × 100\nK = RSV的EMA3\nD = K的EMA3\nJ = 3K - 2D',
                'core_signals': [
                    '🟢 K/D < 20 超卖区 → 关注反弹机会',
                    '🔴 K/D > 80 超买区 → 警惕回调风险',
                    '🟢 20以下金叉 → 最佳买点',
                    '🔴 80以上死叉 → 最佳卖点',
                    '🟢 J < 0 → 严重超卖, 随时反弹',
                    '🔴 J > 100 → 严重超买, 可能回调',
                ],
                'when_to_use': ['震荡市短线买卖点', '判断短期超买超卖', '配合MACD确认入场'],
                'pitfalls': ['单边趋势市KDJ会长期在超买/超卖区钝化', 'KDJ金叉≠立即涨, 可能反复', '参数(9,3,3)适合日线, 其他周期需调整'],
                'links': [
                    ('⭐⭐⭐ 百度百科', 'https://baike.baidu.com/item/KDJ指标'),
                    ('⭐⭐⭐ 雪球KDJ实战技巧', 'https://xueqiu.com/1835612492/228934828'),
                    ('⭐⭐ 同花顺KDJ超买超卖', 'https://www.10jqka.com.cn/20200409/c607281985816864.shtml'),
                ],
            },
            'wr': {
                'title': 'WR 威廉指标 (14)',
                'stars': '⭐⭐⭐', 'star_text': 'KDJ的互补指标',
                'formula': 'WR = (14日最高 - 收盘) / (14日最高 - 14日最低) × (-100)\n取值: -100 ~ 0',
                'core_signals': [
                    '🟢 WR < -80 (下方绿线) → 超卖区',
                    '🔴 WR > -20 (上方红线) → 超买区',
                    '🟢 WR上穿-80 → 买入信号',
                    '🔴 WR下穿-20 → 卖出信号',
                    '⚠️ 与KDJ原理相同, WR更灵敏',
                ],
                'when_to_use': ['配合KDJ交叉验证', '寻找超买超卖拐点'],
                'pitfalls': ['单独使用信号不准', '和KDJ重复, 二选一即可', '震荡市好用, 趋势市钝化'],
                'links': [
                    ('⭐⭐⭐ 百度百科', 'https://baike.baidu.com/item/威廉指标'),
                    ('⭐⭐ 雪球WR实战', 'https://xueqiu.com/5890967038/267454987'),
                    ('⭐⭐ WR与KDJ区别', 'https://www.10jqka.com.cn/20210125/c625805235516864.shtml'),
                ],
            },
            'bias': {
                'title': 'BIAS 乖离率 (12日)',
                'stars': '⭐⭐⭐⭐', 'star_text': '价格偏离均线',
                'formula': 'BIAS(N) = (收盘价 - N日均线) / N日均线 × 100%\n正区(红) = 价格在均线上方\n负区(绿) = 价格在均线下方',
                'core_signals': [
                    '🔴 BIAS(12) > 15% → 严重超买, 注意回调',
                    '🟢 BIAS(12) < -12% → 严重超卖, 可能反弹',
                    '🔴 BIAS顶背离 → 股价新高但BIAS未新高',
                    '🟢 BIAS底背离 → 股价新低但BIAS未新低',
                    '📊 大盘BIAS(20) > 30% → 牛市末期',
                ],
                'when_to_use': ['判断价格是否过度偏离均线', '大盘极端情绪判断', '配合均线系统使用'],
                'pitfalls': ['强趋势中BIAS可以长期超买/超卖', '不同标的超买阈值不同(小盘股波动更大)', '不能单独作为买卖依据'],
                'links': [
                    ('⭐⭐⭐ 百度百科', 'https://baike.baidu.com/item/乖离率'),
                    ('⭐⭐⭐ 雪球BIAS选股技巧', 'https://xueqiu.com/6610295538/304586768'),
                    ('⭐⭐ 东财均线偏离度实战', 'https://caifuhao.eastmoney.com/news/202103/0509543243510'),
                ],
            },
            'chip': {
                'title': '筹码分布 (CYQ)',
                'stars': '⭐⭐⭐⭐⭐', 'star_text': '主力成本判断',
                'formula': '基于日K OHLC × 成交量近似:\n每根K线 30%量均匀分配 + 70%量在收盘价附近高斯加权',
                'core_signals': [
                    '🟢🟢 90%筹码集中在现价附近 → 高度控盘',
                    '🔴🔴 现价远高于90%筹码区 → 获利盘太重',
                    '🟢 现价远低于90%筹码区 → 套牢盘沉重',
                    '💎 平均成本线上方 → 多数人赚钱',
                    '💀 平均成本线下方 → 多数人亏钱',
                    '🔥 筹码峰上移 → 获利盘离场, 套牢盘接盘',
                ],
                'when_to_use': ['判断主力持仓成本', '评估抛压轻重', '支撑压力位参考'],
                'pitfalls': ['本算法为近似值, 非精确L2筹码', '分红除权后筹码会断层', '新股/次新股筹码参考价值低'],
                'links': [
                    ('⭐⭐⭐ 百度百科', 'https://baike.baidu.com/item/筹码分布'),
                    ('⭐⭐⭐ 雪球筹码峰选股法', 'https://xueqiu.com/9383148762/345678901'),
                    ('⭐⭐ 同花顺筹码集中度判断', 'https://www.10jqka.com.cn/20200618/c610293847518843.shtml'),
                ],
            },
        }

        # === 可折叠说明面板 ===
        info_bar = tk.Frame(win, bg="#2A2A3E"); info_bar.pack(fill=tk.X)
        info_visible = [True]  # 用列表包一层以便闭包修改
        toggle_btn = tk.Button(info_bar, text="▼ 📚 指标详解 (点击折叠)", bg="#2A2A3E", fg="#FFD700",
                               activebackground="#3A3A4E", activeforeground="#FFD700",
                               relief=tk.FLAT, anchor="w", font=("TkDefaultFont", 9, "bold"),
                               cursor="hand2", command=lambda: _toggle_info())
        toggle_btn.pack(fill=tk.X, padx=6, pady=(4, 0))
        info_body = tk.Frame(win, bg="#2A2A3E")  # pack_forget/pack 切换

        info_text = tk.Text(info_body, height=8, bg="#2A2A3E", fg="#ECEFF1",
                            font=("TkDefaultFont", 9), wrap=tk.WORD,
                            relief=tk.FLAT, borderwidth=0, padx=10, pady=6, cursor="hand2")
        info_sb = ttk.Scrollbar(info_body, orient=tk.VERTICAL, command=info_text.yview)
        info_text.configure(yscrollcommand=info_sb.set)
        info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=(0, 4)); info_sb.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 4))
        # 标签样式
        info_text.tag_configure('title', foreground='#FFD700', font=("TkDefaultFont", 10, "bold"), spacing3=4)
        info_text.tag_configure('stars', foreground='#FF9800', font=("TkDefaultFont", 9, "bold"))
        info_text.tag_configure('section', foreground='#64B5F6', font=("TkDefaultFont", 9, "bold"))
        info_text.tag_configure('formula', foreground='#B0BEC5', font=("Menlo", 8), background='#1E1E2E')
        info_text.tag_configure('signal', foreground='#ECEFF1', font=("TkDefaultFont", 9))
        info_text.tag_configure('warn', foreground='#EF5350', font=("TkDefaultFont", 9))
        info_text.tag_configure('ok', foreground='#66BB6A', font=("TkDefaultFont", 9))
        info_text.tag_configure('link', foreground='#42A5F5', font=("TkDefaultFont", 9), underline=True)
        info_text.configure(state=tk.DISABLED)

        def _toggle_info():
            if info_visible[0]:
                info_body.pack_forget(); toggle_btn.configure(text="▶ 📚 指标详解 (点击展开)")
                info_visible[0] = False
            else:
                info_body.pack(fill=tk.BOTH, expand=False, padx=0, pady=(0, 2))
                toggle_btn.configure(text="▼ 📚 指标详解 (点击折叠)")
                info_visible[0] = True

        def _open_url(url):
            import webbrowser; webbrowser.open(url)

        def _update_info():
            info_text.configure(state=tk.NORMAL); info_text.delete('1.0', tk.END)
            selected = [k for k, v in ind_vars.items() if v.get()]
            if not selected:
                info_text.insert(tk.END, "👈 勾选左侧指标查看详细说明、核心信号、失效陷阱和参考链接", 'section')
            else:
                for k in selected:
                    if k not in IND_INFO: continue
                    info = IND_INFO[k]
                    # 标题行
                    info_text.insert(tk.END, f"【{info['title']}】  ", 'title')
                    info_text.insert(tk.END, f"{info['stars']}  {info['star_text']}\n", 'stars')
                    # 公式
                    info_text.insert(tk.END, "  📐 公式\n", 'section')
                    for line in info['formula'].split('\n'):
                        info_text.insert(tk.END, f"    {line}\n", 'formula')
                    # 核心信号
                    info_text.insert(tk.END, "  🎯 核心信号\n", 'section')
                    for sig in info['core_signals']:
                        tag = 'ok' if '🟢' in sig else ('warn' if '🔴' in sig else 'signal')
                        info_text.insert(tk.END, f"    {sig}\n", tag)
                    # 使用场景
                    info_text.insert(tk.END, "  ✅ 使用场景\n", 'section')
                    for s in info['when_to_use']:
                        info_text.insert(tk.END, f"    • {s}\n", 'ok')
                    # 失效陷阱
                    info_text.insert(tk.END, "  ⚠️ 失效陷阱\n", 'section')
                    for p in info['pitfalls']:
                        info_text.insert(tk.END, f"    • {p}\n", 'warn')
                    # 链接
                    info_text.insert(tk.END, "  🔗 参考链接\n", 'section')
                    for label, url in info['links']:
                        start_idx = info_text.index(tk.INSERT)
                        info_text.insert(tk.END, f"    {label}\n", 'link')
                        end_idx = info_text.index(tk.INSERT)
                        info_text.tag_add(f'url_{url}', start_idx, end_idx)
                        info_text.tag_bind(f'url_{url}', '<Button-1>', lambda e, u=url: _open_url(u))
                        info_text.tag_bind(f'url_{url}', '<Enter>', lambda e: info_text.configure(cursor='hand2'))
                        info_text.tag_bind(f'url_{url}', '<Leave>', lambda e: info_text.configure(cursor=''))
                    info_text.insert(tk.END, "\n")
            info_text.configure(state=tk.DISABLED)

        for v in ind_vars.values():
            v.trace_add('write', lambda *a: _update_info())
        _update_info()
        info_body.pack(fill=tk.BOTH, expand=False, padx=0, pady=(0, 2))

        # === Canvas + 滚动容器 ===
        wrap = tk.Frame(win, bg="#1E1E2E"); wrap.pack(fill=tk.BOTH, expand=True)
        cv_scroll = tk.Canvas(wrap, highlightthickness=0, borderwidth=0, bg="#1E1E2E")
        cv_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=cv_scroll.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        cv_scroll.configure(yscrollcommand=sb.set)
        fig_frame = tk.Frame(cv_scroll, bg="#1E1E2E")
        cv_scroll.create_window((0, 0), window=fig_frame, anchor="nw")
        fig_frame.bind("<Configure>", lambda e: cv_scroll.configure(scrollregion=cv_scroll.bbox("all")))
        cv_scroll.bind("<Configure>", lambda e: cv_scroll.itemconfigure(cv_scroll.find_withtag("all")[0], width=e.width))

        # === 计算工具 ===
        def _ema(data, period):
            arr = np.array([float(v) if v is not None else 0.0 for v in data], dtype=float)
            if len(arr) < period: return np.zeros(len(arr))
            r = np.zeros(len(arr)); r[period-1] = np.mean(arr[:period])
            k = 2/(period+1)
            for i in range(period, len(arr)): r[i] = arr[i]*k + r[i-1]*(1-k)
            return r
        def _sma(data, period):
            arr = np.array([float(v) if v is not None else np.nan for v in data], dtype=float)
            n = len(arr); out = np.full(n, np.nan)
            if n < period: return out
            cs = np.nancumsum(arr)
            out[period-1:] = (cs[period-1:] - np.concatenate([[0], cs[:-period]])) / period
            return out
        def _bb(closes, n=20, k=2.0):
            mid = _sma(closes, n)
            cv = np.array(closes, dtype=float); std = np.full(len(cv), np.nan)
            for i in range(n-1, len(cv)): std[i] = np.std(cv[i-n+1:i+1])
            return mid, mid + k*std, mid - k*std
        def _macd(closes, fa=12, sa=26, sig=9):
            efa = _ema(closes, fa); esa = _ema(closes, sa)
            dif = efa - esa; dea = _ema(dif, sig); bar = 2.0*(dif - dea)
            return dif, dea, bar
        def _kdj(highs, lows, closes, n=9):
            hh = np.array([max(highs[max(0,i-n+1):i+1]) for i in range(len(highs))])
            ll = np.array([min(lows[max(0,i-n+1):i+1]) for i in range(len(lows))])
            rsv = np.where(hh > ll, (closes - ll)/(hh - ll)*100, 50.0)
            k = _ema(rsv, 3); d = _ema(k, 3); j = 3*k - 2*d
            return k, d, j
        def _wr(highs, lows, closes, n=14):
            hh = np.array([max(highs[max(0,i-n+1):i+1]) for i in range(len(highs))])
            ll = np.array([min(lows[max(0,i-n+1):i+1]) for i in range(len(lows))])
            return np.where(hh > ll, (hh - closes)/(hh - ll)*(-100), -50.0)
        def _bias(closes, n=12):
            ma = _sma(closes, n)
            return np.where(~np.isnan(ma), (closes - ma)/ma*100, 0.0)
        def _chip(data, n_days=60, bins=50):
            recent = data[-n_days:] if len(data) > n_days else data
            o = np.array([float(d["open"]) for d in recent])
            h = np.array([float(d["high"]) for d in recent])
            l = np.array([float(d["low"]) for d in recent])
            c = np.array([float(d["close"]) for d in recent])
            v = np.array([float(d.get("volume", 0)) for d in recent])
            p_lo, p_hi = np.min(l), np.max(h)
            if p_hi - p_lo < 0.01: p_hi = p_lo + 1.0
            bw = (p_hi - p_lo)/bins
            chip = np.zeros(bins)
            for k in range(len(recent)):
                span = max(h[k]-l[k], bw*0.5); sigma = span/3.0
                for b in range(bins):
                    bl, bh = p_lo + b*bw, p_lo + (b+1)*bw
                    ovl, ovh = max(l[k], bl), min(h[k], bh)
                    if ovh <= ovl: continue
                    uni = v[k] * (ovh - ovl)/span
                    bc = bl + bw/2
                    w = np.exp(-0.5*((bc - c[k])/sigma)**2)
                    chip[b] += uni * (0.3 + 0.7*w)
            chip_sum = chip.sum()
            if chip_sum > 0: chip = chip / chip_sum
            return chip, p_lo, p_hi, bw
        def _sr(highs, lows, closes):
            n = len(closes); look = min(30, n)
            rh = max(highs[-look:]); rl = min(lows[-look:])
            pp = (rh + rl + closes[-1])/3
            return {'R1':2*pp-rl, 'R2':pp+(rh-rl), 'S1':2*pp-rh, 'S2':pp-(rh-rl), 'PP':pp, 'max':rh, 'min':rl}

        # === 拉取 + 渲染 ===
        def _redraw():
            name = name_var.get(); symbol = NAME2SYMBOL.get(name, INDICES[0][1])
            status_var.set(f"⏳ 拉取 {name} ...")
            import threading as _th
            def _work():
                import traceback as _tb
                try:
                    data = self._fetch_index_daily(symbol, days_var.get())
                    if not data:
                        print(f"[指数弹窗] ❌ 空 symbol={symbol}", flush=True)
                        win.after(0, lambda: status_var.set("❌ 拉取失败")); return
                    def _do():
                        import traceback as _tb2
                        try: _render(name, data)
                        except Exception as e:
                            print(f"[指数弹窗] ❌ _render: {e}", flush=True); _tb2.print_exc()
                            try: status_var.set(f"❌ 渲染失败: {e}")
                            except Exception: pass
                    win.after(0, _do)
                except Exception as e:
                    print(f"[指数弹窗] ❌ _work: {e}", flush=True); _tb.print_exc()
                    win.after(0, lambda: status_var.set(f"❌ {e}"))
            _th.Thread(target=_work, daemon=True).start()

        def _render(name, data):
            for w in fig_frame.winfo_children(): w.destroy()
            closes = np.array([float(d["close"]) for d in data], dtype=float)
            opens  = np.array([float(d["open"])  for d in data], dtype=float)
            highs  = np.array([float(d["high"])  for d in data], dtype=float)
            lows   = np.array([float(d["low"])   for d in data], dtype=float)
            vols   = np.array([float(d.get("volume", 0)) for d in data], dtype=float)
            days_list = [d["day"] for d in data]
            x = np.arange(len(closes))
            ma5 = _sma(closes, 5); ma10 = _sma(closes, 10)
            ma20 = _sma(closes, 20); ma60 = _sma(closes, 60)
            bmid, bup, blo = _bb(closes, 20, 2.0)
            typ = (highs + lows + closes)/3; cum_pv = np.cumsum(typ*vols); cum_v = np.cumsum(vols)
            vwap = np.where(cum_v > 0, cum_pv/cum_v, typ)
            dif, dea, macd_bar = _macd(closes)
            kv, dv, jv = _kdj(highs, lows, closes)
            wr = _wr(highs, lows, closes)
            bias = _bias(closes)
            chip, cp_lo, cp_hi, cp_bin = _chip(data)
            sr = _sr(highs, lows, closes)

            v_chips = [k for k in ['macd','kdj','wr','bias'] if ind_vars[k].get()]
            show_chip = ind_vars['chip'].get()
            n_rows = 2 + len(v_chips) + (1 if show_chip else 0)  # 主图+VOL + N指标 + 筹码
            ratios = [4] + [1.2]*len(v_chips) + ([1.5] if show_chip else [])
            if len(ratios) > 1: ratios.insert(1, 1.2)  # VOL
            # 重算: 主图(4) VOL(1.2) N指标(各1.2) 筹码(1.5)
            ratios = [4, 1.2] + [1.2]*len(v_chips) + ([1.5] if show_chip else [])
            n_rows = len(ratios)

            fig = plt.Figure(figsize=(15, 2.5*n_rows), dpi=100, facecolor="#1E1E2E")
            gs = gridspec.GridSpec(n_rows, 1, height_ratios=ratios, hspace=0.18)
            axes = [fig.add_subplot(gs[i], facecolor="#1E1E2E") for i in range(n_rows)]
            ax = axes[0]; ax_v = axes[1]
            idx = 2
            chip_ax = None
            ind_axes = {}
            for k in v_chips:
                ind_axes[k] = axes[idx]; idx += 1
            if show_chip: chip_ax = axes[idx]

            # --- 主图 ---
            colors = ["#d32f2f" if closes[i] >= opens[i] else "#388e3c" for i in range(len(closes))]
            ax.bar(x, closes-opens, bottom=opens, color=colors, width=0.7, zorder=3)
            ax.vlines(x, lows, highs, colors=colors, linewidth=0.5, zorder=2)
            for ma, col, lbl in [(ma5,'#FF9800','MA5'),(ma10,'#2196F3','MA10'),(ma20,'#9C27B0','MA20'),(ma60,'#4CAF50','MA60')]:
                v = ~np.isnan(ma)
                if v.any(): ax.plot(x[v], ma[v], color=col, linewidth=1.0, label=lbl, zorder=4)
            bv = ~np.isnan(bmid)
            if bv.any():
                ax.plot(x[bv], bmid[bv], color='#FFEB3B', linewidth=0.9, linestyle='--', label='BOLL中轨', zorder=3)
                ax.plot(x[bv], bup[bv], color='#FF5722', linewidth=0.7, linestyle=':', label='BOLL上轨')
                ax.plot(x[bv], blo[bv], color='#00BCD4', linewidth=0.7, linestyle=':', label='BOLL下轨')
                ax.fill_between(x[bv], blo[bv], bup[bv], color='#FFEB3B', alpha=0.06, zorder=1)
            ax.plot(x, vwap, color='#FFD700', linewidth=1.2, linestyle='--', label='VWAP主力成本', zorder=5)
            sr_colors = {'R2':'#F44336','R1':'#FF7043','S1':'#26A69A','S2':'#4DB6AC','PP':'#ECEFF1','max':'#FF5722','min':'#00BCD4'}
            for k, v in sr.items():
                ax.axhline(v, color=sr_colors.get(k,'#666'), linewidth=0.7, linestyle='--', alpha=0.6, zorder=1)
                ax.text(len(closes)-1, v, f' {k}={v:.2f}', color=sr_colors.get(k,'#666'), fontsize=7, va='bottom')
            pmax = float(np.max(highs)); pmin = float(np.min(lows))
            ppad = (pmax - pmin) * 0.08
            ax.set_ylim(pmin - ppad, pmax + ppad)
            n_ticks = min(8, max(4, len(x)//20))
            tick_idx = np.linspace(0, len(x)-1, n_ticks, dtype=int)
            ax.set_xticks(tick_idx); ax.set_xticklabels([days_list[i] for i in tick_idx], rotation=25, fontsize=7, color="#AAA")
            ax.set_title(f"{name} ({days_list[0]} ~ {days_list[-1]})", color="#FFF", fontsize=13, pad=8)
            ax.legend(loc='upper left', fontsize=7, ncol=5, framealpha=0.5)
            ax.tick_params(colors="#AAA"); ax.grid(True, alpha=0.12)
            for s in ['bottom','top','left','right']: ax.spines[s].set_color('#444') if s!='top' else ax.spines[s].set_visible(False)

            # --- VOL ---
            ax_v.bar(x, vols, color=["#d32f2f" if closes[i]>=opens[i] else "#388e3c" for i in range(len(closes))], width=0.65)
            vma5 = _sma(vols, 5); vm = ~np.isnan(vma5)
            if vm.any(): ax_v.plot(x[vm], vma5[vm], color='#FF9800', linewidth=0.9, label='VOL MA5')
            vmax = np.nanmax(vols); vmin = np.nanmin(vols)
            vpad = (vmax-vmin)*0.15 if vmax>vmin else vmax*0.15
            ax_v.set_ylim(max(0, vmin-vpad), vmax+vpad)
            ax_v.set_ylabel("VOL", color="#AAA"); ax_v.tick_params(colors="#AAA", labelbottom=False)
            ax_v.grid(True, alpha=0.12); ax_v.legend(loc='upper left', fontsize=7)
            for s in ['bottom','top','left','right']: ax_v.spines[s].set_color('#444') if s!='top' else ax_v.spines[s].set_visible(False)

            # --- 动态指标副图 ---
            for key, a in ind_axes.items():
                if key == 'macd':
                    mc = ["#d32f2f" if v>=0 else "#388e3c" for v in macd_bar]
                    a.bar(x, macd_bar, color=mc, width=0.55, alpha=0.7)
                    a.plot(x, dif, color='#1565c0', linewidth=0.9, label='DIF')
                    a.plot(x, dea, color='#c62828', linewidth=0.9, label='DEA')
                    a.axhline(0, color='gray', linewidth=0.5)
                    a.set_ylabel("MACD", color="#AAA"); a.tick_params(colors="#AAA", labelbottom=False)
                    a.legend(loc='upper left', fontsize=7, ncol=3)
                elif key == 'kdj':
                    a.plot(x, kv, color='#FF5722', linewidth=0.9, label='K')
                    a.plot(x, dv, color='#2196F3', linewidth=0.9, label='D')
                    a.plot(x, jv, color='#9C27B0', linewidth=0.8, linestyle=':', label='J')
                    a.axhline(80, color='#EF5350', linewidth=0.5, linestyle='--', alpha=0.5)
                    a.axhline(20, color='#66BB6A', linewidth=0.5, linestyle='--', alpha=0.5)
                    a.set_ylim(-10, 110)
                    a.set_ylabel("KDJ", color="#AAA"); a.tick_params(colors="#AAA", labelbottom=False)
                    a.legend(loc='upper left', fontsize=7, ncol=3)
                elif key == 'wr':
                    a.plot(x, wr, color='#FF9800', linewidth=0.9, label='WR(14)')
                    a.axhline(-20, color='#EF5350', linewidth=0.5, linestyle='--', alpha=0.5)
                    a.axhline(-80, color='#66BB6A', linewidth=0.5, linestyle='--', alpha=0.5)
                    a.set_ylim(-105, 5)
                    a.set_ylabel("WR", color="#AAA"); a.tick_params(colors="#AAA", labelbottom=False)
                    a.legend(loc='upper left', fontsize=7)
                elif key == 'bias':
                    a.plot(x, bias, color='#26C6DA', linewidth=0.9, label='BIAS(12)')
                    a.axhline(0, color='gray', linewidth=0.5)
                    a.fill_between(x, 0, bias, where=bias>0, color='#EF5350', alpha=0.15)
                    a.fill_between(x, 0, bias, where=bias<0, color='#66BB6A', alpha=0.15)
                    a.set_ylabel("BIAS", color="#AAA"); a.tick_params(colors="#AAA", labelbottom=False)
                    a.legend(loc='upper left', fontsize=7)
                a.grid(True, alpha=0.12)
                for s in ['bottom','top','left','right']: a.spines[s].set_color('#444') if s!='top' else a.spines[s].set_visible(False)

            # --- 筹码 ---
            if chip_ax is not None:
                cp_centers = cp_lo + (np.arange(len(chip))+0.5) * cp_bin
                cur_p = closes[-1]
                chip_colors = ['#66BB6A' if cp_centers[i] < cur_p else '#EF5350' for i in range(len(chip))]
                chip_ax.barh(cp_centers, chip*100, height=cp_bin*0.85, color=chip_colors, alpha=0.85)
                chip_ax.axhline(cur_p, color='#FFD700', linewidth=1.2, label=f'现价 {cur_p:.2f}')
                cum_c = np.cumsum(chip); p5_idx = np.searchsorted(cum_c, 0.05); p95_idx = np.searchsorted(cum_c, 0.95)
                p5_pr = cp_lo + p5_idx*cp_bin; p95_pr = cp_lo + p95_idx*cp_bin
                chip_ax.axhline((p5_pr+p95_pr)/2, color='#FF9800', linewidth=1.0, linestyle='--', label=f'平均成本 {(p5_pr+p95_pr)/2:.2f}')
                chip_ax.axhspan(p5_pr, p95_pr, color='#FFD700', alpha=0.08)
                profit_ratio = float(np.sum(chip[cp_centers < cur_p]))
                chip_ax.set_ylabel("价格", color="#AAA"); chip_ax.set_xlabel("筹码密度 (%)", color="#AAA")
                chip_ax.tick_params(colors="#AAA"); chip_ax.grid(True, alpha=0.12)
                for s in ['bottom','top','left','right']: chip_ax.spines[s].set_color('#444') if s!='top' else chip_ax.spines[s].set_visible(False)
                chip_ax.legend(loc='lower right', fontsize=7)
            else:
                profit_ratio = float(np.sum(chip[cp_lo+(np.arange(len(chip))+0.5)*cp_bin < closes[-1]]))

            # 隐藏中间副图的 x 标签
            for a in axes[1:-1]: a.tick_params(axis='x', labelbottom=False)

            # 标题汇总
            pct = ((closes[-1]-closes[-2])/closes[-2]*100) if len(closes)>1 else 0
            title_extra = f" 获利 {profit_ratio*100:.0f}%" if show_chip else ""
            fig.suptitle(f"{name} | 收 {closes[-1]:.2f} {'+' if pct>=0 else ''}{pct:.2f}% | 主力成本 {vwap[-1]:.2f}{title_extra}",
                        color="#FFD700", fontsize=12, y=1.003)
            fig.tight_layout()

            cv = FigureCanvasTkAgg(fig, master=fig_frame); cv.draw()
            cv.get_tk_widget().pack(fill=tk.X, padx=4, pady=4)
            try: NavigationToolbar2Tk(cv, fig_frame).update()
            except Exception: pass
            status_var.set(f"✅ {len(data)}根 | 支撑 {sr['S1']:.2f} / 压力 {sr['R1']:.2f}")

            # === 鼠标十字线 + tooltip ===
            main_ax_list = [ax, ax_v] + list(ind_axes.values())
            cross_v = ax.axvline(x=-1, color='#42A5F5', linewidth=0.6, alpha=0.7, visible=False, zorder=10)
            cross_h = ax.axhline(y=-1, color='#42A5F5', linewidth=0.6, alpha=0.7, visible=False, zorder=10)
            tip = ax.text(0.99, 0.98, '', transform=ax.transAxes, fontsize=8, ha='right',
                          color='#ECEFF1', va='top',
                          bbox=dict(boxstyle='round,pad=0.4', fc='#1E1E2E', ec='#42A5F5', alpha=0.92))
            def _on_move(event):
                if event.inaxes not in main_ax_list:
                    cross_v.set_visible(False); cross_h.set_visible(False); tip.set_text(''); cv.draw_idle(); return
                idx = int(round(event.xdata))
                if idx < 0 or idx >= len(closes):
                    cross_v.set_visible(False); cross_h.set_visible(False); tip.set_text(''); cv.draw_idle(); return
                d = days_list[idx]
                o, hh, l, c, vv = float(opens[idx]), float(highs[idx]), float(lows[idx]), float(closes[idx]), float(vols[idx])
                prev_c = float(closes[idx-1]) if idx > 0 else c
                chg = c - prev_c; pct2 = chg/prev_c*100 if prev_c else 0
                ma5v = ma5[idx]; ma20v = ma20[idx]
                ma5s = f'{ma5v:.2f}' if not np.isnan(ma5v) else '-'
                ma20s = f'{ma20v:.2f}' if not np.isnan(ma20v) else '-'
                txt = (f'{d} | O{o:.2f} H{hh:.2f} L{l:.2f} C{c:.2f}\n'
                       f'量{vv/1e4:.0f}万 | 涨跌{chg:+.2f}({pct2:+.2f}%)\n'
                       f'MA5 {ma5s} | MA20 {ma20s}')
                tip.set_text(txt)
                cross_v.set_visible(True); cross_v.set_xdata([idx, idx])
                cross_h.set_visible(True); cross_h.set_ydata([c, c])
                cv.draw_idle()
            cv.mpl_connect('motion_notify_event', _on_move)

        refresh_btn.configure(command=_redraw)
        sym_combo.bind("<<ComboboxSelected>>", lambda e: _redraw())
        days_combo.bind("<<ComboboxSelected>>", lambda e: _redraw())
        for v in ind_vars.values():
            v.trace_add('write', lambda *a: _redraw())
        _redraw()

__all__ = ["DapanMixin"]

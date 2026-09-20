"""
个股预警 Mixin — WarningMixin

迁移自 stockyidong mac003.py: 21 方法 / ~1973 行
涵盖: MA 跌破预警、振幅异常预警、SOS 报警、盘中预警、暴跌预警刷新、提醒触发
"""
import os, sys, re, json, time, threading, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext

try:
    import numpy as np
except ImportError:
    np = None
try:
    import pandas as pd
except ImportError:
    pd = None

from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数
try:
    import akshare as ak
except ImportError:
    ak = None
try:
    import tushare as ts
except ImportError:
    ts = None

from datetime import datetime, timedelta
import re
import time
import threading
import traceback

class WarningMixin:
    """个股预警 + 提醒相关方法"""


    def _th_reminder_tick(self):
        """每半小时弹出一次:请选择同花顺情绪指数方向。最多同时保留 2 个,超出则停止弹出。"""
        try:
            # 清理已被关闭的弹窗引用,避免列表无限增长
            self._ths_reminder_windows = [w for w in self._ths_reminder_windows if w.winfo_exists()]
            # 已堆叠 2 个未清除时,本轮停止弹出,待用户清除后下个周期再恢复
            if len(self._ths_reminder_windows) < 2 and self.root.winfo_exists():
                self._show_ths_sentiment_reminder_dialog()
        except Exception:
            pass
        try:
            self.root.after(30 * 60 * 1000, self._th_reminder_tick)
        except Exception:
            pass


    def _add_to_warning(self, result_text):
        """将分析结果添加到警示标签页"""
        try:
            content = result_text.get("1.0", tk.END).strip()
            if not content:
                messagebox.showwarning("提示", "没有可添加的内容")
                return
            # 生成标签页名称:警示+时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tab_name = f"警示分析{current_time}"
            # 创建新标签页
            tab_id = self.create_text_tab(tab_name)
            # 获取新创建的文本框
            text_widget = self.text_widgets[tab_id]['widget']
            # 添加内容,包含标题和时间戳
            initial_content = "【警世通言 - 分析结果】\n"
            initial_content += f"时间:{current_time}\n"
            initial_content += "="*50 + "\n\n"
            initial_content += content + "\n"
            text_widget.insert("1.0", initial_content)
            # 更新最近记录显示
            if hasattr(self, 'update_warning_recent_records'):
                self.update_warning_recent_records()
            messagebox.showinfo("成功", "分析结果已添加到警示标签页")
        except Exception as e:
            messagebox.showerror("错误", f"添加到警示失败: {e}")
            import traceback
            traceback.print_exc()


    def _refresh_crash_alert_display(self):
        """刷新暴跌标签页显示。"""
        info = self._get_crash_alert_snapshot()
        txt = getattr(self, "crash_alert_text_widget", None)
        if txt is None:
            return
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
            print(f"[暴跌提示] 刷新显示失败: {e}")


    def _on_amplitude_alert_toggle(self):
        """振幅提醒开关"""
        try:
            # 这里可以添加振幅提醒开关逻辑
            pass
        except Exception as e:
            print(f"振幅提醒开关失败: {e}")
            return
        # 基础技能(常用接口),用于"对技能的查询"
        basic_catalog = [
            {"key": "daily", "title": "daily(日线K - 股票)", "needs_ts_code": True},
            {"key": "index_daily", "title": "index_daily(日线K - 指数)", "needs_ts_code": True},
            {"key": "moneyflow", "title": "moneyflow(资金流)", "needs_ts_code": True},
            {"key": "stock_basic", "title": "stock_basic(股票基础信息)", "needs_ts_code": False},
            {"key": "index_basic", "title": "index_basic(指数基础信息)", "needs_ts_code": False},
            {"key": "index_classify", "title": "index_classify(指数分类)", "needs_ts_code": False},
            {"key": "trade_cal", "title": "trade_cal(交易日历)", "needs_ts_code": False},
        ]
        main = ttk.Frame(win, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.rowconfigure(2, weight=1)
        main.columnconfigure(1, weight=1)
        # 顶部查询栏
        top = ttk.Frame(main)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(top, text="技能关键字:").pack(side=tk.LEFT, padx=(0, 8))
        query_var = tk.StringVar(value="")
        query_entry = ttk.Entry(top, textvariable=query_var, width=28)
        query_entry.pack(side=tk.LEFT, padx=(0, 8))
        def _refresh_skill_list():
            kw = (query_var.get() or "").strip().lower()
            if not kw:
                matches = basic_catalog
            else:
                matches = [
                    s for s in basic_catalog
                    if kw in s["key"].lower() or kw in s["title"].lower()
                ]
            skill_list.delete(0, tk.END)
            for s in matches:
                skill_list.insert(tk.END, f"{s['key']}|{s['title']}")
        ttk.Button(top, text="查询技能", command=_refresh_skill_list, width=10).pack(side=tk.LEFT, padx=(8, 8))
        # 左侧技能列表
        left = ttk.LabelFrame(main, text="技能列表(基础接口)", padding=10)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        skill_list = tk.Listbox(left, height=12)
        skill_list.grid(row=0, column=0, sticky="nsew")
        skill_scroll = ttk.Scrollbar(left, orient="vertical", command=skill_list.yview)
        skill_scroll.grid(row=0, column=1, sticky="ns")
        skill_list.configure(yscrollcommand=skill_scroll.set)
        # 右侧调用参数 + 输出
        right = ttk.Frame(main)
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)
        param_frame = ttk.LabelFrame(right, text="调用参数", padding=10)
        param_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        param_frame.columnconfigure(1, weight=1)
        ttk.Label(param_frame, text="ts_code/指数代码:").grid(row=0, column=0, sticky="w")
        ts_code_var = tk.StringVar(value="")
        ttk.Entry(param_frame, textvariable=ts_code_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(param_frame, text="天数(回溯):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        days_var = tk.IntVar(value=30)
        ttk.Spinbox(param_frame, from_=5, to=180, textvariable=days_var, width=6).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Label(param_frame, text="日期结束:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        end_date_var = tk.StringVar(value=datetime.now().strftime("%Y%m%d"))
        ttk.Entry(param_frame, textvariable=end_date_var).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        call_btn = ttk.Button(right, text="调用技能(基础接口)", width=22)
        call_btn.grid(row=1, column=0, sticky="w", pady=(0, 10))
        out = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=("Consolas", 12))
        out.grid(row=2, column=0, sticky="nsew")
        out.insert(tk.END, "提示:先选择左侧技能,然后点击“调用技能“。\n")
        def _selected_skill_key():
            if not skill_list.curselection():
                return None
            item = skill_list.get(skill_list.curselection()[0])
            return item.split("|", 1)[0].strip() if item else None
        def _format_ts_code_for_call(user_code: str) -> str:
            code = (user_code or "").strip()
            if not code:
                return ""
            # 已经是 Tushare 标准格式(如 000001.SZ / 883404.TI)
            if "." in code:
                return code
            return self._format_ts_code(code)
        def _do_call():
            method_key = _selected_skill_key()
            if not method_key:
                messagebox.showwarning("提示", "请先在左侧选择一个技能。", parent=win)
                return
            # 找到配置
            meta = next((x for x in basic_catalog if x["key"] == method_key), None)
            if not meta:
                messagebox.showerror("错误", f"未知技能:{method_key}", parent=win)
                return
            if meta.get("needs_ts_code"):
                code_in = ts_code_var.get().strip()
                if not code_in:
                    messagebox.showwarning("提示", "该技能需要输入 ts_code/指数代码。", parent=win)
                    return
                ts_code = _format_ts_code_for_call(code_in)
            else:
                ts_code = ""
            try:
                end_date = (end_date_var.get() or "").strip()
                if not re.match(r"^\d{8}$", end_date):
                    raise ValueError("结束日期格式应为 YYYYMMDD")
                back_days = int(days_var.get() or 30)
                start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=back_days + 30)).strftime("%Y%m%d")
            except Exception as e:
                messagebox.showerror("错误", f"日期参数有误:{e}", parent=win)
                return
            out.delete("1.0", tk.END)
            out.insert(tk.END, f"正在调用:{method_key} ...\\n")
            def worker():
                try:
                    fn = getattr(self.ts_client, method_key, None)
                    if fn is None:
                        raise AttributeError(f"Tushare client 不存在该方法:{method_key}")
                    import inspect
                    sig = inspect.signature(fn)
                    kwargs = {}
                    if meta.get("needs_ts_code") and "ts_code" in sig.parameters:
                        kwargs["ts_code"] = ts_code
                    if "start_date" in sig.parameters:
                        kwargs["start_date"] = start_date
                    if "end_date" in sig.parameters:
                        kwargs["end_date"] = end_date
                    # 一些接口用 trade_date(单日),尽量兼容
                    if "trade_date" in sig.parameters:
                        kwargs["trade_date"] = end_date
                    result = fn(**kwargs)
                    # 显示前几行
                    if isinstance(result, pd.DataFrame):
                        s = result.head(20).to_string(index=False)
                        summary = f"返回 DataFrame:rows={len(result)} cols={len(result.columns)}"
                    else:
                        s = str(result)
                        summary = "返回值(非 DataFrame)"
                    text = summary + "\\n\\n" + s
                    win.after(0, lambda: (out.delete("1.0", tk.END), out.insert(tk.END, text)))
                except Exception as e:
                    win.after(0, lambda e=e: out.insert(tk.END, f"调用失败:{e}\\n"))
            threading.Thread(target=worker, daemon=True).start()
        call_btn.configure(command=_do_call)
        _refresh_skill_list()


    def _fetch_intraday_alert_data(self):
        """盘中警告数据拉取: 实时指数涨跌+涨跌家数+量化评分
        非交易时段自动用 tushare 最近交易日收盘数据兜底"""
        import datetime as _dt
        import time as _t
        result = {
            "indices": [],
            "breadth": {"up": 0, "down": 0, "flat": 0, "zt": 0, "dt": 0, "total": 0},
            "composite": {"score": 50, "level": "warning", "signal": "⏳",
                          "details": []},
            "is_trading": False, "timestamp": "", "data_date": ""
        }
        # 判断是否交易时段
        now = _t.localtime()
        hhmm = now.tm_hour * 100 + now.tm_min
        result["is_trading"] = (930 <= hhmm <= 1130) or (1300 <= hhmm <= 1500)
        result["timestamp"] = f"{now.tm_hour:02d}:{now.tm_min:02d}"

        # 找最近交易日 (tushare)
        recent_td = None
        try:
            import tushare as _ts
            _pro_td = _ts.pro_api()
            _cal = _pro_td.trade_cal(exchange="SSE", start_date=(_dt.date.today() - _dt.timedelta(days=10)).strftime("%Y%m%d"),
                                      end_date=_dt.date.today().strftime("%Y%m%d"), is_open="1")
            if _cal is not None and len(_cal) > 0:
                recent_td = str(_cal["cal_date"].iloc[0])  # tushare trade_cal 默认降序, iloc[0]=最新!
                result["data_date"] = recent_td
                print(f"[盘中警告] 最近交易日: {recent_td}", flush=True)
        except Exception as e:
            print(f"[盘中警告] trade_cal fail: {e}")
            # 手动兜底: 往前退
            for _bd in range(1, 8):
                _d = _dt.date.today() - _dt.timedelta(days=_bd)
                if _d.weekday() < 5:
                    recent_td = _d.strftime("%Y%m%d")
                    break
            result["data_date"] = recent_td or ""

        use_tushare_fallback = not result["is_trading"]  # 非交易时段直接用 tushare

        # ===== 优先 akshare 实时数据 =====
        ak_idx_ok = False
        ak_br_ok = False

        try:
            import akshare as ak
            import pandas as _pd

            # --- 指数涨跌 ---
            index_targets = [
                ("上证指数", "000001.SH", "000001"),
                ("深证成指", "399001.SZ", "399001"),
                ("创业板指", "399006.SZ", "399006"),
                ("科创50", "000688.SH", "000688"),
            ]
            if not use_tushare_fallback:
                try:
                    idx_df = safe_call(ak.stock_zh_index_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_index_spot_em")
                    if idx_df is not None and len(idx_df) > 0:
                        for iname, itsc, icode in index_targets:
                            col_code = None
                            for c in idx_df.columns:
                                if '代码' in c: col_code = c; break
                            col_pct = None
                            for c in idx_df.columns:
                                if '涨跌幅' in c: col_pct = c; break
                            col_close = None
                            for c in idx_df.columns:
                                if '最新价' in c or '收盘' in c: col_close = c; break
                            if col_code and col_pct:
                                row = idx_df[idx_df[col_code].astype(str).str.contains(icode)]
                                if len(row) > 0:
                                    r = row.iloc[0]
                                    pct = float(r[col_pct]) if not _pd.isna(r[col_pct]) else 0
                                    close = float(r[col_close]) if col_close and not _pd.isna(r[col_close]) else 0
                                    result["indices"].append({"name": iname, "ts_code": itsc,
                                                               "code": icode, "pct": pct, "close": close})
                        ak_idx_ok = len(result["indices"]) > 0
                except Exception as ei:
                    print(f"[盘中警告] ak指数spot fail: {ei}")

            # --- 涨跌广度 ---
            if not use_tushare_fallback:
                spot = None
                for _ty in range(3):
                    try:
                        spot = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame(), label="ak.stock_zh_a_spot_em")
                        break
                    except Exception:
                        _t.sleep(1.0)
                if spot is not None and len(spot) > 0:
                    try:
                        up = len(spot[spot["涨跌幅"] > 0])
                        dn = len(spot[spot["涨跌幅"] < 0])
                        flat = len(spot) - up - dn
                        zt = len(spot[spot["涨跌幅"] >= 9.5])
                        dt = len(spot[spot["涨跌幅"] <= -9.5])
                        result["breadth"] = {"up": up, "down": dn, "flat": flat,
                                             "zt": zt, "dt": dt, "total": len(spot)}
                        ak_br_ok = True
                    except Exception as eb:
                        print(f"[盘中警告] ak breadth fail: {eb}")

        except Exception as e:
            print(f"[盘中警告] akshare 整体失败: {e}")

        # ===== tushare 最近交易日兜底 =====
        if (not ak_idx_ok or not ak_br_ok) and recent_td:
            print(f"[盘中警告] 用 tushare {recent_td} 兜底...", flush=True)
            import tushare as _ts2
            _pro2 = _ts2.pro_api()

            # --- tushare 指数日线 ---
            if not ak_idx_ok:
                try:
                    for iname, itsc, icode in [
                        ("上证指数", "000001.SH", "000001"),
                        ("深证成指", "399001.SZ", "399001"),
                        ("创业板指", "399006.SZ", "399006"),
                        ("科创50", "000688.SH", "000688"),
                    ]:
                        try:
                            idf = _pro2.index_daily(ts_code=itsc, trade_date=recent_td)
                            if idf is not None and len(idf) > 0:
                                r = idf.iloc[0]
                                pct = float(r.get("pct_chg", 0)) if not _pd.isna(r.get("pct_chg", 0)) else 0
                                close = float(r.get("close", 0)) if not _pd.isna(r.get("close", 0)) else 0
                                result["indices"].append({"name": iname, "ts_code": itsc,
                                                           "code": icode, "pct": pct, "close": close})
                        except Exception:
                            continue
                    print(f"[盘中警告] tushare 指数: {len(result['indices'])} 只", flush=True)
                except Exception as eti:
                    print(f"[盘中警告] tushare 指数 fail: {eti}")

            # --- tushare 全市场涨跌 (分批拉, 每次5000) ---
            if not ak_br_ok:
                try:
                    all_dfs = []
                    for _tsc_suf in [".SH", ".SZ", ".BJ"]:
                        try:
                            _d = _pro2.daily(trade_date=recent_td)
                            if _d is not None and len(_d) > 0:
                                all_dfs.append(_d)
                                break  # daily(trade_date=xxx) 已含沪深全部,不需分 market
                        except Exception:
                            continue
                    if not all_dfs:
                        # fallback: daily_basic
                        try:
                            _d = _pro2.daily_basic(trade_date=recent_td,
                                fields="ts_code,trade_date,close,pct_chg,turnover_rate,volume_ratio")
                            if _d is not None and len(_d) > 0:
                                all_dfs.append(_d)
                        except Exception:
                            pass
                    if all_dfs:
                        import pandas as _pd2
                        _full = _pd2.concat(all_dfs, ignore_index=True)
                        _pct_col = "pct_chg" if "pct_chg" in _full.columns else "涨跌幅"
                        _full[_pct_col] = _full[_pct_col].fillna(0)
                        up = int((_full[_pct_col] > 0).sum())
                        dn = int((_full[_pct_col] < 0).sum())
                        flat = len(_full) - up - dn
                        zt = int((_full[_pct_col] >= 9.5).sum())
                        dt = int((_full[_pct_col] <= -9.5).sum())
                        result["breadth"] = {"up": up, "down": dn, "flat": flat,
                                             "zt": zt, "dt": dt, "total": len(_full)}
                        print(f"[盘中警告] tushare breadth: 涨{up}/跌{dn} ZT{zt} DT{dt} (总{len(_full)})", flush=True)
                except Exception as etb:
                    print(f"[盘中警告] tushare breadth fail: {etb}")

            # --- 量能对比 + MA (tushare index_daily 历史) ---
            try:
                for itsc, icode in [("000001.SH", "000001")]:
                    hdf = _pro2.index_daily(ts_code=itsc,
                        start_date=(_dt.date.today() - _dt.timedelta(days=60)).strftime("%Y%m%d"),
                        end_date=_dt.date.today().strftime("%Y%m%d"))
                    if hdf is not None and len(hdf) >= 5:
                        hdf = hdf.sort_values("trade_date")
                        # 成交额
                        if "amount" in hdf.columns:
                            amt_series = hdf["amount"].dropna()
                            if len(amt_series) >= 6:
                                vol_5d = float(amt_series.iloc[-6:-1].mean())
                                vol_last = float(amt_series.iloc[-1])
                                result["amount_ratio"] = round(vol_last / vol_5d, 2) if vol_5d > 0 else 1.0
                        # MA5 / MA20
                        if "close" in hdf.columns:
                            cls = hdf["close"].dropna()
                            if len(cls) >= 5:
                                result["sh_ma5"] = round(float(cls.iloc[-5:].mean()), 2)
                            if len(cls) >= 20:
                                result["sh_ma20"] = round(float(cls.iloc[-20:].mean()), 2)
                        print(f"[盘中警告] tushare amount/MA: ratio={result.get('amount_ratio','-')} MA5={result.get('sh_ma5','-')} MA20={result.get('sh_ma20','-')}", flush=True)
                    break
            except Exception as eam:
                print(f"[盘中警告] tushare amount/MA fail: {eam}")

        # ===== 主流量化综合评分 =====
        if result["indices"] and (result["breadth"]["up"] + result["breadth"]["down"]) > 0:
            composite, details = self._calc_intraday_composite(result)
            result["composite"] = composite
            result["composite"]["details"] = details
        else:
            result["composite"]["signal"] = "❌"
            result["composite"]["level"] = "danger"
            result["composite"]["details"].append("无可用数据 (akshare+tushare 均失败)")

        print(f"[盘中警告] ⏱{result['timestamp']} 交易={'是' if result['is_trading'] else '否'} "
              f"数据日={result.get('data_date','')} score={result['composite']['score']} level={result['composite']['level_cn']}",
              flush=True)
        return result


    def _show_intraday_alert_dialog(self):
        """⚠️ 盘中警告详细弹窗: 实时指数涨跌+涨跌数+5维度量化判别+综合建议"""
        import tkinter as tk
        from tkinter import ttk

        top = tk.Toplevel(self.root)
        top.title("⚠️ 盘中警告 - 实时盘面诊断")
        top.geometry("900x720")
        top.configure(bg="#FAFAFA")

        # 顶部大标题
        header = tk.Frame(top, bg="#1A237E")
        header.pack(fill=tk.X)
        tk.Label(header, text="⚠️ 盘中警告 · 实时盘面量化诊断",
                 bg="#1A237E", fg="white", font=("", 13, "bold")).pack(side=tk.LEFT, padx=10, pady=8)
        self._ia_timestamp_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self._ia_timestamp_var,
                 bg="#1A237E", fg="#FFD54F", font=("", 9)).pack(side=tk.RIGHT, padx=10)

        # 综合评分大卡片
        score_frame = tk.Frame(top, bg="#FAFAFA")
        score_frame.pack(fill=tk.X, padx=10, pady=(8, 4))
        self._ia_score_canvas = tk.Canvas(score_frame, height=80, bg="#FAFAFA", highlightthickness=0)
        self._ia_score_canvas.pack(fill=tk.X)

        # 指数涨跌表格
        idx_frame = tk.LabelFrame(top, text="📈 实时指数涨跌", bg="#FAFAFA", font=("", 10, "bold"))
        idx_frame.pack(fill=tk.X, padx=10, pady=4)
        cols_idx = ("指数", "收盘", "涨跌幅")
        self._ia_idx_tree = ttk.Treeview(idx_frame, columns=cols_idx, show="headings", height=5)
        for c, w in zip(cols_idx, (100, 120, 120)):
            self._ia_idx_tree.heading(c, text=c)
            self._ia_idx_tree.column(c, width=w, anchor="center")
        self._ia_idx_tree.pack(fill=tk.X, padx=6, pady=4)

        # 涨跌广度卡片
        br_frame = tk.LabelFrame(top, text="📊 涨跌广度 & 涨停情绪", bg="#FAFAFA", font=("", 10, "bold"))
        br_frame.pack(fill=tk.X, padx=10, pady=4)
        self._ia_br_var = tk.StringVar(value="⏳ 加载中...")
        tk.Label(br_frame, textvariable=self._ia_br_var, bg="#FAFAFA", fg="#333",
                 font=("", 11, "bold")).pack(anchor="w", padx=10, pady=8)

        # 5维度量化判别 (用Text + tag带颜色)
        dim_frame = tk.LabelFrame(top, text="🧠 主流量化5维度判别 (权重%)", bg="#FAFAFA", font=("", 10, "bold"))
        dim_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self._ia_dim_txt = tk.Text(dim_frame, height=8, wrap=tk.WORD, font=("Menlo", 10),
                                    bg="#FAFAFA", relief=tk.FLAT, padx=6, pady=6)
        self._ia_dim_txt.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._ia_dim_txt.tag_configure("good", foreground="#2E7D32", font=("", 10, "bold"))
        self._ia_dim_txt.tag_configure("warn", foreground="#F57F17", font=("", 10, "bold"))
        self._ia_dim_txt.tag_configure("bad", foreground="#C62828", font=("", 10, "bold"))
        self._ia_dim_txt.tag_configure("emoji", font=("", 12))

        # 底部建议区
        self._ia_advice_var = tk.StringVar(value="")
        advice_frame = tk.LabelFrame(top, text="💡 操作建议", bg="#FAFAFA", font=("", 10, "bold"))
        advice_frame.pack(fill=tk.X, padx=10, pady=(4, 8))
        self._ia_advice_lbl = tk.Label(advice_frame, textvariable=self._ia_advice_var,
                                        bg="#FAFAFA", fg="#333", font=("", 11),
                                        anchor="w", justify=tk.LEFT, wraplength=850)
        self._ia_advice_lbl.pack(fill=tk.X, padx=10, pady=8)

        # 刷新按钮
        ttk.Button(top, text="🔄 刷新盘中数据",
                   command=lambda: self._ia_load(top)).pack(pady=(0, 8))

        # 首次加载
        self._ia_load(top)


    def _check_holding_amplitude_alerts(self):
        """检查持仓股振幅并弹窗报警"""
        all_holdings = self._get_all_holding_stocks()
        if not all_holdings:
            return
        # 获取市场涨跌板数据(每15分钟更新一次)
        current_time = time.time()
        if current_time - self.last_market_data_time >= self.market_data_update_interval:
            market_data = self._get_market_limit_data()
            self.last_market_data = market_data
            self.last_market_data_time = current_time
            # 打印市场数据(可选,用于调试)
            if market_data['up_count'] > 0 or market_data['down_count'] > 0:
                print(f"[市场数据] 涨停: {market_data['up_count']} 只, 跌停: {market_data['down_count']} 只")
                if market_data['up_opened']:
                    print(f"[市场数据] 涨停开板: {len(market_data['up_opened'])} 只 - {', '.join([s['name'] for s in market_data['up_opened'][:5]])}")
                if market_data['down_opened']:
                    print(f"[市场数据] 跌停开板: {len(market_data['down_opened'])} 只 - {', '.join([s['name'] for s in market_data['down_opened'][:5]])}")
        # 使用缓存的市场数据
        market_data = self.last_market_data if self.last_market_data else {
            'up_count': 0,
            'down_count': 0,
            'up_opened': [],
            'down_opened': []
        }
        alerts = []
        for stock_name, stock_code, group_index, position_index in all_holdings:
            if not stock_code:
                continue
            try:
                # 获取实时价格(与一键分析同源:优先 Tushare,失败则 AKShare)
                spot_row = self._get_realtime_spot_row_for_holding(stock_code, cache_duration=30)
                if spot_row is None:
                    continue
                current_price = float(spot_row.get('最新价', 0))
                high_price = float(spot_row.get('最高', current_price))
                low_price = float(spot_row.get('最低', current_price))
                change_pct = float(spot_row.get('涨跌幅', 0))  # 当前涨跌幅
                prev_close = float(spot_row.get('昨收', 0))  # 昨收价
                if current_price <= 0:
                    continue
                # 计算当天最高涨幅和最低涨幅(相对于昨收价)
                high_change_pct = None
                low_change_pct = None
                if prev_close > 0:
                    high_change_pct = ((high_price - prev_close) / prev_close) * 100
                    low_change_pct = ((low_price - prev_close) / prev_close) * 100
                # 更新价格历史
                self._update_holding_price_history(stock_code, current_price, high_price, low_price)
                # 计算振幅
                amplitude = self._calculate_holding_amplitude(stock_code)
                if amplitude is not None and amplitude > 5.0:
                    # 检查是否已经报警过(避免重复报警)
                    alert_key = f"{stock_code}_{int(time.time() / 900)}"  # 每15分钟最多报警一次
                    if alert_key not in self.holding_amplitude_alerts:
                        # 获取N日高低点百分比
                        nday_percentages = self._get_nday_high_low_percentages(stock_code, current_price)
                        alerts.append({
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                            'group_index': group_index,
                            'position_index': position_index,
                            'amplitude': amplitude,
                            'current_price': current_price,
                            'high': high_price,
                            'low': low_price,
                            'change_pct': change_pct,  # 当前涨跌幅
                            'high_change_pct': high_change_pct,  # 当天最高涨幅
                            'low_change_pct': low_change_pct,  # 当天最低涨幅
                            '5d_high_pct': nday_percentages.get('5d_high_pct'),  # 距离5日最高值百分比
                            '5d_low_pct': nday_percentages.get('5d_low_pct'),   # 距离5日最低值百分比
                            '10d_high_pct': nday_percentages.get('10d_high_pct'), # 距离10日最高值百分比
                            '10d_low_pct': nday_percentages.get('10d_low_pct'),   # 距离10日最低值百分比
                            '20d_high_pct': nday_percentages.get('20d_high_pct'), # 距离20日最高值百分比
                            '20d_low_pct': nday_percentages.get('20d_low_pct')    # 距离20日最低值百分比
                        })
                        self.holding_amplitude_alerts.add(alert_key)
                        # 清理过期的报警记录(保留最近1小时的)
                        current_time = time.time()
                        self.holding_amplitude_alerts = {
                            key for key in self.holding_amplitude_alerts
                            if int(key.split('_')[1]) * 900 >= current_time - 3600
                        }
            except Exception as e:
                print(f"检查持仓股 {stock_name} ({stock_code}) 振幅失败: {e}")
                continue
        # 如果有报警,弹窗显示(包含市场数据)
        if alerts:
            self._show_amplitude_alert(alerts, market_data)


    def _check_holding_ma_alerts(self):
        """检查持仓股均线距离并弹窗报警"""
        all_holdings = self._get_all_holding_stocks()
        if not all_holdings:
            print("[均线预警] 当前无持仓股票,跳过检查(请先在持仓表中添加股票)")
            return
        alerts = []
        print(f"[均线预警] 开始检查 {len(all_holdings)} 只持仓的均线距离(阈值≤3%)...")
        for stock_name, stock_code, group_index, position_index in all_holdings:
            if not stock_code:
                continue
            try:
                # 获取实时价格(与一键分析同源:优先 Tushare,失败则 AKShare)
                spot_row = self._get_realtime_spot_row_for_holding(stock_code, cache_duration=30)
                if spot_row is None:
                    continue
                current_price = float(spot_row.get('最新价', 0))
                change_pct = float(spot_row.get('涨跌幅', 0))  # 当前涨跌幅
                if current_price <= 0:
                    continue
                # 计算均线值(_calculate_ma_values 内部已用 _fetch_recent_daily_closes source='default')
                ma_result = self._calculate_ma_values(stock_code, current_price)
                if ma_result is None:
                    continue
                # 检查是否靠近均线(差值小于3%)
                near_ma5 = ma_result.get('ma5_distance') is not None and ma_result['ma5_distance'] <= 3.0
                near_ma10 = ma_result.get('ma10_distance') is not None and ma_result['ma10_distance'] <= 3.0
                near_ma15 = ma_result.get('ma15_distance') is not None and ma_result['ma15_distance'] <= 3.0
                if near_ma5 or near_ma10 or near_ma15:
                    # 检查是否已经报警过(避免重复报警)
                    alert_key = f"ma_{stock_code}_{int(time.time() / 900)}"  # 每15分钟最多报警一次
                    if alert_key not in self.holding_ma_alerts:
                        # 获取N日高低点百分比
                        nday_percentages = self._get_nday_high_low_percentages(stock_code, current_price)
                        alert_info = {
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                            'group_index': group_index,
                            'position_index': position_index,
                            'current_price': current_price,
                            'change_pct': change_pct,  # 当前涨跌幅
                            'near_ma5': near_ma5,
                            'near_ma10': near_ma10,
                            'near_ma15': near_ma15,
                            'ma5': ma_result.get('ma5'),
                            'ma10': ma_result.get('ma10'),
                            'ma15': ma_result.get('ma15'),
                            'ma5_distance': ma_result.get('ma5_distance'),
                            'ma10_distance': ma_result.get('ma10_distance'),
                            'ma15_distance': ma_result.get('ma15_distance'),
                            '5d_high_pct': nday_percentages.get('5d_high_pct'),  # 距离5日最高值百分比
                            '5d_low_pct': nday_percentages.get('5d_low_pct'),   # 距离5日最低值百分比
                            '10d_high_pct': nday_percentages.get('10d_high_pct'), # 距离10日最高值百分比
                            '10d_low_pct': nday_percentages.get('10d_low_pct'),   # 距离10日最低值百分比
                            '20d_high_pct': nday_percentages.get('20d_high_pct'), # 距离20日最高值百分比
                            '20d_low_pct': nday_percentages.get('20d_low_pct')    # 距离20日最低值百分比
                        }
                        alerts.append(alert_info)
                        self.holding_ma_alerts.add(alert_key)
                        # 清理过期的报警记录(保留最近1小时的)
                        current_time = time.time()
                        self.holding_ma_alerts = {
                            key for key in self.holding_ma_alerts
                            if int(key.split('_')[2]) * 900 >= current_time - 3600
                        }
            except Exception as e:
                print(f"检查持仓股 {stock_name} ({stock_code}) 均线失败: {e}")
                continue
        # 如果有报警,弹窗显示
        if alerts:
            self._show_ma_alert(alerts)


    def _check_holding_break_ma_alerts(self):
        """检查持仓股破均线并弹窗报警(检测所有持仓股票)"""
        all_holdings = self._get_all_holding_stocks()
        if not all_holdings:
            return
        alerts = []
        # 统计信息
        total_holding_stocks = 0  # 总持仓股数(所有组)
        break_ma1_count = 0  # 破1日线数量
        break_ma5_count = 0  # 破5日线数量
        break_ma10_count = 0  # 破10日线数量
        break_ma20_count = 0  # 破20日线数量
        for stock_name, stock_code, group_index, position_index in all_holdings:
            if not stock_code:
                continue
            # 统计所有持仓股(所有组)
            total_holding_stocks += 1
            try:
                # 检测均线状态
                ma_status = self._check_ma_status(stock_code)
                if not ma_status:
                    continue
                # 获取实时价格
                spot_row = get_realtime_spot_row(stock_code, cache_duration=30)
                if spot_row is None:
                    continue
                current_price = float(spot_row.get('最新价', 0))
                change_pct = float(spot_row.get('涨跌幅', 0))
                if current_price <= 0:
                    continue
                # 获取均线值用于判断破位
                ma_result = self._calculate_ma_values(stock_code, current_price)
                if ma_result is None:
                    continue
                break_types = []
                # 检查破1日均线(统计所有持仓股,不管预警开关是否开启)
                break_ma1 = False
                # 1日线:当前价 < 前一日收盘价
                # 获取前一日收盘价
                result = self._fetch_recent_daily_closes(stock_code, days=3, source="default", token=self.ts_token, return_volume=False)
                if isinstance(result, tuple) and len(result) >= 2:
                    _, closes = result[:2]
                else:
                    _, closes = result, []
                if len(closes) >= 2:
                    prev_close = float(closes[-2])
                    if current_price < prev_close:
                        break_ma1 = True
                        break_ma1_count += 1
                # 如果开启了预警开关,添加到报警列表
                if self.break_ma1_alert_enabled and break_ma1:
                    break_types.append('破1日')
                # 检查破5日均线(统计所有持仓股)
                break_ma5 = False
                ma5 = ma_result.get('ma5')
                if ma5 and current_price < ma5:  # 统计所有持仓股
                    break_ma5 = True
                    break_ma5_count += 1
                # 如果开启了预警开关,添加到报警列表
                if self.break_ma5_alert_enabled and break_ma5:
                    break_types.append('破5日')
                # 检查破10日均线(统计所有持仓股)
                ma10 = ma_result.get('ma10')
                if ma10 and current_price < ma10:  # 统计所有持仓股
                    break_ma10_count += 1
                # 检查破20日均线(统计所有持仓股)
                break_ma20 = False
                ma20 = ma_result.get('ma20')
                if ma20 and current_price < ma20:  # 统计所有持仓股
                    break_ma20 = True
                    break_ma20_count += 1
                # 如果开启了预警开关,添加到报警列表
                if self.break_ma20_alert_enabled and break_ma20:
                    break_types.append('破20日')
                if break_types:
                    # 检查是否已经报警过(避免重复报警)
                    alert_key = f"break_ma_{stock_code}_{int(time.time() / 60)}"  # 每1分钟最多报警一次
                    if alert_key not in self.holding_break_ma_alerts:
                        # 获取最近10天的完整历史数据(包括最高价、涨跌幅)
                        ma5_distance_pct = None
                        ma10_distance_pct = None
                        ma20_distance_pct = None
                        max_price_10days = None
                        drop_from_max_10days_pct = None
                        limit_down_count_10days = 0
                        try:
                            # 获取均线距离百分比
                            ma5_distance_pct = ma_result.get('ma5_distance')
                            ma10_distance_pct = ma_result.get('ma10_distance')
                            ma20_distance_pct = ma_result.get('ma20_distance')
                            # 获取最近10天的完整历史数据(包括最高价、涨跌幅)
                            try:
                                import akshare as ak
                                hist_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
                                if hist_data is not None and not hist_data.empty:
                                    # 确保数据按日期排序
                                    if "日期" in hist_data.columns:
                                        hist_data = hist_data.sort_values("日期")
                                    elif "date" in hist_data.columns:
                                        hist_data = hist_data.sort_values("date")
                                    # 取最近10天数据
                                    recent_10days = hist_data.tail(10) if len(hist_data) >= 10 else hist_data
                                    # 获取最高价列名
                                    high_col = None
                                    change_pct_col = None
                                    for col in recent_10days.columns:
                                        col_str = str(col)
                                        if high_col is None and ('最高' in col_str or 'high' in col_str.lower()):
                                            high_col = col
                                        if change_pct_col is None and ('涨跌幅' in col_str or 'change' in col_str.lower() or 'pct' in col_str.lower()):
                                            change_pct_col = col
                                    # 计算近10日内最高点
                                    if high_col and high_col in recent_10days.columns:
                                        highs = recent_10days[high_col].astype(float)
                                        max_price_10days = float(highs.max())
                                        # 计算从最高点下来的百分比
                                        if max_price_10days > 0:
                                            drop_from_max_10days_pct = ((current_price - max_price_10days) / max_price_10days) * 100
                                    # 统计近10日内的跌停板数量(涨跌幅 <= -9.5%)
                                    if change_pct_col and change_pct_col in recent_10days.columns:
                                        changes = recent_10days[change_pct_col].astype(float)
                                        limit_down_count_10days = int((changes <= -9.5).sum())
                                    else:
                                        # 如果没有涨跌幅列,通过计算得出
                                        # 尝试获取收盘价列
                                        close_col = None
                                        for col in recent_10days.columns:
                                            col_str = str(col)
                                            if close_col is None and ('收盘' in col_str or 'close' in col_str.lower()):
                                                close_col = col
                                        if close_col and close_col in recent_10days.columns:
                                            closes = recent_10days[close_col].astype(float).tolist()
                                            if len(closes) >= 2:
                                                for i in range(1, len(closes)):
                                                    prev_close = closes[i-1]
                                                    curr_close = closes[i]
                                                    if prev_close > 0:
                                                        daily_change_pct = ((curr_close - prev_close) / prev_close) * 100
                                                        if daily_change_pct <= -9.5:
                                                            limit_down_count_10days += 1
                            except Exception as e:
                                print(f"获取 {stock_code} 最近10天历史数据失败: {e}")
                        except Exception as e:
                            print(f"计算 {stock_code} 额外统计信息失败: {e}")
                        alert_info = {
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                            'group_index': group_index,
                            'position_index': position_index,
                            'current_price': current_price,
                            'change_pct': change_pct,
                            'break_types': break_types,
                            'ma5': ma_result.get('ma5'),
                            'ma10': ma_result.get('ma10'),
                            'ma20': ma_result.get('ma20'),
                            'ma5_distance_pct': ma5_distance_pct,  # 5日均线距离百分比
                            'ma10_distance_pct': ma10_distance_pct,  # 10日均线距离百分比
                            'ma20_distance_pct': ma20_distance_pct,  # 20日均线距离百分比
                            'max_price_10days': max_price_10days,  # 近10日内最高价
                            'drop_from_max_10days_pct': drop_from_max_10days_pct,  # 从最高点下来的百分比
                            'limit_down_count_10days': limit_down_count_10days  # 近10日内跌停板数量
                        }
                        alerts.append(alert_info)
                        self.holding_break_ma_alerts.add(alert_key)
                        # 清理过期的报警记录(保留最近1小时的)
                        current_time = time.time()
                        self.holding_break_ma_alerts = {
                            key for key in self.holding_break_ma_alerts
                            if int(key.split('_')[3]) * 60 >= current_time - 3600
                        }
            except Exception as e:
                print(f"检查持仓股 {stock_name} ({stock_code}) 破均线失败: {e}")
                continue
        # 准备统计信息
        stats = {
            'total_holding_stocks': total_holding_stocks,
            'break_ma1_count': break_ma1_count,
            'break_ma5_count': break_ma5_count,
            'break_ma10_count': break_ma10_count,
            'break_ma20_count': break_ma20_count
        }
        # 如果有报警,弹窗显示(传递统计信息)
        if alerts:
            self._show_break_ma_alert(alerts, stats)


    def _show_sos_alert(self):
        """显示SOS预警弹窗(情绪周期下行时弹出)"""
        from datetime import datetime, timedelta
        # 检查是否在3小时冷却期内
        if hasattr(self, '_sos_alert_last_closed'):
            time_since_closed = datetime.now() - self._sos_alert_last_closed
            if time_since_closed < timedelta(hours=3):
                remaining_hours = 3 - time_since_closed.total_seconds() / 3600
                print(f"SOS预警在冷却期内,剩余 {remaining_hours:.1f} 小时")
                return
        def show_alert():
            # 如果窗口已存在,先关闭
            if self.sos_alert_window is not None:
                try:
                    self.sos_alert_window.destroy()
                except:
                    pass
                self.sos_alert_window = None
            # 创建SOS预警弹窗
            sos_window = self._toplevel(self.root)
            sos_window.title("⚠️ SOS 预警 ⚠️")
            sos_window.geometry("800x500")  # 增大窗口尺寸,确保文字完整显示
            sos_window.transient(self.root)
            sos_window.attributes('-topmost', True)  # 置顶显示
            # 保存窗口引用
            self.sos_alert_window = sos_window
            # 主框架
            main_frame = ttk.Frame(sos_window, padding=30)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # SOS文字显示区域(Canvas,增大高度确保文字完整显示)
            sos_canvas = tk.Canvas(main_frame, bg="white", height=300)
            sos_canvas.pack(fill=tk.BOTH, expand=True, pady=20)
            # 闪烁文字控制
            sos_text_visible = [True]  # 使用列表以便在闭包中修改
            def draw_sos_text():
                """绘制SOS警告文字(确保完整显示)"""
                sos_canvas.delete("all")
                # 获取Canvas大小
                canvas_width = sos_canvas.winfo_width()
                canvas_height = sos_canvas.winfo_height()
                if canvas_width <= 1 or canvas_height <= 1:
                    canvas_width = 740
                    canvas_height = 300
                if sos_text_visible[0]:
                    # 显示:红色大字体
                    text_color = "red"
                else:
                    # 隐藏:浅红色(几乎透明)
                    text_color = "#FFCCCC"
                # 文字内容(分成多行显示)
                text_lines = [
                    "SOS!!!快跑路啊!!",
                    "情绪周期下行,禁止开新仓!",
                    "应该全部减仓,去乡下躲一躲。"
                ]
                # 使用固定的大字体,确保文字清晰可见
                font_size = 36  # 固定字体大小,确保文字完整显示
                # 计算行间距
                line_height = font_size * 1.8
                total_height = line_height * len(text_lines)
                start_y = (canvas_height - total_height) // 2 + line_height // 2
                # 绘制多行文字(居中显示,确保每行文字完整)
                for i, line in enumerate(text_lines):
                    y_pos = start_y + i * line_height
                    # 使用anchor=tk.CENTER确保文字居中,width参数确保文字不超出Canvas
                    sos_canvas.create_text(
                        canvas_width // 2,
                        y_pos,
                        text=line,
                        fill=text_color,
                        font=("Arial", font_size, "bold"),
                        anchor=tk.CENTER,
                        width=canvas_width - 40  # 留出边距,确保文字不超出
                    )
            def blink_sos_text():
                """闪烁SOS文字"""
                sos_text_visible[0] = not sos_text_visible[0]
                draw_sos_text()
                # 每300毫秒闪烁一次
                if sos_window.winfo_exists():
                    sos_window.after(300, blink_sos_text)
            # 绑定Canvas大小变化事件
            def on_canvas_configure(event):
                draw_sos_text()
            sos_canvas.bind('<Configure>', on_canvas_configure)
            # 关闭按钮
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="我知道了", command=lambda: self._close_sos_alert()).pack()
            # 窗口关闭事件
            def on_closing():
                self.sos_alert_window = None
                sos_window.destroy()
            sos_window.protocol("WM_DELETE_WINDOW", on_closing)
            # 初始绘制
            sos_window.after(100, draw_sos_text)
            # 开始闪烁
            blink_sos_text()
        # 在主线程中显示弹窗
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(0, show_alert)


    def _close_sos_alert(self):
        """关闭SOS预警窗口"""
        from datetime import datetime
        # 记录关闭时间
        self._sos_alert_last_closed = datetime.now()
        if self.sos_alert_window is not None:
            try:
                self.sos_alert_window.destroy()
            except:
                pass
            self.sos_alert_window = None


    def _start_sos_alert_timer(self):
        """启动SOS预警定时器(每3小时重新打开)"""
        # 先停止已有的定时器
        self._stop_sos_alert_timer()
        def timer_callback():
            """定时器回调:每3小时重新打开SOS窗口"""
            # 检查情绪周期是否仍为下行
            if hasattr(self, 'emotion_cycle_var'):
                cycle = self.emotion_cycle_var.get()
                if cycle == "下行":
                    # 重新打开SOS窗口
                    self._show_sos_alert()
                    # 继续设置下一个定时器(3小时)
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.sos_alert_timer = self.root.after(3 * 60 * 60 * 1000, timer_callback)  # 3小时 = 10800000毫秒
                else:
                    # 情绪周期已不是下行,停止定时器
                    self._stop_sos_alert_timer()
            else:
                # 如果情绪周期变量不存在,停止定时器
                self._stop_sos_alert_timer()
        # 启动定时器(3小时后执行)
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.sos_alert_timer = self.root.after(3 * 60 * 60 * 1000, timer_callback)  # 3小时 = 10800000毫秒


    def _stop_sos_alert_timer(self):
        """停止SOS预警定时器"""
        if self.sos_alert_timer is not None:
            try:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.root.after_cancel(self.sos_alert_timer)
            except:
                pass
            self.sos_alert_timer = None


    def _show_break_ma_alert(self, alerts, stats=None):
        """显示破均线预警弹窗(需要手动关闭)"""
        def show_alert():
            # 根据报警数量动态调整窗口大小
            alert_count = len(alerts)
            # 基础大小:800x600
            # 每增加1个报警,高度增加80,宽度增加50(最多不超过屏幕大小)
            base_width = 800
            base_height = 600
            max_width = 1600  # 最大宽度
            max_height = 1200  # 最大高度
            # 计算窗口大小
            window_width = min(base_width + (alert_count - 1) * 50, max_width)
            window_height = min(base_height + (alert_count - 1) * 80, max_height)
            # 创建自定义弹窗
            alert_window = self._toplevel(self.root)
            alert_window.title("⚠️ 破均线预警 ⚠️")
            alert_window.geometry(f"{window_width}x{window_height}")
            alert_window.transient(self.root)
            alert_window.attributes('-topmost', True)  # 置顶显示
            # 不允许通过点击外部关闭,只能点击关闭按钮
            alert_window.protocol("WM_DELETE_WINDOW", lambda: None)  # 禁用关闭按钮,但我们会添加自定义关闭按钮
            # 主框架
            main_frame = ttk.Frame(alert_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 统计信息显示
            if stats:
                total_holding = stats.get('total_holding_stocks', 0)
                break_ma1 = stats.get('break_ma1_count', 0)
                break_ma5 = stats.get('break_ma5_count', 0)
                break_ma10 = stats.get('break_ma10_count', 0)
                break_ma20 = stats.get('break_ma20_count', 0)
                stats_text = f"总共 {total_holding} 个持仓股,"
                stats_text += f"共计 {break_ma1} 个持仓股破1日线,"
                stats_text += f"{break_ma5} 个破5日线,"
                stats_text += f"{break_ma10} 个破10日线,"
                stats_text += f"{break_ma20} 个破20日线"
                stats_label = tk.Label(main_frame,
                                      text=stats_text,
                                      font=("TkDefaultFont", 12, "bold"),
                                      fg="red",
                                      justify=tk.CENTER,
                                      wraplength=window_width - 80)
                stats_label.pack(pady=(0, 10))
            # 标题(显示所有持仓股票的统计)
            title_label = tk.Label(main_frame,
                                  text=f"⚠️ 破均线预警 ⚠️\n检测到 {len(alerts)} 只持仓股破均线",
                                  font=("TkDefaultFont", 16, "bold"),
                                  fg="red",
                                  justify=tk.CENTER)
            title_label.pack(pady=(0, 10))
            # 声音播放控制
            sound_playing = [True]  # 控制声音播放
            def close_alert():
                """关闭报警窗口"""
                sound_playing[0] = False  # 停止声音播放
                alert_window.destroy()
            # 关闭按钮(右上角)- 使用相对位置
            def update_close_button_position():
                """更新关闭按钮位置"""
                window_width = alert_window.winfo_width()
                if window_width > 1:  # 确保窗口已渲染
                    close_button.place(x=window_width - 40, y=5)
                else:
                    # 如果窗口还未渲染,使用计算的大小
                    close_button.place(x=window_width - 40, y=5)
            close_button = tk.Button(alert_window, text="✕", font=("TkDefaultFont", 14, "bold"),
                                    bg="red", fg="white", width=3, height=1,
                                    command=close_alert,
                                    relief=tk.RAISED, bd=2)
            # 延迟更新位置,确保窗口已渲染
            alert_window.after(100, update_close_button_position)
            # 绑定窗口大小变化事件
            alert_window.bind('<Configure>', lambda e: update_close_button_position())
            # SOS闪烁文字区域(在标题下方,作为背景层)
            sos_frame = tk.Frame(main_frame, bg="white")
            sos_frame.pack(fill=tk.X, pady=(0, 10))
            # 左侧:SOS文字Canvas
            sos_left_frame = tk.Frame(sos_frame, bg="white")
            sos_left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            # 创建Canvas用于显示闪烁文字
            sos_canvas = tk.Canvas(sos_left_frame, bg="white", highlightthickness=0, height=100)
            sos_canvas.pack(fill=tk.BOTH, expand=True)
            # 右侧:创业板15分钟K线图
            kline_frame = ttk.LabelFrame(sos_frame, text="创业板指数15分钟K线", padding=5)
            kline_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
            # K线图显示区域(使用matplotlib)
            try:
                import matplotlib.pyplot as plt
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                from matplotlib.figure import Figure
                kline_fig = Figure(figsize=(8, 4), dpi=80)
                kline_ax = kline_fig.add_subplot(111)
                kline_canvas = FigureCanvasTkAgg(kline_fig, kline_frame)
                kline_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                def draw_cyb_15min_kline():
                    """绘制创业板指数15分钟K线图"""
                    try:
                        import akshare as ak
                        # 创业板指数代码:399006
                        cyb_code = "399006"
                        # 获取创业板指数15分钟K线数据
                        kline_data = ak.stock_zh_a_hist_min_em(symbol=cyb_code, period="15", adjust="")
                        if kline_data is None or kline_data.empty:
                            kline_ax.text(0.5, 0.5, "暂无数据", ha='center', va='center',
                                        transform=kline_ax.transAxes, fontsize=12)
                            kline_canvas.draw()
                            return
                        # 处理数据
                        if '时间' in kline_data.columns:
                            kline_data = kline_data.sort_values('时间')
                        # 获取收盘价列
                        close_col = None
                        time_col = None
                        for col in kline_data.columns:
                            col_str = str(col).lower()
                            if close_col is None and ('收盘' in str(col) or 'close' in col_str):
                                close_col = col
                            if time_col is None and ('时间' in str(col) or 'time' in col_str or 'date' in col_str):
                                time_col = col
                        if close_col is None:
                            kline_ax.text(0.5, 0.5, "数据格式错误", ha='center', va='center',
                                        transform=kline_ax.transAxes, fontsize=12)
                            kline_canvas.draw()
                            return
                        closes = kline_data[close_col].astype(float).tolist()
                        times = kline_data[time_col].tolist() if time_col else range(len(closes))
                        # 计算均线(1日=16根,5日=80根,10日=160根,20日=320根)
                        ma1_values = []
                        ma5_values = []
                        ma10_values = []
                        ma20_values = []
                        periods = {
                            'ma1': 16,   # 1日 = 16根15分钟K线
                            'ma5': 80,   # 5日 = 80根15分钟K线
                            'ma10': 160, # 10日 = 160根15分钟K线
                            'ma20': 320  # 20日 = 320根15分钟K线
                        }
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
                        kline_ax.clear()
                        kline_ax.plot(times, closes, 'b-', linewidth=1.5, label='创业板指', alpha=0.8)
                        # 绘制均线
                        if any(v is not None for v in ma1_values):
                            ma1_plot = [v if v is not None else closes[i] for i, v in enumerate(ma1_values)]
                            kline_ax.plot(times, ma1_plot, 'r--', linewidth=1, label='MA1', alpha=0.7)
                        if any(v is not None for v in ma5_values):
                            ma5_plot = [v if v is not None else closes[i] for i, v in enumerate(ma5_values)]
                            kline_ax.plot(times, ma5_plot, 'orange', linewidth=1, label='MA5', alpha=0.7)
                        if any(v is not None for v in ma10_values):
                            ma10_plot = [v if v is not None else closes[i] for i, v in enumerate(ma10_values)]
                            kline_ax.plot(times, ma10_plot, 'green', linewidth=1, label='MA10', alpha=0.7)
                        if any(v is not None for v in ma20_values):
                            ma20_plot = [v if v is not None else closes[i] for i, v in enumerate(ma20_values)]
                            kline_ax.plot(times, ma20_plot, 'purple', linewidth=1, label='MA20', alpha=0.7)
                        kline_ax.set_title("创业板指数15分钟K线", fontsize=10, fontweight='bold')
                        kline_ax.set_xlabel('时间', fontsize=9)
                        kline_ax.set_ylabel('指数', fontsize=9)
                        kline_ax.legend(loc='upper left', fontsize=7)
                        kline_ax.grid(True, alpha=0.3)
                        # 旋转日期标签
                        plt.setp(kline_ax.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=7)
                        kline_fig.tight_layout()
                        kline_canvas.draw()
                    except Exception as e:
                        print(f"绘制创业板15分钟K线失败: {e}")
                        import traceback
                        traceback.print_exc()
                        kline_ax.clear()
                        kline_ax.text(0.5, 0.5, f"加载失败:\n{e!s}", ha='center', va='center',
                                    transform=kline_ax.transAxes, fontsize=10, wrap=True)
                        kline_canvas.draw()
                # 异步加载K线图
                alert_window.after(100, draw_cyb_15min_kline)
            except ImportError:
                # 如果matplotlib不可用,显示文本提示
                error_label = tk.Label(kline_frame, text="matplotlib未安装,无法显示K线图",
                                     font=("TkDefaultFont", 11), fg="red")
                error_label.pack(fill=tk.BOTH, expand=True)
            # 闪烁文字控制
            sos_text_visible = [True]  # 使用列表以便在闭包中修改
            def draw_sos_text():
                """绘制SOS警告文字"""
                sos_canvas.delete("all")
                # 获取Canvas大小
                canvas_width = sos_canvas.winfo_width()
                canvas_height = sos_canvas.winfo_height()
                if canvas_width <= 1 or canvas_height <= 1:
                    # 如果Canvas还未渲染,使用默认大小(减去K线图宽度)
                    canvas_width = window_width - 600  # 预留K线图空间
                    canvas_height = 100
                if sos_text_visible[0]:
                    # 显示:红色大字体
                    text_color = "red"
                else:
                    # 隐藏:浅红色(几乎透明)
                    text_color = "#FFCCCC"
                # 文字内容(分成多行显示)
                text_lines = [
                    "SOS!!!快跑路啊!!",
                    "情绪指数奔溃,应该全部减仓。",
                    "无条件禁止开新仓,去乡下躲一躲。"
                ]
                # 计算字体大小(根据Canvas高度和行数)
                num_lines = len(text_lines)
                font_size_by_height = int(canvas_height * 0.8 / num_lines)
                # 根据宽度计算合适的字体大小(取最长的一行)
                max_line_length = max(len(line) for line in text_lines)
                estimated_width = max_line_length * font_size_by_height * 0.6
                if estimated_width > canvas_width * 0.9:
                    font_size_by_width = int(canvas_width * 0.9 / (max_line_length * 0.6))
                    font_size = min(font_size_by_height, font_size_by_width)
                else:
                    font_size = font_size_by_height
                font_size = max(12, int(font_size * 0.6))  # 减小字体,最小字体大小12
                # 计算行间距
                line_height = font_size * 1.2
                total_height = line_height * num_lines
                start_y = (canvas_height - total_height) // 2 + line_height // 2
                # 绘制多行文字(居中显示)
                for i, line in enumerate(text_lines):
                    y_pos = start_y + i * line_height
                    sos_canvas.create_text(
                        canvas_width // 2,
                        y_pos,
                        text=line,
                        fill=text_color,
                        font=("Arial", font_size, "bold"),
                        anchor=tk.CENTER
                    )
            def blink_sos_text():
                """闪烁SOS文字"""
                sos_text_visible[0] = not sos_text_visible[0]
                draw_sos_text()
                # 每300毫秒闪烁一次
                alert_window.after(300, blink_sos_text)
            # 绑定Canvas大小变化事件,自动调整文字大小
            def on_canvas_configure(event):
                draw_sos_text()
            sos_canvas.bind('<Configure>', on_canvas_configure)
            # 初始绘制
            alert_window.after(100, draw_sos_text)  # 延迟绘制,确保Canvas已渲染
            # 开始闪烁
            blink_sos_text()
            # 股票列表框架(可滚动)- 占据主要空间,使用网格布局每行8个
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            canvas = tk.Canvas(list_frame, bg="white")
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 配置网格布局:每行8列
            cards_per_row = 8
            for i in range(cards_per_row):
                scrollable_frame.columnconfigure(i, weight=1, uniform="card")
            # 显示每个股票的破均线信息
            # 持仓组名称映射
            group_names = {
                1: "持仓",
                2: "龙头股",
                3: "15Min",
                4: "Main",
                5: "持仓历史股"
            }
            for idx, alert in enumerate(alerts):
                group_name = group_names.get(alert.get('group_index', 1), "持仓")
                stock_frame = ttk.LabelFrame(scrollable_frame,
                                           text=f"{group_name} - {alert['stock_name']} ({alert['stock_code']})",
                                           padding=8)
                # 计算行和列位置
                row = idx // cards_per_row
                col = idx % cards_per_row
                # 使用grid布局
                stock_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                # 使用单列布局显示股票信息
                text_frame = tk.Frame(stock_frame)
                text_frame.pack(anchor=tk.W, padx=5, pady=5, fill=tk.BOTH, expand=True)
                # 基本信息
                basic_info = f"当前价: {alert['current_price']:.2f}\n"
                basic_info += f"涨跌幅: {alert['change_pct']:+.2f}%\n"
                basic_info += f"破均线: {', '.join(alert['break_types'])}"
                # 检测是否跌停(涨跌幅 <= -9.5%)
                is_limit_down = alert['change_pct'] <= -9.5
                # 显示基本信息
                basic_label = tk.Label(text_frame, text=basic_info, font=("TkDefaultFont", 11),
                                      fg="red", justify=tk.LEFT, wraplength=150)
                basic_label.pack(anchor=tk.W)
                # 如果跌停,显示加大加粗的"跌停"文字
                if is_limit_down:
                    limit_down_label = tk.Label(text_frame, text="跌停",
                                                font=("Arial", 18, "bold"),
                                                fg="red", bg="yellow")
                    limit_down_label.pack(anchor=tk.W, pady=(2, 2))
                # 判断是否需要加粗加大显示(离最高点<=-20%或距20日线<=-20%)
                drop_from_max_pct = alert.get('drop_from_max_10days_pct')
                ma20_dist = alert.get('ma20_distance_pct')
                should_bold = False
                if drop_from_max_pct is not None and drop_from_max_pct <= -20:
                    should_bold = True
                if ma20_dist is not None and ma20_dist <= -20:
                    should_bold = True
                # 均线距离百分比信息(单列显示)
                if alert.get('ma5_distance_pct') is not None:
                    ma5_dist = alert['ma5_distance_pct']
                    ma5_text = f"距5日线: {ma5_dist:+.2f}%"
                    if should_bold:
                        ma5_label = tk.Label(text_frame, text=ma5_text,
                                            font=("TkDefaultFont", 11, "bold"),
                                            fg="red", justify=tk.LEFT, wraplength=150)
                    else:
                        ma5_label = tk.Label(text_frame, text=ma5_text,
                                            font=("TkDefaultFont", 11),
                                            fg="red", justify=tk.LEFT, wraplength=150)
                    ma5_label.pack(anchor=tk.W, pady=(2, 0))
                if alert.get('ma10_distance_pct') is not None:
                    ma10_dist = alert['ma10_distance_pct']
                    ma10_text = f"距10日线: {ma10_dist:+.2f}%"
                    # 距离10日线小于3%时用黄色显示
                    if abs(ma10_dist) < 3:
                        ma10_fg = "orange"
                    else:
                        ma10_fg = "red"
                    if should_bold:
                        ma10_label = tk.Label(text_frame, text=ma10_text,
                                             font=("TkDefaultFont", 11, "bold"),
                                             fg=ma10_fg, justify=tk.LEFT, wraplength=150)
                    else:
                        ma10_label = tk.Label(text_frame, text=ma10_text,
                                             font=("TkDefaultFont", 11),
                                             fg=ma10_fg, justify=tk.LEFT, wraplength=150)
                    ma10_label.pack(anchor=tk.W, pady=(2, 0))
                if alert.get('ma20_distance_pct') is not None:
                    ma20_dist = alert['ma20_distance_pct']
                    ma20_text = f"距20日线: {ma20_dist:+.2f}%"
                    if should_bold:
                        ma20_label = tk.Label(text_frame, text=ma20_text,
                                             font=("TkDefaultFont", 11, "bold"),
                                             fg="red", justify=tk.LEFT, wraplength=150)
                    else:
                        ma20_label = tk.Label(text_frame, text=ma20_text,
                                             font=("TkDefaultFont", 11),
                                             fg="red", justify=tk.LEFT, wraplength=150)
                    ma20_label.pack(anchor=tk.W, pady=(2, 0))
                # 近10日统计信息(单列显示)
                stats_info = ""
                if alert.get('drop_from_max_10days_pct') is not None:
                    drop_pct = alert['drop_from_max_10days_pct']
                    # 不显示10日最高价格,只显示距最高百分比
                    stats_info += f"距最高: {drop_pct:+.2f}%"
                    if should_bold:
                        stats_info += " ⚠️"  # 添加警告标记
                if alert.get('limit_down_count_10days') is not None:
                    limit_down_count = alert['limit_down_count_10days']
                    if stats_info:
                        stats_info += f"\n10日跌停: {limit_down_count}次"
                    else:
                        stats_info = f"10日跌停: {limit_down_count}次"
                if stats_info:
                    if should_bold:
                        stats_label = tk.Label(text_frame, text=stats_info,
                                              font=("TkDefaultFont", 11, "bold"),
                                              fg="red", justify=tk.LEFT, wraplength=150)
                    else:
                        stats_label = tk.Label(text_frame, text=stats_info,
                                              font=("TkDefaultFont", 11),
                                              fg="red", justify=tk.LEFT, wraplength=150)
                    stats_label.pack(anchor=tk.W, pady=(2, 0))
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            # 警告区域(大红灯和警告文字)
            warning_frame = ttk.Frame(main_frame)
            warning_frame.pack(fill=tk.X, pady=(10, 0))
            # 大红灯(使用Canvas绘制红色圆形,支持闪烁)
            light_canvas = tk.Canvas(warning_frame, width=80, height=80, bg="white", highlightthickness=0)
            light_canvas.pack(side=tk.LEFT, padx=(0, 20))
            # 红灯闪烁控制
            light_is_on = [True]  # 使用列表以便在闭包中修改
            def draw_light(is_on):
                """绘制红灯(亮或暗)"""
                light_canvas.delete("all")
                if is_on:
                    # 亮:红色
                    light_canvas.create_oval(10, 10, 70, 70, fill="red", outline="darkred", width=3)
                    # 添加高光效果
                    light_canvas.create_oval(20, 20, 50, 50, fill="", outline="white", width=2)
                else:
                    # 暗:深红色
                    light_canvas.create_oval(10, 10, 70, 70, fill="#660000", outline="darkred", width=3)
                    light_canvas.create_oval(20, 20, 50, 50, fill="", outline="#999999", width=2)
            def blink_light():
                """闪烁红灯"""
                light_is_on[0] = not light_is_on[0]
                draw_light(light_is_on[0])
                # 每500毫秒闪烁一次
                alert_window.after(500, blink_light)
            # 初始绘制
            draw_light(True)
            # 开始闪烁
            blink_light()
            # 声音控制区域
            sound_control_frame = ttk.Frame(warning_frame)
            sound_control_frame.pack(side=tk.LEFT, padx=(0, 20))
            # 声音开关
            sound_enabled = [True]  # 默认开启
            sound_switch_button = tk.Button(sound_control_frame, text="🔊", font=("TkDefaultFont", 16),
                                           command=lambda: toggle_sound(), relief=tk.FLAT, bg="white")
            sound_switch_button.pack(side=tk.TOP, pady=(0, 5))
            def toggle_sound():
                """切换声音开关"""
                sound_enabled[0] = not sound_enabled[0]
                if sound_enabled[0]:
                    sound_switch_button.config(text="🔊", bg="white")
                else:
                    sound_switch_button.config(text="🔇", bg="lightgray")
            # 音量控制
            ttk.Label(sound_control_frame, text="音量:", font=("TkDefaultFont", 11)).pack(side=tk.TOP)
            volume_var = tk.IntVar(value=50)  # 默认音量50%
            volume_scale = ttk.Scale(sound_control_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                    variable=volume_var, length=100)
            volume_scale.pack(side=tk.TOP, pady=(5, 0))
            # 报警声音播放(火警警报声)
            def play_alert_sound():
                """播放火警警报声音(刺耳的高频快速重复声音)"""
                if not sound_enabled[0]:
                    return
                volume = volume_var.get()
                if volume == 0:
                    return
                try:
                    import threading
                    import winsound
                    def play_fire_alarm():
                        """播放火警警报声(高频快速重复)"""
                        # 火警警报:高频(1000-2000Hz)快速重复
                        # 根据音量调整频率范围
                        base_freq = 1000 + int(volume * 10)  # 1000-2000Hz
                        high_freq = 1500 + int(volume * 5)  # 1500-2000Hz
                        # 快速重复3次(模拟火警警报)
                        for i in range(3):
                            # 高频短促声音
                            winsound.Beep(high_freq, 100)
                            time.sleep(0.05)  # 短暂间隔
                            winsound.Beep(base_freq, 100)
                            if i < 2:  # 最后一次不需要间隔
                                time.sleep(0.05)
                    # 在后台线程中播放,避免阻塞
                    threading.Thread(target=play_fire_alarm, daemon=True).start()
                except ImportError:
                    # 如果没有winsound,尝试使用pygame生成更刺耳的声音
                    try:
                        import threading

                        import numpy as np
                        import pygame
                        def play_fire_alarm_pygame():
                            """使用pygame播放火警警报声"""
                            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                            sample_rate = 44100
                            duration = 0.1  # 100毫秒
                            volume_level = volume / 100.0
                            # 生成高频刺耳声音(锯齿波,比正弦波更刺耳)
                            t = np.linspace(0, duration, int(sample_rate * duration))
                            # 火警警报:快速切换两个高频
                            freq1 = 1500 + int(volume * 5)  # 1500-2000Hz
                            freq2 = 2000 + int(volume * 3)  # 2000-2300Hz
                            # 生成锯齿波(更刺耳)
                            wave1 = 2 * (t * freq1 % 1.0) - 1  # 锯齿波
                            wave2 = 2 * (t * freq2 % 1.0) - 1  # 锯齿波
                            # 快速切换
                            wave = np.concatenate([
                                wave1[:len(wave1)//2] * volume_level,
                                wave2[:len(wave2)//2] * volume_level
                            ])
                            # 转换为立体声
                            stereo_wave = np.zeros((len(wave), 2), dtype=np.int16)
                            stereo_wave[:, 0] = (wave * 32767).astype(np.int16)
                            stereo_wave[:, 1] = (wave * 32767).astype(np.int16)
                            sound = pygame.sndarray.make_sound(stereo_wave)
                            # 播放3次(快速重复)
                            for _ in range(3):
                                sound.play()
                                pygame.time.wait(150)  # 150毫秒间隔
                        # 在后台线程中播放
                        threading.Thread(target=play_fire_alarm_pygame, daemon=True).start()
                    except Exception as e:
                        print(f"无法播放火警警报声音: {e}")
                except Exception as e:
                    print(f"播放火警警报声音失败: {e}")
            # 播放报警声音(循环播放,直到窗口关闭)
            def play_sound_loop():
                """循环播放报警声音"""
                if alert_window.winfo_exists() and sound_playing[0]:
                    if sound_enabled[0]:  # 只有在声音开启时才播放
                        play_alert_sound()
                    # 每2秒播放一次
                    alert_window.after(2000, play_sound_loop)
            # 开始播放声音
            play_alert_sound()  # 立即播放一次
            play_sound_loop()  # 开始循环播放
            # 警告文字
            warning_text_frame = ttk.Frame(warning_frame)
            warning_text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            warning_texts = ["快跑路啊", "救命啊", "保住利润", "安全第一!!!!"]
            for text in warning_texts:
                warning_label = tk.Label(warning_text_frame, text=text,
                                        font=("TkDefaultFont", 18, "bold"),
                                        fg="red", bg="white")
                warning_label.pack(side=tk.LEFT, padx=10)
            # 确保窗口显示在最前面
            alert_window.lift()
            alert_window.focus_force()
        # 在主线程中显示
        self.root.after(0, show_alert)


    def _show_ma_alert(self, alerts):
        """显示均线预警弹窗
        Args:
            alerts: 报警列表,每个元素包含股票信息和均线数据
        """
        def show_alert():
            # 创建自定义弹窗,支持彩色文本,2列布局
            alert_window = self._toplevel(self.root)
            alert_window.title("持仓股均线预警")
            alert_window.geometry("1400x800")  # 加宽窗口
            alert_window.transient(self.root)
            # 主框架
            main_frame = ttk.Frame(alert_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 标题
            title_label = ttk.Label(main_frame, text=f"📊 持仓股均线预警 📊\n检测到 {len(alerts)} 只持仓股靠近均线(距离≤3%)",
                                   font=("TkDefaultFont", 15, "bold"))  # 字体加大4号(11+4=15)
            title_label.pack(pady=(0, 10))
            # 内容框架(2列布局)
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill=tk.BOTH, expand=True)
            # 左列
            left_column = ttk.Frame(content_frame)
            left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            left_result_frame = ttk.LabelFrame(left_column, text="持仓股均线预警(左列)", padding=10)
            left_result_frame.pack(fill=tk.BOTH, expand=True)
            left_result_text = scrolledtext.ScrolledText(left_result_frame, wrap=tk.WORD, font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            left_result_text.pack(fill=tk.BOTH, expand=True)
            # 配置文本标签样式(字体都加大4号)
            left_result_text.tag_config("ma5_alert", foreground="red", font=("TkDefaultFont", 15, "bold"))  # 字体加大4号(11+4=15)
            left_result_text.tag_config("ma10_alert", foreground="orange", font=("TkDefaultFont", 15, "bold"))  # 字体加大4号(11+4=15)
            left_result_text.tag_config("ma15_alert", foreground="blue", font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            left_result_text.tag_config("normal", font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            left_result_text.tag_config("header", font=("TkDefaultFont", 14, "bold"))  # 字体加大4号(10+4=14)
            # 右列
            right_column = ttk.Frame(content_frame)
            right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            right_result_frame = ttk.LabelFrame(right_column, text="持仓股均线预警(右列)", padding=10)
            right_result_frame.pack(fill=tk.BOTH, expand=True)
            right_result_text = scrolledtext.ScrolledText(right_result_frame, wrap=tk.WORD, font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            right_result_text.pack(fill=tk.BOTH, expand=True)
            # 配置文本标签样式(字体都加大4号)
            right_result_text.tag_config("ma5_alert", foreground="red", font=("TkDefaultFont", 15, "bold"))  # 字体加大4号(11+4=15)
            right_result_text.tag_config("ma10_alert", foreground="orange", font=("TkDefaultFont", 15, "bold"))  # 字体加大4号(11+4=15)
            right_result_text.tag_config("ma15_alert", foreground="blue", font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            right_result_text.tag_config("normal", font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            right_result_text.tag_config("header", font=("TkDefaultFont", 14, "bold"))  # 字体加大4号(10+4=14)
            # 将预警信息分配到两列
            mid_point = len(alerts) // 2
            left_alerts = alerts[:mid_point]
            right_alerts = alerts[mid_point:]
            # 左列显示
            for alert in left_alerts:
                stock_name = alert['stock_name']
                stock_code = alert['stock_code']
                current_price = alert['current_price']
                group_index = alert['group_index']
                position_index = alert['position_index']
                group_names = {1: "持仓", 2: "龙头股", 3: "15Min", 4: "Main", 5: "持仓历史股"}
                group_name = group_names.get(group_index, f"持仓组{group_index}")
                # 写入标题
                left_result_text.insert(tk.END, f"【{group_name} - 位置{position_index + 1}】\n", "header")
                left_result_text.insert(tk.END, f"{stock_name} ({stock_code})\n", "normal")
                # 显示当前价和涨跌幅
                change_pct = alert.get('change_pct', None)
                if change_pct is not None:
                    change_color = "red" if change_pct >= 0 else "green"
                    change_sign = "+" if change_pct >= 0 else ""
                    left_result_text.insert(tk.END, f"当前价: {current_price:.2f}  ", "normal")
                    left_result_text.insert(tk.END, f"涨跌幅: {change_sign}{change_pct:.2f}%\n", change_color)
                else:
                    left_result_text.insert(tk.END, f"当前价: {current_price:.2f}\n", "normal")
                left_result_text.insert(tk.END, "靠近: ", "normal")
                # 显示靠近的均线信息(带颜色)
                ma_info_parts = []
                if alert['near_ma5']:
                    ma5 = alert['ma5']
                    distance = alert['ma5_distance']
                    ma_info_parts.append(("5日均线", ma5, distance, "ma5_alert"))
                if alert['near_ma10']:
                    ma10 = alert['ma10']
                    distance = alert['ma10_distance']
                    ma_info_parts.append(("10日均线", ma10, distance, "ma10_alert"))
                if alert['near_ma15']:
                    ma15 = alert['ma15']
                    distance = alert['ma15_distance']
                    ma_info_parts.append(("15日均线", ma15, distance, "ma15_alert"))
                # 写入均线信息(带颜色)
                for i, (ma_name, ma_value, distance, tag) in enumerate(ma_info_parts):
                    if i > 0:
                        left_result_text.insert(tk.END, " | ", "normal")
                    ma_text = f"{ma_name}: {ma_value:.2f} (距离: {distance:.2f}%)"
                    left_result_text.insert(tk.END, ma_text, tag)
                left_result_text.insert(tk.END, "\n", "normal")
                # 显示距离N日最高值和最低值的百分比(在右边)
                nday_info_parts = []
                # 5日数据
                pct_5d_high = alert.get('5d_high_pct', None)
                pct_5d_low = alert.get('5d_low_pct', None)
                if pct_5d_high is not None or pct_5d_low is not None:
                    nday_info = "5日:"
                    if pct_5d_high is not None:
                        sign_5h = "+" if pct_5d_high >= 0 else ""
                        nday_info += f" 距最高{sign_5h}{pct_5d_high:.2f}%"
                    if pct_5d_low is not None:
                        sign_5l = "+" if pct_5d_low >= 0 else ""
                        nday_info += f" 距最低{sign_5l}{pct_5d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 10日数据
                pct_10d_high = alert.get('10d_high_pct', None)
                pct_10d_low = alert.get('10d_low_pct', None)
                if pct_10d_high is not None or pct_10d_low is not None:
                    nday_info = "10日:"
                    if pct_10d_high is not None:
                        sign_10h = "+" if pct_10d_high >= 0 else ""
                        nday_info += f" 距最高{sign_10h}{pct_10d_high:.2f}%"
                    if pct_10d_low is not None:
                        sign_10l = "+" if pct_10d_low >= 0 else ""
                        nday_info += f" 距最低{sign_10l}{pct_10d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 20日数据
                pct_20d_high = alert.get('20d_high_pct', None)
                pct_20d_low = alert.get('20d_low_pct', None)
                if pct_20d_high is not None or pct_20d_low is not None:
                    nday_info = "20日:"
                    if pct_20d_high is not None:
                        sign_20h = "+" if pct_20d_high >= 0 else ""
                        nday_info += f" 距最高{sign_20h}{pct_20d_high:.2f}%"
                    if pct_20d_low is not None:
                        sign_20l = "+" if pct_20d_low >= 0 else ""
                        nday_info += f" 距最低{sign_20l}{pct_20d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 显示N日数据(如果有)
                if nday_info_parts:
                    left_result_text.insert(tk.END, "  |  ", "normal")  # 分隔符
                    left_result_text.insert(tk.END, "  ".join(nday_info_parts), "normal")
                left_result_text.insert(tk.END, "\n\n", "normal")
            # 右列显示
            for alert in right_alerts:
                stock_name = alert['stock_name']
                stock_code = alert['stock_code']
                current_price = alert['current_price']
                group_index = alert['group_index']
                position_index = alert['position_index']
                group_names = {1: "持仓", 2: "龙头股", 3: "15Min", 4: "Main", 5: "持仓历史股"}
                group_name = group_names.get(group_index, f"持仓组{group_index}")
                # 写入标题
                right_result_text.insert(tk.END, f"【{group_name} - 位置{position_index + 1}】\n", "header")
                right_result_text.insert(tk.END, f"{stock_name} ({stock_code})\n", "normal")
                # 显示当前价和涨跌幅
                change_pct = alert.get('change_pct', None)
                if change_pct is not None:
                    change_color = "red" if change_pct >= 0 else "green"
                    change_sign = "+" if change_pct >= 0 else ""
                    right_result_text.insert(tk.END, f"当前价: {current_price:.2f}  ", "normal")
                    right_result_text.insert(tk.END, f"涨跌幅: {change_sign}{change_pct:.2f}%\n", change_color)
                else:
                    right_result_text.insert(tk.END, f"当前价: {current_price:.2f}\n", "normal")
                right_result_text.insert(tk.END, "靠近: ", "normal")
                # 显示靠近的均线信息(带颜色)
                ma_info_parts = []
                if alert['near_ma5']:
                    ma5 = alert['ma5']
                    distance = alert['ma5_distance']
                    ma_info_parts.append(("5日均线", ma5, distance, "ma5_alert"))
                if alert['near_ma10']:
                    ma10 = alert['ma10']
                    distance = alert['ma10_distance']
                    ma_info_parts.append(("10日均线", ma10, distance, "ma10_alert"))
                if alert['near_ma15']:
                    ma15 = alert['ma15']
                    distance = alert['ma15_distance']
                    ma_info_parts.append(("15日均线", ma15, distance, "ma15_alert"))
                # 写入均线信息(带颜色)
                for i, (ma_name, ma_value, distance, tag) in enumerate(ma_info_parts):
                    if i > 0:
                        right_result_text.insert(tk.END, " | ", "normal")
                    ma_text = f"{ma_name}: {ma_value:.2f} (距离: {distance:.2f}%)"
                    right_result_text.insert(tk.END, ma_text, tag)
                right_result_text.insert(tk.END, "\n", "normal")
                # 显示距离N日最高值和最低值的百分比(在右边)
                nday_info_parts = []
                # 5日数据
                pct_5d_high = alert.get('5d_high_pct', None)
                pct_5d_low = alert.get('5d_low_pct', None)
                if pct_5d_high is not None or pct_5d_low is not None:
                    nday_info = "5日:"
                    if pct_5d_high is not None:
                        sign_5h = "+" if pct_5d_high >= 0 else ""
                        nday_info += f" 距最高{sign_5h}{pct_5d_high:.2f}%"
                    if pct_5d_low is not None:
                        sign_5l = "+" if pct_5d_low >= 0 else ""
                        nday_info += f" 距最低{sign_5l}{pct_5d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 10日数据
                pct_10d_high = alert.get('10d_high_pct', None)
                pct_10d_low = alert.get('10d_low_pct', None)
                if pct_10d_high is not None or pct_10d_low is not None:
                    nday_info = "10日:"
                    if pct_10d_high is not None:
                        sign_10h = "+" if pct_10d_high >= 0 else ""
                        nday_info += f" 距最高{sign_10h}{pct_10d_high:.2f}%"
                    if pct_10d_low is not None:
                        sign_10l = "+" if pct_10d_low >= 0 else ""
                        nday_info += f" 距最低{sign_10l}{pct_10d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 20日数据
                pct_20d_high = alert.get('20d_high_pct', None)
                pct_20d_low = alert.get('20d_low_pct', None)
                if pct_20d_high is not None or pct_20d_low is not None:
                    nday_info = "20日:"
                    if pct_20d_high is not None:
                        sign_20h = "+" if pct_20d_high >= 0 else ""
                        nday_info += f" 距最高{sign_20h}{pct_20d_high:.2f}%"
                    if pct_20d_low is not None:
                        sign_20l = "+" if pct_20d_low >= 0 else ""
                        nday_info += f" 距最低{sign_20l}{pct_20d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 显示N日数据(如果有)
                if nday_info_parts:
                    right_result_text.insert(tk.END, "  |  ", "normal")  # 分隔符
                    right_result_text.insert(tk.END, "  ".join(nday_info_parts), "normal")
                right_result_text.insert(tk.END, "\n\n", "normal")
            left_result_text.config(state=tk.DISABLED)  # 设置为只读
            right_result_text.config(state=tk.DISABLED)  # 设置为只读
            # 关闭按钮
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            ttk.Button(button_frame, text="关闭", command=alert_window.destroy, width=12).pack()
        # 在主线程中显示弹窗
        self.root.after(0, show_alert)


    def _show_amplitude_alert(self, alerts, market_data=None):
        """显示振幅报警弹窗
        Args:
            alerts: 报警列表,每个元素包含股票信息和振幅数据
            market_data: 市场涨跌板数据
        """
        def show_alert():
            # 创建自定义弹窗,支持显示市场数据,2列布局
            alert_window = self._toplevel(self.root)
            alert_window.title("持仓股振幅报警")
            alert_window.geometry("1400x800")  # 加宽窗口
            alert_window.transient(self.root)
            # 主框架
            main_frame = ttk.Frame(alert_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 标题
            title_label = ttk.Label(main_frame, text=f"⚠️ 持仓股振幅报警 ⚠️\n检测到 {len(alerts)} 只持仓股在1小时内振幅超过5%",
                                   font=("TkDefaultFont", 15, "bold"))  # 字体加大4号(11+4=15)
            title_label.pack(pady=(0, 10))
            # 内容框架(2列布局)
            content_frame = ttk.Frame(main_frame)
            content_frame.pack(fill=tk.BOTH, expand=True)
            # 左列:市场数据
            left_column = ttk.Frame(content_frame)
            left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
            if market_data:
                market_frame = ttk.LabelFrame(left_column, text="市场涨跌板数据", padding=10)
                market_frame.pack(fill=tk.BOTH, expand=True)
                market_text = scrolledtext.ScrolledText(market_frame, wrap=tk.WORD, font=("TkDefaultFont", 13), height=20)  # 字体加大4号(9+4=13)
                market_text.pack(fill=tk.BOTH, expand=True)
                # 配置文本标签样式
                market_text.tag_config("up_limit", foreground="red", font=("TkDefaultFont", 13, "bold"))  # 字体加大4号
                market_text.tag_config("down_limit", foreground="green", font=("TkDefaultFont", 13, "bold"))  # 字体加大4号
                market_text.tag_config("normal", font=("TkDefaultFont", 13))  # 字体加大4号
                market_info = []
                market_info.append(f"涨停板数量: {market_data.get('up_count', 0)} 只\n")
                market_info.append(f"跌停板数量: {market_data.get('down_count', 0)} 只\n")
                up_opened = market_data.get('up_opened', [])
                if up_opened:
                    market_info.append(f"\n涨停板开板: {len(up_opened)} 只\n")
                    for stock in up_opened[:10]:  # 最多显示10只
                        market_info.append(f"  - {stock['name']} ({stock['code']})\n")
                    if len(up_opened) > 10:
                        market_info.append(f"  ... 还有 {len(up_opened) - 10} 只\n")
                down_opened = market_data.get('down_opened', [])
                if down_opened:
                    market_info.append(f"\n跌停板开板: {len(down_opened)} 只\n")
                    for stock in down_opened[:10]:  # 最多显示10只
                        market_info.append(f"  - {stock['name']} ({stock['code']})\n")
                    if len(down_opened) > 10:
                        market_info.append(f"  ... 还有 {len(down_opened) - 10} 只\n")
                # 写入市场数据
                for line in market_info:
                    if "涨停" in line:
                        market_text.insert(tk.END, line, "up_limit")
                    elif "跌停" in line:
                        market_text.insert(tk.END, line, "down_limit")
                    else:
                        market_text.insert(tk.END, line, "normal")
                market_text.config(state=tk.DISABLED)
            # 右列:持仓股振幅报警结果
            right_column = ttk.Frame(content_frame)
            right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
            result_frame = ttk.LabelFrame(right_column, text="持仓股振幅报警", padding=10)
            result_frame.pack(fill=tk.BOTH, expand=True)
            result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, font=("TkDefaultFont", 14))  # 字体加大4号(10+4=14)
            result_text.pack(fill=tk.BOTH, expand=True)
            # 配置文本标签样式
            result_text.tag_config("normal", font=("TkDefaultFont", 14))
            result_text.tag_config("red", foreground="red", font=("TkDefaultFont", 14))
            result_text.tag_config("green", foreground="green", font=("TkDefaultFont", 14))
            for alert in alerts:
                stock_name = alert['stock_name']
                stock_code = alert['stock_code']
                amplitude = alert['amplitude']
                current_price = alert['current_price']
                high = alert['high']
                low = alert['low']
                group_index = alert['group_index']
                position_index = alert['position_index']
                group_names = {1: "持仓", 2: "龙头股", 3: "15Min", 4: "Main", 5: "持仓历史股"}
                group_name = group_names.get(group_index, f"持仓组{group_index}")
                result_text.insert(tk.END, f"【{group_name} - 位置{position_index + 1}】\n")
                result_text.insert(tk.END, f"{stock_name} ({stock_code})\n")
                result_text.insert(tk.END, f"振幅: {amplitude:.2f}%\n")
                # 显示当前价和涨跌幅
                change_pct = alert.get('change_pct', None)
                if change_pct is not None:
                    change_color = "red" if change_pct >= 0 else "green"
                    change_sign = "+" if change_pct >= 0 else ""
                    result_text.insert(tk.END, f"当前价: {current_price:.2f}  ", "normal")
                    result_text.insert(tk.END, f"涨跌幅: {change_sign}{change_pct:.2f}%\n", change_color)
                else:
                    result_text.insert(tk.END, f"当前价: {current_price:.2f}\n", "normal")
                # 显示最高涨幅和最低涨幅
                high_change_pct = alert.get('high_change_pct', None)
                low_change_pct = alert.get('low_change_pct', None)
                result_text.insert(tk.END, f"最高: {high:.2f}", "normal")
                if high_change_pct is not None:
                    high_sign = "+" if high_change_pct >= 0 else ""
                    high_color = "red" if high_change_pct >= 0 else "green"
                    result_text.insert(tk.END, f" (涨幅{high_sign}{high_change_pct:.2f}%)", high_color)
                result_text.insert(tk.END, "  最低: ", "normal")
                result_text.insert(tk.END, f"{low:.2f}", "normal")
                if low_change_pct is not None:
                    low_sign = "+" if low_change_pct >= 0 else ""
                    low_color = "red" if low_change_pct >= 0 else "green"
                    result_text.insert(tk.END, f" (涨幅{low_sign}{low_change_pct:.2f}%)", low_color)
                result_text.insert(tk.END, "\n")
                # 显示距离N日最高值和最低值的百分比(在右边)
                nday_info_parts = []
                # 5日数据
                pct_5d_high = alert.get('5d_high_pct', None)
                pct_5d_low = alert.get('5d_low_pct', None)
                if pct_5d_high is not None or pct_5d_low is not None:
                    nday_info = "5日:"
                    if pct_5d_high is not None:
                        sign_5h = "+" if pct_5d_high >= 0 else ""
                        nday_info += f" 距最高{sign_5h}{pct_5d_high:.2f}%"
                    if pct_5d_low is not None:
                        sign_5l = "+" if pct_5d_low >= 0 else ""
                        nday_info += f" 距最低{sign_5l}{pct_5d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 10日数据
                pct_10d_high = alert.get('10d_high_pct', None)
                pct_10d_low = alert.get('10d_low_pct', None)
                if pct_10d_high is not None or pct_10d_low is not None:
                    nday_info = "10日:"
                    if pct_10d_high is not None:
                        sign_10h = "+" if pct_10d_high >= 0 else ""
                        nday_info += f" 距最高{sign_10h}{pct_10d_high:.2f}%"
                    if pct_10d_low is not None:
                        sign_10l = "+" if pct_10d_low >= 0 else ""
                        nday_info += f" 距最低{sign_10l}{pct_10d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 20日数据
                pct_20d_high = alert.get('20d_high_pct', None)
                pct_20d_low = alert.get('20d_low_pct', None)
                if pct_20d_high is not None or pct_20d_low is not None:
                    nday_info = "20日:"
                    if pct_20d_high is not None:
                        sign_20h = "+" if pct_20d_high >= 0 else ""
                        nday_info += f" 距最高{sign_20h}{pct_20d_high:.2f}%"
                    if pct_20d_low is not None:
                        sign_20l = "+" if pct_20d_low >= 0 else ""
                        nday_info += f" 距最低{sign_20l}{pct_20d_low:.2f}%"
                    nday_info_parts.append(nday_info)
                # 显示N日数据(如果有)
                if nday_info_parts:
                    result_text.insert(tk.END, "  |  ", "normal")  # 分隔符
                    result_text.insert(tk.END, "  ".join(nday_info_parts), "normal")
                result_text.insert(tk.END, "\n\n")
            result_text.config(state=tk.DISABLED)
            # 关闭按钮
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            ttk.Button(button_frame, text="关闭", command=alert_window.destroy, width=12).pack()
        # 在主线程中显示弹窗
        self.root.after(0, show_alert)


    def _on_amplitude_alert_toggle(self):
        """振幅预警开关切换"""
        if self.amplitude_alert_var.get():
            self.amplitude_alert_enabled = True
            print("[预警开关] 振幅预警已开启")
            # 如果监控未运行,启动监控
            if not self.holding_amplitude_monitor_running:
                self._start_holding_amplitude_monitor()
        else:
            self.amplitude_alert_enabled = False
            print("[预警开关] 振幅预警已关闭")


    def _on_ma_alert_toggle(self):
        """均线预警开关切换(监控循环以界面 ma_alert_var 为准,此处同步内部标志并确保监控已启动)"""
        self.ma_alert_enabled = bool(getattr(self, 'ma_alert_var', None) and self.ma_alert_var.get())
        if self.ma_alert_enabled:
            print("[预警开关] 均线预警已开启")
            if not self.holding_amplitude_monitor_running:
                self._start_holding_amplitude_monitor()
        else:
            print("[预警开关] 均线预警已关闭")


    def _on_break_ma1_alert_toggle(self):
        """破1日预警开关切换"""
        if self.break_ma1_alert_var.get():
            self.break_ma1_alert_enabled = True
            print("[预警开关] 破1日预警已开启")
            # 如果监控未运行,启动监控
            if not self.holding_amplitude_monitor_running:
                self._start_holding_amplitude_monitor()
        else:
            self.break_ma1_alert_enabled = False
            print("[预警开关] 破1日预警已关闭")


    def _on_break_ma5_alert_toggle(self):
        """破5日预警开关切换"""
        if self.break_ma5_alert_var.get():
            self.break_ma5_alert_enabled = True
            print("[预警开关] 破5日预警已开启")
            # 如果监控未运行,启动监控
            if not self.holding_amplitude_monitor_running:
                self._start_holding_amplitude_monitor()
        else:
            self.break_ma5_alert_enabled = False
            print("[预警开关] 破5日预警已关闭")


    def _on_break_ma20_alert_toggle(self):
        """破20日预警开关切换"""
        if self.break_ma20_alert_var.get():
            self.break_ma20_alert_enabled = True
            print("[预警开关] 破20日预警已开启")
            # 如果监控未运行,启动监控
            if not self.holding_amplitude_monitor_running:
                self._start_holding_amplitude_monitor()
        else:
            self.break_ma20_alert_enabled = False
            print("[预警开关] 破20日预警已关闭")



__all__ = ["WarningMixin"]

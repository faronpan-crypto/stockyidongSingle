"""一键流水线"""
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
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

import os
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class PipelineMixin:
    """一键流水线"""

    def one_click_pipeline(self):
        """依次执行爬取、分析和资讯入库"""
        if self.pipeline_lock.locked():
            messagebox.showwarning("警告", "一键操作正在执行,请稍后再试")
            return
        if not self.pipeline_lock.acquire(blocking=False):
            messagebox.showwarning("警告", "一键操作正在执行,请稍后再试")
            return
        def pipeline_thread():
            try:
                result_widget = self.get_active_result_widget()
                if result_widget:
                    result_widget.insert(tk.END, "\n🚀 开始一键操作...\n")
                    result_widget.see(tk.END)
                # 0) 新增:模拟点击"爬取韭研 / 爬取淘股吧",等待Excel生成 -> 上传到文本控制富媒体 -> 各自保存到资讯DB
                try:
                    import glob
                    import os
                    import time
                    start_ts = time.time()
                    def log(msg):
                        if result_widget and hasattr(self, "root") and self.root.winfo_exists():
                            self.root.after(0, lambda m=msg: result_widget.insert(tk.END, m + "\n"))
                            self.root.after(0, lambda: result_widget.see(tk.END))
                    def run_on_ui_thread(fn, *args, timeout=120, **kwargs):
                        done = threading.Event()
                        box = {"res": None, "err": None}
                        def _wrap():
                            try:
                                box["res"] = fn(*args, **kwargs)
                            except Exception as e:
                                box["err"] = e
                            finally:
                                done.set()
                        self.root.after(0, _wrap)
                        done.wait(timeout=timeout)
                        if box["err"] is not None:
                            raise box["err"]
                        return box["res"]
                    def _latest_excel_if_any(pattern, since_ts):
                        """
                        在多个目录中返回最近一个匹配文件。
                        逻辑:
                          1) 先尝试找 mtime >= since_ts 的最新文件
                          2) 如果没有这样的文件,但目录中有旧文件,则退而求其次返回"当前最新的那个"
                        这样既兼顾"本次新生成"的 Excel,也不会因为爬虫没成功就完全找不到历史最新文件。
                        """
                        try:
                            scan_dirs = []
                            # 1) 爬虫默认输出目录
                            if 'D_EXPORT_DIR' in globals() and D_EXPORT_DIR:
                                scan_dirs.append(D_EXPORT_DIR)
                            # 2) 程序导出目录(若用户改过)
                            if hasattr(self, "export_dir") and self.export_dir:
                                scan_dirs.append(self.export_dir)
                            # 3) 最近选择/保存过的Excel所在目录(配置文件)
                            try:
                                recent_files = self._get_recent_excel_files(max_count=20)
                                for fi in (recent_files or []):
                                    p = fi.get("path", "")
                                    if p and os.path.exists(p):
                                        d = os.path.dirname(os.path.abspath(p))
                                        if d:
                                            scan_dirs.append(d)
                            except Exception:
                                pass
                            # 去重 + 过滤存在目录
                            uniq_dirs = []
                            seen = set()
                            for d in scan_dirs:
                                try:
                                    dd = os.path.abspath(d)
                                except Exception:
                                    continue
                                if dd in seen:
                                    continue
                                seen.add(dd)
                                if os.path.isdir(dd):
                                    uniq_dirs.append(dd)
                            candidates = []
                            for d in uniq_dirs:
                                try:
                                    candidates.extend(glob.glob(os.path.join(d, pattern)))
                                except Exception:
                                    continue
                            candidates = [f for f in candidates if os.path.exists(f)]
                            if not candidates:
                                return None
                            # 1) 优先:本次开始后生成的文件
                            fresh = [
                                f for f in candidates
                                if os.path.getmtime(f) >= since_ts - 1
                            ]
                            fresh = sorted(fresh, key=os.path.getmtime, reverse=True)
                            if fresh:
                                return fresh[0]
                            # 2) 兜底:没有新文件时,使用当前目录中"最新的一个"作为最近Excel
                            candidates = sorted(candidates, key=os.path.getmtime, reverse=True)
                            return candidates[0] if candidates else None
                        except Exception:
                            return None
                    log("🧲 步骤0:模拟点击爬取韭研按钮...")
                    run_on_ui_thread(self.run_crawler_script, "jiuyan", timeout=10)
                    log("🧲 步骤0:模拟点击爬取淘股吧按钮...")
                    run_on_ui_thread(self.run_crawler_script, "taoguba", timeout=10)
                    # 等待Excel:任何一个生成就立刻上传+入库;不再强制等两份都齐(避免"生成了但后续不执行")
                    processed = set()
                    first_found_at = None
                    total_timeout = 320  # 秒,总超时
                    grace_after_first = 12  # 首个文件出现后,再给另一个文件的宽限秒数
                    deadline = time.time() + total_timeout
                    last_tick = 0
                    def process_excel(fp):
                        """解析Excel->写入富媒体->保存资讯DB(不依赖UI切换)"""
                        log(f"📥 解析并上传Excel到富媒体:{os.path.basename(fp)}")
                        text_content = ""
                        # 优先:xlsx 用 openpyxl 读取(更稳,不依赖 pandas 引擎)
                        try:
                            if str(fp).lower().endswith(".xlsx"):
                                from openpyxl import load_workbook
                                wb = load_workbook(fp, data_only=True)
                                ws = wb.active
                                lines = []
                                for row in ws.iter_rows(values_only=True):
                                    vals = []
                                    for v in row:
                                        if v is None:
                                            vals.append("")
                                        else:
                                            vals.append(str(v))
                                    # 去掉末尾空列
                                    while vals and vals[-1] == "":
                                        vals.pop()
                                    if any(x != "" for x in vals):
                                        lines.append("\t".join(vals))
                                text_content = "\n".join(lines).strip()
                        except Exception as e_openpyxl:
                            text_content = ""
                            log(f"⚠️ openpyxl读取失败,回退pandas:{e_openpyxl}")
                        # 回退:pandas(支持多sheet/以及xls)
                        if not text_content:
                            try:
                                import pandas as pd
                                df = pd.read_excel(fp)
                                text_content = df.to_string(index=False).strip()
                            except Exception as e_read:
                                log(f"⚠️ pandas读取Excel失败,跳过:{e_read}")
                                return
                        tab_title = f"Excel_{os.path.basename(fp)}"
                        def _create_tab_ui():
                            try:
                                if hasattr(self, "crawler_control_notebook"):
                                    try:
                                        self.crawler_control_notebook.select(1)
                                    except Exception:
                                        pass
                                tab_id_local = self.create_text_tab(tab_title)
                                if tab_id_local in self.text_widgets:
                                    tw = self.text_widgets[tab_id_local]["widget"]
                                    tw.delete("1.0", tk.END)
                                    tw.insert(tk.END, f"\n{'='*80}\n")
                                    tw.insert(tk.END, f"文件: {os.path.basename(fp)}\n")
                                    tw.insert(tk.END, f"{'='*80}\n\n")
                                    tw.insert(tk.END, text_content)
                                    tw.see("1.0")
                            except Exception as e_ui:
                                try:
                                    result_widget.insert(tk.END, f"⚠️ 创建富媒体标签页失败: {e_ui}\n")
                                    result_widget.see(tk.END)
                                except Exception:
                                    pass
                        self.root.after(0, _create_tab_ui)
                        try:
                            if save_news_info_to_db(tab_title, text_content):
                                log(f"💾 已保存到资讯DB:{tab_title}")
                            else:
                                log(f"⚠️ 保存到资讯DB失败:{tab_title}")
                        except Exception as e_db:
                            log(f"⚠️ 保存到资讯DB异常:{e_db}")
                    while time.time() < deadline:
                        jiuyan_xlsx = (
                            _latest_excel_if_any("jiuyang_gongshe_*.xlsx", start_ts)
                            or _latest_excel_if_any("jiuyang_gongshe_*.xls", start_ts)
                            or _latest_excel_if_any("jiuyang_gongshe_*.xlsx", start_ts)  # 兼容历史拼写
                            or _latest_excel_if_any("jiuyang_gongshe_*.xls", start_ts)
                            or _latest_excel_if_any("jiuyang_gongshe_*.xlsx", start_ts)
                        )
                        if jiuyan_xlsx and jiuyan_xlsx not in processed:
                            processed.add(jiuyan_xlsx)
                            first_found_at = first_found_at or time.time()
                            log(f"✅ 韭研Excel已生成:{os.path.basename(jiuyan_xlsx)}")
                            process_excel(jiuyan_xlsx)
                        # 淘股吧:可能是 taoguba_*.xlsx / taoguba_*.xls / taoguba_100_posts_*.xlsx / taoguba_100_posts_*.xls
                        taoguba_xlsx = (
                            _latest_excel_if_any("taoguba_*.xlsx", start_ts)
                            or _latest_excel_if_any("taoguba_*.xls", start_ts)
                            or _latest_excel_if_any("taoguba_100_posts_*.xlsx", start_ts)
                            or _latest_excel_if_any("taoguba_100_posts_*.xls", start_ts)
                        )
                        if taoguba_xlsx and taoguba_xlsx not in processed:
                            processed.add(taoguba_xlsx)
                            first_found_at = first_found_at or time.time()
                            log(f"✅ 淘股吧Excel已生成:{os.path.basename(taoguba_xlsx)}")
                            process_excel(taoguba_xlsx)
                        # 如果两份都处理了,直接结束等待
                        if jiuyan_xlsx and taoguba_xlsx and jiuyan_xlsx in processed and taoguba_xlsx in processed:
                            break
                        # 如果已经处理到至少一份,宽限一会儿就继续后续动作(不无限等第二份)
                        if first_found_at and time.time() - first_found_at >= grace_after_first:
                            break
                        now = time.time()
                        if now - last_tick >= 10:
                            left = int(deadline - now)
                            log(f"⏳ 等待Excel生成中...(剩余约{left}s)")
                            last_tick = now
                        time.sleep(1.5)
                    if not processed:
                        log("i️ 未找到可上传的Excel文件,跳过“Excel->富媒体->资讯DB“步骤。")
                    else:
                        log("✅ Excel上传/保存步骤执行完毕(韭研/淘股吧,先到先处理)。")
                except Exception as e:
                    if result_widget:
                        try:
                            result_widget.insert(tk.END, f"⚠️ 步骤0执行异常(不中断后续一键操作): {e}\n")
                            result_widget.see(tk.END)
                        except Exception:
                            pass
                self.batch_crawl_and_analyze()
                self.batch_crawl_event.wait()
                self.one_click_analyze_tabs()
                self.one_click_analyze_event.wait()
                self.one_click_save_news()
                self.one_click_news_event.wait()
                if result_widget:
                    result_widget.insert(tk.END, "✅ 一键操作完成,资讯已入库\n")
                    result_widget.see(tk.END)
                messagebox.showinfo("成功", "一键操作完成,资讯已保存到数据库")
            finally:
                self.pipeline_lock.release()
        threading.Thread(target=pipeline_thread, daemon=True).start()

    def show_one_click_thinking(self):
        """打开一键思考界面"""
        try:
            win = self._toplevel(self.root)
            win.title("一键思考工作台")
            win.geometry("1400x800")
            win.transient(self.root)
            win.resizable(True, True)
            # 存储窗口状态
            win._is_minimized = False
            win._original_geometry = "1400x800"
            win.columnconfigure(0, weight=1)
            win.columnconfigure(1, weight=1)
            win.rowconfigure(1, weight=1)
            # 头部说明
            header = ttk.Label(
                win,
                text="选择分析维度,选中的维度将作为分析条件插入到左侧文本框",
                anchor="center",
                font=("Microsoft YaHei", 14, "bold")
            )
            header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
            # 左侧:问题描述
            left_frame = ttk.LabelFrame(win, text="分析条件维度", padding=10)
            left_frame.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
            left_frame.columnconfigure(0, weight=1)
            left_frame.rowconfigure(1, weight=1)
            condition_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=25, font=("TkDefaultFont", 12))
            condition_text.grid(row=1, column=0, sticky="nsew")
            # 右侧:分析结果
            right_frame = ttk.LabelFrame(win, text="分析结果", padding=10)
            right_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
            right_frame.columnconfigure(0, weight=1)
            right_frame.rowconfigure(1, weight=1)
            result_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, height=25, font=("TkDefaultFont", 12), state=tk.DISABLED)
            self._enable_clickable_links(result_text)
            result_text.grid(row=1, column=0, sticky="nsew")
            # 底部:所有分析维度选项(带checkbox)
            control_frame = ttk.LabelFrame(win, text="分析维度选择", padding=10)
            control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
            # 定义所有分析维度选项
            all_dimensions = {
                "咨询分析": {
                    "麦肯锡 7S": "战略、结构、系统、风格、人员、技能、价值观",
                    "波士顿矩阵": "明星、现金牛、问号、瘦狗产品分类",
                    "埃森哲价值地图": "价值创造和价值获取路径",
                    "波特五力": "竞争环境分析:供应商、买方、替代品、潜在进入者、同业竞争",
                    "PESTEL": "政治、经济、社会、技术、环境、法律分析",
                    "SWOT": "优势、劣势、机会、威胁分析",
                    "安索夫矩阵": "市场-产品增长策略",
                    "GE 九宫格": "行业吸引力与竞争地位评估",
                    "3C 模型": "公司、客户、竞争对手分析",
                    "价值链分析": "企业内部价值创造活动分析",
                    "综合推断 (咨询)": "整合多个咨询框架的综合分析",
                    "平衡计分卡": "财务、客户、内部流程、学习成长四个维度",
                    "OKR 对齐": "目标与关键结果对齐分析"
                },
                "投资": {
                    "股票": "股票投资分析,包括个股选择、行业分析、技术面、基本面等",
                    "房地产": "房地产投资分析,包括住宅、商业地产、REITs等投资机会",
                    "债券": "债券投资分析,包括国债、企业债、可转债等固定收益产品",
                    "数字货币": "数字货币投资分析,包括比特币、以太坊等加密货币",
                    "基金": "基金投资分析,包括股票基金、债券基金、混合基金、ETF等",
                    "期货": "期货投资分析,包括商品期货、金融期货等衍生品",
                    "外汇": "外汇投资分析,包括主要货币对、汇率走势等",
                    "黄金": "黄金投资分析,包括实物黄金、黄金ETF、黄金期货等",
                    "大宗商品": "大宗商品投资分析,包括原油、铜、农产品等",
                    "另类投资": "另类投资分析,包括私募股权、对冲基金、艺术品等"
                },
                "系统": {
                    "价值投资": "本杰明·格雷厄姆和沃伦·巴菲特的价值投资体系",
                    "海龟交易法则": "理查德·丹尼斯的海龟交易系统,基于趋势跟踪、仓位管理",
                    "量化投资": "基于数学模型和算法的量化投资策略",
                    "技术分析": "基于价格和成交量图表的技术分析方法",
                    "基本面分析": "基于公司财务数据、行业状况、宏观经济的基本面分析",
                    "成长投资": "菲利普·费雪的成长投资策略,关注高成长性公司",
                    "动量投资": "基于价格动量和相对强度的动量投资策略",
                    "均值回归": "基于价格偏离均值的均值回归投资策略",
                    "因子投资": "基于多因子模型的因子投资策略",
                    "资产配置": "现代投资组合理论,包括马科维茨模型、风险平价等"
                },
                "赌博": {
                    "凯利公式": "计算最优投注比例,基于胜率和赔率",
                    "概率计算": "计算各种概率场景,包括胜率、赔率、期望值等",
                    "风险收益比": "计算风险收益比,评估投资机会的风险调整后收益",
                    "仓位管理": "基于概率和风险的资金管理策略",
                    "期望值分析": "计算投资的期望值,评估长期收益预期",
                    "最大回撤": "分析最大回撤风险,评估资金管理的安全性",
                    "夏普比率": "计算风险调整后的收益指标,评估投资效率",
                    "蒙特卡洛模拟": "使用蒙特卡洛方法模拟投资结果,评估概率分布",
                    "VaR风险值": "计算在险价值,评估投资组合的风险敞口",
                    "压力测试": "进行压力测试,评估极端情况下的投资表现"
                },
                "安全": {
                    "同花顺情绪指数": "分析同花顺情绪指数883404的日K、60分钟周期、15分钟周期的情绪判断,以及情绪指数相关的重要指标和分析",
                    "信用风险": "评估交易对手的信用风险,包括公司财务状况、债务水平",
                    "市场风险": "评估市场波动带来的风险,包括系统性风险、黑天鹅事件",
                    "流动性风险": "评估资产变现的难易程度,包括交易量、买卖价差",
                    "操作风险": "评估操作失误带来的风险,包括下单错误、系统故障",
                    "政策风险": "评估政策变化带来的风险,包括监管政策、税收政策",
                    "汇率风险": "评估汇率波动带来的风险,包括外汇敞口、汇率对冲",
                    "集中度风险": "评估投资过于集中带来的风险",
                    "杠杆风险": "评估使用杠杆带来的风险,包括融资融券、期货杠杆",
                    "估值风险": "评估资产估值过高带来的风险,包括PE/PB过高、泡沫风险"
                },
                "流动性": {
                    "市场流动性": "评估标的物的市场流动性,包括成交量、换手率、买卖盘深度",
                    "跌停板检查": "检查是否处于跌停板状态,跌停板无法买入,缺乏流动性",
                    "涨停板检查": "检查是否处于涨停板状态,涨停板难以买入,流动性受限",
                    "停牌检查": "检查是否处于停牌状态,停牌期间无法交易,无流动性",
                    "ST股票检查": "检查是否为ST股票,ST股票交易受限,流动性较差",
                    "成交量分析": "分析成交量变化,评估市场参与度和流动性状况",
                    "买卖价差": "分析买卖价差,评估交易成本和流动性质量",
                    "大宗交易": "分析大宗交易情况,评估机构参与度和市场深度",
                    "限售解禁": "分析限售股解禁情况,评估潜在抛压和流动性冲击",
                    "不当投资检查": "检查不当投资情况,如跌停板、停牌、ST等流动性陷阱"
                },
                "利润": {
                    "趋势分析": "分析价格趋势,包括月线MACD双金叉、60分钟短线非死叉、15分钟多头排列",
                    "月线MACD双金叉": "月线级别MACD双金叉,确认长期上涨趋势",
                    "60分钟非死叉": "60分钟级别MACD未死叉,确认中期上涨趋势",
                    "15分钟多头排列": "15分钟级别均线多头排列,确认短期上涨趋势",
                    "技术指标": "综合分析各种技术指标,包括MACD、KDJ、RSI、BOLL等",
                    "量价关系": "分析成交量与价格的关系,确认上涨的有效性",
                    "支撑阻力": "分析关键支撑位和阻力位,确定买入和卖出时机",
                    "形态识别": "识别K线形态,包括头肩底、双底、三角形等反转或持续形态",
                    "资金流向": "分析主力资金流向,确认资金是否流入",
                    "盈利预期": "评估盈利预期,包括目标价位、止损价位、风险收益比"
                }
            }
            # 存储所有checkbox变量
            checkbox_vars = {}
            # 创建滚动框架
            scroll_frame = ttk.Frame(control_frame)
            scroll_frame.pack(fill=tk.BOTH, expand=True)
            # 添加滚动条
            canvas = tk.Canvas(scroll_frame, height=200)
            scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            # 添加鼠标滚轮支持
            def on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            canvas.bind("<MouseWheel>", on_mousewheel)
            scrollable_frame.bind("<MouseWheel>", on_mousewheel)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            # 先定义run_ai_analysis函数(供checkbox回调使用)
            def run_ai_analysis():
                """运行AI分析"""
                selected = []
                for option_name, var in checkbox_vars.items():
                    if var.get():
                        selected.append(option_name)
                if not selected:
                    messagebox.showwarning("提示", "请至少选择一个分析维度")
                    return
                # 检查是否选择了"同花顺情绪指数",如果是,自动生成询问
                if "同花顺情绪指数" in selected:
                    # 自动生成同花顺情绪指数的询问
                    problem = "同花顺情绪指数883404的日K,60分钟周期,15分钟周期的情绪判断如何,情绪指数相关的重要指标和分析有哪些,现在如何。"
                else:
                    problem = condition_text.get("1.0", tk.END).strip()
                    if not problem:
                        messagebox.showwarning("提示", "请输入分析问题")
                        return
                # 构建分析提示
                dimensions_text = "\n".join([f"- {dim}" for dim in selected])
                prompt = f"""请基于以下分析维度,对以下问题进行综合分析:
分析维度:
{dimensions_text}
分析问题:
{problem}
请提供:
1. 各维度下的关键分析点
2. 维度间的关联和影响
3. 综合判断和建议
4. 风险提示和注意事项"""
                result_text.config(state=tk.NORMAL)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "AI分析中,请稍候...\n")
                result_text.config(state=tk.DISABLED)
                def analyze():
                    try:
                        system_prompt = "你是一位资深的多维度投资分析专家,能够从多个角度综合分析投资问题。"
                        ai_result = self.call_ai_model(prompt, system_prompt)
                        if not ai_result:
                            ai_result = "未获取到AI分析结果,请检查配置。"
                    except Exception as e:
                        ai_result = f"AI分析失败: {e}"
                    def update_ui():
                        result_text.config(state=tk.NORMAL)
                        result_text.delete("1.0", tk.END)
                        result_text.insert(tk.END, "综合分析结果\n\n")
                        result_text.insert(tk.END, "="*50 + "\n\n")
                        result_text.insert(tk.END, f"分析维度:{', '.join(selected)}\n\n")
                        result_text.insert(tk.END, "="*50 + "\n\n")
                        result_text.insert(tk.END, ai_result)
                        result_text.config(state=tk.DISABLED)
                        result_text.see("1.0")
                    if hasattr(self, "root") and self.root.winfo_exists():
                        self.root.after(0, update_ui)
                threading.Thread(target=analyze, daemon=True).start()
            # 按分类创建checkbox
            row = 0
            for category, options in all_dimensions.items():
                # 分类标题
                category_label = ttk.Label(scrollable_frame, text=f"【{category}】",
                                          font=("TkDefaultFont", 12, "bold"))
                category_label.grid(row=row, column=0, columnspan=5, sticky="w", padx=5, pady=(10, 5))
                row += 1
                # 该分类的选项
                col = 0
                for option_name in options:
                    var = tk.BooleanVar()
                    checkbox_vars[option_name] = var
                    # 为"同花顺情绪指数"添加特殊处理:点击后自动触发AI询问
                    if option_name == "同花顺情绪指数":
                        def make_callback(opt_name, checkbox_var):
                            def on_check():
                                # 当选中时,自动触发AI分析
                                if checkbox_var.get():
                                    # 自动填充问题
                                    condition_text.delete("1.0", tk.END)
                                    condition_text.insert("1.0", "同花顺情绪指数883404的日K,60分钟周期,15分钟周期的情绪判断如何,情绪指数相关的重要指标和分析有哪些,现在如何。")
                                    # 延迟触发AI分析,确保UI已更新
                                    win.after(100, run_ai_analysis)
                            return on_check
                        command = make_callback(option_name, var)
                    else:
                        command = None
                    checkbox = ttk.Checkbutton(
                        scrollable_frame,
                        text=option_name,
                        variable=var,
                        command=command if command else None,
                        width=20
                    )
                    checkbox.grid(row=row, column=col, padx=5, pady=3, sticky="w")
                    col += 1
                    if col >= 5:
                        col = 0
                        row += 1
                if col > 0:
                    row += 1
            # 按钮区域
            button_frame = ttk.Frame(win)
            button_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
            def insert_selected_dimensions():
                """将选中的维度插入到左侧文本框"""
                selected = []
                for option_name, var in checkbox_vars.items():
                    if var.get():
                        selected.append(option_name)
                if not selected:
                    messagebox.showwarning("提示", "请至少选择一个分析维度")
                    return
                # 获取当前活动的左侧文本框
                active_text = self.get_active_text_widget()
                if not active_text:
                    messagebox.showwarning("提示", "请先打开一个文本标签页")
                    return
                # 插入选中的维度
                dimensions_text = "分析条件维度:\n" + "\n".join([f"- {dim}" for dim in selected])
                # 在文本末尾插入
                active_text.insert(tk.END, "\n\n" + dimensions_text + "\n")
                active_text.see(tk.END)
                messagebox.showinfo("成功", f"已插入 {len(selected)} 个分析维度到当前文本标签页")
            def clear_all():
                """清空所有内容"""
                condition_text.delete("1.0", tk.END)
                result_text.config(state=tk.NORMAL)
                result_text.delete("1.0", tk.END)
                result_text.config(state=tk.DISABLED)
                # 取消所有checkbox
                for var in checkbox_vars.values():
                    var.set(False)
            def select_all():
                """全选所有维度"""
                for var in checkbox_vars.values():
                    var.set(True)
            def deselect_all():
                """取消全选"""
                for var in checkbox_vars.values():
                    var.set(False)
            ttk.Button(button_frame, text="插入到左侧", command=insert_selected_dimensions, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="AI分析", command=run_ai_analysis, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="全选", command=select_all, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="全不选", command=deselect_all, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="清空", command=clear_all, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="复制结果",
                      command=lambda: self._copy_text_to_clipboard(result_text), width=12).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="添加到咨询",
                      command=lambda: self._add_to_consultation(result_text), width=12).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="添加到警示",
                      command=lambda: self._add_to_warning(result_text), width=12).pack(side=tk.LEFT, padx=5)
            # 窗口控制按钮
            control_btn_frame = ttk.Frame(win)
            control_btn_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
            def toggle_minimize():
                """切换最小化/恢复"""
                if win._is_minimized:
                    win.geometry(win._original_geometry)
                    win._is_minimized = False
                    minimize_btn.config(text="最小化")
                else:
                    win._original_geometry = win.geometry()
                    win.geometry("200x50")
                    win._is_minimized = True
                    minimize_btn.config(text="恢复")
            def toggle_maximize():
                """切换最大化/恢复"""
                try:
                    # Windows平台使用state('zoomed')
                    if win.state() == 'zoomed':
                        win.state('normal')
                        win.geometry(win._original_geometry)
                        maximize_btn.config(text="最大化")
                    else:
                        win._original_geometry = win.geometry()
                        win.state('zoomed')
                        maximize_btn.config(text="恢复")
                except:
                    # 如果state不支持,尝试使用geometry
                    try:
                        current_geom = win.geometry()
                        if hasattr(win, '_is_maximized') and win._is_maximized:
                            win.geometry(win._original_geometry)
                            win._is_maximized = False
                            maximize_btn.config(text="最大化")
                        else:
                            win._original_geometry = current_geom
                            # 获取屏幕尺寸
                            screen_width = win.winfo_screenwidth()
                            screen_height = win.winfo_screenheight()
                            win.geometry(f"{screen_width}x{screen_height}+0+0")
                            win._is_maximized = True
                            maximize_btn.config(text="恢复")
                    except Exception as e:
                        messagebox.showinfo("提示", f"最大化功能不可用: {e}")
            minimize_btn = ttk.Button(control_btn_frame, text="最小化", command=toggle_minimize, width=10)
            minimize_btn.pack(side=tk.LEFT, padx=5)
            maximize_btn = ttk.Button(control_btn_frame, text="最大化", command=toggle_maximize, width=10)
            maximize_btn.pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="隐藏", command=win.withdraw, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="显示", command=win.deiconify, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(control_btn_frame, text="关闭", command=win.destroy, width=10).pack(side=tk.RIGHT, padx=5)
        except Exception as e:
            messagebox.showerror("错误", f"打开一键思考界面失败: {e}")
            import traceback
            traceback.print_exc()


__all__ = ["PipelineMixin"]

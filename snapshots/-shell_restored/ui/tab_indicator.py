"""技术指标/均线/MACD/KDJ/RSI"""
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
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError: plt = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

import re
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class IndicatorMixin:
    """技术指标/均线/MACD/KDJ/RSI"""

    def _apply_popup_fonts_recursive(self, widget, fam, sz):
        for ch in widget.winfo_children():
            try:
                if isinstance(ch, (scrolledtext.ScrolledText, tk.Text)):
                    self._configure_popup_text_font(ch, fam, sz)
                elif isinstance(ch, (tk.Entry, tk.Listbox, tk.Label, tk.Button, tk.Menubutton, tk.Checkbutton, tk.Radiobutton, tk.Spinbox)):
                    ch.configure(font=(fam, sz))
            except Exception:
                pass
            try:
                self._apply_popup_fonts_recursive(ch, fam, sz)
            except Exception:
                pass

    def _calculate_mean_reversion(self, kline_data, stock_name):
        """计算均值回归指标。
        均值回归策略基于以下原理:
        1. 计算价格相对于均值的偏离程度(Z-score)
        2. 当价格偏离均值超过一定阈值时,预测价格会回归均值
        3. 根据偏离程度计算仓位
        Returns:
            dict: 包含Z-score、回归概率、建议仓位等详细信息
        """
        result = {
            'success': False,
            'message': '',
            'z_score': 0.0,
            'mean_price': 0.0,
            'std_deviation': 0.0,
            'current_price': 0.0,
            'reversion_probability': 0.0,
            'suggested_position': 0.0,
            'calculation_steps': [],
            'analysis': []
        }
        try:
            data = kline_data['data']
            n = len(data)
            if n < 20:
                result['message'] = '数据不足,至少需要20条K线'
                return result
            closes = data['收盘'].values
            current_price = float(closes[-1])
            result['current_price'] = current_price
            steps = []
            # 使用最近20日收盘价计算均值和标准差
            window_size = min(20, n)
            recent_closes = closes[-window_size:]
            recent_closes_list = [float(c) for c in recent_closes]
            mean_price = sum(recent_closes_list) / len(recent_closes_list)
            result['mean_price'] = round(mean_price, 2)
            steps.append(f"【步骤1】计算均值:MA{window_size} = {mean_price:.2f}")
            variance = sum((p - mean_price) ** 2 for p in recent_closes_list) / len(recent_closes_list)
            std_deviation = variance ** 0.5
            result['std_deviation'] = round(std_deviation, 2)
            steps.append(f"【步骤2】计算标准差:STD = {std_deviation:.2f}")
            # 计算Z-score
            if std_deviation > 0:
                z_score = (current_price - mean_price) / std_deviation
                result['z_score'] = round(z_score, 4)
                steps.append(f"【步骤3】计算Z-score:Z = ({current_price:.2f} - {mean_price:.2f}) / {std_deviation:.2f} = {z_score:.4f}")
            else:
                z_score = 0.0
                result['z_score'] = 0.0
                steps.append("【步骤3】计算Z-score:标准差为0,Z = 0")
            # 根据Z-score计算回归概率(使用正态分布近似)
            # Z-score绝对值越大,回归概率越高
            abs_z = abs(z_score)
            if abs_z >= 3.0:
                reversion_probability = 0.95
            elif abs_z >= 2.0:
                reversion_probability = 0.85
            elif abs_z >= 1.5:
                reversion_probability = 0.75
            elif abs_z >= 1.0:
                reversion_probability = 0.65
            elif abs_z >= 0.5:
                reversion_probability = 0.55
            else:
                reversion_probability = 0.50
            result['reversion_probability'] = round(reversion_probability * 100, 1)
            steps.append(f"【步骤4】回归概率:|Z| = {abs_z:.2f},概率 = {reversion_probability * 100:.1f}%")
            # 计算建议仓位
            # 当Z-score为负(低于均值),建议买入;当Z-score为正(高于均值),建议卖出
            # 仓位大小与Z-score绝对值成正比,但不超过50%
            base_position = min(abs_z * 0.15, 0.5)
            if z_score < -0.5:
                suggested_position = base_position
                steps.append(f"【步骤5】建议仓位:Z({z_score:.2f}) < -0.5,建议买入,仓位 = {base_position * 100:.1f}%")
            elif z_score > 0.5:
                suggested_position = -base_position
                steps.append(f"【步骤5】建议仓位:Z({z_score:.2f}) > 0.5,建议卖出,仓位 = -{base_position * 100:.1f}%")
            else:
                suggested_position = 0.0
                steps.append(f"【步骤5】建议仓位:|Z|({abs_z:.2f}) < 0.5,无明确信号,仓位 = 0%")
            result['suggested_position'] = round(suggested_position * 100, 1)
            result['calculation_steps'] = steps
            # 生成分析说明
            analysis = []
            analysis.append(f"当前价格:{current_price:.2f}")
            analysis.append(f"{window_size}日均价:{mean_price:.2f}")
            analysis.append(f"标准差:{std_deviation:.2f}")
            analysis.append(f"Z-score:{z_score:.4f}")
            analysis.append(f"回归概率:{result['reversion_probability']:.1f}%")
            if suggested_position > 0:
                analysis.append(f"建议操作:买入,仓位 {suggested_position:.1f}%")
                analysis.append(f"原理:价格低于均值 {abs(z_score):.2f} 个标准差,预计回归")
            elif suggested_position < 0:
                analysis.append(f"建议操作:卖出,仓位 {-suggested_position:.1f}%")
                analysis.append(f"原理:价格高于均值 {abs(z_score):.2f} 个标准差,预计回归")
            else:
                analysis.append("建议操作:观望,价格接近均值,无明确回归信号")
            result['analysis'] = analysis
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result

    def _show_tech_indicator_dialog(self, initial_indicator="MACD"):
        """显示技术指标分析对话框"""
        indicator_info = {
            "MACD": {
                "description": "MACD(指数平滑异同移动平均线)是基于均线的趋势跟踪指标。\n\n计算方法:\n- DIF = 12日EMA - 26日EMA\n- DEA = DIF的9日EMA\n- MACD柱 = (DIF - DEA) × 2\n\n信号解读:\n- DIF上穿DEA为金叉,买入信号\n- DIF下穿DEA为死叉,卖出信号\n- MACD柱红转绿/绿转红为趋势反转信号",
                "applicability": "趋势",
                "formula": "DIF = EMA(12) - EMA(26)\nDEA = EMA(DIF, 9)\nMACD = (DIF - DEA) × 2"
            },
            "RSI": {
                "description": "RSI(相对强弱指标)是衡量价格变动速度和幅度的震荡指标。\n\n计算方法:\n- 平均上涨幅度 = 最近N日上涨幅度平均值\n- 平均下跌幅度 = 最近N日下跌幅度平均值\n- RSI = 100 - (100 / (1 + 平均上涨幅度/平均下跌幅度))\n\n信号解读:\n- RSI > 70:超买区域,可能回调\n- RSI < 30:超卖区域,可能反弹\n- RSI背离:价格新高但RSI未新高,顶背离(看空);价格新低但RSI未新低,底背离(看多)",
                "applicability": "震荡",
                "formula": "RSI(N) = 100 - (100 / (1 + AvgGain/AvgLoss))"
            },
            "KDJ": {
                "description": "KDJ(随机指标)是基于最高价、最低价和收盘价的震荡指标。\n\n计算方法:\n- RSV = (收盘价 - N日最低价) / (N日最高价 - N日最低价) × 100\n- K = RSV的3日EMA\n- D = K的3日EMA\n- J = 3K - 2D\n\n信号解读:\n- K上穿D为金叉,买入信号\n- K下穿D为死叉,卖出信号\n- J > 100:超买区域\n- J < 0:超卖区域",
                "applicability": "震荡",
                "formula": "RSV = (C - L(N)) / (H(N) - L(N)) × 100\nK = EMA(RSV, 3)\nD = EMA(K, 3)\nJ = 3K - 2D"
            },
            "BOLL": {
                "description": "BOLL(布林带)是基于移动平均线和标准差的通道指标。\n\n计算方法:\n- 中轨 = 20日MA\n- 上轨 = 20日MA + 2×标准差\n- 下轨 = 20日MA - 2×标准差\n\n信号解读:\n- 价格触及上轨:可能回调\n- 价格触及下轨:可能反弹\n- 布林带收口:行情即将突破\n- 布林带开口:行情加速",
                "applicability": "震荡+趋势",
                "formula": "中轨 = MA(20)\n上轨 = MA(20) + 2×STD\n下轨 = MA(20) - 2×STD"
            },
            "MA": {
                "description": "MA(移动平均线)是最基础的趋势跟踪指标。\n\n计算方法:\n- MA(N) = 最近N日收盘价的算术平均\n\n常用均线:\n- MA5:短期均线\n- MA10:中期均线\n- MA20:生命线\n- MA60:中期趋势线\n- MA250:年线\n\n信号解读:\n- 均线多头排列(MA5>MA10>MA20>MA60):上升趋势\n- 均线空头排列(MA5<MA10<MA20<MA60):下降趋势\n- 价格上穿均线:买入信号\n- 价格下穿均线:卖出信号",
                "applicability": "趋势",
                "formula": "MA(N) = (C1 + C2 + ... + CN) / N"
            },
            "VOL": {
                "description": "VOL(成交量)是衡量市场活跃度的指标。\n\n计算方法:\n- 成交量 = 当日成交股数\n- 均量线 = 成交量的N日移动平均\n\n信号解读:\n- 价涨量增:健康的上升趋势\n- 价涨量缩:上涨乏力,可能回调\n- 价跌量增:恐慌性抛售,可能加速下跌\n- 价跌量缩:下跌动能减弱,可能反弹\n- 放量突破:趋势确认信号",
                "applicability": "趋势",
                "formula": "VOL = 当日成交股数\nMAVOL(N) = 成交量的N日MA"
            },
            "WR": {
                "description": "WR(威廉指标)是衡量超买超卖程度的震荡指标。\n\n计算方法:\n- WR(N) = (N日最高价 - 收盘价) / (N日最高价 - N日最低价) × (-100)\n\n信号解读:\n- WR > -20:超买区域,可能回调\n- WR < -80:超卖区域,可能反弹\n- WR背离:价格新高但WR未新高,顶背离(看空)",
                "applicability": "震荡",
                "formula": "WR(N) = (H(N) - C) / (H(N) - L(N)) × (-100)"
            },
            "CCI": {
                "description": "CCI(商品通道指标)是衡量价格偏离均值程度的指标。\n\n计算方法:\n- TP = (最高价 + 最低价 + 收盘价) / 3\n- MA(TP, N)\n- MD = TP与MA(TP, N)的平均绝对偏差\n- CCI = (TP - MA(TP, N)) / (0.015 × MD)\n\n信号解读:\n- CCI > 100:进入超买区域\n- CCI < -100:进入超卖区域\n- CCI在±100之间:正常波动",
                "applicability": "震荡+趋势",
                "formula": "CCI = (TP - MA(TP, N)) / (0.015 × MD)"
            },
            "OBV": {
                "description": "OBV(能量潮)是基于成交量和价格关系的指标。\n\n计算方法:\n- 如果当日收盘价 > 前一日收盘价,OBV = 前一日OBV + 当日成交量\n- 如果当日收盘价 < 前一日收盘价,OBV = 前一日OBV - 当日成交量\n- 如果当日收盘价 = 前一日收盘价,OBV = 前一日OBV\n\n信号解读:\n- OBV上升,价格上升:量价配合,趋势延续\n- OBV上升,价格下降:底背离,可能反弹\n- OBV下降,价格上升:顶背离,可能回调\n- OBV下降,价格下降:量价配合,下跌延续",
                "applicability": "趋势",
                "formula": "OBV = OBV_prev ± Volume"
            },
            "DMI": {
                "description": "DMI(方向指标)是衡量趋势强度和方向的指标。\n\n计算方法:\n- +DI:上升方向指标\n- -DI:下降方向指标\n- ADX:平均方向指数\n- ADXR:ADX的移动平均\n\n信号解读:\n- +DI > -DI:上升趋势\n- -DI > +DI:下降趋势\n- ADX > 25:趋势较强\n- ADX < 20:趋势较弱或震荡",
                "applicability": "趋势",
                "formula": "+DI(N) = +DM / TR × 100\n-DI(N) = -DM / TR × 100\nADX = 100 × |+DI - -DI| / (+DI + -DI)"
            }
        }
        dialog = self._safe_toplevel(self.root)
        dialog.title("技术指标分析")
        dialog.geometry("900x600")
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # 指标选择下拉框(放在上方)
        indicator_var = tk.StringVar(value=initial_indicator)
        indicator_combo = ttk.Combobox(main_frame, textvariable=indicator_var,
                                      values=["MACD", "RSI", "KDJ", "BOLL", "MA", "VOL", "WR", "CCI", "OBV", "DMI"],
                                      state="readonly", width=10)
        indicator_combo.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        # 左侧:技术指标说明
        left_frame = ttk.Frame(main_frame, width=450)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        # 标题
        title_label = ttk.Label(left_frame, text=f"{initial_indicator}指标",
                               font=("Microsoft YaHei", 14, "bold"))
        title_label.pack(pady=(0, 10))
        # 适用性标签
        info = indicator_info.get(initial_indicator, {})
        applicability = info.get('applicability', '未知')
        if applicability == '趋势':
            color = 'green'
        elif applicability == '震荡':
            color = 'orange'
        else:
            color = 'blue'
        app_label = ttk.Label(left_frame, text=f"适用行情:{applicability}",
                              font=("Microsoft YaHei", 12, "bold"), foreground=color)
        app_label.pack(pady=(0, 10))
        # 计算公式
        formula_frame = ttk.LabelFrame(left_frame, text="计算公式", padding=10)
        formula_frame.pack(fill=tk.X, pady=(0, 10))
        formula_text = tk.Text(formula_frame, height=4, font=("Consolas", 11), wrap=tk.WORD)
        formula_text.pack(fill=tk.X)
        formula_text.insert(tk.END, info.get('formula', '暂无'))
        formula_text.config(state=tk.DISABLED)
        # 详细说明
        desc_frame = ttk.LabelFrame(left_frame, text="指标说明", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True)
        desc_text = tk.Text(desc_frame, font=("Microsoft YaHei", 10), wrap=tk.WORD)
        desc_text.pack(fill=tk.BOTH, expand=True)
        desc_text.insert(tk.END, info.get('description', '暂无'))
        desc_text.config(state=tk.DISABLED)
        # 右侧:股票分析
        right_frame = ttk.Frame(main_frame, width=450)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        # 标题
        ttk.Label(right_frame, text="股票分析", font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 10))
        # 股票选择
        stock_frame = ttk.Frame(right_frame)
        stock_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(stock_frame, text="选择股票:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT)
        stock_var = tk.StringVar()
        stock_combo = ttk.Combobox(stock_frame, textvariable=stock_var, width=20, state="normal")
        stock_combo.pack(side=tk.LEFT, padx=(5, 5))
        # 加载持仓股和龙头股
        stock_items = []
        try:
            all_holdings = self._get_all_holding_stocks()
            seen_codes = set()
            for stock_name, stock_code, group_idx, pos_idx in all_holdings:
                if stock_code not in seen_codes:
                    seen_codes.add(stock_code)
                    stock_items.append(f"{stock_name}({stock_code})")
        except:
            pass
        if not stock_items:
            stock_items = ["贵州茅台(600519)", "东方财富(300059)", "宁德时代(300750)"]
        stock_combo['values'] = stock_items
        if stock_items:
            stock_var.set(stock_items[0])
        # 分析按钮
        result_text = tk.Text(right_frame, font=("Microsoft YaHei", 10), wrap=tk.WORD)
        def update_indicator_info(event=None):
            """更新指标说明"""
            indicator_name = indicator_var.get()
            info = indicator_info.get(indicator_name, {})
            title_label.config(text=f"{indicator_name}指标")
            applicability = info.get('applicability', '未知')
            if applicability == '趋势':
                color = 'green'
            elif applicability == '震荡':
                color = 'orange'
            else:
                color = 'blue'
            app_label.config(text=f"适用行情:{applicability}", foreground=color)
            formula_text.config(state=tk.NORMAL)
            formula_text.delete("1.0", tk.END)
            formula_text.insert(tk.END, info.get('formula', '暂无'))
            formula_text.config(state=tk.DISABLED)
            desc_text.config(state=tk.NORMAL)
            desc_text.delete("1.0", tk.END)
            desc_text.insert(tk.END, info.get('description', '暂无'))
            desc_text.config(state=tk.DISABLED)
        indicator_combo.bind("<<ComboboxSelected>>", update_indicator_info)
        def analyze_stock():
            """分析选中的股票"""
            stock_text = stock_var.get()
            match = re.match(r".*?(\d{6})", stock_text)
            if not match:
                messagebox.showwarning("警告", "请选择有效的股票", parent=dialog)
                return
            stock_code = match.group(1)
            stock_name = stock_text.split('(')[0]
            indicator_name = indicator_var.get()
            # 清空分析结果
            result_text.config(state=tk.NORMAL)
            result_text.delete("1.0", tk.END)
            # 显示加载中
            result_text.insert(tk.END, "正在分析中...\n")
            result_text.update()
            # 使用tushare获取数据并分析
            try:
                result = self._analyze_stock_with_indicator(stock_code, stock_name, indicator_name)
                if not result.get('success'):
                    result_text.insert(tk.END, f"分析失败:{result.get('message', '')}\n")
                    result_text.config(state=tk.DISABLED)
                    return
                # 显示分析结果
                result_text.insert(tk.END, f"\n{'='*50}\n")
                result_text.insert(tk.END, f"股票:{stock_name}({stock_code})\n")
                result_text.insert(tk.END, f"指标:{indicator_name}\n")
                result_text.insert(tk.END, f"{'='*50}\n\n")
                # 指标数值
                result_text.insert(tk.END, "【指标数值】\n")
                for key, value in result.get('indicator_values', {}).items():
                    result_text.insert(tk.END, f"  {key}: {value}\n")
                # 信号解读
                result_text.insert(tk.END, "\n【信号解读】\n")
                for signal in result.get('signals', []):
                    if signal.get('type') == 'buy':
                        result_text.insert(tk.END, f"  ✅ {signal['description']}\n")
                    elif signal.get('type') == 'sell':
                        result_text.insert(tk.END, f"  ❌ {signal['description']}\n")
                    else:
                        result_text.insert(tk.END, f"  ⚠️ {signal['description']}\n")
                # 综合建议
                result_text.insert(tk.END, "\n【综合建议】\n")
                result_text.insert(tk.END, result.get('suggestion', '暂无建议') + "\n")
            except Exception as e:
                result_text.insert(tk.END, f"分析出错:{e!s}\n")
            result_text.config(state=tk.DISABLED)
        ttk.Button(stock_frame, text="分析", command=analyze_stock, width=8).pack(side=tk.LEFT)
        # 分析结果
        result_frame = ttk.LabelFrame(right_frame, text="分析结果", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text.pack(fill=tk.BOTH, expand=True)
        result_text.insert(tk.END, "请选择股票并点击分析按钮")
        result_text.config(state=tk.DISABLED)

    def _analyze_stock_with_indicator(self, stock_code, stock_name, indicator_name):
        """使用技术指标分析股票"""
        try:
            # 获取K线数据
            kline_data = self._get_daily_kline_data_tushare(stock_code)
            if kline_data is None or kline_data['data'] is None or len(kline_data['data']) < 30:
                return {'success': False, 'message': '获取K线数据失败或数据不足'}
            data = kline_data['data']
            close = data['收盘'].values
            high = data['最高'].values
            low = data['最低'].values
            volume = data['成交量'].values
            result = {'success': True, 'indicator_values': {}, 'signals': [], 'suggestion': ''}
            if indicator_name == 'MACD':
                # 计算MACD
                ema12 = self._calculate_ema(close, 12)
                ema26 = self._calculate_ema(close, 26)
                dif = ema12 - ema26
                dea = self._calculate_ema(dif, 9)
                macd = (dif - dea) * 2
                result['indicator_values'] = {
                    'DIF': f"{dif[-1]:.4f}",
                    'DEA': f"{dea[-1]:.4f}",
                    'MACD柱': f"{macd[-1]:.4f}",
                    'DIF走势': '上升' if dif[-1] > dif[-2] else '下降',
                    'DEA走势': '上升' if dea[-1] > dea[-2] else '下降'
                }
                # 信号判断
                if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'MACD金叉,买入信号'})
                elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'MACD死叉,卖出信号'})
                if macd[-1] > 0 and macd[-2] <= 0:
                    result['signals'].append({'type': 'buy', 'description': 'MACD柱由绿转红,趋势转强'})
                elif macd[-1] < 0 and macd[-2] >= 0:
                    result['signals'].append({'type': 'sell', 'description': 'MACD柱由红转绿,趋势转弱'})
                if dif[-1] > 0 and dea[-1] > 0:
                    result['signals'].append({'type': 'neutral', 'description': 'MACD处于正值区域,多头趋势'})
                elif dif[-1] < 0 and dea[-1] < 0:
                    result['signals'].append({'type': 'neutral', 'description': 'MACD处于负值区域,空头趋势'})
                # 综合建议
                if dif[-1] > dea[-1] and macd[-1] > 0:
                    result['suggestion'] = 'MACD多头排列,建议持有或加仓'
                elif dif[-1] < dea[-1] and macd[-1] < 0:
                    result['suggestion'] = 'MACD空头排列,建议减仓或观望'
                else:
                    result['suggestion'] = 'MACD信号不明确,建议结合其他指标分析'
            elif indicator_name == 'RSI':
                # 计算RSI(6)和RSI(12)
                rsi6 = self._calculate_rsi(close, 6)
                rsi12 = self._calculate_rsi(close, 12)
                result['indicator_values'] = {
                    'RSI(6)': f"{rsi6[-1]:.2f}",
                    'RSI(12)': f"{rsi12[-1]:.2f}",
                    'RSI(6)走势': '上升' if rsi6[-1] > rsi6[-2] else '下降',
                    'RSI(12)走势': '上升' if rsi12[-1] > rsi12[-2] else '下降'
                }
                # 信号判断
                if rsi6[-1] < 30:
                    result['signals'].append({'type': 'buy', 'description': 'RSI(6) < 30,超卖区域,可能反弹'})
                if rsi6[-1] > 70:
                    result['signals'].append({'type': 'sell', 'description': 'RSI(6) > 70,超买区域,可能回调'})
                if rsi6[-1] > rsi12[-1] and rsi6[-2] <= rsi12[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'RSI金叉,买入信号'})
                elif rsi6[-1] < rsi12[-1] and rsi6[-2] >= rsi12[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'RSI死叉,卖出信号'})
                # 综合建议
                if rsi6[-1] < 30:
                    result['suggestion'] = 'RSI处于超卖区域,建议关注反弹机会'
                elif rsi6[-1] > 70:
                    result['suggestion'] = 'RSI处于超买区域,建议减仓或观望'
                else:
                    result['suggestion'] = 'RSI处于正常区域,建议结合其他指标分析'
            elif indicator_name == 'KDJ':
                # 计算KDJ(9,3,3)
                kdj = self._calculate_kdj(high, low, close, 9, 3, 3)
                result['indicator_values'] = {
                    'K值': f"{kdj['k'][-1]:.2f}",
                    'D值': f"{kdj['d'][-1]:.2f}",
                    'J值': f"{kdj['j'][-1]:.2f}",
                    'K走势': '上升' if kdj['k'][-1] > kdj['k'][-2] else '下降',
                    'D走势': '上升' if kdj['d'][-1] > kdj['d'][-2] else '下降'
                }
                # 信号判断
                if kdj['k'][-1] > kdj['d'][-1] and kdj['k'][-2] <= kdj['d'][-2]:
                    result['signals'].append({'type': 'buy', 'description': 'KDJ金叉,买入信号'})
                elif kdj['k'][-1] < kdj['d'][-1] and kdj['k'][-2] >= kdj['d'][-2]:
                    result['signals'].append({'type': 'sell', 'description': 'KDJ死叉,卖出信号'})
                if kdj['j'][-1] > 100:
                    result['signals'].append({'type': 'sell', 'description': 'J值 > 100,超买区域'})
                elif kdj['j'][-1] < 0:
                    result['signals'].append({'type': 'buy', 'description': 'J值 < 0,超卖区域'})
                # 综合建议
                if kdj['k'][-1] > kdj['d'][-1] and kdj['j'][-1] > 0:
                    result['suggestion'] = 'KDJ多头排列,建议持有或加仓'
                elif kdj['k'][-1] < kdj['d'][-1] and kdj['j'][-1] < 100:
                    result['suggestion'] = 'KDJ空头排列,建议减仓或观望'
                else:
                    result['suggestion'] = 'KDJ信号不明确,建议结合其他指标分析'
            elif indicator_name == 'BOLL':
                # 计算布林带(20,2)
                ma20 = self._calculate_ma(close, 20)
                std = np.std(close[-20:])
                upper = ma20[-1] + 2 * std
                lower = ma20[-1] - 2 * std
                result['indicator_values'] = {
                    '中轨(MA20)': f"{ma20[-1]:.2f}",
                    '上轨': f"{upper:.2f}",
                    '下轨': f"{lower:.2f}",
                    '当前价格': f"{close[-1]:.2f}",
                    '通道宽度': f"{upper - lower:.2f}",
                    '价格偏离度': f"{((close[-1] - ma20[-1]) / (upper - lower)) * 100:.2f}%"
                }
                # 信号判断
                if close[-1] >= upper:
                    result['signals'].append({'type': 'sell', 'description': '价格触及上轨,可能回调'})
                elif close[-1] <= lower:
                    result['signals'].append({'type': 'buy', 'description': '价格触及下轨,可能反弹'})
                # 通道宽度变化
                prev_std = np.std(close[-21:-1])
                if std < prev_std * 0.8:
                    result['signals'].append({'type': 'neutral', 'description': '布林带收口,行情即将突破'})
                elif std > prev_std * 1.2:
                    result['signals'].append({'type': 'neutral', 'description': '布林带开口,行情加速'})
                # 综合建议
                if close[-1] <= lower:
                    result['suggestion'] = '价格触及布林带下轨,建议关注反弹机会'
                elif close[-1] >= upper:
                    result['suggestion'] = '价格触及布林带上轨,建议减仓或观望'
                else:
                    result['suggestion'] = '价格在布林带内正常波动,建议持有'
            elif indicator_name == 'MA':
                # 计算MA5, MA10, MA20, MA60
                ma5 = self._calculate_ma(close, 5)
                ma10 = self._calculate_ma(close, 10)
                ma20 = self._calculate_ma(close, 20)
                ma60 = self._calculate_ma(close, 60)
                result['indicator_values'] = {
                    'MA5': f"{ma5[-1]:.2f}",
                    'MA10': f"{ma10[-1]:.2f}",
                    'MA20': f"{ma20[-1]:.2f}",
                    'MA60': f"{ma60[-1]:.2f}",
                    '当前价格': f"{close[-1]:.2f}"
                }
                # 判断均线排列
                if ma5[-1] > ma10[-1] > ma20[-1] > ma60[-1]:
                    result['signals'].append({'type': 'buy', 'description': '均线多头排列,上升趋势'})
                elif ma5[-1] < ma10[-1] < ma20[-1] < ma60[-1]:
                    result['signals'].append({'type': 'sell', 'description': '均线空头排列,下降趋势'})
                else:
                    result['signals'].append({'type': 'neutral', 'description': '均线纠结,震荡行情'})
                # 价格与均线关系
                if close[-1] > ma5[-1]:
                    result['signals'].append({'type': 'buy', 'description': '价格在MA5之上,短期强势'})
                elif close[-1] < ma20[-1]:
                    result['signals'].append({'type': 'sell', 'description': '价格在MA20之下,短期弱势'})
                # 综合建议
                if ma5[-1] > ma10[-1] > ma20[-1]:
                    result['suggestion'] = '均线多头排列,建议持有或加仓'
                elif ma5[-1] < ma10[-1] < ma20[-1]:
                    result['suggestion'] = '均线空头排列,建议减仓或观望'
                else:
                    result['suggestion'] = '均线纠结,建议观望或短线操作'
            elif indicator_name == 'VOL':
                # 计算成交量和均量线
                ma_vol5 = self._calculate_ma(volume, 5)
                ma_vol10 = self._calculate_ma(volume, 10)
                result['indicator_values'] = {
                    '今日成交量': f"{volume[-1]:,.0f}",
                    '5日均量': f"{ma_vol5[-1]:,.0f}",
                    '10日均量': f"{ma_vol10[-1]:,.0f}",
                    '量比': f"{volume[-1] / ma_vol5[-1]:.2f}" if ma_vol5[-1] > 0 else 'N/A',
                    '成交量走势': '放量' if volume[-1] > ma_vol5[-1] * 1.5 else '缩量' if volume[-1] < ma_vol5[-1] * 0.5 else '正常'
                }
                # 判断量价关系
                if close[-1] > close[-2] and volume[-1] > ma_vol5[-1]:
                    result['signals'].append({'type': 'buy', 'description': '价涨量增,趋势健康'})
                elif close[-1] > close[-2] and volume[-1] < ma_vol5[-1]:
                    result['signals'].append({'type': 'sell', 'description': '价涨量缩,上涨乏力'})
                elif close[-1] < close[-2] and volume[-1] > ma_vol5[-1]:
                    result['signals'].append({'type': 'sell', 'description': '价跌量增,恐慌抛售'})
                elif close[-1] < close[-2] and volume[-1] < ma_vol5[-1]:
                    result['signals'].append({'type': 'buy', 'description': '价跌量缩,下跌动能减弱'})
                # 综合建议
                if close[-1] > close[-2] and volume[-1] > ma_vol5[-1]:
                    result['suggestion'] = '价涨量增,趋势健康,建议持有'
                elif close[-1] > close[-2] and volume[-1] < ma_vol5[-1]:
                    result['suggestion'] = '价涨量缩,上涨乏力,建议谨慎'
                else:
                    result['suggestion'] = '成交量信号不明确,建议结合其他指标分析'
            elif indicator_name == 'WR':
                # 计算WR(14)
                wr14 = self._calculate_wr(high, low, close, 14)
                result['indicator_values'] = {
                    'WR(14)': f"{wr14[-1]:.2f}",
                    'WR走势': '上升' if wr14[-1] > wr14[-2] else '下降'
                }
                # 信号判断
                if wr14[-1] > -20:
                    result['signals'].append({'type': 'sell', 'description': 'WR > -20,超买区域,可能回调'})
                elif wr14[-1] < -80:
                    result['signals'].append({'type': 'buy', 'description': 'WR < -80,超卖区域,可能反弹'})
                # 综合建议
                if wr14[-1] < -80:
                    result['suggestion'] = 'WR处于超卖区域,建议关注反弹机会'
                elif wr14[-1] > -20:
                    result['suggestion'] = 'WR处于超买区域,建议减仓或观望'
                else:
                    result['suggestion'] = 'WR处于正常区域,建议结合其他指标分析'
            elif indicator_name == 'CCI':
                # 计算CCI(14)
                cci = self._calculate_cci(high, low, close, 14)
                result['indicator_values'] = {
                    'CCI(14)': f"{cci[-1]:.2f}",
                    'CCI走势': '上升' if cci[-1] > cci[-2] else '下降'
                }
                # 信号判断
                if cci[-1] > 100:
                    result['signals'].append({'type': 'sell', 'description': 'CCI > 100,超买区域'})
                elif cci[-1] < -100:
                    result['signals'].append({'type': 'buy', 'description': 'CCI < -100,超卖区域'})
                # 综合建议
                if cci[-1] < -100:
                    result['suggestion'] = 'CCI处于超卖区域,建议关注反弹机会'
                elif cci[-1] > 100:
                    result['suggestion'] = 'CCI处于超买区域,建议减仓或观望'
                else:
                    result['suggestion'] = 'CCI处于正常区域,建议结合其他指标分析'
            elif indicator_name == 'OBV':
                # 计算OBV
                obv = self._calculate_obv(close, volume)
                result['indicator_values'] = {
                    'OBV': f"{obv[-1]:,.0f}",
                    'OBV走势': '上升' if obv[-1] > obv[-2] else '下降',
                    '价格走势': '上涨' if close[-1] > close[-2] else '下跌'
                }
                # 判断量价关系
                if obv[-1] > obv[-2] and close[-1] > close[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'OBV上升,价格上涨,量价配合'})
                elif obv[-1] > obv[-2] and close[-1] < close[-2]:
                    result['signals'].append({'type': 'buy', 'description': 'OBV上升,价格下跌,底背离'})
                elif obv[-1] < obv[-2] and close[-1] > close[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'OBV下降,价格上涨,顶背离'})
                elif obv[-1] < obv[-2] and close[-1] < close[-2]:
                    result['signals'].append({'type': 'sell', 'description': 'OBV下降,价格下跌,量价配合'})
                # 综合建议
                if obv[-1] > obv[-2] and close[-1] > close[-2]:
                    result['suggestion'] = 'OBV与价格同步上升,量价配合,建议持有'
                elif obv[-1] > obv[-2] and close[-1] < close[-2]:
                    result['suggestion'] = 'OBV上升但价格下跌,底背离,建议关注'
                elif obv[-1] < obv[-2] and close[-1] > close[-2]:
                    result['suggestion'] = 'OBV下降但价格上涨,顶背离,建议谨慎'
                else:
                    result['suggestion'] = 'OBV信号不明确,建议结合其他指标分析'
            elif indicator_name == 'DMI':
                # 计算DMI(14)
                dmi = self._calculate_dmi(high, low, close, 14)
                result['indicator_values'] = {
                    '+DI': f"{dmi['plus_di'][-1]:.2f}",
                    '-DI': f"{dmi['minus_di'][-1]:.2f}",
                    'ADX': f"{dmi['adx'][-1]:.2f}"
                }
                # 信号判断
                if dmi['plus_di'][-1] > dmi['minus_di'][-1]:
                    result['signals'].append({'type': 'buy', 'description': '+DI > -DI,上升趋势'})
                elif dmi['minus_di'][-1] > dmi['plus_di'][-1]:
                    result['signals'].append({'type': 'sell', 'description': '-DI > +DI,下降趋势'})
                if dmi['adx'][-1] > 25:
                    result['signals'].append({'type': 'neutral', 'description': 'ADX > 25,趋势较强'})
                elif dmi['adx'][-1] < 20:
                    result['signals'].append({'type': 'neutral', 'description': 'ADX < 20,趋势较弱或震荡'})
                # 综合建议
                if dmi['plus_di'][-1] > dmi['minus_di'][-1] and dmi['adx'][-1] > 25:
                    result['suggestion'] = '上升趋势明确且强度较高,建议持有或加仓'
                elif dmi['minus_di'][-1] > dmi['plus_di'][-1] and dmi['adx'][-1] > 25:
                    result['suggestion'] = '下降趋势明确且强度较高,建议减仓或观望'
                else:
                    result['suggestion'] = '趋势不明确或较弱,建议观望或短线操作'
            return result
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def _calculate_rsi(self, data, period):
        """计算RSI"""
        if len(data) < period + 1:
            return np.zeros(len(data))
        delta = np.diff(data)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.zeros(len(data))
        avg_loss = np.zeros(len(data))
        avg_gain[period] = np.mean(gain[:period])
        avg_loss[period] = np.mean(loss[:period])
        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss[i-1]) / period
        rsi = np.zeros(len(data))
        rsi[period:] = 100 - (100 / (1 + avg_gain[period:] / (avg_loss[period:] + 1e-10)))
        return rsi

    def _calculate_kdj(self, high, low, close, n, m1, m2):
        """计算KDJ"""
        if len(close) < n:
            return {'k': np.zeros(len(close)), 'd': np.zeros(len(close)), 'j': np.zeros(len(close))}
        # 计算RSV
        rsv = np.zeros(len(close))
        for i in range(n-1, len(close)):
            h_n = np.max(high[i-n+1:i+1])
            l_n = np.min(low[i-n+1:i+1])
            if h_n == l_n:
                rsv[i] = 50
            else:
                rsv[i] = (close[i] - l_n) / (h_n - l_n) * 100
        # 计算K和D
        k = np.zeros(len(close))
        d = np.zeros(len(close))
        k[n-1] = 50
        d[n-1] = 50
        multiplier = 1 / m1
        for i in range(n, len(close)):
            k[i] = rsv[i] * multiplier + k[i-1] * (1 - multiplier)
            d[i] = k[i] * multiplier + d[i-1] * (1 - multiplier)
        # 计算J
        j = 3 * k - 2 * d
        return {'k': k, 'd': d, 'j': j}

    def _williams_r_n(self, highs, lows, closes, n):
        """Williams %R,区间为约 [-100, 0];n=2 时极灵敏。"""
        h = np.asarray(highs, dtype=float)
        l = np.asarray(lows, dtype=float)
        c = np.asarray(closes, dtype=float)
        out = np.full(len(c), np.nan)
        nn = max(2, int(n))
        for i in range(nn - 1, len(c)):
            hh = float(np.max(h[i - nn + 1 : i + 1]))
            ll = float(np.min(l[i - nn + 1 : i + 1]))
            if hh - ll < 1e-12:
                out[i] = -50.0
            else:
                out[i] = -100.0 * (hh - c[i]) / (hh - ll)
        return out

    def _kdj_series(self, highs, lows, closes, n=9):
        """KDJ(9,3,3 型平滑:K、D 递推,J=3K-2D)。"""
        highs = np.asarray(highs, dtype=float)
        lows = np.asarray(lows, dtype=float)
        closes = np.asarray(closes, dtype=float)
        length = len(closes)
        rsv = np.full(length, np.nan)
        for i in range(n - 1, length):
            hn = float(np.max(highs[i - n + 1 : i + 1]))
            ln = float(np.min(lows[i - n + 1 : i + 1]))
            if hn <= ln + 1e-12:
                rsv[i] = 50.0
            else:
                rsv[i] = 100.0 * (closes[i] - ln) / (hn - ln)
        k = np.full(length, np.nan)
        d = np.full(length, np.nan)
        j = np.full(length, np.nan)
        pk, pd = 50.0, 50.0
        for i in range(n - 1, length):
            if np.isnan(rsv[i]):
                continue
            pk = (2.0 * pk + rsv[i]) / 3.0
            pd = (2.0 * pd + pk) / 3.0
            k[i] = pk
            d[i] = pd
            j[i] = 3.0 * pk - 2.0 * pd
        return k, d, j

    def _boll_np(self, closes, window=20, num_std=2.0):
        c = pd.Series(np.asarray(closes, dtype=float))
        mid = c.rolling(int(window), min_periods=1).mean()
        std = c.rolling(int(window), min_periods=1).std(ddof=0)
        upper = mid + float(num_std) * std
        lower = mid - float(num_std) * std
        return upper.values, mid.values, lower.values

    def _mean_reversion_scan_enhanced(self, stock_code, kline_data=None):
        """T2-均值回归: 布林带支撑/阻力提醒(增强版)"""
        result = {"signal": "无", "boll_upper": 0, "boll_lower": 0, "boll_mid": 0, "position": ""}
        try:
            if kline_data and kline_data.get('data') is not None:
                df = kline_data['data']
                closes = df['收盘'].values
                n = len(closes)
                if n < 20:
                    return result
                window = 20
                mid = float(np.mean(closes[-window:]))
                std = float(np.std(closes[-window:]))
                upper = mid + 2 * std
                lower = mid - 2 * std
                close = float(closes[-1])
                result.update({"boll_upper": upper, "boll_lower": lower, "boll_mid": mid})
                dj = self._duanji_score(stock_code, kline_data)
                dj_total = dj.get("total", 0)
                if close <= lower:
                    result.update({"signal": "🟢支撑", "position": "触及布林下轨,超卖反弹机会"})
                elif close >= upper:
                    result.update({"signal": "🔴阻力", "position": "触及布林上轨,注意回调风险"})
                elif close > mid and closes[-2] <= mid:
                    result.update({"signal": "🚀突破", "position": "突破布林中轨,趋势转强"})
                elif close < mid * 0.98:
                    result.update({"signal": "⚠️破位", "position": "跌破布林中轨,趋势转弱"})
                if dj_total >= 65:
                    result["position"] = f"【优质股·段基{dj_total}分】" + result["position"]
        except Exception:
            pass
        return result

    def _calc_ma(prices, period):
        """简单移动平均"""
        import numpy as np
        arr = np.array(prices, dtype=float)
        if len(arr) < period:
            return np.full_like(arr, np.nan)
        ma = np.full_like(arr, np.nan)
        cumsum = np.cumsum(arr)
        ma[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0], cumsum[:-period]])) / period
        return ma

    def _calc_rsi(prices, period=14):
        """RSI(Wilder 标准)"""
        import numpy as np
        arr = np.array(prices, dtype=float)
        n = len(arr)
        rsi = np.full(n, np.nan)
        if n < period + 1:
            return rsi
        deltas = np.diff(arr)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        # 初始平均
        avg_gain = gains[:period].mean()
        avg_loss = losses[:period].mean()
        if avg_loss == 0:
            rsi[period] = 100.0
        else:
            rsi[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        # 平滑
        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rsi[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
        return rsi

    def _calc_bollinger(prices, period=20, num_std=2):
        """布林带 → (mid, upper, lower)"""
        import numpy as np
        arr = np.array(prices, dtype=float)
        mid = np.full(len(arr), np.nan)
        upper = np.full(len(arr), np.nan)
        lower = np.full(len(arr), np.nan)
        if len(arr) < period:
            return mid, upper, lower
        for i in range(period - 1, len(arr)):
            seg = arr[i - period + 1:i + 1]
            m = seg.mean()
            s = seg.std(ddof=0)
            mid[i] = m
            upper[i] = m + num_std * s
            lower[i] = m - num_std * s
        return mid, upper, lower

    def _calc_macd_full(prices, fast=12, slow=26, signal=9):
        """计算完整 MACD 数组(用于背离检测)"""
        import numpy as np
        try:
            arr = np.array(prices, dtype=float)
            if len(arr) < slow + signal:
                return np.zeros(len(arr)), np.zeros(len(arr)), np.zeros(len(arr))
            def _ema(data, period):
                alpha = 2.0 / (period + 1)
                out = np.zeros_like(data)
                out[0] = data[0]
                for i in range(1, len(data)):
                    out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
                return out
            ema_fast = _ema(arr, fast)
            ema_slow = _ema(arr, slow)
            dif = ema_fast - ema_slow
            dea = _ema(dif, signal)
            macd_hist = (dif - dea) * 2  # 同花顺标准 ×2
            return dif, dea, macd_hist
        except Exception:
            import numpy as np
            return np.zeros(len(prices)), np.zeros(len(prices)), np.zeros(len(prices))


__all__ = ["IndicatorMixin"]

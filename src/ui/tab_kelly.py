"""Auto-extracted KellyMixin"""
import os, sys, json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

from datetime import datetime, timedelta
import time
import traceback

class KellyMixin:
    """KellyMixin"""

    def show_kelly_calculator(self):
        """打开凯利公式计算器"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            win = self._toplevel(self.root)
            win.title("凯利公式计算器")
            win.geometry("900x650")
            win.resizable(True, True)
            # 图表字体已在文件开头全局设置,这里不需要重复设置
            main_frame = ttk.Frame(win, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            # 变量
            odds_var = tk.StringVar(value="1.0")
            prob_var = tk.StringVar(value="0.5")
            kelly_result_var = tk.StringVar(value="0.00%")
            suggestion_var = tk.StringVar(value="-")
            risk_var = tk.StringVar(value="-")
            stock_var = tk.StringVar()
            time_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
            kelly_state = {'kelly': None, 'odds': None, 'prob': None}
            # 输入区域
            input_frame = ttk.LabelFrame(main_frame, text="输入参数", padding=15)
            input_frame.pack(fill=tk.X, pady=(0, 15))
            ttk.Label(input_frame, text="盈亏比 (b):", width=15).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
            ttk.Entry(input_frame, textvariable=odds_var, width=20).grid(row=0, column=1, padx=10, pady=10)
            ttk.Label(input_frame, text="(例如盈利2元亏损1元则输入2.0)").grid(row=0, column=2, padx=10, pady=10, sticky=tk.W)
            ttk.Label(input_frame, text="胜率 (p):", width=15).grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
            ttk.Entry(input_frame, textvariable=prob_var, width=20).grid(row=1, column=1, padx=10, pady=10)
            ttk.Label(input_frame, text="(例如50%胜率输入0.5)").grid(row=1, column=2, padx=10, pady=10, sticky=tk.W)
            # 标的信息
            meta_frame = ttk.LabelFrame(main_frame, text="标的信息与说明", padding=15)
            meta_frame.pack(fill=tk.X, pady=(0, 15))
            ttk.Label(meta_frame, text="股票名称:", width=15).grid(row=0, column=0, padx=10, pady=6, sticky=tk.W)
            ttk.Entry(meta_frame, textvariable=stock_var, width=25).grid(row=0, column=1, padx=10, pady=6, sticky=tk.W)
            ttk.Label(meta_frame, text="分析时间:", width=15).grid(row=0, column=2, padx=10, pady=6, sticky=tk.W)
            time_entry = ttk.Entry(meta_frame, textvariable=time_var, width=20)
            time_entry.grid(row=0, column=3, padx=10, pady=6, sticky=tk.W)
            def reset_time_to_now():
                time_var.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
            ttk.Button(meta_frame, text="设为当前时间", command=reset_time_to_now).grid(row=0, column=4, padx=10, pady=6)
            ttk.Label(meta_frame, text="补充说明:").grid(row=1, column=0, padx=10, pady=(8, 4), sticky=tk.NW)
            notes_text = scrolledtext.ScrolledText(meta_frame, height=4, wrap=tk.WORD, font=("TkDefaultFont", 12))
            notes_text.grid(row=1, column=1, columnspan=4, padx=10, pady=(4, 4), sticky=tk.EW)
            meta_frame.columnconfigure(1, weight=1)
            meta_frame.columnconfigure(3, weight=1)
            # 结果区域
            result_frame = ttk.LabelFrame(main_frame, text="计算结果", padding=15)
            result_frame.pack(fill=tk.X, pady=(0, 15))
            ttk.Label(result_frame, text="凯利百分比 (K):", font=("SimHei", 12)).grid(row=0, column=0, padx=20, pady=10, sticky=tk.W)
            ttk.Label(result_frame, textvariable=kelly_result_var, font=("SimHei", 16, "bold"), foreground="#0066cc").grid(row=0, column=1, padx=20, pady=10, sticky=tk.W)
            ttk.Label(result_frame, text="建议仓位:", font=("SimHei", 12)).grid(row=1, column=0, padx=20, pady=10, sticky=tk.W)
            ttk.Label(result_frame, textvariable=suggestion_var, font=("SimHei", 12)).grid(row=1, column=1, padx=20, pady=10, sticky=tk.W)
            ttk.Label(result_frame, text="风险评估:", font=("SimHei", 12)).grid(row=2, column=0, padx=20, pady=10, sticky=tk.W)
            ttk.Label(result_frame, textvariable=risk_var, font=("SimHei", 12)).grid(row=2, column=1, padx=20, pady=10, sticky=tk.W)
            save_btn = ttk.Button(result_frame, text="保存到数据库", command=lambda: save_kelly_record_action())
            save_btn.grid(row=0, column=2, rowspan=3, padx=20, pady=10)
            # 图表
            chart_frame = ttk.LabelFrame(main_frame, text="凯利比例分析图表", padding=15)
            chart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3), dpi=100)
            fig.tight_layout(pad=3.0)
            canvas = FigureCanvasTkAgg(fig, master=chart_frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            def update_suggestion(kelly_value):
                if kelly_value <= 0:
                    suggestion_var.set("不建议投注 (期望值为负)")
                elif kelly_value <= 0.05:
                    suggestion_var.set(f"保守投注: {kelly_value/2*100:.1f}% 仓位")
                elif kelly_value <= 0.10:
                    suggestion_var.set(f"标准投注: {kelly_value*100:.1f}% 仓位")
                else:
                    suggestion_var.set(f"建议使用部分凯利: {(kelly_value/2)*100:.1f}% (半凯利) 或 {(kelly_value/4)*100:.1f}% (1/4凯利)")
            def update_risk(kelly_value):
                if kelly_value <= 0:
                    risk_var.set("风险: 负期望值,避免投注")
                elif kelly_value <= 0.05:
                    risk_var.set("风险: 低风险,适合保守投资者")
                elif kelly_value <= 0.10:
                    risk_var.set("风险: 中等风险,适合平衡型投资者")
                elif kelly_value <= 0.20:
                    risk_var.set("风险: 中高风险,适合进取型投资者")
                else:
                    risk_var.set("风险: 高风险,建议降低投注比例")
            def update_chart(odds_value, prob_value):
                ax1.clear()
                ax2.clear()
                win_probs = np.linspace(0.01, 0.99, 100)
                kelly_values = win_probs - (1 - win_probs) / odds_value
                ax1.plot(win_probs * 100, kelly_values * 100, 'b-', linewidth=2)
                ax1.axhline(y=0, color='r', linestyle='--', alpha=0.7)
                ax1.axvline(x=prob_value * 100, color='g', linestyle='--', alpha=0.7)
                current_kelly = prob_value - (1 - prob_value) / odds_value
                ax1.plot(prob_value * 100, current_kelly * 100, 'ro', markersize=8)
                ax1.set_title('凯利比例与胜率的关系')
                ax1.set_xlabel('胜率 (%)')
                ax1.set_ylabel('凯利比例 (%)')
                ax1.grid(True, linestyle='--', alpha=0.7)
                ax1.set_xlim(0, 100)
                bet_sizes = np.linspace(0, min(max(current_kelly * 2, 0.5), 1.0), 100)
                growth_rates = []
                for size in bet_sizes:
                    if size <= 0:
                        growth_rates.append(0)
                    else:
                        if size < 1:
                            growth = prob_value * np.log(1 + size * odds_value) + (1 - prob_value) * np.log(1 - size)
                        else:
                            growth = -np.inf
                        growth_rates.append(growth)
                ax2.plot(bet_sizes * 100, growth_rates, 'g-', linewidth=2)
                if current_kelly > 0:
                    max_growth = prob_value * np.log(1 + current_kelly * odds_value) + (1 - prob_value) * np.log(1 - current_kelly)
                    ax2.plot(current_kelly * 100, max_growth, 'ro', markersize=8)
                    half_kelly = current_kelly / 2
                    half_growth = prob_value * np.log(1 + half_kelly * odds_value) + (1 - prob_value) * np.log(1 - half_kelly)
                    ax2.plot(half_kelly * 100, half_growth, 'mo', markersize=6, label='半凯利')
                    quarter_kelly = current_kelly / 4
                    quarter_growth = prob_value * np.log(1 + quarter_kelly * odds_value) + (1 - prob_value) * np.log(1 - quarter_kelly)
                    ax2.plot(quarter_kelly * 100, quarter_growth, 'co', markersize=6, label='1/4凯利')
                ax2.set_title('仓位与长期增长率关系')
                ax2.set_xlabel('投注比例 (%)')
                ax2.set_ylabel('长期增长率')
                ax2.grid(True, linestyle='--', alpha=0.7)
                if current_kelly > 0:
                    ax2.legend()
                fig.tight_layout(pad=3.0)
                canvas.draw()
            def save_kelly_record_action():
                stock_name = stock_var.get().strip()
                if not stock_name:
                    messagebox.showwarning("警告", "请先输入股票名称")
                    return
                if kelly_state['kelly'] is None:
                    messagebox.showwarning("警告", "请先计算凯利比例")
                    return
                calc_time = time_var.get().strip() or datetime.now().strftime("%Y-%m-%d %H:%M")
                notes = notes_text.get("1.0", tk.END).strip()
                success = save_kelly_record_to_db(
                    stock_name=stock_name,
                    calc_time=calc_time,
                    odds=kelly_state['odds'],
                    win_prob=kelly_state['prob'],
                    kelly_ratio=kelly_state['kelly'],
                    suggestion=suggestion_var.get(),
                    notes=notes
                )
                if success:
                    messagebox.showinfo("成功", "凯利计算结果已保存到数据库")
                else:
                    messagebox.showerror("错误", "保存失败,请检查日志")
            def calculate_kelly():
                try:
                    odds_value = float(odds_var.get())
                    prob_value = float(prob_var.get())
                    if odds_value <= 0:
                        messagebox.showerror("输入错误", "盈亏比必须大于0")
                        return
                    if prob_value <= 0 or prob_value >= 1:
                        messagebox.showerror("输入错误", "胜率必须在0到1之间")
                        return
                    kelly_value = prob_value - (1 - prob_value) / odds_value
                    kelly_result_var.set(f"{kelly_value * 100:.2f}%")
                    update_suggestion(kelly_value)
                    update_risk(kelly_value)
                    update_chart(odds_value, prob_value)
                    kelly_state['kelly'] = kelly_value
                    kelly_state['odds'] = odds_value
                    kelly_state['prob'] = prob_value
                except ValueError:
                    messagebox.showerror("输入错误", "请输入有效的数字")
            def reset_fields():
                odds_var.set("1.0")
                prob_var.set("0.5")
                kelly_result_var.set("0.00%")
                suggestion_var.set("-")
                risk_var.set("-")
                kelly_state['kelly'] = None
                kelly_state['odds'] = None
                kelly_state['prob'] = None
                stock_var.set("")
                reset_time_to_now()
                notes_text.delete("1.0", tk.END)
                update_chart(1.0, 0.5)
            ttk.Button(input_frame, text="计算凯利比例", command=calculate_kelly, width=20).grid(row=0, column=3, rowspan=2, padx=20, pady=10)
            ttk.Button(input_frame, text="重置", command=reset_fields, width=15).grid(row=0, column=4, padx=10, pady=10, sticky=tk.N)
            # 初始化图表
            update_chart(1.0, 0.5)
        except Exception as e:
            messagebox.showerror("错误", f"打开凯利公式计算器失败: {e}")


    def _calculate_kelly_params(self, ma_status):
        """根据均线状态计算盈亏比b和胜率p(始终从配置表中读取值)"""
        # 确保ma_status包含所有必要的键
        ma1 = ma_status.get('ma1', False)
        ma5 = ma_status.get('ma5', False)
        ma10 = ma_status.get('ma10', False)
        ma20 = ma_status.get('ma20', False)
        below_ma20 = ma_status.get('below_ma20', False)
        # 如果股价低于20日线,从配置表中读取
        if below_ma20:
            config_key = "below_ma20"
            if config_key in self.kelly_config:
                custom_config = self.kelly_config[config_key]
                b = custom_config.get('b')
                p = custom_config.get('p')
                if b is not None and p is not None:
                    print(f"[凯利参数] 低于20日线,使用配置表: b={b}, p={p}")
                    return b, p
            # 如果配置表中没有,使用默认值 b=1, p=0.5
            print(f"[凯利参数] 配置表中缺少 {config_key},使用默认值: b=1.0, p=0.5")
            return 1.0, 0.5
        # 根据均线状态确定配置键
        config_key = f"{ma1}_{ma5}_{ma10}_{ma20}"
        # 从配置表中读取(优先使用配置表中的值)
        if config_key in self.kelly_config:
            custom_config = self.kelly_config[config_key]
            b = custom_config.get('b')
            p = custom_config.get('p')
            if b is not None and p is not None:
                print(f"[凯利参数] 均线状态 {config_key},使用配置表: b={b}, p={p}")
                return b, p
        # 如果配置表中没有对应配置,使用默认值 b=1, p=0.5
        print(f"[凯利参数] 配置表中缺少 {config_key},使用默认值: b=1.0, p=0.5")
        return 1.0, 0.5


    def _calculate_kelly_ratio(self, b, p):
        """计算凯利公式:f = (bp - q) / b,其中q = 1 - p"""
        try:
            q = 1 - p
            kelly_ratio = (b * p - q) / b
            # 确保结果在0-1之间
            kelly_ratio = max(0.0, min(1.0, kelly_ratio))
            return kelly_ratio
        except Exception as e:
            print(f"计算凯利公式失败: {e}")
            return 0.0


    def _calculate_kelly_position(self, kline_data, stock_name):
        """根据凯利公式计算仓位。
        参考成熟量化系统的参数:
        - 胜率:根据BIAS、均线走向、支撑压力位置综合判断
        - 盈亏比:根据支撑线和压力线的距离计算
        - 使用保守凯利公式,避免过度杠杆
        Returns:
            dict: 包含凯利仓位、胜率、盈亏比、输入参数等详细信息
        """
        result = {
            'success': False,
            'message': '',
            'kelly_fraction': 0.0,
            'kelly_pct': 0.0,
            'conservative_kelly_pct': 0.0,
            'win_probability': 0.0,
            'risk_reward_ratio': 0.0,
            'bias': None,
            'trend_direction': 'neutral',
            'support_price': None,
            'resistance_price': None,
            'current_price': None,
            'stop_loss_price': None,
            'take_profit_price': None,
            'risk_amount': None,
            'reward_amount': None,
            'analysis': [],
            'calculation_steps': []
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
            current_price = float(closes[-1])
            result['current_price'] = current_price
            steps = []
            steps.append(f"【步骤1】获取当前价格:current_price = {current_price:.2f}")
            # 计算BIAS(6日乖离率)
            if len(closes) >= 6:
                ma6 = float(sum(closes[-6:]) / 6)
                bias = ((current_price - ma6) / ma6) * 100
                result['bias'] = round(bias, 2)
                steps.append(f"【步骤2】计算BIAS(6日):MA6 = {ma6:.2f},BIAS = (({current_price:.2f} - {ma6:.2f}) / {ma6:.2f}) × 100% = {bias:.2f}%")
            else:
                steps.append("【步骤2】BIAS计算:数据不足,跳过")
            # 分析均线走向
            trend_direction = 'neutral'
            if 'ma20' in ma_values and len(ma_values['ma20']) >= 10:
                ma20 = ma_values['ma20']
                if ma20[-1] > ma20[-5] and ma20[-5] > ma20[-10]:
                    trend_direction = 'up'
                    steps.append(f"【步骤3】趋势判断:MA20({ma20[-1]:.2f}) > MA20[-5]({ma20[-5]:.2f}) > MA20[-10]({ma20[-10]:.2f}) → 上涨趋势")
                elif ma20[-1] < ma20[-5] and ma20[-5] < ma20[-10]:
                    trend_direction = 'down'
                    steps.append(f"【步骤3】趋势判断:MA20({ma20[-1]:.2f}) < MA20[-5]({ma20[-5]:.2f}) < MA20[-10]({ma20[-10]:.2f}) → 下跌趋势")
                else:
                    steps.append("【步骤3】趋势判断:MA20走势不明显 → 震荡走势")
            else:
                steps.append("【步骤3】趋势判断:MA20数据不足 → 震荡走势")
            result['trend_direction'] = trend_direction
            # 获取支撑/压力线
            sr = self._compute_daily_support_resistance_line_prices(kline_data)
            support_price = sr.get('support_price')
            resistance_price = sr.get('resistance_price')
            result['support_price'] = support_price
            result['resistance_price'] = resistance_price
            steps.append(f"【步骤4】支撑/压力线:支撑线 = {support_price:.2f}" if support_price else "【步骤4】支撑/压力线:支撑线 = N/A")
            steps.append(f"【步骤5】支撑/压力线:压力线 = {resistance_price:.2f}" if resistance_price else "【步骤5】支撑/压力线:压力线 = N/A")
            # 额外计算关键支撑/压力位(前期高低点)
            additional_support = None
            additional_resistance = None
            if n >= 10:
                recent_lows = lows[-10:]
                recent_highs = highs[-10:]
                additional_support = float(min(recent_lows))
                additional_resistance = float(max(recent_highs))
            # 确定止损和止盈价格
            stop_loss_price = None
            take_profit_price = None
            if support_price and support_price > 0:
                stop_loss_price = support_price * 0.98
                steps.append(f"【步骤6】止损计算:stop_loss = support_price({support_price:.2f}) × 0.98 = {stop_loss_price:.2f}")
            elif additional_support and additional_support > 0:
                stop_loss_price = additional_support * 0.98
                steps.append(f"【步骤6】止损计算:stop_loss = 前期低点({additional_support:.2f}) × 0.98 = {stop_loss_price:.2f}")
            else:
                steps.append("【步骤6】止损计算:无法确定支撑位,止损 = N/A")
            if resistance_price and resistance_price > 0:
                take_profit_price = resistance_price * 1.02
                steps.append(f"【步骤7】止盈计算:take_profit = resistance_price({resistance_price:.2f}) × 1.02 = {take_profit_price:.2f}")
            elif additional_resistance and additional_resistance > 0:
                take_profit_price = additional_resistance * 1.02
                steps.append(f"【步骤7】止盈计算:take_profit = 前期高点({additional_resistance:.2f}) × 1.02 = {take_profit_price:.2f}")
            else:
                steps.append("【步骤7】止盈计算:无法确定压力位,止盈 = N/A")
            result['stop_loss_price'] = stop_loss_price
            result['take_profit_price'] = take_profit_price
            # 计算风险和回报金额
            if stop_loss_price and stop_loss_price > 0:
                risk_amount = current_price - stop_loss_price
                result['risk_amount'] = round(risk_amount, 2)
                steps.append(f"【步骤8】风险金额:risk = current_price({current_price:.2f}) - stop_loss({stop_loss_price:.2f}) = {risk_amount:.2f}")
            if take_profit_price and take_profit_price > 0:
                reward_amount = take_profit_price - current_price
                result['reward_amount'] = round(reward_amount, 2)
                steps.append(f"【步骤9】回报金额:reward = take_profit({take_profit_price:.2f}) - current_price({current_price:.2f}) = {reward_amount:.2f}")
            # 根据BIAS和趋势计算胜率
            # 参考成熟量化系统的参数,胜率范围调整为 0.50 ~ 0.75
            # 确保大多数情况下有正向预期收益
            win_probability = 0.55
            bias_condition = ""
            if result['bias'] is not None:
                bias = result['bias']
                if trend_direction == 'up':
                    if bias < -3:
                        win_probability = 0.72
                        bias_condition = f"上涨趋势 + BIAS({bias:.2f}%) < -3%"
                    elif bias < -1:
                        win_probability = 0.65
                        bias_condition = f"上涨趋势 + -3% ≤ BIAS({bias:.2f}%) < -1%"
                    elif bias < 1:
                        win_probability = 0.60
                        bias_condition = f"上涨趋势 + -1% ≤ BIAS({bias:.2f}%) < 1%"
                    elif bias < 3:
                        win_probability = 0.55
                        bias_condition = f"上涨趋势 + 1% ≤ BIAS({bias:.2f}%) < 3%"
                    else:
                        win_probability = 0.50
                        bias_condition = f"上涨趋势 + BIAS({bias:.2f}%) ≥ 3%"
                elif trend_direction == 'down':
                    if bias > 3:
                        win_probability = 0.68
                        bias_condition = f"下跌趋势 + BIAS({bias:.2f}%) > 3%"
                    elif bias > 1:
                        win_probability = 0.58
                        bias_condition = f"下跌趋势 + 1% ≤ BIAS({bias:.2f}%) ≤ 3%"
                    else:
                        win_probability = 0.50
                        bias_condition = f"下跌趋势 + BIAS({bias:.2f}%) < 1%"
                else:
                    if bias < -3:
                        win_probability = 0.65
                        bias_condition = f"震荡走势 + BIAS({bias:.2f}%) < -3%"
                    elif bias < -1:
                        win_probability = 0.58
                        bias_condition = f"震荡走势 + -3% ≤ BIAS({bias:.2f}%) < -1%"
                    elif bias < 1:
                        win_probability = 0.55
                        bias_condition = f"震荡走势 + -1% ≤ BIAS({bias:.2f}%) < 1%"
                    elif bias < 3:
                        win_probability = 0.52
                        bias_condition = f"震荡走势 + 1% ≤ BIAS({bias:.2f}%) < 3%"
                    else:
                        win_probability = 0.50
                        bias_condition = f"震荡走势 + BIAS({bias:.2f}%) ≥ 3%"
            result['win_probability'] = round(win_probability * 100, 1)
            steps.append(f"【步骤10】胜率计算:条件 = {bias_condition},胜率 p = {win_probability * 100:.1f}%")
            # 计算盈亏比
            risk_reward_ratio = 1.0
            if result['risk_amount'] and result['reward_amount'] and result['risk_amount'] > 0:
                risk_reward_ratio = result['reward_amount'] / result['risk_amount']
                steps.append(f"【步骤11】盈亏比计算:R = reward({result['reward_amount']:.2f}) / risk({result['risk_amount']:.2f}) = {risk_reward_ratio:.2f}")
            elif resistance_price and stop_loss_price and stop_loss_price > 0:
                risk_reward_ratio = (resistance_price - current_price) / (current_price - stop_loss_price)
                steps.append(f"【步骤11】盈亏比计算:R = (resistance({resistance_price:.2f}) - current({current_price:.2f})) / (current({current_price:.2f}) - stop_loss({stop_loss_price:.2f})) = {risk_reward_ratio:.2f}")
            else:
                steps.append("【步骤11】盈亏比计算:默认 R = 1.0")
            result['risk_reward_ratio'] = round(risk_reward_ratio, 2)
            # 凯利公式计算:f = (bp - q) / b
            # 其中:
            #   b = 赔率(盈亏比)= 盈利/亏损
            #   p = 胜率(盈利概率,0~1)
            #   q = 败率 = 1 - p(亏损概率,0~1)
            p = win_probability
            q = 1 - p
            b = risk_reward_ratio
            if b > 0:
                kelly_fraction = (b * p - q) / b
                steps.append(f"【步骤12】凯利公式:f = (bp - q) / b = ({b:.2f} × {p:.4f} - {q:.4f}) / {b:.2f} = {kelly_fraction:.4f}")
            else:
                kelly_fraction = 0.0
                steps.append("【步骤12】凯利公式:b ≤ 0,凯利仓位 = 0")
            result['kelly_fraction'] = round(kelly_fraction, 4)
            result['kelly_pct'] = round(kelly_fraction * 100, 1)
            # 保守凯利(1/2凯利或1/3凯利)
            conservative_kelly = min(kelly_fraction * 0.5, 0.2)
            result['conservative_kelly_pct'] = round(max(conservative_kelly, 0) * 100, 1)
            steps.append(f"【步骤13】保守凯利:conservative = min({kelly_fraction:.4f} × 0.5, 0.2) = {conservative_kelly:.4f} = {max(conservative_kelly, 0) * 100:.1f}%")
            result['calculation_steps'] = steps
            # 生成分析说明
            analysis = []
            if result['bias'] is not None:
                bias = result['bias']
                if bias < -3:
                    analysis.append(f"BIAS({bias:.1f}%):负乖离较大,可能反弹")
                elif bias > 3:
                    analysis.append(f"BIAS({bias:.1f}%):正乖离较大,注意回调")
                else:
                    analysis.append(f"BIAS({bias:.1f}%):乖离正常")
            trend_desc = {'up': '上涨趋势', 'down': '下跌趋势', 'neutral': '震荡走势'}
            analysis.append(f"趋势方向:{trend_desc[trend_direction]}")
            if support_price:
                analysis.append(f"支撑线:{support_price:.2f}")
            if resistance_price:
                analysis.append(f"压力线:{resistance_price:.2f}")
            if stop_loss_price:
                analysis.append(f"建议止损:{stop_loss_price:.2f}")
            if take_profit_price:
                analysis.append(f"建议止盈:{take_profit_price:.2f}")
            analysis.append(f"预估胜率:{result['win_probability']:.1f}%")
            analysis.append(f"预估盈亏比:{result['risk_reward_ratio']:.2f}")
            if kelly_fraction > 0:
                analysis.append(f"凯利仓位:{result['kelly_pct']:.1f}%(保守:{result['conservative_kelly_pct']:.1f}%)")
            else:
                analysis.append("凯利仓位:0%(当前条件不适合买入)")
            result['analysis'] = analysis
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result


    def _show_kelly_result_dialog(self, result, stock_name, parent_win=None):
        """显示凯利计算结果对话框"""
        dialog = self._toplevel(parent_win or self.root)
        dialog.title(f"{stock_name} - 凯利仓位计算")
        dialog.geometry("800x600")
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        if not result.get('success'):
            ttk.Label(main_frame, text=f"计算失败:{result.get('message', '')}",
                      font=("Microsoft YaHei", 14), foreground='red').pack(pady=30)
            ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(pady=15)
            return
        # 标题
        title_label = ttk.Label(main_frame, text=f"{stock_name} 凯利仓位分析",
                               font=("Microsoft YaHei", 18, "bold"))
        title_label.pack(pady=(0, 15))
        # 左右两列布局
        columns_frame = ttk.Frame(main_frame)
        columns_frame.pack(fill=tk.X, pady=(0, 15))
        # 左列:关键指标
        left_frame = ttk.LabelFrame(columns_frame, text="关键指标", padding=15)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        key_info = [
            ("当前价格", f"{result['current_price']:.2f}"),
            ("BIAS(6日)", f"{result['bias']:.2f}%" if result['bias'] is not None else "N/A"),
            ("趋势方向", {'up': '上涨趋势', 'down': '下跌趋势', 'neutral': '震荡走势'}[result['trend_direction']]),
            ("支撑线", f"{result['support_price']:.2f}" if result['support_price'] else "N/A"),
            ("压力线", f"{result['resistance_price']:.2f}" if result['resistance_price'] else "N/A"),
            ("建议止损", f"{result['stop_loss_price']:.2f}" if result['stop_loss_price'] else "N/A"),
            ("建议止盈", f"{result['take_profit_price']:.2f}" if result['take_profit_price'] else "N/A"),
            ("风险金额", f"{result['risk_amount']:.2f}" if result['risk_amount'] else "N/A"),
            ("回报金额", f"{result['reward_amount']:.2f}" if result['reward_amount'] else "N/A"),
        ]
        for label, value in key_info:
            row = ttk.Frame(left_frame)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=label, width=12, font=("Microsoft YaHei", 12)).pack(side=tk.LEFT)
            if "BIAS" in label:
                bias_val = float(value.replace('%', '')) if '%' in value else 0
                color = 'green' if bias_val < -2 else 'red' if bias_val > 2 else 'black'
                ttk.Label(row, text=value, font=("Microsoft YaHei", 12, "bold"), foreground=color).pack(side=tk.LEFT, padx=(15, 0))
            else:
                ttk.Label(row, text=value, font=("Microsoft YaHei", 12)).pack(side=tk.LEFT, padx=(15, 0))
        # 右列:凯利仓位计算
        right_frame = ttk.LabelFrame(columns_frame, text="凯利仓位计算", padding=15)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        kelly_info = [
            ("预估胜率", f"{result['win_probability']:.1f}%"),
            ("预估盈亏比", f"{result['risk_reward_ratio']:.2f}"),
            ("凯利公式仓位", f"{result['kelly_pct']:.1f}%"),
            ("保守凯利仓位", f"{result['conservative_kelly_pct']:.1f}%"),
        ]
        for label, value in kelly_info:
            row = ttk.Frame(right_frame)
            row.pack(fill=tk.X, pady=6)
            ttk.Label(row, text=label, width=15, font=("Microsoft YaHei", 12)).pack(side=tk.LEFT)
            if "凯利" in label:
                kelly_value = float(value.replace('%', ''))
                color = 'red' if kelly_value > 30 else 'orange' if kelly_value > 15 else 'green'
                ttk.Label(row, text=value, font=("Microsoft YaHei", 16, "bold"), foreground=color).pack(side=tk.LEFT, padx=(15, 0))
            else:
                ttk.Label(row, text=value, font=("Microsoft YaHei", 14)).pack(side=tk.LEFT, padx=(15, 0))
        # 仓位建议区域
        advice_frame = ttk.LabelFrame(main_frame, text="仓位建议", padding=15)
        advice_frame.pack(fill=tk.X, pady=(0, 15))
        kelly_pct = result['kelly_pct']
        conservative_pct = result['conservative_kelly_pct']
        if kelly_pct <= 0:
            advice_text = "当前条件不适合买入,建议观望"
            advice_color = 'gray'
        elif kelly_pct < 10:
            advice_text = f"轻仓参与,建议仓位 {conservative_pct:.1f}%(凯利 {kelly_pct:.1f}%)"
            advice_color = 'green'
        elif kelly_pct < 25:
            advice_text = f"中等仓位,建议仓位 {conservative_pct:.1f}%(凯利 {kelly_pct:.1f}%)"
            advice_color = 'orange'
        else:
            advice_text = f"较重仓位,建议使用保守仓位 {conservative_pct:.1f}%(凯利 {kelly_pct:.1f}%)"
            advice_color = 'red'
        ttk.Label(advice_frame, text=advice_text, font=("Microsoft YaHei", 14),
                  foreground=advice_color, wraplength=750).pack(pady=8)
        # 计算步骤区域
        steps_frame = ttk.LabelFrame(main_frame, text="计算过程", padding=15)
        steps_frame.pack(fill=tk.BOTH, expand=True)
        steps_text = tk.Text(steps_frame, height=6, font=("Microsoft YaHei", 11), wrap=tk.WORD)
        steps_text.pack(fill=tk.BOTH, expand=True)
        for step in result.get('calculation_steps', []):
            steps_text.insert(tk.END, step + "\n")
        steps_text.config(state=tk.DISABLED)
        # 分析说明区域
        analysis_frame = ttk.LabelFrame(main_frame, text="分析说明", padding=15)
        analysis_frame.pack(fill=tk.BOTH, expand=True)
        text_widget = tk.Text(analysis_frame, height=4, font=("Microsoft YaHei", 12), wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)
        for line in result.get('analysis', []):
            text_widget.insert(tk.END, line + "\n")
        text_widget.config(state=tk.DISABLED)
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=dialog.destroy).pack(pady=15)


    def _show_kelly_config(self):
        """显示凯利公式设定对话框"""
        print("凯利设定按钮被点击")
        try:
            config_window = self._toplevel(self.root)
            config_window.title("凯利公式设定")
            config_window.geometry("800x600")
            config_window.transient(self.root)  # 设置为模态窗口
            config_window.grab_set()  # 获取焦点
            print("凯利设定窗口已创建")
            # 说明标签
            ttk.Label(config_window,
                     text="设定不同均线状态下的盈亏比(b)和胜率(p)\n" +
                          "盈亏比(b):盈利时获得的收益与亏损时损失的比值\n" +
                          "胜率(p):交易成功的概率(0-1之间)\n" +
                          "保存后的数值将用于三维一体检测中的凯利公式计算",
                     font=("TkDefaultFont", 11), wraplength=750, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=(10, 5))
            # 创建滚动框架
            canvas = tk.Canvas(config_window)
            scrollbar = ttk.Scrollbar(config_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
            scrollbar.pack(side="right", fill="y")
            # 定义默认配置(按照用户要求的5种情况)
            default_configs = [
                {"name": "股价大于1日、5日、10日、20日均线", "key": "True_True_True_True", "b": 3.0, "p": 0.8},
                {"name": "股价大于5日、10日、20日均线", "key": "False_True_True_True", "b": 3.0, "p": 0.8},
                {"name": "股价大于10日、20日均线", "key": "False_False_True_True", "b": 3.0, "p": 0.7},
                {"name": "股价单纯大于20日均线", "key": "False_False_False_True", "b": 2.0, "p": 0.5},
                {"name": "股价小于20日均线", "key": "below_ma20", "b": 0.3, "p": 0.3},
            ]
            config_vars = {}
            # 创建配置项
            for config in default_configs:
                frame = ttk.LabelFrame(scrollable_frame, text=config["name"], padding=10)
                frame.pack(fill=tk.X, padx=10, pady=5)
                # 从配置中读取或使用默认值
                if config["key"] in self.kelly_config:
                    b_val = self.kelly_config[config["key"]].get("b", config["b"])
                    p_val = self.kelly_config[config["key"]].get("p", config["p"])
                else:
                    b_val = config["b"]
                    p_val = config["p"]
                # 盈亏比b
                b_frame = ttk.Frame(frame)
                b_frame.pack(fill=tk.X, pady=2)
                ttk.Label(b_frame, text="盈亏比(b):", width=12).pack(side=tk.LEFT, padx=(0, 5))
                b_var = tk.DoubleVar(value=b_val)
                b_entry = ttk.Entry(b_frame, textvariable=b_var, width=15)
                b_entry.pack(side=tk.LEFT, padx=(0, 10))
                # 胜率p
                p_frame = ttk.Frame(frame)
                p_frame.pack(fill=tk.X, pady=2)
                ttk.Label(p_frame, text="胜率(p):", width=12).pack(side=tk.LEFT, padx=(0, 5))
                p_var = tk.DoubleVar(value=p_val)
                p_entry = ttk.Entry(p_frame, textvariable=p_var, width=15)
                p_entry.pack(side=tk.LEFT, padx=(0, 10))
                # 显示计算示例(实时更新)
                kelly_label = ttk.Label(p_frame, text="",
                         font=("TkDefaultFont", 11), foreground="blue")
                kelly_label.pack(side=tk.LEFT, padx=(10, 0))
                def update_kelly_display():
                    """更新凯利百分比显示"""
                    try:
                        b = b_var.get()
                        p = p_var.get()
                        if b > 0 and 0 <= p <= 1:
                            kelly_ratio = self._calculate_kelly_ratio(b, p)
                            kelly_label.config(text=f"凯利百分比: {kelly_ratio * 100:.2f}%")
                        else:
                            kelly_label.config(text="凯利百分比: 无效")
                    except:
                        kelly_label.config(text="凯利百分比: 计算错误")
                # 绑定输入变化事件
                b_var.trace_add("write", lambda *args: update_kelly_display())
                p_var.trace_add("write", lambda *args: update_kelly_display())
                # 初始显示
                update_kelly_display()
                config_vars[config["key"]] = {"b": b_var, "p": p_var, "name": config["name"]}
            # 按钮区域
            button_frame = ttk.Frame(config_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            def save_kelly_config():
                """保存凯利公式配置"""
                try:
                    print("开始保存凯利公式配置...")
                    for key, vars_dict in config_vars.items():
                        b_val = vars_dict["b"].get()
                        p_val = vars_dict["p"].get()
                        # 验证范围
                        if b_val <= 0 or p_val < 0 or p_val > 1:
                            messagebox.showerror("错误", f"配置项 '{vars_dict['name']}' 的值超出有效范围\n盈亏比(b)必须>0,胜率(p)必须在0-1之间", parent=config_window)
                            return
                        if key not in self.kelly_config:
                            self.kelly_config[key] = {}
                        self.kelly_config[key]["b"] = float(b_val)
                        self.kelly_config[key]["p"] = float(p_val)
                        print(f"保存配置项 {key}: b={b_val}, p={p_val}")
                    # 保存到配置文件(确保保存到初始配置表中)
                    self.ai_config_manager.config["kelly_config"] = self.kelly_config.copy()  # 使用copy确保是新的字典
                    save_result = self.ai_config_manager.save_config()
                    if save_result:
                        # 确保内存中的配置也更新(重新从配置文件读取,确保一致性)
                        self.kelly_config = self.ai_config_manager.config.get("kelly_config", {}).copy()
                        print("凯利公式配置已成功保存到配置文件")
                        print(f"当前内存中的kelly_config: {self.kelly_config}")
                        messagebox.showinfo("成功", "凯利公式配置已保存到配置文件\n持仓股将使用最新的盈亏比和胜率重新计算", parent=config_window)
                        config_window.destroy()
                        # 重新检测所有持仓股以更新凯利结果(使用最新的凯利公式b和p)
                        # 凯利配置是全局的,需要重新检测所有持仓组
                        for gidx in range(1, 6):
                            holding_stocks, _holding_labels, _holding_kelly_results = self._get_holding_group_data(gidx)
                            # 只检测有持仓股的组
                            if any(holding_stocks):
                                print(f"重新检测持仓组 {gidx},使用最新的凯利配置")
                                self._check_holdings(gidx)
                    else:
                        messagebox.showerror("错误", "保存配置文件失败,请检查文件权限", parent=config_window)
                except Exception as e:
                    import traceback
                    error_msg = f"保存配置失败: {e}\n{traceback.format_exc()}"
                    print(error_msg)
                    messagebox.showerror("错误", f"保存配置失败: {e}", parent=config_window)
            ttk.Button(button_frame, text="保存", command=save_kelly_config, width=10).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="取消", command=config_window.destroy, width=10).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            import traceback
            error_msg = f"打开凯利公式设定对话框失败: {e}\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("错误", f"打开凯利公式设定对话框失败: {e}\n\n详细信息请查看控制台输出", parent=self.root)
            except:
                # 如果无法显示消息框,至少打印错误
                print(f"无法显示错误消息框: {e}")


__all__ = ["KellyMixin"]

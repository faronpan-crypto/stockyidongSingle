"""个股详情/K线/分时/分钟"""
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


class StockDetailMixin:
    """个股详情/K线/分时/分钟"""

    def show_kline_dialog(self):
        """显示K线图对话框"""
        try:
            # 先获取热门股票作为默认数据
            hot_stocks = get_news_stocks_merged_recent_days(ndays=5)
            if hot_stocks:
                stock_name, stock_code = hot_stocks[0]
                # 获取K线数据
                kline_data = self._get_daily_kline_data_tushare(stock_code)
                if kline_data:
                    # 打开K线图弹窗
                    self._show_daily_kline_zoom(kline_data, stock_name)
                else:
                    messagebox.showwarning("提示", "无法获取股票K线数据", parent=self.root)
            else:
                messagebox.showwarning("提示", "暂无热门股票数据", parent=self.root)
        except Exception as e:
            messagebox.showerror("错误", f"打开K线图失败: {e}", parent=self.root)

    def _calc_intraday_composite(self, data):
        """主流量化盘中综合判别: 5维度打分 → 优良差危险
        维度: 指数趋势(25%) + 涨跌广度(25%) + 涨停情绪(20%) + 量能对比(15%) + 均线位置(15%)"""
        details = []
        scores = []

        # 1. 指数趋势分 (25%)
        idx_list = data.get("indices", [])
        if idx_list:
            main_idx = None
            for it in idx_list:
                if it["code"] == "000001": main_idx = it; break
            if main_idx is None and idx_list: main_idx = idx_list[0]
            idx_pct = main_idx["pct"] if main_idx else 0
            if idx_pct > 1.5: isc = 95; idesc = f"上证+{idx_pct:.2f}% 强趋势"
            elif idx_pct > 0.3: isc = 75; idesc = f"上证+{idx_pct:.2f}% 温和上涨"
            elif idx_pct > -0.3: isc = 50; idesc = f"上证{idx_pct:+.2f}% 震荡"
            elif idx_pct > -1.5: isc = 25; idesc = f"上证{idx_pct:+.2f}% 温和下跌"
            else: isc = 5; idesc = f"上证{idx_pct:+.2f}% 大跌!"
            scores.append(("指数趋势", isc, 25, idesc))
        else:
            scores.append(("指数趋势", 50, 25, "无数据"))

        # 2. 涨跌广度分 (25%)
        br = data.get("breadth", {})
        up, dn = br.get("up", 0), br.get("down", 0)
        if up + dn > 0:
            ratio = up / max(dn, 1)
            if ratio > 2.5: bsc = 95; bdesc = f"涨{up}/跌{dn} 极度普涨"
            elif ratio > 1.5: bsc = 75; bdesc = f"涨{up}/跌{dn} 偏多"
            elif ratio > 1.0: bsc = 60; bdesc = f"涨{up}/跌{dn} 略多"
            elif ratio > 0.7: bsc = 35; bdesc = f"涨{up}/跌{dn} 偏空"
            elif ratio > 0.4: bsc = 20; bdesc = f"涨{up}/跌{dn} 明显偏弱"
            else: bsc = 5; bdesc = f"涨{up}/跌{dn} 暴跌!"
            scores.append(("涨跌广度", bsc, 25, bdesc))
        else:
            scores.append(("涨跌广度", 50, 25, "无数据"))

        # 3. 涨停情绪分 (20%)
        zt, dt = br.get("zt", 0), br.get("dt", 0)
        if zt >= 80: zsc = 95; zdesc = f"涨停{zt} 高潮!"
        elif zt >= 50: zsc = 80; zdesc = f"涨停{zt} 情绪好"
        elif zt >= 25: zsc = 60; zdesc = f"涨停{zt} 一般"
        elif zt >= 10: zsc = 40; zdesc = f"涨停{zt} 偏弱"
        elif zt > 0: zsc = 20; zdesc = f"涨停{zt} 冰点"
        else: zsc = 10; zdesc = "0涨停 极寒!"
        if dt >= 10: zsc -= 20; zdesc += f" 跌停{dt}!"
        elif dt >= 5: zsc -= 10; zdesc += f" 跌停{dt}"
        scores.append(("涨停情绪", max(0, min(100, zsc)), 20, zdesc))

        # 4. 量能对比分 (15%)
        ar = data.get("amount_ratio", 1.0)
        if ar > 1.5: asc = 90; adesc = f"量比5日均量{ar:.1f}x 放量活跃"
        elif ar > 1.1: asc = 70; adesc = f"量比{ar:.1f}x 温和"
        elif ar > 0.8: asc = 50; adesc = f"量比{ar:.1f}x 正常"
        elif ar > 0.5: asc = 30; adesc = f"量比{ar:.1f}x 缩量"
        else: asc = 15; adesc = f"量比{ar:.1f}x 极度缩量"
        scores.append(("量能对比", asc, 15, adesc))

        # 5. 均线位置分 (15%)
        sh_ma5 = data.get("sh_ma5")
        sh_ma20 = data.get("sh_ma20")
        idx_list[0]["pct"] if idx_list else 0
        sh_close = idx_list[0]["close"] if idx_list else 0
        if sh_ma5 and sh_close > 0:
            if sh_close > sh_ma5 > sh_ma20: msc = 90; mdesc = "上证>MA5>MA20 多头排列"
            elif sh_close > sh_ma5: msc = 70; mdesc = "上证>MA5 站上短线均线"
            elif sh_close < sh_ma5 < sh_ma20: msc = 20; mdesc = "上证<MA5<MA20 空头排列"
            elif sh_close < sh_ma5: msc = 35; mdesc = "上证<MA5 跌破短线均线"
            else: msc = 50; mdesc = "均线缠绕"
            scores.append(("均线位置", msc, 15, mdesc))
        else:
            scores.append(("均线位置", 50, 15, "无数据"))

        # 加权总分
        total_w = sum(w for _, _, w, _ in scores)
        total_s = sum(s * w for _, s, w, _ in scores)
        final_score = round(total_s / total_w) if total_w > 0 else 50

        # 等级判定
        if final_score >= 75:
            level, signal = "excellent", "🟢"
            level_cn = "优"
        elif final_score >= 55:
            level, signal = "good", "🔵"
            level_cn = "良"
        elif final_score >= 35:
            level, signal = "warning", "🟡"
            level_cn = "差"
        else:
            level, signal = "danger", "🔴"
            level_cn = "危险"

        for name, s, w, desc in scores:
            emoji = "🟢" if s >= 70 else ("🟡" if s >= 40 else "🔴")
            details.append(f"{emoji} {name}: {s}分 ({w}%) → {desc}")

        return {"score": final_score, "level": level, "level_cn": level_cn,
                "signal": signal, "details": details}, details

    def _get_15min_kline_data(self, stock_code, days=10):
        """获取15分钟K线数据(10日周期)"""
        try:
            # 计算开始日期
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            # 获取15分钟K线数据
            kline_data = ak.stock_zh_a_hist_min_em(symbol=stock_code, period="15",
                                                   start_date=start_date_str,
                                                   end_date=end_date_str, adjust="")
            if kline_data is None or kline_data.empty:
                return None
            # 计算均线(1日、3日、5日、10日、20日)
            # 注意:15分钟K线,每天约16根(交易时间4小时=240分钟,240/15=16根)
            # 1日=1*16=16根,3日=48根,5日=80根,10日=160根,20日=320根
            close_prices = kline_data['收盘'].values if '收盘' in kline_data.columns else kline_data.iloc[:, -2].values
            # 计算均线周期(15分钟K线)
            periods = {
                'ma1': min(16, len(close_prices)),    # 1日约16根
                'ma3': min(48, len(close_prices)),    # 3日约48根
                'ma5': min(80, len(close_prices)),    # 5日约80根
                'ma10': min(160, len(close_prices)),  # 10日约160根
                'ma20': min(320, len(close_prices))   # 20日约320根
            }
            # 计算各均线值
            ma_values = {}
            for ma_name, period in periods.items():
                if len(close_prices) >= period:
                    ma_values[ma_name] = []
                    for i in range(period-1, len(close_prices)):
                        ma_value = sum(close_prices[i-period+1:i+1]) / period
                        ma_values[ma_name].append(ma_value)
                else:
                    ma_values[ma_name] = []
            return {
                'data': kline_data,
                'ma_values': ma_values,
                'dates': kline_data.index if hasattr(kline_data.index, '__len__') else range(len(kline_data))
            }
        except Exception as e:
            print(f"获取15分钟K线数据失败 {stock_code}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_daily_kline_data_tushare(self, stock_code, days=60):
        """从Tushare获取日K线数据(用于持仓详情日K线图)"""
        try:
            if not TS_AVAILABLE or not (getattr(self, 'ts_token', None) or TS_DEFAULT_TOKEN):
                return None
            self._ensure_tushare_client(self.ts_token or TS_DEFAULT_TOKEN)
            ts_code = self._format_ts_code(str(stock_code).zfill(6))
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y%m%d')
            df = self.ts_client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return None
            df = df.sort_values('trade_date').tail(days).reset_index(drop=True)
            # 转为与 _draw 兼容的列名(成交量:Tushare daily 的 vol 单位为手)
            _vol = df['vol'].astype(float) if 'vol' in df.columns else pd.Series(np.zeros(len(df)))
            data = pd.DataFrame({
                '开盘': df['open'].astype(float),
                '收盘': df['close'].astype(float),
                '最高': df['high'].astype(float),
                '最低': df['low'].astype(float),
                '成交量': _vol,
            })
            close_prices = data['收盘'].values
            opens = data['开盘'].values
            highs = data['最高'].values
            lows = data['最低'].values
            len(close_prices)
            periods = {
                'ma1': min(1, len(close_prices)),
                'ma5': min(5, len(close_prices)),
                'ma10': min(10, len(close_prices)),
                'ma20': min(20, len(close_prices))
            }
            ma_values = {}
            for ma_name, period in periods.items():
                if len(close_prices) >= period:
                    ma_values[ma_name] = []
                    for i in range(period - 1, len(close_prices)):
                        ma_value = float(sum(close_prices[i - period + 1:i + 1]) / period)
                        ma_values[ma_name].append(ma_value)
                else:
                    ma_values[ma_name] = []
            # 主力成本线(VWAP):累计成交额 / 累计成交量,通达信算法
            # 成交均价 = (开盘 + 最高 + 最低 + 收盘) / 4
            vwap_values = []
            if len(close_prices) >= 2:
                cum_amount = 0.0
                cum_vol = 0.0
                for i in range(len(close_prices)):
                    typical_price = (opens[i] + highs[i] + lows[i] + close_prices[i]) / 4.0
                    amount = typical_price * float(data['成交量'].iloc[i])
                    cum_amount += amount
                    cum_vol += float(data['成交量'].iloc[i])
                    if cum_vol > 0:
                        vwap_values.append(float(cum_amount / cum_vol))
                    else:
                        vwap_values.append(float(typical_price))
            ma_values['vwap'] = vwap_values
            return {
                'data': data,
                'ma_values': ma_values,
                'dates': list(df['trade_date'].astype(str)),
                'trade_dates': list(df['trade_date'].astype(str))
            }
        except Exception as e:
            print(f"获取日K线数据(Tushare)失败 {stock_code}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _plot_kline_zoom_subpanel(self, ax, key, dates, opens, closes, highs, lows, vol):
        """放大窗副图:VOL / MACD / WR2 / KDJ / BOLL。"""
        x = dates
        n = len(closes)
        o = np.asarray(opens, dtype=float)
        c = np.asarray(closes, dtype=float)
        indicator_descriptions = {
            "VOL": "成交量:反映市场交易活跃度,红色为上涨日,绿色为下跌日",
            "MACD": "MACD:指数平滑异同移动平均线,DIF上穿DEA为金叉,下穿为死叉",
            "WR2": "WR:威廉指标,超买超卖指标,低于-80为超卖,高于-20为超买",
            "KDJ": "KDJ:随机指标,K上穿D为金叉买入信号,80以上超买,20以下超卖",
            "BOLL": "BOLL:布林带,价格突破上轨超买,跌破下轨超卖,中轨为趋势线"
        }
        if key == "VOL":
            v = np.asarray(vol, dtype=float) if vol is not None else np.zeros(n)
            if n < 1 or float(np.nanmax(np.abs(v))) < 1e-9:
                ax.text(0.5, 0.5, "无成交量数据(需 Tushare daily 含 vol)", transform=ax.transAxes, ha="center", fontsize=9)
                ax.set_ylabel("VOL")
                return
            colors = ["#d32f2f" if c[i] >= o[i] else "#388e3c" for i in range(n)]
            ax.bar(x, v, color=colors, alpha=0.75, width=0.65)
            if n >= 5:
                vma = pd.Series(v).rolling(5, min_periods=1).mean()
                ax.plot(x, vma.values, color="#f57c00", linewidth=1.0, label="VOL MA5")
            ax.set_ylabel("成交量(手)")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "MACD":
            ema12 = self._ema_np(c, 12)
            ema26 = self._ema_np(c, 26)
            dif = ema12 - ema26
            dea = self._ema_np(dif, 9)
            macdh = 2.0 * (dif - dea)
            ax.plot(x, dif, label="DIF", linewidth=1.0, color="#1565c0")
            ax.plot(x, dea, label="DEA", linewidth=1.0, color="#c62828")
            bar_colors = ["#d32f2f" if v >= 0 else "#388e3c" for v in macdh]
            ax.bar(x, macdh, color=bar_colors, alpha=0.45, width=0.55)
            ax.axhline(0, color="gray", linewidth=0.6)
            ax.set_ylabel("MACD")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "WR2":
            wr = self._williams_r_n(highs, lows, closes, 2)
            ax.plot(x, wr, label="WR(2日)", linewidth=1.0, color="#6a1b9a")
            ax.axhline(-20, color="gray", linestyle="--", linewidth=0.6)
            ax.axhline(-80, color="gray", linestyle="--", linewidth=0.6)
            ax.set_ylabel("WR")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "KDJ":
            kv, dv, jv = self._kdj_series(highs, lows, closes, 9)
            ax.plot(x, kv, label="K", linewidth=1.0, color="#c62828")
            ax.plot(x, dv, label="D", linewidth=1.0, color="#1565c0")
            ax.plot(x, jv, label="J", linewidth=0.9, color="#6a1b9a", alpha=0.9)
            ax.axhline(80, color="gray", linestyle=":", linewidth=0.5)
            ax.axhline(20, color="gray", linestyle=":", linewidth=0.5)
            ax.set_ylabel("KDJ")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        elif key == "BOLL":
            up, mid, lo = self._boll_np(closes, 20, 2.0)
            ax.plot(x, mid, label="MID(20)", color="black", linewidth=1.0)
            ax.plot(x, up, label="UP", color="#d32f2f", linewidth=0.95, alpha=0.9)
            ax.plot(x, lo, label="LOW", color="#2e7d32", linewidth=0.95, alpha=0.9)
            ax.set_ylabel("BOLL")
            ax.legend(loc="upper left", fontsize=7)
            ax.set_title(indicator_descriptions[key], fontsize=7, loc="left", color="#666666", pad=2)
        ax.grid(True, alpha=0.3)

    def _apply_daily_kline_ax(self, ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True, buy_points=None):
        """在给定 Axes 上绘制主图 K 线 + 均线 + 支撑/压力线。"""
        data = kline_data['data']
        ma_values = kline_data['ma_values']
        trade_dates = kline_data.get('trade_dates') or list(range(len(data)))
        dates = list(range(len(data)))
        n = len(dates)
        opens = data['开盘'].values
        closes = data['收盘'].values
        highs = data['最高'].values
        lows = data['最低'].values
        for i in range(len(dates)):
            color = 'red' if closes[i] >= opens[i] else 'green'
            body_bottom = min(opens[i], closes[i])
            body_top = max(opens[i], closes[i])
            ax1.bar(i, body_top - body_bottom, bottom=body_bottom, color=color, alpha=0.8, width=0.6)
            ax1.plot([i, i], [lows[i], body_bottom], color=color, linewidth=1)
            ax1.plot([i, i], [body_top, highs[i]], color=color, linewidth=1)
        ax1.plot(dates, closes, color='black', linewidth=0.5, label='收盘价', alpha=0.5, linestyle='--')
        ma_colors = {'ma1': '#FF0000', 'ma5': '#00FF00', 'ma10': '#0000FF', 'ma20': '#FF00FF', 'vwap': '#FFD700'}
        ma_labels = {'ma1': '1日均线', 'ma5': '5日均线', 'ma10': '10日均线', 'ma20': '20日均线', 'vwap': '主力成本线'}
        period_map = {'ma1': 1, 'ma5': 5, 'ma10': 10, 'ma20': 20, 'vwap': 1}
        for ma_name in ['ma1', 'ma5', 'ma10', 'ma20', 'vwap']:
            if ma_name not in ma_values or len(ma_values[ma_name]) == 0:
                continue
            ma_data = ma_values[ma_name]
            period = period_map[ma_name]
            start_idx = min(period - 1, len(dates) - 1)
            ma_indices = list(range(start_idx, start_idx + len(ma_data)))
            min_len = min(len(ma_indices), len(ma_data))
            if min_len > 0:
                ax1.plot(ma_indices[:min_len], ma_data[:min_len], color=ma_colors[ma_name],
                        linewidth=1.5, label=ma_labels[ma_name], alpha=0.8)
        # 股价震荡区间图
        try:
            import numpy as np
            # 计算20日移动平均线
            if n >= 20:
                # 计算移动平均线
                ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
                # 计算标准差
                std20 = np.array([np.std(closes[i:i+20]) for i in range(n-19)])
                # 计算上轨和下轨
                upper_band = ma20 + 2 * std20
                lower_band = ma20 - 2 * std20
                # 确定开始索引
                start_idx = 19
                # 绘制移动平均线
                ax1.plot(dates[start_idx:], ma20, color='#FFA500', linewidth=1.5, label='20日MA', alpha=0.8)
                # 绘制上轨和下轨
                ax1.plot(dates[start_idx:], upper_band, color='#4682B4', linewidth=1.0, label='上轨', alpha=0.8, linestyle='--')
                ax1.plot(dates[start_idx:], lower_band, color='#4682B4', linewidth=1.0, label='下轨', alpha=0.8, linestyle='--')
                # 填充震荡区间
                ax1.fill_between(dates[start_idx:], lower_band, upper_band, color='#E6E6FA', alpha=0.3, label='震荡区间')
        except Exception as e:
            print(f"绘制震荡区间失败: {e}")
        # 趋势:用 20 日均线近端斜率辅助判断
        uptrend = False
        downtrend = False
        if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
            m20 = np.asarray(ma_values['ma20'], dtype=float)
            uptrend = bool(m20[-1] > m20[-6])
            downtrend = bool(m20[-1] < m20[-6])
        elif n >= 12:
            uptrend = bool(closes[-1] > closes[-11])
            downtrend = bool(closes[-1] < closes[-11])
        # 波谷 / 波峰(简单枢轴)
        piv_lo = [i for i in range(1, n - 1) if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]]
        piv_hi = [i for i in range(1, n - 1) if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]]
        x_end = float(n - 1)
        # 绘制阶梯类型的长方形框架(平行的阻力线和支撑线)
        if show_support_resistance:
            try:
                # 处理支撑线(波谷)
                if len(piv_lo) >= 2:
                    # 按时间顺序排序波谷
                    sorted_piv_lo = sorted(piv_lo)
                    # 根据波谷数量确定线宽,数量越多级别越高
                    line_width = 1.0
                    if len(sorted_piv_lo) >= 3:
                        line_width = 2.0  # 3个及以上波谷,级别更高,线更粗
                    # 绘制水平支撑线
                    for i, piv in enumerate(sorted_piv_lo):
                        support_level = lows[piv]
                        # 绘制支撑线
                        ax1.axhline(y=support_level, color='#006400', linewidth=line_width, linestyle='--', alpha=0.7)
                        # 标注支撑线
                        ax1.text(piv, support_level - (max(closes) - min(closes)) * 0.02, f'支撑 {support_level:.2f}',
                                 fontsize=8, color='#006400', ha='center')
                        # 如果不是最后一个波谷,绘制与下一个波谷之间的垂直线
                        if i < len(sorted_piv_lo) - 1:
                            next_piv = sorted_piv_lo[i + 1]
                            ax1.plot([piv, piv], [support_level, lows[next_piv]], color='#006400', linewidth=line_width, linestyle='--', alpha=0.7)
                # 处理阻力线(波峰)
                if len(piv_hi) >= 2:
                    # 按时间顺序排序波峰
                    sorted_piv_hi = sorted(piv_hi)
                    # 根据波峰数量确定线宽,数量越多级别越高
                    line_width = 1.0
                    if len(sorted_piv_hi) >= 3:
                        line_width = 2.0  # 3个及以上波峰,级别更高,线更粗
                    # 绘制水平阻力线
                    for i, piv in enumerate(sorted_piv_hi):
                        resistance_level = highs[piv]
                        # 绘制阻力线
                        ax1.axhline(y=resistance_level, color='#8B0000', linewidth=line_width, linestyle='--', alpha=0.7)
                        # 标注阻力线
                        ax1.text(piv, resistance_level + (max(closes) - min(closes)) * 0.02, f'阻力 {resistance_level:.2f}',
                                 fontsize=8, color='#8B0000', ha='center')
                        # 如果不是最后一个波峰,绘制与下一个波峰之间的垂直线
                        if i < len(sorted_piv_hi) - 1:
                            next_piv = sorted_piv_hi[i + 1]
                            ax1.plot([piv, piv], [resistance_level, highs[next_piv]], color='#8B0000', linewidth=1.0, linestyle='--', alpha=0.7)
                # 绘制长方形框架
                if len(piv_lo) >= 2 and len(piv_hi) >= 2:
                    # 获取最近的波谷和波峰
                    recent_piv_lo = sorted(piv_lo)[-2:]
                    recent_piv_hi = sorted(piv_hi)[-2:]
                    # 绘制长方形框架
                    if len(recent_piv_lo) == 2 and len(recent_piv_hi) == 2:
                        # 确定长方形的四个顶点
                        x1 = min(recent_piv_lo[0], recent_piv_hi[0])
                        x2 = max(recent_piv_lo[1], recent_piv_hi[1])
                        y1 = min(lows[recent_piv_lo[0]], lows[recent_piv_lo[1]])
                        y2 = max(highs[recent_piv_hi[0]], highs[recent_piv_hi[1]])
                        # 绘制长方形
                        ax1.plot([x1, x2, x2, x1, x1], [y1, y1, y2, y2, y1], color='#9370DB', linewidth=1.5, linestyle='--', alpha=0.8, label='矩形框架')
            except Exception as e:
                print(f"绘制阶梯框架失败: {e}")
            # 趋势:用 20 日均线近端斜率辅助判断
            uptrend = False
            downtrend = False
            if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
                m20 = np.asarray(ma_values['ma20'], dtype=float)
                uptrend = bool(m20[-1] > m20[-6])
                downtrend = bool(m20[-1] < m20[-6])
            elif n >= 12:
                uptrend = bool(closes[-1] > closes[-11])
                downtrend = bool(closes[-1] < closes[-11])
            # 原有的支撑/压力线逻辑
            if uptrend and not downtrend and len(piv_lo) >= 2:
                cand = piv_lo[-3:] if len(piv_lo) >= 3 else piv_lo[-2:]
                ok = None
                if len(cand) >= 3 and lows[cand[-1]] > lows[cand[-2]] > lows[cand[-3]]:
                    ok = (cand[-3], cand[-1])
                elif len(cand) >= 2 and lows[cand[-1]] > lows[cand[-2]]:
                    ok = (cand[-2], cand[-1])
                if ok:
                    i0, i1 = ok
                    x0, y0, x1, y1 = float(i0), float(lows[i0]), float(i1), float(lows[i1])
                    if x1 != x0:
                        m = (y1 - y0) / (x1 - x0)
                        y_end = y0 + m * (x_end - x0)
                        ax1.plot([x0, x_end], [y0, y_end], color='#006400', linewidth=2.0, linestyle='--',
                                label='支撑线(低点连线)', alpha=0.95, zorder=6)
            elif downtrend and not uptrend and len(piv_hi) >= 2:
                cand = piv_hi[-3:] if len(piv_hi) >= 3 else piv_hi[-2:]
                ok = None
                if len(cand) >= 3 and highs[cand[-1]] < highs[cand[-2]] < highs[cand[-3]]:
                    ok = (cand[-3], cand[-1])
                elif len(cand) >= 2 and highs[cand[-1]] < highs[cand[-2]]:
                    ok = (cand[-2], cand[-1])
                if ok:
                    i0, i1 = ok
                    x0, y0, x1, y1 = float(i0), float(highs[i0]), float(i1), float(highs[i1])
                    if x1 != x0:
                        m = (y1 - y0) / (x1 - x0)
                        y_end = y0 + m * (x_end - x0)
                        ax1.plot([x0, x_end], [y0, y_end], color='#8B0000', linewidth=2.0, linestyle='--',
                                label='压力线(高点连线)', alpha=0.95, zorder=6)
        # 绘制买点竖线
        if buy_points and len(buy_points) > 0:
            y_min = min(lows)
            y_max = max(highs)
            y_range = y_max - y_min
            for i, point in enumerate(buy_points):
                idx = point['index']
                ax1.plot([idx, idx], [y_min - y_range * 0.1, y_max + y_range * 0.1],
                        color='#FFD700', linewidth=2.0, linestyle='-.', alpha=0.8, zorder=7)
                ax1.text(idx, y_max + y_range * 0.05, f'买{i+1}', fontsize=8,
                        color='#FFD700', ha='center', rotation=90)
        _hint = " 双击图表可放大" if show_zoom_hint else ""
        ax1.set_title(f"{stock_name} - 日K线图(Tushare){_hint}", fontsize=12, fontweight='bold')
        ax1.set_ylabel("价格", fontsize=10)
        ax1.legend(loc='upper left', fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlabel("日期", fontsize=10)
        def _fmt_date(s):
            if not s or len(s) != 8:
                return str(s)
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        step = max(1, len(trade_dates) // 12)
        ax1.set_xticks(dates[::step])
        ax1.set_xticklabels([_fmt_date(trade_dates[i]) if i < len(trade_dates) else str(i) for i in dates[::step]], rotation=45, ha='right')
        if hide_x_labels:
            ax1.tick_params(axis="x", labelbottom=False)
            ax1.set_xlabel("")

    def _build_daily_kline_figure(self, kline_data, stock_name, figsize=(12, 6), show_zoom_hint=True, show_support_resistance=False):
        """单图日K线 Figure(嵌入持仓详情等)。"""
        from matplotlib.figure import Figure
        fig = Figure(figsize=figsize, dpi=100)
        # 根据情绪周期设置背景颜色
        emotion_cycle = getattr(self, 'emotion_cycle_var', None)
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                fig.patch.set_facecolor('#E8F5E9')
                fig.patch.set_alpha(0.6)
            elif cycle == "震荡":
                fig.patch.set_facecolor('#FFF9C4')
                fig.patch.set_alpha(0.6)
            elif cycle == "下行":
                fig.patch.set_facecolor('#FFEBEE')
                fig.patch.set_alpha(0.6)
        ax1 = fig.add_subplot(111)
        # 设置axes背景颜色
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                ax1.set_facecolor('#E8F5E9')
                ax1.patch.set_alpha(0.4)
            elif cycle == "震荡":
                ax1.set_facecolor('#FFF9C4')
                ax1.patch.set_alpha(0.4)
            elif cycle == "下行":
                ax1.set_facecolor('#FFEBEE')
                ax1.patch.set_alpha(0.4)
        self._apply_daily_kline_ax(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels=False, show_support_resistance=show_support_resistance)
        fig.tight_layout()
        return fig

    def _build_daily_kline_zoom_figure(self, kline_data, stock_name, indicator_keys):
        """放大窗口:主图 K 线 + 2~4 个副图指标(VOL/MACD/WR2/KDJ/BOLL)。"""
        from matplotlib import gridspec
        from matplotlib.figure import Figure
        allowed = {"VOL", "MACD", "WR2", "KDJ", "BOLL"}
        keys = [k for k in (indicator_keys or []) if k in allowed]
        if len(keys) < 2 or len(keys) > 4:
            raise ValueError("副图指标须选 2~4 个")
        ni = len(keys)
        data = kline_data["data"]
        n = len(data)
        dates = list(range(n))
        opens = data["开盘"].values
        closes = data["收盘"].values
        highs = data["最高"].values
        lows = data["最低"].values
        if "成交量" in data.columns:
            vol = data["成交量"].values.astype(float)
        else:
            vol = np.zeros(n, dtype=float)
        fig_h = 7.0 + 2.15 * ni
        fig = Figure(figsize=(14, fig_h), dpi=100)
        # 根据情绪周期设置背景颜色
        emotion_cycle = getattr(self, 'emotion_cycle_var', None)
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                fig.patch.set_facecolor('#E8F5E9')
                fig.patch.set_alpha(0.6)
            elif cycle == "震荡":
                fig.patch.set_facecolor('#FFF9C4')
                fig.patch.set_alpha(0.6)
            elif cycle == "下行":
                fig.patch.set_facecolor('#FFEBEE')
                fig.patch.set_alpha(0.6)
        ratios = [3.2] + [1.0] * ni
        gs = gridspec.GridSpec(1 + ni, 1, figure=fig, height_ratios=ratios, hspace=0.14)
        ax_main = fig.add_subplot(gs[0, 0])
        # 设置主图背景颜色
        if emotion_cycle:
            cycle = emotion_cycle.get()
            if cycle == "上行":
                ax_main.set_facecolor('#E8F5E9')
                ax_main.patch.set_alpha(0.4)
            elif cycle == "震荡":
                ax_main.set_facecolor('#FFF9C4')
                ax_main.patch.set_alpha(0.4)
            elif cycle == "下行":
                ax_main.set_facecolor('#FFEBEE')
                ax_main.patch.set_alpha(0.4)
        self._apply_daily_kline_ax(ax_main, kline_data, stock_name, show_zoom_hint=False, hide_x_labels=True, show_support_resistance=True)
        for row, key in enumerate(keys, start=1):
            ax_sub = fig.add_subplot(gs[row, 0], sharex=ax_main)
            # 设置副图背景颜色
            if emotion_cycle:
                cycle = emotion_cycle.get()
                if cycle == "上行":
                    ax_sub.set_facecolor('#E8F5E9')
                    ax_sub.patch.set_alpha(0.3)
                elif cycle == "震荡":
                    ax_sub.set_facecolor('#FFF9C4')
                    ax_sub.patch.set_alpha(0.3)
                elif cycle == "下行":
                    ax_sub.set_facecolor('#FFEBEE')
                    ax_sub.patch.set_alpha(0.3)
            self._plot_kline_zoom_subpanel(ax_sub, key, dates, opens, closes, highs, lows, vol)
            if row < ni:
                ax_sub.tick_params(axis="x", labelbottom=False)
        fig.tight_layout()
        return fig

    def _show_daily_kline_zoom(self, kline_data, stock_name):
        """双击日K线:最大化窗口 + 可选 2~4 个副图指标。"""
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            win = self._toplevel(self.root)
            win.title(f"{stock_name} - 日K线(放大)")
            try:
                win.state("zoomed")
            except Exception:
                try:
                    win.attributes("-zoomed", True)
                except Exception:
                    win.geometry("1200x900")
            top = ttk.Frame(win, padding=4)
            top.pack(fill=tk.X)
            # 添加只显示主图的选项
            main_only_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(top, text="只显示主图", variable=main_only_var).pack(side=tk.LEFT, padx=(0, 10))
            # 添加显示支撑/压力线的选项
            show_support_resistance_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(top, text="显示支撑/压力线", variable=show_support_resistance_var).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(top, text="副图指标(选 2~4 项后点「应用」):", font=("Microsoft YaHei", 10)).pack(
                side=tk.LEFT, padx=(0, 6)
            )
            opt_specs = [
                ("VOL", "VOL"),
                ("MACD", "MACD"),
                ("WR2", "WR(2)"),
                ("KDJ", "KDJ"),
                ("BOLL", "BOLL"),
            ]
            ivars = {}
            for code, _lbl in opt_specs:
                ivars[code] = tk.BooleanVar(value=code in ("VOL", "MACD", "KDJ"))
            for code, lbl in opt_specs:
                ttk.Checkbutton(top, text=lbl, variable=ivars[code]).pack(side=tk.LEFT, padx=3)
            chart_inner = None
            status_var = tk.StringVar(value="")
            def _collect_keys():
                return [c for c, _ in opt_specs if ivars[c].get()]
            def redraw():
                if main_only_var.get():
                    # 只显示主图
                    for w in chart_inner.winfo_children():
                        w.destroy()
                    try:
                        fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(14, 9), show_support_resistance=show_support_resistance_var.get())
                        canvas = FigureCanvasTkAgg(fig, chart_inner)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        status_var.set("当前显示:只显示主图")
                    except Exception as ex:
                        messagebox.showerror("错误", f"绘制失败: {ex}", parent=win)
                else:
                    # 显示主图+副图
                    sel = _collect_keys()
                    if len(sel) < 2 or len(sel) > 4:
                        messagebox.showwarning(
                            "提示",
                            "请勾选 2~4 个副图指标(VOL、MACD、WR(2)、KDJ、BOLL)。",
                            parent=win,
                        )
                        return
                    for w in chart_inner.winfo_children():
                        w.destroy()
                    try:
                        # 临时修改_apply_daily_kline_ax的调用,添加show_support_resistance参数
                        # 由于_build_daily_kline_zoom_figure没有参数,我们需要在内部修改
                        # 这里使用一个临时变量来传递参数
                        original_apply = self._apply_daily_kline_ax
                        def temp_apply(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                            return original_apply(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels, show_support_resistance=show_support_resistance_var.get())
                        self._apply_daily_kline_ax = temp_apply
                        fig = self._build_daily_kline_zoom_figure(kline_data, stock_name, sel)
                        canvas = FigureCanvasTkAgg(fig, chart_inner)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        status_var.set(f"当前副图:{' + '.join(sel)}")
                        # 恢复原始函数
                        self._apply_daily_kline_ax = original_apply
                    except Exception as ex:
                        # 恢复原始函数
                        if hasattr(self, '_apply_daily_kline_ax'):
                            self._apply_daily_kline_ax = original_apply
                        messagebox.showerror("错误", f"绘制失败: {ex}", parent=win)
            ttk.Button(top, text="应用", command=redraw).pack(side=tk.LEFT, padx=(10, 4))
            current_stock_data = {'kline_data': kline_data, 'stock_name': stock_name}
            def calculate_kelly():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_kelly_position(data, name)
                    self._show_kelly_result_dialog(result, name, win)
                except Exception as e:
                    messagebox.showerror("错误", f"凯利计算失败: {e}", parent=win)
            ttk.Button(top, text="凯利计算", command=calculate_kelly).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_sharpe():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_sharpe_ratio(data, name)
                    self._show_analysis_result_dialog(result, name, "夏普比率分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"夏普比率计算失败: {e}", parent=win)
            ttk.Button(top, text="夏普比率", command=calculate_sharpe).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_mean_reversion():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_mean_reversion(data, name)
                    self._show_analysis_result_dialog(result, name, "均值回归分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"均值回归计算失败: {e}", parent=win)
            ttk.Button(top, text="均值回归", command=calculate_mean_reversion).pack(side=tk.LEFT, padx=(10, 4))
            def predict_buy_points():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_buy_point_prediction(data, name)
                    self._show_buy_point_prediction_dialog(result, name, win)
                except Exception as e:
                    messagebox.showerror("错误", f"买点预测失败: {e}", parent=win)
            ttk.Button(top, text="买点预测", command=predict_buy_points).pack(side=tk.LEFT, padx=(10, 4))
            # 第二行按钮
            top2 = ttk.Frame(win)
            top2.pack(fill=tk.X, pady=(5, 0))
            def calculate_trend_tracking():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_trend_tracking(data, name)
                    self._show_analysis_result_dialog(result, name, "趋势跟踪分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"趋势跟踪计算失败: {e}", parent=win)
            ttk.Button(top2, text="趋势跟踪", command=calculate_trend_tracking).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_dragon_head():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_dragon_head(data, name)
                    self._show_analysis_result_dialog(result, name, "龙头战法分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"龙头战法计算失败: {e}", parent=win)
            ttk.Button(top2, text="龙头战法", command=calculate_dragon_head).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_overbought_bounce():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_overbought_bounce(data, name)
                    self._show_analysis_result_dialog(result, name, "超跌反弹分析", win)
                except Exception as e:
                    messagebox.showerror("错误", f"超跌反弹计算失败: {e}", parent=win)
            ttk.Button(top2, text="超跌反弹", command=calculate_overbought_bounce).pack(side=tk.LEFT, padx=(10, 4))
            def calculate_multi_factor():
                try:
                    data = current_stock_data['kline_data']
                    name = current_stock_data['stock_name']
                    result = self._calculate_multi_factor(data, name)
                    self._show_analysis_result_dialog(result, name, "多因子评分", win)
                except Exception as e:
                    messagebox.showerror("错误", f"多因子评分计算失败: {e}", parent=win)
            ttk.Button(top2, text="多因子评分", command=calculate_multi_factor).pack(side=tk.LEFT, padx=(10, 4))
            def fetch_stock_info():
                try:
                    name = current_stock_data['stock_name']
                    result = self._fetch_stock_info(name)
                    self._show_stock_info_dialog(result, name, win)
                except Exception as e:
                    messagebox.showerror("错误", f"信息获取失败: {e}", parent=win)
            ttk.Button(top2, text="信息获取", command=fetch_stock_info).pack(side=tk.LEFT, padx=(10, 4))
            # 🦅 游资心法全解按钮
            def open_hotmoney_analysis():
                try:
                    self._open_hotmoney_single_dialog(win, current_stock_data)
                except Exception as e:
                    messagebox.showerror("错误", f"游资心法打开失败: {e}", parent=win)
            ttk.Button(top2, text="🦅 游资心法", command=open_hotmoney_analysis).pack(side=tk.LEFT, padx=(10, 4))
            # 添加股票输入下拉框和查询按钮
            stock_frame = ttk.Frame(top2, padding=2)
            stock_frame.pack(side=tk.LEFT, padx=(20, 0))
            ttk.Label(stock_frame, text="股票:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0, 5))
            # 股票输入框(支持下拉和手动输入)
            stock_var = tk.StringVar(value="")
            stock_combo = ttk.Combobox(stock_frame, textvariable=stock_var, width=20, font=("TkDefaultFont", 10), state="normal")
            # 加载股票数据到下拉框
            def load_stock_data():
                try:
                    # 获取持仓股(group_idx=1)和龙头股(group_idx=2)中的股票
                    all_holdings = self._get_all_holding_stocks()
                    # 筛选持仓股和龙头股
                    stock_items = []
                    seen_codes = set()
                    for stock_name, stock_code, group_idx, pos_idx in all_holdings:
                        if stock_code not in seen_codes:
                            seen_codes.add(stock_code)
                            if group_idx == 1:
                                stock_items.append(f"{stock_name}({stock_code})[持仓]")
                            elif group_idx == 2:
                                stock_items.append(f"{stock_name}({stock_code})[龙头股]")
                    # 如果没有数据,使用默认热门股票
                    if not stock_items:
                        hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                        for name, code in hot_stocks[:30]:
                            if code not in seen_codes:
                                stock_items.append(f"{name}({code})[热门]")
                    stock_combo['values'] = stock_items
                except Exception as e:
                    print(f"加载股票数据失败: {e}")
                    # 使用默认热门股票
                    hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                    stock_items = [f"{name}({code})[热门]" for name, code in hot_stocks[:30]]
                    stock_combo['values'] = stock_items
            # 加载股票数据
            load_stock_data()
            stock_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 标签股下拉框
            tab_stock_frame = ttk.Frame(top, padding=2)
            tab_stock_frame.pack(side=tk.LEFT, padx=(10, 0))
            ttk.Label(tab_stock_frame, text="标签股:", font=("Microsoft YaHei", 10)).pack(side=tk.LEFT, padx=(0, 5))
            # 标签股输入框
            tab_stock_var = tk.StringVar(value="")
            tab_stock_combo = ttk.Combobox(tab_stock_frame, textvariable=tab_stock_var, width=20, font=("TkDefaultFont", 10), state="normal")
            # 加载标签股数据
            def load_tab_stock_data():
                try:
                    # 获取同花顺标签页(group_idx=6)的股票
                    all_holdings = self._get_all_holding_stocks()
                    # 筛选同花顺标签页的股票
                    tab_stock_items = []
                    seen_codes = set()
                    for stock_name, stock_code, group_idx, pos_idx in all_holdings:
                        if group_idx == 6 and stock_code not in seen_codes:
                            seen_codes.add(stock_code)
                            tab_stock_items.append(f"{stock_name}({stock_code})[同花顺]")
                    # 如果没有数据,使用默认热门股票
                    if not tab_stock_items:
                        hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                        for name, code in hot_stocks[:30]:
                            if code not in seen_codes:
                                tab_stock_items.append(f"{name}({code})[热门]")
                    tab_stock_combo['values'] = tab_stock_items
                except Exception as e:
                    print(f"加载标签股数据失败: {e}")
                    # 使用默认热门股票
                    hot_stocks = get_news_stocks_merged_recent_days(ndays=3)
                    tab_stock_items = [f"{name}({code})[热门]" for name, code in hot_stocks[:30]]
                    tab_stock_combo['values'] = tab_stock_items
            # 标签股选择事件处理
            def on_tab_stock_select(event):
                tab_stock_input = tab_stock_var.get().strip()
                if tab_stock_input:
                    # 提取股票代码
                    stock_code = None
                    stock_name = None
                    # 从输入中提取股票代码
                    code_match = re.search(r'\d{6}', tab_stock_input)
                    if code_match:
                        stock_code = code_match.group(0)
                    else:
                        # 从输入中提取股票名称
                        name_match = re.search(r'([^()]+)', tab_stock_input)
                        if name_match:
                            stock_name = name_match.group(1).strip()
                        else:
                            stock_name = tab_stock_input
                    try:
                        # 获取股票K线数据
                        if stock_code:
                            kline_data = self._get_daily_kline_data_tushare(stock_code)
                            stock_name = get_stock_name_by_code(stock_code)
                        else:
                            stock_code = get_stock_code_by_name(stock_name)
                            kline_data = self._get_daily_kline_data_tushare(stock_code)
                        if kline_data:
                            # 重新绘制K线图
                            for w in chart_inner.winfo_children():
                                w.destroy()
                            if main_only_var.get():
                                fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(14, 9), show_support_resistance=show_support_resistance_var.get())
                            else:
                                sel = _collect_keys()
                                # 临时修改_apply_daily_kline_ax的调用,添加show_support_resistance参数
                                original_apply = self._apply_daily_kline_ax
                                def temp_apply(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                                    return original_apply(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels, show_support_resistance=show_support_resistance_var.get())
                                self._apply_daily_kline_ax = temp_apply
                                fig = self._build_daily_kline_zoom_figure(kline_data, stock_name, sel)
                                # 恢复原始函数
                                self._apply_daily_kline_ax = original_apply
                            canvas = FigureCanvasTkAgg(fig, chart_inner)
                            canvas.draw()
                            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                            if main_only_var.get():
                                status_var.set("当前显示:只显示主图")
                            else:
                                status_var.set(f"当前副图:{' + '.join(sel)}")
                            # 更新窗口标题
                            win.title(f"{stock_name} - 日K线(放大)")
                            # 更新当前股票数据,供凯利计算等按钮使用
                            current_stock_data['kline_data'] = kline_data
                            current_stock_data['stock_name'] = stock_name
                        else:
                            messagebox.showwarning("提示", "无法获取股票K线数据", parent=win)
                    except Exception as e:
                        messagebox.showerror("错误", f"获取股票数据失败: {e}", parent=win)
            # 绑定标签股下拉框选择事件
            tab_stock_combo.bind("<<ComboboxSelected>>", on_tab_stock_select)
            # 加载标签股数据
            load_tab_stock_data()
            tab_stock_combo.pack(side=tk.LEFT, padx=(0, 5))
            # 查询按钮
            def query_stock():
                stock_input = stock_var.get().strip()
                tab_stock_input = tab_stock_var.get().strip()
                # 优先使用标签股输入,然后是股票输入
                input_to_use = tab_stock_input if tab_stock_input else stock_input
                if not input_to_use:
                    messagebox.showwarning("提示", "请输入股票名称或代码", parent=win)
                    return
                # 提取股票代码
                stock_code = None
                stock_name = None
                # 从输入中提取股票代码
                code_match = re.search(r'\d{6}', input_to_use)
                if code_match:
                    stock_code = code_match.group(0)
                else:
                    # 从输入中提取股票名称
                    name_match = re.search(r'([^()]+)', input_to_use)
                    if name_match:
                        stock_name = name_match.group(1).strip()
                    else:
                        stock_name = input_to_use
                try:
                    # 获取股票K线数据
                    if stock_code:
                        kline_data = self._get_daily_kline_data_tushare(stock_code)
                        stock_name = get_stock_name_by_code(stock_code)
                    else:
                        stock_code = get_stock_code_by_name(stock_name)
                        kline_data = self._get_daily_kline_data_tushare(stock_code)
                    if not kline_data:
                        messagebox.showwarning("提示", "无法获取股票K线数据", parent=win)
                        return
                    # 重新绘制K线图
                    for w in chart_inner.winfo_children():
                        w.destroy()
                    if main_only_var.get():
                        fig = self._build_daily_kline_figure(kline_data, stock_name, figsize=(14, 9), show_support_resistance=show_support_resistance_var.get())
                    else:
                        sel = _collect_keys()
                        # 临时修改_apply_daily_kline_ax的调用,添加show_support_resistance参数
                        original_apply = self._apply_daily_kline_ax
                        def temp_apply(ax1, kline_data, stock_name, show_zoom_hint=True, hide_x_labels=False, show_support_resistance=True):
                            return original_apply(ax1, kline_data, stock_name, show_zoom_hint, hide_x_labels, show_support_resistance=show_support_resistance_var.get())
                        self._apply_daily_kline_ax = temp_apply
                        fig = self._build_daily_kline_zoom_figure(kline_data, stock_name, sel)
                        # 恢复原始函数
                        self._apply_daily_kline_ax = original_apply
                    canvas = FigureCanvasTkAgg(fig, chart_inner)
                    canvas.draw()
                    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                    if main_only_var.get():
                        status_var.set("当前显示:只显示主图")
                    else:
                        status_var.set(f"当前副图:{' + '.join(sel)}")
                    # 更新窗口标题
                    win.title(f"{stock_name} - 日K线(放大)")
                    # 更新当前股票数据,供凯利计算等按钮使用
                    current_stock_data['kline_data'] = kline_data
                    current_stock_data['stock_name'] = stock_name
                except Exception as e:
                    messagebox.showerror("错误", f"获取股票数据失败: {e}", parent=win)
            ttk.Button(stock_frame, text="查询", command=query_stock).pack(side=tk.LEFT, padx=(0, 10))
            # 图表框架 - 在所有按钮之后创建
            chart_fr = ttk.Frame(win, padding=(4, 0, 4, 4))
            chart_fr.pack(fill=tk.BOTH, expand=True)
            chart_inner = ttk.Frame(chart_fr)
            chart_inner.pack(fill=tk.BOTH, expand=True)
            # 添加快速切换按钮
            quick_frame = ttk.Frame(top, padding=2)
            quick_frame.pack(side=tk.LEFT, padx=(10, 0))
            def switch_to_tab_stock(tab_name):
                try:
                    import re
                    import sqlite3
                    from collections import Counter
                    global STOCK_CODES_DICT
                    db_path = os.path.join(D_DB_DIR, "stock_analysis.db")
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    # 确保股票数据已加载
                    load_stock_names()
                    # 从该标签页获取股票
                    cursor.execute("SELECT content FROM news_info WHERE tab_name = ? LIMIT 1", (tab_name,))
                    row = cursor.fetchone()
                    conn.close()
                    if row:
                        content = row[0]
                        # 提取股票代码
                        codes = re.findall(r"\d{6}", content)
                        # 检查代码是否在STOCK_CODES_DICT中
                        valid = [c for c in codes if c in STOCK_CODES_DICT]
                        # 按出现频次排序
                        counter = Counter(valid)
                        most_common = counter.most_common(1)
                        if most_common:
                            stock_code = most_common[0][0]
                            stock_name = STOCK_CODES_DICT[stock_code]
                            # 更新标签股下拉框
                            tab_stock_var.set(f"{stock_name} ({stock_code})")
                            # 执行查询
                            query_stock()
                except Exception as e:
                    print(f"切换到标签股失败: {e}")
            ttk.Button(quick_frame, text="咨询股", command=lambda: switch_to_tab_stock("咨询")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="同花顺", command=lambda: switch_to_tab_stock("同花顺")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="Main", command=lambda: switch_to_tab_stock("Main")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="龙头股", command=lambda: switch_to_tab_stock("龙头股")).pack(side=tk.LEFT, padx=3)
            ttk.Button(quick_frame, text="15Min", command=lambda: switch_to_tab_stock("15Min")).pack(side=tk.LEFT, padx=3)
            lbl_st = ttk.Label(top, textvariable=status_var, font=("Microsoft YaHei", 9), foreground="gray")
            lbl_st.pack(side=tk.LEFT, padx=(8, 0))
            redraw()
            # 延迟自动打开凯利计算对话框,避免阻塞主界面
            # 注意:此功能暂时禁用,待主界面稳定后再启用
            # def delayed_kelly():
            #     try:
            #         result = self._calculate_kelly_position(kline_data, stock_name)
            #         self._show_kelly_result_dialog(result, stock_name, win)
            #     except Exception as e:
            #         pass
            # win.after(500, delayed_kelly)
        except Exception as e:
            messagebox.showerror("错误", f"打开放大K线失败: {e}", parent=self.root)

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

    def _show_stock_detail_direct(self, stock_name, stock_code, group_index=1):
        """直接显示股票详情(不依赖持仓列表)"""
        # 创建临时的持仓股列表,只包含这一个股票
        temp_holding_stocks = [(stock_name, stock_code)]
        temp_index = 0
        # 临时保存原始的_get_holding_group_data方法
        original_get_holding_group_data = self._get_holding_group_data
        # 创建一个临时的_get_holding_group_data方法
        def temp_get_holding_group_data(g_idx):
            # 返回临时数据
            return temp_holding_stocks, [], {}, {}
        # 临时替换方法
        self._get_holding_group_data = temp_get_holding_group_data
        try:
            # 调用原有的显示函数
            self._show_holding_detail(temp_index, group_index)
        finally:
            # 恢复原始方法
            self._get_holding_group_data = original_get_holding_group_data


__all__ = ["StockDetailMixin"]

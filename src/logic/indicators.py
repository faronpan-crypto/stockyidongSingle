# 迁移自 stockyidong mac003.py ranges=[(1714, 1732), (1733, 1759), (1760, 1774), (1775, 1788), (1789, 1831)]
import numpy as np
import pandas as pd

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    try:
        # 计算EMA
        def ema(data, period):
            alpha = 2.0 / (period + 1)
            ema_values = np.zeros_like(data)
            ema_values[0] = data[0]
            for i in range(1, len(data)):
                ema_values[i] = alpha * data[i] + (1 - alpha) * ema_values[i-1]
            return ema_values
        ema_fast = ema(prices, fast)
        ema_slow = ema(prices, slow)
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line[-1], signal_line[-1], histogram[-1]
    except Exception:
        return 0, 0, 0

def calculate_kdj(high_prices, low_prices, close_prices, n=9):
    """计算KDJ指标"""
    try:
        if len(high_prices) < n:
            return 50, 50, 50
        # 计算RSV
        rsv_values = []
        for i in range(n-1, len(high_prices)):
            high_n = max(high_prices[i-n+1:i+1])
            low_n = min(low_prices[i-n+1:i+1])
            if high_n == low_n:
                rsv = 50
            else:
                rsv = ((close_prices[i] - low_n) / (high_n - low_n)) * 100
            rsv_values.append(rsv)
        if not rsv_values:
            return 50, 50, 50
        # 计算K、D、J值
        k = 50
        d = 50
        for rsv in rsv_values:
            k = (2/3) * k + (1/3) * rsv
            d = (2/3) * d + (1/3) * k
        j = 3 * k - 2 * d
        return k, d, j
    except Exception:
        return 50, 50, 50

def calculate_wr(high_prices, low_prices, close_prices, n=14):
    """计算WR指标"""
    try:
        if len(high_prices) < n:
            return 50
        high_n = max(high_prices[-n:])
        low_n = min(low_prices[-n:])
        close_current = close_prices[-1]
        if high_n == low_n:
            wr = 50
        else:
            wr = ((high_n - close_current) / (high_n - low_n)) * 100
        return wr
    except Exception:
        return 50

def calculate_bias(prices, n=6):
    """计算BIAS指标"""
    try:
        if len(prices) < n:
            return 0
        ma_n = np.mean(prices[-n:])
        close_current = prices[-1]
        if ma_n == 0:
            bias = 0
        else:
            bias = ((close_current - ma_n) / ma_n) * 100
        return bias
    except Exception:
        return 0

def analyze_technical_position(indicators):
    """分析技术指标位置"""
    analysis = []
    # MACD分析
    if indicators['macd'] > indicators['macd_signal']:
        if indicators['macd_hist'] > 0:
            analysis.append("MACD: 金叉向上,多头趋势")
        else:
            analysis.append("MACD: 金叉向下,可能转弱")
    else:
        if indicators['macd_hist'] < 0:
            analysis.append("MACD: 死叉向下,空头趋势")
        else:
            analysis.append("MACD: 死叉向上,可能转强")
    # KDJ分析
    k, d, j = indicators['kdj_k'], indicators['kdj_d'], indicators['kdj_j']
    if k > 80 and d > 80:
        analysis.append("KDJ: 超买区域,注意回调风险")
    elif k < 20 and d < 20:
        analysis.append("KDJ: 超卖区域,可能反弹机会")
    elif k > d and j > k:
        analysis.append("KDJ: 金叉向上,短期看涨")
    elif k < d and j < k:
        analysis.append("KDJ: 死叉向下,短期看跌")
    else:
        analysis.append("KDJ: 中性区域,震荡整理")
    # WR分析
    wr = indicators['wr']
    if wr > 80:
        analysis.append("WR: 超卖区域,可能反弹")
    elif wr < 20:
        analysis.append("WR: 超买区域,注意回调")
    else:
        analysis.append("WR: 中性区域,正常波动")
    # BIAS分析
    bias = indicators['bias']
    if bias > 5:
        analysis.append("BIAS: 正乖离较大,注意回调")
    elif bias < -5:
        analysis.append("BIAS: 负乖离较大,可能反弹")
    else:
        analysis.append("BIAS: 乖离正常,趋势稳定")
    return analysis

__all__ = ['analyze_technical_position', 'calculate_bias', 'calculate_kdj', 'calculate_macd', 'calculate_wr']

"""
压支Skill (Support/Resistance Skill)
======================================
计算股票的支撑位和压力位，用于K线图显示和交易信号生成。

算法说明：
1. 趋势判断：基于MA20斜率或价格趋势
2. 枢点检测：识别局部高点和低点
3. 趋势线绘制：
   - 上升趋势 → 连接低点得到支撑线
   - 下降趋势 → 连接高点得到压力线
4. 水平支撑压力：前期高低点、整数关口、均线

使用方法：
    from support_resistance_skill import SupportResistanceCalculator
    
    calculator = SupportResistanceCalculator()
    result = calculator.calculate(df, ma_values)
    
    # result包含：
    # - support_lines: 支撑线列表 [{price, slope, start_idx, end_idx}]
    # - resistance_lines: 压力线列表
    # - horizontal_support: 水平支撑位 [price1, price2, ...]
    # - horizontal_resistance: 水平压力位
    # - near_support: 是否接近支撑
    # - near_resistance: 是否接近压力
"""


import numpy as np
import pandas as pd


class SupportResistanceCalculator:
    """支撑压力位计算器"""
    
    def __init__(self, threshold_pct: float = 2.0):
        """
        Args:
            threshold_pct: 判断"接近"支撑/压力的阈值（百分比）
        """
        self.threshold_pct = threshold_pct
    
    def calculate(self, kline_data: dict, ma_values: dict) -> dict:
        """
        计算支撑压力位
        
        Args:
            kline_data: {
                'data': DataFrame with columns [开盘, 最高, 最低, 收盘],
                'ma_values': {'ma5': [], 'ma10': [], 'ma20': []}
            }
            ma_values: 均线数据（可选，如果kline_data中已包含）
        
        Returns:
            dict: {
                'close': 最新收盘价,
                'support_price': 动态支撑线价格（上升趋势）,
                'resistance_price': 动态压力线价格（下降趋势）,
                'support_lines': [...],  # 所有支撑线
                'resistance_lines': [...],  # 所有压力线
                'horizontal_support': [...],  # 水平支撑位
                'horizontal_resistance': [...],  # 水平压力位
                'near_support': bool,  # 是否接近支撑
                'near_resistance': bool,  # 是否接近压力
            }
        """
        result = {
            'close': None,
            'support_price': None,
            'resistance_price': None,
            'support_lines': [],
            'resistance_lines': [],
            'horizontal_support': [],
            'horizontal_resistance': [],
            'near_support': False,
            'near_resistance': False,
        }
        
        try:
            data = kline_data['data']
            ma_vals = kline_data.get('ma_values', ma_values)
            
            n = len(data)
            if n < 3:
                return result
            
            closes = data['收盘'].values
            highs = data['最高'].values
            lows = data['最低'].values
            result['close'] = float(closes[-1])
            
            # 1. 趋势判断
            uptrend, downtrend = self._detect_trend(closes, ma_vals)
            
            # 2. 枢点检测
            piv_lo = self._find_pivot_lows(lows)
            piv_hi = self._find_pivot_highs(highs)
            
            # 3. 动态支撑/压力线（趋势线）
            if uptrend and not downtrend:
                result['support_price'], result['support_lines'] = self._calc_support_line(
                    lows, piv_lo, n
                )
            elif downtrend and not uptrend:
                result['resistance_price'], result['resistance_lines'] = self._calc_resistance_line(
                    highs, piv_hi, n
                )
            
            # 4. 水平支撑压力位
            result['horizontal_support'] = self._calc_horizontal_support(lows, closes, ma_vals, n)
            result['horizontal_resistance'] = self._calc_horizontal_resistance(highs, closes, ma_vals, n)
            
            # 5. 判断是否接近支撑/压力
            result['near_support'] = self._check_near_support(
                result['close'], result['support_price'], result['horizontal_support']
            )
            result['near_resistance'] = self._check_near_resistance(
                result['close'], result['resistance_price'], result['horizontal_resistance']
            )
            
        except Exception as e:
            print(f"支撑压力计算失败: {e}")
        
        return result
    
    def _detect_trend(self, closes: np.ndarray, ma_values: dict) -> tuple[bool, bool]:
        """判断趋势：上升/下降"""
        uptrend = False
        downtrend = False
        
        if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
            m20 = np.asarray(ma_values['ma20'], dtype=float)
            uptrend = bool(m20[-1] > m20[-6])
            downtrend = bool(m20[-1] < m20[-6])
        elif len(closes) >= 12:
            uptrend = bool(closes[-1] > closes[-11])
            downtrend = bool(closes[-1] < closes[-11])
        
        return uptrend, downtrend
    
    def _find_pivot_lows(self, lows: np.ndarray) -> list[int]:
        """找局部低点（枢点）"""
        pivots = []
        n = len(lows)
        for i in range(1, n - 1):
            if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]:
                pivots.append(i)
        return pivots
    
    def _find_pivot_highs(self, highs: np.ndarray) -> list[int]:
        """找局部高点（枢点）"""
        pivots = []
        n = len(highs)
        for i in range(1, n - 1):
            if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]:
                pivots.append(i)
        return pivots
    
    def _calc_support_line(self, lows: np.ndarray, piv_lo: list[int], n: int) -> tuple[float | None, list[dict]]:
        """
        计算支撑线（上升趋势中连接低点）
        
        Returns:
            (current_support_price, support_lines_list)
        """
        support_price = None
        support_lines = []
        
        if len(piv_lo) < 2:
            return support_price, support_lines
        
        # 取最后2-3个低点
        cand = piv_lo[-3:] if len(piv_lo) >= 3 else piv_lo[-2:]
        
        # 检查是否递增（更高的低点 = 上升趋势）
        ok = None
        if len(cand) >= 3 and lows[cand[-1]] > lows[cand[-2]] > lows[cand[-3]]:
            ok = (cand[-3], cand[-1])
        elif len(cand) >= 2 and lows[cand[-1]] > lows[cand[-2]]:
            ok = (cand[-2], cand[-1])
        
        if ok:
            i0, i1 = ok
            x0, y0 = float(i0), float(lows[i0])
            x1, y1 = float(i1), float(lows[i1])
            
            if x1 != x0:
                # 计算斜率
                slope = (y1 - y0) / (x1 - x0)
                
                # 延伸到现在
                support_price = float(y0 + slope * (n - 1 - x0))
                
                # 保存线信息
                support_lines.append({
                    'start_idx': i0,
                    'end_idx': i1,
                    'start_price': y0,
                    'end_price': y1,
                    'slope': slope,
                    'current_price': support_price
                })
        
        return support_price, support_lines
    
    def _calc_resistance_line(self, highs: np.ndarray, piv_hi: list[int], n: int) -> tuple[float | None, list[dict]]:
        """
        计算压力线（下降趋势中连接高点）
        
        Returns:
            (current_resistance_price, resistance_lines_list)
        """
        resistance_price = None
        resistance_lines = []
        
        if len(piv_hi) < 2:
            return resistance_price, resistance_lines
        
        # 取最后2-3个高点
        cand = piv_hi[-3:] if len(piv_hi) >= 3 else piv_hi[-2:]
        
        # 检查是否递减（更低的高点 = 下降趋势）
        ok = None
        if len(cand) >= 3 and highs[cand[-1]] < highs[cand[-2]] < highs[cand[-3]]:
            ok = (cand[-3], cand[-1])
        elif len(cand) >= 2 and highs[cand[-1]] < highs[cand[-2]]:
            ok = (cand[-2], cand[-1])
        
        if ok:
            i0, i1 = ok
            x0, y0 = float(i0), float(highs[i0])
            x1, y1 = float(i1), float(highs[i1])
            
            if x1 != x0:
                # 计算斜率
                slope = (y1 - y0) / (x1 - x0)
                
                # 延伸到现在
                resistance_price = float(y0 + slope * (n - 1 - x0))
                
                # 保存线信息
                resistance_lines.append({
                    'start_idx': i0,
                    'end_idx': i1,
                    'start_price': y0,
                    'end_price': y1,
                    'slope': slope,
                    'current_price': resistance_price
                })
        
        return resistance_price, resistance_lines
    
    def _calc_horizontal_support(self, lows: np.ndarray, closes: np.ndarray, ma_values: dict, n: int) -> list[float]:
        """计算水平支撑位（前期低点、整数关口、均线）"""
        support_levels = []
        
        # 1. 近期低点（最近20天的低点）
        if len(lows) >= 20:
            recent_low = float(np.min(lows[-20:]))
            support_levels.append(recent_low)
        
        # 2. 整数关口
        current_price = float(closes[-1])
        integer_levels = self._find_integer_levels(current_price, lows)
        support_levels.extend(integer_levels)
        
        # 3. 均线支撑
        for ma_name in ['ma5', 'ma10', 'ma20', 'ma60']:
            if ma_name in ma_values and len(ma_values[ma_name]) > 0:
                ma_val = float(ma_values[ma_name][-1])
                # 只有均线在下方才是支撑
                if ma_val < current_price:
                    support_levels.append(ma_val)
        
        # 去重并排序
        support_levels = sorted(list(set([round(x, 2) for x in support_levels if x > 0])))
        
        return support_levels
    
    def _calc_horizontal_resistance(self, highs: np.ndarray, closes: np.ndarray, ma_values: dict, n: int) -> list[float]:
        """计算水平压力位（前期高点、整数关口、均线）"""
        resistance_levels = []
        
        # 1. 近期高点（最近20天的高点）
        if len(highs) >= 20:
            recent_high = float(np.max(highs[-20:]))
            resistance_levels.append(recent_high)
        
        # 2. 整数关口
        current_price = float(closes[-1])
        integer_levels = self._find_integer_levels(current_price, highs, is_support=False)
        resistance_levels.extend(integer_levels)
        
        # 3. 均线压力
        for ma_name in ['ma5', 'ma10', 'ma20', 'ma60']:
            if ma_name in ma_values and len(ma_values[ma_name]) > 0:
                ma_val = float(ma_values[ma_name][-1])
                # 只有均线在上方才是压力
                if ma_val > current_price:
                    resistance_levels.append(ma_val)
        
        # 去重并排序
        resistance_levels = sorted(list(set([round(x, 2) for x in resistance_levels if x > 0])))
        
        return resistance_levels
    
    def _find_integer_levels(self, current_price: float, price_array: np.ndarray, is_support: bool = True) -> list[float]:
        """找整数关口"""
        levels = []
        
        # 根据价格范围确定整数步长
        if current_price < 5:
            step = 0.5
        elif current_price < 20:
            step = 1.0
        elif current_price < 100:
            step = 5.0
        else:
            step = 10.0
        
        # 生成整数关口
        base = int(current_price / step) * step
        
        if is_support:
            # 支撑：当前价格下方的整数关口
            for i in range(-5, 1):
                level = base + i * step
                if level > 0 and level < current_price:
                    levels.append(level)
        else:
            # 压力：当前价格上方的整数关口
            for i in range(1, 6):
                level = base + i * step
                if level > current_price:
                    levels.append(level)
        
        return levels
    
    def _check_near_support(self, close: float, dynamic_support: float | None, horizontal_support: list[float]) -> bool:
        """判断是否接近支撑位"""
        if close <= 0:
            return False
        
        # 检查动态支撑线
        if dynamic_support is not None and dynamic_support > 0:
            if abs(close - dynamic_support) / dynamic_support * 100.0 <= self.threshold_pct:
                return True
        
        # 检查水平支撑位
        for sup in horizontal_support:
            if sup > 0 and abs(close - sup) / sup * 100.0 <= self.threshold_pct:
                return True
        
        return False
    
    def _check_near_resistance(self, close: float, dynamic_resistance: float | None, horizontal_resistance: list[float]) -> bool:
        """判断是否接近压力位"""
        if close <= 0:
            return False
        
        # 检查动态压力线
        if dynamic_resistance is not None and dynamic_resistance > 0:
            if abs(close - dynamic_resistance) / dynamic_resistance * 100.0 <= self.threshold_pct:
                return True
        
        # 检查水平压力位
        for res in horizontal_resistance:
            if res > 0 and abs(close - res) / res * 100.0 <= self.threshold_pct:
                return True
        
        return False


def calculate_support_resistance(df: pd.DataFrame, ma_periods: list[int] = [5, 10, 20, 60]) -> dict:
    """
    便捷函数：直接计算支撑压力位
    
    Args:
        df: DataFrame with columns [开盘, 最高, 最低, 收盘]
        ma_periods: 均线周期列表
    
    Returns:
        dict: 支撑压力位计算结果
    """
    # 计算均线
    ma_values = {}
    for period in ma_periods:
        ma_values[f'ma{period}'] = df['收盘'].rolling(period).mean().values
    
    # 构造输入数据
    kline_data = {
        'data': df,
        'ma_values': ma_values
    }
    
    # 计算
    calculator = SupportResistanceCalculator()
    result = calculator.calculate(kline_data, ma_values)
    
    return result


# 测试代码
if __name__ == "__main__":
    # 生成测试数据
    dates = pd.date_range('2026-01-01', periods=100, freq='D')
    np.random.seed(42)
    
    # 模拟上升趋势数据
    closes = 100 + np.cumsum(np.random.randn(100) * 0.5 + 0.1)
    highs = closes + np.random.rand(100) * 2
    lows = closes - np.random.rand(100) * 2
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    
    df = pd.DataFrame({
        '日期': dates,
        '开盘': opens,
        '最高': highs,
        '最低': lows,
        '收盘': closes
    })
    
    # 计算支撑压力
    result = calculate_support_resistance(df)
    
    print("=== 压支Skill测试结果 ===")
    print(f"最新收盘价: {result['close']:.2f}")
    print(f"动态支撑线价格: {result['support_price']:.2f}" if result['support_price'] else "无动态支撑线")
    print(f"动态压力线价格: {result['resistance_price']:.2f}" if result['resistance_price'] else "无动态压力线")
    print(f"\n水平支撑位: {result['horizontal_support']}")
    print(f"水平压力位: {result['horizontal_resistance']}")
    print(f"\n是否接近支撑: {result['near_support']}")
    print(f"是否接近压力: {result['near_resistance']}")

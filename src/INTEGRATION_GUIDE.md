# 压支Skill集成指南

## 文件位置

- **Skill模块**: `/Users/faronpan/Agent/stockyidong_project/src/support_resistance_skill.py`
- **原程序**: `/Users/faronpan/Agent/stockyidong_project/src/stockyidong mac.py`

---

## 集成步骤

### Step 1: 导入模块

在 `stockyidong mac.py` 文件开头（约第30行，其他import语句附近）添加：

```python
# 压支Skill：支撑压力位计算
try:
    from support_resistance_skill import SupportResistanceCalculator
    SUPPORT_RESISTANCE_SKILL_AVAILABLE = True
except ImportError:
    SUPPORT_RESISTANCE_SKILL_AVAILABLE = False
    print("警告：压支Skill模块未找到，将使用内置算法")
```

---

### Step 2: 替换支撑压力计算函数

找到 `stockyidong mac.py` 中的 `_compute_daily_support_resistance_line_prices` 函数（约第73228行），替换为：

```python
def _compute_daily_support_resistance_line_prices(self, kline_data):
    """使用压支Skill计算支撑压力线（与原接口兼容）"""
    if SUPPORT_RESISTANCE_SKILL_AVAILABLE:
        try:
            calculator = SupportResistanceCalculator()
            result = calculator.calculate(kline_data, kline_data.get('ma_values', {}))
            return result
        except Exception as e:
            print(f"压支Skill计算失败，降级为原算法: {e}")
    
    # 原算法降级处理（保持兼容性）
    out = {'close': None, 'support_price': None, 'resistance_price': None}
    try:
        data = kline_data['data']
        ma_values = kline_data['ma_values']
        n = len(data)
        if n < 3:
            return out
        closes = data['收盘'].values
        highs = data['最高'].values
        lows = data['最低'].values
        out['close'] = float(closes[-1])
        uptrend = False
        downtrend = False
        if 'ma20' in ma_values and len(ma_values['ma20']) >= 6:
            m20 = np.asarray(ma_values['ma20'], dtype=float)
            uptrend = bool(m20[-1] > m20[-6])
            downtrend = bool(m20[-1] < m20[-6])
        elif n >= 12:
            uptrend = bool(closes[-1] > closes[-11])
            downtrend = bool(closes[-1] < closes[-11])
        piv_lo = [i for i in range(1, n - 1) if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]]
        piv_hi = [i for i in range(1, n - 1) if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]]
        x_end = float(n - 1)
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
                    out['support_price'] = float(y0 + m * (x_end - x0))
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
                    out['resistance_price'] = float(y0 + m * (x_end - x0))
    except Exception:
        pass
    return out
```

**关键改动说明：**
- 优先使用压支Skill计算
- 如果Skill不可用或计算失败，自动降级为原算法
- 保持与原程序的完全兼容（输入输出格式不变）

---

### Step 3（可选）: 在K线图中绘制支撑压力线

如果你想在K线图上实际画出支撑压力线，找到绘制K线的函数（搜索 `_plot_kline` 或类似函数名），在绘制完成后添加：

```python
# 绘制支撑压力线
try:
    from support_resistance_skill import calculate_support_resistance
    
    # 计算支撑压力
    sr_result = calculate_support_resistance(df)
    
    # 绘制动态支撑线（绿色虚线）
    for line in sr_result['support_lines']:
        x = [line['start_idx'], line['end_idx'], len(df)-1]
        y = [line['start_price'], line['end_price'], line['current_price']]
        ax.plot(x, y, color='green', linestyle='--', linewidth=1.5, alpha=0.8, label='支撑线')
    
    # 绘制动态压力线（红色虚线）
    for line in sr_result['resistance_lines']:
        x = [line['start_idx'], line['end_idx'], len(df)-1]
        y = [line['start_price'], line['end_price'], line['current_price']]
        ax.plot(x, y, color='red', linestyle='--', linewidth=1.5, alpha=0.8, label='压力线')
    
    # 绘制水平支撑位（绿色虚线）
    for sup in sr_result['horizontal_support']:
        ax.axhline(y=sup, color='green', alpha=0.3, linestyle=':', linewidth=1.0)
        # 可选：添加价格标签
        ax.text(len(df)-1, sup, f'{sup:.2f}', color='green', fontsize=8, ha='right')
    
    # 绘制水平压力位（红色虚线）
    for res in sr_result['horizontal_resistance']:
        ax.axhline(y=res, color='red', alpha=0.3, linestyle=':', linewidth=1.0)
        # 可选：添加价格标签
        ax.text(len(df)-1, res, f'{res:.2f}', color='red', fontsize=8, ha='right')
except Exception as e:
    print(f"绘制支撑压力线失败: {e}")
```

---

## 测试集成是否成功

在 `stockyidong mac.py` 中，找到持仓检测相关的代码（搜索 `_check_holdings`），在函数开头添加测试代码：

```python
# 测试压支Skill
if SUPPORT_RESISTANCE_SKILL_AVAILABLE:
    print("✓ 压支Skill已加载")
    try:
        calculator = SupportResistanceCalculator()
        print(f"  - 阈值: {calculator.threshold_pct}%")
    except Exception as e:
        print(f"✗ 压支Skill加载失败: {e}")
else:
    print("✗ 压支Skill未找到")
```

运行程序，如果看到 "✓ 压支Skill已加载" 说明集成成功。

---

## 验证计算结果显示

在持仓检测结果显示的地方（搜索 `near_support_buy` 或 `near_resistance_sell`），确认能看到：

- 靠近支撑：买入标记（绿色）
- 靠近压力：卖出标记（红色）

---

## 常见问题

### Q1: 导入失败，提示"模块未找到"

**A**: 确保 `support_resistance_skill.py` 和 `stockyidong mac.py` 在同一个目录

### Q2: 计算结果为None

**A**: 检查输入数据格式是否正确：
```python
kline_data = {
    'data': DataFrame with columns [开盘, 最高, 最低, 收盘],
    'ma_values': {'ma5': [], 'ma10': [], 'ma20': []}
}
```

### Q3: 想调整"接近"的阈值

**A**: 修改 `threshold_pct` 参数：
```python
calculator = SupportResistanceCalculator(threshold_pct=1.0)  # 1%阈值（更严格）
```

---

## 进阶使用

### 获取详细的支撑压力位列表

```python
from support_resistance_skill import calculate_support_resistance

result = calculate_support_resistance(df)

# 打印所有支撑位
print("支撑位：")
for sup in result['horizontal_support']:
    print(f"  {sup:.2f}")

# 打印所有压力位
print("压力位：")
for res in result['horizontal_resistance']:
    print(f"  {res:.2f}")
```

### 只用水平支撑压力（不用趋势线）

如果你觉得趋势线不稳定，可以只使用水平支撑压力：

```python
result = calculate_support_resistance(df)

# 只看水平支撑压力
support_levels = result['horizontal_support']
resistance_levels = result['horizontal_resistance']

# 找最近的支撑和压力
close = result['close']
nearest_support = max([s for s in support_levels if s < close], default=None)
nearest_resistance = min([r for r in resistance_levels if r > close], default=None)

print(f"当前价: {close:.2f}")
print(f"最近支撑: {nearest_support:.2f}" if nearest_support else "最近支撑: 无")
print(f"最近压力: {nearest_resistance:.2f}" if nearest_resistance else "最近压力: 无")
```

---

## 文件清单

- ✅ `support_resistance_skill.py` - 核心计算模块
- ✅ `SUPPORT_RESISTANCE_SKILL.md` - 详细使用文档
- ✅ `INTEGRATION_GUIDE.md` - 本文（集成指南）

---

## 下一步

1. 应用上述补丁到 `stockyidong mac.py`
2. 运行程序测试
3. 如果没问题，approve skill提案
4. 根据需要调整参数或添加绘图功能

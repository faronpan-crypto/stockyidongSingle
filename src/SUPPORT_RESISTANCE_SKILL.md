# 压支Skill (Support/Resistance Skill)

## 功能说明

计算A股的支撑位和压力位，适用于：
- K线图显示（绘制支撑压力线）
- 交易信号生成（接近支撑→买入，接近压力→卖出）
- 量化策略集成

## 算法原理

### 1. 动态支撑压力线（趋势线）
- **上升趋势**：识别局部低点（枢点），连接递增的低点形成支撑线
- **下降趋势**：识别局部高点（枢点），连接递减的高点形成压力线
- 趋势判断：MA20斜率（6日对比）

### 2. 水平支撑压力位
- **前期高低点**：最近20天的最高/最低价
- **整数关口**：3.00/4.00/5.00等心理价位
- **均线支撑压力**：MA5/10/20/60

## 使用方法

### 方式一：在stockyidong_mac.py中集成

```python
# 在文件开头导入
from support_resistance_skill import SupportResistanceCalculator

# 在需要计算支撑压力的地方
calculator = SupportResistanceCalculator(threshold_pct=2.0)
result = calculator.calculate(kline_data, ma_values)

# result包含：
# - support_price: 动态支撑线当前价格
# - resistance_price: 动态压力线当前价格  
# - horizontal_support: 水平支撑位列表
# - horizontal_resistance: 水平压力位列表
# - near_support: 是否接近支撑（bool）
# - near_resistance: 是否接近压力（bool）
```

### 方式二：直接使用便捷函数

```python
from support_resistance_skill import calculate_support_resistance
import pandas as pd

# df需要包含列：开盘, 最高, 最低, 收盘
result = calculate_support_resistance(df, ma_periods=[5, 10, 20, 60])

print(f"支撑位: {result['horizontal_support']}")
print(f"压力位: {result['horizontal_resistance']}")
```

## 输出格式

```python
{
    'close': 3.53,  # 最新收盘价
    
    # 动态趋势线
    'support_price': 3.40,  # 支撑线价格（上升趋势）
    'resistance_price': 4.12,  # 压力线价格（下降趋势）
    
    # 详细线条信息（用于绘图）
    'support_lines': [
        {
            'start_idx': 50,  # 起点K线索引
            'end_idx': 80,  # 终点K线索引
            'start_price': 3.20,
            'end_price': 3.35,
            'slope': 0.005,  # 斜率
            'current_price': 3.40  # 延伸到现在的价格
        }
    ],
    'resistance_lines': [...],
    
    # 水平支撑压力
    'horizontal_support': [3.00, 3.20, 3.40, 3.50],
    'horizontal_resistance': [3.68, 3.80, 4.00, 4.12],
    
    # 交易信号
    'near_support': True,  # 当前价格是否接近支撑
    'near_resistance': False  # 当前价格是否接近压力
}
```

## 与原程序集成

### 替换原有的 `_compute_daily_support_resistance_line_prices` 函数

在 `stockyidong mac.py` 中找到该函数，替换为：

```python
def _compute_daily_support_resistance_line_prices(self, kline_data):
    """使用压支Skill计算支撑压力线"""
    from support_resistance_skill import SupportResistanceCalculator
    
    calculator = SupportResistanceCalculator()
    result = calculator.calculate(kline_data, kline_data.get('ma_values', {}))
    
    return result
```

### 在K线图中绘制支撑压力线

```python
# 假设已有ax（matplotlib的axes对象）
result = calculate_support_resistance(df)

# 绘制动态支撑线
for line in result['support_lines']:
    x = [line['start_idx'], line['end_idx'], len(df)-1]
    y = [line['start_price'], line['end_price'], line['current_price']]
    ax.plot(x, y, color='green', linestyle='--', linewidth=1.5, label='支撑线')

# 绘制动态压力线
for line in result['resistance_lines']:
    x = [line['start_idx'], line['end_idx'], len(df)-1]
    y = [line['start_price'], line['end_price'], line['current_price']]
    ax.plot(x, y, color='red', linestyle='--', linewidth=1.5, label='压力线')

# 绘制水平支撑压力
for sup in result['horizontal_support']:
    ax.axhline(y=sup, color='green', alpha=0.3, linestyle=':')
    
for res in result['horizontal_resistance']:
    ax.axhline(y=res, color='red', alpha=0.3, linestyle=':')
```

## 参数调整

- `threshold_pct`: 判断"接近"的阈值（默认2.0%）
  - 越小越严格（只有非常接近才算）
  - 越大越宽松（稍微靠近就算）

## 注意事项

1. **至少需要3根K线**才能计算
2. **趋势判断依赖MA20**，如果MA20数据不足，会降级为价格对比
3. **整数关口步长自适应**：
   - 股价<5元：0.5元步长
   - 股价5-20元：1元步长
   - 股价20-100元：5元步长
   - 股价>100元：10元步长

## 测试

运行模块自带的测试代码：

```bash
python support_resistance_skill.py
```

应该输出类似：

```
=== 压支Skill测试结果 ===
最新收盘价: 100.23
动态支撑线价格: 98.45
...
```

## 文件清单

- `support_resistance_skill.py`: 核心计算模块
- `SKILL.md`: 本文档

## 版本

- v1.0 (2026-07-03): 初始版本，移植自stockyidong_mac.py的原算法

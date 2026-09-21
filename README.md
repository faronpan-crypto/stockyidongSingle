# 🎯 stockyidong-mac003

A股异动监控 Tkinter 桌面 GUI —— macOS 版本，Mixin 架构（单文件入口 + 46 个 UI 模块）。

## ✨ 核心功能

| 模块 | 说明 |
|------|------|
| **持仓股管理** | 14 个标签页（持仓 / 龙头 / 15Min / Main / 持仓历史 / 同花顺 / 持仓1-8），双击按钮直接打开日K线放大图 |
| **大盘红绿灯** | 实时涨跌家数，红/黄/绿三色情绪灯；持仓股 SOS 弹窗 3 小时冷却 |
| **问财选股** | 三级 fallback：pywencai → HTTP → Tushare 本地筛选；本地缓存 30 分钟 |
| **行情数据** | Tushare 优先 + akshare 新浪/腾讯双通道兜底；daily 限频自动熔断 10 分钟 |
| **游资心法** | 7 位游资实时打分，双击卡片看全解；60 日 K 线指标计算 |
| **六军会师** | ETF 轮动策略（进攻 / 防御模式 + 8% 止损 + 15% 回撤） |
| **数据缓存** | Tushare / AKShare 结果 30 分钟缓存；全市场股票名一次性加载 |

## 🚀 快速开始

```bash
# 1. 克隆
git clone git@github.com:faronpan-crypto/stockyidong-mac003.git
cd stockyidong-mac003

# 2. 安装依赖（macOS 推荐 Python 3.11）
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. 配置环境变量
export TUSHARE_TOKEN=your_tushare_token_here   # https://tushare.pro/user/token
export STOCK_ANALYZER_DATA_DIR="$HOME/StockAnalyzer"

# 4. 运行
cd src && python3 "stockyidong mac003.py"
```

## 📁 目录结构

```
src/
├── stockyidong mac003.py      # 单文件入口 (~100 行, 负责 import + Patch + Mixin 组装)
├── ui/                        # 46 个 Mixin (Tkinter UI 模块化)
│   ├── tab_cangwei.py         # 持仓标签页 + 持仓股管理 (含双击日K)
│   ├── tab_stock_detail.py    # 日K线绘制 + Tushare daily / akshare 兜底
│   ├── tab_dapan.py           # 大盘红绿灯 + 情绪日历
│   ├── tab_getters.py         # 数据获取 (Tushare / AKShare / 缓存)
│   ├── tab_rest.py            # AI 分析 / 消息聚合
│   ├── tab_hot.py             # 热门概念 / 涨停 / 封板
│   └── ...
├── logic/                     # 业务逻辑层 (无 UI)
│   ├── spot.py                # 实时行情
│   ├── stock_names.py         # 股票名缓存 + jieba 词典
│   └── dapan_fetcher.py       # 大盘数据
├── data/                      # sqlite / json 缓存
└── config.py                  # 全局配置
```

## 🔧 技术要点

- **Tushare 熔断机制**：`daily` / `daily_basic` 等接口被限频时自动熔断 10 分钟，后续请求直接短路抛异常走 akshare 兜底，不白等
- **AKShare 双通道**：东财接口被网络拦截时自动切换新浪 / 腾讯
- **线程安全串行化**：所有 Tushare 调用通过 `_TS_CALL_LOCK` 串行化 + 熔断表防止并发击穿
- **macOS 双击判定**：Tkinter Label 在 macOS 上不触发 `<Double-1>`，改为单一 `<Button-1>` + `event.time` 时间戳判定（< 350ms 视为双击）
- **程序零联网启动**：启动时不自动调用任何外部 API，所有数据加载改为手动触发

## 🛠 主要数据链路

| 数据 | 首选 | 兜底 | 说明 |
|------|------|------|------|
| 日K线 | Tushare daily | akshare 新浪 / 腾讯 | daily 需要 ≥ 120 积分，当前 token 限频后自动熔断 |
| 实时行情 | akshare spot_em | tushare daily_basic | 盘中 9:30-15:00 用 akshare |
| 股票列表 | tushare stock_basic | 本地 sqlite | 启动时预加载 |
| 交易日历 | tushare trade_cal | 硬编码表 | 轻量接口无需积分 |

## 🧪 已知问题

- Tushare daily 接口需要 ≥ 120 积分才能调用，积分不够时走 akshare 兜底（新浪数据）
- AKShare 东财接口（`stock_zh_a_hist` / `stock_zh_a_spot_em`）在部分网络环境下被拦截，已自动降级到新浪
- pywencai（问财）需要 Cookie 才能返回完整数据，可设置 `IWENCAI_COOKIE` 环境变量

## 📄 License

MIT © faronpan-crypto

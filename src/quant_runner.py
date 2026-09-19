#!/usr/bin/env python3
"""量化 skill 复用入口：新浪源拉A股日线 -> china-stock-quant 指标/回测/风控。
用法: python3 quant_runner.py 002766 索菱股份
说明: akshare 东方财富源(stock_zh_a_hist)在本机被限流(RemoteDisconnected),
      统一走新浪源 stock_zh_a_daily 绕过。计算层(指标/回测/风控)为纯本地 pandas, 正常。
"""
import sys

sys.path.insert(0, "/Users/faronpan/.qclaw/workspace/skills/china-stock-quant/scripts")
import akshare as ak
import backtest
import technical_indicators


def run(code, name="", start="20240101", end="20260724", capital=100000):
    prefix = "sh" if code.startswith("6") else "sz"
    symbol = prefix + code
    print(f"### {name or code} ({symbol}) {start}~{end} ###")
    raw = ak.stock_zh_a_daily(symbol=symbol, start_date=start, end_date=end, adjust="qfq")
    df = raw.rename(columns={c: c.lower() for c in raw.columns})
    if "volume" not in df.columns and "vol" in df.columns:
        df = df.rename(columns={"vol": "volume"})
    df = df.reset_index(drop=True)
    print(f"数据 {len(df)} 条 | 收盘 {df['close'].iloc[0]} -> {df['close'].iloc[-1]} "
          f"(区间 {(df['close'].iloc[-1]/df['close'].iloc[0]-1)*100:.1f}%)")
    df2 = technical_indicators.add_all_indicators(df)
    for strat, kw in [("ma_cross", dict(ma_short=5, ma_long=20)),
                      ("grid", dict(grid_num=10)),
                      ("bollinger", dict())]:
        try:
            res = backtest.run_backtest(df2, strategy=strat, initial_capital=capital,
                                        stop_loss=0.05, take_profit=0.10, **kw)
            print(f"\n--- 策略: {strat} ---")
            print(res.summary())
        except Exception as e:
            print(f"\n--- 策略: {strat} FAIL: {e} ---")
    try:
        print("\n--- 风险(全样本) ---")
        print(backtest.assess_risk(df2['close']))
    except Exception as e:
        print("risk FAIL", e)


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "002766"
    name = sys.argv[2] if len(sys.argv) > 2 else ""
    run(code, name)

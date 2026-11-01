"""回溯验证引擎 — vectorbt 向量化

能跑:
  1. 给定 signals (买/卖信号) 的回测
  2. 参数网格搜索 (哪些权重/阈值最赚钱)
  3. Walk-forward 交叉验证 (防过拟合)
"""
import numpy as np
import pandas as pd


def backtest_signals(close_series: pd.Series, entries, exits,
                     init_cash=100000, fees=0.001) -> dict:
    """用 vectorbt 回测一组买卖信号"""
    result = {"error": None}
    try:
        import vectorbt as vbt
    except ImportError:
        result["error"] = "vectorbt 未安装"
        return result

    try:
        # 强制转 bool Series, 纯 numpy dtype (Numba 要求)
        entries_clean = entries.astype(bool).fillna(False)
        exits_clean = exits.astype(bool).fillna(False)
        # 确保和 close 对齐
        entries_clean = entries_clean.reindex(close_series.index, fill_value=False)
        exits_clean = exits_clean.reindex(close_series.index, fill_value=False)

        pf = vbt.Portfolio.from_signals(
            close_series.astype(float),
            entries_clean, exits_clean,
            init_cash=init_cash, fees=fees, freq="1D",
        )
        result["total_return"] = float(pf.total_return() * 100)
        result["total_profit"] = float(pf.total_profit())
        result["sharpe"] = float(pf.sharpe_ratio())
        result["max_drawdown"] = float(pf.max_drawdown() * 100)
        trades = pf.trades.records_readable
        result["n_trades"] = len(trades)
        if len(trades) > 0:
            result["win_rate"] = float((trades["Return"] > 0).mean() * 100)
            result["avg_trade_ret"] = float(trades["Return"].mean() * 100)
        else:
            result["win_rate"] = 0.0
            result["avg_trade_ret"] = 0.0
    except Exception as e:
        import traceback
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
    return result


def backtest_score_strategy(close_series: pd.Series, scores: pd.Series,
                            buy_threshold=65, sell_threshold=25,
                            init_cash=100000, fees=0.001) -> dict:
    """把量化综合评分转成买卖信号 → 回测

    Args:
        scores: 综合评分 Series (0-100, index 同 close)
        buy_threshold: 分数 ≥ 此值 → 买入
        sell_threshold: 分数 < 此值 → 卖出
    """
    entries = (scores >= buy_threshold).astype(bool).shift(1).fillna(False).astype(bool)
    exits = (scores < sell_threshold).astype(bool).shift(1).fillna(False).astype(bool)
    return backtest_signals(close_series, entries, exits, init_cash, fees)


def grid_search_scores(close_series: pd.Series, scores: pd.Series,
                       buy_range=(55, 85, 5), sell_range=(15, 35, 5)) -> pd.DataFrame:
    """参数网格搜索 — 找最优 buy/sell 阈值

    Returns:
        DataFrame: rows=params, columns=[buy_t, sell_t, total_return, sharpe, win_rate]
    """
    import vectorbt as vbt

    results = []
    buys = np.arange(*buy_range)
    sells = np.arange(*sell_range)

    for bt in buys:
        for st in sells:
            if st >= bt:
                continue
            r = backtest_score_strategy(close_series, scores, buy_threshold=bt, sell_threshold=st)
            if r.get("error") is None:
                results.append({
                    "buy_t": int(bt), "sell_t": int(st),
                    "total_return": r.get("total_return", 0),
                    "sharpe": r.get("sharpe", 0),
                    "win_rate": r.get("win_rate", 0),
                    "max_drawdown": r.get("max_drawdown", 0),
                    "n_trades": r.get("n_trades", 0),
                })
    return pd.DataFrame(results)


def walk_forward_validation(close_series: pd.Series, scores: pd.Series,
                             train_days=720, test_days=180, buy_t=65, sell_t=25) -> dict:
    """Walk-forward 验证: 滚动窗口训练参数 → 测试集评估

    Args:
        train_days: 训练窗口 (交易日)
        test_days: 测试窗口 (交易日)

    Returns:
        dict: {windows: [{train_range, test_range, train_return, test_return}],
               test_avg_return, test_sharpe, overfitting_ratio}
    """
    n = len(close_series)
    windows = []
    pos = train_days

    while pos + test_days <= n:
        train_slice = slice(pos - train_days, pos)
        test_slice = slice(pos, pos + test_days)

        train_close = close_series.iloc[train_slice]
        test_close = close_series.iloc[test_slice]
        train_scores = scores.iloc[train_slice]
        test_scores = scores.iloc[test_slice]

        train_r = backtest_score_strategy(train_close, train_scores, buy_t, sell_t)
        test_r = backtest_score_strategy(test_close, test_scores, buy_t, sell_t)

        windows.append({
            "train_start": str(train_close.index[0]),
            "train_end": str(train_close.index[-1]),
            "test_start": str(test_close.index[0]),
            "test_end": str(test_close.index[-1]),
            "train_return": train_r.get("total_return", 0),
            "test_return": test_r.get("total_return", 0),
            "test_sharpe": test_r.get("sharpe", 0),
            "test_maxdd": test_r.get("max_drawdown", 0),
        })
        pos += test_days

    if not windows:
        return {"error": "数据不足"}

    test_returns = [w["test_return"] for w in windows]
    train_returns = [w["train_return"] for w in windows]
    overfitting = np.mean(train_returns) - np.mean(test_returns) if train_returns else 0

    return {
        "windows": windows,
        "n_windows": len(windows),
        "test_avg_return": float(np.mean(test_returns)),
        "test_median_return": float(np.median(test_returns)),
        "test_win_rate": float(np.mean([1 for r in test_returns if r > 0]) * 100),
        "overfitting_gap": float(overfitting),
        "conclusion": _wfv_conclusion(test_returns, overfitting),
    }


def _wfv_conclusion(test_returns, overfitting):
    """解读 Walk-forward 结果"""
    if len(test_returns) == 0:
        return "数据不足"
    avg = np.mean(test_returns)
    wr = np.mean([1 for r in test_returns if r > 0])
    if wr >= 0.7 and avg > 5 and overfitting < 15:
        return "✅ 策略稳健：测试集多数窗口盈利，过拟合风险低"
    elif wr >= 0.5 and avg > 0:
        return "🟡 策略可用：测试集正收益但稳定性一般"
    elif avg > 0 and overfitting > 15:
        return "⚠️ 过拟合警告：训练集收益远高于测试集"
    else:
        return "❌ 策略无效：测试集平均亏损，建议放弃"

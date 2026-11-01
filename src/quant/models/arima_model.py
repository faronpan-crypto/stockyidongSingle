"""ARIMA + Prophet 时间序列预测

ARIMA: statsmodels + pmdarima auto 参数选择
Prophet: Meta/Facebook 的可解释性强

输出统一格式:
  {
    "model": "arima",
    "fwd_5d": +1.23,        # 预测未来 5 日涨跌幅 (%)
    "fwd_20d": -2.45,       # 预测未来 20 日涨跌幅 (%)
    "confidence": 0.72,     # 置信度 0-1
    "ci_20d": (-5.1, 0.2),  # 95% 置信区间
    "details": {...}         # 模型内部信息 (AIC, p,d,q 等)
  }
"""
import numpy as np
import pandas as pd


def predict_arima(closes: np.ndarray, steps=(5, 20)) -> dict:
    """ARIMA 预测

    Args:
        closes: 收盘价数组 (≥60 天)
        steps: 预测步长元组

    Returns:
        统一格式的预测结果 dict
    """
    result = {
        "model": "arima",
        "fwd_5d": None, "fwd_20d": None, "confidence": 0.5,
        "ci_20d": None, "details": {},
    }
    if len(closes) < 60:
        result["details"]["error"] = f"数据不足 ({len(closes)}<60)"
        return result

    try:
        from pmdarima import auto_arima
        ts = pd.Series(closes, dtype=float)
        # auto_arima 自动选 p,d,q (AIC 最优)
        model = auto_arima(
            ts, start_p=1, start_q=1, max_p=5, max_q=5, max_d=2,
            seasonal=False, trace=False, suppress_warnings=True,
            stepwise=True, maxiter=50,
        )
        result["details"]["order"] = model.order
        result["details"]["aic"] = float(model.aic())

        # 预测最大步长
        max_step = max(steps)
        fc, conf_int = model.predict(n_periods=max_step, return_conf_int=True)
        fc = np.array(fc)
        conf_int = np.array(conf_int)

        base = closes[-1]
        for s in steps:
            fwd_pct = (fc[s - 1] - base) / base * 100
            result[f"fwd_{s}d"] = float(fwd_pct)

        # 置信区间
        result["ci_20d"] = (
            float((conf_int[-1, 0] - base) / base * 100),
            float((conf_int[-1, 1] - base) / base * 100),
        )
        # 置信度 = 区间越窄置信越高 (归一化)
        ci_width = conf_int[-1, 1] - conf_int[-1, 0]
        result["confidence"] = float(max(0.1, min(0.95, 1.0 - ci_width / base * 5)))
    except Exception as e:
        result["details"]["error"] = str(e)
        result["model"] = "arima_failed"

    return result


def predict_prophet(closes: np.ndarray, trade_dates=None, steps=(5, 20)) -> dict:
    """Prophet 预测 (Meta)

    注意: neuralprophet 新版有兼容性问题，这里用原版 prophet
    """
    result = {
        "model": "prophet",
        "fwd_5d": None, "fwd_20d": None, "confidence": 0.5,
        "ci_20d": None, "details": {},
    }
    try:
        from prophet import Prophet
    except ImportError:
        result["details"]["error"] = "prophet 未安装 (pip install prophet)"
        return result

    if len(closes) < 60:
        result["details"]["error"] = f"数据不足 ({len(closes)}<60)"
        return result

    try:
        if trade_dates is None:
            trade_dates = pd.date_range(end=pd.Timestamp.now(), periods=len(closes), freq="B")
        df = pd.DataFrame({"ds": pd.to_datetime(trade_dates), "y": closes.astype(float)})
        model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        model.fit(df)
        future = model.make_future_dataframe(periods=max(steps), freq="B")
        forecast = model.predict(future)
        fc = forecast["yhat"].values[-max(steps):]
        base = closes[-1]
        for s in steps:
            result[f"fwd_{s}d"] = float((fc[s - 1] - base) / base * 100)
        ci_fc = forecast.iloc[-max(steps):]
        result["ci_20d"] = (
            float((ci_fc["yhat_lower"].iloc[-1] - base) / base * 100),
            float((ci_fc["yhat_upper"].iloc[-1] - base) / base * 100),
        )
        result["confidence"] = 0.6
    except Exception as e:
        result["details"]["error"] = str(e)
        result["model"] = "prophet_failed"
    return result

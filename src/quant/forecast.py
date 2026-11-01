"""统一 forecast 入口 — 给 UI 调用的干净接口

run_forecast()      → 预测 (当前 5D 评分 + Ensemble 融合)
run_backtest()      → 回溯验证
run_validation()    → Walk-forward + 参数网格
list_models()       → 可用模型列表 (含 availability 检查)
"""
import sys
import os
import time
import json
import sqlite3
import traceback
import numpy as np
import pandas as pd

# 相对导入
from .data_loader import (
    get_index_hist, get_breadth, get_trade_date, TS_CODE_MAP,
)
from .features import compute_all_features
from .backtest import (
    backtest_score_strategy, grid_search_scores, walk_forward_validation,
)
from .models.arima_model import predict_arima
from .models.ml_models import predict_svm, predict_rf, predict_xgb
from .models.lstm_model import predict_lstm
from .models.ensemble import ensemble_predict, ensemble_conclusion

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def list_models():
    """列出可用的模型及其版本"""
    import importlib
    models = [
        ("arima", "ARIMA/SARIMA", True),
        ("svm", "SVM 分类", True),
        ("rf", "Random Forest", True),
    ]
    # XGBoost
    try:
        importlib.import_module("xgboost")
        models.append(("xgb", "XGBoost", True))
    except Exception:
        models.append(("xgb", "XGBoost (brew install libomp)", False))
    # LSTM / torch
    try:
        t = importlib.import_module("torch")
        models.append(("lstm", f"LSTM (torch {t.__version__}, MPS={'on' if t.backends.mps.is_available() else 'off'})", True))
    except ImportError:
        models.append(("lstm", "LSTM (pip install torch)", False))
    return models


def _calc_traditional_score(closes):
    """当前 5D 量化评分 (从 tab_builders._scan_quant_forecast_data 迁移)"""
    from .features import compute_ema, compute_rsi, compute_macd

    closes = np.array(closes, dtype=float)
    close_now = float(closes[-1])
    prev_close = float(closes[-2]) if len(closes) >= 2 else close_now

    ma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else None
    ma60 = float(np.mean(closes[-60:])) if len(closes) >= 60 else None
    ma250 = float(np.mean(closes[-250:])) if len(closes) >= 250 else None

    arr_score = 0
    if ma20 and ma60 and ma250:
        if ma20 > ma60 > ma250: arr_score = 100
        elif ma20 < ma60 < ma250: arr_score = 0
        else: arr_score = 50

    dev20 = (close_now - ma20) / ma20 * 100 if ma20 else 0
    dev60 = (close_now - ma60) / ma60 * 100 if ma60 else 0
    dev250 = (close_now - ma250) / ma250 * 100 if ma250 else 0

    dif, dea, macd_hist = compute_macd(closes)
    dif_dir = 1 if len(dif) >= 2 and dif[-1] > dif[-2] else -1
    dea_pos = len(dif) >= 1 and dif[-1] > 0

    if dea_pos and dif_dir > 0: macd_score = 80
    elif not dea_pos and dif_dir < 0: macd_score = 20
    elif dea_pos and dif_dir < 0: macd_score = 45
    else: macd_score = 60

    rsi = compute_rsi(closes) if len(closes) >= 15 else 50.0
    ret_20d = (closes[-1] / closes[-21] - 1) * 100 if len(closes) >= 21 else 0
    trend_score = max(0, min(100, 50 + ret_20d * 3))
    quant_score = arr_score * 0.4 + macd_score * 0.3 + rsi / 100 * 100 * 0.2 + trend_score * 0.1

    return {
        "close": close_now, "pct_chg": (close_now - prev_close) / prev_close * 100,
        "ma20": ma20, "ma60": ma60, "ma250": ma250,
        "arr_score": arr_score, "dev20": dev20, "dev60": dev60, "dev250": dev250,
        "dif": float(dif[-1]) if len(dif) >= 1 else 0,
        "dea": float(dea[-1]) if len(dea) >= 1 else 0,
        "rsi": float(rsi), "ret_20d": ret_20d,
        "ma_score": arr_score, "macd_score": macd_score, "trend_score": trend_score,
        "quant_score": float(quant_score),
    }


def run_forecast(target_date=None, models=None):
    """主入口: 运行完整预测

    Args:
        target_date: 'YYYYMMDD' 或 None (=最近交易日)
        models: 要跑的模型列表 ['arima','svm','rf','xgb','lstm'] 或 None (全跑)

    Returns:
        dict: 完整预测结果
    """
    t0 = time.time()
    if models is None:
        models = ["arima", "svm", "rf", "lstm"]  # 默认: ARIMA + ML + LSTM

    result = {"td": "", "targets": {}, "traditional": {}, "ensemble": {}}

    # 1. 日期 + 宽广度
    trade_date = get_trade_date(target_date)
    result["td"] = trade_date
    breadth = get_breadth(trade_date)
    result["breadth"] = breadth

    # 2. 各指数跑一遍
    for idx_name in ["上证指数", "深证成指", "创业板指"]:
        hist = get_index_hist(idx_name, end_date=trade_date, days_back=3650)
        if hist is None or len(hist) < 120:
            result["targets"][idx_name] = {"error": f"{idx_name} 数据不足"}
            continue

        closes = hist["close"].astype(float).values

        # 传统评分
        trad = _calc_traditional_score(closes)

        # 特征工程 (ML 用)
        df_feat = compute_all_features(hist)

        # ARIMA
        arima_res = predict_arima(closes)

        # ML 模型 (需要足够样本)
        ml_results = []
        if "svm" in models:
            ml_results.append(("svm", predict_svm(df_feat)))
        if "rf" in models:
            ml_results.append(("rf", predict_rf(df_feat)))
        if "xgb" in models:
            ml_results.append(("xgb", predict_xgb(df_feat)))

        # 转换 ML 结果到统一格式
        ml_for_ensemble = []
        for mname, mr in ml_results:
            if "error" in mr:
                continue
            fwd = arima_res.get("fwd_20d", 0) * 0.5  # 没直接的 fwd，暂折中
            if "up_prob" in mr:
                # 用 up_prob 映射: 0.3→-3%, 0.5→0%, 0.7→+3%
                fwd = (mr["up_prob"] - 0.5) * 10  # ±5%
            ml_for_ensemble.append({
                "model": mname,
                "fwd_20d": fwd,
                "up_prob": mr.get("up_prob", 0.5),
                "confidence": 0.6,
            })

        # LSTM
        lstm_res = None
        if "lstm" in models:
            lstm_res = predict_lstm(closes)

        # Ensemble 融合
        ensemble_inputs = [arima_res] + ml_for_ensemble
        if lstm_res and lstm_res.get("fwd_20d") is not None:
            ensemble_inputs.append(lstm_res)
        ensemble = ensemble_predict(ensemble_inputs)
        ensemble["conclusion"] = ensemble_conclusion(
            ensemble.get("up_prob", 0.5), ensemble.get("fwd_20d", 0), ensemble.get("confidence", 0.3)
        )

        result["targets"][idx_name] = {
            "traditional": trad,
            "models": {"arima": arima_res, "lstm": lstm_res, **dict(ml_results)},
            "ensemble": ensemble,
        }

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    return result


def run_backtest(target="上证指数", buy_threshold=65, sell_threshold=25):
    """回溯当前 5D 评分策略

    注意: 历史 breadth/trin/sim/knn 数据不可得, 这里用 MA 排列 + MACD + RSI + 趋势
    4 个纯价格因子做简化综合分 (等价于原始 quant_score)
    """
    hist = get_index_hist(target, days_back=3650)
    if hist is None or len(hist) < 260:
        return {"error": f"{target} 数据不足"}

    closes = hist["close"].astype(float).values
    dates = hist["trade_date"].values

    scores = []
    for i in range(260, len(closes)):
        # 直接用 trad.quant_score (0-100), 这是真正的量化评分
        q = _calc_traditional_score(closes[: i + 1])["quant_score"]
        scores.append(float(q))

    close_s = pd.Series(closes[260:].astype(float), index=pd.to_datetime(dates[260:]))
    scores_s = pd.Series(scores, index=close_s.index).astype(float)

    return backtest_score_strategy(close_s, scores_s, buy_threshold, sell_threshold)


def run_validation(target="上证指数"):
    """完整验证: Walk-forward + 参数网格"""
    hist = get_index_hist(target, days_back=3650)
    if hist is None or len(hist) < 720:
        return {"error": "数据不足 720 天"}

    closes = hist["close"].astype(float).values
    dates = hist["trade_date"].values

    scores = []
    for i in range(260, len(closes)):
        q = _calc_traditional_score(closes[: i + 1])["quant_score"]
        scores.append(float(q))

    close_s = pd.Series(closes[260:].astype(float), index=pd.to_datetime(dates[260:]))
    scores_s = pd.Series(scores, index=close_s.index).astype(float)

    # Walk-forward
    wfv = walk_forward_validation(close_s, scores_s)
    # 参数网格
    grid = grid_search_scores(close_s, scores_s)
    best = None
    if len(grid) > 0:
        # Sharpe 优先
        best = grid.sort_values("sharpe", ascending=False).iloc[0].to_dict()

    return {
        "walk_forward": wfv,
        "param_grid_top10": grid.nlargest(10, "sharpe").to_dict("records") if len(grid) > 0 else [],
        "best_params": best,
        "n_days": len(close_s),
        "date_range": f"{dates[260]} ~ {dates[-1]}",
    }

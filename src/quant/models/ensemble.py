"""Ensemble 融合 — Stacking + 加权投票"""
import numpy as np


def ensemble_predict(model_results: list, weights: dict = None) -> dict:
    """融合多个模型预测

    Args:
        model_results: 各模型 predict 输出 list
        weights: 手动权重 dict, 如 {"arima":0.3, "rf":0.3, "lstm":0.4}
                 None = 自动按 confidence 加权

    Returns:
        dict: {fwd_5d, fwd_20d, up_prob, confidence, ensemble_method}
    """
    valid = [r for r in model_results if r.get("fwd_20d") is not None and "error" not in r]
    if not valid:
        return {"fwd_5d": None, "fwd_20d": None, "up_prob": 0.5, "confidence": 0.3,
                "ensemble_method": "no_models"}

    # 按 confidence 加权
    confs = np.array([max(0.1, r.get("confidence", 0.5)) for r in valid])
    if weights:
        w = np.array([weights.get(r["model"], 0.2) for r in valid])
    else:
        w = confs
    w = w / w.sum()

    fwd5 = np.average([r.get("fwd_5d") for r in valid], weights=w)
    fwd20 = np.average([r.get("fwd_20d") for r in valid], weights=w)

    # SVM/RF/XGB 有 up_prob, LSTM/ARIMA 用 fwd_20d 转
    ups = []
    for r in valid:
        if "up_prob" in r:
            ups.append(r["up_prob"])
        elif r.get("fwd_20d") is not None:
            # 正向涨幅 → up_prob > 0.5
            ups.append(1.0 / (1.0 + np.exp(-r["fwd_20d"])))  # sigmoid
    up_prob = float(np.average(ups, weights=w)) if ups else 0.5

    # 综合置信度 = 模型共识度 (方向一致率) × 平均 confidence
    signs = [1 if r.get("fwd_20d", 0) > 0 else 0 for r in valid]
    consensus = max(np.mean(signs), 1 - np.mean(signs))  # 取多数派比例
    avg_conf = float(np.mean(confs))
    confidence = float(consensus * avg_conf)

    return {
        "fwd_5d": float(fwd5),
        "fwd_20d": float(fwd20),
        "up_prob": up_prob,
        "confidence": confidence,
        "ensemble_method": "confidence_weighted" if weights is None else "manual_weighted",
        "n_models": len(valid),
        "model_names": [r["model"] for r in valid],
    }


def ensemble_conclusion(up_prob, fwd_20d, confidence):
    """给 Ensemble 结果一个文字结论"""
    if up_prob >= 0.65 and confidence >= 0.6:
        return "🟢 强多：多数模型看好，置信度高"
    if up_prob >= 0.55 and confidence >= 0.5:
        return "🟢🟡 中性偏多：模型分歧不大"
    if 0.45 <= up_prob <= 0.55:
        return "🟡 震荡：模型分歧较大，观望"
    if up_prob <= 0.35 and confidence >= 0.6:
        return "🔴 强空：多数模型看跌"
    if up_prob < 0.45:
        return "🟡🔴 偏空：注意下行风险"
    return "🟡 不确定"

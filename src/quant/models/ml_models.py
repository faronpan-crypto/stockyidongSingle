"""ML 分类模型 — SVM / RandomForest / XGBoost

标签定义:
  分类 (classification): 未来 N 日涨幅 > threshold 记为 1 (涨), 否则 0 (跌)
  回归 (regression): 未来 N 日涨幅 (%)

Walk-forward: 严格时间分割, 防过拟合
"""
import numpy as np
import pandas as pd


def _make_dataset(df_features, target_col="ret20d_forward", forward_days=20,
                  method="classification", threshold=0.0):
    """从特征 DataFrame 构建 (X, y)

    Args:
        df_features: 已 compute_all_features 的 DataFrame
        forward_days: 标签前瞻天数
        method: 'classification' (涨/跌) 或 'regression' (涨幅%)
        threshold: classification 下: 涨幅 > threshold*100% 记为涨

    Returns:
        X (特征矩阵), y (标签), feature_names
    """
    df = df_features.copy()
    # 未来 N 日收益率 (收盘价相对于当日)
    df["_close_forward"] = df["close"].shift(-forward_days)
    df["ret_forward"] = (df["_close_forward"] - df["close"]) / df["close"] * 100
    if method == "classification":
        df["target"] = (df["ret_forward"] > threshold).astype(int)
    else:
        df["target"] = df["ret_forward"]

    # 特征列: 所有数值列 (除 close / trade_date / 目标列)
    exclude = {"close", "trade_date", "_close_forward", "ret_forward", "target"}
    feature_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
    df_clean = df.dropna(subset=feature_cols + ["target"])
    X = df_clean[feature_cols].values.astype(np.float64)
    y = df_clean["target"].values
    return X, y, feature_cols, df_clean["trade_date"].values


def predict_svm(df_features, forward_days=20):
    """SVM 分类预测"""
    result = {"model": "svm", "method": "classification"}
    try:
        from sklearn.svm import SVC
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score
    except ImportError:
        result["error"] = "sklearn 未安装"
        return result

    try:
        X, y, features, dates = _make_dataset(df_features, forward_days=forward_days)
        if len(X) < 100:
            result["error"] = f"样本不足 ({len(X)}<100)"
            return result

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = SVC(kernel="rbf", C=1.0, probability=True)
        # Walk-forward: 最后 20% 做测试
        split = int(len(X_scaled) * 0.8)
        model.fit(X_scaled[:split], y[:split])

        # 当前特征 = 最后一行
        latest = scaler.transform(X_scaled[-1:])
        proba = model.predict_proba(latest)[0]
        result["up_prob"] = float(proba[1]) if proba.shape[1] > 1 else 0.5
        result["down_prob"] = float(proba[0]) if proba.shape[1] > 1 else 0.5

        # CV 准确率
        cv_scores = cross_val_score(model, X_scaled[:split], y[:split], cv=5)
        result["train_acc"] = float(cv_scores.mean())
        result["n_features"] = len(features)
        result["n_samples"] = len(X)
    except Exception as e:
        result["error"] = str(e)
    return result


def predict_rf(df_features, forward_days=20):
    """Random Forest — 带特征重要性"""
    result = {"model": "random_forest", "method": "classification"}
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        result["error"] = "sklearn 未安装"
        return result

    try:
        X, y, features, dates = _make_dataset(df_features, forward_days=forward_days)
        if len(X) < 100:
            result["error"] = f"样本不足 ({len(X)}<100)"
            return result

        model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
        model.fit(X, y)

        latest = X[-1:]
        proba = model.predict_proba(latest)[0]
        result["up_prob"] = float(proba[1]) if proba.shape[1] > 1 else 0.5
        result["down_prob"] = float(proba[0]) if proba.shape[1] > 1 else 0.5

        # 特征重要性 Top 5
        importances = dict(sorted(zip(features, model.feature_importances_),
                           key=lambda x: -x[1])[:5])
        result["top_features"] = {k: float(v) for k, v in importances.items()}
        result["n_samples"] = len(X)
    except Exception as e:
        result["error"] = str(e)
    return result


def predict_xgb(df_features, forward_days=20):
    """XGBoost 分类（Gradient Boosting）"""
    result = {"model": "xgboost", "method": "classification"}
    try:
        import xgboost as xgb
    except ImportError:
        result["error"] = "xgboost 未安装 (brew install libomp)"
        return result

    try:
        X, y, features, dates = _make_dataset(df_features, forward_days=forward_days)
        if len(X) < 100:
            result["error"] = f"样本不足 ({len(X)}<100)"
            return result

        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            tree_method="hist", eval_metric="logloss",
        )
        model.fit(X, y)

        latest = X[-1:]
        proba = model.predict_proba(latest)[0]
        result["up_prob"] = float(proba[1]) if proba.shape[1] > 1 else 0.5
        result["down_prob"] = float(proba[0]) if proba.shape[1] > 1 else 0.5

        importances = dict(sorted(zip(features, model.feature_importances_),
                           key=lambda x: -x[1])[:5])
        result["top_features"] = {k: float(v) for k, v in importances.items()}
        result["n_samples"] = len(X)
    except Exception as e:
        result["error"] = str(e)
    return result

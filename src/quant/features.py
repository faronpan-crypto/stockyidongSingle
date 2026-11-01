"""特征工程 — 从原始价格序列生成多维度特征"""
import numpy as np
import pandas as pd


def compute_ema(arr, n):
    """指数加权移动平均"""
    arr = np.array(arr, dtype=float)
    k = 2.0 / (n + 1)
    result = np.empty_like(arr)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = arr[i] * k + result[i - 1] * (1 - k)
    return result


def compute_rsi(arr, n=14):
    """RSI 指标"""
    arr = np.array(arr, dtype=float)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    if len(gains) < n:
        return 50.0
    avg_gain = np.mean(gains[:n])
    avg_loss = np.mean(losses[:n])
    for i in range(n, len(gains)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
    rs = avg_gain / max(avg_loss, 1e-10)
    return float(100 - 100 / (1 + rs))


def compute_macd(closes, fast=12, slow=26, signal=9):
    """MACD: DIF, DEA, MACD柱"""
    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    dif = ema_fast - ema_slow
    dea = compute_ema(dif, signal)
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def compute_all_features(df_close: pd.DataFrame, target_col="close") -> pd.DataFrame:
    """从 index_daily DataFrame 计算全部特征

    Args:
        df_close: 至少有 'trade_date', 'close' 列
        target_col: 收盘价列名

    Returns:
        DataFrame with trade_date + 20+ 特征列
    """
    df = df_close.copy().sort_values("trade_date").reset_index(drop=True)
    closes = df[target_col].astype(float).values

    # === MA 偏离度 ===
    for w in [5, 10, 20, 60, 250]:
        df[f"ma{w}"] = df[target_col].rolling(w).mean()
        df[f"dev{w}"] = (df[target_col] - df[f"ma{w}"]) / df[f"ma{w}"] * 100

    # === 收益率 ===
    for w in [1, 5, 10, 20, 60]:
        df[f"ret{w}d"] = df[target_col].pct_change(w) * 100

    # === 波动率 ===
    df["vol_20d"] = df["ret1d"].rolling(20).std()
    df["vol_60d"] = df["ret1d"].rolling(60).std()

    # === MA 排列评分 ===
    def _arr_score(row):
        m20, m60, m250 = row.get("ma20"), row.get("ma60"), row.get("ma250")
        if pd.isna(m20) or pd.isna(m60) or pd.isna(m250):
            return np.nan
        if m20 > m60 > m250:
            return 100.0
        if m20 < m60 < m250:
            return 0.0
        return 50.0

    df["ma_arr"] = df.apply(_arr_score, axis=1)

    # === MACD ===
    try:
        df["dif"], df["dea"], df["macd_hist"] = compute_macd(closes)
        df["dif_dir"] = np.sign(df["dif"].diff())
    except Exception:
        df["dif"] = df["dea"] = df["macd_hist"] = np.nan
        df["dif_dir"] = 0

    # === RSI ===
    df["rsi14"] = [compute_rsi(closes[: i + 1]) for i in range(len(closes))]

    # === 价格位置 (距年内高点/低点) ===
    df["high_250"] = df[target_col].rolling(250).max()
    df["low_250"] = df[target_col].rolling(250).min()
    df["pos_in_range"] = (df[target_col] - df["low_250"]) / (
        df["high_250"] - df["low_250"] + 1e-10
    )

    return df


def extract_feature_vector(row: pd.Series) -> dict:
    """从一行特征 DataFrame 提取用于 ML/模式匹配的特征向量"""
    keys = [
        "dev20", "dev60", "dev250",
        "ret1d", "ret5d", "ret20d", "ret60d",
        "vol_20d", "vol_60d",
        "ma_arr",
        "dif", "dea", "macd_hist", "rsi14",
        "pos_in_range",
    ]
    return {k: float(row[k]) for k in keys if k in row.index and not pd.isna(row[k])}

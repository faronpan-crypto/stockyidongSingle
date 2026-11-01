"""LSTM 序列预测 — torch (MPS/CUDA)

60 日滑动窗口 → 预测未来 20 日涨幅
"""
import numpy as np


def _create_sequences(closes, window=60, target_step=20):
    """构造 LSTM 输入序列

    Args:
        closes: 收盘价数组
        window: 输入窗口 (天数)
        target_step: 预测目标天数

    Returns:
        X: (n_samples, window, 1) 归一化窗口
        y: (n_samples,) 未来 target_step 涨幅 (%)
    """
    X, y = [], []
    for i in range(window, len(closes) - target_step):
        window_vals = closes[i - window : i]
        # 归一化到 [0, 1]
        w_min, w_max = window_vals.min(), window_vals.max()
        if w_max - w_min < 1e-10:
            continue
        normed = (window_vals - w_min) / (w_max - w_min)
        X.append(normed.reshape(-1, 1))
        fwd_return = (closes[i + target_step] - closes[i]) / closes[i] * 100
        y.append(fwd_return)
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


class _LSTMForecaster:
    def __init__(self, input_size=1, hidden_size=64, num_layers=2, output_size=1):
        import torch
        import torch.nn as nn

        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

        class LSTMNet(nn.Module):
            def __init__(self, in_sz, hid_sz, n_layers, out_sz):
                super().__init__()
                self.lstm = nn.LSTM(in_sz, hid_sz, n_layers, batch_first=True, dropout=0.2)
                self.fc = nn.Sequential(nn.Linear(hid_sz, hid_sz // 2), nn.ReLU(), nn.Linear(hid_sz // 2, out_sz))

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :])

        self.model = LSTMNet(input_size, hidden_size, num_layers, output_size).to(self.device)

    def fit(self, X, y, epochs=50, batch_size=32, lr=1e-3):
        import torch
        import torch.nn as nn

        X_t = torch.FloatTensor(X).to(self.device)
        y_t = torch.FloatTensor(y.reshape(-1, 1)).to(self.device)
        dataset = torch.utils.data.TensorDataset(X_t, y_t)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for xb, yb in loader:
                optimizer.zero_grad()
                pred = self.model(xb)
                loss = criterion(pred, yb)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(xb)
        return total_loss / len(dataset)

    def predict(self, X):
        import torch
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self.device)
            return self.model(X_t).cpu().numpy().ravel()


def predict_lstm(closes: np.ndarray, forward_days=20, window=60, retrain_epochs=50) -> dict:
    """LSTM 预测未来 N 日涨幅 (%)"""
    result = {
        "model": "lstm", "fwd_5d": None, "fwd_20d": None,
        "confidence": 0.5, "details": {}, "device": "cpu",
    }
    try:
        import torch
    except ImportError:
        result["error"] = "torch 未安装"
        return result

    if len(closes) < window + forward_days + 30:
        result["error"] = f"数据不足 ({len(closes)}<{window + forward_days + 30})"
        return result

    result["device"] = "mps" if torch.backends.mps.is_available() else "cpu"

    try:
        X20, y20 = _create_sequences(closes, window=window, target_step=forward_days)
        X5, y5 = _create_sequences(closes, window=window, target_step=5)

        result["n_samples_20d"] = len(X20)
        result["n_samples_5d"] = len(X5)

        if len(X20) >= 50:
            model20 = _LSTMForecaster()
            model20.fit(X20, y20, epochs=retrain_epochs)
            latest20 = X20[-1:]  # 最新窗口
            pred20 = float(model20.predict(latest20)[0])
            result["fwd_20d"] = pred20
            result["confidence"] = float(max(0.2, 1.0 - abs(pred20) / 20))

        if len(X5) >= 50:
            model5 = _LSTMForecaster()
            model5.fit(X5, y5, epochs=retrain_epochs)
            latest5 = X5[-1:]
            result["fwd_5d"] = float(model5.predict(latest5)[0])

    except Exception as e:
        import traceback
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()

    return result

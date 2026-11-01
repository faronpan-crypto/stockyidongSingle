"""🎯 quant — 量化预测引擎包

统一入口: from quant.forecast import run_forecast
"""
from .forecast import run_forecast, run_backtest, run_validation, list_models

__all__ = ["run_forecast", "run_backtest", "run_validation", "list_models"]
__version__ = "1.0.0"

"""财务/基本面/ROE/PE/PB"""
import os, sys, re, json, time, threading, traceback, hashlib, urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
try:
    import numpy as np
except ImportError: np = None
try:
    import pandas as pd
except ImportError: pd = None
try:
    import akshare as ak
except ImportError: ak = None
try:
    import tushare as ts
except ImportError: ts = None
try:
    import requests
except ImportError: requests = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token


class FinanceMixin:
    """财务/基本面/ROE/PE/PB"""

    def _dedupe_elevator_stocks_by_code(self, stocks):
        """问财结果按 6 位代码去重,保留首次出现顺序。"""
        seen = set()
        out = []
        for s in stocks or []:
            if not isinstance(s, dict):
                continue
            c = str(s.get("code", "") or "").strip()
            if not c:
                continue
            c = c.zfill(6) if c.isdigit() and len(c) <= 6 else c
            if c in seen:
                continue
            seen.add(c)
            ns = dict(s)
            ns["code"] = c
            out.append(ns)
        return out

    def _open_growth_type_selector(self):
        self._open_growth_multi_selector(
            "选择股票类型",
            getattr(self, "growth_type_options", ["成长股"]),
            self.growth_type_selections,
            self.growth_type_summary_var,
        )

    def _calculate_sharpe_ratio(self, kline_data, stock_name, risk_free_rate=0.02):
        """计算夏普比率。
        夏普比率公式:Sharpe Ratio = (Rp - Rf) / σp
        其中:
        - Rp = 投资组合平均收益率
        - Rf = 无风险利率(年化,默认2%)
        - σp = 投资组合收益率标准差
        Returns:
            dict: 包含夏普比率、年化收益率、波动率等详细信息
        """
        result = {
            'success': False,
            'message': '',
            'sharpe_ratio': 0.0,
            'annualized_return': 0.0,
            'volatility': 0.0,
            'daily_returns': [],
            'calculation_steps': [],
            'analysis': []
        }
        try:
            data = kline_data['data']
            n = len(data)
            if n < 30:
                result['message'] = '数据不足,至少需要30条K线'
                return result
            closes = data['收盘'].values
            steps = []
            # 计算每日收益率
            daily_returns = []
            for i in range(1, n):
                prev_close = float(closes[i-1])
                curr_close = float(closes[i])
                if prev_close > 0:
                    ret = (curr_close - prev_close) / prev_close
                    daily_returns.append(ret)
            result['daily_returns'] = daily_returns
            steps.append(f"【步骤1】计算每日收益率:共 {len(daily_returns)} 个交易日")
            if len(daily_returns) < 20:
                result['message'] = '有效收益率数据不足'
                return result
            # 计算平均每日收益率
            avg_daily_return = sum(daily_returns) / len(daily_returns)
            steps.append(f"【步骤2】平均每日收益率:avg_daily = {avg_daily_return:.6f}")
            # 年化收益率(假设252个交易日)
            annualized_return = (1 + avg_daily_return) ** 252 - 1
            result['annualized_return'] = round(annualized_return * 100, 2)
            steps.append(f"【步骤3】年化收益率:Rp = (1 + {avg_daily_return:.6f})^252 - 1 = {annualized_return * 100:.2f}%")
            # 计算收益率标准差
            variance = sum((r - avg_daily_return) ** 2 for r in daily_returns) / len(daily_returns)
            daily_std = variance ** 0.5
            steps.append(f"【步骤4】每日收益率标准差:daily_std = {daily_std:.6f}")
            # 年化波动率
            volatility = daily_std * (252 ** 0.5)
            result['volatility'] = round(volatility * 100, 2)
            steps.append(f"【步骤5】年化波动率:σp = {daily_std:.6f} × √252 = {volatility * 100:.2f}%")
            # 无风险利率(年化)
            steps.append(f"【步骤6】无风险利率:Rf = {risk_free_rate * 100:.1f}%")
            # 计算夏普比率
            excess_return = annualized_return - risk_free_rate
            if volatility > 0:
                sharpe_ratio = excess_return / volatility
                result['sharpe_ratio'] = round(sharpe_ratio, 4)
                steps.append(f"【步骤7】夏普比率:Sharpe = ({excess_return * 100:.2f}% - {risk_free_rate * 100:.1f}%) / {volatility * 100:.2f}% = {sharpe_ratio:.4f}")
            else:
                result['sharpe_ratio'] = 0.0
                steps.append("【步骤7】夏普比率:波动率为0,夏普比率 = 0")
            result['calculation_steps'] = steps
            # 生成分析说明
            analysis = []
            analysis.append(f"夏普比率:{result['sharpe_ratio']:.4f}")
            analysis.append(f"年化收益率:{result['annualized_return']:.2f}%")
            analysis.append(f"年化波动率:{result['volatility']:.2f}%")
            sharpe = result['sharpe_ratio']
            if sharpe >= 2.0:
                analysis.append("评价:夏普比率优秀,风险调整后收益很高")
            elif sharpe >= 1.0:
                analysis.append("评价:夏普比率良好,风险调整后收益不错")
            elif sharpe >= 0.5:
                analysis.append("评价:夏普比率一般,需要关注风险")
            elif sharpe >= 0:
                analysis.append("评价:夏普比率较低,收益不足以覆盖风险")
            else:
                analysis.append("评价:夏普比率为负,投资表现不如无风险资产")
            result['analysis'] = analysis
            result['success'] = True
            result['message'] = '计算完成'
        except Exception as e:
            result['message'] = f'计算失败: {e}'
        return result


__all__ = ["FinanceMixin"]

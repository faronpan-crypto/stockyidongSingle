"""龙头股"""
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


class LeaderMixin:
    """龙头股"""

    def _leader_stock_ma_vol_pass(self, stock_code):
        """
        龙头股本地校验:5/10/20 日均线多头排列且三线较昨日走高;5 日均量 > 10 日均量;排除 ST。
        返回 (是否通过, 显示用名称)
        """
        if not stock_code or not AKSHARE_AVAILABLE:
            return False, ""
        try:
            hist = ak.stock_zh_a_hist(symbol=str(stock_code).strip(), period="daily", adjust="qfq")
        except Exception as e:
            print(f"[龙头股均线量] {stock_code}: {e}")
            return False, ""
        if hist is None or hist.empty or len(hist) < 25:
            return False, ""
        closes = pd.to_numeric(hist["收盘"], errors="coerce")
        vol_col = "成交量" if "成交量" in hist.columns else None
        if not vol_col:
            return False, ""
        vols = pd.to_numeric(hist[vol_col], errors="coerce")
        if closes.isna().all() or vols.isna().all():
            return False, ""
        ma5 = closes.rolling(5).mean()
        ma10 = closes.rolling(10).mean()
        ma20 = closes.rolling(20).mean()
        vma5 = vols.rolling(5).mean()
        vma10 = vols.rolling(10).mean()
        m5, m10, m20 = float(ma5.iloc[-1]), float(ma10.iloc[-1]), float(ma20.iloc[-1])
        if not (m5 > m10 > m20):
            return False, ""
        if not (
            m5 > float(ma5.iloc[-2])
            and m10 > float(ma10.iloc[-2])
            and m20 > float(ma20.iloc[-2])
        ):
            return False, ""
        if float(vma5.iloc[-1]) <= float(vma10.iloc[-1]):
            return False, ""
        nm = get_stock_name_by_code(stock_code) or (
            STOCK_CODES_DICT.get(stock_code, stock_code) if STOCK_CODES_DICT else stock_code
        )
        if not isinstance(nm, str):
            nm = str(nm)
        if self._is_st_or_delisted_name(nm):
            return False, ""
        return True, nm


__all__ = ["LeaderMixin"]

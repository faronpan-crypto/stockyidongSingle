"""情绪深度分析/涨跌家数/周期"""
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
from data.snapshot import *  # get_news_stocks_* 函数

import threading
import traceback
import hashlib
from urllib.parse import urljoin

class EmoDeepMixin:
    """情绪深度分析/涨跌家数/周期 + 情绪冰点反包扫描器"""

    def _show_emotion_freeze(self):
        """🧊 情绪冰点修复扫描器 — 跌停翘板 / 冰期反转 / 情绪均值回归"""
        import traceback as _tb
        try:
            from ui.emotion_freeze import show_emotion_freeze as _sf
            root = getattr(self, "win", None) or getattr(self, "_root", None) or getattr(self, "root", None)
            _sf(root=root, app=self)
        except Exception as e:
            print(f"[🧊emotion_freeze❌] {e}", flush=True)
            _tb.print_exc()


__all__ = ["EmoDeepMixin"]

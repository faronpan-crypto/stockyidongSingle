"""资金流/主力/散户/大单"""
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

class MoneyFlowMixin:
    """资金流/主力/散户/大单"""

    def create_money_flow_section(self, parent, data):
        """创建资金流向显示区域"""
        money_frame = ttk.LabelFrame(parent, text="💸 资金流向", padding=10)
        money_frame.pack(fill=tk.X, pady=(0, 10))
        # 北向资金
        if '北向资金' in data:
            northbound = data['北向资金']
            net_buy = northbound.get('净买入额', 0)
            buy_amount = northbound.get('买入额', 0)
            sell_amount = northbound.get('卖出额', 0)
            date = northbound.get('日期', '')
            net_color = "red" if net_buy > 0 else "green" if net_buy < 0 else "black"
            net_label = ttk.Label(money_frame, text=f"北向资金净买入: {net_buy/100000000:.2f}亿",
                                font=("Arial", 12, "bold"), foreground=net_color)
            net_label.pack(anchor=tk.W)
            buy_label = ttk.Label(money_frame, text=f"买入: {buy_amount/100000000:.2f}亿", font=("Arial", 11))
            buy_label.pack(anchor=tk.W)
            sell_label = ttk.Label(money_frame, text=f"卖出: {sell_amount/100000000:.2f}亿", font=("Arial", 11))
            sell_label.pack(anchor=tk.W)
            if date:
                date_label = ttk.Label(money_frame, text=f"数据日期: {date}", font=("Arial", 10), foreground="gray")
                date_label.pack(anchor=tk.W)
        # 融资融券
        if '融资融券' in data:
            margin = data['融资融券']
            margin_balance = margin.get('融资余额', 0)
            short_balance = margin.get('融券余额', 0)
            margin_buy = margin.get('融资买入额', 0)
            margin_label = ttk.Label(money_frame, text=f"融资余额: {margin_balance/100000000:.2f}亿",
                                   font=("Arial", 11))
            margin_label.pack(anchor=tk.W)
            short_label = ttk.Label(money_frame, text=f"融券余额: {short_balance/100000000:.2f}亿",
                                  font=("Arial", 11))
            short_label.pack(anchor=tk.W)
            buy_label = ttk.Label(money_frame, text=f"融资买入: {margin_buy/100000000:.2f}亿",
                                font=("Arial", 11))
            buy_label.pack(anchor=tk.W)


__all__ = ["MoneyFlowMixin"]

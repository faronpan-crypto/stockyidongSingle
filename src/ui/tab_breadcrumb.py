"""面包屑/导航路径/历史"""
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

class BreadcrumbMixin:
    """面包屑/导航路径/历史"""

    def _refresh_search_history_widget(self):
        """刷新搜索记录显示"""
        if hasattr(self, "search_history_listbox") and self.search_history_listbox:
            self.search_history_listbox.delete(0, tk.END)
            for item in getattr(self, "search_history", []):
                self.search_history_listbox.insert(tk.END, item)


__all__ = ["BreadcrumbMixin"]

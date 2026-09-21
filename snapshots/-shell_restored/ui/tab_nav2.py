"""导航排序"""
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

class Nav2Mixin:
    """导航排序"""

    def _edit_market_indices_sort(self):
        """编辑市场指数排序"""
        self._edit_nav_sort("indices", "市场指数排序")


__all__ = ["Nav2Mixin"]

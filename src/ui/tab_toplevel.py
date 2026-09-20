"""Toplevel"""
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


class ToplevelMixin:
    """Toplevel"""

    def _toplevel(self, master=None, **kwargs):
        """创建 Toplevel 并纳入统一弹窗字体管理。"""
        master = self.root if master is None else master
        w = tk.Toplevel(master, **kwargs)
        self._register_popup_for_font(w)
        return w


__all__ = ["ToplevelMixin"]

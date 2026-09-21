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
from data.snapshot import *  # get_news_stocks_* 函数

import threading
import traceback
import hashlib
from urllib.parse import urljoin

class ToplevelMixin:
    """Toplevel"""

    def _toplevel(self, master=None, **kwargs):
        """创建 Toplevel 并纳入统一弹窗字体管理。"""
        master = self.root if master is None else master
        w = tk.Toplevel(master, **kwargs)
        self._register_popup_for_font(w)
        return w

    def _safe_toplevel(self, master=None, **kwargs):
        """安全 Toplevel — 自动安装 after 回调保护 + WM_DELETE_WINDOW。

        防止后台 threading.Thread 通过 win.after(0, cb) 调度回调时,
        用户先关掉窗口 → TclError('invalid command name ...') 风暴。
        返回值 w 自带:
            w._win_alive   [bool] 可被外部线程检查窗口是否存活
            w._safe_after(delay, cb, *args)  安全版 after (自动吞 TclError)
        """
        master = self.root if master is None else master
        w = self._toplevel(master, **kwargs)
        w._win_alive = True
        _orig_after = w.after

        def _safe_after(delay, cb, *args):
            if not getattr(w, '_win_alive', False):
                return None
            def _wrapper(*a):
                if not getattr(w, '_win_alive', False):
                    return
                try:
                    if not w.winfo_exists():
                        w._win_alive = False
                        return
                except Exception:
                    w._win_alive = False
                    return
                try:
                    cb(*a)
                except tk.TclError:
                    pass
            try:
                return _orig_after(delay, _wrapper, *args)
            except Exception:
                return None

        w.after = _safe_after
        w._safe_after = _safe_after

        def _on_win_close():
            w._win_alive = False
            try:
                w.destroy()
            except Exception:
                pass

        try:
            w.protocol("WM_DELETE_WINDOW", _on_win_close)
        except Exception:
            pass
        return w


__all__ = ["ToplevelMixin"]

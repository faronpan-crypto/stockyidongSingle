"""定时/调度/后台任务"""
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


class ScheduleMixin:
    """定时/调度/后台任务"""

    def _log_skill_scheduler(self, msg):
        """记录调度器日志(保留最近 200 条)"""
        ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
        self._skill_scheduler_log.append((ts, msg))
        if len(self._skill_scheduler_log) > 200:
            self._skill_scheduler_log = self._skill_scheduler_log[-200:]
        print(f"[SkillScheduler {ts}] {msg}")

    def _skill_scheduler_tick(self):
        """全局轮询器:每 20 秒遍历 self._scheduled_skills 中 active 任务,命中时间则执行并入库"""
        try:
            import datetime as _dt
            now = _dt.datetime.now()
            cur_hm = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")
            for task in self._scheduled_skills:
                if not task.get("active", True):
                    continue
                times = task.get("times", [])
                if not times:
                    continue
                # 初始化 last_fired
                if not isinstance(task.get("last_fired"), dict):
                    task["last_fired"] = {}
                fired_set = task["last_fired"].get(today)
                if fired_set is None:
                    fired_set = set()
                    task["last_fired"][today] = fired_set
                    # 清理旧天(只保留最近 3 天)
                    keys = sorted(task["last_fired"].keys())
                    if len(keys) > 3:
                        for old in keys[:-3]:
                            task["last_fired"].pop(old, None)
                if cur_hm in times and cur_hm not in fired_set:
                    fired_set.add(cur_hm)
                    task["last_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    self._log_skill_scheduler(f"触发 {cur_hm} → {task.get('skill_name')}")
                    self._run_scheduled_task(task, cur_hm)
            # 保存(任务可能更新了 last_run/last_fired)
            self._save_scheduled_skills()
        except Exception as e:
            self._log_skill_scheduler(f"tick 异常: {e}")
        # 下一次轮询
        try:
            self._skill_scheduler_after_id = self.root.after(20000, self._skill_scheduler_tick)
        except Exception:
            pass


__all__ = ["ScheduleMixin"]

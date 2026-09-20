"""默认配置"""
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


class DefaultConfigMixin:
    """默认配置"""

    def set_merged_as_default_config(self):
        """将合并标签页的当前配置设定为默认值(更新配置文件)"""
        if messagebox.askyesno("确认", "确定要将当前【市场指数&热点导航】配置设定为新的默认值吗?\n\n这将更新配置文件,包括市场指数、财经/量化平台和热门榜单的配置。"):
            try:
                # 获取当前配置
                indices_data = self.market_nav_config.get("indices", [])
                portals_data = self.market_nav_config.get("portals", [])
                hot_sources_data = self.market_nav_config.get("hot_sources", [])
                # 清理数据(移除_type标记,但保留其他所有字段包括颜色)
                cleaned_indices = []
                for item in indices_data:
                    cleaned = {k: v for k, v in item.items() if k != "_type"}
                    if "sort_order" not in cleaned:
                        cleaned["sort_order"] = len(cleaned_indices) + 1
                    cleaned_indices.append(cleaned)
                cleaned_portals = []
                for item in portals_data:
                    cleaned = {k: v for k, v in item.items() if k != "_type"}
                    if "sort_order" not in cleaned:
                        cleaned["sort_order"] = len(cleaned_portals) + 1
                    cleaned_portals.append(cleaned)
                cleaned_hot_sources = []
                for item in hot_sources_data:
                    cleaned = {k: v for k, v in item.items() if k != "_type"}
                    if "sort_order" not in cleaned:
                        cleaned["sort_order"] = len(cleaned_hot_sources) + 1
                    cleaned_hot_sources.append(cleaned)
                # 更新当前配置(确保保存)
                self.market_nav_config["indices"] = cleaned_indices
                self.market_nav_config["portals"] = cleaned_portals
                self.market_nav_config["hot_sources"] = cleaned_hot_sources
                self.save_market_nav_config()
                # 同时保存为备份文件,方便查看
                import json
                backup_file = os.path.join(_APP_CONFIG_DIR, "market_nav_config_merged_default_backup.json")
                default_config = {
                    "indices": cleaned_indices,
                    "portals": cleaned_portals,
                    "hot_sources": cleaned_hot_sources,
                    "dv_accounts": self.market_nav_config.get("dv_accounts", [])
                }
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"当前【市场指数&热点导航】配置已设定为默认值并保存!\n\n备份文件:{backup_file}\n\n配置已保存到配置文件,下次启动程序时会自动加载。")
            except Exception as e:
                messagebox.showerror("错误", f"设定为默认失败: {e}")
                import traceback
                traceback.print_exc()

    def set_as_default_config(self, config_key):
        """将指定配置的当前内容设定为默认值(更新配置文件)"""
        config_name_map = {
            "indices": "宏观&指数",
            "portals": "财经/量化平台",
            "hot_sources": "热门榜单",
            "dv_accounts": "大V公众号"
        }
        config_name = config_name_map.get(config_key, config_key)
        if messagebox.askyesno("确认", f"确定要将当前【{config_name}】配置设定为新的默认值吗?\n\n这将更新配置文件,下次加载时会使用这些值作为默认配置。"):
            try:
                # 获取当前配置
                data_list = self.market_nav_config.get(config_key, [])
                if not data_list:
                    messagebox.showwarning("提示", f"当前{config_name}配置为空,无法设定为默认值。")
                    return
                # 清理数据(移除_type标记,但保留其他所有字段包括颜色)
                cleaned_data = []
                for item in data_list:
                    cleaned = {k: v for k, v in item.items() if k != "_type"}
                    # 确保有排序字段
                    if "sort_order" not in cleaned:
                        cleaned["sort_order"] = len(cleaned_data) + 1
                    cleaned_data.append(cleaned)
                # 更新当前配置(确保保存)
                self.market_nav_config[config_key] = cleaned_data
                self.save_market_nav_config()
                # 同时保存为备份文件,方便查看
                import json
                backup_file = os.path.join(_APP_CONFIG_DIR, f"market_nav_config_{config_key}_default_backup.json")
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"当前【{config_name}】配置已设定为默认值并保存!\n\n备份文件:{backup_file}\n\n配置已保存到配置文件,下次启动程序时会自动加载。")
            except Exception as e:
                messagebox.showerror("错误", f"设定为默认失败: {e}")
                import traceback
                traceback.print_exc()


__all__ = ["DefaultConfigMixin"]

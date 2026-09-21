"""导航/排序/重排/上移下移"""
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

from datetime import datetime, timedelta
import json
import os
import sys
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class NavMixin:
    """导航/排序/重排/上移下移"""

    def _reorder_buttons(self, button_refs, from_idx, to_idx):
        """重新排列按钮顺序并更新排序"""
        if from_idx == to_idx:
            return
        # 移动按钮引用
        moved_item = button_refs.pop(from_idx)
        button_refs.insert(to_idx, moved_item)
        # 更新所有按钮的排序字段和网格位置
        for idx, btn_info in enumerate(button_refs):
            btn_info["index"] = idx
            btn_info["row"] = idx // 3
            btn_info["col"] = idx % 3
            btn_info["item"]["sort_order"] = idx + 1
            # 更新按钮的网格位置
            btn_info["button"].grid(row=btn_info["row"], column=btn_info["col"], padx=4, pady=3, sticky="ew")
        # 保存配置
        # 分别更新indices、portals和hot_sources的排序
        indices_data = []
        portals_data = []
        hot_sources_data = []
        for btn_info in button_refs:
            item = btn_info["item"].copy()  # 复制item,避免修改原始数据
            item_type = item.get("_type", "")
            # 移除临时标记(但保留其他所有字段)
            cleaned_item = {}
            # 保留所有有效字段
            for key, value in item.items():
                if key != "_type":  # 只移除_type标记
                    cleaned_item[key] = value
            # 确保保留所有字段(名称、链接、描述、颜色、排序等)
            if item_type == "indices":
                indices_data.append(cleaned_item)
            elif item_type == "portals":
                portals_data.append(cleaned_item)
            elif item_type == "hot_sources":
                hot_sources_data.append(cleaned_item)
        # 更新配置
        self.market_nav_config["indices"] = indices_data
        self.market_nav_config["portals"] = portals_data
        self.market_nav_config["hot_sources"] = hot_sources_data
        # 保存配置
        self.save_market_nav_config()

    def _edit_nav_sort(self, key, title):
        """编辑导航排序的通用函数"""
        data_list = self.market_nav_config.get(key, [])
        # 如果数据为空,尝试从默认配置加载
        if not data_list:
            default_data = DEFAULT_MARKET_NAV_CONFIG.get(key, [])
            if default_data:
                data_list = default_data
                self.market_nav_config[key] = data_list
                self.save_market_nav_config()
        win = self._safe_toplevel(self.root)
        win.title(title)
        win.geometry("600x500")
        # 创建列表和排序控件
        list_frame = ttk.Frame(win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # 列表显示
        listbox = tk.Listbox(list_frame, height=15)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 排序按钮
        sort_btn_frame = ttk.Frame(list_frame)
        sort_btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ttk.Button(sort_btn_frame, text="↑", command=lambda: self._move_item_up(listbox, data_list)).pack(pady=2)
        ttk.Button(sort_btn_frame, text="↓", command=lambda: self._move_item_down(listbox, data_list)).pack(pady=2)
        # 刷新列表
        def refresh_list():
            listbox.delete(0, tk.END)
            if not data_list:
                listbox.insert(tk.END, "暂无数据,请在编辑导航中添加")
            else:
                # 按排序字段排序
                sorted_list = sorted(data_list, key=lambda x: x.get("sort_order", 999))
                for idx, item in enumerate(sorted_list):
                    sort_order = item.get("sort_order", idx + 1)
                    name = item.get("name", "")
                    listbox.insert(tk.END, f"{sort_order}. {name}")
        refresh_list()
        # 保存按钮
        def save_sort():
            # 更新排序字段
            for idx, item in enumerate(data_list):
                item["sort_order"] = idx + 1
            self.market_nav_config[key] = data_list
            self.save_market_nav_config()
            # 刷新合并标签页(如果key是indices,需要刷新合并标签页)
            if key == "indices":
                self._create_merged_market_hot_tab()
            win.destroy()
        ttk.Button(win, text="保存", command=save_sort).pack(pady=10)

    def _move_item_up(self, listbox, data_list):
        """向上移动列表项"""
        selection = listbox.curselection()
        if not selection or selection[0] == 0:
            return
        idx = selection[0]
        # 交换数据
        data_list[idx], data_list[idx - 1] = data_list[idx - 1], data_list[idx]
        # 刷新显示
        listbox.delete(0, tk.END)
        for i, item in enumerate(data_list):
            sort_order = item.get("sort_order", i + 1)
            name = item.get("name", "")
            listbox.insert(tk.END, f"{sort_order}. {name}")
        listbox.selection_set(idx - 1)

    def _move_item_down(self, listbox, data_list):
        """向下移动列表项"""
        selection = listbox.curselection()
        if not selection or selection[0] == len(data_list) - 1:
            return
        idx = selection[0]
        # 交换数据
        data_list[idx], data_list[idx + 1] = data_list[idx + 1], data_list[idx]
        # 刷新显示
        listbox.delete(0, tk.END)
        for i, item in enumerate(data_list):
            sort_order = item.get("sort_order", i + 1)
            name = item.get("name", "")
            listbox.insert(tk.END, f"{sort_order}. {name}")
        listbox.selection_set(idx + 1)

    def load_market_nav_config(self):
        """加载市场导航配置(打包后优先 D:\\StockAnalyzer,其次 exe 同目录,与原程序初始化一致)"""
        config = copy.deepcopy(DEFAULT_MARKET_NAV_CONFIG)
        config_path = _resolve_market_nav_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                for key in config:
                    user_list = user_config.get(key)
                    if isinstance(user_list, list) and len(user_list) > 0:
                        # 特殊处理:ai_search_questions是字符串列表
                        if key == "ai_search_questions":
                            sanitized = [str(item).strip() for item in user_list if item and str(item).strip()]
                            if sanitized:
                                config[key] = sanitized
                        else:
                            # 其他配置项是字典列表
                            sanitized = []
                            for item in user_list:
                                if not isinstance(item, dict):
                                    continue
                                name = str(item.get("name", "")).strip()
                                url = str(item.get("url", "")).strip()
                                if not name or not url:
                                    continue
                                entry = {"name": name, "url": url}
                                desc = str(item.get("desc", "")).strip()
                                if desc:
                                    entry["desc"] = desc
                                # 保留所有其他字段(颜色、字体大小等)
                                for field in ["bg_color", "fg_color", "font_size", "sort_order"]:
                                    if field in item:
                                        entry[field] = item[field]
                                # 如果没有排序字段,设置一个
                                if "sort_order" not in entry:
                                    entry["sort_order"] = len(sanitized) + 1
                                sanitized.append(entry)
                            if sanitized:
                                config[key] = sanitized
                    # 如果用户配置为空数组,保持默认配置(不覆盖,让用户手动恢复)
                    elif isinstance(user_list, list) and len(user_list) == 0:
                        # 保持默认配置,不覆盖
                        pass
                # 处理用户配置中存在但默认配置中不存在的键(如ai_search_questions)
                for key in user_config:
                    if key not in config:
                        if key == "ai_search_questions" and isinstance(user_config[key], list):
                            config[key] = [str(item).strip() for item in user_config[key] if item and str(item).strip()]
        except Exception as e:
            print(f"加载市场导航配置失败: {e}")
        # 确保ai_search_questions存在
        if "ai_search_questions" not in config:
            config["ai_search_questions"] = []
        return config

    def save_market_nav_config(self):
        """保存市场导航配置(打包后写入 D:\\StockAnalyzer 或 exe 同目录)"""
        config_path = _resolve_market_nav_config_path()
        try:
            if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
                parent = os.path.dirname(config_path)
                if parent and parent != os.path.dirname(sys.executable):
                    os.makedirs(parent, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.market_nav_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存市场导航配置失败: {e}")

    def restore_default_market_nav_config(self):
        """恢复默认市场导航配置"""
        if messagebox.askyesno("确认", "确定要恢复默认配置吗?这将覆盖当前的配置,但会保留您已编辑的数据(如果存在)。"):
            try:
                # 合并默认配置和当前配置,保留用户自定义的颜色等设置
                restored_config = copy.deepcopy(DEFAULT_MARKET_NAV_CONFIG)
                # 为每个配置项设置排序字段
                for key in restored_config:
                    for idx, item in enumerate(restored_config[key]):
                        item["sort_order"] = idx + 1
                # 如果当前配置中有数据,询问是否合并
                for key in self.market_nav_config:
                    if isinstance(self.market_nav_config.get(key), list) and len(self.market_nav_config[key]) > 0:
                        # 检查是否有不在默认配置中的数据
                        default_names = {item.get("name") for item in restored_config.get(key, [])}
                        custom_items = [item for item in self.market_nav_config[key]
                                      if item.get("name") not in default_names]
                        if custom_items:
                            # 合并自定义数据
                            restored_config[key].extend(custom_items)
                            # 重新设置排序
                            for idx, item in enumerate(restored_config[key]):
                                item["sort_order"] = idx + 1
                self.market_nav_config = restored_config
                self.save_market_nav_config()
                # 刷新界面
                if hasattr(self, 'market_nav_container'):
                    self._build_market_nav_section(self.market_nav_container)
                messagebox.showinfo("成功", "默认配置已恢复!")
            except Exception as e:
                messagebox.showerror("错误", f"恢复默认配置失败: {e}")
                import traceback
                traceback.print_exc()

    def _handle_market_nav_click(self, name, url, desc=None):
        """打开链接并一键复制内容到新的文本标签页"""
        if not url:
            messagebox.showwarning("提示", "该导航暂未配置有效链接")
            return
        # 始终先在浏览器中打开
        self._open_market_link(url)
        if not hasattr(self, "_market_nav_fetching"):
            self._market_nav_fetching = set()
        if url in self._market_nav_fetching:
            print(f"正在抓取 {url},请稍候...")
            return
        self._market_nav_fetching.add(url)
        threading.Thread(
            target=self._fetch_market_nav_content,
            args=(name, url, desc),
            daemon=True
        ).start()

    def _fetch_market_nav_content(self, name, url, desc=None):
        """抓取市场导航链接内容并生成新的文本标签页"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        try:
            html_content, used_encoding = self._fetch_with_encoding_fix(url, headers, max_retries=1)
            if not html_content:
                raise ValueError("未能获取网页内容")
            soup = BeautifulSoup(html_content, 'html.parser')
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            text_content = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            cleaned_text = '\n'.join(lines).strip()
            if not cleaned_text:
                cleaned_text = "⚠️ 未提取到有效文本内容,可能需要手动复制。"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            meta_lines = [
                "=" * 80,
                f"来源: {name}",
                f"链接: {url}",
                f"抓取时间: {timestamp}"
            ]
            if desc:
                meta_lines.append(f"描述: {desc}")
            if used_encoding:
                meta_lines.append(f"编码: {used_encoding}")
            meta_lines.append("=" * 80)
            header_text = '\n'.join(meta_lines)
            tab_title = f"{name}{datetime.now().strftime('%H:%M')}"
            full_text = f"{header_text}\n\n{cleaned_text}"
            def create_tab():
                self.create_text_tab(tab_title, full_text)
            self.root.after(0, create_tab)
        except Exception as exc:
            print(f"抓取 {name} ({url}) 失败: {exc}")
        finally:
            if hasattr(self, "_market_nav_fetching"):
                self._market_nav_fetching.discard(url)

    def import_market_nav_data(self):
        """一键导入市场指数与热点导航配置"""
        try:
            raw_text = ""
            file_path = filedialog.askopenfilename(
                title="选择导航数据文件(JSON或文本)",
                filetypes=[("JSON Files", "*.json"), ("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            if file_path:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
            else:
                try:
                    raw_text = self.root.clipboard_get()
                    if not raw_text.strip():
                        raise ValueError("剪贴板为空")
                except Exception:
                    messagebox.showwarning("提示", "未选择文件,且剪贴板无有效内容。")
                    return
            parsed = self._parse_market_nav_import_data(raw_text)
            if not parsed or not any(parsed.values()):
                messagebox.showwarning(
                    "提示",
                    "未识别到有效的导航数据。\n支持 JSON 或按行 “类型|名称|链接|描述(可选)“ 的文本格式。"
                )
                return
            overwrite = messagebox.askyesno(
                "导入导航数据",
                "是否覆盖现有导航配置?\n选择“否“则在原有基础上追加。"
            )
            updated = False
            for key, items in parsed.items():
                if not items:
                    continue
                if overwrite:
                    self.market_nav_config[key] = self._deduplicate_nav_entries(items)
                else:
                    existing = self.market_nav_config.setdefault(key, [])
                    existing.extend(items)
                    self.market_nav_config[key] = self._deduplicate_nav_entries(existing)
                updated = True
            if not updated:
                messagebox.showinfo("提示", "没有可导入的有效数据。")
                return
            self.save_market_nav_config()
            self._build_market_nav_section(self.market_nav_container)
            messagebox.showinfo("成功", "导航数据已导入并生成。")
        except Exception as exc:
            messagebox.showerror("错误", f"导入导航数据失败: {exc}")

    def _map_market_nav_category(self, token):
        if not token:
            return None
        token = str(token).strip().lower()
        mapping = {
            "indices": "indices",
            "index": "indices",
            "macro": "indices",
            "指数": "indices",
            "宏观": "indices",
            "macro/index": "indices",
            "portal": "portals",
            "portals": "portals",
            "platform": "portals",
            "platforms": "portals",
            "site": "portals",
            "sites": "portals",
            "财经": "portals",
            "量化": "portals",
            "hot": "hot_sources",
            "hotlist": "hot_sources",
            "hot_sources": "hot_sources",
            "热门": "hot_sources",
            "榜单": "hot_sources",
            "dv": "dv_accounts",
            "dva": "dv_accounts",
            "大v": "dv_accounts",
            "公众号": "dv_accounts",
            "大v公众号": "dv_accounts",
            "opinion": "dv_accounts",
            "kol": "dv_accounts"
        }
        return mapping.get(token)

    def _deduplicate_nav_entries(self, items):
        seen = set()
        deduped = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            url = item.get("url")
            if not name or not url:
                continue
            key = (name.strip(), url.strip())
            if key in seen:
                continue
            seen.add(key)
            cleaned = {"name": name.strip(), "url": url.strip()}
            desc = item.get("desc")
            if desc:
                cleaned["desc"] = desc.strip()
            deduped.append(cleaned)
        return deduped

    def show_market_nav_editor(self, default_tab=None):
        """显示导航编辑窗口
        Args:
            default_tab: 默认显示的标签页索引(0=宏观&指数, 1=财经/量化平台, 2=热门榜单)
        """
        try:
            if self._nav_editor_window and self._nav_editor_window.winfo_exists():
                self._nav_editor_window.lift()
                self._nav_editor_window.focus_force()
                # 如果指定了默认标签页,切换到该标签页
                if default_tab is not None:
                    try:
                        notebook = None
                        for widget in self._nav_editor_window.winfo_children():
                            if isinstance(widget, ttk.Notebook):
                                notebook = widget
                                break
                        if notebook and default_tab < notebook.index("end"):
                            notebook.select(default_tab)
                    except Exception:
                        pass
                return
        except Exception:
            self._nav_editor_window = None
        win = self._safe_toplevel(self.root)
        win.title("编辑市场指数与热点导航")
        win.geometry("780x560")
        win.transient(self.root)
        self._nav_editor_window = win
        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        editor_specs = [
            ("宏观 & 指数", "indices", True),
            ("财经/量化平台", "portals", False),
            ("热门榜单", "hot_sources", False),
            ("大V公众号", "dv_accounts", True)
        ]
        for title, key, has_desc in editor_specs:
            self._create_nav_editor_tab(notebook, title, key, has_desc)
        # 如果指定了默认标签页,切换到该标签页
        if default_tab is not None and default_tab < len(editor_specs):
            notebook.select(default_tab)
        ttk.Label(
            win,
            text="提示:修改会立即保存,并刷新快速爬取界面的导航区。",
            foreground="gray"
        ).pack(fill=tk.X, padx=10, pady=(0, 10))

    def _signal_ma1_close_crossed_up_last_bar(self, stock_code):
        """仅用日K收盘价:前一日收盘未站上1日线(昨收<前收),最后一日收盘站上1日线(收盘≥昨收)。
        与 _check_ma_status 中 1 日线一致;供「信号」与「持仓检测」共用。"""
        try:
            code = str(stock_code).strip().zfill(6)
            if not code:
                return False
            result = self._fetch_recent_daily_closes(
                code, days=12, source="default", token=self.ts_token, return_volume=False
            )
            if isinstance(result, tuple) and len(result) >= 2:
                closes = result[1]
            else:
                closes = result if isinstance(result, list) else []
            if not closes or len(closes) < 3:
                return False
            c0 = float(closes[-3])
            c1 = float(closes[-2])
            c2 = float(closes[-1])
            if c0 <= 0:
                return False
            prev_day_not_above = c1 < c0
            last_close_above = c2 >= c1
            return bool(prev_day_not_above and last_close_above)
        except Exception:
            return False


__all__ = ["NavMixin"]

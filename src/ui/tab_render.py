"""渲染/图片"""
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
import re
import os
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class RenderMixin:
    """渲染/图片"""

    def _copy_text_to_clipboard(self, text_widget):
        """复制文本到剪贴板"""
        try:
            content = text_widget.get("1.0", tk.END).strip()
            if content:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                messagebox.showinfo("成功", "结果已复制到剪贴板")
            else:
                messagebox.showinfo("提示", "没有可复制的内容")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {e}")

    def _enable_text_copy_menu(text_widget, readonly=True):
        """
        给任意 Text / ScrolledText 组件加上:
          1. 右键菜单(复制 / 全选 / 粘贴 / 剪切 / 清空)
          2. Cmd+A (macOS) / Ctrl+A (Win/Linux) 全选快捷键
          3. 拖拽选中 + 双击选词(Tk 自带)
        readonly=True 时只保留 复制/全选,禁用粘贴/剪切/清空
        """
        w = text_widget
        def _copy():
            try:
                sel = w.get("sel.first", "sel.last")
                if sel:
                    w.clipboard_clear()
                    w.clipboard_append(sel)
                    w.update()
            except tk.TclError:
                pass  # 没有选中
        def _select_all():
            w.tag_add("sel", "1.0", "end-1c")
            w.mark_set("insert", "1.0")
            w.see("insert")
        def _paste():
            if readonly:
                return
            try:
                clip = w.clipboard_get()
                if clip:
                    w.insert("insert", clip)
            except tk.TclError:
                pass
        def _cut():
            if readonly:
                return
            try:
                sel = w.get("sel.first", "sel.last")
                if sel:
                    w.clipboard_clear()
                    w.clipboard_append(sel)
                    w.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
        def _clear():
            if readonly:
                return
            w.delete("1.0", tk.END)
        menu = tk.Menu(w, tearoff=0)
        menu.add_command(label="📋 复制 (⌘C)", command=_copy)
        menu.add_command(label="☑️ 全选 (⌘A)", command=_select_all)
        if not readonly:
            menu.add_separator()
            menu.add_command(label="✂️ 剪切 (⌘X)", command=_cut)
            menu.add_command(label="📌 粘贴 (⌘V)", command=_paste)
            menu.add_separator()
            menu.add_command(label="🗑️ 清空", command=_clear)
        def _show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        # macOS 右键是 Button-2,Windows/Linux 是 Button-3
        w.bind("<Button-2>", _show_menu)
        w.bind("<Button-3>", _show_menu)
        # 全选快捷键
        w.bind("<Command-a>", lambda e: (_select_all(), "break"))
        w.bind("<Control-a>", lambda e: (_select_all(), "break"))
        w.bind("<Command-A>", lambda e: (_select_all(), "break"))
        w.bind("<Control-A>", lambda e: (_select_all(), "break"))
        # 复制快捷键(Tk 默认只在 Entry/Spinbox 工作,Text 手动绑定更可靠)
        w.bind("<Command-c>", lambda e: (_copy(), "break"))
        w.bind("<Control-c>", lambda e: (_copy(), "break"))
        w.bind("<Command-C>", lambda e: (_copy(), "break"))
        w.bind("<Control-C>", lambda e: (_copy(), "break"))
        if not readonly:
            w.bind("<Command-v>", lambda e: (_paste(), "break"))
            w.bind("<Control-v>", lambda e: (_paste(), "break"))
            w.bind("<Command-x>", lambda e: (_cut(), "break"))
            w.bind("<Control-x>", lambda e: (_cut(), "break"))
        return w

    def _render_text_to_long_image(text, title="", bg_color="#FFFFFF",
                                    text_color="#212121", title_color="#333333",
                                    width_px=1080, font_size=16, line_height_factor=1.7):
        """把任意长文本渲染成长图 PNG（用 matplotlib，返回文件路径）。
        可设置背景色、标题、字体大小等。"""
        import matplotlib
        matplotlib.use("Agg")
        import os
        import tempfile

        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        # --- 尝试找一个支持中文的字体 ---
        _cjk_fonts = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            # Windows fallback
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
        _font_path = None
        for _f in _cjk_fonts:
            if os.path.exists(_f):
                _font_path = _f
                break
        if _font_path:
            _fp = FontProperties(fname=_font_path, size=font_size)
            _title_fp = FontProperties(fname=_font_path, size=font_size + 4, weight="bold")
            _body_fp = _fp
        else:
            _fp = FontProperties(size=font_size)
            _title_fp = FontProperties(size=font_size + 4, weight="bold")
            _body_fp = _fp
        # --- 把文字按宽度换行（matplotlib 不自动换行） ---
        # 去掉 emoji（Heiti/PingFang 字体不含 emoji 字形）
        import re as _re
        _emoji_pattern = _re.compile(
            "[" "\U0001F000-\U0001FFFF" "\U00002600-\U000027BF"
            "\U0001F300-\U0001F5FF" "\U0001F600-\U0001F64F"
            "\U0001F680-\U0001F6FF" "\U0001F700-\U0001F77F"
            "\U0001F900-\U0001F9FF" "\U000025AA-\U000025FE"
            "\U0001FA00-\U0001FA6F" "\U0001FA70-\U0001FAFF" "]+",
            flags=_re.UNICODE)
        # 估算每个字符占的宽度（中文≈1个fontsize，英文≈0.55）
        char_w = font_size * 0.62
        max_chars_per_line = max(20, int((width_px - 100) / char_w))
        lines_raw = text.split("\n")
        wrapped = []
        for raw in lines_raw:
            # 处理 markdown 粗体 **text** — matplotlib 不支持，去掉 **
            raw_clean = raw.replace("**", "").replace("__", "")
            # 去掉 emoji
            raw_clean = _emoji_pattern.sub("", raw_clean).strip()
            if not raw_clean:
                wrapped.append("")
                continue
            if len(raw_clean) <= max_chars_per_line:
                wrapped.append(raw_clean)
            else:
                # 硬换行
                for j in range(0, len(raw_clean), max_chars_per_line):
                    wrapped.append(raw_clean[j:j + max_chars_per_line])
        # --- 计算图片尺寸（所有像素值 → 最后统一 / dpi 转英寸）---
        margin_top = 60
        margin_bottom = 40
        line_h = font_size * line_height_factor
        title_h = (font_size + 4) * 1.8 if title else 0
        content_h = len(wrapped) * line_h
        total_h_px = int(margin_top + title_h + content_h + margin_bottom + 20)
        # 最小 400px, 最大 6000px 防止 PIL DecompressionBomb
        total_h_px = max(400, min(6000, total_h_px))
        dpi = 100
        w_in = width_px / dpi
        h_in = total_h_px / dpi
        fig = plt.figure(figsize=(w_in, h_in), dpi=dpi)
        fig.patch.set_facecolor(bg_color)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.set_facecolor(bg_color)
        # --- 画标题（坐标用 px，matplotlib 会自动按 dpi 映射）---
        y_cursor = total_h_px - margin_top
        if title:
            ax.text(width_px / 2 / dpi, y_cursor / dpi, title,
                    fontproperties=_title_fp, color=title_color,
                    ha="center", va="top")
            y_cursor -= title_h + 10
            # 分隔线
            ax.plot([60 / dpi, (width_px - 60) / dpi],
                    [(y_cursor - 4) / dpi, (y_cursor - 4) / dpi],
                    color="#CCCCCC", linewidth=1)
            y_cursor -= 20
        # --- 画正文 ---
        x_start = 60
        for line in wrapped:
            ax.text(x_start / dpi, y_cursor / dpi, line,
                    fontproperties=_body_fp, color=text_color,
                    ha="left", va="top")
            y_cursor -= line_h
            if y_cursor < 20:
                break
        # --- 保存 ---
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        fig.savefig(tmp.name, dpi=dpi, bbox_inches="tight", pad_inches=0.1,
                    facecolor=bg_color, edgecolor="none")
        plt.close(fig)
        return tmp.name

    def _pick_custom_bg(current_bg_list, current_text_list, redraw_cb):
        """弹颜色选择器，支持自定义背景色。"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(title="选一个背景色")
        if color and color[1]:
            current_bg_list[0] = color[1]
            # 白色系背景用深字，深色背景用白字
            r, g, b = color[0]
            brightness = (r + g + b) / 3
            current_text_list[0] = "#FFFFFF" if brightness < 128 else "#212121"
            redraw_cb()

    def create_text_tab(self, title, initial_text="", bg_color=None):
        """创建新的文本标签页
        Args:
            title: 标签页标题
            initial_text: 初始文本内容
            bg_color: 背景颜色(可选)
        """
        self.tab_counter += 1
        tab_id = f"tab_{self.tab_counter}"
        # 创建标签页框架
        tab_frame = ttk.Frame(self.text_notebook)
        # 缩短标签页名称(如果太长)
        display_title = title
        if len(title) > 15:
            display_title = title[:12] + "..."
        self.text_notebook.add(tab_frame, text=display_title)
        # 如果没有指定背景色,使用默认白色
        if bg_color is None:
            bg_color = 'white'
        # 根据情绪周期确定背景颜色(如果未指定)
        if bg_color is None or bg_color == 'white':
            if hasattr(self, 'get_emotion_bg_color'):
                bg_color = self.get_emotion_bg_color()
        # 创建文本框和滚动条(固定宽度,不随标签页变化)
        text_widget = tk.Text(tab_frame, height=15, width=45, font=("TkDefaultFont", 16),
                             wrap=tk.WORD, undo=True, maxundo=50, bg=bg_color)
        scrollbar = tk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        # 配置颜色标签
        color_tags = [
            ("red", "red"), ("orange", "orange"), ("green", "green"),
            ("blue", "blue"), ("purple", "purple"), ("black", "black")
        ]
        for tag_name, color in color_tags:
            text_widget.tag_configure(tag_name, foreground=color)
        # 绑定事件
        text_widget.bind('<Control-v>', self.on_paste)
        text_widget.bind('<KeyRelease>', self.on_text_change)
        text_widget.bind('<Button-3>', self.show_context_menu)
        # 绑定双击事件,打开全窗口浏览
        text_widget.bind('<Double-Button-1>', lambda e, tid=tab_id: self.open_full_window_viewer(tid))
        # 布局
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 创建顶部工具栏(包含关闭按钮和图片插入按钮)
        toolbar = ttk.Frame(tab_frame)
        toolbar.pack(fill=tk.X, padx=2, pady=2, side=tk.TOP)
        # 如果是咨询标签页,添加图片插入按钮
        if title.startswith("咨询"):
            # 插入图片按钮
            insert_img_btn = ttk.Button(toolbar, text="📷 插入图片",
                                       command=lambda: self.insert_image_to_tab(tab_id))
            insert_img_btn.pack(side=tk.LEFT, padx=2)
            # 粘贴图片按钮
            paste_img_btn = ttk.Button(toolbar, text="📋 粘贴图片",
                                      command=lambda: self.paste_image_to_tab(tab_id))
            paste_img_btn.pack(side=tk.LEFT, padx=2)
        # 关闭按钮(使用×符号,更紧凑)
        close_btn = ttk.Button(toolbar, text="×", width=3,
                              command=lambda: self.close_tab(tab_id))
        close_btn.pack(side=tk.RIGHT, padx=2)
        # 插入初始文本
        if initial_text:
            # 如果文本包含图片标记,使用解析方法
            if "[IMAGE:" in initial_text:
                self.parse_and_display_images(text_widget, initial_text)
            else:
                text_widget.insert("1.0", initial_text)
        # 存储引用
        self.text_widgets[tab_id] = {
            'widget': text_widget,
            'title': title,
            'frame': tab_frame
        }
        # 切换到新标签页
        self.text_notebook.select(tab_frame)
        self.update_text_input_reference()
        return tab_id

    def save_image_file(self, image_path_or_data, is_file_path=True):
        """保存图片文件到日期目录
        Args:
            image_path_or_data: 图片文件路径或图片数据(PIL Image对象)
            is_file_path: True表示是文件路径,False表示是PIL Image对象
        Returns:
            保存的相对路径(相对于D_IMAGES_DIR)
        """
        try:
            image_dir = self.get_image_save_directory()
            today = datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if is_file_path:
                # 从文件路径复制
                if not os.path.exists(image_path_or_data):
                    return None
                ext = os.path.splitext(image_path_or_data)[1] or '.png'
                filename = f"img_{timestamp}{ext}"
                dest_path = os.path.join(image_dir, filename)
                shutil.copy2(image_path_or_data, dest_path)
            else:
                # 从PIL Image对象保存
                filename = f"img_{timestamp}.png"
                dest_path = os.path.join(image_dir, filename)
                image_path_or_data.save(dest_path, 'PNG')
            # 返回相对路径(相对于D_IMAGES_DIR)
            relative_path = os.path.join(today, filename)
            return relative_path
        except Exception as e:
            messagebox.showerror("错误", f"保存图片失败: {e}")
            return None


__all__ = ["RenderMixin"]

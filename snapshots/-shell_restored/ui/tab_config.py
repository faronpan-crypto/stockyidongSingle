"""配置/设置/主题/对话框/弹窗"""
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
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
except ImportError: plt = None
from utils.network import safe_call
from utils.config import *  # 路径/配置/Token
from data.snapshot import *  # get_news_stocks_* 函数

from datetime import datetime, timedelta
import re
import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class ConfigMixin:
    """配置/设置/主题/对话框/弹窗"""

    def _popup_font_family(self):
        import tkinter.font as tkfont
        try:
            return tkfont.nametofont("TkDefaultFont").cget("family")
        except Exception:
            return "Microsoft YaHei UI"

    def _register_popup_for_font(self, w):
        if w is None:
            return
        lst = getattr(self, "_popup_windows", None)
        if lst is None:
            self._popup_windows = []
            lst = self._popup_windows
        if w in lst:
            return
        lst.append(w)
        def _on_destroy(event, ref=w, L=lst):
            if event.widget is not ref:
                return
            try:
                L.remove(ref)
            except ValueError:
                pass
        w.bind("<Destroy>", _on_destroy)
        for delay in (1, 120, 400):
            try:
                w.after(delay, lambda ww=w: self._apply_popup_fonts_to_toplevel(ww))
            except Exception:
                pass

    def _configure_popup_text_font(self, ch, fam, sz):
        import tkinter.font as tkfont
        try:
            cur = ch.cget("font")
        except Exception:
            try:
                ch.configure(font=(fam, sz))
            except Exception:
                pass
            return
        fam_use, bold = fam, False
        if isinstance(cur, str):
            try:
                fn = tkfont.nametofont(cur)
                act = fn.actual()
                base = act.get("family", fam)
                if str(base).lower() in ("consolas", "courier", "courier new", "monaco", "menlo"):
                    fam_use = base
                else:
                    fam_use = fam
                bold = str(act.get("weight", "normal")).lower() == "bold"
            except Exception:
                fam_use = fam
        elif isinstance(cur, (tuple, list)) and len(cur) >= 2:
            base = cur[0]
            if str(base).lower() in ("consolas", "courier", "courier new", "monaco", "menlo"):
                fam_use = base
            if (len(cur) >= 3 and str(cur[2]).lower() == "bold") or (
                len(cur) == 2 and str(cur[1]).lower() == "bold"
            ):
                bold = True
        try:
            if bold:
                ch.configure(font=(fam_use, sz, "bold"))
            else:
                ch.configure(font=(fam_use, sz))
        except Exception:
            try:
                ch.configure(font=(fam, sz))
            except Exception:
                pass

    def _apply_popup_fonts_recursive(self, widget, fam, sz):
        for ch in widget.winfo_children():
            try:
                if isinstance(ch, (scrolledtext.ScrolledText, tk.Text)):
                    self._configure_popup_text_font(ch, fam, sz)
                elif isinstance(ch, (tk.Entry, tk.Listbox, tk.Label, tk.Button, tk.Menubutton, tk.Checkbutton, tk.Radiobutton, tk.Spinbox)):
                    ch.configure(font=(fam, sz))
            except Exception:
                pass
            try:
                self._apply_popup_fonts_recursive(ch, fam, sz)
            except Exception:
                pass

    def _apply_popup_fonts_to_toplevel(self, win):
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        try:
            sz = int(self.popup_font_size_var.get())
        except Exception:
            sz = 11
        sz = max(self._popup_font_min, min(self._popup_font_max, sz))
        fam = self._popup_font_family()
        try:
            win.option_add("*Font", (fam, sz))
        except Exception:
            try:
                win.option_add("*Font", f"{fam} {sz}")
            except Exception:
                pass
        try:
            sty = ttk.Style(win)
            for name in (
                "TLabel",
                "TButton",
                "TCheckbutton",
                "TRadiobutton",
                "TEntry",
                "TCombobox",
                "Treeview",
                "Treeview.Heading",
                "TNotebook.Tab",
                "TSpinbox",
                "TScale",
                "TLabelframe",
                "TLabelframe.Label",
                "TMenubutton",
            ):
                try:
                    sty.configure(name, font=(fam, sz))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._apply_popup_fonts_recursive(win, fam, sz)
        except Exception:
            pass
        try:
            self._schedule_rt_news_link_reapply_under_win(win)
        except Exception:
            pass

    def commit_popup_font_size(self):
        """保存弹窗字号并刷新已打开的弹窗。"""
        try:
            v = int(self.popup_font_size_var.get())
        except Exception:
            return
        v = max(self._popup_font_min, min(self._popup_font_max, v))
        self.popup_font_size_var.set(v)
        try:
            self.ai_config_manager.config["popup_font_size"] = v
            self.ai_config_manager.save_config()
        except Exception:
            pass
        self.refresh_all_popup_fonts()

    def refresh_all_popup_fonts(self):
        for w in list(getattr(self, "_popup_windows", [])):
            try:
                if w.winfo_exists():
                    self._apply_popup_fonts_to_toplevel(w)
            except Exception:
                pass

    def _refresh_single_config_tab(self, config_key):
        """刷新单个配置的标签页"""
        if not hasattr(self, 'market_notebook') or not self.market_notebook:
            return
        tab_text_map = {
            "indices": "宏观&指数",
            "dv_accounts": "大V公众号"
        }
        title_map = {
            "indices": "影响股市情绪与流动性的核心指标:",
            "dv_accounts": "精选财经大V公众号:点击打开公众号介绍页,可复制文章或扫码关注。"
        }
        tab_text = tab_text_map.get(config_key)
        title_text = title_map.get(config_key)
        if not tab_text or not title_text:
            return
        # 查找对应的标签页
        for i in range(self.market_notebook.index("end")):
            if self.market_notebook.tab(i, "text") == tab_text:
                tab_frame = self.market_notebook.nametowidget(self.market_notebook.tabs()[i])
                self._create_draggable_button_grid(tab_frame, config_key, title_text)
                break

    def _reorder_single_config_buttons(self, button_refs, from_idx, to_idx, config_key):
        """重新排列单个配置的按钮顺序并更新排序"""
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
        # 更新配置(确保移除_type标记,但保留其他所有字段)
        data_list = []
        for btn_info in button_refs:
            item = btn_info["item"].copy()
            # 移除临时标记
            cleaned_item = {k: v for k, v in item.items() if k != "_type"}
            data_list.append(cleaned_item)
        self.market_nav_config[config_key] = data_list
        # 保存配置
        self.save_market_nav_config()

    def _open_image_popup_with_save(self, text, title="创作结果",
                                     default_bg="#FFFFFF", default_text="#212121"):
        """双击文本框 → 弹出大图预览窗口，可换背景色、保存长图。"""
        import threading
        import tkinter as tk
        from tkinter import messagebox, ttk

        from PIL import Image, ImageTk
        popup = self._safe_toplevel(self.root)
        popup.title(f"🖼️ {title} · 预览 & 保存长图")
        popup.geometry("1100x800")
        popup.minsize(900, 600)
        # --- 背景色预设 ---
        BG_PRESETS = [
            ("纯白", "#FFFFFF"),
            ("暖米", "#FFF8E1"),
            ("浅灰", "#F5F5F5"),
            ("护眼绿", "#E8F5E9"),
            ("淡紫", "#F3E5F5"),
            ("天空蓝", "#E3F2FD"),
            ("日落橙", "#FFF3E0"),
            ("深夜黑", "#1A1A2E"),
            ("樱花粉", "#FCE4EC"),
        ]
        current_bg = [default_bg]
        current_text = [default_text]
        img_path_holder = [None]
        photo_holder = [None]
        # --- 顶栏 ---
        top = tk.Frame(popup); top.pack(fill=tk.X, padx=10, pady=(10, 6))
        tk.Label(top, text="🎨 背景色:", font=("", 10)).pack(side=tk.LEFT)
        for name, hex_c in BG_PRESETS:
            def _pick(bg=hex_c, n=name):
                current_bg[0] = bg
                # 深色背景自动换白字
                if bg in ("#1A1A2E",):
                    current_text[0] = "#FFFFFF"
                else:
                    current_text[0] = default_text
                _redraw()
            tk.Button(top, text=name, bg=hex_c, width=6, height=1,
                      font=("", 9), command=_pick,
                      relief="solid", bd=1, cursor="hand2").pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="🎨 自定义", font=("", 10), padx=6,
                  command=lambda: self._pick_custom_bg(current_bg, current_text, _redraw),
                  cursor="hand2").pack(side=tk.LEFT, padx=8)
        # --- 按钮 ---
        btn = tk.Frame(popup); btn.pack(fill=tk.X, padx=10, pady=4)
        tk.Button(btn, text="📥 保存长图 PNG", font=("", 11, "bold"),
                  bg="#2E7D32", fg="white", padx=14, pady=3, cursor="hand2",
                  command=lambda: self._save_long_image(img_path_holder[0], title)).pack(side=tk.LEFT, padx=4)
        tk.Button(btn, text="📋 复制文字", font=("", 11), padx=12, cursor="hand2",
                  command=lambda: (popup.clipboard_clear(), popup.clipboard_append(text),
                                  messagebox.showinfo("✅", "文字已复制到剪贴板"))).pack(side=tk.LEFT, padx=4)
        tk.Button(btn, text="🔄 重新生成", font=("", 11), padx=12, cursor="hand2",
                  command=_redraw).pack(side=tk.LEFT, padx=4)
        # --- 画布区（带滚动条的长图预览）---
        canvas_frame = tk.Frame(popup); canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
        canvas = tk.Canvas(canvas_frame, bg="#EEEEEE", highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(canvas, bg="#EEEEEE")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        # --- 生成 & 渲染 ---
        def _redraw():
            canvas.delete("all")
            # 加载中提示
            canvas.create_text(550, 400, text="⏳ 正在生成长图...",
                               font=("", 14), fill="#666666")
            # 后台线程渲染（防止大图卡 UI）
            def _work():
                try:
                    p = self._render_text_to_long_image(
                        text, title=title,
                        bg_color=current_bg[0], text_color=current_text[0])
                    img_path_holder[0] = p
                    popup.after(0, lambda: _show_image(p))
                except Exception as e:
                    import traceback
                    err = f"❌ 长图生成失败：{e}\n{traceback.format_exc()}"
                    popup.after(0, lambda: canvas.create_text(
                        550, 400, text=err, font=("", 11), fill="#C62828"))
            threading.Thread(target=_work, daemon=True).start()
        def _show_image(path):
            try:
                img = Image.open(path)
                # 适配窗口宽度
                canvas_w = canvas.winfo_width()
                max_w = max(600, canvas_w - 20)
                w, h = img.size
                if w > max_w:
                    ratio = max_w / w
                    w, h = int(w * ratio), int(h * ratio)
                    img = img.resize((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                photo_holder[0] = photo  # 保持引用防 GC
                canvas.delete("all")
                canvas.create_image(10, 10, anchor="nw", image=photo)
                inner.update_idletasks()
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception as e:
                canvas.create_text(550, 400, text=f"❌ 图片加载失败：{e}",
                                   font=("", 11), fill="#C62828")
        popup.after(100, _redraw)  # 延迟一帧让 canvas 有宽度

    def update_ai_config_display(self):
        """更新AI配置显示"""
        try:
            if hasattr(self, 'ai_config_info') and self.ai_config_info.winfo_exists():
                provider_config = self.ai_config_manager.get_active_provider_config()
                active_provider = self.ai_config_manager.config.get("active_provider", "deepseek")
                config_text = f"当前激活的AI提供商:{active_provider.upper()}\n"
                config_text += f"{'='*40}\n\n"
                if provider_config:
                    config_text += f"Base URL: {provider_config.get('base_url', '未配置')}\n"
                    config_text += f"Model: {provider_config.get('model', '未配置')}\n"
                    config_text += f"API Key: {'已配置' if provider_config.get('api_key') else '未配置'}\n"
                    config_text += f"Temperature: {provider_config.get('temperature', 0.3)}\n"
                    config_text += f"Timeout: {provider_config.get('timeout', 60)}s\n"
                else:
                    config_text += "未找到配置信息\n"
                config_text += "\n点击'AI配置'按钮进行配置"
                self.ai_config_info.delete("1.0", tk.END)
                self.ai_config_info.insert("1.0", config_text)
        except Exception as e:
            print(f"更新AI配置显示失败: {e}")

    def _generate_stock_config_advice(self, stock_code, stock_name, strategy, market_status,
                                      peripheral_sentiment, sector, stock_type="股票"):
        """生成股票配置建议"""
        try:
            # 构建AI分析提示
            prompt = f"""请为以下{stock_type}提供详细的配置建议:
{stock_type}信息:
- 代码:{stock_code}
- 名称:{stock_name}
- 类型:{stock_type}
- 板块:{sector or '未分类'}
市场环境:
- 大盘情况:{market_status}
- 外围情绪:{peripheral_sentiment}分
- 选择策略:{strategy}
请根据以下维度提供配置建议:
1. **是否配置**:
   - 基于当前市场环境、板块情况、策略匹配度,判断是否适合配置
   - 给出明确的配置/不配置建议及理由
2. **配置仓位**:
   - 根据单只股票不超过10%的原则
   - 结合市场环境、板块热度、个股基本面
   - 给出具体仓位建议(如:5%、8%、10%)
3. **交易时机**:
   - 何时买入(如:回调至XX价位、突破XX价位、分批建仓时机)
   - 何时卖出(如:达到目标价、触发止损、止盈时机)
4. **目标价**:
   - 基于技术分析、基本面分析
   - 给出合理的目标价位
5. **止盈止损**:
   - 止损价格(建议-8%)
   - 止盈价格(移动止盈策略)
   - 动态调整建议
6. **行业分析**:
   - 该板块当前状况
   - 板块内个股表现
   - 板块前景分析
7. **风险提示**:
   - 个股风险
   - 板块风险
   - 市场风险
请提供详细、专业的分析和建议,格式清晰易读。"""
            system_prompt = """你是一位资深的股票交易体系专家,精通仓位管理、风险控制、交易时机把握。
你能够根据市场环境、策略选择、个股情况,提供专业的配置建议和交易指导。
你的建议应该:
1. 严格遵循仓位管理原则(单只股票不超过10%,行业不超过20%)
2. 设置明确的止盈止损规则
3. 考虑市场环境和板块情况
4. 提供可执行的交易建议"""
            ai_result = self.call_ai_model(prompt, system_prompt)
            if not ai_result:
                # 如果AI不可用,返回基础建议
                return f"""股票配置建议:{stock_name} ({stock_code})
【是否配置】
建议:待评估(需要AI分析)
【配置仓位】
建议:5-8%(单只股票不超过10%)
【交易时机】
买入时机:待技术分析确定
卖出时机:达到目标价或触发止损
【目标价】
待技术分析确定
【止盈止损】
止损:-8%
止盈:移动止盈(盈利后回落20%平仓)
【行业分析】
板块:{sector or '未分类'}
建议:关注板块整体走势
【风险提示】
1. 个股风险:需进一步分析
2. 板块风险:关注板块轮动
3. 市场风险:关注大盘走势
注:AI分析暂时不可用,请检查AI配置。"""
            return ai_result
        except Exception as e:
            return f"生成配置建议失败: {e!s}"

    def _compose_quant_dialog_right_text(self, snap, spot, concept_lines, *, network_time=None, network_errors=None):
        """量化弹窗右侧全文:数据源说明 → 情绪五问(联网)→ 指数 → 板块 → 好坏 → 左栏仓位 → Skill 建议。"""
        chunks = []
        chunks.extend(self._quant_market_network_sources_header())
        ts = network_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chunks.append(f"══ 本轮联网采集时间:{ts} ══\n")
        if network_errors:
            chunks.append("(部分接口异常:" + ";".join(network_errors) + ")\n")
        chunks.append("══ 1 情绪区间五问(每次打开/刷新均重新请求问财与东财,与右上展示字段一致但不同步于旧缓存)══\n")
        chunks.extend(self._format_sentiment_zone_snapshot_lines(snap))
        chunks.append("")
        chunks.extend(self._quant_board_structure_lines(snap, spot))
        chunks.append("")
        chunks.append("══ 题材/概念热度(AKShare 概念榜或选股通网页,可与问财交叉验证)══")
        if concept_lines:
            chunks.extend(concept_lines)
        else:
            chunks.append("(未拉取)")
        chunks.append("")
        chunks.extend(self._quant_snapshot_good_bad_lines(snap))
        chunks.append("")
        chunks.append("┏━━━━━━━━ 左侧「仓位」标签页补充状态 ━━━━━━━━┓\n")
        chunks.append(self._gather_quant_emotion_context())
        chunks.append("\n")
        chunks.append(self._recommend_quant_strategies())
        return "\n".join(chunks)

    def _configure_quant_dialog_right_tags(self, w):
        """量化弹窗右侧:A 股情绪色(涨/偏多红 #d32f2f,跌/偏空绿 #2e7d32),同「情绪区间」总览。"""
        try:
            w.tag_configure("up_bold", foreground="#d32f2f", font=("Microsoft YaHei UI", 11, "bold"))
            w.tag_configure("down_bold", foreground="#2e7d32", font=("Microsoft YaHei UI", 11, "bold"))
            w.tag_configure("neutral", foreground="#212121", font=("Microsoft YaHei UI", 11))
        except Exception:
            pass

    def _quant_dialog_insert_pct_value(self, w, v):
        """插入涨跌幅百分比(带红绿)。"""
        if not isinstance(v, (int, float)):
            w.insert(tk.END, "未获取", ("neutral",))
            return
        s = f"{float(v):+.2f}%"
        tag = "up_bold" if float(v) > 0 else ("down_bold" if float(v) < 0 else "neutral")
        w.insert(tk.END, s, (tag,))

    def _quant_dialog_insert_line_scan_pcts(self, w, line, end_newline=True):
        """行内所有「数字%」按正负着色(用于指数行、概念行等)。"""
        import re
        if line is None:
            line = ""
        pos = 0
        for m in re.finditer(r"([+-]?\d+\.?\d*)%", line):
            w.insert(tk.END, line[pos : m.start()])
            try:
                val = float(m.group(1))
            except ValueError:
                w.insert(tk.END, m.group(0), ("neutral",))
            else:
                tag = "up_bold" if val > 0 else ("down_bold" if val < 0 else "neutral")
                w.insert(tk.END, m.group(0), (tag,))
            pos = m.end()
        w.insert(tk.END, line[pos:])
        if end_newline:
            w.insert(tk.END, "\n")

    def _fill_quant_dialog_right_text_colored(
        self, w, snap, spot, concept_lines, *, network_time=None, network_errors=None
    ):
        """右侧全文:结构同 _compose_quant_dialog_right_text,数值按情绪红绿着色。"""
        def _ok_line(s):
            if not s:
                return False
            bad_tokens = ("未获取", "暂无", "未拉取", "无快照", "失败", "异常", "指标不全")
            return not any(t in str(s) for t in bad_tokens)
        w.delete("1.0", tk.END)
        for ln in self._quant_market_network_sources_header():
            w.insert(tk.END, ln + "\n")
        ts = network_time if network_time else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        w.insert(tk.END, f"══ 本轮联网采集时间:{ts} ══\n")
        w.insert(
            tk.END,
            "══ 1 情绪区间五问(每次打开/刷新均重新请求问财与东财,与右上展示字段一致但不同步于旧缓存)══\n",
        )
        if snap and isinstance(snap, dict):
            t = snap.get("time", "")
            m = snap.get("metrics", {}) or {}
            def _fv(key, sub="value"):
                o = m.get(key)
                if isinstance(o, (int, float)):
                    return float(o) if sub == "value" else None
                if not isinstance(o, dict):
                    return None
                v = o.get(sub)
                if isinstance(v, (int, float)):
                    return v
                return None
            w.insert(tk.END, f"更新时间: {t}\n", ("neutral",))
            v1, v1y = _fv("m1_today"), _fv("m1_yday")
            if isinstance(v1, (int, float)) and isinstance(v1y, (int, float)):
                w.insert(tk.END, "问1 同花顺情绪指数:", ("neutral",))
                w.insert(tk.END, "当日 ", ("neutral",))
                self._quant_dialog_insert_pct_value(w, v1)
                w.insert(tk.END, " / 昨日 ", ("neutral",))
                self._quant_dialog_insert_pct_value(w, v1y)
                w.insert(tk.END, "\n")
            mk = m.get("m2_market") if isinstance(m.get("m2_market"), dict) else {}
            if isinstance(mk.get("up"), (int, float)) and isinstance(mk.get("down"), (int, float)):
                w.insert(tk.END, "问2 全A涨跌家数:上涨 ", ("neutral",))
                self._quant_dialog_insert_up_down_count(w, mk.get("up"), is_up=True)
                w.insert(tk.END, " 下跌 ", ("neutral",))
                self._quant_dialog_insert_up_down_count(w, mk.get("down"), is_up=False)
                if mk.get("flat") is not None:
                    w.insert(tk.END, " 平盘 ", ("neutral",))
                    w.insert(tk.END, str(mk.get("flat")), ("neutral",))
                if mk.get("total") is not None:
                    w.insert(tk.END, " 总计 ", ("neutral",))
                    w.insert(tk.END, str(mk.get("total")), ("neutral",))
                src = mk.get("source", "")
                if src:
                    w.insert(tk.END, f"({src})", ("neutral",))
                w.insert(tk.END, "\n")
            c3, c4 = _fv("m3", "count"), _fv("m4", "count")
            if isinstance(c3, (int, float)):
                w.insert(tk.END, "问3 60分钟上穿60日线且放量:约 ", ("neutral",))
                w.insert(tk.END, str(c3), ("neutral",))
                w.insert(tk.END, " 只(问财条数)\n", ("neutral",))
            if isinstance(c4, (int, float)):
                w.insert(tk.END, "问4 15分钟多均线发散:约 ", ("neutral",))
                w.insert(tk.END, str(c4), ("neutral",))
                w.insert(tk.END, " 只(问财条数)\n", ("neutral",))
            hs, zz, kc, av = _fv("m5_hs300"), _fv("m5_zz500"), _fv("m5_kc30"), _fv("m5_avg")
            chunks = []
            if isinstance(hs, (int, float)):
                chunks.append(("沪深300 ", hs))
            if isinstance(zz, (int, float)):
                chunks.append(("中证500 ", zz))
            if isinstance(kc, (int, float)):
                chunks.append(("科创30(问财名) ", kc))
            if isinstance(av, (int, float)):
                chunks.append(("三指均值 ", av))
            if chunks:
                w.insert(tk.END, "问5 ", ("neutral",))
                for i, (nm, vv) in enumerate(chunks):
                    if i > 0:
                        w.insert(tk.END, " · ", ("neutral",))
                    w.insert(tk.END, nm, ("neutral",))
                    self._quant_dialog_insert_pct_value(w, vv)
                w.insert(tk.END, "\n")
        w.insert(tk.END, "\n", ("neutral",))
        for ln in self._quant_board_structure_lines(snap, spot):
            if _ok_line(ln):
                self._quant_dialog_insert_line_scan_pcts(w, ln, end_newline=True)
        w.insert(tk.END, "\n", ("neutral",))
        w.insert(tk.END, "══ 题材/概念热度(AKShare 概念榜或选股通网页,可与问财交叉验证)══\n", ("neutral",))
        if concept_lines:
            for ln in concept_lines:
                if _ok_line(ln):
                    self._quant_dialog_insert_line_scan_pcts(w, ln, end_newline=True)
        w.insert(tk.END, "\n", ("neutral",))
        for ln in self._quant_snapshot_good_bad_lines(snap):
            if _ok_line(ln):
                self._quant_dialog_insert_line_scan_pcts(w, ln, end_newline=True)
        w.insert(tk.END, "\n", ("neutral",))
        w.insert(tk.END, "┏━━━━━━━━ 左侧「仓位」标签页补充状态 ━━━━━━━━┓\n", ("neutral",))
        w.insert(tk.END, self._gather_quant_emotion_context(), ("neutral",))
        w.insert(tk.END, "\n\n", ("neutral",))
        w.insert(tk.END, self._recommend_quant_strategies(), ("neutral",))

    def _edit_window_title(self):
        """修改窗口标题"""
        try:
            from tkinter import messagebox, simpledialog
            # 获取当前标题
            current_title = self.root.title()
            # 打开对话框让用户输入新标题
            new_title = simpledialog.askstring(
                "修改窗口标题",
                "请输入新的窗口标题:",
                initialvalue=current_title,
                parent=self.root
            )
            # 如果用户点击了取消或输入为空,不做处理
            if new_title is None:
                return
            new_title = new_title.strip()
            if not new_title:
                messagebox.showinfo("提示", "标题不能为空")
                return
            # 更新窗口标题
            self.root.title(new_title)
            # 更新配置并保存
            global APP_CONFIG
            APP_CONFIG["window_title"] = new_title
            save_app_config(APP_CONFIG)
            # 显示成功消息
            messagebox.showinfo("成功", "窗口标题已修改并保存")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", f"修改标题失败:{e!s}")

    def _open_settings_dialog(self):
        """打开设置对话框"""
        try:
            from tkinter import (
                Button,
                Entry,
                IntVar,
                Label,
                StringVar,
                Toplevel,
                colorchooser,
                messagebox,
            )
            # 创建设置窗口
            settings_window = Toplevel(self.root)
            settings_window.title("设置")
            settings_window.geometry("400x300")
            settings_window.transient(self.root)
            settings_window.grab_set()
            # 获取当前设置
            current_title = self.root.title()
            current_font_size = APP_CONFIG.get("font_size", DEFAULT_APP_CONFIG["font_size"])
            current_color = APP_CONFIG.get("title_color", DEFAULT_APP_CONFIG["title_color"])
            # 标题设置
            Label(settings_window, text="窗口标题:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
            title_var = StringVar(value=current_title)
            Entry(settings_window, textvariable=title_var, width=30).grid(row=0, column=1, padx=10, pady=10)
            # 字体大小设置
            Label(settings_window, text="字体大小:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
            font_size_var = IntVar(value=current_font_size)
            Entry(settings_window, textvariable=font_size_var, width=10).grid(row=1, column=1, padx=10, pady=10, sticky="w")
            # 颜色设置
            Label(settings_window, text="标题颜色:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
            color_var = StringVar(value=current_color)
            def choose_color():
                color = colorchooser.askcolor(title="选择颜色")
                if color[1]:
                    color_var.set(color[1])
                    color_button.config(bg=color[1])
            color_button = Button(settings_window, text="选择颜色", command=choose_color, width=10, bg=current_color)
            color_button.grid(row=2, column=1, padx=10, pady=10, sticky="w")
            # 保存按钮
            def save_settings():
                try:
                    # 获取新设置
                    new_title = title_var.get().strip()
                    new_font_size = font_size_var.get()
                    new_color = color_var.get()
                    # 验证设置
                    if not new_title:
                        messagebox.showinfo("提示", "标题不能为空")
                        return
                    if new_font_size < 8 or new_font_size > 72:
                        messagebox.showinfo("提示", "字体大小应在8-72之间")
                        return
                    # 更新窗口标题
                    self.root.title(new_title)
                    # 更新配置并保存
                    global APP_CONFIG
                    APP_CONFIG["window_title"] = new_title
                    APP_CONFIG["font_size"] = new_font_size
                    APP_CONFIG["title_color"] = new_color
                    save_app_config(APP_CONFIG)
                    # 显示成功消息
                    messagebox.showinfo("成功", "设置已保存")
                    settings_window.destroy()
                except Exception as e:
                    messagebox.showerror("错误", f"保存设置失败:{e!s}")
            Button(settings_window, text="保存", command=save_settings, width=10).grid(row=3, column=1, padx=10, pady=20, sticky="e")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", f"打开设置对话框失败:{e!s}")


__all__ = ["ConfigMixin"]

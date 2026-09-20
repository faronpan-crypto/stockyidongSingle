"""AI/LLM"""
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

import time
import threading
import traceback
import hashlib
from urllib.parse import urljoin

class AiMixin:
    """AI/LLM"""

    def show_ai_config(self):
        """显示AI配置界面(支持更多配置项)"""
        config_window = self._toplevel(self.root)
        config_window.title("AI大模型配置")
        config_window.geometry("700x600")
        # 创建滚动框架
        canvas = tk.Canvas(config_window)
        scrollbar = ttk.Scrollbar(config_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 创建配置框架
        main_frame = ttk.Frame(scrollable_frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # AI提供商选择
        provider_frame = ttk.LabelFrame(main_frame, text="AI提供商选择", padding=10)
        provider_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(provider_frame, text="选择提供商:").pack(side=tk.LEFT, padx=(0, 10))
        provider_var = tk.StringVar(value=self.ai_config_manager.config.get("active_provider", "deepseek"))
        provider_combo = ttk.Combobox(provider_frame, textvariable=provider_var,
                                     values=["deepseek", "doubao", "ollama"],
                                     state="readonly", width=15)
        provider_combo.pack(side=tk.LEFT)
        # 提供商配置(支持base_url、model、api_key等)
        providers = self.ai_config_manager.config.get("providers", {})
        provider_config_vars = {}
        for provider_name in ["deepseek", "doubao", "ollama"]:
            provider_config = providers.get(provider_name, {})
            provider_frame_item = ttk.LabelFrame(main_frame, text=f"{provider_name.upper()} 配置", padding=10)
            provider_frame_item.pack(fill=tk.X, pady=(0, 10))
            config_vars = {}
            # Base URL
            url_frame = ttk.Frame(provider_frame_item)
            url_frame.pack(fill=tk.X, pady=2)
            ttk.Label(url_frame, text="Base URL:", width=15).pack(side=tk.LEFT)
            url_var = tk.StringVar(value=provider_config.get("base_url", ""))
            config_vars["base_url"] = url_var
            ttk.Entry(url_frame, textvariable=url_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            # Model
            model_frame = ttk.Frame(provider_frame_item)
            model_frame.pack(fill=tk.X, pady=2)
            ttk.Label(model_frame, text="Model:", width=15).pack(side=tk.LEFT)
            model_var = tk.StringVar(value=provider_config.get("model", ""))
            config_vars["model"] = model_var
            ttk.Entry(model_frame, textvariable=model_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            # API Key
            key_frame = ttk.Frame(provider_frame_item)
            key_frame.pack(fill=tk.X, pady=2)
            ttk.Label(key_frame, text="API Key:", width=15).pack(side=tk.LEFT)
            key_var = tk.StringVar(value=provider_config.get("api_key", ""))
            config_vars["api_key"] = key_var
            ttk.Entry(key_frame, textvariable=key_var, width=50, show="*").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            # Endpoint (可选)
            endpoint_frame = ttk.Frame(provider_frame_item)
            endpoint_frame.pack(fill=tk.X, pady=2)
            ttk.Label(endpoint_frame, text="Endpoint:", width=15).pack(side=tk.LEFT)
            endpoint_var = tk.StringVar(value=provider_config.get("endpoint", "/chat/completions"))
            config_vars["endpoint"] = endpoint_var
            ttk.Entry(endpoint_frame, textvariable=endpoint_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            # Temperature
            temp_frame = ttk.Frame(provider_frame_item)
            temp_frame.pack(fill=tk.X, pady=2)
            ttk.Label(temp_frame, text="Temperature:", width=15).pack(side=tk.LEFT)
            temp_var = tk.StringVar(value=str(provider_config.get("temperature", 0.3)))
            config_vars["temperature"] = temp_var
            ttk.Entry(temp_frame, textvariable=temp_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            # Timeout
            timeout_frame = ttk.Frame(provider_frame_item)
            timeout_frame.pack(fill=tk.X, pady=2)
            ttk.Label(timeout_frame, text="Timeout(s):", width=15).pack(side=tk.LEFT)
            timeout_var = tk.StringVar(value=str(provider_config.get("timeout", 60)))
            config_vars["timeout"] = timeout_var
            ttk.Entry(timeout_frame, textvariable=timeout_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            # Mode (仅豆包)
            if provider_name == "doubao":
                mode_frame = ttk.Frame(provider_frame_item)
                mode_frame.pack(fill=tk.X, pady=2)
                ttk.Label(mode_frame, text="Mode:", width=15).pack(side=tk.LEFT)
                mode_var = tk.StringVar(value=provider_config.get("mode", "chat"))
                config_vars["mode"] = mode_var
                mode_combo = ttk.Combobox(mode_frame, textvariable=mode_var,
                                        values=["chat", "content"], state="readonly", width=50)
                mode_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
            provider_config_vars[provider_name] = config_vars
        # 保存按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        def save_config():
            # 更新配置
            active_provider = provider_var.get()
            self.ai_config_manager.config["active_provider"] = active_provider
            for provider_name, config_vars in provider_config_vars.items():
                if provider_name not in self.ai_config_manager.config["providers"]:
                    self.ai_config_manager.config["providers"][provider_name] = {}
                # 更新所有配置项
                for key, var in config_vars.items():
                    value = var.get()
                    if key in ["temperature", "timeout"]:
                        try:
                            self.ai_config_manager.config["providers"][provider_name][key] = float(value)
                        except:
                            self.ai_config_manager.config["providers"][provider_name][key] = 0.3 if key == "temperature" else 60
                    else:
                        self.ai_config_manager.config["providers"][provider_name][key] = value
            if self.ai_config_manager.save_config():
                messagebox.showinfo("成功", "AI配置已保存")
                # 更新配置显示
                self.update_ai_config_display()
                config_window.destroy()
            else:
                messagebox.showerror("错误", "保存配置失败")
        def test_config():
            """测试AI配置"""
            try:
                # 临时保存配置用于测试
                active_provider = provider_var.get()
                test_config_override = {}
                for provider_name, config_vars in provider_config_vars.items():
                    if provider_name == active_provider:
                        test_config_override = {}
                        for key, var in config_vars.items():
                            value = var.get()
                            if key in ["temperature", "timeout"]:
                                try:
                                    test_config_override[key] = float(value)
                                except:
                                    test_config_override[key] = 0.3 if key == "temperature" else 60
                            else:
                                test_config_override[key] = value
                        break
                # 测试提示词
                test_prompt = "你好,请回复'测试成功'确认连接正常。"
                # 显示测试中
                test_result_label = ttk.Label(button_frame, text="测试中...", foreground="blue")
                test_result_label.pack(side=tk.LEFT, padx=(10, 0))
                config_window.update()
                # 调用AI
                result = self.call_ai_model(test_prompt, config_override=test_config_override)
                # 显示结果
                test_result_label.destroy()
                if result and "错误" not in result and "失败" not in result:
                    messagebox.showinfo("测试成功", f"AI配置测试成功!\n\n回复内容:\n{result[:200]}")
                else:
                    messagebox.showerror("测试失败", f"AI配置测试失败:\n{result}")
            except Exception as e:
                messagebox.showerror("测试错误", f"测试过程中出现错误:{e}")
        def open_provider_console():
            """打开当前选择的AI提供商账户/充值页面,便于查看余额与充值。"""
            provider = provider_var.get()
            url = None
            if provider == "deepseek":
                # DeepSeek 平台控制台(可查看 API Key、用量与充值)
                url = "https://platform.deepseek.com/"
            elif provider == "doubao":
                # 火山引擎豆包控制台
                url = "https://console.volcengine.com/ark/"
            elif provider == "ollama":
                # 本地 Ollama,一般无需充值,这里打开官方主页
                url = "https://ollama.com/"
            if url:
                try:
                    import webbrowser
                    webbrowser.open(url)
                except Exception as e:
                    messagebox.showerror("错误", f"无法打开浏览器:{e}")
            else:
                messagebox.showinfo("提示", "当前提供商暂不支持直接打开余额/充值页面,请手动在浏览器中查看。")
        ttk.Button(button_frame, text="测试", command=test_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="保存", command=save_config).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="余额/充值页面", command=open_provider_console).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="取消", command=config_window.destroy).pack(side=tk.LEFT)
        # 布局滚动组件
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def show_ai_question(self):
        """显示AI提问对话框"""
        question_window = self._toplevel(self.root)
        question_window.title("AI提问")
        question_window.geometry("600x500")
        # 提示标签
        tip_label = ttk.Label(question_window, text="请输入您的问题,AI将基于左边文本框的内容进行回答:",
                             font=("TkDefaultFont", 12))
        tip_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        # 问题输入框
        question_frame = ttk.LabelFrame(question_window, text="问题", padding=10)
        question_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        question_text = scrolledtext.ScrolledText(question_frame, height=8, wrap=tk.WORD)
        question_text.pack(fill=tk.BOTH, expand=True)
        # 按钮框架
        button_frame = ttk.Frame(question_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        def submit_question():
            question = question_text.get("1.0", tk.END).strip()
            if not question:
                messagebox.showwarning("警告", "请输入问题")
                return
            # 获取左边文本框的内容
            all_texts = self.get_all_texts()
            if not all_texts:
                messagebox.showwarning("警告", "左边文本框没有内容")
                return
            combined_text = "\n\n".join([item['text'] for item in all_texts])
            if not combined_text.strip():
                messagebox.showwarning("警告", "左边文本框内容为空")
                return
            # 关闭提问窗口
            question_window.destroy()
            # 在后台线程中运行AI提问
            def run_ai_question():
                try:
                    # 构建提示词
                    system_prompt = "你是一个专业的股票市场分析师,擅长回答股票相关问题。"
                    user_prompt = f"""基于以下文本内容回答用户的问题:
文本内容:
{combined_text[:3000]}
用户问题:
{question}
请基于文本内容提供准确、专业的回答。如果文本内容中没有相关信息,请说明。"""
                    # 调用AI模型
                    ai_result = self.call_ai_model(user_prompt, system_prompt)
                    # 显示结果
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        if ai_result:
                            result_text = f"问题:{question}\n\n"
                            result_text += "="*80 + "\n\n"
                            result_text += f"AI回答:\n{ai_result}\n"
                            self.root.after(0, lambda: self.append_ai_analysis(result_text))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("错误", "AI回答失败"))
                except Exception as e:
                    if hasattr(self, 'root') and self.root.winfo_exists():
                        self.root.after(0, lambda e=e: messagebox.showerror("错误", f"AI提问失败: {e}"))
            threading.Thread(target=run_ai_question, daemon=True).start()
        ttk.Button(button_frame, text="提交", command=submit_question).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=question_window.destroy).pack(side=tk.LEFT, padx=5)

    def call_ai_model(self, prompt, system_prompt=None, config_override=None, max_tokens=None):
        """调用AI模型(与富媒体 AI 分析使用同一套 active_provider 配置)"""
        try:
            # 使用AI配置管理器
            if config_override:
                provider_config = config_override
            else:
                provider_config = self.ai_config_manager.get_active_provider_config()
            if not provider_config:
                return "错误: 未配置AI提供商"
            api_key = provider_config.get("api_key", "")
            if not api_key:
                return "错误: 未配置API密钥"
            base_url = provider_config.get("base_url", "")
            model = provider_config.get("model", "")
            endpoint = provider_config.get("endpoint", "/chat/completions")
            provider = self.ai_config_manager.config.get("active_provider", "deepseek")
            # 构建URL
            if provider == "deepseek":
                url = f"{base_url.rstrip('/')}/chat/completions"
            elif provider == "doubao":
                # 豆包特殊处理
                if provider_config.get("mode") == "content":
                    url = f"{base_url}/api/v3/contents/generations/tasks"
                else:
                    url = f"{base_url.rstrip('/')}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
            else:
                url = f"{base_url.rstrip('/')}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            # 构建消息
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            data = {
                "model": model,
                "messages": messages,
                "temperature": provider_config.get("temperature", 0.3)
            }
            if max_tokens is not None:
                data["max_tokens"] = int(max_tokens)
            elif provider_config.get("max_tokens"):
                data["max_tokens"] = provider_config["max_tokens"]
            # 超时:支持 (连接, 读取) 元组,避免长时间生成被截断
            to = provider_config.get("timeout", 60)
            try:
                to_f = float(to)
                req_timeout = (min(45.0, to_f), max(to_f, 120.0)) if to_f < 120 else (45.0, to_f)
            except Exception:
                req_timeout = (45, 180)
            # 发送请求(带简单重试)
            import time as _time
            last_err = None
            response = None
            for attempt in range(3):
                try:
                    response = requests.post(url, json=data, headers=headers, timeout=req_timeout)
                    break
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, OSError) as e:
                    last_err = e
                    if attempt < 2:
                        _time.sleep(2 + attempt * 2)
                    else:
                        return f"网络错误(已重试3次): {type(last_err).__name__}: {last_err}"
            if response is None:
                return f"网络错误: {last_err}"
            if response.status_code == 200:
                result = response.json()
                # 处理不同提供商的响应格式
                if provider == "doubao" and provider_config.get("mode") == "content":
                    # 豆包content模式需要轮询任务状态
                    task_id = result.get("id")
                    if task_id:
                        # 轮询任务状态
                        task_url = f"{base_url}/api/v3/contents/generations/tasks/{task_id}"
                        max_attempts = 30
                        for _ in range(max_attempts):
                            time.sleep(2)
                            task_response = requests.get(task_url, headers=headers, timeout=60)
                            if task_response.status_code == 200:
                                task_result = task_response.json()
                                if task_result.get("status") == "completed":
                                    return task_result.get("result", {}).get("content", "")
                                elif task_result.get("status") == "failed":
                                    return f"任务失败: {task_result.get('error', '未知错误')}"
                        return "任务超时"
                    else:
                        return "未获取到任务ID"
                else:
                    # 标准OpenAI格式
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                return f"API调用失败: {response.status_code} - {response.text}"
        except Exception as e:
            return f"AI调用错误: {e!s}"

    def _open_ai_search(self, ai_site, query):
        """打开AI网站并进行搜索分析,结果复制到文本标签页"""
        if not query or not query.strip():
            messagebox.showwarning("提示", "请输入要搜索的关键词或问题")
            return
        query = query.strip()
        # 修复乱码
        query = self._fix_encoding(query)
        # 获取AI搜索URL(如果有的话,否则使用普通URL)
        search_url = ai_site.get("search_url", ai_site.get("url", ""))
        if "{query}" in search_url:
            try:
                from urllib.parse import quote_plus
                encoded = quote_plus(query) if query else ""
                url = search_url.format(query=encoded)
            except Exception:
                url = search_url.format(query=query)
        else:
            # 如果没有搜索URL,使用普通URL并打开
            url = ai_site.get("url", "")
            self._open_market_link(url)
            # 将查询内容复制到剪贴板,方便用户粘贴
            self.root.clipboard_clear()
            self.root.clipboard_append(query)
            self._safe_update()
            messagebox.showinfo("提示", f"已打开{ai_site['name']},查询内容已复制到剪贴板,请粘贴到AI工具中进行搜索和分析")
            if query:
                self._add_search_history(query)
            return
        # 打开AI搜索链接
        self._open_market_link(url)
        # 尝试抓取AI搜索结果并复制到文本标签页
        if not hasattr(self, "_market_nav_fetching"):
            self._market_nav_fetching = set()
        if url in self._market_nav_fetching:
            print(f"正在抓取 {url},请稍候...")
            return
        self._market_nav_fetching.add(url)
        threading.Thread(
            target=self._fetch_ai_search_result,
            args=(ai_site['name'], url, query),
            daemon=True
        ).start()
        if query:
            self._add_search_history(query)

    def _refresh_ai_questions_widget(self):
        """刷新AI问题列表显示"""
        if hasattr(self, "ai_questions_listbox") and self.ai_questions_listbox:
            self.ai_questions_listbox.delete(0, tk.END)
            questions = self.market_nav_config.get("ai_search_questions", [])
            for item in questions:
                self.ai_questions_listbox.insert(tk.END, item)

    def _collect_shanghai_volatility_and_energy_text(self):
        """上证:近端波动率近似 + 能量学(聚集/发散)。"""
        lines = []
        lines.append("══ 上证指数 · 波动率与能量学(研判用)══")
        try:
            lines.append(self._compute_energy_analysis_report_text("000001", days=60))
        except Exception as e:
            lines.append(f"(能量学:{e})")
        try:
            import akshare as ak
            df = ak.index_zh_a_hist(symbol="000001", period="daily")
            if df is None or df.empty:
                lines.append("(日K不足,跳过波动率统计)")
            else:
                close_col = "收盘" if "收盘" in df.columns else None
                if not close_col:
                    for c in df.columns:
                        if "收盘" in str(c) or str(c).lower() == "close":
                            close_col = c
                            break
                if not close_col:
                    close_col = df.columns[-1]
                s = pd.to_numeric(df[close_col], errors="coerce").dropna()
                if len(s) >= 22:
                    r = s.pct_change().dropna()
                    tail = r.tail(20)
                    daily_std_pct = float(tail.std() * 100.0)
                    lines.append(
                        f"· 上证近20日收益波动(日收益率标准差):约 {daily_std_pct:.3f}%(越大表示短线波动越剧烈)"
                    )
                else:
                    lines.append("(有效样本不足)")
        except Exception as e:
            lines.append(f"(波动率统计失败:{e})")
        lines.append("")
        return "\n".join(lines)

    def _gather_ai_staff_risk_context(self):
        """风控员:强制使用联网实时大盘与情绪数据,并附风控补充。"""
        parts = []
        parts.append(self._gather_ai_staff_analyst_context())
        parts.append("\n【风控专用补充 · 指数近日收盘(上证)】\n")
        try:
            import akshare as ak
            df = ak.index_zh_a_hist(symbol="000001", period="daily")
            if df is not None and not df.empty:
                tail = df.tail(8)
                parts.append(tail.to_string(index=False))
            else:
                parts.append("(无)")
        except Exception as e:
            parts.append(f"(失败:{e})")
        return "\n".join(parts)

    def _ai_staff_keyword_tag_schemes(self):
        """AI 员工报告关键词分类:(tag_name, 前景色, 关键词列表)。长词优先匹配。"""
        return [
            (
                "kw_pressure",
                "#c0392b",
                [
                    "压力位",
                    "压力区",
                    "上方压力",
                    "阻力区",
                    "阻力位",
                    "阻力",
                    "假突破",
                    "压力",
                ],
            ),
            (
                "kw_support",
                "#148f77",
                [
                    "支撑位",
                    "支撑区",
                    "下方支撑",
                    "下轨",
                    "支撑",
                ],
            ),
            (
                "kw_position",
                "#2874a6",
                [
                    "建议总仓位",
                    "总仓位",
                    "仓位上限",
                    "建议仓位",
                    "仓位",
                    "建仓",
                    "加仓",
                    "减仓",
                    "清仓",
                    "止损",
                    "止盈",
                    "轻仓",
                    "重仓",
                    "半仓",
                    "满仓",
                    "空仓",
                ],
            ),
            (
                "kw_risk",
                "#7d3c98",
                [
                    "系统性风险",
                    "流动性风险",
                    "最大回撤",
                    "波动放大",
                    "波动加剧",
                ],
            ),
        ]

    def _segment_text_ai_staff_keywords(self, s):
        """按关键词规则将全文拆成 (片段, tag_name 或 None),用于界面着色与导出。"""
        if not s:
            return []
        flat = []
        for tag, _c, kws in self._ai_staff_keyword_tag_schemes():
            for kw in kws:
                if kw:
                    flat.append((len(kw), kw, tag))
        flat.sort(key=lambda x: -x[0])
        n = len(s)
        owner = [None] * n
        for _L, kw, tag in flat:
            start = 0
            while True:
                i = s.find(kw, start)
                if i < 0:
                    break
                end = i + len(kw)
                if any(owner[j] is not None for j in range(i, end)):
                    start = i + 1
                    continue
                for j in range(i, end):
                    owner[j] = tag
                start = end
        out = []
        i = 0
        while i < n:
            tgn = owner[i]
            j = i
            while j < n and owner[j] == tgn:
                j += 1
            out.append((s[i:j], tgn))
            i = j
        return out

    def _configure_ai_staff_text_tags(self, w):
        for tag, color, _ in self._ai_staff_keyword_tag_schemes():
            try:
                w.tag_configure(tag, foreground=color)
            except Exception:
                pass

    def _apply_ai_staff_keyword_highlights(self, w):
        """对 ScrolledText 应用关键词前景色(长词优先、互不覆盖)。"""
        self._configure_ai_staff_text_tags(w)
        for tag, _, _ in self._ai_staff_keyword_tag_schemes():
            try:
                w.tag_remove(tag, "1.0", tk.END)
            except Exception:
                pass
        s = w.get("1.0", "end-1c")
        pos = 0
        for seg, tgn in self._segment_text_ai_staff_keywords(s):
            if not seg:
                continue
            l = len(seg)
            if tgn:
                try:
                    w.tag_add(tgn, f"1.0+{pos}c", f"1.0+{pos + l}c")
                except Exception:
                    pass
            pos += l

    def _compose_quant_skill_ai_advice(self, skill_item, snap, spot, concept_lines):
        """按当前 Skill 结合右上行情给出规则化 AI 建议。"""
        name = skill_item.get("title", "")
        cat = skill_item.get("cat", "")
        m = (snap or {}).get("metrics", {}) or {}
        m1 = (m.get("m1_today") or {}).get("value")
        m5 = m.get("m5_avg")
        if isinstance(m5, dict):
            m5 = m5.get("value")
        mk = m.get("m2_market") if isinstance(m.get("m2_market"), dict) else {}
        up, down = mk.get("up"), mk.get("down")
        strength = "中性"
        if isinstance(m1, (int, float)) and isinstance(m5, (int, float)):
            if m1 >= 0.6 and m5 >= 0.2:
                strength = "偏强"
            elif m1 <= -0.6 and m5 <= -0.2:
                strength = "偏弱"
        if isinstance(up, (int, float)) and isinstance(down, (int, float)) and up + down > 0:
            if up > down * 1.25:
                strength = "偏强"
            elif down > up * 1.25:
                strength = "偏弱"
        lines = [
            f"【当前 Skill】{cat} · {name}",
            f"盘面判断:{strength}(m1={m1},m5均值={m5},涨跌家数={up}/{down})",
            "",
        ]
        hot_concepts = self._extract_quant_hot_concepts_from_lines(concept_lines, top_n=6)
        if cat == "择时":
            if strength == "偏强":
                lines.append("择时结论:可执行顺势择时,优先右侧结构最强指数方向,采用分批上仓。")
                lines.append("执行要点:首次试仓 30%-40%,若午后结构不破坏再加到 50%-70%。")
            elif strength == "偏弱":
                lines.append("择时结论:防守为主,尽量等确认信号,不建议激进追涨。")
                lines.append("执行要点:仅保留观察仓或空仓,等待 m1 与 m5 同步修复。")
            else:
                lines.append("择时结论:震荡过渡,适合轻仓试错+严格止损。")
                lines.append("执行要点:仓位不超过 40%,先看结构再决定是否放大。")
        elif cat == "择股":
            lines.append("择股结论:结合右上结构优先选强势题材与强于指数的个股。")
            if hot_concepts:
                lines.append("优先题材(来自右上题材热度):")
                for nm, p in hot_concepts[:5]:
                    lines.append(f"  - {nm}({p:+.2f}%)")
            try:
                hot_stocks = self._fetch_ths_full_no_dedup() or []
            except Exception:
                hot_stocks = []
            picked = []
            for it in hot_stocks:
                code = str(it.get("股票代码", "")).strip()
                nm = str(it.get("股票名称", "")).strip()
                if code and nm:
                    picked.append(f"{nm}({code})")
                if len(picked) >= 8:
                    break
            if picked:
                lines.append("候选股票(热度样本,需二次核验基本面/公告/流动性):")
                lines.append("  " + ",".join(picked))
            else:
                lines.append("候选股票:未获取到热榜样本,请先点“完整刷新“再试。")
        elif cat == "仓位":
            if strength == "偏强":
                lines.append("仓位建议:50%~75%,分两到三笔递进,不建议一键满仓。")
            elif strength == "偏弱":
                lines.append("仓位建议:0%~25%,以防守和等待确认为主。")
            else:
                lines.append("仓位建议:25%~45%,保持机动性。")
            lines.append("风控补充:单票止损与账户回撤阈值需同时生效。")
        else:
            lines.append("风控建议:按“单票止损 + 账户回撤熔断 + 行业集中度上限“三层执行。")
            if strength == "偏弱":
                lines.append("当前偏弱,建议缩短持仓观察周期并降低单票暴露。")
        lines.append("")
        lines.append("说明:以上为规则化 AI 辅助,不构成投资建议。")
        return "\n".join(lines)

    def _compose_quant_all_skills_ai_advice(self, catalog, snap, spot, concept_lines):
        """一键按全部 Skill 输出依次建议。"""
        parts = ["【一键AI量化】基于右上最新盘面,按左侧 Skill 逐条给出建议", ""]
        for it in catalog or []:
            parts.append(self._compose_quant_skill_ai_advice(it, snap, spot, concept_lines))
            parts.append("\n" + ("-" * 66) + "\n")
        return "\n".join(parts)


__all__ = ["AiMixin"]

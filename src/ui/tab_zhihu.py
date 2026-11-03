"""知乎 CLI 搜索弹窗 Mixin

使用官方 zhihu-cli (binary_path 固定) 访问知乎开放平台:
  - hot              → 知乎热榜 JSON
  - search zhihu     → 知乎社区搜索 (Title, AuthorName, ContentText, Url)
  - search global    → 全网搜索
  - answer           → 知乎直答 (AI 综合)
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk


# ── zhihu-cli 路径 (setup.sh 安装的位置) ──
ZHIHU_CLI = "/Users/faronpan/Library/Application Support/zhihu-cli/current/zhihu-cli"


class ZhihuMixin:
    """知乎搜索 / 热榜 / 直答 弹窗"""

    # 🧠 快捷搜索模板 (股票研究)
    _ZHIHU_SEARCH_TEMPLATES = [
        "比亚迪 估值分析",
        "贵州茅台 消费降级",
        "宁德时代 技术壁垒",
        "半导体板块 国产替代",
        "美联储加息 A股影响",
        "北向资金 长期逻辑",
        "量化交易 实盘经验",
        "价值投资 vs 趋势交易",
        "AI 算力 产业链",
        "新能源 出海 竞争力",
    ]

    # 📋 知乎直答模板
    _ZHIHU_ANSWER_TEMPLATES = [
        "比亚迪现在估值合理吗？",
        "如何看待当前A股市场？有哪些主要机会和风险？",
        "半导体板块的核心逻辑是什么？未来3年怎么看？",
        "新能源行业还能不能投？主要风险点在哪里？",
        "普通投资者如何建立自己的交易系统？",
        "美联储最新加息对中国市场有什么影响？",
    ]

    # ═══════════════════════════════════════════════════════════
    # 🔧 zhihu-cli 调用封装
    # ═══════════════════════════════════════════════════════════

    def _zhihu_cli_available(self) -> bool:
        return os.path.exists(ZHIHU_CLI) and os.access(ZHIHU_CLI, os.X_OK)

    def _zhihu_run(self, args: list[str], timeout: int = 30) -> dict:
        """同步调用 zhihu-cli, 返回 dict (ok/data/error)"""
        if not self._zhihu_cli_available():
            return {"ok": False, "error": "zhihu-cli 未安装"}
        try:
            result = subprocess.run(
                [ZHIHU_CLI] + args,
                capture_output=True, text=True,
                timeout=timeout,
                env=dict(os.environ),
            )
            raw = result.stdout.strip()
            if not raw:
                err = result.stderr.strip() or "(空输出)"
                return {"ok": False, "error": err}
            # zhihu-cli 输出可能是两种格式:
            #   1. {"ok":true, "data":...}     (新版)
            #   2. {"Code":0, "Data":..., "Message":"success"}  (旧版)
            #   3. 错误: {"ok":false, "error":{"code":"AUTH_REQUIRED", ...}}
            j = json.loads(raw)
            # === 翻译错误为友好文字 ===
            def _friendly_err(jobj):
                # 新版错误: {"ok":false, "error":{"code":"AUTH_REQUIRED","message":"..."}}
                if isinstance(jobj.get("error"), dict):
                    ec = jobj["error"].get("code", "")
                    em = jobj["error"].get("message", "")
                    if ec == "AUTH_REQUIRED":
                        return "🔑 认证失效! 请运行 zhihu-cli auth login 重新登录知乎开放平台"
                    if ec == "TOKEN_EXPIRED":
                        return "⏰ Token 过期, 请重新登录知乎开放平台"
                    return f"❌ {em or ec}"
                # 旧版错误: {"Code":30002, "Message":"quota exceeded"}
                code = jobj.get("Code", 0)
                msg = jobj.get("Message", "")
                if code == 30002:
                    return "📊 API 配额用完了 (quota exceeded), 明天再来吧!"
                if msg:
                    return f"❌ {msg}"
                return f"❌ 未知错误 (code={code})"
            # === 判断成功 ===
            ok_flag = j.get("ok") is True or j.get("Code") == 0
            if ok_flag:
                return {"ok": True, "data": j.get("Data", j.get("data", j))}
            else:
                return {"ok": False, "error": _friendly_err(j)}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"⏳ 超时 ({timeout}s) — 知乎响应慢, 请重试"}
        except json.JSONDecodeError:
            return {"ok": False, "error": f"🔧 返回格式异常: {raw[:80]}"}
        except Exception as e:
            return {"ok": False, "error": f"💥 {e}"}

    def _zhihu_hot(self, limit: int = 10) -> dict:
        return self._zhihu_run(["hot", "--limit", str(limit)])

    def _zhihu_search_zhihu(self, query: str, count: int = 5) -> dict:
        return self._zhihu_run(["search", "zhihu", "--query", query, "--count", str(count)])

    def _zhihu_search_global(self, query: str, count: int = 5) -> dict:
        return self._zhihu_run(["search", "global", "--query", query, "--count", str(count)])

    def _zhihu_answer(self, query: str) -> dict:
        return self._zhihu_run(["answer", "--query", query], timeout=90)

    # ═══════════════════════════════════════════════════════════
    # 🎯 主入口: 知乎弹窗
    # ═══════════════════════════════════════════════════════════

    def _show_zhihu_dialog(self):
        """💬 知乎 AI 搜索 / 热榜 / 直答 弹窗 - 三列 PanedWindow"""
        if not self._zhihu_cli_available():
            tk.messagebox.showerror("知乎 CLI 未安装",
                "zhihu-cli 未找到。请先运行 setup.sh 安装。\n"
                f"预期路径: {ZHIHU_CLI}")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("💬 知乎 · 搜索 / 热榜 / AI直答")
        dlg.geometry("1380x800")
        dlg.transient(self.root)

        # ── 顶栏 ──
        topbar = ttk.Frame(dlg)
        topbar.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(topbar, text="💬 知乎 AI 研究助手",
                 font=("", 13, "bold")).pack(side=tk.LEFT)
        self._zhihu_status = tk.StringVar(value="就绪")
        ttk.Label(topbar, textvariable=self._zhihu_status,
                  foreground="gray").pack(side=tk.LEFT, padx=12)

        # ── 三列 PanedWindow ──
        pw = ttk.PanedWindow(dlg, orient=tk.HORIZONTAL)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ═══ 左列: 功能入口 ═══
        left_frame = ttk.Frame(pw, width=200)
        pw.add(left_frame, weight=0)

        tk.Label(left_frame, text="🔍 功能入口",
                 font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(4, 6))

        # 功能 Listbox
        self._zhihu_feat_lb = tk.Listbox(left_frame, selectmode=tk.SINGLE,
                                          font=("", 11), activestyle="dotbox",
                                          height=8)
        self._zhihu_feat_lb.insert(tk.END, "🔥 知乎热榜 TOP15")
        self._zhihu_feat_lb.insert(tk.END, "💬 知乎社区搜索")
        self._zhihu_feat_lb.insert(tk.END, "🌐 全网搜索")
        self._zhihu_feat_lb.insert(tk.END, "🧠 知乎直答 (AI)")
        self._zhihu_feat_lb.pack(fill=tk.X, padx=4)
        self._zhihu_feat_lb.bind("<<ListboxSelect>>",
                                  lambda e: self._zhihu_on_feat_select(dlg))

        tk.Label(left_frame, text="📋 快捷模板",
                 font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(10, 4))

        # 搜索模板按钮
        for tpl in self._ZHIHU_SEARCH_TEMPLATES[:6]:
            btn = tk.Button(left_frame, text=tpl, cursor="hand2", relief=tk.FLAT,
                            fg="#1565C0", font=("", 9), anchor="w", pady=1,
                            command=lambda tt=tpl: self._zhihu_preset_search(tt))
            btn.pack(anchor="w", padx=6)

        # ═══ 中列: 搜索框 + 结果列表 ═══
        mid_frame = ttk.Frame(pw)
        pw.add(mid_frame, weight=3)

        # 搜索输入区
        search_frame = ttk.Frame(mid_frame)
        search_frame.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(search_frame, text="🔎", font=("", 12)).pack(side=tk.LEFT)
        self._zhihu_query_ent = ttk.Entry(search_frame, font=("", 12))
        self._zhihu_query_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._zhihu_query_ent.bind("<Return>",
                                    lambda e: self._zhihu_do_search("search"))

        self._zhihu_search_btn = ttk.Button(search_frame, text="🔍 搜索", width=10,
                                              command=lambda: self._zhihu_do_search("search"))
        self._zhihu_search_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(search_frame, text="🧠 AI直答", width=8,
                   command=lambda: self._zhihu_do_search("answer")).pack(side=tk.LEFT, padx=2)

        ttk.Button(search_frame, text="🔥 热榜", width=8,
                   command=lambda: self._zhihu_do_search("hot")).pack(side=tk.LEFT, padx=2)

        # Notebook: 结果展示 Tab
        self._zhihu_nb = ttk.Notebook(mid_frame)
        self._zhihu_nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        # Tab 1: 列表
        self._zhihu_list_tab = ttk.Frame(self._zhihu_nb)
        self._zhihu_nb.add(self._zhihu_list_tab, text="📋 结果列表")

        # Tab 2: AI 直答
        self._zhihu_answer_tab = ttk.Frame(self._zhihu_nb)
        self._zhihu_nb.add(self._zhihu_answer_tab, text="🧠 AI 直答")

        # Treeview 框架 (在 list_tab 里)
        self._zhihu_tree_frame = ttk.Frame(self._zhihu_list_tab)
        self._zhihu_tree_frame.pack(fill=tk.BOTH, expand=True)

        # ═══ 右列: 详情预览 ═══
        right_frame = ttk.Frame(pw, width=420)
        pw.add(right_frame, weight=2)

        ttk.Label(right_frame, text="📖 详情预览",
                  font=("", 11, "bold")).pack(anchor="w", padx=6, pady=4)

        self._zhihu_detail_text = tk.Text(right_frame, wrap=tk.WORD,
                                           font=("TkDefaultFont", 10),
                                           background="#fafafa", height=30)
        self._zhihu_detail_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._zhihu_detail_text.configure(state=tk.DISABLED)

        # 初始化: 自动加载热榜
        dlg.after(100, lambda: (
            self._zhihu_feat_lb.selection_clear(0, tk.END),
            self._zhihu_feat_lb.selection_set(0),
            self._zhihu_do_search("hot")
        ))

    # ═══════════════════════════════════════════════════════════
    # 🎯 功能调度
    # ═══════════════════════════════════════════════════════════

    def _zhihu_on_feat_select(self, dlg):
        sel = self._zhihu_feat_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        labels = self._zhihu_feat_lb.get(0, tk.END)
        label = labels[idx]

        if idx == 0:  # 热榜
            self._zhihu_do_search("hot")
        elif idx in (1, 2):  # 知乎搜索 / 全网搜索
            query = self._zhihu_query_ent.get().strip()
            if query:
                self._zhihu_do_search("search_global" if idx == 2 else "search")
            else:
                self._zhihu_status.set("⚠️ 请在搜索框输入关键词")
        elif idx == 3:  # AI 直答
            query = self._zhihu_query_ent.get().strip()
            if query:
                self._zhihu_do_search("answer")
            else:
                self._zhihu_status.set("⚠️ 请在搜索框输入问题")

    def _zhihu_preset_search(self, query: str):
        self._zhihu_query_ent.delete(0, tk.END)
        self._zhihu_query_ent.insert(0, query)
        self._zhihu_do_search("search")

    def _zhihu_do_search(self, mode: str):
        """后台线程调用 zhihu-cli"""
        query = self._zhihu_query_ent.get().strip()

        # 切换到列表 tab
        self._zhihu_nb.select(0)

        # 清空
        for w in self._zhihu_tree_frame.winfo_children():
            w.destroy()
        self._zhihu_detail_text.configure(state=tk.NORMAL)
        self._zhihu_detail_text.delete("1.0", tk.END)
        self._zhihu_detail_text.configure(state=tk.DISABLED)

        if mode == "hot":
            self._zhihu_status.set("⏳ 加载知乎热榜...")
        elif mode in ("search", "search_global"):
            if not query:
                self._zhihu_status.set("⚠️ 请输入搜索关键词")
                return
            self._zhihu_status.set(f"⏳ 搜索「{query}」...")
        elif mode == "answer":
            if not query:
                self._zhihu_status.set("⚠️ 请输入问题")
                return
            self._zhihu_status.set(f"⏳ 知乎 AI 思考中: {query}")

        def _bg():
            t0 = time.time()
            if mode == "hot":
                r = self._zhihu_hot(15)
            elif mode == "search":
                r = self._zhihu_search_zhihu(query, count=5)
            elif mode == "search_global":
                r = self._zhihu_search_global(query, count=5)
            elif mode == "answer":
                r = self._zhihu_answer(query)
            else:
                r = {"ok": False, "error": f"未知模式: {mode}"}
            dt = time.time() - t0
            self.root.after(0, lambda: self._zhihu_render_result(mode, r, dt))

        threading.Thread(target=_bg, daemon=True).start()

    # ═══════════════════════════════════════════════════════════
    # 🎨 渲染
    # ═══════════════════════════════════════════════════════════

    def _zhihu_render_result(self, mode: str, r: dict, dt: float):
        if not r.get("ok"):
            self._zhihu_status.set(f"❌ 失败: {r.get('error', '?')}")
            self._zhihu_show_empty(f"❌ 加载失败\n\n{r.get('error', '未知错误')}")
            return

        data = r.get("data", {})

        if mode == "answer":
            self._zhihu_render_answer(data, dt)
        else:
            items = self._zhihu_extract_items(data)
            self._zhihu_render_list(mode, items, dt)

    def _zhihu_extract_items(self, data) -> list:
        """从不同 API 返回里提取 items 列表"""
        if not data:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ("Items", "items", "Data", "data", "Results", "results"):
                v = data.get(k)
                if isinstance(v, list):
                    return v
            # 热榜嵌套
            if "Data" in data and isinstance(data["Data"], dict):
                for k in ("Items", "items"):
                    v = data["Data"].get(k)
                    if isinstance(v, list):
                        return v
        return []

    def _zhihu_render_list(self, mode: str, items: list, dt: float):
        for w in self._zhihu_tree_frame.winfo_children():
            w.destroy()

        if not items:
            self._zhihu_status.set(f"⚠️ 无结果 ({dt:.1f}s)")
            self._zhihu_show_empty("⚠️ 搜索无结果, 试试换个关键词")
            return

        headers = ("#", "标题 / 问题", "作者", "赞同", "类型")
        tree = ttk.Treeview(self._zhihu_tree_frame, columns=headers,
                            show="headings", height=min(20, len(items)))
        widths = (35, 480, 120, 55, 60)
        for h, w in zip(headers, widths):
            tree.heading(h, text=h)
            tree.column(h, width=w, anchor="w" if h in ("标题 / 问题", "作者") else "center")

        for i, it in enumerate(items):
            if not isinstance(it, dict): continue
            title = (it.get("Title") or it.get("QuestionTitle") or it.get("title") or str(it))
            author = it.get("AuthorName") or it.get("Author") or ""
            vote = it.get("VoteUpCount") or it.get("VoteupCount") or ""
            ctype = it.get("ContentType") or it.get("type") or ("热" if mode == "hot" else "")
            # 截断 title
            title_display = title[:60] + "..." if len(title) > 60 else title
            tree.insert("", tk.END, values=(i + 1, title_display, author, vote, ctype))

        # 选中行 → 右列显示详情
        def _on_select(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(items):
                self._zhihu_show_detail(items[idx])

        def _on_double(event):
            sel = tree.selection()
            if not sel: return
            idx = tree.index(sel[0])
            if 0 <= idx < len(items):
                url = items[idx].get("Url") or items[idx].get("url", "")
                if url:
                    webbrowser.open_new_tab(url)

        tree.bind("<<TreeviewSelect>>", _on_select)
        tree.bind("<Double-1>", _on_double)

        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 滚动条
        sb = ttk.Scrollbar(self._zhihu_tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._zhihu_status.set(f"✅ {mode}: {len(items)} 条 ({dt:.1f}s) | 双击 → 打开知乎原文")

    def _zhihu_render_answer(self, data, dt: float):
        """知乎直答结果渲染"""
        self._zhihu_nb.select(1)

        for w in self._zhihu_tree_frame.winfo_children():
            w.destroy()

        # 答案可能在不同字段里
        answer_text = ""
        sources = []

        if isinstance(data, dict):
            answer_text = (data.get("Answer") or data.get("answer") or
                           data.get("Content") or data.get("content") or
                           data.get("Result") or data.get("result") or "")
            sources = data.get("Sources") or data.get("sources") or []
        elif isinstance(data, str):
            answer_text = data

        # 渲染到 answer tab
        txt_frame = ttk.Frame(self._zhihu_answer_tab)
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        txt = tk.Text(txt_frame, wrap=tk.WORD, font=("TkDefaultFont", 11),
                       background="#fffde7")
        sb = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        if answer_text:
            txt.insert("1.0", f"🧠 知乎 AI 直答\n\n{'='*40}\n\n{answer_text}")
        else:
            txt.insert("1.0", f"📋 知乎直答返回 (原始数据)\n\n{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")

        txt.configure(state=tk.DISABLED)

        # 渲染 sources 到右列
        if sources:
            detail = f"📚 参考来源 ({len(sources)} 条)\n\n"
            for i, s in enumerate(sources[:10]):
                if isinstance(s, dict):
                    detail += f"{i+1}. {s.get('Title', s.get('title', str(s))[:80])}\n"
                    u = s.get("Url") or s.get("url")
                    if u: detail += f"   🔗 {u}\n"
                else:
                    detail += f"{i+1}. {str(s)[:80]}\n"
                detail += "\n"
            self._zhihu_set_detail(detail)

        self._zhihu_status.set(f"✅ AI直答完成 ({dt:.1f}s)")

    def _zhihu_show_detail(self, item: dict):
        """右列详情预览"""
        lines = []
        title = item.get("Title") or item.get("QuestionTitle") or item.get("title", "")
        author = item.get("AuthorName") or item.get("AuthorSignature") or ""
        ctype = item.get("ContentType") or ""
        vote = item.get("VoteUpCount") or 0
        comment = item.get("CommentCount") or 0
        url = item.get("Url") or item.get("url", "")
        summary = item.get("Summary") or ""
        content = item.get("ContentText") or ""

        lines.append(f"📰 {title}")
        lines.append(f"{'─' * 40}")
        if author:
            badge = item.get("AuthorBadgeText") or ""
            lines.append(f"👤 {author}" + (f"  [{badge}]" if badge else ""))
        if ctype or vote or comment:
            parts = []
            if ctype: parts.append(f"类型: {ctype}")
            if vote: parts.append(f"👍 {vote}")
            if comment: parts.append(f"💬 {comment}")
            lines.append(" | ".join(parts))
        if url:
            lines.append(f"\n🔗 {url}")
        if summary:
            lines.append(f"\n📋 摘要:\n{summary[:300]}")
        if content:
            # 知乎直答可能没有 content, 但搜索有
            lines.append(f"\n📖 正文片段:\n{content[:600]}")
            if len(content) > 600:
                lines.append(f"\n... (共 {len(content)} 字)")

        self._zhihu_set_detail("\n".join(lines))

    def _zhihu_set_detail(self, text: str):
        self._zhihu_detail_text.configure(state=tk.NORMAL)
        self._zhihu_detail_text.delete("1.0", tk.END)
        self._zhihu_detail_text.insert("1.0", text)
        self._zhihu_detail_text.configure(state=tk.DISABLED)

    def _zhihu_show_empty(self, text: str):
        self._zhihu_show_detail(text)

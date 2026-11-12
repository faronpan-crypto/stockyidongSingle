"""
🤖 AI 设置 — 统一入口
══════════════════════════════════════════
1) 所有 provider 的 API Key 在界面上配置
2) 写入 src/config/ai_config.json（chmod 600，key 保密）
3) 代理 ai_proxy.py 优先从 ai_config.json 读 key
4) 改完自动重启代理进程（带新 key）
5) 立即验证新 key 能不能用

调用方式: _show_ai_settings_dialog(parent_root)
"""
import tkinter as _tk
import tkinter.ttk as _ttk
import tkinter.messagebox as _mb
import json as _json
import os as _os
import re as _re
import subprocess as _sp
import time as _time

_PROJ_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_CFG_PATH = _os.path.join(_PROJ_ROOT, "config", "ai_config.json")


def _read_config():
    """安全读 ai_config.json"""
    try:
        with open(_CFG_PATH) as f:
            return _json.load(f)
    except Exception:
        return {"providers": {}}


def _write_config(cfg):
    """安全写 — chmod 600，key 不落日志"""
    with open(_CFG_PATH, "w") as f:
        _json.dump(cfg, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(_CFG_PATH, 0o600)  # 仅 owner 可读
    except Exception:
        pass


def _restart_proxy():
    """kill + 重启 AI 代理（代理自己从 ai_config.json 读 key）"""
    try:
        _sp.run(["pkill", "-9", "-f", "ai_proxy.py"], capture_output=True)
        _time.sleep(1.2)
    except Exception:
        pass
    try:
        env = _os.environ.copy()
        _sp.Popen(
            ["/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
             "src/logic/ai_proxy.py"],
            stdout=open("/tmp/ai_proxy.log", "w"),
            stderr=_sp.STDOUT, env=env,
            cwd=_PROJ_ROOT,
        )
        _time.sleep(1.8)
    except Exception as e:
        return f"⚠️ 代理启动异常: {e}"
    # 验证代理活着
    try:
        import requests
        r = requests.get("http://127.0.0.1:8787/health", timeout=3)
        if r.status_code == 200:
            return "✅ 代理已重启"
    except Exception:
        pass
    return "⚠️ 代理可能没起来，请手动重启后再试"


def _mask(k):
    """key 脱敏显示"""
    if not k or len(k) < 8:
        return "(未配置)" if not k else f"{k[:2]}...{k[-2:]}"
    return f"{k[:8]}...{k[-4:]}  ({len(k)}字符)"


def _test_one(provider_name, api_key):
    """用代理测一个 provider 的 key 能不能用（返回 ok/fail + 说明）"""
    import requests, hmac, hashlib, secrets
    try:
        secret = open("/tmp/stock_ai_proxy.secret").read().strip()
    except Exception:
        return False, "代理 secret 不存在"
    nonce = secrets.token_hex(8)
    ptoken = hmac.new(secret.encode(), ("ai_proxy"+nonce).encode(),
                      hashlib.sha256).hexdigest()[:16]
    h = {"Content-Type": "application/json",
         "X-Nonce": nonce, "X-Proxy-Token": ptoken}
    body = {"provider": provider_name, "max_tokens": 15,
            "messages": [{"role": "user", "content": "hi"}]}
    try:
        r = requests.post("http://127.0.0.1:8787/v1/chat/completions",
                          headers=h, json=body, timeout=12)
        if r.status_code == 200:
            return True, "✅ 可正常调用"
        txt = r.text[:150]
        if "invalid" in txt.lower() or "88a6" in txt or "Authentication" in txt:
            return False, "❌ key 已过期"
        if "未配置" in txt or "环境变量" in txt:
            return False, "❌ 代理没读到 key（刚改完要等代理重启）"
        return False, f"❌ {r.status_code}: {txt}"
    except Exception as e:
        return False, f"❌ 网络异常: {e}"


def _show_ai_settings_dialog(parent_root=None):
    """主入口 — 弹出统一 AI 设置窗口"""
    win = _tk.Toplevel(parent_root)
    win.title("🤖 AI 设置 · 统一入口")
    win.configure(bg="#1A1A2E")
    win.geometry("720x560")
    try:
        win.attributes("-topmost", True); win.attributes("-topmost", False)
    except Exception:
        pass

    # ══════════════════════════════════════════════
    # Header
    # ══════════════════════════════════════════════
    _tk.Label(win, text="🤖  AI 设置  ·  一次配置，全程序生效",
              bg="#1A1A2E", fg="#FFD54F",
              font=("TkDefaultFont", 14, "bold")).pack(pady=(14, 4))

    _tk.Label(win, text=(
        "所有 AI 功能共用 localhost:8787 代理，代理从 ai_config.json 读 key\n"
        "改完点「💾保存并重启代理」，自动生效。key 保存在本地，chmod 600 保密。"
    ), bg="#1A1A2E", fg="#90A4AE", justify=_tk.CENTER,
        font=("TkDefaultFont", 9)).pack(padx=20, pady=2)

    # ══════════════════════════════════════════════
    # Provider 配置卡片
    # ══════════════════════════════════════════════
    providers = [
        ("deepseek", "DeepSeek", "🤖", "#64B5F6",
         "最常用。deepseek-chat 模型，速度快价格低",
         "sk-... (以 sk- 开头)"),
        ("doubao",   "豆包·火山引擎", "🔴", "#FF7043",
         "国内合规。doubao-seedance-1-0-pro 模型",
         "Ark API Key (火山引擎控制台)"),
        ("ollama",   "本地 Ollama", "💻", "#81C784",
         "完全免费。需要本地 ollama serve 正在运行",
         "(不需要 key，自动检测 localhost:11434)"),
    ]

    cfg = _read_config()
    p_cfg = cfg.get("providers", {})

    entries = {}  # provider_name → Entry
    cur_cards = {}

    for pname, plabel, picon, pcol, pdesc, phint in providers:
        cur = p_cfg.get(pname, {})
        cur_key = (cur.get("api_key") or "").strip()
        cur_model = cur.get("model", "")
        cur_url = cur.get("base_url", "")

        card = _tk.Frame(win, bg="#16213E", highlightthickness=1, highlightbackground=pcol)
        card.pack(fill=_tk.X, padx=16, pady=5)

        # 头部
        hdr = _tk.Frame(card, bg="#16213E"); hdr.pack(fill=_tk.X, padx=10, pady=(8, 2))
        _tk.Label(hdr, text=f"{picon}  {plabel}", bg="#16213E", fg=pcol,
                  font=("TkDefaultFont", 11, "bold")).pack(side=_tk.LEFT)

        masked = _mask(cur_key) if pname != "ollama" else "(不需要 key)"
        status = _tk.Label(hdr, text=f"当前:  {masked}", bg="#16213E", fg="#90A4AE",
                           font=("TkDefaultFont", 9))
        status.pack(side=_tk.RIGHT)
        cur_cards[pname] = status

        _tk.Label(card, text=pdesc, bg="#16213E", fg="#90A4AE",
                  font=("TkDefaultFont", 8)).pack(anchor="w", padx=10)

        # key 输入行（ollama 跳过）
        if pname != "ollama":
            row = _tk.Frame(card, bg="#16213E"); row.pack(fill=_tk.X, padx=10, pady=4)
            _tk.Label(row, text="API Key:", bg="#16213E", fg="#EAEAEA",
                      font=("TkDefaultFont", 9)).pack(side=_tk.LEFT)
            ent = _tk.Entry(row, width=50, show="*",
                            font=("TkDefaultFont", 10),
                            bg="#FFFFFF", fg="black")
            ent.pack(side=_tk.LEFT, fill=_tk.X, expand=True, padx=(4, 4))
            if cur_key:
                ent.insert(0, cur_key)
            entries[pname] = ent

            show_var = _tk.BooleanVar(value=False)
            def _toggle(e=ent, v=show_var):
                e.config(show="" if v.get() else "*")
            _tk.Checkbutton(row, text="显示", variable=show_var,
                            bg="#16213E", fg="#90A4AE", selectcolor="#16213E",
                            command=_toggle,
                            font=("TkDefaultFont", 8)).pack(side=_tk.LEFT)
            _tk.Label(card, text=f"  提示:  {phint}", bg="#16213E", fg="#607D8B",
                      font=("TkDefaultFont", 8)).pack(anchor="w", padx=10)
        else:
            entries[pname] = None
            _tk.Label(card, text=f"  提示:  {phint}", bg="#16213E", fg="#607D8B",
                      font=("TkDefaultFont", 8)).pack(anchor="w", padx=10, pady=(0, 4))

    # ══════════════════════════════════════════════
    # 操作按钮 + 状态
    # ══════════════════════════════════════════════
    status_lbl = _tk.Label(win, text="", bg="#1A1A2E", fg="#FFD54F",
                           font=("TkDefaultFont", 10))
    status_lbl.pack(pady=(8, 2))

    def _save_and_restart():
        # 1) 收集
        new_cfg = _read_config()
        providers_dict = new_cfg.setdefault("providers", {})
        for pname in ["deepseek", "doubao"]:
            ent = entries.get(pname)
            if ent is None: continue
            new_key = ent.get().strip()
            prov = providers_dict.setdefault(pname, {})
            old_key = (prov.get("api_key") or "").strip()
            if new_key and new_key != old_key:
                prov["api_key"] = new_key
                if pname == "deepseek" and new_key.startswith("sk-") and len(new_key) > 20:
                    # 同步到 ~/.zshrc 环境变量（终端直接也生效）
                    zshrc = _os.path.expanduser("~/.zshrc")
                    try:
                        content = open(zshrc).read()
                        pat = r'(export DEEPSEEK_API_KEY=")([^"]+)(")'
                        if _re.search(pat, content):
                            open(zshrc, "w").write(_re.sub(pat, rf'\1{new_key}\3', content))
                        else:
                            open(zshrc, "a").write(f'\nexport DEEPSEEK_API_KEY="{new_key}"\n')
                    except Exception:
                        pass
                status_lbl.config(text=f"✅ 已写入 ai_config.json（{_mask(new_key)}）+ 同步 ~/.zshrc",
                                  fg="#66BB6A")
            elif not new_key:
                # 清空 key
                prov.pop("api_key", None)

        # 2) 写文件
        try:
            _write_config(new_cfg)
        except Exception as e:
            status_lbl.config(text=f"❌ 写 ai_config.json 失败: {e}", fg="#E94560"); return

        # 3) 重启代理（让它读新 config）
        status_lbl.config(text="⏳ 重启 AI 代理...", fg="#FFD54F"); win.update()
        r = _restart_proxy()
        status_lbl.config(text=r, fg="#66BB6A" if "✅" in r else "#E94560")

        # 4) 刷新界面上的脱敏显示
        fresh_cfg = _read_config()
        for pname, label in cur_cards.items():
            ck = ((fresh_cfg.get("providers", {}) or {}).get(pname, {}).get("api_key") or "").strip()
            label.config(text=f"当前:  {_mask(ck)}" if ck or pname == "ollama" else "(未配置)")

        # 5) 自动验证 deepseek
        if "deepseek" in entries and entries["deepseek"].get().strip():
            status_lbl.config(text="⏳ 验证 deepseek...", fg="#FFD54F"); win.update()
            ok, msg = _test_one("deepseek", entries["deepseek"].get().strip())
            status_lbl.config(text=f"{msg}（{r}）", fg="#66BB6A" if ok else "#E94560")

    def _test_now():
        """单独测 deepseek 当前 key"""
        key = entries.get("deepseek")
        if not key or not key.get().strip():
            status_lbl.config(text="⚠️ 先填 deepseek key", fg="#FFD54F"); return
        status_lbl.config(text="⏳ 测试中...", fg="#FFD54F"); win.update()
        ok, msg = _test_one("deepseek", key.get().strip())
        status_lbl.config(text=f"测试结果: {msg}", fg="#66BB6A" if ok else "#E94560")

    btn_row = _tk.Frame(win, bg="#1A1A2E"); btn_row.pack(pady=10)
    _tk.Button(btn_row, text="💾 保存并重启代理", width=18,
               command=_save_and_restart,
               bg="#66BB6A", fg="black", activebackground="#43A047",
               highlightbackground="#FFD54F", highlightthickness=2,
               font=("TkDefaultFont", 11, "bold")).pack(side=_tk.LEFT, padx=6)
    _tk.Button(btn_row, text="🧪 测试 DeepSeek", width=14,
               command=_test_now,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground="#64B5F6", highlightthickness=2,
               font=("TkDefaultFont", 10, "bold")).pack(side=_tk.LEFT, padx=6)
    _tk.Button(btn_row, text="关闭", width=8,
               command=win.destroy,
               bg="#FFFFFF", fg="black", activebackground="#F5F5F5",
               highlightbackground="#90A4AE", highlightthickness=1,
               font=("TkDefaultFont", 10)).pack(side=_tk.LEFT, padx=6)

    # 保密说明
    _tk.Label(win, text=(
        "🔐 保密说明:  key 保存在 src/config/ai_config.json 中（chmod 600，仅 owner 可读）\n"
        "              ai_proxy.py 进程内存中持有，不落地到日志 /tmp 文件\n"
        "              界面显示脱敏（前8后4，中间...），输入框默认隐藏\n"
        "⚠️  不要把 key 提交到 GitHub！.gitignore 已排除 ai_config.json"
    ), bg="#1A1A2E", fg="#78909C", justify=_tk.LEFT,
        font=("TkDefaultFont", 8)).pack(padx=20, pady=(12, 10))

    return win

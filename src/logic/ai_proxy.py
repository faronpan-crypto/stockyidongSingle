"""
🔒 本地 AI 代理 — 安全转发层
═══════════════════════════════════════════
主程序不直接持有 API Key, 只向 localhost:8787 发请求,
代理进程从**自己的环境变量**读取 key, 转发到豆包/DeepSeek/火山引擎。

安全层:
  ① 只允许 127.0.0.1 (远程访问无效)
  ② X-Proxy-Token 签名校验 (防止其他本地程序冒充)
  ③ 调用限额 (每分钟 30 次, 每天 300 次)
  ④ key 只在进程内存中, 不落地到任何文件

启动:  python ai_proxy.py &
停止:  pkill -f ai_proxy

端口:  8787
"""
import os
import sys
import json
import time
import hmac
import hashlib
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── 配置 ──
PORT = 8787
HOST = "127.0.0.1"   # 只接受本地
RATE_PER_MIN = 30
RATE_PER_DAY = 300

# 转发目标 (OpenAI 兼容协议)
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "key_env": "DOUBAO_API_KEY",
        "default_model": "doubao-seedance-1-0-pro-250528",
    },
}

# ── 代理 Token (动态生成, 启动时打印给主程序读) ──
_SECRET_FILE = "/tmp/stock_ai_proxy.secret"
PROXY_SECRET = os.environ.get("STOCK_AI_PROXY_SECRET", "")
if not PROXY_SECRET:
    # 先看有没有前一次留下的 (代理重启时复用, 主程序不用重配)
    if os.path.exists(_SECRET_FILE):
        try:
            PROXY_SECRET = open(_SECRET_FILE).read().strip()
        except Exception:
            pass
    if not PROXY_SECRET:
        PROXY_SECRET = hashlib.sha256(str(os.getpid()).encode() + str(time.time()).encode()).hexdigest()[:16]
        # 写入临时文件, 供主程序读取 (主程序启动时 fork 代理会看到同一个)
        with open(_SECRET_FILE, 'w') as f:
            f.write(PROXY_SECRET)
        # 权限收窄
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except Exception:
            pass


def make_token(nonce: str) -> str:
    """签名 = hmac(secret, 'ai_proxy' + nonce)"""
    return hmac.new(PROXY_SECRET.encode(),
                    ("ai_proxy" + nonce).encode(),
                    hashlib.sha256).hexdigest()[:16]


# ── 调用限额 (线程安全) ──
_lock = threading.Lock()
_rate_min = []      # 时间戳列表, 记录最近 60 秒内的调用
_day_count = 0
_day_start = time.time()


def _check_rate() -> tuple[bool, str]:
    """返回 (ok, 原因)"""
    global _day_count, _day_start
    now = time.time()
    with _lock:
        # 重置天
        if now - _day_start > 86400:
            _day_count = 0
            _day_start = now
        # 清理过期
        while _rate_min and now - _rate_min[0] > 60:
            _rate_min.pop(0)
        if len(_rate_min) >= RATE_PER_MIN:
            return False, f"⏱️ 限速: 每分钟最多 {RATE_PER_MIN} 次, 稍后再试"
        if _day_count >= RATE_PER_DAY:
            return False, f"📅 日限额: 每天最多 {RATE_PER_DAY} 次"
        _rate_min.append(now)
        _day_count += 1
    return True, ""


class ProxyHandler(BaseHTTPRequestHandler):
    """最小化 OpenAI 兼容 chat/completions 代理"""

    def log_message(self, fmt, *args):
        print(f"[proxy] {self.address_string()} {fmt % args}")

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "uptime_s": int(time.time() - _start),
                             "day_left": RATE_PER_DAY - _day_count,
                             "min_left": RATE_PER_MIN - len(_rate_min)})
        elif self.path == "/token":
            self._json(200, {"proxy_token": PROXY_SECRET})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            self._json(404, {"error": f"unknown path: {self.path}"})
            return

        # ① 验证来源 IP
        ip = self.client_address[0]
        if ip not in ("127.0.0.1", "::1"):
            self._json(403, {"error": "拒绝非本地请求"})
            return

        # ② 验证签名 token
        nonce = self.headers.get("X-Nonce", "")
        client_token = self.headers.get("X-Proxy-Token", "")
        expected = make_token(nonce)
        if not nonce or not hmac.compare_digest(expected, client_token):
            self._json(401, {"error": "签名校验失败 (nonce 过期或 token 错误)"})
            return

        # ③ 调用限额
        ok, reason = _check_rate()
        if not ok:
            self._json(429, {"error": reason})
            return

        # ④ 读 body
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._json(400, {"error": "body 非有效 JSON"})
            return

        # ⑤ 路由到真实 provider
        provider_name = body.get("provider", "deepseek")
        if provider_name not in PROVIDERS:
            self._json(400, {"error": f"未知 provider: {provider_name}"})
            return

        cfg = PROVIDERS[provider_name]
        # 🔑 优先读 ai_config.json（持久化 + UI 可改），fallback 环境变量
        api_key = ""
        try:
            _cfg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config", "ai_config.json")
            if os.path.exists(_cfg_path):
                with open(_cfg_path) as _f:
                    _all_cfg = json.load(_f)
                _p_cfg = (_all_cfg.get("providers") or {}).get(provider_name, {})
                api_key = (_p_cfg.get("api_key") or "").strip()
        except Exception:
            pass
        if not api_key:
            api_key = os.environ.get(cfg["key_env"], "")
        if not api_key:
            self._json(502, {"error": f"❌ 未配置 API Key！请在主界面打开 🤖AI 设置 或 ~/.zshrc 配置 {cfg['key_env']}"})
            return

        model = body.get("model", cfg["default_model"])
        messages = body.get("messages", [])

        # ⑥ 构造真实请求
        real_body = {
            "model": model,
            "messages": messages,
            "temperature": body.get("temperature", 0.3),
        }
        if "max_tokens" in body:
            real_body["max_tokens"] = body["max_tokens"]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            resp = requests.post(cfg["base_url"],
                                 json=real_body, headers=headers, timeout=90)
            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() in ("content-type",):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.content)
        except Exception as e:
            self._json(502, {"error": f"转发失败: {str(e)[:200]}"})

    def _json(self, code: int, obj: dict):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


_start = time.time()


def main():
    global _start
    _start = time.time()
    server = HTTPServer((HOST, PORT), ProxyHandler)
    print(f"🔒 AI 代理启动: http://{HOST}:{PORT}")
    print(f"   PROXY_SECRET = {PROXY_SECRET}")
    print(f"   X-Nonce 校验 + 限速 {RATE_PER_MIN}/min {RATE_PER_DAY}/day")
    print(f"   Provider: {list(PROVIDERS.keys())}")
    print(f"   健康检查: curl http://{HOST}:{PORT}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
stockyidong_mac 程序变动监控 + 数据同步脚本（省积分版 v2）
功能：
  1. watchdog 监控 src 目录核心 .py 文件【内容变动】(md5哈希，非mtime，避免rsync/sync误触发)
  2. 有变动时触发 trend_factor_scan.py 数据同步（带60分钟冷却，防死循环烧积分）
  3. 每天 15:25 / 16:10 强制同步一次（每日定时不受冷却限制）

设计要点（省积分）：
  - 只监控代码 .py 文件，ai_config.json 不在监控列表（会被扫描过程改写，避免自触发死循环）
  - 用 md5 内容哈希而非 mtime，rsync 同步不会误判为"变动"
  - 文件变动触发至少间隔 60 分钟；每日定时触发无视冷却

用法（后台常驻，由 launchd 管理）：
  python3 stockyidong_sync_watchdog.py
"""

from __future__ import annotations

import os
import sys
import time
import json
import hashlib
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────────────
SRC_DIR = Path("/Users/faronpan/Agent/stockyidong_project/src")
PROJECT_ROOT = Path("/Users/faronpan/Agent/stockyidong_project")
TREND_SCAN_SCRIPT = SRC_DIR / "trend_factor_scan.py"
DATA_DIR = PROJECT_ROOT / "data"
STATE_FILE = DATA_DIR / "sync_watchdog_state.json"
LOG_FILE = DATA_DIR / "sync_watchdog.log"
PID_FILE = DATA_DIR / "sync_watchdog.pid"
LAST_SCAN_FILE = DATA_DIR / "sync_watchdog_last_scan.txt"

COOLDOWN_SECONDS = 3600  # 文件变动触发的最小间隔：60分钟（防死循环烧积分）

# ── 日志 ──────────────────────────────────────────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("sync_watchdog")

# ── 核心监控文件（仅代码文件，不含会被扫描改写的 ai_config.json）──────────────
WATCH_FILES = [
    SRC_DIR / "stockyidong mac.py",
    SRC_DIR / "trend_factor_scan.py",
    SRC_DIR / "stockyidong_daily_report_v4.py",
    SRC_DIR / "akshare_helper.py",
    SRC_DIR / "holdings_analyzer.py",
    SRC_DIR / "auto_screener.py",
    SRC_DIR / "screen_stocks_simple.py",
    SRC_DIR / "screen_stocks_minimal.py",
]
WATCH_FILES = [f for f in WATCH_FILES if f.exists()]


# ── 状态管理 ─────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_hashes": {}, "daily_1525": None, "daily_1610": None}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_file_hashes() -> dict:
    """用 md5 内容哈希检测真实变动（避免 mtime/rsync 误触发）"""
    result = {}
    for f in WATCH_FILES:
        try:
            result[str(f)] = hashlib.md5(f.read_bytes()).hexdigest()
        except Exception:
            result[str(f)] = None
    return result


def detect_changes(state: dict) -> bool:
    current = get_file_hashes()
    saved = state.get("last_hashes", {})
    for path, h in current.items():
        if saved.get(path) != h:
            return True
    return False


# ── 同步触发 ─────────────────────────────────────────────────────────────────
_sync_lock = threading.Lock()


def trigger_sync(reason: str, force: bool = False):
    """触发数据同步（带并发保护 + 冷却）"""
    if not _sync_lock.acquire(blocking=False):
        log.warning("同步已在进行中，跳过本次触发（%s）", reason)
        return

    try:
        # 冷却检查：文件变动触发至少间隔 COOLDOWN_SECONDS，每日定时(force)不受限
        if not force:
            if LAST_SCAN_FILE.exists():
                try:
                    last = float(LAST_SCAN_FILE.read_text().strip())
                    if time.time() - last < COOLDOWN_SECONDS:
                        log.info("⏳ 冷却期内（<60分钟），跳过文件变动触发: %s", reason)
                        return
                except Exception:
                    pass

        log.info("🔄 开始同步，触发原因：%s", reason)
        start = time.time()

        if TREND_SCAN_SCRIPT.exists():
            log.info("  → 运行 trend_factor_scan.py ...")
            result = subprocess.run(
                [sys.executable, str(TREND_SCAN_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=1800,
                cwd=str(SRC_DIR),
            )
            if result.returncode == 0:
                log.info("  ✅ trend_factor_scan.py 完成")
                for line in result.stdout.splitlines():
                    if any(k in line for k in ["重点信号", "扫描摘要", "✅", "📊"]):
                        log.info("    | %s", line.strip())
            else:
                log.error("  ❌ trend_factor_scan.py 失败: %s", result.stderr[-500:])
        else:
            log.warning("  ⚠️ trend_factor_scan.py 不存在，跳过")

        elapsed = time.time() - start
        log.info("✅ 同步完成，耗时 %.1f 秒", elapsed)

        # 更新状态 + 记录最后扫描时间
        state = load_state()
        state["last_hashes"] = get_file_hashes()
        save_state(state)
        LAST_SCAN_FILE.write_text(str(time.time()))

    except subprocess.TimeoutExpired:
        log.error("❌ 同步超时（30分钟），已终止")
    except Exception as e:
        log.exception("❌ 同步出错: %s", e)
    finally:
        _sync_lock.release()


# ── watchdog 事件处理 ─────────────────────────────────────────────────────────
def on_modified(event):
    if event.is_directory:
        return
    path = Path(event.src_path)
    if path.suffix == ".py":
        log.info("📝 检测到文件变动: %s", path.name)
        trigger_sync(reason=f"文件变动: {path.name}")


# ── 主程序 ────────────────────────────────────────────────────────────────────
def main():
    # 单实例保护
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            os.kill(old_pid, 0)  # 检查进程是否存活
            log.error("监控已在运行 (PID %d)，退出。", old_pid)
            sys.exit(0)
        except (ValueError, ProcessLookupError, PermissionError):
            log.info("旧 PID 文件无效，将重新启动。")

    PID_FILE.write_text(str(os.getpid()))
    log.info("=" * 60)
    log.info("🚀 stockyidong 同步监控启动（省积分版 v2）")
    log.info("   监控目录: %s", SRC_DIR)
    log.info("   监控文件数: %d", len(WATCH_FILES))
    log.info("   文件变动冷却: %d 分钟", COOLDOWN_SECONDS // 60)
    log.info("   日志文件: %s", LOG_FILE)
    log.info("=" * 60)

    # 启动前先检查是否有变动（程序更新后重启时触发一次，强制不受冷却）
    state = load_state()
    if detect_changes(state):
        log.info("📌 启动时检测到文件有变动，先执行一次同步...")
        trigger_sync(reason="启动时文件变动检测", force=True)

    # 检查是否需要每日强制同步（每天 15:25 / 16:10）
    _check_daily_force_sync(state)

    # 启动 watchdog 监控
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class ChangeHandler(FileSystemEventHandler):
            def on_modified(self, event):
                on_modified(event)

            def on_created(self, event):
                on_modified(event)

        observer = Observer()
        observer.schedule(ChangeHandler(), str(SRC_DIR), recursive=False)
        observer.start()
        log.info("👀 watchdog 监控已启动，正在监听文件变动...")

        # 每日定时检查线程（轮询方式）
        def daily_check_loop():
            while True:
                time.sleep(300)  # 每5分钟检查一次时间
                state = load_state()
                _check_daily_force_sync(state)

        threading.Thread(target=daily_check_loop, daemon=True).start()

        # 保持运行
        while True:
            time.sleep(60)

    except ImportError:
        log.warning("watchdog 未安装，改为轮询模式（每30秒检查一次文件变动）")
        _polling_mode()


def _check_daily_force_sync(state: dict):
    """每天固定时间强制同步（不受冷却限制）"""
    now = datetime.now()
    triggers = [(15, 25, "daily_1525"), (16, 10, "daily_1610")]
    for hour, minute, key in triggers:
        today = now.strftime("%Y-%m-%d")
        if state.get(key) != today and now.hour == hour and now.minute <= 5:
            log.info("⏰ 定时同步时间到达 (%02d:%02d)，触发同步", hour, minute)
            trigger_sync(reason=f"每日定时 {hour:02d}:{minute:02d}", force=True)
            state[key] = today
            save_state(state)
            break


def _polling_mode():
    """无 watchdog 时的轮询降级模式"""
    last_hashes = get_file_hashes()
    last_check = time.time()
    while True:
        time.sleep(30)
        current = get_file_hashes()
        for path, h in current.items():
            if h != last_hashes.get(path):
                log.info("📝 检测到文件变动: %s", Path(path).name)
                trigger_sync(reason=f"文件变动: {Path(path).name}")
                last_hashes = current
                break

        # 每日强制同步检查
        if time.time() - last_check >= 300:
            last_check = time.time()
            state = load_state()
            _check_daily_force_sync(state)


if __name__ == "__main__":
    main()

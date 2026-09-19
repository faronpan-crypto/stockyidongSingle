#!/usr/bin/env python3
"""
tushare_helper.py
带超时保护 + 本地缓存的 TuShare 封装。

TuShare 接口：
  - pro.daily(ts_code, start_date)  → 日线（收盘）
  - pro.daily_basic(ts_code, trade_date) → 市值（total_mv，单位：万元）

特性：
  - 单只股票请求超时 10 秒，不会卡死整个流程
  - 结果缓存到 ~/.cache/stockyidong/tushare_cache.json
  - 缓存默认 6 小时有效
  - 自动转换代码格式：600519 → 600519.SH，000066 → 000066.SZ

用法：
  from tushare_helper import get_stock_ma_batch
  results = get_stock_ma_batch(["600519", "000066"], refresh_all=False)
"""

import datetime
import json
import multiprocessing
import os
import time

# ========== 配置 ==========
CACHE_DIR  = os.path.expanduser("~/.cache/stockyidong")
CACHE_FILE = os.path.join(CACHE_DIR, "tushare_cache.json")
TIMEOUT     = 10       # 单只股票请求超时（秒）
MAX_AGE_H   = 6        # 缓存有效期（小时）
# ================================


def _code_to_ts(code6):
    """6 位代码 → TuShare 格式（600519 → 600519.SH）"""
    if code6.startswith("6") or code6.startswith("5"):
        return f"{code6}.SH"
    else:
        return f"{code6}.SZ"


def _fetch_one(code6, token, result_queue):
    """
    子进程函数：用 TuShare 请求单只股票的均线和市值。
    结果放入 result_queue。
    """
    try:
        import tushare as ts

        pro = ts.pro_api(token)

        ts_code = _code_to_ts(code6)

        # 1. 获取日线（最近 120 个交易日）
        end_date = datetime.datetime.now().strftime("%Y%m%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=240)).strftime("%Y%m%d")
        df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            result_queue.put({"code": code6, "error": "empty daily df"})
            return

        # TuShare daily 返回的是倒序（最新在最后），按 trade_date 排序
        df = df.sort_values("trade_date").reset_index(drop=True)

        # 取收盘列（close）
        if "close" not in df.columns:
            result_queue.put({"code": code6, "error": "no close col in daily"})
            return

        closes = []
        for v in df["close"].tolist():
            try:
                closes.append(float(v))
            except (TypeError, ValueError):
                pass

        if len(closes) < 60:
            result_queue.put({"code": code6, "error": f"not enough data: {len(closes)}"})
            return

        last_close = closes[-1]
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60

        near_ma10 = abs(last_close - ma10) / ma10 < 0.03
        near_ma20 = abs(last_close - ma20) / ma20 < 0.03
        ma_bullish = (ma10 > ma20 > ma60)

        # 2. 获取市值（最新交易日）
        market_cap = None
        try:
            # 用最新一天的 trade_date 查 daily_basic
            latest_date = df["trade_date"].iloc[-1]
            basic_df = pro.daily_basic(ts_code=ts_code, trade_date=latest_date)
            if basic_df is not None and not basic_df.empty and "total_mv" in basic_df.columns:
                total_mv_wan = float(basic_df.iloc[0]["total_mv"])  # 单位：万元
                market_cap = total_mv_wan / 10000.0  # 转换为亿
        except Exception:
            pass  # 市值获取失败不阻断

        result_queue.put({
            "code": code6,
            "data": {
                "close": last_close,
                "ma10": ma10,
                "ma20": ma20,
                "ma60": ma60,
                "near_ma10": near_ma10,
                "near_ma20": near_ma20,
                "ma_bullish": ma_bullish,
                "market_cap": market_cap,
                "ts": time.time(),
            }
        })

    except Exception as e:
        result_queue.put({"code": code6, "error": str(e)})


def fetch_one_with_timeout(code6, token, timeout=TIMEOUT):
    """
    带超时的单只股票请求。
    返回 dict 或 None（超时/失败）。
    """
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_fetch_one, args=(code6, token, result_queue))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return None  # 超时
    if not result_queue.empty():
        result = result_queue.get()
        if "error" in result:
            return None
        return result.get("data")
    return None


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def get_stock_ma_batch(codes, token=None, refresh_all=False, verbose=True):
    """
    批量获取股票均线/市值数据，带缓存。

    参数：
      codes:       股票代码列表（6 位纯数字字符串）
      token:       TuShare token（None 则自动从 ~/.tushare/token 或环境变量读取）
      refresh_all: True=强制刷新所有；False=只刷新过期缓存
      verbose:     打印进度

    返回：
      {code: {close, ma10, ma20, ma60, near_ma10, near_ma20, ma_bullish, market_cap}, ...}
    """
    # 读取 token
    if not token:
        token_file = os.path.expanduser("~/.tushare/token")
        if os.path.exists(token_file):
            with open(token_file, "r") as f:
                token = f.read().strip()
        if not token:
            token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            print("[ERROR] TuShare token 未找到，请检查 ~/.tushare/token 或设置 TUSHARE_TOKEN 环境变量")
            return {}

    cache = load_cache()
    now = time.time()
    max_age = MAX_AGE_H * 3600
    results = {}
    need_fetch = []

    # 第一遍：从缓存加载
    for code in codes:
        if refresh_all:
            need_fetch.append(code)
            continue
        entry = cache.get(code)
        if not entry:
            need_fetch.append(code)
            continue
        ts_val = entry.get("ts", 0)
        if now - ts_val > max_age:
            need_fetch.append(code)
        else:
            results[code] = entry
            if verbose:
                print(f"  [缓存] {code}: close={entry.get('close', 0):.2f} ma10={entry.get('ma10', 0):.2f} ...")

    if not need_fetch:
        if verbose:
            print(f"  → 全部 {len(results)} 只命中缓存（不超过 {MAX_AGE_H} 小时）")
        return results

    if verbose:
        print(f"  → 需要请求 {len(need_fetch)} 只股票（TuShare 请求中，单只超时 {TIMEOUT}s）...")
        print("  （TuShare 有请求频率限制，请耐心等待）")

    # 第二遍：请求需要更新的
    for i, code in enumerate(need_fetch, 1):
        if verbose and i % 5 == 0:
            print(f"  进度: {i}/{len(need_fetch)} ...")
        data = fetch_one_with_timeout(code, token, timeout=TIMEOUT)
        if data:
            cache[code] = data
            results[code] = data
        else:
            if verbose:
                print(f"  [WARN] {code} 请求失败或超时（已跳过）")
        time.sleep(0.3)  # 节流，TuShare 有频率限制

    save_cache(cache)
    if verbose:
        print(f"  → 完成，成功 {len(results)}/{len(codes)} 只")
    return results


if __name__ == "__main__":
    # 简单测试（需要 ~/.tushare/token 存在，或手动传 token）
    print("测试 tushare_helper...")
    from tushare_helper import get_stock_ma_batch
    results = get_stock_ma_batch(["600519", "000066", "603538"], refresh_all=True, verbose=True)
    print("结果：")
    for code, data in results.items():
        print(f"  {code}: close={data['close']:.2f} ma10={data['ma10']:.2f} ma20={data['ma20']:.2f} bull={data['ma_bullish']} cap={data.get('market_cap', '?')}亿")

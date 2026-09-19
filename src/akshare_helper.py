#!/usr/bin/env python3
"""
akshare_helper.py
带超时保护 + 本地缓存的 akshare 封装。

特性：
  - 单只股票请求超时 5 秒，不会卡死整个流程
  - 结果缓存到 ~/.cache/stockyidong/akshare_cache.json
  - 缓存默认 6 小时有效，超过才重新请求
  - 第一次跑会慢（200 只 × 5s 理论上限 = 约 17 分钟，实际并行可优化）
    但本实现是顺序请求（避免被 akshare 限流），超时自动跳过

用法（被 daily_report 调用）：
  from akshare_helper import get_stock_ma_batch
  results = get_stock_ma_batch(["600519", "000066"], refresh_all=False)
"""

import json
import multiprocessing
import os
import re
import time

# ========== 配置 ==========
CACHE_DIR  = os.path.expanduser("~/.cache/stockyidong")
CACHE_FILE = os.path.join(CACHE_DIR, "akshare_cache.json")
TIMEOUT     = 8        # 单只股票请求超时（秒）
MAX_AGE_H   = 6        # 缓存有效期（小时）
# =============================


def _fetch_one(code, result_queue):
    """
    子进程函数：请求单只股票的均线和市值。
    结果放入 result_queue。
    """
    try:
        import akshare as ak

        # 1. 获取日线，纯 Python 计算均线
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df is None or df.empty:
            result_queue.put({"code": code, "error": "empty df"})
            return

        # 找收盘列
        close_col = None
        for c in df.columns:
            if "收盘" in str(c) or "close" in str(c).lower():
                close_col = c
                break
        if not close_col:
            result_queue.put({"code": code, "error": "no close col"})
            return

        closes = []
        for v in df[close_col].tail(120).tolist():
            try:
                closes.append(float(v))
            except (TypeError, ValueError):
                pass
        if len(closes) < 60:
            result_queue.put({"code": code, "error": "not enough data"})
            return

        last_close = closes[-1]
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60

        near_ma10 = abs(last_close - ma10) / ma10 < 0.03
        near_ma20 = abs(last_close - ma20) / ma20 < 0.03
        ma_bullish = (ma10 > ma20 > ma60)

        # 2. 获取市值（这个比较慢，可选）
        market_cap = None
        try:
            spot = ak.stock_individual_info_em(symbol=code)
            if spot is not None and not spot.empty:
                for _, row in spot.iterrows():
                    if "总市值" in str(row.iloc[0]):
                        val = str(row.iloc[1])
                        mv = re.search(r"([\d\.]+)", val)
                        if mv:
                            market_cap = float(mv.group(1))
                        break
        except Exception:
            pass  # 市值获取失败不阻断

        result_queue.put({
            "code": code,
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
        result_queue.put({"code": code, "error": str(e)})


def fetch_one_with_timeout(code, timeout=TIMEOUT):
    """
    带超时的单只股票请求。
    返回 dict 或 None（超时/失败）。
    """
    result_queue = multiprocessing.Queue()
    p = multiprocessing.Process(target=_fetch_one, args=(code, result_queue))
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
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def get_stock_ma_batch(codes, refresh_all=False, verbose=True):
    """
    批量获取股票均线/市值数据，带缓存。

    参数：
      codes:       股票代码列表
      refresh_all: True=强制刷新所有；False=只刷新过期缓存
      verbose:     打印进度

    返回：
      {code: {close, ma10, ma20, ma60, near_ma10, near_ma20, ma_bullish, market_cap}, ...}
    """
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
        ts = entry.get("ts", 0)
        if now - ts > max_age:
            need_fetch.append(code)
        else:
            results[code] = entry
            if verbose:
                print(f"  [缓存] {code}: close={entry.get('close', 0):.2f} ...")

    if not need_fetch:
        if verbose:
            print(f"  → 全部 {len(results)} 只命中缓存（不超过 {MAX_AGE_H} 小时）")
        return results

    if verbose:
        print(f"  → 需要请求 {len(need_fetch)} 只股票（akshare 请求中，单只超时 {TIMEOUT}s）...")

    # 第二遍：请求需要更新的
    for i, code in enumerate(need_fetch, 1):
        if verbose and i % 10 == 0:
            print(f"  进度: {i}/{len(need_fetch)} ...")
        data = fetch_one_with_timeout(code, timeout=TIMEOUT)
        if data:
            cache[code] = data
            results[code] = data
        else:
            if verbose:
                print(f"  [WARN] {code} 请求失败或超时（已跳过）")
        time.sleep(0.2)  # 节流，避免被限流

    save_cache(cache)
    if verbose:
        print(f"  → 完成，成功 {len(results)}/{len(codes)} 只")
    return results


if __name__ == "__main__":
    # 简单测试
    print("测试 akshare_helper...")
    results = get_stock_ma_batch(["600519", "000066", "603538"], refresh_all=True, verbose=True)
    print("结果：")
    for code, data in results.items():
        print(f"  {code}: {data}")

#!/usr/bin/env python3
"""拉取全市场实时行情(带重试)，落盘 /tmp/spot_20260828.csv。"""
import sys
import time

import akshare as ak

OUT = "/tmp/spot_20260828.csv"

def fetch_spot():
    last = None
    for i in range(6):
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last = e
            print(f"[retry {i+1}] spot failed: {e}", file=sys.stderr)
            time.sleep(3 + i*2)
    if last:
        raise last
    raise RuntimeError("spot empty")

print("fetching spot...", flush=True)
t0 = time.time()
df = fetch_spot()
print(f"got {len(df)} rows in {time.time()-t0:.1f}s", flush=True)
df.to_csv(OUT, encoding="utf-8-sig", index=False)
print("saved", OUT, flush=True)
print("cols:", list(df.columns), flush=True)

#!/usr/bin/env python3
import json
import sys
import time

import akshare as ak
import pandas as pd


def retry(func, n=4):
    last=None
    for i in range(n):
        try:
            r=func()
            if r is not None and not (isinstance(r,pd.DataFrame) and r.empty):
                return r
        except Exception as e:
            last=e; time.sleep(2+i*2)
    if last: print("WARN", last, file=sys.stderr)
    return None

pools={}
for name, fn in [('zt','stock_zt_pool_em'),('strong','stock_zt_pool_strong_em'),('zbgc','stock_zt_pool_zbgc_em')]:
    try:
        df = retry(lambda: getattr(ak,fn)(date='20260828'))
        if df is not None:
            df.to_csv(f"/tmp/pool_{name}_20260828.csv", index=False, encoding="utf-8-sig")
            pools[name]=len(df)
            print(f"pool {name}: {len(df)} rows", flush=True)
        else:
            print(f"pool {name}: NONE", flush=True)
    except Exception as e:
        print(f"pool {name} FAIL {e}", flush=True)

print("POOLS_DONE", json.dumps(pools), flush=True)

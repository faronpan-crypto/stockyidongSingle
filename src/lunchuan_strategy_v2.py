#!/usr/bin/env python3
"""
轮船策略选股系统 v2
使用腾讯行情API获取实时数据

数据源切换: 东财API → 腾讯API
时间: 2026-04-28
"""

from datetime import datetime

import requests


def get_stocks_from_tencent():
    """从腾讯行情获取所有股票数据"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_stocks = []
    
    # 沪市主板 60xxxx
    for start in range(0, 6000, 100):
        codes = [f'sh60{i:04d}' for i in range(start, start+100)]
        try:
            r = requests.get(f"https://qt.gtimg.cn/q={','.join(codes)}", headers=headers, timeout=6)
            if r.status_code == 200:
                for line in r.text.strip().split('\n'):
                    if '="1~' in line:
                        parts = line.split('=')[1].strip('"').split('~')
                        if len(parts) > 38 and parts[3]:
                            try:
                                price = float(parts[3])
                                pct = float(parts[32]) if parts[32] else 0
                                turnover = float(parts[38]) if parts[38] else 0
                                if 0 < price < 500:
                                    all_stocks.append({
                                        'name': parts[1], 'code': parts[2],
                                        'price': price, 'pct': pct, 'turnover': turnover
                                    })
                            except:
                                pass
        except:
            pass
    
    # 深市主板 00xxxx
    for start in range(0, 2000, 100):
        codes = [f'sz00{i:04d}' for i in range(start, start+100)]
        try:
            r = requests.get(f"https://qt.gtimg.cn/q={','.join(codes)}", headers=headers, timeout=6)
            if r.status_code == 200:
                for line in r.text.strip().split('\n'):
                    if '="1~' in line:
                        parts = line.split('=')[1].strip('"').split('~')
                        if len(parts) > 38 and parts[3]:
                            try:
                                price = float(parts[3])
                                pct = float(parts[32]) if parts[32] else 0
                                turnover = float(parts[38]) if parts[38] else 0
                                if 0 < price < 500:
                                    all_stocks.append({
                                        'name': parts[1], 'code': parts[2],
                                        'price': price, 'pct': pct, 'turnover': turnover
                                    })
                            except:
                                pass
        except:
            pass
    
    # 科创板 688xxx
    for start in range(0, 1000, 100):
        codes = [f'sh688{i:03d}' for i in range(start, start+100)]
        try:
            r = requests.get(f"https://qt.gtimg.cn/q={','.join(codes)}", headers=headers, timeout=6)
            if r.status_code == 200:
                for line in r.text.strip().split('\n'):
                    if '="1~' in line:
                        parts = line.split('=')[1].strip('"').split('~')
                        if len(parts) > 38 and parts[3]:
                            try:
                                price = float(parts[3])
                                pct = float(parts[32]) if parts[32] else 0
                                turnover = float(parts[38]) if parts[38] else 0
                                if 0 < price < 500:
                                    all_stocks.append({
                                        'name': parts[1], 'code': parts[2],
                                        'price': price, 'pct': pct, 'turnover': turnover
                                    })
                            except:
                                pass
        except:
            pass
    
    return all_stocks

def screen_stocks(stocks):
    """筛选强势股"""
    zt = [s for s in stocks if s['pct'] > 9.5]
    qs = [s for s in stocks if 5 < s['pct'] <= 9.5]
    low = [s for s in stocks if 3 < s['pct'] <= 6 and 3 < s['turnover'] < 10]
    return zt, qs, low

def main():
    print("=" * 50)
    print("  轮船策略选股系统 v2")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    stocks = get_stocks_from_tencent()
    print(f"获取 {len(stocks)} 只股票")
    
    if not stocks:
        print("获取数据失败!")
        return
    
    stocks.sort(key=lambda x: x['pct'], reverse=True)
    zt, qs, low = screen_stocks(stocks)
    
    print(f"\n涨停股: {len(zt)} 只")
    for s in zt[:15]:
        print(f"   {s['name']:10s} {s['code']} {s['price']:>8.2f} {s['pct']:>+6.2f}%")
    
    print(f"\n强势股(5-9.5%): {len(qs)} 只")
    for s in qs[:12]:
        print(f"   {s['name']:10s} {s['code']} {s['price']:>8.2f} {s['pct']:>+6.2f}%")
    
    print(f"\n低位启动(3-6%,换手3-10%): {len(low)} 只")
    for s in low[:10]:
        print(f"   {s['name']:10s} {s['code']} {s['price']:>8.2f} {s['pct']:>+5.2f}% 换手{s['turnover']:.1f}%")

if __name__ == "__main__":
    main()
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

datas = []
binaries = []
hiddenimports = ['matplotlib', 'matplotlib.backends.backend_tkagg', 'matplotlib.backends.backend_agg', 'openpyxl', 'bs4', 'lxml', 'jieba', 'scipy', 'tqdm']

# 🆕 爬虫脚本 — 打进去让 run_crawler_script 能找到
_crawler_scripts = [
    "taoguba_100_posts_crawler.py",
    "jiuyan_gongshe_crawler.py",
    "eastmoney_hot_crawler.py",
    "xueqiu_daily_crawler.py",
]
for _s in _crawler_scripts:
    _p = os.path.join("src", _s)
    if os.path.exists(_p):
        datas.append((_p, "."))
        print(f"spec: include crawler → {_p}")
    else:
        print(f"spec: ⚠️ crawler 不存在 → {_p}")
tmp_ret = collect_all('akshare')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tushare')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pywencai')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['src/stockyidong mac003.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stockyidong',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stockyidong',
)
app = BUNDLE(
    coll,
    name='stockyidong.app',
    icon=None,
    bundle_identifier='com.faronpan.stockyidong.standalone',
)

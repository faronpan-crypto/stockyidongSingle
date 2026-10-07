# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('venv/lib/python3.11/site-packages/akshare/file_fold', 'akshare/file_fold')]
hiddenimports = ['PIL.Image', 'jieba.analyse']
datas += collect_data_files('jieba')
datas += collect_data_files('wordcloud')
datas += collect_data_files('matplotlib')
datas += collect_data_files('sklearn')
hiddenimports += collect_submodules('wordcloud')
hiddenimports += collect_submodules('jieba')


a = Analysis(
    ['src/stockyidong mac003.py'],
    pathex=[],
    binaries=[],
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
    name='StockAnalyzer_mac003',
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
    icon=['src/assets/StockAnalyzer.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='StockAnalyzer_mac003',
)
app = BUNDLE(
    coll,
    name='StockAnalyzer_mac003.app',
    icon='src/assets/StockAnalyzer.icns',
    bundle_identifier=None,
)

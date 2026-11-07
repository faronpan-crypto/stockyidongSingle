# -*- mode: python ; coding: utf-8 -*-
"""🦊 家教辅导小助手 — 独立 PyInstaller spec"""

import sys, os

block_cipher = None

# datas: 把整个 src/ui 包带进去 (运行时 sys.path 能找到)
src_dir = os.path.join(os.getcwd(), "src")
datas = [
    (src_dir, "src"),   # 整包 src/ → 运行时 sys.path 加 src 后能 import ui.*
]

# hiddenimports: 显式列出来 (PyInstaller 看不到运行时动态 import)
hiddenimports = [
    "ui.tutor_helper",
    "ui.exam_db",
    "ui.exam_word",
    "ui.exam_ai",
    "ui.knowledge_base",
    "docx", "docx.oxml", "docx.oxml.ns", "docx.shared",
    "docx.enum.text", "docx.enum.table", "docx.oxml.parse_xml",
    "PIL", "PIL.Image", "PIL.ImageTk",
]

a = Analysis(
    ['tutor_launch.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'akshare', 'tushare', 'pandas', 'requests',
        'numpy', 'scipy', 'sklearn',
        'matplotlib', 'seaborn', 'plotly',
        'tesseract', 'pytesseract',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'wx', 'PyWebView',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='家教辅导小助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='家教辅导小助手',
)

app = BUNDLE(
    coll,
    name='家教辅导小助手.app',
    icon=None,
    bundle_identifier='com.tutor.helper',
    info_plist={
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.education',
        'CFBundleShortVersionString': '1.0',
    },
)

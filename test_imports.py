import os
import sys


def _early_sqlite_temp_dir():
    data_root = (os.environ.get('STOCK_ANALYZER_DATA_DIR') or r'D:\StockAnalyzer').strip() or r'D:\StockAnalyzer'
    tmp = os.path.join(data_root, 'temp')
    try:
        os.makedirs(tmp, exist_ok=True)
    except Exception:
        return
    if (os.environ.get('SQLITE_TMPDIR') or '').strip():
        return
    try:
        os.environ['SQLITE_TMPDIR'] = os.path.normpath(tmp)
        if sys.platform == 'win32':
            os.environ['TEMP'] = os.environ['SQLITE_TMPDIR']
            os.environ['TMP'] = os.environ['SQLITE_TMPDIR']
    except Exception:
        pass

_early_sqlite_temp_dir()

print('Step 1: Basic imports')

print('Step 2: After basic imports')

# Try docx
print('Step 3: After docx import')

print('All imports successful!')

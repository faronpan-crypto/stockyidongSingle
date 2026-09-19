import os
import sys

# Simulate __file__ being set like in the actual script
__file__ = "/Users/faronpan/Agent/stockyidong_project/src/stockyidong mac.py"

print("Testing with __file__ set to:", __file__)


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

print("About to import docx...")
try:
    print("docx imported successfully!")
except Exception as e:
    print(f"docx import failed: {e}")
    import traceback
    traceback.print_exc()

print("Script completed!")

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

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
import contextlib
import io


# Error suppression tools
@contextlib.contextmanager
def suppress_stderr():
    old_stderr = sys.stderr
    try:
        sys.stderr = io.StringIO()
        yield
    except Exception:
        pass
    finally:
        sys.stderr = old_stderr

@contextlib.contextmanager
def suppress_all_output():
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        yield
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

class SilentIO(io.StringIO):
    def write(self, *args, **kwargs):
        pass
    def flush(self, *args, **kwargs):
        pass
    def getvalue(self):
        return ''

@contextlib.contextmanager
def suppress_tkinterweb_errors():
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = SilentIO()
        sys.stderr = SilentIO()
        yield
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def suppress_all_errors(func):
    def wrapper(*args, **kwargs):
        with suppress_stderr():
            try:
                return func(*args, **kwargs)
            except Exception:
                return None
    return wrapper

# Tushare import
try:
    import tushare as ts
    TS_AVAILABLE = True
except ImportError:
    ts = None
    TS_AVAILABLE = False

# Path configuration
D_DATA_DIR = (os.environ.get("STOCK_ANALYZER_DATA_DIR") or r"D:\StockAnalyzer").strip() or r"D:\StockAnalyzer"
D_DB_DIR = os.path.join(D_DATA_DIR, "Database")
D_OUTPUT_DIR = os.path.join(D_DATA_DIR, "Output")
D_EXPORT_DIR = os.path.join(D_DATA_DIR, "Export")
D_IMAGES_DIR = os.path.join(D_DATA_DIR, "ConsultationImages")
D_SQLITE_TMP = os.path.join(D_DATA_DIR, "temp")

for dir_path in [D_DATA_DIR, D_DB_DIR, D_OUTPUT_DIR, D_EXPORT_DIR, D_IMAGES_DIR, D_SQLITE_TMP]:
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception as e:
        print(f"创建目录失败 {dir_path}: {e}")

_APP_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_CONFIG_DIR = os.path.join(_APP_SRC_DIR, "config")
try:
    os.makedirs(_APP_CONFIG_DIR, exist_ok=True)
except OSError:
    pass

# Now try importing docx
print("About to import docx...")
try:
    from docx import Document
    DOCX_AVAILABLE = True
    print("docx imported successfully")
except ImportError:
    print("❌ 警告: python-docx未安装，Word文档读取功能不可用")
    DOCX_AVAILABLE = False

print("Script completed successfully!")

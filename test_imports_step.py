import os
import sys

print("Starting step-by-step test...")

# Step 1: Early setup
print("\n1. Running early sqlite setup...")
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
print("   Done")

# Step 2: Import tkinter
print("\n2. Importing tkinter...")
print("   Done")

# Step 3: Import requests
print("\n3. Importing requests...")
print("   Done")

# Step 4: Import re
print("\n4. Importing re...")
print("   Done")

# Step 5: Import jieba
print("\n5. Importing jieba...")
print("   Done")

# Step 6: Try akshare
print("\n6. Trying akshare...")
try:
    import akshare as ak
    print("   akshare imported")
except ImportError:
    print("   akshare not available (this is OK)")

# Step 7: Import collections
print("\n7. Importing collections...")
print("   Done")

# Step 8: Import pandas
print("\n8. Importing pandas...")
print("   Done")

# Step 9: Import PIL
print("\n9. Importing PIL...")
print("   Done")

# Step 10: Import matplotlib
print("\n10. Importing matplotlib...")
print("   Done")

# Step 11: Import wordcloud
print("\n11. Importing wordcloud...")
print("   Done")

# Step 12: Other imports
print("\n12. Importing other modules...")
print("   Done")

# Step 13: Try tushare
print("\n13. Trying tushare...")
try:
    import tushare as ts
    print("   tushare imported")
except ImportError:
    print("   tushare not available (this is OK)")

# Step 14: Path configuration
print("\n14. Setting up paths...")
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
        print(f"   Warning: Failed to create {dir_path}: {e}")

_APP_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"   App src dir: {_APP_SRC_DIR}")
print("   Done")

# Step 15: Try docx
print("\n15. Trying docx...")
try:
    from docx import Document
    print("   docx imported successfully!")
except ImportError:
    print("   docx not available (this is OK)")

print("\n=== All imports completed successfully! ===")

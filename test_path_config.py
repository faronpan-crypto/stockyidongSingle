import os

print("Starting path config test...")

# Test the exact code that triggers the error
print("About to configure DB_PATH")
_STOCKYIDONG_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
print(f"_STOCKYIDONG_PROJECT_ROOT = {_STOCKYIDONG_PROJECT_ROOT}")

_PROJECT_LOCAL_DB = os.path.join(_STOCKYIDONG_PROJECT_ROOT, "data", "stock_analysis.db")
print(f"_PROJECT_LOCAL_DB = {_PROJECT_LOCAL_DB}")

_db_override = (
    (os.environ.get("STOCK_ANALYSIS_DB") or os.environ.get("STOCK_ANALYSIS_DB_PATH") or "").strip().strip('"')
)
print(f"_db_override = {_db_override}")

D_DATA_DIR = (os.environ.get("STOCK_ANALYZER_DATA_DIR") or r"D:\StockAnalyzer").strip() or r"D:\StockAnalyzer"
D_DB_DIR = os.path.join(D_DATA_DIR, "Database")

if _db_override:
    DB_PATH = os.path.normpath(os.path.expanduser(_db_override))
elif os.path.isfile(_PROJECT_LOCAL_DB):
    DB_PATH = os.path.normpath(_PROJECT_LOCAL_DB)
else:
    DB_PATH = os.path.join(D_DB_DIR, "stock_analysis.db")

print(f"DB_PATH = {DB_PATH}")
print("Path config completed successfully!")

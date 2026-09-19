
print("Starting import test...")

# Test imports in groups
groups = [
    ["os", "sys", "re", "json", "copy", "io", "time", "shutil", "random", "threading", "contextlib", "base64", "webbrowser", "warnings", "importlib.util"],
    ["tkinter", "tkinter.ttk", "tkinter.scrolledtext", "tkinter.filedialog", "tkinter.messagebox", "tkinter.simpledialog"],
    ["requests", "bs4", "urllib.parse"],
    ["jieba"],
    ["collections.Counter", "datetime"],
    ["pandas"],
    ["PIL.Image", "PIL.ImageTk", "PIL.ImageDraw", "PIL.ImageFont"],
    ["matplotlib", "matplotlib.pyplot"],
    ["wordcloud.WordCloud"],
    ["numpy"],
    ["sqlite3"],
]

for group in groups:
    print(f"\nTesting group: {group}")
    for module in group:
        try:
            if '.' in module:
                parts = module.split('.')
                exec(f"from {'.'.join(parts[:-1])} import {parts[-1]}")
            else:
                exec(f"import {module}")
            print(f"  ✓ {module}")
        except Exception as e:
            print(f"  ✗ {module}: {e}")
            import traceback
            traceback.print_exc()
            
print("\nAll imports completed!")

#!/usr/bin/env python3
import os
import sys

# 设置环境变量
if sys.platform == "darwin":
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    # 设置TCL/TK路径
    import tkinter
    print(f"TCL_LIBRARY: {os.environ.get('TCL_LIBRARY', 'Not set')}")
    print(f"TK_LIBRARY: {os.environ.get('TK_LIBRARY', 'Not set')}")
    print(f"DYLD_FALLBACK_FRAMEWORK_PATH: {os.environ.get('DYLD_FALLBACK_FRAMEWORK_PATH', 'Not set')}")
    print(f"DYLD_FALLBACK_LIBRARY_PATH: {os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', 'Not set')}")

print("\n=== Step 1: Creating Tkinter root ===")
root = tkinter.Tk()
root.title("Test Window")
root.geometry("400x300")

print(f"Root window created: {root}")
print(f"Root exists: {root.winfo_exists()}")
print(f"Root visible: {root.winfo_viewable()}")
print(f"Root mapped: {root.winfo_ismapped()}")

# 添加一个标签
label = tkinter.Label(root, text="Test Label")
label.pack(pady=20)
print(f"Label created: {label}")

# 显示窗口
print("\n=== Step 2: Showing window ===")
root.deiconify()
root.lift()
root.focus_force()

print(f"After deiconify - visible: {root.winfo_viewable()}")
print(f"After deiconify - mapped: {root.winfo_ismapped()}")

# 等待一下
print("\n=== Step 3: Waiting 2 seconds ===")
root.after(2000, root.quit)
root.mainloop()

print("\n=== Done ===")

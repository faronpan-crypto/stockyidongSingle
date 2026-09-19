import os
import sys
import tkinter as tk

print("Python version:", sys.version)
print("Platform:", sys.platform)
print("DISPLAY:", os.environ.get('DISPLAY', 'Not set'))

try:
    root = tk.Tk()
    print("Created Tk root successfully")
    
    root.title("Test Window")
    print("Set title successfully")
    
    root.geometry("400x300")
    print("Set geometry successfully")
    
    label = tk.Label(root, text="Hello from Tkinter!")
    label.pack(pady=20)
    print("Created label successfully")
    
    button = tk.Button(root, text="Click Me", command=lambda: print("Button clicked"))
    button.pack(pady=10)
    print("Created button successfully")
    
    root.update()
    print("Update successful")
    
    root.mainloop()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
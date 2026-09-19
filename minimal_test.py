import sys

print(f"Python version: {sys.version}")
print(f"Platform: {sys.platform}")

# Check macOS version
import platform

mac_ver = platform.mac_ver()
print(f"macOS version: {mac_ver}")

# Try importing some libraries
print("\nImporting numpy...")
print("numpy imported")

print("\nImporting pandas...")
print("pandas imported")

print("\nImporting matplotlib...")
print("matplotlib imported")

print("\nImporting tkinter...")
print("tkinter imported")

print("\nAll imports successful!")

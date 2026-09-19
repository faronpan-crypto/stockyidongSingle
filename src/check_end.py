file_path = "stockyidong.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"文件共有 {len(lines)} 行")
print("最后 20 行:")
for i, line in enumerate(lines[-20:], len(lines)-19):
    print(f"{i}: {line.rstrip()}")

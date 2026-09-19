import ast

file_path = "stockyidong mac.py"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    ast.parse(content)
    print("文件语法正确")
except SyntaxError as e:
    print(f"语法错误在第 {e.lineno} 行，第 {e.offset} 列: {e.msg}")
    # 打印错误行及其前后几行
    lines = content.split('\n')
    start = max(0, e.lineno - 5)
    end = min(len(lines), e.lineno + 5)
    for i in range(start, end):
        line_num = i + 1
        marker = "->" if line_num == e.lineno else "  "
        print(f"{marker} {line_num}: {lines[i]}")

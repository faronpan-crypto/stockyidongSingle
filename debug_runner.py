import sys
import traceback

print('Step 1: Starting script', file=sys.stderr)

# Read and execute the original script line by line
with open('/Users/faronpan/Agent/stockyidong_project/src/stockyidong mac.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Execute lines in batches to find where it fails
batch_size = 100
for i in range(0, len(lines), batch_size):
    batch = lines[i:i+batch_size]
    try:
        code = ''.join(batch)
        exec(code, globals())
        print(f'Step {i//batch_size + 1}: Executed lines {i+1}-{min(i+batch_size, len(lines))}', file=sys.stderr)
    except Exception as e:
        print(f'Error at batch {i//batch_size + 1}: {e}', file=sys.stderr)
        traceback.print_exc()
        break

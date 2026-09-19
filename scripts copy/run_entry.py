"""Auto-generated launcher; keeps imports working across *_project folders."""
import os
import runpy
import sys
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / "src" / "stockyidong.py"
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ENTRY.parent)
sys.path.insert(0, str(ROOT))
for proj in sorted(ROOT.glob('*_project')):
    sub = proj / 'src'
    if sub.is_dir():
        sys.path.insert(0, str(sub))
runpy.run_path(str(ENTRY), run_name='__main__')

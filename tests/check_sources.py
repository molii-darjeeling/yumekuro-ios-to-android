"""Parse public sources and resolve local Markdown links without touching devices."""
import ast
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for path in sorted(root.rglob('*.py')):
    if '.git' not in path.parts:
        ast.parse(path.read_text(encoding='utf8'), filename=str(path))
for path in (root/'runtime').glob('*.js'):
    subprocess.run(['node','--check',str(path)], check=True)
for path in root.rglob('*.md'):
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf8')):
        if '://' in target or target.startswith('#'):
            continue
        if not (path.parent/target.split('#')[0]).exists():
            raise ValueError('Broken local Markdown link: '+str(path.relative_to(root))+' -> '+target)
print('Python syntax, runtime JS syntax, and local documentation links passed')

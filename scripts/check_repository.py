"""Validate maintained source and local documentation without importing the app."""
import ast
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
errors = []
for folder in ('src', 'scripts', 'tests', 'alembic'):
    for path in (ROOT / folder).rglob('*.py'):
        try:
            ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError as exc:
            errors.append(f'{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}')
for path in [ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', *(ROOT / 'docs').glob('*.md'), *(ROOT / 'examples').rglob('*.md')]:
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if target.startswith(('#', 'http:', 'https:', 'mailto:')):
            continue
        target = unquote(target.split('#', 1)[0])
        if not (path.parent / target).exists():
            errors.append(f'{path.relative_to(ROOT)}: missing link {target}')
if errors:
    raise SystemExit('\n'.join(errors))
print('Source syntax and local documentation links passed.')

"""Run the packaged CLI outside the checkout and reject network access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # Select the version just built, even when older build artifacts remain locally.
    wheel = max((ROOT / 'dist').glob('tender_vendor_discovery-*.whl'), key=lambda path: path.stat().st_mtime)
    script = '''import sys, socket
from pathlib import Path
sys.path.insert(0, sys.argv[1])
def blocked(*args, **kwargs):
    raise AssertionError("Network disabled in package smoke check")
socket.create_connection = blocked
socket.socket.connect = blocked
from vendor_ai_agent import cli
import vendor_ai_agent
assert Path(vendor_ai_agent.__file__).resolve().is_relative_to(Path(sys.argv[1]))
cli.main(["demo", "--output-dir", "review"])
'''
    with tempfile.TemporaryDirectory(prefix='tender-wheel-check-') as directory:
        root = Path(directory).resolve()
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(root / 'package')
        subprocess.run(
            [sys.executable, '-I', '-c', script, str(root / 'package')], cwd=root,
            env={**os.environ, 'PYTHON_DOTENV_DISABLED': '1'}, check=True,
        )
        for name in ('review.json', 'vendor_matches.json'):
            actual = json.loads((root / 'review' / name).read_text())
            expected = json.loads((ROOT / 'examples' / 'demo' / name).read_text())
            assert actual == expected, f'Packaged output differs from committed {name}'
        for name in ('review.html', 'vendor_matches.csv', 'vendor_matches.xlsx', 'tender.md', 'vendors.json'):
            assert (root / 'review' / name).is_file(), f'Missing artifact: {name}'
    print('Packaged CLI, bundled inputs/template and committed examples passed with network disabled.')


if __name__ == '__main__':
    main()

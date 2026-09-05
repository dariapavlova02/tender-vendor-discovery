"""Check the packaged CLI, parser and exporters outside the checkout, offline."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wheel = max((ROOT / 'dist').glob('tender_vendor_discovery-*.whl'), key=lambda path: path.stat().st_mtime)
    script = '''import sys, socket, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
def blocked(*args, **kwargs):
    raise AssertionError("Network disabled in package smoke check")
socket.create_connection = blocked
socket.socket.connect = blocked
from vendor_ai_agent import cli
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.output_generator import OutputGenerator
import vendor_ai_agent
assert Path(vendor_ai_agent.__file__).resolve().is_relative_to(Path(sys.argv[1]))
args = cli.build_parser().parse_args(["run", "tender.txt", "--no-auto-ingestion"])
assert args.command == "run" and args.no_auto_ingestion
source = Path("tender.txt")
source.write_text("Document parser smoke check.")
sections = DocumentParser().parse([source])
assert len(sections) == 1 and sections[0].content == source.read_text()
output = OutputGenerator()
output.to_json([], Path("empty.json"))
output.to_csv([], Path("empty.csv"))
output.to_excel([], Path("empty.xlsx"))
assert json.loads(Path("empty.json").read_text()) == []
assert Path("empty.csv").is_file() and Path("empty.xlsx").is_file()
'''
    with tempfile.TemporaryDirectory(prefix='tender-wheel-check-') as directory:
        root = Path(directory).resolve()
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(root / 'package')
        subprocess.run(
            [sys.executable, '-I', '-c', script, str(root / 'package')], cwd=root,
            env={**os.environ, 'PYTHON_DOTENV_DISABLED': '1'}, check=True,
        )
    print('Packaged CLI, document parser and empty-result exports passed with network disabled.')


if __name__ == '__main__':
    main()

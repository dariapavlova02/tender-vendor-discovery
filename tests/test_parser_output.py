import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")
parser = DocumentParser()
result = parser.parse([pdf_path])

print(f"Type of result: {type(result)}")
print(f"Type of result[0]: {type(result[0]) if result else 'N/A'}")
if result:
    print(f"Fields: {dir(result[0])}")

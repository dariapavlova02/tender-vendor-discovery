#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

parser = DocumentParser()
sections = parser.parse([pdf_path])

print("Searching for '8(A)' or 'COMPETITIVE' in first 50 sections...\n")
for idx, section in enumerate(sections[:50]):
    content_upper = section.content.upper()
    if "8(A)" in section.content or "COMPETITIVE" in content_upper or "SIZE STANDARD" in content_upper:
        print(f"Section {idx}: {section.title[:60]}")
        print(f"  Type: {section.section_type}")
        print(f"  Content: '{section.content}'")
        print()

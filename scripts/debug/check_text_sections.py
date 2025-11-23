#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

parser = DocumentParser()
sections = parser.parse([pdf_path])

# Get non-table sections
text_sections = [s for s in sections if s.section_type != 'table']
print(f"Total text sections: {len(text_sections)}")
print("\nFirst 5 text sections:\n")

for idx, section in enumerate(text_sections[:5]):
    print(f"{idx}. {section.title[:60]}")
    print(f"   Length: {len(section.content)}")
    print(f"   Preview: {section.content[:200].replace(chr(10), ' ')}")
    print()

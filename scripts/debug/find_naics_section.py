#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

parser = DocumentParser()
sections = parser.parse([pdf_path])

print("Searching for section containing '315210'...\n")
for idx, section in enumerate(sections):
    if "315210" in section.content:
        print(f"FOUND in section {idx}:")
        print(f"  Title: {section.title}")
        print(f"  Type: {section.section_type}")
        print(f"  Content length: {len(section.content)}")
        print(f"  Content:\n{section.content}")
        break
else:
    print("Not found in any section!")
    print("\nSearching for 'COMPETITIVE'...")
    for idx, section in enumerate(sections[:20]):
        if "COMPETITIVE" in section.content.upper():
            print(f"\nSection {idx}: {section.title}")
            print(f"  {section.content[:500]}")

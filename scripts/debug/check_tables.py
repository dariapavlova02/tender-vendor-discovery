#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

parser = DocumentParser()
sections = parser.parse([pdf_path])

print(f"Total sections: {len(sections)}")
tables = [s for s in sections if s.section_type == 'table']
print(f"Total tables: {len(tables)}\n")

for idx, table in enumerate(tables[:10]):
    print(f"Table {idx}: {table.title}")
    if "315210" in table.content or "NAICS" in table.content.upper() or "COMPETITIVE" in table.content.upper():
        print(f"  *** CONTAINS TARGET TEXT ***")
        print(f"  Content:\n{table.content}\n")
    else:
        print(f"  Preview: {table.content[:150]}...\n")

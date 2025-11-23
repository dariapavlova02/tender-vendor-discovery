#!/usr/bin/env python
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.modules.document_parser import DocumentParser

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

parser = DocumentParser()
sections = parser.parse([pdf_path])

print("Searching all sections for NAICS mentions:\n")
naics_pattern = re.compile(r"NAICS", re.IGNORECASE)
six_digit = re.compile(r"\b(\d{6})\b")

found_count = 0
for idx, section in enumerate(sections):
    if naics_pattern.search(section.content):
        found_count += 1
        print(f"Section {idx}: {section.title[:50]}")
        for line in section.content.split("\n"):
            if "NAICS" in line.upper():
                print(f"  → {line.strip()}")
                # Check for 6-digit codes nearby
                codes = six_digit.findall(line)
                if codes:
                    print(f"     Found 6-digit codes: {codes}")

print(f"\nTotal sections with NAICS: {found_count}/{len(sections)}")

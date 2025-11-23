#!/usr/bin/env python
import sys
from pathlib import Path
import re
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pdfplumber

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

print("Extracting ALL text from PDF and searching for NAICS...\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages[:20], 1):  # Check first 20 pages
        text = page.extract_text() or ""
        if "NAICS" in text.upper() or "315" in text:
            print(f"Page {page_num}:")
            for line in text.split("\n"):
                if "NAICS" in line.upper() or (re.search(r"\b31[0-9]{4}\b", line)):
                    print(f"  {line.strip()}")
            print()

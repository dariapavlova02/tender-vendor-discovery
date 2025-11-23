#!/usr/bin/env python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pdfplumber

pdf_path = Path("data/DHS-wide+Uniforms+III+Contract/RFP 70B01C26R00000004 Uniforms III.pdf")

with pdfplumber.open(pdf_path) as pdf:
    page1 = pdf.pages[0]
    text = page1.extract_text()
    
    print("="*60)
    print("FULL PAGE 1 TEXT")
    print("="*60)
    print(text)
    print("\n" + "="*60)
    
    # Find line with NAICS
    for line in text.split("\n"):
        if "315210" in line or "NAICS" in line.upper():
            print(f"\n✓ FOUND NAICS LINE:")
            print(f"  '{line}'")

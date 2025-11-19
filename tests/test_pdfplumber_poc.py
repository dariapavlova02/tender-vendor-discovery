#!/usr/bin/env python3
"""PoC: Test pdfplumber's ability to extract structured data from tender PDFs."""

import pdfplumber
from pathlib import Path
import json

def analyze_document(pdf_path: Path):
    """Analyze PDF structure: fonts, tables, text layout."""
    print(f"\n{'='*80}")
    print(f"ANALYZING: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"📄 Total pages: {len(pdf.pages)}\n")
        
        # Analyze first 3 pages
        for page_num in range(min(3, len(pdf.pages))):
            page = pdf.pages[page_num]
            print(f"\n--- PAGE {page_num + 1} ---\n")
            
            # 1. Extract text
            text = page.extract_text()
            if text:
                lines = text.split('\n')
                print(f"📝 Text lines: {len(lines)}")
                print(f"First 5 lines:")
                for i, line in enumerate(lines[:5], 1):
                    print(f"  {i}. {line[:100]}")
            
            # 2. Font analysis
            words = page.extract_words(extra_attrs=["fontname", "size"])
            if words:
                font_sizes = {}
                for word in words:
                    size = round(word.get('size', 0), 1)
                    font_sizes[size] = font_sizes.get(size, 0) + 1
                
                print(f"\n🔤 Font size distribution:")
                for size in sorted(font_sizes.keys(), reverse=True)[:5]:
                    print(f"  {size}pt: {font_sizes[size]} words")
                
                # Determine base text size (most common)
                base_size = max(font_sizes.items(), key=lambda x: x[1])[0]
                print(f"  → Base text size: {base_size}pt")
                
                # Find potential headers (larger than base)
                headers = [w for w in words if round(w.get('size', 0), 1) > base_size]
                if headers:
                    print(f"\n📋 Potential headers (size > {base_size}pt):")
                    seen = set()
                    for h in headers[:10]:
                        text = h['text']
                        if text not in seen and len(text) > 2:
                            print(f"  - '{text}' ({h.get('size')}pt)")
                            seen.add(text)
            
            # 3. Table detection
            tables = page.extract_tables()
            if tables:
                print(f"\n📊 Tables found: {len(tables)}")
                for idx, table in enumerate(tables, 1):
                    if table:
                        print(f"\n  Table {idx}: {len(table)} rows x {len(table[0]) if table else 0} cols")
                        print(f"  First row: {table[0][:3]}...")
                        
                        # Show as markdown
                        print(f"\n  Markdown preview:")
                        md = table_to_markdown(table[:3])  # First 3 rows
                        print("  " + md.replace('\n', '\n  '))
            else:
                print(f"\n📊 No tables detected")
            
            print("\n" + "-"*80)


def table_to_markdown(table):
    """Convert table to markdown format."""
    if not table or not table[0]:
        return ""
    
    # Clean cells
    cleaned = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append('')
            else:
                cleaned_row.append(str(cell).replace('\n', ' ').strip())
        cleaned.append(cleaned_row)
    
    # Build markdown
    md = "| " + " | ".join(cleaned[0]) + " |\n"
    md += "| " + " | ".join(['---'] * len(cleaned[0])) + " |\n"
    for row in cleaned[1:]:
        md += "| " + " | ".join(row) + " |\n"
    
    return md


def test_header_detection(pdf_path: Path):
    """Test header detection heuristics."""
    print(f"\n{'='*80}")
    print(f"HEADER DETECTION TEST: {pdf_path.name}")
    print(f"{'='*80}\n")
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
        
        if not text:
            print("❌ No text extracted")
            return
        
        lines = text.split('\n')
        
        # Keywords for headers
        keywords = ["SCOPE", "REQUIREMENT", "DELIVERABLE", "MANDATORY", 
                   "EVALUATION", "AMENDMENT", "ADDENDUM", "SECTION", "PART",
                   "ARTICLE", "CLAUSE", "SCHEDULE", "APPENDIX", "ANNEX"]
        
        print("🎯 Detected potential headers:\n")
        for i, line in enumerate(lines[:30], 1):
            line_clean = line.strip()
            if not line_clean or len(line_clean) < 3:
                continue
            
            is_header = False
            reasons = []
            
            # Check length (headers are usually short)
            if len(line_clean) < 100:
                # Check for keywords
                if any(kw in line_clean.upper() for kw in keywords):
                    is_header = True
                    reasons.append("keyword")
                
                # Check for numbering: "1.", "1.1", "Section 5"
                import re
                if re.match(r'^(SECTION|PART|ARTICLE)?\s*\d+(\.\d+)*', line_clean, re.IGNORECASE):
                    is_header = True
                    reasons.append("numbering")
                
                # Check if ALL CAPS (common for headers)
                if line_clean.isupper() and len(line_clean.split()) <= 8:
                    is_header = True
                    reasons.append("all_caps")
            
            if is_header:
                print(f"  {i:3d}. [{', '.join(reasons)}] {line_clean[:80]}")


if __name__ == "__main__":
    base_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda")
    
    # Test different document types
    test_files = [
        base_path / "Addendum #7/Amendment No.17 1 Preferred Sealed PR-8310-OPP-1TF_9mm Frangible_2025.pdf",
        base_path / "Addendum #7/Appendix A Table A.2.pdf",
        base_path / "Addendum #1- tender_20070 - Supply and Delivery of Ammunition.pdf",
    ]
    
    for pdf_path in test_files:
        if pdf_path.exists():
            analyze_document(pdf_path)
            test_header_detection(pdf_path)
        else:
            print(f"⚠️  File not found: {pdf_path}")
    
    print(f"\n{'='*80}")
    print("✅ PoC Complete")
    print(f"{'='*80}")

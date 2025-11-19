import sys
sys.path.insert(0, 'src')

from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier

pdf_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda/Addendum #7/Appendix A Table A.2.pdf")

parser = DocumentParser()
classifier = TableClassifier()

sections_list = parser.parse([pdf_path])
tables = [s for s in sections_list if s.section_type == "table"]

print("=" * 80)
print("MULTI-ROW HEADER ANALYSIS")
print("=" * 80)

if tables:
    table = tables[0]
    table_type = classifier.classify(table)
    print(f"\nTABLE 1 (Type: {table_type})")
    print(f"Title: {table.title}\n")
    
    lines = [l.strip() for l in table.content.split('\n') if '|' in l]
    print(f"Total lines: {len(lines)}\n")
    
    for i, line in enumerate(lines[:6]):
        print(f"Line {i}: {line}")
    
    print("\n" + "=" * 80)
    print("PARSED CELLS ANALYSIS")
    print("=" * 80)
    
    if len(lines) > 3:
        header1 = [h.strip() for h in lines[0].split('|')[1:-1]]
        separator = lines[1]
        header2 = [h.strip() for h in lines[2].split('|')[1:-1]]
        data_row1 = [c.strip() for c in lines[3].split('|')[1:-1]]
        
        print(f"\nHeader row 1 ({len(header1)} cells):")
        for i, h in enumerate(header1):
            print(f"  [{i}] '{h}'")
        
        print(f"\nHeader row 2 (subheader) ({len(header2)} cells):")
        for i, h in enumerate(header2):
            print(f"  [{i}] '{h}'")
            
        print(f"\nData row 1 ({len(data_row1)} cells):")
        for i, cell in enumerate(data_row1):
            print(f"  [{i}] '{cell}'")

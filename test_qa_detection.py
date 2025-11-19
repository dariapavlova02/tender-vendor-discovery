from pathlib import Path
from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.document_processing.table_classifier import TableClassifier

parser = DocumentParser()
classifier = TableClassifier()

addenda_dir = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda")

qa_tables_found = []

for pdf_file in addenda_dir.rglob("*.pdf"):
    sections = parser.parse([pdf_file])
    
    for section in sections:
        if section.section_type == "table":
            table_type = classifier.classify(section)
            
            if table_type == "qa":
                qa_tables_found.append({
                    "file": pdf_file.name,
                    "section": section.title,
                    "preview": section.content[:200]
                })

print(f"Found {len(qa_tables_found)} QA tables:\n")

for i, qa in enumerate(qa_tables_found, 1):
    print(f"{i}. {qa['file']}")
    print(f"   Section: {qa['section']}")
    print(f"   Preview: {qa['preview']}...")
    print()

if not qa_tables_found:
    print("No QA tables found. Let's check what types we have:")
    
    sample_file = next(addenda_dir.rglob("Addendum*.pdf"), None)
    if sample_file:
        sections = parser.parse([sample_file])
        print(f"\nSample from {sample_file.name}:")
        for section in sections:
            if section.section_type == "table":
                table_type = classifier.classify(section)
                print(f"  - {section.title}: {table_type}")
                print(f"    Headers: {section.content.split(chr(10))[0][:150]}")

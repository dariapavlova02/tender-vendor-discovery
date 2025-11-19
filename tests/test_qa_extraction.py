"""Test Q&A extraction from OPP-1984 addenda."""
from pathlib import Path
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.requirement_extractor import RequirementExtractor

def test_qa_extraction():
    base_path = Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/RFB Addenda")
    
    addenda_files = [
        base_path / "Addendum #7" / "Addendum #7- tender_20070 - Supply and Delivery of Ammunition.pdf",
        base_path / "Addendum #8" / "Addendum #8- tender_20070 - Supply and Delivery of Ammunition.pdf",
        base_path / "Addendum #9" / "Addendum #9- tender_20070 - Supply and Delivery of Ammunition.pdf",
    ]
    
    existing_files = [f for f in addenda_files if f.exists()]
    
    if not existing_files:
        print("No addenda files found. Skipping test.")
        return
    
    print(f"\nTesting Q&A extraction on {len(existing_files)} addenda files...")
    
    parser = DocumentParser()
    extractor = RequirementExtractor()
    
    for file_path in existing_files:
        print(f"\n{'='*80}")
        print(f"Processing: {file_path.name}")
        print(f"{'='*80}")
        
        sections = parser.parse([file_path])
        
        tables = [s for s in sections if s.section_type == "table"]
        print(f"\nFound {len(tables)} tables in document")
        
        profile = extractor.extract(sections)
        
        clarifications = profile.doc_extracted.structured.clarifications
        print(f"\nExtracted {len(clarifications)} Q&A pairs:")
        
        for i, clarification in enumerate(clarifications, 1):
            print(f"\n--- Q&A Pair {i} ---")
            if clarification.question_number:
                print(f"ID: {clarification.question_number}")
            print(f"Q: {clarification.question[:100]}{'...' if len(clarification.question) > 100 else ''}")
            print(f"A: {clarification.answer[:100]}{'...' if len(clarification.answer) > 100 else ''}")

if __name__ == "__main__":
    test_qa_extraction()

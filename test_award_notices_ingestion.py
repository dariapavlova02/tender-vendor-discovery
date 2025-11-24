import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.vendor_ai_agent.database.connection import get_session
from src.vendor_ai_agent.ingestion.canada_award_notices import load_award_notices

def main():
    print("Starting Award Notices ingestion test...")
    print("=" * 80)
    
    csv_path = "data/canada_sources/award_notices/award_notices.csv"
    
    try:
        with get_session() as session:
            stats = load_award_notices(session, csv_path)
            
            print("\n" + "=" * 80)
            print("INGESTION COMPLETE")
            print("=" * 80)
            print(f"Rows processed:       {stats['rows_processed']:,}")
            print(f"Vendors created:      {stats['vendors_created']:,}")
            print(f"Vendors updated:      {stats['vendors_updated']:,}")
            print(f"GSIN codes added:     {stats['gsin_codes_added']:,}")
            print(f"UNSPSC codes added:   {stats['unspsc_codes_added']:,}")
            print(f"Contacts added:       {stats['contacts_added']:,}")
            print("=" * 80)
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

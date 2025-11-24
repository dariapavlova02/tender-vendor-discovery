import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.vendor_ai_agent.database.connection import get_session
from src.vendor_ai_agent.ingestion.canada_sosa import load_sosa

def main():
    print("Starting SOSA ingestion test...")
    print("=" * 80)
    
    csv_path = "data/canada_sources/standing_offers/sosa.csv"
    
    try:
        with get_session() as session:
            stats = load_sosa(session, csv_path)
            
            print("\n" + "=" * 80)
            print("INGESTION COMPLETE")
            print("=" * 80)
            print(f"Rows processed:         {stats['rows_processed']:,}")
            print(f"Vendors created:        {stats['vendors_created']:,}")
            print(f"Vendors updated:        {stats['vendors_updated']:,}")
            print(f"Standing offers added:  {stats['standing_offers_added']:,}")
            print("=" * 80)
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

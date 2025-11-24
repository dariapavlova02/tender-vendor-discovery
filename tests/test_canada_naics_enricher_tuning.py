import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.enrichment_providers.canada_naics_enricher import CanadaNAICSEnricher
from vendor_ai_agent.models import VendorRecord
from sqlalchemy import select
from vendor_ai_agent.database.models import Vendor


def test_threshold_tuning():
    thresholds = [0.5, 0.6, 0.7, 0.8]
    
    with get_session() as session:
        stmt = (
            select(Vendor)
            .where(
                Vendor.source == "canada_contracts",
                Vendor.city.isnot(None)
            )
            .limit(200)
        )
        
        vendors_to_enrich = session.execute(stmt).scalars().all()
        
        print(f"\n{'='*100}")
        print(f"THRESHOLD TUNING - Testing on {len(vendors_to_enrich)} vendors")
        print(f"{'='*100}\n")
        
        for threshold in thresholds:
            enricher = CanadaNAICSEnricher(
                db_session=session,
                similarity_threshold=threshold,
                max_results_per_vendor=5
            )
            
            enriched_count = 0
            total_naics = 0
            
            for vendor_db in vendors_to_enrich:
                vendor_record = VendorRecord(
                    company_name=vendor_db.legal_name,
                    city=vendor_db.city,
                    source=vendor_db.source,
                    filtering_metadata={}
                )
                
                enriched_vendor = enricher.enrich(vendor_record)
                
                if enriched_vendor.filtering_metadata.get("naics_codes"):
                    enriched_count += 1
                    total_naics += len(enriched_vendor.filtering_metadata["naics_codes"])
            
            enrichment_rate = enriched_count / len(vendors_to_enrich) * 100
            avg_naics = total_naics / enriched_count if enriched_count > 0 else 0
            
            print(f"Threshold {threshold:.1f}: {enriched_count:3d}/{len(vendors_to_enrich)} enriched ({enrichment_rate:5.1f}%) | Avg NAICS: {avg_naics:.1f}")
        
        print(f"\n{'='*100}\n")


if __name__ == "__main__":
    test_threshold_tuning()

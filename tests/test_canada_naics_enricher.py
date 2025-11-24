import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.enrichment_providers.canada_naics_enricher import CanadaNAICSEnricher
from vendor_ai_agent.models import VendorRecord
from sqlalchemy import select, func
from vendor_ai_agent.database.models import Vendor


def test_canada_naics_enricher_sample():
    with get_session() as session:
        enricher = CanadaNAICSEnricher(
            db_session=session,
            similarity_threshold=0.7,
            max_results_per_vendor=5
        )
        
        stmt = (
            select(Vendor)
            .where(
                Vendor.source == "canada_contracts",
                Vendor.city.isnot(None)
            )
            .limit(100)
        )
        
        vendors_to_enrich = session.execute(stmt).scalars().all()
        
        print(f"\n{'='*80}")
        print(f"Testing NAICS Enrichment on {len(vendors_to_enrich)} canada_contracts vendors")
        print(f"{'='*80}\n")
        
        enriched_count = 0
        total_naics_found = 0
        
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
                naics_codes = enriched_vendor.filtering_metadata["naics_codes"]
                total_naics_found += len(naics_codes)
                
                print(f"✓ {vendor_db.legal_name[:50]:50} | {vendor_db.city:20} | {len(naics_codes)} NAICS codes")
                print(f"  Codes: {', '.join(naics_codes[:5])}")
                if enriched_vendor.filtering_metadata.get("naics_match_count"):
                    print(f"  Matched with {enriched_vendor.filtering_metadata['naics_match_count']} ODBus vendors")
                print()
        
        print(f"\n{'='*80}")
        print(f"RESULTS:")
        print(f"  Total vendors tested: {len(vendors_to_enrich)}")
        print(f"  Successfully enriched: {enriched_count} ({enriched_count/len(vendors_to_enrich)*100:.1f}%)")
        print(f"  Total NAICS codes found: {total_naics_found}")
        if enriched_count > 0:
            print(f"  Average NAICS per vendor: {total_naics_found/enriched_count:.1f}")
        print(f"{'='*80}\n")


def test_full_enrichment_potential():
    with get_session() as session:
        stmt_total = select(func.count()).select_from(Vendor).where(
            Vendor.source == "canada_contracts",
            Vendor.city.isnot(None)
        )
        total_eligible = session.execute(stmt_total).scalar()
        
        print(f"\n{'='*80}")
        print(f"FULL ENRICHMENT POTENTIAL")
        print(f"{'='*80}")
        print(f"Total canada_contracts vendors with city data: {total_eligible:,}")
        print(f"Ready for NAICS enrichment via ODBus cross-reference")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    print("Phase 1: Testing on 100 sample vendors...")
    test_canada_naics_enricher_sample()
    
    print("\nPhase 2: Analyzing full enrichment potential...")
    test_full_enrichment_potential()

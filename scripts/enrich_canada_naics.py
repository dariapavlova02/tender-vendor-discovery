import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.enrichment_providers.canada_naics_enricher import CanadaNAICSEnricher
from vendor_ai_agent.models import VendorRecord
from vendor_ai_agent.database.models import Vendor, VendorNAICS
from sqlalchemy import select, func, update
import json


def enrich_all_canada_contracts():
    print("\n" + "="*80)
    print("NAICS ENRICHMENT: canada_contracts vendors")
    print("="*80 + "\n")
    
    with get_session() as session:
        stmt_total = (
            select(func.count())
            .select_from(Vendor)
            .where(
                Vendor.source == "canada_contracts",
                Vendor.city.isnot(None)
            )
        )
        total_eligible = session.execute(stmt_total).scalar()
        
        print(f"Total canada_contracts vendors with city data: {total_eligible:,}\n")
        
        enricher = CanadaNAICSEnricher(
            db_session=session,
            similarity_threshold=0.6,
            max_results_per_vendor=5
        )
        
        stmt = (
            select(Vendor)
            .where(
                Vendor.source == "canada_contracts",
                Vendor.city.isnot(None)
            )
        )
        
        vendors_to_enrich = session.execute(stmt).scalars().all()
        
        enriched_count = 0
        total_naics_added = 0
        batch_size = 1000
        processed = 0
        
        for vendor_db in vendors_to_enrich:
            vendor_record = VendorRecord(
                company_name=vendor_db.legal_name,
                city=vendor_db.city,
                source=vendor_db.source,
                filtering_metadata={}
            )
            
            enriched_vendor = enricher.enrich(vendor_record)
            
            if enriched_vendor.filtering_metadata.get("naics_codes"):
                naics_codes = enriched_vendor.filtering_metadata["naics_codes"]
                
                for code in naics_codes:
                    vendor_naics = VendorNAICS(
                        vendor_id=vendor_db.id,
                        naics_code=code,
                        naics_description=None,
                        is_primary=False
                    )
                    session.add(vendor_naics)
                
                if vendor_db.metadata_json:
                    if isinstance(vendor_db.metadata_json, str):
                        metadata = json.loads(vendor_db.metadata_json)
                    else:
                        metadata = vendor_db.metadata_json
                else:
                    metadata = {}
                
                metadata["naics_enriched"] = True
                metadata["naics_source"] = "canada_odbus_cross_reference"
                metadata["naics_match_count"] = enriched_vendor.filtering_metadata["naics_match_count"]
                
                vendor_db.metadata_json = metadata
                
                enriched_count += 1
                total_naics_added += len(naics_codes)
            
            processed += 1
            
            if processed % batch_size == 0:
                session.commit()
                print(f"Progress: {processed:,}/{total_eligible:,} ({processed/total_eligible*100:.1f}%) | Enriched: {enriched_count:,} ({enriched_count/processed*100:.1f}%)")
        
        session.commit()
        
        print(f"\nFinal Progress: {processed:,}/{total_eligible:,} (100.0%)\n")
        print("="*80)
        print("ENRICHMENT RESULTS:")
        print("="*80)
        print(f"  Total vendors processed: {processed:,}")
        print(f"  Successfully enriched: {enriched_count:,} ({enriched_count/processed*100:.1f}%)")
        print(f"  Total NAICS codes added: {total_naics_added:,}")
        if enriched_count > 0:
            print(f"  Average NAICS per vendor: {total_naics_added/enriched_count:.1f}")
        print("="*80 + "\n")


def verify_enrichment_results():
    print("\n" + "="*80)
    print("VERIFICATION: NAICS enrichment results")
    print("="*80 + "\n")
    
    with get_session() as session:
        stmt_contracts_with_naics = (
            select(func.count(func.distinct(VendorNAICS.vendor_id)))
            .select_from(VendorNAICS)
            .join(Vendor)
            .where(Vendor.source == "canada_contracts")
        )
        contracts_with_naics = session.execute(stmt_contracts_with_naics).scalar()
        
        stmt_total_contracts = (
            select(func.count())
            .select_from(Vendor)
            .where(Vendor.source == "canada_contracts")
        )
        total_contracts = session.execute(stmt_total_contracts).scalar()
        
        print(f"canada_contracts vendors:")
        print(f"  Total: {total_contracts:,}")
        print(f"  With NAICS: {contracts_with_naics:,} ({contracts_with_naics/total_contracts*100:.1f}%)")
        print(f"  Without NAICS: {total_contracts - contracts_with_naics:,}\n")
        
        stmt_total_naics = (
            select(func.count())
            .select_from(VendorNAICS)
            .join(Vendor)
            .where(Vendor.source == "canada_contracts")
        )
        total_naics = session.execute(stmt_total_naics).scalar()
        
        print(f"NAICS codes added: {total_naics:,}")
        if contracts_with_naics > 0:
            print(f"Average NAICS per enriched vendor: {total_naics/contracts_with_naics:.1f}")
        
        print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    print("\nPhase 1: Full NAICS enrichment for canada_contracts...")
    enrich_all_canada_contracts()
    
    print("\nPhase 2: Verification...")
    verify_enrichment_results()

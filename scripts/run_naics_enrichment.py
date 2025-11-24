import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.enrichment_providers.canada_naics_enricher import CanadaNAICSEnricher
from vendor_ai_agent.models import VendorRecord
from vendor_ai_agent.database.models import Vendor, VendorNAICS
from sqlalchemy import select, func
import json
from datetime import datetime


def enrich_canada_contracts():
    print(f"\n{'='*100}")
    print(f"NAICS ENRICHMENT: canada_contracts vendors")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*100}\n")
    
    with get_session() as session:
        stmt_total = select(func.count()).select_from(Vendor).where(
            Vendor.source == "canada_contracts",
            Vendor.city.isnot(None)
        )
        total_eligible = session.execute(stmt_total).scalar() or 0
        
        print(f"Total canada_contracts vendors with city data: {total_eligible:,}\n")
        
        enricher = CanadaNAICSEnricher(
            db_session=session,
            similarity_threshold=0.6,
            max_results_per_vendor=5
        )
        
        stmt = select(Vendor).where(
            Vendor.source == "canada_contracts",
            Vendor.city.isnot(None)
        )
        
        vendors_to_enrich = session.execute(stmt).scalars()
        
        enriched_count = 0
        total_naics_added = 0
        batch_size = 1000
        processed = 0
        commit_counter = 0
        
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
                        metadata = dict(vendor_db.metadata_json)
                else:
                    metadata = {}
                
                metadata["naics_enriched"] = True
                metadata["naics_source"] = "canada_odbus_cross_reference"
                metadata["naics_match_count"] = enriched_vendor.filtering_metadata.get("naics_match_count", 0)
                
                vendor_db.metadata_json = json.dumps(metadata)
                
                enriched_count += 1
                total_naics_added += len(naics_codes)
            
            processed += 1
            commit_counter += 1
            
            if commit_counter >= batch_size:
                session.commit()
                commit_counter = 0
                pct = (processed / total_eligible * 100) if total_eligible > 0 else 0
                enrich_pct = (enriched_count / processed * 100) if processed > 0 else 0
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Progress: {processed:,}/{total_eligible:,} ({pct:.1f}%) | Enriched: {enriched_count:,} ({enrich_pct:.1f}%)")
        
        session.commit()
        
        print(f"\n{'='*100}")
        print(f"ENRICHMENT RESULTS:")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*100}")
        print(f"  Total vendors processed: {processed:,}")
        print(f"  Successfully enriched: {enriched_count:,} ({(enriched_count/processed*100) if processed > 0 else 0:.1f}%)")
        print(f"  Total NAICS codes added: {total_naics_added:,}")
        if enriched_count > 0:
            print(f"  Average NAICS per vendor: {total_naics_added/enriched_count:.1f}")
        print(f"{'='*100}\n")


def verify_results():
    print(f"\n{'='*100}")
    print(f"VERIFICATION: NAICS enrichment results")
    print(f"{'='*100}\n")
    
    with get_session() as session:
        stmt_contracts_with_naics = (
            select(func.count(func.distinct(VendorNAICS.vendor_id)))
            .select_from(VendorNAICS)
            .join(Vendor)
            .where(Vendor.source == "canada_contracts")
        )
        contracts_with_naics = session.execute(stmt_contracts_with_naics).scalar() or 0
        
        stmt_total_contracts = select(func.count()).select_from(Vendor).where(
            Vendor.source == "canada_contracts"
        )
        total_contracts = session.execute(stmt_total_contracts).scalar() or 0
        
        print(f"canada_contracts vendors:")
        print(f"  Total: {total_contracts:,}")
        print(f"  With NAICS: {contracts_with_naics:,} ({(contracts_with_naics/total_contracts*100) if total_contracts > 0 else 0:.1f}%)")
        print(f"  Without NAICS: {total_contracts - contracts_with_naics:,}\n")
        
        stmt_total_naics = (
            select(func.count())
            .select_from(VendorNAICS)
            .join(Vendor)
            .where(Vendor.source == "canada_contracts")
        )
        total_naics = session.execute(stmt_total_naics).scalar() or 0
        
        print(f"NAICS codes added: {total_naics:,}")
        if contracts_with_naics > 0:
            print(f"Average NAICS per enriched vendor: {total_naics/contracts_with_naics:.1f}")
        
        print(f"\n{'='*100}\n")


if __name__ == "__main__":
    enrich_canada_contracts()
    verify_results()

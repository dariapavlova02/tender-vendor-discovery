from vendor_ai_agent.database.connection import get_session
from vendor_ai_agent.sources.canada_contracts import CanadaContractsSource

with get_session() as session:
    source = CanadaContractsSource(session)
    
    stats = source.get_vendor_statistics()
    print("=== Canada Contracts Statistics ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n=== Search by GSIN (Shipbuilding - 30) ===")
    vendors = source.search_vendors(gsin_codes=["30"], limit=5)
    for v in vendors:
        print(f"  {v.legal_name} - {v.city}, {v.state}")
        print(f"    Contracts: {v.contract_count}, Value: ${v.total_contract_value:,.2f}")
    
    print("\n=== Search by Province (Ontario) ===")
    vendors = source.search_vendors(province="Ontario", limit=5)
    for v in vendors:
        print(f"  {v.legal_name} - {v.city}")
        print(f"    Contracts: {v.contract_count}, Value: ${v.total_contract_value:,.2f}")

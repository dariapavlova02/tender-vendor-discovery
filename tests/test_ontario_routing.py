import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from pathlib import Path
from src.vendor_ai_agent.modules.document_parser import DocumentParser
from src.vendor_ai_agent.modules.tender_profiler import TenderProfiler
from src.vendor_ai_agent.modules.llm_providers import AnthropicProvider
from src.vendor_ai_agent.modules.vendor_discovery import VendorDiscovery
from src.vendor_ai_agent.sources.sam_entity import SamEntitySource
from src.vendor_ai_agent.sources.canada_contracts import CanadaContractsVendorSource
from src.vendor_ai_agent.models import TenderProfile, APIMetadata

print("=== Testing Smart Source Routing ===\n")

# Initialize components
parser = DocumentParser()
llm_provider = AnthropicProvider()
profiler = TenderProfiler(llm_provider=llm_provider)

# Sources
sam_source = SamEntitySource()
canada_source = CanadaContractsVendorSource()
discovery = VendorDiscovery(sources=[sam_source, canada_source])

# Parse Ontario Parks tender
print("1. Parsing Ontario Parks tender...")
pdf_path = Path('data/Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles to Ontario Parks/RFB Attachments/tender_20488 - Attachment 1 - Parts 1-4.pdf')
parsed = parser.parse([pdf_path])
print(f"   Extracted {len(parsed)} sections\n")

# Profile tender
print("2. Profiling tender with LLM...")
context = profiler.generate_context(parsed)
print(f"   Sector: {context.sector}")
print(f"   Country: {context.country}")
print(f"   Province: {context.province}")
print(f"   GSIN Codes: {context.gsin_codes}")
print(f"   UNSPSC Codes: {context.unspsc_codes}")
print()

# Create minimal TenderProfile for compatibility testing
from src.vendor_ai_agent.models import DynamicTenderContext, CodesMetadata

profile = TenderProfile(
    dynamic_context=DynamicTenderContext(
        sector=context.sector,
        industry_description=context.industry_description,
        technical_keywords=context.technical_keywords,
        search_terms=context.search_terms,
        gsin_codes=context.gsin_codes,
        unspsc_codes=context.unspsc_codes,
        province=context.province,
        country=context.country
    ),
    api_metadata=APIMetadata(
        codes=CodesMetadata(naics=[], gsin=context.gsin_codes, unspsc=context.unspsc_codes)
    )
)

# Test compatibility
print("3. Testing source compatibility...")
print(f"   SAM Entity compatible: {sam_source.is_compatible(profile)}")
print(f"   Canada Contracts compatible: {canada_source.is_compatible(profile)}")
print()

# Run discovery
print("4. Running vendor discovery...")
vendors = discovery.discover(profile)
print(f"   Found {len(vendors)} vendors\n")

print("5. Vendor sources breakdown:")
sources = {}
for v in vendors:
    sources[v.source] = sources.get(v.source, 0) + 1
for source, count in sources.items():
    print(f"   {source}: {count}")
print()

print(f"6. Sample vendors:")
for v in vendors[:5]:
    print(f"   - {v.company_name} ({v.source}, {v.location})")

print("\n✅ Test complete - check logs for 'Skipping sam_entity' message")

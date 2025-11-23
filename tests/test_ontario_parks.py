import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

from pathlib import Path
from src.vendor_ai_agent.pipeline import TenderVendorPipeline

pipeline = TenderVendorPipeline()
artifacts = pipeline.run([Path('data/Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles to Ontario Parks/RFB Attachments/tender_20488 - Attachment 1 - Parts 1-4.pdf')])

print('\n=== TENDER PROFILE ===')
if artifacts.tender_profile.dynamic_context:
    ctx = artifacts.tender_profile.dynamic_context
    print(f'GSIN Codes: {ctx.gsin_codes}')
    print(f'UNSPSC Codes: {ctx.unspsc_codes}')
    print(f'Province: {ctx.province}')
    print(f'Keywords: {ctx.technical_keywords[:10]}')
else:
    print('No dynamic context extracted')

print(f'\n=== DISCOVERED VENDORS ===')
print(f'Total: {len(artifacts.raw_vendors)}')
for v in artifacts.raw_vendors[:5]:
    print(f'  - {v.company_name} ({v.source})')

print(f'\n=== FINAL MATCHES ===')
print(f'Total: {len(artifacts.final_matches)}')
for m in artifacts.final_matches[:5]:
    print(f'  - {m.vendor.company_name} (Score: {m.capability_match_score}, Source: {m.vendor.source})')

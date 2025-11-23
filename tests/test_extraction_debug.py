import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.DEBUG)

from pathlib import Path
from src.vendor_ai_agent.pipeline import TenderVendorPipeline

pipeline = TenderVendorPipeline()
artifacts = pipeline.run([Path('data/Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles to Ontario Parks/RFB Attachments/tender_20488 - Attachment 1 - Parts 1-4.pdf')])

print('\n=== TENDER PROFILE (EXTRACTED) ===')
if artifacts.tender_profile.dynamic_context:
    ctx = artifacts.tender_profile.dynamic_context
    print(f'Sector: {ctx.sector}')
    print(f'Description: {ctx.industry_description[:200]}...')
    print(f'GSIN Codes: {ctx.gsin_codes}')
    print(f'UNSPSC Codes: {ctx.unspsc_codes}')
    print(f'Province: {ctx.province}')
    print(f'Keywords ({len(ctx.technical_keywords)}): {ctx.technical_keywords}')
    print(f'Search Terms ({len(ctx.search_terms)}): {ctx.search_terms}')
else:
    print('No dynamic context extracted')

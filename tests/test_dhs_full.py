"""Full pipeline test for DHS Uniforms III Contract"""
from dotenv import load_dotenv
load_dotenv()

import os
import requests
from vendor_ai_agent.models import TenderProfile, APIMetadata, CodesMetadata, VendorRecord
from vendor_ai_agent.modules import CapabilityMatcher, VendorFilter
from typing import List

print('='*70)
print('DHS UNIFORMS III CONTRACT - FULL PIPELINE TEST')
print('='*70)

# Step 1: Create tender profile with NAICS 315210 (from PDF page 1)
profile = TenderProfile(
    tender_id='70B01C26R00000004',
    country='US',
    source_system='SAM',
    api_metadata=APIMetadata(
        title='DHS-wide Uniforms III Contract',
        codes=CodesMetadata(naics=['315210', '315990'])
    )
)

print(f'\nTENDER PROFILE:')
print(f'  ID: {profile.tender_id}')
print(f'  Title: {profile.api_metadata.title}')
print(f'  NAICS: {profile.api_metadata.codes.naics}')

# Step 2: Search SAM.gov API
api_key = os.getenv('SAM_API_KEY')
all_vendors = []

print(f'\nVENDOR DISCOVERY (SAM.gov API):')
for naics in profile.api_metadata.codes.naics:
    url = 'https://api.sam.gov/entity-information/v3/entities'
    params = {
        'api_key': api_key,
        'primaryNaics': naics,
        'registrationStatus': 'A',
        'page': 0,
        'size': 100
    }
    
    response = requests.get(url, params=params, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        entities = data.get('entityData', [])
        total_records = data.get('totalRecords', 0)
        print(f'  NAICS {naics}: {total_records} total, retrieved {len(entities)}')
        
        for e in entities:
            reg = e.get('entityRegistration', {})
            core = e.get('coreData', {})
            addr = core.get('physicalAddress', {})
            bt_data = core.get('businessTypes', {})
            bt_list = bt_data.get('businessTypeList', [])
            business_types = [bt.get('businessTypeDesc', '') for bt in bt_list]
            
            vendor = VendorRecord(
                uei_sam_number=reg.get('ueiSAM'),
                legal_name=reg.get('legalBusinessName', ''),
                dba_name=reg.get('dbaName'),
                city=addr.get('city'),
                state=addr.get('stateOrProvinceCode'),
                country='US',
                naics_codes=[naics],
                is_small_business=any('Small' in bt for bt in business_types),
                is_woman_owned=any('Woman' in bt for bt in business_types),
                is_veteran_owned=any('Veteran' in bt for bt in business_types),
                is_8a=any('8(a)' in bt for bt in business_types)
            )
            all_vendors.append(vendor)

print(f'\nTotal vendors discovered: {len(all_vendors)}')

# Step 3: Filter vendors
filter_module = VendorFilter()
filtered = filter_module.filter(profile, all_vendors)
print(f'After filtering: {len(filtered)}')

# Step 4: Score vendors
matcher = CapabilityMatcher()
matches = matcher.score(profile, filtered)
matches_sorted = sorted(matches, key=lambda m: m.score, reverse=True)

print(f'\n{"="*70}')
print(f'TOP 30 VENDOR MATCHES')
print(f'{"="*70}\n')

for i, match in enumerate(matches_sorted[:30], 1):
    v = match.vendor
    name_display = v.legal_name[:55] if len(v.legal_name) > 55 else v.legal_name
    print(f'{i:2d}. {name_display:<55} Score: {match.score:.2f}')
    print(f'    Location: {v.city}, {v.state}')
    print(f'    UEI: {v.uei_sam_number}')
    certs = []
    if v.is_small_business: 
        certs.append('SB')
    if v.is_woman_owned: 
        certs.append('WOSB')
    if v.is_veteran_owned: 
        certs.append('VOSB')
    if v.is_8a: 
        certs.append('8(a)')
    if certs:
        cert_str = ', '.join(certs)
        print(f'    Certifications: {cert_str}')
    print()

# Statistics
print(f'{"="*70}')
print(f'STATISTICS')
print(f'{"="*70}')
states = {}
for m in matches_sorted:
    state = m.vendor.state or 'Unknown'
    states[state] = states.get(state, 0) + 1

print(f'\nTotal matches: {len(matches_sorted)}')
print(f'Small Business: {sum(1 for m in matches_sorted if m.vendor.is_small_business)}')
print(f'Women-Owned: {sum(1 for m in matches_sorted if m.vendor.is_woman_owned)}')
print(f'Veteran-Owned: {sum(1 for m in matches_sorted if m.vendor.is_veteran_owned)}')
print(f'8(a): {sum(1 for m in matches_sorted if m.vendor.is_8a)}')
print(f'\nTop 10 States:')
for state, count in sorted(states.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f'  {state}: {count}')

print(f'\n{"="*70}')
print('TEST COMPLETE')
print(f'{"="*70}')

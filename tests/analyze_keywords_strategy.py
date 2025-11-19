import sys
sys.path.insert(0, 'src')
from vendor_ai_agent.modules.document_processing.keywords import TECHNICAL_KEYWORDS, SECTOR_KEYWORDS

print("=" * 80)
print("KEYWORD STRATEGY ANALYSIS")
print("=" * 80)

print("\n1. CURRENT STATE:")
print(f"   - Defined sectors: {list(TECHNICAL_KEYWORDS.keys())}")
print(f"   - Total technical keywords: {sum(len(v) for v in TECHNICAL_KEYWORDS.values())}")

print("\n2. SCENARIOS:")

print("\n   SCENARIO A: Medical Equipment Tender")
print("   - Sector detection: 'general' (no medical keywords defined)")
print("   - Current behavior: Searches ALL keywords from ALL sectors")
print("   - Risk: May match 'construction', 'ammunition', 'it' by accident")
print("   - Keywords found: 0-3 (random false positives)")
print("   - Impact: 🔴 INCORRECT - false matches")

print("\n   SCENARIO B: Medical Equipment Tender (with sector-aware)")
print("   - Sector detection: 'general'")
print("   - Behavior: Uses TECHNICAL_KEYWORDS.get('general', [])")
print("   - Keywords found: 0 (no medical keywords defined)")
print("   - Impact: ✅ CORRECT - no false matches, just empty list")

print("\n   SCENARIO C: Medical Equipment Tender (with medical keywords)")
print("   - Add SECTOR_KEYWORDS['medical'] = ['medical equipment', 'surgical', ...]")
print("   - Add TECHNICAL_KEYWORDS['medical'] = ['mri', 'ct scanner', ...]")
print("   - Sector detection: 'medical'")
print("   - Behavior: Uses only medical keywords")
print("   - Keywords found: 5-10 (real medical terms)")
print("   - Impact: ✅ CORRECT - accurate matches")

print("\n" + "=" * 80)
print("STRATEGY RECOMMENDATION")
print("=" * 80)

print("\n📋 TWO-PHASE APPROACH:")
print("\n   PHASE 1 (IMMEDIATE - CRITICAL):")
print("   ✅ Fix sector-aware keyword matching")
print("   ✅ Prevent cross-sector contamination")
print("   ✅ Fallback to [] for unknown sectors")
print("   Result: System becomes SAFE and CORRECT")

print("\n   PHASE 2 (GRADUAL - AS NEEDED):")
print("   ✅ Add new sectors when real tenders appear")
print("   ✅ Analyze tender documents to find real keywords")
print("   ✅ Build keyword lists from actual data")
print("   Result: System becomes MORE COMPLETE")

print("\n" + "=" * 80)
print("KEYWORD EXPANSION PRIORITY")
print("=" * 80)

common_canadian_sectors = {
    "construction": "Already covered (15 keywords)",
    "ammo_supply": "Already covered (29 keywords)", 
    "it": "Already covered (14 keywords)",
    "professional_services": "NOT covered - consulting, legal, accounting",
    "medical": "NOT covered - medical equipment, healthcare",
    "facilities_management": "NOT covered - cleaning, security, maintenance",
    "food_services": "NOT covered - catering, meal prep",
    "office_supplies": "NOT covered - furniture, stationery",
    "vehicles": "NOT covered - fleet, vehicles, parts",
    "environmental": "NOT covered - waste management, remediation"
}

print("\nCommon Government Tender Sectors:")
for sector, status in common_canadian_sectors.items():
    icon = "✅" if "Already" in status else "❌"
    print(f"  {icon} {sector:30s} - {status}")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print("""
🎯 ANSWER: НЕ нужно сейчас добавлять больше keywords!

ПОЧЕМУ:
1. Сначала FIX sector-aware matching (безопасность)
2. Для неизвестных секторов возвращать [] (корректно)
3. Добавлять новые секторы ТОЛЬКО когда появятся реальные тендеры
4. Для каждого сектора собирать keywords из реальных документов

ПРАВИЛЬНЫЙ ПРОЦЕСС:
  Real Tender → Analyze Document → Extract Terms → Add Keywords → Test

НЕПРАВИЛЬНЫЙ ПРОЦЕСС:  
  Guess Keywords → Add Random Terms → Hope They Match ❌
""")

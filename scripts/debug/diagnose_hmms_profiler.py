"""
Diagnostic script for HMMS04531 tender profiler analysis.

Goals:
1. Extract scope complexity from HMMS04531 PDFs
2. Generate search_terms via TenderProfiler
3. Analyze word frequency and semantic overlap
4. Measure actual diversity metrics

Usage:
    python scripts/debug/diagnose_hmms_profiler.py
"""
import os
import sys
from pathlib import Path
from typing import List, Dict, Set
import re

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from vendor_ai_agent.modules.tender_profiler import TenderProfiler
from vendor_ai_agent.modules.llm_providers import OpenAIProvider
from vendor_ai_agent.modules.document_parser import DocumentParser


def tokenize_query(query: str) -> List[str]:
    """Tokenize query into meaningful words (lowercase, filter stopwords)."""
    stopwords = {'a', 'an', 'and', 'or', 'the', 'for', 'of', 'in', 'to', 'with', 'by', 'from'}
    words = re.findall(r'\b[a-z]+\b', query.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]


def calculate_semantic_overlap(q1: str, q2: str) -> float:
    """Calculate Jaccard similarity between two queries."""
    words1 = set(tokenize_query(q1))
    words2 = set(tokenize_query(q2))
    if not words1 or not words2:
        return 0.0
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def analyze_word_frequency(queries: List[str]) -> Dict[str, int]:
    """Count word frequencies across all queries."""
    word_counts: Dict[str, int] = {}
    for query in queries:
        for word in tokenize_query(query):
            word_counts[word] = word_counts.get(word, 0) + 1
    return word_counts


def find_semantic_clusters(queries: List[str], threshold: float = 0.4) -> List[List[int]]:
    """Group queries into semantic clusters based on word overlap."""
    n = len(queries)
    clusters = []
    assigned = set()
    
    for i in range(n):
        if i in assigned:
            continue
        
        cluster = [i]
        assigned.add(i)
        
        for j in range(i + 1, n):
            if j in assigned:
                continue
            
            overlap = calculate_semantic_overlap(queries[i], queries[j])
            if overlap >= threshold:
                cluster.append(j)
                assigned.add(j)
        
        clusters.append(cluster)
    
    return clusters


def main():
    """Run diagnostic analysis on HMMS04531 tender."""
    
    print("="*80)
    print("HMMS04531 TENDER PROFILER DIAGNOSTIC")
    print("="*80)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ ERROR: OPENAI_API_KEY not set")
        return
    
    test_case_dir = project_root / "data" / "test_case"
    pdf_path = test_case_dir / "HMMS04531 - Appendix 1 Scope, Schedule, Scoring v4.pdf"
    
    if not pdf_path.exists():
        print(f"\n❌ ERROR: Test case PDF not found at {pdf_path}")
        return
    
    print(f"\n📄 Parsing PDF: {pdf_path.name}")
    
    parser = DocumentParser()
    sections = parser.parse([pdf_path])
    
    print(f"✓ Extracted {len(sections)} sections")
    
    total_chars = sum(len(s.content) for s in sections)
    print(f"✓ Total content: {total_chars:,} characters")
    
    print("\n" + "="*80)
    print("STEP 1: EXTRACT TENDER CONTEXT")
    print("="*80)
    
    provider = OpenAIProvider()
    profiler = TenderProfiler(llm_provider=provider)
    
    context = profiler.generate_context(sections, max_tokens=3000)
    
    print(f"\n📊 TENDER CONTEXT RESULTS:")
    print(f"  Sector: {context.sector}")
    print(f"  Country: {context.country}")
    print(f"  Province: {context.province}")
    print(f"\n  Industry Description:")
    print(f"  {context.industry_description}")
    print(f"\n  Technical Keywords ({len(context.technical_keywords)}):")
    for i, kw in enumerate(context.technical_keywords[:10], 1):
        print(f"    {i:2d}. {kw}")
    if len(context.technical_keywords) > 10:
        print(f"    ... and {len(context.technical_keywords) - 10} more")
    
    print(f"\n  Search Terms ({len(context.search_terms)}):")
    for i, term in enumerate(context.search_terms, 1):
        print(f"    {i:2d}. {term}")
    
    print("\n" + "="*80)
    print("STEP 2: WORD FREQUENCY ANALYSIS")
    print("="*80)
    
    word_freq = analyze_word_frequency(context.search_terms)
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]
    
    print(f"\n📈 TOP 20 WORDS BY FREQUENCY:")
    for word, count in top_words:
        bar = "█" * count
        print(f"  {word:20s} [{count:2d}] {bar}")
    
    overused = [(w, c) for w, c in top_words if c > 3]
    if overused:
        print(f"\n⚠️  WORDS APPEARING >3 TIMES:")
        for word, count in overused:
            print(f"    {word}: {count}×")
    else:
        print(f"\n✓ No words appear >3 times")
    
    print("\n" + "="*80)
    print("STEP 3: SEMANTIC OVERLAP ANALYSIS")
    print("="*80)
    
    clusters = find_semantic_clusters(context.search_terms, threshold=0.4)
    
    print(f"\n🔍 SEMANTIC CLUSTERS (threshold=0.4):")
    print(f"  Total clusters: {len(clusters)}")
    print(f"  Singleton clusters: {sum(1 for c in clusters if len(c) == 1)}")
    print(f"  Multi-query clusters: {sum(1 for c in clusters if len(c) > 1)}")
    
    multi_clusters = [c for c in clusters if len(c) > 1]
    if multi_clusters:
        print(f"\n  DUPLICATE CLUSTERS:")
        for i, cluster in enumerate(multi_clusters, 1):
            print(f"\n  Cluster {i} ({len(cluster)} queries):")
            for idx in cluster:
                overlap_scores = []
                for other_idx in cluster:
                    if idx != other_idx:
                        overlap = calculate_semantic_overlap(
                            context.search_terms[idx],
                            context.search_terms[other_idx]
                        )
                        overlap_scores.append(overlap)
                avg_overlap = sum(overlap_scores) / len(overlap_scores) if overlap_scores else 0
                print(f"    [{idx+1:2d}] {context.search_terms[idx]:50s} (avg overlap: {avg_overlap:.2f})")
    
    print("\n" + "="*80)
    print("STEP 4: DIVERSITY METRICS")
    print("="*80)
    
    business_types = {
        'manufacturers': ['manufacturer', 'producers', 'makers', 'oem', 'fabricator'],
        'distributors': ['distributor', 'wholesaler', 'supplier', 'reseller'],
        'services': ['services', 'installer', 'maintenance', 'integrator', 'consultant'],
    }
    
    type_counts = {k: 0 for k in business_types.keys()}
    for query in context.search_terms:
        query_lower = query.lower()
        for biz_type, keywords in business_types.items():
            if any(kw in query_lower for kw in keywords):
                type_counts[biz_type] += 1
                break
    
    print(f"\n📊 BUSINESS TYPE DISTRIBUTION:")
    for biz_type, count in type_counts.items():
        pct = (count / len(context.search_terms) * 100) if context.search_terms else 0
        print(f"  {biz_type:20s}: {count:2d} ({pct:5.1f}%)")
    
    specificity = {
        'highly_specific': 0,
        'medium': 0,
        'broad': 0
    }
    
    for query in context.search_terms:
        words = tokenize_query(query)
        if len(words) >= 5:
            specificity['highly_specific'] += 1
        elif len(words) >= 3:
            specificity['medium'] += 1
        else:
            specificity['broad'] += 1
    
    print(f"\n📊 SPECIFICITY DISTRIBUTION (by word count):")
    for level, count in specificity.items():
        pct = (count / len(context.search_terms) * 100) if context.search_terms else 0
        print(f"  {level:20s}: {count:2d} ({pct:5.1f}%)")
    
    print("\n" + "="*80)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*80)
    
    issues = []
    
    if overused:
        issues.append(f"❌ Word frequency: {len(overused)} words appear >3 times")
    else:
        issues.append(f"✓ Word frequency: All words appear ≤3 times")
    
    if len(multi_clusters) > 3:
        issues.append(f"❌ Semantic overlap: {len(multi_clusters)} duplicate clusters detected")
    else:
        issues.append(f"✓ Semantic overlap: Low duplication ({len(multi_clusters)} clusters)")
    
    total_queries = len(context.search_terms)
    duplicate_queries = sum(len(c) - 1 for c in multi_clusters)
    unique_queries = total_queries - duplicate_queries
    
    issues.append(f"ℹ️  Query efficiency: {unique_queries}/{total_queries} unique ({unique_queries/total_queries*100:.0f}%)")
    
    print()
    for issue in issues:
        print(f"  {issue}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

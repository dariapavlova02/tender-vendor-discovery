"""Compare old (sync) vs new (streaming) pipeline performance."""
import logging
import time
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.pipeline import TenderVendorPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def run_old_pipeline():
    """Run old synchronous pipeline."""
    print("\n" + "="*80)
    print("🔵 OLD PIPELINE (Synchronous)")
    print("="*80)
    
    config = RuntimeConfig()
    config.enrichment.enable_streaming_pipeline = False  # OLD
    
    # Enable website enrichment
    config.enrichment.enable_website_search = True
    config.enrichment.enable_ddg_search = True
    
    # Limit discovery for fair comparison
    config.discovery.target_results = 25
    config.filtering.max_candidates = 25
    config.discovery.enable_serper_discovery = False
    config.discovery.enable_apollo_discovery = False
    
    config.capability_matching.enable_llm_assessment = True
    
    tender_file = Path("RFB25-106 Waterloo Grounds Maintenance.pdf")
    
    if not tender_file.exists():
        print(f"❌ Tender file not found: {tender_file}")
        return None
    
    print(f"📄 Processing: {tender_file}")
    print(f"   Streaming: {config.enrichment.enable_streaming_pipeline}")
    print()
    
    start_time = time.time()
    
    try:
        pipeline = TenderVendorPipeline(config)
        artifacts = pipeline.run([tender_file])
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ OLD Pipeline completed in {elapsed:.1f}s")
        print(f"   Raw vendors: {len(artifacts.raw_vendors)}")
        print(f"   Enriched vendors: {len(artifacts.enriched_vendors)}")
        print(f"   Final matches: {len(artifacts.final_matches)}")
        print(f"   All matches: {len(artifacts.all_matches or [])}")
        
        if artifacts.final_matches:
            print(f"\n📊 Top 3 matches:")
            for i, match in enumerate(artifacts.final_matches[:3], 1):
                print(f"   {i}. {match.vendor.company_name} - Score: {match.capability_match_score:.1f}")
        
        return {
            "name": "Old (Sync)",
            "time": elapsed,
            "raw_vendors": len(artifacts.raw_vendors),
            "enriched_vendors": len(artifacts.enriched_vendors),
            "final_matches": len(artifacts.final_matches),
            "all_matches": len(artifacts.all_matches or [])
        }
        
    except Exception as e:
        print(f"\n❌ OLD Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_new_pipeline():
    """Run new streaming pipeline."""
    print("\n" + "="*80)
    print("🟢 NEW PIPELINE (Streaming)")
    print("="*80)
    
    config = RuntimeConfig()
    config.enrichment.enable_streaming_pipeline = True  # NEW
    config.enrichment.streaming_batch_size = 50
    config.enrichment.streaming_max_queue_size = 3
    config.enrichment.max_concurrent_batches = 2
    
    # Enable website enrichment
    config.enrichment.enable_website_search = True
    config.enrichment.enable_ddg_search = True
    
    # Limit discovery for fair comparison
    config.discovery.target_results = 25
    config.filtering.max_candidates = 25
    config.discovery.enable_serper_discovery = False
    config.discovery.enable_apollo_discovery = False
    
    config.capability_matching.enable_llm_assessment = True
    
    tender_file = Path("RFB25-106 Waterloo Grounds Maintenance.pdf")
    
    if not tender_file.exists():
        print(f"❌ Tender file not found: {tender_file}")
        return None
    
    print(f"📄 Processing: {tender_file}")
    print(f"   Streaming: {config.enrichment.enable_streaming_pipeline}")
    print(f"   Batch size: {config.enrichment.streaming_batch_size}")
    print(f"   Max concurrent batches: {config.enrichment.max_concurrent_batches}")
    print()
    
    start_time = time.time()
    
    try:
        pipeline = TenderVendorPipeline(config)
        artifacts = pipeline.run([tender_file])
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ NEW Pipeline completed in {elapsed:.1f}s")
        print(f"   Raw vendors: {len(artifacts.raw_vendors)}")
        print(f"   Enriched vendors: {len(artifacts.enriched_vendors)}")
        print(f"   Final matches: {len(artifacts.final_matches)}")
        print(f"   All matches: {len(artifacts.all_matches or [])}")
        
        if artifacts.final_matches:
            print(f"\n📊 Top 3 matches:")
            for i, match in enumerate(artifacts.final_matches[:3], 1):
                print(f"   {i}. {match.vendor.company_name} - Score: {match.capability_match_score:.1f}")
        
        # Check if streaming output exists
        output_dir = Path("outputs")
        streaming_output = output_dir / config.output.base_filename / "all_matches.parquet"
        if streaming_output.exists():
            print(f"   ✅ Streaming output file: {streaming_output}")
        
        return {
            "name": "New (Streaming)",
            "time": elapsed,
            "raw_vendors": len(artifacts.raw_vendors),
            "enriched_vendors": len(artifacts.enriched_vendors),
            "final_matches": len(artifacts.final_matches),
            "all_matches": len(artifacts.all_matches or [])
        }
        
    except Exception as e:
        print(f"\n❌ NEW Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_results(old_result, new_result):
    """Compare results between old and new pipelines."""
    print("\n" + "="*80)
    print("📊 COMPARISON RESULTS")
    print("="*80)
    
    if not old_result or not new_result:
        print("❌ Cannot compare - one or both pipelines failed")
        return
    
    print(f"\n⏱️  PERFORMANCE:")
    print(f"   Old Pipeline:  {old_result['time']:.1f}s")
    print(f"   New Pipeline:  {new_result['time']:.1f}s")
    
    speedup = old_result['time'] / new_result['time'] if new_result['time'] > 0 else 0
    time_saved = old_result['time'] - new_result['time']
    
    if speedup > 1:
        print(f"   🚀 Speedup:     {speedup:.2f}x faster ({time_saved:.1f}s saved)")
    elif speedup < 1:
        print(f"   🐌 Slowdown:    {1/speedup:.2f}x slower ({-time_saved:.1f}s lost)")
    else:
        print(f"   ⚖️  Same speed")
    
    print(f"\n📈 RESULTS:")
    print(f"   {'Metric':<20} {'Old':<15} {'New':<15} {'Diff'}")
    print(f"   {'-'*20} {'-'*15} {'-'*15} {'-'*15}")
    
    for key in ['raw_vendors', 'enriched_vendors', 'final_matches', 'all_matches']:
        old_val = old_result[key]
        new_val = new_result[key]
        diff = new_val - old_val
        diff_str = f"{'+' if diff > 0 else ''}{diff}"
        print(f"   {key:<20} {old_val:<15} {new_val:<15} {diff_str}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    print("\n🔬 PIPELINE PERFORMANCE COMPARISON")
    print("   Testing with ~20-25 vendors from Waterloo tender")
    print()
    
    # Run old pipeline first
    old_result = run_old_pipeline()
    
    # Wait a bit between runs
    print("\n⏸️  Waiting 5 seconds before next run...")
    time.sleep(5)
    
    # Run new pipeline
    new_result = run_new_pipeline()
    
    # Compare results
    compare_results(old_result, new_result)

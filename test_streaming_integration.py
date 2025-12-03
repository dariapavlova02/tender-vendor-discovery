"""Test streaming pipeline integration with a small tender."""
import logging
from pathlib import Path

from src.vendor_ai_agent.config import RuntimeConfig
from src.vendor_ai_agent.pipeline import TenderVendorPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def test_streaming_pipeline():
    """Test streaming pipeline with Waterloo tender."""
    
    # Configure with streaming enabled
    config = RuntimeConfig()
    config.enrichment.enable_streaming_pipeline = True
    config.enrichment.streaming_batch_size = 10  # Small batch for testing
    config.enrichment.streaming_max_queue_size = 3
    config.enrichment.max_concurrent_batches = 2
    
    # Enable website enrichment
    config.enrichment.enable_website_search = True
    config.enrichment.enable_ddg_search = True
    
    # Limit discovery for faster testing
    config.discovery.target_results = 50
    config.filtering.max_candidates = 50
    config.discovery.enable_serper_discovery = False  # Skip for speed
    config.discovery.enable_apollo_discovery = False
    
    # Enable async mode
    config.capability_matching.enable_llm_assessment = True
    
    tender_file = Path("RFB25-106 Waterloo Grounds Maintenance.pdf")
    
    if not tender_file.exists():
        print(f"❌ Tender file not found: {tender_file}")
        return
    
    print(f"🚀 Testing streaming pipeline with {tender_file}")
    print(f"   Streaming enabled: {config.enrichment.enable_streaming_pipeline}")
    print(f"   Batch size: {config.enrichment.streaming_batch_size}")
    print(f"   Max concurrent batches: {config.enrichment.max_concurrent_batches}")
    print(f"   Max queue size: {config.enrichment.streaming_max_queue_size}")
    print()
    
    try:
        pipeline = TenderVendorPipeline(config)
        artifacts = pipeline.run([tender_file])
        
        print("\n✅ Pipeline completed successfully!")
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
            print(f"\n✅ Streaming output file created: {streaming_output}")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_streaming_pipeline()

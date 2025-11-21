# Quick Start: Dynamic Tender Profiling

## Installation

```bash
cd /Users/dariapavlova/Documents/vendor_ai_agent
poetry install
```

## Configuration

### Option 1: Environment Variable (Recommended)
```bash
export OPENAI_API_KEY="sk-..."
```

### Option 2: Pass API Key Directly
```python
from vendor_ai_agent.modules import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
```

## Usage Examples

### Basic Pipeline (Auto-detects LLM Provider)
```python
from pathlib import Path
from vendor_ai_agent.pipeline import TenderVendorPipeline

# Initialize pipeline (will use OpenAI if OPENAI_API_KEY is set)
pipeline = TenderVendorPipeline()

# Run on tender documents
tender_files = [
    Path("data/Object _ rfx_18106 - OPP-1984 Supply and Delivery of Ammunition/...")
]

artifacts = pipeline.run(tender_files)

# Access dynamic context
profile = artifacts.tender_profile
if profile.dynamic_context:
    print(f"Sector: {profile.dynamic_context.sector}")
    print(f"Keywords: {profile.dynamic_context.technical_keywords}")
    print(f"Search terms: {profile.dynamic_context.search_terms}")
```

### Standalone Profiler
```python
from vendor_ai_agent.modules import TenderProfiler, OpenAIProvider

# Initialize
provider = OpenAIProvider()
profiler = TenderProfiler(llm_provider=provider)

# Generate context
context = profiler.generate_context_from_sections(
    scope_of_work="Supply and delivery of ammunition...",
    technical_requirements="SAAMI compliant, non-corrosive primers..."
)

print(f"Sector: {context.sector}")
print(f"Keywords: {context.technical_keywords}")
print(f"Search terms: {context.search_terms}")
```

### Fallback Mode (No LLM Provider)
```python
from vendor_ai_agent.modules import TenderProfiler

# No provider = fallback to hardcoded keywords
profiler = TenderProfiler(llm_provider=None)

context = profiler.generate_context_from_sections(scope, tech_req)
# Returns: sector="Unknown", keywords=[], search_terms=[]
```

## Testing

### Run Dynamic Profiler Test
```bash
# With OpenAI API key
export OPENAI_API_KEY="sk-..."
poetry run python tests/test_dynamic_profiler.py

# Without API key (fallback mode only)
poetry run python tests/test_dynamic_profiler.py
```

### Run Full Test Suite
```bash
poetry run pytest tests/
```

## Cost Estimation

### Per Tender Profiling
- Input tokens: ~1000 (scope + technical requirements)
- Output tokens: ~500 (keywords + search terms)
- **Cost: ~$0.001 per tender** using gpt-4o

### Cost Optimization
```python
from vendor_ai_agent.config import RuntimeConfig

# Use flex tier for 50% discount (adds 30-60s latency)
config = RuntimeConfig()
config.llm.use_flex_tier = True

pipeline = TenderVendorPipeline(config=config)
```

## Troubleshooting

### Import Errors (Expected Before Install)
```
ERROR: Import "openai" could not be resolved
```
**Solution:** Run `poetry install`

### Missing API Key
```
ValueError: OpenAI API key not provided
```
**Solution:** Set `OPENAI_API_KEY` environment variable

### LLM Provider Warnings
```
WARNING: LLM provider not available. Using fallback mode.
```
**Solution:** This is expected if OpenAI is not configured. Pipeline will use hardcoded keywords as fallback.

## Model Configuration

Edit `src/vendor_ai_agent/config.py`:

```python
@dataclass
class LLMConfig:
    smart_model: str = "gpt-4o"              # For complex analysis
    cheap_model: str = "gpt-4o-mini"         # For routine tasks
    vision_model: str = "gpt-4o-mini"        # For OCR/document scanning
    use_flex_tier: bool = True               # 50% discount, adds latency
```

## Architecture Flow

```
Tender PDFs
    ↓
DocumentParser (extract text + tables)
    ↓
RequirementExtractor
    ↓
TenderProfiler ← OpenAIProvider (generates dynamic context)
    ↓
TenderContext:
  - sector: "Ammunition Supply"
  - technical_keywords: ["saami", "frangible", "9mm", ...]
  - search_terms: ["ammunition suppliers ontario", ...]
    ↓
FieldExtractor (uses dynamic keywords instead of hardcoded)
    ↓
VendorDiscovery (uses dynamic search terms)
    ↓
VendorMatches
```

## Next Steps

1. **Test on ammunition tender**
   ```bash
   poetry run python scripts/run_full_pipeline.py
   ```

2. **Test on vehicle tender**
   ```bash
   # Use different tender directory
   poetry run python scripts/run_full_pipeline.py \
     --input "data/Object _ rfx_18456 - Supply and Delivery of 5 Utility Vehicles..."
   ```

3. **Compare dynamic vs. static keywords**
   - Run with LLM provider enabled
   - Run with LLM provider disabled (fallback)
   - Compare vendor discovery results

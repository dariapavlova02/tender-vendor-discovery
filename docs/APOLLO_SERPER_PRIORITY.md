# Discovery Source Priority

This note describes how the discovery stack selects between Apollo and Serper in the current pipeline (see `src/vendor_ai_agent/pipeline.py`).

## Summary

- Only one internet discovery source is active at a time. Apollo is registered when `DiscoveryConfig.enable_apollo_discovery` is `True` **and** an Apollo API key is available. When that flag is `False`, Serper can be registered if `enable_serper_discovery` is `True` and a Serper API key is available. If neither source is configured, the pipeline falls back to the static directory for resilience.
- There is **no** automatic Serper fallback when Apollo returns fewer candidates than expected. If fallback behavior is required, both discovery sources must be run in separate batches or scripts.
- The `enable_apollo_booster` flag controls an additional booster step (after the primary discovery flow) that appends Apollo results when the filtered candidate set is still below `apollo_min_candidates`. This booster is independent of the primary discovery source.

## Configuration Reference

```python
@dataclass
class DiscoveryConfig:
    enable_apollo_discovery: bool = False
    enable_apollo_booster: bool = False
    apollo_min_candidates: int = 200
    enable_serper_discovery: bool = True
```

- Set `enable_apollo_discovery = True` to make Apollo the primary discovery source. The Serper discovery class will not be registered in this mode even if `enable_serper_discovery` is `True`.
- Set `enable_apollo_discovery = False` and `enable_serper_discovery = True` to use Serper instead of Apollo.
- Set both to `False` to rely solely on SAM + Canada sources plus the static directory fallback.

## Operational Recommendations

1. Decide on the primary discovery API per run (Apollo or Serper) based on credentials and availability.
2. When operating Apollo as the primary source, monitor the number of candidates produced by the booster step. If the filtered list is still too small, run a separate Serper-based batch instead of relying on undocumented fallback behavior.
3. Keep `StaticDirectorySource` enabled in configuration for resilience during API outages or credential issues.

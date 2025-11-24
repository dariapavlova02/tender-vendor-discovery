# Enhanced Dashboard Features

## Overview

The dashboard has been enhanced with comprehensive configuration options and manual control features to provide users with full control over the vendor discovery pipeline.

---

## 🆕 New Features

### 1. **Extended Configuration Sidebar**

#### LLM Settings
- **LLM Model Selection**: Choose between `gpt-5-mini` (fast/cheap) and `gpt-5.1` (high quality)
- **Flex Tier**: Enable OpenAI Flex tier for cost optimization

#### Processing Mode
- **Manual Review Mode**: Enable to review and edit extraction results before filtering
- **Auto Ingestion**: Automatically fetch attachments from source APIs

#### Geographic Settings
- **Geographic Scope**: Control vendor search radius
  - `local_only` - Only vendors in the same city/state
  - `local_plus_regional` - Local + nearby regions (default)
  - `national` - All vendors in the same country
  - `custom_radius` - Specify exact search radius in kilometers
- **Custom Search Radius**: Set specific distance for vendor search (50-500 km)

#### Results Settings
- **Max Vendors**: Control maximum number of vendor candidates (50-1000)
- Affects filtering stage to limit result size

#### Enrichment Settings
- **Google Maps Enrichment**: Enable contact enrichment via Google Maps API
- **Apollo Enrichment**: Enable contact enrichment via Apollo API
- **Auto-Enrich Missing Contacts**: Automatically enrich vendors without contact info

---

### 2. **Extraction Editor Tab**

Located in **"🧠 Extracted Data" → "✏️ Edit Extraction"**

#### Features:
- **Edit Location Data**: Correct city, state/province, country
- **Edit NAICS Codes**: Add or remove NAICS codes (comma-separated)
- **Edit Set-Aside Programs**: Modify set-aside types (8(a), WOSB, SDVOSB, etc.)
- **Save & Re-run**: Apply changes and re-execute pipeline with corrected data

#### Use Case:
When the AI extraction makes errors or misses important details, you can manually correct the data before vendor discovery runs.

---

### 3. **Manual Vendor Enrichment Tab**

Located in **"🏢 Vendors" → "💎 Manual Enrichment"**

#### Features:
- **Contact Status Indicators**:
  - ✅ Complete (email + phone)
  - ⚠️ Partial (email or phone)
  - ❌ Missing (no contacts)

- **Filtering Options**:
  - View all vendors
  - View only vendors missing contacts
  - View vendors with partial contacts

- **Enrichment Methods**:
  - **🗺️ Google Maps**: Batch or individual enrichment via Google Maps API
  - **🚀 Apollo**: Batch or individual enrichment via Apollo API
  - **✏️ Manual Entry**: Manually enter contact information

#### Batch Operations:
- **Batch Enrich via Google Maps**: Process all missing vendors at once
- **Batch Enrich via Apollo**: Alternative enrichment source

#### Individual Enrichment:
Each vendor card provides:
- Current company information
- Contact status (email, phone)
- Three enrichment options (Google Maps, Apollo, Manual Entry)

---

### 4. **Enhanced Vendor Display**

#### Contact Status Icons:
- ✅ Complete contacts
- ⚠️ Partial contacts  
- ❌ Missing contacts

#### Additional Metrics:
- **Missing Contacts Count**: Shows how many vendors need enrichment
- **Past Winners**: Highlights vendors with past contract wins

#### Export Options:
- **📥 Download CSV**: Export results with all data
- **💾 Save as Excel**: Save to outputs/ directory
- **📊 Generate Report**: Comprehensive report generation (coming soon)

---

## 📋 Configuration Parameters

### FilteringConfig (Updated)

```python
geographic_search_radius_km: int = 200
geographic_mode: str = "local_plus_regional"
max_candidates: int = 300
```

### EnrichmentConfig (Updated)

```python
enable_google_maps: bool = True
enable_apollo_enrichment: bool = True
enable_manual_enrichment: bool = True
auto_enrich_on_missing: bool = False
```

### RuntimeConfig (Updated)

```python
enable_manual_review: bool = False
```

---

## 🔧 Usage Examples

### Example 1: High-Precision Local Search

```python
# In sidebar:
Geographic Scope: local_only
Max Vendors: 50
Manual Review: Enabled

# Use Case: Municipal procurement with strict local requirements
```

### Example 2: National Search with Large Result Set

```python
# In sidebar:
Geographic Scope: national
Max Vendors: 1000
Auto-Enrich Missing Contacts: Enabled

# Use Case: Federal contract with nationwide eligibility
```

### Example 3: Custom Radius Search

```python
# In sidebar:
Geographic Scope: custom_radius
Search Radius: 300 km
Max Vendors: 500

# Use Case: Regional contract with specific distance requirements
```

---

## 🚀 Workflow

### Standard Workflow:
1. **Upload Documents** → Select tender files
2. **Configure Settings** → Adjust parameters in sidebar
3. **Run Pipeline** → Process documents
4. **Review Results** → Check vendor matches
5. **Export** → Download results

### Manual Review Workflow:
1. **Upload Documents** → Select tender files
2. **Enable Manual Review** → Check "Enable Manual Review" in sidebar
3. **Run Pipeline** → Initial extraction
4. **Edit Extraction** → Go to "Extracted Data" → "Edit Extraction"
5. **Correct Values** → Fix NAICS, location, set-asides
6. **Re-run Pipeline** → Apply changes
7. **Enrich Contacts** → Use "Manual Enrichment" tab for missing contacts
8. **Export** → Download final results

---

## 🔍 API Keys Required

### Required:
- **OPENAI_API_KEY**: For LLM extraction and profiling

### Optional (for enrichment):
- **GOOGLE_MAPS_API_KEY**: For Google Maps contact enrichment
- **APOLLO_API_KEY**: For Apollo contact enrichment

### Status Display:
Check sidebar "🔑 API Keys Status" section to see which keys are configured.

---

## 🐛 Troubleshooting

### Issue: Enrichment buttons show "Integration in progress"
**Solution**: API integration modules need to be enabled. Check that:
- API keys are set in environment variables
- GoogleMapsProvider and ApolloProvider are properly initialized

### Issue: Extraction editor changes not applied
**Solution**: After saving changes, click "🚀 Run Pipeline" again to re-process with new values

### Issue: Too many/too few vendors
**Solution**: Adjust "Max Vendors to Return" slider in sidebar (50-1000 range)

### Issue: Only local vendors returned
**Solution**: Change "Geographic Scope" from "local_only" to "local_plus_regional" or "national"

---

## 📚 Related Documentation

- [Dashboard Guide](./DASHBOARD_GUIDE.md) - Basic dashboard usage
- [Pipeline Workflow](./PIPELINE_WORKFLOW.md) - Understanding the pipeline
- [Contact Enrichment](./CONTACT_ENRICHMENT.md) - Enrichment providers
- [Architecture](./ARCHITECTURE.md) - System architecture

---

## 🔮 Future Enhancements

### Planned Features:
- Real-time enrichment API integration
- Bulk upload for manual contact data
- Advanced filtering (by revenue, employee count, certifications)
- Custom scoring weights configuration
- A/B testing different configurations
- Export to CRM systems
- Email campaign integration

---

## 💡 Best Practices

1. **Start with defaults**: Use default settings first, then adjust based on results
2. **Enable manual review for critical contracts**: High-value contracts benefit from human review
3. **Use custom radius for regional contracts**: Set exact distance requirements
4. **Enrich missing contacts immediately**: Don't wait - enrich while results are fresh
5. **Export results frequently**: Save intermediate results before making changes
6. **Monitor API usage**: Track API costs in OpenAI/Google/Apollo dashboards

---

## 📊 Performance Tips

- **Use gpt-5-mini** for initial testing (faster, cheaper)
- **Enable Flex Tier** for cost savings on production runs
- **Limit max vendors** to 300-500 for faster processing
- **Batch enrich** instead of individual enrichment for efficiency
- **Cache results** by saving artifacts to session state

---

## 🎯 Configuration Presets

### Preset 1: Quick Test
```
Model: gpt-5-mini
Geographic Scope: local_only
Max Vendors: 50
Auto-Enrich: No
```

### Preset 2: Production Run
```
Model: gpt-5.1
Geographic Scope: local_plus_regional
Max Vendors: 300
Auto-Enrich: Yes
Manual Review: Yes
```

### Preset 3: Comprehensive Search
```
Model: gpt-5.1
Geographic Scope: national
Max Vendors: 1000
Auto-Enrich: Yes
```

---

For questions or feature requests, please refer to the main [README.md](../README.md)

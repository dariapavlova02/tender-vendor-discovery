"""Streamlit Dashboard for Tender AI Agent Observability."""
from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
except ImportError:
    raise ImportError("Streamlit not installed. Run: poetry add streamlit")

try:
    import pandas as pd
except ImportError:
    pd = None

from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.models import PipelineArtifacts, TenderSection
from vendor_ai_agent.pipeline import TenderVendorPipeline
from vendor_ai_agent.modules.document_processing.classifier import DocumentClassifier
from vendor_ai_agent.modules.manual_enrichment import ManualEnrichmentService
from vendor_ai_agent.auth import check_authentication, add_logout_button

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
for handler in logging.root.handlers:
    if isinstance(handler, logging.StreamHandler) and hasattr(handler.stream, 'reconfigure'):
        try:
            handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, TypeError):
            pass

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Tender AI Agent Monitor",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

check_authentication()

st.title("Tender Vendor AI Dashboard")
st.markdown("Run the discovery pipeline, review extracted data, and export vendor shortlists.")
add_logout_button()


def render_config_sidebar() -> RuntimeConfig:
    with st.sidebar:
        st.header("Run Configuration")
        st.caption(
            "Choose how detailed the analysis should be. Standard mode balances speed and accuracy."
        )

        config = RuntimeConfig()
        use_presets = st.checkbox(
            "Use analysis presets",
            value=True,
            help="Recommended for most users: keeps a safe mix of speed and accuracy without tweaking every option manually.",
        )
        if use_presets:
            mode = st.radio(
                "Analysis mode",
                ["Standard", "Quick scan", "Detailed"],
                index=0,
                help=(
                    "Quick scan = fastest (no web scrape/LLM). Standard = balanced. Detailed = slowest but captures every website/contact and runs LLM scoring."
                ),
            )
            if mode == "Standard":
                config.capability_matching.enable_llm_assessment = True
                config.enrichment.enable_website_search = True
                config.enrichment.enable_contact_scraping = True
            elif mode == "Quick scan":
                config.capability_matching.enable_llm_assessment = False
                config.enrichment.enable_website_search = False
                config.enrichment.enable_contact_scraping = False
            else:  # Detailed
                config.capability_matching.enable_llm_assessment = True
                config.enrichment.enable_website_search = True
                config.enrichment.enable_contact_scraping = True
                config.capability_matching.llm_parallelism = 8

        max_results = st.slider(
            "Maximum vendors to analyze",
            min_value=100,
            max_value=1000,
            step=50,
            value=config.filtering.max_candidates,
            help="Upper limit for how many companies we pull through enrichment + scoring. Larger values increase run time and API spend.",
        )
        config.filtering.max_candidates = max_results
        config.discovery.target_results = max_results

        max_govt_pct = st.slider(
            "Max Government Source %",
            min_value=0,
            max_value=100,
            step=5,
            value=int(config.discovery.max_government_source_percentage * 100),
            help="Maximum percentage of vendors from SAM.gov/Canada databases. If government sources exceed this limit, they will be cut. Remaining slots filled by web search (Serper/Apollo).",
        )
        config.discovery.max_government_source_percentage = max_govt_pct / 100

        use_places_api = st.checkbox(
            "Use Serper Places API (recommended)",
            value=config.discovery.serper_use_places_api,
            help="Places API provides phone numbers, ratings, and coordinates directly. Disable to use regular Search API for broader web results.",
        )
        config.discovery.serper_use_places_api = use_places_api

        serper_max_queries = st.number_input(
            "Max Serper Queries",
            min_value=10,
            max_value=500,
            step=10,
            value=config.discovery.serper_max_queries,
            help="Maximum number of Serper API queries to make when searching for vendors. Higher values = more results but higher API costs.",
        )
        config.discovery.serper_max_queries = int(serper_max_queries)

        with st.expander("Batch processing", expanded=False):
            batch_size = st.number_input(
                "Vendors per batch",
                min_value=100,
                max_value=2000,
                step=50,
                value=config.discovery.batch_size,
                help="Controls how many vendors are enriched/scored per batch before pausing—useful for multi-thousand vendor runs.",
            )
            processing_batch = st.number_input(
                "Batch number",
                min_value=1,
                value=config.discovery.processing_batch,
                help="Start from the Nth batch of cached vendors (Batch 2 continues where Batch 1 stopped).",
            )
            use_cache = st.checkbox(
                "Reuse cached vendors between runs",
                value=config.discovery.enable_batch_cache,
                help="Stores discovered vendors on disk so subsequent batches can skip re-discovery and pick up instantly.",
            )
            config.discovery.batch_size = int(batch_size)
            config.discovery.processing_batch = int(processing_batch)
            config.discovery.enable_batch_cache = use_cache

        auto_ingest = st.checkbox(
            "Fetch attachments from SAM/Canada when identifiers are found",
            value=config.enable_auto_ingestion,
            help="If the tender mentions a SAM/Canada reference number, automatically pull the official files before we parse anything.",
        )
        config.enable_auto_ingestion = auto_ingest

        manual_review = st.checkbox(
            "Open extraction editor before filtering",
            value=config.enable_manual_review,
            help="Pause after extraction so you can correct location/NAICS fields prior to vendor discovery—handy for messy PDFs.",
        )
        config.enable_manual_review = manual_review

        if config.apollo_api_key:
            apollo_boost = st.checkbox(
                "Use Apollo booster when vendor count is low",
                value=config.discovery.enable_apollo_booster,
                help="If discovery yields too few vendors, run an Apollo search to top up the list (consumes Apollo credits).",
            )
            config.discovery.enable_apollo_booster = apollo_boost
        else:
            config.discovery.enable_apollo_booster = False

        st.subheader("API keys")
        st.write(
            f"OpenAI: {'available' if config.openai_api_key else 'missing'}"
        )
        st.write(f"Apollo: {'available' if config.apollo_api_key else 'missing'}")

        return config


def extract_zip(zip_path: Path, extract_dir: Path) -> List[Path]:
    """Extract all relevant files from a ZIP archive."""
    extracted_files = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.filelist:
            if file_info.is_dir():
                continue
            
            try:
                file_name = Path(file_info.filename).name
            except (UnicodeDecodeError, ValueError):
                try:
                    file_name = Path(file_info.filename.encode('cp437').decode('utf-8', errors='replace')).name
                except Exception:
                    logger.warning("Skipping file with invalid encoding in filename")
                    continue
            
            if file_name.startswith('.') or file_name.startswith('__MACOSX'):
                continue
            
            suffix = Path(file_name).suffix.lower()
            if suffix in {'.pdf', '.docx', '.xlsx', '.xls', '.doc'}:
                extracted_path = extract_dir / file_name
                
                if extracted_path.exists():
                    base = extracted_path.stem
                    suffix = extracted_path.suffix
                    counter = 1
                    while extracted_path.exists():
                        extracted_path = extract_dir / f"{base}_{counter}{suffix}"
                        counter += 1
                
                try:
                    with zip_ref.open(file_info.filename) as source, open(extracted_path, 'wb') as target:
                        target.write(source.read())
                    
                    extracted_files.append(extracted_path)
                    logger.info("Extracted: %s", extracted_path.name)
                except Exception as e:
                    logger.warning("Failed to extract %s: %s", file_name, str(e))
                    continue
    
    return extracted_files


def filter_relevant_documents(files: List[Path]) -> List[Path]:
    """Filter out non-content files (forms, tiny files, drafts)."""
    EXCLUDE_PATTERNS = [
        r'bid\s*form', r'price\s*sheet', r'signature\s*page',
        r'cover\s*page', r'payment\s*form', r'submittal\s*form',
        r'clin\s*pricing\s*list', r'pricing\s*list\s*only',
        r'draft', r'old', r'previous', r'superseded'
    ]
    
    MIN_CONTENT_SIZE = 50_000
    
    relevant = []
    
    for file in files:
        if file.suffix.lower() not in ['.pdf', '.docx', '.doc']:
            continue
        
        name_lower = file.name.lower()
        size = file.stat().st_size
        
        if size < MIN_CONTENT_SIZE:
            continue
        
        excluded = False
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, name_lower):
                if 'pricing' in pattern and size > 500_000:
                    continue
                excluded = True
                break
        
        if excluded:
            continue
        
        relevant.append(file)
    
    return relevant


def select_documents_for_processing(files: List[Path]) -> tuple[List[Path], dict]:
    """Select and prioritize documents for comprehensive extraction.
    
    Returns:
        - List of documents in priority order
        - Metadata dict with stats for UI
    """
    if not files:
        return [], {'total_files': 0, 'relevant_files': 0, 'excluded_files': 0, 'selected_files': 0, 'by_type': {}}
    
    relevant = filter_relevant_documents(files)
    
    if not relevant:
        relevant = [max(files, key=lambda f: f.stat().st_size if f.suffix.lower() == '.pdf' else 0)]
    
    classifier = DocumentClassifier()
    classified = [classifier.classify(f) for f in relevant]
    
    classified.sort(key=lambda x: x.priority_score, reverse=True)
    
    stats = {
        'total_files': len(files),
        'relevant_files': len(relevant),
        'excluded_files': len(files) - len(relevant),
        'selected_files': len(classified),
        'by_type': {}
    }
    
    for doc in classified:
        doc_type = doc.doc_type.value
        stats['by_type'][doc_type] = stats['by_type'].get(doc_type, 0) + 1
    
    selected_paths = [doc.path for doc in classified]
    
    return selected_paths, stats


def save_uploaded_files(uploaded_files) -> List[Path]:
    temp_dir = Path("data/temp_upload")
    temp_dir.mkdir(exist_ok=True)
    
    file_paths = []
    for uploaded_file in uploaded_files:
        path = temp_dir / uploaded_file.name
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        if path.suffix.lower() == '.zip':
            logger.info("Extracting ZIP archive: %s", path.name)
            extracted = extract_zip(path, temp_dir)
            file_paths.extend(extracted)
            logger.info("Extracted %d files from %s", len(extracted), path.name)
        else:
            file_paths.append(path)
    
    return file_paths


def render_overview_tab(artifacts: PipelineArtifacts):
    st.subheader("📊 Pipeline Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Sections", len(artifacts.tender_sections))
    
    with col2:
        sector = artifacts.tender_profile.dynamic_context.sector or "Unknown"
        st.metric("Detected Sector", sector)
    
    with col3:
        st.metric("Vendors Discovered", len(artifacts.raw_vendors))
    
    with col4:
        st.metric("Final Matches", len(artifacts.final_matches))
    
    st.divider()
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 🎯 Technical Keywords")
        keywords = artifacts.tender_profile.dynamic_context.technical_keywords
        if keywords:
            for kw in keywords[:15]:
                st.markdown(f"- `{kw}`")
            if len(keywords) > 15:
                st.caption(f"... and {len(keywords) - 15} more")
        else:
            st.info("No keywords extracted")
    
    with col_right:
        st.markdown("### 🔍 Search Terms")
        search_terms = artifacts.tender_profile.dynamic_context.search_terms
        if search_terms:
            for term in search_terms[:15]:
                st.markdown(f"- `{term}`")
            if len(search_terms) > 15:
                st.caption(f"... and {len(search_terms) - 15} more")
        else:
            st.info("No search terms generated")


def render_extraction_tab(artifacts: PipelineArtifacts):
    st.subheader("🧠 Extracted Structured Data")
    
    structured = artifacts.tender_profile.doc_extracted.structured
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Basic Info", "📦 Requirements", "✏️ Edit Extraction", "🔢 Raw JSON"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Reference Numbers**")
            st.text(f"Solicitation: {structured.solicitation_number or 'N/A'}")
            st.text(f"Reference: {structured.reference_number or 'N/A'}")
            
            st.markdown("**Location**")
            location = structured.location
            if location.city or location.state_province:
                st.text(f"{location.city or ''}, {location.state_province or ''}")
                st.text(f"{location.country or ''}")
            else:
                st.info("No location data")
        
        with col2:
            st.markdown("**Contact Info**")
            contact = structured.contact_info
            if contact.name or contact.email:
                st.text(f"Name: {contact.name or 'N/A'}")
                st.text(f"Email: {contact.email or 'N/A'}")
                st.text(f"Phone: {contact.phone or 'N/A'}")
            else:
                st.info("No contact data")
    
    with tab2:
        st.markdown("**📦 Volume Items**")
        if structured.volumes:
            volume_data = []
            for vol in structured.volumes[:20]:
                volume_data.append({
                    "Item": vol.item,
                    "Quantity": vol.quantity or "N/A",
                    "Unit": vol.unit or "N/A"
                })
            if pd:
                st.dataframe(pd.DataFrame(volume_data), width="stretch")
            else:
                st.json(volume_data)
        else:
            st.info("No volume items extracted")
        
        st.markdown("**🎓 Required Certifications**")
        if structured.required_certifications:
            for cert in structured.required_certifications:
                st.markdown(f"- {cert}")
        else:
            st.info("No certifications specified")
        
        st.markdown("**📜 Required Licenses**")
        if structured.required_licenses:
            for lic in structured.required_licenses:
                st.markdown(f"- {lic}")
        else:
            st.info("No licenses specified")
    
    with tab3:
        render_extraction_editor(artifacts)
    
    with tab4:
        structured_dict = _dataclass_to_dict(structured)
        st.json(structured_dict)


def render_extraction_editor(artifacts: PipelineArtifacts):
    st.markdown("### ✏️ Edit Extracted Data")
    st.info("Modify extracted values before proceeding with vendor search")
    
    structured = artifacts.tender_profile.doc_extracted.structured
    
    with st.form("extraction_editor"):
        st.markdown("**📍 Location**")
        col1, col2, col3 = st.columns(3)
        with col1:
            city = st.text_input("City", value=structured.location.city or "")
        with col2:
            state = st.text_input("State/Province", value=structured.location.state_province or "")
        with col3:
            country = st.text_input("Country", value=structured.location.country or "")
        
        st.divider()
        
        st.markdown("**🏷️ NAICS Codes**")
        naics_str = ", ".join(structured.naics_codes or [])
        naics_input = st.text_area(
            "NAICS Codes (comma-separated)",
            value=naics_str,
            help="Enter NAICS codes separated by commas"
        )
        
        
        submit_button = st.form_submit_button("💾 Save Changes & Re-run Pipeline")
        
        if submit_button:
            st.success("Changes saved! Click 'Run Pipeline' again to apply changes.")
            st.session_state['edited_extraction'] = {
                'city': city,
                'state': state,
                'country': country,
                'naics_codes': [n.strip() for n in naics_input.split(',') if n.strip()]
            }


def render_documents_tab(artifacts: PipelineArtifacts):
    st.subheader("📄 Document Content & Sections")
    
    sections = artifacts.tender_sections
    
    if not sections:
        st.warning("No sections parsed")
        return
    
    st.markdown(f"**Total sections:** {len(sections)}")
    
    section_types = {}
    for sec in sections:
        section_types[sec.section_type] = section_types.get(sec.section_type, 0) + 1
    
    st.markdown("**Section types:**")
    col_list = st.columns(min(4, len(section_types)))
    for idx, (sec_type, count) in enumerate(section_types.items()):
        with col_list[idx % len(col_list)]:
            st.metric(sec_type.upper(), count)
    
    st.divider()
    
    filter_type = st.selectbox(
        "Filter by type",
        ["All"] + list(section_types.keys())
    )
    
    filtered_sections = sections if filter_type == "All" else [
        s for s in sections if s.section_type == filter_type
    ]
    
    for idx, section in enumerate(filtered_sections[:50]):
        with st.expander(
            f"[{section.section_type}] {section.title or 'Untitled'} "
            f"({len(section.content)} chars)",
            expanded=False
        ):
            if section.source_path:
                st.caption(f"Source: {section.source_path.name}")
            
            if section.section_type == "table":
                st.markdown("**Table Content:**")
                st.code(section.content[:2000], language=None)
            else:
                st.markdown(section.content[:3000])
            
            if section.metadata:
                st.caption("Metadata:")
                st.json(section.metadata)
    
    if len(filtered_sections) > 50:
        st.info(f"Showing first 50 of {len(filtered_sections)} sections")


def get_contact_status_icon(vendor):
    has_email = bool(vendor.email)
    has_phone = bool(vendor.phone)
    
    if has_email and has_phone:
        return "✅"
    elif has_email or has_phone:
        return "⚠️"
    else:
        return "❌"


def render_vendors_tab(artifacts: PipelineArtifacts, config: Optional[RuntimeConfig] = None):
    st.subheader("Vendor Discovery & Matching")
    manual_service: Optional[ManualEnrichmentService] = None
    if config and config.apollo_api_key:
        manual_service = ManualEnrichmentService(apollo_api_key=config.apollo_api_key)

    flash_message = st.session_state.pop('apollo_flash', None)
    if flash_message:
        st.success(flash_message)

    batch_caption = (
        f"Batch {artifacts.batch_id}"
        if hasattr(artifacts, "batch_id")
        else "Batch 1"
    )
    processed_caption = (
        ", processed batches: "
        + ", ".join(str(b) for b in (artifacts.processed_batches or []))
        if getattr(artifacts, "processed_batches", [])
        else ""
    )
    st.caption(batch_caption + processed_caption)
    
    tab1, tab2, tab3 = st.tabs(["Selected", "All candidates", "Pipeline stats"])
    
    with tab1:
        if not artifacts.final_matches:
            st.info("No vendor matches generated yet")
            return

        st.markdown(f"**{len(artifacts.final_matches)} matched vendors**")

        if manual_service:
            st.markdown("#### 🔌 Apollo contact enrichment")
            missing_email = [m.vendor for m in artifacts.final_matches if not m.vendor.email]
            missing_phone = [m.vendor for m in artifacts.final_matches if not m.vendor.phone]

            bulk_cols = st.columns(2)
            with bulk_cols[0]:
                label = f"Fetch emails ({len(missing_email)})"
                if st.button(label, type="secondary", disabled=not missing_email):
                    manual_service.batch_enrich_apollo(missing_email)
                    st.session_state['artifacts'] = artifacts
                    st.session_state['apollo_flash'] = "Apollo email enrichment completed"
                    try:
                        st.rerun()
                    except AttributeError:
                        st.experimental_rerun()

            with bulk_cols[1]:
                label = f"Fetch phones ({len(missing_phone)})"
                if st.button(label, type="secondary", disabled=not missing_phone):
                    manual_service.batch_enrich_apollo(missing_phone)
                    st.session_state['artifacts'] = artifacts
                    st.session_state['apollo_flash'] = "Apollo phone enrichment completed"
                    try:
                        st.rerun()
                    except AttributeError:
                        st.experimental_rerun()

            st.caption("Click a specific vendor below to refresh only that record.")
            max_rows = min(25, len(artifacts.final_matches))
            for idx, match in enumerate(artifacts.final_matches[:max_rows]):
                vendor = match.vendor
                cols = st.columns([3, 2, 2, 1.5])
                with cols[0]:
                    st.markdown(f"**{vendor.company_name}**")
                    st.caption(vendor.location or "Location unknown")
                with cols[1]:
                    st.markdown(f"Email: {vendor.email or '—'}")
                with cols[2]:
                    st.markdown(f"Phone: {vendor.phone or '—'}")
                with cols[3]:
                    already_enriched = bool(vendor.filtering_metadata.get("apollo_enriched"))
                    button_label = "Re-fetch" if already_enriched else "Fetch contacts"
                    disabled = False
                    if not vendor.company_name:
                        disabled = True
                    if st.button(
                        button_label,
                        key=f"apollo_enrich_{idx}_{vendor.company_name}",
                        help="Uses Apollo credits for a single vendor lookup.",
                        disabled=disabled,
                    ):
                        manual_service.enrich_single_vendor_apollo(vendor)
                        st.session_state['artifacts'] = artifacts
                        st.session_state['apollo_flash'] = f"Apollo contacts refreshed for {vendor.company_name}."
                        try:
                            st.rerun()
                        except AttributeError:
                            st.experimental_rerun()

        match_data = []
        for match in artifacts.final_matches[:100]:
            vendor = match.vendor
            match_data.append({
                "Status": vendor.filtering_metadata.get("match_status", "selected").title(),
                "Batch": vendor.filtering_metadata.get("batch", 1),
                "Reason": vendor.filtering_metadata.get("match_reason", ""),
                "Company": vendor.company_name,
                "Score": f"{match.capability_match_score:.2f}",
                "Location": vendor.location or "N/A",
                "Website": vendor.website or "N/A",
                "Email": vendor.email or "",
                "Phone": vendor.phone or "",
                "Source": vendor.source or "N/A",
                "Past Winner": "yes" if vendor.is_past_winner else "no",
            })
        
        if pd:
            df = pd.DataFrame(match_data)
            st.dataframe(df, width="stretch", hide_index=True)
            
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv_data,
                file_name="vendor_matches.csv",
                mime="text/csv"
            )
        else:
            st.json(match_data)
        
        st.divider()
        st.markdown("**Match Details**")
        
        for match in artifacts.final_matches[:10]:
            with st.expander(f"{match.vendor.company_name} — Score: {match.capability_match_score:.2f}"):
                st.markdown(f"**Rationale:** {match.rationale}")
                if match.references:
                    st.markdown("**References:**")
                    for ref in match.references:
                        st.markdown(f"- {ref}")
    
    with tab2:
        all_matches = artifacts.all_matches or artifacts.final_matches
        if not all_matches:
            st.info("No scored vendors yet")
            return

        st.markdown(f"**{len(all_matches)} vendors scored**")
        
        rows = []
        for match in all_matches:
            vendor = match.vendor
            rows.append({
                "Status": vendor.filtering_metadata.get("match_status", "needs_review").title(),
                "Batch": vendor.filtering_metadata.get("batch", 1),
                "Reason": vendor.filtering_metadata.get("match_reason", ""),
                "Company": vendor.company_name,
                "Score": match.capability_match_score,
                "Location": vendor.location or "N/A",
                "Website": vendor.website or "N/A",
                "Email": vendor.email or "",
                "Phone": vendor.phone or "",
                "Source": vendor.source or "N/A",
            })

        if pd:
            df = pd.DataFrame(rows)
            st.dataframe(df, width="stretch", hide_index=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download full candidate list",
                data=csv,
                file_name="vendor_candidates.csv",
                mime="text/csv",
            )
        else:
            st.json(rows)
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Raw Vendors", len(artifacts.raw_vendors))
            st.metric("After Enrichment", len(artifacts.enriched_vendors))
            st.metric("Final Matches", len(artifacts.final_matches))
            st.metric("Scored Candidates", len(artifacts.all_matches or []))
        
        with col2:
            if artifacts.final_matches:
                avg_score = sum(m.capability_match_score for m in artifacts.final_matches) / len(artifacts.final_matches)
                st.metric("Avg Match Score", f"{avg_score:.2f}")
                
                past_winners = sum(1 for m in artifacts.final_matches if m.vendor.is_past_winner)
                st.metric("Past Winners", past_winners)
                
                vendors_with_matches = [m.vendor for m in artifacts.final_matches]
                missing_contacts = sum(
                    1 for v in vendors_with_matches 
                    if not v.email and not v.phone
                )
                st.metric("Missing Contacts", missing_contacts)


def render_debug_tab(artifacts: PipelineArtifacts):
    st.subheader("🐛 Debug & Raw Data")
    
    tab1, tab2, tab3 = st.tabs(["🧬 Full Profile", "📡 API Metadata", "⚡ Dynamic Context"])
    
    with tab1:
        profile_dict = _dataclass_to_dict(artifacts.tender_profile)
        st.json(profile_dict)
    
    with tab2:
        api_meta_dict = _dataclass_to_dict(artifacts.tender_profile.api_metadata)
        st.json(api_meta_dict)
    
    with tab3:
        context_dict = _dataclass_to_dict(artifacts.tender_profile.dynamic_context)
        st.json(context_dict)


def _dataclass_to_dict(obj):
    if hasattr(obj, '__dict__'):
        result = {}
        for key, value in obj.__dict__.items():
            if hasattr(value, '__dict__'):
                result[key] = _dataclass_to_dict(value)
            elif isinstance(value, list):
                result[key] = [_dataclass_to_dict(item) if hasattr(item, '__dict__') else item for item in value]
            elif isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result
    return obj


def render_pipeline_results(
    artifacts: PipelineArtifacts,
    config: RuntimeConfig,
    *,
    pipeline: Optional[TenderVendorPipeline] = None,
    cached_run: bool = False,
) -> None:
    """Render the full dashboard + export controls for a finished run."""
    if cached_run:
        st.info(
            "Showing results from the last completed run. Click 'Run Pipeline' to refresh, "
            "or use the reset button below to start over."
        )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Overview", "Extracted Data", "Document Content", "Vendors", "Debug"]
    )

    with tab1:
        render_overview_tab(artifacts)

    with tab2:
        render_extraction_tab(artifacts)

    with tab3:
        render_documents_tab(artifacts)

    with tab4:
        render_vendors_tab(artifacts, config)

    with tab5:
        render_debug_tab(artifacts)

    st.divider()
    st.markdown("### 📤 Export Results")

    match_rows = []
    matches_df = None
    if pd and artifacts.final_matches:
        for match in artifacts.final_matches:
            match_rows.append({
                "Company": match.vendor.company_name,
                "Score": match.capability_match_score,
                "Email": match.vendor.email or "",
                "Phone": match.vendor.phone or "",
                "Website": match.vendor.website or "",
                "Location": match.vendor.location or "",
                "Rationale": match.rationale,
            })
        matches_df = pd.DataFrame(match_rows)

    col_exp1, col_exp2, col_exp3 = st.columns(3)

    with col_exp1:
        if matches_df is not None:
            csv_bytes = matches_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV",
                data=csv_bytes,
                file_name="vendor_matches.csv",
                mime="text/csv",
            )
        else:
            st.info("CSV export available after matches are generated.")

    with col_exp2:
        if matches_df is not None:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                matches_df.to_excel(writer, index=False, sheet_name="Matches")
            st.download_button(
                label="📊 Download Excel",
                data=excel_buffer.getvalue(),
                file_name="vendor_matches.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("Excel export available after matches are generated.")

    with col_exp3:
        if st.button("📂 Save to outputs", type="secondary"):
            try:
                output_dir = Path("outputs")
                output_dir.mkdir(exist_ok=True)
                pipeline_to_use = pipeline or TenderVendorPipeline(config)
                pipeline_to_use.save_outputs(artifacts.final_matches, directory=output_dir)
                st.success("✅ Results saved to outputs/ directory")
            except Exception as e:
                st.error(f"Export failed: {e}")

def apply_extraction_edits(profile):
    edited_data = st.session_state.get('edited_extraction')
    
    if not edited_data:
        return profile, []
    
    structured = profile.doc_extracted.structured
    changes = []
    
    if edited_data.get('city') is not None and edited_data['city'] != structured.location.city:
        old_val = structured.location.city or '(empty)'
        structured.location.city = edited_data['city']
        changes.append(f"📍 City: {old_val} → {edited_data['city']}")
    
    if edited_data.get('state') is not None and edited_data['state'] != structured.location.state_province:
        old_val = structured.location.state_province or '(empty)'
        structured.location.state_province = edited_data['state']
        changes.append(f"📍 State: {old_val} → {edited_data['state']}")
    
    if edited_data.get('country') is not None and edited_data['country'] != structured.location.country:
        old_val = structured.location.country or '(empty)'
        structured.location.country = edited_data['country']
        changes.append(f"📍 Country: {old_val} → {edited_data['country']}")
    
    if edited_data.get('naics_codes') is not None:
        old_codes = set(structured.naics_codes or [])
        new_codes = set(edited_data['naics_codes'])
        if old_codes != new_codes:
            structured.naics_codes = edited_data['naics_codes']
            changes.append(f"🏷️ NAICS: {', '.join(old_codes or ['(empty)'])} → {', '.join(new_codes)}")
    
    return profile, changes


def main():
    config = render_config_sidebar()
    
    st.markdown("### 📤 Upload Tender Documents")
    
    uploaded_files = st.file_uploader(
        "Select PDF, DOCX, or Excel files",
        accept_multiple_files=True,
        type=["pdf", "docx", "xlsx", "xls"]
    )
    
    if not uploaded_files:
        st.info("👆 Upload tender documents to start processing")
        return
    
    all_file_paths = save_uploaded_files(uploaded_files)
    
    if len(all_file_paths) > 1:
        st.markdown("### 📂 Document Selection")
        selected_files, stats = select_documents_for_processing(all_file_paths)
        
        st.info(f"📑 **Processing {stats['selected_files']} of {stats['total_files']} documents**\n\n"
                f"Multi-document processing enabled: extracting comprehensive requirements from all relevant tender documents.")
        
        if stats['by_type']:
            st.markdown("**Document Breakdown:**")
            type_mapping = {
                'CORE_RFP': '📘 Core RFP',
                'TECH_AMENDMENT': '📝 Technical Amendments',
                'ADDENDUM': '📋 Addenda',
                'APPENDIX': '📊 Appendices',
                'SOW': '📄 Statement of Work',
                'PRESENTATION': '📊 Presentations',
                'UNKNOWN': '📎 Other Documents'
            }
            for doc_type, count in stats['by_type'].items():
                display_name = type_mapping.get(doc_type, doc_type)
                st.markdown(f"  - {display_name}: {count}")
        
        with st.expander(f"View selected files ({len(selected_files)})"):
            for fp in selected_files:
                st.markdown(f"📄 `{fp.name}` ({fp.stat().st_size // 1024} KB)")
        
        if stats['excluded_files'] > 0:
            with st.expander(f"View excluded files ({stats['excluded_files']})"):
                all_selected_names = {fp.name for fp in selected_files}
                for fp in all_file_paths:
                    if fp.name not in all_selected_names:
                        st.markdown(f"📎 `{fp.name}` ({fp.stat().st_size // 1024} KB)")
    else:
        selected_files = all_file_paths
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_button = st.button("🚀 Run Pipeline", type="primary", width="stretch")

    cached_artifacts = st.session_state.get('artifacts')
    cached_config = st.session_state.get('config') or config

    if not run_button:
        if cached_artifacts:
            st.markdown("### 🔁 Last Run Results")
            if st.button("🧹 Clear cached results", type="secondary"):
                st.session_state.pop('artifacts', None)
                st.session_state.pop('config', None)
                st.info("Cached results cleared. Upload documents and click 'Run Pipeline' to start a new analysis.")
                return
            render_pipeline_results(
                cached_artifacts,
                cached_config,
                cached_run=True,
            )
        return
    
    try:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        status_text.text("🔧 Initializing pipeline...")
        pipeline = TenderVendorPipeline(config)
        progress_bar.progress(20)
        
        status_text.text("📄 Parsing documents...")
        progress_bar.progress(30)
        
        status_text.text("🧠 Extracting requirements & profiling...")
        progress_bar.progress(50)
        
        status_text.text("🔍 Discovering & enriching vendors...")
        progress_bar.progress(70)
        
        try:
            artifacts = pipeline.run(selected_files, disable_auto_ingestion=not config.enable_auto_ingestion)
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error("🚨 **Vendor Discovery Failed - API Unavailable**")
            st.error(f"**Error:** {str(e)}")
            st.warning("**Please try again later.** The external vendor API (SAM.gov or SBA) is currently unavailable.")
            st.stop()
        
        _, changes_applied = apply_extraction_edits(artifacts.tender_profile)
        if changes_applied:
            st.info("🔄 **Manual edits detected - re-running pipeline with updated extraction data:**")
            for change in changes_applied:
                st.markdown(f"  - {change}")
            
            status_text.text("🔍 Re-discovering & filtering vendors with updated data...")
            progress_bar.progress(50)
            
            try:
                discovered_vendors = pipeline.context.vendor_discovery.discover(artifacts.tender_profile)
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error("🚨 **Vendor Discovery Failed - API Unavailable**")
                st.error(f"**Error:** {str(e)}")
                st.warning("**Please try again later.** The external vendor API (SAM.gov or SBA) is currently unavailable.")
                st.stop()
            filtered_vendors = pipeline.context.vendor_filter.filter(artifacts.tender_profile, discovered_vendors)
            filtering_metrics = pipeline.context.vendor_filter.get_metrics()
            enriched_vendors = pipeline.context.vendor_enricher.enrich(filtered_vendors)
            matches = pipeline.context.capability_matcher.score(artifacts.tender_profile, enriched_vendors)
            
            from vendor_ai_agent.models import PipelineArtifacts as PA
            artifacts = PA(
                tender_sections=artifacts.tender_sections,
                tender_profile=artifacts.tender_profile,
                raw_vendors=discovered_vendors,
                enriched_vendors=enriched_vendors,
                filtered_vendors=filtered_vendors,
                filtering_metrics=filtering_metrics,
                final_matches=matches,
            )
            
            st.session_state.pop('edited_extraction', None)
        
        progress_bar.progress(100)
        status_text.text("✅ Pipeline completed successfully!")
        
        st.success("✅ Pipeline execution completed!")
        
        if config.enable_manual_review:
            st.info("💡 Manual review mode enabled. Check the 'Extracted Data' tab to edit values before re-running.")

        st.session_state['artifacts'] = artifacts
        st.session_state['config'] = config

        render_pipeline_results(
            artifacts,
            config,
            pipeline=pipeline,
        )
        
    except Exception as exc:
        st.error(f"❌ Pipeline failed: {exc}")
        logger.exception("Pipeline execution failed")
        st.exception(exc)


if __name__ == "__main__":
    main()

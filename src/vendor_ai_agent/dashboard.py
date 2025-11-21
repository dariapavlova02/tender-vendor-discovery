"""Streamlit Dashboard for Tender AI Agent Observability."""
from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import List, Optional

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Tender AI Agent Monitor",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🕵️ Tender AI Agent — Control Center")
st.markdown("**Observability Dashboard** for end-to-end pipeline inspection")


def render_config_sidebar() -> RuntimeConfig:
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        model = st.selectbox(
            "LLM Model",
            ["gpt-5-mini", "gpt-5.1", "gpt-4o-mini"],
            index=0,
            help="Select model for extraction and profiling"
        )
        
        use_flex = st.checkbox(
            "Use Flex Tier",
            value=True,
            help="Enable OpenAI Flex tier pricing"
        )
        
        auto_ingest = st.checkbox(
            "Auto Ingestion",
            value=False,
            help="Automatically fetch attachments from source APIs"
        )
        
        st.divider()
        st.caption("OpenAI API Key")
        api_key_status = "✅ Set" if RuntimeConfig().openai_api_key else "❌ Missing"
        st.info(api_key_status)
        
        config = RuntimeConfig()
        config.llm.cheap_model = model
        config.llm.use_flex_tier = use_flex
        config.enable_auto_ingestion = auto_ingest
        
        return config


def save_uploaded_files(uploaded_files) -> List[Path]:
    temp_dir = Path("temp_upload")
    temp_dir.mkdir(exist_ok=True)
    
    file_paths = []
    for uploaded_file in uploaded_files:
        path = temp_dir / uploaded_file.name
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        file_paths.append(path)
    
    return file_paths


def render_overview_tab(artifacts: PipelineArtifacts):
    st.subheader("📊 Pipeline Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Sections", len(artifacts.tender_sections))
    
    with col2:
        sector = artifacts.tender_profile.doc_extracted.structured.sector or "Unknown"
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
    
    tab1, tab2, tab3 = st.tabs(["📋 Basic Info", "📦 Requirements", "🔢 Raw JSON"])
    
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
                st.dataframe(pd.DataFrame(volume_data), use_container_width=True)
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
        structured_dict = _dataclass_to_dict(structured)
        st.json(structured_dict)


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


def render_vendors_tab(artifacts: PipelineArtifacts):
    st.subheader("🏢 Vendor Discovery & Matching")
    
    tab1, tab2, tab3 = st.tabs(["🎯 Final Matches", "🔍 All Discovered", "📊 Stats"])
    
    with tab1:
        if not artifacts.final_matches:
            st.info("No vendor matches generated yet")
            return
        
        st.markdown(f"**{len(artifacts.final_matches)} matched vendors**")
        
        match_data = []
        for match in artifacts.final_matches[:100]:
            match_data.append({
                "Company": match.vendor.company_name,
                "Score": f"{match.capability_match_score:.2f}",
                "Location": match.vendor.location or "N/A",
                "Industry": match.vendor.industry or "N/A",
                "Website": match.vendor.website or "N/A",
                "Email": match.vendor.email or "N/A",
                "Source": match.vendor.source or "N/A",
                "Past Winner": "✅" if match.vendor.is_past_winner else "❌"
            })
        
        if pd:
            df = pd.DataFrame(match_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
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
        if not artifacts.enriched_vendors:
            st.info("No vendors discovered")
            return
        
        st.markdown(f"**{len(artifacts.enriched_vendors)} vendors after enrichment**")
        
        vendor_data = []
        for vendor in artifacts.enriched_vendors[:100]:
            vendor_data.append({
                "Company": vendor.company_name,
                "Location": vendor.location or "N/A",
                "Industry": vendor.industry or "N/A",
                "Website": vendor.website or "N/A",
                "Source": vendor.source or "N/A"
            })
        
        if pd:
            df = pd.DataFrame(vendor_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.json(vendor_data)
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Raw Vendors", len(artifacts.raw_vendors))
            st.metric("After Enrichment", len(artifacts.enriched_vendors))
            st.metric("Final Matches", len(artifacts.final_matches))
        
        with col2:
            if artifacts.final_matches:
                avg_score = sum(m.capability_match_score for m in artifacts.final_matches) / len(artifacts.final_matches)
                st.metric("Avg Match Score", f"{avg_score:.2f}")
                
                past_winners = sum(1 for m in artifacts.final_matches if m.vendor.is_past_winner)
                st.metric("Past Winners", past_winners)


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
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_button = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)
    
    if not run_button:
        return
    
    try:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        status_text.text("💾 Saving uploaded files...")
        file_paths = save_uploaded_files(uploaded_files)
        progress_bar.progress(10)
        
        status_text.text("🔧 Initializing pipeline...")
        pipeline = TenderVendorPipeline(config)
        progress_bar.progress(20)
        
        status_text.text("📄 Parsing documents...")
        progress_bar.progress(30)
        
        status_text.text("🧠 Extracting requirements & profiling...")
        progress_bar.progress(50)
        
        status_text.text("🔍 Discovering & enriching vendors...")
        progress_bar.progress(70)
        
        artifacts = pipeline.run(file_paths, disable_auto_ingestion=not config.enable_auto_ingestion)
        
        progress_bar.progress(100)
        status_text.text("✅ Pipeline completed successfully!")
        
        st.success("Pipeline execution completed!")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Overview",
            "🧠 Extracted Data",
            "📄 Document Content",
            "🏢 Vendors",
            "🐛 Debug"
        ])
        
        with tab1:
            render_overview_tab(artifacts)
        
        with tab2:
            render_extraction_tab(artifacts)
        
        with tab3:
            render_documents_tab(artifacts)
        
        with tab4:
            render_vendors_tab(artifacts)
        
        with tab5:
            render_debug_tab(artifacts)
        
        st.session_state['artifacts'] = artifacts
        
    except Exception as exc:
        st.error(f"❌ Pipeline failed: {exc}")
        logger.exception("Pipeline execution failed")
        st.exception(exc)


if __name__ == "__main__":
    main()

"""Streamlit Dashboard for Tender Vendor Discovery Observability."""
from __future__ import annotations

import gc
import io
import json
import logging
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from vendor_ai_agent.models import ContactInfo, PipelineArtifacts, TenderSection, VendorMatchResult
from vendor_ai_agent.modules.document_processing.classifier import DocumentClassifier
from vendor_ai_agent.modules.manual_enrichment import ManualEnrichmentService
from vendor_ai_agent.auth import check_authentication, add_logout_button, get_user_email
from vendor_ai_agent.run_cache import (
    RUN_CACHE_DIR,
    RunCacheLoader,
    register_job,
    update_job,
    remove_job,
    get_job_for_email,
    clear_all_jobs,
)

RUN_IDLE_TIMEOUT_SECONDS = int(os.getenv("RUN_IDLE_TIMEOUT_SECONDS", "600"))

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
)
logger = logging.getLogger(__name__)


def _safe_rerun():
    """Safely rerun Streamlit app with fallback for older versions."""
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def _current_user_email() -> str:
    return get_user_email() or "anonymous"


def _load_run_config(run_dir: Path) -> Optional[RuntimeConfig]:
    config_path = run_dir / "config.pkl"
    if not config_path.exists():
        return None
    try:
        with config_path.open("rb") as fh:
            return pickle.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load run config %s: %s", config_path, exc)
    return None

st.set_page_config(
    page_title="Tender Vendor Discovery Monitor",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

check_authentication()

st.title("Tender Vendor AI Dashboard")
st.markdown("Run the discovery pipeline, review extracted data, and export vendor shortlists.")
add_logout_button()


def _matches_to_dataframe(matches: List[VendorMatchResult]) -> pd.DataFrame:
    if not matches or not pd:
        return pd.DataFrame()

    def serialize(match: VendorMatchResult) -> Dict[str, Any]:
        vendor = match.vendor
        primary_contact = vendor.primary_contact or ContactInfo()
        return {
            "company_name": vendor.company_name,
            "website": vendor.website,
            "email": vendor.email,
            "phone": vendor.phone,
            "location": vendor.location,
            "city": vendor.city,
            "state": vendor.state,
            "country": vendor.country,
            "industry": vendor.industry,
            "source": vendor.source,
            "is_past_winner": vendor.is_past_winner,
            "enrichment_flags": json.dumps(vendor.enrichment_flags or []),
            "uei": vendor.uei,
            "duns": vendor.duns,
            "cage_code": vendor.cage_code,
            "business_types": json.dumps(vendor.business_types or []),
            "primary_contact_name": primary_contact.name,
            "primary_contact_email": primary_contact.email,
            "primary_contact_phone": primary_contact.phone,
            "geo_score": vendor.geo_score,
            "preliminary_score": vendor.preliminary_score,
            "filtering_metadata": json.dumps(vendor.filtering_metadata or {}),
            "total_contract_value": vendor.total_contract_value,
            "contract_count": vendor.contract_count,
            "capability_match_score": match.capability_match_score,
            "rationale": match.rationale,
            "references": json.dumps(match.references or []),
        }

    return pd.DataFrame([serialize(m) for m in matches])


def _persist_artifacts_to_disk(artifacts: PipelineArtifacts) -> dict:
    run_meta = st.session_state.get("active_run") or {}
    existing_path = run_meta.get("path")
    if existing_path:
        run_dir = Path(existing_path)
    else:
        run_id = f"run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        run_dir = RUN_CACHE_DIR / run_id
        run_meta["id"] = run_id
        run_meta["job_id"] = run_id
        run_meta["created_at"] = datetime.utcnow().isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)

    df_final = _matches_to_dataframe(artifacts.final_matches)
    if not df_final.empty:
        df_final.to_parquet(run_dir / "final_matches.parquet", index=False)
    df_all = _matches_to_dataframe(artifacts.all_matches or artifacts.final_matches)
    if not df_all.empty:
        df_all.to_parquet(run_dir / "all_matches.parquet", index=False)
    metadata_payload = {
        "tender_sections": artifacts.tender_sections,
        "tender_profile": artifacts.tender_profile,
        "filtering_metrics": artifacts.filtering_metrics,
        "batch_id": getattr(artifacts, "batch_id", 1),
        "processed_batches": getattr(artifacts, "processed_batches", []),
        "raw_vendor_count": len(getattr(artifacts, "raw_vendors", []) or []),
        "enriched_vendor_count": len(getattr(artifacts, "enriched_vendors", []) or []),
        "final_match_count": len(artifacts.final_matches),
        "all_match_count": len(artifacts.all_matches or artifacts.final_matches),
    }
    with (run_dir / "metadata.pkl").open("wb") as fh:
        pickle.dump(metadata_payload, fh)
    run_meta["path"] = str(run_dir)
    run_meta["last_viewed_at"] = datetime.utcnow().isoformat()
    st.session_state["active_run"] = run_meta
    return run_meta


def _overwrite_cached_run(artifacts: PipelineArtifacts) -> None:
    _persist_artifacts_to_disk(artifacts)


def _clear_cached_run(delete_file: bool = True, *, job_id: Optional[str] = None) -> None:
    """Remove cached run metadata and optional file from disk."""
    run_meta = st.session_state.pop("active_run", None)
    if delete_file and run_meta:
        run_path = Path(run_meta.get("path", ""))
        try:
            if run_path.is_file():
                run_path.unlink()
            elif run_path.is_dir():
                shutil.rmtree(run_path, ignore_errors=True)
        except OSError as exc:
            logger.warning("Failed to delete cached run %s: %s", run_path, exc)
    if job_id is None and run_meta:
        job_id = run_meta.get("job_id") or run_meta.get("id")
    if job_id:
        remove_job(job_id)
    st.session_state.pop("config", None)
    st.session_state.pop("apollo_flash", None)
    st.session_state.pop("artifacts", None)
    gc.collect()


def _archive_active_run() -> None:
    run_meta = st.session_state.get("active_run")
    if not run_meta:
        st.info("No run to archive.")
        return
    job_id = run_meta.get("job_id") or run_meta.get("id")
    _clear_cached_run(job_id=job_id)
    st.success("Run archived and cache cleared.")


def _archive_everything() -> None:
    clear_all_jobs()
    for path in RUN_CACHE_DIR.iterdir():
        try:
            if path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass
    st.session_state.clear()
    gc.collect()


def _load_cached_artifacts() -> Optional[PipelineArtifacts]:
    run_meta = st.session_state.get("active_run")
    if not run_meta:
        return None

    run_path = Path(run_meta.get("path", ""))
    if not run_path.exists():
        _clear_cached_run(delete_file=False)
        return None

    if run_path.is_file():
        try:
            with run_path.open("rb") as fh:
                return pickle.load(fh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load cached artifacts %s: %s", run_path, exc)
            _clear_cached_run(delete_file=False)
            return None

    try:
        loader = RunCacheLoader(run_path)
        artifacts = loader.load_metadata()
        artifacts.final_matches = loader.load_final_matches_objects()
        artifacts.all_matches = loader.load_all_matches_objects()
        return artifacts
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load run directory %s: %s", run_path, exc)
        _clear_cached_run(delete_file=False)
        return None


def _mark_run_downloaded(source: str) -> None:
    run_meta = st.session_state.get("active_run")
    if not run_meta:
        return
    timestamp = datetime.utcnow().isoformat()
    run_meta["downloaded_at"] = timestamp
    run_meta["last_viewed_at"] = timestamp
    run_meta["last_download_source"] = source
    st.session_state["active_run"] = run_meta


def _touch_active_run() -> None:
    run_meta = st.session_state.get("active_run")
    if not run_meta:
        return
    run_meta["last_viewed_at"] = datetime.utcnow().isoformat()
    st.session_state["active_run"] = run_meta


def _maybe_cleanup_inactive_run() -> None:
    run_meta = st.session_state.get("active_run")
    if not run_meta:
        return

    downloaded_at = run_meta.get("downloaded_at")
    if not downloaded_at:
        return

    last_view = run_meta.get("last_viewed_at", downloaded_at)
    try:
        last_view_dt = datetime.fromisoformat(last_view)
    except ValueError:
        last_view_dt = datetime.utcnow()

    if datetime.utcnow() - last_view_dt >= timedelta(seconds=RUN_IDLE_TIMEOUT_SECONDS):
        logger.info("Active run expired after %s seconds of inactivity", RUN_IDLE_TIMEOUT_SECONDS)
        _clear_cached_run()


def _materialize_run_artifacts(run_dir: Path) -> PipelineArtifacts:
    loader = RunCacheLoader(run_dir)
    artifacts = loader.load_metadata()
    artifacts.final_matches = loader.load_final_matches_objects()
    artifacts.all_matches = loader.load_all_matches_objects()
    return artifacts


def _render_running_job(job_meta: Dict[str, Any]) -> None:
    st.subheader("🚧 Pipeline job in progress")
    started_at = job_meta.get("started_at", "unknown time")
    st.info(
        f"Job `{job_meta.get('job_id')}` started at {started_at} is still running. "
        "This view will show its output when ready."
    )
    log_path = Path(job_meta.get("log_path", ""))
    if log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as log_file:
                log_text = log_file.read()
        except Exception:
            log_text = ""
        st.markdown("**Worker log:**")
        st.code(log_text[-4000:] or "Waiting for log output...", language="text")
    else:
        st.info("Log file not yet available.")
    if st.button("Refresh job status"):
        try:
            st.rerun()
        except AttributeError:
            _safe_rerun()
    st.stop()


def _render_failed_job(job_meta: Dict[str, Any]) -> None:
    st.subheader("❌ Previous job failed")
    st.error("The last pipeline run ended with an error. Review the log below or clear the job to try again.")
    log_path = Path(job_meta.get("log_path", ""))
    if log_path.exists():
        st.markdown("**Worker log:**")
        try:
            st.code(log_path.read_text(encoding="utf-8")[-4000:], language="text")
        except Exception:
            st.code("Unable to read log.")
    if st.button("🔁 Clear failed job"):
        _clear_cached_run(job_id=job_meta.get("job_id"))
        _safe_rerun()
    st.stop()


def _sync_session_with_completed_job(job_meta: Dict[str, Any], fallback_config: RuntimeConfig) -> None:
    run_dir = Path(job_meta.get("run_dir", ""))
    if not run_dir.exists():
        return
    active_meta = st.session_state.get("active_run")
    if active_meta and active_meta.get("job_id") == job_meta.get("job_id") and st.session_state.get("artifacts"):
        return
    artifacts = _materialize_run_artifacts(run_dir)
    job_config = _load_run_config(run_dir) or fallback_config
    st.session_state["artifacts"] = artifacts
    st.session_state["config"] = job_config
    st.session_state["active_run"] = {
        "id": job_meta.get("job_id"),
        "job_id": job_meta.get("job_id"),
        "path": str(run_dir),
        "created_at": job_meta.get("started_at"),
        "last_viewed_at": datetime.utcnow().isoformat(),
    }


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

        scoring_model = st.selectbox(
            "LLM model for capability scoring",
            options=["gpt-5-mini", "gpt-5.1"],
            index=0 if config.capability_matching.llm_model == "gpt-5-mini" else 1,
            help="Use gpt-5-mini for faster, cheaper scoring or gpt-5.1 for maximum accuracy.",
        )
        config.capability_matching.llm_model = scoring_model

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
            "Use Serper Places API",
            value=False,
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
    from vendor_ai_agent.file_storage import save_uploads
    file_paths = []
    for path in save_uploads(uploaded_files, Path("data/temp_upload")):
        if path.suffix.lower() == '.zip':
            logger.info("Extracting ZIP archive: %s", path.name)
            extracted = extract_zip(path, path.parent)
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
        raw_count = getattr(artifacts, "raw_vendor_count", len(artifacts.raw_vendors))
        st.metric("Vendors Discovered", raw_count)
    
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
                    _overwrite_cached_run(artifacts)
                    st.session_state['apollo_flash'] = "Apollo email enrichment completed"
                    _safe_rerun()

            with bulk_cols[1]:
                label = f"Fetch phones ({len(missing_phone)})"
                if st.button(label, type="secondary", disabled=not missing_phone):
                    manual_service.batch_enrich_apollo(missing_phone)
                    _overwrite_cached_run(artifacts)
                    st.session_state['apollo_flash'] = "Apollo phone enrichment completed"
                    _safe_rerun()

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
                        _overwrite_cached_run(artifacts)
                        st.session_state['apollo_flash'] = f"Apollo contacts refreshed for {vendor.company_name}."
                        _safe_rerun()

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
                mime="text/csv",
                on_click=_mark_run_downloaded,
                kwargs={"source": "vendors_matches_csv"},
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
                on_click=_mark_run_downloaded,
                kwargs={"source": "vendors_candidates_csv"},
            )
        else:
            st.json(rows)
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Raw Vendors", getattr(artifacts, "raw_vendor_count", len(artifacts.raw_vendors)))
            st.metric("After Enrichment", getattr(artifacts, "enriched_vendor_count", len(artifacts.enriched_vendors)))
            st.metric("Final Matches", getattr(artifacts, "final_match_count", len(artifacts.final_matches)))
            st.metric("Scored Candidates", getattr(artifacts, "all_match_count", len(artifacts.all_matches or [])))
        
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
    pipeline: Optional[Any] = None,
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
                on_click=_mark_run_downloaded,
                kwargs={"source": "export_csv"},
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
                on_click=_mark_run_downloaded,
                kwargs={"source": "export_excel"},
            )
        else:
            st.info("Excel export available after matches are generated.")

    with col_exp3:
        if st.button("🗂️ Archive run & clear cache", type="secondary"):
            _archive_active_run()
            _safe_rerun()
        if st.button("❌ Archive ALL runs", type="secondary"):
            _archive_everything()
            _safe_rerun()
def main():
    _maybe_cleanup_inactive_run()
    _touch_active_run()
    config = render_config_sidebar()
    user_email = _current_user_email()
    active_job_meta = get_job_for_email(user_email)

    if active_job_meta:
        status = active_job_meta.get("status")
        if status == "running":
            _render_running_job(active_job_meta)
        elif status == "failed":
            _render_failed_job(active_job_meta)
        elif status == "completed":
            _sync_session_with_completed_job(active_job_meta, config)

    st.markdown("### 📤 Upload Tender Documents")
    with st.expander("Housekeeping", expanded=False):
        if st.button("🗂️ Archive current run", key="archive_current_top"):
            _archive_active_run()
            _safe_rerun()
        if st.button("❌ Archive ALL runs", key="archive_all_top"):
            _archive_everything()
            _safe_rerun()

    uploaded_files = st.file_uploader(
        "Select PDF, DOCX, or Excel files",
        accept_multiple_files=True,
        type=["pdf", "docx", "xlsx", "xls"]
    )

    if not uploaded_files:
        cached_artifacts = st.session_state.get('artifacts')
        cached_config = st.session_state.get('config') or config
        if cached_artifacts:
            st.markdown("### 🔁 Last Run Results")
            if st.button("🧹 Clear cached results", type="secondary"):
                job_id = (active_job_meta or {}).get("job_id")
                _clear_cached_run(job_id=job_id)
                st.info("Cached results cleared. Upload documents and click 'Run Pipeline' to start a new analysis.")
                return
            render_pipeline_results(
                cached_artifacts,
                cached_config,
                cached_run=True,
            )
        else:
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

    cached_artifacts = _load_cached_artifacts()
    cached_config = st.session_state.get('config') or config

    cached_run_active = active_job_meta is not None and active_job_meta.get("status") == "completed"

    if not run_button:
        if cached_artifacts:
            st.markdown("### 🔁 Last Run Results")
            if st.button("🧹 Clear cached results", type="secondary"):
                job_id = (active_job_meta or {}).get("job_id")
                _clear_cached_run(job_id=job_id)
                st.info("Cached results cleared. Upload documents and click 'Run Pipeline' to start a new analysis.")
                return
            render_pipeline_results(
                cached_artifacts,
                cached_config,
                cached_run=cached_run_active,
            )
        return

    if active_job_meta and active_job_meta.get("status") == "completed":
        if st.button("Start new run (current will be archived)"):
            _archive_active_run()
            _safe_rerun()
        st.stop()

    edited_data = st.session_state.get('edited_extraction')
    worker_payload = {
        "config": config,
        "file_paths": [str(path) for path in selected_files],
        "edited_extraction": edited_data,
        "disable_auto_ingestion": not config.enable_auto_ingestion,
    }

    job_id = f"run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_dir = RUN_CACHE_DIR / job_id
    run_dir.mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "config.pkl"
    with config_path.open("wb") as fh:
        pickle.dump(config, fh)
    log_path = run_dir / "worker.log"
    job_record = {
        "job_id": job_id,
        "email": user_email,
        "status": "running",
        "run_dir": str(run_dir),
        "log_path": str(log_path),
        "config_path": str(config_path),
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }
    register_job(job_record)

    status_text = st.empty()
    log_placeholder = st.empty()
    last_log_line = ""
    progress_bar = st.progress(5)

    status_text.text("🔧 Preparing pipeline worker...")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as tmp_input:
        pickle.dump(worker_payload, tmp_input)
        worker_input_path = Path(tmp_input.name)

    cmd = [
        sys.executable,
        "-m",
        "vendor_ai_agent.pipeline_worker",
        str(worker_input_path),
        str(run_dir),
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        worker_input_path.unlink(missing_ok=True)  # type: ignore[attr-defined]
        shutil.rmtree(run_dir, ignore_errors=True)
        remove_job(job_id)
        st.error(f"Failed to spawn worker: {exc}")
        return

    status_text.text("🚀 Pipeline worker running...")
    progress_bar.progress(20)

    log_file = log_path.open("a", encoding="utf-8")
    LOG_MAX_BYTES = 256 * 1024

    try:
        if process.stdout:
            for line in process.stdout:
                cleaned = line.strip()
                if not cleaned:
                    continue
                last_log_line = cleaned
                log_placeholder.text(cleaned)
                print(f"[worker] {cleaned}", flush=True)
                log_file.write(cleaned + "\n")
                log_file.flush()
                if log_file.tell() > LOG_MAX_BYTES:
                    log_file.close()
                    try:
                        with log_path.open("rb") as rf:
                            rf.seek(0, 2)
                            file_size = rf.tell()
                            rf.seek(max(0, file_size - LOG_MAX_BYTES))
                            tail = rf.read().decode("utf-8", errors="ignore")
                    except Exception:
                        tail = ""
                    with log_path.open("w", encoding="utf-8") as wf:
                        wf.write(tail)
                    log_file = log_path.open("a", encoding="utf-8")
        return_code = process.wait()
    finally:
        worker_input_path.unlink(missing_ok=True)  # type: ignore[attr-defined]
        log_file.close()

    if return_code != 0:
        progress_bar.empty()
        status_text.empty()
        st.error("🚨 Pipeline worker failed")
        st.error(last_log_line or "Unknown error")
        update_job(job_id, status="failed", finished_at=datetime.utcnow().isoformat())
        return

    if not run_dir.exists():
        progress_bar.empty()
        status_text.empty()
        st.error("Pipeline worker finished without producing output.")
        update_job(job_id, status="failed", finished_at=datetime.utcnow().isoformat())
        return

    metadata_path = run_dir / "metadata.pkl"
    if not metadata_path.exists():
        st.error("Worker output missing metadata")
        update_job(job_id, status="failed", finished_at=datetime.utcnow().isoformat())
        return

    run_state_path = run_dir / "run_state.pkl"
    changes_applied: list[str] = []
    if run_state_path.exists():
        with run_state_path.open("rb") as fh:
            run_state = pickle.load(fh)
            changes_applied = run_state.get("changes", [])

    progress_bar.progress(100)
    status_text.text("✅ Pipeline completed successfully!")
    st.success("✅ Pipeline execution completed!")

    if changes_applied:
        st.info("🔄 **Manual edits detected - pipeline rerun with overrides:**")
        for change in changes_applied:
            st.markdown(f"  - {change}")

    if config.enable_manual_review:
        st.info("💡 Manual review mode enabled. Check the 'Extracted Data' tab to edit values before re-running.")

    finished_at = datetime.utcnow().isoformat()
    update_job(job_id, status="completed", finished_at=finished_at)
    st.session_state['config'] = config
    st.session_state['active_run'] = {
        "id": job_id,
        "job_id": job_id,
        "path": str(run_dir),
        "created_at": job_record["started_at"],
        "last_viewed_at": finished_at,
    }
    st.session_state.pop('edited_extraction', None)
    artifacts = _materialize_run_artifacts(run_dir)

    render_pipeline_results(
        artifacts,
        config,
        pipeline=None,
    )

    del artifacts
    gc.collect()


if __name__ == "__main__":
    main()

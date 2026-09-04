"""Behavioural regressions for the portfolio cleanup; all inputs are local."""
import csv
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from vendor_ai_agent import cli
from vendor_ai_agent.config import RuntimeConfig
from vendor_ai_agent.database.models import Base, IngestionChunk, Vendor
from vendor_ai_agent.demo import example_matches, export_demo
from vendor_ai_agent.file_storage import save_uploads
from vendor_ai_agent.ingestion.canada_contracts import CanadaContractsLoader
from vendor_ai_agent.models import APIMetadata, SetAsideMetadata, TenderProfile, TenderSection, VendorMatchResult, VendorRecord
from vendor_ai_agent.modules.capability_matching import CapabilityMatcher
from vendor_ai_agent.modules.vendor_discovery import VendorDiscovery
from vendor_ai_agent.modules.vendor_filter import VendorFilter
from vendor_ai_agent.pipeline import TenderVendorPipeline


def pipeline_without_services(profile, candidates, matches):
    pipeline = object.__new__(TenderVendorPipeline)
    cfg = RuntimeConfig()
    cfg.enable_auto_ingestion = False
    cfg.discovery.enable_batch_cache = False
    cfg.filtering.enable_geographic = False
    cfg.filtering.enable_size_heuristics = False
    cfg.discovery.enable_serper_discovery = False
    pipeline.llm_provider = None
    parser = Mock()
    parser.parse.return_value = [TenderSection('Scope', 'Grounds maintenance')]
    extractor = Mock()
    extractor.extract.return_value = profile
    discovery = Mock()
    discovery.discover.return_value = candidates
    enricher = Mock(spec=['enrich_with_scoring', 'relevance_score_threshold'])
    enricher.relevance_score_threshold = 40
    enricher.enrich_with_scoring.return_value = (candidates, [], matches)
    pipeline.context = SimpleNamespace(
        config=cfg, document_parser=parser, requirement_extractor=extractor,
        vendor_discovery=discovery, vendor_filter=VendorFilter(cfg.filtering),
        vendor_enricher=enricher, capability_matcher=CapabilityMatcher(),
    )
    return pipeline


@pytest.mark.parametrize('method,score,expected', [('llm', 10, 0), ('rule_based', 95, 0), ('llm', 85, 1)])
def test_final_shortlist_preserves_review_boundary(method, score, expected):
    vendor = VendorRecord('Example Supplier', filtering_metadata={'scoring_method': method})
    match = VendorMatchResult(vendor, score, 'Example')
    pipeline = pipeline_without_services(TenderProfile(), [vendor], [match])
    result = pipeline._run_internal([])
    assert len(result.final_matches) == expected
    assert len(result.all_matches) == 1
    assert vendor.filtering_metadata['match_status'] == ('selected' if expected else 'needs_review')


def test_late_candidates_pass_eligibility_again():
    profile = TenderProfile(api_metadata=APIMetadata(set_aside=SetAsideMetadata(code='WOSB')))
    valid = VendorRecord('Eligible', business_types=['WOSB'])
    invalid = VendorRecord('Ineligible', business_types=[])
    pipeline = pipeline_without_services(profile, [valid], [])
    pipeline._ensure_min_candidates_after_filter = lambda profile, vendors: vendors + [invalid]
    result = pipeline._run_internal([])
    assert [v.company_name for v in result.filtered_vendors] == ['Eligible']
    assert invalid.filtering_metadata['exclusion_reason'] == 'set_aside_missing_WOSB'


def test_no_automatic_fictional_vendors():
    assert VendorDiscovery().discover(TenderProfile()) == []
    assert VendorDiscovery(sources=[]).discover(TenderProfile()) == []
    assert not RuntimeConfig().discovery.enable_static_demo_source


def test_cache_key_changes_with_requirements_and_settings_but_not_batch():
    pipeline = pipeline_without_services(TenderProfile(), [], [])
    first, second = TenderProfile(), TenderProfile()
    first.vendor_capability_profile.summary = 'Mowing'
    second.vendor_capability_profile.summary = 'Snow removal'
    key = pipeline._cache_key(first)
    assert key != pipeline._cache_key(second)
    pipeline.context.config.discovery.processing_batch = 2
    assert key == pipeline._cache_key(first)
    pipeline.context.config.filtering.enable_set_aside_filtering = False
    assert key != pipeline._cache_key(first)


@pytest.mark.parametrize('response', ['{}', '{"score": "NaN"}', '{"score": "Infinity"}'])
def test_invalid_model_scores_do_not_become_selected(response):
    provider = Mock()
    provider.generate.return_value = response
    vendor = VendorRecord('Example', website='https://supplier.example', filtering_metadata={'website_content': 'Some content'})
    result = CapabilityMatcher(provider).score(TenderProfile(), [vendor])
    assert result[0].vendor.filtering_metadata['scoring_method'] == 'rule_based'


def write_contracts(path, count=2):
    rows = [{
        'supplierLegalName-nomLegalFournisseur-eng': 'Example Supplier',
        'supplierAddressPostalCode-fournisseurAdresseCodePostal': 'A1A 1A1',
        'contractNumber-numeroContrat': f'C-{i}',
        'totalContractValue-valeurTotaleContrat': '100',
        'contractAwardDate-dateAttributionContrat': '2025-01-01',
    } for i in range(count)]
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def test_repeated_csv_import_does_not_inflate_totals(tmp_path):
    path = tmp_path / 'contracts.csv'
    write_contracts(path)
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for _ in range(2):
            loader = CanadaContractsLoader(session)
            loader.CHUNK_SIZE = 1
            stats = loader.load_csv(path)
        vendor = session.scalar(select(Vendor))
        assert vendor.total_contract_value == 200
        assert vendor.contract_count == 2
        assert stats['rows_skipped'] == 2
        assert len(session.scalars(select(IngestionChunk)).all()) == 2
    engine.dispose()


def test_failed_import_does_not_mark_chunk_complete(tmp_path, monkeypatch):
    path = tmp_path / 'contracts.csv'
    write_contracts(path, count=1)
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        loader = CanadaContractsLoader(session)
        monkeypatch.setattr(loader, '_upsert_vendor', Mock(side_effect=ValueError('bad row')))
        with pytest.raises(ValueError, match='bad row'):
            loader.load_csv(path)
        assert session.scalar(select(IngestionChunk.id)) is None
        CanadaContractsLoader(session).load_csv(path)
        assert session.scalar(select(Vendor)).contract_count == 1
    engine.dispose()


def test_uploads_cannot_overwrite_another_job(tmp_path):
    first, second = BytesIO(b'one'), BytesIO(b'two')
    first.name = '../../same.pdf'
    second.name = 'same.pdf'
    one = save_uploads([first], tmp_path)[0]
    two = save_uploads([second], tmp_path)[0]
    assert one.name == two.name == 'same.pdf'
    assert one.parent != two.parent
    assert one.is_relative_to(tmp_path) and two.is_relative_to(tmp_path)
    assert one.read_bytes() == b'one' and two.read_bytes() == b'two'


def test_export_retains_contact_provenance(tmp_path):
    export_demo(tmp_path)
    record = json.loads((tmp_path / 'vendor_matches.json').read_text())[0]
    assert record['email_validation'] == 'not_validated'
    assert record['scoring_method'] == 'authored_example'
    assert record['match_status'] == 'needs_review'
    assert (tmp_path / 'vendor_matches.xlsx').exists()


def test_cli_ingest_dispatches_exactly_once(monkeypatch, tmp_path):
    import vendor_ai_agent.ingestion.sam_csv as module
    loader = Mock(return_value=3)
    monkeypatch.setattr(module, 'ingest_sam_csv', loader)
    path = tmp_path / 'source.csv'
    cli.main(['ingest-sam-csv', str(path)])
    loader.assert_called_once_with(path)


@pytest.mark.parametrize('prefix', [[], ['run']])
def test_cli_legacy_and_run_dispatch_same_documents(monkeypatch, prefix, tmp_path):
    import vendor_ai_agent.pipeline as module
    pipeline = Mock()
    pipeline.run.return_value = SimpleNamespace(tender_sections=[], final_matches=[])
    monkeypatch.setattr(module, 'TenderVendorPipeline', lambda: pipeline)
    path = tmp_path / 'tender.pdf'
    cli.main(prefix + [str(path)])
    pipeline.run.assert_called_once_with([path], disable_auto_ingestion=False)
    pipeline.save_outputs.assert_called_once()

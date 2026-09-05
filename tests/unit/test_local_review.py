"""Offline checks for the document-to-review workflow and attachment boundaries."""
import json
from io import BytesIO
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from vendor_ai_agent.demo import DATA_DIR, build_demo, export_demo
from vendor_ai_agent.demo_report import render_report
from vendor_ai_agent.database.models import Base, Vendor
from vendor_ai_agent.models import AttachmentMetadata
from vendor_ai_agent.modules.document_fetcher import DocumentFetcher
from vendor_ai_agent.modules.document_parser import DocumentParser
from vendor_ai_agent.modules.document_processing import SectionExtractor
from vendor_ai_agent.sources.canada_contracts import CanadaContractsSource


def test_local_workflow_exposes_gaps_and_deduplicates(tmp_path):
    report, matches = build_demo()
    assert report['input_count'] == 5
    assert report['duplicates_removed'] == 1
    assert [row['covered'] for row in report['candidates']] == [3, 2, 1, 0]
    assert report['candidates'][1]['missing'] == ['Hedge trimming']
    assert all(row['follow_up'] == ['Certificate of liability insurance', 'Two recent references for comparable work']
               for row in report['candidates'])
    assert all(match.vendor.filtering_metadata['match_status'] == 'needs_review' for match in matches)
    export_demo(tmp_path)
    assert json.loads((tmp_path / 'review.json').read_text()) == report
    assert (tmp_path / 'tender.md').read_text() == (DATA_DIR / 'tender.md').read_text()
    assert '<table>' in (tmp_path / 'review.html').read_text()


def test_demo_recomputes_from_changed_document_and_snapshot(tmp_path):
    tender = tmp_path / 'tender.md'
    tender.write_text('# Snow contract\n\n## Technical requirements\n- Snow removal\n\n## Mandatory requirements\n- Safety plan\n')
    snapshot = tmp_path / 'vendors.json'
    snapshot.write_text(json.dumps([{'company_name': 'Local contractor', 'services': ['Snow removal'],
                                   'source_reference': 'local_snapshot:1'}]))
    report, matches = build_demo(tender, snapshot)
    assert report['title'] == 'Snow contract'
    assert report['requirements'] == ['Snow removal']
    assert report['candidates'][0]['covered'] == 1
    assert matches[0].capability_match_score == 100
    assert report['follow_up'] == ['Safety plan']
    tender.write_text(tender.read_text().replace('- Snow removal', '- Snow removal\n- Gritting'))
    report, matches = build_demo(tender, snapshot)
    assert report['candidates'][0]['missing'] == ['Gritting']
    assert matches[0].capability_match_score == 50


def test_empty_requirement_list_is_not_a_perfect_match(tmp_path):
    tender = tmp_path / 'empty.md'
    tender.write_text('# Empty tender\nNo requirements provided')
    with pytest.raises(ValueError, match='Technical requirements'):
        build_demo(tender)


def test_html_escapes_source_text():
    report, _ = build_demo()
    report['candidates'][0]['company_name'] = '<img src=x onerror=alert(1)>'
    report['candidates'][0]['source_reference'] = 'javascript:alert(1)'
    rendered = render_report(report)
    assert '<img' not in rendered
    assert '&lt;img' in rendered
    assert 'href="javascript:' not in rendered


def test_markdown_sections_preserve_fenced_content(tmp_path):
    document = tmp_path / 'spec.md'
    document.write_text('# Enquiry\n\n## Scope of work\nMaintain a site.\n\n## Technical requirements\n- Mowing\n```text\n# Not a heading\n```\n## Mandatory requirements\n- Insurance\n')
    sections = DocumentParser().parse([document])
    assert [section.title for section in sections] == ['Enquiry', 'Scope of work', 'Technical requirements', 'Mandatory requirements']
    fields = SectionExtractor().extract(sections)
    assert fields.scope_of_work == 'Maintain a site.'
    assert '# Not a heading' in fields.technical_requirements
    assert fields.mandatory_requirements == '- Insurance'


@pytest.mark.parametrize('name,keyword', [('Civic Catering', 'catering'), ('Valley Auto Repair', 'repair'),
                                          ('Local Fitness', 'fitness'), ('Park Property Services', 'property')])
def test_canada_source_does_not_blacklist_relevant_business_names(name, keyword):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Vendor(source='canada_contracts', external_id='fixture', legal_name=name,
                           total_contract_value=10000, contract_count=1))
        session.commit()
        assert [vendor.legal_name for vendor in CanadaContractsSource(session).search_vendors(keywords=[keyword])] == [name]
    engine.dispose()


class Response(BytesIO):
    def __init__(self, body=b'pdf', headers=None):
        super().__init__(body)
        self.headers = headers or {}


def fetcher(tmp_path, responses, **limits):
    instance = DocumentFetcher(tmp_path, **limits)
    instance._opener = Mock()
    instance._opener.open.side_effect = responses
    return instance


def test_attachments_have_safe_names_and_independent_storage(tmp_path):
    instance = fetcher(tmp_path, [Response(b'first'), Response(b'second')])
    saved = instance.fetch([AttachmentMetadata(url='https://source.example/a', filename='../../same.pdf'),
                            AttachmentMetadata(url='https://source.example/b', filename='C:\\temp\\same.pdf')])
    assert [path.name for path in saved] == ['same.pdf', 'same.pdf']
    assert [path.read_bytes() for path in saved] == [b'first', b'second']
    assert saved[0].parent != saved[1].parent
    assert all(path.is_relative_to(tmp_path) for path in saved)
    assert instance._opener.open.call_args.kwargs['timeout'] == 20


@pytest.mark.parametrize('headers', [{}, {'Content-Length': '6'}])
def test_oversized_attachments_leave_no_partial_files(tmp_path, headers, caplog):
    instance = fetcher(tmp_path, [Response(b'123456', headers)], max_bytes=5)
    assert instance.fetch([AttachmentMetadata(url='https://source.example/a.pdf?secret=hidden')]) == []
    assert list(tmp_path.iterdir()) == []
    assert instance.failures == [{'filename': 'a.pdf', 'error': 'ValueError'}]
    assert 'could not be downloaded' in caplog.text and 'hidden' not in caplog.text


def test_download_failure_is_reported_and_later_attachment_survives(tmp_path):
    broken = Response()
    broken.read = Mock(side_effect=[b'partial', TimeoutError('private-url-secret')])
    instance = fetcher(tmp_path, [broken, Response(b'good')])
    saved = instance.fetch([AttachmentMetadata(url='https://source.example/broken.pdf'),
                            AttachmentMetadata(url='https://source.example/good.pdf')])
    assert len(saved) == 1 and saved[0].read_bytes() == b'good'
    assert list(tmp_path.rglob('broken.pdf')) == []
    assert instance.failures[0]['error'] == 'TimeoutError'


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'ftp://source.example/a.pdf', 'https://user:password@source.example/a.pdf', None])
def test_attachment_rejects_unsupported_urls_before_opening(tmp_path, url):
    instance = fetcher(tmp_path, [])
    assert instance.fetch([AttachmentMetadata(url=url)]) == []
    instance._opener.open.assert_not_called()
    assert instance.failures


def test_download_total_deadline(tmp_path, monkeypatch):
    instance = fetcher(tmp_path, [Response(b'slow')])
    times = iter([0, 121])
    monkeypatch.setattr('vendor_ai_agent.modules.document_fetcher.time.monotonic', lambda: next(times))
    assert instance.fetch([AttachmentMetadata(url='https://source.example/slow.pdf')]) == []
    assert instance.failures[0]['error'] == 'TimeoutError'
    assert list(tmp_path.iterdir()) == []


def test_truncated_response_does_not_become_a_saved_document(tmp_path):
    instance = fetcher(tmp_path, [Response(b'partial', {'Content-Length': '100'})])
    assert instance.fetch([AttachmentMetadata(url='https://source.example/incomplete.pdf')]) == []
    assert instance.failures and list(tmp_path.iterdir()) == []

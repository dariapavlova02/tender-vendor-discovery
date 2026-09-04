import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from vendor_ai_agent.enrichment_providers.duckduckgo_website_enricher import (
    DuckDuckGoWebsiteEnricher,
)
from vendor_ai_agent.database.models import Vendor, APICache


class TestDuckDuckGoWebsiteEnricher:
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)

    @pytest.fixture
    def enricher(self, mock_db):
        return DuckDuckGoWebsiteEnricher(db_session=mock_db)

    def test_normalize_company_name_legal_suffixes(self, enricher):
        assert enricher._normalize_company_name("HubSpoke Inc.") == "hubspoke"
        assert enricher._normalize_company_name("SIERRA SYSTEMS GROUP INC") == "sierra systems group"
        assert enricher._normalize_company_name("General Dynamics Corp") == "general dynamics"
        assert enricher._normalize_company_name("Tech Solutions LLC") == "tech solutions"

    def test_normalize_company_name_special_chars(self, enricher):
        assert enricher._normalize_company_name("Smith & Jones Ltd.") == "smith jones"
        assert enricher._normalize_company_name("ABC-Tech Corp.") == "abc tech"
        assert enricher._normalize_company_name("Company (2023)") == "company"

    def test_extract_real_url_uddg_parameter(self, enricher):
        html_link = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fhubspoke.com&rut=123"
        assert enricher._extract_real_url(html_link) == "https://hubspoke.com"

    def test_extract_real_url_no_uddg(self, enricher):
        html_link = "https://example.com/page"
        assert enricher._extract_real_url(html_link) == "https://example.com/page"

    def test_extract_real_url_malformed_uddg(self, enricher):
        html_link = "https://duckduckgo.com/l/?uddg=malformed%url"
        assert enricher._extract_real_url(html_link) == "https://duckduckgo.com/l/?uddg=malformed%url"

    def test_extract_domain_standard(self, enricher):
        assert enricher._extract_domain("https://example.com/page") == "example.com"
        assert enricher._extract_domain("http://www.example.com") == "example.com"
        assert enricher._extract_domain("https://subdomain.example.com") == "subdomain.example.com"

    def test_extract_domain_no_scheme(self, enricher):
        assert enricher._extract_domain("example.com/page") == "example.com"
        assert enricher._extract_domain("www.example.com") == "example.com"

    def test_should_ignore_domain(self, enricher):
        assert enricher._should_ignore_domain("linkedin.com") is True
        assert enricher._should_ignore_domain("www.linkedin.com") is True
        assert enricher._should_ignore_domain("indeed.ca") is True
        assert enricher._should_ignore_domain("canadabuys.canada.ca") is True
        assert enricher._should_ignore_domain("legitcompany.com") is False

    def test_calculate_token_match_exact(self, enricher):
        assert enricher._calculate_token_match("hubspoke", "hubspoke.com") == 1.0

    def test_calculate_token_match_partial(self, enricher):
        score = enricher._calculate_token_match("sierra systems", "sierrasystems.com")
        assert 0.8 <= score <= 1.0

    def test_calculate_token_match_multi_word(self, enricher):
        score = enricher._calculate_token_match("general dynamics", "generaldynamics.com")
        assert score > 0.8

    def test_calculate_token_match_no_match(self, enricher):
        score = enricher._calculate_token_match("hubspoke", "completelydifferent.com")
        assert score < 0.3

    def test_score_result_high_confidence(self, enricher):
        result = {
            "url": "https://hubspoke.com",
            "domain": "hubspoke.com",
            "title": "HubSpoke - Official Site",
            "snippet": "Welcome to HubSpoke official website",
        }
        score = enricher._score_result(result, "hubspoke", position=0)
        assert score >= 0.7
        assert score <= 1.0

    def test_score_result_medium_confidence(self, enricher):
        result = {
            "url": "https://sierrasystems.com",
            "domain": "sierrasystems.com",
            "title": "Sierra Systems",
            "snippet": "Technology consulting",
        }
        score = enricher._score_result(result, "sierra systems", position=0)
        assert 0.5 <= score < 0.7

    def test_score_result_ca_tld_bonus(self, enricher):
        result_ca = {
            "url": "https://example.ca",
            "domain": "example.ca",
            "title": "Example Company",
            "snippet": "Canadian company",
        }
        result_com = {
            "url": "https://example.com",
            "domain": "example.com",
            "title": "Example Company",
            "snippet": "Company website",
        }
        score_ca = enricher._score_result(result_ca, "example", position=0)
        score_com = enricher._score_result(result_com, "example", position=0)
        assert score_ca > score_com

    def test_score_result_position_bonus(self, enricher):
        result = {
            "url": "https://example.com",
            "domain": "example.com",
            "title": "Example Company",
            "snippet": "Company website",
        }
        score_first = enricher._score_result(result, "example", position=0)
        score_second = enricher._score_result(result, "example", position=1)
        assert score_first > score_second

    def test_score_result_snippet_bonus(self, enricher):
        result_with_name = {
            "url": "https://example.com",
            "domain": "example.com",
            "title": "Example",
            "snippet": "Welcome to Example Company official site",
        }
        result_without_name = {
            "url": "https://example.com",
            "domain": "example.com",
            "title": "Example",
            "snippet": "Technology solutions provider",
        }
        score_with = enricher._score_result(result_with_name, "example company", position=0)
        score_without = enricher._score_result(result_without_name, "example company", position=0)
        assert score_with > score_without

    @patch('requests.get')
    def test_search_duckduckgo_success(self, mock_get, enricher):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="results">
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fhubspoke.com">
                        <h2 class="result__title">HubSpoke</h2>
                    </a>
                    <div class="result__snippet">Official HubSpoke website</div>
                </div>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        results = enricher._search_duckduckgo("HubSpoke")
        assert len(results) > 0
        assert results[0]["domain"] == "hubspoke.com"
        assert "hubspoke" in results[0]["title"].lower()

    @patch('requests.get')
    def test_search_duckduckgo_rate_limit(self, mock_get, enricher):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><div class="results"></div></html>'
        mock_get.return_value = mock_response

        start_time = time.time()
        enricher._search_duckduckgo("Company 1")
        enricher._search_duckduckgo("Company 2")
        elapsed = time.time() - start_time

        assert elapsed >= 2.0

    @patch('requests.get')
    def test_search_duckduckgo_http_error(self, mock_get, enricher):
        mock_get.side_effect = Exception("Network error")
        results = enricher._search_duckduckgo("Test Company")
        assert results == []

    def test_check_cache_hit(self, enricher, mock_db):
        cached_entry = APICache(
            cache_key="ddg_website:hubspoke",
            provider="duckduckgo_website",
            response_data={
                "website": "https://hubspoke.com",
                "confidence_score": 0.9,
            },
            created_at=datetime.utcnow(),
        )
        mock_db.query().filter().first.return_value = cached_entry

        result = enricher._check_cache(mock_db, "HubSpoke")
        assert result is not None
        assert result["website"] == "https://hubspoke.com"
        assert result["confidence_score"] == 0.9

    def test_check_cache_miss(self, enricher, mock_db):
        mock_db.query().filter().first.return_value = None
        result = enricher._check_cache(mock_db, "HubSpoke")
        assert result is None

    def test_check_cache_expired(self, enricher, mock_db):
        expired_entry = APICache(
            cache_key="ddg_website:hubspoke",
            provider="duckduckgo_website",
            response_data={"website": "https://hubspoke.com"},
            created_at=datetime.utcnow() - timedelta(days=8),
        )
        mock_db.query().filter().first.return_value = expired_entry

        result = enricher._check_cache(mock_db, "HubSpoke")
        assert result is None

    def test_save_to_cache(self, enricher, mock_db):
        enricher._save_to_cache(
            mock_db,
            "HubSpoke",
            {"website": "https://hubspoke.com", "confidence_score": 0.9},
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch('requests.get')
    def test_enrich_vendor_success(self, mock_get, enricher, mock_db):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="results">
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fhubspoke.com">
                        <h2 class="result__title">HubSpoke</h2>
                    </a>
                    <div class="result__snippet">HubSpoke official website</div>
                </div>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        mock_db.query().filter().first.return_value = None

        vendor = Vendor(id=1, name="HubSpoke Inc.")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates is not None
        assert "website" in updates
        assert "hubspoke.com" in updates["website"]
        assert updates["confidence_score"] >= 0.7

    @patch('requests.get')
    def test_enrich_vendor_cache_hit(self, mock_get, enricher, mock_db):
        cached_entry = APICache(
            cache_key="ddg_website:hubspoke",
            provider="duckduckgo_website",
            response_data={
                "website": "https://hubspoke.com",
                "confidence_score": 0.9,
            },
            created_at=datetime.utcnow(),
        )
        mock_db.query().filter().first.return_value = cached_entry

        vendor = Vendor(id=1, name="HubSpoke Inc.")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates["website"] == "https://hubspoke.com"
        assert updates["confidence_score"] == 0.9
        mock_get.assert_not_called()

    @patch('requests.get')
    def test_enrich_vendor_no_results(self, mock_get, enricher, mock_db):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '<html><div class="results"></div></html>'
        mock_get.return_value = mock_response

        mock_db.query().filter().first.return_value = None

        vendor = Vendor(id=1, name="Nonexistent Company XYZ")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates is None

    @patch('requests.get')
    def test_enrich_vendor_low_confidence_filtered(self, mock_get, enricher, mock_db):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="results">
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fcompletely-different.com">
                        <h2 class="result__title">Different Company</h2>
                    </a>
                    <div class="result__snippet">Not related</div>
                </div>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        mock_db.query().filter().first.return_value = None

        vendor = Vendor(id=1, name="HubSpoke Inc.")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates is None

    def test_get_provider_name(self, enricher):
        assert enricher.get_provider_name() == "duckduckgo_website"

    @patch('requests.get')
    def test_enrich_vendor_ignores_social_media(self, mock_get, enricher, mock_db):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="results">
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Flinkedin.com%2Fcompany%2Fhubspoke">
                        <h2 class="result__title">HubSpoke LinkedIn</h2>
                    </a>
                </div>
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fhubspoke.com">
                        <h2 class="result__title">HubSpoke</h2>
                    </a>
                </div>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        mock_db.query().filter().first.return_value = None

        vendor = Vendor(id=1, name="HubSpoke")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates is not None
        assert "linkedin.com" not in updates["website"]
        assert "hubspoke.com" in updates["website"]


class TestDuckDuckGoIntegration:
    @pytest.fixture
    def enricher(self):
        mock_db = Mock(spec=Session)
        return DuckDuckGoWebsiteEnricher(db_session=mock_db)

    @pytest.mark.integration
    @patch('time.sleep')
    @patch('requests.get')
    def test_hubspoke_real_case(self, mock_get, mock_sleep, enricher):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="results">
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fhubspoke.com">
                        <h2 class="result__title">HubSpoke - Supplier Collaboration</h2>
                    </a>
                    <div class="result__snippet">HubSpoke is a supplier collaboration platform</div>
                </div>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None

        vendor = Vendor(id=1, name="HubSpoke Inc.")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates is not None
        assert updates["website"] == "https://hubspoke.com"
        assert updates["confidence_score"] >= 0.7

    @pytest.mark.integration
    @patch('time.sleep')
    @patch('requests.get')
    def test_sierra_systems_acquired_company(self, mock_get, mock_sleep, enricher):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''
        <html>
            <div class="results">
                <div class="result">
                    <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fnttdata.com">
                        <h2 class="result__title">NTT DATA - Sierra Systems</h2>
                    </a>
                    <div class="result__snippet">Sierra Systems is now part of NTT DATA</div>
                </div>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response

        mock_db = Mock(spec=Session)
        mock_db.query().filter().first.return_value = None

        vendor = Vendor(id=2, name="SIERRA SYSTEMS GROUP INC")
        updates = enricher.enrich_vendor(vendor, mock_db)

        assert updates is not None
        assert "nttdata.com" in updates["website"]
        assert updates["confidence_score"] >= 0.5

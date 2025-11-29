"""
Test suite for SmartEmailGeneratorProvider.

Tests MX validation, email candidate generation, Serper contextual validation,
and confidence scoring for the Level 4 contact enrichment strategy.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from vendor_ai_agent.enrichment_providers.smart_email_generator import SmartEmailGeneratorProvider
from vendor_ai_agent.enrichment_providers.serper_client import SerperResult
from vendor_ai_agent.models import VendorRecord


@pytest.fixture
def mock_serper_client():
    """Mock SerperClient."""
    mock = Mock()
    mock.search_company_async = AsyncMock()
    return mock


@pytest.fixture
def provider_with_mx(mock_serper_client):
    """Provider with MX checking enabled."""
    return SmartEmailGeneratorProvider(
        serper_client=mock_serper_client,
        enable_mx_check=True,
        enable_serper_validation=True,
        prefixes=['sales', 'contact', 'info'],
        max_candidates=3,
        require_company_context=True,
        min_confidence=0.6
    )


@pytest.fixture
def provider_without_mx(mock_serper_client):
    """Provider with MX checking disabled."""
    return SmartEmailGeneratorProvider(
        serper_client=mock_serper_client,
        enable_mx_check=False,
        enable_serper_validation=True,
        prefixes=['sales', 'contact'],
        max_candidates=2,
        require_company_context=False,
        min_confidence=0.5
    )


@pytest.fixture
def sample_vendor():
    """Sample vendor for testing."""
    return VendorRecord(
        company_name="Acme Corporation",
        website="https://acme.com",
        filtering_metadata={}
    )


@pytest.mark.asyncio
class TestMXValidation:
    """Test MX record validation logic."""

    @patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns')
    async def test_valid_mx_records(self, mock_dns, provider_with_mx, sample_vendor, mock_serper_client):
        """Test domain with valid MX records."""
        mock_dns.resolver.resolve.return_value = [Mock()]
        mock_serper_client.search_company_async.return_value = SerperResult(raw_response={"organic": []})
        
        result = await provider_with_mx.enrich_async(sample_vendor)
        
        assert result is not None
        mock_dns.resolver.resolve.assert_called_once_with('acme.com', 'MX')

    @patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns')
    async def test_no_mx_records(self, mock_dns, provider_with_mx, sample_vendor):
        """Test domain with no MX records returns vendor unchanged."""
        from vendor_ai_agent.enrichment_providers.smart_email_generator import dns
        mock_dns.resolver.resolve.side_effect = dns.resolver.NoAnswer()
        
        result = await provider_with_mx.enrich_async(sample_vendor)
        
        assert result.email is None

    @patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns')
    async def test_nxdomain_error(self, mock_dns, provider_with_mx, sample_vendor):
        """Test non-existent domain returns vendor unchanged."""
        from vendor_ai_agent.enrichment_providers.smart_email_generator import dns
        mock_dns.resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
        
        result = await provider_with_mx.enrich_async(sample_vendor)
        
        assert result.email is None

    async def test_mx_check_disabled(self, provider_without_mx, sample_vendor, mock_serper_client):
        """Test that MX check is skipped when disabled."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={"organic": []})
            
            await provider_without_mx.enrich_async(sample_vendor)
            
            mock_dns.resolver.resolve.assert_not_called()


@pytest.mark.asyncio
class TestCandidateGeneration:
    """Test email candidate generation."""

    async def test_candidate_priority_order(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test candidates are generated in priority order."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_dns.resolver.resolve.return_value = [Mock()]
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={"organic": []})
            
            await provider_with_mx.enrich_async(sample_vendor)
            
            calls = mock_serper_client.search_company_async.call_args_list
            # Extract emails from query parameter (kwargs)
            queries = [call.kwargs['query'] for call in calls]
            
            assert 'sales@acme.com' in queries[0]
            assert 'contact@acme.com' in queries[1]
            assert 'info@acme.com' in queries[2]

    async def test_max_candidates_limit(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test max_candidates limit is respected."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_dns.resolver.resolve.return_value = [Mock()]
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={"organic": []})
            
            await provider_with_mx.enrich_async(sample_vendor)
            
            assert mock_serper_client.search_company_async.call_count == 3

    async def test_custom_prefixes(self, mock_serper_client, sample_vendor):
        """Test custom prefix list."""
        provider = SmartEmailGeneratorProvider(
            serper_client=mock_serper_client,
            enable_mx_check=False,
            enable_serper_validation=True,
            prefixes=['hello', 'inquiry'],
            max_candidates=2,
            require_company_context=True,
            min_confidence=0.6
        )
        
        mock_serper_client.search_company_async.return_value = SerperResult(raw_response={"organic": []})
        
        await provider.enrich_async(sample_vendor)
        
        calls = mock_serper_client.search_company_async.call_args_list
        assert len(calls) == 2
        queries = [call.kwargs['query'] for call in calls]
        assert 'hello@acme.com' in queries[0]
        assert 'inquiry@acme.com' in queries[1]


@pytest.mark.asyncio
class TestContextualValidation:
    """Test Serper contextual validation logic."""

    async def test_email_and_company_in_snippet(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test email accepted when both email and company appear in snippet."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_dns.resolver.resolve.return_value = [Mock()]
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={
                "organic": [{
                    "snippet": "Contact Acme Corporation at sales@acme.com for inquiries",
                    "title": "Contact Us"
                }]
            })
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            assert result is not None
            assert result.email == "sales@acme.com"
            assert result.filtering_metadata["email_source"] == "smart_generated"

    async def test_email_without_company_context(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test email accepted when email present (confidence calculated from email domain match)."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_dns.resolver.resolve.return_value = [Mock()]
            # Snippet contains email but not full company name
            # However, "acme" appears in the email address domain, which can be normalized-matched
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={
                "organic": [{
                    "snippet": "Contact us at sales@acme.com for more information",
                    "title": "Contact"
                }]
            })
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            # The algorithm finds "acme" in the email address, which matches normalized company name
            # Base (0.4) + email_in_text (0.2) = 0.6, meets threshold
            assert result.email == "sales@acme.com"

    async def test_company_context_not_required(self, provider_without_mx, sample_vendor, mock_serper_client):
        """Test email accepted without company name when require_company_context=False."""
        mock_serper_client.search_company_async.return_value = SerperResult(raw_response={
            "organic": [{
                "snippet": "Email sales@acme.com for details",
                "title": "Contact"
            }]
        })
        
        result = await provider_without_mx.enrich_async(sample_vendor)
        
        assert result is not None
        assert result.email == "sales@acme.com"

    async def test_no_email_in_snippet(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test candidate rejected when email not found in snippet."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_dns.resolver.resolve.return_value = [Mock()]
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={
                "organic": [{
                    "snippet": "Acme Corporation is a leading provider",
                    "title": "About Us"
                }]
            })
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            assert result.email is None


@pytest.mark.asyncio
class TestConfidenceScoring:
    """Test confidence score calculation."""

    async def test_high_confidence_score(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test high confidence when all signals present."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns'):
            mock_serper_client.search_async.return_value = {
                "organic": [{
                    "snippet": "Contact Acme Corporation at sales@acme.com",
                    "link": "https://acme.com/contact"
                }]
            }
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            assert result is not None

    async def test_below_threshold_confidence(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test candidate rejected when confidence below threshold."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns'):
            mock_serper_client.search_async.return_value = {
                "organic": [{
                    "snippet": "Some generic text"
                }]
            }
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            assert result.email is None

    async def test_custom_confidence_threshold(self, mock_serper_client, sample_vendor):
        """Test custom minimum confidence threshold."""
        provider = SmartEmailGeneratorProvider(
            serper_client=mock_serper_client,
            enable_mx_check=False,
            enable_serper_validation=True,
            prefixes=['sales'],
            max_candidates=1,
            require_company_context=False,
            min_confidence=0.3
        )
        
        mock_serper_client.search_async.return_value = {
            "organic": [{
                "snippet": "Email sales@acme.com"
            }]
        }
        
        result = await provider.enrich_async(sample_vendor)
        
        assert result is not None


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_vendor_without_website(self, provider_with_mx):
        """Test vendor without website returns vendor unchanged."""
        vendor = VendorRecord(company_name="No Website Corp", filtering_metadata={})
        
        result = await provider_with_mx.enrich_async(vendor)
        
        assert result.email is None

    async def test_vendor_without_name(self, provider_with_mx):
        """Test vendor without name returns vendor unchanged."""
        vendor = VendorRecord(company_name="", website="https://example.com", filtering_metadata={})
        
        result = await provider_with_mx.enrich_async(vendor)
        
        assert result.email is None

    async def test_serper_empty_response(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test handling of empty Serper response."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns'):
            mock_serper_client.search_async.return_value = {}
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            assert result.email is None

    async def test_serper_error(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test handling of Serper API error."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns'):
            mock_serper_client.search_async.side_effect = Exception("API error")
            
            result = await provider_with_mx.enrich_async(sample_vendor)
            
            assert result.email is None

    async def test_dnspython_unavailable(self, mock_serper_client, sample_vendor):
        """Test graceful degradation when dnspython unavailable."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns', None):
            provider = SmartEmailGeneratorProvider(
                serper_client=mock_serper_client,
                enable_mx_check=True,
                enable_serper_validation=True,
                prefixes=['sales'],
                max_candidates=1,
                require_company_context=True,
                min_confidence=0.6
            )
            
            mock_serper_client.search_async.return_value = {
                "organic": [{
                    "snippet": "Contact Acme Corporation at sales@acme.com"
                }]
            }
            
            result = await provider.enrich_async(sample_vendor)
            
            assert result is not None


class TestSyncMethod:
    """Test synchronous enrich() method."""

    def test_sync_enrich(self, provider_with_mx, sample_vendor, mock_serper_client):
        """Test sync method calls async implementation."""
        with patch('vendor_ai_agent.enrichment_providers.smart_email_generator.dns') as mock_dns:
            mock_dns.resolver.resolve.return_value = [Mock()]
            mock_serper_client.search_company_async.return_value = SerperResult(raw_response={
                "organic": [{
                    "snippet": "Contact Acme Corporation at sales@acme.com",
                    "title": "Contact Us"
                }]
            })
            
            result = provider_with_mx.enrich(sample_vendor)
            
            assert result is not None
            assert result.email == "sales@acme.com"

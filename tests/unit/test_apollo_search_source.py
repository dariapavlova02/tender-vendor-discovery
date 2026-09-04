from vendor_ai_agent.sources.apollo_search import ApolloSearchSource
from vendor_ai_agent.models import TenderProfile, DocExtracted, StructuredDocData, VendorConstraints


def _build_profile():
    structured = StructuredDocData(
        sector="software",
        vendor_constraints=VendorConstraints(business_size="SMALL_ONLY"),
    )
    doc_extracted = DocExtracted(structured=structured)
    return TenderProfile(country="France", doc_extracted=doc_extracted)


def test_apollo_search_maps_response(monkeypatch):
    profile = _build_profile()
    source = ApolloSearchSource(api_key="test", per_page=50, max_pages=1)

    request_payloads = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "organizations": [
                    {
                        "name": "Alpha Solutions",
                        "website_url": "https://alpha.test",
                        "city": "Paris",
                        "state": "IDF",
                        "country": "France",
                        "id": "org_1",
                        "estimated_num_employees": 120,
                        "last_activity_date": "2025-01-01",
                    }
                ],
                "pagination": {"total_pages": 1},
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        request_payloads.append({"headers": headers, "json": json})
        return FakeResponse()

    monkeypatch.setattr("vendor_ai_agent.sources.apollo_search.requests.post", fake_post)

    vendors = source.search(profile)

    assert len(vendors) == 1
    vendor = vendors[0]
    assert vendor.company_name == "Alpha Solutions"
    assert vendor.website == "https://alpha.test"
    assert vendor.location == "Paris, IDF, France"
    assert vendor.filtering_metadata["apollo_id"] == "org_1"

    # Ensure filters were populated from profile
    assert request_payloads
    payload = request_payloads[0]["json"]
    assert payload["filters"]["organization_locations"] == ["France"]
    assert payload["filters"]["employee_headcount"] == ["1-10", "11-50", "51-200"]

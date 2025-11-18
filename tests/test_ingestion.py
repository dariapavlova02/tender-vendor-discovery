import pytest

from vendor_ai_agent.config import CanadaOpenDataConfig, SamApiConfig
from vendor_ai_agent.ingestion.sam import UsSamIngestor
from vendor_ai_agent.ingestion.canada import CanadaBuysIngestor
from vendor_ai_agent.ingestion.models import CanadaIngestionRequest, DateRange, SamIngestionRequest


class FakeSamClient:
    def __init__(self, payload):
        self.payload = payload
        self.last_params = None

    def search(self, api_key, params):
        self.last_params = params
        assert api_key == "dummy"
        return self.payload


class FakeCanadaClient:
    def __init__(self, tender_payload, awards_payload):
        self.tender_payload = tender_payload
        self.awards_payload = awards_payload

    def package_show(self, dataset_id):  # pragma: no cover - not used in tests
        raise AssertionError("package_show should not be called when resource_id provided")

    def datastore_search(self, resource_id, **kwargs):
        if resource_id == "t_res":
            return self.tender_payload
        if resource_id == "c_res":
            return self.awards_payload
        raise AssertionError("unexpected resource id")


def test_us_sam_ingestor_maps_fields():
    payload = {
        "opportunitiesData": [
            {
                "solicitationNumber": "36C24225Q0001",
                "title": "Roof Replacement",
                "description": "Replace roof at VA hospital",
                "naicsCode": "238160",
                "classificationCode": "Z1NB",
                "organizationName": "Department of Veterans Affairs",
                "fullParentPathName": "VA >> Construction >> Regional",
                "officeAddress": {
                    "addressLine1": "1 Main St",
                    "city": "Albany",
                    "state": "NY",
                    "zipCode": "12201",
                    "countryCode": "USA",
                },
                "placeOfPerformance": {
                    "city": "Albany",
                    "state": "NY",
                    "zipCode": "12201",
                    "countryCode": "USA",
                },
                "postedDate": "2024-10-01T12:00:00Z",
                "responseDeadLine": "2024-10-15T12:00:00Z",
                "setAsideCode": "SDVOSBC",
                "setAside": "Service Disabled Veteran Owned",
                "baseAndAllOptionsValue": "150000",
                "resourceLinks": [
                    {
                        "url": "https://example.com/solicitation.pdf",
                        "title": "Solicitation",
                        "description": "PDF",
                        "fileType": "application/pdf",
                    }
                ],
                "award": [
                    {
                        "awardID": "A1",
                        "recipient": {
                            "name": "ABC Roofing",
                            "location": {
                                "city": "Denver",
                                "state": "CO",
                                "countryCode": "USA",
                            },
                        },
                        "amount": "100000",
                        "currency": "USD",
                        "awardDate": "2024-09-01",
                    }
                ],
            }
        ]
    }
    client = FakeSamClient(payload)
    ingestor = UsSamIngestor(client, SamApiConfig(api_key="dummy"))
    request = SamIngestionRequest(
        solicitation_number="36C24225Q0001",
        date_range=DateRange(start="10/01/2024", end="12/31/2024"),
    )
    result = ingestor.ingest(request)
    meta = result.api_metadata
    assert meta.external_id == "36C24225Q0001"
    assert meta.codes.naics == ["238160"]
    assert meta.place_of_performance.city == "Albany"
    assert meta.dates.response_deadline == "2024-10-15"
    assert meta.set_aside.code == "SDVOSBC"
    assert meta.estimated_value.amount == 150000.0
    assert meta.awards[0].supplier_name == "ABC Roofing"
    assert result.attachments[0].url == "https://example.com/solicitation.pdf"


def test_canada_buys_ingestor_maps_records():
    tender_payload = {
        "result": {
            "records": [
                {
                    "reference_number": "PW-24-01012345",
                    "title_en": "Supply of Ammunition",
                    "description_en": "Ammo tender",
                    "naics_code": "332992;332994",
                    "gsin_code": "N100A",
                    "organization_name": "OPP",
                    "city": "Toronto",
                    "province_state": "Ontario",
                    "delivery_city": "Orillia",
                    "delivery_province_state": "Ontario",
                    "trade_agreement": "CFTA;CETA",
                    "publication_date": "2024-09-01",
                    "closing_date": "2024-09-30",
                    "notice_url": "https://buyandsell.gc.ca/tender",
                }
            ]
        }
    }
    awards_payload = {
        "result": {
            "records": [
                {
                    "reference_number": "PW-24-01012345",
                    "supplier_name": "AmmoCo",
                    "contract_value": "250000",
                    "currency": "CAD",
                    "contract_date": "2023-01-10",
                    "supplier_city": "Montreal",
                    "supplier_province_state": "QC",
                    "supplier_country": "Canada",
                    "contract_number": "C123",
                }
            ]
        }
    }
    client = FakeCanadaClient(tender_payload, awards_payload)
    config = CanadaOpenDataConfig(
        tender_dataset_id="dataset",
        tender_resource_id="t_res",
        contracts_dataset_id="dataset_contracts",
        contracts_resource_id="c_res",
    )
    ingestor = CanadaBuysIngestor(client, config)
    result = ingestor.ingest(CanadaIngestionRequest(reference_number="PW-24-01012345"))
    meta = result.api_metadata
    assert meta.external_id == "PW-24-01012345"
    assert meta.codes.naics == ["332992", "332994"]
    assert meta.trade_agreements == ["CFTA", "CETA"]
    assert meta.place_of_performance.city == "Orillia"
    assert meta.dates.response_deadline == "2024-09-30"
    assert meta.awards[0].supplier_name == "AmmoCo"
    assert any(
        att.url == "https://buyandsell.gc.ca/tender" for att in result.attachments
    )

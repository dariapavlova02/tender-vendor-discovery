import unittest
from unittest.mock import MagicMock, patch
from vendor_ai_agent.sources.sam_entity import SamEntitySource
from vendor_ai_agent.models import VendorRecord, ContactInfo

class TestSamIntegration(unittest.TestCase):
    def setUp(self):
        self.source = SamEntitySource(api_key="mock_key", sync_to_db=False)

    def test_entity_to_vendor_record_full_data(self):
        # Mock SAM API response with all fields
        entity_data = {
            "coreData": {
                "ueiSAM": "UEI123456789",
                "dunsNumber": "DUNS123456789",
                "cageCode": "CAGE12345",
                "legalBusinessName": "Test Company Inc.",
                "dbaName": "Test Co",
                "physicalAddress": {
                    "city": "Test City",
                    "stateOrProvinceCode": "TS",
                    "countryCode": "USA"
                }
            },
            "entityRegistration": {
                "businessTypes": ["Small Business", "Woman Owned Business"],
                "pointsOfContact": {
                    "governmentBusinessPOC": {
                        "firstName": "Jane",
                        "lastName": "Doe",
                        "email": "jane.doe@example.com",
                        "usPhone": "555-123-4567"
                    }
                }
            }
        }

        record = self.source._entity_to_vendor_record(entity_data)

        self.assertIsInstance(record, VendorRecord)
        self.assertEqual(record.company_name, "Test Company Inc.")
        self.assertEqual(record.uei, "UEI123456789")
        self.assertEqual(record.duns, "DUNS123456789")
        self.assertEqual(record.cage_code, "CAGE12345")
        self.assertIn("Small Business", record.business_types)
        self.assertIn("Woman Owned Business", record.business_types)
        
        self.assertIsInstance(record.primary_contact, ContactInfo)
        self.assertEqual(record.primary_contact.name, "Jane Doe")
        self.assertEqual(record.primary_contact.email, "jane.doe@example.com")
        self.assertEqual(record.primary_contact.phone, "555-123-4567")
        self.assertEqual(record.primary_contact.organization, "Test Company Inc.")

    def test_entity_to_vendor_record_minimal_data(self):
        # Mock SAM API response with minimal fields
        entity_data = {
            "coreData": {
                "legalBusinessName": "Minimal Corp",
                "ueiSAM": "UEI987654321"
            },
            "entityRegistration": {}
        }

        record = self.source._entity_to_vendor_record(entity_data)

        self.assertIsInstance(record, VendorRecord)
        self.assertEqual(record.company_name, "Minimal Corp")
        self.assertEqual(record.uei, "UEI987654321")
        self.assertIsNone(record.duns)
        self.assertIsNone(record.cage_code)
        self.assertEqual(record.business_types, [])
        self.assertIsNone(record.primary_contact)

if __name__ == '__main__':
    unittest.main()

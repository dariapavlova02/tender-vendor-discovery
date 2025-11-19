"""Canada Open Government (CanadaBuys) ingestion."""
from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import parse, request as urllib_request

import certifi

from ..config import CanadaOpenDataConfig
from ..models import (
    APIMetadata,
    Address,
    AttachmentMetadata,
    AwardMetadata,
    BuyerInfo,
    CodesMetadata,
    DateMetadata,
    PlaceOfPerformance,
)
from .models import CanadaIngestionRequest, TenderIngestionResult


@dataclass
class CanadaCkanClient:
    base_url: str

    def __post_init__(self):
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    def package_show(self, dataset_id: str) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/package_show?{parse.urlencode({'id': dataset_id})}"
        with urllib_request.urlopen(url, timeout=30, context=self._ssl_context) as response:  # noqa: S310
            return json.loads(response.read())

    def datastore_search(
        self,
        resource_id: str,
        *,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset,
        }
        if filters:
            params["filters"] = json.dumps(filters)
        url = f"{self.base_url.rstrip('/')}/datastore_search?{parse.urlencode(params)}"
        with urllib_request.urlopen(url, timeout=30, context=self._ssl_context) as response:  # noqa: S310
            return json.loads(response.read())


class CanadaBuysIngestor:
    """Ingestor that maps CanadaBuys CKAN datasets into tender metadata."""

    def __init__(self, client: CanadaCkanClient, config: CanadaOpenDataConfig) -> None:
        self.client = client
        self.config = config

    def ingest(self, request: CanadaIngestionRequest) -> TenderIngestionResult:
        tender_resource = self._ensure_resource_id(
            self.config.tender_dataset_id, self.config.tender_resource_id
        )
        filters = {"reference_number": request.reference_number}
        payload = self.client.datastore_search(tender_resource, filters=filters, limit=1)
        record = self._extract_record(payload)
        metadata = self._build_api_metadata(record)
        metadata.attachments.extend(self._derive_attachment_links(record))

        if self.config.contracts_resource_id:
            awards = self._fetch_contract_awards(request.reference_number)
            metadata.awards.extend(awards)

        return TenderIngestionResult(api_metadata=metadata, attachments=metadata.attachments)

    # ------------------------------------------------------------------
    def _ensure_resource_id(self, dataset_id: str, resource_id: Optional[str]) -> str:
        if resource_id:
            return resource_id
        package = self.client.package_show(dataset_id)
        resources = package.get("result", {}).get("resources", [])
        for entry in resources:
            if entry.get("datastore_active"):
                return entry["id"]
        raise ValueError(f"No datastore resource available for dataset {dataset_id}")

    def _extract_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        records = payload.get("result", {}).get("records", [])
        if not records:
            raise ValueError("CanadaBuys query returned no records")
        return records[0]

    def _build_api_metadata(self, record: Dict[str, Any]) -> APIMetadata:
        codes = CodesMetadata(
            naics=self._split_codes(record.get("naics_code")),
            gsin=self._split_codes(record.get("gsin_code")),
            unspsc=self._split_codes(record.get("unspsc_code")),
            classification=record.get("classification"),
        )

        buyer = BuyerInfo(
            name=record.get("organization_name"),
            department=record.get("department"),
            organization_path=self._split_codes(record.get("organization_path")),
            address=self._derive_address(record),
        )
        location = self._derive_location(record)

        dates = DateMetadata(
            posted=self._safe_date(record.get("publication_date")),
            response_deadline=self._safe_date(record.get("closing_date")),
            tender_start=self._safe_date(record.get("contract_start_date")),
            tender_end=self._safe_date(record.get("contract_end_date")),
        )

        metadata = APIMetadata(
            external_id=record.get("reference_number"),
            title=record.get("title_en") or record.get("title"),
            description=record.get("description_en") or record.get("description"),
            codes=codes,
            buyer=buyer,
            place_of_performance=PlaceOfPerformance(**location.__dict__),
            dates=dates,
            trade_agreements=self._split_codes(record.get("trade_agreement")),
        )
        return metadata

    def _derive_attachment_links(self, record: Dict[str, Any]) -> List[AttachmentMetadata]:
        attachments: List[AttachmentMetadata] = []
        for key, value in record.items():
            if not isinstance(value, str):
                continue
            if key.endswith("_url") or key.endswith("_link"):
                attachments.append(
                    AttachmentMetadata(
                        url=value,
                        filename=value.split("/")[-1],
                        label=key.replace("_", " ").title(),
                        source="API",
                    )
                )
        return attachments

    def _derive_address(self, record: Dict[str, Any]) -> Address:
        return Address(
            city=record.get("city"),
            state_province=record.get("province_state"),
            country=record.get("country"),
        )

    def _derive_location(self, record: Dict[str, Any]) -> Address:
        return Address(
            city=record.get("delivery_city") or record.get("city"),
            state_province=record.get("delivery_province_state") or record.get("province_state"),
            country=record.get("delivery_country") or record.get("country"),
        )

    def _safe_date(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value[:10]

    def _split_codes(self, raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        separators = [",", ";", "|"]
        for sep in separators:
            if sep in raw:
                return [part.strip() for part in raw.split(sep) if part.strip()]
        return [raw.strip()]

    def _fetch_contract_awards(self, reference_number: str) -> List[AwardMetadata]:
        if not self.config.contracts_resource_id:
            return []
        payload = self.client.datastore_search(
            self.config.contracts_resource_id,
            filters={"reference_number": reference_number},
            limit=100,
        )
        records = payload.get("result", {}).get("records", [])
        awards: List[AwardMetadata] = []
        for record in records:
            supplier_location = Address(
                city=record.get("supplier_city"),
                state_province=record.get("supplier_province_state"),
                country=record.get("supplier_country"),
            )
            awards.append(
                AwardMetadata(
                    award_id=record.get("contract_number"),
                    supplier_name=record.get("supplier_name"),
                    amount=self._parse_float(record.get("contract_value")),
                    currency=record.get("currency") or "CAD",
                    date=self._safe_date(record.get("contract_date")),
                    supplier_location=supplier_location,
                )
            )
        return awards

    def _parse_float(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None

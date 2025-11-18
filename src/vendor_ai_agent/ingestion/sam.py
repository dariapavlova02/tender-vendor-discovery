"""SAM.gov Opportunities API client and ingestor."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import parse, request as urllib_request

from ..config import SamApiConfig
from ..models import (
    APIMetadata,
    Address,
    AttachmentMetadata,
    AwardMetadata,
    BuyerInfo,
    CodesMetadata,
    DateMetadata,
    EstimatedValue,
    PlaceOfPerformance,
    SetAsideMetadata,
)
from .models import SamIngestionRequest, TenderIngestionResult


@dataclass
class SamClient:
    """Lightweight wrapper around the SAM Opportunities search endpoint."""

    base_url: str

    def search(self, api_key: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = parse.urlencode({"api_key": api_key, **params})
        url = f"{self.base_url}?{query}"
        with urllib_request.urlopen(url, timeout=30) as response:  # noqa: S310
            payload = response.read()
        return json.loads(payload)


class UsSamIngestor:
    """Fetches tender metadata from SAM and maps it to internal schema."""

    def __init__(self, client: SamClient, config: SamApiConfig) -> None:
        self.client = client
        self.config = config

    def ingest(self, request: SamIngestionRequest) -> TenderIngestionResult:
        if not self.config.api_key:
            raise ValueError("SAM API key is not configured")
        params: Dict[str, Any] = {
            "solnum": request.solicitation_number,
            "postedFrom": request.date_range.start,
            "postedTo": request.date_range.end,
            "limit": 1,
            "offset": 0,
        }
        payload = self.client.search(self.config.api_key, params)
        record = self._extract_single_record(payload)
        metadata = self._build_api_metadata(record)
        attachments = metadata.attachments
        return TenderIngestionResult(api_metadata=metadata, attachments=attachments)

    # ------------------------------------------------------------------
    def _extract_single_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("opportunitiesData") or []
        if not data:
            raise ValueError("No SAM opportunities returned for query")
        return data[0]

    def _build_api_metadata(self, record: Dict[str, Any]) -> APIMetadata:
        codes = CodesMetadata(
            naics=self._as_list(record.get("naicsCode")),
            unspsc=self._as_list(record.get("unspsc")),
            gsin=[],
            classification=record.get("classificationCode"),
        )

        buyer_address = self._map_address(record.get("officeAddress") or {})
        organization_path = self._split_path(record.get("fullParentPathName"))
        buyer = BuyerInfo(
            name=record.get("organizationName"),
            department=record.get("department"),
            organization_path=organization_path,
            address=buyer_address,
        )

        place_of_performance = self._map_address(record.get("placeOfPerformance") or {})

        dates = DateMetadata(
            posted=self._normalize_date(record.get("postedDate")),
            response_deadline=self._normalize_date(record.get("responseDeadLine")),
            tender_start=self._normalize_date(record.get("awardDate")),
            tender_end=self._normalize_date(record.get("archiveDate")),
        )

        set_aside = SetAsideMetadata(
            code=record.get("typeOfSetAside") or record.get("setAsideCode"),
            description=record.get("typeOfSetAsideDescription") or record.get("setAside"),
        )

        estimated_value = EstimatedValue(
            amount=self._parse_float(record.get("baseAndAllOptionsValue")),
            currency="USD",
        )

        awards = self._map_awards(record.get("award"))
        attachments = self._map_attachments(record.get("resourceLinks") or [])

        metadata = APIMetadata(
            external_id=record.get("solicitationNumber"),
            title=record.get("title"),
            description=record.get("description"),
            codes=codes,
            buyer=buyer,
            place_of_performance=PlaceOfPerformance(**place_of_performance.__dict__),
            dates=dates,
            set_aside=set_aside,
            estimated_value=estimated_value,
            trade_agreements=self._as_list(record.get("free_trade_agreement")),
            awards=awards,
            attachments=attachments,
        )
        return metadata

    def _map_address(self, raw: Dict[str, Any]) -> Address:
        return Address(
            street=raw.get("addressLine1") or raw.get("street"),
            city=raw.get("city") or raw.get("place"),
            state_province=raw.get("state") or raw.get("stateProvince"),
            postal_code=raw.get("zip") or raw.get("zipCode"),
            country=raw.get("country") or raw.get("countryCode"),
        )

    def _map_awards(self, raw_awards: Any) -> List[AwardMetadata]:
        awards: List[AwardMetadata] = []
        if not raw_awards:
            return awards
        if isinstance(raw_awards, list):
            iterable = raw_awards
        else:
            iterable = [raw_awards]
        for item in iterable:
            supplier = item.get("recipient") or {}
            location = self._map_address(supplier.get("location") or {})
            awards.append(
                AwardMetadata(
                    award_id=item.get("awardID") or item.get("awardId"),
                    supplier_name=supplier.get("name"),
                    amount=self._parse_float(item.get("amount")),
                    currency=item.get("currency") or "USD",
                    date=self._normalize_date(item.get("awardDate")),
                    supplier_location=location,
                )
            )
        return awards

    def _map_attachments(self, links: List[Dict[str, Any]]) -> List[AttachmentMetadata]:
        attachments: List[AttachmentMetadata] = []
        for link in links:
            attachments.append(
                AttachmentMetadata(
                    url=link.get("url"),
                    filename=link.get("title"),
                    mime_type=link.get("fileType"),
                    label=link.get("description"),
                    source="API",
                )
            )
        return attachments

    def _split_path(self, raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        if ">>" in raw:
            parts = raw.split(">>")
        elif ">" in raw:
            parts = raw.split(">")
        else:
            parts = [raw]
        return [part.strip() for part in parts if part.strip()]

    def _normalize_date(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        return raw[:10]

    def _parse_float(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _as_list(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v]
        return [str(value)]

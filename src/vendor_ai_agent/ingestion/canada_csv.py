"""Canada bulk CSV ingestion from CanadaBuys Open Data."""
from __future__ import annotations

import csv
import ssl
from dataclasses import dataclass
from io import StringIO
from typing import Dict, List, Optional
from urllib import request as urllib_request

import certifi

from ..models import (
    APIMetadata,
    Address,
    AttachmentMetadata,
    BuyerInfo,
    CodesMetadata,
    DateMetadata,
    PlaceOfPerformance,
)
from .models import CanadaIngestionRequest, TenderIngestionResult


@dataclass
class CanadaBuysCSVIngestor:
    """Ingestor that fetches CanadaBuys bulk CSV and searches by reference number."""

    csv_url: str = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"

    def __post_init__(self):
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    def ingest(self, request: CanadaIngestionRequest) -> TenderIngestionResult:
        record = self._fetch_record_by_reference(request.reference_number)
        if not record:
            raise ValueError(f"No tender found with reference: {request.reference_number}")
        
        metadata = self._build_api_metadata(record)
        attachments = self._extract_attachments(record)
        metadata.attachments.extend(attachments)
        
        return TenderIngestionResult(api_metadata=metadata, attachments=attachments)

    def _fetch_record_by_reference(self, reference_number: str) -> Optional[Dict[str, str]]:
        with urllib_request.urlopen(self.csv_url, timeout=60, context=self._ssl_context) as response:  # noqa: S310
            content = response.read().decode("utf-8-sig")
        
        reader = csv.DictReader(StringIO(content))
        for row in reader:
            if row.get("referenceNumber-numeroReference") == reference_number:
                return row
        return None

    def _build_api_metadata(self, record: Dict[str, str]) -> APIMetadata:
        codes = CodesMetadata(
            gsin=self._split_field(record.get("gsin-nibs", "")),
            unspsc=self._split_field(record.get("unspsc", "")),
        )

        buyer = BuyerInfo(
            name=record.get("contractingEntityName-nomEntitContractante-eng", ""),
            address=Address(
                street=record.get("contractingEntityAddressLine-ligneAdresseEntiteContractante-eng", ""),
                city=record.get("contractingEntityAddressCity-entiteContractanteAdresseVille-eng", ""),
                state_province=record.get("contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng", ""),
                postal_code=record.get("contractingEntityAddressPostalCode-entiteContractanteAdresseCodePostal", ""),
                country=record.get("contractingEntityAddressCountry-entiteContractanteAdressePays-eng", ""),
            ),
        )

        location = self._parse_location(record)
        dates = DateMetadata(
            posted=self._normalize_date(record.get("publicationDate-datePublication", "")),
            response_deadline=self._normalize_date(record.get("tenderClosingDate-appelOffresDateCloture", "")),
            tender_start=self._normalize_date(record.get("expectedContractStartDate-dateDebutContratPrevue", "")),
            tender_end=self._normalize_date(record.get("expectedContractEndDate-dateFinContratPrevue", "")),
        )

        trade_agreements = self._split_field(record.get("tradeAgreements-accordsCommerciaux-eng", ""))

        return APIMetadata(
            external_id=record.get("referenceNumber-numeroReference", ""),
            title=record.get("title-titre-eng", ""),
            description=record.get("tenderDescription-descriptionAppelOffres-eng", ""),
            codes=codes,
            buyer=buyer,
            place_of_performance=PlaceOfPerformance(**location.__dict__),
            dates=dates,
            trade_agreements=trade_agreements,
        )

    def _parse_location(self, record: Dict[str, str]) -> Address:
        regions_delivery = record.get("regionsOfDelivery-regionsLivraison-eng", "")
        parts = [p.strip() for p in regions_delivery.split(",")]
        
        city = ""
        state_province = ""
        country = "Canada"
        
        if len(parts) >= 2:
            city = parts[0]
            state_province = parts[1]
        elif len(parts) == 1 and parts[0]:
            state_province = parts[0]
        
        return Address(
            city=city,
            state_province=state_province,
            country=country,
        )

    def _extract_attachments(self, record: Dict[str, str]) -> List[AttachmentMetadata]:
        attachments: List[AttachmentMetadata] = []
        
        attachment_field = record.get("attachment-piecesJointes-eng", "")
        if attachment_field:
            urls = self._split_field(attachment_field)
            for url in urls:
                if url.startswith("http"):
                    filename = url.split("/")[-1] if "/" in url else "attachment"
                    attachments.append(
                        AttachmentMetadata(
                            url=url,
                            filename=filename,
                            label="Attachment",
                            source="CSV",
                        )
                    )
        
        notice_url = record.get("noticeURL-URLavis-eng", "")
        if notice_url:
            attachments.append(
                AttachmentMetadata(
                    url=notice_url,
                    filename="notice.html",
                    label="Notice URL",
                    source="CSV",
                )
            )
        
        return attachments

    def _split_field(self, value: str) -> List[str]:
        if not value:
            return []
        separators = ["*", ";", "|", ","]
        for sep in separators:
            if sep in value:
                return [part.strip() for part in value.split(sep) if part.strip()]
        return [value.strip()] if value.strip() else []

    def _normalize_date(self, date_str: str) -> Optional[str]:
        if not date_str:
            return None
        if "T" in date_str:
            return date_str.split("T")[0]
        return date_str[:10] if len(date_str) >= 10 else date_str

"""
PSPC Payments to Prime Contractors Loader

Dataset: PSPC payments made to prime contractors
Source: https://open.canada.ca/data/en/dataset/451b5114-d554-4eba-85a0-43c518e0641f
Updated: November 18, 2025
Format: CSV (5 columns)

Columns:
- procurement-id_id-approvisionnement: Contract ID
- Project-number_Numéro-de-projet: Project number
- Vendor-name_Nom-du-fournisseur: Vendor name
- Payment-date_Date-de-paiement: Payment date
- Proper-Invoice-Received-Date_date-de-réception-de-la-facture-en-règle: Invoice date

Expected: ~1,075 unique vendors from 31,387 payment records
Construction contractors with contracts >$100K managed by PSPC
"""

import csv
import json
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database.models import Vendor
from ..database.connection import get_session


class CanadaPSPCPaymentsLoader:
    def __init__(self):
        self.source = "canada_pspc_payments"
        self.stats = {
            "rows_processed": 0,
            "vendors_created": 0,
            "vendors_updated": 0,
            "payment_records_added": 0,
        }
    
    def _create_external_id(self, vendor_name: str) -> str:
        normalized_name = vendor_name.strip().upper()
        return f"{normalized_name}_PSPC_CONTRACTOR"
    
    def _parse_payment_record(self, row: dict) -> Optional[dict]:
        vendor_name = row.get("Vendor-name_Nom-du-fournisseur", "").strip()
        if not vendor_name:
            return None
        
        return {
            "vendor_name": vendor_name,
            "procurement_id": row.get("﻿procurement-id_id-approvisionnement", "").strip(),
            "project_number": row.get("Project-number_Numéro-de-projet", "").strip(),
            "payment_date": row.get("Payment-date_Date-de-paiement", "").strip(),
            "invoice_date": row.get("Proper-Invoice-Received-Date_date-de-réception-de-la-facture-en-règle", "").strip(),
        }
    
    def _aggregate_payments(self, csv_path: str) -> Dict[str, list]:
        """Aggregate all payments by vendor"""
        vendor_payments = {}
        
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.stats["rows_processed"] += 1
                
                payment = self._parse_payment_record(row)
                if not payment:
                    continue
                
                vendor_name = payment["vendor_name"]
                if vendor_name not in vendor_payments:
                    vendor_payments[vendor_name] = []
                
                vendor_payments[vendor_name].append({
                    "procurement_id": payment["procurement_id"],
                    "project_number": payment["project_number"],
                    "payment_date": payment["payment_date"],
                    "invoice_date": payment["invoice_date"],
                })
        
        return vendor_payments
    
    def _upsert_vendor(
        self,
        session: Session,
        vendor_name: str,
        payments: list,
    ) -> None:
        external_id = self._create_external_id(vendor_name)
        
        stmt = select(Vendor).where(Vendor.external_id == external_id)
        existing = session.execute(stmt).scalar_one_or_none()
        
        metadata_json = {
            "is_construction_contractor": True,
            "pspc_managed_contracts": True,
            "payment_count": len(payments),
            "payments": payments[:100],
        }
        
        if payments:
            latest_payment = max(payments, key=lambda p: p.get("payment_date", ""))
            metadata_json["latest_payment_date"] = latest_payment.get("payment_date")
        
        if existing:
            existing.metadata_json = json.dumps(metadata_json)
            self.stats["vendors_updated"] += 1
        else:
            vendor = Vendor(
                external_id=external_id,
                legal_name=vendor_name,
                source=self.source,
                metadata_json=json.dumps(metadata_json),
            )
            session.add(vendor)
            self.stats["vendors_created"] += 1
        
        self.stats["payment_records_added"] += len(payments)
    
    def load(self, session: Session, csv_path: str) -> dict:
        print(f"Loading PSPC payments from: {csv_path}")
        
        vendor_payments = self._aggregate_payments(csv_path)
        print(f"Found {len(vendor_payments):,} unique vendors")
        
        for i, (vendor_name, payments) in enumerate(vendor_payments.items(), 1):
            if i % 100 == 0:
                print(f"Processing vendor {i}/{len(vendor_payments)}...")
                session.commit()
            
            self._upsert_vendor(session, vendor_name, payments)
        
        session.commit()
        print(f"Completed: {self.stats['vendors_created']} created, {self.stats['vendors_updated']} updated")
        
        return self.stats


def load_pspc_payments(session: Session, csv_path: str) -> dict:
    loader = CanadaPSPCPaymentsLoader()
    return loader.load(session, csv_path)


if __name__ == "__main__":
    csv_path = "data/canada_sources/pspc_payments/pspc_payments.csv"
    
    with get_session() as session:
        stats = load_pspc_payments(session, csv_path)
        
        print("\n" + "=" * 80)
        print("INGESTION COMPLETE")
        print("=" * 80)
        print(f"Rows processed:         {stats['rows_processed']:,}")
        print(f"Vendors created:        {stats['vendors_created']:,}")
        print(f"Vendors updated:        {stats['vendors_updated']:,}")
        print(f"Payment records added:  {stats['payment_records_added']:,}")
        print("=" * 80)

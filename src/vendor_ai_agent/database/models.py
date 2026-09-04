from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Date,
    DateTime,
    Text,
    Boolean,
    JSON,
    Index,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IngestionChunk(Base):
    """Completed CSV chunks, committed atomically with their vendor updates."""

    __tablename__ = "ingestion_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("source", "digest", name="uq_ingestion_chunk"),)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    uei: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    duns: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    cage_code: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    dba_name: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    
    country: Mapped[Optional[str]] = mapped_column(String(2))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    city: Mapped[Optional[str]] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    
    business_types: Mapped[Optional[str]] = mapped_column(JSON)
    
    is_small_business: Mapped[bool] = mapped_column(Boolean, default=False)
    is_woman_owned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_veteran_owned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_minority_owned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_8a: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hubzone: Mapped[bool] = mapped_column(Boolean, default=False)
    
    employee_count_range: Mapped[Optional[str]] = mapped_column(String(50))
    total_contract_value: Mapped[Optional[float]] = mapped_column(Float)
    contract_count: Mapped[Optional[int]] = mapped_column(Integer)
    first_contract_date: Mapped[Optional[date]] = mapped_column(Date)
    last_contract_date: Mapped[Optional[date]] = mapped_column(Date)
    contract_history_json: Mapped[Optional[str]] = mapped_column(JSON)
    
    metadata_json: Mapped[Optional[str]] = mapped_column(JSON)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    naics_codes: Mapped[list["VendorNAICS"]] = relationship(
        "VendorNAICS", back_populates="vendor", cascade="all, delete-orphan"
    )
    gsin_codes: Mapped[list["VendorGSIN"]] = relationship(
        "VendorGSIN", back_populates="vendor", cascade="all, delete-orphan"
    )
    unspsc_codes: Mapped[list["VendorUNSPSC"]] = relationship(
        "VendorUNSPSC", back_populates="vendor", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["VendorContact"]] = relationship(
        "VendorContact", back_populates="vendor", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_vendor_source_external_id"),
        Index("ix_vendor_location", "country", "state", "city"),
        Index("ix_vendor_certifications", "is_small_business", "is_woman_owned", "is_veteran_owned"),
    )


class VendorNAICS(Base):
    __tablename__ = "vendor_naics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    naics_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    naics_description: Mapped[Optional[str]] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="naics_codes")

    __table_args__ = (
        UniqueConstraint("vendor_id", "naics_code", name="uq_vendor_naics"),
        Index("ix_vendor_naics_lookup", "naics_code", "vendor_id"),
    )


class VendorGSIN(Base):
    __tablename__ = "vendor_gsin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    gsin_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    gsin_description: Mapped[Optional[str]] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="gsin_codes")

    __table_args__ = (
        UniqueConstraint("vendor_id", "gsin_code", name="uq_vendor_gsin"),
        Index("ix_vendor_gsin_lookup", "gsin_code", "vendor_id"),
    )


class VendorUNSPSC(Base):
    __tablename__ = "vendor_unspsc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    unspsc_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    unspsc_description: Mapped[Optional[str]] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="unspsc_codes")

    __table_args__ = (
        UniqueConstraint("vendor_id", "unspsc_code", name="uq_vendor_unspsc"),
        Index("ix_vendor_unspsc_lookup", "unspsc_code", "vendor_id"),
    )


class VendorContact(Base):
    __tablename__ = "vendor_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    
    first_name: Mapped[Optional[str]] = mapped_column(String(200))
    last_name: Mapped[Optional[str]] = mapped_column(String(200))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_score: Mapped[Optional[int]] = mapped_column(Integer)
    
    metadata_json: Mapped[Optional[str]] = mapped_column(JSON)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="contacts")

    __table_args__ = (
        Index("ix_vendor_contact_email", "vendor_id", "email"),
    )


class APICache(Base):
    __tablename__ = "api_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    cache_key: Mapped[str] = mapped_column(String(500), nullable=False)
    
    response_data: Mapped[str] = mapped_column(JSON, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("source", "cache_key", name="uq_api_cache_source_key"),
        Index("ix_api_cache_expiry", "source", "expires_at"),
    )

"""Enrichment providers available to the pipeline."""
from .base import BaseEnrichmentProvider
from .static_contacts import StaticContactsProvider

__all__ = ["BaseEnrichmentProvider", "StaticContactsProvider"]

# Data and provenance

## Included material

| Material | Purpose | Status |
| --- | --- | --- |
| [`ODBus Metadata.pdf`](../data/canada_sources/ODBus_v1/ODBus%20Metadata.pdf) | Source-schema reference retained from the original project | Historical third-party metadata, not a vendor dataset |
| [`field_mappings.json`](../data/canada_sources/_metadata/field_mappings.json) | Historical import field mapping notes | Paths, counts and ingestion status describe the original environment |

The mapping counts and coverage statements have not been revalidated. Exact retrieval dates
and usage terms are not fully recorded. Included third-party material is not presented as a
current procurement feed. The longer historical research notes remain in Git history.

The current tree excludes client tender packages, stakeholder handover documents, operational
logs and serialized job payloads. Removing a file from the tree does not erase Git history.
No original customer records are required for the offline tests. Production input documents,
supplier datasets and resulting shortlists are not distributed with this repository.

## Canada contract imports

The loader reads bilingual CSV field names from a locally supplied export. Key fields include:

- `supplierLegalName-nomLegalFournisseur-eng`
- `supplierAddressPostalCode-fournisseurAdresseCodePostal`
- `contractNumber-numeroContrat`
- `totalContractValue-valeurTotaleContrat`
- `contractAwardDate-dateAttributionContrat`
- `gsin-nibs` and `unspsc`

Refer to the actual [loader](../src/vendor_ai_agent/ingestion/canada_contracts.py) when preparing
an export; the older field-mapping notes cover several sources and are not its executable schema.

## Import boundaries

Successful chunks are fingerprinted and recorded atomically with their database updates.
Replaying the same parsed rows in the same order and chunk boundaries skips those chunks.
An interrupted import can resume without adding already committed chunks again.

This protection starts when the chunk ledger is introduced. It cannot identify previously
imported rows in an older database, overlapping extracts with different chunk boundaries,
or amendments to a contract. Use a fresh database for reproducible imports; a general
contract-level upsert/reconciliation model is outside this cleanup.

Vendor totals remain source-derived aggregates. They are not proof of current capability,
eligibility or the availability of a listed contact.

## Licensing boundary

The project's [MIT License](../LICENSE) covers its code and original documentation. It does
not relicense third-party datasets, source metadata (including the ODBus metadata PDF),
or content retrieved from company websites or external APIs. Those materials retain their
own applicable terms. Source retrieval and usage terms that are not recorded above remain
unverified; the project license does not supply the missing permissions.

"""Keyword dictionaries and regex patterns for document processing heuristics."""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Section headings vs. contextual hints
# ---------------------------------------------------------------------------

SECTION_HEADING_PATTERNS = {
    "scope_of_work": [
        "scope of work",
        "statement of work",
        "sow",
        "project scope",
        "work description",
        "description of work",
        "project overview",
        "background and scope",
    ],
    "mandatory_requirements": [
        "mandatory requirements",
        "mandatory criteria",
        "minimum requirements",
        "minimum mandatory",
        "must meet requirements",
        "pre-qualification requirements",
    ],
    "vendor_qualifications": [
        "vendor qualifications",
        "bidder qualifications",
        "proponent qualifications",
        "qualification requirements",
        "experience and qualifications",
        "eligibility requirements",
        "proponent experience",
        "contractor experience",
        "minimum experience",
    ],
    "technical_requirements": [
        "technical requirements",
        "technical specifications",
        "specifications",
        "technical spec",
        "performance requirements",
        "performance specifications",
        "technical scope",
    ],
    "evaluation_criteria": [
        "evaluation criteria",
        "evaluation and scoring",
        "basis of award",
        "bid evaluation",
        "selection criteria",
        "rated criteria",
        "scoring matrix",
    ],
    "location_details": [
        "location of work",
        "place of performance",
        "site location",
        "site information",
        "work site",
        "delivery location",
        "place of delivery",
    ],
    "timeline_details": [
        "project schedule",
        "timeline",
        "milestones",
        "schedule of work",
        "completion schedule",
        "delivery schedule",
        "contract duration",
        "term of contract",
    ],
}

SECTION_CONTEXT_HINTS = {
    "scope_of_work": [
        "includes but not limited to",
        "the contractor shall perform",
        "work to be performed",
        "the work includes",
        "services to be provided",
    ],
    "mandatory_requirements": [
        "shall be considered non-compliant",
        "must submit",
        "failure to provide",
        "is required to",
        "must meet all",
    ],
    "vendor_qualifications": [
        "past experience",
        "similar projects",
        "references",
        "completed at least",
        "proven track record",
        "prior work",
    ],
    "technical_requirements": [
        "shall conform to",
        "must comply with",
        "in accordance with",
        "technical standard",
        "minimum rating",
        "acceptable manufacturers",
    ],
    "evaluation_criteria": [
        "points will be awarded",
        "scored out of",
        "weighting",
        "evaluation team",
        "evaluated based on",
    ],
    "timeline_details": [
        "substantial completion",
        "final completion",
        "calendar days",
        "business days",
        "no later than",
        "within",
    ],
}

NOISE_SECTION_HEADINGS = [
    "instructions to bidders",
    "general conditions",
    "terms and conditions",
    "insurance requirements",
    "bonding requirements",
    "appendices",
    "forms",
    "tender form",
    "bid form",
]

# ---------------------------------------------------------------------------
# Sector-specific keywords
# ---------------------------------------------------------------------------

SECTOR_KEYWORDS = {
    "construction": [
        "construction",
        "roof",
        "roofing",
        "building envelope",
        "insulation",
        "mechanical room",
        "hvac",
        "plumbing",
        "electrical",
        "general contractor",
        "gc services",
        "renovation",
        "retrofit",
        "structural steel",
        "concrete",
        "asphalt",
        "paving",
    ],
    "ammo_supply": [
        "ammunition",
        "ammo",
        "cartridge",
        "rounds",
        "munitions",
        "ball ammunition",
        "training ammunition",
        "duty ammunition",
        "calibre",
        "caliber",
        "grain",
        "fps",
        "saami",
        "cip",
        "nato spec",
    ],
    "it": [
        "it services",
        "software",
        "application",
        "web portal",
        "saas",
        "cloud",
        "network",
        "infrastructure",
        "database",
        "data center",
        "cybersecurity",
        "support and maintenance",
        "help desk",
    ],
}

TECHNICAL_KEYWORDS = {
    "construction": [
        "tpo membrane",
        "epdm",
        "bitumen",
        "torch-on",
        "r-value",
        "vapour barrier",
        "vapor barrier",
        "flashing",
        "parapet",
        "insulation board",
        "rigid insulation",
        "polyisocyanurate",
        "roof deck",
        "roof drains",
        "fall protection",
    ],
    "ammo_supply": [
        "full metal jacket",
        "fmj",
        "hollow point",
        "hp",
        "jacketed",
        "lead-free",
        "non-corrosive primer",
        "brass case",
        "steel case",
        "reloadable",
        "velocity",
        "muzzle velocity",
        "chamber pressure",
        "saami standard",
        "cip standard",
    ],
    "it": [
        "api integration",
        "rest api",
        "soap",
        "microservices",
        "high availability",
        "redundancy",
        "sla",
        "uptime",
        "latency",
        "load balancing",
        "virtual machine",
        "hypervisor",
        "container",
        "kubernetes",
    ],
}

# ---------------------------------------------------------------------------
# Licenses, certifications, special statuses
# ---------------------------------------------------------------------------

LICENSE_PATTERNS = [
    "licensed",
    "license",
    "licence",
    "licensed in",
    "hold a valid",
    "must hold",
    "must be licensed",
    "shall be licensed",
    "trade license",
    "contractor license",
    "electrical contractor licence",
    "plumbing licence",
]

CERTIFICATION_PATTERNS = [
    "iso",
    "iso 9001",
    "iso 14001",
    "saami",
    "cip",
    "csa",
    "astm",
    "cor certification",
    "certificate of recognition",
    "ulc",
    "ul listed",
    "nema",
]

SPECIAL_STATUS_PATTERNS = [
    "indigenous supplier",
    "indigenous-owned",
    "aboriginal business",
    "first nations",
    "women-owned",
    "woman-owned",
    "women owned",
    "minority-owned",
    "small business",
    "service-disabled veteran-owned",
    "sdvosb",
    "hubzone",
]

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

EXPERIENCE_REGEXES = [
    re.compile(r"(\d+)\s+(years|year)\s+of\s+experience", re.IGNORECASE),
    re.compile(r"minimum\s+of\s+(\d+)\s+(years|year)\s+experience", re.IGNORECASE),
    re.compile(r"at\s+least\s+(\d+)\s+(years|year)\s+experience", re.IGNORECASE),
    re.compile(r"completed\s+at\s+least\s+(\d+)\s+projects", re.IGNORECASE),
]

VOLUME_REGEXES = [
    re.compile(r"(\d[\d,\.]+)\s*(square\s*meters?|sq\.?\s*m|m2)", re.IGNORECASE),
    re.compile(r"(\d[\d,\.]+)\s*(square\s*feet|sq\.?\s*ft|ft2)", re.IGNORECASE),
    re.compile(r"(\d[\d,\.]+)\s*(rounds|cartridges|pcs|pieces)", re.IGNORECASE),
    re.compile(r"(\d[\d,\.]+)\s*(kg|kilograms?|lbs|pounds?)", re.IGNORECASE),
]

TIMELINE_REGEXES = [
    re.compile(r"within\s+(\d+)\s+(calendar|business)\s+days", re.IGNORECASE),
    re.compile(r"(\d+)\s+(calendar|business)\s+days\s+from\s+(award|notice)", re.IGNORECASE),
    re.compile(r"no\s+later\s+than\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", re.IGNORECASE),
    re.compile(r"substantial\s+completion\s+by\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", re.IGNORECASE),
]
